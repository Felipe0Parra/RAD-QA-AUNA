"""V.3 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md): tripwire por NOMBRE DE
FUNCIÓN, no por línea (inmune a la trampa 5) -- ninguna función de
producción puede volver a leer `LecturasMaximos` por FILA (V_300 = "medida
1", V_150 = "medida 2", Vn_300 = "medida 3") en vez de por PAPEL (alto,
bajo, negativo -- el contrato completo vive en
`services/lecturas_del_maximo.py`).

El censo es sobre el CÓDIGO, no una lista escrita a mano: toda función de
producción cuyos literales de cadena mencionen `V_300`, `V_150` o
`Vn_300` es, exactamente:
  1. `data/ManejoDatos/conection.py::crearTablasCambioFuente` -- declara el
     esquema (los nombres de columna), no lee filas.
  2. `data/ManejoDatos/load.py::guardar_resultado_CambioFuente` -- el
     ESCRITOR: estas tres columnas son SU contrato de salida, no de
     entrada; nada que leer aquí.
  3. Contiene una llamada a `lecturas_por_voltaje` en algún punto de su
     cuerpo -- lee por papel, como debe.

Si aparece una CUARTA función que mencione estas columnas sin ser 1, 2 ni
3, el mensaje de fallo dice exactamente cuál es y qué hacer (léala con
`lecturas_por_voltaje`, o declárela aquí con su razón si de verdad no
necesita el papel -- p. ej. una migración que solo renombra la columna).
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

COLUMNAS_DEL_PAPEL = ("V_300", "V_150", "Vn_300")

# Las dos únicas funciones que pueden mencionar estas columnas SIN pasar
# por `lecturas_por_voltaje`: el esquema (las declara) y el escritor (las
# llena, no las lee).
EXENTAS = {
    ("data/ManejoDatos/conection.py", "crearTablasCambioFuente"):
        "declara el esquema (CREATE TABLE) -- no lee ninguna fila.",
    ("data/ManejoDatos/load.py", "guardar_resultado_CambioFuente"):
        "es el ESCRITOR: V_300/V_150/Vn_300 son su contrato de SALIDA "
        "(qué papel corresponde a cada columna al insertar), no de "
        "entrada -- no lee filas guardadas.",
    ("services/lecturas_del_maximo.py", "lecturas_por_voltaje"):
        "es la propia función que define el papel -- su mensaje de error "
        "(fila sin las 4 columnas mínimas) nombra las columnas en el "
        "texto que ve el físico; no se llama a sí misma.",
}


def _archivos_produccion(raiz: Path):
    for path in sorted(raiz.rglob("*.py")):
        rel = path.relative_to(raiz)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield str(rel), path


def _menciona_columnas_del_papel(nodo_funcion):
    # Los docstrings y las cadenas-comentario sueltas (patrón de este
    # proyecto: una cadena como sentencia propia, `Expr(Constant)`, usada
    # como comentario largo) NO cuentan -- mismo criterio que ya usan los
    # otros censores AST del proyecto para evitar el falso positivo por
    # docstring (ver CLAUDE.md, hallazgo de `test_a1_censo_raices_qc`/
    # `B.4` sobre `origen_referencia`).
    cadenas_comentario = {id(sub.value) for sub in ast.walk(nodo_funcion)
                          if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Constant)}
    for sub in ast.walk(nodo_funcion):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
           and id(sub) not in cadenas_comentario:
            if any(col in sub.value for col in COLUMNAS_DEL_PAPEL):
                return True
    return False


def _llama_a_lecturas_por_voltaje(nodo_funcion):
    for sub in ast.walk(nodo_funcion):
        if isinstance(sub, ast.Call):
            objetivo = sub.func
            nombre = getattr(objetivo, "id", None) or getattr(objetivo, "attr", None)
            if nombre == "lecturas_por_voltaje":
                return True
    return False


def _funciones_que_mencionan_las_columnas():
    """(archivo, nombre_funcion) -> menciona_columnas Y NO llama a
    lecturas_por_voltaje Y no está en EXENTAS."""
    encontradas = []
    for rel, path in _archivos_produccion(ROOT):
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _menciona_columnas_del_papel(nodo):
                continue
            if (rel, nodo.name) in EXENTAS:
                continue
            if _llama_a_lecturas_por_voltaje(nodo):
                continue
            encontradas.append((rel, nodo.name, nodo.lineno))
    return encontradas


def test_toda_funcion_que_lee_V_300_V_150_o_Vn_300_lo_hace_por_papel():
    sospechosas = _funciones_que_mencionan_las_columnas()
    assert not sospechosas, (
        "Estas funciones mencionan V_300/V_150/Vn_300 sin llamar a "
        "lecturas_por_voltaje ni estar declaradas EXENTAS -- léalas con "
        "services.lecturas_del_maximo.lecturas_por_voltaje, o si de verdad "
        "no leen por fila (p. ej. solo declaran el esquema), añádalas a "
        "EXENTAS en este archivo con la razón escrita:\n" +
        "\n".join(f"  {archivo}::{funcion} (línea {linea})"
                   for archivo, funcion, linea in sospechosas))


def test_las_dos_exentas_siguen_existiendo_con_ese_nombre():
    """Si alguna de las dos EXENTAS se renombra o se borra, este test lo
    dice explícitamente -- así la lista blanca no queda apuntando a nada."""
    encontradas = {(rel, nombre) for rel, path in _archivos_produccion(ROOT)
                   for nodo in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                   if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
                   for nombre in [nodo.name]}
    for clave in EXENTAS:
        assert clave in encontradas, f"la exención {clave} ya no existe en el código"


def test_lecturas_por_voltaje_tiene_al_menos_4_llamadores_reales():
    """Compuerta de que el censo no está midiendo el vacío: V.3 conecta 4
    sitios (recarga del formulario, "Ver tabla", PDF, precarga de la
    redundante) a `lecturas_por_voltaje`."""
    llamadores = []
    for rel, path in _archivos_produccion(ROOT):
        arbol = ast.parse(path.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
               _llama_a_lecturas_por_voltaje(nodo):
                llamadores.append((rel, nodo.name))
    assert len(llamadores) >= 4, llamadores
