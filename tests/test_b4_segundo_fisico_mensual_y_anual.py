"""B4 (PLAN_AUDITORIA_DOS_EJES_21-07.md SS7.2, reducido por decisión del
físico 2026-07-21): diario = 1 físico; mensual y anual = 2 físicos juntos;
nadie más aprueba. Basta con que la BD registre quiénes participaron -- sin
máquina de estados ni tabla `aprobaciones` (descartada). La tarea es
"garantizar que el segundo físico se guarde en mensual y anual
(`controles.user_id_f2`)".

`seiscientos_anual.py::PruebaAnual600.create_control` ya LEE `user_id_f2`
(el reporte anual lo usa, `models/PDF/Anual/reportes_anuales.py`); lo que
faltaba confirmar es si la UI lo ESCRIBE en los dos flujos. Verificado con
estos tests:
  - Mensual (`data/ManejoDatos/load.py::create_control`): SÍ escribe
    user_id_f2 tanto al crear un control nuevo como al reabrir uno existente
    del mismo mes (UPDATE explícito, ver X1).
  - Anual (`seiscientos_anual.py::PruebaAnual600.create_control`): escribía
    user_id_f2 SOLO al crear un control nuevo -- la rama "ya existe control
    para este año" (`old_id is not None`) retornaba el id existente SIN
    ningún UPDATE. Si el físico reabre el control anual del mismo año para
    registrar el 2º físico (el caso real que B4 debía garantizar), ese dato
    nunca llegaba a la BD. Corregido para reflejar el mismo patrón que
    mensual: actualizar user_id/user_id_f2 también al reabrir.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import create_control
import ui.paginasControles.PruebasAnuales.seiscientos_anual as anual_mod
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
        ("fisico1", "x", "Físico Uno", 1, 1, "fisico"))
    cur = conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico2", "x", "Físico Dos", 1, 2, "fisico"))
    conexion.con.commit()
    yield ruta, cur.lastrowid
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(anual_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(anual_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _SelfMensualFalso:
    pass


class _UsuarioFalso:
    _nombre = "Físico Uno"


class _SelfAnualFalso:
    user_id = _UsuarioFalso()


class TestMensualGuardaSegundoFisico:
    def test_crear_control_nuevo_guarda_segundo_fisico(self, app, bd_temporal):
        ruta, id_fisico2 = bd_temporal
        ref = create_control(_SelfMensualFalso(), "Clinac 600", "01/07/2026",
                              "Físico Uno", user_id_f2=id_fisico2)

        con = conection_mod.Conexion().con
        fila = con.execute(
            "SELECT user_id_f2 FROM controles WHERE id = ?", (ref,)).fetchone()
        assert fila[0] == "Físico Dos"

    def test_reabrir_el_mismo_mes_actualiza_segundo_fisico(self, app, bd_temporal):
        """El caso real de B4: el control se crea sin 2º físico y luego se
        reabre (mismo mes) para registrar quién más participó."""
        ruta, id_fisico2 = bd_temporal
        ref1 = create_control(_SelfMensualFalso(), "Clinac iX", "01/07/2026", "Físico Uno")
        ref2 = create_control(_SelfMensualFalso(), "Clinac iX", "15/07/2026",
                               "Físico Uno", user_id_f2=id_fisico2)

        assert ref1 == ref2
        con = conection_mod.Conexion().con
        fila = con.execute(
            "SELECT user_id_f2 FROM controles WHERE id = ?", (ref1,)).fetchone()
        assert fila[0] == "Físico Dos"


class TestAnualGuardaSegundoFisico:
    def test_crear_control_nuevo_guarda_segundo_fisico(self, app, bd_temporal):
        ruta, id_fisico2 = bd_temporal
        ref = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac 600", "01/2026", "Físico Uno",
            user_id_f2=id_fisico2)

        con = conection_mod.Conexion().con
        fila = con.execute(
            "SELECT user_id_f2 FROM controles WHERE id = ?", (ref,)).fetchone()
        assert fila[0] == "Físico Dos"

    def test_reabrir_el_mismo_anio_actualiza_segundo_fisico(self, app, bd_temporal):
        """Mismo caso que en mensual, para el control ANUAL: se crea sin 2º
        físico y se reabre el mismo año para registrar quién más participó.
        Antes de esta tarea, la rama 'ya existe control de este año' no
        actualizaba nada -- el 2º físico nunca quedaba guardado."""
        ruta, id_fisico2 = bd_temporal
        ref1 = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac iX", "03/2026", "Físico Uno")
        ref2 = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac iX", "09/2026", "Físico Uno",
            user_id_f2=id_fisico2)

        assert ref1 == ref2
        con = conection_mod.Conexion().con
        fila = con.execute(
            "SELECT user_id_f2 FROM controles WHERE id = ?", (ref1,)).fetchone()
        assert fila[0] == "Físico Dos"
