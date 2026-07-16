"""I1 (PLAN_FASE_I, 2026-07-16): la calculadora pregunta antes de recargar
un registro guardado.

Caso real del físico (16-07): tras "Aceptar y cerrar", reabrir la calculadora
desde el formulario mensual volvía a mostrar TODOS los valores del registro
recién guardado ("valores pegados"). Causa: el setDate de fecha_inicial (H3.4)
dispara dateChanged -> on_fecha_cambiada -> buscar_por_fecha ->
cargar_datos_desde_db, en silencio. Ahora esa carga exige confirmación
explícita (_confirmar_carga_registro, default No) y la búsqueda filtra por
MÁQUINA (antes pasaba equipo_id como parámetro acelerador).
"""
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QDate

from data.ManejoDatos import conection as conection_mod
import ui.paginasGuia.dialogs as dialogs_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis
from services.dosis_service import DosisService


EQUIPO = {"id": 1, "equip_type": "Cámara de ionización", "model": "N31010",
          "serie": "1822", "calibr_fact": 0.3045, "t_cal": 22.0,
          "p_cal": 101.325, "h_cal": 50.0}

REGISTRO_JULIO = {
    "Fecha": "01/07/2026", "Acelerador": "IX",
    "Tipo_de_radiacion": "Electrones", "Tipo_de_escaneo": "Pulsed",
    "Tipo_de_medicion": "SSD",
    "lectura_Q1": "111.1", "lectura_Q2": "222.2", "lectura_Q3": "333.3",
    "Zmax": "9.987", "unidades_monitor": "100",
}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (el diálogo deduce la máquina)."""


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
        staticmethod(lambda: [{"model": EQUIPO["model"],
                               "equip_type": EQUIPO["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [EQUIPO] if m == EQUIPO["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: EQUIPO if i == EQUIPO["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo,
                            staticmethod(lambda *a, **k: None))

    def _crear(fecha_inicial=None, confirmar_carga=False):
        """confirmar_carga: respuesta simulada del físico (default No). El
        diálogo expone `preguntas_capturadas` con cada fecha por la que se
        preguntó -- OJO: no sirve un tripwire que lance AssertionError,
        porque on_fecha_cambiada envuelve todo en `except Exception` y lo
        tragaría en silencio. Se sobreescribe por SUBCLASE (no por atributo
        de instancia) porque la pregunta puede dispararse durante el propio
        __init__ (el setDate de fecha_inicial) y PyQt no permite tocar la
        instancia antes de inicializar QDialog."""
        preguntas = []

        class _Dialogo(DialogCalculadoraDosis):
            def _confirmar_carga_registro(self, fecha):
                preguntas.append(fecha)
                return confirmar_carga

        dlg = _Dialogo(energias=[], parent=VentanaIX(),
                       fecha_inicial=fecha_inicial)
        dlg.preguntas_capturadas = preguntas
        return dlg

    return _crear


class TestI1CargaConsciente:

    def test_reabrir_con_no_deja_el_formulario_limpio(self, dialogo_factory):
        """El caso del físico: guardar y reabrir NO debe repoblar nada."""
        assert DosisService.guardar_datos(dict(REGISTRO_JULIO)) is True

        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16),
                              confirmar_carga=False)

        assert dlg.date_edit.date() == QDate(2026, 7, 1)  # H3.4 intacto
        assert dlg.lDV1_1.text() == ""
        assert dlg.Zmax.text() == ""
        assert dlg.unidades_monitor.text() == ""
        assert not dlg.electrones.isChecked()

    def test_reabrir_con_si_carga_el_registro(self, dialogo_factory):
        """La consulta de registros históricos (D2.2/E4) sigue disponible."""
        assert DosisService.guardar_datos(dict(REGISTRO_JULIO)) is True

        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16),
                              confirmar_carga=True)

        assert dlg.lDV1_1.text() == "111.1"
        assert dlg.Zmax.text() == "9.987"
        assert dlg.electrones.isChecked()

    def test_mes_sin_registro_no_pregunta(self, dialogo_factory):
        """Sin registro para la fecha, jamás aparece el diálogo."""
        assert DosisService.guardar_datos(dict(REGISTRO_JULIO)) is True

        dlg = dialogo_factory(fecha_inicial=QDate(2026, 6, 16))

        assert dlg.preguntas_capturadas == []
        assert dlg.lDV1_1.text() == ""

    def test_no_al_cambiar_fecha_no_pisa_lo_tecleado(self, dialogo_factory):
        """Cambiar la fecha a una con registro, y responder No, conserva lo
        que el físico ya llevaba tecleado."""
        assert DosisService.guardar_datos(dict(REGISTRO_JULIO)) is True

        dlg = dialogo_factory(fecha_inicial=QDate(2026, 6, 16),
                              confirmar_carga=False)
        dlg.Zmax.setText("5.5")
        dlg.unidades_monitor.setText("200")

        dlg.date_edit.setDate(QDate(2026, 7, 1))  # dispara on_fecha_cambiada

        assert dlg.Zmax.text() == "5.5"
        assert dlg.unidades_monitor.text() == "200"

    def test_busca_filtrando_por_maquina_no_por_equipo_id(
            self, dialogo_factory, monkeypatch):
        """El 2º argumento de buscar_por_fecha debe ser el Acelerador. El
        código anterior pasaba equipo_id (None al abrir -> traía registros de
        CUALQUIER máquina; un entero con serie elegida -> nunca hacía match).
        """
        llamadas = []

        def _espia(fecha, acelerador):
            llamadas.append((fecha, acelerador))
            return None

        monkeypatch.setattr(dialogs_mod.DosisService, "buscar_por_fecha",
                            staticmethod(_espia))

        dialogo_factory(fecha_inicial=QDate(2026, 7, 16))

        assert llamadas, "on_fecha_cambiada no consultó la BD"
        assert all(acel == "IX" for _, acel in llamadas), llamadas

    def test_registro_de_otra_maquina_no_dispara_pregunta(
            self, dialogo_factory):
        """Registro guardado por el 600 en la misma fecha: el diálogo del iX
        ni pregunta ni carga (el filtro por máquina va en la consulta)."""
        registro_600 = dict(REGISTRO_JULIO, Acelerador="Seiscientos")
        assert DosisService.guardar_datos(registro_600) is True

        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))

        assert dlg.preguntas_capturadas == []
        assert dlg.lDV1_1.text() == ""
