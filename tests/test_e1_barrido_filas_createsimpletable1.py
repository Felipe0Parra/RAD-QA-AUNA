"""E1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 2, Protocolo): "el barrido AST
de createSimpleTable1 convertido en test permanente (falla si algún `rows`
contradice el largo de sus datos)".

`F-4`/`AN-6` vivía exactamente así: `datos_fc` traía 8 tamaños de campo
pero `createSimpleTable1(self, 6, 4, headers_fc, datos_fc, ...)` pasaba un
`rows` literal de 6, escrito aparte -- `table.setRowCount(6)` cortaba
"35x35" y "40x40" de la tabla aunque estuvieran en la lista de datos.

Este censo deriva, por AST y contra el código fuente vigente (no por
número de línea), cada llamada a `createSimpleTable1` cuyo `rows` sea un
entero literal Y cuyo argumento `datos` se pueda contar estáticamente
(lista literal, o comprensión de lista sobre una lista literal conocida
en la misma función) -- y falla si el literal no coincide con la longitud
real. Una llamada que pasa `len(datos)` como `rows` quedaba exenta por
construcción: no puede desincronizarse."""
import ast
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = Path(__file__).resolve().parent.parent

ARCHIVOS_CENSADOS = [
    "ui/paginasControles/PruebasAnuales/seiscientos_anual.py",
    "ui/paginasControles/PruebasAnuales/ix_anual.py",
    "ui/paginasControles/PruebasAnuales/halcyon_anual.py",
    "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py",
    "ui/paginasControles/PruebasMensuales/halcyon_mensual.py",
]


def _resolver_longitud(nodo, listas_conocidas):
    """Longitud estática de un argumento `datos`: lista literal,
    comprensión de lista sobre una lista/​nombre conocido, o nombre de
    variable ya resuelto antes en la misma función."""
    if isinstance(nodo, ast.List):
        return len(nodo.elts)
    if isinstance(nodo, ast.Name) and nodo.id in listas_conocidas:
        return listas_conocidas[nodo.id]
    if isinstance(nodo, ast.ListComp) and nodo.generators:
        iterable = nodo.generators[0].iter
        if isinstance(iterable, ast.List):
            return len(iterable.elts)
        if isinstance(iterable, ast.Name) and iterable.id in listas_conocidas:
            return listas_conocidas[iterable.id]
    return None


def contar_llamadas_totales(fuente):
    """Cuenta TODAS las llamadas a createSimpleTable1, sin filtrar por si
    `rows` es resoluble -- guarda independiente contra que el parseo por
    AST falle en silencio y el censo de abajo quede vacío por la razón
    equivocada."""
    arbol = ast.parse(fuente)
    return sum(
        1 for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr == "createSimpleTable1"
    )


def censar_llamadas(fuente):
    """Devuelve {lineno: (rows_literal, longitud_datos)} para cada llamada
    a createSimpleTable1 con rows literal y datos contables, dentro de
    `fuente` (código Python ya en texto). Una llamada con `rows=len(...)`
    (el caso reparado, E1) queda fuera de este diccionario a propósito --
    ver `contar_llamadas_totales` para no confundir eso con un censo vacío
    por fallo de parseo."""
    arbol = ast.parse(fuente)
    resultados = {}

    for funcion in [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)]:
        listas_conocidas = {}
        for nodo in ast.walk(funcion):
            if isinstance(nodo, ast.Assign):
                longitud = _resolver_longitud(nodo.value, listas_conocidas)
                if longitud is not None:
                    for objetivo in nodo.targets:
                        if isinstance(objetivo, ast.Name):
                            listas_conocidas[objetivo.id] = longitud

        for nodo in ast.walk(funcion):
            if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                    and nodo.func.attr == "createSimpleTable1"):
                continue
            posicionales = list(nodo.args)
            if posicionales and isinstance(posicionales[0], ast.Name) and posicionales[0].id == "self":
                posicionales = posicionales[1:]  # Clase.createSimpleTable1(self, rows, ...)
            if len(posicionales) < 4:
                continue
            nodo_rows, _nodo_cols, _nodo_headers, nodo_datos = posicionales[:4]
            if not (isinstance(nodo_rows, ast.Constant) and isinstance(nodo_rows.value, int)):
                continue  # rows es una expresión (p.ej. len(datos)) -- seguro por construcción
            longitud_datos = _resolver_longitud(nodo_datos, listas_conocidas)
            if longitud_datos is None:
                continue  # no se puede determinar estáticamente -- no se afirma nada
            resultados[nodo.lineno] = (nodo_rows.value, longitud_datos)

    return resultados


class TestLaTrampaSeDetectaEnUnCasoSintetico:
    """Rojo antes que verde: reproduce el patrón exacto de F-4/AN-6 (rows
    literal menor que len(datos)) y confirma que el censo lo marca."""

    def test_rows_literal_menor_que_los_datos_se_marca(self):
        fuente = '''
def _crear_tablas_pruebas(self):
    datos_fc = [["3x3","","",""],["10x10","","",""],["15x15","","",""],["20x20","","",""],
                ["25x25","","",""],["30x30","","",""],["35x35","","",""],["40x40","","",""]]
    widget1, tabla_fc = PruebaMensual600.createSimpleTable1(self, 6, 4, headers_fc, datos_fc, "tabla_factor_campo", self.ref, id=True)
'''
        resultados = censar_llamadas(fuente)
        assert len(resultados) == 1
        (rows, longitud), = resultados.values()
        assert rows == 6
        assert longitud == 8
        assert rows != longitud

    def test_rows_como_len_datos_queda_exento(self):
        fuente = '''
def _crear_tablas_pruebas(self):
    datos_fc = [["3x3","","",""],["10x10","","",""]]
    widget1, tabla_fc = PruebaMensual600.createSimpleTable1(self, len(datos_fc), 4, headers_fc, datos_fc, "tabla_factor_campo", self.ref, id=True)
'''
        resultados = censar_llamadas(fuente)
        assert not resultados

    def test_caso_sano_con_rows_literal_correcto_no_se_marca(self):
        fuente = '''
def _crear_tablas_pruebas(self):
    datos = [["a",""],["b",""]]
    widget, tabla = self.createSimpleTable1(2, 2, headers, datos, "tabla_x", self.ref)
'''
        resultados = censar_llamadas(fuente)
        assert resultados
        (rows, longitud), = resultados.values()
        assert rows == longitud == 2


@pytest.mark.parametrize("ruta_relativa", ARCHIVOS_CENSADOS)
class TestCensoRealDeLosCincoArchivos:
    def test_todo_rows_literal_coincide_con_su_lista_de_datos(self, ruta_relativa):
        fuente = (RAIZ / ruta_relativa).read_text(encoding="utf-8")
        resultados = censar_llamadas(fuente)
        descoordinados = {
            linea: (rows, longitud)
            for linea, (rows, longitud) in resultados.items()
            if rows != longitud
        }
        assert not descoordinados, (
            f"{ruta_relativa}: createSimpleTable1 con `rows` literal que no "
            f"coincide con el largo real de `datos` (línea: (rows, len(datos))): "
            f"{descoordinados}")

    def test_el_censo_encuentra_llamadas_de_verdad(self, ruta_relativa):
        # Guarda contra que un refactor rompa el parseo por AST y el censo
        # quede vacío en silencio (falso verde) -- independiente de si
        # `rows` resulta resoluble (E1 dejó los 5 sitios de
        # seiscientos_anual.py/ix_anual.py con `rows=len(datos)` a
        # propósito, así que para esos dos el diccionario de arriba queda
        # vacío por diseño, no por fallo de parseo).
        fuente = (RAIZ / ruta_relativa).read_text(encoding="utf-8")
        assert contar_llamadas_totales(fuente) > 0, (
            f"{ruta_relativa}: no se encontró ninguna llamada a "
            f"createSimpleTable1 -- ¿falló el parseo por AST?")
