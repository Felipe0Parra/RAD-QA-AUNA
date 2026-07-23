"""F4 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): si ya existe un control
mensual para (equipo, mes, año), `create_control` NO pregunta nada --
decisión explícita del físico (2026-07-23): solo avisa y carga
automáticamente. El aviso (QMessageBox.information, sin botones Sí/No)
menciona la fecha REALMENTE registrada, no el día que se usó para buscar.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import create_control


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
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _self_falso():
    return QWidget()


class TestNoPreguntaSoloAvisaYCarga:

    def test_sin_registro_previo_no_muestra_aviso_de_existente(self, app, bd_temporal, monkeypatch):
        llamados = []
        monkeypatch.setattr(load_mod.QMessageBox, "information",
                             staticmethod(lambda *a, **k: llamados.append(a[2] if len(a) > 2 else k.get("text"))))

        create_control(_self_falso(), "Clinac iX", "01/07/2026", "Físico de Prueba")

        assert len(llamados) == 1
        assert "Datos insertados" in llamados[0]

    def test_con_registro_previo_no_pregunta_nada(self, app, bd_temporal, monkeypatch):
        """No debe existir ningún QMessageBox.question en esta ruta -- la
        decisión del físico es que jamás se pregunte."""
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        create_control(_self_falso(), "Clinac iX", "05/07/2026", "Físico de Prueba")

        def reventar(*a, **k):
            raise AssertionError("create_control no debe preguntar nada al reabrir un mes existente")
        monkeypatch.setattr(load_mod.QMessageBox, "question", staticmethod(reventar))

        create_control(_self_falso(), "Clinac iX", "20/07/2026", "Físico de Prueba")

    def test_aviso_menciona_la_fecha_real_registrada_no_la_buscada(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        create_control(_self_falso(), "Clinac iX", "05/07/2026", "Físico de Prueba")

        capturado = {}
        monkeypatch.setattr(
            load_mod.QMessageBox, "information",
            staticmethod(lambda *a, **k: capturado.setdefault("texto", a[2] if len(a) > 2 else k.get("text"))))

        create_control(_self_falso(), "Clinac iX", "20/07/2026", "Físico de Prueba")

        assert "05/07/2026" in capturado["texto"]
        assert "20/07/2026" not in capturado["texto"]

    def test_aviso_menciona_equipo_y_mes(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        create_control(_self_falso(), "Clinac 600", "10/08/2026", "Físico de Prueba")

        capturado = {}
        monkeypatch.setattr(
            load_mod.QMessageBox, "information",
            staticmethod(lambda *a, **k: capturado.setdefault("texto", a[2] if len(a) > 2 else k.get("text"))))

        create_control(_self_falso(), "Clinac 600", "25/08/2026", "Físico de Prueba")

        assert "Clinac 600" in capturado["texto"]
        assert "08/2026" in capturado["texto"]

    def test_dia_dentro_del_mismo_mes_no_duplica_ni_pregunta(self, app, bd_temporal, monkeypatch):
        avisos = []
        monkeypatch.setattr(load_mod.QMessageBox, "information",
                             staticmethod(lambda *a, **k: avisos.append(1)))

        primero = create_control(_self_falso(), "Halcyon", "01/06/2026", "Físico de Prueba")
        segundo = create_control(_self_falso(), "Halcyon", "28/06/2026", "Físico de Prueba")

        assert primero == segundo
        assert len(avisos) == 2  # el de "insertado" + el de "existente", ninguno pregunta
