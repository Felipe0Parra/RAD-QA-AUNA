"""R5 (PLAN_FUGA_CONEXIONES_01-09.md §3-P7/§4): tripwire censal permanente
-- sin él, "el sitio 108 repite la historia" (DP-67/DP-71).

Contraparte, para la fuga de conexiones, de `test_lr1_censo_raices_qc.py`/
`test_le4_lecturas_filtran_activo.py`/`test_eb5_tripwire_escritura.py`
(mismo mecanismo: censo AST exhaustivo del árbol de producción, comparado
contra una lista blanca revisada a mano -- hoy VACÍA, porque A1-A8/M1-M3/
B10-B17 ya convirtieron los únicos sitios que escribían sin cerrar).

Qué censa: para cada función de producción que ESCRIBE (contiene, en su
propio texto fuente, `INSERT`/`UPDATE`/`DELETE`, o -- lección de M3, DP-71
-- `COMMIT`/`ROLLBACK`/`BEGIN TRANSACTION` como texto SQL crudo, no solo
`conn.commit()`), se busca una asignación PELADA (`conn = Conexion().
conectar()` o `conn = algo.obtener_conexion()`, directa o en un ternario)
que NO esté envuelta en un `with`. Esa es exactamente la forma que tenían
los 8+3+8 sitios que este plan cerró -- P3 la reemplazó siempre por
`with ... as conn:`, nunca por un `conn = ...` suelto.

Lo que este tripwire NO cubre (documentado, no un hueco silencioso):
- Sitios de solo LECTURA sin cerrar (B1-B9/B10-B17 ya los cerró todos,
  pero uno nuevo no bloquea a nadie -- P1 solo exige esto para escritura).
- `services/db_pool.py::obtener_conexion` misma (la fachada): por diseño
  ENTREGA la conexión al llamador -- excluida a propósito (R4, DP-71).
- Un `with` cuyo `__exit__` no cierre de verdad (eso es responsabilidad
  de `_ConexionUnaVez`, ya fijado por su propio test, R1)."""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

_RE_ESCRITURA = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|BEGIN\s+TRANSACTION|"
    r'"COMMIT"|\'COMMIT\'|"ROLLBACK"|\'ROLLBACK\')',
    re.IGNORECASE,
)

# services/db_pool.py::DatabaseManager.obtener_conexion es la fachada que
# ENTREGA la conexión al llamador -- por diseño no puede cerrar lo que
# devuelve (R4, DP-71). Es la ÚNICA excepción estructural: no es un sitio
# que "olvidó" envolver su conexión, es lo que hace posible que sus 22
# llamadores (ya todos revisados: A-sitios y M-sitios con with, B-sitios
# de solo lectura documentados) puedan hacerlo.
SITIOS_PERMITIDOS = {
    ("services/db_pool.py", "obtener_conexion"),
}


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


def _es_llamada_conectar(node):
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    return isinstance(fn, ast.Attribute) and fn.attr in ("conectar", "obtener_conexion")


def _contiene_llamada_conectar(node):
    """True si `node` (el `value` de una asignación) ES la llamada, o la
    CONTIENE -- el caso del ternario `X if cond else Y` que B5-B7 usan."""
    return any(_es_llamada_conectar(n) for n in ast.walk(node))


def _nombres_con_target_en_with(func_node):
    """Nombres de variable que en ALGÚN punto de esta función son el
    context_expr de un `with` (directo, o vía el propio Name) -- para no
    marcar como "pelada" una asignación intermedia (`_gestor_conn = ...`)
    que sí se abre con `with` dos líneas después."""
    nombres = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if isinstance(expr, ast.Name):
                    nombres.add(expr.id)
                elif _contiene_llamada_conectar(expr):
                    # el propio with envuelve la llamada directamente --
                    # no hay variable intermedia que registrar aquí.
                    pass
    return nombres


def _nombre_cerrado_en_finally(nombre, cuerpo_try):
    """True si algún `finally:` DENTRO de este cuerpo de `try` (buscando
    recursivamente, para tolerar un try/except anidado dentro del
    mismo try externo) llama `<nombre>.close()` en cualquier parte de su
    bloque -- el patrón real que T7/EB2d/etc. usan en vez de `with`
    (`finally: conn.close()`, a veces con una guarda `if conn:` o
    `if 'conn' in locals():` alrededor)."""
    for node in ast.walk(cuerpo_try):
        if not isinstance(node, ast.Try):
            continue
        for stmt in node.finalbody:
            for sub in ast.walk(stmt):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "close"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == nombre):
                    return True
    return False


def _asignacion_pelada_de_conexion(func_node):
    """Sitios `conn = Conexion().conectar()` / `conn = algo.
    obtener_conexion()` (directos o en ternario) que NO están, ellos
    mismos, envueltos en un `with`, NI resueltos después vía una variable
    intermedia que sí lo esté, NI cerrados por un `finally: <nombre>.
    close()` en algún try que los contenga (patrón EB2d/T7, tan válido
    como el `with` -- R5 solo exige que SE CIERRE en todos los caminos,
    no que sea con `with` específicamente)."""
    nombres_protegidos = _nombres_con_target_en_with(func_node)
    hallados = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Assign):
            continue
        if not _contiene_llamada_conectar(node.value):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        nombre = node.targets[0].id
        if nombre in nombres_protegidos:
            continue
        if _nombre_cerrado_en_finally(nombre, func_node):
            continue
        hallados.append(node.lineno)
    return hallados


def _censar():
    hallazgos = set()
    for rel, path in _archivos_produccion():
        try:
            texto = path.read_text(encoding="utf-8")
            tree = ast.parse(texto, filename=str(path))
        except Exception:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (str(rel), func.name) in SITIOS_PERMITIDOS:
                continue
            fuente_func = ast.get_source_segment(texto, func) or ""
            if not _RE_ESCRITURA.search(fuente_func):
                continue  # esta función no escribe -- fuera del alcance de R5 (P1)
            for lineno in _asignacion_pelada_de_conexion(func):
                hallazgos.add((str(rel), lineno, func.name))
    return hallazgos


# Lista blanca revisada a mano -- HOY VACÍA a propósito: A1-A8/M1-M3/
# B10-B17 (PLAN_FUGA_CONEXIONES_01-09.md) convirtieron todos los sitios
# conocidos que escribían sin cerrar. Un sitio nuevo aquí es SIEMPRE una
# regresión real -- no hay ninguna razón legítima documentada todavía
# para que exista uno.
SITIOS_REVISADOS = set()


def test_ninguna_funcion_que_escribe_deja_una_conexion_pelada():
    encontrados = _censar()
    nuevos = encontrados - SITIOS_REVISADOS
    assert not nuevos, (
        "Función que ESCRIBE (INSERT/UPDATE/DELETE, o COMMIT/ROLLBACK/"
        "BEGIN TRANSACTION como texto SQL crudo) con una conexión pelada "
        "(`conn = Conexion().conectar()` o `conn = algo.obtener_conexion()`) "
        "que no está envuelta en un `with` -- el patrón exacto que "
        "PLAN_FUGA_CONEXIONES_01-09.md cerró en A1-A8/M1-M3/B10-B17. "
        "Conviértela con `with Conexion().conectar() as conn:` (P3 de ese "
        "plan) o, si de verdad hay una razón para no hacerlo, añádela a "
        f"SITIOS_REVISADOS con esa razón: {sorted(nuevos)}")


def test_sitios_revisados_siguen_existiendo():
    """Si `SITIOS_REVISADOS` alguna vez deja de estar vacía, que una
    entrada MUERTA (el sitio se cerró o se borró) no quede pudriéndose
    sin que nadie la note -- mismo criterio que LE4/EB5."""
    encontrados = _censar()
    fantasmas = SITIOS_REVISADOS - encontrados
    assert not fantasmas, (
        f"Entrada en SITIOS_REVISADOS que ya no aparece en el censo -- "
        f"límpiala: {fantasmas}")
