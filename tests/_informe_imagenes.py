"""Ayudas COMPARTIDAS de las pruebas del informe PDF de imágenes de CatPhan (E.1, E.3 y E.2 de
PLAN_HANDOFF_IMAGENES_22-09.md).

Las tres tareas prueban lo mismo: generan el PDF REAL de una sesión archivada, sobre una COPIA de la BD del
21-09 (nunca la de referencia: `Conexion()` commitea aunque no cambie nada y altera el md5), con el visor
sustituido por uno que guarda los bytes y con todo `QMessageBox` mockeado (Trampa 2). Este archivo NO empieza
por `test_`, así pytest no lo colecciona; los tests importan de aquí sus fixtures y funciones.
"""
import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
import models.PDF.Imagenes.reportes_control_sistema_imagenes as rep_mod
from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
from _bd_referencia import BD_REBUILD_21_09  # DP-104: fuente única de rutas de BD


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_copia(monkeypatch, tmp_path):
    """Ruta de una COPIA de la BD del 21-09, ya puesta como la base de la aplicación."""
    if not BD_REBUILD_21_09.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_21_09.name}")
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    conection_mod.Conexion._instance = None
    yield str(copia)
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None


@pytest.fixture
def avisos(monkeypatch):
    """Trampa 2: ningún diálogo modal real. Se anotan para exigir que la generación NO haya fallado
    en silencio detrás de un aviso."""
    vistos = []
    for nombre in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(
            QMessageBox, nombre,
            staticmethod(lambda *a, _n=nombre, **k: vistos.append((_n, a[1:3])) or QMessageBox.Ok))
    return vistos


class FalsoVisor:
    """Sustituye al visor: guarda los bytes del PDF en vez de abrir una ventana."""
    ultimo = {}

    def __init__(self, pdf_data=None, fecha="", maquina="", tipo_reporte=""):
        FalsoVisor.ultimo = {"pdf": bytes(pdf_data), "fecha": fecha,
                             "maquina": maquina, "tipo_reporte": tipo_reporte}

    def show(self):
        pass


class Padre(QWidget):
    def __init__(self, ruta):
        super().__init__()
        self._ruta = ruta

    def opeenDatabase(self):
        if not QSqlDatabase.contains("qt_sql_default_connection"):
            db = QSqlDatabase.addDatabase("QSQLITE")
            db.setDatabaseName(self._ruta)
        else:
            db = QSqlDatabase.database("qt_sql_default_connection")
        db.open()
        return db


def paginas(pdf_bytes):
    """Texto de cada página del PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [p.get_text() for p in doc]


def generar(bd_copia, monkeypatch, ref, equipo, fecha, flag=True):
    """Genera el informe de imágenes de la sesión `ref` y devuelve (ok, lo que recibió el visor)."""
    monkeypatch.setattr(rep_mod, "PdfViewer", FalsoVisor)
    FalsoVisor.ultimo = {}
    ok = generar_reporte_sistema_imagenes(
        Padre(bd_copia), fecha, equipo, "x", ref=ref, sistema_imagenes=flag)
    return ok, FalsoVisor.ultimo
