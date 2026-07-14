"""Fase G2-G5 (auditoría 2026-07-10) -- ajustes de usabilidad pedidos por el
físico en la revisión del 2026-07-10 (HANDOFF_BUILD_WINDOWS). G1 (la
regresión de cierre/pérdida de datos) tiene su propia suite dedicada en
test_calculadora_dosis_g1.py por ser la de mayor prioridad clínica.

- G2: TPR20,10 no aplica a electrones (su kQ sale de R50) -- oculto salvo
  con Fotones marcado.
- G3: la humedad de calibración (h_cal) no se cargaba al elegir la serie,
  aunque EquiposService.obtener_por_id ya la devuelve.
- G4: el modo de escaneo "Pulse" nace marcado por defecto (antes ninguno).
- G5: el ítem de menú muerto "Graficar perfiles" (nunca conectado a nada)
  se retira; se reintroducirá cuando D4 traiga perfiles reales del .mcc.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_N31010 = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                 "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 47.5}
EQUIPO_TN34001 = {"id": 55, "equip_type": "Cámara de ionización", "model": "TN34001",
                  "serie": "001069", "calibr_fact": 0.08563, "t_cal": 20.0,
                  "p_cal": 101.325, "h_cal": 50.0}
EQUIPOS = (EQUIPO_N31010, EQUIPO_TN34001)


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (electrones disponibles)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogo(app, monkeypatch):
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": e["model"], "equip_type": e["equip_type"]}
                              for e in EQUIPOS]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [e for e in EQUIPOS if e["model"] == m]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: next((e for e in EQUIPOS if e["id"] == i), None)))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))

    d = DialogCalculadoraDosis(energias=["6mv"], parent=VentanaIX())
    yield d
    d.deleteLater()


def seleccionar_camara(d, modelo):
    idx = d.combo_modelos.findData(modelo)
    assert idx >= 0, f"{modelo} no está en el combo"
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)


class TestG2OcultarTPR2010ParaElectrones:
    def test_oculto_por_defecto_antes_de_elegir_tipo(self, dialogo):
        assert dialogo.tpr2010.isHidden()

    def test_visible_con_fotones(self, dialogo):
        dialogo.fotones.setChecked(True)
        assert dialogo.tpr2010.isVisible() or not dialogo.tpr2010.isHidden()
        assert not dialogo.tpr2010.isHidden()
        assert not dialogo.lbl_tpr2010.isHidden()
        assert not dialogo.mostrar_ayuda_tpr2010.isHidden()

    def test_oculto_con_electrones(self, dialogo):
        dialogo.electrones.setChecked(True)
        assert dialogo.tpr2010.isHidden()
        assert dialogo.lbl_tpr2010.isHidden()
        assert dialogo.mostrar_ayuda_tpr2010.isHidden()

    def test_alternar_fotones_electrones_actualiza_visibilidad(self, dialogo):
        dialogo.fotones.setChecked(True)
        assert not dialogo.tpr2010.isHidden()
        dialogo.electrones.setChecked(True)
        assert dialogo.tpr2010.isHidden()
        dialogo.fotones.setChecked(True)
        assert not dialogo.tpr2010.isHidden()


class TestG3CargarHumedadCalibracion:
    def test_humedad_se_carga_con_la_serie(self, dialogo):
        seleccionar_camara(dialogo, "N31010")
        assert dialogo.humr_cal.text() == "47.5"

    def test_temperatura_presion_humedad_muestran_el_valor_crudo_del_certificado(self, dialogo):
        """H3.6 (auditoría 2026-07-14) revierte esta parte de G3: redondear
        a 1 decimal introducía una diferencia estructural (~0.02% en ktp)
        frente al comparador/Excel, que usan el certificado a su precisión
        completa (P0=101.325 = 1 atm estándar, no una cifra espuria)."""
        seleccionar_camara(dialogo, "N31010")
        assert dialogo.temp_0.text() == str(EQUIPO_N31010["t_cal"])
        assert dialogo.pressure_0.text() == str(EQUIPO_N31010["p_cal"])
        assert dialogo.pressure_0.text() == "101.325"  # no "101.3" -- evidencia concreta de la reversión
        assert dialogo.humr_cal.text() == str(EQUIPO_N31010["h_cal"])

    def test_humedad_distinta_para_otra_camara(self, dialogo):
        seleccionar_camara(dialogo, "TN34001")
        assert dialogo.humr_cal.text() == "50.0"


class TestG4DefaultPulse:
    def test_pulse_marcado_por_defecto(self, dialogo):
        assert dialogo.pulse.isChecked()

    def test_pulse_scan_no_marcado_por_defecto(self, dialogo):
        assert not dialogo.pulse_scan.isChecked()


class TestG5MenuGraficarPerfilesEliminado:
    """Mismo patrón que TestMenuArchivo (K-fix.3, test_calculadora_dosis_ui.py)
    para 'Importar MCC': DialogCalculadoraDosis es un QDialog, no un
    QMainWindow -- no tiene .menuBar(); las acciones viven como atributos de
    instancia creados en crear_menu()."""

    def test_no_existe_accion_graficar_perfiles(self, dialogo):
        assert not hasattr(dialogo, "act_graficar")

    def test_comparar_excel_y_reporte_pdf_siguen_presentes(self, dialogo):
        assert hasattr(dialogo, "act_comparar_excel")
        assert dialogo.act_comparar_excel.text() == "Comparar con Excel TRS-398"
        assert hasattr(dialogo, "act_pdf")
        assert dialogo.act_pdf.text() == "Generar reporte PDF"
