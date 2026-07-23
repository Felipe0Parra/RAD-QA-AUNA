"""C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md / PLAN_AUDITORIA_DOS_EJES_21-07.md
§7 P4): "controles" es la raíz de la jerarquía mensual/anual/CT. Antes de
esta tarea, borrar un control era un DELETE físico -- el físico señaló
(handoff 23-07, línea 13) que no hay ninguna forma de reponer un registro
eliminado. La columna `activo` (migración idempotente, mismo patrón que
B3.1/K3/E4) es la base para que "eliminar" pase a ser anular en vez de
borrar (ver test_c2_soft_delete_controles.py para el cambio de
comportamiento).

Esta suite solo cubre el ESQUEMA: que la migración corra sobre una BD
"vieja" real (esquema sin `activo`, con filas ya guardadas) sin perder ni
un valor, y que sea idempotente entre reinicios de la app.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _asegurar_columna


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    yield ruta
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None
    for sufijo in ("", "-wal", "-shm"):
        if os.path.exists(ruta + sufijo):
            os.remove(ruta + sufijo)


def _crear_controles_esquema_viejo(ruta):
    """Esquema real de producción (sin `activo`), con una fila ya guardada --
    exactamente la forma de cualquier copia de producción desplegada antes
    de esta tarea."""
    con = sqlite3.connect(ruta)
    con.execute("""
        CREATE TABLE controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo TEXT, control TEXT, fecha TEXT,
            user_id TEXT, user_id_f2 TEXT
        )
    """)
    con.execute(
        "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
        "VALUES ('Clinac ix', 'Mensual', '07/2026', 'Cristian Castellanos', 'Cristian Castellanos')")
    con.commit()
    con.close()


class TestMigracionColumnaActivo:

    def test_arranque_agrega_activo_sin_tocar_filas_existentes(self, bd_temporal):
        _crear_controles_esquema_viejo(bd_temporal)

        Conexion()  # arranque real de la app -- corre createTable()

        con = sqlite3.connect(bd_temporal)
        cols = [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()]
        assert "activo" in cols

        fila = con.execute(
            "SELECT equipo, control, fecha, user_id, user_id_f2, activo "
            "FROM controles WHERE id = 1").fetchone()
        con.close()
        assert fila == ("Clinac ix", "Mensual", "07/2026",
                         "Cristian Castellanos", "Cristian Castellanos", 1)

    def test_migracion_es_idempotente(self, bd_temporal):
        _crear_controles_esquema_viejo(bd_temporal)
        Conexion()

        con = sqlite3.connect(bd_temporal)
        cur = con.cursor()
        _asegurar_columna(cur, "controles", "activo", "INTEGER DEFAULT 1")  # 2da vez
        _asegurar_columna(cur, "controles", "activo", "INTEGER DEFAULT 1")  # 3ra vez
        con.commit()

        cols = [c[1] for c in cur.execute("PRAGMA table_info(controles)").fetchall()]
        assert cols.count("activo") == 1
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT COUNT(*) FROM controles").fetchone()[0] == 1
        con.close()

    def test_control_nuevo_nace_activo_por_defecto(self, bd_temporal):
        """Un control creado DESPUÉS de la migración (esquema ya al día)
        también nace activo=1 sin que nadie tenga que asignarlo a mano."""
        Conexion()
        con = Conexion().conectar()
        con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id) "
            "VALUES ('Clinac 600', 'Mensual', '23/07/2026', 'Administrador')")
        con.commit()
        activo = con.execute(
            "SELECT activo FROM controles WHERE equipo='Clinac 600'").fetchone()[0]
        con.close()
        assert activo == 1

    def test_reiniciar_la_app_varias_veces_no_pierde_datos(self, bd_temporal):
        _crear_controles_esquema_viejo(bd_temporal)

        for _ in range(3):
            Conexion()
            if Conexion._instance is not None:
                Conexion._instance.con.close()
            Conexion._instance = None

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
        con.close()
        assert n == 1
        assert integridad == "ok"
