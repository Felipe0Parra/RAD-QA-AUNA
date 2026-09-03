"""D1 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): "Fuera de servicio" deja
de ser un pestillo de una sola vía.

Causa raíz (rebuild 2026-08-05): `reasignar_botonySERVICIO` ponía
`self.fueradeservicio = True` y NADA en todo el programa lo devolvía a
False -- solo el constructor. Desde ese click, TODO "Subir" posterior en esa
instancia se iba por `conectarfueradeservicio` (INSERT sin DELETE por fecha),
produciendo una fila vacía por cada click. Evidencia real: 7 filas vacías el
mismo día en `aceleradorlineal_ix`.

`self.fueradeservicio` es leído en el momento del click por el lambda de
conexión (`ordenar_botones(maquina, self.fueradeservicio)`), no capturado al
conectar la señal -- por eso el test de regresión (abajo) simula dos llamadas
sucesivas a `ordenar_botones` pasando el valor ACTUAL de la bandera en cada
una, igual que hace el binding real.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton

import ui.paginasControles.PruebasDiarias.PruebasDiarias as pd_mod
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _formulario(app):
    w = PruebaBasico(user_id=None)
    w.btn_add = QPushButton("Subir")
    w.datos_tabla = []
    w.botones_finales = set()
    w.botones_ordenados = []
    w.df_lines = []
    w.boolean_colums = []
    # I2 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md): `clean_info` ahora delega
    # en `_restablecer_formulario_diario`, que llama a
    # `_limpiar_widgets_diaria` -- necesita estos dos aunque estén vacíos,
    # o `zip(self.df_bnt_funciona, ...)` revienta con AttributeError. Este
    # doble es deliberadamente mínimo (D1 solo prueba la bandera "fuera de
    # servicio"), pero ahora `clean_info` de verdad los necesita.
    w.df_bnt_funciona = []
    w.df_bnt_nofunciona = []
    w.dosis = []
    w.dosis_ix = []
    return w


class TestD1FueraDeServicioNoEsPestillo:

    def test_guardado_fuera_de_servicio_restablece_la_bandera(self, app, monkeypatch):
        monkeypatch.setattr(pd_mod, "conectarfueradeservicio", lambda *a, **k: None)
        monkeypatch.setattr(pd_mod, "load_table", lambda *a, **k: None)
        w = _formulario(app)

        w.reasignar_botonySERVICIO()
        assert w.fueradeservicio is True

        w.ordenar_botones("aceleradorlineal_ix", True)

        assert w.fueradeservicio is False

    def test_guardado_normal_sigue_en_false(self, app, monkeypatch):
        monkeypatch.setattr(pd_mod, "add_info", lambda *a, **k: None)
        w = _formulario(app)

        w.ordenar_botones("aceleradorlineal_ix", False)

        assert w.fueradeservicio is False

    def test_clean_info_restablece_la_bandera(self, app):
        w = _formulario(app)
        w.reasignar_botonySERVICIO()
        assert w.fueradeservicio is True

        w.clean_info()

        assert w.fueradeservicio is False

    def test_dos_subir_tras_un_solo_click_no_repiten_conectarfueradeservicio(self, app, monkeypatch):
        """Regresión exacta del incidente 05-08: sin el fix, el segundo
        "Subir" también se iba por conectarfueradeservicio -- con el fix, va
        por el guardado normal (add_info)."""
        llamadas = {"fuera_de_servicio": 0, "normal": 0}
        monkeypatch.setattr(
            pd_mod, "conectarfueradeservicio",
            lambda *a, **k: llamadas.__setitem__(
                "fuera_de_servicio", llamadas["fuera_de_servicio"] + 1))
        monkeypatch.setattr(pd_mod, "load_table", lambda *a, **k: None)
        monkeypatch.setattr(
            pd_mod, "add_info",
            lambda *a, **k: llamadas.__setitem__("normal", llamadas["normal"] + 1))
        w = _formulario(app)

        w.reasignar_botonySERVICIO()
        w.ordenar_botones("aceleradorlineal_ix", w.fueradeservicio)  # 1er "Subir"
        w.ordenar_botones("aceleradorlineal_ix", w.fueradeservicio)  # 2do "Subir"

        assert llamadas == {"fuera_de_servicio": 1, "normal": 1}

    def test_texto_del_boton_vuelve_al_original(self, app, monkeypatch):
        monkeypatch.setattr(pd_mod, "conectarfueradeservicio", lambda *a, **k: None)
        monkeypatch.setattr(pd_mod, "load_table", lambda *a, **k: None)
        w = _formulario(app)
        texto_original = w.btn_add.text()

        w.reasignar_botonySERVICIO()
        assert w.btn_add.text() != texto_original

        w.ordenar_botones("aceleradorlineal_ix", True)

        assert w.btn_add.text() == texto_original
