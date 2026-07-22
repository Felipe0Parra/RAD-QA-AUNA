"""A2-bis (§8.1 H1 del PLAN_AUDITORIA_DOS_EJES_21-07): el borrado DIARIO
(`eliminarfilas`, data/GraficasyTablas/tablas.py) ahora deja rastro.

Hallazgo del rebuild 22-07: el DELETE es físico y tablas.py no tenía
NINGUNA llamada de auditoría -- A2 solo cubrió las rutas de load.py
(mensual/anual/CT). El físico reportó: "elimino un registro diario del
iX... lo grave es que no parece quedar rastro del registro eliminado".
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

import data.ManejoDatos.conection as conection_mod
import data.GraficasyTablas.tablas as tablas_mod
from data.ManejoDatos.user import Usuario


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)

    # Conexión de SETUP con nombre propio -- eliminarfilas() gestiona su
    # propia conexión "qt_sql_default_connection"; usar un nombre distinto
    # aquí evita pisarla mientras se prepara la tabla de prueba.
    db = QSqlDatabase.addDatabase("QSQLITE", "conexion_setup_a2bis")
    db.setDatabaseName(ruta)
    assert db.open()
    QSqlQuery(db).exec(
        "CREATE TABLE aceleradorlineal_ix (id INTEGER PRIMARY KEY, date TEXT, dato TEXT)")
    QSqlQuery(db).exec(
        "INSERT INTO aceleradorlineal_ix (id, date, dato) VALUES (1, '01/07/2026', 'valor_x')")
    db.close()
    QSqlDatabase.removeDatabase("conexion_setup_a2bis")

    yield ruta

    # eliminarfilas() deja abierta "qt_sql_default_connection" -- limpiarla
    # entre tests, si no el siguiente test la reutilizaría apuntando a la
    # BD temporal de ESTE test (setDatabaseName solo corre si la conexión
    # no existía todavía).
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    if os.path.exists(ruta):
        os.remove(ruta)


class _ItemFalso:
    def __init__(self, texto):
        self._texto = texto

    def text(self):
        return self._texto


class _TablaFalsa:
    """Imita lo mínimo que eliminarfilas() lee de self.table."""

    def __init__(self, id_fila):
        self._id_fila = id_fila

    def currentRow(self):
        return 0

    def item(self, row, col):
        return _ItemFalso(str(self._id_fila))


class _WidgetFalso(QWidget):
    def __init__(self, id_fila=1, usuario=None):
        super().__init__()
        self.table = _TablaFalsa(id_fila)
        self.user_id = usuario


class TestA2BisAuditaElBorradoDiario:

    def test_registra_eliminar_con_la_fila_completa(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(tablas_mod.QMessageBox, "question",
                             staticmethod(lambda *a, **k: tablas_mod.QMessageBox.Yes))
        monkeypatch.setattr(tablas_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))

        widget = _WidgetFalso(id_fila=1, usuario=Usuario(fullname="Cristian Castellanos"))
        tablas_mod.eliminarfilas(widget, "aceleradorlineal_ix")

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchone()
        con.close()

        assert fila is not None, "eliminarfilas no dejó ningún rastro en audit_log"
        usuario, accion, tabla, ref, detalle = fila
        assert usuario == "Cristian Castellanos"
        assert accion == "eliminar"
        assert tabla == "aceleradorlineal_ix"
        assert ref == "1"
        assert "date=01/07/2026" in detalle
        assert "dato=valor_x" in detalle

    def test_la_fila_realmente_desaparece(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(tablas_mod.QMessageBox, "question",
                             staticmethod(lambda *a, **k: tablas_mod.QMessageBox.Yes))
        monkeypatch.setattr(tablas_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))

        widget = _WidgetFalso(id_fila=1)
        tablas_mod.eliminarfilas(widget, "aceleradorlineal_ix")

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM aceleradorlineal_ix").fetchone()[0]
        con.close()
        assert n == 0

    def test_cancelar_no_borra_ni_audita(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(tablas_mod.QMessageBox, "question",
                             staticmethod(lambda *a, **k: tablas_mod.QMessageBox.No))

        widget = _WidgetFalso(id_fila=1)
        tablas_mod.eliminarfilas(widget, "aceleradorlineal_ix")

        con = sqlite3.connect(bd_temporal)
        n_filas = con.execute("SELECT COUNT(*) FROM aceleradorlineal_ix").fetchone()[0]
        n_audit = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='audit_log'"
        ).fetchone()[0]
        con.close()
        assert n_filas == 1, "cancelar (No) no debe borrar nada"
        assert n_audit == 0, "cancelar no debe ni siquiera crear audit_log"

    def test_sin_usuario_no_revienta(self, app, bd_temporal, monkeypatch):
        """usuario_actual(obj) puede devolver None -- registrar() debe
        aceptarlo (best-effort, ver services/audit_minimo.py), no lanzar."""
        monkeypatch.setattr(tablas_mod.QMessageBox, "question",
                             staticmethod(lambda *a, **k: tablas_mod.QMessageBox.Yes))
        monkeypatch.setattr(tablas_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))

        widget = _WidgetFalso(id_fila=1, usuario=None)
        tablas_mod.eliminarfilas(widget, "aceleradorlineal_ix")  # no debe lanzar

        con = sqlite3.connect(bd_temporal)
        usuario = con.execute("SELECT usuario FROM audit_log").fetchone()[0]
        con.close()
        assert usuario is None
