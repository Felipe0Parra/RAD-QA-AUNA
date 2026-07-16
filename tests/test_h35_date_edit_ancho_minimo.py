"""H3.5 (PLAN_FASE_H, 2026-07-16) -- el "combo de mes" (QDateEdit con
`setDisplayFormat("MM/yyyy")`) de los formularios mensuales (600/iX/Halcyon/
TAC) mostraba el texto cortado ("07/202" en vez de "07/2026"): verificado
offscreen que el ancho natural (sizeHint) de un QDateEdit con calendario
emergente es ~87px con el stylesheet real de la app (`resources/estilo.qss`,
regla `QDateEdit::drop-down` de 20px + `padding: 5px`) -- por debajo de eso
la flecha del calendario le come espacio al texto. Cuando el layout real
comparte columna con otros campos, puede terminar más angosto que eso.

Arreglado en el punto único de creación (`PruebasDiarias.createInterface`,
usado por TODOS los formularios diarios y mensuales vía el sistema de UI
generado desde `widgets.xlsx`) para que ningún QDateEdit nuevo repita el
problema -- no en cada formulario por separado. No toca la calculadora:
`DialogCalculadoraDosis.date_edit` (dialogs.py:1296) se crea directo con
`QDateEdit(self)`, sin pasar por este método."""
import os

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico


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
    def test_date_edit_recien_creado_tiene_ancho_minimo_seguro(self, app):
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(), 1)

        # 100px con margen sobre los ~87px de sizeHint natural medidos
        # offscreen para "MM/yyyy" con el stylesheet real de la app.
        assert obj.date_box.minimumWidth() >= 100

    def test_sigue_seguro_tras_cambiar_a_formato_de_solo_mes(self, app):
        # El ancho mínimo se fija en la creación, ANTES de que cada
        # formulario mensual llame setDisplayFormat("MM/yyyy") -- debe
        # seguir aplicando después del cambio de formato (setMinimumWidth
        # no se resetea por setDisplayFormat).
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(), 1)

        obj.date_box.setDisplayFormat("MM/yyyy")

        assert obj.date_box.minimumWidth() >= 100

    def test_formularios_diarios_no_se_ven_afectados(self, app):
        # dd/MM/yyyy (formularios diarios) ya es más ancho que el mínimo
        # nuevo -- setMinimumWidth es un piso, no fuerza un ancho fijo.
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(), 1)
        obj.date_box.setDisplayFormat("dd/MM/yyyy")

        assert obj.date_box.sizeHint().width() >= obj.date_box.minimumWidth()
