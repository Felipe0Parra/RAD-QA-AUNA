"""Round-trip guardar↔cargar de DialogCalculadoraDosis POR MÁQUINA (Fase F1).

Motivación (auditoría 2026-07-10, hallazgo H-F4): toda la suite de
guardar/cargar existente (test_calculadora_dosis_guardar_cargar.py) usa un
único padre falso `VentanaIX` -- 600 y Halcyon nunca se probaron con un test
commiteado, solo una vez en un script de scratchpad ya descartado (Fase E).
Este archivo cierra ese hueco con la CONFIGURACIÓN DE ORO confirmada por el
usuario (PLAN_FASE_F0_GATE.md §5): cámara de fotones N31010/serie 1822 igual
en las 3 máquinas, cámara de electrones TN34001 (solo iX, único acelerador
con electrones), campo 10x10 en todas.

Verifica, para cada máquina: (a) `acelerador_actual` se deduce correctamente
del nombre de la clase padre, (b) ese valor se persiste y se recupera vía
`buscar_por_fecha` (que FILTRA por Acelerador -- una deducción equivocada
haría que el registro "desaparezca" al buscarlo), (c) el registro completo
sobrevive el round-trip real.
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
from services.nombres_acelerador import nombre_canonico

# Configuración de oro (PLAN_FASE_F0_GATE.md §5, confirmada por el usuario
# 2026-07-10): misma cámara de fotones en las 3 máquinas; serie 1822 (NO 1825,
# usada en otros archivos de test con fines distintos).
EQUIPO_FOTONES_ORO = {"id": 200, "equip_type": "Cámara de ionización", "model": "N31010",
                      "serie": "1822", "calibr_fact": 0.3036, "t_cal": 20.0,
                      "p_cal": 101.325, "h_cal": 50.0}
# Electrones: solo iX tiene electrones (600/Halcyon no). TN34001, no N34001
# (grafía con prefijo T -- ver alias en K2/Q0_R50_TABLE).
EQUIPO_ELECTRONES_ORO = {"id": 201, "equip_type": "Cámara de ionización", "model": "TN34001",
                         "serie": "001069", "calibr_fact": 0.08563, "t_cal": 20.0,
                         "p_cal": 101.325, "h_cal": 50.0}


class Ventana600(QWidget):
    """Padre falso cuyo nombre termina en '600' -> acelerador_actual='Seiscientos'."""


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en 'IX' -> acelerador_actual='IX'."""


class VentanaHc(QWidget):
    """Padre falso cuyo nombre termina en 'Hc' -> acelerador_actual='Hc'."""


MAQUINAS_FOTONES = [
    pytest.param(Ventana600, "Seiscientos", id="600"),
    pytest.param(VentanaIX, "IX", id="iX"),
    pytest.param(VentanaHc, "Hc", id="Halcyon"),
]


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


def _dialogo_factory(app, bd_temporal, monkeypatch, equipo, ventana_cls):
    """Construye un DialogCalculadoraDosis con el catálogo simulado limitado
    a `equipo` y el padre `ventana_cls` (deduce el acelerador)."""
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
        return DialogCalculadoraDosis(energias=["6mv"], parent=ventana_cls())

    return _crear


def llenar_fotones_10x10(d, equipo):
    idx = d.combo_modelos.findData(equipo["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.fotones.setChecked(True)
    d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.combo_fieldsize.setCurrentIndex(0)  # config de oro: 10x10 (primer ítem)

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
    d.Zref.setText("10.0")  # anotación manual, sin cascada -- F3 exige completo
    d.Zmax.setText("1.5")
    return d


def llenar_electrones_10x10(d, equipo):
    idx = d.combo_modelos.findData(equipo["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.electrones.setChecked(True)
    d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.combo_fieldsize.setCurrentIndex(0)

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
    d.Zref.setText("3.0")  # anotación manual, sin cascada -- F3 exige completo
    d.Zmax.setText("2.7")
    return d


class TestFotonesConfigDeOroPorMaquina:
    """N31010/serie 1822 -- la MISMA cámara para las 3 máquinas (F0 §3).
    Round-trip completo, verificando la deducción/persistencia correcta del
    acelerador para cada una."""

    @pytest.mark.parametrize("ventana_cls, acelerador_esperado", MAQUINAS_FOTONES)
    def test_acelerador_se_deduce_correctamente(
            self, app, bd_temporal, monkeypatch, ventana_cls, acelerador_esperado):
        factory = _dialogo_factory(app, bd_temporal, monkeypatch, EQUIPO_FOTONES_ORO, ventana_cls)
        d = factory()
        assert d.acelerador_actual == acelerador_esperado

    @pytest.mark.parametrize("ventana_cls, acelerador_esperado", MAQUINAS_FOTONES)
    def test_roundtrip_completo_por_maquina(
            self, app, bd_temporal, monkeypatch, ventana_cls, acelerador_esperado):
        factory = _dialogo_factory(app, bd_temporal, monkeypatch, EQUIPO_FOTONES_ORO, ventana_cls)
        original = llenar_fotones_10x10(factory(), EQUIPO_FOTONES_ORO)
        assert original.visualize_calib.text() == "0.3036"
        assert original.combo_fieldsize.currentText() == "10x10 cm"
        original.guardar_db()

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        # buscar_por_fecha FILTRA por (Fecha, Acelerador) -- si acelerador_actual
        # se hubiera deducido mal, esta búsqueda devolvería None (H-F5).
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(
            fecha, original.acelerador_actual)
        assert datos_bd is not None, (
            f"registro no encontrado buscando por Acelerador={original.acelerador_actual!r} "
            f"-- ¿guardó con un valor de Acelerador distinto?")
        # B3-N: lo guardado es el nombre CANÓNICO (Clinac 600/Clinac iX/
        # Halcyon), aunque acelerador_actual siga siendo el código corto de
        # la calculadora -- buscar_por_fecha normaliza el parámetro de
        # búsqueda, así que el registro se encuentra igual (línea 186-190).
        assert datos_bd["Acelerador"] == nombre_canonico(acelerador_esperado)
        assert datos_bd["Modelo_equipo"] == "N31010"
        # Numero_serie persiste el ID del combo_series (currentData()), no el
        # string de serie -- nombre de columna heredado, algo engañoso.
        assert datos_bd["Numero_serie"] == str(EQUIPO_FOTONES_ORO["id"])
        assert datos_bd["dosis_maxima"] not in (None, "")

        cargado = factory()
        cargado.cargar_datos_desde_db(datos_bd)
        assert cargado.visualize_calib.text() == "0.3036"
        assert cargado.dosis_maxima.text() == original.dosis_maxima.text()
        assert cargado.Kq_0.text() == original.Kq_0.text() == "0.99"


class TestElectronesConfigDeOroSoloIX:
    """TN34001/serie 001069 -- única cámara/máquina con electrones (F0 §3)."""

    def test_acelerador_se_deduce_correctamente(self, app, bd_temporal, monkeypatch):
        factory = _dialogo_factory(app, bd_temporal, monkeypatch, EQUIPO_ELECTRONES_ORO, VentanaIX)
        d = factory()
        assert d.acelerador_actual == "IX"

    def test_roundtrip_completo_electrones_ix(self, app, bd_temporal, monkeypatch):
        factory = _dialogo_factory(app, bd_temporal, monkeypatch, EQUIPO_ELECTRONES_ORO, VentanaIX)
        original = llenar_electrones_10x10(factory(), EQUIPO_ELECTRONES_ORO)
        assert original.visualize_calib.text() == "0.08563"
        original.guardar_db()

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd is not None
        # B3-N: canónico ("Clinac iX"), no el código corto de la calculadora.
        assert datos_bd["Acelerador"] == "Clinac iX"
        assert datos_bd["Tipo_de_radiacion"] == "Electrones"
        assert datos_bd["Modelo_equipo"] == "TN34001"
        assert datos_bd["r50_medido"] == "5.127"

        cargado = factory()
        cargado.cargar_datos_desde_db(datos_bd)
        assert cargado.Kq0r50_widget.text() == original.Kq0r50_widget.text() == "0.91027"
        assert cargado.dosis_maxima.text() == original.dosis_maxima.text() == "0.0100396"
        assert cargado.Kq_0.text() == ""  # el kQ NO debe caer en el widget de fotones (E4)
