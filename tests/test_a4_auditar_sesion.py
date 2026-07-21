"""A4 (PLAN_AUDITORIA_DOS_EJES_21-07): login/logout dejan rastro en `audit_log`.

Antes de esta tarea, `UsuarioData.login()`/`logout()` (usuariosManager.py)
no auditaban nada -- ni un login exitoso, ni un intento fallido (usuario
inexistente o contraseña incorrecta), ni el cierre de sesión. Además
`MainWindow` nunca guardaba `self.user_id` (la línea quedaba comentada) --
sin eso, `cerrar()` (el logout real de la app: emite `reRun_signal` y vuelve
a la pantalla de login, ver `main.py:AppController.reRun`) no tenía forma de
saber quién cerraba sesión.
"""
import sqlite3

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
import ui.mainpages as mainpages_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.encriptarInfo import encrypt_data
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real -- crea las 69 tablas
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("ffisico", encrypt_data("clave123"), "Físico de Prueba", 1, "1", "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _audit_log(ruta_db):
    con = sqlite3.connect(ruta_db)
    filas = con.execute("SELECT usuario, accion, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestLoginAuditaExitoYFallos:
    def test_login_exitoso_audita_ok_con_el_fullname(self, bd_temporal):
        resultado = UsuarioData().login(Usuario(username="ffisico", password="clave123"))

        assert resultado is not None
        assert _audit_log(bd_temporal) == [("Físico de Prueba", "login", "OK")]

    def test_password_incorrecta_audita_con_el_usuario_intentado(self, bd_temporal):
        resultado = UsuarioData().login(Usuario(username="ffisico", password="mala"))

        assert resultado is None
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, detalle = filas[0]
        # Aún no hay fullname válido (login falló) -- se audita el intento.
        assert usuario == "ffisico"
        assert accion == "login"
        assert "incorrecta" in detalle

    def test_usuario_inexistente_audita_con_el_usuario_intentado(self, bd_temporal):
        resultado = UsuarioData().login(Usuario(username="no_existe", password="x"))

        assert resultado is None
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, detalle = filas[0]
        assert usuario == "no_existe"
        assert accion == "login"
        assert "no encontrado" in detalle


class TestLogoutAudita:
    def test_logout_registra_al_usuario(self, bd_temporal):
        UsuarioData().logout("Físico de Prueba")

        assert _audit_log(bd_temporal) == [("Físico de Prueba", "logout", "")]


class _SignalFalsa:
    def __init__(self):
        self.emitida = False

    def emit(self):
        self.emitida = True


class _MainWindowFalsa:
    """No es un QMainWindow real -- cerrar() solo toca user_id, reRun_signal
    y close(), así que basta un objeto con esa forma (evita instanciar todos
    los tabs reales de MainWindow.Tab, que no vienen al caso aquí)."""

    def __init__(self, user_id):
        self.user_id = user_id
        self.reRun_signal = _SignalFalsa()
        self.cerrada = False

    def close(self):
        self.cerrada = True


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class TestMainWindowCerrarAuditaLogout:
    def test_cerrar_audita_logout_con_el_usuario_resuelto(self, app, bd_temporal):
        fake = _MainWindowFalsa(user_id=_UsuarioFalso())

        mainpages_mod.MainWindow.cerrar(fake)

        assert fake.reRun_signal.emitida
        assert fake.cerrada
        assert _audit_log(bd_temporal) == [("Físico de Prueba", "logout", "")]
