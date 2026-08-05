"""A6.6 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): braquiterapia deja rastro
en `audit_log` -- archivos que no tenían NI UNA sola llamada de auditoría.

- `guardar_resultado_CambioFuente` (data/ManejoDatos/load.py): 11 escrituras
  (TipoCalibracion + 5 tablas hijas) para una sola acción -- 1 fila.
- `PruebaMensualBraq.actualizar_desplazamiento_en_db` (braq_mensual.py).
- `Linealidad.guardar_linealidad` y los dos `eliminar_fila_resultado`
  (`PruebaDiariaBraq`/`PosicionamientoInicial`, ui/paginasControles/
  PruebasDiarias/braquiterapia.py) -- estos dos últimos conectan a
  `resultados.db` (DP-08, tabla fantasma, fuera de alcance de esta tarea):
  se audita igual el punto de escritura, aunque hoy la tabla no exista.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QLineEdit, QTableWidget,
    QTableWidgetItem, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import guardar_resultado_CambioFuente
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import (
    Linealidad, PruebaDiariaBraq, PosicionamientoInicial,
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
    for modulo in (braq_mensual_mod, braq_mod):
        monkeypatch.setattr(modulo.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(modulo.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(modulo.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(modulo.QMessageBox, "question",
                            staticmethod(lambda *a, **k: modulo.QMessageBox.Yes))


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestGuardarResultadoCambioFuenteAuditaUnaVez:
    def test_11_escrituras_dejan_una_sola_fila(self, app, bd_temporal):
        ref = guardar_resultado_CambioFuente(
            "Físico de Prueba", "2026-08-04", "Cambio de fuente",
            "A092535", "HDR12899", "2025-07-28", 1.1, 1.0,
            "HDR1000 Plus", "1825", 464700, "Unidos-E", "2343",
            "T10010", 22.0, 101.325, 50.0, 22.0, 101.325, 50.0,
            ["A", "B"], [1.0, 2.0], [1.1, 2.1], [1.05, 2.05],
            [400, 100], [1e-9, 2e-9], [1e-9, 2e-9], [1e-9, 2e-9], [1.0, 1.0],
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
            "No Aplica", "sin observaciones")

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "TipoCalibracion", str(ref),
             "cambio de fuente (braquiterapia)")]


class TestActualizarDesplazamientoAudita:
    def test_audita_con_ref_bd(self, app, bd_temporal):
        obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioFalso("Físico de Prueba")
        obj.ref = 1
        obj.ref_bd = 5

        obj.actualizar_desplazamiento_en_db("1.2")

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "actualizar", "CondicionesMedicion", "5", "")]


def _linealidad_pelada():
    obj = Linealidad.__new__(Linealidad)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso("Físico de Prueba")
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 8, 4))

    for nombre in ("modelo", "serie_cp", "modelo_elec", "serie_ele"):
        combo = QComboBox()
        combo.addItem("valor")
        setattr(obj, nombre, combo)

    for nombre, valor in (
        ("calibracion", "464700"), ("electrometro", "1.0"),
        ("q_est", "1.0"), ("t_integrado", "60.0"), ("i_est", "0.0166"),
        ("repro", "0.5"),
        ("repro_med1", "1.0"), ("repro_med2", "1.0"), ("repro_med3", "1.0"),
        ("repro_med4", "1.0"), ("repro_med5", "1.0"), ("repro_prom", "1.0"),
    ):
        setattr(obj, nombre, QLineEdit(valor))

    obj.r2 = 0.999
    obj.b = 1.5
    obj.extraer_datos_medidas = lambda: (
        [1, 2], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0])
    obj.tabla_resultados = QTableWidget()
    return obj


class TestGuardarLinealidadAudita:
    def test_audita_con_ref_correcto(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(braq_mod, "mostrar_db_linealidad", lambda *a, **k: None)
        obj = _linealidad_pelada()

        obj.guardar_linealidad()

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        assert filas[0][:3] == ("Físico de Prueba", "guardar", "LinealidadBraquiterapia")


def _tabla_con_fila(id_valor):
    tabla = QTableWidget(1, 1)
    tabla.setItem(0, 0, QTableWidgetItem(str(id_valor)))
    tabla.setCurrentCell(0, 0)
    return tabla


class TestEliminarFilaResultadoAudita:
    """DP-08: `resultados.db` es una tabla fantasma (ruta relativa, nunca
    creada por ninguna migración) -- fuera de alcance aquí. Se audita el
    punto de escritura igual; la tabla se crea a mano en el test para
    poder ejercitar la ruta completa sin depender de ese hueco."""

    def _con_tabla_resultados(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        con = sqlite3.connect("resultados.db")
        con.execute("CREATE TABLE resultados (id INTEGER PRIMARY KEY)")
        con.execute("INSERT INTO resultados (id) VALUES (7)")
        con.commit()
        con.close()

    def test_prueba_diaria_braq_audita_el_borrado(self, app, bd_temporal, monkeypatch, tmp_path):
        self._con_tabla_resultados(monkeypatch, tmp_path)
        obj = PruebaDiariaBraq.__new__(PruebaDiariaBraq)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioFalso("Físico de Prueba")
        obj.resultados_table = _tabla_con_fila(7)
        obj.cargar_y_mostrar_resultados = lambda: None

        obj.eliminar_fila_resultado()

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "eliminar", "resultados", "7", "")]

    def test_posicionamiento_inicial_audita_el_borrado(self, app, bd_temporal, monkeypatch, tmp_path):
        self._con_tabla_resultados(monkeypatch, tmp_path)
        obj = PosicionamientoInicial.__new__(PosicionamientoInicial)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioFalso("Físico de Prueba")
        obj.resultados_table = _tabla_con_fila(7)
        obj.cargar_y_mostrar_resultados = lambda: None

        obj.eliminar_fila_resultado()

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "eliminar", "resultados", "7", "")]
