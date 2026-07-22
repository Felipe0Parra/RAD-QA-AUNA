"""A11 (§8.1 H6 del PLAN_AUDITORIA_DOS_EJES_21-07): la pestaña "Registros"
queda habilitada en la UI.

Hallazgo del rebuild 22-07: el físico preguntó "¿qué es el visor de
registros? ¿una nueva tabla, una pestaña?" -- A7 dejó el widget
`console_logs.Registros` correcto y usable, pero la entrada en
`_tab_definiciones` y el método `MainWindow.Registros()` seguían
comentados en `mainpages.py`, así que la pestaña nunca existió en la app.
"""
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import ui.mainpages as mainpages_mod
from ui.paginasGuia.console_logs import Registros


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestA11PestanaRegistrosHabilitada:

    def test_registros_aparece_activa_en_las_definiciones_de_pestanas(self):
        """_tab_definiciones se arma dentro de MainWindow.Tab() -- se
        verifica sobre el código fuente para no tener que levantar toda la
        ventana principal (login, menús, conexión a BD, etc.)."""
        fuente = inspect.getsource(mainpages_mod.MainWindow.Tab)
        assert '("Registros", lambda: self.Registros())' in fuente
        assert not any(
            linea.strip().startswith('#') and 'Registros' in linea
            for linea in fuente.splitlines()
        ), "la entrada de Registros sigue comentada"

    def test_metodo_registros_crea_el_widget_correcto(self, app):
        """El método no usa `self` -- se puede invocar unbound sin
        necesidad de construir un MainWindow completo."""
        resultado = mainpages_mod.MainWindow.Registros(object())
        assert isinstance(resultado, Registros)
