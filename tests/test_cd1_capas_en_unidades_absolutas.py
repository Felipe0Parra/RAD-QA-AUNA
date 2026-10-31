"""CD.1 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, tarea CD.1; el fisico, 22-10: «dejé de normalizar la imagen, para crear un rango absoluto y no relativo a cada perfil, pues si eventualmente queremos medir
dosis es necesario esto»): LA PESTAÑA «CAPAS» SE PINTA EN UNIDADES ABSOLUTAS.

CAUSA (codigo de HEAD b926ada): `dibujo_placa_mensual.capa_acondicionada` normalizaba cada capa entre su piso (0) y su meseta (1) con `motor.normalizar` y `dibujar_capas` la pintaba en `jet` con una barra de 0 a 1:
el 1 del azul (netOD de la meseta 0.34) y el 1 del verde (0.72) se veian iguales. Los perfiles ya se dibujaban absolutos desde OD.1 (`valores_en_la_base`); la imagen de las capas no.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del codigo bajo prueba (la formula de la netOD escrita AQUI con numpy, las constantes y los textos escritos AQUI, el generador independiente de PF.0 y los
numeros de las diez peliculas reales medidos en el pre-vuelo de Opus del 23-10):
  (a) `capa_acondicionada(resultado, capa)` da una `CapaEnUnidades(valores, tope, unidad, texto, meseta, motivo)`: `valores` es la netOD de cada pixel (log10(piso / max(v, 0.5)), a 2e-6), SIN normalizar y SIN recortar
      (la negativa, ruido bajo el piso, se conserva), con NaN exactamente donde la pelicula girada no tiene dato; en un registro en valor de pixel (o en una capa sin piso) son sus niveles de 0 a 255.
  (b) la escala va de 0 (el piso del analisis) a `1.1` veces la netOD de la meseta de esa capa (el promedio de las de sus dos perfiles); sin meseta valida (ninguna medida, recortada por el escaner o no mas oscura que el
      piso) va al percentil 99.5 y el texto dice por que; si ese tampoco es positivo, de 0 a 1.
  (c) lo pintado es el mapa de color `jet` de `valores / tope` (la netOD negativa con el color del cero, lo que no es pelicula transparente); la barra dice su unidad y va de 0 al tope; el titulo de cada capa dice la escala
      y la meseta, partido en renglones de 52 caracteres para que las tres no se pisen.
  (d) la unica normalizacion que quedaba, `motor.normalizar` en el dibujo, ya no esta; el valor de pixel nunca se pinta como netOD.
  (e) la ventana real pinta su pestaña 2 con esa regla y no cambia nada mas (la nota de la pestaña sigue vacia).
  Se prueba en las DIEZ peliculas reales de C.2 (netOD, piso de las esquinas), en ML0 con el piso de la pelicula virgen EPSON179, en la sintetica de PF.0 (netOD y valor de pixel; ademas contra la calibracion de su
  generador) y en los casos que una pelicula real no da, construidos sobre un resultado real con `dataclasses.replace`: una capa sin piso, sin meseta, «ok» sin mesetas, con la meseta no mas oscura que el piso, con un
  solo perfil recortado y sin ningun pixel mas oscuro que el piso (y en valor de pixel, sin piso y sin mesetas).

Rojo contra HEAD (b926ada): 146 de los 177 casos caen, 80 por ASERCION (la barra dice que la capa esta normalizada entre el piso y la meseta y va de 0 a 1, lo pintado es esa capa normalizada, el titulo va en un solo
renglon que invade al de la vecina, el modulo llama a `motor.normalizar`, la ventana real pinta eso) y 66 por la API que HEAD no tiene (`CapaEnUnidades`, sus campos y las seis constantes: HEAD devuelve la tupla
(arreglo, texto, meseta)); ninguno por otra causa. Los 31 que pasan son controles de lo que CD.1 NO cambia: la firma de `dibujar_capas` y la ventana que la llama, que `matplotlib` entra solo en `colorear` y
`dibujar_capas`, y que la netOD negativa ya salia con el color del cero y lo que no es pelicula ya salia transparente en las capas acondicionadas (lo que CD.1 mueve es DONDE se recorta la negativa: del dato al color).

NOTA CD.1b (a8d4dee + CD.1b; P17 de la curva, DA-90): la escala de lo que el DIBUJO pinta dejo de ser el tope PROPIO de cada capa y paso a ser el COMUN de las tres (el mayor de los topes de las capas no recortadas
por el escaner, en la unidad de la base: `escala_comun_esperada`, el oraculo escrito mas abajo). Ocho pruebas de este archivo fijaban el tope propio EN EL DIBUJO (la barra, lo pintado y el titulo) y se actualizaron, cada una
con su motivo en su docstring o en un comentario (clase b del censo): el resto de las aserciones, todas las de `capa_acondicionada` (que sigue dando el tope PROPIO: es la entrada de la regla comun), no cambian.
La regla comun, sus escenas y la ventana tienen su propia prueba: `test_cd1b_escala_comun_de_las_capas.py`.

Importa la produccion POR PRUEBA (`_dib()`, `_pm()`...): en HEAD el archivo se recoge entero y cada prueba cae con su razon (la API que no existe o la asercion que HEAD desmiente), no con un error de coleccion que las
tapa a todas. Trampa 2 (todo `QMessageBox` se parcha: la fixture `dialogos`), Trampa 9 (la ventana se cierra con la receta completa: `fabrica`), Trampa 10 (ningun `lru_cache` ni cache de modulo: cada escena es una
fixture de modulo que se suelta al terminar su turno; las peliculas se leen de `_corpus.pelicula(clave)`; los skips son los de siempre, HI-0, y solo si la pelicula real no esta).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import dataclasses
import gc
import importlib
import inspect
import math
import re
import textwrap
import types
from pathlib import Path

import numpy as np
import pytest
from matplotlib import colormaps
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import _corpus
import _placa_mensual_sintetica as gen
from _e1_ayudas import _cursor_limpio, analizada, app, archivo_placa, dialogos, fabrica, por_gid, sin_simbolos  # noqa: F401
from test_d1_guardado_placa_mensual import bd, clics, placa, plantilla  # noqa: F401  (fixtures de D.1: la BD temporal, la sintetica y sus clics)

RAIZ = Path(__file__).resolve().parent.parent
DIBUJO_PY = RAIZ / "analisisImagenes" / "dibujo_placa_mensual.py"

# --- lo que la regla dice, escrito AQUI a proposito: la prueba fija las constantes y los textos, no los importa
BASE_OD = "densidad óptica neta"
BASE_VP = "valor de píxel normalizado"
UNIDAD_OD = "densidad óptica neta [1]"
UNIDAD_VP = "valor de píxel [nivel]"
VP_MINIMO = 0.5                                  # medio nivel de 8 bits: el piso del logaritmo (el negro del escaner)
FACTOR = 1.1                                     # el tope es 1.1 veces la netOD de la meseta
PERCENTIL = 99.5                                 # el tope de una capa sin meseta valida
TOPE_EN_NIVELES = 255.0
TOPE_SIN_SENAL = 1.0
ANCHO_DEL_TITULO = 52
RECORTADA = "recortada por el escáner"
MOTIVO_DEL_MOTOR = "la meseta está recortada por el escáner"      # lo que el motor escribe en el estado de un perfil recortado (se comprueba contra `pm().MOTIVO_MESETA_RECORTADA`)
SIN_MESETA = "la capa no tiene meseta medida"
ADJETIVO = {"R": "roja", "G": "verde", "B": "azul"}              # concuerda con «capa»
CAPAS = ("R", "G", "B")
NBSP = "\u00a0"                                                    # el espacio de no separacion que une un numero con su unidad en el titulo (CD1-M4)

def titulo_esperado(capa, texto):
    """El titulo de una capa, escrito aqui: «Capa <color>: <texto>» con el espacio antes de cada unidad (« [1]», « [nivel]») sin separacion, partido en renglones de 52 caracteres (CD1-D8 y CD1-M4)."""
    return textwrap.fill(f"Capa {ADJETIVO[capa]}: {texto}".replace(" [", NBSP + "["), ANCHO_DEL_TITULO)


# los cinco puntos (UL, UR, DR, DL y el reticulo) de las diez peliculas mensuales reales: los mismos de C.2 y de `test_c3_barrido.py` (los de ML0 son los clics del cuaderno del fisico)
CLICS = {
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
REALES = tuple(CLICS)
VIRGEN = "ML0_con_la_virgen_EPSON179"
SINT_OD = "SINTETICA_netOD"
SINT_VP = "SINTETICA_valor_de_pixel"
CONSTRUIDAS_OD = ("construida_sin_piso", "construida_sin_meseta", "construida_ok_sin_mesetas", "construida_meseta_no_mas_oscura", "construida_solo_el_inplane_recortado",
                  "construida_ningun_pixel_mas_oscuro", "construida_otra_falla_en_el_crossplane_y_el_inplane_recortado", "construida_solo_el_inplane_con_meseta",
                  "construida_solo_el_crossplane_con_meseta")
CONSTRUIDAS_VP = ("construida_valor_de_pixel_sin_piso", "construida_valor_de_pixel_sin_mesetas")
ESCENAS_DE_LA_ESCALA_COMUN = ("construida_roja_no_recortada_manda", "construida_dos_recortadas_y_una_sin_senal", "construida_ninguna_capa_con_senal")      # CD.1b (R1-AMB-01): solo las recorre su prueba
EN_NETOD = REALES + (VIRGEN, SINT_OD) + CONSTRUIDAS_OD
EN_VALOR_DE_PIXEL = (SINT_VP,) + CONSTRUIDAS_VP
ESCENAS = EN_NETOD + EN_VALOR_DE_PIXEL

todas = pytest.mark.parametrize("escena", ESCENAS, indirect=True)
reales = pytest.mark.parametrize("escena", REALES, indirect=True)
en_netod = pytest.mark.parametrize("escena", EN_NETOD, indirect=True)


def _pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _dib():
    return importlib.import_module("analisisImagenes.dibujo_placa_mensual")


def _P(base=BASE_OD):
    """Los parametros de fabrica con la base pedida (escrita a mano: no se lee de la constante de la produccion)."""
    return {**copy.deepcopy(_pm().VALORES_DE_LA_GEOMETRIA), "base_de_la_medida": base}


# ===================================================================================================== las escenas

def _analizar_real(clave, modo="automatico", referencia=None):
    """El analisis netOD de una pelicula real con sus cinco clics refinados, por el camino de `guardar` (`leer_pelicula`, `refinar_marca` de cada clic, `analizar`)."""
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"HI-0: la pelicula real {clave} no esta ({_corpus.PELICULAS_RAIZ})")
    pm, pel, P = _pm(), _pel(), _P()
    pelicula = pel.leer_pelicula(Path(ruta).read_bytes())
    marcas = [pm.refinar_marca(pelicula.gris, c, P, pel.escala_mm(pelicula.dpi, P), pelicula.validos) for c in CLICS[clave]]
    r = pm.analizar(pelicula, marcas, P, modo_piso=modo, referencia_virgen=referencia)
    assert r.ok, (clave, r.estado)
    return r


def _analizar_sintetica(placa_sintetica, base):
    pm, pel = _pm(), _pel()
    puntos = [placa_sintetica.verdad.marcas_px[k] for k in ("UL", "UR", "DR", "DL", "C")]
    r = pm.analizar(pel.leer_pelicula(placa_sintetica.datos), puntos, _P(base), modo_piso="automatico")
    assert r.ok and r.base == base, (r.estado, r.base)
    return r


def _con_la_capa(r, capa, **cambios):
    """El mismo resultado con UNA capa medida cambiada (`dataclasses.replace`): el caso que una pelicula real no da."""
    return dataclasses.replace(r, capas={**r.capas, capa: dataclasses.replace(r.capas[capa], **cambios)})


def _construida(nombre, base_netod, base_pixel):
    """Los casos construidos sobre la capa verde de un resultado real (netOD: ML0) o de la sintetica en valor de pixel."""
    pm = _pm()
    if nombre in CONSTRUIDAS_VP:
        r = base_pixel
        G = r.capas["G"]
        if nombre == "construida_valor_de_pixel_sin_piso":
            return _con_la_capa(r, "G", piso=None, estado="no medible: el piso de esta capa no se pudo medir")
        return _con_la_capa(r, "G", crossplane=dataclasses.replace(G.crossplane, meseta=None), inplane=dataclasses.replace(G.inplane, meseta=None))      # el estado sigue «ok»
    r = base_netod
    G = r.capas["G"]
    sin_meseta_cross = dataclasses.replace(G.crossplane, meseta=None)
    sin_meseta_in = dataclasses.replace(G.inplane, meseta=None)
    estado_sin_meseta = "no medible: perfil crossplane: la zona central de la meseta no está sobre la película"
    if nombre == "construida_sin_piso":
        return _con_la_capa(r, "G", piso=None, estado="no medible: el piso de esta capa no se pudo medir")
    if nombre == "construida_sin_meseta":
        return _con_la_capa(r, "G", crossplane=sin_meseta_cross, inplane=sin_meseta_in, estado=estado_sin_meseta)
    if nombre == "construida_ok_sin_mesetas":
        return _con_la_capa(r, "G", crossplane=sin_meseta_cross, inplane=sin_meseta_in)                                                                  # el estado sigue «ok»
    if nombre == "construida_meseta_no_mas_oscura":
        mas_clara = float(G.piso) + 5.0
        return _con_la_capa(r, "G", crossplane=dataclasses.replace(G.crossplane, meseta=mas_clara), inplane=dataclasses.replace(G.inplane, meseta=mas_clara))
    if nombre == "construida_solo_el_inplane_recortado":
        estado = f"no medible: perfil inplane: {pm.MOTIVO_MESETA_RECORTADA}: el 90 % de la zona central de la meseta vale 1.5 niveles o menos y la densidad óptica no existe"
        return _con_la_capa(r, "G", inplane=dataclasses.replace(G.inplane, estado=estado), estado=estado)
    if nombre == "construida_otra_falla_en_el_crossplane_y_el_inplane_recortado":
        # `_medir_la_capa` guarda en la capa SOLO la primera falla (`fallas[0]`, el crossplane primero): aqui la del crossplane no es la meseta recortada y el inplane si; el estado de la capa no lo dice
        recortado = f"no medible: perfil inplane: {pm.MOTIVO_MESETA_RECORTADA}: el 90 % de la zona central de la meseta vale 1.5 niveles o menos y la densidad óptica no existe"
        return _con_la_capa(r, "G", crossplane=dataclasses.replace(G.crossplane, meseta=None, estado=estado_sin_meseta), inplane=dataclasses.replace(G.inplane, meseta=1.0, estado=recortado),
                            estado=estado_sin_meseta)
    if nombre == "construida_solo_el_inplane_con_meseta":
        # el crossplane no se pudo medir (sin meseta, como lo deja `perfil_central` al lanzar) y el inplane si: la meseta de la capa es la del que la tiene; la mitad del piso, para que la netOD sea log10(2)
        return _con_la_capa(r, "G", crossplane=dataclasses.replace(G.crossplane, meseta=None, estado=estado_sin_meseta), inplane=dataclasses.replace(G.inplane, meseta=0.5 * float(G.piso)),
                            estado=estado_sin_meseta)
    if nombre == "construida_solo_el_crossplane_con_meseta":
        # el espejo: el inplane sin meseta y el crossplane con la cuarta parte del piso (netOD log10(4)), distinta de la del caso anterior
        sin_inplane = "no medible: perfil inplane: la zona central de la meseta no está sobre la película"
        return _con_la_capa(r, "G", inplane=dataclasses.replace(G.inplane, meseta=None, estado=sin_inplane), crossplane=dataclasses.replace(G.crossplane, meseta=0.25 * float(G.piso)), estado=sin_inplane)
    if nombre in ESCENAS_DE_LA_ESCALA_COMUN:
        # CD.1b, correccion de la ronda 1 (R1-AMB-01): las escenas DIBUJADAS cuya escala comun no es la de una verde o una azul con señal bajo una roja recortada (las diez reales). Solo las usa
        # `test_cd1b_escala_comun_de_las_capas.py`; no estan en CONSTRUIDAS_OD, asi que las pruebas de CD.1 no las recorren.
        g = r.girada
        sin_mesetas = lambda capa: dict(crossplane=dataclasses.replace(r.capas[capa].crossplane, meseta=None, estado=estado_sin_meseta),
                                        inplane=dataclasses.replace(r.capas[capa].inplane, meseta=None, estado=estado_sin_meseta), estado=estado_sin_meseta)
        if nombre == "construida_roja_no_recortada_manda":
            # la roja SIN recortar, con una meseta de netOD 1.0 (la decima parte de su piso): su tope, 1.1, es mayor que el 0.797 de la verde y fija la escala de las tres (una roja asi no existe en las diez reales)
            R = r.capas["R"]
            oscura = float(R.piso) / 10.0
            return _con_la_capa(r, "R", estado="ok", crossplane=dataclasses.replace(R.crossplane, meseta=oscura, estado="ok"), inplane=dataclasses.replace(R.inplane, meseta=oscura, estado="ok"))
        if nombre == "construida_dos_recortadas_y_una_sin_senal":
            # NINGUNA capa de nivel 0 (CD1b-D6): la roja real (recortada), la verde recortada solo en su inplane y la azul entera mas clara que su piso (sin ningun pixel mas oscuro): manda la mayor de las dos recortadas
            estado_g = f"no medible: perfil inplane: {pm.MOTIVO_MESETA_RECORTADA}: el 90 % de la zona central de la meseta vale 1.5 niveles o menos y la densidad óptica no existe"
            clara = dict(g.capas)
            clara["B"] = np.full_like(g.capas["B"], 250.0)
            r2 = _con_la_capa(r, "G", inplane=dataclasses.replace(G.inplane, estado=estado_g), estado=estado_g)
            return dataclasses.replace(_con_la_capa(r2, "B", **sin_mesetas("B")), girada=dataclasses.replace(g, capas=clara))
        assert nombre == "construida_ninguna_capa_con_senal", nombre
        # las tres enteras mas claras que su piso y sin meseta (la roja deja de estar recortada: su estado y el de sus dos perfiles dicen lo mismo que los de las otras): el comun es TOPE_SIN_SENAL
        r3 = r
        for capa in CAPAS:
            r3 = _con_la_capa(r3, capa, **sin_mesetas(capa))
        return dataclasses.replace(r3, girada=dataclasses.replace(g, capas={**g.capas, **{capa: np.full_like(g.capas[capa], 250.0) for capa in CAPAS}}))
    assert nombre == "construida_ningun_pixel_mas_oscuro", nombre
    # la capa verde entera mas clara que su piso y sin meseta: ningun pixel tiene netOD positiva
    g = r.girada
    clara = dict(g.capas)
    clara["G"] = np.full_like(g.capas["G"], 250.0)
    return dataclasses.replace(_con_la_capa(r, "G", crossplane=sin_meseta_cross, inplane=sin_meseta_in, estado=estado_sin_meseta), girada=dataclasses.replace(g, capas=clara))


class Escena:
    """Un resultado del analisis, su pestaña 2 dibujada (`dibujar_capas` en una figura de 13.6 x 6.6 pulgadas, el tamaño de la pestaña) y, por capa, lo que la regla dice que debe salir (`esperado`)."""

    def __init__(self, nombre, resultado, figura):
        self.nombre, self.resultado, self.figura = nombre, resultado, figura
        self._esperado = {}

    def esperado(self, capa):
        if capa not in self._esperado:
            self._esperado[capa] = esperado(self.resultado, capa)
        return self._esperado[capa]

    def escala(self):
        """CD.1b: la escala comun esperada de las tres capas (`escala_comun_esperada`), o None."""
        return escala_comun_esperada(self.resultado, {capa: self.esperado(capa) for capa in CAPAS})

    def soltar(self):
        self.resultado = self.figura = None
        self._esperado.clear()


@pytest.fixture(scope="module")
def ml0():
    """El analisis netOD de ML0 con el piso de las esquinas (la escena «ML0» y la base de los casos construidos), una vez por modulo."""
    yield _analizar_real("ML0")
    gc.collect()


@pytest.fixture(scope="module")
def sintetica():
    """La pelicula sintetica de PF.0 (independiente del motor), una vez por modulo."""
    yield gen.generar("tiff", variante="A", theta_deg=0.4, seed=1)
    gc.collect()


@pytest.fixture(scope="module")
def referencia_virgen():
    """La referencia de la pelicula virgen EPSON179 (el TIFF que el fisico escaneo el 21-10), medida UNA vez por modulo (7.6 s)."""
    ruta = _corpus.pelicula("VIRGEN_EPSON179")
    if ruta is None:
        pytest.skip(f"HI-0: la pelicula virgen EPSON179 no esta ({_corpus.PELICULAS_RAIZ})")
    ref = _pel().piso_de_pelicula_virgen(Path(ruta).read_bytes(), _P(), "EPSON179.TIF", fecha_calculo="2026-10-21")
    assert ref.estado == "ok", ref.estado
    yield ref
    gc.collect()


@pytest.fixture(scope="module")
def escena(request, ml0, sintetica):
    """La escena que pide cada prueba (`indirect`): se analiza una vez, se dibuja una vez y se suelta cuando el modulo pasa a la siguiente (cada una retiene unos 125 MB)."""
    nombre = request.param
    if nombre == "ML0":
        r = ml0
    elif nombre in REALES:
        r = _analizar_real(nombre)
    elif nombre == VIRGEN:
        r = _analizar_real("ML0", modo="virgen", referencia=request.getfixturevalue("referencia_virgen"))
    elif nombre == SINT_OD:
        r = _analizar_sintetica(sintetica, BASE_OD)
    elif nombre == SINT_VP:
        r = _analizar_sintetica(sintetica, BASE_VP)
    elif nombre in CONSTRUIDAS_VP:
        r = _construida(nombre, None, _analizar_sintetica(sintetica, BASE_VP))
    else:
        r = _construida(nombre, ml0, None)
    figura = Figure(figsize=(13.6, 6.6), dpi=100, layout="constrained")
    _dib().dibujar_capas(figura, r)
    e = Escena(nombre, r, figura)
    yield e
    e.soltar()
    del r
    gc.collect()


# ===================================================================================================== el oraculo: la regla, escrita aqui

def esperado(r, capa):
    """Lo que la regla dice que sale de esa capa, por una ruta escrita AQUI con numpy (no la de `valores_en_la_base` ni la de la produccion): `SimpleNamespace(valores, tope, unidad, texto, meseta, motivo)`.
    La unica entrada del motor es lo que el MOTOR midio: el piso de la capa, las mesetas y el estado de sus dos perfiles y la pelicula girada."""
    g, m = r.girada, r.capas[capa]
    mesetas = [p.meseta for p in (m.crossplane, m.inplane) if p.meseta is not None]
    meseta_en_niveles = (float(mesetas[0]) + float(mesetas[1])) / 2.0 if len(mesetas) == 2 else (float(mesetas[0]) if mesetas else None)
    en_niveles = r.base == BASE_VP or m.piso is None
    if en_niveles:
        valores = np.array(g.capas[capa], dtype=np.float32)
    else:
        valores = np.log10(float(m.piso) / np.maximum(np.asarray(g.capas[capa], dtype=np.float64), VP_MINIMO)).astype(np.float32)
    valores[~g.validos] = np.nan
    if en_niveles:
        escala = "valor de píxel de 0 a 255 [nivel]"
        if r.base != BASE_VP:                                                    # netOD sin piso: sin piso no hay densidad optica
            motivo = f"sin piso no hay densidad óptica: {m.estado}"
            return types.SimpleNamespace(valores=valores, tope=TOPE_EN_NIVELES, unidad=UNIDAD_VP, texto=f"{escala}; {motivo}", meseta=None, motivo=motivo)
        if m.piso is None or meseta_en_niveles is None:
            motivo = m.estado if m.estado != "ok" else SIN_MESETA
            return types.SimpleNamespace(valores=valores, tope=TOPE_EN_NIVELES, unidad=UNIDAD_VP, texto=f"{escala}; {motivo}", meseta=meseta_en_niveles, motivo=motivo)
        return types.SimpleNamespace(valores=valores, tope=TOPE_EN_NIVELES, unidad=UNIDAD_VP, texto=f"{escala}; piso {float(m.piso):.1f} y meseta {meseta_en_niveles:.1f} [nivel]",
                                     meseta=meseta_en_niveles, motivo=None)
    recortada = any(MOTIVO_DEL_MOTOR in p.estado for p in (m.crossplane, m.inplane))
    meseta = None if meseta_en_niveles is None else float(np.log10(float(m.piso) / np.maximum(np.float64(meseta_en_niveles), VP_MINIMO)))
    if recortada:
        motivo = RECORTADA
    elif meseta is None:
        motivo = m.estado if m.estado != "ok" else SIN_MESETA
    elif not meseta > 0:
        motivo = "la meseta no es más oscura que el piso"
    else:
        tope = FACTOR * meseta
        return types.SimpleNamespace(valores=valores, tope=tope, unidad=UNIDAD_OD, texto=f"de 0 a {tope:.3f} [1]: 1.1 veces su meseta, {meseta:.3f} [1]", meseta=meseta, motivo=None)
    finitos = valores[np.isfinite(valores)]
    tope = float(np.percentile(finitos, PERCENTIL)) if finitos.size else math.nan
    if not (math.isfinite(tope) and tope > 0):
        return types.SimpleNamespace(valores=valores, tope=TOPE_SIN_SENAL, unidad=UNIDAD_OD, texto=f"{motivo}; de 0 a 1 [1]: ningún píxel es más oscuro que el piso", meseta=None, motivo=motivo)
    return types.SimpleNamespace(valores=valores, tope=tope, unidad=UNIDAD_OD, texto=f"{motivo}; de 0 a {tope:.3f} [1]: el percentil 99.5 de la capa", meseta=None, motivo=motivo)


def jet(x):
    """El mapa de color `jet` de un arreglo ya llevado a 0-1 (lo de afuera se recorta; un NaN queda transparente): RGBA uint8, escrito aqui con matplotlib."""
    return colormaps["jet"](np.clip(x, 0.0, 1.0), bytes=True)


def pintado(figura, k):
    """La imagen RGBA uint8 que la pestaña 2 puso en el eje de la capa k."""
    return np.asarray(por_gid(figura.axes[k], "capas:imagen")[0].get_array())


# --- CD.1b (P17, 23-10): la escala COMUN de las tres capas, escrita AQUI como el oraculo de lo pintado, de la barra y del titulo. Parte de lo que dice `esperado(...)` de cada capa (la regla de CD.1, que no
# cambia) y nunca importa las funciones de la produccion: los niveles de preferencia, el origen y los textos estan escritos a mano. La usan las pruebas de CD.1 que fijan lo que el DIBUJO pinta (su motivo: el dibujo
# ya no pinta cada capa con su tope propio, sino con el comun) y `test_cd1b_escala_comun_de_las_capas.py`.
ORIGEN_ESPERADO = {0: "la mayor de las no recortadas", 1: "la mayor de las recortadas por el escáner: no hay capa sin recortar", 2: "ningún píxel es más oscuro que el piso"}
FINAL_DEL_TEXTO_SIN_SENAL = "ningún píxel es más oscuro que el piso"             # como termina el texto de CD.1 de una capa sin ningun pixel mas oscuro que el piso


def nivel_esperado(esp):
    """0: el tope de la capa sale de su pelicula y no esta recortada por el escaner (con su meseta o con su percentil); 1: esta recortada por el escaner; 2: ningun pixel mas oscuro que el piso (el tope 1 no sale de
    la pelicula). La capa sin señal se reconoce aqui por lo que dice su texto, no por su tope."""
    if esp.texto.endswith(FINAL_DEL_TEXTO_SIN_SENAL):
        return 2
    return 1 if esp.motivo == RECORTADA else 0


def escala_comun_esperada(r, esps):
    """`esps`: {capa: esperado(r, capa)}. La escala comun de las capas que estan en la unidad de la base: el MAYOR de los topes de las del MENOR nivel presente (CD1b-D1, D2, D3 y D6); None si ninguna lo esta."""
    unidad = UNIDAD_OD if r.base == BASE_OD else UNIDAD_VP
    candidatas = [c for c in CAPAS if esps[c].unidad == unidad]
    if not candidatas:
        return None
    nivel = min(nivel_esperado(esps[c]) for c in candidatas)
    entre = [c for c in candidatas if nivel_esperado(esps[c]) == nivel]
    tope = max(esps[c].tope for c in entre)
    return types.SimpleNamespace(tope=tope, unidad=unidad, capa=next(c for c in entre if esps[c].tope == tope), nivel=nivel)


def tope_comun_esperado(escala, esp):
    """Con que tope se pinta la capa y va su barra: el comun si esta en su unidad; si no, el suyo."""
    return escala.tope if escala is not None and esp.unidad == escala.unidad else esp.tope


def texto_comun_esperado(escala, esp):
    """Lo que dice el titulo de la capa tras «Capa <color>: »: el texto de CD.1 si no se pinta con la escala comun o si el analisis esta en valor de pixel; si no, lo suyo (su meseta, o su motivo) y la escala comun."""
    if escala is None or esp.unidad != escala.unidad or escala.unidad == UNIDAD_VP:
        return esp.texto
    propio = f"meseta {esp.meseta:.3f} [1]" if esp.motivo is None else esp.motivo
    return f"{propio}; escala común de 0 a {escala.tope:.3f} [1], {ORIGEN_ESPERADO[escala.nivel]}"


# ===================================================================================================== (a) y (b) la regla de la escala

class TestElArregloYLaEscalaSonLosDeLaRegla:
    @todas
    def test_el_arreglo_de_cada_capa_es_su_unidad_absoluta_sin_normalizar_ni_recortar_y_con_nan_fuera_de_la_pelicula(self, escena):
        """`valores` es la netOD de cada pixel (a 2e-6 de la formula escrita en esta prueba), sin normalizar a la meseta y con la netOD negativa conservada; en valor de pixel (o sin piso) son los niveles; NaN
        exactamente donde la pelicula girada no tiene dato."""
        r, g = escena.resultado, escena.resultado.girada
        assert (~g.validos).any(), "compuerta: el giro deja pixeles fuera de la pelicula y la prueba los ve"
        for capa in CAPAS:
            c = _dib().capa_acondicionada(r, capa)
            esp = escena.esperado(capa)
            assert c.valores.dtype == np.float32 and c.valores.shape == esp.valores.shape == g.capas[capa].shape, (capa, c.valores.dtype, c.valores.shape)
            assert np.array_equal(np.isnan(c.valores), ~g.validos), f"{capa}: NaN exactamente donde la pelicula girada no tiene dato"
            fin = np.isfinite(esp.valores)
            assert np.allclose(c.valores[fin], esp.valores[fin], atol=2e-6, rtol=0), (capa, float(np.max(np.abs(c.valores[fin] - esp.valores[fin]))))
            if esp.unidad == UNIDAD_OD:
                assert float(np.nanmin(esp.valores)) < 0, f"{capa}: compuerta, hay netOD negativa (ruido bajo el piso) y debe conservarse en el dato"
                assert float(np.nanmin(c.valores)) < 0 and np.array_equal(c.valores[fin] < 0, esp.valores[fin] < 0), f"{capa}: la netOD negativa no se recorta en el dato"

    @todas
    def test_el_tope_la_unidad_el_texto_la_meseta_y_el_motivo_son_los_de_la_regla(self, escena):
        for capa in CAPAS:
            c = _dib().capa_acondicionada(escena.resultado, capa)
            esp = escena.esperado(capa)
            assert c.tope == pytest.approx(esp.tope, rel=1e-9, abs=0), (capa, c.tope, esp.tope)
            assert c.unidad == esp.unidad, (capa, c.unidad)
            assert c.texto == esp.texto, (capa, c.texto)
            assert c.motivo == esp.motivo, (capa, c.motivo)
            if esp.meseta is None:
                assert c.meseta is None, (capa, c.meseta)
            else:
                assert c.meseta == pytest.approx(esp.meseta, rel=1e-9, abs=0), (capa, c.meseta)

    @todas
    def test_lo_pintado_es_el_mapa_jet_de_los_valores_entre_cero_y_el_tope(self, escena):
        """Lo que `dibujar_capas` puso en el eje es `jet(valores / tope)` en RGBA uint8, pixel a pixel, con la extension y la interpolacion de siempre. CD.1b (motivo del cambio de esta prueba, clase b): el tope
        con que se lleva a 0-1 ya no es el PROPIO de cada capa sino el COMUN de las tres (`escala_comun_esperada`; la capa en otra unidad conserva el suyo)."""
        r = escena.resultado
        esc = escena.escala()
        ox, oy = r.girada.origen
        for k, capa in enumerate(CAPAS):
            esp = escena.esperado(capa)
            imagen = por_gid(escena.figura.axes[k], "capas:imagen")[0]
            arreglo = np.asarray(imagen.get_array())
            alto, ancho = esp.valores.shape
            assert arreglo.dtype == np.uint8 and arreglo.shape == (alto, ancho, 4), "RGBA uint8 con el mapa de color ya aplicado: una imagen 2D con mapa de color pedia 2 GB"
            assert np.array_equal(arreglo, jet(esp.valores / np.float32(tope_comun_esperado(esc, esp)))), f"{capa}: lo pintado no es jet(valores / tope)"
            assert imagen.get_interpolation() == "nearest" and tuple(map(float, imagen.get_extent())) == (ox - 0.5, ox + ancho - 0.5, oy + alto - 0.5, oy - 0.5)

    @todas
    def test_la_barra_dice_su_unidad_y_va_de_cero_al_tope(self, escena):
        """CD.1b (motivo del cambio, clase b): el tope de la barra es el COMUN de las tres capas (el de la capa en otra unidad, el suyo)."""
        esc = escena.escala()
        assert len(escena.figura.axes) == 6 and [e.get_label() for e in escena.figura.axes[3:]] == ["<colorbar>"] * 3
        for k, capa in enumerate(CAPAS):
            esp = escena.esperado(capa)
            barra = escena.figura.axes[3 + k]
            assert barra.get_xlabel() == esp.unidad, (capa, barra.get_xlabel())
            assert tuple(float(v) for v in barra.get_xlim()) == (0.0, pytest.approx(tope_comun_esperado(esc, esp), rel=1e-9)), (capa, barra.get_xlim())

    @todas
    def test_el_titulo_de_cada_capa_es_el_texto_de_su_escala_partido_en_renglones_de_52_caracteres(self, escena):
        """CD.1b (motivo del cambio, clase b): el texto de la escala que dice el titulo es el de la escala COMUN (`texto_comun_esperado`: su meseta, o por que no la tiene, y de 0 a cuanto y de que capas sale la
        escala comun); en valor de pixel o en una capa en otra unidad es el de CD.1 tal cual."""
        esc = escena.escala()
        for k, capa in enumerate(CAPAS):
            texto = texto_comun_esperado(esc, escena.esperado(capa))
            titulo = escena.figura.axes[k].get_title()
            assert titulo == titulo_esperado(capa, texto), (capa, titulo)
            assert all(len(renglon) <= ANCHO_DEL_TITULO for renglon in titulo.split("\n")), (capa, titulo)
            assert " ".join(titulo.split("\n")).replace(NBSP, " ") == f"Capa {ADJETIVO[capa]}: {texto}", (capa, "partir el titulo no pierde ni agrega nada")
            assert not titulo.endswith(".") and sin_simbolos(titulo), (capa, "sin punto final ni simbolos de correcto o incorrecto (DA-18)")

    @todas
    def test_una_unidad_nunca_queda_sola_al_principio_de_un_renglon_del_titulo(self, escena):
        """Hallazgo titulo-parte-numero-y-unidad (revision de CD.1): `textwrap` parte por espacios y la roja de ML0 decia «... de 0 a 2.342» en un renglon y «[1]: el percentil 99.5 de la capa» en el siguiente. El espacio
        antes de cada unidad («[1]», «[nivel]») es de no separacion: el caracter que precede a una unidad es NBSP, nunca un espacio ni un salto de renglon, y ningun renglon empieza con una unidad."""
        for k, capa in enumerate(CAPAS):
            titulo = escena.figura.axes[k].get_title()
            unidades = list(re.finditer(r"\[[^\]]*\]", titulo))
            assert unidades, (capa, "compuerta: el titulo de toda capa lleva al menos una unidad", titulo)
            for u in unidades:
                assert titulo[u.start() - 1] == NBSP, (capa, u.group(), repr(titulo))
            assert not any(renglon.startswith("[") for renglon in titulo.split("\n")), (capa, titulo)


# ===================================================================================================== (c-bis) la barra pinta con el mismo mapa que la imagen

class TestLaBarraPintaConElMismoMapaQueLaImagen:
    @pytest.mark.parametrize("escena", ["ML0", SINT_VP, "construida_sin_piso"], indirect=True)
    def test_la_barra_pinta_con_el_mismo_mapa_de_color_que_la_imagen(self, escena):
        """Hallazgo R2: las pruebas de la barra miraban su rotulo y sus limites; con la barra en `jet_r` (invertido) cada color señalaba una netOD que no es la pintada y todo seguia verde. Se mide en los PIXELES de la
        figura dibujada: a la fraccion f del ancho de la barra el color es `jet(f)` (el valor f * tope se pinta en la imagen `jet(valor / tope)`). Medido: la diferencia con `jet` es de 5 niveles como mucho y la de
        `jet_r` de 165 o mas en estas fracciones; la tolerancia es 12."""
        canvas = FigureCanvasAgg(escena.figura)
        canvas.draw()
        pixeles = np.asarray(canvas.buffer_rgba())
        for k in range(3):
            caja = escena.figura.axes[3 + k].get_window_extent()
            fila = int(round(pixeles.shape[0] - (caja.y0 + caja.y1) / 2))
            for f in (0.1, 0.2, 0.3, 0.7, 0.8, 0.9):
                real = pixeles[fila, int(caja.x0 + f * caja.width), :3].astype(int)
                esperado = jet(np.array([f]))[0, :3].astype(int)
                assert np.abs(real - esperado).max() <= 12, (CAPAS[k], f, real.tolist(), esperado.tolist())


# ===================================================================================================== (c) lo pintado: el color del cero y lo transparente

class TestLaNetODNegativaYLoQueNoEsPelicula:
    @en_netod
    def test_una_netod_negativa_se_pinta_con_el_color_del_cero_y_no_queda_transparente(self, escena):
        """El ruido bajo el piso no se recorta en el dato (arriba) sino al colorear: sale con el color del cero, opaco (jet(0) = [0, 0, 127, 255])."""
        for k, capa in enumerate(CAPAS):
            esp = escena.esperado(capa)
            if esp.unidad != UNIDAD_OD:
                continue                                                          # esa capa se pinta en niveles (sin piso)
            negativos = np.argwhere(esp.valores < 0)
            assert len(negativos) > 0, f"{capa}: compuerta, hay netOD negativa"
            salto = max(1, len(negativos) // 200)
            arreglo = pintado(escena.figura, k)
            for i, j in negativos[::salto]:
                assert arreglo[i, j].tolist() == [0, 0, 127, 255], (capa, i, j, float(esp.valores[i, j]), arreglo[i, j].tolist())

    @todas
    def test_lo_que_no_es_pelicula_queda_transparente_y_la_pelicula_opaca(self, escena):
        validos = escena.resultado.girada.validos
        for k, capa in enumerate(CAPAS):
            alfa = pintado(escena.figura, k)[:, :, 3]
            assert (alfa[~validos] == 0).all() and (alfa[validos] == 255).all(), f"{capa}: transparente fuera de la pelicula girada y opaca dentro"


# ===================================================================================================== el valor de pixel nunca se pinta como netOD

class TestElValorDePixelSePintaEnNiveles:
    @pytest.mark.parametrize("escena", [SINT_VP], indirect=True)
    def test_un_registro_en_valor_de_pixel_se_pinta_en_niveles_de_0_a_255_con_su_barra_y_nunca_como_netod(self, escena):
        r = escena.resultado
        assert r.base == BASE_VP
        for k, capa in enumerate(CAPAS):
            c = _dib().capa_acondicionada(r, capa)
            niveles = np.array(r.girada.capas[capa], dtype=np.float32)
            niveles[~r.girada.validos] = np.nan
            fin = np.isfinite(niveles)
            assert c.unidad == UNIDAD_VP and c.tope == TOPE_EN_NIVELES
            assert np.array_equal(c.valores[fin], niveles[fin]) and float(np.nanmax(c.valores)) > 20 and float(np.nanmin(c.valores)) >= 0, f"{capa}: son los niveles de la pelicula (una netOD de 8 bits nunca pasa de 2.71), no una densidad optica"
            assert "densidad" not in c.texto and "[1]" not in c.texto and c.texto.startswith("valor de píxel de 0 a 255 [nivel]; piso "), (capa, c.texto)
            barra = escena.figura.axes[3 + k]
            assert barra.get_xlabel() == UNIDAD_VP and tuple(float(v) for v in barra.get_xlim()) == (0.0, 255.0)
            # el campo, mas oscuro que la pelicula virgen, sale en el extremo azul del jet sin invertir y la pelicula virgen cerca del rojo (los niveles de 8 bits altos)
            arreglo = pintado(escena.figura, k)
            claro = np.unravel_index(np.nanargmax(niveles), niveles.shape)
            oscuro = np.unravel_index(np.nanargmin(niveles), niveles.shape)
            assert arreglo[claro].tolist() == jet(np.array([niveles[claro]], dtype=np.float32) / np.float32(255.0))[0].tolist()
            assert arreglo[oscuro].tolist() == jet(np.array([niveles[oscuro]], dtype=np.float32) / np.float32(255.0))[0].tolist()
            assert arreglo[oscuro][2] > arreglo[oscuro][0], f"{capa}: el nivel mas bajo sale azul (jet sin invertir)"


# ===================================================================================================== la verdad conocida y los numeros medidos

class TestLaEscalaContraVerdadConocida:
    @pytest.mark.parametrize("escena", [SINT_OD], indirect=True)
    def test_en_la_sintetica_el_tope_de_cada_capa_sale_de_la_calibracion_de_su_generador(self, escena):
        """El generador de PF.0 da el nivel de la meseta de cada capa sin ruido (`gen.CALIB`): el tope es 1.1 veces log10(piso medido / ese nivel). La roja de la sintetica esta recortada por el escaner (su meseta
        vale 1 nivel): su tope es el negro del escaner, log10(piso / 0.5). Verdad que no sale del motor ni del dibujo."""
        r = escena.resultado
        for capa, i in (("G", gen.INDICE_CAPA["G"]), ("B", gen.INDICE_CAPA["B"])):
            piso = float(r.capas[capa].piso)
            assert abs(piso - gen.CALIB["virgen_bgr"][i]) < 8.0, f"{capa}: compuerta, el piso de las esquinas esta cerca de la pelicula virgen del generador"
            verdad = FACTOR * math.log10(piso / gen.CALIB["meseta_bgr"][i])
            assert _dib().capa_acondicionada(r, capa).tope == pytest.approx(verdad, abs=0.005), (capa, verdad)
        c = _dib().capa_acondicionada(r, "R")
        assert c.motivo == RECORTADA and c.tope == pytest.approx(math.log10(float(r.capas["R"].piso) / VP_MINIMO), abs=1e-6)

    @pytest.mark.parametrize("escena", ["ML0"], indirect=True)
    def test_los_topes_de_ML0_son_los_medidos_en_el_pre_vuelo_del_23_10(self, escena):
        """ML0 (la pelicula del cuaderno del fisico, piso de las esquinas): la verde de 0 a 0.797, la azul de 0 a 0.349 y la roja, recortada, hasta el negro del escaner (2.342). Medidos por el pre-vuelo de Opus."""
        for capa, tope in (("R", 2.342), ("G", 0.797), ("B", 0.349)):
            assert _dib().capa_acondicionada(escena.resultado, capa).tope == pytest.approx(tope, abs=1.5e-3), capa

    @pytest.mark.parametrize("escena", [VIRGEN], indirect=True)
    def test_con_la_pelicula_virgen_el_cero_de_la_escala_es_su_media_y_no_el_de_las_esquinas(self, escena):
        """El cero de la escala es el piso del analisis: con la virgen EPSON179 (R 152.12, G 194.11, B 86.77 medidos el 22-10) la escala sale de log10(194.11 / meseta), mas ancha que la de las esquinas (0.797)."""
        r = escena.resultado
        assert r.piso.modo == "virgen"
        for capa, piso in (("R", 152.12), ("G", 194.11), ("B", 86.77)):
            assert float(r.capas[capa].piso) == pytest.approx(piso, abs=0.05), capa
        for capa, tope in (("R", 2.483), ("G", 0.841), ("B", 0.376)):
            assert _dib().capa_acondicionada(r, capa).tope == pytest.approx(tope, abs=1.5e-3), capa

    @reales
    def test_la_roja_de_las_diez_peliculas_reales_esta_recortada_por_el_escaner_y_su_escala_llega_al_negro(self, escena):
        """El rojo a 800 UM esta recortado por el escaner (la mediana de su meseta, de 0.5 a 1 nivel): no tiene netOD. Su escala va hasta el percentil 99.5 de la capa, que es el negro del escaner,
        log10(piso / 0.5), y el titulo lo dice. Es lo que el motor dice (`pm().MOTIVO_MESETA_RECORTADA`) y el dibujo reconoce."""
        r = escena.resultado
        assert _pm().MOTIVO_MESETA_RECORTADA == MOTIVO_DEL_MOTOR
        m = r.capas["R"]
        assert MOTIVO_DEL_MOTOR in m.crossplane.estado + m.inplane.estado, "compuerta: el motor dice que el rojo esta recortado"
        c = _dib().capa_acondicionada(r, "R")
        assert c.motivo == RECORTADA and c.meseta is None and c.texto.startswith("recortada por el escáner; de 0 a ")
        assert c.tope == pytest.approx(math.log10(float(m.piso) / VP_MINIMO), abs=1e-6)
        assert escena.figura.axes[0].get_title().replace("\n", " ").replace(NBSP, " ").startswith("Capa roja: recortada por el escáner; escala común de 0 a "), "el titulo lo dice (sin importar donde se parte el renglon); CD.1b: la escala que dice es la comun, su tope propio (hasta el negro) es el de `capa_acondicionada`"


# ===================================================================================================== los casos que una pelicula real no da (los textos, escritos a mano)

class TestLosCasosQueUnaPeliculaRealNoDa:
    @pytest.mark.parametrize("escena", ["construida_sin_piso"], indirect=True)
    def test_en_netod_una_capa_sin_piso_se_pinta_en_niveles_y_dice_que_sin_piso_no_hay_densidad_optica(self, escena):
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert c.texto == "valor de píxel de 0 a 255 [nivel]; sin piso no hay densidad óptica: no medible: el piso de esta capa no se pudo medir"
        assert c.tope == 255.0 and c.unidad == UNIDAD_VP and c.meseta is None and c.motivo.startswith("sin piso no hay densidad óptica: ")
        assert escena.figura.axes[4].get_xlabel() == UNIDAD_VP and tuple(escena.figura.axes[4].get_xlim()) == (0.0, 255.0), "la barra de la capa sin piso es la de niveles, no la de la netOD"
        assert float(np.nanmax(c.valores)) <= 255.0 and float(np.nanmin(c.valores)) >= 0.0, "son los niveles de la capa, no una densidad optica"
        otras = _dib().capa_acondicionada(escena.resultado, "B")
        assert otras.unidad == UNIDAD_OD, "compuerta: las otras dos capas siguen en netOD"

    @pytest.mark.parametrize("escena", ["construida_sin_meseta"], indirect=True)
    def test_una_capa_sin_meseta_medida_va_al_percentil_y_dice_el_estado_del_motor(self, escena):
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert c.texto.startswith("no medible: perfil crossplane: la zona central de la meseta no está sobre la película; de 0 a ")
        assert c.texto.endswith(" [1]: el percentil 99.5 de la capa") and c.tope == pytest.approx(0.860, abs=1e-3) and c.meseta is None
        finitos = c.valores[np.isfinite(c.valores)]
        assert c.tope == pytest.approx(float(np.percentile(finitos, 99.5)), rel=1e-6), "el percentil 99.5 de lo finito (no el maximo)"
        assert c.tope < float(np.max(finitos)) - 0.5, "compuerta: en la verde el percentil 99.5 no es el maximo (hay pixeles muy oscuros: tinta y motas)"

    @pytest.mark.parametrize("escena", ["construida_ok_sin_mesetas"], indirect=True)
    def test_una_capa_ok_sin_mesetas_dice_que_no_tiene_meseta_y_no_repite_su_estado(self, escena):
        assert escena.resultado.capas["G"].estado == "ok", "compuerta: el estado de la capa sigue siendo ok"
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert c.texto.startswith("la capa no tiene meseta medida; de 0 a ") and c.texto.endswith(" [1]: el percentil 99.5 de la capa")
        assert c.motivo == "la capa no tiene meseta medida" and not c.texto.startswith("ok")

    @pytest.mark.parametrize("escena", ["construida_meseta_no_mas_oscura"], indirect=True)
    def test_una_meseta_no_mas_oscura_que_el_piso_no_da_una_escala_negativa_y_va_al_percentil(self, escena):
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert c.texto.startswith("la meseta no es más oscura que el piso; de 0 a ") and c.texto.endswith(" [1]: el percentil 99.5 de la capa")
        assert c.tope > 0 and c.tope == pytest.approx(0.860, abs=1e-3) and c.meseta is None
        assert escena.figura.axes[4].get_xlim()[1] > 0

    @pytest.mark.parametrize("escena", ["construida_solo_el_inplane_recortado"], indirect=True)
    def test_basta_que_uno_de_los_dos_perfiles_este_recortado_para_que_la_capa_lo_diga(self, escena):
        r = escena.resultado
        assert r.capas["G"].crossplane.estado == "ok" and _pm().MOTIVO_MESETA_RECORTADA in r.capas["G"].inplane.estado, "compuerta: solo el inplane esta recortado"
        c = _dib().capa_acondicionada(r, "G")
        assert c.texto.startswith("recortada por el escáner; de 0 a ") and c.motivo == RECORTADA and c.tope == pytest.approx(0.860, abs=1e-3) and c.meseta is None

    @pytest.mark.parametrize("escena", ["construida_otra_falla_en_el_crossplane_y_el_inplane_recortado"], indirect=True)
    def test_la_recortada_se_decide_por_los_dos_perfiles_y_no_por_el_estado_de_la_capa(self, escena):
        """Hallazgo R1: el motor guarda en la capa solo la PRIMERA falla (el crossplane primero). Si el crossplane falla por otra razon y el inplane esta recortado, el estado de la capa no dice «recortada» y la
        capa lo esta: su meseta (1 nivel) no es una densidad optica y no puede fijar el tope. Decidirlo por el estado de la capa pinta una meseta recortada como valida (tope 2.5 en vez de 0.86)."""
        r = escena.resultado
        G = r.capas["G"]
        assert _pm().MOTIVO_MESETA_RECORTADA not in G.estado and G.crossplane.meseta is None and _pm().MOTIVO_MESETA_RECORTADA in G.inplane.estado and G.inplane.meseta == 1.0, "compuerta: solo el inplane esta recortado y la capa no lo dice"
        c = _dib().capa_acondicionada(r, "G")
        assert c.texto.startswith("recortada por el escáner; de 0 a ") and c.motivo == RECORTADA and c.meseta is None
        assert c.tope == pytest.approx(0.860, abs=1e-3), "el percentil 99.5 de la capa, no 1.1 veces la netOD de una meseta recortada"
        # CD.1b (motivo del cambio, clase b): la barra de la verde va de 0 al tope COMUN y no al suyo: la roja y la verde estan recortadas y la unica no recortada es la azul (0.349); si la verde se tomara por no
        # recortada su percentil (0.860) mandaria sobre las tres, que es lo que esta prueba vigila en el tope propio y aqui, en la escala comun
        assert tuple(float(v) for v in escena.figura.axes[4].get_xlim()) == (0.0, pytest.approx(tope_comun_esperado(escena.escala(), escena.esperado("G")), rel=1e-9))
        assert escena.escala().capa == "B" and escena.escala().tope == pytest.approx(0.349, abs=1.5e-3)

    @pytest.mark.parametrize("escena, meseta, tope, texto", [
        ("construida_solo_el_inplane_con_meseta", math.log10(2.0), 1.1 * math.log10(2.0), "de 0 a 0.331 [1]: 1.1 veces su meseta, 0.301 [1]"),
        ("construida_solo_el_crossplane_con_meseta", math.log10(4.0), 1.1 * math.log10(4.0), "de 0 a 0.662 [1]: 1.1 veces su meseta, 0.602 [1]"),
    ], indirect=["escena"])
    def test_la_meseta_de_un_solo_perfil_medido_es_la_de_la_capa_y_fija_la_escala(self, escena, meseta, tope, texto):
        """Hallazgo R3: la meseta de la capa es el promedio de las de sus dos perfiles «o la del que la tiene». Con un solo perfil medido (el otro sin meseta y no medible) la capa conserva su escala; exigir las dos
        la mandaria al percentil. Los valores salen de la cuenta a mano: la meseta es la mitad (o la cuarta parte) del piso, su netOD log10(2) (o log10(4)) y el tope 1.1 veces eso; cada caso con el perfil medido
        en un eje distinto, para que no se pueda tomar siempre el mismo."""
        G = escena.resultado.capas["G"]
        assert [p.meseta is None for p in (G.crossplane, G.inplane)].count(True) == 1 and G.estado != "ok", "compuerta: un solo perfil con meseta y la capa no medible por el otro"
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert c.meseta == pytest.approx(meseta, rel=1e-9) and c.tope == pytest.approx(tope, rel=1e-9) and c.motivo is None
        assert c.texto == texto and c.unidad == UNIDAD_OD
        # CD.1b (motivo del cambio, clase b): la barra de la verde va de 0 al tope COMUN (el mayor de las no recortadas: su 0.331 o su 0.662 contra el 0.349 de la azul); su tope propio (arriba) no cambia
        comun = max(tope, 0.349)
        assert tuple(float(v) for v in escena.figura.axes[4].get_xlim()) == (0.0, pytest.approx(comun, abs=1.5e-3))
        assert escena.escala().tope == pytest.approx(comun, abs=1.5e-3)

    @pytest.mark.parametrize("escena", ["construida_ningun_pixel_mas_oscuro"], indirect=True)
    def test_sin_ningun_pixel_mas_oscuro_que_el_piso_la_escala_va_de_0_a_1_y_no_tiene_ancho_cero(self, escena):
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert float(np.nanmax(c.valores)) < 0, "compuerta: ningun pixel es mas oscuro que el piso"
        assert c.tope == 1.0 and c.texto.endswith("; de 0 a 1 [1]: ningún píxel es más oscuro que el piso") and c.meseta is None
        # CD.1b (motivo del cambio, clase b; CD1b-D2): el tope 1 de la capa sin señal es el SUYO (la escala no tiene ancho cero); la barra de la verde va de 0 al tope COMUN: mientras la azul tenga un tope que sale de su
        # pelicula (0.349) el 1 no manda. Con las tres sin señal la comun si es 1 (escena S7 de `test_cd1b_escala_comun_de_las_capas.py`)
        assert tuple(float(v) for v in escena.figura.axes[4].get_xlim()) == (0.0, pytest.approx(0.349, abs=1.5e-3))
        assert escena.escala().capa == "B" and escena.escala().nivel == 0
        assert (pintado(escena.figura, 1)[escena.resultado.girada.validos] == [0, 0, 127, 255]).all(), "todo lo que es pelicula sale con el color del cero"

    @pytest.mark.parametrize("escena", ["construida_valor_de_pixel_sin_piso"], indirect=True)
    def test_en_valor_de_pixel_una_capa_sin_piso_se_pinta_en_niveles_y_dice_por_que(self, escena):
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert c.texto == "valor de píxel de 0 a 255 [nivel]; no medible: el piso de esta capa no se pudo medir" and c.tope == 255.0 and c.unidad == UNIDAD_VP

    @pytest.mark.parametrize("escena", ["construida_valor_de_pixel_sin_mesetas"], indirect=True)
    def test_en_valor_de_pixel_una_capa_sin_mesetas_se_pinta_en_niveles_y_dice_que_no_tiene_meseta(self, escena):
        c = _dib().capa_acondicionada(escena.resultado, "G")
        assert c.texto == "valor de píxel de 0 a 255 [nivel]; la capa no tiene meseta medida" and c.tope == 255.0 and c.unidad == UNIDAD_VP and c.meseta is None


# ===================================================================================================== el dibujo: que los tres titulos quepan

class TestLosTitulosDeLasTresCapasNoSePisan:
    @pytest.mark.parametrize("escena", ["ML0", "construida_sin_meseta"], indirect=True)
    @pytest.mark.parametrize("ancho_pulgadas", [13.6, 11.0])
    def test_el_titulo_de_cada_capa_cabe_en_la_figura_y_no_invade_el_de_la_vecina(self, escena, ancho_pulgadas):
        """CD1-D8: sin partir, el titulo de la roja («recortada por el escaner; de 0 a 2.342 [1]: el percentil 99.5 de la capa») mide mas que su eje y, en una pantalla mas angosta, invade el de la verde y se
        sale de la figura. Se mide con la caja de cada titulo (`get_window_extent`) en dos anchos de figura."""
        figura = Figure(figsize=(ancho_pulgadas, 6.6), dpi=100, layout="constrained")
        _dib().dibujar_capas(figura, escena.resultado)
        FigureCanvasAgg(figura).draw()
        render = figura.canvas.get_renderer()
        cajas = [ax.title.get_window_extent(render) for ax in figura.axes[:3]]
        ejes = [ax.get_window_extent(render) for ax in figura.axes[:3]]
        assert cajas[0].x0 >= 0 and cajas[2].x1 <= figura.bbox.width, (ancho_pulgadas, cajas[0].x0, cajas[2].x1, figura.bbox.width)
        for a, b in zip(cajas, cajas[1:]):
            assert a.x1 <= b.x0, f"un titulo invade el de su vecina: {a.x1:.0f} > {b.x0:.0f}"
        assert all(caja.width <= eje.width * 1.05 for caja, eje in zip(cajas, ejes)), "cada titulo cabe sobre su eje"


# ===================================================================================================== la API y lo que ya no esta

class TestLaApiYLoQueYaNoEsta:
    def test_capa_acondicionada_devuelve_una_capa_en_unidades_congelada_con_sus_seis_campos(self, ml0):
        d = _dib()
        assert dataclasses.is_dataclass(d.CapaEnUnidades) and d.CapaEnUnidades.__dataclass_params__.frozen
        assert [f.name for f in dataclasses.fields(d.CapaEnUnidades)] == ["valores", "tope", "unidad", "texto", "meseta", "motivo"]
        c = d.capa_acondicionada(ml0, "G")
        assert isinstance(c, d.CapaEnUnidades)
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.tope = 1.0
        assert list(inspect.signature(d.capa_acondicionada).parameters) == ["resultado", "capa"]

    def test_dibujar_capas_conserva_su_firma_y_la_ventana_solo_la_llama_con_la_figura_y_el_resultado(self):
        d = _dib()
        assert list(inspect.signature(d.dibujar_capas).parameters) == ["figura", "resultado"]
        ventana = (RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "placa_mensual.py").read_text(encoding="utf-8")
        assert ventana.count("dibujar_capas(") == 1 and "dibujo.dibujar_capas(self._fig_capas, resultado)" in ventana, "la ventana no cambia: CD.7 le agrega una rama al dibujo, no otra funcion"

    def test_las_seis_constantes_de_la_escala_son_del_dibujo_y_no_parametros_del_analisis(self):
        d, pm = _dib(), _pm()
        assert (d.FACTOR_DEL_TOPE, d.PERCENTIL_DEL_TOPE, d.TOPE_EN_NIVELES, d.TOPE_SIN_SENAL, d.RECORTADA_POR_EL_ESCANER, d.ANCHO_DEL_TITULO_DE_LA_CAPA) == (FACTOR, PERCENTIL, TOPE_EN_NIVELES, TOPE_SIN_SENAL,
                                                                                                                                                               RECORTADA, ANCHO_DEL_TITULO)
        nombres = {"factor_del_tope", "percentil_del_tope", "tope_en_niveles", "tope_sin_senal", "ancho_del_titulo_de_la_capa", "recortada_por_el_escaner"}
        assert not nombres & set(pm.VALORES_DE_LA_GEOMETRIA) and not nombres & set(d.TRAZO_DE_PARAMETRO), "CD1-D7: no viajan con lo guardado ni se dibujan como parametros del analisis"
        # CD.6 (31-10): el 42 es `diferencia_virgen_maxima_pct` (`PARAMETROS_DE_LA_DOSIS`): no entra en ninguna medida y su entrada en el dibujo la pone CD.7 (H-CD6-6), que vuelve a dejar esta igualdad sin la resta.
        assert set(d.TRAZO_DE_PARAMETRO) == set(pm.VALORES_DE_LA_GEOMETRIA) - set(pm.PARAMETROS_DE_LA_DOSIS), "compuerta: el dibujo sigue diciendo donde se ve cada parametro del analisis"

    def test_el_dibujo_ya_no_normaliza_ninguna_capa(self):
        """La causa: `capa_acondicionada` normalizaba con `motor.normalizar`. Ninguna funcion del modulo de dibujo la llama ya, y su docstring no la nombra."""
        arbol = ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))
        llamadas = [n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "normalizar"]
        assert llamadas == [], f"el dibujo llama a una normalizacion en las lineas {llamadas}"
        assert "motor.normalizar" not in (ast.get_docstring(arbol) or "")

    def test_las_funciones_que_importan_matplotlib_siguen_siendo_solo_colorear_y_dibujar_capas(self):
        """`capa_acondicionada` es pura (sin matplotlib): el docstring del modulo sigue diciendo cuales son."""
        arbol = ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))
        funciones = {f.name: f for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef)}
        with_matplotlib = {nombre for nombre, f in funciones.items() if any(isinstance(n, (ast.Import, ast.ImportFrom)) and "matplotlib" in (getattr(n, "module", None) or ",".join(a.name for a in n.names))
                                                                         for n in ast.walk(f))}
        assert "capa_acondicionada" in funciones and "capa_acondicionada" not in with_matplotlib
        assert {"colorear", "dibujar_capas"} <= with_matplotlib


# ===================================================================================================== (e) la ventana real

class TestLaVentana:
    def _comprobar(self, v, r):
        """La pestaña 2 de la ventana es la regla aplicada a su resultado: unidad y limites de cada barra, titulo y lo pintado."""
        figura = v._fig_capas
        assert len(figura.axes) == 6
        esps = {capa: esperado(r, capa) for capa in CAPAS}
        esc = escala_comun_esperada(r, esps)                 # CD.1b (motivo del cambio, clase b): la ventana pinta con la escala COMUN de las tres capas y no con el tope propio de cada una
        for k, capa in enumerate(CAPAS):
            esp = esps[capa]
            tope = tope_comun_esperado(esc, esp)
            barra = figura.axes[3 + k]
            assert barra.get_xlabel() == esp.unidad and tuple(float(x) for x in barra.get_xlim()) == (0.0, pytest.approx(tope, rel=1e-9)), (capa, barra.get_xlabel(), barra.get_xlim())
            assert figura.axes[k].get_title() == titulo_esperado(capa, texto_comun_esperado(esc, esp)), capa
            assert np.array_equal(pintado(figura, k), jet(esp.valores / np.float32(tope))), capa
        assert v.nota_pestana2.text() == "", "CD1-D10: la ventana no agrega nota a la pestaña 2"

    def test_la_ventana_pinta_la_pestana_de_las_capas_en_la_netod_absoluta_del_analisis(self, fabrica, dialogos, archivo_placa, clics):
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        r = v._resultado
        assert r.base == BASE_OD
        self._comprobar(v, r)
        assert v._fig_capas.axes[4].get_xlabel() == UNIDAD_OD

    def test_un_analisis_en_valor_de_pixel_se_pinta_en_niveles_de_0_a_255(self, fabrica, dialogos, archivo_placa, clics, monkeypatch):
        monkeypatch.setitem(_pm().VALORES_DE_LA_GEOMETRIA, "base_de_la_medida", BASE_VP)
        v = fabrica()
        analizada(v, dialogos, archivo_placa, clics)
        r = v._resultado
        assert r.base == BASE_VP
        self._comprobar(v, r)
        assert all(v._fig_capas.axes[3 + k].get_xlabel() == UNIDAD_VP and tuple(v._fig_capas.axes[3 + k].get_xlim()) == (0.0, 255.0) for k in range(3))
