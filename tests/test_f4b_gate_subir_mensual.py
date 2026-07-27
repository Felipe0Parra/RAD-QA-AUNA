"""F4b (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4, tarea C1): "Subir" en el
mensual respeta la ventana de 2 meses -- alcance de esta tarea: los dos
puntos de escritura de dosimetría/energía (`subirlineasmensuales` en
load.py, usado por 600/Halcyon vía `_subir_optimizado`, y
`subirlineasmensuales_ix` en ix_mensual.py). Los "Subir" de otras
categorías del mensual (aspectos mecánicos, tamaños de campo, MLC, vía
`loadtablacomplex`) NO quedan cubiertos por esta tarea -- residual
documentado, no un olvido silencioso.
"""
import os
import sqlite3
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
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
    obj.df_lines = ["val_teo_6mv", "ln_dosis_ref_cgy_um_6mv", "ln_observaciones_dosi"]
    return obj


def _pelado_ix():
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    obj.val_teo_6mv = QLineEdit()
    obj.ln_dosis_ref_cgy_um_6mv = QLineEdit()
    obj.ln_observaciones_dosi = QLineEdit()
    return obj, ["val_teo_6mv", "ln_dosis_ref_cgy_um_6mv", "ln_observaciones_dosi"]


def _crear_control_con_ancla(ruta_db, timestamp_creacion):
    con = sqlite3.connect(ruta_db)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Clinac iX", "Mensual", "05/07/2026"))
    con.commit()
    control_id = cur.lastrowid
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (timestamp_creacion, str(control_id)))
    con.commit()
    con.close()
    return control_id


def _filas_dosimetria(ruta_db, ref):
    con = sqlite3.connect(ruta_db)
    n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=?", (ref,)).fetchone()[0]
    con.close()
    return n


class TestGateSubirLineasMensuales600:

    def test_fuera_de_ventana_bloquea_y_no_escribe(self, app, bd_temporal, monkeypatch):
        control_id = _crear_control_con_ancla(bd_temporal, "2026-01-05 10:00:00")
        avisos = []
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: avisos.append(a[2] if len(a) > 2 else k.get("text"))))

        obj = _pelado_600()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=control_id, usarid=False)

        assert len(avisos) == 1
        assert "2 meses" in avisos[0]
        assert _filas_dosimetria(bd_temporal, control_id) == 0

    def test_dentro_de_ventana_permite_escribir(self, app, bd_temporal, monkeypatch):
        control_id = _crear_control_con_ancla(bd_temporal, "2026-07-05 10:00:00")
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                 AssertionError("no debía bloquear -- está dentro de la ventana"))))

        obj = _pelado_600()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=control_id, usarid=False)

        assert _filas_dosimetria(bd_temporal, control_id) == 1

    def test_anual_no_se_bloquea(self, app, bd_temporal, monkeypatch):
        """Anual usa su propio create_control (sin ancla de auditoría) --
        el guard no debe aplicar la ventana ahí."""
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                 AssertionError("Anual no debía bloquearse"))))

        obj = _pelado_600()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=999999, usarid=False, anual=True)


class TestGateSubirLineasMensualesIX:

    def test_fuera_de_ventana_bloquea_y_no_escribe(self, app, bd_temporal, monkeypatch):
        control_id = _crear_control_con_ancla(bd_temporal, "2026-01-05 10:00:00")
        avisos = []
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: avisos.append(1)))

        obj, df_lines = _pelado_ix()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=control_id, usarid=True, df_lines=df_lines)

        assert len(avisos) == 1
        assert _filas_dosimetria(bd_temporal, control_id) == 0
