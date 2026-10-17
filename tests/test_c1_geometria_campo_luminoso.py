"""C.1 (PLAN_ANALISIS_PELICULAS_08-10.md): el MOTOR MENSUAL (1/3) -- la geometria del campo luminoso desde los cinco puntos (`analisisImagenes/placa_mensual.py`, version PM-1).

CAUSA (R2, R3: N2, N7, N10, celda 91; A3, A5). El cuaderno del fisico clasifica los puntos con el centro de la imagen y con `shape[0]`/`shape[1]` cruzados, gira con la MAYOR de las diagonales
(0.463 grados en ML0; la media da 0.403) y mide los lados por proyeccion; la app original no gira; ninguno da angulos interiores ni diagonales ni refina el clic (el del reticulo de ML0 quedo
a 10 pixeles de su marca).

LO QUE SE GARANTIZA (a-f del PROTOCOLO del plan), cada cosa contra una verdad que NO sale de las funciones:
  (a) ML0 (los clics del cuaderno) SIN refinar reproduce R2: 0.403 grados; angulos interiores 90.515 / 89.708 / 89.879 / 89.898; lados 99.314 / 99.699 / 98.939 / 99.655 mm; reticulo - luz 0.698 / 0.616 mm
      en el marco sin girar (y 0.7018 / 0.6112 en el girado, con cualquier pivote); con los clics refinados los numeros son otros (0.367 grados, 0.46 / 0.28 mm) y quedan FIJADOS aqui: refinar mueve
      los numeros de ML0 mas que su tolerancia (P10; es un hecho a informar, no un defecto). La pagina entera (EPSON027) y el recorte (ML0) dan lo mismo.
  (b) cuadrilateros de verdad conocida (rectangulos de varias proporciones, un trapecio, un paralelogramo y los de las peliculas sinteticas de PF.0) girados 0, 0.4, 1 y -3 grados: <= 0.005 grados y
      <= 0.005 mm, y la verdad se calcula con otro algoritmo (numeros complejos y formulas cerradas); de punta a punta (clic -> refinar -> clasificar -> geometria) sobre las sinteticas de 600 dpi.
  (c) las 120 permutaciones de los cinco clics dan EXACTAMENTE lo mismo, tambien con la pelicula a 800 px del centro de la imagen donde el cuaderno ni clasifica.
  (d) un clic a 1 mm o menos del centro de una marca sintetica vuelve a el (<= 0.05 mm; en la practica <= 0.003 mm a 600 dpi); sin marca, con una mancha a mas de 1.5 mm, con una mancha que no es
      tinta (clara, tenue, chica, cortada por el borde) el clic queda «sin refinar».
  (e) el pivote del giro no cambia ninguna medida (R2.2).
  (f) `recuadro_luminoso`: las 120 permutaciones dan el mismo recuadro; con una marca «sin refinar» usa el clic; con las refinadas, las refinadas; con puntos que no forman el campo da el motivo y
      ninguna esquina.
Y las garantias de estructura: cada parametro vive con nombre, unidad y motivo y se usa; la escala es la del procedimiento (nadie divide 25.4 aqui); un solo diccionario alimenta `refinar_marca`,
`escala_mm` y `piso_de_pelicula`; el modulo no importa Qt, ni base de datos, ni servicios, ni `cv2.imread` (la imagen entra por `leer_pelicula`); `refinar_marca` trabaja sobre un recorte (una pagina de
6600 x 5100 no se copia); sin simbolos de correcto o incorrecto (DA-18).

La verdad: las peliculas sinteticas de PF.0 (`tests/_placa_mensual_sintetica.py`, generador INDEPENDIENTE del motor; la verdad de sus marcas es `verdad.marcas_px`) y un ORACULO escrito aqui con numeros
complejos (`oraculo`) y formulas cerradas (rectangulo, trapecio, paralelogramo); no se repite el codigo del modulo. Las peliculas reales (ML0, EPSON027, y las demas del recuento) saltan (HI-0) si
`ImagenesDeReferencia/PlacasHistoricas` no existe y la regla de PR.0 hace fallar nombrandola si existe y falta una.

Rojo contra HEAD (89b0b7a): HEAD no tiene `analisisImagenes/placa_mensual.py`, asi que todas las pruebas caen con su error (el archivo se colecciona: cada prueba importa el modulo por dentro). El rojo
SUSTANTIVO (que las pruebas discriminan) esta en `c1_rojo_head.py` del anexo: la replica del cuaderno puesta en lugar del modulo da 0.463 grados y lados por proyeccion y hace caer (a), (b), (d), (e) y (f)
por su asercion. Las mutaciones estan en `c1_mutaciones.py`.

Ronda 1 del corrector (17-10, tras la revision esceptica): PROD-01 (unidades entre corchetes: lo vigila el tripwire D.1, `test_nav_d1_corchetes_no_parentesis`), PROD-02 (el limite de oscuridad de la tinta NO se
incluye: `test_un_nucleo_que_llega_al_limite_no_es_tinta` y las motas y la tinta reales), PROD-03 (lo que trae una geometria «no medible»: `test_la_geometria_no_medible_trae_solo_lo_que_dice_su_documentacion`),
R1P-01 (los VALORES de `como_dict()`), R1P-02 (el reticulo fuera por cada uno de los cuatro lados), R1P-03 (`GeometriaLuz.reticulo`, `.tam_mm` y el resto de los campos en `comparar`), R1P-04 (la comparacion «sin
refinar es peor»), R1P-05 (el medidor de memoria con `tracemalloc` ya encendido) y R1P-06 (el numero magico distingue 10.0 de 10). Cada una se reprodujo con un mutante que sobrevivia a las 269 pruebas de
antes; las mutaciones `RV-*` de `c1_mutaciones.py` son esos mutantes y caen por su razon.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import cmath
import dataclasses
import importlib
import itertools
import json
import math
import re
import time
import tracemalloc
from pathlib import Path

import cv2
import numpy as np
import pytest

import _corpus
import _placa_mensual_sintetica as gen

RAIZ = Path(__file__).resolve().parent.parent
MODULO = RAIZ / "analisisImagenes" / "placa_mensual.py"
ESC = 25.4 / 600.0                                     # mm por pixel: la escala del procedimiento (600 dpi)
LADOS = ("superior", "derecho", "inferior", "izquierdo")
ESQUINAS = ("UL", "UR", "DR", "DL")
CLICS_ML0 = [(196, 143), (2542, 147), (1371, 1330), (2526, 2501), (171, 2480)]          # UL, UR, C, DR, DL: los clics del cuaderno del fisico (R2)
CLICS_EPSON027 = [(206, 150), (2552, 154), (1381, 1337), (2536, 2508), (181, 2487)]     # los de ML0 mas el desplazamiento exacto (10, 7) de ML0 dentro de la pagina (medido en A.2)


def _pm():
    """El modulo, importado POR PRUEBA: en HEAD (sin `placa_mensual.py`) el archivo se colecciona y cada prueba cae con su error."""
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pelicula_mod():
    return importlib.import_module("analisisImagenes.pelicula")


def _P(**cambios):
    return {**_pm().VALORES_DE_LA_GEOMETRIA, **cambios}


def _real(clave):
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"HI-0: la pelicula real {clave} no esta (ImagenesDeReferencia/PlacasHistoricas)")
    return ruta


# ----------------------------------------------------------------------------------------------------------------------------------- el oraculo
def oraculo(esquinas, reticulo, tam, pivote=None):
    """La geometria de las cuatro `esquinas` (UL, UR, DR, DL) y el `reticulo`, calculada con NUMEROS COMPLEJOS (otro camino que las funciones del modulo, que usan pares y `atan2`): el cruce de las
    diagonales por productos cruz, los angulos con `cmath.phase`, el giro como una multiplicacion por e^(-i angulo) (el giro de OpenCV con un angulo positivo es antihorario en la pantalla)."""
    ul, ur, dr, dl = (complex(*p) for p in esquinas)
    r = complex(*reticulo)

    def cruz(a, b):
        return (a.conjugate() * b).imag

    d1, d2 = dr - ul, dl - ur
    cruce = ul + (cruz(ur - ul, d2) / cruz(d1, d2)) * d1
    principal, secundaria = math.degrees(cmath.phase(dr - ul)), math.degrees(cmath.phase(ur - dl))
    angulo = (principal + secundaria) / 2.0

    def interior(p, antes, despues):
        return math.degrees(abs(cmath.phase((antes - p) / (despues - p))))

    centro = cruce if pivote is None else complex(*pivote)
    giro = cmath.exp(-1j * math.radians(angulo))

    def girar(z):
        return centro + (z - centro) * giro

    gul, gur, gdr, gdl = (girar(z) for z in (ul, ur, dr, dl))
    v = (cruce - r) * tam
    w = v * giro
    return {
        "esquinas": [tuple(p) for p in esquinas], "reticulo": tuple(reticulo), "tam": tam,
        "cruce": (cruce.real, cruce.imag), "angulo": angulo, "angulos_diagonales": (principal, secundaria), "desviacion": (principal - 45.0, secundaria + 45.0),
        "lados": {"superior": abs(ur - ul) * tam, "derecho": abs(dr - ur) * tam, "inferior": abs(dr - dl) * tam, "izquierdo": abs(dl - ul) * tam},
        "interiores": {"UL": interior(ul, dl, ur), "UR": interior(ur, ul, dr), "DR": interior(dr, ur, dl), "DL": interior(dl, dr, ul)},
        "diagonales": (abs(dr - ul) * tam, abs(ur - dl) * tam),
        "inclinacion": {"superior": math.degrees(cmath.phase(gur - gul)), "inferior": math.degrees(cmath.phase(gdr - gdl)),
                        "izquierdo": math.degrees(cmath.phase((gdl - gul) * -1j)), "derecho": math.degrees(cmath.phase((gdr - gur) * -1j))},
        "luz_menos_reticulo_imagen": (v.real, v.imag), "luz_menos_reticulo_girado": (w.real, w.imag), "modulo": abs(v),
        "esquinas_giradas": [(z.real, z.imag) for z in (gul, gur, gdr, gdl)], "reticulo_girado": (girar(r).real, girar(r).imag),
    }


def comparar(g, o, tolerancia_deg, tolerancia_mm):
    """Compara una `GeometriaLuz` con el oraculo, campo por campo: TODOS los campos con valor del resultado (los puntos con que se midio, la escala y el marco girado tambien, no solo las medidas)."""
    assert g.estado == "ok", g.estado
    assert g.tam_mm == o["tam"]                                                              # la escala con que se midio (R1P-03: ninguna prueba la miraba)
    assert list(g.esquinas) == pytest.approx(o["esquinas"], abs=1e-9)                        # los puntos con que se midio, en el orden UL, UR, DR, DL
    assert g.reticulo == pytest.approx(o["reticulo"], abs=1e-9)                              # y el reticulo (R1P-03: `reticulo=cruce` pasaba las 269 pruebas)
    assert g.pivote == pytest.approx(o["cruce"], abs=1e-6)                                   # el pivote por omision es el cruce
    assert [c for p in g.esquinas_giradas for c in p] == pytest.approx([c for p in o["esquinas_giradas"] for c in p], abs=1e-6)
    assert g.reticulo_girado == pytest.approx(o["reticulo_girado"], abs=1e-6)
    assert g.cruce == pytest.approx(o["cruce"], abs=1e-6)
    assert g.angulo_grados == pytest.approx(o["angulo"], abs=tolerancia_deg)
    assert g.angulos_de_las_diagonales_grados == pytest.approx(o["angulos_diagonales"], abs=tolerancia_deg)
    assert g.desviacion_de_las_diagonales_grados == pytest.approx(o["desviacion"], abs=tolerancia_deg)
    for lado in LADOS:
        assert g.lados_mm[lado] == pytest.approx(o["lados"][lado], abs=tolerancia_mm), lado
        assert g.inclinacion_de_los_lados_grados[lado] == pytest.approx(o["inclinacion"][lado], abs=tolerancia_deg), lado
    for esquina in ESQUINAS:
        assert g.angulos_interiores_grados[esquina] == pytest.approx(o["interiores"][esquina], abs=tolerancia_deg), esquina
    assert g.diagonales_mm == pytest.approx(o["diagonales"], abs=tolerancia_mm)
    assert g.luz_menos_reticulo_imagen_mm == pytest.approx(o["luz_menos_reticulo_imagen"], abs=tolerancia_mm)
    assert g.luz_menos_reticulo_girado_mm == pytest.approx(o["luz_menos_reticulo_girado"], abs=tolerancia_mm)
    assert g.luz_menos_reticulo_modulo_mm == pytest.approx(o["modulo"], abs=tolerancia_mm)


def geometria(esquinas, reticulo, tam=ESC, **kw):
    return _pm().geometria_luz(esquinas, reticulo, tam, **kw)


def _par(z):
    return (z.real, z.imag)


def rectangulo(w_mm, h_mm, theta, centro=(1300.0, 1250.0), reticulo_mm=(0.0, 0.0)):
    """(esquinas UL, UR, DR, DL, reticulo) en pixeles de un rectangulo `w_mm` x `h_mm` girado `theta` grados en sentido HORARIO en la pantalla: (x + iy) e^(i theta). `reticulo_mm`: el reticulo
    respecto del centro, en el sistema del rectangulo."""
    giro = cmath.exp(1j * math.radians(theta))
    c = complex(*centro)
    w, h = w_mm / ESC, h_mm / ESC
    esq = [_par(c + giro * complex(x, y)) for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
    return esq, _par(c + giro * complex(reticulo_mm[0] / ESC, reticulo_mm[1] / ESC))


def trapecio(theta, centro=(1300.0, 1250.0), reticulo_mm=(0.0, 0.0)):
    """Un trapecio isosceles (base de arriba 80 mm, de abajo 120 mm, alto 100 mm) girado `theta`. Verdad cerrada: simetrico, asi que su angulo sin girar es 0 y el girado es `theta`."""
    giro = cmath.exp(1j * math.radians(theta))
    c = complex(*centro)
    mm = [(-40.0, -50.0), (40.0, -50.0), (60.0, 50.0), (-60.0, 50.0)]
    return [_par(c + giro * complex(x, y) / ESC) for x, y in mm], _par(c + giro * complex(*reticulo_mm) / ESC)


def paralelogramo(theta, centro=(1300.0, 1250.0), reticulo_mm=(0.0, 0.0), a=100.0, s=3.0, h=98.0):
    """Un paralelogramo (lado de arriba `a`, corrimiento `s`, alto `h`; mm) girado `theta`. Sus diagonales se cortan en su centro."""
    giro = cmath.exp(1j * math.radians(theta))
    c = complex(*centro)
    mm = [(-a / 2 - s / 2, -h / 2), (a / 2 - s / 2, -h / 2), (a / 2 + s / 2, h / 2), (-a / 2 + s / 2, h / 2)]
    return [_par(c + giro * complex(x, y) / ESC) for x, y in mm], _par(c + giro * complex(*reticulo_mm) / ESC)


GIROS = (0.0, 0.4, 1.0, -3.0)


# ---------------------------------------------------------------------------------------------------------------------------- (a) ML0, los clics
@pytest.fixture(scope="module")
def sin_refinar():
    pm = _pm()
    c = pm.clasificar_puntos(CLICS_ML0)
    return c, pm.geometria_luz(c.esquinas, c.reticulo, ESC)


class TestMl0ReproduceR2:
    """(a): con los clics de ML0 SIN refinar el modulo reproduce lo que R2 midio (el cuaderno da 0.463 grados y lados por proyeccion)."""

    def test_a_los_cinco_clics_se_clasifican_sin_importar_el_orden_del_cuaderno(self, sin_refinar):
        c, _ = sin_refinar
        assert c.estado == "ok" and c.ok
        assert c.reticulo == (1371.0, 1330.0)
        assert c.esquinas == ((196.0, 143.0), (2542.0, 147.0), (2526.0, 2501.0), (171.0, 2480.0))
        assert c.indice_del_reticulo == 2 and c.indices_de_las_esquinas == (0, 1, 3, 4)

    def test_a_el_angulo_es_el_promedio_con_signo_0_403_no_el_de_la_diagonal_mayor_0_463(self, sin_refinar):
        _, g = sin_refinar
        assert g.angulo_grados == pytest.approx(0.403, abs=5e-4)
        assert g.angulos_de_las_diagonales_grados == pytest.approx((45.342, -44.537), abs=5e-4)       # R9, paso 3: +45.342 y -44.537, promedio 0.403
        assert abs(g.angulo_grados - 0.46284) > 0.05, "es el de la diagonal MAYOR del cuaderno (celda 18), no el promedio"
        assert abs(g.angulo_grados - 44.94) > 40, "es el promedio SIN signo de las dos diagonales"

    def test_a_la_desviacion_de_cada_diagonal_es_la_de_la_celda_18_del_cuaderno(self, sin_refinar):
        _, g = sin_refinar
        assert g.desviacion_de_las_diagonales_grados == pytest.approx((0.34221, 0.46284), abs=5e-5)    # tetha_0 y -tetha_1 impresos por el cuaderno
        assert g.angulo_grados == pytest.approx(sum(g.desviacion_de_las_diagonales_grados) / 2, abs=1e-12)

    def test_a_los_angulos_interiores_son_los_de_r2(self, sin_refinar):
        _, g = sin_refinar
        assert g.angulos_interiores_grados == pytest.approx({"UL": 90.515, "UR": 89.708, "DR": 89.879, "DL": 89.898}, abs=5e-4)
        assert sum(g.angulos_interiores_grados.values()) == pytest.approx(360.0, abs=1e-9)

    def test_a_los_lados_son_euclideos_y_son_los_de_r2_no_los_de_la_proyeccion_del_cuaderno(self, sin_refinar):
        _, g = sin_refinar
        assert g.lados_mm == pytest.approx({"superior": 99.314, "inferior": 99.699, "izquierdo": 98.939, "derecho": 99.655}, abs=5e-4)
        # la proyeccion del cuaderno (celda 91, sobre los puntos girados por 0.463 grados) da otros: 99.314 / 99.737 / 98.975 / 99.695 (derecho e izquierdo +0.04 mm)
        assert abs(g.lados_mm["izquierdo"] - 98.975) > 0.03 and abs(g.lados_mm["derecho"] - 99.695) > 0.03

    def test_a_las_diagonales_son_las_de_r2_y_no_son_iguales(self, sin_refinar):
        _, g = sin_refinar
        assert g.diagonales_mm == pytest.approx((140.334, 140.815), abs=5e-4)
        assert g.diagonales_mm[0] != pytest.approx(g.diagonales_mm[1], abs=0.1)

    def test_a_luz_menos_reticulo_en_la_imagen_y_en_el_marco_girado(self, sin_refinar):
        _, g = sin_refinar
        # el plan lo da como «reticulo - luz 0.698 / 0.616 en el marco sin girar»: es el MISMO numero con el signo contrario
        assert g.luz_menos_reticulo_imagen_mm == pytest.approx((-0.698, -0.616), abs=5e-4)
        assert g.luz_menos_reticulo_girado_mm == pytest.approx((-0.7018, -0.6112), abs=5e-4)          # R2.2
        assert g.luz_menos_reticulo_modulo_mm == pytest.approx(math.hypot(0.698, 0.616), abs=5e-4)
        assert g.cruce == pytest.approx((1354.523, 1315.445), abs=5e-4)

    def test_a_las_inclinaciones_de_los_lados_en_el_marco_girado(self, sin_refinar):
        _, g = sin_refinar
        # el lado superior, antes de girar, esta a atan2(4, 2346) = 0.0977 grados; girado 0.4025 queda a -0.3048 (positivo = horario, como el angulo)
        assert g.inclinacion_de_los_lados_grados["superior"] == pytest.approx(-0.3048, abs=5e-4)
        assert g.inclinacion_de_los_lados_grados == pytest.approx({"superior": -0.3048, "derecho": -0.0131, "inferior": 0.1084, "izquierdo": 0.2104}, abs=5e-4)

    def test_a_todo_coincide_con_el_oraculo_de_numeros_complejos(self, sin_refinar):
        c, g = sin_refinar
        comparar(g, oraculo(c.esquinas, c.reticulo, ESC), 1e-9, 1e-9)

    def test_a_la_geometria_trae_los_puntos_y_la_escala_con_que_se_midio(self, sin_refinar):
        """R1P-03 (revision de la ronda 1): `GeometriaLuz.reticulo` y `.tam_mm` no se comprobaban en ninguna prueba y `reticulo=cruce` pasaba las 269. El reticulo es (1371, 1330) y NO el cruce de
        diagonales (1354.5, 1315.4: a 20 px de el); las esquinas, las de `clasificar_puntos`; la escala, la del procedimiento."""
        c, g = sin_refinar
        assert g.reticulo == (1371.0, 1330.0) and g.reticulo == c.reticulo
        assert g.esquinas == ((196.0, 143.0), (2542.0, 147.0), (2526.0, 2501.0), (171.0, 2480.0)) and g.esquinas == c.esquinas
        assert g.tam_mm == ESC
        assert g.reticulo != pytest.approx(g.cruce, abs=10.0), "el reticulo y el cruce de diagonales son dos puntos distintos"

    def test_a_el_pivote_por_omision_es_el_cruce_y_el_marco_girado_lo_deja_fijo(self, sin_refinar):
        pm = _pm()
        _, g = sin_refinar
        assert g.pivote == g.cruce
        M = np.array(g.matriz_de_giro)
        assert M == pytest.approx(pm.matriz_giro(g.cruce, g.angulo_grados))
        assert pm.transformar_puntos(M, [g.cruce])[0] == pytest.approx(g.cruce, abs=1e-9)
        # en el marco girado el campo queda con sus dos diagonales simetricas (angulo girado 0) y el lado superior casi horizontal
        angulos = [math.degrees(math.atan2(g.esquinas_giradas[2][1] - g.esquinas_giradas[0][1], g.esquinas_giradas[2][0] - g.esquinas_giradas[0][0])),
                   math.degrees(math.atan2(g.esquinas_giradas[1][1] - g.esquinas_giradas[3][1], g.esquinas_giradas[1][0] - g.esquinas_giradas[3][0]))]
        assert (angulos[0] + angulos[1]) / 2 == pytest.approx(0.0, abs=1e-9)


@pytest.fixture(scope="module")
def ml0():
    pm, pel = _pm(), _pelicula_mod()
    ruta = _real("ML0")
    pelicula = pel.leer_pelicula(Path(ruta).read_bytes())
    marcas = [pm.refinar_marca(pelicula.gris, clic, _P()) for clic in CLICS_ML0]
    c = pm.clasificar_puntos(marcas)
    return marcas, c, pm.geometria_luz(c.esquinas, c.reticulo, ESC)


class TestMl0ConLosClicsRefinados:
    """(a), segunda mitad: con los clics refinados por `refinar_marca` los numeros de ML0 cambian mas que la tolerancia (P10; la revision, con otro refinamiento, midio 0.360 grados y 0.49 / 0.30 mm).
    Los valores de abajo son los de `refinar_marca` y quedan fijados (JPEG decodificado por OpenCV 4.11: la tolerancia cubre una decodificacion distinta)."""

    def test_a_las_cinco_marcas_de_tinta_de_ml0_se_refinan_y_el_clic_del_reticulo_se_mueve_10_pixeles(self, ml0):
        marcas, _, _ = ml0
        assert [m.estado for m in marcas] == ["refinada"] * 5 and all(m.refinada for m in marcas)
        # lo que se movio cada clic [mm]: UL, UR, C (el reticulo: 10 pixeles, 0.44-0.50 mm), DR, DL
        assert [m.desplazamiento_mm for m in marcas] == pytest.approx([0.087, 0.180, 0.497, 0.051, 0.035], abs=0.01)
        assert all(m.desplazamiento_mm <= 1.5 for m in marcas)
        assert marcas[2].desplazamiento_px == pytest.approx(11.7, abs=0.5), "el clic del reticulo quedo a mas de 10 pixeles de su marca"
        assert [m.gris_del_nucleo for m in marcas] == pytest.approx([1, 1, 0, 0, 1], abs=1)           # tinta negra
        assert [m.area_mm2 for m in marcas] == pytest.approx([0.79, 0.64, 0.405, 0.73, 0.70], abs=0.03)

    def test_a_los_puntos_refinados_quedan_fijados(self, ml0):
        marcas, _, _ = ml0
        refinados = [c for m in marcas for c in m.punto]
        assert refinados == pytest.approx([195.403, 141.036, 2538.601, 144.437, 1364.58, 1320.183, 2525.733, 2499.822, 170.604, 2480.724], abs=0.15)

    def test_a_la_geometria_refinada_queda_fijada_y_difiere_de_la_sin_refinar_mas_que_la_tolerancia(self, ml0):
        _, c, g = ml0
        assert c.ok
        assert g.angulo_grados == pytest.approx(0.3670, abs=0.003)                                    # sin refinar 0.4025; la revision, con otro refinamiento, 0.360
        assert g.lados_mm == pytest.approx({"superior": 99.195, "derecho": 99.713, "inferior": 99.704, "izquierdo": 99.052}, abs=0.008)
        assert g.angulos_interiores_grados == pytest.approx({"UL": 90.524, "UR": 89.770, "DR": 89.848, "DL": 89.857}, abs=0.006)
        assert g.diagonales_mm == pytest.approx((140.367, 140.822), abs=0.008)
        assert g.luz_menos_reticulo_imagen_mm == pytest.approx((-0.461, -0.284), abs=0.015)           # la revision, con otro refinamiento: 0.49 / 0.30
        assert g.luz_menos_reticulo_girado_mm == pytest.approx((-0.4625, -0.281), abs=0.015)
        # EL HECHO A INFORMAR: refinar mueve los numeros de ML0 mas que su tolerancia (0.005 grados y 0.005 mm)
        sin = _pm().geometria_luz(_pm().clasificar_puntos(CLICS_ML0).esquinas, (1371.0, 1330.0), ESC)
        assert abs(g.angulo_grados - sin.angulo_grados) > 0.005
        assert abs(g.luz_menos_reticulo_modulo_mm - sin.luz_menos_reticulo_modulo_mm) > 0.005

    def test_a_la_geometria_refinada_tambien_coincide_con_el_oraculo(self, ml0):
        _, c, g = ml0
        comparar(g, oraculo(c.esquinas, c.reticulo, ESC), 1e-9, 1e-9)

    def test_a_la_pagina_entera_da_lo_mismo_que_el_recorte(self):
        """EPSON027 es la pagina de la que sale ML0 (ML0 esta en ella en (10, 7)): las mismas marcas, los mismos numeros."""
        pm, pel = _pm(), _pelicula_mod()
        gris_pagina = pel.leer_pelicula(Path(_real("EPSON027")).read_bytes()).gris
        gris_recorte = pel.leer_pelicula(Path(_real("ML0")).read_bytes()).gris
        en_pagina = [pm.refinar_marca(gris_pagina, c, _P()) for c in CLICS_EPSON027]
        en_recorte = [pm.refinar_marca(gris_recorte, c, _P()) for c in CLICS_ML0]
        del gris_pagina
        assert all(m.refinada for m in en_pagina)
        for a, b in zip(en_pagina, en_recorte):
            assert (a.punto[0] - 10.0, a.punto[1] - 7.0) == pytest.approx(b.punto, abs=0.6)           # la misma marca, +- una decodificacion de JPEG
        ga = pm.geometria_luz(*[getattr(pm.clasificar_puntos(en_pagina), k) for k in ("esquinas", "reticulo")], ESC)
        gb = pm.geometria_luz(*[getattr(pm.clasificar_puntos(en_recorte), k) for k in ("esquinas", "reticulo")], ESC)
        assert ga.angulo_grados == pytest.approx(gb.angulo_grados, abs=0.005)
        assert list(ga.lados_mm.values()) == pytest.approx(list(gb.lados_mm.values()), abs=0.005)
        assert ga.luz_menos_reticulo_modulo_mm == pytest.approx(gb.luz_menos_reticulo_modulo_mm, abs=0.03)


# --------------------------------------------------------------------------------------------------------- (b) cuadrilateros de verdad conocida
class TestCuadrilaterosDeVerdadConocida:
    """(b): la verdad sale de formulas cerradas (un rectangulo girado theta tiene el angulo theta, lados w y h, angulos de 90, diagonales raiz(w^2 + h^2), sus lados a theta - angulo = 0 del eje) o del
    oraculo de numeros complejos; <= 0.005 grados y <= 0.005 mm es lo que pide el plan, y la exactitud real es de 1e-7."""

    @pytest.mark.parametrize("theta", GIROS)
    @pytest.mark.parametrize("w,h", [(99.6, 99.8), (100.0, 100.0), (120.0, 80.0), (60.0, 140.0)])
    def test_b_un_rectangulo_girado_da_su_giro_sus_lados_y_sus_angulos_exactos(self, w, h, theta):
        esq, ret = rectangulo(w, h, theta, reticulo_mm=(0.3, -0.2))
        g = geometria(esq, ret)
        assert g.angulo_grados == pytest.approx(theta, abs=0.005) and g.angulo_grados == pytest.approx(theta, abs=1e-9)
        assert g.lados_mm == pytest.approx({"superior": w, "inferior": w, "derecho": h, "izquierdo": h}, abs=0.005)
        assert g.lados_mm == pytest.approx({"superior": w, "inferior": w, "derecho": h, "izquierdo": h}, abs=1e-7)
        assert list(g.angulos_interiores_grados.values()) == pytest.approx([90.0] * 4, abs=1e-8)
        assert g.diagonales_mm == pytest.approx((math.hypot(w, h),) * 2, abs=1e-7)
        # girado, el campo queda recto: ninguna inclinacion, y el reticulo (+0.3, -0.2) respecto del centro luminoso es luz - reticulo = (-0.3, +0.2) en el marco girado
        assert list(g.inclinacion_de_los_lados_grados.values()) == pytest.approx([0.0] * 4, abs=1e-8)
        assert g.luz_menos_reticulo_girado_mm == pytest.approx((-0.3, 0.2), abs=1e-7)
        # el angulo de las diagonales: +alfa y -alfa sin girar, theta + alfa y theta - alfa girado (R9, paso 3), alfa = atan(h / w)
        alfa = math.degrees(math.atan2(h, w))
        assert g.angulos_de_las_diagonales_grados == pytest.approx((theta + alfa, theta - alfa), abs=1e-8)
        # y la desviacion de cada diagonal es lo que se aparta de las de un cuadrado: solo un cuadrado perfecto da 0 y 0 sin girar
        if w == h:
            assert g.desviacion_de_las_diagonales_grados == pytest.approx((theta, theta), abs=1e-8)
        comparar(g, oraculo(esq, ret, ESC), 1e-8, 1e-8)

    @pytest.mark.parametrize("theta", GIROS)
    def test_b_un_trapecio_isosceles_girado_da_el_giro_y_los_numeros_de_sus_formulas_cerradas(self, theta):
        esq, ret = trapecio(theta, reticulo_mm=(1.0, 2.0))
        g = geometria(esq, ret)
        assert g.angulo_grados == pytest.approx(theta, abs=1e-9)                                       # simetrico: sus diagonales son +45 y -45, promedio 0
        assert g.angulos_de_las_diagonales_grados == pytest.approx((45.0 + theta, -45.0 + theta), abs=1e-9)
        a = math.degrees(math.atan2(100.0, 20.0))                                                      # 78.69: el angulo de las esquinas de abajo
        assert g.angulos_interiores_grados == pytest.approx({"UL": 180.0 - a, "UR": 180.0 - a, "DR": a, "DL": a}, abs=1e-8)
        largo_lateral = math.hypot(20.0, 100.0)
        assert g.lados_mm == pytest.approx({"superior": 80.0, "inferior": 120.0, "izquierdo": largo_lateral, "derecho": largo_lateral}, abs=1e-7)
        assert g.diagonales_mm == pytest.approx((math.hypot(100.0, 100.0),) * 2, abs=1e-7)
        inclinacion_lateral = math.degrees(math.atan2(20.0, 100.0))                                    # 11.31: los dos lados abren hacia abajo
        assert g.inclinacion_de_los_lados_grados == pytest.approx({"superior": 0.0, "inferior": 0.0, "izquierdo": inclinacion_lateral, "derecho": -inclinacion_lateral}, abs=1e-8)
        # las diagonales (y = x - 10 y y = -x - 10 en mm, con el origen en el centro del trapecio) se cortan en (0, -10): el cruce de diagonales NO es el centro de un trapecio
        assert g.luz_menos_reticulo_girado_mm == pytest.approx((0.0 - 1.0, -10.0 - 2.0), abs=1e-7)
        c0 = complex(1300.0, 1250.0) + cmath.exp(1j * math.radians(theta)) * complex(0.0, -10.0) / ESC
        assert g.cruce == pytest.approx((c0.real, c0.imag), abs=1e-6)
        comparar(g, oraculo(esq, ret, ESC), 1e-8, 1e-8)

    @pytest.mark.parametrize("theta", GIROS)
    def test_b_un_paralelogramo_girado_da_las_formulas_cerradas_con_el_cruce_en_su_centro(self, theta):
        a, s, h = 100.0, 3.0, 98.0
        esq, ret = paralelogramo(theta, reticulo_mm=(-1.0, 0.5), a=a, s=s, h=h)
        g = geometria(esq, ret)
        angulo_sin_girar = (math.degrees(math.atan2(h, a + s)) + math.degrees(math.atan2(-h, a - s))) / 2.0       # UL-DR = (a + s, h); DL-UR = (a - s, -h)
        assert g.angulo_grados == pytest.approx(theta + angulo_sin_girar, abs=1e-8)
        alfa = math.degrees(math.atan2(h, s))
        assert g.angulos_interiores_grados == pytest.approx({"UL": alfa, "DR": alfa, "UR": 180.0 - alfa, "DL": 180.0 - alfa}, abs=1e-8)
        lateral = math.hypot(s, h)
        assert g.lados_mm == pytest.approx({"superior": a, "inferior": a, "izquierdo": lateral, "derecho": lateral}, abs=1e-7)
        assert g.diagonales_mm == pytest.approx((math.hypot(a + s, h), math.hypot(a - s, h)), abs=1e-7)
        centro = (1300.0, 1250.0)
        assert g.cruce == pytest.approx(centro, abs=1e-6)                                              # las diagonales de un paralelogramo se cortan en su centro
        lateral_tilt = math.degrees(math.atan2(-s, h))                                                 # UL -> DL = (s, h) respecto de la vertical
        assert g.inclinacion_de_los_lados_grados == pytest.approx({"superior": -angulo_sin_girar, "inferior": -angulo_sin_girar,
                                                                  "izquierdo": lateral_tilt - angulo_sin_girar, "derecho": lateral_tilt - angulo_sin_girar}, abs=1e-8)
        comparar(g, oraculo(esq, ret, ESC), 1e-8, 1e-8)

    @pytest.mark.parametrize("theta", GIROS)
    def test_b_un_cuadrilatero_cualquiera_coincide_con_el_oraculo_y_sus_angulos_interiores_suman_360(self, theta):
        giro = cmath.exp(1j * math.radians(theta))
        crudo = [(-1180.0, -1190.0), (1160.0, -1210.0), (1195.0, 1100.0), (-1170.0, 1215.0)]
        esq = [_par(complex(1300.0, 1250.0) + giro * complex(*p)) for p in crudo]
        ret = _par(complex(1300.0, 1250.0) + giro * complex(14.0, -9.0))
        g = geometria(esq, ret)
        comparar(g, oraculo(esq, ret, ESC), 1e-8, 1e-8)
        assert sum(g.angulos_interiores_grados.values()) == pytest.approx(360.0, abs=1e-8)

    @pytest.mark.parametrize("theta", GIROS)
    def test_b_girar_todo_el_campo_theta_suma_theta_al_angulo_y_no_cambia_lados_ni_interiores(self, theta):
        base = [(-1180.0, -1190.0), (1160.0, -1210.0), (1195.0, 1100.0), (-1170.0, 1215.0)]
        g0 = geometria([(1300 + x, 1250 + y) for x, y in base], (1300.0, 1250.0))
        giro = cmath.exp(1j * math.radians(theta))
        g1 = geometria([_par(complex(1300.0, 1250.0) + giro * complex(*p)) for p in base], (1300.0, 1250.0))
        assert g1.angulo_grados == pytest.approx(g0.angulo_grados + theta, abs=1e-9)
        assert list(g1.lados_mm.values()) == pytest.approx(list(g0.lados_mm.values()), abs=1e-9)
        assert list(g1.angulos_interiores_grados.values()) == pytest.approx(list(g0.angulos_interiores_grados.values()), abs=1e-9)
        assert g1.desviacion_de_las_diagonales_grados[0] - g0.desviacion_de_las_diagonales_grados[0] == pytest.approx(theta, abs=1e-9)

    def test_b_un_campo_girado_en_sentido_horario_tiene_angulo_positivo_y_matriz_giro_con_ese_angulo_lo_endereza(self):
        pm = _pm()
        for theta in (1.0, 3.0, -3.0):
            esq, ret = rectangulo(99.6, 99.8, theta)
            g = geometria(esq, ret)
            assert np.sign(g.angulo_grados) == np.sign(theta)
            enderezado = pm.transformar_puntos(pm.matriz_giro(g.cruce, g.angulo_grados), esq)
            assert enderezado[0][1] == pytest.approx(enderezado[1][1], abs=1e-6) and enderezado[3][1] == pytest.approx(enderezado[2][1], abs=1e-6)     # arriba y abajo horizontales
            assert enderezado[0][0] == pytest.approx(enderezado[3][0], abs=1e-6) and enderezado[1][0] == pytest.approx(enderezado[2][0], abs=1e-6)     # izquierda y derecha verticales
            torcido = pm.transformar_puntos(pm.matriz_giro(g.cruce, -g.angulo_grados), esq)
            ancho_px = 99.6 / ESC
            assert abs(torcido[0][1] - torcido[1][1]) == pytest.approx(ancho_px * math.sin(math.radians(2 * abs(theta))), rel=0.02), "con el angulo cambiado de signo el campo queda al doble de torcido"


# El encuadre de cada giro: el recorte ajustado («A») a 1 y a -3 grados deja la marca superior derecha pegada al borde de la imagen (1.3 px a -3 grados: cortada, y por eso «sin refinar»), asi que esos dos
# giros van en el recorte suelto («L»: la caja de la pelicula girada, con las cuñas blancas de las esquinas).
ENCUADRE_POR_GIRO = {0.0: "A", 0.4: "A", 1.0: "L", -3.0: "L"}


@pytest.fixture(scope="module", params=GIROS, ids=[f"giro{g:+g}" for g in GIROS])
def cadena(request):
    pm, pel = _pm(), _pelicula_mod()
    placa = gen.generar("png", variante=ENCUADRE_POR_GIRO[request.param], theta_deg=request.param, seed=11, dpi=600)
    pelicula = pel.leer_pelicula(placa.datos)
    clics = placa.verdad.clics_del_cuaderno()
    marcas = [pm.refinar_marca(pelicula.gris, c, _P()) for c in clics]
    c = pm.clasificar_puntos(marcas)
    return request.param, placa.verdad, clics, marcas, c, pm.geometria_luz(c.esquinas, c.reticulo, ESC), pelicula


class TestPeliculasSinteticasDePuntaAPunta:
    """(b), la cadena entera sobre las peliculas de PF.0 a 600 dpi: clic (el centro verdadero de cada marca, redondeado a entero como el clic del fisico) -> `refinar_marca` -> `clasificar_puntos`
    -> `geometria_luz`, contra la verdad del generador: el campo luminoso es un rectangulo de 99.6 x 99.8 mm girado theta con el reticulo a (0.3, -0.2) mm de su centro."""

    def test_b_cada_marca_vuelve_al_centro_verdadero_a_600_dpi(self, cadena):
        _, verdad, clics, marcas, _, _, _ = cadena
        assert all(m.refinada for m in marcas)
        for clic, m, nombre in zip(clics, marcas, ("UL", "UR", "C", "DR", "DL")):
            mx, my = verdad.marcas_px[nombre]
            assert math.hypot(m.punto[0] - mx, m.punto[1] - my) * ESC <= 0.005, nombre
            # el clic estaba a lo sumo a medio pixel de la verdad: no hay nada que corregir y el punto no se aleja
            assert m.desplazamiento_px <= 1.0

    def test_b_el_angulo_los_lados_y_el_reticulo_salen_dentro_de_0_005_grados_y_0_005_mm(self, cadena):
        theta, _, _, _, c, g, _ = cadena
        assert c.ok and g.ok
        assert g.angulo_grados == pytest.approx(theta, abs=0.005)
        assert g.lados_mm == pytest.approx({"superior": 99.6, "inferior": 99.6, "izquierdo": 99.8, "derecho": 99.8}, abs=0.005)
        assert list(g.angulos_interiores_grados.values()) == pytest.approx([90.0] * 4, abs=0.005)
        assert g.diagonales_mm == pytest.approx((math.hypot(99.6, 99.8),) * 2, abs=0.005)
        assert list(g.inclinacion_de_los_lados_grados.values()) == pytest.approx([0.0] * 4, abs=0.005)
        assert g.luz_menos_reticulo_girado_mm == pytest.approx((-0.3, 0.2), abs=0.005)               # el reticulo esta a (+0.3, -0.2) mm del centro luminoso

    def test_b_la_geometria_de_los_clics_sin_refinar_es_peor_que_la_refinada(self, cadena):
        """R1P-04 (revision de la ronda 1): el nombre promete una COMPARACION y antes solo habia dos cotas sueltas (pasaba aunque «sin refinar» fuera identica a la refinada). Medido en los cuatro giros: el error
        de los lados es 8.9 a 19.6 veces mayor sin refinar (0.020 a 0.033 mm contra 0.001 a 0.003) y el del reticulo 5.7 a 109 veces (0.014 a 0.044 mm contra 0.0004 a 0.003): el clic entero se queda a medio pixel."""
        theta, verdad, clics, _, c, g, _ = cadena
        pm = _pm()
        sin = pm.clasificar_puntos(clics)
        gs = pm.geometria_luz(sin.esquinas, sin.reticulo, ESC)
        assert gs.estado == "ok"
        lados = {"superior": 99.6, "inferior": 99.6, "izquierdo": 99.8, "derecho": 99.8}
        error_refinado = max(abs(g.lados_mm[k] - v) for k, v in lados.items())
        error_sin_refinar = max(abs(gs.lados_mm[k] - v) for k, v in lados.items())
        reticulo_refinado = math.hypot(g.luz_menos_reticulo_girado_mm[0] + 0.3, g.luz_menos_reticulo_girado_mm[1] - 0.2)                 # el reticulo esta a (+0.3, -0.2) mm del centro luminoso
        reticulo_sin_refinar = math.hypot(gs.luz_menos_reticulo_girado_mm[0] + 0.3, gs.luz_menos_reticulo_girado_mm[1] - 0.2)
        assert error_refinado <= 0.005
        assert error_sin_refinar > 3 * error_refinado, (error_sin_refinar, error_refinado)
        assert reticulo_sin_refinar > 3 * reticulo_refinado, (reticulo_sin_refinar, reticulo_refinado)
        assert abs(gs.angulo_grados - theta) < 0.02          # redondear el clic a entero tambien deja el angulo a menos de 0.02 grados: lo que cambia el refinamiento es la medida de lados y reticulo


@pytest.fixture(scope="module")
def pagina():
    placa = gen.generar("png", variante="D", theta_deg=0.4, seed=5, dpi=300)
    return placa.verdad, placa.verdad.clics_del_cuaderno(), 25.4 / 300


class TestPeliculaSinteticaFueraDelCentroDeLaImagen:
    """(c) y N2: la pelicula a 800 px del centro de la imagen (variante D de PF.0: pagina de 4400 x 3300) donde el cuaderno ni clasifica (`NameError`): aqui se clasifica igual."""

    def test_c_la_pelicula_descentrada_se_clasifica_y_su_geometria_es_la_de_la_verdad(self, pagina):
        verdad, clics, tam = pagina
        pm = _pm()
        c = pm.clasificar_puntos(clics)
        assert c.ok and c.reticulo == clics[2] and c.esquinas == (clics[0], clics[1], clics[3], clics[4])
        g = pm.geometria_luz(c.esquinas, c.reticulo, tam)
        assert g.angulo_grados == pytest.approx(0.4, abs=0.02)
        assert g.lados_mm == pytest.approx({"superior": 99.6, "inferior": 99.6, "izquierdo": 99.8, "derecho": 99.8}, abs=0.1)
        # el retículo esta a 394 px del centro de la imagen a 300 dpi (800 a 600 dpi; el cuaderno lo exige a 100): clasificar no mira la imagen
        assert abs(c.reticulo[0] - verdad.ancho / 2) > 350

    def test_c_los_mismos_cinco_puntos_en_otro_lugar_de_la_imagen_dan_la_misma_geometria(self):
        pm = _pm()
        base = pm.geometria_luz(*[getattr(pm.clasificar_puntos(CLICS_ML0), k) for k in ("esquinas", "reticulo")], ESC)
        for dx, dy in ((0, 0), (1500, -100), (-150, 4000), (30000, 20000)):
            puntos = [(x + dx, y + dy) for x, y in CLICS_ML0]
            c = pm.clasificar_puntos(puntos)
            g = pm.geometria_luz(c.esquinas, c.reticulo, ESC)
            assert c.ok and c.indice_del_reticulo == 2
            assert g.angulo_grados == pytest.approx(base.angulo_grados, abs=1e-9)
            assert list(g.lados_mm.values()) == pytest.approx(list(base.lados_mm.values()), abs=1e-9)
            assert g.luz_menos_reticulo_imagen_mm == pytest.approx(base.luz_menos_reticulo_imagen_mm, abs=1e-9)


# ------------------------------------------------------------------------------------------------------------------------ (c) las 120 permutaciones
def _sin_indices(c):
    d = c.como_dict()
    d.pop("indice_del_reticulo")
    d.pop("indices_de_las_esquinas")
    return d


CONJUNTOS_DE_PUNTOS = {
    "ml0": CLICS_ML0,
    "trapecio": lambda: [tuple(p) for p in (lambda e, r: e[:2] + [r] + e[2:])(*trapecio(0.7, reticulo_mm=(2.0, -1.5)))],
    "descentrada_y_girada": lambda: [tuple(p) for p in (lambda e, r: e[:2] + [r] + e[2:])(*rectangulo(99.6, 99.8, -3.0, centro=(4600.5, 800.25), reticulo_mm=(3.0, 2.0)))],
}


@pytest.fixture(scope="module", params=sorted(CONJUNTOS_DE_PUNTOS))
def conjunto(request):
    c = CONJUNTOS_DE_PUNTOS[request.param]
    return request.param, list(c() if callable(c) else c)


class TestPermutacionesDeLosClics:
    """(c): el orden en que se marcan los cinco puntos no cambia nada. Las 120 permutaciones dan lo mismo, BIT A BIT (las funciones ordenan por coordenadas antes de operar)."""

    def test_c_las_120_permutaciones_clasifican_igual_y_los_indices_dicen_cual_era_cual(self, conjunto):
        pm = _pm()
        nombre, puntos = conjunto
        ref = pm.clasificar_puntos(puntos)
        assert ref.ok
        vistas = 0
        for perm in itertools.permutations(range(5)):
            lista = [puntos[i] for i in perm]
            c = pm.clasificar_puntos(lista)
            assert _sin_indices(c) == _sin_indices(ref), (nombre, perm)
            assert lista[c.indice_del_reticulo] == c.reticulo
            assert tuple(lista[i] for i in c.indices_de_las_esquinas) == c.esquinas
            assert sorted([c.indice_del_reticulo, *c.indices_de_las_esquinas]) == [0, 1, 2, 3, 4]
            vistas += 1
        assert vistas == 120

    def test_c_las_120_permutaciones_dan_la_misma_geometria_exacta(self, conjunto):
        pm = _pm()
        _, puntos = conjunto
        c0 = pm.clasificar_puntos(puntos)
        ref = pm.geometria_luz(c0.esquinas, c0.reticulo, ESC).como_dict()
        for perm in itertools.permutations(range(5)):
            c = pm.clasificar_puntos([puntos[i] for i in perm])
            assert pm.geometria_luz(c.esquinas, c.reticulo, ESC).como_dict() == ref, perm

    def test_c_las_esquinas_en_cualquier_orden_dan_la_misma_geometria(self, conjunto):
        pm = _pm()
        _, puntos = conjunto
        c0 = pm.clasificar_puntos(puntos)
        ref = pm.geometria_luz(c0.esquinas, c0.reticulo, ESC).como_dict()
        for perm in itertools.permutations(range(4)):
            g = pm.geometria_luz([c0.esquinas[i] for i in perm], c0.reticulo, ESC)
            assert g.como_dict() == ref, perm

    def test_c_el_reticulo_es_el_mas_cercano_al_centroide_de_los_otros_cuatro_aunque_este_lejos_del_centro(self):
        pm = _pm()
        esq, _ = rectangulo(99.6, 99.8, 0.4, centro=(900.0, 700.0))
        for ret_mm in ((0.0, 0.0), (6.0, -4.0), (-12.0, 9.0)):
            _, ret = rectangulo(99.6, 99.8, 0.4, centro=(900.0, 700.0), reticulo_mm=ret_mm)
            c = pm.clasificar_puntos([*esq[:2], ret, *esq[2:]])
            assert c.ok and c.reticulo == tuple(ret) and c.indice_del_reticulo == 2

    def test_c_otra_tipo_de_entrada_da_lo_mismo_pares_marcas_y_diccionarios(self):
        pm = _pm()
        referencia = pm.clasificar_puntos(CLICS_ML0)
        como_marcas = [pm.MarcaRefinada("sin refinar", tuple(map(float, p)), tuple(map(float, p)), 0.0, 0.0, 35.4, "sin refinar: x") for p in CLICS_ML0]
        assert _sin_indices(pm.clasificar_puntos(como_marcas)) == _sin_indices(referencia)
        assert _sin_indices(pm.clasificar_puntos([m.como_dict() for m in como_marcas])) == _sin_indices(referencia)
        assert _sin_indices(pm.clasificar_puntos(np.array(CLICS_ML0, float))) == _sin_indices(referencia)
        assert _sin_indices(pm.clasificar_puntos(tuple(CLICS_ML0))) == _sin_indices(referencia)


class TestPuntosQueNoFormanElCampo:
    """«no medible: los puntos no forman el campo»: lo que lo atrapa es la convexidad y el reticulo adentro, no la imagen."""

    @staticmethod
    def _motivo(c):
        return c.estado

    def _no_forman(self, puntos):
        c = _pm().clasificar_puntos(puntos)
        assert not c.ok and c.estado.startswith("no medible: los puntos no forman el campo"), c.estado
        assert c.reticulo is None and c.esquinas == () and c.indice_del_reticulo is None and c.indices_de_las_esquinas == ()
        return c

    def test_un_punto_lejano_que_empata_dos_esquinas_no_deja_distinguir_el_reticulo(self):
        esq, _ = rectangulo(99.6, 99.8, 0.0, centro=(1300.0, 1250.0))
        c = self._no_forman([*esq, (1300.0 + 4000.0, 1250.0)])                 # en el eje del rectangulo: dos esquinas empatan como las mas cercanas al centroide
        assert c.estado == "no medible: los puntos no forman el campo (no se distingue cuál de los puntos es el retículo)"

    def test_un_punto_lejano_que_no_empata_deja_al_reticulo_fuera_del_cuadrilatero(self):
        c = self._no_forman([(0, 0), (100, 0), (100, 100), (0, 100), (400, 40)])
        assert c.estado == "no medible: los puntos no forman el campo (el retículo no cae dentro del cuadrilátero de las cuatro esquinas)"

    def test_el_reticulo_sobre_un_lado_no_esta_dentro(self):
        c = self._no_forman([(0, 0), (100, 0), (100, 100), (0, 100), (50, 0)])
        assert c.estado == "no medible: los puntos no forman el campo (el retículo no cae dentro del cuadrilátero de las cuatro esquinas)"

    # hacia donde queda cada lado del campo desde su centro, en el marco del propio rectangulo (la y hacia abajo)
    HACIA_EL_LADO = {"superior": (0.0, -1.0), "derecho": (1.0, 0.0), "inferior": (0.0, 1.0), "izquierdo": (-1.0, 0.0)}
    NO_ESTA_DENTRO = "no medible: los puntos no forman el campo (el retículo no cae dentro del cuadrilátero de las cuatro esquinas)"

    @classmethod
    def _con_el_reticulo_a(cls, lado, theta, mm_del_lado):
        """(esquinas, reticulo) de un campo de 99.6 x 99.8 mm girado `theta` con el reticulo sobre la perpendicular al `lado` por el centro, a `mm_del_lado` mm de ese lado (positivo = mas alla de el)."""
        w, h = 99.6, 99.8
        dx, dy = cls.HACIA_EL_LADO[lado]
        medio = w / 2 if dx else h / 2
        return rectangulo(w, h, theta, reticulo_mm=(dx * (medio + mm_del_lado), dy * (medio + mm_del_lado)))

    @pytest.mark.parametrize("theta", (0.0, 25.0, -3.0))
    @pytest.mark.parametrize("lado", LADOS)
    @pytest.mark.parametrize("mas_alla_mm", (0.5, 5.0))
    def test_un_reticulo_fuera_por_cualquiera_de_los_cuatro_lados_no_forma_el_campo(self, lado, theta, mas_alla_mm):
        """R1P-02 (revision de la ronda 1): el reticulo fuera solo se probaba por el lado derecho y SOBRE el superior; una `_reticulo_dentro` que no mira el lado izquierdo o el inferior daba «ok» con el
        reticulo fuera del cuadrilatero. Los cuatro lados, con el campo recto y girado, a 0.5 mm (apenas fuera) y a 5 mm, por las dos puertas (`geometria_luz` y `clasificar_puntos`)."""
        pm = _pm()
        esq, ret = self._con_el_reticulo_a(lado, theta, mas_alla_mm)
        g = pm.geometria_luz(esq, ret, ESC)
        assert not g.ok and g.estado == self.NO_ESTA_DENTRO and g.angulo_grados is None, (lado, theta, g.estado)
        c = pm.clasificar_puntos([*esq[:2], ret, *esq[2:]])
        assert not c.ok and c.estado == self.NO_ESTA_DENTRO and c.reticulo is None and c.esquinas == (), (lado, theta, c.estado)

    @pytest.mark.parametrize("theta", (0.0, 25.0, -3.0))
    @pytest.mark.parametrize("lado", LADOS)
    @pytest.mark.parametrize("dentro_mm", (0.5, 5.0))
    def test_un_reticulo_justo_adentro_de_cualquiera_de_los_cuatro_lados_si_forma_el_campo(self, lado, theta, dentro_mm):
        """El control de la anterior: a la misma distancia pero del lado de adentro el campo se forma (la guarda no rechaza de mas por ningun lado)."""
        pm = _pm()
        esq, ret = self._con_el_reticulo_a(lado, theta, -dentro_mm)
        g = pm.geometria_luz(esq, ret, ESC)
        assert g.ok and g.reticulo == pytest.approx(ret, abs=1e-9), (lado, theta, g.estado)
        c = pm.clasificar_puntos([*esq[:2], ret, *esq[2:]])
        assert c.ok and c.reticulo == tuple(ret) and c.indice_del_reticulo == 2, (lado, theta, c.estado)

    def test_cuatro_esquinas_no_convexas_no_forman_el_campo(self):
        # una «punta de flecha»: (60, 40) esta dentro del triangulo (0, 0), (100, 0), (100, 100); el reticulo (65, 35) es el mas cercano al centroide de los cinco
        c = self._no_forman([(0, 0), (100, 0), (100, 100), (60, 40), (65, 35)])
        assert c.estado == "no medible: los puntos no forman el campo (las cuatro esquinas no forman un cuadrilátero convexo)"

    def test_tres_esquinas_colineales_no_forman_el_campo(self):
        self._no_forman([(0, 0), (50, 0), (100, 0), (100, 100), (30, 30)])

    def test_dos_puntos_en_el_mismo_lugar_no_forman_el_campo(self):
        c = self._no_forman([(0, 0), (100, 0), (100, 100), (0, 100), (0, 100)])
        assert "mismo lugar" in c.estado

    def test_cinco_puntos_que_no_dejan_distinguir_el_reticulo_no_lo_clasifican(self):
        pentagono = [(100 + 100 * math.cos(2 * math.pi * k / 5), 100 + 100 * math.sin(2 * math.pi * k / 5)) for k in range(5)]
        c = self._no_forman(pentagono)
        assert c.estado == "no medible: los puntos no forman el campo (no se distingue cuál de los puntos es el retículo)"

    @pytest.mark.parametrize("malo", [[(0, 0)] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0)] * 6, 7, None])
    def test_una_forma_equivocada_de_los_puntos_es_valueerror(self, malo):
        with pytest.raises(ValueError):
            _pm().clasificar_puntos(malo)

    @pytest.mark.parametrize("punto", [(float("nan"), 1.0), (1.0, float("inf")), "ab", (1, 2, 3), (1,), None, "no"])
    def test_un_punto_que_no_es_un_par_finito_es_valueerror(self, punto):
        with pytest.raises(ValueError):
            _pm().clasificar_puntos([(0, 0), (10, 0), (10, 10), (0, 10), punto])


# ------------------------------------------------------------------------------------------------------------------------ la mancha de tinta (d)
def parche(forma=(420, 420), centro=(210.0, 205.0), radio_px=12.0, nucleo=3.0, fondo=100.0, gradiente=(0.0, 0.0), ruido=1.5, borde_px=2.4, semilla=1, semi_largo_px=0.0):
    """Un recorte de pelicula SINTETICO: el fondo (`fondo` en el centro mas el `gradiente` en niveles por pixel), un disco de tinta de `radio_px` con borde suave (erf, sigma `borde_px`) y de nivel
    `nucleo`, y ruido gaussiano. uint8, como el escaneo. El centro verdadero del disco es `centro` (x, y). Con `semi_largo_px` > 0 no es un disco sino una barra horizontal con extremos redondos
    (el segmento de ese semilargo con `radio_px` de ancho a cada lado): un trazo de rotulador, angosto pero largo."""
    h, w = forma
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    bg = fondo + gradiente[0] * (xx - w / 2) + gradiente[1] * (yy - h / 2)
    from scipy.special import erf
    d = np.hypot(np.maximum(np.abs(xx - centro[0]) - semi_largo_px, 0.0), yy - centro[1])
    m = 0.5 * (1.0 - erf((d - radio_px) / (math.sqrt(2) * borde_px)))
    img = bg * (1 - m) + nucleo * m + np.random.default_rng(semilla).normal(0.0, ruido, bg.shape)
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


class TestRefinarUnaMarca:
    """(d): un clic a 1 mm o menos del centro de una marca vuelve al centro (<= 0.05 mm); sin marca, queda «sin refinar»."""

    def test_d_un_clic_a_menos_de_1_mm_vuelve_al_centro_de_la_marca_en_todas_las_direcciones(self):
        pm = _pm()
        gris = parche(centro=(210.4, 205.7))
        for r_mm in (0.0, 0.25, 0.5, 0.75, 1.0):
            for ang in np.linspace(0, 2 * math.pi, 12, endpoint=False):
                clic = (210.4 + r_mm / ESC * math.cos(ang), 205.7 + r_mm / ESC * math.sin(ang))
                m = pm.refinar_marca(gris, clic, _P())
                assert m.estado == "refinada" and m.refinada and m.motivo is None, (r_mm, ang, m.motivo)
                assert math.hypot(m.punto[0] - 210.4, m.punto[1] - 205.7) * ESC <= 0.05
                assert math.hypot(m.punto[0] - 210.4, m.punto[1] - 205.7) * ESC <= 0.01          # y en la practica
                assert m.clic == pytest.approx(clic) and m.desplazamiento_px == pytest.approx(math.hypot(m.punto[0] - clic[0], m.punto[1] - clic[1]))
                assert m.desplazamiento_mm == pytest.approx(m.desplazamiento_px * ESC)

    @pytest.mark.parametrize("gradiente_mm", [0.0, 10.0, 25.0, -25.0, 40.0])
    def test_d_el_degradado_de_la_penumbra_no_corre_el_centro(self, gradiente_mm):
        """Un fondo que cambia 25 niveles por mm (la penumbra del campo) corria el centro 0.02 a 0.03 mm con el umbral solo; con la fraccion de tinta no pasa de 0.01."""
        pm = _pm()
        g = gradiente_mm * ESC
        for gx, gy in ((g, 0.0), (0.0, g), (g * 0.7, -g * 0.7)):
            gris = parche(centro=(210.3, 204.6), fondo=110.0, gradiente=(gx, gy))
            m = pm.refinar_marca(gris, (212.0, 206.0), _P())
            assert m.refinada
            assert math.hypot(m.punto[0] - 210.3, m.punto[1] - 204.6) * ESC <= 0.01, (gx, gy)

    def test_d_sobre_la_meseta_oscura_del_campo_tambien_se_refina(self):
        """El reticulo cae sobre la meseta del campo, a ~24 niveles: la tinta negra contrasta 20."""
        m = _pm().refinar_marca(parche(fondo=24.0, nucleo=2.0), (213.0, 209.0), _P())
        assert m.refinada and math.hypot(m.punto[0] - 210.0, m.punto[1] - 205.0) * ESC <= 0.01

    def test_d_sin_marca_el_clic_queda_sin_refinar_y_el_punto_es_el_clic(self):
        pm = _pm()
        liso = parche(radio_px=0.001, nucleo=100.0)                  # sin tinta: una pelicula lisa con su ruido
        m = pm.refinar_marca(liso, (210.25, 205.5), _P())
        assert m.estado == "sin refinar" and not m.refinada
        assert m.punto == m.clic == (210.25, 205.5) and m.desplazamiento_px == 0.0 and m.desplazamiento_mm == 0.0
        assert m.motivo.startswith("sin refinar") and m.area_mm2 is None and m.contraste is None and m.gris_del_nucleo is None
        assert m.radio_px == pytest.approx(1.5 / ESC)

    def test_d_una_mancha_a_mas_de_1_5_mm_no_se_toma(self):
        pm = _pm()
        gris = parche(centro=(210.0, 205.0))
        r_aceptada = pm.refinar_marca(gris, (210.0 + 1.4 / ESC, 205.0), _P())
        assert r_aceptada.refinada, "a 1.4 mm todavia es la marca"
        for lejos_mm in (1.7, 2.0, 2.4, 3.0):
            m = pm.refinar_marca(gris, (210.0 + lejos_mm / ESC, 205.0), _P())
            assert m.estado == "sin refinar" and m.punto == m.clic, lejos_mm
            assert m.motivo == "sin refinar: no hay una mancha de tinta a menos de 1.5 mm del clic"

    @pytest.mark.parametrize("radio_mm", [0.3, 0.6, 1.0, 1.3])
    def test_d_el_cierre_es_del_tamano_del_radio_de_busqueda_y_quita_marcas_de_hasta_2_6_mm_de_diametro(self, radio_mm):
        """El cierre morfologico que separa la mancha de su fondo es un circulo del radio de busqueda (1.5 mm): quita todo disco de tinta que quepa en el. Con uno mas chico (un cuarto del radio) una marca de
        mas de ~0.4 mm de radio no se quitaria, la «tinta» no la veria y quedaria sin refinar (las de ML0 miden 0.4 a 0.8 mm2: 0.36 a 0.5 mm de radio)."""
        m = _pm().refinar_marca(parche(radio_px=radio_mm / ESC), (212.0, 206.0), _P())
        assert m.refinada, (radio_mm, m.motivo)
        assert math.hypot(m.punto[0] - 210.0, m.punto[1] - 205.0) * ESC <= 0.01, radio_mm

    def test_d_el_radio_de_busqueda_es_un_parametro_y_se_aplica(self):
        pm = _pm()
        gris = parche(centro=(210.0, 205.0))
        clic = (210.0 + 2.0 / ESC, 205.0)
        assert not pm.refinar_marca(gris, clic, _P()).refinada
        assert pm.refinar_marca(gris, clic, _P(radio_marca_mm=2.5)).refinada
        assert not pm.refinar_marca(gris, (210.0 + 1.0 / ESC, 205.0), _P(radio_marca_mm=0.8)).refinada

    def test_d_la_escala_es_un_argumento_y_a_otra_resolucion_se_comporta_igual_en_milimetros(self):
        """A 150 dpi (tam 0.169 mm) el disco de 0.5 mm mide 3 pixeles y se refina igual; el radio de 1.5 mm son 8.9 pixeles."""
        pm = _pm()
        tam = 25.4 / 150
        gris = parche(forma=(110, 110), centro=(55.3, 54.6), radio_px=0.5 / tam, borde_px=0.1 / tam, ruido=1.0)
        m = pm.refinar_marca(gris, (55.3 + 1.0 / tam, 54.6), _P(), tam)
        assert m.refinada and math.hypot(m.punto[0] - 55.3, m.punto[1] - 54.6) * tam <= 0.03
        assert m.radio_px == pytest.approx(1.5 / tam)
        assert not pm.refinar_marca(gris, (55.3 + 2.0 / tam, 54.6), _P(), tam).refinada

    def test_d_la_marca_a_su_vez_con_la_escala_del_procedimiento_por_omision(self):
        pm = _pm()
        gris = parche()
        a = pm.refinar_marca(gris, (214.0, 207.0), _P())
        b = pm.refinar_marca(gris, (214.0, 207.0), _P(), 25.4 / 600)
        assert a.como_dict() == b.como_dict()

    @pytest.mark.parametrize("tipo", ["uint8", "float32", "float64", "uint16_escalado"])
    def test_d_el_tipo_del_arreglo_no_cambia_el_resultado(self, tipo):
        pm = _pm()
        base = parche(centro=(210.4, 205.7))
        referencia = pm.refinar_marca(base, (213.0, 207.0), _P())
        gris = {"uint8": base, "float32": base.astype(np.float32), "float64": base.astype(np.float64), "uint16_escalado": base.astype(np.uint16) * 257}[tipo]
        if tipo == "uint16_escalado":
            gris = (gris.astype(np.float32) * (255.0 / 65535.0))              # lo que entrega `Pelicula.gris` de un TIFF de 16 bits
        m = pm.refinar_marca(gris, (213.0, 207.0), _P())
        assert m.refinada and m.punto == pytest.approx(referencia.punto, abs=1e-3)

    def test_d_dos_manchas_gana_la_mas_cercana_al_clic(self):
        pm = _pm()
        a = parche(centro=(150.0, 205.0))
        b = parche(centro=(215.0, 205.0), semilla=2)
        gris = np.minimum(a, b)                                        # las dos manchas en la misma pelicula (dos discos de tinta)
        cerca_de_b = pm.refinar_marca(gris, (205.0, 205.0), _P())
        cerca_de_a = pm.refinar_marca(gris, (160.0, 205.0), _P())
        assert cerca_de_b.refinada and abs(cerca_de_b.punto[0] - 215.0) < 0.5
        assert cerca_de_a.refinada and abs(cerca_de_a.punto[0] - 150.0) < 0.5

    def test_d_la_marca_se_encuentra_aunque_la_pelicula_tenga_un_rayon_claro_cerca(self):
        pm = _pm()
        gris = parche(centro=(210.0, 205.0)).copy()
        gris[:, 222:226] = 250                                          # un rayon vertical claro a 0.5 mm de la marca
        m = pm.refinar_marca(gris, (214.0, 207.0), _P())
        assert m.refinada and math.hypot(m.punto[0] - 210.0, m.punto[1] - 205.0) * ESC <= 0.03


class TestLaMedidaDeLaMancha:
    """Los parametros de la forma de medir la mancha (el borde a la mitad del contraste, el margen del borde blando, el circulo del que sale el maximo) hacen algo y lo hacen bien."""

    @staticmethod
    def _con_una_mancha_tenue_pegada(**cambios):
        fuerte = parche(centro=(210.0, 205.0), fondo=100.0, nucleo=3.0)
        tenue = parche(centro=(224.0, 205.0), fondo=100.0, nucleo=70.0, semilla=2)         # contraste 30, solapada con la de tinta
        return np.minimum(fuerte, tenue), _P(**cambios)

    def test_el_borde_de_la_mancha_es_la_mitad_de_su_contraste_y_la_tenue_pegada_no_la_corre(self):
        pm = _pm()
        g, P = self._con_una_mancha_tenue_pegada()
        m = pm.refinar_marca(g, (212.0, 206.0), P)
        assert m.refinada and abs(m.punto[0] - 210.0) < 1.0 and abs(m.punto[1] - 205.0) < 0.5
        assert m.area_mm2 == pytest.approx(0.8, abs=0.06)
        # con el borde en el 10 % del contraste, la mancha tenue entra, la mancha crece y el centro se corre hacia ella
        g, P = self._con_una_mancha_tenue_pegada(fraccion_del_contraste_marca=0.1)
        m2 = pm.refinar_marca(g, (212.0, 206.0), P)
        assert m2.refinada and m2.punto[0] - 210.0 > 2.5 and m2.area_mm2 > 1.5

    def test_el_margen_del_borde_blando_es_un_parametro_y_pesa_lo_que_hay_alrededor(self):
        pm = _pm()
        g, P = self._con_una_mancha_tenue_pegada()
        m = pm.refinar_marca(g, (212.0, 206.0), P)
        ancho = pm.refinar_marca(*[g, (212.0, 206.0)], _P(borde_blando_marca_mm=0.5))
        assert abs(ancho.punto[0] - m.punto[0]) > 1.0, "con 0.5 mm de margen la mancha tenue de al lado pesa en el centro"

    def test_en_una_pelicula_clara_y_en_una_oscura_la_mancha_mide_lo_mismo(self):
        pm = _pm()
        clara = pm.refinar_marca(parche(fondo=200.0, centro=(210.4, 205.7)), (212.0, 207.0), _P())
        oscura = pm.refinar_marca(parche(fondo=40.0, centro=(210.4, 205.7)), (212.0, 207.0), _P())
        assert clara.refinada and oscura.refinada
        assert clara.area_mm2 == pytest.approx(oscura.area_mm2, rel=0.05)
        assert clara.punto == pytest.approx(oscura.punto, abs=0.1)

    def test_un_hueco_claro_dentro_de_la_mancha_no_le_quita_area(self):
        pm = _pm()
        entera = parche(centro=(210.0, 205.0), nucleo=3.0)
        con_hueco = entera.copy()
        yy, xx = np.mgrid[0:420, 0:420]
        con_hueco[np.hypot(xx - 210, yy - 205) < 5] = 100            # una mota clara de 0.4 mm dentro de la tinta (como las de ML0)
        a, b = pm.refinar_marca(entera, (212.0, 206.0), _P()), pm.refinar_marca(con_hueco, (212.0, 206.0), _P())
        assert a.refinada and b.refinada
        assert b.area_mm2 == pytest.approx(a.area_mm2, rel=0.03)
        assert b.punto == pytest.approx(a.punto, abs=0.15)

    def test_la_mancha_mas_oscura_de_al_lado_pero_fuera_del_circulo_no_hace_perder_la_del_clic(self):
        """El maximo con que se mide el borde sale del circulo de 1.5 mm del clic: una marca fuerte a 2.2 mm no sube el umbral de la debil que esta en el clic."""
        pm = _pm()
        from scipy.ndimage import gaussian_filter
        from scipy.special import erf
        yy, xx = np.mgrid[0:420, 0:420].astype(float)
        fondo = np.full((420, 420), 45.0)
        fondo[:, 250:] = 200.0                                          # un escalon de la penumbra: oscuro a la izquierda, claro a la derecha
        img = gaussian_filter(fondo, 2.0)
        for cx in (230.0, 230.0 + 47.0):                                # la debil (sobre el oscuro) en el clic y la fuerte (sobre el claro) a 2.2 mm
            m = 0.5 * (1 - erf((np.hypot(xx - cx, yy - 205.0) - 12.0) / (math.sqrt(2) * 2.4)))
            img = img * (1 - m) + 3.0 * m
        gris = np.clip(np.rint(img + np.random.default_rng(3).normal(0, 1.5, img.shape)), 0, 255).astype(np.uint8)
        m = pm.refinar_marca(gris, (225.0, 205.0), _P())
        assert m.refinada and abs(m.punto[0] - 230.0) < 0.5 and 35 < m.contraste < 80, (m.motivo, m.contraste)
        fuerte = pm.refinar_marca(gris, (277.0, 205.0), _P())
        assert fuerte.refinada and fuerte.contraste > 150


class TestLoQueNoEsTintaNoSeRefina:
    """Lo que no es una marca de tinta deja el clic donde esta (R3: en las peliculas con anillos de presion y en las motas, arrastrar el punto lo empeoraria)."""

    def test_un_anillo_claro_con_un_punto_oscuro_en_el_centro_no_se_refina(self):
        pm = _pm()
        gris = parche(radio_px=0.001, nucleo=100.0, fondo=90.0).astype(np.float64)
        yy, xx = np.mgrid[0:420, 0:420]
        d = np.hypot(xx - 210.0, yy - 205.0)
        gris += 45.0 * np.exp(-0.5 * ((d - 17.0) / 3.5) ** 2)             # el anillo (mas claro que el fondo), de 0.7 mm de radio
        gris -= 40.0 * np.exp(-0.5 * (d / 3.0) ** 2)                      # y el punto oscuro de su centro: 40 niveles mas oscuro, pero no es tinta (su nucleo no baja de 50)
        m = pm.refinar_marca(np.clip(gris, 0, 255).astype(np.uint8), (213.0, 203.0), _P())
        assert m.estado == "sin refinar" and m.punto == m.clic

    @pytest.mark.parametrize("nucleo,esperada", [(0.0, True), (5.0, True), (8.0, True), (14.0, False), (20.0, False), (30.0, False), (60.0, False)])
    def test_la_mancha_solo_es_tinta_si_su_nucleo_es_casi_negro(self, nucleo, esperada):
        """El limite esta en 10 niveles (`gris_maximo_de_la_tinta`): la meseta del campo (24 a 30) y las motas (10 a 18) no son tinta."""
        m = _pm().refinar_marca(parche(fondo=120.0, nucleo=nucleo), (213.0, 207.0), _P())
        assert m.refinada == esperada, (nucleo, m.motivo, m.gris_del_nucleo)

    def test_un_nucleo_que_llega_al_limite_no_es_tinta(self):
        """PROD-02 (revision de la ronda 1): el limite NO se incluye. El decimo mas oscuro de una mancha de pixeles enteros cae con frecuencia justo en un entero, y las motas y el ruido JPEG de EPSON029 y
        ref40 dan EXACTAMENTE 10.0; con `nucleo > limite` pasaban por tinta (un clic a menos de 1.5 mm de una se movia hasta 1.5 mm con estado «refinada»). Se mide el nucleo de una mancha y se pone el
        limite justo en el: ahi ya no es tinta; un pelo por encima si (la comparacion es exacta, independiente del decodificador de JPEG)."""
        pm = _pm()
        gris, clic = parche(fondo=120.0, nucleo=4.0), (213.0, 207.0)
        medida = pm.refinar_marca(gris, clic, _P(gris_maximo_de_la_tinta=255.0))               # sin limite practico: que nucleo da esta mancha
        assert medida.refinada
        nucleo = medida.gris_del_nucleo
        assert 1.0 < nucleo < 10.0, nucleo
        en_el_limite = pm.refinar_marca(gris, clic, _P(gris_maximo_de_la_tinta=nucleo))
        assert en_el_limite.estado == "sin refinar" and en_el_limite.punto == en_el_limite.clic, "un nucleo que LLEGA al limite no es tinta"
        assert en_el_limite.motivo == "sin refinar: no hay una mancha de tinta a menos de 1.5 mm del clic"
        assert not pm.refinar_marca(gris, clic, _P(gris_maximo_de_la_tinta=nucleo - 1e-6)).refinada
        assert pm.refinar_marca(gris, clic, _P(gris_maximo_de_la_tinta=nucleo + 1e-6)).refinada

    @pytest.mark.parametrize("clave,clic", [("EPSON029", (1717, 1448)), ("PLACA_REF40", (2177, 1833)), ("PLACA_REF40", (2232, 563))])
    def test_las_motas_reales_de_epson029_y_ref40_con_nucleo_10_no_se_refinan(self, clave, clic):
        """PROD-02, sobre las peliculas reales: las tres motas que la revision encontro barriendo las paginas enteras (nucleo 10.0, contraste 13 a 15) dejan el clic donde esta. Sin el limite practico se
        ve su nucleo (10.0 con OpenCV 4.11: el decimo mas oscuro de enteros); si un decodificador de JPEG distinto lo bajara de 10 esta prueba lo dira nombrandolo."""
        pm, pel = _pm(), _pelicula_mod()
        gris = pel.leer_pelicula(Path(_real(clave)).read_bytes()).gris
        sin_limite = pm.refinar_marca(gris, clic, _P(gris_maximo_de_la_tinta=255.0))
        m = pm.refinar_marca(gris, clic, _P())
        assert m.estado == "sin refinar" and m.punto == m.clic, (clave, clic, "nucleo de la mota:", sin_limite.gris_del_nucleo, "contraste:", sin_limite.contraste)

    @pytest.mark.parametrize("clic,nucleo_esperado", [((1767, 2635), 7.0), ((2046, 2657), 9.0)])
    def test_la_tinta_real_de_epson030_con_nucleo_7_y_9_si_se_refina(self, clic, nucleo_esperado):
        """El otro lado del margen: dos puntos de rotulador de verdad (el final de los trazos de la fecha escrita a mano en EPSON030, contraste 130) miden 7 y 9, justo debajo del limite de 10. Bajar
        `gris_maximo_de_la_tinta` por debajo de 9 las dejaria sin refinar. Medido por `refinar_marca` en el centro de 941 manchas de las peliculas reales (`c1_corr1_hueco_de_la_compuerta.py` del anexo): lo que se
        toma por tinta llega a 9.7 (ademas, el borde negro de la pelicula de EPSON028) y lo que no lo es empieza en 10.0: un hueco de 0.3 niveles."""
        pm, pel = _pm(), _pelicula_mod()
        gris = pel.leer_pelicula(Path(_real("EPSON030")).read_bytes()).gris
        m = pm.refinar_marca(gris, clic, _P())
        assert m.refinada and m.gris_del_nucleo == pytest.approx(nucleo_esperado, abs=0.5) and m.contraste > 100, (clic, m.motivo, m.gris_del_nucleo, m.contraste)
        assert m.desplazamiento_mm <= 1.5

    def test_el_nivel_del_nucleo_de_la_mancha_aceptada_se_informa(self):
        m = _pm().refinar_marca(parche(nucleo=4.0), (213.0, 207.0), _P())
        assert m.refinada and 2.0 <= m.gris_del_nucleo <= 8.0 and m.contraste > 80

    def test_el_limite_de_oscuridad_es_un_parametro(self):
        pm = _pm()
        gris = parche(fondo=120.0, nucleo=14.0)
        assert not pm.refinar_marca(gris, (213.0, 207.0), _P()).refinada
        assert pm.refinar_marca(gris, (213.0, 207.0), _P(gris_maximo_de_la_tinta=20.0)).refinada
        assert not pm.refinar_marca(parche(fondo=120.0, nucleo=3.0), (213.0, 207.0), _P(gris_maximo_de_la_tinta=1.0)).refinada

    @pytest.mark.parametrize("radio_mm,esperada", [(0.1, False), (0.15, False), (0.22, True), (0.3, True), (0.5, True)])
    def test_una_mota_de_menos_de_0_1_mm2_no_es_una_marca(self, radio_mm, esperada):
        """El area minima es 0.1 mm2 (56 pixeles a 600 dpi): el area de un disco es pi r2, asi que 0.1 mm2 es un disco de 0.18 mm de radio."""
        m = _pm().refinar_marca(parche(radio_px=radio_mm / ESC, borde_px=0.8), (211.0, 206.0), _P())
        assert m.refinada == esperada, (radio_mm, m.motivo, m.area_mm2)

    def test_el_area_minima_es_un_parametro(self):
        pm = _pm()
        gris = parche(radio_px=0.12 / ESC, borde_px=0.8)                   # 0.045 mm2
        assert not pm.refinar_marca(gris, (211.0, 206.0), _P()).refinada
        assert pm.refinar_marca(gris, (211.0, 206.0), _P(area_minima_marca_mm2=0.01)).refinada

    @pytest.mark.parametrize("fondo,esperada", [(3.0, False), (5.0, False), (10.0, True), (16.0, True), (60.0, True)])
    def test_la_tinta_tiene_que_contrastar_10_niveles_con_su_entorno(self, fondo, esperada):
        """El contraste que mide es el del cierre contra el gris: el ruido de 1.5 niveles le suma ~4 (un disco de contraste nominal 8 sobre la pelicula mide 12), asi que el limite de 10 cae
        entre un contraste nominal de 5 (se descarta) y uno de 8 (se acepta)."""
        m = _pm().refinar_marca(parche(fondo=fondo, nucleo=2.0), (212.0, 206.0), _P())
        assert m.refinada == esperada, (fondo, m.motivo, m.contraste)
        if fondo == 3.0:
            assert m.motivo == "sin refinar: no hay una mancha más oscura que su entorno a menos de 1.5 mm del clic"

    def test_el_contraste_minimo_es_un_parametro(self):
        pm = _pm()
        gris = parche(fondo=16.0, nucleo=2.0)                              # contraste medido ~20
        assert pm.refinar_marca(gris, (212.0, 206.0), _P()).refinada
        exigente = pm.refinar_marca(gris, (212.0, 206.0), _P(contraste_minimo_marca=25.0))
        assert not exigente.refinada
        assert exigente.motivo == "sin refinar: no hay una mancha más oscura que su entorno a menos de 1.5 mm del clic", "el motivo es el del contraste: el minimo que se lee es el de `P`, no el 10 de siempre"
        assert pm.refinar_marca(gris, (212.0, 206.0), _P(contraste_minimo_marca=15.0)).refinada

    def test_una_mancha_pegada_al_borde_de_la_imagen_esta_cortada_y_no_se_refina(self):
        pm = _pm()
        cortada = pm.refinar_marca(parche(centro=(210.0, 6.0)), (210.0, 8.0), _P())
        entera = pm.refinar_marca(parche(centro=(210.0, 40.0)), (210.0, 42.0), _P())
        assert cortada.estado == "sin refinar" and entera.refinada
        for centro, clic in (((6.0, 205.0), (8.0, 205.0)), ((414.0, 205.0), (412.0, 205.0)), ((210.0, 414.0), (210.0, 412.0))):
            assert pm.refinar_marca(parche(centro=centro), clic, _P()).estado == "sin refinar", centro

    def test_una_mancha_mas_ancha_que_un_circulo_de_3_mm_no_es_una_marca_de_punto(self):
        pm = _pm()
        ancha = parche(radio_px=2.0 / ESC)                           # 4 mm de diametro
        assert pm.refinar_marca(ancha, (210.0, 205.0), _P()).estado == "sin refinar"
        assert pm.refinar_marca(parche(radio_px=1.1 / ESC), (210.0, 205.0), _P()).refinada            # 2.2 mm de diametro: todavia cabe

    def test_una_barra_de_tinta_mas_larga_que_un_circulo_de_3_mm_no_es_una_marca_de_punto(self):
        """El cierre (un circulo de 3 mm) quita lo angosto aunque sea largo: una barra de 0.8 mm de ancho es «tinta» de cualquier largo, y solo la extension maxima de la mancha (la de un circulo de 3 mm)
        la distingue de una marca: una barra de 2.8 mm todavia es un trazo corto; una de 3.4 y una de 4.4 mm son un rayon, no un punto."""
        pm = _pm()
        corta = pm.refinar_marca(parche(radio_px=0.4 / ESC, semi_largo_px=1.0 / ESC), (213.0, 207.0), _P())
        assert corta.refinada and math.hypot(corta.punto[0] - 210.0, corta.punto[1] - 205.0) * ESC <= 0.02, corta.motivo
        for semi_mm in (1.3, 1.8):
            larga = pm.refinar_marca(parche(radio_px=0.4 / ESC, semi_largo_px=semi_mm / ESC), (213.0, 207.0), _P())
            assert larga.estado == "sin refinar" and larga.punto == larga.clic, semi_mm
            assert larga.motivo == "sin refinar: no hay una mancha de tinta a menos de 1.5 mm del clic", semi_mm

    def test_un_clic_fuera_de_la_imagen_queda_sin_refinar(self):
        pm = _pm()
        gris = parche()
        for clic in ((-3.0, 100.0), (100.0, -0.5), (500.0, 100.0), (100.0, 419.5)):
            m = pm.refinar_marca(gris, clic, _P())
            assert m.estado == "sin refinar" and "fuera de la imagen" in m.motivo and m.punto == m.clic

    def test_un_clic_en_la_esquina_de_la_imagen_no_revienta(self):
        m = _pm().refinar_marca(parche(), (0.0, 0.0), _P())
        assert m.estado == "sin refinar"

    def test_una_forma_equivocada_de_los_argumentos_es_valueerror(self):
        pm = _pm()
        gris = parche()
        with pytest.raises(ValueError):
            pm.refinar_marca(gris[:, :, None], (10.0, 10.0), _P())
        with pytest.raises(ValueError):
            pm.refinar_marca(gris, (float("nan"), 10.0), _P())
        with pytest.raises(ValueError):
            pm.refinar_marca(gris, (10.0, 10.0), {"radio_marca_mm": 1.5})
        for malo in (0.0, -1.0, float("nan"), "x"):
            with pytest.raises(ValueError):
                pm.refinar_marca(gris, (10.0, 10.0), _P(), malo)

    def test_la_mancha_en_las_peliculas_sinteticas_sin_tinta_no_se_refina_nunca(self):
        pm, pel = _pm(), _pelicula_mod()
        placa = gen.generar("png", variante="A", theta_deg=0.4, seed=1, dpi=150, tinta=False)
        gris = pel.leer_pelicula(placa.datos).gris
        for nombre, (mx, my) in placa.verdad.marcas_px.items():
            for ang in np.linspace(0, 2 * math.pi, 6, endpoint=False):
                m = pm.refinar_marca(gris, (mx + 5 * math.cos(ang), my + 5 * math.sin(ang)), _P(), 25.4 / 150)
                assert m.estado == "sin refinar", (nombre, ang, m.punto)


class TestLoTransparenteNoEsTinta:
    """A.1: un alfa menor que el maximo es «sin dato» (`Pelicula.validos`). Lo transparente se ve negro o blanco segun lo que haya debajo: si es negro, es una mancha oscura perfecta. `refinar_marca(...,
    validos=)` no lo toma por tinta, y una mancha que lo toca esta cortada."""

    @staticmethod
    def _bloque(gris, y0, y1, x0, x1):
        sin_dato = np.ones(gris.shape, bool)
        sin_dato[y0:y1, x0:x1] = False
        g = gris.copy()
        g[y0:y1, x0:x1] = 0                                          # transparente, y debajo hay negro
        return g, sin_dato

    def test_un_bloque_negro_sin_dato_es_una_mancha_sin_la_mascara_y_no_lo_es_con_ella(self):
        pm = _pm()
        liso = parche(radio_px=0.001, nucleo=100.0)
        g, validos = self._bloque(liso, 195, 216, 195, 216)
        sin_mascara = pm.refinar_marca(g, (200.0, 203.0), _P())
        assert sin_mascara.refinada, "sin la mascara el bloque negro pasa por tinta: por eso la mascara existe"
        con_mascara = pm.refinar_marca(g, (200.0, 203.0), _P(), validos=validos)
        assert con_mascara.estado == "sin refinar" and con_mascara.punto == con_mascara.clic

    def test_con_la_marca_verdadera_y_un_bloque_sin_dato_mas_cerca_del_clic_gana_la_marca(self):
        pm = _pm()
        g, validos = self._bloque(parche(centro=(235.0, 205.0)), 195, 216, 190, 211)
        sin_mascara = pm.refinar_marca(g, (205.0, 205.0), _P())
        con_mascara = pm.refinar_marca(g, (205.0, 205.0), _P(), validos=validos)
        assert sin_mascara.refinada and abs(sin_mascara.punto[0] - 200.0) < 1.0, "sin la mascara gana el bloque, que esta mas cerca del clic"
        assert con_mascara.refinada and abs(con_mascara.punto[0] - 235.0) < 0.5 and abs(con_mascara.punto[1] - 205.0) < 0.5

    def test_un_bloque_negro_sin_dato_sobre_la_pelicula_clara_no_sube_el_umbral_de_una_marca_debil(self):
        """El maximo de tinta con que se mide el borde de la mancha sale del circulo del clic: un bloque negro sin dato (tinta 200 sobre la pelicula clara) lo subiria a 100 y la marca debil del clic (contraste ~42,
        sobre la pelicula oscura) se perderia si el bloque contara como tinta; sin dato, sigue la pelicula de alrededor y no cuenta."""
        pm = _pm()
        from scipy.ndimage import gaussian_filter
        from scipy.special import erf
        yy, xx = np.mgrid[0:420, 0:420].astype(float)
        fondo = np.full((420, 420), 45.0)
        fondo[:, 250:] = 200.0                                         # oscuro a la izquierda, claro a la derecha (el escalon de la penumbra)
        img = gaussian_filter(fondo, 2.0)
        m = 0.5 * (1 - erf((np.hypot(xx - 230.0, yy - 205.0) - 12.0) / (math.sqrt(2) * 2.4)))
        img = img * (1 - m) + 3.0 * m
        gris = np.clip(np.rint(img + np.random.default_rng(3).normal(0, 1.5, img.shape)), 0, 255).astype(np.uint8)
        g, validos = self._bloque(gris, 195, 216, 258, 279)             # el bloque negro sin dato, sobre lo claro, a 33 px (1.4 mm) del clic
        sin_mascara = pm.refinar_marca(g, (225.0, 205.0), _P())
        con_mascara = pm.refinar_marca(g, (225.0, 205.0), _P(), validos=validos)
        assert not sin_mascara.refinada, "sin la mascara el bloque negro (tinta 200) sube el umbral y la marca debil se pierde"
        assert con_mascara.refinada and abs(con_mascara.punto[0] - 230.0) < 0.5 and abs(con_mascara.punto[1] - 205.0) < 0.5

    def test_una_mancha_que_toca_lo_que_no_tiene_dato_esta_cortada_y_no_se_refina(self):
        pm = _pm()
        gris = parche(centro=(210.0, 205.0))
        validos = np.ones(gris.shape, bool)
        assert pm.refinar_marca(gris, (212.0, 206.0), _P(), validos=validos).refinada
        validos[:, 220:] = False                                     # la transparencia empieza a 10 pixeles del centro: la mancha (radio 12) la toca
        assert pm.refinar_marca(gris, (212.0, 206.0), _P(), validos=validos).estado == "sin refinar"

    def test_un_trozo_sin_dato_dentro_de_la_marca_la_deja_sin_refinar_aunque_el_relleno_la_complete(self):
        """Lo que no tiene dato se rellena con el vecino con dato mas cercano (no es tinta), y el relleno puede completar una marca que la transparencia se comio un pedazo: aun asi la mancha que lo toca esta
        cortada y su centro seria el de una mancha inventada. Un trozo de 11 x 5 pixeles sin dato dentro de la marca (de 24 pixeles de ancho) la deja sin refinar; el mismo trozo a 2.5 mm de ella no la toca."""
        pm = _pm()
        gris = parche(centro=(210.0, 205.0))
        ref = pm.refinar_marca(gris, (212.0, 206.0), _P())
        validos = np.ones(gris.shape, bool)
        validos[200:211, 216:221] = False
        g = gris.copy()
        g[~validos] = 0
        comida = pm.refinar_marca(g, (212.0, 206.0), _P(), validos=validos)
        assert comida.estado == "sin refinar" and comida.punto == comida.clic
        validos = np.ones(gris.shape, bool)
        validos[200:211, 282:287] = False                            # el mismo trozo, a 60 pixeles del centro: lo ve el recorte, pero no toca la marca
        g = gris.copy()
        g[~validos] = 0
        cerca = pm.refinar_marca(g, (212.0, 206.0), _P(), validos=validos)
        assert cerca.refinada and cerca.punto == pytest.approx(ref.punto, abs=1e-6)

    def test_la_transparencia_lejos_de_la_marca_no_cambia_nada(self):
        pm = _pm()
        gris = parche(centro=(210.0, 205.0))
        ref = pm.refinar_marca(gris, (212.0, 206.0), _P())
        validos = np.ones(gris.shape, bool)
        validos[:, 330:] = False                                     # a 120 pixeles: mas lejos de lo que ve el recorte de la marca
        validos[:30, :] = False
        g = gris.copy()
        g[~validos] = 0
        con = pm.refinar_marca(g, (212.0, 206.0), _P(), validos=validos)
        assert con.refinada and con.punto == pytest.approx(ref.punto, abs=1e-9)

    def test_con_todo_valido_da_lo_mismo_que_sin_mascara(self):
        pm = _pm()
        gris = parche(centro=(210.4, 205.7))
        todo = np.ones(gris.shape, bool)
        assert pm.refinar_marca(gris, (213.0, 207.0), _P(), validos=todo).como_dict() == pm.refinar_marca(gris, (213.0, 207.0), _P()).como_dict()

    def test_sin_ningun_pixel_con_dato_alrededor_del_clic_queda_sin_refinar(self):
        pm = _pm()
        gris = parche()
        m = pm.refinar_marca(gris, (210.0, 205.0), _P(), validos=np.zeros(gris.shape, bool))
        assert m.estado == "sin refinar" and "dato" in m.motivo

    def test_una_mascara_de_otra_forma_es_valueerror(self):
        with pytest.raises(ValueError):
            _pm().refinar_marca(parche(), (210.0, 205.0), _P(), validos=np.ones((10, 10), bool))

    def test_la_mascara_de_una_pelicula_con_alfa_es_la_que_entrega_el_lector(self):
        """De punta a punta con el lector: un TIFF RGBA de 8 bits con la esquina transparente (negra debajo) se lee con `validos` y la marca de al lado no se confunde con ella."""
        import tifffile
        pm, pel = _pm(), _pelicula_mod()
        liso = parche(centro=(210.0, 205.0))
        rgb = np.stack([liso] * 3 + [np.full(liso.shape, 255, np.uint8)], axis=-1)
        rgb[195:216, 120:141, :3] = 0                                # un bloque negro...
        rgb[195:216, 120:141, 3] = 0                                 # ...transparente
        import io
        buf = io.BytesIO()
        tifffile.imwrite(buf, rgb, photometric="rgb", resolution=(600, 600), resolutionunit="INCH", compression=None, extrasamples=["unassalpha"])
        pelicula = pel.leer_pelicula(buf.getvalue())
        assert pelicula.transparentes == 21 * 21
        sin = pm.refinar_marca(pelicula.gris, (150.0, 205.0), _P())
        con = pm.refinar_marca(pelicula.gris, (150.0, 205.0), _P(), validos=pelicula.validos)
        assert sin.refinada and abs(sin.punto[0] - 130.0) < 1.5                 # el bloque, tomado por tinta
        assert not con.refinada or abs(con.punto[0] - 210.0) < 1.0              # con la mascara no es el bloque


class TestElRadioDeBusqueda:
    def test_un_radio_de_menos_de_2_pixeles_no_busca_nada(self):
        m = _pm().refinar_marca(parche(), (210.0, 205.0), _P(radio_marca_mm=0.05))
        assert m.estado == "sin refinar" and "menos de 2 píxeles" in m.motivo

    def test_un_radio_absurdo_es_valueerror_y_no_se_cuelga(self):
        with pytest.raises(ValueError):                              # primero en una imagen diminuta: sin la guarda el cierre tardaria ~1 s y la prueba cae en vez de colgarse
            _pm().refinar_marca(np.full((8, 8), 100, np.uint8), (4.0, 4.0), _P(radio_marca_mm=100.0))
        t0 = time.perf_counter()
        with pytest.raises(ValueError):                              # y en una de verdad: el cierre de 4725 pixeles sobre un recorte de 420 x 420 costaria minutos
            _pm().refinar_marca(parche(), (210.0, 205.0), _P(radio_marca_mm=100.0))
        assert time.perf_counter() - t0 < 1.0

    def test_el_radio_maximo_son_1000_pixeles(self):
        """Un radio de busqueda de mas de 1000 pixeles es un error de `P` (el cierre costaria minutos sobre una pagina): 999.9 todavia vale, 1000.1 no. Una imagen chica, para que el cierre quepa."""
        pm = _pm()
        tam = 25.4 / 600
        gris = np.full((60, 60), 100, np.uint8)
        assert pm.refinar_marca(gris, (30.0, 30.0), _P(radio_marca_mm=999.9 * tam)).estado == "sin refinar"
        with pytest.raises(ValueError, match="más de 1000"):
            pm.refinar_marca(gris, (30.0, 30.0), _P(radio_marca_mm=1000.1 * tam))

    def test_un_gris_diminuto_no_revienta(self):
        pm = _pm()
        assert pm.refinar_marca(np.zeros((1, 1), np.uint8), (0.0, 0.0), _P()).estado == "sin refinar"
        assert pm.refinar_marca(np.zeros((0, 0), np.uint8), (0.0, 0.0), _P()).estado == "sin refinar"
        assert pm.refinar_marca(np.zeros((3, 40), np.uint8), (20.0, 1.0), _P()).estado == "sin refinar"


@pytest.fixture(scope="module", params=[("A", 0.4, "png", 150), ("L", -3.0, "png", 150), ("B", 1.0, "jpeg", 300), ("D", 0.0, "jpeg", 150), ("E", -3.0, "png", 300)],
                ids=["A-0.4-150", "L--3-150", "B-1-jpeg-300", "D-0-jpeg-150", "E--3-300"])
def placa(request):
    variante, theta, formato, dpi = request.param
    p = gen.generar(formato, variante=variante, theta_deg=theta, seed=3, dpi=dpi)
    return p.verdad, _pelicula_mod().leer_pelicula(p.datos).gris, 25.4 / dpi


class TestMarcasDeLasPeliculasSinteticas:
    """(d) sobre las peliculas de PF.0 (la verdad de cada marca es `verdad.marcas_px`, el centro del disco de tinta)."""

    def test_d_los_clics_a_1_mm_vuelven_al_centro_de_cada_marca_sintetica(self, placa):
        verdad, gris, tam = placa
        pm = _pm()
        for nombre, (mx, my) in verdad.marcas_px.items():
            for ang in np.linspace(0, 2 * math.pi, 8, endpoint=False):
                for r_mm in (0.0, 0.5, 1.0):
                    clic = (mx + r_mm / tam * math.cos(ang), my + r_mm / tam * math.sin(ang))
                    m = pm.refinar_marca(gris, clic, _P(), tam)
                    assert m.refinada, (nombre, r_mm, ang, m.motivo)
                    assert math.hypot(m.punto[0] - mx, m.punto[1] - my) * tam <= 0.05, (nombre, r_mm, ang)

    def test_d_a_1_6_mm_o_mas_la_marca_ya_no_es_la_del_clic(self, placa):
        verdad, gris, tam = placa
        pm = _pm()
        mx, my = verdad.marcas_px["UL"]
        for lejos in (1.7, 2.2):
            m = pm.refinar_marca(gris, (mx + lejos / tam, my), _P(), tam)
            assert m.estado == "sin refinar", lejos


def _pico_de_una_llamada(funcion):
    """(lo que devuelve `funcion()`, el pico de memoria en bytes que alcanza por ENCIMA de lo que ya habia). Sirve con `tracemalloc` apagado (lo enciende y lo apaga) y con el ya encendido desde afuera
    (`PYTHONTRACEMALLOC=1`, `python -X tracemalloc`): entonces ni lo reinicia ni lo apaga, y no cuenta lo que ya estaba reservado (la pagina de la propia prueba) ni un pico anterior (`reset_peak`)."""
    estaba_encendido = tracemalloc.is_tracing()
    if not estaba_encendido:
        tracemalloc.start()
    try:
        antes = tracemalloc.get_traced_memory()[0]
        tracemalloc.reset_peak()
        resultado = funcion()
        pico = tracemalloc.get_traced_memory()[1]
    finally:
        if not estaba_encendido:
            tracemalloc.stop()
    return resultado, pico - antes


class TestCostoDeRefinarSobreUnaPaginaEntera:
    """El costo: `refinar_marca` trabaja sobre un recorte local de la marca, no sobre la pagina entera (6600 x 5100). Medido el 17-10 con la pagina real EPSON027: 20 ms y 1.4 MB de pico por marca."""

    def test_el_medidor_de_pico_cuenta_solo_la_llamada_con_tracemalloc_apagado_o_ya_encendido(self):
        """R1P-05 (revision de la ronda 1): con `PYTHONTRACEMALLOC=1` la prueba de la pagina daba un falso rojo (83.4 MB: el `np.full` de la propia prueba y no la llamada) y, ademas, apagaba el rastreo del
        usuario. El medidor cuenta SOLO el pico de la llamada, con el rastreo apagado o ya encendido, y no cambia si estaba encendido."""
        desde_afuera = tracemalloc.is_tracing()                           # PYTHONTRACEMALLOC=1, python -X tracemalloc...: no es nuestro y no se toca
        for ya_encendido in ([True] if desde_afuera else [False, True]):
            if ya_encendido and not desde_afuera:
                tracemalloc.start()
            try:
                previo = np.zeros(40_000_000, np.uint8)                   # 40 MB reservados ANTES de medir: con el rastreo ya encendido los ve y no son de la llamada
                temporal = np.zeros(60_000_000, np.uint8)                 # y un pico ANTERIOR mayor que el de la llamada: sin `reset_peak` contaminaria la medida
                del temporal
                resultado, pico = _pico_de_una_llamada(lambda: bytearray(6_000_000))
                assert len(resultado) == 6_000_000 and previo.size == 40_000_000
                assert 5.5e6 <= pico < 8.5e6, (ya_encendido, pico)        # los 6 MB de la llamada y no los 40 ni los 100 de antes
                assert tracemalloc.is_tracing() == (ya_encendido or desde_afuera), "el medidor ni apaga lo que estaba encendido ni deja encendido lo que estaba apagado"
            finally:
                if ya_encendido and not desde_afuera:
                    tracemalloc.stop()
        assert tracemalloc.is_tracing() == desde_afuera

    def test_una_pagina_de_6600_x_5100_no_se_copia_ni_se_recorre(self):
        pm = _pm()
        pagina = np.full((5100, 6600), 150, np.uint8)
        pagina[2540:2560, 3290:3310] = 2                                    # una marca de tinta de ~0.9 mm
        t = time.perf_counter()
        m, pico = _pico_de_una_llamada(lambda: pm.refinar_marca(pagina, (3303.0, 2545.0), _P()))
        segundos = time.perf_counter() - t
        assert m.refinada and m.punto == pytest.approx((3299.5, 2549.5), abs=0.6)
        assert pico < 8e6, f"el pico de {pico / 1e6:.1f} MB no es el de un recorte (la pagina entera en float32 serian 135 MB)"
        assert segundos < 1.0, segundos

    def test_los_pixeles_de_la_pagina_lejos_de_la_marca_no_cambian_el_resultado(self):
        pm = _pm()
        a = np.full((900, 900), 150, np.uint8)
        a[440:460, 440:460] = 2
        b = np.full((5100, 6600), 40, np.uint8)
        b[3000:3900, 3000:3900] = a
        ra = pm.refinar_marca(a, (452.0, 449.0), _P())
        rb = pm.refinar_marca(b, (3452.0, 3449.0), _P())
        assert ra.refinada and rb.refinada
        assert (rb.punto[0] - 3000.0, rb.punto[1] - 3000.0) == pytest.approx(ra.punto, abs=1e-9)


# ------------------------------------------------------------------------------------------------------------------------------ (e) el pivote
@pytest.fixture(scope="module")
def clasificado():
    c = _pm().clasificar_puntos(CLICS_ML0)
    return c.esquinas, c.reticulo


class TestElPivoteNoCambiaNingunaMedida:
    """(e) R2.2: girar alrededor del cruce de diagonales, del centro de la imagen o de la esquina (0, 0) da las mismas longitudes, angulos y desfases."""

    PIVOTES = [None, (1345.0, 1355.0), (0.0, 0.0), (5000.0, -300.0), (1371.0, 1330.0), (1354.52307506465, 1315.44524077355), (-80000.0, 90000.0)]

    CAMPOS = ("angulo_grados", "angulos_de_las_diagonales_grados", "desviacion_de_las_diagonales_grados", "lados_mm", "angulos_interiores_grados", "diagonales_mm",
              "inclinacion_de_los_lados_grados", "luz_menos_reticulo_imagen_mm", "luz_menos_reticulo_girado_mm", "luz_menos_reticulo_modulo_mm", "cruce")

    def test_e_ninguna_medida_cambia_con_el_pivote(self, clasificado):
        esq, ret = clasificado
        ref = geometria(esq, ret, pivote=None)
        for pivote in self.PIVOTES:
            g = geometria(esq, ret, pivote=pivote)
            for campo in self.CAMPOS:
                a, b = getattr(ref, campo), getattr(g, campo)
                if isinstance(a, dict):
                    a, b = list(a.values()), list(b.values())
                assert b == pytest.approx(a, abs=1e-7, rel=0), (campo, pivote)

    def test_e_con_cualquier_pivote_los_numeros_de_r2_son_los_mismos(self, clasificado):
        esq, ret = clasificado
        for pivote in self.PIVOTES:
            g = geometria(esq, ret, pivote=pivote)
            assert g.luz_menos_reticulo_girado_mm == pytest.approx((-0.7018, -0.6112), abs=5e-4), pivote           # R2.2
            assert g.angulo_grados == pytest.approx(0.403, abs=5e-4)

    def test_e_lo_unico_que_depende_del_pivote_son_las_posiciones_de_los_puntos_girados(self, clasificado):
        esq, ret = clasificado
        pm = _pm()
        for pivote in self.PIVOTES[1:]:
            g = geometria(esq, ret, pivote=pivote)
            assert g.pivote == pytest.approx(pivote)
            o = oraculo(esq, ret, ESC, pivote=pivote)
            assert [c for p in g.esquinas_giradas for c in p] == pytest.approx([c for p in o["esquinas_giradas"] for c in p], abs=1e-6)
            assert g.reticulo_girado == pytest.approx(o["reticulo_girado"], abs=1e-6)
            assert np.array(g.matriz_de_giro) == pytest.approx(pm.matriz_giro(pivote, g.angulo_grados))
            assert pm.transformar_puntos(g.matriz_de_giro, [pivote])[0] == pytest.approx(pivote, abs=1e-6)         # el pivote queda fijo
        a, b = geometria(esq, ret, pivote=(0.0, 0.0)), geometria(esq, ret, pivote=(3000.0, 2000.0))
        assert a.esquinas_giradas != b.esquinas_giradas

    def test_e_el_mismo_resultado_con_cualquier_pivote_en_los_cuadrilateros_sinteticos(self):
        for theta in GIROS:
            esq, ret = rectangulo(99.6, 99.8, theta, reticulo_mm=(0.3, -0.2))
            ref = geometria(esq, ret)
            for pivote in ((0.0, 0.0), (1345.0, 1355.0), (-4000.0, 7000.0)):
                g = geometria(esq, ret, pivote=pivote)
                assert g.luz_menos_reticulo_girado_mm == pytest.approx(ref.luz_menos_reticulo_girado_mm, abs=1e-7)
                assert list(g.inclinacion_de_los_lados_grados.values()) == pytest.approx([0.0] * 4, abs=1e-8)
                assert g.angulo_grados == pytest.approx(theta, abs=1e-9)


# -------------------------------------------------------------------------------------------------------------------------- la matriz del giro
class TestMatrizDelGiro:
    """`matriz_giro` es la de `cv2.getRotationMatrix2D` en flotante: una sola definicion para la imagen (`warpAffine`) y para los puntos."""

    @pytest.mark.parametrize("angulo", [0.0, 0.403, -3.0, 1.0, 45.0, -90.0, 180.0, 360.0, 721.5])
    @pytest.mark.parametrize("centro", [(0.0, 0.0), (1354.0, 1315.0), (3000.0, -20.0), (-5.0, 400.0)])
    def test_es_la_de_opencv_con_centros_enteros_exactos(self, angulo, centro):
        M = _pm().matriz_giro(centro, angulo)
        esperada = cv2.getRotationMatrix2D(centro, angulo, 1.0)
        assert M.shape == (2, 3) and M.dtype == np.float64
        assert M == pytest.approx(esperada, abs=1e-9)

    def test_con_un_centro_decimal_es_la_de_opencv_salvo_su_redondeo_a_float32(self):
        pm = _pm()
        centro, angulo = (1354.52307506465, 1315.44524077355), 0.4025223546352237
        M = pm.matriz_giro(centro, angulo)
        assert M == pytest.approx(cv2.getRotationMatrix2D(centro, angulo, 1.0), abs=2e-4)
        # pero en flotante de 64 bits el centro queda FIJO a 1e-9, que con el float32 de OpenCV no pasa de 1e-4
        assert pm.transformar_puntos(M, [centro])[0] == pytest.approx(centro, abs=1e-9)

    def test_un_angulo_positivo_gira_en_sentido_antihorario_en_la_pantalla_con_la_y_hacia_abajo(self):
        pm = _pm()
        arriba = pm.transformar_puntos(pm.matriz_giro((0.0, 0.0), 90.0), [(10.0, 0.0)])[0]          # un punto a la derecha del centro pasa a estar ARRIBA (y negativa)
        assert arriba == pytest.approx((0.0, -10.0), abs=1e-12)
        assert pm.transformar_puntos(pm.matriz_giro((0.0, 0.0), -90.0), [(10.0, 0.0)])[0] == pytest.approx((0.0, 10.0), abs=1e-12)

    def test_transformar_puntos_es_cv2_transform_y_warpaffine_a_la_imagen(self):
        pm = _pm()
        M = pm.matriz_giro((1354.52307506465, 1315.44524077355), 0.4025223546352237)
        puntos = [(196.0, 143.0), (2542.0, 147.0), (1371.0, 1330.0), (2526.0, 2501.0), (171.0, 2480.0)]
        assert np.array(pm.transformar_puntos(M, puntos)) == pytest.approx(cv2.transform(np.array(puntos, np.float64).reshape(-1, 1, 2), M).reshape(-1, 2), abs=1e-9)
        # la imagen: un punto blanco girado con warpAffine cae donde `transformar_puntos` dice
        img = np.zeros((300, 300), np.float32)
        img[100, 200] = 1.0
        M2 = pm.matriz_giro((150.0, 150.0), 20.0)
        rot = cv2.warpAffine(img, M2, (300, 300), flags=cv2.INTER_LINEAR)
        y, x = np.unravel_index(np.argmax(rot), rot.shape)
        esperado = pm.transformar_puntos(M2, [(200.0, 100.0)])[0]
        assert (x, y) == (round(esperado[0]), round(esperado[1]))

    @pytest.mark.parametrize("malo", [None, (1.0,), (float("nan"), 2.0), "ab", (1, 2, 3)])
    def test_un_centro_equivocado_es_valueerror(self, malo):
        with pytest.raises(ValueError):
            _pm().matriz_giro(malo, 1.0)

    @pytest.mark.parametrize("malo", [None, "x", float("nan"), float("inf")])
    def test_un_angulo_equivocado_es_valueerror(self, malo):
        with pytest.raises(ValueError):
            _pm().matriz_giro((0.0, 0.0), malo)

    def test_transformar_puntos_con_una_matriz_de_otra_forma_es_valueerror(self):
        with pytest.raises(ValueError):
            _pm().transformar_puntos(np.eye(3), [(0.0, 0.0)])


# -------------------------------------------------------------------------------------------------------------------------------- (f) el recuadro
@pytest.fixture(scope="module")
def marcas():
    """Cinco marcas (UL, UR, C, DR, DL de ML0) con el punto REFINADO distinto del clic (movido unos pixeles)."""
    pm = _pm()
    moves = [(-0.6, -2.0), (-3.4, -2.6), (-6.4, -9.8), (-0.3, -1.2), (-0.4, 0.7)]
    return [pm.MarcaRefinada("refinada", (float(x), float(y)), (x + dx, y + dy), math.hypot(dx, dy), math.hypot(dx, dy) * ESC, 35.4)
            for (x, y), (dx, dy) in zip(CLICS_ML0, moves)]


class TestRecuadroLuminoso:
    """(f): `recuadro_luminoso` es la UNICA definicion del recuadro: las cuatro esquinas con que se midio, en el orden UL, UR, DR, DL, o el motivo."""

    def test_f_las_120_permutaciones_dan_el_mismo_recuadro(self, marcas):
        pm = _pm()
        ref = pm.recuadro_luminoso(marcas)
        assert ref.ok and len(ref.esquinas) == 4
        for perm in itertools.permutations(range(5)):
            r = pm.recuadro_luminoso([marcas[i] for i in perm])
            assert r.como_dict() == ref.como_dict(), perm

    def test_f_el_recuadro_es_el_de_los_puntos_refinados_no_el_de_los_clics(self, marcas):
        pm = _pm()
        r = pm.recuadro_luminoso(marcas)
        refinados = [marcas[0].punto, marcas[1].punto, marcas[3].punto, marcas[4].punto]
        clics = [marcas[0].clic, marcas[1].clic, marcas[3].clic, marcas[4].clic]
        assert list(r.esquinas) == pytest.approx(refinados, abs=1e-9)
        assert list(r.esquinas) != pytest.approx(clics, abs=0.5), "los clics y los puntos refinados difieren: el recuadro no puede salir de los clics"
        assert r.estado == "ok" and r.ok

    def test_f_con_una_marca_sin_refinar_usa_el_clic_en_su_lugar(self, marcas):
        pm = _pm()
        UR = marcas[1]
        sin = pm.MarcaRefinada("sin refinar", UR.clic, UR.clic, 0.0, 0.0, 35.4, "sin refinar: no hay una mancha de tinta a menos de 1.5 mm del clic")
        r = pm.recuadro_luminoso([marcas[0], sin, marcas[2], marcas[3], marcas[4]])
        assert r.ok
        assert r.esquinas == (marcas[0].punto, UR.clic, marcas[3].punto, marcas[4].punto)

    def test_f_las_esquinas_salen_en_el_orden_superior_izquierda_superior_derecha_inferior_derecha_inferior_izquierda(self, marcas):
        r = _pm().recuadro_luminoso(marcas)
        ul, ur, dr, dl = r.esquinas
        assert ul[0] < ur[0] and ul[1] < dl[1] and dr[0] > dl[0] and dr[1] > ur[1]
        assert ul[1] < dr[1] and ur[0] > dl[0]

    def test_f_con_los_dos_formatos_guardados_da_lo_mismo_diccionarios_como_dict_y_json(self, marcas):
        pm = _pm()
        ref = pm.recuadro_luminoso(marcas)
        guardadas = [m.como_dict() for m in marcas]
        assert pm.recuadro_luminoso(guardadas).como_dict() == ref.como_dict()
        ida_y_vuelta = json.loads(json.dumps(guardadas))
        assert np.array(pm.recuadro_luminoso(ida_y_vuelta).esquinas) == pytest.approx(np.array(ref.esquinas), abs=1e-9)

    def test_f_una_marca_guardada_sin_su_punto_es_valueerror(self):
        pm = _pm()
        marcas = [{"clic": [0, 0]}, (10, 0), (10, 10), (0, 10), (5, 5)]
        with pytest.raises(ValueError):
            pm.recuadro_luminoso(marcas)

    def test_f_con_puntos_que_no_forman_el_campo_da_el_motivo_y_ninguna_esquina(self):
        pm = _pm()
        r = pm.recuadro_luminoso([(0, 0), (100, 0), (100, 100), (60, 40), (65, 35)])
        assert not r.ok and r.esquinas == ()
        assert r.estado.startswith("no medible: los puntos no forman el campo")
        assert r.como_dict() == {"estado": r.estado, "esquinas": []}

    def test_f_el_recuadro_de_un_clic_cualquiera_es_el_de_su_clasificacion(self):
        pm = _pm()
        c = pm.clasificar_puntos(CLICS_ML0)
        assert pm.recuadro_luminoso(CLICS_ML0).esquinas == c.esquinas

    def test_f_el_recuadro_y_la_geometria_ven_las_mismas_esquinas(self, marcas):
        pm = _pm()
        r = pm.recuadro_luminoso(marcas)
        c = pm.clasificar_puntos(marcas)
        g = pm.geometria_luz(c.esquinas, c.reticulo, ESC)
        assert r.esquinas == c.esquinas == g.esquinas


# -------------------------------------------------------------------------------------------------------------- la forma de lo que se devuelve
def _a_json(x):
    """Lo que `json` haria con el resultado de `dataclasses.asdict`: las tuplas son listas, en el MISMO orden. Otro camino que el `como_dict()` de cada clase (que arma sus listas a mano)."""
    if isinstance(x, dict):
        return {k: _a_json(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [_a_json(v) for v in x]
    return x


class TestLoQueDevuelven:
    def test_como_dict_es_el_resultado_mismo_con_x_antes_que_y(self):
        """R1P-01 (revision de la ronda 1): `como_dict()` es el contrato de serializacion que D.1, E.1 y F.1 consumen y ninguna prueba miraba sus VALORES (solo las llaves): con x e y traspuestos pasaban
        las 269. Aqui cada resultado se compara, valor por valor y en su orden, con el que sale de `dataclasses.asdict` (otro camino: las tuplas pasan a listas) y los de ML0 se fijan a mano (con x distinta de y, para que se vea una traspuesta)."""
        pm = _pm()
        c = pm.clasificar_puntos(CLICS_ML0)
        g = pm.geometria_luz(c.esquinas, c.reticulo, ESC)
        recuadro = pm.recuadro_luminoso(CLICS_ML0)
        marca = pm.refinar_marca(parche(), (212.0, 207.0), _P())
        sin_refinar = pm.refinar_marca(parche(radio_px=0.001, nucleo=100.0), (212.0, 207.0), _P())
        for objeto in (c, g, recuadro, marca, sin_refinar, pm.clasificar_puntos([(0, 0), (100, 0), (100, 100), (60, 40), (65, 35)]), pm.geometria_luz([(0, 0), (100, 0), (100, 100), (0, 100)], (150.0, 50.0), ESC)):
            assert objeto.como_dict() == _a_json(dataclasses.asdict(objeto)), type(objeto).__name__
        esquinas = [[196.0, 143.0], [2542.0, 147.0], [2526.0, 2501.0], [171.0, 2480.0]]                       # UL, UR, DR, DL de ML0: x primero, y despues
        assert c.como_dict()["reticulo"] == [1371.0, 1330.0] and c.como_dict()["esquinas"] == esquinas
        assert recuadro.como_dict()["esquinas"] == esquinas
        d = g.como_dict()
        assert d["reticulo"] == [1371.0, 1330.0] and d["esquinas"] == esquinas and d["tam_mm"] == ESC
        assert d["cruce"] == pytest.approx([1354.523, 1315.445], abs=5e-4) and d["pivote"] == d["cruce"]
        assert d["angulos_de_las_diagonales_grados"] == pytest.approx([45.342, -44.537], abs=5e-4)
        assert d["luz_menos_reticulo_imagen_mm"] == pytest.approx([-0.698, -0.616], abs=5e-4)
        assert d["luz_menos_reticulo_girado_mm"] == pytest.approx([-0.7018, -0.6112], abs=5e-4)
        assert d["lados_mm"] == pytest.approx({"superior": 99.314, "derecho": 99.655, "inferior": 99.699, "izquierdo": 98.939}, abs=5e-4)
        assert len(d["matriz_de_giro"]) == 2 and all(len(fila) == 3 for fila in d["matriz_de_giro"]) and d["matriz_de_giro"] == _a_json(g.matriz_de_giro)
        assert d["esquinas_giradas"] == _a_json(g.esquinas_giradas) and d["reticulo_girado"] == list(g.reticulo_girado)
        # una marca: el clic tal como se marco y el punto con que se mide, cada uno con su x primero (x distinta de y, para que una traspuesta se vea)
        dm = marca.como_dict()
        assert dm["clic"] == [212.0, 207.0] and dm["punto"] == [marca.punto[0], marca.punto[1]] and dm["punto"][0] != dm["punto"][1]
        assert sin_refinar.como_dict()["clic"] == sin_refinar.como_dict()["punto"] == [212.0, 207.0]

    def test_como_dict_es_json_y_lleva_todo(self):
        pm = _pm()
        c = pm.clasificar_puntos(CLICS_ML0)
        g = pm.geometria_luz(c.esquinas, c.reticulo, ESC)
        sin_refinar = pm.refinar_marca(parche(radio_px=0.001, nucleo=100.0), (212.0, 207.0), _P())
        for objeto in (c, g, pm.recuadro_luminoso(CLICS_ML0), pm.refinar_marca(parche(), (212.0, 207.0), _P()), sin_refinar):
            texto = json.dumps(objeto.como_dict())
            assert json.loads(texto) == objeto.como_dict()
            assert set(objeto.como_dict()) == {campo.name for campo in dataclasses.fields(objeto)}, "el diccionario lleva TODOS los campos del resultado, ni uno mas ni uno menos"
        assert sin_refinar.como_dict()["motivo"].startswith("sin refinar") and sin_refinar.como_dict()["estado"] == "sin refinar"
        d = g.como_dict()
        assert set(d) == {"estado", "esquinas", "reticulo", "cruce", "tam_mm", "angulo_grados", "angulos_de_las_diagonales_grados", "desviacion_de_las_diagonales_grados", "lados_mm",
                          "angulos_interiores_grados", "diagonales_mm", "inclinacion_de_los_lados_grados", "luz_menos_reticulo_imagen_mm", "luz_menos_reticulo_girado_mm",
                          "luz_menos_reticulo_modulo_mm", "matriz_de_giro", "pivote", "esquinas_giradas", "reticulo_girado"}
        assert list(d["lados_mm"]) == list(LADOS) and list(d["angulos_interiores_grados"]) == list(ESQUINAS) and list(d["inclinacion_de_los_lados_grados"]) == list(LADOS)

    def test_los_resultados_son_inmutables_y_no_comparten_nada_con_la_entrada(self):
        pm = _pm()
        entrada = [list(p) for p in CLICS_ML0]
        c = pm.clasificar_puntos(entrada)
        entrada[0][0] = 99999
        assert c.esquinas[0] == (196.0, 143.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.estado = "otra cosa"
        g = pm.geometria_luz(c.esquinas, c.reticulo, ESC)
        with pytest.raises(dataclasses.FrozenInstanceError):
            g.angulo_grados = 5.0
        with pytest.raises(dataclasses.FrozenInstanceError):
            pm.recuadro_luminoso(CLICS_ML0).estado = "otra cosa"
        marca = pm.refinar_marca(parche(), (212.0, 207.0), _P())
        with pytest.raises(dataclasses.FrozenInstanceError):
            marca.punto = (0.0, 0.0)

    def test_la_geometria_de_unos_puntos_que_no_forman_el_campo_dice_no_medible_y_nada_mas(self):
        pm = _pm()
        g = pm.geometria_luz([(0, 0), (100, 0), (100, 100), (60, 40)], (65.0, 35.0), ESC)
        assert not g.ok and g.estado.startswith("no medible: los puntos no forman el campo")
        assert g.angulo_grados is None and g.lados_mm is None and g.cruce is None and g.matriz_de_giro is None
        g2 = pm.geometria_luz([(0, 0), (100, 0), (100, 100), (0, 100)], (150.0, 50.0), ESC)
        assert not g2.ok and "retículo" in g2.estado

    def test_sin_escala_la_geometria_dice_no_medible_con_su_motivo(self):
        pm = _pm()
        c = pm.clasificar_puntos(CLICS_ML0)
        g = pm.geometria_luz(c.esquinas, c.reticulo, None)
        assert not g.ok and g.estado.startswith("no medible") and "escala" in g.estado and g.lados_mm is None

    def test_la_geometria_no_medible_trae_solo_lo_que_dice_su_documentacion(self):
        """PROD-03 (revision de la ronda 1): la documentacion de `GeometriaLuz` decia de TODO «no medible» que «nada mas trae valor» y, sin escala, el objeto trae las esquinas ordenadas y el reticulo (un
        consumidor que siguiera la documentacion los ignoraria). Dos razones, dos contenidos: sin campo, nada; sin escala, `esquinas` y `reticulo` y ninguna medida (ni el angulo ni los angulos
        interiores, que no dependen de la escala). La documentacion tiene que decirlo."""
        pm = _pm()
        c = pm.clasificar_puntos(CLICS_ML0)
        sin_campo = pm.geometria_luz([(0, 0), (100, 0), (100, 100), (60, 40)], (65.0, 35.0), ESC)
        sin_escala = pm.geometria_luz(c.esquinas, c.reticulo, None)

        def trae(g):
            return {k for k, v in g.como_dict().items() if k != "estado" and v not in (None, [])}

        assert trae(sin_campo) == set()
        assert trae(sin_escala) == {"esquinas", "reticulo"}, trae(sin_escala)
        assert sin_escala.esquinas == c.esquinas and sin_escala.reticulo == c.reticulo
        assert sin_escala.angulo_grados is None and sin_escala.angulos_interiores_grados is None and sin_escala.cruce is None and sin_escala.tam_mm is None
        doc = " ".join(pm.GeometriaLuz.__doc__.split())
        assert "nada más trae valor" in doc, "lo que se dice de los puntos que no forman el campo"
        assert re.search(r"sin escala[^.]*`esquinas` y `reticulo`", doc, re.IGNORECASE), "lo que se dice del «no medible» por falta de escala: la documentacion tiene que nombrar lo que trae"

    @pytest.mark.parametrize("malo", [0.0, -0.04, float("nan"), "x", float("inf")])
    def test_una_escala_equivocada_es_valueerror(self, malo):
        c = _pm().clasificar_puntos(CLICS_ML0)
        with pytest.raises(ValueError):
            _pm().geometria_luz(c.esquinas, c.reticulo, malo)

    @pytest.mark.parametrize("esquinas", [[(0, 0), (1, 0), (1, 1)], [(0, 0)] * 5, 3, None])
    def test_unas_esquinas_equivocadas_son_valueerror(self, esquinas):
        with pytest.raises(ValueError):
            _pm().geometria_luz(esquinas, (0.5, 0.5), ESC)

    def test_las_longitudes_son_proporcionales_a_la_escala_y_los_angulos_no_dependen_de_ella(self):
        pm = _pm()
        c = pm.clasificar_puntos(CLICS_ML0)
        a = pm.geometria_luz(c.esquinas, c.reticulo, ESC)
        b = pm.geometria_luz(c.esquinas, c.reticulo, 2 * ESC)
        assert list(b.lados_mm.values()) == pytest.approx([2 * v for v in a.lados_mm.values()], abs=1e-9)
        assert b.diagonales_mm == pytest.approx(tuple(2 * v for v in a.diagonales_mm), abs=1e-9)
        assert b.luz_menos_reticulo_imagen_mm == pytest.approx(tuple(2 * v for v in a.luz_menos_reticulo_imagen_mm), abs=1e-9)
        assert b.angulo_grados == a.angulo_grados and b.angulos_interiores_grados == a.angulos_interiores_grados


# ------------------------------------------------------------------------------------------------------------------- los parametros y la estructura
class TestLosParametros:
    def test_cada_parametro_tiene_nombre_unidad_y_motivo(self):
        pm = _pm()
        assert pm.VERSION_ALGORITMO == "PM-1"
        for nombre, p in pm.PARAMETROS.items():
            assert set(p) == {"valor", "unidad", "motivo"}, nombre
            assert isinstance(p["unidad"], str) and p["unidad"].strip(), nombre
            assert isinstance(p["motivo"], str) and len(p["motivo"].strip()) >= 40, nombre

    def test_el_diccionario_plano_es_el_de_los_valores_y_no_comparte_nada_con_la_tabla(self):
        pm = _pm()
        assert set(pm.VALORES_DE_LA_GEOMETRIA) == set(pm.PARAMETROS)
        for nombre, p in pm.PARAMETROS.items():
            assert pm.VALORES_DE_LA_GEOMETRIA[nombre] == p["valor"], nombre
        pm.VALORES_DE_LA_GEOMETRIA["resoluciones_de_editor_dpi"].append(1.0)
        try:
            assert pm.PARAMETROS["resoluciones_de_editor_dpi"]["valor"] == [72.0, 96.0]
        finally:
            pm.VALORES_DE_LA_GEOMETRIA["resoluciones_de_editor_dpi"].remove(1.0)
        json.dumps(pm.VALORES_DE_LA_GEOMETRIA)                    # viaja como JSON con cada analisis

    def test_los_valores_de_la_mancha_son_los_del_plan(self):
        v = _pm().VALORES_DE_LA_GEOMETRIA
        assert v["radio_marca_mm"] == 1.5
        assert (v["contraste_minimo_marca"], v["fraccion_del_contraste_marca"], v["gris_maximo_de_la_tinta"], v["borde_blando_marca_mm"], v["area_minima_marca_mm2"]) == (10.0, 0.5, 10.0, 0.15, 0.1)

    def test_el_plano_lleva_la_escala_del_procedimiento_y_los_veintidos_del_piso(self):
        pm, pel = _pm(), _pelicula_mod()
        v = pm.VALORES_DE_LA_GEOMETRIA
        assert all(k in v for k in pel.CLAVES_DE_LA_ESCALA)
        assert (v["resolucion_escaneo_dpi"], v["resoluciones_de_editor_dpi"], v["tolerancia_dpi_relativa"]) == (600.0, [72.0, 96.0], 0.01)
        assert len(pel.VALORES_DEL_PISO) == 22
        assert all(v[k] == pel.VALORES_DEL_PISO[k] for k in pel.VALORES_DEL_PISO)

    def test_la_escala_es_la_del_motor_de_la_posicion_inicial_una_sola_definicion_del_procedimiento(self):
        from analisisImagenes import posicion_inicial_braqui as braqui
        v = _pm().VALORES_DE_LA_GEOMETRIA
        for k in _pelicula_mod().CLAVES_DE_LA_ESCALA:
            assert v[k] == braqui.PARAMETROS[k], k

    def test_la_escala_por_omision_es_25_4_entre_600_y_nadie_mas_divide_25_4(self):
        pm, pel = _pm(), _pelicula_mod()
        assert pel.escala_mm(None, pm.VALORES_DE_LA_GEOMETRIA) == pytest.approx(25.4 / 600)
        constantes = [n.value for n in ast.walk(ast.parse(MODULO.read_text(encoding="utf-8"))) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
        assert 25.4 not in constantes, "una resolucion se vuelve escala en UN solo lugar (`pelicula.escala_mm`)"

    def test_un_mismo_diccionario_alimenta_refinar_marca_escala_y_el_piso(self, cadena):
        """La convergencia de los tres caminos: `refinar_marca`, `escala_mm` y `piso_de_pelicula` aceptan el MISMO `P` sin que le falte nada, sobre una pelicula de 600 dpi."""
        pm, pel = _pm(), _pelicula_mod()
        theta, _, _, marcas, c, g, pelicula = cadena
        P = pm.VALORES_DE_LA_GEOMETRIA
        assert pel.escala_mm(pelicula.dpi, P) == pytest.approx(25.4 / 600)
        piso = pel.piso_de_pelicula(pelicula, c.esquinas, P)
        assert piso.estado == "ok", piso.estado
        assert piso.escala_mm == pytest.approx(ESC) and piso.parametros["margen_campo_mm"] == P["margen_campo_mm"]
        assert all(piso.valor(capa) is not None for capa in ("R", "G", "B", "gris"))

    def test_cada_parametro_propio_se_usa_en_alguna_funcion(self):
        """PD1: nada escondido ni muerto. Todo `P["x"]` del modulo es un parametro de `PARAMETROS` y cada parametro propio (no del piso) lo lee alguna funcion."""
        pm, pel = _pm(), _pelicula_mod()
        arbol = ast.parse(MODULO.read_text(encoding="utf-8"))
        usados = {n.slice.value for n in ast.walk(arbol) if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "P"
                  and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
        assert usados, "no hay ningun P['...'] en el modulo"
        assert usados <= set(pm.PARAMETROS), usados - set(pm.PARAMETROS)
        propios = set(pm.PARAMETROS) - set(pel.PARAMETROS_DEL_PISO) - set(pel.CLAVES_DE_LA_ESCALA)
        assert propios == {"radio_marca_mm", "contraste_minimo_marca", "fraccion_del_contraste_marca", "gris_maximo_de_la_tinta", "borde_blando_marca_mm", "area_minima_marca_mm2"}
        assert propios <= usados, propios - usados
        assert set(pm.CLAVES_DE_LA_MARCA) == propios

    def test_ningun_parametro_viaja_dentro_de_una_funcion_como_numero_magico_de_la_mancha(self):
        """Los umbrales de la mancha (10, 0.5, 35, 0.15, 0.1, 1.5) viven en `PARAMETROS`, no en el cuerpo de `refinar_marca`.

        R1P-06 (revision de la ronda 1): el filtro `x not in (10,)` de antes descartaba tambien el 10.0 (10.0 == 10), asi que un 10.0 escrito a mano (el valor de DOS parametros: `contraste_minimo_marca` y
        `gris_maximo_de_la_tinta`) no lo veia esta prueba. Ahora se distingue por TIPO: ningun flotante igual a un umbral y UN solo 10 entero, el percentil 10 del nucleo."""
        arbol = ast.parse(MODULO.read_text(encoding="utf-8"))
        refinar = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "refinar_marca")
        constantes = [n.value for n in ast.walk(refinar) if isinstance(n, ast.Constant)]
        flotantes = [x for x in constantes if type(x) is float]
        enteros = [x for x in constantes if type(x) is int]
        for magico in (10.0, 0.5, 35.0, 0.15, 0.1, 1.5):
            assert magico not in flotantes, magico
        assert 35 not in enteros, "el limite de 35 niveles de antes de medir"
        assert enteros.count(10) == 1, ("el unico 10 entero es el percentil 10 del nucleo; otro seria un umbral escrito a mano", enteros)


@pytest.fixture(scope="module")
def arbol():
    return ast.parse(MODULO.read_text(encoding="utf-8"))


class TestElModuloEsPuro:
    """El modulo no importa Qt, ni sqlite3, ni services, ni data, ni ui, ni models; no lee imagenes (la imagen entra por `leer_pelicula`)."""

    def test_sin_qt_base_de_datos_servicios_ni_interfaz(self, arbol):
        importados = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                importados |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                importados.add((n.module or "").split(".")[0])
        assert not importados & {"PyQt5", "PyQt6", "PySide2", "sqlite3", "services", "data", "ui", "models", "matplotlib", "pylinac"}, importados
        assert importados <= {"copy", "math", "numbers", "dataclasses", "cv2", "numpy", "scipy", "analisisImagenes"}, importados

    def test_no_lee_ninguna_imagen_ni_abre_archivos(self, arbol):
        llamadas = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Call):
                f = n.func
                llamadas.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
        prohibidas = {"imread", "imdecode", "imwrite", "imencode", "open", "fromfile", "tofile", "load", "loads", "read_bytes", "read_text", "VideoCapture"}
        assert not llamadas & prohibidas, llamadas & prohibidas

    def test_ninguna_funcion_importa_nada_en_su_cuerpo(self, arbol):
        for f in ast.walk(arbol):
            if isinstance(f, ast.FunctionDef):
                assert not [n for n in ast.walk(f) if isinstance(n, (ast.Import, ast.ImportFrom))], f.name

    def test_el_orden_de_las_esquinas_y_la_escala_se_importan_de_pelicula_py(self):
        pm, pel = _pm(), _pelicula_mod()
        assert pm.ESQUINAS is pel.ESQUINAS and pm.escala_mm is pel.escala_mm and pm.CLAVES_DE_LA_ESCALA is pel.CLAVES_DE_LA_ESCALA
        assert pm.ESQUINAS == ESQUINAS

    def test_el_cruce_de_diagonales_es_el_mismo_que_el_del_piso(self):
        """Dos definiciones de la misma formula (pelicula.py no se toca en C.1): la convergencia se afirma con una prueba."""
        pm, pel = _pm(), _pelicula_mod()
        for theta in GIROS:
            esq, ret = rectangulo(99.6, 99.8, theta, centro=(1900.0, 700.0))
            assert pm.geometria_luz(esq, ret, ESC).cruce == pytest.approx(tuple(pel._piso_cruce_de_diagonales(np.array(esq, np.float64))), abs=1e-9)
        c = pm.clasificar_puntos(CLICS_ML0)
        assert pm.geometria_luz(c.esquinas, c.reticulo, ESC).cruce == pytest.approx(tuple(pel._piso_cruce_de_diagonales(np.array(c.esquinas, np.float64))), abs=1e-9)

    def test_sin_simbolos_de_correcto_o_incorrecto_en_lo_agregado(self):
        pm = _pm()
        prohibidos = re.compile("[✓✔✅✗✘❌⚠☑☒❎]")
        assert not prohibidos.search(MODULO.read_text(encoding="utf-8"))
        textos = [p["motivo"] for p in pm.PARAMETROS.values()] + [pm.MOTIVO_NO_FORMAN_EL_CAMPO, pm.MOTIVO_SIN_ESCALA]
        assert not any(prohibidos.search(t) for t in textos)

    def test_los_motivos_no_medibles_empiezan_por_no_medible_para_quien_pregunta_startswith(self):
        pm = _pm()
        assert pm.MOTIVO_NO_FORMAN_EL_CAMPO == "no medible: los puntos no forman el campo"
        assert pm.MOTIVO_SIN_ESCALA.startswith("no medible")
        assert pm.ESTADO_REFINADA == "refinada" and pm.ESTADO_SIN_REFINAR == "sin refinar"
