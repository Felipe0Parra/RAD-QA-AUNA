"""A.3 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-86): EL PISO POR ESQUINAS, con su rango esperado y su respaldo, un selector de modo (automatico, punto marcado, pelicula virgen) y la
funcion de la PELICULA VIRGEN.

CAUSA (medida el 13-10, borradores/A3/diseno_A3_Opus.md §1): el piso de A.2 tomaba el 20 % mas lejano de TODA la pelicula de fuera del campo, que en las 10 reales es solo un 20-29 % de cuña de
esquina y un 28-39 % de lateral central; en el centro de cada lado el rojo esta 11 a 38 niveles por debajo del de las esquinas, asi que el piso salia R -9 a -16, G -4 a -10 niveles mas oscuro
y el FWHM mas corto. Ademas no habia rango declarado (un fondo neutro por debajo de 170 daba «ok»), ni forma de dar el piso con una pelicula virgen escaneada aparte, ni de pasar de un modo a otro.

LO QUE SE GARANTIZA (a-m del PROTOCOLO de A.3), cada cosa contra una verdad que NO sale de la funcion (las sinteticas de PF.0 y el ORACULO de `tests/_oraculo_piso.py`: pelicula conocida,
distancia por rasterizacion, cuñas como conos normales rasterizados):
  (a) EL SELECTOR: `MODO_DEL_PISO_POR_OMISION` se define UNA vez; `modo=None` hace lo de A.2; el modo «virgen» sin referencia es «no medible», nunca el automatico; formas equivocadas de llamar son `ValueError`.
  (b) LAS ESQUINAS: la region es la union de las cuatro cuñas (lo mas lejano de cada una) y el piso es la verdad del generador +-1 nivel; oscurecer el CENTRO de los lados no lo mueve.
  (c) LAS DIEZ REALES: la tabla del diseño (§1.5), exacta: piso por capa, pixeles, distancia, y el estado de cada esquina (EPSON001: la inferior izquierda, dispersa, la reemplaza el giro +5).
  (d) EL RANGO Y EL FONDO: un fondo neutro de 169, 150 o 100 ya no pasa por pelicula; una pelicula con el rojo 65 niveles mas claro es «no medible»; los limites son inclusivos.
  (e) EL RESPALDO: una etiqueta en una esquina la reemplaza el giro (el signo de «+»); en dos esquinas no hay respaldo; el orden de los seis candidatos; ninguno entra a la zona prohibida;
      la ventana va a la mayor distancia que la pelicula deja; un recorte demasiado ajustado es «no medible» con su propio motivo.
  (f) EL FLECO DEL CORTE: el anillo de 1 mm junto al corte y junto al borde de la imagen no entra al piso.
  (g) LA PELICULA VIRGEN: los escenarios del prototipo, cada uno con la comprobacion que rechaza o avisa.
  (h) LA PERSISTENCIA: guardar, leer, archivar la anterior sin borrar nada, escritura atomica; y (ronda 1 de la revision, 13-10: RV-A3-1 y RV-A3-3) frente a lo alterado y a lo dañado: un JSON anterior
      que no se puede leer se archiva igual, un escaneo ya copiado con otro contenido se rechaza sin tocar nada, y un archivo dañado o con un valor del TIPO equivocado se rechaza al LEERLO con
      `ValueError` (nunca otra excepcion, ni mas tarde al usarlo). Y (A3-M2, 14-10, RV-A3-2; decision de Opus vetable por el fisico) la anterior se archiva SIEMPRE que el contenido cambie, tambien
      con la misma huella sha256 (otro usuario, otra fecha de calculo, otra orientacion declarada, otros parametros u otro instante de guardado): solo un guardado IDENTICO, byte a byte, a lo
      que se va a escribir no archiva nada.
  (i) EL MODO VIRGEN: el piso es el de la virgen, la comparacion con el automatico, la virgen mas oscura, otra cadena de captura, la copia guardada.
  (j) LOS TEXTOS: sin simbolos de correcto o incorrecto (DA-18).
  (k) LA ESTRUCTURA: una sola definicion; ni Qt ni base de datos; ningun literal de parametro en las funciones; el piso se toma sobre la imagen SIN girar (por AST, `pelicula.py` no llama
      warpAffine, warpPerspective, getRotationMatrix2D, rot90 ni nada que se llame rotate: el «giro» del respaldo es solo la direccion de la ventana, con vectores).
  (l) MEMORIA Y TIEMPO.  (m) LA RANURA DE LA VIRGEN REAL: mide si existe `VIRGEN*` y PASA si no (nunca `pytest.skip`: el conteo de skips de la suite es EXACTAMENTE 4).

Rojo contra HEAD (975344c): HEAD no tiene el selector, las esquinas ni la virgen; las pruebas que usan nombres nuevos caen con su error y las que miden (las diez reales, el rango) caen por su
aserción (A.2 daba 101/173/86/142 donde las esquinas dan 110/177/82/146). El rojo SUSTANTIVO esta en `a3_mutaciones.py rojo` del anexo.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import gc
import hashlib
import importlib
import io
import json
import math
import time
import tokenize
import tracemalloc
from pathlib import Path

import cv2
import numpy as np
import pytest
import tifffile

import _corpus
import _placa_mensual_sintetica as gen
import test_a2_piso_de_pelicula as A2
from _oraculo_piso import Oraculo
from analisisImagenes import posicion_inicial_braqui as motor

RAIZ = Path(__file__).resolve().parent.parent
ESC = A2.ESC
CAPAS = ("R", "G", "B", "gris")
ESQUINAS = ("UL", "UR", "DR", "DL")
NOMBRE_DE_ESQUINA = {"UL": "superior izquierda", "UR": "superior derecha", "DR": "inferior derecha", "DL": "inferior izquierda"}
CLICS_REALES = A2.CLICS_REALES

# Los parametros del diseño (§7), escritos AQUI a proposito: la prueba fija los valores, no los importa.
PISO_ESPERADO = {"R": [60.0, 140.0], "G": [145.0, 200.0], "B": [65.0, 100.0], "gris": [110.0, 170.0]}
PISO_ESPERADO_SIN_IRRADIAR = {"R": [60.0, 170.0], "G": [145.0, 230.0], "B": [65.0, 130.0], "gris": [110.0, 200.0]}
PLAN_A3 = {"margen_borde_mm": 1.0, "apartar_borde_de_la_imagen": True, "piso_esperado": PISO_ESPERADO, "piso_esperado_sin_irradiar": PISO_ESPERADO_SIN_IRRADIAR,
           "iqr_maximo": 15.0, "esquinas_minimas": 3, "giro_respaldo_grados": 5.0, "s_respaldo": [0.05, 0.10], "distancia_respaldo_maxima_mm": 11.0, "paso_respaldo_mm": 0.5,
           "tolerancia_virgen_mas_oscura": 3.0, "aviso_azul_virgen": 5.0, "aviso_verde_virgen": 25.0}
PLAN_DEL_PISO = {**A2.PLAN, **PLAN_A3}
# OD.1 (21-10): el recorte (C3), la uniformidad (C5) y las motas (C6) AVISAN y ya no rechazan: se retiran `recorte_rechazo`, `cv_rechazo`, `dev_rechazo` y `motas_rechazo_fraccion`; se suma
# `lado_region_uniformidad_virgen_mm` (las cinco regiones de 10 x 10 mm de la tabla de uniformidad y ruido, como el Catphan).
PLAN_DE_LA_VIRGEN = {
    "margen_borde_virgen_mm": 2.0, "area_minima_virgen_mm2": 400.0, "lado_bloque_virgen_mm": 5.0, "bloques_minimos_virgen": 4, "recorte_aviso": 0.0001,
    "distancia_fondo_mm": 2.0, "borde_imagen_fondo_mm": 1.0, "pixeles_fondo_minimos": 10000, "fondo_blanco_minimo": 0.995,
    "cv_aviso": {"R": 0.015, "G": 0.010, "B": 0.015, "gris": 0.010},
    "dev_aviso": {"R": 0.03, "G": 0.02, "B": 0.03, "gris": 0.02},
    "gradiente_aviso_pct_por_10cm": 1.0, "extension_minima_gradiente_mm": 60.0, "ventana_motas_mm": 1.3, "motas_sigmas": 6.0, "motas_niveles": 8.0, "motas_pixeles_grupo": 3,
    "dilatacion_tinta_y_motas_mm": 0.5, "motas_aviso_fraccion": 0.0005, "motas_aviso_grupo_mm2": 0.2, "lado_region_uniformidad_virgen_mm": 10.0, "ventana_ruido_mm": 0.5,
    "ruido_aviso": {"R": 3.5, "G": 2.5, "B": 3.5}, "ventana_rayas_mm": 2.0, "rayas_aviso_niveles": 1.0, "azul_testigo": [75.0, 95.0], "calidad_jpeg_editor": 90.0}
ABIERTO = {"piso_esperado": {c: [0.0, 255.0] for c in CAPAS}, "iqr_maximo": 255.0}          # el rango y el IQR abiertos: lo que el control de la regla (7) necesita

# La tabla del diseño §1.5 (prototipo de Opus a3_prototipo_piso.py; logs/A3/medicion/TABLA_FINAL.txt): el piso por esquinas de las diez reales. Por pelicula: el piso (R, G, B, gris), los pixeles
# y la distancia media; y por esquina (UL, UR, DR, DL): estado, origen, pixeles y medianas R, G, B, gris de la parte USADA. Mas, lo que daba A.2 (el 20 % mas lejano de toda la pelicula).
TABLA_DE_LAS_REALES = {
    "ML0": dict(R=110, G=177, B=82, gris=146, n=10333, d=7.901,
        esquinas=(("UL", "ok", "esquina", 2000, 107, 172, 82, 142), ("UR", "ok", "esquina", 2000, 98, 171, 81, 139), ("DR", "ok", "esquina", 3039, 113, 180, 84, 149), ("DL", "ok", "esquina", 3294, 110, 178, 81, 147))),
    "EPSON027": dict(R=110, G=177, B=82, gris=146, n=11489, d=8.16,
        esquinas=(("UL", "ok", "esquina", 2356, 107, 172, 83, 142), ("UR", "ok", "esquina", 2000, 98, 171, 80, 139), ("DR", "ok", "esquina", 3474, 114, 181, 85, 150), ("DL", "ok", "esquina", 3659, 111, 178, 81, 147))),
    "EPSON007": dict(R=112, G=180, B=81, gris=148, n=13504, d=8.669,
        esquinas=(("UL", "ok", "esquina", 3338, 113, 180, 83, 149), ("UR", "ok", "esquina", 2893, 107, 174, 80, 143), ("DR", "ok", "esquina", 3292, 112, 179, 77, 147), ("DL", "ok", "esquina", 3981, 117, 184, 83, 152))),
    "EPSON008_TIF": dict(R=113, G=180, B=84, gris=148, n=13836, d=8.635,
        esquinas=(("UL", "ok", "esquina", 3740, 114, 180, 84, 149), ("UR", "ok", "esquina", 3269, 109, 174, 82, 144), ("DR", "ok", "esquina", 2950, 113, 177, 79, 147), ("DL", "ok", "esquina", 3877, 117, 183, 84, 152))),
    "EPSON030": dict(R=112, G=180, B=82, gris=148, n=12492, d=8.491,
        esquinas=(("UL", "ok", "esquina", 2160, 105, 172, 79, 141), ("UR", "ok", "esquina", 3238, 108, 175, 83, 144), ("DR", "ok", "esquina", 4146, 117, 184, 84, 153), ("DL", "ok", "esquina", 2948, 112, 180, 78, 148))),
    "EPSON001_JPG": dict(R=123, G=185, B=80, gris=154, n=16861, d=9.513,
        esquinas=(("UL", "ok", "esquina", 4875, 123, 184, 77, 154), ("UR", "ok", "esquina", 4696, 121, 184, 80, 153), ("DR", "ok", "esquina", 4592, 127, 189, 83, 158), ("DL", "reemplazada", "giro +5 grados", 2698, 118, 183, 81, 152))),
    "EPSON001_TIF": dict(R=123, G=185, B=79, gris=154, n=16853, d=9.511,
        esquinas=(("UL", "ok", "esquina", 4873, 123, 184, 77, 154), ("UR", "ok", "esquina", 4691, 121, 184, 79, 153), ("DR", "ok", "esquina", 4591, 127, 189, 84, 158), ("DL", "reemplazada", "giro +5 grados", 2698, 117, 182, 82, 151))),
    "PLACA_REF40": dict(R=96, G=164, B=83, gris=134, n=8000, d=6.895,
        esquinas=(("UL", "ok", "esquina", 2000, 99, 168, 85, 138), ("UR", "ok", "esquina", 2000, 98, 163, 79, 134), ("DR", "ok", "esquina", 2000, 91, 162, 80, 131), ("DL", "ok", "esquina", 2000, 95, 169, 87, 137))),
    "EPSON028": dict(R=89, G=163, B=83, gris=132, n=10834, d=8.209,
        esquinas=(("UL", "ok", "esquina", 2000, 87, 160, 81, 129), ("UR", "ok", "esquina", 4098, 92, 165, 86, 134), ("DR", "ok", "esquina", 2736, 90, 164, 86, 133), ("DL", "ok", "esquina", 2000, 74, 155, 76, 122))),
    "EPSON029": dict(R=106, G=176, B=81, gris=144, n=13856, d=8.661,
        esquinas=(("UL", "ok", "esquina", 2729, 104, 171, 80, 141), ("UR", "ok", "esquina", 3861, 109, 178, 82, 146), ("DR", "ok", "esquina", 3578, 109, 180, 84, 148), ("DL", "ok", "esquina", 3688, 103, 173, 79, 141))),
}
LO_QUE_DABA_A2 = {"ML0": (101, 173, 86, 142), "EPSON027": (100, 173, 85, 141), "EPSON007": (99, 171, 83, 139), "EPSON008_TIF": (101, 170, 84, 139), "EPSON030": (98, 170, 83, 139),
                  "EPSON001_JPG": (111, 179, 81, 148), "EPSON001_TIF": (111, 180, 82, 148), "PLACA_REF40": (82, 156, 82, 125), "EPSON028": (73, 154, 82, 122), "EPSON029": (91, 167, 81, 135)}


def _pel():
    """El modulo, importado POR PRUEBA (en HEAD el archivo se coleciona y cada prueba cae con su error)."""
    return importlib.import_module("analisisImagenes.pelicula")


def _P(**cambios):
    return A2._P(**cambios)


def piso(pelicula, campo, P=None, punto=None, modo=None, referencia=None):
    """`piso_de_pelicula` con la forma de llamar de A.3; `modo` y `referencia_virgen` solo se pasan si se piden (en HEAD la llamada de A.2 sigue valiendo)."""
    extra = {}
    if modo is not None:
        extra["modo"] = modo
    if referencia is not None:
        extra["referencia_virgen"] = referencia
    return _pel().piso_de_pelicula(pelicula, campo, _P() if P is None else P, punto, **extra)


def _oraculo(s):
    if not hasattr(s, "_o_a3"):
        s._o_a3 = Oraculo(s)
    return s._o_a3


def _region(p, forma):
    return A2._region_completa(p, forma)


def _union(mascaras, forma):
    u = np.zeros(forma, bool)
    for m in mascaras:
        u |= m
    return u


def _punto_sobre_la_pelicula(s):
    """Un punto de pelicula de fuera del campo, lejos del borde (el mismo criterio de A.2): para el sexto clic."""
    o = _oraculo(s)
    cand = o.pelicula & (o.borde_mm >= 2.1) & (o.dcam > 5.5)
    k = int(np.argmax(np.where(cand, o.dcam, -1.0)))
    return (float(k % s.forma[1]), float(k // s.forma[1]))


def _sin_la_regla_7(pelicula, campo, punto=None):
    """El piso con la regla (7) APAGADA (`umbral_como_fondo` = 1000) Y el rango y el IQR abiertos: sin eso el vacio lo frenaria el rango o el IQR y el control ya no demostraria lo que la regla (7)
    cambia (clase 4 del diseño §9.2)."""
    return piso(pelicula, campo, _P(umbral_como_fondo=1000.0, **ABIERTO), punto)


def _cifra(x):
    t = f"{x:.1f}"
    return t[:-2] if t.endswith(".0") else t


# ====================================================================================================================== geometria independiente (para las pruebas del respaldo)

def _distancia_a_los_lados(campo, x, y):
    """Distancia del punto (x, y) al cuadrilatero (0 dentro), con segmentos de numpy: la verdad de «a que distancia del campo esta este centro»."""
    C = np.asarray(campo, np.float64)
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    mejor = np.full(x.shape, np.inf)
    signos = []
    for j in range(4):
        a, b = C[j], C[(j + 1) % 4]
        e = b - a
        px, py = x - a[0], y - a[1]
        t = np.clip((px * e[0] + py * e[1]) / float(e @ e), 0.0, 1.0)
        mejor = np.minimum(mejor, np.hypot(px - t * e[0], py - t * e[1]))
        signos.append(e[0] * py - e[1] * px)
    signos = np.array(signos)
    dentro = np.all(signos >= 0, axis=0) | np.all(signos <= 0, axis=0)
    return np.where(dentro, 0.0, mejor)


def _s_y_lado(campo, x, y):
    """(s, indice del lado, distancia) del lado MAS CERCANO a cada punto: s = 1 - |1 - 2t| (0 en la esquina, 1 en el punto medio), t la fraccion del lado donde cae la proyeccion."""
    C = np.asarray(campo, np.float64)
    x, y = np.atleast_1d(np.asarray(x, np.float64)), np.atleast_1d(np.asarray(y, np.float64))
    mejor = np.full(x.shape, np.inf)
    s_mejor = np.zeros(x.shape)
    lado = np.zeros(x.shape, int)
    for j in range(4):
        a, b = C[j], C[(j + 1) % 4]
        e = b - a
        t = np.clip(((x - a[0]) * e[0] + (y - a[1]) * e[1]) / float(e @ e), 0.0, 1.0)
        d = np.hypot(x - (a[0] + t * e[0]), y - (a[1] + t * e[1]))
        mas_cerca = d < mejor
        mejor = np.where(mas_cerca, d, mejor)
        s_mejor = np.where(mas_cerca, 1.0 - np.abs(1.0 - 2.0 * t), s_mejor)
        lado = np.where(mas_cerca, j, lado)
    return s_mejor, lado, mejor


def _cruce_de_diagonales(campo):
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = campo
    d = (x1 - x3) * (y2 - y4) - (y1 - y3) * (x2 - x4)
    a, b = x1 * y3 - y1 * x3, x2 * y4 - y2 * x4
    return np.array([(a * (x2 - x4) - (x1 - x3) * b) / d, (a * (y2 - y4) - (y1 - y3) * b) / d])


def _centro_de_un_respaldo(campo, k, nombre, d_mm):
    """Donde cae el centro de la ventana de un candidato del respaldo de la esquina k a `d_mm` del campo, calculado AQUI (biseccion sobre las distancias de arriba para el giro; el punto del lado
    mas la normal para el lateral). `nombre`: «giro +5 grados», «giro -5 grados» o «lateral s=0.05 del lado UL-UR»."""
    C = np.asarray(campo, np.float64)
    centro = _cruce_de_diagonales(C)
    if nombre.startswith("giro"):
        g = math.radians(float(nombre.split()[1]))
        u0 = (C[k] - centro) / np.hypot(*(C[k] - centro))
        u_mas = np.array([u0[0] * math.cos(g) - u0[1] * math.sin(g), u0[0] * math.sin(g) + u0[1] * math.cos(g)])
        u_menos = np.array([u0[0] * math.cos(g) + u0[1] * math.sin(g), -u0[0] * math.sin(g) + u0[1] * math.cos(g)])
        hacia = C[(k + 1) % 4] - centro
        # la rotacion que ACERCA la direccion a la esquina siguiente (UL -> UR -> DR -> DL) es la «+»
        mas, menos = (u_mas, u_menos) if np.dot(u_mas, hacia) > np.dot(u_menos, hacia) else (u_menos, u_mas)
        u = mas if g > 0 else menos
        lo, hi = 0.0, 4.0 * float(np.hypot(*(C[0] - C[2])))
        for _ in range(80):
            mid = (lo + hi) / 2
            q = centro + mid * u
            if float(_distancia_a_los_lados(C, q[0], q[1])) * ESC < d_mm:
                lo = mid
            else:
                hi = mid
        return tuple(centro + hi * u)
    s_nominal = float(nombre.split("s=")[1].split()[0])
    lado_txt = nombre.split("lado ")[1]
    a_txt, b_txt = lado_txt.split("-")
    j = ESQUINAS.index(a_txt)
    assert ESQUINAS[(j + 1) % 4] == b_txt, nombre
    e = C[(j + 1) % 4] - C[j]
    t = s_nominal / 2 if j == k else 1.0 - s_nominal / 2
    normal = np.array([e[1], -e[0]]) / np.hypot(*e)
    if np.dot((C[j] + C[(j + 1) % 4]) / 2 - centro, normal) < 0:
        normal = -normal
    return tuple(C[j] + t * e + normal * (d_mm / ESC))


NOMBRES_DE_LOS_SEIS = {
    "UL": ["giro +5 grados", "giro -5 grados", "lateral s=0.05 del lado UL-UR", "lateral s=0.05 del lado DL-UL", "lateral s=0.1 del lado UL-UR", "lateral s=0.1 del lado DL-UL"],
    "UR": ["giro +5 grados", "giro -5 grados", "lateral s=0.05 del lado UR-DR", "lateral s=0.05 del lado UL-UR", "lateral s=0.1 del lado UR-DR", "lateral s=0.1 del lado UL-UR"],
    "DR": ["giro +5 grados", "giro -5 grados", "lateral s=0.05 del lado DR-DL", "lateral s=0.05 del lado UR-DR", "lateral s=0.1 del lado DR-DL", "lateral s=0.1 del lado UR-DR"],
    "DL": ["giro +5 grados", "giro -5 grados", "lateral s=0.05 del lado DL-UL", "lateral s=0.05 del lado DR-DL", "lateral s=0.1 del lado DL-UL", "lateral s=0.1 del lado DR-DL"],
}


# ====================================================================================================================== (a) el selector

class TestElSelectorDeModo:
    def test_a_las_constantes_del_selector(self):
        pel = _pel()
        assert pel.MODOS_DEL_PISO == ("automatico", "punto_manual", "virgen")
        assert pel.MODO_DEL_PISO_POR_OMISION == "virgen"           # OD.1 (DA-87): el piso por omision es el de la pelicula virgen; sin una referencia cargada `modo_efectivo` toma las esquinas
        assert pel.MODO_DE_ORIGEN == {"automatico": "automatico", "manual": "punto_manual", "virgen": "virgen"}
        assert pel.ESQUINAS == ESQUINAS and pel.NOMBRE_DE_ESQUINA == NOMBRE_DE_ESQUINA

    def test_a_modo_none_hace_lo_de_A2_el_punto_si_lo_hay_y_si_no_el_modo_por_omision(self):
        s = A2._sint("B", 0.4)
        auto = piso(s.pelicula, s.campo)
        assert auto.modo == "automatico" and auto.origen == "automatico" and auto.estado == "ok"
        assert A2._medianas(auto) == A2._medianas(piso(s.pelicula, s.campo, modo="automatico"))
        punto = _punto_sobre_la_pelicula(s)
        con_punto = piso(s.pelicula, s.campo, punto=punto)
        assert con_punto.modo == "punto_manual" and con_punto.origen == "manual" and con_punto.estado == "ok"
        assert A2._medianas(con_punto) == A2._medianas(piso(s.pelicula, s.campo, punto=punto, modo="punto_manual"))
        assert tuple(con_punto.punto) == punto and auto.punto is None

    def test_a_cambiar_el_modo_por_omision_es_una_linea_y_sin_referencia_nunca_cae_al_automatico(self, monkeypatch):
        """OD.1 (DA-87): con el modo por omision en «virgen» y SIN un modo pedido, la regla (`modo_efectivo`) toma las esquinas si todavia no hay una referencia cargada (el `Piso` dice su origen); con el modo
        «virgen» PEDIDO y sin referencia el piso sigue siendo «no medible» y nunca cae solo al automatico (V7)."""
        s = A2._sint("B", 0.4)
        pel = _pel()
        monkeypatch.setattr(pel, "MODO_DEL_PISO_POR_OMISION", "virgen")
        sin = piso(s.pelicula, s.campo)
        assert sin.estado == "ok" and sin.origen == "automatico" and sin.modo == "automatico", "OD.1: la omision «virgen» sin referencia son las esquinas"
        p = piso(s.pelicula, s.campo, modo="virgen")
        assert p.estado.startswith(pel.MOTIVO_SIN_REFERENCIA_VIRGEN) and p.origen == "virgen" and p.modo == "virgen" and p.region is None
        assert all(c.mediana is None and c.estado == p.estado for c in p.capas.values()), "con el modo «virgen» pedido y sin referencia dio un numero (¿cayo al automatico?)"
        assert piso(s.pelicula, s.campo, punto=_punto_sobre_la_pelicula(s)).modo == "punto_manual", "el punto marcado manda sobre el modo por omision, como en A.2"

    @pytest.mark.parametrize("modo,con_punto,referencia", [("otro", False, None), ("AUTOMATICO", False, None), ("automatico", True, None), ("punto_manual", False, None),
                                                            ("virgen", True, None), ("automatico", False, {"no": "es una referencia"}), ("virgen", False, "texto")])
    def test_a_una_forma_equivocada_de_llamar_es_un_error_de_quien_llama(self, modo, con_punto, referencia):
        s = A2._sint("B", 0.4)
        pel = _pel()
        punto = (1500.0, 1500.0) if con_punto else None
        with pytest.raises(ValueError):
            pel.piso_de_pelicula(s.pelicula, s.campo, _P(), punto, modo=modo, referencia_virgen=referencia)

    def test_a_el_mensaje_de_un_modo_invalido_nombra_los_validos(self):
        s = A2._sint("B", 0.4)
        with pytest.raises(ValueError) as e:
            _pel().piso_de_pelicula(s.pelicula, s.campo, _P(), None, modo="otro")
        assert all(m in str(e.value) for m in ("automatico", "punto_manual", "virgen"))

    def test_a_el_modo_por_omision_se_define_una_vez_y_ninguna_funcion_lo_escribe_de_nuevo(self):
        definiciones = []
        for ruta in RAIZ.rglob("*.py"):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in {".venv", "build", "dist", "tests", "__pycache__"} or any(p.startswith(".") for p in partes):
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for n in ast.walk(arbol):
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODO_DEL_PISO_POR_OMISION" for t in n.targets):
                    definiciones.append(str(ruta.relative_to(RAIZ)).replace(os.sep, "/"))
        assert definiciones == ["analisisImagenes/pelicula.py"], definiciones
        arbol = ast.parse((RAIZ / "analisisImagenes" / "pelicula.py").read_text(encoding="utf-8"))
        f = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "piso_de_pelicula")
        firma = {a.arg: d for a, d in zip(f.args.args[-len(f.args.defaults):], f.args.defaults)}
        assert isinstance(firma["modo"], ast.Constant) and firma["modo"].value is None, "el modo por omision de la firma es None: lo decide la constante"
        # OD.1: la constante la lee la regla del modo, `modo_efectivo` (la UNICA), y `piso_de_pelicula` le pregunta a ella; ninguna funcion escribe el modo por omision a mano
        g = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "modo_efectivo")
        assert "MODO_DEL_PISO_POR_OMISION" in {n.id for n in ast.walk(g) if isinstance(n, ast.Name)}, "`modo_efectivo` no lee la constante del modo por omision"
        assert "modo_efectivo" in {n.id for n in ast.walk(f) if isinstance(n, ast.Name)}, "la funcion no le pregunta a la regla del modo"
        escritos = [c.value for n in ast.walk(f) if isinstance(n, ast.Compare) for c in [n.comparators[0]] if isinstance(c, ast.Constant) and c.value == "automatico"]
        assert not [n for n in ast.walk(f) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "modo" for t in n.targets)
                    and isinstance(n.value, ast.Constant) and n.value.value == "automatico"], "la funcion escribe el modo por omision en vez de leerlo de la constante"


# ====================================================================================================================== (b) las esquinas

CASOS_DEL_ORACULO = [("A", 0.0, {}), ("A", 1.0, {}), ("B", 0.9, {}), ("C", 0.4, {}), ("E", -3.0, {}), ("D", 0.0, {"beta": 0.02, "cupula_pct_40mm": -3.5}), ("L", -1.0, {})]


class TestElPisoSaleDeLasCuatroEsquinas:
    @pytest.mark.parametrize("variante,theta,kw", CASOS_DEL_ORACULO)
    def test_b_la_region_es_la_union_de_las_cunas_del_oraculo_y_el_piso_es_la_verdad_del_generador(self, variante, theta, kw):
        s = A2._sint(variante, theta, **kw)
        o = _oraculo(s)
        p = piso(s.pelicula, s.campo)
        assert p.estado == "ok" and p.origen == "automatico" and len(p.esquinas) == 4 and [e.esquina for e in p.esquinas] == list(ESQUINAS)
        region = _region(p, s.forma)
        for e in p.esquinas:
            # una esquina da piso exactamente cuando su cuña tiene 2000 pixeles elegibles (el recorte a ras girado 1 grado pierde la superior izquierda: 1498)
            assert (e.estado == "ok") == (o.n_cuna[e.esquina] >= 2000), (e.esquina, e.estado, o.n_cuna[e.esquina])
            if e.estado == "ok":
                suya = region & o.cunas[e.esquina]
                assert A2._jaccard(suya, o.region_de[e.esquina]) >= 0.95, f"{e.esquina}: la region no es el 20 % mas lejano de la cuña del oraculo"
                assert abs(e.n - int(o.region_de[e.esquina].sum())) <= 0.03 * e.n + 5
            else:
                assert e.estado == "sin piso" and not (region & o.cunas[e.esquina] & o.elegibles).any(), "una esquina sin piso dejo pixeles en la region"
        # el oraculo rasteriza los conos con fillConvexPoly y la funcion decide cada pixel con dos desigualdades: sus bordes discrepan hasta un pixel (L -1 grado: 4 pixeles de 13753). Un pixel del
        # LATERAL del campo estaria a cientos de pixeles de todo cono, asi que la tolerancia de 1 px no le quita fuerza a la comprobacion.
        cerca_de_un_cono = cv2.dilate(_union(o.cunas.values(), s.forma).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        assert not (region & ~cerca_de_un_cono).any(), "la region tiene pixeles que no son de ninguna cuña (¿el lateral del campo?)"
        assert p.region.n == sum(e.n for e in p.esquinas if e.estado == "ok") == int(region.sum())
        verdad = o.piso(region=_union([o.region_de[e.esquina] for e in p.esquinas if e.estado == "ok"], s.forma))
        for c in "BGR":
            assert abs(p.capas[c].mediana - verdad[c]) <= 1.0, f"{variante} {theta} {c}: {p.capas[c].mediana} contra la verdad {verdad[c]:.2f}"
        assert not (region & ~o.valida).any() and not (region & (o.dcam <= 5.0 - 0.1)).any(), "la region toca el borde de la pelicula, el borde de la imagen o el margen del campo"

    def test_b_oscurecer_el_centro_de_los_lados_no_mueve_el_piso_y_el_de_la_region_de_A2_si(self):
        """Simula la dosis lateral: el rojo 20 niveles mas oscuro en la pelicula cuyo punto mas cercano esta a mas del 25 % del semilado de la esquina (s > 0.25). Ninguna cuña llega ahi, asi que el
        piso de A.3 no se mueve; el CONTROL es el piso de A.2 (la mediana del 20 % mas lejano de toda la pelicula elegible), calculado aqui, que si baja: la prueba discrimina."""
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        lateral = o.elegibles & ~_union(o.cunas.values(), s.forma)
        ys, xs = np.nonzero(lateral)
        s_, _, _ = _s_y_lado(s.campo, xs.astype(float), ys.astype(float))
        oscuro = np.zeros(s.forma, bool)
        oscuro[ys[s_ > 0.25], xs[s_ > 0.25]] = True
        assert int(oscuro.sum()) > 20000, "el centro de los lados es chico: la prueba no discrimina"
        img = s.img.copy()
        rojo = img[:, :, 2].astype(np.int16)
        rojo[oscuro] -= 20
        img[:, :, 2] = np.clip(rojo, 0, 255).astype(np.uint8)
        limpio, oscurecido = piso(s.pelicula, s.campo), piso(A2._a_pelicula(img), s.campo)
        for c in CAPAS:
            assert abs(oscurecido.capas[c].mediana - limpio.capas[c].mediana) <= 0.5, f"{c}: el centro de los lados movio el piso"
        region_a2 = o.elegibles & (o.dcam >= np.quantile(o.dcam[o.elegibles], 0.8))
        assert (region_a2 & oscuro).sum() > 0.2 * region_a2.sum(), "el control de A.2 no toca el centro de los lados: no discrimina"
        a2_limpio, a2_oscuro = float(np.median(s.img[:, :, 2][region_a2])), float(np.median(img[:, :, 2][region_a2]))
        assert a2_limpio - a2_oscuro >= 3.0, f"el piso de A.2 solo bajo {a2_limpio - a2_oscuro:.1f} niveles: el control no discrimina"

    @pytest.mark.parametrize("theta", [0.4, 0.9, 1.0, -3.0, 5.0])
    def test_b_la_misma_pelicula_en_la_pagina_da_el_mismo_piso_con_cualquier_giro_y_las_mismas_esquinas(self, theta):
        sin_giro, con_giro = A2._sint("B", 0.0), A2._sint("B", theta)
        a, b = piso(sin_giro.pelicula, sin_giro.campo), piso(con_giro.pelicula, con_giro.campo)
        assert a.estado == b.estado == "ok" and [e.estado for e in b.esquinas] == ["ok"] * 4
        for c in CAPAS:
            assert abs(a.capas[c].mediana - b.capas[c].mediana) <= 1.0, f"{c} con giro {theta}"
        assert abs(a.region.distancia_media_mm - b.region.distancia_media_mm) <= 0.1

    def test_b_cada_esquina_dice_su_parte_sus_pixeles_su_caja_y_su_distancia(self):
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        p = piso(s.pelicula, s.campo)
        region = _region(p, s.forma)
        for e in p.esquinas:
            x0, y0, x1, y1 = e.caja
            suya = np.zeros(s.forma, bool)
            suya[y0:y1, x0:x1] = True
            suya &= region & o.cunas[e.esquina]
            assert abs(int(suya.sum()) - e.n) <= 0.03 * e.n + 5
            independiente = float(o.dcam[o.region_de[e.esquina]].mean())
            assert abs(e.distancia_media_mm - independiente) <= 0.1, (e.esquina, e.distancia_media_mm, independiente)
            assert e.origen == "esquina" and e.motivo == "" and e.respaldos == ()
            assert set(e.medianas) == set(CAPAS) and set(e.iqr) == set(CAPAS) and all(v <= 15.0 for v in e.iqr.values())

    def test_b_una_pelicula_en_grises_y_los_16_bits_dan_el_mismo_piso_por_esquinas(self):
        a, b = A2._sint("B", 0.4), A2._sint("B", 0.4, bits=16)
        pa, pb = piso(a.pelicula, a.campo), piso(b.pelicula, b.campo)
        assert pb.estado == "ok" and [e.estado for e in pb.esquinas] == ["ok"] * 4
        for c in CAPAS:
            assert abs(pa.capas[c].mediana - pb.capas[c].mediana) <= 0.75, c


# ====================================================================================================================== (c) las diez peliculas reales

class TestLasDiezRealesDanLaTablaDelDiseno:
    @pytest.mark.parametrize("clave", sorted(TABLA_DE_LAS_REALES))
    def test_c_el_piso_por_esquinas_de_cada_real_es_el_de_la_tabla_exacto(self, clave):
        t = TABLA_DE_LAS_REALES[clave]
        p = piso(A2._real(clave), CLICS_REALES[clave])
        assert p.estado == "ok" and p.origen == "automatico" and p.modo == "automatico", p.estado
        assert {c: p.capas[c].mediana for c in CAPAS} == {"R": t["R"], "G": t["G"], "B": t["B"], "gris": t["gris"]}, clave
        assert p.region.n == t["n"] and abs(p.region.distancia_media_mm - t["d"]) <= 0.01, (p.region.n, p.region.distancia_media_mm)
        assert len(p.esquinas) == 4
        for e, (nombre, estado, origen, n, R, G, B, gris) in zip(p.esquinas, t["esquinas"]):
            assert (e.esquina, e.estado, e.origen, e.n) == (nombre, estado, origen, n), (clave, e)
            assert (e.medianas["R"], e.medianas["G"], e.medianas["B"], e.medianas["gris"]) == (R, G, B, gris), (clave, e.esquina)

    @pytest.mark.parametrize("clave", sorted(TABLA_DE_LAS_REALES))
    def test_c_el_piso_por_esquinas_es_mas_claro_que_el_de_A2_que_se_tomaba_en_el_centro_de_los_lados(self, clave):
        """A.2 daba R -9 a -16, G -4 a -10 niveles mas oscuro (el rojo y el verde del centro de cada lado estan 11 a 38 y 1 a 28 por debajo del de las esquinas): el fisico tenia razon."""
        p = piso(A2._real(clave), CLICS_REALES[clave])
        R2, G2, B2, gris2 = LO_QUE_DABA_A2[clave]
        assert p.capas["R"].mediana - R2 >= 8 and p.capas["G"].mediana - G2 >= 4 and p.capas["gris"].mediana - gris2 >= 4, (clave, A2._medianas(p))
        assert abs(p.capas["B"].mediana - B2) <= 4

    @pytest.mark.parametrize("clave", ["EPSON001_JPG", "EPSON001_TIF"])
    def test_c_en_EPSON001_la_esquina_inferior_izquierda_es_dispersa_y_la_reemplaza_el_giro_mas_5(self, clave):
        p = piso(A2._real(clave), CLICS_REALES[clave])
        dl = p.esquinas[3]
        assert dl.esquina == "DL" and dl.estado == "reemplazada" and dl.origen == "giro +5 grados"
        assert dl.motivo == "dispersa (IQR del azul 24 > 15)", dl.motivo
        assert [i.nombre for i in dl.respaldos] == ["giro +5 grados"] and dl.respaldos[0].estado == "ok" and dl.respaldos[0].d_mm == 7.5
        assert all(e.estado == "ok" and e.respaldos == () for e in p.esquinas[:3])

    def test_c_el_rojo_de_la_banda_lateral_de_ML0_que_midio_la_revision_queda_por_debajo_del_piso_por_esquinas(self):
        """87/172/97 (B/G/R) en el centro del lado de abajo de ML0: el rojo (97) y el verde (172) quedan por debajo del piso de las esquinas (110 y 177): lo que el fisico dijo."""
        p = piso(A2._real("ML0"), CLICS_REALES["ML0"])
        b, g, r = A2.FRANJA_MAS_LEJANA_ML0_BGR
        assert p.capas["R"].mediana - r >= 9 and p.capas["G"].mediana - g >= 3

    @pytest.mark.parametrize("a,b,tolerancia", [("ML0", "EPSON027", 1.0), ("EPSON001_JPG", "EPSON001_TIF", 1.0), ("EPSON007", "EPSON008_TIF", 3.0), ("EPSON007", "EPSON030", 3.0)])
    def test_c_la_misma_pelicula_en_dos_archivos_da_el_mismo_piso_por_esquinas(self, a, b, tolerancia):
        pa, pb = piso(A2._real(a), CLICS_REALES[a]), piso(A2._real(b), CLICS_REALES[b])
        for c in CAPAS:
            assert abs(pa.capas[c].mediana - pb.capas[c].mediana) <= tolerancia, f"{a} contra {b}, {c}"


# ====================================================================================================================== (d) el rango esperado y el fondo

def _etiqueta(img, s, esquina, lado_mm, valor=None, rojo_mas=None):
    """Una etiqueta cuadrada de `lado_mm` en la esquina de la PELICULA (no del campo) hacia adentro: de un valor fijo (blanca 245, negra 20) o sumando `rojo_mas` al rojo de la pelicula."""
    a = np.array(img).copy()
    x, y = (int(c) for c in s.verdad.esquinas_pelicula_px[esquina])
    L = int(round(lado_mm / ESC))
    caja = {"UL": (slice(y, y + L), slice(x, x + L)), "UR": (slice(y, y + L), slice(x - L, x)),
            "DR": (slice(y - L, y), slice(x - L, x)), "DL": (slice(y - L, y), slice(x, x + L))}[esquina]
    if valor is not None:
        a[caja] = valor
    else:
        sub = a[caja].astype(np.int16)
        sub[:, :, 2] += rojo_mas
        a[caja] = np.clip(sub, 0, 255).astype(np.uint8)
    return a


class TestElRangoEsperadoYElFondo:
    @pytest.mark.parametrize("fondo", [169, 150, 100])
    def test_d_un_fondo_neutro_por_debajo_de_170_ya_no_se_toma_por_pelicula(self, fondo):
        """El limite declarado de la regla (7) de A.2: con el fondo en 169 o menos la funcion daba «ok» con el vacio como piso. Con el rango esperado el verde exige 145 o mas y el azul 100 o menos:
        un fondo neutro, de cualquier gris, no pasa."""
        s = A2._con_fondo("B", 0.4, fondo)
        pel = _pel()
        p = piso(s.pelicula, s.campo)
        assert p.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PISO), p.estado
        assert p.region is None and all(c.mediana is None and c.estado == p.estado for c in p.capas.values())
        assert [e.estado for e in p.esquinas] == ["falla"] * 4 and all("fuera del rango esperado" in e.motivo for e in p.esquinas) and all(e.respaldos == () for e in p.esquinas)
        assert piso(s.pelicula, s.campo, _P(umbral_como_fondo=1000.0)).estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PISO), "con la regla (7) apagada tambien: lo frena el rango"
        abierto = piso(s.pelicula, s.campo, _P(**ABIERTO))
        assert abierto.estado == "ok" and all(abs(abierto.capas[c].mediana - fondo) <= 1.0 for c in CAPAS), "con el rango abierto el vacio vuelve a ser «ok»: lo que cambia es el rango"

    def test_d_la_pelicula_entera_con_el_rojo_65_niveles_mas_clara_es_no_medible(self):
        pel = _pel()
        s = A2.Sint("B", 0.4, calib=dict(gen.CALIB, virgen_bgr=(82.0, 174.0, 170.5)))
        p = piso(s.pelicula, s.campo)
        assert p.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PISO) and "rojo" in p.estado, p.estado
        assert [e.estado for e in p.esquinas] == ["falla"] * 4
        assert piso(s.pelicula, s.campo, _P(piso_esperado={**PISO_ESPERADO, "R": [60.0, 255.0], "gris": [110.0, 255.0]})).estado == "ok", "el piso_esperado de P cambia el resultado"

    def test_d_el_rango_incluye_el_gris(self):
        """Solo el gris fuera de su rango (las tres capas dentro): la esquina falla por el gris."""
        s = A2._sint("B", 0.4)
        base = piso(s.pelicula, s.campo)
        gris = base.capas["gris"].mediana
        rango = {**PISO_ESPERADO, "gris": [gris + 5.0, 255.0]}
        p = piso(s.pelicula, s.campo, _P(piso_esperado=rango))
        assert p.estado.startswith(_pel().MOTIVO_ESQUINAS_SIN_PISO) and all("gris" in e.motivo for e in p.esquinas), p.estado
        assert all(e.estado == "falla" for e in p.esquinas)

    def test_d_los_limites_del_rango_son_inclusivos(self):
        s = A2._sint("B", 0.4)
        base = piso(s.pelicula, s.campo)
        medianas = [e.medianas["R"] for e in base.esquinas]
        lo, hi = min(medianas), max(medianas)
        assert lo < hi
        justo = piso(s.pelicula, s.campo, _P(piso_esperado={**PISO_ESPERADO, "R": [lo, hi]}))
        assert justo.estado == "ok" and [e.estado for e in justo.esquinas] == ["ok"] * 4, "las medianas justo en el limite deben pasar"
        k_bajo, k_alto = medianas.index(lo), medianas.index(hi)
        por_arriba = piso(s.pelicula, s.campo, _P(piso_esperado={**PISO_ESPERADO, "R": [lo + 0.5, hi]}))
        assert por_arriba.esquinas[k_bajo].estado != "ok", "una mediana medio nivel por debajo del limite inferior paso"
        por_abajo = piso(s.pelicula, s.campo, _P(piso_esperado={**PISO_ESPERADO, "R": [lo, hi - 0.5]}))
        assert por_abajo.esquinas[k_alto].estado != "ok", "una mediana medio nivel por encima del limite superior paso"

    def test_d_el_iqr_maximo_se_usa_y_el_motivo_dice_que_capa_y_cuanto(self):
        s = A2._sint("B", 0.4)
        p = piso(s.pelicula, s.campo, _P(iqr_maximo=0.5))
        assert p.estado.startswith(_pel().MOTIVO_ESQUINAS_SIN_PISO) and all(e.estado == "falla" and e.motivo.startswith("dispersa (IQR del ") and e.motivo.endswith("> 0.5)") for e in p.esquinas)
        assert piso(s.pelicula, s.campo).estado == "ok"

    def test_d_la_regla_7_se_aplica_a_la_union_y_su_texto_lleva_el_porcentaje_de_la_union(self):
        """Con el fondo en 200 el vacio es el 100 % del piso: el estado es el de A.2 con el porcentaje de la UNION de las cuatro esquinas, no el de una esquina, y sin intentar respaldos."""
        s = A2._con_fondo("B", 0.4, 200)
        p = piso(s.pelicula, s.campo)
        assert p.estado == A2.motivo_completo(100)
        assert p.region is None and [e.estado for e in p.esquinas] == ["sin comprobar"] * 4 and all(e.respaldos == () for e in p.esquinas)

    def test_d_el_recorte_suelto_girado_04_con_el_fondo_en_200_ya_no_lleva_vacio_al_piso(self):
        """A.2 daba «ok» con un 25 % de vacio en el piso (las cuñas blancas del recorte suelto); aqui el borde de la imagen se aparta 1 mm y los triangulos de vacio (0.77 mm) caen dentro."""
        s = A2._con_fondo("L", 0.4, 200)
        p = piso(s.pelicula, s.campo)
        assert p.estado == "ok", p.estado
        assert A2._fraccion_como_fondo(p, s.pelicula) < 0.01
        verdad = _oraculo(s).piso()
        assert all(abs(p.capas[c].mediana - verdad[c]) <= 1.0 for c in "BGR")

    def test_d_el_recorte_suelto_girado_09_con_el_fondo_en_200_lo_frena_la_regla_7(self):
        s = A2._con_fondo("L", 0.9, 200)
        p = piso(s.pelicula, s.campo)
        assert p.estado.startswith(A2.MOTIVO_COMO_EL_FONDO), p.estado
        sin = _sin_la_regla_7(s.pelicula, s.campo)
        assert sin.estado == "ok" and 0.35 < A2._fraccion_como_fondo(sin, s.pelicula) < 0.5, "sin la regla el vacio es la minoria que mueve la mediana: la prueba no discrimina"

    @pytest.mark.parametrize("dx,dy", [(-3400.0, -3400.0), (3400.0, 3400.0), (-3400.0, 0.0), (0.0, 3400.0)])
    def test_d_un_campo_que_no_esta_sobre_la_pelicula_dice_sin_meseta_antes_de_juzgar_las_esquinas(self, dx, dy):
        """DECISION DE DISENO DE OPUS (13-10, borradores/A3/decision_caidas_a2.md; VETABLE POR EL FISICO): en el automatico la meseta (que el campo luminoso este sobre la pelicula) se comprueba
        ANTES de juzgar las esquinas, justo despues de la regla (7) de la union. Las cuñas se construyen desde el campo: con el campo fuera de la pelicula no describen la pelicula, y sus motivos
        («la pelicula no sobresale lo bastante...: escanee la pelicula entera», «dos o mas esquinas...: revise el escaneo o use la pelicula virgen o marque un punto») mandarian a corregir lo que no
        esta mal; sin meseta ningun modo da un numero. El motivo es el de A.2 (test_a2::test_e_un_campo_que_la_pelicula_no_cubre...) y las esquinas quedan «sin comprobar», sin respaldos.
        CONTROL: con ese campo dos o mas esquinas tienen menos de `pixeles_minimos` pixeles, asi que si se juzgaran primero el motivo seria el de las esquinas: el orden decide."""
        s = A2._sint("B", 0.4)
        pel = _pel()
        lejos = [(x + dx, y + dy) for x, y in s.campo]
        assert int((A2._poligono(s.forma, lejos) & _oraculo(s).pelicula).sum()) == 0, "el campo tendria que caer entero fuera de la pelicula: la prueba no mide lo que dice"
        p = piso(s.pelicula, lejos)
        assert p.estado == pel.MOTIVO_SIN_MESETA, p.estado
        assert p.region is None and all(c.mediana is None and c.estado == p.estado for c in p.capas.values())
        assert [e.estado for e in p.esquinas] == ["sin comprobar"] * 4 and all(e.respaldos == () for e in p.esquinas), [(e.estado, len(e.respaldos)) for e in p.esquinas]
        assert sum(e.n < PLAN_DEL_PISO["pixeles_minimos"] for e in p.esquinas) >= 2, "con este campo las esquinas no fallarian: la prueba no discrimina el orden"

    def test_d_con_el_campo_fuera_y_el_fondo_gris_manda_la_regla_7_de_la_union_y_las_esquinas_no_se_juzgan(self):
        """El orden entero del automatico con el campo fuera: la regla (7) de la union, despues la meseta, despues las esquinas. Con el fondo del escaner en 200 lo que se toma es el vacio de la
        pagina: manda la regla (7), como en A.2 (test_a2::test_a_la_regla_va_antes_de_la_meseta), y las esquinas quedan «sin comprobar». CONTROL: con la regla apagada (y el rango y el IQR
        abiertos) el motivo es la meseta, no el de las esquinas."""
        s = A2._con_fondo("B", 0.4, 200)
        lejos = [(x - 3400.0, y - 3400.0) for x, y in s.campo]
        p = piso(s.pelicula, lejos)
        assert p.estado.startswith(A2.MOTIVO_COMO_EL_FONDO), p.estado
        assert [e.estado for e in p.esquinas] == ["sin comprobar"] * 4 and all(e.respaldos == () for e in p.esquinas)
        sin = _sin_la_regla_7(s.pelicula, lejos)
        assert sin.estado == _pel().MOTIVO_SIN_MESETA and [e.estado for e in sin.esquinas] == ["sin comprobar"] * 4, sin.estado


# ====================================================================================================================== (e) el respaldo

def _pintar_rojo_cerca_de_la_esquina(s, esquina, radio_mm, mas=70):
    """El rojo `mas` niveles mas claro en la pelicula a menos de `radio_mm` de la esquina de la PELICULA: esa parte queda fuera del rango (R > 140) pero sigue siendo pelicula limpia."""
    x, y = s.verdad.esquinas_pelicula_px[esquina]
    columnas, filas = np.arange(s.forma[1], dtype=np.float32)[None, :], np.arange(s.forma[0], dtype=np.float32)[:, None]
    cerca = np.hypot(columnas - np.float32(x), filas - np.float32(y)) * np.float32(ESC) < radio_mm
    a = np.array(s.img).copy()
    rojo = a[:, :, 2].astype(np.int16)
    rojo[cerca & (a.min(axis=2) < 235)] += mas
    a[:, :, 2] = np.clip(rojo, 0, 255).astype(np.uint8)
    return a


def _pixeles_de_la_ventana(o, centro, lado_mm=3.0, margen_campo_mm=5.0):
    """Cuantos pixeles de pelicula limpia (segun el oraculo) a mas de `margen_campo_mm` del campo hay en la ventana cuadrada de `lado_mm` centrada en `centro`."""
    h = lado_mm / 2.0 / ESC
    cx, cy = centro
    alto, ancho = o.valida.shape
    x0, x1 = max(0, int(math.floor(cx - h))), min(ancho, int(math.ceil(cx + h)) + 1)
    y0, y1 = max(0, int(math.floor(cy - h))), min(alto, int(math.ceil(cy + h)) + 1)
    if x1 <= x0 or y1 <= y0:
        return 0
    cuad = (np.abs(np.arange(x0, x1)[None, :] - cx) <= h) & (np.abs(np.arange(y0, y1)[:, None] - cy) <= h)
    return int((cuad & o.valida[y0:y1, x0:x1] & (o.dcam[y0:y1, x0:x1] > margen_campo_mm)).sum())


class TestElRespaldoDeUnaEsquina:
    @pytest.mark.parametrize("valor,origen_esperado,primero_falla", [(245, "giro +5 grados", False), (20, "giro -5 grados", True)],
                             ids=["etiqueta_blanca", "etiqueta_negra"])
    def test_e_una_etiqueta_en_una_esquina_la_reemplaza_el_giro_y_el_signo_de_mas_es_hacia_la_esquina_siguiente(self, valor, origen_esperado, primero_falla):
        """Una etiqueta de 9.7 x 9.7 mm sobre la esquina inferior derecha de la pelicula. La blanca (no es pelicula) deja libre el giro +5; la negra (es pelicula, oscura) deja libre el giro -5: el
        signo se fija con la geometria (el «+» es la rotacion que se acerca a la esquina SIGUIENTE, UL -> UR -> DR -> DL)."""
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        etiquetada = _etiqueta(s.img, s, "DR", 9.7, valor=valor)
        p = piso(A2._a_pelicula(etiquetada), s.campo)
        assert p.estado == "ok", p.estado
        dr = p.esquinas[2]
        assert dr.esquina == "DR" and dr.estado == "reemplazada" and dr.origen == origen_esperado, (dr.estado, dr.origen, dr.motivo)
        assert [i.nombre for i in dr.respaldos][-1] == origen_esperado and dr.respaldos[-1].estado == "ok"
        assert (dr.respaldos[0].estado == "falla") == primero_falla
        assert all(e.estado == "ok" and e.respaldos == () for i, e in enumerate(p.esquinas) if i != 2)
        # la geometria del candidato que gano: el centro esta donde la geometria independiente dice, y el «+» queda mas cerca de la esquina siguiente (DL) que el «-»
        centro = _centro_de_un_respaldo(s.campo, 2, origen_esperado, dr.respaldos[-1].d_mm)
        assert np.hypot(*(np.array(dr.respaldos[-1].centro) - np.array(centro))) <= 1.0
        mas = np.array(_centro_de_un_respaldo(s.campo, 2, "giro +5 grados", 8.0))
        menos = np.array(_centro_de_un_respaldo(s.campo, 2, "giro -5 grados", 8.0))
        siguiente = np.array(s.campo[3])
        assert np.hypot(*(mas - siguiente)) < np.hypot(*(menos - siguiente)), "el «+» no se acerca a la esquina siguiente"
        # la region no tiene pixeles de la etiqueta y el piso es la verdad del generador en los pixeles que uso
        region = _region(p, s.forma)
        etiqueta = (etiquetada != np.array(s.img)).any(axis=2)
        assert not (region & etiqueta).any(), "la region conserva pixeles de la etiqueta"
        verdad = o.piso(region=region)
        for c in "BGR":
            assert abs(p.capas[c].mediana - verdad[c]) <= 1.0, f"{c}: {p.capas[c].mediana} contra {verdad[c]:.2f}"
        limpio = piso(s.pelicula, s.campo)
        assert all(abs(p.capas[c].mediana - limpio.capas[c].mediana) <= 1.5 for c in CAPAS), "la esquina reemplazada movio el piso mas de lo que mueve quitar una esquina"

    def test_e_el_orden_de_los_candidatos_se_fija_con_una_etiqueta_que_solo_deja_libre_el_lateral_s_01_del_lado_k_menos_1(self):
        """En la esquina inferior izquierda la etiqueta blanca deja sin lugar a los cinco primeros candidatos y libre al sexto, el lateral s = 0.1 del lado que LLEGA a la esquina (k - 1): el orden
        giro +, giro -, lateral 0.05 del lado k, lateral 0.05 del lado k-1, lateral 0.1 del lado k, lateral 0.1 del lado k-1 (laterales antes que giros, o el lado k-1 antes que el k, cambia la lista)."""
        s = A2._sint("B", 0.4)
        p = piso(A2._a_pelicula(_etiqueta(s.img, s, "DL", 9.7, valor=245)), s.campo)
        dl = p.esquinas[3]
        assert dl.estado == "reemplazada" and dl.origen == "lateral s=0.1 del lado DR-DL"
        assert [i.nombre for i in dl.respaldos] == NOMBRES_DE_LOS_SEIS["DL"]
        assert [i.estado for i in dl.respaldos] == ["sin lugar"] * 5 + ["ok"]
        assert dl.respaldos[-1].d_mm == 9.5 and all(i.d_mm is None and i.centro is None and "no deja poner la ventana a más de 5 mm del campo" in i.motivo for i in dl.respaldos[:5])

    def test_e_en_la_esquina_superior_derecha_gana_el_lateral_s_01_del_lado_k(self):
        s = A2._sint("B", 0.4)
        p = piso(A2._a_pelicula(_etiqueta(s.img, s, "UR", 9.7, valor=245)), s.campo)
        ur = p.esquinas[1]
        assert ur.estado == "reemplazada" and ur.origen == "lateral s=0.1 del lado UR-DR"
        assert [i.nombre for i in ur.respaldos] == NOMBRES_DE_LOS_SEIS["UR"][:5] and [i.estado for i in ur.respaldos] == ["sin lugar"] * 4 + ["ok"]
        assert ur.respaldos[-1].d_mm == 6.5

    def test_e_etiquetas_en_dos_esquinas_no_tienen_respaldo_y_el_motivo_es_que_la_pelicula_no_sobresale(self):
        """Dos esquinas sin pelicula (las etiquetas blancas la quitan): no es un defecto de UNA esquina, asi que no se intenta ningun respaldo; como las dos fallan por falta de pelicula, el motivo es el
        de un recorte demasiado ajustado, que pide escanear la pelicula entera."""
        s = A2._sint("B", 0.4)
        pel = _pel()
        a = _etiqueta(_etiqueta(s.img, s, "DR", 9.7, valor=245), s, "UL", 9.7, valor=245)
        p = piso(A2._a_pelicula(a), s.campo)
        assert p.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PELICULA), p.estado
        assert "superior izquierda: 0 píxeles; inferior derecha: 0 píxeles" in p.estado and "hacen falta 2000 a más de 5 mm del campo en cada una" in p.estado
        assert "escanee la película entera" in p.estado and "película virgen" in p.estado
        assert [e.estado for e in p.esquinas] == ["falla", "ok", "falla", "ok"] and all(e.respaldos == () for e in p.esquinas)
        assert p.region is None and all(c.mediana is None for c in p.capas.values())

    def test_e_dos_esquinas_fuera_del_rango_no_tienen_respaldo_y_el_motivo_nombra_a_cada_una(self):
        s = A2._sint("B", 0.4)
        pel = _pel()
        a = s.img
        for esquina in ("DR", "UL"):
            a = _etiqueta(a, s, esquina, 20.0, rojo_mas=70)
        p = piso(A2._a_pelicula(a), s.campo)
        assert p.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PISO), p.estado
        assert "superior izquierda: fuera del rango esperado: rojo" in p.estado and "inferior derecha: fuera del rango esperado: rojo" in p.estado and "no es un defecto de una sola esquina" in p.estado
        assert [e.estado for e in p.esquinas] == ["falla", "ok", "falla", "ok"] and all(e.respaldos == () for e in p.esquinas)

    def test_e_una_etiqueta_que_tapa_la_esquina_y_sus_seis_candidatos_deja_la_esquina_sin_piso_y_el_piso_sale_de_las_otras_tres(self):
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        etiquetada = _etiqueta(s.img, s, "DR", 20.0, valor=245)
        p = piso(A2._a_pelicula(etiquetada), s.campo)
        assert p.estado == "ok", p.estado
        dr = p.esquinas[2]
        assert dr.estado == "sin piso" and dr.origen == "esquina" and dr.motivo.startswith("sin película suficiente (")
        assert [i.nombre for i in dr.respaldos] == NOMBRES_DE_LOS_SEIS["DR"] and all(i.estado == "sin lugar" for i in dr.respaldos)
        assert [e.estado for i, e in enumerate(p.esquinas) if i != 2] == ["ok"] * 3
        region = _region(p, s.forma)
        assert not (region & o.cunas["DR"]).any(), "la esquina sin piso dejo pixeles en la region"
        assert p.region.n == sum(e.n for e in p.esquinas if e.estado == "ok")
        verdad = o.piso(region=region)
        assert all(abs(p.capas[c].mediana - verdad[c]) <= 1.0 for c in "BGR")

    @staticmethod
    def _con_las_seis_ventanas_fuera_del_rango(s):
        """Todo el borde de la pelicula a menos de 18 mm de la esquina inferior derecha con el rojo +70: la esquina y los seis candidatos caen en pelicula limpia pero fuera del rango."""
        return A2._a_pelicula(_pintar_rojo_cerca_de_la_esquina(s, "DR", 18.0))

    def test_e_los_seis_candidatos_se_prueban_en_orden_a_la_mayor_distancia_que_cabe_y_ninguno_entra_a_la_zona_prohibida(self):
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        pel = self._con_las_seis_ventanas_fuera_del_rango(s)
        p = piso(pel, s.campo)
        assert p.estado == "ok", p.estado
        dr = p.esquinas[2]
        assert dr.estado == "sin piso" and "fuera del rango esperado" in dr.motivo
        assert [i.nombre for i in dr.respaldos] == NOMBRES_DE_LOS_SEIS["DR"] and all(i.estado == "falla" and "fuera del rango esperado" in i.motivo for i in dr.respaldos)
        assert [i.d_mm for i in dr.respaldos] == [9.5, 7.5, 9.5, 7.5, 9.5, 7.5], "la mayor distancia a la que la pelicula deja poner cada ventana (referencia: a3_prototipo_piso.py)"
        for i in dr.respaldos:
            # 1. el centro esta donde la geometria independiente lo pone y a la distancia que dice
            esperado = np.array(_centro_de_un_respaldo(s.campo, 2, i.nombre, i.d_mm))
            assert np.hypot(*(np.array(i.centro) - esperado)) <= 1.0, (i.nombre, i.centro, esperado)
            assert abs(float(_distancia_a_los_lados(s.campo, *i.centro)) * ESC - i.d_mm) <= 0.03
            # 2. nunca la zona prohibida: el lateral con s <= 0.10 (en el lado que dice su nombre) y el giro de 5 grados dentro de la cuña de la esquina
            s_, lado, _ = _s_y_lado(s.campo, i.centro[0], i.centro[1])
            if i.nombre.startswith("lateral"):
                nominal = float(i.nombre.split("s=")[1].split()[0])
                assert abs(float(s_[0]) - nominal) <= 0.01 and float(s_[0]) <= 0.10 + 0.01, (i.nombre, float(s_[0]))
                assert ESQUINAS[int(lado[0])] + "-" + ESQUINAS[(int(lado[0]) + 1) % 4] == i.nombre.split("lado ")[1]
            else:
                c0 = _cruce_de_diagonales(s.campo)
                a, b = np.array(s.campo[2]) - c0, np.array(i.centro) - c0
                angulo = math.degrees(math.acos(np.dot(a, b) / (np.hypot(*a) * np.hypot(*b))))
                assert abs(angulo - 5.0) <= 0.2, (i.nombre, angulo)
            # 3. la mayor distancia que cabe, segun el oraculo: a esa d hay pelicula limpia para la ventana y a 0.5 mm mas lejos ya no
            assert _pixeles_de_la_ventana(o, i.centro) >= 2000 - 80
            if i.d_mm + 0.5 <= 11.0:
                mas_lejos = _centro_de_un_respaldo(s.campo, 2, i.nombre, i.d_mm + 0.5)
                assert _pixeles_de_la_ventana(o, mas_lejos) < 2000 + 80, f"{i.nombre}: cabia a {i.d_mm + 0.5} mm y la funcion lo puso a {i.d_mm}"

    def test_e_los_parametros_del_respaldo_se_usan(self):
        s = A2._sint("B", 0.4)
        pel = self._con_las_seis_ventanas_fuera_del_rango(s)
        giro = piso(pel, s.campo, _P(giro_respaldo_grados=8.0)).esquinas[2]
        assert [i.nombre for i in giro.respaldos][:2] == ["giro +8 grados", "giro -8 grados"]
        s_ = piso(pel, s.campo, _P(s_respaldo=[0.03, 0.08])).esquinas[2]
        assert [i.nombre for i in s_.respaldos][2:] == ["lateral s=0.03 del lado DR-DL", "lateral s=0.03 del lado UR-DR", "lateral s=0.08 del lado DR-DL", "lateral s=0.08 del lado UR-DR"]
        corto = piso(pel, s.campo, _P(distancia_respaldo_maxima_mm=8.0)).esquinas[2]
        assert all(i.d_mm <= 8.0 for i in corto.respaldos if i.d_mm is not None) and corto.respaldos[0].d_mm == 8.0
        paso = piso(pel, s.campo, _P(paso_respaldo_mm=1.0)).esquinas[2]
        assert all(i.d_mm in (11.0, 10.0, 9.0, 8.0, 7.0) for i in paso.respaldos if i.d_mm is not None)

    def test_e_el_minimo_de_esquinas_se_usa(self):
        """Con `esquinas_minimas` = 4 una esquina sin piso ya es «no medible»; con 2, dos esquinas sin piso todavia miden con las otras dos."""
        recorte = A2._sint("A", 1.0)
        assert piso(recorte.pelicula, recorte.campo).estado == "ok"
        assert piso(recorte.pelicula, recorte.campo, _P(esquinas_minimas=4)).estado.startswith("no medible")
        s = A2._sint("B", 0.4)
        a = _etiqueta(_etiqueta(s.img, s, "DR", 20.0, valor=245), s, "UL", 20.0, valor=245)
        pel = A2._a_pelicula(a)
        assert piso(pel, s.campo).estado.startswith("no medible")
        dos = piso(pel, s.campo, _P(esquinas_minimas=2))
        assert dos.estado == "ok" and [e.estado for e in dos.esquinas] == ["sin piso", "ok", "sin piso", "ok"]
        assert dos.region.n == dos.esquinas[1].n + dos.esquinas[3].n

    def test_e_la_tinta_se_aparta_antes_de_elegir_lo_mas_lejano_de_la_cuna(self):
        """Tinta oscura sobre casi todo lo que usa la esquina inferior derecha (todo menos sus 1000 pixeles mas cercanos al campo): la tinta se aparta ANTES de elegir el 20 % mas lejano de la cuña
        (regla 2), asi que la esquina elige entre la pelicula limpia que queda, conserva sus 2000 pixeles y es «ok» con su propio conjunto. Si se eligiera primero lo mas lejano y la tinta se
        apartara despues, la esquina quedaria con 1000 pixeles, bajo el minimo, y pasaria al respaldo."""
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        limpio = piso(s.pelicula, s.campo)
        usados = _region(limpio, s.forma) & o.cunas["DR"]
        ys, xs = np.nonzero(usados)
        assert limpio.esquinas[2].n >= 2000 and len(ys) >= 1500, "la esquina de la sintetica tiene que usar al menos 2000 pixeles para que la prueba discrimine"
        lejos = np.hypot(xs - s.campo[2][0], ys - s.campo[2][1])
        mas_lejanos = np.argsort(lejos, kind="stable")[1000:]
        tinta = np.zeros(s.forma, bool)
        tinta[ys[mas_lejanos], xs[mas_lejanos]] = True
        a = np.array(s.img).copy()
        rojo = a[:, :, 2].astype(np.int16)
        rojo[tinta] -= 90
        a[:, :, 2] = np.clip(rojo, 0, 255).astype(np.uint8)
        p = piso(A2._a_pelicula(a), s.campo)
        dr = p.esquinas[2]
        assert p.estado == "ok" and dr.estado == "ok" and dr.origen == "esquina" and dr.n >= 2000 and dr.respaldos == (), (dr.estado, dr.origen, dr.n, dr.motivo)
        region = _region(p, s.forma)
        assert not (region & tinta).any(), "la region conserva pixeles de tinta"
        verdad = o.piso(region=region)
        assert all(abs(p.capas[c].mediana - verdad[c]) <= 1.0 for c in "BGR")

    def test_e_el_respaldo_tambien_aparta_la_tinta_de_su_ventana(self):
        """El rojo +70 a menos de 6 mm de la esquina de la pelicula hace fallar la esquina inferior derecha (fuera del rango) y el primer candidato (giro +5, su ventana a 9.5 mm del campo) la
        reemplaza con 2391 pixeles. Con una tira de tinta oscura (cuatro columnas, el rojo -90) por el centro de ESA ventana, la tinta se aparta antes de comprobarla: el mismo candidato gana con
        menos pixeles (los de la tinta ya no cuentan) y su region no tiene tinta. Sin apartar la tinta del respaldo, el candidato conservaria los 2391."""
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        pintada = _pintar_rojo_cerca_de_la_esquina(s, "DR", 6.0)
        sin_tinta = piso(A2._a_pelicula(pintada), s.campo).esquinas[2]
        assert sin_tinta.estado == "reemplazada" and sin_tinta.origen == "giro +5 grados" and sin_tinta.respaldos[0].estado == "ok", (sin_tinta.estado, sin_tinta.origen)
        cx, cy = sin_tinta.respaldos[0].centro
        h = 3.0 / 2.0 / ESC
        franja = np.zeros(s.forma, bool)
        franja[int(round(cy - h)):int(round(cy + h)) + 1, int(round(cx)) - 2:int(round(cx)) + 2] = True
        a = np.array(pintada).copy()
        tinta = franja & (a.min(axis=2) < 235)
        rojo = a[:, :, 2].astype(np.int16)
        rojo[tinta] -= 90
        a[:, :, 2] = np.clip(rojo, 0, 255).astype(np.uint8)
        p = piso(A2._a_pelicula(a), s.campo)
        dr = p.esquinas[2]
        assert p.estado == "ok" and dr.estado == "reemplazada" and dr.origen == "giro +5 grados" and dr.respaldos[0].estado == "ok", (dr.estado, dr.origen)
        assert sin_tinta.respaldos[0].n - dr.respaldos[0].n >= 100 and dr.respaldos[0].n >= 2000, (sin_tinta.respaldos[0].n, dr.respaldos[0].n)
        region = _region(p, s.forma)
        assert not (region & tinta).any(), "la region conserva pixeles de tinta"
        verdad = o.piso(region=region)
        assert all(abs(p.capas[c].mediana - verdad[c]) <= 1.0 for c in "BGR")

    def test_e_el_recorte_a_ras_girado_1_grado_pierde_la_esquina_superior_izquierda_y_mide_con_tres(self):
        s = A2._sint("A", 1.0)
        o = _oraculo(s)
        p = piso(s.pelicula, s.campo)
        ul = p.esquinas[0]
        assert p.estado == "ok" and ul.estado == "sin piso" and [e.estado for e in p.esquinas[1:]] == ["ok"] * 3
        assert ul.motivo.startswith("sin película suficiente (") and 1450 <= int(ul.motivo.split("(")[1].split()[0]) <= 1560, ul.motivo
        assert [i.nombre for i in ul.respaldos] == NOMBRES_DE_LOS_SEIS["UL"] and all(i.estado == "sin lugar" for i in ul.respaldos)
        verdad = o.piso(region=_region(p, s.forma))
        assert all(abs(p.capas[c].mediana - verdad[c]) <= 1.0 for c in "BGR")

    def test_e_el_recorte_a_ras_girado_menos_3_grados_no_se_puede_medir_y_el_motivo_pide_la_pelicula_entera(self):
        """Tres esquinas sin pelicula a mas de 5 mm del campo (0, 0 y 1345 pixeles): en esos encuadres la unica pelicula elegible es el lateral, que en las reales esta 11 a 38 niveles por
        debajo de la esquina. A.2 lo medio con el lateral; A.3 dice que la pelicula no sobresale lo bastante."""
        s = A2._sint("A", -3.0)
        p = piso(s.pelicula, s.campo)
        assert p.estado.startswith(_pel().MOTIVO_ESQUINAS_SIN_PELICULA), p.estado
        assert "superior izquierda: 0 píxeles; superior derecha: 0 píxeles; inferior izquierda: 1345 píxeles" in p.estado, p.estado
        assert [e.estado for e in p.esquinas] == ["falla", "falla", "ok", "falla"] and p.region is None

    def test_e_la_pagina_recortada_a_5_5_mm_del_campo_no_se_puede_medir_y_a_6_mm_si(self):
        pel = _pel()
        sin_lugar, campo = A2.TestSinMargenNuncaUnNumero._recortada_con_margen_mm(5.5)
        p = piso(sin_lugar, campo)
        assert p.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PELICULA), p.estado
        assert "superior izquierda: 1396 píxeles; superior derecha: 1324 píxeles; inferior derecha: 1247 píxeles; inferior izquierda: 1315 píxeles" in p.estado, p.estado
        alcanza, campo = A2.TestSinMargenNuncaUnNumero._recortada_con_margen_mm(6.0)
        q = piso(alcanza, campo)
        assert q.estado == "ok" and [e.n for e in q.esquinas] == [2000] * 4 and q.region.n == 8000 and abs(q.region.distancia_media_mm - 5.876) <= 0.02, (q.estado, [e.n for e in q.esquinas])
        for margen in (3.0, 4.0, 4.5):
            r, campo = A2.TestSinMargenNuncaUnNumero._recortada_con_margen_mm(margen)
            assert piso(r, campo).estado == pel.MOTIVO_SIN_PISO, f"a {margen} mm no hay ni 2000 pixeles en total"
        siete, campo = A2.TestSinMargenNuncaUnNumero._recortada_con_margen_mm(7.0)
        assert piso(siete, campo).estado == "ok"


class TestLaVentanaDelRespaldo:
    """La ventana de 3 x 3 mm de un candidato del respaldo, probada SOLA con una pelicula y un campo hechos aqui (la funcion es privada, pero es la unidad que decide dos cosas del diseño §3.3:
    que solo cuenten los pixeles a mas de `margen_campo_mm` del campo y que haya al menos `pixeles_minimos` o no haya ventana)."""

    CAMPO = [(1000.0, 1000.0), (2500.0, 1000.0), (2500.0, 2500.0), (1000.0, 2500.0)]

    @staticmethod
    def _llamar(limpia, cx, cy, **cambios):
        pel = _pel()
        p = pel._piso_parametros(_P(**cambios))
        return pel._piso_ventana_de_respaldo(limpia, (0, 0), np.asarray(TestLaVentanaDelRespaldo.CAMPO, np.float64), ESC, p, cx, cy)

    @staticmethod
    def _cuadricula(cx, cy):
        """Las columnas y filas de la ventana de 3 mm centrada en (cx, cy), contadas aqui (|x - cx| <= 1.5 mm)."""
        h = 3.0 / 2.0 / ESC
        columnas = [x for x in range(int(np.floor(cx - h)) - 2, int(np.ceil(cx + h)) + 3) if abs(x - cx) <= h]
        filas = [y for y in range(int(np.floor(cy - h)) - 2, int(np.ceil(cy + h)) + 3) if abs(y - cy) <= h]
        return columnas, filas

    def test_e_la_ventana_solo_cuenta_los_pixeles_a_mas_de_5_mm_del_campo(self):
        limpia = np.ones((3000, 3000), bool)
        cx, cy = 1000.0 - 6.0 / ESC, 1750.0                      # el centro a 6 mm del lado izquierdo del campo: la ventana va de 4.5 a 7.5 mm
        columnas, filas = self._cuadricula(cx, cy)
        a_mas_de_5 = [x for x in columnas if (1000.0 - x) * ESC > 5.0]
        assert 0 < len(a_mas_de_5) < len(columnas), "la ventana tiene que cruzar los 5 mm para que la prueba discrimine"
        ys, xs = self._llamar(limpia, cx, cy)
        assert len(ys) == len(a_mas_de_5) * len(filas) and ((1000.0 - xs) * ESC > 5.0).all()
        assert sorted(set(xs.tolist())) == a_mas_de_5
        # el parametro: sin margen entra toda la ventana; con un margen de 7 mm solo lo que pasa de 7 mm
        todos = self._llamar(limpia, cx, cy, margen_campo_mm=0.0)
        assert len(todos[0]) == len(columnas) * len(filas)
        a_mas_de_7 = [x for x in columnas if (1000.0 - x) * ESC > 7.0]
        assert len(self._llamar(limpia, cx, cy, margen_campo_mm=7.0, pixeles_minimos=100)[0]) == len(a_mas_de_7) * len(filas)

    @pytest.mark.parametrize("n,hay_ventana", [(1999, False), (2000, True)])
    def test_e_la_ventana_exige_los_pixeles_minimos(self, n, hay_ventana):
        cx, cy = 1000.0 - 9.0 / ESC, 1750.0                      # a 9 mm: toda la ventana esta a mas de 5 mm
        limpia = np.zeros((3000, 3000), bool)
        x0, y0, ancho = int(cx) - 20, int(cy) - 20, 40
        alto, resto = divmod(n, ancho)
        limpia[y0:y0 + alto, x0:x0 + ancho] = True
        limpia[y0 + alto, x0:x0 + resto] = True
        assert int(limpia.sum()) == n
        res = self._llamar(limpia, cx, cy)
        if hay_ventana:
            assert res is not None and len(res[0]) == n
        else:
            assert res is None, "una ventana con menos de `pixeles_minimos` pixeles no es una ventana"
            assert self._llamar(limpia, cx, cy, pixeles_minimos=1500) is not None, "el minimo es el parametro `pixeles_minimos`"


# ====================================================================================================================== (f) el fleco del corte

class TestElFlecoDelCorte:
    @staticmethod
    def _pintar(img, mascara):
        a = np.array(img).copy()
        rojo, azul = a[:, :, 2].astype(np.int16), a[:, :, 0].astype(np.int16)
        rojo[mascara] -= 10
        azul[mascara] += 20
        a[:, :, 2], a[:, :, 0] = np.clip(rojo, 0, 255).astype(np.uint8), np.clip(azul, 0, 255).astype(np.uint8)
        return a

    def test_f_el_anillo_de_1_mm_junto_al_corte_no_entra_al_piso(self):
        """A 0.5-1.0 mm del corte, a igual distancia del campo, el rojo baja 2-7 niveles y el azul sube 2-24 (el fleco, medido el 13-10): el rojo -10 y el azul +20 en el anillo de 1 mm. Con el
        margen de 1.0 mm el piso no se entera; con 0.5 mm (el de A.2) el anillo de 0.5 a 1.0 mm entra y lo mueve (el control)."""
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        anillo = o.pelicula & (o.borde_mm <= 1.0)
        pel = A2._a_pelicula(self._pintar(s.img, anillo))
        limpio = piso(s.pelicula, s.campo)
        con_fleco = piso(pel, s.campo)
        assert not (_region(con_fleco, s.forma) & anillo).any(), "el anillo de 1 mm entro a la region"
        assert all(abs(con_fleco.capas[c].mediana - limpio.capas[c].mediana) <= 0.5 for c in CAPAS)
        # con el fleco dentro de la region la esquina sale «dispersa» (IQR) o fuera de rango y el piso es «no medible»: otra proteccion del mismo fleco. El CONTROL abre el IQR y el rango para ver lo que
        # el margen de 1 mm evita (la mediana movida), como el control de la regla (7).
        a_medio = piso(pel, s.campo, _P(margen_borde_mm=0.5, **ABIERTO))
        assert a_medio.parametros["margen_borde_mm"] == 0.5
        assert (_region(a_medio, s.forma) & anillo).any() and abs(a_medio.capas["B"].mediana - limpio.capas["B"].mediana) >= 2.0, "con 0.5 mm el anillo tendria que entrar (el control)"

    def test_f_el_borde_de_la_imagen_tambien_se_aparta(self):
        """En un recorte a ras el corte de la pelicula puede coincidir con el borde de la imagen: la banda de 1 mm pegada al borde de la imagen no entra al piso. Con
        `apartar_borde_de_la_imagen` = False (el comportamiento de A.2) si entra: el control."""
        s = A2._sint("A", 0.0)
        banda = np.zeros(s.forma, bool)
        k = int(1.0 / ESC)
        banda[:k, :] = banda[-k:, :] = True
        banda[:, :k] = banda[:, -k:] = True
        pel = A2._a_pelicula(self._pintar(s.img, banda))
        limpio = piso(s.pelicula, s.campo)
        con_banda = piso(pel, s.campo)
        assert not (_region(con_banda, s.forma) & banda).any() and all(abs(con_banda.capas[c].mediana - limpio.capas[c].mediana) <= 0.5 for c in CAPAS)
        sin_apartar = piso(pel, s.campo, _P(apartar_borde_de_la_imagen=False, **ABIERTO))
        assert sin_apartar.parametros["apartar_borde_de_la_imagen"] is False
        assert (_region(sin_apartar, s.forma) & banda).any() and abs(sin_apartar.capas["B"].mediana - limpio.capas["B"].mediana) >= 2.0, "sin apartar el borde de la imagen la banda tendria que entrar (el control)"

    def test_f_el_sexto_clic_tambien_aparta_el_borde_de_la_pelicula_de_1_mm(self):
        s, pel = A2.TestElSextoClic._con_un_trozo_sin_irradiar()
        p = piso(pel, s.campo, punto=A2.PUNTO_DEL_PARCHE)
        assert p.estado == "ok" and p.region.n >= 2000 and p.parametros["margen_borde_mm"] == 1.0
        assert piso(pel, s.campo, _P(margen_borde_mm=0.0), punto=(2951.0, 120.0)).estado == "ok" and piso(pel, s.campo, punto=(2951.0, 120.0)).estado == _pel().MOTIVO_POCA_PELICULA_EN_EL_PUNTO

    def test_f_el_sexto_clic_junto_al_borde_de_la_imagen_aparta_la_banda_de_1_mm(self):
        """Un recorte a ras (la pelicula llega al borde de la imagen) con el fleco del corte en su banda de 1 mm, y un sexto clic a 2 mm del borde: su cuadrado de 3 x 3 mm llega a 0.5 mm del
        borde. El cuadrado no toma la banda (el borde de la imagen es un borde, como en la region automatica). Con `apartar_borde_de_la_imagen` = False (A.2) si la toma: el control."""
        s = A2._sint("A", 0.0)
        banda = np.zeros(s.forma, bool)
        k = int(1.0 / ESC)
        banda[:k, :] = banda[-k:, :] = True
        banda[:, :k] = banda[:, -k:] = True
        pel = A2._a_pelicula(self._pintar(s.img, banda))
        punto = (2.0 / ESC, s.forma[0] / 2.0)
        p = piso(pel, s.campo, punto=punto)
        assert p.estado == "ok" and p.region.n >= 2000, p.estado
        assert not (_region(p, s.forma) & banda).any(), "el cuadrado del sexto clic tomo la banda del borde de la imagen"
        sin_apartar = piso(pel, s.campo, _P(apartar_borde_de_la_imagen=False), punto=punto)
        assert (_region(sin_apartar, s.forma) & banda).any(), "sin apartar el borde de la imagen la banda tendria que entrar (el control)"


# ====================================================================================================================== (g) la pelicula virgen

FECHA = "2026-10-13"
INSTANTE_FIJO = "2031-02-03 23:59:59"      # el reloj congelado de las pruebas que leen la hora; a un segundo de la medianoche, a proposito: ni el dia ni la medianoche pueden moverlo
NOMBRES_DE_LAS_PRUEBAS = ["C1 cadena", "C2 zona", "C3 recorte", "C3 fondo", "C7 ruido", "C6 motas", "rango", "azul testigo", "C5 uniformidad", "C5 gradiente", "C7 rayas"]
_CACHE_VIRGEN = {}


class _RelojFijo:
    """El modulo `time` con el reloj CONGELADO: `strftime` formatea siempre el mismo instante y todo lo demas es el modulo real. Se pone en el espacio de nombres de `pelicula` (y solo ahi: el
    reloj de la maquina no se toca) con la fixture `reloj_fijo`. Asi una prueba que compara con «hoy» no depende del dia en que corra ni de si la medianoche cae en medio de una medicion
    (la clase de DP-75, DP-94 y DP-155; RV-A3-4 de la ronda 1 de la revision)."""
    def __init__(self, instante=INSTANTE_FIJO):
        self._instante = time.strptime(instante, "%Y-%m-%d %H:%M:%S")

    def strftime(self, formato, *resto):
        return time.strftime(formato, *(resto or (self._instante,)))

    def __getattr__(self, nombre):
        return getattr(time, nombre)


@pytest.fixture
def reloj_fijo(monkeypatch):
    reloj = _RelojFijo()
    monkeypatch.setattr(_pel(), "time", reloj)
    return reloj


def _virgen_arreglo(variante="A", bits=8, calib_extra=None, fondo_puro=True, **kw):
    """La pelicula virgen sintetica de PF.0 (`meseta = virgen`, sin dosis ni tinta): un arreglo BGR escribible. El generador pone ruido tambien en el fondo de la pagina, asi que C3 fondo avisaria
    en toda sintetica de pagina: `fondo_puro` lo fija en el maximo exacto (como lo entrega un escaner con la tapa cerrada)."""
    calib = dict(gen.CALIB, meseta_bgr=gen.CALIB["virgen_bgr"], fondo_escaner=255.0)
    calib.update(calib_extra or {})
    img, _ = gen.generar_arreglo(variante=variante, theta_deg=0.0, bits=bits, dpi=600, tinta=False, calib=calib, **kw)
    img = np.array(img)
    if fondo_puro:
        img[img.min(axis=2) >= (235 if bits == 8 else 235 * 257)] = 255 if bits == 8 else 65535
    return img


def _medir_virgen(datos, nombre="virgen_lote.tif", P=None, **kw):
    return _pel().piso_de_pelicula_virgen(datos, _P() if P is None else P, nombre, fecha_calculo=FECHA, **kw)


def _resultados(ref):
    return {p.nombre: p.resultado for p in ref.pruebas}


def _base():
    """(referencia, datos) de la virgen sintetica de siempre (recorte a ras, TIFF de 8 bits). Se mide una vez por proceso: es inmutable y ninguna prueba la modifica."""
    if "base" not in _CACHE_VIRGEN:
        datos = gen.codificar(_virgen_arreglo("A"), "tiff", 600)
        _CACHE_VIRGEN["base"] = (_medir_virgen(datos), datos)
    return _CACHE_VIRGEN["base"]


def _no_valida():
    """Una referencia «no valida» (la virgen sintetica escaneada a 300 ppp: C1 la rechaza). Inmutable; se mide una vez por proceso."""
    if "no_valida" not in _CACHE_VIRGEN:
        _CACHE_VIRGEN["no_valida"] = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 300))
    return _CACHE_VIRGEN["no_valida"]


def liberar_las_virgenes():
    """Suelta lo que este modulo guarda entre pruebas: `_CACHE_VIRGEN` (B.4, deuda heredada de B.3, R1-LD-02): la virgen sintetica en TIFF y su referencia medida (3 elementos y 64 MB medidos al terminar el
    archivo). Una fixture de modulo autouse la llama DESPUES de su yield. Vaciar es siempre seguro: se recalcula la primera vez que una prueba la pide."""
    _CACHE_VIRGEN.clear()
    gc.collect()


@pytest.fixture(scope="module", autouse=True)
def _suelta_las_virgenes_al_terminar_el_modulo():
    yield
    liberar_las_virgenes()


@pytest.fixture(scope="module", autouse=True)
def _suelta_los_objetos_caros_de_a2_al_terminar_el_modulo():
    """A.3 llena tambien el cache de A.2 (`A2._sint`, `A2._real`, `A2._con_fondo`: 11 objetos y 2677 MB medidos al terminar este archivo) y el modulo de A.2 solo lo suelta al terminar el SUYO: en la suite repartida
    en procesos el cache de A.2 quedaba vivo en el proceso que corriera A.3 aunque A.2 estuviera en otro."""
    yield
    A2.liberar_los_objetos_caros()


def _valores(ref):
    return {c: ref.valor(c) for c in CAPAS}


class TestLaPeliculaVirgen:
    def test_g_la_virgen_sintetica_en_una_pagina_da_la_virgen_del_generador_con_todas_las_pruebas_en_ok(self):
        datos = gen.codificar(_virgen_arreglo("B"), "tiff", 600)
        ref = _medir_virgen(datos)
        assert ref.estado == "ok", ref.estado
        v = _valores(ref)
        assert abs(v["R"] - 105.5) <= 0.5 and abs(v["G"] - 174.0) <= 0.5 and abs(v["B"] - 82.0) <= 0.5 and abs(v["gris"] - 143.0) <= 0.6, v
        assert [p.nombre for p in ref.pruebas] == NOMBRES_DE_LAS_PRUEBAS and set(_resultados(ref).values()) == {"ok"} and ref.avisos == ()
        for c in CAPAS:
            capa = ref.capas[c]
            assert capa.estado == "ok" and capa.n > 100000 and capa.iqr is not None and 0 < capa.iqr < 6, (c, capa)
        # la procedencia: de donde salio el archivo, con su huella
        pr = ref.procedencia
        assert pr["archivo"] == "virgen_lote.tif" and pr["sha256"] == hashlib.sha256(datos).hexdigest() and pr["bytes"] == len(datos)
        assert pr["formato"] == "TIFF" and pr["bits"] == 8 and abs(pr["dpi_declarado"] - 600.0) < 0.01 and pr["clase_resolucion"] == "coincide" and pr["forma"] == [3300, 3300]
        assert pr["fecha_calculo"] == FECHA and pr["version"] == "PV-2" and pr["orientacion_declarada"] is None and pr["calidad_jpeg"] is None
        assert ref.region["n"] == ref.capas["G"].n and ref.region["area_mm2"] > 10000 and len(ref.region["caja"]) == 4
        assert {k: ref.parametros[k] for k in PLAN_DE_LA_VIRGEN} == PLAN_DE_LA_VIRGEN and {k: ref.parametros[k] for k in PLAN_DEL_PISO} == PLAN_DEL_PISO
        # el control del fondo: con el ruido del generador en el fondo de la pagina, C3 fondo avisa
        ruidosa = _medir_virgen(gen.codificar(_virgen_arreglo("B", fondo_puro=False), "tiff", 600))
        assert ruidosa.estado == "ok" and _resultados(ruidosa)["C3 fondo"] == "aviso" and any("fondo" in a for a in ruidosa.avisos)

    def test_g_la_orientacion_declarada_y_la_fecha_de_calculo_se_guardan(self, reloj_fijo):
        ref = _medir_virgen(_base()[1], orientacion_declarada="girada")
        assert ref.procedencia["orientacion_declarada"] == "girada" and ref.procedencia["fecha_calculo"] == FECHA
        # sin `fecha_calculo` la produccion lee el reloj (hoy): el reloj va CONGELADO, asi la prueba no compara con una segunda lectura del reloj de la maquina (que, si la medianoche cae en
        # medio de la medicion, daria otro dia: RV-A3-4) y la fecha por omision se verifica EXACTA
        hoy = _pel().piso_de_pelicula_virgen(_base()[1], _P(), "virgen_lote.tif")
        assert hoy.procedencia["fecha_calculo"] == "2031-02-03"

    def test_g_los_16_bits_dan_lo_mismo_que_los_8(self):
        ref = _medir_virgen(gen.codificar(_virgen_arreglo("A", bits=16), "tiff", 600))
        base = _base()[0]
        assert ref.estado == "ok" and ref.procedencia["bits"] == 16
        for c in CAPAS:
            assert abs(ref.valor(c) - base.valor(c)) <= 0.6, c
        assert abs(ref.valor("R") - 105.5) <= 0.2, "con 16 bits la mediana resuelve decimales"

    def test_g_recortada_a_ras_no_tiene_fondo_y_da_lo_mismo(self):
        ref, base = _base()[0], _medir_virgen(gen.codificar(_virgen_arreglo("B"), "tiff", 600))
        assert ref.estado == "ok" and {p.nombre: (p.resultado, p.texto) for p in ref.pruebas}["C3 fondo"] == ("ok", "no se ve fondo del escáner; no se juzga"), "OD.1: antes se omitia en silencio"
        assert all(abs(ref.valor(c) - base.valor(c)) <= 0.6 for c in CAPAS)

    def test_g_un_jpeg_vuelto_a_guardar_avisa_de_la_cadena_de_captura(self):
        ref = _medir_virgen(gen.codificar(_virgen_arreglo("B"), "jpeg", 600), nombre="virgen.jpg")
        assert ref.estado == "ok" and _resultados(ref)["C1 cadena"] == "aviso"
        assert any("vuelto a guardar por un editor" in a for a in ref.avisos), ref.avisos
        pr = ref.procedencia
        assert pr["formato"] == "JPEG" and pr["submuestreo"] == "4:2:0" and 94 <= pr["calidad_jpeg"] <= 96
        assert all(abs(ref.valor(c) - v) <= 1.0 for c, v in (("R", 105.5), ("G", 174.0), ("B", 82.0)))
        # el umbral de calidad es un parametro: con 99 un JPEG de calidad 95 ya no parece vuelto a guardar y el aviso es el de «se recomienda TIFF»
        menos = _medir_virgen(gen.codificar(_virgen_arreglo("B"), "jpeg", 600), nombre="virgen.jpg", P=_P(calidad_jpeg_editor=99.0))
        assert _resultados(menos)["C1 cadena"] == "aviso" and not any("vuelto a guardar" in a for a in menos.avisos) and any("TIFF sin compresión" in a for a in menos.avisos), menos.avisos

    def test_g_una_virgen_declarada_a_96_ppp_es_un_archivo_vuelto_a_guardar(self):
        ref = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 96))
        assert ref.estado == "ok" and ref.procedencia["clase_resolucion"] == "editor" and _resultados(ref)["C1 cadena"] == "aviso"
        assert any("vuelto a guardar por un editor" in a for a in ref.avisos)

    def test_g_una_virgen_escaneada_a_300_ppp_se_rechaza_sin_mirar_nada_mas(self):
        ref = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 300))
        assert ref.estado.startswith("no válida: ") and ref.estado == _pel().PREFIJO_NO_VALIDA + ref.pruebas[0].texto
        assert [(p.nombre, p.resultado) for p in ref.pruebas] == [("C1 cadena", "rechazo")] and "300" in ref.pruebas[0].texto
        assert all(ref.valor(c) is None and ref.capas[c].estado.startswith("no") for c in CAPAS) and ref.region is None

    def test_g_la_pelicula_irradiada_no_es_virgen_por_el_rango_y_su_recorte_y_su_uniformidad_solo_avisan(self):
        """OD.1 (DA-87): lo unico que rechaza una pelicula irradiada es el rango de una pelicula sin irradiar; su recorte (C3) y su uniformidad (C5) AVISAN y se ven en la tabla."""
        irradiada = A2._sint("B", 0.0)
        ref = _medir_virgen(gen.codificar(np.array(irradiada.img), "tiff", 600))
        malas = {p.nombre for p in ref.pruebas if p.resultado == "rechazo"}
        avisos = {p.nombre for p in ref.pruebas if p.resultado == "aviso"}
        assert ref.estado.startswith("no válida: ") and malas == {"rango"} and {"C3 recorte", "C5 uniformidad"} <= avisos, (ref.estado, malas, avisos)
        primero = next(p for p in ref.pruebas if p.resultado == "rechazo")
        assert ref.estado == _pel().PREFIJO_NO_VALIDA + primero.texto and primero.nombre == "rango"

    def test_g_una_zona_irradiada_avisa_por_uniformidad_y_no_se_rechaza(self):
        img = _virgen_arreglo("A").astype(np.float32)
        h, w = img.shape[:2]
        bulto = np.exp(-(((np.arange(w)[None, :] - w * 0.35) ** 2 + (np.arange(h)[:, None] - h * 0.35) ** 2) / (2 * 300.0 ** 2)))
        for canal, dv in ((0, -2), (1, -6), (2, -10)):
            img[:, :, canal] += dv * bulto
        ref = _medir_virgen(gen.codificar(np.clip(np.rint(img), 0, 255).astype(np.uint8), "tiff", 600))
        assert ref.estado == "ok" and not [p for p in ref.pruebas if p.resultado == "rechazo"], _resultados(ref)          # OD.1: la uniformidad avisa; la tabla de uniformidad y ruido la muestra
        texto = next(p.texto for p in ref.pruebas if p.nombre == "C5 uniformidad")
        assert _resultados(ref)["C5 uniformidad"] == "aviso" and "rojo" in texto and "no es uniforme" not in texto and texto in ref.avisos

    def test_g_una_irregularidad_leve_solo_avisa_y_no_rechaza(self):
        """El umbral de aviso no es el de rechazo: un bulto de -4 niveles en el rojo (3.8 % del valor) avisa y no rechaza."""
        img = _virgen_arreglo("A").astype(np.float32)
        h, w = img.shape[:2]
        bulto = np.exp(-(((np.arange(w)[None, :] - w * 0.35) ** 2 + (np.arange(h)[:, None] - h * 0.35) ** 2) / (2 * 300.0 ** 2)))
        img[:, :, 2] += -4.0 * bulto
        ref = _medir_virgen(gen.codificar(np.clip(np.rint(img), 0, 255).astype(np.uint8), "tiff", 600))
        assert ref.estado == "ok" and _resultados(ref)["C5 uniformidad"] == "aviso", _resultados(ref)

    def test_g_un_pixel_recortado_en_el_1_por_ciento_avisa_por_recorte_y_no_se_rechaza(self):
        img = _virgen_arreglo("A")
        rng = np.random.default_rng(3)
        img[:, :, 2][rng.random(img.shape[:2]) < 0.01] = 255
        ref = _medir_virgen(gen.codificar(img, "tiff", 600))
        assert ref.estado == "ok" and _resultados(ref)["C3 recorte"] == "aviso", _resultados(ref)          # OD.1: el recorte avisa (el rango de una pelicula sin irradiar es quien rechaza)
        assert "recortada" in next(p.texto for p in ref.pruebas if p.nombre == "C3 recorte")

    def test_g_el_recorte_entre_el_umbral_de_aviso_y_el_de_rechazo_solo_avisa(self):
        img = _virgen_arreglo("A")
        rng = np.random.default_rng(3)
        img[:, :, 2][rng.random(img.shape[:2]) < 0.0005] = 255                      # 0.05 %: mas que el aviso (0.01 %); desde OD.1 el recorte ya no rechaza ni con el 1 %
        ref = _medir_virgen(gen.codificar(img, "tiff", 600))
        assert _resultados(ref)["C3 recorte"] == "aviso" and ref.estado == "ok", _resultados(ref)

    def test_g_un_trozo_de_15_x_15_mm_no_es_suficiente_y_el_parametro_del_area_se_usa(self):
        img = _virgen_arreglo("B")
        chico = np.full_like(img, 255)
        h, w = img.shape[:2]
        lado = int(15.0 / ESC / 2)
        chico[h // 2 - lado:h // 2 + lado, w // 2 - lado:w // 2 + lado] = img[h // 2 - lado:h // 2 + lado, w // 2 - lado:w // 2 + lado]
        datos = gen.codificar(chico, "tiff", 600)
        ref = _medir_virgen(datos)
        assert ref.estado.startswith("no válida: ") and _resultados(ref)["C2 zona"] == "rechazo"
        texto = next(p.texto for p in ref.pruebas if p.nombre == "C2 zona")
        assert "a 2 mm de los bordes" in texto and "hacen falta 400" in texto and "121" in texto, texto
        assert [p.nombre for p in ref.pruebas] == ["C1 cadena", "C2 zona"] and ref.region is None
        con_menos = _medir_virgen(datos, P=_P(area_minima_virgen_mm2=100.0))
        assert _resultados(con_menos)["C2 zona"] == "ok" and con_menos.parametros["area_minima_virgen_mm2"] == 100.0

    def test_g_un_papel_gris_neutro_no_es_pelicula_y_el_rango_de_la_virgen_se_usa(self):
        img = _virgen_arreglo("A")
        rng = np.random.default_rng(3)
        gris = np.clip(np.rint(160.0 + rng.normal(0, 1.5, img.shape)), 0, 255).astype(np.uint8)
        datos = gen.codificar(gris, "tiff", 600)
        ref = _medir_virgen(datos)
        assert ref.estado.startswith("no válida: ") and _resultados(ref)["rango"] == "rechazo" and _resultados(ref)["azul testigo"] == "aviso"
        assert "azul 160 fuera de [65, 130]" in next(p.texto for p in ref.pruebas if p.nombre == "rango")
        abierta = _medir_virgen(datos, P=_P(piso_esperado_sin_irradiar={**PISO_ESPERADO_SIN_IRRADIAR, "B": [65.0, 200.0]}))
        assert _resultados(abierta)["rango"] == "ok" and abierta.estado == "ok"

    def test_g_un_papel_tan_claro_como_el_fondo_se_rechaza_por_la_regla_7(self):
        rng = np.random.default_rng(3)
        claro = np.clip(np.rint(215.0 + rng.normal(0, 1.5, (2700, 2700, 3))), 0, 255).astype(np.uint8)
        ref = _medir_virgen(gen.codificar(claro, "tiff", 600))
        assert ref.estado.startswith("no válida: ") and _resultados(ref)["rango"] == "rechazo"
        assert "tan clara como el fondo del escáner" in next(p.texto for p in ref.pruebas if p.nombre == "rango" and p.resultado == "rechazo")

    def test_g_otro_lote_con_el_azul_en_60_se_rechaza_por_rango_y_el_testigo_lo_nota(self):
        img = _virgen_arreglo("A", calib_extra={"virgen_bgr": (60.0, 174.0, 105.5), "meseta_bgr": (60.0, 174.0, 105.5)})
        ref = _medir_virgen(gen.codificar(img, "tiff", 600))
        assert ref.estado.startswith("no válida: ") and _resultados(ref)["rango"] == "rechazo" and _resultados(ref)["azul testigo"] == "aviso"
        assert "azul 60 fuera de [65, 130]" in next(p.texto for p in ref.pruebas if p.nombre == "rango")
        sano = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"virgen_bgr": (90.0, 174.0, 105.5), "meseta_bgr": (90.0, 174.0, 105.5)}), "tiff", 600))
        assert sano.estado == "ok" and _resultados(sano)["azul testigo"] == "ok", "90 esta dentro del testigo [75, 95]"
        fuera = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"virgen_bgr": (100.0, 174.0, 105.5), "meseta_bgr": (100.0, 174.0, 105.5)}), "tiff", 600))
        assert fuera.estado == "ok" and _resultados(fuera)["azul testigo"] == "aviso", "100 esta dentro del rango de la virgen pero fuera del testigo"

    def test_g_el_ruido_alto_avisa(self):
        ref = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"ruido": 4.5}), "tiff", 600))
        assert ref.estado == "ok" and _resultados(ref)["C7 ruido"] == "aviso", _resultados(ref)
        assert _resultados(_base()[0])["C7 ruido"] == "ok"

    def test_g_un_rayon_claro_avisa_y_sus_pixeles_se_apartan_del_piso(self):
        img = _virgen_arreglo("A")
        sin_rayon = _base()[0]
        h, w = img.shape[:2]
        img[h // 2 - 400:h // 2 + 400, w // 2:w // 2 + 7] = 200                    # 0.3 mm de ancho y 34 mm de largo
        ref = _medir_virgen(gen.codificar(img, "tiff", 600))
        assert ref.estado == "ok" and _resultados(ref)["C6 motas"] == "aviso", _resultados(ref)
        perdidos = sin_rayon.capas["G"].n - ref.capas["G"].n
        assert perdidos >= 0.9 * (800 * 7), f"solo se apartaron {perdidos} pixeles del rayon de {800 * 7}"
        assert all(abs(ref.valor(c) - sin_rayon.valor(c)) <= 0.6 for c in CAPAS)
        # y se aparta tambien 0.5 mm alrededor (un disco de 12 pixeles): el rayon de 7 x 800 pixeles ocupa 5600 y con su halo 25420 (7 x 800 + 2 x (7 + 800) x 12 + el disco de las puntas)
        radio = round(0.5 / ESC)
        con_halo = 7 * 800 + 2 * (7 + 800) * radio + math.pi * radio ** 2
        assert 0.97 * con_halo <= perdidos <= 1.03 * con_halo, f"se apartaron {perdidos} pixeles y con el halo de 0.5 mm son {con_halo:.0f}"
        mas = _medir_virgen(gen.codificar(img, "tiff", 600), P=_P(dilatacion_tinta_y_motas_mm=1.0))
        radio_mayor = round(1.0 / ESC)
        con_halo_mayor = 7 * 800 + 2 * (7 + 800) * radio_mayor + math.pi * radio_mayor ** 2
        assert 0.97 * con_halo_mayor <= sin_rayon.capas["G"].n - mas.capas["G"].n <= 1.03 * con_halo_mayor, "la dilatacion es el parametro `dilatacion_tinta_y_motas_mm`"

    def test_g_un_gradiente_de_2_por_ciento_por_10_cm_avisa_y_no_es_una_raya(self):
        img = _virgen_arreglo("A").astype(np.float32)
        w = img.shape[1]
        img[:, :, 1] += ((np.arange(w)[None, :] - w / 2) * ESC / 100.0 * 0.02 * 174.0)
        ref = _medir_virgen(gen.codificar(np.clip(np.rint(img), 0, 255).astype(np.uint8), "tiff", 600))
        assert ref.estado == "ok" and _resultados(ref)["C5 gradiente"] == "aviso" and _resultados(ref)["C7 rayas"] == "ok", _resultados(ref)
        assert "verde" in next(p.texto for p in ref.pruebas if p.nombre == "C5 gradiente")

    def test_g_unas_bandas_verticales_de_2_niveles_avisan_por_rayas(self):
        """Franjas verticales de 0.85 mm (20 columnas) que alternan +2 y -2 niveles: lo que dejaria un elemento del CIS defectuoso. La amplitud de las medias por columna (menos la media movil
        de 2 mm) es de 2 niveles, el doble del umbral."""
        img = _virgen_arreglo("A").astype(np.int16)
        img += (2 * np.where((np.arange(img.shape[1]) // 20) % 2 == 0, 1, -1))[None, :, None]
        ref = _medir_virgen(gen.codificar(np.clip(img, 0, 255).astype(np.uint8), "tiff", 600))
        assert _resultados(ref)["C7 rayas"] == "aviso" and ref.estado == "ok", _resultados(ref)
        assert "columnas" in next(p.texto for p in ref.pruebas if p.nombre == "C7 rayas")

    def test_g_una_pelicula_sucia_o_rayada_avisa_y_no_se_rechaza(self):
        """400 motas de 7 x 7 pixeles (0.3 mm, +60 niveles) al azar: con el halo de 0.5 mm cubren el 4.6 % de la zona medida. OD.1 (DA-87): las motas AVISAN y se apartan del piso (antes el 2 % rechazaba: una
        pieza de 10 x 10 cm de una pelicula sin tocar tiene motas en el 2.14 % de su zona); 40 motas (0.5 %) tambien avisan."""
        rng = np.random.default_rng(5)
        resultados = {}
        for n in (40, 400):
            img = _virgen_arreglo("A").astype(np.int16)
            alto, ancho = img.shape[:2]
            for y, x in zip(rng.integers(100, alto - 100, n), rng.integers(100, ancho - 100, n)):
                img[y:y + 7, x:x + 7, :] += 60
            resultados[n] = _medir_virgen(gen.codificar(np.clip(img, 0, 255).astype(np.uint8), "tiff", 600))
        sucia, poca = resultados[400], resultados[40]
        assert sucia.estado == "ok" and _resultados(sucia)["C6 motas"] == "aviso", _resultados(sucia)
        assert "se apartan del piso" in next(p.texto for p in sucia.pruebas if p.nombre == "C6 motas") and not [p for p in sucia.pruebas if p.resultado == "rechazo"]
        assert all(sucia.valor(c) is not None for c in CAPAS) and sucia.region is not None, "una pelicula con motas se mide: las motas se apartan del piso y no la rechazan"
        assert sucia.capas["G"].n < poca.capas["G"].n, "con mas motas se apartan mas pixeles"
        assert poca.estado == "ok" and _resultados(poca)["C6 motas"] == "aviso", (poca.estado, _resultados(poca))

    def test_g_los_pixeles_sueltos_y_los_pares_no_son_motas_y_los_grupos_de_tres_si(self):
        """600 grupos de 1, de 2 y de 3 pixeles claros (+60) en una cuadricula: un pixel o dos son ruido del sensor (la mota minima es `motas_pixeles_grupo` = 3 pixeles) y no se apartan ni
        avisan; con tres, los mismos 600 grupos cubren el 4.6 % de la zona (con su halo): avisan y se apartan del piso (OD.1: ya no rechazan)."""
        paso = 60
        base = _virgen_arreglo("A")
        alto, ancho = base.shape[:2]
        celdas = [(y, x) for y in range(150, alto - 150, paso) for x in range(150, ancho - 150, paso)]
        elegidas = np.random.default_rng(7).permutation(len(celdas))[:600]
        sin_motas = _base()[0]
        for tam, avisa in ((1, False), (2, False), (3, True)):
            img = base.astype(np.int16)
            for k in elegidas:
                y, x = celdas[k]
                img[y, x:x + tam, :] += 60
            ref = _medir_virgen(gen.codificar(np.clip(img, 0, 255).astype(np.uint8), "tiff", 600))
            if avisa:
                assert ref.estado == "ok" and _resultados(ref)["C6 motas"] == "aviso" and ref.capas["G"].n < sin_motas.capas["G"].n, (tam, _resultados(ref))      # OD.1: las motas avisan y se apartan
            else:
                assert ref.estado == "ok" and _resultados(ref)["C6 motas"] == "ok", (tam, _resultados(ref))
                assert ref.capas["G"].n == sin_motas.capas["G"].n, "los pixeles sueltos no se apartan del piso"

    def test_g_el_ruido_es_el_de_cada_pixel_contra_sus_vecinos_y_no_la_variacion_lenta_de_la_pelicula(self):
        """Una rampa suave de ±5 niveles en el verde (3.6 % en 14 cm, 0.002 niveles por pixel) no es ruido: el ruido es lo que cada pixel se aparta de la media de su vecindad de 0.5 mm. La
        desviacion del plano entero, que la rampa sube a mas de 3, avisaria de un ruido que no hay."""
        img = _virgen_arreglo("A").astype(np.float32)
        ancho = img.shape[1]
        img[:, :, 1] += (np.arange(ancho)[None, :] / ancho - 0.5) * 10.0
        ref = _medir_virgen(gen.codificar(np.clip(np.rint(img), 0, 255).astype(np.uint8), "tiff", 600))
        assert ref.estado == "ok" and _resultados(ref)["C5 gradiente"] == "aviso", _resultados(ref)
        assert _resultados(ref)["C7 ruido"] == "ok", "la rampa lenta no es ruido"
        sigma_verde = float(next(p.texto for p in ref.pruebas if p.nombre == "C7 ruido").split("verde ")[1].split(",")[0])
        assert 1.2 <= sigma_verde <= 1.8, sigma_verde

    def test_g_la_media_de_un_bloque_es_la_recortada_y_un_parche_de_pixeles_sueltos_no_la_mueve(self):
        """Un parche de 4 x 4 bloques con un pixel de cada tres (11 % de los pixeles) +60 niveles: aislados no son motas. La media de cada bloque de la uniformidad es la RECORTADA (descarta lo que
        esta a mas de 3 sigmas robustas de la mediana): no se mueve y la uniformidad entre bloques sigue «ok»; con la media simple cada bloque del parche subiria 6.7 niveles (3.8 % del verde,
        6.3 % del rojo) y la uniformidad avisaria o rechazaria."""
        lado = int(round(5.0 / ESC))
        img = _virgen_arreglo("A").astype(np.int16)
        img[700:700 + 4 * lado:3, 700:700 + 4 * lado:3, :] += 60
        ref = _medir_virgen(gen.codificar(np.clip(img, 0, 255).astype(np.uint8), "tiff", 600))
        assert ref.estado == "ok" and _resultados(ref)["C5 uniformidad"] == "ok" and _resultados(ref)["C6 motas"] == "ok", _resultados(ref)

    def test_g_el_gradiente_solo_se_juzga_donde_la_zona_mide_60_mm_o_mas(self):
        """Una rampa de 3 % por 10 cm en el verde, a lo ancho de una pelicula de 55 mm de ancho (la zona medida mide 50 mm en esa direccion, menos de 60): no se juzga. La misma rampa en una
        pelicula de 101 mm (97 mm de zona) si avisa: el control. Y la extension minima es un parametro."""
        datos = {}
        for ancho_mm in (55.0, 101.0):
            ancho_px = int(round(ancho_mm / ESC))
            base = _virgen_arreglo("A")
            img = np.full_like(base, 255).astype(np.float32)
            img[:, :ancho_px, :] = base[:, :ancho_px, :]
            img[:, :ancho_px, 1] += (np.arange(ancho_px) * ESC / 100.0 * 0.03 * 174.0)[None, :]
            datos[ancho_mm] = gen.codificar(np.clip(np.rint(img), 0, 255).astype(np.uint8), "tiff", 600)
        angosta, ancha = _medir_virgen(datos[55.0]), _medir_virgen(datos[101.0])
        assert angosta.estado == "ok" and _resultados(angosta)["C5 gradiente"] == "ok", _resultados(angosta)
        assert "extensión 50 ×" in next(p.texto for p in angosta.pruebas if p.nombre == "C5 gradiente")
        assert ancha.estado == "ok" and _resultados(ancha)["C5 gradiente"] == "aviso", _resultados(ancha)
        corta = _medir_virgen(datos[55.0], P=_P(extension_minima_gradiente_mm=20.0))
        assert _resultados(corta)["C5 gradiente"] == "aviso", "la extension minima es el parametro `extension_minima_gradiente_mm`"

    def test_g_el_borde_de_la_imagen_tambien_se_aparta_en_la_virgen(self):
        """Una virgen recortada a ras (la pelicula llena la imagen): la zona medida queda a 2 mm del borde de la imagen, donde el fleco del corte ya no llega; con un margen mayor, mas adentro."""
        ref, datos = _base()
        alto, ancho = ref.procedencia["forma"]
        x0, y0, x1, y1 = ref.region["caja"]
        margen = 2.0 / ESC
        assert min(x0, y0, ancho - x1, alto - y1) >= margen - 1.0, (ref.region["caja"], margen)
        mas = _medir_virgen(datos, P=_P(margen_borde_virgen_mm=5.0))
        x0b, y0b, x1b, y1b = mas.region["caja"]
        assert min(x0b, y0b, ancho - x1b, alto - y1b) >= 5.0 / ESC - 1.0 > margen

    def test_g_el_valor_de_la_virgen_es_la_mediana_de_la_zona_y_no_su_media(self):
        """Los mismos pixeles claros aislados de arriba (6 % de la zona, +60): la media subiria 3.8 niveles, la mediana 0.1. El valor que se guarda es la mediana (diseño V6)."""
        base = _base()[0]
        img = _virgen_arreglo("A").astype(np.int16)
        img[::4, ::4, :] += 60
        ref = _medir_virgen(gen.codificar(np.clip(img, 0, 255).astype(np.uint8), "tiff", 600))
        assert ref.estado == "ok"
        zona = np.array(img[ref.region["caja"][1]:ref.region["caja"][3], ref.region["caja"][0]:ref.region["caja"][2], 1], np.float64)
        assert zona.mean() - np.median(zona) > 3.0, "la prueba tiene que discriminar entre la media y la mediana"
        assert abs(ref.valor("G") - base.valor("G")) <= 0.6 and ref.valor("G") < zona.mean() - 3.0

    def test_g_el_ancho_de_los_bloques_y_su_minimo_se_usan(self):
        datos = _base()[1]
        pocos = _medir_virgen(datos, P=_P(bloques_minimos_virgen=10 ** 6))
        assert pocos.estado.startswith("no válida: ") and _resultados(pocos)["C5 uniformidad"] == "rechazo"

    def test_g_el_resultado_nunca_lanza_por_el_contenido(self):
        for malo in (b"", b"no es una imagen", b"\xff\xd8\xff\xe0" + bytes(50)):
            ref = _medir_virgen(malo)
            assert ref.estado.startswith("no válida: ") and ref.region is None and all(ref.valor(c) is None for c in CAPAS)
        with pytest.raises(ValueError, match="resolucion_escaneo_dpi"):
            _pel().piso_de_pelicula_virgen(_base()[1], {}, "x.tif")


# ====================================================================================================================== (h) la persistencia

def _otra_virgen():
    """Una segunda referencia, con otra huella: el mismo lote en 16 bits."""
    if "otra" not in _CACHE_VIRGEN:
        datos = gen.codificar(_virgen_arreglo("A", bits=16), "tiff", 600)
        _CACHE_VIRGEN["otra"] = (_medir_virgen(datos, nombre="virgen_16.tif"), datos)
    return _CACHE_VIRGEN["otra"]


# A3-M2 (14-10; decision de Opus vetable por el fisico, borradores/A3/decision_rv_a3_2.md; hallazgo RV-A3-2 de la revision de la ronda 1): guardar la referencia virgen archiva la anterior SIEMPRE
# QUE CAMBIE SU CONTENIDO, tambien con la MISMA huella sha256: la misma pelicula con otro usuario, otra fecha de calculo, otra orientacion declarada, otros parametros u otro instante de guardado
# es otra version, y lo que se perdia sin rastro era justo quien fijo la referencia y cuando. Solo un guardado IDENTICO, byte a byte, a lo que se va a escribir no archiva (un duplicado exacto no
# guarda nada que no este ya). Antes (la regla de «otra huella» del diseño §4.2) el segundo guardado del mismo escaneo pisaba el JSON y la carpeta de anteriores ni se creaba.
# Lo que cambia entre el primer guardado y el segundo, del MISMO escaneo: cada caso es un dato distinto de los que el JSON guarda.
USUARIO_DEL_PRIMER_GUARDADO = "lamaya"
CAMBIOS_EN_EL_MISMO_ESCANEO = {
    "otro_usuario": {"usuario": "otro_fisico"},
    "otra_fecha_de_calculo": {"fecha_calculo": "2026-10-14"},
    "otra_orientacion_declarada": {"orientacion_declarada": "girada"},
    "otros_parametros_de_la_medicion": {"margen_borde_virgen_mm": 3.0},
    "otro_instante_de_guardado": {"instante": "2031-02-04 00:00:00"},
}


def _medir_otra_vez_el_mismo_escaneo(datos, fecha_calculo=FECHA, orientacion_declarada=None, **parametros):
    """El MISMO escaneo (la misma huella sha256) medido otra vez con la funcion de produccion: solo cambia lo que se pida (la fecha de calculo, la orientacion declarada o un parametro de la medicion)."""
    return _pel().piso_de_pelicula_virgen(datos, _P(**parametros), "virgen_lote.tif", fecha_calculo=fecha_calculo, orientacion_declarada=orientacion_declarada)


def _los_archivados(tmp_path):
    """{nombre: bytes} de lo que hay en la carpeta de anteriores ({} si ni siquiera existe)."""
    anteriores = tmp_path / _pel().CARPETA_REFERENCIAS_VIRGEN_ANTERIORES
    return {p.name: p.read_bytes() for p in anteriores.iterdir()} if anteriores.is_dir() else {}


class TestLaReferenciaVirgenSeGuardaJuntoALaBase:
    def test_h_guardar_y_leer_devuelve_la_misma_referencia_campo_por_campo(self, tmp_path):
        pel = _pel()
        ref, datos = _base()
        ruta = pel.guardar_referencia_virgen(ref, str(tmp_path), datos=datos, usuario="lamaya")
        assert Path(ruta) == tmp_path / pel.ARCHIVO_REFERENCIA_VIRGEN == tmp_path / "piso_pelicula_virgen.json"
        contenido = json.loads(Path(ruta).read_text(encoding="utf-8"))
        assert set(contenido) == {"version", "referencia", "guardada_por", "guardada_el"} and contenido["version"] == "PV-2" and contenido["guardada_por"] == "lamaya"
        assert len(contenido["guardada_el"]) == 19 and contenido["guardada_el"][4] == "-" and contenido["guardada_el"][10] == "T"
        assert contenido["referencia"] == ref.como_dict()
        leida = pel.leer_referencia_virgen(str(tmp_path))
        assert leida.como_dict() == ref.como_dict() and leida.estado == "ok"
        assert {c: leida.valor(c) for c in CAPAS} == _valores(ref) and leida.procedencia == ref.procedencia
        copia = tmp_path / pel.CARPETA_ESCANEOS_VIRGEN / (ref.procedencia["sha256"] + ".tif")
        assert copia.read_bytes() == datos, "el escaneo se copia con su huella por nombre"

    def test_h_no_hay_archivo_no_hay_referencia(self, tmp_path):
        assert _pel().leer_referencia_virgen(str(tmp_path)) is None

    def test_h_una_segunda_referencia_archiva_la_primera_y_nada_se_borra(self, tmp_path):
        pel = _pel()
        a, datos_a = _base()
        b, datos_b = _otra_virgen()
        ruta = pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a)
        primero = Path(ruta).read_bytes()
        pel.guardar_referencia_virgen(b, str(tmp_path), datos=datos_b)
        anteriores = tmp_path / pel.CARPETA_REFERENCIAS_VIRGEN_ANTERIORES
        nombre_a = f"{FECHA}_{a.procedencia['sha256'][:8]}.json"
        assert sorted(p.name for p in anteriores.iterdir()) == [nombre_a] and (anteriores / nombre_a).read_bytes() == primero, "la anterior se archiva igual, con su nombre fecha_huella"
        assert pel.leer_referencia_virgen(str(tmp_path)).procedencia["sha256"] == b.procedencia["sha256"]
        assert sorted(p.name for p in (tmp_path / pel.CARPETA_ESCANEOS_VIRGEN).iterdir()) == sorted([a.procedencia["sha256"] + ".tif", b.procedencia["sha256"] + ".tif"])
        # volver a la primera archiva la segunda; y volver a la segunda archiva OTRA VEZ la primera: el nombre ya existe, no se sobrescribe
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a)
        pel.guardar_referencia_virgen(b, str(tmp_path), datos=datos_b)
        nombres = sorted(p.name for p in anteriores.iterdir())
        nombre_b = f"{FECHA}_{b.procedencia['sha256'][:8]}.json"
        assert nombres == sorted([nombre_a, nombre_a.replace(".json", "_2.json"), nombre_b]), nombres
        for n in (nombre_a, nombre_a.replace(".json", "_2.json")):
            assert json.loads((anteriores / n).read_text(encoding="utf-8"))["referencia"] == a.como_dict()

    # `test_h_guardar_la_misma_referencia_otra_vez_no_archiva_nada` (la condicion era «la misma huella sha256») se reescribio el 14-10 en estas dos pruebas (A3-M2, RV-A3-2): «la misma referencia»
    # era ambiguo, y era justo lo que pisaba, sin rastro, quien fijo la referencia y cuando.
    def test_h_guardar_exactamente_lo_mismo_otra_vez_no_archiva_nada(self, tmp_path, reloj_fijo):
        """(1 de A3-M2) Con el reloj congelado, guardar la MISMA referencia, por el MISMO usuario, otra vez escribe EXACTAMENTE los mismos bytes: archivar un duplicado exacto no guarda nada que no
        este ya (el caso real: dos clics seguidos en «Guardar»). La condicion para no archivar ya no es «la misma huella» sino «los mismos bytes»."""
        pel = _pel()
        a, datos_a = _base()
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a, usuario=USUARIO_DEL_PRIMER_GUARDADO))
        primero = ruta.read_bytes()
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a, usuario=USUARIO_DEL_PRIMER_GUARDADO)
        assert _los_archivados(tmp_path) == {}, "se archivo un duplicado exacto: no guarda nada que no este ya"
        assert ruta.read_bytes() == primero, "el control: el segundo guardado escribio EXACTAMENTE los mismos bytes (el reloj esta congelado)"
        assert pel.leer_referencia_virgen(str(tmp_path)).como_dict() == a.como_dict()

    @pytest.mark.parametrize("cambia", list(CAMBIOS_EN_EL_MISMO_ESCANEO.values()), ids=list(CAMBIOS_EN_EL_MISMO_ESCANEO))
    def test_h_guardar_el_mismo_escaneo_con_otros_datos_archiva_la_anterior_con_sus_bytes_intactos(self, tmp_path, reloj_fijo, monkeypatch, cambia):
        """(2 de A3-M2) La MISMA pelicula (la misma huella sha256) guardada otra vez con otro usuario, otra fecha de calculo, otra orientacion declarada, otros parametros u otro instante de
        guardado: la anterior se archiva con sus bytes intactos (con el nombre de siempre, el de la ANTERIOR: `<fecha_calculo>_<sha8>.json`), el JSON vivo es el nuevo y el escaneo, que es el
        mismo, se copia una sola vez. Antes la carpeta de anteriores ni se creaba y se perdian `guardada_por`, `guardada_el`, `fecha_calculo`, `orientacion_declarada` y los parametros de la primera."""
        pel = _pel()
        a, datos = _base()
        b = _medir_otra_vez_el_mismo_escaneo(datos, **{k: v for k, v in cambia.items() if k not in ("usuario", "instante")})
        # el control: es el MISMO escaneo (la misma huella) y la segunda medicion es valida; si no, se compararian dos peliculas distintas y la prueba pasaria por la razon equivocada
        assert b.estado == "ok" and b.procedencia["sha256"] == a.procedencia["sha256"], (b.estado, b.procedencia["sha256"], a.procedencia["sha256"])
        if "margen_borde_virgen_mm" in cambia:
            assert b.parametros["margen_borde_virgen_mm"] == 3.0 != a.parametros["margen_borde_virgen_mm"], "el control: se midio con otro parametro"
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario=USUARIO_DEL_PRIMER_GUARDADO))
        primero = ruta.read_bytes()
        if "instante" in cambia:
            monkeypatch.setattr(pel, "time", _RelojFijo(cambia["instante"]))
        usuario_b = cambia.get("usuario", USUARIO_DEL_PRIMER_GUARDADO)
        pel.guardar_referencia_virgen(b, str(tmp_path), datos=datos, usuario=usuario_b)
        nombre = f"{FECHA}_{a.procedencia['sha256'][:8]}.json"
        archivados = _los_archivados(tmp_path)
        assert archivados, "la anterior no se archivo (la carpeta de anteriores ni se creo): se perdieron, sin rastro, quien fijo la referencia y cuando"
        assert list(archivados) == [nombre], "la anterior se archiva con el nombre de siempre, el de LA ANTERIOR (fecha de calculo y huella)"
        assert archivados[nombre] == primero, "se archiva tal cual, byte por byte"
        vivo = ruta.read_bytes()
        assert vivo != primero, "el control: el segundo guardado escribio otro contenido"
        contenido = json.loads(vivo.decode("utf-8"))
        assert contenido["guardada_por"] == usuario_b and contenido["referencia"] == b.como_dict(), "el JSON vivo es el nuevo"
        assert pel.leer_referencia_virgen(str(tmp_path)).como_dict() == b.como_dict()
        assert sorted(p.name for p in (tmp_path / pel.CARPETA_ESCANEOS_VIRGEN).iterdir()) == [a.procedencia["sha256"] + ".tif"], "el escaneo es el mismo: se copia una sola vez"

    def test_h_una_referencia_no_valida_no_se_guarda(self, tmp_path):
        malo = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 300))
        with pytest.raises(ValueError):
            _pel().guardar_referencia_virgen(malo, str(tmp_path))
        assert list(tmp_path.iterdir()) == []

    def test_h_unos_datos_que_no_son_los_de_la_referencia_se_rechazan(self, tmp_path):
        with pytest.raises(ValueError):
            _pel().guardar_referencia_virgen(_base()[0], str(tmp_path), datos=_otra_virgen()[1])

    def test_h_un_json_danado_o_de_otra_version_se_rechaza_con_su_motivo(self, tmp_path):
        pel = _pel()
        a, datos = _base()
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path)))
        ruta.write_text("{ esto no es json", encoding="utf-8")
        with pytest.raises(ValueError):
            pel.leer_referencia_virgen(str(tmp_path))
        bueno = {"version": "PV-2", "referencia": a.como_dict(), "guardada_por": None, "guardada_el": "2026-10-13T10:00:00"}
        for cambio in ({"version": "PV-9"}, {"referencia": {**a.como_dict(), "version": "PV-9"}}, {"referencia": {k: v for k, v in a.como_dict().items() if k != "capas"}}):
            ruta.write_text(json.dumps({**bueno, **cambio}), encoding="utf-8")
            with pytest.raises(ValueError):
                pel.leer_referencia_virgen(str(tmp_path))
        ruta.write_text(json.dumps(bueno), encoding="utf-8")
        assert pel.leer_referencia_virgen(str(tmp_path)).como_dict() == a.como_dict()

    @pytest.mark.parametrize("que_falla", ["el_json", "la_copia_del_escaneo"])
    def test_h_la_escritura_es_atomica_un_fallo_deja_la_referencia_anterior_intacta(self, tmp_path, monkeypatch, que_falla):
        """El reemplazo (`os.replace`) falla SOLO para un destino: el JSON de la referencia, o la copia del escaneo (que se hace antes). En los dos casos la referencia anterior queda intacta,
        se puede leer, y no queda ningun temporal; escribir directo sobre el destino (sin temporal) dejaria el JSON a medias o borrado."""
        pel = _pel()
        a, datos_a = _base()
        b, datos_b = _otra_virgen()
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a))
        antes = ruta.read_bytes()
        real = os.replace

        def falla(origen, destino):
            es_el_json = Path(destino).name == pel.ARCHIVO_REFERENCIA_VIRGEN
            if es_el_json == (que_falla == "el_json"):
                raise OSError("disco lleno (simulado)")
            return real(origen, destino)

        monkeypatch.setattr(os, "replace", falla)
        with pytest.raises(OSError):
            pel.guardar_referencia_virgen(b, str(tmp_path), datos=datos_b)
        monkeypatch.undo()
        assert ruta.is_file() and ruta.read_bytes() == antes, "el JSON anterior cambio tras un fallo"
        assert pel.leer_referencia_virgen(str(tmp_path)).procedencia["sha256"] == a.procedencia["sha256"]
        assert not [p for p in tmp_path.rglob("*") if ".tmp" in p.name], "quedo un temporal"
        if que_falla == "el_json":
            assert b.procedencia["sha256"] + ".tif" in {p.name for p in (tmp_path / pel.CARPETA_ESCANEOS_VIRGEN).iterdir()}, "la copia del escaneo, hecha antes, se conserva: nada se borra"

    def test_h_la_referencia_desde_su_diccionario_es_la_inversa_de_como_dict(self):
        a = _base()[0]
        d = a.como_dict()
        assert json.loads(json.dumps(d)) == d and d["version"] == "PV-2" and d["estado"] == "ok"
        assert _pel().referencia_virgen_desde_dict(d).como_dict() == d
        for malo in ({**d, "version": "PV-9"}, {k: v for k, v in d.items() if k != "procedencia"}, {k: v for k, v in d.items() if k != "estado"}, "no es un diccionario"):
            with pytest.raises(ValueError):
                _pel().referencia_virgen_desde_dict(malo)


# ---------------------------------------------------------------------------------------------------------------------- (h) frente a lo ALTERADO y a lo DAÑADO
# Ronda 1 de la revision de A.3 (13-10). RV-A3-1: tres ramas de proteccion de la persistencia (un JSON anterior que no se puede leer, la clave `referencia` que falta, un escaneo ya copiado con
# otro contenido) y varias mas del mismo tipo no tenian ninguna prueba: una mutacion plausible de cada una sobrevivia a todas. RV-A3-3: `referencia_virgen_desde_dict` validaba la FORMA (las
# claves) y no los TIPOS: un valor `null` o de texto pasaba la lectura y reventaba despues, lejos de donde se leyo, con otra excepcion que `ValueError`.

# Lo que `_archivar_la_anterior` no sabe nombrar con la fecha y la huella: se archiva igual, byte por byte, con un nombre propio (cada forma lanza una de las TRES excepciones que atrapa).
_JSON_ANTERIOR_QUE_NO_SE_PUEDE_LEER = {
    "bytes_que_no_son_json": b"{ esto no es json \xff\xfe",                       # UnicodeDecodeError (un ValueError)
    "vacio": b"",                                                                # JSONDecodeError (un ValueError)
    "una_lista": b"[1, 2, 3]",                                                   # TypeError
    "un_texto": b'"solo un texto"',                                              # TypeError
    "sin_la_referencia": b'{"version": "PV-2"}',                                 # KeyError
    "la_referencia_es_un_texto": b'{"version": "PV-2", "referencia": "x"}',      # TypeError
    "sin_procedencia": b'{"version": "PV-2", "referencia": {}}',                 # KeyError
    "procedencia_nula": b'{"version": "PV-2", "referencia": {"procedencia": null}}',          # TypeError
    "sin_huella": b'{"version": "PV-2", "referencia": {"procedencia": {"fecha_calculo": "2026-10-13"}}}',         # KeyError
    "sin_fecha": b'{"version": "PV-2", "referencia": {"procedencia": {"sha256": "' + b"ab" * 32 + b'"}}}',      # KeyError
}


def _contenido_que_no_es_una_referencia(caso, a):
    """El texto de un `piso_pelicula_virgen.json` que `leer_referencia_virgen` debe rechazar con `ValueError`: no es un diccionario, le falta la version o la referencia, o es de otra version."""
    d = a.como_dict()
    return {"vacio": "", "una_lista": "[]", "un_texto": '"texto"', "un_numero": "5", "nulo": "null", "verdadero": "true", "objeto_vacio": "{}",
            "solo_la_version": '{"version": "PV-2"}',
            "referencia_nula": '{"version": "PV-2", "referencia": null}',
            "referencia_lista": '{"version": "PV-2", "referencia": []}',
            "sin_version_arriba": json.dumps({"referencia": d}),
            "otra_version_dentro": json.dumps({"version": "PV-2", "referencia": {**d, "version": "PV-9"}})}[caso]


CASOS_DE_JSON_QUE_NO_ES_UNA_REFERENCIA = ["vacio", "una_lista", "un_texto", "un_numero", "nulo", "verdadero", "objeto_vacio", "solo_la_version", "referencia_nula", "referencia_lista",
                                          "sin_version_arriba", "otra_version_dentro"]


class TestLaPersistenciaFrenteALoAlteradoYLoDanado:
    @pytest.mark.parametrize("contenido", list(_JSON_ANTERIOR_QUE_NO_SE_PUEDE_LEER.values()), ids=list(_JSON_ANTERIOR_QUE_NO_SE_PUEDE_LEER))
    def test_h_un_json_anterior_que_no_se_puede_leer_se_archiva_con_nombre_propio_y_no_se_pierde(self, tmp_path, reloj_fijo, contenido):
        pel = _pel()
        a, datos_a = _base()
        (tmp_path / pel.ARCHIVO_REFERENCIA_VIRGEN).write_bytes(contenido)
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a, usuario="lamaya")
        anteriores = tmp_path / pel.CARPETA_REFERENCIAS_VIRGEN_ANTERIORES
        assert [p.name for p in anteriores.iterdir()] == ["ilegible_20310203T235959.json"], "el JSON que no se puede leer se archiva con un nombre propio (ilegible_<instante>)"
        assert (anteriores / "ilegible_20310203T235959.json").read_bytes() == contenido, "se archiva tal cual, byte por byte: nada se pierde"
        assert pel.leer_referencia_virgen(str(tmp_path)).como_dict() == a.como_dict(), "y la referencia nueva queda vigente y se lee"

    def test_h_dos_anteriores_ilegibles_se_archivan_los_dos_sin_pisarse(self, tmp_path, reloj_fijo):
        pel = _pel()
        a, datos_a = _base()
        b, datos_b = _otra_virgen()
        ruta = tmp_path / pel.ARCHIVO_REFERENCIA_VIRGEN
        ruta.write_bytes(b"primera basura")
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a)
        ruta.write_bytes(b"segunda basura")                        # el JSON vigente se daña a mano; el reloj sigue en el mismo segundo: el nombre se repite
        pel.guardar_referencia_virgen(b, str(tmp_path), datos=datos_b)
        anteriores = tmp_path / pel.CARPETA_REFERENCIAS_VIRGEN_ANTERIORES
        assert {p.name: p.read_bytes() for p in anteriores.iterdir()} == {"ilegible_20310203T235959.json": b"primera basura", "ilegible_20310203T235959_2.json": b"segunda basura"}

    @pytest.mark.parametrize("como", ["un_bit", "truncado", "vacio", "mas_largo"])
    def test_h_un_escaneo_ya_copiado_con_otro_contenido_se_rechaza_y_no_se_toca_nada(self, tmp_path, como):
        pel = _pel()
        a, datos_a = _base()
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a))
        copia = tmp_path / pel.CARPETA_ESCANEOS_VIRGEN / (a.procedencia["sha256"] + ".tif")
        alterado = {"un_bit": datos_a[:-1] + bytes([datos_a[-1] ^ 1]), "truncado": datos_a[:len(datos_a) // 2], "vacio": b"", "mas_largo": datos_a + b"\0"}[como]
        copia.write_bytes(alterado)
        json_antes = ruta.read_bytes()
        with pytest.raises(ValueError, match="otro contenido"):
            pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a)
        assert copia.read_bytes() == alterado, "no se sobrescribe lo que haya en la carpeta de escaneos"
        assert ruta.read_bytes() == json_antes and not (tmp_path / pel.CARPETA_REFERENCIAS_VIRGEN_ANTERIORES).exists()

    def test_h_si_el_escaneo_de_la_nueva_esta_alterado_la_vigente_no_se_archiva_ni_se_cambia(self, tmp_path):
        """El orden importa: la copia del escaneo (que puede fallar) va ANTES de archivar y de escribir el JSON; si no, un fallo dejaria una copia archivada de la vigente que sigue vigente."""
        pel = _pel()
        a, datos_a = _base()
        b, datos_b = _otra_virgen()
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a))
        json_antes = ruta.read_bytes()
        (tmp_path / pel.CARPETA_ESCANEOS_VIRGEN / (b.procedencia["sha256"] + ".tif")).write_bytes(b"alterado")
        with pytest.raises(ValueError, match="otro contenido"):
            pel.guardar_referencia_virgen(b, str(tmp_path), datos=datos_b)
        assert ruta.read_bytes() == json_antes and pel.leer_referencia_virgen(str(tmp_path)).procedencia["sha256"] == a.procedencia["sha256"]
        assert not (tmp_path / pel.CARPETA_REFERENCIAS_VIRGEN_ANTERIORES).exists(), "no se archivo la vigente: sigue siendo la vigente"

    def test_h_un_escaneo_ya_copiado_con_el_mismo_contenido_no_se_vuelve_a_escribir(self, tmp_path):
        pel = _pel()
        a, datos_a = _base()
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a)
        copia = tmp_path / pel.CARPETA_ESCANEOS_VIRGEN / (a.procedencia["sha256"] + ".tif")
        os.utime(copia, (1_000_000_000, 1_000_000_000))
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos_a)
        assert copia.stat().st_mtime == 1_000_000_000 and copia.read_bytes() == datos_a, "el escaneo igual que ya esta copiado se deja tal cual (ni se reemplaza ni se toca)"

    @pytest.mark.parametrize("no_es", [None, {}, "texto", 5, "referencia"], ids=["nulo", "diccionario_vacio", "texto", "numero", "el_diccionario_de_una_referencia"])
    def test_h_lo_que_se_guarda_debe_ser_una_ReferenciaVirgen(self, tmp_path, no_es):
        no_es = _base()[0].como_dict() if no_es == "referencia" else no_es
        with pytest.raises(ValueError, match="ReferenciaVirgen"):
            _pel().guardar_referencia_virgen(no_es, str(tmp_path))
        assert list(tmp_path.iterdir()) == []

    def test_h_la_carpeta_se_crea_si_no_existe(self, tmp_path):
        pel = _pel()
        a = _base()[0]
        carpeta = tmp_path / "base" / "de" / "datos"
        ruta = pel.guardar_referencia_virgen(a, str(carpeta))
        assert Path(ruta) == carpeta / pel.ARCHIVO_REFERENCIA_VIRGEN and pel.leer_referencia_virgen(str(carpeta)).como_dict() == a.como_dict()

    @pytest.mark.parametrize("archivo,formato,esperada", [
        ("virgen.TIF", "TIFF", ".tif"), ("virgen.tiff", "TIFF", ".tiff"), ("v.JPG", "JPEG", ".jpg"), ("v.jpeg", "JPEG", ".jpeg"), ("v.png", "PNG", ".png"),
        ("v.TIFF", "JPEG", ".tiff"), ("v.JPG", "PNG", ".jpg"),          # la extension del nombre manda aunque este en mayusculas y el formato diga otra cosa
        ("sin_extension", "TIFF", ".tif"), ("", "JPEG", ".jpg"), ("v.bmp", "PNG", ".png"), ("v.bmp", None, ".bin"), ("", "BMP", ".bin"), (None, "TIFF", ".tif")])
    def test_h_la_extension_de_la_copia_del_escaneo_sale_de_su_nombre_y_si_no_de_su_formato(self, archivo, formato, esperada):
        assert _pel()._extension_del_escaneo({"archivo": archivo, "formato": formato}) == esperada

    @pytest.mark.parametrize("caso", CASOS_DE_JSON_QUE_NO_ES_UNA_REFERENCIA)
    def test_h_un_json_que_no_es_una_referencia_se_rechaza_con_valueerror_y_dice_cual_archivo(self, tmp_path, caso):
        pel = _pel()
        ruta = tmp_path / pel.ARCHIVO_REFERENCIA_VIRGEN
        ruta.write_text(_contenido_que_no_es_una_referencia(caso, _base()[0]), encoding="utf-8")
        with pytest.raises(ValueError) as error:
            pel.leer_referencia_virgen(str(tmp_path))
        assert str(ruta) in str(error.value), "el mensaje dice cual archivo es"

    def test_h_la_escritura_vuelca_y_sincroniza_con_el_disco_antes_de_reemplazar(self, tmp_path, monkeypatch):
        """Un corte de luz entre escribir y reemplazar no puede dejar un JSON vacio: el temporal ya tiene TODO su contenido (vuelco) cuando se sincroniza con el disco, y se sincroniza ANTES de
        reemplazar. No se ve en el resultado (nada se corta aqui): se espian `os.fsync` y `os.replace`."""
        eventos = []
        fsync_real, replace_real = os.fsync, os.replace

        def fsync(fd):
            eventos.append(("fsync", [p.read_bytes() for p in tmp_path.iterdir() if ".tmp" in p.name]))
            return fsync_real(fd)

        def replace(origen, destino):
            eventos.append(("replace",))
            return replace_real(origen, destino)

        monkeypatch.setattr(os, "fsync", fsync)
        monkeypatch.setattr(os, "replace", replace)
        _pel()._escribir_sin_pisar(str(tmp_path / "x.json"), "contenido {}", False)
        assert eventos == [("fsync", [b"contenido {}"]), ("replace",)], eventos

    def test_h_los_archivos_de_texto_se_abren_siempre_en_utf8(self, tmp_path, monkeypatch):
        """La app corre en Windows (cp1252 por omision) y la carpeta de la base la comparten varios equipos: el JSON lleva tildes («película»); si un `open` de texto no dijera `encoding="utf-8"`,
        un equipo lo escribiria en cp1252 y otro lo leeria como dañado (un `UnicodeDecodeError` es un `ValueError`). En Linux (UTF-8 por omision) ninguna otra prueba lo nota: se espia `open`."""
        import builtins
        real = builtins.open
        abiertos = []

        def espia(archivo, *args, **kw):
            if str(archivo).startswith(str(tmp_path)):
                abiertos.append((Path(str(archivo)).name, args[0] if args else kw.get("mode", "r"), kw.get("encoding")))
            return real(archivo, *args, **kw)

        monkeypatch.setattr(builtins, "open", espia)
        pel = _pel()
        a, datos = _base()
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos)
        pel.leer_referencia_virgen(str(tmp_path))
        de_texto = [(nombre, modo, codificacion) for nombre, modo, codificacion in abiertos if "b" not in modo]
        assert len(de_texto) >= 2 and all(codificacion == "utf-8" for _, _, codificacion in de_texto), de_texto


# ---------------------------------------------------------------------------------------------------------------------- (h) A3-M2: guardar varias veces el mismo escaneo (14-10)
# El resto de lo que fija la decision A3-M2 (las dos pruebas principales estan arriba, en `TestLaReferenciaVirgenSeGuardaJuntoALaBase`): el caso MEDIDO en la revision, la manera de nombrar
# lo archivado, que un guardado identico despues de un cambio no vuelva a archivar y la forma que el archivo tiene en Windows.

class TestGuardarVariasVecesElMismoEscaneoNoPierdeNingunaVersion:
    @pytest.mark.parametrize("fechas", [("2026-10-13", "2026-10-14", "2026-10-15"), (FECHA, FECHA, FECHA)], ids=["tres_fechas_de_calculo", "la_misma_fecha_de_calculo"])
    def test_h_tres_guardados_del_mismo_escaneo_con_otros_datos_dejan_las_tres_versiones(self, tmp_path, reloj_fijo, fechas):
        """El caso MEDIDO en la revision (RV-A3-2): tres guardados del mismo escaneo, con otro usuario, otra fecha de calculo y otra orientacion declarada cada vez, dejaban solo el ultimo y la
        carpeta de anteriores ni se creaba. Ahora quedan las tres versiones: las dos primeras archivadas, con sus bytes intactos y el esquema de nombres de siempre (`<fecha_calculo>_<sha8>.json` y,
        si el nombre ya existe, `_2`), y la tercera vigente."""
        pel = _pel()
        a, datos = _base()
        sha8 = a.procedencia["sha256"][:8]
        guardados = []
        for fecha, orientacion, usuario in zip(fechas, (None, "girada", None), ("lamaya", "otro_fisico", "tercero")):
            ref = _medir_otra_vez_el_mismo_escaneo(datos, fecha_calculo=fecha, orientacion_declarada=orientacion)
            assert ref.estado == "ok" and ref.procedencia["sha256"] == a.procedencia["sha256"], "el control: es siempre el MISMO escaneo"
            ruta = Path(pel.guardar_referencia_virgen(ref, str(tmp_path), datos=datos, usuario=usuario))
            guardados.append(ruta.read_bytes())
        assert len(set(guardados)) == 3, "el control: los tres guardados escriben contenidos distintos"
        nombres = [f"{fechas[0]}_{sha8}.json", f"{fechas[1]}_{sha8}.json"] if fechas[0] != fechas[1] else [f"{FECHA}_{sha8}.json", f"{FECHA}_{sha8}_2.json"]
        assert _los_archivados(tmp_path) == dict(zip(nombres, guardados[:2])), "las dos primeras versiones quedan archivadas, tal cual, con sus nombres"
        assert (tmp_path / pel.ARCHIVO_REFERENCIA_VIRGEN).read_bytes() == guardados[2], "la tercera es la vigente"
        assert [json.loads(g.decode("utf-8"))["guardada_por"] for g in guardados] == ["lamaya", "otro_fisico", "tercero"], "de cada version se puede saber quien la guardo"
        assert [json.loads(g.decode("utf-8"))["referencia"]["procedencia"]["orientacion_declarada"] for g in guardados] == [None, "girada", None]

    def test_h_repetir_el_ultimo_guardado_despues_de_un_cambio_no_archiva_otra_vez(self, tmp_path, reloj_fijo):
        """Un cambio archiva la anterior una vez; repetir EXACTAMENTE ese guardado (el reloj congelado: los mismos bytes) ya no archiva nada mas."""
        pel = _pel()
        a, datos = _base()
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="lamaya")
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="otro_fisico")
        despues_del_cambio = _los_archivados(tmp_path)
        assert len(despues_del_cambio) == 1, "el cambio de usuario archivo la primera version"
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="otro_fisico")
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="otro_fisico")
        assert _los_archivados(tmp_path) == despues_del_cambio, "repetir el ultimo guardado, identico, no archiva un duplicado"

    def test_h_un_json_anterior_con_saltos_de_linea_de_windows_y_el_mismo_contenido_no_se_archiva(self, tmp_path, reloj_fijo):
        """El modo texto de Windows escribe cada «\\n» como «\\r\\n»: el JSON que esta app escribio alla y el que va a escribir ahora son el MISMO contenido, y no se archiva un duplicado exacto (la
        app se usa en Windows; en Linux se simula la forma que tiene el archivo alla)."""
        pel = _pel()
        a, datos = _base()
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="lamaya"))
        como_linux = ruta.read_bytes()
        en_windows = como_linux.replace(b"\n", b"\r\n")
        assert b"\r\n" in en_windows and en_windows != como_linux and b"\r" not in como_linux, "el control: el JSON no lleva ningun «\\r» propio, solo los de los saltos de linea"
        ruta.write_bytes(en_windows)
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="lamaya")
        assert _los_archivados(tmp_path) == {}, "se archivo un duplicado exacto: lo unico que difiere es como el sistema escribe los saltos de linea"

    def test_h_un_json_anterior_con_saltos_de_linea_de_windows_y_otro_contenido_se_archiva_tal_cual(self, tmp_path, reloj_fijo):
        """El control del anterior: con los saltos de linea de Windows pero OTRO contenido (otro usuario), la anterior se archiva con sus bytes intactos, los «\\r\\n» incluidos."""
        pel = _pel()
        a, datos = _base()
        ruta = Path(pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="lamaya"))
        en_windows = ruta.read_bytes().replace(b"\n", b"\r\n")
        ruta.write_bytes(en_windows)
        pel.guardar_referencia_virgen(a, str(tmp_path), datos=datos, usuario="otro_fisico")
        assert _los_archivados(tmp_path) == {f"{FECHA}_{a.procedencia['sha256'][:8]}.json": en_windows}, "se archiva tal cual, byte por byte"
        assert json.loads(ruta.read_text(encoding="utf-8"))["guardada_por"] == "otro_fisico"


# Un campo dañado de una referencia «ok» -> la funcion que lo daña. Cada uno debe rechazarse con `ValueError`; ninguno puede pasar la lectura ni lanzar otra excepcion.
def _poner(*ruta, valor):
    def f(d):
        x = d
        for k in ruta[:-1]:
            x = x[k]
        x[ruta[-1]] = valor
    return f


def _quitar(*ruta):
    def f(d):
        x = d
        for k in ruta[:-1]:
            x = x[k]
        del x[ruta[-1]]
    return f


def _con_una_capa_de_mas(d):
    d["capas"]["X"] = copy.deepcopy(d["capas"]["R"])


DANOS_DE_LA_REFERENCIA = {
    # una clave de las siete que `como_dict()` siempre escribe
    "falta_el_estado": _quitar("estado"), "faltan_las_capas": _quitar("capas"), "faltan_las_pruebas": _quitar("pruebas"), "faltan_los_avisos": _quitar("avisos"),
    "falta_la_region": _quitar("region"), "falta_la_procedencia": _quitar("procedencia"), "faltan_los_parametros": _quitar("parametros"),
    # el estado y las capas
    "estado_nulo": _poner("estado", valor=None), "estado_numerico": _poner("estado", valor=5),
    "capas_nulas": _poner("capas", valor=None), "capas_en_lista": _poner("capas", valor=[]), "capas_sin_gris": _quitar("capas", "gris"), "capas_con_una_de_mas": _con_una_capa_de_mas,
    "capa_nula": _poner("capas", "R", valor=None), "capa_de_texto": _poner("capas", "R", valor="x"), "capa_sin_mediana": _quitar("capas", "R", "mediana"),
    "capa_sin_estado": _quitar("capas", "R", "estado"), "capa_con_estado_nulo": _poner("capas", "R", "estado", valor=None),
    "capa_no_ok_en_una_referencia_ok": _poner("capas", "R", "estado", valor="no medible: x"),
    "mediana_nula": _poner("capas", "G", "mediana", valor=None), "mediana_de_texto": _poner("capas", "G", "mediana", valor="x"), "mediana_booleana": _poner("capas", "G", "mediana", valor=True),
    "mediana_nan": _poner("capas", "G", "mediana", valor=float("nan")), "mediana_infinita": _poner("capas", "G", "mediana", valor=float("inf")),
    "n_de_texto": _poner("capas", "B", "n", valor="x"), "n_nulo": _poner("capas", "B", "n", valor=None), "n_negativo": _poner("capas", "B", "n", valor=-1),
    "n_cero_en_una_referencia_ok": _poner("capas", "B", "n", valor=0), "n_decimal": _poner("capas", "B", "n", valor=1.5), "n_booleano": _poner("capas", "B", "n", valor=True),
    "iqr_de_texto": _poner("capas", "gris", "iqr", valor="x"), "iqr_nan": _poner("capas", "gris", "iqr", valor=float("nan")),
    "meseta_de_texto": _poner("capas", "gris", "meseta", valor="x"), "contraste_de_texto": _poner("capas", "gris", "contraste", valor="x"),
    # las pruebas y los avisos
    "pruebas_nulas": _poner("pruebas", valor=None), "pruebas_de_texto": _poner("pruebas", valor="x"), "prueba_nula": _poner("pruebas", 0, valor=None),
    "prueba_sin_nombre": _quitar("pruebas", 0, "nombre"), "prueba_con_nombre_numerico": _poner("pruebas", 0, "nombre", valor=5), "prueba_con_resultado_nulo": _poner("pruebas", 0, "resultado", valor=None),
    "prueba_con_texto_nulo": _poner("pruebas", 0, "texto", valor=None),
    "avisos_nulos": _poner("avisos", valor=None), "avisos_de_texto": _poner("avisos", valor="x"), "avisos_que_no_son_textos": _poner("avisos", valor=[1]),
    "avisos_en_diccionario": _poner("avisos", valor={"a": "b"}),
    # la region de una referencia «ok»
    "region_nula": _poner("region", valor=None), "region_en_lista": _poner("region", valor=[]), "region_sin_n": _quitar("region", "n"), "region_con_n_de_texto": _poner("region", "n", valor="x"),
    "region_con_n_cero": _poner("region", "n", valor=0), "region_sin_caja": _quitar("region", "caja"), "caja_de_tres": _poner("region", "caja", valor=[1, 2, 3]),
    "caja_con_un_texto": _poner("region", "caja", valor=[1, 2, 3, "x"]), "caja_que_no_es_lista": _poner("region", "caja", valor="x"), "region_sin_area": _quitar("region", "area_mm2"),
    "area_de_texto": _poner("region", "area_mm2", valor="x"),
    # la procedencia
    "procedencia_nula": _poner("procedencia", valor=None), "procedencia_en_lista": _poner("procedencia", valor=[]), "sin_huella": _quitar("procedencia", "sha256"),
    "huella_numerica": _poner("procedencia", "sha256", valor=5), "huella_corta": _poner("procedencia", "sha256", valor="abc"), "huella_con_una_ruta": _poner("procedencia", "sha256", valor="../" + "a" * 61),
    "huella_que_no_es_hexadecimal": _poner("procedencia", "sha256", valor="g" * 64), "huella_con_basura_al_final": _poner("procedencia", "sha256", valor="a" * 64 + "/x"),
    "huella_de_65": _poner("procedencia", "sha256", valor="a" * 65),
    "sin_fecha_de_calculo": _quitar("procedencia", "fecha_calculo"), "fecha_de_calculo_vacia": _poner("procedencia", "fecha_calculo", valor=""),
    "fecha_de_calculo_numerica": _poner("procedencia", "fecha_calculo", valor=5), "sin_archivo": _quitar("procedencia", "archivo"), "archivo_numerico": _poner("procedencia", "archivo", valor=5),
    # los parametros
    "parametros_nulos": _poner("parametros", valor=None), "parametros_en_lista": _poner("parametros", valor=[]), "parametros_sin_el_margen": _quitar("parametros", "margen_borde_virgen_mm"),
    "margen_de_texto": _poner("parametros", "margen_borde_virgen_mm", valor="x"), "margen_nan": _poner("parametros", "margen_borde_virgen_mm", valor=float("nan")),
}

_QUITAR = object()                   # "quitar la clave", un caso mas del barrido
_HOSTILES = [None, True, -1, 1.5, "x", [], {}, float("nan"), 10 ** 30, _QUITAR]       # 10 ** 30: un entero que `numpy` no sabe preguntar si es finito (lanzaria `TypeError`)


def _rutas_a_las_hojas(x, ruta=()):
    """Cada hoja de un diccionario de JSON como una tupla de claves: los diccionarios y las listas de diccionarios se recorren; una lista de numeros o de textos (o vacia) es una hoja."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _rutas_a_las_hojas(v, ruta + (k,))
    elif isinstance(x, list) and x and not all(isinstance(e, (int, float, str)) for e in x):
        for i, v in enumerate(x):
            yield from _rutas_a_las_hojas(v, ruta + (i,))
    else:
        yield ruta


def _dano(d, ruta, valor):
    """`d` (una copia) con la hoja `ruta` cambiada por `valor` (o la clave quitada)."""
    d = copy.deepcopy(d)
    padre = d
    for k in ruta[:-1]:
        padre = padre[k]
    if valor is _QUITAR:
        if isinstance(padre, dict):
            del padre[ruta[-1]]
        else:
            return None                                  # el elemento de una lista no se "quita": sin caso
    else:
        padre[ruta[-1]] = valor
    return d


class TestUnaReferenciaDanadaSeRechazaAlLeerla:
    @pytest.mark.parametrize("dano", list(DANOS_DE_LA_REFERENCIA), ids=list(DANOS_DE_LA_REFERENCIA))
    def test_h_cada_campo_danado_se_rechaza_con_valueerror_al_leerlo(self, tmp_path, dano):
        pel = _pel()
        d = copy.deepcopy(_base()[0].como_dict())
        DANOS_DE_LA_REFERENCIA[dano](d)
        with pytest.raises(ValueError):
            pel.referencia_virgen_desde_dict(d)
        ruta = tmp_path / pel.ARCHIVO_REFERENCIA_VIRGEN
        ruta.write_text(json.dumps({"version": "PV-2", "referencia": d, "guardada_por": None, "guardada_el": "2026-10-13T10:00:00"}), encoding="utf-8")
        with pytest.raises(ValueError) as error:
            pel.leer_referencia_virgen(str(tmp_path))
        assert str(ruta) in str(error.value), "el mensaje dice cual archivo esta dañado"

    def test_h_un_campo_danado_de_a_uno_se_rechaza_o_se_puede_usar_pero_nunca_revienta_despues(self):
        """El barrido: cada una de las hojas de una referencia buena (147) se cambia, de a una, por cada valor hostil (nulo, booleano, negativo, decimal, texto, lista vacia, diccionario vacio,
        NaN, un entero enorme, o la clave quitada). La lectura la rechaza con `ValueError` o la acepta; si la acepta, lo que se leyo se puede describir, volver a escribir y preguntar sin ninguna excepcion.
        Cualquier OTRA excepcion (un `TypeError` de leer, un `KeyError` o un `ValueError` de usar lo leido) es el defecto de RV-A3-3: el archivo dañado revienta lejos de donde se leyo."""
        pel = _pel()
        bueno = _base()[0].como_dict()
        rechazados = aceptados = 0
        fallos = []
        for ruta in _rutas_a_las_hojas(bueno):
            for hostil in _HOSTILES:
                d = _dano(bueno, ruta, hostil)
                if d is None:
                    continue
                cual = f"{'.'.join(map(str, ruta))} = {'(quitada)' if hostil is _QUITAR else repr(hostil)}"
                try:
                    ref = pel.referencia_virgen_desde_dict(d)
                except ValueError:
                    rechazados += 1
                    continue
                except Exception as e:                                         # noqa: BLE001
                    fallos.append(f"{cual}: al LEER lanza {type(e).__name__}: {str(e)[:60]}")
                    continue
                aceptados += 1
                try:
                    ref.descripcion()
                    json.dumps(ref.como_dict())
                    [ref.valor(c) for c in CAPAS]
                except Exception as e:                                         # noqa: BLE001
                    fallos.append(f"{cual}: se lee y al USARLO lanza {type(e).__name__}: {str(e)[:60]}")
        assert not fallos, f"{len(fallos)} daños de un solo campo no se rechazan con ValueError al leerlos:\n" + "\n".join(fallos[:15])
        assert rechazados > 300 and aceptados > 300, (rechazados, aceptados)        # no vacuidad (hoy ~550 y ~900): rechaza lo que debe y deja pasar lo que nada usa (parametros, procedencia...)

    def test_h_una_referencia_no_valida_tambien_se_lee_de_su_diccionario(self):
        """La copia de una referencia «no valida» viaja dentro de un piso «no medible» (DA-81): se lee igual, sin medianas."""
        no_valida = _no_valida()
        assert no_valida.estado.startswith("no válida: ") and no_valida.region is None
        leida = _pel().referencia_virgen_desde_dict(json.loads(json.dumps(no_valida.como_dict())))
        assert leida.estado == no_valida.estado and leida.como_dict() == no_valida.como_dict() and all(leida.valor(c) is None for c in CAPAS)

    @pytest.mark.parametrize("dano", ["n_negativo", "n_de_texto", "mediana_de_texto", "avisos_nulos", "capas_sin_gris", "procedencia_nula", "prueba_sin_nombre", "estado_numerico", "region_en_lista", "capa_con_estado_nulo"])
    def test_h_una_referencia_no_valida_danada_tambien_se_rechaza(self, dano):
        """Los TIPOS se exigen a toda referencia, «ok» o no: la copia de una «no valida» que viaja con un piso «no medible» tambien puede venir dañada."""
        d = copy.deepcopy(_no_valida().como_dict())
        DANOS_DE_LA_REFERENCIA[dano](d)
        with pytest.raises(ValueError):
            _pel().referencia_virgen_desde_dict(d)

    @pytest.mark.parametrize("cambio", ["sin_iqr", "sin_bits", "formato_y_clase_de_resolucion_numericos"])
    def test_h_una_referencia_leida_con_campos_laxos_se_puede_usar_en_el_modo_virgen(self, cambio):
        """Los campos que la lectura NO exige (la dispersion, y de la procedencia lo que `piso_de_pelicula` compara con `.get`) no pueden reventar el modo virgen aunque vengan raros."""
        pel = _pel()
        d = copy.deepcopy(_base()[0].como_dict())
        if cambio == "sin_iqr":
            for capa in d["capas"].values():
                capa["iqr"] = None
        elif cambio == "sin_bits":
            d["procedencia"]["bits"] = None
        else:
            d["procedencia"]["formato"], d["procedencia"]["clase_resolucion"] = 5, 5
        ref = pel.referencia_virgen_desde_dict(d)
        s = A2._sint("B", 0.4)
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=ref)
        assert p.estado == "ok" or p.estado.startswith("no medible"), p.estado
        assert json.loads(json.dumps(p.como_dict()))["modo"] == "virgen" and p.descripcion()


# ====================================================================================================================== (i) el modo virgen

def _signo(d):
    return "0" if d == 0 else f"{d:+.1f}".replace(".0", "")


class TestElModoVirgen:
    def test_i_el_piso_es_el_de_la_virgen_y_trae_la_comparacion_con_el_automatico(self):
        s = A2._sint("B", 0.4)
        ref = _base()[0]
        pel = _pel()
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=ref)
        auto = piso(s.pelicula, s.campo)
        assert p.estado == "ok" and p.origen == "virgen" and p.modo == "virgen" and p.referencia is ref and p.region is None and p.punto is None and p.esquinas == ()
        for c in CAPAS:
            capa = p.capas[c]
            assert capa.estado == "ok" and capa.mediana == ref.valor(c) and capa.n == ref.capas[c].n and capa.iqr == ref.capas[c].iqr
            assert capa.meseta is not None and capa.contraste == pytest.approx(ref.valor(c) - capa.meseta)
        assert p.comparacion is not None and p.comparacion.estado == "ok" and p.comparacion.comparacion is None and A2._medianas(p.comparacion) == A2._medianas(auto)
        assert p.avisos == () and p.todas_medibles is True and p.parametros["tolerancia_virgen_mas_oscura"] == 3.0
        d = p.comparacion.region.distancia_media_mm
        dif = {c: ref.valor(c) - auto.valor(c) for c in CAPAS}
        assert all(v > 0 for v in dif.values()) and dif["R"] > 5, dif
        esperado = (f"Comparación (solo informativa): el piso automático de esta película (en sus cuatro esquinas, a {d:.1f} mm del campo en promedio) es rojo {_cifra(auto.valor('R'))}, "
                    f"verde {_cifra(auto.valor('G'))}, azul {_cifra(auto.valor('B'))}, gris {_cifra(auto.valor('gris'))}; "
                    f"la película virgen está {_signo(dif['R'])} / {_signo(dif['G'])} / {_signo(dif['B'])} / {_signo(dif['gris'])} niveles más clara.")
        assert pel.texto_de_la_comparacion(p) == esperado
        assert pel.texto_de_la_comparacion(auto) == "" and pel.texto_de_la_comparacion(piso(s.pelicula, s.campo, punto=_punto_sobre_la_pelicula(s))) == ""

    def test_i_una_capa_mas_oscura_que_el_automatico_cambia_la_frase_de_la_comparacion(self):
        s = A2._sint("B", 0.4)
        ref = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"virgen_bgr": (82.0, 168.0, 105.5), "meseta_bgr": (82.0, 168.0, 105.5)}), "tiff", 600))
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=ref)
        assert p.estado == "ok", p.estado
        texto = _pel().texto_de_la_comparacion(p)
        assert texto.endswith("más clara en el rojo y 2 niveles más oscura en el verde.") or "2 niveles más oscura en el verde" in texto, texto
        assert "más clara en el rojo" in texto

    def test_i_si_la_virgen_es_mas_oscura_que_la_pelicula_de_fuera_del_campo_no_sirve(self):
        s = A2._sint("B", 0.4)
        oscura = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"virgen_bgr": (82.0, 165.0, 105.5), "meseta_bgr": (82.0, 165.0, 105.5)}), "tiff", 600))
        assert oscura.estado == "ok"
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=oscura)
        assert p.estado.startswith(_pel().MOTIVO_VIRGEN_MAS_OSCURA) and " en el verde (-5 niveles)" in p.estado, p.estado
        assert "no puede tener más dosis que la película irradiada de fuera del campo" in p.estado
        assert p.region is None and all(c.mediana is None for c in p.capas.values()) and p.comparacion is not None, "aun rechazada, la comparacion se muestra"
        tolerante = piso(s.pelicula, s.campo, _P(tolerancia_virgen_mas_oscura=10.0), modo="virgen", referencia=oscura)
        assert tolerante.estado == "ok" and tolerante.capas["G"].mediana == oscura.valor("G"), "la tolerancia es un parametro"

    @pytest.mark.parametrize("capa,delta,rechaza", [("R", -5.0, True), ("G", -5.0, True), ("B", -4.5, False)])
    def test_i_la_virgen_mas_oscura_se_juzga_en_el_rojo_y_el_verde_y_no_en_el_azul(self, capa, delta, rechaza):
        """La virgen apenas mas clara (+1) que el piso automatico en las tres capas salvo una, 5 niveles mas oscura (4.5 en el azul: por debajo del aviso de 5): mas oscura en el rojo o en el
        verde no sirve (una virgen no puede tener mas dosis que la pelicula de fuera del campo); en el azul no se juzga (la dosis casi no lo cambia, diseño §5)."""
        s = A2._sint("B", 0.4)
        auto = piso(s.pelicula, s.campo)
        v = {c: auto.valor(c) + 1.0 for c in "RGB"}
        v[capa] = auto.valor(capa) + delta
        ref = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"virgen_bgr": (v["B"], v["G"], v["R"]), "meseta_bgr": (v["B"], v["G"], v["R"])}), "tiff", 600))
        assert ref.estado == "ok", ref.estado
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=ref)
        if rechaza:
            nombre = {"R": "rojo", "G": "verde"}[capa]
            assert p.estado.startswith(_pel().MOTIVO_VIRGEN_MAS_OSCURA) and f"en el {nombre} (" in p.estado and p.region is None, p.estado
        else:
            assert p.estado == "ok" and p.avisos == (), (p.estado, p.avisos)

    def test_i_el_azul_y_el_verde_muy_distintos_del_automatico_avisan_y_los_umbrales_son_parametros(self):
        s = A2._sint("B", 0.4)
        azul = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"virgen_bgr": (90.0, 174.0, 105.5), "meseta_bgr": (90.0, 174.0, 105.5)}), "tiff", 600))
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=azul)
        assert p.estado == "ok" and len(p.avisos) == 1 and "azul" in p.avisos[0], p.avisos
        assert piso(s.pelicula, s.campo, _P(aviso_azul_virgen=20.0), modo="virgen", referencia=azul).avisos == ()
        verde = _medir_virgen(gen.codificar(_virgen_arreglo("A", calib_extra={"virgen_bgr": (82.0, 200.0, 105.5), "meseta_bgr": (82.0, 200.0, 105.5)}), "tiff", 600))
        q = piso(s.pelicula, s.campo, modo="virgen", referencia=verde)
        assert q.estado == "ok" and len(q.avisos) == 1 and "verde" in q.avisos[0], q.avisos
        assert piso(s.pelicula, s.campo, _P(aviso_verde_virgen=40.0), modo="virgen", referencia=verde).avisos == ()

    def test_i_una_virgen_de_16_bits_contra_una_pelicula_de_8_es_otra_cadena_de_captura(self):
        s = A2._sint("B", 0.4)
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=_otra_virgen()[0])
        assert p.estado.startswith(_pel().MOTIVO_VIRGEN_OTRA_CADENA) and "16 bits contra 8" in p.estado, p.estado
        assert p.region is None and all(c.mediana is None for c in p.capas.values())

    def test_i_un_jpeg_contra_un_tiff_avisa(self):
        s = A2._sint("B", 0.4)
        jpeg = _pel().leer_pelicula(gen.codificar(s.img, "jpeg", 600))
        p = piso(jpeg, s.campo, modo="virgen", referencia=_base()[0])
        assert p.estado == "ok" and any("JPEG" in a and "TIFF" in a for a in p.avisos), p.avisos
        assert p.avisos and p.como_dict()["avisos"] == list(p.avisos), "el diccionario que viaja con el analisis lleva los avisos"

    def test_i_una_virgen_con_otra_clase_de_resolucion_avisa(self):
        s = A2._sint("B", 0.4)
        editada = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 96))
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=editada)
        assert p.estado == "ok" and any("resolución" in a for a in p.avisos), p.avisos

    def test_i_sin_referencia_o_con_una_no_valida_no_hay_piso_y_nunca_se_cae_al_automatico(self):
        s = A2._sint("B", 0.4)
        pel = _pel()
        sin = piso(s.pelicula, s.campo, modo="virgen")
        assert sin.estado == pel.MOTIVO_SIN_REFERENCIA_VIRGEN + ": cárguela con «Película virgen...»" and sin.origen == "virgen" and sin.region is None
        assert all(c.mediana is None and c.estado == sin.estado for c in sin.capas.values())
        mala = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 300))
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=mala)
        assert p.estado.startswith(pel.MOTIVO_REFERENCIA_VIRGEN_NO_VALIDA + ": ") and mala.estado.removeprefix(pel.PREFIJO_NO_VALIDA) in p.estado
        assert all(c.mediana is None for c in p.capas.values())
        # OD.1: sin modo pedido, una referencia presente SI cambia el modo (`modo_efectivo`: la virgen si hay referencia); un modo pedido se respeta
        assert piso(s.pelicula, s.campo, referencia=_base()[0]).modo == "virgen" and piso(s.pelicula, s.campo, modo="automatico", referencia=_base()[0]).modo == "automatico"

    def test_i_si_el_automatico_no_se_puede_medir_la_virgen_si_y_el_aviso_lo_dice(self):
        """El caso para el que sirve: un recorte demasiado ajustado, donde el piso automatico es "no medible" (A -3 grados)."""
        s = A2._sint("A", -3.0)
        assert piso(s.pelicula, s.campo).estado.startswith("no medible")
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=_base()[0])
        assert p.estado == "ok" and p.comparacion is not None and p.comparacion.estado.startswith("no medible")
        assert any("no se pudo comparar con el piso automático" in a for a in p.avisos), p.avisos
        assert _pel().texto_de_la_comparacion(p).startswith("Comparación (solo informativa): no se pudo")

    def test_i_el_diccionario_lleva_la_referencia_entera_y_la_copia_guardada_da_el_mismo_piso(self):
        s = A2._sint("B", 0.4)
        pel = _pel()
        ref = _base()[0]
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=ref)
        d = p.como_dict()
        assert json.loads(json.dumps(d)) == d and d["modo"] == "virgen" and d["origen"] == "virgen" and d["region"] is None and d["esquinas"] == [] and d["punto"] is None
        assert d["referencia_virgen"] == ref.como_dict()
        assert d["comparacion"]["piso_automatico"]["estado"] == "ok" and d["comparacion"]["piso_automatico"]["origen"] == "automatico"
        assert d["comparacion"]["diferencia"] == {c: pytest.approx(p.capas[c].mediana - p.comparacion.capas[c].mediana) for c in CAPAS}
        copia = pel.referencia_virgen_desde_dict(json.loads(json.dumps(d["referencia_virgen"])))
        again = piso(s.pelicula, s.campo, modo="virgen", referencia=copia)
        assert again.como_dict() == d, "reabrir un analisis con SU copia de la referencia da el mismo piso"
        auto = piso(s.pelicula, s.campo).como_dict()
        assert auto["referencia_virgen"] is None and auto["comparacion"] is None and auto["modo"] == "automatico" and len(auto["esquinas"]) == 4

    def test_i_el_diccionario_trae_las_siete_claves_de_A2_y_las_seis_nuevas_en_cada_forma_de_terminar(self):
        s = A2._sint("B", 0.4)
        viejas = {"estado", "origen", "escala_mm", "campo_luz", "parametros", "capas", "region"}
        nuevas = {"modo", "punto", "esquinas", "referencia_virgen", "comparacion", "avisos"}
        casos = [piso(s.pelicula, s.campo), piso(s.pelicula, s.campo, punto=_punto_sobre_la_pelicula(s)), piso(s.pelicula, s.campo, punto=(10 ** 6, 10 ** 6)),
                 piso(s.pelicula, s.campo, modo="virgen"), piso(s.pelicula, s.campo, modo="virgen", referencia=_base()[0]), piso(s.pelicula, [(0, 0), (1, 1), (2, 2), (3, 3)]),
                 piso(A2._a_pelicula(s.img, dpi=300), s.campo)]
        for p in casos:
            d = p.como_dict()
            assert set(d) == viejas | nuevas and json.loads(json.dumps(d)) == d, p.estado
            assert d["modo"] == p.modo and d["avisos"] == list(p.avisos) and (d["punto"] is None) == (p.punto is None)
        auto = casos[0].como_dict()
        for e, objeto in zip(auto["esquinas"], casos[0].esquinas):
            assert set(e) == {"esquina", "estado", "motivo", "origen", "n", "medianas", "iqr", "distancia_media_mm", "caja", "respaldos"} and e["esquina"] == objeto.esquina
            assert isinstance(e["caja"], list) and len(e["caja"]) == 4 and e["respaldos"] == []
        manual = casos[1].como_dict()
        assert manual["punto"] == list(_punto_sobre_la_pelicula(s)) and manual["esquinas"] == []
        real = piso(A2._real("EPSON001_JPG"), CLICS_REALES["EPSON001_JPG"]).como_dict()
        r = real["esquinas"][3]["respaldos"][0]
        assert set(r) == {"nombre", "estado", "motivo", "d_mm", "centro", "n", "medianas"} and r["nombre"] == "giro +5 grados" and r["d_mm"] == 7.5 and isinstance(r["centro"], list)
        assert json.loads(json.dumps(real)) == real

    def test_i_los_campos_nuevos_del_piso_tienen_valor_por_omision_y_los_constructores_de_A2_siguen_valiendo(self):
        pel = _pel()
        p = pel.Piso("no medible: x", "automatico", {c: pel.CapaDelPiso(c, "no medible: x") for c in CAPAS + ("gris",)}, None, None, (), {})
        assert p.esquinas == () and p.punto is None and p.referencia is None and p.comparacion is None and p.avisos == () and p.modo == "automatico"
        with pytest.raises(Exception):
            p.estado = "ok"

    def test_i_con_el_campo_fuera_de_la_pelicula_los_tres_modos_dicen_sin_meseta_y_la_comparacion_tambien(self):
        """Con el campo fuera de la pelicula ningun modo da un numero (los tres necesitan la meseta) y los tres lo dicen igual (decision de Opus del 13-10): en el modo virgen la comparacion
        con el automatico, que se guarda con el analisis (`como_dict()["comparacion"]`), tambien dice la meseta y no un motivo de las esquinas."""
        s = A2._sint("B", 0.4)
        pel = _pel()
        lejos = [(x - 3400.0, y - 3400.0) for x, y in s.campo]
        automatico = piso(s.pelicula, lejos)
        punto = piso(s.pelicula, lejos, punto=_punto_sobre_la_pelicula(s))
        virgen = piso(s.pelicula, lejos, modo="virgen", referencia=_base()[0])
        assert automatico.estado == punto.estado == virgen.estado == pel.MOTIVO_SIN_MESETA, (automatico.estado, punto.estado, virgen.estado)
        assert virgen.comparacion is not None and virgen.comparacion.estado == pel.MOTIVO_SIN_MESETA, virgen.comparacion.estado
        d = virgen.como_dict()["comparacion"]
        assert d["piso_automatico"]["estado"] == pel.MOTIVO_SIN_MESETA and d["diferencia"] is None


# ====================================================================================================================== (j) los textos

_ADJETIVO = {"R": "roja", "G": "verde", "B": "azul", "gris": "gris"}


class TestLosTextos:
    def test_j_la_descripcion_del_automatico_dice_de_donde_salio_en_sus_cuatro_esquinas(self):
        s = A2._sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        t = p.descripcion()
        r = p.region
        assert t.startswith(f"Piso tomado en {r.n} píxeles de película fuera del campo luminoso, a {r.distancia_media_mm:.1f} mm de él en promedio "
                            f"(de {r.distancia_minima_mm:.1f} a {r.distancia_maxima_mm:.1f} mm) en sus cuatro esquinas."), t
        assert "No es película sin irradiar: recibe dosis periférica." in t and "virgen" not in t.lower() and "se tomó con la ventana" not in t

    def test_j_la_descripcion_dice_la_esquina_reemplazada_y_la_quitada(self):
        real = piso(A2._real("EPSON001_JPG"), CLICS_REALES["EPSON001_JPG"])
        assert "La esquina inferior izquierda se tomó con la ventana girada +5 grados a 7.5 mm del campo (dispersa: IQR del azul 24 > 15)." in real.descripcion(), real.descripcion()
        s = A2._sint("A", 1.0)
        quitada = piso(s.pelicula, s.campo)
        t = quitada.descripcion()
        assert "La esquina superior izquierda no dio piso (sin película suficiente) y se usaron las otras tres." in t and "en 3 de sus cuatro esquinas." in t, t
        lateral = piso(A2._a_pelicula(_etiqueta(A2._sint("B", 0.4).img, A2._sint("B", 0.4), "UR", 9.7, valor=245)), A2._sint("B", 0.4).campo)
        assert "La esquina superior derecha se tomó con la ventana lateral s=0.1 del lado UR-DR a 6.5 mm del campo (" in lateral.descripcion(), lateral.descripcion()

    def test_j_la_descripcion_del_sexto_clic_y_de_la_virgen(self):
        s = A2._sint("B", 0.4)
        manual = piso(s.pelicula, s.campo, punto=_punto_sobre_la_pelicula(s))
        assert "punto" in manual.descripcion() and "3 × 3 mm" in manual.descripcion() and "esquinas" not in manual.descripcion()
        ref = _base()[0]
        virgen = piso(s.pelicula, s.campo, modo="virgen", referencia=ref)
        t = virgen.descripcion()
        assert t.startswith(ref.descripcion()) and "virgen_lote.tif" in t and ref.procedencia["sha256"][:8] in t
        assert all(f"{_cifra(ref.valor(c))}" in ref.descripcion() for c in ("R", "G", "B", "gris")) and "2 mm o más de sus bordes" in ref.descripcion()
        rota = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 300))
        assert rota.estado in rota.descripcion()
        con_aviso = _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 96))
        assert all(a in con_aviso.descripcion() for a in con_aviso.avisos) and con_aviso.avisos

    def test_j_el_texto_breve_del_piso_en_cada_forma(self):
        pel = _pel()
        s = A2._sint("B", 0.4)
        auto = piso(s.pelicula, s.campo)
        d = auto.region.distancia_media_mm
        assert pel.texto_breve_del_piso(auto) == f"Piso (capa verde): {_cifra(auto.valor('G'))} niveles; automático, en las cuatro esquinas de la película a {d:.1f} mm del campo."
        assert pel.texto_breve_del_piso(auto, "R").startswith(f"Piso (capa roja): {_cifra(auto.valor('R'))} niveles; automático")
        assert pel.texto_breve_del_piso(auto, "gris").startswith("Piso (capa gris): ") and pel.texto_breve_del_piso(auto, "B").startswith("Piso (capa azul): ")
        assert pel.texto_breve_del_piso(auto.como_dict()) == pel.texto_breve_del_piso(auto), "acepta el Piso o su diccionario (lo que viaja guardado)"
        real = piso(A2._real("EPSON001_JPG"), CLICS_REALES["EPSON001_JPG"])
        assert pel.texto_breve_del_piso(real) == ("Piso (capa verde): 185 niveles; automático, en las cuatro esquinas de la película a 9.5 mm del campo; "
                                                 "la esquina inferior izquierda con la ventana girada +5 grados.")
        quitada = piso(A2._sint("A", 1.0).pelicula, A2._sint("A", 1.0).campo)
        t = pel.texto_breve_del_piso(quitada)
        assert "automático, en 3 de las 4 esquinas de la película a " in t and t.endswith("la esquina superior izquierda sin piso.")
        punto = piso(s.pelicula, s.campo, punto=_punto_sobre_la_pelicula(s))
        assert pel.texto_breve_del_piso(punto) == f"Piso (capa verde): {_cifra(punto.valor('G'))} niveles; punto marcado sobre película sin irradiar, a {punto.region.distancia_media_mm:.1f} mm del campo."
        assert pel.texto_breve_del_piso(piso(s.pelicula, [(0, 0), (1, 1), (2, 2), (3, 3)])) == "Piso: " + pel.MOTIVO_CAMPO_INVALIDO

    def test_j_el_texto_breve_de_la_virgen_dice_el_archivo_la_fecha_y_la_huella(self, tmp_path):
        pel = _pel()
        s = A2._sint("B", 0.4)
        sal = io.BytesIO()
        tifffile.imwrite(sal, np.ascontiguousarray(_virgen_arreglo("A")[:, :, ::-1]), photometric="rgb", resolution=(600, 600), resolutionunit="INCH", compression=None,
                         datetime="2026:10:13 10:00:00")
        ref = _medir_virgen(sal.getvalue(), nombre="virgen_lote.tif")
        assert ref.estado == "ok" and ref.procedencia["fecha_escaneo"] == "2026-10-13"
        p = piso(s.pelicula, s.campo, modo="virgen", referencia=ref)
        assert pel.texto_breve_del_piso(p) == f"Piso (capa verde): {_cifra(ref.valor('G'))} niveles; película virgen «virgen_lote.tif», escaneada el 2026-10-13 (huella {ref.procedencia['sha256'][:8]})."
        sin_fecha = piso(s.pelicula, s.campo, modo="virgen", referencia=_base()[0])
        assert pel.texto_breve_del_piso(sin_fecha) == (f"Piso (capa verde): {_cifra(_base()[0].valor('G'))} niveles; película virgen «virgen_lote.tif», "
                                                      f"medida el {FECHA} (huella {_base()[0].procedencia['sha256'][:8]}).")

    def test_j_una_capa_que_no_se_pudo_medir_lo_dice_el_texto_breve(self):
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        sucia = s.img.copy()
        sucia[:, :, 2][o.pelicula & (o.dcam > 4.0)] = 3
        p = piso(A2._a_pelicula(sucia), s.campo, _P(**ABIERTO))                                   # con el rango de fabrica el rojo en 3 es «no medible» en las cuatro esquinas
        assert p.estado == "ok" and _pel().texto_breve_del_piso(p, "R") == "Piso (capa roja): " + p.capas["R"].estado and p.capas["R"].estado.startswith("no medible")
        assert piso(A2._a_pelicula(sucia), s.campo).estado.startswith(_pel().MOTIVO_ESQUINAS_SIN_PISO)

    def test_j_todos_los_motivos_empiezan_con_no_medible_y_los_de_la_referencia_con_no_valida(self):
        pel = _pel()
        for nombre in ("MOTIVO_ESQUINAS_SIN_PELICULA", "MOTIVO_ESQUINAS_SIN_PISO", "MOTIVO_PISO_FUERA_DEL_RANGO", "MOTIVO_PUNTO_FUERA_DEL_RANGO", "MOTIVO_SIN_REFERENCIA_VIRGEN",
                       "MOTIVO_REFERENCIA_VIRGEN_NO_VALIDA", "MOTIVO_VIRGEN_OTRA_CADENA", "MOTIVO_VIRGEN_MAS_OSCURA"):
            assert getattr(pel, nombre).startswith("no medible: "), nombre
        assert pel.PREFIJO_NO_VALIDA == "no válida: "
        assert pel.MOTIVO_ESQUINAS_SIN_PELICULA == "no medible: la película no sobresale lo bastante del campo luminoso en sus esquinas"
        assert pel.MOTIVO_ESQUINAS_SIN_PISO == "no medible: dos o más esquinas de la película no dan un piso válido"
        assert pel.MOTIVO_PISO_FUERA_DEL_RANGO == "no medible: el piso está fuera del rango esperado de la película de fuera del campo"
        assert pel.MOTIVO_PUNTO_FUERA_DEL_RANGO == "no medible: el punto marcado no tiene el nivel de una película sin irradiar"
        assert pel.MOTIVO_SIN_REFERENCIA_VIRGEN == "no medible: no hay película virgen de referencia"
        assert pel.MOTIVO_REFERENCIA_VIRGEN_NO_VALIDA == "no medible: la película virgen de referencia no es válida"
        assert pel.MOTIVO_VIRGEN_OTRA_CADENA == "no medible: la película virgen se escaneó con otra cadena de captura"
        assert pel.MOTIVO_VIRGEN_MAS_OSCURA == "no medible: la película virgen es más oscura que la película de fuera del campo"

    def test_j_el_punto_marcado_fuera_del_rango_de_una_pelicula_sin_irradiar_es_no_medible(self):
        """El sexto clic va sobre un trozo SIN IRRADIAR: el rango es el de la virgen ([65, 130] en el azul). Un trozo de papel gris de 160 no lo es."""
        s, pel = A2.TestElSextoClic._con_un_trozo_sin_irradiar()
        sucia = np.array(s.img).copy()
        sucia[A2.PARCHE] = 160
        p = piso(A2._a_pelicula(sucia), s.campo, punto=A2.PUNTO_DEL_PARCHE)
        assert p.estado.startswith(_pel().MOTIVO_PUNTO_FUERA_DEL_RANGO) and "azul 160 fuera de [65, 130]" in p.estado, p.estado
        assert p.origen == "manual" and p.region is None
        ok = piso(pel, s.campo, punto=A2.PUNTO_DEL_PARCHE)
        assert ok.estado == "ok" and ok.punto == A2.PUNTO_DEL_PARCHE
        abierto = piso(A2._a_pelicula(sucia), s.campo, _P(piso_esperado_sin_irradiar={**PISO_ESPERADO_SIN_IRRADIAR, "B": [65.0, 200.0]}), punto=A2.PUNTO_DEL_PARCHE)
        assert abierto.estado == "ok"

    def test_j_el_rango_del_punto_va_antes_que_la_meseta(self):
        """Un trozo de papel gris (no es pelicula sin irradiar) con el campo fuera de la imagen: sin campo sobre la pelicula no hay meseta, pero lo que el fisico tiene que saber primero es que el
        punto no es una pelicula sin irradiar (el rango); la falta de meseta se dice despues, cuando el punto sirve. El control: con el trozo sano y el mismo campo, el motivo es la meseta."""
        s, pel = A2.TestElSextoClic._con_un_trozo_sin_irradiar()
        sucia = np.array(s.img).copy()
        sucia[A2.PARCHE] = 160
        lejos = [(x + 20000.0, y) for x, y in s.campo]
        con_papel = piso(A2._a_pelicula(sucia), lejos, punto=A2.PUNTO_DEL_PARCHE)
        assert con_papel.estado.startswith(_pel().MOTIVO_PUNTO_FUERA_DEL_RANGO) and "azul 160" in con_papel.estado, con_papel.estado
        sano = piso(pel, lejos, punto=A2.PUNTO_DEL_PARCHE)
        assert sano.estado == _pel().MOTIVO_SIN_MESETA, "el control: sin campo sobre la pelicula y con el punto sano, el motivo es la meseta"

    def test_j_ningun_texto_lleva_simbolos_de_correcto_o_incorrecto(self):
        """DA-18: ni marcas de verificacion, ni equis, ni advertencias, ni emojis, ni el signo menos tipografico (U+2212)."""
        pel = _pel()
        s = A2._sint("B", 0.4)
        textos = [getattr(pel, n) for n in dir(pel) if n.startswith("MOTIVO_")] + [pel.PREFIJO_NO_VALIDA]
        base = _base()[0]
        casos = [piso(s.pelicula, s.campo), piso(s.pelicula, s.campo, punto=(0.0, 0.0)), piso(s.pelicula, s.campo, modo="virgen"), piso(s.pelicula, s.campo, modo="virgen", referencia=base),
                 piso(A2._sint("A", 1.0).pelicula, A2._sint("A", 1.0).campo), piso(A2._con_fondo("B", 0.4, 150).pelicula, A2._con_fondo("B", 0.4, 150).campo),
                 piso(s.pelicula, s.campo, modo="virgen", referencia=_otra_virgen()[0])]
        for p in casos:
            textos += [p.estado, p.descripcion(), pel.texto_breve_del_piso(p), pel.texto_de_la_comparacion(p)] + [c.estado for c in p.capas.values()] + list(p.avisos)
            for e in p.esquinas:
                textos += [e.motivo, e.origen] + [i.motivo for i in e.respaldos] + [i.nombre for i in e.respaldos]
        malas = [_medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 300)), _medir_virgen(gen.codificar(_virgen_arreglo("A"), "tiff", 96)), base]
        for r in malas:
            textos += [r.estado, r.descripcion()] + [p.texto for p in r.pruebas] + list(r.avisos)
        textos += [v["motivo"] for v in pel.PARAMETROS_DEL_PISO.values()] + [v["unidad"] for v in pel.PARAMETROS_DEL_PISO.values()]
        textos += [v["motivo"] for v in pel.PARAMETROS_DE_LA_VIRGEN.values()] + [v["unidad"] for v in pel.PARAMETROS_DE_LA_VIRGEN.values()]
        assert len([t for t in textos if t]) > 100
        for t in textos:
            assert all(ord(ch) < 0x2190 for ch in t), f"simbolo en: {t}"


# ====================================================================================================================== (k) la estructura y los parametros

def _fuente(ruta):
    texto = (RAIZ / ruta).read_text(encoding="utf-8")
    return texto, ast.parse(texto)


class TestLosParametrosVivenConNombreUnidadYMotivo:
    def test_k_los_parametros_del_piso_son_los_del_diseno_con_nombre_unidad_y_motivo(self):
        pel = _pel()
        assert set(pel.PARAMETROS_DEL_PISO) == set(PLAN_DEL_PISO) and set(pel.VALORES_DEL_PISO) == set(PLAN_DEL_PISO)
        for nombre, esperado in PLAN_DEL_PISO.items():
            p = pel.PARAMETROS_DEL_PISO[nombre]
            assert p["valor"] == esperado and pel.VALORES_DEL_PISO[nombre] == esperado, f"{nombre}: {p['valor']} en vez de {esperado}"
            assert p["unidad"].strip() and len(p["motivo"]) > 20, f"{nombre} no trae unidad y motivo"
        assert PLAN_DEL_PISO["margen_borde_mm"] == 1.0, "A.2 tenia 0.5: el fleco del corte llega a 1 mm"

    def test_k_los_parametros_de_la_virgen_son_los_del_diseno_con_nombre_unidad_y_motivo(self):
        pel = _pel()
        assert set(pel.PARAMETROS_DE_LA_VIRGEN) == set(PLAN_DE_LA_VIRGEN) and set(pel.VALORES_DE_LA_VIRGEN) == set(PLAN_DE_LA_VIRGEN)
        for nombre, esperado in PLAN_DE_LA_VIRGEN.items():
            p = pel.PARAMETROS_DE_LA_VIRGEN[nombre]
            assert p["valor"] == esperado and pel.VALORES_DE_LA_VIRGEN[nombre] == esperado, nombre
            assert p["unidad"].strip() and len(p["motivo"]) > 20, f"{nombre} no trae unidad y motivo"
            assert "propuesta" in p["motivo"].lower() or nombre in ("distancia_fondo_mm", "borde_imagen_fondo_mm", "pixeles_fondo_minimos", "fondo_blanco_minimo", "dilatacion_tinta_y_motas_mm",
                                                                    "ventana_motas_mm", "ventana_ruido_mm", "ventana_rayas_mm", "motas_pixeles_grupo", "lado_bloque_virgen_mm"), \
                f"{nombre}: un umbral sin virgen real detras debe decir que es una propuesta"

    def test_k_los_valores_son_json_y_cada_piso_lleva_su_propia_copia(self):
        pel = _pel()
        for diccionario in (pel.VALORES_DEL_PISO, pel.VALORES_DE_LA_VIRGEN):
            assert json.loads(json.dumps(diccionario)) == diccionario, "un parametro con tupla o con numpy no viaja como JSON"
        s = A2._sint("B", 0.4)
        p = piso(s.pelicula, s.campo)
        assert {k: p.parametros[k] for k in PLAN_DEL_PISO} == PLAN_DEL_PISO and json.loads(json.dumps(p.parametros)) == p.parametros
        p.parametros["piso_esperado"]["R"][0] = -1.0
        assert pel.VALORES_DEL_PISO["piso_esperado"]["R"][0] == 60.0 and piso(s.pelicula, s.campo).parametros["piso_esperado"]["R"][0] == 60.0, "los parametros de un piso son una copia"
        ref = _base()[0]
        assert {k: ref.parametros[k] for k in PLAN_DE_LA_VIRGEN} == PLAN_DE_LA_VIRGEN

    def test_k_un_P_con_tuplas_se_guarda_como_listas(self):
        s = A2._sint("B", 0.4)
        p = piso(s.pelicula, s.campo, _P(piso_esperado={"R": (60.0, 140.0), "G": (145.0, 200.0), "B": (65.0, 100.0), "gris": (110.0, 170.0)}, s_respaldo=(0.05, 0.10)))
        assert p.parametros["piso_esperado"]["R"] == [60.0, 140.0] and p.parametros["s_respaldo"] == [0.05, 0.1] and json.loads(json.dumps(p.como_dict())) == p.como_dict()

    @pytest.mark.parametrize("nombre,valor", [("iqr_maximo", 0.5), ("piso_esperado", {"R": [0.0, 1.0], "G": [0.0, 1.0], "B": [0.0, 1.0], "gris": [0.0, 1.0]}), ("margen_campo_mm", 200.0),
                                                ("pixeles_minimos", 10 ** 7), ("fraccion_lejana", 1.0)])
    def test_k_cada_parametro_nuevo_o_viejo_del_automatico_cambia_el_resultado(self, nombre, valor):
        s = A2._sint("B", 0.4)
        base = piso(s.pelicula, s.campo)
        p = piso(s.pelicula, s.campo, _P(**{nombre: valor}))
        assert p.parametros[nombre] == valor
        if nombre == "fraccion_lejana":
            assert p.estado == "ok" and p.region.n > 2 * base.region.n and p.region.distancia_media_mm < base.region.distancia_media_mm - 1.0
        else:
            assert p.estado.startswith("no medible") and base.estado == "ok"

    def test_k_cada_parametro_actua_donde_dice_su_motivo(self):
        """No basta que un parametro cambie el resultado: tiene que cambiarlo POR SU RAZON, en el lugar donde actua. `margen_campo_mm` fija lo elegible de cada cuña (con 200 mm no hay nada elegible
        y se dice antes de mirar ninguna esquina); `piso_esperado` y `iqr_maximo` son la comprobacion de CADA esquina (cada una dice por que falla) y `pixeles_minimos` es lo que cada esquina
        necesita: el recorte con 2000 pixeles justos en cada una sirve con 2500 (la cuña tiene mas) y deja de servir con 4000 (ninguna tiene tanto)."""
        pel = _pel()
        s = A2._sint("B", 0.4)
        lejos = piso(s.pelicula, s.campo, _P(margen_campo_mm=200.0))
        assert lejos.estado == pel.MOTIVO_SIN_PISO and [e.estado for e in lejos.esquinas] == ["sin comprobar"] * 4 and all(e.n == 0 for e in lejos.esquinas), lejos.estado
        cerrado = piso(s.pelicula, s.campo, _P(piso_esperado={c: [0.0, 1.0] for c in CAPAS}))
        assert cerrado.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PISO) and all(e.estado == "falla" and e.motivo.startswith("fuera del rango esperado") for e in cerrado.esquinas)
        disperso = piso(s.pelicula, s.campo, _P(iqr_maximo=0.5))
        assert disperso.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PISO) and all(e.estado == "falla" and e.motivo.startswith("dispersa") for e in disperso.esquinas)
        justo, campo = A2.TestSinMargenNuncaUnNumero._recortada_con_margen_mm(6.0)
        assert piso(justo, campo).estado == "ok" and [e.n for e in piso(justo, campo).esquinas] == [2000] * 4
        assert [e.n for e in piso(justo, campo, _P(pixeles_minimos=2500)).esquinas] == [2500] * 4
        mas = piso(justo, campo, _P(pixeles_minimos=4000))
        assert mas.estado.startswith(pel.MOTIVO_ESQUINAS_SIN_PELICULA) and all(e.estado == "falla" and e.motivo.startswith("sin película suficiente") for e in mas.esquinas), mas.estado

    def test_k_la_fraccion_lejana_se_aplica_por_cuna_y_no_a_toda_la_pelicula(self):
        s = A2._sint("B", 0.4)
        o = _oraculo(s)
        todo = piso(s.pelicula, s.campo, _P(fraccion_lejana=1.0))
        assert todo.estado == "ok" and abs(todo.region.n - int(sum(o.n_cuna.values()))) <= 0.02 * todo.region.n, (todo.region.n, o.n_cuna)

    def test_k_los_parametros_del_respaldo_y_de_la_virgen_que_no_se_probaron_arriba_se_usan(self):
        s = A2._sint("B", 0.4)
        # el piso esperado del sexto clic
        cerca = piso(s.pelicula, s.campo, _P(piso_esperado_sin_irradiar={c: [0.0, 1.0] for c in CAPAS}), punto=_punto_sobre_la_pelicula(s))
        assert cerca.estado.startswith(_pel().MOTIVO_PUNTO_FUERA_DEL_RANGO)
        # la virgen: el lado del bloque y la ventana de las motas y del ruido cambian el resultado registrado
        datos = _base()[1]
        for nombre, valor in (("lado_bloque_virgen_mm", 10.0), ("ventana_motas_mm", 2.1), ("ventana_ruido_mm", 1.1), ("ventana_rayas_mm", 3.0), ("margen_borde_virgen_mm", 3.0),
                              ("dilatacion_tinta_y_motas_mm", 1.0)):
            ref = _medir_virgen(datos, P=_P(**{nombre: valor}))
            assert ref.parametros[nombre] == valor
        mayor = _medir_virgen(datos, P=_P(margen_borde_virgen_mm=3.0))
        assert mayor.region["area_mm2"] < _base()[0].region["area_mm2"], "el margen de la ROI de la virgen se usa"
        solo_aviso = _medir_virgen(datos, P=_P(ruido_aviso={"R": 0.1, "G": 0.1, "B": 0.1}))
        assert _resultados(solo_aviso)["C7 ruido"] == "aviso" and _resultados(_base()[0])["C7 ruido"] == "ok"
        assert _resultados(_medir_virgen(datos, P=_P(azul_testigo=[0.0, 10.0])))["azul testigo"] == "aviso"


class TestEstructura:
    def test_k_una_sola_definicion_de_cada_funcion_nueva_en_todo_el_arbol_de_produccion(self):
        buscadas = {"piso_de_pelicula", "piso_de_pelicula_virgen", "guardar_referencia_virgen", "leer_referencia_virgen", "referencia_virgen_desde_dict", "texto_breve_del_piso",
                    "texto_de_la_comparacion"}
        definiciones = []
        for ruta in RAIZ.rglob("*.py"):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in {"build", "dist", "tests", "__pycache__", ".venv"} or any(p.startswith(".") for p in partes):
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            definiciones += [(str(ruta.relative_to(RAIZ)).replace(os.sep, "/"), n.name) for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name in buscadas]
        assert sorted(definiciones) == sorted(("analisisImagenes/pelicula.py", n) for n in buscadas), definiciones

    def test_k_pelicula_py_sigue_sin_qt_ni_base_de_datos_ni_servicios(self):
        _, arbol = _fuente("analisisImagenes/pelicula.py")
        importados = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                importados |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                importados.add(n.module.split(".")[0])
        assert not importados & {"PyQt5", "PySide2", "sqlite3", "services", "data", "ui", "models"}, importados

    def test_k_el_motor_de_braqui_no_usa_el_piso_ni_la_virgen(self):
        texto, _ = _fuente("analisisImagenes/posicion_inicial_braqui.py")
        assert "piso_de_pelicula" not in texto and "referencia_virgen" not in texto

    def test_k_ningun_codigo_de_produccion_consume_todavia_el_piso(self):
        """Lo consumen C.2 y E.1: A.3 no cambia pantallas, PDF ni base. Fuera de `pelicula.py`, solo nombran las funciones nuevas el motor mensual y la ventana del analisis mensual.

        EDITADA EN C.2 (17-10-2026, clase b: fijaba el contrato de «nadie lo consume todavia»; el nombre de la prueba es el de A.3 y se conserva para no perder su identidad en el inventario): el consumo que A.3
        anticipaba llego con `placa_mensual.analizar` (el motor mensual), que llama UNA vez a `piso_de_pelicula`. Ese era el UNICO archivo de produccion, fuera de `pelicula.py`, que nombraba alguna de
        estas funciones, y solo nombraba `piso_de_pelicula`: la pelicula virgen, su persistencia y el modo por omision los consumirian la ventana (E.1) y el guardado (D.1).

        EDITADA EN E.1 (21-10-2026, clase b: fijaba el contrato de «solo el motor mensual lo consume»; la identidad de la prueba se conserva por la misma razon): el consumo que C.2 anticipaba llego con la
        ventana del analisis mensual (`VentanaPlacaMensual`), que elige el modo del piso (`MODO_DEL_PISO_POR_OMISION`), mide la pelicula virgen (`piso_de_pelicula_virgen`) y la guarda y la lee junto a la
        base (`guardar_referencia_virgen`, `leer_referencia_virgen`). Hoy los UNICOS archivos de produccion, fuera de `pelicula.py`, que nombran alguna de estas funciones son el motor mensual (solo
        `piso_de_pelicula`) y esa ventana (las cinco); el servicio del guardado (D.1) recibe la referencia por argumento y no las nombra, y el modulo de dibujo tampoco. Un consumidor nuevo sigue haciendo
        caer la prueba."""
        nombres = ("piso_de_pelicula", "piso_de_pelicula_virgen", "guardar_referencia_virgen", "leer_referencia_virgen", "MODO_DEL_PISO_POR_OMISION")
        usan = {}
        for ruta in RAIZ.rglob("*.py"):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in {"build", "dist", "tests", "__pycache__", ".venv"} or any(p.startswith(".") for p in partes) or partes[-1] == "pelicula.py":
                continue
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            hallados = [n for n in nombres if n in texto]
            if hallados:
                usan[str(ruta.relative_to(RAIZ))] = hallados
        assert usan == {"analisisImagenes/placa_mensual.py": ["piso_de_pelicula"],
                        "ui/paginasControles/PruebasMensuales/placa_mensual.py": ["piso_de_pelicula", "piso_de_pelicula_virgen", "guardar_referencia_virgen", "leer_referencia_virgen", "MODO_DEL_PISO_POR_OMISION"]}, usan

    def test_k_la_escala_sale_de_escala_mm_y_ninguna_funcion_nueva_divide_25_4(self):
        _, arbol = _fuente("analisisImagenes/pelicula.py")
        for n in ast.walk(arbol):
            if isinstance(n, ast.FunctionDef) and n.name != "escala_mm":
                assert 25.4 not in [c.value for c in ast.walk(n) if isinstance(c, ast.Constant) and isinstance(c.value, float)], f"{n.name} divide 25.4"
        for nombre in ("piso_de_pelicula", "piso_de_pelicula_virgen"):
            f = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == nombre)
            assert "escala_mm" in {c.func.id for c in ast.walk(f) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}, nombre

    def test_k_ningun_literal_de_un_parametro_vive_en_las_funciones_del_piso_ni_de_la_virgen(self):
        """Un literal escrito en la funcion ignora el parametro que se guarda con cada analisis. Se buscan los valores bastante distintivos: los de A.2 (235, 2000, 170, 0.10) y los del
        diseño (25 niveles de tinta, 15 de IQR, 11 mm del respaldo, 0.05 y 0.20, 10 de contraste); y los de la virgen (400 mm2, 10000 pixeles, 0.995, los umbrales de recorte, 75 y 95)."""
        _, arbol = _fuente("analisisImagenes/pelicula.py")
        prohibidos = {235, 2000, 170, 0.10, 15, 11, 0.05, 0.20, 10, 0.995, 400, 10000, 0.001, 0.0001, 0.0005, 0.02, 95, 145, 140, 200, 65, 110, 60}
        funciones = [n for n in arbol.body if isinstance(n, ast.FunctionDef) and (n.name.startswith(("piso_de_pelicula", "_piso", "_region", "_virgen", "_respaldo")))]
        assert len(funciones) >= 12, [f.name for f in funciones]
        assert any(f.name == "piso_de_pelicula_virgen" for f in funciones)
        for f in funciones:
            for c in ast.walk(f):
                if isinstance(c, ast.Constant) and not isinstance(c.value, bool) and isinstance(c.value, (int, float)):
                    assert c.value not in prohibidos, f"{f.name} escribe el literal {c.value}: debe salir de los parametros"

    def test_k_pelicula_py_conserva_el_lector_y_las_funciones_de_A1_y_A2(self):
        pel = _pel()
        for nombre in ("leer_pelicula", "Pelicula", "clase_resolucion", "escala_mm", "CAPAS", "NOMBRE_DE_CAPA", "CAPA_POR_OMISION", "CapaDelPiso", "RegionDelPiso", "Piso", "piso_de_pelicula",
                       "CAPAS_DEL_PISO", "CLAVES_DE_LA_ESCALA", "MOTIVO_SIN_PISO", "MOTIVO_PISO_COMO_EL_FONDO"):
            assert hasattr(pel, nombre), nombre
        _, arbol = _fuente("analisisImagenes/pelicula.py")
        assert sum(isinstance(n, ast.FunctionDef) for n in arbol.body) >= 30


# Lo que gira una imagen (o un arreglo) en OpenCV, NumPy, SciPy o PIL: la lista del PROTOCOLO (k) de A.3 (diseño §3.3-bis; consulta del fisico del 13-10: «verifica que no sea excesiva la
# rotacion… y que esto sea solo para encontrar este valor»). El «giro de +5 y -5 grados» del respaldo es solo la DIRECCION, desde el cruce de diagonales, en que se pone la ventana de 3 x 3 mm
# (matematica de vectores con cos y sin); el piso es un numero por capa tomado sobre la imagen SIN girar. El giro de alineacion (la media con signo de las dos diagonales) lo aplica C.2 una vez.
NOMBRES_QUE_GIRAN = frozenset({"warpAffine", "warpPerspective", "getRotationMatrix2D", "rot90", "rotate"})


def _usos_de_nombres(texto):
    """El recorrido UNICO de un texto fuente: [(linea, clase, receptor, nombre)] de cada nombre que el codigo usa. `clase`: «llamada» (`cv2.blur(...)`, `np.rot90(...)`, `imagen.rotate(5)`, y la
    llamada de un nombre suelto, `rotate(x)`; `receptor` es lo que va antes del punto: «cv2», «np», «imagen»...), «atributo» (`cv2.warpAffine` sin llamarlo, o una constante como
    `cv2.IMREAD_COLOR`), «importado» (cada nombre de un `from X import a as b`: `nombre` es `a`, el nombre ORIGINAL, tenga el alias que tenga) y «cadena» (una cadena suelta, como la de
    `getattr(cv2, "warpAffine")`)."""
    arbol = ast.parse(texto)
    llamados = {id(n.func) for n in ast.walk(arbol) if isinstance(n, ast.Call)}
    usos = []
    for n in ast.walk(arbol):
        if isinstance(n, ast.Attribute):
            usos.append((n.lineno, "llamada" if id(n) in llamados else "atributo", ast.unparse(n.value), n.attr))
        elif isinstance(n, ast.Name) and id(n) in llamados:
            usos.append((n.lineno, "llamada", None, n.id))
        elif isinstance(n, ast.ImportFrom):
            usos += [(n.lineno, "importado", n.module, a.name) for a in n.names]
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            usos.append((n.lineno, "cadena", None, n.value))
    return usos


def _giros_en(texto):
    """UNA sola funcion que dice que hay en un texto fuente que gire la imagen: [(linea, clase, receptor, nombre)] de todo uso de un nombre de NOMBRES_QUE_GIRAN, por el ULTIMO nombre de cada
    llamada (con cualquier receptor o alias: `cv2.warpAffine`, `c.warpAffine`, `np.rot90`, `numpy.rot90`, `imagen.rotate(5)`, `ndimage.rotate`) y por los nombres IMPORTADOS (`from cv2 import
    warpAffine as torcer`: el original, se llame o no), mas la referencia sin llamarla y la cadena exacta. La usan la prueba sobre `pelicula.py` y los casos sinteticos."""
    return [u for u in _usos_de_nombres(texto) if u[3] in NOMBRES_QUE_GIRAN]


def _llamadas_a_cv2_por_tokens(texto):
    """OTRA forma de encontrar las llamadas `cv2.nombre(` de un texto, sin AST: por tokens (NAME `cv2`, OP `.`, NAME, OP `(`), que no miran comentarios ni cadenas."""
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(texto).readline) if t.type in (tokenize.NAME, tokenize.OP)]
    return {c.string for a, b, c, d in zip(tokens, tokens[1:], tokens[2:], tokens[3:]) if a.string == "cv2" and b.string == "." and c.type == tokenize.NAME and d.string == "("}


CASOS_QUE_GIRAN = [
    ("cv2.warpAffine", "import cv2\nimport numpy as np\ngirada = cv2.warpAffine(imagen, np.eye(2, 3, dtype=np.float32), (3, 3))\n", {"warpAffine"}),
    ("cv2.getRotationMatrix2D", "import cv2\nm = cv2.getRotationMatrix2D((0, 0), 5.0, 1.0)\n", {"getRotationMatrix2D"}),
    ("cv2.warpAffine con su matriz de giro", "import cv2\ny = cv2.warpAffine(imagen, cv2.getRotationMatrix2D((0, 0), -5.0, 1.0), (3, 3))\n", {"warpAffine", "getRotationMatrix2D"}),
    ("cv2.warpPerspective", "import cv2\ny = cv2.warpPerspective(imagen, matriz, (3, 3))\n", {"warpPerspective"}),
    ("np.rot90", "import numpy as np\ny = np.rot90(imagen)\n", {"rot90"}),
    ("numpy.rot90", "import numpy\ny = numpy.rot90(imagen, 2)\n", {"rot90"}),
    ("cv2 con otro alias", "import cv2 as c\ny = c.warpAffine(imagen, m, (3, 3))\n", {"warpAffine"}),
    ("numpy con otro alias", "import numpy as xp\ny = xp.rot90(imagen)\n", {"rot90"}),
    ("from cv2 import warpAffine", "from cv2 import warpAffine\n", {"warpAffine"}),
    ("from cv2 import warpAffine as otro_nombre, llamada con el alias", "from cv2 import warpAffine as torcer\ny = torcer(imagen, m, (3, 3))\n", {"warpAffine"}),
    ("from numpy import rot90 as otro_nombre", "from numpy import rot90 as r\n", {"rot90"}),
    ("imagen.rotate(5)", "y = imagen.rotate(5)\n", {"rotate"}),
    ("scipy.ndimage.rotate", "from scipy import ndimage\ny = ndimage.rotate(imagen, 5)\n", {"rotate"}),
    ("cv2.rotate", "import cv2\ny = cv2.rotate(imagen, cv2.ROTATE_90_CLOCKWISE)\n", {"rotate"}),
    ("una funcion suelta que se llama rotate", "def rotate(x):\n    return x\n\n\ny = rotate(imagen)\n", {"rotate"}),
    ("la funcion nombrada sin llamarla", "import cv2\nf = cv2.warpAffine\n", {"warpAffine"}),
    ("getattr con el nombre en una cadena", "import cv2\ny = getattr(cv2, 'warpAffine')(imagen, m, (3, 3))\n", {"warpAffine"}),
    ("dentro de una funcion que nadie llama", "import cv2\n\n\ndef _nunca(x):\n    if False:\n        return cv2.warpAffine(x, m, (3, 3))\n", {"warpAffine"}),
]
CASOS_LIMPIOS = [
    ("lo que usa pelicula.py: filtros, morfologia y vectores", "import cv2\nimport numpy as np\ny = cv2.blur(x, (3, 3))\nz = cv2.distanceTransform(m, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)\n"
                                                              "angulo = np.radians(5.0)\nu = np.array([np.cos(angulo), np.sin(angulo)])\n"),
    ("una funcion que gira un VECTOR (la direccion del respaldo)", "import numpy as np\n\n\ndef _girar_direccion(u, grados):\n    g = np.radians(grados)\n"
                                                                    "    return np.array([u[0] * np.cos(g) - u[1] * np.sin(g), u[0] * np.sin(g) + u[1] * np.cos(g)])\n"),
    ("los nombres en un comentario y en un texto", '"""No llama a cv2.warpAffine ni a np.rot90: no gira la imagen."""\n# imagen.rotate(5) no se usa\nx = "la ventana girada +5 grados"\n'),
    ("nombres que se parecen", "rotacion = 5\ny = obj.rotation + obj.rot90_no + obj.rotated\n"),
]


class TestElPisoSeTomaSobreLaImagenSinGirar:
    """PROTOCOLO (k) de A.3, consulta del fisico del 13-10: nada del piso gira la imagen. Una sola funcion revisa un texto fuente (`_giros_en`) y la usan la prueba sobre `pelicula.py` y los casos
    sinteticos que la hacen caer; los limpios no marcan y el recorrido se comprueba contra otra forma de encontrar las llamadas, para que la prueba no pase en vacio."""

    def test_k_pelicula_py_no_gira_la_imagen(self):
        texto, _ = _fuente("analisisImagenes/pelicula.py")
        giros = _giros_en(texto)
        assert giros == [], (f"pelicula.py gira la imagen o importa algo que la gira: {giros}. El piso se toma sobre la imagen SIN girar; el «giro de +5 y -5 grados» del respaldo es solo la "
                             "direccion, desde el cruce de diagonales, en que se pone la ventana de 3 x 3 mm (vectores, no pixeles).")

    @pytest.mark.parametrize("fuente,nombres", [(c[1], c[2]) for c in CASOS_QUE_GIRAN], ids=[c[0] for c in CASOS_QUE_GIRAN])
    def test_k_el_revisor_marca_cada_forma_de_girar(self, fuente, nombres):
        marcas = _giros_en(fuente)
        assert marcas and {m[3] for m in marcas} == nombres, marcas

    @pytest.mark.parametrize("fuente", [c[1] for c in CASOS_LIMPIOS], ids=[c[0] for c in CASOS_LIMPIOS])
    def test_k_el_revisor_no_marca_lo_que_no_gira(self, fuente):
        assert _giros_en(fuente) == []
        assert _usos_de_nombres(fuente), "el recorrido no vio nada en un texto que tiene llamadas: la prueba pasaria en vacio"

    def test_k_el_recorrido_ve_las_llamadas_a_cv2_de_pelicula_py(self):
        """Una revision que no ve nada pasa en vacio. El recorrido por AST tiene que ver EXACTAMENTE las llamadas `cv2.nombre(` que el texto de `pelicula.py` trae, buscadas con otro metodo (los
        tokens, que no miran comentarios ni cadenas); y los dos metodos se comprueban primero sobre un texto chico."""
        chico = "import cv2\ny = cv2.blur(x, (3, 3))\n# cv2.dilate(m)\nz = 'cv2.erode(m)'\nw = cv2.IMREAD_COLOR\n"
        assert _llamadas_a_cv2_por_tokens(chico) == {"blur"}
        assert {nombre for _, clase, receptor, nombre in _usos_de_nombres(chico) if clase == "llamada" and receptor == "cv2"} == {"blur"}
        texto, _ = _fuente("analisisImagenes/pelicula.py")
        por_tokens = _llamadas_a_cv2_por_tokens(texto)
        vistas = {nombre for _, clase, receptor, nombre in _usos_de_nombres(texto) if clase == "llamada" and receptor == "cv2"}
        assert len(por_tokens) >= 5 and {"imdecode", "distanceTransform"} <= por_tokens, por_tokens
        assert vistas == por_tokens, sorted(vistas ^ por_tokens)


# ====================================================================================================================== (l) memoria y tiempo

class TestLaMemoriaYElTiempo:
    def test_l_una_pagina_completa_no_pide_mas_de_350_MB_sobre_las_capas_y_tarda_menos_de_3_s(self):
        pel = A2._real("EPSON027")
        for c in ("R", "G", "B", "gris"):
            getattr(pel, c)
        pel.validos
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            t0 = time.perf_counter()
            p = piso(pel, CLICS_REALES["EPSON027"])
            tiempo = time.perf_counter() - t0
            pico = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert p.estado == "ok"
        assert pico < 350e6, f"el piso por esquinas de una pagina completa pidio {pico / 1e6:.0f} MB sobre las capas"
        assert tiempo < 3.0, f"el piso por esquinas de una pagina completa tardo {tiempo:.1f} s"

    def test_l_la_virgen_de_una_pagina_completa_cabe_en_la_memoria(self):
        datos = gen.codificar(_virgen_arreglo("B"), "tiff", 600)
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            t0 = time.perf_counter()
            ref = _medir_virgen(datos)
            tiempo = time.perf_counter() - t0
            pico = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert ref.estado == "ok"
        assert pico < 800e6, f"la virgen de una pagina de 3300 x 3300 pidio {pico / 1e6:.0f} MB (medido: 501 MB)"
        assert tiempo < 15.0, f"la virgen tardo {tiempo:.1f} s (medido: 2 s)"


# ====================================================================================================================== (m) la ranura de la virgen real

class TestLaRanuraDeLaVirgenReal:
    def test_m_si_hay_una_virgen_real_se_mide_y_si_no_la_ranura_esta_documentada(self):
        """Cuando el fisico deje en `ImagenesDeReferencia/PlacasHistoricas` un escaneo `VIRGEN*.tif|TIF|jpg|JPG|jpeg|png`, cada uno se mide y debe dar «ok» dentro de
        `piso_esperado_sin_irradiar` (e imprime sus cifras: si falla, son los umbrales [propuesta] los que hay que recalibrar, diseño §12). Si no hay ninguno, la prueba PASA comprobando solo
        que la ranura esta documentada: nunca `pytest.skip` ni un `parametrize` vacio (el conteo de skips de la suite es EXACTAMENTE 4). No se declara en `_corpus.PELICULAS_*`: la regla de PR.0
        exigiria que existiera."""
        raiz = Path(_corpus.PELICULAS_RAIZ)
        archivos = []
        if raiz.is_dir():
            for patron in ("VIRGEN*.tif", "VIRGEN*.TIF", "VIRGEN*.tiff", "VIRGEN*.jpg", "VIRGEN*.JPG", "VIRGEN*.jpeg", "VIRGEN*.png", "VIRGEN*.PNG"):
                archivos += sorted(raiz.glob(patron))
        malas = []
        for ruta in sorted(set(archivos)):
            ref = _pel().piso_de_pelicula_virgen(ruta.read_bytes(), _P(), ruta.name)
            print(f"VIRGEN REAL {ruta.name}: {ref.estado}; " + ", ".join(f"{c} {ref.valor(c)}" for c in CAPAS) + "; avisos: " + "; ".join(ref.avisos))
            if ref.estado != "ok":
                malas.append((ruta.name, ref.estado))
            else:
                rango = PISO_ESPERADO_SIN_IRRADIAR
                assert all(rango[c][0] <= ref.valor(c) <= rango[c][1] for c in CAPAS), (ruta.name, _valores(ref))
        assert not malas, f"una virgen real no paso las comprobaciones (recalibrar los umbrales [propuesta]): {malas}"
        if not archivos:
            texto, _ = _fuente("analisisImagenes/pelicula.py")
            assert "VIRGEN" in (RAIZ / "tests" / Path(__file__).name).read_text(encoding="utf-8") and "recalibr" in texto.lower(), "la ranura no esta documentada"
