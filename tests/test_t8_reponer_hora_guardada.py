"""T8 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md §Fase 0): "abrir un control
guardado debe posicionar la HORA guardada".

[medido] el defecto: se guarda un control el 2026-09-10 a las 18:45; al
navegar a otro día y volver, `date_box` mostraba 09:00 -- la hora que tenía
puesta, no la del registro. La pantalla quedaba incoherente consigo misma:
decía que el control era de las 09:00 y mostraba la actividad esperada de
las 18:45.

La búsqueda ya era correcta (`WHERE DATE(date) = ?`, discrimina solo hasta
el día) y no se toca. Lo que faltaba: al encontrar el registro, reponer
FECHA Y HORA desde la columna `date`, con las señales bloqueadas -- si no,
reponer la hora dispara `dateTimeChanged` -> recálculo, que pisaría el
valor guardado (la carrera de DP-56/DP-66).

Compatibilidad: los registros anteriores a H6 (todos los de agosto) tienen
`date` sin hora -- para esos no hay hora que reponer, se deja la que ya
tenía el widget, sin inventar ninguna."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "critical", "warning"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.Yes))


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
    # con hora (posterior a H6)
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, activo) VALUES "
        "('2026-03-10 18:45:00', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "5.4604,5.4604,10.0,10.0, '', 1)")
    # histórico SIN hora (anterior a H6, como los 449 reales)
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, activo) VALUES "
        "('2020-01-01', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "1.0,1.0,1.0,1.0, '', 1)")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class TestT8ReponerHoraAlAbrirUnControlGuardado:
    def test_navegar_afuera_y_volver_repone_fecha_y_hora_exactas(
            self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.date_box.setDate(QDate(2026, 3, 11))  # navega a otro día, sin registro
        valor_exp_otro_dia = d.line_1_exp_act_ci.text()

        d.date_box.setDate(QDate(2026, 3, 10))  # vuelve al día guardado

        assert d.date_box.dateTime().toString("yyyy-MM-dd HH:mm:ss") == "2026-03-10 18:45:00", (
            "el date_box debe reponer la hora GUARDADA, no quedarse en la "
            "que tenía puesta al navegar")
        assert d.line_1_exp_act_ci.text() == "5.4604", (
            "la actividad esperada debe seguir siendo la guardada -- "
            "reponer la hora con las señales bloqueadas no debe disparar "
            "ningún recálculo que la pisara")
        assert valor_exp_otro_dia != "5.4604" or valor_exp_otro_dia == "", (
            "precondición débil: solo para evidenciar que hubo un tránsito "
            "real por un día sin registro entre medio")

    def test_registro_historico_sin_hora_no_inventa_ninguna(
            self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.date_box.setDate(QDate(2026, 3, 5))  # otro día, sin registro
        hora_antes = d.date_box.time()

        d.date_box.setDate(QDate(2020, 1, 1))  # histórico, `date` sin hora

        assert d.date_box.date() == QDate(2020, 1, 1)
        assert d.date_box.time() == hora_antes, (
            "un registro sin hora guardada (anterior a H6) no debe "
            "inventar ninguna -- el widget conserva la hora que ya tenía")
        assert d.line_1_rep_act_ci.text() == "1", (
            "el registro histórico debe seguir cargando sus campos con "
            "normalidad pese a no tener hora")
