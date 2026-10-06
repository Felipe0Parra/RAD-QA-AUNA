"""GI.0 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, D8 y D9): estructura de las tablas de imagenes de Catphan.

CAUSA: (a) DP-41 -- `tamaño_pixel` no declaraba `error_pct` y el escritor la inserta: en una BD NUEVA guardar
"Tamaño de pixel" fallaba siempre y `guardar_prueba_completa_catphan` devolvia `None` sin decir por que (las 5 BD de
referencia la tienen). (b) D9 -- `resolucion_espacial.lp_mm_maximo` y `resolucion_espacial_regiones.lp_mm` guardan lp/cm
(D3: el formato oficial y el fantoma lo dan asi; `Analisis_Catphan_TAC` interpola sobre `roi_settings[...]["lp/cm"]`): el
nombre mentia sobre la unidad.

GARANTIAS, una por bloque:

  1. BASE NUEVA -- nace con `error_pct` y con las dos columnas en lp/cm; "Tamaño de pixel" se guarda y se relee.
  2. LAS CINCO BD DE REFERENCIA (sobre COPIA) -- el renombrado es en sitio: ningun dato cambia de valor (huella
     SHA-256 de TODAS las tablas), el censo de filas es identico, `integrity_check = ok`, `foreign_key_check` no
     aumenta (109 / 116) y una segunda corrida no cambia nada.
  3. HERRAMIENTA DE MIGRACION -- usa la misma implementacion (corre `Conexion()`), no deja una columna vacia al lado
     y su informe NOMBRA el renombrado, tambien en el ensayo (dry-run).
  4. CASOS FABRICADOS -- con las dos columnas presentes no toca nada; con SQLite < 3.25 no renombra y avisa; una BD
     vieja sin `error_pct` y con los nombres viejos queda al dia por el camino real de la app.
  5. DE PUNTA A PUNTA -- analisis -> mapeador -> escritor -> BD -> lector -> PDF con las claves nuevas.
  6. NINGUN NOMBRE MIENTE -- tripwires por AST: ninguna cadena de produccion nombra `lp_mm`/`lp_mm_maximo`/
     `mtf_lp_mm` salvo la lista del renombrado; los DDL de las tres tablas dicen lp/cm y declaran `error_pct`.

FRONTERA con GI.1/GI.2/GI.3 (lo que esta prueba NO fija a proposito): que el mapeador lea `'lp/cm'` del analisis (GI.1),
la clave por region `'lp/mm'` del diccionario reconstruido y la unidad de las filas viejas (GI.2), y los rotulos del
PDF y de "Ver tabla" (GI.3).

Nunca se conecta a una BD de referencia: se copia a un temporal primero.
"""
import ast
import hashlib
import os
import pathlib
import re
import shutil
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from _bd_referencia import (BD_A_AJUSTAR, BD_QA, BD_REBUILD_14_09, BD_REBUILD_21_09, CARPETA_BD)

RAIZ = pathlib.Path(__file__).resolve().parent.parent

BD_PRIMITIVA = CARPETA_BD / "BaseDatosQA(Primitiva-01).db"
CINCO = [BD_QA, BD_REBUILD_14_09, BD_A_AJUSTAR, BD_PRIMITIVA, BD_REBUILD_21_09]
# Linea base de huerfanos de FK medida el 06-10 sobre las copias (DA-43: 109 en produccion, 116 en las primitivas).
FK_LINEA_BASE = {BD_QA.name: 109, BD_REBUILD_14_09.name: 109, BD_A_AJUSTAR.name: 116,
                 BD_PRIMITIVA.name: 116, BD_REBUILD_21_09.name: 109}

TABLA_ESP, TABLA_REG, TABLA_PX = "resolucion_espacial", "resolucion_espacial_regiones", "tamaño_pixel"
RENOMBRADAS = {TABLA_ESP: ("lp_mm_maximo", "lp_cm_maximo"), TABLA_REG: ("lp_mm", "lp_cm")}
COLUMNAS_PX = ["id_prueba", "valor_teorico_dicom", "X", "Y", "diferencia_x", "diferencia_y", "error_pct", "activo"]
COLUMNAS_ESP = ["id_prueba", "regiones_analizadas", "regiones_exitosas", "lp_cm_maximo", "ultima_region_exitosa",
                "gap_size_minimo_cm", "num_picos_totales", "mtf_10_pct", "mtf_20_pct", "mtf_50_pct", "activo"]
COLUMNAS_REG = ["id", "id_prueba", "region_nombre", "lp_cm", "peak_mean", "valley_mean", "gap_size_cm",
                "n_peaks_used", "n_valleys_used", "status", "activo"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# ayudas
# ---------------------------------------------------------------------------

def _requerir(origen):
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")


def _copiar(origen, tmp_path, nombre="copia.db"):
    _requerir(origen)
    ruta = str(tmp_path / nombre)
    shutil.copy(origen, ruta)
    return ruta


def _abrir_con_la_app(ruta, monkeypatch):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    con = Conexion()
    con.con.close()
    Conexion._instance = None


def _cols(ruta_o_con, tabla):
    con = sqlite3.connect(ruta_o_con) if isinstance(ruta_o_con, str) else ruta_o_con
    try:
        return [f[1] for f in con.execute(f"PRAGMA table_info('{tabla}')")]
    finally:
        if isinstance(ruta_o_con, str):
            con.close()


def _tablas(con):
    return [t[0] for t in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _huella_filas(con, tabla, columnas=None):
    """(n, sha256) del contenido de la tabla, fila por fila y en el orden fisico; los BLOB entran por sus bytes."""
    cols = "*" if columnas is None else ", ".join(f'"{c}"' for c in columnas)
    try:
        cursor = con.execute(f'SELECT {cols} FROM "{tabla}" ORDER BY rowid')
    except sqlite3.OperationalError:                       # tabla WITHOUT ROWID: ya viene en el orden de su clave
        cursor = con.execute(f'SELECT {cols} FROM "{tabla}"')
    h, n = hashlib.sha256(), 0
    for fila in cursor:
        for valor in fila:
            h.update(valor if isinstance(valor, bytes) else repr(valor).encode())
            h.update(b"\x1f")
        h.update(b"\x1e")
        n += 1
    return n, h.hexdigest()


def _huella_de_todo(con):
    return {t: _huella_filas(con, t) for t in _tablas(con)}


def _censo(ruta):
    con = sqlite3.connect(ruta)
    try:
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in _tablas(con)}
    finally:
        con.close()


def _fk(ruta_o_con):
    con = sqlite3.connect(ruta_o_con) if isinstance(ruta_o_con, str) else ruta_o_con
    try:
        return len(con.execute("PRAGMA foreign_key_check").fetchall())
    finally:
        if isinstance(ruta_o_con, str):
            con.close()


def _integridad(ruta):
    con = sqlite3.connect(ruta)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def _con_nombres_viejos(ruta):
    """Devuelve la BD a como la tienen las ya desplegadas: columnas con los nombres viejos y SIN `error_pct`."""
    con = sqlite3.connect(ruta)
    try:
        for tabla, (vieja, nueva) in RENOMBRADAS.items():
            con.execute(f'ALTER TABLE "{tabla}" RENAME COLUMN "{nueva}" TO "{vieja}"')
        con.execute(f'ALTER TABLE "{TABLA_PX}" DROP COLUMN error_pct')
        con.commit()
    finally:
        con.close()


requiere_drop_column = pytest.mark.skipif(sqlite3.sqlite_version_info < (3, 35, 0),
                                          reason="SQLite < 3.35: sin DROP COLUMN para fabricar la BD vieja")


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "nueva.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _crear_control(ruta, equipo="Tomógrafo", fecha="06/2026"):
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)", (equipo, fecha))
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


def _guardar(sesion, categorias, **kw):
    from data.ManejoDatos.catphan_TAC.catphan_db import guardar_prueba_completa_catphan
    base = dict(user_id="fisico1", fecha="2026-06-01", equipo="Tomógrafo", kv=120, ma=200, espesor_corte=2.0,
                resultados_por_categoria=categorias, id_sesion=sesion, tam_px_teorico=1.074)
    base.update(kw)
    return guardar_prueba_completa_catphan(**base)


# Forma del resultado real de `Analisis_Catphan_TAC.resolucion_espacial`, con las claves de GI.0 y con TODOS los numeros distintos entre si
# (regiones_analizadas 6, regiones_exitosas 5, lp_cm_maximo 10.0, num_picos 12, MTF 5.2/4.1/3.1, un lp/cm, un pico y un gap distintos por
# region...): un cruce de columnas al escribir o al leer SE NOTA. Cada region trae `'lp/cm'` (lo que produce el analisis) Y `'lp/mm'` con el
# MISMO valor: hoy el mapeador lee `'lp/mm'` (GI.1 lo cambia a `'lp/cm'`), y asi la prueba verifica el camino del VALOR de las columnas
# renombradas sin depender de cual de las dos claves lea.
RESULTADO_ESPACIAL = {
    "region_results": {
        f"region {n}": {"lp/cm": 2.0 * n, "lp/mm": 2.0 * n, "peak_mean": 100.0 + n, "valley_mean": 50.0 + n,
                        "gap_size_cm": round(0.5 / n, 3), "n_peaks_used": 3 + n, "n_valleys_used": 2 + n,
                        "status": "OK" if n <= 5 else "Picos insuficientes"}
        for n in range(1, 7)
    },
    "mtf_lp_cm": {"10": 5.2, "20": 4.1, "50": 3.1},
    "num_picos": 12,
    "resolucion_limite": {"ultima_region": "region 5", "lp_cm_maximo": 10.0, "gap_size_cm": 0.1},
    "imagen_analisis": None,
}


# ---------------------------------------------------------------------------
# 1. BASE NUEVA
# ---------------------------------------------------------------------------

def test_bd_nueva_declara_error_pct_y_las_dos_columnas_en_lp_cm(tmp_path, monkeypatch):
    ruta = str(tmp_path / "nueva.db")
    _abrir_con_la_app(ruta, monkeypatch)
    assert _cols(ruta, TABLA_PX) == COLUMNAS_PX, "tamaño_pixel debe declarar error_pct, como las 5 BD de referencia"
    assert _cols(ruta, TABLA_ESP) == COLUMNAS_ESP
    assert _cols(ruta, TABLA_REG) == COLUMNAS_REG
    con = sqlite3.connect(ruta)
    try:
        tipo = {f[1]: (f[2], f[3]) for f in con.execute(f"PRAGMA table_info('{TABLA_PX}')")}
    finally:
        con.close()
    assert tipo["error_pct"] == ("REAL", 0), "error_pct es REAL y admite NULL (el escritor guarda None si no hay teorico)"


def test_tamano_de_pixel_se_guarda_y_se_relee_en_una_bd_nueva(bd_temporal):
    """DP-41: hoy el guardado falla con `no column named error_pct`, el `except` de
    `guardar_prueba_completa_catphan` lo traga y la funcion devuelve None sin que nadie se entere."""
    sesion = _crear_control(bd_temporal)
    resultado = _guardar(sesion, {"tamano_pixel": {"X": 1.08, "Y": 1.06}})
    assert resultado is not None, "guardar 'Tamaño de pixel' en una BD nueva debe entrar"
    con = sqlite3.connect(bd_temporal)
    try:
        fila = con.execute(f'SELECT valor_teorico_dicom, X, Y, error_pct FROM "{TABLA_PX}"').fetchone()
    finally:
        con.close()
    assert fila[0] == 1.074 and fila[1] == 1.08 and fila[2] == 1.06
    # |1.074 - 1.07| / 1.074 * 100 = 0.372 (el escritor redondea a 3 decimales)
    assert abs(fila[3] - 0.372) < 1e-9


def test_el_visor_de_tamano_de_pixel_pide_columnas_que_existen(bd_temporal, monkeypatch):
    import data.ManejoDatos.load as load_mod
    config = {}
    monkeypatch.setattr(load_mod, "_mostrar_tabla_generica", lambda parent, id_control, cfg: config.update(cfg))
    load_mod.mostrar_tamaño_pixel(None, 1)
    columnas = [c for _, c in config["columnas"]]
    assert "error_pct" in columnas
    con = sqlite3.connect(bd_temporal)
    try:
        con.execute(f'SELECT {", ".join(columnas)} FROM "{config["tabla"]}"').fetchall()
    finally:
        con.close()


def test_el_visor_de_resolucion_espacial_pide_la_columna_en_lp_cm(bd_temporal, monkeypatch):
    """`mostrar_resolucion_espacial` consulta la COLUMNA por nombre: sin renombrarla aqui daria `no such column`.
    El ROTULO ('LP/mm Maximo') es de GI.3 y esta prueba no lo fija."""
    import data.ManejoDatos.load as load_mod
    config = {}
    monkeypatch.setattr(load_mod, "_mostrar_tabla_generica", lambda parent, id_control, cfg: config.update(cfg))
    load_mod.mostrar_resolucion_espacial(None, 1)
    columnas = [c for _, c in config["columnas"]]
    assert "lp_cm_maximo" in columnas and "lp_mm_maximo" not in columnas
    con = sqlite3.connect(bd_temporal)
    try:
        con.execute(f'SELECT {", ".join(columnas)} FROM "{config["tabla"]}"').fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 2. LAS CINCO BD DE REFERENCIA (sobre copia)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("origen", CINCO, ids=lambda p: p.name)
def test_la_funcion_renombra_en_sitio_sin_cambiar_un_solo_dato(origen, tmp_path):
    """Sobre la copia, SIN pasar por `Conexion()` (que migraria ademas otras cosas): lo unico que cambia es el
    nombre de dos columnas. Huella SHA-256 de TODAS las tablas idéntica."""
    from data.ManejoDatos.conection import (
        RENOMBRES_DE_COLUMNAS, RENOMBRE_HECHO, RENOMBRE_YA_HECHO, _asegurar_columna, _asegurar_renombre_columna)
    ruta = _copiar(origen, tmp_path)
    con = sqlite3.connect(ruta)
    try:
        huella_antes = _huella_de_todo(con)
        cols_antes = {t: _cols(con, t) for t in _tablas(con)}
        fk_antes = _fk(con)
        assert fk_antes == FK_LINEA_BASE[origen.name], "la linea base de FK de la copia ya no es la medida"

        cur = con.cursor()
        estados = [_asegurar_renombre_columna(cur, *r) for r in RENOMBRES_DE_COLUMNAS]
        _asegurar_columna(cur, TABLA_PX, "error_pct", "REAL")      # las 5 ya la tienen: no debe tocar nada
        con.commit()

        assert estados == [RENOMBRE_HECHO, RENOMBRE_HECHO]
        assert _huella_de_todo(con) == huella_antes, "el renombrado cambio contenido de alguna tabla"
        esperado = {t: list(c) for t, c in cols_antes.items()}
        for tabla, (vieja, nueva) in RENOMBRADAS.items():
            esperado[tabla] = [nueva if c == vieja else c for c in cols_antes[tabla]]
        assert {t: _cols(con, t) for t in _tablas(con)} == esperado, "solo deben cambiar los dos nombres"
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert _fk(con) == fk_antes, "foreign_key_check no puede aumentar"

        estados_2 = [_asegurar_renombre_columna(cur, *r) for r in RENOMBRES_DE_COLUMNAS]
        assert estados_2 == [RENOMBRE_YA_HECHO, RENOMBRE_YA_HECHO], "la segunda corrida debe ser un no-op"
        assert _huella_de_todo(con) == huella_antes
    finally:
        con.close()


@pytest.mark.parametrize("origen", CINCO, ids=lambda p: p.name)
def test_al_abrir_con_la_app_las_columnas_quedan_en_lp_cm_con_los_mismos_datos(origen, tmp_path, monkeypatch):
    ruta = _copiar(origen, tmp_path)
    con = sqlite3.connect(ruta)
    try:
        previas = {t: _cols(con, t) for t in (TABLA_ESP, TABLA_REG, TABLA_PX)}
        huella_antes = {t: _huella_filas(con, t, previas[t]) for t in previas}
    finally:
        con.close()
    censo_antes = _censo(ruta)

    _abrir_con_la_app(ruta, monkeypatch)

    assert _cols(ruta, TABLA_PX) == COLUMNAS_PX
    assert _cols(ruta, TABLA_ESP) == COLUMNAS_ESP
    assert _cols(ruta, TABLA_REG) == COLUMNAS_REG
    con = sqlite3.connect(ruta)
    try:
        for tabla, columnas in previas.items():
            nuevas = [RENOMBRADAS.get(tabla, ("", ""))[1] if c == RENOMBRADAS.get(tabla, ("", ""))[0] else c
                      for c in columnas]
            assert _huella_filas(con, tabla, nuevas) == huella_antes[tabla], \
                f"'{tabla}' cambio de contenido al abrir con la app"
    finally:
        con.close()
    assert _integridad(ruta) == "ok"
    assert _fk(ruta) == FK_LINEA_BASE[origen.name], "foreign_key_check no puede aumentar"
    censo_despues = _censo(ruta)
    for tabla, n in censo_antes.items():
        assert censo_despues.get(tabla) == n, f"el censo de '{tabla}' cambio: {n} -> {censo_despues.get(tabla)}"

    _abrir_con_la_app(ruta, monkeypatch)                   # segunda corrida
    assert _cols(ruta, TABLA_ESP) == COLUMNAS_ESP and _cols(ruta, TABLA_REG) == COLUMNAS_REG
    assert _censo(ruta) == censo_despues
    con = sqlite3.connect(ruta)
    try:
        for tabla, columnas in {TABLA_ESP: COLUMNAS_ESP, TABLA_REG: COLUMNAS_REG, TABLA_PX: COLUMNAS_PX}.items():
            assert _huella_filas(con, tabla, columnas)[0] == censo_antes[tabla]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 3. HERRAMIENTA DE MIGRACION
# ---------------------------------------------------------------------------

def _lineas_de_renombrado(salida):
    return [l for l in salida.splitlines() if "renombrad" in l.lower()]


def test_la_herramienta_renombra_lo_informa_y_no_deja_columna_vacia_al_lado(tmp_path, capsys):
    from scripts.migrar_bd_a_estandar import migrar
    ruta = _copiar(BD_REBUILD_21_09, tmp_path)
    con = sqlite3.connect(ruta)
    try:
        previas = {t: _cols(con, t) for t in (TABLA_ESP, TABLA_REG)}
        huella_antes = {t: _huella_filas(con, t, previas[t]) for t in previas}
    finally:
        con.close()

    migrar(ruta, aplicar=True)
    salida = capsys.readouterr().out

    lineas = _lineas_de_renombrado(salida)
    for tabla, (vieja, nueva) in RENOMBRADAS.items():
        assert any(tabla in l and vieja in l and nueva in l for l in lineas), \
            f"el informe no nombra el renombrado de {tabla}.{vieja} -> {nueva}:\n" + "\n".join(lineas)
    # el renombrado no se cuenta ademas como columna NUEVA (sugeriria una columna vacia al lado)
    for l in salida.splitlines():
        if "columna(s) nueva(s)" in l:
            assert "lp_cm" not in l, f"se informo como columna nueva lo que es un renombrado: {l}"
    assert _cols(ruta, TABLA_ESP) == COLUMNAS_ESP and _cols(ruta, TABLA_REG) == COLUMNAS_REG
    con = sqlite3.connect(ruta)
    try:
        for tabla, columnas in previas.items():
            nuevas = [RENOMBRADAS[tabla][1] if c == RENOMBRADAS[tabla][0] else c for c in columnas]
            assert _huella_filas(con, tabla, nuevas) == huella_antes[tabla]
    finally:
        con.close()
    assert _integridad(ruta) == "ok"


def test_el_ensayo_dry_run_tambien_nombra_el_renombrado_y_no_toca_el_original(tmp_path, capsys):
    from scripts.migrar_bd_a_estandar import migrar
    ruta = _copiar(BD_REBUILD_14_09, tmp_path)
    md5_antes = hashlib.md5(pathlib.Path(ruta).read_bytes()).hexdigest()

    migrar(ruta, aplicar=False)
    salida = capsys.readouterr().out

    lineas = _lineas_de_renombrado(salida)
    for tabla, (vieja, nueva) in RENOMBRADAS.items():
        assert any(tabla in l and vieja in l and nueva in l for l in lineas), \
            f"el dry-run no nombra el renombrado de {tabla}:\n" + "\n".join(lineas)
    assert hashlib.md5(pathlib.Path(ruta).read_bytes()).hexdigest() == md5_antes, "el dry-run modifico el original"
    assert "lp_mm_maximo" in _cols(ruta, TABLA_ESP), "el dry-run no debe renombrar nada en el archivo original"


def test_el_estado_de_los_renombres_distingue_los_casos_que_el_informe_debe_nombrar():
    """Las fotos del esquema (antes y despues) bastan para decir que paso con cada renombrado: hecho, dos columnas, sin
    renombrar (SQLite viejo) o nada que informar (la base ya estaba al dia)."""
    from scripts.migrar_bd_a_estandar import _estado_de_los_renombres
    esp, reg = TABLA_ESP, TABLA_REG
    vieja_esp, vieja_reg = {"id_prueba", "lp_mm_maximo"}, {"id", "lp_mm"}
    nueva_esp, nueva_reg = {"id_prueba", "lp_cm_maximo"}, {"id", "lp_cm"}
    antes = {esp: vieja_esp, reg: vieja_reg}

    assert _estado_de_los_renombres(antes, {esp: nueva_esp, reg: nueva_reg}) == [
        (esp, "lp_mm_maximo", "lp_cm_maximo", "renombrada"), (reg, "lp_mm", "lp_cm", "renombrada")]
    assert _estado_de_los_renombres({esp: nueva_esp, reg: nueva_reg}, {esp: nueva_esp, reg: nueva_reg}) == [], \
        "una base que ya tenia las columnas nuevas no debe aparecer en el informe"
    assert _estado_de_los_renombres({esp: vieja_esp, reg: nueva_reg},
                                    {esp: {"id_prueba", "lp_mm_maximo", "lp_cm_maximo"}, reg: nueva_reg}) == [
        (esp, "lp_mm_maximo", "lp_cm_maximo", "las dos")]
    assert _estado_de_los_renombres(antes, antes) == [
        (esp, "lp_mm_maximo", "lp_cm_maximo", "sin renombrar"), (reg, "lp_mm", "lp_cm", "sin renombrar")]
    assert _estado_de_los_renombres({}, {}) == [], "sin las tablas no hay nada que informar"
    assert _estado_de_los_renombres({esp: {"id_prueba", "LP_MM_MAXIMO"}, reg: nueva_reg}, {esp: nueva_esp, reg: nueva_reg}) == [
        (esp, "lp_mm_maximo", "lp_cm_maximo", "renombrada")], \
        "SQLite no distingue mayusculas: la columna vieja con otra capitalizacion tambien se informa"


# ---------------------------------------------------------------------------
# 4. CASOS FABRICADOS
# ---------------------------------------------------------------------------

def test_con_las_dos_columnas_presentes_no_toca_nada_y_lo_dice(bd_temporal, capsys):
    from data.ManejoDatos.conection import RENOMBRE_DOS_COLUMNAS, _asegurar_renombre_columna
    con = sqlite3.connect(bd_temporal)
    try:
        con.execute(f'ALTER TABLE "{TABLA_ESP}" ADD COLUMN lp_mm_maximo REAL')       # fabricada: la vieja junto a la nueva
        con.execute(f'INSERT INTO "{TABLA_ESP}" (id_prueba, lp_cm_maximo, lp_mm_maximo) VALUES (1, 4.0, 0.4)')
        con.commit()
        columnas_antes = _cols(con, TABLA_ESP)
        huella_antes = _huella_de_todo(con)

        estado = _asegurar_renombre_columna(con.cursor(), TABLA_ESP, "lp_mm_maximo", "lp_cm_maximo")

        assert estado == RENOMBRE_DOS_COLUMNAS
        assert _cols(con, TABLA_ESP) == columnas_antes
        assert _huella_de_todo(con) == huella_antes, "con las dos columnas presentes no puede tocar ningun dato"
    finally:
        con.close()
    salida = capsys.readouterr().out
    assert "lp_mm_maximo" in salida and "lp_cm_maximo" in salida, "debe informar cuales son las dos columnas"


def test_sin_ninguna_de_las_dos_columnas_o_sin_tabla_no_hace_nada(bd_temporal):
    from data.ManejoDatos.conection import RENOMBRE_NADA_QUE_RENOMBRAR, _asegurar_renombre_columna
    con = sqlite3.connect(bd_temporal)
    try:
        cur = con.cursor()
        assert _asegurar_renombre_columna(cur, "tabla_que_no_existe", "a", "b") == RENOMBRE_NADA_QUE_RENOMBRAR
        assert _asegurar_renombre_columna(cur, TABLA_ESP, "columna_que_no_existe", "otra") == RENOMBRE_NADA_QUE_RENOMBRAR
        assert _cols(con, TABLA_ESP) == COLUMNAS_ESP
    finally:
        con.close()


@requiere_drop_column
def test_con_sqlite_menor_que_3_25_no_renombra_avisa_y_la_app_no_se_cae(tmp_path, monkeypatch, capsys):
    from data.ManejoDatos.conection import RENOMBRE_SIN_SOPORTE, _asegurar_renombre_columna
    ruta = str(tmp_path / "vieja.db")
    _abrir_con_la_app(ruta, monkeypatch)
    _con_nombres_viejos(ruta)
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 24, 0))

    con = sqlite3.connect(ruta)
    try:
        estado = _asegurar_renombre_columna(con.cursor(), TABLA_ESP, "lp_mm_maximo", "lp_cm_maximo")
        assert estado == RENOMBRE_SIN_SOPORTE
        assert "lp_mm_maximo" in _cols(con, TABLA_ESP), "no debe renombrar con SQLite < 3.25"
    finally:
        con.close()
    assert "3.25" in capsys.readouterr().out, "debe avisar la version minima"

    _abrir_con_la_app(ruta, monkeypatch)                   # abrir la app entera tampoco revienta
    assert "lp_mm_maximo" in _cols(ruta, TABLA_ESP)


@requiere_drop_column
def test_un_renombrado_que_falla_no_impide_el_resto_del_arranque(tmp_path, monkeypatch, capsys):
    """La cadena de migraciones de `Conexion` vive en UN try/except: una excepcion en un paso omite los siguientes. Medido: con
    una vista rota en la base el `RENAME COLUMN` lanza `error in view ...`; sin captura se perderian E8 y el indice unico de
    controles (aqui: `idx_controles_unico_mes`, que se borra a proposito para ver si el arranque llega hasta el final)."""
    ruta = str(tmp_path / "vieja.db")
    _abrir_con_la_app(ruta, monkeypatch)
    _con_nombres_viejos(ruta)
    con = sqlite3.connect(ruta)
    try:
        con.execute("CREATE VIEW v_rota AS SELECT * FROM tabla_que_no_existe")
        con.execute("DROP INDEX IF EXISTS idx_controles_unico_mes")
        con.commit()
        with pytest.raises(sqlite3.Error):                 # el escenario es real: el RENAME falla de verdad
            con.execute(f'ALTER TABLE "{TABLA_ESP}" RENAME COLUMN lp_mm_maximo TO lp_cm_maximo')
    finally:
        con.close()
    capsys.readouterr()

    _abrir_con_la_app(ruta, monkeypatch)

    salida = capsys.readouterr().out
    assert "no se pudo renombrar" in salida and "lp_mm_maximo" in salida and "lp_cm_maximo" in salida, \
        "debe avisar cual renombrado fallo"
    assert "lp_mm_maximo" in _cols(ruta, TABLA_ESP) and "lp_cm_maximo" not in _cols(ruta, TABLA_ESP), "no se renombro: la base queda como estaba"
    assert "error_pct" in _cols(ruta, TABLA_PX), "los pasos de GI.0 anteriores al renombrado si se hicieron"
    con = sqlite3.connect(ruta)
    try:
        assert con.execute("SELECT 1 FROM sqlite_master WHERE name='idx_controles_unico_mes'").fetchone(), \
            "el arranque se detuvo en el renombrado y no llego a recrear el indice unico de controles"
    finally:
        con.close()


@requiere_drop_column
def test_una_bd_vieja_sin_error_pct_y_con_los_nombres_viejos_queda_al_dia_por_la_app(tmp_path, monkeypatch):
    ruta = str(tmp_path / "vieja.db")
    _abrir_con_la_app(ruta, monkeypatch)
    con = sqlite3.connect(ruta)
    try:
        con.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('Tomógrafo', 'Mensual', '06/2026')")
        ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
        con.execute("INSERT INTO pruebas (id_sesion, id_tipo, kv, ma, espesor_corte, created_at, equipo) "
                    "VALUES (?, 4, 120, 200, 2.0, '2026-06-01', 'Tomógrafo')", (ref,))
        prueba = con.execute("SELECT id_prueba FROM pruebas ORDER BY id_prueba DESC LIMIT 1").fetchone()[0]
        con.execute(f'INSERT INTO "{TABLA_ESP}" (id_prueba, regiones_analizadas, regiones_exitosas, lp_cm_maximo, '
                    "ultima_region_exitosa, mtf_50_pct) VALUES (?, 4, 4, 4.0, 'region 4', 3.1)", (prueba,))
        con.execute(f'INSERT INTO "{TABLA_REG}" (id_prueba, region_nombre, lp_cm, status) '
                    "VALUES (?, 'region 4', 4.0, 'OK')", (prueba,))
        con.execute(f'INSERT INTO "{TABLA_PX}" (id_prueba, valor_teorico_dicom, X, Y, error_pct) '
                    "VALUES (?, 1.074, 1.08, 1.06, 0.372)", (prueba,))
        con.commit()
    finally:
        con.close()
    _con_nombres_viejos(ruta)                              # estado de una base ya desplegada
    assert "lp_mm_maximo" in _cols(ruta, TABLA_ESP) and "error_pct" not in _cols(ruta, TABLA_PX)

    _abrir_con_la_app(ruta, monkeypatch)

    assert _cols(ruta, TABLA_ESP) == COLUMNAS_ESP and _cols(ruta, TABLA_REG) == COLUMNAS_REG
    # En una BD ya desplegada `ALTER TABLE ... ADD COLUMN` deja `error_pct` al final FISICO (despues de `activo`, DP-80):
    # el orden fisico difiere del de una BD nueva y no importa, porque el escritor, el lector y "Ver tabla" van por nombre.
    assert sorted(_cols(ruta, TABLA_PX)) == sorted(COLUMNAS_PX)
    con = sqlite3.connect(ruta)
    try:
        assert con.execute(f'SELECT lp_cm_maximo, mtf_50_pct FROM "{TABLA_ESP}"').fetchall() == [(4.0, 3.1)]
        assert con.execute(f'SELECT lp_cm FROM "{TABLA_REG}"').fetchall() == [(4.0,)]
        assert con.execute(f'SELECT X, Y, error_pct FROM "{TABLA_PX}"').fetchall() == [(1.08, 1.06, None)], \
            "la fila historica gana error_pct en NULL: no se inventa un valor retroactivo"
        tipo = {f[1]: (f[2], f[3], f[4]) for f in con.execute(f"PRAGMA table_info('{TABLA_PX}')")}
        assert tipo["error_pct"] == ("REAL", 0, None), "la columna que gana una BD vieja es REAL, admite NULL y no lleva valor por defecto"
        con.execute(f'UPDATE "{TABLA_PX}" SET error_pct = 0.372')
        assert con.execute(f'SELECT typeof(error_pct) FROM "{TABLA_PX}"').fetchone()[0] == "real", \
            "con otra afinidad el porcentaje se guardaria como texto"
    finally:
        con.close()


def test_el_informe_con_solo_renombrado_no_dice_que_la_base_ya_estaba_al_dia(tmp_path, monkeypatch, capsys):
    """Una BD que SOLO necesita el renombrado (todo lo demas al dia): el informe debe decir que hubo un cambio de esquema; junto a las
    lineas del renombrado no puede aparecer «sin cambios de esquema»."""
    from scripts.migrar_bd_a_estandar import migrar
    ruta = _copiar(BD_REBUILD_21_09, tmp_path)
    _abrir_con_la_app(ruta, monkeypatch)                   # deja todo al dia (tablas nuevas incluidas)
    con = sqlite3.connect(ruta)
    try:
        for tabla, (vieja, nueva) in RENOMBRADAS.items():  # ...y se devuelven SOLO las dos columnas a su nombre viejo
            con.execute(f'ALTER TABLE "{tabla}" RENAME COLUMN "{nueva}" TO "{vieja}"')
        con.commit()
    finally:
        con.close()
    capsys.readouterr()

    migrar(ruta, aplicar=False)
    salida = capsys.readouterr().out

    seccion = salida.split("--- Cambios de esquema ---", 1)[1].split("--- Normaliza", 1)[0]
    assert len(_lineas_de_renombrado(seccion)) == 2, seccion
    assert "sin cambios de esquema" not in seccion, "el informe afirma que la base ya estaba al dia junto al renombrado"


def test_nombres_con_otra_capitalizacion_se_reconocen_y_no_cortan_el_arranque(tmp_path, monkeypatch, capsys):
    """SQLite compara los nombres de columna sin distinguir mayusculas (el codigo tambien debe): una base con `LP_MM_MAXIMO`, `Lp_Mm` y
    `ERROR_PCT` se renombra y no agrega una segunda error_pct (el `duplicate column name` cortaba la cadena de arranque)."""
    ruta = str(tmp_path / "mayusculas.db")
    _abrir_con_la_app(ruta, monkeypatch)
    con = sqlite3.connect(ruta)
    try:
        con.execute(f'ALTER TABLE "{TABLA_ESP}" RENAME COLUMN lp_cm_maximo TO LP_MM_MAXIMO')
        con.execute(f'ALTER TABLE "{TABLA_REG}" RENAME COLUMN lp_cm TO Lp_Mm')
        con.execute(f'ALTER TABLE "{TABLA_PX}" RENAME COLUMN error_pct TO ERROR_PCT')
        con.execute("DROP INDEX IF EXISTS idx_controles_unico_mes")      # el final de la cadena de arranque lo recrea
        con.commit()
    finally:
        con.close()
    capsys.readouterr()

    _abrir_con_la_app(ruta, monkeypatch)

    salida = capsys.readouterr().out
    assert "no se pudo" not in salida, salida
    assert _cols(ruta, TABLA_ESP) == COLUMNAS_ESP and _cols(ruta, TABLA_REG) == COLUMNAS_REG
    assert [c for c in _cols(ruta, TABLA_PX) if c.lower() == "error_pct"] == ["ERROR_PCT"], "no debe agregar una segunda error_pct"
    con = sqlite3.connect(ruta)
    try:
        assert con.execute("SELECT 1 FROM sqlite_master WHERE name='idx_controles_unico_mes'").fetchone(), \
            "el arranque no llego hasta el final"
    finally:
        con.close()


def test_el_respaldo_previo_a_e10_conserva_los_nombres_viejos(tmp_path, monkeypatch):
    """El respaldo que E10 toma antes de recrear tablas (F1) es la base COMO LLEGO: con las columnas ya renombradas un build anterior no
    podria guardar la resolucion espacial con el. Por eso el renombrado va DESPUES de E10 en la cadena de arranque."""
    _requerir(BD_A_AJUSTAR)
    carpeta = tmp_path / "primitiva"
    carpeta.mkdir()
    ruta = str(carpeta / "primitiva.db")
    shutil.copy(BD_A_AJUSTAR, ruta)

    _abrir_con_la_app(ruta, monkeypatch)

    respaldos = sorted((carpeta / "respaldos_bd" / "pre_migracion").glob("*.db"))
    assert len(respaldos) == 1, f"E10 debia dejar un respaldo previo (hay {len(respaldos)})"
    assert "lp_mm_maximo" in _cols(str(respaldos[0]), TABLA_ESP) and "lp_mm" in _cols(str(respaldos[0]), TABLA_REG), \
        "el respaldo previo a E10 ya trae las columnas renombradas"
    assert _cols(ruta, TABLA_ESP) == COLUMNAS_ESP and _cols(ruta, TABLA_REG) == COLUMNAS_REG, "la base viva si queda renombrada"


@requiere_drop_column
def test_si_error_pct_no_se_puede_asegurar_el_resto_del_arranque_sigue(tmp_path, monkeypatch, capsys):
    """Igual que el renombrado: el paso de error_pct captura su error, avisa y el arranque llega hasta el final."""
    ruta = str(tmp_path / "falla.db")
    _abrir_con_la_app(ruta, monkeypatch)
    con = sqlite3.connect(ruta)
    try:
        con.execute(f'ALTER TABLE "{TABLA_PX}" DROP COLUMN error_pct')
        con.execute("DROP INDEX IF EXISTS idx_controles_unico_mes")
        con.commit()
    finally:
        con.close()
    original = conection_mod._asegurar_columna

    def falla_solo_para_error_pct(cursor, tabla, columna, ddl):
        if columna == "error_pct":
            raise sqlite3.OperationalError("fallo simulado")
        return original(cursor, tabla, columna, ddl)

    monkeypatch.setattr(conection_mod, "_asegurar_columna", falla_solo_para_error_pct)
    capsys.readouterr()

    _abrir_con_la_app(ruta, monkeypatch)

    salida = capsys.readouterr().out
    assert "no se pudo asegurar" in salida and "error_pct" in salida and "fallo simulado" in salida
    assert "error_pct" not in _cols(ruta, TABLA_PX), "el paso fallo: la columna no existe"
    con = sqlite3.connect(ruta)
    try:
        assert con.execute("SELECT 1 FROM sqlite_master WHERE name='idx_controles_unico_mes'").fetchone(), \
            "el arranque se detuvo en el paso de error_pct y no llego a recrear el indice unico de controles"
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 5. DE PUNTA A PUNTA con las claves nuevas
# ---------------------------------------------------------------------------

def test_el_mapeador_entrega_las_claves_en_lp_cm():
    from data.ManejoDatos.catphan_TAC.catphan_db import mapear_resolucion_espacial
    resumen, regiones = mapear_resolucion_espacial(RESULTADO_ESPACIAL)
    assert resumen["lp_cm_maximo"] == 10.0 and "lp_mm_maximo" not in resumen
    assert (resumen["regiones_analizadas"], resumen["regiones_exitosas"]) == (6, 5)
    assert (resumen["mtf_10_pct"], resumen["mtf_20_pct"], resumen["mtf_50_pct"]) == (5.2, 4.1, 3.1)
    assert len(regiones) == 6
    assert all("lp_cm" in r and "lp_mm" not in r for r in regiones)
    assert [r["lp_cm"] for r in regiones] == [2.0 * n for n in range(1, 7)], "el valor de cada region llega a la clave nueva"


def test_escritor_bd_lector_ida_y_vuelta_con_las_claves_nuevas(bd_temporal):
    """Ida y vuelta del VALOR, no solo de los nombres: todos los numeros del resultado son distintos entre si, asi que una columna
    escrita o leida en el lugar equivocado (lp_cm por gap_size_cm, regiones_analizadas por lp_cm_maximo...) se nota."""
    from data.ManejoDatos.catphan_TAC.catphan_db import reconstruir_resolucion_espacial
    sesion = _crear_control(bd_temporal)
    assert _guardar(sesion, {"resolucion_espacial": RESULTADO_ESPACIAL}) is not None
    con = sqlite3.connect(bd_temporal)
    try:
        fila = con.execute(f'SELECT regiones_analizadas, regiones_exitosas, lp_cm_maximo, ultima_region_exitosa, gap_size_minimo_cm, '
                           f'num_picos_totales, mtf_10_pct, mtf_20_pct, mtf_50_pct FROM "{TABLA_ESP}"').fetchone()
        assert fila == (6, 5, 10.0, "region 5", 0.1, 12, 5.2, 4.1, 3.1)
        regiones = con.execute(f'SELECT region_nombre, lp_cm, peak_mean, valley_mean, gap_size_cm, n_peaks_used, n_valleys_used, '
                               f'status FROM "{TABLA_REG}" ORDER BY id').fetchall()
        assert regiones == [(f"region {n}", 2.0 * n, 100.0 + n, 50.0 + n, round(0.5 / n, 3), 3 + n, 2 + n,
                             "OK" if n <= 5 else "Picos insuficientes") for n in range(1, 7)]
        id_prueba = con.execute(f'SELECT id_prueba FROM "{TABLA_ESP}"').fetchone()[0]
        reconstruido = reconstruir_resolucion_espacial(con.cursor(), id_prueba, None)
    finally:
        con.close()
    assert reconstruido["resolucion_limite"] == {"ultima_region": "region 5", "lp_cm_maximo": 10.0, "gap_size_cm": 0.1}
    assert reconstruido["mtf_lp_cm"] == {"10": 5.2, "20": 4.1, "50": 3.1}
    assert reconstruido["num_picos"] == 12
    assert "lp_mm_maximo" not in reconstruido["resolucion_limite"] and "mtf_lp_mm" not in reconstruido
    for n in range(1, 7):
        r = reconstruido["region_results"][f"region {n}"]
        # la clave por region de lo reconstruido la renombra GI.2 ('lp/mm' -> 'lp/cm'): se lee por cualquiera de las dos
        assert r.get("lp/cm", r.get("lp/mm")) == 2.0 * n
        assert (r["peak_mean"], r["valley_mean"], r["gap_size_cm"], r["n_peaks_used"], r["n_valleys_used"]) == (
            100.0 + n, 50.0 + n, round(0.5 / n, 3), 3 + n, 2 + n)


def test_el_pdf_lee_las_claves_reconstruidas_en_lp_cm():
    """El PDF de un control reabierto lee lo que `reconstruir_resolucion_espacial` entrega: con las claves nuevas
    imprime el maximo y el MTF, no 'N/A'. Los rotulos de unidad del PDF son de GI.3."""
    from models.PDF.Imagenes.reportes_control_sistema_imagenes import ReporteControlSistemaImagenes
    reconstruido = {
        "region_results": {}, "num_picos": 12, "imagen_analisis": None,
        "resolucion_limite": {"ultima_region": "region 4", "lp_cm_maximo": 4.0, "gap_size_cm": 0.125},
        "mtf_lp_cm": {"10": 5.2, "50": 3.1},
    }
    informe = object.__new__(ReporteControlSistemaImagenes)
    tabla = informe._crear_tabla_resolucion_espacial(reconstruido)
    filas = {f[0]: f[1] for f in tabla.values.tolist()}
    assert filas["Resolución máxima"] == "4.00"
    assert filas["MTF 10%"] == "5.20" and filas["MTF 50%"] == "3.10"


# ---------------------------------------------------------------------------
# 6. NINGUN NOMBRE MIENTE (tripwires por AST)
# ---------------------------------------------------------------------------

EXCLUIDOS = {".venv", "build", "dist", "tests", "__pycache__", ".git", "node_modules", "respaldos_bd"}
NOMBRES_VIEJOS = re.compile(r"(?<![A-Za-z0-9_])(lp_mm_maximo|lp_mm|mtf_lp_mm)(?![A-Za-z0-9_])")


def _archivos_de_produccion():
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [d for d in subcarpetas if d not in EXCLUIDOS]
        for a in archivos:
            if a.endswith(".py"):
                yield pathlib.Path(carpeta) / a


def _ids_de_docstrings(arbol):
    ids = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            cuerpo = nodo.body
            if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant) \
                    and isinstance(cuerpo[0].value.value, str):
                ids.add(id(cuerpo[0].value))
    return ids


def _constantes_de(nodo):
    return {id(n) for n in ast.walk(nodo) if isinstance(n, ast.Constant)}


def test_ninguna_cadena_de_produccion_nombra_las_columnas_o_claves_viejas():
    """SQL, claves de diccionario y rotulos: ninguna cadena (salvo docstrings y la lista del renombrado) lleva
    `lp_mm`, `lp_mm_maximo` ni `mtf_lp_mm`. Los NOMBRES DE VARIABLE locales (p. ej. `lp_mm` de pylinac en motor.py, que SI es
    lp/mm) no se miran: la prueba vigila lo que se persiste y lo que cruza entre modulos."""
    revisados, hallazgos = 0, []
    for ruta in _archivos_de_produccion():
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        revisados += 1
        permitidas = _ids_de_docstrings(arbol)
        if ruta.name == "conection.py":
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RENOMBRES_DE_COLUMNAS"
                                                       for t in nodo.targets):
                    permitidas |= _constantes_de(nodo)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in permitidas:
                for m in NOMBRES_VIEJOS.finditer(nodo.value):
                    hallazgos.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno}: {m.group(1)}")
    assert revisados > 100, f"el censo debe recorrer la produccion, solo vio {revisados} archivos"
    assert not hallazgos, "nombres que mienten la unidad de lo que persisten:\n  " + "\n  ".join(sorted(set(hallazgos)))


def test_el_analisis_produce_las_claves_en_lp_cm():
    ruta = RAIZ / "analisisImagenes" / "Analisis_Catphan_TAC.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "resolucion_espacial")
    claves = {n.value for n in ast.walk(funcion) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert {"lp_cm_maximo", "mtf_lp_cm"} <= claves, "el analisis debe nombrar sus claves con la unidad real (lp/cm)"


def _ddl(nombre_tabla):
    arbol = ast.parse((RAIZ / "data" / "ManejoDatos" / "conection.py").read_text(encoding="utf-8"))
    patron = re.compile(rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(nombre_tabla)}\s*\(")
    hallados = [n.value for n in ast.walk(arbol)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and patron.search(n.value)]
    assert len(hallados) == 1, f"debe haber exactamente un CREATE TABLE de {nombre_tabla}, hay {len(hallados)}"
    return hallados[0]


def test_los_ddl_de_las_tres_tablas_dicen_lp_cm_y_declaran_error_pct():
    assert re.search(r"\berror_pct\s+REAL\b", _ddl(TABLA_PX)), "el CREATE de tamaño_pixel debe declarar error_pct REAL"
    esp, reg = _ddl(TABLA_ESP), _ddl(TABLA_REG)
    assert re.search(r"\blp_cm_maximo\s+REAL\b", esp) and re.search(r"\blp_cm\s+REAL\b", reg)
    for nombre, ddl in ((TABLA_ESP, esp), (TABLA_REG, reg)):
        assert "lp/mm" not in ddl, f"un comentario del CREATE de {nombre} sigue diciendo lp/mm (son lp/cm)"
