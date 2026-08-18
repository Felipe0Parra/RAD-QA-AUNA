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
# Solo cuatro, y ninguna se acepta "en bloque": cada una se leyó en su
# fuente y se comprobó que el censo SIN filtro es justo lo que la función
# tiene que hacer -- filtrar ahí no arreglaría nada, rompería la función.
# Es el mismo criterio (y, se verificó, los mismos cuatro sitios) que ES1
# ya clasificó como "migración/censo" en `SITIOS_DINAMICOS_PERMITIDOS`;
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
    ("scripts/observador_contrato.py", 142):
        "censo (OB1, censo.total): el observador necesita el total SIN "
        "filtrar para poder calcular `anuladas = total - activas`; la "
        "consulta de al lado (línea 146) sí filtra, y es la que compara.",
    ("data/ManejoDatos/conection.py", 535):
        "migración (E10, _asegurar_fk_on_delete_restrict): "
        "`INSERT INTO \"{temporal}\" SELECT * FROM \"{nombre}\"` copia la "
        "tabla ENTERA al reconstruirla para cambiar sus FK. Filtrar aquí "
        "no sería una lectura más estricta: BORRARÍA el histórico.",
}

# Acumulador de la sesión completa de pytest -- una lista de
# (sql, origen, [SinFiltro, ...]) por cada sentencia con hallazgos.
hallazgos_sesion = []

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
}

_tablas_cache = None


def _tablas():
    global _tablas_cache
    if _tablas_cache is None:
        _tablas_cache = lv.tablas_hijas_del_bloque_qc()
    return _tablas_cache


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
    alguna de las 22 tablas hijas. Medido, no listado: coincide con las
    "19 funciones" de §2.5 del plan."""
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
    if not any(t.lower() in minus for t in tablas):
        return
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
    _estadisticas["sentencias_produccion_con_tabla_versionada"] += 1
    funciones_produccion_ejercitadas.add((origen[0], origen[1]))
    hallazgos = lv.analizar(sql, tablas)
    if not hallazgos:
        return
    if (origen[0], origen[2]) in SITIOS_CENSALES_PERMITIDOS:
        _estadisticas["sentencias_censales_permitidas"] += 1
        return
    hallazgos_sesion.append((sql, origen, hallazgos))


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
    funciones_produccion_ejercitadas.clear()
    descartados_por_origen.clear()
    for k in _estadisticas:
        _estadisticas[k] = 0


def estadisticas():
    d = dict(_estadisticas)
    d["funciones_produccion_ejercitadas"] = len(funciones_produccion_ejercitadas)
    d["sitios_de_test_descartados_por_origen"] = len(descartados_por_origen)
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
        f"  lecturas censales de producción permitidas (4 sitios revisados): "
        f"{e['sentencias_censales_permitidas']}",
    ]
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
