"""A3-bis (§8.1 H2 del PLAN_AUDITORIA_DOS_EJES_21-07): la edición DIARIA
(`cargarDatosEditados`, PruebasDiarias.py) ahora deja rastro.

Hallazgo del rebuild 22-07: A3 solo auditó `editar_tablas` (load.py, rutas
mensual/anual); `cargarDatosEditados` (la ruta de edición de las tablas
DIARIAS) hacía el UPDATE + commit sin auditar nada. El físico reportó:
"editar un valor numérico sí se puede pero se registra esta edición como un
login" -- el login era la reautenticación de DialogAdminPermisoEditar (A8),
y la edición real no dejaba ningún rastro propio.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget, QTableWidget, QTableWidgetItem
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

import data.ManejoDatos.conection as conection_mod
import ui.paginasControles.PruebasDiarias.PruebasDiarias as pd_mod
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from data.ManejoDatos.user import Usuario


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)

    db = QSqlDatabase.addDatabase("QSQLITE", "conexion_setup_a3bis")
    db.setDatabaseName(ruta)
    assert db.open()
    QSqlQuery(db).exec(
        "CREATE TABLE aceleradorlineal_ix (id INTEGER PRIMARY KEY, camilla_vert_desp TEXT)")
    QSqlQuery(db).exec(
        "INSERT INTO aceleradorlineal_ix (id, camilla_vert_desp) VALUES (30, '1.000')")
    db.close()
    QSqlDatabase.removeDatabase("conexion_setup_a3bis")

    yield ruta

    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    if os.path.exists(ruta):
        os.remove(ruta)


def _widget_con_celda_editada(id_valor="30", nuevo_valor="55", usuario=None):
    """Un PruebaBasico mínimo, con la tabla y el mapeo de columnas que
    cargarDatosEditados necesita -- item.row()/item.column() exigen un
    QTableWidgetItem REAL insertado en una tabla, no un doble de prueba."""
    w = PruebaBasico(user_id=usuario)
    w.user_id = usuario
    w.table = QTableWidget(1, 2)
    w.table.setItem(0, 0, QTableWidgetItem(id_valor))
    item_editado = QTableWidgetItem(nuevo_valor)
    w.table.setItem(0, 1, item_editado)
    w.encabezados_actuales = {0: "id", 1: "camilla_vert_desp"}
    w.edit_table = QWidget()
    w.search_bar = QWidget()
    w.accept_edit = QWidget()
    w.cancel_edit = QWidget()
    w.btn_delete = QWidget()
    return w, item_editado


class TestA3BisAuditaLaEdicionDiaria:

    def test_registra_editar_con_columna_y_valores(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(pd_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        w, item = _widget_con_celda_editada(
            usuario=Usuario(fullname="Cristian Castellanos"))

        w.cargarDatosEditados(item, "1.000", "aceleradorlineal_ix")

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchone()
        con.close()

        assert fila is not None, "cargarDatosEditados no dejó ningún rastro en audit_log"
        usuario, accion, tabla, ref, detalle = fila
        assert usuario == "Cristian Castellanos"
        assert accion == "editar"
        assert tabla == "aceleradorlineal_ix"
        assert ref == "30"
        assert "camilla_vert_desp" in detalle
        assert "1.000" in detalle
        assert "55" in detalle

    def test_el_valor_realmente_cambio_en_bd(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(pd_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        w, item = _widget_con_celda_editada()

        w.cargarDatosEditados(item, "1.000", "aceleradorlineal_ix")

        con = sqlite3.connect(bd_temporal)
        valor = con.execute(
            "SELECT camilla_vert_desp FROM aceleradorlineal_ix WHERE id=30").fetchone()[0]
        con.close()
        assert valor == "55"

    def test_sin_cambio_real_no_audita(self, app, bd_temporal, monkeypatch):
        """new_value == old_value: cargarDatosEditados corta antes de tocar
        la BD -- no debe auditar tampoco."""
        monkeypatch.setattr(pd_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        w, item = _widget_con_celda_editada(id_valor="30", nuevo_valor="1.000")

        w.cargarDatosEditados(item, "1.000", "aceleradorlineal_ix")

        con = sqlite3.connect(bd_temporal)
        n_audit = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='audit_log'"
        ).fetchone()[0]
        con.close()
        assert n_audit == 0

    def test_sin_usuario_no_revienta(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(pd_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        w, item = _widget_con_celda_editada(usuario=None)

        w.cargarDatosEditados(item, "1.000", "aceleradorlineal_ix")  # no debe lanzar

        con = sqlite3.connect(bd_temporal)
        usuario = con.execute("SELECT usuario FROM audit_log").fetchone()[0]
        con.close()
        assert usuario is None
