"""A4 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `seiscientos_anual.py::
PruebaAnual600.create_control` es la copia anual del mensual (A3) --
mismo patrón, mismo defecto: `except sqlite3.Error` que avisa y traga,
sin rollback y sin close.

P2 (mismo método que A2/A3): espía sobre `_ConexionUnaVez`, fallo
inyectado con un tipo que sqlite3 no puede bindear."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
import ui.paginasControles.PruebasAnuales.seiscientos_anual as anual_mod
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(anual_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(anual_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


class _SelfAnualFalso:
    def __init__(self):
        self.user_id = _UsuarioFalso("Físico de Prueba")


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA4CreateControlAnualCierraSiempre:
    def test_insert_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        resultado = PruebaAnual600.create_control(
            _SelfAnualFalso(), ["no bindable"], "01/2026", "Físico de Prueba")

        assert resultado is None
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el INSERT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        ref = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac 600", "01/2026", "Físico de Prueba")
        assert ref is not None
