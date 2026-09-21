"""A.2 (PLAN_REFERENCIAS_EDITABLES_21-09.md): la referencia se guarda
SIEMPRE, no solo cuando alguien la teclea -- la otra mitad del principio de
copia guardada. `A.1` hace que el número se USE; `A.2` hace que quede
ESCRITO, para que un control se pueda volver a juzgar dentro de un año.

[medido] `val_teo_calidad` es NULL en 4/5 filas del 600, 5/7 del iX y 3/4
del Halcyon (§0.3 del plan) -- porque el guardado de hoy solo persiste lo
que el físico tecleó, nunca el respaldo que de verdad se usó para calcular.

Rojo-antes-que-verde real: `git stash` (sin `-u`) sobre
`seiscientos_mensual.py`/`ix_mensual.py` reproduce el NULL de hoy; con el
arreglo, el respaldo queda escrito.
"""
import os
import sqlite3
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
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


def _sin_avisos(monkeypatch):
    """Trampa 2: mockear TODO QMessageBox, incluidos los de éxito."""
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, nombre,
                             staticmethod(lambda *a, **k: None))


def _crear_control_activo(ruta_bd, control_id, equipo="Clinac ix", mes="01/2026"):
    """idx_controles_unico_mes es único por (equipo, mes/año, tipo) -- cada
    ref usado en los tests que compartan equipo va en un mes distinto."""
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, ?, 'Mensual', ?, 'Físico de Prueba')",
        (control_id, equipo, mes))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


def _fila_dosimetria(ruta_bd, ref, energia="6mv"):
    con = sqlite3.connect(ruta_bd)
    cols = [d[1] for d in con.execute("PRAGMA table_info(dosimetriaMen)")]
    fila = con.execute(
        "SELECT * FROM dosimetriaMen WHERE ref=? AND energia=? "
        "AND (activo IS NULL OR activo=1)", (ref, energia)).fetchone()
    con.close()
    return dict(zip(cols, fila)) if fila else None


def _pelado_600():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    return obj


def _pelado_ix():
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    return obj


class TestValTeoCalidadSePersisteSiempre:
    """La copia guardada de val_teo_calidad ya no puede quedar NULL solo
    porque el físico no tecleó nada -- cae al respaldo por energía."""

    def test_600_widget_vacio_guarda_respaldo_no_null(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 201, equipo="Clinac 600")

        obj = _pelado_600()
        obj.val_teo_6mv = QLineEdit("")  # el físico no tecleó nada
        obj.ln_calidad_pdd20_10_6mv = QLineEdit("0.66")
        obj.ln_observaciones_dosi = QLineEdit("")
        df_lines = ["val_teo_6mv", "ln_calidad_pdd20_10_6mv", "ln_observaciones_dosi"]

        obj._subir_optimizado(df_lines, "dosimetriaMen", 0, ref=201, usarid=False)

        fila = _fila_dosimetria(bd_temporal, 201)
        assert fila is not None
        assert fila["val_teo_calidad"] == pytest.approx(0.665)  # respaldo del 600, 6mv

    def test_600_widget_lleno_no_se_pisa(self, app, bd_temporal, monkeypatch):
        """Lo tecleado manda -- el respaldo nunca sobrescribe un valor real."""
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 202, equipo="Clinac 600")

        obj = _pelado_600()
        obj.val_teo_6mv = QLineEdit("0.6667")
        obj.ln_calidad_pdd20_10_6mv = QLineEdit("0.66")
        df_lines = ["val_teo_6mv", "ln_calidad_pdd20_10_6mv"]

        obj._subir_optimizado(df_lines, "dosimetriaMen", 0, ref=202, usarid=False)

        fila = _fila_dosimetria(bd_temporal, 202)
        assert fila["val_teo_calidad"] == pytest.approx(0.6667)

    def test_ix_seis_energias_vacias_guardan_su_propio_respaldo(self, app, bd_temporal, monkeypatch):
        """Cada energía del iX cae a SU respaldo -- no todas al mismo."""
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 203, equipo="Clinac ix")

        obj = _pelado_ix()
        energias_widgets = {
            "6mv": ("ln_calidad_pdd20_10_6mv", "0.66"),
            "15mv": ("ln_calidad_pdd20_10_15mv", "0.75"),
            "6mev": ("ln_calidad_j2_j1_6mev", "0.48"),
            "9mev": ("ln_calidad_j2_j1_9mev", "0.49"),
            "12mev": ("ln_calidad_j2_j1_12mev", "0.60"),
            "15mev": ("ln_calidad_j2_j1_15mev", "0.60"),
        }
        df_lines = []
        for energia, (calidad_attr, calidad_val) in energias_widgets.items():
            setattr(obj, f"val_teo_{energia}", QLineEdit(""))
            setattr(obj, calidad_attr, QLineEdit(calidad_val))
            df_lines.append(f"val_teo_{energia}")
            df_lines.append(calidad_attr)
        obj.ln_observaciones_dosi = QLineEdit("")
        df_lines.append("ln_observaciones_dosi")

        # El camino real del iX es subirlineasmensuales_ix (una fila POR
        # energía), no _subir_optimizado/subirlineasmensuales (single-row,
        # el del 600) -- así lo hace la función subir() de ix_mensual.py.
        obj._persistir_referencia_calidad_si_vacia(df_lines)
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=203, usarid=False, df_lines=df_lines)
        obj._persistir_val_teo_dosis(203)

        esperado = {
            "6mv": 0.665, "15mv": 0.761, "6mev": 0.483,
            "9mev": 0.500, "12mev": 0.606, "15mev": 0.605,
        }
        for energia, valor in esperado.items():
            fila = _fila_dosimetria(bd_temporal, 203, energia=energia)
            assert fila is not None, f"sin fila para {energia}"
            assert fila["val_teo_calidad"] == pytest.approx(valor), energia


class TestValTeoDosisSePersiste:
    """val_teo_dosis no tiene widget (R5) -- se persiste el literal que
    usa hoy el cálculo (1.0), sin inventar nada más ni pisar lo existente."""

    def test_600_guarda_1_0_en_val_teo_dosis(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 204, equipo="Clinac 600")

        obj = _pelado_600()
        obj.ln_dosis_ref_cgy_um_6mv = QLineEdit("0.99")
        df_lines = ["ln_dosis_ref_cgy_um_6mv"]

        obj._subir_optimizado(df_lines, "dosimetriaMen", 0, ref=204, usarid=False)

        fila = _fila_dosimetria(bd_temporal, 204)
        assert fila["val_teo_dosis"] == pytest.approx(1.0)

    def test_no_pisa_un_val_teo_dosis_ya_guardado(self, app, bd_temporal, monkeypatch):
        """Guardar dos veces no debe cambiar un val_teo_dosis histórico
        distinto de 1 (p. ej. 1.0009 del Halcyon, medido en producción)."""
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 205, equipo="Clinac 600")
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO dosimetriaMen (ref, energia, val_teo_dosis) "
            "VALUES (205, '6mv', 1.0009)")
        con.commit()
        con.close()

        obj = _pelado_600()
        obj.ln_observaciones_dosi = QLineEdit("otra observación")
        df_lines = ["ln_observaciones_dosi"]

        obj._subir_optimizado(df_lines, "dosimetriaMen", 0, ref=205, usarid=False)

        fila = _fila_dosimetria(bd_temporal, 205)
        assert fila["val_teo_dosis"] == pytest.approx(1.0009)


class TestRoundTripYNoTocaHistorico:
    def test_guardar_cerrar_reabrir_da_lo_mismo(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 206, equipo="Clinac 600")

        obj = _pelado_600()
        obj.val_teo_6mv = QLineEdit("")
        obj.ln_calidad_pdd20_10_6mv = QLineEdit("0.66")
        df_lines = ["val_teo_6mv", "ln_calidad_pdd20_10_6mv"]
        obj._subir_optimizado(df_lines, "dosimetriaMen", 0, ref=206, usarid=False)

        primera = _fila_dosimetria(bd_temporal, 206)

        # "Reabrir": un objeto nuevo, releer la misma fila.
        segunda = _fila_dosimetria(bd_temporal, 206)
        assert primera == segunda
        assert primera["val_teo_calidad"] == pytest.approx(0.665)
        assert primera["val_teo_dosis"] == pytest.approx(1.0)

    def test_ninguna_fila_historica_ajena_cambia(self, app, bd_temporal, monkeypatch):
        """Censo antes/después: guardar el ref=207 no puede tocar ref=208."""
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 207, equipo="Clinac 600", mes="01/2026")
        _crear_control_activo(bd_temporal, 208, equipo="Clinac 600", mes="02/2026")
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO dosimetriaMen (ref, energia, val_teo_calidad, val_teo_dosis) "
            "VALUES (208, '6mv', 0.627, 1.0009)")
        con.commit()
        con.close()
        fila_208_antes = _fila_dosimetria(bd_temporal, 208)

        obj = _pelado_600()
        obj.val_teo_6mv = QLineEdit("")
        obj.ln_calidad_pdd20_10_6mv = QLineEdit("0.66")
        df_lines = ["val_teo_6mv", "ln_calidad_pdd20_10_6mv"]
        obj._subir_optimizado(df_lines, "dosimetriaMen", 0, ref=207, usarid=False)

        fila_208_despues = _fila_dosimetria(bd_temporal, 208)
        assert fila_208_antes == fila_208_despues
