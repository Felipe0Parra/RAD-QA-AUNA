"""C3 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.3/§7.7a): DialogAdminPermiso y
DialogAdminPermiso2 (Login.py: crear usuario / cambiar contraseña) aceptan
admin O lamaya con su propia contraseña; cualquier otro físico con
contraseña válida queda rechazado con un mensaje distinto al de contraseña
incorrecta.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import ui.paginasGuia.dialogs as dialogs_mod
from ui.paginasGuia.dialogs import DialogAdminPermiso, DialogAdminPermiso2
from data.ManejoDatos.user import Usuario


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _mock_login(usuarios_validos):
    # `accion` (A8): los diálogos de permiso pasan ACCION_AUTORIZACION como 2º
    # posicional. El mock la acepta y la ignora -- qué acción se registra lo
    # cubre test_a8_a9_rastro_login_limpio.py; aquí solo importa el permiso.
    def _login(self, user, accion=None):
        if user._usuario in usuarios_validos:
            return Usuario(username=user._usuario, password=user._clave)
        return None
    return _login


@pytest.mark.parametrize("dialogo_cls", [DialogAdminPermiso, DialogAdminPermiso2])
class TestPermisosAdminJefe:

    def test_admin_con_contrasena_correcta_es_aceptado(
            self, app, dialogo_cls, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login", _mock_login({"admin"}))
        dlg = dialogo_cls()
        dlg.admin_user.setText("admin")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()
        assert dlg.res is not None
        assert dlg.labelwarnign.text() == ""

    def test_lamaya_con_contrasena_correcta_es_aceptada(
            self, app, dialogo_cls, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login",
                             _mock_login({"admin", "lamaya"}))
        dlg = dialogo_cls()
        dlg.admin_user.setText("lamaya")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()
        assert dlg.res is not None
        assert dlg.labelwarnign.text() == ""

    def test_fisico_sin_permiso_admin_con_contrasena_correcta_es_rechazado(
            self, app, dialogo_cls, monkeypatch):
        monkeypatch.setattr(
            dialogs_mod.UsuarioData, "login",
            _mock_login({"admin", "lamaya", "accastellanos"}))
        dlg = dialogo_cls()
        dlg.admin_user.setText("accastellanos")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()
        assert dlg.labelwarnign.text() == "Este usuario no tiene permisos administrativos"

    def test_contrasena_incorrecta_da_mensaje_distinto(
            self, app, dialogo_cls, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login", _mock_login(set()))
        dlg = dialogo_cls()
        dlg.admin_user.setText("admin")
        dlg.admin_password.setText("clave_mala")
        dlg.open_main_window()
        assert dlg.labelwarnign.text() == "Verifique la contraseña por favor"

    def test_campo_usuario_ya_no_es_de_solo_lectura(self, app, dialogo_cls):
        dlg = dialogo_cls()
        assert dlg.admin_user.isReadOnly() is False
