"""Z7 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): "Limpiar datos" en
braquiterapia limpia TODO -- tres huecos confirmados empíricamente (no las
hipótesis del plan original: se hizo primero un inventario real de qué
sobrevive a "limpiar", antes de tocar código, tal como pedía el plan).

- `PruebaDiariaBraq`/`PosicionamientoInicial` (diarias): `self.observaciones`
  queda fuera de `self.df_lines` a propósito -- `storeDailyTests`
  (`PruebasDiarias.py`) lo excluye para no confundirlo con un botón
  Funciona/No funciona -- y por eso también quedaba fuera de "Limpiar datos".
- `PruebaMensualBraq` (mensual, "Cambio de fuente"): `campos_maximos`
  (MEDIDAS MÁXIMO DE LA CÁMARA) y `campos_lecturas` (LECTURAS DEL MÁXIMO) son
  `QLineEdit` crudos creados en `generar_tabla_medidas`/
  `generar_tabla_lecturas`, fuera de `self.df_lines` por completo (no vienen
  de `widgets.xlsx`) -- "Limpiar datos" nunca tocaba esas dos tablas.

`Linealidad` (`line_cal`/`line_cal_elec`) se investigó y es un FALSO
positivo: son alias del MISMO objeto `QLineEdit` que `self.calibracion`/
`self.electrometro` (ya en `df_lines`) -- limpiar el nombre en `df_lines` ya
limpia el alias. Se deja como anti-regresión, no como fix.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import (
    PruebaDiariaBraq, PosicionamientoInicial, Linealidad)
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """Trampa 2: `QMessageBox` real cuelga el proceso para siempre bajo
    `QT_QPA_PLATFORM=offscreen`. Este archivo construye pantallas REALES de
    braquiterapia, y desde B2 (PLAN_ACTIVIDAD_ESPERADA_BRAQUI_27-08.md) el
    cálculo de la actividad esperada avisa por `QMessageBox.warning` cuando
    no hay ninguna fuente ("Cambio de fuente") registrada antes de la fecha
    -- exactamente el caso de la BD temporal de este archivo, y ese cálculo
    corre dentro de `PruebaDiariaBraq.__init__`. Se mockea sobre la clase de
    `PyQt5.QtWidgets`, inmune a desde qué módulo la importe producción."""
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


class TestDiariaObservacionesSeLimpia:
    def test_prueba_diaria_braq_limpia_observaciones(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso("Físico de Prueba"))
        d.observaciones.setText("nota que debía desaparecer")

        d.clean_info()

        assert d.observaciones.text() == ""

    def test_posicionamiento_inicial_limpia_observaciones(self, app, bd_temporal):
        d = PosicionamientoInicial(_UsuarioFalso("Físico de Prueba"))
        d.observaciones.setText("nota que debía desaparecer")

        d.clean_info()

        assert d.observaciones.text() == ""


class TestMensualCamposMaximosYLecturasSeLimpian:
    def test_campos_maximos_medidas_se_limpian_posicion_no(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso("Físico de Prueba"))
        fila = d.campos_maximos[0]
        posicion_original = fila[0].text()
        fila[1].setText("12.34")
        fila[2].setText("56.78")
        fila[3].setText("34.56")  # promedio "calculado" por un cálculo previo

        d.clean_info()

        assert fila[0].text() == posicion_original  # etiqueta de referencia, intacta
        assert fila[1].text() == ""
        assert fila[2].text() == ""
        assert fila[3].text() == "-"  # promedio vuelve al valor de fábrica

    def test_campos_lecturas_medidas_se_limpian_voltaje_no(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso("Físico de Prueba"))
        fila = d.campos_lecturas[0]
        voltaje_original = fila[0].text()
        fila[1].setText("1.1")
        fila[2].setText("2.2")
        fila[3].setText("3.3")
        fila[4].setText("2.2e+00")

        d.clean_info()

        assert fila[0].text() == voltaje_original
        assert fila[1].text() == ""
        assert fila[2].text() == ""
        assert fila[3].text() == ""
        assert fila[4].text() == "-"

    def test_todas_las_filas_quedan_limpias_no_solo_la_primera(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso("Físico de Prueba"))
        for fila in d.campos_maximos:
            fila[1].setText("9.9")
        for fila in d.campos_lecturas:
            fila[1].setText("9.9")

        d.clean_info()

        assert all(fila[1].text() == "" for fila in d.campos_maximos)
        assert all(fila[1].text() == "" for fila in d.campos_lecturas)


class TestLinealidadNoTeniaUnHuecoReal:
    """Anti-regresión: line_cal/line_cal_elec SON el mismo objeto que
    self.calibracion/self.electrometro (ya en df_lines) -- no un hueco real."""

    def test_line_cal_es_alias_de_calibracion(self, app, bd_temporal):
        d = Linealidad(_UsuarioFalso("Físico de Prueba"))

        assert d.line_cal is d.calibracion
        assert d.line_cal_elec is d.electrometro
