"""B3 (PLAN_FUGA_CONEXIONES_01-09.md §2.3/§4): `braquiterapia.py::
Linealidad.cargar_nombres_tablas` -- RIESGO BAJO: ejecuta un único SELECT
de solo lectura contra `sqlite_master` y nunca usa el resultado (código
sin efecto observable, pero SÍ ejercitado en producción -- se llama desde
`initUI`). Nunca cierra `conn`; [medido] 3 descriptores por llamada.

No hay una rama de fallo real que inyectar (un SELECT sobre
`sqlite_master` no revienta con datos válidos): el invariante que importa
aquí es simplemente que el `with` invoque `__exit__` en el camino normal,
que es justo lo que faltaba antes de este commit."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad


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


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB3CargarNombresTablasCierraSiempre:
    def test_camino_normal_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = Linealidad.__new__(Linealidad)
        QWidget.__init__(obj)

        obj.cargar_nombres_tablas()

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ tras el SELECT -- se registró: "
            f"{_ConexionUnaVezEspia.llamadas}")
