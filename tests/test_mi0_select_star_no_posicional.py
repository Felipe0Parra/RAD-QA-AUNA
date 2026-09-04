"""MI0-T (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI0-T): tripwire de la clase de
defecto que MI0 corrigió -- un `SELECT *` sobre una tabla del bloque de QC
cuyo resultado se consume por POSICIÓN (`row[N]`, `row[a:b]`, o
desempaquetado en tupla), en vez de por nombre.

MI0 convirtió 6 sitios ya conocidos. Al construir ESTE tripwire (recorriendo
todo el árbol con la misma lógica, no a mano) apareció un SÉPTIMO sitio no
censado en el plan: `construir_tablas_reporte_linealidad`
(`ui/paginasControles/PruebasDiarias/braquiterapia.py`) tenía un desfase de
+1 en los 34 índices que usaba -- el PDF de reporte de linealidad de la
fuente de braquiterapia mostraba la FECHA bajo la etiqueta "Modelo cámara",
y así en cascada los 34 valores. Defecto preexistente desde antes del
commit inicial (`git log -S` sobre los índices y la función solo devuelve
`408090b`), sin cobertura de tests, sin mención en el diario -- verificado
con un subagente Opus antes de tocarlo por las implicaciones clínicas.
Corregido en el mismo commit que este tripwire: acceso por nombre vía
`cursor.description`, ya no por índice mágico.

Diseño del detector: dentro de cada función, rastrea (a) variables de SQL
que son literales `SELECT * FROM ...` (directos o vía una variable
intermedia), (b) el cursor/query que las ejecuta, (c) la variable que
recibe `fetchall()`/`fetchone()` sobre ESE cursor (o el `for` que itera
sobre ella), y (d) si esa variable se indexa con un entero/slice literal, o
se desempaqueta en tupla. Acotado a tablas del bloque de QC (`TABLAS_ANULABLES
∪ EXCEPCIONES_INVENTARIO`) para no arrastrar `users`/otras tablas fuera de
este contrato -- `usuariosManager.py::login`/`get_user` SÍ hacen `SELECT *
FROM users` con acceso posicional, pero `users` no es una tabla de QC y está
deliberadamente fuera de este plan.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.lectura_vigente import (
    excepciones_inventario, tablas_anulables,
)

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}
EXEC_METHODS = {"execute", "prepare", "exec_", "exec"}
FETCH_METHODS = {"fetchall", "fetchone"}
SELECT_STAR = re.compile(r'select\s+\*\s+from\s+"?\{?(\w*)\}?"?', re.IGNORECASE)

# Sitios revisados a mano donde SELECT * consume por posición pero la tabla
# NO es del bloque de QC (fuera del alcance de este plan por completo) --
# análogo a SITIOS_DINAMICOS_PERMITIDOS de test_le4_lecturas_filtran_activo.py.
SITIOS_FUERA_DE_QC_PERMITIDOS = {
    ("data/ManejoDatos/usuariosManager.py", 42): "tabla 'users', no es del bloque de QC",
    ("data/ManejoDatos/usuariosManager.py", 51): "tabla 'users', no es del bloque de QC",
    ("data/ManejoDatos/usuariosManager.py", 52): "tabla 'users', no es del bloque de QC",
    ("data/ManejoDatos/usuariosManager.py", 161): "tabla 'users', no es del bloque de QC",
    ("data/ManejoDatos/usuariosManager.py", 163): "tabla 'users', no es del bloque de QC",
}


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


def _texto_select_star(node):
    """Si `node` es un literal (Constant o f-string) que contiene
    'SELECT * FROM', devuelve el nombre de tabla si es literal, '' si el
    nombre de tabla también es dinámico, o None si no aplica."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        m = SELECT_STAR.search(node.value)
        return (m.group(1) or "") if m else None
    if isinstance(node, ast.JoinedStr):
        texto = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
        m = SELECT_STAR.search(texto)
        if not m:
            return None
        return m.group(1) or ""
    return None


def _nombre_base(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _hallazgos_en_funcion(func, rel):
    hallazgos = []

    vars_select_star = {}
    for node in ast.walk(func):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            tabla = _texto_select_star(node.value)
            if tabla is not None:
                vars_select_star[node.targets[0].id] = tabla

    cursor_vars = {}
    for node in ast.walk(func):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in EXEC_METHODS and node.args):
            continue
        arg0 = node.args[0]
        tabla = _texto_select_star(arg0)
        if tabla is None and isinstance(arg0, ast.Name) and arg0.id in vars_select_star:
            tabla = vars_select_star[arg0.id]
        if tabla is None:
            continue
        base = _nombre_base(node.func.value)
        if base:
            cursor_vars[base] = tabla

    if not cursor_vars:
        return hallazgos

    result_vars = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            val = node.value
            if (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute)
                    and val.func.attr in FETCH_METHODS
                    and isinstance(node.targets[0], ast.Name)):
                base = _nombre_base(val.func.value)
                if base in cursor_vars:
                    result_vars[node.targets[0].id] = cursor_vars[base]

    objetivos = dict(result_vars)
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.comprehension)):
            it = node.iter
            if (isinstance(it, ast.Name) and it.id in result_vars
                    and isinstance(node.target, ast.Name)):
                objetivos[node.target.id] = result_vars[it.id]

    for node in ast.walk(func):
        if isinstance(node, ast.Subscript):
            base = node.value
            if isinstance(base, ast.Name) and base.id in objetivos:
                sl = node.slice
                es_posicional = (isinstance(sl, ast.Slice)
                                  or (isinstance(sl, ast.Constant) and isinstance(sl.value, int)))
                if es_posicional:
                    hallazgos.append((node.lineno, objetivos[base.id]))
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
                and node.value.id in objetivos and len(node.targets) == 1
                and isinstance(node.targets[0], (ast.Tuple, ast.List))):
            hallazgos.append((node.lineno, objetivos[node.value.id]))

    return hallazgos


def _censar():
    """Todos los sitios con SELECT * consumido por posición, SIN filtrar
    por tabla -- el filtrado de alcance (bloque de QC) lo hace cada test,
    para poder distinguir "no es QC, permitido" de "no apareció nada"."""
    hallazgos = []
    for rel, path in _archivos_produccion():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for func in [n for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for lineno, tabla in _hallazgos_en_funcion(func, rel):
                hallazgos.append((str(rel), lineno, tabla))
    return hallazgos


def test_ningun_select_star_sobre_tabla_qc_se_consume_por_posicion():
    qc = set(tablas_anulables()) | set(excepciones_inventario())
    hallazgos = _censar()
    nuevos = []
    for archivo, lineno, tabla in hallazgos:
        # tabla == "" significa nombre de tabla dinámico (variable): no se
        # puede probar que esté fuera del bloque de QC, se trata como QC
        # por precaución.
        if tabla and tabla not in qc:
            continue
        if (archivo, lineno) in SITIOS_FUERA_DE_QC_PERMITIDOS:
            continue
        nuevos.append((archivo, lineno))
    assert not nuevos, (
        "SELECT * sobre una tabla del bloque de QC consumido por POSICIÓN "
        "(row[N], row[a:b], o desempaquetado en tupla) -- un cambio de "
        "esquema futuro desplazaría los índices en silencio (el defecto de "
        "construir_tablas_reporte_linealidad, corregido en este mismo "
        "commit). Convierte a columnas explícitas o acceso por nombre "
        "(cursor.description + dict, o record.indexOf/query.value(nombre) "
        "si es QSqlQuery):\n" + "\n".join(f"  {a}:{b}" for a, b in nuevos)
    )


def test_sitios_permitidos_siguen_existiendo():
    """Si uno de los sitios en SITIOS_FUERA_DE_QC_PERMITIDOS desaparece
    (la tabla entró al bloque de QC, o el código cambió), hay que revisar
    y limpiar la lista -- no dejarla acumulando entradas muertas."""
    hallazgos = {(archivo, lineno) for archivo, lineno, _ in _censar()}
    ausentes = set(SITIOS_FUERA_DE_QC_PERMITIDOS) - hallazgos
    assert not ausentes, (
        f"Sitio(s) en SITIOS_FUERA_DE_QC_PERMITIDOS que ya no aparecen -- "
        f"revisa y limpia la lista: {ausentes}"
    )
