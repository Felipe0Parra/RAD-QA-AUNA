"""H3.5 + I5 -- ancho mínimo de los QDateEdit para que la flecha del
calendario nunca se coma el texto de la fecha.

Historia: H3.5 puso `setMinimumWidth(100)` -- un valor ABSOLUTO calibrado con
la fuente del entorno de desarrollo -- y el físico reportó (16-07) que en su
Windows (otra fuente/escala) el campo seguía cortado, tanto en el formulario
mensual como en la calculadora (que H3.5 había excluido a propósito). I5 lo
reemplaza por `ui.util_fechas.ancho_minimo_fecha`: el piso sale de la MÉTRICA
DE FUENTE real del widget en runtime, así que se adapta solo a Segoe UI, DPI
125%, etc. Estos tests verifican contra fontMetrics del propio widget, nunca
contra un número fijo de px (un número fijo repetiría el bug de H3.5 dentro
del test).

El punto único de creación de los formularios es `PruebasDiarias.
createInterface` (todos los diarios y mensuales, vía widgets.xlsx); la
calculadora crea su `date_edit` aparte (dialogs.py) y se cubre en
test_calculadora_dosis_ui.py::test_i5_*.
"""
import os

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.util_fechas import RESERVA_DECORACION_PX

# Decoración sin la holgura: el assert exige lo IRRENUNCIABLE (texto +
# drop-down 20px + padding 10px + bordes 4px); la holgura extra del helper
# es bienvenida pero no es el contrato.
_DECORACION_DURA_PX = 34


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _instancia_pelada():
    obj = PruebaBasico.__new__(PruebaBasico)
    QWidget.__init__(obj)
    return obj


def _fila_date_edit(nombre="date_box", prueba="encabezado"):
    return pd.DataFrame([{
        "prueba": prueba, "nombres": nombre, "widget_type": "QDateEdit",
        "descripcion": None, "pose": (0, 0, 1, 1),
    }])


class TestAnchoMinimoQDateEdit:
    def test_minimo_cubre_el_formato_largo_segun_la_fuente_real(self, app):
        """dd/MM/yyyy (el formato más ancho en uso) debe caber junto a la
        decoración, medido con la fuente REAL del widget."""
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(), 1)

        fm = obj.date_box.fontMetrics()
        necesario = fm.horizontalAdvance("00/00/0000") + _DECORACION_DURA_PX
        assert obj.date_box.minimumWidth() >= necesario

    def test_sigue_cubriendo_tras_cambiar_a_formato_de_solo_mes(self, app):
        """Los formularios mensuales cambian a "MM/yyyy" DESPUÉS de crear el
        widget (seiscientos_mensual) -- el piso se calcula con el formato
        más ancho, así que cubre de sobra el corto y no se resetea con
        setDisplayFormat."""
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(), 1)

        obj.date_box.setDisplayFormat("MM/yyyy")

        fm = obj.date_box.fontMetrics()
        necesario_mes = fm.horizontalAdvance("00/0000") + _DECORACION_DURA_PX
        assert obj.date_box.minimumWidth() >= necesario_mes

    def test_nunca_por_debajo_del_piso_h35(self, app):
        """Regresión H3.5: con cualquier fuente, el piso nuevo no puede ser
        más laxo que los 100px que ya se habían probado insuficientes solo
        por quedarse cortos (el texto medía ~87px con la fuente de dev)."""
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(), 1)

        assert obj.date_box.minimumWidth() >= 100

    def test_la_reserva_de_decoracion_no_se_degrada(self):
        """Tripwire: la reserva del helper debe seguir cubriendo al menos la
        decoración dura del stylesheet (drop-down 20 + padding 10 + bordes
        4). Si alguien la recorta, esto revienta antes que la UI."""
        assert RESERVA_DECORACION_PX >= _DECORACION_DURA_PX
