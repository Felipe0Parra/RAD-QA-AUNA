"""A2 (PLAN_AUDITORIA_DOS_EJES_21-07): el borrado deja rastro en `audit_log`.

Antes de esta tarea, `eliminarRegistro`/`eliminarRegistroCT`/
`eliminarRegistroCT_anual` (load.py) hacían DELETE físico sin llamar
`registrar()` -- un control de QC podía desaparecer sin dejar rastro de
quién lo borró, cuándo, ni qué contenía. Ahora cada uno, tras el DELETE
exitoso, registra `"eliminar"` con la fila borrada SERIALIZADA en `detalle`
-- la única forma de reconstruir algo que ya no está en la BD, porque el
borrado sigue siendo físico (decisión de producto aparte, pregunta abierta
§4.4 del plan).

Usa `QSqlDatabase` real (QSQLITE) porque estas 3 funciones usan
`PruebaBasico().opeenDatabase()`, un patrón de conexión Qt aparte del
sqlite3-vía-`Conexion()` del resto de la app (el "doble patrón de conexión"
ya documentado). El esquema se crea primero con la `Conexion()` real (que ya
sabe crear las 69 tablas) y se cierra esa conexión antes de que
`opeenDatabase()` abra la suya -- y como `qt_sql_default_connection` es un
registro GLOBAL de proceso (no por test), el fixture lo resetea antes y
después de cada test para que no se filtre entre tests.
"""
import sqlite3

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import eliminarRegistro, eliminarRegistroCT, eliminarRegistroCT_anual


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _reset_qtsql_default_connection():
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real -- crea las 69 tablas
    conexion.con.close()
    Conexion._instance = None

    _reset_qtsql_default_connection()
    yield ruta
    _reset_qtsql_default_connection()


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _DlgFalso:
    user_id = _UsuarioFalso()


def _tabla_con_fila(id_valor, texto="fila"):
    tabla = QTableWidget(1, 1)
    item = QTableWidgetItem(texto)
    item.setData(Qt.UserRole, id_valor)
    tabla.setItem(0, 0, item)
    tabla.setCurrentCell(0, 0)
    return tabla


def _audit_log(ruta_db):
    con = sqlite3.connect(ruta_db)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


def _no_confirmar_qmessagebox(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "question",
                         staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))


class TestEliminarRegistroAuditaElBorrado:
    def test_borra_y_audita_con_la_fila_serializada(self, app, bd_temporal, monkeypatch):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (1, 'Halcyon', 'diario', '2026-07-01', 'Otro Fisico')")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(1)

        eliminarRegistro(_DlgFalso(), tabla, "controles")

        con = sqlite3.connect(bd_temporal)
        quedan = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        con.close()
        assert quedan == 0, "el DELETE debe seguir funcionando igual que antes"

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla_auditada, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "eliminar"
        assert tabla_auditada == "controles"
        assert ref == "1"
        assert "equipo=Halcyon" in detalle, (
            "detalle debe traer la fila borrada serializada -- es la única "
            "forma de reconstruir un registro que un DELETE físico ya quitó")


class TestEliminarRegistroCTAuditaLaSesion:
    def test_borra_y_audita_la_fila_de_controles(self, app, bd_temporal, monkeypatch):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (5, 'TAC', 'mensual', '2026-06-01', 'Otro Fisico')")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(5, texto="Junio 2026")

        eliminarRegistroCT(_DlgFalso(), tabla)

        con = sqlite3.connect(bd_temporal)
        quedan = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        con.close()
        assert quedan == 0

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla_auditada, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "eliminar"
        assert tabla_auditada == "controles"
        assert ref == "5"
        assert "CT diario" in detalle and "equipo=TAC" in detalle


class TestEliminarRegistroCTAnualAuditaLaSesion:
    def test_borra_y_audita_la_fila_de_controles(self, app, bd_temporal, monkeypatch):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (7, 'TAC', 'anual', '2026-01-01', 'Otro Fisico')")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(7, texto="2026")

        eliminarRegistroCT_anual(_DlgFalso(), tabla)

        con = sqlite3.connect(bd_temporal)
        quedan = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        con.close()
        assert quedan == 0

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla_auditada, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "eliminar"
        assert tabla_auditada == "controles"
        assert ref == "7"
        assert "CT anual" in detalle and "equipo=TAC" in detalle
