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

from PyQt5.QtWidgets import QApplication, QWidget

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
EQUIPOS = (EQUIPO_N31010, EQUIPO_N31014, EQUIPO_N31022)


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
        assert d.pressure_0.text() == "101.325"
        assert not d.avisos, f"no debía haber avisos para N31010: {d.avisos}"

        d.fotones.setChecked(True)
        d.SSD.setChecked(True)
        d.pulse.setChecked(True)

        # Condiciones clínicas → kTP (valor pineado en la suite D1)
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


HALCYON = os.path.expanduser(
    "~/Documents/Archivos_UseApp/TRS-398 6 MV FFF Halcyon Dmax.xls")


class TestComparacionConExcel:
    """Flujo D3.3: menú 'Comparar con Excel TRS-398' sobre el diálogo real."""

    def _parchear_dialogo_modal(self, d, monkeypatch, ruta):
        """QFileDialog devuelve `ruta`; exec_ no bloquea; captura los filas."""
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
