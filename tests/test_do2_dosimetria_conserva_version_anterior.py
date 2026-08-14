"""DO2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-DO2): tripwire permanente de
DO1 -- corregir una dosis de referencia en `dosimetriaMen` conserva la
versión anterior (histórica, `activo=0`), nunca la pisa ni la borra. Es lo
que convierte [[DA-05]] ("corrección con rastro") en algo real para el
registro más consecuente de la app: antes de DO1, corregir un valor mal
transcrito lo destruía sin dejar ningún rastro en ninguna parte
(`audit_log` no guarda valor previo/nuevo, así que la fila superada ERA el
único rastro posible).

Cubre las dos rutas de guardado (`subirlineasmensuales` del 600/iX no
multi-energía en load.py, y `subirlineasmensuales_ix` del iX multi-energía
en ix_mensual.py) y la invariante 3 en ambas.
"""
import os
import sqlite3
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import subirlineasmensuales
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager)
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


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


def _sin_avisos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


def _crear_control_activo(ruta_bd, control_id, equipo="Clinac 600"):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, ?, 'Mensual', '01/2026', 'Físico de Prueba')",
        (control_id, equipo))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _pelado_600():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.val_teo_6mv = QLineEdit()
    obj.ln_dosis_ref_cgy_um_6mv = QLineEdit()
    obj.ln_observaciones_dosi = QLineEdit()
    return obj


def _historico(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT rowid, dosis_ref_cgy_um, activo FROM dosimetriaMen "
        "WHERE ref = ? ORDER BY rowid", (ref,)).fetchall()
    con.close()
    return filas


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT accion, tabla, ref FROM audit_log WHERE tabla = 'dosimetriaMen'"
    ).fetchall()
    con.close()
    return filas


class TestCorreccionDejaRastro600:
    def test_corregir_la_dosis_conserva_la_version_anterior(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 900)

        obj = _pelado_600()
        obj.df_lines = ["ln_dosis_ref_cgy_um_6mv"]
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=900, usarid=False)

        obj2 = _pelado_600()
        obj2.df_lines = ["ln_dosis_ref_cgy_um_6mv"]
        obj2.ln_dosis_ref_cgy_um_6mv.setText("1.050")  # el físico corrige
        subirlineasmensuales(obj2, "dosimetriaMen", 0, ref=900, usarid=False)

        historico = _historico(bd_temporal, 900)
        assert len(historico) == 2, (
            "la corrección debía dejar 2 filas -- la vieja histórica, la "
            f"nueva vigente: {historico}")
        valores_por_activo = {activo: dosis for _, dosis, activo in historico}
        assert valores_por_activo == {0: 0.993, 1: 1.05}, (
            f"el valor viejo (0.993) debía quedar activo=0, el corregido "
            f"(1.05) activo=1: {historico}")

        # DA-05: "corrección con rastro" -- las dos escrituras quedan
        # auditadas (no solo la última).
        assert len(_audit_log(bd_temporal)) == 2

    def test_invariante_3_guardado_vacio_no_anula_la_dosis_vigente(
            self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 901)

        obj = _pelado_600()
        obj.df_lines = ["ln_dosis_ref_cgy_um_6mv"]
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=901, usarid=False)

        # Un guardado posterior que no aporta NINGUNA columna real (p.ej.
        # solo un widget huérfano) no debe anular la dosis ya guardada.
        obj2 = _pelado_600()
        obj2.ln_action_tolerance = QLineEdit("0.25")
        obj2.df_lines = ["ln_action_tolerance"]
        subirlineasmensuales(obj2, "dosimetriaMen", 0, ref=901, usarid=False)

        historico = _historico(bd_temporal, 901)
        assert len(historico) == 1, (
            f"un guardado sin columnas reales no debía tocar la fila: {historico}")
        assert historico[0][1:] == (0.993, 1)


def _pelado_ix(energias=("6mv",)):
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    df_lines = []
    for e in energias:
        for campo in ("ln_dosis_ref_cgy_um", "ln_calidad_pdd20_10"):
            nombre = f"{campo}_{e}"
            setattr(obj, nombre, QLineEdit())
            df_lines.append(nombre)
    obj.ln_observaciones_dosi = QLineEdit()
    df_lines.append("ln_observaciones_dosi")
    return obj, df_lines


class TestCorreccionDejaRastroIX:
    def test_corregir_la_dosis_de_una_energia_conserva_la_version_anterior(
            self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 910, equipo="Clinac ix")

        obj, df_lines = _pelado_ix()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=910, usarid=True, df_lines=df_lines)

        obj2, df_lines2 = _pelado_ix()
        obj2.ln_dosis_ref_cgy_um_6mv.setText("1.050")
        obj2.subirlineasmensuales_ix("dosimetriaMen", 0, ref=910, usarid=True, df_lines=df_lines2)

        con = sqlite3.connect(bd_temporal)
        historico = con.execute(
            "SELECT rowid, dosis_ref_cgy_um, activo FROM dosimetriaMen "
            "WHERE ref = ? AND energia = '6mv' ORDER BY rowid", (910,)).fetchall()
        con.close()

        assert len(historico) == 2
        valores_por_activo = {activo: dosis for _, dosis, activo in historico}
        assert valores_por_activo == {0: 0.993, 1: 1.05}

    def test_invariante_3_energia_no_tocada_no_se_anula(self, app, bd_temporal, monkeypatch):
        """Guardar UNA energía (con datos reales) no debe anular ni tocar
        las demás -- cada una es su propio bloque independiente."""
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 911, equipo="Clinac ix")

        obj, df_lines = _pelado_ix(energias=("6mv", "15mv"))
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        obj.ln_dosis_ref_cgy_um_15mv.setText("1.10")
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=911, usarid=True, df_lines=df_lines)

        # Reguardar solo con datos NUEVOS de 6mv -- 15mv no debe tocarse.
        obj2, df_lines2 = _pelado_ix(energias=("6mv",))
        obj2.ln_dosis_ref_cgy_um_6mv.setText("1.05")
        obj2.subirlineasmensuales_ix("dosimetriaMen", 0, ref=911, usarid=True, df_lines=df_lines2)

        con = sqlite3.connect(bd_temporal)
        fila_15mv = con.execute(
            "SELECT dosis_ref_cgy_um, activo FROM dosimetriaMen "
            "WHERE ref = ? AND energia = '15mv' AND (activo IS NULL OR activo = 1)",
            (911,)).fetchall()
        con.close()

        assert fila_15mv == [(1.1, 1)], (
            f"guardar 6mv no debía tocar la energía 15mv: {fila_15mv}")
