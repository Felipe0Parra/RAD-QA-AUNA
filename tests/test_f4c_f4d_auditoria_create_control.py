"""F4c/F4d (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): `create_control`
audita la creación de un control mensual -- antes no dejaba NINGÚN rastro
(verificado: `audit_log` de producción no tiene una sola fila con
tabla='controles'). Esta ancla es lo que F4b (ventana de edición de dos
meses) necesita para saber desde cuándo se cuenta el plazo. `detalle` es
legible (equipo + tipo + mes/año), no solo el id numérico -- decisión del
físico (2026-07-23): "garantizar que se muestre qué registro se tocó, no
solo qué tabla".
"""
import os
import sqlite3

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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _self_falso():
    w = QWidget()
    w.user_id = _UsuarioFalso()
    return w


def _filas_audit(ruta_db, tabla="controles"):
    con = sqlite3.connect(ruta_db)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log WHERE tabla = ?",
        (tabla,)).fetchall()
    con.close()
    return filas


class TestAuditaLaCreacion:

    def test_crear_nuevo_control_audita_una_fila(self, app, bd_temporal):
        nuevo_id = create_control(_self_falso(), "Clinac iX", "05/07/2026", "Físico de Prueba")

        filas = _filas_audit(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "guardar"
        assert tabla == "controles"
        assert ref == str(nuevo_id)

    def test_detalle_es_legible_equipo_y_mes(self, app, bd_temporal):
        create_control(_self_falso(), "Clinac 600", "15/08/2026", "Físico de Prueba")

        filas = _filas_audit(bd_temporal)
        detalle = filas[0][4]
        assert "Clinac 600" in detalle
        assert "08/2026" in detalle
        assert "Mensual" in detalle

    def test_reabrir_control_existente_no_agrega_fila_nueva(self, app, bd_temporal):
        create_control(_self_falso(), "Halcyon", "01/06/2026", "Físico de Prueba")
        assert len(_filas_audit(bd_temporal)) == 1

        create_control(_self_falso(), "Halcyon", "20/06/2026", "Físico de Prueba")

        assert len(_filas_audit(bd_temporal)) == 1

    def test_dos_controles_distintos_generan_dos_filas_con_su_propio_ref(self, app, bd_temporal):
        id_julio = create_control(_self_falso(), "Clinac iX", "01/07/2026", "Físico de Prueba")
        id_agosto = create_control(_self_falso(), "Clinac iX", "01/08/2026", "Físico de Prueba")

        filas = _filas_audit(bd_temporal)
        assert len(filas) == 2
        refs = {f[3] for f in filas}
        assert refs == {str(id_julio), str(id_agosto)}

    def test_sin_usuario_no_lanza(self, app, bd_temporal):
        w = QWidget()  # sin user_id
        create_control(w, "Clinac iX", "01/09/2026", "Físico de Prueba")

        filas = _filas_audit(bd_temporal)
        assert len(filas) == 1
        assert filas[0][0] is None
