"""C1 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase C, R5): tres lecturas de
`TipoCalibracion` resolvían por fecha sin discriminar `tipo`, con `ORDER BY
id DESC` -- con dos calibraciones el mismo día (evidencia real: `id=30`
"Cambio de fuente" e `id=33` "Calibración Redundante", `fecha` idéntica al
segundo), siempre ganaba el `id` más alto. El guardado ya discriminaba por
`(DATE(fecha), tipo)` (`load.py:987`, clave de bloque de EB6); las tres
lecturas se quedaron atrás:

  - `braq_mensual.py::actualizar_ref_bd` -- el tipo lo decide el botón
    marcado (`_tipo_calibracion_seleccionado`, extraído de `guardar_DB`).
  - `braquiterapia.py::CalRedundanteFuente._ejecutar_carga_calibracion` --
    tipo constante "Cambio de fuente" (carga la plantilla de la última
    fuente instalada para pre-llenar una Calibración Redundante).
  - `braquiterapia.py::PosicionamientoInicial.actualizar_ref_bd` -- tipo
    constante "Cambio de fuente" (el posicionamiento inicial ocurre al
    instalar la fuente, nunca en una calibración redundante).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QDateEdit, QPushButton, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
import ui.paginasControles.PruebasDiarias.braquiterapia as braquiterapia_mod

FECHA_COMPARTIDA = "2026-06-26 11:42:13"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = conexion.con
    # Reproduce el escenario real: dos calibraciones, misma fecha al segundo.
    con.execute(
        "INSERT INTO TipoCalibracion (id, fecha, tipo, serie, certificado, "
        "fecha_cer, intensidad, conversion) VALUES "
        "(30, ?, 'Cambio de fuente', 'SERIE-30', 111, '2026-01-01 00:00:00', 1.0, 1.0)",
        (FECHA_COMPARTIDA,))
    con.execute(
        "INSERT INTO TipoCalibracion (id, fecha, tipo, serie, certificado, "
        "fecha_cer, intensidad, conversion) VALUES "
        "(33, ?, 'Calibración Redundante', 'SERIE-33', 222, '2026-01-01 00:00:00', 2.0, 2.0)",
        (FECHA_COMPARTIDA,))
    con.commit()
    yield con
    conexion.con.close()
    Conexion._instance = None


def _fecha_qdate():
    return QDate.fromString(FECHA_COMPARTIDA.split(" ")[0], "yyyy-MM-dd")


def _boton_checkable(marcado):
    b = QPushButton()
    b.setCheckable(True)
    b.setChecked(marcado)
    return b


class TestBraqMensualActualizarRefBd:

    def _obj(self, tipo):
        obj = braq_mensual_mod.PruebaMensualBraq.__new__(braq_mensual_mod.PruebaMensualBraq)
        QWidget.__init__(obj)
        obj.date_box = QDateEdit()
        obj.ref_bd = None
        obj.pri_cal = _boton_checkable(tipo == "Control Mensual")
        obj.cambio_cal = _boton_checkable(tipo == "Cambio de fuente")
        obj.es_calibracion_redundante = (tipo == "Calibración Redundante")
        return obj

    def test_cambio_de_fuente_selecciona_id_30(self, app, bd_temporal):
        obj = self._obj("Cambio de fuente")

        obj.date_box.setDate(_fecha_qdate())
        obj.actualizar_ref_bd()

        assert obj.ref_bd == 30

    def test_calibracion_redundante_selecciona_id_33(self, app, bd_temporal):
        obj = self._obj("Calibración Redundante")

        obj.date_box.setDate(_fecha_qdate())
        obj.actualizar_ref_bd()

        assert obj.ref_bd == 33


class TestCalRedundanteFuenteCargaLaPlantillaCorrecta:

    def test_carga_datos_de_cambio_de_fuente_no_de_la_redundante(self, app, bd_temporal):
        obj = braquiterapia_mod.CalRedundanteFuente.__new__(
            braquiterapia_mod.CalRedundanteFuente)
        QWidget.__init__(obj)
        obj.serie = braq_mensual_mod.QLineEdit()
        obj.certificado = braq_mensual_mod.QLineEdit()
        obj.fecha_cer = QDateEdit()
        obj.intensidad = braq_mensual_mod.QLineEdit()
        obj.conversion = braq_mensual_mod.QLineEdit()
        obj.modelo = None
        obj.serie_cp = None

        try:
            obj._ejecutar_carga_calibracion(None)
        except AttributeError:
            pass  # SistemaMedicion/CondicionesMedicion vacíos -- no interesa aquí

        assert obj.serie.text() == "SERIE-30", (
            "debe traer los datos de id=30 (Cambio de fuente), no id=33 "
            "(Calibración Redundante), aunque comparten fecha")


class TestPosicionamientoInicialActualizarRefBd:

    def test_selecciona_cambio_de_fuente_no_la_redundante(self, app, bd_temporal, monkeypatch):
        obj = braquiterapia_mod.PosicionamientoInicial.__new__(
            braquiterapia_mod.PosicionamientoInicial)
        QWidget.__init__(obj)
        obj.date_box = QDateEdit()
        obj.ref_bd = None

        obj.date_box.setDate(_fecha_qdate())
        obj.actualizar_ref_bd()

        assert obj.ref_bd == 30
