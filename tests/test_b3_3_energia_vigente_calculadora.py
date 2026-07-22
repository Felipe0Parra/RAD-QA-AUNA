"""B3.3 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7c/d): el botón de energía dejar
`self.energia_calculo` listo en memoria (sin guardar nada -- el tooltip del
botón ya avisa que solo alimenta el formulario mensual); "Aceptar y Cerrar"
(guardar_db) es el único punto que persiste esa energía, y `guardar_datos`
gestiona ahí la bandera `vigente` por (Acelerador, energia): baja la versión
anterior de esa clave e inserta la nueva como vigente=1, en la MISMA
transacción. Nunca se borra nada -- las versiones históricas quedan
completas, solo se mueve la bandera.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import data.ManejoDatos.conection as conection_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_FOTONES_ORO = {"id": 200, "equip_type": "Cámara de ionización", "model": "N31010",
                      "serie": "1822", "calibr_fact": 0.3036, "t_cal": 20.0,
                      "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en 'IX' -> acelerador_actual='IX'
    (nombre corto de la calculadora; lo guardado es el canónico "Clinac iX",
    ver B3-N)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


@pytest.fixture
def dialogo_factory(app, bd_temporal, monkeypatch):
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

    def _crear(energias=("6mv", "15mv")):
        return DialogCalculadoraDosis(energias=list(energias), parent=VentanaIX())

    return _crear


def _llenar_fotones_completo(d):
    """Mínimo exigido por guardar_db para fotones (10x10) -- mismo patrón
    que test_calculadora_dosis_g1.py."""
    idx = d.combo_modelos.findData(EQUIPO_FOTONES_ORO["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.fotones.setChecked(True)
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


class TestEnergiaCalculoEnMemoria:

    def test_arranca_en_none(self, dialogo_factory):
        assert dialogo_factory().energia_calculo is None

    def test_boton_de_energia_lo_fija(self, dialogo_factory):
        d = _llenar_fotones_completo(dialogo_factory())
        d.emitir_dosis("6mv")
        assert d.energia_calculo == "6mv"

    def test_ultimo_boton_pulsado_gana(self, dialogo_factory):
        """Caso límite anotado en el plan: si se pulsa más de un botón antes
        de cerrar, gana el último -- igual que ya pasa hoy con la dosis
        emitida al formulario mensual."""
        d = _llenar_fotones_completo(dialogo_factory())
        d.emitir_dosis("6mv")
        d.emitir_dosis("15mv")
        assert d.energia_calculo == "15mv"


class TestPersistenciaSoloAlAceptar:

    def test_sin_pulsar_boton_guarda_con_energia_null_y_no_vigente(
            self, dialogo_factory, bd_temporal):
        """Sin energía asignada, el guardado NO se bloquea (compatibilidad
        con el resto de la suite existente) -- la fila queda fuera del
        esquema de vigencia, igual que la fila legacy (B3.8)."""
        d = _llenar_fotones_completo(dialogo_factory())
        assert d.guardar_db() is True

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT energia, vigente FROM calculadora_dosimetrica WHERE Fecha=?",
            (fecha,)).fetchone()
        con.close()
        assert fila == (None, 0)

    def test_pulsar_boton_y_aceptar_persiste_energia_vigente_y_nombre_canonico(
            self, dialogo_factory, bd_temporal):
        d = _llenar_fotones_completo(dialogo_factory())
        d.emitir_dosis("6mv")
        assert d.guardar_db() is True

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT Acelerador, energia, vigente FROM calculadora_dosimetrica WHERE Fecha=?",
            (fecha,)).fetchone()
        con.close()
        assert fila == ("Clinac iX", "6mv", 1)


class TestBanderaVigentePorAceleradorYEnergia:
    """B3.3/d: guardar una nueva versión de la MISMA clave (Acelerador,
    energia) baja la anterior a vigente=0 -- nunca se borra nada."""

    def test_segunda_version_misma_clave_baja_la_anterior(
            self, dialogo_factory, bd_temporal, monkeypatch):
        d1 = _llenar_fotones_completo(dialogo_factory())
        d1.emitir_dosis("6mv")
        assert d1.guardar_db() is True

        # H2.3 (versionado consciente): mismo Fecha+Acelerador ya guardado
        # hoy -- el diálogo pregunta antes de agregar una versión nueva.
        d2 = _llenar_fotones_completo(dialogo_factory())
        monkeypatch.setattr(d2, "_confirmar_registro_existente", lambda *a, **k: True)
        d2.emitir_dosis("6mv")
        d2.Zmax.setText("1.9")  # distingue la version nueva
        assert d2.guardar_db() is True

        con = sqlite3.connect(bd_temporal)
        con.row_factory = sqlite3.Row
        filas = con.execute(
            "SELECT Zmax, vigente FROM calculadora_dosimetrica "
            "WHERE Acelerador='Clinac iX' AND energia='6mv' ORDER BY id"
        ).fetchall()
        con.close()

        assert len(filas) == 2, "las dos versiones deben conservarse (nunca DELETE)"
        assert (filas[0]["Zmax"], filas[0]["vigente"]) == ("1.5", 0)
        assert (filas[1]["Zmax"], filas[1]["vigente"]) == ("1.9", 1)

    def test_energia_distinta_no_afecta_la_vigencia_de_la_otra(
            self, dialogo_factory, bd_temporal, monkeypatch):
        d1 = _llenar_fotones_completo(dialogo_factory())
        d1.emitir_dosis("6mv")
        assert d1.guardar_db() is True

        # NOTA (queda para B3.4/B3.5): _confirmar_registro_existente hoy
        # dispara por Fecha+Acelerador nada más -- todavía no distingue
        # energia, así que guardar un 15mv el mismo día "choca" con el 6mv
        # recién guardado aunque sean claves distintas. B3.4/B3.5 debe
        # afinar esa pregunta a la clave real (Acelerador, energia).
        d2 = _llenar_fotones_completo(dialogo_factory())
        monkeypatch.setattr(d2, "_confirmar_registro_existente", lambda *a, **k: True)
        d2.emitir_dosis("15mv")
        d2.Zmax.setText("1.9")
        assert d2.guardar_db() is True

        con = sqlite3.connect(bd_temporal)
        con.row_factory = sqlite3.Row
        fila_6mv = con.execute(
            "SELECT vigente FROM calculadora_dosimetrica WHERE energia='6mv'").fetchone()
        fila_15mv = con.execute(
            "SELECT vigente FROM calculadora_dosimetrica WHERE energia='15mv'").fetchone()
        con.close()

        assert fila_6mv["vigente"] == 1, "6mv sigue vigente -- es una clave distinta a 15mv"
        assert fila_15mv["vigente"] == 1
