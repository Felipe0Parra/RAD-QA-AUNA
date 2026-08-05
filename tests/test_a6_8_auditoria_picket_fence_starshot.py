"""A6.8 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): Picket Fence / Starshot
dejan rastro en `audit_log`. De las 8 funciones de
`services/MLCs_calibration_service.py`, ninguna auditaba ni en detalle ni
en el padre.

Cada análisis (MLC o Starshot) dispara 4 escrituras repartidas en 2
métodos: el que arranca el análisis (`_ejecutar_analisis_mlc`/
`_ejecutar_analisis_starshot`, que llama al primer INSERT directo) y el
que muestra resultados (`_mostrar_resultados_mlc`/
`_mostrar_resultados_starshot`, llamado SOLO desde el primero, que hace
los otros 3 INSERT). La auditoría se pone al FINAL del primer método,
después de que el segundo ya corrió -- 1 fila para las 4 escrituras, no
una por INSERT.

Las funciones de análisis reales (pylinac, generación de DICOM sintético,
dibujo con matplotlib) se aíslan con monkeypatch: lo que prueba A6.8 es el
cableado de auditoría, no el análisis en sí (ya cubierto en otro lado).
"""
import os
import sqlite3
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


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
    def __init__(self, nombre):
        self._nombre = nombre


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


def _mensual_pelado():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso("Físico de Prueba")
    obj.ref = 7
    obj.fecha_control = "08/2026"
    obj.equipo_f = "Clinac 600"
    obj.nombre_fisico1 = "Físico de Prueba"
    obj.nombre_fisico2 = None
    return obj


class _MlcMeasFalso:
    leaf_num = 1
    leaf_center_px = 10
    position = 1.0
    position_mm = [1.0, 1.0]
    error = 0.1
    passed = True
    leaf_width_px = 5
    picket_num = 1


class _PicketFalso:
    dist2cax = 1.0
    orientation = "UP-DOWN"
    mlc_meas = [_MlcMeasFalso(), _MlcMeasFalso()]


class _PfDataFalsa:
    pickets = [_PicketFalso()]


class TestAnalisisMlcAuditaUnaVez:
    def test_las_4_escrituras_pf_dejan_una_sola_fila(self, app, bd_temporal, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        # generate_picketfence genera un DICOM sintético que la función ni
        # siquiera usa después (usa self._dcm_mlc_path) -- se anula para no
        # depender de la velocidad/estabilidad del generador real.
        monkeypatch.setattr(
            "pylinac.core.image_generator.generate_picketfence",
            lambda *a, **k: None)

        llamadas = []
        obj = _mensual_pelado()
        obj.ln_tolerance_mlc = QLineEdit("1.0")
        obj.ln_action_tolerance = QLineEdit("2.0")
        obj._dcm_mlc_path = "no-importa.dcm"
        obj._mlc_analyzer = SimpleNamespace(
            picket_fence=lambda *a, **k: _PfDataFalsa())
        obj._mostrar_resultados_mlc = lambda *a, **k: llamadas.append("mostrar_resultados_mlc")
        monkeypatch.setattr(mensual_mod, "pf_db_insertion",
                            lambda *a, **k: llamadas.append("pf_db_insertion"))

        obj._ejecutar_analisis_mlc()

        # Las 2 escrituras "de verdad" alcanzables desde aquí sí ocurrieron
        # (las otras 3 quedan dentro de _mostrar_resultados_mlc, aislado).
        assert llamadas == ["pf_db_insertion", "mostrar_resultados_mlc"]
        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "picket_fence", "7", "")]


class TestAnalisisStarshotAuditaUnaVez:
    def test_las_4_escrituras_starshot_dejan_una_sola_fila(self, app, bd_temporal, monkeypatch):
        llamadas = []
        obj = _mensual_pelado()
        obj.ln_tolerance_starshot = QLineEdit("1.0")
        obj.ln_sid_starshot = QLineEdit("1000")
        obj._dcm_mlc_path = "no-importa.dcm"
        obj._starshot_analyzer = SimpleNamespace(
            analyze=lambda *a, **k: SimpleNamespace(results_data=lambda: None))

        monkeypatch.setattr(mensual_mod.pydicom, "dcmread", lambda *a, **k: None)
        monkeypatch.setattr(mensual_mod, "procesar_data_starshot", lambda *a, **k: {})
        monkeypatch.setattr(mensual_mod, "analisis_profundo_starshot", lambda *a, **k: {})
        monkeypatch.setattr(mensual_mod, "starshot_insert",
                            lambda *a, **k: llamadas.append("starshot_insert"))
        obj._mostrar_resultados_starshot = lambda *a, **k: llamadas.append("mostrar_resultados_starshot")

        obj._ejecutar_analisis_starshot()

        assert llamadas == ["starshot_insert", "mostrar_resultados_starshot"]
        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "starshot", "7", "")]
