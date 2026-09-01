"""A3 (PLAN_REPARACION_ANUAL_27-08.md §Fase 4, AN-8): la imagen del perfil
MLC (Halcyon anual) traga el error. `halcyon_anual.py::subir_imagen_perfil_mlc_db`
tenía `except Exception as e: print(...)` -- sin aviso al físico, sin
`rollback`, y sin cerrar la conexión abierta al principio de la función.
Misma familia que `DP-46`/`DP-51` (conexión huérfana + error silencioso).

Reparación: avisar con `QMessageBox.critical`, hacer `rollback` de
cualquier escritura a medias, y cerrar la conexión siempre (`finally`),
tanto si sale bien como si falla.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch, MagicMock

from PyQt5.QtWidgets import QApplication, QWidget

from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaAnualHalcyon


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _halcyon_pelado():
    obj = PruebaAnualHalcyon.__new__(PruebaAnualHalcyon)
    QWidget.__init__(obj)
    obj.ref = 10
    return obj


class TestA3ErrorAlEjecutarElInsertAvisaYCierra:
    def test_avisa_con_messagebox_critical(self, app):
        obj = _halcyon_pelado()
        conexion_falsa = MagicMock()
        conexion_falsa.conectar.return_value.cursor.return_value.execute.side_effect = Exception("boom")

        with patch("data.ManejoDatos.conection.Conexion", return_value=conexion_falsa), \
             patch("ui.paginasControles.PruebasAnuales.halcyon_anual.QMessageBox") as mb:
            obj.subir_imagen_perfil_mlc_db(b"img", b"perfil", "1,2,3")
            assert mb.critical.called, "debe avisar con QMessageBox.critical si falla"
            assert not mb.information.called, "no debe avisar éxito si falló"

    def test_hace_rollback_si_falla(self, app):
        obj = _halcyon_pelado()
        conexion_falsa = MagicMock()
        conexion_falsa.conectar.return_value.cursor.return_value.execute.side_effect = Exception("boom")

        with patch("data.ManejoDatos.conection.Conexion", return_value=conexion_falsa), \
             patch("ui.paginasControles.PruebasAnuales.halcyon_anual.QMessageBox"):
            obj.subir_imagen_perfil_mlc_db(b"img", b"perfil", "1,2,3")
            assert conexion_falsa.conectar.return_value.rollback.called

    def test_cierra_la_conexion_incluso_si_falla(self, app):
        obj = _halcyon_pelado()
        conexion_falsa = MagicMock()
        conexion_falsa.conectar.return_value.cursor.return_value.execute.side_effect = Exception("boom")

        with patch("data.ManejoDatos.conection.Conexion", return_value=conexion_falsa), \
             patch("ui.paginasControles.PruebasAnuales.halcyon_anual.QMessageBox"):
            obj.subir_imagen_perfil_mlc_db(b"img", b"perfil", "1,2,3")
            assert conexion_falsa.conectar.return_value.close.called

    def test_cierra_la_conexion_cuando_sale_bien(self, app):
        obj = _halcyon_pelado()
        conexion_falsa = MagicMock()

        with patch("data.ManejoDatos.conection.Conexion", return_value=conexion_falsa), \
             patch("ui.paginasControles.PruebasAnuales.halcyon_anual.QMessageBox") as mb, \
             patch("ui.paginasControles.PruebasAnuales.halcyon_anual._registrar_auditoria"), \
             patch("ui.paginasControles.PruebasAnuales.halcyon_anual._usuario_actual"):
            obj.subir_imagen_perfil_mlc_db(b"img", b"perfil", "1,2,3")
            assert conexion_falsa.conectar.return_value.close.called
            assert mb.information.called
