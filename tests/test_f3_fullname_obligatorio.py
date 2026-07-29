"""F3 (PLAN_F_CIERRE_ESTANDAR_29-07.md): `users.fullname` no puede quedar
vacío.

`fullname` es `TEXT UNIQUE` -- admite vacío por esquema. Es el destino de 6
FK (`aceleradorlineal_600/ix`, `braqui`, `halcyon`, `controles.user_id` y
`.user_id_f2`) y la identidad que `audit_log` conserva de por vida; un
usuario con `fullname=''` quedaría permanentemente inatribuible. La interfaz
de registro ya lo exige (`register_page.py` deshabilita "Crear cuenta" sin
texto en Nombre Completo) -- esta suite fija que `add_user` también lo
rechaza, para cualquier otro llamador presente o futuro.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData


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
    filas = con.execute("SELECT usuario, accion, tabla FROM audit_log").fetchall()
    con.close()
    return filas


def _usuarios(ruta_db):
    con = sqlite3.connect(ruta_db)
    filas = con.execute("SELECT user FROM users").fetchall()
    con.close()
    return filas


class TestFullnameVacioNoSeAgrega:
    def test_fullname_vacio_no_inserta_y_devuelve_falsy(self, bd_temporal):
        usuario = Usuario(username="sin_nombre", password="clave123",
                          fullname="", active=1, identificacion="1",
                          role="fisico", firma=b"")

        resultado = UsuarioData().add_user(usuario)

        assert not resultado
        assert ("sin_nombre",) not in _usuarios(bd_temporal)
        assert _audit_log(bd_temporal) == []  # tampoco audita un alta que no ocurrió

    def test_fullname_de_solo_espacios_no_inserta(self, bd_temporal):
        usuario = Usuario(username="espacios", password="clave123",
                          fullname="   ", active=1, identificacion="1",
                          role="fisico", firma=b"")

        resultado = UsuarioData().add_user(usuario)

        assert not resultado
        assert ("espacios",) not in _usuarios(bd_temporal)

    def test_fullname_none_no_inserta(self, bd_temporal):
        usuario = Usuario(username="nulo", password="clave123",
                          fullname=None, active=1, identificacion="1",
                          role="fisico", firma=b"")

        resultado = UsuarioData().add_user(usuario)

        assert not resultado
        assert ("nulo",) not in _usuarios(bd_temporal)


class TestFullnameValidoSigueFuncionando:
    def test_alta_normal_sigue_insertando_y_auditando(self, bd_temporal):
        """El guardián de F3 no debe volverse un obstáculo para el camino
        normal -- mismo caso ya cubierto en A6.2, repetido aquí para que
        esta suite sea autocontenida sobre el contrato de F3."""
        usuario = Usuario(username="fisico_valido", password="clave123",
                          fullname="Físico Válido", active=1,
                          identificacion="1", role="fisico", firma=b"")

        resultado = UsuarioData().add_user(usuario)

        assert resultado is not None
        assert ("fisico_valido",) in _usuarios(bd_temporal)
        assert _audit_log(bd_temporal) == [("Físico Válido", "guardar", "users")]
