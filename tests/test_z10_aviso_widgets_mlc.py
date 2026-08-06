"""Z10 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): el aviso "Widgets MLC
no encontrados" en `ix_mensual.py::_configurar_mlcs_ix`.

Causa real, confirmada instanciando el diálogo real (no hipótesis): el
código comprobaba `hasattr(self, 'ln_action_tolerance_ix')` -- un nombre que
NUNCA existe. El widget real, creado desde `widgets.xlsx` con el MISMO
nombre que usa el 600 (`_configurar_mlcs`, `seiscientos_mensual.py`), es
`ln_action_tolerance`, sin sufijo `_ix`. El aviso salía SIEMPRE, aunque los
widgets sí estuvieran presentes y correctamente configurados -- 6 veces en
la terminal del handoff. Además usaba un símbolo de advertencia (⚠️), contra
DA-18 (sin símbolos de correcto/incorrecto/advertencia, aunque sea consola).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _ix_pelado(con_widgets):
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    if con_widgets:
        obj.ln_tolerance_mlc = QLineEdit()
        obj.ln_action_tolerance = QLineEdit()
    return obj


class TestWidgetsPresentesNoAvisan:
    def test_con_los_widgets_reales_no_imprime_el_aviso(self, app, capsys):
        d = _ix_pelado(con_widgets=True)

        capsys.readouterr()
        d._configurar_mlcs_ix()
        salida = capsys.readouterr().out

        assert "Widgets MLC encontrados y configurados" in salida
        assert "no encontrados" not in salida


class TestSinWidgetsAvisaSinSimbolo:
    def test_sin_los_widgets_avisa_pero_sin_simbolo(self, app, capsys):
        d = _ix_pelado(con_widgets=False)

        capsys.readouterr()
        d._configurar_mlcs_ix()
        salida = capsys.readouterr().out

        assert "no encontrados" in salida
        assert "⚠️" not in salida


class TestNingunCasoUsaSimboloDeAdvertencia:
    """DA-18: sin símbolos de correcto/incorrecto/advertencia en ningún
    texto que el físico lea -- ni siquiera en consola."""

    @pytest.mark.parametrize("con_widgets", [True, False])
    def test_sin_simbolo_en_ningun_caso(self, app, con_widgets, capsys):
        d = _ix_pelado(con_widgets=con_widgets)

        capsys.readouterr()
        d._configurar_mlcs_ix()
        salida = capsys.readouterr().out

        assert "⚠️" not in salida
