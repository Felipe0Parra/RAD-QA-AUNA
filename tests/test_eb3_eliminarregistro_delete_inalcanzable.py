"""EB3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB3, 24-08): `eliminarRegistro`
(data/ManejoDatos/load.py) tiene dos ramas:

    if table_name in TABLAS_ANULABLES:
        anular_fila(...)          # nunca borra
    else:
        DELETE FROM "{table_name}" WHERE ...   # físico

El plan pedía verificar que la rama `DELETE` es **inalcanzable para toda
descendiente del bloque de QC** -- ya lo era desde MI1 (que amplió
`TABLAS_ANULABLES` a las 59 tablas del cierre transitivo), pero nadie lo
había demostrado con un test dedicado que uniera las piezas:

  1. IV2 (`test_iv2_completitud_inventario.py`) garantiza que
     `cierre_transitivo_fk() == TABLAS_ANULABLES ∪ EXCEPCIONES_INVENTARIO`
     -- ninguna tabla del bloque de QC puede quedar sin clasificar.
  2. `EXCEPCIONES_INVENTARIO` (hoy: `posicionamiento_reposicionamiento`,
     que EB7 retira) es la única abertura -- y esa tabla no tiene
     `CREATE TABLE` ni ruta de UI, así que la rama `DELETE` no puede
     alcanzarla en la práctica.
  3. `TestTripwireDeAlcance` (test_e7_soft_delete_bloque_qc.py) verifica
     estáticamente que ningún llamador real de
     `eliminarRegistro`/`verificar_eliminar`/etc. nombra, con un literal,
     una tabla de QC fuera de la lista blanca.

Este archivo cierra el círculo con una prueba DIRECTA: ejercita
`eliminarRegistro` sobre una MUESTRA representativa del inventario --
incluida una de las 30 tablas que MI1 movió (antes PENDIENTE-LF) -- y
confirma que la fila SOBREVIVE anulada, nunca desaparece.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import eliminarRegistro
from services.anulacion import TABLAS_ANULABLES
from services.lectura_vigente import (
    RAICES_QC, cierre_transitivo_fk, excepciones_inventario,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _reset_qtsql_default_connection():
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real
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


def _no_confirmar_qmessagebox(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "question",
                         staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))


class TestCompletitudQueHaceInalcanzableElDelete:
    """Las piezas que, juntas, prueban que la rama DELETE no puede
    alcanzar ninguna tabla del bloque de QC hoy."""

    def test_cierre_transitivo_es_tablas_anulables_mas_excepciones(self, bd_temporal):
        """Mismo par de comprobaciones que IV2 (no una igualdad estricta):
        `excepciones_inventario()` puede nombrar tablas que ya NO existen
        en una BD fresca (`equipos_anual`, retirada por MI5;
        `posicionamiento_reposicionamiento`, sin CREATE TABLE) -- eso es
        justo lo que las vuelve inalcanzables para eliminarRegistro, no un
        error de conteo."""
        con = sqlite3.connect(bd_temporal)
        try:
            cierre = cierre_transitivo_fk(con, RAICES_QC)
        finally:
            con.close()
        actuales = TABLAS_ANULABLES - RAICES_QC
        excepciones = set(excepciones_inventario())
        clasificadas = actuales | excepciones
        huecos = cierre - clasificadas
        assert not huecos, (
            f"tabla(s) del cierre sin clasificar -- si esto ocurre, IV2 "
            f"(test_iv2_completitud_inventario.py) ya lo habría detectado: "
            f"{huecos}")
        sobrantes = actuales - cierre
        assert not sobrantes, (
            f"tabla(s) en TABLAS_ANULABLES que ya no son descendientes de "
            f"ninguna raíz de QC: {sobrantes}")

    def test_excepciones_no_tienen_create_table_ni_ruta_de_ui(self, bd_temporal):
        """La única abertura declarada (posicionamiento_reposicionamiento)
        no tiene CREATE TABLE -- una BD nueva ni siquiera la crea, así que
        eliminarRegistro jamás podría recibir ese nombre desde una fila
        real de la interfaz."""
        excepciones = excepciones_inventario()
        assert set(excepciones) <= {
            "equipos_anual", "posicionamiento_reposicionamiento"
        }, ("EXCEPCIONES_INVENTARIO cambió -- revisa si la nueva excepción "
            "sigue siendo inalcanzable para eliminarRegistro")
        con = sqlite3.connect(bd_temporal)
        try:
            existe = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='posicionamiento_reposicionamiento'").fetchone()
        finally:
            con.close()
        assert existe is None, (
            "si esta tabla empezó a crearse en BD nuevas, la premisa de "
            "'inalcanzable en la práctica' hay que revisarla")


class TestRamaDeleteInalcanzableEnLaPractica:
    """Ejercita eliminarRegistro sobre una muestra representativa --
    incluida una tabla del grupo MI1 (antes PENDIENTE-LF) -- y confirma
    que la fila sobrevive anulada, nunca desaparece."""

    def test_tabla_clasica_control_cunas_sobrevive_anulada(self, app, bd_temporal, monkeypatch):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO control_cunas (id, ref, angulo) VALUES (501, 1, '90')")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(501)
        eliminarRegistro(_DlgFalso(), tabla, "control_cunas")

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT activo FROM control_cunas WHERE id = 501").fetchone()
        con.close()
        assert fila is not None, "la fila no debe desaparecer -- TABLAS_ANULABLES la cubre"
        assert fila[0] == 0

    def test_tabla_mi1_hc_fantomas_sobrevive_anulada(self, app, bd_temporal, monkeypatch):
        """MI1 (§6-MI1, DA-40): `HC_fantomas` era una de las 30 tablas
        PENDIENTE-LF hasta que MI1 las movió a `TABLAS_ANULABLES` de una
        vez. Es la muestra que demuestra que EB3 cubre también las tablas
        nuevas del inventario, no solo las clásicas de antes de MI1."""
        con = sqlite3.connect(bd_temporal)
        con.execute("INSERT INTO HC_fantomas (id, modelo1, serie1) VALUES (502, 'X', 'Y')")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(502)
        eliminarRegistro(_DlgFalso(), tabla, "HC_fantomas")

        con = sqlite3.connect(bd_temporal)
        fila = con.execute("SELECT activo FROM HC_fantomas WHERE id = 502").fetchone()
        con.close()
        assert fila is not None, (
            "HC_fantomas: la fila no debe desaparecer -- MI1 la puso en "
            "TABLAS_ANULABLES precisamente para esto")
        assert fila[0] == 0
