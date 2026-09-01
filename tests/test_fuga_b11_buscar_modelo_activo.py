"""B11 (PLAN_FUGA_CONEXIONES_01-09.md §8.1/§4, hallazgo de la auditoría):
`seiscientos_mensual.py::buscarModeloActivo` -- RIESGO BAJO, solo lectura:
nunca cerraba `conn`. [medido] 3 descriptores por llamada, no bloquea a
nadie.

Nota de proceso: el `with` de este sitio se aplicó junto con B10/B12-B15
antes de escribir sus tests individuales (batching accidental,
documentado en el commit de B10) -- el código ya estaba en HEAD cuando se
escribió este archivo; el rojo se confirmó revirtiendo SOLO este sitio en
el árbol de trabajo, sin tocar el commit.

P2: `filter_column` con un paréntesis suelto rompe la sintaxis del SELECT
armado por f-string -- revienta dentro del `with`. El resto ya está
cubierto por `test_e1_combo_modelos_activo.py`/`test_f9_selector_equipos.py`."""
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


class TestB11BuscarModeloActivoCierraSiempre:
    def test_select_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _mensual_pelado()
        resultado = obj.buscarModeloActivo("equip_type)", "model", "Cámara de ionización")

        assert resultado == set()  # el except propio lo traga y avisa
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")
