"""T2/T3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS1.3): TPR20,10 calculado
automáticamente desde PDD a 20 cm y a 10 cm (ecuación 4-2, catálogo PTW
DETECTORS_Cat_en_16522900_16.pdf p.84, IAEA TRS-398:
TPR20,10 = 1.2661 · PDD20,10 − 0.0595), sin bloquear el llenado manual --
requisito explícito del físico. T3: tooltip que explica el origen del
valor, sin símbolos de correcto/incorrecto (regla de sesión).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import data.ManejoDatos.conection as conection_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO = {"id": 1, "equip_type": "Cámara de ionización", "model": "N31010",
          "serie": "1822", "calibr_fact": 0.3045, "t_cal": 22.0,
          "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en 'IX' -> acelerador_actual='IX'."""


class VentanaHc(QWidget):
    """Padre falso cuyo nombre termina en 'Hc' -> acelerador_actual='Hc'."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    yield ruta


@pytest.fixture
def dialogo_factory(app, bd_temporal, monkeypatch):
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": EQUIPO["model"], "equip_type": EQUIPO["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [EQUIPO] if m == EQUIPO["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: EQUIPO if i == EQUIPO["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))

    def _crear(parent_cls=VentanaIX):
        d = DialogCalculadoraDosis(energias=["6mv"], parent=parent_cls())
        d.fotones.setChecked(True)
        return d

    return _crear


class TestCalculoAutomaticoDesdeReto:

    def test_reproduce_el_valor_de_oro_de_dosis_service_calculations(self, dialogo_factory):
        """Mismos valores que test_dosis_service_calculations.py::charge --
        no se recalibra la fórmula, se reutiliza el motor ya validado."""
        d = dialogo_factory()
        d.pdd20.setText("38.5")
        d.pdd10.setText("66.6")
        assert d.tpr2010.text() == "0.6724"

    def test_pdd10_cero_no_escribe_nada(self, dialogo_factory):
        d = dialogo_factory()
        d.pdd20.setText("38.5")
        d.pdd10.setText("0")
        assert d.tpr2010.text() == ""

    def test_texto_no_numerico_no_lanza(self, dialogo_factory):
        d = dialogo_factory()
        d.pdd20.setText("abc")
        d.pdd10.setText("66.6")
        assert d.tpr2010.text() == ""

    def test_solo_un_campo_lleno_no_calcula(self, dialogo_factory):
        d = dialogo_factory()
        d.pdd20.setText("38.5")
        assert d.tpr2010.text() == ""


class TestPrecedenciaManual:

    def test_editar_a_mano_gana_sobre_autollenado_posterior(self, dialogo_factory):
        d = dialogo_factory()
        d.pdd20.setText("38.5")
        d.pdd10.setText("66.6")
        assert d.tpr2010.text() == "0.6724"

        d.tpr2010.setText("0.700")
        d.tpr2010.textEdited.emit("0.700")  # setText() por código no emite textEdited

        d.pdd20.setText("40.0")  # cambia el PDD DESPUÉS de la edición manual

        assert d.tpr2010.text() == "0.700", "el valor tecleado a mano no debe pisarse"

    def test_borrar_tpr_manual_libera_el_autollenado(self, dialogo_factory):
        d = dialogo_factory()
        d.tpr2010.setText("0.700")
        d.tpr2010.textEdited.emit("0.700")

        d.tpr2010.setText("")
        d.tpr2010.textEdited.emit("")

        d.pdd20.setText("38.5")
        d.pdd10.setText("66.6")

        assert d.tpr2010.text() == "0.6724"

    def test_autollenado_nunca_marca_como_editado_manualmente(self, dialogo_factory):
        d = dialogo_factory()
        d.pdd20.setText("38.5")
        d.pdd10.setText("66.6")
        assert d._tpr2010_editado_manualmente is False


class TestExclusionHalcyon:

    def test_halcyon_no_autollena_aunque_pdd_tenga_datos(self, dialogo_factory):
        """Decisión del físico (2026-07-23): sin TPR automático en Halcyon
        (FFF) -- ni siquiera si los widgets llegaran a tener datos (p.ej.
        restaurados de un registro antiguo)."""
        d = dialogo_factory(parent_cls=VentanaHc)
        d.pdd20.setText("38.5")
        d.pdd10.setText("66.6")
        assert d.tpr2010.text() == ""


class TestTooltipOrigen:

    def test_sin_dato_explica_las_dos_vias(self, dialogo_factory):
        d = dialogo_factory()
        tooltip = d.tpr2010.toolTip().lower()
        assert "manual" in tooltip
        assert "pdd" in tooltip

    def test_autollenado_explica_la_formula(self, dialogo_factory):
        d = dialogo_factory()
        d.pdd20.setText("38.5")
        d.pdd10.setText("66.6")
        tooltip = d.tpr2010.toolTip()
        assert "TRS-398" in tooltip
        assert "PDD" in tooltip

    def test_edicion_manual_explica_que_es_manual(self, dialogo_factory):
        d = dialogo_factory()
        d.tpr2010.setText("0.700")
        d.tpr2010.textEdited.emit("0.700")
        assert "manual" in d.tpr2010.toolTip().lower()

    def test_ningun_tooltip_usa_simbolos_de_correcto_incorrecto(self, dialogo_factory):
        """Regla de sesión (2026-07-23): sin chulito/equis ni similares."""
        d = dialogo_factory()
        for texto in (d.tpr2010.toolTip(),):
            assert not any(c in texto for c in ("✓", "✗", "✔", "❌"))

        d.pdd20.setText("38.5")
        d.pdd10.setText("66.6")
        assert not any(c in d.tpr2010.toolTip() for c in ("✓", "✗", "✔", "❌"))
