"""Fase H1.1 (auditoría 2026-07-14) -- electrones auto-marca SSD.

Hallazgo (PLAN_FASE_H_AUDITORIA_Y_REVISION_14-07.md, sección 1.5/H1.1):
`geometry_box` (el checkbox SSD) solo es visible con Fotones
(dialogs.py: `fotones.toggled.connect(lambda c: self.geometry_box.setVisible(c))`),
pero "Tipo_de_medicion" está en `_CAMPOS_SIEMPRE_REQUERIDOS` y sale de
`self.SSD.isChecked()` -- para electrones el físico no podía ver el
checkbox que el guardado exige, así que quedaba en None y bloqueaba el
cierre de la calculadora (bug real, visto en producción). TRS-398 Rev.1
Tabla 19: la dosimetría de referencia de electrones es SIEMPRE SSD=100 cm,
así que marcarlo por código al elegir electrones es correcto, no una
imposición arbitraria.
"""
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import services.dosis_service as dosis_service_mod
import data.ManejoDatos.conection as conection_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_ELECTRONES_ORO = {"id": 201, "equip_type": "Cámara de ionización", "model": "TN34001",
                         "serie": "001069", "calibr_fact": 0.08563, "t_cal": 20.0,
                         "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en 'IX' (única máquina con electrones)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    # HI-3: dosis_service.py ahora importa el MÓDULO conection (no la función
    # por valor) -- basta parchear conection_mod.ruta_base_datos.
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


@pytest.fixture
def dialogo(app, bd_temporal, monkeypatch):
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": EQUIPO_ELECTRONES_ORO["model"],
                               "equip_type": EQUIPO_ELECTRONES_ORO["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [EQUIPO_ELECTRONES_ORO] if m == EQUIPO_ELECTRONES_ORO["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: EQUIPO_ELECTRONES_ORO if i == EQUIPO_ELECTRONES_ORO["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(dialogs_mod, "generar_reporte_calibracion", lambda **kwargs: None)

    d = DialogCalculadoraDosis(energias=["6mv"], parent=VentanaIX())
    yield d
    d.deleteLater()


def llenar_electrones_completo(d, marcar_ssd_manual=False):
    """Llena TODOS los campos que guardar_db exige para electrones (10x10).

    marcar_ssd_manual=False (default): a propósito NO toca d.SSD -- así el
    test de guardado verifica que quede marcado SOLO por el auto-marcado de
    H1.1, sin que el físico tenga que interactuar con un checkbox invisible.
    """
    idx = d.combo_modelos.findData(EQUIPO_ELECTRONES_ORO["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.electrones.setChecked(True)
    if marcar_ssd_manual:
        d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.combo_fieldsize.setCurrentIndex(0)  # 10x10

    d.temp.setText("21.9")
    d.pressure.setText("85.43")
    d.humr_cal.setText("45.0")
    d.humedad_r.setText("48.0")
    for campo in (d.lDV1_1, d.lDV1_2, d.lDV1_3):
        campo.setText("21.36")
    d.unidades_monitor.setText("200")
    for campo in (d.Mminus1, d.Mminus2, d.Mminus3):
        campo.setText("-20.93")
    d.tension_v1.setText("200")
    d.tension_v2.setText("50")
    for campo in (d.lect_m2_1, d.lect_m2_2, d.lect_m2_3):
        campo.setText("20.52")
    d.R50.setText("5.127")
    d.pddzrefE.setText("99.3")
    d.Zref.setText("3.0")
    d.Zmax.setText("2.7")
    return d


class TestElectronesAutoMarcaSSD:
    def test_marcar_electrones_marca_ssd_automaticamente(self, dialogo):
        assert dialogo.SSD.isChecked() is False
        dialogo.electrones.setChecked(True)
        assert dialogo.SSD.isChecked() is True

    def test_marcar_fotones_no_marca_ssd_por_si_solo(self, dialogo):
        """Fotones solo hace visible el geometry_box; el físico sigue
        eligiendo SSD a mano en ese caso (no cambia con H1.1)."""
        dialogo.fotones.setChecked(True)
        assert dialogo.SSD.isChecked() is False

    def test_volver_a_fotones_tras_electrones_deja_ssd_marcado(self, dialogo):
        """QButtonGroup exclusivo: una vez marcado, no se puede desmarcar
        por código (quirk documentado en test_calculadora_dosis_g1.py) --
        SSD es también el caso normal de fotones, así que es aceptable que
        quede marcado al volver."""
        dialogo.electrones.setChecked(True)
        dialogo.fotones.setChecked(True)
        assert dialogo.SSD.isChecked() is True

    def test_guardar_electrones_sin_tocar_ssd_a_mano(self, dialogo):
        d = llenar_electrones_completo(dialogo, marcar_ssd_manual=False)
        assert d.guardar_db() is True

    def test_tipo_de_medicion_queda_ssd_en_bd_sin_tocar_ssd_a_mano(self, dialogo):
        d = llenar_electrones_completo(dialogo, marcar_ssd_manual=False)
        assert d.guardar_db() is True

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, d.acelerador_actual)
        assert datos_bd is not None
        assert datos_bd["Tipo_de_medicion"] == "SSD"
