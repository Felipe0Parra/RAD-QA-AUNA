"""Z6 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): un solo botón "Subir"
para la imagen/perfil del MLC anual de Halcyon.

Causa (anotación 5, confirmada en `audit_log`: dos filas de
`HC_imagen_perfil_mlc_anual`, ids 81 y 82, a 4 segundos de diferencia).
`analizar_imagen` (halcyon_anual.py) creaba un `QPushButton("Subir")` NUEVO
cada vez que se llamaba -- si el físico re-analiza la imagen (elige otra,
vuelve a pulsar "Aceptar"), el botón anterior nunca se quitaba de
`canvas_layout`: quedaban dos botones "Subir" apilados, cada uno con su
propia conexión al mismo `subir_imagen_perfil_mlc_db`. El toolbar, en la
misma función, sí tenía la guarda (`self.toolbar.setParent(None)` antes de
crear uno nuevo) -- el botón se quedó sin ese mismo cuidado.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from resources.utils.matplotlib_lazy import get_matplotlib_components
import ui.paginasControles.PruebasAnuales.halcyon_anual as halcyon_anual_mod
from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaAnualHalcyon


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO controles (id, equipo, control, fecha) VALUES (1, 'Halcyon', 'Anual', '01/2026')")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(halcyon_anual_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(halcyon_anual_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(halcyon_anual_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


@pytest.fixture
def instancia_con_canvas(app, tmp_path):
    """Instancia pelada de PruebaAnualHalcyon con un canvas real embebido
    en un contenedor con layout -- exactamente lo que analizar_imagen
    necesita (self.canvas.parent().layout())."""
    ruta_img = str(tmp_path / "imagen_mlc.png")
    cv2.imwrite(ruta_img, (np.random.rand(60, 60) * 255).astype("uint8"))

    mpl = get_matplotlib_components()
    contenedor = QWidget()
    QVBoxLayout(contenedor)  # se auto-asigna como layout del contenedor

    obj = PruebaAnualHalcyon.__new__(PruebaAnualHalcyon)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso("Físico de Prueba")
    obj.ref = 1
    obj.imagen_path = ruta_img
    canvas = mpl["FigureCanvas"](mpl["Figure"]())
    contenedor.layout().addWidget(canvas)
    obj.canvas = canvas
    obj._contenedor_test = contenedor  # mantiene vivo el wrapper de Python
    return obj


def _contar_botones_subir(layout):
    total = 0
    for i in range(layout.count()):
        w = layout.itemAt(i).widget()
        if isinstance(w, QPushButton) and w.text() == "Subir":
            total += 1
    return total


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT accion, tabla, ref FROM audit_log").fetchall()
    con.close()
    return filas


class TestUnSoloBotonTrasVariosAnalisis:
    def test_un_solo_boton_subir_tras_reanalizar(self, instancia_con_canvas, bd_temporal):
        d = instancia_con_canvas

        d.analizar_imagen()
        d.analizar_imagen()
        d.analizar_imagen()

        layout = d.canvas.parent().layout()
        assert _contar_botones_subir(layout) == 1

    def test_un_solo_boton_tras_un_solo_analisis(self, instancia_con_canvas, bd_temporal):
        d = instancia_con_canvas

        d.analizar_imagen()

        layout = d.canvas.parent().layout()
        assert _contar_botones_subir(layout) == 1


class TestSigueGuardandoImagenYPerfil:
    """Anti-regresión de A6.4: el botón único sigue guardando la imagen y
    el perfil, y con la conexión ACTUALIZADA al último análisis (no la del
    primero) -- clic tras reanalizar debe auditar una sola fila."""

    def test_click_tras_reanalizar_audita_una_sola_fila(self, instancia_con_canvas, bd_temporal):
        d = instancia_con_canvas

        d.analizar_imagen()
        d.analizar_imagen()

        layout = d.canvas.parent().layout()
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, QPushButton) and w.text() == "Subir":
                w.click()

        filas = _audit_log(bd_temporal)
        assert filas == [("guardar", "HC_imagen_perfil_mlc_anual", "1")]
