"""EB5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB5): tripwire permanente de
escritura -- la contraparte de ES1 (`test_le4_lecturas_filtran_activo.py`)
para el lado de escritura. ES1 vigila "¿toda lectura filtra el bloque
vigente?"; EB5 vigila "¿algo BORRA o MUTA EN SITIO el bloque vigente en vez
de anularlo e insertar uno nuevo?" -- el patrón G1/G2 (§2.4 del plan) que
`crear_algo`, `guardar_resultado_CambioFuente` y las 8 funciones de MLC
tenían, y que EB1/EB2/EB4 existen para eliminar.

Mismo mecanismo AST que ES1 (recorre TODO el árbol de producción, resuelve
SQL armado en variable vía `services.lectura_vigente.resolver_argumento_execute`,
trata lo irresoluble como "opaco"), pero con un criterio nuevo
(`lectura_vigente.analizar_escritura`): un `DELETE FROM <tabla>` o un
`UPDATE <tabla> SET <col>` donde `<col>` es cualquier columna que NO sea
`activo`, sobre una tabla del bloque de QC.

**Por qué no se intenta distinguir "legítimo" de "bug" con una heurística
sobre el WHERE** (a diferencia de ES1, que sí usa DA-47 para eso del lado
de lectura): del lado de escritura conviven, sobre las MISMAS tablas, dos
mecanismos genuinamente distintos y ambos legítimos --

  1. El contrato anular+insertar (EB1): reemplaza el bloque entero, nunca
     muta una columna de datos del bloque anterior.
  2. La corrección con rastro (A3, [[DA-05]]/[[DA-07]]/[[DA-08]]): edición
     DIRECTA de un campo ya guardado, con auditoría (`guardarEdicion` y sus
     primos QtSql), decidida como mecanismo PERMANENTE, no un resto por
     limpiar -- "se conservan los DOS caminos de corrección" (DA-08).

Ninguna forma sintáctica del SQL distingue los dos con garantías: los dos
pueden ir por `WHERE id = ?` o por una clave de bloque. La única frontera
real es "¿qué función es, y decidimos guardarla así?" -- que es
precisamente lo que una lista revisada a mano registra, igual que ES1 hace
con sus tablas dinámicas/opacas. Un sitio NUEVO (no revisado) pone el test
en rojo y exige la misma decisión explícita que cualquier otro tripwire de
este plan.

Tres categorías, mismo criterio que ES1:

1. **Literal**: `execute()`/`executemany()`/`prepare()` con SQL resuelto
   (directo o vía variable) que nombra una tabla real tras `DELETE FROM` o
   `UPDATE ... SET`.
2. **Dinámico**: el nombre de tabla (o de columna, en el SET) se arma en
   tiempo de ejecución -- marcador `{DYN}`, igual que ES1.
3. **Opaco**: el argumento de `execute()` no es resoluble en absoluto (bucle,
   `try`, reasignación compleja) -- se censa TODO sitio así, sea o no
   DELETE/UPDATE, exactamente como hace `SITIOS_OPACOS_PERMITIDOS` de ES1;
   la mayoría son INSERT/DDL/SELECT y se descartan con una línea.

Censo hecho a mano el 24-08 sobre el árbol de producción completo (0
literales, 0 dinámicos, 0 opacos sin revisar al cerrar esta tarea) --
verificado con un script de censo aparte antes de escribir las listas de
abajo, no adivinado.

**Actualizado el 25-08 (Fase 6)**: IM1 retiró el `UPDATE` en sitio de
`crear_algo` sobre `preguntas.imagen` -- la entrada de IMG-2, que EB5 dejaba
deliberadamente VISIBLE en la lista de literales, desapareció del censo y se
retiró con su explicación. Es el primer caso en que este tripwire cumple su
segunda función: no solo avisar de una escritura NUEVA, sino obligar a
limpiar la excepción cuando el defecto que la justificaba se cierra de raíz.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import lectura_vigente as lv  # noqa: E402

# Mismo alcance que ES1 -- no se comparte el módulo (evita acoplar dos
# archivos de test entre sí), pero deben coincidir; si un día divergen,
# ES1 y EB5 censarían árboles distintos sin que nada lo avise. Aceptado
# igual que RT1/ES1 mantienen sus propias listas censales por separado.
EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}
EXEC_METHODS = {"execute", "executemany", "prepare"}


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


# ---------------------------------------------------------------------------
# Sitios LITERALES: la tabla se resuelve a un nombre real (directo o vía
# variable) y el SET escribe al menos una columna que no es `activo`.
# ---------------------------------------------------------------------------
SITIOS_LITERALES_PERMITIDOS = {
    ("data/ManejoDatos/load.py", 341):
        "create_control (mensual 600/iX) -- 'control ya existe este mes, "
        "reabrirlo': reasigna user_id/user_id_f2 en la fila YA EXISTENTE "
        "por su propio id físico. Edición directa de UNA celda (DA-08), no "
        "un reemplazo de bloque -- las hijas de QC de ese control llegan "
        "después, por su propio camino de guardado.",
    # RETIRADA el 25-08 por IM1 (Fase 6): aquí vivía `crear_algo`
    # (`load.py:395`), el `UPDATE preguntas SET imagen = ?` en sitio -- IMG-2,
    # el defecto que destruyó 9 imágenes en el rebuild del 19-08. EB5 lo dejó
    # VISIBLE en esta lista en vez de ocultarlo, precisamente para que su
    # desaparición se notara: `crear_algo` compone ahora el bloque y lo
    # reemplaza con `reemplazar_bloque` (EB1), así que ya no hay ningún
    # `UPDATE` que censar. La entrada se retira porque el sitio dejó de
    # existir, no porque se haya relajado el criterio -- y el test
    # `test_sitios_literales_coinciden_con_la_lista_revisada` es lo que
    # obligó a hacerlo explícito en vez de dejar una excepción muerta.
    ("scripts/migrar_bd_a_estandar.py", 355):
        "migración H5 (centinela de segundo físico): normaliza "
        "controles.user_id_f2 a NULL para el centinela histórico ' ---- ' "
        "-- censal a propósito (tiene que alcanzar TAMBIÉN las filas "
        "anuladas, si no la migración quedaría a medias). Ya documentado "
        "como excepción censal en ES1 (SITIOS_CENSALES_LITERALES).",
    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py", 75):
        "create_control (anual) -- gemelo exacto de load.py:309: reabre el "
        "control existente del año y reasigna los físicos por su id "
        "físico. Mismo mecanismo DA-08, misma tabla, otra raíz de UI.",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 108):
        "actualizar_desplazamiento (DP-39, hallazgo del 24-08 al resolver "
        "DP-38/DA-50): escribe CondicionesMedicion.desplazamiento_ini en "
        "sitio sobre el `ref` vigente, filtrado a activo. Es la ruta real "
        "que justificó retirar posicionamiento_reposicionamiento (DA-50) -- "
        "funciona hoy -- pero SI se reguarda dos veces el mismo bloque, el "
        "desplazamiento anterior se pierde sin anular. DP-39 ya lo deja "
        "abierto EXPLÍCITAMENTE como 'nada del contrato de guardado -- es "
        "del formulario de braquiterapia': fuera de alcance de EB1-EB7 por "
        "decisión ya registrada, no un descuido de esta tarea.",
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 3623):
        "subir_control_cunas -- UPDATE de 'observaciones' restringido a "
        "'activo = 1', pero DENTRO de la misma transacción y DESPUÉS de "
        "anular el bloque anterior (activo=0) e insertar las filas nuevas: "
        "en este punto 'activo=1' solo puede ser las filas RECIÉN "
        "insertadas de este mismo guardado -- es composición del bloque "
        "nuevo (un campo que el INSERT no cubre), no mutación del "
        "histórico. Seguro por el ORDEN de la transacción, no por el SQL "
        "en sí -- ver el propio docstring de la función.",
}

# ---------------------------------------------------------------------------
# Sitios DINÁMICOS: nombre de tabla (o de tabla+columna) armado en runtime,
# marcador {DYN}.
# ---------------------------------------------------------------------------
SITIOS_DINAMICOS_PERMITIDOS = {
    ("data/ManejoDatos/load.py", 641):
        "rama DELETE físico de la función compartida MI3 -- SOLO se toma "
        "cuando la tabla NO tiene columna 'activo' (fuera del bloque de "
        "QC): 'indicadores_brazo'/'indicadores_angulares_colimador' del "
        "mensual 600/iX. La rama hermana (UPDATE SET activo=0) es la que "
        "corre para cualquier tabla del bloque de QC -- ver el propio "
        "comentario del archivo, 'fuera de alcance de este plan'.",
    ("ui/paginasControles/PruebasDiarias/PruebasDiarias.py", 910):
        "edición directa de UNA celda ya identificada por su id físico "
        "(QtSql, DA-08) -- gemelo Qt del mecanismo genérico de "
        "guardarEdicion (load.py:4201, más abajo en OPACOS). Tabla y "
        "columna dinámicas (elegidas en la UI), WHERE siempre 'id = ?'.",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 58):
        "normalizar_fechas_db -- migración de FORMATO de fecha "
        "(DD-MM-YYYY -> YYYY-MM-DD) sobre las 6 tablas de braquiterapia. "
        "Tiene que alcanzar TAMBIÉN las filas anuladas (una anulada con la "
        "fecha vieja la conserva para siempre) -- ya documentado como "
        "censal en ES1 (SITIOS_DINAMICOS_PERMITIDOS). No toca ninguna "
        "columna de DATOS, solo el formato de `fecha`.",
}

# ---------------------------------------------------------------------------
# Sitios OPACOS: el argumento de execute()/prepare() no es resoluble en
# absoluto -- se censa CUALQUIER sitio así, sea o no DELETE/UPDATE (mismo
# criterio que SITIOS_OPACOS_PERMITIDOS de ES1). La mayoría son
# INSERT/DDL/SELECT, irrelevantes para EB5, y se descartan con una línea.
# ---------------------------------------------------------------------------
SITIOS_OPACOS_PERMITIDOS = {
    # A11 (PLAN_FUGA_CONEXIONES_01-09.md §9, 01-09): mismo punto ciego
    # que A9/A10 (Trampa 6) -- with envolvio mostrar_controles_tac.
    ("data/ManejoDatos/load.py", 2723): "mostrar_controles_tac -- UPDATE de backfill mes_control, ya filtraba con filtro_activo('pruebas')",
    ("data/ManejoDatos/load.py", 2751): "SELECT (mostrar_controles_tac, MAX/MIN final) -- no aplica a EB5, tercer gemelo del sitio 2119/2091 de A9",
    # A10 (PLAN_FUGA_CONEXIONES_01-09.md §9, 01-09): mismo punto ciego
    # que A9 (Trampa 6) -- with envolvio mostrar_controles_imgHC. El
    # comentario original decia "imgHC_anual" por error (ese gemelo no
    # tiene este backfill, verificado igual que en A9).
    ("data/ManejoDatos/load.py", 2523): "mostrar_controles_imgHC -- UPDATE de backfill mes_control, ya filtraba con filtro_activo('pruebas')",
    ("data/ManejoDatos/load.py", 2551): "SELECT (mostrar_controles_imgHC, MAX/MIN final) -- no aplica a EB5, gemelo del sitio 2119/2091 de A9",
    ("data/ManejoDatos/load.py", 2155):
        "SELECT (mostrar_controles_imgIX, MAX/MIN final) -- no aplica a "
        "EB5, un SELECT nunca muta el bloque vigente. Opaco desde A9 "
        "(PLAN_FUGA_CONEXIONES_01-09.md §9) por el mismo punto ciego de "
        "Trampa 6 que el UPDATE de la línea 2091, arriba.",
    ("data/ManejoDatos/load.py", 2127):
        # A9 (PLAN_FUGA_CONEXIONES_01-09.md §9, 01-09): vivía en
        # SITIOS_LITERALES_PERMITIDOS (resuelto via _rastrear_variable
        # antes del `with`) hasta que A9 envolvió el cuerpo de
        # mostrar_controles_imgIX en un `with Conexion().conectar() as
        # conn:` -- mismo punto ciego que A7 (Trampa 6): el resolver da
        # `query_addmonth` por irresoluble en cuanto se la toca dentro
        # de un ast.With. El comentario original decía "imgIX_anual"
        # por error -- ese gemelo (mostrar_controles_imgIX_anual,
        # verificado) NO tiene este backfill, es de solo lectura.
        "mostrar_controles_imgIX -- backfill de UNA sola vez de "
        "pruebas.mes_control (columna derivada de created_at), con guarda "
        "de idempotencia (solo corre si la columna no existía) y filtrado a "
        "'activo' -- migración, no reemplazo de bloque en cada guardado. "
        "Primero de tres sitios gemelos (imgHC, tac).",
    ("data/ManejoDatos/load.py", 851):
        # A7 (PLAN_FUGA_CONEXIONES_01-09.md, 01-09): vivía en
        # SITIOS_DINAMICOS_PERMITIDOS hasta que A7 envolvió TODO el
        # cuerpo de subirlineasmensuales en un `with Conexion().
        # conectar() as conn:` -- _rastrear_variable (services/
        # lectura_vigente.py) da cualquier variable por irresoluble en
        # cuanto se la toca dentro de un ast.With (mismo trato que
        # For/While/Try). Punto ciego del analizador ante el `with`,
        # no un cambio de riesgo -- mismo sql/cursor.execute(sql, datos)
        # de siempre.
        "subirlineasmensuales, rama 'fuera del bloque de QC' -- mismo "
        "criterio que la entrada anterior: solo corre para tablas sin "
        "'activo' (p.ej. 'preguntas' antes de PR1). Contrato original, sin "
        "cambios; documentado también en el propio archivo.",
    ("services/anulacion.py", 247):
        # R1 (PLAN_REPARACION_ANUAL_27-08.md, 27-08): 238->247, desplazado
        # por las 4 tablas nuevas agregadas a TABLAS_ANULABLES. Mismo sitio.
        "anular_fila -- _SQL_ANULAR.format(...) compone siempre "
        "'SET activo = 0'. Verificado a mano contra el propio literal del "
        "helper (services/anulacion.py, _SQL_ANULAR).",
    ("services/anulacion.py", 357):
        # R1: 348->357, mismo desplazamiento que el sitio de arriba.
        "reemplazar_bloque (EB1) -- sql_anular_bloque(...) compone siempre "
        "'SET activo = 0' más el AND de vigencia. Mismo helper, mismo "
        "template verificado a mano.",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", 665):
        "anular_datos_especificos (EB2c) -- sql_anular_bloque(...), mismo "
        "template 'SET activo = 0' de EB1.",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", 886):
        "INSERT (linealidad_ct) -- no aplica a EB5, un INSERT nunca muta el "
        "bloque vigente.",
    ("data/ManejoDatos/conection.py", 679):  # R.1 (11-09): 593->678
        "DDL (E10 -- CREATE TABLE de la tabla temporal de la migración "
        "CASCADE->RESTRICT) -- no aplica a EB5.",
    ("data/ManejoDatos/conection.py", 779):  # R.1 (11-09): 693->778
        "DDL (EB2d, DA-57 -- CREATE TABLE de la tabla temporal que retira "
        "el UNIQUE de angulo_starshot) -- no aplica a EB5.",
    ("data/ManejoDatos/conection.py", 2363):
        # R1 (PLAN_REPARACION_ANUAL_27-08.md, 27-08): 2091->2160, desplazado
        # por las 4 tablas nuevas (CREATE TABLE) agregadas a
        # crearTablasAnuales. Mismo sitio. R.1 (11-09): 2224->2309.
        # T.0 (16-09): 2309->2363, desplazado por
        # _asegurar_identidad_sistema_medicion y su llamada en __init__.
        "INSERT (users, admin de arranque) -- no aplica a EB5.",
    ("data/ManejoDatos/load.py", 370):
        "INSERT (controles, alta de un control nuevo) -- no aplica a EB5.",
    ("data/ManejoDatos/load.py", 4363):
        "guardarEdicion (A3, DA-05/DA-07/DA-08) -- mecanismo GENÉRICO de "
        "edición directa de una celda: tabla y columna dinámicas (elegidas "
        "en la UI), WHERE por id físico O por (ref, energia) según la "
        "tabla. Mecanismo de corrección PERMANENTE, decidido, auditado -- "
        "no el patrón G1/G2 que este plan elimina (que mutaba TODO el "
        "bloque en cada guardado, no un campo puntual con rastro).",
    ("data/ManejoDatos/load.py", 4443):
        "guardarEdicion -- recálculo en cascada de ResultadosActividad "
        "(Ks/Kp/Ktp/actividad_calculada/actividad_decaimiento) al editar un "
        "campo de TipoCalibracion. Filtra 'activo' (filtro_activo), opaco "
        "para el resolver por reasignación de `sql` en varias ramas de la "
        "misma función. Parte del mismo mecanismo A3/DA-05 que la entrada "
        "anterior: una corrección dispara su recálculo derivado, ambos con "
        "el mismo rastro de auditoría.",
    ("data/ManejoDatos/load.py", 4779):
        "eliminarRegistro, rama else -- DELETE físico, alcanzable SOLO "
        "para tablas fuera del cierre transitivo de QC (catálogos "
        "genéricos). La rama if (anular_fila) cubre las 59 tablas de "
        "TABLAS_ANULABLES desde MI1; EB3 (test_eb3_eliminarregistro_"
        "delete_inalcanzable.py) ya demuestra que esta rama es inalcanzable "
        "para cualquier descendiente real de QC hoy.",
    ("data/ManejoDatos/obtenerDatosHalcyon.py", 397):
        "INSERT (halcyon) -- no aplica a EB5.",
    ("services/dosis_service.py", 281):
        "DDL (CREATE TABLE calculadora_dosimetrica, no está en "
        "TABLAS_ANULABLES) -- no aplica a EB5.",
    ("services/dosis_service.py", 391):
        "INSERT (calculadora_dosimetrica) -- no aplica a EB5.",
    ("services/dosis_service.py", 449):
        "SELECT (calculadora_dosimetrica) -- no aplica a EB5, no escribe.",
    ("services/dosis_service.py", 550):
        "SELECT (calculadora_dosimetrica) -- no aplica a EB5, no escribe.",
    ("services/dosis_service.py", 556):
        "SELECT (calculadora_dosimetrica) -- no aplica a EB5, no escribe.",
    ("ui/paginasControles/PruebasAnuales/halcyon_anual.py", 323):
        # C2 (27-08): 303->316 (comentarios de _configurar_subtoolbox,
        # AN-4/AN-5). A3 (27-08): 316->323 (rollback/finally en
        # subir_imagen_perfil_mlc_db). Mismo sitio, remapeado por contenido.
        "INSERT (HC_imagen_perfil_mlc_anual) -- no aplica a EB5.",
    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py", 89):
        "INSERT (controles, alta de un control nuevo) -- no aplica a EB5.",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 295):
        "INSERT (subirlineasmensuales_ix, dentro del bucle de energías) -- "
        "no aplica a EB5.",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 315):
        "INSERT (subirlineasmensuales_ix, rama fuera del bloque de QC) -- "
        "no aplica a EB5.",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 329):
        "subirlineasmensuales_ix, rama UPDATE fuera del bloque de QC -- "
        "mismo criterio que load.py:727: nombre_tabla nunca es una tabla "
        "de TABLAS_ANULABLES en esta rama (ya verificado por ES1).",
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 4065):  # R.3 (11-09): 3911->3922
        "SELECT (DO1, pruebatalas -- lectura genérica, ya filtra con "
        "filtro_activo) -- no aplica a EB5, no escribe.",
    ("ui/paginasGuia/SQLtoEXCEL.py", 529):
        "SELECT (LR3, exportación de imágenes de braqui) -- no aplica a "
        "EB5, no escribe.",
}


def _censar():
    """Recorre todo el árbol de producción una vez. Devuelve los hallazgos
    de `analizar_escritura` repartidos en las tres categorías de ES1."""
    tablas = lv.tablas_del_bloque_qc()
    literales = {}
    dinamicos = {}
    opacos = set()

    for rel, path in _archivos_produccion():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:
            continue
        for func in [n for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (isinstance(fn, ast.Attribute) and fn.attr in EXEC_METHODS):
                    continue
                if not node.args:
                    continue
                arg0 = node.args[0]
                clave = (str(rel), node.lineno)

                if isinstance(arg0, (ast.Constant, ast.JoinedStr)):
                    textos = [lv._literal_str_ast(arg0)]
                elif isinstance(arg0, ast.Name):
                    textos = lv.resolver_argumento_execute(func, node)
                    if textos is None:
                        opacos.add(clave)
                        continue
                else:
                    opacos.add(clave)
                    continue

                for texto in textos:
                    if texto is None:
                        continue
                    minus = texto.lower()
                    if "delete" not in minus and "update" not in minus:
                        continue
                    for h in lv.analizar_escritura(texto, tablas):
                        if h.tabla == "{DYN}":
                            dinamicos[clave] = (h, texto.strip())
                        else:
                            literales[clave] = (h, texto.strip())

    return {"literales": literales, "dinamicos": dinamicos, "opacos": opacos}


def test_ninguna_escritura_nueva_muta_o_borra_el_bloque_vigente():
    resultado = _censar()
    nuevos_literales = set(resultado["literales"]) - set(SITIOS_LITERALES_PERMITIDOS)
    nuevos_dinamicos = set(resultado["dinamicos"]) - set(SITIOS_DINAMICOS_PERMITIDOS)
    nuevos_opacos = resultado["opacos"] - set(SITIOS_OPACOS_PERMITIDOS)
    mensajes = []
    for clave in sorted(nuevos_literales):
        h, texto = resultado["literales"][clave]
        mensajes.append(f"{clave[0]}:{clave[1]} {h.motivo} sobre '{h.tabla}': {texto[:120]!r}")
    for clave in sorted(nuevos_dinamicos):
        h, texto = resultado["dinamicos"][clave]
        mensajes.append(f"{clave[0]}:{clave[1]} {h.motivo} (tabla dinámica): {texto[:120]!r}")
    for clave in sorted(nuevos_opacos):
        mensajes.append(f"{clave[0]}:{clave[1]} sitio opaco nuevo (SQL irresoluble) -- revisar a mano")
    assert not mensajes, (
        "Escritura nueva que borra o muta en sitio el bloque vigente de una "
        "tabla del bloque de QC (patrón G1/G2, EB5) -- si es legítima "
        "(edición directa de celda, DA-05/07/08; migración censal; o fuera "
        "del bloque de QC), añádela a la lista revisada correspondiente con "
        "su razón; si no, conviértela a reemplazar_bloque/anular_fila "
        "(EB1):\n" + "\n".join(mensajes))


def test_sitios_literales_coinciden_con_la_lista_revisada():
    resultado = _censar()
    encontrados = set(resultado["literales"])
    esperados = set(SITIOS_LITERALES_PERMITIDOS)
    assert encontrados == esperados, (
        f"Nuevos: {encontrados - esperados} / "
        f"Ya no aparecen (limpiar la lista): {esperados - encontrados}")


def test_sitios_dinamicos_coinciden_con_la_lista_revisada():
    resultado = _censar()
    encontrados = set(resultado["dinamicos"])
    esperados = set(SITIOS_DINAMICOS_PERMITIDOS)
    assert encontrados == esperados, (
        f"Nuevos: {encontrados - esperados} / "
        f"Ya no aparecen (limpiar la lista): {esperados - encontrados}")


def test_sitios_opacos_coinciden_con_la_lista_revisada():
    resultado = _censar()
    encontrados = resultado["opacos"]
    esperados = set(SITIOS_OPACOS_PERMITIDOS)
    assert encontrados == esperados, (
        f"Nuevos: {encontrados - esperados} / "
        f"Ya no aparecen (limpiar la lista): {esperados - encontrados}")


def test_cada_sitio_revisado_declara_su_razon():
    for lista in (SITIOS_LITERALES_PERMITIDOS, SITIOS_DINAMICOS_PERMITIDOS,
                  SITIOS_OPACOS_PERMITIDOS):
        for sitio, razon in lista.items():
            assert len(razon) > 30, f"{sitio} sin razón documentada"


class TestAnalizarEscrituraDetectaElPatronGuardado:
    """Rojo-antes-que-verde del DETECTOR mismo (no de código de producción
    ya convertido -- revertir cuatro tareas de EB2/EB4 para demostrarlo
    sería el camino caro sin aportar nada que estos casos sintéticos no
    prueben igual de bien): `analizar_escritura` debe atrapar exactamente
    la forma real que tenían `crear_algo`, `guardar_resultado_CambioFuente`
    y las funciones de MLC antes de EB1/EB2/EB4 -- un DELETE físico o un
    UPDATE que escribe una columna de datos sobre la tabla vigente."""

    def test_delete_fisico_sobre_tabla_del_bloque_de_qc_se_reporta(self):
        hallazgos = lv.analizar_escritura(
            'DELETE FROM "control_cunas" WHERE ref = ?',
            {"control_cunas"})
        assert len(hallazgos) == 1
        assert hallazgos[0].tabla == "control_cunas"
        assert hallazgos[0].motivo == "DELETE"

    def test_update_de_columna_de_datos_se_reporta(self):
        hallazgos = lv.analizar_escritura(
            'UPDATE "control_cunas" SET in_val = ? WHERE ref = ?',
            {"control_cunas"})
        assert len(hallazgos) == 1
        assert hallazgos[0].motivo == "UPDATE de columnas de datos"

    def test_update_de_activo_no_se_reporta(self):
        assert lv.analizar_escritura(
            'UPDATE "control_cunas" SET activo = 0 WHERE ref = ?',
            {"control_cunas"}) == []

    def test_update_con_varias_columnas_de_datos_se_reporta_una_vez(self):
        hallazgos = lv.analizar_escritura(
            'UPDATE "TipoCalibracion" SET serie = ?, modelo = ? WHERE id = ?',
            {"TipoCalibracion"})
        assert len(hallazgos) == 1

    def test_delete_o_update_fuera_del_alcance_no_se_reporta(self):
        assert lv.analizar_escritura(
            'DELETE FROM "equipos" WHERE id = ?', {"control_cunas"}) == []
        assert lv.analizar_escritura(
            'UPDATE "equipos" SET modelo = ? WHERE id = ?',
            {"control_cunas"}) == []

    def test_tabla_dinamica_se_reporta_con_marcador(self):
        hallazgos = lv.analizar_escritura(
            'UPDATE {DYN} SET valor = ? WHERE ref = ?', {"control_cunas"})
        assert len(hallazgos) == 1
        assert hallazgos[0].tabla == "{DYN}"

    def test_coma_dentro_de_funcion_no_se_confunde_con_dos_columnas(self):
        """El caso real de pruebas.mes_control: `strftime('%Y-%m',
        created_at)` tiene una coma que NO separa dos columnas del SET."""
        hallazgos = lv.analizar_escritura(
            "UPDATE pruebas SET mes_control = strftime('%Y-%m', created_at) "
            "WHERE mes_control IS NULL", {"pruebas"})
        assert len(hallazgos) == 1  # una sola columna, no dos
