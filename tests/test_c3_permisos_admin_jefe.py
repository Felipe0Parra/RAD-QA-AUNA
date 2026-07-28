"""C3 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.3/§7.7a): DialogAdminPermiso,
DialogAdminPermiso2 (Login.py: crear usuario / cambiar contraseña) y
DialogAdminPermisoEliminar (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md: el
físico pidió "verificar que solo el administrador puede eliminar un
registro, o físico médico jefe") aceptan admin O lamaya con su propia
contraseña; cualquier otro físico con contraseña válida queda rechazado con
un mensaje distinto al de contraseña incorrecta.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QLabel

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.dialogs as dialogs_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.dialogs import (
    DialogAdminPermiso, DialogAdminPermiso2, DialogAdminPermisoEditar,
    DialogAdminPermisoEliminar)
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


class _UsuarioLogueadoFalso:
    _usuario = "accastellanos"


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class TestDialogAdminPermisoEliminarSoloAdminOJefe:
    """C3 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): antes este diálogo
    re-validaba la contraseña del USUARIO YA LOGUEADO (campo fijo, solo
    lectura) -- cualquier físico podía eliminar/anular un registro con su
    propia clave. Ahora exige admin o física en jefe, igual que crear
    usuario/cambiar contraseña."""

    def test_admin_con_contrasena_correcta_es_aceptado(self, app, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login", _mock_login({"admin"}))
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        dlg.admin_user.setText("admin")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()
        assert dlg.res is not None
        assert dlg.labelwarnign.text() == ""

    def test_lamaya_con_contrasena_correcta_es_aceptada(self, app, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login",
                             _mock_login({"admin", "lamaya"}))
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        dlg.admin_user.setText("lamaya")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()
        assert dlg.res is not None
        assert dlg.labelwarnign.text() == ""

    def test_el_propio_fisico_logueado_ya_no_puede_autorizar_con_su_clave(
            self, app, monkeypatch):
        """El caso que motivó la tarea: 'accastellanos' es el usuario YA
        LOGUEADO (el que antes se auto-aceptaba); ahora se rechaza igual que
        cualquier otro físico sin permisos."""
        monkeypatch.setattr(
            dialogs_mod.UsuarioData, "login",
            _mock_login({"admin", "lamaya", "accastellanos"}))
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        dlg.admin_user.setText("accastellanos")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()
        assert dlg.labelwarnign.text() == "Este usuario no tiene permisos administrativos"

    def test_contrasena_incorrecta_da_mensaje_distinto(self, app, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login", _mock_login(set()))
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        dlg.admin_user.setText("admin")
        dlg.admin_password.setText("clave_mala")
        dlg.open_main_window()
        assert dlg.labelwarnign.text() == "Verifique la contraseña por favor"

    def test_campo_usuario_ya_no_es_de_solo_lectura(self, app):
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        assert dlg.admin_user.isReadOnly() is False

    def test_intento_denegado_queda_auditado(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(
            dialogs_mod.UsuarioData, "login",
            _mock_login({"admin", "lamaya", "accastellanos"}))
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        dlg.admin_user.setText("accastellanos")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()

        con = sqlite3.connect(bd_temporal)
        filas = con.execute(
            "SELECT usuario, accion, detalle FROM audit_log").fetchall()
        con.close()
        assert len(filas) == 1
        usuario, accion, detalle = filas[0]
        assert usuario == "accastellanos"
        assert accion == "autorizacion"
        assert "denegado" in detalle and "accastellanos" in detalle

    def test_intento_aceptado_no_audita_denegacion(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login", _mock_login({"admin"}))
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        dlg.admin_user.setText("admin")
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert n == 0


class TestE4EditarReautenticaAlPropioFisico:
    """E4 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §5, decisión D1): editar es
    DELIBERADAMENTE menos estricto que eliminar -- reautenticación del propio
    físico, sin es_admin_equivalente. El texto viejo pedía "la cuenta de
    administrador" con el usuario del físico precargado, y el físico tecleaba
    la clave de admin sobre su propia cuenta (audit_log del rebuild 28-07,
    filas 47/48: dos autorizaciones fallidas seguidas). La conducta NO cambia;
    esta clase ancla la asimetría para que no se "arregle" por error."""

    def test_editar_acepta_al_propio_fisico_logueado(self, app, monkeypatch):
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login",
                             _mock_login({"accastellanos"}))
        dlg = DialogAdminPermisoEditar(_UsuarioLogueadoFalso())
        assert dlg.admin_user.text() == "accastellanos"  # precargado, no "admin"
        dlg.admin_password.setText("cualquierclave")
        dlg.open_main_window()
        assert dlg.res is not None
        assert dlg.labelwarnign.text() == ""

    def test_asimetria_editar_acepta_eliminar_rechaza(self, app, monkeypatch):
        """El MISMO físico con la MISMA clave válida: Editar acepta, Eliminar
        exige permisos administrativos."""
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login",
                             _mock_login({"accastellanos"}))

        editar = DialogAdminPermisoEditar(_UsuarioLogueadoFalso())
        editar.admin_password.setText("cualquierclave")
        editar.open_main_window()
        assert editar.res is not None

        eliminar = DialogAdminPermisoEliminar(_UsuarioLogueadoFalso())
        eliminar.admin_user.setText("accastellanos")
        eliminar.admin_password.setText("cualquierclave")
        eliminar.open_main_window()
        assert (eliminar.labelwarnign.text()
                == "Este usuario no tiene permisos administrativos")

    def test_el_texto_ya_no_pide_la_cuenta_de_administrador(self, app):
        dlg = DialogAdminPermisoEditar(_UsuarioLogueadoFalso())
        textos = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        assert "cuenta de administrador" not in textos
        assert "propia contraseña" in textos
