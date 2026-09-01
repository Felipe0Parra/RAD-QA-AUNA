"""C1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 1): repara
`PruebaAnual600._calcular_discrepancias_tablas` en la raíz -- alimenta la
columna de discrepancia de las 10 tablas de los tres anuales y del mensual
de Halcyon.

Tres defectos, todos medidos contra el callback real antes de tocar nada:

- `AN-1`: un "esperado" vacío (o "medida" vacía) se colapsaba a `0.0` y
  fabricaba una discrepancia de "0.00" que se guardaba y se imprimía en el
  informe firmado. Correcto: una celda vacía no escribe nada (`D-B`).
- `AN-2`: la guarda `if valor_esperado != 0` existe para evitar la división
  por cero de `porcentaje`, pero se aplicaba a los cuatro tipos. `absoluta`,
  `angular` y `promedio` deben calcular normalmente con esperado `0` (`D-C`);
  solo `porcentaje` queda indefinido.
- `AN-3`: el envoltorio angular (0<->360) se aplicaba a un solo lado de la
  resta. Debe aplicarse a los dos lados, independientemente.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QWidget

from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _anual_pelado():
    obj = PruebaAnual600.__new__(PruebaAnual600)
    QWidget.__init__(obj)
    return obj


def _tabla(medida, esperado, columna_real=1, columna_esperada=2, ncols=4):
    tabla = QTableWidget(1, ncols)
    if medida is not None:
        tabla.setItem(0, columna_real, QTableWidgetItem(str(medida)))
    if esperado is not None:
        tabla.setItem(0, columna_esperada, QTableWidgetItem(str(esperado)))
    return tabla


def _texto_discrepancia(tabla, fila=0, columna=3):
    item = tabla.item(fila, columna)
    return item.text() if item is not None else None


class TestAN1CeldaVaciaNoFabricaCero:
    """`D-B`: con la casilla "esperado" (o "medida") vacía, la discrepancia
    queda vacía -- no `"0.00"`, no `"N/A"`."""

    def test_esperado_vacio_no_escribe_cero(self, app):
        obj = _anual_pelado()
        tabla = _tabla(0.812, "")
        calcular = obj._calcular_discrepancias_tablas(tabla, 1, 2)
        calcular()
        assert _texto_discrepancia(tabla) in ("", None)

    def test_ambos_vacios_no_escribe_cero(self, app):
        obj = _anual_pelado()
        tabla = _tabla("", "")
        calcular = obj._calcular_discrepancias_tablas(tabla, 1, 2)
        calcular()
        assert _texto_discrepancia(tabla) in ("", None)

    def test_medida_vacia_esperado_presente_no_escribe_cero(self, app):
        # Simétrico a AN-1: el callback recorre TODAS las filas en cada
        # edición -- una fila cuya "medida" nadie ha tecleado todavía no
        # debe recibir una discrepancia fabricada contra el "esperado".
        obj = _anual_pelado()
        tabla = _tabla("", 1.0)
        calcular = obj._calcular_discrepancias_tablas(tabla, 1, 2)
        calcular()
        assert _texto_discrepancia(tabla) in ("", None)

    def test_caso_normal_sigue_calculando_igual(self, app):
        obj = _anual_pelado()
        tabla = _tabla(1.020, 1.000)
        calcular = obj._calcular_discrepancias_tablas(tabla, 1, 2)
        calcular()
        assert _texto_discrepancia(tabla) == "2.00"


class TestAN2GuardaSoloParaPorcentaje:
    """`D-C`: un esperado legítimamente `0` devuelve la desviación real para
    `absoluta`, `angular` y `promedio`; solo `porcentaje` queda indefinido."""

    def test_angular_con_esperado_cero_calcula(self, app):
        obj = _anual_pelado()
        tabla = _tabla(0.7, 0)
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 1, 2, diferencia_tipo="angular")
        calcular()
        assert _texto_discrepancia(tabla) == "0.70"

    def test_absoluta_con_esperado_cero_calcula(self, app):
        obj = _anual_pelado()
        tabla = _tabla(0.4, 0)
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 1, 2, diferencia_tipo="absoluta")
        calcular()
        assert _texto_discrepancia(tabla) == "0.40"

    def test_promedio_con_esperado_cero_calcula(self, app):
        obj = _anual_pelado()
        tabla = _tabla(5.0, 0)
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 1, 2, diferencia_tipo="promedio")
        calcular()
        assert _texto_discrepancia(tabla) == "2.50"

    def test_porcentaje_con_esperado_cero_no_da_cero(self, app):
        obj = _anual_pelado()
        tabla = _tabla(1.02, 0)
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 1, 2, diferencia_tipo="porcentaje")
        calcular()
        assert _texto_discrepancia(tabla) != "0.00"


class TestAN3EnvoltorioAngularEnLosDosLados:
    def test_ambos_lados_cerca_del_cero_dan_la_desviacion_real(self, app):
        # esperado 358, medida 359.5 -> desviación real 1.5, no 357.50
        obj = _anual_pelado()
        tabla = _tabla(359.5, 358)
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 1, 2, diferencia_tipo="angular")
        calcular()
        assert _texto_discrepancia(tabla) == "1.50"

    def test_ningun_lado_cerca_del_cero_no_cambia(self, app):
        obj = _anual_pelado()
        tabla = _tabla(92.0, 90)
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 1, 2, diferencia_tipo="angular")
        calcular()
        assert _texto_discrepancia(tabla) == "2.00"


class TestAlcanceCubreHalcyonMensual:
    """El plan avisa expresamente: esta función también alimenta
    `halcyon_mensual.py:127,132` (mismo método heredado, sin sobreescribir).
    Se reproduce aquí la firma exacta de esos dos registros."""

    def test_registro_angular_de_halcyon_mensual_127(self, app):
        # halcyon_mensual.py:127 -- (tabla, 0, 1, 2, diferencia_tipo='angular')
        obj = _anual_pelado()
        tabla = _tabla(359.5, 358, columna_real=0, columna_esperada=1, ncols=3)
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 0, 1, 2, diferencia_tipo="angular")
        calcular()
        assert _texto_discrepancia(tabla, columna=2) == "1.50"

    def test_registro_porcentaje_de_halcyon_mensual_132(self, app):
        # halcyon_mensual.py:132 -- (tabla, 2, 1, 3, diferencia_tipo='porcentaje')
        obj = _anual_pelado()
        tabla = _tabla(20.4, None, columna_real=2, columna_esperada=1, ncols=4)
        tabla.setItem(0, 1, QTableWidgetItem("20"))
        calcular = obj._calcular_discrepancias_tablas(
            tabla, 2, 1, 3, diferencia_tipo="porcentaje")
        calcular()
        assert _texto_discrepancia(tabla, columna=3) == "2.00"


class TestZ9SigueVerdeTrasElCambio:
    """No debe romperse la protección de tabla destruida ni el cálculo base
    que Z9 ya cubría."""

    def test_tabla_viva_calcula_la_discrepancia(self, app):
        obj = _anual_pelado()
        tabla = _tabla(10, 8)
        calcular = obj._calcular_discrepancias_tablas(tabla, 1, 2)
        calcular()
        assert _texto_discrepancia(tabla) == "25.00"
