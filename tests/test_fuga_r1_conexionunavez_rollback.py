"""R1 (PLAN_FUGA_CONEXIONES_01-09.md §3-P1, §8.8): endurece
`_ConexionUnaVez.__exit__` para que el invariante de P1 -- "al salir del
`with` por cualquier camino, la conexión queda cerrada y SIN transacción
abierta" -- sea explícito en el código, no un efecto colateral implícito.

[medido antes de tocar nada, ver conftest de este archivo]: `sqlite3.
Connection.close()` YA revierte una transacción abierta por sí sola (así
lo hace la biblioteca SQLite al cerrar el handle) -- un escritor nuevo con
`timeout=2` entra en <0.01 s tras un `close()` sin `rollback()` previo, y
la fila sin commitear NO sobrevive. Es decir: el invariante YA se cumplía
en la práctica. Lo que R1 arregla es que dejara de depender de ese detalle
implícito: ahora `__exit__` llama `rollback()` explícito si
`in_transaction`, ANTES de `close()`, y el test de este archivo fija esa
secuencia con un espía -- no solo el resultado final, que ya pasaba antes."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
import time

import pytest

from data.ManejoDatos.conection import _ConexionUnaVez


class _ConexionEspia:
    """Envuelve una conexión sqlite3 real y registra el ORDEN de llamadas a
    rollback()/commit()/close(), para fijar la secuencia exacta que P1 exige
    -- no solo que el resultado final sea correcto."""

    def __init__(self, con):
        self._con = con
        self.llamadas = []

    def __getattr__(self, nombre):
        return getattr(self._con, nombre)

    @property
    def in_transaction(self):
        return self._con.in_transaction

    def rollback(self):
        self.llamadas.append("rollback")
        return self._con.rollback()

    def commit(self):
        self.llamadas.append("commit")
        return self._con.commit()

    def close(self):
        self.llamadas.append("close")
        return self._con.close()


@pytest.fixture
def bd_temporal(tmp_path):
    ruta = str(tmp_path / "test_r1.db")
    con = sqlite3.connect(ruta, isolation_level='')
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t(x)")
    con.commit()
    con.close()
    return ruta


class TestR1ConexionUnaVezRollback:
    def test_transaccion_abierta_se_revierte_ANTES_de_cerrar_nunca_commitea(self, bd_temporal):
        """P2: inyecta el fallo real -- un INSERT sin commit dentro del
        `with`, como quedaría cualquiera de los sitios A1-A8 si la
        excepción sube antes del commit."""
        con_real = sqlite3.connect(bd_temporal, isolation_level='')
        espia = _ConexionEspia(con_real)

        with _ConexionUnaVez(espia) as con:
            con.execute("INSERT INTO t VALUES (1)")
            assert espia.in_transaction is True  # precondición: sí hay algo que revertir

        assert espia.llamadas == ["rollback", "close"], (
            "el orden debe ser rollback() y LUEGO close(); commit() no debe "
            f"aparecer nunca -- se registró: {espia.llamadas}")

        with pytest.raises(sqlite3.ProgrammingError):
            con_real.execute("SELECT 1")  # cerrada de verdad

    def test_sin_transaccion_abierta_no_llama_rollback(self, bd_temporal):
        """Si solo se leyó (o ya se commiteó), `rollback()` no debe
        llamarse -- sería una operación de más, no un error, pero un
        `__exit__` que lo hiciera siempre escondería el caso real."""
        con_real = sqlite3.connect(bd_temporal, isolation_level='')
        espia = _ConexionEspia(con_real)

        with _ConexionUnaVez(espia) as con:
            con.execute("SELECT COUNT(*) FROM t").fetchone()

        assert espia.llamadas == ["close"]

    def test_escritor_nuevo_no_se_bloquea_tras_abandonar_con_transaccion_abierta(self, bd_temporal):
        """El invariante en términos del síntoma real del físico: tras un
        `with` que deja una transacción sin commitear, un escritor NUEVO con
        timeout corto debe entrar de inmediato -- no colgarse ni terminar en
        "database is locked". Y la fila sin commitear no debe sobrevivir
        (prueba de que fue rollback, no un commit accidental)."""
        con_real = sqlite3.connect(bd_temporal, isolation_level='')
        with _ConexionUnaVez(con_real) as con:
            con.execute("INSERT INTO t VALUES (99)")
            # sale del `with` SIN commit -- el camino que hoy dejan abierto
            # los sitios A1-A8 cuando la excepción sube antes del commit()

        escritor_nuevo = sqlite3.connect(bd_temporal, isolation_level='', timeout=2)
        t0 = time.time()
        escritor_nuevo.execute("INSERT INTO t VALUES (2)")
        escritor_nuevo.commit()
        transcurrido = time.time() - t0
        assert transcurrido < 0.5, (
            f"un escritor nuevo no debe esperar el busy_timeout: tardó {transcurrido:.3f}s")

        filas = escritor_nuevo.execute("SELECT x FROM t ORDER BY x").fetchall()
        escritor_nuevo.close()
        assert filas == [(2,)], (
            f"la fila 99 (sin commit) no debe sobrevivir -- se revirtió, no se perdió "
            f"silenciosamente ni se comprometió: filas reales {filas}")
