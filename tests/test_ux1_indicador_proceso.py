"""UX1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-UX1, [[DA-51]]/[[DA-70]]): mientras
`analizar_cuadrado2` corre (síncrono, bloquea el hilo de la GUI), el físico
ve un cursor de espera y un indicador estático -- antes no había ninguna
señal de que la app seguía viva.

**Alcance recortado por la auditoría de viabilidad del 25-08 (§7.0 del
plan, V5)**: el plan original nombraba como parte de UX1 "el botón conserva
el handler del análisis anterior" -- ya cerrado por `IM3` (Fase 6, mismo
día), que deshabilita el botón ANTES de llamar a `analizar_cuadrado2` y solo
lo rehabilita al volver. Este archivo prueba solo lo que UX1 añadió de
verdad: cursor + indicador, y que conviven bien con lo que IM3 ya hace.

Cuatro hallazgos de esa auditoría, cada uno con su test:

  - **V6**: el indicador vive en `self.botones_layout` (el de
    `imagenUpLoader`), NUNCA en `self.col2` -- `mostrar_resultados_
    AnalisisImagen` hace `deleteLater()` sobre todo widget de `col2` que no
    sea canvas/toolbar/graficar, en cada análisis. `test_el_indicador_
    sobrevive_a_dos_analisis_reales` deja correr esa función REAL (no
    mockeada) para probarlo de verdad, no solo confiar en dónde se puso.
  - **V7**: `repaint()` se llama sobre el indicador antes del cómputo --
    sin este archivo no hay forma de probar "se ve" sin un event loop real,
    así que se prueba lo verificable: que el método existe y se invoca (ver
    `test_repaint_se_invoca_antes_del_computo`).
  - **V8**: el cursor se restaura en un `finally` -- probado forzando que
    `analizar_cuadrado2` LANCE, e inspeccionando que `QApplication.
    overrideCursor()` queda en `None` de todos modos.
  - **V9**: no había precedente de `setOverrideCursor` en el proyecto --
    sin test, un futuro cambio podría dejarlo puesto sin que nada lo note.

Se usa `isHidden()` para el indicador, no `isVisible()`: `isVisible()`
depende de que TODA la cadena de padres esté realizada en pantalla (no es
el caso aquí, un widget suelto sin ventana mostrada), mientras que
`isHidden()` refleja directamente si se llamó `show()`/`hide()` sobre ESE
widget -- el flag que este código controla.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
    QWidget,
)

import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_cursor_de_espera_colgado(app):
    """El override cursor de Qt es una PILA compartida por todo el proceso.
    Si un test anterior (de este archivo o de cualquier otro) dejara uno sin
    restaurar, contaminaría los demás -- se limpia antes y después de cada
    test, sin asumir que el código bajo prueba es quien tiene la culpa."""
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
    yield
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()


def _sin_avisos(monkeypatch):
    """Trampa 2 de CLAUDE.md: `analizar_imagen` abre `QMessageBox.warning`
    en DOS caminos que estos tests recorren a propósito (la guarda de
    `imagen_path` y el `except` que atrapa un análisis fallido) -- sin
    mockearlo, el test se cuelga esperando un clic que nunca llega."""
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)


def _pelado():
    """Objeto mínimo pero REAL en sus widgets -- suficiente para que
    `analizar_imagen` Y `mostrar_resultados_AnalisisImagen` corran de
    principio a fin sin necesitar matplotlib real: `canvas`/`graficar`/
    `toolbar` son QWidget lisos (soportan `.show()`/`.update()`/
    `.setVisible()`, que es todo lo que ese código les pide), y `toolbar`
    ya existe de antemano para que ninguna de las dos ramas intente
    construir un `NavigationToolbar` real."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.imagen_path = "no-importa.png"
    obj.boton_siguiente = QPushButton()
    obj.boton_anterior = QPushButton()
    obj.botones_layout = QHBoxLayout()
    obj.col2 = QVBoxLayout()
    obj.canvas = QWidget()
    obj.graficar = QWidget()
    obj.toolbar = QWidget()
    return obj


def _mockear_analisis(monkeypatch, fake_analizar):
    monkeypatch.setattr(mensual_mod, "analizar_cuadrado2", fake_analizar)
    monkeypatch.setattr(mensual_mod, "generar_reporte_completo", lambda res: "reporte")


class TestDuranteElAnalisisElEstadoEsElCorrecto:

    def test_cursor_de_espera_indicador_visible_boton_deshabilitado(
            self, app, monkeypatch):
        obj = _pelado()
        _sin_avisos(monkeypatch)
        estado = {}

        def fake_analizar(imagen_path, filtro, mostrar, canvas):
            cursor = QApplication.overrideCursor()
            estado["cursor_puesto"] = cursor is not None
            estado["cursor_shape"] = cursor.shape() if cursor else None
            estado["indicador_oculto"] = obj.indicador_analizando.isHidden()
            estado["boton_deshabilitado"] = not obj.guardar_analisis.isEnabled()
            return {"graficas": []}

        _mockear_analisis(monkeypatch, fake_analizar)
        obj.analizar_imagen()

        assert estado["cursor_puesto"], "debía haber un cursor de espera puesto"
        assert estado["cursor_shape"] == Qt.WaitCursor
        assert estado["indicador_oculto"] is False, "el indicador debía estar visible"
        assert estado["boton_deshabilitado"], (
            "el botón debía seguir deshabilitado (IM3) durante el análisis")

    def test_repaint_se_invoca_antes_del_computo(self, app, monkeypatch):
        """V7: sin forzar el repintado, el indicador no se vería hasta que
        el bucle de eventos vuelva a girar -- que es justo lo que el
        cómputo síncrono bloquea. No se puede comprobar el PÍXEL sin un
        event loop real; sí se puede comprobar que `repaint()` se llamó
        antes de que el cómputo arrancara."""
        obj = _pelado()
        _sin_avisos(monkeypatch)
        llamadas = []

        def fake_analizar(imagen_path, filtro, mostrar, canvas):
            llamadas.append("analizar_cuadrado2")
            return {"graficas": []}

        _mockear_analisis(monkeypatch, fake_analizar)
        repaint_original = QLabel.repaint

        def _repaint_espiado(self, *a, **k):
            llamadas.append("repaint")
            return repaint_original(self, *a, **k)

        monkeypatch.setattr(QLabel, "repaint", _repaint_espiado)

        obj.analizar_imagen()

        assert "repaint" in llamadas
        assert llamadas.index("repaint") < llamadas.index("analizar_cuadrado2"), (
            "repaint() debe llamarse ANTES del cómputo, no después")


class TestAlTerminarBienSeRestauraTodo:

    def test_cursor_restaurado_indicador_oculto_boton_habilitado(
            self, app, monkeypatch):
        obj = _pelado()
        _sin_avisos(monkeypatch)
        _mockear_analisis(monkeypatch, lambda **_k: {"graficas": []})

        obj.analizar_imagen()

        assert QApplication.overrideCursor() is None
        assert obj.indicador_analizando.isHidden()
        assert obj.guardar_analisis.isEnabled()


class TestAlFallarTambienSeRestaura:
    """V8: `analizar_cuadrado2` lanza de verdad hoy (IMG-1, cualquier DPI
    fuera de 200/300/600) -- sin un `finally`, el cursor de espera quedaría
    PERMANENTE, un síntoma peor que el que UX1 viene a resolver."""

    def test_analisis_que_lanza_restaura_cursor_y_oculta_indicador(
            self, app, monkeypatch):
        obj = _pelado()
        _sin_avisos(monkeypatch)

        def fake_que_falla(**_k):
            raise RuntimeError("simulando IMG-1 (DPI fuera de 200/300/600)")

        _mockear_analisis(monkeypatch, fake_que_falla)
        obj.analizar_imagen()  # el except interno la atrapa; no debe propagar

        assert QApplication.overrideCursor() is None, (
            "un análisis fallido no debe dejar el cursor de espera puesto")
        assert obj.indicador_analizando.isHidden()

    def test_analisis_que_lanza_deja_el_boton_deshabilitado(self, app, monkeypatch):
        """IM3 + UX1 combinados: `self.res` queda en `None` y el botón
        nunca llega a la línea que lo rehabilita."""
        obj = _pelado()
        _sin_avisos(monkeypatch)
        _mockear_analisis(monkeypatch, lambda **_k: (_ for _ in ()).throw(
            RuntimeError("IMG-1")))

        obj.analizar_imagen()

        assert not obj.guardar_analisis.isEnabled()
        assert obj.res is None


class TestSinImagenNoTocaElCursor:

    def test_sin_imagen_path_no_deja_cursor_puesto(self, app, monkeypatch):
        obj = _pelado()
        obj.imagen_path = None
        _sin_avisos(monkeypatch)

        obj.analizar_imagen()

        assert QApplication.overrideCursor() is None
        assert not hasattr(obj, "indicador_analizando"), (
            "sin imagen seleccionada no debe crearse ni tocarse nada del "
            "análisis -- se sale por la guarda antes de todo eso")


class TestElIndicadorSobreviveALaLimpiezaDeCol2:
    """V6: la prueba de verdad -- se deja correr `mostrar_resultados_
    AnalisisImagen` SIN mockear, para comprobar que su limpieza de `col2`
    (que hace `deleteLater()` sobre cualquier widget ajeno) nunca alcanza
    al indicador, porque vive en un layout distinto."""

    def test_el_indicador_sobrevive_a_dos_analisis_reales(self, app, monkeypatch):
        obj = _pelado()
        _sin_avisos(monkeypatch)
        _mockear_analisis(monkeypatch, lambda **_k: {"graficas": []})

        obj.analizar_imagen()
        primero = obj.indicador_analizando
        assert primero.isHidden()

        obj.analizar_imagen()  # segundo análisis -- dispara la limpieza de col2

        assert obj.indicador_analizando is primero, (
            "el indicador no debía recrearse ni destruirse entre análisis")
        # Si estuviera en col2, esta llamada ya habría lanzado
        # RuntimeError: wrapped C/C++ object of type QLabel has been deleted.
        assert primero.isHidden()
        assert obj.col2.indexOf(primero) == -1, (
            "el indicador NUNCA debe estar en col2 -- es lo que lo expone "
            "a la limpieza de mostrar_resultados_AnalisisImagen")
