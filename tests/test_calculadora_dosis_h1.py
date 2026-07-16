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
    # I3: Zref ya NO se teclea -- se autollena de la cadena R50 -> Q(R50) ->
    # zref (0.6*R50,w - 0.1). Que el guardado pase sin tocarlo es parte de
    # lo que estos tests verifican ahora.
    d.Zmax.setText("2.7")
    return d


class TestElectronesAutoMarcaSSD:
    def test_marcar_electrones_marca_ssd_automaticamente(self, dialogo):
        assert dialogo.SSD.isChecked() is False
        dialogo.electrones.setChecked(True)
        assert dialogo.SSD.isChecked() is True

    def test_marcar_fotones_tambien_marca_ssd(self, dialogo):
        """I6 (pedido del físico 16-07, INVIERTE el contrato anterior de
        H1.1): fotones también nace con SSD marcado -- es la geometría de
        rutina -- pero el box queda VISIBLE para que el físico lo constate
        (a diferencia de electrones, donde el box permanece oculto)."""
        dialogo.fotones.setChecked(True)
        assert dialogo.SSD.isChecked() is True
        assert not dialogo.geometry_box.isHidden()
        # y con I2, el PDD de fotones aparece de una vez (lo exige la
        # dosis máxima en geometría SSD)
        assert not dialogo.pddzref.isHidden()

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


class TestI2PddUnico:
    """I2 (PLAN_FASE_I, 2026-07-16): un solo campo PDD(Zref) visible a la vez.

    El auto-SSD de H1.1 disparaba `SSD.toggled -> mostrar_pdd` (PDD de
    FOTONES) a la vez que `electrones.toggled -> mostrar_pddE` (PDD de
    electrones); con etiquetas idénticas, el físico veía la casilla
    "duplicada" (reporte 16-07). `_actualizar_visibilidad_pdd` deriva ahora
    ambos campos del estado completo. Se usa isHidden() y no isVisible()
    (convención K-fix.1: isVisible exige la cadena de ancestros mapeada,
    falsa en offscreen sin .show()).
    """

    def test_electrones_muestra_solo_pdd_electrones(self, dialogo):
        """El caso del físico: electrones no debe mostrar el PDD de fotones."""
        dialogo.electrones.setChecked(True)

        assert not dialogo.pddzrefE.isHidden()
        assert not dialogo.pdd_zrefE.isHidden()
        assert dialogo.pddzref.isHidden(), "PDD de fotones visible en electrones (duplicado H1.1)"
        assert dialogo.pdd_zref.isHidden()
        # H1.1 no debe regresar: SSD sigue auto-marcado (guardado requiere)
        assert dialogo.SSD.isChecked() is True

    def test_fotones_con_ssd_muestra_solo_pdd_fotones(self, dialogo):
        dialogo.fotones.setChecked(True)
        dialogo.SSD.setChecked(True)

        assert not dialogo.pddzref.isHidden()
        assert not dialogo.pdd_zref.isHidden()
        assert dialogo.pddzrefE.isHidden()
        assert dialogo.pdd_zrefE.isHidden()

    def test_alternar_haz_no_deja_residuos(self, dialogo):
        """E -> F -> E: en cada estado hay UN solo PDD visible (SSD queda
        marcado tras pasar por electrones -- quirk documentado de H1.1 -- y
        aun así el PDD de fotones no debe filtrarse al estado de electrones).
        """
        dialogo.electrones.setChecked(True)
        dialogo.fotones.setChecked(True)  # SSD sigue marcado (H1.1)
        assert not dialogo.pddzref.isHidden()
        assert dialogo.pddzrefE.isHidden()

        dialogo.electrones.setChecked(True)
        assert not dialogo.pddzrefE.isHidden()
        assert dialogo.pddzref.isHidden()

    def test_etiquetas_diferenciadas(self, dialogo):
        """Nunca más dos campos con el mismo nombre en pantalla."""
        assert dialogo.pdd_zref.text() != dialogo.pdd_zrefE.text()
        assert "FOTONES" in dialogo.pdd_zref.text()
        assert "ELECTRONES" in dialogo.pdd_zrefE.text()


class TestI3ZrefElectrones:
    """I3 (PLAN_FASE_I, 2026-07-16): en electrones, el Zref de Resultados
    Finales se autollena desde la cadena R50 -> Q(R50) -> zrefR50 y se oculta
    (era re-teclear la misma cantidad, reporte del físico 16-07). En fotones
    sigue visible y manual.
    """

    def test_oculto_en_electrones_visible_en_fotones(self, dialogo):
        assert not dialogo.Zref.isHidden()  # estado inicial: visible
        dialogo.electrones.setChecked(True)
        assert dialogo.Zref.isHidden()
        assert dialogo.lbl_zref.isHidden()
        dialogo.fotones.setChecked(True)
        assert not dialogo.Zref.isHidden()
        assert not dialogo.lbl_zref.isHidden()

    def test_se_autollena_del_r50(self, dialogo):
        dialogo.electrones.setChecked(True)
        dialogo.R50.setText("5.127")
        assert dialogo.zrefR50.text() != ""
        assert dialogo.Zref.text() == dialogo.zrefR50.text()

    def test_r50_antes_de_marcar_electrones_tambien_sincroniza(self, dialogo):
        """La sincronización no depende del orden R50/tipo de haz."""
        dialogo.R50.setText("5.127")
        dialogo.electrones.setChecked(True)
        assert dialogo.Zref.text() == dialogo.zrefR50.text() != ""

    def test_guardar_electrones_sin_teclear_zref(self, dialogo):
        """El flujo completo guarda sin que el físico toque Zref, y la BD
        recibe el valor calculado (la validación F3 sigue completa: nunca
        campo-requerido-invisible)."""
        d = llenar_electrones_completo(dialogo)
        assert d.Zref.text() == d.zrefR50.text() != ""
        assert d.guardar_db() is True

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(
            fecha, d.acelerador_actual)
        assert datos_bd is not None
        assert str(datos_bd["Zref"]) == d.zrefR50.text()

    def test_volver_a_fotones_limpia_el_zref_de_electrones(self, dialogo):
        """Un zref de electrones (~1-3 g/cm²) no es un zref de fotones: al
        cambiar de haz el valor autollenado se limpia para que el físico
        ingrese el suyo (10.0 / 5.0)."""
        dialogo.electrones.setChecked(True)
        dialogo.R50.setText("5.127")
        assert dialogo.Zref.text() != ""

        dialogo.fotones.setChecked(True)
        assert dialogo.Zref.text() == ""
        assert not dialogo.Zref.isHidden()
