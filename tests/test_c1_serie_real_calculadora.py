"""C1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md): la calculadora guarda la
serie REAL de la cámara en `Numero_serie`, no el id interno del combo
(`combo_series.currentData()`, F1) -- el reporte PDF (Z3,
PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md) ya resolvía la serie real desde
`equipo_id` al MOSTRAR; este cambio hace que lo GUARDADO desde ahora en
adelante ya sea la serie real, sin reescribir ningún dato histórico
(DA-02/DA-28) ni alterar el fallback de `cargar_datos_desde_db` (activo solo
cuando `equipo_id` es None -- filas anteriores a B3).
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

EQUIPO_N31010 = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                 "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (el diálogo deduce el acelerador)."""


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


def _dialogo_factory(bd_temporal, monkeypatch, equipo):
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": equipo["model"], "equip_type": equipo["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [equipo] if m == equipo["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: equipo if i == equipo["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(dialogs_mod, "generar_reporte_calibracion", lambda **kwargs: None)

    def _crear():
        return DialogCalculadoraDosis(energias=["6mv"], parent=VentanaIX())

    return _crear


def _llenar_fotones_10x10(d, equipo):
    idx = d.combo_modelos.findData(equipo["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.fotones.setChecked(True)
    d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.combo_fieldsize.setCurrentIndex(0)

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


class TestC1SerieRealAlGuardar:

    def test_guardar_db_persiste_la_serie_real_no_el_id(self, app, bd_temporal, monkeypatch):
        factory = _dialogo_factory(bd_temporal, monkeypatch, EQUIPO_N31010)
        d = _llenar_fotones_10x10(factory(), EQUIPO_N31010)
        assert d.equipo_id == EQUIPO_N31010["id"]
        assert d.combo_series.currentData() == EQUIPO_N31010["id"]

        d.guardar_db()

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, d.acelerador_actual)
        assert datos_bd is not None
        assert datos_bd["Numero_serie"] == EQUIPO_N31010["serie"]
        assert datos_bd["Numero_serie"] != str(EQUIPO_N31010["id"])
        assert datos_bd["equipo_id"] == EQUIPO_N31010["id"]

    def test_registro_nuevo_sigue_cargando_bien_por_equipo_id(self, app, bd_temporal, monkeypatch):
        """El lado de lectura (Z3, equipo_id como fuente autoritativa) no se
        toca -- un registro guardado con la serie real en Numero_serie
        recarga la misma selección de combo, porque cargar_datos_desde_db
        resuelve por equipo_id primero y ni siquiera mira Numero_serie."""
        factory = _dialogo_factory(bd_temporal, monkeypatch, EQUIPO_N31010)
        original = _llenar_fotones_10x10(factory(), EQUIPO_N31010)
        original.guardar_db()

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)

        cargado = factory()
        cargado.cargar_datos_desde_db(datos_bd)
        assert cargado.equipo_id == EQUIPO_N31010["id"]
        assert cargado.combo_series.currentData() == EQUIPO_N31010["id"]

    def test_sin_datos_equipo_resuelto_conserva_el_comportamiento_anterior(
            self, app, bd_temporal, monkeypatch):
        """Último recurso documentado en el comentario de C1: si
        self.datos_equipo no llegó a cargarse (equipo_id sin resolver en el
        catálogo), Numero_serie cae de vuelta a combo_series.currentData()
        en vez de reventar con AttributeError sobre None."""
        factory = _dialogo_factory(bd_temporal, monkeypatch, EQUIPO_N31010)
        d = _llenar_fotones_10x10(factory(), EQUIPO_N31010)
        assert d.datos_equipo is not None

        d.datos_equipo = None  # simula el caso "equipo_id sin resolver"

        d.guardar_db()

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, d.acelerador_actual)
        assert datos_bd is not None
        assert datos_bd["Numero_serie"] == str(EQUIPO_N31010["id"])

    def test_registro_legacy_sin_equipo_id_sigue_usando_numero_serie_como_fallback(
            self, app, bd_temporal, monkeypatch):
        """Filas anteriores a B3 (equipo_id NULL, Numero_serie con el id
        crudo) no se reescriben (DA-02/DA-28) y su fallback de lectura
        (dialogs.py:2571-2574) sigue funcionando exactamente igual."""
        factory = _dialogo_factory(bd_temporal, monkeypatch, EQUIPO_N31010)
        cargado = factory()
        datos_bd_legacy = {
            "Acelerador": cargado.acelerador_actual,
            "Modelo_equipo": EQUIPO_N31010["model"],
            "equipo_id": None,
            "Numero_serie": str(EQUIPO_N31010["id"]),
        }
        cargado.cargar_datos_desde_db(datos_bd_legacy)
        assert cargado.combo_series.currentData() == EQUIPO_N31010["id"]
