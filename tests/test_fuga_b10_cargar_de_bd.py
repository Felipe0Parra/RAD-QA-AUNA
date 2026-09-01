"""B10 (PLAN_FUGA_CONEXIONES_01-09.md §8.1/§4, hallazgo de la auditoría --
uno de los 8 sitios de `obtener_conexion()` invisibles al censo original de
107): `seiscientos_mensual.py::_cargar_de_bd` -- RIESGO BAJO, solo lectura:
nunca cerraba `conn`. [medido] 3 descriptores por llamada, no bloquea a
nadie.

P2: `nombre_tabla` con un paréntesis suelto rompe la sintaxis del
`PRAGMA table_info(...)` armado por f-string -- revienta dentro del
`with`. El resto del comportamiento ya está cubierto por
`test_h27_bd_unica_mensual.py`."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _mensual_pelado():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB10CargarDeBdCierraSiempre:
    def test_pragma_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _mensual_pelado()
        resultado = obj._cargar_de_bd([], "dosimetriaMen)", 1)

        assert resultado is False  # el except propio lo traga y avisa
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el PRAGMA revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")
