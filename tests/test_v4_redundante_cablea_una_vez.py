"""V.4 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md): la Calibración Redundante
cablea sus botones UNA sola vez.

CAUSA medida en el plan (§1.5): `CalRedundanteFuente.__init__` llama a
`super().__init__(user_id)` -- que ya ejecuta `self.button_click()`
(`braq_mensual.py:42`) -- y después vuelve a llamar `self.button_click()`
(`braquiterapia.py`, dentro de `CalRedundanteFuente.__init__`). Cada botón
queda conectado dos veces: "Guardar" guarda, anula y vuelve a guardar
(`EB2b`), con dos filas de auditoría y dos avisos; el botón de PDF llama
dos veces a `guardarPDF_mensual`.
"""
import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
import ui.paginasControles.PruebasDiarias.braquiterapia as braquiterapia_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import CalRedundanteFuente
from _bd_referencia import BD_REBUILD_21_09


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_copia_real(monkeypatch, tmp_path):
    """Copia REAL de `Rebuild_21-09` -- nunca se conecta directo a la BD de
    referencia (regla de sesión)."""
    if not BD_REBUILD_21_09.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_21_09.name}")
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    conection_mod.Conexion._instance = None
    yield copia
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None


class _UsuarioFalso:
    def __init__(self, nombre="Físico de Prueba"):
        self._nombre = nombre
        self.nombre = nombre
        self.id = 1

    def __getattr__(self, item):
        return None


# Las 8 señales que el plan nombra (§V.4, protocolo de verificación):
# btn_add.clicked, aceptar.clicked, btn_submit.clicked, btn_clean.clicked,
# date_box.dateChanged, menu_graficar.currentTextChanged, edit_table/
# accept_edit/cancel_edit/btn_delete.clicked y search_bar.textChanged.
SENALES = [
    ("btn_add", "clicked"),
    ("aceptar", "clicked"),
    ("btn_submit", "clicked"),
    ("btn_clean", "clicked"),
    ("date_box", "dateChanged"),
    ("menu_graficar", "currentTextChanged"),
    ("edit_table", "clicked"),
    ("accept_edit", "clicked"),
    ("cancel_edit", "clicked"),
    ("btn_delete", "clicked"),
    ("search_bar", "textChanged"),
]


def _receptores(obj, atributo, nombre_senal):
    widget = getattr(obj, atributo)
    senal = getattr(widget, nombre_senal)
    return widget.receivers(senal)


# ---------------------------------------------------------------------------
# Lo nuevo: los receptores de la redundante son EXACTAMENTE los del mensual.
# ---------------------------------------------------------------------------

class TestReceptoresIgualesAlMensual:

    def test_cada_senal_tiene_los_mismos_receptores_que_el_mensual(self, app, bd_copia_real):
        mensual = PruebaMensualBraq(_UsuarioFalso())
        redundante = CalRedundanteFuente(_UsuarioFalso())

        diferencias = []
        for atributo, nombre_senal in SENALES:
            r_mensual = _receptores(mensual, atributo, nombre_senal)
            r_redundante = _receptores(redundante, atributo, nombre_senal)
            if r_redundante != r_mensual:
                diferencias.append((atributo, nombre_senal, r_mensual, r_redundante))
        assert diferencias == [], (
            "receptores distintos entre el mensual y la redundante: "
            f"{diferencias}")

    def test_las_tres_senales_medidas_en_el_plan(self, app, bd_copia_real):
        """§1.5: `btn_add`=2/4, `aceptar`=3/4, `date_box.dateChanged`=8/15
        en HEAD (con el bug); después del arreglo, la redundante iguala
        al mensual en las tres."""
        mensual = PruebaMensualBraq(_UsuarioFalso())
        redundante = CalRedundanteFuente(_UsuarioFalso())

        assert _receptores(redundante, "btn_add", "clicked") == \
            _receptores(mensual, "btn_add", "clicked")
        assert _receptores(redundante, "aceptar", "clicked") == \
            _receptores(mensual, "aceptar", "clicked")
        assert _receptores(redundante, "date_box", "dateChanged") == \
            _receptores(mensual, "date_box", "dateChanged")


# ---------------------------------------------------------------------------
# Lo viejo sigue igual: la tarea NO toca braq_mensual.py.
# ---------------------------------------------------------------------------

class TestElMensualNoCambia:

    def test_receptores_del_mensual_son_los_medidos_en_el_plan(self, app, bd_copia_real):
        mensual = PruebaMensualBraq(_UsuarioFalso())
        assert _receptores(mensual, "btn_add", "clicked") == 2
        assert _receptores(mensual, "aceptar", "clicked") == 3
        assert _receptores(mensual, "date_box", "dateChanged") == 8


# ---------------------------------------------------------------------------
# Por el camino del usuario: un clic en "Guardar" guarda una sola vez.
# ---------------------------------------------------------------------------

class TestUnClicGuardaUnaSolaVez:

    def test_guardar_ejecuta_guardar_resultado_cambiofuente_una_sola_vez(
            self, app, bd_copia_real, monkeypatch):
        llamadas = []
        original = braq_mensual_mod.guardar_resultado_CambioFuente

        def _espia(*args, **kwargs):
            llamadas.append((args, kwargs))
            return original(*args, **kwargs)

        monkeypatch.setattr(braq_mensual_mod, "guardar_resultado_CambioFuente", _espia)

        redundante = CalRedundanteFuente(_UsuarioFalso())
        assert redundante._tipo_calibracion_seleccionado() == "Calibración Redundante"
        # ref 24: única "Calibración Redundante" del 2025-12-29 (ref 17,
        # mismo día, tiene tipo vacío -- la discriminación por tipo, C1,
        # no debe confundirlas).
        redundante.date_box.setDate(QDate(2025, 12, 29))
        # "Guardar" nace deshabilitado (`checkBotonesFinales`, DA-37); esta
        # prueba mide el CABLEADO, no la lógica de habilitación -- se
        # habilita a mano, como si el físico ya hubiera contestado todo.
        redundante.btn_add.setEnabled(True)

        redundante.btn_add.click()

        assert len(llamadas) == 1, (
            f"se esperaba 1 llamada a guardar_resultado_CambioFuente, "
            f"hubo {len(llamadas)}")

    def test_pdf_se_genera_una_sola_vez(self, app, bd_copia_real, monkeypatch):
        """(Segunda ronda, §1.5): el botón de PDF de la redundante llama
        dos veces a `guardarPDF_mensual` en HEAD."""
        llamadas = []
        original = braq_mensual_mod.guardarPDF_mensual

        def _espia(*args, **kwargs):
            llamadas.append((args, kwargs))
            return None

        monkeypatch.setattr(braq_mensual_mod, "guardarPDF_mensual", _espia)

        redundante = CalRedundanteFuente(_UsuarioFalso())
        redundante.date_box.setDate(QDate(2025, 12, 29))

        redundante.btn_submit.click()

        assert len(llamadas) == 1, (
            f"se esperaba 1 llamada a guardarPDF_mensual, hubo {len(llamadas)}")
