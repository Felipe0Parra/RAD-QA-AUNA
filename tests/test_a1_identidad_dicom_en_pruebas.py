"""A.1 (PLAN_HANDOFF_IMAGENES_22-09.md, ajustada el 23-09): cada prueba de
imagen guarda DE QUE MAQUINA eran las imagenes con las que se corrio.

CAUSA (§0.4): `pruebas` guardaba `kv`, `ma` y `espesor_corte` y nada que
identificara el equipo. Por eso las sesiones 6 y 48 llevan la adquisicion de un
equipo distinto al declarado y nadie podia verlo. Y habia un SEGUNDO camino,
independiente: `kv_actual`/`ma_actual`/`espesor_corte_val` se fijaban una sola
vez al cargar y se aplicaban a todas las pruebas guardadas despues -- con dos
carpetas en una misma sesion, las de la primera quedaban con los parametros de
la segunda (la sesion 47 del 22-09).

GARANTIAS, una por bloque:

  1. LECTURA -- las seis series reales dan modelo, estacion, fecha y
     adquisicion; `fecha_adquisicion` sale de `SeriesDate` (no de `StudyDate`);
     lo que el equipo no publica queda `None`, nunca la cadena "None".
  2. UN SOLO CORTE -- las etiquetas salen del corte espacialmente PRIMERO, el
     mismo del que `DicomVolume` toma `kv`/`ma`: la identidad y el kV/mA de una
     prueba no pueden venir de cortes distintos.
  3. ESQUEMA -- cuatro columnas TEXT aditivas, idempotentes, con `NULL`, que no
     tocan ninguna fila; ensayo sobre COPIA de las BD reales.
  4. GUARDADO -- cada categoria se guarda con SU adquisicion; sin ella (un
     llamador anterior) se conserva el comportamiento de siempre.
  5. SEGUNDO CAMINO -- dos volumenes en la misma sesion no se contaminan.
  6. TRIPWIRES -- ningun resultado guardable se asigna sin registrar su
     adquisicion; ningun llamador de produccion puede omitirla.

Nunca se conecta a una BD de referencia: se copia a un temporal primero.
"""
import ast
import json
import os
import pathlib
import shutil
import sqlite3
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pydicom
import pytest
from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.catphan_TAC.catphan_db import (
    guardar_prueba_completa_catphan, mapear_identidad_dicom)
from analisisImagenes.catphan.serie import (
    CT_IMAGE_STORAGE, adquisicion_de_serie, leer_serie)
from _bd_referencia import BD_A_AJUSTAR, BD_QA, BD_REBUILD_11_09, BD_REBUILD_14_09
from _corpus import serie_catphan

RAIZ = pathlib.Path(__file__).resolve().parent.parent
COLUMNAS_NUEVAS = ("equipo_dicom", "serie_uid", "fecha_adquisicion", "adquisicion_dicom")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


# ---------------------------------------------------------------------------
# 1. LECTURA de las seis series reales
#    Valores [medidos 23-09-2026] sobre el corpus; modelo/estacion coinciden con
#    la tabla de §0.2 del plan.
# ---------------------------------------------------------------------------

ESPERADO = {
    "TOMOGRAFO": dict(
        fabricante="Siemens Healthineers", modelo="SOMATOM go.Sim", estacion="CT128260",
        numero_serie_equipo="128260", software="syngo CT VA40A",
        descripcion_serie="RT_CABEZA 2,00 Qr40 S2", fecha_adquisicion="2026-08-31",
        kv=120.0, ma=200, mas=250, tiempo_exposicion_ms=1250,
        kernel="Qr40f", filtro="W1", fov_mm=550.0, espesor_mm=2.0, n_cortes=102),
    "HALCYON_JUN": dict(
        fabricante="Varian Medical Systems", modelo="Halcyon - PVA", estacion="Halcyon",
        numero_serie_equipo="1161", software="2.37.0.937",
        descripcion_serie="Pelvis Fast_iCBCT_2.0", fecha_adquisicion="2026-06-21",
        kv=125.0, ma=100, mas=591, tiempo_exposicion_ms=5910,
        kernel="None", filtro="Tit V2,HF V2", espesor_mm=2.0, n_cortes=123),
    "HALCYON_SEP": dict(
        fabricante="Varian Medical Systems", modelo="Halcyon - PVA", estacion="Halcyon",
        numero_serie_equipo="1161", software="2.37.0.937",
        descripcion_serie="Pelvis_iCBCT_2.0_IQ!", fecha_adquisicion="2026-09-12",
        kv=125.0, ma=80, mas=1074, tiempo_exposicion_ms=13425,
        filtro="Tit V2,HF V2", espesor_mm=2.0, n_cortes=122),
    "HALCYON_236": dict(
        fabricante="Varian Medical Systems", modelo="Halcyon - PVA", estacion="Halcyon",
        numero_serie_equipo="1161", software="2.36.0.146",
        descripcion_serie=None, fecha_adquisicion="2025-09-13",
        kv=140.0, ma=90, mas=1456, tiempo_exposicion_ms=16180, n_cortes=123),
    "IX_DIC": dict(
        fabricante="Varian Medical Systems", modelo="OBI Cone-beam CT", estacion="IX5005",
        numero_serie_equipo="505", software="2.1.5.11",
        descripcion_serie=None, fecha_adquisicion="2025-12-14",
        kv=100.0, ma=80, mas=724, tiempo_exposicion_ms=9050,
        ctdi_vol_mgy=None, filtro=None, kernel="Ram-Lak", fov_mm=250.0,
        espesor_mm=2.5, n_cortes=70),
    "MIXTA": dict(
        fabricante="Siemens Healthineers", modelo="SOMATOM go.Sim", estacion="CT128260",
        descripcion_serie="RT_CABEZA 1,00 Qr40 S2", fecha_adquisicion="2023-12-15",
        kv=120.0, ma=200, espesor_mm=1.0, n_cortes=278),
}


@pytest.mark.parametrize("clave", sorted(ESPERADO))
def test_las_seis_series_reales_dan_su_identidad_y_adquisicion(clave):
    adq = adquisicion_de_serie(leer_serie(_requerir(clave)))
    for campo, valor in ESPERADO[clave].items():
        if isinstance(valor, float):
            assert adq[campo] == pytest.approx(valor), f"{clave}.{campo}"
        else:
            assert adq[campo] == valor, f"{clave}.{campo}: {adq[campo]!r} != {valor!r}"


def test_la_fecha_es_la_de_la_serie_no_la_del_estudio():
    """§0.10.2: `StudyDate` es la fecha del estudio del fantoma (2023-12-15 en
    cinco de seis carpetas); la de adquisicion es `SeriesDate`."""
    ruta = _requerir("HALCYON_SEP")
    serie = leer_serie(ruta)
    ds = pydicom.dcmread(serie.cortes[0].ruta, stop_before_pixels=True)
    assert str(ds.StudyDate) == "20231215"           # el defecto que la tarea evita
    assert adquisicion_de_serie(serie)["fecha_adquisicion"] == "2026-09-12"


def test_lo_que_el_equipo_no_publica_queda_none_no_la_cadena_none():
    """El iX no trae `AcquisitionDate`, `CTDIvol`, `FilterType` ni
    `SeriesDescription` [medido]. Se guarda ausencia, no texto."""
    adq = adquisicion_de_serie(leer_serie(_requerir("IX_DIC")))
    for campo in ("ctdi_vol_mgy", "filtro", "descripcion_serie"):
        assert adq[campo] is None, f"{campo} debia ser None, es {adq[campo]!r}"
    # y la fecha cae al respaldo (SeriesDate), que el iX si trae
    assert adq["fecha_adquisicion"] == "2025-12-14"


@pytest.mark.parametrize("clave", sorted(ESPERADO))
def test_la_adquisicion_es_serializable_a_json_sin_perdida(clave):
    adq = adquisicion_de_serie(leer_serie(_requerir(clave)))
    assert json.loads(json.dumps(adq, ensure_ascii=False, sort_keys=True)) == adq


# ---------------------------------------------------------------------------
# 2. UN SOLO CORTE: las etiquetas salen del corte espacialmente primero
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", sorted(ESPERADO))
def test_kv_y_ma_de_la_adquisicion_son_los_del_corte_que_usa_dicomvolume(clave):
    """`DicomVolume` toma `kv`/`ma` de `self.cortes[0]` = el corte espacialmente
    primero de `leer_serie`. La identidad debe salir de ESE corte."""
    serie = leer_serie(_requerir(clave))
    ds = pydicom.dcmread(serie.cortes[0].ruta, stop_before_pixels=True)
    adq = adquisicion_de_serie(serie)
    assert adq["kv"] == float(ds.KVP)
    assert adq["ma"] == int(ds.XRayTubeCurrent)


def _escribir_serie_sintetica(carpeta, mas_por_posicion):
    """Serie CT sintetica donde el corte espacialmente PRIMERO NO es el primero
    en disco, y cada corte lleva un `XRayTubeCurrent` distinto (modulacion de
    dosis). Devuelve la lista de posiciones en orden espacial."""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    serie_uid = generate_uid()
    n = len(mas_por_posicion)
    for i, ma in enumerate(mas_por_posicion):
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.SOPClassUID = CT_IMAGE_STORAGE
        ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
        ds.SeriesInstanceUID = serie_uid
        ds.Modality = "CT"
        ds.Manufacturer = "Fabricante Sintetico"
        ds.ManufacturerModelName = "Modelo Sintetico"
        ds.StationName = "ESTACION1"
        ds.KVP = 120
        ds.XRayTubeCurrent = ma
        ds.Rows = 4
        ds.Columns = 4
        ds.PixelSpacing = [1.0, 1.0]
        ds.RescaleSlope = 1
        ds.RescaleIntercept = -1024
        ds.SliceThickness = 2.0
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.ImagePositionPatient = [0, 0, float(i * 2)]
        ds.PixelData = np.zeros((4, 4), dtype=np.int16).tobytes()
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        # Nombre INVERSO a la posicion: el primero en disco es el ULTIMO en el
        # espacio.
        ds.save_as(str(carpeta / f"corte_{n - 1 - i}.dcm"), write_like_original=False)


def test_las_etiquetas_salen_del_corte_espacialmente_primero_no_del_primero_en_disco(tmp_path):
    # posicion 0 -> 111 mA, 1 -> 222, 2 -> 333: si se leyera el primero en disco
    # (corte_0.dcm = posicion 2) saldria 333.
    _escribir_serie_sintetica(tmp_path, [111, 222, 333])
    serie = leer_serie(str(tmp_path))
    assert serie.cortes[0].posicion_mm < serie.cortes[-1].posicion_mm
    assert serie.etiquetas["XRayTubeCurrent"] == 111
    assert adquisicion_de_serie(serie)["ma"] == 111
    # el mismo corte del que DicomVolume toma su `ma`
    primero = pydicom.dcmread(serie.cortes[0].ruta, stop_before_pixels=True)
    assert int(primero.XRayTubeCurrent) == 111


def test_dicomvolume_expone_la_adquisicion_de_su_serie():
    """El visor no relee ningun archivo: expone la misma adquisicion que
    calcula `leer_serie`, y su `kv`/`ma` coinciden con ella."""
    from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume

    ruta = _requerir("IX_DIC")          # la mas pequena del corpus (70 cortes)
    vol = DicomVolume(ruta)
    esperado = adquisicion_de_serie(leer_serie(ruta))
    assert vol.adquisicion == esperado
    assert float(vol.kv) == esperado["kv"]
    assert int(vol.ma) == esperado["ma"]
    assert vol.serie_uid == esperado["serie_uid"]


# ---------------------------------------------------------------------------
# 3. ESQUEMA: cuatro columnas TEXT, aditivas, idempotentes
# ---------------------------------------------------------------------------

def _columnas(ruta, tabla="pruebas"):
    con = sqlite3.connect(ruta)
    try:
        return [(f[1], f[2], f[3]) for f in con.execute(f"PRAGMA table_info({tabla})")]
    finally:
        con.close()


def _abrir_con_la_app(ruta, monkeypatch):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    con = Conexion()
    con.con.close()
    Conexion._instance = None


def _censo_de_filas(ruta):
    con = sqlite3.connect(ruta)
    try:
        tablas = [t[0] for t in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
    finally:
        con.close()


def _huella_pruebas(ruta, columnas):
    con = sqlite3.connect(ruta)
    try:
        filas = con.execute(
            f"SELECT {', '.join(columnas)} FROM pruebas ORDER BY id_prueba").fetchall()
    finally:
        con.close()
    import hashlib
    h = hashlib.sha256()
    for f in filas:
        h.update(repr(f).encode())
    return len(filas), h.hexdigest()


def test_bd_nueva_tiene_las_cuatro_columnas_text_y_admiten_null(tmp_path, monkeypatch):
    ruta = str(tmp_path / "nueva.db")
    _abrir_con_la_app(ruta, monkeypatch)
    cols = {n: (tipo, notnull) for n, tipo, notnull in _columnas(ruta)}
    for nueva in COLUMNAS_NUEVAS:
        assert nueva in cols, f"falta {nueva}: {list(cols)}"
        assert cols[nueva] == ("TEXT", 0), f"{nueva}: {cols[nueva]} (debe ser TEXT y admitir NULL)"


def _bd_legada(tmp_path, monkeypatch):
    """Una BD con `pruebas` SIN las cuatro columnas y con una fila dentro: el
    estado real de cualquier base ya desplegada."""
    ruta = str(tmp_path / "legada.db")
    _abrir_con_la_app(ruta, monkeypatch)
    con = sqlite3.connect(ruta)
    if sqlite3.sqlite_version_info < (3, 35, 0):
        con.close()
        pytest.skip("SQLite < 3.35: sin DROP COLUMN para fabricar la BD legada")
    for c in COLUMNAS_NUEVAS:
        con.execute(f"ALTER TABLE pruebas DROP COLUMN {c}")
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('Halcyon', 'Mensual', '06/2026')")
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.execute(
        "INSERT INTO pruebas (id_sesion, id_tipo, kv, ma, espesor_corte, created_at, equipo) "
        "VALUES (?, 1, 125, 80, 2.0, '2026-06-01', 'Halcyon TAC')", (ref,))
    con.commit()
    assert not set(COLUMNAS_NUEVAS) & {n for n, _, _ in _columnas(ruta)}, "la BD legada debia carecer de las columnas"
    con.close()
    return ruta


def test_bd_legada_gana_las_columnas_sin_tocar_ninguna_fila(tmp_path, monkeypatch):
    ruta = _bd_legada(tmp_path, monkeypatch)
    previas = [n for n, _, _ in _columnas(ruta)]
    antes = _huella_pruebas(ruta, previas)

    _abrir_con_la_app(ruta, monkeypatch)

    nombres = [n for n, _, _ in _columnas(ruta)]
    for nueva in COLUMNAS_NUEVAS:
        assert nueva in nombres
    assert _huella_pruebas(ruta, previas) == antes, "A.1 cambio el contenido de `pruebas`"
    con = sqlite3.connect(ruta)
    try:
        nulos = con.execute(
            "SELECT COUNT(*) FROM pruebas WHERE equipo_dicom IS NULL AND serie_uid IS NULL "
            "AND fecha_adquisicion IS NULL AND adquisicion_dicom IS NULL").fetchone()[0]
    finally:
        con.close()
    assert nulos == antes[0], "las filas historicas deben quedar en NULL (sin relleno retroactivo)"


def test_segunda_apertura_es_idempotente(tmp_path, monkeypatch):
    ruta = _bd_legada(tmp_path, monkeypatch)
    _abrir_con_la_app(ruta, monkeypatch)
    uno = _columnas(ruta)
    _abrir_con_la_app(ruta, monkeypatch)
    dos = _columnas(ruta)
    assert uno == dos
    for nueva in COLUMNAS_NUEVAS:
        assert [n for n, _, _ in dos].count(nueva) == 1


@pytest.mark.parametrize("origen", [BD_QA, BD_A_AJUSTAR, BD_REBUILD_11_09, BD_REBUILD_14_09],
                         ids=lambda p: p.name)
def test_ensayo_sobre_copia_de_bd_real(origen, tmp_path, monkeypatch):
    """Punto 6 del protocolo (CLAUDE.md): ensayo previo sobre COPIA."""
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")
    ruta = str(tmp_path / "copia_real.db")
    shutil.copy(origen, ruta)

    censo_antes = _censo_de_filas(ruta)
    previas = [n for n, _, _ in _columnas(ruta)]
    huella_antes = _huella_pruebas(ruta, previas) if previas else None
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
    assert fk_despues <= fk_antes, f"foreign_key_check AUMENTO: {fk_antes} -> {fk_despues}"

    nombres = [n for n, _, _ in _columnas(ruta)]
    for nueva in COLUMNAS_NUEVAS:
        assert nueva in nombres
    if huella_antes is not None:
        assert _huella_pruebas(ruta, previas) == huella_antes, "cambio el contenido previo de `pruebas`"

    censo_despues = _censo_de_filas(ruta)
    for tabla, n in censo_antes.items():
        assert censo_despues.get(tabla) == n, f"el censo de '{tabla}' cambio: {n} -> {censo_despues.get(tabla)}"

    _abrir_con_la_app(ruta, monkeypatch)                # segunda corrida
    assert [n for n, _, _ in _columnas(ruta)] == nombres
    assert _censo_de_filas(ruta) == censo_despues


# ---------------------------------------------------------------------------
# 4. GUARDADO: cada categoria con SU adquisicion
# ---------------------------------------------------------------------------

@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _crear_control(ruta, equipo="Halcyon", fecha="06/2026"):
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)", (equipo, fecha))
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


def _adq(modelo, estacion, kv, ma, espesor, uid, fecha="2026-09-12"):
    """Un registro `{"kv", "ma", "espesor_corte", "adquisicion"}` como el que
    arma `PruebaMensualTAC._registrar_adquisicion`."""
    return {
        "kv": kv, "ma": ma, "espesor_corte": espesor,
        "adquisicion": {
            "fabricante": "F", "modelo": modelo, "estacion": estacion,
            "serie_uid": uid, "fecha_adquisicion": fecha, "kv": kv, "ma": ma,
            "espesor_mm": espesor, "ctdi_vol_mgy": None,
        },
    }


# Resultado minimo VALIDO de `uniformidad` (id_tipo 7). No se usa `tamano_pixel`:
# su guardado esta roto en produccion por una columna inexistente (`error_pct`,
# DP-41), ajeno a esta tarea.
UNIFORMIDAD = {"Uniformidad": {"max_diferencia": 1.0}, "Centro": {"promedio_hu": 1.0, "desviacion": 2.0}}


def _guardar(sesion, categorias, **kw):
    base = dict(user_id="fisico1", fecha="2026-06-01", equipo="Halcyon TAC",
                kv=120, ma=100, espesor_corte=1.5,
                resultados_por_categoria=categorias, id_sesion=sesion)
    base.update(kw)
    return guardar_prueba_completa_catphan(**base)


def _fila(ruta, sesion, id_tipo):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(
            "SELECT kv, ma, espesor_corte, equipo_dicom, serie_uid, fecha_adquisicion, "
            "adquisicion_dicom FROM pruebas WHERE id_sesion=? AND id_tipo=? "
            "AND (activo IS NULL OR activo=1)", (sesion, id_tipo)).fetchone()
    finally:
        con.close()


def test_guardar_escribe_y_relee_la_identidad(bd_temporal):
    sesion = _crear_control(bd_temporal)
    adq = _adq("Halcyon - PVA", "Halcyon", 125.0, 80, 2.0, "1.2.3.4")
    assert _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.1}},
                    adquisicion_por_categoria={"espesor": adq}) is not None
    kv, ma, esp, equipo_dicom, uid, fecha, blob = _fila(bd_temporal, sesion, 1)
    assert (kv, ma, esp) == (125.0, 80, 2.0)
    assert equipo_dicom == "Halcyon - PVA / Halcyon"
    assert uid == "1.2.3.4"
    assert fecha == "2026-09-12"
    assert json.loads(blob) == adq["adquisicion"]


def test_sin_adquisicion_se_comporta_como_siempre_y_deja_null(bd_temporal):
    """Un llamador anterior (no pasa `adquisicion_por_categoria`): kv/ma/
    espesor son los de la llamada y la identidad queda en NULL -- nunca un
    valor inventado."""
    sesion = _crear_control(bd_temporal)
    _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.1}})
    kv, ma, esp, *identidad = _fila(bd_temporal, sesion, 1)
    assert (kv, ma, esp) == (120, 100, 1.5)
    assert identidad == [None, None, None, None]


def test_dos_categorias_de_una_misma_llamada_guardan_cada_una_la_suya(bd_temporal):
    """La CLASE del segundo camino, a nivel de guardado: antes habia UN kv/ma/
    espesor para toda la llamada."""
    sesion = _crear_control(bd_temporal)
    tomografo = _adq("SOMATOM go.Sim", "CT128260", 120.0, 200, 2.0, "uid-tomografo", "2026-08-31")
    halcyon = _adq("Halcyon - PVA", "Halcyon", 125.0, 80, 2.0, "uid-halcyon", "2026-09-12")
    _guardar(
        sesion,
        {"espesor": {"espesor_promedio_mm": 2.0},
         "uniformidad": UNIFORMIDAD},
        adquisicion_por_categoria={"espesor": tomografo, "uniformidad": halcyon},
    )
    esp = _fila(bd_temporal, sesion, 1)
    pix = _fila(bd_temporal, sesion, 7)
    assert (esp[0], esp[1], esp[3], esp[4]) == (120.0, 200, "SOMATOM go.Sim / CT128260", "uid-tomografo")
    assert (pix[0], pix[1], pix[3], pix[4]) == (125.0, 80, "Halcyon - PVA / Halcyon", "uid-halcyon")


def test_una_categoria_sin_adquisicion_no_hereda_la_de_otra(bd_temporal):
    sesion = _crear_control(bd_temporal)
    _guardar(
        sesion,
        {"espesor": {"espesor_promedio_mm": 2.0},
         "uniformidad": UNIFORMIDAD},
        adquisicion_por_categoria={"espesor": _adq("Halcyon - PVA", "Halcyon", 125.0, 80, 2.0, "u")},
    )
    assert _fila(bd_temporal, sesion, 1)[4] == "u"
    kv, ma, esp, *identidad = _fila(bd_temporal, sesion, 7)
    assert (kv, ma, esp) == (120, 100, 1.5)          # los de la llamada
    assert identidad == [None, None, None, None]     # y NADA de la otra categoria


def test_reguardar_conserva_la_identidad_de_la_generacion_anulada(bd_temporal):
    """EB2c sigue en pie: la fila anterior se ANULA, no se borra, y conserva SU
    identidad; la nueva lleva la suya."""
    sesion = _crear_control(bd_temporal)
    _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.0}},
             adquisicion_por_categoria={"espesor": _adq("Halcyon - PVA", "Halcyon", 125.0, 80, 2.0, "vieja")})
    _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.1}},
             adquisicion_por_categoria={"espesor": _adq("OBI Cone-beam CT", "IX5005", 100.0, 80, 2.5, "nueva")})
    con = sqlite3.connect(bd_temporal)
    try:
        filas = con.execute(
            "SELECT serie_uid, activo FROM pruebas WHERE id_sesion=? AND id_tipo=1 ORDER BY id_prueba",
            (sesion,)).fetchall()
    finally:
        con.close()
    assert filas == [("vieja", 0), ("nueva", 1)]


@pytest.mark.parametrize("adq,esperado", [
    (None, (None, None, None, None)),
    ({}, (None, None, None, None)),
    ({"modelo": "M", "estacion": None, "serie_uid": "u", "fecha_adquisicion": None},
     ("M", "u", None)),
    ({"modelo": None, "estacion": "E", "serie_uid": "u", "fecha_adquisicion": "2026-01-01"},
     ("E", "u", "2026-01-01")),
    ({"modelo": None, "estacion": None, "serie_uid": None, "fecha_adquisicion": None},
     (None, None, None)),
])
def test_mapear_identidad_no_inventa_lo_que_falta(adq, esperado):
    resultado = mapear_identidad_dicom(adq)
    if esperado == (None, None, None, None):
        assert resultado == esperado
    else:
        assert resultado[:3] == esperado
        assert json.loads(resultado[3]) == adq


# ---------------------------------------------------------------------------
# 5. SEGUNDO CAMINO en la pantalla: dos volumenes en la misma sesion
# ---------------------------------------------------------------------------

def _pantalla(app):
    from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
    obj = PruebaMensualTAC.__new__(PruebaMensualTAC)
    QWidget.__init__(obj)
    obj.adquisicion_por_categoria = {}
    obj.criterios_por_categoria = {}      # G.3: lo que `__init__` inicializa junto a la adquisicion
    return obj


def _vol(kv, ma, espesor, adquisicion):
    return types.SimpleNamespace(kv=kv, ma=ma, espesor_corte=espesor, adquisicion=adquisicion)


def test_cargar_otra_carpeta_no_reescribe_la_adquisicion_de_lo_ya_analizado(app):
    pantalla = _pantalla(app)
    vol_a = _vol(120.0, 200, 2.04, {"modelo": "SOMATOM go.Sim", "serie_uid": "A"})
    vol_b = _vol(125.0, 80, 2.0, {"modelo": "Halcyon - PVA", "serie_uid": "B"})
    pantalla.visualizador_principal = types.SimpleNamespace(vol=vol_a)

    pantalla._registrar_adquisicion("espesor")                 # se corre con A
    pantalla.visualizador_principal.vol = vol_b                # se carga otra carpeta
    pantalla.asignar_parametros_adquisicion()                  # lo que hacia el defecto
    assert pantalla.kv_actual == 125.0                         # el estado global SI se pisa...
    pantalla._registrar_adquisicion("uniformidad")              # ...se corre con B

    snap = pantalla.adquisicion_por_categoria
    assert snap["espesor"]["kv"] == 120.0 and snap["espesor"]["adquisicion"]["serie_uid"] == "A"
    assert snap["espesor"]["espesor_corte"] == 2.0             # redondeado a 1 decimal
    assert snap["uniformidad"]["kv"] == 125.0 and snap["uniformidad"]["adquisicion"]["serie_uid"] == "B"


def test_end_to_end_las_pruebas_de_la_primera_carpeta_no_quedan_con_los_parametros_de_la_segunda(
        app, bd_temporal):
    pantalla = _pantalla(app)
    pantalla.visualizador_principal = types.SimpleNamespace(
        vol=_vol(120.0, 200, 2.0, {"modelo": "SOMATOM go.Sim", "estacion": "CT128260",
                                   "serie_uid": "A", "fecha_adquisicion": "2026-08-31"}))
    pantalla._registrar_adquisicion("espesor")
    pantalla.visualizador_principal.vol = _vol(
        125.0, 80, 2.0, {"modelo": "Halcyon - PVA", "estacion": "Halcyon",
                         "serie_uid": "B", "fecha_adquisicion": "2026-09-12"})
    pantalla.asignar_parametros_adquisicion()
    pantalla._registrar_adquisicion("uniformidad")

    sesion = _crear_control(bd_temporal)
    _guardar(
        sesion,
        {"espesor": {"espesor_promedio_mm": 2.0},
         "uniformidad": UNIFORMIDAD},
        # lo que el guardado de la pantalla envia hoy: los kv/ma del ULTIMO volumen
        kv=pantalla.kv_actual, ma=pantalla.ma_actual, espesor_corte=pantalla.espesor_corte_val,
        adquisicion_por_categoria=pantalla.adquisicion_por_categoria)
    esp, pix = _fila(bd_temporal, sesion, 1), _fila(bd_temporal, sesion, 7)
    assert (esp[0], esp[1], esp[4]) == (120.0, 200, "A"), "espesor quedo con los parametros de la 2.a carpeta"
    assert (pix[0], pix[1], pix[4]) == (125.0, 80, "B")


def test_sin_volumen_no_se_inventa_una_adquisicion(app):
    pantalla = _pantalla(app)
    pantalla.visualizador_principal = types.SimpleNamespace(vol=None)
    pantalla.adquisicion_por_categoria["espesor"] = {"kv": 1}
    pantalla._registrar_adquisicion("espesor")
    assert "espesor" not in pantalla.adquisicion_por_categoria


def test_la_linealidad_hereda_la_adquisicion_de_valores_ct_si_se_corrio_en_la_sesion(app):
    """La linealidad se calcula desde los HU de `valores_ct`: su adquisicion es
    la de ESA prueba aunque despues se haya cargado otra carpeta."""
    pantalla = _pantalla(app)
    pantalla.visualizador_principal = types.SimpleNamespace(vol=_vol(120.0, 200, 2.0, {"serie_uid": "A"}))
    pantalla._registrar_adquisicion("valores_ct")
    pantalla.visualizador_principal.vol = _vol(125.0, 80, 2.0, {"serie_uid": "B"})   # otra carpeta

    pantalla._registrar_adquisicion_linealidad()

    snap = pantalla.adquisicion_por_categoria
    assert snap["linealidad_ct"]["adquisicion"]["serie_uid"] == "A", (
        "la linealidad quedo con la adquisicion del volumen activo, no la de valores_ct")
    assert snap["linealidad_ct"]["kv"] == 120.0


def test_la_linealidad_sin_valores_ct_en_la_sesion_usa_el_volumen_activo(app):
    """Si `valores_ct` no se corrio en esta sesion (vino de la BD), no hay una
    adquisicion mejor que la del volumen activo."""
    pantalla = _pantalla(app)
    pantalla.visualizador_principal = types.SimpleNamespace(vol=_vol(125.0, 80, 2.0, {"serie_uid": "B"}))
    pantalla._registrar_adquisicion_linealidad()
    assert pantalla.adquisicion_por_categoria["linealidad_ct"]["adquisicion"]["serie_uid"] == "B"


def test_limpiar_resultados_limpia_tambien_las_adquisiciones(app):
    pantalla = _pantalla(app)
    for c in ("espesor", "uniformidad"):
        pantalla.adquisicion_por_categoria[c] = {"kv": 1}
    pantalla.limpiar_resultados_catphan("espesor")
    assert list(pantalla.adquisicion_por_categoria) == ["uniformidad"]
    pantalla.limpiar_resultados_catphan()
    assert pantalla.adquisicion_por_categoria == {}


# ---------------------------------------------------------------------------
# 6. TRIPWIRES censales (derivados del codigo, no de una lista escrita a mano)
# ---------------------------------------------------------------------------

ARCHIVO_PANTALLA = RAIZ / "ui/paginasControles/PruebasMensuales/tac_mensual.py"

# atributo `self.resultados_*` -> categoria de la BD (las que usa
# `guardar_prueba_completa_catphan`)
CATEGORIA_DE_ATRIBUTO = {
    "resultados_espesor": "espesor",
    "resultados_tamano_pixel": "tamano_pixel",
    "resultados_resolucion_contraste": "resolucion_contraste",
    "resultados_resolucion_espacial": "resolucion_espacial",
    "resultados_ct": "valores_ct",
    "resultados_linealidad_ct": "linealidad_ct",
    "resultados_uniformidad": "uniformidad",
}

# Asignaciones que NO corren un analisis: los resultados vienen ya de la BD (su
# adquisicion es la que se guardo entonces, no la del volumen activo); NO se
# registra ninguna y el guardado cae al comportamiento de siempre.
ASIGNACIONES_DESDE_BD = {("cargar_valores_ct_desde_bd", "resultados_ct")}


def _funciones(arbol):
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield nodo


def _es_self_attr(nodo, nombre=None):
    return (isinstance(nodo, ast.Attribute) and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "self" and (nombre is None or nodo.attr == nombre))


def _categorias_registradas(nodo_raiz):
    """Categorias que `nodo_raiz` registra: `_registrar_adquisicion('x')`, o
    `_registrar_adquisicion_linealidad()` (que registra 'linealidad_ct')."""
    categorias = set()
    for n in ast.walk(nodo_raiz):
        if not isinstance(n, ast.Call):
            continue
        if _es_self_attr(n.func, "_registrar_adquisicion") and n.args and isinstance(n.args[0], ast.Constant):
            categorias.add(n.args[0].value)
        elif _es_self_attr(n.func, "_registrar_adquisicion_linealidad"):
            categorias.add("linealidad_ct")
    return categorias


def test_todo_resultado_guardable_registra_su_adquisicion():
    """Cada asignacion `self.resultados_X = <algo distinto de None>` debe ir con
    su `self._registrar_adquisicion('<categoria>')` en la MISMA funcion. Sin
    esto, un analisis nuevo o movido vuelve a guardarse con los parametros del
    ultimo volumen cargado."""
    arbol = ast.parse(ARCHIVO_PANTALLA.read_text(encoding="utf-8"))
    faltan = []
    vistas = set()
    for func in _funciones(arbol):
        registradas = _categorias_registradas(func)
        for nodo in ast.walk(func):
            if not isinstance(nodo, ast.Assign):
                continue
            for objetivo in nodo.targets:
                if _es_self_attr(objetivo) and objetivo.attr in CATEGORIA_DE_ATRIBUTO:
                    if isinstance(nodo.value, ast.Constant) and nodo.value.value is None:
                        continue                       # `= None`: es limpiar
                    vistas.add(objetivo.attr)
                    if (func.name, objetivo.attr) in ASIGNACIONES_DESDE_BD:
                        continue
                    if CATEGORIA_DE_ATRIBUTO[objetivo.attr] not in registradas:
                        faltan.append((func.name, objetivo.attr, nodo.lineno))
    assert not faltan, f"resultados asignados sin registrar su adquisicion: {faltan}"
    # y el censo no es vacuo: las 7 categorias se asignan en algun sitio
    assert vistas == set(CATEGORIA_DE_ATRIBUTO), f"categorias sin ningun sitio de asignacion: {set(CATEGORIA_DE_ATRIBUTO) - vistas}"


def test_las_categorias_registradas_son_las_que_guarda_la_pantalla():
    """Los nombres de `_registrar_adquisicion('x')` son las claves con las que
    `guardar_resultados_catphan` arma `resultados_por_categoria`."""
    arbol = ast.parse(ARCHIVO_PANTALLA.read_text(encoding="utf-8"))
    registradas = _categorias_registradas(arbol)
    guardadas = set()
    for func in _funciones(arbol):
        if func.name != "guardar_resultados_catphan":
            continue
        for nodo in ast.walk(func):
            if (isinstance(nodo, ast.Subscript) and isinstance(nodo.value, ast.Name)
                    and nodo.value.id == "resultados_por_categoria"
                    and isinstance(nodo.slice, ast.Constant)):
                guardadas.add(nodo.slice.value)
    assert guardadas, "no se encontro guardar_resultados_catphan"
    assert registradas == guardadas, (registradas ^ guardadas)


def test_ningun_llamador_de_produccion_omite_la_adquisicion_por_categoria():
    """Un llamador que la omita guarda `NULL` en la identidad SIN AVISAR: es
    exactamente el hueco que A.1 cierra."""
    llamadores = []
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")):
            continue
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if (isinstance(nodo, ast.Call)
                    and getattr(nodo.func, "id", getattr(nodo.func, "attr", None)) == "guardar_prueba_completa_catphan"):
                llamadores.append((rel, nodo.lineno, {k.arg for k in nodo.keywords}))
    assert llamadores, "el censo no encontro ningun llamador (ya no es una prueba)"
    sin = [(r, l) for r, l, kws in llamadores if "adquisicion_por_categoria" not in kws]
    assert not sin, f"llamadores de produccion sin `adquisicion_por_categoria`: {sin}"
