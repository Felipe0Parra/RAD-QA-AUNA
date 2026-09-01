"""A6 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `equipos.py::Config.
guardarCambios` (edición de un equipo) cerraba en 3 caminos EXPLÍCITOS
(`conn.close()` repetido 3 veces, uno de ellos tras un `conn.commit()`) y
al final del camino normal -- pero **sin `try` y sin `finally`**: cualquier
fallo que no fuera uno de esos 3 puntos exactos (p. ej. el propio `INSERT`)
sube sin que nada la cierre.

El `with` cubre toda la parte que usa `conn` (los 4 `conn.close()`
explícitos, ahora redundantes, se retiran; los 2 `conn.commit()` se
conservan intactos, sin mover nada).

P2: no hay ningún parámetro externo a `guardarCambios(self)` -- todo se
lee de los widgets de `self` -- así que el fallo se inyecta con un widget
falso cuyo `.text()` devuelve un valor NO bindeable (una lista), igual de
válido como inyección de P2 que un dato mal formado real: ninguna
conversión intermedia lo sanea antes del `INSERT`."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
import ui.paginasGuia.equipos as equipos_mod
from ui.paginasGuia.equipos import Config


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
    monkeypatch.setattr(equipos_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(equipos_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))


_CERT_DEFECTO = dict(
    equip_type="Cámara de ionización", model="N30013", serie="2123",
    calibr_fact=0.0545, calibr_fact2=None, fecha_calibr="30/07/2026",
    fabricante=None, t_cal=22.0, p_cal=101.325, h_cal=50.0, v1=None,
)


def _preparar_equipo(ruta):
    con = sqlite3.connect(ruta)
    cur = con.execute("""
        INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2,
            fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1, activo, vigente)
        VALUES (:equip_type, :model, :serie, :calibr_fact, :calibr_fact2,
            :fecha_calibr, :fabricante, :t_cal, :p_cal, :h_cal, :v1, 1, 0)
    """, _CERT_DEFECTO)
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


class _TextoNoBindeable:
    def text(self):
        return ["no bindable"]


def _instancia_con_formulario(id_equipo, fabricante_widget=None):
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.cargartabla = lambda: None
    obj.tipo = QComboBox()
    obj.tipo.addItem(_CERT_DEFECTO["equip_type"])
    obj.modelo = QLineEdit(_CERT_DEFECTO["model"])
    obj.serie = QLineEdit(_CERT_DEFECTO["serie"])
    obj.calib_factor = QLineEdit(str(_CERT_DEFECTO["calibr_fact"]))
    obj.calib_date = QLineEdit(_CERT_DEFECTO["fecha_calibr"])
    obj.fabricante = fabricante_widget if fabricante_widget is not None else QLineEdit("")
    obj.t_cal = QLineEdit(str(_CERT_DEFECTO["t_cal"]))
    obj.p_cal = QLineEdit(str(_CERT_DEFECTO["p_cal"]))
    obj.h_cal = QLineEdit(str(_CERT_DEFECTO["h_cal"]))
    obj.v1_cal = QLineEdit("")
    obj.sel_activo = QCheckBox()
    obj.sel_activo.setChecked(True)

    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem()
    item.setData(Qt.UserRole, id_equipo)
    obj.table.setItem(0, 0, item)
    obj.table.setCurrentCell(0, 0)
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA6GuardarCambiosCierraSiempre:
    def test_insert_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        id_equipo = _preparar_equipo(bd_temporal)
        obj = _instancia_con_formulario(id_equipo, fabricante_widget=_TextoNoBindeable())

        with pytest.raises(sqlite3.ProgrammingError):
            Config.guardarCambios(obj)

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el INSERT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        id_equipo = _preparar_equipo(bd_temporal)
        obj = _instancia_con_formulario(id_equipo, fabricante_widget=QLineEdit("PTW"))

        Config.guardarCambios(obj)

        con = sqlite3.connect(bd_temporal)
        n = con.execute(
            "SELECT COUNT(*) FROM equipos WHERE fabricante = ? AND activo = 1",
            ("PTW",)).fetchone()[0]
        con.close()
        assert n == 1
