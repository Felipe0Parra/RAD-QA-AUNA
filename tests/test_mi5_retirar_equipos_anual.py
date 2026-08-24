"""MI5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI5, DA-44): la única operación
IRREVERSIBLE de todo el plan -- `DROP TABLE equipos_anual`, condicionado a
que esté vacía en la BD que se está migrando.

`equipos_anual` no tiene NINGÚN `CREATE TABLE` en `conection.py` (a
diferencia de las 11 tablas vacías de DA-42, que sí se crean al
arrancar) -- solo existe en BD ya desplegadas antes de que el proyecto
dejara de usarla (G-3: los formularios anuales guardan sus equipos en
`equipos_medicion`). Por eso estos tests la crean a mano con `sqlite3`
puro, reproduciendo el estado de una BD real -- `Conexion()` nunca la
generaría.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts.retirar_equipos_anual import retirar_equipos_anual


@pytest.fixture
def bd_con_equipos_anual_vacia(tmp_path):
    ruta = str(tmp_path / "test.db")
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE equipos_anual (id INTEGER PRIMARY KEY, modelo TEXT)")
    con.commit()
    con.close()
    return ruta


@pytest.fixture
def bd_con_equipos_anual_con_filas(tmp_path):
    ruta = str(tmp_path / "test.db")
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE equipos_anual (id INTEGER PRIMARY KEY, modelo TEXT)")
    con.execute("INSERT INTO equipos_anual (modelo) VALUES ('modelo real inesperado')")
    con.commit()
    con.close()
    return ruta


@pytest.fixture
def bd_sin_equipos_anual(tmp_path):
    ruta = str(tmp_path / "test.db")
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE controles (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()
    return ruta


def _existe(ruta, tabla):
    con = sqlite3.connect(ruta)
    existe = bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (tabla,)).fetchone())
    con.close()
    return existe


class TestRetirarEquiposAnual:

    def test_tabla_vacia_se_retira(self, bd_con_equipos_anual_vacia):
        resultado = retirar_equipos_anual(bd_con_equipos_anual_vacia)
        assert resultado == {"estado": "retirada", "filas": 0}
        assert not _existe(bd_con_equipos_anual_vacia, "equipos_anual")

    def test_tabla_con_filas_no_se_toca(self, bd_con_equipos_anual_con_filas):
        resultado = retirar_equipos_anual(bd_con_equipos_anual_con_filas)
        assert resultado["filas"] == 1
        assert resultado["estado"].startswith("NO RETIRADA")
        assert _existe(bd_con_equipos_anual_con_filas, "equipos_anual"), (
            "una tabla con filas NUNCA debe borrarse por este camino -- "
            "DA-44 solo autoriza el DROP sobre una tabla vacía")

        con = sqlite3.connect(bd_con_equipos_anual_con_filas)
        fila = con.execute("SELECT modelo FROM equipos_anual").fetchone()
        con.close()
        assert fila == ("modelo real inesperado",), (
            "el contenido de la fila debe sobrevivir intacto")

    def test_tabla_inexistente_no_revienta(self, bd_sin_equipos_anual):
        resultado = retirar_equipos_anual(bd_sin_equipos_anual)
        assert resultado == {"estado": "no existe", "filas": 0}

    def test_segunda_corrida_es_idempotente(self, bd_con_equipos_anual_vacia):
        """Tras retirarla, correr otra vez sobre la misma BD no debe
        lanzar -- la tabla ya no existe, cae en la rama "no existe"."""
        retirar_equipos_anual(bd_con_equipos_anual_vacia)
        resultado2 = retirar_equipos_anual(bd_con_equipos_anual_vacia)
        assert resultado2 == {"estado": "no existe", "filas": 0}

    def test_no_toca_ninguna_otra_tabla(self, bd_con_equipos_anual_vacia):
        con = sqlite3.connect(bd_con_equipos_anual_vacia)
        con.execute("CREATE TABLE otra_tabla_cualquiera (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        retirar_equipos_anual(bd_con_equipos_anual_vacia)

        assert _existe(bd_con_equipos_anual_vacia, "otra_tabla_cualquiera")


class TestWiradoEnLaMigracion:
    """La orquestación real (migrar_bd_a_estandar.py::_aplicar_migracion_en)
    se ejercita de extremo a extremo sobre copias de BD reales en
    test_u2_indice_unico_controles.py -- aquí solo se fija el contrato del
    resultado devuelto, con una BD temporal mínima."""

    def test_migrar_incluye_equipos_anual_en_el_resultado(self, tmp_path):
        from data.ManejoDatos.conection import Conexion
        from scripts.migrar_bd_a_estandar import migrar

        ruta = str(tmp_path / "vieja.db")
        con = sqlite3.connect(ruta)
        con.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "fullname TEXT UNIQUE)")
        con.execute("CREATE TABLE equipos_anual (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        Conexion._instance = None
        resultado = migrar(ruta, aplicar=False)
        Conexion._instance = None

        assert resultado["equipos_anual"] == {"estado": "retirada", "filas": 0}
