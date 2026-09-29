"""A5 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `braquiterapia.py::
Linealidad.guardar_linealidad` cerraba la conexión EXPLÍCITAMENTE tras el
`commit()` -- pero el `except:` (desnudo, deuda de otro plan, no se toca
aquí) que envuelve TODA la función hace `return` sin cerrar nada si algo
revienta ANTES de ese `close()` explícito -- p. ej. el propio
`cursor.execute(INSERT...)`.

L.3 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, tercera ronda) reemplazó el
`with Conexion().conectar() as conn:` por el mismo patrón de conexión que
`guardar_resultado_CambioFuente` (EB2b): `conn = Conexion().conectar()` +
`try/except Exception: conn.rollback(); raise/finally: conn.close()`. Ya
no hay ningún `with` que envolver, así que la garantía de este archivo ya
no se verifica contando invocaciones de `_ConexionUnaVez.__exit__` (ese
código ya no corre en este camino) sino verificando el efecto real que
`__exit__` perseguía: que una transacción de escritura abandonada no deje
bloqueado a un escritor nuevo (DP-67) y que el INSERT fallido no deje
ninguna fila a medias.

P2: `extraer_datos_medidas` (ya inyectable en el fixture existente,
`_linealidad_pelada`) devuelve un valor NO bindeable en una de las 10
filas de linealidad -- el fallo real ocurre en `cursor.execute`, dentro
del `try` de `reemplazar_bloque`."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QLineEdit, QTableWidget, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
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

    # L.2 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md): `guardar_linealidad`
    # ahora escribe la exactitud/tránsito recalculados en la pantalla.
    obj.exactitud = QLineEdit()
    obj.tiempo_transito = QLineEdit()
    obj.r2 = 0.999
    obj.b = 1.5
    obj.extraer_datos_medidas = lambda: (
        [1, 2], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0])
    obj.tabla_resultados = QTableWidget()
    return obj


class TestA5GuardarLinealidadCierraSiempre:
    def test_insert_revienta_y_no_deja_transaccion_abierta(self, app, bd_temporal):
        obj = _linealidad_pelada()
        # q1[0] llega como una lista -- tipo que sqlite3 no puede
        # bindear -- así que el INSERT revienta dentro del `try` de
        # `reemplazar_bloque`. El `except:` desnudo de la función lo
        # traga (return sin más).
        # L.2 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md): `tp`/`te` tienen
        # que llegar VÁLIDOS -- ahora `guardar_linealidad` los usa para
        # `ajuste_linealidad` ANTES de tocar la BD (para que exactitud y
        # tránsito salgan de lo que se va a guardar); corromper `tp` haría
        # que la función reventara ahí, antes de llegar al INSERT que este
        # test quiere ejercitar. `q1` no lo toca `ajuste_linealidad`, así
        # que sigue siendo el campo correcto para simular el fallo tardío.
        obj.extraer_datos_medidas = lambda: (
            [1, 2], [["no bindable"], 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0])

        resultado = obj.guardar_linealidad()

        assert resultado is None

        # DP-67: una transacción de escritura ABANDONADA congela a
        # cualquier escritor nuevo hasta agotar el busy_timeout real
        # (30 s). Con un timeout corto aquí, un `database is locked`
        # demostraría la fuga; que un escritor nuevo pueda tomar el
        # candado EXCLUSIVO de inmediato prueba que el `finally:
        # conn.close()` (L.3) cerró de verdad, sin depender de contar
        # invocaciones de `_ConexionUnaVez.__exit__` -- ese camino ya no
        # usa ningún `with`.
        con_escritor_nuevo = sqlite3.connect(bd_temporal, timeout=0.5)
        con_escritor_nuevo.execute("BEGIN IMMEDIATE")
        con_escritor_nuevo.commit()
        con_escritor_nuevo.close()

        con_verificacion = Conexion().conectar()
        n = con_verificacion.execute(
            "SELECT COUNT(*) FROM LinealidadBraquiterapia").fetchone()[0]
        con_verificacion.close()
        assert n == 0, "el INSERT fallido no debió dejar ninguna fila a medias"

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        obj = _linealidad_pelada()
        obj.guardar_linealidad()

        con_verificacion = Conexion().conectar()
        n = con_verificacion.execute(
            "SELECT COUNT(*) FROM LinealidadBraquiterapia").fetchone()[0]
        con_verificacion.close()
        assert n == 1
