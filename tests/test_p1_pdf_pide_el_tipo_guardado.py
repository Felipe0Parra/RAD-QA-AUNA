"""P.1 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, segunda ronda): el PDF
pide el tipo con el que se guardó.

CAUSA (§1.11): el botón de PDF decidía el tipo con `es_cambio_fuente`
(nada lo crea en producción) y `cambio_cal` (el widget real del botón
"Cambio de Fuente" es `red_cal` -- `cambio_cal` solo existía en la
columna duplicada, sin usar, de `preguntas_mensualBraqui`) -- por eso el
PDF salía siempre "Control Mensual", y en un día con dos calibraciones
imprimía la otra. Ahora usa la MISMA regla que ya usan
`guardar_DB`/`actualizar_ref_bd`: `_tipo_calibracion_seleccionado()`.

PROTOCOLO DE VERIFICACIÓN (a)/(b) del plan: por el camino del usuario
(marcar el botón, clic en "PDF"), contra una copia real de
`BaseDatosQA(Rebuild_21-09-2026).db` -- mismo patrón que
`test_v4_redundante_cablea_una_vez.py`."""
import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from models.PDF.Mensuales.reportes_mensuales import _obtener_referencia_braquiterapia
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
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


def _espiar_guardarpdf(monkeypatch):
    llamadas = []

    def _espia(*args, **kwargs):
        llamadas.append((args, kwargs))
        return None

    monkeypatch.setattr(braq_mensual_mod, "guardarPDF_mensual", _espia)
    return llamadas


class TestElPdfPideElTipoConElQueSeGuardo:
    def test_boton_cambio_de_fuente_pide_tipo_cambio_de_fuente(self, app, bd_copia_real, monkeypatch):
        llamadas = _espiar_guardarpdf(monkeypatch)

        obj = PruebaMensualBraq(_UsuarioFalso())
        obj.pri_cal.setChecked(False)
        obj.red_cal.setChecked(True)

        obj.btn_submit.click()

        assert len(llamadas) == 1
        _, kwargs = llamadas[0]
        assert kwargs["tipo_reporte"] == "Cambio de fuente"

    def test_boton_control_mensual_pide_tipo_control_mensual(self, app, bd_copia_real, monkeypatch):
        llamadas = _espiar_guardarpdf(monkeypatch)

        obj = PruebaMensualBraq(_UsuarioFalso())
        obj.red_cal.setChecked(False)
        obj.pri_cal.setChecked(True)

        obj.btn_submit.click()

        assert len(llamadas) == 1
        _, kwargs = llamadas[0]
        assert kwargs["tipo_reporte"] == "Control Mensual"

    def test_calibracion_redundante_pide_su_propio_tipo(self, app, bd_copia_real, monkeypatch):
        llamadas = _espiar_guardarpdf(monkeypatch)

        redundante = CalRedundanteFuente(_UsuarioFalso())

        redundante.btn_submit.click()

        assert len(llamadas) == 1
        _, kwargs = llamadas[0]
        assert kwargs["tipo_reporte"] == "Calibración Redundante"


class TestElPdfImprimeSuPropioControl:
    """(a) del protocolo, completo: por el camino del usuario (marcar el
    botón, elegir la fecha, clic en PDF) y con el resolutor REAL del
    reporte (`_obtener_referencia_braquiterapia`) sobre la copia real. Con
    dos calibraciones el mismo día -- 26-06-2026 (ids 30 y 33) y
    26-04-2026 (ids 28 y 34) -- el control que se imprimiría es el suyo;
    en `HEAD` el PDF pedía "Control Mensual", el resolutor no hallaba
    ninguno de ese tipo ese día, caía a "el de id más alto" y salía la
    OTRA (33 y 34)."""

    def _ref_que_se_imprimiria(self, pantalla, llamadas):
        _, kwargs = llamadas[-1]
        db = pantalla.opeenDatabase()
        try:
            return _obtener_referencia_braquiterapia(
                db, kwargs["fecha"], kwargs["tipo_reporte"])
        finally:
            db.close()

    @pytest.mark.parametrize("fecha, ref_esperado", [
        (QDate(2026, 6, 26), 30),
        (QDate(2026, 4, 26), 28),
    ])
    def test_cambio_de_fuente_imprime_el_suyo_no_la_redundante(
            self, app, bd_copia_real, monkeypatch, fecha, ref_esperado):
        llamadas = _espiar_guardarpdf(monkeypatch)
        obj = PruebaMensualBraq(_UsuarioFalso())
        obj.date_box.setDate(fecha)
        obj.pri_cal.setChecked(False)
        obj.red_cal.setChecked(True)

        obj.btn_submit.click()

        assert self._ref_que_se_imprimiria(obj, llamadas) == ref_esperado

    def test_control_mensual_imprime_el_control_mensual(
            self, app, bd_copia_real, monkeypatch):
        """2026-03-30 tiene un único "Control Mensual" (id 29)."""
        llamadas = _espiar_guardarpdf(monkeypatch)
        obj = PruebaMensualBraq(_UsuarioFalso())
        obj.date_box.setDate(QDate(2026, 3, 30))
        obj.red_cal.setChecked(False)
        obj.pri_cal.setChecked(True)

        obj.btn_submit.click()

        _, kwargs = llamadas[-1]
        assert kwargs["tipo_reporte"] == "Control Mensual"
        assert self._ref_que_se_imprimiria(obj, llamadas) == 29

    @pytest.mark.parametrize("fecha, ref_esperado", [
        (QDate(2026, 6, 26), 33),
        (QDate(2026, 4, 26), 34),
    ])
    def test_redundante_imprime_la_redundante(
            self, app, bd_copia_real, monkeypatch, fecha, ref_esperado):
        llamadas = _espiar_guardarpdf(monkeypatch)
        redundante = CalRedundanteFuente(_UsuarioFalso())
        redundante.date_box.setDate(fecha)

        redundante.btn_submit.click()

        assert self._ref_que_se_imprimiria(redundante, llamadas) == ref_esperado


class TestElEncabezadoDeLaRedundanteEsElSuyo:
    """(b) del protocolo: la redundante muestra su propio título en
    pantalla -- antes usaba, por el mismo defecto de `hasattr(self,
    'es_cambio_fuente')`, el título del mensual."""

    def test_titulo_de_la_redundante_es_el_de_actividad_no_el_del_mensual(self, app, bd_copia_real):
        redundante = CalRedundanteFuente(_UsuarioFalso())
        mensual = PruebaMensualBraq(_UsuarioFalso())

        assert redundante.title1.text() == "Verificacion de la Actividad de la Fuente de Braquiterapia"
        assert mensual.title1.text() == "Control de calidad Mensual de Braquiterapia"
        assert redundante.title1.text() != mensual.title1.text()
