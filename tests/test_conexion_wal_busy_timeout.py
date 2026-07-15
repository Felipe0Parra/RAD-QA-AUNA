"""H2.5 (auditoría 2026-07-14) -- WAL + busy_timeout en las conexiones.

La app tiene un "doble patrón de conexión" (hallazgo D5, registrado en
CLAUDE.md): el singleton `Conexion().con` (persistente, nunca se cierra)
conviviendo con conexiones nuevas por llamada (`Conexion().conectar()`,
`DosisService._get_connection()`). Sin WAL/busy_timeout, dos escrituras
concurrentes pueden chocar con `sqlite3.OperationalError: database is
locked` de inmediato. Con `PRAGMA busy_timeout=30000`, el segundo escritor
espera en vez de fallar; con `PRAGMA journal_mode=WAL`, lectores y
escritores no se bloquean entre sí.

Se prueban las 3 conexiones tocadas (`Conexion.__init_connection`,
`Conexion.conectar()`, `DosisService._get_connection`) más un escenario de
concurrencia real con hilos.
"""
import os
import sqlite3
import tempfile
import threading
import time

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import services.dosis_service as dosis_service_mod
from services.dosis_service import DosisService


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    # HI-3: dosis_service.py ahora importa el MÓDULO conection (no la función
    # por valor) -- un solo parche sobre conection_mod.ruta_base_datos basta
    # para redirigir también DosisService (antes hacían falta 2 parches).
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    yield ruta
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None
    for sufijo in ("", "-wal", "-shm"):
        if os.path.exists(ruta + sufijo):
            os.remove(ruta + sufijo)


def _pragma(con, nombre):
    return con.execute(f"PRAGMA {nombre}").fetchone()[0]


class TestPragmasAplicados:
    def test_singleton_con_wal_y_busy_timeout(self, bd_temporal):
        con = Conexion().con
        assert _pragma(con, "journal_mode").lower() == "wal"
        assert _pragma(con, "busy_timeout") == 30000

    def test_conectar_nueva_conexion_wal_y_busy_timeout(self, bd_temporal):
        Conexion()  # asegura que el archivo/esquema ya existe
        con = Conexion().conectar()
        assert _pragma(con, "journal_mode").lower() == "wal"
        assert _pragma(con, "busy_timeout") == 30000
        con.close()

    def test_dosis_service_get_connection_wal_y_busy_timeout(self, bd_temporal):
        con = DosisService._get_connection()
        assert _pragma(con, "journal_mode").lower() == "wal"
        assert _pragma(con, "busy_timeout") == 30000
        con.close()


class TestMismaFuenteDeConfiguracion:
    """HI-3: los PRAGMAs se centralizaron en aplicar_pragmas_conexion() y
    dosis_service.py ahora importa el MÓDULO conection (no una función
    capturada por valor) -- los 3 caminos comparten literalmente la misma
    fuente, no 3 copias que puedan desincronizarse (TEMA A/B del PLAN_HI)."""

    def test_dosis_service_usa_el_mismo_modulo_conection(self):
        assert dosis_service_mod._conection is conection_mod

    def test_los_3_caminos_dan_los_mismos_pragmas(self, bd_temporal):
        Conexion()  # asegura que el archivo/esquema ya existe
        con_singleton = Conexion().con
        con_nueva = Conexion().conectar()
        con_dosis = DosisService._get_connection()
        try:
            for con in (con_singleton, con_nueva, con_dosis):
                assert _pragma(con, "journal_mode").lower() == "wal"
                assert _pragma(con, "busy_timeout") == 30000
        finally:
            con_nueva.close()
            con_dosis.close()


class TestConcurrenciaSinDatabaseIsLocked:
    """El escenario real que motiva H2.5: dos conexiones escribiendo casi
    al mismo tiempo NO deben chocar con 'database is locked'."""

    def test_segunda_escritura_espera_en_vez_de_fallar(self, bd_temporal):
        Conexion()  # crea el esquema (incluye 'users', tabla simple a usar)

        errores = []

        def escritor_que_retiene_el_lock():
            con = Conexion().conectar()
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO users (user, password, fullname, active, idreal, role) "
                "VALUES (?,?,?,?,?,?)", ("hilo1", "x", "Hilo Uno", 1, 1, "fisico"))
            time.sleep(0.4)  # retiene el lock de escritura un rato
            con.commit()
            con.close()

        hilo = threading.Thread(target=escritor_que_retiene_el_lock)
        hilo.start()
        time.sleep(0.05)  # asegurar que el hilo ya tomó el lock

        con2 = Conexion().conectar()
        try:
            con2.execute(
                "INSERT INTO users (user, password, fullname, active, idreal, role) "
                "VALUES (?,?,?,?,?,?)", ("hilo2", "x", "Hilo Dos", 1, 1, "fisico"))
            con2.commit()
        except sqlite3.OperationalError as e:
            errores.append(e)
        finally:
            con2.close()
            hilo.join()

        assert errores == [], f"'database is locked' pese a WAL+busy_timeout: {errores}"

        con_verif = Conexion().conectar()
        n = con_verif.execute(
            "SELECT COUNT(*) FROM users WHERE user IN ('hilo1','hilo2')").fetchone()[0]
        con_verif.close()
        assert n == 2
