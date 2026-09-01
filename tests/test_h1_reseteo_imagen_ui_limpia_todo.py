"""H1 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): `resetear_imagen_ui`
(`braquiterapia.py:930`) dejaba vivas las dos variables que de verdad se
guardan -- `self.archivo` (el BLOB/ruta que persiste `add_info`) y
`self.resultado_label` (la fuente de los 6 números que lee
`guardar_datos()`). Ninguna de las dos se limpiaba al "resetear", así que
sobrevivían a un cambio de día -- la raíz medida de la fila 447 del handoff
(el 31-08 quedó con el análisis del 28-08, sin imagen).

También dejaba el canvas sin repintar (`figure.clear()` sin `canvas.draw()`):
el físico veía la placa anterior hasta que algo (p. ej. el zoom) forzaba un
repintado real.

Protocolo del plan: construir el formulario, simular una imagen ya
analizada, llamar `resetear_imagen_ui()`, y comprobar los cinco: `archivo is
None`, `imagen_path is None`, `resultado_label.text() == ""`,
`figure.axes == []`, y que `guardar_datos()` devuelva la tupla vacía.

Trampa 2 (CLAUDE.md): `QMessageBox` mockeado ANTES de construir la pantalla
-- `PruebaDiariaBraq.__init__` calcula la actividad esperada y puede avisar.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
        "certificado, fecha_cer, intensidad, conversion, activo) "
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, 10.0, "
        "1.0, 1)",
        (FECHA_FUENTE, FECHA_FUENTE))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _simular_imagen_analizada(d, ruta_archivo):
    """Reproduce el estado que deja un análisis real, sin ejercitar
    `analizar_lineas` (necesitaría una imagen radiográfica real de disco)."""
    d.archivo = ruta_archivo
    d.imagen_path = ruta_archivo
    d.figure.add_subplot(111).plot([1, 2, 3])
    d.canvas.draw()
    d.mostrar_texto([
        "Distancias entre líneas (mm): [10.03, 10.16, 10.03]",
        "Promedio = 10.01 mm",
        "Desviación estándar = 0.11 mm",
    ])


class TestH1ReseteoLimpiaTodoElEstadoDeImagen:
    def test_los_cinco_quedan_limpios(self, app, bd_temporal, tmp_path):
        d = PruebaDiariaBraq(_UsuarioFalso())
        archivo_falso = str(tmp_path / "placa.jpg")
        open(archivo_falso, "wb").close()
        _simular_imagen_analizada(d, archivo_falso)
        assert d.guardar_datos() != ("", None, None, "", None, None), (
            "precondición: antes de resetear debe haber algo que perder")
        assert d.figure.axes != [], "precondición: la figura debe tener contenido"

        d.resetear_imagen_ui()

        assert d.archivo is None, (
            "self.archivo (el BLOB que add_info persiste) sobrevivía al "
            "reseteo -- raíz de la fila 447 del handoff")
        assert d.imagen_path is None
        assert d.resultado_label.text() == "", (
            "self.resultado_label (fuente de los 6 números de "
            "guardar_datos()) sobrevivía al reseteo")
        assert d.figure.axes == [], "figure.clear() debe dejar la figura vacía"
        assert d.guardar_datos() == ("", None, None, "", None, None), (
            "tras resetear, guardar_datos() no puede devolver ni un solo "
            "número (intuición de garantía de H1)")

    def test_el_canvas_se_repinta(self, app, bd_temporal, tmp_path):
        """El punto 3 de H1: `figure.clear()` no repinta por sí solo -- el
        físico veía la placa anterior hasta mover la rueda del zoom (primer
        repintado real). Se comprueba que `canvas.draw()` corre de verdad."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        llamadas = []
        d.canvas.draw = lambda *a, **k: llamadas.append(1)
        d.figure.add_subplot(111).plot([1, 2, 3])

        d.resetear_imagen_ui()

        assert llamadas, (
            "resetear_imagen_ui() debe llamar a canvas.draw() tras "
            "figure.clear() -- si no, el canvas sigue mostrando el render "
            "anterior hasta el próximo repintado accidental")

    def test_resetear_sin_haber_analizado_nada_no_revienta(self, app, bd_temporal):
        """`resultado_label` se crea tarde (recién al analizar la primera
        imagen) -- resetear antes de eso no debe lanzar AttributeError."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        assert not hasattr(d, "resultado_label")

        d.resetear_imagen_ui()  # no debe lanzar

        assert d.archivo is None
        assert d.imagen_path is None
