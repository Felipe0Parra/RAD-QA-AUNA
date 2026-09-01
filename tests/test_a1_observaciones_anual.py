"""A1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 4, F-6): el anual del 600/iX
no tenía campo de observaciones -- el formato oficial trae contenido
clínicamente relevante ahí (ej. iX sept-2025: "Debido a que la tasa de
dosis de 100 UM/min en electrones se caía hicimos la prueba iniciando en
200 UM/min") y no había dónde ponerlo.

Reparación de menor riesgo: una fila más de "Indicador"/"Valor" en
`tabla_control_camaras_monitoras` -- la misma tabla libre-de-esquema que
ya guarda "Desviación estándar" como texto, sin columna dedicada, sin
tocar loadtablacomplex/reemplazar_bloque/el generador de PDF (todos leen
esta tabla genéricamente, fila por fila, ya verificado que ninguno asume
un número fijo de filas)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from PyQt5.QtWidgets import QApplication, QToolBox, QWidget
import pytest


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _ix_pelado():
    obj = PruebaAnualIX.__new__(PruebaAnualIX)
    QWidget.__init__(obj)
    obj.ref = "ref-test-a1"
    obj.anual = True
    obj.subtool = QToolBox()
    obj.subtool2 = QToolBox()
    obj.subtool3 = QToolBox()
    obj.subtool4 = QToolBox()
    obj.subtool5 = QToolBox()
    return obj


def _seis_pelado():
    obj = PruebaAnual600.__new__(PruebaAnual600)
    QWidget.__init__(obj)
    obj.ref = "ref-test-a1"
    obj.anual = True
    obj.subtool = QToolBox()
    return obj


class TestIXTieneObservacionesEnCamarasMonitoras:
    def test_las_seis_energias_tienen_fila_de_observaciones(self, app):
        obj = _ix_pelado()
        _, _, _, tablas_ccm = obj._crear_tablas_pruebas()
        assert len(tablas_ccm) == 6
        for entry in tablas_ccm:
            tabla = entry["tabla"]
            etiquetas = [tabla.item(f, 0).text() for f in range(tabla.rowCount())]
            assert "Observaciones" in etiquetas


class TestSeiscientosTieneObservacionesEnCamarasMonitoras:
    def test_tiene_fila_de_observaciones(self, app):
        obj = _seis_pelado()
        _, _, _, tabla_ccm = obj._crear_tablas_pruebas()
        etiquetas = [tabla_ccm.item(f, 0).text() for f in range(tabla_ccm.rowCount())]
        assert "Observaciones" in etiquetas
