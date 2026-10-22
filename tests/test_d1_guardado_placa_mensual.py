"""D.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-83 a DA-86): guardar el analisis nuevo del mensual de aceleradores -- la imagen y los datos finales de la capa reportada, en su propia tabla del
contrato (`analisis_placa_mensual`, hija de `controles`), con el servicio `services/placa_mensual.py` como la UNICA puerta a la tabla y `services/medidas_placa_mensual.py` (`MEDIDAS_GUARDADAS`) como la
lista unica de lo que se guarda.

CAUSA (H12; DP-92/DP-93). Las tres tablas del analisis viejo guardan magnitudes de otro metodo y ninguna guarda pixeles, puntos, piso, capa ni base: al reabrir no se reconstruye nada. El motor nuevo (C.1 a
C.3) mide todo, pero hasta aqui no hay donde dejarlo. DA-84 (11-10): solo se guardan los datos FINALES de la capa que el fisico reporta (su estado, el FWHM crossplane e inplane y el desfase de cada lado) mas lo
necesario para volver a medir (la imagen ORIGINAL tal cual, los puntos, los parametros, la version y el piso con su copia de la referencia virgen); lo demas se mide, se muestra y se vuelve a calcular al abrir.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del servicio (el oraculo es el MOTOR sobre esos mismos bytes: `leer_pelicula` + `refinar_marca` + `analizar`, y el generador de PF.0):
  (a) guardar con el escritor REAL -> leer: los valores son los del motor (igualdad exacta), PARAMETRIZADO sobre la capa (R, G y B: se guardan los de ESA capa y su letra; cambiar `CAPA_POR_OMISION` no
      cambia nada) y sobre el modo del piso (automatico, punto marcado y pelicula virgen: el modo recibido, no el de omision);
  (b) la imagen se guarda tal cual (los mismos bytes), los puntos como los da `MarcaRefinada.como_dict()` (clic y punto refinado), los parametros y la version del motor, y el piso ENTERO (con la copia de
      la referencia virgen en el modo virgen); el FWHM guardado = ancho luminoso + desfase izquierdo + desfase derecho (1e-9 mm) en los dos ejes;
  (c) reguardar anula sin borrar (la anterior queda entera, `activo = 0`), un control anulado o inexistente no acepta (W1) y no deja nada, un fallo a mitad no deja nada, y hay UNA fila de auditoria por
      guardado, escrita en la misma transaccion (al hacer `commit` ya esta), que nombra la capa y el piso (`texto_breve_del_piso`);
  (d) `recalcular(registro)` vuelve a medir con el modo, el punto y la copia de la referencia virgen GUARDADOS (nunca el archivo vigente), los parametros y los puntos guardados, sin refinar de nuevo, y
      `diferencias` da cero sobre lo recien guardado y ve cada valor, el piso de cada capa y la version cuando cambian;
  (e) la tabla, el escritor, el lector y la migracion de una base ya creada salen de UNA lista (`MEDIDAS_GUARDADAS`): quitar un valor de la lista lo quita de los tres, y sus claves son EXACTAMENTE las de
      `valores_medidos` (C.2);
  (f) el esquema: columnas y orden, NOT NULL, `capa IN ('R','G','B')`, FK a `controles` con RESTRICT, en `TABLAS_ANULABLES`, clave de bloque `("ref",)` con su indice unico parcial, hija (no raiz) del
      grafo de FK, ensayo sobre COPIA de las bases de referencia (solo aparece la tabla, `integrity_check` ok, `foreign_key_check` sin aumento, segunda apertura idempotente);
  (g) TRIPWIRE (patron C.3 del 21-09): toda escritura a la tabla vive en el servicio y toda funcion que escribe comprueba W1.
  (h) D.1b (20-10-2026, decision del fisico que revierte D1-D3): una capa elegida que NO es medible, por el motivo que sea, NO se guarda: `guardar` la rechaza sin escribir, sin auditar y sin
      anular el vigente, con el texto de `motivo_para_no_guardar` (la UNICA definicion de la regla, la que usa la ventana); una penumbra incompleta no la vuelve no medible. Ronda 1 de la revision: se
      juzga cada capa por lo suyo y cada uno de sus dos perfiles (la pelicula cortada por un solo lado), y el rechazo sin piso nombra la capa elegida y no siempre la verde.

Rojo contra HEAD (5079b2f): el servicio y la lista unica no existen y la tabla no existe; las pruebas importan por dentro (`_svc()`), asi que cada una cae con su error y las que fijan lo que D.1 no
cambia pasan. El rojo clasificado y las mutaciones estan en el anexo del plan (`d1_rojo_head.py`, `d1_mutaciones.py`).

Todo contra BD temporales copiadas de una plantilla: nunca se abre una BD de referencia (solo copias, con la regla de sesion). Sin Qt: no hay dialogos que parchear.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import dataclasses
import hashlib
import importlib
import inspect
import io
import json
import re
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import CLAVES_INDICE, crear_indices, nombre_indice
from services import visor_anulados as visor
from services.anulacion import TABLAS_ANULABLES
from services.lectura_vigente import RAICES_QC, cierre_transitivo_fk

import _corpus
import _placa_mensual_sintetica as gen
from _bd_referencia import BD_A_AJUSTAR, BD_QA, BD_REBUILD_08_10, BD_REBUILD_14_09, BD_REBUILD_21_09

RAIZ = Path(__file__).resolve().parent.parent
TABLA = "analisis_placa_mensual"
SERVICIO_PY = RAIZ / "services" / "placa_mensual.py"
MEDIDAS_PY = RAIZ / "services" / "medidas_placa_mensual.py"
CONECTION_PY = RAIZ / "data" / "ManejoDatos" / "conection.py"
USUARIO = "Fisico de prueba"
CAPAS = ("R", "G", "B")
MODOS = ("automatico", "punto_manual", "virgen")
EJES = ("crossplane", "inplane")
TAM = 25.4 / 600.0
CLICS_ML0 = [(196, 143), (2542, 147), (1371, 1330), (2526, 2501), (171, 2480)]       # los del cuaderno del fisico (R2), como en C.1

# lo que dice el PLAN (D.1) que se guarda de la capa reportada, escrito aqui a mano a proposito: es el ancla EXTERNA de la lista del codigo
MEDIDAS_DEL_PLAN = ("estado", "fwhm_crossplane_mm", "fwhm_inplane_mm", "desfase_izquierdo_mm", "desfase_derecho_mm", "desfase_superior_mm", "desfase_inferior_mm")
COLUMNAS_DE_DATOS = ("ref", "imagen", "nombre_archivo", "sha256", "formato", "bits", "transparentes", "dpi_declarado", "clase_resolucion", "tamano_pixel_mm", "version", "parametros", "puntos", "piso",
                     "capa") + MEDIDAS_DEL_PLAN + ("usuario", "fecha_registro")
OBLIGATORIAS = ("ref", "imagen", "sha256", "version", "parametros", "puntos", "piso", "capa", "estado", "usuario", "fecha_registro")
CLAVES_DE_LEER = frozenset(("id",) + COLUMNAS_DE_DATOS + ("activo",))


def _svc():
    """El servicio, importado POR PRUEBA: en HEAD (sin D.1) el archivo se colecciona y cada prueba cae con su error."""
    return importlib.import_module("services.placa_mensual")


def _med():
    return importlib.import_module("services.medidas_placa_mensual")


def _pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _P():
    # OD.1 (DA-87): la netOD es la base por omision del analisis y el rojo de la sintetica (y de las peliculas a 800 UM) esta recortado en ella; las pruebas de este
    # archivo fijan verdades del VALOR DE PIXEL (el generador de PF.0 las da en esa base), asi que la fijan explicitamente para seguir probando lo mismo. La netOD la
    # prueba `test_od1_densidad_optica.py`.
    return {**copy.deepcopy(_pm().VALORES_DE_LA_GEOMETRIA), "base_de_la_medida": _pm().BASE_VALOR_DE_PIXEL}


def _json(valor):
    return json.dumps(valor, sort_keys=True)


# ------------------------------------------------------------------------------------------------------------------------------- BD y siembra

@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    """La BD nueva con todo el esquema y los indices unicos, hecha UNA vez (el indice unico lo crea `crear_indices`, que llaman la herramienta de migracion y las pruebas; no corre al abrir la app)."""
    ruta = str(tmp_path_factory.mktemp("d1") / "plantilla.db")
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


def _sembrar_auditoria_ajena(ruta, cuantas=7):
    """Filas de `audit_log` de OTRA tabla, para que los ids de la auditoria y los del analisis NO avancen juntos. En una base recien creada `audit_log` esta vacia: sin esto el id de la fila de auditoria de
    un guardado y el id de su analisis son SIEMPRE el mismo numero, y ninguna prueba distingue el id que devuelve `guardar` del de su fila de auditoria (R1-PRU-02 de la ronda 1 de D.1)."""
    for i in range(cuantas):
        _sql(ruta, "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) VALUES ('2026-10-17 09:00:00', 'otro', 'guardar', 'controles', ?, 'fila ajena sembrada para desalinear los ids')",
             (str(i + 1),))


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    """Una copia de la plantilla y un `Conexion` sin arranque (el esquema ya esta): `conectar()` es el real. Con la auditoria ya desalineada del analisis (`_sembrar_auditoria_ajena`)."""
    ruta = str(tmp_path / "d1.db")
    shutil.copy(plantilla, ruta)
    _sembrar_auditoria_ajena(ruta)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    yield ruta
    Conexion._instance = previo


@pytest.fixture
def bd_nueva(monkeypatch, tmp_path):
    """Una BD que la app crea desde cero (sin el indice unico): para mirar el esquema tal como lo deja `Conexion()`."""
    ruta = str(tmp_path / "nueva.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _consulta(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, parametros).fetchall()
    finally:
        con.close()


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        cursor = con.execute(sql, parametros)
        con.commit()
        return cursor.lastrowid
    finally:
        con.close()


def _control(ruta, activo=1):
    """Un control mensual sembrado (cada uno de un equipo distinto: el indice unico de controles es por equipo, control y mes)."""
    nuevo = _sql(ruta, "INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', '10/2026')", (f"Equipo de prueba {uuid.uuid4().hex[:8]}",))
    if activo != 1:
        _sql(ruta, "UPDATE controles SET activo = ? WHERE id = ?", (activo, nuevo))
    return nuevo


def _columnas(ruta, tabla=TABLA):
    return [c[1] for c in _consulta(ruta, f"PRAGMA table_info('{tabla}')")]


def _filas(ruta):
    return _consulta(ruta, f"SELECT id, ref, activo, capa FROM {TABLA} ORDER BY id")


def _auditoria(ruta):
    return _consulta(ruta, "SELECT accion, usuario, ref, detalle FROM audit_log WHERE tabla = ? ORDER BY id", (TABLA,))


def _fila_minima(ref, **cambios):
    """Una fila valida con solo lo obligatorio (para probar el esquema y la lectura sin pasar por el analisis)."""
    fila = {"ref": ref, "imagen": b"\x89PNG bytes de una imagen de prueba", "sha256": "0" * 64, "version": "PM-1", "parametros": "{}", "puntos": "[]", "piso": "{}", "capa": "G", "estado": "ok",
            "usuario": USUARIO, "fecha_registro": "2026-10-18 10:00:00"}
    fila.update(cambios)
    return fila


def _insertar(ruta_o_con, fila):
    columnas = ", ".join(fila)
    marcas = ", ".join("?" * len(fila))
    sql = f"INSERT INTO {TABLA} ({columnas}) VALUES ({marcas})"
    if isinstance(ruta_o_con, sqlite3.Connection):
        return ruta_o_con.execute(sql, list(fila.values())).lastrowid
    return _sql(ruta_o_con, sql, list(fila.values()))


# ------------------------------------------------------------------------------------------------------ la pelicula y el oraculo (el motor)

@pytest.fixture(scope="module")
def placa():
    """La pelicula sintetica de PF.0 (independiente del motor): un PNG de 8 bits a 600 dpi, ~9 MB. Una vez por modulo."""
    return gen.generar("png", variante="A", seed=1)


@pytest.fixture(scope="module")
def clics(placa):
    return placa.verdad.clics_del_cuaderno()


@pytest.fixture(scope="module")
def punto_manual(placa):
    """El sexto clic: sobre la pelicula sin irradiar, a ~3.8 mm de la esquina superior izquierda de la pelicula (medido: es un piso valido)."""
    ul = placa.verdad.esquinas_pelicula_px["UL"]
    return (float(round(ul[0] + 90)), float(round(ul[1] + 90)))


@pytest.fixture(scope="module")
def virgen():
    """La referencia de una pelicula VIRGEN sintetica (la del generador con `meseta = virgen`, sin dosis ni tinta), medida con `piso_de_pelicula_virgen`, como en A.3. Se guardan solo las medidas."""
    calibracion = dict(gen.CALIB, meseta_bgr=gen.CALIB["virgen_bgr"], fondo_escaner=255.0)
    arreglo, _ = gen.generar_arreglo(variante="A", theta_deg=0.0, bits=8, dpi=600, tinta=False, calib=calibracion)
    arreglo = np.array(arreglo)
    arreglo[arreglo.min(axis=2) >= 235] = 255                    # el fondo del escaner, puro (la tapa cerrada)
    referencia = _pel().piso_de_pelicula_virgen(gen.codificar(arreglo, "tiff", 600), _P(), "virgen_lote.tif", fecha_calculo="2026-10-13")
    assert referencia.estado == "ok", referencia.estado
    return referencia


def _oraculo(datos, puntos, parametros, modo="automatico", punto=None, referencia=None):
    """Lo que el MOTOR da sobre esos bytes: `leer_pelicula`, cada clic refinado con `refinar_marca`, `analizar`. Devuelve un resumen sin los arreglos pesados."""
    pm, pel = _pm(), _pel()
    pelicula = pel.leer_pelicula(datos)
    tam = pel.escala_mm(pelicula.dpi, parametros)
    marcas = [pm.refinar_marca(pelicula.gris, clic, parametros, tam, pelicula.validos) for clic in puntos]
    resultado = pm.analizar(pelicula, marcas, parametros, modo_piso=modo, punto_manual=punto, referencia_virgen=referencia)
    anchos = {}
    for eje in EJES:
        luz = resultado.bordes_luz_px[eje]
        anchos[eje] = None if luz is None else float((luz[1] - luz[0]) * resultado.tam_mm)
    return SimpleNamespace(
        modo=modo, estado=resultado.estado, version=resultado.version, tam_mm=resultado.tam_mm, parametros=resultado.parametros, marcas=[m.como_dict() for m in marcas],
        valores={capa: pm.valores_medidos(resultado, capa) for capa in ("R", "G", "B", "gris")}, piso=resultado.piso.como_dict(), ancho_luz_mm=anchos,
        dpi=pelicula.dpi, bits=pelicula.bits, formato=pelicula.formato, transparentes=pelicula.transparentes)


@pytest.fixture(scope="module")
def oraculos(placa, clics, punto_manual, virgen):
    """El oraculo de los tres modos del piso sobre la misma pelicula (una vez por modulo)."""
    P = _P()
    return {"automatico": _oraculo(placa.datos, clics, P),
            "punto_manual": _oraculo(placa.datos, clics, P, "punto_manual", punto=punto_manual),
            "virgen": _oraculo(placa.datos, clics, P, "virgen", referencia=virgen)}


def _argumentos(placa, clics, el_punto, virgen, capa, modo, **cambios):
    """Lo que se le pasa a `guardar` (sin el ref): el modo decide si lleva el punto marcado o la referencia virgen."""
    argumentos = dict(usuario=USUARIO, datos=placa.datos, nombre="C:\\carpeta\\placa.png", puntos=clics, parametros=_P(), capa=capa, modo_piso=modo)
    if modo == "punto_manual":
        argumentos["punto_manual"] = el_punto
    if modo == "virgen":
        argumentos["referencia_virgen"] = virgen
    argumentos.update(cambios)
    return argumentos


@pytest.fixture
def guardar(placa, clics, punto_manual, virgen):
    """`guardar(ref, capa=..., modo=..., **cambios)` con los argumentos de siempre y el servicio real."""
    def _guardar(ref, capa="G", modo="automatico", **cambios):
        return _svc().guardar(ref, **_argumentos(placa, clics, punto_manual, virgen, capa, modo, **cambios))
    return _guardar


@pytest.fixture(scope="module")
def guardados(plantilla, tmp_path_factory, placa, clics, punto_manual, virgen):
    """Los NUEVE guardados (3 modos x 3 capas), cada uno sobre su control, en una BD del modulo: las pruebas de ida y vuelta solo LEEN de aqui (guardar cuesta ~1.5 s)."""
    ruta = str(tmp_path_factory.mktemp("guardados") / "guardados.db")
    shutil.copy(plantilla, ruta)
    _sembrar_auditoria_ajena(ruta)
    refs = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            for modo in MODOS:
                for capa in CAPAS:
                    ref = _control(ruta)
                    nuevo = _svc().guardar(ref, **_argumentos(placa, clics, punto_manual, virgen, capa, modo))
                    refs[(modo, capa)] = (ref, nuevo)
        finally:
            Conexion._instance = previo
    return SimpleNamespace(ruta=ruta, refs=refs)


@pytest.fixture
def lectura(guardados, monkeypatch):
    """Apunta el servicio a la BD de los guardados (solo lectura) y devuelve `leer(modo, capa)`."""
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: guardados.ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)

    def _leer(modo, capa):
        return _svc().leer(guardados.refs[(modo, capa)][0])
    _leer.guardados = guardados
    yield _leer
    Conexion._instance = previo


# ====================================================================================================================== (e) la lista unica

class TestLaListaUnica:
    def test_la_lista_dice_lo_que_el_plan_dice_que_se_guarda_con_su_unidad(self):
        medidas = _med().MEDIDAS_GUARDADAS
        assert [m.nombre for m in medidas] == list(MEDIDAS_DEL_PLAN)
        assert {m.nombre: m.unidad for m in medidas if m.nombre != "estado"} == {n: "mm" for n in MEDIDAS_DEL_PLAN[1:]}
        assert [m.tipo for m in medidas] == ["TEXT"] + ["REAL"] * 6
        assert [m.nombre for m in medidas if not m.admite_nulo] == ["estado"]        # sin el estado un vacio se confundiria con un cero

    def test_las_claves_de_valores_medidos_son_exactamente_los_nombres_de_la_lista(self):
        """Si no, el escritor generado de la lista dejaria fuera una clave del motor sin decirlo (o pediria una que el motor no produce)."""
        nombres = [m.nombre for m in _med().MEDIDAS_GUARDADAS]
        claves = list(_pm().CLAVES_DE_VALORES_MEDIDOS)
        assert len(set(nombres)) == len(nombres) and set(claves) == set(nombres) and len(claves) == len(nombres)

    def test_el_motor_produce_cada_nombre_de_la_lista(self, oraculos):
        nombres = {m.nombre for m in _med().MEDIDAS_GUARDADAS}
        for capa, valores in oraculos["automatico"].valores.items():
            assert set(valores) == nombres, capa

    def test_la_lista_no_importa_nada_del_proyecto(self):
        """Un modulo pequeno SIN dependencias: la importan `conection.py` (el CREATE TABLE) y el servicio sin riesgo de ciclo."""
        arbol = ast.parse(MEDIDAS_PY.read_text(encoding="utf-8"))
        importados = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                importados |= {a.name.split(".")[0] for a in nodo.names}
            elif isinstance(nodo, ast.ImportFrom):
                importados.add((nodo.module or "").split(".")[0])
        assert importados <= {"dataclasses", "__future__"}, importados

    def test_quitar_un_valor_de_la_lista_lo_quita_de_la_tabla_del_escritor_y_del_lector(self, monkeypatch, tmp_path, placa, clics, virgen, oraculos):
        med = _med()
        sin = tuple(m for m in med.MEDIDAS_GUARDADAS if m.nombre != "fwhm_inplane_mm")
        assert len(sin) == len(med.MEDIDAS_GUARDADAS) - 1
        monkeypatch.setattr(med, "MEDIDAS_GUARDADAS", sin)
        ruta = str(tmp_path / "sin_una_medida.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        try:
            Conexion().con.close()
            Conexion._instance = None
            columnas = _columnas(ruta)
            assert "fwhm_inplane_mm" not in columnas and "fwhm_crossplane_mm" in columnas                    # LA TABLA
            svc = _svc()
            assert "fwhm_inplane_mm" not in svc.sql_insert() and "fwhm_crossplane_mm" in svc.sql_insert()    # EL ESCRITOR
            Conexion._instance = object.__new__(Conexion)
            ref = _control(ruta)
            svc.guardar(ref, usuario=USUARIO, datos=placa.datos, nombre="placa.png", puntos=clics, parametros=_P(), capa="G", modo_piso="automatico")
            registro = svc.leer(ref)                                                                           # EL LECTOR
            assert "fwhm_inplane_mm" not in registro and registro["fwhm_crossplane_mm"] == oraculos["automatico"].valores["G"]["fwhm_crossplane_mm"]
            assert "fwhm_inplane_mm" not in " ".join(_columnas(ruta))
        finally:
            Conexion._instance = None
        # el control: con la lista entera los tres la llevan
        monkeypatch.undo()
        assert "fwhm_inplane_mm" in [m.nombre for m in med.MEDIDAS_GUARDADAS] and "fwhm_inplane_mm" in _svc().sql_insert()

    def test_agregar_un_valor_a_la_lista_agrega_su_columna_a_una_base_ya_creada(self, monkeypatch, tmp_path):
        """La migracion es aditiva e idempotente: una base creada con la lista de ayer recibe la columna de hoy, sin perder ni una fila."""
        med = _med()
        ayer = tuple(m for m in med.MEDIDAS_GUARDADAS if m.nombre != "desfase_inferior_mm")
        ruta = str(tmp_path / "ayer.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        with monkeypatch.context() as ayer_mp:
            ayer_mp.setattr(med, "MEDIDAS_GUARDADAS", ayer)
            Conexion._instance = None
            Conexion().con.close()
            Conexion._instance = None
        assert "desfase_inferior_mm" not in _columnas(ruta)
        ref = _control(ruta)
        _insertar(ruta, _fila_minima(ref))
        for _ in range(2):                                                                   # hoy (dos aperturas: idempotente)
            Conexion._instance = None
            Conexion().con.close()
            Conexion._instance = None
            columnas = _columnas(ruta)
            assert columnas.count("desfase_inferior_mm") == 1 and columnas[-1] == "desfase_inferior_mm"      # al final fisico (DP-80), una sola vez
        tipos = {c[1]: c[2] for c in _consulta(ruta, f"PRAGMA table_info('{TABLA}')")}
        assert tipos["desfase_inferior_mm"] == "REAL"                                        # con el tipo de la lista, no uno cualquiera
        assert _consulta(ruta, f"SELECT ref, estado, desfase_inferior_mm FROM {TABLA}") == [(ref, "ok", None)]

    def test_ningun_archivo_fuera_de_la_lista_escribe_el_nombre_de_una_medida(self):
        """Una operacion, una definicion: el nombre de lo que se guarda vive en `MEDIDAS_GUARDADAS`. Ni el servicio ni `conection.py` lo repiten en una cadena (los docstrings se ignoran)."""
        for ruta in (SERVICIO_PY, CONECTION_PY):
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            docstrings = {id(n.body[0].value) for n in ast.walk(arbol) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr)
                          and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)}
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in docstrings:
                    for nombre in MEDIDAS_DEL_PLAN[1:]:
                        assert nombre not in nodo.value, f"{ruta.name}:{nodo.lineno} escribe '{nombre}' a mano: sale de MEDIDAS_GUARDADAS"


# ====================================================================================================================== (f) el esquema

class TestLaTabla:
    def test_la_plantilla_trae_la_tabla_nueva_con_su_indice_unico(self, plantilla):
        """La base que la app crea (y el indice que crean la herramienta de migracion y las pruebas): sin D.1 la tabla no existe y el indice dice por que no se pudo crear."""
        assert _columnas(plantilla), f"{TABLA}: no existe (sin CREATE TABLE)"
        assert _consulta(plantilla, "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (nombre_indice(TABLA),)) == [(nombre_indice(TABLA),)]

    def test_nace_con_las_columnas_del_plan_en_su_orden_y_activo_al_final(self, bd_nueva):
        columnas = _columnas(bd_nueva)
        assert columnas, f"{TABLA}: no existe (sin CREATE TABLE)"
        assert columnas[0] == "id" and tuple(columnas[1:1 + len(COLUMNAS_DE_DATOS)]) == COLUMNAS_DE_DATOS
        assert columnas[-1] == "activo"          # DP-80: ALTER TABLE ADD COLUMN agrega siempre al final fisico; la tabla nace SIN `activo` y `_asegurar_activo_bloque_qc` lo agrega

    @pytest.mark.parametrize("columna", OBLIGATORIAS)
    def test_las_columnas_obligatorias_no_admiten_null(self, columna, bd):
        ref = _control(bd)
        fila = _fila_minima(ref)
        del fila[columna]
        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
            _insertar(bd, fila)

    def test_lo_demas_admite_null(self, bd):
        """La procedencia y las medidas numericas pueden faltar (un archivo sin resolucion declarada, una capa sin medir)."""
        _insertar(bd, _fila_minima(_control(bd)))
        fila = _consulta(bd, f"SELECT nombre_archivo, formato, bits, transparentes, dpi_declarado, clase_resolucion, tamano_pixel_mm, fwhm_crossplane_mm, fwhm_inplane_mm, desfase_izquierdo_mm,"
                             f" desfase_derecho_mm, desfase_superior_mm, desfase_inferior_mm, activo FROM {TABLA}")[0]
        assert fila == (None,) * 13 + (1,)

    @pytest.mark.parametrize("capa,valida", [("R", True), ("G", True), ("B", True), ("gris", False), ("r", False), ("", False), ("X", False)])
    def test_la_capa_solo_admite_r_g_o_b(self, capa, valida, bd):
        ref = _control(bd)
        if valida:
            _insertar(bd, _fila_minima(ref, capa=capa))
            assert _consulta(bd, f"SELECT capa FROM {TABLA}") == [(capa,)]
        else:
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                _insertar(bd, _fila_minima(ref, capa=capa))
            assert _consulta(bd, f"SELECT COUNT(*) FROM {TABLA}") == [(0,)]

    def test_ref_es_una_clave_foranea_a_controles_con_restrict(self, bd):
        claves = _consulta(bd, f"PRAGMA foreign_key_list('{TABLA}')")
        assert claves, f"{TABLA}: no existe (sin CREATE TABLE)"
        assert [(c[2], c[3], c[4], c[6]) for c in claves] == [("controles", "ref", "id", "RESTRICT")]

    @staticmethod
    def _ddl_en_memoria():
        """Una base en memoria con un `controles` minimo y un `Conexion` sin arranque (solo `.con`): el DDL de D.1 se corre TAL CUAL, sin el arranque de la app (que normaliza las FK y migra)."""
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE controles (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        return con, SimpleNamespace(con=con)

    def test_el_create_table_declara_por_si_mismo_restrict_en_la_clave_foranea(self):
        """La app normaliza a RESTRICT las FK de las tablas del contrato al abrir (`_asegurar_fk_on_delete_restrict`): el esquema FINAL no distingue un CREATE TABLE con CASCADE. Lo que D.1 declara tiene que
        ser correcto por si mismo y no por la correccion ajena (que ademas recrearia la tabla con un respaldo)."""
        con, falsa = self._ddl_en_memoria()
        try:
            Conexion.crearTablaAnalisisPlacaMensual(falsa)
            claves = con.execute(f"PRAGMA foreign_key_list('{TABLA}')").fetchall()
            assert [(c[2], c[3], c[4], c[6]) for c in claves] == [("controles", "ref", "id", "RESTRICT")]
        finally:
            con.close()

    def test_el_create_table_es_idempotente_por_si_mismo(self):
        """Cada apertura de la app lo vuelve a correr, y `__init_connection` TRAGA la excepcion de un CREATE TABLE que ya existe (`traceback.print_exc()`) dejando el resto del arranque sin correr."""
        con, falsa = self._ddl_en_memoria()
        try:
            Conexion.crearTablaAnalisisPlacaMensual(falsa)
            antes = con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (TABLA,)).fetchall()
            assert antes and antes[0][0]
            Conexion.crearTablaAnalisisPlacaMensual(falsa)
            assert con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (TABLA,)).fetchall() == antes
        finally:
            con.close()

    def test_una_columna_que_no_se_puede_agregar_se_avisa_y_no_corta_el_arranque_ni_las_demas_columnas(self, monkeypatch, capsys):
        """Cada columna de la migracion aditiva tiene su PROPIO intento: un fallo (la base ocupada, un disco de solo lectura) se avisa con el nombre de la columna y no deja sin correr ni el resto del arranque ni las
        columnas que siguen."""
        con, falsa = self._ddl_en_memoria()
        try:
            med = _med()
            ayer = tuple(m for m in med.MEDIDAS_GUARDADAS if m.nombre not in ("desfase_superior_mm", "desfase_inferior_mm"))
            with monkeypatch.context() as ayer_mp:
                ayer_mp.setattr(med, "MEDIDAS_GUARDADAS", ayer)
                Conexion.crearTablaAnalisisPlacaMensual(falsa)                            # la tabla con la lista de ayer
            intentos = []

            def _falla(cursor, tabla, columna, ddl):
                intentos.append(columna)
                raise sqlite3.OperationalError("database is locked")
            monkeypatch.setattr(conection_mod, "_asegurar_columna", _falla)
            capsys.readouterr()
            Conexion.crearTablaAnalisisPlacaMensual(falsa)                                # hoy: no lanza
            salida = capsys.readouterr().out
            assert intentos == ["desfase_superior_mm", "desfase_inferior_mm"], intentos      # el primer fallo no corta el segundo intento
            assert "desfase_superior_mm" in salida and "desfase_inferior_mm" in salida and "Aviso" in salida
        finally:
            con.close()

    @pytest.mark.parametrize("nombre", MEDIDAS_DEL_PLAN)
    def test_la_migracion_aditiva_deja_cada_columna_como_la_de_una_base_nueva_o_avisa_que_no_puede(self, nombre, monkeypatch, capsys):
        """R1-PRU-03: la promesa de la lista unica llega a las bases ya desplegadas -- una base creada con la lista de ayer (SIN ese valor) y abierta con la de hoy tiene la columna con el mismo tipo y la misma
        restriccion que una base nueva. Salvo una excepcion que impone SQLite: no agrega una columna NOT NULL (sin valor por omision) a una tabla ya creada, asi que un valor obligatorio (`admite_nulo=False`)
        queda admitiendo NULL en la base migrada; eso no puede pasar EN SILENCIO (dos esquemas distintos que nadie ve): se AVISA con el nombre de la columna. Se prueba con CADA valor de la lista, no con uno."""
        med = _med()
        hoy = med.MEDIDAS_GUARDADAS
        medida = next(m for m in hoy if m.nombre == nombre)
        nueva_con, nueva = self._ddl_en_memoria()
        vieja_con, vieja = self._ddl_en_memoria()
        try:
            Conexion.crearTablaAnalisisPlacaMensual(nueva)                                                    # una base NUEVA, con la lista de hoy
            with monkeypatch.context() as ayer_mp:
                ayer_mp.setattr(med, "MEDIDAS_GUARDADAS", tuple(m for m in hoy if m.nombre != nombre))
                Conexion.crearTablaAnalisisPlacaMensual(vieja)                                                # una base de AYER, sin ese valor
            capsys.readouterr()
            Conexion.crearTablaAnalisisPlacaMensual(vieja)                                                    # ... abierta con la lista de hoy (migracion aditiva)
            salida = capsys.readouterr().out
            columna = lambda con: {c[1]: (c[2], c[3]) for c in con.execute(f"PRAGMA table_info('{TABLA}')")}[nombre]          # (tipo, obligatoria)
            (tipo_nuevo, obligatoria_nueva), (tipo_viejo, obligatoria_vieja) = columna(nueva_con), columna(vieja_con)
            assert tipo_nuevo == tipo_viejo == medida.tipo and obligatoria_nueva == (0 if medida.admite_nulo else 1)
            if medida.admite_nulo:
                assert obligatoria_vieja == obligatoria_nueva and "Aviso" not in salida, (obligatoria_vieja, salida)
            else:
                assert obligatoria_vieja == 0 and "Aviso" in salida and nombre in salida, f"un valor obligatorio que la migracion no puede exigir se avisa: {salida!r}"
        finally:
            nueva_con.close()
            vieja_con.close()

    def test_una_fila_de_un_control_que_no_existe_se_rechaza(self, bd):
        con = sqlite3.connect(bd)
        try:
            con.execute("PRAGMA foreign_keys = ON")
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                _insertar(con, _fila_minima(99999))
        finally:
            con.close()

    def test_la_segunda_apertura_no_falla_ni_cambia_el_esquema(self, bd_nueva, monkeypatch, capsys):
        antes = _consulta(bd_nueva, "SELECT sql FROM sqlite_master WHERE name = ?", (TABLA,))
        assert antes and antes[0][0], f"{TABLA}: no existe (sin CREATE TABLE)"
        Conexion._instance.con.close()
        Conexion._instance = None
        capsys.readouterr()                                    # lo que imprimio la primera apertura no cuenta aqui
        Conexion().con.close()
        Conexion._instance = None
        salida = capsys.readouterr()
        assert "Traceback" not in salida.err + salida.out, salida.err[-800:]          # `__init_connection` traga la excepcion de un paso que falla (un CREATE TABLE no idempotente) y deja el resto del arranque sin correr
        assert _consulta(bd_nueva, "SELECT sql FROM sqlite_master WHERE name = ?", (TABLA,)) == antes
        Conexion()              # la fixture cierra la ultima


class TestEstaEnElContrato:
    def test_esta_en_tablas_anulables_y_su_clave_de_bloque_es_ref(self):
        assert TABLA in TABLAS_ANULABLES
        assert CLAVES_INDICE[TABLA] == ("ref",)

    def test_es_hija_de_controles_y_no_una_raiz(self, bd):
        """Hija (a diferencia de `braqui_posicion_inicial`): cuelga de `controles` por FK, asi que `RAICES_QC` no cambia y IV2 la ve en el cierre transitivo."""
        assert TABLA not in RAICES_QC
        con = sqlite3.connect(bd)
        try:
            assert TABLA in cierre_transitivo_fk(con, {"controles"})
        finally:
            con.close()

    def test_el_indice_unico_parcial_se_crea_y_es_idempotente(self, plantilla):
        assert crear_indices(plantilla)[TABLA] == "ya existía"
        sql = _consulta(plantilla, "SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (nombre_indice(TABLA),))[0][0]
        assert "UNIQUE" in sql.upper() and '"ref"' in sql and "activo" in sql           # unico y PARCIAL (solo vigentes)

    def test_dos_vigentes_del_mismo_control_se_rechazan_pero_las_anuladas_y_otros_controles_conviven(self, bd):
        a, b = _control(bd), _control(bd)
        _insertar(bd, _fila_minima(a))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            _insertar(bd, _fila_minima(a, imagen=b"otra"))
        _insertar(bd, _fila_minima(a, activo=0))
        _insertar(bd, _fila_minima(a, activo=0))
        _insertar(bd, _fila_minima(b))
        assert _consulta(bd, f"SELECT COUNT(*) FROM {TABLA}") == [(4,)]

    def test_la_capa_de_datos_del_visor_de_anulados_la_lista_bajo_controles_y_lee_su_imagen(self, bd):
        """El visor deriva sus secciones del grafo de FK: la tabla nueva aparece sola bajo `controles` (y la PANTALLA la ofrece en el combo «Tabla:» de esa seccion: SI tiene entrada) y su capa de datos
        entrega la imagen COMPLETA de cada version, byte por byte, con el tamano de una pelicula real (ML0, 2.8 MB). R1-PRU-04: la prueba usaba 5 KB y solo miraba que la columna existiera -- el nombre prometia
        leer la imagen y no la leia (truncar el BLOB a 100 bytes no la hacia caer). Lo que NO resuelve D.1 y queda a la decision del fisico: el visor (pantalla y capa de datos, zona ambar, DP-144) carga los BLOB
        de todas las filas como texto, y con imagenes de decenas de MB eso cuesta (3 filas de 44 MB: ~1.2 s y ~1 GB de pico al elegir la tabla, medido en la ronda 1 de D.1)."""
        ref = _control(bd)
        anulada, vigente = b"\x89PNG" + os.urandom(2_800_000), b"\xff\xd8" + os.urandom(2_800_000)
        _insertar(bd, _fila_minima(ref, imagen=anulada, activo=0))
        _insertar(bd, _fila_minima(ref, imagen=vigente))
        assert TABLA in visor.secciones()["controles"]
        columnas, filas = visor.filas_de(TABLA)
        assert "activo" not in columnas and "imagen" in columnas and sorted(f["estado"] for f in filas) == ["anulado", "vigente"]
        assert {f["estado"]: f["valores"][columnas.index("imagen")] for f in filas} == {"anulado": anulada, "vigente": vigente}          # la imagen ENTERA de cada version
        assert visor.filas_de(TABLA, "zzz-esto-no-esta-en-ninguna-columna")[1] == []                       # la busqueda recorre tambien el BLOB sin error y sin falsos aciertos
        assert len(visor.filas_de(TABLA, "G")[1]) == 2                                                     # y encuentra por la capa de las dos versiones


BD_REALES = [BD_QA, BD_A_AJUSTAR, BD_REBUILD_14_09, BD_REBUILD_21_09, BD_REBUILD_08_10]


def _censo_de_filas(ruta):
    con = sqlite3.connect(ruta)
    try:
        tablas = [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
    finally:
        con.close()


def _abrir_con_la_app(ruta, monkeypatch):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    Conexion().con.close()
    Conexion._instance = None


@pytest.mark.parametrize("origen", BD_REALES, ids=lambda p: p.name)
def test_ensayo_sobre_copia_de_una_bd_de_referencia(origen, tmp_path, monkeypatch, capsys):
    """Protocolo de esquema (DA-80, item 6): sobre COPIA (nunca la original), la app crea la tabla y nada mas cambia; `integrity_check` ok, `foreign_key_check` sin aumento, segunda corrida idempotente
    y el indice unico se crea sin saneamiento (la tabla es nueva). La comparacion contra la misma copia abierta con HEAD y las TRES de la produccion del 06-10 las hace `d1_ensayo_esquema.py`."""
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")
    ruta = str(tmp_path / "copia_real.db")
    shutil.copy(origen, ruta)
    antes = _censo_de_filas(ruta)
    assert TABLA not in antes, "la BD de referencia ya trae la tabla: el ensayo no probaria la creacion"
    fk_antes = len(_consulta(ruta, "PRAGMA foreign_key_check"))
    capsys.readouterr()
    _abrir_con_la_app(ruta, monkeypatch)
    primera = capsys.readouterr()
    assert "Traceback" not in primera.err + primera.out, primera.err[-800:]              # `__init_connection` traga la excepcion de un paso que falla: la unica senal es el Traceback impreso
    assert _consulta(ruta, "PRAGMA integrity_check") == [("ok",)]
    assert len(_consulta(ruta, "PRAGMA foreign_key_check")) <= fk_antes
    columnas = _columnas(ruta)
    assert columnas, f"{TABLA}: no existe (sin CREATE TABLE)"
    assert columnas[0] == "id" and columnas[-1] == "activo"
    despues = _censo_de_filas(ruta)
    assert despues.get(TABLA) == 0
    for tabla, n in antes.items():
        assert despues.get(tabla) == n, f"el censo de filas de '{tabla}' cambio: {n} -> {despues.get(tabla)}"
    assert crear_indices(ruta)[TABLA] == "creado"
    _abrir_con_la_app(ruta, monkeypatch)                                       # segunda corrida idempotente sobre la misma copia real
    segunda = capsys.readouterr()
    assert "Traceback" not in segunda.err + segunda.out, segunda.err[-800:]
    assert _censo_de_filas(ruta) == despues


# ====================================================================================================================== (a), (b) guardar -> leer

class TestGuardarYLeer:
    @pytest.mark.parametrize("capa", CAPAS)
    @pytest.mark.parametrize("modo", MODOS)
    def test_lo_guardado_es_lo_que_midio_el_motor_sobre_esos_bytes_de_ESA_capa(self, modo, capa, lectura, oraculos):
        registro = lectura(modo, capa)
        esperado = oraculos[modo].valores[capa]
        assert set(esperado) == set(MEDIDAS_DEL_PLAN)
        assert {nombre: registro[nombre] for nombre in MEDIDAS_DEL_PLAN} == esperado             # igualdad EXACTA (REAL de SQLite guarda el doble tal cual)
        assert registro["capa"] == capa
        assert esperado["estado"] == "ok" and all(esperado[n] is not None for n in MEDIDAS_DEL_PLAN[1:]), "la prueba necesita una capa medida de verdad"
        for otra in set(CAPAS) - {capa}:                                                         # y no las de otra capa: sobre esta pelicula las tres capas miden distinto
            assert oraculos[modo].valores[otra]["fwhm_crossplane_mm"] != esperado["fwhm_crossplane_mm"]

    @pytest.mark.parametrize("modo", MODOS)
    def test_el_piso_se_guarda_entero_con_el_modo_recibido_y_no_el_de_omision(self, modo, lectura, oraculos):
        registro = lectura(modo, "G")
        assert registro["piso"]["modo"] == modo and registro["piso"]["estado"] == "ok"
        assert _json(registro["piso"]) == _json(json.loads(_json(oraculos[modo].piso)))          # TODO el dict del piso, tal como lo da `Piso.como_dict()`
        if modo == "punto_manual":
            assert registro["piso"]["punto"] is not None and registro["piso"]["referencia_virgen"] is None
        if modo == "virgen":
            assert registro["piso"]["punto"] is None and registro["piso"]["referencia_virgen"] is not None
        if modo == "automatico":
            assert registro["piso"]["punto"] is None and registro["piso"]["referencia_virgen"] is None and len(registro["piso"]["esquinas"]) == 4

    def test_en_el_modo_virgen_la_copia_entera_de_la_referencia_viaja_con_el_analisis(self, lectura, virgen):
        copia = lectura("virgen", "B")["piso"]["referencia_virgen"]
        recuperada = _pel().referencia_virgen_desde_dict(copia)                               # es una referencia USABLE (con sus capas, region y huella)
        assert recuperada.estado == "ok" and {c: recuperada.valor(c) for c in ("R", "G", "B", "gris")} == {c: virgen.valor(c) for c in ("R", "G", "B", "gris")}
        assert copia["procedencia"]["sha256"] == virgen.procedencia["sha256"] and copia["pruebas"]

    @pytest.mark.parametrize("modo", MODOS)
    def test_el_fwhm_guardado_es_el_ancho_luminoso_mas_los_dos_desfases(self, modo, lectura, oraculos):
        """FWHM = ancho luminoso del motor en esa linea + desfase izquierdo + desfase derecho (y superior + inferior en el inplane), a 1e-9 mm, SOBRE LO GUARDADO."""
        for capa in CAPAS:
            registro = lectura(modo, capa)
            ancho = oraculos[modo].ancho_luz_mm
            assert ancho["crossplane"] is not None and ancho["inplane"] is not None
            assert abs(registro["fwhm_crossplane_mm"] - (ancho["crossplane"] + registro["desfase_izquierdo_mm"] + registro["desfase_derecho_mm"])) < 1e-9, capa
            assert abs(registro["fwhm_inplane_mm"] - (ancho["inplane"] + registro["desfase_superior_mm"] + registro["desfase_inferior_mm"])) < 1e-9, capa

    @pytest.mark.parametrize("modo", MODOS)
    def test_los_puntos_son_los_cinco_clics_y_sus_marcas_refinadas_como_los_da_el_motor(self, modo, lectura, oraculos, clics):
        puntos = lectura(modo, "G")["puntos"]
        assert puntos == oraculos[modo].marcas and len(puntos) == 5
        assert [tuple(p["clic"]) for p in puntos] == [tuple(float(v) for v in c) for c in clics]       # en el orden en que llegaron
        assert all(p["estado"] in ("refinada", "sin refinar") and "punto" in p for p in puntos)
        assert any(p["estado"] == "refinada" and p["punto"] != p["clic"] for p in puntos), "ninguna marca se refino: la prueba no distinguiria un clic de una marca"

    @pytest.mark.parametrize("modo", MODOS)
    def test_los_parametros_y_la_version_son_los_del_analisis(self, modo, lectura, oraculos):
        registro = lectura(modo, "G")
        assert _json(registro["parametros"]) == _json(json.loads(_json(oraculos[modo].parametros)))
        assert registro["version"] == oraculos[modo].version == _pm().VERSION_ALGORITMO

    def test_la_imagen_se_guarda_tal_cual_y_su_procedencia(self, lectura, placa, oraculos):
        registro = lectura("automatico", "G")
        assert registro["imagen"] == placa.datos and isinstance(registro["imagen"], bytes)
        assert registro["sha256"] == hashlib.sha256(placa.datos).hexdigest()
        assert registro["nombre_archivo"] == "placa.png"                                     # solo el nombre: no la carpeta del equipo de quien la subio
        assert (registro["formato"], registro["bits"], registro["transparentes"]) == ("PNG", 8, 0)
        assert registro["dpi_declarado"] == pytest.approx(600.0, abs=0.01) and registro["clase_resolucion"] == "coincide"
        assert registro["tamano_pixel_mm"] == pytest.approx(TAM) == oraculos["automatico"].tam_mm

    def test_la_procedencia_de_una_pelicula_con_zonas_transparentes_es_la_de_ese_archivo(self, bd, guardar, placa, clics):
        """`transparentes`, el formato y los bits son los de ESE archivo y no constantes: los pixeles con alfa 0 cuentan como «sin dato» y la base lo dice."""
        con_alfa = np.dstack([placa.imagen, np.full(placa.imagen.shape[:2], 255, np.uint8)])
        con_alfa[:, :40, 3] = 0                                                  # una tira transparente en el borde izquierdo, fuera del campo
        datos = gen.codificar(con_alfa, "png", 600)
        esperado = _oraculo(datos, clics, _P())
        assert esperado.transparentes > 0 and (esperado.formato, esperado.bits) == ("PNG", 8)
        ref = _control(bd)
        guardar(ref, datos=datos)
        registro = _svc().leer(ref)
        assert registro["transparentes"] == esperado.transparentes and (registro["formato"], registro["bits"]) == ("PNG", 8)
        assert registro["sha256"] == hashlib.sha256(datos).hexdigest() and {n: registro[n] for n in MEDIDAS_DEL_PLAN} == esperado.valores["G"]

    @pytest.mark.parametrize("dpi,clase", [(96, "editor"), (None, "sin_dato")])
    def test_la_resolucion_declarada_y_su_clase_son_las_del_archivo(self, dpi, clase, bd, guardar, placa, clics):
        """Paint reescribe la resolucion al recortar (96) y un archivo puede no declarar ninguna: la base guarda LO QUE EL ARCHIVO DECLARA y su clase; la escala sigue siendo la del procedimiento (600 dpi)."""
        if dpi is None:
            from PIL import Image
            salida = io.BytesIO()
            Image.fromarray(np.ascontiguousarray(placa.imagen[:, :, ::-1])).save(salida, format="PNG")         # sin `dpi=`: el PNG no trae la resolucion
            datos = salida.getvalue()
        else:
            datos = gen.codificar(placa.imagen, "png", dpi)
        esperado = _oraculo(datos, clics, _P())
        assert esperado.dpi is None if dpi is None else abs(esperado.dpi - dpi) < 0.1
        ref = _control(bd)
        guardar(ref, datos=datos)
        registro = _svc().leer(ref)
        assert registro["clase_resolucion"] == clase and registro["dpi_declarado"] == esperado.dpi
        assert registro["tamano_pixel_mm"] == pytest.approx(TAM) == esperado.tam_mm
        assert {n: registro[n] for n in MEDIDAS_DEL_PLAN} == esperado.valores["G"]

    def test_un_ref_entero_de_numpy_se_acepta_y_se_guarda_como_entero(self, bd, guardar):
        """El id de un control puede llegar de numpy (una tabla de pandas, un arreglo): es un entero y SQLite no sabe enlazar un `numpy.int64`, asi que el servicio lo vuelve entero de Python."""
        ref = _control(bd)
        nuevo = guardar(np.int64(ref))
        registro = _svc().leer(ref)
        assert registro["id"] == nuevo and registro["ref"] == ref and type(registro["ref"]) is int

    def test_un_archivo_sin_nombre_se_guarda_sin_nombre_y_el_nombre_con_carpeta_se_guarda_sin_ella(self, bd, guardar):
        sin_nombre, solo_espacios, con_barras = _control(bd), _control(bd), _control(bd)
        guardar(sin_nombre, nombre=None)
        guardar(solo_espacios, nombre="  ")
        guardar(con_barras, nombre="/home/fisico/escaneos/mensual/placa 1.tif")
        assert _svc().leer(sin_nombre)["nombre_archivo"] is None and _svc().leer(solo_espacios)["nombre_archivo"] is None
        assert _svc().leer(con_barras)["nombre_archivo"] == "placa 1.tif"
        detalles = {f[2]: f[3] for f in _auditoria(bd)}
        assert "sin nombre de archivo" in detalles[str(sin_nombre)] and "sin nombre de archivo" in detalles[str(solo_espacios)] and "placa 1.tif" in detalles[str(con_barras)]
        assert "/home" not in detalles[str(con_barras)]

    def test_el_tamano_del_pixel_es_el_de_la_escala_con_que_se_midio(self, bd, guardar, placa):
        """Lo guardado es `resultado.tam_mm` (25.4 / la resolucion del PROCEDIMIENTO de ese analisis), no una constante: con otro procedimiento (300 dpi) cambia, y los parametros guardados lo dicen."""
        P = _P()
        P["resolucion_escaneo_dpi"] = 300.0
        datos = gen.codificar(placa.imagen, "png", 300)
        ref = _control(bd)
        guardar(ref, datos=datos, parametros=P)
        registro = _svc().leer(ref)
        assert registro["dpi_declarado"] == pytest.approx(300.0, abs=0.1) and registro["clase_resolucion"] == "coincide"
        assert registro["tamano_pixel_mm"] == pytest.approx(25.4 / 300.0) and registro["tamano_pixel_mm"] != pytest.approx(TAM)
        assert registro["parametros"]["resolucion_escaneo_dpi"] == 300.0

    def test_quien_cuando_y_vigente(self, lectura, guardados):
        registro = lectura("automatico", "G")
        assert registro["usuario"] == USUARIO and registro["activo"] == 1 and registro["ref"] == guardados.refs[("automatico", "G")][0]
        assert abs((datetime.now() - datetime.strptime(registro["fecha_registro"], "%Y-%m-%d %H:%M:%S")).total_seconds()) < 600
        assert set(registro) == CLAVES_DE_LEER and registro["id"] == guardados.refs[("automatico", "G")][1]

    def test_guardar_devuelve_el_id_de_la_fila_vigente(self, lectura, guardados):
        for (modo, capa), (ref, nuevo) in guardados.refs.items():
            assert lectura(modo, capa)["id"] == nuevo

    def test_guardar_devuelve_el_id_de_la_fila_nueva_del_analisis_y_no_el_de_su_fila_de_auditoria(self, bd, guardar):
        """R1-PRU-02: en una base recien creada `audit_log` esta vacia y los ids del analisis y de la auditoria avanzaban juntos (1 y 1, 2 y 2...), asi que ninguna prueba distinguia el id que devuelve `guardar`
        del de su fila de auditoria. Las fixtures desalinean los dos contadores (siembran filas de auditoria ajenas) y aqui se comprueba que el id devuelto es el de la fila del ANALISIS."""
        assert _consulta(bd, "SELECT MAX(id) FROM audit_log")[0][0] >= 7, "la prueba necesita la auditoria desalineada del analisis (la fixture siembra filas ajenas)"
        for _ in range(3):              # y el id del analisis desalineado del NUMERO de filas: tres filas que se borran a mano dejan la secuencia (AUTOINCREMENT) por delante de la cuenta
            _sql(bd, f"DELETE FROM {TABLA} WHERE id = ?", (_insertar(bd, _fila_minima(_control(bd))),))
        assert _consulta(bd, f"SELECT COUNT(*) FROM {TABLA}") == [(0,)]
        ref = _control(bd)
        nuevo = guardar(ref)
        assert nuevo != _consulta(bd, f"SELECT COUNT(*) FROM {TABLA}")[0][0], "el id devuelto coincide con la cuenta de filas: la prueba no distinguiria un id de un conteo"
        id_del_analisis = _consulta(bd, f"SELECT id FROM {TABLA} WHERE ref = ?", (ref,))[0][0]
        id_de_la_auditoria = _consulta(bd, "SELECT id FROM audit_log WHERE tabla = ? AND ref = ?", (TABLA, str(ref)))[0][0]
        assert id_del_analisis != id_de_la_auditoria, "los dos ids siguen avanzando juntos: la prueba no distinguiria uno de otro"
        assert nuevo == id_del_analisis and nuevo != id_de_la_auditoria
        segundo = guardar(ref, capa="R")                                                                 # y al reguardar, el id nuevo es el de la fila nueva y no el de la anulada ni el de la auditoria
        assert segundo == _consulta(bd, f"SELECT id FROM {TABLA} WHERE ref = ? AND activo = 1", (ref,))[0][0] and segundo not in (nuevo, _consulta(bd, "SELECT MAX(id) FROM audit_log")[0][0])

    def test_un_control_sin_analisis_o_solo_con_anulados_no_tiene_registro(self, bd):
        sin = _control(bd)
        solo_anulado = _control(bd)
        _insertar(bd, _fila_minima(solo_anulado, activo=0))
        svc = _svc()
        assert svc.leer(sin) is None and svc.leer(solo_anulado) is None and svc.leer(99999) is None

    def test_leer_trae_la_vigente_y_no_la_anulada(self, bd):
        ref = _control(bd)
        _insertar(bd, _fila_minima(ref, capa="R", activo=0))
        vigente = _insertar(bd, _fila_minima(ref, capa="B"))
        registro = _svc().leer(ref)
        assert (registro["id"], registro["capa"], registro["activo"]) == (vigente, "B", 1)
        assert isinstance(registro["parametros"], dict) and registro["puntos"] == [] and registro["piso"] == {}

    @pytest.mark.parametrize("capa_guardada,omision", [("R", "B"), ("B", "R")])
    def test_cambiar_la_capa_por_omision_no_cambia_nada_de_lo_guardado_ni_de_lo_leido(self, capa_guardada, omision, bd, guardar, monkeypatch, oraculos):
        """La capa la elige el fisico y viaja con cada analisis (DA-85): `CAPA_POR_OMISION` es solo el valor con que arranca el menu y ningun PDF ni el servicio la lee."""
        monkeypatch.setattr(_pel(), "CAPA_POR_OMISION", omision)
        ref = _control(bd)
        guardar(ref, capa=capa_guardada)
        registro = _svc().leer(ref)
        assert registro["capa"] == capa_guardada
        assert {n: registro[n] for n in MEDIDAS_DEL_PLAN} == oraculos["automatico"].valores[capa_guardada]
        detalle = _auditoria(bd)[0][3]
        assert f"capa reportada {capa_guardada}" in detalle and f"Piso (capa {_pel().ADJETIVO_DE_LA_CAPA[capa_guardada]})" in detalle
        assert f"capa reportada {omision}" not in detalle and f"Piso (capa {_pel().ADJETIVO_DE_LA_CAPA[omision]})" not in detalle

    def test_una_pelicula_real_de_la_clinica_se_guarda_y_se_lee_igual_que_la_mide_el_motor(self, bd):
        ruta = _corpus.pelicula("ML0")
        if ruta is None:
            pytest.skip("HI-0: la pelicula real ML0 no esta (ImagenesDeReferencia/PlacasHistoricas)")
        datos = Path(ruta).read_bytes()
        esperado = _oraculo(datos, CLICS_ML0, _P())
        assert esperado.estado == "ok"
        ref = _control(bd)
        _svc().guardar(ref, usuario=USUARIO, datos=datos, nombre="ML0.JPG", puntos=CLICS_ML0, parametros=_P(), capa="G", modo_piso="automatico")
        registro = _svc().leer(ref)
        assert {n: registro[n] for n in MEDIDAS_DEL_PLAN} == esperado.valores["G"] and registro["imagen"] == datos
        assert (registro["formato"], registro["bits"]) == ("JPEG", 8) and registro["puntos"] == esperado.marcas

    def test_un_tiff_de_16_bits_de_decenas_de_megabytes_se_guarda_y_se_lee_byte_por_byte(self, bd):
        """P12: la imagen ORIGINAL tal cual (un TIFF de 16 bits de una pelicula completa pesa ~40 MB; ML0 2.8 MB): el BLOB se guarda y vuelve identico."""
        grande = gen.generar("tiff", bits=16, variante="A", seed=3)
        assert len(grande.datos) > 30_000_000
        ref = _control(bd)
        _svc().guardar(ref, usuario=USUARIO, datos=grande.datos, nombre="gran_tiff.tif", puntos=grande.verdad.clics_del_cuaderno(), parametros=_P(), capa="G", modo_piso="automatico")
        registro = _svc().leer(ref)
        assert registro["imagen"] == grande.datos and registro["sha256"] == hashlib.sha256(grande.datos).hexdigest()
        assert (registro["formato"], registro["bits"]) == ("TIFF", 16) and registro["estado"] == "ok"

    def test_un_registro_viejo_con_una_capa_no_medible_se_sigue_leyendo_recalculando_y_comparando(self, bd, guardar, monkeypatch):
        """D.1b (20-10-2026) revierte D1-D3: una capa no medible ya NO se guarda. Un registro de ANTES (aqui se fabrica quitando la regla para UN guardado, como guardaba D.1) se sigue leyendo con su estado y
        los numeros vacios (nunca ceros: S12), y recalcularlo da cero diferencias: `leer`, `recalcular` y `diferencias` no dependen de la regla. Hoy ese mismo analisis no se podria volver a guardar."""
        svc = _svc()
        ref = _control(bd)
        with monkeypatch.context() as sin_la_regla:
            sin_la_regla.setattr(svc, "motivo_para_no_guardar", lambda resultado, capa: None)
            guardar(ref, capa="G", parametros=_rango_imposible())
        registro = svc.leer(ref)
        assert registro["estado"].startswith("no medible") and "rango" in registro["estado"]
        assert all(registro[n] is None for n in MEDIDAS_DEL_PLAN[1:])
        assert registro["piso"]["estado"].startswith("no medible")
        resultado = svc.recalcular(registro)
        assert svc.diferencias(registro, resultado) == []
        assert svc.motivo_para_no_guardar(resultado, "G") == MENSAJE_NO_MEDIBLE.format(capa="verde", estado=registro["estado"])


# ====================================================================================================================== D.1b: una capa NO medible no se guarda (decision del fisico del 20-10-2026)

# El texto del rechazo, escrito aqui a mano a proposito (el ancla EXTERNA de `motivo_para_no_guardar`): dice que la capa no es medible, que no se guarda sea cual sea el motivo, y el estado del motor tal cual.
MENSAJE_NO_MEDIBLE = "la capa {capa} no es medible y no se guarda, sea cual sea el motivo; el análisis dice «{estado}»"


def _rango_imposible():
    """Los parametros de fabrica con un rango del piso en que ningun piso real cae: el piso automatico es «no medible» (el caso del test de D1-D3)."""
    P = _P()
    P["piso_esperado"] = {"R": [200.0, 250.0], "G": [200.0, 250.0], "B": [200.0, 250.0], "gris": [200.0, 250.0]}
    return P


@pytest.fixture(scope="module")
def recortada(placa, clics):
    """La pelicula «cortada»: recortada a 3 mm del campo LUMINOSO por los cuatro lados. Sin pelicula en las esquinas el piso automatico no es medible; con la pelicula virgen como piso la roja pierde sus
    bordes al 50 % (salen de la pelicula) y la verde y la azul se miden con penumbras incompletas (medido en D.1b: logs/D1b/v1_hechos.log, casos c2 y c2v). Devuelve (bytes, los cinco clics desplazados)."""
    cx, cy = placa.verdad.centro_campo_px
    luz = placa.verdad.bordes_luz
    x0, x1 = int(round(cx + (luz["L"] - 3.0) / TAM)), int(round(cx + (luz["R"] + 3.0) / TAM))
    y0, y1 = int(round(cy + (luz["T"] - 3.0) / TAM)), int(round(cy + (luz["B"] + 3.0) / TAM))
    return gen.codificar(np.ascontiguousarray(placa.imagen[y0:y1, x0:x1]), "png", 600), [(c[0] - x0, c[1] - y0) for c in clics]


# cada causa por la que la capa elegida no es medible y que D.1 GUARDABA igual (con su estado y los numeros vacios): (capa, modo del piso, lo que cambia en `guardar`)
CAUSAS_NO_MEDIBLES = ("piso fuera del rango esperado", "modo virgen sin pelicula virgen", "sexto clic sobre pelicula irradiada", "pelicula cortada, piso automatico sin esquinas",
                      "pelicula cortada, la roja con sus bordes fuera de la pelicula")


def _causa(nombre, placa, recortada):
    cx, cy = placa.verdad.centro_campo_px
    datos, cl = recortada
    return {
        "piso fuera del rango esperado": ("G", "automatico", dict(parametros=_rango_imposible())),
        "modo virgen sin pelicula virgen": ("G", "virgen", dict(referencia_virgen=None)),
        "sexto clic sobre pelicula irradiada": ("G", "punto_manual", dict(punto_manual=(float(round(cx + 20 / TAM)), float(round(cy + 20 / TAM))))),
        "pelicula cortada, piso automatico sin esquinas": ("G", "automatico", dict(datos=datos, puntos=cl)),
        "pelicula cortada, la roja con sus bordes fuera de la pelicula": ("R", "virgen", dict(datos=datos, puntos=cl)),
        "puntos que no forman el campo": ("G", "automatico", dict(puntos=[(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)])),
        "otra resolucion declarada": ("G", "automatico", dict(datos=gen.codificar(placa.imagen, "png", 300))),
        "medible": ("G", "automatico", {}),
    }[nombre]


def _resultado_de(argumentos):
    """El `ResultadoPlacaMensual` que el MOTOR da con los argumentos de `guardar` (lo que la ventana tendra en mano antes de ofrecer «Guardar»)."""
    pm, pel = _pm(), _pel()
    pelicula = pel.leer_pelicula(argumentos["datos"])
    P = argumentos["parametros"]
    tam = pel.escala_mm(pelicula.dpi, P)
    marcas = [pm.refinar_marca(pelicula.gris, clic, P, tam, pelicula.validos) for clic in argumentos["puntos"]]
    return pm.analizar(pelicula, marcas, P, modo_piso=argumentos["modo_piso"], punto_manual=argumentos.get("punto_manual"), referencia_virgen=argumentos.get("referencia_virgen"))


# --- RONDA 1 DE LA REVISION DE D.1b (hallazgos P-01, P-02 y P-03 / D1b-PROD-R1-01): la pelicula cortada por UN solo lado y el rechazo sin piso con una capa que no es la verde.
# La regla juzga la capa ELEGIDA y sus DOS perfiles. Ni los escenarios de `CAUSAS_NO_MEDIBLES` ni `test_se_juzga_la_capa_elegida_...` lo distinguian: en ellos la capa que falla falla en el crossplane o en los dos
# perfiles, y la verde y la azul siempre comparten estado; la rama SIN piso solo se probaba con la verde. Una regla que mirara un solo perfil, una que cruzara la verde con la azul o una rama sin piso que nombrara
# siempre la verde pasaban el archivo entero (206 casos). Las dos escenas se fabrican recortando la pelicula sintetica de PF.0 (independiente del motor) a `u` mm del centro del campo de radiacion, en el MEDIO
# del intervalo donde se cumplen (medido con pasos de 0.05 a 0.1 mm en logs/D1b/correccion_ronda1/escenas_afinadas.log: derecha de 51.3 a 51.6 mm, arriba de 52.0 a 52.6 mm; margen de 0.15 mm = 3 pixeles o mas a cada lado).
ESCENAS_DE_UN_SOLO_LADO = {"derecha": 51.45, "arriba": 52.3}
# El nombre de cada capa tal como lo dice el rechazo, escrito a mano a proposito (el ancla EXTERNA de `ADJETIVO_DE_LA_CAPA`: si el servicio nombrara siempre la verde, el texto de la roja y el de la azul no coincidirian).
ADJETIVO_A_MANO = {"R": "roja", "G": "verde", "B": "azul"}


@pytest.fixture(scope="module")
def cortadas(placa, clics):
    """Las dos escenas de la pelicula cortada por UN solo lado (`ESCENAS_DE_UN_SOLO_LADO`) y lo que el MOTOR dice de cada capa en ellas: {escena: SimpleNamespace(datos, puntos, perfiles, valores)}. `perfiles[capa]` es
    (crossplane medido, inplane medido); `valores[capa]` es `valores_medidos` (el estado literal y los seis numeros). Las premisas son `assert`, nunca un `skip`: si el motor cambia y la escena deja de ser la que las
    pruebas necesitan, falla aqui diciendo cual era la premisa. Se guardan solo los numeros: ningun resultado completo (con sus arreglos) queda vivo en el modulo."""
    pm = _pm()
    cx, cy = placa.verdad.centro_campo_px
    escenas = {}
    for escena, u in ESCENAS_DE_UN_SOLO_LADO.items():
        if escena == "derecha":
            corte, puntos = placa.imagen[:, :int(round(cx + u / TAM))], list(clics)
        else:
            y0 = max(0, int(round(cy - u / TAM)))
            corte, puntos = placa.imagen[y0:, :], [(c[0], c[1] - y0) for c in clics]
        datos = gen.codificar(np.ascontiguousarray(corte), "png", 600)
        resultado = _resultado_de(dict(datos=datos, puntos=puntos, parametros=_P(), modo_piso="automatico"))
        escenas[escena] = SimpleNamespace(datos=datos, puntos=puntos, perfiles={c: (resultado.capas[c].crossplane.ok, resultado.capas[c].inplane.ok) for c in CAPAS},
                                          valores={c: pm.valores_medidos(resultado, c) for c in CAPAS})
    assert escenas["derecha"].perfiles == {"R": (False, True), "G": (False, True), "B": (True, True)}, (
        "la premisa de la escena «derecha»: la roja y la verde pierden su perfil crossplane (el inplane se mide) y la azul se mide entera", escenas["derecha"].perfiles)
    assert escenas["arriba"].perfiles == {"R": (True, False), "G": (True, True), "B": (True, True)}, (
        "la premisa de la escena «arriba»: la roja pierde su perfil inplane (el crossplane se mide) y la verde y la azul se miden enteras", escenas["arriba"].perfiles)
    return escenas


class TestUnaCapaNoMedibleNoSeGuarda:
    """D.1b. Decision del fisico (20-10-2026), que revierte D1-D3: «que se rechace el guardado de la capa que es no medible con el comentario de que es no medible por cualquier motivo». La regla es UNA
    funcion (`motivo_para_no_guardar`), que usa `guardar` y usara la ventana (E.1) antes de ofrecer «Guardar»; va despues de armar la fila (lo que no cabe en JSON se dice como tal) y ANTES de W1 y de la
    transaccion: el rechazo no escribe, no audita ni anula el vigente. Medible = el estado de ESA capa es «ok» (sus dos perfiles medidos: los dos FWHM y los cuatro desfases existen; medido en D.1b sobre 69
    analisis, 185 capas «ok» con los seis numeros y 91 no «ok» con al menos uno vacio); una penumbra incompleta no la vuelve no medible (la penumbra no se guarda)."""

    @pytest.mark.parametrize("causa", CAUSAS_NO_MEDIBLES)
    def test_cada_causa_se_rechaza_sin_escribir_ni_auditar_y_dice_por_que(self, causa, bd, guardar, placa, clics, punto_manual, virgen, recortada):
        capa, modo, cambios = _causa(causa, placa, recortada)
        estado = _pm().valores_medidos(_resultado_de(_argumentos(placa, clics, punto_manual, virgen, capa, modo, **cambios)), capa)["estado"]
        assert estado.startswith("no medible"), (causa, estado)                    # la premisa: el MOTOR dice que esa capa no es medible
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError) as error:
            guardar(ref, capa=capa, modo=modo, **cambios)
        assert type(error.value) is _svc().PlacaMensualError
        assert str(error.value) == MENSAJE_NO_MEDIBLE.format(capa=_pel().ADJETIVO_DE_LA_CAPA[capa], estado=estado)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_se_juzga_la_capa_elegida_y_no_otra_ni_la_raiz(self, bd, guardar, virgen, recortada):
        datos, cl = recortada
        o = _oraculo(datos, cl, _P(), "virgen", referencia=virgen)
        assert o.estado == "ok" and o.valores["R"]["estado"].startswith("no medible") and o.valores["G"]["estado"] == "ok" == o.valores["B"]["estado"], "la prueba necesita una capa si y otra no"
        roja, verde, azul = _control(bd), _control(bd), _control(bd)
        with pytest.raises(_svc().PlacaMensualError, match="^la capa roja no es medible"):
            guardar(roja, capa="R", modo="virgen", datos=datos, puntos=cl)
        guardar(verde, capa="G", modo="virgen", datos=datos, puntos=cl)
        guardar(azul, capa="B", modo="virgen", datos=datos, puntos=cl)
        assert _svc().leer(roja) is None
        for ref, capa in ((verde, "G"), (azul, "B")):
            assert {n: _svc().leer(ref)[n] for n in MEDIDAS_DEL_PLAN} == o.valores[capa]
        assert [f[2] for f in _auditoria(bd)] == [str(verde), str(azul)]

    def test_una_penumbra_incompleta_no_vuelve_no_medible_la_capa(self, bd, guardar, virgen, recortada):
        """«como con las penumbras»: la penumbra incompleta dice su motivo (un aviso) y no se guarda; la capa sigue siendo medible y se guarda con sus seis numeros. Las diez peliculas reales traen la roja
        con 2 a 4 penumbras incompletas y la verde de ML0, EPSON030 y EPSON028 con una (D.1b, logs/D1b/v1_hechos.log): si la penumbra contara, no se guardaria la roja de ninguna."""
        datos, cl = recortada
        resultado = _resultado_de(dict(datos=datos, puntos=cl, parametros=_P(), modo_piso="virgen", referencia_virgen=virgen))
        verde = resultado.capas["G"]
        penumbras = verde.crossplane.penumbras_mm + verde.inplane.penumbras_mm
        assert verde.estado == "ok" and None in penumbras and any(a.startswith("incompleta") for a in verde.crossplane.avisos + verde.inplane.avisos), "la prueba necesita una penumbra incompleta"
        assert _svc().motivo_para_no_guardar(resultado, "G") is None
        ref = _control(bd)
        guardar(ref, capa="G", modo="virgen", datos=datos, puntos=cl)
        registro = _svc().leer(ref)
        assert registro["estado"] == "ok" and all(registro[n] is not None for n in MEDIDAS_DEL_PLAN[1:])

    def test_un_reguardado_no_medible_deja_el_analisis_vigente_intacto_y_no_audita(self, bd, guardar):
        ref = _control(bd)
        vigente = guardar(ref, capa="G")
        antes, auditoria = _consulta(bd, f"SELECT * FROM {TABLA}"), _auditoria(bd)
        with pytest.raises(_svc().PlacaMensualError, match="^la capa azul no es medible"):
            guardar(ref, capa="B", parametros=_rango_imposible())
        assert _consulta(bd, f"SELECT * FROM {TABLA}") == antes and _filas(bd) == [(vigente, ref, 1, "G")]
        assert _auditoria(bd) == auditoria and len(auditoria) == 1
        assert _svc().leer(ref)["id"] == vigente

    @pytest.mark.parametrize("control", ["anulado", "inexistente"])
    def test_con_el_control_anulado_la_capa_no_medible_se_dice_antes_que_w1(self, bd, guardar, control):
        """La regla mira lo medido y va ANTES de W1, que sigue justo antes de la transaccion (D1-D8): un control anulado o inexistente con una capa no medible dice que la capa no es medible; con una capa medible, W1."""
        ref, w1 = (_control(bd, activo=0), "anulado") if control == "anulado" else (99999, "no existe")
        with pytest.raises(_svc().PlacaMensualError) as error:
            guardar(ref, parametros=_rango_imposible())
        assert type(error.value) is _svc().PlacaMensualError and str(error.value).startswith("la capa verde no es medible")
        with pytest.raises(_svc().ControlNoEditable, match=w1):
            guardar(ref)
        assert _filas(bd) == [] and _auditoria(bd) == []

    @pytest.mark.parametrize("causa", CAUSAS_NO_MEDIBLES + ("puntos que no forman el campo", "otra resolucion declarada", "medible"))
    def test_la_ventana_tiene_la_misma_regla_y_el_mismo_texto_que_guardar(self, causa, bd, guardar, placa, clics, punto_manual, virgen, recortada):
        """E.1 llamara a `motivo_para_no_guardar(resultado, capa)` con SU analisis antes de ofrecer «Guardar»: da None exactamente cuando `guardar` guarda y, si no, el texto con que `guardar` rechaza
        (tambien sin piso: los puntos que no forman el campo y otra resolucion)."""
        capa, modo, cambios = _causa(causa, placa, recortada)
        motivo = _svc().motivo_para_no_guardar(_resultado_de(_argumentos(placa, clics, punto_manual, virgen, capa, modo, **cambios)), capa)
        assert (motivo is None) == (causa == "medible"), (causa, motivo)
        ref = _control(bd)
        if motivo is None:
            guardar(ref, capa=capa, modo=modo, **cambios)
            assert _svc().leer(ref)["estado"] == "ok"
        else:
            with pytest.raises(_svc().PlacaMensualError) as error:
                guardar(ref, capa=capa, modo=modo, **cambios)
            assert str(error.value) == motivo
            assert _filas(bd) == [] and _auditoria(bd) == []

    @pytest.mark.parametrize("escena,capa,perfil", [("arriba", "R", "inplane"), ("derecha", "G", "crossplane")],
                             ids=["solo el inplane: la roja con la pelicula cortada por arriba", "solo el crossplane: la verde con la pelicula cortada por la derecha"])
    def test_una_capa_con_solo_uno_de_sus_dos_perfiles_medidos_no_se_guarda(self, escena, capa, perfil, bd, guardar, cortadas):
        """P-01 (ronda 1): medible = los DOS perfiles de la capa medidos (D1b-D2), no uno. A la capa le falta UN solo perfil y del otro SI hay numeros (los que una regla mas floja se llevaria a la base): no se guarda,
        no se audita, y el texto es el de la regla con el estado literal del motor. Una regla que mire solo el crossplane (M8) deja pasar la roja de «arriba»; una que mire solo el inplane (M9), la verde de «derecha»."""
        e = cortadas[escena]
        assert dict(zip(("crossplane", "inplane"), e.perfiles[capa])) == {"crossplane": perfil != "crossplane", "inplane": perfil != "inplane"}, ("la premisa: a esa capa le falta UN solo perfil", perfil, e.perfiles[capa])
        assert e.valores[capa]["estado"].startswith("no medible") and any(e.valores[capa][n] is not None for n in MEDIDAS_DEL_PLAN[1:]), "la premisa: no medible, pero con numeros del perfil que si se midio"
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError) as error:
            guardar(ref, capa=capa, datos=e.datos, puntos=e.puntos)
        assert type(error.value) is _svc().PlacaMensualError
        assert str(error.value) == MENSAJE_NO_MEDIBLE.format(capa=ADJETIVO_A_MANO[capa], estado=e.valores[capa]["estado"])
        assert _filas(bd) == [] and _auditoria(bd) == []

    @pytest.mark.parametrize("capa", CAPAS)
    def test_cada_capa_se_juzga_por_lo_suyo_con_la_pelicula_cortada_por_la_derecha(self, capa, bd, guardar, cortadas):
        """P-02 (ronda 1): con la pelicula terminando a 51.45 mm por la derecha el MOTOR separa a la azul (medible) de la roja y la verde (no medibles). La roja y la verde se rechazan, nombrando cada una la SUYA; la azul
        se guarda con sus seis numeros. Una regla que juzgue la verde por la azul y la azul por la verde (M1) guarda la verde que no se midio y rechaza la azul que si; antes ninguna prueba tenia una verde y una azul con
        estados distintos."""
        e = cortadas["derecha"]
        se_guarda = {"R": False, "G": False, "B": True}[capa]
        assert (e.valores[capa]["estado"] == "ok") == se_guarda, ("la premisa: el motor separa la azul de la roja y la verde", capa, e.valores[capa]["estado"])
        ref = _control(bd)
        if se_guarda:
            nuevo = guardar(ref, capa=capa, datos=e.datos, puntos=e.puntos)
            registro = _svc().leer(ref)
            assert registro["id"] == nuevo and registro["capa"] == capa and {n: registro[n] for n in MEDIDAS_DEL_PLAN} == e.valores[capa]
            assert _filas(bd) == [(nuevo, ref, 1, capa)] and [f[2] for f in _auditoria(bd)] == [str(ref)]
        else:
            with pytest.raises(_svc().PlacaMensualError) as error:
                guardar(ref, capa=capa, datos=e.datos, puntos=e.puntos)
            assert type(error.value) is _svc().PlacaMensualError
            assert str(error.value) == MENSAJE_NO_MEDIBLE.format(capa=ADJETIVO_A_MANO[capa], estado=e.valores[capa]["estado"])
            assert _filas(bd) == [] and _auditoria(bd) == []

    @pytest.mark.parametrize("capa", CAPAS)
    @pytest.mark.parametrize("causa", ["puntos que no forman el campo", "otra resolucion declarada"])
    def test_el_rechazo_de_un_analisis_sin_piso_nombra_la_capa_elegida(self, causa, capa, bd, guardar, placa, clics, punto_manual, virgen, recortada):
        """P-03 / D1b-PROD-R1-01 (ronda 1): el rechazo de la rama SIN piso (los puntos no forman el campo, el archivo declara otra resolucion: `resultado.piso is None`) nombra la capa ELEGIDA, la roja, la verde o la
        azul, y trae el estado del motor tal cual: es el texto que la ventana (E.1) le copiara al fisico para decirle por que no puede guardar. Antes solo se probaba con la verde: una rama que nombrara siempre la
        verde (M2p) le habria dicho «la capa verde» a quien eligio la roja."""
        _, modo, cambios = _causa(causa, placa, recortada)
        resultado = _resultado_de(_argumentos(placa, clics, punto_manual, virgen, capa, modo, **cambios))
        assert resultado.piso is None, "la premisa: este analisis ni llega a tomar el piso (la rama SIN piso de `guardar`)"
        estado = _pm().valores_medidos(resultado, capa)["estado"]
        assert estado.startswith({"puntos que no forman el campo": "no medible: los puntos no forman el campo", "otra resolucion declarada": "no medible: no hay escala en milímetros"}[causa]), (causa, estado)
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError) as error:
            guardar(ref, capa=capa, modo=modo, **cambios)
        assert type(error.value) is _svc().PlacaMensualError
        assert str(error.value) == MENSAJE_NO_MEDIBLE.format(capa=ADJETIVO_A_MANO[capa], estado=estado)
        assert _filas(bd) == [] and _auditoria(bd) == []


# ====================================================================================================================== lo que se rechaza ANTES de escribir

class TestRechazaSinEscribirNada:
    CASOS = {
        "sin usuario": dict(usuario="  "),
        "usuario ausente": dict(usuario=None),
        "capa gris": dict(capa="gris"),
        "capa en minuscula": dict(capa="g"),
        "capa ausente": dict(capa=None),
        "modo que no existe": dict(modo_piso="al_azar"),
        "modo ausente": dict(modo_piso=None),
        "imagen vacia": dict(datos=b""),
        "imagen que no es bytes": dict(datos="texto"),
        "bytes que no son una imagen": dict(datos=b"esto no es una pelicula"),
        "cuatro puntos": dict(puntos=[(1, 1), (2, 2), (3, 3), (4, 4)]),
        "puntos que no son pares": dict(puntos=[1, 2, 3, 4, 5]),
        "puntos ausentes": dict(puntos=None),
        "parametros ausentes": dict(parametros=None),
        "parametros incompletos": dict(parametros={"banda_perfil_mm": 1.0}),
        "un punto marcado sin el modo punto_manual": dict(punto_manual=(87.0, 87.0)),
    }

    @pytest.mark.parametrize("caso", sorted(CASOS))
    def test_rechaza_con_su_error_y_no_escribe_ni_audita_nada(self, caso, bd, guardar):
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError):
            guardar(ref, **self.CASOS[caso])
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_la_tabla_de_casos_rechazados_no_esta_vacia(self):
        assert len(self.CASOS) >= 15

    @pytest.mark.parametrize("cuantos", [0, 4, 6])
    def test_los_cinco_puntos_los_exige_el_servicio_con_su_propio_mensaje(self, cuantos, bd, guardar):
        """No se le deja al motor decir que faltan o sobran puntos: el servicio lo dice ANTES de leer la imagen, con las palabras del plan."""
        ref = _control(bd)
        puntos = [(100.0 + 50 * i, 100.0 + 30 * i) for i in range(cuantos)]
        with pytest.raises(_svc().PlacaMensualError, match="hacen falta los cinco puntos"):
            guardar(ref, puntos=puntos)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_si_la_lista_pide_un_valor_que_el_motor_no_entrega_no_se_guarda_nada_y_se_dice_cual(self, bd, guardar, monkeypatch):
        """La lista y el motor se mantienen de acuerdo (una prueba estatica lo fija); si alguna vez divergen, el servicio lo dice con el nombre del valor y no escribe nada (en vez de un KeyError a mitad)."""
        med = _med()
        monkeypatch.setattr(med, "MEDIDAS_GUARDADAS", med.MEDIDAS_GUARDADAS + (med.MedidaGuardada("penumbra_inventada_mm", "mm", "REAL"),))
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError, match="penumbra_inventada_mm"):
            guardar(ref)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_a_los_parametros_les_falta_una_clave_que_pide_el_analisis_y_el_servicio_dice_cual(self, bd, guardar):
        """Los parametros se guardan y al reabrir se recalcula con ESOS: un diccionario al que le falta una clave del motor no se guarda a medias. El mensaje es el del servicio (no el del motor, que tambien lo diria
        pero DESPUES de leer y refinar la imagen)."""
        ref = _control(bd)
        claves = sorted(set(_pm().CLAVES_QUE_PIDE_ANALIZAR + _pm().CLAVES_DE_LA_MARCA))
        assert len(claves) >= 20, "la prueba necesita las claves de verdad"
        for clave in claves:
            P = _P()
            del P[clave]
            with pytest.raises(_svc().PlacaMensualError, match=rf"a los parámetros les faltan.*{re.escape(clave)}"):
                guardar(ref, parametros=P)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_a_los_parametros_les_falta_una_clave_del_piso_y_el_servicio_la_exige_en_vez_de_guardarlos_incompletos(self, bd, guardar):
        """D1-PROD-02: `guardar` solo exigia las 22 claves que `analizar` y la marca leen por nombre; el motor rellena cualquiera de las otras 18 (el piso, el margen del campo...) con el valor de HOY. Un
        diccionario sin ellas se guardaba a medias (39 de 40 claves en `parametros`) y, si ese valor cambiaba sin subir `VERSION_ALGORITMO`, lo guardado dejaba de reproducirse al reabrir (15 diferencias y «no
        medible»). El docstring dice «todos los de VALORES_DE_LA_GEOMETRIA» y «rechaza parametros incompletos»: se exige el diccionario ENTERO, la copia guardada manda (DA-81)."""
        ref = _control(bd)
        del_analisis = set(_pm().CLAVES_QUE_PIDE_ANALIZAR + _pm().CLAVES_DE_LA_MARCA)
        del_piso = sorted(set(_pm().VALORES_DE_LA_GEOMETRIA) - del_analisis)
        assert len(del_piso) >= 10 and "margen_campo_mm" in del_piso, "la prueba necesita las claves de verdad (las que el motor rellena con el valor de hoy)"
        for clave in del_piso:
            P = _P()
            del P[clave]
            with pytest.raises(_svc().PlacaMensualError, match=rf"a los parámetros les faltan.*{re.escape(clave)}"):
                guardar(ref, parametros=P)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_lo_guardado_en_parametros_es_el_diccionario_completo_y_recalcular_no_depende_de_los_defaults_de_hoy(self, bd, guardar, monkeypatch):
        """D1-PROD-02, la otra mitad: lo que se guarda en `parametros` son TODAS las claves con que se midio (tambien las del piso), de modo que cambiar un valor por omision del motor despues de guardar (una version
        futura que olvidara subir `VERSION_ALGORITMO`) no mueve lo reabierto: `recalcular` da cero diferencias."""
        ref = _control(bd)
        guardar(ref)
        registro = _svc().leer(ref)
        assert set(registro["parametros"]) >= set(_pm().VALORES_DE_LA_GEOMETRIA)
        clave = "margen_campo_mm"
        monkeypatch.setitem(_pel().VALORES_DEL_PISO, clave, registro["parametros"][clave] + 3.0)
        assert _pel().VALORES_DEL_PISO[clave] != registro["parametros"][clave], "la prueba necesita un default de hoy distinto del guardado"
        assert _svc().diferencias(registro, _svc().recalcular(registro)) == []

    @pytest.mark.parametrize("punto", [(float("nan"), float("nan")), (float("inf"), float("inf")), (float("nan"), 3.0), (-float("inf"), 0.0)], ids=["nan_nan", "inf_inf", "nan_x", "menos_inf_cero"])
    def test_un_punto_marcado_no_finito_se_rechaza_y_no_deja_un_json_invalido_en_la_base(self, punto, bd, guardar):
        """D1-PROD-03: el sexto clic con NaN o infinito pasaba (el motor lo da por «el punto no esta sobre pelicula») y `json.dumps` escribia el literal `NaN` o `Infinity` en la columna `piso`, que la tabla documenta
        como JSON: `json_valid(piso)` daba 0 y la fila se auditaba como guardada."""
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError, match="piso"):
            guardar(ref, modo="punto_manual", punto_manual=punto)
        assert _filas(bd) == [] and _auditoria(bd) == []

    @pytest.mark.parametrize("clave,valor", [("iqr_maximo", float("nan")), ("margen_campo_mm", float("inf")), ("iqr_maximo", np.float32(15.0))], ids=["iqr_nan", "margen_inf", "iqr_float32_de_numpy"])
    def test_un_parametro_no_finito_o_de_un_tipo_que_json_no_admite_se_rechaza_y_no_deja_nada(self, clave, valor, bd, guardar):
        """D1-PROD-03, la misma puerta por otro lado: 55 de las 70 combinaciones de un parametro numerico NaN o infinito se guardaban con `NaN` o `Infinity` en `parametros` (json_valid = 0), y un escalar de numpy
        ni se serializa (salia un `TypeError` y no el error del servicio, que es el que la ventana sabe decir). Las tres columnas JSON se escriben solo por una puerta estricta."""
        ref = _control(bd)
        P = _P()
        P[clave] = valor
        with pytest.raises(_svc().PlacaMensualError, match="parametros"):
            guardar(ref, parametros=P)
        assert _filas(bd) == [] and _auditoria(bd) == []

    @pytest.mark.parametrize("columna", ["parametros", "puntos", "piso"])
    def test_las_tres_columnas_json_se_escriben_por_la_puerta_estricta_aunque_el_motor_devuelva_un_nan(self, columna, bd, guardar, monkeypatch):
        """D1-PROD-03, defensa en profundidad: hoy ningun analisis legitimo lleva un NaN en lo que se guarda (medido en 20 analisis: las diez peliculas reales en automatico, la sintetica en los tres modos del piso y
        varios «no medible»), pero la regla de la tabla (`parametros`, `puntos` y `piso` son JSON) no puede depender de eso: si el motor devolviera uno, ninguna de las tres columnas lo escribe."""
        pm = _pm()
        real = pm.analizar

        def _con_un_nan(*argumentos, **opciones):
            resultado = real(*argumentos, **opciones)
            if columna == "parametros":
                return dataclasses.replace(resultado, parametros={**resultado.parametros, "inventado": float("nan")})
            if columna == "puntos":
                return dataclasses.replace(resultado, marcas=(dict(resultado.marcas[0], contraste=float("nan")),) + tuple(resultado.marcas[1:]))
            return dataclasses.replace(resultado, piso=dataclasses.replace(resultado.piso, escala_mm=float("nan")))
        monkeypatch.setattr(pm, "analizar", _con_un_nan)
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError, match=columna):
            guardar(ref)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_toda_fila_guardada_tiene_sus_tres_columnas_json_validas(self, guardados):
        """La tabla documenta `parametros`, `puntos` y `piso` como JSON y SQLite lo comprueba (`json_valid`): las nueve filas guardadas (3 modos x 3 capas) lo cumplen."""
        assert len(guardados.refs) == 9
        validas = _consulta(guardados.ruta, f"SELECT COUNT(*) FROM {TABLA} WHERE json_valid(parametros) AND json_valid(puntos) AND json_valid(piso)")
        assert validas == [(9,)]

    @pytest.mark.parametrize("ref", [None, 0, -3, True, "7", 2.5, ""])
    def test_un_ref_que_no_es_un_control_posible_se_rechaza(self, ref, bd, guardar):
        """`puede_editarse(0)` o `puede_editarse(None)` dan True (W1 no bloquea lo que no puede resolver): el servicio exige un ref de verdad ANTES."""
        assert _control(bd) == 1                     # el control 1 EXISTE y esta vigente: `True == 1` seria un control real si el servicio aceptara un booleano como ref
        with pytest.raises(_svc().PlacaMensualError):
            guardar(ref)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_un_rechazo_deja_intacta_la_vigente_que_ya_habia(self, bd, guardar):
        ref = _control(bd)
        anterior = _insertar(bd, _fila_minima(ref))
        antes = _consulta(bd, f"SELECT * FROM {TABLA}")
        with pytest.raises(_svc().PlacaMensualError):
            guardar(ref, capa="gris")
        assert _consulta(bd, f"SELECT * FROM {TABLA}") == antes and _filas(bd) == [(anterior, ref, 1, "G")]

    def test_si_el_analisis_no_llega_a_tomar_el_piso_no_hay_nada_que_volver_a_medir_y_no_se_guarda(self, bd, guardar, placa):
        """Los cinco puntos no forman el campo, o el archivo declara otra resolucion (no hay escala): `analizar` no llega al piso, la columna `piso` es obligatoria y no hay con que reabrir. D.1b: el texto
        es el de la regla unica (`motivo_para_no_guardar`): la capa no es medible, con el motivo del motor."""
        ref = _control(bd)
        with pytest.raises(_svc().PlacaMensualError, match="^la capa verde no es medible y no se guarda, sea cual sea el motivo; el análisis dice «no medible: los puntos no forman el campo"):
            guardar(ref, puntos=[(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)])
        con_300_dpi = gen.codificar(placa.imagen, "png", 300)
        with pytest.raises(_svc().PlacaMensualError, match="^la capa verde no es medible y no se guarda, sea cual sea el motivo; el análisis dice «no medible: no hay escala en milímetros"):
            guardar(ref, datos=con_300_dpi)
        assert _filas(bd) == [] and _auditoria(bd) == []


# ====================================================================================================================== (c) reguardar, W1, entero o nada, auditoria

class TestReguardarW1YAuditoria:
    def test_reguardar_anula_la_anterior_sin_borrarla_ni_tocarla(self, bd, guardar):
        ref = _control(bd)
        primera = guardar(ref, capa="G")
        antes = _consulta(bd, f"SELECT * FROM {TABLA} WHERE id = ?", (primera,))[0]
        segunda = guardar(ref, capa="R")
        assert segunda != primera and _filas(bd) == [(primera, ref, 0, "G"), (segunda, ref, 1, "R")]
        ahora = _consulta(bd, f"SELECT * FROM {TABLA} WHERE id = ?", (primera,))[0]
        columnas = _columnas(bd)
        diferentes = [c for c, a, b in zip(columnas, antes, ahora) if a != b]
        assert diferentes == ["activo"], diferentes                 # la anulada conserva TODO (la imagen, los valores, el piso): solo cambia su vigencia
        assert _svc().leer(ref)["id"] == segunda and _svc().leer(ref)["capa"] == "R"

    def test_cada_control_tiene_su_propio_analisis_vigente(self, bd, guardar):
        a, b = _control(bd), _control(bd)
        id_a, id_b = guardar(a), guardar(b)
        id_a2 = guardar(a, capa="B")
        assert _filas(bd) == [(id_a, a, 0, "G"), (id_b, b, 1, "G"), (id_a2, a, 1, "B")]
        assert _svc().leer(b)["id"] == id_b and _svc().leer(a)["id"] == id_a2

    def test_una_sola_fila_de_auditoria_por_guardado_que_nombra_la_capa_y_el_piso(self, lectura, guardados, oraculos):
        for (modo, capa), (ref, nuevo) in guardados.refs.items():
            filas = [f for f in _auditoria(guardados.ruta) if f[2] == str(ref)]
            assert len(filas) == 1, (modo, capa, filas)
            accion, usuario, _, detalle = filas[0]
            assert (accion, usuario) == ("guardar", USUARIO)
            assert f"capa reportada {capa}" in detalle and _pel().texto_breve_del_piso(oraculos[modo].piso, capa) in detalle
            assert "placa.png" in detalle and "C:" not in detalle                    # el nombre del archivo, sin la carpeta de quien lo subio
        assert len(_auditoria(guardados.ruta)) == len(guardados.refs)

    def test_reguardar_audita_un_reemplazo_con_el_id_de_la_reemplazada(self, bd, guardar):
        ref = _control(bd)
        primera = guardar(ref)
        segunda = guardar(ref, capa="B")
        guardado, reemplazo = _auditoria(bd)
        assert (guardado[0], guardado[1], guardado[2]) == ("guardar", USUARIO, str(ref))
        assert (reemplazo[0], reemplazo[1], reemplazo[2]) == ("reemplazo", USUARIO, str(ref))
        assert f"reemplaza id={primera}" in reemplazo[3] and "capa reportada B" in reemplazo[3] and segunda != primera

    def test_la_fila_de_auditoria_se_escribe_en_la_misma_transaccion_antes_del_commit(self, bd, guardar, monkeypatch):
        """Una fila de auditoria que se escribiera DESPUES del commit (o en otra conexion) podria perderse sin que el guardado lo supiera, o quedar sin guardado: al hacer `commit` la fila ya esta, en la misma conexion."""
        vistas = []

        class _ConexionEspia(sqlite3.Connection):
            def commit(self):
                filas = self.execute("SELECT COUNT(*) FROM audit_log WHERE tabla = ?", (TABLA,)).fetchone()[0]
                self.__dict__.setdefault("al_commit", []).append((filas, self.in_transaction))
                super().commit()

        def _conectar(self_):
            con = sqlite3.connect(bd, check_same_thread=False, factory=_ConexionEspia)
            conection_mod.aplicar_pragmas_conexion(con)
            vistas.append(con)
            return conection_mod._ConexionUnaVez(con)
        monkeypatch.setattr(Conexion, "conectar", _conectar)
        ref = _control(bd)
        guardar(ref)
        al_commit = [c for con in vistas for c in con.__dict__.get("al_commit", [])]
        assert al_commit == [(1, True)], al_commit             # UN solo commit, y al hacerlo la fila de auditoria ya estaba (1) en la misma conexion, con la transaccion todavia abierta
        assert len(_auditoria(bd)) == 1

    def test_un_control_anulado_no_acepta_el_analisis_y_no_deja_nada(self, bd, guardar):
        ref = _control(bd, activo=0)
        with pytest.raises(_svc().ControlNoEditable, match="anulado"):
            guardar(ref)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_un_control_que_se_anula_despues_de_guardar_no_acepta_reguardar_y_la_vigente_queda(self, bd, guardar):
        ref = _control(bd)
        primera = guardar(ref)
        _sql(bd, "UPDATE controles SET activo = 0 WHERE id = ?", (ref,))
        with pytest.raises(_svc().ControlNoEditable):
            guardar(ref, capa="R")
        assert _filas(bd) == [(primera, ref, 1, "G")] and len(_auditoria(bd)) == 1

    def test_un_control_inexistente_se_rechaza_como_no_editable_y_no_deja_nada(self, bd, guardar):
        with pytest.raises(_svc().ControlNoEditable, match="no existe"):
            guardar(99999)
        assert _filas(bd) == [] and _auditoria(bd) == []

    def test_entero_o_nada_si_el_insert_falla_no_se_anula_ni_se_audita(self, bd, guardar):
        """Un fallo a mitad no deja nada: la anulacion de la vigente, que ya se habia ejecutado en la misma transaccion, se deshace, y la auditoria tampoco queda."""
        ref = _control(bd)
        primera = guardar(ref)
        antes = _auditoria(bd)
        _sql(bd, f"CREATE TRIGGER falla_a_proposito BEFORE INSERT ON {TABLA} BEGIN SELECT RAISE(ABORT, 'falla de prueba'); END")
        with pytest.raises(sqlite3.Error, match="falla de prueba"):
            guardar(ref, capa="R")
        assert _filas(bd) == [(primera, ref, 1, "G")] and _auditoria(bd) == antes
        assert _svc().leer(ref)["id"] == primera


# ====================================================================================================================== (d) recalcular y diferencias

@pytest.fixture(scope="module")
def registro_guardado(guardados):
    """El registro (automatico, G) tal como lo lee el servicio, leido una vez."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: guardados.ruta)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            return _svc().leer(guardados.refs[("automatico", "G")][0])
        finally:
            Conexion._instance = previo


@pytest.fixture(scope="module")
def recalculado(registro_guardado):
    """El `ResultadoPlacaMensual` de recalcular ese registro (una vez); sus arreglos pesados se sueltan al terminar el modulo."""
    return _svc().recalcular(registro_guardado)


class TestRecalcularYDiferencias:
    @pytest.mark.parametrize("modo,capa", [("automatico", "G"), ("punto_manual", "R"), ("virgen", "B")])
    def test_recalcular_lo_guardado_da_cero_diferencias(self, modo, capa, lectura):
        registro = lectura(modo, capa)
        resultado = _svc().recalcular(registro)
        assert _svc().diferencias(registro, resultado) == []
        assert resultado.piso.modo == modo == registro["piso"]["modo"] and resultado.estado == "ok"

    def test_recalcular_usa_el_punto_marcado_guardado(self, lectura, punto_manual):
        registro = lectura("punto_manual", "G")
        resultado = _svc().recalcular(registro)
        assert tuple(resultado.piso.punto) == tuple(punto_manual) and resultado.piso.modo == "punto_manual"

    def test_recalcular_usa_los_puntos_ya_refinados_y_no_vuelve_a_refinar(self, registro_guardado, recalculado, monkeypatch):
        assert [dict(m) for m in recalculado.marcas] == registro_guardado["puntos"]

        def _refinar_no(*argumentos, **opciones):
            raise AssertionError("recalcular volvio a refinar un clic: usa las marcas YA refinadas que guardo (refinar de nuevo da el mismo numero, pero es otra operacion y otra definicion de la marca)")
        monkeypatch.setattr(_pm(), "refinar_marca", _refinar_no)
        de_nuevo = _svc().recalcular(registro_guardado)
        assert [dict(m) for m in de_nuevo.marcas] == registro_guardado["puntos"]

    def test_recalcular_una_imagen_o_una_referencia_que_ya_no_se_leen_dice_por_que_con_su_error(self, registro_guardado):
        svc = _svc()
        with pytest.raises(svc.PlacaMensualError):
            svc.recalcular(dict(registro_guardado, imagen=b"esto ya no es una pelicula"))
        referencia_rota = dict(registro_guardado, piso=dict(registro_guardado["piso"], modo="virgen", referencia_virgen={"estado": "ok"}))
        with pytest.raises(svc.PlacaMensualError):
            svc.recalcular(referencia_rota)

    def test_recalcular_usa_los_parametros_guardados_no_los_de_hoy(self, bd, guardar):
        """Se guarda con otro parametro (sin suavizar el perfil); recalcular da cero diferencias porque usa ESE, y con los de hoy (los de fabrica) daria otra cosa."""
        P = _P()
        P["suavizado_perfil_mm"] = 0.0
        P["banda_perfil_mm"] = 2.0
        ref = _control(bd)
        guardar(ref, capa="G", parametros=P)
        registro = _svc().leer(ref)
        assert registro["parametros"]["suavizado_perfil_mm"] == 0.0 and registro["parametros"]["banda_perfil_mm"] == 2.0
        assert _svc().diferencias(registro, _svc().recalcular(registro)) == []
        de_hoy = dict(registro, parametros=_P())
        assert _svc().diferencias(registro, _svc().recalcular(de_hoy)) != [], "con los parametros de hoy el resultado tendria que ser otro: la prueba no discriminaria"

    def test_recalcular_nunca_lee_la_referencia_virgen_vigente_del_archivo(self, lectura, tmp_path, guardados, monkeypatch):
        """DA-81: la copia guardada manda. Se deja en la carpeta de la base OTRA referencia vigente (15 niveles mas clara) y el registro sigue dando lo suyo."""
        registro = lectura("virgen", "G")
        distinta = copy.deepcopy(registro["piso"]["referencia_virgen"])
        for capa in distinta["capas"].values():
            capa["mediana"] = capa["mediana"] + 15.0
            capa["media"] = capa["media"] + 15.0                          # OD.1 (21-10): el VALOR de la referencia (`valor`, el piso que se usa) es la MEDIA de su zona, no la mediana
        otra = _pel().referencia_virgen_desde_dict(distinta)
        carpeta = str(Path(guardados.ruta).parent)                                       # la carpeta de la base: donde E.1 guarda `piso_pelicula_virgen.json`
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: guardados.ruta)    # la base "en uso" es esa: un servicio que buscara la referencia VIGENTE junto a ella la encontraria
        _pel().guardar_referencia_virgen(otra, carpeta)
        assert _pel().leer_referencia_virgen(carpeta).valor("G") == registro["piso"]["referencia_virgen"]["capas"]["G"]["media"] + 15.0
        resultado = _svc().recalcular(registro)
        assert _svc().diferencias(registro, resultado) == []
        assert resultado.piso.referencia.valor("G") == registro["piso"]["referencia_virgen"]["capas"]["G"]["media"]

    def test_diferencias_ve_cada_valor_guardado_que_cambia(self, registro_guardado, recalculado):
        svc = _svc()
        for nombre in MEDIDAS_DEL_PLAN:
            alterado = copy.copy(registro_guardado)
            alterado[nombre] = "no medible: otra cosa" if nombre == "estado" else registro_guardado[nombre] + 0.001
            diferencias = svc.diferencias(alterado, recalculado)
            assert len(diferencias) == 1 and nombre in diferencias[0], (nombre, diferencias)

    def test_diferencias_tolera_el_ruido_de_punto_flotante_y_ve_una_milesima_de_milimetro(self, registro_guardado, recalculado):
        svc = _svc()
        ruido = dict(registro_guardado, fwhm_crossplane_mm=registro_guardado["fwhm_crossplane_mm"] + 1e-9)
        assert svc.diferencias(ruido, recalculado) == []
        milesima = dict(registro_guardado, fwhm_crossplane_mm=registro_guardado["fwhm_crossplane_mm"] + 1e-3)
        assert len(svc.diferencias(milesima, recalculado)) == 1

    @pytest.mark.parametrize("capa", ("R", "G", "B", "gris"))
    def test_diferencias_tolera_el_ruido_de_punto_flotante_del_piso_y_ve_una_milesima_de_nivel(self, capa, registro_guardado, recalculado):
        """R1-PRU-01: la misma tolerancia (`TOLERANCIA_AL_RECALCULAR`) vale para el VALOR del piso de cada capa. La prueba de ruido de arriba solo perturbaba un FWHM: cambiar la comparacion de la mediana del piso por
        una igualdad exacta dejaba las 156 pruebas del archivo en verde, y una regresion asi daria falsas diferencias al reabrir en otra CPU o con otro decodificador sin que nadie las viera."""
        svc = _svc()
        ruido = copy.deepcopy(registro_guardado)
        ruido["piso"]["capas"][capa]["mediana"] += 1e-9
        assert svc.diferencias(ruido, recalculado) == [], capa
        milesima = copy.deepcopy(registro_guardado)
        milesima["piso"]["capas"][capa]["mediana"] += 1e-3
        diferencias = svc.diferencias(milesima, recalculado)
        assert len(diferencias) == 1 and "piso" in diferencias[0] and "valor" in diferencias[0], diferencias

    @pytest.mark.parametrize("capa", ("R", "G", "B", "gris"))
    def test_diferencias_compara_tambien_el_piso_de_cada_capa(self, capa, registro_guardado, recalculado):
        alterado = copy.deepcopy(registro_guardado)
        alterado["piso"]["capas"][capa]["mediana"] += 1.0
        diferencias = _svc().diferencias(alterado, recalculado)
        assert len(diferencias) == 1 and "piso" in diferencias[0] and (capa in diferencias[0] or _pel().ADJETIVO_DE_LA_CAPA[capa] in diferencias[0]), diferencias

    def test_diferencias_ve_que_el_estado_del_piso_de_una_capa_cambio(self, registro_guardado, recalculado):
        alterado = copy.deepcopy(registro_guardado)
        alterado["piso"]["capas"]["G"]["estado"] = "no medible: otra cosa"
        diferencias = _svc().diferencias(alterado, recalculado)
        assert len(diferencias) == 1 and "piso" in diferencias[0] and "estado" in diferencias[0] and "no medible: otra cosa" in diferencias[0], diferencias

    def test_diferencias_ve_que_el_modo_del_piso_es_otro(self, registro_guardado, recalculado):
        alterado = copy.deepcopy(registro_guardado)
        alterado["piso"]["modo"] = "virgen"
        diferencias = _svc().diferencias(alterado, recalculado)
        assert len(diferencias) == 1 and "modo del piso" in diferencias[0] and "virgen" in diferencias[0] and "automatico" in diferencias[0], diferencias

    def test_diferencias_con_un_resultado_sin_piso_lo_dice_y_no_lanza(self, registro_guardado, recalculado):
        sin_piso = dataclasses.replace(recalculado, piso=None)
        diferencias = _svc().diferencias(registro_guardado, sin_piso)
        assert any("recalculado sin piso" in d for d in diferencias), diferencias

    def test_diferencias_ve_que_la_version_del_motor_es_otra(self, registro_guardado, recalculado):
        diferencias = _svc().diferencias(dict(registro_guardado, version="PM-0"), recalculado)
        assert len(diferencias) == 1 and "PM-0" in diferencias[0] and recalculado.version in diferencias[0]

    def test_diferencias_ve_un_valor_que_aparece_o_desaparece(self, registro_guardado, recalculado):
        vacio = dict(registro_guardado, desfase_derecho_mm=None)
        diferencias = _svc().diferencias(vacio, recalculado)
        assert len(diferencias) == 1 and "desfase_derecho_mm" in diferencias[0]

    def test_diferencias_dice_lo_guardado_y_lo_recalculado_sin_simbolos(self, registro_guardado, recalculado):
        texto = _svc().diferencias(dict(registro_guardado, desfase_derecho_mm=None), recalculado)[0]
        assert "guardado" in texto and "recalculado" in texto and not any(s in texto for s in ("✓", "✗", "✔", "✘", "⚠", "❌", "✅"))


# ====================================================================================================================== el servicio, por dentro

class TestElServicioPorDentro:
    def test_la_firma_del_plan_con_capa_y_modo_sin_valor_por_omision(self):
        parametros = inspect.signature(_svc().guardar).parameters
        assert list(parametros) == ["ref", "usuario", "datos", "nombre", "puntos", "parametros", "capa", "modo_piso", "punto_manual", "referencia_virgen"]
        con_valor = {n: p.default for n, p in parametros.items() if p.default is not inspect.Parameter.empty}
        assert con_valor == {"punto_manual": None, "referencia_virgen": None}      # ningun valor por omision para lo que decide el numero: ni la capa ni el modo del piso

    def test_las_cuatro_funciones_publicas(self):
        svc = _svc()
        assert [n for n in ("guardar", "leer", "recalcular", "diferencias") if callable(getattr(svc, n, None))] == ["guardar", "leer", "recalcular", "diferencias"]
        assert list(inspect.signature(svc.leer).parameters) == ["ref"]
        assert list(inspect.signature(svc.recalcular).parameters) == ["registro"]
        assert list(inspect.signature(svc.diferencias).parameters) == ["registro", "resultado"]

    def _llamadas(self):
        arbol = ast.parse(SERVICIO_PY.read_text(encoding="utf-8"))
        llamadas = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                f = nodo.func
                llamadas.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", None))
        return arbol, llamadas

    def test_usa_las_definiciones_unicas_del_motor_del_contrato_y_de_la_auditoria(self):
        _, llamadas = self._llamadas()
        for nombre in ("refinar_marca", "analizar", "valores_medidos", "leer_pelicula", "texto_breve_del_piso", "referencia_virgen_desde_dict", "puede_editarse", "reemplazar_bloque", "filtro_activo"):
            assert nombre in llamadas, f"el servicio no llama a {nombre}"

    def test_no_calcula_la_medida_ni_el_piso_ni_el_texto_del_piso_por_su_cuenta(self):
        texto = SERVICIO_PY.read_text(encoding="utf-8")
        _, llamadas = self._llamadas()
        assert "piso_de_pelicula" not in llamadas and "piso_de_pelicula_virgen" not in llamadas       # el piso lo toma `analizar`, una sola vez
        assert "25.4" not in texto and "medir_perfil" not in llamadas and "perfil_central" not in llamadas and "geometria_luz" not in llamadas

    def test_no_importa_qt_ni_la_interfaz(self):
        arbol = ast.parse(SERVICIO_PY.read_text(encoding="utf-8"))
        importados = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                importados |= {a.name for a in nodo.names}
            elif isinstance(nodo, ast.ImportFrom):
                importados.add(nodo.module or "")
        assert not any(m.startswith(("PyQt5", "ui", "models")) for m in importados), importados

    def test_ningun_texto_del_servicio_lleva_simbolos_de_correcto_o_incorrecto(self):
        """DA-18: sin marcas ni emojis en lo que ve el usuario (el servicio solo da textos de auditoria, de error y de diferencias)."""
        texto = SERVICIO_PY.read_text(encoding="utf-8")
        assert not any(s in texto for s in ("✓", "✗", "✔", "✘", "⚠", "❌", "✅", "☑", "☒"))

    def test_la_regla_de_la_capa_no_medible_es_una_funcion_publica_y_guardar_no_la_repite(self):
        """D.1b: la ventana (E.1) necesita la MISMA regla antes de ofrecer «Guardar» (corolario 1: una operacion, una definicion). `guardar` la consulta en sus dos puntos (sin piso y antes de W1) y no
        decide por su cuenta si la capa es medible (ninguna comparacion con «ok» propia, ni un `.ok` ni un `startswith`)."""
        assert list(inspect.signature(_svc().motivo_para_no_guardar).parameters) == ["resultado", "capa"]
        guardar_def = next(n for n in ast.parse(SERVICIO_PY.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == "guardar")
        llamadas = [n for n in ast.walk(guardar_def) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "motivo_para_no_guardar"]
        assert len(llamadas) == 2, len(llamadas)
        propias = [n for n in ast.walk(guardar_def) if isinstance(n, ast.Compare) and any(isinstance(c, ast.Constant) and c.value == "ok" for c in [n.left, *n.comparators])]
        assert propias == [], "guardar decide por su cuenta si la capa es medible: eso lo dice `motivo_para_no_guardar`"
        por_su_cuenta = [n for n in ast.walk(guardar_def) if (isinstance(n, ast.Attribute) and n.attr == "ok")
                         or (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "startswith")]
        assert por_su_cuenta == [], "guardar decide por su cuenta si la capa es medible (un `.ok` o un `startswith`): eso lo dice `motivo_para_no_guardar`"


# ====================================================================================================================== (g) el tripwire: toda escritura a la tabla vive en el servicio

EXCLUDE_DIRS = {".venv", "tests", "build", "dist", "__pycache__", ".git", ".pytest_cache", "resources", "mcc_PTW_read"}
PRIMITIVAS_DE_ESCRITURA = {"reemplazar_bloque", "anular_fila", "sql_anular_bloque"}
_TABLA_RE = rf"(?:{TABLA}|(?-i:\{{TABLA\}}))"
PATRON_ESCRITURA = re.compile(
    rf"(insert\s+(?:or\s+\w+\s+)?into\s+{_TABLA_RE}|replace\s+into\s+{_TABLA_RE}|update\s+{_TABLA_RE}|delete\s+from\s+{_TABLA_RE}|drop\s+table\s+(?:if\s+exists\s+)?{_TABLA_RE})",
    re.IGNORECASE)

# Los UNICOS sitios autorizados, con su motivo: el servicio (compone el INSERT y lo ejecuta con la primitiva del contrato, tras comprobar W1).
SITIOS_PERMITIDOS = {
    ("services/placa_mensual.py", "guardar"): "comprueba W1 (`puede_editarse`), valida, y reemplaza el bloque con su fila de auditoria en una sola transaccion (DA-52)",
    ("services/placa_mensual.py", "sql_insert"): "solo COMPONE el texto del INSERT a partir de `MEDIDAS_GUARDADAS`; lo ejecuta `guardar` por `reemplazar_bloque`",
}


def _texto_de(nodo):
    """Texto de una cadena o f-string, con cada `{nombre}` conservado (asi `f"INSERT INTO {TABLA}"` se reconoce)."""
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


def _es_la_tabla(nodo):
    if isinstance(nodo, ast.Constant):
        return nodo.value == TABLA
    if isinstance(nodo, ast.Name):
        return nodo.id == "TABLA"
    if isinstance(nodo, ast.Attribute):
        return nodo.attr == "TABLA"
    return False


def _toca_la_tabla(arbol):
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and TABLA in nodo.value:
            return True
        if isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.module.endswith("placa_mensual") and not nodo.module.endswith("analisisImagenes.placa_mensual"):
            return True
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "services" and any(a.name == "placa_mensual" for a in nodo.names):
            return True
        if isinstance(nodo, ast.Import) and any(a.name.endswith("services.placa_mensual") for a in nodo.names):
            return True
    return False


class _Censo(ast.NodeVisitor):
    """Recorre el modulo llevando la funcion que envuelve a cada nodo (`<modulo>` fuera de toda funcion)."""

    def __init__(self):
        self._pila = ["<modulo>"]
        self.sitios = set()
        self.con_primitivas = set()

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
        if texto and PATRON_ESCRITURA.search(texto):
            self.sitios.add(self._pila[-1])

    def visit_Call(self, nodo):
        f = nodo.func
        nombre = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
        if nombre in PRIMITIVAS_DE_ESCRITURA and (any(_es_la_tabla(a) for a in nodo.args) or any(_es_la_tabla(k.value) for k in nodo.keywords)):
            self.sitios.add(self._pila[-1])
            self.con_primitivas.add(self._pila[-1])
        self.generic_visit(nodo)


def _sitios_de_archivo(ruta):
    try:
        arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"), filename=str(ruta))
    except (SyntaxError, UnicodeDecodeError):
        return set(), set()
    if not _toca_la_tabla(arbol):
        return set(), set()
    censo = _Censo()
    censo.visit(arbol)
    return censo.sitios, censo.con_primitivas


def _censar(raiz=RAIZ):
    hallazgos = set()
    for ruta in Path(raiz).rglob("*.py"):
        relativo = ruta.relative_to(raiz)
        if set(relativo.parts) & EXCLUDE_DIRS:
            continue
        for funcion in _sitios_de_archivo(ruta)[0]:
            hallazgos.add((relativo.as_posix(), funcion))
    return hallazgos


class TestTodaEscrituraALaTablaViveEnElServicio:
    def test_ninguna_escritura_sobre_la_tabla_fuera_del_servicio(self):
        sin_declarar = _censar() - set(SITIOS_PERMITIDOS)
        assert not sin_declarar, ("Escritura(s) NUEVA(S) sobre `analisis_placa_mensual` fuera del servicio -- se saltan W1, la auditoria y la transaccion unica. Pasa por "
                                  f"services.placa_mensual.guardar, o (si de verdad es legitima) declarala en SITIOS_PERMITIDOS con su motivo: {sin_declarar}")

    def test_los_sitios_permitidos_siguen_existiendo_y_el_censo_encuentra_exactamente_esos(self):
        assert SERVICIO_PY.exists(), "services/placa_mensual.py: no existe (el servicio no esta)"
        assert _censar() == set(SITIOS_PERMITIDOS)

    def test_toda_funcion_del_servicio_que_reemplaza_el_bloque_comprueba_w1(self):
        """Un segundo escritor DENTRO del modulo no puede saltarse W1 por vivir en el sitio autorizado."""
        sitios, con_primitivas = _sitios_de_archivo(SERVICIO_PY)
        assert con_primitivas, "el censo no encontro ninguna funcion que reemplace el bloque en el servicio: ¿cambio el archivo de forma que el detector ya no la ve?"
        arbol = ast.parse(SERVICIO_PY.read_text(encoding="utf-8"))
        funciones = {n.name: n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}
        for nombre in con_primitivas:
            llama = any(isinstance(s, ast.Call) and isinstance(s.func, ast.Name) and s.func.id == "puede_editarse" for s in ast.walk(funciones[nombre]))
            assert llama, f"{nombre} escribe en `analisis_placa_mensual` pero no llama a puede_editarse (W1): un control anulado aceptaria el analisis"


class TestElCensoDiscrimina:
    """Rojo dirigido (patron C.3): un intruso en un arbol TEMPORAL (nunca en el real: tres procesos pueden correr esta prueba a la vez) DEBE aparecer en el censo, en cada forma de escribir."""

    def _con_intruso(self, tmp_path, cuerpo, donde="services"):
        (tmp_path / donde).mkdir(exist_ok=True)
        (tmp_path / donde / "_intruso_d1.py").write_text(cuerpo, encoding="utf-8")
        return _censar(tmp_path)

    def test_detecta_un_insert_literal(self, tmp_path):
        assert self._con_intruso(tmp_path, f"def cambia(cur):\n    cur.execute(\"INSERT INTO {TABLA} (ref) VALUES (1)\")\n") == {("services/_intruso_d1.py", "cambia")}

    @pytest.mark.parametrize("sql", [f"UPDATE {TABLA} SET capa = 'R'", f"DELETE FROM {TABLA}", f"DROP TABLE IF EXISTS {TABLA}", f"REPLACE INTO {TABLA} (ref) VALUES (1)"])
    def test_detecta_un_update_un_delete_un_drop_y_un_replace(self, sql, tmp_path):
        assert self._con_intruso(tmp_path, f"def cambia(cur):\n    cur.execute({sql!r})\n", "ui") == {("ui/_intruso_d1.py", "cambia")}

    def test_detecta_una_primitiva_del_contrato_con_la_tabla_literal(self, tmp_path):
        assert self._con_intruso(tmp_path, f"def cambia(cur):\n    reemplazar_bloque(cur, '{TABLA}', [], '', [], 'u')\n") == {("services/_intruso_d1.py", "cambia")}

    def test_detecta_la_constante_TABLA_importada_del_servicio(self, tmp_path):
        cuerpo = "from services.placa_mensual import TABLA\ndef cambia(cur):\n    cur.execute(f'INSERT INTO {TABLA} (ref) VALUES (1)')\n    anular_fila(cur, TABLA, 1)\n"
        assert self._con_intruso(tmp_path, cuerpo, "scripts") == {("scripts/_intruso_d1.py", "cambia")}

    def test_una_lectura_no_es_una_escritura(self, tmp_path):
        assert self._con_intruso(tmp_path, f"def lee(cur):\n    return cur.execute('SELECT capa FROM {TABLA}').fetchall()\n") == set()

    def test_una_TABLA_ajena_en_un_modulo_que_no_toca_la_tabla_no_es_ruido(self, tmp_path):
        assert self._con_intruso(tmp_path, "TABLA = 'otra'\ndef escribe(cur):\n    cur.execute(f'INSERT INTO {TABLA} VALUES (1)')\n") == set()

    def test_el_censo_no_mira_los_tests_ni_el_entorno_virtual(self, tmp_path):
        assert self._con_intruso(tmp_path, f"def cambia(cur):\n    cur.execute(\"DELETE FROM {TABLA}\")\n", "tests") == set()
        assert self._con_intruso(tmp_path, f"def cambia(cur):\n    cur.execute(\"DELETE FROM {TABLA}\")\n", ".venv") == set()

    def test_el_arbol_real_no_se_toca(self):
        assert not (RAIZ / "services" / "_intruso_d1.py").exists()
