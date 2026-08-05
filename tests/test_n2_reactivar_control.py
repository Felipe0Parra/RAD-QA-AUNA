"""N2 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): reactivar un
control anulado, con guarda de unicidad obligatoria (índice parcial de U2,
`idx_controles_unico_mes`) y auditoría propia (`ACCION_REACTIVAR`).

Origen: el físico anuló un control mensual y `create_control` lo seguía
devolviendo -- con `puede_editarse` bloqueando cualquier "Subir" sobre él
(W1). Decisión del físico: reversible desde la app, con autenticación
PERSONAL (DA-07), no de administrador.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
import ui.paginasGuia.dialogs as dialogs_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import _ofrecer_reactivar_control
from services.reactivacion import reactivar_control


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _crear_control(ruta_bd, equipo="Clinac ix", control="Mensual",
                    fecha="05/08/2026", activo=1):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha, user_id, activo) "
        "VALUES (?, ?, ?, ?, ?)",
        (equipo, control, fecha, "Físico de Prueba", activo))
    con.commit()
    id_ = cur.lastrowid
    con.close()
    return id_


def _activo_de(ruta_bd, id_):
    con = sqlite3.connect(ruta_bd)
    fila = con.execute("SELECT activo FROM controles WHERE id = ?", (id_,)).fetchone()
    con.close()
    return fila[0] if fila else None


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestReactivarControl:
    """La función pura del servicio, sin UI."""

    def test_reactiva_y_audita_con_el_nombre_del_fisico(self, app, bd_temporal):
        id_ = _crear_control(bd_temporal, activo=0)

        ok, motivo = reactivar_control(id_, "Físico de Prueba")

        assert ok is True
        assert motivo is None
        assert _activo_de(bd_temporal, id_) == 1
        assert _audit_log(bd_temporal) == [
            ("Físico de Prueba", "reactivar", "controles", str(id_), "activo: 0→1")]

    def test_guarda_de_unicidad_rechaza_si_ya_hay_otro_activo_del_mismo_mes(
            self, app, bd_temporal):
        id_anulado = _crear_control(bd_temporal, fecha="05/08/2026", activo=0)
        _crear_control(bd_temporal, fecha="20/08/2026", activo=1)  # mismo mes, ACTIVO

        ok, motivo = reactivar_control(id_anulado, "Físico de Prueba")

        assert ok is False
        assert "ya hay un control activo" in motivo
        assert _activo_de(bd_temporal, id_anulado) == 0  # sigue anulado
        assert _audit_log(bd_temporal) == []  # nada escrito

    def test_id_inexistente_no_revienta(self, app, bd_temporal):
        ok, motivo = reactivar_control(9999, "Físico de Prueba")

        assert ok is False
        assert motivo is not None
        assert _audit_log(bd_temporal) == []

    def test_control_ya_activo_es_idempotente(self, app, bd_temporal):
        id_ = _crear_control(bd_temporal, activo=1)

        ok, motivo = reactivar_control(id_, "Físico de Prueba")

        assert ok is True
        assert _audit_log(bd_temporal) == []  # ya estaba activo, nada que auditar

    def test_no_viola_el_indice_unico_de_controles(self, app, bd_temporal):
        """La guarda de unicidad debe rechazar ANTES de que el UPDATE
        llegue a chocar con idx_controles_unico_mes (U2)."""
        con = sqlite3.connect(bd_temporal)
        assert con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_controles_unico_mes'").fetchone() is not None
        con.close()

        id_anulado = _crear_control(bd_temporal, fecha="05/08/2026", activo=0)
        _crear_control(bd_temporal, fecha="20/08/2026", activo=1)

        # No debe lanzar sqlite3.IntegrityError.
        ok, motivo = reactivar_control(id_anulado, "Físico de Prueba")

        assert ok is False
        assert motivo is not None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"
    _usuario = "fisico"


class _SelfFalso:
    def __init__(self):
        self.user_id = _UsuarioFalso()


class _DialogoAdminFalso:
    _resultado = QDialog.DialogCode.Accepted

    def __init__(self, user):
        self.user = user

    def exec(self):
        return self._resultado


class TestOfrecerReactivarControl:
    """El helper de UI: la pregunta + la reautenticación personal."""

    def test_dialogo_denegado_no_reactiva(self, app, bd_temporal, monkeypatch):
        id_ = _crear_control(bd_temporal, activo=0)
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.No))

        resultado = _ofrecer_reactivar_control(_SelfFalso(), id_)

        assert resultado is False
        assert _activo_de(bd_temporal, id_) == 0

    def test_reautenticacion_rechazada_no_reactiva(self, app, bd_temporal, monkeypatch):
        id_ = _crear_control(bd_temporal, activo=0)
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))

        class _DialogoRechazado(_DialogoAdminFalso):
            _resultado = QDialog.DialogCode.Rejected
        monkeypatch.setattr(dialogs_mod, "DialogAdminPermisoEditar", _DialogoRechazado)

        resultado = _ofrecer_reactivar_control(_SelfFalso(), id_)

        assert resultado is False
        assert _activo_de(bd_temporal, id_) == 0

    def test_confirmado_y_reautenticado_reactiva(self, app, bd_temporal, monkeypatch):
        id_ = _crear_control(bd_temporal, activo=0)
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                            staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(dialogs_mod, "DialogAdminPermisoEditar", _DialogoAdminFalso)

        resultado = _ofrecer_reactivar_control(_SelfFalso(), id_)

        assert resultado is True
        assert _activo_de(bd_temporal, id_) == 1
