"""A3 (PLAN_AUDITORIA_DOS_EJES_21-07): la edición in-place deja rastro en
`audit_log`.

Antes de esta tarea, `guardarEdicion` (load.py) hacía `UPDATE ... SET col=?`
sin llamar `registrar()` -- un valor de QC se podía corregir sin dejar
constancia de cuál era el valor anterior. `old_value` ya estaba disponible
en la función (se usa para detectar "sin cambios" antes del UPDATE), así que
no hace falta un SELECT extra: el `detalle` queda como "columna:
viejo→nuevo".

Usa `QSqlDatabase` real (QSQLITE) por el mismo motivo que A2
(`PruebaBasico().opeenDatabase()` -- ver docstring de test_a2_auditar_borrado.py).
"""
import sqlite3

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import guardarEdicion


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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _DlgFalso(QWidget):
    """Página real (QWidget): trae el contexto de edición en curso
    (old_value/editing_item/editing_row/editing_col, tal como lo deja el
    click en una celda editable) + los 4 widgets que guardarEdicion
    muestra/oculta al final -- reales para no tener que fingir hide()/show()."""

    def __init__(self, old_value, new_value, editing_col=0):
        super().__init__()
        self.user_id = _UsuarioFalso()
        self.old_value = old_value
        self.editing_row = 0
        self.editing_col = editing_col
        self.editing_item = QTableWidgetItem(new_value)
        self.accept_edit = QWidget()
        self.cancel_edit = QWidget()
        self.btn_delete = QWidget()
        self.edit_table = QWidget()


def _tabla_con_metadata(row_id, col_data, col=0):
    tabla = QTableWidget(1, col + 1)
    item = QTableWidgetItem("x")
    item.setData(Qt.UserRole, row_id)
    item.setData(Qt.UserRole + 1, col_data)
    tabla.setItem(0, col, item)
    return tabla


def _audit_log(ruta_db):
    con = sqlite3.connect(ruta_db)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestGuardarEdicionAuditaElCambio:
    def test_update_exitoso_registra_viejo_y_nuevo(self, app, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (3, 'Halcyon', 'diario', '2026-07-01', 'Otro Fisico')")
        con.commit()
        con.close()

        dlg = _DlgFalso(old_value="Halcyon", new_value="Halcyon2")
        tabla = _tabla_con_metadata(row_id=3, col_data="equipo")

        guardarEdicion(dlg, tabla, "controles", id_ref=3)

        con = sqlite3.connect(bd_temporal)
        (equipo,) = con.execute("SELECT equipo FROM controles WHERE id=3").fetchone()
        con.close()
        assert equipo == "Halcyon2", "el UPDATE debe seguir funcionando igual que antes"

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla_auditada, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "editar"
        assert tabla_auditada == "controles"
        assert ref == "3"
        assert "equipo" in detalle and "Halcyon" in detalle and "Halcyon2" in detalle

    def test_sin_cambios_no_audita(self, app, bd_temporal):
        """Si el valor no cambió, guardarEdicion cancela antes del UPDATE --
        no debe auditar nada (no hay nada que reconstruir)."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (4, 'Halcyon', 'diario', '2026-07-01', 'Otro Fisico')")
        con.commit()
        con.close()

        dlg = _DlgFalso(old_value="Halcyon", new_value="Halcyon")  # mismo valor
        tabla = _tabla_con_metadata(row_id=4, col_data="equipo")

        guardarEdicion(dlg, tabla, "controles", id_ref=4)

        assert _audit_log(bd_temporal) == []
