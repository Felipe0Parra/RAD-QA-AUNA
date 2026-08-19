"""Fase H1 (auditoría 2026-07-14) -- formulario mensual, hallazgos H1.2/H1.3.

H1.2: la tabla de indicadores angulares del colimador nacía con solo 3 filas
(0°/90°/270°) mientras que la del brazo siempre tuvo 4 (incluye 180°) --
seiscientos_mensual.py:872 (heredado por PruebaMensualIX) y su equivalente
propio en Halcyon (HC_indicadores_colimador, halcyon_mensual.py:160). Ambas
tablas son "por fila" en BD (ref + nivel + valores, sin columnas fijas por
ángulo -- ver conection.py) así que agregar la fila no requiere migración.

H1.3: `fieldSize` (seiscientos_mensual.py:2369, solo 600/iX -- Halcyon tiene
su propia tabla ya correcta en _crear_tablas_aspectos_dosimetricos) prellenaba
las 8 columnas de MEDICIÓN con el valor NOMINAL repetido cuando no había datos
en BD ni JSON -- el físico veía números que parecían mediciones reales sin
haber medido nada. Ahora solo la columna "Campo nominal" nace con datos; las
de medición nacen "".

Los objetos se construyen "pelados" (__new__ + QWidget.__init__), igual que
test_mcc_autofill_mensual.py: _crear_tablas_indicadores/_crear_tablas_aspectos_
mecanicos/fieldSize llaman a pruebatalas/_cargar_datos_tabla, que ya envuelven
TODO en try/except y caen a los datos por defecto si self.db_manager o
self.file_cache no existen (exactamente el caso de un objeto pelado) -- no
hace falta mockear BD para verificar la estructura de la tabla.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QTableWidget, QToolBox, QWidget

import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
import data.ManejoDatos.conection as conection_mod


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


class TestTamanoCampoNaceVacio:
    """fieldSize (600/iX) -- las columnas de medición NO deben nacer con el
    valor nominal repetido cuando no hay datos reales en BD ni JSON."""

    def _construir(self, tmp_path, monkeypatch):
        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj.ref = 999999
        # Hermético: sin esto, ruta_datos() apunta a la raíz del proyecto en
        # desarrollo -- redirigir a tmp_path evita tocar (o depender de) un
        # tamano_campo.json real fuera del test.
        # HI-1: seiscientos_mensual.py ya no re-exporta ruta_datos por valor
        # -- parchear conection_mod (unico punto necesario ahora).
        monkeypatch.setattr(
            conection_mod, "ruta_datos",
            lambda nombre: str(tmp_path / nombre))
        return obj

    def test_columnas_de_medicion_nacen_vacias(self, app, tmp_path, monkeypatch):
        obj = self._construir(tmp_path, monkeypatch)

        widget = obj.fieldSize("tamano_campo", obj.ref)

        tabla = widget.findChild(QTableWidget)
        nominales = [tabla.item(f, 0).text() for f in range(3, 7)]
        assert nominales == ["5 x 5", "10 x 10", "15 x 15", "20 x 20"]
        for fila in range(3, 7):
            for columna in range(1, 9):
                assert tabla.item(fila, columna).text() == "", (
                    f"fila {fila} columna {columna} nació con un valor "
                    "-- las columnas de medición deben empezar vacías")
