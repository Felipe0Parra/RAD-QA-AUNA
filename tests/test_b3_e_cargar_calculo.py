"""B3-e (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7e): botón "Cargar cálculo" con
menú en cascada por energía, filtrado al MES de `date_edit`.

Reemplaza el mecanismo de I1 (PLAN_FASE_I, 2026-07-16): antes, cambiar la
fecha disparaba `on_fecha_cambiada` -> `buscar_por_fecha` ->
`_confirmar_carga_registro` (pregunta silenciosa) -> `cargar_datos_desde_db`.
Ese mecanismo se retira por completo (decisión del físico, 2026-07-21):
`date_edit` queda como selector de fecha para un cálculo NUEVO, sin ningún
efecto de carga; cargar un registro guardado es ahora siempre una acción
explícita vía el botón "Cargar cálculo".
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

    def _crear(fecha_inicial=None, energias=("6mv", "15mv", "6mev")):
        return DialogCalculadoraDosis(
            energias=list(energias), parent=VentanaIX(), fecha_inicial=fecha_inicial)

    return _crear


def _guardar_directo(fecha, acelerador, energia, tipo_radiacion="Fotones", **extra):
    """Inserta un registro YA vigente vía el service, sin pasar por el
    diálogo -- construir el escenario de datos previos, no lo que se está
    probando."""
    datos = {
        "Fecha": fecha, "Acelerador": acelerador, "energia": energia,
        "Tipo_de_radiacion": tipo_radiacion, "dosis_maxima": "0.0101419",
    }
    datos.update(extra)
    assert DosisService.guardar_datos(datos) is True


class TestDateEditYaNoCargaNada:
    """Residuo de I1: cambiar la fecha no debe disparar ninguna consulta ni
    ninguna carga -- ese mecanismo se retiró por completo."""

    def test_cambiar_fecha_no_consulta_la_bd(self, dialogo_factory, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            dialogs_mod.DosisService, "buscar_por_fecha",
            staticmethod(lambda *a, **k: llamadas.append(a) or None))
        monkeypatch.setattr(
            dialogs_mod.DosisService, "buscar_vigente_del_mes",
            staticmethod(lambda *a, **k: llamadas.append(a) or None))

        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))
        dlg.date_edit.setDate(QDate(2026, 8, 1))

        assert llamadas == [], "cambiar la fecha ya no debe consultar nada"

    def test_cambiar_fecha_no_pisa_lo_tecleado(self, dialogo_factory):
        _guardar_directo("01/07/2026", "Clinac iX", "6mv", Zmax="9.987")
        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))
        dlg.Zmax.setText("5.5")

        dlg.date_edit.setDate(QDate(2026, 7, 1))

        assert dlg.Zmax.text() == "5.5"

    def test_on_fecha_cambiada_ya_no_existe(self, dialogo_factory):
        """El método murió con el mecanismo -- si alguien lo reintrodujera
        por accidente (copiar/pegar de una rama vieja), este test avisa."""
        dlg = dialogo_factory()
        assert not hasattr(dlg, "on_fecha_cambiada")
        assert not hasattr(dlg, "_confirmar_carga_registro")


class TestMenuCargarCalculo:

    def test_boton_existe_y_tiene_tooltip(self, dialogo_factory):
        dlg = dialogo_factory()
        assert dlg.btn_cargar_calculo.text() == "📂 Cargar cálculo"
        assert "vigente" in dlg.btn_cargar_calculo.toolTip().lower()

    def test_menu_lista_las_energias_agrupadas(self, dialogo_factory):
        dlg = dialogo_factory(energias=("6mv", "15mv", "6mev", "9mev"))
        etiquetas = []
        monkeypatch_menu = dlg.mostrar_menu_cargar_calculo
        # Se inspecciona construyendo el menú real (offscreen, no se
        # muestra) y leyendo sus acciones -- exec_() se sustituye para no
        # bloquear la corrida de tests.
        import ui.paginasGuia.dialogs as dm
        original_exec = dm.QMenu.exec_
        capturado = {}

        def _exec_falso(self_menu, *a, **k):
            capturado["acciones"] = [act.text() for act in self_menu.actions()]

        dm.QMenu.exec_ = _exec_falso
        try:
            dlg.mostrar_menu_cargar_calculo()
        finally:
            dm.QMenu.exec_ = original_exec

        acciones = capturado["acciones"]
        assert "Fotones:" in acciones
        assert "Electrones:" in acciones
        assert "6 MV" in acciones
        assert "15 MV" in acciones
        assert "6 MeV" in acciones
        assert "9 MeV" in acciones
        # el orden agrupado: fotones antes que electrones (mismo orden que
        # self.energias, igual que construir_botones_asignacion)
        assert acciones.index("Fotones:") < acciones.index("6 MV") < acciones.index("Electrones:")


class TestCargarCalculoDelMes:

    def test_carga_el_vigente_de_ese_mes(self, dialogo_factory):
        _guardar_directo("05/07/2026", "Clinac iX", "6mv", Zmax="7.777")
        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))

        dlg._cargar_calculo_del_mes("6mv")

        assert dlg.Zmax.text() == "7.777"

    def test_no_carga_el_vigente_de_otro_mes(self, dialogo_factory):
        """Alcance por MES (decisión de arquitecto, §7.7e): un vigente de
        junio no debe aparecer al abrir la calculadora en julio."""
        _guardar_directo("05/06/2026", "Clinac iX", "6mv", Zmax="7.777")
        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))

        dlg._cargar_calculo_del_mes("6mv")

        assert dlg.Zmax.text() == ""

    def test_sin_dato_avisa_y_no_revienta(self, dialogo_factory):
        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))
        dlg._cargar_calculo_del_mes("15mev")  # no debe lanzar
        assert dlg.Zmax.text() == ""

    def test_no_cruza_aceleradores(self, dialogo_factory):
        _guardar_directo("05/07/2026", "Clinac 600", "6mv", Zmax="1.234")
        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))  # abre como iX

        dlg._cargar_calculo_del_mes("6mv")

        assert dlg.Zmax.text() == ""

    def test_solo_carga_la_version_vigente_no_la_superada(self, dialogo_factory):
        _guardar_directo("02/07/2026", "Clinac iX", "6mv", Zmax="1.111")
        _guardar_directo("20/07/2026", "Clinac iX", "6mv", Zmax="2.222")  # baja la anterior
        dlg = dialogo_factory(fecha_inicial=QDate(2026, 7, 16))

        dlg._cargar_calculo_del_mes("6mv")

        assert dlg.Zmax.text() == "2.222"
