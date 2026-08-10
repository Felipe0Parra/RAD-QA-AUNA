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


@pytest.fixture(autouse=True, scope="session")
def _bd_sesion_por_defecto():
    ruta = os.path.join(tempfile.mkdtemp(prefix="radqa_tests_"), "sesion.db")
    original = conection_mod.ruta_base_datos
    conection_mod.ruta_base_datos = lambda: ruta
    yield
    conection_mod.ruta_base_datos = original


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
