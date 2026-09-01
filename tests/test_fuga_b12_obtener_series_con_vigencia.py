"""B12 (PLAN_FUGA_CONEXIONES_01-09.md §8.1/§4, hallazgo de la auditoría):
`seiscientos_mensual.py::obtenerSeriesConVigencia` -- RIESGO BAJO, solo
lectura: nunca cerraba `conn`. [medido] 3 descriptores por llamada.

Nota de proceso: ver test_fuga_b11 -- el with de este sitio se aplicó en
el mismo lote que B10/B11/B13-B15 antes de escribir su test individual;
el código ya estaba en HEAD, el rojo se confirmó revirtiendo SOLO este
sitio en el árbol de trabajo.

Sin parámetro bindeable que corromper aquí de forma limpia: la única
columna dinámica es `modelo`, que pasa por `@lru_cache` -- necesita ser
hashable, así que no puede ser una lista. El invariante que importa es
que el `with` invoque `__exit__` en el camino normal (cada test usa una
instancia nueva de `self`, así que `lru_cache` -- que cachea por
identidad de `self` -- nunca sirve un resultado de otra corrida)."""
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


class TestB12ObtenerSeriesConVigenciaCierraSiempre:
    def test_camino_normal_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _mensual_pelado()
        resultado = obj.obtenerSeriesConVigencia("N30013")

        assert resultado == []
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ tras el SELECT -- se registró: "
            f"{_ConexionUnaVezEspia.llamadas}")
