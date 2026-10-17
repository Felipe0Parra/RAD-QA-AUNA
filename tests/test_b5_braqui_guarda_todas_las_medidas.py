"""B.5 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-83/DA-84, autorizado el 09-10 y confirmado el 11-10): la tabla `braqui_posicion_inicial` guarda TODAS las medidas del gris y de R, G y B, y qué capa se reportó.

CAUSA. La tabla guardaba de R, G y B solo el estado y el desfase (px y mm); la incertidumbre, la dispersión y el número de filas, solo del gris; la media de las filas, de ninguno. El físico pidió que se
guarden *«todos esos parámetros y medidas para las 3 capas»* (*«De braqui sí prefiero que se guarden todas… debido a cómo varía con el tiempo»*). Lo que imprime el PDF de la capa reportada (B.6) y lo
que se grafique después en el tiempo (DP-142) tiene que salir de lo guardado, no de un recálculo. Y cada registro tiene que decir qué capa se reportó (el menú es B.7).

QUÉ GARANTIZA ESTE ARCHIVO, cada cosa con su prueba:
  1. EL MOTOR (`valores_medidos`): las cuatro capas (gris, r, g, b) producen LAS MISMAS siete medidas, cada una con el nombre de columna que le toca (30 claves: las 17 de hoy y 13 nuevas); cada valor
     nuevo es lo que el motor midió, calculado AQUÍ desde las mesetas por fila sin llamar a ninguna función que B.5 cambie; un perfil que no se mide no guarda ningún número; y añadir o quitar una medida es
     UNA línea del motor (una lista de medidas por perfil dentro del bucle que ya recorre `CAPAS_GUARDADAS`: lo fija un censo por AST).
  2. LA TABLA: 14 columnas aditivas (13 medidas y `capa_reportada`) con su tipo, en una base nueva y en una base ya creada con PI.2 (la migración las agrega sin tocar una fila, es idempotente y deja el
     `CHECK` de la capa); `capa_reportada` acepta el NULL y solo R, G o B (el `CHECK` dice el NULL explícito: un CHECK que evalúa a NULL deja pasar la fila, y el texto de la regla no puede depender de eso).
     LA MIGRACIÓN mira CADA columna (una base a medio migrar, con `capa_reportada` o sin ella, queda con las 14: ninguna columna hace de centinela) y un `ALTER TABLE` que falla se avisa POR COLUMNA sin cortar
     ni las demás columnas ni el resto del arranque (ronda 1 de revisión, 17-10: ninguna prueba lo fijaba).
  3. EL SERVICIO (`guardar`, `listar`, `leer`): un análisis guardado y releído devuelve, para el gris y para R, G y B, EXACTAMENTE lo que el motor midió (por los tres caminos de lectura); las columnas de
     hoy no cambian de nombre ni de valor; `capa_reportada` es la que se pasó (parametrizado R, G, B; sin capa, vacía y la auditoría de siempre) y la fila de auditoría la nombra; una capa que no es R, G
     ni B se rechaza SIN escribir nada, también al reemplazar (y lo vigente queda intacto); reemplazar sin capa la deja vacía, no hereda la de la prueba anterior.
  4. LA PÁGINA: un rótulo legible por cada clave de `valores_medidos` (sin él, reabrir un registro que difiera lanza `KeyError`) que nombra el perfil, la medida y la unidad de SU clave (el de la dispersión
     de la roja no puede decir «azul»: lo lee el físico); lo guardado con el escritor real y reabierto da cero diferencias.
  5. EL OBSERVADOR DE CONTRATO (versión 3, GI.8a): las columnas nacen en NULL, así que no ve cambios en las filas viejas; un valor que aparece en una columna nueva sí.
Rojo contra `HEAD`: hoy esas claves, esas columnas y ese parámetro no existen. Se prueba con filas de la tabla hechas con el CREATE TABLE de PI.2 (la tabla tal como la dejó `HEAD`), no con una lista escrita a
mano de lo que se espera. Todo contra una BD temporal: nunca se abre una BD de referencia."""
import ast
import gc
import inspect
import io
import json
import os
import re
import shutil
import sqlite3
import textwrap
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PIL import Image

import data.ManejoDatos.conection as conection_mod
import scripts.observador_contrato as obs
import _placa_braqui_sintetica as pf0
import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod
from analisisImagenes import posicion_inicial_braqui as motor
from analisisImagenes.pelicula import CAPAS
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import crear_indices
from services import posicion_inicial_braqui as svc

TABLA = "braqui_posicion_inicial"
DATOS = Path(__file__).resolve().parent / "datos"
USUARIO = "Fisico de prueba"
S1 = "2026-01-10"
SERIE_A = "24-05-0001-A"
# las tres películas de tests/datos con los clics de la suite (los mismos de test_pi1/test_pi3)
PELICULAS = {
    "braqui_00": ("braqui_00.jpeg", [(191, 377), (190, 56)]),          # gris, G y B miden; R "la mancha esta cortada"
    "EPSON009": ("EPSON009.jpeg", [(228, 185), (234, 545)]),           # los CUATRO perfiles miden
    "EPSON031": ("EPSON031.JPG", [(2511, 3687), (2832, 3686)]),        # gris, G y B miden; R "se sale de la zona"
}
SUFIJOS = ("gris", "r", "g", "b")
NOMBRE_DEL_PERFIL = {"gris": "gris", "r": "R", "g": "G", "b": "B"}
MM_POR_PX = 25.4 / 600.0

# --- LA ESPECIFICACIÓN del plan, escrita aquí a mano (no derivada del código bajo prueba) ---------------------------------------------------------------------------------------------------------
LAS_SIETE_MEDIDAS_POR_PERFIL = ("estado_{}", "desfase_{}_px", "desfase_{}_mm", "incertidumbre_{}_px", "dispersion_{}_px", "media_{}_px", "filas_{}")
CLAVES_DE_HOY = {                                                         # las 17 de PI.1b/PI.1c: lo que se guardaba antes de B.5
    "tamano_pixel_mm", "lado_transito",
    "estado_gris", "desfase_gris_px", "desfase_gris_mm", "estado_r", "desfase_r_px", "desfase_r_mm", "estado_g", "desfase_g_px", "desfase_g_mm",
    "estado_b", "desfase_b_px", "desfase_b_mm", "incertidumbre_gris_px", "dispersion_gris_px", "filas_gris"}
CLAVES_NUEVAS = ("incertidumbre_r_px", "incertidumbre_g_px", "incertidumbre_b_px", "dispersion_r_px", "dispersion_g_px", "dispersion_b_px",
                 "filas_r", "filas_g", "filas_b", "media_r_px", "media_g_px", "media_b_px", "media_gris_px")      # las 13 del plan, en su orden
LAS_CATORCE = CLAVES_NUEVAS + ("capa_reportada",)
TIPO_DE_LAS_CATORCE = {n: ("INTEGER" if n.startswith("filas_") else "TEXT" if n == "capa_reportada" else "REAL") for n in LAS_CATORCE}
CLAVES_DE_VALORES_MEDIDOS = CLAVES_DE_HOY | set(CLAVES_NUEVAS)            # las 30
# la declaración de cada una de las 14 tal como el plan la pide, escrita AQUÍ y no tomada de `COLUMNAS_NUEVAS_DE_POSICION_INICIAL`: con ella se fabrican las bases «a medio migrar»
DDL_DE_LAS_CATORCE = {n: ("TEXT CHECK (capa_reportada IS NULL OR capa_reportada IN ('R', 'G', 'B'))" if n == "capa_reportada" else t) for n, t in TIPO_DE_LAS_CATORCE.items()}
# lo que el rótulo de una clave tiene que decir para que el aviso «reabrir un registro que difiere» no engañe al físico: de qué MEDIDA habla (con qué palabra EMPIEZA y con qué unidad entre corchetes TERMINA, o
# ninguna), en el orden de `LAS_SIETE_MEDIDAS_POR_PERFIL`, y de qué PERFIL (el color con que lo nombra: el rótulo de la clave de uno nombra a ese y a ningún otro). Cambiar el texto de un rótulo (B5-D1, vetable)
# es cambiar una palabra de estas dos tablas, no la lógica de la prueba.
COMO_SE_DICE_CADA_MEDIDA = (("estado", None), ("desfase", "[px]"), ("desfase", "[mm]"), ("incertidumbre", "[px]"), ("dispersión", "[px]"), ("media", "[px]"), ("número de cuerdas", None))
COMO_SE_DICE_CADA_PERFIL = {"gris": r"gris(es)?", "r": r"roj[oa]", "g": r"verde", "b": r"azul"}

# la tabla tal como la creó PI.2 (HEAD 5666a11): sin las 14 columnas y sin `activo` (la agrega `_asegurar_activo_bloque_qc`). Es la tabla "hecha con HEAD" de las pruebas de la migración.
DDL_DE_PI2 = """
CREATE TABLE braqui_posicion_inicial (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, serie_fuente TEXT, user TEXT, imagen BLOB NOT NULL, imagen_nombre TEXT, imagen_md5 TEXT, dpi REAL, tamano_pixel_mm REAL,
    puntos TEXT NOT NULL, parametros TEXT NOT NULL, version_algoritmo TEXT NOT NULL, estado_gris TEXT, desfase_gris_px REAL, desfase_gris_mm REAL, incertidumbre_gris_px REAL,
    dispersion_gris_px REAL, filas_gris INTEGER, estado_r TEXT, desfase_r_px REAL, desfase_r_mm REAL, estado_g TEXT, desfase_g_px REAL, desfase_g_mm REAL, estado_b TEXT,
    desfase_b_px REAL, desfase_b_mm REAL, lado_transito TEXT, tolerancia_mm REAL, observaciones TEXT,
    CHECK ((desfase_gris_mm IS NULL) = (desfase_gris_px IS NULL OR tamano_pixel_mm IS NULL)
           AND (desfase_gris_mm IS NULL OR abs(desfase_gris_mm - desfase_gris_px * tamano_pixel_mm) <= 1e-9)),
    CHECK ((desfase_r_mm IS NULL) = (desfase_r_px IS NULL OR tamano_pixel_mm IS NULL)
           AND (desfase_r_mm IS NULL OR abs(desfase_r_mm - desfase_r_px * tamano_pixel_mm) <= 1e-9)),
    CHECK ((desfase_g_mm IS NULL) = (desfase_g_px IS NULL OR tamano_pixel_mm IS NULL)
           AND (desfase_g_mm IS NULL OR abs(desfase_g_mm - desfase_g_px * tamano_pixel_mm) <= 1e-9)),
    CHECK ((desfase_b_mm IS NULL) = (desfase_b_px IS NULL OR tamano_pixel_mm IS NULL)
           AND (desfase_b_mm IS NULL OR abs(desfase_b_mm - desfase_b_px * tamano_pixel_mm) <= 1e-9))
)"""
COLUMNAS_DE_PI2 = ("id", "fecha", "serie_fuente", "user", "imagen", "imagen_nombre", "imagen_md5", "dpi", "tamano_pixel_mm", "puntos", "parametros", "version_algoritmo", "estado_gris",
                   "desfase_gris_px", "desfase_gris_mm", "incertidumbre_gris_px", "dispersion_gris_px", "filas_gris", "estado_r", "desfase_r_px", "desfase_r_mm", "estado_g",
                   "desfase_g_px", "desfase_g_mm", "estado_b", "desfase_b_px", "desfase_b_mm", "lado_transito", "tolerancia_mm", "observaciones")


# ================================================================================================================ lo que el motor midió, calculado AQUÍ
def medidas_esperadas(resultado):
    """{clave de `valores_medidos`: valor} de un resultado del motor, calculado desde las mesetas por fila (`m`), las filas útiles y `x_ref`: ninguna función que B.5 cambie interviene. Es el oráculo
    independiente de la prueba. Las filas que cuentan salen de `motivos_de_las_filas` (B.4), no de `len(filas)`; la incertidumbre se recalcula de sus tres componentes (la suma de `incertidumbre_px`)."""
    tam = resultado["tamano_pixel_mm"]
    x_ref = resultado["x_ref"]
    esperado = {"tamano_pixel_mm": tam, "lado_transito": resultado["lado_transito"]}
    for perfil, sufijo in (("gris", "gris"), ("R", "r"), ("G", "g"), ("B", "b")):
        p = resultado["perfiles"][perfil]
        if p["estado"] != "ok":
            esperado.update({f"estado_{sufijo}": p["estado"], f"desfase_{sufijo}_px": None, f"desfase_{sufijo}_mm": None, f"incertidumbre_{sufijo}_px": None,
                             f"dispersion_{sufijo}_px": None, f"media_{sufijo}_px": None, f"filas_{sufijo}": None})
            continue
        m, filas = p["m"], p["filas"]
        centros = (m["x_izq"][filas] + m["x_der"][filas]) / 2.0
        desfases = x_ref[filas] - centros
        px = float(np.median(desfases))
        n_eff = max(len(filas) / 8.0, 1.0)
        u_filas = 1.2533 * np.std(desfases) / np.sqrt(n_eff)
        cruces = p["desfase_cruces_px"]
        u_metodo = abs(px - cruces) / np.sqrt(3) if np.isfinite(cruces) else u_filas
        usadas = motor.motivos_de_las_filas(m, resultado["parametros"])["usada"]
        esperado.update({
            f"estado_{sufijo}": "ok", f"desfase_{sufijo}_px": px, f"desfase_{sufijo}_mm": px * tam if tam is not None else None,
            f"incertidumbre_{sufijo}_px": 2 * float(np.sqrt(u_filas ** 2 + resultado["u_linea_px"] ** 2 + u_metodo ** 2)),
            f"dispersion_{sufijo}_px": float(np.std(desfases)), f"media_{sufijo}_px": float(np.mean(desfases)), f"filas_{sufijo}": int(np.count_nonzero(usadas))})
    return esperado


# ================================================================================================================ fixtures
@pytest.fixture(scope="module")
def peliculas():
    """El análisis REAL de las tres películas de tests/datos, hecho una vez (es la misma función que `guardar` llama). Fixture y no variable de módulo: se suelta sola al terminar el módulo."""
    salida = {}
    for nombre, (archivo, clics) in PELICULAS.items():
        datos = (DATOS / archivo).read_bytes()
        salida[nombre] = SimpleNamespace(datos=datos, clics=clics, nombre=archivo, resultado=svc.analizar_imagen(datos, clics))
    yield salida
    salida.clear()
    gc.collect()


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    """La BD nueva con todo el esquema de HOY y los índices únicos, hecha UNA vez; cada prueba trabaja sobre su copia."""
    ruta = str(tmp_path_factory.mktemp("b5") / "plantilla.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
            Conexion._instance = None
            assert crear_indices(ruta)[TABLA] == "creado"
        finally:
            Conexion._instance = previo
    return ruta


def _poner_la_ruta(monkeypatch, ruta):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    """Copia de la plantilla y un `Conexion` sin arranque (el esquema ya está): `conectar()` es el real."""
    ruta = str(tmp_path / "b5.db")
    shutil.copy(plantilla, ruta)
    _poner_la_ruta(monkeypatch, ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    yield ruta
    Conexion._instance = previo


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        cursor = con.execute(sql, parametros)
        con.commit()
        return cursor.lastrowid
    finally:
        con.close()


def _consulta(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, parametros).fetchall()
    finally:
        con.close()


def _fila_como_dict(ruta, id_registro):
    con = sqlite3.connect(ruta)
    try:
        con.row_factory = sqlite3.Row
        return dict(con.execute(f"SELECT * FROM {TABLA} WHERE id = ?", (id_registro,)).fetchone())
    finally:
        con.close()


def _sembrar_cambio_de_fuente(ruta, fecha=S1, serie=SERIE_A):
    return _sql(ruta, "INSERT INTO TipoCalibracion (user, fecha, tipo, serie, activo) VALUES ('Siembra', ?, 'Cambio de fuente', ?, 1)", (f"{fecha} 15:03:03", serie))


def _auditoria(ruta):
    return _consulta(ruta, "SELECT accion, usuario, ref, detalle FROM audit_log WHERE tabla = ? ORDER BY id", (TABLA,))


def _filas(ruta):
    return _consulta(ruta, f"SELECT id, fecha, activo FROM {TABLA} ORDER BY id")


def _guardar_con_capa(pelicula, capa, **extra):
    """`svc.guardar` con la capa que se pide; antes de llamar afirma que el servicio la recibe (si no, la prueba cae por lo que FALTA, no por un TypeError de Python)."""
    assert "capa_reportada" in inspect.signature(svc.guardar).parameters, "guardar no recibe capa_reportada"
    return svc.guardar(USUARIO, S1, pelicula.datos, pelicula.nombre, pelicula.clics, capa_reportada=capa, **extra)


def _columnas(ruta):
    """[(nombre, tipo declarado)] en el orden físico de la tabla."""
    return [(c[1], c[2]) for c in _consulta(ruta, f"PRAGMA table_info('{TABLA}')")]


def _abrir_con_la_app(ruta, monkeypatch):
    """Abre la BD con el arranque REAL de la app (`Conexion()`), que crea y migra, y la suelta."""
    _poner_la_ruta(monkeypatch, ruta)
    previo = Conexion._instance
    Conexion._instance = None
    try:
        Conexion().con.close()
    finally:
        Conexion._instance = previo


def _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=None):
    """Una BD cuya tabla de la posición inicial es EXACTAMENTE la que dejó HEAD (PI.2: sin las 14 columnas, con `activo` y su índice único), con una fila vieja si se pide. Se parte de la plantilla de HOY
    para tener todo lo demás del esquema; la tabla se rehace con el DDL de PI.2. Devuelve la ruta."""
    ruta = str(tmp_path / "hecha_con_head.db")
    shutil.copy(plantilla, ruta)
    con = sqlite3.connect(ruta)
    try:
        con.execute(f"DROP TABLE {TABLA}")
        con.execute(DDL_DE_PI2)
        con.execute(f"ALTER TABLE {TABLA} ADD COLUMN activo INTEGER DEFAULT 1")
        con.commit()
    finally:
        con.close()
    assert crear_indices(ruta)[TABLA] == "creado"
    if con_fila_vieja is not None:
        _insertar_fila_de_head(ruta, con_fila_vieja)
    assert [c[0] for c in _columnas(ruta)] == list(COLUMNAS_DE_PI2) + ["activo"], "la tabla de PI.2 no quedo como la dejo HEAD"
    return ruta


def _insertar_fila_de_head(ruta, pelicula):
    """Una fila como la que HEAD guardaba: los 17 valores de hoy y nada de las 14 nuevas."""
    valores = {k: v for k, v in medidas_esperadas(pelicula.resultado).items() if k in CLAVES_DE_HOY}
    fila = {"fecha": S1, "serie_fuente": SERIE_A, "user": USUARIO, "imagen": pelicula.datos, "imagen_nombre": pelicula.nombre, "imagen_md5": "0" * 32,
            "dpi": pelicula.resultado["dpi"], "puntos": json.dumps([list(map(float, c)) for c in pelicula.clics]),
            "parametros": json.dumps(pelicula.resultado["parametros"], sort_keys=True), "version_algoritmo": motor.VERSION_ALGORITMO, "tolerancia_mm": 1.0, **valores}
    return _sql(ruta, f"INSERT INTO {TABLA} ({', '.join(fila)}) VALUES ({', '.join('?' * len(fila))})", list(fila.values()))


def _con_solo_estas_de_las_catorce(ruta, ya_estan):
    """Deja la tabla como la dejaría una migración INTERRUMPIDA (o un parche a mano): de las 14 columnas nuevas solo `ya_estan`, en el orden del plan y con la declaración del plan. Parte de una base hecha con HEAD."""
    con = sqlite3.connect(ruta)
    try:
        for nombre in LAS_CATORCE:
            if nombre in ya_estan:
                con.execute(f"ALTER TABLE {TABLA} ADD COLUMN {nombre} {DDL_DE_LAS_CATORCE[nombre]}")
        con.commit()
    finally:
        con.close()


# lo que repone el FINAL de la cadena de arranque de `Conexion` (el índice único de controles es su ÚLTIMO paso; el trigger que protege a `users`, E8, va justo antes): si el arranque se aborta en la migración de las
# 14 columnas, que está ANTES, ninguno de los dos vuelve a existir. Son los testigos de «el resto del arranque corrió».
TESTIGOS_DEL_FINAL_DEL_ARRANQUE = ("idx_controles_unico_mes", "trg_no_borrar_users")


def _testigos_del_final_del_arranque(ruta):
    return {f[0] for f in _consulta(ruta, f"SELECT name FROM sqlite_master WHERE name IN ({', '.join('?' * len(TESTIGOS_DEL_FINAL_DEL_ARRANQUE))})", TESTIGOS_DEL_FINAL_DEL_ARRANQUE)}


def _quitar_los_testigos_del_final_del_arranque(ruta):
    con = sqlite3.connect(ruta)
    try:
        con.execute("DROP INDEX idx_controles_unico_mes")
        con.execute("DROP TRIGGER trg_no_borrar_users")
        con.commit()
    finally:
        con.close()


CAPAS_VALIDAS = (None,) + tuple(CAPAS)
CAPAS_INVALIDAS = ("X", "r", "g", "b", "gris", "GRIS", "", " G", "G ", "RG", "1", 1, 0)


def _insertar_con_capa(ruta, fecha, capa):
    _sql(ruta, f"INSERT INTO {TABLA} (fecha, imagen, puntos, parametros, version_algoritmo, capa_reportada) VALUES (?, x'00', '[]', '{{}}', 'PI-2', ?)", (fecha, capa))


def _el_check_de_la_capa_funciona(ruta):
    """El vacio y R, G, B entran; todo lo demas rechaza la fila entera (y no queda nada a medias)."""
    assert "capa_reportada" in {c[0] for c in _columnas(ruta)}, f"{TABLA}: no existe capa_reportada"
    for i, capa in enumerate(CAPAS_VALIDAS):
        _insertar_con_capa(ruta, f"2026-02-{i + 1:02d}", capa)
    assert [r[0] for r in _consulta(ruta, f"SELECT capa_reportada FROM {TABLA} ORDER BY id")] == list(CAPAS_VALIDAS)
    for capa in CAPAS_INVALIDAS:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            _insertar_con_capa(ruta, "2026-03-01", capa)
    assert _consulta(ruta, f"SELECT COUNT(*) FROM {TABLA}")[0][0] == len(CAPAS_VALIDAS)


# ================================================================================================================ 1. EL MOTOR
class TestElMotorProduceLasMismasMedidasParaLasCuatroCapas:
    def test_valores_medidos_trae_las_mismas_siete_medidas_para_el_gris_y_para_cada_capa(self, peliculas):
        v = motor.valores_medidos(peliculas["EPSON009"].resultado)
        esperadas = {"tamano_pixel_mm", "lado_transito"} | {plantilla.format(s) for s in SUFIJOS for plantilla in LAS_SIETE_MEDIDAS_POR_PERFIL}
        assert esperadas == CLAVES_DE_VALORES_MEDIDOS and len(esperadas) == 30, "compuerta: la especificacion del plan son 30 claves (17 de hoy + 13 nuevas)"
        faltan, sobran = sorted(esperadas - set(v)), sorted(set(v) - esperadas)
        assert not faltan and not sobran, f"valores_medidos: faltan {faltan}; sobran {sobran}"
        for sufijo in SUFIJOS:                              # la simetria: el gris ya no tiene tres medidas que las capas no tengan
            assert {p.format(sufijo) in v for p in LAS_SIETE_MEDIDAS_POR_PERFIL} == {True}, sufijo

    @pytest.mark.parametrize("nombre", sorted(PELICULAS))
    def test_cada_valor_es_lo_que_el_motor_midio_en_ese_perfil(self, nombre, peliculas):
        resultado = peliculas[nombre].resultado
        v = motor.valores_medidos(resultado)
        esperado = medidas_esperadas(resultado)
        faltan = sorted(set(esperado) - set(v))
        assert not faltan, f"valores_medidos no trae {faltan}"
        for clave, valor in esperado.items():
            if clave.startswith("incertidumbre_"):
                assert v[clave] == (pytest.approx(valor, rel=1e-12) if valor is not None else None), (nombre, clave)
                continue
            assert v[clave] == valor and type(v[clave]) is type(valor), (nombre, clave, v[clave], valor)     # igualdad EXACTA y tipos de Python (SQLite y JSON)

    @pytest.mark.parametrize("nombre", sorted(PELICULAS))
    def test_la_incertidumbre_de_cada_perfil_es_la_unica_definicion(self, nombre, peliculas):
        resultado = peliculas[nombre].resultado
        v = motor.valores_medidos(resultado)
        assert "incertidumbre_r_px" in v, "valores_medidos no guarda la incertidumbre de las capas"
        for perfil, sufijo in (("gris", "gris"), ("R", "r"), ("G", "g"), ("B", "b")):
            assert v[f"incertidumbre_{sufijo}_px"] == motor.incertidumbre_px(resultado, perfil), (nombre, perfil)
        assert v["incertidumbre_gris_px"] == motor.resumen(resultado)["U_px"]

    def test_la_media_no_es_la_mediana_y_el_desfase_sigue_siendo_la_mediana(self, peliculas):
        """Una media calculada con la mediana (o al revés) pasaria por todo lo demas: en las tres peliculas la media de cada perfil que mide difiere de su mediana, y el desfase que se guarda y se reporta es la mediana."""
        medidos = 0
        for nombre, pelicula in peliculas.items():
            v = motor.valores_medidos(pelicula.resultado)
            assert "media_gris_px" in v, "valores_medidos no guarda la media"
            for sufijo in SUFIJOS:
                if v[f"estado_{sufijo}"] != "ok":
                    continue
                medidos += 1
                media, desfase = v[f"media_{sufijo}_px"], v[f"desfase_{sufijo}_px"]
                assert abs(media - desfase) > 0.1, (nombre, sufijo, media, desfase)
                assert desfase == float(np.median(pelicula.resultado["perfiles"][NOMBRE_DEL_PERFIL[sufijo]]["desfases"])), (nombre, sufijo)
        assert medidos == 4 + 3 + 3, "compuerta: gris+R+G+B de EPSON009 y gris+G+B de las otras dos"

    def test_un_perfil_que_no_se_mide_no_guarda_ninguna_de_las_medidas_numericas(self, peliculas):
        v = motor.valores_medidos(peliculas["braqui_00"].resultado)                  # la capa roja de braqui_00 no se mide
        assert v["estado_r"].startswith("no medible"), "compuerta: la capa roja de braqui_00 no se mide"
        faltan = [c for c in ("incertidumbre_r_px", "dispersion_r_px", "media_r_px", "filas_r") if c not in v]
        assert not faltan, f"valores_medidos no trae {faltan}"
        for clave in ("desfase_r_px", "desfase_r_mm", "incertidumbre_r_px", "dispersion_r_px", "media_r_px", "filas_r"):
            assert v[clave] is None, clave

    def test_sin_escala_hay_pixeles_y_no_milimetros_y_las_medidas_nuevas_no_dependen_de_ella(self, peliculas):
        """Una resolucion 'otra' declarada (300 dpi): hay pixeles y no hay milimetros. Las medidas nuevas son pixeles o cuentas: no las toca la escala."""
        datos, clics = peliculas["braqui_00"].datos, peliculas["braqui_00"].clics
        gris, color, _, _ = motor.leer_imagen(datos)
        sin_escala = motor.valores_medidos(motor.analizar(gris, color, 300.0, clics))
        con_escala = motor.valores_medidos(peliculas["braqui_00"].resultado)
        assert sin_escala["tamano_pixel_mm"] is None and all(sin_escala[f"desfase_{s}_mm"] is None for s in SUFIJOS)
        faltan = [c for c in CLAVES_NUEVAS if c not in sin_escala]
        assert not faltan, f"valores_medidos no trae {faltan}"
        for clave in CLAVES_NUEVAS:
            assert sin_escala[clave] == con_escala[clave], clave

    def test_anadir_una_medida_es_una_linea_del_motor(self):
        """`valores_medidos` recorre `CAPAS_GUARDADAS` UNA vez y escribe las medidas de cada perfil desde UNA lista de pares (plantilla del nombre de la columna, valor): una medida nueva es una linea de esa
        lista. Nada por perfil se escribe a mano fuera de ella (ningun f-string con el sufijo)."""
        arbol = ast.parse(textwrap.dedent(inspect.getsource(motor.valores_medidos)))
        funcion = arbol.body[0]
        bucles = [n for n in ast.walk(funcion) if isinstance(n, ast.For) and isinstance(n.iter, ast.Name) and n.iter.id == "CAPAS_GUARDADAS"]
        assert len(bucles) == 1, "valores_medidos debe recorrer CAPAS_GUARDADAS una sola vez"

        def es_lista_de_pares(n):
            return (isinstance(n, (ast.Tuple, ast.List)) and len(n.elts) >= 2
                    and all(isinstance(e, ast.Tuple) and len(e.elts) == 2 and isinstance(e.elts[0], ast.Constant) and isinstance(e.elts[0].value, str) for e in n.elts))
        listas = [n for n in ast.walk(bucles[0]) if es_lista_de_pares(n)]
        assert len(listas) == 1, "dentro del bucle debe haber UNA lista de medidas por perfil"
        nombres = sorted(e.elts[0].value.format("X") for e in listas[0].elts)
        assert nombres == sorted(p.format("X") for p in LAS_SIETE_MEDIDAS_POR_PERFIL), nombres
        assert not [n for n in ast.walk(funcion) if isinstance(n, ast.JoinedStr)], "ninguna clave por perfil se escribe a mano con un f-string"

    @pytest.mark.parametrize("nombre", ["braqui_00", "EPSON009"])
    def test_la_media_que_dibuja_el_barrido_es_la_que_se_guarda(self, nombre, peliculas):
        """Dos caminos a la misma cifra, uno para la pantalla (B.4: `datos_del_barrido`, en mm) y otro para la base (`media_*_px`): la convergencia se AFIRMA, no se confia. Lo que se dibuja como «media» es lo
        que se guarda, y la mediana punteada es el desfase que se guarda."""
        resultado = peliculas[nombre].resultado
        v = motor.valores_medidos(resultado)
        assert "media_gris_px" in v, "valores_medidos no guarda la media"
        tam = resultado["tamano_pixel_mm"]
        comparados = 0
        for perfil, sufijo in (("gris", "gris"), ("R", "r"), ("G", "g"), ("B", "b")):
            datos = pagina_mod.datos_del_barrido(resultado, perfil)
            if resultado["perfiles"][perfil]["estado"] != "ok":
                assert "media" not in datos and v[f"media_{sufijo}_px"] is None, (nombre, perfil)
                continue
            assert datos["media"] == pytest.approx(v[f"media_{sufijo}_px"] * tam, rel=1e-12), (nombre, perfil)
            assert datos["mediana"] == v[f"desfase_{sufijo}_px"] * tam, (nombre, perfil)
            comparados += 1
        assert comparados == (3 if nombre == "braqui_00" else 4), "compuerta: los perfiles que miden en cada pelicula"

    def test_la_version_del_algoritmo_sigue_en_PI_2_porque_ningun_numero_de_hoy_cambia(self):
        """B.5 solo agrega lo que se guarda; ni el desfase, ni la incertidumbre del gris, ni las filas, ni las mesetas cambian (lo prueba la compuerta de cero diferencias del anexo, bit a bit en 26 peliculas y en las placas de PF.0)."""
        assert motor.VERSION_ALGORITMO == "PI-2"


class TestLaMediaSePareceAlDesfaseVerdadero:
    """Regla 13 del plan (exactitud contra VERDAD CONOCIDA, con un generador INDEPENDIENTE del motor) para la unica magnitud que B.5 calcula por primera vez, la media de los desfases de las cuerdas. Las placas de PF.0
    traen el desfase verdadero (linea - centro de la mancha, en mm a 600 dpi): la media de cada perfil que mide cae a menos de 0.05 mm de el, en los dos modelos del generador y en los cuatro perfiles. Medido el 16-10
    (14 placas, 52 comparaciones): el peor error es 0.028 mm; el de la mediana, 0.021 mm."""
    GENERADORES = {"independiente": lambda d: pf0.generar_independiente(d, formato="png"), "fisico": lambda d: pf0.generar_fisico(d)}

    @pytest.mark.parametrize("modelo", ["independiente", "fisico"])
    @pytest.mark.parametrize("desfase_mm", [-3.0, -1.0, 0.75, 3.0])
    def test_la_media_de_cada_perfil_cae_a_menos_de_5_centesimas_de_milimetro_del_desfase_verdadero(self, modelo, desfase_mm):
        placa = self.GENERADORES[modelo](desfase_mm)
        v = motor.valores_medidos(svc.analizar_imagen(placa.datos, [tuple(c) for c in placa.clics]))
        assert "media_gris_px" in v, "valores_medidos no guarda la media"
        medidos = 0
        for sufijo in SUFIJOS:
            if v[f"estado_{sufijo}"] != "ok":
                continue
            medidos += 1
            error = v[f"media_{sufijo}_px"] * MM_POR_PX - placa.verdad.desfase_mm
            assert abs(error) <= 0.05, (modelo, desfase_mm, sufijo, error)
        assert medidos == 4, "compuerta: en estas placas miden los cuatro perfiles"


# ================================================================================================================ 2. LA TABLA
class TestLaTablaTieneLasCatorceColumnas:
    def test_una_base_nueva_nace_con_las_catorce_columnas_y_su_tipo_y_activo_sigue_al_final(self, bd):
        columnas = _columnas(bd)
        nombres = [c[0] for c in columnas]
        faltan = [c for c in LAS_CATORCE if c not in nombres]
        assert not faltan, f"{TABLA}: faltan las columnas {faltan}"
        assert nombres[:len(COLUMNAS_DE_PI2)] == list(COLUMNAS_DE_PI2), "las 29 columnas de datos de PI.2 siguen donde estaban, con su nombre"
        assert nombres[-1] == "activo" and len(nombres) == 30 + 14 + 1
        assert {n: t for n, t in columnas if n in LAS_CATORCE} == TIPO_DE_LAS_CATORCE

    def test_cada_valor_que_el_motor_entrega_tiene_su_columna(self, bd, peliculas):
        """El productor y la tabla no pueden separarse: toda clave de `valores_medidos` es una columna con el mismo nombre, y las 30 de la especificacion del plan tambien (si el motor dejara de producir una, la tabla seguiria
        debiendola; si la tabla perdiera una, el motor la produciria para nada)."""
        columnas = {c[0] for c in _columnas(bd)}
        valores = motor.valores_medidos(peliculas["EPSON009"].resultado)
        assert CLAVES_DE_VALORES_MEDIDOS <= columnas, f"{TABLA}: faltan las columnas {sorted(CLAVES_DE_VALORES_MEDIDOS - columnas)}"
        assert set(valores) <= columnas, sorted(set(valores) - columnas)

    def test_capa_reportada_acepta_el_vacio_y_R_G_B_y_rechaza_cualquier_otra_cosa(self, bd):
        _el_check_de_la_capa_funciona(bd)

    def test_el_check_de_la_capa_dice_el_null_explicito_y_las_mismas_capas_que_el_menu(self, bd):
        """La plan lo pide asi (como los CHECK de los milimetros): un CHECK que evalua a NULL deja pasar la fila, y el texto de la regla no puede depender de eso. Las letras son `pelicula.CAPAS`, las del menu de B.7."""
        sql = _consulta(bd, "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (TABLA,))[0][0]
        lista = r"\s*,\s*".join(re.escape(repr(c)) for c in CAPAS)
        assert re.search(rf"CHECK\s*\(\s*capa_reportada\s+IS\s+NULL\s+OR\s+capa_reportada\s+IN\s*\(\s*{lista}\s*\)\s*\)", sql), sql

    def test_los_check_de_los_milimetros_de_cada_perfil_siguen_ahi(self, bd):
        sql = _consulta(bd, "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (TABLA,))[0][0]
        for s in SUFIJOS:
            assert f"abs(desfase_{s}_mm - desfase_{s}_px * tamano_pixel_mm)" in sql, s


# ================================================================================================================ 2b. LA MIGRACION
class TestLaMigracionDeUnaBaseHechaConHead:
    def test_agrega_las_catorce_columnas_al_final_sin_tocar_una_fila_y_la_segunda_apertura_no_cambia_nada(self, plantilla, monkeypatch, tmp_path, peliculas):
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=peliculas["EPSON009"])
        antes = _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id")
        columnas_antes = _columnas(ruta)
        assert len(antes) == 1 and len(columnas_antes) == 31
        _abrir_con_la_app(ruta, monkeypatch)
        columnas = _columnas(ruta)
        assert [c[0] for c in columnas[:len(columnas_antes)]] == [c[0] for c in columnas_antes], "las columnas viejas siguen en su sitio"
        assert [c[0] for c in columnas[len(columnas_antes):]] == list(LAS_CATORCE), "las 14 llegan al final, en el orden del plan"
        assert {n: t for n, t in columnas if n in LAS_CATORCE} == TIPO_DE_LAS_CATORCE
        despues = _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id")
        assert [f[:len(columnas_antes)] for f in despues] == antes, "ni un valor de la fila vieja cambia"
        assert all(valor is None for f in despues for valor in f[len(columnas_antes):]), "las 14 nacen vacias (sin relleno retroactivo)"
        assert _consulta(ruta, "PRAGMA integrity_check") == [("ok",)]
        _abrir_con_la_app(ruta, monkeypatch)                                                    # segunda apertura: idempotente
        assert _columnas(ruta) == columnas and _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id") == despues

    def test_la_tabla_migrada_y_la_tabla_nueva_tienen_las_mismas_catorce_columnas_con_el_mismo_tipo_y_la_misma_regla_de_la_capa(self, plantilla, monkeypatch, tmp_path, bd):
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path)
        _abrir_con_la_app(ruta, monkeypatch)
        assert {n: t for n, t in _columnas(ruta) if n in LAS_CATORCE} == {n: t for n, t in _columnas(bd) if n in LAS_CATORCE} == TIPO_DE_LAS_CATORCE
        _el_check_de_la_capa_funciona(ruta)

    def test_una_fila_hecha_con_head_se_lee_con_el_servicio_nuevo_y_trae_las_catorce_vacias(self, plantilla, monkeypatch, tmp_path, peliculas):
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=peliculas["braqui_00"])
        _sql(ruta, "INSERT INTO TipoCalibracion (user, fecha, tipo, serie, activo) VALUES ('Siembra', ?, 'Cambio de fuente', ?, 1)", (f"{S1} 15:03:03", SERIE_A))
        _abrir_con_la_app(ruta, monkeypatch)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            leida = svc.leer(1)
            listada = [f for f in svc.listar() if f["id"] == 1][0]
        finally:
            Conexion._instance = previo
        for via, fila in (("leer", leida), ("listar", listada)):
            assert all(c in fila for c in LAS_CATORCE), (via, sorted(set(LAS_CATORCE) - set(fila)))
            assert all(fila[c] is None for c in LAS_CATORCE), via
            assert fila["desfase_gris_px"] == motor.valores_medidos(peliculas["braqui_00"].resultado)["desfase_gris_px"], "las de hoy conservan su valor"

    @pytest.mark.parametrize("ya_estan", [tuple(n for n in LAS_CATORCE if n != faltante) for faltante in LAS_CATORCE] + [LAS_CATORCE[:7], LAS_CATORCE[7:]],
                             ids=[f"falta_solo_{n}" for n in LAS_CATORCE] + ["ya_estan_las_primeras_7", "ya_estan_las_ultimas_7_con_capa_reportada"])
    def test_una_base_a_medio_migrar_se_completa_columna_por_columna(self, ya_estan, plantilla, monkeypatch, tmp_path, peliculas):
        """La migración mira CADA columna: una base cuya migración se interrumpió (o a la que alguien agregó a mano unas columnas, `capa_reportada` entre ellas) queda con las 14 al abrirla, y no hay una columna que valga
        de centinela (una migración que decidiera por «`capa_reportada` ya existe» dejaría sin completar la base a medio migrar). Las columnas que ya estaban siguen en su sitio, la fila vieja no cambia, nada se rellena y la
        segunda apertura no cambia nada."""
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=peliculas["EPSON009"])
        _con_solo_estas_de_las_catorce(ruta, ya_estan)
        columnas_antes = _columnas(ruta)
        filas_antes = _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id")
        assert {c[0] for c in columnas_antes} & set(LAS_CATORCE) == set(ya_estan), "compuerta: la base quedo con exactamente las columnas que se pidieron"
        _abrir_con_la_app(ruta, monkeypatch)
        columnas = _columnas(ruta)
        faltan = sorted(set(LAS_CATORCE) - {c[0] for c in columnas})
        assert not faltan, f"la migracion no completo una base a medio migrar (ya estaban {sorted(ya_estan)}): faltan {faltan}"
        assert {n: t for n, t in columnas if n in LAS_CATORCE} == TIPO_DE_LAS_CATORCE
        assert [c[0] for c in columnas[:len(columnas_antes)]] == [c[0] for c in columnas_antes], "las columnas que ya estaban siguen en su sitio"
        assert len(columnas) == len(columnas_antes) + len(LAS_CATORCE) - len(ya_estan), "ni una columna de mas"
        filas = _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id")
        assert [f[:len(columnas_antes)] for f in filas] == filas_antes, "ni un valor de la fila vieja cambia"
        assert all(valor is None for f in filas for valor in f[len(columnas_antes):]), "las que se agregaron nacen vacias (sin relleno retroactivo)"
        _abrir_con_la_app(ruta, monkeypatch)                                                    # segunda apertura: idempotente
        assert _columnas(ruta) == columnas and _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id") == filas
        _insertar_con_capa(ruta, "2026-03-01", "R")                                          # la regla de la capa vale tambien aqui: la declaro la migracion o la declaro la base a medio migrar
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            _insertar_con_capa(ruta, "2026-03-02", "X")

    @pytest.mark.parametrize("fallan", [("media_g_px",), LAS_CATORCE], ids=["falla_solo_media_g_px", "fallan_las_catorce"])
    def test_un_ALTER_que_falla_se_avisa_por_columna_y_no_corta_ni_las_demas_columnas_ni_el_resto_del_arranque(self, fallan, plantilla, monkeypatch, tmp_path, peliculas, capsys):
        """La promesa de la migración (su docstring): cada columna tiene SU intento y un `ALTER TABLE` que falla se avisa SIN cortar el resto del arranque. Con el arranque REAL (`Conexion()`) y lo que el FINAL de la
        cadena repone como testigo: una migración que relanzara el error, que pusiera todo el bucle en UN `try` (el primer fallo corta las demás columnas) o que callara el fallo no pasa. Y la siguiente apertura,
        sin el fallo, completa la tabla."""
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=peliculas["EPSON009"])
        assert _testigos_del_final_del_arranque(ruta) == set(TESTIGOS_DEL_FINAL_DEL_ARRANQUE), "compuerta: la plantilla trae los testigos del final del arranque"
        _quitar_los_testigos_del_final_del_arranque(ruta)
        assert _testigos_del_final_del_arranque(ruta) == set(), "compuerta: sin los testigos"
        antes = _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id")
        original = conection_mod._asegurar_columna

        def falla_solo_para_esas_columnas(cursor, tabla, columna, ddl):
            if tabla == TABLA and columna in fallan:
                raise sqlite3.OperationalError("falla de prueba")
            return original(cursor, tabla, columna, ddl)

        monkeypatch.setattr(conection_mod, "_asegurar_columna", falla_solo_para_esas_columnas)
        capsys.readouterr()                                                                       # lo anterior no cuenta
        _abrir_con_la_app(ruta, monkeypatch)                                                    # no debe lanzar
        salida = capsys.readouterr().out
        nombres = {c[0] for c in _columnas(ruta)}
        assert not set(fallan) & nombres, "compuerta: la falla simulada debio impedir esas columnas"
        sin_agregar = sorted((set(LAS_CATORCE) - set(fallan)) - nombres)
        assert not sin_agregar, f"un fallo en {list(fallan)} dejo sin agregar {sin_agregar}"
        avisos = re.findall(rf"Aviso: no se pudo asegurar '{TABLA}\.(\w+)': (.*)", salida)
        assert sorted(c for c, _ in avisos) == sorted(fallan), f"debe haber un aviso por cada columna que fallo, y solo por ellas: {avisos}"
        assert all(causa == "falla de prueba" for _, causa in avisos), f"el aviso dice la causa: {avisos}"
        assert "Error al conectar a la base de datos" not in salida, "la cadena de arranque se aborto"
        assert _testigos_del_final_del_arranque(ruta) == set(TESTIGOS_DEL_FINAL_DEL_ARRANQUE), "el resto del arranque no corrio: el indice unico y el trigger no se repusieron"
        assert [f[:len(antes[0])] for f in _consulta(ruta, f"SELECT * FROM {TABLA} ORDER BY id")] == antes, "ni un valor de la fila vieja cambia"
        monkeypatch.setattr(conection_mod, "_asegurar_columna", original)
        _abrir_con_la_app(ruta, monkeypatch)                                                    # la siguiente apertura, sin el fallo, completa la tabla
        assert {n: t for n, t in _columnas(ruta) if n in LAS_CATORCE} == TIPO_DE_LAS_CATORCE


# ================================================================================================================ 3. EL SERVICIO
class TestElServicioGuardaYDevuelveLasCatorce:
    @pytest.mark.parametrize("nombre", sorted(PELICULAS))
    def test_lo_guardado_y_releido_es_exactamente_lo_que_el_motor_midio_en_el_gris_y_en_cada_capa(self, nombre, bd, peliculas):
        pelicula = peliculas[nombre]
        _sembrar_cambio_de_fuente(bd)
        nuevo = _guardar_con_capa(pelicula, "G")
        esperado = medidas_esperadas(pelicula.resultado)
        assert len(esperado) == 30
        listada = [f for f in svc.listar() if f["id"] == nuevo]
        assert len(listada) == 1
        for via, fila in (("leer", svc.leer(nuevo)), ("listar", listada[0]), ("sqlite", _fila_como_dict(bd, nuevo))):
            faltan = sorted(set(esperado) - set(fila))
            assert not faltan, f"{via}: no devuelve {faltan}"
            for clave, valor in esperado.items():
                if clave.startswith("incertidumbre_"):
                    assert fila[clave] == (pytest.approx(valor, rel=1e-12) if valor is not None else None), (via, clave)
                else:
                    assert fila[clave] == valor and type(fila[clave]) is type(valor), (via, clave, fila[clave], valor)

    def test_una_resolucion_otra_guarda_las_medidas_nuevas_en_pixeles_y_sin_milimetros(self, bd, peliculas):
        """La placa real declarando 300 dpi (una resolucion 'otra'): no hay escala ni milimetros, y las 13 medidas nuevas (pixeles y cuentas) se guardan igual y releidas son las del motor."""
        _, color, _, _ = motor.leer_imagen(peliculas["braqui_00"].datos)
        buffer = io.BytesIO()
        Image.fromarray(cv2.cvtColor(color, cv2.COLOR_BGR2RGB)).save(buffer, "TIFF", dpi=(300, 300))
        datos, clics = buffer.getvalue(), peliculas["braqui_00"].clics
        resultado = svc.analizar_imagen(datos, clics)
        assert resultado["tamano_pixel_mm"] is None, "compuerta: 300 dpi declarados es una resolucion 'otra'"
        _sembrar_cambio_de_fuente(bd)
        pelicula = SimpleNamespace(datos=datos, clics=clics, nombre="otra_resolucion.tif")
        fila = svc.leer(_guardar_con_capa(pelicula, "G"))
        esperado = medidas_esperadas(resultado)
        assert fila["tamano_pixel_mm"] is None and all(fila[f"desfase_{s}_mm"] is None for s in SUFIJOS)
        assert fila["media_gris_px"] == esperado["media_gris_px"] and fila["media_g_px"] == esperado["media_g_px"] and fila["filas_b"] == esperado["filas_b"]
        assert fila["dispersion_r_px"] is None and fila["incertidumbre_r_px"] is None, "la capa roja no mide en esta placa"
        for clave, valor in esperado.items():
            if not clave.startswith("incertidumbre_"):
                assert fila[clave] == valor, clave

    @pytest.mark.parametrize("capa", list(CAPAS))
    def test_la_capa_reportada_es_la_que_se_paso_y_la_auditoria_la_nombra(self, capa, bd, peliculas):
        pelicula = peliculas["braqui_00"]
        _sembrar_cambio_de_fuente(bd)
        nuevo = _guardar_con_capa(pelicula, capa)
        assert svc.leer(nuevo)["capa_reportada"] == capa
        assert [f["capa_reportada"] for f in svc.listar()] == [capa]
        assert _fila_como_dict(bd, nuevo)["capa_reportada"] == capa
        (accion, usuario, ref, detalle), = _auditoria(bd)
        assert (accion, usuario, ref) == ("guardar", USUARIO, str(nuevo))
        assert detalle == f"{S1} (fuente {SERIE_A}); {pelicula.nombre}; PI-2; capa reportada {capa}"

    def test_sin_capa_queda_vacia_y_la_auditoria_es_la_de_siempre(self, bd, peliculas):
        pelicula = peliculas["braqui_00"]
        _sembrar_cambio_de_fuente(bd)
        nuevo = svc.guardar(USUARIO, S1, pelicula.datos, pelicula.nombre, pelicula.clics)
        assert "capa_reportada" in svc.leer(nuevo), "leer no devuelve capa_reportada"
        assert svc.leer(nuevo)["capa_reportada"] is None and _fila_como_dict(bd, nuevo)["capa_reportada"] is None
        assert [f["capa_reportada"] for f in svc.listar()] == [None]
        (accion, _, _, detalle), = _auditoria(bd)
        assert accion == "guardar" and detalle == f"{S1} (fuente {SERIE_A}); {pelicula.nombre}; PI-2"

    @pytest.mark.parametrize("capa", ["X", "r", "g", "b", "gris", "GRIS", "", " G", "G ", "RG", 1, 0, ("G",), ["G"]], ids=repr)
    def test_una_capa_que_no_es_R_G_ni_B_se_rechaza_sin_escribir_nada(self, capa, bd, peliculas):
        pelicula = peliculas["braqui_00"]
        _sembrar_cambio_de_fuente(bd)
        with pytest.raises(svc.PosicionInicialError):
            _guardar_con_capa(pelicula, capa)
        assert _filas(bd) == [] and _auditoria(bd) == []

    @pytest.mark.parametrize("capa", ["X", "g", 1], ids=repr)
    @pytest.mark.parametrize("hay_vigente", [True, False], ids=["reemplaza_una_vigente", "reemplaza_sin_vigente"])
    def test_una_capa_invalida_tambien_se_rechaza_al_reemplazar_y_lo_vigente_queda_intacto(self, capa, hay_vigente, bd, peliculas):
        """La validación de la capa no depende de `reemplazar`: con `reemplazar=True` también lanza `PosicionInicialError` (la que la página atrapa), antes de leer nada, y no deja que sea el `CHECK` de la tabla (un
        `IntegrityError` que la página no espera) quien la rechace. Lo vigente conserva su capa, y no se escribe ni se audita nada."""
        pelicula = peliculas["braqui_00"]
        _sembrar_cambio_de_fuente(bd)
        primera = _guardar_con_capa(pelicula, "G") if hay_vigente else None
        antes = (_filas(bd), _auditoria(bd), _fila_como_dict(bd, primera)["capa_reportada"] if hay_vigente else None)
        with pytest.raises(svc.PosicionInicialError, match="capa reportada"):
            _guardar_con_capa(pelicula, capa, reemplazar=True)
        assert (_filas(bd), _auditoria(bd), _fila_como_dict(bd, primera)["capa_reportada"] if hay_vigente else None) == antes

    @pytest.mark.parametrize("capa_anterior", list(CAPAS))
    def test_reemplazar_sin_capa_deja_la_capa_vacia_y_no_hereda_la_de_la_prueba_anterior(self, capa_anterior, bd, peliculas):
        """El plan: `guardar(..., capa_reportada=None)` recibe la capa elegida y *sin ella queda vacía, como hoy*. Reemplazar una prueba que tenía capa, sin pasar otra, deja la nueva SIN capa (y su auditoría no la nombra):
        la capa no se hereda de la anulada, que conserva la suya."""
        pelicula = peliculas["braqui_00"]
        _sembrar_cambio_de_fuente(bd)
        primera = _guardar_con_capa(pelicula, capa_anterior)
        segunda = svc.guardar(USUARIO, S1, pelicula.datos, pelicula.nombre, pelicula.clics, reemplazar=True)
        assert _filas(bd) == [(primera, S1, 0), (segunda, S1, 1)]
        assert _fila_como_dict(bd, primera)["capa_reportada"] == capa_anterior, "la anulada conserva su capa"
        assert _fila_como_dict(bd, segunda)["capa_reportada"] is None, "reemplazar sin capa hereda la de la prueba anterior: la nueva debe quedar sin capa"
        assert svc.leer(segunda)["capa_reportada"] is None
        assert svc.posicion_inicial_para(S1)["capa_reportada"] is None, "lo vigente no tiene capa"
        guardado, reemplazo = _auditoria(bd)
        assert guardado[3].endswith(f"; capa reportada {capa_anterior}")
        assert reemplazo[0] == "reemplazo" and reemplazo[3] == f"{S1} (fuente {SERIE_A}); {pelicula.nombre}; PI-2; reemplaza id={primera}"

    def test_reemplazar_guarda_la_capa_nueva_y_la_anulada_conserva_la_suya(self, bd, peliculas):
        pelicula = peliculas["braqui_00"]
        _sembrar_cambio_de_fuente(bd)
        primera = _guardar_con_capa(pelicula, "G")
        segunda = _guardar_con_capa(pelicula, "B", reemplazar=True)
        assert _filas(bd) == [(primera, S1, 0), (segunda, S1, 1)]
        assert _fila_como_dict(bd, primera)["capa_reportada"] == "G" and _fila_como_dict(bd, segunda)["capa_reportada"] == "B"
        guardado, reemplazo = _auditoria(bd)
        assert guardado[3].endswith("; capa reportada G")
        assert reemplazo[0] == "reemplazo" and reemplazo[3] == f"{S1} (fuente {SERIE_A}); {pelicula.nombre}; PI-2; capa reportada B; reemplaza id={primera}"

    def test_la_firma_de_guardar_agrega_capa_reportada_al_final_y_vacia_por_omision(self):
        parametros = inspect.signature(svc.guardar).parameters
        assert list(parametros) == ["usuario", "fecha", "imagen_bytes", "imagen_nombre", "puntos", "reemplazar", "observaciones", "capa_reportada"]
        assert parametros["capa_reportada"].default is None and parametros["reemplazar"].default is False

    def test_el_insert_y_las_lecturas_nombran_las_catorce_columnas(self):
        insert, lectura = set(svc._COLUMNAS_INSERT), {c.strip() for c in svc._COLUMNAS_SQL.split(",")}
        assert set(LAS_CATORCE) <= insert, sorted(set(LAS_CATORCE) - insert)
        assert set(LAS_CATORCE) <= lectura, sorted(set(LAS_CATORCE) - lectura)
        assert len(insert) == len(svc._COLUMNAS_INSERT) and len(lectura) == len(svc._COLUMNAS_SQL.split(","))

    def test_listar_y_leer_devuelven_las_catorce_aunque_la_fila_este_vacia(self, bd):
        """Una fila sin nada de lo nuevo (sembrada por SQL, como las pruebas de la regla de vigencia): las catorce claves existen y valen None."""
        _sembrar_cambio_de_fuente(bd)
        id_fila = _sql(bd, f"INSERT INTO {TABLA} (fecha, serie_fuente, user, imagen, puntos, parametros, version_algoritmo) VALUES (?, ?, 'Siembra', x'00', '[]', '{{}}', 'PI-2')", (S1, SERIE_A))
        for fila in (svc.leer(id_fila), svc.listar()[0], svc.posicion_inicial_para(S1)):
            assert all(c in fila and fila[c] is None for c in LAS_CATORCE), sorted(set(LAS_CATORCE) - set(fila))


# ================================================================================================================ 4. LA PAGINA
class TestLaPaginaDiceCadaClaveQueCompara:
    def test_cada_clave_de_valores_medidos_tiene_su_rotulo_legible_y_distinto(self):
        rotulos = pagina_mod.ROTULOS_DE_LO_GUARDADO
        faltan, sobran = sorted(CLAVES_DE_VALORES_MEDIDOS - set(rotulos)), sorted(set(rotulos) - CLAVES_DE_VALORES_MEDIDOS)
        assert not faltan and not sobran, f"ROTULOS_DE_LO_GUARDADO: faltan {faltan}; sobran {sobran}"
        assert len(set(rotulos.values())) == len(rotulos) == 30, "un rotulo distinto por clave: dos claves con el mismo texto se confunden en el aviso"
        for clave, rotulo in rotulos.items():
            assert rotulo and rotulo == rotulo.strip() and not re.search(r"[\u2713\u2714\u2715\u2717\u2718\u274c\u2705\u26a0]", rotulo), (clave, rotulo)

    @pytest.mark.parametrize("sufijo", SUFIJOS)
    @pytest.mark.parametrize("plantilla_de_la_clave, como_se_dice", list(zip(LAS_SIETE_MEDIDAS_POR_PERFIL, COMO_SE_DICE_CADA_MEDIDA)), ids=[p.format("*") for p in LAS_SIETE_MEDIDAS_POR_PERFIL])
    def test_cada_rotulo_nombra_el_perfil_la_medida_y_la_unidad_de_su_clave(self, sufijo, plantilla_de_la_clave, como_se_dice):
        """El aviso «reabrir un registro que difiere» lo lee el físico y le dice QUÉ difiere con el rótulo de la clave: el de `dispersion_r_px` no puede decir «azul» ni el de `incertidumbre_g_px` «dispersión» ni el de
        `media_r_px` «[mm]». Lo que debe decir cada clave está escrito arriba (`COMO_SE_DICE_CADA_*`), no sale del código bajo prueba. Cubre las 28 claves por perfil (las 15 de PI.4 y las 13 de B.5)."""
        clave = plantilla_de_la_clave.format(sufijo)
        prefijo, unidad = como_se_dice
        assert clave in pagina_mod.ROTULOS_DE_LO_GUARDADO, f"{clave}: la pagina no tiene rotulo para esta clave (reabrir un registro que difiera lanzaria KeyError)"
        rotulo = pagina_mod.ROTULOS_DE_LO_GUARDADO[clave]
        assert rotulo.startswith(prefijo), f"{clave}: el rotulo {rotulo!r} debe empezar por {prefijo!r}"
        nombrados = [s for s, patron in COMO_SE_DICE_CADA_PERFIL.items() if re.search(rf"\b{patron}\b", rotulo)]
        assert nombrados == [sufijo], f"{clave}: el rotulo {rotulo!r} debe nombrar el perfil {sufijo!r} y ningun otro; nombra {nombrados}"
        if unidad:
            assert rotulo.endswith(unidad), f"{clave}: el rotulo {rotulo!r} debe terminar en {unidad!r}"
        else:
            assert "[" not in rotulo, f"{clave}: el rotulo {rotulo!r} no lleva unidad"

    def test_los_rotulos_de_la_escala_y_del_lado_dicen_de_que_hablan(self):
        """Las dos claves que no son de un perfil: la escala del píxel (en mm) y el lado de la banda de tránsito."""
        rotulos = pagina_mod.ROTULOS_DE_LO_GUARDADO
        assert {"tamano_pixel_mm", "lado_transito"} <= set(rotulos), "la pagina no tiene rotulo para la escala o para el lado"
        assert "píxel" in rotulos["tamano_pixel_mm"] and rotulos["tamano_pixel_mm"].endswith("[mm]"), rotulos["tamano_pixel_mm"]
        assert "tránsito" in rotulos["lado_transito"] and "[" not in rotulos["lado_transito"], rotulos["lado_transito"]

    def test_capa_reportada_no_se_compara_al_abrir_porque_no_se_mide(self, peliculas):
        assert "capa_reportada" not in motor.valores_medidos(peliculas["braqui_00"].resultado) and "capa_reportada" not in pagina_mod.ROTULOS_DE_LO_GUARDADO

    @pytest.mark.parametrize("clave", CLAVES_NUEVAS)
    def test_reabrir_un_registro_que_difiere_en_una_clave_nueva_lo_dice_con_su_rotulo_y_no_lanza(self, clave, peliculas):
        resultado = peliculas["EPSON009"].resultado
        registro = dict(motor.valores_medidos(resultado), version_algoritmo=resultado["version"])
        assert clave in registro, f"valores_medidos no trae {clave}"
        assert pagina_mod.diferencias_con_lo_guardado(registro, resultado) == []
        registro[clave] = registro[clave] + (1 if clave.startswith("filas_") else 0.5)
        diferencias = pagina_mod.diferencias_con_lo_guardado(registro, resultado)
        assert len(diferencias) == 1 and diferencias[0].startswith(f"{pagina_mod.ROTULOS_DE_LO_GUARDADO[clave]}: guardado "), diferencias

    @pytest.mark.parametrize("nombre", sorted(PELICULAS))
    def test_lo_guardado_con_el_escritor_real_y_reabierto_no_da_diferencias(self, nombre, bd, peliculas):
        """Es lo que hace `abrir_registro`: leer, volver a analizar con los bytes, los puntos y los PARAMETROS guardados y comparar las 30 claves."""
        pelicula = peliculas[nombre]
        _sembrar_cambio_de_fuente(bd)
        registro = svc.leer(svc.guardar(USUARIO, S1, pelicula.datos, pelicula.nombre, pelicula.clics))
        faltan = sorted(CLAVES_DE_VALORES_MEDIDOS - set(registro))
        assert not faltan, f"lo guardado no trae {faltan}: la comparacion de la pagina no puede cubrirlas"
        recalculado = svc.analizar_imagen(registro["imagen"], json.loads(registro["puntos"]), json.loads(registro["parametros"]))
        assert pagina_mod.diferencias_con_lo_guardado(registro, recalculado) == []

    def test_un_registro_anterior_a_B5_reabierto_dice_diferencias_solo_en_las_claves_nuevas_y_no_lanza(self, plantilla, monkeypatch, tmp_path, peliculas):
        """DD3: al reabrir se comparan las claves de `valores_medidos` con las guardadas. Un registro hecho con HEAD (no hay ninguno en ninguna base real) no trae las nuevas: la pagina lo dice, nombrando
        SOLO lo nuevo y con su rotulo, y no lanza `KeyError`. Se deja asi a proposito (la pagina no cambia mas que los rotulos)."""
        pelicula = peliculas["EPSON009"]
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=pelicula)
        _abrir_con_la_app(ruta, monkeypatch)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            registro = svc.leer(1)
        finally:
            Conexion._instance = previo
        recalculado = svc.analizar_imagen(registro["imagen"], json.loads(registro["puntos"]), json.loads(registro["parametros"]))
        diferencias = pagina_mod.diferencias_con_lo_guardado(registro, recalculado)
        nuevas = motor.valores_medidos(recalculado)
        assert set(CLAVES_NUEVAS) <= set(nuevas), f"valores_medidos no trae {sorted(set(CLAVES_NUEVAS) - set(nuevas))}"
        esperadas = {pagina_mod.ROTULOS_DE_LO_GUARDADO[c] for c in CLAVES_NUEVAS if nuevas[c] is not None}
        assert len(esperadas) == 13 and {d.split(": guardado ")[0] for d in diferencias} == esperadas and len(diferencias) == 13


# ================================================================================================================ 5. EL OBSERVADOR DE CONTRATO
class TestElObservadorNoVeFalsosCambios:
    def test_las_catorce_columnas_nacen_vacias_y_no_mueven_la_huella_de_la_fila_vieja(self, plantilla, monkeypatch, tmp_path, peliculas):
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=peliculas["EPSON009"])
        antes = obs.capturar(ruta)
        assert antes["vigente"][TABLA], "compuerta: la fila vieja es un bloque vigente del censo"
        _abrir_con_la_app(ruta, monkeypatch)
        despues = obs.capturar(ruta)
        fallos, info = obs.comparar(antes, despues)
        assert fallos == [], fallos
        assert sorted(linea for linea in info if f"columna nueva {TABLA}." in linea) == sorted(f"[esquema] columna nueva {TABLA}.{c}" for c in LAS_CATORCE)
        assert antes["vigente"][TABLA] == despues["vigente"][TABLA]

    def test_un_valor_que_aparece_en_una_columna_nueva_si_cambia_la_huella_de_su_bloque(self, plantilla, monkeypatch, tmp_path, peliculas):
        ruta = _bd_hecha_con_head(plantilla, monkeypatch, tmp_path, con_fila_vieja=peliculas["EPSON009"])
        _abrir_con_la_app(ruta, monkeypatch)
        assert "media_gris_px" in {c[0] for c in _columnas(ruta)}, f"{TABLA}: la migracion no agrego media_gris_px"
        antes = obs.capturar(ruta)
        _sql(ruta, f"UPDATE {TABLA} SET media_gris_px = 1.5 WHERE id = 1")
        fallos, _ = obs.comparar(antes, obs.capturar(ruta))
        assert [f for f in fallos if f.startswith(f"[vigente] {TABLA}")] and all("NO declarado" in f for f in fallos), fallos
