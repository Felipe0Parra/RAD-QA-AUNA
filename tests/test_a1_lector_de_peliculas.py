"""A.1 (PLAN_ANALISIS_PELICULAS_08-10.md): UN SOLO LECTOR de peliculas -- 8 o 16 bits por canal, capas con nombre y el alfa como "sin dato".

CAUSA (R8, H9). Tres lectores distintos: el del analisis viejo (`cv2.imread`, 8 bits), el de la posicion inicial (`IMREAD_COLOR` +
`IMREAD_GRAYSCALE`: un TIFF de 16 bits se reducia a 8, 34567 -> 135; y cualquier pixel transparente se rechazaba) y el del cuaderno. Ninguno leia
16 bits ni trataba el alfa como un dato que falta. Ahora hay `analisisImagenes/pelicula.py::leer_pelicula` y el motor de la posicion inicial lo usa.

LO QUE SE GARANTIZA (a-e del PROTOCOLO del plan), cada cosa con su prueba, contra una verdad que no sale del motor:
  (a) CERO DIFERENCIAS EN 8 BITS: para las 23 imagenes de `ImagenesDeReferencia/PlacasHistoricas` (si la carpeta existe) y las 3 de `tests/datos`,
      los arreglos de `leer_imagen` son, ARREGLO POR ARREGLO, los que entregaba antes de A.1 (`IMREAD_GRAYSCALE` e `IMREAD_COLOR`, uint8, la misma
      resolucion y la misma fecha), y `analizar` da el mismo resultado numero por numero con los clics de la suite, por el motor y por el servicio.
  (b) 16 BITS: un TIFF de 16 bits se lee sin perder precision (valor * 255 / 65535, con decimales); uno hecho de otro de 8 bits x 257 da lo MISMO por capa
      (+-0.01 px) en la placa sintetica y en gris exacto si la escena es neutra; la pagina lo muestra en uint8 (sus niveles de 8 bits redondeados) como muestra la de 8.
      NOTA (medida el 12-10, ronda 1 de la revision, R1-G-02): el +-0.01 px del plan vale SOLO para la placa sintetica. En las peliculas REALES del repo (JPEG y
      TIFF del escaner) el desfase de una capa del gemelo de 16 bits difiere del de 8 bits hasta 0.086 px (0.0036 mm, ocho veces menos que la exactitud del motor,
      0.03 mm). Las TRES capas R, G y B del gemelo son bit a bit las de 8 bits: lo que difiere es el GRIS, que es de donde el motor ubica la linea de referencia
      (el gris de 8 bits es la luma que da el decodificador, un entero redondeado -- en un JPEG, hasta 8.6 niveles de diferencia con el gris calculado del color --;
      el de 16 bits es `cvtColor(BGR2GRAY)` de los tres canales, en flotante). No es un defecto del lector: el gris de 16 bits es el correcto y el mas fiel. Por eso
      la prueba de las peliculas reales (`TestLos16BitsEnPeliculasReales`) fija la cota MEDIDA (0.15 px), no la del plan.
  (c) ALFA: opaco -> todo valido y mismo resultado; transparencia lejos de la mancha -> mide igual; sobre la mancha -> "no medible" con el motivo; nunca
      `ValueError`; el motor, el servicio (`analizar_imagen` y `guardar`) y la pagina. La mascara equivale a poner esos pixeles en blanco puro (oraculo
      independiente del codigo nuevo).
  (d) CAPAS CON NOMBRE: R, G y B conocidos y distintos salen cada uno donde dice (rojo contra un lector que confunda BGR).
  (e) EPSON009 (TIFF RGBA de Paint, 96.012 dpi declarados) igual que hoy.
Y las garantias de estructura: una sola definicion de `clase_resolucion` y de `escala_mm` (ahora en `pelicula.py`, re-exportadas por el motor),
una sola lectura de la resolucion declarada, la version del algoritmo (PI-2), `CAPAS`/`NOMBRE_DE_CAPA`/`CAPA_POR_OMISION` y que ningun PDF lea la capa por omision.

Rojo contra HEAD (d3c34b3): las pruebas del modulo nuevo caen por `ModuleNotFoundError` (no existe `pelicula.py`; el archivo se colecciona porque cada prueba
importa el modulo, no el archivo entero); las que se escriben contra la API de siempre (`leer_imagen`, `analizar`, `svc.analizar_imagen`, la pagina) caen por su
aserción o por la excepcion que HEAD lanza (transparencia, `validos=`, 16 bits reducidos a 8). Las que PASAN en HEAD son la conducta que A.1 conserva (8 bits).
Ver logs/A1/rojo.log (cifras y causas) y a1_mutaciones.py en el anexo (las mutaciones, cada una atrapada por su razon).
Ademas del generador independiente de braqui, la lectura se contrasta con la pelicula MENSUAL sintetica de PF.0 (`alfa='sin_pelicula'`: transparente fuera de la pelicula).

Compuertas de no vacuidad (Trampa 8): cada tabla de casos declara cuantos corrio; las escenas con transparencia afirman primero que la transparencia EXISTE
en lo que se le da al lector.

RONDA 1 DE LA REVISION (12-10, hallazgos R1-G-01 a R1-G-05; ver borradores/A1/obstaculos.md y las mutaciones S4, S5, P7, P8, Q1-Q3 y R1-R3 del anexo):
  G-01 el alfa con 16 bits por el motor, el servicio, `guardar` y la pagina (antes solo habia TIFF de 8 bits con alfa: quitar la mascara en 16 bits sobrevivia);
  G-02 los 16 bits contra los 8 bits en las peliculas REALES, con la cota medida (arriba, la NOTA del punto (b));
  G-03 una mascara delgada (una tira transparente de 1 px junto a la linea) hacia lanzar `TypeError` a `refinar_linea`: el recorte robusto podia rechazar TODAS las filas;
  G-04 el motivo de "no medible" cuando la transparencia deja sin mancha la zona analizada ya no culpa a la linea: dice que la zona tiene zonas transparentes;
  G-05 la pagina de 16 bits pedia 1.4 GB (tres planos en flotante cacheados y ademas un `np.dstack` que los copiaba); ahora un solo arreglo de color.
Las pruebas con peliculas reales SALTAN (HI-0) si `ImagenesDeReferencia/PlacasHistoricas` no existe y FALLAN nombrando la pelicula si existe y falta una de las 23."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import hashlib
import importlib
import inspect
import io
import struct
import tracemalloc
import zlib
from datetime import date
from pathlib import Path

import cv2
import numpy as np
import pytest
import tifffile
from PIL import Image

import _corpus
import _placa_braqui_sintetica as gen
import _placa_mensual_sintetica as gen_mensual
from analisisImagenes import posicion_inicial_braqui as motor
from services import posicion_inicial_braqui as svc
# La BD temporal y la pagina son las de PI.3 y PI.4 (se reutilizan, no se reescriben; precedente: test_pi4 importa de test_pi3).
from test_pi1_motor_posicion_inicial import _bgr, _escena
from test_pi3_servicio_posicion_inicial import S1, SERIE_A, USUARIO, _calibracion, _consulta, bd, plantilla  # noqa: F401
from test_pi4_pagina_posicion_inicial import (CAMBIO, _cargar, _cursor_limpio, _marcar, app, dialogos, fabrica,  # noqa: F401
                                              pagina)

RAIZ = Path(__file__).resolve().parent.parent
DATOS = Path(__file__).resolve().parent / "datos"
SIN_ORIENTACION = cv2.IMREAD_IGNORE_ORIENTATION
MM_POR_PX = 25.4 / 600.0

# Las 23 imagenes de PlacasHistoricas (PR.0 de las peliculas declara 15; las otras 8 se nombran aqui, una por una, porque tres pruebas de PF.0 fijan el
# registro exacto de `_corpus.py` y A.1 es la primera tarea que las usa).
LAS_23 = (
    "braqui_00.jpeg", "braqui_00.JPG", "EPSON001.jpg", "EPSON001.TIF", "EPSON002.JPG", "EPSON003.JPG", "EPSON004.JPG", "EPSON005.JPG", "EPSON006.JPG",
    "EPSON007.JPG", "EPSON008.TIF", "EPSON009.jpeg", "EPSON027.JPG", "EPSON028.JPG", "EPSON029.JPG", "EPSON030.JPG", "EPSON031.JPG", "ML0.JPG",
    "placa_ANOMALA_96dpi_ref10.jpeg", "placa_ref30.jpeg", "placa_ref35.jpeg", "placa_ref40.jpeg", "placa_ref6.jpeg",
)
LAS_3_DEL_REPO = ("braqui_00.jpeg", "EPSON009.jpeg", "EPSON031.JPG")
# Los clics de la suite (test_pi1 / test_pi4) sobre las imagenes que los tienen; el resto se lee pero no se analiza (no hay verdad que comparar).
CLICS_DE_LA_SUITE = {
    "braqui_00.jpeg": {"G1": [(191, 377), (190, 56)], "no_medible": [(191, 120), (190, 20)], "linea_alejada": [(197, 377), (196, 56)],
                       "linea_no_refinada": [(191, 250), (190, 150)]},
    "EPSON009.jpeg": {f"juego{i}": c for i, c in enumerate((
        [(228, 185), (234, 545)], [(229, 190), (233, 425)], [(227, 180), (235, 550)],
        [(230, 200), (232, 420)], [(226, 176), (234, 540)], [(234, 545), (228, 185)]))},
    "EPSON031.JPG": {"G2": [(2511, 3687), (2832, 3686)]},
}
# Resolucion declarada y fecha del escaneo que entregaba el lector de HEAD (d3c34b3) para cada una (constantes del ARCHIVO, no de la libreria):
# salen de logs/A1/oraculo_head.json, capturado ANTES de editar produccion.
HEAD_DPI_Y_FECHA = {
    "braqui_00.jpeg": (600.0, "2026-09-30"), "braqui_00.JPG": (600.0, "2026-09-30"), "EPSON001.jpg": (599.999, None), "EPSON001.TIF": (599.999, None),
    "EPSON002.JPG": (600.0, None), "EPSON003.JPG": (600.0, None), "EPSON004.JPG": (600.0, None), "EPSON005.JPG": (600.0, None),
    "EPSON006.JPG": (600.0, None), "EPSON007.JPG": (600.0, None), "EPSON008.TIF": (599.999, None), "EPSON009.jpeg": (96.012, None),
    "EPSON027.JPG": (600.0, None), "EPSON028.JPG": (600.0, None), "EPSON029.JPG": (600.0, None), "EPSON030.JPG": (600.0, None),
    "EPSON031.JPG": (600.0, "2026-09-30"), "ML0.JPG": (600.0, "2026-10-06"), "placa_ANOMALA_96dpi_ref10.jpeg": (96.0, "2026-02-16"),
    "placa_ref30.jpeg": (300.0, None), "placa_ref35.jpeg": (200.0, None), "placa_ref40.jpeg": (600.0, None), "placa_ref6.jpeg": (599.999, None),
}


def _pel():
    """El modulo nuevo, importado POR PRUEBA: en HEAD (sin `pelicula.py`) el archivo se coleciona y cada prueba cae con su error."""
    return importlib.import_module("analisisImagenes.pelicula")


# ====================================================================================================================== ayudas

def _huella(objeto):
    """Un resultado del motor -> estructura comparable EXACTA: cada arreglo por su sha256, cada flotante en hexadecimal."""
    if isinstance(objeto, np.ndarray):
        return ("nd", tuple(objeto.shape), str(objeto.dtype), hashlib.sha256(np.ascontiguousarray(objeto).tobytes()).hexdigest())
    if isinstance(objeto, (np.floating, float)):
        return ("f", float(objeto).hex())
    if isinstance(objeto, (np.bool_, bool)):
        return bool(objeto)
    if isinstance(objeto, (np.integer, int)):
        return int(objeto)
    if isinstance(objeto, dict):
        return {str(k): _huella(v) for k, v in objeto.items()}
    if isinstance(objeto, (list, tuple)):
        return [_huella(v) for v in objeto]
    return objeto


def _sin_la_version(resultado):
    h = _huella(resultado)
    h.pop("version")
    return h


# Los textos con que el motor dice que lo transparente esta en la zona analizada (R1-G-03 y R1-G-04). Escritos aqui, no importados: una prueba que importara la
# constante del motor no veria que alguien la cambiara.
LINEA_TAPA = "no medible: la linea tapa el borde de la meseta"
CORTADA = "no medible: la mancha esta cortada por el borde de la pelicula"
NOTA_TRANSPARENCIA = "; la zona analizada tiene zonas transparentes"
SIN_FILAS_POR_TRANSPARENCIA = "no medible: no quedan filas con la mancha a la vista" + NOTA_TRANSPARENCIA
LINEA_NO_REFINADA = "no se pudo refinar la linea: se usan los clics"


def _huella_como_el_blanqueo(resultado):
    """La huella de un analisis CON MASCARA sin lo unico que puede diferir de poner esos pixeles en blanco puro: las dos notas con que el motor dice que la zona
    analizada tiene zonas transparentes (el motivo "no quedan filas con la mancha a la vista" en lugar de "la linea tapa el borde de la meseta", y la nota al final del
    mensaje de una linea que no se pudo ubicar). Todo lo demas -- las ventanas, los perfiles, los numeros -- debe ser IDENTICO, bit a bit."""
    h = _huella(resultado)
    for perfil in h["perfiles"].values():
        if perfil["estado"] == SIN_FILAS_POR_TRANSPARENCIA:
            perfil["estado"] = LINEA_TAPA
    if h["mensaje_linea"].endswith(NOTA_TRANSPARENCIA):
        h["mensaje_linea"] = h["mensaje_linea"][:-len(NOTA_TRANSPARENCIA)]
    return h


def _arreglos_como_en_head(datos):
    """Lo que entregaba `leer_imagen` antes de A.1 (HEAD d3c34b3): `IMREAD_GRAYSCALE` e `IMREAD_COLOR` sin orientacion, uint8."""
    arreglo = np.frombuffer(datos, np.uint8)
    return (cv2.imdecode(arreglo, cv2.IMREAD_GRAYSCALE | SIN_ORIENTACION), cv2.imdecode(arreglo, cv2.IMREAD_COLOR | SIN_ORIENTACION))


def _niveles(plano, bits):
    """Verdad independiente de los niveles de 8 bits: valor * 255 / maximo del tipo, en float64 y luego float32."""
    maximo = 255.0 if bits == 8 else 65535.0
    return (plano.astype(np.float64) * 255.0 / maximo).astype(np.float32)


def _tiff(datos, alfa=False, **etiquetas):
    buffer = io.BytesIO()
    foto = "minisblack" if datos.ndim == 2 else "rgb"
    extra = {"extrasamples": ["unassalpha"]} if alfa else {}
    tifffile.imwrite(buffer, datos, photometric=foto, resolution=(600, 600), resolutionunit="INCH", **extra, **etiquetas)
    return buffer.getvalue()


def _codificar(formato, bits, rgb, alfa=None, **etiquetas):
    """RGB (alto, ancho, 3) del tipo de `bits` (y, si hay, su alfa (alto, ancho)) -> bytes de un TIFF o un PNG."""
    if formato == "tiff":
        return _tiff(rgb if alfa is None else np.dstack([rgb, alfa]), alfa=alfa is not None, **etiquetas)
    if bits == 8:
        buffer = io.BytesIO()
        Image.fromarray(rgb if alfa is None else np.dstack([rgb, alfa])).save(buffer, "PNG", dpi=(600, 600))
        return buffer.getvalue()
    bgr = rgb[:, :, ::-1]
    return cv2.imencode(".png", np.ascontiguousarray(bgr if alfa is None else np.dstack([bgr, alfa])))[1].tobytes()


def _planos(bits, forma=(24, 40), semilla=0):
    """RGB aleatorio con canales INDEPENDIENTES (R, G y B distintos en cada pixel) y los dos extremos del tipo presentes."""
    tipo, maximo = (np.uint8, 255) if bits == 8 else (np.uint16, 65535)
    rgb = np.random.default_rng(semilla).integers(0, maximo + 1, forma + (3,), dtype=tipo)
    rgb[0, 0] = 0
    rgb[0, 1] = maximo
    return rgb


def _alfa(bits, forma=(24, 40)):
    """Alfa conocido: opaco salvo un bloque de 5 x 5 transparente (25 pixeles) y UN pixel casi opaco (maximo - 1): 26 no validos."""
    maximo = 255 if bits == 8 else 65535
    alfa = np.full(forma, maximo, np.uint8 if bits == 8 else np.uint16)
    alfa[2:7, 3:8] = 0
    alfa[-1, -1] = maximo - 1
    return alfa


# ====================================================================================================================== §1 constantes

class TestLasCapasTienenUnNombre:
    def test_capas_nombre_y_capa_por_omision_se_definen_una_vez(self):
        p = _pel()
        assert p.CAPAS == ("R", "G", "B")
        assert p.NOMBRE_DE_CAPA == {"R": "rojo", "G": "verde", "B": "azul"} and set(p.NOMBRE_DE_CAPA) == set(p.CAPAS)
        assert p.CAPA_POR_OMISION == "G" and p.CAPA_POR_OMISION in p.CAPAS

    def test_los_nombres_viejos_de_la_constante_ya_no_existen_en_produccion(self):
        """`CAPA_REPORTADA` y `CAPA_DEL_PDF` se llamaron asi en dos ajustes del plan (09 y 11-10); la constante es solo `CAPA_POR_OMISION`. Por AST: el comentario
        historico de `pelicula.py` puede nombrarlas, ningun codigo."""
        viejos = {"CAPA_REPORTADA", "CAPA_DEL_PDF"}
        vivos, leidos = [], 0
        for ruta in sorted(RAIZ.rglob("*.py")):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in {".venv", "build", "dist", "tests", "__pycache__", ".git"}:
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            leidos += 1
            for n in ast.walk(arbol):
                nombre = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else n.name if isinstance(n, ast.alias) else None
                if nombre in viejos:
                    vivos.append((str(ruta.relative_to(RAIZ)), nombre))
        assert leidos >= 100, "compuerta: el censo lee el arbol de produccion"
        assert not vivos, vivos

    def test_ningun_pdf_ni_modelo_lee_la_capa_por_omision(self):
        """Cada PDF imprime la capa que GUARDO su registro, nunca la constante con que arrancan los menus (B.6 y F.1 dependen de esto)."""
        archivos = sorted((RAIZ / "models").rglob("*.py"))
        assert len(archivos) >= 10, "compuerta: el censo encuentra los modelos y los PDF"
        assert [str(a.relative_to(RAIZ)) for a in archivos if "CAPA_POR_OMISION" in a.read_text(encoding="utf-8", errors="replace")] == []


# ====================================================================================================================== §2 capas con nombre (d)

FORMATOS = [("png", 8, False), ("png", 8, True), ("tiff", 8, False), ("tiff", 8, True),
            ("tiff", 16, False), ("tiff", 16, True), ("png", 16, False), ("png", 16, True)]


def _id_formato(caso):
    formato, bits, alfa = caso
    return f"{formato}{bits}{'_alfa' if alfa else ''}"


class TestCapasConNombre:
    @pytest.mark.parametrize("caso", FORMATOS, ids=_id_formato)
    def test_d_cada_capa_sale_donde_dice_con_canales_distintos_en_cada_pixel(self, caso):
        """R, G y B independientes pixel a pixel: cualquier permutacion de canales (BGR confundido con RGB) o de ejes cae."""
        formato, bits, con_alfa = caso
        rgb = _planos(bits)
        pel = _pel().leer_pelicula(_codificar(formato, bits, rgb, _alfa(bits) if con_alfa else None))
        assert pel.bits == bits
        for capa, indice in (("R", 0), ("G", 1), ("B", 2)):
            obtenida = getattr(pel, capa)
            assert obtenida.dtype == np.float32 and obtenida.shape == rgb.shape[:2], capa
            esperada = _niveles(rgb[:, :, indice], bits)
            validos = pel.validos                      # bajo lo transparente de un TIFF de 8 bits libtiff "asocia" el alfa: el color ahi no significa nada
            assert np.allclose(obtenida[validos], esperada[validos], rtol=0, atol=3e-5), (capa, float(np.abs(obtenida - esperada)[validos].max()))
            if bits == 8:
                assert np.array_equal(obtenida[validos], rgb[:, :, indice].astype(np.float32)[validos]), f"en 8 bits la capa {capa} es el valor, sin tocar"
        if bits == 16:                                 # el gris de 16 bits (con alfa o sin el: BGR2GRAY o BGRA2GRAY) es la suma ponderada de los tres canales de 16 bits
            ponderado = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) * 255.0 / 65535.0
            assert float(np.abs(pel.gris - ponderado)[pel.validos].max()) < 0.02, "el gris de 16 bits no es 0.299 R + 0.587 G + 0.114 B"

    @pytest.mark.parametrize("caso", FORMATOS, ids=_id_formato)
    def test_d_rojo_verde_y_azul_conocidos_y_distintos(self, caso):
        """La prueba del plan: R = 200, G = 100, B = 50 (y su equivalente de 16 bits, x 257) en toda la imagen."""
        formato, bits, con_alfa = caso
        k = 1 if bits == 8 else 257
        rgb = np.empty((20, 30, 3), np.uint8 if bits == 8 else np.uint16)
        rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2] = 200 * k, 100 * k, 50 * k
        pel = _pel().leer_pelicula(_codificar(formato, bits, rgb, _alfa(bits, (20, 30)) if con_alfa else None))
        v = pel.validos                           # bajo lo transparente de un TIFF de 8 bits libtiff "asocia" el alfa y el color ahi no significa nada
        assert v.sum() > 0 and (float(pel.R[v].min()), float(pel.R[v].max())) == (200.0, 200.0), "el rojo no es 200: canales cruzados"
        assert (float(pel.G[v].min()), float(pel.G[v].max())) == (100.0, 100.0)
        assert (float(pel.B[v].min()), float(pel.B[v].max())) == (50.0, 50.0)

    @pytest.mark.parametrize("bits", [8, 16])
    def test_una_imagen_en_grises_da_la_misma_capa_en_las_tres(self, bits):
        tipo, maximo = (np.uint8, 255) if bits == 8 else (np.uint16, 65535)
        gris = np.random.default_rng(3).integers(0, maximo + 1, (24, 40), dtype=tipo)
        pel = _pel().leer_pelicula(_tiff(gris))
        assert pel.bits == bits and pel.formato == "TIFF"
        for capa in ("R", "G", "B", "gris"):
            assert np.allclose(getattr(pel, capa), _niveles(gris, bits), rtol=0, atol=3e-5), capa

    def test_las_capas_son_arreglos_aparte_de_la_imagen_que_se_entrego(self):
        """`R` y compañia son flotantes del tamaño de la imagen, no vistas de un solo arreglo compartido que alguien pueda estropear."""
        pel = _pel().leer_pelicula(_codificar("tiff", 8, _planos(8)))
        for capa in ("R", "G", "B", "gris"):
            assert getattr(pel, capa) is getattr(pel, capa), "la capa se calcula una vez"
        assert pel.R is not pel.G and not np.shares_memory(pel.R, pel.G)


# ====================================================================================================================== §3 los 16 bits (b)

class TestDieciseisBits:
    def test_b_se_lee_sin_perder_precision_valor_por_255_entre_65535(self):
        """Valores que NO son multiplos de 257: en 8 bits se perderian (el 16 -> 8 de OpenCV): aqui conservan sus decimales."""
        rgb = np.empty((6, 8, 3), np.uint16)
        rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2] = 12345, 34567, 65535
        rgb[0, 0] = (0, 1, 256)
        pel = _pel().leer_pelicula(_tiff(rgb))
        assert pel.bits == 16
        assert float(pel.R[3, 3]) == pytest.approx(12345 * 255 / 65535, abs=1e-5) and float(pel.R[3, 3]) != round(float(pel.R[3, 3]))
        assert float(pel.G[3, 3]) == pytest.approx(34567 * 255 / 65535, abs=1e-5)
        assert float(pel.B[3, 3]) == 255.0, "65535 es el maximo: 255.0 exacto (dividir entre 256 daria 255.996)"
        assert (float(pel.R[0, 0]), float(pel.G[0, 0])) == (0.0, pytest.approx(1 * 255 / 65535, abs=1e-6))
        assert float(pel.B[0, 0]) == pytest.approx(256 * 255 / 65535, abs=1e-5) and float(pel.B[0, 0]) < 1.0, "256 no es 1 nivel de 8 bits: es 0.996"

    def test_b_257_es_un_nivel_de_8_bits_exacto(self):
        rgb = np.random.default_rng(1).integers(0, 256, (10, 12, 3), dtype=np.uint16) * 257
        pel = _pel().leer_pelicula(_tiff(rgb))
        for capa, i in (("R", 0), ("G", 1), ("B", 2)):
            assert np.array_equal(getattr(pel, capa), (rgb[:, :, i] // 257).astype(np.float32)), capa

    def test_b_el_gris_de_16_bits_es_el_gris_de_los_tres_canales_de_16_bits(self):
        """`gris` = cvtColor(BGR2GRAY) del de 16 bits (0.299 R + 0.587 G + 0.114 B), en niveles de 8 bits; contra la formula, escrita aqui."""
        rgb = _planos(16, (30, 40), semilla=5)
        pel = _pel().leer_pelicula(_tiff(rgb))
        ponderado = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) * 255.0 / 65535.0
        assert pel.gris.dtype == np.float32 and pel.gris.shape == rgb.shape[:2]
        assert float(np.abs(pel.gris - ponderado).max()) < 0.02, float(np.abs(pel.gris - ponderado).max())
        # y no es ninguna de las simplificaciones: ni el verde solo, ni el promedio
        assert float(np.abs(pel.gris - pel.G).max()) > 5 and float(np.abs(pel.gris - (pel.R + pel.G + pel.B) / 3).max()) > 1

    def test_b_un_tiff_de_16_bits_hecho_de_uno_de_8_x_257_da_las_mismas_capas_que_el_de_8(self):
        rgb8 = _planos(8, (30, 40), semilla=2)
        pel8 = _pel().leer_pelicula(_tiff(rgb8))
        pel16 = _pel().leer_pelicula(_tiff(rgb8.astype(np.uint16) * 257))
        assert (pel8.bits, pel16.bits) == (8, 16)
        for capa in ("R", "G", "B"):
            assert np.array_equal(getattr(pel16, capa), getattr(pel8, capa)), capa
        assert float(np.abs(pel16.gris - pel8.gris).max()) <= 0.5 + 1e-3, "el gris de 8 bits es un entero redondeado: difiere hasta medio nivel"

    def test_los_16_bits_no_se_leen_como_8_el_error_de_hoy_es_visible_en_el_lector_de_la_posicion_inicial(self):
        """Antes de A.1 `leer_imagen` reducia el TIFF de 16 bits a uint8: 34567 -> 135. Ahora devuelve flotantes en niveles de 8 bits."""
        rgb = np.full((20, 30, 3), 34567, np.uint16)
        gris, color, dpi, fecha = motor.leer_imagen(_tiff(rgb))
        assert gris.dtype == np.float32 and color.dtype == np.float32 and gris.shape == (20, 30) and color.shape == (20, 30, 3)
        assert float(color[5, 5, 0]) == pytest.approx(34567 * 255 / 65535, abs=1e-5) and float(color[5, 5, 0]) != 135.0
        assert dpi == 600.0 and fecha is None

    @pytest.mark.parametrize("bits", [8, 16])
    def test_leer_imagen_devuelve_el_color_en_el_orden_de_opencv_BGR(self, bits):
        """El motor indexa `color[:, :, 0]` como B, 1 como G y 2 como R: tambien en 16 bits."""
        k = 1 if bits == 8 else 257
        rgb = np.empty((12, 14, 3), np.uint8 if bits == 8 else np.uint16)
        rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2] = 200 * k, 100 * k, 50 * k
        gris, color, _, _ = motor.leer_imagen(_tiff(rgb))
        assert (float(color[0, 0, 0]), float(color[0, 0, 1]), float(color[0, 0, 2])) == (50.0, 100.0, 200.0), "B, G, R"
        assert color.shape == (12, 14, 3) and gris.shape == (12, 14)

    @pytest.mark.parametrize("bits", [8, 16])
    def test_leer_imagen_entrega_el_gris_y_las_tres_capas_de_la_pelicula(self, bits):
        """`leer_imagen` = `leer_pelicula` + `en_bgr`: con canales independientes en cada pixel, su gris es el gris de la pelicula y su color es (B, G, R), sin
        cruces ni copias de otra capa (en 8 bits los valores sin tocar; en 16, los niveles de 8 bits con decimales)."""
        datos = _codificar("tiff", bits, _planos(bits, (30, 40), semilla=7))
        pel = _pel().leer_pelicula(datos)
        gris, color, _, _ = motor.leer_imagen(datos)
        assert np.array_equal(gris, pel.gris) and gris.shape == (30, 40) and color.shape == (30, 40, 3)
        for indice, capa in ((0, "B"), (1, "G"), (2, "R")):
            assert np.array_equal(color[:, :, indice], getattr(pel, capa)), capa
        assert float(np.abs(pel.R - pel.B).max()) > 10 and float(np.abs(pel.G - pel.B).max()) > 10, "compuerta: las capas son distintas"

    def test_un_flotante_de_32_bits_no_se_lee_y_lo_dice(self):
        flotante = np.random.default_rng(0).random((10, 12, 3)).astype(np.float32)
        buffer = io.BytesIO()
        tifffile.imwrite(buffer, flotante, photometric="rgb")
        with pytest.raises(ValueError, match="8 o 16 bits"):
            _pel().leer_pelicula(buffer.getvalue())

    def test_bytes_que_no_son_una_imagen_o_vacios_dicen_que_no_se_reconoce_el_formato(self):
        for basura in (b"esto no es una imagen", b""):
            with pytest.raises(ValueError, match="No se reconoce el formato"):
                _pel().leer_pelicula(basura)

    def test_la_resolucion_la_fecha_y_el_formato_se_leen_con_pillow_tambien_en_16_bits(self):
        """Pillow abre un TIFF RGBA de 16 bits como 8 bits: lo declarado se lee con Pillow, los PIXELES nunca (cv2.IMREAD_UNCHANGED)."""
        rgb = _planos(16)
        pel = _pel().leer_pelicula(_tiff(rgb, datetime="2026:09:30 10:00:00"))
        assert (pel.bits, pel.dpi, pel.fecha_escaneo, pel.formato) == (16, 600.0, date(2026, 9, 30), "TIFF")
        sin_unidad = io.BytesIO()
        tifffile.imwrite(sin_unidad, rgb, photometric="rgb")               # tifffile escribe una resolucion SIN UNIDAD (1, sin unidad): no es una resolucion declarada
        pel = _pel().leer_pelicula(sin_unidad.getvalue())
        assert (pel.dpi, pel.fecha_escaneo) == (None, None)
        sin_etiquetas = io.BytesIO()
        Image.fromarray(_planos(8)).save(sin_etiquetas, "TIFF")           # un TIFF SIN las etiquetas de resolucion: Pillow RELLENA info['dpi'] = (1, 1)
        assert Image.open(io.BytesIO(sin_etiquetas.getvalue())).info.get("dpi") == (1, 1), "compuerta: Pillow rellena 1 dpi"
        pel = _pel().leer_pelicula(sin_etiquetas.getvalue())
        assert (pel.dpi, pel.bits) == (None, 8), "lo que Pillow rellena (1 dpi) no es lo que el archivo declara"
        assert _pel().leer_pelicula(_codificar("png", 16, rgb)).formato == "PNG"
        # Pillow RELLENA 72 dpi en un JPEG con bloque EXIF y sin resolucion (JpegImagePlugin): lo que el archivo declara es NADA
        exif = Image.Exif()
        exif[306] = "2026:02:10 08:00:00"
        buffer = io.BytesIO()
        Image.new("L", (64, 64), 128).save(buffer, "JPEG", exif=exif)
        assert Image.open(io.BytesIO(buffer.getvalue())).info.get("dpi") == (72, 72), "compuerta: Pillow rellena 72 dpi"
        pel = _pel().leer_pelicula(buffer.getvalue())
        assert (pel.dpi, pel.fecha_escaneo, pel.formato) == (None, date(2026, 2, 10), "JPEG")

    def test_la_orientacion_exif_se_ignora_en_cada_lectura(self):
        """Un JPEG con orientacion 6 (girar 90 grados) se lee como esta guardado: 40 filas x 80 columnas, en el gris y en cada capa (DD3)."""
        exif = Image.Exif()
        exif[274] = 6
        buffer = io.BytesIO()
        Image.fromarray(np.random.default_rng(0).integers(0, 256, (40, 80, 3), dtype=np.uint8)).save(buffer, "JPEG", exif=exif)
        pel = _pel().leer_pelicula(buffer.getvalue())
        assert pel.gris.shape == (40, 80), "el gris viene de IMREAD_GRAYSCALE"
        for capa in ("R", "G", "B"):
            assert getattr(pel, capa).shape == (40, 80), capa



class TestElLectorNoDerrocha:
    def test_la_pagina_de_8_bits_no_construye_planos_en_flotante_que_nadie_pidio(self):
        """EPSON031 (6600 x 5100) ocupa unos 135 MB leida (el pico medido el 12-10: 136 MB, igual que antes de A.1); cuatro planos float32 serian 540 MB mas: los
        flotantes se construyen solo si se piden."""
        datos = (DATOS / "EPSON031.JPG").read_bytes()
        leer = _pel().leer_pelicula
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            pel = leer(datos)
            pico = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert pel.bits == 8 and pel.gris.shape == (6600, 5100)
        assert pico < 400e6, f"leer la pagina completa pidio {pico / 1e6:.0f} MB"

    def test_la_pagina_de_16_bits_no_duplica_los_planos_en_flotante(self, gemelos_de_16_bits):
        """R1-G-05. La pagina completa de 16 bits (6600 x 5100 x 3 x 2 B = 202 MB) pasaba por el lector con un pico de 1.4 GB: `en_bgr()` construia el gris y los tres
        planos B, G, R en flotante (cacheados en la `Pelicula`: 405 MB) y ademas un `np.dstack` que los copiaba otra vez (otros 405 MB). Ahora el color sale en UN solo
        arreglo de 405 MB desde el nativo. Se mide con tracemalloc (cada arreglo de numpy y de OpenCV): determinista, no depende de como devuelva la memoria el sistema."""
        datos = gemelos_de_16_bits["EPSON031.JPG"].read_bytes()
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            gris, color, dpi, _ = motor.leer_imagen(datos)
            pico = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert gris.dtype == np.float32 and gris.shape == (6600, 5100) and color.dtype == np.float32 and color.shape == (6600, 5100, 3) and dpi == 600.0
        assert pico < 900e6, f"leer la pagina completa de 16 bits pidio {pico / 1e6:.0f} MB (el color en flotante es de 405 MB; antes de la correccion, 1214 MB)"

    def test_en_bgr_de_16_bits_no_construye_los_planos_aparte_y_su_color_es_un_solo_arreglo(self):
        rgb = _planos(16, (30, 40), semilla=11)
        pel = _pel().leer_pelicula(_tiff(rgb))
        gris, color = pel.en_bgr()
        assert not ({"R", "G", "B"} & set(vars(pel))), "en_bgr construyo (y cacheo) los planos R, G y B que nadie pidio"
        assert color.base is None and color.flags["C_CONTIGUOUS"] and color.dtype == np.float32 and color.shape == (30, 40, 3), "el color es UN arreglo propio, no una pila de planos"
        for indice, capa in ((0, "B"), (1, "G"), (2, "R")):
            assert np.array_equal(color[:, :, indice], getattr(pel, capa)), capa            # al pedirlos despues, los planos son los mismos valores, bit a bit

    def test_en_bgr_de_una_imagen_de_16_bits_en_grises_repite_el_gris_en_las_tres_capas(self):
        gris16 = np.random.default_rng(4).integers(0, 65536, (20, 30), dtype=np.uint16)
        gris, color = _pel().leer_pelicula(_tiff(gris16)).en_bgr()
        assert color.shape == (20, 30, 3) and color.dtype == np.float32
        for indice in range(3):
            assert np.array_equal(color[:, :, indice], gris)


@pytest.fixture(scope="module")
def gemelos_de_16_bits(tmp_path_factory):
    """El gemelo de 16 bits de cada pelicula real del repo: el MISMO color (`IMREAD_COLOR`) x 257 como TIFF RGB de 16 bits, escrito a disco ({nombre: ruta}). El de la pagina
    completa pesa 202 MB: se lee solo cuando una prueba lo pide."""
    carpeta = tmp_path_factory.mktemp("gemelos16")
    rutas = {}
    for nombre in sorted(CLICS_DE_LA_SUITE):
        bgr = cv2.imdecode(np.fromfile(str(DATOS / nombre), np.uint8), cv2.IMREAD_COLOR | SIN_ORIENTACION)
        rutas[nombre] = carpeta / (Path(nombre).stem + "_x257.tif")
        tifffile.imwrite(str(rutas[nombre]), bgr[:, :, ::-1].astype(np.uint16) * 257, photometric="rgb", resolution=(600, 600), resolutionunit="INCH")
        del bgr
    return rutas


class TestLos16BitsEnPeliculasReales:
    """R1-G-02: la promesa del plan (un TIFF de 16 bits hecho de uno de 8 x 257 da el MISMO desfase, +-0.01 px) solo se cumple en la placa sintetica. En las peliculas
    reales del repo el desfase de CADA CAPA del gemelo de 16 bits difiere del de 8 bits hasta 0.086 px (0.0036 mm) porque el motor ubica la linea de referencia sobre el
    GRIS, y el gris de 8 bits (el que da el decodificador) no es el de 16 bits (`cvtColor(BGR2GRAY)` del color), aunque R, G y B del gemelo sean bit a bit los mismos.
    Esta prueba ve lo que la del plan no veia: fija la cota MEDIDA sobre las tres peliculas reales con los clics de la suite."""

    COTA_PX = 0.15           # medido: 0.0861 (R, EPSON009 juego 4); 0.15 px son 0.0064 mm, la quinta parte de la exactitud del motor (0.03 mm)
    PISO_DE_COMPARACIONES = {"braqui_00.jpeg": 9, "EPSON009.jpeg": 24, "EPSON031.JPG": 3}      # capas medibles por pelicula (lo medido el 12-10): que no pase en vacio

    @pytest.mark.parametrize("nombre", sorted(CLICS_DE_LA_SUITE))
    def test_b_las_capas_del_gemelo_son_las_de_8_bits_y_el_desfase_de_cada_capa_difiere_menos_de_la_cota(self, gemelos_de_16_bits, nombre):
        d8 = (DATOS / nombre).read_bytes()
        d16 = gemelos_de_16_bits[nombre].read_bytes()
        gris8, color8, _, _ = motor.leer_imagen(d8)
        gris16, color16, _, _ = motor.leer_imagen(d16)
        assert gris8.dtype == np.uint8 and gris16.dtype == np.float32
        for indice in range(3):                                   # la CAUSA, comprobada: las tres capas de color no difieren en un solo valor
            assert np.array_equal(color8[:, :, indice].astype(np.float32), color16[:, :, indice]), f"{nombre}: el color {indice} del gemelo no es el de 8 bits"
        assert float(np.abs(gris8.astype(np.float32) - gris16).max()) > 0.4, "compuerta: el GRIS si difiere (es lo que mueve la linea de referencia)"
        comparadas = 0
        for etiqueta, clics in CLICS_DE_LA_SUITE[nombre].items():
            r8 = svc.analizar_imagen(d8, clics)
            r16 = svc.analizar_imagen(d16, clics)
            assert r8["mensaje_linea"] == r16["mensaje_linea"], (nombre, etiqueta)
            for capa in ("gris", "R", "G", "B"):
                a, b = r8["perfiles"][capa], r16["perfiles"][capa]
                assert a["estado"] == b["estado"], (nombre, etiqueta, capa)
                if a["estado"] == "ok":
                    comparadas += 1
                    assert abs(a["desfase_px"] - b["desfase_px"]) <= self.COTA_PX, (nombre, etiqueta, capa, a["desfase_px"], b["desfase_px"])
        assert comparadas >= self.PISO_DE_COMPARACIONES[nombre], (nombre, comparadas)

    def test_b_la_cota_medida_esta_muy_por_debajo_de_la_exactitud_del_motor(self):
        """0.15 px son 0.0064 mm: la quinta parte de la exactitud del motor contra el generador independiente (0.03 mm). No es una cota que esconda un error."""
        assert self.COTA_PX * MM_POR_PX < 0.03 / 4


# ====================================================================================================================== §4 el alfa (c)

def _con_paleta_transparente():
    """PNG de paleta con el indice 3 transparente (tRNS): un bloque de 5 x 5 pixeles con ese indice."""
    indices = np.full((24, 40), 5, np.uint8)
    indices[2:7, 3:8] = 3
    imagen = Image.fromarray(indices).convert("P")
    buffer = io.BytesIO()
    imagen.save(buffer, "PNG", transparency=3)
    return buffer.getvalue(), 25


def _gris_con_clave_de_color():
    """PNG en grises con una CLAVE DE COLOR transparente (tRNS = 7): OpenCV no la entrega como alfa; Pillow si. Un bloque de 5 x 5 valdra 7."""
    gris = np.random.default_rng(0).integers(100, 200, (24, 40), dtype=np.uint8)
    gris[2:7, 3:8] = 7
    buffer = io.BytesIO()
    Image.fromarray(gris).save(buffer, "PNG", transparency=7)
    return buffer.getvalue(), 25


def _gris_con_alfa():
    gris = np.random.default_rng(1).integers(0, 256, (24, 40), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(np.dstack([gris, _alfa(8)])).save(buffer, "PNG")
    return buffer.getvalue(), 26


class TestElAlfaEsSinDato:
    @pytest.mark.parametrize("caso", [c for c in FORMATOS if c[2]], ids=_id_formato)
    def test_c_las_transparentes_se_cuentan_y_validos_es_alfa_igual_al_maximo(self, caso):
        formato, bits, _ = caso
        alfa = _alfa(bits)
        rgb = _planos(bits)
        pel = _pel().leer_pelicula(_codificar(formato, bits, rgb, alfa))
        maximo = 255 if bits == 8 else 65535
        assert int((alfa != maximo).sum()) == 26, "compuerta: la escena TIENE transparencia (25 pixeles a 0 y uno a maximo - 1)"
        assert pel.transparentes == 26
        assert pel.validos.dtype == bool and pel.validos.shape == rgb.shape[:2]
        assert np.array_equal(pel.validos, alfa == maximo), "un alfa de maximo - 1 NO es opaco"
        # donde HAY dato el color es el guardado (bajo lo transparente no significa nada: libtiff "asocia" el alfa en un TIFF de 8 bits y lo deja a 0)
        assert np.array_equal(pel.R[pel.validos], _niveles(rgb[:, :, 0], bits)[pel.validos])

    @pytest.mark.parametrize("caso", [c for c in FORMATOS if c[2]], ids=_id_formato)
    def test_c_un_alfa_opaco_en_todo_es_todo_valido(self, caso):
        formato, bits, _ = caso
        maximo = 255 if bits == 8 else 65535
        alfa = np.full((24, 40), maximo, np.uint8 if bits == 8 else np.uint16)
        pel = _pel().leer_pelicula(_codificar(formato, bits, _planos(bits), alfa))
        assert pel.transparentes == 0 and pel.validos.all() and pel.validos.shape == (24, 40)

    @pytest.mark.parametrize("caso", [c for c in FORMATOS if not c[2]], ids=_id_formato)
    def test_c_sin_alfa_todo_es_valido(self, caso):
        formato, bits, _ = caso
        pel = _pel().leer_pelicula(_codificar(formato, bits, _planos(bits)))
        assert pel.transparentes == 0 and pel.validos.all() and pel.validos.shape == (24, 40) and pel.validos.dtype == bool

    @pytest.mark.parametrize("construir", [_con_paleta_transparente, _gris_con_clave_de_color, _gris_con_alfa], ids=["paleta_tRNS", "gris_clave_tRNS", "gris_LA"])
    def test_c_las_otras_formas_de_transparencia_de_8_bits_tambien_cuentan(self, construir):
        """Paleta con tRNS, grises con clave de color (que OpenCV no entrega como alfa) y grises con alfa: lo que HEAD rechazaba por `_hay_transparencia`."""
        datos, esperadas = construir()
        pel = _pel().leer_pelicula(datos)
        assert pel.bits == 8 and pel.transparentes == esperadas and int((~pel.validos).sum()) == esperadas

    def test_c_una_transparencia_de_16_bits_que_no_se_puede_leer_se_rechaza_en_vez_de_tomarse_por_pelicula(self):
        """Un PNG de grises de 16 bits con una clave de color (tRNS): Pillow dice que hay transparencia y OpenCV no entrega alfa; con 16 bits Pillow no puede dar el
        alfa de 8 bits que serviria en 8: lo unico honesto es negarse (lo transparente nunca se toma por pelicula)."""
        gris = np.random.default_rng(2).integers(1000, 60000, (24, 40), dtype=np.uint16)
        png = cv2.imencode(".png", gris)[1].tobytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        # insertar el trozo tRNS (clave de color de grises: un valor de 16 bits) justo despues del IHDR (8 de firma + 4 de largo + 4 de tipo + 13 de datos + 4 de CRC)
        cuerpo = struct.pack(">H", int(gris[0, 0]))
        trozo = struct.pack(">I", len(cuerpo)) + b"tRNS" + cuerpo + struct.pack(">I", zlib.crc32(b"tRNS" + cuerpo))
        con_clave = png[:33] + trozo + png[33:]
        assert "transparency" in Image.open(io.BytesIO(con_clave)).info, "compuerta: Pillow ve la transparencia"
        assert cv2.imdecode(np.frombuffer(con_clave, np.uint8), cv2.IMREAD_UNCHANGED).shape == (24, 40), "compuerta: OpenCV no la entrega como alfa"
        with pytest.raises(ValueError, match="transparencia"):
            _pel().leer_pelicula(con_clave)

    def test_c_nunca_se_lanza_valueerror_por_transparencia_ni_en_el_lector_de_la_posicion_inicial(self):
        """HEAD: `ValueError("La imagen tiene zonas transparentes ...")`. Ahora se lee, y la mascara viaja aparte."""
        rgba = Image.new("RGBA", (64, 64), (128, 128, 128, 255))
        rgba.putpixel((3, 3), (0, 0, 0, 0))
        buffer = io.BytesIO()
        rgba.save(buffer, "PNG")
        gris, color, dpi, fecha = motor.leer_imagen(buffer.getvalue())
        assert gris.shape == (64, 64) and color.shape == (64, 64, 3)
        assert _pel().leer_pelicula(buffer.getvalue()).transparentes == 1


# ---------------------------------------------------------------------------------------------------------------- la pelicula mensual sintetica (PF.0)

PELICULAS_MENSUALES_SINTETICAS = [("tiff", 16, "sin_pelicula"), ("tiff", 16, True), ("tiff", 8, "sin_pelicula"), ("tiff", 8, True), ("png", 8, "sin_pelicula"),
                                  ("png", 8, False), ("jpeg", 8, False)]


class TestConLaPeliculaMensualSinteticaDePF0:
    """El generador de PF.0 (independiente del motor y de este lector) escribe sus propios TIFF, PNG y JPEG: su arreglo BGR(A) es la verdad de lo que el lector debe entregar.
    `alfa = 'sin_pelicula'` es el caso real del mensual: transparente FUERA de la pelicula (alfa 0 alrededor de ella), opaco dentro."""

    @pytest.mark.parametrize("formato,bits,alfa", PELICULAS_MENSUALES_SINTETICAS, ids=[f"{f}{b}_{a}" for f, b, a in PELICULAS_MENSUALES_SINTETICAS])
    def test_lo_que_el_generador_escribio_es_lo_que_el_lector_entrega(self, formato, bits, alfa):
        # 'sin_pelicula' pide la pelicula SOBRE UNA PAGINA (variante B): fuera de ella el alfa es 0; con el recorte a ras (variante A) no hay nada fuera
        placa = gen_mensual.generar(formato, bits=bits, alfa=alfa, dpi=60, seed=3, variante="B" if alfa == "sin_pelicula" else "A", theta_deg=0.4)
        arreglo = placa.imagen                                            # BGR o BGRA, uint8 o uint16, antes de codificar
        pel = _pel().leer_pelicula(placa.datos)
        assert (pel.bits, pel.formato) == (bits, {"tiff": "TIFF", "png": "PNG", "jpeg": "JPEG"}[formato])
        assert pel.gris.shape == arreglo.shape[:2] and pel.dpi == pytest.approx(60.0, rel=1e-3)
        maximo = 255 if bits == 8 else 65535
        if alfa:
            opaco = arreglo[:, :, 3] == maximo
            assert np.array_equal(pel.validos, opaco) and pel.transparentes == int((~opaco).sum())
            if alfa == "sin_pelicula":
                assert 0 < pel.transparentes < opaco.size, "compuerta: hay pelicula y hay 'sin dato' alrededor"
            else:
                assert pel.transparentes == 0, "un alfa opaco, como el de los TIFF del Epson"
        else:
            assert pel.transparentes == 0 and bool(pel.validos.all())
        if formato == "jpeg":                                             # con perdida: solo la forma
            return
        v = pel.validos
        for capa, indice in (("B", 0), ("G", 1), ("R", 2)):
            esperada = _niveles(arreglo[:, :, indice], bits)
            assert np.allclose(getattr(pel, capa)[v], esperada[v], rtol=0, atol=3e-5), (formato, bits, alfa, capa)

    def test_en_la_meseta_de_la_pelicula_el_rojo_es_el_mas_oscuro_y_el_azul_el_mas_claro(self):
        """En la pelicula real la capa roja es la mas saturada y la azul la menos: la meseta central tiene R << G < B (calibracion de PF.0: meseta BGR = (39, 32, 1)); un lector
        que cruce R y B lo delata con la pelicula misma, no con una prueba escrita para eso."""
        placa = gen_mensual.generar("tiff", bits=16, alfa=True, dpi=60, seed=3)
        pel = _pel().leer_pelicula(placa.datos)
        alto, ancho = pel.gris.shape
        centro = (slice(alto // 2 - 3, alto // 2 + 3), slice(ancho // 2 - 3, ancho // 2 + 3))
        assert float(pel.R[centro].mean()) < float(pel.G[centro].mean()) < float(pel.B[centro].mean())


# ====================================================================================================================== §5 el motor y la mascara

@pytest.fixture(scope="module")
def placa():
    """La placa sintetica del generador INDEPENDIENTE de PF.0 (mancha a +0.8 mm de la linea, 672 x 1156): PNG, BGR uint8 y su verdad."""
    return gen.generar_independiente(0.8, formato="png")


@pytest.fixture(scope="module")
def rgb(placa):
    return np.ascontiguousarray(placa.imagen[:, :, ::-1])


@pytest.fixture(scope="module")
def tiff8(rgb):
    """La escena como TIFF de 8 bits (RGB): las variantes se comparan en el MISMO contenedor, porque el gris que OpenCV saca de un PNG difiere del de un TIFF."""
    return _tiff(rgb)


# Regiones transparentes, medidas el 12-10 BLANQUEANDO esos pixeles con el codigo de HEAD (una mascara equivale a poner el pixel en blanco puro: inv = 0).
# {nombre: ((filas), (columnas), lo que debe pasar)}; la mancha esta en x = 281.5, y = 308.5 y mide ~77 px; la linea en x = 300; los clics en y = 137 y 480.
REGIONES = {
    "fuera_de_la_ventana": ((0, 60), (0, 400), "igual"),
    "dentro_de_la_ventana_lejos_de_la_mancha": ((140, 200), (700, 1000), "igual"),
    "a_la_derecha_lejos_de_la_mancha": ((200, 420), (450, 1156), "igual"),
    "toca_solo_la_capa_azul": ((200, 420), (330, 1156), "solo_azul"),      # la mancha del azul es 1 px mas ancha por la derecha: el gris, el rojo y el verde ni se enteran
    "corta_la_mancha_por_la_izquierda": ((200, 420), (0, 270), "cortada"),
    "toda_la_mancha": ((230, 390), (200, 380), "no_medible"),
}


def _mascara(region):
    (f0, f1), (c0, c1), _ = REGIONES[region]
    validos = np.ones((672, 1156), bool)
    validos[f0:f1, c0:c1] = False
    return validos


def _blanqueada(rgb, region):
    """El oraculo independiente de la mascara: la misma escena con esos pixeles en BLANCO PURO (255), como lo veria un escaner sin pelicula."""
    (f0, f1), (c0, c1), _ = REGIONES[region]
    salida = rgb.copy()
    salida[f0:f1, c0:c1] = 255
    return salida


def _gris_y_color(rgb_):
    bgr = np.ascontiguousarray(rgb_[:, :, ::-1])
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), bgr


class TestElMotorAplicaLaMascara:
    def test_c_sin_mascara_con_todo_valido_y_la_conducta_de_hoy_son_lo_mismo(self, placa, rgb):
        gris, color = _gris_y_color(rgb)
        de_hoy = motor.analizar(gris, color, 600.0, placa.clics)
        con_none = motor.analizar(gris, color, 600.0, placa.clics, validos=None)
        con_todo_valido = motor.analizar(gris, color, 600.0, placa.clics, validos=np.ones(gris.shape, bool))
        assert _huella(de_hoy) == _huella(con_none) == _huella(con_todo_valido)

    @pytest.mark.parametrize("region", sorted(REGIONES))
    def test_c_la_mascara_equivale_a_poner_esos_pixeles_en_blanco_puro(self, placa, rgb, region):
        """El oraculo independiente: `analizar(imagen blanqueada)` (sin mascara) == `analizar(imagen, validos=mascara)`, resultado completo, bit a bit."""
        gris, color = _gris_y_color(rgb)
        gris_b, color_b = _gris_y_color(_blanqueada(rgb, region))
        validos = _mascara(region)
        assert not validos.all() and int((~validos).sum()) > 1000, "compuerta: la region transparente existe"
        con_mascara = motor.analizar(gris, color, 600.0, placa.clics, validos=validos)
        blanqueada = motor.analizar(gris_b, color_b, 600.0, placa.clics)
        # igual bit a bit, salvo las notas con que el motor dice que la zona tiene zonas transparentes (R1-G-03 y R1-G-04): el blanco puro no las lleva
        assert _huella_como_el_blanqueo(con_mascara) == _huella(blanqueada)

    @pytest.mark.parametrize("region", [r for r in sorted(REGIONES) if REGIONES[r][2] == "igual"])
    def test_c_la_transparencia_lejos_de_la_mancha_mide_igual(self, placa, rgb, region):
        gris, color = _gris_y_color(rgb)
        opaco = motor.analizar(gris, color, 600.0, placa.clics)
        r = motor.analizar(gris, color, 600.0, placa.clics, validos=_mascara(region))
        assert opaco["perfiles"]["gris"]["estado"] == "ok" and r["perfiles"]["gris"]["estado"] == "ok"
        for capa in ("gris", "R", "G", "B"):
            assert r["perfiles"][capa]["desfase_px"] == opaco["perfiles"][capa]["desfase_px"], (region, capa)

    def test_c_la_transparencia_puede_tocar_una_capa_y_no_otra(self, placa, rgb):
        """La mancha del azul es mas ancha (saturada 1 px mas): la misma region transparente la corta y no toca al gris, al rojo ni al verde."""
        gris, color = _gris_y_color(rgb)
        opaco = motor.analizar(gris, color, 600.0, placa.clics)
        r = motor.analizar(gris, color, 600.0, placa.clics, validos=_mascara("toca_solo_la_capa_azul"))
        assert opaco["perfiles"]["B"]["estado"] == "ok", "compuerta: sin la region transparente el azul se mide"
        for capa in ("gris", "R", "G"):
            assert r["perfiles"][capa]["desfase_px"] == opaco["perfiles"][capa]["desfase_px"], capa
        assert r["perfiles"]["B"]["estado"] == "no medible: la mancha esta cortada por el borde de la pelicula"

    def test_c_la_transparencia_que_corta_la_mancha_dice_no_medible_con_el_motivo(self, placa, rgb):
        gris, color = _gris_y_color(rgb)
        r = motor.analizar(gris, color, 600.0, placa.clics, validos=_mascara("corta_la_mancha_por_la_izquierda"))
        s = motor.resumen(r)
        assert s["estado"] == "no medible: la mancha esta cortada por el borde de la pelicula" and s["veredicto"] == "No medible"

    def test_c_la_transparencia_sobre_toda_la_mancha_dice_no_medible(self, placa, rgb):
        gris, color = _gris_y_color(rgb)
        r = motor.analizar(gris, color, 600.0, placa.clics, validos=_mascara("toda_la_mancha"))
        assert motor.resumen(r)["estado"].startswith("no medible: ") and motor.valores_medidos(r)["desfase_gris_px"] is None

    def test_c_la_mascara_se_aplica_al_recorte_igual_que_el_marco(self, placa, rgb):
        """`ventana_rotada(..., validos=)`: lo transparente es 0 (sin pelicula) en cada ventana y lo demas queda como estaba."""
        gris, color = _gris_y_color(rgb)
        P = motor.PARAMETROS
        validos = np.ones(gris.shape, bool)
        validos[250:270, 250:300] = False                  # dentro de la ventana, sin tocar la linea (x = 300 +- 4)
        sin, _, _ = motor.ventana_rotada(gris, color, placa.clics, 0.0, P, MM_POR_PX)
        con, clics_v, M = motor.ventana_rotada(gris, color, placa.clics, 0.0, P, MM_POR_PX, validos=validos)
        assert set(con) == set(sin) == {"gris", "R", "G", "B"}
        # la ventana empieza en x0 = floor(300) - medio_ancho, y0 = floor(137) - margen; un angulo 0 no mueve los pixeles
        medio = int(round(P["ventana_mm"] / MM_POR_PX))
        margen = int(round(P["margen_filas_mm"] / MM_POR_PX))
        x0, y0 = 300 - medio, 137 - margen
        oculto = np.zeros(sin["gris"].shape, bool)
        oculto[250 - y0:270 - y0, 250 - x0:300 - x0] = True
        for nombre in sin:
            assert np.all(con[nombre][oculto] == 0.0), nombre
            assert np.array_equal(con[nombre][~oculto], sin[nombre][~oculto]), nombre
            assert float(np.abs(sin[nombre][oculto]).max()) > 0, "compuerta: sin mascara ahi si hay senal"

    def test_una_mascara_de_otra_forma_que_la_imagen_se_rechaza(self, placa, rgb):
        gris, color = _gris_y_color(rgb)
        with pytest.raises(ValueError, match="mascara"):
            motor.analizar(gris, color, 600.0, placa.clics, validos=np.ones((10, 10), bool))

    def test_las_firmas_nuevas_tienen_un_valor_por_defecto_que_reproduce_la_conducta_de_hoy(self):
        for nombre in ("analizar", "ventana_rotada"):
            parametro = inspect.signature(getattr(motor, nombre)).parameters["validos"]
            assert parametro.default is None, nombre
        assert list(inspect.signature(motor.leer_imagen).parameters) == ["datos"]

    def test_la_version_del_algoritmo_cambio_porque_cambia_la_conducta_con_16_bits_y_alfa(self):
        assert motor.VERSION_ALGORITMO == "PI-2"


# ====================================================================================================================== §6 el servicio (c y b)

def _rgba_tiff(rgb, validos):
    return _tiff(np.dstack([rgb, np.where(validos, 255, 0).astype(np.uint8)]), alfa=True)


class TestElServicioPasaLaMascara:
    def test_c_un_tiff_rgba_opaco_da_lo_mismo_que_el_rgb_por_el_servicio(self, placa, rgb, tiff8):
        a = svc.analizar_imagen(tiff8, placa.clics)
        b = svc.analizar_imagen(_rgba_tiff(rgb, np.ones(rgb.shape[:2], bool)), placa.clics)
        assert _sin_la_version(a) == _sin_la_version(b)

    @pytest.mark.parametrize("region", [r for r in sorted(REGIONES) if REGIONES[r][2] == "igual"])
    def test_c_transparencia_lejos_de_la_mancha_mide_igual_por_el_servicio(self, placa, rgb, tiff8, region):
        opaco = svc.analizar_imagen(tiff8, placa.clics)
        r = svc.analizar_imagen(_rgba_tiff(rgb, _mascara(region)), placa.clics)
        for capa in ("gris", "R", "G", "B"):
            assert r["perfiles"][capa]["desfase_px"] == opaco["perfiles"][capa]["desfase_px"], (region, capa)

    def test_c_la_transparencia_puede_tocar_una_capa_y_no_otra_por_el_servicio(self, placa, rgb, tiff8):
        opaco = svc.analizar_imagen(tiff8, placa.clics)
        r = svc.analizar_imagen(_rgba_tiff(rgb, _mascara("toca_solo_la_capa_azul")), placa.clics)
        for capa in ("gris", "R", "G"):
            assert r["perfiles"][capa]["desfase_px"] == opaco["perfiles"][capa]["desfase_px"], capa
        assert opaco["perfiles"]["B"]["estado"] == "ok" and r["perfiles"]["B"]["estado"].startswith("no medible: la mancha esta cortada")

    def test_c_transparencia_sobre_la_mancha_es_no_medible_con_motivo_y_sin_valueerror(self, placa, rgb):
        datos = _rgba_tiff(rgb, _mascara("corta_la_mancha_por_la_izquierda"))
        r = svc.analizar_imagen(datos, placa.clics)
        assert r["perfiles"]["gris"]["estado"] == "no medible: la mancha esta cortada por el borde de la pelicula"
        r = svc.analizar_imagen(_rgba_tiff(rgb, _mascara("toda_la_mancha")), placa.clics)
        assert r["perfiles"]["gris"]["estado"].startswith("no medible: ")

    def test_c_el_servicio_usa_la_misma_mascara_que_el_blanqueo_independiente(self, placa, rgb):
        """Servicio (bytes con alfa) == motor sobre la escena blanqueada: la mascara que lee `leer_pelicula` es la que `analizar` aplica."""
        region = "corta_la_mancha_por_la_izquierda"
        por_servicio = svc.analizar_imagen(_rgba_tiff(rgb, _mascara(region)), placa.clics)
        gris_b, color_b = _gris_y_color(_blanqueada(rgb, region))
        por_blanqueo = motor.analizar(gris_b, color_b, 600.0, placa.clics)
        for capa in ("gris", "R", "G", "B"):
            assert por_servicio["perfiles"][capa]["estado"] == por_blanqueo["perfiles"][capa]["estado"], capa

    def test_b_el_servicio_mide_un_tiff_de_16_bits_y_la_verdad_conocida_lo_respalda(self, placa, rgb):
        """Verdad conocida: el generador independiente da el desfase de la mancha; el TIFF de 16 bits (x 257) mide dentro de la exactitud del motor."""
        datos16 = _tiff(rgb.astype(np.uint16) * 257)
        r = svc.analizar_imagen(datos16, placa.clics)
        s = motor.resumen(r)
        assert s["estado"] == "ok" and r["dpi"] == 600.0
        for capa in ("G", "R"):
            assert r["perfiles"][capa]["estado"] == "ok"
        verdad_px = placa.verdad.desfase_px
        assert abs(r["perfiles"]["G"]["desfase_px"] - verdad_px) < 0.25, (r["perfiles"]["G"]["desfase_px"], verdad_px)
        assert abs(s["desfase_mm"] - placa.verdad.desfase_mm) < 0.03, (s["desfase_mm"], placa.verdad.desfase_mm)

    def test_b_un_tiff_de_16_bits_hecho_de_uno_de_8_x_257_da_el_mismo_desfase_por_capa(self, placa, rgb, tiff8):
        ocho = svc.analizar_imagen(tiff8, placa.clics)
        diez_y_seis = svc.analizar_imagen(_tiff(rgb.astype(np.uint16) * 257), placa.clics)
        for capa in ("R", "G", "B"):
            a, b = ocho["perfiles"][capa], diez_y_seis["perfiles"][capa]
            assert a["estado"] == b["estado"] == "ok", capa
            assert b["desfase_px"] == pytest.approx(a["desfase_px"], abs=0.01), capa
        gris_a, gris_b = ocho["perfiles"]["gris"]["desfase_px"], diez_y_seis["perfiles"]["gris"]["desfase_px"]
        assert gris_b == pytest.approx(gris_a, abs=0.5), "el gris de color: ver la nota del docstring (la cuantizacion del gris de 8 bits mueve el borde)"

    @pytest.mark.parametrize("desfase_mm", [-1.2, 0.0, 0.8, 2.5])
    def test_b_una_escena_neutra_de_16_bits_da_exactamente_lo_mismo_que_la_de_8_bits(self, desfase_mm):
        """Con R = G = B el gris de 8 bits es el valor y el de 16 bits tambien: sin cuantizacion distinta, el desfase coincide en las cuatro capas."""
        p = gen.generar_independiente(desfase_mm, formato="png")
        neutro = np.repeat(cv2.cvtColor(p.imagen, cv2.COLOR_BGR2GRAY)[:, :, None], 3, axis=2)
        a = svc.analizar_imagen(_tiff(neutro), p.clics)
        b = svc.analizar_imagen(_tiff(neutro.astype(np.uint16) * 257), p.clics)
        for capa in ("gris", "R", "G", "B"):
            assert a["perfiles"][capa]["estado"] == "ok" and b["perfiles"][capa]["estado"] == "ok", capa
            assert b["perfiles"][capa]["desfase_px"] == pytest.approx(a["perfiles"][capa]["desfase_px"], abs=0.01), (desfase_mm, capa)

    def test_c_guardar_acepta_una_imagen_con_transparencia_lejos_de_la_mancha_y_guarda_lo_medido(self, bd, placa, rgb, tiff8):
        _calibracion(bd, f"{S1} 15:03:03", "Cambio de fuente", SERIE_A)
        medido = svc.analizar_imagen(tiff8, placa.clics)["perfiles"]["gris"]["desfase_px"]
        nuevo = svc.guardar(USUARIO, S1, _rgba_tiff(rgb, _mascara("dentro_de_la_ventana_lejos_de_la_mancha")), "placa.tif", placa.clics)
        fila = _consulta(bd, "SELECT estado_gris, desfase_gris_px, version_algoritmo, dpi FROM braqui_posicion_inicial WHERE id = ?", (nuevo,))[0]
        assert fila == ("ok", pytest.approx(medido), "PI-2", 600.0)

    def test_c_guardar_con_transparencia_sobre_la_mancha_guarda_el_no_medible_sin_lanzar(self, bd, placa, rgb):
        _calibracion(bd, f"{S1} 15:03:03", "Cambio de fuente", SERIE_A)
        nuevo = svc.guardar(USUARIO, S1, _rgba_tiff(rgb, _mascara("corta_la_mancha_por_la_izquierda")), "placa.tif", placa.clics)
        fila = _consulta(bd, "SELECT estado_gris, desfase_gris_px FROM braqui_posicion_inicial WHERE id = ?", (nuevo,))[0]
        assert fila == ("no medible: la mancha esta cortada por el borde de la pelicula", None)

    def test_el_servicio_lee_con_leer_pelicula_y_le_pasa_la_mascara_al_motor(self):
        """Por AST: `analizar_imagen` llama a `leer_pelicula` y a `motor.analizar(..., validos=...)`; ya no pasa por `motor.leer_imagen`."""
        fuente = (RAIZ / "services" / "posicion_inicial_braqui.py").read_text(encoding="utf-8")
        funcion = next(n for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.FunctionDef) and n.name == "analizar_imagen")
        llamadas = [n for n in ast.walk(funcion) if isinstance(n, ast.Call)]
        nombres = {(n.func.id if isinstance(n.func, ast.Name) else n.func.attr) for n in llamadas}
        assert "leer_pelicula" in nombres, nombres
        al_motor = [n for n in llamadas if isinstance(n.func, ast.Attribute) and n.func.attr == "analizar"]
        assert len(al_motor) == 1 and "validos" in {k.arg for k in al_motor[0].keywords}


# ====================================================================================================================== §6-bis la ronda 1 de la revision (12-10)

def _rgba(rgb, validos, bits, **etiquetas):
    """La escena como TIFF RGBA de 8 o de 16 bits: el alfa vale el maximo del tipo donde hay dato y 0 donde no (en 16 bits el color de la escena es x 257)."""
    if bits == 8:
        return _tiff(np.dstack([rgb, np.where(validos, 255, 0).astype(np.uint8)]), alfa=True, **etiquetas)
    return _tiff(np.dstack([rgb.astype(np.uint16) * 257, np.where(validos, 65535, 0).astype(np.uint16)]), alfa=True, **etiquetas)


def _rgb(rgb, bits, **etiquetas):
    return _tiff(rgb if bits == 8 else rgb.astype(np.uint16) * 257, **etiquetas)


class TestElAlfaConDieciseisBits:
    """R1-G-01: el caso real (un TIFF RGBA de 48 o 64 bits guardado por Paint) no estaba cubierto por ninguna prueba: las de alfa del servicio usaban solo TIFF de
    8 bits y las de 16 bits solo TIFF opacos, asi que un servicio que dejara de pasar la mascara cuando la imagen es de 16 bits sobrevivia a las 162 pruebas."""

    @pytest.mark.parametrize("region", sorted(REGIONES))
    def test_c_16_bits_el_motor_con_la_mascara_que_lee_el_lector_equivale_a_poner_esos_pixeles_en_blanco_puro(self, placa, rgb, region):
        validos = _mascara(region)
        pel = _pel().leer_pelicula(_rgba(rgb, validos, 16))
        assert pel.bits == 16 and pel.transparentes == int((~validos).sum()) and pel.transparentes > 1000, "compuerta: el TIFF de 16 bits TRAE la transparencia"
        gris, color = pel.en_bgr()
        blanqueada = _pel().leer_pelicula(_rgb(_blanqueada(rgb, region), 16))
        assert blanqueada.transparentes == 0
        con_mascara = motor.analizar(gris, color, pel.dpi, placa.clics, validos=pel.validos)
        de_blanco = motor.analizar(*blanqueada.en_bgr(), blanqueada.dpi, placa.clics)
        assert _huella_como_el_blanqueo(con_mascara) == _huella(de_blanco)

    @pytest.mark.parametrize("region", sorted(REGIONES))
    def test_c_16_bits_el_servicio_con_alfa_equivale_a_poner_esos_pixeles_en_blanco_puro(self, placa, rgb, region):
        """La prueba que mata al servicio que descarta la mascara en 16 bits (mutacion S4): bytes con alfa por `svc.analizar_imagen` == la escena blanqueada, sin alfa."""
        por_servicio = svc.analizar_imagen(_rgba(rgb, _mascara(region), 16), placa.clics)
        de_blanco = svc.analizar_imagen(_rgb(_blanqueada(rgb, region), 16), placa.clics)
        assert _huella_como_el_blanqueo(por_servicio) == _huella(de_blanco), region

    def test_c_16_bits_la_mascara_cambia_algo_de_verdad(self, placa, rgb):
        """Compuerta de las dos anteriores: el servicio con alfa NO da lo mismo que el servicio sin alfa. Si diera lo mismo, las pruebas de equivalencia pasarian en
        vacio aunque el servicio descartara la mascara."""
        opaco = svc.analizar_imagen(_rgb(rgb, 16), placa.clics)
        for region in ("corta_la_mancha_por_la_izquierda", "toca_solo_la_capa_azul", "a_la_derecha_lejos_de_la_mancha"):
            con_alfa = svc.analizar_imagen(_rgba(rgb, _mascara(region), 16), placa.clics)
            assert _huella(con_alfa) != _huella(opaco), region

    @pytest.mark.parametrize("bits", [8, 16])
    def test_c_la_transparencia_que_corta_la_mancha_es_no_medible_con_el_motivo_en_las_cuatro_capas_por_el_servicio(self, placa, rgb, bits):
        r = svc.analizar_imagen(_rgba(rgb, _mascara("corta_la_mancha_por_la_izquierda"), bits), placa.clics)
        assert {capa: r["perfiles"][capa]["estado"] for capa in ("gris", "R", "G", "B")} == {c: CORTADA for c in ("gris", "R", "G", "B")}

    @pytest.mark.parametrize("bits", [8, 16])
    def test_c_guardar_con_transparencia_sobre_la_mancha_guarda_el_no_medible_sin_lanzar_en_8_y_16_bits(self, bd, placa, rgb, bits):
        _calibracion(bd, f"{S1} 15:03:03", "Cambio de fuente", SERIE_A)
        nuevo = svc.guardar(USUARIO, S1, _rgba(rgb, _mascara("corta_la_mancha_por_la_izquierda"), bits), "placa.tif", placa.clics)
        fila = _consulta(bd, "SELECT estado_gris, estado_r, estado_g, estado_b, desfase_gris_px FROM braqui_posicion_inicial WHERE id = ?", (nuevo,))[0]
        assert fila == (CORTADA, CORTADA, CORTADA, CORTADA, None)

    @pytest.mark.parametrize("bits", [8, 16])
    def test_c_la_pagina_dice_no_medible_con_el_motivo_cuando_la_transparencia_corta_la_mancha(self, fabrica, dialogos, placa, rgb, tmp_path, bits):
        p = fabrica()
        ruta = tmp_path / "corta.tif"
        ruta.write_bytes(_rgba(rgb, _mascara("corta_la_mancha_por_la_izquierda"), bits, datetime="2026:09:30 10:00:00"))
        _cargar(p, dialogos, str(ruta))
        assert p.estado == "imagen" and dialogos.de("warning") == []
        _marcar(p, placa.clics)
        assert p.estado == "analizada" and dialogos.de("warning") == []
        assert p.recuadro_gris.text().split("\n\n")[0] == "No medible: la mancha esta cortada por el borde de la pelicula"       # B.7: y, en otro parrafo, la capa que se reporta
        for capa in "RGB":
            assert f"Capa {capa}: No medible: la mancha esta cortada por el borde de la pelicula" in p.recuadro_rgb.text()

    def test_c_la_pagina_mide_la_de_16_bits_con_alfa_lejos_de_la_mancha_igual_que_la_opaca(self, fabrica, dialogos, placa, rgb, tmp_path):
        p = fabrica()
        ruta = tmp_path / "lejos.tif"
        ruta.write_bytes(_rgba(rgb, _mascara("dentro_de_la_ventana_lejos_de_la_mancha"), 16, datetime="2026:09:30 10:00:00"))
        _cargar(p, dialogos, str(ruta))
        _marcar(p, placa.clics)
        assert p.estado == "analizada"
        opaco = svc.analizar_imagen(_rgb(rgb, 16), placa.clics)
        for capa in ("gris", "R", "G", "B"):
            assert p._resultado["perfiles"][capa]["desfase_px"] == opaco["perfiles"][capa]["desfase_px"], capa


# Mascaras delgadas, junto a la linea o repartidas por toda la imagen: tiras de 1 y 3 px, una columna de cada dos, una fila de cada tres.
def _mascaras_delgadas():
    alto, ancho = 672, 1156
    casos = {}
    for x in (298, 300, 302, 304):
        v = np.ones((alto, ancho), bool)
        v[:, x] = False
        casos[f"tira_de_1_px_en_x{x}"] = v
    v = np.ones((alto, ancho), bool)
    v[:, ::2] = False
    casos["columnas_de_por_medio"] = v
    v = np.ones((alto, ancho), bool)
    v[::3, :] = False
    casos["una_fila_de_cada_tres"] = v
    v = np.ones((alto, ancho), bool)
    v[140:300, 301:304] = False
    casos["tira_de_3_px_junto_a_la_linea_entre_los_clics"] = v
    return casos


class TestUnaMascaraDelgadaNoHaceFallarAlMotor:
    """R1-G-03: una tira transparente de 1 px junto a la linea partia los centros de la linea en dos grupos; el recorte robusto de `refinar_linea` rechazaba TODAS las
    filas y `np.polyfit` recibia un vector vacio (`TypeError: expected non-empty vector for x`): el motor lanzaba (y la pagina decia "Error inesperado") en vez de
    decir que no pudo ubicar la linea. Ya fallaba con el motor de HEAD sobre la imagen con esos pixeles en blanco; A.1 solo abrio la puerta (antes esa imagen se rechazaba)."""

    def test_refinar_linea_no_lanza_cuando_el_recorte_robusto_rechaza_todas_las_filas(self, monkeypatch):
        alto = 100
        centros = np.where(np.random.default_rng(0).random(alto) < 0.52, 20.0, 24.6)      # dos grupos intercalados, el 52 % en uno: MAD = 0 y tolerancia 0.5
        filas = np.arange(5, 95)
        pendiente, corte = np.polyfit(filas, centros[filas], 1)
        residuo = centros[filas] - (pendiente * filas + corte)
        mad = np.median(np.abs(residuo - np.median(residuo)))
        assert not np.any(np.abs(residuo) <= max(3 * 1.4826 * mad, 0.5)), "compuerta: en la primera vuelta el recorte robusto rechaza TODAS las filas"
        imagen = np.zeros((alto, 40), np.float32)
        imagen[:, 0] = np.arange(alto)                                  # la fila lleva su numero: la funcion sustituta lo lee
        monkeypatch.setattr(motor, "centro_de_linea_en_fila", lambda fila, x_aprox, *a, **k: float(centros[int(fila[0])]))
        assert motor.refinar_linea(imagen, [(22, 5), (22, 94)]) is None

    def test_el_recorte_robusto_de_siempre_no_cambia_cuando_si_hay_una_recta(self, monkeypatch):
        """El control: centros sobre una recta (con dos valores atipicos) siguen dando su recta; la guarda solo actua cuando no queda ninguna fila."""
        alto = 100
        centros = 20.0 + 0.01 * np.arange(alto)
        centros[[30, 60]] += 9.0
        imagen = np.zeros((alto, 40), np.float32)
        imagen[:, 0] = np.arange(alto)
        monkeypatch.setattr(motor, "centro_de_linea_en_fila", lambda fila, x_aprox, *a, **k: float(centros[int(fila[0])]))
        linea = motor.refinar_linea(imagen, [(22, 5), (22, 94)])
        assert linea is not None and linea["pendiente"] == pytest.approx(0.01, abs=1e-9) and linea["corte"] == pytest.approx(20.0, abs=1e-9)
        assert int(np.sum(~linea["usadas"])) == 2

    @pytest.mark.parametrize("bits", [8, 16])
    @pytest.mark.parametrize("nombre", sorted(_mascaras_delgadas()))
    def test_c_ninguna_mascara_delgada_hace_lanzar_al_servicio_ni_a_lo_que_se_hace_con_su_resultado(self, placa, rgb, nombre, bits):
        validos = _mascaras_delgadas()[nombre]
        assert not validos.all() and int((~validos).sum()) >= 480, "compuerta: la mascara existe (la mas chica, la tira de 3 px entre los clics, tiene 480 pixeles)"
        r = svc.analizar_imagen(_rgba(rgb, validos, bits), placa.clics)
        assert set(r["perfiles"]) == {"gris", "R", "G", "B"}
        assert motor.resumen(r)["veredicto"] and motor.valores_medidos(r)["estado_gris"] == r["perfiles"]["gris"]["estado"]

    @pytest.mark.parametrize("bits", [8, 16])
    def test_c_si_la_linea_no_se_pudo_ubicar_por_la_transparencia_el_mensaje_lo_dice(self, placa, rgb, bits):
        r = svc.analizar_imagen(_rgba(rgb, _mascaras_delgadas()["tira_de_1_px_en_x302"], bits), placa.clics)
        assert r["mensaje_linea"] == LINEA_NO_REFINADA + NOTA_TRANSPARENCIA
        assert r["linea"] is None

    @pytest.mark.parametrize("bits", [8, 16])
    def test_c_la_pagina_no_dice_error_inesperado_ni_deja_guardar_y_dice_por_que(self, fabrica, dialogos, placa, rgb, tmp_path, bits):
        p = fabrica()
        ruta = tmp_path / "tira.tif"
        ruta.write_bytes(_rgba(rgb, _mascaras_delgadas()["tira_de_1_px_en_x302"], bits, datetime="2026:09:30 10:00:00"))
        _cargar(p, dialogos, str(ruta))
        _marcar(p, placa.clics)
        assert p.estado == "analizada" and dialogos.de("critical") == [] and dialogos.de("warning") == []
        assert not p.boton_guardar.isEnabled(), "la linea no se ubico: lo medido contra los puntos no se guarda (P10)"
        texto = p.recuadro_gris.text()
        assert "No se encontró la línea marcada" in texto and "la zona analizada tiene zonas transparentes" in texto

    def test_las_dos_formas_de_no_ubicar_la_linea_llevan_la_nota_y_las_otras_no(self, monkeypatch):
        """`referencia_de_la_linea(..., nota=)`: la nota va al final de los DOS mensajes de linea no ubicada (no se pudo refinar; la refinada se aleja de los clics) y de
        ninguno de los otros dos (refinada por su perfil; ubicada con los clics porque asi se pidio). Sin nota, los cuatro textos son los de siempre."""
        P = dict(motor.PARAMETROS)
        imagen = np.zeros((100, 60), np.float32)
        clics = [(30, 5), (30, 94)]
        recta = {"pendiente": 0.0, "corte": 30.0, "filas": np.arange(5, 95), "centros": np.full(90, 30.0), "usadas": np.ones(90, bool), "dispersion": 0.1}
        escenas = {"no_se_pudo_refinar": (None, LINEA_NO_REFINADA),
                   "pocas_filas": (dict(recta, usadas=np.arange(90) < 4), LINEA_NO_REFINADA),
                   "se_aleja_de_los_clics": (dict(recta, corte=40.0), "la linea refinada se aleja mas de 5 px de los clics: se usan los clics"),
                   "refinada": (recta, "linea refinada por su perfil")}
        for nombre, (devuelve, texto) in escenas.items():
            monkeypatch.setattr(motor, "refinar_linea", lambda imagen, clics, devuelve=devuelve: devuelve)
            falla = nombre != "refinada"
            assert motor.referencia_de_la_linea(imagen, clics, P)[3] == texto, nombre
            assert motor.referencia_de_la_linea(imagen, clics, P, nota=NOTA_TRANSPARENCIA)[3] == texto + (NOTA_TRANSPARENCIA if falla else ""), nombre
        sin_refinar = dict(P, refinar_linea=False)                      # "ubicada con los clics" porque asi se pidio: no es un fallo, no lleva la nota
        assert motor.referencia_de_la_linea(imagen, clics, sin_refinar, nota=NOTA_TRANSPARENCIA)[3] == "linea ubicada con los clics"

    def test_el_mensaje_de_la_linea_de_siempre_no_cambia_sin_transparencia_en_la_zona(self, placa, rgb):
        """Con el valor por omision de `nota` y de `con_transparencia` el motor es el de hoy; y una mascara toda valida no agrega nada."""
        gris, color = _gris_y_color(rgb)
        sin = motor.analizar(gris, color, 600.0, placa.clics)
        todo_valido = motor.analizar(gris, color, 600.0, placa.clics, validos=np.ones(gris.shape, bool))
        assert sin["mensaje_linea"] == todo_valido["mensaje_linea"] == "linea refinada por su perfil"
        assert inspect.signature(motor.referencia_de_la_linea).parameters["nota"].default == ""
        assert inspect.signature(motor.medir_perfil).parameters["con_transparencia"].default is False


class TestElMotivoDiceQueLaTransparenciaEsLaCausa:
    """R1-G-04: cuando la region transparente cubre TODA la mancha, el motor decia "la linea tapa el borde de la meseta" (el motivo de cuando no hay filas con los dos
    bordes a la vista) y culpaba a la linea. La prueba de antes solo pedia `startswith("no medible: ")` y no veia el texto falso."""

    def test_la_transparencia_sobre_toda_la_mancha_ya_no_culpa_a_la_linea(self, placa, rgb):
        gris, color = _gris_y_color(rgb)
        r = motor.analizar(gris, color, 600.0, placa.clics, validos=_mascara("toda_la_mancha"))
        for capa in ("gris", "R", "G", "B"):
            assert r["perfiles"][capa]["estado"] == SIN_FILAS_POR_TRANSPARENCIA, capa
        s = motor.resumen(r)
        assert s["estado"] == SIN_FILAS_POR_TRANSPARENCIA and s["veredicto"] == "No medible" and "linea" not in s["estado"]
        assert motor.valores_medidos(r)["estado_gris"] == SIN_FILAS_POR_TRANSPARENCIA

    @pytest.mark.parametrize("bits", [8, 16])
    def test_lo_mismo_por_el_servicio_y_lo_que_se_guarda(self, bd, placa, rgb, bits):
        datos = _rgba(rgb, _mascara("toda_la_mancha"), bits)
        r = svc.analizar_imagen(datos, placa.clics)
        assert {capa: r["perfiles"][capa]["estado"] for capa in ("gris", "R", "G", "B")} == {c: SIN_FILAS_POR_TRANSPARENCIA for c in ("gris", "R", "G", "B")}
        _calibracion(bd, f"{S1} 15:03:03", "Cambio de fuente", SERIE_A)
        nuevo = svc.guardar(USUARIO, S1, datos, "placa.tif", placa.clics)
        assert _consulta(bd, "SELECT estado_gris FROM braqui_posicion_inicial WHERE id = ?", (nuevo,))[0] == (SIN_FILAS_POR_TRANSPARENCIA,)

    @pytest.mark.parametrize("bits", [8, 16])
    def test_la_pagina_lo_dice_con_las_palabras_del_motivo(self, fabrica, dialogos, placa, rgb, tmp_path, bits):
        p = fabrica()
        ruta = tmp_path / "toda.tif"
        ruta.write_bytes(_rgba(rgb, _mascara("toda_la_mancha"), bits, datetime="2026:09:30 10:00:00"))
        _cargar(p, dialogos, str(ruta))
        _marcar(p, placa.clics)
        assert p.estado == "analizada" and dialogos.de("warning") == []
        assert p.recuadro_gris.text().split("\n\n")[0] == "No medible: no quedan filas con la mancha a la vista; la zona analizada tiene zonas transparentes"       # B.7: y, en otro parrafo, la capa que se reporta
        assert "linea tapa" not in p.recuadro_gris.text() and "linea tapa" not in p.recuadro_rgb.text()

    def test_el_motivo_de_siempre_no_cambia_si_la_transparencia_no_esta_en_la_zona_analizada(self):
        """La escena de PI.1 donde la linea cae de verdad sobre el borde de la pelicula (`la linea tapa el borde`, V3): sin mascara, con la mascara toda valida y con una
        transparencia a mas de 20 mm de la linea (fuera de la ventana) el motivo es EXACTAMENTE el de siempre. La nota es sobre la zona analizada, no sobre la imagen."""
        escaneo = _escena(97.0 + 30, 90.0 + 30, borde=80.0 + 30)
        clics = [(120, 56), (120, 377)]
        lejos = np.ones(escaneo.shape, bool)
        lejos[:, 900:] = False
        assert int((~lejos).sum()) > 10000
        for etiqueta, validos in (("sin mascara", None), ("toda valida", np.ones(escaneo.shape, bool)), ("transparencia fuera de la ventana", lejos)):
            r = motor.analizar(escaneo, _bgr(escaneo), 600.0, clics, validos=validos)
            assert r["perfiles"]["gris"]["estado"] == LINEA_TAPA, etiqueta
            assert not r["mensaje_linea"].endswith(NOTA_TRANSPARENCIA), etiqueta

    def test_con_transparencia_dentro_de_la_zona_el_motivo_lleva_la_nota_aunque_la_causa_sea_la_linea(self):
        """El limite de la regla, dicho en voz alta: si la zona analizada tiene zonas transparentes y no quedan filas con la mancha a la vista, el motor no puede saber cual
        de las dos cosas lo causo, y dice lo que SI sabe (no quedan filas; la zona tiene zonas transparentes) en vez de culpar a la linea."""
        escaneo = _escena(97.0 + 30, 90.0 + 30, borde=80.0 + 30)
        clics = [(120, 56), (120, 377)]
        dentro = np.ones(escaneo.shape, bool)
        dentro[430:460, 300:500] = False                       # dentro de la ventana (x -352..592, y 0..448), lejos de la mancha y de la linea
        r = motor.analizar(escaneo, _bgr(escaneo), 600.0, clics, validos=dentro)
        assert r["perfiles"]["gris"]["estado"] == SIN_FILAS_POR_TRANSPARENCIA

    def test_los_motivos_de_cortada_y_los_que_miden_no_cambian_con_la_transparencia_en_la_zona(self, placa, rgb):
        gris, color = _gris_y_color(rgb)
        r = motor.analizar(gris, color, 600.0, placa.clics, validos=_mascara("corta_la_mancha_por_la_izquierda"))
        assert r["perfiles"]["gris"]["estado"] == CORTADA, "este motivo ya dice que la mancha esta cortada por un borde: no se toca"
        r = motor.analizar(gris, color, 600.0, placa.clics, validos=_mascara("a_la_derecha_lejos_de_la_mancha"))
        assert r["perfiles"]["gris"]["estado"] == "ok" and r["mensaje_linea"] == "linea refinada por su perfil"


# ====================================================================================================================== §7 cero diferencias en 8 bits (a, e)

def _bytes_de(origen, nombre):
    if origen == "datos":
        return (DATOS / nombre).read_bytes()
    if not Path(_corpus.PELICULAS_RAIZ).is_dir():
        pytest.skip("no hay carpeta de peliculas reales en esta maquina (HI-0)")
    ruta = Path(_corpus.PELICULAS_RAIZ) / nombre
    if not ruta.is_file():
        pytest.fail(f"{nombre}: la carpeta de peliculas existe y la pelicula no esta ({ruta})")
    return ruta.read_bytes()


IMAGENES_REALES = [("datos", n) for n in LAS_3_DEL_REPO] + [("corpus", n) for n in LAS_23]


class TestCeroDiferenciasEn8Bits:
    def test_las_23_declaradas_aqui_son_las_de_la_carpeta_y_las_3_del_repo_estan(self):
        assert len(LAS_23) == 23 and len(set(LAS_23)) == 23 and set(HEAD_DPI_Y_FECHA) == set(LAS_23)
        assert all((DATOS / n).is_file() for n in LAS_3_DEL_REPO)
        for clave, relativa in _corpus.todas_las_peliculas_declaradas().items():
            assert relativa in LAS_23, f"{clave} ({relativa}) esta en el registro del corpus y no entre las 23"

    @pytest.mark.parametrize("origen,nombre", IMAGENES_REALES, ids=[f"{o}/{n}" for o, n in IMAGENES_REALES])
    def test_a_leer_imagen_entrega_los_mismos_arreglos_la_misma_resolucion_y_la_misma_fecha_que_antes(self, origen, nombre):
        datos = _bytes_de(origen, nombre)
        gris, color, dpi, fecha = motor.leer_imagen(datos)
        gris_h, color_h = _arreglos_como_en_head(datos)
        assert gris.dtype == np.uint8 and color.dtype == np.uint8, "en 8 bits el lector entrega uint8, como siempre"
        assert gris.shape == gris_h.shape and color.shape == color_h.shape
        assert np.array_equal(gris, gris_h), "el gris de 8 bits es IMREAD_GRAYSCALE, no cvtColor del color"
        assert np.array_equal(color, color_h), "el color de 8 bits es IMREAD_COLOR (BGR)"
        dpi_head, fecha_head = HEAD_DPI_Y_FECHA[nombre]
        assert dpi == pytest.approx(dpi_head, abs=1e-3), nombre
        assert (fecha.isoformat() if fecha else None) == fecha_head, nombre

    @pytest.mark.parametrize("origen,nombre", IMAGENES_REALES, ids=[f"{o}/{n}" for o, n in IMAGENES_REALES])
    def test_a_la_pelicula_de_8_bits_es_valida_en_todo_y_sus_capas_son_los_valores_sin_tocar(self, origen, nombre):
        datos = _bytes_de(origen, nombre)
        pel = _pel().leer_pelicula(datos)
        gris_h, color_h = _arreglos_como_en_head(datos)
        assert pel.bits == 8 and pel.transparentes == 0 and pel.validos.shape == gris_h.shape and bool(pel.validos.all())
        assert np.array_equal(pel.gris, gris_h.astype(np.float32))
        for capa, indice in (("B", 0), ("G", 1), ("R", 2)):
            assert np.array_equal(getattr(pel, capa), color_h[:, :, indice].astype(np.float32)), (nombre, capa)

    @pytest.mark.parametrize("nombre", sorted(CLICS_DE_LA_SUITE))
    def test_a_analizar_da_el_mismo_resultado_numero_por_numero_con_los_clics_de_la_suite(self, nombre):
        datos = (DATOS / nombre).read_bytes()
        gris_h, color_h = _arreglos_como_en_head(datos)
        gris_n, color_n, dpi, _ = motor.leer_imagen(datos)         # la resolucion se compara aparte (arriba); aqui es la misma para los tres caminos
        juegos = CLICS_DE_LA_SUITE[nombre]
        assert len(juegos) >= 1
        for etiqueta, clics in juegos.items():
            de_antes = motor.analizar(gris_h, color_h, dpi, clics)
            por_el_motor = motor.analizar(gris_n, color_n, dpi, clics)
            por_el_servicio = svc.analizar_imagen(datos, clics)
            assert _huella(por_el_motor) == _huella(de_antes), (nombre, etiqueta, "motor")
            # el servicio convierte los clics a float y pasa la mascara: el resultado es el mismo numero por numero
            assert _huella(por_el_servicio) == _huella(de_antes), (nombre, etiqueta, "servicio")
            assert por_el_servicio["version"] == "PI-2"

    def test_e_epson009_es_un_tiff_rgba_de_paint_que_se_lee_como_hoy(self):
        datos = (DATOS / "EPSON009.jpeg").read_bytes()
        pel = _pel().leer_pelicula(datos)
        assert (pel.formato, pel.bits, pel.transparentes) == ("TIFF", 8, 0), "un .jpeg que es un TIFF RGBA de 8 bits con alfa opaco"
        assert pel.dpi == pytest.approx(96.012, abs=1e-3) and motor.clase_resolucion(pel.dpi, motor.PARAMETROS) == "editor"
        assert pel.validos.shape == (672, 1156) and bool(pel.validos.all())

    def test_a_no_vacuidad_se_comparo_lo_que_se_dice_que_se_comparo(self):
        assert sum(len(j) for j in CLICS_DE_LA_SUITE.values()) == 11, "4 juegos de braqui_00, 6 de EPSON009 y 1 de EPSON031"
        assert len(IMAGENES_REALES) == 26


# ====================================================================================================================== §8 una sola definicion

def _definiciones(nombre):
    """[ruta] de cada archivo de `analisisImagenes/` (sin los de Catphan) que DEFINE una funcion con ese nombre."""
    salida = []
    for ruta in sorted((RAIZ / "analisisImagenes").glob("*.py")):
        if any(isinstance(n, ast.FunctionDef) and n.name == nombre for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8")))):
            salida.append(ruta.name)
    return salida


class TestUnaSolaDefinicion:
    @pytest.mark.parametrize("nombre", ["clase_resolucion", "escala_mm"])
    def test_clase_resolucion_y_escala_mm_se_definen_en_pelicula_py_y_el_motor_las_reexporta(self, nombre):
        assert _definiciones(nombre) == ["pelicula.py"]
        assert getattr(motor, nombre) is getattr(_pel(), nombre), "el motor las re-exporta con el mismo nombre (una sola funcion)"

    def test_escala_mm_y_clase_resolucion_siguen_dando_lo_de_siempre_desde_su_nueva_casa(self):
        P = motor.PARAMETROS
        pel = _pel()
        assert [pel.clase_resolucion(d, P) for d in (None, 600.0, 599.999, 96.012, 72.0, 300.0)] == ["sin_dato", "coincide", "coincide", "editor", "editor", "otra"]
        assert pel.escala_mm(600.0, P) == 25.4 / 600.0 and pel.escala_mm(96.012, P) == 25.4 / 600.0 and pel.escala_mm(300.0, P) is None

    def test_solo_pelicula_py_lee_la_resolucion_declarada_y_abre_la_imagen_con_pillow(self):
        """El motor, el servicio y la pagina no leen `resolucion_declarada` ni abren la imagen con Pillow: eso es de `leer_pelicula` (corolario 1)."""
        archivos = {"motor": "analisisImagenes/posicion_inicial_braqui.py", "servicio": "services/posicion_inicial_braqui.py",
                    "pagina": "ui/paginasControles/PruebasMensuales/posicion_inicial_braqui.py"}
        for etiqueta, ruta in archivos.items():
            arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
            nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
            assert "resolucion_declarada" not in nombres, etiqueta
            llamadas_open = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "open"
                             and isinstance(n.func.value, ast.Name) and n.func.value.id == "Image"]
            if etiqueta != "pagina":           # la pagina abre Pillow solo para ROTULAR el formato (`formato_de_la_imagen`, "TIFF (extension .jpeg)"): observado y no tocado
                assert llamadas_open == [], f"{etiqueta}: abre la imagen con Pillow"
        assert "resolucion_declarada" in (RAIZ / "analisisImagenes" / "pelicula.py").read_text(encoding="utf-8")

    def test_el_motor_no_decodifica_el_archivo_del_usuario_solo_su_propia_placa_sintetica(self):
        """Ninguna funcion del motor pide `IMREAD_*` salvo `placa_sintetica` (decodifica el JPEG que ella misma acaba de codificar)."""
        arbol = ast.parse((RAIZ / "analisisImagenes" / "posicion_inicial_braqui.py").read_text(encoding="utf-8"))
        funciones = [n for n in arbol.body if isinstance(n, ast.FunctionDef)]
        assert len(funciones) >= 15
        con_imread = sorted(f.name for f in funciones if any(isinstance(n, ast.Attribute) and n.attr.startswith("IMREAD_") for n in ast.walk(f)))
        assert con_imread == ["placa_sintetica"], con_imread

    def test_leer_imagen_delega_en_leer_pelicula(self):
        arbol = ast.parse((RAIZ / "analisisImagenes" / "posicion_inicial_braqui.py").read_text(encoding="utf-8"))
        leer = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "leer_imagen")
        assert "leer_pelicula" in {n.id for n in ast.walk(leer) if isinstance(n, ast.Name)}


# ====================================================================================================================== §9 la pagina

def _escena16(rgb, tmp_path, nombre="placa16.tif"):
    """La escena como TIFF de 16 bits (x 257 + 3, NO multiplos de 257: cada nivel lleva decimales) con la fecha del escaneo dentro de los 7 dias del cambio."""
    base = rgb.astype(np.uint16) * 257 + 3
    ruta = tmp_path / nombre
    ruta.write_bytes(_tiff(base, datetime="2026:09:30 10:00:00"))
    return str(ruta), base


class TestLaPaginaMuestraLos16BitsEnUint8:
    def test_b_la_pagina_muestra_la_de_16_bits_en_uint8_con_sus_niveles_de_8_bits_redondeados(self, fabrica, dialogos, placa, rgb, tmp_path):
        p = fabrica()
        ruta, base = _escena16(rgb, tmp_path)
        _cargar(p, dialogos, ruta)
        assert p.estado == "imagen" and not dialogos.de("warning")
        mostrada = p.eje_imagen.images[0].get_array()
        assert mostrada.dtype == np.uint8 and mostrada.shape == (672, 1156, 3), "un RGB en float32 de 0 a 255 sale casi todo blanco en imshow"
        # B.8 (DA-88, clase b): la pestana «Imagen» muestra la pelicula A COLOR, la original: cada canal es el nivel de 8 bits REDONDEADO de esa capa de 16 bits (antes esta prueba fijaba el GRIS de 16 bits
        # redondeado en los tres canales, que es lo que el fisico pidio cambiar). Lo demas (uint8, la forma, `nearest`) no cambia.
        esperado = np.clip(np.rint(base.astype(np.float64) * 255.0 / 65535.0), 0, 255).astype(np.uint8)
        assert np.array_equal(mostrada, esperado)
        assert not (np.array_equal(mostrada[:, :, 0], mostrada[:, :, 1]) and np.array_equal(mostrada[:, :, 1], mostrada[:, :, 2])), "la imagen no se ve en gris"
        assert p.eje_imagen.images[0].get_interpolation() == "nearest"

    def test_b_la_pagina_analiza_la_de_16_bits_igual_que_el_servicio(self, fabrica, dialogos, placa, rgb, tmp_path):
        p = fabrica()
        ruta, base = _escena16(rgb, tmp_path)
        _cargar(p, dialogos, ruta)
        _marcar(p, placa.clics)
        assert p.estado == "analizada"
        esperado = svc.analizar_imagen(Path(ruta).read_bytes(), placa.clics)
        for capa in ("gris", "R", "G", "B"):
            assert p._resultado["perfiles"][capa]["desfase_px"] == esperado["perfiles"][capa]["desfase_px"], capa
        assert p._resultado["perfiles"]["G"]["desfase_px"] == pytest.approx(placa.verdad.desfase_px, abs=0.25)

    def test_b_al_abrir_un_registro_guardado_con_16_bits_la_imagen_tambien_sale_en_uint8(self, fabrica, dialogos, placa, rgb, tmp_path, bd):
        p = fabrica()
        ruta, _ = _escena16(rgb, tmp_path)
        _cargar(p, dialogos, ruta)
        _marcar(p, placa.clics)
        p.boton_guardar.click()
        assert p.estado == "registro"
        fila = _consulta(bd, "SELECT id, version_algoritmo, fecha FROM braqui_posicion_inicial")
        assert len(fila) == 1 and fila[0][1] == "PI-2" and fila[0][2] == CAMBIO
        p.boton_recalcular.click()
        assert p.abrir_registro(fila[0][0]) is True and p.estado == "registro"
        mostrada = p.eje_imagen.images[0].get_array()
        assert mostrada.dtype == np.uint8 and mostrada.shape == (672, 1156, 3)
        assert not [c for c in dialogos.de("warning")], "lo recalculado coincide con lo guardado: sin aviso"

    def test_c_una_imagen_con_zonas_transparentes_se_carga_sin_avisos(self, fabrica, dialogos, tmp_path):
        """Era el segundo caso de `test_21` (HEAD: aviso 'transparentes' y la pagina queda igual). Con P11 se mide: la pagina la carga."""
        p = fabrica()
        rgba = np.zeros((40, 40, 4), np.uint8)
        rgba[..., :3] = 128
        rgba[:20, :, 3] = 255                      # la mitad transparente
        ruta = tmp_path / "con_transparencia.png"
        Image.fromarray(rgba).save(ruta)
        _cargar(p, dialogos, str(ruta))
        assert p.estado == "imagen" and dialogos.de("warning") == []
        assert p.eje_imagen.images[0].get_array().shape == (40, 40, 3)
