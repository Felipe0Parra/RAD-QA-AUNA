"""E10 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §18): toda FK con borrado en
cascada pasa a `ON DELETE RESTRICT`.

Medido sobre la BD real: un solo DELETE en `controles` se llevaba 19 filas
hijas de 5 tablas. C2/E7 evitan que la APP lo dispare; con RESTRICT es la
BD misma quien rechaza borrar un padre con hijas, venga de donde venga.

Las dos mitades del mismo commit (omitir una invalida la otra):
1. Migración idempotente al arranque (`_asegurar_fk_on_delete_restrict`)
   que recrea las tablas de una BD existente.
2. El DDL de `conection.py` ya declara RESTRICT -- cualquier BD nueva
   (incluidas las de esta suite) nace igual que producción migrada.

Aviso del plan §18 (lo planteó el físico y es exacto): RESTRICT por sí solo
NO da soft-delete -- no impide borrar un padre sin hijas ni borrar hijas
directamente. Esa capa la dan E7 (anulación) y E8 (triggers).
"""
import re
import sqlite3
from pathlib import Path

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion

RUTA_CONECTION = Path(conection_mod.__file__)


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta, conexion
    conexion.con.close()
    Conexion._instance = None


def _acciones_on_delete(ruta):
    con = sqlite3.connect(ruta)
    try:
        acciones = {}
        for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"):
            for fk in con.execute(f"PRAGMA foreign_key_list('{t}')"):
                acciones.setdefault(fk[6], []).append(t)
        return acciones
    finally:
        con.close()


class TestEsquemaNuevoNaceEnRestrict:
    def test_ninguna_fk_declara_borrado_en_cascada(self, bd_temporal):
        """Verifica la mitad 2: una BD recién creada por `Conexion()` no
        tiene ni una FK con on_delete=CASCADE."""
        ruta, _ = bd_temporal
        acciones = _acciones_on_delete(ruta)
        assert "CASCADE" not in acciones, acciones.get("CASCADE")
        assert len(acciones.get("RESTRICT", [])) >= 50  # las ~59 del esquema


class TestRestrictFunciona:
    def test_borrar_padre_con_hijas_lo_rechaza_la_bd(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute("INSERT INTO controles (equipo, control, fecha) "
                    "VALUES ('Clinac iX', 'Mensual', '07/2026')")
        ref = cur.lastrowid
        cur.execute("INSERT INTO dosimetriaMen (ref, energia) VALUES (?, '6mv')", (ref,))
        conexion.con.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("DELETE FROM controles WHERE id = ?", (ref,))
        conexion.con.rollback()

    def test_anular_e_insertar_siguen_funcionando(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute("INSERT INTO controles (equipo, control, fecha) "
                    "VALUES ('Clinac iX', 'Mensual', '07/2026')")
        ref = cur.lastrowid
        cur.execute("INSERT INTO dosimetriaMen (ref, energia) VALUES (?, '6mv')", (ref,))
        cur.execute("UPDATE controles SET activo = 0 WHERE id = ?", (ref,))
        conexion.con.commit()

        con = sqlite3.connect(ruta)
        try:
            activo = con.execute(
                "SELECT activo FROM controles WHERE id = ?", (ref,)).fetchone()[0]
            hijas = con.execute(
                "SELECT COUNT(*) FROM dosimetriaMen WHERE ref = ?", (ref,)).fetchone()[0]
        finally:
            con.close()
        assert activo == 0
        assert hijas == 1


class TestTripwireDdl:
    def test_conection_no_contiene_la_declaracion_en_cascada(self):
        """Impide que una tabla nueva reintroduzca el patrón. La migración
        de E10 compone el texto en dos partes a propósito para no aparecer
        aquí (ver su docstring)."""
        texto = RUTA_CONECTION.read_text(encoding="utf-8")
        assert "ON DELETE " + "CASCADE" not in texto
        assert texto.count("ON DELETE RESTRICT") >= 58


class TestMigracionDeBdLegada:
    """Verifica la mitad 1 sobre una BD que nació con el esquema viejo."""

    def _bd_legada(self, tmp_path, monkeypatch):
        ruta = str(tmp_path / "legada.db")
        con = sqlite3.connect(ruta)
        # subconjunto real del esquema PRE-E10 (tal como estaba en producción)
        con.executescript("""
            CREATE TABLE controles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipo TEXT, control TEXT, fecha TEXT,
                user_id TEXT, user_id_f2 TEXT);
            CREATE TABLE dosimetriaMen (
                ref INTEGER, energia TEXT,
                FOREIGN KEY (ref) REFERENCES controles(id)
                    ON DELETE CASCADE ON UPDATE CASCADE);
        """)
        con.execute("INSERT INTO controles (equipo, control, fecha) "
                    "VALUES ('Clinac iX', 'Mensual', '01/2026')")
        con.execute("INSERT INTO dosimetriaMen (ref, energia) VALUES (1, '6mv')")
        con.commit()
        con.close()
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        return ruta

    def test_migra_a_restrict_conservando_los_datos(self, tmp_path, monkeypatch):
        ruta = self._bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()  # arranque real: corre la migración
        try:
            con = sqlite3.connect(ruta)
            try:
                fks = con.execute("PRAGMA foreign_key_list('dosimetriaMen')").fetchall()
                fila = con.execute(
                    "SELECT ref, energia FROM dosimetriaMen").fetchone()
                padre = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
            finally:
                con.close()
            acciones = {fk[6] for fk in fks}
            assert acciones == {"RESTRICT"}
            assert fila == (1, "6mv")  # ni una fila perdida
            assert padre == 1
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
        """Protección contra la reutilización de ids: si el contador iba más
        adelante que MAX(id) (filas altas borradas físicamente en el pasado),
        la recreación NO debe devolverlo atrás -- un id reutilizado haría que
        los huérfanos heredados que apuntan a él 'adoptaran' al registro
        nuevo."""
        ruta = self._bd_legada(tmp_path, monkeypatch)
        con = sqlite3.connect(ruta)
        con.execute("INSERT INTO controles (equipo) VALUES ('x')")  # id 2
        con.execute("INSERT INTO controles (equipo) VALUES ('x')")  # id 3
        con.execute("DELETE FROM controles WHERE id IN (2, 3)")     # seq queda en 3
        con.commit()
        con.close()

        conexion = Conexion()
        try:
            cur = conexion.con.cursor()
            cur.execute("INSERT INTO controles (equipo, control, fecha) "
                        "VALUES ('Halcyon', 'Mensual', '02/2026')")
            nuevo_id = cur.lastrowid
            conexion.con.rollback()
        finally:
            conexion.con.close()
            Conexion._instance = None
        assert nuevo_id == 4  # nunca 2 ni 3: esos ids ya existieron

    def test_normaliza_secuencias_duplicadas(self, tmp_path, monkeypatch):
        """La BD real traía filas DUPLICADAS en sqlite_sequence para 35
        tablas (users x4, TipoCalibracion x4, ... herencia de recreaciones
        antiguas y de la fusión de BD) -- SQLite podía leer el contador
        MENOR y reutilizar ids. La migración deja UNA fila por tabla con el
        máximo."""
        ruta = self._bd_legada(tmp_path, monkeypatch)
        con = sqlite3.connect(ruta)
        # sqlite_sequence no declara unicidad: se puede duplicar a mano,
        # igual que quedó duplicada en producción.
        con.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('controles', 7)")
        con.commit()
        assert len(con.execute(
            "SELECT * FROM sqlite_sequence WHERE name='controles'").fetchall()) == 2
        con.close()

        conexion = Conexion()
        try:
            con = sqlite3.connect(ruta)
            filas = con.execute(
                "SELECT seq FROM sqlite_sequence WHERE name='controles'").fetchall()
            con.close()
        finally:
            conexion.con.close()
            Conexion._instance = None
        assert filas == [(7,)]  # una sola fila, con el máximo
