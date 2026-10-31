"""C.3 (PLAN_ANALISIS_PELICULAS_08-10.md): el MOTOR MENSUAL (3/3) -- el barrido, sin parametro, en la misma zona central, con sus medidas estadisticas
(`analisisImagenes/placa_mensual.py`, version PM-1; se AGREGA al modulo de C.1 y C.2, cuyas funciones no cambian).

CAUSA (R3: N6 y N11; PD2 y PD3). El barrido del cuaderno recorre el rango de la y tambien para el inplane, llega a +-44.5 mm (ya en el hombro y a 4-5 mm de las marcas de las esquinas), reasigna las
variables del perfil central (la celda 80 imprime el ULTIMO barrido) y solo guarda los valores dentro de +-5 % de 100 mm en las tres capas a la vez: lo que se sale desaparece y su eje x es un indice. La
primera regla del 09-10 (el 80 % del FWHM perpendicular de cada capa) salia de la meseta en las capas saturadas y daba ocho regiones distintas por placa. C.3: `barrido(resultado)` mide, con la MISMA
`medir_perfil` de C.2, bandas de `banda_perfil_mm` ancladas en el cruce de diagonales sobre ESA zona central (+-40 % de la distancia entre los bordes luminosos de la linea central perpendicular), la
misma para las cuatro capas, sin ningun parametro, sin descartar ninguna banda, con la media, la mediana, la desviacion y cuantas bandas se pudieron medir.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale de las funciones (el generador de PF.0 es INDEPENDIENTE del motor):
  (a) una pelicula con un FWHM que varia linealmente con la posicion (`beta`): cada banda cae donde predice el generador en SU posicion en mm (+-0.15 mm) y la pendiente es la de beta;
  (b) con la cupula de las peliculas reales (-4 %) las bandas de los extremos de las capas saturadas salen MAS ANGOSTAS, lo que dice el oraculo de la definicion del plan, y en las diez peliculas reales
      el rojo de los extremos queda 0.25 a 1.3 mm bajo el del centro (el plan midio -0.3 a -0.95);
  (c) la region es +-40 % de la distancia entre los bordes luminosos de la linea perpendicular, alrededor del cruce: escala con el campo luminoso (80, 100 y 120 mm), es la misma en las cuatro capas, no cambia
      si se altera el perfil perpendicular de la radiacion y NINGUNA banda cae fuera;
  (d) la banda 0 ES el perfil central: igualdad EXACTA, campo por campo, con el resultado de `analizar`;
  (e) el inplane recorre la x y el crossplane la y (un campo de 80 x 110 mm las distingue; el cuaderno recorre la y para los dos);
  (f) una mota sobre la linea central mueve el corte central y no la mediana;
  (g) ninguna banda medible se excluye de la media ni de la mediana (ni las que se salen de +-5 % de 100 mm);
  (h) por AST, `barrido` tiene UN solo parametro y no hay ningun parametro nuevo.
Y las garantias de estructura: el barrido no gira la pelicula, no vuelve a calcular el piso, no cambia el resultado que recibe, usa los parametros que el resultado ya trae, cada banda lleva SUS bordes
luminosos (las esquinas pueden quedar inclinadas) y el costo es de fracciones de segundo.

Rojo contra HEAD (266dfb1): HEAD no tiene `barrido`: todas las pruebas caen por API ausente. El rojo SUSTANTIVO esta en `c3_rojo_head.py` del anexo (el barrido del cuaderno puesto en lugar del nuevo) y las
mutaciones en `c3_mutaciones.py`.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import dataclasses
import gc
import hashlib
import importlib
import inspect
import json
import math
import time
import tracemalloc
import weakref
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import brentq

import _corpus
import _placa_mensual_sintetica as gen

RAIZ = Path(__file__).resolve().parent.parent
MODULO = RAIZ / "analisisImagenes" / "placa_mensual.py"
TAM = 25.4 / 600.0                                      # mm por pixel: la escala del procedimiento (600 dpi)
CAPAS = ("R", "G", "B", "gris")
EJES = ("crossplane", "inplane")
PERPENDICULAR = {"crossplane": "inplane", "inplane": "crossplane"}
ORDEN_DE_LOS_PUNTOS = ("UL", "UR", "DR", "DL", "C")
SIGMA = gen.CALIB["sigma_mm"]                           # la penumbra del generador: 2.3 mm
PESOS_DEL_GRIS = {"B": 0.114, "G": 0.587, "R": 0.299}  # cv2.COLOR_BGR2GRAY
BETA = 0.05                                             # mm de ancho por mm de posicion: +-2 mm de FWHM a +-40 mm
BANDAS_DE_100 = 79                                      # 2 K + 1 con K = floor(0.4 x 99.8 mm / 1 mm - 1/2) = 39


def _pm():
    """El modulo, importado POR PRUEBA: en HEAD (sin lo de C.3) el archivo se colecciona y cada prueba cae con su error."""
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _P(**cambios):
    # OD.1 (DA-87): la netOD es la base por omision del analisis y el rojo de la sintetica (y de las peliculas a 800 UM) esta recortado en ella; las pruebas de este
    # archivo fijan verdades del VALOR DE PIXEL (el generador de PF.0 las da en esa base), asi que la fijan explicitamente para seguir probando lo mismo. La netOD la
    # prueba `test_od1_densidad_optica.py`.
    return {**_pm().VALORES_DE_LA_GEOMETRIA, "base_de_la_medida": _pm().BASE_VALOR_DE_PIXEL, **cambios}


def _real(clave):
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"HI-0: la pelicula real {clave} no esta (ImagenesDeReferencia/PlacasHistoricas)")
    return ruta


# ======================================================================================================================================= los ORACULOS
# Independientes del motor: usan solo el generador de PF.0 y formulas cerradas. Nada de lo que sigue importa `analisisImagenes` (salvo para llamarlo).
def nivel_de_capa(calib, capa, D):
    """El nivel crudo SIN ruido que el generador da a una dosis relativa D en `capa` (B, G, R) o en el gris (la combinacion BGR2GRAY de las tres)."""
    if capa == "gris":
        return sum(peso * nivel_de_capa(calib, c, D) for c, peso in PESOS_DEL_GRIS.items())
    i = gen.INDICE_CAPA[capa]
    virgen, meseta = calib["virgen_bgr"][i], calib["meseta_bgr"][i]
    return virgen - (virgen - meseta) * gen._g(D, calib["k_bgr"][i])


def bordes_esperados(campo, calib, capa, eje, linea_mm, piso, meseta=None, fraccion=0.5):
    """(menor, mayor) en mm del sistema de la pelicula (origen: centro del campo de radiacion) donde el nivel de `capa` cruza `piso - fraccion * (piso - meseta)` a lo largo de la fila v = `linea_mm`
    (crossplane) o de la columna u = `linea_mm` (inplane). `meseta`: el nivel en el eje (dosis 1) si no se da."""
    if meseta is None:
        meseta = float(nivel_de_capa(calib, capa, 1.0))
    nivel = piso - fraccion * (piso - meseta)
    if eje == "crossplane":
        def f(u):
            return float(nivel_de_capa(calib, capa, campo.dosis(np.array(u), np.array(linea_mm)))) - nivel
        semi = campo.ancho_x(linea_mm) / 2.0
    else:
        def f(v):
            return float(nivel_de_capa(calib, capa, campo.dosis(np.array(linea_mm), np.array(v)))) - nivel
        semi = campo.wy / 2.0
    return (brentq(f, -(semi + 8 * SIGMA), -(semi - 6 * SIGMA), xtol=1e-10), brentq(f, semi - 6 * SIGMA, semi + 8 * SIGMA, xtol=1e-10))


def linea_de_la_banda(verdad, eje, k, banda_mm=1.0):
    """La coordenada, en el sistema de la pelicula (mm desde el centro del campo de RADIACION), de la linea central de la banda k: el cruce de diagonales luminosas mas k bandas."""
    lcx, lcy = verdad.centro_luz
    return (lcy if eje == "crossplane" else lcx) + k * banda_mm


def meseta_media_de_la_linea(verdad, capa, eje, linea_mm, calib=None, fraccion=0.8, excepcion_mm=3.8):
    """El nivel de `capa` que el plan llama la meseta (R9, paso 7) de la LINEA `linea_mm`: el promedio de la zona central de esa linea calculado de la respuesta SIN ruido del generador (no del motor):
    sobre [centro - e, centro + e], con e = `fraccion` / 2 x la distancia entre los dos bordes luminosos de esa linea, sin los +-`excepcion_mm` alrededor del reticulo."""
    calib = gen.CALIB if calib is None else calib
    lcx, lcy = verdad.centro_luz
    luz = verdad.bordes_luz
    rx, ry = verdad.reticulo_menos_luz
    if eje == "crossplane":
        centro, ancho, reticulo = lcx, luz["R"] - luz["L"], lcx + rx
    else:
        centro, ancho, reticulo = lcy, luz["B"] - luz["T"], lcy + ry
    s = np.arange(centro - fraccion / 2 * ancho, centro + fraccion / 2 * ancho, 0.005)
    s = s[np.abs(s - reticulo) > excepcion_mm]
    dosis = verdad.campo.dosis(s, linea_mm) if eje == "crossplane" else verdad.campo.dosis(linea_mm, s)
    return float(np.mean(nivel_de_capa(calib, capa, dosis)))


def fwhm_esperado(verdad, capa, eje, k, piso, calib=None, con_meseta_media=False):
    """El FWHM que PREDICE el generador para la banda k de `capa` si el piso es `piso`: contra el nivel del centro de la linea (la dosis) o, con `con_meseta_media`, contra la meseta como la define el plan."""
    calib = gen.CALIB if calib is None else calib
    linea = linea_de_la_banda(verdad, eje, k)
    meseta = meseta_media_de_la_linea(verdad, capa, eje, linea, calib) if con_meseta_media else None
    menor, mayor = bordes_esperados(verdad.campo, calib, capa, eje, linea, piso, meseta=meseta)
    return mayor - menor


def k_esperado(longitud_mm, fraccion=0.8, banda_mm=1.0):
    """K = floor(fraccion / 2 x L / banda - 1/2): la mayor banda cuyo borde de afuera (k + 1/2 bandas) cabe en +-fraccion / 2 de la distancia L entre los bordes luminosos."""
    return int(math.floor(fraccion / 2 * longitud_mm / banda_mm - 0.5))


def longitud_perpendicular(verdad, eje):
    """L: la distancia entre los dos bordes luminosos de la linea central PERPENDICULAR al eje del barrido (el generador pone un rectangulo): la altura para el crossplane, el ancho para el inplane."""
    luz = verdad.bordes_luz
    return (luz["B"] - luz["T"]) if eje == "crossplane" else (luz["R"] - luz["L"])


def cruce_de_diagonales(ul, ur, dr, dl):
    """La interseccion de UL-DR con UR-DL (resolviendo el sistema 2 x 2 de las dos rectas; independiente de la formula del modulo)."""
    a = np.array([[dr[0] - ul[0], dl[0] - ur[0]], [dr[1] - ul[1], dl[1] - ur[1]]], dtype=float)
    t = np.linalg.solve(a, np.array([ur[0] - ul[0], ur[1] - ul[1]], dtype=float))
    return (ul[0] + t[0] * (dr[0] - ul[0]), ul[1] + t[0] * (dr[1] - ul[1]))


def lado_en_la_linea(a, b, eje_fijo, valor):
    """La coordenada del lado a-b donde la otra coordenada vale `valor` (interseccion de una recta con un segmento, a mano): eje_fijo 1 da x en la fila y = valor, eje_fijo 0 da y en la columna x = valor."""
    (xa, ya), (xb, yb) = a, b
    if eje_fijo == 1:
        return xa + (valor - ya) * (xb - xa) / (yb - ya)
    return ya + (valor - xa) * (yb - ya) / (xb - xa)


# ======================================================================================================================================= comparar a fondo
def iguales(a, b):
    """Igualdad EXACTA, campo por campo, de dos medidas (dataclasses, tuplas, listas, diccionarios, arreglos y escalares). Los NaN de un arreglo cuentan como iguales; un float distinto por 1e-15 no."""
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return isinstance(a, np.ndarray) and isinstance(b, np.ndarray) and a.shape == b.shape and a.dtype == b.dtype and bool(np.array_equal(a, b, equal_nan=True))
    if dataclasses.is_dataclass(a) and not isinstance(a, type):
        return type(a) is type(b) and all(iguales(getattr(a, f.name), getattr(b, f.name)) for f in dataclasses.fields(a))
    if isinstance(a, (tuple, list)):
        return type(a) is type(b) and len(a) == len(b) and all(iguales(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(iguales(a[k], b[k]) for k in a)
    return a == b


# ======================================================================================================================================= las peliculas
def puntos_exactos(verdad):
    """Los centros verdaderos de las marcas en pixeles (floats): UL, UR, DR, DL y el reticulo."""
    return [verdad.marcas_px[k] for k in ORDEN_DE_LOS_PUNTOS]


def sintetica(formato="tiff", variante="A", theta=0.0, seed=1, **opciones):
    """(verdad, Pelicula) de la pelicula sintetica de PF.0 pasada por el lector de A.1 (el camino real de un archivo)."""
    placa = gen.generar(formato, variante=variante, theta_deg=theta, seed=seed, **opciones)
    return placa.verdad, _pel().leer_pelicula(placa.datos)


def virgen_sintetica(P=None):
    """La referencia de una pelicula virgen sintetica (meseta = virgen, sin dosis ni tinta, fondo de escaner puro) medida con `piso_de_pelicula_virgen` de A.3."""
    calib = dict(gen.CALIB, meseta_bgr=gen.CALIB["virgen_bgr"], fondo_escaner=255.0)
    imagen, _ = gen.generar_arreglo(variante="A", theta_deg=0.0, bits=8, dpi=600, tinta=False, calib=calib)
    imagen = np.array(imagen)
    imagen[imagen.min(axis=2) >= 235] = 255
    return _pel().piso_de_pelicula_virgen(gen.codificar(imagen, "tiff", 600), _P() if P is None else P, "virgen_sintetica.tif", fecha_calculo="2026-10-18")


MOTA = [{"tipo": "rayon_v", "u_mm": -44.0, "largo_mm": 2.0, "valor": 120.0, "ancho_px": 40}]      # (f): 1.7 mm de ancho y 2 mm de largo, a 44 mm del centro, ya dentro del campo
RAYON = [{"tipo": "rayon_h", "v_mm": -1.0, "largo_mm": 90.0, "valor": 250.0, "ancho_px": 60}]     # un rayon blanco de 2.5 mm de alto y 90 mm de largo sobre la linea central del crossplane


def calib_con_campo(ancho_luz, alto_luz, ancho_rad=None, alto_rad=None):
    """La calibracion del generador con otro campo luminoso (y la radiacion y la pelicula del mismo tamano relativo que las de siempre: 0.4 mm mas ancha y 0.8 mm mas baja que la luz, 15.4 y 16.2 mm de
    margen en total, el campo 0.2 mm a la izquierda y 2.7 mm arriba del centro de la pelicula)."""
    pw, ph = ancho_luz + 15.4, alto_luz + 16.2
    return dict(gen.CALIB, campo_luz_mm=(ancho_luz, alto_luz),
                campo_rad_mm=(ancho_luz + 0.4 if ancho_rad is None else ancho_rad, alto_luz - 0.8 if alto_rad is None else alto_rad),
                pelicula_mm=(pw, ph), campo_en_pelicula_mm=(pw / 2 - 0.2, ph / 2 - 2.7))


class Ficha:
    """Lo que varias pruebas leen de una escena SIN guardar la pelicula ni el resultado entero (~130 MB cada uno): la verdad, el barrido y lo ligero del resultado."""

    def __init__(self, verdad, res, b):
        self.verdad, self.barrido = verdad, b
        self.estado = res.estado
        self.parametros = res.parametros
        self.geometria = res.geometria
        self.bordes_luz_px = res.bordes_luz_px
        self.capas = res.capas
        self.pisos = {c: res.capas[c].piso for c in CAPAS}
        self.cruce = None if res.girada is None else res.girada.cruce
        self.origen = None if res.girada is None else res.girada.origen


class Base(Ficha):
    """La escena de siempre CON la pelicula y el resultado entero: las pruebas que los necesitan (el resultado no cambia, no se gira de nuevo, la memoria). `antes`: la instantanea del resultado
    tomada ANTES de la primera llamada a `barrido` (la que hace la fixture): sin ella, un barrido que pisara el resultado lo haria ya en la fixture y las pruebas compararian contra lo ya pisado."""

    def __init__(self, verdad, pelicula, puntos, res, b, tiempo, antes):
        super().__init__(verdad, res, b)
        self.pelicula, self.puntos, self.resultado, self.tiempo, self.antes = pelicula, puntos, res, tiempo, antes


@pytest.fixture(scope="module")
def banco():
    """Lo caro que varias pruebas comparten (escenas, la virgen, las reales). Vive lo que dura el modulo y se suelta al terminar (T10: sin caches de modulo)."""
    cosas = {}
    yield cosas
    cosas.clear()
    gc.collect()


@pytest.fixture(scope="module")
def virgen(banco):
    if "virgen" not in banco:
        banco["virgen"] = virgen_sintetica()
    return banco["virgen"]


@pytest.fixture(scope="module")
def base(banco):
    """La sintetica de siempre: recorte ajustado, giro de 0.4 grados, ruido del escaner, marcas exactas, piso automatico; con la pelicula y el resultado entero."""
    verdad, pelicula = sintetica(variante="A", theta=0.4, seed=1)
    puntos = puntos_exactos(verdad)
    res = _pm().analizar(pelicula, puntos, _P())
    antes = instantanea(res)
    t0 = time.perf_counter()
    b = _pm().barrido(res)
    banco["base"] = Base(verdad, pelicula, puntos, res, b, time.perf_counter() - t0, antes)
    return banco["base"]


def escena(banco, clave, *, modo=None, virgen=None, P=None, variante="A", theta=0.4, seed=1, **opciones):
    """Una escena sintetica ligera (la `Ficha`): arma la pelicula, la mide, la barre y suelta la pelicula y el resultado."""
    if clave not in banco:
        verdad, pelicula = sintetica(variante=variante, theta=theta, seed=seed, **opciones)
        extra = {} if modo is None else dict(modo_piso=modo, referencia_virgen=virgen)
        res = _pm().analizar(pelicula, puntos_exactos(verdad), _P() if P is None else P, **extra)
        banco[clave] = Ficha(verdad, res, _pm().barrido(res))
        del res, pelicula
        gc.collect()
    return banco[clave]


def huella_de_los_arreglos(res):
    """El sha256 de las cuatro capas giradas y de las dos mascaras (sin armar una copia de todo junto)."""
    h = hashlib.sha256()
    for a in [*res.girada.capas.values(), res.girada.validos, res.girada.pelicula]:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


@pytest.fixture(scope="module")
def trapecio(banco, virgen):
    """Las esquinas marcadas 1.5 mm fuera de un rectangulo (UL abajo, UR a la derecha y arriba, DR a la izquierda y abajo, DL arriba): los cuatro lados quedan inclinados (~1.7 grados)."""
    if "trapecio" not in banco:
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=1, ruido=0)
        p = puntos_exactos(verdad)
        d = 1.5 / TAM                                   # 1.5 mm en pixeles
        p[0] = (p[0][0], p[0][1] + d)                   # UL 1.5 mm hacia abajo
        p[1] = (p[1][0] + d, p[1][1] - d)               # UR 1.5 mm a la derecha y 1.5 mm hacia arriba
        p[2] = (p[2][0] - d, p[2][1] + d)               # DR 1.5 mm a la izquierda y 1.5 mm hacia abajo
        p[3] = (p[3][0], p[3][1] - d)                   # DL 1.5 mm hacia arriba
        res = _pm().analizar(pelicula, p, _P(), modo_piso="virgen", referencia_virgen=virgen)
        banco["trapecio"] = Ficha(verdad, res, _pm().barrido(res))
        del res, pelicula
        gc.collect()
    return banco["trapecio"]


@pytest.fixture(scope="module")
def con_beta(banco, virgen):
    return escena(banco, "beta", modo="virgen", virgen=virgen, beta=BETA)


@pytest.fixture(scope="module")
def con_cupula(banco, virgen):
    return escena(banco, "cupula", modo="virgen", virgen=virgen, cupula_pct_40mm=-4.0)


@pytest.fixture(scope="module")
def campo_80x110(banco, virgen):
    return escena(banco, "campo_80x110", modo="virgen", virgen=virgen, calib=calib_con_campo(80.0, 110.0), ruido=0)


@pytest.fixture(scope="module")
def las_dos(banco):
    """La misma pelicula (sin ruido) limpia y con la mota de (f)."""
    limpia = escena(banco, "limpia_sin_ruido", theta=0.0, seed=2, ruido=0)
    mota = escena(banco, "con_mota", theta=0.0, seed=2, ruido=0, defectos=MOTA)
    return limpia, mota


@pytest.fixture(scope="module")
def muy_inclinada(banco, virgen):
    """beta = 0.16 en una pelicula de 135 x 136 mm: el campo llega a 94 y 110 mm de ancho y el rojo de los extremos cabe en la pelicula."""
    return escena(banco, "beta_grande", modo="virgen", virgen=virgen, beta=0.16, ruido=0, calib=dict(gen.CALIB, pelicula_mm=(135.0, 136.0), campo_en_pelicula_mm=(67.3, 65.3)))


def instantanea(res):
    """Todo lo que `barrido` no puede cambiar de un resultado: los numeros (`como_dict`), la pelicula girada (sha256), los parametros (copia profunda), las capas y los bordes luminosos (los objetos) y, de cada corte
    central, el objeto y una copia profunda."""
    return dict(firma=json.dumps(res.como_dict(), sort_keys=True, default=str), huella=huella_de_los_arreglos(res), parametros=copy.deepcopy(res.parametros), capas=dict(res.capas),
                bordes=dict(res.bordes_luz_px), estado=res.estado, centrales={(c, e): (getattr(res.capas[c], e), copy.deepcopy(getattr(res.capas[c], e))) for c in CAPAS for e in EJES})


def bandas_de(b, eje, capa):
    return b.ejes[eje].capas[capa].bandas


def fwhm_de(b, eje, capa):
    return [x.fwhm_mm for x in bandas_de(b, eje, capa)]


def coherente(b):
    """(R1-01) Lo que cualquier barrido cumple entre sus bandas, sus capas, sus ejes y su raiz, escrito aparte del modulo: una capa es «ok» si y solo si alguna de sus bandas se midio (tambien con UNA sola),
    el conteo de medibles es el de las bandas «ok», y la raiz es «ok» si y solo si alguna capa de algun eje lo es; lo que no es «ok» dice «no medible»."""
    alguna = False
    for e in b.ejes.values():
        for c in e.capas.values():
            medibles = [x for x in c.bandas if x.ok]
            assert c.estadistica.n_bandas == len(c.bandas) and c.estadistica.n_medibles == len(medibles), (e.eje, c.capa)
            assert c.ok == bool(medibles) == (c.estado == "ok") and (c.ok or c.estado.startswith("no medible")), (e.eje, c.capa, c.estado)
            alguna = alguna or c.ok
    assert b.ok == alguna == (b.estado == "ok") and (b.ok or b.estado.startswith("no medible")), b.estado


def recortada(res, eje):
    """(R1-03) La pelicula girada de `res` recortada a 10.5 mm del cruce (en filas para el crossplane, en columnas para el inplane: las bandas que quedan fuera de ella no se pueden sacar) y el barrido de
    ese resultado: (la pelicula recortada, el barrido)."""
    g = res.girada
    perp = 1 if eje == "crossplane" else 0
    corte = int(math.ceil(g.cruce[perp] + 10.5 / TAM)) - g.origen[perp]
    recortar = (lambda a: a[:corte]) if eje == "crossplane" else (lambda a: a[:, :corte])
    corto = dataclasses.replace(g, capas={n: recortar(a) for n, a in g.capas.items()}, validos=recortar(g.validos), pelicula=recortar(g.pelicula))
    return corto, _pm().barrido(dataclasses.replace(res, girada=corto))


def _lista(par):
    return None if par is None else [None if x is None else float(x) for x in par]


def como_dict_esperado(b):
    """(R1-02) El `como_dict` que DEBE dar un barrido, armado aqui desde los atributos publicos de sus objetos y sin llamar a ningun `como_dict`: la raiz, cada eje, cada capa con su estadistica y cada banda."""
    def banda(x):
        m = x.medida
        return {"k": int(x.k), "posicion_mm": float(x.posicion_mm), "linea_px": float(x.linea_px), "estado": m.estado, "fwhm_mm": m.fwhm_mm, "centro_rad_px": m.centro_rad_px,
                "bordes_rad_px": _lista(m.bordes_rad_px), "bordes_luz_px": _lista(m.bordes_luz_px), "banda_px": None if m.perfil is None else _lista(m.perfil.filas_px)}

    def capa(c):
        s = c.estadistica
        return {"estado": c.estado, "estadistica": {"n_bandas": s.n_bandas, "n_medibles": s.n_medibles, "media_mm": s.media_mm, "mediana_mm": s.mediana_mm, "desviacion_mm": s.desviacion_mm},
                "bandas": [banda(x) for x in c.bandas]}

    def eje(e):
        return {"estado": e.estado, "perpendicular": e.perpendicular, "longitud_perpendicular_mm": e.longitud_perpendicular_mm, "k_maximo": e.k_maximo, "zona_px": _lista(e.zona_px),
                "zona_mm": _lista(e.zona_mm), "banda_mm": e.banda_mm, "capas": {n: capa(c) for n, c in e.capas.items()}}
    return {"version": b.version, "estado": b.estado, "tam_mm": b.tam_mm, "ejes": {n: eje(e) for n, e in b.ejes.items()}}


# ======================================================================================================================================= (a) la verdad del generador
class TestElBarridoSigueLaVerdadDelGenerador:
    """(a) del bloque: una pelicula cuyo ancho crece linealmente con la posicion (w_x(v) = w_x0 + beta v). El generador (independiente del motor) da el FWHM de CADA banda en SU posicion; el cuaderno pierde
    las que se salen de +-5 % y su eje es un indice. Piso virgen (el modo «virgen» de A.3): la verdad de la dosis aplica en el azul, y en las demas capas la respuesta del propio generador."""

    @pytest.mark.parametrize("capa", CAPAS)
    def test_cada_banda_del_crossplane_cae_donde_predice_el_generador_en_su_posicion(self, con_beta, capa):
        f = con_beta
        c = f.barrido.ejes["crossplane"].capas[capa]
        assert c.estado == "ok" and c.estadistica.n_bandas == BANDAS_DE_100 == c.estadistica.n_medibles == len(c.bandas)
        errores = [b.fwhm_mm - fwhm_esperado(f.verdad, capa, "crossplane", b.k, f.pisos[capa]) for b in c.bandas]
        assert max(abs(e) for e in errores) <= 0.15, max(errores, key=abs)
        # el sesgo medio de las 79 bandas: un corrimiento de una banda (beta x 1 mm = 0.05 mm) lo delata aunque cada banda este dentro de +-0.15
        assert abs(float(np.mean(errores))) <= 0.02, float(np.mean(errores))

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_fwhm_crece_con_la_posicion_en_mm_con_la_pendiente_de_beta(self, con_beta, capa):
        """El eje es la posicion en mm (no un indice): la pendiente del FWHM contra `posicion_mm` es beta (0.05 mm por mm), y el FWHM de la banda 0 es el del centro."""
        f = con_beta
        bandas = bandas_de(f.barrido, "crossplane", capa)
        x = np.array([b.posicion_mm for b in bandas])
        y = np.array([b.fwhm_mm for b in bandas])
        pendiente, corte = np.polyfit(x, y, 1)
        assert pendiente == pytest.approx(BETA, rel=0.03), pendiente
        esperado_en_0 = fwhm_esperado(f.verdad, capa, "crossplane", 0, f.pisos[capa])
        assert corte == pytest.approx(esperado_en_0, abs=0.03)
        assert all(y[i + 1] > y[i] - 0.1 for i in range(len(y) - 1)), "crece con la posicion (cada banda no baja de la anterior mas que el ruido)"
        assert y[-1] - y[0] == pytest.approx(BETA * 78.0, abs=0.12)

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_inplane_no_cambia_con_la_posicion_cuando_solo_cambia_el_ancho_de_la_rendija(self, con_beta, capa):
        """Con beta el ancho en x crece con v, pero la altura del campo (el FWHM inplane de cada columna dentro de la meseta) no cambia: las 79 bandas del inplane valen lo mismo, y lo que dice el generador."""
        f = con_beta
        y = np.array(fwhm_de(f.barrido, "inplane", capa))
        assert len(y) == BANDAS_DE_100 and float(y.max() - y.min()) <= 0.12, float(y.max() - y.min())
        assert float(np.median(y)) == pytest.approx(fwhm_esperado(f.verdad, capa, "inplane", 0, f.pisos[capa]), abs=0.08)

    def test_las_posiciones_de_las_bandas_son_los_mm_del_cruce_y_las_filas_usadas_estan_donde_dice_la_posicion(self, con_beta):
        """`posicion_mm` es k x banda_perfil_mm, positiva hacia abajo en el crossplane (y) y hacia la derecha en el inplane (x); la banda usa de verdad las filas (columnas) que estan a esa distancia del cruce."""
        f = con_beta
        for eje, i in (("crossplane", 1), ("inplane", 0)):
            for capa in CAPAS:
                for b in bandas_de(f.barrido, eje, capa):
                    assert b.posicion_mm == pytest.approx(float(b.k), abs=1e-12)
                    primera, fin = b.medida.perfil.filas_px
                    centro_de_las_filas = ((primera + fin - 1) / 2.0 - f.cruce[i]) * TAM
                    assert centro_de_las_filas == pytest.approx(b.posicion_mm, abs=0.5 * TAM + 1e-9), (eje, capa, b.k)


# ======================================================================================================================================= (b) la cupula
class TestLaCupulaEstrechaLosExtremosDeLasCapasSaturadas:
    """(b) del bloque: con una cupula como la de las peliculas reales (-4 % a 40 mm) la meseta de una banda que no esta en el centro es MAS BAJA, el 50 % de esa media cae mas adentro y las bandas
    de los extremos salen mas angostas en las capas saturadas. El oraculo es la definicion del plan (la meseta es el promedio de la zona de ESA banda, calculado de la respuesta del generador)."""

    @pytest.mark.parametrize("eje", EJES)
    @pytest.mark.parametrize("capa", CAPAS)
    def test_cada_banda_mide_lo_que_define_el_plan_con_la_meseta_de_su_propia_zona(self, con_cupula, capa, eje):
        f = con_cupula
        errores = [b.fwhm_mm - fwhm_esperado(f.verdad, capa, eje, b.k, f.pisos[capa], con_meseta_media=True) for b in bandas_de(f.barrido, eje, capa)]
        assert len(errores) == BANDAS_DE_100
        assert max(abs(e) for e in errores) <= 0.09, max(errores, key=abs)       # medido: <= 0.073 en el azul (el de menor contraste), <= 0.03 en las demas
        assert abs(float(np.mean(errores))) <= 0.015

    @pytest.mark.parametrize("eje", EJES)
    @pytest.mark.parametrize("capa, extremo_menos_centro, tolerancia", [("R", -0.117, 0.03), ("G", -0.046, 0.03), ("gris", -0.052, 0.03)])
    def test_las_bandas_de_los_extremos_de_las_capas_saturadas_son_mas_angostas_y_la_prueba_fija_cuanto(self, con_cupula, capa, eje, extremo_menos_centro, tolerancia):
        """Promedio de las 5 bandas de cada extremo menos el de las 5 centrales: -0.117 mm el rojo, -0.046 el verde y -0.052 el gris (lo que da el oraculo de la definicion del plan con una cupula de -4 %).
        El plan midio -0.3 a -0.95 en el rojo y hasta -0.43 en el verde de las peliculas reales (que tienen mas cupula): las diez estan abajo."""
        f = con_cupula
        y = {b.k: b.fwhm_mm for b in bandas_de(f.barrido, eje, capa)}
        k_max = f.barrido.ejes[eje].k_maximo
        extremos = np.mean([y[s * k] for s in (-1, 1) for k in range(k_max - 4, k_max + 1)])
        centro = np.mean([y[k] for k in range(-2, 3)])
        assert float(extremos - centro) == pytest.approx(extremo_menos_centro, abs=tolerancia), float(extremos - centro)
        oraculo = [fwhm_esperado(f.verdad, capa, eje, s * k, f.pisos[capa], con_meseta_media=True) for s in (-1, 1) for k in range(k_max - 4, k_max + 1)]
        oraculo_centro = [fwhm_esperado(f.verdad, capa, eje, k, f.pisos[capa], con_meseta_media=True) for k in range(-2, 3)]
        assert float(np.mean(oraculo) - np.mean(oraculo_centro)) == pytest.approx(extremo_menos_centro, abs=0.005), "el numero fijado es el del oraculo, no el de la salida del motor"

    def test_sin_cupula_las_bandas_de_los_extremos_no_son_mas_angostas_que_las_del_centro(self, banco, virgen):
        """Con la meseta plana la media de la zona es el nivel del centro de cada banda y ningun extremo se aparta del centro: es la cupula (y no el barrido) la que las angosta."""
        f = escena(banco, "plana", modo="virgen", virgen=virgen)
        for eje in EJES:
            for capa in CAPAS:
                y = np.array(fwhm_de(f.barrido, eje, capa))
                assert float(y.max() - y.min()) <= 0.12, (eje, capa)


# ======================================================================================================================================= (c) la region
class TestLaRegionEsLaZonaCentralDeLaMeseta:
    """(c) del bloque: +-40 % de la distancia entre los bordes luminosos de la linea central perpendicular, alrededor del cruce de diagonales. Sale de las marcas: no de ningun perfil medido."""

    def test_en_un_10_por_10_son_79_bandas_de_menos_39_a_mas_39_y_la_zona_es_la_del_perfil_perpendicular(self, base):
        b = base.barrido
        assert b.ejes["crossplane"].k_maximo == b.ejes["inplane"].k_maximo == 39
        for eje in EJES:
            e = b.ejes[eje]
            assert e.estado == "ok" and e.perpendicular == PERPENDICULAR[eje] and e.banda_mm == 1.0
            assert e.ks == tuple(range(-39, 40)) and len(e.ks) == BANDAS_DE_100
            for capa in CAPAS:
                assert tuple(x.k for x in e.capas[capa].bandas) == e.ks, "las cuatro capas se barren en las mismas posiciones"
                # la zona del barrido ES la zona central de la meseta del perfil perpendicular (la de C.2): la misma, bit a bit
                assert e.zona_px == getattr(base.resultado.capas[capa], PERPENDICULAR[eje]).zona_px
        assert b.ejes["crossplane"].longitud_perpendicular_mm == pytest.approx(longitud_perpendicular(base.verdad, "crossplane"), abs=1e-3)
        assert b.ejes["inplane"].longitud_perpendicular_mm == pytest.approx(longitud_perpendicular(base.verdad, "inplane"), abs=1e-3)

    @pytest.mark.parametrize("ancho, alto", [(80.0, 80.0), (120.0, 120.0)])
    def test_la_region_escala_con_el_campo_luminoso_y_es_la_misma_en_las_cuatro_capas(self, banco, virgen, ancho, alto):
        """80 mm: +-32 mm, K = 31 (31.5 bandas caben; con la banda 32 el borde de afuera pasaria de 32); 120 mm: +-48 mm, K = 47. El cuaderno llega a +-44.5 mm en cualquier campo."""
        f = escena(banco, f"campo_{ancho:g}x{alto:g}", modo="virgen", virgen=virgen, calib=calib_con_campo(ancho, alto), ruido=0)
        assert f.estado == "ok"
        for eje in EJES:
            e = f.barrido.ejes[eje]
            largo = longitud_perpendicular(f.verdad, eje)
            assert e.k_maximo == k_esperado(largo) == (31 if ancho == 80.0 else 47)
            assert e.zona_mm == pytest.approx((-0.4 * largo, 0.4 * largo), abs=2e-3)
            assert e.zona_px[1] - e.zona_px[0] == pytest.approx(0.8 * largo / TAM, abs=0.1)
            assert (e.zona_px[0] + e.zona_px[1]) / 2 == pytest.approx(f.cruce[1 if eje == "crossplane" else 0], abs=1e-6), "la zona esta centrada en el cruce, a lo largo del eje de la zona"
            for capa in CAPAS:
                assert tuple(x.k for x in e.capas[capa].bandas) == tuple(range(-e.k_maximo, e.k_maximo + 1))

    @pytest.mark.parametrize("eje", EJES)
    def test_ninguna_banda_cae_fuera_de_la_zona_y_la_siguiente_ya_no_cabria(self, base, eje):
        """Las filas (columnas) de las 79 bandas tienen su centro DENTRO de la zona; la banda K + 1 tendria su borde de afuera pasado de ella. Las bandas son contiguas, sin huecos ni solapes, y cada fila
        esta en la banda que contiene su centro."""
        e = base.barrido.ejes[eje]
        i = 1 if eje == "crossplane" else 0
        ancho_px = 1.0 / TAM
        cruce = base.resultado.girada.cruce[i]
        for capa in CAPAS:
            filas = [x.medida.perfil.filas_px for x in e.capas[capa].bandas]
            assert filas[0][0] >= e.zona_px[0] and filas[-1][1] - 1 <= e.zona_px[1]
            for (a0, a1), (b0, b1) in zip(filas, filas[1:]):
                assert a1 == b0, "contiguas: la primera fila de una banda es la que sigue a la ultima de la anterior"
            for x in e.capas[capa].bandas:
                primera, fin = x.medida.perfil.filas_px
                dentro = {r for r in range(primera - 3, fin + 3) if cruce + (x.k - 0.5) * ancho_px <= r < cruce + (x.k + 0.5) * ancho_px}
                assert set(range(primera, fin)) == dentro, (capa, x.k)
        extremo_mm = (e.zona_px[1] - cruce) * TAM
        assert (e.k_maximo + 0.5) <= extremo_mm < (e.k_maximo + 1.5), "K es la mayor banda cuyo borde de afuera cabe en la zona"

    def test_la_region_no_depende_de_ningun_perfil_medido_ni_cambia_si_se_altera_el_perfil_perpendicular(self, banco, virgen, base):
        """Una pelicula igual pero con la radiacion de 92 mm de alto (no 99): el FWHM perpendicular de cada capa cambia 7 mm y la region del barrido NO se mueve (sale de los bordes luminosos). La regla del
        09-10, el 80 % del FWHM perpendicular de cada capa, daba una region por capa (K = 40 en el rojo y 39 en el azul en la base)."""
        f = escena(banco, "radiacion_baja", modo="virgen", virgen=virgen, calib=dict(gen.CALIB, campo_rad_mm=(100.0, 92.0)))
        assert f.estado == "ok"
        perpendiculares = {c: f.capas[c].inplane.fwhm_mm for c in CAPAS}
        assert max(perpendiculares.values()) - min(perpendiculares.values()) > 3.0, "las capas SI miden anchos perpendiculares distintos entre si"
        assert all(abs(perpendiculares[c] - base.capas[c].inplane.fwhm_mm) > 5.0 for c in CAPAS), "y distintos de los de la base (92 contra 99 mm de radiacion)"
        for eje in EJES:
            a, b = f.barrido.ejes[eje], base.barrido.ejes[eje]
            assert a.k_maximo == b.k_maximo == 39 and a.ks == b.ks
            assert a.zona_mm == pytest.approx(b.zona_mm, abs=1e-3) and a.longitud_perpendicular_mm == pytest.approx(b.longitud_perpendicular_mm, abs=1e-3)
            assert all(len(a.capas[c].bandas) == BANDAS_DE_100 for c in CAPAS)

    def test_un_campo_que_no_es_cuadrado_barre_con_la_longitud_perpendicular_de_cada_eje(self, banco, virgen):
        """80 x 110 mm: el crossplane barre la y (alto 110: K = 43) y el inplane la x (ancho 80: K = 31). Un barrido que usara la longitud del propio eje (o la del otro) daria K = 31 y 43."""
        f = escena(banco, "campo_80x110", modo="virgen", virgen=virgen, calib=calib_con_campo(80.0, 110.0), ruido=0)
        assert f.estado == "ok"
        assert f.barrido.ejes["crossplane"].k_maximo == k_esperado(110.0 - 0.0) == 43
        assert f.barrido.ejes["inplane"].k_maximo == k_esperado(80.0) == 31
        assert len(bandas_de(f.barrido, "crossplane", "G")) == 87 and len(bandas_de(f.barrido, "inplane", "G")) == 63


# ======================================================================================================================================= (d) banda 0 = corte central
class TestLaBandaCeroEsElCorteCentral:
    """(d) del bloque: la autoprueba. `perfil_central(..., banda=0)` es el perfil de `analizar` y `medir_perfil` es la misma funcion: la banda 0 del barrido es EXACTAMENTE el corte central."""

    @pytest.mark.parametrize("eje", EJES)
    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_banda_0_es_el_perfil_central_de_analizar_campo_por_campo(self, base, capa, eje):
        banda = base.barrido.ejes[eje].capas[capa].central
        assert banda is not None and banda.k == 0 and banda.posicion_mm == 0.0
        central = getattr(base.resultado.capas[capa], eje)
        assert central.ok and iguales(banda.medida, central), (capa, eje)

    @pytest.mark.parametrize("eje", EJES)
    def test_la_igualdad_es_exacta_tambien_en_una_pelicula_real_con_una_mota(self, banco, eje):
        r = _real_barrido(banco, "EPSON007")
        for capa in CAPAS:
            assert iguales(r.barrido.ejes[eje].capas[capa].central.medida, getattr(r.capas[capa], eje)), (capa, eje)

    def test_el_barrido_no_cambia_el_corte_central_de_analizar(self, base):
        """El barrido nunca modifica el resultado que recibe: las medidas centrales de despues (de la llamada de la fixture y de otra mas) son las de antes de la primera, objeto por objeto y campo por campo."""
        pm = _pm()
        pm.barrido(base.resultado)
        for (c, e), (objeto, copia) in base.antes["centrales"].items():
            assert getattr(base.resultado.capas[c], e) is objeto and iguales(copia, getattr(base.resultado.capas[c], e)), (c, e)


# ======================================================================================================================================= (e) cada eje recorre su direccion
class TestCadaEjeRecorreSuDireccion:
    """(e) del bloque: el crossplane (horizontal) barre filas distintas, es decir, recorre la y; el inplane (vertical) barre columnas distintas, es decir, recorre la x. El cuaderno recorre el rango de la y
    como columnas tambien para el inplane (N11). Un campo de 80 x 110 mm las distingue: la x y la y del cruce son muy distintas y las dos longitudes tambien."""

    def test_las_bandas_del_crossplane_son_filas_alrededor_de_la_y_del_cruce_y_las_del_inplane_columnas_alrededor_de_su_x(self, campo_80x110):
        f = campo_80x110
        assert abs(f.cruce[0] - f.cruce[1]) > 100.0, "la x y la y del cruce son muy distintas (si fueran iguales, cruzar los ejes pasaria sin que nadie lo vea)"
        cruce_luz = _pm()._cruce_de_diagonales(*f.geometria.esquinas_giradas)
        for capa in CAPAS:
            for x in f.barrido.ejes["crossplane"].capas[capa].bandas:
                assert x.linea_px == pytest.approx(f.cruce[1] + x.k / TAM, abs=1e-6)
            for x in f.barrido.ejes["inplane"].capas[capa].bandas:
                assert x.linea_px == pytest.approx(f.cruce[0] + x.k / TAM, abs=1e-6)
            # la linea de la banda 0 es EXACTAMENTE el cruce de las diagonales luminosas (el que usa `analizar` para el corte central), no el cruce girado que difiere en el ultimo bit
            assert f.barrido.ejes["crossplane"].capas[capa].central.linea_px == cruce_luz[1] and f.barrido.ejes["inplane"].capas[capa].central.linea_px == cruce_luz[0]
            c0 = f.barrido.ejes["crossplane"].capas[capa].central.medida.perfil.filas_px
            i0 = f.barrido.ejes["inplane"].capas[capa].central.medida.perfil.filas_px
            assert c0[0] <= f.cruce[1] <= c0[1] and i0[0] <= f.cruce[0] <= i0[1]
            for x in f.barrido.ejes["crossplane"].capas[capa].bandas:
                assert x.medida.eje == "crossplane" and x.medida.perfil.eje == "crossplane"
            for x in f.barrido.ejes["inplane"].capas[capa].bandas:
                assert x.medida.eje == "inplane" and x.medida.perfil.eje == "inplane"

    def test_cada_banda_lleva_el_eje_la_capa_y_el_centro_a_lo_largo_de_su_propio_eje(self, campo_80x110):
        f = campo_80x110
        for eje, i in (("crossplane", 0), ("inplane", 1)):
            for capa in CAPAS:
                for x in bandas_de(f.barrido, eje, capa):
                    assert x.medida.eje == eje and x.medida.capa == capa and x.medida.centro_px == pytest.approx(f.cruce[i], abs=1e-12)

    def test_cada_eje_se_barre_en_su_longitud_perpendicular_y_se_mide_de_verdad_en_el_campo_que_no_es_cuadrado(self, campo_80x110):
        """Ademas de contar las bandas, las del inplane (63 columnas de la x) miden el FWHM vertical de 109.2 mm del generador y las del crossplane (87 filas de la y) el horizontal de 80.4 mm."""
        f = campo_80x110
        for capa in CAPAS:
            assert f.barrido.ejes["crossplane"].capas[capa].estadistica.n_medibles == 87 and f.barrido.ejes["inplane"].capas[capa].estadistica.n_medibles == 63
            assert f.barrido.ejes["crossplane"].capas[capa].estadistica.mediana_mm == pytest.approx(fwhm_esperado(f.verdad, capa, "crossplane", 0, f.pisos[capa]), abs=0.12)
            assert f.barrido.ejes["inplane"].capas[capa].estadistica.mediana_mm == pytest.approx(fwhm_esperado(f.verdad, capa, "inplane", 0, f.pisos[capa]), abs=0.12)


# ======================================================================================================================================= (f) la mota
class TestUnaMotaMueveElCorteCentralYNoLaMediana:
    """(f) del bloque: una mota clara y ancha sobre la linea central (1.7 mm de ancho, 2 mm de largo, a 44 mm del centro, ya dentro del campo) esta en el primer cruce desde la meseta: mueve el corte
    central (bandas -1 y 0) varios mm y deja las otras 77 en su sitio. La mediana del barrido no se mueve; la media se arrastra. La diferencia entre el corte central y la mediana ES la señal."""

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_mota_mueve_el_corte_central_y_no_la_mediana(self, las_dos, capa):
        limpia, mota = las_dos
        a, b = limpia.barrido.ejes["crossplane"].capas[capa], mota.barrido.ejes["crossplane"].capas[capa]
        assert a.estadistica.n_medibles == b.estadistica.n_medibles == BANDAS_DE_100
        assert a.central.fwhm_mm - b.central.fwhm_mm > 5.0, "el corte central cae varios mm por la mota"
        assert b.estadistica.mediana_mm == pytest.approx(a.estadistica.mediana_mm, abs=0.02)
        assert a.estadistica.mediana_mm - b.central.fwhm_mm > 5.0, "y se ve como la diferencia entre el corte central y la mediana"
        assert a.estadistica.media_mm - b.estadistica.media_mm > 0.1, "la media se arrastra"
        movidas = [x.k for x in b.bandas if abs(x.fwhm_mm - a.bandas[x.k + 39].fwhm_mm) > 0.5]
        assert movidas == [-1, 0], "solo las dos bandas que la mota cubre"

    @pytest.mark.parametrize("capa", CAPAS)
    def test_el_inplane_no_ve_la_mota_porque_esta_fuera_de_su_zona(self, las_dos, capa):
        """La mota esta en u = -44 mm: ninguna de las 79 columnas del inplane (|k| <= 39) la toca, y su barrido es el de la pelicula limpia."""
        limpia, mota = las_dos
        assert iguales(limpia.barrido.ejes["inplane"].capas[capa].estadistica, mota.barrido.ejes["inplane"].capas[capa].estadistica)

    def test_epson007_real_la_mediana_aguanta_las_motas_y_la_media_no(self, banco):
        """EPSON007 (azul inplane): despues del suavizado de C.2 el corte central ya no cae a 96.24 mm, pero las bandas con motas siguen ahi (90.99 mm en la +29, 97.45 en la +10): la mediana es 99.2 y la
        media 99.05 con una desviacion de casi 1 mm. Ninguna se descarta."""
        r = _real_barrido(banco, "EPSON007")
        c = r.barrido.ejes["inplane"].capas["B"]
        assert 98.9 < c.estadistica.mediana_mm < 99.6 and c.estadistica.media_mm < c.estadistica.mediana_mm - 0.1 and c.estadistica.desviacion_mm > 0.5
        assert c.estadistica.n_bandas == 77 and c.estadistica.n_medibles >= 75
        assert min(c.bandas, key=lambda x: x.fwhm_mm if x.ok else 1e9).fwhm_mm < 92.0, "la banda de la mota esta en la lista y en la media"


# ======================================================================================================================================= (g) no se descarta nada
class TestNingunaBandaSeDescartaNiSeExcluye:
    """(g) del bloque: el cuaderno guarda solo lo que cae dentro de +-5 % de 100 mm en las tres capas a la vez. Aqui no se filtra ni se excluye nada: una pelicula con beta = 0.16 tiene bandas a 94 y 106 mm
    (6 % de 100) y entran a la lista, a la media y a la mediana."""

    @pytest.mark.parametrize("capa", ("R", "G", "B", "gris"))
    def test_las_bandas_fuera_de_5_por_ciento_estan_medidas_y_cuentan_en_la_media_y_en_la_mediana(self, muy_inclinada, capa):
        c = muy_inclinada.barrido.ejes["crossplane"].capas[capa]
        y = np.array([x.fwhm_mm for x in c.bandas])
        assert len(c.bandas) == BANDAS_DE_100 and c.estadistica.n_medibles == BANDAS_DE_100 and not np.isnan(y).any()
        centro = float(np.median(y))
        fuera = [x.k for x in c.bandas if abs(x.fwhm_mm - centro) > 0.05 * centro]
        assert len(fuera) >= 2 and fuera[0] < 0 < fuera[-1], "hay bandas a mas de 5 % del valor central en los dos lados"
        assert c.estadistica.media_mm == pytest.approx(float(np.mean(y)), abs=1e-9) and c.estadistica.mediana_mm == pytest.approx(centro, abs=1e-9)
        sin_los_extremos = np.array([x.fwhm_mm for x in c.bandas if x.k not in fuera])
        assert abs(c.estadistica.desviacion_mm - float(np.std(sin_los_extremos))) > 0.5, "la desviacion es la de las 79, no la de las que cumplen una tolerancia"

    @pytest.mark.parametrize("eje", EJES)
    def test_una_banda_que_no_se_pudo_medir_sigue_en_la_lista_con_su_motivo_y_no_cuenta_como_medida(self, base, eje):
        """Una pelicula girada recortada a 10.5 mm del cruce (en filas para el crossplane, en columnas para el inplane): las bandas que quedan fuera de ella NO se tiran: siguen en la lista como «no medible»
        con el motivo de C.2 y con SU eje y SU capa, y no entran a las medidas. Y el otro eje, cuyo perfil ya no cabe en la pelicula, no mide ninguna de sus 79 bandas y la capa lo dice con el motivo de la central.
        (R1-03) La medida que lleva cada banda que no se pudo sacar es la que le corresponde, ENTERA: SU eje, SU capa, el cruce a lo largo de SU eje, el tamano del pixel y el piso de SU capa, y nada mas."""
        pm = _pm()
        res = base.resultado
        g = res.girada
        _, b = recortada(res, eje)
        c = b.ejes[eje].capas["G"]
        assert len(c.bandas) == BANDAS_DE_100 and c.estadistica.n_bandas == BANDAS_DE_100
        fuera = [x for x in c.bandas if x.k >= 11]
        assert len(fuera) == 29 and all(not x.ok and x.fwhm_mm is None and x.medida.estado.startswith(f"no medible: perfil {eje}:") for x in fuera)
        assert all("fuera de la película girada" in x.medida.estado and x.medida.eje == eje and x.medida.capa == "G" and x.medida.perfil is None for x in fuera)
        i = 0 if eje == "crossplane" else 1                                   # el perfil del crossplane recorre la x y el del inplane la y: el centro de la medida es el cruce a lo largo de ese eje
        assert abs(g.cruce[0] - g.cruce[1]) > 10.0, "los cruces de los dos ejes son distintos (si fueran iguales, tomar el del otro eje pasaria sin que nadie lo vea)"
        for x in fuera:
            esperada = pm.MedidaDePerfil(estado=x.medida.estado, capa="G", eje=eje, tam_mm=g.tam_mm, centro_px=float(g.cruce[i]), piso=float(res.piso.capas["G"].mediana))
            assert iguales(x.medida, esperada), (x.k, x.medida)
        coherente(b)
        medibles = [x for x in c.bandas if x.ok]
        assert c.estadistica.n_medibles == len(medibles) and 0 < len(medibles) <= 50 and c.ok
        assert c.estadistica.media_mm == pytest.approx(float(np.mean([x.fwhm_mm for x in medibles])), abs=1e-12)
        assert c.estadistica.mediana_mm == pytest.approx(float(np.median([x.fwhm_mm for x in medibles])), abs=1e-12)
        otro = b.ejes[EJES[1 - EJES.index(eje)]].capas["G"]
        otro_eje = EJES[1 - EJES.index(eje)]
        assert len(otro.bandas) == BANDAS_DE_100 and otro.estadistica.n_medibles == 0 and not otro.ok and otro.estadistica.media_mm is None
        assert otro.estado == f"no medible: ninguna de las {BANDAS_DE_100} bandas del barrido se pudo medir (la central: {otro.central.medida.estado})" and otro.central.medida.estado.startswith(f"no medible: perfil {otro_eje}:")
        assert b.ok and b.estado == "ok", "el eje recortado si se midio"


# ======================================================================================================================================= (h) sin parametros, por AST
def _arbol():
    return ast.parse(MODULO.read_text(encoding="utf-8"))


def _funcion(arbol, nombre):
    return next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == nombre)


def _funciones_del_barrido(arbol):
    """Las funciones que C.3 agrega: `barrido` y las privadas del barrido (los nombres que empiezan por `_barr`, `_banda`, `_estadistica` o `_motivo_del_barrido`). Falla si no estan (una prueba que
    recorre una lista vacia pasaria en vacio, y en HEAD pasaria)."""
    funciones = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and (n.name == "barrido" or n.name.startswith(("_barr", "_banda", "_estadistica", "_motivo_del_barrido")))]
    assert {f.name for f in funciones} >= {"barrido", "_estadistica"} and len(funciones) >= 5, [f.name for f in funciones]
    return funciones


def _flotantes(nodo):
    return [n.value for n in ast.walk(nodo) if isinstance(n, ast.Constant) and type(n.value) is float]


class TestBarridoNoTieneParametros:
    """(h) del bloque y PD2: el barrido no tiene libertad. UN solo argumento, el resultado; ningun valor por omision; ningun parametro nuevo en el plano; ningun numero de la medida escrito en el codigo."""

    def test_barrido_tiene_un_solo_parametro_sin_valor_por_omision(self):
        pm = _pm()
        f = _funcion(_arbol(), "barrido")
        a = f.args
        assert [x.arg for x in a.args] == ["resultado"] and not a.posonlyargs and not a.vararg and not a.kwarg and not a.kwonlyargs and not a.defaults and not a.kw_defaults
        assert list(inspect.signature(pm.barrido).parameters) == ["resultado"]
        assert all(p.default is inspect.Parameter.empty for p in inspect.signature(pm.barrido).parameters.values())

    def test_c3_no_agrega_ningun_parametro_ni_cambia_la_version(self):
        pm = _pm()
        assert pm.VERSION_ALGORITMO == "PM-1"
        # OD.1 (21-10): `PARAMETROS` suma `base_de_la_medida` (`PARAMETROS_DE_LA_BASE`), que tampoco es de C.3: la vigila `test_od1_densidad_optica.py`.
        # CD.6 (31-10): el 42 es `diferencia_virgen_maxima_pct` (`PARAMETROS_DE_LA_DOSIS`): tampoco es de C.3; lo vigila `test_cd6_base_dosis_del_motor.py`.
        propios = set(pm.PARAMETROS) - set(pm.PARAMETROS_DE_LA_MEDIDA) - set(_pel().PARAMETROS_DEL_PISO) - set(pm.PARAMETROS_DE_LA_BASE) - set(pm.PARAMETROS_DE_LA_DOSIS)
        assert propios == {"radio_marca_mm", "contraste_minimo_marca", "fraccion_del_contraste_marca", "gris_maximo_de_la_tinta", "borde_blando_marca_mm", "area_minima_marca_mm2",
                           "resolucion_escaneo_dpi", "resoluciones_de_editor_dpi", "tolerancia_dpi_relativa"}, "los de C.1: ninguno de C.3"
        assert set(pm.PARAMETROS_DE_LA_MEDIDA) == {"margen_recorte_mm", "banda_perfil_mm", "fraccion_meseta", "excepcion_centro_mm", "muestras_minimas_de_la_meseta",
                                                  "altura_media", "penumbra_alta", "penumbra_baja", "suavizado_perfil_mm"}, "los de C.2: ninguno de C.3"
        assert set(pm.VALORES_DE_LA_GEOMETRIA) == set(pm.PARAMETROS)

    def test_el_codigo_del_barrido_no_lee_ningun_parametro_que_no_este_y_no_escribe_ningun_numero_de_la_medida(self):
        arbol = _arbol()
        funciones = _funciones_del_barrido(arbol)
        leidos = set()
        for f in funciones:
            leidos |= {n.slice.value for n in ast.walk(f) if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "P"
                       and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
            sueltos = [x for x in _flotantes(f) if x in (0.8, 0.4, 0.2, 3.8, 0.5, 1.0, 0.80, 44.5, 25.4, 600.0, 0.05, 1050.0)]
            assert not sueltos, (f.name, sueltos)
        assert leidos and leidos <= {"banda_perfil_mm", "fraccion_meseta"}, leidos

    def test_el_barrido_no_gira_no_vuelve_a_calcular_el_piso_ni_vuelve_a_analizar(self):
        """Lo que C.3 reutiliza (R9, paso 11): la pelicula ya girada, el piso del resultado, la geometria. Ninguna funcion del barrido llama a `girar`, `piso_de_pelicula`, `analizar`, `geometria_luz`,
        `refinar_marca`, `clasificar_puntos` ni a OpenCV."""
        prohibidas = {"girar", "piso_de_pelicula", "analizar", "geometria_luz", "refinar_marca", "clasificar_puntos", "warpAffine", "leer_pelicula", "imread", "transformar_puntos", "matriz_giro"}
        for f in _funciones_del_barrido(_arbol()):
            llamadas = {getattr(n.func, "id", getattr(n.func, "attr", None)) for n in ast.walk(f) if isinstance(n, ast.Call)}
            assert not (llamadas & prohibidas), (f.name, llamadas & prohibidas)
            assert "cv2" not in {n.id for n in ast.walk(f) if isinstance(n, ast.Name)}

    def test_el_barrido_usa_los_parametros_del_resultado_y_no_los_del_modulo(self, base, monkeypatch):
        """Con los `PARAMETROS` y `VALORES_DE_LA_GEOMETRIA` del modulo vaciados el barrido da lo mismo: lee `resultado.parametros`."""
        pm = _pm()
        antes = pm.barrido(base.resultado)
        monkeypatch.setattr(pm, "VALORES_DE_LA_GEOMETRIA", {})
        monkeypatch.setattr(pm, "PARAMETROS", {})
        despues = pm.barrido(base.resultado)
        assert iguales(antes, despues)


# ======================================================================================================================================= los parametros y el piso del resultado
class TestElBarridoUsaLoQueElResultadoYaTrae:
    def test_cambiar_la_banda_y_la_fraccion_del_analisis_cambia_la_region_y_las_posiciones_del_barrido(self, base):
        """`analizar` con banda_perfil_mm = 2 y fraccion_meseta = 0.6: la zona es +-30 % de 99.8 mm (29.94 mm), K = floor(29.94 / 2 - 1/2) = 14 (29 bandas) y la posicion de la banda k es 2 k mm."""
        pm = _pm()
        res = pm.analizar(base.pelicula, base.puntos, _P(banda_perfil_mm=2.0, fraccion_meseta=0.6, suavizado_perfil_mm=0.0))
        b = pm.barrido(res)
        e = b.ejes["crossplane"]
        assert e.banda_mm == 2.0 and e.k_maximo == k_esperado(longitud_perpendicular(base.verdad, "crossplane"), fraccion=0.6, banda_mm=2.0) == 14
        assert e.zona_mm == pytest.approx((-0.3 * longitud_perpendicular(base.verdad, "crossplane"), 0.3 * longitud_perpendicular(base.verdad, "crossplane")), abs=2e-3)
        assert [x.posicion_mm for x in e.capas["G"].bandas] == [2.0 * k for k in range(-14, 15)]
        assert b.ejes["inplane"].k_maximo == k_esperado(longitud_perpendicular(base.verdad, "inplane"), fraccion=0.6, banda_mm=2.0)
        assert all(x.medida.perfil.n_filas in (47, 48) for x in e.capas["G"].bandas), "bandas de 2 mm de 600 dpi: 47.2 filas"

    def test_cada_banda_usa_el_piso_de_su_capa_en_el_resultado_y_no_lo_recalcula(self, base, monkeypatch):
        pm = _pm()
        res = base.resultado

        def prohibido(*a, **k):
            raise AssertionError("el barrido no puede volver a calcular el piso ni a girar la pelicula")
        monkeypatch.setattr(pm, "piso_de_pelicula", prohibido)
        monkeypatch.setattr(pm, "girar", prohibido)
        b = pm.barrido(res)
        for capa in CAPAS:
            for eje in EJES:
                assert all(x.medida.piso == res.piso.capas[capa].mediana for x in bandas_de(b, eje, capa))
        # y si el resultado trae otro piso en una capa, el barrido mide con ESE (no hay otro lugar de donde sacarlo)
        capas = dict(res.piso.capas)
        capas["R"] = dataclasses.replace(capas["R"], mediana=capas["R"].mediana + 3.0)
        otro = dataclasses.replace(res, piso=dataclasses.replace(res.piso, capas=capas))
        bo = pm.barrido(otro)
        assert all(x.medida.piso == res.piso.capas["R"].mediana + 3.0 for x in bandas_de(bo, "crossplane", "R"))
        assert all(x.medida.piso == res.piso.capas["G"].mediana for x in bandas_de(bo, "crossplane", "G"))
        assert bo.ejes["crossplane"].capas["R"].estadistica.media_mm != b.ejes["crossplane"].capas["R"].estadistica.media_mm

    def test_el_barrido_no_cambia_el_resultado_que_recibe(self, base):
        """Ni los numeros (`como_dict`), ni las capas giradas, ni las medidas centrales, ni los parametros: el barrido no reasigna nada del corte central (el defecto N6 del cuaderno)."""
        pm = _pm()
        res = base.resultado
        antes = base.antes
        b1 = pm.barrido(res)                     # (la fixture ya llamo una vez a `barrido` DESPUES de tomar la instantanea)
        b2 = pm.barrido(res)
        ahora = instantanea(res)
        for clave in ("firma", "huella", "parametros", "capas", "bordes", "estado"):
            assert ahora[clave] == antes[clave], clave
        assert res.parametros is not antes["parametros"] and iguales(b1, b2) and iguales(b1, base.barrido), "tres llamadas dan lo mismo"

    @pytest.mark.parametrize("eje", EJES)
    def test_el_resultado_trae_los_bordes_luminosos_de_las_lineas_centrales_y_el_barrido_los_usa_para_su_region(self, base, eje):
        luz = base.bordes_luz_px[PERPENDICULAR[eje]]
        centro = base.cruce[1 if eje == "crossplane" else 0]
        assert base.barrido.ejes[eje].zona_px == pytest.approx((centro - 0.4 * (luz[1] - luz[0]), centro + 0.4 * (luz[1] - luz[0])), abs=1e-9)


# ======================================================================================================================================= los bordes luminosos de cada banda
class TestCadaBandaLlevaSusBordesLuminosos:
    """El plan: «bordes luminosos con `bordes_luz(eje, esquinas_giradas, linea_px=<la linea de ESA banda: cruce + k mm>)`». Con las esquinas marcadas como un trapecio los lados quedan inclinados (1.7 grados)
    y el borde luminoso cambia de una banda a otra: usar el de la linea central para todas movería la zona y el borde de cada banda."""

    @pytest.mark.parametrize("eje", EJES)
    def test_los_bordes_luminosos_de_cada_banda_son_la_interseccion_de_su_linea_con_los_lados(self, trapecio, eje):
        f = trapecio
        assert f.barrido.ok
        ul, ur, dr, dl = f.geometria.esquinas_giradas
        cruce = cruce_de_diagonales(ul, ur, dr, dl)
        ancho_px = 1.0 / TAM
        separacion = []
        for capa in CAPAS:
            for x in bandas_de(f.barrido, eje, capa):
                if eje == "crossplane":
                    y = cruce[1] + x.k * ancho_px
                    esperado = (lado_en_la_linea(ul, dl, 1, y), lado_en_la_linea(ur, dr, 1, y))
                else:
                    xx = cruce[0] + x.k * ancho_px
                    esperado = (lado_en_la_linea(ul, ur, 0, xx), lado_en_la_linea(dl, dr, 0, xx))
                assert x.medida.bordes_luz_px == pytest.approx(esperado, abs=1e-6), (capa, x.k)
                assert x.linea_px == pytest.approx(y if eje == "crossplane" else xx, abs=1e-6)
                if capa == "G":
                    separacion.append(x.medida.bordes_luz_px[1] - x.medida.bordes_luz_px[0])
        assert max(separacion) - min(separacion) > 0.5 / TAM, "los lados estan inclinados: la longitud luminosa cambia mas de 0.5 mm entre la primera y la ultima banda"

    @pytest.mark.parametrize("eje", EJES)
    def test_la_zona_y_la_exclusion_de_cada_banda_siguen_a_su_linea_y_al_reticulo_refinado(self, trapecio, eje):
        """La zona central de cada banda es el cruce +- 40 % de SU ancho luminoso; la exclusion del reticulo es +-3.8 mm alrededor del reticulo girado a lo largo de ese eje (la de C.2 para el corte central)."""
        f = trapecio
        i = 0 if eje == "crossplane" else 1
        for capa in CAPAS:
            for x in bandas_de(f.barrido, eje, capa):
                m = x.medida
                assert m.zona_px[0] == pytest.approx(m.centro_px - 0.4 * (m.bordes_luz_px[1] - m.bordes_luz_px[0]), abs=1e-9)
                assert m.zona_px[1] == pytest.approx(m.centro_px + 0.4 * (m.bordes_luz_px[1] - m.bordes_luz_px[0]), abs=1e-9)
                assert m.exclusion_px == pytest.approx((f.geometria.reticulo_girado[i] - 3.8 / TAM, f.geometria.reticulo_girado[i] + 3.8 / TAM), abs=1e-9)
                assert m.centro_px == pytest.approx(f.cruce[i], abs=1e-12)


# ======================================================================================================================================= lo que no se puede medir
class TestLoQueNoSePuedeMedir:
    """«Si el campo luminoso no es medible, el barrido es «no medible», nunca una region inventada.» Un resultado se pregunta con `estado != "ok"` o `startswith("no medible")`."""

    def _sin_nada_medido(self, b, estado):
        assert b.estado == estado and not b.ok and b.estado.startswith("no medible")
        assert set(b.ejes) == set(EJES) and b.memoria_bytes() == 0
        for eje in EJES:
            e = b.ejes[eje]
            assert e.estado == estado and e.k_maximo is None and e.zona_px is None and e.zona_mm is None and e.ks == () and set(e.capas) == set(CAPAS)
            for capa in CAPAS:
                c = e.capas[capa]
                assert c.estado == estado and c.bandas == () and c.central is None and not c.ok
                s = c.estadistica
                assert (s.n_bandas, s.n_medibles, s.media_mm, s.mediana_mm, s.desviacion_mm) == (0, 0, None, None, None)

    def test_si_los_puntos_no_forman_el_campo_no_hay_region_ni_bandas(self, base):
        pm = _pm()
        res = pm.analizar(base.pelicula, [(100.0, 100.0)] * 5, _P())
        assert res.estado.startswith("no medible") and res.girada is None
        self._sin_nada_medido(pm.barrido(res), res.estado)

    def test_si_el_piso_no_se_mide_no_hay_pelicula_girada_y_el_barrido_dice_el_motivo_del_piso(self):
        """El caso tipico (R7): recorte ajustado y girado 3 grados. El campo luminoso se midio (los bordes luminosos estan en la raiz) pero no hay pelicula girada que barrer: ninguna region inventada."""
        pm = _pm()
        verdad, pelicula = sintetica(variante="A", theta=3.0, seed=3, ruido=0)
        res = pm.analizar(pelicula, puntos_exactos(verdad), _P())
        assert res.estado.startswith("no medible") and res.geometria.ok and res.girada is None and all(res.bordes_luz_px[e] is not None for e in EJES)
        self._sin_nada_medido(pm.barrido(res), res.estado)

    def test_un_resultado_sin_pelicula_girada_que_dice_ok_tampoco_se_barre_y_lo_dice(self, base):
        pm = _pm()
        b = pm.barrido(dataclasses.replace(base.resultado, girada=None))
        self._sin_nada_medido(b, pm.MOTIVO_BARRIDO_SIN_PELICULA)

    def test_con_una_dosis_tan_baja_que_ninguna_capa_tiene_contraste_ninguna_se_barre_porque_ninguna_tiene_piso_y_el_barrido_lo_dice(self):
        """El caso del 6 % de la dosis: la geometria y la pelicula girada estan, pero el piso de cada capa no es 10 niveles mas claro que su meseta (A.2): sin piso no hay nivel de normalizacion y la
        capa no se barre (su motivo es el del piso). Las regiones SI se definen (no dependen de ningun perfil); la raiz dice `MOTIVO_NINGUNA_BANDA`, no «ok»."""
        pm = _pm()
        virgen_, meseta = np.array(gen.CALIB["virgen_bgr"]), np.array(gen.CALIB["meseta_bgr"])
        calib = dict(gen.CALIB, meseta_bgr=tuple(virgen_ - (virgen_ - meseta) * 0.06))
        verdad, pelicula = sintetica(variante="L", theta=1.0, seed=3, calib=calib)
        res = pm.analizar(pelicula, puntos_exactos(verdad), _P())
        assert res.estado.startswith("no medible: ninguna de las cuatro capas") and res.girada is not None
        b = pm.barrido(res)
        assert b.estado == pm.MOTIVO_NINGUNA_BANDA and not b.ok and b.estado.startswith("no medible")
        for eje in EJES:
            assert b.ejes[eje].estado == "ok" and b.ejes[eje].k_maximo == 39 and len(b.ejes[eje].ks) == BANDAS_DE_100
            for capa in CAPAS:
                c = b.ejes[eje].capas[capa]
                assert c.estado == res.piso.capas[capa].estado and "10 niveles" in c.estado and c.bandas == () and not c.ok
                assert (c.estadistica.n_bandas, c.estadistica.n_medibles, c.estadistica.media_mm) == (0, 0, None)

    def test_si_el_corte_central_no_se_midio_pero_la_pelicula_y_el_piso_si_estan_las_bandas_se_prueban_igual(self, banco, las_dos):
        """Un rayon blanco de 2.5 mm de alto sobre la linea central (cruza de lado a lado las bandas -1, 0 y +1 del crossplane): el corte central del crossplane no se mide en NINGUNA capa y la raiz de
        `analizar` es `MOTIVO_NINGUNA_CAPA`. El barrido no se corta por eso (la region no depende de ningun perfil medido): las otras 76 bandas del crossplane y las 79 del inplane se miden, y la mediana
        del crossplane es la de la pelicula limpia."""
        limpia, _ = las_dos
        f = escena(banco, "con_rayon", theta=0.0, seed=2, ruido=0, defectos=RAYON)
        assert f.estado.startswith("no medible: ninguna de las cuatro capas")
        assert f.barrido.ok and f.barrido.estado == "ok"
        for capa in CAPAS:
            c = f.barrido.ejes["crossplane"].capas[capa]
            assert c.ok and [x.k for x in c.bandas if not x.ok] == [-1, 0, 1] and c.estadistica.n_medibles == 76 and c.estadistica.n_bandas == BANDAS_DE_100
            assert c.estadistica.mediana_mm == pytest.approx(limpia.barrido.ejes["crossplane"].capas[capa].estadistica.mediana_mm, abs=0.02)
            assert f.capas[capa].crossplane.estado.startswith("no medible") and c.central.medida.estado == f.capas[capa].crossplane.estado
            i = f.barrido.ejes["inplane"].capas[capa]
            assert i.ok and i.estadistica.n_medibles == BANDAS_DE_100
            assert i.estadistica.mediana_mm == pytest.approx(limpia.barrido.ejes["inplane"].capas[capa].estadistica.mediana_mm, abs=0.02)

    def test_la_capa_cuyo_piso_no_se_midio_no_se_barre_y_no_detiene_a_las_demas(self, base):
        pm = _pm()
        res = base.resultado
        capas = dict(res.piso.capas)
        capas["B"] = dataclasses.replace(capas["B"], estado="no medible: el piso de la capa azul no es más claro que la meseta en al menos 10 niveles (piso 80.0, meseta 79.0)")
        b = pm.barrido(dataclasses.replace(res, piso=dataclasses.replace(res.piso, capas=capas)))
        assert b.ok and b.estado == "ok"
        for eje in EJES:
            azul = b.ejes[eje].capas["B"]
            assert azul.estado == capas["B"].estado and azul.bandas == () and azul.estadistica.n_bandas == 0 and not azul.ok
            for capa in ("R", "G", "gris"):
                assert b.ejes[eje].capas[capa].ok and len(b.ejes[eje].capas[capa].bandas) == BANDAS_DE_100
        # una capa «ok» pero sin nivel de piso tampoco se barre, y no dice «ok»
        capas["B"] = dataclasses.replace(res.piso.capas["B"], mediana=None)
        b2 = pm.barrido(dataclasses.replace(res, piso=dataclasses.replace(res.piso, capas=capas)))
        assert b2.ejes["crossplane"].capas["B"].estado.startswith("no medible") and b2.ejes["crossplane"].capas["B"].bandas == ()

    def test_si_la_linea_central_perpendicular_no_cruza_el_campo_ese_eje_no_tiene_region_y_el_otro_si(self, base):
        pm = _pm()
        res = base.resultado
        b = pm.barrido(dataclasses.replace(res, bordes_luz_px={"crossplane": None, "inplane": res.bordes_luz_px["inplane"]}))
        e = b.ejes["inplane"]                                        # su perpendicular es el crossplane, que no cruza
        assert e.estado == pm.MOTIVO_BARRIDO_SIN_LINEA and e.k_maximo is None and e.zona_px is None and e.ks == () and e.longitud_perpendicular_mm is None and e.ok is False
        assert all(e.capas[c].estado == pm.MOTIVO_BARRIDO_SIN_LINEA and e.capas[c].bandas == () for c in CAPAS)
        assert b.ejes["crossplane"].estado == "ok" and b.ejes["crossplane"].k_maximo == 39 and b.ok

    def test_si_la_zona_no_alcanza_para_una_banda_no_hay_ninguna(self, base):
        pm = _pm()
        res = base.resultado
        c = res.girada.cruce
        chico = {"crossplane": (c[0] - 2.0, c[0] + 2.0), "inplane": (c[1] - 2.0, c[1] + 2.0)}     # 4 px = 0.17 mm de largo
        b = pm.barrido(dataclasses.replace(res, bordes_luz_px=chico))
        for eje in EJES:
            e = b.ejes[eje]
            assert e.estado == pm.MOTIVO_BARRIDO_SIN_BANDA and e.k_maximo is None and e.ks == () and all(e.capas[x].bandas == () for x in CAPAS) and e.ok is False
        assert not b.ok

    def test_el_motivo_de_la_capa_sin_bandas_medibles_es_el_de_la_banda_central_y_no_el_de_otra(self, base, monkeypatch):
        """Si ninguna banda se mide (aqui `medir_perfil` dice, de cada una, que banda es), la capa dice el motivo de la CENTRAL; y la raiz, `MOTIVO_NINGUNA_BANDA`."""
        pm = _pm()

        def sin_medir(perfil, centro_px, piso, base_, P, bordes, reticulo_px=None, curva=None):          # CD.6 (31-10): `medir_perfil` se llama con `curva=` (None fuera de la dosis)
            return pm.MedidaDePerfil(estado=f"no medible: perfil {perfil.eje}: banda {perfil.banda}", capa=perfil.capa, eje=perfil.eje, tam_mm=perfil.tam_mm, centro_px=float(centro_px), perfil=perfil, piso=float(piso))
        monkeypatch.setattr(pm, "medir_perfil", sin_medir)
        b = pm.barrido(base.resultado)
        assert b.estado == pm.MOTIVO_NINGUNA_BANDA and not b.ok
        for eje in EJES:
            assert b.ejes[eje].estado == "ok"
            for capa in CAPAS:
                c = b.ejes[eje].capas[capa]
                assert c.estado == f"no medible: ninguna de las {BANDAS_DE_100} bandas del barrido se pudo medir (la central: no medible: perfil {eje}: banda 0)" and not c.ok
                assert [x.medida.estado for x in c.bandas[:2]] == [f"no medible: perfil {eje}: banda -39", f"no medible: perfil {eje}: banda -38"]

    def test_si_el_eje_crossplane_no_tiene_region_y_el_inplane_si_la_raiz_tambien_es_ok(self, base):
        pm = _pm()
        res = base.resultado
        b = pm.barrido(dataclasses.replace(res, bordes_luz_px={"crossplane": res.bordes_luz_px["crossplane"], "inplane": None}))
        assert b.ejes["crossplane"].estado == pm.MOTIVO_BARRIDO_SIN_LINEA and b.ejes["crossplane"].ks == ()
        assert b.ejes["inplane"].estado == "ok" and b.ejes["inplane"].k_maximo == 39 and b.ok and b.estado == "ok"

    def test_una_zona_de_0_8_mm_deja_una_sola_banda_la_central_y_cada_limite_de_k_se_decide_a_favor_de_que_la_banda_quepa(self, base):
        """Los limites de K: la zona es +-40 % de L. L = 2 mm: +-0.8 mm, K = floor(0.8 - 1/2) = 0 (la banda central sola, cuyo borde de afuera, a 0.5 mm, cabe); L = 3 mm: +-1.2, K = 0 (la banda 1 asomaria
        su borde de afuera a 1.5 mm); L = 4 mm: +-1.6, K = 1; L = 6 mm: +-2.4, K = 1 (la banda 2 llegaria a 2.5 mm).
        (R1-01) Y esas bandas SI se miden (la zona angosta solo decide cuantas caben, no si se pueden medir): con UNA sola banda (K = 0) la capa, el eje y la raiz son «ok» y la estadistica es la de esa banda."""
        pm = _pm()
        res = base.resultado
        c = res.girada.cruce
        for L_mm, K in ((2.0, 0), (3.0, 0), (4.0, 1), (6.0, 1)):
            a = L_mm / 2 / TAM
            b = pm.barrido(dataclasses.replace(res, bordes_luz_px={"crossplane": (c[0] - a, c[0] + a), "inplane": (c[1] - a, c[1] + a)}))
            for eje in EJES:
                e = b.ejes[eje]
                assert e.estado == "ok" and e.k_maximo == K and e.ks == tuple(range(-K, K + 1)) and e.zona_mm == pytest.approx((-0.4 * L_mm, 0.4 * L_mm), abs=1e-9)
                for capa in CAPAS:
                    cc = e.capas[capa]
                    assert [x.k for x in cc.bandas] == list(range(-K, K + 1)) and cc.estadistica.n_bandas == 2 * K + 1
                    assert iguales(cc.central.medida, getattr(res.capas[capa], eje))
                    assert cc.ok and cc.estado == "ok" and cc.estadistica.n_medibles == 2 * K + 1 and all(x.ok for x in cc.bandas), (L_mm, eje, capa, cc.estado)
                    if K == 0:
                        s = cc.estadistica
                        assert s.media_mm == s.mediana_mm == cc.central.fwhm_mm and s.desviacion_mm == 0.0
            assert b.ok and b.estado == "ok", (L_mm, b.estado)
            coherente(b)

    def test_una_capa_con_una_sola_banda_medible_entre_muchas_es_ok_y_la_raiz_tambien(self, base, monkeypatch):
        """(R1-01) El limite de «al menos una banda medible» con 79 bandas de las que SOLO la central se mide (a `medir_perfil` se le deja medir la banda 0 y a las demas se les contesta «no medible»): cada capa,
        cada eje y la raiz son «ok», la estadistica es la de ESA banda (n = 1, desviacion 0) y las otras 78 siguen en la lista con su motivo. Con ninguna medible la capa no es «ok» (otra prueba)."""
        pm = _pm()
        real = pm.medir_perfil

        def solo_la_central(perfil, centro_px, piso, base_, P, bordes, reticulo_px=None, curva=None):          # CD.6 (31-10): `medir_perfil` se llama con `curva=` (None fuera de la dosis)
            if perfil.banda == 0:
                return real(perfil, centro_px, piso, base_, P, bordes, reticulo_px)
            return pm.MedidaDePerfil(estado=f"no medible: perfil {perfil.eje}: banda {perfil.banda}", capa=perfil.capa, eje=perfil.eje, tam_mm=perfil.tam_mm, centro_px=float(centro_px), perfil=perfil, piso=float(piso))
        monkeypatch.setattr(pm, "medir_perfil", solo_la_central)
        b = pm.barrido(base.resultado)
        assert b.ok and b.estado == "ok"
        coherente(b)
        for eje in EJES:
            assert b.ejes[eje].ok
            for capa in CAPAS:
                c = b.ejes[eje].capas[capa]
                assert c.ok and c.estado == "ok" and (c.estadistica.n_bandas, c.estadistica.n_medibles) == (BANDAS_DE_100, 1), (eje, capa, c.estado)
                assert [x.k for x in c.bandas if x.ok] == [0] and c.estadistica.media_mm == c.estadistica.mediana_mm == c.central.fwhm_mm and c.estadistica.desviacion_mm == 0.0
                assert all(x.medida.estado == f"no medible: perfil {eje}: banda {x.k}" for x in c.bandas if x.k != 0)

    def test_argumentos_de_forma_equivocada_son_value_error(self, base):
        pm = _pm()
        for malo in (None, 3, {}, base.resultado.como_dict(), base.barrido):
            with pytest.raises(ValueError):
                pm.barrido(malo)
        parametros = {k: v for k, v in base.resultado.parametros.items() if k != "suavizado_perfil_mm"}
        with pytest.raises(ValueError, match="suavizado_perfil_mm"):
            pm.barrido(dataclasses.replace(base.resultado, parametros=parametros))
        with pytest.raises(ValueError, match="suavizado_perfil_mm"):                  # tambien cuando no hay pelicula girada y ninguna banda llegaria a pedirlo
            pm.barrido(dataclasses.replace(base.resultado, girada=None, parametros=parametros))


# ======================================================================================================================================= la estadistica
class TestLaEstadisticaDeLasBandasMedibles:
    def test_media_mediana_y_desviacion_de_la_poblacion(self):
        """[1, 2, 3, 10]: media 4, mediana 2.5, desviacion de la POBLACION sqrt(12.5) = 3.5355 (la `np.std` del resto de la app; con n - 1 daria 4.0825)."""
        s = _pm()._estadistica([1.0, 2.0, 3.0, 10.0], 7)
        assert (s.n_bandas, s.n_medibles) == (7, 4)
        assert s.media_mm == pytest.approx(4.0, abs=1e-12) and s.mediana_mm == pytest.approx(2.5, abs=1e-12) and s.desviacion_mm == pytest.approx(math.sqrt(12.5), abs=1e-12)
        assert all(type(v) is float for v in (s.media_mm, s.mediana_mm, s.desviacion_mm))
        impar = _pm()._estadistica([5.0, 1.0, 9.0], 3)
        assert impar.mediana_mm == 5.0 and impar.media_mm == pytest.approx(5.0)

    def test_sin_bandas_medibles_no_hay_numeros_y_con_una_sola_la_desviacion_es_cero(self):
        s0 = _pm()._estadistica([], 79)
        assert (s0.n_bandas, s0.n_medibles, s0.media_mm, s0.mediana_mm, s0.desviacion_mm) == (79, 0, None, None, None)
        s1 = _pm()._estadistica([98.7], 79)
        assert (s1.n_bandas, s1.n_medibles, s1.media_mm, s1.mediana_mm, s1.desviacion_mm) == (79, 1, 98.7, 98.7, 0.0)

    @pytest.mark.parametrize("eje", EJES)
    @pytest.mark.parametrize("capa", CAPAS)
    def test_las_medidas_de_cada_capa_son_las_de_todas_sus_bandas_medibles(self, base, capa, eje):
        c = base.barrido.ejes[eje].capas[capa]
        y = np.array([x.fwhm_mm for x in c.bandas if x.medida.ok])
        s = c.estadistica
        assert s.n_bandas == len(c.bandas) == BANDAS_DE_100 and s.n_medibles == len(y) == sum(1 for x in c.bandas if x.ok)
        assert s.media_mm == pytest.approx(float(np.mean(y)), rel=1e-12) and s.mediana_mm == pytest.approx(float(np.median(y)), rel=1e-12)
        assert s.desviacion_mm == pytest.approx(float(np.std(y)), rel=1e-12) and s.desviacion_mm != pytest.approx(float(np.std(y, ddof=1)), rel=1e-6)
        assert min(y) <= s.mediana_mm <= max(y) and min(y) <= s.media_mm <= max(y)


# ======================================================================================================================================= la forma del resultado
class TestLaFormaDelResultado:
    def test_el_resultado_trae_los_dos_ejes_con_las_cuatro_capas_y_es_de_solo_lectura(self, base):
        pm = _pm()
        b = base.barrido
        assert isinstance(b, pm.BarridoPlacaMensual) and b.version == "PM-1" and b.estado == "ok" and b.ok and b.tam_mm == pytest.approx(TAM)
        assert tuple(b.ejes) == EJES
        coherente(b)
        for eje in EJES:
            e = b.ejes[eje]
            assert isinstance(e, pm.BarridoDeEje) and e.eje == eje and tuple(e.capas) == CAPAS and e.ok is True and e.estado == "ok"
            for capa in CAPAS:
                c = e.capas[capa]
                assert isinstance(c, pm.BarridoDeCapa) and (c.capa, c.eje) == (capa, eje) and c.ok and c.estado == "ok"
                assert isinstance(c.estadistica, pm.EstadisticaDelBarrido) and all(isinstance(x, pm.BandaDelBarrido) for x in c.bandas)
                assert [x.k for x in c.bandas] == list(range(-39, 40)) and c.central is c.bandas[39]
                x = c.bandas[10]
                assert x.ok == x.medida.ok and x.fwhm_mm == x.medida.fwhm_mm and isinstance(x.medida, pm.MedidaDePerfil)
        for obj in (b, b.ejes["crossplane"], b.ejes["crossplane"].capas["G"], b.ejes["crossplane"].capas["G"].bandas[0], b.ejes["crossplane"].capas["G"].estadistica):
            with pytest.raises(dataclasses.FrozenInstanceError):
                obj.estado = "x"

    def test_como_dict_es_json_con_numeros_y_textos_con_los_valores_de_sus_pares_y_pesa_menos_de_400_kb(self, base):
        """Medido el 18-10: 183 KB de JSON para las 632 bandas (cada una con sus bordes); el barrido no se guarda, asi que el tamano solo importa para mostrarlo y compararlo."""
        d = base.barrido.como_dict()
        texto = json.dumps(d, allow_nan=False)
        assert len(texto) < 400_000
        assert d["version"] == "PM-1" and d["estado"] == "ok" and set(d["ejes"]) == set(EJES)
        e = d["ejes"]["crossplane"]
        assert e["k_maximo"] == 39 and e["perpendicular"] == "inplane" and len(e["zona_px"]) == 2 and len(e["zona_mm"]) == 2 and e["banda_mm"] == 1.0
        g = e["capas"]["G"]
        assert g["estado"] == "ok" and set(g["estadistica"]) == {"n_bandas", "n_medibles", "media_mm", "mediana_mm", "desviacion_mm"} and len(g["bandas"]) == BANDAS_DE_100
        b0 = g["bandas"][39]
        assert b0["k"] == 0 and b0["posicion_mm"] == 0.0 and b0["estado"] == "ok" and b0["fwhm_mm"] == base.barrido.ejes["crossplane"].capas["G"].central.fwhm_mm
        assert len(b0["bordes_rad_px"]) == 2 and len(b0["bordes_luz_px"]) == 2 and len(b0["banda_px"]) == 2
        # los VALORES de cada par son los del objeto (floats), no solo su largo: una lista de dos None tambien mide 2
        central = base.barrido.ejes["crossplane"].capas["G"].central
        assert b0["bordes_rad_px"] == [float(x) for x in central.medida.bordes_rad_px] and b0["bordes_luz_px"] == [float(x) for x in central.medida.bordes_luz_px]
        assert b0["banda_px"] == [float(x) for x in central.medida.perfil.filas_px] and b0["centro_rad_px"] == central.medida.centro_rad_px
        assert b0["linea_px"] == central.linea_px and None not in b0["bordes_rad_px"] + b0["bordes_luz_px"] + b0["banda_px"]
        eje = base.barrido.ejes["crossplane"]
        assert e["zona_px"] == [float(x) for x in eje.zona_px] and e["zona_mm"] == [float(x) for x in eje.zona_mm] and e["longitud_perpendicular_mm"] == eje.longitud_perpendicular_mm

    @pytest.mark.parametrize("caso", ("completo", "pelicula_recortada", "sin_pelicula_girada"))
    def test_como_dict_dice_lo_mismo_que_el_objeto_en_cada_nivel_con_bandas_medibles_con_bandas_no_medibles_y_sin_bandas(self, base, caso):
        """(R1-02) El diccionario es el objeto ENTERO hecho numeros y textos, valor por valor y en cada nivel (la raiz con su tam_mm, cada eje, cada capa con su estadistica, cada banda), y no solo las claves: con las
        632 bandas medibles, con la pelicula recortada (bandas «no medible» con su motivo y sin FWHM, capas «no medible») y sin pelicula girada (ejes sin zona ni bandas). El esperado se arma en la prueba."""
        pm = _pm()
        res = base.resultado
        b = {"completo": lambda: base.barrido, "pelicula_recortada": lambda: recortada(res, "crossplane")[1],
             "sin_pelicula_girada": lambda: pm.barrido(dataclasses.replace(res, girada=None))}[caso]()
        d = b.como_dict()
        esperado = como_dict_esperado(b)
        assert d == esperado
        assert json.loads(json.dumps(d, allow_nan=False)) == json.loads(json.dumps(esperado, allow_nan=False))
        capas = [c for e in d["ejes"].values() for c in e["capas"].values()]
        assert d["tam_mm"] == b.tam_mm and (caso == "sin_pelicula_girada" or d["tam_mm"] == pytest.approx(TAM))
        if caso == "completo":
            assert sum(len(c["bandas"]) for c in capas) == 8 * BANDAS_DE_100 and all(x["estado"] == "ok" and x["fwhm_mm"] is not None for c in capas for x in c["bandas"])
        if caso == "pelicula_recortada":
            no_medibles = [x for c in capas for x in c["bandas"] if x["estado"] != "ok"]
            assert len(no_medibles) > 100 and all(x["fwhm_mm"] is None and x["centro_rad_px"] is None and x["estado"].startswith("no medible") for x in no_medibles)
            assert any(c["estado"] != "ok" and c["estadistica"]["media_mm"] is None for c in capas) and any(c["estado"] == "ok" for c in capas)
        if caso == "sin_pelicula_girada":
            assert all(e["estado"] == b.estado and e["zona_px"] is None and e["zona_mm"] is None and e["k_maximo"] is None for e in d["ejes"].values())
            assert all(c["bandas"] == [] and c["estado"] == b.estado and c["estadistica"]["n_bandas"] == 0 for c in capas)

    def test_un_par_se_cuenta_como_lista_de_floats_y_lo_que_no_hay_sigue_siendo_none(self):
        """`_par_como_lista`: None queda None (una banda sin bordes, un eje sin zona), un par queda como lista de floats y un valor que falta dentro del par queda None sin tumbar nada."""
        pm = _pm()
        assert pm._par_como_lista(None) is None
        assert pm._par_como_lista((1, 2.5)) == [1.0, 2.5] and all(type(x) is float for x in pm._par_como_lista((1, 2)))
        assert pm._par_como_lista((None, 2)) == [None, 2.0] and pm._par_como_lista((3.5, None)) == [3.5, None]
        assert pm._par_como_lista(np.array([1.5, 2.5])) == [1.5, 2.5]

    def test_memoria_bytes_cuenta_los_perfiles_que_el_barrido_retiene(self, base):
        total = sum(x.medida.perfil.valores.nbytes + x.medida.suavizado.nbytes for e in base.barrido.ejes.values() for c in e.capas.values() for x in c.bandas
                    if x.medida.perfil is not None and x.medida.suavizado is not None)
        assert base.barrido.memoria_bytes() == total > 10_000_000

    def test_memoria_bytes_cuenta_una_sola_vez_el_arreglo_que_es_a_la_vez_el_perfil_y_el_suavizado(self, base):
        """(R1-04) Con `suavizado_perfil_mm` = 0 no se suaviza (`_suavizar` con una muestra devuelve el MISMO arreglo): el perfil suavizado de cada banda ES su perfil y `memoria_bytes` lo cuenta una vez, no dos.
        La cuenta es la de los arreglos DISTINTOS y coincide, dentro del mismo margen de la prueba de costo, con lo que `tracemalloc` ve retenido (con la cuenta doble se pasaba de largo en un 46 %)."""
        pm = _pm()
        res = dataclasses.replace(base.resultado, parametros={**base.resultado.parametros, "suavizado_perfil_mm": 0.0})
        gc.collect()
        tracemalloc.start()
        try:
            b = pm.barrido(res)
            actual, _ = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        bandas = [x for e in b.ejes.values() for c in e.capas.values() for x in c.bandas]
        assert len(bandas) == 8 * BANDAS_DE_100 and all(x.medida.perfil is not None and x.medida.suavizado is x.medida.perfil.valores for x in bandas), "la premisa: sin suavizado el suavizado es el propio perfil"
        distintos = {id(x.medida.perfil.valores): x.medida.perfil.valores.nbytes for x in bandas}
        assert len(distintos) == len(bandas) and b.memoria_bytes() == sum(distintos.values()) > 5_000_000
        assert abs(actual - b.memoria_bytes()) < 0.25 * b.memoria_bytes(), (actual, b.memoria_bytes())


# ======================================================================================================================================= el costo
class TestMemoriaYTiempo:
    def test_barrer_las_632_bandas_tarda_fracciones_de_segundo_y_no_retiene_la_pelicula_ni_la_pagina(self, base):
        """Medido el 18-10: 0.21 s por 79 bandas x 2 ejes x 4 capas (el plan: 0.2 a 0.6 s). La memoria que queda es la de los perfiles de las bandas (~27 MB), no la de la pelicula girada (~130 MB)."""
        assert base.tiempo < 3.0, base.tiempo
        pm = _pm()
        res = base.resultado
        gc.collect()
        tracemalloc.start()
        try:
            b = pm.barrido(res)
            actual, pico = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert abs(actual - b.memoria_bytes()) < 0.25 * b.memoria_bytes(), (actual, b.memoria_bytes())
        assert pico < 80_000_000, pico
        assert pico < res.girada.memoria_bytes() / 2, "el barrido no copia la pelicula girada"

    def test_el_barrido_no_retiene_el_resultado_ni_la_pelicula_girada(self, base):
        pm = _pm()
        res = pm.analizar(base.pelicula, base.puntos, _P())
        b = pm.barrido(res)
        de_la_capa = weakref.ref(res.girada.capas["G"])
        del res
        gc.collect()
        assert de_la_capa() is None, "el barrido no guarda la pelicula girada ni el resultado"
        assert b.estado == "ok"


# ======================================================================================================================================= las peliculas reales
# Los cinco puntos (UL, UR, DR, DL y el reticulo) de las diez peliculas mensuales reales, los mismos de C.2: los de ML0 son los clics del cuaderno del fisico; los de EPSON027, los de ML0 mas el
# desplazamiento exacto (10, 7) de ML0 dentro de la pagina; los demas, marcas localizadas con scripts/med_mensual_marcas.py y llevadas entre archivos de la misma pelicula. EPSON029: la esquina UL esta ESTIMADA.
CLICS_REALES = {
    "ML0": ((196, 143), (2542, 147), (2526, 2501), (171, 2480), (1371, 1330)),
    "EPSON027": ((206, 150), (2552, 154), (2536, 2508), (181, 2487), (1381, 1337)),
    "EPSON007": ((207, 173), (2516, 153), (2553, 2507), (232, 2525), (1376, 1345)),
    "EPSON008_TIF": ((206, 189), (2517, 169), (2553, 2525), (230, 2542), (1376, 1362)),
    "EPSON030": ((166, 174), (2475, 158), (2507, 2512), (187, 2526), (1333, 1348)),
    "EPSON001_JPG": ((178, 255), (2541, 252), (2553, 2593), (203, 2608), (1368, 1435)),
    "EPSON001_TIF": ((178, 255), (2541, 252), (2553, 2593), (203, 2608), (1368, 1435)),
    "PLACA_REF40": ((104, 182), (2444, 149), (2496, 2493), (125, 2506), (1284, 1339)),
    "EPSON028": ((111, 200), (2452, 175), (2496, 2520), (124, 2525), (1287, 1362)),
    "EPSON029": ((215, 151), (2526, 195), (2494, 2542), (183, 2498), (1361, 1350)),
}
# los mismos rangos de C.2 (lo que midieron R5 y R6 sobre estas peliculas con el piso corregido), para la MEDIANA del barrido
RANGOS_DE_FWHM = {"R": (101.5, 105.5), "G": (98.8, 102.8), "B": (96.8, 101.2), "gris": (99.5, 103.5)}


class Real:
    """Lo que se lee de una pelicula real medida y barrida (sin la pelicula): el barrido, el resultado ligero y el tiempo."""

    def __init__(self, res, b, tiempo):
        self.barrido, self.capas, self.estado, self.tiempo = b, res.capas, res.estado, tiempo


def _real_barrido(banco, clave):
    k = ("real", clave)
    if k not in banco:
        pm, pel = _pm(), _pel()
        pelicula = pel.leer_pelicula(Path(_real(clave)).read_bytes())
        marcas = [pm.refinar_marca(pelicula.gris, punto, _P(), validos=pelicula.validos) for punto in CLICS_REALES[clave]]
        res = pm.analizar(pelicula, marcas, _P())
        assert res.ok, (clave, res.estado)
        t0 = time.perf_counter()
        b = pm.barrido(res)
        banco[k] = Real(res, b, time.perf_counter() - t0)
        del res, pelicula, marcas
        gc.collect()
    return banco[k]


class TestPeliculasReales:
    @pytest.mark.parametrize("clave", sorted(CLICS_REALES))
    def test_cada_pelicula_real_se_barre_completa_y_su_mediana_cae_en_lo_que_midio_el_plan(self, banco, clave):
        r = _real_barrido(banco, clave)
        assert r.barrido.ok and r.tiempo < 3.0, r.tiempo
        for eje in EJES:
            e = r.barrido.ejes[eje]
            assert e.estado == "ok" and 37 <= e.k_maximo <= 39, "un campo luminoso de 98 a 100 mm"
            for capa in CAPAS:
                c = e.capas[capa]
                s = c.estadistica
                assert s.n_bandas == len(c.bandas) == 2 * e.k_maximo + 1 and s.n_medibles >= 0.9 * s.n_bandas, (eje, capa, s)
                assert RANGOS_DE_FWHM[capa][0] < s.mediana_mm < RANGOS_DE_FWHM[capa][1], (clave, eje, capa, s.mediana_mm)
                assert abs(c.central.fwhm_mm - s.mediana_mm) < 0.6, "el corte central cae cerca de la mediana de su barrido (EPSON028: 0.1 a 0.4 mm)"
                assert s.desviacion_mm < 1.5
            # el ancho de las capas sigue el orden de su saturacion (R6): azul < verde < gris < rojo, tambien en la mediana del barrido
            m = {capa: e.capas[capa].estadistica.mediana_mm for capa in CAPAS}
            assert m["B"] < m["G"] < m["gris"] < m["R"], (clave, eje, m)

    @pytest.mark.parametrize("clave", sorted(CLICS_REALES))
    def test_en_el_rojo_de_las_peliculas_reales_los_extremos_del_barrido_son_mas_angostos_que_el_centro(self, banco, clave):
        """El plan midio -0.3 a -0.95 mm en el rojo (cupula + saturacion). Promedio de las 5 bandas de cada extremo menos el de las 5 centrales, en los dos ejes: de -0.25 a -1.3 mm en las diez peliculas."""
        r = _real_barrido(banco, clave)
        for eje in EJES:
            e = r.barrido.ejes[eje]
            y = {x.k: x.fwhm_mm for x in e.capas["R"].bandas if x.ok}
            extremos = np.mean([y[s * k] for s in (-1, 1) for k in range(e.k_maximo - 4, e.k_maximo + 1) if s * k in y])
            centro = np.mean([y[k] for k in range(-2, 3)])
            assert -1.3 < float(extremos - centro) < -0.25, (clave, eje, float(extremos - centro))

    @pytest.mark.parametrize("par, tolerancia", [(("ML0", "EPSON027"), 0.1), (("EPSON001_JPG", "EPSON001_TIF"), 0.2)])
    def test_la_misma_pelicula_en_dos_archivos_da_la_misma_mediana_del_barrido(self, banco, par, tolerancia):
        """ML0 es un recorte de la pagina EPSON027 y EPSON001 jpg/TIF son la misma imagen en dos formatos: el barrido de los dos da lo mismo (la diferencia del azul es el piso entero de A.2, C2-D4)."""
        a, b = _real_barrido(banco, par[0]), _real_barrido(banco, par[1])
        for eje in EJES:
            assert a.barrido.ejes[eje].ks == b.barrido.ejes[eje].ks
            for capa in CAPAS:
                x, y = a.barrido.ejes[eje].capas[capa].estadistica, b.barrido.ejes[eje].capas[capa].estadistica
                assert x.mediana_mm == pytest.approx(y.mediana_mm, abs=tolerancia), (eje, capa)
                assert x.media_mm == pytest.approx(y.media_mm, abs=tolerancia), (eje, capa)

    def test_barrer_una_pagina_entera_de_6600_por_5100_tarda_segundos_menos_de_uno(self, banco):
        """EPSON027 es la pagina del escaner (6600 x 5100): `analizar` recorta antes de girar y el barrido trabaja sobre esa pelicula girada, no sobre la pagina: 0.2 s medidos."""
        r = _real_barrido(banco, "EPSON027")
        assert r.tiempo < 3.0 and r.barrido.memoria_bytes() < 60_000_000


# ======================================================================================================================================= la estructura del modulo
class TestLaEstructuraDelModulo:
    def test_las_funciones_y_clases_de_c1_y_c2_siguen_en_el_modulo(self):
        pm = _pm()
        for nombre in ("clasificar_puntos", "refinar_marca", "geometria_luz", "matriz_giro", "transformar_puntos", "recuadro_luminoso", "punto_de_medida", "girar", "perfil_central", "medir_perfil",
                       "bordes_luz", "coincidencia", "analizar", "valores_medidos"):
            assert callable(getattr(pm, nombre)), nombre
        for clase in ("PuntosClasificados", "MarcaRefinada", "RecuadroLuminoso", "GeometriaLuz", "CapaGirada", "PeliculaGirada", "PerfilCentral", "MedidaDePerfil", "MedidaDeCapa", "ResultadoPlacaMensual"):
            assert dataclasses.is_dataclass(getattr(pm, clase)), clase

    def test_cada_dataclass_nuevo_es_congelado_y_el_barrido_no_lo_construye_nadie_mas(self):
        pm = _pm()
        for clase in ("BandaDelBarrido", "EstadisticaDelBarrido", "BarridoDeCapa", "BarridoDeEje", "BarridoPlacaMensual"):
            c = getattr(pm, clase)
            assert dataclasses.is_dataclass(c) and c.__dataclass_params__.frozen, clase

    def test_los_motivos_de_no_medible_empiezan_por_no_medible(self):
        pm = _pm()
        for motivo in (pm.MOTIVO_BARRIDO_SIN_LINEA, pm.MOTIVO_BARRIDO_SIN_BANDA, pm.MOTIVO_BARRIDO_SIN_PELICULA, pm.MOTIVO_NINGUNA_BANDA):
            assert motivo.startswith("no medible: ")

    def test_el_codigo_del_barrido_no_tiene_simbolos_de_correcto_o_incorrecto_ni_unidades_entre_parentesis(self):
        """DA-18 y D.1 de la navegacion: ni marcas de verificacion o equis en lo que se escribe, ni unidades entre parentesis (corchetes)."""
        import re
        texto = MODULO.read_text(encoding="utf-8")
        assert not re.search("[✓✔✗✘❌✅⚠️\U0001f534\U0001f7e2☑☒]", texto)
        for f in _funciones_del_barrido(_arbol()):
            for n in ast.walk(f):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    assert not re.search(r"(?<=\s)\((mm|px|s|h|%|A|V|U)\)", n.value), (f.name, n.value)
