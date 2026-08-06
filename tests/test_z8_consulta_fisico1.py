"""Z8 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): la consulta del físico 1
deja de fallar en silencio -- cierra F9 (07-07).

`Error: 'QComboBox' object has no attribute 'setText'`, precedido de
`Consulta de físicos exitosa: Nombre F1: []`. Dos defectos:

- `actualizar_fisicos` (conectada a `date_box.dateChanged`) llamaba
  `self.fisico1.setText(...)` -- `fisico1`/`fisico2` son `QComboBox`, sin
  ese método -- AttributeError garantizado en cuanto había un control
  existente ese mes, atrapado en silencio por el `except` genérico.
- `consultar_fisicos_bd` imprimía "exitosa" junto a una lista vacía --
  contradictorio: una lista vacía es un resultado LEGÍTIMO cuando quien
  inició sesión no tiene `role='Físico Médico'` (admin/jefe verificando el
  formulario), no un fallo de la consulta.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    # controles.user_id/user_id_f2 tienen FK a users(fullname) (W2,
    # foreign_keys=ON) -- deben existir antes de insertar un control.
    for nombre in ("Físico Uno", "Físico Dos"):
        conexion.con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)",
            (nombre.lower().replace(" ", "_"), "x", nombre, 1, 1, "Físico Médico"))
    conexion.con.commit()
    yield conexion
    conexion.con.close()
    Conexion._instance = None


def _mensual_pelado():
    """PruebaMensual600 sin su __init__ pesado -- solo lo que
    actualizar_fisicos necesita. equipo_f='Tomógrafo' fuerza el camino
    Conexion().conectar() directo, sin depender de self.db_manager."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.equipo_f = "Tomógrafo"
    obj.date_box = QDateEdit()
    obj.date_box.setDisplayFormat("dd/MM/yyyy")
    obj.fisico1 = QComboBox()
    obj.fisico2 = QComboBox()
    obj.fisico1.addItem("Seleccionar...", None)
    obj.fisico1.addItem("Físico Uno", 1)
    obj.fisico1.addItem("Físico Dos", 2)
    obj.fisico2.addItem("Seleccionar...", None)
    obj.fisico2.addItem("Físico Uno", 1)
    obj.fisico2.addItem("Físico Dos", 2)
    return obj


class TestFisico1SeSelecciona:
    def test_control_existente_selecciona_fisico1_y_fisico2(self, app, bd_temporal):
        con = bd_temporal.con
        con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
            "VALUES (?,?,?,?,?)",
            ("Tomógrafo", "Mensual", "08/2026", "Físico Uno", "Físico Dos"))
        con.commit()

        d = _mensual_pelado()
        d.date_box.setDate(QDate(2026, 8, 15))

        d.actualizar_fisicos()

        assert d.fisico1.currentText() == "Físico Uno"
        assert d.fisico2.currentText() == "Físico Dos"


class TestSinFisico1NoRevienta:
    def test_sin_control_existente_no_cambia_nada_ni_revienta(self, app, bd_temporal):
        d = _mensual_pelado()
        d.date_box.setDate(QDate(2026, 8, 15))
        indice_original = d.fisico1.currentIndex()

        d.actualizar_fisicos()  # no debe lanzar

        assert d.fisico1.currentIndex() == indice_original


class TestNoSeImprimeElError:
    def test_no_imprime_el_error_de_setext(self, app, bd_temporal, capsys):
        con = bd_temporal.con
        con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
            "VALUES (?,?,?,?,?)",
            ("Tomógrafo", "Mensual", "08/2026", "Físico Uno", None))
        con.commit()

        d = _mensual_pelado()
        d.date_box.setDate(QDate(2026, 8, 20))

        capsys.readouterr()
        d.actualizar_fisicos()
        salida = capsys.readouterr().out

        assert "setText" not in salida
        assert "QComboBox" not in salida
        assert d.fisico1.currentText() == "Físico Uno"
