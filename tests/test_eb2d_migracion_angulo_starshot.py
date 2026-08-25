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

**DA-69 (25-08, decisión del físico): esta migración YA NO CORRE AL
ABRIR LA APP.** Reconstruye una tabla (crear temporal, copiar, DROP,
renombrar) y, a diferencia de E10, sin respaldo previo propio -- que eso se
dispare solo en cada arranque es lo que el físico pidió acotar: *"que las
correcciones que se hagan sean de una sola vez... la solución siempre
apuntando a corregir la estructura de la BD"*. Su único disparador es ahora
`scripts/migrar_bd_a_estandar.py`, que respalda antes y reporta lo que hizo.

Se movió SOLO esta, a propósito: E10 lleva desde el 29-07 con su respaldo
propio (F1) y `_asegurar_activo_bloque_qc` es aditivo (`ALTER TABLE ADD
COLUMN`, no puede perder una fila). Mover lo que ya funcionaba era el
riesgo mayor.

Los tests de BD legada invocan la migración EXPLÍCITAMENTE, igual que hace
la herramienta -- ya no basta con abrir `Conexion()`.
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
        conexion = Conexion()
        # DA-69 (25-08): el arranque ya NO dispara esta migración -- se
        # invoca explícitamente, igual que hace la herramienta de
        # migración, que es su único disparador desde entonces.
        conexion._asegurar_angulo_starshot_sin_unique_de_tabla()
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
        conexion._asegurar_angulo_starshot_sin_unique_de_tabla()
        conexion.con.close()
        Conexion._instance = None

        con = sqlite3.connect(ruta)
        esquema_1 = sorted((r[0], r[1] or "") for r in con.execute(
            "SELECT name, sql FROM sqlite_master"))
        con.close()

        conexion = Conexion()
        conexion._asegurar_angulo_starshot_sin_unique_de_tabla()  # 2a corrida
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
        conexion._asegurar_angulo_starshot_sin_unique_de_tabla()
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
        conexion._asegurar_angulo_starshot_sin_unique_de_tabla()
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


class TestNoCorreSolaAlAbrirLaApp:
    """DA-69 (25-08): la garantía que el físico pidió -- abrir la aplicación
    NO puede disparar una reconstrucción de tabla. Es la contraparte
    verificable de haber sacado la llamada de `__init_connection`: sin este
    test, alguien podría reponerla y nadie se enteraría."""

    def _bd_legada_con_unique(self, tmp_path, monkeypatch):
        ruta = str(tmp_path / "legada.db")
        con = sqlite3.connect(ruta)
        con.execute("""
            CREATE TABLE angulo_starshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER NOT NULL,
                spoke_index INTEGER NOT NULL,
                angulo_nominal_deg REAL, angulo_real_deg REAL,
                desviacion_deg REAL,
                UNIQUE(ref, spoke_index)
            )""")
        con.commit()
        con.close()
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        return ruta

    def test_abrir_la_app_no_reconstruye_la_tabla(self, tmp_path, monkeypatch):
        ruta = self._bd_legada_con_unique(tmp_path, monkeypatch)
        conexion = Conexion()          # arranque real y completo
        try:
            con = sqlite3.connect(ruta)
            sql = con.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                "AND name='angulo_starshot'").fetchone()[0]
            con.close()
            assert "UNIQUE(ref, spoke_index)" in sql, (
                "abrir la app NO debe reconstruir angulo_starshot -- si esta "
                "constraint desapareció, la llamada volvió a "
                "__init_connection y la reconstrucción se dispara sola otra "
                "vez (DA-69)")
        finally:
            conexion.con.close()
            Conexion._instance = None

    def test_la_herramienta_de_migracion_si_la_aplica(self, tmp_path, monkeypatch):
        """El otro lado: sacarla del arranque no puede dejarla huérfana."""
        from scripts.migrar_bd_a_estandar import migrar
        ruta = self._bd_legada_con_unique(tmp_path, monkeypatch)
        Conexion._instance = None
        resultado = migrar(ruta, aplicar=True)
        Conexion._instance = None

        assert resultado["angulo_starshot_sin_unique"]["estado"].startswith("migrada")
        con = sqlite3.connect(ruta)
        sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='angulo_starshot'").fetchone()[0]
        con.close()
        assert "UNIQUE(ref, spoke_index)" not in sql


class TestLaFuncionDestructivaYaNoExiste:
    """DP-44 -> [[DA-68]] (25-08, decisión del físico): se retiró
    `eliminar_tablas_cambio_fuente()`, que hacía `DROP TABLE IF EXISTS` sobre
    las 6 tablas de braquiterapia sin ninguna guarda. Nunca estuvo conectada,
    pero descomentar su llamada habría destruido braquiterapia entera al
    siguiente arranque. Se eligió retirarla en vez de vigilarla: lo que no
    existe no se puede reconectar por descuido -- y este test es lo que
    impide que vuelva."""

    def test_no_existe_el_metodo(self):
        assert not hasattr(Conexion, "eliminar_tablas_cambio_fuente"), (
            "eliminar_tablas_cambio_fuente() volvió al código -- hacía DROP "
            "TABLE sobre las 6 tablas de braquiterapia sin mirar si tenían "
            "datos, sin confirmar, sin auditar y sin respaldar (DA-68)")

    def test_ningun_drop_table_de_braquiterapia_en_el_arranque(self):
        """Más fuerte que comprobar el nombre: que no aparezca NINGÚN `DROP
        TABLE` sobre esas 6 tablas en todo `conection.py`, se llame como se
        llame la función que lo hiciera."""
        import re
        from pathlib import Path
        fuente = (Path(conection_mod.__file__)).read_text(encoding="utf-8")
        # se ignoran los comentarios: el que documenta la retirada las nombra
        codigo = "\n".join(l for l in fuente.split("\n")
                           if not l.lstrip().startswith("#"))
        for tabla in ("TipoCalibracion", "SistemaMedicion", "CondicionesMedicion",
                      "MaximosCamaras", "LecturasMaximos", "ResultadosActividad"):
            assert not re.search(rf'DROP\s+TABLE\s+(IF\s+EXISTS\s+)?["\[]?{tabla}\b',
                                 codigo, re.IGNORECASE), (
                f"apareció un DROP TABLE sobre {tabla} en conection.py -- "
                f"esas 6 tablas cargan todo el histórico de braquiterapia")
