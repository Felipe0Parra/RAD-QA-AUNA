"""N1 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): `create_control`
deja de devolver un control ANULADO en silencio.

Causa raíz: la consulta de "¿ya existe un control este mes?" no filtraba
`activo` -- un control ANULADO se devolvía igual que uno activo, y como
"Subir" ya bloquea sobre un control anulado (W1), el mes quedaba
inutilizable sin que nadie lo explicara (el físico tuvo que crear el
siguiente control en el mes SIGUIENTE, 2026-08-05).

Ahora se clasifica en dos candidatos independientes del mismo mes: el
activo (comportamiento de siempre, sin cambios) y el anulado (se ofrece
reactivar vía `_ofrecer_reactivar_control`, N2).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import create_control


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


def _self_falso():
    return QWidget()


def _anular(ruta_bd, control_id):
    con = sqlite3.connect(ruta_bd)
    con.execute("UPDATE controles SET activo = 0 WHERE id = ?", (control_id,))
    con.commit()
    con.close()


def _activo_de(ruta_bd, id_):
    con = sqlite3.connect(ruta_bd)
    fila = con.execute("SELECT activo FROM controles WHERE id = ?", (id_,)).fetchone()
    con.close()
    return fila[0] if fila else None


class TestCreateControlIgnoraAnulados:

    def test_control_activo_del_mes_no_ofrece_reactivar(self, app, bd_temporal, monkeypatch):
        """Anti-regresión: con un control ACTIVO del mes, ni siquiera debe
        llamarse a _ofrecer_reactivar_control -- es el 100% del camino
        normal (F4) y no debe moverse."""
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Clinac iX", "05/08/2026", "Físico de Prueba")

        def reventar(*a, **k):
            raise AssertionError("no debía ofrecer reactivar -- ya hay un control activo")
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", reventar)

        id_2 = create_control(_self_falso(), "Clinac iX", "20/08/2026", "Físico de Prueba")

        assert id_1 == id_2

    def test_solo_anulado_ofrece_reactivar(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Clinac 600", "05/08/2026", "Físico de Prueba")
        _anular(bd_temporal, id_1)

        llamado = []
        monkeypatch.setattr(
            load_mod, "_ofrecer_reactivar_control",
            lambda self, cid: llamado.append(cid) or False)

        create_control(_self_falso(), "Clinac 600", "20/08/2026", "Físico de Prueba")

        assert llamado == [id_1]

    def test_reactiva_y_devuelve_ese_id_ya_activo(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Halcyon", "05/08/2026", "Físico de Prueba")
        _anular(bd_temporal, id_1)

        def reactivar_de_verdad(self, control_id):
            _con = sqlite3.connect(bd_temporal)
            _con.execute("UPDATE controles SET activo = 1 WHERE id = ?", (control_id,))
            _con.commit()
            _con.close()
            return True
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", reactivar_de_verdad)

        id_2 = create_control(_self_falso(), "Halcyon", "20/08/2026", "Físico de Prueba")

        assert id_2 == id_1
        assert _activo_de(bd_temporal, id_1) == 1

    def test_declina_y_devuelve_el_id_anulado(self, app, bd_temporal, monkeypatch):
        """Fallback seguro: NUNCA None -- puede_editarse() sigue bloqueando
        sobre ese id (incidente H-A si se dejara pasar sin ancla)."""
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Clinac iX", "05/08/2026", "Físico de Prueba")
        _anular(bd_temporal, id_1)
        monkeypatch.setattr(load_mod, "_ofrecer_reactivar_control", lambda self, cid: False)

        id_2 = create_control(_self_falso(), "Clinac iX", "20/08/2026", "Físico de Prueba")

        assert id_2 == id_1
        assert _activo_de(bd_temporal, id_1) == 0  # sigue anulado

    def test_ningun_control_del_mes_crea_uno_nuevo(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))

        id_1 = create_control(_self_falso(), "Clinac 600", "05/08/2026", "Físico de Prueba")

        assert id_1 is not None
        assert _activo_de(bd_temporal, id_1) == 1
