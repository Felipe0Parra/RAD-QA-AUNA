"""Z4 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): un cálculo cargado se
VE, no se edita -- petición textual del físico (anotación 1, handoff
05-08): *"bloquear la edicion de estos datos cargados, depronto anadir un
boton de limpiar y habilitar la edicion, pero que el boton inmediatamente lo
saque a uno de ese registro como si apenas estuviera llenando uno nuevo
porque la intencion es no modificar esos valores y mucho menos usar esa
carga para llenar mas rapido un nuevo calculo."*

Nota de infraestructura de test (diagnosticada con un subagente Opus, según
instrucción del usuario): en offscreen, sin `.show()`, `QWidget.isVisible()`
exige toda la cadena de ancestros mapeada en pantalla y da `False` SIEMPRE,
sin importar el flag real puesto con `setVisible()` -- mismo patrón ya
documentado en K-fix.1 (2026-07-09). Se usa `isHidden()` en su lugar, que sí
refleja el flag explícito.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

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


def _cargar_registro_completo(d):
    """Simula cargar un cálculo guardado (vía _cargar_calculo_del_mes,
    B3-e) con TODOS los campos llenos -- el escenario real que dispara
    _entrar_modo_consulta. QualityR50/zrefR50 se rellenan a mano después:
    cargar_datos_desde_db no los restaura directo desde el dict (no los
    persiste guardar_db), pero si quedaron con texto de una interacción
    previa del físico, deben limpiarse igual al cargar/al iniciar nuevo."""
    datos = {
        "Fecha": "05/08/2026", "Acelerador": d.acelerador_actual,
        "equipo_id": EQUIPO_N31010["id"], "Modelo_equipo": EQUIPO_N31010["model"],
        "Numero_serie": str(EQUIPO_N31010["id"]), "factor_calibracion": "5.397",
        "Tamano_campo": "10x10 cm", "Tipo_de_radiacion": "Fotones",
        "Tipo_de_escaneo": "Pulsed", "Tipo_de_medicion": "SSD",
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
    d.cargar_datos_desde_db(datos)
    d.QualityR50.setText("0.98")
    d.zrefR50.setText("3.0")
    return d


class TestModoConsultaTrasCargar:

    def test_campos_en_solo_lectura_tras_cargar(self, dialogo_factory):
        d = _cargar_registro_completo(dialogo_factory())

        for nombre in d._CAMPOS_TEXTO_CALCULO:
            assert getattr(d, nombre).isReadOnly(), f"{nombre} debía quedar en solo lectura"
        for nombre in d._COMBOS_CALCULO:
            assert not getattr(d, nombre).isEnabled(), f"{nombre} debía quedar deshabilitado"
        for nombre in d._CHECKS_CALCULO:
            assert not getattr(d, nombre).isEnabled(), f"{nombre} debía quedar deshabilitado"

    def test_aceptar_y_cerrar_deshabilitado(self, dialogo_factory):
        d = _cargar_registro_completo(dialogo_factory())

        assert d.btn_ok.isEnabled() is False

    def test_boton_nuevo_calculo_visible(self, dialogo_factory):
        d = _cargar_registro_completo(dialogo_factory())

        assert d.btn_nuevo_calculo.isHidden() is False


class TestNuevoCalculoLimpiaTodo:

    def test_todos_los_campos_de_texto_quedan_vacios_y_en_estado_de_fabrica(self, dialogo_factory):
        d = _cargar_registro_completo(dialogo_factory())
        assert d.tpr2010.text() == "0.68"  # confirma que sí había algo que limpiar
        assert d.QualityR50.text() == "0.98"
        assert d.zrefR50.text() == "3.0"

        d.iniciar_nuevo_calculo()

        for nombre in d._CAMPOS_TEXTO_CALCULO:
            campo = getattr(d, nombre)
            assert campo.text() == "", f"{nombre} debía quedar vacío tras Nuevo cálculo"
            esperado = nombre in d._CAMPOS_SOLO_LECTURA_SIEMPRE
            assert campo.isReadOnly() is esperado, (
                f"{nombre} debía volver a su estado de fábrica (readOnly={esperado})")

    def test_la_lista_de_solo_lectura_coincide_con_un_dialogo_recien_abierto(self, dialogo_factory):
        """Un diálogo recién construido YA está en estado de fábrica -- sus
        campos readOnly deben ser exactamente _CAMPOS_SOLO_LECTURA_SIEMPRE,
        ni más ni menos. Si esto cambiara silenciosamente (alguien agrega o
        quita un setReadOnly(True) en __init__), este test lo detecta."""
        d = dialogo_factory()

        reales = {n for n in d._CAMPOS_TEXTO_CALCULO if getattr(d, n).isReadOnly()}

        assert reales == set(d._CAMPOS_SOLO_LECTURA_SIEMPRE)

    def test_el_inventario_cubre_todos_los_qlineedit_del_dialogo(self, dialogo_factory):
        """Tripwire: si se agrega un QLineEdit nuevo al formulario de
        cálculo y no se suma a _CAMPOS_TEXTO_CALCULO, Nuevo cálculo lo
        dejaría con datos del cálculo anterior -- exactamente el hueco que
        tenían QualityR50/zrefR50 antes de este commit."""
        d = dialogo_factory()

        reales = {n for n, w in vars(d).items() if isinstance(w, QLineEdit)}

        faltantes = reales - set(d._CAMPOS_TEXTO_CALCULO)
        assert faltantes == set(), f"QLineEdit sin cubrir en _CAMPOS_TEXTO_CALCULO: {faltantes}"

    def test_combos_y_checks_vuelven_a_habilitarse(self, dialogo_factory):
        """OJO: solo _COMBOS_RESET_EXPLICITO debe quedar habilitado.
        combo_series NO -- on_modelo_cambiado lo deja vacío y deshabilitado
        al restablecer combo_modelos al índice 0 (mismo estado que un
        diálogo recién abierto, comentario ya existente en
        iniciar_nuevo_calculo). Afirmar que combo_series también queda
        habilitado sería falso -- ver
        test_la_lista_de_solo_lectura_coincide_con_un_dialogo_recien_abierto
        para el mismo criterio aplicado a los campos de texto."""
        d = _cargar_registro_completo(dialogo_factory())

        d.iniciar_nuevo_calculo()

        for nombre in d._COMBOS_RESET_EXPLICITO:
            assert getattr(d, nombre).isEnabled(), f"{nombre} debía volver a estar habilitado"
        assert d.combo_series.isEnabled() is False
        assert d.combo_series.count() == 0
        for nombre in d._CHECKS_CALCULO:
            assert getattr(d, nombre).isEnabled(), f"{nombre} debía volver a estar habilitado"

    def test_checks_vuelven_al_default_de_fabrica(self, dialogo_factory):
        d = _cargar_registro_completo(dialogo_factory())

        d.iniciar_nuevo_calculo()

        assert d.fotones.isChecked() is False
        assert d.electrones.isChecked() is False
        assert d.pulse.isChecked() is True  # default de fábrica (G4)
        assert d.pulse_scan.isChecked() is False
        assert d.SSD.isChecked() is False

    def test_reinicia_energia_calculo_y_protocolo(self, dialogo_factory):
        """energia_calculo NO se restaura al cargar (metadato de B3.3, sin
        widget -- ver ALLOWLIST_NO_RESTAURADO de Z2), así que el escenario
        real a proteger es: se cargó un cálculo, el físico pulsó un botón
        de energía (emitir_dosis) o cambió el protocolo ANTES de decidir
        empezar de cero -- Nuevo cálculo debe limpiar eso también."""
        d = _cargar_registro_completo(dialogo_factory())
        d.energia_calculo = "15mv"  # simula que se había pulsado un botón de energía
        d.combo_protocolo.setCurrentIndex(1)  # simula que se había cambiado a rev1

        d.iniciar_nuevo_calculo()

        assert d.energia_calculo is None
        assert d.combo_protocolo.currentData() == "2000"

    def test_equipo_id_y_flag_de_tpr_manual_se_reinician(self, dialogo_factory):
        d = _cargar_registro_completo(dialogo_factory())
        assert d.equipo_id == EQUIPO_N31010["id"]
        assert d._tpr2010_editado_manualmente is True

        d.iniciar_nuevo_calculo()

        assert d.equipo_id is None
        assert d._tpr2010_editado_manualmente is False

    def test_boton_aceptar_vuelve_a_habilitarse_y_nuevo_calculo_se_oculta(self, dialogo_factory):
        d = _cargar_registro_completo(dialogo_factory())

        d.iniciar_nuevo_calculo()

        assert d.btn_ok.isEnabled() is True
        assert d.btn_nuevo_calculo.isHidden() is True


class TestDialogoNuevoSigueEditable:
    """Anti-regresión: un diálogo recién abierto (sin cargar nada) no debe
    quedar afectado por _entrar_modo_consulta -- solo se dispara al cargar."""

    def test_dialogo_recien_abierto_no_esta_en_modo_consulta(self, dialogo_factory):
        d = dialogo_factory()

        assert d.btn_ok.isEnabled() is True
        assert d.btn_nuevo_calculo.isHidden() is True
        for nombre in d._CAMPOS_TEXTO_CALCULO:
            esperado = nombre in d._CAMPOS_SOLO_LECTURA_SIEMPRE
            assert getattr(d, nombre).isReadOnly() is esperado
