"""EB2d (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2d, DA-57, 24-08): migración
idempotente que retira el `UNIQUE(ref, spoke_index)` DE TABLA de
`angulo_starshot` -- no era `partial` (a diferencia del índice que
`crear_indices()`/CL1 crea sobre la misma clave, con `WHERE activo IS NULL
OR activo=1`), así que bloqueaba el modelo de anular+insertar que
`starshot_angles_insertion` (EB2d) pasó a usar: una fila anulada y una
vigente con el mismo (ref, spoke_index) violaban esta constraint igual,
aunque `activo` fuera distinto.

Mismo procedimiento de `_asegurar_fk_on_delete_restrict` (E10): recrear y
copiar, preservando filas, índices propios y el contador de
`sqlite_sequence`. Medido: 0 filas en las 3 BD de referencia -- pero el
test de conservación de datos usa una BD legada con filas reales para
probarlo de verdad, no solo confiar en la medición.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion


class TestEsquemaNuevoNaceSinLaConstraint:

    def test_bd_nueva_no_tiene_unique_de_tabla(self, monkeypatch, tmp_path):
        ruta = str(tmp_path / "test.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        conexion = Conexion()
        try:
            con = sqlite3.connect(ruta)
            sql = con.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                "AND name='angulo_starshot'").fetchone()[0]
            con.close()
            assert "UNIQUE(ref, spoke_index)" not in sql
        finally:
            conexion.con.close()
            Conexion._instance = None

    def test_bd_nueva_permite_anular_e_insertar_mismo_spoke(self, monkeypatch, tmp_path):
        """La razón de ser de la migración: sin ella, esto reventaría con
        IntegrityError."""
        ruta = str(tmp_path / "test.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        conexion = Conexion()
        try:
            con = sqlite3.connect(ruta)
            con.execute(
                "INSERT INTO controles (equipo, control, fecha) "
                "VALUES ('Halcyon', 'Mensual', '06/2026')")
            con.commit()
            ref = con.execute("SELECT id FROM controles").fetchone()[0]
            con.execute(
                "INSERT INTO angulo_starshot "
                "(ref, spoke_index, angulo_nominal_deg, angulo_real_deg, desviacion_deg) "
                "VALUES (?, 0, 0.0, 0.1, 0.1)", (ref,))
            con.execute(
                "UPDATE angulo_starshot SET activo=0 WHERE ref=? AND spoke_index=0", (ref,))
            con.execute(
                "INSERT INTO angulo_starshot "
                "(ref, spoke_index, angulo_nominal_deg, angulo_real_deg, desviacion_deg) "
                "VALUES (?, 0, 0.0, 0.2, 0.2)", (ref,))
            con.commit()
            filas = con.execute(
                "SELECT angulo_real_deg, activo FROM angulo_starshot "
                "WHERE ref=? ORDER BY id", (ref,)).fetchall()
            con.close()
            assert filas == [(0.1, 0), (0.2, 1)]
        finally:
            conexion.con.close()
            Conexion._instance = None


class TestMigracionDeBdLegada:
    """Verifica la migración sobre una BD que nació con el esquema viejo
    (la constraint de tabla, sin partial index) -- mismo patrón que
    tests/test_e10_restrict.py::TestMigracionDeBdLegada."""

    def _bd_legada(self, tmp_path, monkeypatch):
        ruta = str(tmp_path / "legada.db")
        con = sqlite3.connect(ruta)
        con.executescript("""
            CREATE TABLE controles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipo TEXT, control TEXT, fecha TEXT,
                user_id TEXT, user_id_f2 TEXT);
            CREATE TABLE angulo_starshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER NOT NULL,
                spoke_index INTEGER NOT NULL,
                angulo_nominal_deg REAL NOT NULL,
                angulo_real_deg REAL NOT NULL,
                desviacion_deg REAL NOT NULL,
                FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                UNIQUE(ref, spoke_index));
        """)
        con.execute("INSERT INTO controles (equipo, control, fecha) "
                    "VALUES ('Halcyon', 'Mensual', '05/2026')")
        con.execute(
            "INSERT INTO angulo_starshot "
            "(ref, spoke_index, angulo_nominal_deg, angulo_real_deg, desviacion_deg) "
            "VALUES (1, 0, 0.0, 0.1, 0.1)")
        con.commit()
        con.close()
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        return ruta

    def test_migra_conservando_los_datos(self, tmp_path, monkeypatch):
        ruta = self._bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()  # arranque real: corre la migración
        try:
            con = sqlite3.connect(ruta)
            try:
                sql = con.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' "
                    "AND name='angulo_starshot'").fetchone()[0]
                fila = con.execute(
                    "SELECT ref, spoke_index, angulo_real_deg FROM angulo_starshot"
                ).fetchone()
            finally:
                con.close()
            assert "UNIQUE(ref, spoke_index)" not in sql
            assert fila == (1, 0, 0.1), "ni una fila perdida en la recreación"
        finally:
            conexion.con.close()
            Conexion._instance = None

    def test_es_idempotente(self, tmp_path, monkeypatch):
        ruta = self._bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()
        conexion.con.close()
        Conexion._instance = None

        con = sqlite3.connect(ruta)
        esquema_1 = sorted((r[0], r[1] or "") for r in con.execute(
            "SELECT name, sql FROM sqlite_master"))
        con.close()

        conexion = Conexion()  # segunda corrida
        try:
            con = sqlite3.connect(ruta)
            esquema_2 = sorted((r[0], r[1] or "") for r in con.execute(
                "SELECT name, sql FROM sqlite_master"))
            con.close()
            assert esquema_1 == esquema_2
        finally:
            conexion.con.close()
            Conexion._instance = None

    def test_preserva_el_contador_autoincrement(self, tmp_path, monkeypatch):
        ruta = self._bd_legada(tmp_path, monkeypatch)
        con = sqlite3.connect(ruta)
        con.execute(
            "INSERT INTO angulo_starshot "
            "(ref, spoke_index, angulo_nominal_deg, angulo_real_deg, desviacion_deg) "
            "VALUES (1, 1, 0.0, 0.2, 0.2)")  # id 2
        con.execute(
            "INSERT INTO angulo_starshot "
            "(ref, spoke_index, angulo_nominal_deg, angulo_real_deg, desviacion_deg) "
            "VALUES (1, 2, 0.0, 0.3, 0.3)")  # id 3
        con.execute("DELETE FROM angulo_starshot WHERE id IN (2, 3)")  # seq queda en 3
        con.commit()
        con.close()

        conexion = Conexion()
        try:
            con = sqlite3.connect(ruta)
            con.execute(
                "INSERT INTO angulo_starshot "
                "(ref, spoke_index, angulo_nominal_deg, angulo_real_deg, desviacion_deg) "
                "VALUES (1, 5, 0.0, 0.5, 0.5)")
            con.commit()
            nuevo_id = con.execute(
                "SELECT id FROM angulo_starshot WHERE spoke_index=5").fetchone()[0]
            con.close()
            assert nuevo_id == 4, (
                "el contador no debe retroceder -- un id reutilizado "
                "'adoptaría' cualquier huérfano heredado que apuntara a él")
        finally:
            conexion.con.close()
            Conexion._instance = None

    def test_permite_anular_e_insertar_mismo_spoke_tras_migrar(self, tmp_path, monkeypatch):
        ruta = self._bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()
        try:
            con = sqlite3.connect(ruta)
            con.execute(
                "UPDATE angulo_starshot SET activo=0 WHERE ref=1 AND spoke_index=0")
            con.execute(
                "INSERT INTO angulo_starshot "
                "(ref, spoke_index, angulo_nominal_deg, angulo_real_deg, desviacion_deg) "
                "VALUES (1, 0, 0.0, 0.9, 0.9)")
            con.commit()
            filas = con.execute(
                "SELECT angulo_real_deg, activo FROM angulo_starshot "
                "WHERE ref=1 AND spoke_index=0 ORDER BY id").fetchall()
            con.close()
            assert filas == [(0.1, 0), (0.9, 1)]
        finally:
            conexion.con.close()
            Conexion._instance = None
