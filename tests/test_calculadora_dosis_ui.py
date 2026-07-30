"""Test de integración de DialogCalculadoraDosis (Fase D2).

Maneja el diálogo REAL en modo offscreen simulando al físico: selecciona
cámara y serie, llena los campos en orden y verifica que la cascada de
señales produce la dosis correcta al final. Cubre los dos escenarios D2:

1. Cámara CON coeficientes kQ (N31010): flujo de fotones completo,
   kQ automático desde TPR20,10 y dosis máxima al final.
2. Cámara SIN coeficientes (N31014): aviso claro al seleccionarla y,
   crucialmente, el kQ ingresado a mano NO se borra al teclear el TPR
   (antes de D2.1 sí se borraba: la interpolación fallida hacía clear()).

EquiposService y QMessageBox van parcheados: sin base de datos real y sin
diálogos modales que bloqueen la corrida.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel

import ui.paginasGuia.dialogs as dialogs_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_N31010 = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                 "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}
EQUIPO_N31014 = {"id": 7, "equip_type": "Cámara de ionización", "model": "N31014",
                 "serie": "0453", "calibr_fact": 2.404, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}
EQUIPO_N31022 = {"id": 99, "equip_type": "Cámara de ionización", "model": "N31022",
                 "serie": "3344", "calibr_fact": 3.100, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}
EQUIPO_N34001 = {"id": 55, "equip_type": "Cámara de ionización", "model": "N34001",
                 "serie": "1069", "calibr_fact": 0.08563, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}
EQUIPO_N30013 = {"id": 12, "equip_type": "Cámara de ionización", "model": "N30013",
                 "serie": "2123", "calibr_fact": 0.306, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}
EQUIPOS = (EQUIPO_N31010, EQUIPO_N31014, EQUIPO_N31022, EQUIPO_N34001, EQUIPO_N30013)


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (el diálogo deduce el acelerador)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogo(app, monkeypatch):
    avisos = []

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
        monkeypatch.setattr(
            dialogs_mod.QMessageBox, tipo,
            staticmethod(lambda *a, _t=tipo, **k: avisos.append((_t,) + a[1:3])))

    d = DialogCalculadoraDosis(energias=[], parent=VentanaIX())
    d.avisos = avisos
    yield d
    d.deleteLater()


def seleccionar_camara(d, modelo, con_serie=True):
    idx = d.combo_modelos.findData(modelo)
    assert idx >= 0, f"{modelo} no está en el combo"
    d.combo_modelos.setCurrentIndex(idx)
    if con_serie:
        d.combo_series.setCurrentIndex(1)  # única serie del modelo parcheado


def seleccionar_protocolo(d, codigo):
    idx = d.combo_protocolo.findData(codigo)
    assert idx >= 0, f"protocolo {codigo!r} no está en el selector"
    d.combo_protocolo.setCurrentIndex(idx)


class TestFlujoFotonesConDatos:
    """Cadena completa con N31010, la cámara con coeficientes kQ cargados."""

    def test_cadena_completa_hasta_dosis_maxima(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31010")

        # Selección de serie carga la calibración del certificado
        assert d.visualize_calib.text() == "5.397"
        assert d.temp_0.text() == "20.0"
        # H3.6 (auditoría 2026-07-14, revierte G3): se muestra el valor
        # CRUDO del certificado (101.325 = 1 atm estándar, no una cifra
        # espuria) -- redondear a 1 decimal introducía una diferencia
        # estructural frente al comparador/Excel (ver PLAN_FASE_H).
        assert d.pressure_0.text() == "101.325"
        assert d.humr_cal.text() == "50.0"
        assert not d.avisos, f"no debía haber avisos para N31010: {d.avisos}"

        d.fotones.setChecked(True)
        d.SSD.setChecked(True)
        d.pulse.setChecked(True)

        # Condiciones clínicas → kTP (valor pineado en la suite D1)
        # H3.6: ktp se calcula con P0=101.325 crudo (antes 101.3 redondeado)
        # -- coincide exacto con la columna "App" del comparador Excel.
        d.temp.setText("22.0")
        d.pressure.setText("101.325")
        assert d.ktp.text() == "1.0068"

        # Lecturas del dosímetro → promedio, Mplus y M1
        for campo in (d.lDV1_1, d.lDV1_2, d.lDV1_3):
            campo.setText("12.437")
        assert d.lDV1_prom.text() == "12.437"
        assert d.Mplus.text() == "12.437"
        assert d.lect_m1.text() == "12.437"

        # Unidades monitor → cociente lectura/UM
        d.unidades_monitor.setText("100")
        assert d.cociente.text() == "0.12437"

        # Polaridad: lecturas negativas simétricas → kpol = 1
        for campo in (d.Mminus1, d.Mminus2, d.Mminus3):
            campo.setText("-12.437")
        assert d.Mminus.text() == "-12.437"
        assert d.Kpol.text() == "1.0"

        # Recombinación: V1/V2 = 4 → coeficientes de la tabla pulsados
        d.tension_v1.setText("400")
        d.tension_v2.setText("100")
        assert d.cociente_tensiones.text() == "4.0"
        assert (d.a0.text(), d.a1.text(), d.a2.text()) == ("1.022", "-0.3632", "0.3413")

        # M1/M2 = 1 → ks = a0+a1+a2 (redondeo de tabla: 1.0001)
        for campo in (d.lect_m2_1, d.lect_m2_2, d.lect_m2_3):
            campo.setText("12.437")
        assert d.lect_m2.text() == "12.437"
        assert d.cociente_lecturas.text() == "1.0"
        assert d.ks.text() == "1.0001"

        # Mq = cociente·ktp·kpol·ks
        assert d.MQvar.text() == "0.125228"

        # TPR20,10 = 0.68 → kQ automático interpolado de KQ_TPR_TABLE
        d.tpr2010.setText("0.68")
        assert d.Kq_0.text() == "0.99"

        # D(zref) = N_D,w · Mq · kQ y dosis máxima vía PDD
        assert d.Dzref.text() == "0.669097"
        d.pddzref.setText("66.6")
        assert d.dosis_maxima.text() == "1.0046502"

    def test_borrar_tpr_limpia_el_kq_automatico(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31010")
        d.fotones.setChecked(True)
        d.tpr2010.setText("0.68")
        assert d.Kq_0.text() == "0.99"
        d.tpr2010.clear()
        assert d.Kq_0.text() == ""  # kQ auto pendiente, sin valor fantasma


class TestCamaraSinDatosKq:
    """N31014 está activa en la BD pero sin fila en KQ_TPR_TABLE (guarda D2)."""

    def test_avisa_al_seleccionar_modelo(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31014", con_serie=False)
        avisos_kq = [a for a in d.avisos if "coeficientes kQ" in a[1]]
        assert len(avisos_kq) == 1, f"avisos: {d.avisos}"
        assert "N31014" in avisos_kq[0][2]
        assert "manualmente" in avisos_kq[0][2]
        assert "manualmente" in d.Kq_0.placeholderText()

    def test_aviso_indica_marcar_fotones_si_kq0_aun_no_es_visible(self, dialogo):
        """Bug reportado en pruebas Windows 2026-07-09: el aviso decía
        'ingréselo en el campo correspondiente' pero Kq_0 nace oculto
        (solo se muestra al marcar 'Fotones') -> el físico no encontraba
        ninguna casilla habilitada. Sin marcar Fotones todavía, el mensaje
        debe decir explícitamente que hay que marcarlo.

        Nota: se usa isHidden(), no isVisible() -- este último exige que
        TODA la cadena de ancestros esté mapeada en pantalla (siempre falso
        aquí, porque el diálogo de test nunca llama a .show())."""
        d = dialogo
        assert d.Kq_0.isHidden()  # todavía no se marcó "Fotones"
        seleccionar_camara(d, "N31014", con_serie=False)
        avisos_kq = [a for a in d.avisos if "coeficientes kQ" in a[1]]
        assert len(avisos_kq) == 1
        assert "Fotones" in avisos_kq[0][2]

    def test_aviso_no_pide_marcar_fotones_si_kq0_ya_es_visible(self, dialogo):
        """Con 'Fotones' ya marcado (Kq_0 visible), el aviso vuelve al
        mensaje original -- no hace falta redirigir a un campo que el
        físico ya tiene delante."""
        d = dialogo
        d.fotones.setChecked(True)
        assert not d.Kq_0.isHidden()
        seleccionar_camara(d, "N31014", con_serie=False)
        avisos_kq = [a for a in d.avisos if "coeficientes kQ" in a[1]]
        assert len(avisos_kq) == 1
        assert "Fotones" not in avisos_kq[0][2]
        assert "manualmente" in avisos_kq[0][2]

    def test_kq_manual_sobrevive_al_teclear_tpr(self, dialogo):
        """El bug corregido en D2.1: antes, cada tecla en TPR20,10 disparaba
        una interpolación fallida (KeyError) que borraba el kQ manual."""
        d = dialogo
        seleccionar_camara(d, "N31014", con_serie=False)
        d.fotones.setChecked(True)
        d.Kq_0.setText("0.985")
        d.tpr2010.setText("0.68")
        assert d.Kq_0.text() == "0.985"

    def test_kq_electrones_manual_sobrevive_al_teclear_r50(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31014", con_serie=False)
        d.electrones.setChecked(True)
        d.Kq0r50_widget.setText("0.912")
        d.R50.setText("4.0")
        assert d.Kq0r50_widget.text() == "0.912"

    def test_al_volver_a_camara_con_datos_se_restaura_el_flujo(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31014", con_serie=False)
        seleccionar_camara(d, "N31010")
        d.fotones.setChecked(True)
        assert "manualmente" not in d.Kq_0.placeholderText()
        d.tpr2010.setText("0.68")
        assert d.Kq_0.text() == "0.99"


def _llenar_hasta_dosis_maxima_n31010(d):
    """Reproduce el mismo flujo de TestFlujoFotonesConDatos hasta obtener
    dosis_maxima='1.0046502' -- reusado para probar emitir_dosis (F2).
    H3.6 (auditoría 2026-07-14): p_cal se muestra/calcula con el valor
    crudo del certificado (101.325) -- ver test_cadena_completa_hasta_dosis_maxima."""
    seleccionar_camara(d, "N31010")
    d.fotones.setChecked(True)
    d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.temp.setText("22.0")
    d.pressure.setText("101.325")
    for campo in (d.lDV1_1, d.lDV1_2, d.lDV1_3):
        campo.setText("12.437")
    d.unidades_monitor.setText("100")
    for campo in (d.Mminus1, d.Mminus2, d.Mminus3):
        campo.setText("-12.437")
    d.tension_v1.setText("400")
    d.tension_v2.setText("100")
    for campo in (d.lect_m2_1, d.lect_m2_2, d.lect_m2_3):
        campo.setText("12.437")
    d.tpr2010.setText("0.68")
    d.pddzref.setText("66.6")
    assert d.dosis_maxima.text() == "1.0046502"
    return d


class TestEmitirDosisFormularioMensual:
    """F2 (auditoría 2026-07-10): corrige H-F1 -- emitir_dosis calculaba
    '1 - dosis_maxima' (unidad y signo equivocados; el campo destino del
    formulario mensual espera cGy/MU). La fórmula correcta es
    'dosis_maxima * 100' (dosis_maxima está en Gy/MU)."""

    def test_valor_emitido_es_dosis_por_100_no_1_menos_dosis(self, dialogo):
        d = _llenar_hasta_dosis_maxima_n31010(dialogo)
        emitidos = []
        d.dosis_asignada.connect(lambda e, v: emitidos.append((e, v)))
        d.emitir_dosis("6mv")
        assert emitidos == [("6mv", 100.46502)]
        # el bug viejo habría emitido 1 - 1.0046502 = -0.0046502
        assert emitidos[0][1] > 0

    def test_mensaje_de_exito_usa_cgy_um(self, dialogo, monkeypatch):
        import ui.paginasGuia.dialogs as dialogs_mod
        mensajes = []
        monkeypatch.setattr(
            dialogs_mod.QMessageBox, "information",
            staticmethod(lambda *a, **k: mensajes.append(a[2])))
        d = _llenar_hasta_dosis_maxima_n31010(dialogo)
        d.emitir_dosis("6mv")
        assert mensajes and "cGy/MU" in mensajes[0]
        assert "Gy/MU" not in mensajes[0].replace("cGy/MU", "")

    def test_dosis_no_calculada_avisa_y_no_emite(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31010")  # dosis_maxima nunca se llena
        emitidos = []
        d.dosis_asignada.connect(lambda e, v: emitidos.append((e, v)))
        d.emitir_dosis("6mv")
        assert not emitidos
        assert any(a[0] == "warning" for a in d.avisos)


class TestCamaraN30013YaNoAvisaSinDatos:
    """E6 (auditoría 2026-07-10): antes del alias, N30013 caía en esta misma
    clase (TestCamaraSinDatosKq) -- disparaba el aviso "sin coeficientes kQ"
    pese a que la fila SÍ existe en la tabla bajo la clave "30013". Verificado
    end-to-end contra la hoja real de Mayo/2024 (serie 2123): 7/7 verdes."""

    def test_no_avisa_al_seleccionar(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N30013")
        avisos_kq = [a for a in d.avisos if "coeficientes kQ" in a[1]]
        assert not avisos_kq, f"N30013 ya no debería avisar, pero: {avisos_kq}"
        assert "manualmente" not in d.Kq_0.placeholderText()

    def test_kq_automatico_desde_tpr(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N30013")
        d.fotones.setChecked(True)
        d.tpr2010.setText("0.6707")
        assert d.Kq_0.text() == "0.9912"


class TestSelectorProtocolo:
    """Fase K4: selector TRS-398 (2000/Rev.1) sobre el diálogo real."""

    def test_protocolo_default_es_2000(self, dialogo):
        assert dialogo.combo_protocolo.currentData() == "2000"

    def test_etiquetas_del_selector_sin_provisional_y_con_2000_2005(self, dialogo):
        """El usuario reportó (2026-07-09) que la palabra "provisional" no
        aportaba (no se aprecia diferencia real al cambiar de protocolo,
        ambos son opciones igual de válidas) y que el PDF de la TRS-398
        más antigua que tiene fechada dice 2005, no 2000 (protocolo
        original en inglés de 2000; traducción española oficial de 2005)."""
        d = dialogo
        idx_2000 = d.combo_protocolo.findData("2000")
        idx_rev1 = d.combo_protocolo.findData("rev1")
        assert d.combo_protocolo.itemText(idx_2000) == "TRS-398 (2000/2005)"
        assert d.combo_protocolo.itemText(idx_rev1) == "TRS-398 Rev.1 (2024)"
        assert "provisional" not in d.combo_protocolo.itemText(idx_rev1).lower()

    def test_n31010_cambia_de_2000_a_rev1_y_vuelve(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31010")
        d.fotones.setChecked(True)
        d.tpr2010.setText("0.68")
        assert d.Kq_0.text() == "0.99"  # tabla 2000 (default)

        seleccionar_protocolo(d, "rev1")
        assert d.Kq_0.text() == "0.9869"  # tabla Rev.1, valores oficiales de la 31010

        seleccionar_protocolo(d, "2000")
        assert d.Kq_0.text() == "0.99"  # vuelve a la tabla validada en D3

    def test_n31022_sin_datos_en_2000_automatico_en_rev1(self, dialogo):
        """N31022 está congelada en 2000 (guarda D2) pero SÍ tiene fila en
        Rev.1 (Tabla 16) — el selector la habilita sin tocar código."""
        d = dialogo
        seleccionar_camara(d, "N31022", con_serie=False)
        avisos_kq = [a for a in d.avisos if "coeficientes kQ" in a[1]]
        assert len(avisos_kq) == 1, f"avisos: {d.avisos}"
        assert "manualmente" in d.Kq_0.placeholderText()

        d.fotones.setChecked(True)
        n_avisos_antes = len(d.avisos)
        seleccionar_protocolo(d, "rev1")
        assert len(d.avisos) == n_avisos_antes, "no debía avisar de nuevo: rev1 sí tiene datos"
        assert "manualmente" not in d.Kq_0.placeholderText()

        d.tpr2010.setText("0.68")
        assert d.Kq_0.text() == "0.9905"

        seleccionar_protocolo(d, "2000")
        assert "manualmente" in d.Kq_0.placeholderText()  # guarda activa otra vez
        d.Kq_0.setText("0.985")  # kQ manual del físico
        d.tpr2010.setText("0.70")  # re-teclear TPR no debe borrarlo (bug D2.1)
        assert d.Kq_0.text() == "0.985"

    def test_n31014_manual_sobrevive_al_cambiar_protocolo_y_teclear_tpr(self, dialogo):
        """N31014 no está en NINGUNA tabla (ni 2000 ni Rev.1, verificado en
        K2) — kQ manual siempre, sin importar el protocolo seleccionado."""
        d = dialogo
        seleccionar_camara(d, "N31014", con_serie=False)
        d.fotones.setChecked(True)
        d.Kq_0.setText("0.978")

        seleccionar_protocolo(d, "rev1")
        assert d.Kq_0.text() == "0.978"

        d.tpr2010.setText("0.68")
        assert d.Kq_0.text() == "0.978"

        seleccionar_protocolo(d, "2000")
        assert d.Kq_0.text() == "0.978"


# HI-0: hoja Halcyon movida a PrimerosArchivosPruebas/ (ver tests/_corpus.py).
from _corpus import HALCYON_DMAX as HALCYON


class TestEtiquetaSerieCalibracion:
    """K-fix.4: distinguir series repetidas con distinta calibración.

    Reportado 2026-07-09: un mismo número de serie (ej. 1825) aparece varias
    veces en el catálogo con factores/condiciones distintos por
    recalibración, sin nada en el desplegable que indique cuál es la
    vigente -- solo servía para elegir el factor, y las condiciones
    (temp/presión/humedad) se podían de todos modos editar a mano en la app.
    """

    def test_combo_series_sin_fecha_ni_vigente_mantiene_texto_original(self, dialogo):
        """Compatibilidad: el fixture EQUIPOS no trae fecha_calibr/vigente
        (igual que un EquiposService.obtener_series_por_modelo() más viejo)
        -> el texto debe seguir siendo solo 'Serie: X', sin colgar 'None'."""
        d = dialogo
        idx = d.combo_modelos.findData("N31010")
        d.combo_modelos.setCurrentIndex(idx)
        assert d.combo_series.itemText(1) == "Serie: 1825"

    def test_combo_series_muestra_fecha_y_vigente(self, dialogo, monkeypatch):
        # F9 (PLAN_F_CIERRE_ESTANDAR_29-07.md §9): sin símbolos -- la
        # vigencia se deriva con es_vigente_en_fecha contra self.date_edit
        # (hoy, en este fixture), no contra una columna `vigente` que ya no
        # llega en el dict (retirada del contrato en F8). 16/03/2026 + 2
        # años sigue vigente hoy; 05/02/2024 + 2 años ya venció en 02/2026.
        equipos_n31010 = [
            {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
             "serie": "1825", "calibr_fact": 0.3045, "t_cal": 22.0,
             "p_cal": 101.325, "h_cal": 50.0,
             "fecha_calibr": "16/03/2026"},
            {"id": 5, "equip_type": "Cámara de ionización", "model": "N31010",
             "serie": "1825", "calibr_fact": 0.3034, "t_cal": 20.9,
             "p_cal": 98.97, "h_cal": 33.0,
             "fecha_calibr": "05/02/2024"},
        ]
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_series_por_modelo",
            staticmethod(lambda m: equipos_n31010 if m == "N31010" else []))

        d = dialogo
        idx = d.combo_modelos.findData("N31010")
        d.combo_modelos.setCurrentIndex(idx)
        assert d.combo_series.itemText(1) == "Serie: 1825 — calibrado 16/03/2026"
        assert d.combo_series.itemText(2) == "Serie: 1825 — calibrado 05/02/2024 (vencida)"
        # Los ids distintos siguen siendo la data real del combo (para poder
        # elegir cuál certificado usar, aunque el número de serie se repita).
        assert d.combo_series.itemData(1) == 76
        assert d.combo_series.itemData(2) == 5


class TestMenuArchivo:
    """K-fix.3: el menú 'Importar MCC' (win32com, crasheaba en los 3 casos
    probados en Windows -- F5/HANDOFF) se retiró de la UI 2026-07-09."""

    def test_no_existe_accion_importar_mcc(self, dialogo):
        assert not hasattr(dialogo, "act_importar")

    def test_comparar_excel_sigue_disponible(self, dialogo):
        assert hasattr(dialogo, "act_comparar_excel")
        assert dialogo.act_comparar_excel.text() == "Comparar con Excel TRS-398"


def _parchear_dialogo_modal(d, monkeypatch, ruta):
    """QFileDialog devuelve `ruta`; exec_ no bloquea; captura los filas.

    Extraída a nivel de módulo (antes método de TestComparacionConExcel) para
    que TestComparacionConExcelElectrones (E5) pueda reusarla sin heredar de
    la clase de fotones y duplicar toda su colección de tests."""
    monkeypatch.setattr(
        dialogs_mod.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (ruta, "")))
    monkeypatch.setattr(dialogs_mod.QDialog, "exec_", lambda self: 0)
    capturado = {}
    orig = d._mostrar_dialogo_comparacion

    def espia(datos, filas, modelo):
        capturado["datos"], capturado["filas"], capturado["modelo"] = datos, filas, modelo
        return orig(datos, filas, modelo)
    monkeypatch.setattr(d, "_mostrar_dialogo_comparacion", espia)
    return capturado


class TestComparacionConExcel:
    """Flujo D3.3: menú 'Comparar con Excel TRS-398' sobre el diálogo real."""

    _parchear_dialogo_modal = staticmethod(_parchear_dialogo_modal)

    def test_cancelar_selector_no_hace_nada(self, dialogo, monkeypatch):
        monkeypatch.setattr(
            dialogs_mod.QFileDialog, "getOpenFileName",
            staticmethod(lambda *a, **k: ("", "")))
        llamado = []
        monkeypatch.setattr(dialogo, "_mostrar_dialogo_comparacion",
                            lambda *a: llamado.append(True))
        dialogo.comparar_con_excel()
        assert not llamado

    def test_extension_invalida_avisa_sin_reventar(self, dialogo, monkeypatch, tmp_path):
        p = tmp_path / "x.txt"
        p.write_text("no soy excel")
        monkeypatch.setattr(
            dialogs_mod.QFileDialog, "getOpenFileName",
            staticmethod(lambda *a, **k: (str(p), "")))
        dialogo.comparar_con_excel()
        assert any(a[0] == "critical" for a in dialogo.avisos)

    @pytest.mark.skipif(not os.path.exists(HALCYON),
                        reason="archivo real del físico no disponible")
    def test_halcyon_con_n31010_todo_ok(self, dialogo, monkeypatch):
        seleccionar_camara(dialogo, "N31010")
        cap = self._parchear_dialogo_modal(dialogo, monkeypatch, HALCYON)
        dialogo.comparar_con_excel()
        assert cap["modelo"] == "N31010"
        for f in cap["filas"]:
            assert f["comparable"], f["magnitud"]
            assert f["ok"], f"{f['magnitud']} difiere"

    @pytest.mark.skipif(not os.path.exists(HALCYON),
                        reason="archivo real del físico no disponible")
    def test_halcyon_sin_camara_compara_parcial(self, dialogo, monkeypatch):
        cap = self._parchear_dialogo_modal(dialogo, monkeypatch, HALCYON)
        dialogo.comparar_con_excel()  # sin cámara seleccionada
        filas = {f["magnitud"]: f for f in cap["filas"]}
        assert filas["kQ"]["comparable"] is False
        assert filas["ktp"]["comparable"] is True and filas["ktp"]["ok"]

    @pytest.mark.skipif(not os.path.exists(HALCYON),
                        reason="archivo real del físico no disponible")
    def test_halcyon_con_selector_en_rev1_sigue_pineado_a_2000(self, dialogo, monkeypatch):
        """Fase K1/K4: comparar_trs398 (vía trs398_excel._recalcular_con_app)
        queda PINEADA a protocolo "2000" a propósito, sin importar en qué
        protocolo esté el selector de la calculadora -- las hojas del físico
        están calculadas con TRS-398 2000. Con el selector en rev1, la
        comparación debe seguir dando exactamente el mismo resultado (todo
        verde) que con el selector en 2000 (test_halcyon_con_n31010_todo_ok)."""
        seleccionar_camara(dialogo, "N31010")
        seleccionar_protocolo(dialogo, "rev1")
        cap = self._parchear_dialogo_modal(dialogo, monkeypatch, HALCYON)
        dialogo.comparar_con_excel()
        assert cap["modelo"] == "N31010"
        for f in cap["filas"]:
            assert f["comparable"], f["magnitud"]
            assert f["ok"], f"{f['magnitud']} difiere -- ¿el pin a 2000 se rompió?"


ELECTRONES_12MEV = os.path.expanduser(
    "~/Documents/Archivos_UseApp/Archivos QA/2024/Enero/iX/Electrones/TRS-398 12 MeV.xls")


class TestComparacionConExcelElectrones:
    """E5 (auditoría 2026-07-10): el comparador 'Comparar con Excel TRS-398'
    ahora reconoce hojas de ELECTRONES (antes solo entendía el layout de
    fotones -- leerlas producía celdas corridas / NC engañoso). Reusa
    _parchear_dialogo_modal (función de módulo, ver TestComparacionConExcel)."""

    @pytest.mark.skipif(not os.path.exists(ELECTRONES_12MEV),
                        reason="corpus 2024 no disponible en esta máquina")
    def test_electrones_12mev_con_roos_todo_ok(self, dialogo, monkeypatch):
        seleccionar_camara(dialogo, "N34001")
        dialogo.electrones.setChecked(True)
        cap = _parchear_dialogo_modal(dialogo, monkeypatch, ELECTRONES_12MEV)
        dialogo.comparar_con_excel()
        assert cap["datos"]["tipo_haz"] == "electrones"
        assert cap["modelo"] == "N34001"
        for f in cap["filas"]:
            assert f["comparable"], f["magnitud"]
            assert f["ok"], f"{f['magnitud']} difiere: {f['diferencia_rel']}"

    @pytest.mark.skipif(not os.path.exists(ELECTRONES_12MEV),
                        reason="corpus 2024 no disponible en esta máquina")
    def test_electrones_sin_camara_compara_parcial_con_aviso_correcto(
            self, dialogo, monkeypatch):
        """Sin cámara seleccionada, el aviso debe evaluar la guarda de
        ELECTRONES (camara_tiene_kq_electrones) -- si usara por error la de
        fotones, N31010 (que SÍ tiene fila de fotones) pasaría la guarda y
        el aviso desaparecería incorrectamente para una hoja de electrones."""
        cap = _parchear_dialogo_modal(dialogo, monkeypatch, ELECTRONES_12MEV)
        dialogo.comparar_con_excel()
        filas = {f["magnitud"]: f for f in cap["filas"]}
        assert filas["kQ"]["comparable"] is False
        assert filas["ktp"]["comparable"] is True and filas["ktp"]["ok"]

    @pytest.mark.skipif(not os.path.exists(ELECTRONES_12MEV),
                        reason="corpus 2024 no disponible en esta máquina")
    def test_electrones_incluye_beam_quality_r50_y_zref(self, dialogo, monkeypatch):
        """H3.2 (auditoría 2026-07-14): invierte la exclusión original de E5.
        Aunque el físico sobreescribe zref a mano en muchas hojas de 6 MeV
        (convención clínica desde mediados de 2024, no un error -- ver
        test_corpus_2024_cross_check.py), la decisión pasó a ser mostrar y
        explicar (aviso en el diálogo, H3.2/H3.1), no ocultar la fila. Esta
        hoja (Enero/12 MeV) no tiene el override -- debe comparar exacto."""
        seleccionar_camara(dialogo, "N34001")
        cap = _parchear_dialogo_modal(dialogo, monkeypatch, ELECTRONES_12MEV)
        dialogo.comparar_con_excel()
        filas = {f["magnitud"]: f for f in cap["filas"]}
        assert "beam_quality_r50" in filas and filas["beam_quality_r50"]["ok"]
        assert "zref" in filas and filas["zref"]["ok"]


class TestH31ComparadorEncabezadoHonesto:
    """H3.1 (auditoría 2026-07-14): la columna "App" recalcula con el motor
    de la app usando las entradas DE LA HOJA -- no lo tecleado en la sesión
    actual. El diálogo debe decirlo, no solo el docstring del método."""

    def _capturar_dialogo(self, dialogo, monkeypatch, filas, datos=None, modelo="N31010"):
        capturado = {}

        def exec_espia(self):
            capturado["dlg"] = self
            return 0
        monkeypatch.setattr(dialogs_mod.QDialog, "exec_", exec_espia)

        datos = datos or {"archivo": "hoja.xls", "tipo_haz": "fotones"}
        dialogo._mostrar_dialogo_comparacion(datos, filas, modelo)
        return capturado["dlg"]

    def test_columna_app_declara_que_usa_entradas_del_excel(self, dialogo, monkeypatch):
        filas = [{"magnitud": "ktp", "etiqueta": "kTP", "app": 1.0068, "excel": 1.0068,
                  "comparable": True, "ok": True, "diferencia_rel": 0.0}]
        dlg = self._capturar_dialogo(dialogo, monkeypatch, filas)

        tabla = dlg.findChild(dialogs_mod.QTableWidget)
        assert tabla.horizontalHeaderItem(1).text() == "App (motor, entradas del Excel)"

    def test_aparece_la_aclaracion_de_que_no_compara_la_sesion_actual(self, dialogo, monkeypatch):
        filas = [{"magnitud": "ktp", "etiqueta": "kTP", "app": 1.0068, "excel": 1.0068,
                  "comparable": True, "ok": True, "diferencia_rel": 0.0}]
        dlg = self._capturar_dialogo(dialogo, monkeypatch, filas)

        textos = [lbl.text() for lbl in dlg.findChildren(dialogs_mod.QLabel)]
        assert any("no compara" in t and "sesión actual" in t for t in textos), textos


class TestFlujoElectronesRoos:
    """Camino de electrones corregido en la auditoría 2026-07-09 contra el
    corpus 2024 (53 hojas TRS-398 reales): kQ y zref se derivan de la CALIDAD
    R50,w (no del R50 crudo) y el kQ automático sale de la tabla de electrones
    del protocolo activo (antes: tabla de fotones, bloqueada por accidente).
    Valores centinela = hoja real Enero/iX/12 MeV."""

    def test_cadena_r50_calidad_zref_kq(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N34001")
        d.electrones.setChecked(True)
        d.R50.setText("5.127")                      # R50 medido (ionización)
        assert d.QualityR50.text() == "5.2157"      # 1.029*R50 - 0.06
        # zref = 0.6*R50,w - 0.1; con el bug (R50 crudo) daba 2.9762
        assert d.zrefR50.text() == "3.0294"
        # Cuadro 18 (2000) Roos a R50,w; la hoja calcula 0.9102745
        assert d.Kq0r50_widget.text() == "0.91027"

    def test_selector_protocolo_conmuta_kq_electrones(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N34001")
        d.electrones.setChecked(True)
        d.R50.setText("5.127")
        assert d.Kq0r50_widget.text() == "0.91027"   # 2000 default
        seleccionar_protocolo(d, "rev1")
        assert d.Kq0r50_widget.text() == "0.91102"   # Table 20 Rev.1
        seleccionar_protocolo(d, "2000")
        assert d.Kq0r50_widget.text() == "0.91027"   # de vuelta al Cuadro 18

    def test_camara_de_fotones_no_autollena_kq_electrones(self, dialogo):
        # Antes del fix, N31010 (con fila en la tabla de FOTONES) pasaba la
        # guarda equivocada y el kQ de electrones se llenaba con el borde de
        # la tabla de fotones. Ahora el valor manual del físico sobrevive.
        d = dialogo
        seleccionar_camara(d, "N31010")
        d.electrones.setChecked(True)
        d.Kq0r50_widget.setText("0.945")
        d.R50.setText("5.127")
        assert d.Kq0r50_widget.text() == "0.945"
        seleccionar_protocolo(d, "rev1")
        assert d.Kq0r50_widget.text() == "0.945"

    def test_kq_manual_n31014_sobrevive_en_electrones(self, dialogo):
        d = dialogo
        seleccionar_camara(d, "N31014")   # sin datos en NINGUNA tabla
        d.electrones.setChecked(True)
        d.Kq0r50_widget.setText("0.912")
        d.R50.setText("2.397")
        assert d.Kq0r50_widget.text() == "0.912"


class TestH33BotonesEnergiaLegibles:
    """H3.3 (auditoría 2026-07-14): antes "6MV"/"6MEV" (energia.upper()) --
    legible pero fácil de confundir con lectura rápida. Ahora "6 MV"/"6 MeV",
    con etiquetas de grupo "Fotones:"/"Electrones:" antes del primer botón
    de cada tipo."""

    ENERGIAS_IX = ["6mv", "15mv", "6mev", "9mev", "12mev", "15mev"]

    @pytest.fixture
    def dialogo_ix_completo(self, app, monkeypatch):
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
        d = DialogCalculadoraDosis(energias=self.ENERGIAS_IX, parent=VentanaIX())
        yield d
        d.deleteLater()

    def _widgets_asignar(self, d):
        widgets = []
        for i in range(d.layout_asignar.count()):
            w = d.layout_asignar.itemAt(i).widget()
            if w is not None:
                widgets.append(w)
        return widgets

    def test_etiquetas_de_botones_legibles(self, dialogo_ix_completo):
        botones = [w for w in self._widgets_asignar(dialogo_ix_completo)
                   if isinstance(w, QPushButton)]
        assert [b.text() for b in botones] == [
            "6 MV", "15 MV", "6 MeV", "9 MeV", "12 MeV", "15 MeV"]

    def test_grupos_fotones_electrones_antes_del_primer_boton(self, dialogo_ix_completo):
        widgets = self._widgets_asignar(dialogo_ix_completo)
        textos = [w.text() for w in widgets]
        assert textos == [
            "Fotones:", "6 MV", "15 MV",
            "Electrones:", "6 MeV", "9 MeV", "12 MeV", "15 MeV",
        ]
        etiquetas_grupo = [w for w in widgets if isinstance(w, QLabel)]
        assert [e.text() for e in etiquetas_grupo] == ["Fotones:", "Electrones:"]

    def test_boton_emite_energia_cruda_no_la_etiqueta(self, dialogo_ix_completo):
        """El texto visible cambió (H3.3) pero emitir_dosis debe seguir
        recibiendo la clave cruda ("6mev", no "6 MeV") -- es la que usa para
        ubicar el widget ln_dosis_ref_cgy_um_{energia} del formulario."""
        d = dialogo_ix_completo
        emitidos = []
        d.dosis_asignada.connect(lambda e, v: emitidos.append(e))
        boton_6mev = next(w for w in self._widgets_asignar(d)
                          if isinstance(w, QPushButton) and w.text() == "6 MeV")
        d.dosis_maxima.setText("0.01")  # necesario para que emitir_dosis no aborte
        boton_6mev.click()
        assert emitidos == ["6mev"]


class TestH34FechaCalculadoraDesdeFormulario:
    """H3.4 (auditoría 2026-07-14): antes la calculadora siempre abría en
    "hoy", sin relación con el mes que el físico está diligenciando en el
    formulario mensual."""

    @pytest.fixture
    def dialogo_factory(self, app, monkeypatch):
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

        def _crear(fecha_inicial=None):
            d = DialogCalculadoraDosis(energias=[], parent=VentanaIX(), fecha_inicial=fecha_inicial)
            return d

        return _crear

    def test_sin_fecha_inicial_usa_hoy(self, dialogo_factory):
        d = dialogo_factory()
        assert d.date_edit.date() == QDate.currentDate()

    def test_con_fecha_inicial_usa_el_dia_real_no_el_dia_1(self, dialogo_factory):
        """F5 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): desde F3 el
        formulario mensual guarda el día real -- la calculadora hereda ESE
        día completo, ya no lo descarta fijando el día 1 (H3.4, retirado)."""
        fecha_formulario = QDate(2026, 3, 31)
        d = dialogo_factory(fecha_inicial=fecha_formulario)
        assert d.date_edit.date() == QDate(2026, 3, 31)

    def test_con_fecha_inicial_queda_bloqueada(self, dialogo_factory):
        """F5: la fecha heredada del mensual no se puede editar en la
        calculadora -- siempre debe coincidir con la del formulario que la
        abrió."""
        d = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))
        assert d.date_edit.isReadOnly() is True
        assert d.date_edit.calendarPopup() is False

    def test_con_fecha_inicial_sin_flechas(self, dialogo_factory):
        """H-H (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md, hallazgo del físico
        2026-07-23): un campo bloqueado no debe insinuar que se puede
        cambiar -- sin botones de incremento/decremento, solo el texto."""
        from PyQt5.QtWidgets import QAbstractSpinBox
        d = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))
        assert d.date_edit.buttonSymbols() == QAbstractSpinBox.NoButtons

    def test_sin_fecha_inicial_sigue_editable(self, dialogo_factory):
        d = dialogo_factory()
        assert d.date_edit.isReadOnly() is False
        assert d.date_edit.calendarPopup() is True

    def test_sin_fecha_inicial_conserva_flechas(self, dialogo_factory):
        """En uso independiente (sin fecha heredada) el campo sigue siendo
        un QDateEdit normal, con sus botones de siempre."""
        from PyQt5.QtWidgets import QAbstractSpinBox
        d = dialogo_factory()
        assert d.date_edit.buttonSymbols() == QAbstractSpinBox.UpDownArrows

    def test_i4_formato_de_fecha_explicito_no_del_locale(self, dialogo_factory):
        """I4 (2026-07-16): sin setDisplayFormat, QDateEdit muestra el formato
        corto del LOCALE del SO (en un Windows en inglés, "M/d/yy": la fecha
        del formulario se veía "7/1/26", ilegible en español -- por eso el
        físico reportó que 'la fecha no era la del formulario' aunque H3.4 sí
        fijaba el mes correcto). El formato visible debe ser el mismo que el
        interno de guardado (dd/MM/yyyy), en cualquier máquina."""
        d = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))
        assert d.date_edit.displayFormat() == "dd/MM/yyyy"
        assert d.date_edit.text() == "16/07/2026"

    def test_i5_ancho_minimo_de_la_fecha_cubre_el_texto(self, dialogo_factory):
        """I5 (2026-07-16): el date_edit de la calculadora nunca tuvo ancho
        mínimo (H3.5 lo excluyó a propósito) y el físico reportó la flecha
        del calendario sobre el texto también aquí. El piso debe salir de la
        métrica de fuente REAL del widget (nunca px fijos: los 100px de H3.5
        quedaron cortos con la fuente de Windows)."""
        d = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))
        fm = d.date_edit.fontMetrics()
        # texto dd/MM/yyyy + drop-down 20 + padding 10 + bordes 4
        necesario = fm.horizontalAdvance("00/00/0000") + 34
        assert d.date_edit.minimumWidth() >= necesario
