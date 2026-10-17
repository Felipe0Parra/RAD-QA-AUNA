"""PI.2 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md): la tabla `braqui_posicion_inicial` al contrato de QC completo -- donde
se guarda la prueba de posición inicial de la fuente de braquiterapia (imagen, clics, parámetros y lo medido: el desfase
del gris y de cada capa de color, en píxeles y en milímetros). Receta de 6 pasos de R1/B.1 (`referencias_qc`):
(1) columna `activo` (la agrega sola `_asegurar_activo_bloque_qc`); (2) `TABLAS_ANULABLES`; (3) `CLAVES_INDICE`;
(4) índice UNIQUE parcial; (5) `CREATE TABLE IF NOT EXISTS` idempotente; (6) escritura con `reemplazar_bloque`, lectura
con `filtro_activo` (PI.3, tarea aparte -- este archivo cubre 1-5, el esquema y el contrato, no el servicio).

Raíz PROPIA del contrato (sexta de la historia del proyecto, como `referencias_qc`): sin FK, porque el enlace con el
cambio de fuente es por la FECHA -- un FK por `id` se rompería al primer reguardado del cambio de fuente (anular+insertar
le da `id` nuevo). Clave de bloque: `("fecha",)` -- dos pruebas VIGENTES para el mismo cambio de fuente son imposibles.

Un CHECK por perfil (gris, r, g, b) rechaza milímetros que no sean EXACTAMENTE píxeles por la escala con que se midió
(`tamano_pixel_mm`): milímetros con otra escala, milímetros sin píxeles, píxeles sin milímetros (con escala) y
milímetros redondeados. Se prueba que SQLite rechaza cada una de esas filas y que acepta lo que el motor entrega de
verdad (los valores salen de `valores_medidos` sobre la placa real braqui_00, no de una lista escrita a mano).

Autorizada por el plan (tarea PI.2) bajo el protocolo de `DA-80`: ensayo previo sobre COPIA de las BD reales, censo de
filas idéntico, `integrity_check=ok`, `foreign_key_check` sin aumento sobre la línea base de 109 (`DA-43`), segunda
corrida idempotente. Nunca se conecta a una BD de referencia directamente: se copia a un temporal antes (regla de
sesión).
"""
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from analisisImagenes import posicion_inicial_braqui as motor
from services import visor_anulados as visor
from services.anulacion import TABLAS_ANULABLES, reemplazar_bloque
from services.lectura_vigente import RAICES_QC
from scripts.indices_bloque_qc import CLAVES_INDICE, crear_indices, nombre_indice

from _bd_referencia import BD_QA, BD_REBUILD_14_09, BD_REBUILD_21_09, BD_A_AJUSTAR

TABLA = "braqui_posicion_inicial"
CLAVE = ("fecha",)
DATOS = Path(__file__).resolve().parent / "datos"
CLICS_PLACA_REAL = [(191, 377), (190, 56)]          # los del físico sobre braqui_00.jpeg (como en test_pi1)
PERFILES = ("gris", "r", "g", "b")
ESCALA = 25.4 / 600.0                                # el tamaño de píxel con que se mide a 600 dpi

COLUMNAS_DATO = (
    "fecha", "serie_fuente", "user", "imagen", "imagen_nombre", "imagen_md5", "dpi", "tamano_pixel_mm",
    "puntos", "parametros", "version_algoritmo",
    "estado_gris", "desfase_gris_px", "desfase_gris_mm", "incertidumbre_gris_px", "dispersion_gris_px", "filas_gris",
    "estado_r", "desfase_r_px", "desfase_r_mm",
    "estado_g", "desfase_g_px", "desfase_g_mm",
    "estado_b", "desfase_b_px", "desfase_b_mm",
    "lado_transito", "tolerancia_mm", "observaciones",
    # B.5 (16-10): las 14 columnas aditivas (las medidas de R, G y B y `capa_reportada`); en una base nueva van ANTES de `activo`
    "incertidumbre_r_px", "incertidumbre_g_px", "incertidumbre_b_px", "dispersion_r_px", "dispersion_g_px", "dispersion_b_px",
    "filas_r", "filas_g", "filas_b", "media_r_px", "media_g_px", "media_b_px", "media_gris_px", "capa_reportada",
)
OBLIGATORIAS = ("fecha", "imagen", "puntos", "parametros", "version_algoritmo")

INSERT_MINIMO = (f"INSERT INTO {TABLA} (fecha, serie_fuente, imagen, puntos, parametros, version_algoritmo) "
                 "VALUES (?, ?, ?, ?, ?, ?)")


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield conexion
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def bd_con_indice(bd_temporal, tmp_path):
    """Una BD nueva con el índice único parcial ya creado (lo crea `crear_indices`, que llaman la herramienta de
    migración y los tests; no corre al abrir la app)."""
    bd_temporal.con.close()
    assert crear_indices(str(tmp_path / "test.db"))[TABLA] == "creado"
    Conexion._instance = None
    con = Conexion().con
    yield con
    con.close()
    Conexion._instance = None


@pytest.fixture(scope="module")
def valores_reales():
    """Lo que el motor entrega de verdad para guardar, sobre la placa real: es el PRODUCTOR de las columnas."""
    gris, color, dpi, _ = motor.leer_imagen((DATOS / "braqui_00.jpeg").read_bytes())
    return motor.valores_medidos(motor.analizar(gris, color, dpi, CLICS_PLACA_REAL))


@pytest.fixture(scope="module")
def valores_sin_escala():
    """El mismo análisis con una resolución 'otra' declarada (300 dpi): hay píxeles y no hay milímetros."""
    gris, color, _, _ = motor.leer_imagen((DATOS / "braqui_00.jpeg").read_bytes())
    return motor.valores_medidos(motor.analizar(gris, color, 300.0, CLICS_PLACA_REAL))


def _columnas(con, tabla=TABLA):
    return [c[1] for c in con.execute(f"PRAGMA table_info('{tabla}')").fetchall()]


def _fila(**cambios):
    """Una fila mínima válida (solo lo obligatorio y lo que no entra en los CHECK); `cambios` la ajusta."""
    fila = {"fecha": "2026-06-26", "serie_fuente": "24-05-9498-003-060526-13659-19", "user": "Fisico de prueba",
            "imagen": b"\xff\xd8\xff bytes de una imagen de prueba", "imagen_nombre": "braqui_00.jpeg",
            "imagen_md5": "0" * 32, "dpi": 600.0, "puntos": "[[191, 377], [190, 56]]", "parametros": "{}",
            "version_algoritmo": "PI-1", "tolerancia_mm": 1.0}
    fila.update(cambios)
    return fila


def _insertar(con, fila):
    columnas = ", ".join(fila)
    marcas = ", ".join("?" * len(fila))
    con.execute(f"INSERT INTO {TABLA} ({columnas}) VALUES ({marcas})", list(fila.values()))


def _censo_de_filas(ruta):
    con = sqlite3.connect(ruta)
    try:
        tablas = [t[0] for t in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
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

    def test_activo_queda_al_final_fisico(self, bd_temporal):
        """DP-80: ALTER TABLE ADD COLUMN agrega siempre al final físico. La tabla nace SIN `activo` y
        `_asegurar_activo_bloque_qc` lo agrega en el mismo arranque: queda como la última columna, igual que en una BD
        ya desplegada."""
        assert _columnas(bd_temporal.con)[-1] == "activo"

    @pytest.mark.parametrize("columna", OBLIGATORIAS)
    def test_las_columnas_obligatorias_no_admiten_null(self, columna, bd_temporal):
        fila = _fila()
        del fila[columna]
        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
            _insertar(bd_temporal.con, fila)

    def test_activo_nace_en_uno(self, bd_temporal):
        _insertar(bd_temporal.con, _fila())
        assert bd_temporal.con.execute(f"SELECT activo FROM {TABLA}").fetchone()[0] == 1

    def test_cada_valor_que_el_motor_entrega_tiene_su_columna(self, bd_temporal, valores_reales, valores_sin_escala):
        """El productor (`valores_medidos`, PI.1b) y la tabla no pueden separarse: toda clave que el motor entrega para
        guardar es una columna, con el mismo nombre."""
        columnas = set(_columnas(bd_temporal.con))
        for nombre, valores in (("con escala", valores_reales), ("sin escala", valores_sin_escala)):
            assert valores and set(valores) <= columnas, (nombre, sorted(set(valores) - columnas))

    def test_ida_y_vuelta_de_lo_que_el_motor_entrega(self, bd_temporal, valores_reales):
        """Lo que sale del motor entra a la tabla (los CHECK lo aceptan: mm = px x escala sin redondear) y vuelve igual."""
        con = bd_temporal.con
        _insertar(con, _fila(**valores_reales))
        con.row_factory = sqlite3.Row
        guardado = con.execute(f"SELECT * FROM {TABLA}").fetchone()
        assert {k: guardado[k] for k in valores_reales} == valores_reales
        assert valores_reales["tamano_pixel_mm"] == ESCALA and valores_reales["desfase_gris_mm"] is not None

    def test_lo_que_el_motor_entrega_sin_escala_tambien_entra(self, bd_temporal, valores_sin_escala):
        """Resolución 'otra' declarada: píxeles sí, milímetros no, y sin `tamano_pixel_mm` (la fila vale igual)."""
        assert valores_sin_escala["tamano_pixel_mm"] is None and valores_sin_escala["desfase_gris_px"] is not None
        assert all(valores_sin_escala[f"desfase_{p}_mm"] is None for p in PERFILES)
        _insertar(bd_temporal.con, _fila(**valores_sin_escala))

    def test_segunda_apertura_no_falla_ni_duplica(self, bd_temporal, monkeypatch, tmp_path):
        """CREATE TABLE IF NOT EXISTS: idempotente, sin importar cuántas veces arranque la app sobre la misma BD."""
        ruta = str(tmp_path / "test.db")
        cols_1 = _columnas(bd_temporal.con)
        assert cols_1, f"{TABLA}: no existe (sin CREATE TABLE)"           # sin esto, dos listas vacias pasarian
        bd_temporal.con.close()
        Conexion._instance = None
        _abrir_con_la_app(ruta, monkeypatch)
        con2 = sqlite3.connect(ruta)
        try:
            cols_2 = _columnas(con2)
        finally:
            con2.close()
        assert cols_1 == cols_2


class TestElCheckDeLosMilimetros:
    """Un CHECK por perfil. Cada caso inválido cambia SOLO las columnas de un perfil, así que solo el CHECK de ese
    perfil puede rechazarlo: si falta (o está flojo) la fila entra y el test falla."""

    @pytest.mark.parametrize("perfil", PERFILES)
    def test_acepta_milimetros_que_son_exactamente_pixeles_por_la_escala(self, perfil, bd_temporal):
        _insertar(bd_temporal.con, _fila(**{"tamano_pixel_mm": ESCALA, f"desfase_{perfil}_px": -8.553322,
                                            f"desfase_{perfil}_mm": -8.553322 * ESCALA}))

    @pytest.mark.parametrize("perfil", PERFILES)
    def test_acepta_un_perfil_que_no_se_midio(self, perfil, bd_temporal):
        _insertar(bd_temporal.con, _fila(**{"tamano_pixel_mm": ESCALA, f"estado_{perfil}": "no medible: la linea tapa",
                                            f"desfase_{perfil}_px": None, f"desfase_{perfil}_mm": None}))

    @pytest.mark.parametrize("perfil", PERFILES)
    def test_acepta_pixeles_sin_escala(self, perfil, bd_temporal):
        _insertar(bd_temporal.con, _fila(**{"tamano_pixel_mm": None, f"desfase_{perfil}_px": -8.55,
                                            f"desfase_{perfil}_mm": None}))

    INVALIDAS = {
        "milimetros con otra escala (300 dpi) aunque la columna diga 600": dict(
            tamano_pixel_mm=ESCALA, px=-8.55, mm=-8.55 * (25.4 / 300.0)),
        "milimetros sin pixeles": dict(tamano_pixel_mm=ESCALA, px=None, mm=-0.36),
        "pixeles sin milimetros (con escala)": dict(tamano_pixel_mm=ESCALA, px=-8.55, mm=None),
        "milimetros redondeados": dict(tamano_pixel_mm=ESCALA, px=-8.553322, mm=round(-8.553322 * ESCALA, 2)),
        "milimetros sin escala": dict(tamano_pixel_mm=None, px=-8.55, mm=-0.36),
    }

    @pytest.mark.parametrize("caso", sorted(INVALIDAS))
    @pytest.mark.parametrize("perfil", PERFILES)
    def test_rechaza_la_fila_inconsistente(self, perfil, caso, bd_temporal):
        c = self.INVALIDAS[caso]
        fila = _fila(**{"tamano_pixel_mm": c["tamano_pixel_mm"], f"desfase_{perfil}_px": c["px"],
                        f"desfase_{perfil}_mm": c["mm"]})
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            _insertar(bd_temporal.con, fila)
        assert bd_temporal.con.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0] == 0

    def test_un_perfil_malo_no_se_salva_por_tener_otros_buenos(self, bd_temporal):
        """Cada perfil se juzga por separado: el gris bien medido no tapa un rojo con milímetros que no cuadran."""
        fila = _fila(tamano_pixel_mm=ESCALA, desfase_gris_px=-8.55, desfase_gris_mm=-8.55 * ESCALA,
                     desfase_r_px=3.8, desfase_r_mm=99.0)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            _insertar(bd_temporal.con, fila)


class TestEstaEnElContrato:
    def test_esta_en_tablas_anulables(self):
        assert TABLA in TABLAS_ANULABLES

    def test_es_raiz_propia_sin_clave_foranea(self, bd_temporal):
        """Sin FK (el enlace con el cambio de fuente es por fecha) => raíz propia de QC, no hija de ninguna."""
        assert TABLA in RAICES_QC
        assert bd_temporal.con.execute(f"PRAGMA foreign_key_list('{TABLA}')").fetchall() == []
        assert RAICES_QC <= TABLAS_ANULABLES

    def test_clave_de_bloque_declarada_y_sus_columnas_existen(self, bd_temporal):
        assert CLAVES_INDICE[TABLA] == CLAVE
        assert set(CLAVE) <= set(_columnas(bd_temporal.con))


class TestElIndiceUnicoParcial:
    def test_crear_indices_lo_crea_y_es_idempotente(self, bd_temporal, tmp_path):
        ruta = str(tmp_path / "test.db")
        bd_temporal.con.close()
        assert crear_indices(ruta)[TABLA] == "creado"
        assert crear_indices(ruta)[TABLA] == "ya existía"
        con = sqlite3.connect(ruta)
        try:
            sql = con.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
                              (nombre_indice(TABLA),)).fetchone()[0]
        finally:
            con.close()
        assert "UNIQUE" in sql.upper() and '"fecha"' in sql and "activo" in sql      # único y PARCIAL (solo vigentes)

    def test_dos_vigentes_de_la_misma_fecha_se_rechazan(self, bd_con_indice):
        _insertar(bd_con_indice, _fila())
        bd_con_indice.commit()
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            _insertar(bd_con_indice, _fila(imagen=b"otra"))

    def test_la_serie_no_forma_parte_de_la_clave(self, bd_con_indice):
        """El cambio de fuente se identifica por la fecha: otra serie el mismo día NO permite una segunda prueba
        vigente (si la serie fuera clave, `serie_fuente` NULL dejaría pasar duplicados: NULL no choca en un UNIQUE)."""
        _insertar(bd_con_indice, _fila(serie_fuente=None))
        bd_con_indice.commit()
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            _insertar(bd_con_indice, _fila(serie_fuente=None))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            _insertar(bd_con_indice, _fila(serie_fuente="otra serie"))

    def test_fechas_distintas_conviven(self, bd_con_indice):
        for fecha in ("2026-01-10", "2026-04-15", "2026-06-26"):
            _insertar(bd_con_indice, _fila(fecha=fecha))
        bd_con_indice.commit()
        assert bd_con_indice.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0] == 3

    def test_las_anuladas_no_cuentan_para_el_indice(self, bd_con_indice):
        """Es PARCIAL: el historial (activo = 0) puede repetir fecha; solo UNA vigente por fecha."""
        for _ in range(3):
            _insertar(bd_con_indice, _fila(activo=0))
        _insertar(bd_con_indice, _fila(activo=1))
        bd_con_indice.commit()
        assert bd_con_indice.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0] == 4

    def test_reemplazar_bloque_anula_la_vigente_e_inserta_la_nueva(self, bd_con_indice):
        """La garantía titular del contrato, por el primitivo REAL: guardar de nuevo la misma fecha anula la vigente
        (activo = 0, queda como historial) e inserta la nueva con `id` nuevo; una sola fila de auditoría por reemplazo
        (DA-52). Es lo que hará `guardar` (PI.3)."""
        cur = bd_con_indice.cursor()
        clave = [("fecha", "2026-06-26")]
        reemplazar_bloque(cur, TABLA, clave, INSERT_MINIMO, [("2026-06-26", "A", b"1", "[]", "{}", "PI-1")],
                          "Fisico de prueba")
        primera = cur.lastrowid
        reemplazar_bloque(cur, TABLA, clave, INSERT_MINIMO, [("2026-06-26", "A", b"2", "[]", "{}", "PI-1")],
                          "Fisico de prueba")
        segunda = cur.lastrowid
        bd_con_indice.commit()
        assert primera != segunda
        assert bd_con_indice.execute(f"SELECT id, activo, imagen FROM {TABLA} ORDER BY id").fetchall() == [
            (primera, 0, b"1"), (segunda, 1, b"2")]
        assert bd_con_indice.execute(
            "SELECT COUNT(*) FROM audit_log WHERE tabla = ?", (TABLA,)).fetchone()[0] == 2


class TestLaCapaDeDatosDelVisorDeAnulados:
    """§6.4-4 del plan: el visor no se toca. Lo que se comprueba aquí es su CAPA DE DATOS (`services/visor_anulados.py`),
    que deriva las secciones de `RAICES_QC`: la tabla nueva aparece sola y se lee con su imagen sin error. NO se comprueba
    (porque no es cierto) el botón de sección de la PANTALLA: `ui/paginasGuia/visor_anulados.py` tiene una lista fija de
    7 raíces y no muestra ni `referencias_qc` ni esta tabla (DP-144; zona ámbar, sin autorización: queda como deuda)."""

    def test_la_seccion_nueva_aparece_sin_error(self, bd_temporal):
        secciones = visor.secciones()
        assert TABLA in secciones and secciones[TABLA] == [TABLA]       # raíz propia, sin hijas

    def test_lista_vigentes_y_anuladas_con_su_imagen(self, bd_con_indice):
        _insertar(bd_con_indice, _fila(imagen=b"\xff\xd8" + b"x" * 1000, activo=0))
        _insertar(bd_con_indice, _fila(imagen=b"\xff\xd8" + b"y" * 1000, activo=1))
        bd_con_indice.commit()
        columnas, filas = visor.filas_de(TABLA)
        assert "activo" not in columnas and "imagen" in columnas and "fecha" in columnas
        assert sorted(f["estado"] for f in filas) == ["anulado", "vigente"]
        _, encontradas = visor.filas_de(TABLA, "2026-06-26")             # la búsqueda recorre también el BLOB sin error
        assert len(encontradas) == 2


# ---------------------------------------------------------------------------
# Ensayo sobre COPIA de las BD reales (protocolo de DA-80/CLAUDE.md)
# ---------------------------------------------------------------------------

BD_REALES = [BD_QA, BD_REBUILD_14_09, BD_REBUILD_21_09, BD_A_AJUSTAR]


@pytest.mark.parametrize("origen", BD_REALES, ids=lambda p: p.name)
def test_ensayo_sobre_copia_de_bd_real(origen, tmp_path, monkeypatch):
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")

    ruta = str(tmp_path / "copia_real.db")
    shutil.copy(origen, ruta)

    censo_antes = _censo_de_filas(ruta)
    assert TABLA not in censo_antes, "la BD de referencia ya trae la tabla: el ensayo no probaría la creación"
    con = sqlite3.connect(ruta)
    fk_antes = len(con.execute("PRAGMA foreign_key_check").fetchall())
    con.close()

    _abrir_con_la_app(ruta, monkeypatch)

    con = sqlite3.connect(ruta)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        fk_despues = len(con.execute("PRAGMA foreign_key_check").fetchall())
        assert _columnas(con)[-1] == "activo"
    finally:
        con.close()

    assert fk_despues <= fk_antes, f"foreign_key_check AUMENTÓ: {fk_antes} -> {fk_despues}"

    censo_despues = _censo_de_filas(ruta)
    assert censo_despues.get(TABLA) == 0                       # la tabla nueva aparece, vacía -- nada más cambia
    for tabla, n in censo_antes.items():
        assert censo_despues.get(tabla) == n, f"el censo de filas de '{tabla}' cambió: {n} -> {censo_despues.get(tabla)}"

    _abrir_con_la_app(ruta, monkeypatch)                       # segunda corrida idempotente sobre la misma copia real
    assert _censo_de_filas(ruta) == censo_despues


@pytest.mark.parametrize("origen", BD_REALES, ids=lambda p: p.name)
def test_crear_indices_sobre_copia_de_bd_real(origen, tmp_path, monkeypatch):
    """El índice UNIQUE también se ensaya sobre copia real: la tabla es nueva (no puede traer duplicados), y la prueba
    dice con su motivo exacto si alguna BD lo impidiera."""
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")

    ruta = str(tmp_path / "copia_real.db")
    shutil.copy(origen, ruta)
    _abrir_con_la_app(ruta, monkeypatch)

    resultado = crear_indices(ruta)
    assert resultado[TABLA] == "creado", resultado[TABLA]
