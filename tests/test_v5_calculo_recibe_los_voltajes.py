"""V.5 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md): con los tres voltajes
editables, `factores_correccion`/`CalcularActividad` (`analisisImagenes/
ActividadFuente.py`) YA NO pueden asumir 300/150 por defecto -- toda
llamada de PRODUCCIÓN debe pasar `v_alto`/`v_bajo` POR NOMBRE, con el
voltaje que el físico escribió (`_voltajes_del_formulario`), no con el
valor por defecto de la firma.

El censo es por AST, sobre el código fuente vigente, no una lista de
línea: toda llamada a estas dos funciones, en cualquier archivo de
producción salvo el que las define, tiene que traer los dos keywords.

RC.1 (PLAN_RECALCULO_CALIBRACION_BRAQUI_30-09.md): `resultados_para_archivar`
entra al censo -- es la única función que `guardar_DB` usa ahora para
archivar, y exige `v_alto`/`v_bajo` por nombre y sin valor por defecto.

RC.2 (mismo plan): la EXENTA de `guardarEdicion` se retira -- esa llamada
(sin `v_alto`/`v_bajo`) ya no existe: la corrección de `TipoCalibracion`
pasa por `corregir_calibracion`, que recalcula con
`resultados_desde_lo_guardado` (`services/correccion_calibracion.py`),
la cual sí llama a `resultados_para_archivar` por nombre. `EXENTAS` queda
vacía.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

ARCHIVO_DEFINICION = "analisisImagenes/ActividadFuente.py"
FUNCIONES_CENSADAS = {"factores_correccion", "CalcularActividad", "resultados_para_archivar"}

EXENTAS = {}


def _archivos_produccion(raiz: Path):
    for path in sorted(raiz.rglob("*.py")):
        rel = path.relative_to(raiz)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        if str(rel) == ARCHIVO_DEFINICION:
            continue
        yield str(rel), path


def _nombre_de_la_llamada(nodo_call):
    objetivo = nodo_call.func
    return getattr(objetivo, "id", None) or getattr(objetivo, "attr", None)


def _envolvente(arbol, nodo_objetivo):
    """Nombre de la función que contiene `nodo_objetivo` (la más interna
    que lo envuelve), o None si está a nivel de módulo."""
    mejor = None
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if nodo.lineno <= nodo_objetivo.lineno <= getattr(nodo, "end_lineno", nodo.lineno):
                if any(sub is nodo_objetivo for sub in ast.walk(nodo)):
                    mejor = nodo.name
    return mejor


def _llamadas_sin_voltajes():
    """(archivo, funcion_envolvente, nombre_llamada, linea) de cada
    llamada a factores_correccion/CalcularActividad que NO trae v_alto
    Y v_bajo por nombre -- excluidas las EXENTAS."""
    encontradas = []
    for rel, path in _archivos_produccion(ROOT):
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            nombre = _nombre_de_la_llamada(nodo)
            if nombre not in FUNCIONES_CENSADAS:
                continue
            kwargs = {kw.arg for kw in nodo.keywords if kw.arg is not None}
            if {"v_alto", "v_bajo"} <= kwargs:
                continue
            funcion = _envolvente(arbol, nodo)
            if (rel, funcion) in EXENTAS:
                continue
            encontradas.append((rel, funcion, nombre, nodo.lineno))
    return encontradas


def test_toda_llamada_de_produccion_pasa_v_alto_y_v_bajo():
    sospechosas = _llamadas_sin_voltajes()
    assert not sospechosas, (
        "Estas llamadas a factores_correccion/CalcularActividad no pasan "
        "v_alto/v_bajo por nombre -- usarían el 300/150 por defecto aunque "
        "el físico haya escrito otro voltaje. Páselos desde "
        "_voltajes_del_formulario(), o si de verdad no aplica, añada el "
        "sitio a EXENTAS en este archivo con la razón escrita:\n" +
        "\n".join(f"  {archivo}::{funcion} -- {llamada} (línea {linea})"
                   for archivo, funcion, llamada, linea in sospechosas))


def test_la_exenta_sigue_existiendo_con_ese_nombre():
    """Si `guardarEdicion` se renombra o se borra, este test lo dice --
    así la lista blanca no queda apuntando a nada."""
    encontradas = set()
    for rel, path in _archivos_produccion(ROOT):
        arbol = ast.parse(path.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                encontradas.add((rel, nodo.name))
    for clave in EXENTAS:
        assert clave in encontradas, f"la exención {clave} ya no existe en el código"


def test_censo_encuentra_al_menos_las_3_llamadas_reales():
    """Compuerta de que el censo no está midiendo el vacío: hoy hay 3
    llamadas de producción (braq_mensual.py x2: CalcularActividad y
    resultados_para_archivar en guardar_DB; services/correccion_
    calibracion.py x1: resultados_para_archivar en
    resultados_desde_lo_guardado)."""
    total = 0
    for rel, path in _archivos_produccion(ROOT):
        arbol = ast.parse(path.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and _nombre_de_la_llamada(nodo) in FUNCIONES_CENSADAS:
                total += 1
    assert total >= 3, total
