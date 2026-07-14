"""Fase H1 (auditoría 2026-07-14) -- formulario mensual, hallazgos H1.2/H1.3.

H1.2: la tabla de indicadores angulares del colimador nacía con solo 3 filas
(0°/90°/270°) mientras que la del brazo siempre tuvo 4 (incluye 180°) --
seiscientos_mensual.py:871 (heredado por PruebaMensualIX) y su equivalente
propio en Halcyon (HC_indicadores_colimador, halcyon_mensual.py:160). Ambas
tablas son "por fila" en BD (ref + nivel + valores, sin columnas fijas por
ángulo -- ver conection.py) así que agregar la fila no requiere migración.

Los objetos se construyen "pelados" (__new__ + QWidget.__init__), igual que
test_mcc_autofill_mensual.py: _crear_tablas_indicadores/_crear_tablas_aspectos_
mecanicos llaman createSimpleTable1 -> _cargar_datos_tabla, que ya envuelve
TODO en try/except y cae a los datos por defecto si self.db_manager o
self.file_cache no existen (exactamente el caso de un objeto pelado) -- no
hace falta mockear BD para verificar la estructura de la tabla.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QTableWidget, QToolBox, QWidget

from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestColimadorFila180Seiscientos:
    """PruebaMensual600._crear_tablas_indicadores -- también usada por
    PruebaMensualIX (no la sobreescribe)."""

    def _construir(self):
        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj.ref = 999999  # ref inexistente -> pruebatalas no encuentra nada -> caen los defaults
        obj.subtool = QToolBox()
        return obj

    def test_colimador_tiene_4_filas_incluyendo_180(self, app):
        obj = self._construir()

        obj._crear_tablas_indicadores()

        assert obj.subtool.count() == 2
        tabla_colimador = obj.subtool.widget(1).findChild(QTableWidget)
        assert tabla_colimador.rowCount() == 4
        etiquetas = [tabla_colimador.item(f, 0).text() for f in range(4)]
        assert etiquetas == ["0°", "90°", "180°", "270°"]

    def test_brazo_sigue_con_4_filas_sin_cambios(self, app):
        obj = self._construir()

        obj._crear_tablas_indicadores()

        tabla_brazo = obj.subtool.widget(0).findChild(QTableWidget)
        assert tabla_brazo.rowCount() == 4
        etiquetas = [tabla_brazo.item(f, 0).text() for f in range(4)]
        assert etiquetas == ["0°", "90°", "180°", "270°"]


class TestColimadorFila180Halcyon:
    """PruebaMensualHc tiene su PROPIA tabla de colimador (HC_indicadores_
    colimador) -- mismo hallazgo, corregido por separado."""

    def _construir(self):
        obj = PruebaMensualHc.__new__(PruebaMensualHc)
        QWidget.__init__(obj)
        obj.ref = 999999
        obj.subtool = QToolBox()
        return obj

    def test_colimador_halcyon_tiene_4_filas_incluyendo_180(self, app):
        obj = self._construir()

        resultado = obj._crear_tablas_aspectos_mecanicos()

        assert resultado is not None, "la construcción de tablas falló (ver stdout)"
        _, tabla_ic, _, _, _ = resultado
        assert tabla_ic.rowCount() == 4
        etiquetas = [tabla_ic.item(f, 0).text() for f in range(4)]
        assert etiquetas == ["0", "90", "180", "270"]
