"""M2 (PLAN_FUGA_CONEXIONES_01-09.md §2.2/§4): `seiscientos_mensual.py::
subir_control_cunas` -- RIESGO MEDIO, gemelo de M1: ya hace `rollback()`
en su `except` antes de re-lanzar (nunca deja una transacción abierta),
pero JAMÁS cierra `conn` en ningún camino. Cuesta 3 descriptores por
llamada, en 600 e iX (heredado).

P2: `self.ref` llega como una lista -- no bindeable -- así que el UPDATE
revienta DENTRO de la transacción ya abierta por BEGIN TRANSACTION,
ejercitando el rollback() real."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _ComboFalso:
    def __init__(self, texto="Funciona"):
        self._texto = texto

    def currentText(self):
        return self._texto


def _combos_cunas(valor="Funciona"):
    return {ang: {k: _ComboFalso(valor) for k in ("in", "out", "right", "left")}
            for ang in (15, 30, 45, 60)}


def _insertar_control(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Clinac 600", "Mensual", "06/2026"))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _mensual_pelado():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestM2SubirControlCunasCierraSiempre:
    def test_update_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _mensual_pelado()
        obj.ref = ["no bindable"]

        with pytest.raises(sqlite3.ProgrammingError):
            obj.subir_control_cunas(_combos_cunas("Funciona"))

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el UPDATE revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref

        resultado = obj.subir_control_cunas(_combos_cunas("Funciona"))

        assert resultado is True
        con = sqlite3.connect(bd_temporal)
        n = con.execute(
            "SELECT COUNT(*) FROM control_cunas WHERE ref = ? AND activo = 1",
            (ref,)).fetchone()[0]
        con.close()
        assert n == 4
