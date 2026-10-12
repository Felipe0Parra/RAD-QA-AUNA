"""A.2 (PLAN_ANALISIS_PELICULAS_08-10.md): EL PISO -- una sola funcion, blindada contra el vacio, el giro y la tinta, que dice de donde salio.

CAUSA (R7, H4). El piso es el nivel de la pelicula FUERA del campo; el 50 % del borde de radiacion es el 50 % entre el piso y la meseta. El cuaderno del fisico
toma UN pixel en `[filas - 16, columnas - 16]` (en una pagina completa es el FONDO BLANCO del escaner, 255: +15 / +17 mm de FWHM; con un giro de 0.55 grados o mas
cae en el negro del giro) y la app original toma el minimo del perfil a todo lo ancho (en una pagina, el fondo). Ninguno dice de donde salio, y la pelicula de fuera del
campo no es virgen: recibe dosis periferica y se aclara con la distancia, de modo que el FWHM depende de DONDE se tome el piso (R7, H18).

LO QUE SE GARANTIZA (a-g del PROTOCOLO del plan), cada cosa con su prueba, contra una verdad que NO sale de la funcion:
  (a) NUNCA EL VACIO. ML0 (el recorte) y EPSON027 (la pagina de la que sale) dan el mismo piso por capa (+-2 niveles); en la pagina el pixel del cuaderno vale 255.
  (b) NUNCA EL GIRO. La pelicula sintetica de PF.0 girada 1, 0.9, 0.4 o -3 grados, en recorte a ras o en una pagina descentrada, da el piso que predice el generador
      (+-1 nivel) y el mismo piso que sin giro; y una pelicula girada por el propio programa (con el relleno negro del giro marcado como "sin dato") da el mismo.
  (c) NUNCA LA TINTA. Texto y diagonales pintados EN la region del piso, y una tinta que oscurece UNA sola capa (la roja, la verde o la azul, en la region y en el sexto clic),
      dan el piso verdadero (+-1 nivel); el polvo claro, un halo claro del borde de la pelicula y una etiqueta clara lejos de ella tampoco lo mueven.
  (d) SIN MARGEN, NUNCA UN NUMERO. Una pelicula que no sobresale lo bastante del campo (o con muy pocos pixeles) dice "no medible: no hay pelicula suficiente fuera del campo".
  (e) COHERENCIA. Una capa cuyo piso no es mas claro que la meseta en al menos 10 niveles es "no medible"; las demas siguen. La meseta aparta 5 mm de los lados del campo.
  (f) EL SEXTO CLIC. Sobre pelicula: su mediana; sobre el fondo: "no medible: el punto no esta sobre pelicula".
  (g) DICE DE DONDE SALIO. El piso trae la region usada y su distancia al campo luminoso (comprobada con una distancia calculada de otro modo) y en ML0 coincide
      con la franja mas lejana que midio la revision (logs/REV_09-10/piso_franjas.log). Y `como_dict()`, que viaja con el analisis, dice campo por campo lo que dice el piso.
Y las garantias de estructura: los parametros viven con nombre, unidad y motivo; la escala es la del procedimiento (nadie divide 25.4 aqui); el motor de braqui no usa
el piso; ni Qt ni base de datos; sin simbolos de correcto o incorrecto (DA-18).

La verdad: las peliculas sinteticas de PF.0 (`tests/_placa_mensual_sintetica.py`, generador INDEPENDIENTE del motor: la respuesta de la pelicula sin ruido en cada pixel
es `virgen - (virgen - meseta) * g(D)` con `D` el mapa de dosis) y un ORACULO escrito aqui con otros algoritmos (poligonos rasterizados y `cv2.distanceTransform`, no
las distancias analiticas de la funcion). Las peliculas reales saltan (HI-0) si `ImagenesDeReferencia/PlacasHistoricas` no existe y la regla de PR.0 hace fallar nombrandola
si existe y falta una.

Rojo contra HEAD (35a4b43): HEAD no tiene `piso_de_pelicula`, asi que todas las pruebas caen con su error (el archivo se colecciona: cada prueba importa el modulo
por dentro). El rojo SUSTANTIVO (que las pruebas discriminan) esta en `a2_mutaciones.py rojo` del anexo: el piso de hoy del cuaderno (UN pixel en [filas - 16, columnas - 16]) puesto en lugar de la funcion hace caer
(a), (b), (c), (d) y (g) por su aserción. Ver logs/A2/rojo.log y a2_mutaciones.py (cada mutacion, atrapada por su razon).

REVISION ESCEPTICA DE LA RONDA 1 (12-10, correccion en logs/A2/correccion_ronda1/): tres huecos de ESTA prueba, no de la funcion (que estaba bien). A2-R1-01: la tinta solo
oscurecia el rojo, asi que tres variantes del barrido sin el azul o sin el verde pasaban las 124 pruebas (RV1 a RV3 de a2_mutaciones.py); ahora se prueba cada capa, en la region y en
el sexto clic. A2-R1-03: `como_dict()` no tenia fijado ningun campo (el cruce de la distancia minima y la maxima pasaba: RV5 a RV16), y la meseta de la regla (5) no apartaba nada que
una prueba notara (RV17 y RV18, porque en un campo de 100 mm la mediana absorbe el anillo de la penumbra); ahora hay una prueba por cada forma de terminar de `como_dict()` y una de la
meseta con un campo de 25.4 mm.

A2-R1-02 (12-10, DECISION DE DISENO DE OPUS, VETABLE POR EL FISICO; logs/A2/decision_r1_02/ y borradores/A2/decision_A2-R1-02_Opus.md): «nunca el vacio» dependia SOLO de que el fondo del escaner
llegara a `umbral_fondo` = 235 en las tres capas; con el fondo por debajo (otro escaner, vidrio sucio, tapa abierta) el fondo contaba como pelicula, la region «mas lejana del campo» era el fondo y la
funcion daba «ok» con el vacio como piso, a unos 20 mm del campo, SIN aviso. Se resolvio con una regla (7) en `_piso_resultado` (opcion D', guarda por FRACCION de pixeles): sobre los pixeles finales de la
region (despues de la tinta), si el `fraccion_como_fondo` (10 %) o mas de ellos llega a `umbral_como_fondo` (170 niveles) hasta en su capa mas oscura, TODO el piso es «no medible: el piso es tan claro
como el fondo del escaner, no como pelicula (...)». Sus pruebas: (a) la pagina con el fondo en 232, 200 y 175, el recorte suelto con fondo 200 (el vacio es MINORIA: 47 % y 25 %; la guarda por mediana lo
dejaba pasar), el borde (170 se rechaza, 169 es el limite declarado que pasa) y las peliculas claras que no se rechazan; (f) el sexto clic sobre el fondo gris; (k) los dos parametros; (d) el texto; (i)
`como_dict()` en esta septima forma de terminar; (l) las diez reales no pierden nada; (m) el 170 solo vive en su diccionario. Cada una lleva su control (con `umbral_como_fondo=1000` la funcion da «ok» con
el vacio) y su mutacion en a2_mutaciones.py (RV19 a RV32).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import importlib
import io
import json
import tracemalloc
from pathlib import Path

import cv2
import numpy as np
import pytest
import tifffile

import _corpus
import _placa_mensual_sintetica as gen
from analisisImagenes import posicion_inicial_braqui as motor

RAIZ = Path(__file__).resolve().parent.parent
ESC = 25.4 / 600.0                                    # mm por pixel: la escala del procedimiento (600 dpi)
CAPAS_DEL_PISO = ("R", "G", "B", "gris")
NOMBRES = {"R": "rojo", "G": "verde", "B": "azul", "gris": "gris"}
# Los parametros del plan (A.2, OBJETIVO), escritos AQUI a proposito: la prueba fija los valores, no los importa. `lado_punto_manual_mm` es el "3 x 3 mm" de la regla (6); `umbral_como_fondo` y
# `fraccion_como_fondo` son los de la regla (7) (A2-R1-02, decision D' de Opus): 170 niveles es la mitad de la brecha entre la capa mas oscura del piso de las diez reales (73 a 86) y el fondo (255),
# y el 10 % es 17 veces lo peor que miden las reales (0.6 %) y menos de lo que mueve la mediana (desde el 19 % la sube 1 a 3 niveles).
PLAN = {"umbral_fondo": 235.0, "margen_borde_mm": 0.5, "margen_campo_mm": 5.0, "fraccion_lejana": 0.20, "delta_tinta": 25.0, "pixeles_minimos": 2000,
        "contraste_minimo": 10.0, "lado_punto_manual_mm": 3.0, "umbral_como_fondo": 170.0, "fraccion_como_fondo": 0.10}
# El texto de la regla (7), escrito AQUI tal cual (la prueba fija el texto, no lo importa): el motivo es una constante del modulo y el estado completo lleva, entre parentesis, el porcentaje de pixeles
# del piso que parecen fondo y el umbral, y dice que revisar.
MOTIVO_COMO_EL_FONDO = "no medible: el piso es tan claro como el fondo del escáner, no como película"
QUE_REVISAR = "revise la tapa y el vidrio del escáner y que el escaneo no lleve ajustes de brillo"


def motivo_completo(porcentaje, umbral=170):
    """El `estado` de un piso rechazado por la regla (7), escrito desde el plan: «<motivo> (el N % de sus píxeles llega a U niveles hasta en su capa más oscura): <que revisar>»."""
    return f"{MOTIVO_COMO_EL_FONDO} (el {porcentaje} % de sus píxeles llega a {umbral} niveles hasta en su capa más oscura): {QUE_REVISAR}"

# Los clics del campo luminoso de las 10 peliculas mensuales reales (UL, UR, DR, DL), los que pondria el fisico: ML0 son los del cuaderno; EPSON027 son los de ML0 mas el
# desplazamiento exacto (10, 7) de ML0 dentro de la pagina (medido a resolucion completa, logs/A2/offset_ml0.log); las demas, marcas localizadas con
# scripts/med_mensual_marcas.py y llevadas entre archivos de la misma pelicula (scripts/med_mensual_reales.py). EPSON029: la esquina UL esta ESTIMADA (marca ausente).
CLICS_REALES = {
    "ML0": ((196, 143), (2542, 147), (2526, 2501), (171, 2480)),
    "EPSON027": ((206, 150), (2552, 154), (2536, 2508), (181, 2487)),
    "EPSON007": ((207, 173), (2516, 153), (2553, 2507), (232, 2525)),
    "EPSON008_TIF": ((206, 189), (2517, 169), (2553, 2525), (230, 2542)),
    "EPSON030": ((166, 174), (2475, 158), (2507, 2512), (187, 2526)),
    "EPSON001_JPG": ((178, 255), (2541, 252), (2553, 2593), (203, 2608)),
    "EPSON001_TIF": ((178, 255), (2541, 252), (2553, 2593), (203, 2608)),
    "PLACA_REF40": ((104, 182), (2444, 149), (2496, 2493), (125, 2506)),
    "EPSON028": ((111, 200), (2452, 175), (2496, 2520), (124, 2525)),
    "EPSON029": ((215, 151), (2526, 195), (2494, 2542), (183, 2498)),
}
# La franja mas lejana del lado de abajo de ML0 que midio la revision (logs/REV_09-10/piso_franjas.log): 8-9 mm del campo luminoso, mediana B/G/R.
FRANJA_MAS_LEJANA_ML0_BGR = (87, 172, 97)
PAGINAS = {"EPSON027", "EPSON028", "EPSON029", "EPSON030"}      # 6600 x 5100: con sus cuatro planos en flotante pesan 700 MB; no se guardan en la cache


def _pel():
    """El modulo, importado POR PRUEBA: en HEAD (sin `piso_de_pelicula`) el archivo se coleciona y cada prueba cae con su error."""
    return importlib.import_module("analisisImagenes.pelicula")


def _P(**cambios):
    """Lo que un llamador real pasa: el `PARAMETROS` del motor (trae la escala del procedimiento) y, si quiere, sus cambios. Los del piso salen de los de fabrica."""
    return {**motor.PARAMETROS, **cambios}


def piso(pelicula, campo, P=None, punto=None):
    return _pel().piso_de_pelicula(pelicula, campo, _P() if P is None else P, punto)


_CACHE = {}


def _cacheado(clave, fabrica):
    """Un objeto caro compartido por las pruebas del modulo. Nada de lo que se guarda aqui se modifica nunca (las pruebas que pintan copian primero)."""
    if clave not in _CACHE:
        _CACHE[clave] = fabrica()
    return _CACHE[clave]


# ====================================================================================================================== las peliculas

def _real(clave):
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"HI-0: no existe {_corpus.PELICULAS_RAIZ} (o {clave})")
    if clave in PAGINAS:
        return _pel().leer_pelicula(Path(ruta).read_bytes())
    return _cacheado(("real", clave), lambda: _pel().leer_pelicula(Path(ruta).read_bytes()))


def _datos_de_tiff_sin_resolucion(imagen_bgr):
    sal = io.BytesIO()
    tifffile.imwrite(sal, np.ascontiguousarray(imagen_bgr[:, :, ::-1]), photometric="rgb", compression=None)
    return sal.getvalue()


class Sint:
    """Una pelicula sintetica de PF.0 lista: el arreglo, la verdad, la `Pelicula` leida (TIFF sin compresion, 600 dpi declarados) y las 4 esquinas del campo luminoso."""

    def __init__(self, variante, theta, bits=8, **kw):
        self.kw = dict(kw)
        self._oraculo = None
        self.img, self.verdad = gen.generar_arreglo(variante=variante, theta_deg=theta, bits=bits, dpi=600, **kw)
        self.pelicula = _pel().leer_pelicula(gen.codificar(self.img, "tiff", 600))
        m = self.verdad.marcas_px
        self.campo = [m["UL"], m["UR"], m["DR"], m["DL"]]

    @property
    def forma(self):
        return self.img.shape[:2]

    @property
    def oraculo(self):
        if self._oraculo is None:
            self._oraculo = Oraculo(self)
        return self._oraculo


_SE_GUARDAN = {("B", 0.4, 8, ()), ("B", 0.0, 8, ())}        # las dos que casi todas las pruebas usan; el resto se genera y se suelta (cada pagina sintetica pesa 250 MB con sus planos)


def _sint(variante, theta, bits=8, **kw):
    clave = (variante, theta, bits, tuple(sorted(kw.items())))
    if clave in _SE_GUARDAN:
        return _cacheado(("sint",) + clave, lambda: Sint(variante, theta, bits, **kw))
    return Sint(variante, theta, bits, **kw)


def _a_pelicula(imagen, dpi=600):
    return _pel().leer_pelicula(gen.codificar(imagen, "tiff", dpi))


_SE_GUARDAN_CON_FONDO = {("B", 0.4, 200.0), ("L", 0.4, 200.0)}      # las dos que varias pruebas de la regla (7) usan; el resto se genera y se suelta (una pagina pesa 250 MB con sus planos)


def _con_fondo(variante, theta, fondo):
    """La sintetica de PF.0 con el blanco del escaner en `fondo` niveles (de fabrica, 250): otro escaner, un vidrio sucio o la tapa abierta (A2-R1-02). Solo cambia el fondo: la pelicula, el
    ruido (misma semilla) y las marcas son los de la sintetica de siempre. Nada de lo que se guarda aqui se modifica nunca."""
    clave = (variante, float(theta), float(fondo))
    def fabrica():
        return Sint(variante, theta, calib={**gen.CALIB, "fondo_escaner": float(fondo)})
    return _cacheado(("con_fondo",) + clave, fabrica) if clave in _SE_GUARDAN_CON_FONDO else fabrica()


def _sin_la_regla(pelicula, campo, punto=None):
    """El piso con la regla (7) APAGADA (`umbral_como_fondo` = 1000: ningun pixel lo alcanza): lo que la funcion daba antes de A2-R1-02. Es el CONTROL de cada prueba de la regla: demuestra que, sin
    ella, el piso de un fondo gris es «ok» con el vacio."""
    return piso(pelicula, campo, _P(umbral_como_fondo=1000.0), punto)


def _fraccion_como_fondo(p, pelicula, umbral=170.0):
    """De los pixeles de la region de un `Piso`, la fraccion cuya capa mas oscura (el minimo de R, G y B) llega a `umbral`. Se recalcula AQUI desde la mascara de la region con numpy, no con la
    funcion que se prueba."""
    x0, y0, x1, y1 = p.region.caja
    minimo = np.minimum(np.minimum(pelicula.R[y0:y1, x0:x1], pelicula.G[y0:y1, x0:x1]), pelicula.B[y0:y1, x0:x1])
    return float(np.mean(minimo[p.region.mascara] >= umbral))


# ====================================================================================================================== el oraculo (otros algoritmos)

def _poligono(forma, puntos):
    m = np.zeros(forma, np.uint8)
    cv2.fillConvexPoly(m, np.rint(np.asarray(puntos, np.float64)).astype(np.int32), 1)
    return m.astype(bool)


def _distancia_al_campo_mm(forma, campo):
    """Distancia (mm) de cada pixel al campo luminoso, por rasterizacion + transformada de distancia (NO las distancias analiticas de la funcion)."""
    dentro = _poligono(forma, campo)
    return cv2.distanceTransform((~dentro).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * np.float32(ESC)


def _crudo_sin_ruido(D, capa):
    """La respuesta de la pelicula en esa capa SIN ruido: `virgen - (virgen - meseta) * g(D)` (el generador de PF.0; `_g` es privada y se usa a proposito)."""
    c = gen.CALIB
    i = gen.INDICE_CAPA[capa]
    virgen, meseta, k = c["virgen_bgr"][i], c["meseta_bgr"][i], c["k_bgr"][i]
    return virgen - (virgen - meseta) * gen._g(D, k)


class Oraculo:
    """La verdad de una sintetica: la pelicula (poligono conocido; lo de fuera de la imagen cuenta como pelicula, porque sigue), su erosion de 0.5 mm, la distancia al campo
    luminoso, la region del piso (el 20 % mas lejano de lo que esta a mas de 5 mm) y, por capa, la mediana de la respuesta sin ruido en esa region."""

    def __init__(self, s):
        v = s.verdad
        alto, ancho = s.forma
        D, _ = gen.mapa_dosis(v.variante, v.giro_deg, 600, s.kw.get("desplazamiento_px"), s.kw.get("beta", 0.0), s.kw.get("cupula_pct_40mm", 0.0))
        self.D = D.astype(np.float32)
        del D
        pad = 200
        esq = v.esquinas_pelicula_px
        lienzo = np.zeros((alto + 2 * pad, ancho + 2 * pad), np.uint8)
        cv2.fillConvexPoly(lienzo, np.rint(np.array([esq["UL"], esq["UR"], esq["DR"], esq["DL"]]) + pad).astype(np.int32), 1)
        lienzo[:pad] = 1
        lienzo[-pad:] = 1
        lienzo[:, :pad] = 1
        lienzo[:, -pad:] = 1                                     # fuera de la imagen la pelicula sigue: el borde de la imagen no es un borde de pelicula
        self.borde_mm = cv2.distanceTransform(lienzo, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[pad:pad + alto, pad:pad + ancho] * np.float32(ESC)
        self.pelicula = self.borde_mm > 0
        self.dcam = _distancia_al_campo_mm(s.forma, s.campo)
        self.elegibles = (self.borde_mm > 0.5) & (self.dcam > 5.0)
        self.umbral_distancia = float(np.quantile(self.dcam[self.elegibles], 0.8))
        self.region = self.elegibles & (self.dcam >= self.umbral_distancia)

    def crudo(self, capa, mascara):
        """La respuesta sin ruido de esa capa en los pixeles de `mascara` (las del tamano de la imagen)."""
        return _crudo_sin_ruido(self.D[mascara].astype(np.float64), capa)

    def piso(self, excluir=None):
        region = self.region if excluir is None else self.region & ~excluir
        return {c: float(np.median(self.crudo(c, region))) for c in "BGR"}


def _region_completa(p, forma):
    """La region que reporta la funcion, como mascara del tamano de la imagen."""
    x0, y0, x1, y1 = p.region.caja
    m = np.zeros(forma, bool)
    m[y0:y1, x0:x1] = p.region.mascara
    return m


def _jaccard(a, b):
    return float((a & b).sum()) / float((a | b).sum())


def _medianas(p):
    return {c: p.capas[c].mediana for c in CAPAS_DEL_PISO}


def _dict_esperado(p):
    """Lo que `como_dict()` tiene que decir de un `Piso`, escrito campo por campo desde sus atributos publicos: la lista de claves y su forma (listas y no tuplas, floats y no numpy:
    viaja como JSON) es el contrato del diccionario, y esta aqui y no en la funcion que se prueba."""
    r = p.region
    region = None if r is None else {"origen": r.origen, "caja": [int(v) for v in r.caja], "n": int(r.n), "distancia_media_mm": float(r.distancia_media_mm),
                                     "distancia_minima_mm": float(r.distancia_minima_mm), "distancia_maxima_mm": float(r.distancia_maxima_mm)}
    return {"estado": p.estado, "origen": p.origen, "escala_mm": p.escala_mm, "campo_luz": [[float(x), float(y)] for x, y in p.campo_luz], "parametros": dict(p.parametros),
            "capas": {c: {"estado": k.estado, "mediana": k.mediana, "n": int(k.n), "iqr": k.iqr, "meseta": k.meseta, "contraste": k.contraste} for c, k in p.capas.items()},
            "region": region}


def _pintar_texto_y_diagonales(imagen, region, color):
    """Pinta texto y dos diagonales EN la region del piso (el rotulo «IX 14-09-2026» y las diagonales de EPSON028): devuelve el arreglo pintado y la mascara de lo pintado."""
    out = imagen.copy()
    ys, xs = np.nonzero(region)
    ymed = int(np.median(ys))
    xmin, xmax = int(np.percentile(xs, 30)), int(np.percentile(xs, 70))
    cv2.putText(out, "IX 14-09-2026", (xmin, ymed + 30), cv2.FONT_HERSHEY_SIMPLEX, 2.2, color, 9)
    cv2.line(out, (xmin, ymed + 60), (xmin + 700, ymed - 20), color, 8)
    cv2.line(out, (xmax - 700, ymed - 20), (xmax, ymed + 60), color, 8)
    return out, (out != imagen).any(axis=2)


# ====================================================================================================================== los parametros

class TestLosParametrosVivenConNombreUnidadYMotivo:
    def test_k_los_parametros_son_los_del_plan_con_nombre_unidad_y_motivo(self):
        pel = _pel()
        assert set(pel.PARAMETROS_DEL_PISO) == set(PLAN), "el diccionario de parametros no tiene exactamente los del plan (mas el lado del sexto clic)"
        for nombre, esperado in PLAN.items():
            p = pel.PARAMETROS_DEL_PISO[nombre]
            assert p["valor"] == esperado, f"{nombre}: {p['valor']} en vez de {esperado}"
            assert p["unidad"].strip() and p["motivo"].strip() and len(p["motivo"]) > 20, f"{nombre} no trae unidad y motivo"
            assert pel.VALORES_DEL_PISO[nombre] == esperado
        assert set(pel.VALORES_DEL_PISO) == set(PLAN)

    def test_k_los_valores_de_fabrica_son_los_que_usa_la_funcion_y_los_que_registra(self):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        assert {k: p.parametros[k] for k in PLAN} == PLAN, "la funcion no uso (o no registro) los valores del plan"

    @pytest.mark.parametrize("nombre,valor,efecto", [
        ("pixeles_minimos", 10 ** 7, "sin_pixeles"),               # pide mas pixeles de los que hay: no medible
        ("pixeles_minimos", 150000, "sin_pixeles"),                # mas de los 124 mil de la region y menos de los 4 millones de la meseta: solo la region lo nota
        ("contraste_minimo", 10 ** 4, "sin_contraste"),            # exige un contraste imposible: ninguna capa
        ("margen_campo_mm", 200.0, "sin_pixeles"),                 # la region empieza a 200 mm del campo: no hay
        ("fraccion_lejana", 1.0, "mas_cerca"),                     # toda la pelicula de fuera: mas pixeles y mas cerca
        ("umbral_como_fondo", 60.0, "como_el_fondo"),              # la capa mas oscura del piso (81-88) ya llega a 60: la pelicula misma "parece fondo" y la regla (7) la rechaza
    ])
    def test_k_cada_parametro_de_P_se_usa(self, nombre, valor, efecto):
        s = _sint("B", 0.4)
        base = piso(s.pelicula, s.campo)
        cambiado = piso(s.pelicula, s.campo, _P(**{nombre: valor}))
        assert cambiado.parametros[nombre] == valor
        if efecto == "sin_pixeles":
            assert cambiado.estado.startswith("no medible") and cambiado.region is None
        elif efecto == "sin_contraste":
            assert cambiado.estado == "ok" and all(c.estado.startswith("no medible") and c.mediana is None for c in cambiado.capas.values())
        elif efecto == "como_el_fondo":
            assert base.estado == "ok", "la pelicula de fabrica tiene que medirse para que el cambio del umbral se note"
            assert cambiado.estado.startswith(MOTIVO_COMO_EL_FONDO) and cambiado.region is None and all(c.mediana is None for c in cambiado.capas.values())
        else:
            assert cambiado.region.n > 3 * base.region.n and cambiado.region.distancia_media_mm < base.region.distancia_media_mm - 1.0

    def test_k_fraccion_como_fondo_se_usa(self):
        """El recorte suelto con el fondo en 200 y 0.4 grados: el 24.9 % de los pixeles del piso es vacio (las cunas de las esquinas). Con `fraccion_como_fondo` = 0.24 la regla (7) lo rechaza y con
        0.25 lo mide (con el sesgo de +1 nivel que la regla de fabrica, 0.10, no deja pasar): el parametro decide, no un 0.10 escrito en la funcion."""
        s = _con_fondo("L", 0.4, 200)
        f = _fraccion_como_fondo(_sin_la_regla(s.pelicula, s.campo), s.pelicula)
        assert 0.24 < f < 0.25, f"{f:.4f} del piso es vacio: los dos valores de la prueba ya no quedan a cada lado"
        rechaza = piso(s.pelicula, s.campo, _P(fraccion_como_fondo=0.24))
        mide = piso(s.pelicula, s.campo, _P(fraccion_como_fondo=0.25))
        assert rechaza.estado.startswith(MOTIVO_COMO_EL_FONDO) and rechaza.region is None and rechaza.parametros["fraccion_como_fondo"] == 0.24
        assert mide.estado == "ok" and mide.region is not None and mide.parametros["fraccion_como_fondo"] == 0.25

    def test_k_delta_tinta_se_usa(self):
        s = _sint("B", 0.4)
        pintada, mascara = _pintar_texto_y_diagonales(s.img, s.oraculo.region, (30, 35, 25))
        pel = _a_pelicula(pintada)
        con_regla = piso(pel, s.campo)
        sin_regla = piso(pel, s.campo, _P(delta_tinta=1000.0))
        assert not (_region_completa(con_regla, s.forma) & mascara).any()
        assert (_region_completa(sin_regla, s.forma) & mascara).sum() > 2000, "con delta_tinta enorme la tinta tendria que quedarse"
        assert sin_regla.parametros["delta_tinta"] == 1000.0 and con_regla.parametros["delta_tinta"] == 25.0

    def test_k_el_margen_del_borde_y_el_umbral_del_fondo_se_usan(self):
        s = _sint("B", 0.4)
        base = piso(s.pelicula, s.campo)
        sin_erosion = piso(s.pelicula, s.campo, _P(margen_borde_mm=0.0))
        mas_erosion = piso(s.pelicula, s.campo, _P(margen_borde_mm=3.0))
        assert sin_erosion.region.distancia_maxima_mm > base.region.distancia_maxima_mm + 0.3
        assert base.region.distancia_maxima_mm > mas_erosion.region.distancia_maxima_mm + 0.3
        # un umbral de fondo bajo (60) deja todo como fondo: no hay pelicula; uno alto (256) deja el fondo como pelicula
        sin_pelicula = piso(s.pelicula, s.campo, _P(umbral_fondo=60.0))
        assert sin_pelicula.estado.startswith("no medible") and sin_pelicula.region is None
        con_fondo = piso(s.pelicula, s.campo, _P(umbral_fondo=256.0))
        assert con_fondo.region is None or con_fondo.region.n != base.region.n

    def test_k_el_margen_del_campo_mueve_la_region(self):
        """Con 7.5 mm en lugar de 5, solo cuenta la pelicula a mas de 7.5 mm del campo: la region se achica (medido: 124 160 -> 40 281 pixeles) y se aleja (la distancia minima
        pasa de 8.2 a 9.4 mm). La meseta de referencia no lo nota: por eso el margen se prueba aqui, en la region."""
        s = _sint("B", 0.4)
        base = piso(s.pelicula, s.campo)
        lejos = piso(s.pelicula, s.campo, _P(margen_campo_mm=7.5))
        assert lejos.estado == "ok" and lejos.parametros["margen_campo_mm"] == 7.5
        assert lejos.region.n < 0.5 * base.region.n and lejos.region.distancia_minima_mm > base.region.distancia_minima_mm + 0.8, (base.region, lejos.region)
        assert lejos.region.distancia_minima_mm > 9.0

    def test_k_el_margen_del_borde_se_usa_tambien_en_el_sexto_clic(self):
        s = TestElSextoClic._con_un_trozo_sin_irradiar()
        pegado, pel = s
        con_erosion = piso(pel, pegado.campo, punto=(2951.0, 120.0))
        sin_erosion = piso(pel, pegado.campo, _P(margen_borde_mm=0.0), punto=(2951.0, 120.0))
        assert con_erosion.estado == _pel().MOTIVO_POCA_PELICULA_EN_EL_PUNTO
        assert sin_erosion.estado == "ok" and sin_erosion.region.n > 2000

    def test_k_el_lado_del_sexto_clic_se_usa(self):
        s = _sint("B", 0.4)
        o = s.oraculo
        cand = o.pelicula & (o.borde_mm >= 4.5) & (o.dcam > 5.5)
        k = int(np.argmax(np.where(cand, o.dcam, -1.0)))
        punto = (float(k % s.forma[1]), float(k // s.forma[1]))
        chico, grande = piso(s.pelicula, s.campo, punto=punto), piso(s.pelicula, s.campo, _P(lado_punto_manual_mm=6.0), punto=punto)
        assert chico.estado == grande.estado == "ok"
        assert abs(grande.region.n / chico.region.n - 4.0) < 0.3, (chico.region.n, grande.region.n)

    def test_k_un_P_sin_las_claves_del_piso_usa_las_de_fabrica_y_uno_sin_la_escala_se_rechaza(self):
        s = _sint("B", 0.4)
        solo_escala = {k: motor.PARAMETROS[k] for k in ("resolucion_escaneo_dpi", "resoluciones_de_editor_dpi", "tolerancia_dpi_relativa")}
        assert piso(s.pelicula, s.campo, solo_escala).estado == "ok"
        with pytest.raises(ValueError, match="resolucion_escaneo_dpi"):
            piso(s.pelicula, s.campo, {})


# ====================================================================================================================== (a) nunca el vacio

class TestNuncaElVacio:
    def test_a_ml0_el_recorte_y_epson027_la_pagina_dan_el_mismo_piso_por_capa(self):
        recorte, pagina = piso(_real("ML0"), CLICS_REALES["ML0"]), piso(_real("EPSON027"), CLICS_REALES["EPSON027"])
        assert recorte.estado == "ok" and pagina.estado == "ok"
        for c in CAPAS_DEL_PISO:
            assert abs(recorte.capas[c].mediana - pagina.capas[c].mediana) <= 2.0, f"{c}: recorte {recorte.capas[c].mediana} y pagina {pagina.capas[c].mediana}"
        assert abs(recorte.region.distancia_media_mm - pagina.region.distancia_media_mm) <= 0.3

    @pytest.mark.parametrize("clave", ["EPSON027", "EPSON028", "EPSON029", "EPSON030"])
    def test_a_en_una_pagina_completa_el_piso_no_es_el_fondo_blanco_del_escaner(self, clave):
        pel = _real(clave)
        alto, ancho = pel.R.shape
        assert alto > 6000 and ancho > 5000, "no es una pagina completa del escaner"
        # el "piso" del cuaderno: UN pixel en [filas - 16, columnas - 16]: en la pagina es el fondo blanco
        assert min(pel.R[alto - 16, ancho - 16], pel.G[alto - 16, ancho - 16], pel.B[alto - 16, ancho - 16]) >= 240, "el pixel del cuaderno ya no es el fondo: la prueba no discrimina"
        p = piso(pel, CLICS_REALES[clave])
        assert p.estado == "ok"
        for c in "RGB":
            assert 60 < p.capas[c].mediana < 200, f"{clave} {c}: piso {p.capas[c].mediana} (el fondo es 255)"

    def test_a_el_piso_esta_sobre_pelicula_y_no_sobre_fondo_ni_sobre_pixeles_sin_dato(self):
        pel = _real("EPSON027")
        p = piso(pel, CLICS_REALES["EPSON027"])
        x0, y0, x1, y1 = p.region.caja
        m = p.region.mascara
        minimo = np.minimum(np.minimum(pel.R[y0:y1, x0:x1], pel.G[y0:y1, x0:x1]), pel.B[y0:y1, x0:x1])
        assert int(m.sum()) == p.region.n > 50000
        assert float(minimo[m].max()) < 235.0, "la region incluye fondo del escaner"
        assert bool(pel.validos[y0:y1, x0:x1][m].all())

    def test_a_con_la_pagina_y_el_recorte_sinteticos_de_la_misma_pelicula_el_piso_es_el_mismo(self):
        pagina, recorte = _sint("B", 0.0), _sint("A", 0.0)
        a, b = piso(pagina.pelicula, pagina.campo), piso(recorte.pelicula, recorte.campo)
        assert a.estado == b.estado == "ok"
        for c in CAPAS_DEL_PISO:
            assert abs(a.capas[c].mediana - b.capas[c].mediana) <= 1.0, c


# ====================================================================================================================== (a) nunca el vacio, tampoco con otro fondo de escaner (A2-R1-02)

class TestNuncaElPisoComoElFondoDelEscaner:
    """La regla (7) (decision D' de Opus): la garantia «nunca el vacio» de la regla (1) depende de que el fondo del escaner llegue a `umbral_fondo` (235). Si el fondo queda por debajo (otro escaner, un
    vidrio sucio, la tapa abierta) el fondo cuenta como pelicula y, sin la regla (7), el piso es el vacio y la funcion dice «ok» a unos 20 mm del campo, SIN aviso. Cada prueba lleva su CONTROL
    (`_sin_la_regla`): la funcion con la regla apagada da «ok» con el vacio; lo que se afirma es lo que la regla cambia."""

    @pytest.mark.parametrize("fondo", [232, 200, 175])
    def test_a_la_pagina_con_el_fondo_del_escaner_gris_no_da_un_piso_del_vacio(self, fondo):
        s = _con_fondo("B", 0.4, fondo)
        sin_regla = _sin_la_regla(s.pelicula, s.campo)
        assert sin_regla.estado == "ok" and all(abs(sin_regla.capas[c].mediana - fondo) <= 1.0 for c in CAPAS_DEL_PISO), \
            "sin la regla el piso tendria que ser el vacio (el fondo): la prueba no discrimina"
        assert sin_regla.region.distancia_media_mm > 15.0, "el vacio de una pagina esta lejos del campo: el piso de A2-R1-02 sale a unos 20 mm"
        p = piso(s.pelicula, s.campo)
        assert p.estado.startswith(MOTIVO_COMO_EL_FONDO), p.estado
        assert p.region is None and all(c.mediana is None and c.iqr is None and c.estado == p.estado for c in p.capas.values()), "dio un numero que es el vacio"
        assert p.valor("G") is None and p.todas_medibles is False and p.descripcion() == p.estado

    @pytest.mark.parametrize("theta,vacio,sesgo_minimo", [(0.9, 0.47, 2.5), (0.4, 0.25, 0.7)])
    def test_a_el_recorte_suelto_con_fondo_gris_no_deja_pasar_el_vacio_aunque_sea_minoria(self, theta, vacio, sesgo_minimo):
        """El recorte suelto (la caja que envuelve la pelicula girada) solo trae fondo en las cunas de las esquinas: el vacio es el 25 % (0.4 grados) o el 47 % (0.9) del piso, MINORIA o casi.
        Una guarda por MEDIANA (la opcion D que Opus descarto) lo deja pasar: la mediana si se corre (+1 y +3 niveles contra la verdad del generador) y el estado sigue «ok». El fisico pidio «nunca
        el vacio», no «nunca una mayoria de vacio»."""
        s = _con_fondo("L", theta, 200)
        sin_regla = _sin_la_regla(s.pelicula, s.campo)
        assert sin_regla.estado == "ok"
        f = _fraccion_como_fondo(sin_regla, s.pelicula)
        assert abs(f - vacio) <= 0.02, f"{f:.3f} del piso es vacio y la prueba espera {vacio}: no discrimina"
        verdad = s.oraculo.piso()
        for c in "BGR":
            assert sin_regla.capas[c].mediana - verdad[c] >= sesgo_minimo, f"{c}: sin la regla el piso solo se corre {sin_regla.capas[c].mediana - verdad[c]:+.2f} niveles de la verdad {verdad[c]:.2f}"
        p = piso(s.pelicula, s.campo)
        assert p.estado.startswith(MOTIVO_COMO_EL_FONDO), f"con {100 * f:.0f} % de vacio en el piso la funcion dijo: {p.estado}"
        assert p.region is None and all(c.mediana is None for c in p.capas.values())

    def test_a_el_limite_declarado_el_fondo_en_170_se_rechaza_y_en_169_pasa_con_el_vacio(self):
        """El umbral es inclusivo (`>=`) y es el LIMITE que el plan declara: un fondo neutro por debajo de 170 se toma por pelicula (se ve en la region que dibuja E.1). Con el fondo del escaner en 170 la capa
        mas oscura de un pixel de fondo llega a 170 en el 25 % de los pixeles (ruido de 1.5 niveles) y se rechaza; en 169, en el 5 %, y pasa con el vacio como piso."""
        en_170, en_169 = _con_fondo("B", 0.4, 170), _con_fondo("B", 0.4, 169)
        f170 = _fraccion_como_fondo(_sin_la_regla(en_170.pelicula, en_170.campo), en_170.pelicula)
        f169 = _fraccion_como_fondo(_sin_la_regla(en_169.pelicula, en_169.campo), en_169.pelicula)
        assert f170 >= 0.10 > f169, f"fraccion de vacio: {f170:.4f} con el fondo en 170 y {f169:.4f} en 169; la prueba espera 0.25 y 0.05"
        rechazado = piso(en_170.pelicula, en_170.campo)
        assert rechazado.estado.startswith(MOTIVO_COMO_EL_FONDO) and rechazado.region is None, "el fondo en 170 tiene que rechazarse (el umbral es inclusivo)"
        pasa = piso(en_169.pelicula, en_169.campo)
        assert pasa.estado == "ok" and all(abs(pasa.capas[c].mediana - 169) <= 1.0 for c in CAPAS_DEL_PISO), "el limite declarado: con el fondo en 169 pasa con el vacio como piso"

    def test_a_una_pelicula_en_grises_no_se_rechaza_y_su_piso_es_el_de_siempre(self):
        s = _sint("B", 0.4)
        gris = np.rint(0.114 * s.img[:, :, 0] + 0.587 * s.img[:, :, 1] + 0.299 * s.img[:, :, 2]).astype(np.uint8)
        gris = np.where(gris >= 235, 250, gris).astype(np.uint8)                       # el fondo sigue siendo blanco
        pel = _a_pelicula(np.ascontiguousarray(np.repeat(gris[:, :, None], 3, axis=2)))
        sin_regla, con_regla = _sin_la_regla(pel, s.campo), piso(pel, s.campo)
        assert con_regla.estado == "ok" and _medianas(con_regla) == _medianas(sin_regla), "la regla (7) movio o rechazo el piso de una pelicula en grises"
        assert all(abs(con_regla.capas[c].mediana - 138.0) <= 1.5 for c in CAPAS_DEL_PISO), _medianas(con_regla)
        assert _fraccion_como_fondo(con_regla, pel) < 0.01

    @pytest.mark.parametrize("subir,se_rechaza", [(80, False), (88, True)])
    def test_a_una_pelicula_mas_clara_solo_se_rechaza_cuando_su_capa_mas_oscura_parece_fondo(self, subir, se_rechaza):
        """Una pelicula `subir` niveles mas clara (el fondo de siempre). Con 80 la capa mas oscura del piso vale 161 (por debajo de 170) aunque la media de las tres capas ya es 178: NO se rechaza y
        su piso es el mismo que sin la regla (la mutacion «la mediana de las tres capas» la rechazaria). Con 88 la capa mas oscura llega a 169 y el 40 % de sus pixeles pasa de 170: se rechaza."""
        s = _sint("B", 0.4)
        clara = s.img.astype(np.int16)
        en_pelicula = s.img.min(axis=2) < 235
        clara[en_pelicula] = np.minimum(clara[en_pelicula] + subir, 234)
        pel = _a_pelicula(clara.astype(np.uint8))
        sin_regla, con_regla = _sin_la_regla(pel, s.campo), piso(pel, s.campo)
        assert sin_regla.estado == "ok"
        f = _fraccion_como_fondo(sin_regla, pel)
        if se_rechaza:
            assert f >= 0.10, f"solo el {100 * f:.1f} % del piso llega a 170: la prueba no discrimina"
            assert con_regla.estado.startswith(MOTIVO_COMO_EL_FONDO) and con_regla.region is None
        else:
            assert f < 0.01 and sorted(sin_regla.capas[c].mediana for c in "RGB")[1] > 170, "la capa media tiene que pasar de 170 y la mas oscura no: la prueba no discrimina"
            assert con_regla.estado == "ok" and _medianas(con_regla) == _medianas(sin_regla), "se rechazo (o se movio) una pelicula clara cuya capa mas oscura no parece fondo"

    def test_a_la_regla_va_antes_de_la_meseta(self):
        """El plan fija el orden: primero que el piso no parezca el fondo, despues la comprobacion contra la meseta. Con el campo fuera de la imagen no hay meseta (sin la regla: «la pelicula no cubre el
        campo luminoso...») y la region sigue siendo el vacio de la pagina: el motivo que manda es el de la regla (7)."""
        s = _con_fondo("B", 0.4, 200)
        lejos = [(x - 3400.0, y - 3400.0) for x, y in s.campo]
        assert _sin_la_regla(s.pelicula, lejos).estado == _pel().MOTIVO_SIN_MESETA, "sin la regla el campo fuera de la imagen tendria que dar «sin meseta»: la prueba no discrimina el orden"
        assert piso(s.pelicula, lejos).estado.startswith(MOTIVO_COMO_EL_FONDO)


# ====================================================================================================================== (b) nunca el giro

class TestNuncaElGiro:
    @pytest.mark.parametrize("variante,theta,kw", [
        ("A", 0.0, {}), ("A", 1.0, {}), ("A", -3.0, {}), ("B", 0.9, {}), ("C", 0.4, {}), ("E", -3.0, {}),
        ("D", 0.0, {"beta": 0.02, "cupula_pct_40mm": -3.5}), ("L", -1.0, {})])
    def test_b_el_piso_es_el_que_predice_el_generador_con_cualquier_giro_y_encuadre(self, variante, theta, kw):
        s = _sint(variante, theta, **kw)
        o = s.oraculo
        p = piso(s.pelicula, s.campo)
        assert p.estado == "ok"
        verdad = o.piso()
        for capa in "BGR":
            assert abs(p.capas[capa].mediana - verdad[capa]) <= 1.0, f"{variante} {theta} {capa}: {p.capas[capa].mediana} contra la verdad {verdad[capa]:.2f}"
        assert _jaccard(_region_completa(p, s.forma), o.region) >= 0.93, "la region no es la que dicta la geometria conocida"

    @pytest.mark.parametrize("theta", [0.4, 0.9, 1.0, -3.0, 5.0])
    def test_b_la_misma_pelicula_en_la_pagina_da_el_mismo_piso_con_cualquier_giro(self, theta):
        sin_giro, con_giro = _sint("B", 0.0), _sint("B", theta)
        a, b = piso(sin_giro.pelicula, sin_giro.campo), piso(con_giro.pelicula, con_giro.campo)
        assert a.estado == b.estado == "ok"
        for c in CAPAS_DEL_PISO:
            assert abs(a.capas[c].mediana - b.capas[c].mediana) <= 1.0, f"{c} con giro {theta}"
        assert abs(a.region.distancia_media_mm - b.region.distancia_media_mm) <= 0.1

    def test_b_un_giro_hecho_por_el_programa_con_relleno_negro_sin_dato_da_el_mismo_piso(self):
        """La pelicula girada por el programa (C.2): el relleno negro que entra por los bordes se marca en `validos`. Sin esa marca, el relleno (lo mas lejano del campo,
        pegado a la pelicula) seria el piso."""
        s = _sint("A", 0.0)
        alto, ancho = s.forma
        M = cv2.getRotationMatrix2D((ancho / 2.0, alto / 2.0), 3.0, 1.0)
        girada = cv2.warpAffine(s.img, M, (ancho, alto), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        dato = cv2.warpAffine(np.full((alto, ancho), 255, np.uint8), M, (ancho, alto), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0
        dato = cv2.erode(dato.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)     # los pixeles del borde mezclan con el negro
        assert 0.01 < float((~dato).mean()) < 0.2 and bool((girada[~dato] == 0).mean() > 0.9), "el relleno negro no existe: la prueba no discrimina"
        campo = cv2.transform(np.array(s.campo, np.float64).reshape(-1, 1, 2), M).reshape(-1, 2)

        class PeliculaGirada:                     # lo unico que la funcion le pide a una pelicula: R, G, B, gris, validos y dpi
            pass

        g = PeliculaGirada()
        g.B, g.G, g.R = (girada[:, :, i].astype(np.float32) for i in range(3))
        g.gris = cv2.cvtColor(girada, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g.validos, g.dpi = dato, 600.0
        p = piso(g, campo)
        ref = piso(s.pelicula, s.campo)
        assert p.estado == "ok" and ref.estado == "ok"
        x0, y0, x1, y1 = p.region.caja
        assert bool(dato[y0:y1, x0:x1][p.region.mascara].all()), "la region incluye pixeles sin dato (el relleno del giro)"
        for c in "RGB":
            assert abs(p.capas[c].mediana - ref.capas[c].mediana) <= 2.0, f"{c}: {p.capas[c].mediana} contra {ref.capas[c].mediana} sin girar"

    @pytest.mark.parametrize("theta", [1.0, -3.0])
    def test_b_el_recorte_a_ras_girado_da_el_mismo_piso_que_sin_girar(self, theta):
        """La frase del plan: «la sintetica girada 1 grado y recortada a ras da el mismo piso»."""
        sin_giro, con_giro = _sint("A", 0.0), _sint("A", theta)
        a, b = piso(sin_giro.pelicula, sin_giro.campo), piso(con_giro.pelicula, con_giro.campo)
        assert a.estado == b.estado == "ok"
        for c in CAPAS_DEL_PISO:
            assert abs(a.capas[c].mediana - b.capas[c].mediana) <= 1.0, f"{c} con giro {theta}: {b.capas[c].mediana} contra {a.capas[c].mediana}"

    def test_b_las_zonas_transparentes_de_un_tiff_rgba_no_son_pelicula(self):
        """De punta a punta con el lector: un TIFF RGBA con un bloque transparente (alfa 0, pero de un color que parece pelicula clara) en la parte mas lejana de la region. El bloque
        no es pelicula ni su borde (la erosion de 0.5 mm lo rodea): el piso es el de lo que queda."""
        s = _sint("B", 0.4)
        o = s.oraculo
        ys, xs = np.nonzero(o.region)
        bloque = np.zeros(s.forma, bool)
        bloque[ys.max() - 300:ys.max() + 1, xs.max() - 300:xs.max() + 1] = True
        bloque &= o.region
        assert bloque.sum() > 5000, "el bloque no cae en la region: la prueba no discrimina"
        bgra = np.dstack([s.img, np.full(s.forma, 255, np.uint8)])
        bgra[bloque, :3] = (150, 200, 170)
        bgra[bloque, 3] = 0
        pel = _a_pelicula(bgra)
        assert pel.transparentes == int(bloque.sum()) and not pel.validos[bloque].any()
        p = piso(pel, s.campo)
        assert p.estado == "ok"
        r = _region_completa(p, s.forma)
        assert not (r & bloque).any(), "la region incluye pixeles sin dato"
        cerca = cv2.distanceTransform((~bloque).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * ESC <= 0.5
        assert not (r & cerca).any(), "la region llega hasta el borde de lo transparente (sin erosion)"
        elegibles = o.elegibles & ~cerca
        region_esperada = elegibles & (o.dcam >= np.quantile(o.dcam[elegibles], 0.8))
        for capa in "BGR":
            verdad = float(np.median(o.crudo(capa, region_esperada)))
            assert abs(p.capas[capa].mediana - verdad) <= 1.0, f"{capa}: {p.capas[capa].mediana} contra {verdad:.2f}"

    def test_b_los_16_bits_dan_el_mismo_piso_que_los_8(self):
        a, b = _sint("B", 0.4), _sint("B", 0.4, bits=16)
        assert b.pelicula.bits == 16
        pa, pb = piso(a.pelicula, a.campo), piso(b.pelicula, b.campo)
        for c in "RGB":
            assert abs(pa.capas[c].mediana - pb.capas[c].mediana) <= 0.75, c


# ====================================================================================================================== (c) nunca la tinta

class TestNuncaLaTinta:
    def test_c_texto_y_diagonales_pintados_en_la_region_del_piso_no_lo_mueven(self):
        s = _sint("B", 0.4)
        o = s.oraculo
        pintada, mascara = _pintar_texto_y_diagonales(s.img, o.region, (30, 35, 25))
        dentro = int((mascara & o.region).sum())
        assert dentro > 4000, f"solo {dentro} pixeles de tinta caen en la region: la prueba no discrimina"
        p = piso(_a_pelicula(pintada), s.campo)
        limpia = piso(s.pelicula, s.campo)
        verdad = o.piso(excluir=mascara)
        assert p.estado == "ok"
        for c in "BGR":
            assert abs(p.capas[c].mediana - verdad[c]) <= 1.0, f"{c}: {p.capas[c].mediana} contra el piso verdadero {verdad[c]:.2f}"
            assert abs(p.capas[c].mediana - limpia.capas[c].mediana) <= 1.0
        assert not (_region_completa(p, s.forma) & mascara).any(), "la region conserva pixeles de tinta"

    @pytest.mark.parametrize("canal_bgr,capa", [(2, "R"), (1, "G"), (0, "B")], ids=["rojo", "verde", "azul"])
    def test_c_una_tinta_oscura_solo_en_una_capa_tambien_se_rechaza(self, canal_bgr, capa):
        """«En alguna capa» (regla 3): una tinta que oscurece UNA sola capa en casi la mitad de la region, y se prueba con cada una de las tres (un rotulador azul oscurece el rojo;
        uno amarillo, el azul; uno magenta, el verde). La primera version de esta prueba solo oscurecia el rojo: tres variantes del barrido que dejaban fuera el azul o el verde (RV1 a
        RV3 de a2_mutaciones.py) pasaban las 124 pruebas, aunque una tinta que solo oscurece el azul SI mueve el piso (2.1 niveles; revision de la ronda 1, A2-R1-01)."""
        s = _sint("B", 0.4)
        o = s.oraculo
        ys, xs = np.nonzero(o.region)
        manchada = s.img.copy()
        ymed = int(np.median(ys))
        franja = np.zeros(s.forma, bool)
        franja[ymed - 20:ymed + 20, int(np.percentile(xs, 25)):int(np.percentile(xs, 75))] = True
        franja &= o.region
        assert 0.15 < franja.sum() / o.region.sum() < 0.6, f"la tinta cubre {franja.sum() / o.region.sum():.2f} de la region: la prueba no discrimina"
        manchada[:, :, canal_bgr][franja] = 5                         # solo esa capa (BGR: 0 azul, 1 verde, 2 rojo)
        verdad = o.piso(excluir=franja)
        sin_apartar = float(np.median(manchada[:, :, canal_bgr][o.region]))
        assert abs(sin_apartar - verdad[capa]) > 1.5, f"sin apartar la tinta la mediana {NOMBRES[capa]} solo se corre {sin_apartar - verdad[capa]:+.2f}: la tolerancia de 1 nivel no la veria"
        p = piso(_a_pelicula(manchada), s.campo)
        assert p.estado == "ok"
        for c in "BGR":
            assert abs(p.capas[c].mediana - verdad[c]) <= 1.0, f"{c}: {p.capas[c].mediana} contra el piso verdadero {verdad[c]:.2f} (la tinta solo oscurecia el {NOMBRES[capa]})"
        assert not (_region_completa(p, s.forma) & franja).any(), f"la region conserva pixeles de la tinta que solo oscurece el {NOMBRES[capa]}"

    def test_c_el_polvo_claro_no_mueve_la_mediana(self):
        """4 % de la region con +70 niveles (motas, pelos): la media se corre 2.8 niveles, la mediana menos de uno."""
        s = _sint("B", 0.4)
        o = s.oraculo
        rng = np.random.default_rng(7)
        ys, xs = np.nonzero(o.region)
        elegidos = rng.choice(len(ys), size=int(0.04 * len(ys)), replace=False)
        sucia = s.img.astype(np.int16)
        sucia[ys[elegidos], xs[elegidos], :] += 70
        sucia = np.clip(sucia, 0, 255).astype(np.uint8)
        p = piso(_a_pelicula(sucia), s.campo)
        verdad = o.piso()
        for c in "BGR":
            assert abs(p.capas[c].mediana - verdad[c]) <= 1.0, f"{c}: {p.capas[c].mediana} contra {verdad[c]:.2f}: el polvo claro la movio (¿media en vez de mediana?)"

    def test_c_un_halo_claro_en_el_borde_de_la_pelicula_no_mueve_el_piso(self):
        """El borde de la pelicula se aclara (corte, halo del escaner): la erosion de 0.5 mm deja fuera ese anillo, que es lo MAS lejano del campo."""
        s = _sint("B", 0.4)
        o = s.oraculo
        anillo = o.pelicula & (o.borde_mm <= 0.45)
        assert int((anillo & (o.dcam > 5.0)).sum()) > 20000
        halo = s.img.astype(np.int16)
        halo[anillo] += 22
        p = piso(_a_pelicula(np.clip(halo, 0, 255).astype(np.uint8)), s.campo)
        verdad = o.piso()
        for c in "BGR":
            assert abs(p.capas[c].mediana - verdad[c]) <= 1.0, f"{c}: {p.capas[c].mediana} contra {verdad[c]:.2f}: el halo del borde entro (¿sin erosion?)"

    def test_c_un_pixel_con_una_sola_capa_brillante_no_es_fondo(self):
        """El fondo es blanco en las TRES capas: es fondo el pixel cuya capa mas oscura llega al umbral. Una mota verde (solo el verde alto) es pelicula: sigue en la region (no es tinta,
        que es lo oscuro) y la mediana la absorbe."""
        s = _sint("B", 0.4)
        o = s.oraculo
        ys, xs = np.nonzero(o.region)
        ymed = int(np.median(ys))
        mota = np.zeros(s.forma, bool)
        mota[ymed - 12:ymed + 12, int(np.percentile(xs, 40)):int(np.percentile(xs, 60))] = True
        mota &= o.region
        assert mota.sum() > 3000, "la mota no cae en la region: la prueba no discrimina"
        sucia = s.img.copy()
        sucia[:, :, 1][mota] = 250                                    # BGR: solo el verde; el azul y el rojo siguen siendo los de la pelicula (min < 235)
        p = piso(_a_pelicula(sucia), s.campo)
        assert p.estado == "ok"
        incluidos = int((_region_completa(p, s.forma) & mota).sum())
        assert incluidos > 0.95 * mota.sum(), f"solo {incluidos} de {int(mota.sum())} pixeles de la mota quedaron en la region: se tomaron por fondo"

    def test_c_una_etiqueta_clara_lejos_de_la_pelicula_no_es_el_piso(self):
        """Un trozo claro (una etiqueta, otro pedazo de pelicula) sobre la pagina, lejos de la pelicula: no es la pelicula (componente conexa mas grande)."""
        s = _sint("B", 0.4)
        o = s.oraculo
        alto, ancho = s.forma
        sucia = s.img.copy()
        sucia[alto - 260:alto - 40, ancho - 260:ancho - 40, :] = (150, 200, 170)           # BGR; ni fondo (min < 235) ni oscuro
        assert not o.pelicula[alto - 260:alto - 40, ancho - 260:ancho - 40].any(), "la etiqueta cae sobre la pelicula"
        p = piso(_a_pelicula(sucia), s.campo)
        verdad = o.piso()
        for c in "BGR":
            assert abs(p.capas[c].mediana - verdad[c]) <= 1.0, f"{c}: {p.capas[c].mediana} contra {verdad[c]:.2f}: la etiqueta fue el piso"
        x0, y0, x1, y1 = p.region.caja
        assert x1 < ancho - 260 or y1 < alto - 260, "la region incluye la etiqueta"


# ====================================================================================================================== (d) sin margen, nunca un numero

class TestSinMargenNuncaUnNumero:
    @staticmethod
    def _recortada_con_margen_mm(margen_mm):
        """La pagina sintetica SIN giro recortada a `margen_mm` del campo luminoso por los cuatro lados (el cuadrilatero queda alineado con los ejes: el margen es parejo)."""
        s = _sint("B", 0.0)
        c = np.array(s.campo)
        m = int(round(margen_mm / ESC))
        x0, y0 = int(c[:, 0].min()) - m, int(c[:, 1].min()) - m
        x1, y1 = int(c[:, 0].max()) + m + 1, int(c[:, 1].max()) + m + 1
        return _a_pelicula(np.ascontiguousarray(s.img[y0:y1, x0:x1])), [(x - x0, y - y0) for x, y in s.campo]

    @pytest.mark.parametrize("margen", [3.0, 4.0, 4.5])
    def test_d_una_pelicula_que_no_sobresale_del_campo_lo_bastante_no_da_numero(self, margen):
        pel, campo = self._recortada_con_margen_mm(margen)
        p = piso(pel, campo)
        assert p.estado == _pel().MOTIVO_SIN_PISO and p.region is None
        assert all(c.mediana is None and c.iqr is None and c.estado == _pel().MOTIVO_SIN_PISO for c in p.capas.values()), "dio un numero sin pelicula suficiente"
        assert p.valor("G") is None

    def test_d_los_motivos_son_los_del_plan_y_todo_lo_que_no_se_mide_empieza_con_no_medible(self):
        """Los dos textos que el plan fija se escriben aqui tal cual (la prueba compara con la constante del modulo en otros sitios; esta fija la constante). Y cualquier
        `estado` que no sea «ok» empieza con «no medible:» para que la pantalla y los PDF lo reconozcan."""
        pel = _pel()
        assert pel.MOTIVO_SIN_PISO == "no medible: no hay película suficiente fuera del campo"
        assert pel.MOTIVO_PUNTO_FUERA_DE_PELICULA == "no medible: el punto no está sobre película"
        assert pel.MOTIVO_PISO_COMO_EL_FONDO == MOTIVO_COMO_EL_FONDO == "no medible: el piso es tan claro como el fondo del escáner, no como película"
        for nombre in ("MOTIVO_SIN_PISO", "MOTIVO_PUNTO_FUERA_DE_PELICULA", "MOTIVO_POCA_PELICULA_EN_EL_PUNTO", "MOTIVO_CAMPO_INVALIDO", "MOTIVO_SIN_PELICULA", "MOTIVO_SIN_MESETA",
                       "MOTIVO_PISO_COMO_EL_FONDO"):
            assert getattr(pel, nombre).startswith("no medible: "), nombre
        s = _sint("B", 0.4)
        for r in (piso(s.pelicula, s.campo, punto=(0.0, 0.0)), piso(s.pelicula, [(0, 0), (1, 1), (2, 2), (3, 3)]), piso(s.pelicula, s.campo, _P(margen_campo_mm=200.0)),
                  piso(s.pelicula, s.campo, _P(umbral_como_fondo=60.0))):
            assert r.estado.startswith("no medible: ") and all(c.estado.startswith("no medible: ") for c in r.capas.values())

    def test_d_el_estado_de_la_regla_7_dice_el_porcentaje_el_umbral_y_que_revisar(self):
        """El estado completo: «<motivo> (el N % de sus píxeles llega a U niveles hasta en su capa más oscura): revise la tapa y el vidrio del escáner y que el escaneo no lleve ajustes de brillo».
        El porcentaje es el de los pixeles del piso que llegan al umbral (recalculado aqui) y el umbral es el del parametro. Va con numeros dentro: quien lo consuma (C.2, D.1, E.1) pregunta
        `estado != "ok"` o `startswith("no medible")`, nunca compara con una lista cerrada de motivos."""
        pagina = _con_fondo("B", 0.4, 200)
        assert piso(pagina.pelicula, pagina.campo).estado == motivo_completo(100)
        recorte = _con_fondo("L", 0.4, 200)
        f = _fraccion_como_fondo(_sin_la_regla(recorte.pelicula, recorte.campo), recorte.pelicula)
        assert piso(recorte.pelicula, recorte.campo).estado == motivo_completo(round(100 * f)) == motivo_completo(25)
        s = _sint("B", 0.4)
        assert piso(s.pelicula, s.campo, _P(umbral_como_fondo=60.0)).estado == motivo_completo(100, umbral=60), "el umbral que dice el texto es el del parametro"

    def test_d_con_pelicula_de_sobra_en_cambio_si_mide(self):
        pel, campo = self._recortada_con_margen_mm(7.0)
        p = piso(pel, campo)
        assert p.estado == "ok" and p.region.n >= 2000 and p.capas["G"].mediana > 100

    def test_d_una_imagen_sin_pelicula_o_toda_transparente_no_da_numero(self):
        s = _sint("B", 0.4)
        blanca = np.full_like(s.img, 250)
        p = piso(_a_pelicula(blanca), s.campo)
        assert p.estado == _pel().MOTIVO_SIN_PELICULA and p.region is None and all(c.mediana is None for c in p.capas.values())

        class Transparente:
            pass

        t = Transparente()
        t.R, t.G, t.B, t.gris = (s.pelicula.R, s.pelicula.G, s.pelicula.B, s.pelicula.gris)
        t.validos, t.dpi = np.zeros(s.forma, bool), 600.0
        q = piso(t, s.campo)
        assert q.estado == _pel().MOTIVO_SIN_PELICULA and all(c.mediana is None for c in q.capas.values())


# ====================================================================================================================== (e) coherencia con la meseta

class TestCoherenciaConLaMeseta:
    @staticmethod
    def _con_el_marco_en(s, capa_bgr, valor):
        o = s.oraculo
        marco = o.pelicula & (o.dcam > 4.0)
        sucia = s.img.copy()
        sucia[:, :, capa_bgr][marco] = valor
        return _a_pelicula(sucia)

    def test_e_la_meseta_de_referencia_sale_del_campo_y_es_la_de_la_pelicula(self):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        for c, esperado in (("R", 1.0), ("G", 32.0), ("B", 39.0), ("gris", 0.299 * 1.0 + 0.587 * 32.0 + 0.114 * 39.0)):
            assert abs(p.capas[c].meseta - esperado) <= 3.0, f"{c}: meseta {p.capas[c].meseta} (la del generador es {esperado})"
            assert p.capas[c].contraste == pytest.approx(p.capas[c].mediana - p.capas[c].meseta)
            assert p.capas[c].estado == "ok"

    @pytest.mark.parametrize("capa_bgr,capa,valor", [(2, "R", 3), (1, "G", 20), (0, "B", 30)])
    def test_e_una_capa_con_el_piso_igual_o_mas_oscuro_que_la_meseta_es_no_medible_y_las_demas_siguen(self, capa_bgr, capa, valor):
        s = _sint("B", 0.4)
        p = piso(self._con_el_marco_en(s, capa_bgr, valor), s.campo)
        assert p.estado == "ok"
        mala = p.capas[capa]
        assert mala.estado.startswith("no medible") and mala.mediana is None and mala.iqr is None, f"{capa}: dio {mala.mediana}"
        assert NOMBRES[capa] in mala.estado and "meseta" in mala.estado
        assert mala.contraste is not None and mala.contraste < 10.0
        for otra in "RGB":
            if otra != capa:
                assert p.capas[otra].estado == "ok" and p.capas[otra].mediana is not None, f"{otra} tambien se anulo"

    def test_e_el_umbral_son_10_niveles_justos(self):
        s = _sint("B", 0.4)
        meseta = piso(s.pelicula, s.campo).capas["R"].meseta
        justo_debajo = piso(self._con_el_marco_en(s, 2, int(round(meseta + 7))), s.campo)
        justo_encima = piso(self._con_el_marco_en(s, 2, int(round(meseta + 13))), s.campo)
        assert justo_debajo.capas["R"].estado.startswith("no medible"), f"contraste {justo_debajo.capas['R'].contraste}"
        assert justo_encima.capas["R"].estado == "ok", f"contraste {justo_encima.capas['R'].contraste}"

    def test_e_una_pelicula_sin_irradiar_no_tiene_piso_en_ninguna_capa(self):
        s = _sint("B", 0.4)
        o = s.oraculo
        dentro = _poligono(s.forma, s.campo)
        virgen = s.img.copy()
        virgen[dentro & o.pelicula] = (82, 174, 105)
        p = piso(_a_pelicula(virgen), s.campo)
        assert p.estado == "ok"
        assert all(c.estado.startswith("no medible") and c.mediana is None for c in p.capas.values()), "dio piso en una pelicula sin dosis"

    def test_e_un_campo_que_la_pelicula_no_cubre_no_se_puede_comprobar(self):
        s = _sint("B", 0.4)
        lejos = [(x - 3400.0, y - 3400.0) for x, y in s.campo]               # el cuadrilatero cae entero fuera de la imagen: sobre ninguna pelicula
        p = piso(s.pelicula, lejos)
        assert p.estado == _pel().MOTIVO_SIN_MESETA and p.region is None and all(c.mediana is None for c in p.capas.values())


    def test_e_la_meseta_de_referencia_solo_cuenta_pelicula(self):
        """Si parte del campo cae sobre el fondo del escaner (la pelicula no lo cubre entero), esa parte no es meseta: la referencia es la de la pelicula que si esta."""
        s = _sint("B", 0.4)
        c = np.array(s.campo)
        limite = c[:, 0].min() + 0.65 * (c[:, 0].max() - c[:, 0].min())
        columnas = np.arange(s.forma[1])[None, :]
        blanco = _poligono(s.forma, s.campo) & (columnas < limite)
        sucia = s.img.copy()
        sucia[blanco] = 250
        assert 0.4 < blanco.sum() / _poligono(s.forma, s.campo).sum() < 0.7
        p = piso(_a_pelicula(sucia), s.campo)
        assert p.estado == "ok"
        for capa, esperado in (("R", 1.0), ("G", 32.0), ("B", 39.0)):
            assert abs(p.capas[capa].meseta - esperado) <= 4.0 and p.capas[capa].estado == "ok", f"{capa}: meseta {p.capas[capa].meseta}"

    @staticmethod
    def _campo_chico_en_tres_zonas():
        """Una pelicula sin fondo de escaner (sigue mas alla de la imagen) con un campo luminoso de 25.4 mm de lado y tres zonas de valor conocido segun la profundidad dentro de el:
        de 0 a 5 mm de los lados (la penumbra: la mas clara), de 5 a 10 mm y a mas de 10 mm (el centro: la mas oscura). Fuera del campo, el piso. En un campo de 100 mm el anillo de 5 mm es
        el 19 % del area y la mediana lo absorbe (la meseta se mueve 1 nivel en cinco de seis peliculas reales y 3 en la peor, logs/A2/correccion_ronda1/08_p5_meseta_con_y_sin_margen.log);
        en uno de 25.4 mm es el 63 %."""
        n, a, b = 1500, 450, 1050                                                  # 600 px = 25.4 mm de lado
        yy, xx = np.mgrid[0:n, 0:n]
        profundidad = np.minimum(np.minimum(xx - a, b - xx), np.minimum(yy - a, b - yy)) * np.float64(ESC)          # mm hacia adentro del campo (negativa fuera)
        zona = np.select([profundidad < 0, profundidad <= 5.0, profundidad <= 10.0], [0, 1, 2], default=3)
        valores = {0: (105.0, 174.0, 82.0), 1: (70.0, 120.0, 70.0), 2: (30.0, 70.0, 55.0), 3: (2.0, 30.0, 40.0)}      # R, G, B de cada zona
        tabla = np.array([valores[z] for z in range(4)], np.float32)

        class Pel:
            pass

        pel = Pel()
        pel.R, pel.G, pel.B = (np.ascontiguousarray(tabla[zona, i]) for i in range(3))
        pel.gris = (0.299 * pel.R + 0.587 * pel.G + 0.114 * pel.B).astype(np.float32)
        pel.validos, pel.dpi = np.ones((n, n), bool), 600.0
        return pel, [(a, a), (b, a), (b, b), (a, b)], valores

    def test_e_la_meseta_de_referencia_aparta_el_margen_de_los_lados_del_campo(self):
        """Regla 5: la meseta contra la que se compara el piso es la mediana de la pelicula dentro del campo a MAS de `margen_campo_mm` de sus lados (la penumbra esta ahi). Con un campo de
        25.4 mm el anillo de 0 a 5 mm es el 63 % del campo: si la meseta lo contara saldria el valor del anillo y no el del interior. La mutacion RV17 de a2_mutaciones.py (sin el margen)
        sobrevivia a las 124 pruebas porque en un campo de 100 mm la mediana absorbe el anillo (observacion M5 de la revision de la ronda 1, A2-R1-03). Y el margen es el del parametro
        (RV18): con 10 mm la meseta es la del centro."""
        pel, campo, valores = self._campo_chico_en_tres_zonas()
        for margen, zona in ((None, 2), (10.0, 3)):
            p = piso(pel, campo) if margen is None else piso(pel, campo, _P(margen_campo_mm=margen))
            etiqueta = "margen de fabrica (5 mm)" if margen is None else f"margen de {margen:g} mm"
            assert p.estado == "ok", (etiqueta, p.estado)
            for i, c in enumerate("RGB"):
                assert p.capas[c].meseta == pytest.approx(valores[zona][i], abs=1e-3), f"{etiqueta}, {c}: meseta {p.capas[c].meseta}, la de la zona {zona} es {valores[zona][i]}"
                assert p.capas[c].mediana == pytest.approx(valores[0][i], abs=1e-3), f"{etiqueta}, {c}: el piso no es el de la pelicula de fuera del campo"
                assert p.capas[c].contraste == pytest.approx(valores[0][i] - valores[zona][i], abs=1e-3)
            esperada_gris = 0.299 * valores[zona][0] + 0.587 * valores[zona][1] + 0.114 * valores[zona][2]
            assert p.capas["gris"].meseta == pytest.approx(esperada_gris, abs=1e-2), f"{etiqueta}, gris: meseta {p.capas['gris'].meseta} y la de la zona {zona} es {esperada_gris:.2f}"


# ====================================================================================================================== (f) el sexto clic

PARCHE = (slice(20, 220), slice(2950, 3150))          # el trozo sin irradiar, en la pagina B: 200 x 200 px (8.5 mm), arriba a la derecha, separado de la pelicula
PUNTO_DEL_PARCHE = (3050.0, 120.0)


class TestElSextoClic:
    @staticmethod
    def _con_un_trozo_sin_irradiar(tinta=None):
        """La pagina B con un trozo de pelicula sin irradiar (virgen: 82/174/105, con el ruido del escaner) escaneado junto, separado de la pelicula del campo."""
        s = _sint("B", 0.4)
        sucia = s.img.copy()
        rng = np.random.default_rng(3)
        sucia[PARCHE] = np.clip(np.rint(np.array((82, 174, 105), np.float64) + rng.normal(0.0, 1.5, (200, 200, 3))), 0, 255).astype(np.uint8)
        if tinta is not None:
            sucia[60:180, 2990:3110, :] = tinta
        assert not s.oraculo.pelicula[PARCHE].any(), "el trozo toca la pelicula del campo"
        return s, _a_pelicula(sucia)

    def test_f_sobre_un_trozo_sin_irradiar_el_piso_es_su_mediana(self):
        s, pel = self._con_un_trozo_sin_irradiar()
        p = piso(pel, s.campo, punto=PUNTO_DEL_PARCHE)
        assert p.estado == "ok" and p.origen == "manual" and p.region.origen == "manual"
        for c, esperado in (("B", 82.0), ("G", 174.0), ("R", 105.0)):
            assert abs(p.capas[c].mediana - esperado) <= 1.0, f"{c}: {p.capas[c].mediana}"
        lado = 3.0 / ESC
        assert abs(p.region.n - lado * lado) <= 0.05 * lado * lado, f"{p.region.n} pixeles para un cuadrado de 3 x 3 mm ({lado * lado:.0f})"
        x0, y0, x1, y1 = p.region.caja
        assert abs((x1 - x0) - lado) <= 3 and abs((y1 - y0) - lado) <= 3 and x0 < PUNTO_DEL_PARCHE[0] < x1 and y0 < PUNTO_DEL_PARCHE[1] < y1
        independiente = float(_distancia_al_campo_mm(s.forma, s.campo)[_region_completa(p, s.forma)].mean())          # el trozo esta a unos 16 mm del campo y asi se dice
        assert abs(p.region.distancia_media_mm - independiente) <= 0.08 and p.region.distancia_media_mm > 14.0, (p.region.distancia_media_mm, independiente)

    def test_f_el_sexto_clic_no_necesita_ser_parte_de_la_pelicula_del_campo(self):
        """El trozo es otra componente conexa: la regla de la componente mas grande es de la region AUTOMATICA, no del sexto clic."""
        s, pel = self._con_un_trozo_sin_irradiar()
        assert piso(pel, s.campo, punto=PUNTO_DEL_PARCHE).estado == "ok"
        automatico = piso(pel, s.campo)
        assert automatico.origen == "automatico" and automatico.estado == "ok"
        assert not _region_completa(automatico, s.forma)[PARCHE].any(), "el piso automatico tomo el trozo suelto"

    @pytest.mark.parametrize("punto", [(3200.0, 1600.0), (1600.0, 3260.0), (100.0, 100.0)])
    def test_f_sobre_el_fondo_no_es_medible_con_el_motivo_del_plan(self, punto):
        s, pel = self._con_un_trozo_sin_irradiar()
        p = piso(pel, s.campo, punto=punto)
        assert p.estado == _pel().MOTIVO_PUNTO_FUERA_DE_PELICULA, punto
        assert p.origen == "manual" and p.region is None
        assert all(c.mediana is None and c.estado == _pel().MOTIVO_PUNTO_FUERA_DE_PELICULA for c in p.capas.values())

    @pytest.mark.parametrize("punto", [(-5.0, 10.0), (10 ** 6, 10 ** 6), (float("nan"), 3.0)])
    def test_f_un_punto_fuera_de_la_imagen_no_esta_sobre_pelicula(self, punto):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, s.campo, punto=punto)
        assert p.estado == _pel().MOTIVO_PUNTO_FUERA_DE_PELICULA

    def test_f_con_poca_pelicula_alrededor_del_punto_no_es_medible(self):
        s, pel = self._con_un_trozo_sin_irradiar()
        p = piso(pel, s.campo, punto=(2951.0, 120.0))          # en el borde izquierdo del trozo: la mitad del cuadrado cae en el fondo y lo demas se erosiona
        assert p.estado == _pel().MOTIVO_POCA_PELICULA_EN_EL_PUNTO and p.region is None

    def test_f_la_tinta_no_es_un_piso(self):
        s, pel = self._con_un_trozo_sin_irradiar(tinta=(15, 20, 3))         # BGR: una mancha de tinta negra de 5 mm en el centro del trozo
        p = piso(pel, s.campo, punto=PUNTO_DEL_PARCHE)
        assert p.estado == "ok" and all(c.estado.startswith("no medible") and c.mediana is None for c in p.capas.values()), "la tinta se tomo por piso"

    def test_f_la_tinta_a_medias_en_el_cuadrado_no_mueve_el_piso(self):
        """Casi la mitad del cuadrado de 3 x 3 mm es tinta: la mediana de todo el cuadrado ya se movio (1.5 a 2 niveles); sin la tinta, el piso es el del trozo."""
        s, pel_limpia = self._con_un_trozo_sin_irradiar()
        sucia = s.img.copy()
        rng = np.random.default_rng(3)
        sucia[PARCHE] = np.clip(np.rint(np.array((82, 174, 105), np.float64) + rng.normal(0.0, 1.5, (200, 200, 3))), 0, 255).astype(np.uint8)
        sucia[20:220, 3000:3047, :] = (15, 20, 3)                                   # el 45 % izquierdo del cuadrado (x de 3015 a 3085)
        p = piso(_a_pelicula(sucia), s.campo, punto=PUNTO_DEL_PARCHE)
        assert p.estado == "ok", p.estado
        for c, esperado in (("B", 82.0), ("G", 174.0), ("R", 105.0)):
            assert abs(p.capas[c].mediana - esperado) <= 1.0, f"{c}: {p.capas[c].mediana} (la tinta no se aparto)"
        assert 0.4 < p.region.n / (3.0 / ESC) ** 2 < 0.7, "la region deberia ser lo que queda del cuadrado sin la tinta"

    @pytest.mark.parametrize("canal_bgr,capa", [(2, "R"), (1, "G"), (0, "B")], ids=["rojo", "verde", "azul"])
    def test_f_la_tinta_de_una_sola_capa_a_medias_del_cuadrado_tampoco_mueve_el_piso(self, canal_bgr, capa):
        """La regla 3 («en alguna capa») vale tambien para el sexto clic: el 45 % del cuadrado de 3 x 3 mm oscurecido en UNA sola capa. Sin apartarla, la mediana de esa capa baja 2
        niveles (revision de la ronda 1, A2-R1-01); con la regla, el piso es el del trozo en las tres capas."""
        s = _sint("B", 0.4)
        sucia = s.img.copy()
        rng = np.random.default_rng(3)
        sucia[PARCHE] = np.clip(np.rint(np.array((82, 174, 105), np.float64) + rng.normal(0.0, 1.5, (200, 200, 3))), 0, 255).astype(np.uint8)
        sucia[20:220, 3000:3047, canal_bgr] = 5                                      # el 45 % izquierdo del cuadrado (x de 3015 a 3085), solo esa capa
        p = piso(_a_pelicula(sucia), s.campo, punto=PUNTO_DEL_PARCHE)
        assert p.estado == "ok", p.estado
        for c, esperado in (("B", 82.0), ("G", 174.0), ("R", 105.0)):
            assert abs(p.capas[c].mediana - esperado) <= 1.0, f"{c}: {p.capas[c].mediana} (la tinta que solo oscurece el {NOMBRES[capa]} no se aparto)"
        assert 0.4 < p.region.n / (3.0 / ESC) ** 2 < 0.7, "la region deberia ser lo que queda del cuadrado sin la tinta"

    def test_f_un_punto_dentro_del_campo_no_es_un_piso(self):
        s = _sint("B", 0.4)
        centro = tuple(np.mean(np.array(s.campo), axis=0) + (150.0, 150.0))
        p = piso(s.pelicula, s.campo, punto=centro)
        assert p.origen == "manual" and all(c.mediana is None for c in p.capas.values())

    def test_f_sobre_la_pelicula_de_fuera_del_campo_da_su_mediana(self):
        s = _sint("B", 0.4)
        o = s.oraculo
        cand = o.pelicula & (o.borde_mm >= 2.1) & (o.dcam > 5.5)
        k = int(np.argmax(np.where(cand, o.dcam, -1.0)))
        punto = (float(k % s.forma[1]), float(k // s.forma[1]))
        p = piso(s.pelicula, s.campo, punto=punto)
        assert p.estado == "ok" and p.origen == "manual", p.estado
        local = _region_completa(p, s.forma)
        for capa in "BGR":
            assert abs(p.capas[capa].mediana - float(np.median(o.crudo(capa, local)))) <= 1.0, capa

    def test_f_el_sexto_clic_sobre_el_fondo_gris_no_toma_el_vacio_como_piso(self):
        """La regla (7) vale para los DOS origenes del piso. Con el fondo del escaner en 200 (por debajo de `umbral_fondo`) el fondo cuenta como pelicula: el punto (150, 150), en la esquina de la
        pagina, «esta sobre pelicula» y el cuadrado de 3 x 3 mm que lo rodea es fondo. Sin la regla el piso seria 200; con ella, «no medible: el piso es tan claro como el fondo del escaner...»."""
        s = _con_fondo("B", 0.4, 200)
        sin_regla = _sin_la_regla(s.pelicula, s.campo, (150.0, 150.0))
        assert sin_regla.estado == "ok" and sin_regla.origen == "manual" and all(abs(sin_regla.capas[c].mediana - 200) <= 1.0 for c in CAPAS_DEL_PISO), \
            "sin la regla el sexto clic sobre el fondo gris tendria que dar el vacio como piso: la prueba no discrimina"
        p = piso(s.pelicula, s.campo, punto=(150.0, 150.0))
        assert p.estado.startswith(MOTIVO_COMO_EL_FONDO), p.estado
        assert p.origen == "manual" and p.region is None and all(c.mediana is None and c.estado == p.estado for c in p.capas.values())

    def test_f_con_el_fondo_gris_el_sexto_clic_sobre_la_pelicula_si_mide(self):
        """La regla mira los pixeles de la REGION, no la pagina: con el mismo fondo gris, un sexto clic sobre la pelicula de fuera del campo (el mismo punto que en la sintetica de fondo blanco) da el
        mismo piso que con el fondo blanco."""
        base = _sint("B", 0.4)
        o = base.oraculo
        cand = o.pelicula & (o.borde_mm >= 2.1) & (o.dcam > 5.5)
        k = int(np.argmax(np.where(cand, o.dcam, -1.0)))
        punto = (float(k % base.forma[1]), float(k // base.forma[1]))
        gris = _con_fondo("B", 0.4, 200)
        p, ref = piso(gris.pelicula, gris.campo, punto=punto), piso(base.pelicula, base.campo, punto=punto)
        assert ref.estado == "ok" and p.estado == "ok" and p.origen == "manual", (ref.estado, p.estado)
        for c in CAPAS_DEL_PISO:
            assert abs(p.capas[c].mediana - ref.capas[c].mediana) <= 0.5, f"{c}: {p.capas[c].mediana} contra {ref.capas[c].mediana} con el fondo blanco"


# ====================================================================================================================== (g) de donde salio

class TestDiceDeDondeSalio:
    @pytest.mark.parametrize("variante,theta", [("A", 0.0), ("A", 1.0), ("B", 0.9), ("C", 0.4), ("E", -3.0)])
    def test_g_la_distancia_media_que_dice_es_la_de_la_region_medida_de_otro_modo(self, variante, theta):
        s = _sint(variante, theta)
        o = s.oraculo
        p = piso(s.pelicula, s.campo)
        r = _region_completa(p, s.forma)
        independiente = float(o.dcam[r].mean())
        assert abs(p.region.distancia_media_mm - independiente) <= 0.08, f"dice {p.region.distancia_media_mm:.3f} mm y la region esta a {independiente:.3f}"
        assert p.region.distancia_minima_mm == pytest.approx(float(o.dcam[r].min()), abs=0.1)
        assert p.region.distancia_maxima_mm == pytest.approx(float(o.dcam[r].max()), abs=0.1)
        assert p.region.distancia_minima_mm > 5.0 - 0.1, "la region toca el margen del campo"

    def test_g_la_region_es_lo_mas_lejano_y_nunca_lo_cercano(self):
        s = _sint("B", 0.4)
        o = s.oraculo
        p = piso(s.pelicula, s.campo)
        r = _region_completa(p, s.forma)
        assert p.region.distancia_media_mm > float(np.median(o.dcam[o.elegibles])) + 0.2, "no es la parte mas lejana de lo elegible"
        assert float(o.dcam[r].min()) >= o.umbral_distancia - 0.1
        assert 0.15 < r.sum() / o.elegibles.sum() < 0.25, "no es el 20 % de lo elegible"
        assert not (r & ~o.pelicula).any() and not (r & (o.borde_mm <= 0.4)).any(), "la region toca fuera de la pelicula o el borde"

    def test_g_en_ml0_el_piso_coincide_con_la_franja_mas_lejana_que_midio_la_revision(self):
        p = piso(_real("ML0"), CLICS_REALES["ML0"])
        assert p.estado == "ok"
        assert 7.5 <= p.region.distancia_media_mm <= 9.0, f"distancia media {p.region.distancia_media_mm:.2f} mm"
        b, g, r = FRANJA_MAS_LEJANA_ML0_BGR
        assert abs(p.capas["B"].mediana - b) <= 5 and abs(p.capas["G"].mediana - g) <= 5 and abs(p.capas["R"].mediana - r) <= 6, (
            f"piso B/G/R {p.capas['B'].mediana}/{p.capas['G'].mediana}/{p.capas['R'].mediana} contra la franja de 8-9 mm de la revision {FRANJA_MAS_LEJANA_ML0_BGR}")

    def test_g_la_franja_de_la_revision_se_reproduce_con_codigo_independiente_y_el_piso_cae_entre_las_dos_mas_lejanas(self):
        """Ancla del ancla: la tabla de la revision se reproduce con otro codigo (distancia por rasterizacion, lado de abajo, +-30 mm), y el piso queda entre las franjas de
        7-8 y 8-9 mm (el 20 % mas lejano incluye las esquinas, algo mas claras)."""
        ruta = _corpus.pelicula("ML0")
        if ruta is None:
            pytest.skip("HI-0")
        img = cv2.imdecode(np.fromfile(ruta, np.uint8), cv2.IMREAD_COLOR)
        UL, UR, DR, DL = CLICS_REALES["ML0"]
        d = _distancia_al_campo_mm(img.shape[:2], [UL, UR, DR, DL])
        c0, c1 = int(max(UL[0], DL[0]) + 30 / ESC), int(min(UR[0], DR[0]) - 30 / ESC)
        franjas = {}
        for lo in (7, 8):
            sel = (d >= lo) & (d < lo + 1)
            sel[:, :c0] = False
            sel[:, c1:] = False
            sel[:max(DL[1], DR[1]), :] = False
            franjas[lo] = [float(np.median(img[:, :, c][sel])) for c in range(3)]       # B, G, R
        p = piso(_real("ML0"), CLICS_REALES["ML0"])
        for i, capa in enumerate(("B", "G", "R")):
            bajo, alto = sorted((franjas[7][i], franjas[8][i]))
            assert bajo - 4 <= p.capas[capa].mediana <= alto + 4, f"{capa}: piso {p.capas[capa].mediana}, franjas 7-8 y 8-9 mm: {franjas[7][i]:.0f} y {franjas[8][i]:.0f}"
        assert abs(franjas[8][1] - FRANJA_MAS_LEJANA_ML0_BGR[1]) <= 4 and abs(franjas[8][0] - FRANJA_MAS_LEJANA_ML0_BGR[0]) <= 6, "la tabla de la revision ya no se reproduce"


# ====================================================================================================================== la escala

class TestLaEscalaEsLaDelProcedimiento:
    def test_h_una_resolucion_de_editor_96_dpi_da_lo_mismo_que_600(self):
        s = _sint("B", 0.4)
        a = piso(s.pelicula, s.campo)
        b_pelicula = _pel().leer_pelicula(gen.codificar(s.img, "tiff", 96))
        assert b_pelicula.dpi == pytest.approx(96.0, abs=0.1)
        b = piso(b_pelicula, s.campo)
        assert b.escala_mm == pytest.approx(ESC) == pytest.approx(a.escala_mm)
        assert _medianas(a) == _medianas(b) and a.region.n == b.region.n and a.region.distancia_media_mm == b.region.distancia_media_mm

    def test_h_sin_resolucion_declarada_tambien_da_lo_mismo(self):
        s = _sint("B", 0.4)
        sin = _pel().leer_pelicula(_datos_de_tiff_sin_resolucion(s.img))
        assert sin.dpi is None
        assert _medianas(piso(sin, s.campo)) == _medianas(piso(s.pelicula, s.campo))

    @pytest.mark.parametrize("dpi", [300, 200, 1200])
    def test_h_otra_resolucion_no_tiene_escala_y_no_se_inventa_un_piso(self, dpi):
        s = _sint("B", 0.4)
        p = piso(_pel().leer_pelicula(gen.codificar(s.img, "tiff", dpi)), s.campo)
        assert p.escala_mm is None and p.region is None
        assert p.estado.startswith("no medible") and "resolución" in p.estado and str(dpi) in p.estado
        assert all(c.mediana is None for c in p.capas.values())


# ====================================================================================================================== el contrato de la salida

class TestElContratoDeLaSalida:
    def test_i_el_piso_trae_las_cuatro_capas_con_todo_lo_que_dice_el_plan(self):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        assert p.estado == "ok" and p.origen == "automatico" and set(p.capas) == set(CAPAS_DEL_PISO)
        for c, capa in p.capas.items():
            assert capa.capa == c and capa.estado == "ok"
            assert isinstance(capa.mediana, float) and isinstance(capa.iqr, float) and isinstance(capa.n, int)
            assert capa.n == p.region.n > 2000 and capa.iqr > 0
        x0, y0, x1, y1 = p.region.caja
        assert p.region.mascara.shape == (y1 - y0, x1 - x0) and p.region.mascara.dtype == bool and int(p.region.mascara.sum()) == p.region.n
        assert not p.region.mascara.flags.writeable
        assert p.escala_mm == pytest.approx(ESC) and len(p.campo_luz) == 4

    def test_i_la_mediana_el_iqr_y_el_gris_son_los_de_los_pixeles_de_la_region(self):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        x0, y0, x1, y1 = p.region.caja
        for c in CAPAS_DEL_PISO:
            plano = getattr(s.pelicula, c)[y0:y1, x0:x1][p.region.mascara]
            q1, q3 = np.percentile(plano, [25, 75])
            assert p.capas[c].mediana == pytest.approx(float(np.median(plano)), abs=1e-4), c
            assert p.capas[c].iqr == pytest.approx(float(q3 - q1), abs=1e-4), c

    def test_i_valor_todas_medibles_campo_luz_y_la_descripcion_de_lo_que_falla(self):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        assert p.todas_medibles is True and all(p.valor(c) == p.capas[c].mediana and p.valor(c) is not None for c in CAPAS_DEL_PISO)
        assert sorted(p.campo_luz) == sorted((float(x), float(y)) for x, y in s.campo)
        assert "no medible" not in p.descripcion()
        o = s.oraculo
        marco = o.pelicula & (o.dcam > 4.0)
        sucia = s.img.copy()
        sucia[:, :, 2][marco] = 3                                 # el rojo del marco igual a la meseta: esa capa no se puede medir y las otras si
        q = piso(_a_pelicula(sucia), s.campo)
        assert q.estado == "ok" and q.todas_medibles is False and q.valor("R") is None and q.valor("G") is not None
        assert "rojo: no medible" in q.descripcion() and "verde: no medible" not in q.descripcion()
        assert piso(s.pelicula, [(0, 0), (1, 1), (2, 2), (3, 3)]).todas_medibles is False

    def test_i_no_modifica_la_pelicula_y_es_determinista(self):
        s = _sint("B", 0.4)
        antes = [hash(getattr(s.pelicula, c).tobytes()) for c in ("R", "G", "B", "gris", "validos")]
        a, b = piso(s.pelicula, s.campo), piso(s.pelicula, s.campo)
        assert [hash(getattr(s.pelicula, c).tobytes()) for c in ("R", "G", "B", "gris", "validos")] == antes
        assert _medianas(a) == _medianas(b) and a.region.n == b.region.n and (a.region.mascara == b.region.mascara).all()

    def test_i_el_orden_de_las_esquinas_no_importa(self):
        s = _sint("B", 0.4)
        a = piso(s.pelicula, s.campo)
        for orden in ([3, 2, 1, 0], [1, 3, 0, 2], [2, 0, 3, 1]):
            b = piso(s.pelicula, [s.campo[i] for i in orden])
            assert _medianas(a) == _medianas(b) and a.region.n == b.region.n and a.region.distancia_media_mm == pytest.approx(b.region.distancia_media_mm)

    def test_i_el_campo_puede_llegar_como_lista_de_listas_tupla_de_tuplas_o_arreglo(self):
        s = _sint("B", 0.4)
        a = piso(s.pelicula, s.campo)
        for forma in ([list(p) for p in s.campo], tuple(tuple(p) for p in s.campo), np.array(s.campo), np.array(s.campo, np.float32)):
            b = piso(s.pelicula, forma)
            assert _medianas(a) == _medianas(b) and a.region.n == b.region.n, type(forma)

    def test_i_se_puede_resumir_en_un_diccionario_que_viaja_como_json(self):
        s = _sint("B", 0.4)
        d = piso(s.pelicula, s.campo).como_dict()
        texto = json.dumps(d)
        assert d["estado"] == "ok" and d["origen"] == "automatico" and set(d["capas"]) == set(CAPAS_DEL_PISO)
        assert d["capas"]["G"]["mediana"] > 100 and d["region"]["n"] > 2000 and d["region"]["distancia_media_mm"] > 5.0
        assert "mascara" not in texto
        sin = piso(s.pelicula, s.campo, punto=(10 ** 6, 10 ** 6)).como_dict()
        json.dumps(sin)
        assert sin["region"] is None and sin["capas"]["G"]["mediana"] is None

    CASOS_DEL_DICCIONARIO = ("automatico", "manual", "sin_region", "una_capa_sin_medir", "sin_escala", "campo_no_convexo", "como_el_fondo")

    @staticmethod
    def _caso_del_diccionario(caso):
        """(el `Piso`, la sintetica, la pelicula medida y el campo que se dio) de cada forma de terminar la funcion: con la region automatica, con el sexto clic, sin region (el punto no esta
        sobre pelicula), con una capa que no se puede medir, sin escala (otra resolucion), con un campo que no es un cuadrilatero convexo y con un piso tan claro como el fondo del escaner
        (la regla 7: la pagina con el fondo en 200)."""
        if caso == "como_el_fondo":
            gris = _con_fondo("B", 0.4, 200)
            return piso(gris.pelicula, gris.campo), gris, gris.pelicula, gris.campo
        s = _sint("B", 0.4)
        o = s.oraculo
        pelicula, campo = s.pelicula, s.campo
        if caso == "automatico":
            return piso(pelicula, campo), s, pelicula, campo
        if caso == "manual":
            cand = o.pelicula & (o.borde_mm >= 2.1) & (o.dcam > 5.5)
            k = int(np.argmax(np.where(cand, o.dcam, -1.0)))
            return piso(pelicula, campo, punto=(float(k % s.forma[1]), float(k // s.forma[1]))), s, pelicula, campo
        if caso == "sin_region":
            return piso(pelicula, campo, punto=(10 ** 6, 10 ** 6)), s, pelicula, campo
        if caso == "una_capa_sin_medir":
            sucia = s.img.copy()
            sucia[:, :, 2][o.pelicula & (o.dcam > 4.0)] = 3                          # el rojo del marco igual a la meseta: esa capa no se puede medir y las otras si
            pelicula = _a_pelicula(sucia)
            return piso(pelicula, campo), s, pelicula, campo
        if caso == "sin_escala":
            pelicula = _a_pelicula(s.img, dpi=300)                                     # otra resolucion: sin escala no hay milimetros
            return piso(pelicula, campo), s, pelicula, campo
        if caso == "campo_no_convexo":
            campo = [(100, 100), (300, 100), (300, 300), (250, 150)]
            return piso(pelicula, campo), s, pelicula, campo
        raise AssertionError(caso)

    @pytest.mark.parametrize("caso", CASOS_DEL_DICCIONARIO)
    def test_i_el_diccionario_dice_lo_mismo_que_el_piso_campo_por_campo(self, caso):
        """`como_dict()` es lo que viaja con el analisis: cada campo suyo dice lo que el `Piso` dice, en cada forma de terminar la funcion. La primera version de la prueba (la de arriba)
        solo miraba cinco campos y un diccionario con la distancia minima y la maxima cruzadas la pasaba (RV5 de a2_mutaciones.py; revision de la ronda 1, A2-R1-03)."""
        pel = _pel()
        p, s, pelicula, campo = self._caso_del_diccionario(caso)
        d = p.como_dict()
        assert json.loads(json.dumps(d)) == d, "no viaja como JSON sin perder nada"
        # 1. campo por campo (y las claves: dos diccionarios iguales tienen las mismas) contra los atributos publicos del piso
        assert d == _dict_esperado(p)
        # 2. lo que no sale de la funcion: la entrada, los parametros del plan y la escala del procedimiento
        if caso == "campo_no_convexo":
            assert d["campo_luz"] == [[float(x), float(y)] for x, y in campo], "un campo invalido se devuelve tal como llego, en el orden dado"
        else:
            assert sorted(map(tuple, d["campo_luz"])) == sorted((float(x), float(y)) for x, y in campo)
        assert set(d["parametros"]) == set(PLAN) and {k: d["parametros"][k] for k in PLAN} == PLAN
        assert d["origen"] == ("manual" if caso in ("manual", "sin_region") else "automatico")             # el punto fuera de la pelicula tambien es un sexto clic
        assert d["escala_mm"] == (None if caso == "sin_escala" else pytest.approx(ESC))
        assert set(d["capas"]) == set(CAPAS_DEL_PISO)
        # 3. lo que dice cada forma de terminar
        if caso in ("automatico", "manual", "una_capa_sin_medir"):
            r = d["region"]
            x0, y0, x1, y1 = r["caja"]
            assert d["estado"] == "ok" and r["origen"] == d["origen"]
            assert r["n"] == int(p.region.mascara.sum()) and p.region.mascara.shape == (y1 - y0, x1 - x0)
            assert r["distancia_minima_mm"] < r["distancia_media_mm"] < r["distancia_maxima_mm"]
            independiente = s.oraculo.dcam[_region_completa(p, s.forma)]
            assert r["distancia_media_mm"] == pytest.approx(float(independiente.mean()), abs=0.1)
            assert r["distancia_minima_mm"] == pytest.approx(float(independiente.min()), abs=0.1)
            assert r["distancia_maxima_mm"] == pytest.approx(float(independiente.max()), abs=0.1)
            for c, capa in d["capas"].items():
                assert capa["n"] == r["n"] and capa["meseta"] is not None and capa["contraste"] is not None
                if caso == "una_capa_sin_medir" and c == "R":
                    assert capa["estado"].startswith("no medible") and capa["mediana"] is None and capa["iqr"] is None and capa["contraste"] < 10.0
                    continue
                plano = getattr(pelicula, c)[y0:y1, x0:x1][p.region.mascara]
                q1, q3 = np.percentile(plano, [25, 75])
                assert capa["estado"] == "ok"
                assert capa["mediana"] == pytest.approx(float(np.median(plano)), abs=1e-4) and capa["iqr"] == pytest.approx(float(q3 - q1), abs=1e-4)
                assert capa["contraste"] == pytest.approx(capa["mediana"] - capa["meseta"], abs=1e-4)
        else:
            assert d["region"] is None and d["estado"].startswith("no medible: ")
            for capa in d["capas"].values():
                assert capa["estado"] == d["estado"] and capa["mediana"] is None and capa["iqr"] is None and capa["n"] == 0
        if caso == "sin_region":
            assert d["estado"] == pel.MOTIVO_PUNTO_FUERA_DE_PELICULA
        if caso == "sin_escala":
            assert d["estado"].startswith("no medible: la película se escaneó a otra resolución (300 dpi)")
        if caso == "campo_no_convexo":
            assert d["estado"] == pel.MOTIVO_CAMPO_INVALIDO
        if caso == "como_el_fondo":
            assert d["estado"] == motivo_completo(100) and d["estado"].startswith(pel.MOTIVO_PISO_COMO_EL_FONDO), "el estado del diccionario es el del piso rechazado por la regla 7"
            assert d["origen"] == "automatico" and d["parametros"]["umbral_como_fondo"] == 170.0 and d["parametros"]["fraccion_como_fondo"] == 0.10, "los dos parametros de la regla viajan con el analisis"

    def test_i_la_descripcion_dice_de_donde_salio_y_que_es_piso_y_no_pelicula_virgen(self):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        texto = p.descripcion()
        assert "piso" in texto.lower() and "fuera del campo" in texto and f"{p.region.distancia_media_mm:.1f} mm" in texto
        assert "No es película sin irradiar" in texto and "virgen" not in texto.lower()
        o = s.oraculo
        cand = o.pelicula & (o.borde_mm >= 2.1) & (o.dcam > 5.5)
        k = int(np.argmax(np.where(cand, o.dcam, -1.0)))
        sexto = piso(s.pelicula, s.campo, punto=(float(k % s.forma[1]), float(k // s.forma[1])))
        assert "punto" in sexto.descripcion() and "3 × 3 mm" in sexto.descripcion()
        assert "no medible" in piso(s.pelicula, s.campo, punto=(10 ** 6, 10 ** 6)).descripcion()

    def test_i_los_textos_no_llevan_simbolos_de_correcto_o_incorrecto(self):
        """DA-18: ningun texto que ve el usuario lleva marcas de verificacion, equis, advertencias ni emojis."""
        pel = _pel()
        s = _sint("B", 0.4)
        textos = [pel.MOTIVO_SIN_PISO, pel.MOTIVO_PUNTO_FUERA_DE_PELICULA, pel.MOTIVO_POCA_PELICULA_EN_EL_PUNTO, pel.MOTIVO_CAMPO_INVALIDO, pel.MOTIVO_SIN_PELICULA,
                  pel.MOTIVO_SIN_MESETA, pel.MOTIVO_PISO_COMO_EL_FONDO]
        for r in (piso(s.pelicula, s.campo), piso(s.pelicula, s.campo, punto=(0.0, 0.0)), piso(s.pelicula, [(0, 0), (1, 1), (2, 2), (3, 3)]),
                  piso(s.pelicula, s.campo, _P(umbral_como_fondo=60.0))):
            textos += [r.estado, r.descripcion()] + [c.estado for c in r.capas.values()]
        textos += [v["motivo"] for v in pel.PARAMETROS_DEL_PISO.values()] + [v["unidad"] for v in pel.PARAMETROS_DEL_PISO.values()]
        for t in textos:
            assert all(ord(ch) < 0x2190 for ch in t), f"simbolo en: {t}"


# ====================================================================================================================== entradas invalidas

class TestEntradasInvalidas:
    @pytest.mark.parametrize("campo", [
        [(100, 100), (300, 100), (300, 300), (250, 150)],                     # un punto adentro del triangulo de los otros: no es convexo
        [(0, 0), (1, 1), (2, 2), (3, 3)],                                      # colineales
        [(5, 5), (5, 5), (5, 5), (5, 5)],                                      # un punto
    ])
    def test_j_un_campo_que_no_es_un_cuadrilatero_convexo_no_mide(self, campo):
        s = _sint("B", 0.4)
        p = piso(s.pelicula, campo)
        assert p.estado == _pel().MOTIVO_CAMPO_INVALIDO and p.region is None and all(c.mediana is None for c in p.capas.values())

    @pytest.mark.parametrize("campo", [[(1, 2), (3, 4), (5, 6)], [(1, 2)] * 5, [[1, 2, 3]] * 4, "no es un campo", None])
    def test_j_un_campo_con_la_forma_equivocada_es_un_error_de_quien_llama(self, campo):
        s = _sint("B", 0.4)
        with pytest.raises((ValueError, TypeError)):
            piso(s.pelicula, campo)

    def test_j_un_campo_con_nan_o_infinito_no_mide_ni_lanza(self):
        s = _sint("B", 0.4)
        malo = list(s.campo)
        malo[2] = (float("nan"), malo[2][1])
        assert piso(s.pelicula, malo).estado == _pel().MOTIVO_CAMPO_INVALIDO
        malo[2] = (float("inf"), 5.0)
        assert piso(s.pelicula, malo).estado == _pel().MOTIVO_CAMPO_INVALIDO

    def test_j_un_campo_enorme_o_diminuto_no_lanza(self):
        s = _sint("B", 0.4)
        c = np.array(s.campo)
        centro = c.mean(axis=0)
        for escala in (0.001, 50.0):
            p = piso(s.pelicula, [tuple(centro + (q - centro) * escala) for q in c])
            assert p.estado.startswith(("ok", "no medible"))

    def test_j_una_pelicula_pequena_no_lanza(self):
        pequena = _a_pelicula(np.full((40, 30, 3), 120, np.uint8))
        p = piso(pequena, [(5, 5), (25, 5), (25, 35), (5, 35)])
        assert p.estado.startswith("no medible") and all(c.mediana is None for c in p.capas.values())


# ====================================================================================================================== las peliculas reales

class TestLasPeliculasReales:
    @pytest.mark.parametrize("clave", sorted(CLICS_REALES))
    def test_l_las_diez_peliculas_reales_dan_un_piso_plausible_y_dicen_de_donde_salio(self, clave):
        pel = _real(clave)
        p = piso(pel, CLICS_REALES[clave])
        assert p.estado == "ok", p.estado
        assert all(c.estado == "ok" for c in p.capas.values()), {k: c.estado for k, c in p.capas.items()}
        m = {c: p.capas[c].mediana for c in CAPAS_DEL_PISO}
        assert 60 <= m["R"] <= 130 and 140 <= m["G"] <= 195 and 70 <= m["B"] <= 100, m          # la pelicula de fuera del campo (medida: R 73-111, G 154-180, B 81-86)
        assert 6.0 <= p.region.distancia_media_mm <= 14.0 and p.region.n >= 50000
        for c in "RGB":
            assert p.capas[c].contraste > 30, f"{clave} {c}: contraste con la meseta {p.capas[c].contraste}"
            assert p.capas[c].iqr < 30

    @pytest.mark.parametrize("clave", sorted(CLICS_REALES))
    def test_l_en_las_diez_reales_los_pixeles_del_piso_que_parecen_fondo_son_menos_del_1_por_ciento(self, clave):
        """La regla (7) no puede rechazar una pelicula real: en las diez, la fraccion de pixeles del piso cuya capa mas oscura llega a 170 (recalculada AQUI desde la mascara de la region) es de 0 a 0.6 %
        (motas claras sueltas dentro de la pelicula, 3 a 17 por pelicula), 17 veces menos que el 10 % con que la regla rechaza. Nace verde a proposito: es el control de que la regla no sobra; su rojo es
        la mutacion «el maximo de las tres capas en lugar de la mas oscura» (RV21), que rechaza las diez."""
        pel = _real(clave)
        p = piso(pel, CLICS_REALES[clave])
        assert p.estado == "ok", f"{clave}: la regla (7) o el piso rechazaron una pelicula real: {p.estado}"
        f = _fraccion_como_fondo(p, pel)
        assert f < 0.01, f"{clave}: el {100 * f:.2f} % de los pixeles del piso parece fondo (el maximo medido es 0.60 %)"

    @pytest.mark.parametrize("a,b,tolerancia", [
        ("ML0", "EPSON027", 2.0), ("EPSON001_JPG", "EPSON001_TIF", 2.0), ("EPSON007", "EPSON008_TIF", 3.0), ("EPSON007", "EPSON030", 3.0)])
    def test_l_la_misma_pelicula_en_dos_archivos_da_el_mismo_piso(self, a, b, tolerancia):
        pa, pb = piso(_real(a), CLICS_REALES[a]), piso(_real(b), CLICS_REALES[b])
        for c in CAPAS_DEL_PISO:
            assert abs(pa.capas[c].mediana - pb.capas[c].mediana) <= tolerancia, f"{a} contra {b}, {c}: {pa.capas[c].mediana} y {pb.capas[c].mediana}"


# ====================================================================================================================== estructura

def _fuente(ruta):
    texto = (RAIZ / ruta).read_text(encoding="utf-8")
    return texto, ast.parse(texto)


class TestEstructura:
    def test_m_una_sola_definicion_del_piso_en_todo_el_arbol_de_produccion(self):
        definiciones = []
        for ruta in RAIZ.rglob("*.py"):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in {"build", "dist", "tests", "__pycache__"} or any(p.startswith(".") for p in partes):
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            definiciones += [(str(ruta.relative_to(RAIZ)).replace(os.sep, "/"), n.name) for n in ast.walk(arbol)
                             if isinstance(n, ast.FunctionDef) and n.name == "piso_de_pelicula"]
        assert definiciones == [("analisisImagenes/pelicula.py", "piso_de_pelicula")], definiciones

    def test_m_el_motor_de_braqui_no_usa_el_piso(self):
        texto, _ = _fuente("analisisImagenes/posicion_inicial_braqui.py")
        assert "piso_de_pelicula" not in texto, "el motor de braqui mide sin piso (B.3 lo fija): no debe usar esta funcion"

    def test_m_pelicula_py_sigue_sin_qt_ni_base_de_datos(self):
        _, arbol = _fuente("analisisImagenes/pelicula.py")
        importados = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                importados |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                importados.add(n.module.split(".")[0])
        assert not importados & {"PyQt5", "sqlite3", "services", "data", "ui", "models"}, importados

    def test_m_la_funcion_no_calcula_la_escala_por_su_cuenta(self):
        _, arbol = _fuente("analisisImagenes/pelicula.py")
        funcion = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "piso_de_pelicula")
        constantes = [n.value for n in ast.walk(funcion) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
        assert 25.4 not in constantes, "la escala (mm por pixel) sale de `escala_mm`, la unica definicion"
        llamadas = {n.func.id for n in ast.walk(funcion) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "escala_mm" in llamadas

    def test_m_los_valores_de_los_parametros_viven_solo_en_su_diccionario(self):
        """Cuatro de los valores del plan son bastante distintivos para buscarlos como literales en las funciones del piso: ninguna los escribe. 235 (`umbral_fondo`) y 2000 (`pixeles_minimos`);
        y los de la regla (7): 170 (`umbral_como_fondo`, el nivel) y 0.10 (`fraccion_como_fondo`). Un literal escrito en la funcion ignoraria el parametro que se guarda con cada analisis."""
        _, arbol = _fuente("analisisImagenes/pelicula.py")
        del_piso = [n for n in arbol.body if isinstance(n, ast.FunctionDef) and (n.name == "piso_de_pelicula" or n.name.startswith("_piso") or n.name.startswith("_region"))]
        assert del_piso and any(n.name == "piso_de_pelicula" for n in del_piso)
        for n in del_piso:
            for c in ast.walk(n):
                if isinstance(c, ast.Constant) and not isinstance(c.value, bool) and isinstance(c.value, (int, float)):
                    assert c.value not in (235, 2000, 170, 0.10), f"{n.name} escribe el literal {c.value}: debe salir de los parametros"


# ====================================================================================================================== memoria

class TestLaMemoria:
    def test_n_una_pagina_completa_no_pide_mas_de_lo_que_pide_leerla_y_pedir_sus_capas(self):
        """6600 x 5100 en 8 bits: leida ocupa 135 MB; sus cuatro planos en flotante, 540 MB que C.2 va a necesitar de todos modos; el piso suma mascaras y el vecindario
        de la pelicula, no una copia por capa. Se mide con tracemalloc (cada arreglo de numpy y de OpenCV)."""
        pel = _real("EPSON027")
        for c in ("R", "G", "B", "gris"):
            getattr(pel, c)                                # los planos ya existen (los pide C.2): se mide lo que el PISO agrega
        pel.validos
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            p = piso(pel, CLICS_REALES["EPSON027"])
            pico = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert p.estado == "ok"
        assert pico < 350e6, f"el piso de una pagina completa pidio {pico / 1e6:.0f} MB sobre las capas (medido: 176 MB; copiar una capa son 135 MB mas)"
