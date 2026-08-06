"""Z9 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): el cálculo de
discrepancias no corre sobre una tabla destruida.

`RuntimeError: wrapped C/C++ object of type QTableWidget has been deleted`
en `seiscientos_anual.py`, dentro del `calcular()` que devuelve
`_calcular_discrepancias_tablas`. El callback queda conectado a un
`itemChanged`/`textChanged` con debouncing (~300ms) y se dispara cuando la
tabla ya fue destruida -- gemelo exacto de G6 (`_debounce_timers` sin
`hasattr`), pero aquí el objeto que desaparece es la propia tabla, no el
diccionario de timers.

Mecanismo: guarda `sip.isdeleted(tabla)` al entrar en `calcular()` --
defensa complementaria a `limpiar_recursos` (heredado de
`PruebaMensual600`), que ya detiene los timers pendientes al destruir la
vista, para la ventana de carrera en que el timer ya estaba en curso.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import sip
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QWidget

from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _anual_pelado():
    obj = PruebaAnual600.__new__(PruebaAnual600)
    QWidget.__init__(obj)
    return obj


def _tabla_con_fila(medida, esperado):
    tabla = QTableWidget(1, 4)
    tabla.setItem(0, 1, QTableWidgetItem(str(medida)))
    tabla.setItem(0, 2, QTableWidgetItem(str(esperado)))
    return tabla


class TestTablaDestruidaNoLanzaNiImprime:
    def test_no_lanza_ni_imprime_el_error(self, app, capsys):
        obj = _anual_pelado()
        tabla = _tabla_con_fila(10, 8)
        calcular = obj._calcular_discrepancias_tablas(tabla, 1, 2)

        sip.delete(tabla)
        assert sip.isdeleted(tabla)

        capsys.readouterr()
        calcular()  # no debe lanzar
        salida = capsys.readouterr().out

        assert "wrapped C/C++ object" not in salida
        assert "Error calculando discrepancias" not in salida


class TestTablaVivaSigueCalculandoIgual:
    def test_tabla_viva_calcula_la_discrepancia(self, app):
        obj = _anual_pelado()
        tabla = _tabla_con_fila(10, 8)
        calcular = obj._calcular_discrepancias_tablas(tabla, 1, 2)

        calcular()

        # |10-8|/8 * 100 = 25.00
        assert tabla.item(0, 3).text() == "25.00"
