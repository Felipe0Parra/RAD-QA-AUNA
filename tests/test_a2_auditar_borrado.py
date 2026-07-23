"""A2 (PLAN_AUDITORIA_DOS_EJES_21-07): el borrado deja rastro en `audit_log`.

Antes de esta tarea, `eliminarRegistro`/`eliminarRegistroCT`/
`eliminarRegistroCT_anual` (load.py) hacían DELETE físico sin llamar
`registrar()` -- un control de QC podía desaparecer sin dejar rastro de
quién lo borró, cuándo, ni qué contenía. Ahora cada uno, tras la operación
exitosa, registra la fila SERIALIZADA en `detalle`.

C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): las 3 funciones, cuando la
tabla es "controles" (la raíz de la jerarquía mensual/anual/CT), YA NO
hacen DELETE físico -- anulan (`activo = 0`, acción `"anular"`). El físico
señaló que no había ningún soft-delete ("¿dónde queda el registro borrado
en caso de querer reponerlo?"); estos tests quedan actualizados para el
nuevo comportamiento (ver test_c2_soft_delete_controles.py para la cobertura
completa: tablas de detalle intactas, filtrado en los listados, etc.).

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
    def test_anula_controles_y_audita_con_la_fila_serializada(self, app, bd_temporal, monkeypatch):
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
        fila = con.execute("SELECT COUNT(*), activo FROM controles").fetchone()
        con.close()
        assert fila[0] == 1, "C2: anular ya no borra la fila -- queda como histórico"
        assert fila[1] == 0, "la fila debe quedar marcada activo=0"

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla_auditada, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "anular"
        assert tabla_auditada == "controles"
        assert ref == "1"
        assert "equipo=Halcyon" in detalle, (
            "detalle debe traer la fila serializada tal como estaba al anularse")


class TestEliminarRegistroCTAuditaLaSesion:
    def test_anula_y_audita_la_fila_de_controles(self, app, bd_temporal, monkeypatch):
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
        fila = con.execute("SELECT COUNT(*), activo FROM controles").fetchone()
        con.close()
        assert fila[0] == 1, "C2: anular ya no borra la fila"
        assert fila[1] == 0

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla_auditada, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "anular"
        assert tabla_auditada == "controles"
        assert ref == "5"
        assert "CT diario" in detalle and "equipo=TAC" in detalle


class TestEliminarRegistroCTAnualAuditaLaSesion:
    def test_anula_y_audita_la_fila_de_controles(self, app, bd_temporal, monkeypatch):
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
        fila = con.execute("SELECT COUNT(*), activo FROM controles").fetchone()
        con.close()
        assert fila[0] == 1, "C2: anular ya no borra la fila"
        assert fila[1] == 0

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla_auditada, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "anular"
        assert tabla_auditada == "controles"
        assert ref == "7"
        assert "CT anual" in detalle and "equipo=TAC" in detalle
