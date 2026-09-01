"""A3 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase A, R2): "se crea el control
mensual aunque el aviso diga que el Físico 1 no existe" -- reportado
textualmente por el físico en el handoff del 25-08.

Causa real: `preINIGI` conecta 3 slots INDEPENDIENTES al botón "Iniciar"
(limpiar_layout / iniGUI / button_click), pero los desconecta de inmediato
y reconecta a `_iniciar_moviendo_tabla` -- ese bloque de 3 conexiones nunca
sobrevive para que el usuario haga click (código muerto heredado, no se
toca). El handler real, `_iniciar_moviendo_tabla`, SÍ encadenaba los 3
pasos sin mirar si `limpiar_layout` (vía `create_control`) había bloqueado
por Físico 1 inexistente -- `create_control` ya avisaba y no insertaba,
pero `iniGUI`/`button_click` se ejecutaban igual, armando la UI de captura
sobre un `self.ref` inválido (None). Cualquier guardado posterior con ese
`ref` habría quedado huérfano.

`limpiar_layout` ahora retorna `self.ref is not None`, y
`_iniciar_moviendo_tabla` corta si es False. Se prueba en las DOS clases
donde vive el contrato: `PruebaMensual600` (define el método) y
`PruebaAnual600` (lo hereda pero sobreescribe `limpiar_layout` -- si ese
override no retornara bool, el guard bloquearía el anual SIEMPRE, aunque
el físico sí exista; ver `test_a3_anual_no_queda_bloqueado_por_error_de_tipo`).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QMessageBox, QVBoxLayout, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600

INPUTS_MAQUINA = ["_", "_", "_", "Clinac ix"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = conexion.con
    con.execute("INSERT INTO users (fullname) VALUES ('Fisico Real')")
    con.commit()
    yield con
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def avisos(monkeypatch):
    capturados = {"warning": [], "information": [], "critical": []}
    for nombre in capturados:
        monkeypatch.setattr(
            QMessageBox, nombre,
            lambda *a, _n=nombre, **k: capturados[_n].append(a[1:]))
    return capturados


def _combo_con(texto):
    combo = QComboBox()
    combo.addItem(texto)
    return combo


def _obj(clase, fisico1_texto, fisico2_texto=""):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.general_layout = QVBoxLayout()
    obj.main_layout = QVBoxLayout()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 6, 1))
    obj.user_id_f1 = fisico1_texto
    obj.user_id_f2 = None
    obj.fisico1 = _combo_con(fisico1_texto)
    obj.fisico2 = _combo_con(fisico2_texto)
    obj.iniciado = []
    obj.iniGUI = lambda inputs_maquina=None: obj.iniciado.append("iniGUI")
    obj.button_click = lambda: obj.iniciado.append("button_click")
    return obj


class TestA3Mensual600FisicoInexistente:

    def test_no_llama_iniGUI_ni_button_click(self, app, bd_temporal, avisos):
        obj = _obj(PruebaMensual600, "Nombre Que No Existe")

        obj._iniciar_moviendo_tabla(INPUTS_MAQUINA)

        assert obj.iniciado == [], (
            "sin Físico 1 válido no debe armarse la UI de captura")
        assert obj.ref is None
        assert len(avisos["critical"]) == 1

    def test_no_inserta_fila_en_controles(self, app, bd_temporal, avisos):
        obj = _obj(PruebaMensual600, "Nombre Que No Existe")

        obj._iniciar_moviendo_tabla(INPUTS_MAQUINA)

        fila = bd_temporal.execute(
            "SELECT COUNT(*) FROM controles WHERE equipo = 'Clinac ix'"
        ).fetchone()
        assert fila[0] == 0


class TestA3Mensual600FisicoExistente:

    def test_si_llama_iniGUI_y_button_click_en_orden(self, app, bd_temporal, avisos):
        obj = _obj(PruebaMensual600, "Fisico Real")

        obj._iniciar_moviendo_tabla(INPUTS_MAQUINA)

        assert obj.iniciado == ["iniGUI", "button_click"]
        assert obj.ref is not None
        assert not avisos["critical"]

    def test_inserta_fila_en_controles(self, app, bd_temporal, avisos):
        obj = _obj(PruebaMensual600, "Fisico Real")

        obj._iniciar_moviendo_tabla(INPUTS_MAQUINA)

        fila = bd_temporal.execute(
            "SELECT COUNT(*) FROM controles WHERE equipo = 'Clinac ix'"
        ).fetchone()
        assert fila[0] == 1


class TestA3AnualHereda:
    """El anual (PruebaAnual600) sobreescribe `limpiar_layout` -- si ese
    override no retornara bool, `_iniciar_moviendo_tabla` (heredado)
    bloquearía el anual SIEMPRE, sin importar el físico. Este archivo
    verifica que el arreglo cubrió también ese segundo `limpiar_layout`."""

    def test_anual_no_queda_bloqueado_por_error_de_tipo(self, app, bd_temporal, avisos):
        obj = _obj(PruebaAnual600, "Fisico Real")
        obj.anual = True
        obj.user_id = type("U", (), {"_nombre": "Fisico Real"})()

        obj._iniciar_moviendo_tabla(INPUTS_MAQUINA)

        assert obj.iniciado == ["iniGUI", "button_click"], (
            "limpiar_layout del anual debe retornar True cuando el físico "
            "SÍ existe -- si retornara None (falsy), esto bloquearía el "
            "anual incondicionalmente")

    def test_anual_bloquea_si_fisico_no_existe(self, app, bd_temporal, avisos):
        obj = _obj(PruebaAnual600, "Nombre Que No Existe")
        obj.anual = True
        obj.user_id = type("U", (), {"_nombre": "Nombre Que No Existe"})()

        obj._iniciar_moviendo_tabla(INPUTS_MAQUINA)

        assert obj.iniciado == []
        assert obj.ref is None
