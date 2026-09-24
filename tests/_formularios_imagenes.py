"""Ayudas COMPARTIDAS de las pruebas de los formularios de imágenes (G.1, G.2 y G.3 de
PLAN_HANDOFF_IMAGENES_22-09.md): la BD temporal, los diálogos mockeados (Trampa 2) y los constructores de las
cinco pantallas de imágenes -- tomógrafo, iX (mensual y anual) y Halcyon (mensual y anual).

Este archivo NO empieza por `test_`, así pytest no lo colecciona; los tests importan de aquí sus fixtures.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion


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
    """Trampa 2: ningún QMessageBox real. `information` registra lo que se le pide."""
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    llamadas = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda parent, titulo, texto, *a, **k: llamadas.append((titulo, texto)))
    return llamadas


def _tomografo():
    from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
    return PruebaMensualTAC(user_id=None)


def _ix_mensual():
    from ui.paginasControles.PruebasMensuales.ix_imagenes_mensual import PruebaImagenesIX
    return PruebaImagenesIX(user_id=None)


def _hc_mensual():
    from ui.paginasControles.PruebasMensuales.HC_imagenes_mensual import PruebaImagenesHC
    return PruebaImagenesHC(user_id=None)


def _ix_anual():
    from ui.paginasControles.PruebasAnuales.ix_anual import PruebaImagenesIX
    return PruebaImagenesIX(user_id=None)


def _hc_anual():
    from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaImagenesHalcyon
    return PruebaImagenesHalcyon(user_id=None)


# clave -> (constructor, equipo, hoja del encabezado en data/widgets.xlsx)
FORMULARIOS = {
    "tomografo": (_tomografo, "Tomógrafo", "encabezado_mensu_TAC"),
    "ix_mensual": (_ix_mensual, "Clinac ix", "encabezado_images_ix"),
    "ix_anual": (_ix_anual, "Clinac ix", "encabezado_images_ix"),
    "hc_mensual": (_hc_mensual, "Halcyon", "encabezado_images_HC"),
    "hc_anual": (_hc_anual, "Halcyon", "encabezado_images_HC"),
}


def iniciar(obj):
    """Lo que hace el físico al pulsar "Iniciar": elige el físico, se crea el control y se construye el
    formulario de las siete pruebas (los gráficos primero: crean el `canvas`). Devuelve `obj`."""
    obj.fisico1.addItem("Fisico Real", 1)
    obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
    obj.user_id_f1 = "Fisico Real"
    obj.user_id_f2 = None
    obj._iniciar_moviendo_tabla(obj.lista_maquina)
    assert obj.ref is not None, "no se creó el control"
    obj.graphicsWindow()
    obj.controlTestWindow(sheet_name="preguntas_mensu_TAC")
    return obj
