"""A10 (§8.1 H5 del PLAN_AUDITORIA_DOS_EJES_21-07): el diario del Halcyon
queda SIN edición manual (decisión del físico, 2026-07-22): el registro se
carga solo desde los archivos MPC, así que no tiene sentido editarlo a mano.

Antes, el botón "Editar" reusaba verificar_editar()/edicionTabla()
(PruebasDiarias.py), que revienta con `AttributeError: 'PruebaDiariaHc'
object has no attribute 'boolean_colums'` -- esa clase nunca definió ese
atributo (solo existe en seiscientos.py/IX.py). Traza real en
error_log(22-07-2026).txt, correlacionada con los logins id 37/38 del
audit_log del rebuild (el físico reintentó dos veces).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit, QComboBox, QDateEdit)

from ui.paginasControles.PruebasDiarias.halcyon import PruebaDiariaHc


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _HalcyonDiarioFalso(QWidget):
    """Solo los widgets que button_click() conecta -- boolean_colums se deja
    AUSENTE a propósito: si algo volviera a intentar leerlo, debe fallar
    ruidosamente aquí, no en producción."""

    def __init__(self):
        super().__init__()
        self.btn_submit = QPushButton()
        self.mach_name2 = QLineEdit("Halcyon")
        self.code_1 = QLineEdit("HAL1161")
        self.date_box = QDateEdit()
        self.diccionario_invertido = {}
        self.menu_graficar = QComboBox()
        self.btn_delete = QPushButton()
        self.graficar = []
        self.limit1 = QDateEdit()
        self.limit2 = QDateEdit()
        self.search_bar = QLineEdit()
        self.edit_table = QPushButton("Editar")
        self.accept_edit = QPushButton()
        self.cancel_edit = QPushButton()
        self.btn_add = QPushButton()  # H1: button_click() la conecta

    # button_click() los conecta directamente (no dentro de una lambda), así
    # que deben existir como atributos llamables ya al conectar -- no hace
    # falta que hagan nada para este test (no se disparan).
    def mostrar_submenu(self):
        pass

    def filtrarTabla(self):
        pass

    def agregar_fecha_seleccionada(self):
        # H3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §H3): antes se
        # llamaba `importar_fecha_seleccionada`; al separarse el flujo en
        # previsualizar/agregar, `button_click` conecta btn_add a este nombre.
        pass


class TestA10HalcyonSinEdicionManual:

    def test_boton_editar_queda_deshabilitado(self, app):
        w = _HalcyonDiarioFalso()
        PruebaDiariaHc.button_click(w)
        assert w.edit_table.isEnabled() is False

    def test_boton_editar_explica_por_que(self, app):
        w = _HalcyonDiarioFalso()
        PruebaDiariaHc.button_click(w)
        assert "MPC" in w.edit_table.toolTip()

    def test_no_reconecta_verificar_editar(self, app):
        """El punto de fondo del hallazgo: ya no debe existir ningún camino
        de "Editar" -> verificar_editar -> edicionTabla para esta clase."""
        w = _HalcyonDiarioFalso()
        PruebaDiariaHc.button_click(w)
        assert w.edit_table.receivers(w.edit_table.clicked) == 0
