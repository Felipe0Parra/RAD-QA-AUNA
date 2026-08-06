"""C3 / DA-35 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.1): el
físico en jefe (lamaya) tiene permisos administrativos idénticos a admin
desde C3. Desde DA-35 (2026-08-06, decisión TEMPORAL del físico -- "por ahora
asignar a todos el mismo nivel de permiso que administrador"), CUALQUIER rol
resuelto ('admin'/'jefe'/'fisico') es admin-equivalente. Para revertir:
quitar "fisico" de ROLES_ADMIN_EQUIVALENTE en services/permisos.py -- no hay
ningún otro punto que tocar.

El respaldo LEGADO {"admin","lamaya"} (USUARIOS_ADMIN_EQUIVALENTE) es un
conjunto DISTINTO, solo consultado cuando el rol NO se puede resolver (BD sin
migrar, usuario inexistente); DA-35 no lo toca.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.permisos import (
    ROLES_ADMIN_EQUIVALENTE, USUARIOS_ADMIN_EQUIVALENTE, es_admin_equivalente)


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


class TestEsAdminEquivalente:

    def test_admin_es_equivalente(self):
        assert es_admin_equivalente("admin") is True

    def test_lamaya_es_equivalente(self):
        assert es_admin_equivalente("lamaya") is True

    def test_fisico_con_rol_resuelto_es_equivalente_da35(self, bd_temporal):
        """DA-35: un usuario cuyo rol_sistema RESUELTO en BD es 'fisico' es
        admin-equivalente. Antes de DA-35 esta aserción era False."""
        for user in ("accastellanos", "adloaiza", "dmesa", "jjcastillo", "JADIAZ"):
            _sembrar_usuario(bd_temporal, user, "fisico")
            assert es_admin_equivalente(user) is True, user

    def test_usuario_sin_rol_resoluble_sigue_denegado(self, bd_temporal):
        """Anti-regresión de DA-35: un nombre que no existe en `users` (rol
        NO resoluble) cae al respaldo legado {"admin","lamaya"} -- que DA-35
        no toca -- y sigue denegado."""
        assert es_admin_equivalente("nombre_que_no_existe") is False

    def test_tolera_mayusculas_y_espacios(self):
        assert es_admin_equivalente("LAMAYA") is True
        assert es_admin_equivalente(" admin ") is True

    def test_none_y_vacio_no_lanzan_y_no_son_equivalentes(self):
        assert es_admin_equivalente(None) is False
        assert es_admin_equivalente("") is False

    def test_conjunto_legado_no_crece_por_accidente(self):
        assert USUARIOS_ADMIN_EQUIVALENTE == {"admin", "lamaya"}

    def test_roles_admin_equivalente_incluye_fisico_da35(self):
        assert ROLES_ADMIN_EQUIVALENTE == {"admin", "jefe", "fisico"}
