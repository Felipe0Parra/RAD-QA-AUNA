"""Bugfix (hallado 2026-07-30 al ejecutar F6-F10/F7, PLAN_F_CIERRE_ESTANDAR_
29-07.md -- no pertenece a ninguna de esas tareas, corregido aparte a
pedido del físico): `Config.guardarCambios` conservaba la imagen vieja del
certificado con `datos_originales[12]` cuando se editan otros campos sin
subir una imagen nueva. Ese índice es `vigente` (columna 12 del SELECT:
equip_type, model, serie, calibr_fact, calibr_fact2, fecha_calibr,
fabricante, t_cal, p_cal, h_cal, v1, activo, vigente, imagen_certificado),
no `imagen_certificado` (índice 13) -- así que el BLOB de la imagen se
llenaba con lo que fuera que `vigente` valiera (0/1/None) en vez de la
imagen real.
"""
import sqlite3

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QWidget,
)

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.equipos as equipos_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.equipos import Config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "accastellanos"


IMAGEN_REAL = b"\xff\xd8\xff\xe0no-es-un-jpg-real-pero-no-es-0-ni-1-tampoco"


def _preparar_equipo_con_imagen(ruta, vigente=1):
    con = sqlite3.connect(ruta)
    cur = con.execute("""
        INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2,
            fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1, activo, vigente,
            imagen_certificado)
        VALUES ('Cámara de ionización', 'N30013', '2123', 0.0545, NULL,
            '05/02/2024', NULL, 22.0, 101.325, 50.0, NULL, 1, ?, ?)
    """, (vigente, IMAGEN_REAL))
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


def _instancia_editando_fabricante(id_equipo):
    """Cambia SOLO `fabricante` (un campo real, no `activo`) y no sube
    ninguna imagen nueva -- exactamente la rama que tenía el bug."""
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioActualFalso()
    obj.cargartabla = lambda: None

    obj.tipo = QComboBox()
    obj.tipo.addItem("Cámara de ionización")
    obj.modelo = QLineEdit("N30013")
    obj.serie = QLineEdit("2123")
    obj.calib_factor = QLineEdit("0.0545")
    obj.calib_date = QLineEdit("05/02/2024")
    obj.fabricante = QLineEdit("PTW")  # el único campo que cambia
    obj.t_cal = QLineEdit("22.0")
    obj.p_cal = QLineEdit("101.325")
    obj.h_cal = QLineEdit("50.0")
    obj.v1_cal = QLineEdit("")
    obj.sel_activo = QCheckBox()
    obj.sel_activo.setChecked(True)  # ya estaba activo, sin cambio

    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem()
    item.setData(Qt.UserRole, id_equipo)
    obj.table.setItem(0, 0, item)
    obj.table.setCurrentCell(0, 0)
    # hasattr(self, "imagen_path") es False -> hay_nueva_imagen = False
    return obj


def _mock_messagebox(monkeypatch):
    monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(equipos_mod.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))


def _imagen_de_la_fila_mas_reciente(ruta, model, serie):
    con = sqlite3.connect(ruta)
    fila = con.execute(
        "SELECT imagen_certificado FROM equipos WHERE model=? AND serie=? "
        "ORDER BY id DESC LIMIT 1", (model, serie)).fetchone()
    con.close()
    return fila[0]


class TestImagenCertificadoSeConservaAlEditarOtroCampo:
    def test_la_imagen_guardada_es_la_imagen_real_no_el_valor_de_vigente(
            self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo_con_imagen(bd_temporal, vigente=1)
        _mock_messagebox(monkeypatch)
        obj = _instancia_editando_fabricante(id_equipo)

        Config.guardarCambios(obj)

        imagen_guardada = _imagen_de_la_fila_mas_reciente(bd_temporal, "N30013", "2123")
        assert imagen_guardada == IMAGEN_REAL

    def test_funciona_igual_si_el_historico_tenia_vigente_0(
            self, app, bd_temporal, monkeypatch):
        """Con vigente=0, el bug viejo habría escrito 0 (falsy) -- distinto
        de None (sin imagen) pero igual de incorrecto; se prueba aparte
        para no depender de un valor "que por casualidad se parece a bytes"."""
        id_equipo = _preparar_equipo_con_imagen(bd_temporal, vigente=0)
        _mock_messagebox(monkeypatch)
        obj = _instancia_editando_fabricante(id_equipo)

        Config.guardarCambios(obj)

        imagen_guardada = _imagen_de_la_fila_mas_reciente(bd_temporal, "N30013", "2123")
        assert imagen_guardada == IMAGEN_REAL
