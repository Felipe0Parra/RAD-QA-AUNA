"""P1.1 (PLAN_P1_POOL_CONEXIONES_27-07.md §3): reproduce el mecanismo EXACTO
del bug H-B ("Cannot operate on a closed database", ~15 veces en la
terminal del físico, 23-07) y prueba que la fachada sin estado de
`services/db_pool.py` lo elimina de raíz.

Mecanismo (verificado en código antes del fix): `DatabaseManager` era un
SINGLETON (`_instance` en `__new__`) con `_connections` a nivel de CLASE --
compartido entre TODAS las vistas. `obtener_conexion()` reusaba la primera
conexión sin transacción activa; si la vista 1 tenía una transacción
abierta, el pool le abría una conexión PROPIA a la vista 2 y la agregaba al
MISMO diccionario compartido. `limpiar_recursos()` (disparado por
`__del__`, heredado por TODAS las vistas mensuales/anuales) llamaba
`cerrar_conexiones()`, que iteraba y cerraba TODAS las conexiones del
diccionario compartido -- incluida la de una vista que seguía viva.

Este test simula exactamente esa secuencia (transacción abierta en la vista
1 para forzar que el pool viejo le diera una conexión propia a la vista 2,
luego `cerrar_conexiones()` desde la vista 1) y verifica que la conexión de
la vista 2 sigue usable.

Verificado en ROJO contra el código viejo con `git stash push --
services/db_pool.py ui/paginasControles/PruebasMensuales/seiscientos_mensual.py`
(restaura la clase con estado; el test revienta con
`sqlite3.ProgrammingError: Cannot operate on a closed database`) y en VERDE
tras `git stash pop`.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import DatabaseManager


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    if hasattr(DatabaseManager, "_instance"):
        DatabaseManager._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class TestHBEliminado:
    def test_cerrar_conexiones_de_una_vista_no_invalida_la_de_otra_viva(self, bd_temporal):
        dbm_vista1 = DatabaseManager()
        conn1 = dbm_vista1.obtener_conexion()

        # Deja la conexión de la vista 1 EN TRANSACCIÓN -- con el pool viejo
        # (reusaba la primera conexión sin transacción activa) esto obligaba
        # a abrir una conexión PROPIA para la vista 2, tal como ocurría en
        # producción con dos vistas mensuales abiertas a la vez.
        conn1.execute("BEGIN")
        conn1.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES ('t_hb', 'x', 'Test HB', 1, 99, 'fisico')"
        )

        dbm_vista2 = DatabaseManager()
        conn2 = dbm_vista2.obtener_conexion()

        conn1.commit()

        # __del__ de la vista 1 (limpiar_recursos -> cerrar_conexiones()).
        dbm_vista1.cerrar_conexiones()

        # La vista 2 sigue "viva": su conexión NO debe quedar inutilizable.
        cur2 = conn2.cursor()
        cur2.execute("SELECT 1")
        assert cur2.fetchone() == (1,)
