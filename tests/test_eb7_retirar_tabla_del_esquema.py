"""MI5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI5, DA-44) + EB7 (§6-EB7,
DA-50): las dos únicas operaciones IRREVERSIBLES de todo el plan --
`DROP TABLE`, condicionado a que la tabla esté vacía en la BD que se está
migrando.

`equipos_anual` y `posicionamiento_reposicionamiento` no tienen NINGÚN
`CREATE TABLE` en `conection.py` -- solo existen en BD ya desplegadas
antes de que el proyecto dejara de usarlas (G-3: el anual guarda sus
equipos en `equipos_medicion`; DA-50: el posicionamiento ya lo recibe
`CondicionesMedicion.desplazamiento_ini`). Por eso estos tests las crean a
mano con `sqlite3` puro, reproduciendo el estado de una BD real --
`Conexion()` nunca las generaría.

Reemplaza a `test_mi5_retirar_equipos_anual.py` (retirado junto con
`scripts/retirar_equipos_anual.py`, generalizado en
`scripts/retirar_tabla_del_esquema.py`, EB7) -- mismo comportamiento,
ahora parametrizado sobre las dos tablas de `TABLAS_RETIRABLES` para no
duplicar el mismo test dos veces.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts.retirar_tabla_del_esquema import (
    TABLAS_RETIRABLES, retirar_tabla_del_esquema,
)

TABLAS = sorted(TABLAS_RETIRABLES)


@pytest.fixture(params=TABLAS)
def tabla(request):
    return request.param


@pytest.fixture
def bd_con_tabla_vacia(tmp_path, tabla):
    ruta = str(tmp_path / "test.db")
    con = sqlite3.connect(ruta)
    con.execute(f'CREATE TABLE "{tabla}" (id INTEGER PRIMARY KEY, modelo TEXT)')
    con.commit()
    con.close()
    return ruta


@pytest.fixture
def bd_con_tabla_con_filas(tmp_path, tabla):
    ruta = str(tmp_path / "test.db")
    con = sqlite3.connect(ruta)
    con.execute(f'CREATE TABLE "{tabla}" (id INTEGER PRIMARY KEY, modelo TEXT)')
    con.execute(f'INSERT INTO "{tabla}" (modelo) VALUES (?)', ("dato real inesperado",))
    con.commit()
    con.close()
    return ruta


@pytest.fixture
def bd_sin_la_tabla(tmp_path):
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


class TestRetirarTablaDelEsquema:
    """Parametrizado sobre las dos tablas de TABLAS_RETIRABLES --
    equipos_anual (MI5) y posicionamiento_reposicionamiento (EB7)
    comparten exactamente el mismo contrato."""

    def test_tabla_vacia_se_retira(self, bd_con_tabla_vacia, tabla):
        resultado = retirar_tabla_del_esquema(bd_con_tabla_vacia, tabla)
        assert resultado == {"estado": "retirada", "filas": 0}
        assert not _existe(bd_con_tabla_vacia, tabla)

    def test_tabla_con_filas_no_se_toca(self, bd_con_tabla_con_filas, tabla):
        resultado = retirar_tabla_del_esquema(bd_con_tabla_con_filas, tabla)
        assert resultado["filas"] == 1
        assert resultado["estado"].startswith("NO RETIRADA")
        assert _existe(bd_con_tabla_con_filas, tabla), (
            "una tabla con filas NUNCA debe borrarse por este camino -- "
            "solo se autoriza el DROP sobre una tabla vacía")

        con = sqlite3.connect(bd_con_tabla_con_filas)
        fila = con.execute(f'SELECT modelo FROM "{tabla}"').fetchone()
        con.close()
        assert fila == ("dato real inesperado",), (
            "el contenido de la fila debe sobrevivir intacto")

    def test_tabla_inexistente_no_revienta(self, bd_sin_la_tabla, tabla):
        resultado = retirar_tabla_del_esquema(bd_sin_la_tabla, tabla)
        assert resultado == {"estado": "no existe", "filas": 0}

    def test_segunda_corrida_es_idempotente(self, bd_con_tabla_vacia, tabla):
        """Tras retirarla, correr otra vez sobre la misma BD no debe
        lanzar -- la tabla ya no existe, cae en la rama "no existe"."""
        retirar_tabla_del_esquema(bd_con_tabla_vacia, tabla)
        resultado2 = retirar_tabla_del_esquema(bd_con_tabla_vacia, tabla)
        assert resultado2 == {"estado": "no existe", "filas": 0}

    def test_no_toca_ninguna_otra_tabla(self, bd_con_tabla_vacia, tabla):
        con = sqlite3.connect(bd_con_tabla_vacia)
        con.execute("CREATE TABLE otra_tabla_cualquiera (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        retirar_tabla_del_esquema(bd_con_tabla_vacia, tabla)

        assert _existe(bd_con_tabla_vacia, "otra_tabla_cualquiera")


class TestListaBlancaCerrada:
    """La propiedad que el docstring del módulo hereda de
    retirar_equipos_anual.py: NO es un mecanismo genérico apuntable a
    cualquier tabla."""

    def test_rechaza_tabla_fuera_de_la_lista_blanca(self, tmp_path):
        ruta = str(tmp_path / "test.db")
        con = sqlite3.connect(ruta)
        con.execute("CREATE TABLE controles (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        with pytest.raises(ValueError, match="lista blanca"):
            retirar_tabla_del_esquema(ruta, "controles")

        con = sqlite3.connect(ruta)
        existe = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='controles'"
        ).fetchone()
        con.close()
        assert existe is not None, "el rechazo debe ocurrir ANTES de tocar la BD"


class TestWiradoEnLaMigracion:
    """La orquestación real (migrar_bd_a_estandar.py::_aplicar_migracion_en)
    se ejercita de extremo a extremo sobre copias de BD reales en
    test_u2_indice_unico_controles.py -- aquí solo se fija el contrato del
    resultado devuelto, con una BD temporal mínima."""

    def test_migrar_incluye_las_dos_tablas_en_el_resultado(self, tmp_path):
        from data.ManejoDatos.conection import Conexion
        from scripts.migrar_bd_a_estandar import migrar

        ruta = str(tmp_path / "vieja.db")
        con = sqlite3.connect(ruta)
        con.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "fullname TEXT UNIQUE)")
        con.execute("CREATE TABLE equipos_anual (id INTEGER PRIMARY KEY)")
        con.execute(
            "CREATE TABLE posicionamiento_reposicionamiento (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        Conexion._instance = None
        resultado = migrar(ruta, aplicar=False)
        Conexion._instance = None

        assert resultado["equipos_anual"] == {"estado": "retirada", "filas": 0}
        assert resultado["posicionamiento_reposicionamiento"] == {
            "estado": "retirada", "filas": 0}
