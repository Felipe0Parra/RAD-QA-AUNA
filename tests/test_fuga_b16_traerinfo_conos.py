"""B16 (PLAN_FUGA_CONEXIONES_01-09.md §8.1/§4, hallazgo de la auditoría --
el último de los 8 sitios de `obtener_conexion()` invisibles al censo
original de 107): `ix_mensual.py::Traerinfo_conos` -- RIESGO BAJO, solo
lectura: nunca cerraba `conn`. [medido] 3 descriptores por llamada.

P2: `self.ref` llega como una lista -- no bindeable -- el SELECT revienta
dentro del `with`. El resto ya está cubierto por
`test_t2_traerinfo_conos_estilo.py`/`test_m3_restauracion_cunas_conos.py`."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import DatabaseManager


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


def _instancia():
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.ref = ["no bindable"]
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB16TraerinfoConosCierraSiempre:
    def test_select_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _instancia()
        resultado = obj.Traerinfo_conos()

        assert resultado is False  # el except propio lo traga y avisa
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")
