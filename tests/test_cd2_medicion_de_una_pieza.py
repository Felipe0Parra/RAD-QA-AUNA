"""CD.2 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, bloque CD.2): UNA SOLA MEDICION de una zona uniforme de pelicula, la de la pelicula virgen del analisis y la de una pieza de calibracion.

CAUSA (pre-vuelo del 26-10, `borradores/CD2/pistas_CD2.md` §0): la medicion de una zona uniforme (la caja de la pelicula, la tinta, las motas, el ruido, la media sin tinta, la tabla de uniformidad y ruido,
las rayas, la cadena de captura y el fondo) vivia DENTRO de `piso_de_pelicula_virgen`, mezclada con cuatro juicios que solo valen para una pelicula SIN irradiar: el rango esperado (con la regla de «tan
clara como el fondo»), el azul testigo, el area minima de 400 mm2 y el rechazo de C5 con menos de 4 bloques de 5 mm. Una pieza de calibracion necesita esa misma medicion sin esos juicios (una pieza a 800 cGy
esta fuera del rango de una virgen por definicion; las 21 piezas de H9 miden 1.8 cm y dejan de 204 a 235 mm2 limpios). La regla del recorte de la netOD vivia ademas en linea dentro de
`placa_mensual.medir_perfil`.

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del motor: el generador `_piezas_de_calibracion_sinteticas.py` (valor por capa, ruido, gradiente, tinta y resolucion conocidos; una prueba por AST
vigila que no importa nada del motor), los arreglos armados aqui para la regla del recorte y los TIFF reales de H9 contra la medida independiente del 22-10:
  (1) `medir_pieza_uniforme` devuelve el valor de cada capa (la media de la region central de 10 x 10 mm) a 0.1 nivel del valor con que se armo la pieza, a 150 y a 600 ppp, en 8 y 16 bits, a ras de la
      imagen y sobre una pagina, con la region en el centro de la pieza (no de la imagen) y su n, su desviacion y el ruido de la tabla los del generador; con un gradiente conocido la media es el valor
      del centro de su caja.
  (2) La tinta y las motas de la region central NO entran al valor (la tabla, con todo, si las ve).
  (3) El recorte por capa es informativo (la fraccion, o None) y no vuelve «no medible» a la pieza; la regla es UNA funcion (`meseta_recortada`) con sus bordes de OD.1c, y `medir_perfil` la usa.
  (4) Una pieza por imagen: con dos (zonas de 1 cm2 o mas) no se mide ninguna y se dice.
  (5) La escala de la pieza sale de `escala_mm` con la resolucion que declara el archivo (150 ppp -> 59 pixeles de region, 600 -> 236); una resolucion ausente o de editor, o «procedimiento» con otra
      resolucion, es «no medible» con su motivo.
  (6) A una pieza no se le juzga lo de una virgen (CD2-D1): ni el rango ni el azul testigo, ni el area, y C5 con pocos bloques solo avisa; si no le cabe su region central, o esta toda cubierta de tinta,
      es «no medible».
  (7) La pieza y la virgen son LA MISMA medicion (capas, tabla, region y procedencia iguales, tambien con EPSON179 real), y la virgen sigue dando, en cada rama, el estado y las pruebas de HEAD (escritos aqui
      a mano, medidos antes de tocar produccion).
  (8) `_copiar_el_escaneo` recibe la subcarpeta (por omision, la de la virgen).
  (9) Las 21 piezas reales de H9 miden «ok» y su media coincide con la medida independiente del 22-10 a 0.1 nivel.
  (10) Estructura: la regla del recorte vive en `pelicula.py` y nadie mas compara contra sus constantes; `placa_mensual` las re-exporta con el mismo nombre; el generador es independiente del motor.
  RONDA 1 DE REVISION (28-10, `borradores/CD2/obstaculos.md`):
  (11) CD2-PROD-01: con `escala="declarada"` una resolucion tan baja que un bloque de 5 mm (o la region central) no llega a un pixel es «no medible» con su motivo, y nunca lanza (a 2.54 dpi, 1 pixel por
       cm, `_virgen_bloques` lanzaba `ValueError`: paso de cero en `range()`); el limite es el de la propia conversion, ni un valor propuesto ni un escalon.
  (12) R1-PRU-01: medir una pieza no cambia la `P` de quien llama (CD.3 a CD.5 reusan una `P` entre piezas y con la virgen).
  (13) R1-PRU-02 / CD2-PROD-02: el recorte por capa se juzga sobre TODA la region central, con la tinta y las motas dentro (CD2-D5), no sobre los pixeles limpios.
  (14) R1-PRU-03: una pieza rectangular y descentrada (las demas son cuadradas y la region queda centrada) mide los pixeles de la caja que dice su tabla, no los de otra con los ejes cambiados.
  (15) R1-PRU-04: una pieza que no se mide no trae ningun numero medido (ni centro, ni region, ni recortes), sea cual sea la causa; conserva lo que explica el rechazo.

Rojo contra HEAD (99aac85): HEAD no tiene la API (`medir_pieza_uniforme`, `MedidaDePieza`, `meseta_recortada`, `_copiar_el_escaneo(..., subcarpeta=)`) y caen con su error las que la usan; caen por ASERCION las
estructurales (la regla vive en `pelicula.py`, el motor usa LA MISMA, ninguna definicion de las cuatro constantes en `placa_mensual.py`, nadie compara fuera de `pelicula.py`); pasan, como controles de lo que
no cambia, las vírgenes de cada rama, el valor de las constantes y la independencia del generador. El conteo esta en `logs/CD2/rojo.log` del anexo.
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
import io
import math
from pathlib import Path

import numpy as np
import pytest
import tifffile

import _corpus
import _piezas_de_calibracion_sinteticas as gen

RAIZ = Path(__file__).resolve().parent.parent
FECHA = "2026-10-28"
CAPAS = ("R", "G", "B", "gris")
LAS_TRES = ("R", "G", "B")
VALORES = (150.0, 120.0, 95.0)            # el (R, G, B) con que se arman casi todas las piezas
SIGMA = 1.5                               # el ruido de cada capa, en niveles de 8 bits
UN_CENTIMETRO_CUADRADO = 100.0            # mm2: lo que ocupa la region central de una pieza, y lo minimo para contar como pieza

# Los textos de lo que NO se mide, escritos AQUI tal cual (la prueba fija el texto, no lo importa).
PREFIJO = "no medible: "
SIN_RESOLUCION = "la pieza no declara la resolución con que se escaneó: sin ella la región central de 10 × 10 mm tendría otro tamaño (escanee la pieza y suba el archivo tal como lo entrega el escáner)"
DE_EDITOR = ("la pieza declara {dpi} dpi, la resolución que escribe un editor al guardar un recorte y no la del escaneo: sin la del escaneo la región central de 10 × 10 mm tendría otro tamaño "
             "(suba el archivo tal como lo entrega el escáner)")
OTRA_RESOLUCION = "la pieza se escaneó a otra resolución ({dpi} dpi) y no a la del procedimiento (600 dpi): sin esa escala no hay milímetros con que medirla"
VARIAS_PIEZAS = "hay {n} piezas de película en la imagen: suba una pieza por imagen"
NO_SE_LEE = "no se pudo leer el archivo: No se reconoce el formato de la imagen."
NO_CABE = "no cabe la región central de 10 × 10 mm en la película a 2 mm o más de sus bordes"
TODA_CUBIERTA = "la región central de 10 × 10 mm está toda cubierta de tinta o motas"
NO_QUEDA_LIMPIA = "no queda película limpia (sin tinta ni motas) en la zona medida"
POCOS_BLOQUES = "no caben 4 bloques de {lado} mm en la película: la uniformidad entre bloques no se juzga"
BAJA = ("la pieza declara {dpi} dpi, una resolución tan baja que {que} de {lado} × {lado} mm no llega a un píxel: no hay con qué medirla (suba el archivo tal como lo entrega el escáner)")
SIN_PELICULA = "no hay película en la imagen (todo es fondo del escáner o no tiene dato)"

# La medida independiente del 22-10 de las 21 piezas de H9 (`logs/piezas_calibracion_22-10.log` del anexo, `scripts/piezas_calibracion.py`: OpenCV, sin nada de la app): la media de la region central de 10 x 10 mm
# de cada capa, en niveles de 8 bits. {dosis en cGy: (R, G, B)}. CD.3 (CD2-M2) la mudo a `tests/_corpus.py`, con la lista de las piezas y su carpeta: una sola definicion.
H9_MEDIAS = _corpus.MEDIA_DE_LAS_PIEZAS_22_10
CARPETA_DE_H9 = Path(_corpus.PIEZAS_DE_CALIBRACION_RAIZ)

# Lo que `piso_de_pelicula_virgen` de HEAD (99aac85) da en cada escena, medido el 28-10 ANTES de tocar produccion y escrito aqui tal cual (JSON: listas y numeros). Los flotantes se comparan a 1e-9.
TABLA_PLANA = {'cabe': True,
 'lado_mm': 10.0,
 'regiones': {'centro': {'caja': [472, 472, 708, 708]},
              'arriba': {'caja': [472, 230, 708, 466]},
              'abajo': {'caja': [472, 714, 708, 950]},
              'izquierda': {'caja': [230, 472, 466, 708]},
              'derecha': {'caja': [714, 472, 950, 708]}},
 'capas': {'R': {'centro': 105.0,
                 'regiones': {'centro': 105.0, 'arriba': 105.0, 'abajo': 105.0, 'izquierda': 105.0, 'derecha': 105.0},
                 'uniformidad_pct': 0.0,
                 'ruido': 0.0,
                 'gradiente_x_pct_por_10cm': None,
                 'gradiente_y_pct_por_10cm': None},
           'G': {'centro': 174.0,
                 'regiones': {'centro': 174.0, 'arriba': 174.0, 'abajo': 174.0, 'izquierda': 174.0, 'derecha': 174.0},
                 'uniformidad_pct': 0.0,
                 'ruido': 0.0,
                 'gradiente_x_pct_por_10cm': None,
                 'gradiente_y_pct_por_10cm': None},
           'B': {'centro': 82.0,
                 'regiones': {'centro': 82.0, 'arriba': 82.0, 'abajo': 82.0, 'izquierda': 82.0, 'derecha': 82.0},
                 'uniformidad_pct': 0.0,
                 'ruido': 0.0,
                 'gradiente_x_pct_por_10cm': None,
                 'gradiente_y_pct_por_10cm': None},
           'gris': {'centro': 143.0,
                    'regiones': {'centro': 143.0, 'arriba': 143.0, 'abajo': 143.0, 'izquierda': 143.0, 'derecha': 143.0},
                    'uniformidad_pct': 0.0,
                    'ruido': 0.0,
                    'gradiente_x_pct_por_10cm': None,
                    'gradiente_y_pct_por_10cm': None}}}

LA_VIRGEN_DE_HEAD = {'no_se_lee': {'estado': 'no válida: no se pudo leer el archivo: No se reconoce el formato de la imagen.',
               'pruebas': [['C1 cadena', 'rechazo', 'no se pudo leer el archivo: No se reconoce el formato de la imagen.']],
               'avisos': [],
               'clase_resolucion': None,
               'dpi_declarado': None},
 'otra_resolucion': {'estado': 'no válida: la película virgen se escaneó a otra resolución (300 dpi) y no a la del procedimiento (600 dpi): sin esa escala no hay milímetros con que medirla',
                     'pruebas': [['C1 cadena',
                                  'rechazo',
                                  'la película virgen se escaneó a otra resolución (300 dpi) y no a la del procedimiento (600 dpi): sin esa escala no hay milímetros con que medirla']],
                     'avisos': [],
                     'clase_resolucion': 'otra',
                     'dpi_declarado': 300.0},
 'sin_pelicula': {'estado': 'no válida: no hay película en la imagen (todo es fondo del escáner o no tiene dato)',
                  'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución coincide'], ['C2 zona', 'rechazo', 'no hay película en la imagen (todo es fondo del escáner o no tiene dato)']],
                  'avisos': [],
                  'clase_resolucion': 'coincide',
                  'dpi_declarado': 600.0},
 'area_chica': {'estado': 'no válida: no hay película virgen suficiente a 2 mm de los bordes (121 mm²; hacen falta 400)',
                'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución coincide'],
                            ['C2 zona', 'rechazo', 'no hay película virgen suficiente a 2 mm de los bordes (121 mm²; hacen falta 400)']],
                'avisos': [],
                'clase_resolucion': 'coincide',
                'dpi_declarado': 600.0},
 'todo_cubierto_de_polvo': {'estado': 'no válida: no queda película limpia (sin tinta ni motas) en la zona medida',
                            'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución coincide'],
                                        ['C2 zona', 'ok', '1683 mm² a 2 mm o más de los bordes'],
                                        ['C3 recorte', 'ok', 'recorte 0.000 %'],
                                        ['C3 fondo', 'ok', 'no se ve fondo del escáner; no se juzga'],
                                        ['C7 ruido', 'ok', 'sigma rojo 2.11, verde 2.11, azul 2.11'],
                                        ['C6 motas', 'aviso', 'motas en el 100.000 % (la mayor, 0.01 mm²); se apartan del piso'],
                                        ['rango', 'rechazo', 'no queda película limpia (sin tinta ni motas) en la zona medida']],
                            'avisos': ['motas en el 100.000 % (la mayor, 0.01 mm²); se apartan del piso'],
                            'clase_resolucion': 'coincide',
                            'dpi_declarado': 600.0},
 'rango_oscura': {'estado': 'no válida: fuera del rango esperado de una película sin irradiar: verde 65 fuera de [145, 230], gris 64 fuera de [110, 200]',
                  'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución coincide'],
                              ['C2 zona', 'ok', '1683 mm² a 2 mm o más de los bordes'],
                              ['C3 recorte', 'ok', 'recorte 0.000 %'],
                              ['C3 fondo', 'ok', 'no se ve fondo del escáner; no se juzga'],
                              ['C7 ruido', 'ok', 'sigma rojo 0.00, verde 0.00, azul 0.00'],
                              ['C6 motas', 'ok', 'motas 0.000 %'],
                              ['rango', 'rechazo', 'fuera del rango esperado de una película sin irradiar: verde 65 fuera de [145, 230], gris 64 fuera de [110, 200]'],
                              ['azul testigo', 'aviso', 'azul 70 fuera de [75, 95]: ¿otro lote u otra cadena de escaneo?'],
                              ['C5 uniformidad',
                               'ok',
                               'rojo CV 0.00 % desviación 0.00 %; verde CV 0.00 % desviación 0.00 %; azul CV 0.00 % desviación 0.00 %; gris CV 0.00 % desviación 0.00 % (64 bloques)'],
                              ['C5 gradiente', 'ok', 'sin gradiente (extensión 40 × 40 mm)'],
                              ['C7 rayas', 'ok', 'sin rayas']],
                  'avisos': ['azul 70 fuera de [75, 95]: ¿otro lote u otra cadena de escaneo?'],
                  'clase_resolucion': 'coincide',
                  'dpi_declarado': 600.0},
 'rango_clara': {'estado': 'no válida: es tan clara como el fondo del escáner (el 100 % de sus píxeles llega a 170 niveles hasta en su capa más oscura); fuera del rango esperado de una '
                           'película sin irradiar: rojo 225 fuera de [60, 170], azul 225 fuera de [65, 130], gris 225 fuera de [110, 200]',
                 'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución coincide'],
                             ['C2 zona', 'ok', '1683 mm² a 2 mm o más de los bordes'],
                             ['C3 recorte', 'ok', 'recorte 0.000 %'],
                             ['C3 fondo', 'ok', 'no se ve fondo del escáner; no se juzga'],
                             ['C7 ruido', 'ok', 'sigma rojo 0.00, verde 0.00, azul 0.00'],
                             ['C6 motas', 'ok', 'motas 0.000 %'],
                             ['rango',
                              'rechazo',
                              'es tan clara como el fondo del escáner (el 100 % de sus píxeles llega a 170 niveles hasta en su capa más oscura); fuera del rango esperado de una película '
                              'sin irradiar: rojo 225 fuera de [60, 170], azul 225 fuera de [65, 130], gris 225 fuera de [110, 200]'],
                             ['azul testigo', 'aviso', 'azul 225 fuera de [75, 95]: ¿otro lote u otra cadena de escaneo?'],
                             ['C5 uniformidad',
                              'ok',
                              'rojo CV 0.00 % desviación 0.00 %; verde CV 0.00 % desviación 0.00 %; azul CV 0.00 % desviación 0.00 %; gris CV 0.00 % desviación 0.00 % (64 bloques)'],
                             ['C5 gradiente', 'ok', 'sin gradiente (extensión 40 × 40 mm)'],
                             ['C7 rayas', 'ok', 'sin rayas']],
                 'avisos': ['azul 225 fuera de [75, 95]: ¿otro lote u otra cadena de escaneo?'],
                 'clase_resolucion': 'coincide',
                 'dpi_declarado': 600.0},
 'editor_96': {'estado': 'ok',
               'pruebas': [['C1 cadena',
                            'aviso',
                            'el archivo parece vuelto a guardar por un editor (resolución de editor o JPEG 4:2:0 de calidad alta): suba el archivo tal como lo entrega el escáner'],
                           ['C2 zona', 'ok', '1683 mm² a 2 mm o más de los bordes'],
                           ['C3 recorte', 'ok', 'recorte 0.000 %'],
                           ['C3 fondo', 'ok', 'no se ve fondo del escáner; no se juzga'],
                           ['C7 ruido', 'ok', 'sigma rojo 0.00, verde 0.00, azul 0.00'],
                           ['C6 motas', 'ok', 'motas 0.000 %'],
                           ['rango', 'ok', 'dentro del rango: rojo 105, verde 174, azul 82, gris 143'],
                           ['azul testigo', 'ok', 'azul 82'],
                           ['C5 uniformidad',
                            'ok',
                            'rojo CV 0.00 % desviación 0.00 %; verde CV 0.00 % desviación 0.00 %; azul CV 0.00 % desviación 0.00 %; gris CV 0.00 % desviación 0.00 % (64 bloques)'],
                           ['C5 gradiente', 'ok', 'sin gradiente (extensión 40 × 40 mm)'],
                           ['C7 rayas', 'ok', 'sin rayas']],
               'avisos': ['el archivo parece vuelto a guardar por un editor (resolución de editor o JPEG 4:2:0 de calidad alta): suba el archivo tal como lo entrega el escáner'],
               'capas': {'R': [105.0, 938961, 0.0, 105.0], 'G': [174.0, 938961, 0.0, 174.0], 'B': [82.0, 938961, 0.0, 82.0], 'gris': [143.0, 938961, 0.0, 143.0]},
               'region': {'caja': [106, 106, 1075, 1075],
                          'n': 938961,
                          'area_mm2': 1682.7,
                          'pelicula_mm': {'x': 2.5, 'y': 2.5, 'ancho': 45.0, 'alto': 45.0},
                          'pagina_mm': {'ancho': 50.0, 'alto': 50.0}},
               'uniformidad': TABLA_PLANA,
               'clase_resolucion': 'editor',
               'dpi_declarado': 96.0},
 'sin_resolucion': {'estado': 'ok',
                    'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución sin_dato'],
                                ['C2 zona', 'ok', '1683 mm² a 2 mm o más de los bordes'],
                                ['C3 recorte', 'ok', 'recorte 0.000 %'],
                                ['C3 fondo', 'ok', 'no se ve fondo del escáner; no se juzga'],
                                ['C7 ruido', 'ok', 'sigma rojo 0.00, verde 0.00, azul 0.00'],
                                ['C6 motas', 'ok', 'motas 0.000 %'],
                                ['rango', 'ok', 'dentro del rango: rojo 105, verde 174, azul 82, gris 143'],
                                ['azul testigo', 'ok', 'azul 82'],
                                ['C5 uniformidad',
                                 'ok',
                                 'rojo CV 0.00 % desviación 0.00 %; verde CV 0.00 % desviación 0.00 %; azul CV 0.00 % desviación 0.00 %; gris CV 0.00 % desviación 0.00 % (64 bloques)'],
                                ['C5 gradiente', 'ok', 'sin gradiente (extensión 40 × 40 mm)'],
                                ['C7 rayas', 'ok', 'sin rayas']],
                    'avisos': [],
                    'capas': {'R': [105.0, 938961, 0.0, 105.0], 'G': [174.0, 938961, 0.0, 174.0], 'B': [82.0, 938961, 0.0, 82.0], 'gris': [143.0, 938961, 0.0, 143.0]},
                    'region': {'caja': [106, 106, 1075, 1075],
                               'n': 938961,
                               'area_mm2': 1682.7,
                               'pelicula_mm': {'x': 2.5, 'y': 2.5, 'ancho': 45.0, 'alto': 45.0},
                               'pagina_mm': {'ancho': 50.0, 'alto': 50.0}},
                    'uniformidad': TABLA_PLANA,
                    'clase_resolucion': 'sin_dato',
                    'dpi_declarado': None},
 'ok': {'estado': 'ok',
        'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución coincide'],
                    ['C2 zona', 'ok', '1683 mm² a 2 mm o más de los bordes'],
                    ['C3 recorte', 'ok', 'recorte 0.000 %'],
                    ['C3 fondo', 'ok', 'no se ve fondo del escáner; no se juzga'],
                    ['C7 ruido', 'ok', 'sigma rojo 0.00, verde 0.00, azul 0.00'],
                    ['C6 motas', 'ok', 'motas 0.000 %'],
                    ['rango', 'ok', 'dentro del rango: rojo 105, verde 174, azul 82, gris 143'],
                    ['azul testigo', 'ok', 'azul 82'],
                    ['C5 uniformidad',
                     'ok',
                     'rojo CV 0.00 % desviación 0.00 %; verde CV 0.00 % desviación 0.00 %; azul CV 0.00 % desviación 0.00 %; gris CV 0.00 % desviación 0.00 % (64 bloques)'],
                    ['C5 gradiente', 'ok', 'sin gradiente (extensión 40 × 40 mm)'],
                    ['C7 rayas', 'ok', 'sin rayas']],
        'avisos': [],
        'capas': {'R': [105.0, 938961, 0.0, 105.0], 'G': [174.0, 938961, 0.0, 174.0], 'B': [82.0, 938961, 0.0, 82.0], 'gris': [143.0, 938961, 0.0, 143.0]},
        'region': {'caja': [106, 106, 1075, 1075],
                   'n': 938961,
                   'area_mm2': 1682.7,
                   'pelicula_mm': {'x': 2.5, 'y': 2.5, 'ancho': 45.0, 'alto': 45.0},
                   'pagina_mm': {'ancho': 50.0, 'alto': 50.0}},
        'uniformidad': TABLA_PLANA,
        'clase_resolucion': 'coincide',
        'dpi_declarado': 600.0},
 'ok_inclinada': {'estado': 'ok',
                  'pruebas': [['C1 cadena', 'ok', 'TIFF, 8 bits, resolución coincide'],
                              ['C2 zona', 'ok', '4361 mm² a 2 mm o más de los bordes'],
                              ['C3 recorte', 'ok', 'recorte 0.000 %'],
                              ['C3 fondo', 'ok', 'no se ve fondo del escáner; no se juzga'],
                              ['C7 ruido', 'ok', 'sigma rojo 0.00, verde 0.00, azul 0.00'],
                              ['C6 motas', 'ok', 'motas 0.000 %'],
                              ['rango', 'ok', 'dentro del rango: rojo 105, verde 174, azul 82, gris 143'],
                              ['azul testigo', 'ok', 'azul 82'],
                              ['C5 uniformidad',
                               'ok',
                               'rojo CV 1.05 % desviación 2.05 %; verde CV 0.64 % desviación 1.24 %; azul CV 1.35 % desviación 2.63 %; gris CV 0.77 % desviación 1.51 % (169 bloques)'],
                              ['C5 gradiente',
                               'aviso',
                               'gradiente (respuesta lateral del escáner o película curvada): rojo 4.77 % por 10 cm en x, rojo 2.82 % por 10 cm en y, verde 2.88 % por 10 cm en x, verde '
                               '1.70 % por 10 cm en y, azul 6.10 % por 10 cm en x, azul 3.61 % por 10 cm en y'],
                              ['C7 rayas', 'ok', 'sin rayas']],
                  'avisos': ['gradiente (respuesta lateral del escáner o película curvada): rojo 4.77 % por 10 cm en x, rojo 2.82 % por 10 cm en y, verde 2.88 % por 10 cm en x, verde 1.70 '
                             '% por 10 cm en y, azul 6.10 % por 10 cm en x, azul 3.61 % por 10 cm en y'],
                  'capas': {'R': [105.0, 2433600, 2.0, 105.0], 'G': [174.0, 2433600, 2.0, 174.0], 'B': [82.0, 2433600, 2.0, 82.0], 'gris': [143.0, 2433600, 2.0, 143.0]},
                  'region': {'caja': [118, 118, 1678, 1678],
                             'n': 2433600,
                             'area_mm2': 4361.3,
                             'pelicula_mm': {'x': 3.0, 'y': 3.0, 'ancho': 70.0, 'alto': 70.0},
                             'pagina_mm': {'ancho': 76.0, 'alto': 76.0}},
                  'uniformidad': {'cabe': True,
                                  'lado_mm': 10.0,
                                  'regiones': {'centro': {'caja': [780, 780, 1016, 1016]},
                                               'arriba': {'caja': [780, 390, 1016, 626]},
                                               'abajo': {'caja': [780, 1169, 1016, 1405]},
                                               'izquierda': {'caja': [390, 780, 626, 1016]},
                                               'derecha': {'caja': [1169, 780, 1405, 1016]}},
                                  'capas': {'R': {'centro': 105.0,
                                                  'regiones': {'centro': 105.0,
                                                               'arriba': 105.490250646366,
                                                               'abajo': 104.51228095374893,
                                                               'izquierda': 104.01843938523413,
                                                               'derecha': 105.98050129273197},
                                                  'uniformidad_pct': 0.9348196331103509,
                                                  'ruido': 0.0,
                                                  'gradiente_x_pct_por_10cm': 4.766226566747095,
                                                  'gradiente_y_pct_por_10cm': -2.8192525063646547},
                                            'G': {'centro': 174.0,
                                                  'regiones': {'centro': 174.0,
                                                               'arriba': 174.49025064636598,
                                                               'abajo': 173.51228095374893,
                                                               'izquierda': 173.01843938523413,
                                                               'derecha': 174.980501292732},
                                                  'uniformidad_pct': 0.5641152958424531,
                                                  'ruido': 0.0,
                                                  'gradiente_x_pct_por_10cm': 2.8760502547086815,
                                                  'gradiente_y_pct_por_10cm': -1.7012026985878832},
                                            'B': {'centro': 82.0,
                                                  'regiones': {'centro': 82.0,
                                                               'arriba': 82.490250646366,
                                                               'abajo': 81.51228095374893,
                                                               'izquierda': 81.01843938523413,
                                                               'derecha': 82.98050129273197},
                                                  'uniformidad_pct': 1.1970251399583762,
                                                  'ruido': 0.0,
                                                  'gradiente_x_pct_por_10cm': 6.103273354430009,
                                                  'gradiente_y_pct_por_10cm': -3.6101239545666597},
                                            'gris': {'centro': 143.0,
                                                     'regiones': {'centro': 143.0,
                                                                  'arriba': 143.49025064636598,
                                                                  'abajo': 142.51228095374893,
                                                                  'izquierda': 142.01843938523413,
                                                                  'derecha': 143.980501292732},
                                                     'uniformidad_pct': 0.6864060243117961,
                                                     'ruido': 0.0,
                                                     'gradiente_x_pct_por_10cm': None,
                                                     'gradiente_y_pct_por_10cm': None}}},
                  'clase_resolucion': 'coincide',
                  'dpi_declarado': 600.0}}


# ===================================================================================================== ayudas

def _pel():
    """El modulo, importado POR PRUEBA (en HEAD el archivo se coleciona y cada prueba que usa la API nueva cae con su error)."""
    return importlib.import_module("analisisImagenes.pelicula")


def _pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def _P(**cambios):
    """Lo que la ventana del mensual le pasa a la medicion: `VALORES_DE_LA_GEOMETRIA` (trae la escala del procedimiento: 600 dpi, 72 y 96 de editor) y, si se quiere, cambios."""
    return {**copy.deepcopy(_pm().VALORES_DE_LA_GEOMETRIA), **cambios}


def medir(datos, escala="declarada", P=None, nombre="pieza.tif"):
    return _pel().medir_pieza_uniforme(datos, _P() if P is None else P, nombre, FECHA, escala=escala)


def medir_virgen(datos, nombre="virgen.tif", P=None):
    return _pel().piso_de_pelicula_virgen(datos, _P() if P is None else P, nombre, FECHA)


def _decodificar(datos):
    """El TIFF como (alto, ancho, 3) en niveles de 8 bits (float64), decodificado con la libreria que lo escribio y no con el motor."""
    arreglo = tifffile.imread(io.BytesIO(datos))
    return arreglo.astype(np.float64) / (gen.CODIGOS_POR_NIVEL if arreglo.dtype == np.uint16 else 1.0)


def _caja_central(m):
    """La caja «centro» de la tabla de uniformidad y ruido de la medida: (x0, y0, x1, y1) en pixeles de la imagen, x1 e y1 exclusivos."""
    return tuple(m.uniformidad["regiones"]["centro"]["caja"])


def _centro_de(caja):
    x0, y0, x1, y1 = caja
    return (x0 + x1 - 1) / 2.0, (y0 + y1 - 1) / 2.0


def _pieza(dpi=150.0, bits=8, margen=0.0, valores=VALORES, semilla=11, **kw):
    return gen.pieza_uniforme(valores, lado_mm=kw.pop("lado_mm", 18.0), dpi=dpi, sigma=kw.pop("sigma", SIGMA), semilla=semilla, margen_mm=margen, bits=bits, **kw)


def _diferencia(real, esperado, ruta="valor"):
    """Compara dos estructuras de JSON (diccionarios, listas, numeros, textos, None): los flotantes a 1e-9 (relativa y absoluta), todo lo demas exacto. None si coinciden; si no, el camino y los dos valores."""
    if isinstance(esperado, dict):
        if not isinstance(real, dict) or set(real) != set(esperado):
            return f"{ruta}: claves {sorted(real) if isinstance(real, dict) else real!r} y no {sorted(esperado)}"
        for k in esperado:
            d = _diferencia(real[k], esperado[k], f"{ruta}[{k!r}]")
            if d:
                return d
        return None
    if isinstance(esperado, (list, tuple)):
        if not isinstance(real, (list, tuple)) or len(real) != len(esperado):
            return f"{ruta}: {real!r} y no {esperado!r}"
        for i, (a, b) in enumerate(zip(real, esperado)):
            d = _diferencia(a, b, f"{ruta}[{i}]")
            if d:
                return d
        return None
    if isinstance(esperado, float) and isinstance(real, (int, float)) and not isinstance(real, bool):
        return None if math.isclose(real, esperado, rel_tol=1e-9, abs_tol=1e-9) else f"{ruta}: {real!r} y no {esperado!r}"
    return None if real == esperado and type(real) is type(esperado) else f"{ruta}: {real!r} y no {esperado!r}"


def _sin_numeros(m):
    """Una medida que no es «ok» no trae ningun numero medido: ni centro, ni valor, ni capas con mediana, ni la region de la pelicula ni los recortes por capa (como la virgen que no sirve, que no trae region;
    CD2-D2 y R1-PRU-04 de la ronda 1). Lo que SI conserva es lo que explica el rechazo: las pruebas, los avisos, la procedencia, los parametros, cuantas piezas hay, la escala y la tabla si se llego a medir."""
    assert m.estado.startswith(PREFIJO) and m.centro is None and m.region is None and m.recortadas is None
    for capa in CAPAS:
        assert m.valor(capa) is None
        assert m.capas[capa].estado == m.estado and m.capas[capa].mediana is None and m.capas[capa].media is None


@pytest.fixture(scope="module", autouse=True)
def _suelta_lo_grande_al_terminar_el_modulo():
    """Las medidas de EPSON179 (99 MB) y de la virgen de 70 mm dejan arreglos grandes: se sueltan al terminar el archivo (Trampa 10: nada vive entre archivos)."""
    yield
    gc.collect()


CONFIGURACIONES = [
    pytest.param(150.0, "declarada", 8, 0.0, 59, id="150ppp_declarada_8bits_a_ras"),
    pytest.param(150.0, "declarada", 16, 0.0, 59, id="150ppp_declarada_16bits_a_ras"),
    pytest.param(150.0, "declarada", 8, 6.0, 59, id="150ppp_declarada_8bits_en_pagina"),
    pytest.param(600.0, "declarada", 8, 0.0, 236, id="600ppp_declarada"),
    pytest.param(600.0, "procedimiento", 8, 0.0, 236, id="600ppp_procedimiento"),
]


# ===================================================================================================== (1) el valor de la pieza es la verdad del generador

class TestElValorDeLaPiezaEsLaVerdadDelGenerador:
    @pytest.mark.parametrize("dpi, escala, bits, margen, lado_px", CONFIGURACIONES)
    def test_cada_capa_da_el_valor_con_que_se_armo_la_pieza_a_una_decima_de_nivel(self, dpi, escala, bits, margen, lado_px):
        pieza = _pieza(dpi, bits, margen)
        m = medir(pieza.datos, escala)
        assert m.estado == "ok" and m.piezas == 1, (m.estado, m.piezas)
        for capa in CAPAS:
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1, (capa, m.valor(capa), pieza.nominal(capa))
            assert m.centro[capa]["media"] == m.valor(capa), "`valor(capa)` es la media del centro"
            assert abs(m.capas[capa].mediana - pieza.nominal(capa)) <= 0.5, (capa, m.capas[capa].mediana)
            assert m.capas[capa].estado == "ok" and m.capas[capa].n > lado_px ** 2

    @pytest.mark.parametrize("dpi, escala, bits, margen, lado_px", CONFIGURACIONES)
    def test_la_desviacion_del_centro_y_el_ruido_de_la_tabla_son_los_del_generador_a_cinco_por_ciento(self, dpi, escala, bits, margen, lado_px):
        m = medir(_pieza(dpi, bits, margen).datos, escala)
        assert m.estado == "ok", m.estado
        for capa in LAS_TRES:
            assert abs(m.centro[capa]["desviacion"] - SIGMA) <= 0.05 * SIGMA, (capa, m.centro[capa]["desviacion"])
            assert abs(m.uniformidad["capas"][capa]["ruido"] - SIGMA) <= 0.05 * SIGMA, (capa, m.uniformidad["capas"][capa]["ruido"])

    @pytest.mark.parametrize("dpi, escala, bits, margen, lado_px", CONFIGURACIONES)
    def test_la_region_central_mide_diez_milimetros_en_pixeles_y_su_n_es_el_de_su_caja(self, dpi, escala, bits, margen, lado_px):
        """10 mm a 150 ppp son 59 pixeles y a 600 ppp 236 (el bloque de CD.2): sin tinta ni motas, el n del centro es el de la caja entera."""
        pieza = _pieza(dpi, bits, margen)
        m = medir(pieza.datos, escala)
        assert m.estado == "ok", m.estado
        x0, y0, x1, y1 = _caja_central(m)
        assert (x1 - x0, y1 - y0) == (lado_px, lado_px)
        for capa in CAPAS:
            assert m.centro[capa]["n"] == lado_px ** 2, (capa, m.centro[capa]["n"])
        assert m.escala == escala and m.escala_mm == pytest.approx(gen.MM_POR_PULGADA / dpi), (m.escala, m.escala_mm)

    @pytest.mark.parametrize("dpi, escala, bits, margen, lado_px", CONFIGURACIONES)
    def test_la_region_central_esta_en_el_centro_de_la_pieza_a_un_pixel(self, dpi, escala, bits, margen, lado_px):
        pieza = _pieza(dpi, bits, margen)
        m = medir(pieza.datos, escala)
        cx, cy = _centro_de(_caja_central(m))
        px, py = pieza.caja.centro
        assert abs(cx - px) <= 1.0 and abs(cy - py) <= 1.0, ((cx, cy), (px, py))

    @pytest.mark.parametrize("dpi, escala, bits, margen, lado_px", CONFIGURACIONES)
    def test_la_media_del_centro_es_la_media_de_los_pixeles_de_su_caja(self, dpi, escala, bits, margen, lado_px):
        """Con el TIFF decodificado por `tifffile`: el valor es la media de los pixeles de la caja que la tabla dice, no de otra region parecida (el gris es el de BT.601, a 0.05 por los redondeos de OpenCV)."""
        pieza = _pieza(dpi, bits, margen)
        m = medir(pieza.datos, escala)
        x0, y0, x1, y1 = _caja_central(m)
        caja = _decodificar(pieza.datos)[y0:y1, x0:x1]
        for k, capa in enumerate(LAS_TRES):
            assert m.centro[capa]["media"] == pytest.approx(float(caja[..., k].mean()), abs=1e-4), capa
        assert m.centro["gris"]["media"] == pytest.approx(float(sum(p * caja[..., k] for k, p in enumerate(gen.PESOS_DEL_GRIS)).mean()), abs=0.05)

    @pytest.mark.parametrize("eje", ["x", "y"])
    @pytest.mark.parametrize("donde", ["a_ras", "en_una_pagina_con_la_pieza_descentrada"])
    def test_con_un_gradiente_conocido_la_media_es_el_valor_del_centro_de_la_caja(self, eje, donde):
        """Un gradiente de 0.6 niveles por mm (0.1 por pixel a 150 ppp): la media de una caja simetrica es el valor de su centro, asi que una region corrida un pixel mueve la media 0.1 y una corrida 8 pixeles, 0.8.
        La pieza descentrada en la pagina caza una region que tomara el centro de la IMAGEN en vez del de la pieza."""
        pendiente = {"pendiente_" + eje: 0.6}
        if donde == "a_ras":
            pieza = _pieza(semilla=13, **pendiente)
        else:
            pieza = _pieza(semilla=13, pagina_mm=(50.0, 40.0), posicion_mm=(22.0, 6.0), **pendiente)
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        for capa in LAS_TRES:
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1, (capa, m.valor(capa), pieza.nominal(capa))
        antes = _decodificar(pieza.datos)
        x0, y0, x1, y1 = _caja_central(m)
        assert antes[y0:y1, x0:x1, 0].std() > 1.8, "premisa: la caja SI abarca el gradiente (su desviacion pasa de la del ruido)"

    def test_la_region_central_esta_en_el_centro_de_la_pieza_y_no_en_el_de_la_imagen(self):
        """Una pieza en una pagina de 50 x 40 mm con su esquina en (22, 6) mm: el centro de la pieza queda a mas de 20 pixeles del de la imagen en cada eje."""
        pieza = _pieza(pagina_mm=(50.0, 40.0), posicion_mm=(22.0, 6.0))
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        cx, cy = _centro_de(_caja_central(m))
        px, py = pieza.caja.centro
        assert abs(cx - px) <= 1.0 and abs(cy - py) <= 1.0, ((cx, cy), (px, py))
        imagen = ((gen.pixeles(50.0, 150.0) - 1) / 2.0, (gen.pixeles(40.0, 150.0) - 1) / 2.0)                  # el centro de la pagina, en pixeles
        assert abs(cx - imagen[0]) > 20 and abs(cy - imagen[1]) > 20, "premisa: la pieza esta descentrada en la pagina"

    def test_una_pieza_rectangular_y_descentrada_con_gradiente_mide_los_pixeles_de_la_caja_que_dice_su_tabla(self):
        """R1-PRU-03. Las demas piezas son CUADRADAS: su region central queda centrada en la ventana de la pelicula y una ventana con los ejes cambiados toma los MISMOS pixeles. Una pieza de 30 x 18 mm
        (177 x 106 pixeles) en una pagina de 60 x 40 mm, con un gradiente de 0.6 niveles por mm en x, no: con los ejes cambiados la media sale 3.6 niveles mas abajo (146.3) y con otro n (2183)."""
        lienzo = gen.Lienzo(60.0, 40.0, 150.0, semilla=13)
        caja = lienzo.pegar_pelicula(20.0, 12.0, 30.0, 18.0, VALORES, SIGMA, pendiente_x=0.6)
        datos = lienzo.codificar()
        assert caja.ancho != caja.alto, "premisa: la pieza no es cuadrada"
        m = medir(datos)
        assert m.estado == "ok", m.estado
        x0, y0, x1, y1 = _caja_central(m)
        assert (x1 - x0, y1 - y0) == (59, 59)
        (cx, cy), (px, py) = _centro_de((x0, y0, x1, y1)), caja.centro
        assert abs(cx - px) <= 1.0 and abs(cy - py) <= 1.0, ((cx, cy), (px, py))
        decodificada = _decodificar(datos)[y0:y1, x0:x1]
        for k, capa in enumerate(LAS_TRES):
            assert m.centro[capa]["n"] == 59 ** 2, (capa, m.centro[capa]["n"])
            assert m.centro[capa]["media"] == pytest.approx(float(decodificada[..., k].mean()), abs=1e-4), (capa, "la media es la de los pixeles de SU caja")
            assert abs(m.valor(capa) - VALORES[k]) <= 0.15, (capa, m.valor(capa), VALORES[k])

    @pytest.mark.parametrize("pendiente", [0.6, -0.6])
    def test_con_un_gradiente_en_una_pieza_de_60_mm_la_tabla_da_la_diferencia_esperada_entre_izquierda_y_derecha(self, pendiente):
        """La diferencia de las medias de las regiones «izquierda» y «derecha» de la tabla es la pendiente del generador por la distancia (en pixeles) entre los centros de las dos cajas que la propia tabla dice."""
        pieza = _pieza(lado_mm=60.0, semilla=19, pendiente_x=pendiente)
        m = medir(pieza.datos)
        assert m.estado == "ok" and m.uniformidad["cabe"] is True, (m.estado, m.uniformidad["cabe"])
        izquierda, derecha = (m.uniformidad["regiones"][n]["caja"] for n in ("izquierda", "derecha"))
        separacion_px = _centro_de(derecha)[0] - _centro_de(izquierda)[0]
        por_pixel = pendiente * 25.4 / 150.0
        for capa in LAS_TRES:
            diferencia = m.uniformidad["capas"][capa]["regiones"]["derecha"] - m.uniformidad["capas"][capa]["regiones"]["izquierda"]
            assert diferencia == pytest.approx(por_pixel * separacion_px, abs=0.15), (capa, diferencia, por_pixel * separacion_px)
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1

    def test_una_pieza_de_60_mm_cabe_en_la_tabla_entera_y_su_uniformidad_es_cero(self):
        """Con 60 mm caben las cinco regiones de la tabla: la uniformidad (la mayor diferencia contra el centro, en % del centro) de una pieza uniforme es ~0."""
        pieza = _pieza(lado_mm=60.0, semilla=17)
        m = medir(pieza.datos)
        assert m.estado == "ok" and m.uniformidad["cabe"] is True, (m.estado, m.uniformidad["cabe"])
        assert all(r["caja"] is not None for r in m.uniformidad["regiones"].values())
        for capa in CAPAS:
            assert m.uniformidad["capas"][capa]["uniformidad_pct"] < 0.1, (capa, m.uniformidad["capas"][capa]["uniformidad_pct"])
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1

    def test_una_pieza_chica_no_cabe_en_la_tabla_entera_pero_si_su_centro(self):
        m = medir(_pieza().datos)
        assert m.uniformidad["cabe"] is False and m.uniformidad["regiones"]["centro"]["caja"] is not None
        assert all(m.uniformidad["capas"][c]["uniformidad_pct"] is None for c in CAPAS)

    def test_la_region_central_sale_del_parametro_y_no_de_un_numero_escrito_en_la_funcion(self):
        """`lado_region_uniformidad_virgen_mm` = 6 mm a 150 ppp son 35 pixeles: la region central sigue al parametro."""
        pieza = _pieza()
        m = medir(pieza.datos, P=_P(lado_region_uniformidad_virgen_mm=6.0))
        x0, y0, x1, y1 = _caja_central(m)
        assert m.estado == "ok" and (x1 - x0, y1 - y0) == (35, 35) and m.centro["G"]["n"] == 35 ** 2, (m.estado, (x1 - x0, y1 - y0))
        assert m.parametros["lado_region_uniformidad_virgen_mm"] == 6.0

    def test_la_procedencia_dice_de_donde_salio_el_archivo_y_con_que_escala_se_midio(self):
        pieza = _pieza(bits=16)
        m = medir(pieza.datos, nombre="pieza_150.tif")
        pr = m.procedencia
        assert pr["archivo"] == "pieza_150.tif" and pr["sha256"] == hashlib.sha256(pieza.datos).hexdigest() and pr["bytes"] == len(pieza.datos)
        assert pr["formato"] == "TIFF" and pr["bits"] == 16 and pr["dpi_declarado"] == 150.0 and pr["forma"] == [pieza.caja.alto, pieza.caja.ancho]
        assert pr["clase_resolucion"] == "coincide", "con la escala declarada la resolucion del procedimiento ES la del archivo (CD2-D6)"
        assert pr["fecha_calculo"] == FECHA and pr["version"] == "PV-2" and pr["orientacion_declarada"] is None

    def test_el_resultado_nunca_lanza_por_el_contenido(self):
        for basura in (b"", b"\x00" * 100, b"esto no es una imagen", gen.pieza_uniforme(dpi=150.0).datos[:200]):
            m = medir(basura)
            assert m.estado.startswith(PREFIJO), m.estado


# ===================================================================================================== (2) la tinta y las motas no entran al valor

class TestLaTintaYLasMotasNoEntranAlValor:
    def test_una_mancha_de_tinta_en_el_centro_se_aparta_del_valor_y_la_tabla_con_todo_si_la_ve(self):
        pieza = _pieza(manchas=[(7.0, 7.0, 4.0, 4.0, -60.0)])
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        for capa in LAS_TRES:
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1, (capa, m.valor(capa))
            assert m.centro[capa]["desviacion"] <= 2.0, "el centro no ve la mancha"
            assert m.uniformidad["capas"][capa]["ruido"] > 10.0, "la tabla (con todo) si la ve"
        assert 2000 < m.centro["G"]["n"] < 59 * 59 - 500, m.centro["G"]["n"]

    def test_una_mota_clara_en_el_centro_se_aparta_del_valor(self):
        pieza = _pieza(manchas=[(8.75, 8.75, 0.5, 0.5, 70.0)])
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        for capa in LAS_TRES:
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1, (capa, m.valor(capa))
            assert m.centro[capa]["desviacion"] <= 2.0
        assert m.centro["G"]["n"] < 59 * 59 - 50, "la mota y su borde (0.5 mm de cada lado) salen de la region"

    def test_la_media_de_toda_la_region_medida_tambien_va_sin_la_tinta(self):
        """`capas[c].media` (el valor de la virgen, V6 de OD.1) y la mediana de cada capa salen de la zona sin tinta ni motas."""
        pieza = _pieza(manchas=[(7.0, 7.0, 4.0, 4.0, -60.0)])
        m = medir(pieza.datos)
        for capa in LAS_TRES:
            assert abs(m.capas[capa].media - pieza.nominal(capa)) <= 0.1 and abs(m.capas[capa].mediana - pieza.nominal(capa)) <= 0.5, capa

    def test_una_mancha_oscura_en_una_capa_clara_no_es_un_recorte(self):
        """Tinta de -200 niveles (pixeles en 0) en medio de una capa de 150: la mediana de la region es 150 y la regla del recorte no la mira; el valor no la lleva."""
        pieza = _pieza(manchas=[(7.0, 7.0, 4.0, 4.0, -200.0)])
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        assert m.recortadas == {c: None for c in CAPAS}, m.recortadas
        assert abs(m.valor("R") - 150.0) <= 0.1

    def test_una_pieza_toda_cubierta_de_polvo_no_deja_pelicula_limpia_y_se_dice_sin_numeros(self):
        lienzo = gen.Lienzo(18.0, 18.0, 150.0, semilla=5)
        lienzo.pegar_pelicula(0, 0, 18.0, 18.0, VALORES, SIGMA)
        lienzo.pegar_punteado(0, 0, 18.0, 18.0, paso_px=4, lado_px=2, delta=60.0)
        m = medir(lienzo.codificar())
        assert m.estado == PREFIJO + NO_QUEDA_LIMPIA, m.estado
        _sin_numeros(m)
        rechazos = [p for p in m.pruebas if p.resultado == "rechazo"]
        assert [(p.nombre, p.texto) for p in rechazos] == [("C2 zona", NO_QUEDA_LIMPIA)], "en una pieza el rechazo es de la zona, no de un «rango» que solo tiene una virgen"


# ===================================================================================================== (3) el recorte por capa y la regla del recorte

def _meseta(n, k, mediana):
    """Un arreglo de `n` muestras con `k` en 0 y las demas en `mediana` (la mediana del arreglo es `mediana` mientras k sea menos de la mitad)."""
    v = np.full(n, float(mediana))
    v[:k] = 0.0
    return v


class TestElRecorteDeLaPieza:
    def test_una_capa_en_el_negro_del_escaner_dice_su_fraccion_recortada_y_la_pieza_sigue_siendo_ok(self):
        pieza = _pieza(valores=(0.4, 120.0, 95.0))
        m = medir(pieza.datos)
        assert m.estado == "ok", "el recorte es informativo (CD2-D5): no vuelve «no medible» a la pieza"
        x0, y0, x1, y1 = _caja_central(m)
        rojo = _decodificar(pieza.datos)[y0:y1, x0:x1, 0]
        esperada = float(np.mean(rojo <= 1.5))
        assert esperada > 0.5, "premisa: casi todo el rojo esta en el negro del escaner"
        assert m.recortadas["R"] == pytest.approx(esperada, abs=1e-12) and m.recortadas["R"] > 0.01
        assert all(m.recortadas[c] is None for c in ("G", "B", "gris")), m.recortadas
        assert any("recortada" in a for a in m.avisos), "la cadena de captura ya avisa de la capa en 0 (C3 recorte)"

    @pytest.mark.parametrize("manchas", [[(7.0, 7.0, 4.0, 4.0, -60.0)], [(8.5, 8.5, 1.0, 1.0, 80.0)]], ids=["tinta_de_4_mm", "mota_de_1_mm"])
    def test_el_recorte_se_juzga_sobre_toda_la_region_central_con_la_tinta_y_las_motas_dentro(self, manchas):
        """R1-PRU-02 / CD2-PROD-02 (CD2-D5: «sobre TODA la region central, como `medir_perfil` sobre su zona central»). El VALOR aparta la tinta y las motas, pero la fraccion recortada es la de la caja entera:
        con una mancha de tinta de 4 x 4 mm sobre el rojo en el negro la fraccion es 0.808 (y 0.772 si solo se mirara lo limpio); con una mota de 1 x 1 mm, 0.763 (y 0.769)."""
        pieza = _pieza(valores=(0.4, 120.0, 95.0), semilla=11, manchas=manchas)
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        x0, y0, x1, y1 = _caja_central(m)
        assert m.centro["R"]["n"] < (x1 - x0) * (y1 - y0), "premisa: la mancha esta DENTRO de la region central y el valor la aparta"
        rojo = _decodificar(pieza.datos)[y0:y1, x0:x1, 0]
        esperada = float(np.mean(rojo <= 1.5))
        mancha_x, mancha_y, ancho, alto, _ = manchas[0]
        px0, py0 = pieza.caja.x0 + gen.pixeles(mancha_x, 150.0) - x0, pieza.caja.y0 + gen.pixeles(mancha_y, 150.0) - y0
        fuera = np.ones(rojo.shape, bool)
        fuera[max(py0, 0):py0 + gen.pixeles(alto, 150.0), max(px0, 0):px0 + gen.pixeles(ancho, 150.0)] = False
        assert abs(esperada - float(np.mean(rojo[fuera] <= 1.5))) > 0.003, "premisa: la escena distingue la caja entera de lo que queda fuera de la mancha"
        assert m.recortadas["R"] == pytest.approx(esperada, abs=1e-12), (m.recortadas["R"], esperada)
        assert all(m.recortadas[c] is None for c in ("G", "B", "gris"))

    def test_una_pieza_sin_ninguna_capa_en_el_negro_no_trae_recortes(self):
        m = medir(_pieza().datos)
        assert m.recortadas == {c: None for c in CAPAS}

    def test_una_pieza_que_no_se_mide_no_trae_recortes(self):
        assert medir(b"basura").recortadas is None

    @pytest.mark.parametrize("n, k, mediana, esperada", [
        (1000, 20, 11.4, 0.02), (1000, 20, 11.5, 0.02), (1000, 20, 11.6, None), (1000, 20, 18.0, None),
        (1700, 17, 5.0, None), (1700, 18, 5.0, 18 / 1700), (1700, 0, 5.0, None), (1000, 300, 5.0, 0.3), (1000, 1000, 0.0, 1.0),
    ], ids=["mediana_11_4", "mediana_11_5_exacta", "mediana_11_6", "mediana_18", "17_de_1700_es_el_1_por_ciento_exacto", "18_de_1700", "ninguna_en_el_negro", "el_30_por_ciento",
            "todo_en_cero"])
    def test_la_regla_del_recorte_en_sus_bordes_es_la_de_OD1c(self, n, k, mediana, esperada):
        """La regla (OD.1c): solo se mira una meseta cuya MEDIANA vale 1.5 + 10 = 11.5 niveles o menos (el `<=`), y esta recortada si MAS del 1 % de sus muestras vale 1.5 o menos (el `>`: 17 de 1700 es el 1 %
        exacto y no lo es). Devuelve la fraccion o None."""
        v = _meseta(n, k, mediana)
        if mediana == 11.5:
            assert float(np.median(v)) == 11.5, "premisa: la mediana es exactamente el limite"
        assert float(np.median(v)) == (0.0 if k > n // 2 else mediana), "premisa: la mediana del arreglo es la que dice el caso"
        resultado = _pel().meseta_recortada(v)
        if esperada is None:
            assert resultado is None, resultado
        else:
            assert resultado == pytest.approx(esperada, abs=1e-12), resultado

    def test_la_regla_con_una_mediana_de_once_y_medio_que_viene_de_dos_valores_distintos(self):
        """La mediana de un numero PAR de muestras es la media de las dos del medio: 11 y 12 dan 11.5 exacto y la regla (`<=`) la mira; 11 y 13 dan 12 y no."""
        v = np.concatenate([np.zeros(20), np.full(480, 11.0), np.full(500, 12.0)])
        assert float(np.median(v)) == 11.5
        assert _pel().meseta_recortada(v) == pytest.approx(0.02)
        w = np.concatenate([np.zeros(20), np.full(480, 11.0), np.full(500, 13.0)])
        assert float(np.median(w)) == 12.0 and _pel().meseta_recortada(w) is None

    def test_la_regla_no_distingue_la_forma_del_arreglo_ni_su_tipo(self):
        v = _meseta(1200, 36, 4.0)
        for forma in (v, v.reshape(30, 40), v.reshape(40, 30).T, v.astype(np.float32), list(v)):
            assert _pel().meseta_recortada(forma) == pytest.approx(0.03), type(forma)

    def test_sin_muestras_no_hay_recorte_y_no_lanza(self):
        assert _pel().meseta_recortada(np.array([])) is None
        assert _pel().meseta_recortada(np.zeros((0, 5))) is None

    def test_una_muestra_en_el_negro_dentro_de_una_meseta_clara_es_tinta_y_no_recorte(self):
        """La mitad menos una de las muestras en 0 sobre una meseta de 120: es tinta, polvo o un rayon (OD.1c), no el escaner."""
        assert _pel().meseta_recortada(_meseta(1000, 499, 120.0)) is None


class TestMedirPerfilUsaLaReglaDelRecorte:
    """`medir_perfil` ya no lleva la regla en linea (las lineas 1119-1122 de `placa_mensual.py`): le pregunta a `meseta_recortada` por la zona central. Se prueba con una `meseta_recortada` sustituida por otra
    que contesta una fraccion conocida, sobre un perfil plano (la regla de verdad sobre el motor entero la prueban OD.1 y OD.1c, que pasan sin tocarlas)."""

    @staticmethod
    def _perfil():
        pm = _pm()
        return pm.PerfilCentral("R", "crossplane", 0, np.full(600, 6.0), 0, (0, 1), 1, 0.05)

    def _medir(self, base):
        pm = _pm()
        return pm.medir_perfil(self._perfil(), 300.0, 100.0, base, _P(), (100.0, 500.0))

    def test_en_netOD_la_decision_es_la_de_meseta_recortada_sobre_las_muestras_de_la_zona(self, monkeypatch):
        pm = _pm()
        recibidas = []

        def pregunta(valores):
            recibidas.append(np.asarray(valores))
            return 0.37

        monkeypatch.setattr(pm, "meseta_recortada", pregunta)
        m = self._medir(pm.BASE_DENSIDAD_OPTICA)
        assert m.estado == ("no medible: perfil crossplane: la meseta está recortada por el escáner: el 37 % de la zona central de la meseta vale 1.5 niveles o menos y la densidad óptica no existe"), m.estado
        assert len(recibidas) == 1 and recibidas[0].ndim == 1 and recibidas[0].size == 321 and np.all(recibidas[0] == 6.0), "recibe las muestras usables de la zona central"

    def test_en_netOD_si_la_regla_dice_que_no_esta_recortada_el_perfil_sigue_de_largo(self, monkeypatch):
        pm = _pm()
        monkeypatch.setattr(pm, "meseta_recortada", lambda valores: None)
        m = self._medir(pm.BASE_DENSIDAD_OPTICA)
        assert pm.MOTIVO_MESETA_RECORTADA not in m.estado and m.meseta == 6.0, m.estado

    def test_en_valor_de_pixel_no_se_pregunta_por_el_recorte(self, monkeypatch):
        pm = _pm()
        llamadas = []
        monkeypatch.setattr(pm, "meseta_recortada", lambda valores: llamadas.append(valores) or 0.37)
        m = self._medir(pm.BASE_VALOR_DE_PIXEL)
        assert llamadas == [] and pm.MOTIVO_MESETA_RECORTADA not in m.estado, (llamadas, m.estado)


# ===================================================================================================== (4) una pieza por imagen

class TestUnaPiezaPorImagen:
    @staticmethod
    def _pagina(*piezas, ancho=70.0, alto=30.0):
        """Una pagina blanca con piezas (x_mm, y_mm, ancho_mm, alto_mm) de los valores de siempre."""
        lienzo = gen.Lienzo(ancho, alto, 150.0, semilla=5)
        for x, y, w, h in piezas:
            lienzo.pegar_pelicula(x, y, w, h, VALORES, SIGMA)
        return lienzo

    def test_dos_piezas_en_la_imagen_no_se_mide_ninguna_y_se_dice(self):
        m = medir(self._pagina((5, 5, 18, 18), (35, 5, 18, 18)).codificar())
        assert m.estado == PREFIJO + VARIAS_PIEZAS.format(n=2) and m.piezas == 2, (m.estado, m.piezas)
        _sin_numeros(m)
        assert m.recortadas is None and m.region is None

    def test_tres_piezas_dicen_tres(self):
        m = medir(self._pagina((3, 5, 18, 18), (26, 5, 18, 18), (49, 5, 18, 18)).codificar())
        assert m.estado == PREFIJO + VARIAS_PIEZAS.format(n=3) and m.piezas == 3, (m.estado, m.piezas)

    def test_una_pieza_y_una_mota_de_dos_milimetros_son_una_pieza_y_se_mide(self):
        pagina = self._pagina((5, 5, 18, 18))
        pagina.pegar_pelicula(40, 20, 2, 2, (60, 60, 60))
        m = medir(pagina.codificar())
        assert m.estado == "ok" and m.piezas == 1, (m.estado, m.piezas)
        for k, capa in enumerate(LAS_TRES):
            assert abs(m.valor(capa) - VALORES[k]) <= 0.1

    @pytest.mark.parametrize("lado, cuenta", [(10.5, True), (9.0, False)], ids=["10_5_mm_son_110_mm2", "9_mm_son_81_mm2"])
    def test_una_zona_de_pelicula_cuenta_como_pieza_desde_un_centimetro_cuadrado(self, lado, cuenta):
        """Cuenta como pieza toda zona conexa de pelicula de 1 cm2 o mas (lo que ocupa la region central); lo mas chico es polvo, una marca o un fleco. Medidas por el generador: 110 y 81 mm2."""
        pagina = self._pagina((5, 5, 18, 18))
        pagina.pegar_pelicula(40, 8, lado, lado, VALORES, SIGMA)
        m = medir(pagina.codificar())
        if cuenta:
            assert m.estado == PREFIJO + VARIAS_PIEZAS.format(n=2) and m.piezas == 2, (m.estado, m.piezas)
        else:
            assert m.estado == "ok" and m.piezas == 1, (m.estado, m.piezas)

    def test_el_conteo_de_piezas_es_el_mismo_con_la_escala_del_procedimiento(self):
        lienzo = gen.Lienzo(70.0, 30.0, 600.0, semilla=5)
        lienzo.pegar_pelicula(5, 5, 18, 18, VALORES, SIGMA)
        lienzo.pegar_pelicula(35, 5, 18, 18, VALORES, SIGMA)
        m = medir(lienzo.codificar(), "procedimiento")
        assert m.estado == PREFIJO + VARIAS_PIEZAS.format(n=2) and m.piezas == 2


# ===================================================================================================== (5) la escala de la pieza

class TestLaEscalaDeLaPieza:
    @pytest.mark.parametrize("declarada", [96, 72])
    def test_una_resolucion_de_editor_no_es_la_del_escaneo_y_la_pieza_no_se_mide(self, declarada):
        m = medir(_pieza(dpi_declarado=declarada).datos)
        assert m.estado == PREFIJO + DE_EDITOR.format(dpi=declarada), m.estado
        _sin_numeros(m)
        assert m.piezas is None and m.escala_mm is None and m.escala == "declarada" and m.recortadas is None

    def test_una_pieza_que_no_declara_su_resolucion_no_se_mide(self):
        m = medir(_pieza(dpi_declarado=None).datos)
        assert m.estado == PREFIJO + SIN_RESOLUCION, m.estado
        _sin_numeros(m)
        assert m.escala_mm is None and m.procedencia["dpi_declarado"] is None and m.procedencia["clase_resolucion"] == "sin_dato"

    def test_con_la_escala_del_procedimiento_una_pieza_de_150_ppp_es_de_otra_resolucion(self):
        m = medir(_pieza().datos, "procedimiento")
        assert m.estado == PREFIJO + OTRA_RESOLUCION.format(dpi=150), m.estado
        _sin_numeros(m)
        assert m.escala == "procedimiento" and m.escala_mm is None and m.piezas is None

    def test_con_la_escala_del_procedimiento_se_mide_como_una_virgen_y_un_editor_solo_avisa(self):
        """«procedimiento» (el valor por omision) es la escala de la virgen: una resolucion de editor no se rechaza, la cadena de captura AVISA."""
        pieza = _pieza(dpi=600.0, dpi_declarado=96)
        m = medir(pieza.datos, "procedimiento")
        assert m.estado == "ok" and m.procedencia["clase_resolucion"] == "editor", (m.estado, m.procedencia["clase_resolucion"])
        assert any("vuelto a guardar por un editor" in a for a in m.avisos)

    @pytest.mark.parametrize("dpi, lado_mm, region_px", [(300.0, 36.0, 118), (1200.0, 18.0, 472), (150.0, 18.0, 59)], ids=["300ppp", "1200ppp", "150ppp"])
    def test_la_resolucion_que_declara_el_archivo_es_la_escala_de_la_pieza(self, dpi, lado_mm, region_px):
        """La escala de la pieza es la que declara su archivo (DC15), cualquiera menos una de editor o ninguna: el mismo trozo de 10 mm son 59, 118 o 472 pixeles."""
        pieza = _pieza(dpi=dpi, lado_mm=lado_mm)
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        x0, y0, x1, y1 = _caja_central(m)
        assert (x1 - x0, y1 - y0) == (region_px, region_px) and m.escala_mm == pytest.approx(gen.MM_POR_PULGADA / dpi)
        for capa in LAS_TRES:
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1

    def test_una_escala_que_no_es_ninguna_de_las_dos_es_un_error_de_quien_llama(self):
        with pytest.raises(ValueError, match="procedimiento, declarada"):
            medir(_pieza().datos, escala="otra")

    @pytest.mark.parametrize("P", [{}, None, {"resolucion_escaneo_dpi": 600.0}], ids=["vacio", "none", "incompleto"])
    def test_sin_la_escala_del_procedimiento_en_P_es_un_error_de_quien_llama(self, P):
        with pytest.raises(ValueError, match="escala del procedimiento"):
            _pel().medir_pieza_uniforme(_pieza().datos, P, "pieza.tif", FECHA)

    def test_las_dos_escalas_dan_lo_mismo_con_una_pieza_de_600_ppp(self):
        pieza = _pieza(dpi=600.0)
        a, b = medir(pieza.datos, "declarada"), medir(pieza.datos, "procedimiento")
        assert a.estado == b.estado == "ok" and a.escala_mm == b.escala_mm
        assert [a.centro[c] for c in CAPAS] == [b.centro[c] for c in CAPAS]

    def test_la_escala_por_omision_es_la_del_procedimiento_y_las_dos_estan_declaradas(self):
        pel = _pel()
        assert pel.ESCALAS_DE_LA_PIEZA == ("procedimiento", "declarada")
        firma = inspect.signature(pel.medir_pieza_uniforme)
        assert list(firma.parameters) == ["datos", "P", "nombre_archivo", "fecha_calculo", "escala"]
        assert firma.parameters["escala"].default == "procedimiento" and firma.parameters["nombre_archivo"].default == "" and firma.parameters["fecha_calculo"].default is None


def _pagina_a(dpi, lado_mm=100.0, margen_mm=25.0, valores=VALORES):
    """Una pieza uniforme (sin ruido) de `lado_mm` en una pagina que declara `dpi`: a resoluciones tan bajas la pagina son unas decenas de pixeles."""
    return gen.pieza_uniforme(valores, lado_mm=lado_mm, dpi=dpi, sigma=0.0, margen_mm=margen_mm)


class TestUnaResolucionDeclaradaQueNoLlegaAUnPixel:
    """CD2-PROD-01 (ronda 1 de revision). Con `escala="declarada"` la resolucion del archivo vuelve en pixeles cada longitud en milimetros de la medicion. A 2.54 dpi (1 pixel por cm: lo que escribe un TIFF con la
    resolucion en centimetros) un bloque de 5 mm es medio pixel y `_virgen_bloques` redondeaba su lado a 0: `range()` lanzaba `ValueError` (paso de cero) en una funcion que promete NO lanzar por el contenido."""

    @pytest.mark.parametrize("dpi, texto", [(1.0, "1"), (2.0, "2"), (2.54, "2.54")], ids=["1_dpi", "2_dpi", "2_54_dpi_un_pixel_por_cm"])
    def test_un_bloque_de_5_mm_que_no_llega_a_un_pixel_no_se_mide_y_lo_dice_sin_lanzar(self, dpi, texto):
        m = medir(_pagina_a(dpi).datos)
        assert m.estado == PREFIJO + BAJA.format(dpi=texto, que="un bloque", lado="5"), m.estado
        _sin_numeros(m)
        assert m.escala == "declarada" and m.piezas is None and m.escala_mm is None and m.procedencia["dpi_declarado"] == dpi
        assert [(p.nombre, p.resultado) for p in m.pruebas] == [("C1 cadena", "rechazo")], m.pruebas

    @pytest.mark.parametrize("dpi", [2.6, 3.0, 4.0, 10.0], ids=["2_6_dpi", "3_dpi", "4_dpi", "10_dpi"])
    def test_apenas_por_encima_del_limite_la_pieza_se_mide_con_los_pixeles_que_tiene(self, dpi):
        """El limite es el de la propia conversion (el lado del bloque redondea a 0), no un escalon puesto aparte: a 2.6 dpi el bloque (y la region central) son 1 pixel y se mide."""
        pieza = _pagina_a(dpi)
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        x0, y0, x1, y1 = _caja_central(m)
        lado = gen.pixeles(10.0, dpi)
        assert lado >= 1 and (x1 - x0, y1 - y0) == (lado, lado), ((x1 - x0, y1 - y0), lado)
        for capa in CAPAS:
            assert m.centro[capa]["n"] == lado ** 2, (capa, m.centro[capa]["n"])
        for capa in LAS_TRES:
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1, (capa, m.valor(capa), pieza.nominal(capa))
        assert abs(m.valor("gris") - pieza.nominal("gris")) <= 0.5, "el gris de una pieza sin ruido es un entero (el redondeo de OpenCV), no el 126.12 de BT.601"

    def test_ninguna_resolucion_declarada_lanza_y_se_rechaza_justo_cuando_el_bloque_redondea_a_cero_pixeles(self):
        """Un barrido de 0.5 a 12 dpi cada 0.25 (y 2.54): nunca lanza, se rechaza con el motivo de la resolucion exactamente cuando el lado de un bloque de 5 mm, `round(5 / (25.4 / dpi))`, es 0 (la cuenta
        del generador, no la del motor) y de ahi para arriba la pieza es «ok»."""
        barrido = [float(d) for d in np.arange(0.5, 12.01, 0.25)] + [2.54]
        rechazadas = []
        for dpi in barrido:
            m = medir(_pagina_a(dpi).datos)
            baja = int(round(5.0 / (gen.MM_POR_PULGADA / dpi))) < 1
            if baja:
                assert m.estado == PREFIJO + BAJA.format(dpi=f"{dpi:g}", que="un bloque", lado="5"), (dpi, m.estado)
                rechazadas.append(dpi)
            else:
                assert m.estado == "ok", (dpi, m.estado)
        assert rechazadas == [d for d in barrido if d <= 2.54] and len(rechazadas) == 10, rechazadas

    def test_la_region_central_que_no_llega_a_un_pixel_tampoco_se_mide(self):
        """Con los parametros por omision manda el bloque de 5 mm; si la region central se pide mas chica (1 mm), a 10 dpi (2.54 mm por pixel) es ELLA la que no llega a un pixel. A 150 dpi, la misma, se mide."""
        m = medir(_pagina_a(10.0).datos, P=_P(lado_region_uniformidad_virgen_mm=1.0))
        assert m.estado == PREFIJO + BAJA.format(dpi="10", que="la región central", lado="1"), m.estado
        _sin_numeros(m)
        bien = medir(_pieza().datos, P=_P(lado_region_uniformidad_virgen_mm=1.0))
        x0, y0, x1, y1 = _caja_central(bien)
        assert bien.estado == "ok" and (x1 - x0, y1 - y0) == (gen.pixeles(1.0, 150.0),) * 2, (bien.estado, (x1 - x0, y1 - y0))

    def test_con_la_escala_del_procedimiento_el_motivo_sigue_siendo_el_de_otra_resolucion(self):
        """La resolucion «declarada» es el unico camino en que el contenido del archivo se vuelve escala: con «procedimiento» (600 ppp) un archivo de 2 dpi es de otra resolucion, como antes."""
        m = medir(_pagina_a(2.0).datos, "procedimiento")
        assert m.estado == PREFIJO + OTRA_RESOLUCION.format(dpi=2), m.estado


class TestLaPDeQuienLlamaQuedaIntacta:
    """R1-PRU-01 (ronda 1 de revision). CD.3 a CD.5 reusaran UNA `P` entre pieza y pieza y con la virgen: la resolucion declarada de una pieza se pone en una `P` PROPIA de la medicion
    (`P = {**P, ...}`), nunca en la de quien llama; si se escribiera en ella, una virgen de 600 ppp medida despues se rechazaria por estar «a otra resolucion»."""

    ESCENAS = {
        "150ppp_declarada": (lambda: _pieza().datos, "declarada"),
        "96ppp_de_editor_declarada": (lambda: _pieza(dpi_declarado=96).datos, "declarada"),
        "sin_resolucion_declarada": (lambda: _pieza(dpi_declarado=None).datos, "declarada"),
        "2ppp_demasiado_baja_declarada": (lambda: _pagina_a(2.0).datos, "declarada"),
        "150ppp_con_la_del_procedimiento": (lambda: _pieza().datos, "procedimiento"),
        "600ppp_con_la_del_procedimiento": (lambda: _pieza(dpi=600.0).datos, "procedimiento"),
        "basura_declarada": (lambda: b"esto no es una imagen", "declarada"),
    }

    @pytest.mark.parametrize("escena", list(ESCENAS))
    def test_medir_una_pieza_no_cambia_la_P_de_quien_llama(self, escena):
        construir, escala = self.ESCENAS[escena]
        P = _P()
        antes = copy.deepcopy(P)
        medir(construir(), escala, P=P)
        assert P == antes, {k: (antes[k], P[k]) for k in P if P[k] != antes.get(k)}

    def test_una_virgen_de_600_ppp_medida_despues_de_una_pieza_de_150_con_la_misma_P_sigue_siendo_valida(self):
        P = _P()
        pieza = medir(_pieza().datos, "declarada", P=P)
        virgen = medir_virgen(_virgen_sintetica().codificar(8), P=P)
        assert pieza.estado == "ok" and virgen.estado == "ok", (pieza.estado, virgen.estado)
        assert P["resolucion_escaneo_dpi"] == 600.0 and virgen.procedencia["clase_resolucion"] == "coincide"


# ===================================================================================================== (6) lo que no se le juzga a una pieza

class TestLoQueNoSeLeJuzgaAUnaPieza:
    @pytest.mark.parametrize("valores", [(60.0, 65.0, 70.0), (225.0, 225.0, 225.0), (105.0, 174.0, 130.0)], ids=["oscura", "tan_clara_como_el_fondo", "azul_fuera_del_testigo"])
    def test_una_pieza_fuera_del_rango_de_una_virgen_se_mide_y_no_trae_ni_rango_ni_azul_testigo(self, valores):
        pieza = _pieza(valores=valores)
        m = medir(pieza.datos)
        assert m.estado == "ok", m.estado
        nombres = [p.nombre for p in m.pruebas]
        assert "rango" not in nombres and "azul testigo" not in nombres, nombres
        for capa in CAPAS:
            assert abs(m.valor(capa) - pieza.nominal(capa)) <= 0.1, (capa, m.valor(capa))

    def test_una_pieza_de_18_mm_tiene_menos_de_400_mm2_limpios_y_se_mide(self):
        pieza = _pieza()
        m = medir(pieza.datos)
        assert m.estado == "ok" and m.region["area_mm2"] < 400.0, (m.estado, m.region["area_mm2"])

    def test_con_menos_de_4_bloques_la_uniformidad_avisa_con_su_cola_y_la_pieza_se_mide(self):
        """Bloques de 8 mm (menos de 4 caben en 14 mm): la virgen lo rechaza; una pieza lo AVISA: el valor es la region central y no la uniformidad entre bloques."""
        m = medir(_pieza().datos, P=_P(lado_bloque_virgen_mm=8.0))
        texto = POCOS_BLOQUES.format(lado=8)
        assert m.estado == "ok", m.estado
        assert [(p.resultado, p.texto) for p in m.pruebas if p.nombre == "C5 uniformidad"] == [("aviso", texto)] and texto in m.avisos, m.pruebas

    def test_si_no_le_cabe_su_region_central_la_pieza_no_se_mide_y_lo_dice(self):
        """12 x 12 mm: a 2 mm de los bordes quedan 8 x 8 mm y la region central es de 10 x 10. El primer rechazo es el de la region central (C5 solo avisa)."""
        m = medir(_pieza(lado_mm=12.0).datos)
        assert m.estado == PREFIJO + NO_CABE, m.estado
        _sin_numeros(m)
        assert m.piezas == 1 and m.escala_mm == pytest.approx(gen.MM_POR_PULGADA / 150.0)
        assert [p.resultado for p in m.pruebas if p.nombre == "C5 uniformidad"] == ["aviso"]

    def test_si_la_region_central_esta_toda_cubierta_de_tinta_la_pieza_no_se_mide_y_lo_dice(self):
        pieza = _pieza(lado_mm=40.0, manchas=[(10.0, 10.0, 20.0, 20.0, -70.0)])
        m = medir(pieza.datos)
        assert m.estado == PREFIJO + TODA_CUBIERTA, m.estado
        _sin_numeros(m)

    def test_no_se_lee_el_archivo(self):
        basura = b"esto no es una imagen"
        m = medir(basura)
        assert m.estado == PREFIJO + NO_SE_LEE, m.estado
        _sin_numeros(m)
        assert m.piezas is None and m.escala_mm is None and m.procedencia["sha256"] == hashlib.sha256(basura).hexdigest() and m.procedencia["bytes"] == len(basura)

    def test_el_estado_de_una_pieza_que_no_se_mide_lleva_el_prefijo_de_la_app_y_no_el_de_la_virgen(self):
        """DA-88: «no medible: <motivo>», no el «no válida: » de la película virgen."""
        for datos in (b"basura", _pieza(dpi_declarado=96).datos, _pieza(lado_mm=12.0).datos):
            assert medir(datos).estado.startswith("no medible: ") and "no válida" not in medir(datos).estado


def _escena_dos_piezas():
    lienzo = gen.Lienzo(70.0, 30.0, 150.0, semilla=5)
    lienzo.pegar_pelicula(5, 5, 18, 18, VALORES, SIGMA)
    lienzo.pegar_pelicula(35, 5, 18, 18, VALORES, SIGMA)
    return lienzo.codificar()


def _escena_polvo():
    lienzo = gen.Lienzo(18.0, 18.0, 150.0, semilla=5)
    lienzo.pegar_pelicula(0, 0, 18.0, 18.0, VALORES, SIGMA)
    lienzo.pegar_punteado(0, 0, 18.0, 18.0, paso_px=4, lado_px=2, delta=60.0)
    return lienzo.codificar()


class TestLoQueNoSeMideNoTraeNingunNumero:
    """R1-PRU-04 (ronda 1 de revision). La pieza que no se mide no trae NINGUN numero medido, sea cual sea la causa (CD2-D2: «como la virgen rechazada», que no trae region): ni centro, ni capas, ni la region de la
    pelicula, ni los recortes por capa. Antes, una pieza «no medible» por su region central (no cabe, o toda cubierta) traia `region` con numeros y, la cubierta, `recortadas` (con la roja en el negro, 1.0).
    Lo que conserva es lo que explica el rechazo: las pruebas, la procedencia, cuantas piezas hay, la escala y la tabla si se llego a medir. Cada escena: (bytes, escala, motivo, piezas, escala_mm, tabla)."""

    ESCENAS = {
        "no_se_lee": (lambda: b"esto no es una imagen", "declarada", NO_SE_LEE, None, None, False),
        "resolucion_de_editor": (lambda: _pieza(dpi_declarado=96).datos, "declarada", DE_EDITOR.format(dpi=96), None, None, False),
        "sin_resolucion": (lambda: _pieza(dpi_declarado=None).datos, "declarada", SIN_RESOLUCION, None, None, False),
        "otra_resolucion": (lambda: _pieza().datos, "procedimiento", OTRA_RESOLUCION.format(dpi=150), None, None, False),
        "resolucion_demasiado_baja": (lambda: _pagina_a(2.0).datos, "declarada", BAJA.format(dpi="2", que="un bloque", lado="5"), None, None, False),
        "dos_piezas": (_escena_dos_piezas, "declarada", VARIAS_PIEZAS.format(n=2), 2, 25.4 / 150.0, False),
        "pagina_sin_pelicula": (lambda: gen.Lienzo(40.0, 40.0, 150.0, semilla=5).codificar(), "declarada", SIN_PELICULA, 0, 25.4 / 150.0, False),
        "toda_la_pelicula_cubierta_de_polvo": (_escena_polvo, "declarada", NO_QUEDA_LIMPIA, 1, 25.4 / 150.0, False),
        "no_cabe_la_region_central": (lambda: _pieza(lado_mm=12.0).datos, "declarada", NO_CABE, 1, 25.4 / 150.0, True),
        "region_central_toda_cubierta": (lambda: _pieza(lado_mm=40.0, manchas=[(10.0, 10.0, 20.0, 20.0, -70.0)]).datos, "declarada", TODA_CUBIERTA, 1, 25.4 / 150.0, True),
        "toda_cubierta_con_la_roja_en_el_negro": (lambda: _pieza(valores=(0.4, 120.0, 95.0), lado_mm=40.0, manchas=[(10.0, 10.0, 20.0, 20.0, -70.0)]).datos, "declarada", TODA_CUBIERTA, 1,
                                                  25.4 / 150.0, True),
    }

    @pytest.mark.parametrize("escena", list(ESCENAS))
    def test_una_pieza_que_no_se_mide_no_trae_ningun_numero_y_conserva_lo_que_explica_el_rechazo(self, escena):
        construir, escala, motivo, piezas, escala_mm, con_tabla = self.ESCENAS[escena]
        m = medir(construir(), escala)
        assert m.estado == PREFIJO + motivo, m.estado
        _sin_numeros(m)
        assert m.piezas == piezas and (m.escala_mm is None if escala_mm is None else m.escala_mm == pytest.approx(escala_mm)), (m.piezas, m.escala_mm)
        assert (m.uniformidad is not None) is con_tabla, "la tabla de uniformidad (con todo) se conserva cuando se llego a medir: es lo que explica por que no se mide"
        assert [p.resultado for p in m.pruebas].count("rechazo") == 1 and m.pruebas[-1].resultado == "rechazo", [(p.nombre, p.resultado) for p in m.pruebas]
        assert m.procedencia["sha256"] and m.parametros, "la procedencia y los parametros viajan siempre"

    def test_una_pieza_que_se_mide_si_trae_su_region_y_sus_recortes(self):
        """El otro lado: «ok» trae la region de la pelicula y los cuatro recortes (None o la fraccion), para que el rechazo de arriba no sea simplemente que nunca se devuelven."""
        m = medir(_pieza(valores=(0.4, 120.0, 95.0)).datos)
        assert m.estado == "ok" and set(m.region) >= {"caja", "n", "area_mm2"} and set(m.recortadas) == set(CAPAS), (m.estado, m.region, m.recortadas)
        assert m.recortadas["R"] is not None and all(m.recortadas[c] is None for c in ("G", "B", "gris"))


# ===================================================================================================== (7) la pieza y la virgen son la misma medicion

def _virgen_sintetica(valores=(105.0, 174.0, 82.0), lado=60.0, pagina=66.0, dpi=600.0, sigma=1.5, **kw):
    """Una pelicula virgen sintetica (la «virgen» del lote de siempre: R 105, G 174, B 82) centrada en una pagina blanca."""
    lienzo = gen.Lienzo(pagina, pagina, dpi, semilla=9)
    lienzo.pegar_pelicula((pagina - lado) / 2, (pagina - lado) / 2, lado, lado, valores, sigma, **kw)
    return lienzo


def _igual_que_la_virgen(virgen, pieza):
    """Lo que la virgen y la pieza comparten: capas, tabla de uniformidad y ruido, region, procedencia, parametros y avisos; y las pruebas, salvo las dos que solo tiene la virgen."""
    for capa in CAPAS:
        assert dataclasses.asdict(virgen.capas[capa]) == dataclasses.asdict(pieza.capas[capa]), capa
    assert virgen.uniformidad == pieza.uniformidad and virgen.region == pieza.region and virgen.procedencia == pieza.procedencia and virgen.parametros == pieza.parametros
    assert virgen.avisos == pieza.avisos
    assert [(p.nombre, p.resultado, p.texto) for p in virgen.pruebas if p.nombre not in ("rango", "azul testigo")] == [(p.nombre, p.resultado, p.texto) for p in pieza.pruebas]


class TestLaPiezaYLaVirgenSonLaMismaMedicion:
    def test_una_virgen_sintetica_de_60_mm_da_las_mismas_capas_tabla_region_y_procedencia_como_pieza(self):
        datos = _virgen_sintetica().codificar(8)
        v, p = medir_virgen(datos), medir(datos, "procedimiento", nombre="virgen.tif")
        assert v.estado == "ok" and p.estado == "ok", (v.estado, p.estado)
        _igual_que_la_virgen(v, p)

    def test_con_tinta_y_motas_en_la_pelicula_tambien(self):
        lienzo = _virgen_sintetica()
        lienzo.pegar_mancha(20.0, 20.0, 3.0, 3.0, -40.0)
        lienzo.pegar_mancha(45.0, 30.0, 1.5, 1.5, 70.0)
        datos = lienzo.codificar(8)
        v, p = medir_virgen(datos), medir(datos, "procedimiento", nombre="virgen.tif")
        assert v.estado == "ok" and p.estado == "ok"
        _igual_que_la_virgen(v, p)
        assert any(pr.nombre == "C6 motas" and pr.resultado == "aviso" for pr in p.pruebas), "premisa: la escena si tiene motas"

    def test_la_pelicula_oscura_la_rechaza_la_virgen_por_el_rango_y_la_pieza_la_mide(self):
        lienzo = _virgen_sintetica((60.0, 65.0, 70.0), lado=45.0, pagina=50.0)
        datos = lienzo.codificar(8)
        v, p = medir_virgen(datos), medir(datos, "procedimiento")
        assert v.estado.startswith("no válida: fuera del rango esperado de una película sin irradiar"), v.estado
        assert p.estado == "ok"
        for k, capa in enumerate(LAS_TRES):
            assert abs(p.valor(capa) - (60.0, 65.0, 70.0)[k]) <= 0.1

    def test_la_pelicula_de_18_mm_la_rechaza_la_virgen_por_el_area_y_la_pieza_la_mide(self):
        lienzo = gen.Lienzo(24.0, 24.0, 600.0, semilla=9)
        lienzo.pegar_pelicula(3.0, 3.0, 18.0, 18.0, (105.0, 174.0, 82.0), 1.5)
        datos = lienzo.codificar(8)
        v, p = medir_virgen(datos), medir(datos, "procedimiento")
        assert v.estado.startswith("no válida: no hay película virgen suficiente a 2 mm de los bordes"), v.estado
        assert p.estado == "ok" and abs(p.valor("G") - 174.0) <= 0.1

    def test_epson179_real_medida_como_pieza_tiene_las_mismas_capas_tabla_region_y_procedencia_que_como_virgen(self):
        ruta = _corpus.pelicula("VIRGEN_EPSON179")
        if ruta is None:
            pytest.skip("HI-0: EPSON179.TIF no esta")
        datos = Path(ruta).read_bytes()
        v = medir_virgen(datos, "EPSON179.TIF")
        p = medir(datos, "procedimiento", nombre="EPSON179.TIF")
        assert v.estado == "ok" and p.estado == "ok" and p.piezas == 1, (v.estado, p.estado, p.piezas)
        _igual_que_la_virgen(v, p)
        del datos, v, p
        gc.collect()


class TestLaVirgenNoCambio:
    """La virgen sigue dando, en cada rama de `piso_de_pelicula_virgen`, el estado y las pruebas de HEAD (99aac85): los literales de `LA_VIRGEN_DE_HEAD` se midieron ANTES de tocar produccion."""

    @staticmethod
    def _escena(nombre):
        def virgen(valores=(105.0, 174.0, 82.0), lado=45.0, pagina=50.0, **kw):
            return _virgen_sintetica(valores, lado=lado, pagina=pagina, sigma=0.0, **kw)             # sin ruido: los literales de HEAD no dependen de ninguna semilla

        if nombre == "no_se_lee":
            return b"esto no es una imagen"
        if nombre == "otra_resolucion":
            return virgen().codificar(8, 300)
        if nombre == "sin_pelicula":
            return gen.Lienzo(50, 50, 600).codificar(8)
        if nombre == "area_chica":
            return virgen(lado=15.0).codificar(8)
        if nombre == "todo_cubierto_de_polvo":
            lienzo = virgen()
            lienzo.pegar_punteado(2.5, 2.5, 45.0, 45.0, paso_px=6, lado_px=2, delta=60.0)
            return lienzo.codificar(8)
        if nombre == "rango_oscura":
            return virgen((60.0, 65.0, 70.0)).codificar(8)
        if nombre == "rango_clara":
            return virgen((225.0, 225.0, 225.0)).codificar(8)
        if nombre == "editor_96":
            return virgen().codificar(8, 96)
        if nombre == "sin_resolucion":
            return virgen().codificar(8, None)
        if nombre == "ok":
            return virgen().codificar(8)
        if nombre == "ok_inclinada":
            return virgen(lado=70.0, pagina=76.0, pendiente_x=0.05, pendiente_y=-0.03).codificar(8)
        raise KeyError(nombre)

    @pytest.mark.parametrize("nombre", list(LA_VIRGEN_DE_HEAD))
    def test_cada_rama_da_el_estado_y_las_pruebas_de_HEAD(self, nombre):
        esperado = LA_VIRGEN_DE_HEAD[nombre]
        r = medir_virgen(self._escena(nombre), nombre + ".tif")
        real = {"estado": r.estado, "pruebas": [[p.nombre, p.resultado, p.texto] for p in r.pruebas], "avisos": list(r.avisos),
                "clase_resolucion": r.procedencia["clase_resolucion"], "dpi_declarado": r.procedencia["dpi_declarado"]}
        if r.estado == "ok":
            real["capas"] = {c: [r.capas[c].mediana, r.capas[c].n, r.capas[c].iqr, r.capas[c].media] for c in CAPAS}
            real["region"] = r.region
            real["uniformidad"] = r.uniformidad
        assert _diferencia(real, esperado) is None, _diferencia(real, esperado)

    @pytest.mark.parametrize("nombre", [n for n, e in LA_VIRGEN_DE_HEAD.items() if e["estado"] != "ok"])
    def test_una_virgen_que_no_sirve_no_trae_numeros_en_ninguna_capa_y_su_estado_es_el_primer_rechazo(self, nombre):
        r = medir_virgen(self._escena(nombre), nombre + ".tif")
        primero = next(p.texto for p in r.pruebas if p.resultado == "rechazo")
        assert r.estado == "no válida: " + primero
        for capa in CAPAS:
            assert r.capas[capa].estado == r.estado and r.capas[capa].mediana is None and r.capas[capa].media is None and r.region is None

    def test_el_dict_de_una_virgen_es_json_y_se_reconstruye_igual(self):
        pel = _pel()
        r = medir_virgen(self._escena("ok_inclinada"), "ok_inclinada.tif")
        d = r.como_dict()
        assert pel.referencia_virgen_desde_dict(d).como_dict() == d and list(d) == ["version", "estado", "capas", "pruebas", "avisos", "region", "procedencia", "parametros", "uniformidad"]


# ===================================================================================================== (8) la copia del escaneo

class TestLaCopiaDelEscaneo:
    def test_con_una_subcarpeta_la_copia_va_ahi_y_nada_se_escribe_en_la_de_la_virgen(self, tmp_path):
        pel = _pel()
        pieza = _pieza()
        m = medir(pieza.datos, nombre="5.tif")
        pel._copiar_el_escaneo(str(tmp_path), m, pieza.datos, subcarpeta="calibraciones_pelicula_escaneos")
        destino = tmp_path / "calibraciones_pelicula_escaneos" / (hashlib.sha256(pieza.datos).hexdigest() + ".tif")
        assert destino.read_bytes() == pieza.datos
        assert [p.name for p in tmp_path.iterdir()] == ["calibraciones_pelicula_escaneos"], "la carpeta de la virgen no se crea"

    def test_sin_subcarpeta_la_copia_va_a_la_de_la_virgen(self, tmp_path):
        pel = _pel()
        datos = _virgen_sintetica(lado=45.0, pagina=50.0).codificar(8)
        ref = medir_virgen(datos, "virgen.tif")
        pel._copiar_el_escaneo(str(tmp_path), ref, datos)
        assert pel.CARPETA_ESCANEOS_VIRGEN == "piso_pelicula_virgen_escaneos"
        assert (tmp_path / "piso_pelicula_virgen_escaneos" / (ref.procedencia["sha256"] + ".tif")).read_bytes() == datos
        assert [p.name for p in tmp_path.iterdir()] == ["piso_pelicula_virgen_escaneos"]

    def test_guardar_la_referencia_de_la_virgen_sigue_copiando_el_escaneo_a_su_carpeta(self, tmp_path):
        pel = _pel()
        datos = _virgen_sintetica(lado=45.0, pagina=50.0).codificar(8)
        ref = medir_virgen(datos, "virgen.tif")
        pel.guardar_referencia_virgen(ref, str(tmp_path), datos, usuario="fisico")
        assert (tmp_path / "piso_pelicula_virgen_escaneos" / (ref.procedencia["sha256"] + ".tif")).read_bytes() == datos
        assert sorted(p.name for p in tmp_path.iterdir()) == ["piso_pelicula_virgen.json", "piso_pelicula_virgen_escaneos"]

    def test_la_misma_pieza_en_dos_subcarpetas_se_copia_a_cada_una_y_una_segunda_vez_no_cambia_nada(self, tmp_path):
        pel = _pel()
        pieza = _pieza()
        m = medir(pieza.datos)
        for sub in ("a", "b", "a"):
            pel._copiar_el_escaneo(str(tmp_path), m, pieza.datos, subcarpeta=sub)
        sha = hashlib.sha256(pieza.datos).hexdigest()
        assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == ["a", f"a/{sha}.tif", "b", f"b/{sha}.tif"]

    def test_un_archivo_ya_copiado_con_otro_contenido_se_rechaza_tambien_en_la_subcarpeta_de_la_calibracion(self, tmp_path):
        pel = _pel()
        pieza = _pieza()
        m = medir(pieza.datos)
        carpeta = tmp_path / "calibraciones_pelicula_escaneos"
        carpeta.mkdir()
        (carpeta / (hashlib.sha256(pieza.datos).hexdigest() + ".tif")).write_bytes(b"otro contenido")
        with pytest.raises(ValueError, match="ya hay un archivo"):
            pel._copiar_el_escaneo(str(tmp_path), m, pieza.datos, subcarpeta="calibraciones_pelicula_escaneos")
        assert (carpeta / (hashlib.sha256(pieza.datos).hexdigest() + ".tif")).read_bytes() == b"otro contenido"

    def test_la_firma_de_la_copia_lleva_la_subcarpeta_con_la_de_la_virgen_por_omision(self):
        pel = _pel()
        firma = inspect.signature(pel._copiar_el_escaneo)
        assert list(firma.parameters) == ["carpeta", "referencia", "datos", "subcarpeta"]
        assert firma.parameters["subcarpeta"].default == pel.CARPETA_ESCANEOS_VIRGEN == "piso_pelicula_virgen_escaneos"


# ===================================================================================================== (9) las 21 piezas reales de H9

def _pieza_de_h9(dosis):
    ruta = CARPETA_DE_H9 / f"{dosis}.tif"
    return ruta.read_bytes()


@pytest.fixture(scope="module")
def _h9_completo():
    """Si la carpeta de las piezas esta, tienen que estar las 21 (si falta una, falla nombrandola); si la carpeta no esta, salta como las demas peliculas del corpus (HI-0)."""
    if not CARPETA_DE_H9.is_dir():
        pytest.skip(f"HI-0: no esta {CARPETA_DE_H9}")
    faltan = [d for d in H9_MEDIAS if not (CARPETA_DE_H9 / f"{d}.tif").is_file()]
    assert not faltan, f"faltan piezas de calibracion en {CARPETA_DE_H9}: {faltan}"


class TestLas21PiezasRealesDeH9:
    @pytest.mark.parametrize("dosis", sorted(H9_MEDIAS))
    def test_la_media_de_la_region_central_es_la_medida_independiente_del_22_10_a_una_decima_de_nivel(self, _h9_completo, dosis):
        m = medir(_pieza_de_h9(dosis), nombre=f"{dosis}.tif")
        assert m.estado == "ok" and m.piezas == 1, (m.estado, m.piezas)
        for k, capa in enumerate(LAS_TRES):
            assert abs(m.valor(capa) - H9_MEDIAS[dosis][k]) <= 0.1, (dosis, capa, m.valor(capa), H9_MEDIAS[dosis][k])
        assert all(3400 <= m.centro[c]["n"] <= 59 * 59 for c in CAPAS), "casi los 59 x 59 pixeles de 10 mm a 150 ppp: la tinta o las motas apartan a lo sumo unos pocos (la de 450 cGy, dos)"
        assert m.recortadas == {c: None for c in CAPAS}, "ninguna capa recortada por el escaner"
        assert m.escala_mm == pytest.approx(gen.MM_POR_PULGADA / 150.0) and m.procedencia["bits"] == 16 and m.procedencia["dpi_declarado"] == 150.0

    def test_con_la_escala_del_procedimiento_las_21_son_de_otra_resolucion(self, _h9_completo):
        for dosis in sorted(H9_MEDIAS):
            m = medir(_pieza_de_h9(dosis), "procedimiento", nombre=f"{dosis}.tif")
            assert m.estado == PREFIJO + OTRA_RESOLUCION.format(dpi=150), (dosis, m.estado)

    def test_ninguna_pieza_de_h9_es_una_virgen_pero_todas_se_miden(self, _h9_completo):
        """Las 21 estan fuera del rango de una pelicula sin irradiar y miden 1.8 cm (204 a 235 mm2 limpios): la virgen no las mediria; la pieza si (CD2-D1)."""
        for dosis in (5, 500, 1000):
            m = medir(_pieza_de_h9(dosis), nombre=f"{dosis}.tif")
            assert m.estado == "ok" and 150.0 < m.region["area_mm2"] < 400.0 and "rango" not in [p.nombre for p in m.pruebas], (dosis, m.region["area_mm2"])


# ===================================================================================================== (10) estructura

NOMBRES_DE_LA_REGLA = ("NIVEL_DE_RECORTE", "FRACCION_DE_RECORTE_MAXIMA", "MARGEN_DEL_RECORTE", "MOTIVO_MESETA_RECORTADA")
EXCLUIDOS = {"tests", ".venv", ".git", ".pytest_cache", "build", "dist", "node_modules", "__pycache__"}


def _produccion():
    fuentes = {}
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in EXCLUIDOS]
        for nombre in archivos:
            if nombre.endswith(".py"):
                ruta = Path(carpeta) / nombre
                fuentes[ruta.relative_to(RAIZ).as_posix()] = ruta.read_text(encoding="utf-8", errors="replace")
    return fuentes


class TestUnaSolaReglaDelRecorte:
    def test_la_regla_y_sus_cuatro_constantes_viven_en_pelicula(self):
        pel = _pel()
        faltan = [n for n in NOMBRES_DE_LA_REGLA + ("meseta_recortada",) if not hasattr(pel, n)]
        assert not faltan, f"`pelicula.py` no define {faltan}: la regla del recorte vive ahi (CD.2)"
        assert callable(pel.meseta_recortada)

    def test_las_constantes_valen_lo_de_OD1c_con_el_mismo_nombre_en_el_motor(self):
        """Los numeros de la decision (OD1c-D1), escritos aqui: pasa antes y despues de CD.2 (el motor las re-exporta con su nombre)."""
        pm = _pm()
        assert (pm.NIVEL_DE_RECORTE, pm.FRACCION_DE_RECORTE_MAXIMA, pm.MARGEN_DEL_RECORTE) == (1.5, 0.01, 10.0)
        assert pm.MOTIVO_MESETA_RECORTADA == "la meseta está recortada por el escáner"

    def test_el_motor_usa_la_misma_regla_y_las_mismas_constantes_que_la_pieza(self):
        pel, pm = _pel(), _pm()
        sin_regla = [n for n in NOMBRES_DE_LA_REGLA + ("meseta_recortada",) if not hasattr(pel, n) or not hasattr(pm, n)]
        assert not sin_regla, f"falta en `pelicula.py` o en `placa_mensual.py`: {sin_regla}"
        for nombre in NOMBRES_DE_LA_REGLA + ("meseta_recortada",):
            assert getattr(pm, nombre) is getattr(pel, nombre), nombre

    def test_placa_mensual_no_define_ninguna_de_las_cuatro_constantes(self):
        arbol = ast.parse((RAIZ / "analisisImagenes" / "placa_mensual.py").read_text(encoding="utf-8"))
        definidas = [t.id for n in arbol.body if isinstance(n, (ast.Assign, ast.AnnAssign)) for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                     if isinstance(t, ast.Name) and t.id in NOMBRES_DE_LA_REGLA]
        assert not definidas, f"`placa_mensual.py` define {definidas}: se re-exportan de `pelicula.py` (una operacion, una definicion)"

    def test_nadie_fuera_de_pelicula_compara_contra_las_constantes_numericas_de_la_regla(self):
        comparan = []
        for ruta, texto in _produccion().items():
            if ruta == "analisisImagenes/pelicula.py":
                continue
            for nodo in ast.walk(ast.parse(texto)):
                if isinstance(nodo, ast.Compare):
                    usados = {n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(nodo) if isinstance(n, ast.Attribute)}
                    if usados & {"NIVEL_DE_RECORTE", "FRACCION_DE_RECORTE_MAXIMA", "MARGEN_DEL_RECORTE"}:
                        comparan.append((ruta, nodo.lineno))
        assert not comparan, f"se compara contra la regla del recorte fuera de `pelicula.meseta_recortada`: {comparan}"

    def test_los_comentarios_de_la_regla_se_mudaron_con_ella_a_pelicula(self):
        """La condicion de REAPERTURA y el LIMITE CONOCIDO de `NIVEL_DE_RECORTE` (OD1b-PROD-02, OD.1c) no se pierden: viajan con la constante."""
        texto = (RAIZ / "analisisImagenes" / "pelicula.py").read_text(encoding="utf-8")
        assert "REAPERTURA" in texto and "LÍMITE CONOCIDO" in texto and "medir la mediana del rojo de una película a 800 UM" in texto


class TestLaApiDeLaPieza:
    def test_la_medida_de_una_pieza_tiene_estos_trece_campos_y_es_inmutable(self):
        pel = _pel()
        campos = [f.name for f in dataclasses.fields(pel.MedidaDePieza)]
        assert campos == ["estado", "capas", "centro", "recortadas", "piezas", "pruebas", "avisos", "region", "procedencia", "parametros", "uniformidad", "escala", "escala_mm"], campos
        m = medir(_pieza().datos)
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.estado = "otro"
        assert isinstance(m.pruebas, tuple) and isinstance(m.avisos, tuple)

    def test_el_registro_de_la_virgen_y_su_firma_no_cambian(self):
        pel = _pel()
        firma = inspect.signature(pel.piso_de_pelicula_virgen)
        assert list(firma.parameters) == ["datos", "P", "nombre_archivo", "fecha_calculo", "orientacion_declarada"]
        assert [firma.parameters[n].default for n in ("nombre_archivo", "fecha_calculo", "orientacion_declarada")] == ["", None, None]
        assert [f.name for f in dataclasses.fields(pel.ReferenciaVirgen)] == ["estado", "capas", "pruebas", "avisos", "region", "procedencia", "parametros", "uniformidad"]

    def test_la_virgen_con_P_sin_escala_sigue_siendo_un_error_de_quien_llama(self):
        with pytest.raises(ValueError, match="escala del procedimiento"):
            _pel().piso_de_pelicula_virgen(b"x", {}, "v.tif", FECHA)


class TestElGeneradorEsIndependienteDelMotor:
    def test_el_generador_no_importa_nada_del_proyecto(self):
        arbol = ast.parse((RAIZ / "tests" / "_piezas_de_calibracion_sinteticas.py").read_text(encoding="utf-8"))
        raices = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                raices |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                raices.add((n.module or "").split(".")[0])
        assert raices <= {"io", "dataclasses", "numpy", "tifffile"}, f"el generador importa {sorted(raices)}: la verdad con que se prueba el motor no puede salir del motor"

    def test_la_misma_semilla_da_los_mismos_bytes_y_otra_semilla_otros(self):
        assert _pieza(semilla=3).datos == _pieza(semilla=3).datos and _pieza(semilla=3).datos != _pieza(semilla=4).datos

    def test_el_generador_escribe_la_resolucion_que_se_le_pide_y_nada_si_se_le_pide_nada(self):
        for declarado, esperado in (("real", 150.0), (96, 96.0), (None, None)):
            with tifffile.TiffFile(io.BytesIO(_pieza(dpi_declarado=declarado).datos)) as tif:
                tags = tif.pages[0].tags
                x = tags.get("XResolution")
                assert (None if x is None or tags["ResolutionUnit"].value != 2 else float(x.value[0]) / float(x.value[1])) == esperado, (declarado, x)

    def test_los_bits_y_el_tamano_son_los_pedidos(self):
        for bits, dtype in ((8, np.uint8), (16, np.uint16)):
            pieza = _pieza(bits=bits)
            arreglo = tifffile.imread(io.BytesIO(pieza.datos))
            assert arreglo.dtype == dtype and arreglo.shape == (pieza.caja.alto, pieza.caja.ancho, 3) == (106, 106, 3)

    def test_la_verdad_nominal_es_la_que_se_pidio(self):
        pieza = _pieza()
        assert pieza.nominal("R") == 150.0 and pieza.nominal("G") == 120.0 and pieza.nominal("B") == 95.0
        assert pieza.nominal("gris") == pytest.approx(0.299 * 150.0 + 0.587 * 120.0 + 0.114 * 95.0)

    def test_el_ruido_y_el_gradiente_son_los_pedidos(self):
        a = _decodificar(_pieza(sigma=SIGMA, semilla=21).datos)
        assert abs(a[..., 0].mean() - 150.0) < 0.1 and abs(a[..., 0].std() - SIGMA) < 0.1
        plana = _decodificar(_pieza(sigma=0.0, pendiente_x=0.6).datos)
        pendiente_por_pixel = np.polyfit(np.arange(plana.shape[1]), plana[53, :, 0], 1)[0]          # el ajuste de minimos cuadrados no se deja engañar por el redondeo a niveles enteros
        assert abs(pendiente_por_pixel * (150.0 / 25.4) - 0.6) < 0.01, "0.6 niveles por mm"
        assert np.ptp(plana[:, 40, 0]) == 0, "sin pendiente en y, cada columna es constante"

    def test_la_caja_de_la_pieza_es_la_que_se_pega(self):
        pieza = _pieza(margen=6.0)
        assert (pieza.caja.x0, pieza.caja.y0) == (gen.pixeles(6.0, 150.0),) * 2 and (pieza.caja.ancho, pieza.caja.alto) == (gen.pixeles(18.0, 150.0),) * 2
        assert pieza.caja.centro == ((pieza.caja.x0 + pieza.caja.x1 - 1) / 2, (pieza.caja.y0 + pieza.caja.y1 - 1) / 2)
