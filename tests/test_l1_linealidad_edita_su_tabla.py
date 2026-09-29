"""L.1 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, segunda ronda): Linealidad
edita su propia tabla, por el mismo camino que el mensual de braqui.

CAUSA (§1.8 del plan): `Linealidad.button_click` era copia del de la
pantalla diaria (`PruebaDiariaBraq`) -- "Guardar" le ponía los TÍTULOS DEL
DIARIO a la tabla lateral de linealidad; "Editar"/"Aceptar"/"Cancelar"
apuntaban al camino de edición del DIARIO, que escribe sobre `braqui` con
el mismo `id` que la fila de linealidad -- solo no ocurría porque los ids
no coincidían.

Este archivo prueba que "Guardar", "Editar", "Aceptar" y "Cancelar" ya
nunca tocan los títulos ni la tabla `braqui`, y que una edición escribe
EXACTAMENTE la columna de su propia celda en `LinealidadBraquiterapia`.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad, PruebaDiariaBraq
import ui.paginasGuia.dialogs as dialogs_mod


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
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Cristian Castellanos", 1, 1, "fisico"))
    conexion.con.execute(
        "INSERT INTO LinealidadBraquiterapia "
        "(id, user, fecha, modelo, serie_cp, calibracion, modelo_elec, "
        "serie_ele, electrometro, q_est, t_integrado, i_est, "
        "reproducibilidad, exactitud, tiempo_transito) VALUES "
        "(10, 'Cristian Castellanos', '2026-06-26', 'HDR1000 Plus', "
        "'A092535', 464700.0, 'Unidos-E', '2343', 1.0, 2510.3, 60.0, "
        "2.5, 99.8, 0.997, 3.14)")
    conexion.con.commit()
    yield ruta
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None
    _reset_qtsql_default_connection()


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for modulo in (braq_mod, load_mod):
        for tipo in ("information", "warning", "critical", "question"):
            monkeypatch.setattr(modulo.QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture(autouse=True)
def _permiso_de_edicion_concedido(monkeypatch):
    """`verificar_editar` (load.py) importa `DialogAdminPermisoEditar`
    DENTRO de la función (`from ui.paginasGuia.dialogs import ...`), así
    que se sustituye en su módulo de origen -- el import local recoge la
    versión sustituida en cada llamada."""
    class _DialogoFalso:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(dialogs_mod, "DialogAdminPermisoEditar", _DialogoFalso)


class _UsuarioFalso:
    def __init__(self, nombre="Cristian Castellanos"):
        self._nombre = nombre


def _fila_bd(ruta, col, id_pk=10):
    con = sqlite3.connect(ruta)
    valor = con.execute(
        f"SELECT {col} FROM LinealidadBraquiterapia WHERE id=?", (id_pk,)).fetchone()[0]
    con.close()
    return valor


def _huella_tabla(table):
    """(títulos, filas, columnas, texto de cada celda) -- para comparar
    antes/después sin asumir qué cambia."""
    titulos = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
    celdas = [[table.item(r, c).text() if table.item(r, c) else None
               for c in range(table.columnCount())]
              for r in range(table.rowCount())]
    return titulos, table.rowCount(), table.columnCount(), celdas


def _col_de(table, titulo):
    for c in range(table.columnCount()):
        if table.horizontalHeaderItem(c).text() == titulo:
            return c
    raise AssertionError(f"no existe la columna {titulo!r}")


def _fila_de(table, id_pk, col_id=0):
    for r in range(table.rowCount()):
        item = table.item(r, col_id)
        if item is not None and item.data(Qt.UserRole) == id_pk:
            return r
    raise AssertionError(f"no existe una fila con id={id_pk}")


# ---------------------------------------------------------------------------
# (a) Títulos y filas estables: "Guardar", "Editar"->"Aceptar",
# "Editar"->"Cancelar" nunca reemplazan la tabla lateral por la del diario.
# ---------------------------------------------------------------------------

def test_guardar_no_cambia_los_titulos_de_la_tabla(app, monkeypatch, bd_temporal):
    """`guardar_linealidad` (el guardado en sí) está conectado a `btn_add`
    por FUERA de `button_click` (línea 2456) y exige llenar todo el
    formulario -- ajeno al alcance de L.1. Se sustituye por un no-op para
    aislar EXACTAMENTE lo que `button_click` conecta a esa misma señal:
    antes de L.1, un clic disparaba las DOS cosas (guardar_linealidad Y
    `asignar_encabezados(self, 'braqui')`, esta última con los 27 títulos
    del diario) -- con el no-op puesto, cualquier cambio de título que
    sobreviva viene de la segunda conexión."""
    d = Linealidad(_UsuarioFalso())
    d._cargar_datos_diferidos()
    monkeypatch.setattr(d, "guardar_linealidad", lambda: None)
    titulos_antes, _, _, _ = _huella_tabla(d.table)

    d.btn_add.click()

    titulos_despues, filas_despues, cols_despues, _ = _huella_tabla(d.table)
    assert titulos_despues == titulos_antes, (
        "'Guardar' no debe reemplazar los títulos de LECTURAS DEL MÁXIMO "
        "por los 27 títulos del diario")
    assert titulos_despues != [""] * len(titulos_despues)
    # La tabla sigue siendo la de linealidad (pocas columnas), no la del
    # diario (27 columnas booleanas).
    assert cols_despues < 20
    assert "Usuario" in titulos_despues and "Fecha" in titulos_despues


def test_editar_aceptar_no_cambia_los_titulos_ni_las_filas(app, monkeypatch, bd_temporal):
    d = Linealidad(_UsuarioFalso())
    d._cargar_datos_diferidos()
    titulos_antes, filas_antes, cols_antes, _ = _huella_tabla(d.table)

    fila = _fila_de(d.table, 10)
    col = _col_de(d.table, "Q_est")
    d.table.setCurrentCell(fila, col)
    d.edit_table.click()
    d.table.item(fila, col).setText("2511.0")
    d.accept_edit.click()

    titulos_despues, filas_despues, cols_despues, _ = _huella_tabla(d.table)
    assert titulos_despues == titulos_antes
    assert filas_despues == filas_antes
    assert cols_despues == cols_antes


def test_editar_cancelar_no_cambia_los_titulos_ni_las_filas(app, monkeypatch, bd_temporal):
    d = Linealidad(_UsuarioFalso())
    d._cargar_datos_diferidos()
    titulos_antes, filas_antes, cols_antes, _ = _huella_tabla(d.table)

    fila = _fila_de(d.table, 10)
    col = _col_de(d.table, "Q_est")
    d.table.setCurrentCell(fila, col)
    d.edit_table.click()
    d.table.item(fila, col).setText("2511.0")
    d.cancel_edit.click()

    titulos_despues, filas_despues, cols_despues, _ = _huella_tabla(d.table)
    assert titulos_despues == titulos_antes
    assert filas_despues == filas_antes
    assert cols_despues == cols_antes


# ---------------------------------------------------------------------------
# (b) La edición escribe SU registro de LinealidadBraquiterapia.
# ---------------------------------------------------------------------------

def test_editar_q_est_escribe_en_linealidadbraquiterapia(app, monkeypatch, bd_temporal):
    d = Linealidad(_UsuarioFalso())
    d._cargar_datos_diferidos()

    fila = _fila_de(d.table, 10)
    col = _col_de(d.table, "Q_est")
    d.table.setCurrentCell(fila, col)
    d.edit_table.click()
    d.table.item(fila, col).setText("2511.0")
    d.accept_edit.click()

    assert _fila_bd(bd_temporal, "q_est") == 2511.0
    # Nada más cambia.
    assert _fila_bd(bd_temporal, "user") == "Cristian Castellanos"
    assert _fila_bd(bd_temporal, "exactitud") == 0.997


def test_editar_registra_en_audit_log(app, monkeypatch, bd_temporal):
    d = Linealidad(_UsuarioFalso())
    d._cargar_datos_diferidos()

    fila = _fila_de(d.table, 10)
    col = _col_de(d.table, "Q_est")
    d.table.setCurrentCell(fila, col)
    d.edit_table.click()
    d.table.item(fila, col).setText("2511.0")
    d.accept_edit.click()

    con = sqlite3.connect(bd_temporal)
    filas = con.execute(
        "SELECT tabla, ref FROM audit_log WHERE tabla='LinealidadBraquiterapia'").fetchall()
    con.close()
    assert filas, "debía quedar una fila de auditoría de LinealidadBraquiterapia"
    assert filas[-1] == ("LinealidadBraquiterapia", "10")


# ---------------------------------------------------------------------------
# (c) El caso grave: una fila DIARIA con el mismo id no se toca.
# ---------------------------------------------------------------------------

def test_editar_linealidad_no_toca_la_fila_diaria_con_el_mismo_id(app, monkeypatch, bd_temporal):
    con = sqlite3.connect(bd_temporal)
    con.execute(
        "INSERT INTO braqui (id, date, lum_puerta) VALUES (10, '2026-06-26 10:00:00', 5.5)")
    con.commit()
    con.close()

    d = Linealidad(_UsuarioFalso())
    d._cargar_datos_diferidos()
    fila = _fila_de(d.table, 10)
    col = _col_de(d.table, "Q_est")
    d.table.setCurrentCell(fila, col)
    d.edit_table.click()
    d.table.item(fila, col).setText("2511.0")
    d.accept_edit.click()

    con = sqlite3.connect(bd_temporal)
    lum_puerta = con.execute("SELECT lum_puerta FROM braqui WHERE id=10").fetchone()[0]
    con.close()
    assert lum_puerta == 5.5, "la fila DIARIA con el mismo id no debía tocarse"


# ---------------------------------------------------------------------------
# (d) Con W.1: editar "Usuario" escribe la columna `user`, no `fecha`.
# ---------------------------------------------------------------------------

def test_editar_usuario_escribe_user_no_fecha(app, monkeypatch, bd_temporal):
    d = Linealidad(_UsuarioFalso())
    d._cargar_datos_diferidos()

    fila = _fila_de(d.table, 10)
    col = _col_de(d.table, "Usuario")
    d.table.setCurrentCell(fila, col)
    d.edit_table.click()
    d.table.item(fila, col).setText("Otro Físico")
    d.accept_edit.click()

    assert _fila_bd(bd_temporal, "user") == "Otro Físico"
    assert _fila_bd(bd_temporal, "fecha") == "2026-06-26"


# ---------------------------------------------------------------------------
# Receptores: un clic, un guardado (ninguna conexión duplicada).
# ---------------------------------------------------------------------------

def test_receptores_de_guardar_editar_aceptar_cancelar(app, bd_temporal):
    d = Linealidad(_UsuarioFalso())
    assert d.btn_add.receivers(d.btn_add.clicked) == 1
    assert d.edit_table.receivers(d.edit_table.clicked) == 1
    assert d.accept_edit.receivers(d.accept_edit.clicked) == 1
    assert d.cancel_edit.receivers(d.cancel_edit.clicked) == 1


# ---------------------------------------------------------------------------
# Lo viejo sigue igual: la pantalla DIARIA no cambia.
# ---------------------------------------------------------------------------

def test_la_pantalla_diaria_no_cambia(app, bd_temporal):
    d = PruebaDiariaBraq(_UsuarioFalso())
    # La diaria sigue con su propio camino de edición (heredado), no el
    # de load.py -- L.1 solo tocó `Linealidad.button_click`.
    assert d.edit_table.receivers(d.edit_table.clicked) == 1
    assert d.accept_edit.receivers(d.accept_edit.clicked) == 3
    assert d.cancel_edit.receivers(d.cancel_edit.clicked) == 3
