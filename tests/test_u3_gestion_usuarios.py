"""U3 (PLAN_PESTANA_USUARIOS_02-09.md): `services/gestion_usuarios.py`,
única puerta a `users` para la pestaña -- el permiso se verifica DENTRO
del servicio, no solo en la UI (ocultar un botón no es un control de
acceso). Sin esto, la pestaña repetiría la divergencia de DP-79 (dos
limpiadores que no coinciden) en el sitio más sensible de la aplicación.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.gestion_usuarios import dar_de_baja, listar_usuarios, reactivar


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sembrar_usuario(ruta, user, fullname, rol_sistema, active=1):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES (?, 'x', ?, ?, '1', 'Físico Médico', ?)",
        (user, fullname, active, rol_sistema))
    con.commit()
    con.close()


def _filas_audit(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log ORDER BY id"
    ).fetchall()
    con.close()
    return filas


def _active_de(ruta, user):
    con = sqlite3.connect(ruta)
    fila = con.execute("SELECT active FROM users WHERE user=?", (user,)).fetchone()
    con.close()
    return fila[0] if fila else None


class TestListarUsuarios:

    def test_no_devuelve_password_ni_firma(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")
        usuarios = listar_usuarios()
        assert usuarios, "debe haber al menos una fila"
        for fila in usuarios:
            assert "password" not in fila
            assert "firma" not in fila

    def test_incluye_lo_necesario_para_la_pestana(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")
        usuarios = listar_usuarios()
        objetivo = next(u for u in usuarios if u["user"] == "jjcastillo")
        assert objetivo["fullname"] == "Javier Castillo"
        assert objetivo["rol_sistema"] == "fisico"
        assert objetivo["active"] == 1


class TestDarDeBaja:

    def test_pedida_por_fisico_es_rechazada(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")
        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", "fisico")

        resultado = dar_de_baja("dmesa", "jjcastillo")

        assert resultado is False
        assert _active_de(bd_temporal, "dmesa") == 1

        usuario, accion, tabla, ref, detalle = _filas_audit(bd_temporal)[-1]
        assert detalle == "denegado: sin permiso de gestión de usuarios"
        assert usuario == "Javier Castillo"
        assert tabla == "users"
        assert ref == "dmesa"

    def test_pedida_por_jefe_se_aplica(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", "fisico")

        resultado = dar_de_baja("dmesa", "lamaya")

        assert resultado is True
        assert _active_de(bd_temporal, "dmesa") == 0

        usuario, accion, tabla, ref, detalle = _filas_audit(bd_temporal)[-1]
        assert accion == "anular"
        assert detalle == "baja"
        assert usuario == "Luz Adriana Maya"
        assert ref == "dmesa"

    def test_auto_baja_es_rechazada(self, bd_temporal):
        """Ni el jefe puede darse de baja a sí mismo (O-3-i)."""
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")

        resultado = dar_de_baja("lamaya", "lamaya")

        assert resultado is False
        assert _active_de(bd_temporal, "lamaya") == 1
        _, _, _, _, detalle = _filas_audit(bd_temporal)[-1]
        assert "no puede darse de baja a sí mismo" in detalle

    def test_baja_del_ultimo_jefe_es_rechazada(self, bd_temporal):
        """O-3-ii: no se apaga la última cuenta ACTIVA capaz de
        administrar usuarios -- aislado de la guarda de auto-baja (ya
        probada aparte) con un solicitante DISTINTO del objetivo.

        `admin` (creada por `createAdmin`) se desactiva para dejar a
        `lamaya` como única cuenta de gestión activa. El solicitante
        (`jefe_fantasma`) tiene `rol_sistema='jefe'` -- pasa
        `es_fisico_jefe`, que no mira `active` -- pero está él mismo
        inactivo, así que la guarda (que sí filtra por `active=1`) no lo
        cuenta: prueba que `_quedaria_sin_jefes` mira el ESTADO REAL en
        la BD, no la identidad de quien pregunta."""
        con = sqlite3.connect(bd_temporal)
        con.execute("UPDATE users SET active=0 WHERE user='admin'")
        con.commit()
        con.close()
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        _sembrar_usuario(bd_temporal, "jefe_fantasma", "Jefe Fantasma", "jefe", active=0)

        resultado = dar_de_baja("lamaya", "jefe_fantasma")

        assert resultado is False
        assert _active_de(bd_temporal, "lamaya") == 1
        _, _, _, _, detalle = _filas_audit(bd_temporal)[-1]
        assert "quedaría sin nadie que administre usuarios" in detalle

    def test_baja_de_cuenta_inexistente_no_hace_nada(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        assert dar_de_baja("no_existe", "lamaya") is False


class TestReactivar:

    def test_reactivar_devuelve_active_a_uno_y_audita(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", "fisico", active=0)

        resultado = reactivar("dmesa", "lamaya")

        assert resultado is True
        assert _active_de(bd_temporal, "dmesa") == 1
        usuario, accion, tabla, ref, detalle = _filas_audit(bd_temporal)[-1]
        assert accion == "reactivar"
        assert detalle == "reactivado"
        assert usuario == "Luz Adriana Maya"

    def test_reactivar_pedida_por_fisico_es_rechazada(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")
        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", "fisico", active=0)

        assert reactivar("dmesa", "jjcastillo") is False
        assert _active_de(bd_temporal, "dmesa") == 0


class TestBorradoFisicoSigueSiendoImposible:

    def test_delete_from_users_aborta(self, bd_temporal):
        """Documenta POR QUÉ la baja es lógica: el trigger E8 hace
        imposible el DELETE, con o sin este plan."""
        con = sqlite3.connect(bd_temporal)
        with pytest.raises(sqlite3.IntegrityError, match="no admite borrado fisico"):
            con.execute("DELETE FROM users WHERE user='admin'")
        con.close()
