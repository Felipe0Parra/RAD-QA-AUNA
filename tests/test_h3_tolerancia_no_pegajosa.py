"""H3 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): `tolerancia()`
(`braquiterapia.py:825`) tenía DOS defectos encadenados.

H3a -- el estilo se queda pegado: si `line_1_exp_act_ci` o `line_1_rep_act_ci`
estaban vacíos, `float(...)` lanzaba `ValueError`, el `except` general se
limitaba a un `print` y DEJABA EL ESTILO COMO ESTABA. [medido] en el log del
físico: "could not convert string to float: ''".

H3b -- se evaluaba contra el "esperado" del día anterior: el cargador
(`cargar_dailytest_desde_db`) escribe `line_1_rep_act_ci` (dispara
`tolerancia()` por su única conexión) ANTES que `line_1_exp_act_ci` (sin
ninguna conexión) -- el veredicto que quedaba en pantalla comparaba el `rep`
del día nuevo contra el `exp` del día ANTERIOR.

Se corrigieron las dos mitades juntas a propósito: arreglar solo H3a sin H3b
habría dejado el widget PEOR -- con `_limpiar_widgets_diaria` (H2) limpiando
`rep` antes que el cargador reponga `exp`, el rojo dejaría de aparecer
SIEMPRE, ni siquiera en un día genuinamente fuera de tolerancia.

Trampa 2: `QMessageBox` mockeado antes de construir la pantalla.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"
ROJO = "QLineEdit { background-color: #ffcccc; border: 1px solid red; }"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


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
    conexion.con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
        "certificado, fecha_cer, intensidad, conversion, activo) "
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, 10.0, "
        "1.0, 1)",
        (FECHA_FUENTE, FECHA_FUENTE))
    # DIA_A (03-10): esperado alto (100) -- cualquier `rep` normal quedará
    # MUY fuera de tolerancia si se compara contra este `exp`.
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, activo) VALUES "
        "('2026-03-10', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "100.0,100.0,1.0,1.0, '', 1)")
    # DIA_B (03-11): esperado bajo (10.0) y `rep` = 10.05 -- DENTRO de
    # tolerancia (0.5 %) si se compara contra SU PROPIO esperado; muy FUERA
    # si (H3b) se comparara contra el esperado de DIA_A (100).
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, activo) VALUES "
        "('2026-03-11', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "10.05,10.0,1.0,1.0, '', 1)")
    # DIA_C (03-12): mismo exp que B (10.0) pero rep MUY fuera de tolerancia
    # (50.0) -- para la prueba de H3b sembrada por adelantado (insertar una
    # fila nueva DESPUÉS de que la pantalla ya abrió su propia conexión
    # QSqlDatabase no es visible para esa conexión: mismo patrón que ya usan
    # el resto de tests de este módulo).
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, activo) VALUES "
        "('2026-03-12', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "50.0,10.0,1.0,1.0, '', 1)")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class TestH3aElEstiloNoQuedaPegado:
    """4 saltos (fuera de tolerancia -> vacío -> dentro -> vacío), en los
    dos sentidos: tanto rojo->vacío como normal->vacío deben limpiar."""

    def test_los_cuatro_saltos(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.line_1_exp_act_ci.setText("10.0")

        d.line_1_rep_act_ci.setText("50.0")  # muy fuera de tolerancia
        assert d.line_1_rep_act_ci.styleSheet() == ROJO

        d.line_1_rep_act_ci.setText("")      # vacío tras estar rojo
        assert d.line_1_rep_act_ci.styleSheet() == "", (
            "H3a: un campo vacío no puede dejar el estilo rojo de un "
            "cálculo anterior")

        d.line_1_rep_act_ci.setText("10.05")  # dentro de tolerancia
        assert d.line_1_rep_act_ci.styleSheet() == ""

        d.line_1_rep_act_ci.setText("")       # vacío tras estar normal
        assert d.line_1_rep_act_ci.styleSheet() == "", (
            "H3a: también debe limpiarse llegando desde un estado SIN rojo")

    def test_exp_vacio_tambien_limpia_el_estilo(self, app, bd_temporal):
        """El `except` cubre CUALQUIER campo faltante, no solo `rep`."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.line_1_exp_act_ci.setText("10.0")
        d.line_1_rep_act_ci.setText("50.0")
        assert d.line_1_rep_act_ci.styleSheet() == ROJO

        d.line_1_exp_act_ci.setText("")
        d.tolerancia()

        assert d.line_1_rep_act_ci.styleSheet() == ""


class TestH3bNoSeEvaluaContraElDiaAnterior:
    def test_dia_fuera_de_tolerancia_sale_rojo_pese_a_venir_de_otro_exp(
            self, app, bd_temporal):
        """El caso que el plan midió roto: se llega a DIA_A (rep=100 vs
        exp=100, dentro de tolerancia) primero, y LUEGO a un día que -contra
        SU PROPIO esperado- está fuera de tolerancia debería salir rojo
        de todas formas."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 3, 10))
        assert d.line_1_rep_act_ci.styleSheet() == "", (
            "precondición: DIA_A está dentro de tolerancia (100 vs 100)")

        d.date_box.setDate(QDate(2026, 3, 12))  # DIA_C: rep=50 vs exp=10

        assert d.line_1_rep_act_ci.styleSheet() == ROJO, (
            "H3b: rep=50 vs exp=10 (400% de desviación) debe salir rojo -- "
            "si el veredicto se calculó contra el exp del día anterior "
            "(100), habría salido dentro de tolerancia por error")

    def test_dia_dentro_de_tolerancia_no_sale_rojo_viniendo_de_otro_exp(
            self, app, bd_temporal):
        """La otra mitad: DIA_B está DENTRO de su propia tolerancia
        (10.05 vs 10.0), pero MUY fuera si se comparara contra el `exp` de
        DIA_A (100) -- [medido] sin H3b esto salía rojo por error."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 3, 10))

        d.date_box.setDate(QDate(2026, 3, 11))

        assert d.line_1_rep_act_ci.styleSheet() == "", (
            "DIA_B (10.05 vs su propio 10.0) está dentro de tolerancia -- "
            "no debe salir rojo por comparación contra el exp del día "
            "anterior (100)")
