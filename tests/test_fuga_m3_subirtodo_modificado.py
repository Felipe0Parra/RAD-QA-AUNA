"""M3 (PLAN_FUGA_CONEXIONES_01-09.md §8.1/§4, hallazgo de la auditoría del
01-09): `seiscientos_mensual.py::subirtodo_modificado` llega por
`self.db_manager.obtener_conexion()` -- invisible para el censo original de
107 llamadas a `.conectar()` porque ese texto nunca aparece aquí. Maneja su
propia transacción con SQL crudo (`BEGIN TRANSACTION`/`COMMIT`/`ROLLBACK`,
no `conn.commit()`) y la cierra en TODOS sus caminos -- pero **nunca cierra
la conexión**. RIESGO MEDIO: no bloquea a nadie, cuesta 3 descriptores por
llamada.

El `with` se acota al CUERPO DEL `try` que ya existía (marcador hasta la
línea anterior al primer `except`) -- los dos `except sqlite3.Error`/
`Exception` quedan exactamente donde estaban, al nivel del `try`, sin
tocarlos (P3: no se reordena nada, solo se envuelve la adquisición de la
conexión).

P2: `self.ref` llega como una lista -- no bindeable -- el `UPDATE`/`INSERT`
revienta DENTRO de la transacción ya abierta por `BEGIN TRANSACTION`."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QLineEdit, QMessageBox, QWidget

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
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def _insertar_equipo(ruta_bd, eq_id):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO equipos (id, equip_type, model, serie, calibr_fact, "
        "fecha_calibr, activo, vigente) VALUES (?, ?, ?, ?, ?, ?, 1, 1)",
        (eq_id, "Cámara de ionización", "N30013", "2123", 0.0545, "05/02/2024"))
    con.commit()
    con.close()


def _insertar_control(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Clinac 600", "Mensual", "06/2026"))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _instancia(ref):
    """Un grupo (modelo/serie/calibración) apuntando al equipo id=13,
    igual que el patrón ya probado en test_f9_selector_equipos.py."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2024, 3, 1))
    obj.ref = ref

    combo_modelo = QComboBox()
    combo_modelo.addItems(["Seleccionar...", "N30013"])
    combo_modelo.setCurrentText("N30013")
    combo_serie = QComboBox()
    combo_serie.addItem("2123 — calibrado 05/02/2024", 13)
    combo_serie.setCurrentIndex(0)
    lineedit_calib = QLineEdit("0.0545")
    obj.commenu = [combo_modelo, combo_serie, lineedit_calib]
    return obj


def _datos(obj):
    return [obj.commenu[0].currentText(), obj.commenu[1].currentText(),
            obj.commenu[2].text(), "", "", "", "", "", ""]


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestM3SubirtodoModificadoCierraSiempre:
    def test_update_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        _insertar_equipo(bd_temporal, 13)
        ref = _insertar_control(bd_temporal)

        obj = _instancia(ref)
        obj.ref = ["no bindable"]  # revienta el UPDATE, dentro de BEGIN TRANSACTION

        obj.subirtodo_modificado(_datos(obj))  # el propio except lo traga y avisa

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el UPDATE revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        _insertar_equipo(bd_temporal, 13)
        ref = _insertar_control(bd_temporal)
        obj = _instancia(ref)

        obj.subirtodo_modificado(_datos(obj))

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT serie, equipo_id FROM equipos_medicion WHERE ref = ? AND activo = 1",
            (ref,)).fetchone()
        con.close()
        assert fila == ("2123", 13)
