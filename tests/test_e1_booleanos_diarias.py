"""E1 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §2): editar "Funciona/No
Funciona" en las diarias ya no corrompe el tipo de dato.

Las columnas booleanas de las 4 tablas diarias son INTEGER pero se pintan
como texto; `cargarDatosEditados` escribía la cadena mostrada tal cual y
SQLite (tipado dinámico) la guardaba como TEXT sin error -- la celda dejaba
de pintarse como booleano y el físico veía que sus ediciones "no se
aceptaban" (rebuild 28-07). Ahora el texto se traduce a 0/1 (insensible a
mayúsculas/espacios) y un valor no traducible NO se escribe. Los dos caminos
de edición (directa y reemplazo) se conservan (decisión D4).
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
from data.GraficasyTablas.tablas import load_table
from ui.paginasControles.PruebasDiarias.PruebasDiarias import (
    PruebaBasico, traducir_booleano_editado)
from data.ManejoDatos.user import Usuario

RUTA_PRODUCCION_REAL = os.path.join(
    os.path.dirname(__file__), "..", "..", "BaseDatosQA.db")

TABLAS_DIARIAS = ["braqui", "aceleradorlineal_600", "aceleradorlineal_ix", "halcyon"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)

    db = QSqlDatabase.addDatabase("QSQLITE", "conexion_setup_e1")
    db.setDatabaseName(ruta)
    assert db.open()
    QSqlQuery(db).exec(
        "CREATE TABLE aceleradorlineal_600 "
        "(id INTEGER PRIMARY KEY, date TEXT, luces_consola INTEGER)")
    QSqlQuery(db).exec(
        "INSERT INTO aceleradorlineal_600 (id, date, luces_consola) "
        "VALUES (7, '01/07/2026', 1)")
    db.close()
    QSqlDatabase.removeDatabase("conexion_setup_e1")

    yield ruta

    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    if os.path.exists(ruta):
        os.remove(ruta)


def _widget_con_celda_booleana(nuevo_texto):
    """PruebaBasico mínimo con una celda booleana editada (mismo arnés que
    test_a3_bis; la celda 1 mapea a la columna booleana luces_consola)."""
    w = PruebaBasico(user_id=Usuario(fullname="Físico de Prueba"))
    w.table = QTableWidget(1, 2)
    w.table.setItem(0, 0, QTableWidgetItem("7"))
    item = QTableWidgetItem(nuevo_texto)
    w.table.setItem(0, 1, item)
    w.encabezados_actuales = {0: "id", 1: "luces_consola"}
    w.boolean_colums = {"luces_consola"}
    w.edit_table = QWidget()
    w.search_bar = QWidget()
    w.accept_edit = QWidget()
    w.cancel_edit = QWidget()
    w.btn_delete = QWidget()
    return w, item


class TestTraduccion:
    @pytest.mark.parametrize("texto,esperado", [
        ("Funciona", 1),
        ("No Funciona", 0),
        ("No funciona", 0),          # el caso real de la BD del físico
        ("  no   FUNCIONA  ", 0),    # espacios y mayúsculas arbitrarios
        ("funciona", 1),
        ("1", 1),
        ("0", 0),
        ("quizá", None),
        ("", None),
        (None, None),
    ])
    def test_traducir_booleano_editado(self, texto, esperado):
        assert traducir_booleano_editado(texto) == esperado


class TestEdicionBooleana:
    def test_editar_a_no_funciona_guarda_entero_cero(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(pd_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        w, item = _widget_con_celda_booleana("No funciona")  # tecleado a mano

        w.cargarDatosEditados(item, "Funciona", "aceleradorlineal_600")

        con = sqlite3.connect(bd_temporal)
        tipo, valor = con.execute(
            "SELECT typeof(luces_consola), luces_consola "
            "FROM aceleradorlineal_600 WHERE id=7").fetchone()
        con.close()
        assert (tipo, valor) == ("integer", 0)

    def test_ida_y_vuelta_la_celda_se_vuelve_a_pintar_como_booleano(
            self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(pd_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        w, item = _widget_con_celda_booleana("No Funciona")
        w.cargarDatosEditados(item, "Funciona", "aceleradorlineal_600")

        load_table(w, {"luces_consola"}, None, "aceleradorlineal_600")

        # localizar la columna por su encabezado real
        headers = [w.table.horizontalHeaderItem(c).text()
                   for c in range(w.table.columnCount())]
        col = headers.index("luces_consola")
        assert w.table.item(0, col).text() == "No Funciona"

    def test_valor_no_traducible_no_escribe_y_avisa(self, app, bd_temporal, monkeypatch):
        avisos = []
        monkeypatch.setattr(pd_mod.QMessageBox, "warning",
                            staticmethod(lambda *a, **k: avisos.append(a[2])))
        w, item = _widget_con_celda_booleana("quizá")

        w.cargarDatosEditados(item, "Funciona", "aceleradorlineal_600")

        con = sqlite3.connect(bd_temporal)
        tipo, valor = con.execute(
            "SELECT typeof(luces_consola), luces_consola "
            "FROM aceleradorlineal_600 WHERE id=7").fetchone()
        n_audit = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='audit_log'").fetchone()[0]
        con.close()
        assert (tipo, valor) == ("integer", 1)     # intacto
        assert n_audit == 0                        # nada que auditar
        assert len(avisos) == 1 and "quizá" in avisos[0]
        assert item.text() == "Funciona"           # la celda vuelve a lo real

    def test_columna_no_booleana_sigue_aceptando_texto(self, app, bd_temporal, monkeypatch):
        """El traductor solo aplica a boolean_colums -- una columna normal
        (p.ej. observaciones) sigue guardando el texto tal cual."""
        monkeypatch.setattr(pd_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        w, item = _widget_con_celda_booleana("nota libre")
        w.encabezados_actuales = {0: "id", 1: "date"}  # date es TEXT

        w.cargarDatosEditados(item, "01/07/2026", "aceleradorlineal_600")

        con = sqlite3.connect(bd_temporal)
        valor = con.execute(
            "SELECT date FROM aceleradorlineal_600 WHERE id=7").fetchone()[0]
        con.close()
        assert valor == "nota libre"


class TestTripwireDatosReales:
    def test_ninguna_columna_integer_diaria_contiene_texto(self):
        """Tripwire sobre la BD de producción (solo lectura): si alguna vía
        vuelve a escribir cadenas en columnas INTEGER de las diarias, esto se
        pone rojo aunque la UI parezca funcionar."""
        if not os.path.exists(RUTA_PRODUCCION_REAL):
            pytest.skip("BaseDatosQA.db real no está presente en este entorno")
        con = sqlite3.connect(f"file:{RUTA_PRODUCCION_REAL}?mode=ro", uri=True)
        try:
            corruptas = []
            for tabla in TABLAS_DIARIAS:
                columnas = con.execute(f"PRAGMA table_info('{tabla}')").fetchall()
                for _, nombre, tipo, *_ in columnas:
                    if tipo.upper() != "INTEGER" or nombre == "id":
                        continue
                    n = con.execute(
                        f"SELECT COUNT(*) FROM {tabla} "
                        f"WHERE typeof({nombre}) = 'text'").fetchone()[0]
                    if n:
                        corruptas.append((tabla, nombre, n))
        finally:
            con.close()
        assert corruptas == [], (
            "columnas INTEGER de las diarias con texto guardado: " + repr(corruptas))
