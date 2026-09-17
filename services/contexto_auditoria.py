"""T.4 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §5): resuelve, para cada fila
de `audit_log`, de qué MÁQUINA y de qué FECHA es el control al que se
refiere -- sin almacenar nada nuevo. Decisión del 09-09: *"un valor derivado
de columnas ya guardadas no se almacena, se construye al mostrarlo"* -- no se
toca `audit_log` ni el esquema; esto solo LEE.

`audit_log.ref` tiene tres formas según la tabla (§0.8 del plan, medido
contra la BD real):

  - **id entero que cuelga de `controles`** (`tamano_campo`, `indicadores_
    brazo`, `control_cunas`, `equipos_medicion`, `dosimetriaMen`,
    `preguntas`, `controles` mismo, ...): se resuelve `controles.equipo` +
    `controles.fecha`. La pertenencia se DERIVA consultando
    `PRAGMA foreign_key_list` de la tabla citada (¿tiene un borde hacia
    `controles`?), no de una lista escrita a mano -- igual que
    `services/lectura_vigente.py::cierre_transitivo_fk` deriva el inventario
    de tablas versionables (DA-40). Deliberadamente se exige el borde
    DIRECTO: una tabla dos saltos de `controles` (p. ej. las de Catphan/TAC,
    colgadas de `pruebas`, o las de Picket Fence, colgadas de
    `configuracion_picketfence`) tendría un `ref` que apunta a la tabla
    intermedia, no a `controles.id` -- resolverla iría a la fila equivocada.
    Hoy [medido] ninguna de esas tablas aparece nunca en `audit_log.tabla`;
    si alguna vez apareciera, cae en la categoría "desconocida" -- en blanco,
    no un valor inventado.
  - **tabla diaria** (`aceleradorlineal_600`, `aceleradorlineal_ix`,
    `halcyon`, `braqui`): la máquina la dice la propia tabla (son raíces sin
    padre en el grafo de QC, DA-40); la fecha ES el propio `ref`.
  - **`TipoCalibracion` y sus hijas** (`SistemaMedicion`,
    `CondicionesMedicion`, `MaximosCamaras`, `LecturasMaximos`,
    `ResultadosActividad`): máquina = "Braquiterapia" (literal, es la única
    máquina de braquiterapia), fecha = `TipoCalibracion.fecha` -- el `ref`
    de una hija también apunta al `id` de `TipoCalibracion` (EB2b: "su id
    (autoincrement) es el ref que heredan las 5 tablas hijas").
  - **cualquier otra cosa** (`equipos`, `users`, `backup`, `login`, una
    tabla desconocida como `analisis_placa600` -- medido en producción,
    citada en `audit_log` pero sin tabla real que la respalde): en blanco.
    Es la respuesta HONESTA, no un hueco -- inventar un valor sería peor
    que no decir nada.

DA-47: la lectura de `controles`/`TipoCalibracion` por `id` NO filtra
`activo` -- un control o una calibración anulados deben seguir
identificándose en su propio rastro de auditoría.

Resuelve EN LOTE (dos consultas `IN (...)`, más una `PRAGMA foreign_key_
list` por cada nombre de tabla DISTINTO presente en el lote -- acotado por
cuántas tablas distintas aparecen, nunca por cuántas filas hay), no una
consulta por fila -- con 500 filas de audit_log eso serían 500 consultas.

Módulo puro: no importa PyQt5, no abre ninguna conexión por sí mismo --
recibe una ya abierta (con `.execute()`, el mismo contrato que usa
`console_logs.py` con `Conexion().conectar()`), así que es trivial de
probar contra una BD temporal real.
"""

TABLAS_DIARIAS_A_MAQUINA = {
    "aceleradorlineal_600": "Clinac 600",
    "aceleradorlineal_ix": "Clinac iX",
    "halcyon": "Halcyon",
    "braqui": "Braquiterapia",
}

_EN_BLANCO = ("", "")


def _clasificar_tabla(tabla, con):
    """Devuelve 'diaria' | 'controles' | 'tipo_calibracion' | 'desconocida'
    para una tabla dada, derivándolo del grafo de FK cuando hace falta."""
    if tabla in TABLAS_DIARIAS_A_MAQUINA:
        return "diaria"
    if tabla == "controles":
        return "controles"
    if tabla == "TipoCalibracion":
        return "tipo_calibracion"
    try:
        fks = con.execute(f'PRAGMA foreign_key_list("{tabla}")').fetchall()
    except Exception:
        return "desconocida"
    # fk[2] es la tabla PADRE de cada borde -- exigimos el borde DIRECTO,
    # no transitivo (ver docstring del módulo: dos saltos es demasiado
    # ambiguo para resolver con garantías).
    objetivos = {fk[2] for fk in fks}
    if "controles" in objetivos:
        return "controles"
    if "TipoCalibracion" in objetivos:
        return "tipo_calibracion"
    return "desconocida"


def _entero_o_none(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def contexto_de_auditoria(filas, con, nombre_canonico=None):
    """`filas`: iterable de `(tabla, ref)` -- lo que `audit_log` ya trae.
    `con`: conexión abierta con `.execute(sql, params)` (sqlite3 puro).
    `nombre_canonico`: normalizador de nombre de máquina
    (`services/nombres_acelerador.py::nombre_canonico` por defecto, DA-15 --
    inyectable para no acoplar el test a PyQt5 si no hace falta).

    Devuelve `{(tabla, ref): (equipo, fecha)}`. Una clave ausente, o un valor
    `("", "")`, significa "no se pudo identificar" -- nunca un `KeyError` ni
    una excepción."""
    if nombre_canonico is None:
        from services.nombres_acelerador import nombre_canonico as _nc
        nombre_canonico = _nc

    pares = {(tabla, ref) for tabla, ref in filas if tabla}
    if not pares:
        return {}

    tablas_distintas = {tabla for tabla, _ in pares}
    clasificacion = {tabla: _clasificar_tabla(tabla, con) for tabla in tablas_distintas}

    refs_controles = set()
    refs_tipo_calibracion = set()
    for tabla, ref in pares:
        categoria = clasificacion[tabla]
        if categoria == "controles":
            entero = _entero_o_none(ref)
            if entero is not None:
                refs_controles.add(entero)
        elif categoria == "tipo_calibracion":
            entero = _entero_o_none(ref)
            if entero is not None:
                refs_tipo_calibracion.add(entero)

    datos_controles = {}
    if refs_controles:
        marcas = ",".join("?" * len(refs_controles))
        for id_, equipo, fecha in con.execute(
                f"SELECT id, equipo, fecha FROM controles WHERE id IN ({marcas})",
                tuple(refs_controles)).fetchall():
            datos_controles[id_] = (nombre_canonico(equipo), fecha)

    datos_tipo_calibracion = {}
    if refs_tipo_calibracion:
        marcas = ",".join("?" * len(refs_tipo_calibracion))
        for id_, fecha in con.execute(
                f"SELECT id, fecha FROM TipoCalibracion WHERE id IN ({marcas})",
                tuple(refs_tipo_calibracion)).fetchall():
            datos_tipo_calibracion[id_] = ("Braquiterapia", fecha)

    contexto = {}
    for tabla, ref in pares:
        categoria = clasificacion[tabla]
        if categoria == "diaria":
            contexto[(tabla, ref)] = (TABLAS_DIARIAS_A_MAQUINA[tabla], ref)
        elif categoria == "controles":
            entero = _entero_o_none(ref)
            contexto[(tabla, ref)] = (
                datos_controles.get(entero, _EN_BLANCO) if entero is not None
                else _EN_BLANCO)
        elif categoria == "tipo_calibracion":
            entero = _entero_o_none(ref)
            contexto[(tabla, ref)] = (
                datos_tipo_calibracion.get(entero, _EN_BLANCO) if entero is not None
                else _EN_BLANCO)
        else:
            contexto[(tabla, ref)] = _EN_BLANCO

    return contexto
