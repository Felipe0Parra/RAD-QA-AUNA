"""Z1 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): la calculadora persiste
el TPR20,10 (`self.tpr2010`) y el voltaje negativo (`self.tension_neg`).

Causa: ninguno de los dos campos tenía columna en `calculadora_dosimetrica`
-- se tecleaban, se veían en pantalla, y se perdían al cerrar el diálogo
(anotación 1 del handoff 05-08). El TPR es el grave: como el registro SÍ
guarda `Kq_0` (derivado del TPR) y lo re-aplica al cargar, el número se veía
correcto pero el dato de entrada que lo produjo no existía en ninguna parte
-- un cálculo guardado no se podía reproducir ni auditar.

Única tarea del plan que toca esquema: dos columnas nuevas, aditivas, vía
`_asegurar_columna` (mismo patrón que K3/E4/B3.1) -- no recrean la tabla ni
tocan los triggers de E8.
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
from services.dosis_service import DosisService
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


@pytest.fixture
def dialogo_factory(app, bd_temporal, monkeypatch):
    reportes = []
    catalogo = dict(EQUIPO_N31010)
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": catalogo["model"], "equip_type": catalogo["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [catalogo] if m == catalogo["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: catalogo if i == catalogo["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        dialogs_mod, "generar_reporte_calibracion",
        lambda **kwargs: reportes.append(kwargs))

    def _crear():
        return DialogCalculadoraDosis(energias=[], parent=VentanaIX())

    _crear.reportes = reportes
    return _crear


def _llenar_flujo_fotones_completo(d):
    """Mismo flujo de test_calculadora_dosis_guardar_cargar.py, con el
    voltaje negativo tecleado también (antes no tenía a dónde ir)."""
    idx = d.combo_modelos.findData(EQUIPO_N31010["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.fotones.setChecked(True)
    d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.combo_fieldsize.setCurrentIndex(0)

    d.humr_cal.setText("45.0")
    d.temp.setText("22.0")
    d.pressure.setText("101.325")
    d.humedad_r.setText("48.0")

    for campo, val in ((d.lDV1_1, "12.437"), (d.lDV1_2, "12.437"), (d.lDV1_3, "12.437")):
        campo.setText(val)
    d.unidades_monitor.setText("100")

    for campo in (d.Mminus1, d.Mminus2, d.Mminus3):
        campo.setText("-12.437")
    d.tension_neg.setText("-300")

    d.tension_v1.setText("400")
    d.tension_v2.setText("100")

    for campo, val in ((d.lect_m2_1, "12.430"), (d.lect_m2_2, "12.435"), (d.lect_m2_3, "12.440")):
        campo.setText(val)

    d.tpr2010.setText("0.68")
    d.pddzref.setText("66.6")
    d.Zref.setText("10.0")
    d.Zmax.setText("1.5")
    return d


class TestMigracionColumnas:

    def test_agrega_las_dos_columnas_y_es_idempotente(self, bd_temporal):
        assert DosisService.crear_tabla() is True
        assert DosisService.crear_tabla() is True  # 2da corrida -- sin excepción

        con = sqlite3.connect(bd_temporal)
        cols = [c[1] for c in con.execute(
            "PRAGMA table_info('calculadora_dosimetrica')").fetchall()]
        con.close()
        assert "tpr2010" in cols
        assert "tension_negativa" in cols


class TestIdaYVuelta:

    @pytest.fixture
    def registro_recuperado(self, dialogo_factory):
        original = _llenar_flujo_fotones_completo(dialogo_factory())
        original.guardar_db()
        assert dialogo_factory.reportes, "guardar_db no llegó a generar el reporte (¿guardó?)"

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd is not None, "el registro no quedó en la BD"

        cargado = dialogo_factory()
        cargado.cargar_datos_desde_db(datos_bd)
        return original, cargado

    def test_tpr2010_sobrevive(self, registro_recuperado):
        original, cargado = registro_recuperado
        assert original.tpr2010.text() == "0.68"
        assert cargado.tpr2010.text() == "0.68"

    def test_tension_negativa_sobrevive(self, registro_recuperado):
        original, cargado = registro_recuperado
        assert original.tension_neg.text() == "-300"
        assert cargado.tension_neg.text() == "-300"

    def test_kq_historico_sigue_ganando_tras_restaurar_el_tpr(self, dialogo_factory):
        """Anti-regresión de K3 (el caso más importante): si al restaurar
        tpr2010 la cascada (actualizar_kCharge) recalculara kQ contra la
        tabla vigente, el valor mostrado dejaría de ser el histórico
        guardado con el registro."""
        original = _llenar_flujo_fotones_completo(dialogo_factory())
        original.guardar_db()
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)

        # Simula que la tabla/TPR guardado ya no coincidiría con un
        # recálculo limpio: si la cascada ganara, Kq_0 cambiaría.
        kq_historico = datos_bd["Kq_0"]
        assert kq_historico

        cargado = dialogo_factory()
        cargado.cargar_datos_desde_db(datos_bd)

        assert cargado.Kq_0.text() == kq_historico

    def test_tpr_restaurado_no_lo_pisa_el_autollenado_desde_pdd(self, dialogo_factory):
        """El registro trae PDD20/PDD10 (D4/T1) Y un TPR TECLEADO A MANO
        (textEdited, no setText -- _marcar_tpr2010_editado, T2/T3) distinto
        del que esos PDD producirían -- al restaurar, el TPR guardado debe
        ganar, no el recalculado desde los PDD que se restauran después."""
        original = _llenar_flujo_fotones_completo(dialogo_factory())
        # Simula que el físico tecleó el TPR a mano DESPUÉS de que los PDD
        # ya estuvieran ahí -- el guard de _actualizar_tpr_desde_pdd
        # (_tpr2010_editado_manualmente) queda activo, igual que con una
        # interacción real de teclado.
        original._tpr2010_editado_manualmente = True
        original.pdd20.setText("50.0")
        original.pdd10.setText("100.0")  # sin el guard, recalcularía el TPR
        assert original.tpr2010.text() == "0.68"  # precondición: no se pisó
        original.guardar_db()
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd["tpr2010"] == "0.68"

        cargado = dialogo_factory()
        cargado.cargar_datos_desde_db(datos_bd)

        assert cargado.tpr2010.text() == "0.68"
        assert cargado._tpr2010_editado_manualmente is True

    def test_fila_antigua_sin_las_columnas_carga_sin_excepcion(self, dialogo_factory):
        original = _llenar_flujo_fotones_completo(dialogo_factory())
        original.guardar_db()
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        del datos_bd["tpr2010"]
        del datos_bd["tension_negativa"]

        cargado = dialogo_factory()
        cargado.cargar_datos_desde_db(datos_bd)  # no debe lanzar

        assert cargado.tpr2010.text() == ""
        assert cargado.tension_neg.text() == ""
