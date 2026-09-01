"""LR5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR5, BRQ-1): el bloque de
recarga en `PosicionamientoInicial.actualizar_ref_bd` (`braquiterapia.py`)
era alcanzable de verdad -- no código muerto.

Averiguado reproduciendo el crash EN VIVO (no solo por `hasattr`/MRO):
instanciando `PosicionamientoInicial` real, con un `TipoCalibracion` real,
y cambiando `self.date_box` como lo haría el físico, el `dateChanged`
conectado a `actualizar_ref_bd` (`initUI`/`button_click`) llega hasta
`self.addsomething(...)` y lanza `AttributeError` -- confirmado con el
traceback completo antes de tocar nada.

No era un crash duro: PyQt5 atrapa por defecto la excepción de un slot
conectado a una señal, imprime el traceback (a una consola que el físico
nunca ve en el `.exe`) y la app sigue -- la recarga simplemente no ocurría,
en silencio, cada vez que se cambiaba la fecha.

Investigado a fondo (initUI/button_click) antes de decidir: `self.category1`
en esta clase es el cargador de imágenes de "ANALIZAR IMÁGENES", no una
pestaña de datos de calibración -- no existen `category2/3/6`. La rama
"sin ref_bd" tampoco funcionaba: `limpiar_todos_los_campos` tampoco está
definida aquí. El bloque completo (las DOS ramas) es un resto de copiar
`PruebaMensualBraq.actualizar_ref_bd` (braq_mensual.py) que nunca aplicó a
esta pantalla -- el diario de posicionamiento no tiene campos de tipo/
sistema/condiciones que recargar por fecha; su tabla de calibraciones
(`self.table`) la refresca `mostrar_db_mensualBraqui` por separado, nunca
atada a la fecha elegida. Retirado con el físico confirmando la decisión.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PosicionamientoInicial


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    # C1 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase C, R5): tipo ahora debe
    # ser 'Cambio de fuente' -- actualizar_ref_bd filtra por ese tipo desde
    # C1, y este test verifica el camino de "sí hay calibración", no la
    # lógica de tipo (que cubre tests/test_c1_lectura_por_clave_completa.py).
    conexion.con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, certificado, "
        "fecha_cer, intensidad, conversion, activo) VALUES "
        "(5, 'fisico', '2026-03-15 10:00:00', 'Cambio de fuente', 'SN1', 1.0, "
        "'01/01/2025', 1.0, 1.0, 1)")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class TestBrq1ActualizarRefBdNoCrashea:

    def test_no_tiene_addsomething_ni_limpiar_todos_los_campos(self, app, bd_temporal):
        """La premisa exacta del hallazgo: ninguna de las dos ramas del
        bloque retirado tenía a dónde ir."""
        obj = PosicionamientoInicial(_UsuarioFalso())
        assert not hasattr(obj, "addsomething")
        assert not hasattr(obj, "limpiar_todos_los_campos")

    def test_cambiar_fecha_con_calibracion_real_actualiza_ref_bd_sin_crash(
            self, app, bd_temporal):
        """El camino exacto que reproducía el crash: dateChanged -- ya
        conectado a actualizar_ref_bd desde button_click -- con una
        TipoCalibracion real para esa fecha."""
        obj = PosicionamientoInicial(_UsuarioFalso())

        obj.date_box.setDate(QDate(2026, 3, 15))

        assert obj.ref_bd == 5

    def test_cambiar_a_fecha_sin_calibracion_tambien_actualiza_sin_crash(
            self, app, bd_temporal):
        """La otra rama rota (`limpiar_todos_los_campos`, tampoco
        definida): sin TipoCalibracion para la fecha, ref_bd vuelve a
        None sin lanzar nada."""
        obj = PosicionamientoInicial(_UsuarioFalso())
        obj.date_box.setDate(QDate(2026, 3, 15))
        assert obj.ref_bd == 5

        obj.date_box.setDate(QDate(2020, 1, 1))

        assert obj.ref_bd is None
