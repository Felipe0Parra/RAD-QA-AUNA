"""A6.4 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): anual (600/iX/Halcyon) deja
rastro en `audit_log` -- archivos que no tenían NI UNA sola llamada de
auditoría.

Cuatro puntos: `PruebaAnual600.create_control` (mismo patrón que el
create_control mensual -- solo audita el alta, no la reapertura, por
consistencia con el hermano de `data/ManejoDatos/load.py`),
`PruebaAnualHalcyon.subir_imagen_perfil_mlc_db` (escritura aparte, no pasa
por loadtablacomplex), y los dos `guardar_todas_fse` (uno en
seiscientos_anual.py -- compartido con Halcyon anual por herencia -- y su
copia propia en ix_anual.py). Estos dos últimos cierran, junto con
`_subir_tabla_optimizada` de A6.3, los 3 puntos de cierre reales de
`loadtablacomplex` que quedaban pendientes.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasAnuales.seiscientos_anual as anual_mod
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
import ui.paginasControles.PruebasAnuales.ix_anual as ix_anual_mod
from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
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
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _insertar_control(ruta_bd, equipo="Halcyon", fecha="01/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, "Anual", fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _boton_de(layout):
    """Los botones de _agregar_botones_tabla van dentro de un QHBoxLayout
    anidado (layout.addLayout(button_layout)), no directo -- bajar un
    nivel más que un addWidget simple."""
    return layout.itemAt(0).layout().itemAt(0).widget()


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    for modulo in (anual_mod, halcyon_anual_mod):
        monkeypatch.setattr(modulo.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(modulo.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


class _SelfAnualFalso:
    def __init__(self):
        self.user_id = _UsuarioFalso("Físico de Prueba")


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


def _anual_pelado(clase):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso("Físico de Prueba")
    obj.anual = True
    return obj


class TestCreateControlAnualAudita:
    def test_alta_de_control_nuevo_audita_una_vez(self, app, bd_temporal):
        ref = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac 600", "01/2026", "Físico de Prueba")

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "controles", str(ref),
             "Clinac 600 -- Anual 01/2026")]

    def test_reabrir_el_mismo_anio_no_audita_de_nuevo(self, app, bd_temporal):
        """Espejo del mensual (data/ManejoDatos/load.py::create_control):
        la reapertura tampoco audita ahí, así que aquí tampoco -- 1 fila
        para el alta, ninguna para reabrir."""
        ref1 = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac iX", "03/2026", "Físico de Prueba")
        ref2 = PruebaAnual600.create_control(
            _SelfAnualFalso(), "Clinac iX", "09/2026", "Físico de Prueba")

        assert ref1 == ref2
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1


class TestSubirImagenPerfilMlcAudita:
    def test_audita_con_tabla_y_ref_correctos(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        obj = _anual_pelado(PruebaAnualHalcyon)
        obj.ref = ref

        obj.subir_imagen_perfil_mlc_db(b"img", b"perfil", "1,2,3")

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "HC_imagen_perfil_mlc_anual",
             str(ref), "")]


class TestGuardarTodasFseSeiscientosAnualAudita:
    def _instancia(self):
        obj = _anual_pelado(PruebaAnual600)
        obj.ref = 7
        return obj

    def test_tabla_individual_audita_una_vez(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(anual_mod, "loadtablacomplex", lambda *a, **k: None)
        obj = self._instancia()
        layout = QHBoxLayout()
        tabla = object()

        obj._agregar_botones_tabla(layout, tabla, "tabla_fc", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "tabla_fc", str(obj.ref), "")]

    def test_bucle_de_energias_fse_audita_una_sola_vez(self, app, bd_temporal, monkeypatch):
        """El caso citado en el plan: un solo click puede subir VARIAS
        tablas FSE (una por energía) -- 1 fila, no una por tabla."""
        llamadas = []
        monkeypatch.setattr(
            anual_mod, "loadtablacomplex",
            lambda *a, **k: llamadas.append(a))
        obj = self._instancia()
        tabla_1 = object()
        tabla_2 = object()
        obj.tablas_fse = [
            {"tabla": tabla_1, "pdd": "6mv"},
            {"tabla": tabla_2, "pdd": "15mv"},
        ]
        layout = QHBoxLayout()

        obj._agregar_botones_tabla(layout, tabla_1, "tablas_fse", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        assert len(llamadas) == 2  # las 2 tablas FSE sí se subieron
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1  # pero 1 sola fila de auditoría


class TestGuardarTodasFseIxAnualAudita:
    def test_tabla_individual_audita_una_vez(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(ix_anual_mod, "loadtablacomplex", lambda *a, **k: None)
        obj = _anual_pelado(PruebaAnualIX)
        obj.ref = 9
        layout = QHBoxLayout()
        tabla = object()

        obj._agregar_botones_tabla(layout, tabla, "tabla_ccm", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        filas = _audit_log(bd_temporal)
        assert filas == [
            ("Físico de Prueba", "guardar", "tabla_ccm", str(obj.ref), "")]

    def test_bucle_de_energias_fse_audita_una_sola_vez(self, app, bd_temporal, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            ix_anual_mod, "loadtablacomplex",
            lambda *a, **k: llamadas.append(a))
        obj = _anual_pelado(PruebaAnualIX)
        obj.ref = 11
        tabla_1 = object()
        tabla_2 = object()
        obj.tablas_fse = [[
            {"tabla": tabla_1, "pdd": "6mev", "id_energia": 1},
            {"tabla": tabla_2, "pdd": "9mev", "id_energia": 2},
        ]]
        layout = QHBoxLayout()

        obj._agregar_botones_tabla(layout, tabla_1, "tablas_fse", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        assert len(llamadas) == 2
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
