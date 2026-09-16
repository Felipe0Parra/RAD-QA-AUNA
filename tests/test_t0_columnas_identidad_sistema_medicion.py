"""T.0 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §1-bis): `SistemaMedicion`
gana `equipo_id_cp` y `equipo_id_ele`.

CAUSA: la tabla no tenía NINGUNA columna de id, así que con dos calibraciones
activas de la misma serie era imposible saber cuál se usó en un control de
braquiterapia -- el caso que motivó el principio del físico (16-09-2026).

El id es TRAZABILIDAD, no fuente de lectura: por el principio, ni la recarga
ni el PDF dependerán de estas columnas. Su valor es que, cuando existan, la
recarga pueda posicionar el combo en la calibración EXACTA; cuando no existan
(las 15 filas históricas, que quedan en `NULL` por `DA-13`), el comportamiento
es idéntico al de antes.

Cinco garantías, una por punto del protocolo de verificación del plan:

  1. la migración AGREGA las dos columnas y admiten `NULL`;
  2. es IDEMPOTENTE -- una segunda apertura no duplica ni falla;
  3. CERO filas tocadas -- censo y huella del contenido de `SistemaMedicion`
     idénticos antes y después, con `NULL` en las dos nuevas;
  4. ensayo sobre COPIA de las BD reales: `integrity_check=ok`,
     `foreign_key_check` sin aumento, censo de filas de TODAS las tablas
     idéntico, segunda corrida idempotente;
  5. los consumidores siguen funcionando -- en particular el ÚNICO que lee
     `SistemaMedicion` por POSICIÓN (`addsomething` vía `encontrar_columnas`),
     que es donde `DP-80` mordió la vez anterior.

TRAMPA DE `DP-80`, verificada y no supuesta: `ALTER TABLE ADD COLUMN` agrega
al final FÍSICO. El plan afirmaba que los "4 consumidores usan columnas
explícitas y ninguno hace `SELECT *`" -- **[medido] son 9 y dos SÍ hacen
`SELECT *`** (`reportes_mensuales.py:345`, `SQLtoEXCEL.py`). La conclusión se
sostiene, pero por otra razón: esos dos leen POR NOMBRE de campo, no por
índice. El que sí es posicional es `addsomething`, y lo salva que
`encontrar_columnas` excluye `activo` por NOMBRE (`P1`/`DP-80`) y que lo nuevo
queda al final, donde su `zip` lo descarta. `test_encontrar_columnas_*` de
abajo es lo que fija esa garantía.

Nunca se conecta a una BD de referencia: se copia a un temporal primero
(regla de sesión, `LR6`).
"""
import hashlib
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from _bd_referencia import BD_QA, BD_REBUILD_14_09

COLUMNAS_NUEVAS = ("equipo_id_cp", "equipo_id_ele")

# Esquema de `SistemaMedicion` ANTES de T.0, tal cual estaba en el
# `CREATE TABLE` de conection.py -- para fabricar una BD legada de verdad.
ESQUEMA_LEGADO = """
    CREATE TABLE SistemaMedicion (
        ref INTEGER,
        user TEXT,
        fecha TEXT,
        modelo TEXT,
        serie_cp TEXT,
        calibracion REAL,
        modelo_elec TEXT,
        serie_ele TEXT,
        electrometro REAL,
        t0 REAL,
        p0 REAL,
        h0 REAL,
        activo INTEGER DEFAULT 1
    )
"""

FILAS_LEGADAS = [
    (1, "fisico", "2026-01-15", "TW33004", "A092535", 464700.0,
     "CDX-2000B", "B091982", 1.0, 22.0, 760.0, 50.0, 1),
    (2, "fisico", "2026-02-15", "TW33004", "A972662", 466700.0,
     "Unidos-E", "002343", 1.001, 21.5, 758.0, 50.0, 1),
]


def _columnas(ruta, tabla="SistemaMedicion"):
    con = sqlite3.connect(ruta)
    try:
        return [f[1] for f in con.execute(f"PRAGMA table_info({tabla})")]
    finally:
        con.close()


def _huella_sistema_medicion(ruta, columnas=None):
    """SHA-256 del contenido de SistemaMedicion sobre un conjunto EXPLÍCITO de
    columnas, leídas por NOMBRE.

    `columnas` se captura ANTES de migrar y se reusa después, a propósito. La
    primera versión de esta función derivaba la lista de cada instantánea
    ("todas menos las nuevas") y dio un FALSO POSITIVO sobre la BD real:
    **[medido]** `BaseDatosQA.db` (copia del 21-08) no tiene `activo` en
    `SistemaMedicion`, y abrirla dispara `_asegurar_activo_bloque_qc` -- una
    migración PREEXISTENTE, ajena a `T.0`. La huella comparaba 12 columnas
    contra 13 y acusaba a `T.0` de un cambio de contenido que nunca hubo.
    Es la misma clase de error que `DP-86` describe para el observador de
    contrato: la herramienta de verificación cambiando de criterio a través
    del propio cambio que verifica."""
    con = sqlite3.connect(ruta)
    try:
        if columnas is None:
            cols = [f[1] for f in con.execute("PRAGMA table_info(SistemaMedicion)")]
            columnas = [c for c in cols if c not in COLUMNAS_NUEVAS]
        filas = con.execute(
            f"SELECT {', '.join(columnas)} FROM SistemaMedicion "
            f"ORDER BY ref, fecha").fetchall()
    finally:
        con.close()
    h = hashlib.sha256()
    for fila in filas:
        h.update(repr(fila).encode())
    return columnas, len(filas), h.hexdigest()


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
    """Arranca `Conexion()` contra `ruta` -- es lo que corre la migración."""
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    con = Conexion()
    con.con.close()
    Conexion._instance = None


@pytest.fixture
def bd_legada(tmp_path):
    """BD con `SistemaMedicion` SIN las columnas nuevas y con filas dentro --
    el estado real de cualquier base ya desplegada."""
    ruta = str(tmp_path / "legada.db")
    con = sqlite3.connect(ruta)
    con.execute(ESQUEMA_LEGADO)
    con.executemany(
        "INSERT INTO SistemaMedicion VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        FILAS_LEGADAS)
    con.commit()
    con.close()
    return ruta


# ---------------------------------------------------------------------------
# 1. La migración agrega las columnas (rojo-antes-que-verde: sin el código de
#    T.0 la BD legada sale de la app sin ellas)
# ---------------------------------------------------------------------------

def test_bd_legada_gana_las_dos_columnas(bd_legada, monkeypatch):
    assert COLUMNAS_NUEVAS[0] not in _columnas(bd_legada)
    assert COLUMNAS_NUEVAS[1] not in _columnas(bd_legada)

    _abrir_con_la_app(bd_legada, monkeypatch)

    cols = _columnas(bd_legada)
    for nueva in COLUMNAS_NUEVAS:
        assert nueva in cols, (
            f"T.0 no agregó '{nueva}' a SistemaMedicion. Columnas: {cols}")


def test_las_columnas_nuevas_van_despues_de_activo(bd_legada, monkeypatch):
    """Orden físico DETERMINISTA: la migración corre después de
    `_asegurar_activo_bloque_qc`, así que `activo` queda antes en cualquier
    BD, nueva o ya desplegada. Si alguien la mueve a
    `_asegurar_migraciones_ad_hoc` (que corre antes), una BD nueva quedaría
    con el orden invertido respecto de una vieja."""
    _abrir_con_la_app(bd_legada, monkeypatch)
    cols = _columnas(bd_legada)
    assert cols.index("activo") < cols.index("equipo_id_cp") < cols.index("equipo_id_ele")


def test_bd_nueva_tambien_las_tiene(tmp_path, monkeypatch):
    ruta = str(tmp_path / "nueva.db")
    _abrir_con_la_app(ruta, monkeypatch)
    cols = _columnas(ruta)
    for nueva in COLUMNAS_NUEVAS:
        assert nueva in cols


def test_admiten_null_y_admiten_un_id(bd_legada, monkeypatch):
    _abrir_con_la_app(bd_legada, monkeypatch)
    con = sqlite3.connect(bd_legada)
    try:
        # NULL es el estado honesto de lo histórico (DA-13)
        nulos = con.execute(
            "SELECT COUNT(*) FROM SistemaMedicion "
            "WHERE equipo_id_cp IS NULL AND equipo_id_ele IS NULL").fetchone()[0]
        assert nulos == len(FILAS_LEGADAS)
        # y la columna acepta un id cuando T.2 lo escriba
        con.execute("UPDATE SistemaMedicion SET equipo_id_cp=17, "
                    "equipo_id_ele=79 WHERE ref=1")
        con.commit()
        assert con.execute(
            "SELECT equipo_id_cp, equipo_id_ele FROM SistemaMedicion "
            "WHERE ref=1").fetchone() == (17, 79)
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 2. Idempotencia
# ---------------------------------------------------------------------------

def test_segunda_apertura_no_duplica_ni_falla(bd_legada, monkeypatch):
    _abrir_con_la_app(bd_legada, monkeypatch)
    cols_1 = _columnas(bd_legada)
    _abrir_con_la_app(bd_legada, monkeypatch)
    cols_2 = _columnas(bd_legada)
    assert cols_1 == cols_2
    assert cols_2.count("equipo_id_cp") == 1
    assert cols_2.count("equipo_id_ele") == 1


# ---------------------------------------------------------------------------
# 3. Cero filas tocadas
# ---------------------------------------------------------------------------

def test_ninguna_fila_existente_cambia(bd_legada, monkeypatch):
    columnas, antes = _huella_sistema_medicion(bd_legada)[0], _huella_sistema_medicion(bd_legada)[1:]
    _abrir_con_la_app(bd_legada, monkeypatch)
    despues = _huella_sistema_medicion(bd_legada, columnas)[1:]
    assert antes == despues, (
        "T.0 cambió el contenido de SistemaMedicion. Es ADITIVA: "
        f"antes={antes} despues={despues}")


# ---------------------------------------------------------------------------
# 4. Ensayo sobre COPIA de las BD reales (punto 6 del protocolo de CLAUDE.md)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("origen", [BD_QA, BD_REBUILD_14_09])
def test_ensayo_sobre_copia_de_bd_real(origen, tmp_path, monkeypatch):
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")

    ruta = str(tmp_path / "copia_real.db")
    shutil.copy(origen, ruta)

    censo_antes = _censo_de_filas(ruta)
    columnas_previas, n_antes, huella_antes = _huella_sistema_medicion(ruta)
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

    cols = _columnas(ruta)
    for nueva in COLUMNAS_NUEVAS:
        assert nueva in cols

    _, n_despues, huella_despues = _huella_sistema_medicion(ruta, columnas_previas)
    assert (n_despues, huella_despues) == (n_antes, huella_antes), (
        "el contenido previo de SistemaMedicion cambió en una BD real")

    censo_despues = _censo_de_filas(ruta)
    for tabla, n in censo_antes.items():
        assert censo_despues.get(tabla) == n, (
            f"el censo de filas de '{tabla}' cambió: {n} -> "
            f"{censo_despues.get(tabla)}")

    # segunda corrida idempotente sobre la misma copia real
    _abrir_con_la_app(ruta, monkeypatch)
    assert _columnas(ruta) == cols
    assert _censo_de_filas(ruta) == censo_despues


# ---------------------------------------------------------------------------
# 5. El consumidor POSICIONAL sigue leyendo lo mismo (la trampa de DP-80)
# ---------------------------------------------------------------------------

def test_encontrar_columnas_deja_las_previas_en_su_posicion(bd_legada, monkeypatch):
    """`addsomething` (braq_mensual.py) hace
    `zip(df_lines, datos)` sobre el resultado de
    `encontrar_columnas("SistemaMedicion", id=True, delete=0)`: es POSICIONAL.

    La garantía que necesita es que las columnas de siempre conserven su
    índice y que lo nuevo quede al final (donde `zip` lo descarta). Esto es
    exactamente lo que `DP-80` rompió en `braqui` cuando la exclusión de
    `activo` todavía era por posición."""
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: bd_legada)
    Conexion._instance = None
    from data.ManejoDatos.load import encontrar_columnas

    columnas_str, _ = encontrar_columnas("SistemaMedicion", id=True, delete=0)
    columnas = columnas_str.split(", ")
    Conexion._instance = None

    previas = ["user", "fecha", "modelo", "serie_cp", "calibracion",
               "modelo_elec", "serie_ele", "electrometro", "t0", "p0", "h0"]
    assert columnas[:len(previas)] == previas, (
        "T.0 desplazó las columnas que addsomething lee por posición")
    assert "activo" not in columnas, "activo debe seguir excluido POR NOMBRE"
    assert columnas[len(previas):] == list(COLUMNAS_NUEVAS)


def test_los_consumidores_explicitos_siguen_nombrando_sus_columnas():
    """Compuerta de alcance: T.0 NO debe haber tocado ningún `SELECT`/`INSERT`
    de SistemaMedicion. Los 5 sitios de columnas explícitas se quedan como
    estaban -- `T.2` será quien añada las dos al INSERT, no esta tarea."""
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parent.parent
    insert = (raiz / "data/ManejoDatos/load.py").read_text(encoding="utf-8", errors="replace")
    assert ("INSERT INTO SistemaMedicion (ref, user, fecha, modelo, serie_cp, "
            "calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0)") in insert, (
        "el INSERT explícito de SistemaMedicion cambió en T.0; le corresponde a T.2")
