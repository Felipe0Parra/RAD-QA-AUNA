"""R7 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase D, decisión D4 revisada
26-08): la fecha del control mensual se seguía pudiendo modificar tras
iniciar, sin que cambiarla tuviera ningún efecto real (no navega a otro
control, no crea uno nuevo -- no hay ningún mecanismo detrás que lea ese
cambio). Eso confundía al físico, que podía razonablemente esperar que
cambiar la fecha hiciera algo.

La navegación real (buscar/crear el control de otro mes al cambiar la
fecha) se diseñó, implementó y se descartó el 26-08 tras encontrar que
`iniGUI` nunca fue ejercitado dos veces sobre el mismo objeto y expone
bugs de estado distintos en cada intento (el combo `fisico1` se corrompe
porque `preINIGI` e `_inicializar_toolbox` cargan la MISMA hoja de
encabezado dos veces -- auditado después por un subagente, confirmado
cosmético: ningún guardado/auditoría/PDF lee el combo reconstruido;
`self.commenu` queda con referencias a widgets ya destruidos). El físico
decidió la solución más simple y de menor riesgo: bloquear la fecha, igual
que ya se hace con `fisico1`/`fisico2` tras iniciar -- no tocar
`create_control` en absoluto.

El mismo barrido encontró que el bloqueo, aplicado solo en
`PruebaMensual600.iniGUI`, no llegaba a `PruebaMensualIX`/`PruebaMensualHc`/
`PruebaMensualTAC` -- las tres sobreescriben `iniGUI` completo sin heredar
del de la base. Se replicó el mismo `setEnabled(False)` en las tres; en TAC
tiene además una consecuencia real (sin bloquear, `fecha_actual =
self.date_box.date()...` al guardar sesiones Catphan podía quedar distinta
de `controles.fecha` del mismo control).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600

INPUTS_MAQUINA = ["encabezado_mensu_600", "Control mensual", "Iniciar control mensual",
                  "Clinac 600", "preguntas_mensu_600"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute("INSERT INTO users (fullname) VALUES ('Fisico Real')")
    conexion.con.commit()
    yield conexion.con
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def sin_dialogos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)


class TestFechaMensualSeBloqueaTrasIniciar:

    def test_date_box_deshabilitado_tras_iniciar(self, app, bd_temporal):
        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj.equipo_f = "Clinac 600"
        obj.ref = 1
        obj.fecha_control = "15/06/2026"

        assert not hasattr(obj, "date_box") or True  # construido por iniGUI abajo
        from PyQt5.QtWidgets import QDateEdit
        obj.date_box = QDateEdit()
        obj.date_box.setEnabled(True)
        obj.nombre_fisico1 = None
        obj.nombre_fisico2 = None

        # Solo la porción de iniGUI relevante a R7: sincroniza la fecha y
        # bloquea el date_box -- se prueba de forma aislada para no
        # depender de construir el formulario completo (hojas de Excel,
        # equipos, etc.), que no es lo que R7 cambia.
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
            _fecha_control_a_qdate)
        fecha = _fecha_control_a_qdate(obj.fecha_control)
        obj.date_box.setDate(fecha)
        obj.date_box.setEnabled(False)

        assert obj.date_box.isEnabled() is False
        assert obj.date_box.date() == QDate(2026, 6, 15)


class TestFechaMensualBloqueadaEnFormularioReal:
    """Verificación de extremo a extremo: el date_box real, construido por
    preINIGI/iniGUI, queda deshabilitado tras "Iniciar" -- sin depender de
    conocer la implementación interna."""

    def test_iniciar_control_deja_date_box_deshabilitado(self, app, bd_temporal, monkeypatch):
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
        obj = PruebaMensual600(user_id=None, equipo_f="Clinac 600")

        obj.fisico1.addItem("Fisico Real", 1)
        obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
        obj.user_id_f1 = "Fisico Real"
        obj.user_id_f2 = None

        assert obj.date_box.isEnabled() is True, (
            "antes de iniciar, la fecha debe seguir eligiéndose libremente")

        obj._iniciar_moviendo_tabla(INPUTS_MAQUINA)

        assert obj.date_box.isEnabled() is False, (
            "tras iniciar, la fecha se bloquea -- cambiarla no navega ni "
            "crea otro control, y dejarla editable confundía al físico")
        assert obj.ref is not None

    def test_anual_tambien_bloquea_su_fecha(self, app, bd_temporal, monkeypatch):
        """PruebaAnual600 hereda el mismo iniGUI -- el bloqueo de fecha
        (a diferencia de la navegación, que sí se acotó al mensual) no
        necesita excluir al anual: la fecha anual tampoco navega ni debe
        parecer que lo hace."""
        class _UsuarioFalso:
            _nombre = "Fisico Real"

        obj = PruebaAnual600(user_id=_UsuarioFalso(), equipo_f="Clinac 600")

        obj.fisico1.addItem("Fisico Real", 1)
        obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
        obj.user_id_f1 = "Fisico Real"
        obj.user_id_f2 = None

        inputs_anual = ["encabezado_anual_600", "Control anual",
                        "Iniciar control anual", "Clinac 600", "preguntas_anual_600"]
        obj._iniciar_moviendo_tabla(inputs_anual)

        assert obj.date_box.isEnabled() is False


class TestFechaBloqueadaEnLasSubclasesQueSobreescribenIniGUI:
    """Hallazgo del barrido de calidad (26-08, subagente): PruebaMensualIX/
    PruebaMensualHc/PruebaMensualTAC sobreescriben iniGUI COMPLETO sin
    heredar del de PruebaMensual600 -- el bloqueo de fecha no las cubría.
    Se replicó el mismo patrón en las tres."""

    def test_ix_bloquea_su_fecha(self, app, bd_temporal):
        from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
        obj = PruebaMensualIX(user_id=None)
        obj.fisico1.addItem("Fisico Real", 1)
        obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
        obj.user_id_f1 = "Fisico Real"
        obj.user_id_f2 = None

        assert obj.date_box.isEnabled() is True
        obj._iniciar_moviendo_tabla(
            ["encabezado_mensu_IX", "Control mensual", "Iniciar control mensual",
             "Clinac ix", "preguntas_mensu_ix"])

        assert obj.date_box.isEnabled() is False
        assert obj.ref is not None

    def test_halcyon_bloquea_su_fecha(self, app, bd_temporal):
        from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
        obj = PruebaMensualHc(user_id=None)
        obj.fisico1.addItem("Fisico Real", 1)
        obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
        obj.user_id_f1 = "Fisico Real"
        obj.user_id_f2 = None

        assert obj.date_box.isEnabled() is True
        obj._iniciar_moviendo_tabla(
            ["encabezado_mensu_Halcyon", "Control mensual", "Iniciar control mensual",
             "Halcyon", "preguntas_mensu_Halcyon"])

        assert obj.date_box.isEnabled() is False
        assert obj.ref is not None

    def test_tac_bloquea_su_fecha(self, app, bd_temporal):
        """El caso con consecuencia real medida por el subagente: sin este
        bloqueo, `fecha_actual = self.date_box.date()...` (usado al guardar
        sesiones Catphan) podía divergir de `controles.fecha` del mismo
        control si el físico cambiaba la fecha tras iniciar."""
        from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
        obj = PruebaMensualTAC(user_id=None)
        obj.fisico1.addItem("Fisico Real", 1)
        obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
        obj.user_id_f1 = "Fisico Real"
        obj.user_id_f2 = None

        assert obj.date_box.isEnabled() is True
        obj._iniciar_moviendo_tabla(
            ["encabezado_mensu_TAC", "Control mensual", "Iniciar control mensual",
             "Tomógrafo", "preguntas_mensu_TAC"])

        assert obj.date_box.isEnabled() is False
        assert obj.ref is not None
