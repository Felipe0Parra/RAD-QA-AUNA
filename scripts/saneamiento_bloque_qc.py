"""SA1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-SA1, [[DA-38]]): resuelve las
claves duplicadas activas que el hallazgo H2 (§2.3 del plan) encontró en 8
tablas del bloque de QC -- residuo anterior a M2 (11-08-2026), concentrado
en 5 controles antiguos (`ref` 15, 16, 30, 31, 33).

Regla DA-38 (resuelta por el físico 2026-08-13, "me gusta tu idea, me
parece lo apropiado"): de cada grupo de filas ACTIVAS que comparten la
misma clave natural, gana el bloque más reciente (mayor `rowid`) -- el
resto pasa a `activo = 0`. NINGUNA fila se borra. Coherente con lo que la
app ya muestra hoy: `Traerinfo_conos`/`Traerinfo_cunas` ya desempatan con
`ORDER BY ... id DESC`, así que el bloque que este saneamiento deja activo
es el mismo que el físico ya ve en pantalla.

Ensayado sobre copia real de `BaseDatosQA(Rebuild_13-08-2026).db` antes de
comprometerse (§2.6 del plan): 57 filas anuladas, `censo.total` idéntico en
las 21 tablas (cero pérdidas), `PRAGMA integrity_check = ok`,
`foreign_key_check` sin aumento, y los 21 índices UNIQUE de CL1 se crearon
sin fallos sobre el resultado -- la prueba de que la resolución es correcta.

Claves naturales (§2.3 del plan) -- no se derivan del esquema porque la
clave del bloque no es "toda la fila", es la combinación de columnas que
identifica el mismo bloque lógico dentro de un control:

MI2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI2, movido aquí desde IV3 por la
corrección de ejecución de §4.4: antes de que `MI1` exista, `activo` no
existe en estas tablas y `_grupos_duplicados` rompería con
`OperationalError: no such column: activo`, sin ningún `try/except` que lo
contenga -- a diferencia de `crear_indices`, que sí valida la columna antes
de usarla) añade las 4 tablas con duplicados reales medidos en §2.8 del
plan: `analisis_placa_verificaciones` (4 filas a anular),
`analisis_placa_correcciones` (8), `indicadores_brazo` (12),
`indicadores_angulares_colimador` (6). Mismas claves que
`scripts/indices_bloque_qc.py::CLAVES_INDICE` declara para estas tablas --
el índice UNIQUE de `MI3` no podría crearse si quedara un duplicado sin
sanear, así que su creación exitosa vuelve a ser la prueba de que este
saneamiento funcionó (mismo criterio que ya vale para las 8 originales).

MI3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI3) añade las 4 diarias, con **33
fechas duplicadas reales** medidas en §2.8 del plan (`aceleradorlineal_ix`
30, `aceleradorlineal_600` 2, `braqui` 1 -- residuo anterior a la guarda de
reemplazo, mismo ID de usuario con dos IDs distintos). Su clave es la
EXPRESIÓN `DATE(date)` (normaliza la columna `date` TEXT), no una columna
-- `_columna_referenciada()` (scripts/indices_bloque_qc.py, la misma
función que usa `crear_indices()` para no duplicar el criterio) reconoce
la forma `FUNC(columna)` y evita entrecomillarla como identificador al
construir el `SELECT`.
"""
import sqlite3

from scripts.indices_bloque_qc import _columna_referenciada

CLAVES_NATURALES = {
    "control_cunas": ("ref", "angulo"),
    "control_conos": ("ref", "medida"),
    "equipos_medicion": ("ref", "tipo_camara"),
    "analisis_placa_franjas": ("ref", "franja"),
    "tamano_campo": ("ref", "campo_nominal"),
    "HC_indicadores_camilla": ("ref", "id_energia", "ubicacion", "desplazamiento"),
    "HC_indicadores_colimador": ("ref", "id_energia", "nivel"),
    "HC_indicadores_laser": ("ref", "id_energia", "ubicacion"),
    # MI2: las 4 tablas con duplicados reales medidos en §2.8 del plan --
    # mismas claves que CLAVES_INDICE (scripts/indices_bloque_qc.py).
    "analisis_placa_verificaciones": ("ref", "tipo"),
    "analisis_placa_correcciones": ("ref", "vertice"),
    "indicadores_brazo": ("ref", "nivel"),
    "indicadores_angulares_colimador": ("ref", "nivel"),
    # MI3: las 4 diarias, clave por expresión (ver docstring del módulo).
    "aceleradorlineal_600": ("DATE(date)",),
    "aceleradorlineal_ix": ("DATE(date)",),
    "halcyon": ("DATE(date)",),
    "braqui": ("DATE(date)",),
}


def _grupos_duplicados(con, tabla, clave):
    """Grupos de filas ACTIVAS que comparten la misma clave natural, con
    más de una fila -- devuelve [(valores_clave, [rowids ordenados asc])]."""
    columnas = ", ".join(
        c if _columna_referenciada(c) else f'"{c}"' for c in clave)
    filas = con.execute(f"""
        SELECT rowid, {columnas} FROM "{tabla}"
        WHERE activo IS NULL OR activo = 1
        ORDER BY rowid
    """).fetchall()

    grupos = {}
    for fila in filas:
        rowid, valores = fila[0], fila[1:]
        grupos.setdefault(valores, []).append(rowid)
    return [(valores, rowids) for valores, rowids in grupos.items() if len(rowids) > 1]


def sanear_tabla(con, tabla, usuario=None, ruta_db=None, dry_run=False):
    """Resuelve los duplicados de UNA tabla. Devuelve la lista de filas
    anuladas: [{"tabla", "rowid", "clave", "gano_rowid"}, ...]."""
    from services.audit_minimo import registrar, ACCION_ANULAR

    clave = CLAVES_NATURALES[tabla]
    anuladas = []
    for valores_clave, rowids in _grupos_duplicados(con, tabla, clave):
        rowid_ganador = max(rowids)
        clave_legible = dict(zip(clave, valores_clave))
        # MI3: las diarias no tienen "ref" -- su única columna de clave
        # (la fecha normalizada) es igual de trazable para la auditoría.
        ref = clave_legible.get("ref")
        if ref is None and len(clave_legible) == 1:
            ref = str(next(iter(clave_legible.values())))
        for rowid in rowids:
            if rowid == rowid_ganador:
                continue
            entrada = {"tabla": tabla, "rowid": rowid, "clave": clave_legible,
                       "gano_rowid": rowid_ganador}
            anuladas.append(entrada)
            if dry_run:
                continue
            con.execute(f'UPDATE "{tabla}" SET activo = 0 WHERE rowid = ?', (rowid,))
            # Commit antes de auditar: registrar() abre su propia conexión
            # (mismo patrón que saneamiento_equipos_h26.py) -- si la UPDATE
            # de esta fila sigue sin confirmar, esa segunda conexión choca
            # con "database is locked".
            con.commit()
            registrar(usuario, ACCION_ANULAR, tabla=tabla, ref=ref,
                      detalle=(f"SA1: clave duplicada {clave_legible} -- "
                               f"gana rowid={rowid_ganador} (más reciente), "
                               f"esta fila (rowid={rowid}) queda histórica"),
                      ruta_db=ruta_db)
    return anuladas


def verificar_sin_duplicados_activos(con):
    """SA2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-SA2): guardián permanente,
    independiente del índice UNIQUE de CL1 (que todavía no existe cuando
    SA1 corre). Devuelve la lista de violaciones -- vacía si las 8 tablas
    tienen, cada una, a lo sumo UNA fila activa por clave natural.
    Cada violación: {"tabla", "clave", "rowids"} (los rowids que quedaron
    activos en conflicto)."""
    violaciones = []
    for tabla, clave in CLAVES_NATURALES.items():
        for valores_clave, rowids in _grupos_duplicados(con, tabla, clave):
            violaciones.append({
                "tabla": tabla, "clave": dict(zip(clave, valores_clave)),
                "rowids": rowids})
    return violaciones


def sanear_bloque_qc(ruta_db, usuario=None, dry_run=False):
    """Aplica `sanear_tabla` a las 8 tablas de CLAVES_NATURALES sobre
    `ruta_db`. Idempotente: una segunda corrida no encuentra grupos (cada
    clave ya tiene una sola fila activa) y no anula nada más."""
    con = sqlite3.connect(ruta_db)
    try:
        anuladas = []
        for tabla in CLAVES_NATURALES:
            anuladas.extend(
                sanear_tabla(con, tabla, usuario=usuario, ruta_db=ruta_db,
                             dry_run=dry_run))
        return anuladas
    finally:
        con.close()
