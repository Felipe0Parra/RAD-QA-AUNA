"""GI.1 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, H1, H2, H5, D3 y D4): lo que se guarda son las claves que el analisis produce.

CAUSA (medida el 06-10 con las series reales de los tres equipos): los mapeadores de `catphan_db.py` leian claves que el analisis no
produce. `mapear_resolucion_contraste` leia `rois_visibles_visibilidad_lim` y `pasa_test_visibilidad_lim` (el analisis da
`rois_visibles_visibilidad` y `pasa_test_visibilidad`) y el resumen de contraste de TODO control guardado desde 05/2026 quedo NULL/0 con
los ROI visibles en su detalle; `mapear_resolucion_espacial` leia `'lp/mm'` por region (el analisis da `'lp/cm'`: la region N vale N lp/cm)
y `lp_cm` quedo NULL en todas las regiones y `regiones_exitosas` en 0; el espesor guardaba `error_pct = 'No disponible'` cuando la
diferencia era exactamente 0.0 (veracidad en vez de `is not None`); y `linealidad_aceptable` llegaba como `numpy.bool_`, que SQLite guarda
como BLOB.

GARANTIAS, una por bloque:

  1. CENSO DERIVADO DEL PRODUCTOR -- el analisis REAL de una serie por equipo (tomografo, Halcyon, iX) pasa por los siete mapeadores reales,
     envueltos en un espia que anota cada clave que piden: toda clave pedida existe en la salida de alguna serie; la lista revisada de
     excepciones (con el motivo de cada una) solo puede achicarse. El espia se prueba a si mismo (detecta una clave inexistente; no es vacuo).
  2. LO QUE EL ANALISIS MIDIO ES LO QUE QUEDA -- esas mismas salidas reales, guardadas con el escritor real en una BD nueva, dejan en cada
     tabla hija los valores del analisis (contraste, espacial, espesor, tamano de pixel, valores CT, linealidad y uniformidad), y ninguna
     columna de las diez tablas hijas guarda un BLOB.
  3. CASOS CON LA FORMA DEL PRODUCTOR (sin corpus) -- el resumen de contraste con 3, 4 (la frontera) y 5 ROI visibles y con otros minimos (los
     dos veredictos siguen al analisis), la resolucion espacial con SOLO `'lp/cm'` (la forma real: sin `'lp/mm'`), regiones que no se midieron, una
     OK sin `'lp/cm'` y el centinela -1 del maximo, el espesor con diferencia (y promedio) exactamente 0.0, y la linealidad con `numpy.bool_`,
     numeros de numpy y sin `r_squared`, y la uniformidad con `pasa_ui` y `pasa_inu` distintos. Con el corpus, una prueba comprueba que esas
     formas copiadas a mano tienen exactamente las claves del productor real.
  4. NINGUN NOMBRE VIEJO -- tripwire por AST: ni los `mapear_*` ni los `guardar_*` nombran las claves que el analisis no produce.

FRONTERA con GI.2/GI.3 (lo que esta prueba NO fija a proposito): lo que LEEN `reconstruir_*` (la clave por region `'lp/mm'` de lo reconstruido, el
`Y` del tamano de pixel, el BLOB de linealidad ya guardado) es GI.2; los rotulos y el PDF son GI.3.

Nunca se conecta a una BD de referencia: las bases son nuevas, en un temporal.
"""
import ast
import contextlib
import copy
import os
import pathlib
import re
import sqlite3
import types
import warnings
from functools import lru_cache

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.catphan_TAC import catphan_db as C
from data.ManejoDatos.conection import Conexion
from _catphan_oro import ESPESOR_MM, LIMITE_HOMOGENEIDAD_IX
from _corpus import serie_catphan

RAIZ =pathlib.Path(__file__).resolve().parent.parent
CATPHAN_DB =RAIZ / "data" / "ManejoDatos" / "catphan_TAC" / "catphan_db.py"
ANALISIS = RAIZ / "analisisImagenes" / "Analisis_Catphan_TAC.py"

# Una serie por equipo (el plan: "una serie por equipo"): equipo de la app y limite de homogeneidad con el que pylinac localiza la serie.
SERIES = {
    "TOMOGRAFO": ("Tomógrafo", None),
    "HALCYON_JUN": ("Halcyon", None),
    "IX_DIC": ("Clinac ix", LIMITE_HOMOGENEIDAD_IX),
}

ID_TIPO = {"espesor": 1, "tamano_pixel": 2, "resolucion_contraste": 3, "resolucion_espacial": 4, "valores_ct": 5, "linealidad_ct": 6,
           "uniformidad": 7}
TABLAS_HIJAS = ("espesor_corte", "tamaño_pixel", "resolucion_contraste", "resolucion_contraste_rois", "resolucion_espacial",
                "resolucion_espacial_regiones", "valores_ct", "linealidad_ct", "uniformidad_ruido", "uniformidad_global")
ORDEN_MATERIALES = ("Aire", "PMP", "LDPE", "Poliestireno", "Acrilico", "Delrin", "Teflon")

# Claves que un mapeador PIDE, que el analisis solo produce A VECES (o que no produce el analisis sino el LECTOR al reabrir lo guardado), y que ninguna de las tres series
# reales produce: lista revisada a mano, con el motivo de cada entrada, que SOLO PUEDE ACHICARSE (`test_la_lista_revisada_solo_puede_achicarse`). Cada una es
# (categoria, ruta del diccionario, clave).
LECTURAS_CONDICIONALES_SIN_CASO_REAL = {
    ("resolucion_espacial", "resolucion_espacial.mtf_lp_cm", "10"):
        "el 10 % de la MTF solo se interpola si la MTF baja hasta ese valor (`for pct in (10, 20, 30, 40, 50)` de `resolucion_espacial`) y "
        "ninguna de las tres series baja tanto",
    ("valores_ct", "valores_ct[]", "rango_hu_de_catalogo"):
        "marca de PROCEDENCIA que pone el LECTOR (`reconstruir_valores_ct`) en un resultado reabierto de un control anterior a GI.8d, cuyo `rango_hu` es el del catalogo; "
        "un analisis recien hecho no tiene catalogo que marcar. El mapeador la lee para no sellar ese rango como el del analisis al volver a guardar lo reabierto (GI.8d)",
}

# Las claves con las que el mapeador leia lo que el analisis NO produce (la causa de GI.1).
CLAVES_VIEJAS = {"lp/mm", "rois_visibles_visibilidad_lim", "pasa_test_visibilidad_lim"}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# El espia: anota cada clave que un mapeador PIDE y cada clave que el analisis PRODUCE
# ---------------------------------------------------------------------------

class _Registro:
    def __init__(self):
        self.pedidas, self.producidas = set(), set()


def _normal(clave):
    """Los nombres de region, de diametro y de ROI de uniformidad son datos, no claves del esquema: una sola ruta para todos."""
    clave = str(clave)
    return "*" if re.fullmatch(r"region \d+|\d+mm", clave) or clave in ("Centro", "Arriba", "Abajo", "Izquierda", "Derecha") else clave


class _Espia(dict):
    """Un `dict` que anota cada `get`, cada `[]` y cada `in` (la clave pedida) y, al crearse, las claves que trae (las que el analisis produce)."""

    def __init__(self, base, categoria, ruta, registro):
        super().__init__({k: _envolver(v, categoria, f"{ruta}.{_normal(k)}", registro) for k, v in base.items()})
        self._categoria, self._ruta, self._registro = categoria, ruta, registro
        for clave in base:
            registro.producidas.add((categoria, ruta, str(clave)))

    def get(self, clave, defecto=None):
        self._registro.pedidas.add((self._categoria, self._ruta, str(clave)))
        return dict.get(self, clave, defecto)

    def __getitem__(self, clave):
        self._registro.pedidas.add((self._categoria, self._ruta, str(clave)))
        return dict.__getitem__(self, clave)

    def __contains__(self, clave):
        self._registro.pedidas.add((self._categoria, self._ruta, str(clave)))
        return dict.__contains__(self, clave)


def _envolver(valor, categoria, ruta, registro):
    if isinstance(valor, dict):
        return _Espia(valor, categoria, ruta, registro)
    if isinstance(valor, list):
        return [_envolver(v, categoria, ruta + "[]", registro) for v in valor]
    return valor


def _correr_mapeadores(resultados, espesor_nominal, tam_px, registro=None):
    """Los siete mapeadores REALES sobre las salidas del analisis envueltas en el espia."""
    registro = registro or _Registro()
    e = {c: _envolver(v, c, c, registro) for c, v in resultados.items()}
    C.mapear_espesor_corte(e["espesor"], espesor_nominal)
    C.mapear_tamano_pixel(e["tamano_pixel"], tam_px)
    C.mapear_resolucion_contraste(e["resolucion_contraste"])
    C.mapear_resolucion_espacial(e["resolucion_espacial"])
    C.mapear_valores_ct(e["valores_ct"])
    C.mapear_uniformidad(e["uniformidad"])
    C.mapear_linealidad_ct(e["linealidad_ct"])
    return registro


# ---------------------------------------------------------------------------
# El analisis REAL de una serie por equipo (las funciones que la pantalla invoca, con sus mismos argumentos)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _sin_ventanas():
    """`visualizar=True` sin canvas termina en `plt.show()`, que con un backend interactivo se queda esperando una ventana: aqui `show` no hace
    nada y se cierran SOLO las figuras que creo el analisis (no se cambia el backend: `switch_backend` cierra las figuras de otras pruebas). Con
    `visualizar=True` el resultado trae las imagenes y el elemento de metadatos de `valores_ct`, como en la pantalla."""
    import matplotlib.pyplot as plt
    antes = set(plt.get_fignums())
    parche = pytest.MonkeyPatch()
    parche.setattr(plt, "show", lambda *args, **kwargs: None)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        for numero in set(plt.get_fignums()) - antes:
            plt.close(numero)
        parche.undo()


def _v255(hu, wl=40, ww=400):
    lo, hi = wl - ww / 2, wl + ww / 2
    return ((np.clip(hu, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)


def _hu_del_corte(serie, indice):
    import pydicom
    ds = pydicom.dcmread(serie.cortes[indice].ruta)
    hu = ds.pixel_array.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
    return hu, float(ds.PixelSpacing[0])


@lru_cache(maxsize=None)
def _analisis_real(clave):
    """(equipo, tam_px, espesor nominal, {categoria: salida del analisis}) de una serie real. Se calcula UNA vez por serie."""
    from analisisImagenes import Analisis_Catphan_TAC as AN
    from analisisImagenes.catphan import criterios, motor
    from analisisImagenes.catphan.atenuacion import energia_de_linealidad_mev, materiales_a_energia
    from analisisImagenes.catphan.serie import leer_serie

    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    equipo, limite = SERIES[clave]
    serie = leer_serie(ruta)
    n = len(serie.cortes)
    with _sin_ventanas():
        perfil = types.SimpleNamespace(limite_variacion_hu=limite, nombre=clave)
        resultado = motor.analizar(serie, perfil)
        orientacion, roll = resultado.orientacion, resultado.roll_deg

        def corte(modulo):
            idx_pylinac = resultado.modulos[modulo].corte_indice
            idx = (n - 1 - idx_pylinac) if orientacion == "invertido" else idx_pylinac
            hu, px = _hu_del_corte(serie, idx)
            return hu, px, idx

        hu404, px, i404 = corte("CTP404")
        vecinos = [_hu_del_corte(serie, j)[0] for j in (i404 - 1, i404 + 1) if 0 <= j < n]
        salidas = {
            "espesor": AN.espesor_corte(_v255(hu404), hu404, px, visualizar=True, combinar_slices=True, slices_adyacentes=vecinos),
            "tamano_pixel": AN.tamano_pixel(_v255(hu404), hu404, px, visualizar=True),
            "valores_ct": AN.valor_numero_ct(_v255(hu404), hu404, px, visualizar=True),
        }
        hu515, px515, _ = corte("CTP515")
        salidas["resolucion_contraste"] = AN.resolucion_contraste(
            _v255(hu515), hu515, px515, visualizar=True, orientacion=orientacion, roll_deg=roll,
            **criterios.parametros_de_analisis("resolucion_contraste", equipo))
        hu528, px528, _ = corte("CTP528")
        salidas["resolucion_espacial"] = AN.resolucion_espacial(
            _v255(hu528), hu528, px528, visualizar=True, orientacion=orientacion, roll_deg=roll)
        hu486, px486, _ = corte("CTP486")
        salidas["uniformidad"] = AN.uniformidad(
            _v255(hu486), hu486, px486, visualizar=True, **criterios.parametros_de_analisis("uniformidad", equipo))
        energia = energia_de_linealidad_mev(equipo)
        materiales = materiales_a_energia(energia)
        hu_por_material = {r["material"]: r["promedio_hu"] for r in salidas["valores_ct"] if "material" in r}
        mu = [materiales[m]["mu"] for m in ORDEN_MATERIALES]
        hu = [hu_por_material[m] for m in ORDEN_MATERIALES]
        linealidad = AN.linealidad_ct(datos=mu, hu_promedio=hu, visualizar=True)
        linealidad["energia_mev"] = energia            # como la pantalla (G.2)
        salidas["linealidad_ct"] = linealidad
    return equipo, px, ESPESOR_MM[clave][1], salidas


# ---------------------------------------------------------------------------
# Bases nuevas y el escritor real
# ---------------------------------------------------------------------------

def _crear_control(ruta, equipo="Tomógrafo", fecha="06/2026"):
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)", (equipo, fecha))
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


def _guardar(sesion, categorias, **kw):
    base = dict(user_id="fisico1", fecha="2026-06-01", equipo="Tomógrafo", kv=120, ma=200, espesor_corte=2.0,
                resultados_por_categoria=categorias, id_sesion=sesion, tam_px_teorico=1.074)
    base.update(kw)
    return C.guardar_prueba_completa_catphan(**base)


@pytest.fixture
def bd_nueva(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "nueva.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _leer(ruta):
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    return con


def _id_prueba(con, sesion, categoria):
    return con.execute("SELECT id_prueba FROM pruebas WHERE id_sesion = ? AND id_tipo = ? AND (activo IS NULL OR activo = 1)",
                       (sesion, ID_TIPO[categoria])).fetchone()[0]


def _filas(con, tabla, id_prueba, orden="rowid"):
    return con.execute(f'SELECT * FROM "{tabla}" WHERE id_prueba = ? ORDER BY {orden}', (id_prueba,)).fetchall()


def _una_fila(con, tabla, id_prueba):
    filas = _filas(con, tabla, id_prueba)
    assert len(filas) == 1, f"{tabla}: se esperaba una fila y hay {len(filas)}"
    return filas[0]


@pytest.fixture(scope="module", params=sorted(SERIES))
def base_real(request, app, tmp_path_factory):
    """(clave, ruta de la BD, sesion, analisis) -- las salidas REALES de una serie, guardadas con el escritor real en una BD nueva."""
    clave = request.param
    equipo, px, nominal, salidas = _analisis_real(clave)
    ruta = str(tmp_path_factory.mktemp("gi1") / "real.db")
    mp = pytest.MonkeyPatch()
    mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    try:
        sesion = _crear_control(ruta, equipo)
        guardado = _guardar(sesion, copy.deepcopy(salidas), equipo=equipo, espesor_corte=nominal, tam_px_teorico=px)
        assert guardado == sesion, f"{clave}: el guardado real no entro (devolvio {guardado!r})"
    finally:
        conexion.con.close()
        Conexion._instance = None
        mp.undo()
    return types.SimpleNamespace(clave=clave, ruta=ruta, sesion=sesion, equipo=equipo, px=px, nominal=nominal, salidas=salidas)


# ---------------------------------------------------------------------------
# 1. CENSO DERIVADO DEL PRODUCTOR
# ---------------------------------------------------------------------------

def _series_disponibles():
    disponibles = [c for c in sorted(SERIES) if serie_catphan(c) is not None]
    if not disponibles:
        pytest.skip("corpus Catphan no disponible")
    return disponibles


def _censo_de_las_series():
    """(pedidas, producidas) sumadas sobre las series reales disponibles."""
    total = _Registro()
    for clave in _series_disponibles():
        equipo, px, nominal, salidas = _analisis_real(clave)
        registro = _correr_mapeadores(salidas, nominal, px)
        total.pedidas |= registro.pedidas
        total.producidas |= registro.producidas
    return total


def test_cada_clave_que_lee_un_mapeador_la_produce_el_analisis_real():
    """El analisis real de una serie por equipo -> el mapeador real: toda clave que el mapeador lee existe en la salida del analisis (de alguna
    serie). Hoy el de contraste lee `*_lim` y el espacial `'lp/mm'`: el analisis no las produce."""
    censo = _censo_de_las_series()
    sin_productor = sorted(k for k in censo.pedidas if k not in censo.producidas and k not in LECTURAS_CONDICIONALES_SIN_CASO_REAL)
    assert not sin_productor, (
        "Un mapeador lee claves que el analisis no produce (categoria, ruta, clave): " + "; ".join(map(str, sin_productor)))


def test_la_lista_revisada_solo_puede_achicarse():
    """Cada entrada de la lista revisada sigue siendo una lectura SIN productor en las series reales: si el analisis ya la produce, la entrada
    sobra y se retira (la lista solo puede achicarse); y toda entrada es una lectura que el mapeador de verdad hace."""
    censo = _censo_de_las_series()
    sobran = sorted(k for k in LECTURAS_CONDICIONALES_SIN_CASO_REAL if k in censo.producidas)
    assert not sobran, f"El analisis ya produce estas claves: retirelas de la lista revisada: {sobran}"
    inventadas = sorted(k for k in LECTURAS_CONDICIONALES_SIN_CASO_REAL if k not in censo.pedidas)
    assert not inventadas, f"Ningun mapeador pide ya estas claves: retirelas de la lista revisada: {inventadas}"


def test_el_censo_no_es_vacuo_y_detecta_una_clave_inexistente():
    """El espia se prueba a si mismo: con un productor de juguete anota lo pedido y lo producido, y una lectura de una clave que el productor no
    trae queda como pedida SIN productor. Y sobre las salidas reales el censo examina un numero de lecturas que no puede ser una corrida vacia."""
    registro = _Registro()
    producto = _envolver({"a": {"b": 1}, "c": [{"d": 2}]}, "juguete", "juguete", registro)
    producto["a"].get("b")
    producto["a"].get("x")                       # no existe
    producto["c"][0]["d"]
    sin_productor = sorted(k for k in registro.pedidas if k not in registro.producidas)
    assert sin_productor == [("juguete", "juguete.a", "x")]
    assert ("juguete", "juguete.a", "b") in registro.producidas and ("juguete", "juguete.c[]", "d") in registro.producidas
    # sobre una serie real (si hay corpus) el censo examina decenas de lecturas
    clave = next(iter(_series_disponibles()))
    equipo, px, nominal, salidas = _analisis_real(clave)
    real = _correr_mapeadores(salidas, nominal, px)
    assert len(real.pedidas) >= 40 and len(real.producidas) >= 100, (len(real.pedidas), len(real.producidas))
    categorias = {c for c, _, _ in real.pedidas}
    assert categorias == set(ID_TIPO), f"El censo no pidio claves de todas las categorias: {sorted(categorias)}"


def test_el_motivo_de_la_marca_de_procedencia_sigue_siendo_cierto():
    """La segunda entrada de la lista revisada se sostiene en un hecho de los productores: la marca `rango_hu_de_catalogo` la escribe el LECTOR (en el diccionario de cada
    material de `reconstruir_valores_ct`) y el analisis (`Analisis_Catphan_TAC`) no la conoce. Si el analisis empezara a producirla, la entrada sobraria y se retira."""
    lector = ast.parse((RAIZ / "data/ManejoDatos/catphan_TAC/catphan_db.py").read_text(encoding="utf-8"))
    funcion = next(n for n in ast.walk(lector) if isinstance(n, ast.FunctionDef) and n.name == "reconstruir_valores_ct")
    claves_del_lector = {k.value for d in ast.walk(funcion) if isinstance(d, ast.Dict) for k in d.keys if isinstance(k, ast.Constant)}
    assert "rango_hu_de_catalogo" in claves_del_lector
    assert "rango_hu_de_catalogo" not in ANALISIS.read_text(encoding="utf-8")


def test_el_motivo_de_la_unica_excepcion_sigue_siendo_cierto():
    """La entrada de la lista revisada se sostiene en un hecho del productor: las claves de `mtf_lp_cm` salen de `str(pct)` para
    `pct in (10, 20, 30, 40, 50)`, y solo se escriben si la MTF alcanza ese valor. Si el productor cambia, la excepcion deja de tener motivo."""
    fuente = ANALISIS.read_text(encoding="utf-8")
    assert "for pct in (10, 20, 30, 40, 50):" in fuente
    assert re.search(r"if min\(y\) <= target <= max\(y\):\s*\n\s*mtf_lp_cm\[str\(pct\)\]", fuente)


# ---------------------------------------------------------------------------
# 2. LO QUE EL ANALISIS MIDIO ES LO QUE QUEDA EN LA BASE (series reales)
# ---------------------------------------------------------------------------

def test_real_el_resumen_de_contraste_es_el_del_analisis(base_real):
    resumen = base_real.salidas["resolucion_contraste"]["resumen"]
    rois = base_real.salidas["resolucion_contraste"]["resultados_roi"]
    con = _leer(base_real.ruta)
    try:
        id_prueba = _id_prueba(con, base_real.sesion, "resolucion_contraste")
        fila = _una_fila(con, "resolucion_contraste", id_prueba)
        assert fila["rois_visibles_visibilidad"] == resumen["rois_visibles_visibilidad"]
        assert fila["rois_visibles_cnr"] == resumen["rois_visibles_cnr"]
        assert fila["total_rois"] == resumen["total_rois"]
        assert fila["pasa_test_visibilidad"] == int(resumen["pasa_test_visibilidad"])
        assert fila["pasa_test_cnr"] == int(resumen["pasa_test_cnr"])        # el analisis y el mapeador cuentan igual (min_rois_visibles = 4)
        visibles = [int(d.replace("mm", "")) for d, r in rois.items() if r["pasa_visibilidad_lim"]]
        assert fila["diametro_minimo_visible"] == (min(visibles) if visibles else None)
        assert len(visibles) == resumen["rois_visibles_visibilidad"]
        por_roi = {r["diametro_mm"]: r for r in _filas(con, "resolucion_contraste_rois", id_prueba)}
        assert sorted(por_roi) == sorted(int(d.replace("mm", "")) for d in rois)
        for d, roi in rois.items():
            guardado = por_roi[int(d.replace("mm", ""))]
            assert guardado["roi_promedio_hu"] == roi["roi_prom"] and guardado["cnr"] == roi["cnr"]
            assert guardado["visibilidad_lim"] == roi["visibilidad_lim"]
            assert guardado["pasa_visibilidad_lim"] == int(roi["pasa_visibilidad_lim"]) and guardado["pasa_cnr"] == int(roi["pasa_cnr"])
    finally:
        con.close()


def test_real_la_resolucion_espacial_es_la_del_analisis(base_real):
    esp = base_real.salidas["resolucion_espacial"]
    regiones = esp["region_results"]
    con = _leer(base_real.ruta)
    try:
        id_prueba = _id_prueba(con, base_real.sesion, "resolucion_espacial")
        fila = _una_fila(con, "resolucion_espacial", id_prueba)
        ok = [n for n, r in regiones.items() if r.get("status") == "OK"]
        assert ok, "la serie no midio ninguna region: la prueba no discrimina"
        assert fila["regiones_analizadas"] == len(regiones)
        assert fila["regiones_exitosas"] == len(ok)                          # contadas con la misma lectura que `lp_cm`
        assert fila["lp_cm_maximo"] == esp["resolucion_limite"]["lp_cm_maximo"]
        assert fila["ultima_region_exitosa"] == esp["resolucion_limite"]["ultima_region"]
        assert fila["gap_size_minimo_cm"] == esp["resolucion_limite"].get("gap_size_cm") and fila["num_picos_totales"] == esp["num_picos"]
        for columna, clave in (("mtf_10_pct", "10"), ("mtf_20_pct", "20"), ("mtf_50_pct", "50")):
            assert fila[columna] == esp["mtf_lp_cm"].get(clave), columna
        guardadas = {r["region_nombre"]: r for r in _filas(con, "resolucion_espacial_regiones", id_prueba)}
        assert sorted(guardadas) == sorted(regiones)
        for nombre, datos in regiones.items():
            g = guardadas[nombre]
            assert g["lp_cm"] == datos.get("lp/cm"), f"{nombre}: lp_cm {g['lp_cm']!r} no es el del analisis {datos.get('lp/cm')!r}"
            assert g["status"] == datos["status"]
            assert g["peak_mean"] == datos.get("peak_mean") and g["n_peaks_used"] == datos.get("n_peaks_used")
        # la region N vale N lp/cm por construccion: lo guardado dice lo mismo
        assert all(guardadas[n]["lp_cm"] == float(n.split()[1]) for n in guardadas if guardadas[n]["lp_cm"] is not None)
        assert sum(1 for g in guardadas.values() if g["lp_cm"] is not None) >= len(ok)
    finally:
        con.close()


def test_real_el_espesor_y_el_tamano_de_pixel_son_los_del_analisis(base_real):
    esp, tam = base_real.salidas["espesor"], base_real.salidas["tamano_pixel"]
    con = _leer(base_real.ruta)
    try:
        fila = _una_fila(con, "espesor_corte", _id_prueba(con, base_real.sesion, "espesor"))
        promedio = esp["espesor_promedio_mm"]
        assert promedio is not None
        assert fila["espesor_promedio_mm"] == round(promedio, 3)
        assert fila["espesor_teorico_mm"] == round(base_real.nominal, 3)
        assert fila["diferencia_mm"] == round(abs(promedio - base_real.nominal), 3)
        assert fila["error_pct"] == round(abs(promedio - base_real.nominal) / base_real.nominal * 100, 3)
        fila = _una_fila(con, "tamaño_pixel", _id_prueba(con, base_real.sesion, "tamano_pixel"))
        assert fila["X"] == round(tam["X"], 3) and fila["Y"] == round(tam["Y"], 3)
        assert fila["valor_teorico_dicom"] == round(base_real.px, 3)
        assert fila["diferencia_x"] == round(abs(tam["X"] - base_real.px), 3) and fila["diferencia_y"] == round(abs(tam["Y"] - base_real.px), 3)
        promedio_xy = (tam["X"] + tam["Y"]) / 2                                  # el error del promedio de X e Y contra el teorico (DP-41)
        assert fila["error_pct"] == round(abs(round(base_real.px, 3) - round(promedio_xy, 3)) / round(base_real.px, 3) * 100, 3)
    finally:
        con.close()


def test_real_los_valores_ct_y_la_uniformidad_son_los_del_analisis(base_real):
    con = _leer(base_real.ruta)
    try:
        id_ct = _id_prueba(con, base_real.sesion, "valores_ct")
        hu = {r["material"]: r for r in base_real.salidas["valores_ct"] if "material" in r}
        guardados = con.execute("""SELECT m.nombre_material AS material, v.promedio_hu, v.error_absoluto, v.error_relativo
                                   FROM valores_ct v JOIN materiales_ct m ON m.id_material = v.id_material
                                   WHERE v.id_prueba = ? ORDER BY v.id_material""", (id_ct,)).fetchall()
        assert [g["material"] for g in guardados] == list(ORDEN_MATERIALES)
        for g in guardados:
            origen = hu[g["material"]]
            assert g["promedio_hu"] == origen["promedio_hu"] and g["error_absoluto"] == origen["error_abs"]
            assert g["error_relativo"] == origen["error_rel"]
        uni = base_real.salidas["uniformidad"]
        id_uni = _id_prueba(con, base_real.sesion, "uniformidad")
        regiones = {r["id_region"]: r for r in _filas(con, "uniformidad_ruido", id_uni)}
        for id_region, nombre in enumerate(("Centro", "Arriba", "Derecha", "Abajo", "Izquierda"), start=1):
            assert regiones[id_region]["hu_promedio"] == uni[nombre]["promedio_hu"]
            assert regiones[id_region]["desviacion"] == uni[nombre]["desviacion"]
        g = _una_fila(con, "uniformidad_global", id_uni)
        u = uni["Uniformidad"]
        for columna in ("max_diferencia", "desviacion_global", "uniformity_index_max", "uniformity_index_roi", "integral_non_uniformity",
                        "integral_non_uniformity_pct"):
            esperado = u[columna] if u[columna] is not None else "No disponible"      # el escritor lo dice asi cuando el analisis no lo entrega
            assert g[columna] == esperado, columna
        for columna in ("pasa_ui", "pasa_inu", "pasa_global"):
            assert g[columna] == int(u[columna]), columna
    finally:
        con.close()


def test_real_la_linealidad_es_la_del_analisis_y_su_bandera_es_un_entero(base_real):
    lin = base_real.salidas["linealidad_ct"]
    con = _leer(base_real.ruta)
    try:
        id_prueba = _id_prueba(con, base_real.sesion, "linealidad_ct")
        fila = _una_fila(con, "linealidad_ct", id_prueba)
        assert fila["pendiente"] == lin["pendiente"] and fila["intercepto"] == lin["intercepto"] and fila["r_cuadrado"] == lin["r_squared"]
        assert fila["referencia"] == lin["referencia"] and fila["escala_contraste"] == lin["escala_contraste"]
        assert fila["num_materiales"] == 7 and fila["rango_hu_min"] == -1000 and fila["rango_hu_max"] == 1000       # constantes del mapeador
        assert fila["energia_mev"] == lin["energia_mev"]
        tipo = con.execute("SELECT typeof(linealidad_aceptable) FROM linealidad_ct WHERE id_prueba = ?", (id_prueba,)).fetchone()[0]
        assert tipo == "integer", f"linealidad_aceptable se guardo como {tipo} (un numpy.bool_ llega como BLOB)"
        assert fila["linealidad_aceptable"] == (1 if lin["r_squared"] >= 0.99 else 0)
    finally:
        con.close()


def test_real_reabrir_la_sesion_guardada_trae_las_siete_categorias_con_lo_guardado(base_real, monkeypatch):
    """Lo que GI.1 deja en la base ya no es NULL: reabrir la sesion no revienta con los valores nuevos y los trae (con los nombres con que los
    lee hoy `reconstruir_*`, que renombran GI.2 y GI.3: aqui se lee por cualquiera de las dos claves)."""
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: base_real.ruta)
    Conexion._instance = None
    try:
        reconstruido = C.reconstruir_resultados_desde_bd(base_real.sesion)
    finally:
        if Conexion._instance is not None:
            Conexion._instance.con.close()
        Conexion._instance = None
    assert sorted(reconstruido) == sorted(ID_TIPO), f"la reapertura no trajo todas las categorias: {sorted(reconstruido)}"
    regiones = reconstruido["resolucion_espacial"]["region_results"]
    lp = {n: r.get("lp/cm", r.get("lp/mm")) for n, r in regiones.items()}
    assert any(v is not None for v in lp.values()), f"la reapertura trae las regiones sin lp/cm: {lp}"
    resumen = reconstruido["resolucion_contraste"]["resumen"]
    guardado = base_real.salidas["resolucion_contraste"]["resumen"]
    cuenta = resumen.get("rois_visibles_visibilidad", resumen.get("rois_visibles_visibilidad_lim"))
    assert cuenta == guardado["rois_visibles_visibilidad"]
    assert reconstruido["linealidad_ct"]["linealidad_aceptable"] is bool(base_real.salidas["linealidad_ct"]["r_squared"] >= 0.99)


def test_real_ninguna_columna_de_las_tablas_hijas_guarda_un_blob(base_real):
    """Todo valor que el analisis entrega se guarda con su tipo nativo: ningun BLOB en las diez tablas hijas (las imagenes viven en `pruebas`)."""
    con = _leer(base_real.ruta)
    try:
        malas = []
        for tabla in TABLAS_HIJAS:
            columnas = [r[1] for r in con.execute(f'PRAGMA table_info("{tabla}")')]
            filas = con.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
            assert filas >= 1, f"{tabla}: la serie real no dejo ninguna fila"
            for c in columnas:
                tipos = {r[0] for r in con.execute(f'SELECT typeof("{c}") FROM "{tabla}"')}
                if "blob" in tipos:
                    malas.append(f"{tabla}.{c}")
        assert not malas, f"columnas con BLOB: {malas}"
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 3. CASOS CON LA FORMA DEL PRODUCTOR (sin corpus)
# ---------------------------------------------------------------------------

def _roi(diametro, n, visible, pasa_cnr):
    """Un ROI con la forma de `resolucion_contraste`: todos los numeros distintos entre ROI, para que un cruce de columnas se note."""
    return {
        "centro_roi": (200 + n, 300 + n), "diametro_mm": diametro, "radio_mm": diametro / 2.0, "radio_px": 4 + n,
        "roi_prom": 10.0 + n, "roi_std": 5.0 + n, "background_prom": 20.0 + n, "background_std": 3.0 + n,
        "diferencia_hu": 11.0 + n, "contraste_michelson": round(0.1 + n / 100, 4), "cnr": round(1.0 + n / 10, 2), "snr": round(2.0 + n / 10, 2),
        "visibilidad": round(0.2 + n / 100, 4), "visibilidad_lim": round(0.2 + n / 100, 4), "area_px": 50.0 + n,
        "pasa_visibilidad": visible, "pasa_visibilidad_lim": visible, "pasa_cnr": pasa_cnr,
        "visible_manual": None, "criterio_visibilidad": "calculo" if visible else "ninguno",
        "centro_fondo_int": (100, 100), "centro_fondo_ext": (110, 110),
    }


def _resultado_contraste(visibles, con_cnr, minimo=4):
    """Forma real de `resolucion_contraste`: `resumen` con `rois_visibles_*` y `pasa_test_*` (sin sufijo `_lim`). `visibles`/`con_cnr` son
    los diametros que pasan cada criterio."""
    diametros = (15, 9, 8, 7, 6, 5)
    rois = {f"{d}mm": _roi(d, n, d in visibles, d in con_cnr) for n, d in enumerate(diametros, start=1)}
    resumen = {"rois_visibles_cnr": len(con_cnr), "rois_visibles_visibilidad": len(visibles), "total_rois": 6, "cnr_lim": 1.0,
               "visibilidad_lim": 0.1, "min_rois_visibles": minimo, "pasa_test_cnr": len(con_cnr) >= minimo,
               "pasa_test_visibilidad": len(visibles) >= minimo}
    return {"resultados_roi": rois, "resumen": resumen}


@pytest.mark.parametrize("visibles, con_cnr", [
    ((15, 9, 8), (15, 9, 8, 7, 6)),               # 3 visibles: no pasa; 5 con CNR: pasa
    ((15, 9, 8, 7, 6), (15, 9)),                  # 5 visibles: pasa; 2 con CNR: no pasa
    ((15, 9, 8, 7), (15, 9, 8, 7)),               # EXACTAMENTE 4 de cada (la frontera del veredicto): los dos pasan
    ((), (15, 9, 8, 7, 6, 5)),                    # ninguna visible (el iX real): 0, no NULL
    ((15, 9, 8, 7, 6, 5), (15, 9, 8, 7, 6, 5)),   # las seis
])
def test_el_resumen_de_contraste_guarda_lo_que_produce_el_analisis(bd_nueva, visibles, con_cnr):
    resultado = _resultado_contraste(visibles, con_cnr)
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": resultado}) == sesion
    con = _leer(bd_nueva)
    try:
        id_prueba = _id_prueba(con, sesion, "resolucion_contraste")
        fila = _una_fila(con, "resolucion_contraste", id_prueba)
        assert fila["rois_visibles_visibilidad"] == len(visibles)
        assert fila["rois_visibles_cnr"] == len(con_cnr)
        assert fila["total_rois"] == 6
        assert fila["pasa_test_visibilidad"] == int(len(visibles) >= 4)
        assert fila["pasa_test_cnr"] == int(len(con_cnr) >= 4)
        assert fila["diametro_minimo_visible"] == (min(visibles) if visibles else None)
        assert fila["metodo_recomendado"] == "visibilidad_lim"
        rois = {r["diametro_mm"]: r for r in _filas(con, "resolucion_contraste_rois", id_prueba)}
        assert sorted(rois) == [5, 6, 7, 8, 9, 15]
        assert {d for d, r in rois.items() if r["pasa_visibilidad_lim"]} == set(visibles)
        assert {d for d, r in rois.items() if r["pasa_cnr"]} == set(con_cnr)
    finally:
        con.close()


@pytest.mark.parametrize("minimo, visibles, con_cnr", [
    (3, (15, 9, 8), (15, 9, 8)),                  # con 3 ROI y minimo 3 los dos veredictos pasan (con el 4 escrito en el mapeador, el de CNR no)
    (5, (15, 9, 8, 7), (15, 9, 8, 7)),            # con 4 ROI y minimo 5 los dos fallan
    (4, (15, 9, 8, 7), (15, 9, 8)),               # visibilidad pasa, CNR no
    (2, (15, 9), ()),                             # visibilidad pasa con 2, CNR (0) no
])
def test_los_dos_veredictos_del_resumen_siguen_el_minimo_con_que_corrio_el_analisis(bd_nueva, minimo, visibles, con_cnr):
    """`pasa_test_cnr` y `pasa_test_visibilidad` son del MISMO analisis (`min_rois_visibles` de `criterios.PARAMETROS_HEREDADOS`): la base guarda lo
    que el analisis dijo de cada uno, no un 4 escrito en el mapeador (dos revisores lo marcaron como segunda fuente de verdad en la misma fila)."""
    resultado = _resultado_contraste(visibles, con_cnr, minimo=minimo)
    resumen = resultado["resumen"]
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": resultado}) == sesion
    con = _leer(bd_nueva)
    try:
        fila = _una_fila(con, "resolucion_contraste", _id_prueba(con, sesion, "resolucion_contraste"))
        assert fila["pasa_test_visibilidad"] == int(resumen["pasa_test_visibilidad"]) == int(len(visibles) >= minimo)
        assert fila["pasa_test_cnr"] == int(resumen["pasa_test_cnr"]) == int(len(con_cnr) >= minimo)
    finally:
        con.close()


def _region(n, status, **extra):
    base = {"lp/cm": n, "peak_mean": 100.0 + n, "valley_mean": 50.0 + n, "n_peaks_used": 2 + n, "n_valleys_used": 1 + n,
            "gap_size_cm": round(1 / n / 2, 3), "status": status}
    base.update(extra)
    return base


def _resultado_espacial():
    """Forma real de `resolucion_espacial`: cada region trae SOLO `'lp/cm'` (nunca `'lp/mm'`); las que no se midieron traen solo estado
    (y `'lp/cm'` si lo conocen); una region con el intervalo invalido no trae ni `'lp/cm'`. Las OK son 4 (regiones 1, 2, 3 y 5) y la
    ultima es la 5: `regiones_exitosas` (4) y `lp_cm_maximo` (5) NO coinciden, para que un cruce entre columnas se note."""
    regiones = {                                  # en el orden en que el productor recorre `roi_settings`: 1..8
        "region 1": _region(1, "OK"), "region 2": _region(2, "OK"), "region 3": _region(3, "OK"),
        "region 4": {"lp/cm": 4, "found_peaks": 3, "expected_peaks": 4, "status": "Picos insuficientes"},
        "region 5": _region(5, "OK"),
        "region 6": {"lp/cm": 6, "status": "Fuera del límite de muestreo (4.65 lp/cm con este píxel)"},
        "region 7": {"status": "Región muy pequeña", "lp/cm": 7},
        "region 8": {"status": "Intervalo inválido (start<=end)"},
    }
    return {
        "region_results": regiones, "mtf_values": {"2.0": 0.8, "3.0": 0.5},
        "mtf_lp_cm": {"20": 4.1, "50": 3.1}, "num_picos": 11, "valores_picos": [1.0, 2.0],
        "resolucion_limite": {"ultima_region": "region 5", "lp_cm_maximo": 5, "gap_size_cm": 0.1},
        "imagen_analisis": None,
    }


def test_la_resolucion_espacial_guarda_lp_cm_por_region_con_la_forma_del_analisis(bd_nueva):
    resultado = _resultado_espacial()
    assert not any("lp/mm" in r for r in resultado["region_results"].values())   # la forma real: nadie trae `'lp/mm'`
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": resultado}) == sesion
    con = _leer(bd_nueva)
    try:
        id_prueba = _id_prueba(con, sesion, "resolucion_espacial")
        fila = _una_fila(con, "resolucion_espacial", id_prueba)
        assert fila["regiones_analizadas"] == 8
        assert fila["regiones_exitosas"] == 4                      # solo las OK (con el valor de `'lp/cm'`)
        assert fila["lp_cm_maximo"] == 5 and fila["ultima_region_exitosa"] == "region 5"
        assert fila["mtf_20_pct"] == 4.1 and fila["mtf_50_pct"] == 3.1 and fila["mtf_10_pct"] is None
        assert fila["num_picos_totales"] == 11 and fila["gap_size_minimo_cm"] == 0.1
        guardadas = {r["region_nombre"]: r for r in _filas(con, "resolucion_espacial_regiones", id_prueba)}
        assert {n: g["lp_cm"] for n, g in guardadas.items()} == {
            "region 1": 1, "region 2": 2, "region 3": 3, "region 4": 4, "region 5": 5, "region 6": 6, "region 7": 7, "region 8": None}
        assert guardadas["region 2"]["peak_mean"] == 102.0 and guardadas["region 3"]["n_peaks_used"] == 5
        assert guardadas["region 5"]["status"] == "OK" and guardadas["region 5"]["peak_mean"] == 105.0
        assert guardadas["region 4"]["status"] == "Picos insuficientes" and guardadas["region 4"]["peak_mean"] is None
        assert guardadas["region 8"]["status"].startswith("Intervalo")
    finally:
        con.close()


def test_regiones_exitosas_cuenta_solo_las_ok_aunque_las_otras_traigan_lp_cm():
    resumen, regiones = C.mapear_resolucion_espacial(_resultado_espacial())
    assert resumen["regiones_exitosas"] == 4 and resumen["regiones_analizadas"] == 8
    assert {r["region_nombre"]: r["lp_cm"] for r in regiones} == {
        "region 1": 1, "region 2": 2, "region 3": 3, "region 4": 4, "region 5": 5, "region 6": 6, "region 7": 7, "region 8": None}


def test_una_region_ok_sin_lp_cm_no_cuenta_como_exitosa():
    """`regiones_exitosas` se cuenta con la MISMA lectura que `lp_cm` (plan GI.1): una region OK a la que el analisis no le dio `'lp/cm'` no cuenta."""
    resumen, regiones = C.mapear_resolucion_espacial({
        "region_results": {"region 1": {"lp/cm": 1, "status": "OK"}, "region 2": {"status": "OK"}},
        "resolucion_limite": {"ultima_region": "region 1", "lp_cm_maximo": 1}})
    assert resumen["regiones_analizadas"] == 2 and resumen["regiones_exitosas"] == 1
    assert {r["region_nombre"]: r["lp_cm"] for r in regiones} == {"region 1": 1, "region 2": None}


def test_el_centinela_del_maximo_se_guarda_tal_cual(bd_nueva):
    """Ninguna region OK: el analisis deja `lp_cm_maximo = -1` (centinela de su `max_lp_cm`) y `ultima_region = None`, y la base guarda lo que el
    analisis entrego (reproducido con el analisis real sobre un corte desenfocado). Como lo dice un PDF o «Ver tabla» es de GI.3; esta prueba
    fija el estado de hoy para que un cambio de ese centinela no pase inadvertido."""
    resultado = {"region_results": {f"region {n}": {"lp/cm": n, "found_peaks": 1, "expected_peaks": 2, "status": "Picos insuficientes"}
                                    for n in range(1, 4)},
                 "mtf_values": {}, "mtf_lp_cm": {}, "num_picos": 0, "valores_picos": [],
                 "resolucion_limite": {"ultima_region": None, "lp_cm_maximo": -1}, "imagen_analisis": None}
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_espacial": resultado}) == sesion
    con = _leer(bd_nueva)
    try:
        fila = _una_fila(con, "resolucion_espacial", _id_prueba(con, sesion, "resolucion_espacial"))
        assert fila["regiones_analizadas"] == 3 and fila["regiones_exitosas"] == 0
        assert fila["lp_cm_maximo"] == -1 and fila["ultima_region_exitosa"] is None and fila["gap_size_minimo_cm"] is None
    finally:
        con.close()


def _resultado_espesor(promedio):
    return {"espesor_promedio_mm": promedio, "espesores_individuales": {"Izquierda": 1.9, "Abajo": 2.0, "Derecha": 2.1, "Arriba": 2.0},
            "factor_correccion": 0.42, "num_rampas_detectadas": 4, "combinacion_slices": True, "imagen_analisis": None}


@pytest.mark.parametrize("promedio, nominal, diferencia, error", [
    (2.0, 2.0, 0.0, 0.0),            # diferencia EXACTAMENTE 0.0: un cero es un valor, no "No disponible"
    (2.5, 2.0, 0.5, 25.0),
    (1.92, 2.0, 0.08, 4.0),
    (2.0, 2.5, 0.5, 20.0),
    (0.0, 2.0, 2.0, 100.0),          # un promedio de 0.0 tambien es un valor (la otra copia de «veracidad en vez de is not None», en el mapeador)
])
def test_el_espesor_guarda_un_error_numerico_tambien_cuando_la_diferencia_es_cero(bd_nueva, promedio, nominal, diferencia, error):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"espesor": _resultado_espesor(promedio)}, espesor_corte=nominal) == sesion
    con = _leer(bd_nueva)
    try:
        id_prueba = _id_prueba(con, sesion, "espesor")
        fila = _una_fila(con, "espesor_corte", id_prueba)
        assert fila["espesor_promedio_mm"] == promedio and fila["espesor_teorico_mm"] == nominal
        assert fila["diferencia_mm"] == diferencia
        assert fila["error_pct"] == error
        tipos = con.execute("SELECT typeof(espesor_promedio_mm), typeof(espesor_teorico_mm), typeof(diferencia_mm), typeof(error_pct) "
                            "FROM espesor_corte WHERE id_prueba = ?", (id_prueba,)).fetchone()
        assert set(tipos) == {"real"}, f"el espesor guardo algo que no es un numero: {tuple(tipos)}"
    finally:
        con.close()


def test_el_espesor_sin_valor_sigue_diciendo_no_disponible(bd_nueva):
    """Control: lo que NO cambia. Sin espesor medido (o sin nominal) no hay diferencia que calcular y la fila lo dice como hasta hoy."""
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"espesor": _resultado_espesor(None)}, espesor_corte=2.0) == sesion
    con = _leer(bd_nueva)
    try:
        fila = _una_fila(con, "espesor_corte", _id_prueba(con, sesion, "espesor"))
        assert fila["espesor_promedio_mm"] == "No disponible" and fila["diferencia_mm"] == "No disponible"
        assert fila["error_pct"] == "No disponible" and fila["espesor_teorico_mm"] == 2.0
    finally:
        con.close()


def _forma_linealidad(r2):
    """Forma real de `linealidad_ct` (con la energia que la pantalla le agrega): numeros de numpy, como los entrega el analisis."""
    return {"pendiente": np.float64(6146.9), "intercepto": np.float64(-996.0), "r_squared": r2, "referencia": np.float64(0.5),
            "escala_contraste": np.float64(0.00016), "energia_mev": 0.12, "imagen_analisis": None}


def test_una_linealidad_sin_r_cuadrado_no_es_aceptable():
    """Sin `r_squared` el mapeador usa 0 por omision: la bandera es False y la columna del coeficiente queda vacia (no hay aceptacion inventada)."""
    mapeo = C.mapear_linealidad_ct({"pendiente": 1.0})
    assert mapeo["linealidad_aceptable"] is False and mapeo["r_cuadrado"] is None


@pytest.mark.parametrize("r2, esperado", [(np.float64(0.995), True), (np.float64(0.5), False), (np.float64(0.99), True),
                                           (np.float64(0.9899), False), (0.9991, True)])
def test_la_bandera_de_linealidad_es_un_booleano_nativo_y_se_guarda_como_entero(bd_nueva, r2, esperado):
    """El analisis entrega `round(np.float64, 3)`: `r2 >= 0.99` es un `numpy.bool_`, y SQLite guarda un `numpy.bool_` como BLOB (que luego se lee
    como True aunque sea 0). La bandera es un `bool` de Python y se guarda como 0 o 1."""
    lin = _forma_linealidad(r2)
    mapeo = C.mapear_linealidad_ct(lin)
    assert mapeo["linealidad_aceptable"] is esperado, (type(mapeo["linealidad_aceptable"]), mapeo["linealidad_aceptable"])
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"linealidad_ct": lin}) == sesion
    con = _leer(bd_nueva)
    try:
        id_prueba = _id_prueba(con, sesion, "linealidad_ct")
        fila = con.execute("SELECT *, typeof(linealidad_aceptable) AS t, typeof(r_cuadrado) AS tr, typeof(pendiente) AS tp "
                           "FROM linealidad_ct WHERE id_prueba = ?", (id_prueba,)).fetchone()
        assert fila["t"] == "integer" and fila["linealidad_aceptable"] == int(esperado)
        assert fila["tr"] == "real" and fila["tp"] == "real"
        assert fila["r_cuadrado"] == float(r2) and fila["energia_mev"] == 0.12
    finally:
        con.close()


def _resultado_uniformidad(pasa_ui, pasa_inu):
    """Forma real de `uniformidad`: los cinco ROI (el de `Centro` sin `ui`), el bloque `Uniformidad` y la imagen; los dos veredictos DISTINTOS
    (`pasa_ui` y `pasa_inu`) para que un cruce entre ellos se note: las tres series reales dan los dos iguales."""
    rois = {}
    for n, nombre in enumerate(("Centro", "Abajo", "Derecha", "Arriba", "Izquierda"), start=1):
        rois[nombre] = {"centro": (100 + n, 200 + n), "promedio_hu": 10.0 + n, "desviacion": round(1.0 + n / 10, 1)}
        if nombre != "Centro":
            rois[nombre].update({"ui": round(0.1 * n, 3), "pasa_tolerancia_rel_centro": True})
    rois["Uniformidad"] = {"max_diferencia": 5.5, "desviacion_global": 1.7, "uniformity_index_max": 0.4, "uniformity_index_roi": "Arriba",
                           "integral_non_uniformity": 0.01234, "integral_non_uniformity_pct": 1.234, "pasa_ui": pasa_ui,
                           "pasa_inu": pasa_inu, "pasa_global": bool(pasa_ui and pasa_inu), "inu_warning": None,
                           # GI.8b: los tres umbrales con que se juzgo (el analisis los devuelve); valores distintos de los 2.0 / 2.0 / 40.0 de antes
                           "ui_threshold_pct": 3.5, "inu_threshold_pct": 4.5, "hu_tolerancia": 12.5}
    rois["imagen_analisis"] = None
    return rois


@pytest.mark.parametrize("pasa_ui, pasa_inu", [(True, False), (False, True), (True, True), (False, False)])
def test_la_uniformidad_guarda_cada_veredicto_en_su_columna(bd_nueva, pasa_ui, pasa_inu):
    resultado = _resultado_uniformidad(pasa_ui, pasa_inu)
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"uniformidad": resultado}) == sesion
    con = _leer(bd_nueva)
    try:
        id_prueba = _id_prueba(con, sesion, "uniformidad")
        g = _una_fila(con, "uniformidad_global", id_prueba)
        u = resultado["Uniformidad"]
        for columna in ("max_diferencia", "desviacion_global", "uniformity_index_max", "uniformity_index_roi", "integral_non_uniformity",
                        "integral_non_uniformity_pct"):
            assert g[columna] == u[columna], columna
        assert (g["pasa_ui"], g["pasa_inu"], g["pasa_global"]) == (int(pasa_ui), int(pasa_inu), int(pasa_ui and pasa_inu))
        regiones = {r["id_region"]: r for r in _filas(con, "uniformidad_ruido", id_prueba)}
        for id_region, nombre in enumerate(("Centro", "Arriba", "Derecha", "Abajo", "Izquierda"), start=1):
            assert regiones[id_region]["hu_promedio"] == resultado[nombre]["promedio_hu"], nombre
            assert regiones[id_region]["desviacion"] == resultado[nombre]["desviacion"], nombre
    finally:
        con.close()


def test_las_formas_sinteticas_tienen_exactamente_las_claves_del_productor_real():
    """Los casos sin corpus copian a mano la FORMA de lo que produce el analisis: con el corpus se comprueba que la copia no se desvio (si el
    productor renombra o agrega una clave, esta prueba lo dice y los casos sinteticos se ajustan)."""
    clave = next(iter(_series_disponibles()))
    equipo, px, nominal, salidas = _analisis_real(clave)
    real_contraste = salidas["resolucion_contraste"]
    sintetico = _resultado_contraste((15,), (15,))
    assert set(sintetico["resumen"]) == set(real_contraste["resumen"]) - {"imagen_analisis"}
    assert set(sintetico["resultados_roi"]["15mm"]) == set(real_contraste["resultados_roi"]["15mm"])
    real_espacial = salidas["resolucion_espacial"]
    assert set(_resultado_espacial()) == set(real_espacial)
    region_ok = next(r for r in real_espacial["region_results"].values() if r["status"] == "OK")
    assert set(_region(1, "OK")) == set(region_ok)
    assert set(_resultado_espesor(2.0)) == set(salidas["espesor"])
    assert set(_forma_linealidad(0.999)) == set(salidas["linealidad_ct"])
    real_uniformidad, sintetica = salidas["uniformidad"], _resultado_uniformidad(True, False)
    assert set(sintetica) == set(real_uniformidad)
    assert set(sintetica["Uniformidad"]) == set(real_uniformidad["Uniformidad"])
    assert set(sintetica["Centro"]) == set(real_uniformidad["Centro"]) and set(sintetica["Arriba"]) == set(real_uniformidad["Arriba"])


# ---------------------------------------------------------------------------
# 4. NINGUN NOMBRE VIEJO (tripwire por AST)
# ---------------------------------------------------------------------------

def _funciones(nombre_archivo):
    arbol = ast.parse(nombre_archivo.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}


def test_ni_los_mapeadores_ni_los_escritores_nombran_claves_que_el_analisis_no_produce():
    """Los siete `mapear_*` y los siete `guardar_*` por categoria (el lado del GUARDADO): ninguna cadena es una de las claves con las que se
    leia lo que el analisis no produce. Los lectores (`reconstruir_*`) y los rotulos quedan fuera a proposito: para las filas viejas todavia
    dicen `'lp/mm'` (GI.2, GI.3)."""
    funciones = _funciones(CATPHAN_DB)
    objetivo = [n for n in funciones if n.startswith("mapear_") and n != "mapear_identidad_dicom"] + [
        "guardar_espesor_corte", "guardar_tamano_pixel", "guardar_resolucion_contraste", "guardar_resolucion_espacial",
        "guardar_valores_ct", "guardar_linealidad_ct", "guardar_uniformidad"]
    assert len([n for n in objetivo if n.startswith("mapear_")]) == 7, sorted(objetivo)
    encontradas = []
    for nombre in objetivo:
        for nodo in ast.walk(funciones[nombre]):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and nodo.value in CLAVES_VIEJAS:
                encontradas.append((nombre, nodo.lineno, nodo.value))
    assert not encontradas, f"claves que el analisis no produce: {encontradas}"
