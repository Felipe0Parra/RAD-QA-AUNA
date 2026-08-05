"""A6.5 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): diario deja rastro en
`audit_log`. `conectarfueradeservicio` (declarar un equipo fuera de
servicio el día, vía `ordenar_botones` en
`ui/paginasControles/PruebasDiarias/PruebasDiarias.py`) no auditaba nada.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QDateEdit, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import conectarfueradeservicio


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
    conexion.con.execute(
        "CREATE TABLE IF NOT EXISTS aceleradorlineal_600_fuera_servicio "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user_id TEXT, "
        "observaciones TEXT)")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _SelfFalso(QWidget):
    def __init__(self):
        super().__init__()
        self.user_id = _UsuarioFalso()
        self.date_box = QDateEdit()
        self.date_box.setDate(QDate(2026, 8, 4))
        self.observaciones = QLineEdit("mantenimiento programado")


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestConectarFueraDeServicioAudita:
    def test_audita_una_vez_con_la_fecha_como_ref(self, app, bd_temporal):
        obj = _SelfFalso()
        conectarfueradeservicio(obj, "aceleradorlineal_600_fuera_servicio")

        filas = _audit_log(bd_temporal)
        # D2 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): el detalle ya no
        # queda vacío -- antes esta fila era indistinguible en audit_log de
        # un control diario normal.
        assert filas == [
            ("Físico de Prueba", "guardar",
             "aceleradorlineal_600_fuera_servicio", "2026-08-04",
             "equipo fuera de servicio")]
