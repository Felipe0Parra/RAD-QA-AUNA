"""H7 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): la rama `QDateTimeEdit` de
`PruebasDiarias.createInterface` (`:267`) nunca recibió el piso de ancho que
H3.5/I5 ya le dieron a su rama hermana `QDateEdit` (`:242`) -- pese a
necesitar CASI EL DOBLE de ancho ("yyyy-MM-dd HH:mm:ss", 19 caracteres,
contra "dd/MM/yyyy", 10). [medido]: el widget SÍ acepta teclear la hora (no
es un rechazo de entrada); sin piso, el layout la aprieta y las secciones de
hora quedan fuera del área alcanzable con el mouse -- "no se puede ubicar el
cursor adecuadamente" describe un problema de posicionamiento.

Mismo criterio que test_h35_date_edit_ancho_minimo.py: medir contra
fontMetrics del propio widget, nunca contra un número fijo de px.
"""
import os

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.util_fechas import RESERVA_DECORACION_PX

_DECORACION_DURA_PX = 34


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _instancia_pelada():
    obj = PruebaBasico.__new__(PruebaBasico)
    QWidget.__init__(obj)
    return obj


def _fila_date_time_edit(nombre="date_box", prueba="encabezado"):
    return pd.DataFrame([{
        "prueba": prueba, "nombres": nombre, "widget_type": "QDateTimeEdit",
        "descripcion": None, "pose": (0, 0, 1, 1),
    }])


class TestAnchoMinimoQDateTimeEdit:
    def test_minimo_cubre_fecha_y_hora_segun_la_fuente_real(self, app):
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_time_edit(), 1)

        fm = obj.date_box.fontMetrics()
        necesario = fm.horizontalAdvance("0000-00-00 00:00:00") + _DECORACION_DURA_PX
        assert obj.date_box.minimumWidth() >= necesario, (
            "el QDateTimeEdit debe caber junto a la decoración con su "
            "propio formato completo -- nunca puede quedar más angosto "
            "que su propio texto (intuición de garantía de H7)")

    def test_necesita_mas_ancho_que_el_qdateedit_hermano(self, app):
        """El defecto medido: "yyyy-MM-dd HH:mm:ss" es casi el doble de
        ancho que "dd/MM/yyyy" -- si el mínimo de QDateTimeEdit terminara
        siendo igual o menor al de QDateEdit, el piso no estaría cubriendo
        su propio formato."""
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_time_edit("date_box_hora"), 1)
        obj.createInterface(
            pd.DataFrame([{
                "prueba": "encabezado", "nombres": "date_box_fecha",
                "widget_type": "QDateEdit", "descripcion": None,
                "pose": (0, 1, 1, 1),
            }]), 1)

        assert (obj.date_box_hora.minimumWidth()
                > obj.date_box_fecha.minimumWidth())

    def test_la_reserva_de_decoracion_no_se_degrada(self):
        assert RESERVA_DECORACION_PX >= _DECORACION_DURA_PX
