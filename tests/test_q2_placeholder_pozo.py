"""Q.2 (PLAN_EQUIPOS_BORRADO_Y_VIGENCIA_10-09.md SS3): el placeholder del
factor de calibracion de una camara de pozo decia "Unidades: 1 x 10^5
Gy*m^2/h*A" -- se lee como "la unidad es 10^5", es decir "teclee la
mantisa" (4.647), justo lo contrario de lo que la formula real necesita
(confirmado en SS0.7 del plan: 15 de 15 calibraciones reales reproducen la
actividad archivada solo con el numero COMPLETO, 464700, nunca con la
mantisa -- error de un factor ~100000).

Cuatro filas reales del catalogo (63, 71, 57, 17) tienen hoy el factor con
la escala mal (DA-28/DP-24): la instruccion que las produjo seguia en
pantalla. Este test fija que deje de decirlo.

No se toca el placeholder de la camara de ionizacion (":257"): no lo
nombro el fisico y describe una conversion real y necesaria (DA-26, N_D,w
en Gy/C dividido por 1e9) -- el "10^9" ahi NO sobra. Ese placeholder es la
compuerta de cero diferencias de esta tarea.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.equipos import Config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test_q2.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class TestPlaceholderCamaraDePozo:
    def test_no_menciona_ninguna_potencia_de_diez(self, app, bd_temporal):
        cfg = Config(user_id=None)
        cfg.actualizar_unidades_calibracion("Cámara de pozo")

        texto = cfg.calib_factor.placeholderText()
        assert "10⁵" not in texto, (
            f"el placeholder sigue sugiriendo la mantisa: {texto!r}")

    def test_dice_la_unidad_completa(self, app, bd_temporal):
        cfg = Config(user_id=None)
        cfg.actualizar_unidades_calibracion("Cámara de pozo")

        texto = cfg.calib_factor.placeholderText()
        assert "Gy·m²/h·A" in texto, (
            f"el placeholder debe seguir nombrando la unidad: {texto!r}")


class TestCompuertaDeCeroDiferencias:
    """La rama de Camara de ionizacion NO se toca -- su '10^9' describe una
    conversion real (DA-26), no una potencia de la que se pueda prescindir."""

    def test_camara_de_ionizacion_sigue_diciendo_10_9(self, app, bd_temporal):
        cfg = Config(user_id=None)
        cfg.actualizar_unidades_calibracion("Cámara de ionización")

        texto = cfg.calib_factor.placeholderText()
        assert "10⁹" in texto
        assert "Gy/nC" in texto
