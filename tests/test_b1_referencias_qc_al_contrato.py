"""B.1 (PLAN_REFERENCIAS_EDITABLES_21-09.md): tabla `referencias_qc` al
contrato de QC completo -- la tabla que guarda las líneas base y valores de
referencia editables desde la app (DP-25/DP-108), con la receta de 6 pasos
que R1 (PLAN_REPARACION_ANUAL_27-08.md) ya usó para 4 tablas parecidas:
(1) columna `activo` (la agrega sola `_asegurar_activo_bloque_qc`);
(2) `TABLAS_ANULABLES`; (3) `CLAVES_INDICE`; (4) índice UNIQUE parcial;
(5) `CREATE TABLE IF NOT EXISTS` idempotente; (6) escritura con
`reemplazar_bloque`, lectura con `filtro_activo` (B.2, tarea aparte -- este
archivo cubre 1-5, el esquema y el contrato, no el servicio).

Autorizada por el físico el 21-09-2026 ("Listo, autorizo todo eso"), bajo el
mismo protocolo que `DA-80`: ensayo previo sobre COPIA de las BD reales,
censo de filas idéntico, `integrity_check=ok`, `foreign_key_check` sin
aumento sobre la línea base de 109 (`DA-43`), segunda corrida idempotente.

Clave de bloque: `(equipo, magnitud, energia)`. `energia` guarda `''` (no
`NULL`) cuando la magnitud no depende de la energía -- en SQLite dos `NULL`
no colisionan en un índice `UNIQUE`, así que `NULL` dejaría esas filas sin
proteger (demostrado en `TestElIndiceProtegeLaClave`).

Nunca se conecta a una BD de referencia directamente: se copia a un
temporal antes (regla de sesión).
"""
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.anulacion import TABLAS_ANULABLES
from scripts.indices_bloque_qc import CLAVES_INDICE, crear_indices

from _bd_referencia import BD_QA, BD_REBUILD_14_09, BD_A_AJUSTAR

TABLA = "referencias_qc"
COLUMNAS_DATO = ("equipo", "magnitud", "energia", "valor", "unidad", "fuente",
                  "observaciones", "fijada_por", "fecha")
CLAVE = ("equipo", "magnitud", "energia")


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield conexion
    conexion.con.close()
    Conexion._instance = None


def _columnas(con, tabla=TABLA):
    return [c[1] for c in con.execute(f"PRAGMA table_info('{tabla}')").fetchall()]


def _censo_de_filas(ruta):
    con = sqlite3.connect(ruta)
    try:
        tablas = [t[0] for t in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                for t in tablas}
    finally:
        con.close()


def _abrir_con_la_app(ruta, monkeypatch):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    con = Conexion()
    con.con.close()
    Conexion._instance = None


class TestNaceConElEsquemaCorrecto:
    def test_columnas_de_datos_en_el_orden_declarado(self, bd_temporal):
        columnas_reales = _columnas(bd_temporal.con)
        assert columnas_reales, f"{TABLA}: no existe (sin CREATE TABLE)"
        assert columnas_reales[0] == "id"
        assert tuple(columnas_reales[1:1 + len(COLUMNAS_DATO)]) == COLUMNAS_DATO

    def test_gana_activo_al_arrancar(self, bd_temporal):
        assert "activo" in _columnas(bd_temporal.con)

    def test_activo_queda_al_final_fisico(self, bd_temporal):
        """DP-80: ALTER TABLE ADD COLUMN agrega siempre al final físico.
        Como la tabla nace SIN `activo` y `_asegurar_activo_bloque_qc` lo
        agrega en el mismo arranque, en una BD nueva termina siendo la
        última columna -- lo mismo que en una BD ya desplegada."""
        columnas = _columnas(bd_temporal.con)
        assert columnas[-1] == "activo"

    def test_esta_en_tablas_anulables(self):
        assert TABLA in TABLAS_ANULABLES

    def test_clave_natural_declarada_y_sus_columnas_existen(self, bd_temporal):
        assert TABLA in CLAVES_INDICE
        assert CLAVES_INDICE[TABLA] == CLAVE
        columnas_reales = set(_columnas(bd_temporal.con))
        for columna in CLAVE:
            assert columna in columnas_reales

    def test_columnas_obligatorias_no_admiten_null(self, bd_temporal):
        con = bd_temporal.con
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"INSERT INTO {TABLA} (magnitud, energia, valor) "
                "VALUES ('calidad', '6mv', 0.665)")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"INSERT INTO {TABLA} (equipo, energia, valor) "
                "VALUES ('Halcyon', '6mv', 0.627)")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"INSERT INTO {TABLA} (equipo, magnitud, energia) "
                "VALUES ('Halcyon', 'calidad', '6mv')")

    def test_segunda_apertura_no_falla_ni_duplica(self, bd_temporal, monkeypatch, tmp_path):
        """CREATE TABLE IF NOT EXISTS: idempotente, sin importar cuántas
        veces arranque la app sobre la misma BD."""
        ruta = str(tmp_path / "test.db")
        cols_1 = _columnas(bd_temporal.con)
        bd_temporal.con.close()
        Conexion._instance = None
        _abrir_con_la_app(ruta, monkeypatch)
        con2 = sqlite3.connect(ruta)
        try:
            cols_2 = _columnas(con2)
        finally:
            con2.close()
        assert cols_1 == cols_2


class TestElIndiceUnicoSeCreaSinExcepciones:
    def test_crear_indices_crea_referencias_qc(self, bd_temporal, tmp_path):
        ruta = str(tmp_path / "test.db")
        bd_temporal.con.close()
        resultado = crear_indices(ruta)
        assert resultado[TABLA] == "creado"


class TestElIndiceProtegeLaClave:
    def _con_indice(self, bd_temporal, tmp_path):
        ruta = str(tmp_path / "test.db")
        bd_temporal.con.close()
        resultado = crear_indices(ruta)
        assert resultado[TABLA] == "creado"
        Conexion._instance = None
        return Conexion().con

    def test_dos_filas_activas_misma_clave_rechaza(self, bd_temporal, tmp_path):
        con = self._con_indice(bd_temporal, tmp_path)
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
            "VALUES ('Halcyon', 'calidad', '6mv', 0.627)")
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
                "VALUES ('Halcyon', 'calidad', '6mv', 0.640)")
        Conexion._instance = None

    def test_anular_e_insertar_no_choca(self, bd_temporal, tmp_path):
        """La garantía titular del contrato: cambiar una referencia anula
        la vigente e inserta la nueva -- nunca un UPDATE en sitio, así que
        la anterior queda recuperable (historial via el propio contrato)."""
        con = self._con_indice(bd_temporal, tmp_path)
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor, activo) "
            "VALUES ('Halcyon', 'calidad', '6mv', 0.627, 1)")
        con.commit()

        con.execute(
            f"UPDATE {TABLA} SET activo = 0 WHERE equipo='Halcyon' "
            "AND magnitud='calidad' AND energia='6mv' "
            "AND (activo IS NULL OR activo = 1)")
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor, activo) "
            "VALUES ('Halcyon', 'calidad', '6mv', 0.640, 1)")
        con.commit()

        total = con.execute(
            f"SELECT COUNT(*) FROM {TABLA} WHERE equipo='Halcyon' "
            "AND magnitud='calidad' AND energia='6mv'").fetchone()[0]
        assert total == 2, "la referencia anterior debe seguir existiendo, anulada"
        vigente = con.execute(
            f"SELECT valor FROM {TABLA} WHERE equipo='Halcyon' "
            "AND magnitud='calidad' AND energia='6mv' "
            "AND (activo IS NULL OR activo = 1)").fetchone()
        assert vigente[0] == pytest.approx(0.640)
        Conexion._instance = None

    def test_distintas_energias_o_equipos_no_chocan(self, bd_temporal, tmp_path):
        con = self._con_indice(bd_temporal, tmp_path)
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
            "VALUES ('Clinac ix', 'calidad', '6mv', 0.665)")
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
            "VALUES ('Clinac ix', 'calidad', '15mv', 0.761)")
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
            "VALUES ('Clinac 600', 'calidad', '6mv', 0.6667)")
        con.commit()  # ninguna de las tres debe chocar con otra
        Conexion._instance = None

    def test_energia_null_no_protege_pero_cadena_vacia_si(self, bd_temporal, tmp_path):
        """§1.3 del plan: en SQLite dos NULL no colisionan en un UNIQUE --
        por eso la convención es guardar '' para 'no aplica', nunca NULL.
        Se demuestra el riesgo (NULL no protege) Y la solución ('' sí)."""
        con = self._con_indice(bd_temporal, tmp_path)
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
            "VALUES ('Clinac ix', 'tol_dosis', NULL, 2.0)")
        con.commit()
        # Con NULL, una segunda fila "vigente" para la misma clave NO es
        # rechazada -- es la trampa que motiva la convención de '':
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
            "VALUES ('Clinac ix', 'tol_dosis', NULL, 3.0)")
        con.commit()  # no lanza -- dos filas "vigentes" conviven sin aviso

        # Con '' sí protege:
        con.execute(
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
            "VALUES ('Clinac 600', 'tol_dosis', '', 2.0)")
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor) "
                "VALUES ('Clinac 600', 'tol_dosis', '', 3.0)")
        Conexion._instance = None


# ---------------------------------------------------------------------------
# Ensayo sobre COPIA de las BD reales (protocolo de DA-80/CLAUDE.md)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("origen", [BD_QA, BD_REBUILD_14_09, BD_A_AJUSTAR])
def test_ensayo_sobre_copia_de_bd_real(origen, tmp_path, monkeypatch):
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")

    ruta = str(tmp_path / "copia_real.db")
    shutil.copy(origen, ruta)

    censo_antes = _censo_de_filas(ruta)
    con = sqlite3.connect(ruta)
    fk_antes = len(con.execute("PRAGMA foreign_key_check").fetchall())
    con.close()

    _abrir_con_la_app(ruta, monkeypatch)

    con = sqlite3.connect(ruta)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        fk_despues = len(con.execute("PRAGMA foreign_key_check").fetchall())
    finally:
        con.close()

    assert fk_despues <= fk_antes, (
        f"foreign_key_check AUMENTÓ: {fk_antes} -> {fk_despues}")

    censo_despues = _censo_de_filas(ruta)
    # la tabla nueva aparece, vacía -- nada más cambia
    assert censo_despues.get(TABLA) == 0
    for tabla, n in censo_antes.items():
        assert censo_despues.get(tabla) == n, (
            f"el censo de filas de '{tabla}' cambió: {n} -> "
            f"{censo_despues.get(tabla)}")

    # segunda corrida idempotente sobre la misma copia real
    _abrir_con_la_app(ruta, monkeypatch)
    assert _censo_de_filas(ruta) == censo_despues


@pytest.mark.parametrize("origen", [BD_QA, BD_REBUILD_14_09, BD_A_AJUSTAR])
def test_crear_indices_sobre_copia_de_bd_real(origen, tmp_path, monkeypatch):
    """El índice UNIQUE también se ensaya sobre copia real: si alguna BD
    tuviera ya filas conflictivas (no debería, la tabla es nueva), el
    índice fallaría a crearse y este test lo diría con el motivo exacto."""
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")

    ruta = str(tmp_path / "copia_real.db")
    shutil.copy(origen, ruta)
    _abrir_con_la_app(ruta, monkeypatch)

    resultado = crear_indices(ruta)
    assert resultado[TABLA] == "creado", resultado[TABLA]
