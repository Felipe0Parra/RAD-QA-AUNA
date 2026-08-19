"""SN2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-SN2): tripwire del patrón que
produjo SN1.

SN1 corrigió `mostrar_resultados_AnalisisImagen`
(`seiscientos_mensual.py:2627`): conectaba `self.guardar_analisis.clicked` a
`self.guardar_analisis_e_imagen` bajo una guarda `hasattr(self,
'guardar_analisis')`, dentro de un método que corre UNA VEZ POR CADA análisis
de imagen (no una vez por formulario). Cada análisis añadía una conexión más
encima de las anteriores -- 3 análisis + 1 clic en "Guardar" = 3 guardados y
3 filas de auditoría.

El patrón exacto, estructural: una llamada `self.<widget>.<señal>.connect(
self.<método>)`, dentro de un `if hasattr(self, '<widget>')` (POLARIDAD
POSITIVA -- el caso contrario, `if not hasattr(...): self.<widget> = ...;
...connect(...)`, es el idiomatismo SEGURO de "crear y conectar una sola
vez", y no cuenta aquí). El censo amplio de la sesión encontró 315 `connect`
sin `disconnect` fuera de constructores obvios en todo el árbol -- filtrar
solo por esa condición habría sido "barrer a ciegas", que este proyecto
rechaza. Restringido a la polaridad + patrón de reenvío exactos de arriba,
el censo estructural da 18 sitios, agrupados en 6 pares (archivo, función).

Cada uno de los 6 se revisó a mano (no se asume, se verificó por censo de
llamadores): la función que los contiene se invoca EXACTAMENTE UNA VEZ por
instancia, de forma DIRECTA y SÍNCRONA (`self.metodo()`) desde `__init__` o
equivalente -- nunca conectada a una señal Qt que pueda disparar de nuevo.
Por eso el `hasattr` ahí no es "¿ya existe de una vuelta anterior?" (el
riesgo real) sino "¿esta subclase/hoja de Excel creó este widget opcional?"
-- construcción condicional, no reconexión. Si algún día una de estas
funciones se conecta a una señal repetible, el censo de llamadores de este
archivo NO lo detecta solo: hace falta releer el `motivo` de esa entrada.

Sitio(s) donde SÍ aplica -- ninguno hoy (SN1 ya lo corrigió con
`conectar_unico`, que este test verifica que se siga usando ahí).
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

# Revisados a mano (censo de llamadores, ver docstring): (archivo, función
# contenedora) -> por qué es seguro que esa función corra una sola vez.
SITIOS_UNA_VEZ_REVISADOS = {
    ("ui/paginasControles/PruebasDiarias/IX.py", "button_click"):
        "invocada 1 vez desde __init__ (línea 26), directa, nunca conectada a una señal",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", "button_click"):
        "4 subclases distintas la llaman 1 vez cada una desde su propio __init__"
        " (líneas 210, 1472, 1669, 2965), nunca vía .connect(self.button_click)",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", "initUI"):
        "3 subclases la llaman 1 vez cada una desde su propio __init__"
        " (líneas 208, 1656, 2885), nunca vía .connect(self.initUI)",
    ("ui/paginasControles/PruebasDiarias/seiscientos.py", "button_click"):
        "invocada 1 vez desde __init__ (línea 21), directa, nunca conectada a una señal",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", "button_click"):
        "invocada 1 vez desde __init__ (línea 34), directa, nunca conectada a una señal",
    ("ui/paginasControles/PruebasMensuales/tac_mensual.py", "controlTestWindow"):
        "invocada 1 vez por instancia (4 subclases, 1 llamada cada una desde"
        " su propio iniGUI: halcyon_mensual.py:30, ix_mensual.py:48,"
        " tac_mensual.py:475, seiscientos_mensual.py:537), nunca conectada a"
        " una señal; los `hasattr(self, 'btn_*')` son construcción"
        " condicional según la hoja de Excel de esa máquina, no reconexión",
}


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


def _guardas_positivas(test_node):
    """Nombres de `hasattr(self, 'X')` en polaridad POSITIVA dentro de
    `test_node` -- descendiendo solo por `and`/`or`. Un `hasattr` bajo un
    `not` (el idiomatismo seguro "crear si no existe") NO cuenta: esa rama
    es justo la que garantiza una única conexión."""
    nombres = set()

    def rec(n):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "hasattr" and len(n.args) == 2
                and isinstance(n.args[0], ast.Name) and n.args[0].id == "self"
                and isinstance(n.args[1], ast.Constant)
                and isinstance(n.args[1].value, str)):
            nombres.add(n.args[1].value)
        elif isinstance(n, ast.BoolOp):
            for v in n.values:
                rec(v)
        # ast.UnaryOp(Not, ...) y cualquier otro nodo: no se desciende --
        # así "not hasattr(...)" nunca cuenta como guarda positiva.

    rec(test_node)
    return nombres


def _atributo_self_raiz(node):
    """Si `node` es una cadena de `Attribute` que arranca en `self`, el
    primer atributo -- cubre tanto `self.widget` como el anidado
    `X(self.widget)` al pasar por `node.value`."""
    while isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            return node.attr
        node = node.value
    return None


def _es_slot_de_self(node):
    if isinstance(node, ast.Attribute):
        return _atributo_self_raiz(node) is not None
    if isinstance(node, ast.Lambda):
        return any(isinstance(n, ast.Name) and n.id == "self" for n in ast.walk(node))
    return False


def _revisar_statement(stmt, guardas, rel, funcname, hallazgos):
    for n in ast.walk(stmt):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "connect"):
            continue
        senal = n.func.value  # p.ej. self.guardar_analisis.clicked
        if not isinstance(senal, ast.Attribute):
            continue
        widget_expr = senal.value  # p.ej. self.guardar_analisis
        if not isinstance(widget_expr, ast.Attribute):
            continue
        widget_attr = _atributo_self_raiz(widget_expr)
        if widget_attr is None or widget_attr not in guardas:
            continue
        if not n.args or not _es_slot_de_self(n.args[0]):
            continue
        hallazgos.append((str(rel), funcname, n.lineno, widget_attr))


def _recorrer(stmts, guardas, rel, funcname, hallazgos):
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            nuevas = guardas | _guardas_positivas(stmt.test)
            _recorrer(stmt.body, nuevas, rel, funcname, hallazgos)
            _recorrer(stmt.orelse, guardas, rel, funcname, hallazgos)
        elif isinstance(stmt, (ast.For, ast.While)):
            _recorrer(stmt.body, guardas, rel, funcname, hallazgos)
            _recorrer(stmt.orelse, guardas, rel, funcname, hallazgos)
        elif isinstance(stmt, ast.With):
            _recorrer(stmt.body, guardas, rel, funcname, hallazgos)
        elif isinstance(stmt, ast.Try):
            _recorrer(stmt.body, guardas, rel, funcname, hallazgos)
            for handler in stmt.handlers:
                _recorrer(handler.body, guardas, rel, funcname, hallazgos)
            _recorrer(stmt.orelse, guardas, rel, funcname, hallazgos)
            _recorrer(stmt.finalbody, guardas, rel, funcname, hallazgos)
        else:
            _revisar_statement(stmt, guardas, rel, funcname, hallazgos)


def _censar():
    hallazgos = []
    for rel, path in _archivos_produccion():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]
                if args and args[0] == "self":
                    _recorrer(node.body, set(), rel, node.name, hallazgos)
    return hallazgos


def test_conjunto_revisado_coincide_con_el_censo_actual():
    """Ancla el resultado del censo estructural. Si cambia (aparece un sitio
    nuevo, o desaparece uno ya revisado por refactor), este test lo nota --
    es la señal de que hay que revisar SITIOS_UNA_VEZ_REVISADOS a mano."""
    hallazgos = _censar()
    encontrados = {(archivo, funcname) for archivo, funcname, _, _ in hallazgos}
    esperados = set(SITIOS_UNA_VEZ_REVISADOS)
    assert encontrados == esperados, (
        f"El censo de conexiones bajo guarda hasattr cambió.\n"
        f"Nuevos (sin revisar): {encontrados - esperados}\n"
        f"Ya no aparecen (revisar si el motivo sigue vigente): {esperados - encontrados}"
    )


def test_ningun_sitio_sin_revisar_conecta_bajo_guarda_hasattr():
    """SN2: cualquier sitio del patrón exacto (conexión a un slot de self
    sobre un widget de self, bajo `hasattr` en polaridad positiva) que NO
    esté en SITIOS_UNA_VEZ_REVISADOS hace fallar el test -- ese es
    precisamente el defecto que tenía SN1 antes de corregirse."""
    hallazgos = _censar()
    sin_revisar = [
        f"{archivo}:{lineno} en {funcname}() -- self.{widget}.<señal>.connect(...)"
        for archivo, funcname, lineno, widget in hallazgos
        if (archivo, funcname) not in SITIOS_UNA_VEZ_REVISADOS
    ]
    assert not sin_revisar, (
        "Sitio(s) nuevo(s) que conectan una señal bajo `hasattr(self, ...)` "
        "sin pasar por conectar_unico() -- riesgo de acumular conexiones si "
        "la función que los contiene puede correr más de una vez (el "
        "defecto de SN1). Revisa si la función es de construcción única "
        "(añádela a SITIOS_UNA_VEZ_REVISADOS con el motivo) o si hace falta "
        "conectar_unico() ahí:\n" + "\n".join(sin_revisar)
    )
