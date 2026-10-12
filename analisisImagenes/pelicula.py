"""A.1 (PLAN_ANALISIS_PELICULAS_08-10.md): el LECTOR único de las películas radiocrómicas escaneadas -- 8 o 16 bits por canal, capas con nombre
y el alfa como "sin dato" -- y las dos funciones que dicen qué escala tiene lo que el archivo declara.

Lo usan los dos análisis de película (la posición inicial de braquiterapia desde ya; el mensual de aceleradores en C.1-C.3): UNA operación, UNA definición.

QUÉ SE LEE. `leer_pelicula(datos)` decodifica los BYTES del archivo (no una ruta: `cv2.imread` no abre rutas con tildes en Windows y la imagen se guarda
en la base como bytes) y devuelve una `Pelicula`. Los PÍXELES siempre salen de OpenCV; lo que el archivo DECLARA (resolución, fecha del escaneo, formato y si
trae alfa) sale de Pillow, que NO lee los 16 bits (abre un TIFF RGBA de 16 bits como RGBA de 8) pero sí sus etiquetas.
  - 8 bits: los arreglos son EXACTAMENTE los de siempre (`IMREAD_GRAYSCALE` para el gris e `IMREAD_COLOR` para el color; el gris de un JPEG a color no es
    `cvtColor` del color, por eso son dos lecturas), uint8, sin cambiar un valor.
  - 16 bits: `IMREAD_UNCHANGED`; el gris es `cvtColor(BGR2GRAY)` del de 16 bits. Una página completa de 16 bits (202 MB) pasa por `en_bgr()` con un pico de unos 0.8 GB.
  - Las capas `R`, `G`, `B` y el `gris` se entregan en float32 y en "NIVELES DE 8 BITS" (valor x 255 / máximo del tipo), para que los umbrales que ya existen
    sigan valiendo y los 16 bits conserven sus decimales: 65535 es 255.0, 257 es 1.0 y 34567 es 134.5, no 135. Se construyen al pedirlas (una vez) y no al leer: una
    página completa del escáner (6600 x 5100) ocupa unos 135 MB leída y cuatro planos float32 serían 540 MB más que nadie pidió.
  - El orden de canales de OpenCV es B, G, R: aquí se llaman por su nombre (`pelicula.R` es el rojo) y `en_bgr()` entrega el color en el orden que el motor de la
    posición inicial espera (`color[:, :, 0]` es el azul).
  - La orientación EXIF se ignora (JPEG y PNG), para que lo recalculado al abrir un registro no dependa de ese valor por defecto de OpenCV. Observado y no
    tocado: OpenCV 4.11 aplica SIEMPRE la etiqueta de orientación de un TIFF aunque se le pida ignorarla; los escáneres Epson no la escriben, y lo que decodifica
    es lo mismo cada vez que se abre el mismo archivo.
  - ALFA: píxeles con alfa < máximo del tipo (255 o 65535) son "sin dato": `validos` los marca en False y `transparentes` los cuenta. No son película ni fondo; el
    análisis los trata como el marco del escáner. Un alfa de máximo - 1 NO es opaco. Ya no se rechaza la imagen (antes: `ValueError`): si la transparencia toca lo que
    se mide, el análisis dice "no medible" con su motivo. Sin alfa, `validos` es todo True.

Sin Qt y sin base de datos."""
import io
import re
from datetime import date
from functools import cached_property

import cv2
import numpy as np
from PIL import Image

from analisisImagenes.resolucion_imagen import resolucion_declarada

# Las tres capas de color de la película. `NOMBRE_DE_CAPA` es la ÚNICA definición de cómo se nombra la capa reportada (en los menús «Capa reportada» de
# las dos ventanas, en la tabla de registros y en los PDF).
CAPAS = ("R", "G", "B")
NOMBRE_DE_CAPA = {"R": "rojo", "G": "verde", "B": "azul"}
# La capa con que ARRANCAN los menús «Capa reportada» de las dos ventanas (la posición inicial, B.7, y el mensual, E.1). Es solo el valor inicial del menú: la
# elige el físico y cada registro guarda cuál guardó. NINGÚN PDF la lee: cada PDF imprime la capa que guardó su registro (antes se llamó `CAPA_REPORTADA` y
# `CAPA_DEL_PDF`; un test impide que un PDF la importe).
CAPA_POR_OMISION = "G"

NO_SE_RECONOCE = "No se reconoce el formato de la imagen."
_SIN_ORIENTACION = cv2.IMREAD_IGNORE_ORIENTATION


# ----------------------------------------------------------------------------- la escala que dice una resolución

def clase_resolucion(dpi, P):
    """Qué es la resolución que el archivo declara frente a la del procedimiento (`resolucion_escaneo_dpi`):
    "coincide" (600, 599.999, 599), "sin_dato" (no declara), "editor" (72 o 96: lo que un editor escribe al guardar un
    recorte, no una resolución de escaneo) u "otra" (300, 200, 1200...: ningún editor escribe eso; es un escaneo a
    otra resolución)."""
    if not dpi:
        return "sin_dato"
    tolerancia = P["tolerancia_dpi_relativa"]
    escaneo = P["resolucion_escaneo_dpi"]
    if abs(dpi - escaneo) <= tolerancia * escaneo:
        return "coincide"
    if any(abs(dpi - v) <= tolerancia * v for v in P["resoluciones_de_editor_dpi"]):
        return "editor"
    return "otra"


def escala_mm(dpi, P):
    """Milímetros por píxel, o None si NO hay escala que dar. Es el ÚNICO lugar donde una resolución se vuelve
    escala (nadie más calcula 25.4 / dpi), y la escala es SIEMPRE la del procedimiento de escaneo
    (`resolucion_escaneo_dpi`, 600 dpi), nunca la que declara el archivo: Paint reescribe la resolución declarada
    (96) al recortar, sin remuestrear. Solo con una resolución "otra" (declarada y que ningún editor escribe) no hay
    escala: es un escaneo a otra resolución y los milímetros saldrían falsos."""
    if clase_resolucion(dpi, P) == "otra":
        return None
    return 25.4 / P["resolucion_escaneo_dpi"]


# ----------------------------------------------------------------------------- lo que el archivo declara (Pillow)

_FECHA_EXIF = re.compile(r"^\s*(\d{4})[:\-/](\d{2})[:\-/](\d{2})")


def _fecha_de_texto(valor):
    """'2026:09:30 16:12:29' (formato EXIF) -> date(2026, 9, 30); None si no se puede leer."""
    if isinstance(valor, bytes):
        valor = valor.decode("ascii", "ignore")
    if not isinstance(valor, str):
        return None
    coincidencia = _FECHA_EXIF.match(valor)
    if coincidencia is None:
        return None
    try:
        return date(int(coincidencia.group(1)), int(coincidencia.group(2)), int(coincidencia.group(3)))
    except ValueError:
        return None


def _fecha_del_escaneo(imagen_pil):
    """Fecha en que el escáner escribió la imagen (EXIF), o None si no la trae. Prefiere la fecha de
    captura (DateTimeOriginal, luego DateTimeDigitized) a `DateTime`, que un editor puede reescribir;
    el Epson WF-6590 solo escribe `DateTime`."""
    exif = imagen_pil.getexif()
    try:
        interno = exif.get_ifd(0x8769)
    except Exception:
        interno = {}
    for origen, etiqueta in ((interno, 36867), (interno, 36868), (exif, 306)):
        fecha = _fecha_de_texto(origen.get(etiqueta))
        if fecha is not None:
            return fecha
    return None


def _declara_alfa(imagen_pil):
    """True si el archivo dice que puede traer transparencia: un modo con canal alfa (RGBA, LA, PA) o una transparencia de paleta o de color clave."""
    return imagen_pil.mode in ("RGBA", "LA", "PA") or "transparency" in imagen_pil.info


# ----------------------------------------------------------------------------- la película

def _a_niveles_de_8_bits(plano, maximo):
    """valor x 255 / maximo del tipo, en float32. En 8 bits es el valor sin tocar. En 16 bits el producto (hasta 16 711 425) cabe exacto en float32 (menos de
    2**24) y la división es la correctamente redondeada: la mejor aproximación float32 de x * 255 / 65535."""
    niveles = plano.astype(np.float32)
    if maximo != 255:
        niveles *= np.float32(255.0)
        niveles /= np.float32(maximo)
    return niveles


class Pelicula:
    """Una película leída. Solo lectura: nadie modifica sus arreglos.

    `R`, `G`, `B`, `gris`: float32 (alto, ancho) en niveles de 8 bits (ver el docstring del módulo). `bits`: 8 o 16. `validos`: bool (alto, ancho), alfa == máximo
    (todo True si no hay alfa). `transparentes`: cuántos píxeles no son válidos. `dpi`: la resolución que el ARCHIVO declara (None si no la trae). `fecha_escaneo`:
    `datetime.date` o None. `formato`: el de Pillow ('JPEG', 'TIFF', 'PNG'...)."""

    def __init__(self, bgr, gris, alfa, maximo, dpi, fecha_escaneo, formato):
        self._bgr = bgr                  # (alto, ancho, 3) del tipo nativo en el orden de OpenCV (B, G, R); None si la fuente es en grises (solo 16 bits)
        self._gris = gris                # (alto, ancho) del tipo nativo
        self._alfa = alfa                # (alto, ancho) del tipo nativo, o None
        self._maximo = maximo            # 255 o 65535
        self.bits = 8 if maximo == 255 else 16
        self.dpi = dpi
        self.fecha_escaneo = fecha_escaneo
        self.formato = formato
        self.transparentes = 0 if alfa is None else int(np.count_nonzero(alfa != maximo))

    @cached_property
    def gris(self):
        return _a_niveles_de_8_bits(self._gris, self._maximo)

    def _capa(self, indice_bgr):
        if self._bgr is None:                       # fuente en grises de 16 bits: las tres capas valen lo mismo
            return self.gris.copy()
        return _a_niveles_de_8_bits(self._bgr[:, :, indice_bgr], self._maximo)

    @cached_property
    def R(self):
        return self._capa(2)

    @cached_property
    def G(self):
        return self._capa(1)

    @cached_property
    def B(self):
        return self._capa(0)

    @cached_property
    def validos(self):
        if self._alfa is None:
            return np.ones(self._gris.shape, bool)
        return self._alfa == self._maximo

    def en_bgr(self):
        """(gris, color) en la forma que espera el motor de la posición inicial. En 8 bits son los MISMOS arreglos uint8 de siempre (gris de `IMREAD_GRAYSCALE`,
        color BGR de `IMREAD_COLOR`); en 16 bits, float32 en niveles de 8 bits (gris y color BGR (alto, ancho, 3)).

        En 16 bits el color sale en UN solo arreglo, convertido de una vez desde el nativo (B, G, R): no se pasa por los planos `B`, `G` y `R` ni por un `np.dstack` que
        los copie (R1-G-05). Una página completa del escáner (6600 x 5100) ocupaba 1.4 GB de pico leída así (los tres planos, cacheados en la `Pelicula`, y su copia, 405 MB
        cada uno); ahora el pico es de 0.8 GB: el nativo (202 MB), su gris (67 MB), el gris en flotante (135 MB) y el color en flotante (405 MB). Cada valor es el mismo, bit a
        bit, que el del plano de su capa. El piso que queda es el del diseño (el motor recibe la página entera en flotante): convertir solo la ventana sería otro cambio."""
        if self.bits == 8:
            return self._gris, self._bgr
        if self._bgr is None:                       # fuente en grises de 16 bits: las tres capas valen lo mismo
            return self.gris, np.dstack((self.gris,) * 3)
        return self.gris, _a_niveles_de_8_bits(self._bgr, self._maximo)


def _abrir_con_pillow(datos):
    try:
        return Image.open(io.BytesIO(datos))
    except Exception:
        return None


def _plano_alfa(sin_cambios, imagen_pil, maximo):
    """El alfa en el tipo nativo, o None si el archivo no declara alfa. Sale de OpenCV (su cuarto canal, con los 16 bits completos) y, si OpenCV no lo entrega
    pero Pillow dice que hay transparencia (una clave de color en una imagen de grises), de Pillow (8 bits). Si el archivo declara transparencia y no hay
    forma de leerla, se rechaza: lo transparente nunca se toma por película."""
    if imagen_pil is not None:
        declara = _declara_alfa(imagen_pil)
    else:
        declara = sin_cambios.ndim == 3 and sin_cambios.shape[2] == 4
    if not declara:
        return None
    if sin_cambios.ndim == 3 and sin_cambios.shape[2] == 4:
        return sin_cambios[:, :, 3]
    if maximo == 255 and imagen_pil is not None:
        try:
            return np.array(imagen_pil.convert("RGBA").getchannel("A"))
        except Exception:
            pass
    raise ValueError("La imagen declara transparencia que no se puede leer: guardela sin transparencia.")


def leer_pelicula(datos):
    """Bytes del archivo tal como se subió -> `Pelicula`. `ValueError` si no se reconoce el formato, si no es de 8 o 16 bits por canal o si declara una
    transparencia que no se puede leer. Una imagen con zonas transparentes NO se rechaza: se lee y `validos` las marca."""
    if not len(datos):
        raise ValueError(NO_SE_RECONOCE)
    arreglo = np.frombuffer(datos, np.uint8)
    sin_cambios = cv2.imdecode(arreglo, cv2.IMREAD_UNCHANGED | _SIN_ORIENTACION)
    if sin_cambios is None:
        raise ValueError(NO_SE_RECONOCE)
    if sin_cambios.dtype == np.uint8:
        maximo = 255
    elif sin_cambios.dtype == np.uint16:
        maximo = 65535
    else:
        raise ValueError(f"La imagen es de {sin_cambios.dtype}: solo se leen imagenes de 8 o 16 bits por canal.")
    imagen_pil = _abrir_con_pillow(datos)
    dpi = None
    fecha_escaneo = None
    formato = ""
    if imagen_pil is not None:
        formato = imagen_pil.format or ""
        try:
            dpi = resolucion_declarada(imagen_pil)
        except Exception:
            dpi = None
        try:
            fecha_escaneo = _fecha_del_escaneo(imagen_pil)
        except Exception:
            fecha_escaneo = None
    alfa = _plano_alfa(sin_cambios, imagen_pil, maximo)
    if maximo == 255:
        # EXACTAMENTE los arreglos de siempre: el gris de `IMREAD_GRAYSCALE` (en un JPEG a color es la luma, no `cvtColor` del color) y el color de `IMREAD_COLOR`
        alfa = None if alfa is None else alfa.copy()
        del sin_cambios
        gris = cv2.imdecode(arreglo, cv2.IMREAD_GRAYSCALE | _SIN_ORIENTACION)
        bgr = cv2.imdecode(arreglo, cv2.IMREAD_COLOR | _SIN_ORIENTACION)
        if gris is None or bgr is None:
            raise ValueError(NO_SE_RECONOCE)
    else:
        canales = 1 if sin_cambios.ndim == 2 else sin_cambios.shape[2]
        if canales == 1:
            gris, bgr = sin_cambios, None
        elif canales == 3:
            gris, bgr = cv2.cvtColor(sin_cambios, cv2.COLOR_BGR2GRAY), sin_cambios
        elif canales == 4:
            gris, bgr = cv2.cvtColor(sin_cambios, cv2.COLOR_BGRA2GRAY), sin_cambios[:, :, :3]
        else:
            raise ValueError(f"La imagen tiene {canales} canales: solo se leen imagenes en grises, RGB o RGBA.")
    return Pelicula(bgr, gris, alfa, maximo, dpi, fecha_escaneo, formato)
