"""U5 (PLAN_PESTANA_USUARIOS_02-09.md): la pestaña de usuarios. La UI NO
decide el permiso -- pregunta a `es_fisico_jefe` solo para pintar (mostrar
u ocultar los botones); el servicio (U3/U4/U4-bis) vuelve a preguntarlo
para actuar. Si solo se ocultara el botón, el control sería cosmético.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.encriptarInfo import encrypt_data
from data.ManejoDatos.user import Usuario
from ui.paginasGuia.usuarios import Usuarios


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sembrar_usuario(ruta, user, fullname, rol_sistema, active=1,
                      password="clave", firma=b"BYTES_DE_FIRMA_REAL"):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, "
        "firma, rol_sistema) VALUES (?, ?, ?, ?, '1', 'Físico Médico', ?, ?)",
        (user, encrypt_data(password), fullname, active, firma, rol_sistema))
    con.commit()
    con.close()


def _sembrar_seis_cuentas_mas(ruta):
    """`admin` ya existe (createAdmin) -- se agregan 6 más para llegar a
    las 7 cuentas [medido] en la sección 0 del plan, con al menos una
    inactiva."""
    _sembrar_usuario(ruta, "lamaya", "Luz Adriana Maya", "jefe")
    _sembrar_usuario(ruta, "accastellanos", "Cristian Castellanos", "fisico")
    _sembrar_usuario(ruta, "adloaiza", "Andres David Loaiza Baena", "fisico")
    _sembrar_usuario(ruta, "dmesa", "Daniela Mesa Lotero", "fisico")
    _sembrar_usuario(ruta, "jjcastillo", "Javier Castillo", "fisico", active=0)
    _sembrar_usuario(ruta, "JADIAZ", "José Antonio Diaz Merchán", "fisico")


class TestBotonesSoloParaElJefe:

    def test_fisico_no_tiene_boton_de_alta(self, app, bd_temporal):
        _sembrar_seis_cuentas_mas(bd_temporal)
        widget = Usuarios(Usuario(username="jjcastillo", fullname="Javier Castillo"))
        assert not hasattr(widget, "btn_agregar")
        assert not hasattr(widget, "btn_baja")
        assert not hasattr(widget, "btn_reactivar")
        assert not hasattr(widget, "btn_cambiar_rol")

    def test_jefe_tiene_boton_de_alta_habilitado(self, app, bd_temporal):
        _sembrar_seis_cuentas_mas(bd_temporal)
        widget = Usuarios(Usuario(username="lamaya", fullname="Luz Adriana Maya"))
        assert hasattr(widget, "btn_agregar")
        assert widget.btn_agregar.isEnabled()

    def test_admin_tambien_ve_los_botones(self, app, bd_temporal):
        _sembrar_seis_cuentas_mas(bd_temporal)
        widget = Usuarios(Usuario(username="admin", fullname="Administrador"))
        assert hasattr(widget, "btn_agregar")
        assert widget.btn_agregar.isEnabled()


class TestTablaListaTodasLasCuentas:

    def test_lista_las_siete_cuentas_incluidas_las_inactivas(self, app, bd_temporal):
        _sembrar_seis_cuentas_mas(bd_temporal)
        widget = Usuarios(Usuario(username="lamaya", fullname="Luz Adriana Maya"))
        assert widget._tabla.rowCount() == 7

        usuarios_en_tabla = {
            widget._tabla.item(fila, 0).text() for fila in range(widget._tabla.rowCount())
        }
        assert usuarios_en_tabla == {
            "admin", "lamaya", "accastellanos", "adloaiza", "dmesa",
            "jjcastillo", "JADIAZ",
        }

    def test_no_expone_password_ni_firma_en_ninguna_celda(self, app, bd_temporal):
        """Recorre TODAS las celdas de la tabla -- ni la contraseña
        (cifrada o no) ni los bytes de la firma pueden aparecer en
        ninguna, sea cual sea el rol de quien mira."""
        _sembrar_seis_cuentas_mas(bd_temporal)
        widget = Usuarios(Usuario(username="jjcastillo", fullname="Javier Castillo"))

        for fila in range(widget._tabla.rowCount()):
            for columna in range(widget._tabla.columnCount()):
                item = widget._tabla.item(fila, columna)
                texto = item.text() if item is not None else ""
                assert "BYTES_DE_FIRMA_REAL" not in texto
                assert "clave" not in texto
                # Tampoco la forma cifrada (base64 de encrypt_data) debe
                # colarse -- ninguna columna mostrada es 'password'.
                assert "AES" not in texto
