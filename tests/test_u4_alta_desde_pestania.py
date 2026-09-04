"""U4 (PLAN_PESTANA_USUARIOS_02-09.md): el alta desde la pestaña reusa
`UsuarioData.add_user` -- la MISMA operación que ya usa el registro
público (E6, F3, A6.2), en vez de reescribir el cifrado de la contraseña,
la validación de `fullname` o la auditoría.

`add_user` colapsa "ya existe" / "fullname vacío" / "error de BD" en un
solo `None` -- `crear_usuario` distingue las dos primeras ANTES de
llamarlo (O-5), para que la pestaña nunca tenga que mostrar "no se pudo
crear" sin decir por qué.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.encriptarInfo import decrypt_data
from services.gestion_usuarios import (
    MOTIVO_CREADO, MOTIVO_FULLNAME_VACIO, MOTIVO_SIN_PERMISO,
    MOTIVO_USUARIO_DUPLICADO, crear_usuario)


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sembrar_usuario(ruta, user, fullname, rol_sistema):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES (?, 'x', ?, 1, '1', 'Físico Médico', ?)",
        (user, fullname, rol_sistema))
    con.commit()
    con.close()


def _fila_users(ruta, user):
    con = sqlite3.connect(ruta)
    fila = con.execute(
        "SELECT password, fullname, rol_sistema FROM users WHERE user=?", (user,)
    ).fetchone()
    con.close()
    return fila


class TestAltaDesdeLaPestania:

    def test_jefe_crea_usuario_con_password_cifrada_y_rol_fisico(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")

        exito, motivo = crear_usuario(
            {"user": "nuevofisico", "password": "clave_en_claro",
             "fullname": "Nuevo Físico"},
            "lamaya")

        assert (exito, motivo) == (True, MOTIVO_CREADO)

        password_guardada, fullname, rol_sistema = _fila_users(bd_temporal, "nuevofisico")
        assert password_guardada != "clave_en_claro", (
            "la contraseña NUNCA debe guardarse en claro")
        assert decrypt_data(password_guardada) == "clave_en_claro"
        assert fullname == "Nuevo Físico"
        # El rol_sistema SIEMPRE nace 'fisico', aunque lo pida el jefe --
        # ascender a 'jefe' es U4-bis, una operación aparte.
        assert rol_sistema == "fisico"

    def test_fisico_no_puede_crear_usuarios(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")

        exito, motivo = crear_usuario(
            {"user": "otro", "password": "x", "fullname": "Otra Persona"},
            "jjcastillo")

        assert (exito, motivo) == (False, MOTIVO_SIN_PERMISO)
        assert _fila_users(bd_temporal, "otro") is None

    def test_usuario_duplicado_da_un_motivo_propio_no_none_mudo(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", "fisico")

        exito, motivo = crear_usuario(
            {"user": "dmesa", "password": "x", "fullname": "Daniela Mesa Otra Vez"},
            "lamaya")

        assert (exito, motivo) == (False, MOTIVO_USUARIO_DUPLICADO)

    def test_fullname_vacio_es_rechazado(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")

        exito, motivo = crear_usuario(
            {"user": "sinfullname", "password": "x", "fullname": "   "},
            "lamaya")

        assert (exito, motivo) == (False, MOTIVO_FULLNAME_VACIO)
        assert _fila_users(bd_temporal, "sinfullname") is None

    def test_admin_tambien_puede_crear_usuarios(self, bd_temporal):
        exito, motivo = crear_usuario(
            {"user": "otro_mas", "password": "x", "fullname": "Otro Más"},
            "admin")
        assert (exito, motivo) == (True, MOTIVO_CREADO)
