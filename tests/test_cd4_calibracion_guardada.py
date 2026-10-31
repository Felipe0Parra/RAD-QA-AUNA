"""CD.4 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, bloque CD.4, DA-90): DÓNDE VIVE UNA CALIBRACIÓN -- las dos tablas del contrato (`calibracion_pelicula`, raíz propia sin FK, y `calibracion_pelicula_pieza`, su
hija), los escaneos junto a la base y su ÚNICA puerta, `services/curva_dosis.py`.

CAUSA: nada guardaba una calibración.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del servicio (el motor de CD.3 llamado aquí, la base leída con `sqlite3` a mano y el sha256 de los bytes):
  (1) El esquema: `Conexion()` crea las dos tablas con sus columnas (la raíz sin FK, la hija con FK `ref` RESTRICT), `activo` lo agrega el arranque, `crear_indices` crea los dos índices únicos parciales
      (clave de bloque (`lote`, `DATE(fecha_irradiacion)`, `energia`) y (`ref`, `orden`)), una segunda apertura no cambia nada, y las listas del contrato (TABLAS_ANULABLES, CLAVES_INDICE, RAICES_QC) las nombran.
  (2) Guardar y leer con el escritor real: lo guardado es EXACTAMENTE lo que miden CD.2 y ajusta CD.3 sobre los mismos bytes; una fila de auditoría con el lote, la fecha y el estado de cada capa.
  (3) Reemplazar (la misma clave de bloque) y anular: la vigente y sus piezas quedan anuladas, la auditoría dice «reemplazo» o «anular», y `leer(id)` de lo anulado lo devuelve igual, con sus piezas.
  (4) Los escaneos: se copian junto a la base con su huella, la copia se comprueba leyéndola y nunca se sobrescribe; una copia que falla no deja nada en la base.
  (5) `recalcular` sin los escaneos y con ellos da lo mismo y `diferencias` no ve nada; lo guardado alterado sí se ve.
  (6) La auditoría va en la transacción del guardado y un fallo a mitad no deja nada.
  (7) La puerta estricta de los JSON (la de D.1): NaN, infinito o un escalar de numpy no entran.
  (8) Lo que el servicio rechaza ANTES de escribir.
  (9) La selectividad (DA-47) y la Trampa 6, por AST: las lecturas por la clave de bloque filtran `activo` dentro del f-string; `leer(id)` no; nadie más escribe en estas tablas.
  (10) `vigentes_validas`: solo lo vigente con una capa «válida», la más reciente primero.
  (11) La película virgen montada: su copia viaja con la calibración y `recalcular` usa ESA copia (DA-81).
  (12) Las 21 piezas reales de H9 (regla de PR.0): se guardan, sus estados son los de CD.3 y lo guardado se rehace igual.
  (13) La ampliacion del implementador (30-10): cada validacion de entrada del encabezado y de las piezas, que el equipo y la fecha del EXIF de cada pieza son los que lee CD.2, el orden y el empate de las
       lecturas, un escaneo ilegible, los textos de `diferencias` y su tolerancia por los dos lados, y la forma canonica de los JSON guardados (mutaciones E01..E56 de `cd4_mutaciones.py`).
  (14) La correccion de la ronda 1 de la revision (30-10): huecos que los revisores mostraron con una mutacion que sobrevivia a los casos de arriba (E57..E69 de `cd4_mutaciones.py`) -- la regla «al menos UNA
       capa valida» de `vigentes_validas` con unas capas validas y otras no (el rojo recortado) y con una curva «guia», el LOTE como parte de la clave de bloque, el censo de escritores por AST con las primitivas
       del contrato (el patron de D.1 y de C.3), la decision CD4-D8 con UN escaneo de menos, el CONTENIDO de `escaneos_que_faltan` y la medicion guardada ENTERA de cada pieza (CD4-D11).
  (15) La decision de Opus de la ronda 1 (30-10, CD4-R1-D1 a D3; mutaciones R1-D1-M1..M16, R1-D2-M1..M4 y R1-D3-M1..M7 de `cd4_mutaciones.py`): los valores de `parametros_de_la_curva` se validan por el tipo de
       su valor de fabrica (`modelo` y `version` solo se admiten iguales), todo numero que entra cabe en la base y en sus mensajes (un entero de mas de 4300 cifras tampoco rompe el mensaje) y `-0.0` se guarda
       `0.0`; `recalcular` no vuelve a medir una copia que ya no es su huella y `diferencias` lo dice (`Recalculo.escaneos_que_no_coinciden`); y una copia que no es su huella nunca queda bloqueando en silencio:
       la que escribio el guardado se quita, la que ya estaba se mide antes y no se toca (el rechazo dice que hay que apartarla a mano).
  (16) La ronda 2 de la revision (30-10, CD4-R2-PRU-01 a PROD-02; mutaciones R2-* y la E02 reubicada de `cd4_mutaciones.py`): el PISO del rango de 64 bits (`-2**63 - 1` en el orden y en los dos `equipo_id`, y `-2**63`
       exacto, que si cabe), un entero de mas de 4300 cifras en el mensaje del orden y del `equipo_id` que no caben (y, por la medicion sitio a sitio de `_como_texto`, en los otros cuatro sitios de `guardar` que
       interpolan un valor del llamador: CD4-R2-M1), el mensaje ENTERO con que se rechaza un `modelo` o una `version` que no son los del motor, el
       mensaje de CD.3 (llamado alli mismo) con que se rechaza una dosis nan, inf, -inf, bool o texto, y `recalcular` con una copia que existe y no se puede leer (`CurvaDosisError`, no un `OSError` crudo).
  (17) El barrido por AST de la ronda 2 (30-10, BARREDOR; mutaciones R2-BA-001..071 de `cd4_mutaciones.py`): los 71 sobrevivientes del barrido sistematico del servicio que eran huecos de prueba.
  (18) La ronda 3 de la revision, parte 1 (30-10, APLICADOR 1; mutaciones R3C-D1..D8 de `cd4_mutaciones.py`): las ocho decisiones del supervisor CD4-R3-D1 a D8 -- el usuario validado UNA vez en la frontera y ese texto a la fila y a
       la auditoria (un usuario que no es un texto se rechaza), el id de la calibracion (un entero que cabe en la base), las condiciones (solo `None` da `{}`, claves de texto a cualquier profundidad con un recorrido iterativo que
       no cuelga con una estructura recursiva) y el modo de escaneo (un texto de la lista), una copia que no se puede comprobar en `recalcular` (no es una copia que falta), la fecha escrita a mano (el año 999 es `0999`),
       `_como_texto` ante un `repr` que lanza, lo que no se puede escribir en UTF-8 (un surrogado) rechazado antes de copiar nada y el parrafo «Contrato del llamador» del docstring del modulo.
  (19) La ronda 3 de la revision, parte 2 (30-10, APLICADOR 2; mutaciones R3C-PRU01-M1/M2 y R3C-PRU03-M1/M2 de `cd4_mutaciones.py`; SOLO pruebas, la produccion no cambia): un real negativo que redondea a -0.0
       (`Fraction(-1, 10**400)`, `np.longdouble('-1e-400')`) se acepta y se guarda como 0.0 en la incertidumbre de la dosis y en los parametros de la curva (CD4-R3-PRU-01: B079 y B207 del barrido no eran equivalentes) y la TABLA
       de los textos EXACTOS de los rechazos de `guardar` y de las copias que solo se comprobaban por subcadena (CD4-R3-PRU-03: un texto que miente sobre la causa -«le faltan []», «la pieza 2» donde era la 7- no pasa).

Rojo contra HEAD (28851ae): el servicio no existe y las tablas tampoco; caen todas las que los usan.
"""
import ast
import builtins
import copy
import dataclasses
import decimal
import fractions
import hashlib
import importlib
import io
import json
import math
import os
import re
import shutil
import signal
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

import _corpus
import _piezas_de_calibracion_sinteticas as gen
import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import crear_indices

RAIZ = Path(__file__).resolve().parent.parent
TABLA, PIEZAS = "calibracion_pelicula", "calibracion_pelicula_pieza"
CAPAS = ("R", "G", "B", "gris")
DOSIS = (50, 100, 150, 200, 300, 400, 500, 600, 800, 1000)
DEVIC = (gen.RespuestaDevic(700.0, 3300.0, 2.06), gen.RespuestaDevic(1100.0, 4600.0, 2.19), gen.RespuestaDevic(1750.0, 8200.0, 1.58))
GRANDE = 50.0                                                       # piezas de 5 x 5 cm: con el ruido de EPSON179 las cuatro capas salen «válidas» (CD.3)
CARPETA = "calibraciones_pelicula_escaneos"
VALIDA = "válida"
LAS_CUATRO_PRIMERAS = {1, 2, 3, 4}                                  # 0, 50, 100 y 150 cGy: una calibracion INCOMPLETA (hacen falta 6 dosis) y la mas barata de guardar (seccion 15)
ENORME = 10**5000                                                   # de mas de 4300 cifras: `repr` y `str` lanzan ValueError (el limite de Python 3.11); sus pruebas llevan `ids` explicitos (seccion 15)

COLUMNAS_RAIZ = ["id", "lote", "tipo_pelicula", "fecha_irradiacion", "acelerador", "energia", "condiciones", "camara_modelo", "camara_serie", "camara_factor", "camara_equipo_id", "electrometro_modelo", "electrometro_serie", "electrometro_factor", "electrometro_equipo_id", "u_dosis_medida_pct", "cadena_de_captura", "cero", "virgen", "parametros", "modelo", "version", "ajuste", "estado", "observaciones", "usuario", "fecha_registro", "activo"]
COLUMNAS_PIEZA = ["id", "ref", "orden", "dosis_nominal_cgy", "dosis_medida_cgy", "nombre_archivo", "sha256", "bytes", "formato", "bits", "dpi_declarado", "equipo", "fecha_exif", "dimensiones_px", "escaner_declarado", "fecha_escaneo", "posicion_mm", "medida", "estado", "activo"]

ENCABEZADO = {"lote": "L-01", "tipo_pelicula": "EBT3", "fecha_irradiacion": "2026-10-20", "energia": "6 MV", "acelerador": "Clinac iX",
              "condiciones": {"profundidad_cm": 3.0, "dfs_cm": 100.0, "campo_cm": 10.0}, "camara": {"modelo": "FC65-G", "serie": "1234", "factor": 4.85e-2, "equipo_id": 19},
              "electrometro": {"modelo": "Dose 1", "serie": "5678", "factor": None, "equipo_id": None}, "u_dosis_medida_pct": 1.5, "escaner_declarado": "Epson WF-6590",
              "modo_de_escaneo": "reflexión", "observaciones": "prueba"}


def _svc():
    """El servicio, importado POR PRUEBA (en HEAD no existe y cada prueba que lo usa cae con su error)."""
    return importlib.import_module("services.curva_dosis")


def _cd():
    return importlib.import_module("analisisImagenes.curva_dosis")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _P():
    return copy.deepcopy(importlib.import_module("analisisImagenes.placa_mensual").VALORES_DE_LA_GEOMETRIA)


def _sql(ruta, consulta, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        filas = con.execute(consulta, parametros).fetchall()
        con.commit()
        return filas
    finally:
        con.close()


# ===================================================================================================== las piezas y la base

@pytest.fixture(scope="module")
def escaneos():
    """Los bytes de una calibración sintética (la plantilla del §7 en piezas de 5 x 5 cm): {orden: (dosis, nombre, bytes)}; la de 0 cGy es la 1."""
    salida = {1: (0, "0.tif", gen.pieza_de_dosis(0, DEVIC, lado_mm=GRANDE, semilla=1).datos)}
    for k, d in enumerate(DOSIS):
        salida[k + 2] = (d, f"{d}.tif", gen.pieza_de_dosis(d, DEVIC, lado_mm=GRANDE, semilla=k + 2).datos)
    return salida


def _piezas(escaneos, cuales=None):
    return [{"orden": o, "dosis_nominal_cgy": float(d), "dosis_medida_cgy": float(d), "datos": datos, "nombre_archivo": f"C:\\escaneos\\{nombre}"}
            for o, (d, nombre, datos) in sorted(escaneos.items()) if cuales is None or o in cuales]


@pytest.fixture(scope="module")
def la_curva_del_motor(escaneos):
    """La verdad de (2): CD.2 y CD.3 llamados AQUÍ sobre los mismos bytes, con los mismos nombres de archivo (sin la carpeta)."""
    piezas = [_cd().pieza_de_calibracion(o, float(d), float(d), _pel().medir_pieza_uniforme(datos, _P(), nombre, "2026-10-30", escala="declarada")) for o, (d, nombre, datos) in sorted(escaneos.items())]
    return _cd().ajustar(piezas, u_dosis_medida_pct=1.5)


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    ruta = str(tmp_path_factory.mktemp("cd4") / "plantilla.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
            Conexion._instance = None
            crear_indices(ruta)
        finally:
            Conexion._instance = previo
    return ruta


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    """Una copia de la plantilla en su propia carpeta (los escaneos van junto a ella) y un `Conexion` sin arranque: `conectar()` es el real. Con filas de auditoría ajenas para desalinear los ids."""
    carpeta = tmp_path / "base"
    carpeta.mkdir()
    ruta = str(carpeta / "cd4.db")
    shutil.copy(plantilla, ruta)
    for i in range(5):
        _sql(ruta, "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) VALUES ('2026-10-30 03:00:00', 'otro', 'guardar', 'controles', ?, 'ajena')", (str(i + 1),))
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    yield ruta
    Conexion._instance = previo


@pytest.fixture
def bd_nueva(monkeypatch, tmp_path):
    ruta = str(tmp_path / "nueva.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _auditoria(ruta):
    return _sql(ruta, "SELECT accion, tabla, ref, detalle, usuario FROM audit_log WHERE tabla IN (?, ?) ORDER BY id", (TABLA, PIEZAS))


def _conteos(ruta):
    return (_sql(ruta, f"SELECT COUNT(*) FROM {TABLA}")[0][0], _sql(ruta, f"SELECT COUNT(*) FROM {PIEZAS}")[0][0], len(_auditoria(ruta)))


def _carpeta(ruta):
    return os.path.join(os.path.dirname(ruta), CARPETA)


# ===================================================================================================== (1) el esquema

class TestElEsquema:
    def test_las_dos_tablas_nacen_con_sus_columnas_y_activo_al_final(self, bd_nueva):
        assert [c[1] for c in _sql(bd_nueva, f"PRAGMA table_info({TABLA})")] == COLUMNAS_RAIZ
        assert [c[1] for c in _sql(bd_nueva, f"PRAGMA table_info({PIEZAS})")] == COLUMNAS_PIEZA

    def test_la_raiz_no_tiene_fk_y_la_hija_cuelga_de_ella_con_restrict(self, bd_nueva):
        assert _sql(bd_nueva, f"PRAGMA foreign_key_list({TABLA})") == []
        fk = _sql(bd_nueva, f"PRAGMA foreign_key_list({PIEZAS})")
        assert [(f[2], f[3], f[4], f[5], f[6]) for f in fk] == [(TABLA, "ref", "id", "CASCADE", "RESTRICT")]

    def test_nacen_vacias_y_una_segunda_apertura_no_cambia_nada(self, bd_nueva, monkeypatch):
        antes = _sql(bd_nueva, "SELECT type, name, sql FROM sqlite_master ORDER BY name")
        Conexion._instance = None
        Conexion().con.close()
        assert _sql(bd_nueva, "SELECT type, name, sql FROM sqlite_master ORDER BY name") == antes
        assert _sql(bd_nueva, f"SELECT COUNT(*) FROM {TABLA}") == [(0,)] and _sql(bd_nueva, f"SELECT COUNT(*) FROM {PIEZAS}") == [(0,)]

    def test_crear_indices_crea_los_dos_unicos_parciales_e_idempotente(self, bd_nueva):
        primero, segundo = crear_indices(bd_nueva), crear_indices(bd_nueva)
        assert (primero[TABLA], primero[PIEZAS]) == ("creado", "creado") and (segundo[TABLA], segundo[PIEZAS]) == ("ya existía", "ya existía")
        sql = dict(_sql(bd_nueva, "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name IN (?, ?)", (TABLA, PIEZAS)))
        assert sql[f"idx_{TABLA}_bloque_activo"].endswith('ON "calibracion_pelicula" ("lote", DATE(fecha_irradiacion), "energia") WHERE (activo IS NULL OR activo = 1)')
        assert sql[f"idx_{PIEZAS}_bloque_activo"].endswith('ON "calibracion_pelicula_pieza" ("ref", "orden") WHERE (activo IS NULL OR activo = 1)')

    def test_el_indice_impide_dos_vigentes_de_la_misma_clave_y_no_dos_anuladas(self, bd_nueva):
        crear_indices(bd_nueva)
        fila = ("L", "EBT3", "2026-10-20", "6 MV", "{}", "{}", "devic", "CD-1", "{}", "{}", "{}", "u", "2026-10-30 00:00:00")
        sql = (f"INSERT INTO {TABLA} (lote, tipo_pelicula, fecha_irradiacion, energia, condiciones, cadena_de_captura, modelo, version, parametros, ajuste, estado, usuario, fecha_registro, activo) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        _sql(bd_nueva, sql, fila + (0,))
        _sql(bd_nueva, sql, fila + (1,))
        with pytest.raises(sqlite3.IntegrityError):
            _sql(bd_nueva, sql, fila[:2] + ("2026-10-20 10:00:00",) + fila[3:] + (1,))          # la misma fecha con hora: `DATE(fecha_irradiacion)` es la clave

    def test_las_listas_del_contrato_las_nombran(self):
        from scripts.indices_bloque_qc import CLAVES_INDICE
        from services.anulacion import TABLAS_ANULABLES, filtro_activo
        from services.lectura_vigente import RAICES_QC
        assert {TABLA, PIEZAS} <= TABLAS_ANULABLES and filtro_activo(PIEZAS) == " AND (activo IS NULL OR activo = 1)"
        assert CLAVES_INDICE[TABLA] == ("lote", "DATE(fecha_irradiacion)", "energia") and CLAVES_INDICE[PIEZAS] == ("ref", "orden")
        assert TABLA in RAICES_QC and PIEZAS not in RAICES_QC


# ===================================================================================================== (2) guardar y leer

class TestGuardarYLeer:
    def test_guarda_lo_que_miden_cd2_y_cd3_sobre_los_mismos_bytes(self, bd, escaneos, la_curva_del_motor):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        r = _svc().leer(nuevo)
        assert r["id"] == nuevo and r["activo"] == 1
        assert r["ajuste"] == json.loads(json.dumps(la_curva_del_motor.como_dict()))
        assert r["estado"] == {c: la_curva_del_motor.estado(c) for c in CAPAS} == {c: VALIDA for c in CAPAS}
        assert r["cero"] == json.loads(json.dumps(la_curva_del_motor.cero)) and r["cero"]["fuente"] == "piezas_de_0_cgy"
        assert (r["modelo"], r["version"]) == ("devic", "CD-1")
        assert r["parametros"]["medida"] == json.loads(json.dumps(_P())) and r["parametros"]["curva"] == la_curva_del_motor.parametros
        assert r["cadena_de_captura"] == {"piezas": la_curva_del_motor.cadena, "escaner_declarado": "Epson WF-6590", "modo_de_escaneo": "reflexión"}

    def test_el_encabezado_se_guarda_tal_cual_con_la_copia_y_el_puntero_de_los_equipos(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        assert (r["lote"], r["tipo_pelicula"], r["fecha_irradiacion"], r["energia"], r["acelerador"]) == ("L-01", "EBT3", "2026-10-20", "6 MV", "Clinac iX")
        assert r["condiciones"] == ENCABEZADO["condiciones"] and r["u_dosis_medida_pct"] == 1.5 and r["observaciones"] == "prueba" and r["usuario"] == "fisico"
        assert (r["camara_modelo"], r["camara_serie"], r["camara_factor"], r["camara_equipo_id"]) == ("FC65-G", "1234", 4.85e-2, 19)
        assert (r["electrometro_modelo"], r["electrometro_serie"], r["electrometro_factor"], r["electrometro_equipo_id"]) == ("Dose 1", "5678", None, None)
        assert r["virgen"] is None

    def test_cada_pieza_guarda_su_huella_sus_metadatos_y_su_medida(self, bd, escaneos, la_curva_del_motor):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        assert [p["orden"] for p in r["piezas"]] == sorted(escaneos)
        por_orden = {p.orden: p for p in la_curva_del_motor.piezas}
        for p in r["piezas"]:
            d, nombre, datos = escaneos[p["orden"]]
            assert p["ref"] == r["id"] and p["activo"] == 1 and p["estado"] == "ok"
            assert (p["dosis_nominal_cgy"], p["dosis_medida_cgy"], p["nombre_archivo"]) == (float(d), float(d), nombre)          # sin la carpeta del equipo
            assert p["sha256"] == hashlib.sha256(datos).hexdigest() and p["bytes"] == len(datos)
            assert (p["formato"], p["bits"], p["dpi_declarado"], p["escaner_declarado"], p["fecha_escaneo"]) == ("TIFF", 8, 150.0, "Epson WF-6590", None)
            assert p["dimensiones_px"] == por_orden[p["orden"]].medida.procedencia["forma"]
            assert p["medida"]["pieza"]["capas"] == json.loads(json.dumps(por_orden[p["orden"]].capas))
            assert p["medida"]["medicion"]["estado"] == "ok" and p["medida"]["medicion"]["centro"]["G"]["media"] == por_orden[p["orden"]].medida.centro["G"]["media"]
            assert p["posicion_mm"] == por_orden[p["orden"]].posicion_mm

    def test_una_fila_de_auditoria_con_el_lote_la_fecha_y_el_estado_de_cada_capa(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        filas = _auditoria(bd)
        assert len(filas) == 1
        accion, tabla, ref, detalle, usuario = filas[0]
        assert (accion, tabla, ref, usuario) == ("guardar", TABLA, str(nuevo), "fisico")
        assert detalle == "lote L-01, irradiada el 2026-10-20, 6 MV; 11 piezas; R: válida; G: válida; B: válida; gris: válida"

    def test_guardar_devuelve_el_id_de_la_raiz_no_el_de_la_auditoria(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        assert _sql(bd, f"SELECT id FROM {TABLA}") == [(nuevo,)]
        assert _sql(bd, "SELECT MAX(id) FROM audit_log")[0][0] != nuevo

    def test_leer_de_un_id_que_no_existe_es_none(self, bd):
        assert _svc().leer(999) is None


# ===================================================================================================== (3) reemplazar y anular

class TestReemplazarYAnular:
    def test_la_misma_clave_reemplaza_la_vigente_y_sus_piezas(self, bd, escaneos):
        primero = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        segundo = _svc().guardar("otra", {**ENCABEZADO, "observaciones": "de nuevo"}, _piezas(escaneos))
        assert segundo != primero
        assert _sql(bd, f"SELECT id, activo FROM {TABLA} ORDER BY id") == [(primero, 0), (segundo, 1)]
        assert set(_sql(bd, f"SELECT activo FROM {PIEZAS} WHERE ref = ?", (primero,))) == {(0,)}
        assert set(_sql(bd, f"SELECT activo FROM {PIEZAS} WHERE ref = ?", (segundo,))) == {(1,)}
        acciones = _auditoria(bd)
        assert [a[0] for a in acciones] == ["guardar", "reemplazo"] and acciones[1][2] == str(segundo) and acciones[1][3].endswith(f"; reemplaza id={primero}")

    def test_otra_energia_u_otro_dia_es_otra_calibracion(self, bd, escaneos):
        a = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        b = _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos, {1, 2, 3}))
        c = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-10-21"}, _piezas(escaneos, {1, 2, 3}))
        assert _sql(bd, f"SELECT id, activo FROM {TABLA} ORDER BY id") == [(a, 1), (b, 1), (c, 1)]
        assert [x[0] for x in _auditoria(bd)] == ["guardar", "guardar", "guardar"]

    def test_leer_lo_reemplazado_lo_devuelve_con_sus_piezas(self, bd, escaneos):
        primero = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        viejo = _svc().leer(primero)
        assert viejo["activo"] == 0 and len(viejo["piezas"]) == 11 and {p["activo"] for p in viejo["piezas"]} == {0}

    def test_anular_anula_la_raiz_y_sus_piezas_con_una_fila_de_auditoria(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        assert _svc().anular(nuevo, "jefe") is True
        assert _sql(bd, f"SELECT activo FROM {TABLA}") == [(0,)] and set(_sql(bd, f"SELECT activo FROM {PIEZAS}")) == {(0,)}
        assert _auditoria(bd)[-1] == ("anular", TABLA, str(nuevo), f"id={nuevo} (lote L-01, irradiada el 2026-10-20, 6 MV)", "jefe")

    def test_anular_lo_anulado_o_lo_que_no_existe_no_escribe_ni_audita(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        _svc().anular(nuevo, "jefe")
        antes = _conteos(bd)
        assert _svc().anular(nuevo, "jefe") is False and _svc().anular(999, "jefe") is False
        assert _conteos(bd) == antes

    def test_leer_lo_anulado_lo_devuelve_y_las_vigentes_no(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        assert [r["id"] for r in _svc().vigentes_validas()] == [nuevo] and [r["id"] for r in _svc().listar()] == [nuevo]
        _svc().anular(nuevo, "jefe")
        r = _svc().leer(nuevo)
        assert r["activo"] == 0 and len(r["piezas"]) == 11
        assert _svc().vigentes_validas() == [] and _svc().listar() == []

    def test_volver_a_guardar_tras_anular_es_un_guardado_nuevo(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        _svc().anular(nuevo, "jefe")
        otro = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert [a[0] for a in _auditoria(bd)] == ["guardar", "anular", "guardar"] and otro != nuevo


# ===================================================================================================== (4) los escaneos

class TestLosEscaneos:
    def test_se_copian_junto_a_la_base_con_su_huella_por_nombre(self, bd, escaneos):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        esperados = {hashlib.sha256(datos).hexdigest() + ".tif": datos for _, _, datos in escaneos.values()}
        assert sorted(os.listdir(_carpeta(bd))) == sorted(esperados)
        for nombre, datos in esperados.items():
            with open(os.path.join(_carpeta(bd), nombre), "rb") as f:
                assert f.read() == datos

    def test_un_archivo_con_ese_nombre_y_otro_contenido_no_se_sobrescribe_y_no_se_escribe_nada(self, bd, escaneos):
        datos = escaneos[3][2]
        os.makedirs(_carpeta(bd))
        ajeno = os.path.join(_carpeta(bd), hashlib.sha256(datos).hexdigest() + ".tif")
        with open(ajeno, "wb") as f:
            f.write(b"otro contenido")
        with pytest.raises(_svc().CurvaDosisError, match="no se sobrescribe"):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        with open(ajeno, "rb") as f:
            assert f.read() == b"otro contenido"
        assert _conteos(bd) == (0, 0, 0)

    def test_una_copia_que_no_coincide_con_su_huella_se_rechaza_y_no_se_escribe_nada(self, bd, escaneos, monkeypatch):
        real = _pel()._escribir_sin_pisar
        monkeypatch.setattr(_pel(), "_escribir_sin_pisar", lambda destino, contenido, binario: real(destino, contenido[:-1] + b"\x00", binario))
        with pytest.raises(_svc().CurvaDosisError, match="no coincide con su huella"):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        assert _conteos(bd) == (0, 0, 0)

    def test_el_mismo_escaneo_otra_vez_reusa_la_copia(self, bd, escaneos):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        antes = sorted(os.listdir(_carpeta(bd)))
        _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos))
        assert sorted(os.listdir(_carpeta(bd))) == antes

    def test_los_escaneos_no_van_a_la_base(self, bd, escaneos):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        tipos = {t for fila in _sql(bd, f"SELECT * FROM {PIEZAS}") + _sql(bd, f"SELECT * FROM {TABLA}") for t in map(type, fila)}
        assert bytes not in tipos

    # ------------------------------------------------------------------------------------------------- (15) CD4-R1-D3: una copia que no es su huella nunca queda bloqueando en silencio
    @staticmethod
    def _con_la_escritura_corrupta(m):
        """El corruptor de `test_una_copia_que_no_coincide_con_su_huella_se_rechaza_y_no_se_escribe_nada`: CD.2 escribe cada escaneo con el ultimo byte cambiado. `m` es un `monkeypatch.context()`; NUNCA
        `monkeypatch.undo()`: deshace tambien la fixture `bd` y manda el guardado a la base de sesion del conftest."""
        real = _pel()._escribir_sin_pisar
        m.setattr(_pel(), "_escribir_sin_pisar", lambda destino, contenido, binario: real(destino, contenido[:-1] + b"\x00", binario))

    def test_la_copia_corrupta_que_escribio_el_guardado_se_quita_y_el_siguiente_guarda(self, bd, escaneos, monkeypatch):
        """La copia que escribio ESTA llamada y no coincide con su huella es un intento fallido, no un registro: se quita (su nombre mentiria y bloquearia todo guardado posterior de ese escaneo, incluido el
        que la repararia). La carpeta conserva una sola clase de archivo: aquel cuyo nombre es su huella."""
        with monkeypatch.context() as m:
            self._con_la_escritura_corrupta(m)
            with pytest.raises(_svc().CurvaDosisError, match="la copia que escribió este guardado se quitó"):
                _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
            assert _conteos(bd) == (0, 0, 0)
            assert os.listdir(_carpeta(bd)) == []
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))          # ya sin el corruptor: el siguiente guardado entra
        assert _sql(bd, f"SELECT id FROM {TABLA}") == [(nuevo,)]
        archivos = os.listdir(_carpeta(bd))
        assert len(archivos) == 11
        for nombre in archivos:
            with open(os.path.join(_carpeta(bd), nombre), "rb") as f:
                assert hashlib.sha256(f.read()).hexdigest() + ".tif" == nombre

    def test_lo_que_ya_estaba_y_cambia_mientras_se_guarda_no_se_quita(self, bd, escaneos, monkeypatch):
        """Una copia que YA estaba (la dejo otro guardado) y cambia entre la copia y la lectura de vuelta no es de esta llamada: se rechaza diciendo que cambio y que hay que apartarla a mano, y NO se toca."""
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        antes = _conteos(bd)
        sha2 = hashlib.sha256(escaneos[2][2]).hexdigest()
        real = _svc()._copiar_el_escaneo

        def espia(carpeta, medida, datos, **kw):
            real(carpeta, medida, datos, **kw)
            if medida.procedencia["sha256"] == sha2:          # solo la pieza 2: se sobrescribe DESPUES de que CD.2 la dio por buena
                with open(_svc().ruta_del_escaneo(sha2, medida.procedencia), "wb") as f:
                    f.write(b"ajeno")

        monkeypatch.setattr(_svc(), "_copiar_el_escaneo", espia)
        with pytest.raises(_svc().CurvaDosisError, match="es la que ya estaba junto a la base: cambió mientras se guardaba y no se toca; hay que apartarla a mano"):
            _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        with open(os.path.join(_carpeta(bd), sha2 + ".tif"), "rb") as f:
            assert f.read() == b"ajeno"
        assert _conteos(bd) == antes

    def test_si_no_se_puede_quitar_lo_dice(self, bd, escaneos, monkeypatch):
        def no_se_quita(ruta):
            raise OSError(13, "sin permiso", ruta)

        with monkeypatch.context() as m:
            self._con_la_escritura_corrupta(m)
            m.setattr(_svc().os, "remove", no_se_quita)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert "no se pudo quitar" in str(e.value) and "sin permiso" in str(e.value) and "hay que quitarla a mano antes de volver a guardar" in str(e.value)
        assert _conteos(bd) == (0, 0, 0)
        assert len(os.listdir(_carpeta(bd))) == 1          # la copia corrupta sigue ahi: el servicio no pudo quitarla y lo dijo

    def test_una_copia_que_ya_estaba_y_no_es_su_huella_no_se_toca_y_apartada_se_repara(self, bd, escaneos):
        """Una copia que ya estaba junto a la base y no es su huella (cambio en reposo, o la dejo la rama «cambio mientras se guardaba») se MIDE antes de copiar y no se toca nunca: el guardado se rechaza diciendo
        que hay que apartarla a mano. Apartada, el reemplazo la repone y la calibracion vieja vuelve a dar `diferencias == []`."""
        viejo = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        copia2 = os.path.join(_carpeta(bd), hashlib.sha256(escaneos[2][2]).hexdigest() + ".tif")
        with open(copia2, "wb") as f:
            f.write(b"ajeno")                                              # la copia de la pieza 2 cambia en reposo
        for intento in ({**ENCABEZADO, "energia": "15 MV"}, ENCABEZADO):          # otra calibracion y el reemplazo de la misma
            with pytest.raises(_svc().CurvaDosisError, match="hay que apartarla a mano"):
                _svc().guardar("fisico", intento, _piezas(escaneos))
            with open(copia2, "rb") as f:
                assert f.read() == b"ajeno"                                # no se toco
            assert _conteos(bd)[0] == 1
        os.rename(copia2, os.path.join(os.path.dirname(_carpeta(bd)), "apartada.bin"))          # el fisico la aparta a mano
        assert _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)) != viejo["id"]          # el reemplazo la repone
        rec = _svc().recalcular(viejo)
        assert rec.escaneos_que_no_coinciden == () and rec.desde_los_escaneos is not None and _svc().diferencias(viejo, rec) == []
        for nombre in os.listdir(_carpeta(bd)):
            with open(os.path.join(_carpeta(bd), nombre), "rb") as f:
                assert hashlib.sha256(f.read()).hexdigest() + ".tif" == nombre

    def test_si_la_copia_desaparece_antes_de_leerla_de_vuelta_es_curva_dosis_error(self, bd, escaneos, monkeypatch):
        real = _svc()._copiar_el_escaneo

        def espia(carpeta, medida, datos, **kw):
            real(carpeta, medida, datos, **kw)
            os.remove(_svc().ruta_del_escaneo(medida.procedencia["sha256"], medida.procedencia))          # alguien (u otro equipo, en una carpeta de red) la quita antes de leerla

        monkeypatch.setattr(_svc(), "_copiar_el_escaneo", espia)
        with pytest.raises(_svc().CurvaDosisError, match="no se pudo leer de vuelta la copia del escaneo"):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert _conteos(bd) == (0, 0, 0)

    def test_si_no_se_puede_leer_la_copia_que_ya_estaba_lo_dice(self, bd, escaneos, monkeypatch):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        antes = _conteos(bd)
        copia2 = os.path.join(_carpeta(bd), hashlib.sha256(escaneos[2][2]).hexdigest() + ".tif")

        def abrir(ruta, modo="r", *a, **k):
            if modo == "rb" and os.path.normpath(os.fspath(ruta)) == os.path.normpath(copia2):
                raise PermissionError(13, "sin permiso", ruta)
            return builtins.open(ruta, modo, *a, **k)

        monkeypatch.setattr(_svc(), "open", abrir, raising=False)          # sombrea el `open` global del modulo del servicio
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert "no se pudo leer la copia del escaneo" in str(e.value) and "que ya estaba junto a la base" in str(e.value) and "sin permiso" in str(e.value)
        assert _conteos(bd) == antes


# ===================================================================================================== (5) recalcular y diferencias

class TestRecalcular:
    def test_sin_los_escaneos_y_con_ellos_da_lo_mismo_y_no_hay_diferencias(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        con = _svc().recalcular(r)
        assert con.escaneos_que_faltan == () and con.desde_los_escaneos is not None
        assert con.desde_lo_medido.como_dict() == con.desde_los_escaneos.como_dict()
        assert _svc().diferencias(r, con) == []
        shutil.rmtree(_carpeta(bd))
        sin = _svc().recalcular(r)
        assert sin.desde_los_escaneos is None and len(sin.escaneos_que_faltan) == 11
        assert sin.desde_lo_medido.como_dict() == con.desde_lo_medido.como_dict() and _svc().diferencias(r, sin) == []

    def test_un_ajuste_guardado_alterado_se_ve(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        ajuste = json.loads(_sql(bd, f"SELECT ajuste FROM {TABLA} WHERE id = ?", (nuevo,))[0][0])
        ajuste["capas"]["G"]["parametros"]["a"] *= 1.001
        _sql(bd, f"UPDATE {TABLA} SET ajuste = ? WHERE id = ?", (json.dumps(ajuste), nuevo))
        r = _svc().leer(nuevo)
        dif = _svc().diferencias(r, _svc().recalcular(r))
        assert any(d.startswith("ajuste (desde lo medido) › capas › G › parametros › a: guardado") for d in dif), dif

    def test_lo_medido_de_una_pieza_alterado_se_ve(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        medida = json.loads(_sql(bd, f"SELECT medida FROM {PIEZAS} WHERE ref = ? AND orden = 5", (nuevo,))[0][0])
        medida["pieza"]["capas"]["G"]["valor"] += 0.5
        _sql(bd, f"UPDATE {PIEZAS} SET medida = ? WHERE ref = ? AND orden = 5", (json.dumps(medida), nuevo))
        r = _svc().leer(nuevo)
        dif = _svc().diferencias(r, _svc().recalcular(r))
        assert any(d.startswith("ajuste (desde lo medido)") for d in dif) and any(d.startswith("la pieza 5 (desde su escaneo) › capas › G › valor") for d in dif), dif

    def test_recalcular_usa_los_parametros_guardados_no_los_de_hoy(self, bd, escaneos, monkeypatch):
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"residuo_maximo_pct": 0.01}}, _piezas(escaneos)))
        assert r["parametros"]["curva"]["residuo_maximo_pct"] == 0.01 and r["estado"]["G"].startswith("no válida: el residuo")
        assert _svc().diferencias(r, _svc().recalcular(r)) == []

    def test_lo_guardado_ilegible_se_dice_como_curva_dosis_error(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2})))
        r["piezas"][0]["medida"] = {"otra": "cosa"}
        with pytest.raises(_svc().CurvaDosisError, match="no se puede volver a ajustar"):
            _svc().recalcular(r)


# ===================================================================================================== (6) la auditoría en la transacción

class TestLaAuditoriaEnLaTransaccion:
    def _espiar(self, monkeypatch):
        import services.anulacion as anulacion
        llamadas = []
        for modulo in (anulacion, _svc()):
            real = modulo._registrar_auditoria

            def espia(*a, _real=real, **k):
                con = k.get("con")
                llamadas.append((a[1], con is not None and con.in_transaction))
                return _real(*a, **k)
            monkeypatch.setattr(modulo, "_registrar_auditoria", espia)
        return llamadas

    def test_guardar_reemplazar_y_anular_auditan_una_vez_dentro_de_su_transaccion(self, bd, escaneos, monkeypatch):
        llamadas = self._espiar(monkeypatch)
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        otro = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        _svc().anular(otro, "jefe")
        assert llamadas == [("guardar", True), ("reemplazo", True), ("anular", True)] and nuevo != otro

    def test_un_fallo_a_mitad_no_deja_nada(self, bd, escaneos, monkeypatch):
        monkeypatch.setattr(_svc(), "SQL_INSERT_PIEZA", _svc().SQL_INSERT_PIEZA.replace("dosis_nominal_cgy)", "no_existe)", 1).replace("dosis_nominal_cgy,", "no_existe,", 1))
        with pytest.raises(sqlite3.OperationalError):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        assert _conteos(bd) == (0, 0, 0)

    def test_un_fallo_a_mitad_de_un_reemplazo_deja_la_vigente_como_estaba(self, bd, escaneos, monkeypatch):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        antes = (_sql(bd, f"SELECT id, activo FROM {TABLA}"), _sql(bd, f"SELECT id, activo FROM {PIEZAS}"), _auditoria(bd))
        monkeypatch.setattr(_svc(), "SQL_INSERT_PIEZA", "INSERT INTO calibracion_pelicula_pieza (no_existe) VALUES (?)")
        with pytest.raises(sqlite3.OperationalError):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        assert (_sql(bd, f"SELECT id, activo FROM {TABLA}"), _sql(bd, f"SELECT id, activo FROM {PIEZAS}"), _auditoria(bd)) == antes and antes[0] == [(nuevo, 1)]


# ===================================================================================================== (7) la puerta estricta de los JSON

class TestLosJsonEstrictos:
    @pytest.mark.parametrize("valor", [float("nan"), float("inf"), np.int64(3)], ids=["nan", "infinito", "numpy"])
    def test_lo_que_no_es_json_valido_no_entra_ni_copia_escaneos(self, bd, escaneos, valor):
        with pytest.raises(_svc().CurvaDosisError, match="no es JSON válido"):
            _svc().guardar("fisico", {**ENCABEZADO, "condiciones": {"profundidad_cm": valor}}, _piezas(escaneos, {1, 2}))
        assert _conteos(bd) == (0, 0, 0) and not os.path.exists(_carpeta(bd))

    def test_la_puerta_es_la_de_d1_una_sola_definicion(self):
        """CD4-D1: la puerta de D.1 subió a `services/json_estricto.py`; el servicio de la curva y el del mensual la usan, y en `services/` nadie más escribe JSON con `json.dumps`."""
        arbol = ast.parse((RAIZ / "services" / "curva_dosis.py").read_text(encoding="utf-8"))
        dumps = [n for n in ast.walk(arbol) if isinstance(n, ast.Attribute) and n.attr == "dumps"]
        importa = [n for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module == "services.json_estricto" and [a.name for a in n.names] == ["json_estricto"]]
        assert dumps == [] and len(importa) == 1
        mensual = ast.parse((RAIZ / "services" / "placa_mensual.py").read_text(encoding="utf-8"))
        funcion = next(n for n in ast.walk(mensual) if isinstance(n, ast.FunctionDef) and n.name == "_json_estricto")
        assert not [n for n in ast.walk(funcion) if isinstance(n, ast.Attribute) and n.attr == "dumps"], "el mensual ya no tiene su propia copia de la regla"
        assert any(isinstance(n, ast.Call) and getattr(n.func, "id", None) == "json_estricto" for n in ast.walk(funcion))
        comun = ast.parse((RAIZ / "services" / "json_estricto.py").read_text(encoding="utf-8"))
        assert [k.value.value for n in ast.walk(comun) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "dumps" for k in n.keywords if k.arg == "allow_nan"] == [False]

    def test_el_mensual_dice_lo_mismo_con_su_error(self):
        from services.placa_mensual import PlacaMensualError, _json_estricto
        with pytest.raises(PlacaMensualError, match=r"lo que se guarda en la columna 'piso' no es JSON válido \(.*\): hay un número no finito"):
            _json_estricto({"x": float("nan")}, "piso", sort_keys=True)
        assert _json_estricto({"b": 1, "a": 2}, "piso", sort_keys=True) == '{"a": 2, "b": 1}'


# ===================================================================================================== (8) lo que se rechaza antes de escribir

class TestLoQueSeRechaza:
    @pytest.mark.parametrize("cambio, texto", [
        ({"lote": " "}, "falta el lote"), ({"fecha_irradiacion": "20/10/2026"}, "aaaa-mm-dd"), ({"fecha_irradiacion": "2026-02-30"}, "aaaa-mm-dd"), ({"energia": None}, "falta la energía"),
        ({"otra_clave": 1}, "no conoce"), ({"camara": {"modelo": "x"}}, "la cámara es un diccionario"), ({"camara": {**ENCABEZADO["camara"], "equipo_id": "19"}}, "equipo_id"),
        ({"u_dosis_medida_pct": -1.0}, "incertidumbre"), ({"modo_de_escaneo": "otro"}, "modo de escaneo"), ({"parametros_de_la_curva": {"no_existe": 1}}, "PARAMETROS_DE_LA_CURVA"),
        ({"condiciones": [1]}, "condiciones")], ids=lambda v: str(v)[:24])
    def test_un_encabezado_mal_formado(self, bd, escaneos, cambio, texto):
        with pytest.raises(_svc().CurvaDosisError, match=texto):
            _svc().guardar("fisico", {**ENCABEZADO, **cambio}, _piezas(escaneos, {1, 2}))
        assert _conteos(bd) == (0, 0, 0) and not os.path.exists(_carpeta(bd))

    def test_falta_una_clave_obligatoria_del_encabezado(self, bd, escaneos):
        cabeza = dict(ENCABEZADO)
        del cabeza["tipo_pelicula"]
        with pytest.raises(_svc().CurvaDosisError, match="le faltan"):
            _svc().guardar("fisico", cabeza, _piezas(escaneos, {1, 2}))

    def test_piezas_mal_formadas(self, bd, escaneos):
        buenas = _piezas(escaneos, {1, 2})
        for piezas, texto in (([], "al menos una pieza"), ([{**buenas[0], "otra": 1}], "no se conocen"), ([buenas[0], {**buenas[1], "orden": 1}], "no se repite"),
                              ([{**buenas[0], "datos": b""}], "falta el escaneo"), ([{**buenas[0], "nombre_archivo": "C:\\carpeta\\"}], "falta el nombre"),
                              ([{**buenas[0], "fecha_escaneo": "ayer"}], "fecha de escaneo")):
            with pytest.raises(_svc().CurvaDosisError, match=texto):
                _svc().guardar("fisico", ENCABEZADO, piezas)
        assert _conteos(bd) == (0, 0, 0)

    def test_sin_usuario_o_con_una_virgen_que_no_es_una_referencia_valida(self, bd, escaneos):
        with pytest.raises(_svc().CurvaDosisError, match="falta el usuario"):
            _svc().guardar(" ", ENCABEZADO, _piezas(escaneos, {1, 2}))
        with pytest.raises(_svc().CurvaDosisError, match="virgen montada"):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}), virgen={"estado": "ok"})
        with pytest.raises(_svc().CurvaDosisError, match="falta el usuario"):
            _svc().anular(1, None)
        assert _conteos(bd) == (0, 0, 0)

    def test_la_fecha_de_escaneo_declarada_se_guarda_normalizada(self, bd, escaneos):
        piezas = [{**p, "fecha_escaneo": "2026-10-21"} for p in _piezas(escaneos, {1, 2})]
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert [p["fecha_escaneo"] for p in r["piezas"]] == ["2026-10-21", "2026-10-21"]


# ===================================================================================================== (9) la selectividad y la Trampa 6, por AST

def _llamadas_sql(ruta):
    """(función, texto con `{...}` en lugar de lo interpolado, si interpola `filtro_activo`) de cada `execute` del archivo."""
    arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    salida = []
    for f in [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)]:
        for n in ast.walk(f):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "execute" and n.args:
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    salida.append((f.name, a.value, False))
                elif isinstance(a, ast.JoinedStr):
                    texto = "".join(p.value if isinstance(p, ast.Constant) else "{}" for p in a.values)
                    filtra = any(isinstance(p, ast.FormattedValue) and isinstance(p.value, ast.Call) and getattr(p.value.func, "id", None) == "filtro_activo" for p in a.values)
                    salida.append((f.name, texto, filtra))
    return salida


class TestLaSelectividad:
    def test_las_lecturas_y_anulaciones_por_la_clave_de_bloque_filtran_dentro_del_fstring(self):
        llamadas = _llamadas_sql(RAIZ / "services" / "curva_dosis.py")
        por_bloque = [(f, t, filtra) for f, t, filtra in llamadas if ("WHERE lote = ?" in t or "WHERE 1=1" in t or ("SET activo = 0 WHERE ref = ?" in t))]
        assert sorted((f, filtra) for f, _, filtra in por_bloque) == [("anular", True), ("guardar", True), ("guardar", True), ("listar", True)], por_bloque
        assert [f for f, _, _ in llamadas if f == "vigentes_validas"] == []          # sin SQL propio: sale de `listar` (que filtra) y de `leer`

    def test_leer_va_por_identidad_y_no_filtra(self):
        llamadas = [(t, filtra) for f, t, filtra in _llamadas_sql(RAIZ / "services" / "curva_dosis.py") if f == "leer"]
        assert [(t.split(" FROM ")[1], filtra) for t, filtra in llamadas] == [("calibracion_pelicula WHERE id = ?", False), ("calibracion_pelicula_pieza WHERE ref = ? ORDER BY orden", False)]
        piezas = next(t for t, _ in llamadas if "calibracion_pelicula_pieza" in t)
        assert piezas.split(" FROM ")[0] == "SELECT " + ", ".join(COLUMNAS_PIEZA)          # las columnas de la tabla, escritas y en su orden

    def test_nadie_mas_escribe_ni_crea_estas_tablas(self):
        escriben, crean = set(), set()
        for ruta in RAIZ.rglob("*.py"):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in {"build", "dist", "tests", "__pycache__", ".venv"} or any(p.startswith(".") for p in partes):
                continue
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            for tabla in (TABLA, PIEZAS):
                if f"INSERT INTO {tabla} " in texto or f"UPDATE {tabla} " in texto or f"DELETE FROM {tabla}" in texto:
                    escriben.add(str(ruta.relative_to(RAIZ)))
                if f"CREATE TABLE IF NOT EXISTS {tabla} " in texto:
                    crean.add(str(ruta.relative_to(RAIZ)))
        assert escriben == {"services/curva_dosis.py"} and crean == {"data/ManejoDatos/conection.py"}

    def test_el_servicio_no_tiene_qt_ni_nombra_las_funciones_del_piso(self):
        texto = (RAIZ / "services" / "curva_dosis.py").read_text(encoding="utf-8")
        assert "PyQt5" not in texto and "piso_de_pelicula" not in texto and "leer_referencia_virgen" not in texto and "MODO_DEL_PISO" not in texto


# ===================================================================================================== (10) vigentes_validas

class TestLasVigentesValidas:
    def test_solo_lo_vigente_con_una_capa_valida_la_mas_reciente_primero(self, bd, escaneos):
        vieja = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-09-01"}, _piezas(escaneos))
        incompleta = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-10-25"}, _piezas(escaneos, {1, 2, 3}))
        nueva = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        assert _svc().leer(incompleta)["estado"]["G"].startswith("incompleta: ")
        assert [r["id"] for r in _svc().listar()] == [incompleta, nueva, vieja]
        validas = _svc().vigentes_validas()
        assert [r["id"] for r in validas] == [nueva, vieja] and validas[0]["ajuste"]["version"] == "CD-1"
        primera = _svc().listar()[0]
        assert "ajuste" not in primera and primera["estado"] == _svc().leer(incompleta)["estado"] and primera["estado"]["R"].startswith("incompleta: quedan ")


# ===================================================================================================== (11) la película virgen montada

def _virgen(valores=(152.12, 194.11, 86.77)):
    lienzo = gen.Lienzo(66.0, 66.0, 600.0, semilla=9)
    lienzo.pegar_pelicula(3.0, 3.0, 60.0, 60.0, valores, gen.RUIDO_EPSON179)
    return _pel().piso_de_pelicula_virgen(lienzo.codificar(), _P(), "virgen.tif", "2026-10-30")


class TestLaVirgenMontada:
    def test_su_copia_viaja_con_la_calibracion_aunque_no_haga_de_cero(self, bd, escaneos):
        virgen = _virgen()
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}), virgen=virgen))
        assert r["virgen"] == json.loads(json.dumps(virgen.como_dict())) and r["cero"]["fuente"] == "piezas_de_0_cgy"

    def test_sin_pieza_de_0_cgy_la_virgen_de_la_misma_cadena_es_el_cero_y_recalcular_usa_su_copia(self, bd):
        virgen = _virgen()
        piezas = [{"orden": k, "dosis_nominal_cgy": float(d), "dosis_medida_cgy": float(d), "nombre_archivo": f"{d}.tif",
                   "datos": gen.pieza_de_dosis(d, DEVIC, lado_mm=20.0, dpi=600.0, semilla=k).datos} for k, d in enumerate((100, 200, 400), 1)]
        nuevo = _svc().guardar("fisico", ENCABEZADO, piezas, virgen=virgen)
        r = _svc().leer(nuevo)
        assert r["cero"]["fuente"] == "pelicula_virgen" and _svc().diferencias(r, _svc().recalcular(r)) == []
        otra = json.loads(json.dumps(_virgen((150.0, 190.0, 85.0)).como_dict()))
        _sql(bd, f"UPDATE {TABLA} SET virgen = ? WHERE id = ?", (json.dumps(otra), nuevo))
        r = _svc().leer(nuevo)
        assert any(d.startswith("ajuste (desde lo medido) › cero") for d in _svc().diferencias(r, _svc().recalcular(r)))


# ===================================================================================================== (12) las 21 piezas reales de H9

@pytest.mark.skipif(not os.path.isdir(_corpus.PIEZAS_DE_CALIBRACION_RAIZ), reason="la carpeta de las piezas de H9 no existe en esta máquina")
class TestLasPiezasDeH9:
    def test_se_guardan_con_los_estados_de_cd3_y_lo_guardado_se_rehace_igual(self, bd):
        assert _corpus.piezas_de_calibracion_que_faltan() == []
        piezas = []
        for k, (dosis, archivo) in enumerate(sorted(_corpus.PIEZAS_DE_CALIBRACION.items()), 1):
            with open(_corpus.ruta_de_pieza_de_calibracion(dosis), "rb") as f:
                piezas.append({"orden": k, "dosis_nominal_cgy": float(dosis), "dosis_medida_cgy": float(dosis), "datos": f.read(), "nombre_archivo": archivo})
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "escaner_declarado": "Epson 12000XL (declarado por el físico)", "modo_de_escaneo": "transmisión"}, piezas))
        assert r["estado"] == {"R": "guía: el cero es la pieza de 5 cGy", "G": "no válida: el residuo de la pieza de 350 cGy es +3.19 % (la tolerancia es ±3 %)",
                               "B": "incompleta: quedan 0 dosis en el rango útil (hacen falta 6)", "gris": "no válida: el residuo de la pieza de 350 cGy es +3.60 % (la tolerancia es ±3 %)"}
        assert r["cero"]["fuente"] == "pieza_de_menor_dosis" and {p["bits"] for p in r["piezas"]} == {16} and {p["dpi_declarado"] for p in r["piezas"]} == {150.0}
        assert _svc().vigentes_validas() == [] and _svc().diferencias(r, _svc().recalcular(r)) == []


# ===================================================================================================== (13) la ampliacion del implementador
# La prueba de referencia (60 casos) dejaba SIN guardia, medido con las mutaciones propias de `cd4_mutaciones.py` (E01..E52): cada validacion de entrada del encabezado y de las piezas, que el equipo, la
# fecha del EXIF y los bytes de cada pieza son los que lee CD.2, el orden y el empate de las lecturas, los textos de `diferencias` y su tolerancia por los DOS lados, y la forma canonica de los JSON
# guardados. Solo se AGREGA (nunca se debilita un caso de la referencia).

def _con_exif(datos, marca="EPSON", modelo="Perfection V850", fecha="2026:10:21 09:30:00"):
    """Los mismos pixeles de un escaneo de 8 bits, con las etiquetas EXIF de un escaner (Make 271, Model 272 y DateTime 306): lo que la referencia sintetica no trae."""
    from PIL import Image, TiffImagePlugin
    imagen = Image.open(io.BytesIO(datos))
    imagen.load()
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[271], ifd[272], ifd[306] = marca, modelo, fecha
    salida = io.BytesIO()
    imagen.save(salida, format="TIFF", tiffinfo=ifd, dpi=(150, 150), compression=None)
    return salida.getvalue()


class TestLaAmpliacionDelImplementador:
    # ------------------------------------------------------------------------------------------------- el encabezado
    def test_los_textos_del_encabezado_se_guardan_sin_espacios(self, bd, escaneos):
        nuevo = _svc().guardar("  fisico ", {**ENCABEZADO, "lote": "  L-01 ", "energia": " 6 MV  ", "tipo_pelicula": " EBT3 ", "acelerador": " Clinac iX ", "observaciones": " prueba  "},
                               _piezas(escaneos, {1, 2, 3}))
        r = _svc().leer(nuevo)
        assert (r["lote"], r["energia"], r["tipo_pelicula"], r["acelerador"], r["observaciones"], r["usuario"]) == ("L-01", "6 MV", "EBT3", "Clinac iX", "prueba", "fisico")
        otro = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))          # la clave de bloque es la del texto sin espacios: es la MISMA calibracion
        assert [a[0] for a in _auditoria(bd)] == ["guardar", "reemplazo"] and _sql(bd, f"SELECT id, activo FROM {TABLA} ORDER BY id") == [(nuevo, 0), (otro, 1)]

    @pytest.mark.parametrize("cambio, texto", [
        ({"u_dosis_medida_pct": True}, "incertidumbre"), ({"u_dosis_medida_pct": float("nan")}, "incertidumbre"), ({"u_dosis_medida_pct": float("inf")}, "incertidumbre"),
        ({"camara": {**ENCABEZADO["camara"], "factor": True}}, "factor de .*cámara"), ({"camara": {**ENCABEZADO["camara"], "factor": float("nan")}}, "factor de .*cámara"),
        ({"electrometro": {**ENCABEZADO["electrometro"], "factor": float("inf")}}, "factor de.* electrómetro")], ids=["u_booleano", "u_nan", "u_infinito", "factor_booleano", "factor_nan", "factor_infinito"])
    def test_un_booleano_o_un_no_finito_no_son_numeros(self, bd, escaneos, cambio, texto):
        with pytest.raises(_svc().CurvaDosisError, match=texto):
            _svc().guardar("fisico", {**ENCABEZADO, **cambio}, _piezas(escaneos, {1, 2}))
        assert _conteos(bd) == (0, 0, 0) and not os.path.exists(_carpeta(bd))

    @pytest.mark.parametrize("equipo", [{**ENCABEZADO["camara"], "extra": 1}, {**ENCABEZADO["camara"], "equipo_id": True}, {**ENCABEZADO["camara"], "equipo_id": 1.5}],
                             ids=["clave_de_mas", "puntero_booleano", "puntero_decimal"])
    def test_un_equipo_con_una_clave_de_mas_o_un_puntero_que_no_es_entero_se_rechaza(self, bd, escaneos, equipo):
        with pytest.raises(_svc().CurvaDosisError, match="la cámara es un diccionario|el equipo_id de la cámara es un entero"):
            _svc().guardar("fisico", {**ENCABEZADO, "camara": equipo}, _piezas(escaneos, {1, 2}))
        assert _conteos(bd) == (0, 0, 0)

    def test_un_puntero_de_numpy_se_guarda_como_entero(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "camara": {**ENCABEZADO["camara"], "equipo_id": np.int64(19)}}, _piezas(escaneos, {1, 2, 3})))
        assert r["camara_equipo_id"] == 19 and type(r["camara_equipo_id"]) is int

    @pytest.mark.parametrize("condiciones", [None, {}, "ausente"], ids=["none", "vacio", "ausente"])
    def test_unas_condiciones_vacias_o_none_se_guardan_como_diccionario_vacio(self, bd, escaneos, condiciones):
        cabeza = {k: v for k, v in ENCABEZADO.items() if k != "condiciones"}
        if condiciones != "ausente":
            cabeza["condiciones"] = condiciones
        assert _svc().leer(_svc().guardar("fisico", cabeza, _piezas(escaneos, {1, 2})))["condiciones"] == {}

    # ------------------------------------------------------------------------------------------------- las piezas
    def test_piezas_mal_formadas_de_otras_formas(self, bd, escaneos):
        buenas = _piezas(escaneos, {1, 2})
        for piezas, texto in ((None, "una lista de diccionarios"), (["no es un diccionario"], "no es un diccionario"), ([{**buenas[0], "orden": True}], "entero que no se repite"),
                              ([{**buenas[0], "orden": 1.5}], "entero que no se repite"), ([{**buenas[0], "datos": "texto"}], "falta el escaneo"),
                              ([{**buenas[0], "nombre_archivo": 5}], "falta el nombre")):
            with pytest.raises(_svc().CurvaDosisError, match=texto):
                _svc().guardar("fisico", ENCABEZADO, piezas)
        assert _conteos(bd) == (0, 0, 0) and not os.path.exists(_carpeta(bd))

    def test_un_escaneo_ilegible_se_guarda_como_pieza_no_medible_y_no_entra_a_la_curva(self, bd, escaneos):
        piezas = _piezas(escaneos, {1, 2, 3, 4, 5, 6, 7})
        piezas[3] = {**piezas[3], "datos": b"esto no es una imagen", "nombre_archivo": "C:\\x\\basura.tif"}
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        mala = r["piezas"][3]
        assert mala["estado"].startswith("no medible: ") and mala["sha256"] == hashlib.sha256(b"esto no es una imagen").hexdigest() and mala["bytes"] == 21
        assert _sql(bd, f"SELECT dimensiones_px, posicion_mm FROM {PIEZAS} WHERE orden = 4") == [(None, None)]          # lo que no se midio es NULL en la base, no el texto 'null'
        assert any(a.startswith("la pieza 4 (150 cGy) no entra en la curva: no medible") for a in r["ajuste"]["avisos"]), r["ajuste"]["avisos"]
        assert all(e == "incompleta: quedan 5 dosis en el rango útil (hacen falta 6)" for e in r["estado"].values()), r["estado"]          # 7 piezas, menos la de 0 cGy (el cero) y la ilegible
        assert _svc().diferencias(r, _svc().recalcular(r)) == []

    def test_sin_ninguna_pieza_medible_la_calibracion_se_guarda_incompleta_y_sin_cero(self, bd):
        piezas = [{"orden": 1, "dosis_nominal_cgy": 0.0, "dosis_medida_cgy": 0.0, "datos": b"basura uno", "nombre_archivo": "a.tif"},
                  {"orden": 2, "dosis_nominal_cgy": 100.0, "dosis_medida_cgy": 100.0, "datos": b"basura dos", "nombre_archivo": "b.png"}]
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert r["estado"] == {c: "incompleta: falta la película virgen (0 cGy)" for c in CAPAS} and r["cero"] is None and r["cadena_de_captura"]["piezas"] is None
        assert _sql(bd, f"SELECT cero, virgen FROM {TABLA}") == [(None, None)]                          # sin cero y sin virgen: NULL en la base, no el texto 'null'
        assert _svc().vigentes_validas() == [] and _svc().diferencias(r, _svc().recalcular(r)) == []

    def test_la_fecha_de_escaneo_con_espacios_se_guarda_normalizada(self, bd, escaneos):
        piezas = [{**p, "fecha_escaneo": " 2026-10-21 "} for p in _piezas(escaneos, {1, 2})]
        assert [p["fecha_escaneo"] for p in _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))["piezas"]] == ["2026-10-21", "2026-10-21"]

    def test_una_virgen_que_no_es_ok_se_rechaza(self, bd, escaneos):
        mala = dataclasses.replace(_virgen(), estado="no válida: la prueba")
        with pytest.raises(_svc().CurvaDosisError, match="virgen montada"):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}), virgen=mala)
        assert _conteos(bd) == (0, 0, 0)

    @pytest.mark.parametrize("cambio", [{"dosis_nominal_cgy": -5.0}, {"dosis_nominal_cgy": float("nan")}, {"dosis_nominal_cgy": "100"}, {"dosis_medida_cgy": "100"}],
                             ids=["nominal_negativa", "nominal_nan", "nominal_texto", "medida_texto"])
    def test_una_dosis_mal_dada_la_dice_el_servicio_y_no_escribe_ni_copia_nada(self, bd, escaneos, cambio):
        piezas = _piezas(escaneos, {1, 2, 3})
        piezas[1] = {**piezas[1], **cambio}
        with pytest.raises(_svc().CurvaDosisError, match="dosis"):
            _svc().guardar("fisico", ENCABEZADO, piezas)
        assert _conteos(bd) == (0, 0, 0) and not os.path.exists(_carpeta(bd))

    def test_anular_sin_usuario_o_con_solo_espacios_no_escribe_ni_audita(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        antes = _conteos(bd)
        for usuario in (None, "", "   "):
            with pytest.raises(_svc().CurvaDosisError, match="falta el usuario"):
                _svc().anular(nuevo, usuario)
        assert _conteos(bd) == antes and _sql(bd, f"SELECT activo FROM {TABLA}") == [(1,)]

    def test_la_fecha_de_registro_es_la_del_guardado(self, bd, escaneos):
        antes = datetime.now().replace(microsecond=0)
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2})))
        despues = datetime.now()
        assert antes <= datetime.strptime(r["fecha_registro"], "%Y-%m-%d %H:%M:%S") <= despues

    def test_el_equipo_y_la_fecha_del_exif_de_cada_pieza_son_los_que_lee_cd2(self, bd, escaneos):
        piezas = [{**p, "datos": _con_exif(p["datos"])} for p in _piezas(escaneos, {1, 2, 3})]
        for p in piezas:
            procedencia = _pel().medir_pieza_uniforme(p["datos"], _P(), os.path.basename(p["nombre_archivo"].replace("\\", "/")), "2026-10-30", escala="declarada").procedencia
            assert procedencia["equipo"] == "EPSON Perfection V850" and procedencia["fecha_escaneo"] == "2026-10-21"          # la verdad: lo que se escribio en el archivo, leido por CD.2
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert {(p["equipo"], p["fecha_exif"]) for p in r["piezas"]} == {("EPSON Perfection V850", "2026-10-21")} and {p["fecha_escaneo"] for p in r["piezas"]} == {None}

    def test_si_no_se_puede_crear_la_carpeta_de_los_escaneos_se_dice_y_no_se_escribe_nada(self, bd, escaneos):
        with open(_carpeta(bd), "wb") as f:                                   # un ARCHIVO donde tendria que ir la carpeta
            f.write(b"x")
        with pytest.raises(_svc().CurvaDosisError, match="no se pudo copiar"):
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert _conteos(bd) == (0, 0, 0)

    # ------------------------------------------------------------------------------------------------- las lecturas
    def test_el_mismo_dia_la_guardada_despues_va_primero(self, bd, escaneos):
        a = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        b = _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos, {1, 2, 3}))
        c = _svc().guardar("fisico", {**ENCABEZADO, "energia": "15 MV"}, _piezas(escaneos, {1, 2, 3}))
        assert [r["id"] for r in _svc().listar()] == [c, b, a]

    def test_listar_trae_el_estado_y_la_cadena_de_captura_ya_convertidos(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        fila, completo = _svc().listar()[0], _svc().leer(nuevo)
        assert set(fila) == {"id", "lote", "tipo_pelicula", "fecha_irradiacion", "acelerador", "energia", "modelo", "version", "estado", "cadena_de_captura", "usuario", "fecha_registro", "activo"}
        assert type(fila["estado"]) is dict and fila["estado"] == completo["estado"]
        assert type(fila["cadena_de_captura"]) is dict and fila["cadena_de_captura"] == completo["cadena_de_captura"]

    def test_leer_da_las_piezas_en_el_orden_del_formulario_aunque_se_guardaron_en_otro(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, list(reversed(_piezas(escaneos)))))
        assert [p["orden"] for p in r["piezas"]] == sorted(escaneos)
        assert _svc().diferencias(r, _svc().recalcular(r)) == []

    # ------------------------------------------------------------------------------------------------- recalcular y comparar
    @pytest.mark.parametrize("sufijo, extension", [(".png", ".png"), (".tiff", ".tiff"), ("", ".tif")], ids=["png", "tiff", "sin_extension"])
    def test_recalcular_encuentra_los_escaneos_de_cualquier_extension(self, bd, escaneos, sufijo, extension):
        piezas = [{**p, "nombre_archivo": f"C:\\escaneos\\pieza{p['orden']}{sufijo}"} for p in _piezas(escaneos, {1, 2, 3, 4, 5, 6, 7})]
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert sorted(os.path.splitext(f)[1] for f in os.listdir(_carpeta(bd))) == [extension] * 7          # la del nombre si es de una imagen conocida y, si no, la del formato (TIFF)
        rec = _svc().recalcular(r)
        assert rec.escaneos_que_faltan == () and rec.desde_los_escaneos is not None and _svc().diferencias(r, rec) == []

    def test_recalcular_vuelve_a_medir_con_los_parametros_de_medida_guardados(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        parametros = json.loads(_sql(bd, f"SELECT parametros FROM {TABLA} WHERE id = ?", (nuevo,))[0][0])
        assert parametros["medida"]["delta_tinta"] == 25.0                                               # lo que cuenta como tinta en la region central: con 3 la region de la pieza queda con menos pixeles
        parametros["medida"]["delta_tinta"] = 3.0
        _sql(bd, f"UPDATE {TABLA} SET parametros = ? WHERE id = ?", (json.dumps(parametros), nuevo))
        r = _svc().leer(nuevo)
        dif = _svc().diferencias(r, _svc().recalcular(r))
        assert any(d.startswith("ajuste (desde los escaneos)") for d in dif), dif                    # las piezas se midieron con los parametros GUARDADOS (3), no con los de hoy (25)
        assert any(d.startswith("la pieza ") and "(desde su escaneo) › " in d for d in dif), dif
        assert not any(d.startswith("ajuste (desde lo medido)") for d in dif), dif                    # y lo medido guardado no cambio: la curva rehecha desde las filas es la guardada

    def test_diferencias_dice_el_estado_alterado_y_lo_que_falta_en_cada_lado(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        rec = _svc().recalcular(r)
        assert _svc().diferencias(r, rec) == []
        alterado = copy.deepcopy(r)
        alterado["estado"]["G"] = "no válida: otra cosa"
        assert "estado (desde lo medido) › G: guardado 'no válida: otra cosa', recalculado 'válida'" in _svc().diferencias(alterado, rec)
        sin_clave = copy.deepcopy(r)
        del sin_clave["ajuste"]["capas"]["G"]["rms_pct"]
        assert "ajuste (desde lo medido) › capas › G › rms_pct: falta en lo guardado" in _svc().diferencias(sin_clave, rec)
        con_clave = copy.deepcopy(r)
        con_clave["ajuste"]["capas"]["G"]["extra"] = 1
        assert "ajuste (desde lo medido) › capas › G › extra: falta en lo recalculado" in _svc().diferencias(con_clave, rec)
        corto = copy.deepcopy(r)
        corto["ajuste"]["piezas"].pop()
        assert "ajuste (desde lo medido) › piezas: guardado 10 elementos, recalculado 11" in _svc().diferencias(corto, rec)

    def test_la_tolerancia_absorbe_el_ruido_y_no_un_cambio_real(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        rec = _svc().recalcular(r)
        base = r["ajuste"]["capas"]["G"]["parametros"]["a"]
        assert r["ajuste"]["piezas"][0]["capas"]["R"]["netod"] == 0.0                                  # exactamente 0: la pieza de 0 cGy contra su propio cero
        for relativo, se_ve in ((1e-12, False), (1e-6, True)):                                         # la relativa es de 1e-9: el ruido de punto flotante no es una diferencia, un cambio de una millonesima si
            alterado = copy.deepcopy(r)
            alterado["ajuste"]["capas"]["G"]["parametros"]["a"] = base * (1 + relativo)
            assert bool(_svc().diferencias(alterado, rec)) is se_ve, relativo
        for absoluto, se_ve in ((1e-14, False), (1e-6, True)):                                         # cerca de cero manda la absoluta, de 1e-12
            alterado = copy.deepcopy(r)
            alterado["ajuste"]["piezas"][0]["capas"]["R"]["netod"] = absoluto
            assert bool(_svc().diferencias(alterado, rec)) is se_ve, absoluto

    def test_una_pieza_sin_dosis_medida_se_guarda_y_lo_guardado_se_rehace_igual(self, bd, escaneos):
        piezas = _piezas(escaneos)
        piezas[4] = {**piezas[4], "dosis_medida_cgy": None}
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert r["piezas"][4]["dosis_medida_cgy"] is None and r["piezas"][4]["dosis_nominal_cgy"] == 200.0
        assert all(e.startswith("incompleta: ") for e in r["estado"].values()), r["estado"]
        assert _svc().diferencias(r, _svc().recalcular(r)) == []

    # ------------------------------------------------------------------------------------------------- la forma de lo guardado
    def test_los_json_guardados_son_la_forma_canonica_con_los_acentos_legibles(self, bd, escaneos):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        columnas = {TABLA: ("condiciones", "cadena_de_captura", "cero", "virgen", "parametros", "ajuste", "estado"), PIEZAS: ("dimensiones_px", "posicion_mm", "medida")}
        vistas = 0
        for tabla, cols in columnas.items():
            for c in cols:
                for (texto,) in _sql(bd, f"SELECT {c} FROM {tabla} WHERE {c} IS NOT NULL"):
                    assert texto == json.dumps(json.loads(texto), sort_keys=True, ensure_ascii=False), (tabla, c)
                    vistas += 1
        assert vistas == 6 + 3 * 3                                                                      # la `virgen` es NULL (sin virgen montada): 6 de la raiz y 3 de cada una de las 3 piezas
        assert "reflexión" in _sql(bd, f"SELECT cadena_de_captura FROM {TABLA}")[0][0]                  # el acento se lee tal cual en la base (y en la exportacion a Excel)
        assert _sql(bd, f"SELECT virgen FROM {TABLA}") == [(None,)]                                      # sin virgen montada: NULL en la base, no el texto 'null'


# ===================================================================================================== (14) la correccion de la ronda 1 de la revision (30-10)
# Los revisores escepticos de CD.4 (logs/CD4/revision_ronda1_pruebas/ y revision_ronda1_produccion/) mostraron, cada uno con una mutacion que sobrevivia a los casos de arriba, huecos de lo que el bloque
# de CD.4 pide: la regla «al menos UNA capa valida» de `vigentes_validas` (CD4-D7) nunca vio unas capas validas y otras no, ni una curva «guia» (que solo caia, de rebote, en el caso de las 21 piezas de H9);
# de los tres componentes de la clave de bloque, el LOTE no tenia caso propio; el censo de escritores buscaba solo el SQL literal y no las primitivas del contrato (como si lo hacen D.1 y C.3); la decision
# CD4-D8 («vuelve a medir solo si estan TODOS los escaneos») se probaba con todos o con ninguno; el CONTENIDO de `escaneos_que_faltan` nunca se miraba, solo su largo; y de la medicion guardada de cada pieza
# solo se miraban dos valores. Solo se AGREGA: ningun caso de arriba cambia.

@pytest.fixture(scope="module")
def escaneos_con_el_rojo_recortado():
    """Las 11 piezas de `escaneos` (0 y de 50 a 1000 cGy, las mismas semillas) con el ROJO en el negro del escaner desde 300 cGy: el caso real del plan, el rojo que se recorta (a 800 UM). El verde y el azul siguen
    dando una curva «valida»; el rojo y el gris no (CD.3)."""
    return {o: (d, f"{d}.tif", gen.pieza_de_dosis(d, DEVIC, lado_mm=GRANDE, semilla=o, negro_desde_cgy={"R": 300}).datos) for o, d in enumerate((0,) + DOSIS, 1)}


class TestLosHuecosQueMostroLaRonda1:
    # ------------------------------------------------------------------------------------------------- CD4-D7: «al menos UNA capa valida» (CD4-PROD-R1-02, CD4-PRU-01)
    def test_una_calibracion_con_unas_capas_validas_y_otras_no_es_una_vigente_valida(self, bd, escaneos, escaneos_con_el_rojo_recortado):
        """`vigentes_validas` da las vigentes con AL MENOS UNA capa «valida» (CD4-D7). Las calibraciones de los otros casos tienen las cuatro capas en el mismo estado, asi que «al menos una» y «todas» daban lo mismo:
        con el rojo recortado (el caso real) el verde y el azul valen y el rojo no, y CD.6 se quedaria sin curva si la regla exigiera las cuatro."""
        completa = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-09-01"}, _piezas(escaneos))
        mixta = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-10-20"}, _piezas(escaneos_con_el_rojo_recortado))
        ninguna = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-10-25"}, _piezas(escaneos, {1, 2, 3}))
        estados = _svc().leer(mixta)["estado"]
        assert estados["G"] == VALIDA and estados["B"] == VALIDA and estados["R"].startswith("incompleta: ") and estados["gris"] != VALIDA, estados          # unas validas y otras no
        assert {c: _svc().leer(completa)["estado"][c] for c in CAPAS} == {c: VALIDA for c in CAPAS}                                                         # las cuatro
        assert not any(e == VALIDA for e in _svc().leer(ninguna)["estado"].values())                                                                       # ninguna
        assert [r["id"] for r in _svc().listar()] == [ninguna, mixta, completa]
        assert [r["id"] for r in _svc().vigentes_validas()] == [mixta, completa]

    def test_una_curva_guia_no_es_una_vigente_valida(self, bd, escaneos):
        """Sin piezas de 0 cGy ni pelicula virgen montada el cero es la pieza de MENOR dosis y la curva es una GUIA: nunca pasa a dosis (condicion 5 de DC8). `vigentes_validas` es lo que lee CD.6 y una «guia»
        no es una «valida»; antes solo lo afirmaba, de rebote, el caso de las 21 piezas de H9 (que se salta si esa carpeta no esta en la maquina). Hallado por el otro corrector de la ronda 1 (C02)."""
        valida = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-09-01"}, _piezas(escaneos))
        guia = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-10-25"}, _piezas(escaneos, set(range(2, 12))))
        r = _svc().leer(guia)
        assert r["cero"]["fuente"] == "pieza_de_menor_dosis" and all(e.startswith("guía: ") for e in r["estado"].values()), r["estado"]
        assert [x["id"] for x in _svc().listar()] == [guia, valida]
        assert [x["id"] for x in _svc().vigentes_validas()] == [valida]

    # ------------------------------------------------------------------------------------------------- la clave de bloque: (lote, DATE(fecha_irradiacion), energia) (CD4-PRU-02)
    def test_otro_lote_el_mismo_dia_y_a_la_misma_energia_es_otra_calibracion_y_no_anula_la_primera(self, bd, escaneos):
        """De los tres componentes de la clave de bloque, la energia y el dia tienen su caso (`test_otra_energia_u_otro_dia_es_otra_calibracion`); el LOTE no lo tenia: sin el, guardar el lote L-02 anulaba EN SILENCIO
        la calibracion de L-01 (sus piezas seguian vigentes bajo una raiz anulada y la auditoria decia «guardar» en las dos filas)."""
        a = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))
        b = _svc().guardar("fisico", {**ENCABEZADO, "lote": "L-02"}, _piezas(escaneos, {1, 2, 3}))
        assert _sql(bd, f"SELECT id, lote, activo FROM {TABLA} ORDER BY id") == [(a, "L-01", 1), (b, "L-02", 1)]
        assert _sql(bd, f"SELECT ref, activo, COUNT(*) FROM {PIEZAS} GROUP BY ref, activo ORDER BY ref") == [(a, 1, 3), (b, 1, 3)]          # las piezas de la primera siguen vigentes
        assert [x[0] for x in _auditoria(bd)] == ["guardar", "guardar"] and [r["id"] for r in _svc().listar()] == [b, a]                  # ningun «reemplazo»
        c = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3}))                                                              # y volver a guardar el primer lote reemplaza SOLO ese lote
        assert _sql(bd, f"SELECT id, lote, activo FROM {TABLA} ORDER BY id") == [(a, "L-01", 0), (b, "L-02", 1), (c, "L-01", 1)]
        acciones = _auditoria(bd)
        assert [x[0] for x in acciones] == ["guardar", "guardar", "reemplazo"] and acciones[2][3].endswith(f"; reemplaza id={a}")
        assert _sql(bd, f"SELECT ref, activo, COUNT(*) FROM {PIEZAS} GROUP BY ref, activo ORDER BY ref, activo") == [(a, 0, 3), (b, 1, 3), (c, 1, 3)]

    # ------------------------------------------------------------------------------------------------- CD4-D8: vuelve a medir solo si estan TODOS los escaneos (CD4-PRU-04 y CD4-PRU-05)
    @pytest.mark.parametrize("faltan", [(3,), (2, 6), (1, 2, 3, 4, 5, 6)], ids=["uno", "dos", "todos_menos_uno"])
    def test_con_algun_escaneo_de_menos_recalcular_da_lo_medido_no_vuelve_a_medir_y_nombra_los_que_faltan(self, bd, escaneos, faltan):
        """La decision CD4-D8 se probaba con TODOS los escaneos o con NINGUNO (la carpeta entera borrada). El caso realista de la carpeta en red (P15, DP-152) es que falte UNO: `recalcular` da entonces lo
        medido, `desde_los_escaneos` queda en None y `escaneos_que_faltan` nombra EXACTAMENTE los archivos que faltan -- `<sha256 de sus bytes><extension>`, el nombre de la copia, que CD.5 mostrara al fisico --,
        en el orden del formulario, y no el nombre original del archivo."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 3, 4, 5, 6, 7})))
        esperados = tuple(hashlib.sha256(escaneos[o][2]).hexdigest() + ".tif" for o in sorted(faltan))                          # la verdad: la huella de los bytes que se subieron
        assert len(set(esperados)) == len(faltan) and set(esperados) <= set(os.listdir(_carpeta(bd)))
        for nombre in esperados:
            os.remove(os.path.join(_carpeta(bd), nombre))
        rec = _svc().recalcular(r)
        assert rec.desde_los_escaneos is None and rec.escaneos_que_faltan == esperados
        assert rec.desde_lo_medido is not None and rec.desde_lo_medido.estado("G") == r["estado"]["G"] and _svc().diferencias(r, rec) == []

    # ------------------------------------------------------------------------------------------------- CD4-D11: la medicion guardada de cada pieza es la ENTERA de CD.2 (CD4-PRU-06)
    def test_la_medicion_guardada_de_cada_pieza_es_la_entera_de_cd2(self, bd, escaneos):
        """El plan pide guardar de cada pieza la `MedidaDePieza` ENTERA (CD4-D11): su region, la mediana, la media y n de cada capa, la media, n y la desviacion del centro, las pruebas y la procedencia. Solo se
        miraban el estado y `centro.G.media`, asi que una `medicion` sin la region (o sin la desviacion) pasaba: `diferencias` nunca compara la parte «medicion». La verdad es CD.2 llamada aqui sobre los mismos bytes."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2, 5, 11})))
        campos = {f.name for f in dataclasses.fields(_pel().MedidaDePieza)}
        assert [p["orden"] for p in r["piezas"]] == [1, 2, 5, 11]
        for p in r["piezas"]:
            _, nombre, datos = escaneos[p["orden"]]
            guardada = p["medida"]["medicion"]
            assert set(guardada) == campos, sorted(campos ^ set(guardada))
            fecha = guardada["procedencia"]["fecha_calculo"]
            assert _svc().fecha_iso(fecha) == fecha
            medida = _pel().medir_pieza_uniforme(datos, _P(), nombre, fecha, escala="declarada")
            assert guardada == json.loads(json.dumps(_pel()._json_normal(dataclasses.asdict(medida)))), p["orden"]
        m = r["piezas"][2]["medida"]["medicion"]
        assert m["estado"] == "ok" and m["region"]["n"] > 0 and m["region"]["caja"] and m["escala"] == "declarada"
        assert {"mediana", "media", "n", "iqr"} <= set(m["capas"]["G"]) and set(m["centro"]["G"]) == {"media", "n", "desviacion"}


# ------------------------------------------------------------------------------------------------- el censo de escritores, por AST y con las primitivas del contrato (CD4-PRU-03)
# `test_nadie_mas_escribe_ni_crea_estas_tablas` (arriba) busca solo el texto literal «INSERT INTO <tabla> », «UPDATE <tabla> » y «DELETE FROM <tabla>»: un escritor fuera del servicio que use una primitiva del
# contrato (`anular_fila`, `reemplazar_bloque`, `sql_anular_bloque`) o la constante `TABLA` dentro de un f-string no se veia. Este es el censo de D.1 (tests/test_d1_guardado_placa_mensual.py) y de C.3
# (tests/test_c3_tripwire_escritura_referencias_qc.py), con las dos tablas de CD.4: por (archivo, funcion), no por numero de linea (inmune a la Trampa 5).

EXCLUDE_DIRS = {".venv", "tests", "build", "dist", "__pycache__", ".git", ".pytest_cache", "resources", "mcc_PTW_read"}
PRIMITIVAS_DE_ESCRITURA = {"reemplazar_bloque", "anular_fila", "sql_anular_bloque"}
LAS_TABLAS = (TABLA, PIEZAS)
CONSTANTES_DE_LAS_TABLAS = ("TABLA", "TABLA_PIEZAS")
# Las dos tablas, con su nombre o con la constante del servicio embebida en un f-string (`{TABLA}`, `{TABLA_PIEZAS}`). Las constantes distinguen mayusculas a proposito: las primitivas genericas del contrato
# (`anular_fila`, `reemplazar_bloque`) escriben `{tabla}` en minuscula.
_TABLA_RE = r"(?:calibracion_pelicula(?:_pieza)?\b|(?-i:\{TABLA(?:_PIEZAS)?\}))"
PATRON_DE_ESCRITURA = re.compile(rf"(insert\s+(?:or\s+\w+\s+)?into\s+{_TABLA_RE}|replace\s+into\s+{_TABLA_RE}|update\s+{_TABLA_RE}|delete\s+from\s+{_TABLA_RE}|drop\s+table\s+(?:if\s+exists\s+)?{_TABLA_RE})",
                                 re.IGNORECASE)

# Los UNICOS sitios autorizados, con su motivo: el servicio.
SITIOS_PERMITIDOS = {
    ("services/curva_dosis.py", "<modulo>"): "solo COMPONE los dos INSERT (`SQL_INSERT_CALIBRACION` y `SQL_INSERT_PIEZA`, con las columnas escritas); los ejecuta `guardar` por `reemplazar_bloque`",
    ("services/curva_dosis.py", "guardar"): "mide, ajusta, copia y verifica los escaneos y reemplaza el bloque con su fila de auditoria en UNA transaccion (DA-52)",
    ("services/curva_dosis.py", "anular"): "anula la raiz y sus piezas con su fila de auditoria en la misma transaccion (el permiso lo pide el dialogo de la ventana, CD4-D10)",
}


def _texto_de(nodo):
    """Texto de una cadena o de un f-string, con cada `{nombre}` conservado (asi `f"INSERT INTO {TABLA}"` se reconoce)."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        partes = []
        for valor in nodo.values:
            if isinstance(valor, ast.Constant):
                partes.append(str(valor.value))
            elif isinstance(valor, ast.FormattedValue):
                v = valor.value
                partes.append("{" + v.id + "}" if isinstance(v, ast.Name) else "{" + v.attr + "}" if isinstance(v, ast.Attribute) else "{?}")
        return "".join(partes)
    return None


def _es_una_de_las_tablas(nodo):
    """¿Este argumento ES una de las dos tablas? Su nombre literal o una de las constantes del servicio."""
    if isinstance(nodo, ast.Constant):
        return nodo.value in LAS_TABLAS
    if isinstance(nodo, ast.Name):
        return nodo.id in CONSTANTES_DE_LAS_TABLAS
    if isinstance(nodo, ast.Attribute):
        return nodo.attr in CONSTANTES_DE_LAS_TABLAS
    return False


def _toca_las_tablas(arbol):
    """Solo se examinan los archivos que TOCAN las tablas (mencionan su nombre o importan el servicio): una `TABLA` ajena en otro modulo no es ruido. `analisisImagenes.curva_dosis` (el motor) NO es el servicio."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and ("calibracion_pelicula" in nodo.value or nodo.value == "services.curva_dosis"):
            return True
        if isinstance(nodo, ast.ImportFrom) and (nodo.module == "services.curva_dosis" or (nodo.module == "services" and any(a.name == "curva_dosis" for a in nodo.names))):
            return True
        if isinstance(nodo, ast.Import) and any(a.name == "services.curva_dosis" for a in nodo.names):
            return True
    return False


class _CensoDeEscrituras(ast.NodeVisitor):
    """Recorre el modulo llevando la funcion que envuelve a cada nodo (`<modulo>` fuera de toda funcion)."""

    def __init__(self):
        self._pila = ["<modulo>"]
        self.sitios = set()

    def _entrar(self, nodo):
        self._pila.append(nodo.name)
        self.generic_visit(nodo)
        self._pila.pop()

    visit_FunctionDef = _entrar
    visit_AsyncFunctionDef = _entrar

    def visit_Constant(self, nodo):
        self._revisar_texto(nodo)

    def visit_JoinedStr(self, nodo):
        self._revisar_texto(nodo)           # no se desciende: el texto completo del f-string ya se examino

    def _revisar_texto(self, nodo):
        texto = _texto_de(nodo)
        if texto and PATRON_DE_ESCRITURA.search(texto):
            self.sitios.add(self._pila[-1])

    def visit_Call(self, nodo):
        f = nodo.func
        nombre = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
        if nombre in PRIMITIVAS_DE_ESCRITURA and (any(_es_una_de_las_tablas(a) for a in nodo.args) or any(_es_una_de_las_tablas(k.value) for k in nodo.keywords)):
            self.sitios.add(self._pila[-1])
        self.generic_visit(nodo)


def _sitios_de_archivo(ruta):
    try:
        arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"), filename=str(ruta))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    if not _toca_las_tablas(arbol):
        return set()
    censo = _CensoDeEscrituras()
    censo.visit(arbol)
    return censo.sitios


def _censar(raiz):
    """{(archivo relativo, funcion)} de todo sitio de produccion que escribe en una de las dos tablas. No entra a las carpetas de `EXCLUDE_DIRS` ni a las ocultas."""
    hallazgos = set()
    for carpeta, subcarpetas, archivos in os.walk(raiz):
        subcarpetas[:] = [d for d in subcarpetas if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for archivo in archivos:
            if archivo.endswith(".py"):
                ruta = Path(carpeta, archivo)
                for funcion in _sitios_de_archivo(ruta):
                    hallazgos.add((ruta.relative_to(raiz).as_posix(), funcion))
    return hallazgos


@pytest.fixture(scope="module")
def censo_real():
    return _censar(RAIZ)


class TestElCensoDeEscritores:
    def test_ninguna_escritura_sobre_las_dos_tablas_fuera_del_servicio(self, censo_real):
        nuevos, ausentes = censo_real - set(SITIOS_PERMITIDOS), set(SITIOS_PERMITIDOS) - censo_real
        assert not nuevos, ("Escritura(s) NUEVA(S) sobre `calibracion_pelicula` o `calibracion_pelicula_pieza` fuera del servicio -- se saltan la auditoria y la transaccion unica. Pasa por "
                            f"services.curva_dosis.guardar o anular, o (si de verdad es legitima) declarala en SITIOS_PERMITIDOS con su motivo: {sorted(nuevos)}")
        assert not ausentes, f"Sitio(s) autorizado(s) que ya no aparecen (el servicio cambio de forma, o el censo ya no lo ve): {sorted(ausentes)}"


class TestElCensoDeEscritoresDiscrimina:
    """Rojo dirigido (el patron de D.1 y de C.3): un intruso en un arbol TEMPORAL (nunca en el real) DEBE aparecer en el censo, en cada forma de escribir."""

    def _con_intruso(self, tmp_path, cuerpo, donde="services"):
        servicio = _svc()          # las dos tablas y sus constantes son las del SERVICIO: si cambian de nombre el censo tiene que enterarse (y sin servicio no hay nada que censar)
        assert (servicio.TABLA, servicio.TABLA_PIEZAS) == LAS_TABLAS and all(hasattr(servicio, c) for c in CONSTANTES_DE_LAS_TABLAS)
        (tmp_path / donde).mkdir(exist_ok=True)
        (tmp_path / donde / "_intruso_cd4.py").write_text(cuerpo, encoding="utf-8")
        return _censar(tmp_path)

    @pytest.mark.parametrize("cuerpo", [
        "def cambia(cur):\n    anular_fila(cur, 'calibracion_pelicula', 1, 'u')\n",
        "def cambia(cur):\n    reemplazar_bloque(cur, 'calibracion_pelicula_pieza', [], '', [], 'u')\n",
        "from services.curva_dosis import TABLA\ndef cambia(cur):\n    sql_anular_bloque(TABLA, ['lote'])\n",
        "from services.curva_dosis import TABLA_PIEZAS\ndef cambia(cur):\n    reemplazar_bloque(cur, tabla=TABLA_PIEZAS)\n",
        "from services import curva_dosis\ndef cambia(cur):\n    anular_fila(cur, curva_dosis.TABLA, 1, 'u')\n",
        "def cambia(cur):\n    cur.execute('UPDATE calibracion_pelicula_pieza SET orden = 9')\n",
        "from services.curva_dosis import TABLA\ndef cambia(cur):\n    cur.execute(f'DELETE FROM {TABLA}')\n",
        "def cambia(cur):\n    cur.execute('INSERT OR REPLACE INTO calibracion_pelicula (lote) VALUES (1)')\n"],
        ids=["primitiva_con_la_raiz", "primitiva_con_la_hija", "primitiva_con_la_constante", "primitiva_con_la_constante_por_nombre", "primitiva_con_el_atributo", "update_literal",
             "delete_con_la_constante_en_un_fstring", "insert_or_replace"])
    def test_detecta_cada_forma_de_escribir(self, tmp_path, cuerpo):
        assert self._con_intruso(tmp_path, cuerpo) == {("services/_intruso_cd4.py", "cambia")}

    def test_una_lectura_no_es_una_escritura(self, tmp_path):
        assert self._con_intruso(tmp_path, "def lee(cur):\n    return cur.execute('SELECT lote FROM calibracion_pelicula WHERE id = 1').fetchall()\n") == set()

    def test_una_TABLA_ajena_en_un_modulo_que_no_toca_las_tablas_no_es_ruido(self, tmp_path):
        assert self._con_intruso(tmp_path, "TABLA = 'otra'\ndef escribe(cur):\n    cur.execute(f'INSERT INTO {TABLA} VALUES (1)')\n") == set()

    def test_el_censo_no_mira_los_tests_ni_el_entorno_virtual(self, tmp_path):
        cuerpo = "def cambia(cur):\n    cur.execute('DELETE FROM calibracion_pelicula')\n"
        assert self._con_intruso(tmp_path, cuerpo, "tests") == set()
        assert self._con_intruso(tmp_path, cuerpo, ".venv") == set()


# ===================================================================================================== (15) la decision de Opus de la ronda 1 (CD4-R1-D1 a D3, 30-10)
# Los tres hallazgos de PRODUCCION de la ronda 1 (CD4-PROD-R1-01, CD4-PROD-R1-03 y CD4-PRU-07) los decidio Opus (borradores/CD4/decision_ronda1_Opus.md) y se corrigen solo en `services/curva_dosis.py`. Cada caso
# de abajo cae contra el servicio de antes de la decision (logs/CD4/decision_ronda1/rojo_antes.log) por la razon que dice su nombre, salvo tres BARRERAS que pasan antes y despues: los parametros de fabrica
# tal cual se guardan byte a byte como sin parametros, `piezas_minimas = 2**63 - 1` (el borde de la base) se guarda y se rehace sin diferencias, y la parte de CONTENIDO de lo que ya estaba y cambia (no se toca).
# Toda parametrizacion con enteros enormes lleva `ids` explicitos: pytest hace `str(valor)` para el id y `10**5000` revienta la recoleccion. Las seis pruebas de D3 estan en `TestLosEscaneos` (arriba).

LOS_VALORES_MAL_DADOS = [
    pytest.param("piezas_minimas", "6", id="piezas_minimas-'6'"), pytest.param("piezas_minimas", True, id="piezas_minimas-True"), pytest.param("piezas_minimas", 6.0, id="piezas_minimas-6.0"),
    pytest.param("piezas_minimas", 0, id="piezas_minimas-0"), pytest.param("piezas_minimas", -1, id="piezas_minimas--1"),
    pytest.param("residuo_maximo_pct", "3", id="residuo_maximo_pct-'3'"), pytest.param("residuo_maximo_pct", True, id="residuo_maximo_pct-True"),
    pytest.param("residuo_maximo_pct", float("nan"), id="residuo_maximo_pct-nan"), pytest.param("residuo_maximo_pct", float("inf"), id="residuo_maximo_pct-inf"),
    pytest.param("residuo_maximo_pct", -1.0, id="residuo_maximo_pct--1.0"), pytest.param("residuo_maximo_pct", None, id="residuo_maximo_pct-None"),
    pytest.param("residuo_maximo_pct", [1], id="residuo_maximo_pct-[1]"), pytest.param("residuo_maximo_pct", 10**400, id="residuo_maximo_pct-10**400"),
    pytest.param("dosis_baja_cgy", [1], id="dosis_baja_cgy-[1]"), pytest.param("separacion_minima_u", "2", id="separacion_minima_u-'2'"),
    pytest.param("distancia_en_el_vidrio_mm", "20", id="distancia_en_el_vidrio_mm-'20'"), pytest.param("diferencia_de_fondo_blanco", "0.005", id="diferencia_de_fondo_blanco-'0.005'"),
    pytest.param("modelo", "polinomio", id="modelo-polinomio"), pytest.param("modelo", None, id="modelo-None"),
    pytest.param("version", "CD-2", id="version-CD-2"), pytest.param("version", [1], id="version-[1]")]

LOS_NUMEROS_QUE_NO_CABEN = [
    pytest.param("piezas_minimas", 2**63, "el parámetro de la curva 'piezas_minimas' debe ser un entero de 1 o más", id="piezas_minimas-2**63"),
    pytest.param("piezas_minimas", 10**400, "el parámetro de la curva 'piezas_minimas' debe ser un entero de 1 o más", id="piezas_minimas-10**400"),
    pytest.param("piezas_minimas", 10**5000, "el parámetro de la curva 'piezas_minimas' debe ser un entero de 1 o más", id="piezas_minimas-10**5000"),
    pytest.param("orden", 2**63, "el orden de la pieza 2 de la lista no cabe en la base", id="orden"),
    pytest.param("camara", 2**63, "el equipo_id de la cámara no cabe en la base", id="camara"),
    pytest.param("electrometro", 2**63, "el equipo_id de el electrómetro no cabe en la base", id="electrometro"),          # el «de el» es el `que` de hoy
    pytest.param("dosis_nominal_cgy", 10**400, "la dosis nominal de la pieza 2 debe ser un número finito", id="dosis_nominal_cgy"),
    pytest.param("dosis_medida_cgy", 10**400, "la dosis medida de la pieza 2 debe ser un número finito", id="dosis_medida_cgy")]


class TestLosValoresDeLosParametrosDeLaCurva:
    """CD4-R1-D1 (CD4-PROD-R1-01): `parametros_de_la_curva` se valida por el TIPO de su valor de fabrica (`motor.VALORES_DE_LA_CURVA`, la unica definicion), no solo por el nombre de la clave: antes un valor de otro
    tipo escapaba como `TypeError` crudo o se guardaba, el mismo `'3'` lanzaba con 11 piezas y se guardaba con 4, `modelo` y `version` del diccionario se guardaban distintos de las columnas y `np.int64` salia con un
    error de JSON enganoso."""

    @pytest.mark.parametrize("cuales", [None, LAS_CUATRO_PRIMERAS], ids=["completa", "incompleta"])
    @pytest.mark.parametrize("nombre, valor", LOS_VALORES_MAL_DADOS)
    def test_un_valor_mal_dado_se_rechaza_con_su_nombre_sin_escribir_ni_copiar_nada(self, bd, escaneos, nombre, valor, cuales):
        with pytest.raises(_svc().CurvaDosisError, match=re.escape(f"el parámetro de la curva {nombre!r} ")):
            _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {nombre: valor}}, _piezas(escaneos, cuales))
        assert _conteos(bd) == (0, 0, 0)
        assert not os.path.exists(_carpeta(bd))

    def test_numpy_y_un_entero_por_un_real_se_guardan_con_el_tipo_de_fabrica(self, bd, escaneos):
        cambios = {"piezas_minimas": np.int64(6), "residuo_maximo_pct": 3, "dosis_baja_cgy": np.float64(100.0)}
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": cambios}, _piezas(escaneos)))
        curva = r["parametros"]["curva"]
        assert type(curva["piezas_minimas"]) is int and curva["piezas_minimas"] == 6
        assert type(curva["residuo_maximo_pct"]) is float and curva["residuo_maximo_pct"] == 3.0
        assert type(curva["dosis_baja_cgy"]) is float and curva["dosis_baja_cgy"] == 100.0
        assert _svc().diferencias(r, _svc().recalcular(r)) == []

    def test_los_de_fabrica_tal_cual_se_guardan_byte_a_byte_como_sin_parametros(self, bd, escaneos):
        """BARRERA (pasa antes y despues): con una entrada valida lo guardado no cambia. Mismas piezas, una vez con TODOS los parametros de fabrica y otra sin parametros: los textos JSON de `parametros` y de
        `ajuste` son identicos, y `modelo` y `version` de las columnas dicen lo mismo que `parametros.curva`."""
        _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": dict(_cd().VALORES_DE_LA_CURVA)}, _piezas(escaneos))
        _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos))
        con, sin = _sql(bd, f"SELECT parametros, ajuste, modelo, version FROM {TABLA} ORDER BY id")
        assert con[0] == sin[0] and con[1] == sin[1]
        for parametros, _, modelo, version in (con, sin):
            curva = json.loads(parametros)["curva"]
            assert (modelo, version) == (curva["modelo"], curva["version"]) == ("devic", "CD-1")

    def test_recalcular_rechaza_un_parametro_guardado_que_ya_no_es_valido(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        r["parametros"]["curva"]["residuo_maximo_pct"] = "3"                  # en memoria: lo guardado "ya no es valido"
        with pytest.raises(_svc().CurvaDosisError, match=re.escape("no se puede volver a ajustar: el parámetro de la curva 'residuo_maximo_pct' debe ser un número finito de 0 o más, no '3'")):
            _svc().recalcular(r)

    def test_un_parametro_de_un_tipo_que_el_servicio_no_sabe_validar_se_rechaza(self, bd, escaneos, monkeypatch):
        monkeypatch.setitem(_cd().VALORES_DE_LA_CURVA, "nuevo", [1])          # un parametro nuevo del motor, de un tipo que el servicio no conoce
        with pytest.raises(_svc().CurvaDosisError, match="no es un número ni un nombre: este servicio no sabe validarlo"):
            _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"nuevo": [1]}}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert _conteos(bd) == (0, 0, 0)

    def test_una_incertidumbre_que_no_cabe_en_un_float_es_curva_dosis_error(self, bd, escaneos):
        with pytest.raises(_svc().CurvaDosisError, match="la incertidumbre de la dosis medida debe ser un número finito"):
            _svc().guardar("fisico", {**ENCABEZADO, "u_dosis_medida_pct": 10**400}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert _conteos(bd) == (0, 0, 0)


class TestLosNumerosQueNoCabenEnLaBase:
    """CD4-R1-D1, la quinta cosa: un entero que no cabe en un INTEGER de SQLite (`orden`, `equipo_id`, `piezas_minimas`) o en un float (las dosis, `piezas_minimas = 10**400`) escapaba como `OverflowError` crudo,
    algunos con las copias ya escritas; y un entero de mas de 4300 cifras hacia reventar el propio mensaje de rechazo con un `ValueError`."""

    @pytest.mark.parametrize("donde, valor, texto", LOS_NUMEROS_QUE_NO_CABEN)
    def test_un_entero_que_no_cabe_en_la_base_se_rechaza_antes_de_copiar(self, bd, escaneos, donde, valor, texto):
        cabeza, piezas = dict(ENCABEZADO), _piezas(escaneos, LAS_CUATRO_PRIMERAS)
        if donde == "piezas_minimas":
            cabeza["parametros_de_la_curva"] = {"piezas_minimas": valor}
        elif donde == "orden":
            piezas[1]["orden"] = valor
        elif donde in ("camara", "electrometro"):
            cabeza[donde] = {**(cabeza.get(donde) or dict.fromkeys(_svc().CLAVES_DE_UN_EQUIPO)), "equipo_id": valor}
        else:
            piezas[1][donde] = valor
        with pytest.raises(_svc().CurvaDosisError, match=re.escape(texto)):
            _svc().guardar("fisico", cabeza, piezas)
        assert _conteos(bd) == (0, 0, 0)
        assert not os.path.exists(_carpeta(bd))                           # ni una copia de un escaneo

    @pytest.mark.parametrize("caso", ["u_dosis_medida_pct", "camara.factor", "residuo_maximo_pct", "piezas_minimas-negativa", "escaner_declarado", "modo_de_escaneo", "fecha_irradiacion", "fecha_escaneo",
                                      "no_existe"],
                             ids=["u_dosis_medida_pct", "camara.factor", "residuo_maximo_pct", "piezas_minimas-negativa", "escaner_declarado", "modo_de_escaneo", "fecha_irradiacion", "fecha_escaneo",
                                  "no_existe"])
    def test_un_entero_de_mas_de_4300_cifras_se_rechaza_con_su_texto(self, bd, escaneos, caso):
        cabeza, piezas = dict(ENCABEZADO), _piezas(escaneos, LAS_CUATRO_PRIMERAS)
        if caso == "u_dosis_medida_pct":
            cabeza["u_dosis_medida_pct"] = ENORME
        elif caso == "camara.factor":
            cabeza["camara"] = {**cabeza["camara"], "factor": ENORME}
        elif caso == "residuo_maximo_pct":
            cabeza["parametros_de_la_curva"] = {"residuo_maximo_pct": ENORME}
        elif caso == "piezas_minimas-negativa":
            cabeza["parametros_de_la_curva"] = {"piezas_minimas": -ENORME}
        elif caso == "escaner_declarado":
            cabeza["escaner_declarado"] = ENORME
        elif caso == "modo_de_escaneo":
            cabeza["modo_de_escaneo"] = ENORME
        elif caso == "fecha_irradiacion":
            cabeza["fecha_irradiacion"] = ENORME
        elif caso == "fecha_escaneo":
            piezas[1]["fecha_escaneo"] = ENORME
        else:
            cabeza["parametros_de_la_curva"] = {"no_existe": ENORME}
        with pytest.raises(_svc().CurvaDosisError, match=re.escape("con un entero de más de 4300 cifras")):
            _svc().guardar("fisico", cabeza, piezas)
        assert _conteos(bd) == (0, 0, 0)

    def test_menos_cero_se_guarda_como_cero(self, bd, escaneos):
        """`-0.0` es un 0 de 0 o mas, pero escrito como texto es «-0»: con una tolerancia de -0.0 la curva decia «la tolerancia es ±-0 %». Se guarda `0.0`."""
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"residuo_maximo_pct": -0.0}}, _piezas(escaneos)))
        assert math.copysign(1.0, r["parametros"]["curva"]["residuo_maximo_pct"]) == 1.0
        assert "±-0" not in str(r["estado"]) and "±-0" not in str(r)

    def test_piezas_minimas_2_63_menos_1_se_guarda_y_no_da_diferencias(self, bd, escaneos):
        """BARRERA (pasa antes y despues): el borde de la base, `2**63 - 1`, es un entero valido; apretar el limite lo romperia."""
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"piezas_minimas": 2**63 - 1}}, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        assert r["parametros"]["curva"]["piezas_minimas"] == 2**63 - 1
        assert _svc().diferencias(r, _svc().recalcular(r)) == []


class TestUnaCopiaQueYaNoEsSuHuella:
    """CD4-R1-D2 (CD4-PROD-R1-03): `recalcular` no vuelve a medir una copia que ya no es su huella sha256 (DA-81: la copia ES su huella) y `diferencias` lo dice con una linea por pieza. Antes volvia a medir sobre
    otro escaneo y daba de 149 a 229 diferencias numericas sin decir la causa."""

    def test_no_se_vuelve_a_medir_y_diferencias_lo_dice_por_pieza(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        nombre2, copia2 = escaneos[2][1], hashlib.sha256(escaneos[2][2]).hexdigest() + ".tif"          # la verdad sale de los bytes, no del servicio
        with open(os.path.join(_carpeta(bd), copia2), "wb") as f:
            f.write(escaneos[3][2])                                        # la copia de la pieza 2 pasa a tener los bytes del escaneo de la pieza 3
        rec = _svc().recalcular(r)
        assert rec.escaneos_que_faltan == () and rec.escaneos_que_no_coinciden == (copia2,)
        assert rec.desde_los_escaneos is None and rec.desde_lo_medido is not None
        dif = _svc().diferencias(r, rec)
        assert dif == [_svc().TEXTO_COPIA_QUE_NO_COINCIDE.format(orden=2, archivo=nombre2, copia=copia2)]
        assert dif[0].startswith(f"la pieza 2 ({nombre2}): su copia {copia2} junto a la base ya no coincide con su huella sha256") and dif[0].endswith("ninguna pieza desde su escaneo")

    def test_intacta_ninguna_copia_deja_de_coincidir(self, bd, escaneos):
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos)))
        rec = _svc().recalcular(r)
        assert rec.escaneos_que_no_coinciden == () and rec.escaneos_que_faltan == () and rec.desde_los_escaneos is not None
        assert _svc().diferencias(r, rec) == []

    def test_un_recalculo_de_tres_campos_sigue_valiendo(self):
        """`Recalculo` gana un cuarto campo con valor por omision: quien lo construya con los tres de antes sigue pudiendo."""
        rec = _svc().Recalculo(None, None, ())
        assert rec.escaneos_que_faltan == () and rec.escaneos_que_no_coinciden == ()
        assert _svc().Recalculo(None, None, (), ("a.tif",)).escaneos_que_no_coinciden == ("a.tif",)


# ===================================================================================================== (16) la ronda 2 de la revision (CD4-R2, 30-10)
# Los dos revisores de la ronda 2 (logs/CD4/revision_ronda2_pruebas/ y revision_ronda2_conformidad/) revisaron lo que aplico la decision de la ronda 1 y mostraron, cada uno con una mutacion que sobrevivia a los 192 casos de
# arriba, tres huecos de las pruebas (CD4-R2-PRU-01 a PRU-03; el cuarto, PRU-04, es del registro de mutaciones y se arregla en `cd4_mutaciones.py`) y uno de la conformidad con la decision de la ronda 1 (CD4-R2-PROD-01: nan, inf,
# bool y texto en una dosis siguen rechazandose con el mensaje de CD.3 y ninguna prueba lo fijaba). Ademas, un hallazgo de PRODUCCION de la clase que D3 cerro en `guardar` (CD4-R2-PROD-02, decision CD4-R2-D1): `recalcular`
# dejaba escapar el `OSError` crudo de una copia que existe y no se puede leer. Solo se AGREGA: ningun caso de arriba cambia. Toda parametrizacion con enteros enormes lleva `ids` explicitos.

EL_RANGO_DE_LA_BASE = "(un entero de -9223372036854775808 a 9223372036854775807)"
LOS_TEXTOS_DE_NO_CABE = {"orden": "el orden de la pieza 2 de la lista no cabe en la base", "camara": "el equipo_id de la cámara no cabe en la base",
                         "electrometro": "el equipo_id de el electrómetro no cabe en la base"}          # el «de el» es el `que` de hoy
LOS_SITIOS_DE_UN_ENTERO = ["orden", "camara", "electrometro"]
# nan, inf, -inf, bool y texto en cada una de las dos dosis: el servicio los deja pasar a CD.3 (`pieza_de_calibracion`) y su `ValueError` sale tal cual como `CurvaDosisError` (D1, punto 8)
LAS_DOSIS_QUE_RECHAZA_CD3 = [pytest.param(campo, valor, id=f"{campo}-{etiqueta}") for campo in ("dosis_nominal_cgy", "dosis_medida_cgy")
                             for etiqueta, valor in (("nan", float("nan")), ("inf", float("inf")), ("menos_inf", float("-inf")), ("True", True), ("texto", "100"))]
LAS_LECTURAS_QUE_FALLAN = [pytest.param(PermissionError, 13, "sin permiso", id="permiso"),
                           pytest.param(FileNotFoundError, 2, "No existe el archivo o el directorio", id="desaparece_entre_el_isfile_y_el_open"),
                           pytest.param(OSError, 5, "Error de entrada/salida", id="oserror_generico")]


def _con_el_entero_en(donde, valor, escaneos):
    """(encabezado, piezas) de una calibracion INCOMPLETA y barata (las cuatro primeras piezas) con `valor` en el `orden` de la pieza 2 o en el `equipo_id` de la camara o del electrometro."""
    cabeza, piezas = dict(ENCABEZADO), _piezas(escaneos, LAS_CUATRO_PRIMERAS)
    if donde == "orden":
        piezas[1]["orden"] = valor
    else:
        cabeza[donde] = {**cabeza[donde], "equipo_id": valor}
    return cabeza, piezas


@pytest.fixture(scope="module")
def la_medida_de_la_pieza_2(escaneos):
    """La `MedidaDePieza` de la pieza 2 tal como la mide el servicio (CD.2, escala declarada): el cuarto argumento con que las pruebas de las dosis mal dadas llaman a CD.3 DIRECTAMENTE."""
    _, nombre, datos = escaneos[2]
    return _pel().medir_pieza_uniforme(datos, _P(), nombre, "2026-10-30", escala="declarada")


class TestLosHuecosQueMostroLaRonda2:
    # ------------------------------------------------------------------------------------------------- CD4-R2-PRU-01: el PISO del rango de 64 bits
    @pytest.mark.parametrize("donde", LOS_SITIOS_DE_UN_ENTERO, ids=LOS_SITIOS_DE_UN_ENTERO)
    def test_un_entero_menor_que_el_piso_de_64_bits_se_rechaza_antes_de_copiar(self, bd, escaneos, donde):
        """`LOS_NUMEROS_QUE_NO_CABEN` solo probaba el TOPE (`2**63`): quitar el piso de `_entero_que_cabe_en_la_base` dejaba pasar los 192 casos, y un `orden` o un `equipo_id` menor que `-2**63` escapaba como `OverflowError` crudo
        del INSERT con las cuatro copias de los escaneos ya escritas junto a la base. Aqui: `-2**63 - 1` en el orden y en los dos `equipo_id`, con el rango en el mensaje."""
        cabeza, piezas = _con_el_entero_en(donde, -2**63 - 1, escaneos)
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", cabeza, piezas)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"{LOS_TEXTOS_DE_NO_CABE[donde]} {EL_RANGO_DE_LA_BASE}, no -9223372036854775809"
        assert _conteos(bd) == (0, 0, 0)
        assert not os.path.exists(_carpeta(bd))                           # ni una copia de un escaneo

    @pytest.mark.parametrize("donde", LOS_SITIOS_DE_UN_ENTERO, ids=LOS_SITIOS_DE_UN_ENTERO)
    def test_el_piso_exacto_de_64_bits_se_guarda_y_se_rehace_sin_diferencias(self, bd, escaneos, donde):
        """BARRERA (pasa antes y despues de CD4-R2): `-2**63` es el menor INTEGER de SQLite y SI cabe; apretar el piso (`-2**63 <` en lugar de `<=`) lo rechazaria. El borde de arriba ya lo fija
        `test_piezas_minimas_2_63_menos_1_se_guarda_y_no_da_diferencias`."""
        cabeza, piezas = _con_el_entero_en(donde, -2**63, escaneos)
        r = _svc().leer(_svc().guardar("fisico", cabeza, piezas))
        if donde == "orden":
            assert [p["orden"] for p in r["piezas"]] == [-2**63, 1, 3, 4]
        else:
            assert r[f"{donde}_equipo_id"] == -2**63 and type(r[f"{donde}_equipo_id"]) is int
        assert _svc().diferencias(r, _svc().recalcular(r)) == []

    # ------------------------------------------------------------------------------------------------- CD4-R2-PRU-02: un entero de mas de 4300 cifras en el mensaje del orden y del equipo_id
    @pytest.mark.parametrize("donde", LOS_SITIOS_DE_UN_ENTERO, ids=LOS_SITIOS_DE_UN_ENTERO)
    def test_un_entero_de_mas_de_4300_cifras_en_el_orden_o_el_equipo_id_se_rechaza_con_su_texto(self, bd, escaneos, donde):
        """D1-8 pasa `ENORME` por nueve mensajes de rechazo pero no por el del orden que no cabe ni por el del `equipo_id` que no cabe (D1-7 usa `2**63`, de 19 cifras): si cualquiera de los dos vuelve a `!r`, el propio
        mensaje revienta con un `ValueError` crudo («Exceeds the limit (4300 digits)»). `CurvaDosisError` ES un `ValueError`: el TIPO exacto es lo que distingue el rechazo del servicio del error crudo."""
        cabeza, piezas = _con_el_entero_en(donde, ENORME, escaneos)
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", cabeza, piezas)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"{LOS_TEXTOS_DE_NO_CABE[donde]} {EL_RANGO_DE_LA_BASE}, no un int con un entero de más de 4300 cifras"
        assert _conteos(bd) == (0, 0, 0)
        assert not os.path.exists(_carpeta(bd))

    @pytest.mark.parametrize("caso", ["modelo", "dosis_nominal_cgy", "dosis_medida_cgy", "orden_no_entero", "equipo_id_no_entero"],
                             ids=["modelo", "dosis_nominal_cgy", "dosis_medida_cgy", "orden_no_entero", "equipo_id_no_entero"])
    def test_un_entero_de_mas_de_4300_cifras_en_el_resto_de_los_mensajes_de_guardar_se_rechaza_con_su_texto(self, bd, escaneos, caso):
        """CD4-R2-M1 (decision del corrector, vetable): medido sitio a sitio (scripts/cd4_r2_sitios_como_texto.py), de las 14 llamadas de `_como_texto(` que alcanza `guardar` ninguna prueba cubria, ademas del orden y del
        `equipo_id` que no caben (arriba), cuatro mas: el `modelo` o la `version` que no son los del motor, una dosis entera que no cabe en un float, un orden que no es un entero y un `equipo_id` que no es un entero. Los dos
        ultimos se alcanzan con un contenedor que lleva el entero enorme dentro (como el caso `no_existe` de D1-8): `repr` de la lista lanza el mismo `ValueError`, y el texto dice «un list»."""
        cabeza, piezas = dict(ENCABEZADO), _piezas(escaneos, LAS_CUATRO_PRIMERAS)
        enorme, lista = "un int con un entero de más de 4300 cifras", "un list con un entero de más de 4300 cifras"
        if caso == "modelo":
            cabeza["parametros_de_la_curva"] = {"modelo": ENORME}
            esperado = f"el parámetro de la curva 'modelo' es el del motor ({_cd().VALORES_DE_LA_CURVA['modelo']!r}) y no se elige, no {enorme}"
        elif caso in ("dosis_nominal_cgy", "dosis_medida_cgy"):
            piezas[1][caso] = ENORME
            esperado = f"la dosis {'nominal' if caso == 'dosis_nominal_cgy' else 'medida'} de la pieza 2 debe ser un número finito, no {enorme}"
        elif caso == "orden_no_entero":
            piezas[1]["orden"] = [ENORME]
            esperado = f"el orden de la pieza 2 de la lista debe ser un entero que no se repite, no {lista}"
        else:
            cabeza["camara"] = {**cabeza["camara"], "equipo_id": [ENORME]}
            esperado = f"el equipo_id de la cámara es un entero o nada, no {lista}"
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", cabeza, piezas)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == esperado
        assert _conteos(bd) == (0, 0, 0)
        assert not os.path.exists(_carpeta(bd))

    # ------------------------------------------------------------------------------------------------- CD4-R2-PRU-03: el texto con que se rechaza un modelo o una version que no son los del motor
    @pytest.mark.parametrize("nombre, valor", [("modelo", "polinomio"), ("version", "CD-0")], ids=["modelo", "version"])
    def test_un_modelo_o_una_version_que_no_son_los_del_motor_dicen_que_no_se_eligen_con_el_mensaje_entero(self, bd, escaneos, nombre, valor):
        """D1-1 solo compara el prefijo `el parámetro de la curva '<nombre>' `: la RAZON («es el del motor (...) y no se elige, no ...») no la fijaba nadie, y copiar y pegar la de los reales («debe ser un número finito de 0
        o más») pasaba los 192 casos: el fisico habria leido que el modelo debe ser un numero. Lo de fabrica sale de `motor.VALORES_DE_LA_CURVA` (la unica definicion) y no de un texto copiado aqui; `CD-0` es una
        version que el motor nunca tendra (la suya empieza en `CD-1`)."""
        fabrica = _cd().VALORES_DE_LA_CURVA[nombre]
        assert valor != fabrica
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {nombre: valor}}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"el parámetro de la curva {nombre!r} es el del motor ({fabrica!r}) y no se elige, no {valor!r}"
        assert _conteos(bd) == (0, 0, 0)
        assert not os.path.exists(_carpeta(bd))

    # ------------------------------------------------------------------------------------------------- CD4-R2-PROD-01: nan, inf, bool y texto en una dosis se rechazan con el mensaje de CD.3
    @pytest.mark.parametrize("campo, valor", LAS_DOSIS_QUE_RECHAZA_CD3)
    def test_una_dosis_que_no_es_un_numero_se_rechaza_con_el_mensaje_de_cd3_y_con_ningun_otro(self, bd, escaneos, la_medida_de_la_pieza_2, campo, valor):
        """D1, punto 8: nan, inf, bool y texto en una dosis «siguen rechazandose con el mensaje de CD.3, que no cambia»; el servicio solo se adelanta a CD.3 con el entero que no cabe en un float (`float(10**400)` lanza
        `OverflowError`). `test_una_dosis_mal_dada_la_dice_el_servicio_y_no_escribe_ni_copia_nada` pide solo `match="dosis"`, asi que ampliar el control del servicio a toda dosis no finita (con su propio texto) pasaba los
        192 casos. La verdad es CD.3 LLAMADO AQUI con la misma dosis: la prueba sobrevive a un cambio de redaccion de CD.3 (CD.10) y no a que el servicio los pise con otro texto."""
        piezas = _piezas(escaneos, {1, 2, 3})
        piezas[1] = {**piezas[1], campo: valor}
        with pytest.raises(ValueError) as cd3:
            _cd().pieza_de_calibracion(piezas[1]["orden"], piezas[1]["dosis_nominal_cgy"], piezas[1]["dosis_medida_cgy"], la_medida_de_la_pieza_2)
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", ENCABEZADO, piezas)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == str(cd3.value)
        assert _conteos(bd) == (0, 0, 0)
        assert not os.path.exists(_carpeta(bd))

    # ------------------------------------------------------------------------------------------------- CD4-R2-PROD-02 (decision CD4-R2-D1): una copia que existe y no se puede leer
    @pytest.mark.parametrize("clase, numero, razon", LAS_LECTURAS_QUE_FALLAN)
    def test_recalcular_con_una_copia_que_existe_y_no_se_puede_leer_es_curva_dosis_error(self, bd, escaneos, monkeypatch, clase, numero, razon):
        """`recalcular` promete `CurvaDosisError` «si lo guardado ya no se puede leer» y dejaba escapar el `OSError` crudo (un `PermissionError`, o el error de una carpeta de red, DP-152) si la copia de un escaneo existe
        y no se puede abrir: la misma clase que D3 cerro en la lectura previa y en la de vuelta de `guardar`, y D2 hizo que `recalcular` lea CADA copia entera. El texto trae la copia, el error del sistema y el prefijo de
        `recalcular` (el `except` exterior envuelve con el suyo todo lo que sea un `ValueError`, y `CurvaDosisError` lo es). Sin `chmod` (si la prueba corre como root un `chmod` no impide leer): se parchea `open`, solo
        para la copia de la pieza 2, DENTRO de un `monkeypatch.context()`. El caso del medio es el archivo que desaparece entre el `isfile` y el `open`."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        nombre2 = hashlib.sha256(escaneos[2][2]).hexdigest() + ".tif"                 # la verdad sale de los bytes, no del servicio
        copia2 = os.path.join(_carpeta(bd), nombre2)
        abrir_de_verdad = builtins.open

        def abrir(ruta, *a, **k):
            modo = a[0] if a else k.get("mode", "r")
            if modo == "rb" and os.path.normpath(os.fspath(ruta)) == os.path.normpath(copia2):
                raise clase(numero, razon, ruta)
            return abrir_de_verdad(ruta, *a, **k)

        with monkeypatch.context() as m:
            m.setattr(builtins, "open", abrir)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().recalcular(r)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == ("lo guardado de la calibración no se puede volver a ajustar: "
                                f"no se pudo leer la copia del escaneo {nombre2} junto a la base: [Errno {numero}] {razon}: {copia2!r}")
        rec = _svc().recalcular(r)          # la copia sigue ahi, intacta: no era un escaneo que faltara ni uno que ya no coincidiera, y sin el fallo `recalcular` la da por buena
        assert rec.escaneos_que_faltan == () and rec.escaneos_que_no_coinciden == () and rec.desde_los_escaneos is not None
        assert _svc().diferencias(r, rec) == []


# ===================================================================================================== (17) el barrido por AST de la ronda 2 (BARREDOR, 30-10)
# Los revisores de la ronda 2 mostraron que 4 de sus 6 mutaciones propias sobrevivian a los 192 casos: la bateria `cd4_mutaciones.py` se escribio a mano y deja huecos. El BARREDOR genero por AST TODA mutacion de una sola
# sustitucion del servicio (scripts/cd4_barrido_ast.py: comparaciones, and/or, not, constantes, if True/False, raise, except, return, conversiones, enunciados...) y corrio cada una contra los 221 casos de arriba
# (scripts/cd4_barrido_correr.py, logs/CD4/ronda2_barrido/barrido.csv). Cada caso de esta seccion mata una o varias de las que SOBREVIVIAN (mutaciones R2-BA-* de `cd4_mutaciones.py`, con su id del barrido). Solo se AGREGA.

LOS_CUATRO_OBLIGATORIOS = ("lote", "tipo_pelicula", "fecha_irradiacion", "energia")
LAS_COLUMNAS_OPCIONALES_DE_LA_RAIZ = ("acelerador", "observaciones", "u_dosis_medida_pct", "camara_modelo", "camara_serie", "camara_factor", "camara_equipo_id", "electrometro_modelo", "electrometro_serie",
                                      "electrometro_factor", "electrometro_equipo_id")
UN_EQUIPO_DE_PURA_NADA = {"modelo": None, "serie": None, "factor": None, "equipo_id": None}
LO_OPCIONAL_EN_NADA = {"acelerador": None, "condiciones": None, "camara": None, "electrometro": None, "u_dosis_medida_pct": None, "escaner_declarado": None, "modo_de_escaneo": None, "observaciones": None,
                       "parametros_de_la_curva": None}


class TestElBarridoPorAstDeLaRonda2:
    # ------------------------------------------------------------------------------------------------- lo opcional del encabezado, ausente o en nada
    @pytest.mark.parametrize("como", ["ausente", "en_nada", "equipos_de_pura_nada"], ids=["ausente", "en_nada", "equipos_de_pura_nada"])
    def test_un_encabezado_con_solo_lo_obligatorio_guarda_todo_lo_opcional_como_nada(self, bd, escaneos, como):
        """Todos los casos de arriba parten de `ENCABEZADO`, que trae TODO lo opcional: ninguno guardaba una calibracion con lo opcional ausente (o en `None`), asi que `_texto(None, ..., False)` -> `None`, el `{}` de las
        condiciones, los equipos en nada, la incertidumbre en nada y el modo y el escaner en nada nunca se ejercitaban (el barrido: la condicion `valor is None and not obligatorio` en `False`, ese `return None` en `True` o
        omitido). Lo guardado es NULL de verdad (no el texto 'null' ni un cero), `condiciones` es `{}` y la cadena de captura lleva el escaner y el modo en nada."""
        cabeza = {k: ENCABEZADO[k] for k in LOS_CUATRO_OBLIGATORIOS}
        if como == "en_nada":
            cabeza.update(LO_OPCIONAL_EN_NADA)
        elif como == "equipos_de_pura_nada":
            cabeza.update({"camara": dict(UN_EQUIPO_DE_PURA_NADA), "electrometro": dict(UN_EQUIPO_DE_PURA_NADA)})
        nuevo = _svc().guardar("fisico", cabeza, _piezas(escaneos, {1, 2}))
        assert _sql(bd, f"SELECT {', '.join(LAS_COLUMNAS_OPCIONALES_DE_LA_RAIZ)}, condiciones FROM {TABLA}") == [(None,) * len(LAS_COLUMNAS_OPCIONALES_DE_LA_RAIZ) + ("{}",)]
        r = _svc().leer(nuevo)
        assert r["condiciones"] == {}
        assert (r["cadena_de_captura"]["escaner_declarado"], r["cadena_de_captura"]["modo_de_escaneo"]) == (None, None)
        assert _sql(bd, f"SELECT escaner_declarado FROM {PIEZAS} ORDER BY orden") == [(None,), (None,)]

    # ------------------------------------------------------------------------------------------------- el limite de la incertidumbre de la dosis
    def test_una_incertidumbre_de_cero_se_guarda_y_una_apenas_negativa_no(self, bd, escaneos):
        """`_numero(..., minimo=0.0)` rechaza lo MENOR que cero: el cero mismo es una incertidumbre valida (un instrumento ideal) y se guarda como real. D1 solo probaba -1.0, asi que `<` -> `<=` (el cero deja de caber)
        pasaba todos los casos (el barrido). El otro lado del limite: lo apenas negativo se rechaza con el mensaje que dice el minimo."""
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "u_dosis_medida_pct": 0}, _piezas(escaneos, {1, 2})))
        assert r["u_dosis_medida_pct"] == 0.0 and type(r["u_dosis_medida_pct"]) is float
        assert type(r["ajuste"]["u_dosis_medida_pct"]) is float          # y en la copia del ajuste (CD.3 guarda lo que recibe): `0` entero se guarda `0.0`
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "u_dosis_medida_pct": -1e-9, "lote": "otro"}, _piezas(escaneos, {1, 2}))
        assert str(e.value) == "la incertidumbre de la dosis medida debe ser un número finito de 0 o más o nada, no -1e-09"

    # ------------------------------------------------------------------------------------------------- un equipo que no es un diccionario
    @pytest.mark.parametrize("equipo", [5, "FC65-G", ["modelo", "serie", "factor", "equipo_id"], ("modelo", "serie", "factor", "equipo_id")], ids=["entero", "texto", "lista_con_las_cuatro_claves", "tupla_con_las_cuatro_claves"])
    @pytest.mark.parametrize("donde, que", [("camara", "la cámara"), ("electrometro", "el electrómetro")], ids=["camara", "electrometro"])
    def test_un_equipo_que_no_es_un_diccionario_se_rechaza_con_curva_dosis_error_y_su_texto(self, bd, escaneos, donde, que, equipo):
        """`_equipo` pide un diccionario con EXACTAMENTE las cuatro claves, o nada. Los casos de arriba solo dan diccionarios (con una clave de mas o de menos): quitar la comprobacion `isinstance(datos, dict)` (el barrido:
        la condicion `or` con solo su segundo operando) dejaba pasar un entero (`set(5)` lanza un `TypeError` crudo) y una lista o una tupla con las cuatro claves (`set(...)` da las cuatro claves y el acceso por clave
        lanza un `TypeError`). Y el `datos is None` de la primera linea de `_equipo` ya lo cubre el caso de lo opcional en nada."""
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, donde: equipo}, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"{que} es un diccionario con modelo, serie, factor, equipo_id, o nada"
        assert _conteos(bd) == (0, 0, 0)

    # ------------------------------------------------------------------------------------------------- unos parametros de la curva que no son un diccionario
    @pytest.mark.parametrize("parametros", [5, "modelo", ["modelo"], [], ("residuo_maximo_pct",)], ids=["entero", "texto", "lista_con_un_nombre_valido", "lista_vacia", "tupla_con_un_nombre_valido"])
    def test_unos_parametros_de_la_curva_que_no_son_un_diccionario_se_rechazan_con_su_texto(self, bd, escaneos, parametros):
        """D1 solo probaba un diccionario con un nombre que no existe. Sin el `isinstance(parametros, dict)` (el barrido: la condicion `or` con solo su segundo operando) un entero lanza un `TypeError` crudo y una lista o
        una tupla de nombres validos (o vacia) pasa la comprobacion de los nombres y se guarda como si no se hubiera dado nada."""
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": parametros}, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"los parámetros de la curva son un diccionario con nombres de PARAMETROS_DE_LA_CURVA, no {parametros!r}"
        assert _conteos(bd) == (0, 0, 0)

    # ------------------------------------------------------------------------------------------------- el tipo del valor de un parametro de la curva
    @pytest.mark.parametrize("nombre", ["modelo", "version"], ids=["modelo", "version"])
    def test_un_objeto_que_dice_ser_igual_al_nombre_del_motor_no_es_el_nombre(self, bd, escaneos, nombre):
        """`modelo` y `version` se admiten solo si son TEXTO e iguales al de fabrica. La comparacion `valor != fabrica` sola (el barrido: la condicion `or` con solo su segundo operando) deja pasar cualquier objeto cuyo
        `__eq__` diga que si, y se guardaria el nombre del motor en su lugar: solo el `isinstance(valor, str)` lo detiene."""
        class IgualATodo:
            __hash__ = None

            def __eq__(self, otro):
                return True

            def __ne__(self, otro):
                return False

            def __repr__(self):
                return "IgualATodo()"
        fabrica = _cd().VALORES_DE_LA_CURVA[nombre]
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {nombre: IgualATodo()}}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert str(e.value) == f"el parámetro de la curva {nombre!r} es el del motor ({fabrica!r}) y no se elige, no IgualATodo()"
        assert _conteos(bd) == (0, 0, 0)

    def test_un_parametro_nuevo_del_motor_de_valor_booleano_no_se_valida_como_un_entero(self, bd, escaneos, monkeypatch):
        """En Python `True` es un `int`: un parametro nuevo del motor cuyo valor de fabrica fuera un booleano caeria en la rama de los enteros si el servicio no excluyera `bool` (el barrido: la condicion `and` con solo su
        primer operando) y se validaria como «un entero de 1 o más». El servicio no sabe validarlo, y lo dice (la rama de abajo del todo)."""
        with monkeypatch.context() as m:
            m.setitem(_cd().VALORES_DE_LA_CURVA, "bandera", True)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"bandera": 1}}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert str(e.value) == "el parámetro de la curva 'bandera' no es un número ni un nombre: este servicio no sabe validarlo"
        assert _conteos(bd) == (0, 0, 0)

    @pytest.mark.parametrize("nombre, valor", [("piezas_minimas", 1)] + [(n, 0.0) for n in ("residuo_maximo_pct", "residuo_maximo_bajas_pct", "dosis_baja_cgy", "resolucion_maxima_pct", "separacion_minima_u",
                                                                                           "distancia_en_el_vidrio_mm", "diferencia_de_fondo_blanco")],
                             ids=["piezas_minimas-1", "residuo_maximo_pct-0", "residuo_maximo_bajas_pct-0", "dosis_baja_cgy-0", "resolucion_maxima_pct-0", "separacion_minima_u-0", "distancia_en_el_vidrio_mm-0",
                                  "diferencia_de_fondo_blanco-0"])
    def test_el_limite_mismo_de_cada_parametro_de_la_curva_se_guarda_con_su_tipo_y_se_rehace_sin_diferencias(self, bd, escaneos, nombre, valor):
        """Los casos de D1 prueban el valor de AFUERA del limite (0 en un entero de «1 o más», -1.0 en un real de «0 o más»): el limite mismo (`1` y `0.0`, que SI son validos) no lo probaba nadie, asi que apretar
        cualquiera de las dos comparaciones (`<` -> `<=`: el barrido) pasaba todos los casos. Cada parametro en su limite se guarda con el tipo de fabrica y lo guardado se rehace sin diferencias."""
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {nombre: valor}}, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        guardado = r["parametros"]["curva"][nombre]
        assert guardado == valor and type(guardado) is type(valor)
        assert _svc().diferencias(r, _svc().recalcular(r)) == []

    # ------------------------------------------------------------------------------------------------- un encabezado que no es un diccionario
    @pytest.mark.parametrize("encabezado", [None, 5, "lote", [], ["lote", "tipo_pelicula", "fecha_irradiacion", "energia"]], ids=["nada", "entero", "texto", "lista_vacia", "lista_con_las_cuatro_claves_obligatorias"])
    def test_un_encabezado_que_no_es_un_diccionario_se_rechaza_con_su_texto(self, bd, escaneos, encabezado):
        """Todos los casos de encabezado mal formado dan un diccionario. Sin la primera comprobacion de `_encabezado_valido` (el barrido: su `if` en `False` o su `raise` en `pass`) un `None` o un entero lanzan un
        `TypeError` crudo y una lista con las cuatro claves obligatorias llega a `encabezado['fecha_irradiacion']`, que lanza otro."""
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", encabezado, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == "el encabezado de la calibración es un diccionario"
        assert _conteos(bd) == (0, 0, 0)

    # ------------------------------------------------------------------------------------------------- a una pieza le falta una clave obligatoria
    @pytest.mark.parametrize("clave", ["orden", "dosis_nominal_cgy", "dosis_medida_cgy", "datos", "nombre_archivo"], ids=["orden", "dosis_nominal_cgy", "dosis_medida_cgy", "datos", "nombre_archivo"])
    def test_a_una_pieza_le_falta_una_clave_obligatoria_y_el_texto_dice_cual_y_de_que_pieza(self, bd, escaneos, clave):
        """`test_piezas_mal_formadas` prueba una clave de MAS (`otra`), un orden repetido y valores mal dados, pero ninguna pieza a la que le FALTE una clave: con el filtro de `faltan` en `False` o la condicion `sobran or
        faltan` reducida a `sobran` (el barrido) la pieza pasaba la comprobacion y reventaba mas abajo con un `KeyError` crudo. El texto dice que clave falta y de que pieza de la lista."""
        piezas = _piezas(escaneos, {1, 2, 3})
        del piezas[1][clave]
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", ENCABEZADO, piezas)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"la pieza 2 de la lista: le faltan [{clave!r}] o trae claves que no se conocen []"
        assert _conteos(bd) == (0, 0, 0)

    # ------------------------------------------------------------------------------------------------- el tipo de los datos de una pieza
    def test_un_escaneo_dado_como_bytearray_y_un_orden_de_numpy_se_guardan_como_bytes_y_entero(self, bd, escaneos):
        """El servicio acepta los bytes del escaneo como `bytes` o `bytearray` y el orden como cualquier entero (`numbers.Integral`: tambien el de numpy), y los vuelve `bytes` e `int` de Python. Ningun caso de arriba daba
        un `bytearray` (quitar la clase `bytearray` de la comprobacion rechazaba el escaneo) ni un orden de numpy (sin el `int(...)`, el INSERT no sabe enlazarlo): la huella es la de los bytes y la copia junto a la base es el archivo."""
        piezas = _piezas(escaneos, {1, 2})
        piezas[0]["datos"] = bytearray(piezas[0]["datos"])
        piezas[1]["orden"] = np.int64(2)
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert [p["orden"] for p in r["piezas"]] == [1, 2] and _sql(bd, f"SELECT typeof(orden) FROM {PIEZAS} ORDER BY orden") == [("integer",), ("integer",)]
        sha = hashlib.sha256(escaneos[1][2]).hexdigest()
        assert r["piezas"][0]["sha256"] == sha and r["piezas"][0]["bytes"] == len(escaneos[1][2])
        with open(os.path.join(_carpeta(bd), sha + ".tif"), "rb") as f:
            assert f.read() == escaneos[1][2]

    def test_el_servicio_guarda_una_copia_de_los_bytes_y_no_le_afecta_que_el_llamador_cambie_su_buffer(self, bd, escaneos, monkeypatch):
        """`bytes(p['datos'])` es una FOTO inmutable de lo que dio el llamador: lo que se mide y lo que se copia junto a la base son los mismos bytes aunque el llamador siga dueno de un `bytearray` y lo cambie a media llamada.
        Sin la conversion (el barrido) el servicio mediria el buffer, el llamador lo cambiaria, y la copia saldria con otra huella (`CurvaDosisError`). El cambio lo hace un envoltorio de la medicion, sin hilos."""
        piezas = _piezas(escaneos, {1, 2})
        buffer = bytearray(piezas[1]["datos"])
        piezas[1]["datos"] = buffer
        medir = _svc().medir_pieza_uniforme

        def medir_y_ensuciar(datos, *a, **k):
            resultado = medir(datos, *a, **k)
            buffer[0] = (buffer[0] + 1) % 256                                    # el llamador "sigue escribiendo" en su buffer
            return resultado

        with monkeypatch.context() as m:
            m.setattr(_svc(), "medir_pieza_uniforme", medir_y_ensuciar)
            r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        sha = hashlib.sha256(escaneos[2][2]).hexdigest()
        assert r["piezas"][1]["sha256"] == sha and bytes(buffer) != escaneos[2][2]
        with open(os.path.join(_carpeta(bd), sha + ".tif"), "rb") as f:
            assert f.read() == escaneos[2][2]

    # ------------------------------------------------------------------------------------------------- `_iguales` y `_comparar`: lo que `diferencias` da por igual y lo que dice cuando no
    @pytest.mark.parametrize("guardado, recalculado, iguales", [
        pytest.param(True, True, True, id="true-true"), pytest.param(False, False, True, id="false-false"), pytest.param(True, False, False, id="true-false"),
        pytest.param(True, 1, False, id="true-1"), pytest.param(1, True, False, id="1-true"), pytest.param(0, False, False, id="0-false"), pytest.param(False, 0.0, False, id="false-0.0"),
        pytest.param(1, 1.0, True, id="1-1.0"), pytest.param(1.0, 1.0 + 1e-12, True, id="1.0-1.0+1e-12"), pytest.param(1.0, 1.0001, False, id="1.0-1.0001"),
        pytest.param(0, 1e-13, True, id="0-1e-13"), pytest.param(0, 1e-11, False, id="0-1e-11"), pytest.param(0, 1e-10, False, id="0-1e-10"), pytest.param(1.0, 1.0 + 2e-9, False, id="1.0-1.0+2e-9"),
        pytest.param(1.0, 1.0 + 1e-7, False, id="1.0-1.0+1e-7"), pytest.param(1e6, 1e6 * (1.0 + 5e-10), True, id="1e6-medio_nanorelativo"), pytest.param(np.float64(1.0), 1.0, True, id="numpy-1.0"),
        pytest.param("a", "a", True, id="a-a"), pytest.param("a", "b", False, id="a-b"), pytest.param("1", 1, False, id="'1'-1"), pytest.param(None, None, True, id="None-None"),
        pytest.param(None, 0, False, id="None-0"), pytest.param([1], [1], True, id="[1]-[1]"), pytest.param([1], [2], False, id="[1]-[2]")])
    def test_iguales_dice_cuando_dos_valores_guardado_y_recalculado_son_el_mismo(self, guardado, recalculado, iguales):
        """`diferencias` da por igual lo numerico a `TOLERANCIA_RELATIVA_AL_RECALCULAR` (relativa y, cerca de cero, absoluta), un booleano solo contra el mismo booleano (`True` no es `1`) y lo demas por `==`. El barrido
        mostro que cada una de las condiciones de `_iguales` se podia torcer (`or` en `and`, un operando solo, `is` en `is not`, `==` en `!=`) sin que un caso de arriba lo notara: aqui, la tabla de pares con su respuesta."""
        assert _svc()._iguales(guardado, recalculado) is iguales
        assert _svc()._iguales(recalculado, guardado) is iguales                           # y es simetrica

    @pytest.mark.parametrize("guardado, recalculado, esperado", [
        pytest.param({"a": 1}, {"a": 1}, [], id="iguales"),
        pytest.param({"b": 1, "a": 2}, {"b": 1, "a": 3}, ["r › a: guardado 2, recalculado 3"], id="un_valor_distinto"),
        pytest.param({"a": 1, "c": 3}, {"a": 1, "b": 2}, ["r › b: falta en lo guardado", "r › c: falta en lo recalculado"], id="faltan_claves_de_cada_lado_y_en_orden"),
        pytest.param({"a": 1}, {}, ["r › a: falta en lo recalculado"], id="falta_en_lo_recalculado"),
        pytest.param({}, {"a": 1}, ["r › a: falta en lo guardado"], id="falta_en_lo_guardado"),
        pytest.param({"a": {"b": [1, {"c": "x"}]}}, {"a": {"b": [1, {"c": "y"}]}}, ["r › a › b › 2 › c: guardado 'x', recalculado 'y'"], id="anidado_con_la_posicion_de_la_lista_desde_1"),
        pytest.param([1, 2], [1, 2, 3], ["r: guardado 2 elementos, recalculado 3"], id="listas_de_otro_largo"),
        pytest.param([1, 2, 3], [1, 5], ["r: guardado 3 elementos, recalculado 2", "r › 2: guardado 2, recalculado 5"], id="otro_largo_y_ademas_un_elemento_distinto"),
        pytest.param({"a": 1}, [1], ["r: guardado {'a': 1}, recalculado [1]"], id="dict-lista"), pytest.param([1], {"a": 1}, ["r: guardado [1], recalculado {'a': 1}"], id="lista-dict"),
        pytest.param({"a": 1}, 5, ["r: guardado {'a': 1}, recalculado 5"], id="dict-entero"), pytest.param(5, {"a": 1}, ["r: guardado 5, recalculado {'a': 1}"], id="entero-dict"),
        pytest.param([1], 5, ["r: guardado [1], recalculado 5"], id="lista-entero"), pytest.param(5, [1], ["r: guardado 5, recalculado [1]"], id="entero-lista"),
        pytest.param({"a": 1}, None, ["r: guardado {'a': 1}, recalculado None"], id="dict-nada"), pytest.param(None, [1], ["r: guardado None, recalculado [1]"], id="nada-lista"),
        pytest.param(True, 1, ["r: guardado True, recalculado 1"], id="bool-entero"),
        pytest.param({f"k{i}": 1 for i in (1, 3, 5, 7)}, {f"k{i}": 1 for i in (2, 4, 6, 8)},
                     [f"r › k{i}: falta en lo {'recalculado' if i % 2 else 'guardado'}" for i in range(1, 9)], id="ocho_claves_repartidas_salen_en_orden_alfabetico"),
        pytest.param(ENORME, "x", ["r: guardado un int con un entero de más de 4300 cifras, recalculado 'x'"], id="entero_enorme-texto"),
        pytest.param("x", ENORME, ["r: guardado 'x', recalculado un int con un entero de más de 4300 cifras"], id="texto-entero_enorme")])
    def test_comparar_dice_cada_diferencia_con_su_camino(self, guardado, recalculado, esperado):
        """El texto exacto de cada diferencia (el camino con `›`, las posiciones de una lista contadas desde 1, las claves ordenadas, el lado que falta y el largo distinto) y que un diccionario contra un no-diccionario (o una
        lista contra un no-lista) se compare como un valor y no como una estructura, y un entero de mas de 4300 cifras contra un no-numero se dice con el texto de `_como_texto` (las dos llamadas de `_comparar` que la
        medicion de la ronda 2 dejo sin prueba: se alcanzan aqui, con la estructura armada a mano). Lo que en `diferencias` cubren los casos de arriba solo con la curva real; aqui, estructura por estructura."""
        encontradas = []
        _svc()._comparar(guardado, recalculado, "r", encontradas)
        assert encontradas == esperado

    def test_la_medida_de_una_pieza_que_no_trae_su_medicion_dice_medicion_nada(self, bd, escaneos):
        """`_medida_de_la_pieza` arma el JSON `medida` de una pieza: lo que entro a la curva y, aparte, la medicion entera de CD.2 (`None` si la pieza no trae medicion, como la que `recalcular` arma desde lo guardado,
        sin escaneo). Ninguna ruta publica la llama con una pieza sin medicion, asi que el `None` de esa rama (el barrido: la condicion `pieza.medida is None` en `False`, que revienta con un `TypeError` al pedirle
        `asdict(None)`) no lo probaba nadie. La parte `pieza` es la guardada, campo por campo, salvo lo que vuelve a poner `ajustar`."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2})))
        fila = r["piezas"][1]
        sin_medicion = _svc()._pieza_desde_la_fila(fila)
        assert sin_medicion.medida is None
        medida = _svc()._medida_de_la_pieza(sin_medicion)
        assert medida["medicion"] is None
        guardada = fila["medida"]["pieza"]
        assert (medida["pieza"]["posicion_mm"], medida["pieza"]["fondo_blanco"], medida["pieza"]["cadena"]) == (guardada["posicion_mm"], guardada["fondo_blanco"], guardada["cadena"])
        assert set(medida["pieza"]["capas"]) == set(guardada["capas"])

    def test_si_el_nombre_de_la_copia_ya_existe_y_no_es_un_archivo_se_dice_que_no_se_pudo_copiar(self, bd, escaneos):
        """Una copia que YA ESTABA se mide antes de copiar (D3) solo si es un archivo: si el nombre de la copia existe y es una CARPETA, la lectura previa no tiene sentido y el rechazo es el de la copia (`no se pudo copiar
        el escaneo ...`), no el de «la copia que ya estaba» (el barrido: `ya_estaba and isfile` -> `ya_estaba`, o con `or`). Lo que dice el sistema para abrir una carpeta cambia de un sistema a otro: se compara el prefijo."""
        sha = hashlib.sha256(escaneos[1][2]).hexdigest()
        os.makedirs(os.path.join(_carpeta(bd), sha + ".tif"))
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value).startswith("no se pudo copiar el escaneo '0.tif' junto a la base: ") and "que ya estaba" not in str(e.value)
        assert _conteos(bd) == (0, 0, 0)

    def test_si_la_copia_se_rechaza_con_un_valueerror_de_cd2_es_curva_dosis_error_y_no_se_escribe_nada(self, bd, escaneos, monkeypatch):
        """`_copiar_el_escaneo` (CD.2) rechaza con un `ValueError` («ya hay un archivo ... con otro contenido: no se sobrescribe») el nombre que cambio de contenido DESPUES de la lectura previa del servicio (una carrera:
        D3 la mide antes y rechaza con su propio texto). Esa rama no la alcanza ningun caso sin simular la carrera, y el `except` solo con `OSError` (el barrido: el `except` pierde `ValueError`) dejaba escapar el
        `ValueError` crudo. Se simula con un envoltorio de la copia, dentro de un `monkeypatch.context()`."""
        def copiar(*a, **k):
            raise ValueError("En la carpeta ya hay un archivo con otro contenido: no se sobrescribe.")

        with monkeypatch.context() as m:
            m.setattr(_svc(), "_copiar_el_escaneo", copiar)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == "no se pudo copiar el escaneo '0.tif' junto a la base: En la carpeta ya hay un archivo con otro contenido: no se sobrescribe."
        assert _conteos(bd) == (0, 0, 0)

    # ------------------------------------------------------------------------------------------------- `recalcular` de un registro roto
    @pytest.mark.parametrize("caso", ["sin_piezas", "piezas_en_nada", "pieza_sin_su_medida"], ids=["sin_piezas", "piezas_en_nada", "pieza_sin_su_medida"])
    def test_recalcular_de_un_registro_incompleto_o_mal_formado_es_curva_dosis_error(self, bd, escaneos, caso):
        """`recalcular` promete `CurvaDosisError` «si lo guardado ya no se puede leer»: un registro al que le falta una clave (`KeyError`) o con un valor de otro tipo (`TypeError`) tambien. El unico caso de arriba daba
        un `ValueError` (un parametro guardado que ya no es valido); el barrido: el `except` pierde `KeyError` o `TypeError` y el error crudo escapa. Los textos de Python cambian entre versiones: se compara el prefijo."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2})))
        if caso == "sin_piezas":
            del r["piezas"]
        elif caso == "piezas_en_nada":
            r["piezas"] = None
        else:
            del r["piezas"][0]["medida"]
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().recalcular(r)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value).startswith("lo guardado de la calibración no se puede volver a ajustar: ")

    # ------------------------------------------------------------------------------------------------- guardar sin usuario
    @pytest.mark.parametrize("usuario", [None, "", "   ", "\t\n"], ids=["nada", "vacio", "espacios", "tabulador_y_salto"])
    def test_guardar_sin_usuario_se_rechaza_antes_de_medir_ni_copiar_nada(self, bd, escaneos, usuario):
        """`test_sin_usuario_o_con_una_virgen_...` pide solo `' '` en `guardar` (y `None` en `anular`): con `None` el texto `str(None)` es «None», no esta vacio, y la condicion `usuario is None or not str(usuario).strip()`
        reducida a su segundo operando (el barrido) dejaba guardar una calibracion a nombre del usuario «None»."""
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar(usuario, ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError and str(e.value) == "falta el usuario que guarda la calibración"
        assert _conteos(bd) == (0, 0, 0) and not os.path.exists(_carpeta(bd))

    # ------------------------------------------------------------------------------------------------- `_a_dict` y `vigentes_validas`: lo defensivo
    def test_a_dict_convierte_solo_las_columnas_json_pedidas_que_estan_en_la_consulta_y_deja_el_nada(self):
        """`_a_dict` vuelve diccionario una fila y decodifica las columnas JSON que se le piden: una columna NULL se queda en `None` y una columna pedida que la consulta no trae se ignora (el barrido: la condicion `c in
        registro and registro[c] is not None` reducida a su segundo operando lanzaria un `KeyError`). Con una base en memoria: sin servicio ni escaneos."""
        con = sqlite3.connect(":memory:")
        try:
            cursor = con.execute("""SELECT 1 AS n, '{"a": [1, 2]}' AS j, NULL AS v, '[3]' AS no_pedida""")
            registro = _svc()._a_dict(cursor, cursor.fetchone(), ("j", "v", "ausente"))
        finally:
            con.close()
        assert registro == {"n": 1, "j": {"a": [1, 2]}, "v": None, "no_pedida": "[3]"}

    def test_vigentes_validas_salta_la_calibracion_que_desaparece_entre_listar_y_leer(self, bd, escaneos, monkeypatch):
        """`vigentes_validas` lista y despues lee cada una: si una ya no se puede leer (`leer` da `None`: la borraron entre las dos lecturas) no entra en el resultado en lugar de entrar como `None` (el barrido: el filtro
        `r is not None` de la comprension en `True`). La carrera se simula con un envoltorio de `leer`, dentro de un `monkeypatch.context()`."""
        a = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "2026-09-01"}, _piezas(escaneos))
        b = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos))
        leer = _svc().leer
        with monkeypatch.context() as m:
            m.setattr(_svc(), "leer", lambda i: None if i == a else leer(i))
            validas = _svc().vigentes_validas()
        assert [r["id"] for r in validas] == [b]

    # ------------------------------------------------------------------------------------------------- `Recalculo`
    def test_un_recalculo_es_inmutable_y_dos_recalculos_distintos_no_son_iguales(self, bd, escaneos):
        """`Recalculo` es un resultado: congelado (`frozen=True`) y comparado por identidad (`eq=False`: lleva curvas con arreglos de numpy, que no se comparan con `==`). El barrido: `frozen=False` dejaba cambiarlo y
        `eq=True` lo comparaba campo por campo."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2})))
        rec = _svc().recalcular(r)
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.escaneos_que_faltan = ("otro",)
        a, b = _svc().Recalculo(rec.desde_lo_medido, None, (), ()), _svc().Recalculo(rec.desde_lo_medido, None, (), ())
        assert a == a and (a == b) is False and a != b                         # los mismos campos, y aun asi no son iguales: se comparan por identidad

    # ------------------------------------------------------------------------------------------------- las tolerancias y los textos en orden
    def test_con_varios_parametros_mal_dados_el_texto_nombra_el_primero_por_orden_alfabetico(self, bd, escaneos):
        """`_parametros_de_la_curva` valida los parametros en orden alfabetico (`sorted(parametros)`): con varios mal dados el rechazo nombra siempre el MISMO, el primero del alfabeto, y no el que el llamador puso primero.
        El barrido: quitar el `sorted` dejaba el orden en el que llegan."""
        malos = {"residuo_maximo_pct": "3", "piezas_minimas": "6", "dosis_baja_cgy": "100"}
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": malos}, _piezas(escaneos, {1, 2}))
        assert str(e.value) == "el parámetro de la curva 'dosis_baja_cgy' debe ser un número finito de 0 o más, no '100'"

    def test_las_claves_de_mas_del_encabezado_y_de_una_pieza_se_nombran_todas_y_ordenadas(self, bd, escaneos):
        """Los casos de arriba piden solo `match='no conoce'` o `'no se conocen'`: el texto exacto (la lista, ordenada, con TODAS las claves de mas) no lo fijaba nadie, asi que quitar el `sorted` de `sobran` en el
        encabezado o en una pieza (el barrido) cambiaba la lista por un conjunto sin que cayera ninguna prueba."""
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "zeta": 1, "alfa": 2, "medio": 3}, _piezas(escaneos, {1, 2}))
        assert str(e.value) == "el encabezado trae claves que la calibración no conoce: ['alfa', 'medio', 'zeta']"
        piezas = _piezas(escaneos, {1, 2, 3})
        piezas[1] = {**piezas[1], "zeta": 1, "alfa": 2, "medio": 3}
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", ENCABEZADO, piezas)
        assert str(e.value) == "la pieza 2 de la lista: le faltan [] o trae claves que no se conocen ['alfa', 'medio', 'zeta']"
        assert _conteos(bd) == (0, 0, 0)

    # ------------------------------------------------------------------------------------------------- el nombre del archivo y el usuario
    def test_el_nombre_del_archivo_se_guarda_sin_la_carpeta_y_sin_los_espacios_de_los_lados(self, bd, escaneos):
        """`_nombre_de_archivo` deja solo el nombre (con `/` o con `\\`) y sin espacios de los lados: «  C:\\escaneos\\ 0.tif  » se guarda «0.tif». Los casos de arriba daban nombres sin espacios (el barrido: quitar el
        `.strip()` final dejaba el nombre con un espacio delante y detras en la base y en la procedencia)."""
        piezas = _piezas(escaneos, {1, 2})
        piezas[0]["nombre_archivo"] = "  C:\\escaneos\\ 0.tif  "
        piezas[1]["nombre_archivo"] = " /mnt/x/y/ 50.tif "
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert [p["nombre_archivo"] for p in r["piezas"]] == ["0.tif", "50.tif"]

    # `test_un_usuario_que_no_es_un_texto_se_guarda_como_su_texto` (la lenidad de la ronda 1: un entero como usuario se guardaba, y se auditaba, como su texto) QUEDA REEMPLAZADA, en la ronda 3c, por el contrato
    # ESTRICTO de CD4-R3-D1: un usuario que no es un texto se rechaza con `CurvaDosisError` antes de medir y de copiar nada (`TestR3cD1ElUsuario`, seccion 18). Los barridos R2-BA-040, R2-BA-042 y R2-BA-043, que la
    # guardaban con `str(usuario)`, se reubicaron en `cd4_mutaciones.py` a la validacion nueva (`_usuario`).

    # ------------------------------------------------------------------------------------------------- las copias defensivas y el orden de las piezas
    def test_ni_guardar_ni_recalcular_dejan_que_la_medicion_cambie_los_parametros_de_medida_que_no_son_suyos(self, bd, escaneos, monkeypatch):
        """El servicio le da a CD.2 una COPIA de los parametros de medida (la constante `VALORES_DE_LA_GEOMETRIA` en `guardar`, los guardados del registro en `recalcular`): si la medicion cambiara el diccionario que recibe
        (hoy no lo hace; una version futura podria) la constante y el registro quedarian alterados para todo el que venga despues. El barrido: sin `copy.deepcopy` en cualquiera de los dos sitios. Se simula con un
        envoltorio de la medicion que agrega una clave al diccionario que recibe, dentro de un `monkeypatch.context()`."""
        from analisisImagenes.placa_mensual import VALORES_DE_LA_GEOMETRIA
        medir = _svc().medir_pieza_uniforme

        def medir_y_ensuciar(datos, parametros, *a, **k):
            parametros["intruso"] = True
            return medir(datos, parametros, *a, **k)

        antes = copy.deepcopy(VALORES_DE_LA_GEOMETRIA)
        with monkeypatch.context() as m:
            m.setattr(_svc(), "medir_pieza_uniforme", medir_y_ensuciar)
            r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2})))
            assert VALORES_DE_LA_GEOMETRIA == antes and "intruso" not in VALORES_DE_LA_GEOMETRIA
            r["parametros"]["medida"] = copy.deepcopy(antes)
            _svc().recalcular(r)
            assert "intruso" not in r["parametros"]["medida"] and r["parametros"]["medida"] == antes

    def test_recalcular_y_diferencias_ordenan_las_piezas_por_su_orden_aunque_el_registro_las_traiga_al_reves(self, bd, escaneos):
        """`leer` da las piezas en el orden del formulario, pero `recalcular` y `diferencias` reciben un diccionario cualquiera: ordenan por `orden` ellos mismos (los nombres de `escaneos_que_faltan` y las lineas de la
        copia que no coincide salen en ese orden). El barrido: quitar el `sorted` de cualquiera de los dos los dejaba en el orden en que llegan."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        al_reves = {**r, "piezas": list(reversed(r["piezas"]))}
        copia = {o: os.path.join(_carpeta(bd), hashlib.sha256(escaneos[o][2]).hexdigest() + ".tif") for o in (1, 2, 3, 4)}
        os.remove(copia[1])
        os.remove(copia[3])
        with open(copia[2], "ab") as f:
            f.write(b"x")
        with open(copia[4], "ab") as f:
            f.write(b"x")
        rec = _svc().recalcular(al_reves)
        assert rec.escaneos_que_faltan == tuple(os.path.basename(copia[o]) for o in (1, 3)) and rec.escaneos_que_no_coinciden == tuple(os.path.basename(copia[o]) for o in (2, 4))
        lineas = [d for d in _svc().diferencias(al_reves, rec) if d.startswith("la pieza ")]
        assert [d.split()[2] for d in lineas] == ["2", "4"]

    def test_diferencias_dice_la_pieza_guardada_que_no_esta_en_lo_recalculado_y_sigue_con_las_demas(self, bd, escaneos):
        """Una pieza que esta guardada y no aparece en lo recalculado desde los escaneos (otro numero de piezas) es UNA diferencia con su texto, y `diferencias` sigue con las demas piezas (el barrido: la condicion
        `p is None` torcida o el `continue` omitido lanzaban un `AttributeError` al pedirle la medida a `None`). Un registro con una pieza de mas, copia de la primera con otro orden, y lo recalculado de los mismos escaneos."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        rec = _svc().recalcular(r)
        assert rec.desde_los_escaneos is not None and _svc().diferencias(r, rec) == []
        con_una_de_mas = {**r, "piezas": r["piezas"] + [{**r["piezas"][0], "orden": 99}]}
        assert _svc().diferencias(con_una_de_mas, rec) == ["la pieza 99: no está en lo recalculado"]

    def test_un_real_de_numpy_de_32_bits_se_guarda_como_real_de_python(self, bd, escaneos):
        """`float(valor) + 0.0`: el `float(...)` vuelve un real de Python cualquier escalar de numpy. Sin el (el barrido), `np.float32(3.5) + 0.0` sigue siendo un `float32` (los escalares de Python no ensanchan el
        tipo de numpy 2) y la puerta estricta de los JSON lo rechaza por no ser JSON. `np.float64` si pasa (es un `float`): el caso de arriba no lo distinguia."""
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"residuo_maximo_pct": np.float32(3.5)}}, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        assert r["parametros"]["curva"]["residuo_maximo_pct"] == 3.5 and type(r["parametros"]["curva"]["residuo_maximo_pct"]) is float

    def test_recalcular_vuelve_real_la_dosis_nominal_de_cada_pieza_aunque_el_registro_la_traiga_entera(self, bd, escaneos):
        """`_pieza_desde_la_fila` hace `float(fila['dosis_nominal_cgy'])`: la `PiezaDeCalibracion` lleva la dosis nominal como real aunque el registro (armado a mano o por otro lector) la traiga como entero. Sin ese `float`
        (el barrido) la dosis llegaba entera a CD.3 y se quedaba entera en la curva rehecha; `diferencias` no lo ve porque da por igual `50` y `50.0`, asi que se mira el tipo de la pieza."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        r["piezas"][1]["dosis_nominal_cgy"] = 50
        piezas = _svc().recalcular(r).desde_lo_medido.piezas
        assert [(p.orden, p.dosis_nominal_cgy, type(p.dosis_nominal_cgy)) for p in piezas if p.orden == 2] == [(2, 50.0, float)]


# ===================================================================================================== (18) la ronda 3 de la revision, parte 1 (CD4-R3-D1 a D8, 30-10)
# Los tres revisores de la ronda 3 (produccion, pruebas y un fuzz de la frontera de 3021 casos; borradores/CD4/hallazgos_ronda3_revisores.json) revisaron lo que dejo la ronda 2 y el supervisor acoto la ronda a lo REALISTA: lo que un
# llamador cooperante (la ventana CD.5, el motor CD.6, los PDF) puede mandar por un descuido y el unico hallazgo que toca la trazabilidad (el usuario crudo que la auditoria se tragaba). Las ocho decisiones CD4-R3-D1 a D8 se aplican
# SOLO en `services/curva_dosis.py`, en este orden (D6, D7, D5, D1, D2, D3, D4 y D8), y cada una tiene aqui su clase `TestR3cD<n>...`; sus mutaciones son las `R3C-D<n>-M<m>` de `cd4_mutaciones.py`. Cada caso cae contra el servicio de
# antes de la ronda (logs/CD4/ronda3c/rojo_antes.log) por la razon que dice su nombre, salvo las BARRERAS, que pasan antes y despues y fijan lo que NO cambia. Solo se AGREGA, salvo `test_un_usuario_que_no_es_un_texto_se_guarda_como_
# su_texto` (seccion 17): fijaba la lenidad de la ronda 1 con un entero y D1 la reemplaza por el contrato estricto. Toda parametrizacion con valores enormes o raros lleva `ids` explicitos.

SURROGADO = "a\ud800b"                    # un surrogado suelto: no se puede escribir en UTF-8 (un nombre de archivo de Linux con bytes invalidos lo produce)
SIN_ESCRIBIR = " tiene un carácter que no se puede escribir en la base"          # CD4-R4-D1 (CD4-R4-PROD-03): con su acento, como el resto de los textos nuevos y de las docstrings
NO_ES_UN_DICCIONARIO = "las condiciones de irradiación son un diccionario (profundidad, DFS y campo)"
SOLO_CLAVES_DE_TEXTO = "las condiciones de irradiación solo admiten claves de texto, no "
EL_ID_NO_CABE = "el id de la calibración no cabe en la base (un entero de -9223372036854775808 a 9223372036854775807), no "
EL_ID_NO_ES_UN_ENTERO = "el id de la calibración debe ser un entero, no "
UN_ENTERO_ENORME = "un int con un entero de más de 4300 cifras"
UN_OBJETO_QUE_NO_SE_ESCRIBE = "un UnObjetoQueNoSeEscribe que no se puede escribir"


class UnObjetoQueNoSeEscribe:
    """Su `repr` (y su `str`) lanzan el error que se le diga, por omision un `RuntimeError`: no el `ValueError` del limite de cifras de Python, que es el unico que `_como_texto` atrapaba (CD4-R3-D6)."""

    def __init__(self, error=RuntimeError):
        self.error = error

    def __repr__(self):
        raise self.error("repr lanza")

    __str__ = __repr__


class UnEnteroQueNoSeEscribe(int):
    """Un entero (pasa por `numbers.Integral`) cuyo `repr` lanza: el caso de una subclase de `int` con un `__repr__` roto."""

    def __repr__(self):
        raise RuntimeError("repr lanza")

    __str__ = __repr__


QUE_NO_SE_ESCRIBE = UnObjetoQueNoSeEscribe()


def _el_guardado_se_rechaza(bd, escaneos, texto, usuario="fisico", cambio=None, piezas=None):
    """`guardar` con `cambio` sobre el encabezado de siempre (y, si se dan, otras piezas; por omision las dos primeras): se rechaza con `CurvaDosisError` EXACTO (el tipo y el texto) y no queda nada escrito: ni filas, ni auditoria,
    ni una copia de un escaneo."""
    with pytest.raises(_svc().CurvaDosisError) as e:
        _svc().guardar(usuario, {**ENCABEZADO, **(cambio or {})}, _piezas(escaneos, {1, 2}) if piezas is None else piezas)
    assert type(e.value) is _svc().CurvaDosisError
    assert str(e.value) == texto
    assert _conteos(bd) == (0, 0, 0)
    assert not os.path.exists(_carpeta(bd))                           # ni una copia de un escaneo


def _poner_en_el_guardado(cabeza, piezas, donde, valor):
    """Pone `valor` donde dice `donde`: una clave del encabezado, `camara.equipo_id` (o cualquier `<equipo>.<campo>`), `parametros.<nombre>` (los parametros de la curva) o `pieza<n>.<campo>` (la pieza n-esima de la lista)."""
    if donde.startswith("pieza"):
        n, campo = donde[len("pieza"):].split(".")
        piezas[int(n) - 1][campo] = valor
    elif donde.startswith("parametros."):
        cabeza["parametros_de_la_curva"] = {donde.split(".", 1)[1]: valor}
    elif "." in donde:
        sitio, campo = donde.split(".")
        cabeza[sitio] = {**cabeza[sitio], campo: valor}
    else:
        cabeza[donde] = valor


class _SeAgotoElTiempo(Exception):
    """La alarma de `_con_tope` saltó antes de que la llamada terminara."""


def _con_tope(segundos, llamada):
    """Corre `llamada` en el hilo principal con una ALARMA de `segundos` (`SIGALRM`, que interrumpe un bucle de Python que no termina): (si termino, {'valor': ...} o {'error': ...}). Una prueba que puede colgarse (un
    recorrido que no recuerda lo que ya vio) no cuelga la corrida: falla, y no deja ningun hilo girando (un hilo suelto con un bucle vuelve lentisimo el resto del proceso: cada operacion de entrada y salida espera
    el relevo del GIL). `SIGALRM` solo existe fuera de Windows; alli la prueba se salta."""
    if not hasattr(signal, "SIGALRM"):
        pytest.skip("este sistema no tiene SIGALRM")
    salida = {}

    def alarma(*_):
        raise _SeAgotoElTiempo()

    anterior = signal.signal(signal.SIGALRM, alarma)
    signal.setitimer(signal.ITIMER_REAL, segundos)
    try:
        try:
            salida["valor"] = llamada()
        except _SeAgotoElTiempo:
            return False, salida
        except Exception as error:                                       # noqa: BLE001 -- lo que lance se informa, no se pierde
            salida["error"] = error
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, anterior)
    return True, salida


# ------------------------------------------------------------------------------------------------------------------------------------- D6: `_como_texto`

LOS_SITIOS_DE_UN_REPR_QUE_LANZA = [
    pytest.param("acelerador", "el acelerador debe ser un texto o nada, no ", id="acelerador"),
    pytest.param("u_dosis_medida_pct", "la incertidumbre de la dosis medida debe ser un número finito de 0 o más o nada, no ", id="u_dosis_medida_pct"),
    pytest.param("fecha_irradiacion", "la fecha de irradiación debe ser 'aaaa-mm-dd', no ", id="fecha_irradiacion"),
    pytest.param("modo_de_escaneo", "el modo de escaneo es transmisión o reflexión, o nada, no ", id="modo_de_escaneo"),
    pytest.param("camara.equipo_id", "el equipo_id de la cámara es un entero o nada, no ", id="camara.equipo_id"),
    pytest.param("parametros.residuo_maximo_pct", "el parámetro de la curva 'residuo_maximo_pct' debe ser un número finito de 0 o más, no ", id="parametro_de_la_curva"),
    pytest.param("pieza2.orden", "el orden de la pieza 2 de la lista debe ser un entero que no se repite, no ", id="orden_de_la_pieza"),
    pytest.param("pieza2.fecha_escaneo", "la fecha de escaneo de la pieza 2 debe ser 'aaaa-mm-dd' o nada, no ", id="fecha_de_escaneo")]


class TestR3cD6ComoTexto:
    """CD4-R3-D6 (CD4-R3-FRO-05): `_como_texto` solo atrapaba el `ValueError` del limite de cifras; un valor cuyo `repr` lanza OTRA excepcion la hacia escapar cruda desde casi todos los mensajes de rechazo. Ahora cualquier
    `Exception` se dice como «un <tipo> que no se puede escribir»; el texto del entero enorme no cambia."""

    @pytest.mark.parametrize("donde, prefijo", LOS_SITIOS_DE_UN_REPR_QUE_LANZA)
    def test_un_valor_cuyo_repr_lanza_se_rechaza_con_su_texto_y_sin_escribir_nada(self, bd, escaneos, donde, prefijo):
        cabeza, piezas = dict(ENCABEZADO), _piezas(escaneos, {1, 2})
        _poner_en_el_guardado(cabeza, piezas, donde, QUE_NO_SE_ESCRIBE)
        _el_guardado_se_rechaza(bd, escaneos, prefijo + UN_OBJETO_QUE_NO_SE_ESCRIBE, cambio=cabeza, piezas=piezas)

    @pytest.mark.parametrize("error", [RuntimeError, TypeError, KeyError, AttributeError], ids=["RuntimeError", "TypeError", "KeyError", "AttributeError"])
    def test_como_texto_atrapa_cualquier_error_del_repr_y_dice_el_tipo(self, error):
        assert _svc()._como_texto(UnObjetoQueNoSeEscribe(error)) == UN_OBJETO_QUE_NO_SE_ESCRIBE

    def test_como_texto_dice_el_tipo_de_una_subclase_de_int_cuyo_repr_lanza(self):
        assert _svc()._como_texto(UnEnteroQueNoSeEscribe(5)) == "un UnEnteroQueNoSeEscribe que no se puede escribir"

    def test_como_texto_no_cambia_lo_que_ya_decia(self):
        """BARRERA (pasa antes y despues): lo que se puede escribir sale como su `repr` y el entero de mas de 4300 cifras conserva el texto de la ronda 1."""
        como = _svc()._como_texto
        assert [como("x"), como(3), como(None), como([1, "a"]), como(1.5)] == ["'x'", "3", "None", "[1, 'a']", "1.5"]
        assert como(ENORME) == UN_ENTERO_ENORME and como([ENORME]) == "un list con un entero de más de 4300 cifras"


# ------------------------------------------------------------------------------------------------------------------------------------- D7: lo que no se puede escribir en UTF-8

LOS_TEXTOS_DEL_ENCABEZADO = [pytest.param(campo, que, id=campo) for campo, que in (
    ("lote", "el lote de la película"), ("tipo_pelicula", "el tipo de película"), ("energia", "la energía"), ("acelerador", "el acelerador"), ("escaner_declarado", "el escáner declarado"),
    ("observaciones", "las observaciones"), ("camara.modelo", "el modelo de la cámara"), ("camara.serie", "la serie de la cámara"), ("electrometro.modelo", "el modelo de el electrómetro"),
    ("electrometro.serie", "la serie de el electrómetro"))]          # el «de el» es el `que` de hoy
LAS_CONDICIONES_CON_UN_SURROGADO = [pytest.param({"profundidad_cm": 3.0, SURROGADO: 1}, id="clave"), pytest.param({"profundidad_cm": SURROGADO}, id="valor"),
                                    pytest.param({"a": [{"b": (1, SURROGADO)}]}, id="valor_anidado")]


class TestR3cD7LosSurrogados:
    """CD4-R3-D7 (CD4-R3-FRO-03): un surrogado suelto (un nombre de archivo de Linux con bytes invalidos) pasaba la validacion, la medicion y la COPIA de los escaneos y reventaba despues en el INSERT con un `UnicodeEncodeError`
    (cero filas, solo copias). Ahora se rechaza en la frontera, antes de copiar nada: `_texto`, `_nombre_de_archivo` y el `_json` del servicio (la puerta comun no se edita)."""

    @pytest.mark.parametrize("campo, que", LOS_TEXTOS_DEL_ENCABEZADO)
    def test_un_texto_del_encabezado_con_un_surrogado_se_rechaza_antes_de_copiar(self, bd, escaneos, campo, que):
        cabeza = dict(ENCABEZADO)
        _poner_en_el_guardado(cabeza, [], campo, SURROGADO)
        _el_guardado_se_rechaza(bd, escaneos, que + SIN_ESCRIBIR, cambio=cabeza)

    def test_un_nombre_de_archivo_con_un_surrogado_se_rechaza_nombrando_la_pieza(self, bd, escaneos):
        piezas = _piezas(escaneos, {1, 2})
        piezas[1]["nombre_archivo"] = f"C:\\escaneos\\{SURROGADO}.tif"
        _el_guardado_se_rechaza(bd, escaneos, "el nombre del archivo de la pieza 2" + SIN_ESCRIBIR, piezas=piezas)

    def test_un_surrogado_en_la_carpeta_del_nombre_no_importa_porque_no_se_guarda(self, bd, escaneos):
        """BARRERA (pasa antes y despues): solo se mira lo que se guarda, el nombre sin la carpeta del equipo de quien lo subio."""
        piezas = _piezas(escaneos, {1, 2})
        piezas[0]["nombre_archivo"] = f"C:\\{SURROGADO}\\0.tif"
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert [p["nombre_archivo"] for p in r["piezas"]] == ["0.tif", "50.tif"]

    @pytest.mark.parametrize("condiciones", LAS_CONDICIONES_CON_UN_SURROGADO)
    def test_las_condiciones_con_un_surrogado_se_rechazan_antes_de_copiar(self, bd, escaneos, condiciones):
        _el_guardado_se_rechaza(bd, escaneos, "lo que se guarda en la columna 'condiciones'" + SIN_ESCRIBIR, cambio={"condiciones": condiciones})

    def test_el_orden_de_la_pieza_solo_se_escribe_si_hay_que_nombrarla_en_un_rechazo(self, bd, escaneos):
        """El fuzz de la frontera, repetido tras la primera version de D7, mostro una regresion: el texto «el nombre del archivo de la pieza {orden}» se armaba SIEMPRE, y un `orden` cuyo `__str__` lanza (una subclase de `int` rota:
        fuera de contrato, pero antes se aceptaba porque el orden solo se usa como entero) reventaba con su `RuntimeError` al validar la pieza. Lo que se acepta no se escribe: el texto que nombra la pieza se arma solo si hay que rechazar."""
        piezas = _piezas(escaneos, {1, 2})
        piezas[0]["orden"] = UnEnteroQueNoSeEscribe(1)
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, piezas))
        assert [p["orden"] for p in r["piezas"]] == [1, 2]

    def test_se_puede_escribir_dice_si_un_texto_cabe_en_utf_8(self):
        escribe = _svc()._se_puede_escribir
        assert [escribe(t) for t in ("", "abc", "ñ€𝄞", "película «virgen»", "\ud7ff", "\ue000")] == [True] * 6
        assert [escribe(t) for t in (SURROGADO, "\ud800", "\udfff", "x\udc80")] == [False] * 4

    def test_el_texto_que_si_se_puede_escribir_se_guarda_tal_cual_con_sus_acentos_y_sus_simbolos(self, bd, escaneos):
        """BARRERA (pasa antes y despues): el texto con acentos, la eñe, el euro y un simbolo fuera del plano basico es UTF-8 valido y se guarda intacto (el encabezado, el nombre del archivo y las condiciones)."""
        cabeza = {"lote": "Ñandú-€𝄞", "observaciones": "película «virgen» — 5 µm", "condiciones": {"nota": "ñ€𝄞", "campo ñ": [1, "ü"]}}
        piezas = _piezas(escaneos, {1, 2})
        piezas[0]["nombre_archivo"] = "C:\\escáneos\\película ñ.tif"
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, **cabeza}, piezas))
        assert (r["lote"], r["observaciones"], r["condiciones"]) == (cabeza["lote"], cabeza["observaciones"], cabeza["condiciones"])
        assert [p["nombre_archivo"] for p in r["piezas"]] == ["película ñ.tif", "50.tif"]


# ------------------------------------------------------------------------------------------------------------------------------------- D5: las fechas

LAS_FECHAS_QUE_SE_ESCRIBEN_ASI = [pytest.param(entrada, salida, id=entrada.strip()) for entrada, salida in (
    ("0001-01-01", "0001-01-01"), ("0999-12-31", "0999-12-31"), ("0400-02-29", "0400-02-29"), ("1000-01-01", "1000-01-01"), ("2026-03-05", "2026-03-05"), (" 2026-10-20 ", "2026-10-20"), ("9999-12-31", "9999-12-31"))]
LAS_FECHAS_IMPOSIBLES = [pytest.param(entrada, id=entrada or "vacia") for entrada in ("0000-01-01", "0100-02-29", "2026-02-30", "2026-13-01", "2026-00-10", "26-10-2026", "2026/10/20", "")]


class TestR3cD5LasFechas:
    """CD4-R3-D5 (CD4-R3-PROD-02): `fecha_iso` aceptaba los años 0001 a 0999 y `strftime('%Y')` los escribe SIN el cero de la izquierda en Linux ('999-12-31'): `DATE()` de SQLite da NULL, la clave de bloque deja de funcionar y
    quedaban DOS calibraciones vigentes del mismo bloque. Ahora se escribe a mano, con el año de cuatro cifras (el año no se rechaza)."""

    @pytest.mark.parametrize("entrada, salida", LAS_FECHAS_QUE_SE_ESCRIBEN_ASI)
    def test_fecha_iso_escribe_el_anio_con_cuatro_cifras_y_el_mes_y_el_dia_con_dos(self, entrada, salida):
        assert _svc().fecha_iso(entrada) == salida

    @pytest.mark.parametrize("entrada", LAS_FECHAS_IMPOSIBLES)
    def test_fecha_iso_sigue_rechazando_lo_imposible(self, entrada):
        """BARRERA (pasa antes y despues): el año 0 no existe, 1900 no fue bisiesto, no hay 30 de febrero ni mes 13 y la fecha se escribe aaaa-mm-dd."""
        assert _svc().fecha_iso(entrada) is None

    def test_un_anio_anterior_a_1000_se_guarda_con_cuatro_cifras_y_la_segunda_calibracion_reemplaza_a_la_primera(self, bd, escaneos):
        primera = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "0999-12-31"}, _piezas(escaneos, {1, 2}))
        piezas = _piezas(escaneos, {1, 2})
        piezas[0]["fecha_escaneo"] = "0999-01-02"
        segunda = _svc().guardar("fisico", {**ENCABEZADO, "fecha_irradiacion": "0999-12-31"}, piezas)
        assert _sql(bd, f"SELECT id, fecha_irradiacion, DATE(fecha_irradiacion), activo FROM {TABLA} ORDER BY id") == [(primera, "0999-12-31", "0999-12-31", 0), (segunda, "0999-12-31", "0999-12-31", 1)]
        assert [a[0] for a in _auditoria(bd)] == ["guardar", "reemplazo"] and "irradiada el 0999-12-31" in _auditoria(bd)[1][3]
        assert _sql(bd, f"SELECT fecha_escaneo FROM {PIEZAS} WHERE ref = ? ORDER BY orden", (segunda,)) == [("0999-01-02",), (None,)]
        assert _svc().leer(segunda)["fecha_irradiacion"] == "0999-12-31" and [f["id"] for f in _svc().listar()] == [segunda]


# ------------------------------------------------------------------------------------------------------------------------------------- D1: el usuario

LOS_USUARIOS_QUE_NO_SON_UN_TEXTO = [pytest.param(valor, repr(valor), id=nombre) for nombre, valor in (
    ("lista", ["ana"]), ("tupla", ("ana",)), ("dict", {"nombre": "ana"}), ("set", {"ana"}), ("path", Path("ana")), ("fraction", fractions.Fraction(1, 3)), ("decimal", decimal.Decimal("1.5")),
    ("entero", 7), ("entero_de_mas_de_64_bits", 2**63), ("True", True), ("False", False), ("nan", float("nan")), ("real", 1.5), ("bytes", b"ana"), ("bytes_vacio", b""), ("bytearray", bytearray(b"ana")),
    ("np.int64", np.int64(7)), ("np.float64", np.float64(1.5)), ("np.array", np.array([1, 2])), ("generador", (i for i in range(3))), ("callable", len))] + [
    pytest.param(ENORME, UN_ENTERO_ENORME, id="entero_enorme"), pytest.param(QUE_NO_SE_ESCRIBE, UN_OBJETO_QUE_NO_SE_ESCRIBE, id="repr_que_lanza")]


class TestR3cD1ElUsuario:
    """CD4-R3-D1 (CD4-R3-FRO-01, PRU-04): `guardar` y `anular` validaban el usuario con `str(usuario).strip()` pero pasaban el usuario CRUDO a `reemplazar_bloque` y a la auditoria: con una lista, un `Path`, un `Fraction` o un
    entero de mas de 64 bits la calibracion se comiteaba (o se anulaba) SIN su fila de auditoria y sin aviso (`audit_minimo` se traga el error por diseño), y con «  ana  » la fila y la auditoria guardaban usuarios distintos.
    Ahora se valida UNA vez en la frontera (`_usuario`) y ESE texto, sin los espacios de los lados, va a la fila, a `reemplazar_bloque` y a la auditoria."""

    @pytest.mark.parametrize("usuario, como", LOS_USUARIOS_QUE_NO_SON_UN_TEXTO)
    def test_guardar_con_un_usuario_que_no_es_un_texto_se_rechaza_antes_de_medir_ni_copiar_nada(self, bd, escaneos, usuario, como):
        _el_guardado_se_rechaza(bd, escaneos, f"el usuario que guarda la calibración debe ser un texto, no {como}", usuario=usuario)

    @pytest.mark.parametrize("usuario, como", LOS_USUARIOS_QUE_NO_SON_UN_TEXTO)
    def test_anular_con_un_usuario_que_no_es_un_texto_se_rechaza_primero_aunque_el_id_no_exista(self, bd, usuario, como):
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().anular(999, usuario)                                   # ni siquiera existe: el usuario se valida primero
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"el usuario que anula la calibración debe ser un texto, no {como}"
        assert _conteos(bd) == (0, 0, 0)

    def test_anular_con_un_usuario_que_no_es_un_texto_no_anula_y_no_deja_la_auditoria_a_medias(self, bd, escaneos):
        """La parte grave de FRO-01: `anular(1, ['ana'])` anulaba la calibracion y su fila de auditoria se perdia en silencio. Aqui no se anula nada y la auditoria sigue teniendo solo el `guardar`."""
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        antes = _conteos(bd)
        for usuario in (["ana"], 7, True, float("nan"), 2**63, ENORME, QUE_NO_SE_ESCRIBE):
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().anular(nuevo, usuario)
            assert type(e.value) is _svc().CurvaDosisError and str(e.value).startswith("el usuario que anula la calibración debe ser un texto, no ")
        assert _conteos(bd) == antes and _sql(bd, f"SELECT activo FROM {TABLA}") == [(1,)] and _sql(bd, f"SELECT activo FROM {PIEZAS} ORDER BY orden") == [(1,), (1,)]
        assert [a[0] for a in _auditoria(bd)] == ["guardar"]

    def test_un_usuario_con_un_caracter_que_no_se_puede_escribir_se_rechaza_en_guardar_y_en_anular(self, bd, escaneos):
        _el_guardado_se_rechaza(bd, escaneos, "el usuario que guarda la calibración" + SIN_ESCRIBIR, usuario=SURROGADO)
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().anular(nuevo, f"  {SURROGADO}  ")
        assert type(e.value) is _svc().CurvaDosisError and str(e.value) == "el usuario que anula la calibración" + SIN_ESCRIBIR
        assert _sql(bd, f"SELECT activo FROM {TABLA}") == [(1,)] and [a[0] for a in _auditoria(bd)] == ["guardar"]

    def test_el_usuario_se_guarda_y_se_audita_sin_los_espacios_de_los_lados(self, bd, escaneos):
        """El mismo texto en la fila, en la auditoria del `guardar`, en la del `reemplazo` y en la del `anular`: «  ana  » es «ana» en las cuatro (antes la auditoria guardaba «  ana  »)."""
        primera = _svc().guardar("  ana  ", ENCABEZADO, _piezas(escaneos, {1, 2}))
        segunda = _svc().guardar(" ana\t", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert _svc().anular(segunda, "  jefe  ") is True
        assert _sql(bd, f"SELECT id, usuario FROM {TABLA} ORDER BY id") == [(primera, "ana"), (segunda, "ana")]
        assert [(a[0], a[4]) for a in _auditoria(bd)] == [("guardar", "ana"), ("reemplazo", "ana"), ("anular", "jefe")]

    def test_un_usuario_de_numpy_que_es_un_texto_y_uno_con_espacios_por_dentro_se_aceptan(self, bd, escaneos):
        """`np.str_` es un `str` y se acepta; el nombre «Ana  María» se guarda tal cual (solo se quitan los espacios de los lados) en la fila y en la auditoria."""
        a = _svc().guardar(np.str_(" ana "), ENCABEZADO, _piezas(escaneos, {1, 2}))
        b = _svc().guardar("Ana  María", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos, {1, 2}))
        assert _sql(bd, f"SELECT id, usuario FROM {TABLA} ORDER BY id") == [(a, "ana"), (b, "Ana  María")]
        assert [(x[0], x[4]) for x in _auditoria(bd)] == [("guardar", "ana"), ("guardar", "Ana  María")]


# ------------------------------------------------------------------------------------------------------------------------------------- D2: los ids

LOS_IDS_QUE_NO_SON_UN_ENTERO = [pytest.param(valor, repr(valor), id=nombre) for nombre, valor in (
    ("texto", "1"), ("real", 1.0), ("True", True), ("False", False), ("None", None), ("lista", [1]), ("tupla", (1,)), ("set", {1}), ("dict", {"id": 1}), ("fraction", fractions.Fraction(1, 1)),
    ("decimal", decimal.Decimal(1)), ("path", Path("1")), ("bytes", b"1"), ("np.float64", np.float64(1.0)), ("np.bool_", np.bool_(True)), ("texto_con_un_surrogado", SURROGADO), ("callable", len))] + [
    pytest.param(QUE_NO_SE_ESCRIBE, UN_OBJETO_QUE_NO_SE_ESCRIBE, id="repr_que_lanza")]
LOS_IDS_QUE_NO_CABEN = [pytest.param(valor, repr(valor), id=nombre) for nombre, valor in (
    ("2**63", 2**63), ("menos_2**63_menos_1", -2**63 - 1), ("10**400", 10**400), ("np.uint64", np.uint64(2**63)))] + [pytest.param(ENORME, UN_ENTERO_ENORME, id="entero_enorme")]


class TestR3cD2LosIds:
    """CD4-R3-D2 (CD4-R3-FRO-02): `anular(id)` y `leer(id)` pasaban el id a SQLite sin validarlo: un entero fuera de 64 bits salia como `OverflowError` crudo, un `Fraction`, un `Path` o una lista como `sqlite3.ProgrammingError`, un texto con
    un surrogado como `UnicodeEncodeError`, y `True` actuaba sobre la calibracion 1. Ahora el id se valida como el `equipo_id` (un entero que cabe en la base) y sale como `int`."""

    @pytest.mark.parametrize("id_calibracion, como", LOS_IDS_QUE_NO_SON_UN_ENTERO)
    def test_leer_con_un_id_que_no_es_un_entero_se_rechaza(self, bd, id_calibracion, como):
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().leer(id_calibracion)
        assert type(e.value) is _svc().CurvaDosisError and str(e.value) == EL_ID_NO_ES_UN_ENTERO + como

    @pytest.mark.parametrize("id_calibracion, como", LOS_IDS_QUE_NO_SON_UN_ENTERO)
    def test_anular_con_un_id_que_no_es_un_entero_se_rechaza_sin_escribir_ni_auditar(self, bd, id_calibracion, como):
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().anular(id_calibracion, "fisico")
        assert type(e.value) is _svc().CurvaDosisError and str(e.value) == EL_ID_NO_ES_UN_ENTERO + como
        assert _conteos(bd) == (0, 0, 0)

    @pytest.mark.parametrize("id_calibracion, como", LOS_IDS_QUE_NO_CABEN)
    def test_leer_y_anular_con_un_id_que_no_cabe_en_la_base_se_rechazan(self, bd, id_calibracion, como):
        for llamada in (lambda: _svc().leer(id_calibracion), lambda: _svc().anular(id_calibracion, "fisico")):
            with pytest.raises(_svc().CurvaDosisError) as e:
                llamada()
            assert type(e.value) is _svc().CurvaDosisError and str(e.value) == EL_ID_NO_CABE + como
        assert _conteos(bd) == (0, 0, 0)

    def test_un_bool_no_actua_sobre_la_calibracion_1(self, bd, escaneos):
        """`True == 1` para SQLite: `leer(True)` devolvia la calibracion 1 y `anular(True, ...)` la anulaba y auditaba su ref como «True»."""
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert nuevo == 1
        for llamada in (lambda: _svc().leer(True), lambda: _svc().anular(True, "fisico")):
            with pytest.raises(_svc().CurvaDosisError) as e:
                llamada()
            assert type(e.value) is _svc().CurvaDosisError and str(e.value) == EL_ID_NO_ES_UN_ENTERO + "True"
        assert _sql(bd, f"SELECT activo FROM {TABLA}") == [(1,)] and [a[0] for a in _auditoria(bd)] == ["guardar"]

    def test_un_id_de_numpy_se_usa_como_el_entero_que_es(self, bd, escaneos):
        nuevo = _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert _svc().leer(np.int64(nuevo))["id"] == nuevo
        assert _svc().anular(np.int64(nuevo), "fisico") is True
        anulada = [a for a in _auditoria(bd) if a[0] == "anular"]
        assert len(anulada) == 1 and anulada[0][2] == str(nuevo) and f"id={nuevo} (" in anulada[0][3]
        assert _sql(bd, f"SELECT activo FROM {TABLA}") == [(0,)]

    def test_un_id_valido_que_no_existe_sigue_dando_none_y_false(self, bd):
        """BARRERA (pasa antes y despues): el borde de la base (`2**63 - 1`, `-2**63`) y el cero son ids validos que no existen: `leer` da `None` y `anular` da `False` sin escribir ni auditar nada."""
        for id_calibracion in (0, -1, 2**63 - 1, -2**63):
            assert _svc().leer(id_calibracion) is None
            assert _svc().anular(id_calibracion, "fisico") is False
        assert _conteos(bd) == (0, 0, 0)


# ------------------------------------------------------------------------------------------------------------------------------------- D3: condiciones y modo de escaneo

LAS_CONDICIONES_FALSAS_QUE_NO_SON_UN_DICCIONARIO = [pytest.param(valor, id=nombre) for nombre, valor in (
    ("cero", 0), ("cero_real", 0.0), ("texto_vacio", ""), ("lista_vacia", []), ("tupla_vacia", ()), ("conjunto_vacio", set()), ("False", False), ("bytes_vacio", b""), ("np.float64_cero", np.float64(0.0)),
    ("arreglo_vacio_de_numpy", np.array([])), ("arreglo_de_numpy", np.array([1.0, 2.0])))]
LAS_CONDICIONES_VERDADERAS_QUE_NO_SON_UN_DICCIONARIO = [pytest.param(valor, id=nombre) for nombre, valor in (("lista", [1]), ("texto", "x"), ("entero", 3), ("tupla", (1, 2)), ("True", True))]
LAS_CLAVES_QUE_NO_SON_UN_TEXTO = [
    pytest.param({1: 2}, "1", id="entero"), pytest.param({True: 1}, "True", id="bool"), pytest.param({None: 1}, "None", id="none"), pytest.param({1.5: 1}, "1.5", id="real"),
    pytest.param({(1, 2): 3}, "(1, 2)", id="tupla"), pytest.param({b"x": 1}, "b'x'", id="bytes"), pytest.param({float("nan"): 1}, "nan", id="nan"),
    pytest.param({"a": {"b": {1: 2}}}, "1", id="en_un_diccionario_anidado"), pytest.param({"a": [{"x": 1}, {2: 3}]}, "2", id="en_una_lista"), pytest.param({"a": ({True: 0},)}, "True", id="en_una_tupla"),
    pytest.param({"a": [[{None: 0}]]}, "None", id="en_listas_anidadas"), pytest.param({"a": 1, 2: 2, 3: 3}, "2", id="la_primera_en_el_orden_del_diccionario"), pytest.param({1: "a", "b": 2}, "1", id="claves_mezcladas"),
    pytest.param({ENORME: 1}, UN_ENTERO_ENORME, id="entero_enorme"), pytest.param({QUE_NO_SE_ESCRIBE: 1}, UN_OBJETO_QUE_NO_SE_ESCRIBE, id="repr_que_lanza"),
    # CD4-R4-D4 (CD4-R4-PRU-01): una TUPLA dentro de una lista o de otra tupla. Si el recorrido deja de apilar tuplas en su rama final, {'a': [({1: 2},)]} se guardaria como {"a": [[{"1": 2}]]} (la clave cambia por JSON, justo lo que D3 evita)
    pytest.param({"a": [({1: 2},)]}, "1", id="en_una_tupla_dentro_de_una_lista"), pytest.param({"a": (({1: 2},),)}, "1", id="en_una_tupla_dentro_de_una_tupla")]
LOS_MODOS_QUE_NO_SON_UN_TEXTO_DE_LA_LISTA = [pytest.param(valor, id=nombre) for nombre, valor in (
    ("arreglo_de_numpy_con_un_modo", np.array(["transmisión"])), ("arreglo_vacio_de_numpy", np.array([])), ("arreglo_de_numpy_de_dos", np.array([1, 2])), ("arreglo_de_numpy_de_0_dim", np.array("transmisión")),
    ("lista_con_un_modo", ["transmisión"]), ("tupla_con_un_modo", ("transmisión",)), ("cero", 0), ("False", False), ("texto_vacio", ""), ("texto_distinto", "otro"), ("sin_tilde", "transmision"))]


class TestR3cD3CondicionesYModo:
    """CD4-R3-D3 (CD4-R3-PROD-03, PROD-04, FRO-04): `encabezado.get('condiciones') or {}` convertia en `{}` cualquier falso que no es un diccionario (y con un arreglo de numpy lanzaba un `ValueError` crudo), las claves que no son
    texto cambiaban al pasar por JSON ({1: 2} se guardaba {"1": 2}) y `modo not in MODOS_DE_ESCANEO` lanzaba un `ValueError` crudo con un arreglo de numpy. Ahora solo `None` da `{}`, toda clave de diccionario (a cualquier
    profundidad, en diccionarios, listas y tuplas) es texto y el modo es un texto de la lista o nada. Los VALORES de las condiciones siguen libres (CD4-R2-D2)."""

    @pytest.mark.parametrize("condiciones", LAS_CONDICIONES_FALSAS_QUE_NO_SON_UN_DICCIONARIO)
    def test_unas_condiciones_falsas_que_no_son_un_diccionario_se_rechazan(self, bd, escaneos, condiciones):
        _el_guardado_se_rechaza(bd, escaneos, NO_ES_UN_DICCIONARIO, cambio={"condiciones": condiciones})

    @pytest.mark.parametrize("condiciones", LAS_CONDICIONES_VERDADERAS_QUE_NO_SON_UN_DICCIONARIO)
    def test_unas_condiciones_verdaderas_que_no_son_un_diccionario_se_rechazan(self, bd, escaneos, condiciones):
        """BARRERA (pasa antes y despues): lo verdadero que no es un diccionario ya se rechazaba, con el mismo texto."""
        _el_guardado_se_rechaza(bd, escaneos, NO_ES_UN_DICCIONARIO, cambio={"condiciones": condiciones})

    @pytest.mark.parametrize("condiciones, como", LAS_CLAVES_QUE_NO_SON_UN_TEXTO)
    def test_una_clave_de_las_condiciones_que_no_es_un_texto_se_rechaza_con_su_texto(self, bd, escaneos, condiciones, como):
        _el_guardado_se_rechaza(bd, escaneos, SOLO_CLAVES_DE_TEXTO + como, cambio={"condiciones": condiciones})

    def test_los_valores_de_las_condiciones_siguen_siendo_libres(self, bd, escaneos):
        """BARRERA (pasa antes y despues, CD4-R2-D2): lo unico que se tipa son las CLAVES; los valores pueden ser numeros, textos, nada, listas, tuplas (que JSON vuelve listas) y diccionarios anidados."""
        condiciones = {"profundidad_cm": 3.0, "lista": [1, 2, {"c": None}], "tupla": (1, "a"), "anidado": {"x": {"y": [True, None, 1.5]}}, "ñ": "ü", "vacio": {}}
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "condiciones": condiciones}, _piezas(escaneos, {1, 2})))
        assert r["condiciones"] == json.loads(json.dumps(condiciones))

    def test_el_recorrido_de_las_condiciones_no_cuelga_con_una_estructura_recursiva_y_la_puerta_de_json_la_rechaza(self, bd, escaneos):
        """Una estructura que se contiene a si misma no debe colgar el recorrido de las claves (un conjunto de los contenedores ya vistos) ni lanzar `RecursionError`: el recorrido termina y la puerta estricta de JSON la
        rechaza despues con su texto, sin escribir ni copiar nada. Con un tope de 20 s (una alarma: un recorrido que no recuerda lo que ya vio no cuelga la corrida, falla)."""
        propio = {"profundidad_cm": 3.0}
        propio["yo"] = propio
        lista = []
        lista.append(lista)
        for condiciones in (propio, {"a": lista}, {"a": [propio]}):
            terminado, salida = _con_tope(20, lambda: _svc()._encabezado_valido({**ENCABEZADO, "condiciones": condiciones}))
            assert terminado, "el recorrido de las condiciones no termina con una estructura recursiva"
            assert "error" not in salida, repr(salida.get("error"))
            with pytest.raises(_svc().CurvaDosisError, match="lo que se guarda en la columna 'condiciones' no es JSON válido \\(Circular reference detected\\)") as e:
                _svc().guardar("fisico", {**ENCABEZADO, "condiciones": condiciones}, _piezas(escaneos, {1, 2}))
            assert type(e.value) is _svc().CurvaDosisError
            assert _conteos(bd) == (0, 0, 0) and not os.path.exists(_carpeta(bd))

    def test_una_clave_que_no_es_un_texto_en_una_estructura_recursiva_se_encuentra_igual(self, bd, escaneos):
        propio = {"profundidad_cm": 3.0}
        propio["yo"] = propio
        propio[7] = "x"
        terminado, salida = _con_tope(20, lambda: _svc()._encabezado_valido({**ENCABEZADO, "condiciones": propio}))
        assert terminado and type(salida.get("error")) is _svc().CurvaDosisError and str(salida["error"]) == SOLO_CLAVES_DE_TEXTO + "7"

    def test_el_recorrido_de_las_condiciones_no_usa_la_recursion_de_python(self):
        """Una estructura MUY honda (5000 niveles, mas que el limite de recursion de Python) se recorre sin `RecursionError`: el recorrido es iterativo. Y una clave que no es texto en el fondo se encuentra."""
        honda = {}
        actual = honda
        for _ in range(5000):
            actual["x"] = {}
            actual = actual["x"]
        assert _svc()._encabezado_valido({**ENCABEZADO, "condiciones": honda})["condiciones"] is honda
        actual[3] = "fondo"
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc()._encabezado_valido({**ENCABEZADO, "condiciones": honda})
        assert type(e.value) is _svc().CurvaDosisError and str(e.value) == SOLO_CLAVES_DE_TEXTO + "3"

    @pytest.mark.parametrize("modo", LOS_MODOS_QUE_NO_SON_UN_TEXTO_DE_LA_LISTA)
    def test_un_modo_de_escaneo_que_no_es_un_texto_de_la_lista_se_rechaza(self, bd, escaneos, modo):
        _el_guardado_se_rechaza(bd, escaneos, f"el modo de escaneo es transmisión o reflexión, o nada, no {modo!r}", cambio={"modo_de_escaneo": modo})

    def test_un_modo_de_escaneo_de_la_lista_o_nada_se_guarda(self, bd, escaneos):
        """BARRERA (pasa antes y despues): los dos modos, `None` y un `np.str_` (que es un texto) se aceptan y quedan en la cadena de captura."""
        for energia, modo in (("6 MV", "transmisión"), ("10 MV", "reflexión"), ("15 MV", None), ("18 MV", np.str_("reflexión"))):
            r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "energia": energia, "modo_de_escaneo": modo}, _piezas(escaneos, {1, 2})))
            assert r["cadena_de_captura"]["modo_de_escaneo"] == (None if modo is None else str(modo))


# ------------------------------------------------------------------------------------------------------------------------------------- D4: una copia que no se puede comprobar

LOS_ERRORES_DE_STAT = [pytest.param(PermissionError, 13, "Permission denied", id="sin_permiso_de_recorrido"), pytest.param(OSError, 5, "Input/output error", id="error_de_entrada_salida"),
                       pytest.param(OSError, 116, "Stale file handle", id="carpeta_de_red_obsoleta")]


class TestR3cD4LaCopiaQueNoSePuedeComprobar:
    """CD4-R3-D4 (CD4-R3-PROD-01): `recalcular` usaba `os.path.isfile`, que se traga el `OSError` del `stat`: una carpeta de escaneos sin permiso de recorrido (una carpeta de red, DP-152) salia como «escaneos_que_faltan»
    con `desde_los_escaneos=None` y `diferencias=[]`, es decir, lo ilegible se confundia con lo que falta. Ahora un `os.stat`: `FileNotFoundError` y `NotADirectoryError` son una falta (y lo que no es un archivo regular
    tambien); cualquier otro `OSError` es `CurvaDosisError`."""

    @pytest.mark.parametrize("clase, numero, razon", LOS_ERRORES_DE_STAT)
    def test_recalcular_con_una_copia_que_no_se_puede_comprobar_es_curva_dosis_error_y_no_una_falta(self, bd, escaneos, monkeypatch, clase, numero, razon):
        """Sin `chmod` (si la prueba corre como root un `chmod` no impide recorrer): se parchea `os.stat`, solo para la copia de la pieza 2, DENTRO de un `monkeypatch.context()`."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        nombre2 = hashlib.sha256(escaneos[2][2]).hexdigest() + ".tif"                 # la verdad sale de los bytes, no del servicio
        copia2 = os.path.join(_carpeta(bd), nombre2)
        stat_de_verdad = os.stat

        def stat(ruta, *a, **k):
            if os.path.normpath(os.fspath(ruta)) == os.path.normpath(copia2):
                raise clase(numero, razon, ruta)
            return stat_de_verdad(ruta, *a, **k)

        with monkeypatch.context() as m:
            m.setattr(os, "stat", stat)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().recalcular(r)
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == ("lo guardado de la calibración no se puede volver a ajustar: "
                                f"no se pudo comprobar la copia del escaneo {nombre2} junto a la base: [Errno {numero}] {razon}: {copia2!r}")
        rec = _svc().recalcular(r)          # sin el fallo la copia esta, intacta: ni falta ni no coincide, y se vuelve a medir
        assert rec.escaneos_que_faltan == () and rec.escaneos_que_no_coinciden == () and rec.desde_los_escaneos is not None
        assert _svc().diferencias(r, rec) == []

    def _guardada(self, bd, escaneos):
        """(registro, {orden: nombre de su copia}) de una calibracion de cuatro piezas."""
        r = _svc().leer(_svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS)))
        return r, {o: hashlib.sha256(escaneos[o][2]).hexdigest() + ".tif" for o in (1, 2, 3, 4)}

    def test_si_la_carpeta_de_los_escaneos_es_un_archivo_las_copias_faltan(self, bd, escaneos):
        """BARRERA (pasa antes y despues): un componente de la ruta que es un archivo da `NotADirectoryError`, que es una falta (no un error)."""
        r, copias = self._guardada(bd, escaneos)
        shutil.rmtree(_carpeta(bd))
        Path(_carpeta(bd)).write_bytes(b"no soy una carpeta")
        rec = _svc().recalcular(r)
        assert rec.escaneos_que_faltan == tuple(copias[o] for o in (1, 2, 3, 4)) and rec.escaneos_que_no_coinciden == () and rec.desde_los_escaneos is None
        assert _svc().diferencias(r, rec) == []

    def test_un_directorio_donde_debia_estar_la_copia_es_una_falta(self, bd, escaneos):
        """BARRERA (pasa antes y despues): lo que no es un archivo regular (aqui una carpeta con el nombre de la copia) cuenta como que falta la copia, no como una copia que no se puede leer."""
        r, copias = self._guardada(bd, escaneos)
        os.remove(os.path.join(_carpeta(bd), copias[2]))
        os.mkdir(os.path.join(_carpeta(bd), copias[2]))
        rec = _svc().recalcular(r)
        assert rec.escaneos_que_faltan == (copias[2],) and rec.escaneos_que_no_coinciden == () and rec.desde_los_escaneos is None

    def test_un_enlace_roto_es_una_falta(self, bd, escaneos):
        """BARRERA (pasa antes y despues): un enlace simbolico cuyo destino no existe es una falta."""
        r, copias = self._guardada(bd, escaneos)
        copia = os.path.join(_carpeta(bd), copias[3])
        os.remove(copia)
        try:
            os.symlink(os.path.join(os.path.dirname(copia), "no_existe.tif"), copia)
        except (OSError, NotImplementedError):
            pytest.skip("este sistema no deja crear enlaces simbolicos")
        rec = _svc().recalcular(r)
        assert rec.escaneos_que_faltan == (copias[3],) and rec.escaneos_que_no_coinciden == () and rec.desde_los_escaneos is None

    def test_un_enlace_a_un_archivo_que_si_esta_se_lee_como_la_copia(self, bd, escaneos, tmp_path):
        """BARRERA (pasa antes y despues): el `stat` sigue los enlaces (como `isfile`): un enlace a un archivo regular con los bytes de la pieza es la copia, y se vuelve a medir."""
        r, copias = self._guardada(bd, escaneos)
        copia = os.path.join(_carpeta(bd), copias[2])
        fuera = tmp_path / "fuera"
        fuera.mkdir()
        shutil.move(copia, str(fuera / copias[2]))
        try:
            os.symlink(str(fuera / copias[2]), copia)
        except (OSError, NotImplementedError):
            pytest.skip("este sistema no deja crear enlaces simbolicos")
        rec = _svc().recalcular(r)
        assert rec.escaneos_que_faltan == () and rec.escaneos_que_no_coinciden == () and rec.desde_los_escaneos is not None
        assert _svc().diferencias(r, rec) == []


# ------------------------------------------------------------------------------------------------------------------------------------- D8: el contrato del llamador

class TestR3cD8ElContratoDelLlamador:
    """CD4-R3-D8 (CD4-R3-FRO-06): sin codigo. `diferencias(registro, recalculo)`, `ruta_del_escaneo(sha256, procedencia)` y `recalcular` con algo que no es lo que dan `leer` y `recalcular` lanzan los `TypeError`, `AttributeError`,
    `KeyError` o `IndexError` naturales de Python; en vez de envolverlos se DECLARA el contrato del llamador en el docstring del modulo, que es lo que lee quien escribe CD.5, CD.6 y los PDF."""

    def test_el_docstring_del_modulo_declara_el_contrato_del_llamador(self):
        doc = _svc().__doc__
        assert "Contrato del llamador" in doc
        for frase in ("la ventana de calibración (CD.5)", "el motor mensual (CD.6)", "los PDF", "tipos básicos de Python y de numpy", "no se escribió nada: ni filas, ni auditoría, ni copias de escaneos",
                      "Fuera de contrato", "`__repr__`, `__hash__`, `__eq__` o `__bool__`", "`diferencias` y `ruta_del_escaneo`"):
            assert frase in doc, frase


# ===================================================================================================== (19) la ronda 3 de la revision, parte 2 (CD4-R3-PRU-01 y PRU-03, 30-10)
# El APLICADOR 2 escribe SOLO pruebas (la produccion no cambia: `services/curva_dosis.py` sigue como la dejo la parte 1) y SOLO las AGREGA. Dos hallazgos de pruebas de la ronda 3:
#   PRU-01  dos de las 18 «equivalentes» del barredor (B079, `_numero`, y B207, `_parametros_de_la_curva`: `float(valor) < minimo` pasa a `valor < minimo`) NO lo son: con un real NEGATIVO que redondea a -0.0 en float
#           (`Fraction(-1, 10**400)`, `np.longdouble('-1e-400')`) el servicio de hoy lo ACEPTA y lo guarda como 0.0 (compara el numero ya redondeado), y los mutantes lo rechazan. Se FIJA la conducta de hoy.
#   PRU-03  varios textos de rechazo de `guardar` que CD.5 mostrara tal cual solo se comprobaban por subcadena (`match=`): un texto que MIENTE sobre la causa pasaba (dos mutaciones del revisor: «al encabezado le faltan
#           {sobran}» y «falta el escaneo de la pieza {posicion}»). Se fija una TABLA caso -> texto EXACTO. Un texto fijado es un texto que la ventana mostrara tal cual: si alguno enganara, se dice en el informe y no se cambia aqui.
# Sus mutaciones son las `R3C-PRU01-M1`, `R3C-PRU01-M2`, `R3C-PRU03-M1` y `R3C-PRU03-M2` de `cd4_mutaciones.py` (LA_RONDA_3C_PARTE2). PRU-02 (siete parejas de R2-BA con el mismo efecto) no lleva prueba: es una cuenta honesta
# anotada en obstaculos.md y en el docstring del registro.

LOS_NEGATIVOS_QUE_REDONDEAN_A_CERO = [pytest.param(fractions.Fraction(-1, 10**400), id="fraction_de_menos_uno_sobre_10_a_la_400"), pytest.param(np.longdouble("-1e-400"), id="longdouble_de_menos_1e_400")]
SIN_VALOR_POR_OMISION = " (sin valor por omisión: deciden qué se calibró)"
LA_VIRGEN_NO_ES_VALIDA = "la película virgen montada debe ser una referencia válida («ok») o nada"
LAS_PIEZAS_NO_SON_UNA_LISTA = "las piezas son una lista de diccionarios, una por escaneo"


class TestR3cPru01UnNegativoQueRedondeaACero:
    """CD4-R3-PRU-01: `_numero` compara `float(valor) < minimo` y `_parametros_de_la_curva` `float(valor) < 0.0`: el numero YA redondeado. Un real negativo tan chico que su `float` es -0.0 (`Fraction(-1, 10**400)`, o un
    `np.longdouble('-1e-400')` en un sistema donde el longdouble es mas ancho que un double) pasa la regla «de 0 o mas», y se guarda como 0.0. Quitar el `float(...)` (B079 y B207 del barrido) compara el real exacto y lo
    rechaza. Se fija la conducta de hoy por la via publica (`guardar`, `leer`, `recalcular`, `diferencias`): lo que se acepta, como se guarda y que se relee y se recalcula sin diferencias."""

    @pytest.mark.parametrize("valor", LOS_NEGATIVOS_QUE_REDONDEAN_A_CERO)
    def test_una_incertidumbre_negativa_que_redondea_a_cero_se_acepta_y_se_guarda_como_cero(self, bd, escaneos, valor):
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "u_dosis_medida_pct": valor}, _piezas(escaneos, {1, 2})))
        assert r["u_dosis_medida_pct"] == 0.0 and type(r["u_dosis_medida_pct"]) is float
        assert r["ajuste"]["u_dosis_medida_pct"] == 0.0 and type(r["ajuste"]["u_dosis_medida_pct"]) is float          # y en la copia del ajuste
        rec = _svc().recalcular(r)
        assert rec.desde_los_escaneos is not None and _svc().diferencias(r, rec) == []

    @pytest.mark.parametrize("valor", LOS_NEGATIVOS_QUE_REDONDEAN_A_CERO)
    def test_un_parametro_de_la_curva_negativo_que_redondea_a_cero_se_acepta_y_se_guarda_como_cero(self, bd, escaneos, valor):
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"residuo_maximo_pct": valor}}, _piezas(escaneos, {1, 2})))
        guardado = r["parametros"]["curva"]["residuo_maximo_pct"]
        assert guardado == 0.0 and type(guardado) is float and repr(guardado) == "0.0"          # `float(valor) + 0.0`: el -0.0 se guarda 0.0 (CD4-R1-D1), sin signo, en el JSON
        rec = _svc().recalcular(r)
        assert rec.desde_los_escaneos is not None and _svc().diferencias(r, rec) == []

    @pytest.mark.parametrize("valor", LOS_NEGATIVOS_QUE_REDONDEAN_A_CERO)
    def test_el_factor_de_un_equipo_negativo_que_redondea_a_cero_se_acepta_y_se_guarda_como_cero(self, bd, escaneos, valor):
        """BARRERA (pasa antes y despues, y NO mata B079 ni B207): el factor de un equipo no tiene minimo (`_numero` sin `minimo` lo acepta con cualquier signo), asi que aqui lo unico que se fija es que un real que
        redondea a -0.0 se guarda como 0.0 y se relee y se recalcula sin diferencias, como la incertidumbre y el parametro de arriba."""
        r = _svc().leer(_svc().guardar("fisico", {**ENCABEZADO, "camara": {**ENCABEZADO["camara"], "factor": valor}}, _piezas(escaneos, {1, 2})))
        assert r["camara_factor"] == 0.0 and type(r["camara_factor"]) is float
        rec = _svc().recalcular(r)
        assert rec.desde_los_escaneos is not None and _svc().diferencias(r, rec) == []

    @pytest.mark.parametrize("donde, texto", [
        pytest.param("u_dosis_medida_pct", "la incertidumbre de la dosis medida debe ser un número finito de 0 o más o nada, no -1e-300", id="u_dosis_medida_pct"),
        pytest.param("parametros.residuo_maximo_pct", "el parámetro de la curva 'residuo_maximo_pct' debe ser un número finito de 0 o más, no -1e-300", id="residuo_maximo_pct")])
    def test_un_negativo_que_no_redondea_a_cero_se_sigue_rechazando(self, bd, escaneos, donde, texto):
        """BARRERA (pasa antes y despues): el borde esta en el `float`, no en el signo: -1e-300 es un double normal y distinto de cero, y se rechaza con su texto."""
        cabeza, piezas = dict(ENCABEZADO), _piezas(escaneos, {1, 2})
        _poner_en_el_guardado(cabeza, piezas, donde, -1e-300)
        _el_guardado_se_rechaza(bd, escaneos, texto, cambio=cabeza, piezas=piezas)


# ------------------------------------------------------------------------------------------------------------------------------------- PRU-03: la tabla de los textos EXACTOS de los rechazos de `guardar`

def _rechazo_exacto_de_guardar(bd, texto, cabeza, piezas, usuario="fisico", virgen=None):
    """`guardar` con EXACTAMENTE esos argumentos (a diferencia de `_el_guardado_se_rechaza`, que parte del `ENCABEZADO` y no puede quitarle una clave ni pasar `piezas=None`): se rechaza con `CurvaDosisError` EXACTO (el tipo y el
    texto ENTERO) y no queda nada escrito: ni filas, ni auditoria, ni una copia de un escaneo."""
    with pytest.raises(_svc().CurvaDosisError) as e:
        _svc().guardar(usuario, cabeza, piezas, virgen)
    assert type(e.value) is _svc().CurvaDosisError
    assert str(e.value) == texto
    assert _conteos(bd) == (0, 0, 0)
    assert not os.path.exists(_carpeta(bd))


# (donde, valor, texto): `donde` es lo que entiende `_poner_en_el_guardado`. El «de el» de los textos del electrometro es el `que` de hoy («el electrómetro»), como en la tabla de D7.
LOS_TEXTOS_EXACTOS_DEL_ENCABEZADO = [pytest.param(donde, valor, texto, id=ident) for ident, donde, valor, texto in (
    ("lote_en_blanco", "lote", " ", "falta el lote de la película"), ("lote_nada", "lote", None, "falta el lote de la película"), ("lote_que_no_es_un_texto", "lote", 5, "falta el lote de la película"),
    ("tipo_nada", "tipo_pelicula", None, "falta el tipo de película"), ("tipo_en_blanco", "tipo_pelicula", "  ", "falta el tipo de película"),
    ("energia_nada", "energia", None, "falta la energía"), ("energia_en_blanco", "energia", "", "falta la energía"),
    ("acelerador_que_no_es_un_texto", "acelerador", 5, "el acelerador debe ser un texto o nada, no 5"), ("acelerador_en_blanco", "acelerador", "  ", "el acelerador debe ser un texto o nada, no '  '"),
    ("escaner_que_no_es_un_texto", "escaner_declarado", 5, "el escáner declarado debe ser un texto o nada, no 5"),
    ("observaciones_que_no_son_un_texto", "observaciones", ["a"], "las observaciones debe ser un texto o nada, no ['a']"),
    ("modelo_de_la_camara", "camara.modelo", 5, "el modelo de la cámara debe ser un texto o nada, no 5"), ("serie_de_la_camara", "camara.serie", 5, "la serie de la cámara debe ser un texto o nada, no 5"),
    ("modelo_del_electrometro", "electrometro.modelo", 5, "el modelo de el electrómetro debe ser un texto o nada, no 5"),
    ("serie_del_electrometro", "electrometro.serie", 5, "la serie de el electrómetro debe ser un texto o nada, no 5"),
    ("fecha_con_otro_formato", "fecha_irradiacion", "20/10/2026", "la fecha de irradiación debe ser 'aaaa-mm-dd', no '20/10/2026'"),
    ("fecha_imposible", "fecha_irradiacion", "2026-02-30", "la fecha de irradiación debe ser 'aaaa-mm-dd', no '2026-02-30'"),
    ("fecha_que_no_es_un_texto", "fecha_irradiacion", 20261020, "la fecha de irradiación debe ser 'aaaa-mm-dd', no 20261020"),
    ("fecha_nada", "fecha_irradiacion", None, "la fecha de irradiación debe ser 'aaaa-mm-dd', no None"),
    ("incertidumbre_booleana", "u_dosis_medida_pct", True, "la incertidumbre de la dosis medida debe ser un número finito de 0 o más o nada, no True"),
    ("incertidumbre_en_texto", "u_dosis_medida_pct", "1.5", "la incertidumbre de la dosis medida debe ser un número finito de 0 o más o nada, no '1.5'"),
    ("incertidumbre_nan", "u_dosis_medida_pct", float("nan"), "la incertidumbre de la dosis medida debe ser un número finito de 0 o más o nada, no nan"),
    ("factor_de_la_camara_nan", "camara.factor", float("nan"), "el factor de la cámara debe ser un número finito o nada, no nan"),
    ("factor_del_electrometro_en_texto", "electrometro.factor", "x", "el factor de el electrómetro debe ser un número finito o nada, no 'x'"),
    ("equipo_id_en_texto", "camara.equipo_id", "19", "el equipo_id de la cámara es un entero o nada, no '19'"),
    ("equipo_id_booleano", "electrometro.equipo_id", True, "el equipo_id de el electrómetro es un entero o nada, no True"),
    ("piezas_minimas_cero", "parametros.piezas_minimas", 0, "el parámetro de la curva 'piezas_minimas' debe ser un entero de 1 o más, no 0"),
    ("piezas_minimas_decimal", "parametros.piezas_minimas", 1.5, "el parámetro de la curva 'piezas_minimas' debe ser un entero de 1 o más, no 1.5"),
    ("piezas_minimas_en_texto", "parametros.piezas_minimas", "3", "el parámetro de la curva 'piezas_minimas' debe ser un entero de 1 o más, no '3'"),
    ("residuo_maximo_negativo", "parametros.residuo_maximo_pct", -1.0, "el parámetro de la curva 'residuo_maximo_pct' debe ser un número finito de 0 o más, no -1.0"))]

# La pieza 2 de la lista lleva el ORDEN 7: la posicion en la lista (2) y el orden (7) son distintos, asi un texto que nombra la una donde debia nombrar el otro (la mutacion O3 del revisor) no pasa.
LOS_TEXTOS_EXACTOS_DE_UN_CAMPO_DE_LA_PIEZA = [pytest.param(campo, valor, texto, id=ident) for ident, campo, valor, texto in (
    ("escaneo_vacio", "datos", b"", "falta el escaneo de la pieza 7"), ("escaneo_que_es_un_texto", "datos", "texto", "falta el escaneo de la pieza 7"), ("escaneo_nada", "datos", None, "falta el escaneo de la pieza 7"),
    ("nombre_que_es_solo_una_carpeta", "nombre_archivo", "C:\\carpeta\\", "falta el nombre del archivo de la pieza 7"), ("nombre_en_blanco", "nombre_archivo", "  ", "falta el nombre del archivo de la pieza 7"),
    ("nombre_que_no_es_un_texto", "nombre_archivo", 5, "falta el nombre del archivo de la pieza 7"), ("nombre_nada", "nombre_archivo", None, "falta el nombre del archivo de la pieza 7"),
    ("fecha_de_escaneo_en_palabras", "fecha_escaneo", "ayer", "la fecha de escaneo de la pieza 7 debe ser 'aaaa-mm-dd' o nada, no 'ayer'"),
    ("fecha_de_escaneo_imposible", "fecha_escaneo", "2026-02-30", "la fecha de escaneo de la pieza 7 debe ser 'aaaa-mm-dd' o nada, no '2026-02-30'"),
    ("fecha_de_escaneo_que_no_es_un_texto", "fecha_escaneo", 20261021, "la fecha de escaneo de la pieza 7 debe ser 'aaaa-mm-dd' o nada, no 20261021"),
    ("dosis_nominal_que_no_cabe", "dosis_nominal_cgy", 10**400, f"la dosis nominal de la pieza 7 debe ser un número finito, no {10**400!r}"),
    ("dosis_medida_que_no_cabe", "dosis_medida_cgy", 10**400, f"la dosis medida de la pieza 7 debe ser un número finito, no {10**400!r}"))]

# Los textos que nombran la pieza por su POSICION en la lista (la pieza 2 de la lista): el orden de la pieza 2 se cambia por algo que no es un orden valido.
LOS_TEXTOS_EXACTOS_DEL_ORDEN = [pytest.param(valor, texto, id=ident) for ident, valor, texto in (
    ("orden_decimal", 1.5, "el orden de la pieza 2 de la lista debe ser un entero que no se repite, no 1.5"), ("orden_booleano", True, "el orden de la pieza 2 de la lista debe ser un entero que no se repite, no True"),
    ("orden_repetido", 1, "el orden de la pieza 2 de la lista debe ser un entero que no se repite, no 1"), ("orden_en_texto", "2", "el orden de la pieza 2 de la lista debe ser un entero que no se repite, no '2'"),
    ("orden_nada", None, "el orden de la pieza 2 de la lista debe ser un entero que no se repite, no None"))]


class TestR3cPru03LosTextosExactosDeGuardar:
    """CD4-R3-PRU-03: los textos de rechazo de `guardar` que la ventana (CD.5) mostrara tal cual y que solo se comprobaban por subcadena (`match=`): una mutacion que los hace MENTIR sobre la causa («al encabezado le faltan
    {sobran}», «falta el escaneo de la pieza {posicion}») sobrevivia a los 327 casos. Aqui cada rechazo se compara con su texto ENTERO y se comprueba que no queda nada escrito."""

    @pytest.mark.parametrize("donde, valor, texto", LOS_TEXTOS_EXACTOS_DEL_ENCABEZADO)
    def test_un_campo_del_encabezado_mal_dado_se_rechaza_con_su_texto_exacto(self, bd, escaneos, donde, valor, texto):
        cabeza, piezas = dict(ENCABEZADO), _piezas(escaneos, {1, 2})
        _poner_en_el_guardado(cabeza, piezas, donde, valor)
        _el_guardado_se_rechaza(bd, escaneos, texto, cambio=cabeza, piezas=piezas)

    @pytest.mark.parametrize("faltan, texto", [
        pytest.param(("tipo_pelicula",), "al encabezado le faltan ['tipo_pelicula']" + SIN_VALOR_POR_OMISION, id="una"),
        pytest.param(("energia", "lote"), "al encabezado le faltan ['lote', 'energia']" + SIN_VALOR_POR_OMISION, id="dos_en_el_orden_de_las_obligatorias"),
        pytest.param(("energia", "fecha_irradiacion", "tipo_pelicula", "lote"), "al encabezado le faltan ['lote', 'tipo_pelicula', 'fecha_irradiacion', 'energia']" + SIN_VALOR_POR_OMISION, id="las_cuatro")])
    def test_al_encabezado_le_faltan_dice_lo_que_falta_en_el_orden_de_las_obligatorias(self, bd, escaneos, faltan, texto):
        """La mutacion O2 del revisor (decir lo que SOBRA donde decia lo que FALTA, «le faltan []») pasaba los 327 casos: pedian solo `match='le faltan'`."""
        _rechazo_exacto_de_guardar(bd, texto, {k: v for k, v in ENCABEZADO.items() if k not in faltan}, _piezas(escaneos, {1, 2}))

    @pytest.mark.parametrize("campo, valor, texto", LOS_TEXTOS_EXACTOS_DE_UN_CAMPO_DE_LA_PIEZA)
    def test_un_campo_mal_dado_de_una_pieza_se_rechaza_nombrandola_por_su_orden_y_no_por_su_posicion(self, bd, escaneos, campo, valor, texto):
        """La mutacion O3 del revisor (nombrar la POSICION en la lista donde el texto nombra el ORDEN de la pieza) pasaba los 327 casos: `match='falta el escaneo'` y las piezas de las pruebas tienen el orden igual a
        su posicion. Aqui la pieza 2 de la lista tiene el orden 7."""
        piezas = _piezas(escaneos, {1, 2})
        piezas[1]["orden"] = 7
        piezas[1][campo] = valor
        _el_guardado_se_rechaza(bd, escaneos, texto, piezas=piezas)

    @pytest.mark.parametrize("valor, texto", LOS_TEXTOS_EXACTOS_DEL_ORDEN)
    def test_un_orden_que_no_es_valido_se_rechaza_nombrando_la_pieza_por_su_posicion_en_la_lista(self, bd, escaneos, valor, texto):
        piezas = _piezas(escaneos, {1, 2})
        piezas[1]["orden"] = valor
        _el_guardado_se_rechaza(bd, escaneos, texto, piezas=piezas)

    @pytest.mark.parametrize("posicion, intruso, texto", [
        pytest.param(1, "x", "la pieza 1 de la lista no es un diccionario", id="la_primera"), pytest.param(2, None, "la pieza 2 de la lista no es un diccionario", id="la_segunda"),
        pytest.param(3, 5, "la pieza 3 de la lista no es un diccionario", id="la_tercera")])
    def test_una_pieza_que_no_es_un_diccionario_se_rechaza_nombrandola_por_su_posicion(self, bd, escaneos, posicion, intruso, texto):
        piezas = _piezas(escaneos, {1, 2})[:posicion - 1] + [intruso]          # las buenas que anteceden al intruso y el intruso en la posicion dada
        _el_guardado_se_rechaza(bd, escaneos, texto, piezas=piezas)

    @pytest.mark.parametrize("piezas, texto", [
        pytest.param(None, LAS_PIEZAS_NO_SON_UNA_LISTA, id="nada"), pytest.param(5, LAS_PIEZAS_NO_SON_UNA_LISTA, id="un_entero"),
        pytest.param([], "una calibración necesita al menos una pieza", id="lista_vacia"), pytest.param((), "una calibración necesita al menos una pieza", id="tupla_vacia")])
    def test_unas_piezas_que_no_son_una_lista_o_que_estan_vacias_se_rechazan_con_su_texto(self, bd, piezas, texto):
        _rechazo_exacto_de_guardar(bd, texto, ENCABEZADO, piezas)

    @pytest.mark.parametrize("virgen", [{"estado": "ok"}, "ok", 5, False], ids=["un_diccionario", "un_texto", "un_entero", "False"])
    def test_una_virgen_que_no_es_una_referencia_valida_se_rechaza_con_su_texto(self, bd, escaneos, virgen):
        _rechazo_exacto_de_guardar(bd, LA_VIRGEN_NO_ES_VALIDA, ENCABEZADO, _piezas(escaneos, {1, 2}), virgen=virgen)

    @pytest.mark.parametrize("usuario", [None, "", "   "], ids=["nada", "vacio", "en_blanco"])
    def test_sin_usuario_se_rechaza_con_el_texto_de_guardar_y_con_el_de_anular(self, bd, escaneos, usuario):
        _el_guardado_se_rechaza(bd, escaneos, "falta el usuario que guarda la calibración", usuario=usuario)
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().anular(1, usuario)
        assert type(e.value) is _svc().CurvaDosisError and str(e.value) == "falta el usuario que anula la calibración"
        assert _conteos(bd) == (0, 0, 0)


# ------------------------------------------------------------------------------------------------------------------------------------- PRU-03: los textos EXACTOS de los rechazos de las copias

class TestR3cPru03LosTextosExactosDeLasCopias:
    """CD4-R3-PRU-03 (los «de las copias» del revisor): los seis rechazos de `_copiar_y_verificar` solo se comprobaban por una o dos subcadenas (`match=` o `in str(...)`). Cada uno reutiliza el montaje de su prueba de la
    seccion (4) y compara el texto ENTERO. Lo que dice el sistema operativo (`{error}`) se arma aqui con el mismo error simulado, o con la causa (`__cause__`) que el servicio encadena, para no depender de la plataforma."""

    @staticmethod
    def _huellas(datos):
        return hashlib.sha256(datos).hexdigest(), hashlib.sha256(datos[:-1] + b"\x00").hexdigest()          # la huella del escaneo y la de su copia corrupta (el ultimo byte cambiado)

    def test_la_copia_que_escribio_el_guardado_y_no_coincide_se_quita_diciendolo(self, bd, escaneos, monkeypatch):
        sha, copiado = self._huellas(escaneos[1][2])
        with monkeypatch.context() as m:
            TestLosEscaneos._con_la_escritura_corrupta(m)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"la copia del escaneo {sha}.tif no coincide con su huella: se esperaba {sha} y la copia da {copiado}; la copia que escribió este guardado se quitó"
        assert _conteos(bd) == (0, 0, 0) and os.listdir(_carpeta(bd)) == []

    def test_si_la_copia_que_no_coincide_no_se_puede_quitar_lo_dice_con_el_error_del_sistema(self, bd, escaneos, monkeypatch):
        sha, copiado = self._huellas(escaneos[1][2])
        destino = os.path.join(_carpeta(bd), sha + ".tif")

        def no_se_quita(ruta):
            raise OSError(13, "sin permiso", ruta)

        with monkeypatch.context() as m:
            TestLosEscaneos._con_la_escritura_corrupta(m)
            m.setattr(_svc().os, "remove", no_se_quita)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == (f"la copia del escaneo {sha}.tif no coincide con su huella: se esperaba {sha} y la copia da {copiado}; "
                                f"no se pudo quitar ({OSError(13, 'sin permiso', destino)}): hay que quitarla a mano antes de volver a guardar")
        assert _conteos(bd) == (0, 0, 0) and os.listdir(_carpeta(bd)) == [sha + ".tif"]          # la copia corrupta sigue ahi: el servicio no pudo quitarla y lo dijo

    def test_lo_que_ya_estaba_y_cambia_mientras_se_guarda_dice_que_cambio_y_que_hay_que_apartarlo(self, bd, escaneos, monkeypatch):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        antes = _conteos(bd)
        sha2 = hashlib.sha256(escaneos[2][2]).hexdigest()
        real = _svc()._copiar_el_escaneo

        def espia(carpeta, medida, datos, **kw):
            real(carpeta, medida, datos, **kw)
            if medida.procedencia["sha256"] == sha2:          # solo la pieza 2: se sobrescribe DESPUES de que CD.2 la dio por buena
                with open(_svc().ruta_del_escaneo(sha2, medida.procedencia), "wb") as f:
                    f.write(b"ajeno")

        with monkeypatch.context() as m:
            m.setattr(_svc(), "_copiar_el_escaneo", espia)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == (f"la copia del escaneo {sha2}.tif no coincide con su huella: se esperaba {sha2} y la copia da {hashlib.sha256(b'ajeno').hexdigest()}; "
                                "es la que ya estaba junto a la base: cambió mientras se guardaba y no se toca; hay que apartarla a mano para volver a guardar este escaneo")
        assert _conteos(bd) == antes

    def test_una_copia_que_ya_estaba_y_no_es_su_huella_dice_cual_es_y_donde_apartarla(self, bd, escaneos):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        antes = _conteos(bd)
        sha2 = hashlib.sha256(escaneos[2][2]).hexdigest()
        with open(os.path.join(_carpeta(bd), sha2 + ".tif"), "wb") as f:
            f.write(b"ajeno")                                              # la copia de la pieza 2 cambia en reposo
        with pytest.raises(_svc().CurvaDosisError) as e:
            _svc().guardar("fisico", {**ENCABEZADO, "energia": "15 MV"}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == (f"no se pudo copiar el escaneo '50.tif' junto a la base: la copia {sha2}.tif que ya estaba no coincide con su huella (da {hashlib.sha256(b'ajeno').hexdigest()}), "
                                f"así que no es el escaneo que se midió; no se sobrescribe ni se toca: hay que apartarla a mano de {_carpeta(bd)} para volver a guardar este escaneo")
        assert _conteos(bd) == antes

    def test_si_no_se_puede_leer_la_copia_que_ya_estaba_el_texto_trae_el_error_del_sistema(self, bd, escaneos, monkeypatch):
        _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        antes = _conteos(bd)
        sha2 = hashlib.sha256(escaneos[2][2]).hexdigest()
        copia2 = os.path.join(_carpeta(bd), sha2 + ".tif")

        def abrir(ruta, modo="r", *a, **k):
            if modo == "rb" and os.path.normpath(os.fspath(ruta)) == os.path.normpath(copia2):
                raise PermissionError(13, "sin permiso", ruta)
            return builtins.open(ruta, modo, *a, **k)

        with monkeypatch.context() as m:
            m.setattr(_svc(), "open", abrir, raising=False)          # sombrea el `open` global del modulo del servicio
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", {**ENCABEZADO, "energia": "10 MV"}, _piezas(escaneos, LAS_CUATRO_PRIMERAS))
        assert type(e.value) is _svc().CurvaDosisError
        assert str(e.value) == f"no se pudo leer la copia del escaneo {sha2}.tif que ya estaba junto a la base: {PermissionError(13, 'sin permiso', copia2)}"
        assert _conteos(bd) == antes

    def test_si_la_copia_desaparece_antes_de_leerla_de_vuelta_el_texto_trae_el_error_del_sistema(self, bd, escaneos, monkeypatch):
        sha = hashlib.sha256(escaneos[1][2]).hexdigest()
        real = _svc()._copiar_el_escaneo

        def espia(carpeta, medida, datos, **kw):
            real(carpeta, medida, datos, **kw)
            os.remove(_svc().ruta_del_escaneo(medida.procedencia["sha256"], medida.procedencia))          # alguien (u otro equipo, en una carpeta de red) la quita antes de leerla

        with monkeypatch.context() as m:
            m.setattr(_svc(), "_copiar_el_escaneo", espia)
            with pytest.raises(_svc().CurvaDosisError) as e:
                _svc().guardar("fisico", ENCABEZADO, _piezas(escaneos, {1, 2}))
        assert type(e.value) is _svc().CurvaDosisError and isinstance(e.value.__cause__, FileNotFoundError)
        assert str(e.value) == f"no se pudo leer de vuelta la copia del escaneo {sha}.tif junto a la base: {FileNotFoundError(2, os.strerror(2), os.path.join(_carpeta(bd), sha + '.tif'))}"
        assert _conteos(bd) == (0, 0, 0)
