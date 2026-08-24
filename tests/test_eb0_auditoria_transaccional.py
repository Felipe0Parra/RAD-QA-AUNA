"""EB0 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB0, DA-52): precede a `EB1`.

Hallazgo que motiva esta tarea (§4.10 del plan, medido empíricamente en el
scratchpad de la sesión del 24-08): `audit_minimo.registrar()` abría SIEMPRE
su PROPIA conexión sqlite3. Con una transacción de escritura abierta en
OTRA conexión (el caso real de `reemplazar_bloque`, EB1), esa segunda
conexión espera el `busy_timeout` completo (30 s en producción) y falla con
"database is locked" -- la fila de auditoría se pierde en silencio, porque
`registrar()` nunca relanza (best-effort por diseño).

`registrar(..., con=...)` cierra el defecto: si se pasa una conexión ya
abierta, la fila se escribe en ESA MISMA transacción, envuelta en un
SAVEPOINT (un fallo de auditoría deshace solo la fila, nunca el guardado).
Este archivo prueba las dos rutas y demuestra, con un timeout reducido para
que el test no tarde 30 s, que la ruta vieja (con=None) sigue existiendo
tal cual para los llamadores QtSql que la necesitan (autocommit).
"""
import os
import sqlite3
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from services.audit_minimo import registrar


def _con_con_pragmas(ruta, busy_timeout_ms=500):
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    return con


class TestConTransaccionDelLlamador:

    def test_fila_queda_en_la_misma_transaccion(self, tmp_path):
        ruta = str(tmp_path / "test.db")
        con = _con_con_pragmas(ruta)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, activo INTEGER)")
        con.commit()

        con.execute("BEGIN")
        con.execute("INSERT INTO t (id, activo) VALUES (1, 1)")
        registrar("fisico1", "reemplazo", "t", ref="1", con=con)
        # Sin commit todavía -- la fila de auditoría debe verse DESDE la
        # misma conexión (misma transacción), pero no desde otra.
        assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1

        con2 = sqlite3.connect(ruta)
        con2.execute("PRAGMA busy_timeout=500")
        # No hay tabla audit_log todavía visible fuera de la transacción, o
        # sí existe pero sin filas -- cualquiera de las dos es aceptable
        # aquí; lo que importa es que NO se vea comprometida (commit
        # implícito) antes de que el llamador decida.
        try:
            filas_fuera = con2.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        except sqlite3.OperationalError:
            filas_fuera = 0
        assert filas_fuera == 0, (
            "la fila de auditoría no debe ser visible fuera de la "
            "transacción del llamador antes de que éste haga commit")
        con2.close()

        con.commit()
        assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
        con.close()

    def test_no_abre_una_segunda_conexion(self, tmp_path, monkeypatch):
        """Si registrar(con=...) abriera una conexión propia además,
        colisionaría con el lock de escritor de `con` -- exactamente el
        defecto que EB0 cierra. Se verifica que sqlite3.connect NO se
        llama por dentro de esta ruta."""
        ruta = str(tmp_path / "test.db")
        con = _con_con_pragmas(ruta)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        con.commit()

        llamadas = []
        original_connect = sqlite3.connect

        def _connect_espia(*args, **kwargs):
            llamadas.append((args, kwargs))
            return original_connect(*args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", _connect_espia)

        con.execute("BEGIN")
        con.execute("INSERT INTO t (id) VALUES (1)")
        registrar("fisico1", "reemplazo", "t", ref="1", con=con)
        con.commit()
        con.close()

        assert llamadas == [], (
            "registrar(con=...) no debe abrir ninguna conexión sqlite3 "
            "nueva -- debe escribir en la conexión que se le pasó")

    def test_fallo_de_auditoria_no_arrastra_el_guardado(self, tmp_path, monkeypatch):
        """Best-effort (docstring del módulo): un fallo al auditar nunca
        debe impedir ni revertir el guardado principal. Se simula un DDL
        de audit_log que falla y se verifica que la fila de `t` sobrevive."""
        ruta = str(tmp_path / "test.db")
        con = _con_con_pragmas(ruta)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        con.commit()

        import services.audit_minimo as audit_minimo
        monkeypatch.setattr(
            audit_minimo, "_DDL_AUDIT_LOG", "ESTO NO ES SQL VALIDO")

        con.execute("BEGIN")
        con.execute("INSERT INTO t (id) VALUES (1)")
        registrar("fisico1", "reemplazo", "t", ref="1", con=con)  # no debe lanzar
        con.commit()

        assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
        con.close()


class TestSinTransaccionDelLlamador:
    """Comportamiento histórico (con=None): conexión propia, autocommit.
    Sigue siendo la ruta correcta para `anular_fila` (QtSql, autocommit)."""

    def test_conexion_propia_sigue_funcionando(self, tmp_path):
        ruta = str(tmp_path / "test.db")
        registrar("fisico1", "anular", "controles", ref="5", ruta_db=ruta)
        con = sqlite3.connect(ruta)
        fila = con.execute(
            "SELECT usuario, accion, tabla, ref FROM audit_log").fetchone()
        con.close()
        assert fila == ("fisico1", "anular", "controles", "5")


class TestEB0T_RojoAntesQueVerde:
    """El criterio de terminación EB0-T (§7 del plan): con una transacción
    de escritura abierta, `registrar(con=...)` debe completar en menos de
    1 s. Se demuestra primero que la ruta VIEJA (con=None, dos conexiones
    independientes) es la que colgaba -- con un busy_timeout reducido para
    no hacer esperar 30 s reales al test -- y luego que la ruta NUEVA
    (con=con) no sufre el mismo problema."""

    def test_dos_conexiones_independientes_colisionan_de_verdad(self, tmp_path):
        """Reproduce el hallazgo de DA-52 (no ejercita registrar() -- es la
        prueba de que el escenario que EB0 evita es real en esta versión
        de SQLite/WAL, con un busy_timeout corto para que el test sea
        rápido)."""
        ruta = str(tmp_path / "test.db")
        c1 = _con_con_pragmas(ruta, busy_timeout_ms=300)
        c1.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        c1.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, x TEXT)")
        c1.commit()

        c1.execute("BEGIN")
        c1.execute("INSERT INTO t (id) VALUES (1)")

        c2 = _con_con_pragmas(ruta, busy_timeout_ms=300)
        t0 = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            c2.execute("INSERT INTO audit_log (x) VALUES ('y')")
            c2.commit()
        duracion = time.monotonic() - t0
        c2.close()
        c1.commit()
        c1.close()
        assert duracion >= 0.25, (
            "la conexión independiente debe haber esperado el busy_timeout "
            "-- si no esperó nada, el escenario no se reprodujo")

    def test_registrar_con_con_no_espera_nada(self, tmp_path):
        ruta = str(tmp_path / "test.db")
        con = _con_con_pragmas(ruta, busy_timeout_ms=30000)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        con.commit()

        con.execute("BEGIN")
        con.execute("INSERT INTO t (id) VALUES (1)")
        t0 = time.monotonic()
        registrar("fisico1", "reemplazo", "t", ref="1", con=con)
        duracion = time.monotonic() - t0
        con.commit()
        con.close()

        assert duracion < 1.0, (
            f"registrar(con=...) tardó {duracion:.2f}s -- EB0-T exige "
            "menos de 1s con la transacción del llamador abierta")
