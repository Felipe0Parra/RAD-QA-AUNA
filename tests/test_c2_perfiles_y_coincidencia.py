"""C.2 (PLAN_ANALISIS_PELICULAS_08-10.md): el MOTOR MENSUAL (2/3) -- los perfiles por capa, el FWHM, la coincidencia por lado, los tres centros y la penumbra
(`analisisImagenes/placa_mensual.py`, version PM-1; se AGREGA al modulo de C.1, cuyas funciones no cambian).

CAUSA (R3: N1, N3-N9; A1-A4). El cuaderno del fisico toma el piso de UN pixel de la pagina (el fondo del escaner: +15 / +17 mm de FWHM), ubica las ventanas con el centro de la imagen (`shape//2`),
busca el borde con `argmin`, usa UNA fila, rasteriza los bordes luminosos, usa las variables del ultimo barrido y da signos opuestos por lado; la app original mide solo el rojo recortado, sin piso y
sin girar. C.2 mide cada capa (R, G, B y el gris) por separado, con UNA base (el valor de pixel normalizado, (piso - v) / (piso - meseta), sin netOD), sobre la pelicula recortada y girada.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale de las funciones (el generador de PF.0 es INDEPENDIENTE del motor):
  (a) contra la verdad del generador: en el AZUL (la unica capa lineal en la dosis) el FWHM, la coincidencia por lado y los tres centros caen donde dice el generador (piso virgen: el modo «virgen»
      de A.3 con la virgen sintetica) y, con el piso de las esquinas (el modo automatico), donde predice el generador PARA ESE PISO (la pelicula de fuera del campo recibe la cola de dispersion y no es
      virgen, R7: el piso queda 1 nivel por debajo y el FWHM del azul 0.13 mm). En las demas capas la verdad es la respuesta del propio generador en esa capa, nunca la dosis. Los +-0.15 mm contra la
      dosis valen con la MESETA PLANA: con la cupula de las peliculas reales el 50 % de la media de la zona central no es el 50 % de la dosis del centro (C2-D15, `TestUnaMesetaQueNoEsPlana`).
  (b) RECORTE CONTRA PAGINA, pelicula DESCENTRADA en la pagina y GIRO de 1 grado: la misma pelicula da lo mismo (<= 0.05 mm sin ruido; el cuaderno pierde +15 / +17 mm con la pagina, el `shape//2` con
      la descentrada y el piso con el giro).
  (c) el rojo recortado por el escaner (meseta en 0) se mide igual y sin ninguna marca: cada capa por separado (PD3).
  (d) SIGNOS: la radiacion corrida +0.6 mm a la derecha da derecho +0.6, izquierdo -0.6 y centro +0.6 (positivo hacia afuera en los cuatro lados).
  (e) la exclusion central sigue al RETICULO REFINADO (sintetica con el reticulo corrido 4 mm), el borde se busca DESDE LA MESETA HACIA AFUERA (un cruce lejano no lo confunde), con interpolacion
      lineal subpixel, y el piso es el de A.2/A.3 (no el minimo del perfil).
  (f) los tres desplazamientos de centro, contra el MISMO cruce de diagonales: radiacion - retículo es exactamente la suma de radiacion - luz y luz - retículo.
  (g) placas reales: ML0 y EPSON027 (la misma pelicula), EPSON001 jpg y TIF, EPSON007 y EPSON008.
Y las garantias de estructura: `analizar` llama UNA vez a `piso_de_pelicula` y todas las capas usan ese `Piso`; `valores_medidos` es la UNICA definicion de lo que se guarda; el resultado trae lo
que C.3 necesita sin retener la pagina; cada parametro nuevo vive con nombre, unidad y motivo; sin simbolos de correcto o incorrecto (DA-18).

Rojo contra HEAD (3f54aef): HEAD no tiene `girar`, `perfil_central`, `medir_perfil`, `bordes_luz`, `coincidencia`, `analizar` ni `valores_medidos`: todas las pruebas caen por API ausente (el archivo se
colecciona: cada prueba importa el modulo por dentro). El rojo SUSTANTIVO esta en `c2_rojo_head.py` del anexo (la replica del cuaderno puesta en lugar de `analizar`) y las mutaciones en `c2_mutaciones.py`.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import dataclasses
import gc
import hashlib
import importlib
import json
import math
import re
import subprocess
import sys
import weakref
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.special import erf

import _corpus
import _placa_mensual_sintetica as gen

RAIZ = Path(__file__).resolve().parent.parent
MODULO = RAIZ / "analisisImagenes" / "placa_mensual.py"
TAM = 25.4 / 600.0                                      # mm por pixel: la escala del procedimiento (600 dpi)
CAPAS = ("R", "G", "B", "gris")
EJES = ("crossplane", "inplane")
LADOS = ("izquierdo", "derecho", "superior", "inferior")
ORDEN_DE_LOS_PUNTOS = ("UL", "UR", "DR", "DL", "C")
SIGMA = gen.CALIB["sigma_mm"]                           # la penumbra del generador: 2.3 mm
PESOS_DEL_GRIS = {"B": 0.114, "G": 0.587, "R": 0.299}  # cv2.COLOR_BGR2GRAY


def _pm():
    """El modulo, importado POR PRUEBA: en HEAD (sin lo de C.2) el archivo se colecciona y cada prueba cae con su error."""
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _P(**cambios):
    return {**_pm().VALORES_DE_LA_GEOMETRIA, **cambios}


def _real(clave):
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"HI-0: la pelicula real {clave} no esta (ImagenesDeReferencia/PlacasHistoricas)")
    return ruta


# ======================================================================================================================================= los ORACULOS
# Independientes del motor: usan solo el generador de PF.0 (`gen.Campo`, su respuesta por capa) y formulas cerradas. Nada de lo que sigue importa `analisisImagenes`.
def nivel_de_capa(calib, capa, D):
    """El nivel crudo SIN ruido que el generador da a una dosis relativa D en `capa` (B, G, R) o en el gris (la combinacion BGR2GRAY de las tres)."""
    if capa == "gris":
        return sum(peso * nivel_de_capa(calib, c, D) for c, peso in PESOS_DEL_GRIS.items())
    i = gen.INDICE_CAPA[capa]
    virgen, meseta = calib["virgen_bgr"][i], calib["meseta_bgr"][i]
    return virgen - (virgen - meseta) * gen._g(D, calib["k_bgr"][i])


def bordes_esperados(campo, calib, capa, eje, linea_mm, piso, meseta=None, fraccion=0.5):
    """(menor, mayor) en mm del sistema de la pelicula (origen: centro del campo de radiacion) donde el nivel de `capa` cruza `piso - fraccion * (piso - meseta)` a lo largo de la fila v = `linea_mm`
    (crossplane) o de la columna u = `linea_mm` (inplane). `meseta`: el nivel en el eje (dosis 1) si no se da. Con fraccion 0.5 es la altura media; 0.8 y 0.2 son los de la penumbra."""
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


def meseta_media_esperada(verdad, capa, eje, calib=None, fraccion=0.8, excepcion_mm=3.8):
    """El nivel de `capa` que el plan llama la meseta (R9, paso 7): el promedio de la zona central, calculado de la respuesta SIN ruido del generador (no del motor): sobre [centro - e, centro + e], con e =
    `fraccion` / 2 x la distancia entre los dos bordes luminosos de esa linea, sin los +-`excepcion_mm` alrededor del reticulo. Con la meseta plana es el nivel del centro del campo; con una cupula, no."""
    calib = gen.CALIB if calib is None else calib
    lcx, lcy = verdad.centro_luz
    luz = verdad.bordes_luz
    rx, ry = verdad.reticulo_menos_luz
    if eje == "crossplane":
        centro, ancho, reticulo, linea = lcx, luz["R"] - luz["L"], lcx + rx, lcy
    else:
        centro, ancho, reticulo, linea = lcy, luz["B"] - luz["T"], lcy + ry, lcx
    s = np.arange(centro - fraccion / 2 * ancho, centro + fraccion / 2 * ancho, 0.005)
    s = s[np.abs(s - reticulo) > excepcion_mm]
    dosis = verdad.campo.dosis(s, linea) if eje == "crossplane" else verdad.campo.dosis(linea, s)
    return float(np.mean(nivel_de_capa(calib, capa, dosis)))


def esperado(verdad, capa, piso, calib=None, con_meseta_media=False):
    """Lo que PREDICE el generador para `capa` si el piso es `piso`: el FWHM de los dos ejes, la coincidencia por lado (positiva hacia afuera) y radiacion - luz, todo sobre las lineas que pasan por el
    cruce de diagonales de las marcas luminosas (el centro del campo luminoso del generador). El 50 % se toma entre el piso y el nivel del CENTRO del campo (la dosis) o, con `con_meseta_media`, entre el
    piso y la meseta como la define el plan (el promedio de la zona central: `meseta_media_esperada`); con la meseta plana son lo mismo."""
    calib = gen.CALIB if calib is None else calib
    campo = verdad.campo
    lcx, lcy = verdad.centro_luz
    bx = bordes_esperados(campo, calib, capa, "crossplane", lcy, piso, meseta=meseta_media_esperada(verdad, capa, "crossplane", calib) if con_meseta_media else None)
    by = bordes_esperados(campo, calib, capa, "inplane", lcx, piso, meseta=meseta_media_esperada(verdad, capa, "inplane", calib) if con_meseta_media else None)
    luz = verdad.bordes_luz
    return {
        "fwhm_crossplane": bx[1] - bx[0], "fwhm_inplane": by[1] - by[0],
        "coincidencia": {"izquierdo": luz["L"] - bx[0], "derecho": bx[1] - luz["R"], "superior": luz["T"] - by[0], "inferior": by[1] - luz["B"]},
        "radiacion_menos_luz": ((bx[0] + bx[1]) / 2 - lcx, (by[0] + by[1]) / 2 - lcy),
    }


def penumbras_esperadas(verdad, capa, piso, calib=None):
    """La penumbra 80-20 % del generador en `capa` con ese piso: {lado: mm}."""
    calib = gen.CALIB if calib is None else calib
    campo = verdad.campo
    lcx, lcy = verdad.centro_luz
    salida = {}
    for eje, linea, lados in (("crossplane", lcy, ("izquierdo", "derecho")), ("inplane", lcx, ("superior", "inferior"))):
        b80 = bordes_esperados(campo, calib, capa, eje, linea, piso, fraccion=0.8)
        b20 = bordes_esperados(campo, calib, capa, eje, linea, piso, fraccion=0.2)
        salida[lados[0]] = b80[0] - b20[0]
        salida[lados[1]] = b20[1] - b80[1]
    return salida


# ======================================================================================================================================= las peliculas
def puntos_exactos(verdad):
    """Los centros verdaderos de las marcas en pixeles (floats): UL, UR, DR, DL y el reticulo."""
    return [verdad.marcas_px[k] for k in ORDEN_DE_LOS_PUNTOS]


def sintetica(formato="tiff", variante="A", theta=0.0, seed=1, **opciones):
    """(verdad, Pelicula) de la pelicula sintetica de PF.0 pasada por el lector de A.1 (el camino real de un archivo)."""
    placa = gen.generar(formato, variante=variante, theta_deg=theta, seed=seed, **opciones)
    pelicula = _pel().leer_pelicula(placa.datos)
    return placa.verdad, pelicula


def virgen_sintetica(P=None):
    """La referencia de una pelicula virgen sintetica (meseta = virgen, sin dosis ni tinta, fondo de escaner puro) medida con `piso_de_pelicula_virgen` de A.3."""
    calib = dict(gen.CALIB, meseta_bgr=gen.CALIB["virgen_bgr"], fondo_escaner=255.0)
    imagen, _ = gen.generar_arreglo(variante="A", theta_deg=0.0, bits=8, dpi=600, tinta=False, calib=calib)
    imagen = np.array(imagen)
    imagen[imagen.min(axis=2) >= 235] = 255
    return _pel().piso_de_pelicula_virgen(gen.codificar(imagen, "tiff", 600), _P() if P is None else P, "virgen_sintetica.tif", fecha_calculo="2026-10-17")


class Resumen:
    """Los numeros de un resultado, copiados (para soltar el resultado, que pesa ~125 MB, apenas se mide)."""

    def __init__(self, res):
        self.estado = res.estado
        self.capas = {}
        for c in CAPAS:
            m = res.capas[c]
            self.capas[c] = {
                "estado": m.estado, "piso": m.piso,
                "fwhm_crossplane": m.crossplane.fwhm_mm, "fwhm_inplane": m.inplane.fwhm_mm,
                "coincidencia": dict(m.coincidencia_mm), "radiacion_menos_luz": tuple(m.radiacion_menos_luz_mm),
                "radiacion_menos_reticulo": tuple(m.radiacion_menos_reticulo_mm),
                "meseta": (m.crossplane.meseta, m.inplane.meseta),
                "penumbras": {"crossplane": m.crossplane.penumbras_mm, "inplane": m.inplane.penumbras_mm},
            }
        self.luz_menos_reticulo_mm = tuple(res.luz_menos_reticulo_mm) if res.luz_menos_reticulo_mm is not None else None
        self.angulo = res.geometria.angulo_grados if res.geometria is not None else None


def medir_pelicula(pelicula, puntos, P=None, **opciones):
    return _pm().analizar(pelicula, puntos, _P() if P is None else P, **opciones)


# ======================================================================================================================================= los perfiles a mano
def perfil_erf(*, ancho_mm=100.0, sigma_mm=SIGMA, piso=170.0, meseta=32.0, n=3400, centro=1700.0, corrimiento_mm=0.0, desde=0, eje="crossplane", capa="G",
               ruido=0.0, semilla=0, modificar=None):
    """Un perfil de dosis ideal (la diferencia de dos erf de ancho `ancho_mm` y penumbra `sigma_mm`) en niveles de pelicula: `piso - (piso - meseta) * D`. El cruce de diagonales esta en `centro` y la
    radiacion corrida `corrimiento_mm` hacia la derecha. `modificar(x, v)` cambia el perfil. Devuelve (PerfilCentral, centro). Sin ruido, el borde al 50 % esta EXACTAMENTE en +-ancho/2 + corrimiento."""
    pm = _pm()
    x = desde + np.arange(n, dtype=float)
    u = (x - centro) * TAM - corrimiento_mm
    D = 0.5 * (erf((u + ancho_mm / 2) / (math.sqrt(2) * sigma_mm)) - erf((u - ancho_mm / 2) / (math.sqrt(2) * sigma_mm)))
    v = piso - (piso - meseta) * D
    if ruido:
        v = v + np.random.default_rng(semilla).normal(0.0, ruido, n)
    if modificar is not None:
        v = modificar(x, v)
    perfil = pm.PerfilCentral(capa=capa, eje=eje, banda=0, valores=np.asarray(v, dtype=np.float64), desde_px=desde, filas_px=(0.0, 24.0), n_filas=24, tam_mm=TAM)
    return perfil, float(centro)


def medir(perfil, centro, *, piso=170.0, luz_mm=99.6, reticulo_mm=0.0, P=None, luz=None, reticulo_px="auto"):
    """`medir_perfil` con los bordes luminosos de un campo de `luz_mm` centrado en `centro` y el reticulo a `reticulo_mm` del centro."""
    pm = _pm()
    luz = (centro - luz_mm / 2 / TAM, centro + luz_mm / 2 / TAM) if luz is None else luz
    ret = centro + reticulo_mm / TAM if reticulo_px == "auto" else reticulo_px
    return pm.medir_perfil(perfil, centro, piso, pm.BASE_VALOR_DE_PIXEL, _P() if P is None else P, luz, ret)


# ======================================================================================================================================= medir_perfil: la exactitud
class TestMedirPerfilContraUnaVerdadCerrada:
    """El perfil ideal tiene el borde al 50 % EXACTAMENTE en +-ancho/2 + corrimiento: el FWHM, los bordes, el centro y la penumbra 80-20 (= 2 x 0.8416 sigma) salen sin tolerancia de ruido."""

    @pytest.mark.parametrize("corrimiento_mm", [0.0, 0.6, -0.6, 2.5])
    def test_el_fwhm_el_centro_y_los_bordes_son_los_del_perfil_ideal(self, corrimiento_mm):
        perfil, c = perfil_erf(corrimiento_mm=corrimiento_mm)
        m = medir(perfil, c)
        assert m.estado == "ok" and m.ok
        assert m.fwhm_mm == pytest.approx(100.0, abs=0.003)
        assert m.centro_rad_px == pytest.approx(c + corrimiento_mm / TAM, abs=0.1)
        assert m.bordes_rad_px[0] == pytest.approx(c + (corrimiento_mm - 50.0) / TAM, abs=0.1)
        assert m.bordes_rad_px[1] == pytest.approx(c + (corrimiento_mm + 50.0) / TAM, abs=0.1)

    @pytest.mark.parametrize("fraccion_de_pixel", [0.0, 0.25, 0.5, 0.75])
    def test_la_interpolacion_lineal_subpixel_da_el_borde_entre_dos_muestras(self, fraccion_de_pixel):
        """Sin interpolar, el borde saldria en un entero (error hasta 1 pixel = 0.042 mm); con ella, en el valor correcto aunque caiga a mitad de pixel."""
        perfil, c = perfil_erf(corrimiento_mm=fraccion_de_pixel * TAM)
        m = medir(perfil, c)
        assert m.bordes_rad_px[0] == pytest.approx(c + (fraccion_de_pixel * TAM - 50.0) / TAM, abs=0.02)
        assert m.bordes_rad_px[1] == pytest.approx(c + (fraccion_de_pixel * TAM + 50.0) / TAM, abs=0.02)
        assert m.fwhm_mm == pytest.approx(100.0, abs=0.003)

    def test_la_meseta_es_el_nivel_medio_de_la_zona_central_y_la_altura_media_esta_a_mitad_de_camino(self):
        perfil, c = perfil_erf(piso=170.0, meseta=32.0)
        m = medir(perfil, c)
        assert m.meseta == pytest.approx(32.0, abs=0.01) and m.piso == 170.0
        assert m.altura_media == pytest.approx(101.0, abs=0.01)                    # (piso + meseta) / 2: n = (piso - v) / (piso - meseta) = 0.5
        assert m.nivel_penumbra_alta == pytest.approx(170.0 - 0.8 * 138.0, abs=0.02) and m.nivel_penumbra_baja == pytest.approx(170.0 - 0.2 * 138.0, abs=0.02)

    def test_la_penumbra_80_20_de_cada_lado_es_dos_veces_0_8416_sigma(self):
        perfil, c = perfil_erf()
        m = medir(perfil, c)
        esperada = 2 * 0.8416212335729143 * SIGMA                                  # el 80 % esta en +0.8416 sigma hacia adentro y el 20 % en 0.8416 hacia afuera
        assert m.penumbras_mm[0] == pytest.approx(esperada, abs=0.01) and m.penumbras_mm[1] == pytest.approx(esperada, abs=0.01)
        assert m.avisos == ()

    def test_el_resultado_no_depende_de_donde_este_el_cruce_en_el_arreglo_ni_de_donde_empiece_el_perfil(self):
        """El cuaderno ubica sus ventanas en la mitad del arreglo (`shape//2`): con el cruce a 1200 de 3400 la zona caeria fuera de la meseta."""
        a, ca = perfil_erf(centro=1700.0)
        b, cb = perfil_erf(centro=1200.0, n=3400)
        c_, cc = perfil_erf(centro=1700.0, desde=-250, n=3400)
        for perfil, centro in ((a, ca), (b, cb), (c_, cc)):
            m = medir(perfil, centro)
            assert m.ok, m.estado
            assert m.fwhm_mm == pytest.approx(100.0, abs=0.003)
            assert m.zona_px[0] == pytest.approx(centro - 0.4 * 99.6 / TAM, abs=0.6) and m.zona_px[1] == pytest.approx(centro + 0.4 * 99.6 / TAM, abs=0.6)
            assert m.bordes_rad_px == pytest.approx((centro - 50.0 / TAM, centro + 50.0 / TAM), abs=0.1) and m.centro_rad_px == pytest.approx(centro, abs=0.1), "las posiciones son las del marco girado, con el origen del perfil"

    def test_la_zona_central_se_centra_en_el_cruce_de_diagonales_aunque_los_bordes_luminosos_de_la_linea_no_sean_simetricos_alrededor_de_el(self):
        """El plan: la zona va «alrededor del cruce de diagonales», con e = fraccion / 2 x la distancia entre los dos bordes luminosos de esa linea. En una pelicula real el cuadrilatero luminoso no es un
        paralelogramo (ML0: lados de 98.9 a 99.7 mm): los dos bordes de la linea no quedan a la misma distancia del cruce, y la zona NO se centra en el punto medio de ellos (con 50 mm a un lado y 54 al
        otro ese punto medio esta a 2 mm del cruce). Hasta ahora todas las pruebas ponian los bordes luminosos simetricos alrededor del centro: una zona centrada en su punto medio pasaba todas."""
        perfil, c = perfil_erf()
        luz = (c - 50.0 / TAM, c + 54.0 / TAM)
        m = medir(perfil, c, luz=luz)
        extremo = 0.4 * (luz[1] - luz[0])
        assert m.ok, m.estado
        assert m.zona_px == pytest.approx((c - extremo, c + extremo), abs=1e-6)
        assert sum(m.zona_px) / 2 == pytest.approx(c, abs=1e-6), "la zona esta centrada en el cruce de diagonales, no en el punto medio de los bordes luminosos"
        assert m.bordes_luz_px == pytest.approx(luz) and (luz[0] + luz[1]) / 2 - c == pytest.approx(2.0 / TAM), "(la prueba tiene bordes luminosos asimetricos de verdad)"

    def test_con_ruido_del_escaner_el_fwhm_se_mantiene_dentro_de_la_incertidumbre(self):
        errores = []
        for semilla in range(12):
            perfil, c = perfil_erf(ruido=0.3, semilla=semilla)                    # una banda de 24 filas con sigma 1.5 por pixel
            errores.append(medir(perfil, c).fwhm_mm - 100.0)
        assert abs(np.mean(errores)) < 0.04 and max(abs(e) for e in errores) < 0.12, errores


# ======================================================================================================================================= medir_perfil: los defectos del cuaderno
class TestMedirPerfilContraLosDefectosDelCuaderno:
    def test_el_borde_se_busca_desde_la_meseta_hacia_afuera_y_un_cruce_lejano_no_lo_confunde(self):
        """El cuaderno busca el `argmin` de |perfil - HM| en medio perfil: una mancha oscura LEJOS del campo que baje a la altura media (aqui hasta 101.005, a 0.005 de ella) le gana al borde
        verdadero. La busqueda desde la meseta hacia afuera se detiene en el primer cruce, que es el borde."""
        def con_manchas(x, v):
            u = (x - 1700.0) * TAM
            for lado in (-1, 1):
                v = np.where(np.abs(u - lado * 59.0) < 1.0, 101.005, v)
            return v
        perfil, c = perfil_erf(modificar=con_manchas)
        m = medir(perfil, c)
        assert m.ok and m.fwhm_mm == pytest.approx(100.0, abs=0.003)

    @pytest.mark.parametrize("piso_usado", [170.0, 180.0, 160.0])
    def test_el_piso_es_el_que_se_le_da_y_no_el_extremo_del_perfil(self, piso_usado):
        """El perfil de la prueba llega a 180 en un rincon lejano (una mota clara) y a 160 en otro (el fleco del corte): si el piso fuera el maximo o el minimo del perfil, el FWHM saldria de 100. Con
        el piso que se le da, la altura media es (piso + meseta) / 2 y el borde cae donde la dosis vale (170 - HM) / 138; el valor esperado sale de la erf inversa, sin tocar el modulo."""
        from scipy.special import erfinv

        def con_extremos(x, v):
            u = (x - 1700.0) * TAM
            v = np.where(np.abs(u - 66.0) < 0.5, 180.0, v)
            return np.where(np.abs(u + 66.0) < 0.5, 160.0, v)
        perfil, c = perfil_erf(modificar=con_extremos)
        m = medir(perfil, c, piso=piso_usado)
        assert m.ok, m.estado
        D = (170.0 - (piso_usado + 32.0) / 2.0) / 138.0                                  # la dosis a la que el perfil cruza la altura media
        semiancho = 50.0 + SIGMA * math.sqrt(2) * float(erfinv(1.0 - 2.0 * D))             # D(u) = (1 + erf((w/2 - u) / (sigma sqrt2))) / 2  ->  u = w/2 + sigma sqrt2 erfinv(1 - 2D)
        assert m.fwhm_mm == pytest.approx(2 * semiancho, abs=0.005)
        assert m.altura_media == pytest.approx((piso_usado + 32.0) / 2.0, abs=0.01)

    def test_la_marca_central_no_entra_en_la_meseta_y_la_exclusion_sigue_al_reticulo_refinado_no_al_cruce(self):
        """Una marca clara de 3.4 mm de ancho (+60 niveles, menos que la altura media: no la rechaza la regla de la tinta) a 4 mm del cruce. Con el reticulo refinado ahi, la exclusion de 3.8 mm
        alrededor suyo la deja fuera y la meseta es 32.0; con la exclusion centrada en el cruce (el cuaderno) solo queda fuera lo que cae a menos de 3.8 mm de el y de la marca entran 1.9 mm de 72.08
        (la zona de 79.68 mm menos los 7.6 de la exclusion): la meseta sube a 32 + 60 * 1.9 / 72.08 = 33.58; sin exclusion entra toda, 3.4 mm de 79.68, y sube a 32 + 60 * 3.4 / 79.68 = 34.56."""
        def con_marca(x, v):
            u = (x - 1700.0) * TAM
            return np.where(np.abs(u - 4.0) < 1.7, v + 60.0, v)
        perfil, c = perfil_erf(modificar=con_marca)
        sigue_al_reticulo = medir(perfil, c, reticulo_mm=4.0)
        assert sigue_al_reticulo.ok and sigue_al_reticulo.meseta == pytest.approx(32.0, abs=0.05)
        assert sigue_al_reticulo.exclusion_px[0] == pytest.approx(c + (4.0 - 3.8) / TAM, abs=0.6) and sigue_al_reticulo.exclusion_px[1] == pytest.approx(c + (4.0 + 3.8) / TAM, abs=0.6)
        en_el_cruce = medir(perfil, c, reticulo_mm=0.0)
        sin_exclusion = medir(perfil, c, reticulo_px=None)
        assert en_el_cruce.meseta == pytest.approx(32.0 + 60.0 * 1.9 / 72.08, abs=0.1) and sin_exclusion.meseta == pytest.approx(32.0 + 60.0 * 3.4 / 79.68, abs=0.1)
        assert en_el_cruce.exclusion_px[0] == pytest.approx(c - 3.8 / TAM, abs=0.6) and sin_exclusion.exclusion_px is None

    def test_la_tinta_oscura_dentro_de_la_zona_se_rechaza_como_en_a2_si_baja_de_la_mediana_mas_que_delta_tinta(self):
        """A.2 llama tinta a lo que esta mas de `delta_tinta` (25 niveles) por debajo de la mediana. Una raya de -30 (de 1.5 mm, lejos del reticulo) no cuenta; una de -20 si."""
        def con_raya(profundidad):
            def f(x, v):
                u = (x - 1700.0) * TAM
                return np.where(np.abs(u - 12.0) < 0.75, v - profundidad, v)
            return f
        rechazada = medir(*perfil_erf(modificar=con_raya(30.0)))
        aceptada = medir(*perfil_erf(modificar=con_raya(20.0)))
        n_raya = int(round(1.5 / TAM))
        zona = 0.4 * 99.6 / TAM * 2 - 2 * 3.8 / TAM
        assert rechazada.meseta == pytest.approx(32.0, abs=0.02)
        assert aceptada.meseta == pytest.approx(32.0 - 20.0 * n_raya / zona, abs=0.05) and aceptada.meseta < 31.8
        assert rechazada.muestras_meseta < aceptada.muestras_meseta

    def test_una_mota_fina_en_la_meseta_no_mueve_el_borde_por_el_suavizado_de_medio_milimetro(self):
        """Dos muestras de +100 niveles (0.085 mm de mota, entre el borde de la zona central y el borde de radiacion): sin suavizar cruzan la altura media y el 'borde' queda ahi (en una pelicula
        real, EPSON007 azul inplane da 96.04 mm); con el suavizado de 0.5 mm la mota queda en +18, bajo la altura media, y el borde es el de siempre."""
        def con_mota(x, v):
            i = int(round(1700 - 44.0 / TAM))
            v = v.copy()
            v[i:i + 2] += 100.0
            return v
        perfil, c = perfil_erf(modificar=con_mota)
        m = medir(perfil, c)
        assert m.ok and m.fwhm_mm == pytest.approx(100.0, abs=0.01)
        sin_suavizar = medir(perfil, c, P=_P(suavizado_perfil_mm=0.0))
        assert not sin_suavizar.ok or abs(sin_suavizar.fwhm_mm - 100.0) > 3.0, "sin el suavizado la mota si cruza la altura media"

    def test_la_base_es_el_valor_de_pixel_normalizado_y_no_hay_otra(self):
        pm = _pm()
        perfil, c = perfil_erf()
        assert pm.BASE_VALOR_DE_PIXEL == "valor de píxel normalizado"
        with pytest.raises(ValueError):
            pm.medir_perfil(perfil, c, 170.0, "netOD", _P(), (c - 1000.0, c + 1000.0), c)
        n = pm.normalizar(pm.BASE_VALOR_DE_PIXEL, np.array([170.0, 101.0, 32.0, 200.0]), 170.0, 32.0)
        assert n == pytest.approx([0.0, 0.5, 1.0, -30.0 / 138.0])

    def test_los_valores_fijos_de_la_medida_son_los_del_plan_y_cada_uno_se_usa(self):
        v = _pm().VALORES_DE_LA_GEOMETRIA
        assert (v["banda_perfil_mm"], v["fraccion_meseta"], v["excepcion_centro_mm"]) == (1.0, 0.80, 3.8)
        assert (v["altura_media"], v["penumbra_alta"], v["penumbra_baja"]) == (0.5, 0.8, 0.2)

    def test_la_zona_central_es_la_fraccion_de_la_distancia_entre_los_bordes_luminosos_de_esa_linea(self):
        perfil, c = perfil_erf()
        for luz_mm in (80.0, 99.6, 120.0):
            m = medir(perfil, c, luz_mm=luz_mm, P=_P(fraccion_meseta=0.5))
            assert m.ok, m.estado
            assert m.zona_px[0] == pytest.approx(c - 0.25 * luz_mm / TAM, abs=0.6) and m.zona_px[1] == pytest.approx(c + 0.25 * luz_mm / TAM, abs=0.6)
            assert m.bordes_luz_px == pytest.approx((c - luz_mm / 2 / TAM, c + luz_mm / 2 / TAM))

    def test_un_campo_de_radiacion_mas_chico_que_la_zona_central_no_se_mide(self):
        perfil, c = perfil_erf(ancho_mm=60.0)
        m = medir(perfil, c)
        assert not m.ok and m.estado.startswith("no medible") and "campo de radiación" in m.estado and "altura media" in m.estado
        assert m.fwhm_mm is None and m.bordes_rad_px == (None, None)

    def test_una_mota_clara_y_ancha_dentro_de_la_zona_central_no_se_mide(self):
        """Una mota clara de 3 mm (+120 niveles: 152, mas clara que la altura media aun suavizada) sobre la zona central: la meseta saldria contaminada, asi que no se mide y se dice por que; una fina
        (la de EPSON007, de 0.085 mm) se absorbe con el suavizado y se mide (`test_una_mota_fina_en_la_meseta...`)."""
        def con_mota(x, v):
            u = (x - 1700.0) * TAM
            return np.where(np.abs(u - 20.0) < 1.5, v + 120.0, v)
        perfil, c = perfil_erf(modificar=con_mota)
        m = medir(perfil, c)
        assert not m.ok and m.estado.startswith("no medible") and "altura media" in m.estado and m.fwhm_mm is None

    def test_una_zona_central_fuera_de_la_pelicula_no_se_mide(self):
        def sin_pelicula(x, v):
            v = v.copy()
            v[int(1700 + 20.0 / TAM):] = np.nan
            return v
        perfil, c = perfil_erf(modificar=sin_pelicula)
        m = medir(perfil, c)
        assert not m.ok and m.estado.startswith("no medible") and "zona central" in m.estado

    def test_el_borde_que_no_se_alcanza_antes_del_fin_de_la_pelicula_no_se_inventa(self):
        """La pelicula termina a 45 mm del cruce, antes del borde de radiacion (a 50): el borde derecho no existe, el izquierdo si, y el FWHM no se da."""
        def termina(x, v):
            v = v.copy()
            v[int(1700 + 45.0 / TAM):] = np.nan
            return v
        perfil, c = perfil_erf(modificar=termina)
        m = medir(perfil, c)
        assert not m.ok and m.estado.startswith("no medible") and "derecho" in m.estado and "al 50 %" in m.estado
        assert m.bordes_rad_px[0] == pytest.approx(c - 50.0 / TAM, abs=0.1) and m.bordes_rad_px[1] is None and m.fwhm_mm is None and m.centro_rad_px is None

    def test_un_borde_cuya_vecindad_toca_un_hueco_sin_dato_no_se_inventa(self):
        """La pelicula termina 0.1 mm despues del borde de radiacion (a 50.1 mm del cruce): el cruce esta a 2 pixeles del hueco, dentro de la mitad de la ventana del suavizado (5 pixeles): el promedio de
        ahi no esta completo, asi que el borde derecho no se mide (nunca un cruce calculado con medias de menos muestras)."""
        def termina(x, v):
            v = v.copy()
            v[int(round(1700 + 50.1 / TAM)):] = np.nan
            return v
        perfil, c = perfil_erf(modificar=termina)
        m = medir(perfil, c)
        assert not m.ok and m.estado.startswith("no medible") and "derecho" in m.estado and m.bordes_rad_px[1] is None and m.bordes_rad_px[0] is not None
        sin_suavizar = medir(perfil, c, P=_P(suavizado_perfil_mm=0.0))
        assert sin_suavizar.ok and sin_suavizar.fwhm_mm == pytest.approx(100.0, abs=0.01), "sin suavizado el cruce esta antes del hueco y se mide: el hueco solo importa por la ventana"

    def test_la_penumbra_no_monotona_se_avisa_y_no_se_inventa(self):
        """La meseta se aclara hacia los extremos de la zona central (una planitud pesima): al salir de la zona el perfil ya esta bajo el 80 % de la meseta, el cruce del 80 % no existe y se avisa; el FWHM,
        que cruza el 50 % mas afuera, se mide, y la penumbra de los dos lados no se inventa."""
        def se_aclara(x, v):
            u = np.abs((x - 1700.0) * TAM)
            return v + 50.0 * np.clip((u - 20.0) / 19.8, 0.0, 1.0) ** 2
        perfil, c = perfil_erf(modificar=se_aclara)
        m = medir(perfil, c)
        assert m.ok, m.estado
        assert m.penumbras_mm == (None, None) and m.avisos == (_pm().AVISO_PENUMBRA_NO_MONOTONA.format(alto=80, medio=50, bajo=20),) * 2
        assert m.avisos[0] == "no monótona: el perfil no cruza el 80 %, el 50 % y el 20 % en ese orden"
        assert m.fwhm_mm is not None

    def test_la_penumbra_incompleta_se_avisa_con_su_frase_y_no_se_inventa(self):
        """La pelicula termina a 51.2 mm: el 80 % y el 50 % se alcanzan, el 20 % (a 50 + 1.94 mm) no. Aviso exacto del plan; el FWHM y el otro lado no se pierden."""
        def termina(x, v):
            v = v.copy()
            v[int(1700 + 51.2 / TAM):] = np.nan
            return v
        perfil, c = perfil_erf(modificar=termina)
        m = medir(perfil, c)
        assert m.ok and m.fwhm_mm == pytest.approx(100.0, abs=0.01)
        assert m.penumbras_mm[1] is None and m.penumbras_mm[0] == pytest.approx(2 * 0.8416 * SIGMA, abs=0.02)
        assert "incompleta: el perfil llega al borde de la película antes del 20 %" in m.avisos

    @pytest.mark.parametrize("piso", [None, float("nan"), 40.0, 32.0, 20.0])
    def test_sin_un_piso_mas_claro_que_la_meseta_en_el_contraste_minimo_no_se_mide(self, piso):
        perfil, c = perfil_erf()
        m = medir(perfil, c, piso=piso)
        assert not m.ok and m.estado.startswith("no medible") and m.fwhm_mm is None

    def test_sin_bordes_luminosos_en_esa_linea_no_se_mide(self):
        perfil, c = perfil_erf()
        pm = _pm()
        m = pm.medir_perfil(perfil, c, 170.0, pm.BASE_VALOR_DE_PIXEL, _P(), None, c)
        assert not m.ok and m.estado.startswith("no medible")
        for sin_ancho in ((c, c), (c + 100.0, c - 100.0)):
            m = pm.medir_perfil(perfil, c, 170.0, pm.BASE_VALOR_DE_PIXEL, _P(), sin_ancho, c)
            assert not m.ok and m.estado.startswith("no medible") and "no tienen ancho" in m.estado, sin_ancho

    def test_una_zona_central_de_pocas_muestras_no_se_mide(self):
        """Con un campo luminoso de 10 mm la zona central (el 80 %) es de 8 mm = 190 muestras, menos de `muestras_minimas_de_la_meseta` (200): una media de tan pocas muestras no distingue una mota de un
        nivel y se prefiere decir «no medible». Con 11 mm son 208 y se mide (sin exclusion del reticulo, para contar la zona entera)."""
        perfil, c = perfil_erf()
        poca = medir(perfil, c, luz_mm=10.0, reticulo_px=None)
        assert not poca.ok and poca.estado.startswith("no medible") and "menos de 200 muestras" in poca.estado and poca.fwhm_mm is None and poca.muestras_meseta == 0
        suficiente = medir(perfil, c, luz_mm=11.0, reticulo_px=None)
        assert suficiente.ok and suficiente.muestras_meseta >= 200, suficiente.estado
        un_minimo_mayor = medir(perfil, c, luz_mm=11.0, reticulo_px=None, P=_P(muestras_minimas_de_la_meseta=300))
        assert not un_minimo_mayor.ok and "menos de 300 muestras" in un_minimo_mayor.estado, "el minimo es el parametro, no un 200 escrito en la funcion"

    def test_la_zona_central_incluye_sus_dos_extremos_y_el_minimo_de_muestras_es_el_del_parametro(self):
        """Zona de 100 pixeles a cada lado del cruce, de 1600 a 1800 con los dos extremos: 201 muestras (sin exclusion del reticulo)."""
        perfil, c = perfil_erf()
        luz = (c - 100.0, c + 100.0)
        m = medir(perfil, c, luz=luz, reticulo_px=None, P=_P(fraccion_meseta=1.0))
        assert m.ok, m.estado
        assert m.zona_px == (c - 100.0, c + 100.0) and m.muestras_meseta == 201, m.muestras_meseta
        exacto = medir(perfil, c, luz=luz, reticulo_px=None, P=_P(fraccion_meseta=1.0, muestras_minimas_de_la_meseta=201))
        assert exacto.ok, "201 muestras alcanzan para un minimo de 201"
        una_mas = medir(perfil, c, luz=luz, reticulo_px=None, P=_P(fraccion_meseta=1.0, muestras_minimas_de_la_meseta=202))
        assert not una_mas.ok and "menos de 202 muestras" in una_mas.estado

    def test_una_zona_que_se_sale_del_perfil_no_se_mide_y_una_que_cabe_justo_llega_a_buscar_los_bordes(self):
        """Un perfil de 201 muestras (x de 0 a 200) y una zona de 200 pixeles: igual a el, medio pixel adentro de cada extremo y medio pixel afuera por un lado y por el otro. Solo las dos ultimas se salen del
        perfil («la zona central de la meseta no esta sobre la pelicula»); en las demas lo que falta son los bordes de radiacion, que estan a 1181 pixeles."""
        perfil, _ = perfil_erf(n=201, centro=100.0)
        P = _P(fraccion_meseta=1.0, muestras_minimas_de_la_meseta=100)
        fuera = "no está sobre la película"

        def con_zona(centro_zona):
            return medir(perfil, centro_zona, luz=(centro_zona - 100.0, centro_zona + 100.0), reticulo_px=None, P=P)
        m = con_zona(100.0)
        assert fuera not in m.estado and "borde" in m.estado, m.estado
        assert fuera not in medir(perfil, 100.0, luz=(0.5, 199.5), reticulo_px=None, P=P).estado, "una zona un poco mas chica que el perfil cabe"
        for centro_zona in (99.5, 100.5):
            m = con_zona(centro_zona)
            assert not m.ok and fuera in m.estado, (centro_zona, m.estado)
        antes = medir(perfil, 99.0, luz=(-1.0, 199.0), reticulo_px=None, P=P)
        assert not antes.ok and fuera in antes.estado

    def test_el_suavizado_es_un_promedio_movil_de_11_muestras_para_0_5_mm_a_600_dpi_y_con_0_no_toca_nada(self):
        perfil, c = perfil_erf(ruido=0.5, semilla=1)
        m = medir(perfil, c)
        v = perfil.valores
        for i in (900, 1700, 2500):
            assert m.suavizado[i] == pytest.approx(float(np.mean(v[i - 5:i + 6])), abs=1e-9), i
        assert np.isnan(m.suavizado[:5]).all() and np.isnan(m.suavizado[-5:]).all() and np.isfinite(m.suavizado[5]) and np.isfinite(m.suavizado[-6]), "sin ventana completa no hay valor"
        sin = medir(perfil, c, P=_P(suavizado_perfil_mm=0.0))
        assert np.array_equal(sin.suavizado, v)
        un_mm = medir(perfil, c, P=_P(suavizado_perfil_mm=1.0))                                        # 1 mm = 23.6 pixeles: 2 * round(11.3) + 1 = 23 muestras
        assert un_mm.suavizado[1700] == pytest.approx(float(np.mean(v[1700 - 11:1700 + 12])), abs=1e-9)
        trece = medir(perfil, c, P=_P(suavizado_perfil_mm=12.5 * TAM))                                 # 12.5 pixeles: (12.5 - 1) / 2 = 5.75 -> 6 -> 13 muestras (el numero impar mas cercano al ancho pedido)
        assert trece.suavizado[1700] == pytest.approx(float(np.mean(v[1700 - 6:1700 + 7])), abs=1e-9)

    def test_las_igualdades_se_deciden_a_favor_de_medir_en_el_contraste_la_tinta_y_los_extremos_de_la_exclusion(self):
        """Con una meseta de valor EXACTO (32.0, en el perfil forzado a 32 hasta 45 mm) las igualdades se pueden construir: un contraste igual al minimo (piso 42 contra meseta 32, minimo 10) se mide; una raya
        exactamente `delta_tinta` por debajo de la mediana (7.0) no es tinta (entra a la meseta) y una apenas mas oscura (6.99) si; y los dos extremos de la exclusion del reticulo (a 90 pixeles
        del reticulo, en pixeles enteros) quedan FUERA de la meseta (1883 muestras en la zona menos las 181 de 1610 a 1790)."""
        def plateau_exacto(x, v):
            return np.where(np.abs((x - 1700.0) * TAM) < 45.0, 32.0, v)

        def con_raya(valor):
            def f(x, v):
                return np.where(np.abs((x - 1700.0) * TAM - 12.0) < 0.75, valor, plateau_exacto(x, v))
            return f
        perfil, c = perfil_erf(modificar=plateau_exacto)
        igual = medir(perfil, c, piso=42.0)
        assert igual.ok and igual.meseta == 32.0, igual.estado
        menos = medir(perfil, c, piso=41.9)
        assert not menos.ok and "al menos 10 niveles" in menos.estado
        en_el_limite = medir(*perfil_erf(modificar=con_raya(7.0)))
        apenas_mas_oscura = medir(*perfil_erf(modificar=con_raya(6.99)))
        assert en_el_limite.ok and apenas_mas_oscura.ok
        assert en_el_limite.meseta < 31.9 and apenas_mas_oscura.meseta == 32.0 and en_el_limite.muestras_meseta > apenas_mas_oscura.muestras_meseta
        exacta = medir(perfil, c, reticulo_px=c, P=_P(excepcion_centro_mm=90.0 * TAM))
        assert exacta.ok and exacta.exclusion_px == (c - 90.0, c + 90.0) and exacta.muestras_meseta == 1883 - 181, exacta.muestras_meseta

    def test_el_perfil_que_se_midio_viaja_con_la_medida(self):
        perfil, c = perfil_erf()
        m = medir(perfil, c)
        assert m.perfil is perfil and m.capa == "G" and m.eje == "crossplane" and m.centro_px == c and m.tam_mm == TAM


# ======================================================================================================================================= las dos ayudas de bordes_luz y de medir_perfil
class TestEnElLado:
    def test_los_extremos_del_lado_cuentan_y_un_lado_paralelo_a_la_linea_no_tiene_punto(self):
        pm = _pm()
        assert pm._en_el_lado((0.0, 0.0), (10.0, 20.0), 1, 20.0) == pytest.approx(10.0)       # la linea pasa justo por el extremo b
        assert pm._en_el_lado((0.0, 0.0), (10.0, 20.0), 1, 0.0) == pytest.approx(0.0)         # ... y por el extremo a
        assert pm._en_el_lado((0.0, 0.0), (10.0, 20.0), 1, 20.01) is None and pm._en_el_lado((0.0, 0.0), (10.0, 20.0), 1, -0.01) is None
        assert pm._en_el_lado((3.0, 0.0), (13.0, 20.0), 0, 8.0) == pytest.approx(10.0)        # con la x fija da la y
        assert pm._en_el_lado((0.0, 5.0), (10.0, 5.0), 1, 5.0) is None                        # un lado horizontal no corta una fila en un solo punto


class TestPrimerCruce:
    def test_el_primer_cruce_por_interpolacion_lineal_en_las_dos_direcciones_y_sus_limites(self):
        pm = _pm()
        n = np.array([1.0, 1.0, 0.8, 0.3, 0.1, 0.0])
        assert pm._primer_cruce(n, 0, 1, 0.5) == pytest.approx(2 + (0.8 - 0.5) / (0.8 - 0.3))
        espejo = n[::-1].copy()
        assert pm._primer_cruce(espejo, 5, -1, 0.5) == pytest.approx(5 - (2 + (0.8 - 0.5) / (0.8 - 0.3)))
        assert pm._primer_cruce(np.array([1.0, 0.4]), 0, 1, 0.5) == pytest.approx((1.0 - 0.5) / (1.0 - 0.4)), "el cruce entre las dos primeras muestras"
        assert pm._primer_cruce(np.array([1.0, 0.5, 0.0]), 0, 1, 0.5) == pytest.approx(1.0), "una muestra exactamente en el nivel es el cruce"
        assert pm._primer_cruce(np.array([0.5, 0.2]), 0, 1, 0.5) is None, "empezar en el nivel no es empezar por encima"
        assert pm._primer_cruce(np.array([0.3, 1.0, 0.2]), 0, 1, 0.5) is None, "empieza por debajo"
        assert pm._primer_cruce(np.array([1.0, np.nan, 0.2]), 0, 1, 0.5) is None, "un hueco antes del cruce"
        assert pm._primer_cruce(np.array([1.0, 0.9, 0.8]), 0, 1, 0.5) is None, "no cruza"
        assert pm._primer_cruce(np.array([]), 0, 1, 0.5) is None and pm._primer_cruce(np.array([1.0, 0.4]), 2, 1, 0.5) is None


# ======================================================================================================================================= bordes_luz y coincidencia
def _interseccion(p, q, a, b):
    """Donde la recta que pasa por p y q corta la recta que pasa por a y b: resuelto con un sistema lineal (no con la formula de pendientes del modulo)."""
    A = np.array([[q[0] - p[0], a[0] - b[0]], [q[1] - p[1], a[1] - b[1]]], dtype=float)
    t, _ = np.linalg.solve(A, np.array([a[0] - p[0], a[1] - p[1]], dtype=float))
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))


QUADRILATERO = ((102.3, 80.7), (2401.6, 95.2), (2410.9, 2391.4), (95.4, 2380.2))          # UL, UR, DR, DL de un campo girado: casi un rectangulo, no exactamente


class TestBordesLuz:
    def test_crossplane_es_la_interseccion_analitica_de_la_linea_por_el_cruce_con_los_lados_izquierdo_y_derecho(self):
        pm = _pm()
        ul, ur, dr, dl = QUADRILATERO
        cruce = _interseccion(ul, dr, ur, dl)
        izq = _interseccion(ul, dl, (0.0, cruce[1]), (1.0, cruce[1]))
        der = _interseccion(ur, dr, (0.0, cruce[1]), (1.0, cruce[1]))
        menor, mayor = pm.bordes_luz("crossplane", QUADRILATERO)
        assert menor == pytest.approx(izq[0], abs=1e-9) and mayor == pytest.approx(der[0], abs=1e-9)
        assert menor != round(menor) and mayor != round(mayor), "bordes rasterizados: la interseccion es fraccionaria"

    def test_inplane_es_la_interseccion_con_los_lados_superior_e_inferior(self):
        pm = _pm()
        ul, ur, dr, dl = QUADRILATERO
        cruce = _interseccion(ul, dr, ur, dl)
        sup = _interseccion(ul, ur, (cruce[0], 0.0), (cruce[0], 1.0))
        inf = _interseccion(dl, dr, (cruce[0], 0.0), (cruce[0], 1.0))
        menor, mayor = pm.bordes_luz("inplane", QUADRILATERO)
        assert menor == pytest.approx(sup[1], abs=1e-9) and mayor == pytest.approx(inf[1], abs=1e-9)

    @pytest.mark.parametrize("eje, linea", [("crossplane", 1500.0), ("inplane", 700.0)])
    def test_en_otra_linea_la_interseccion_es_la_de_esa_linea(self, eje, linea):
        pm = _pm()
        ul, ur, dr, dl = QUADRILATERO
        if eje == "crossplane":
            esperado = (_interseccion(ul, dl, (0.0, linea), (1.0, linea))[0], _interseccion(ur, dr, (0.0, linea), (1.0, linea))[0])
        else:
            esperado = (_interseccion(ul, ur, (linea, 0.0), (linea, 1.0))[1], _interseccion(dl, dr, (linea, 0.0), (linea, 1.0))[1])
        assert pm.bordes_luz(eje, QUADRILATERO, linea) == pytest.approx(esperado, abs=1e-9)

    def test_una_linea_fuera_del_campo_no_tiene_bordes(self):
        pm = _pm()
        assert pm.bordes_luz("crossplane", QUADRILATERO, 5000.0) is None and pm.bordes_luz("inplane", QUADRILATERO, -300.0) is None

    def test_una_linea_que_cruza_un_solo_lado_tampoco_tiene_bordes(self):
        """y = 90 esta entre las esquinas superiores (80.7 a la izquierda, 95.2 a la derecha): corta el lado izquierdo y no el derecho. x = 98 esta antes de la esquina superior izquierda (102.3) y despues
        de la inferior izquierda (95.4): corta el lado inferior y no el superior. Un borde solo no es un par de bordes: no se rellena con el otro."""
        pm = _pm()
        assert pm.bordes_luz("crossplane", QUADRILATERO, 90.0) is None
        assert pm.bordes_luz("inplane", QUADRILATERO, 98.0) is None

    def test_un_eje_que_no_existe_es_value_error(self):
        with pytest.raises(ValueError):
            _pm().bordes_luz("axial", QUADRILATERO)


class TestCoincidencia:
    BORDES_RAD = {"izquierdo": 100.0, "derecho": 2400.0, "superior": 90.0, "inferior": 2390.0}

    def test_cada_lado_es_positivo_hacia_afuera_con_la_formula_de_r9_paso_9(self):
        """izquierdo: x_luz - x_rad; derecho: x_rad - x_luz; superior: y_luz - y_rad; inferior: y_rad - y_luz. Con la y hacia abajo: afuera es -x a la izquierda, +x a la derecha, -y arriba, +y abajo."""
        luz = {"izquierdo": 102.0, "derecho": 2398.0, "superior": 95.0, "inferior": 2385.0}
        c = _pm().coincidencia(self.BORDES_RAD, luz, TAM)
        assert c == pytest.approx({"izquierdo": 2 * TAM, "derecho": 2 * TAM, "superior": 5 * TAM, "inferior": 5 * TAM}, abs=1e-12)
        dentro = _pm().coincidencia({"izquierdo": 104.0, "derecho": 2396.0, "superior": 100.0, "inferior": 2380.0}, luz, TAM)
        assert dentro == pytest.approx({"izquierdo": -2 * TAM, "derecho": -2 * TAM, "superior": -5 * TAM, "inferior": -5 * TAM}, abs=1e-12)

    def test_la_radiacion_corrida_a_la_derecha_da_derecho_positivo_e_izquierdo_negativo(self):
        """Los signos del cuaderno eran opuestos por lado (izquierdo y superior hacia afuera, derecho e inferior hacia adentro): aqui un corrimiento de +0.6 mm da +0.6 en el derecho y -0.6 en el izquierdo."""
        luz = {"izquierdo": 100.0, "derecho": 2400.0, "superior": 90.0, "inferior": 2390.0}
        d = 0.6 / TAM
        c = _pm().coincidencia({"izquierdo": 100.0 + d, "derecho": 2400.0 + d, "superior": 90.0 + d, "inferior": 2390.0 + d}, luz, TAM)
        assert c["derecho"] == pytest.approx(0.6, abs=1e-9) and c["izquierdo"] == pytest.approx(-0.6, abs=1e-9)
        assert c["inferior"] == pytest.approx(0.6, abs=1e-9) and c["superior"] == pytest.approx(-0.6, abs=1e-9)

    def test_un_lado_sin_borde_queda_en_none_y_los_demas_se_dan(self):
        luz = {"izquierdo": 100.0, "derecho": 2400.0, "superior": 90.0, "inferior": 2390.0}
        c = _pm().coincidencia({"izquierdo": 99.0, "derecho": None, "superior": 90.0}, luz, TAM)
        assert c["izquierdo"] == pytest.approx(TAM) and c["derecho"] is None and c["inferior"] is None and c["superior"] == 0.0
        assert set(c) == set(LADOS)


# ======================================================================================================================================= girar y perfil_central
class FalsaPelicula:
    """Una pelicula minima con los atributos de `Pelicula` (armada a mano para probar `girar` sin pasar por un archivo): todas las capas valen `nivel` dentro de `caja` (x0, y0, x1, y1) y 255 (el
    fondo del escaner) fuera de ella."""

    def __init__(self, alto, ancho, caja, nivel=100.0, dpi=600):
        self.bits, self.dpi, self.formato, self.transparentes = 8, dpi, "TIFF", 0
        x0, y0, x1, y1 = caja
        base = np.full((alto, ancho), 255.0, np.float32)
        base[y0:y1, x0:x1] = nivel
        self.R, self.G, self.B, self.gris = base.copy(), base.copy(), base.copy(), base.copy()
        self.validos = np.ones((alto, ancho), bool)

    def marcar(self, x, y, valor=200.0, medio=2):
        for capa in (self.R, self.G, self.B, self.gris):
            capa[y - medio:y + medio + 1, x - medio:x + medio + 1] = valor


def _centroide_cerca(arreglo, mascara, esperado, radio=10, fondo=100.0):
    """El centroide (en indices del arreglo) de lo que sobresale de `fondo` en una ventana de +-`radio` pixeles alrededor de `esperado` (x, y)."""
    cx, cy = int(round(esperado[0])), int(round(esperado[1]))
    sub = arreglo[cy - radio:cy + radio + 1, cx - radio:cx + radio + 1].astype(np.float64)
    ok = mascara[cy - radio:cy + radio + 1, cx - radio:cx + radio + 1]
    peso = np.where(ok & (sub > fondo + 0.5), sub - fondo, 0.0)
    ys, xs = np.mgrid[cy - radio:cy + radio + 1, cx - radio:cx + radio + 1]
    return float((peso * xs).sum() / peso.sum()), float((peso * ys).sum() / peso.sum())


class TestGirar:
    def test_la_imagen_y_los_puntos_giran_con_la_misma_matriz(self):
        """UNA definicion del giro: un marcador de 5 x 5 pixeles termina donde `transformar_puntos` lleva el punto, medido en el marco girado (indice del arreglo + origen)."""
        pm = _pm()
        pelicula = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400))
        pelicula.marcar(1300, 900)
        for angulo, centro in ((10.0, (1100.0, 1050.0)), (-6.0, (1000.0, 1100.0)), (0.4, (1100.0, 1050.0))):
            M = pm.matriz_giro(centro, angulo)
            g = pm.girar(pelicula, M, _P(), centro)
            esperado = pm.transformar_puntos(M, [(1300.0, 900.0)])[0]
            x, y = _centroide_cerca(g.capas["G"], g.pelicula, (esperado[0] - g.origen[0], esperado[1] - g.origen[1]))
            assert (x + g.origen[0], y + g.origen[1]) == pytest.approx(esperado, abs=0.15), angulo
            assert g.cruce == pytest.approx(pm.transformar_puntos(M, [centro])[0], abs=1e-9)

    def test_gira_solo_la_pelicula_y_no_la_pagina(self):
        pm = _pm()
        pagina = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400))
        centro = (1100.0, 1050.0)
        g = pm.girar(pagina, pm.matriz_giro(centro, 10.0), _P(), centro)
        alto, ancho = g.capas["G"].shape
        assert alto * ancho < 0.35 * 2400 * 2400, (alto, ancho)
        assert ancho >= 800 and alto >= 700, "contiene toda la pelicula girada"
        x0, y0, x1, y1 = g.caja
        assert x0 <= 700 and y0 <= 700 and x1 >= 1500 and y1 >= 1400 and x1 - x0 < 1100 and y1 - y0 < 1000, "el recorte es la pelicula mas un margen, no la pagina"
        # la caja sale de la pelicula vista de 8 en 8 pixeles (sus primeros pixeles son 704, y la ultima muestra de la fila 1392 y de la columna 1496 cierra en 1504 y 1400) mas `margen_recorte_mm` y dos pasos
        margen = math.ceil(_P()["margen_recorte_mm"] / TAM) + 2 * 8
        assert g.caja == (704 - margen, 704 - margen, 1504 + margen, 1400 + margen), g.caja
        assert not any(a.flags.writeable for a in (*g.capas.values(), g.validos, g.pelicula)), "la pelicula girada la comparten C.3, la ventana y el PDF: de solo lectura"
        assert g.memoria_bytes() == sum(a.nbytes for a in g.capas.values()) + g.validos.nbytes + g.pelicula.nbytes
        assert g.capas["R"].shape == g.capas["G"].shape == g.capas["B"].shape == g.capas["gris"].shape == g.validos.shape == g.pelicula.shape
        assert all(g.capas[c].dtype == np.float32 for c in CAPAS)
        assert g.memoria_bytes() < 8 * alto * ancho * 4, "cuatro capas float32, la mascara y poco mas: ninguna copia de la pagina"

    def test_lo_que_entra_por_el_borde_es_sin_dato_y_lo_que_estaba_tiene_dato(self):
        pm = _pm()
        pelicula = FalsaPelicula(600, 800, (0, 0, 800, 600), nivel=100.0)             # la pelicula llena la imagen: al girar entran esquinas de afuera
        centro = (400.0, 300.0)
        g = pm.girar(pelicula, pm.matriz_giro(centro, 10.0), _P(), centro)
        assert not g.validos[0, 0] and not g.validos[-1, -1], "las esquinas del arreglo girado vienen de afuera de la imagen: sin dato"
        cy, cx = int(round(g.cruce[1] - g.origen[1])), int(round(g.cruce[0] - g.origen[0]))
        assert g.validos[cy, cx] and g.pelicula[cy, cx]
        assert 0.02 < 1.0 - g.validos.mean() < 0.5
        assert not np.any(g.pelicula & ~g.validos), "lo que no tiene dato no es pelicula"

    def test_el_arreglo_girado_cubre_el_recorte_girado_con_un_pixel_de_holgura_por_lado(self):
        """El arreglo de salida es la caja del recorte girado: las cuatro esquinas del recorte (sus ultimos pixeles) caen dentro, a 1 pixel o mas de cada borde y a menos de 2."""
        pm = _pm()
        pelicula = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400))
        centro = (1100.0, 1050.0)
        for angulo in (10.0, -6.0, 0.4, -25.0):
            M = pm.matriz_giro(centro, angulo)
            g = pm.girar(pelicula, M, _P(), centro)
            x0, y0, x1, y1 = g.caja
            esquinas = pm.transformar_puntos(M, [(x0, y0), (x1 - 1, y0), (x1 - 1, y1 - 1), (x0, y1 - 1)])
            xs, ys = [e[0] for e in esquinas], [e[1] for e in esquinas]
            alto, ancho = g.capas["G"].shape
            ox, oy = g.origen
            assert 1.0 <= min(xs) - ox < 2.0 and 1.0 <= min(ys) - oy < 2.0, (angulo, min(xs) - ox, min(ys) - oy)
            assert 1.0 <= ox + ancho - 1 - max(xs) < 2.0 and 1.0 <= oy + alto - 1 - max(ys) < 2.0, (angulo, ox + ancho - 1 - max(xs), oy + alto - 1 - max(ys))

    def test_un_nivel_igual_al_umbral_del_fondo_es_fondo_y_uno_apenas_menor_es_pelicula(self):
        """El fondo del escaner empieza en `umbral_fondo` (235): una pelicula entera en 235 no es pelicula (no hay nada que recortar), una en 234 si; una franja de 235 dentro de la pelicula no cuenta."""
        pm = _pm()
        centro = (1100.0, 1050.0)
        en_el_umbral = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400), nivel=235.0)
        with pytest.raises(ValueError):
            pm.girar(en_el_umbral, pm.matriz_giro(centro, 0.4), _P(), centro)
        apenas_menos = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400), nivel=234.0)
        assert pm.girar(apenas_menos, pm.matriz_giro(centro, 0.4), _P(), centro).pelicula.sum() > 500_000
        con_franja = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400), nivel=100.0)
        for capa in (con_franja.R, con_franja.G, con_franja.B, con_franja.gris):
            capa[1000:1040, 800:1400] = 235.0
        g = pm.girar(con_franja, pm.matriz_giro(centro, 0.0), _P(), centro)           # angulo 0: la matriz es un traslado entero, sin interpolacion
        ox, oy = g.origen
        assert not g.pelicula[1020 - oy, 1100 - ox] and g.pelicula[900 - oy, 1100 - ox] and g.pelicula[1060 - oy, 1100 - ox]

    def test_un_pixel_solo_tiene_dato_si_todo_lo_que_lo_forma_lo_tenia(self):
        """Una pelicula que llena la imagen, girada 10 grados: el pixel de salida cuyo punto de origen cae fuera de la imagen (a mas de 0.05 pixel, por encima de la cuantizacion de 1/32 de pixel con que
        OpenCV calcula los pesos del bilineal) no tiene dato aunque lo mezcle un vecino de adentro, y el que cae dentro (a mas de 0.05 pixel del borde) si: una mezcla con lo de afuera no cuenta como
        dato (umbral de validez de 0.999)."""
        pm = _pm()
        pelicula = FalsaPelicula(600, 800, (0, 0, 800, 600), nivel=100.0)
        centro = (400.0, 300.0)
        M = np.array(pm.matriz_giro(centro, 10.0))
        g = pm.girar(pelicula, M, _P(), centro)
        inversa = cv2.invertAffineTransform(M)
        alto, ancho = g.validos.shape
        ys, xs = np.mgrid[0:alto, 0:ancho]
        px, py = xs + g.origen[0], ys + g.origen[1]
        sx = inversa[0, 0] * px + inversa[0, 1] * py + inversa[0, 2]
        sy = inversa[1, 0] * px + inversa[1, 1] * py + inversa[1, 2]
        dentro = (sx >= 0.05) & (sx <= 799 - 0.05) & (sy >= 0.05) & (sy <= 599 - 0.05)
        fuera = (sx < -0.05) | (sx > 799 + 0.05) | (sy < -0.05) | (sy > 599 + 0.05)
        mezcla = fuera & (sx > -0.5) & (sx < 799.5) & (sy > -0.5) & (sy < 599.5)
        assert dentro.sum() > 400_000 and fuera.sum() > 10_000 and mezcla.sum() > 1_000, "la prueba tiene pixeles de adentro, de afuera y de mezcla"
        assert g.validos[dentro].all()
        assert not g.validos[fuera].any(), int(g.validos[fuera].sum())

    def test_una_mota_suelta_fuera_de_la_pelicula_no_cambia_el_recorte(self):
        """La caja es la de la componente MAS GRANDE de lo que es pelicula: una mota oscura de 10 x 10 pixeles en la esquina de la pagina (polvo del vidrio) no la arrastra."""
        pm = _pm()
        pelicula = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400))
        for capa in (pelicula.R, pelicula.G, pelicula.B, pelicula.gris):
            capa[100:110, 100:110] = 50.0
        centro = (1100.0, 1050.0)
        g = pm.girar(pelicula, pm.matriz_giro(centro, 0.4), _P(), centro)
        x0, y0, x1, y1 = g.caja
        assert x0 <= 700 and y0 <= 700 and x1 >= 1500 and y1 >= 1400 and x1 - x0 < 1100 and y1 - y0 < 1000, g.caja

    def test_el_fondo_del_escaner_no_es_pelicula(self):
        pm = _pm()
        pelicula = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400))
        centro = (1100.0, 1050.0)
        g = pm.girar(pelicula, pm.matriz_giro(centro, 0.4), _P(), centro)
        assert g.pelicula[int(g.cruce[1] - g.origen[1]), int(g.cruce[0] - g.origen[0])]
        assert not g.pelicula[0, 0] and g.pelicula.sum() < 0.9 * g.pelicula.size
        # la pelicula (800 x 700 pixeles) esta ahi, con un margen de pocos pixeles por la mezcla del borde al interpolar
        assert g.pelicula.sum() == pytest.approx(800 * 700, rel=0.02)

    @pytest.mark.parametrize("capa_oscura", ["R", "G", "B"])
    def test_es_pelicula_lo_que_tiene_dato_y_alguna_de_las_tres_capas_baja_del_umbral_aunque_las_otras_dos_sean_claras(self, capa_oscura):
        """La definicion de «pelicula» es la de A.2: un pixel con dato cuya capa MAS OSCURA (la menor de R, G y B) baja de `umbral_fondo`; el fondo del escaner es el que no baja en ninguna. Una pelicula
        cuyo unico canal oscuro es uno (R = 100, G = B = 250, que A.2 y la caja del recorte toman por pelicula) sigue siendo pelicula en el arreglo girado. Las pruebas de siempre ponian los tres canales
        juntos (`FalsaPelicula`, la sintetica): una definicion que mirara un solo canal pasaba todas. Aqui falla en R y en B si mira solo el verde, en G y en B si mira solo el rojo."""
        pm = _pm()
        pelicula = FalsaPelicula(2400, 2400, (700, 700, 1500, 1400))
        for capa in ("R", "G", "B", "gris"):
            getattr(pelicula, capa)[700:1400, 700:1500] = 100.0 if capa == capa_oscura else (200.0 if capa == "gris" else 250.0)
        centro = (1100.0, 1050.0)
        g = pm.girar(pelicula, pm.matriz_giro(centro, 0.4), _P(), centro)
        assert g.pelicula.sum() == pytest.approx(800 * 700, rel=0.02), f"con solo la capa {capa_oscura} oscura la pelicula (800 x 700 pixeles) sigue siendo pelicula"
        assert g.pelicula[int(g.cruce[1] - g.origen[1]), int(g.cruce[0] - g.origen[0])] and not g.pelicula[0, 0]

    def test_el_recorte_girado_es_la_pagina_girada_en_la_region_de_la_pelicula(self):
        """El recorte antes de girar da lo mismo que girar la pagina entera con OpenCV (la referencia, otra llamada independiente)."""
        pm = _pm()
        verdad, pelicula = sintetica(variante="B", theta=0.4, seed=2, ruido=0)
        g_ = pm.geometria_luz(*_esquinas_y_reticulo(verdad), TAM)
        g = pm.girar(pelicula, np.array(g_.matriz_de_giro), _P(), g_.cruce)
        alto, ancho = pelicula.G.shape
        for capa in ("G", "gris"):
            fuente = getattr(pelicula, capa)
            completa = cv2.warpAffine(fuente, np.array(g_.matriz_de_giro), (ancho, alto), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            ox, oy = g.origen
            alto_g, ancho_g = g.capas[capa].shape
            ya, yb, xa, xb = max(0, oy), min(alto, oy + alto_g), max(0, ox), min(ancho, ox + ancho_g)
            propia = g.capas[capa][ya - oy:yb - oy, xa - ox:xb - ox]
            ref = completa[ya:yb, xa:xb]
            usable = g.validos[ya - oy:yb - oy, xa - ox:xb - ox]
            dif = np.abs(propia.astype(np.float64) - ref)[usable]
            assert dif.size > 0.5 * usable.size
            # OpenCV calcula las coordenadas del bilineal en punto fijo de 1/32 de pixel: mover el origen del recorte cambia ese redondeo, y en el borde de la pelicula (un escalon de `e` niveles entre
            # dos pixeles vecinos) la diferencia es a lo mas e / 32 (medido: 2.5625 = 82 / 32 en el verde y 3.5625 = 114 / 32 en el gris); en todo lo demas es 0 (1/32 de nivel a lo mas)
            escalon = float(max(np.abs(np.diff(fuente, axis=0)).max(), np.abs(np.diff(fuente, axis=1)).max()))
            assert dif.mean() < 0.005 and np.percentile(dif, 99.9) < 0.5 and dif.max() <= escalon / 32.0 + 0.01, (capa, float(dif.mean()), float(np.percentile(dif, 99.9)), float(dif.max()), escalon)

    def test_sin_escala_o_sin_pelicula_es_un_error_de_uso(self):
        pm = _pm()
        pelicula = FalsaPelicula(900, 900, (100, 100, 800, 800), dpi=300)             # 300 dpi: otra resolucion, sin escala
        with pytest.raises(ValueError):
            pm.girar(pelicula, pm.matriz_giro((450.0, 450.0), 1.0), _P(), (450.0, 450.0))
        vacia = FalsaPelicula(900, 900, (0, 0, 0, 0))
        with pytest.raises(ValueError):
            pm.girar(vacia, pm.matriz_giro((450.0, 450.0), 1.0), _P(), (450.0, 450.0))


def _esquinas_y_reticulo(verdad):
    """(esquinas UL, UR, DR, DL, reticulo) exactos de la sintetica, para `geometria_luz`."""
    p = puntos_exactos(verdad)
    return p[:4], p[4]


def capa_a_mano(datos, cruce, *, origen=(0, 0), pelicula=None, validos=None, nombre="G"):
    datos = np.asarray(datos, dtype=np.float32)
    return _pm().CapaGirada(nombre=nombre, datos=datos, validos=np.ones(datos.shape, bool) if validos is None else validos,
                            pelicula=np.ones(datos.shape, bool) if pelicula is None else pelicula, origen=origen, cruce=cruce, tam_mm=TAM)


class TestPerfilCentral:
    CRUCE = (150.3, 100.7)                                     # (x, y)

    def test_el_crossplane_recorre_x_y_el_inplane_recorre_y_nunca_cruzados(self):
        """Una imagen cuyo valor es la COLUMNA: el crossplane (horizontal) la reproduce y el inplane (vertical) es constante. Una cuyo valor es la FILA: al reves. Con la fila y la columna cruzadas
        (el `shape[0]` por `[1]` del cuaderno) saldria lo contrario."""
        pm = _pm()
        por_columna = capa_a_mano(np.tile(np.arange(400.0), (300, 1)), self.CRUCE)
        por_fila = capa_a_mano(np.tile(np.arange(300.0)[:, None], (1, 400)), self.CRUCE)
        p = pm.perfil_central(por_columna, "crossplane", _P())
        buenos = ~np.isnan(p.valores)
        assert len(p.valores) == 400 and buenos.sum() > 300
        assert p.valores[buenos] == pytest.approx(np.arange(400.0)[p.desde_px:p.desde_px + len(p.valores)][buenos], abs=1e-9)
        q = pm.perfil_central(por_columna, "inplane", _P())
        assert len(q.valores) == 300 and np.ptp(q.valores[~np.isnan(q.valores)]) == 0.0
        assert np.nanmean(q.valores) == pytest.approx(150.0, abs=0.51)                       # el promedio de las columnas de la banda (alrededor de x = 150.3)
        r = pm.perfil_central(por_fila, "crossplane", _P())
        assert len(r.valores) == 400 and np.ptp(r.valores[~np.isnan(r.valores)]) == 0.0
        assert np.nanmean(r.valores) == pytest.approx(100.5, abs=0.51)                       # el promedio de las filas de la banda (alrededor de y = 100.7)
        s = pm.perfil_central(por_fila, "inplane", _P())
        buenos = ~np.isnan(s.valores)
        assert len(s.valores) == 300 and buenos.sum() > 200
        assert s.valores[buenos] == pytest.approx(np.arange(300.0)[s.desde_px:s.desde_px + len(s.valores)][buenos], abs=1e-9)

    def test_la_banda_es_de_un_milimetro_y_cada_fila_entra_si_su_centro_cae_dentro(self):
        pm = _pm()
        capa = capa_a_mano(np.random.default_rng(3).normal(100.0, 5.0, (300, 400)), self.CRUCE)
        p = pm.perfil_central(capa, "crossplane", _P())
        mitad = 0.5 / TAM
        primera, fin = p.filas_px
        assert primera == math.ceil(self.CRUCE[1] - mitad) and fin == math.ceil(self.CRUCE[1] + mitad) and p.n_filas == fin - primera
        assert p.n_filas in (23, 24) and abs(p.n_filas * TAM - 1.0) < TAM
        esperado = capa.datos[int(primera):int(fin), :].mean(axis=0, dtype=np.float64)
        ok = ~np.isnan(p.valores)
        assert p.valores[ok] == pytest.approx(esperado[ok], abs=1e-9)
        q = pm.perfil_central(capa, "inplane", _P())
        assert q.filas_px == (math.ceil(self.CRUCE[0] - mitad), math.ceil(self.CRUCE[0] + mitad))
        doble = pm.perfil_central(capa, "crossplane", _P(banda_perfil_mm=2.0))
        assert doble.filas_px == (math.ceil(self.CRUCE[1] - 2 * mitad), math.ceil(self.CRUCE[1] + 2 * mitad)) and doble.n_filas in (47, 48), "el ancho de la banda es el parametro, no un milimetro escrito en la funcion"

    def test_las_bandas_vecinas_no_se_solapan_ni_dejan_huecos_y_la_banda_cero_es_la_de_siempre(self):
        pm = _pm()
        capa = capa_a_mano(np.zeros((300, 400)), self.CRUCE)
        bandas = {k: pm.perfil_central(capa, "crossplane", _P(), banda=k) for k in range(-3, 4)}
        for k in range(-3, 3):
            assert bandas[k].filas_px[1] == bandas[k + 1].filas_px[0], k
        assert bandas[0].filas_px == pm.perfil_central(capa, "crossplane", _P()).filas_px
        assert all(23 <= b.n_filas <= 24 for b in bandas.values()) and all(b.banda == k for k, b in bandas.items())

    def test_la_banda_puede_tocar_el_borde_del_arreglo_pero_no_salirse_de_el(self):
        """Con el cruce en y = 11.5 la banda de 1 mm cubre las filas 0 a 23 (de la ceil(11.5 - 11.81) = 0 a la ceil(11.5 + 11.81) = 24, exclusiva): justo un arreglo de 24 filas. Con 23 filas termina una
        despues; con el cruce en 10.5 empieza una antes (la fila -1)."""
        pm = _pm()
        justo = pm.perfil_central(capa_a_mano(np.full((24, 400), 5.0), (150.3, 11.5)), "crossplane", _P())
        assert justo.filas_px == (0, 24) and justo.n_filas == 24
        with pytest.raises(ValueError):
            pm.perfil_central(capa_a_mano(np.full((23, 400), 5.0), (150.3, 11.5)), "crossplane", _P())
        with pytest.raises(ValueError):
            pm.perfil_central(capa_a_mano(np.full((24, 400), 5.0), (150.3, 10.5)), "crossplane", _P())
        # el inplane lo mismo con las columnas: 24 columnas y el cruce en x = 11.5
        solo = pm.perfil_central(capa_a_mano(np.full((400, 24), 5.0), (11.5, 150.3)), "inplane", _P())
        assert solo.filas_px == (0, 24)
        with pytest.raises(ValueError):
            pm.perfil_central(capa_a_mano(np.full((400, 23), 5.0), (11.5, 150.3)), "inplane", _P())

    def test_donde_no_hay_pelicula_o_falta_dato_en_alguna_fila_de_la_banda_no_hay_valor(self):
        pm = _pm()
        datos = np.full((300, 400), 50.0)
        pelicula = np.ones((300, 400), bool)
        pelicula[:, 200:220] = False                                    # una franja sin pelicula (fondo del escaner)
        validos = np.ones((300, 400), bool)
        validos[95, 300] = False                                        # UN pixel sin dato en una de las filas de la banda
        p = pm.perfil_central(capa_a_mano(datos, self.CRUCE, pelicula=pelicula, validos=validos), "crossplane", _P())
        radio = math.ceil(1.0 / TAM)                                    # `margen_borde_mm`: el borde de la pelicula (1 mm) tampoco es pelicula limpia
        assert np.all(np.isnan(p.valores[200 - radio:220 + radio])) and np.isnan(p.valores[300])
        assert not np.isnan(p.valores[200 - radio - 1]) and not np.isnan(p.valores[220 + radio]) and not np.isnan(p.valores[299 - radio])
        assert np.all(np.isnan(p.valores[:radio])) and np.all(np.isnan(p.valores[-radio:])), "el borde del arreglo girado es un borde"

    def test_un_eje_que_no_existe_o_una_banda_vacia_es_un_error_de_uso(self):
        pm = _pm()
        capa = capa_a_mano(np.zeros((300, 400)), self.CRUCE)
        with pytest.raises(ValueError):
            pm.perfil_central(capa, "axial", _P())
        with pytest.raises(ValueError):
            pm.perfil_central(capa, "crossplane", _P(banda_perfil_mm=0.001))
        with pytest.raises(ValueError):
            pm.perfil_central(capa, "crossplane", _P(), banda=5000)

    def test_el_origen_del_arreglo_pone_las_coordenadas_en_el_marco_girado(self):
        """Un arreglo que empieza en (-120, 40) del marco girado: la banda y `desde_px` se dan en ese marco."""
        pm = _pm()
        capa = capa_a_mano(np.tile(np.arange(400.0), (300, 1)), (30.3, 140.7), origen=(-120, 40))
        p = pm.perfil_central(capa, "crossplane", _P())
        assert p.desde_px == -120 and p.filas_px == (math.ceil(140.7 - 0.5 / TAM), math.ceil(140.7 + 0.5 / TAM))
        i = int(30.3 - (-120))
        assert p.valores[i] == pytest.approx(float(i), abs=1e-9)


# ======================================================================================================================================= analizar: el contrato
class Escena:
    """La pelicula sintetica de una prueba: su verdad, la `Pelicula` leida, los cinco puntos exactos y el resultado de `analizar` (solo para las pocas escenas que varias pruebas leen)."""

    def __init__(self, verdad, pelicula, puntos, resultado):
        self.verdad, self.pelicula, self.puntos, self.resultado = verdad, pelicula, puntos, resultado


@pytest.fixture(scope="module")
def banco():
    """Lo caro que varias pruebas comparten (resumenes, escenas, la virgen). Vive lo que dura el modulo y se suelta al terminar (T10: sin caches de modulo)."""
    cosas = {}
    yield cosas
    cosas.clear()
    gc.collect()


@pytest.fixture(scope="module")
def base(banco):
    """La sintetica de siempre: recorte ajustado, giro de 0.4 grados, ruido del escaner, marcas exactas, piso automatico."""
    verdad, pelicula = sintetica(variante="A", theta=0.4, seed=1)
    puntos = puntos_exactos(verdad)
    escena = Escena(verdad, pelicula, puntos, medir_pelicula(pelicula, puntos))
    banco["base"] = escena
    return escena


@pytest.fixture(scope="module")
def virgen(banco):
    if "virgen" not in banco:
        banco["virgen"] = virgen_sintetica()
    return banco["virgen"]


def _fwhm(res, capa, eje):
    return getattr(res.capas[capa], eje).fwhm_mm


class TestAnalizarArmaTodoYLlamaUnaVezAlPiso:
    def test_el_resultado_es_ok_y_trae_las_cuatro_capas_el_piso_y_la_geometria(self, base):
        r = base.resultado
        assert r.estado == "ok" and r.ok and r.version == "PM-1" and r.base == _pm().BASE_VALOR_DE_PIXEL
        assert set(r.capas) == set(CAPAS)
        assert all(r.capas[c].estado == "ok" and r.capas[c].ok for c in CAPAS)
        assert r.piso.estado == "ok" and r.geometria.estado == "ok" and r.tam_mm == pytest.approx(TAM)
        assert r.puntos.ok and sorted(r.puntos.indices_de_las_esquinas + (r.puntos.indice_del_reticulo,)) == [0, 1, 2, 3, 4]
        assert r.parametros == _P() and r.parametros is not _pm().VALORES_DE_LA_GEOMETRIA
        assert r.geometria.angulo_grados == pytest.approx(0.4, abs=0.001)

    def test_llama_una_sola_vez_a_piso_de_pelicula_con_el_modo_el_punto_y_la_referencia_que_recibio(self, base, monkeypatch):
        pm = _pm()
        piso = base.resultado.piso
        llamadas = []

        def espia(*args, **kwargs):
            llamadas.append((args, kwargs))
            return piso
        monkeypatch.setattr(pm, "piso_de_pelicula", espia)
        referencia = object()
        res = pm.analizar(base.pelicula, base.puntos, _P(), modo_piso="punto_manual", punto_manual=(1000.0, 1100.0), referencia_virgen=referencia)
        assert len(llamadas) == 1, "una sola llamada: todas las capas y el barrido usan ESE Piso"
        args, kwargs = llamadas[0]
        assert args[0] is base.pelicula and len(args[1]) == 4 and args[2] == _P()
        assert kwargs == {"punto_manual": (1000.0, 1100.0), "modo": "punto_manual", "referencia_virgen": referencia}
        assert res.piso is piso

    def test_sin_modo_el_modo_es_none_y_decide_el_piso(self, base, monkeypatch):
        pm = _pm()
        vistos = []

        def espia(*args, **kwargs):
            vistos.append(kwargs)
            return base.resultado.piso
        monkeypatch.setattr(pm, "piso_de_pelicula", espia)
        pm.analizar(base.pelicula, base.puntos, _P())
        assert vistos == [{"punto_manual": None, "modo": None, "referencia_virgen": None}]

    @pytest.mark.parametrize("capa", ["R", "G", "B", "gris"])
    def test_cada_capa_usa_el_nivel_de_piso_de_ese_piso_y_no_otro(self, base, monkeypatch, capa):
        """El piso que devuelve la unica llamada se sube 10 niveles en `capa`: su FWHM y sus lados cambian a lo que predice el generador para ese piso, y las demas capas no se tocan."""
        pm = _pm()
        piso0 = base.resultado.piso
        capas = dict(piso0.capas)
        capas[capa] = dataclasses.replace(capas[capa], mediana=capas[capa].mediana + 10.0)
        piso1 = dataclasses.replace(piso0, capas=capas)
        monkeypatch.setattr(pm, "piso_de_pelicula", lambda *a, **k: piso1)
        res = pm.analizar(base.pelicula, base.puntos, _P())
        assert res.piso is piso1 and res.capas[capa].piso == piso0.capas[capa].mediana + 10.0
        e = esperado(base.verdad, capa, piso1.valor(capa))
        assert res.capas[capa].crossplane.fwhm_mm == pytest.approx(e["fwhm_crossplane"], abs=0.12)
        assert res.capas[capa].inplane.fwhm_mm == pytest.approx(e["fwhm_inplane"], abs=0.12)
        antes = esperado(base.verdad, capa, piso0.valor(capa))
        assert abs(e["fwhm_crossplane"] - antes["fwhm_crossplane"]) > 0.2, "el cambio de piso se nota (la prueba discrimina)"
        for otra in CAPAS:
            if otra != capa:
                assert res.capas[otra].crossplane.fwhm_mm == pytest.approx(base.resultado.capas[otra].crossplane.fwhm_mm, abs=1e-9)

    def test_un_piso_no_medible_deja_todas_las_capas_no_medibles_con_su_motivo_y_no_gira_nada(self, base):
        pm = _pm()
        res = pm.analizar(base.pelicula, base.puntos, _P(), modo_piso="virgen")       # sin referencia virgen: el piso es «no medible» (nunca cae al automatico)
        assert res.memoria_bytes() == 0, "nada girado y ningun perfil: no retiene nada"
        assert res.estado.startswith("no medible") and "virgen" in res.estado and not res.ok
        assert res.piso is not None and res.piso.estado == res.estado and res.girada is None
        for c in CAPAS:
            assert res.capas[c].estado.startswith("no medible") and res.capas[c].crossplane.fwhm_mm is None and res.capas[c].inplane.fwhm_mm is None
            assert all(v is None for v in res.capas[c].coincidencia_mm.values()) and set(res.capas[c].coincidencia_mm) == set(LADOS)
        assert res.geometria.estado == "ok" and res.memoria_bytes() < 5_000_000

    def test_un_piso_no_medible_deja_los_bordes_luminosos_y_luz_menos_reticulo_que_no_dependen_de_la_pelicula(self, base):
        """El campo luminoso sale de los cinco puntos y no de la pelicula (R9: luz - reticulo no depende de ella): con el piso «no medible» la geometria es buena y la raiz del resultado trae SUS bordes
        luminosos y SU luz - reticulo, los mismos que con el piso medido (E.1 y F.1 los leen de la raiz), no None. Solo lo que necesita el piso o la pelicula girada queda sin medir."""
        pm = _pm()
        res = pm.analizar(base.pelicula, base.puntos, _P(), modo_piso="virgen")       # sin referencia virgen: el piso es «no medible»
        assert res.estado.startswith("no medible") and not res.ok and res.geometria.ok and res.girada is None
        assert res.luz_menos_reticulo_mm == tuple(res.geometria.luz_menos_reticulo_girado_mm) == base.resultado.luz_menos_reticulo_mm
        for eje in EJES:
            assert res.bordes_luz_px[eje] is not None and res.bordes_luz_px[eje] == pm.bordes_luz(eje, res.geometria.esquinas_giradas) == base.resultado.bordes_luz_px[eje]
        d = res.como_dict()
        assert d["luz_menos_reticulo_mm"] == [float(x) for x in res.luz_menos_reticulo_mm]
        assert d["bordes_luz_px"] == {eje: [float(x) for x in res.bordes_luz_px[eje]] for eje in EJES}
        assert all(v is None for v in (res.capas["G"].crossplane.bordes_luz_px, res.capas["G"].crossplane.fwhm_mm)), "lo de cada capa si queda sin medir"

    def test_con_un_recorte_ajustado_y_girado_el_piso_no_se_mide_pero_el_campo_luminoso_si_y_cae_donde_dice_el_generador(self):
        """El caso tipico de «piso no medible» (R7): un recorte ajustado y girado 3 grados no deja pelicula a mas de 5 mm del campo en las esquinas. La geometria no necesita el piso: los bordes luminosos
        miden lo que el generador (independiente del motor) pone, 99.6 x 99.8 mm, y luz - reticulo es lo que el generador pone, con el signo de C1-D2."""
        verdad, pelicula = sintetica(variante="A", theta=3.0, seed=3, ruido=0)
        res = medir_pelicula(pelicula, puntos_exactos(verdad))
        assert res.estado.startswith("no medible") and "esquinas" in res.estado and not res.ok and res.geometria.ok and res.girada is None
        assert res.luz_menos_reticulo_mm is not None and all(res.bordes_luz_px[eje] is not None for eje in EJES), "el campo luminoso se midio aunque el piso no"
        luz = verdad.bordes_luz
        ancho = {eje: (res.bordes_luz_px[eje][1] - res.bordes_luz_px[eje][0]) * TAM for eje in EJES}
        assert ancho["crossplane"] == pytest.approx(luz["R"] - luz["L"], abs=0.05) and ancho["inplane"] == pytest.approx(luz["B"] - luz["T"], abs=0.05)
        assert res.luz_menos_reticulo_mm == pytest.approx((-verdad.reticulo_menos_luz[0], -verdad.reticulo_menos_luz[1]), abs=0.03)

    def test_si_ninguna_capa_se_pudo_medir_la_raiz_lo_dice_y_ya_no_es_ok(self, base, monkeypatch):
        """`estado` de la raiz es «ok» o el motivo por el que no se pudo medir nada: con la geometria y el piso buenos pero las cuatro capas «no medibles» no hay nada que reportar, y quien pregunte `res.ok`
        (D.1, E.1) no puede tomarlo por un exito. Cada capa conserva su propio motivo; con UNA capa medida por completo la raiz es «ok» y las demas siguen diciendo el suyo."""
        pm = _pm()
        piso0 = base.resultado.piso
        capas = {c: type(piso0.capas[c])(c, f"no medible: la capa {c} no se midio") for c in CAPAS}
        monkeypatch.setattr(pm, "piso_de_pelicula", lambda *a, **k: dataclasses.replace(piso0, capas=capas))
        res = pm.analizar(base.pelicula, base.puntos, _P())
        assert res.piso.estado == "ok" and res.geometria.ok and res.girada is not None
        assert all(not res.capas[c].ok and res.capas[c].estado == f"no medible: la capa {c} no se midio" for c in CAPAS)
        assert not res.ok and res.estado.startswith("no medible: ninguna de las cuatro capas se pudo medir por completo")
        assert res.como_dict()["estado"] == res.estado and all(res.capas[c].estado != res.estado for c in CAPAS)
        capas["gris"] = piso0.capas["gris"]
        una = pm.analizar(base.pelicula, base.puntos, _P())
        assert una.ok and una.estado == "ok" and una.capas["gris"].ok and not una.capas["R"].ok and una.capas["R"].estado == "no medible: la capa R no se midio"

    def test_con_una_dosis_tan_baja_que_ninguna_capa_tiene_contraste_la_raiz_no_dice_ok(self):
        """El caso real de la revision (6 % de la dosis): el piso es bueno, la geometria tambien, y ninguna capa llega a los 10 niveles de contraste. La raiz no es «ok»: el estado verdadero no puede
        estar solo dentro de cada capa y de `valores_medidos`."""
        pm = _pm()
        virgen, meseta = np.array(gen.CALIB["virgen_bgr"]), np.array(gen.CALIB["meseta_bgr"])
        calib = dict(gen.CALIB, meseta_bgr=tuple(virgen - (virgen - meseta) * 0.06))
        verdad, pelicula = sintetica(variante="L", theta=1.0, seed=3, calib=calib)
        res = medir_pelicula(pelicula, puntos_exactos(verdad))
        assert res.piso.estado == "ok" and res.geometria.ok and res.girada is not None
        assert all(not res.capas[c].ok and "10 niveles" in res.capas[c].estado for c in CAPAS)
        assert not res.ok and res.estado.startswith("no medible: ninguna de las cuatro capas se pudo medir por completo")
        assert pm.valores_medidos(res, "G")["estado"] == res.capas["G"].estado and pm.valores_medidos(res, "G")["fwhm_crossplane_mm"] is None

    def test_unas_capas_medidas_a_medias_no_hacen_ok_a_la_raiz_pero_conservan_lo_que_se_midio(self, base, monkeypatch):
        """Una capa es «ok» si sus DOS perfiles se midieron. Si en ninguna lo estan (aqui el inplane de las cuatro), la raiz dice que no se pudo medir ninguna por completo y cada capa conserva su crossplane."""
        pm = _pm()
        original = pm.perfil_central

        def sin_el_inplane(capa, eje, P, banda=0):
            if eje == "inplane":
                raise ValueError("La banda 0 del perfil inplane (de 1 a 25) queda fuera de la película girada.")
            return original(capa, eje, P, banda)
        monkeypatch.setattr(pm, "perfil_central", sin_el_inplane)
        res = pm.analizar(base.pelicula, base.puntos, _P())
        assert all(not res.capas[c].ok and res.capas[c].crossplane.ok and res.capas[c].inplane.fwhm_mm is None for c in CAPAS)
        assert res.capas["G"].crossplane.fwhm_mm == pytest.approx(base.resultado.capas["G"].crossplane.fwhm_mm, abs=1e-9)
        assert not res.ok and res.estado.startswith("no medible: ninguna de las cuatro capas se pudo medir por completo")

    def test_la_capa_cuyo_piso_no_se_pudo_medir_no_detiene_a_las_demas(self, base, monkeypatch):
        pm = _pm()
        piso0 = base.resultado.piso
        capas = dict(piso0.capas)
        capas["B"] = type(capas["B"])("B", "no medible: el piso de la capa azul no es más claro que la meseta en al menos 10 niveles (piso 80.0, meseta 79.0)")
        monkeypatch.setattr(pm, "piso_de_pelicula", lambda *a, **k: dataclasses.replace(piso0, capas=capas))
        res = pm.analizar(base.pelicula, base.puntos, _P())
        assert res.ok and not res.capas["B"].ok and res.capas["B"].estado.startswith("no medible") and "azul" in res.capas["B"].estado
        assert res.capas["B"].crossplane.fwhm_mm is None and res.capas["B"].inplane.fwhm_mm is None
        for c in ("R", "G", "gris"):
            assert res.capas[c].ok and res.capas[c].crossplane.fwhm_mm == pytest.approx(base.resultado.capas[c].crossplane.fwhm_mm, abs=1e-9)
        # un piso incoherente (estado «no medible» pero con nivel): manda el estado, no se mide con ese nivel
        capas["B"] = dataclasses.replace(piso0.capas["B"], estado="no medible: la capa azul no se midio")
        monkeypatch.setattr(pm, "piso_de_pelicula", lambda *a, **k: dataclasses.replace(piso0, capas=capas))
        incoherente = pm.analizar(base.pelicula, base.puntos, _P())
        assert not incoherente.capas["B"].ok and incoherente.capas["B"].estado == "no medible: la capa azul no se midio" and incoherente.capas["B"].crossplane.fwhm_mm is None

    def test_puntos_que_no_forman_el_campo_dan_no_medible_con_el_motivo_de_c1(self, base):
        pm = _pm()
        res = pm.analizar(base.pelicula, [(10.0, 10.0), (20.0, 20.0), (30.0, 30.0), (40.0, 40.0), (50.0, 50.0)], _P())
        assert not res.ok and res.estado.startswith(pm.MOTIVO_NO_FORMAN_EL_CAMPO) and res.piso is None and res.girada is None
        assert all(not res.capas[c].ok and res.capas[c].estado == res.estado for c in CAPAS)

    def test_sin_escala_dice_que_no_hay_milimetros(self):
        pm = _pm()
        verdad, pelicula = sintetica(variante="A", theta=0.0, seed=1, dpi=300, ruido=0)    # una pelicula escaneada a 300 dpi: otra resolucion, sin escala
        res = pm.analizar(pelicula, puntos_exactos(verdad), _P())
        assert not res.ok and res.estado == pm.MOTIVO_SIN_ESCALA and res.tam_mm is None
        assert all(res.capas[c].estado == pm.MOTIVO_SIN_ESCALA for c in CAPAS)
        d = res.como_dict()
        assert d["tam_mm"] is None and d["capas"]["G"]["crossplane"]["tam_mm"] is None and d["estado"] == pm.MOTIVO_SIN_ESCALA

    def test_una_forma_equivocada_de_los_argumentos_es_value_error(self, base):
        pm = _pm()
        with pytest.raises(ValueError):
            pm.analizar(base.pelicula, base.puntos[:4], _P())
        with pytest.raises(ValueError):
            pm.analizar(base.pelicula, base.puntos, {k: v for k, v in _P().items() if k != "fraccion_meseta"})
        with pytest.raises(ValueError):
            pm.analizar(base.pelicula, base.puntos, {k: v for k, v in _P().items() if k != "resolucion_escaneo_dpi"})
        with pytest.raises(ValueError):
            pm.analizar(base.pelicula, base.puntos, _P(), modo_piso="inventado")

    def test_el_resultado_como_dato_trae_los_numeros_de_lo_medido(self, base):
        """`como_dict()` es lo que D.1 guarda para volver a medir: cada campo es el del resultado (listas de floats donde hay pares, None donde no hay nada)."""
        r = base.resultado
        d = r.como_dict()
        par = lambda p: [float(x) for x in p]
        assert d["tam_mm"] == r.tam_mm and d["puntos"] == r.puntos.como_dict() and d["geometria"] == r.geometria.como_dict() and d["piso"] == r.piso.como_dict()
        assert d["luz_menos_reticulo_mm"] == par(r.luz_menos_reticulo_mm) and d["bordes_luz_px"] == {eje: par(r.bordes_luz_px[eje]) for eje in EJES}
        assert len(d["marcas"]) == 5 and d["marcas"] == [list(m) for m in r.marcas]
        for c in CAPAS:
            m, dc = r.capas[c], d["capas"][c]
            assert dc["capa"] == c and dc["estado"] == "ok" and dc["piso"] == m.piso and dc["coincidencia_mm"] == m.coincidencia_mm
            assert dc["centro_radiacion_px"] == par(m.centro_radiacion_px) and dc["radiacion_menos_luz_mm"] == par(m.radiacion_menos_luz_mm) and dc["radiacion_menos_reticulo_mm"] == par(m.radiacion_menos_reticulo_mm)
            for eje in EJES:
                p, dp = getattr(m, eje), dc[eje]
                assert dp["estado"] == "ok" and dp["capa"] == c and dp["eje"] == eje and dp["tam_mm"] == p.tam_mm and dp["centro_px"] == float(p.centro_px)
                assert dp["banda_px"] == [float(p.perfil.filas_px[0]), float(p.perfil.filas_px[1])]
                assert dp["zona_px"] == par(p.zona_px) and dp["exclusion_px"] == par(p.exclusion_px) and dp["bordes_luz_px"] == par(p.bordes_luz_px) and dp["bordes_rad_px"] == par(p.bordes_rad_px)
                assert dp["penumbras_mm"] == par(p.penumbras_mm) and dp["avisos"] == list(p.avisos) and dp["muestras_meseta"] == p.muestras_meseta
                for k in ("piso", "meseta", "altura_media", "nivel_penumbra_alta", "nivel_penumbra_baja", "fwhm_mm", "centro_rad_px"):
                    assert dp[k] == getattr(p, k), (c, eje, k)

    def test_el_resultado_de_lo_que_no_se_midio_como_dato_trae_none_donde_no_hay_nada(self, base):
        pm = _pm()
        res = pm.analizar(base.pelicula, [(10.0, 10.0), (20.0, 20.0), (30.0, 30.0), (40.0, 40.0), (50.0, 50.0)], _P())
        d = res.como_dict()
        assert d["piso"] is None and d["geometria"] is None and d["luz_menos_reticulo_mm"] is None and d["bordes_luz_px"] == {"crossplane": None, "inplane": None}
        assert d["puntos"] is not None and d["puntos"]["estado"].startswith("no medible") and d["tam_mm"] == pytest.approx(TAM)
        for c in CAPAS:
            dc = d["capas"][c]
            assert dc["piso"] is None and dc["centro_radiacion_px"] == [None, None] and dc["radiacion_menos_luz_mm"] == [None, None] and dc["radiacion_menos_reticulo_mm"] == [None, None]
            assert set(dc["coincidencia_mm"].values()) == {None}
            for eje in EJES:
                dp = dc[eje]
                assert dp["estado"].startswith("no medible") and dp["tam_mm"] == pytest.approx(TAM) and dp["centro_px"] is None and dp["banda_px"] is None
                assert dp["zona_px"] is None and dp["exclusion_px"] is None and dp["bordes_luz_px"] is None and dp["bordes_rad_px"] == [None, None] and dp["penumbras_mm"] == [None, None]
                assert dp["fwhm_mm"] is None and dp["centro_rad_px"] is None and dp["muestras_meseta"] == 0 and dp["avisos"] == []
        # con el piso medido pero un perfil sin medir (la medida de una capa sin reticulo): None en el exclusion_px
        perfil, c = perfil_erf()
        sin_reticulo = medir(perfil, c, reticulo_px=None)
        assert sin_reticulo.como_dict()["exclusion_px"] is None and sin_reticulo.como_dict()["zona_px"] is not None

    def test_unos_puntos_que_no_son_una_lista_son_value_error(self, base):
        pm = _pm()
        for malos in (5, None, 3.5):
            with pytest.raises(ValueError):
                pm.analizar(base.pelicula, malos, _P())

    def test_los_parametros_que_viajan_con_el_resultado_son_una_copia(self, base):
        """El resultado guarda los `P` con que se midio (D.1 los guarda y al reabrir se recalcula con ELLOS, no con los de hoy): una copia profunda, ni el diccionario del llamador ni nada que comparta."""
        pm = _pm()
        P = copy.deepcopy(_P())
        res = pm.analizar(base.pelicula, [(10.0, 10.0), (20.0, 20.0), (30.0, 30.0), (40.0, 40.0), (50.0, 50.0)], P)         # puntos que no forman el campo: no cuesta nada y igual guarda los parametros
        assert res.parametros == P and res.parametros is not P
        P["suavizado_perfil_mm"] = 99.0
        P["resoluciones_de_editor_dpi"].append(1.0)
        assert res.parametros["suavizado_perfil_mm"] == 0.5 and 1.0 not in res.parametros["resoluciones_de_editor_dpi"]
        res.parametros["fraccion_meseta"] = 0.1
        assert P["fraccion_meseta"] == 0.8

    def test_analizar_no_modifica_la_pelicula_ni_los_puntos(self):
        pm = _pm()
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=3, ruido=0)
        puntos = puntos_exactos(verdad)

        def huella():
            return {c: hashlib.md5(np.ascontiguousarray(getattr(pelicula, c)).tobytes()).hexdigest() for c in CAPAS} | {"validos": hashlib.md5(np.ascontiguousarray(pelicula.validos).tobytes()).hexdigest()}
        antes, copia = huella(), copy.deepcopy(puntos)
        res = pm.analizar(pelicula, puntos, _P())
        assert res.ok and huella() == antes and puntos == copia

    def test_un_perfil_que_no_se_puede_sacar_deja_esa_capa_no_medible_y_las_demas_se_miden(self, base, monkeypatch):
        """`perfil_central` lanza `ValueError` si la banda queda fuera de la pelicula girada: `analizar` no lanza, dice «no medible: perfil inplane: ...» en ESA capa y sigue con las demas."""
        pm = _pm()
        original = pm.perfil_central

        def sin_la_banda_del_azul(capa, eje, P, banda=0):
            if capa.nombre == "B" and eje == "inplane":
                raise ValueError("La banda 0 del perfil inplane (de 1 a 25) queda fuera de la película girada.")
            return original(capa, eje, P, banda)
        monkeypatch.setattr(pm, "perfil_central", sin_la_banda_del_azul)
        res = pm.analizar(base.pelicula, base.puntos, _P())
        assert res.ok
        azul = res.capas["B"]
        assert not azul.ok and azul.estado.startswith("no medible: perfil inplane") and "fuera de la película girada" in azul.estado
        assert azul.inplane.fwhm_mm is None and azul.crossplane.ok and azul.crossplane.fwhm_mm == pytest.approx(base.resultado.capas["B"].crossplane.fwhm_mm, abs=1e-9)
        for c in ("R", "G", "gris"):
            assert res.capas[c].ok and res.capas[c].inplane.fwhm_mm == pytest.approx(base.resultado.capas[c].inplane.fwhm_mm, abs=1e-9)

    def test_los_puntos_pueden_llegar_como_marcas_refinadas_o_como_su_diccionario_guardado_y_en_cualquier_orden(self, base):
        """`punto_de_medida` es la unica definicion de con que punto se mide (C.1): reabrir un analisis guardado pasa los diccionarios de `MarcaRefinada.como_dict()`."""
        pm = _pm()
        marcas = [pm.refinar_marca(base.pelicula.gris, p, _P(), validos=base.pelicula.validos) for p in base.puntos]
        desordenadas = [marcas[i] for i in (2, 4, 0, 3, 1)]
        guardadas = [m.como_dict() for m in desordenadas]
        a = pm.analizar(base.pelicula, desordenadas, _P(), modo_piso="automatico")
        b = pm.analizar(base.pelicula, guardadas, _P(), modo_piso="automatico")
        for c in CAPAS:
            assert _fwhm(a, c, "crossplane") == _fwhm(b, c, "crossplane") and a.capas[c].coincidencia_mm == b.capas[c].coincidencia_mm
        assert a.marcas == tuple(m.como_dict() for m in desordenadas) and b.marcas == tuple(guardadas), "las marcas viajan con el resultado como datos, en el orden en que llegaron"


# ======================================================================================================================================= analizar: contra la verdad del generador
class TestContraLaVerdadDelGenerador:
    """(a) del PROTOCOLO: el generador de PF.0 no importa nada del motor. Con el piso de las esquinas (la pelicula de fuera del campo recibe la cola de dispersion y es 1 nivel mas oscura que la virgen:
    R7) lo que se compara es lo que PREDICE el generador para ese piso; con la virgen sintetica en el modo «virgen» (A.3), la verdad de la dosis."""

    @pytest.mark.parametrize("capa", ["R", "G", "B", "gris"])
    def test_el_fwhm_y_cada_lado_caen_donde_predice_el_generador_para_el_piso_usado(self, base, capa):
        m = base.resultado.capas[capa]
        e = esperado(base.verdad, capa, m.piso)
        assert m.crossplane.fwhm_mm == pytest.approx(e["fwhm_crossplane"], abs=0.12)
        assert m.inplane.fwhm_mm == pytest.approx(e["fwhm_inplane"], abs=0.12)
        for lado in LADOS:
            assert m.coincidencia_mm[lado] == pytest.approx(e["coincidencia"][lado], abs=0.12), lado
        assert m.radiacion_menos_luz_mm == pytest.approx(e["radiacion_menos_luz"], abs=0.08)

    @pytest.mark.parametrize("capa", ["R", "G", "B", "gris"])
    def test_la_penumbra_80_20_de_cada_lado_es_la_que_predice_el_generador(self, base, capa):
        m = base.resultado.capas[capa]
        p = penumbras_esperadas(base.verdad, capa, m.piso)
        medidas = {"izquierdo": m.crossplane.penumbras_mm[0], "derecho": m.crossplane.penumbras_mm[1], "superior": m.inplane.penumbras_mm[0], "inferior": m.inplane.penumbras_mm[1]}
        for lado in LADOS:
            assert medidas[lado] is not None and medidas[lado] == pytest.approx(p[lado], abs=0.25), (lado, medidas[lado], p[lado])
        assert m.crossplane.avisos == () and m.inplane.avisos == ()

    def test_con_la_virgen_sintetica_en_modo_virgen_el_azul_cae_sobre_la_dosis_del_generador(self, base, virgen):
        """Las tolerancias del plan: FWHM +-0.15 mm, coincidencia por lado +-0.15 mm, los tres centros +-0.1 mm. El azul es la unica capa lineal en la dosis (k = 0)."""
        v = base.verdad
        res = medir_pelicula(base.pelicula, base.puntos, modo_piso="virgen", referencia_virgen=virgen)
        assert res.ok and res.piso.origen == "virgen" and res.piso.referencia is virgen
        m = res.capas["B"]
        assert m.crossplane.fwhm_mm == pytest.approx(v.FWHM_x, abs=0.15) and m.inplane.fwhm_mm == pytest.approx(v.FWHM_y, abs=0.15)
        verdadera = {"izquierdo": v.exceso["L"], "derecho": v.exceso["R"], "superior": v.exceso["T"], "inferior": v.exceso["B"]}
        for lado in LADOS:
            assert m.coincidencia_mm[lado] == pytest.approx(verdadera[lado], abs=0.15), lado
        assert m.radiacion_menos_luz_mm == pytest.approx(v.centro_rad_menos_luz, abs=0.1)
        assert m.radiacion_menos_reticulo_mm == pytest.approx((v.centro_rad_menos_luz[0] - v.reticulo_menos_luz[0], v.centro_rad_menos_luz[1] - v.reticulo_menos_luz[1]), abs=0.1)
        assert res.luz_menos_reticulo_mm == pytest.approx((-v.reticulo_menos_luz[0], -v.reticulo_menos_luz[1]), abs=0.03)

    @pytest.mark.parametrize("capa", ["R", "G", "B"])
    def test_con_la_virgen_sintetica_cada_capa_cae_sobre_los_bordes_que_predice_el_generador_en_esa_capa(self, base, virgen, capa):
        """La verdad por capa (`verdad.capas`): la respuesta del propio generador con el piso virgen. La sintetica no dice cual capa es la buena; solo que cada una cae donde el generador la pone."""
        v = base.verdad
        res = medir_pelicula(base.pelicula, base.puntos, modo_piso="virgen", referencia_virgen=virgen)
        m, t = res.capas[capa], v.capas[capa]
        assert m.crossplane.fwhm_mm == pytest.approx(t.FWHM_x, abs=0.15) and m.inplane.fwhm_mm == pytest.approx(t.FWHM_y, abs=0.15)
        luz = v.bordes_luz
        verdadera = {"izquierdo": luz["L"] - t.bordes["L"], "derecho": t.bordes["R"] - luz["R"], "superior": luz["T"] - t.bordes["T"], "inferior": t.bordes["B"] - luz["B"]}
        for lado in LADOS:
            assert m.coincidencia_mm[lado] == pytest.approx(verdadera[lado], abs=0.15), lado

    def test_sin_cola_de_dispersion_el_piso_de_las_esquinas_es_el_virgen_y_el_azul_cae_sobre_la_dosis(self):
        """Con la cola de dispersion en cero la pelicula de fuera del campo SI es virgen: el modo automatico da tambien la dosis del generador (las tolerancias del plan, sin virgen aparte)."""
        calib = dict(gen.CALIB, s_cola=0.0)
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=5, calib=calib)
        res = medir_pelicula(pelicula, puntos_exactos(verdad))
        m = res.capas["B"]
        assert m.piso == pytest.approx(82.0, abs=1.0)
        assert m.crossplane.fwhm_mm == pytest.approx(verdad.FWHM_x, abs=0.15) and m.inplane.fwhm_mm == pytest.approx(verdad.FWHM_y, abs=0.15)
        verdadera = {"izquierdo": verdad.exceso["L"], "derecho": verdad.exceso["R"], "superior": verdad.exceso["T"], "inferior": verdad.exceso["B"]}
        for lado in LADOS:
            assert m.coincidencia_mm[lado] == pytest.approx(verdadera[lado], abs=0.15), lado
        assert m.radiacion_menos_luz_mm == pytest.approx(verdad.centro_rad_menos_luz, abs=0.1)

    def test_el_reticulo_corrido_4_mm_se_excluye_donde_esta_el_reticulo_y_no_en_el_cruce(self):
        """La sintetica con el reticulo 4 mm a la derecha del centro del campo luminoso: la exclusion central de 3.8 mm se centra en el RETICULO REFINADO."""
        calib = dict(gen.CALIB, reticulo_mm=(4.0, 0.0))
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=1, calib=calib)
        pm = _pm()
        marcas = [pm.refinar_marca(pelicula.gris, p, _P(), validos=pelicula.validos) for p in puntos_exactos(verdad)]
        res = pm.analizar(pelicula, marcas, _P())
        for c in CAPAS:
            m = res.capas[c].crossplane
            assert m.ok, (c, m.estado)
            retx = res.geometria.reticulo_girado[0]
            assert m.exclusion_px[0] == pytest.approx(retx - 3.8 / TAM, abs=0.6) and m.exclusion_px[1] == pytest.approx(retx + 3.8 / TAM, abs=0.6)
            assert (m.exclusion_px[0] + m.exclusion_px[1]) / 2 - m.centro_px == pytest.approx(4.0 / TAM, abs=1.5), "la exclusion esta a 4 mm del cruce, donde esta el reticulo"
            assert m.zona_px[0] < m.exclusion_px[0] and m.exclusion_px[1] < m.zona_px[1], "el reticulo a 4 mm del cruce cae dentro de la zona central: es lo que se excluye"
        e = esperado(verdad, "B", res.capas["B"].piso, calib)
        assert res.capas["B"].crossplane.fwhm_mm == pytest.approx(e["fwhm_crossplane"], abs=0.12)
        assert res.luz_menos_reticulo_mm == pytest.approx((-4.0, 0.0), abs=0.05)

    def test_el_reticulo_corrido_en_los_dos_ejes_se_excluye_en_cada_perfil_donde_esta_el_reticulo_a_lo_largo_de_ese_eje(self):
        """La exclusion de CADA perfil se centra en la coordenada del reticulo a lo largo de ESE eje: la x en el crossplane y la y en el inplane (el obstaculo 3 del plan, para los dos ejes; la prueba de arriba
        solo mira el crossplane con el reticulo corrido en x). Con el reticulo corrido -3 mm en x y +4 mm en y, usar para el inplane la x del reticulo (`reticulo[0]` en los dos ejes) o intercambiar las
        dos deja la exclusion del inplane a cientos de pixeles de la marca: la tinta entra a la meseta."""
        calib = dict(gen.CALIB, reticulo_mm=(-3.0, 4.0))
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=1, calib=calib)
        res = medir_pelicula(pelicula, puntos_exactos(verdad))
        assert res.ok, res.estado
        for c in CAPAS:
            for i, eje in enumerate(EJES):
                m = getattr(res.capas[c], eje)
                assert m.ok, (c, eje, m.estado)
                centro_de_la_exclusion = sum(m.exclusion_px) / 2
                assert centro_de_la_exclusion == pytest.approx(res.geometria.reticulo_girado[i], abs=1e-6), (c, eje)
                assert (centro_de_la_exclusion - m.centro_px) * TAM == pytest.approx(calib["reticulo_mm"][i], abs=0.05), (c, eje, "el generador pone el reticulo a este desplazamiento del centro luminoso")
                assert m.exclusion_px[1] - m.exclusion_px[0] == pytest.approx(2 * 3.8 / TAM, abs=1e-6)
                assert m.zona_px[0] < m.exclusion_px[0] and m.exclusion_px[1] < m.zona_px[1]


# ======================================================================================================================================= una meseta que no es plana
CUPULAS = (-2.0, -5.7)                                   # el rango real de las peliculas (PF.0: de -1.6 a -5.7 % a 40 mm)
CUPULAS_DEL_ORACULO = CUPULAS + (-10.0,)                # y una FUERA del rango real, para que el estimador de la meseta (media, mediana, maximo...) se vea con holgura de sobra


def _con_cupula(banco, cupula):
    """Lo medido en la sintetica sin ruido con la cupula `cupula` (porcentaje a 40 mm), una sola vez por modulo: (Resumen, verdad)."""
    clave = ("cupula", cupula)
    if clave not in banco:
        verdad, pelicula = sintetica(variante="L", theta=0.5, seed=4, ruido=0, cupula_pct_40mm=cupula)
        resultado = medir_pelicula(pelicula, puntos_exactos(verdad))
        assert resultado.ok, resultado.estado
        banco[clave] = (Resumen(resultado), verdad)
        del resultado, pelicula
        gc.collect()
    return banco[clave]


class TestUnaMesetaQueNoEsPlana:
    """Las peliculas reales no tienen la meseta plana: tienen cupula (PF.0: de -1.6 a -5.7 % a 40 mm del centro, media -4.1 %). El plan define la meseta como el nivel MEDIO de la zona central (R9, paso 7) y
    el borde como el 50 % entre el piso y ESE nivel. Con la meseta plana el 50 % de la meseta es el de la dosis; con cupula, no: la media queda por debajo del centro del campo y el borde sale mas afuera.
    Todas las pruebas de arriba usan la meseta plana (cupula 0): ninguna distingue «la media de la zona» de otro estimador de la meseta, y la garantia de +-0.15 mm contra la dosis solo vale ahi (C2-D15)."""

    @pytest.mark.parametrize("cupula", CUPULAS_DEL_ORACULO)
    @pytest.mark.parametrize("capa", ["R", "G", "B", "gris"])
    def test_con_cupula_el_borde_cae_donde_lo_pone_la_definicion_del_plan_el_50_por_ciento_entre_el_piso_y_la_media_de_la_zona_central(self, banco, cupula, capa):
        """Contra una verdad que no sale del motor: el nivel medio de la zona central lo calcula la prueba de la respuesta del generador (`meseta_media_esperada`). Sin ruido y con la cupula del rango real,
        el FWHM, cada lado y el centro caen donde dice esa definicion (el error no crece con la cupula); contra la dosis del centro del campo (`esperado` sin `con_meseta_media`) se alejan hasta 0.13 mm."""
        resumen, verdad = _con_cupula(banco, cupula)
        m = resumen.capas[capa]
        e = esperado(verdad, capa, m["piso"], con_meseta_media=True)
        assert m["fwhm_crossplane"] == pytest.approx(e["fwhm_crossplane"], abs=0.04) and m["fwhm_inplane"] == pytest.approx(e["fwhm_inplane"], abs=0.04)
        for lado in LADOS:
            assert m["coincidencia"][lado] == pytest.approx(e["coincidencia"][lado], abs=0.03), lado
        assert m["radiacion_menos_luz"] == pytest.approx(e["radiacion_menos_luz"], abs=0.02)

    @pytest.mark.parametrize("cupula", CUPULAS)
    def test_con_cupula_el_azul_se_aparta_de_la_dosis_del_generador_lo_que_declara_el_limite_del_metodo(self, banco, cupula):
        """EL LIMITE, medido (C2-D15): con la meseta plana el azul (la unica capa lineal en la dosis) cae a menos de 0.05 mm de la dosis; con cupula, el 50 % de la media de la meseta no es el 50 % de la dosis
        del centro y el FWHM del azul sale mas ancho unos 0.0225 mm por cada 1 % de cupula a 40 mm (+-0.03): 0.13 mm con -5.7 %, que con el ruido del escaner (hasta 0.05 mm en el azul) pasa de los +-0.15 mm
        del protocolo. Es la definicion del plan y no un defecto de la medida; la prueba fija el tamano del apartamiento para que se vea si algun dia cambia."""
        resumen, verdad = _con_cupula(banco, cupula)
        m = resumen.capas["B"]
        e = esperado(verdad, "B", m["piso"])
        for eje in ("fwhm_crossplane", "fwhm_inplane"):
            assert m[eje] - e[eje] == pytest.approx(0.0225 * abs(cupula), abs=0.03), (eje, cupula, m[eje] - e[eje])
        assert m["fwhm_crossplane"] > e["fwhm_crossplane"], "la meseta media es mas baja que el centro: el borde sale mas afuera y el FWHM mas ancho"


# ======================================================================================================================================= la misma pelicula da lo mismo
CAMBIOS_DE_ENCUADRE = [("B", 0.4), ("C", 0.4), ("D", 0.4), ("E", 0.4), ("A", 0.0), ("L", 1.0), ("A", -0.7)]


def _resumen(banco, virgen, variante, theta, modo="virgen", ruido=0, seed=1, calib=None):
    clave = ("resumen", variante, theta, modo, ruido, seed, repr(calib))
    if clave not in banco:
        opciones = dict(variante=variante, theta=theta, seed=seed, ruido=ruido)
        if calib is not None:
            opciones["calib"] = calib
        verdad, pelicula = sintetica(**opciones)
        extra = dict(modo_piso="virgen", referencia_virgen=virgen) if modo == "virgen" else {}
        resultado = medir_pelicula(pelicula, puntos_exactos(verdad), **extra)
        assert resultado.ok, resultado.estado
        banco[clave] = (Resumen(resultado), verdad)
        del resultado, pelicula
        gc.collect()
    return banco[clave]


def _diferencias(a, b):
    """Las diferencias absolutas (mm) entre dos Resumen: {(capa, que): valor}."""
    sal = {}
    for c in CAPAS:
        x, y = a.capas[c], b.capas[c]
        for k in ("fwhm_crossplane", "fwhm_inplane"):
            sal[(c, k)] = abs(x[k] - y[k])
        for lado in LADOS:
            sal[(c, lado)] = abs(x["coincidencia"][lado] - y["coincidencia"][lado])
        for i, eje in enumerate("xy"):
            sal[(c, "radiacion_menos_luz_" + eje)] = abs(x["radiacion_menos_luz"][i] - y["radiacion_menos_luz"][i])
    return sal


class TestLaMismaPeliculaDaLoMismo:
    """(b): la misma pelicula sintetica, sin ruido y con la misma virgen, en un recorte, en una pagina del escaner (centrada, descentrada o muy descentrada) o girada 1 grado, da lo mismo (<= 0.05 mm).
    Rojo: el cuaderno toma el piso de UN pixel de la pagina (el fondo blanco: +15 / +17 mm), ubica las ventanas con `shape//2` (descentrada) y pierde el piso con el giro (el negro del `warpAffine`)."""

    @pytest.mark.parametrize("variante, theta", CAMBIOS_DE_ENCUADRE)
    def test_en_el_modo_virgen_no_cambia_nada_mas_de_0_05_mm(self, banco, virgen, variante, theta):
        referencia, _ = _resumen(banco, virgen, "A", 0.4)
        otro, _ = _resumen(banco, virgen, variante, theta)
        dif = _diferencias(referencia, otro)
        peor = max(dif, key=dif.get)
        assert dif[peor] <= 0.05, (variante, theta, peor, dif[peor])

    @pytest.mark.parametrize("variante, theta", [("B", 0.4), ("D", 0.4), ("L", 1.0)])
    def test_en_el_modo_automatico_la_pagina_y_el_giro_tampoco_corren_nada_mas_que_el_piso_cuantizado(self, banco, virgen, variante, theta):
        """Con el piso de las esquinas el unico cambio posible es el que mueve un nivel del piso (que se mide como mediana de numeros enteros): FWHM <= 0.05 mm en las capas de contraste alto y
        <= 0.15 en el azul, donde un nivel de piso son 0.13 mm."""
        referencia, _ = _resumen(banco, virgen, "A", 0.4, modo="automatico")
        otro, _ = _resumen(banco, virgen, variante, theta, modo="automatico")
        dif = _diferencias(referencia, otro)
        for (capa, que), valor in dif.items():
            assert valor <= (0.16 if capa == "B" else 0.07), (variante, theta, capa, que, valor)

    def test_un_error_de_unos_pocos_pixeles_de_las_marcas_no_cambia_lo_que_se_mide(self, banco, virgen):
        """Los clics del fisico caen a +-0.5 pixel de la marca (redondeados a entero): FWHM y lados cambian < 0.03 mm, y los dos 'centros' que dependen del cruce < 0.03 mm."""
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=1, ruido=0)
        exactos = medir_pelicula(pelicula, puntos_exactos(verdad), modo_piso="virgen", referencia_virgen=virgen)
        enteros = medir_pelicula(pelicula, verdad.clics_del_cuaderno(), modo_piso="virgen", referencia_virgen=virgen)
        a, b = Resumen(exactos), Resumen(enteros)
        dif = _diferencias(a, b)
        assert max(dif.values()) <= 0.06, max(dif.items(), key=lambda kv: kv[1])
        assert a.luz_menos_reticulo_mm == pytest.approx(b.luz_menos_reticulo_mm, abs=0.04)


# ======================================================================================================================================= los signos y los tres centros
class TestSignosYCentros:
    CALIB_DERECHA = dict(gen.CALIB, campo_luz_mm=(100.0, 99.0), luz_desplazada_mm=(-0.6, 0.0))      # la luz 0.6 mm a la izquierda de la radiacion = la radiacion 0.6 mm a la DERECHA
    CALIB_ARRIBA = dict(gen.CALIB, campo_luz_mm=(100.0, 99.0), luz_desplazada_mm=(0.0, 0.6))        # la luz 0.6 mm ABAJO de la radiacion = la radiacion 0.6 mm hacia ARRIBA (y hacia abajo en la imagen)

    @pytest.mark.parametrize("calib, esperado_coincidencia, esperado_centro", [
        ("derecha", {"izquierdo": -0.6, "derecho": 0.6, "superior": 0.0, "inferior": 0.0}, (0.6, 0.0)),
        ("arriba", {"izquierdo": 0.0, "derecho": 0.0, "superior": 0.6, "inferior": -0.6}, (0.0, -0.6)),
    ])
    def test_la_radiacion_corrida_0_6_mm_da_el_signo_de_afuera_en_cada_lado_y_el_centro_con_el_signo_de_la_imagen(self, banco, virgen, calib, esperado_coincidencia, esperado_centro):
        """x a la derecha, y hacia abajo: una radiacion corrida 0.6 mm a la derecha da derecho +0.6 (sobresale), izquierdo -0.6 (queda adentro) y radiacion - luz = (+0.6, 0). Corrida 0.6 mm hacia arriba: superior +0.6,
        inferior -0.6, radiacion - luz = (0, -0.6)."""
        c = self.CALIB_DERECHA if calib == "derecha" else self.CALIB_ARRIBA
        resumen, verdad = _resumen(banco, virgen, "A", 0.4, calib=c)
        azul = resumen.capas["B"]
        for lado in LADOS:
            assert azul["coincidencia"][lado] == pytest.approx(esperado_coincidencia[lado], abs=0.12), lado
        assert azul["radiacion_menos_luz"] == pytest.approx(esperado_centro, abs=0.1)
        assert verdad.centro_rad_menos_luz == pytest.approx(esperado_centro, abs=1e-6), "la verdad del generador dice lo mismo"
        # y para cada capa lo que predice el generador con el piso usado (las capas saturadas ensanchan los dos lados por igual: el centro no cambia)
        for capa in CAPAS:
            e = esperado(verdad, capa, resumen.capas[capa]["piso"], c)
            assert resumen.capas[capa]["radiacion_menos_luz"] == pytest.approx(e["radiacion_menos_luz"], abs=0.12), capa

    def test_radiacion_menos_reticulo_es_exactamente_la_suma_de_radiacion_menos_luz_y_luz_menos_reticulo(self, base):
        r = base.resultado
        for c in CAPAS:
            m = r.capas[c]
            for i in (0, 1):
                assert m.radiacion_menos_reticulo_mm[i] == pytest.approx(m.radiacion_menos_luz_mm[i] + r.luz_menos_reticulo_mm[i], abs=1e-9), (c, i)
        assert r.luz_menos_reticulo_mm == tuple(r.geometria.luz_menos_reticulo_girado_mm), "luz - reticulo es el de C.1, en el marco girado"
        v = base.verdad
        assert r.luz_menos_reticulo_mm == pytest.approx((-v.reticulo_menos_luz[0], -v.reticulo_menos_luz[1]), abs=0.03)

    def test_los_tres_centros_se_miden_contra_el_mismo_cruce_de_diagonales(self, base):
        """El centro de radiacion de cada capa es el punto medio de sus dos bordes y radiacion - luz es ese punto menos el cruce de diagonales (no el centro de los bordes luminosos de la linea)."""
        r = base.resultado
        cruce = r.girada.cruce
        for c in CAPAS:
            m = r.capas[c]
            cx = (m.crossplane.bordes_rad_px[0] + m.crossplane.bordes_rad_px[1]) / 2
            cy = (m.inplane.bordes_rad_px[0] + m.inplane.bordes_rad_px[1]) / 2
            assert m.centro_radiacion_px == pytest.approx((cx, cy), abs=1e-9)
            assert m.radiacion_menos_luz_mm == pytest.approx(((cx - cruce[0]) * TAM, (cy - cruce[1]) * TAM), abs=1e-9)
            assert m.radiacion_menos_reticulo_mm == pytest.approx(((cx - r.geometria.reticulo_girado[0]) * TAM, (cy - r.geometria.reticulo_girado[1]) * TAM), abs=1e-9)

    def test_el_fwhm_es_el_ancho_luminoso_de_la_linea_mas_las_dos_coincidencias(self, base):
        """La identidad en la que D.1 apoya lo que guarda (dentro de 1e-9 mm): FWHM = ancho luminoso + desfase de un lado + desfase del otro, en crossplane e inplane y en todas las capas."""
        r = base.resultado
        for c in CAPAS:
            m = r.capas[c]
            luz_x, luz_y = r.bordes_luz_px["crossplane"], r.bordes_luz_px["inplane"]
            assert m.crossplane.fwhm_mm == pytest.approx((luz_x[1] - luz_x[0]) * TAM + m.coincidencia_mm["izquierdo"] + m.coincidencia_mm["derecho"], abs=1e-9), c
            assert m.inplane.fwhm_mm == pytest.approx((luz_y[1] - luz_y[0]) * TAM + m.coincidencia_mm["superior"] + m.coincidencia_mm["inferior"], abs=1e-9), c

    def test_los_bordes_luminosos_son_los_de_la_linea_por_el_cruce_aunque_el_reticulo_este_lejos_y_el_campo_sea_un_trapecio(self):
        """La esquina inferior derecha 2.5 mm mas abajo (los lados ya no son paralelos) y el reticulo 4 mm bajo y a la derecha del cruce: la linea del perfil es la que pasa por el cruce de diagonales, no por
        el reticulo, y los bordes luminosos del resultado son los de ESA linea (entre las dos lineas la interseccion con los lados cambia mas de 0.3 pixel)."""
        pm = _pm()
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=2, ruido=0)
        ul, ur, dr, dl, c = puntos_exactos(verdad)
        r = medir_pelicula(pelicula, [ul, ur, (dr[0], dr[1] + 60.0), dl, (c[0] + 94.0, c[1] + 94.0)])
        assert r.ok, r.estado
        esquinas, reticulo = r.geometria.esquinas_giradas, r.geometria.reticulo_girado
        for i, eje in enumerate(EJES):
            por_el_cruce = pm.bordes_luz(eje, esquinas)
            assert r.bordes_luz_px[eje] == pytest.approx(por_el_cruce, abs=1e-12)
            por_el_reticulo = pm.bordes_luz(eje, esquinas, linea_px=reticulo[1 - i])
            assert max(abs(a - b) for a, b in zip(por_el_cruce, por_el_reticulo)) > 0.3, (eje, por_el_cruce, por_el_reticulo)

    def test_los_bordes_luminosos_del_resultado_son_los_de_la_funcion_sobre_las_esquinas_giradas(self, base):
        r = base.resultado
        for eje in EJES:
            assert r.bordes_luz_px[eje] == pytest.approx(_pm().bordes_luz(eje, r.geometria.esquinas_giradas), abs=1e-12)


# ======================================================================================================================================= cada capa por separado, sin marcas
class TestCadaCapaSeMideYSeMuestraPorSeparado:
    """PD3: R, G, B y el gris se miden cada uno con SUS numeros; ninguna regla las compara ni las marca («capa recortada», «poco fiable»...). El rojo del escaner llega a 0 en la meseta y se mide igual."""
    PALABRAS = re.compile(r"recortada|fiable|satur|compar|mejor|confiab|descart|inservible", re.I)      # «recortada» (la capa), no «recorte» (el margen de la pelicula, un parametro de la geometria)

    def test_el_rojo_recortado_por_el_escaner_se_mide_igual_y_sin_ninguna_marca(self, base):
        r = base.resultado
        rojo = r.capas["R"]
        assert rojo.crossplane.meseta < 3.0 and rojo.inplane.meseta < 3.0, "la meseta del rojo esta en el piso de la escala: el escaner la recorto"
        assert rojo.ok and rojo.estado == "ok" and rojo.crossplane.avisos == () and rojo.inplane.avisos == ()
        e = esperado(base.verdad, "R", rojo.piso)
        assert rojo.crossplane.fwhm_mm == pytest.approx(e["fwhm_crossplane"], abs=0.12)
        assert rojo.crossplane.fwhm_mm > r.capas["B"].crossplane.fwhm_mm + 3.0, "cada capa da SU ancho: el rojo no se 'corrige' hacia el azul"

    def test_ni_el_resultado_ni_las_medidas_tienen_un_campo_un_estado_o_un_aviso_que_hable_de_comparar_capas(self, base):
        pm = _pm()
        for clase in (pm.ResultadoPlacaMensual, pm.MedidaDeCapa, pm.MedidaDePerfil, pm.PerfilCentral, pm.PeliculaGirada):
            nombres = [f.name for f in dataclasses.fields(clase)]
            assert not [n for n in nombres if self.PALABRAS.search(n)], (clase.__name__, nombres)
        r = base.resultado
        textos = [r.estado] + [m.estado for m in r.capas.values()] + [a for m in r.capas.values() for e in (m.crossplane, m.inplane) for a in e.avisos]
        assert not [t for t in textos if self.PALABRAS.search(t)], textos
        assert not [k for k in pm.PARAMETROS if self.PALABRAS.search(k)]

    def test_las_cuatro_capas_dan_cuatro_anchos_distintos_y_en_el_orden_de_su_saturacion(self, base):
        """El azul (lineal) es el mas angosto, despues el verde, el gris y el rojo (saturado): la sintetica lo dice porque asi esta construida (R6); no es una eleccion de la aplicacion."""
        ancho = {c: base.resultado.capas[c].crossplane.fwhm_mm for c in CAPAS}
        assert ancho["B"] < ancho["G"] < ancho["gris"] < ancho["R"]
        assert ancho["R"] - ancho["B"] > 3.0

    def test_el_gris_se_mide_con_su_propio_piso_y_su_propia_meseta(self, base):
        gris = base.resultado.capas["gris"]
        assert gris.piso == pytest.approx(base.resultado.piso.valor("gris")) and gris.piso != base.resultado.capas["G"].piso
        assert gris.crossplane.meseta == pytest.approx(sum(PESOS_DEL_GRIS[c] * gen.CALIB["meseta_bgr"][gen.INDICE_CAPA[c]] for c in "BGR"), abs=0.6)


# ======================================================================================================================================= valores_medidos: lo unico que se guarda
class TestValoresMedidos:
    CLAVES = ("estado", "fwhm_crossplane_mm", "fwhm_inplane_mm", "desfase_izquierdo_mm", "desfase_derecho_mm", "desfase_superior_mm", "desfase_inferior_mm")

    def test_las_claves_son_las_de_d1_y_en_ese_orden(self, base):
        pm = _pm()
        assert pm.CLAVES_DE_VALORES_MEDIDOS == self.CLAVES
        assert tuple(pm.valores_medidos(base.resultado, "G")) == self.CLAVES

    @pytest.mark.parametrize("capa", ["R", "G", "B"])
    def test_son_los_de_la_capa_que_se_le_pasa_y_ninguna_otra(self, base, capa):
        r = base.resultado
        v = _pm().valores_medidos(r, capa)
        m = r.capas[capa]
        assert v["estado"] == "ok"
        assert v["fwhm_crossplane_mm"] == m.crossplane.fwhm_mm and v["fwhm_inplane_mm"] == m.inplane.fwhm_mm
        for lado in LADOS:
            assert v["desfase_" + lado + "_mm"] == m.coincidencia_mm[lado], lado
        assert all(isinstance(x, float) for k, x in v.items() if k != "estado")
        for otra in set("RGB") - {capa}:
            assert _pm().valores_medidos(r, otra)["fwhm_crossplane_mm"] != v["fwhm_crossplane_mm"]

    def test_el_gris_tambien_se_puede_pedir_y_la_capa_que_no_existe_es_value_error(self, base):
        pm = _pm()
        assert pm.valores_medidos(base.resultado, "gris")["fwhm_crossplane_mm"] == base.resultado.capas["gris"].crossplane.fwhm_mm
        for mala in ("X", "g", "", None, "verde"):
            with pytest.raises(ValueError):
                pm.valores_medidos(base.resultado, mala)

    def test_no_depende_de_la_capa_por_omision_de_los_menus(self, base, monkeypatch):
        pm, pel = _pm(), _pel()
        antes = {c: pm.valores_medidos(base.resultado, c) for c in "RGB"}
        monkeypatch.setattr(pel, "CAPA_POR_OMISION", "B")
        assert {c: pm.valores_medidos(base.resultado, c) for c in "RGB"} == antes

    def test_un_resultado_que_no_se_pudo_medir_da_su_motivo_y_ningun_numero(self, base):
        pm = _pm()
        res = pm.analizar(base.pelicula, base.puntos, _P(), modo_piso="virgen")
        v = pm.valores_medidos(res, "G")
        assert v["estado"] == res.capas["G"].estado and v["estado"].startswith("no medible")
        assert all(v[k] is None for k in self.CLAVES[1:])

    def test_si_falta_un_lado_los_demas_se_guardan_y_el_estado_dice_por_que(self, base, monkeypatch):
        """La capa donde un borde no se alcanzo: el estado es el motivo (nunca «ok» con un vacio) y los lados que SI se midieron conservan su numero."""
        pm = _pm()
        original = pm.medir_perfil

        def sin_borde_derecho(perfil, *a, **k):
            m = original(perfil, *a, **k)
            if perfil.capa == "G" and perfil.eje == "crossplane":
                return dataclasses.replace(m, estado="no medible: no se encuentra el borde derecho al 50 %", bordes_rad_px=(m.bordes_rad_px[0], None), fwhm_mm=None, centro_rad_px=None)
            return m
        monkeypatch.setattr(pm, "medir_perfil", sin_borde_derecho)
        res = pm.analizar(base.pelicula, base.puntos, _P())
        v = pm.valores_medidos(res, "G")
        assert v["estado"].startswith("no medible") and "derecho" in v["estado"]
        assert v["fwhm_crossplane_mm"] is None and v["desfase_derecho_mm"] is None
        assert v["desfase_izquierdo_mm"] is not None and v["fwhm_inplane_mm"] is not None and v["desfase_superior_mm"] is not None and v["desfase_inferior_mm"] is not None

    def test_el_fwhm_guardado_es_el_ancho_luminoso_mas_los_dos_desfases_guardados(self, base):
        """D.1 lo verifica sobre lo guardado: FWHM = ancho luminoso del motor en esa linea + desfase izquierdo + desfase derecho (dentro de 1e-9 mm), en crossplane e inplane, para cada capa elegida."""
        pm, r = _pm(), base.resultado
        luz_x, luz_y = r.bordes_luz_px["crossplane"], r.bordes_luz_px["inplane"]
        for c in "RGB":
            v = pm.valores_medidos(r, c)
            assert v["fwhm_crossplane_mm"] == pytest.approx((luz_x[1] - luz_x[0]) * TAM + v["desfase_izquierdo_mm"] + v["desfase_derecho_mm"], abs=1e-9)
            assert v["fwhm_inplane_mm"] == pytest.approx((luz_y[1] - luz_y[0]) * TAM + v["desfase_superior_mm"] + v["desfase_inferior_mm"], abs=1e-9)

    def test_es_json_y_el_resultado_entero_tambien_lo_es_sin_arreglos(self, base):
        pm = _pm()
        json.dumps(pm.valores_medidos(base.resultado, "G"))
        d = base.resultado.como_dict()
        texto = json.dumps(d)
        assert len(texto) < 200_000, "sin los perfiles ni los arreglos: solo numeros y textos"
        assert d["version"] == "PM-1" and d["estado"] == "ok" and set(d["capas"]) == set(CAPAS)
        assert d["parametros"] == _P() and d["piso"]["estado"] == "ok" and d["geometria"]["estado"] == "ok"
        assert d["capas"]["G"]["crossplane"]["fwhm_mm"] == base.resultado.capas["G"].crossplane.fwhm_mm


# ======================================================================================================================================= el suavizado, sobre la pelicula
class TestUnaMotaFinaNoMueveElCorteCentral:
    """(7) del bloque: EPSON007 azul inplane da 96.04 mm con una mota sobre la linea central y ~99.3 con el suavizado de 0.5 mm del perfil antes de buscar el cruce (el barrido de C.3 lo deja ver).
    Aqui, una raya fina y clara (2 pixeles, nivel 120) a 44 mm del campo, entre la zona central y el borde: sin suavizar el primer cruce desde la meseta es la raya."""

    def test_la_raya_no_cambia_el_fwhm_con_el_suavizado_y_lo_destruye_sin_el(self):
        defecto = [{"tipo": "rayon_v", "u_mm": -44.0, "largo_mm": 40.0, "valor": 120.0, "ancho_px": 2}]
        limpia, pel_limpia = sintetica(variante="A", theta=0.0, seed=2, ruido=0)
        mota, pel_mota = sintetica(variante="A", theta=0.0, seed=2, ruido=0, defectos=defecto)
        a = medir_pelicula(pel_limpia, puntos_exactos(limpia))
        b = medir_pelicula(pel_mota, puntos_exactos(mota))
        c = medir_pelicula(pel_mota, puntos_exactos(mota), P=_P(suavizado_perfil_mm=0.0))
        for capa in ("R", "G", "B", "gris"):
            assert _fwhm(b, capa, "crossplane") == pytest.approx(_fwhm(a, capa, "crossplane"), abs=0.03), capa
        assert abs(_fwhm(c, "B", "crossplane") - _fwhm(a, "B", "crossplane")) > 3.0 or not c.capas["B"].crossplane.ok, "sin el suavizado, la raya si es el 'borde'"
        assert b.parametros["suavizado_perfil_mm"] == 0.5 and c.parametros["suavizado_perfil_mm"] == 0.0

    def test_el_suavizado_no_corre_el_borde_de_una_pelicula_limpia(self, banco, virgen):
        """Sin sesgo medible: sobre la sintetica sin ruido, el suavizado (un nucleo simetrico) no corre el cruce al 50 %. Cada medida, con y sin el, cae a menos de 0.05 mm de lo que predice el generador
        (una pelicula de 8 bits tiene niveles enteros: un cruce se mueve hasta ~0.04 mm en las capas de pendiente suave, mas que cualquier sesgo del nucleo), y el promedio CON SIGNO de las diferencias
        suavizado menos sin suavizar es < 0.012 mm: no hay un corrimiento sistematico hacia ningun lado."""
        verdad, pelicula = sintetica(variante="A", theta=0.4, seed=1, ruido=0)
        puntos = puntos_exactos(verdad)
        con = Resumen(medir_pelicula(pelicula, puntos, modo_piso="virgen", referencia_virgen=virgen))
        sin = Resumen(medir_pelicula(pelicula, puntos, P=_P(suavizado_perfil_mm=0.0), modo_piso="virgen", referencia_virgen=virgen))
        con_signo = []
        for capa in CAPAS:
            e = esperado(verdad, capa, con.capas[capa]["piso"])
            verdades = {"fwhm_crossplane": e["fwhm_crossplane"], "fwhm_inplane": e["fwhm_inplane"], **{"coincidencia_" + l: e["coincidencia"][l] for l in LADOS}}
            for resumen, nombre in ((con, "con"), (sin, "sin")):
                x = resumen.capas[capa]
                medidas = {"fwhm_crossplane": x["fwhm_crossplane"], "fwhm_inplane": x["fwhm_inplane"], **{"coincidencia_" + l: x["coincidencia"][l] for l in LADOS}}
                for clave, valor in medidas.items():
                    assert abs(valor - verdades[clave]) < 0.05, (nombre, capa, clave, valor, verdades[clave])
            for clave in ("fwhm_crossplane", "fwhm_inplane"):
                con_signo.append(con.capas[capa][clave] - sin.capas[capa][clave])
            for lado in LADOS:
                con_signo.append(con.capas[capa]["coincidencia"][lado] - sin.capas[capa]["coincidencia"][lado])
        assert len(con_signo) == 6 * len(CAPAS)
        assert abs(sum(con_signo) / len(con_signo)) < 0.012, sum(con_signo) / len(con_signo)
        assert max(abs(d) for d in con_signo) < 0.05, max(con_signo, key=abs)

    def test_con_el_ruido_del_escaner_el_suavizado_reduce_la_dispersion_del_azul_y_no_le_agrega_sesgo(self):
        """La medida que justifica adoptar los 0.5 mm (se repite con `scripts/c2_medir_suavizado.py`): en el azul, la capa de menor contraste, con el ruido del escaner el error contra lo que predice el
        generador tiene un rms de ~0.014 a 0.019 mm con el suavizado y de ~0.037 sin el (el primer cruce desde la meseta lo adelanta el ruido: sesgo -0.007 a -0.021). Cuatro semillas, seis medidas
        por semilla: el rms con el suavizado es menos de 0.65 del rms sin el, su sesgo es < 0.015 mm y ningun error pasa de 0.07 mm."""
        con, sin = [], []
        for semilla in (1, 2, 3, 4):
            verdad, pelicula = sintetica(variante="A", theta=0.4, seed=semilla)
            puntos = puntos_exactos(verdad)
            for lista, P in ((con, _P()), (sin, _P(suavizado_perfil_mm=0.0))):
                x = Resumen(medir_pelicula(pelicula, puntos, P=P)).capas["B"]
                e = esperado(verdad, "B", x["piso"])
                lista.extend([x["fwhm_crossplane"] - e["fwhm_crossplane"], x["fwhm_inplane"] - e["fwhm_inplane"]] + [x["coincidencia"][l] - e["coincidencia"][l] for l in LADOS])
        rms = lambda v: math.sqrt(sum(d * d for d in v) / len(v))
        assert len(con) == len(sin) == 24
        assert rms(con) < 0.65 * rms(sin), (rms(con), rms(sin))
        assert abs(sum(con) / len(con)) < 0.015, sum(con) / len(con)
        assert max(abs(d) for d in con) < 0.07, max(con, key=abs)


# ======================================================================================================================================= memoria
VMHWM = r'''
import os, sys, threading, time
RAIZ, RUTA = sys.argv[1], sys.argv[2]
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "tests"))
import numpy as np, cv2
from analisisImagenes import pelicula as pel, placa_mensual as pm

def rss_mb():
    with open("/proc/self/statm") as f:
        return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6

class Pico:
    def __init__(self):
        self.max, self.vivo = rss_mb(), True
        self.hilo = threading.Thread(target=self.vigilar, daemon=True); self.hilo.start()
    def vigilar(self):
        while self.vivo:
            self.max = max(self.max, rss_mb()); time.sleep(0.003)
    def parar(self):
        self.vivo = False; self.hilo.join(); self.max = max(self.max, rss_mb()); return self.max

P = dict(pm.VALORES_DE_LA_GEOMETRIA)
CLICS = [(206, 150), (2552, 154), (2536, 2508), (181, 2487), (1381, 1337)]
p = pel.leer_pelicula(open(RUTA, "rb").read())
for c in ("R", "G", "B", "gris"):
    getattr(p, c)
marcas = [pm.refinar_marca(p.gris, q, P, validos=p.validos) for q in CLICS]
base = rss_mb()
pico = Pico()
res = pm.analizar(p, marcas, P)
analizar_mb = pico.parar() - base
estado = res.estado
retenido_mb = res.memoria_bytes() / 1e6
del res
import gc; gc.collect()
cl = pm.clasificar_puntos(marcas)
g = pm.geometria_luz(cl.esquinas, cl.reticulo, 25.4 / 600)
base2 = rss_mb()
pico = Pico()
completa = [cv2.warpAffine(getattr(p, c), np.array(g.matriz_de_giro), (p.R.shape[1], p.R.shape[0]), flags=cv2.INTER_LINEAR) for c in ("R", "G", "B", "gris")]
pagina_entera_mb = pico.parar() - base2
print("RESULTADO", estado, round(analizar_mb, 1), round(pagina_entera_mb, 1), round(retenido_mb, 1), round(base, 1))
'''


class TestMemoriaYTiempo:
    def test_analizar_una_pagina_entera_cuesta_mucho_menos_que_girarla(self, tmp_path):
        """Medido en un proceso aparte (EPSON027: 6600 x 5100, con sus cuatro capas ya leidas): lo que `analizar` suma al pico, contra lo que costaria girar la pagina entera (+984 MB y 3 a 6 s en la medicion
        del plan; recortando antes +352 MB y 0.7 a 1.7 s)."""
        ruta = _real("EPSON027")
        guion = tmp_path / "medir_memoria.py"
        guion.write_text(VMHWM, encoding="utf-8")
        r = subprocess.run([sys.executable, "-u", str(guion), str(RAIZ), ruta], capture_output=True, text=True, timeout=900, cwd=tmp_path)
        assert r.returncode == 0, r.stderr[-1500:]
        linea = [l for l in r.stdout.splitlines() if l.startswith("RESULTADO")][-1].split()
        estado, analizar_mb, entera_mb, retenido_mb = " ".join(linea[1:-4]), float(linea[-4]), float(linea[-3]), float(linea[-2])
        assert estado == "ok"
        assert analizar_mb < 0.75 * entera_mb, (analizar_mb, entera_mb)
        assert analizar_mb < 700.0, analizar_mb
        assert retenido_mb < 200.0, "el resultado retiene la pelicula recortada y girada (cuatro capas), no la pagina"

    @pytest.mark.parametrize("variante", ["A", "B", "D"])
    def test_lo_que_retiene_el_resultado_es_la_pelicula_girada_y_no_depende_del_tamano_de_la_pagina(self, banco, variante):
        """El recorte A es la pelicula sola (2689 x 2715 px); B y D son la misma pelicula con el borde del escaner que la rodea, en una pagina de 3300 x 3300 y en otra de 4400 x 3300 (un tercio mas de
        pixeles): lo que retiene el resultado de B y de D es lo mismo (el borde del escaner suma ~6 % a la pelicula sola; la pagina no suma nada)."""
        verdad, pelicula = sintetica(variante=variante, theta=0.4, seed=1, ruido=0)
        res = medir_pelicula(pelicula, puntos_exactos(verdad))
        alto, ancho = res.girada.capas["G"].shape
        assert alto < 2950 and ancho < 2950, "el recorte es la pelicula (115 x 116 mm = 2717 x 2740 px) mas un margen"
        banco[("memoria", variante)] = res.memoria_bytes()
        assert res.memoria_bytes() < 2950 * 2950 * 19
        otra = banco.get(("memoria", "B" if variante == "D" else "D")) if variante != "A" else None
        if otra is not None:
            assert max(res.memoria_bytes(), otra) / min(res.memoria_bytes(), otra) < 1.05
        del res

    def test_apenas_se_descarta_el_resultado_se_sueltan_las_capas_giradas_y_no_se_retiene_la_pelicula(self):
        verdad, pelicula = sintetica(variante="D", theta=0.4, seed=1, ruido=0)
        res = medir_pelicula(pelicula, puntos_exactos(verdad))
        de_la_pelicula = weakref.ref(pelicula)
        de_la_capa = weakref.ref(res.girada.capas["G"])
        de_la_mascara = weakref.ref(res.girada.pelicula)
        del pelicula
        assert de_la_pelicula() is None, "el resultado no guarda la pelicula (ni, con ella, la pagina entera)"
        assert de_la_capa() is not None
        del res
        gc.collect()
        assert de_la_capa() is None and de_la_mascara() is None

    def test_analizar_una_pelicula_de_600_dpi_tarda_segundos(self, base):
        import time
        t0 = time.perf_counter()
        _pm().analizar(base.pelicula, base.puntos, _P())
        assert time.perf_counter() - t0 < 25.0


# ======================================================================================================================================= las peliculas reales
# Los cinco puntos (UL, UR, DR, DL y el reticulo) de las diez peliculas mensuales reales: los de ML0 son los clics del cuaderno del fisico; los de EPSON027, los de ML0 mas el desplazamiento exacto (10, 7)
# de ML0 dentro de la pagina (A.2); los demas, marcas localizadas con scripts/med_mensual_marcas.py y llevadas entre archivos de la misma pelicula (anexo, logs/MED_mensual). EPSON029: la esquina UL esta ESTIMADA.
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
# lo que midieron R5 y R6 sobre estas peliculas con el piso corregido (valor de pixel): azul 97.8-100.5, verde 99.9-102.2, rojo 102.5-104.7 mm; margenes de 1 mm para el gris y los extremos
RANGOS_DE_FWHM = {"R": (101.5, 105.5), "G": (98.8, 102.8), "B": (96.8, 101.2), "gris": (99.5, 103.5)}


def _real_resumen(banco, clave):
    k = ("real", clave)
    if k not in banco:
        pm, pel = _pm(), _pel()
        pelicula = pel.leer_pelicula(Path(_real(clave)).read_bytes())
        marcas = [pm.refinar_marca(pelicula.gris, punto, _P(), validos=pelicula.validos) for punto in CLICS_REALES[clave]]
        res = pm.analizar(pelicula, marcas, _P())
        assert res.ok, (clave, res.estado)
        banco[k] = Resumen(res)
        del res, pelicula, marcas
        gc.collect()
    return banco[k]


class TestPeliculasReales:
    @pytest.mark.parametrize("clave", sorted(CLICS_REALES))
    def test_cada_pelicula_real_se_mide_en_las_cuatro_capas_dentro_de_lo_que_midio_el_plan(self, banco, clave):
        r = _real_resumen(banco, clave)
        for c in CAPAS:
            m = r.capas[c]
            assert m["estado"] == "ok", (clave, c, m["estado"])
            for eje in ("fwhm_crossplane", "fwhm_inplane"):
                assert RANGOS_DE_FWHM[c][0] < m[eje] < RANGOS_DE_FWHM[c][1], (clave, c, eje, m[eje])
        # el ancho de las capas sigue el orden de su saturacion (R6): azul < verde < gris < rojo, en los dos ejes
        for eje in ("fwhm_crossplane", "fwhm_inplane"):
            assert r.capas["B"][eje] < r.capas["G"][eje] < r.capas["gris"][eje] < r.capas["R"][eje], (clave, eje)

    @pytest.mark.parametrize("par, tolerancia", [
        (("ML0", "EPSON027"), 0.1),
        (("EPSON001_JPG", "EPSON001_TIF"), 0.1),
        (("EPSON007", "EPSON008_TIF"), 0.3),
    ])
    def test_la_misma_pelicula_en_dos_archivos_da_lo_mismo(self, banco, par, tolerancia):
        """ML0 y EPSON027 son la misma pelicula (ML0 es un recorte de la pagina); EPSON001.jpg y .TIF son la misma imagen en dos formatos; EPSON007 y EPSON008 son dos escaneos de la misma pelicula (que sigue
        oscureciendo entre uno y otro). Plan: +-0.1 mm, +-0.1 mm y +-0.3 mm. Lo que el plan no ve: el piso es la mediana de numeros ENTEROS y dos archivos pueden dar pisos que difieren en uno o mas
        niveles (EPSON001: 80 y 79 en el azul; EPSON007 y 008: 81 y 84 en el azul y 112 y 113 en el rojo), y cada nivel de piso mueve el FWHM SIGMA sqrt(2 pi) / contraste mm (0.13 mm en el azul, de unos 40
        niveles de contraste; 0.04 en las demas): esa diferencia viene del piso y no de la medida. Se permite lo que diga el plan o lo que el piso explique (0.1 mm + ese corrimiento), lo que sea mayor
        (decision del implementador, vetable: C2-D4)."""
        a, b = _real_resumen(banco, par[0]), _real_resumen(banco, par[1])
        dif = _diferencias(a, b)
        malas = {}
        for (capa, que), valor in dif.items():
            x, y = a.capas[capa], b.capas[capa]
            contraste = x["piso"] - sum(x["meseta"]) / 2.0
            por_el_piso = 0.1 + SIGMA * math.sqrt(2.0 * math.pi) / contraste * abs(x["piso"] - y["piso"])
            if valor > max(tolerancia, por_el_piso):
                malas[(capa, que)] = (round(valor, 3), round(max(tolerancia, por_el_piso), 3))
        assert not malas, (par, malas)
        assert a.luz_menos_reticulo_mm == pytest.approx(b.luz_menos_reticulo_mm, abs=0.05)

    def test_la_pagina_entera_y_el_recorte_de_la_misma_pelicula_dan_el_mismo_piso_y_el_mismo_angulo(self, banco):
        a, b = _real_resumen(banco, "ML0"), _real_resumen(banco, "EPSON027")
        assert a.angulo == pytest.approx(b.angulo, abs=0.005)
        for c in CAPAS:
            assert a.capas[c]["piso"] == pytest.approx(b.capas[c]["piso"], abs=1.0)

    def test_epson007_azul_inplane_con_la_mota_sobre_la_linea_central_ya_no_da_96_mm(self, banco):
        """Sin el suavizado del perfil esta cifra es 96.04 mm (la mota cruza la altura media); con el suavizado de 0.5 mm queda con sus vecinas (99.3)."""
        r = _real_resumen(banco, "EPSON007")
        assert r.capas["B"]["fwhm_inplane"] > 98.5, r.capas["B"]["fwhm_inplane"]


# ======================================================================================================================================= la estructura del modulo
def _arbol():
    return ast.parse(MODULO.read_text(encoding="utf-8"))


def _funcion(arbol, nombre):
    return next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == nombre)


def _flotantes(nodo):
    return [n.value for n in ast.walk(nodo) if isinstance(n, ast.Constant) and type(n.value) is float]


class TestLaEstructuraDelModulo:
    FUNCIONES_QUE_MIDEN = ("girar", "perfil_central", "medir_perfil", "bordes_luz", "coincidencia", "analizar", "valores_medidos")

    def test_las_funciones_de_c2_existen_con_la_firma_del_plan(self):
        pm = _pm()
        import inspect
        assert list(inspect.signature(pm.girar).parameters)[:2] == ["pelicula", "M"]
        assert list(inspect.signature(pm.perfil_central).parameters)[:3] == ["capa", "eje", "P"]
        assert list(inspect.signature(pm.medir_perfil).parameters)[:5] == ["perfil", "centro_px", "piso", "base", "P"]
        assert list(inspect.signature(pm.bordes_luz).parameters)[:2] == ["eje", "esquinas_giradas"]
        assert list(inspect.signature(pm.coincidencia).parameters)[:2] == ["bordes_rad", "bordes_luz"]
        sig = inspect.signature(pm.analizar)
        assert list(sig.parameters) == ["pelicula", "puntos", "parametros", "modo_piso", "punto_manual", "referencia_virgen"]
        assert [sig.parameters[k].default for k in ("modo_piso", "punto_manual", "referencia_virgen")] == [None, None, None]
        assert list(inspect.signature(pm.valores_medidos).parameters) == ["resultado", "capa"]

    def test_valores_medidos_es_la_unica_definicion_de_lo_que_se_guarda(self):
        """Los nombres de lo guardado viven en UN sitio (`CLAVES_DE_VALORES_MEDIDOS`) y `valores_medidos` es la unica funcion que arma ese diccionario."""
        arbol = _arbol()
        literales = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and n.value == "fwhm_crossplane_mm"]
        assert len(literales) == 1, "el nombre de cada valor guardado se escribe una sola vez"
        definiciones = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "valores_medidos"]
        assert len(definiciones) == 1
        llamadas = [n for n in ast.walk(definiciones[0]) if isinstance(n, ast.Name) and n.id == "CLAVES_DE_VALORES_MEDIDOS"]
        assert llamadas, "valores_medidos arma el diccionario con CLAVES_DE_VALORES_MEDIDOS"

    def test_solo_una_llamada_a_piso_de_pelicula_y_vive_en_analizar(self):
        arbol = _arbol()
        llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "piso_de_pelicula"]
        assert len(llamadas) == 1
        analizar = _funcion(arbol, "analizar")
        assert llamadas[0] in list(ast.walk(analizar))

    def test_ningun_valor_de_la_medida_vive_como_numero_magico_en_las_funciones_que_miden(self):
        """PD1: 0.8 (la fraccion de la meseta y la penumbra alta), 0.4, 0.2, 3.8, 0.5 y 1.0 estan en `PARAMETROS`, no en el cuerpo de las funciones de C.2."""
        arbol = _arbol()
        for nombre in self.FUNCIONES_QUE_MIDEN:
            sueltos = [x for x in _flotantes(_funcion(arbol, nombre)) if x in (0.8, 0.4, 0.2, 3.8, 0.5, 1.0, 0.80, 25.4, 600.0)]
            assert not sueltos, (nombre, sueltos)

    def test_ninguna_ventana_se_ubica_con_el_centro_del_arreglo(self):
        """El defecto N3 del cuaderno (`shape//2`): ni una division por 2 del tamano del arreglo en el modulo."""
        for n in ast.walk(_arbol()):
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.FloorDiv, ast.Div)) and isinstance(n.right, ast.Constant) and n.right.value == 2:
                texto = ast.unparse(n.left)
                assert "shape" not in texto and "len(" not in texto, ast.unparse(n)

    def test_los_parametros_de_la_medida_son_estos_y_cada_uno_se_usa(self):
        pm = _pm()
        assert set(pm.PARAMETROS_DE_LA_MEDIDA) == {"margen_recorte_mm", "banda_perfil_mm", "fraccion_meseta", "excepcion_centro_mm", "muestras_minimas_de_la_meseta",
                                                  "altura_media", "penumbra_alta", "penumbra_baja", "suavizado_perfil_mm"}
        usados = {n.slice.value for n in ast.walk(_arbol()) if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "P"
                  and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
        assert set(pm.PARAMETROS_DE_LA_MEDIDA) <= usados, set(pm.PARAMETROS_DE_LA_MEDIDA) - usados
        for nombre in pm.PARAMETROS_DE_LA_MEDIDA:
            assert pm.PARAMETROS[nombre] == pm.PARAMETROS_DE_LA_MEDIDA[nombre] and pm.VALORES_DE_LA_GEOMETRIA[nombre] == pm.PARAMETROS_DE_LA_MEDIDA[nombre]["valor"]
        assert pm.VALORES_DE_LA_GEOMETRIA["suavizado_perfil_mm"] == 0.5

    def test_las_funciones_de_c1_siguen_siendo_las_de_c1(self):
        """C.2 agrega y no cambia: las funciones y clases de C.1 siguen en el modulo con su firma (la igualdad del AST contra HEAD la prueba la compuerta del anexo)."""
        pm = _pm()
        for nombre in ("clasificar_puntos", "refinar_marca", "geometria_luz", "matriz_giro", "transformar_puntos", "recuadro_luminoso", "punto_de_medida"):
            assert callable(getattr(pm, nombre)), nombre
        for clase in ("PuntosClasificados", "MarcaRefinada", "RecuadroLuminoso", "GeometriaLuz"):
            assert dataclasses.is_dataclass(getattr(pm, clase)), clase
        assert pm.VERSION_ALGORITMO == "PM-1"

    def test_los_motivos_de_no_medible_empiezan_por_no_medible_para_quien_pregunta_startswith(self, base):
        pm = _pm()
        perfil, c = perfil_erf(ancho_mm=60.0)
        assert medir(perfil, c).estado.startswith("no medible")
        assert pm.AVISO_PENUMBRA_INCOMPLETA.format(porcentaje=20) == "incompleta: el perfil llega al borde de la película antes del 20 %"
