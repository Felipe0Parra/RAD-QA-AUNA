"""A8/A9 (§8.1 H3/H4 del PLAN_AUDITORIA_DOS_EJES_21-07): el rastro de sesión
deja de mentir.

Hallazgos del rebuild 22-07 (BaseDatosQA(Rebuild_22-07-2026).db, 72 filas):
  - 36 de 72 filas eran `login` -- la mitad del audit_log era ruido.
  - Pares de `login` idénticos al segundo (ids 24/25, 26/27, 30/31, 33/34,
    39/40, 63/64, 71/72): `Login.authenticateUser` llamaba `verify()` dos
    veces y cada una auditaba (A9).
  - Los `login` sueltos (ids 35-38, 50-56) eran en realidad confirmaciones de
    permiso de los diálogos `DialogAdminPermiso*`, que autenticaban vía
    `UsuarioData.login()` (A8). El físico los leía como "mi borrado quedó
    registrado como un login".
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.usuariosManager as um_mod
import ui.paginasGuia.dialogs as dialogs_mod
from data.ManejoDatos.user import Usuario
from services.audit_minimo import ACCION_LOGIN, ACCION_AUTORIZACION
from ui.paginasGuia.dialogs import (
    DialogAdminPermiso, DialogAdminPermiso2,
    DialogAdminPermisoEliminar, DialogAdminPermisoEditar,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def auditoria_capturada(monkeypatch):
    """Captura lo que `login()` escribiría, sin tocar ninguna BD."""
    registros = []
    monkeypatch.setattr(
        um_mod, "_registrar_auditoria",
        lambda usuario, accion, **kw: registros.append((usuario, accion, kw)))

    class _ConexionFalsa:
        def conectar(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self):
            return self

        def execute(self, *a):
            return self

        def fetchone(self):
            # (id, user, password, fullname, ...) -- password ya "descifrada"
            return (1, "admin", "cifrada", "Administrador", 1, None, None)

    monkeypatch.setattr(um_mod.con, "Conexion", lambda: _ConexionFalsa())
    monkeypatch.setattr(um_mod, "decrypt_data", lambda _: "clave_ok")
    return registros


class TestA8AutorizacionNoEsLogin:

    def test_login_por_defecto_sigue_siendo_login(self, auditoria_capturada):
        """Login.py no pasa `accion`: el inicio de sesión real no cambia."""
        um_mod.UsuarioData().login(Usuario("admin", "clave_ok"))
        assert [a for _, a, _ in auditoria_capturada] == [ACCION_LOGIN]

    def test_login_acepta_accion_explicita(self, auditoria_capturada):
        um_mod.UsuarioData().login(Usuario("admin", "clave_ok"), ACCION_AUTORIZACION)
        assert [a for _, a, _ in auditoria_capturada] == [ACCION_AUTORIZACION]

    def test_credencial_erronea_tambien_respeta_la_accion(self, auditoria_capturada):
        """Un intento fallido de AUTORIZAR no debe contarse como intento de
        login fallido: son eventos de seguridad distintos."""
        um_mod.UsuarioData().login(Usuario("admin", "clave_mala"), ACCION_AUTORIZACION)
        assert [a for _, a, _ in auditoria_capturada] == [ACCION_AUTORIZACION]

    @pytest.mark.parametrize("dialogo_cls", [
        DialogAdminPermiso, DialogAdminPermiso2,
        DialogAdminPermisoEliminar, DialogAdminPermisoEditar,
    ])
    def test_los_cuatro_dialogos_de_permiso_registran_autorizacion(
            self, app, dialogo_cls, monkeypatch):
        """Ninguno de los 4 diálogos debe escribir `login`."""
        recibido = {}

        def _login_espia(self, user, accion=ACCION_LOGIN):
            recibido["accion"] = accion
            return Usuario(username=user._usuario, password=user._clave)

        monkeypatch.setattr(dialogs_mod.UsuarioData, "login", _login_espia)

        dlg = (dialogo_cls(Usuario("admin", "x"))
               if dialogo_cls in (DialogAdminPermisoEliminar, DialogAdminPermisoEditar)
               else dialogo_cls())
        dlg.admin_user.setText("admin")
        dlg.admin_password.setText("clave_ok")
        dlg.open_main_window()

        assert recibido["accion"] == ACCION_AUTORIZACION, (
            f"{dialogo_cls.__name__} sigue escribiendo '{recibido.get('accion')}' "
            "en audit_log en vez de 'autorizacion'")


class TestA9SinLoginDuplicado:

    def test_authenticate_user_verifica_una_sola_vez(self, app, monkeypatch):
        """El bug: `if self.verify(): user_id = self.verify()` -> 2 filas
        `login` idénticas al segundo por cada inicio de sesión."""
        from ui.paginasEntrReg.Login import LoginPage

        llamadas = []
        usuario_falso = Usuario(username="admin", fullname="Administrador")

        monkeypatch.setattr(LoginPage, "verify",
                            lambda self: llamadas.append(1) or usuario_falso)

        pagina = LoginPage.__new__(LoginPage)  # sin construir la GUI completa
        emitidos = []
        pagina.login_successful = type(
            "S", (), {"emit": lambda _self, v: emitidos.append(v)})()

        LoginPage.authenticateUser(pagina)

        assert len(llamadas) == 1, (
            f"verify() se llamó {len(llamadas)} veces: cada llamada audita un "
            "login, por eso aparecían pares idénticos en audit_log")
        assert emitidos == [usuario_falso], "debe emitir el usuario autenticado"

    def test_credenciales_invalidas_no_emiten_ni_duplican(self, app, monkeypatch):
        from ui.paginasEntrReg.Login import LoginPage

        llamadas = []
        monkeypatch.setattr(LoginPage, "verify",
                            lambda self: llamadas.append(1) or False)

        pagina = LoginPage.__new__(LoginPage)
        emitidos = []
        pagina.login_successful = type(
            "S", (), {"emit": lambda _self, v: emitidos.append(v)})()

        LoginPage.authenticateUser(pagina)

        assert len(llamadas) == 1
        assert emitidos == []
