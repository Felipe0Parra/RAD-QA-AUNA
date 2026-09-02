"""RT1 (PLAN_LECTURA_VIGENTE_18-08.md §6-RT1): interceptor de SQL en tiempo
de ejecución -- el frente DINÁMICO que complementa a ES1.

Por qué hace falta además de ES1: ES1 ve SQL reconstruido del AST -- ciego
por diseño a `mostrar_controles_mensuales` (D1/D2), cuya `query` se arma en
una variable con un if/else + `+=` que ES1 marca "opaco, revisado a mano"
(EXCEPCIONES_LITERALES). RT1 ve el SQL YA RESUELTO -- variables sustituidas,
nombre de tabla dinámico ya convertido en su nombre real -- exactamente lo
que hace falta para verificar esos sitios de verdad, no solo por revisión
manual congelada en el tiempo.

Mecanismo: `sqlite3.Connection.set_trace_callback` recibe el texto de CADA
sentencia justo antes de ejecutarse -- con los nombres de tabla ya
resueltos (la interpolación de Python ya ocurrió), aunque los parámetros
`?` siguen sin sustituir (irrelevante: solo miramos nombres de tabla y
cláusulas de filtro, nunca valores). Se engancha en `sqlite3.connect` en
vez de en una conexión concreta, para cubrir TODA conexión que abra la
suite, incluidas las que crea código de producción bajo prueba (los 24
sitios del árbol llaman `sqlite3.connect` por atributo del módulo, así que
el parche los alcanza a todos).

Filtro por ORIGEN (medido en la práctica, no supuesto): la suite entera
está llena de helpers de verificación que leen TODAS las filas de una tabla
a propósito (activas e históricas) para comprobar el estado interno tras un
anular+insertar -- p.ej. `_filas_preguntas` en
`test_pr1_pr2_preguntas_al_contrato.py`, o los censos
`SELECT COUNT(*) FROM "{t}"` de `test_u2_indice_unico_controles.py` y
`test_f5_convergencia_bd_vieja.py`. Vigilar esas lecturas también habría
exigido una lista blanca de cientos de sitios repartidos por decenas de
archivos: el mismo error de "lista inmanejable" que ya se evitó en ES1
(106 sitios opacos), y esta vez sin la salida de construir un resolver,
porque el problema no es de RESOLUCIÓN sino de ORIGEN.

Por eso `_origen_es_produccion()` mira el frame INMEDIATO que llamó a
`.execute()` -- `sys._getframe(2)` contado desde el propio helper
(0=`_origen_es_produccion`, 1=`_rastrear_sql`, 2=el llamador real) -- y
solo analiza si ese frame vive dentro del árbol de PRODUCCIÓN (data/,
services/, ui/, models/, scripts/), nunca si vive en `tests/`. Que
`sqlite3` no interpone ningún frame Python entre quien llama `.execute()`
y el callback está VERIFICADO empíricamente, y para las cuatro formas de
invocación que aparecen en el árbol: `Connection.execute` (atajo),
`Cursor.execute`, `executemany` y el `COMMIT` implícito de `commit()`.

Si una función de producción (p.ej. `mostrar_controles_mensuales`) es la
que llama a `.execute()`, cuenta como producción sin importar qué test la
invocó -- que es exactamente lo que hace falta vigilar.

LF3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF3) -- el alcance de RT1 y el de
ES1 son el MISMO conjunto de tablas (`tablas_del_bloque_qc`, fuente
única), pero el fallo duro de RT1 se DIFIERE sobre las tablas
`PENDIENTE-LF`, y esto no es una excepción de conveniencia: es la
consecuencia de que los dos frentes observen objetos distintos. LF1 escribió
`filtro_activo(tabla)` en los 74 sitios; para una tabla que todavía no está
en `TABLAS_ANULABLES` esa llamada evalúa a `""`, así que el SQL ejecutado
sale sin cláusula de `activo` -- correctamente, porque la columna aún no
existe y el plan pide que LF sea un no-op observable con el SQL "idéntico"
al de antes (§2.6, §3 regla 4). ES1 puede verificar esos sitios (ve la
llamada en el fuente); RT1 no puede (ve el resultado, que es la cadena
vacía), y exigírselo solo se podría satisfacer escribiendo la cláusula a
mano contra una columna inexistente, rompiendo el punto único de LE0.

Difiere, pero no queda ciego, por tres razones que se sostienen entre sí:
los hallazgos diferidos se cuentan y se PUBLICAN en `informe_cobertura()`
(no desaparecen, se miden); el conjunto se deriva de la resta
`PENDIENTE-LF - TABLAS_ANULABLES`, así que se vacía SOLO en cuanto MI1
amplíe el frozenset -- sin lista que nadie tenga que acordarse de borrar,
y sin que una tabla que ya versiona pueda seguir difiriéndose ni por
descuido; y el reparto es por HALLAZGO, no por sentencia, así que un JOIN
entre una tabla que ya versiona y una PENDIENTE-LF sigue fallando por la
primera. `TestDiferidasHastaMI1` (en `test_rt1_interceptor_sql.py`)
demuestra las tres, incluida la reactivación simulando MI1.
"""
import ast
import re
import sqlite3
import sys
from pathlib import Path

from services import lectura_vigente as lv

_ROOT = Path(__file__).resolve().parent.parent
_DIRS_PRODUCCION = ("data", "services", "ui", "models", "scripts")


def _origen():
    """(ruta_relativa_al_repo, funcion, linea) del llamador real de
    `.execute()`, o None si vive fuera del árbol del proyecto (.venv,
    stdlib) o si la pila no llega tan atrás."""
    try:
        frame = sys._getframe(2)  # 0=_origen, 1=_rastrear_sql, 2=el llamador
    except ValueError:            # pragma: no cover -- pila degenerada
        return None
    try:
        relativo = Path(frame.f_code.co_filename).resolve().relative_to(_ROOT)
    except (ValueError, OSError):
        return None               # fuera del árbol del proyecto
    return (relativo.as_posix(), frame.f_code.co_name, frame.f_lineno)


def _es_produccion(origen):
    return (origen is not None
            and Path(origen[0]).parts[0] in _DIRS_PRODUCCION)


# Excepciones CENSALES de RT1 (clave: (archivo, línea del `.execute()`)).
#
# Seis, y ninguna se acepta "en bloque": cada una se leyó en su
# fuente y se comprobó que el censo SIN filtro es justo lo que la función
# tiene que hacer -- filtrar ahí no arreglaría nada, rompería la función.
# Es el mismo criterio (y, se verificó, los mismos sitios) que ES1 ya
# clasificó como "migración/censo" en `SITIOS_DINAMICOS_PERMITIDOS` o, para
# los dos que LR4 hizo visibles, en `SITIOS_CENSALES_LITERALES`;
# `test_rt1_interceptor_sql.py` exige que ambas listas sigan de acuerdo,
# para que no puedan derivar una de otra en silencio (§3 del plan: dos
# copias del mismo criterio es exactamente el error que causó todo esto).
#
# Lo que NO se hereda de ES1 son sus `SITIOS_OPACOS_PERMITIDOS`: esos son
# opacos al AST, pero en tiempo de ejecución RT1 los ve resueltos y debe
# juzgarlos por su contenido real. Heredarlos sería anular el frente
# dinámico justo donde aporta.
SITIOS_CENSALES_PERMITIDOS = {
    ("scripts/migrar_bd_a_estandar.py", 147):
        "censo (_contar_qc): cuenta el TOTAL de filas de cada tabla de QC "
        "antes y después de migrar, para verificar que ninguna se pierde. "
        "Filtrar por activo ocultaría justo la pérdida que vigila.",
    ("scripts/migrar_bd_a_estandar.py", 179):
        "censo (_contar_todas_las_tablas): igual que el anterior, extendido "
        "a las ~69 tablas que E10 puede recrear en una corrida.",
    ("scripts/observador_contrato.py", 154):
        "censo (OB1, censo.total): el observador necesita el total SIN "
        "filtrar para poder calcular `anuladas = total - activas`; la "
        "consulta de al lado (línea 146) sí filtra, y es la que compara.",
    ("data/ManejoDatos/conection.py", 593):
        "migración (E10, _asegurar_fk_on_delete_restrict): "
        "`INSERT INTO \"{temporal}\" SELECT * FROM \"{nombre}\"` copia la "
        "tabla ENTERA al reconstruirla para cambiar sus FK. Filtrar aquí "
        "no sería una lectura más estricta: BORRARÍA el histórico.",
    ("data/ManejoDatos/conection.py", 693):
        "migración (EB2d, DA-57, _asegurar_angulo_starshot_sin_unique_de_tabla): "
        "mismo patrón que E10 arriba -- copia la tabla ENTERA al "
        "reconstruirla para retirar el UNIQUE(ref, spoke_index) de tabla "
        "(no partial, bloqueaba anular+insertar). Filtrar aquí borraría "
        "el histórico que la propia migración existe para preservar.",
    # LR4 (§6-LR4, [[DA-48]]): con las 7 raíces dentro del alcance, estas dos
    # sentencias sobre `controles` pasan a ser visibles para RT1. Las dos son
    # de la MISMA migración y tienen que ver las dos ramas o dejarían el
    # histórico a medio normalizar. Declaradas también en ES1
    # (`SITIOS_CENSALES_LITERALES`), y el test cruzado exige que sigan
    # coincidiendo.
    ("scripts/migrar_bd_a_estandar.py", 121):
        "migración (_contar_centinela): cuenta las filas de `controles` con "
        "el centinela histórico de 2º físico. Una fila anulada con el dato "
        "mal sigue teniendo el dato mal -- filtrar aquí haría que la cuenta "
        "y el UPDATE de la línea 339 discreparan en silencio.",
    ("scripts/migrar_bd_a_estandar.py", 355):
        "migración (el UPDATE que normaliza ese centinela a NULL): misma "
        "razón que la cuenta de la línea 121, y la otra mitad de la misma "
        "operación -- filtrar una de las dos deja la migración a medias.",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 54):
        "censo/migración (normalizar_fechas_db): reescribe el FORMATO de "
        "`fecha` (DD-MM-YYYY -> YYYY-MM-DD) en las 6 tablas de "
        "braquiterapia, TipoCalibracion incluida. Tiene que alcanzar también "
        "a las filas anuladas -- una fila anulada con la fecha en el formato "
        "viejo la conserva para siempre, y es justo eso lo que obliga a "
        "`braq_mensual.py:1257` a consultar en los dos formatos (DP-32). "
        "Lo encontró ESTE frente y no ES1: era un `UPDATE {tabla}` con "
        "nombre dinámico, y el detector de ES1 solo miraba `FROM {DYN}` "
        "(hueco cerrado en LR4 con PATRON_UPDATE_DINAMICO).",

    # C2 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase C): motivo "clave de
    # bloque incompleta" -- JOIN + COUNT/MAX/MIN con GROUP BY sobre
    # `pruebas.id_sesion` sin discriminar `id_tipo`. Son AGREGACIONES sobre
    # TODAS las pruebas de una sesión, no una elección arbitraria entre
    # varias -- mismo criterio que ES1 ya aplicó a los sitios de lista
    # completa/agregación (`load.py:3038`/`3890`, ver
    # SITIOS_CLAVE_INCOMPLETA_PERMITIDOS en test_le4). RT1 los ve porque los
    # tests ejercitan de verdad `mostrar_controles_img*`/`mostrar_controles_tac`.
    ("data/ManejoDatos/load.py", 1882):
        "mostrar_controles_imgIX_anual -- COUNT(p.id_prueba) GROUP BY c.id: "
        "cuenta TODAS las pruebas de la sesión, no elige una.",
    ("data/ManejoDatos/load.py", 1916):
        "mostrar_controles_imgIX_anual -- MAX/MIN GROUP BY c.id: agregación "
        "sobre todas las pruebas de la sesión.",
    ("data/ManejoDatos/load.py", 2071):
        "mostrar_controles_imgIX -- gemelo mensual del COUNT anterior.",
    # CORRECCIÓN 01-09 (A9/A10/A11, PLAN_FUGA_CONEXIONES_01-09.md §9): las
    # tres entradas de esta familia (2119/2515/2715) se retiraron por error
    # al envolver mostrar_controles_imgIX/imgHC/tac en `with` (P3) -- se
    # asumió que el motivo era Trampa 6 (el sitio se vuelve opaco para ES1),
    # igual que A7. Es FALSO para estas tres: el motivo real de `lv.analizar`
    # aquí es "clave de bloque incompleta" (la clave de 'pruebas' es
    # (id_sesion, id_tipo) -- scripts/indices_bloque_qc.py -- y el JOIN solo
    # cubre id_sesion), preexistente a este plan y AJENO al `with`: ya vivía
    # aquí antes del commit 7e7eba8 (A9), con `filtro_p_on` puesto y todo.
    # Retirarlas dejó a RT1 sin excepción para un hallazgo REAL que sigue
    # ocurriendo en cada ejecución -- confirmado reproduciendo el error con
    # tests/test_c2_listados_ocultan_anulados.py (accumula en la sesión, se
    # ve al cerrar cualquier corrida que ejercite estas 3 funciones). Se
    # restauran con el número de línea vigente (sin cambios: P3 no desplazó
    # estas líneas). test_rt1_no_hereda_los_sitios_opacos_de_es1 permite
    # este solape puntual porque está documentado como independiente, no
    # heredado -- ver EXCEPCIONES_INDEPENDIENTES en test_rt1_interceptor_sql.py.
    ("data/ManejoDatos/load.py", 2119):
        "mostrar_controles_imgIX -- gemelo mensual del MAX/MIN anterior.",
    ("data/ManejoDatos/load.py", 2276):
        "mostrar_controles_imgHC_anual -- gemelo Halcyon del COUNT.",
    ("data/ManejoDatos/load.py", 2310):
        "mostrar_controles_imgHC_anual -- gemelo Halcyon del MAX/MIN.",
    ("data/ManejoDatos/load.py", 2467):
        "mostrar_controles_imgHC -- gemelo Halcyon mensual del COUNT.",
    ("data/ManejoDatos/load.py", 2515):
        "mostrar_controles_imgHC -- gemelo Halcyon mensual del MAX/MIN.",
    ("data/ManejoDatos/load.py", 2667):
        "mostrar_controles_tac -- gemelo TAC del COUNT.",
    ("data/ManejoDatos/load.py", 2715):
        "mostrar_controles_tac -- gemelo TAC del MAX/MIN.",
    ("scripts/observador_contrato.py", 158):
        "_censo_y_vigente -- COUNT(*) sobre TODA la tabla (censo total, sin "
        "relación a ningún ref/clave) -- mismo espíritu que la línea 154 ya "
        "documentada arriba, para una tabla con clave compuesta.",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", 61):
        "buscar_datos_db -- función GENÉRICA reusada por muchas tablas "
        "anuales; fetchall() sin ORDER BY/LIMIT, trae la LISTA completa de "
        "filas activas de ese ref, no elige una.",
}

# Acumulador de la sesión completa de pytest -- una lista de
# (sql, origen, [SinFiltro, ...]) por cada sentencia con hallazgos.
hallazgos_sesion = []

# LF3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF3): hallazgos sobre una tabla
# cuyo `filtro_activo()` es HOY un no-op (ver
# `lectura_vigente.tablas_con_filtro_no_op`). NO fallan la sesión -- el SQL
# ejecutado no puede llevar la cláusula mientras la columna no exista -- pero
# se cuentan y se publican, para no perder de vista que existen ni cuántos
# son. Clave: (archivo, funcion, linea, tabla); valor: cuántas ejecuciones.
#
# Esta excepción no es una lista escrita a mano y no hay que vaciarla en MI1:
# se deriva de la resta `PENDIENTE-LF - TABLAS_ANULABLES`, así que se vacía
# sola en cuanto MI1 amplíe el frozenset, y RT1 recupera el fallo duro sobre
# esas tablas en la misma corrida.
sitios_diferidos = {}

# Medición de cobertura exigida por §9.3 del plan ("con el número de
# funciones lectoras realmente ejercitadas publicado"): qué funciones de
# PRODUCCIÓN llegaron a ejecutar de verdad una sentencia sobre una tabla
# del bloque de QC. No es un detalle interno: es un entregable de RT1.
funciones_produccion_ejercitadas = set()   # {(archivo, funcion), ...}

# Falsos positivos que el filtro de ORIGEN evita: sentencias SIN filtro de
# `activo` cuyo llamador NO es producción (helpers de verificación de la
# propia suite, que leen activas + históricas a propósito). Se cuentan de
# verdad -- el plan pide el número real, no un estimado. Clave: el sitio
# (archivo, funcion) que la ejecutó; valor: cuántas veces.
descartados_por_origen = {}

_estadisticas = {
    "sentencias_vistas": 0,
    "sentencias_con_tabla_versionada": 0,
    "sentencias_produccion_con_tabla_versionada": 0,
    "sentencias_sin_filtro_descartadas_por_origen": 0,
    "sentencias_censales_permitidas": 0,
    "hallazgos_diferidos_filtro_no_op": 0,
}

_tablas_cache = None
_diferidas_cache = None
_tablas_filtro_posible_cache = None


def _tablas():
    global _tablas_cache
    if _tablas_cache is None:
        _tablas_cache = lv.tablas_del_bloque_qc()
    return _tablas_cache


def _tablas_con_filtro_posible():
    """LF5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF5, DA-47): superconjunto de
    `_tablas()` que SÍ incluye las 7 raíces -- necesario para que el
    pre-filtro de `_rastrear_sql` no descarte, antes de llamar a
    `lv.analizar()`, la sentencia real que el motivo "filtro sobre lectura
    de identidad" vigila (braq_mensual.py, TipoCalibracion). Sin esto,
    revertir LF4 nunca pondría a RT1 en rojo: TipoCalibracion es raíz,
    fuera de `_tablas()`, así que el `return` temprano descartaría la
    sentencia antes de que `analizar()` tuviera oportunidad de mirarla."""
    global _tablas_filtro_posible_cache
    if _tablas_filtro_posible_cache is None:
        _tablas_filtro_posible_cache = lv.tablas_con_filtro_posible()
    return _tablas_filtro_posible_cache


def _diferidas():
    """Las tablas cuyo hallazgo se difiere (no falla la sesión) porque su
    `filtro_activo()` todavía evalúa a `""`. Se deriva del mismo módulo que
    el alcance -- ni una segunda lista, ni un criterio propio."""
    global _diferidas_cache
    if _diferidas_cache is None:
        _diferidas_cache = lv.tablas_con_filtro_no_op()
    return _diferidas_cache


# ---------------------------------------------------------------------------
# El DENOMINADOR de la cobertura (§9.3: "con el número de funciones lectoras
# realmente ejercitadas publicado").
#
# No se congela una lista de 19 nombres: se DERIVA del árbol con el mismo
# analizador, en cada corrida. Un número escrito a mano envejece en
# silencio -- que es la forma exacta del defecto que este plan persigue.
# ---------------------------------------------------------------------------
_EXCLUIR = {".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
            "resources", "mcc_PTW_read"}
_RE_SELECT = re.compile(r'\bSELECT\b', re.IGNORECASE)


def _sql_de_la_funcion(func):
    """Textos SQL que una función llega a pasar a execute(): literales, más
    los que AN1 sabe resolver de una variable."""
    for n in ast.walk(func):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("execute", "executemany", "prepare") and n.args):
            continue
        literal = lv._literal_str_ast(n.args[0])
        if literal is not None:
            yield literal
        elif isinstance(n.args[0], ast.Name):
            for t in (lv.resolver_argumento_execute(func, n) or ()):
                yield t


def lectoras_del_bloque_qc():
    """{(archivo, función)} de PRODUCCIÓN que hacen un SELECT nombrando
    alguna tabla del bloque de QC. Medido en cada corrida, nunca listado a
    mano: 19 funciones en §2.5 del plan de lectura vigente, 56 tras LF2
    (entran las 30 PENDIENTE-LF), 97 tras LR4 (entran las 7 raíces). El
    número sube porque sube la superficie vigilada."""
    tablas = _tablas()
    encontradas = set()
    for d in _DIRS_PRODUCCION:
        for py in sorted((_ROOT / d).rglob("*.py")):
            relativo = py.relative_to(_ROOT)
            if set(relativo.parts) & _EXCLUIR:
                continue
            try:
                arbol = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:                      # pragma: no cover
                continue
            for n in ast.walk(arbol):
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for sql in _sql_de_la_funcion(n):
                    if not _RE_SELECT.search(sql):
                        continue
                    refs = {m.group(1).lower()
                            for m in lv._RE_FROM_JOIN.finditer(sql)}
                    if any(t.lower() in refs for t in tablas):
                        encontradas.add((relativo.as_posix(), n.name))
                        break
    return encontradas


def _rastrear_sql(sql):
    _estadisticas["sentencias_vistas"] += 1
    minus = sql.lower()
    if "from" not in minus and "update" not in minus:
        return
    tablas = _tablas()
    tiene_tabla_conocida = any(t.lower() in minus for t in tablas)
    # LF5: el motivo "filtro sobre lectura de identidad" tiene su propio
    # alcance (`tablas_con_filtro_posible`), que NO coincide con `tablas`:
    # desde LR4 las raíces están en los dos, pero las 30 PENDIENTE-LF solo
    # están en `tablas`. Este segundo `any` evita que una sentencia se
    # descarte ANTES de llegar a `lv.analizar()`; no cuenta para las
    # métricas de cobertura de §9.3, que siguen midiendo el alcance de "sin
    # filtro" (97 funciones tras LR4).
    if not tiene_tabla_conocida and not any(
            t.lower() in minus for t in _tablas_con_filtro_posible()):
        return
    if tiene_tabla_conocida:
        _estadisticas["sentencias_con_tabla_versionada"] += 1
    origen = _origen()
    if not _es_produccion(origen):
        # Verificación de test: lee activas + históricas a propósito. No se
        # vigila, pero SÍ se cuenta -- para poder decir con un número real
        # cuántos falsos positivos evita el filtro de origen.
        if lv.analizar(sql, tablas):
            _estadisticas["sentencias_sin_filtro_descartadas_por_origen"] += 1
            clave = (origen[0], origen[1]) if origen else ("<desconocido>", "?")
            descartados_por_origen[clave] = descartados_por_origen.get(clave, 0) + 1
        return
    if tiene_tabla_conocida:
        _estadisticas["sentencias_produccion_con_tabla_versionada"] += 1
        funciones_produccion_ejercitadas.add((origen[0], origen[1]))
    hallazgos = lv.analizar(sql, tablas)
    if not hallazgos:
        return
    if (origen[0], origen[2]) in SITIOS_CENSALES_PERMITIDOS:
        _estadisticas["sentencias_censales_permitidas"] += 1
        return
    # LF3: el reparto es POR HALLAZGO, no por sentencia. Un JOIN entre una
    # tabla que ya versiona y una PENDIENTE-LF debe seguir fallando por la
    # primera; agrupar por sentencia dejaría que la segunda le prestara
    # cobertura -- el mismo error de "filtro por sentencia y no por tabla"
    # que fue el hueco 4 de LE4 (ver el docstring de `lectura_vigente`).
    diferidas = _diferidas()
    diferidos = [h for h in hallazgos if h.tabla in diferidas]
    exigibles = [h for h in hallazgos if h.tabla not in diferidas]
    for h in diferidos:
        _estadisticas["hallazgos_diferidos_filtro_no_op"] += 1
        clave = (origen[0], origen[1], origen[2], h.tabla)
        sitios_diferidos[clave] = sitios_diferidos.get(clave, 0) + 1
    if exigibles:
        hallazgos_sesion.append((sql, origen, exigibles))


_connect_original = sqlite3.connect


def _connect_instrumentado(*args, **kwargs):
    con = _connect_original(*args, **kwargs)
    con.set_trace_callback(_rastrear_sql)
    return con


def activar():
    sqlite3.connect = _connect_instrumentado


def desactivar():
    sqlite3.connect = _connect_original


def reiniciar():
    hallazgos_sesion.clear()
    sitios_diferidos.clear()
    funciones_produccion_ejercitadas.clear()
    descartados_por_origen.clear()
    for k in _estadisticas:
        _estadisticas[k] = 0


def estadisticas():
    d = dict(_estadisticas)
    d["funciones_produccion_ejercitadas"] = len(funciones_produccion_ejercitadas)
    d["sitios_de_test_descartados_por_origen"] = len(descartados_por_origen)
    d["sitios_diferidos_filtro_no_op"] = len(sitios_diferidos)
    return d


def informe_cobertura():
    """Texto legible con la medición que §9.3 del plan exige publicar."""
    e = estadisticas()
    lineas = [
        "RT1 -- cobertura real del frente dinámico (§9.3 del plan):",
        f"  sentencias SQL vistas por el interceptor ....... {e['sentencias_vistas']}",
        f"  ... que mencionan una tabla del bloque de QC ... {e['sentencias_con_tabla_versionada']}",
        f"  ... y cuyo llamador es PRODUCCIÓN .............. {e['sentencias_produccion_con_tabla_versionada']}",
        f"  funciones de producción ejercitadas ............ {e['funciones_produccion_ejercitadas']}",
        f"  falsos positivos evitados por el filtro de origen: "
        f"{e['sentencias_sin_filtro_descartadas_por_origen']} ejecuciones "
        f"en {e['sitios_de_test_descartados_por_origen']} sitios de test",
        f"  lecturas censales de producción permitidas "
        f"({len(SITIOS_CENSALES_PERMITIDOS)} sitios revisados): "
        f"{e['sentencias_censales_permitidas']}",
    ]
    # LF3: la ventana LF→MI1, publicada en vez de silenciada. Estas
    # sentencias SÍ salieron sin cláusula de `activo`, y es lo correcto hoy
    # (`filtro_activo()` devuelve "" mientras la tabla no versione); ES1 es
    # quien comprueba, sobre el fuente, que la llamada está escrita.
    diferidas = sorted(_diferidas())
    lineas.append(
        f"  hallazgos DIFERIDOS hasta MI1 (filtro_activo() aún es no-op en "
        f"{len(diferidas)} tablas PENDIENTE-LF): "
        f"{e['hallazgos_diferidos_filtro_no_op']} ejecuciones en "
        f"{e['sitios_diferidos_filtro_no_op']} sitios")
    for (archivo, funcion, linea, tabla), veces in sorted(sitios_diferidos.items()):
        lineas.append(f"    {archivo}::{funcion}:{linea} -> {tabla} (x{veces})")
    if not diferidas:
        lineas.append("    (ninguna: MI1 ya amplió TABLAS_ANULABLES, RT1 "
                      "exige el filtro sobre todo el bloque de QC)")
    lectoras = lectoras_del_bloque_qc()
    cubiertas = lectoras & funciones_produccion_ejercitadas
    pendientes = lectoras - funciones_produccion_ejercitadas
    pct = f"{100.0 * len(cubiertas) / len(lectoras):.0f} %" if lectoras else "n/a"
    lineas.append(
        f"  FUNCIONES LECTORAS del bloque de QC ejercitadas: "
        f"{len(cubiertas)}/{len(lectoras)} ({pct})")
    lineas.append("  deuda nominal -- lectoras que la suite NUNCA ejecuta "
                  "(RT1 no las ve; solo ES1 las cubre):")
    for archivo, funcion in sorted(pendientes):
        lineas.append(f"    {archivo}::{funcion}")
    lineas.append("  toda función de producción que tocó una tabla versionada:")
    for archivo, funcion in sorted(funciones_produccion_ejercitadas):
        marca = "L" if (archivo, funcion) in lectoras else " "
        lineas.append(f"    [{marca}] {archivo}::{funcion}")
    return "\n".join(lineas)
