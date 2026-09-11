"""A.5 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS2, SS0.5b): `mainpages.py`
leía `ref.ref` sobre una página anual que todavía no tiene `ref` (solo
nace dentro de `limpiar_layout`, al pulsar "Iniciar"). Abrir "Imágenes
Anual" ANTES de iniciar el Anual lanzaba `AttributeError`, hoy, sin ningún
cambio -- PyQt la atrapa en el slot de Qt y el físico ve que el botón no
hace nada, sin ningún aviso (patrón H3).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.mainpages import Menuu


class _UsuarioFalso:
    _nombre = "Fisico Uno"
    _usuario = "f1"


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


class TestImagenAnualSinIniciarNoRevienta:
    @pytest.mark.parametrize("maquina", ["iX", "Halcyon"])
    def test_pedir_imagen_anual_sin_iniciar_el_anual_no_lanza_attributeerror(
            self, app, bd_temporal, monkeypatch, maquina):
        avisos = []
        monkeypatch.setattr(
            QMessageBox, "information",
            staticmethod(lambda *a, **k: avisos.append(a)))
        for tipo in ("warning", "critical", "question"):
            monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))

        menuu = Menuu(maquina, _UsuarioFalso())

        # Directo, sin pasar por "anual": es exactamente el camino que
        # antes reventaba -- self._pagina_anual_ix/_hc ni siquiera existen
        # todavía como atributo (getattr con default ya lo cubre).
        pagina = menuu._crear_pagina("imagen_anual")

        assert pagina is not None
        assert avisos, "no avisó -- el botón se hubiera quedado mudo"

    @pytest.mark.parametrize("maquina", ["iX", "Halcyon"])
    def test_pagina_anual_creada_pero_no_iniciada_tampoco_revienta(
            self, app, bd_temporal, monkeypatch, maquina):
        """Caso más fino que el anterior: la página anual SÍ se creó (el
        físico entró a "Anual") pero no pulsó "Iniciar" -- self.ref no
        existe como atributo en absoluto, ni siquiera en None."""
        avisos = []
        monkeypatch.setattr(
            QMessageBox, "information",
            staticmethod(lambda *a, **k: avisos.append(a)))
        for tipo in ("warning", "critical", "question"):
            monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))

        menuu = Menuu(maquina, _UsuarioFalso())
        menuu._mostrar_pagina("anual")
        pagina_anual = menuu._paginas["anual"]
        assert not hasattr(pagina_anual, "ref"), (
            "la fixture asume que 'ref' todavía no existe antes de Iniciar")

        pagina_img = menuu._crear_pagina("imagen_anual")

        assert pagina_img is not None
        assert avisos
