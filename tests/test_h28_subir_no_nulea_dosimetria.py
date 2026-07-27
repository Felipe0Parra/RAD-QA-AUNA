"""H2.8 (auditoría 2026-07-16) -- "Subir" ya no puede anular (poner en NULL)
datos de dosimetría que otro panel ya guardó.

Causa: el panel "MLCS" de Halcyon solo tiene un widget suelto
(`ln_action_tolerance`, "Tolerancia de acción") que nunca tuvo el análisis
real de Picket Fence (a diferencia del iX, que sí lo tiene completo). Ese
widget se conectaba a `addsomething(self.category5, df, "mlcs",
"dosimetriaMen", 0, ref=self.ref)` -- tratado como un campo más de
dosimetría. Como "action_tolerance" no es ninguna columna real de
dosimetriaMen, `subirlineasmensuales` hacía un UPDATE de TODAS las columnas
del esquema, poniendo en None cualquiera sin widget correspondiente: pulsar
"Subir" en la pestaña MLCS borraba silenciosamente la dosimetría del mes ya
guardada (dosis, calidad, simetría, planicidad...).

Alcance decidido con el físico (2026-07-16, sin construir el Picket Fence
real de Halcyon todavía -- eso queda como tarea aparte, ver PLAN_FASE_H
H2.9): (1) fix general en ambas rutas de guardado (`subirlineasmensuales` y
`subirlineasmensuales_ix`) -- el UPDATE solo toca columnas con un widget
presente en ESE guardado; (2) se desconectó `ln_action_tolerance` del
guardado en Halcyon (ya no pasa por `addsomething`/dosimetriaMen).

Convenciones: mismo patrón de BD temporal + objetos "pelados" que
test_h27_bd_unica_mensual.py.
"""
import os
import sqlite3
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import subirlineasmensuales
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
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: None))


def _crear_control_activo(ruta_bd, control_id):
    """W1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): subirlineasmensuales/_ix
    ahora exige que el control exista y esté activo. Se ancla la auditoría
    de creación a AHORA para que la ventana de edición de F4b (2 meses)
    quede siempre abierta, sin importar cuándo corra la suite."""
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, 'Clinac ix', 'Mensual', '01/2026', 'Físico de Prueba')",
        (control_id,))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


def _insertar_fila_completa(ruta_bd, ref, energia="6mv"):
    valores = {
        "val_teo_dosis": 1.05, "val_teo_calidad": 0.665,
        "dosis_ref_cgy_um": 0.993, "discrepancia_dosis": 0.7,
        "tolerancia_dosis": 2.5, "calidad_pdd20_10": 0.6676,
        "discrepancia_calidad": 0.391, "tolerancia_calidad": 2.1,
        "simetria_inplane": 0.87, "simetria_crossplane": 1.14,
        "tolerancia_simetria": 2.2, "planicidad_inplane": 2.43,
        "planicidad_crossplane": 2.45, "tolerancia_planicidad": 3.5,
        "observaciones_dosi": "dosimetria del mes, ya guardada",
    }
    con = sqlite3.connect(ruta_bd)
    cols = ", ".join(["ref"] + list(valores) + ["energia"])
    marcas = ", ".join("?" * (len(valores) + 2))
    con.execute(f"INSERT INTO dosimetriaMen ({cols}) VALUES ({marcas})",
                [ref] + list(valores.values()) + [energia])
    con.commit()
    con.close()
    return valores


def _pelado_600():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    return obj


def _pelado_ix():
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    return obj


class TestSubirNoNuleaColumnasAusentes:
    """El caso concreto de Halcyon: un guardado con UN SOLO widget ajeno a
    la tabla (como ln_action_tolerance, que no mapea a ninguna columna real)
    no debe tocar la fila existente."""

    def test_guardado_con_campo_huerfano_no_toca_fila_existente(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 111)
        valores_originales = _insertar_fila_completa(bd_temporal, ref=111)

        obj = _pelado_600()
        obj.ln_action_tolerance = QLineEdit("0.25")  # el widget huérfano de Halcyon
        obj.df_lines = ["ln_action_tolerance"]

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=111, usarid=False)

        con = sqlite3.connect(bd_temporal)
        fila = dict(zip(
            [d[1] for d in con.execute("PRAGMA table_info(dosimetriaMen)")],
            con.execute("SELECT * FROM dosimetriaMen WHERE ref=111").fetchone()))
        con.close()
        for columna, valor_esperado in valores_originales.items():
            assert fila[columna] == valor_esperado, (
                f"{columna} cambió de {valor_esperado} a {fila[columna]} -- "
                "un guardado sin columnas reales no debe tocar la fila")

    def test_guardado_parcial_real_solo_actualiza_lo_presente(self, app, bd_temporal, monkeypatch):
        """Contraste: un guardado con ALGUNOS campos reales (p.ej. solo
        observaciones) SÍ debe actualizar esos campos -- el fix no vuelve
        "Subir" un no-op general, solo protege columnas sin widget."""
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 112)
        valores_originales = _insertar_fila_completa(bd_temporal, ref=112)

        obj = _pelado_600()
        obj.ln_observaciones_dosi = QLineEdit("observación nueva")
        obj.df_lines = ["ln_observaciones_dosi"]

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=112, usarid=False)

        con = sqlite3.connect(bd_temporal)
        fila = dict(zip(
            [d[1] for d in con.execute("PRAGMA table_info(dosimetriaMen)")],
            con.execute("SELECT * FROM dosimetriaMen WHERE ref=112").fetchone()))
        con.close()
        assert fila["observaciones_dosi"] == "observación nueva"
        for columna, valor_esperado in valores_originales.items():
            if columna == "observaciones_dosi":
                continue
            assert fila[columna] == valor_esperado, (
                f"{columna} no debía cambiar (no tenía widget en este guardado)")


class TestSubirIxNoNuleaColumnasAusentes:
    """Mismo fix, ruta del iX (subirlineasmensuales_ix, por energía)."""

    def test_guardado_sin_widgets_no_toca_energia_existente(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 222)
        valores_originales = _insertar_fila_completa(bd_temporal, ref=222, energia="6mv")

        obj = _pelado_ix()
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=222, usarid=True, df_lines=[])

        con = sqlite3.connect(bd_temporal)
        fila = dict(zip(
            [d[1] for d in con.execute("PRAGMA table_info(dosimetriaMen)")],
            con.execute(
                "SELECT * FROM dosimetriaMen WHERE ref=222 AND energia='6mv'").fetchone()))
        con.close()
        for columna, valor_esperado in valores_originales.items():
            assert fila[columna] == valor_esperado


class TestHalcyonMlcsDesconectadoDeDosimetria:
    """Tripwire estructural: la pestaña MLCS de Halcyon ya NO debe conectar
    su widget a addsomething/dosimetriaMen (ver halcyon_mensual.py,
    _crear_tablas_aspectos_dosimetricos) -- si alguien lo reconecta sin
    querer, que truene aquí en vez de en producción."""

    def test_codigo_fuente_no_llama_addsomething_con_mlcs(self):
        import inspect
        from ui.paginasControles.PruebasMensuales import halcyon_mensual
        codigo = inspect.getsource(
            halcyon_mensual.PruebaMensualHc._crear_tablas_aspectos_dosimetricos)
        llamadas_addsomething = codigo.count("self.addsomething(")
        assert llamadas_addsomething == 1, (
            "la pestaña MLCS de Halcyon no debe volver a pasar por "
            "addsomething/dosimetriaMen sin una tabla propia (H2.8) -- "
            f"se esperaba 1 sola llamada (dosimetria), hay {llamadas_addsomething}")
