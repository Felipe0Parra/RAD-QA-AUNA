"""K1 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.2): el bloque
"Tipo de Escaneo" de la calculadora se oculta -- indicación directa de la
física jefe. "Pulse" sigue marcado por defecto (G4); los widgets
self.pulse/self.pulse_scan siguen existiendo, con su señal y su pertenencia
al QButtonGroup exclusivo -- se oculta el CONTENEDOR, no los checkboxes.

Opción (b) del plan: una etiqueta de solo lectura avisa cuando el modo
activo no es el default "Pulsed" (caso: cargar un registro histórico en
'Pulse scanned', que usa otros coeficientes ks -- ver
coeficientes_ks_pulse), para que ese dato no quede invisible.

Nota de infraestructura (K-fix.1/Z4): en offscreen sin `.show()`,
`QWidget.isVisible()` exige la cadena de ancestros mapeada en pantalla y da
`False` siempre -- se usa `isHidden()`, que sí refleja el flag explícito de
`setVisible()`.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import data.ManejoDatos.conection as conection_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_N31010 = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                 "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (el diálogo deduce el acelerador)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogo_factory(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": EQUIPO_N31010["model"],
                              "equip_type": EQUIPO_N31010["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [EQUIPO_N31010] if m == EQUIPO_N31010["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: EQUIPO_N31010 if i == EQUIPO_N31010["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(dialogs_mod, "generar_reporte_calibracion", lambda **kw: None)

    def _crear():
        return DialogCalculadoraDosis(energias=[], parent=VentanaIX())

    return _crear


DATOS_BASE = {
    "Fecha": "05/08/2026", "Acelerador": None,
    "equipo_id": EQUIPO_N31010["id"], "Modelo_equipo": EQUIPO_N31010["model"],
    "Numero_serie": str(EQUIPO_N31010["id"]), "factor_calibracion": "5.397",
    "Tamano_campo": "10x10 cm", "Tipo_de_radiacion": "Fotones",
    "Tipo_de_medicion": "SSD",
    "temperatura": "20.0", "presion": "101.325", "Humedad_calibracion": "45.0",
    "temp_clinica": "22.0", "presion_clinica": "101.325", "Humedad_relativa": "48.0",
    "ktp": "1.0", "lectura_Q1": "12.4", "lectura_Q2": "12.4", "lectura_Q3": "12.4",
    "lectura_dosimetro": "12.4", "unidades_monitor": "100", "cociente_ldv1_um": "0.124",
    "Mplus": "12.4", "Lectura_neg_1": "-12.4", "Lectura_neg_2": "-12.4",
    "Lectura_neg_3": "-12.4", "Lectura_neg_prom": "-12.4", "Kpol": "1.0",
    "tension_v1": "400", "tension_v2": "100", "cociente_tensiones": "4.0",
    "lectura_m1": "12.4", "lectura_m2_1": "12.4", "lectura_m2_2": "12.4",
    "lectura_m2_3": "12.4", "lectura_m2": "12.4", "cociente_lecturas": "1.0",
    "a0": "1.0", "a1": "0.0", "a2": "0.0", "ks": "1.0", "Mq": "12.4",
    "Zref": "10.0", "Zmax": "1.5", "Kq_0": "0.99", "Dzref": "1.2",
    "pdd20": "50.0", "pdd10": "100.0", "pddzref": "66.6", "tmrzref": "",
    "dosis_maxima": "1.0", "tpr2010": "0.68", "tension_negativa": "-300",
    "protocolo_trs398": "2000", "r50_medido": "", "pdd_zref_electrones": "",
    "energia": "6mv",
}


def _cargar(d, tipo_escaneo):
    datos = dict(DATOS_BASE, Acelerador=d.acelerador_actual, Tipo_de_escaneo=tipo_escaneo)
    d.cargar_datos_desde_db(datos)
    return d


class TestBloqueOculto:

    def test_bloque_tipo_escaneo_esta_oculto(self, dialogo_factory):
        d = dialogo_factory()
        assert d.escaneo_box.isHidden() is True

    def test_pulse_sigue_marcado_por_defecto(self, dialogo_factory):
        d = dialogo_factory()
        assert d.pulse.isChecked() is True
        assert d.pulse_scan.isChecked() is False

    def test_etiqueta_oculta_por_defecto(self, dialogo_factory):
        d = dialogo_factory()
        assert d.lbl_modo_escaneo_oculto.isHidden() is True


class TestCoeficientesKsSiguenFuncionandoConElBloqueOculto:
    """Protocolo #3: coeficientes_ks_pulse debe seguir devolviendo los
    valores exactos de "pulsados" con el bloque oculto -- no solo "no
    revienta"."""

    def test_coeficientes_pulsados_con_bloque_oculto(self, dialogo_factory):
        d = dialogo_factory()
        assert d.escaneo_box.isHidden() is True
        d.cociente_tensiones.setText("4.0")

        d.coeficientes_ks_pulse()

        from services.dosis_service import DosisService
        esperado = DosisService.obtener_coeficientes_ks("pulsados", 4.0)
        assert (d.a0.text(), d.a1.text(), d.a2.text()) == tuple(str(x) for x in esperado)

    def test_cambiar_a_pulse_scan_cambia_los_coeficientes(self, dialogo_factory):
        """El checkbox oculto sigue siendo funcional -- marcarlo por código
        (como hace cargar_datos_desde_db con un registro histórico) cambia
        el modo de coeficientes, aunque no se vea en pantalla."""
        d = dialogo_factory()
        d.cociente_tensiones.setText("4.0")
        d.pulse_scan.setChecked(True)  # exclusivo: desmarca pulse

        assert d.pulse.isChecked() is False
        from services.dosis_service import DosisService
        esperado = DosisService.obtener_coeficientes_ks("pulsados_y_barridos", 4.0)
        assert (d.a0.text(), d.a1.text(), d.a2.text()) == tuple(str(x) for x in esperado)


class TestCampoNoFaltanteEnValidacionF3:

    def test_tipo_de_escaneo_no_se_reporta_como_faltante(self, dialogo_factory):
        """_campos_faltantes recibe el MISMO dict que guardar_db construye
        (línea "Tipo_de_escaneo": "Pulsed" if self.pulse.isChecked() else
        "Pulse scanned") -- con el bloque oculto y "Pulse" marcado por
        defecto (G4), la clave nunca queda vacía."""
        d = dialogo_factory()
        datos = {"Tipo_de_escaneo": "Pulsed" if d.pulse.isChecked() else "Pulse scanned"}
        assert "Tipo_de_escaneo" not in d._campos_faltantes(datos)


class TestEtiquetaModoEscaneoHistorico:
    """Opción (b): un registro guardado en 'Pulse scanned' no debe quedar
    invisible solo porque el bloque está oculto."""

    def test_cargar_pulse_scanned_muestra_la_etiqueta(self, dialogo_factory):
        d = _cargar(dialogo_factory(), "Pulse scanned")

        assert d.pulse_scan.isChecked() is True
        assert d.lbl_modo_escaneo_oculto.isHidden() is False
        assert d.lbl_modo_escaneo_oculto.text() == "Tipo de escaneo: Pulse-Scanned"

    def test_cargar_pulsed_mantiene_la_etiqueta_oculta(self, dialogo_factory):
        d = _cargar(dialogo_factory(), "Pulsed")

        assert d.pulse.isChecked() is True
        assert d.lbl_modo_escaneo_oculto.isHidden() is True

    def test_cargar_pulse_scanned_y_luego_pulsed_oculta_de_nuevo(self, dialogo_factory):
        """El grupo exclusivo dispara toggled(False) en pulse_scan al
        marcar pulse -- la etiqueta debe reevaluarse y ocultarse."""
        d = dialogo_factory()
        _cargar(d, "Pulse scanned")
        assert d.lbl_modo_escaneo_oculto.isHidden() is False

        _cargar(d, "Pulsed")
        assert d.lbl_modo_escaneo_oculto.isHidden() is True


class TestResetASFabricaSigueDejandoPulseMarcado:
    """Protocolo #5: _resetear_checks_a_fabrica (Z4) no se toca, pero debe
    seguir dejando pulse marcado y pulse_scan desmarcado con el bloque
    oculto -- y la etiqueta debe volver a ocultarse."""

    def test_nuevo_calculo_tras_pulse_scanned_deja_pulse_por_defecto(self, dialogo_factory):
        d = _cargar(dialogo_factory(), "Pulse scanned")
        assert d.lbl_modo_escaneo_oculto.isHidden() is False

        d.iniciar_nuevo_calculo()

        assert d.pulse.isChecked() is True
        assert d.pulse_scan.isChecked() is False
        assert d.lbl_modo_escaneo_oculto.isHidden() is True
