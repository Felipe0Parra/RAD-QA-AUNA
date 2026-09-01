"""B6 (PLAN_FUGA_CONEXIONES_01-09.md §2.3/§4): `seiscientos_mensual.py::
actualizar_fisicos` -- RIESGO BAJO, solo lectura: cerraba `conn`
EXPLÍCITAMENTE, pero DESPUÉS del bloque que puebla los combos -- si algo
revienta antes de llegar ahí (el propio SELECT, o el `except` genérico ya
documentado en Z8 para el AttributeError de `setText`), la conexión queda
sin cerrar. [medido] 3 descriptores por llamada, no bloquea a nadie.

La adquisición es un ternario de una sola línea (`obtener_conexion() if
... else Conexion().conectar()`); el `with` se abre directamente sobre esa
expresión entre paréntesis, sin variable intermedia -- más simple que B5
porque cabe en una sola línea. El `conn.close()` explícito, ahora
redundante, se retira.

P2: `equipo_f` llega como una lista -- no bindeable -- el SELECT revienta
dentro del `with`."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    for nombre in ("Físico Uno", "Físico Dos"):
        conexion.con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)",
            (nombre.lower().replace(" ", "_"), "x", nombre, 1, 1, "Físico Médico"))
    conexion.con.commit()
    yield conexion
    conexion.con.close()
    Conexion._instance = None


def _mensual_pelado():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.equipo_f = "Tomógrafo"
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 8, 15))
    obj.fisico1 = QComboBox()
    obj.fisico2 = QComboBox()
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB6ActualizarFisicosCierraSiempre:
    def test_select_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        def _filtro_que_revienta(tabla):
            raise RuntimeError("fallo inyectado por el test")

        monkeypatch.setattr(mensual_mod, "filtro_activo", _filtro_que_revienta)

        obj = _mensual_pelado()
        obj.actualizar_fisicos()  # el except genérico lo traga y avisa

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_leyendo_igual(self, app, bd_temporal):
        bd_temporal.con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
            "VALUES (?,?,?,?,?)",
            ("Tomógrafo", "Mensual", "08/2026", "Físico Uno", "Físico Dos"))
        bd_temporal.con.commit()

        obj = _mensual_pelado()
        obj.fisico1.addItem("Físico Uno", 1)
        obj.fisico2.addItem("Físico Dos", 2)

        obj.actualizar_fisicos()

        assert obj.fisico1.currentText() == "Físico Uno"
        assert obj.fisico2.currentText() == "Físico Dos"
