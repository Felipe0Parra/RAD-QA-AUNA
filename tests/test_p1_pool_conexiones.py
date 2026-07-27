"""P1.0 (PLAN_P1_POOL_CONEXIONES_27-07.md §3): red de seguridad ANTES de
tocar la implementación del pool de conexiones. Ancla el contrato
observable que debe sobrevivir el refactor (P1.1/P1.2: 5 copias idénticas
de `DatabaseManager` -> 1 fachada sin estado en `services/db_pool.py`):

  - `obtener_conexion()` devuelve una conexión USABLE.
  - Esa conexión trae los 3 PRAGMAs correctos (WAL/busy_timeout=30000/
    foreign_keys=ON, W2) -- esto es lo único que un error de refactor podría
    perder en silencio con impacto real (FK ON es la defensa de W2 contra
    huérfanos).
  - La conexión apunta al archivo de BD de la SESIÓN de tests
    (`conftest.py::_bd_sesion_por_defecto`), nunca a la BD real.

Este archivo se corre y queda VERDE contra el código ACTUAL (las 5 copias
con estado) antes de escribir una sola línea de `services/db_pool.py` --
es la referencia para verificar que P1.1/P1.2 no cambian el contrato.

El flujo integral de guardar/reabrir un control mensual ya está cubierto
por W1 (`test_w1_no_escribir_sobre_control_eliminado.py`) y H2.7
(`test_h27_bd_unica_mensual.py`) -- no se duplica aquí, solo se referencia.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import DatabaseManager


class TestContratoObtenerConexion:
    def test_devuelve_una_conexion_usable(self):
        dbm = DatabaseManager()
        conn = dbm.obtener_conexion()

        cur = conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone() == (1,)

    def test_trae_los_3_pragmas_correctos(self):
        dbm = DatabaseManager()
        conn = dbm.obtener_conexion()
        cur = conn.cursor()

        assert cur.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert cur.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert cur.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_apunta_a_la_bd_de_la_sesion_de_tests_no_a_la_real(self):
        dbm = DatabaseManager()
        conn = dbm.obtener_conexion()

        # `PRAGMA database_list` trae la ruta real del archivo abierto --
        # debe coincidir con la que conftest.py fijó para toda la sesión,
        # nunca con una ruta de BD real de producción o de desarrollo.
        ruta_conexion = conn.execute("PRAGMA database_list").fetchone()[2]
        ruta_sesion = conection_mod.ruta_base_datos()

        assert os.path.abspath(ruta_conexion) == os.path.abspath(ruta_sesion)
        assert "BaseDatosQA.db" not in ruta_conexion
