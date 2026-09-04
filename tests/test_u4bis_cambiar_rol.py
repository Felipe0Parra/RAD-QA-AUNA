"""U4-bis (PLAN_PESTANA_USUARIOS_02-09.md, decidido por el físico el
02-09): el jefe puede nombrar a otro jefe. Operación de GOBIERNO, separada
del alta a propósito -- cambiar el rol de una cuenta es un acto
deliberado, no un dato de registro; meterlo en `U4` habría convertido el
alta rutinaria en el sitio donde por descuido se reparten permisos.

Reusa `_quedaria_sin_jefes` -- la MISMA guarda que ya usa `dar_de_baja`
(U3) -- en vez de una copia propia: dos copias de "no te quedes sin nadie
que administre" es exactamente el patrón que produjo DP-79.
"""
import ast
import sqlite3
from pathlib import Path

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.permisos import es_fisico_jefe
from services.gestion_usuarios import cambiar_rol_sistema


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
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


def _rol_de(ruta, user):
    con = sqlite3.connect(ruta)
    fila = con.execute("SELECT rol_sistema FROM users WHERE user=?", (user,)).fetchone()
    con.close()
    return fila[0] if fila else None


def _ultima_fila_audit(ruta):
    con = sqlite3.connect(ruta)
    fila = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    con.close()
    return fila


class TestPromocion:

    def test_jefe_promueve_a_fisico_y_queda_auditado_con_los_dos_valores(
            self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")

        resultado = cambiar_rol_sistema("jjcastillo", "jefe", "lamaya")

        assert resultado is True
        assert _rol_de(bd_temporal, "jjcastillo") == "jefe"
        assert es_fisico_jefe("jjcastillo") is True

        usuario, accion, tabla, ref, detalle = _ultima_fila_audit(bd_temporal)
        assert accion == "actualizar"
        assert detalle == "rol_sistema: fisico -> jefe"
        assert usuario == "Luz Adriana Maya"
        assert ref == "jjcastillo"

    def test_promocion_pedida_por_fisico_es_rechazada(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")
        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", "fisico")

        resultado = cambiar_rol_sistema("dmesa", "jefe", "jjcastillo")

        assert resultado is False
        assert _rol_de(bd_temporal, "dmesa") == "fisico"
        _, _, _, _, detalle = _ultima_fila_audit(bd_temporal)
        assert detalle == "denegado: sin permiso de gestión de usuarios"

    def test_rol_nuevo_admin_rechazado_siempre_incluso_pedido_por_el_jefe(
            self, bd_temporal):
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")

        resultado = cambiar_rol_sistema("jjcastillo", "admin", "lamaya")

        assert resultado is False
        assert _rol_de(bd_temporal, "jjcastillo") == "fisico"
        _, _, _, _, detalle = _ultima_fila_audit(bd_temporal)
        assert "no permitido" in detalle


class TestDegradacion:

    def test_degradar_al_unico_jefe_es_rechazado(self, bd_temporal):
        """admin ya existe (createAdmin) -- se desactiva primero para que
        'lamaya' sea la única cuenta de gestión ACTIVA, aislando la
        guarda de _quedaria_sin_jefes."""
        con = sqlite3.connect(bd_temporal)
        con.execute("UPDATE users SET active=0 WHERE user='admin'")
        con.commit()
        con.close()
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")

        resultado = cambiar_rol_sistema("lamaya", "fisico", "lamaya")

        assert resultado is False
        assert _rol_de(bd_temporal, "lamaya") == "jefe"
        _, _, _, _, detalle = _ultima_fila_audit(bd_temporal)
        assert "quedaría sin nadie que administre usuarios" in detalle

    def test_degradar_a_uno_de_dos_jefes_es_permitido(self, bd_temporal):
        """El otro jefe activo sigue pudiendo administrar -- degradar
        (incluso a sí mismo) no deja el sistema sin nadie."""
        con = sqlite3.connect(bd_temporal)
        con.execute("UPDATE users SET active=0 WHERE user='admin'")
        con.commit()
        con.close()
        _sembrar_usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", "jefe")

        resultado = cambiar_rol_sistema("lamaya", "fisico", "jjcastillo")

        assert resultado is True
        assert _rol_de(bd_temporal, "lamaya") == "fisico"


class TestGuardaCompartidaPorAST:
    """La guarda de 'no quedarse sin jefes' tiene que ser LA MISMA función
    en dar_de_baja (U3) y cambiar_rol_sistema (U4-bis) -- inspección del
    AST, no del texto, para que no baste con que las dos LLAMEN a algo
    con ese nombre por casualidad."""

    def test_dar_de_baja_y_cambiar_rol_sistema_llaman_a_la_misma_funcion(self):
        ruta = Path(__file__).resolve().parent.parent / "services" / "gestion_usuarios.py"
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))

        funciones = {
            nodo.name: nodo for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.FunctionDef)
        }
        assert "dar_de_baja" in funciones
        assert "cambiar_rol_sistema" in funciones
        assert "_quedaria_sin_jefes" in funciones, (
            "la guarda debe existir como función propia, no inline")

        def _llama_a(nodo_funcion, nombre_objetivo):
            for sub in ast.walk(nodo_funcion):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                    if sub.func.id == nombre_objetivo:
                        return True
            return False

        assert _llama_a(funciones["dar_de_baja"], "_quedaria_sin_jefes"), (
            "dar_de_baja debe llamar a _quedaria_sin_jefes")
        assert _llama_a(funciones["cambiar_rol_sistema"], "_quedaria_sin_jefes"), (
            "cambiar_rol_sistema debe llamar a _quedaria_sin_jefes -- "
            "una copia propia de esta guarda es el patrón que produjo DP-79")
