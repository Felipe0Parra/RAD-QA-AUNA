"""Fase G1 (auditoría 2026-07-10) -- regresión de cierre/pérdida de datos.

Antes de esta fase, "✓ Aceptar y Cerrar" (btn_ok) conectaba DOS señales
independientes: guardar_db y accept(). Si guardar_db interrumpía sin guardar
(formulario incompleto), accept() se ejecutaba de todas formas y cerraba el
diálogo -- el físico vivió esto exactamente: llenó una dosimetría de
electrones, faltó un campo, salió el aviso, y aun así se cerró y perdió todo.

Esta suite fija: (a) formulario incompleto -> guardar_db devuelve False y el
diálogo NO cierra (ni con "Seguir editando" ni acumulando llamadas
accidentales a accept); (b) el físico puede elegir explícitamente "Descartar
y salir" y AHÍ SÍ cierra, vía reject(); (c) formulario completo -> True y
cierra vía accept(); (d) el aviso usa etiquetas legibles, no nombres crudos
de columna.

_avisar_formulario_incompleto se sustituye por un espía en vez de dejar que
abra un QMessageBox modal real (con exec_() colgaría la corrida offscreen).
"""
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import services.dosis_service as dosis_service_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

# Misma cámara/config de oro que test_calculadora_dosis_por_maquina.py
# (PLAN_FASE_F0_GATE.md §5); esta suite no depende de la máquina, así que se
# fija una sola (iX).
EQUIPO_FOTONES_ORO = {"id": 200, "equip_type": "Cámara de ionización", "model": "N31010",
                      "serie": "1822", "calibr_fact": 0.3036, "t_cal": 20.0,
                      "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en 'IX' -> acelerador_actual='IX'."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(dosis_service_mod, "ruta_base_datos", lambda: ruta)
    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


@pytest.fixture
def dialogo(app, bd_temporal, monkeypatch):
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": EQUIPO_FOTONES_ORO["model"],
                               "equip_type": EQUIPO_FOTONES_ORO["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [EQUIPO_FOTONES_ORO] if m == EQUIPO_FOTONES_ORO["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: EQUIPO_FOTONES_ORO if i == EQUIPO_FOTONES_ORO["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(dialogs_mod, "generar_reporte_calibracion", lambda **kwargs: None)

    d = DialogCalculadoraDosis(energias=["6mv"], parent=VentanaIX())
    yield d
    d.deleteLater()


def _espiar_accept_reject(d, monkeypatch):
    """Reemplaza accept/reject por contadores -- así se distingue "no hizo
    nada" de "cerró", sin depender de isVisible()/result() en offscreen."""
    llamadas = {"accept": 0, "reject": 0}
    monkeypatch.setattr(d, "accept", lambda: llamadas.__setitem__("accept", llamadas["accept"] + 1))
    monkeypatch.setattr(d, "reject", lambda: llamadas.__setitem__("reject", llamadas["reject"] + 1))
    return llamadas


def llenar_fotones_completo(d, marcar_ssd=True):
    """Llena TODOS los campos que guardar_db exige para fotones (10x10).

    marcar_ssd=False deja Tipo_de_medicion en None a propósito (para el test
    de etiquetas legibles) -- SSD vive en un QButtonGroup exclusivo de un
    solo miembro (SAD está comentado, hallazgo D1-H2): una vez marcado con
    setChecked(True), un setChecked(False) posterior NO lo desmarca (Qt
    garantiza que un grupo exclusivo con un botón ya marcado no se quede sin
    ninguno), así que hay que dejarlo sin marcar desde el principio.
    """
    idx = d.combo_modelos.findData(EQUIPO_FOTONES_ORO["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.fotones.setChecked(True)
    if marcar_ssd:
        d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.combo_fieldsize.setCurrentIndex(0)  # 10x10

    d.temp.setText("22.0")
    d.pressure.setText("101.325")
    d.humr_cal.setText("45.0")
    d.humedad_r.setText("48.0")
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
    d.Zref.setText("10.0")
    d.Zmax.setText("1.5")
    return d


class TestFormularioIncompletoNoCierra:
    """El núcleo de la regresión: sin guardado confirmado, NO debe cerrar."""

    def test_guardar_db_devuelve_false_si_falta_un_campo(self, dialogo, monkeypatch):
        d = llenar_fotones_completo(dialogo)
        d.unidades_monitor.setText("")  # rompe deliberadamente un campo exigido
        monkeypatch.setattr(d, "_avisar_formulario_incompleto", lambda etiquetas: False)

        resultado = d.guardar_db()

        assert resultado is False

    def test_seguir_editando_no_cierra_el_dialogo(self, dialogo, monkeypatch):
        d = llenar_fotones_completo(dialogo)
        d.unidades_monitor.setText("")
        monkeypatch.setattr(d, "_avisar_formulario_incompleto", lambda etiquetas: False)
        llamadas = _espiar_accept_reject(d, monkeypatch)

        d.on_aceptar_y_cerrar()

        assert llamadas == {"accept": 0, "reject": 0}, (
            "regresión F3: el diálogo no debe cerrarse ni con accept ni con "
            "reject cuando el físico elige 'Seguir editando'")

    def test_descartar_y_salir_cierra_via_reject(self, dialogo, monkeypatch):
        """El físico puede elegir explícitamente salir sin guardar: eso SÍ
        cierra, pero via reject() (nunca accept(), que implicaría éxito)."""
        d = llenar_fotones_completo(dialogo)
        d.unidades_monitor.setText("")
        monkeypatch.setattr(d, "_avisar_formulario_incompleto", lambda etiquetas: True)
        llamadas = _espiar_accept_reject(d, monkeypatch)

        d.on_aceptar_y_cerrar()

        assert llamadas == {"accept": 0, "reject": 1}


class TestFormularioCompletoCierra:
    def test_guardar_db_devuelve_true_si_completo(self, dialogo):
        d = llenar_fotones_completo(dialogo)
        assert d.guardar_db() is True

    def test_on_aceptar_y_cerrar_cierra_via_accept(self, dialogo, monkeypatch):
        d = llenar_fotones_completo(dialogo)
        llamadas = _espiar_accept_reject(d, monkeypatch)

        d.on_aceptar_y_cerrar()

        assert llamadas == {"accept": 1, "reject": 0}

    def test_el_registro_completo_queda_en_bd(self, dialogo):
        d = llenar_fotones_completo(dialogo)
        assert d.guardar_db() is True

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, d.acelerador_actual)
        assert datos_bd is not None
        assert datos_bd["dosis_maxima"] not in (None, "")


class TestEtiquetasLegibles:
    """El aviso debe usar nombres amigables, no claves crudas de columna."""

    def test_mensaje_usa_etiqueta_legible_no_clave_cruda(self, dialogo, monkeypatch):
        # marcar_ssd=False -> Tipo_de_medicion queda None (campo exigido).
        d = llenar_fotones_completo(dialogo, marcar_ssd=False)

        capturado = {}
        monkeypatch.setattr(
            d, "_avisar_formulario_incompleto",
            lambda etiquetas: capturado.setdefault("etiquetas", etiquetas) and False)

        d.guardar_db()

        etiquetas = capturado.get("etiquetas", [])
        assert "Tipo de medición (SSD)" in etiquetas
        assert "Tipo_de_medicion" not in etiquetas

    def test_todas_las_etiquetas_de_campos_siempre_requeridos_existen(self):
        """Ningún campo siempre-requerido queda sin traducción (evita que el
        mapa se desactualice si se agrega un campo nuevo a la validación)."""
        faltantes_de_mapa = [
            c for c in DialogCalculadoraDosis._CAMPOS_SIEMPRE_REQUERIDOS
            if c not in DialogCalculadoraDosis._ETIQUETAS_CAMPOS
        ]
        assert faltantes_de_mapa == []
