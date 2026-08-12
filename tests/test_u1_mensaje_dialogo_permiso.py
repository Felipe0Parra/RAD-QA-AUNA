"""U1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §U1): el mensaje de
`DialogAdminPermisoEliminar` deja de afirmar sin condición "ingrese la
cuenta de administrador" -- con DA-35 vigente (TEMPORAL,
PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md) eso es falso, cualquier
físico logueado con rol resuelto sirve.

El texto se DERIVA de `es_admin_equivalente(self.user._usuario)` (el
usuario CON SESIÓN ABIERTA que abrió el diálogo, no lo que se teclee
después):
  - si ya califica -> "Para continuar, confirme su contraseña, <nombre>."
  - si no califica -> "Para continuar ingrese una cuenta con permiso de
    administrador."

Así el mensaje sigue siendo cierto tanto con DA-35 vigente como el día que
se revierta, sin volver a tocar este archivo -- por eso la mitad de los
tests aísla la lógica del texto mockeando `es_admin_equivalente`
directamente (no depende de cómo esté resuelto DA-35 hoy), y la otra mitad
confirma el enganche real contra una BD temporal con rol_sistema sembrado
de verdad (mismo patrón que test_c3_permisos_admin_jefe.py).
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.dialogs as dialogs_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.encriptarInfo import encrypt_data
from ui.paginasGuia.dialogs import DialogAdminPermisoEliminar

TEXTO_VIEJO = "Para continuar ingrese la cuenta de administrador y su contraseña."
TEXTO_NO_CALIFICA = "Para continuar ingrese una cuenta con permiso de administrador."


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


class _UsuarioLogueado:
    def __init__(self, usuario, nombre=None):
        self._usuario = usuario
        self._nombre = nombre


class _UsuarioLogueadoSinNombre:
    """El único atributo que garantiza el resto del código (`_usuario`) --
    la personalización debe caer a él si `_nombre` no existe."""
    _usuario = "accastellanos"


class TestTextoDerivadoDePermiso:
    """Aísla la lógica del texto de la resolución real de DA-35 mockeando
    es_admin_equivalente directamente."""

    def test_usuario_que_ya_califica_ve_mensaje_personalizado(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(dialogs_mod, "es_admin_equivalente", lambda u: True)
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueado("lamaya", "Luz Adriana Maya"))
        assert dlg.subtitle_label.text() == "Para continuar, confirme su contraseña, Luz Adriana Maya."

    def test_usuario_que_no_califica_ve_mensaje_generico(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(dialogs_mod, "es_admin_equivalente", lambda u: False)
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueado("fisico_x", "Un Físico"))
        assert dlg.subtitle_label.text() == TEXTO_NO_CALIFICA

    def test_ninguno_de_los_dos_mensajes_es_el_texto_viejo(self, app, bd_temporal, monkeypatch):
        """Regresión directa: el texto viejo mentía sobre requerir 'la
        cuenta de administrador' bajo DA-35 -- no debe volver a aparecer,
        califique o no el usuario."""
        for califica in (True, False):
            monkeypatch.setattr(dialogs_mod, "es_admin_equivalente", lambda u, c=califica: c)
            dlg = DialogAdminPermisoEliminar(_UsuarioLogueado("x", "X"))
            assert dlg.subtitle_label.text() != TEXTO_VIEJO
            assert "la cuenta de administrador" not in dlg.subtitle_label.text()

    def test_sin_nombre_completo_cae_al_usuario_de_login(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(dialogs_mod, "es_admin_equivalente", lambda u: True)
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueadoSinNombre())
        assert dlg.subtitle_label.text() == "Para continuar, confirme su contraseña, accastellanos."

    def test_no_llama_a_es_admin_equivalente_con_el_texto_tecleado_despues(
            self, app, bd_temporal, monkeypatch):
        """El mensaje se decide en la construcción -- antes de que el
        físico teclee nada en admin_user -- así que debe consultarse con el
        usuario LOGUEADO (self.user), no con el campo de texto (que nace en
        'admin', el valor por defecto del campo, no de la sesión)."""
        llamado_con = []

        def _fake(usuario):
            llamado_con.append(usuario)
            return True

        monkeypatch.setattr(dialogs_mod, "es_admin_equivalente", _fake)
        DialogAdminPermisoEliminar(_UsuarioLogueado("fparrap", "Felipe Parra Paez"))
        assert llamado_con == ["fparrap"]


class TestEnganchadoConDA35Real:
    """Integración de punta a punta contra una BD temporal real, sin
    mockear es_admin_equivalente -- confirma que el texto deriva de verdad
    del estado vigente de DA-35, no de una constante paralela."""

    def test_fisico_con_rol_resuelto_ve_mensaje_personalizado(self, app, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, "
            "role, rol_sistema) VALUES (?, ?, ?, 1, '1', 'Físico Médico', 'fisico')",
            ("accastellanos", encrypt_data("clave123"), "Cristian Castellanos"))
        con.commit()
        con.close()

        dlg = DialogAdminPermisoEliminar(_UsuarioLogueado("accastellanos", "Cristian Castellanos"))
        assert dlg.subtitle_label.text() == "Para continuar, confirme su contraseña, Cristian Castellanos."

    def test_usuario_sin_rol_resoluble_ni_en_el_respaldo_legado_ve_mensaje_generico(
            self, app, bd_temporal):
        """No sembrado en BD (rol_sistema no resuelve) y fuera del
        respaldo legado {"admin","lamaya"} -- no califica bajo ningún
        camino de es_admin_equivalente."""
        dlg = DialogAdminPermisoEliminar(_UsuarioLogueado("nadie_conocido", "Nadie"))
        assert dlg.subtitle_label.text() == TEXTO_NO_CALIFICA
