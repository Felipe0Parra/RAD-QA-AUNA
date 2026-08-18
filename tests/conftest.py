"""HI-1 (PLAN_HI): red de seguridad de sesion para toda la suite.

TEMA A del PLAN_HI: antes de esta tarea, cualquier test que instanciara
Conexion()/DosisService sin parchear su propia ruta caia en
Codigo_radqa/BaseDatosQA.db -- un archivo de desarrollo real, distinto de la
BD de produccion, pero que no deberia crearse solo por correr la suite
(sintoma preexistente, documentado en CLAUDE.md, encontrado durante H2.4).

Este fixture autouse de sesion redirige conection.ruta_base_datos() a una BD
temporal por defecto ANTES de que corra el primer test, para que ningun test
pueda tocar/crear la ruta real de desarrollo por accidente -- ni siquiera uno
que se olvide de parchearla.

Los tests que ya parchean su propia ruta con monkeypatch de ALCANCE DE FUNCION
siguen ganando: ese monkeypatch se aplica DESPUES de este (fixture de funcion
corre despues del autouse de sesion) y se revierte al valor de este fixture al
terminar la funcion, nunca al original real -- por eso el orden es seguro.
"""
import os
import tempfile

import pytest

import data.ManejoDatos.conection as conection_mod
import _rt1_interceptor_sql as _rt1


@pytest.fixture(autouse=True, scope="session")
def _bd_sesion_por_defecto():
    ruta = os.path.join(tempfile.mkdtemp(prefix="radqa_tests_"), "sesion.db")
    original = conection_mod.ruta_base_datos
    conection_mod.ruta_base_datos = lambda: ruta
    yield
    conection_mod.ruta_base_datos = original


@pytest.fixture(autouse=True, scope="session")
def _rt1_interceptor_de_sql():
    """RT1 (PLAN_LECTURA_VIGENTE_18-08.md §6-RT1): frente DINÁMICO -- ve el
    SQL ya resuelto de TODA conexión sqlite3 que abra la suite (incluida la
    que abre el código de producción bajo prueba), complementando a ES1
    (ciego al SQL armado en variable que no puede resolver estáticamente).
    Falla al final de la sesión si algo quedó sin filtrar `activo` sobre
    una tabla del bloque de QC -- el mismo criterio de AN1, aplicado al
    texto REAL en vez de al reconstruido.

    Solo se vigila el SQL cuyo llamador INMEDIATO de `.execute()` vive en
    el árbol de producción: los helpers de verificación de la propia suite
    leen activas + históricas a propósito y no son defectos (ver el
    docstring de `_rt1_interceptor_sql`)."""
    _rt1.reiniciar()
    _rt1.activar()
    yield
    _rt1.desactivar()
    if _rt1.hallazgos_sesion:
        detalle = "\n".join(
            f"  {archivo}::{funcion}:{linea}\n"
            f"    {sql.strip()[:200]!r}\n"
            f"    -> {h}"
            for sql, (archivo, funcion, linea), hs in _rt1.hallazgos_sesion
            for h in hs)
        raise AssertionError(
            f"RT1: {len(_rt1.hallazgos_sesion)} sentencia(s) SQL ejecutada(s) "
            f"por código de PRODUCCIÓN sin filtrar 'activo' sobre una tabla "
            f"del bloque de QC (visto por el interceptor con el SQL ya "
            f"resuelto, no por el AST):\n{detalle}")


def pytest_terminal_summary(terminalreporter):
    """§9.3 del plan: la cobertura real de RT1 es un ENTREGABLE, no un
    detalle interno -- se publica al final de cada corrida completa."""
    if _rt1.estadisticas()["sentencias_vistas"]:
        terminalreporter.write_sep("-", "RT1 cobertura")
        terminalreporter.write_line(_rt1.informe_cobertura())


@pytest.fixture(autouse=True)
def _qtsql_sin_fugas():
    """PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §9: `opeenDatabase`
    fija `qt_sql_default_connection` (global al proceso) solo la primera vez
    que se crea -- cualquier test que la ejercite (directo o vía código de
    producción) la deja clavada a su BD temporal para el resto de la sesión
    de pytest. Se destruye al final de cada test para que la condición
    necesaria del fallo no sobreviva de un test al siguiente.
    """
    yield
    from PyQt5.QtSql import QSqlDatabase

    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
