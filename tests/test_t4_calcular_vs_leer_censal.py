"""T4 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md §Fase 0): "cuándo se
calcula y cuándo se lee", decidido por el físico (28-08): *"debe mostrar
el valor guardado y ya; recalcular es para registros nuevos, sea mover
hora o fecha"*.

Las cuatro filas de la tabla del plan ya se comportaban así antes de este
plan (T4 no cambia código) -- este archivo las fija TODAS JUNTAS, censal,
para que ninguna tarea posterior las mueva por separado sin que se note:

    | momento                                  | qué hace el campo        |
    |-------------------------------------------|---------------------------|
    | al abrir la pantalla                       | calcula                   |
    | día/hora nuevos, SIN registro               | calcula                   |
    | al abrir un día CON registro                | lee el valor guardado     |
    | sin fuente registrada                      | queda vacío               |

Por qué "leer lo guardado" es además lo coherente (nota del plan): con T8
el `date_box` queda en la hora del registro, así que un recálculo daría el
MISMO número -- se prefiere leer porque un control cerrado es un registro:
no puede cambiar en pantalla porque después se corrigiera la fuente."""
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


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _dia_sin_registro():
    """C0.0 (PLAN_FUGA_CONEXIONES_01-09.md §8.7, DP-75): antes un literal
    fijo (`QDate(2026, 9, 1)`) -- bomba de tiempo, detonó el 01-09-2026
    cuando "hoy" alcanzó esa fecha y el recálculo dio el MISMO valor que
    el de construcción (ambos "hoy"). Relativo a la fecha real de la
    corrida; el guardia evita la única colisión conocida con un dato fijo
    del archivo (el registro de `bd_con_fuente` en 2026-07-10)."""
    dia = QDate.currentDate().addDays(30)
    if dia == QDate(2026, 7, 10):
        dia = dia.addDays(1)
    return dia


@pytest.fixture
def bd_con_fuente(monkeypatch, tmp_path):
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
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, activo) VALUES "
        "('2026-07-10 12:00:00', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "6.0,4.9182,10.0,10.0, '', 1)")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def bd_sin_fuente(monkeypatch, tmp_path):
    """Fila 4 de la tabla: la ÚNICA calibración 'Cambio de fuente' es
    posterior a la fecha que se va a pedir -- `WHERE tc.fecha <= ?` no
    encuentra fila. Se registra la fuente en 2026-06-01 (para que la
    pantalla, al construirse con la fecha de "hoy", SÍ calcule algo) y
    luego se pide un día ANTERIOR a esa fuente, donde no hay con qué
    calcular -- distingue "nunca se calculó nada" de "se limpió lo que
    había", que es lo que el mecanismo real hace."""
    ruta = str(tmp_path / "test_sin_fuente.db")
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
        "VALUES (1, 'fisico', '2026-06-01 00:00:00', 'Cambio de fuente', "
        "'SN1', 1.0, '2026-06-01 00:00:00', 10.0, 1.0, 1)")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class TestT4CensoDeLasCuatroFilas:
    def test_fila_1_al_abrir_la_pantalla_calcula(self, app, bd_con_fuente):
        d = PruebaDiariaBraq(_UsuarioFalso())
        assert d.line_1_exp_act_ci.text(), (
            "fila 1: al abrir la pantalla el campo debe llegar ya calculado")

    def test_fila_2_dia_nuevo_sin_registro_calcula(self, app, bd_con_fuente):
        d = PruebaDiariaBraq(_UsuarioFalso())
        valor_inicial = d.line_1_exp_act_ci.text()

        d.date_box.setDate(_dia_sin_registro())  # sin registro para ese día

        assert d.line_1_exp_act_ci.text(), (
            "fila 2: un día nuevo sin registro debe recalcular, no dejar "
            "el campo vacío ni el valor del día anterior")
        assert d.line_1_exp_act_ci.text() != valor_inicial

    def test_fila_2b_hora_nueva_sin_cambiar_de_dia_calcula(self, app, bd_con_fuente):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(_dia_sin_registro())  # día sin registro
        valor_a_una_hora = d.line_1_exp_act_ci.text()

        d.date_box.setTime(QTime(23, 0, 0))  # solo la hora, mismo día

        assert d.line_1_exp_act_ci.text(), "fila 2 (variante hora): debe seguir calculando"
        assert d.line_1_exp_act_ci.text() != valor_a_una_hora, (
            "mover solo la hora en un día sin registro debe recalcular "
            "para el nuevo instante, no repetir el de la hora anterior")

    def test_fila_3_dia_con_registro_lee_el_guardado(self, app, bd_con_fuente):
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.date_box.setDate(QDate(2026, 7, 10))  # tiene registro guardado

        assert d.line_1_exp_act_ci.text() == "4.9182", (
            "fila 3: un día con registro debe mostrar el valor GUARDADO, "
            "no uno recalculado en este instante")

    def test_fila_4_sin_fuente_registrada_queda_vacio(self, app, bd_sin_fuente):
        """Se llama a `actividad_braq_automatica` DIRECTAMENTE (no vía
        `date_box.setDate`) para aislar su propio guardián de "sin fuente"
        del de `_limpiar_widgets_diaria` (A4) -- ambos limpian el campo
        para un día nuevo sin registro, y llamando por el `date_box` no se
        podría distinguir cuál de los dos lo hizo. Un centinela detecta si
        ESTA función, sola, deja de limpiar."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        assert d.line_1_exp_act_ci.text(), (
            "precondición: al construirse (fecha de 'hoy', posterior a la "
            "fuente del 2026-06-01) el campo debe calcular algo")

        d.line_1_exp_act_ci.setText("9.9999")  # centinela
        d.actividad_braq_automatica(fecha=QDate(2020, 1, 1), avisar=False)  # anterior a CUALQUIER fuente

        assert d.line_1_exp_act_ci.text() == "", (
            "fila 4: sin ninguna fuente registrada EN O ANTES de la fecha "
            "pedida, el campo debe quedar vacío -- el centinela no debe "
            "sobrevivir")
