"""X1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): `create_control`
(mensual, `load.py`) guardaba el centinela de texto `" ---- "` en
`controles.user_id_f2` cuando no había 2º físico -- esa columna tiene
FOREIGN KEY a `users(fullname)`, así que el centinela viola la integridad
referencial (7 filas así en producción, confirmadas con
`PRAGMA foreign_key_check`) y bloquearía activar `PRAGMA foreign_keys=ON`
(W2): con FK ON, INSERTar ese centinela habría fallado con
`FOREIGN KEY constraint failed` -- justo el caso común (control de un solo
físico). Ahora se guarda NULL, que todo lector existente ya trata igual
(`if user_id_f2:`/`if resultado[1]:`).

La copia anual (`seiscientos_anual.py`, heredada por iX/Halcyon) tenía
además un bug real: `_nombre_fisico2` solo se asignaba DENTRO del
`if user_id_f2:` -- sin 2º físico (el caso común) nunca se inicializaba,
así que armar `lista` más abajo revienta con `UnboundLocalError`. Se
corrige junto con el centinela porque es la misma causa (falta de un valor
por defecto para "sin 2º físico").
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import create_control
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600


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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _SelfMensualFalso:
    pass


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _SelfAnualFalso:
    user_id = _UsuarioFalso()


class TestCreateControlMensualGuardaNullSinCentinela:

    def test_sin_segundo_fisico_guarda_null(self, app, bd_temporal):
        ref = create_control(_SelfMensualFalso(), "Clinac iX", "01/07/2026", "Físico de Prueba")

        con = conection_mod.Conexion().con
        fila = con.execute(
            "SELECT user_id_f2 FROM controles WHERE id = ?", (ref,)).fetchone()
        assert fila[0] is None
        assert fila[0] != " ---- "

    def test_reabrir_sin_segundo_fisico_sigue_guardando_null(self, app, bd_temporal):
        """El UPDATE del camino 'ya existe' (create_control, rama
        control_id_existente) también debe guardar NULL, no el centinela."""
        ref1 = create_control(_SelfMensualFalso(), "Clinac 600", "01/07/2026", "Físico de Prueba")
        ref2 = create_control(_SelfMensualFalso(), "Clinac 600", "15/07/2026", "Físico de Prueba")

        assert ref1 == ref2
        con = conection_mod.Conexion().con
        fila = con.execute(
            "SELECT user_id_f2 FROM controles WHERE id = ?", (ref1,)).fetchone()
        assert fila[0] is None


class TestCreateControlAnualNoRevientaSinSegundoFisico:

    def test_sin_segundo_fisico_no_lanza_unboundlocalerror(self, app, bd_temporal):
        """Bug real encontrado durante X1: sin esta corrección, esta llamada
        lanzaba UnboundLocalError en 'lista = [..., _nombre_fisico2]' --
        _nombre_fisico2 nunca se inicializaba fuera del 'if user_id_f2:'."""
        ref = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac iX", "01/2026", "Físico de Prueba")

        assert ref is not None
        con = conection_mod.Conexion().con
        fila = con.execute(
            "SELECT user_id_f2 FROM controles WHERE id = ?", (ref,)).fetchone()
        assert fila[0] is None
