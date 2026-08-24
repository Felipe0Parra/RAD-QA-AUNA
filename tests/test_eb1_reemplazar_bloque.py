"""EB1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB1, DA-52): punto único de
reemplazo de bloque para la pila `sqlite3` -- `reemplazar_bloque` sustituye
a los `DELETE FROM ...; INSERT INTO ...` de las ramas de guardado del
bloque de QC (EB2/EB4). El bloque anterior se ANULA (activo=0), nunca se
borra; si no hay filas nuevas que insertar, el bloque vigente no se toca
(invariante 4, T3).

Prueba también `sql_anular_bloque` en aislamiento (claves simples y por
expresión, reusando el mecanismo de MI3) y que `EB0` (auditoría en la
misma transacción) queda realmente enganchado -- `reemplazar_bloque` no
abre ninguna conexión aparte para auditar.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from services.anulacion import (
    TABLAS_ANULABLES, reemplazar_bloque, sql_anular_bloque,
)


@pytest.fixture
def con(tmp_path):
    ruta = str(tmp_path / "test.db")
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute(
        "CREATE TABLE control_cunas (id INTEGER PRIMARY KEY, ref INTEGER, "
        "angulo TEXT, valor REAL, activo INTEGER DEFAULT 1)")
    con.execute(
        "CREATE TABLE aceleradorlineal_ix (id INTEGER PRIMARY KEY, "
        "date TEXT, user_id TEXT, observaciones TEXT, activo INTEGER DEFAULT 1)")
    con.commit()
    yield con
    con.close()


class TestSqlAnularBloque:

    def test_clave_simple(self):
        sql = sql_anular_bloque("control_cunas", ("ref", "angulo"))
        assert sql == (
            'UPDATE "control_cunas" SET activo = 0 WHERE "ref"=? AND '
            '"angulo"=? AND (activo IS NULL OR activo = 1)')

    def test_clave_por_expresion(self):
        sql = sql_anular_bloque("aceleradorlineal_ix", ("DATE(date)",))
        assert sql == (
            'UPDATE "aceleradorlineal_ix" SET activo = 0 WHERE DATE(date)=DATE(?) '
            'AND (activo IS NULL OR activo = 1)')
        assert '"DATE(date)"' not in sql, (
            "una expresión no debe quedar citada como si fuera un "
            "identificador -- rompería el SQL")

    def test_rechaza_tabla_fuera_del_inventario(self):
        with pytest.raises(ValueError, match="lista blanca"):
            sql_anular_bloque("users", ("id",))


class TestReemplazarBloque:

    def test_ausencia_de_activo_previo_no_impide_insertar(self, con):
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1", ref="1/90")
        con.commit()

        filas = con.execute(
            "SELECT ref, angulo, valor, activo FROM control_cunas").fetchall()
        assert filas == [(1, "90", 3.5, 1)]

    def test_reemplazo_anula_el_bloque_anterior_y_conserva_historial(self, con):
        cur = con.cursor()
        cur.execute(
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (1, '90', 3.5)")
        con.commit()

        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.9)], "fisico1", ref="1/90")
        con.commit()

        filas = con.execute(
            "SELECT valor, activo FROM control_cunas ORDER BY id").fetchall()
        assert filas == [(3.5, 0), (3.9, 1)], (
            "el bloque anterior debe quedar anulado (activo=0), NUNCA "
            "borrado -- y el nuevo debe quedar vigente")

    def test_filas_vacias_no_toca_el_bloque_vigente(self, con):
        """Invariante 4 (T3): sin bloque nuevo válido, el vigente se
        conserva intacto -- ni se anula ni se borra."""
        cur = con.cursor()
        cur.execute(
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (1, '90', 3.5)")
        con.commit()

        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [], "fisico1", ref="1/90")
        con.commit()

        filas = con.execute(
            "SELECT valor, activo FROM control_cunas").fetchall()
        assert filas == [(3.5, 1)], (
            "con `filas` vacío no debe anularse el bloque vigente -- "
            "invariante 4 del contrato")

    def test_no_commitea_es_responsabilidad_del_llamador(self, con):
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1", ref="1/90")

        con2 = sqlite3.connect(con.execute("PRAGMA database_list").fetchone()[2])
        con2.execute("PRAGMA busy_timeout=200")
        filas_fuera = con2.execute("SELECT COUNT(*) FROM control_cunas").fetchone()[0]
        con2.close()
        con.rollback()

        assert filas_fuera == 0, (
            "reemplazar_bloque NO debe commitear -- si lo hiciera, un "
            "guardado de varias tablas no podría revertirse entero ante "
            "un fallo a mitad de camino (G2)")

    def test_expresion_acepta_valor_con_hora(self, con):
        """`DATE(?)` en el WHERE (no un `?` desnudo) es lo que permite
        pasar un datetime completo (el caso real de TipoCalibracion,
        EB2b) y que aun así compare bien contra `DATE(columna)`."""
        cur = con.cursor()
        cur.execute(
            "INSERT INTO aceleradorlineal_ix (date, user_id, observaciones) "
            "VALUES ('2026-08-20', 'u1', 'antes')")
        con.commit()

        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "aceleradorlineal_ix",
            [("DATE(date)", "2026-08-20 14:30:00")],
            "INSERT INTO aceleradorlineal_ix (date, user_id, observaciones) "
            "VALUES (?, ?, ?)",
            [("2026-08-20", "u1", "despues")], "fisico1", ref="2026-08-20")
        con.commit()

        filas = con.execute(
            "SELECT observaciones, activo FROM aceleradorlineal_ix "
            "ORDER BY id").fetchall()
        assert filas == [("antes", 0), ("despues", 1)]

    def test_expresion_como_clave_de_las_diarias(self, con):
        cur = con.cursor()
        cur.execute(
            "INSERT INTO aceleradorlineal_ix (date, user_id, observaciones) "
            "VALUES ('2026-08-20', 'u1', 'antes')")
        con.commit()

        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "aceleradorlineal_ix", [("DATE(date)", "2026-08-20")],
            "INSERT INTO aceleradorlineal_ix (date, user_id, observaciones) "
            "VALUES (?, ?, ?)",
            [("2026-08-20", "u1", "despues")], "fisico1", ref="2026-08-20")
        con.commit()

        filas = con.execute(
            "SELECT observaciones, activo FROM aceleradorlineal_ix "
            "ORDER BY id").fetchall()
        assert filas == [("antes", 0), ("despues", 1)]

    def test_rechaza_tabla_fuera_del_inventario(self, con):
        cur = con.cursor()
        con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        cur.execute("BEGIN")
        with pytest.raises(ValueError, match="lista blanca"):
            reemplazar_bloque(
                cur, "users", [("id", 1)],
                "INSERT INTO users (id) VALUES (?)", [(1,)], "fisico1")
        con.rollback()

    def test_auditoria_queda_en_la_misma_transaccion(self, con):
        """EB0 enganchado de verdad: la auditoría no debe abrir una
        conexión propia -- debe verse en la MISMA transacción antes del
        commit, y confirmarse después de él."""
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1", ref="1/90", detalle="prueba EB0")

        fila = con.execute(
            "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchone()
        assert fila == ("fisico1", "reemplazo", "control_cunas", "1/90", "prueba EB0")

        con.commit()
        assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1


class TestRefYAccionPorDefecto:

    def test_ref_por_defecto_es_el_lastrowid(self, con):
        """Sin `ref` explícito, la auditoría usa el id recién insertado --
        el caso natural de una RAÍZ con autoincrement (TipoCalibracion,
        EB2b), cuyo `ref` de negocio ES ese id, no algo conocido antes de
        insertar."""
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1")
        nuevo_id = cur.lastrowid
        fila = con.execute(
            "SELECT ref FROM audit_log").fetchone()
        assert fila == (str(nuevo_id),)
        con.commit()

    def test_accion_por_defecto_es_reemplazo(self, con):
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1", ref="1/90")
        accion = con.execute("SELECT accion FROM audit_log").fetchone()
        assert accion == ("reemplazo",)
        con.commit()

    def test_accion_override(self, con):
        """guardar_resultado_CambioFuente (EB2b) conserva su propio verbo
        histórico ('guardar') en vez de 'reemplazo' -- no rompe el
        vocabulario que sus propios tests/reportes ya leen."""
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1", ref="1/90", accion="guardar")
        accion = con.execute("SELECT accion FROM audit_log").fetchone()
        assert accion == ("guardar",)
        con.commit()


class TestAuditarFalse:
    """A6.3 ("una acción, una fila"): cuando `reemplazar_bloque` es solo
    UNA pieza de una acción más grande auditada en otro punto (p.ej.
    guardar_analisis_placa600, EB2a, con sus 3 tablas)."""

    def test_no_escribe_fila_de_auditoria(self, con):
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1", auditar=False)
        con.commit()
        try:
            total = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        except sqlite3.OperationalError:
            total = 0  # ni siquiera se creó la tabla -- registrar() nunca corrió
        assert total == 0

    def test_el_update_y_el_insert_si_ocurren(self, con):
        cur = con.cursor()
        cur.execute(
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (1, '90', 3.5)")
        con.commit()

        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.9)], "fisico1", auditar=False)
        con.commit()

        filas = con.execute(
            "SELECT valor, activo FROM control_cunas ORDER BY id").fetchall()
        assert filas == [(3.5, 0), (3.9, 1)]


class TestLastrowid:
    """Hallazgo real (24-08, al preparar EB2b): `sqlite3.Cursor.executemany`
    NO actualiza `cursor.lastrowid` (queda en `None` incluso con una sola
    fila) -- `reemplazar_bloque` usa un bucle de `execute()` en su lugar
    precisamente para que esto funcione. Varios llamadores de EB2
    necesitan el id recién insertado (p.ej. el nuevo `id` de
    `TipoCalibracion` se vuelve el `ref` de sus 5 tablas hijas)."""

    def test_lastrowid_disponible_tras_una_sola_fila(self, con):
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 1), ("angulo", "90")],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(1, "90", 3.5)], "fisico1", ref="1/90")
        assert cur.lastrowid is not None
        nuevo_id = cur.lastrowid
        con.commit()

        fila = con.execute(
            "SELECT id FROM control_cunas WHERE ref=1 AND angulo='90'").fetchone()
        assert fila == (nuevo_id,)

    def test_lastrowid_es_la_ultima_fila_con_varias(self, con):
        cur = con.cursor()
        cur.execute("BEGIN")
        reemplazar_bloque(
            cur, "control_cunas", [("ref", 2)],
            "INSERT INTO control_cunas (ref, angulo, valor) VALUES (?, ?, ?)",
            [(2, "90", 1.0), (2, "270", 2.0)], "fisico1", ref="2")
        ultimo_id = cur.lastrowid
        con.commit()

        fila = con.execute(
            "SELECT id FROM control_cunas WHERE ref=2 AND angulo='270'").fetchone()
        assert fila == (ultimo_id,)


def test_ambas_tablas_de_prueba_estan_en_el_inventario():
    """Guarda contra un fixture que deje de reflejar el inventario real."""
    assert {"control_cunas", "aceleradorlineal_ix"} <= TABLAS_ANULABLES
