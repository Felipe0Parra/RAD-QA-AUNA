"""A6.2 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): identidad y catálogo dejan
rastro en `audit_log`.

Tres huecos confirmados por el inventario AST de A6.1
(tests/test_a6_1_tripwire_auditoria.py): `usuariosManager.py` ya auditaba
login/logout (A4) pero no el alta de usuario ni el cambio de contraseña; y
`equipos.py` ya auditaba alta y edición del catálogo pero no el borrado
físico (el mismo catálogo curado a mano en H2.6/H2.10).

- `add_user`: alta desde `register_page.py`, sin sesión activa todavía --
  se audita con la identidad del usuario recién creado (igual que la rama
  "OK" de `login()`), no con un "actor" que no existe en ese flujo.
- `update_password`: recibe `usuario` como parámetro propio, se audita con
  ese mismo valor.
- `eliminarEquipo`: identificado ANTES de anular (mismo patrón de `ref`
  que `guardarCambios`, f"{modelo}/{serie}"). La cobertura de esta función
  vive ahora en `test_e2_borrado_equipos.py` -- E2
  (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §3) le agregó un gate de permiso
  admin/jefe y cambió el DELETE físico por soft-delete (activo=0).
"""
import sqlite3

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
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
    conexion = Conexion()  # corre el DDL real
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _audit_log(ruta_db):
    con = sqlite3.connect(ruta_db)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestAddUserAudita:
    def test_alta_de_usuario_audita_con_su_propio_nombre(self, bd_temporal):
        nuevo = Usuario(username="nuevo_fisico", password="clave123",
                         fullname="Físico Nuevo", active=1, identificacion="99",
                         role="fisico", firma=b"")

        resultado = UsuarioData().add_user(nuevo)

        assert resultado is not None
        assert _audit_log(bd_temporal) == [
            ("Físico Nuevo", "guardar", "users", "nuevo_fisico", "")]

    def test_usuario_ya_existente_no_agrega_ni_audita(self, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("repetido", encrypt_data("x"), "Ya Existe", 1, "1", "fisico"))
        con.commit()
        con.close()

        duplicado = Usuario(username="repetido", password="otra",
                             fullname="Otro Nombre", active=1,
                             identificacion="2", role="fisico", firma=b"")
        resultado = UsuarioData().add_user(duplicado)

        assert resultado is None
        assert _audit_log(bd_temporal) == []


class TestUpdatePasswordAudita:
    def test_cambio_de_contrasena_audita_con_el_nombre_completo(self, bd_temporal):
        """A6.2-bis: identidad HOMOGÉNEA con el resto de `audit_log`.

        La primera versión (A6.2) auditaba con el nombre de CUENTA
        ("ffisico"), porque es el único dato que `update_password` recibe --
        mientras que `add_user` y `login()` usan el nombre COMPLETO. En la BD
        del rebuild del físico (27-07-2026) eso dejó dos filas de la misma
        persona sobre `users` con identidades distintas (id 33 "Felipe Parra
        Paez" vs id 35 "fparrap"), ilegible en el visor. Ahora espeja a
        `add_user`: nombre completo en `usuario`, cuenta en `ref`.
        """
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("ffisico", encrypt_data("vieja"), "Físico de Prueba", 1, "1", "fisico"))
        con.commit()
        con.close()

        ok = UsuarioData().update_password("ffisico", "nueva_clave")

        assert ok is True
        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert ref == "ffisico"
        assert accion == "actualizar"
        assert tabla == "users"
        assert "contraseña" in detalle


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"

# TestEliminarEquipoAudita se retiró de aquí -- E2
# (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §3) reemplazó el DELETE físico
# (sin barrera de permiso) por un gate DialogAdminPermisoEliminar +
# soft-delete. Cobertura completa en test_e2_borrado_equipos.py.
