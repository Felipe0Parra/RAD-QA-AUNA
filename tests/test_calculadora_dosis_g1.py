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
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import services.dosis_service as dosis_service_mod
import data.ManejoDatos.conection as conection_mod
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

    marcar_ssd quedó VESTIGIAL con I6 (2026-07-16): marcar fotones ya marca
    SSD por código (pedido del físico), así que Tipo_de_medicion nunca queda
    en None por esa vía -- el test de etiquetas legibles ahora provoca el
    faltante vaciando Zmax (anotación manual sin cascada). El parámetro se
    conserva para no tocar todos los call-sites; ambos valores dejan SSD
    marcado.
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


class TestH23RegistroExistente:
    """H2.3: versionado consciente -- guardar dos veces la MISMA
    fecha+acelerador pregunta antes de agregar una fila nueva (nunca borra,
    a diferencia del reporte diario de H2.2, que sí reemplaza con
    DELETE+INSERT). "No" cancela sin insertar; "Sí" agrega una versión
    nueva y buscar_por_fecha (ORDER BY id DESC LIMIT 1) trae la más
    reciente."""

    def _contar_filas(self, bd_temporal, fecha, acelerador):
        # B3-N: guardar_datos normaliza Acelerador al nombre canónico antes
        # de insertar -- esta consulta cruda (a propósito, para verificar
        # la fila REAL sin pasar por el service) debe normalizar igual.
        from services.nombres_acelerador import nombre_canonico
        con = sqlite3.connect(bd_temporal)
        try:
            return con.execute(
                "SELECT COUNT(*) FROM calculadora_dosimetrica WHERE Fecha=? AND Acelerador=?",
                (fecha, nombre_canonico(acelerador))).fetchone()[0]
        finally:
            con.close()

    def test_sin_registro_previo_no_pregunta(self, dialogo, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            dialogo, "_confirmar_registro_existente",
            lambda *a, **k: llamadas.append((a, k)) or True)
        d = llenar_fotones_completo(dialogo)

        assert d.guardar_db() is True
        assert llamadas == [], "el primer guardado no debe preguntar nada"

    def test_segundo_guardado_con_no_cancela_sin_insertar(self, dialogo, bd_temporal, monkeypatch):
        d = llenar_fotones_completo(dialogo)
        assert d.guardar_db() is True  # primer guardado, sin registro previo
        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        assert self._contar_filas(bd_temporal, fecha, d.acelerador_actual) == 1

        monkeypatch.setattr(d, "_confirmar_registro_existente", lambda *a, **k: False)
        d.Zmax.setText("1.9")  # si se colara, distinguiria el intento cancelado

        resultado = d.guardar_db()

        assert resultado is False
        assert self._contar_filas(bd_temporal, fecha, d.acelerador_actual) == 1

    def test_segundo_guardado_con_si_agrega_version_nueva(self, dialogo, bd_temporal, monkeypatch):
        d = llenar_fotones_completo(dialogo)
        assert d.guardar_db() is True  # primer guardado, sin registro previo
        fecha = d.date_edit.date().toString("dd/MM/yyyy")

        monkeypatch.setattr(d, "_confirmar_registro_existente", lambda *a, **k: True)
        d.Zmax.setText("1.9")  # marca la "nueva version"

        resultado = d.guardar_db()

        assert resultado is True
        assert self._contar_filas(bd_temporal, fecha, d.acelerador_actual) == 2
        recuperado = dosis_service_mod.DosisService.buscar_por_fecha(fecha, d.acelerador_actual)
        assert recuperado["Zmax"] == "1.9", (
            "buscar_por_fecha debe devolver la version mas reciente")

    def test_pregunta_recibe_fecha_y_acelerador_correctos(self, dialogo, monkeypatch):
        d = llenar_fotones_completo(dialogo)
        assert d.guardar_db() is True

        capturado = {}
        monkeypatch.setattr(
            d, "_confirmar_registro_existente",
            lambda fecha, acelerador: capturado.update(
                fecha=fecha, acelerador=acelerador) or False)

        d.guardar_db()

        fecha_esperada = d.date_edit.date().toString("dd/MM/yyyy")
        assert capturado == {"fecha": fecha_esperada, "acelerador": d.acelerador_actual}


class TestH24AuditoriaCalculadora:
    """H2.4: guardar_db debe dejar rastro en audit_log al guardar con éxito
    (y NO al fallar validación) -- verifica el cableado, no el helper
    (services/audit_minimo.py ya tiene su propia suite aislada)."""

    def test_guardado_exitoso_llama_a_la_auditoria(self, dialogo, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            dialogs_mod, "_registrar_auditoria",
            lambda *a, **k: llamadas.append((a, k)))
        d = llenar_fotones_completo(dialogo)

        assert d.guardar_db() is True

        assert len(llamadas) == 1
        args, kwargs = llamadas[0]
        assert args[1] == "guardar"
        assert args[2] == "calculadora_dosimetrica"
        assert kwargs["ref"] == f"{d.date_edit.date().toString('dd/MM/yyyy')}|{d.acelerador_actual}"

    def test_formulario_incompleto_no_llama_a_la_auditoria(self, dialogo, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            dialogs_mod, "_registrar_auditoria",
            lambda *a, **k: llamadas.append((a, k)))
        d = llenar_fotones_completo(dialogo)
        d.unidades_monitor.setText("")  # rompe un campo exigido
        monkeypatch.setattr(d, "_avisar_formulario_incompleto", lambda etiquetas: False)

        assert d.guardar_db() is False
        assert llamadas == []


class TestEtiquetasLegibles:
    """El aviso debe usar nombres amigables, no claves crudas de columna."""

    def test_mensaje_usa_etiqueta_legible_no_clave_cruda(self, dialogo, monkeypatch):
        # I6 dejó Tipo_de_medicion siempre lleno (fotones auto-marca SSD),
        # así que el faltante se provoca con Zmax: anotación manual sin
        # cascada -- ningún otro campo la llena por sí solo.
        d = llenar_fotones_completo(dialogo)
        d.Zmax.clear()

        capturado = {}
        monkeypatch.setattr(
            d, "_avisar_formulario_incompleto",
            lambda etiquetas: capturado.setdefault("etiquetas", etiquetas) and False)

        d.guardar_db()

        etiquetas = capturado.get("etiquetas", [])
        assert "Profundidad de dosis máxima (zmax)" in etiquetas
        assert "Zmax" not in etiquetas

    def test_todas_las_etiquetas_de_campos_siempre_requeridos_existen(self):
        """Ningún campo siempre-requerido queda sin traducción (evita que el
        mapa se desactualice si se agrega un campo nuevo a la validación)."""
        faltantes_de_mapa = [
            c for c in DialogCalculadoraDosis._CAMPOS_SIEMPRE_REQUERIDOS
            if c not in DialogCalculadoraDosis._ETIQUETAS_CAMPOS
        ]
        assert faltantes_de_mapa == []
