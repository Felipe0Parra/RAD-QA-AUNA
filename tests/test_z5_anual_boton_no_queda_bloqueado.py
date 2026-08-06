"""Z5 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): el botón "Subir" de las
tablas anuales (600/iX, Halcyon anual por herencia) NO debe quedar
deshabilitado para siempre tras el primer guardado.

Causa (§6.3 del plan): `bloquearboton(btn_guardar)` se llamaba al final de
`guardar_todas_fse` en los dos anuales, y nada en esa sesión lo rehabilitaba
-- el físico no podía corregir un dato mal tecleado sin cerrar y reabrir el
formulario. `ix_mensual.py:451` ya tenía la llamada análoga COMENTADA -- la
prueba de que la inconsistencia ya se había detectado sin cerrarse. La
protección real contra un guardado indebido no es el botón: es la ventana de
2 meses (F4b/C1), la verificación de control activo (W1) y la auditoría
(A6.4), las tres ya vigentes en esta misma ruta.

`bloquearboton` en sí NO se toca -- lo sigue usando braquiterapia
(`braquiterapia.py:2984`) con otra semántica.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QHBoxLayout, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasAnuales.seiscientos_anual as anual_mod
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
import ui.paginasControles.PruebasAnuales.ix_anual as ix_anual_mod
from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX


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


def _boton_de(layout):
    """Los botones de _agregar_botones_tabla van dentro de un QHBoxLayout
    anidado (layout.addLayout(button_layout)), no directo -- bajar un nivel
    más que un addWidget simple. Mismo helper que test_a6_4."""
    return layout.itemAt(0).layout().itemAt(0).widget()


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    for modulo in (anual_mod,):
        monkeypatch.setattr(modulo.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(modulo.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


def _anual_pelado(clase):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso("Físico de Prueba")
    obj.anual = True
    return obj


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute("SELECT accion, tabla, ref FROM audit_log").fetchall()
    con.close()
    return filas


class TestSeiscientosAnualBotonNoQuedaBloqueado:
    def test_boton_sigue_habilitado_tras_guardar(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(anual_mod, "loadtablacomplex", lambda *a, **k: None)
        obj = _anual_pelado(PruebaAnual600)
        obj.ref = 7
        layout = QHBoxLayout()
        tabla = object()

        obj._agregar_botones_tabla(layout, tabla, "tabla_fc", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        assert btn.isEnabled() is True


class TestIxAnualBotonNoQuedaBloqueado:
    def test_boton_sigue_habilitado_tras_guardar(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(ix_anual_mod, "loadtablacomplex", lambda *a, **k: None)
        obj = _anual_pelado(PruebaAnualIX)
        obj.ref = 9
        layout = QHBoxLayout()
        tabla = object()

        obj._agregar_botones_tabla(layout, tabla, "tabla_ccm", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        assert btn.isEnabled() is True


class TestGuardarDosVecesEscribeLasDos:
    """Lo que el físico quería poder hacer: corregir un valor mal tecleado
    sin cerrar y reabrir el formulario -- guardar dos veces seguidas debe
    ejecutar loadtablacomplex las dos veces, no solo la primera."""

    def test_dos_clics_seguidos_suben_dos_veces(self, app, bd_temporal, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            anual_mod, "loadtablacomplex",
            lambda *a, **k: llamadas.append(a))
        obj = _anual_pelado(PruebaAnual600)
        obj.ref = 13
        layout = QHBoxLayout()
        tabla = object()

        obj._agregar_botones_tabla(layout, tabla, "tabla_fta", obj.ref)
        btn = _boton_de(layout)

        btn.click()
        assert btn.isEnabled() is True  # sigue habilitado tras el primer click
        btn.click()

        assert len(llamadas) == 2  # las dos escrituras llegaron
        filas = _audit_log(bd_temporal)
        assert len(filas) == 2  # y quedaron auditadas las dos veces
