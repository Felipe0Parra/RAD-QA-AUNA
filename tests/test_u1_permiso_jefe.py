"""U1 (PLAN_PESTANA_USUARIOS_02-09.md): `es_fisico_jefe()` -- un predicado
propio para "¿esta persona puede administrar usuarios?", deliberadamente
SEPARADO de `es_admin_equivalente()`. DA-35 (06-08, decisión TEMPORAL) metió
"fisico" en `ROLES_ADMIN_EQUIVALENTE`; reusar esa función para la gestión de
usuarios habría hecho que la restricción pedida por el físico ("únicamente
por el físico médico en jefe") no restringiera nada -- y el defecto sería
INVISIBLE, la pestaña se vería correcta y funcionaría para las 7 cuentas.

Fallback INVERTIDO respecto a `es_admin_equivalente`: aquí, si el rol no se
puede resolver, se DENIEGA -- lo contrario del criterio legado (C3), que
concede de más para no dejar a la física en jefe sin permisos en un turno
clínico. Aquí conceder de más significa que cualquiera pueda crear cuentas,
sin ninguna urgencia clínica que lo justifique.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.permisos import (
    ROLES_GESTION_USUARIOS, es_admin_equivalente, es_fisico_jefe)


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sembrar_usuario(ruta, user, rol_sistema):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES (?, 'x', ?, 1, '1', 'Físico Médico', ?)",
        (user, user, rol_sistema))
    con.commit()
    con.close()


class TestEsFisicoJefe:

    def test_rol_jefe_administra(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "jefe")
        assert es_fisico_jefe("lamaya") is True

    def test_rol_admin_administra(self, bd_temporal):
        # `Conexion()` (fixture `bd_temporal`) ya siembra "admin" con
        # rol_sistema='admin' (createAdmin + _asegurar_roles_de_sistema) --
        # sembrarlo de nuevo aquí violaría el UNIQUE de `users.user`.
        assert es_fisico_jefe("admin") is True

    def test_rol_fisico_NO_administra(self, bd_temporal):
        """El corazón de U1: DA-35 hace a 'fisico' admin-equivalente para
        el resto de la app, pero NO para la gestión de usuarios."""
        _sembrar_usuario(bd_temporal, "jjcastillo", "fisico")
        assert es_fisico_jefe("jjcastillo") is False

    def test_usuario_inexistente_no_administra(self, bd_temporal):
        assert es_fisico_jefe("nombre_que_no_existe") is False

    def test_none_y_vacio_no_administran(self, bd_temporal):
        assert es_fisico_jefe(None) is False
        assert es_fisico_jefe("") is False

    def test_lamaya_con_bd_sin_migrar_no_administra(self, bd_temporal):
        """El test que importa: a diferencia de `es_admin_equivalente`
        (que caería al respaldo legado {"admin","lamaya"} y devolvería
        True), `es_fisico_jefe` NO tiene fallback legado -- una fila real
        con `rol_sistema` NULL (BD no migrada a rol_sistema, o el valor
        nunca se pobló) debe negar el permiso, no concederlo."""
        _sembrar_usuario(bd_temporal, "lamaya", None)
        assert es_fisico_jefe("lamaya") is False
        # Confirma que el contraste es real: el legado SÍ la habría dejado pasar.
        assert es_admin_equivalente("lamaya") is True

    def test_tolera_mayusculas_y_espacios(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "jefe")
        assert es_fisico_jefe("LAMAYA") is True
        assert es_fisico_jefe(" lamaya ") is True


class TestDA35NoSeAltero:
    """U1 no debe tocar DA-35: `es_admin_equivalente` sigue devolviendo
    True para 'fisico' (la apertura temporal sigue vigente)."""

    def test_fisico_sigue_siendo_admin_equivalente(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "fisico")
        assert es_admin_equivalente("jjcastillo") is True

    def test_roles_gestion_usuarios_no_incluye_fisico(self):
        assert ROLES_GESTION_USUARIOS == {"admin", "jefe"}
        assert "fisico" not in ROLES_GESTION_USUARIOS
