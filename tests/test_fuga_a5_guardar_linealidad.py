"""A5 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `braquiterapia.py::
Linealidad.guardar_linealidad` cerraba la conexión EXPLÍCITAMENTE tras el
`commit()` -- pero el `except:` (desnudo, deuda de otro plan, no se toca
aquí) que envuelve TODA la función hace `return` sin cerrar nada si algo
revienta ANTES de ese `close()` explícito -- p. ej. el propio
`cursor.execute(INSERT...)`.

El `with` se acota SOLO a la parte que necesita `conn` (de `cursor =
conn.cursor()` a `conn.commit()`); el resto de la función (auditoría,
diálogo, refresco de tabla) no usa `conn` y queda fuera, sin tocar su
indentación -- P3 permite acotar el `with` a lo que de verdad hace falta,
no reordena ni mueve nada.

P2: `extraer_datos_medidas` (ya inyectable en el fixture existente,
`_linealidad_pelada`) devuelve un valor NO bindeable en una de las 10
filas de linealidad -- el fallo real ocurre en `cursor.execute`, dentro
del `with`."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QLineEdit, QTableWidget, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad


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
    monkeypatch.setattr(braq_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(braq_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(braq_mod, "mostrar_db_linealidad", lambda *a, **k: None)


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


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


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA5GuardarLinealidadCierraSiempre:
    def test_insert_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _linealidad_pelada()
        # tp[0] llega como una lista -- tipo que sqlite3 no puede
        # bindear -- así que el INSERT revienta dentro del with. El
        # `except:` desnudo de la función lo traga (return sin más).
        obj.extraer_datos_medidas = lambda: (
            [["no bindable"], 2], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0])

        resultado = obj.guardar_linealidad()

        assert resultado is None
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el INSERT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        obj = _linealidad_pelada()
        obj.guardar_linealidad()

        con_verificacion = Conexion().conectar()
        n = con_verificacion.execute(
            "SELECT COUNT(*) FROM LinealidadBraquiterapia").fetchone()[0]
        con_verificacion.close()
        assert n == 1
