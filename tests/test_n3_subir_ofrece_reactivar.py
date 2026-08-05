"""N3 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): el aviso de
"Subir" bloqueado ofrece reactivar ahí mismo cuando el motivo es
"anulado" -- en `subirlineasmensuales` (load.py, 600/Halcyon) y
`subirlineasmensuales_ix` (ix_mensual.py, iX).

Cualquier otro motivo (control inexistente, fuera de la ventana de 2
meses de F4b) mantiene el aviso de siempre, sin ofrecer nada -- ofrecer
reactivar ahí se tragaría el bloqueo de F4b (riesgo ya identificado en el
plan, R5).
"""
import os
import sqlite3
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
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


def _crear_control(ruta_bd, control_id, activo=1, timestamp=None,
                    equipo="Clinac ix", fecha="01/2026"):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id, activo) "
        "VALUES (?, ?, 'Mensual', ?, 'Físico de Prueba', ?)",
        (control_id, equipo, fecha, activo))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


def _activo_de(ruta_bd, control_id):
    con = sqlite3.connect(ruta_bd)
    fila = con.execute("SELECT activo FROM controles WHERE id = ?", (control_id,)).fetchone()
    con.close()
    return fila[0] if fila else None


def _pelado_600():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    return obj


def _pelado_ix():
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    return obj


def _capturar_avisos(monkeypatch):
    avisos = []
    monkeypatch.setattr(load_mod.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: avisos.append(a[1:])))
    monkeypatch.setattr(load_mod.QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    return avisos


class TestSubirOfreceReactivar600:

    def test_anulado_y_acepta_reactivar_guarda(self, app, bd_temporal, monkeypatch):
        avisos = _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 43, activo=0)

        def reactivar_de_verdad(self, control_id):
            con = sqlite3.connect(bd_temporal)
            con.execute("UPDATE controles SET activo = 1 WHERE id = ?", (control_id,))
            con.commit()
            con.close()
            return True
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", reactivar_de_verdad)

        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        obj.ln_observaciones_dosi = QLineEdit("dato legítimo, tras reactivar")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=43, usarid=False)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=43").fetchone()[0]
        con.close()
        assert n == 1, "tras reactivar, el guardado debe continuar normalmente"
        assert avisos == []  # ningún aviso de bloqueo
        assert _activo_de(bd_temporal, 43) == 1

    def test_anulado_y_declina_no_guarda(self, app, bd_temporal, monkeypatch):
        avisos = _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 44, activo=0)
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", lambda self, cid: False)

        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        obj.ln_observaciones_dosi = QLineEdit("no debería guardarse")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=44, usarid=False)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=44").fetchone()[0]
        con.close()
        assert n == 0
        assert len(avisos) == 1
        assert "anulado" in avisos[0][1]
        assert _activo_de(bd_temporal, 44) == 0

    def test_fuera_de_ventana_no_ofrece_reactivar(self, app, bd_temporal, monkeypatch):
        """Anti-regresión de F4b/R5: fuera de la ventana de 2 meses, NO se
        ofrece reactivar aunque el control siga activo -- el bloqueo de F4b
        no se puede sortear por esta vía."""
        avisos = _capturar_avisos(monkeypatch)
        hace_tres_meses = (datetime.now() - timedelta(days=95)).strftime("%Y-%m-%d %H:%M:%S")
        _crear_control(bd_temporal, 45, activo=1, timestamp=hace_tres_meses)

        def reventar(*a, **k):
            raise AssertionError("no debía ofrecerse reactivar -- el control sigue activo, "
                                "el motivo es la ventana de F4b, no la anulación")
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", reventar)

        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        obj.ln_observaciones_dosi = QLineEdit("no debería guardarse")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=45, usarid=False)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=45").fetchone()[0]
        con.close()
        assert n == 0
        assert len(avisos) == 1
        assert "ventana" in avisos[0][1]

    def test_control_normal_no_pregunta_nada(self, app, bd_temporal, monkeypatch):
        avisos = _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 46, activo=1)

        def reventar(*a, **k):
            raise AssertionError("no debía ofrecerse reactivar -- el control está activo y en ventana")
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", reventar)

        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        obj.ln_observaciones_dosi = QLineEdit("dato legítimo")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=46, usarid=False)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=46").fetchone()[0]
        con.close()
        assert n == 1
        assert avisos == []


class TestSubirOfreceReactivarIX:

    def test_anulado_y_acepta_reactivar_guarda(self, app, bd_temporal, monkeypatch):
        avisos = _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 47, activo=0)

        def reactivar_de_verdad(self, control_id):
            con = sqlite3.connect(bd_temporal)
            con.execute("UPDATE controles SET activo = 1 WHERE id = ?", (control_id,))
            con.commit()
            con.close()
            return True
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", reactivar_de_verdad)

        obj = _pelado_ix()
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=47, usarid=True, df_lines=[])

        assert avisos == []
        assert _activo_de(bd_temporal, 47) == 1

    def test_anulado_y_declina_no_reactiva(self, app, bd_temporal, monkeypatch):
        avisos = _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 48, activo=0)
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", lambda self, cid: False)

        obj = _pelado_ix()
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=48, usarid=True, df_lines=[])

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=48").fetchone()[0]
        con.close()
        assert n == 0
        assert len(avisos) == 1
        assert "anulado" in avisos[0][1]
        assert _activo_de(bd_temporal, 48) == 0
