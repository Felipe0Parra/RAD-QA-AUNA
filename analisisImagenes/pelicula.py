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

EL PISO (A.2, 12-10). `piso_de_pelicula(pelicula, campo_luz, P, punto_manual=None)` dice cuál es el nivel de la película FUERA del campo luminoso, de dónde lo sacó y a qué distancia
del campo: el 50 % del borde de radiación es el 50 % entre ese piso y la meseta, así que de él depende el FWHM. Una sola función para las cuatro capas (R, G, B y el gris). Se
llama «piso» y no «película virgen»: la película de fuera del campo recibe dosis periférica y se sigue aclarando con la distancia (R7, H18), por eso se toma LO MÁS LEJOS POSIBLE
del campo y se dice a qué distancia. Reglas (los valores están en `PARAMETROS_DEL_PISO`, con nombre, unidad y motivo):
  (1) máscara de película = `validos` y no fondo (el fondo es casi blanco en las tres capas) y la componente conexa más grande, erosionada `margen_borde_mm` de todo lo que no es película
      (fondo, píxeles sin dato). El borde de la IMAGEN no se erosiona: un recorte a ras corta la película, que sigue más allá. «Fondo» es un umbral FIJO, `umbral_fondo` (235): el fondo de las diez
      páginas reales es 255 y la capa más oscura del piso de la película va de 73 a 86, así que del lado de la película el margen es de 149 niveles y del lado del fondo de 20 solamente (NO es
      un margen amplio a los dos lados). Un fondo por debajo de 235 (otro escáner, un vidrio sucio, la tapa abierta) contaría como película y el piso saldría del vacío: de eso se ocupa la regla (7);
  (2) región = lo de la máscara a más de `margen_campo_mm` del cuadrilátero luminoso y, de eso, la fracción `fraccion_lejana` más lejana;
  (3) tinta: fuera los píxeles que estén por debajo de la mediana de la región en más de `delta_tinta` niveles en alguna capa (R, G o B);
  (4) al menos `pixeles_minimos` píxeles, o «no medible: no hay película suficiente fuera del campo»;
  (5) coherencia: en cada capa el piso más claro que la meseta (la mediana de la película dentro del campo, a más de `margen_campo_mm` de sus lados) en al menos `contraste_minimo`
      niveles; la capa que no lo cumple es «no medible» y las demás siguen;
  (6) con `punto_manual` (el sexto clic, sobre un trozo sin irradiar escaneado junto) el piso es la mediana de un cuadrado de `lado_punto_manual_mm` centrado en el punto, con las
      reglas (3) a (5): ese trozo es OTRA componente conexa, así que la regla de la componente más grande es solo de la región automática;
  (7) el piso no puede parecerse al fondo del escáner (A2-R1-02, 12-10: DECISIÓN DE DISEÑO DE OPUS ante un obstáculo que el plan no preveía, VETABLE POR EL FÍSICO). Va ANTES de la meseta y vale para
      los dos orígenes (región automática y sexto clic), sobre los píxeles finales de la región (después de la tinta): con la capa MÁS OSCURA de cada píxel (el mínimo de R, G y B: la misma definición
      de fondo que la regla 1, a otro nivel), si la fracción `fraccion_como_fondo` (10 %) o más de ellos llega a `umbral_como_fondo` (170 niveles), TODO el piso es «no medible: el piso es tan claro
      como el fondo del escáner, no como película (el N % de sus píxeles llega a 170 niveles hasta en su capa más oscura): revise la tapa y el vidrio del escáner y que el escaneo no lleve ajustes de
      brillo»: las cuatro capas sin número y sin región, como cuando no hay película suficiente. Es una guarda por FRACCIÓN y no por mediana: un fondo que se cuela en las esquinas de un recorte suelto
      (en la sintética de PF.0, el 25 % del piso con un giro de 0.4 grados y el 47 % con 0.9) sube la mediana 1 a 3 niveles sin que la mediana lo note. Las películas reales no pierden nada: de sus
      píxeles, del 0 al 0.6 % llega a 170.
      LÍMITE DECLARADO: un fondo NEUTRO por debajo de 170 no se distingue de la película (en una página sale a unos 20 mm del campo; se ve en la región del piso dibujada, E.1).
CONTRATO de las entradas: `pelicula` es una `Pelicula` o cualquier objeto con `R`, `G`, `B`, `gris` (float32 en niveles de 8 bits), `validos` (bool) y `dpi`; `campo_luz` son las 4 esquinas del
campo luminoso como (x, y) en PÍXELES de esos arreglos (x = columna, y = fila; el centro del primer píxel es (0, 0)), en cualquier orden, formando un cuadrilátero convexo; `P` trae la escala
del procedimiento (`resolucion_escaneo_dpi`, `resoluciones_de_editor_dpi` y `tolerancia_dpi_relativa`) y, si quiere cambiarlos, los parámetros del piso (los que falte los pone de fábrica).
Lo que no se puede medir NO lanza: el resultado dice «no medible» con su motivo; solo una forma equivocada de los argumentos (el campo que no son 4 puntos, un `P` sin la escala) es
un `ValueError`. Los motivos son TEXTOS y alguno lleva cifras (el de la regla 7): quien los consume pregunta `estado != "ok"` o `startswith("no medible")`, nunca compara con una lista cerrada.

Sin Qt y sin base de datos."""
import io
import re
from dataclasses import dataclass, field
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


# ============================================================================= A.2: el piso (nivel de la película fuera del campo luminoso)

CAPAS_DEL_PISO = CAPAS + ("gris",)                       # el piso se da de las tres capas y del gris (C.2 mide las cuatro)
_NOMBRE_DE_LA_CAPA_DEL_PISO = dict(NOMBRE_DE_CAPA, gris="gris")
CLAVES_DE_LA_ESCALA = ("resolucion_escaneo_dpi", "resoluciones_de_editor_dpi", "tolerancia_dpi_relativa")      # lo que `escala_mm` le pide a `P`
FILAS_POR_BLOQUE = 256                                    # las operaciones por píxel de una página completa se hacen por bloques de filas: sin temporales de 135 MB

# Los parámetros del piso, cada uno con su nombre, su unidad y su motivo (PD1: lo que decide un número vive escrito, no en el código). `VALORES_DEL_PISO` es el diccionario plano
# que se le pasa a la función dentro de `P` (el `PARAMETROS` de C.1 lo incluye).
PARAMETROS_DEL_PISO = {
    "umbral_fondo": {
        "valor": 235.0, "unidad": "nivel (0 a 255)",
        "motivo": "Un píxel es fondo del escáner si hasta su capa más oscura llega a 235: el fondo es casi blanco en las tres capas (255 en las páginas reales) y la capa más oscura del "
                  "piso de la película va de 73 a 86 en las diez reales. Del lado de la película el margen es de 149 niveles, pero del lado del fondo es de 20: un fondo por debajo de 235 "
                  "(otro escáner, un vidrio sucio, la tapa abierta) se tomaría por película, y de eso se ocupa la regla (7) con `umbral_como_fondo` y `fraccion_como_fondo`, no este umbral."},
    "margen_borde_mm": {
        "valor": 0.5, "unidad": "mm",
        "motivo": "El borde de la película (el corte, la mezcla con el fondo que deja la compresión JPEG) no es película limpia: se aparta medio milímetro hacia adentro de todo lo que no es "
                  "película. El borde de la imagen no cuenta: un recorte a ras corta la película, que sigue más allá."},
    "margen_campo_mm": {
        "valor": 5.0, "unidad": "mm",
        "motivo": "La película pegada al campo recibe la penumbra y la dispersión del haz; a menos de 5 mm del cuadrilátero luminoso no se toma el piso (R7, H18). Es también la distancia "
                  "a los lados del campo desde la que se toma la meseta de referencia de la comprobación de coherencia."},
    "fraccion_lejana": {
        "valor": 0.20, "unidad": "fracción",
        "motivo": "De la película a más de 5 mm del campo se toma el 20 % más lejano: la película de fuera del campo no es virgen, recibe dosis periférica y se sigue aclarando con la "
                  "distancia (R7: en ML0 el verde pasa de 159 a 175 entre 5 y 9 mm), así que el piso se toma lo más lejos posible y se dice a qué distancia."},
    "delta_tinta": {
        "valor": 25.0, "unidad": "niveles",
        "motivo": "Un píxel que esté más de 25 niveles por debajo de la mediana de la región, en el rojo, el verde o el azul, es tinta (el rótulo, las diagonales pintadas) y no cuenta: "
                  "25 es mucho más que el ruido del escáner (1.5) y que la dispersión de la película. Aparta también la cola oscura del gradiente del rojo, con efecto de 2 niveles o menos "
                  "sobre la mediana (A.2, logs/A2/explorar_tinta.log)."},
    "pixeles_minimos": {
        "valor": 2000, "unidad": "píxeles",
        "motivo": "Con menos de 2000 píxeles (3.6 mm² a 600 dpi) la mediana no es estable ni distingue una mota de un nivel de piso: se prefiere decir «no medible»."},
    "contraste_minimo": {
        "valor": 10.0, "unidad": "niveles",
        "motivo": "Sin al menos 10 niveles entre el piso y la meseta, la normalización (piso - valor)/(piso - meseta) divide el ruido (1.5 por píxel) por una diferencia casi nula: esa capa "
                  "no se puede normalizar y se declara «no medible»."},
    "lado_punto_manual_mm": {
        "valor": 3.0, "unidad": "mm",
        "motivo": "El sexto clic toma un cuadrado de 3 × 3 mm (71 × 71 píxeles a 600 dpi) centrado en el punto: bastante para una mediana estable y menor que un trozo de película "
                  "escaneado junto al campo."},
    "umbral_como_fondo": {
        "valor": 170.0, "unidad": "nivel (0 a 255)",
        "motivo": "Un píxel del piso cuya capa más oscura llega a 170 es tan claro como el fondo de un escáner, no como película: en las diez películas reales la mediana de la capa más "
                  "oscura del piso está entre 73 y 86 (en grises, 138) y el fondo en 255; 170 es la mitad de esa brecha. Un fondo neutro por debajo de 170 no se distingue así "
                  "(límite declarado; se ve en la región del piso dibujada)."},
    "fraccion_como_fondo": {
        "valor": 0.10, "unidad": "fracción",
        "motivo": "Si el 10 % o más de los píxeles del piso llega a `umbral_como_fondo`, no se toma piso: en las películas reales esos píxeles (motas claras) son del 0 al 0.6 %; un fondo "
                  "gris que se cuela en las esquinas de un recorte no mueve la mediana hasta el 13.9 % y la sube 1 a 3 niveles desde el 19 % (medido el 12-10)."},
}
VALORES_DEL_PISO = {nombre: parametro["valor"] for nombre, parametro in PARAMETROS_DEL_PISO.items()}

MOTIVO_SIN_PISO = "no medible: no hay película suficiente fuera del campo"
MOTIVO_PUNTO_FUERA_DE_PELICULA = "no medible: el punto no está sobre película"
MOTIVO_POCA_PELICULA_EN_EL_PUNTO = "no medible: no hay película suficiente alrededor del punto"
MOTIVO_CAMPO_INVALIDO = "no medible: el campo luminoso no forma un cuadrilátero convexo"
MOTIVO_SIN_PELICULA = "no medible: no hay película en la imagen (todo es fondo del escáner o no tiene dato)"
MOTIVO_SIN_MESETA = "no medible: la película no cubre el campo luminoso, así que no se puede comprobar el contraste con la meseta"
# Regla (7): es el comienzo del `estado` (lleva detrás, entre paréntesis, el porcentaje de píxeles del piso que llegan a `umbral_como_fondo` y el umbral, y qué revisar).
MOTIVO_PISO_COMO_EL_FONDO = "no medible: el piso es tan claro como el fondo del escáner, no como película"


@dataclass(frozen=True)
class CapaDelPiso:
    """El piso de UNA capa. `estado`: «ok» o «no medible: <motivo>». `mediana`: el nivel de piso (niveles de 8 bits) o None; `n`: los píxeles en que se basa (los mismos en las cuatro
    capas); `iqr`: la dispersión (rango intercuartílico); `meseta`: la mediana de la película dentro del campo luminoso, la referencia de la comprobación de coherencia; `contraste` =
    mediana - meseta (se informa aunque la capa sea «no medible» por ese motivo: es lo que lo explica)."""
    capa: str
    estado: str
    mediana: float | None = None
    n: int = 0
    iqr: float | None = None
    meseta: float | None = None
    contraste: float | None = None


@dataclass(frozen=True, eq=False)
class RegionDelPiso:
    """DE DÓNDE salió el piso. `caja`: (x0, y0, x1, y1) en píxeles de la película, x1 e y1 exclusivos; `mascara`: bool (y1 - y0, x1 - x0), solo lectura, los píxeles usados; `n` cuántos;
    y la distancia al cuadrilátero luminoso de esos píxeles en mm (media, mínima, máxima). `origen`: «automatico» o «manual» (el sexto clic)."""
    origen: str
    caja: tuple
    mascara: np.ndarray = field(repr=False)
    n: int
    distancia_media_mm: float
    distancia_minima_mm: float
    distancia_maxima_mm: float


@dataclass(frozen=True, eq=False)
class Piso:
    """El piso de una película: `estado` («ok» si hubo región; si no, «no medible: <motivo>» y ninguna capa trae número), `origen`, `capas` (R, G, B y gris), `region`, `escala_mm`
    (la del procedimiento; None si el archivo declara otra resolución), `campo_luz` (las 4 esquinas con que se midió) y `parametros` (los del piso con que se midió, para guardarlos
    con el análisis). Se llama «piso» y no «película virgen»: la película de fuera del campo recibe dosis periférica (R7)."""
    estado: str
    origen: str
    capas: dict
    region: RegionDelPiso | None
    escala_mm: float | None
    campo_luz: tuple
    parametros: dict

    def valor(self, capa):
        """El nivel de piso de una capa (R, G, B o gris), o None si no se pudo medir."""
        return self.capas[capa].mediana

    @property
    def todas_medibles(self):
        return self.estado == "ok" and all(c.estado == "ok" for c in self.capas.values())

    def descripcion(self):
        """Una frase que dice de dónde salió el piso (y qué capas no se pudieron medir). Sin símbolos de correcto o incorrecto (DA-18)."""
        if self.estado != "ok" or self.region is None:
            return self.estado
        r = self.region
        if self.origen == "manual":
            lado = self.parametros["lado_punto_manual_mm"]
            texto = f"Piso tomado en el punto marcado (un cuadrado de {lado:g} × {lado:g} mm, {r.n} píxeles), a {r.distancia_media_mm:.1f} mm del campo luminoso."
        else:
            texto = (f"Piso tomado en {r.n} píxeles de película fuera del campo luminoso, a {r.distancia_media_mm:.1f} mm de él en promedio "
                     f"(de {r.distancia_minima_mm:.1f} a {r.distancia_maxima_mm:.1f} mm). No es película sin irradiar: recibe dosis periférica.")
        sin_piso = [f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]}: {capa.estado}" for c, capa in self.capas.items() if capa.estado != "ok"]
        return texto + ("" if not sin_piso else " " + "; ".join(sin_piso) + ".")

    def como_dict(self):
        """Todo lo que dice el piso en un diccionario de números y textos (sin arreglos): viaja como JSON."""
        region = None
        if self.region is not None:
            r = self.region
            region = {"origen": r.origen, "caja": [int(v) for v in r.caja], "n": int(r.n), "distancia_media_mm": float(r.distancia_media_mm),
                      "distancia_minima_mm": float(r.distancia_minima_mm), "distancia_maxima_mm": float(r.distancia_maxima_mm)}
        return {"estado": self.estado, "origen": self.origen, "escala_mm": None if self.escala_mm is None else float(self.escala_mm),
                "campo_luz": [[float(x), float(y)] for x, y in self.campo_luz], "parametros": dict(self.parametros),
                "capas": {c: {"estado": capa.estado, "mediana": capa.mediana, "n": int(capa.n), "iqr": capa.iqr, "meseta": capa.meseta, "contraste": capa.contraste}
                          for c, capa in self.capas.items()},
                "region": region}


def _piso_sin_numero(motivo, origen, campo, escala, p):
    """Un piso sin número en ninguna capa, con el motivo."""
    return Piso(motivo, origen, {c: CapaDelPiso(c, motivo) for c in CAPAS_DEL_PISO}, None, escala, campo, dict(p))


def _piso_cuadrilatero(campo_luz):
    """(esquinas ordenadas, esquinas tal como llegaron). Las ordenadas son un arreglo (4, 2) float64 en el orden del ángulo alrededor del centroide, o None si no forman un cuadrilátero
    convexo (colineales, repetidas, un punto dentro del triángulo de los otros, una coordenada que no es finita). `ValueError` si lo que llega no son 4 puntos (x, y)."""
    try:
        puntos = np.asarray(campo_luz, dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError("El campo luminoso son 4 esquinas (x, y) en pixeles de la pelicula.") from None
    if puntos.shape != (4, 2):
        raise ValueError(f"El campo luminoso son 4 esquinas (x, y) en pixeles de la pelicula, no un arreglo de forma {puntos.shape}.")
    if not np.isfinite(puntos).all():
        return None, puntos
    centro = puntos.mean(axis=0)
    ordenados = puntos[np.argsort(np.arctan2(puntos[:, 1] - centro[1], puntos[:, 0] - centro[0]), kind="stable")]
    aristas = np.roll(ordenados, -1, axis=0) - ordenados
    giros = aristas[:, 0] * np.roll(aristas[:, 1], -1) - aristas[:, 1] * np.roll(aristas[:, 0], -1)       # producto cruz de aristas consecutivas: el mismo signo en las cuatro si es convexo
    if not (np.all(giros > 1e-9) or np.all(giros < -1e-9)):
        return None, puntos
    return ordenados, puntos


def _piso_punto(punto):
    try:
        a = np.asarray(punto, dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError("El sexto clic es un punto (x, y) en pixeles de la pelicula.") from None
    if a.shape != (2,):
        raise ValueError(f"El sexto clic es un punto (x, y) en pixeles de la pelicula, no un arreglo de forma {a.shape}.")
    return float(a[0]), float(a[1])


def _piso_mascara_de_pelicula(pelicula, umbral_fondo, y0=0, y1=None, x0=0, x1=None):
    """True donde hay película: con dato (`validos`) y que no es fondo (la capa más oscura de las tres llega al umbral del fondo), en la ventana [y0, y1) x [x0, x1)."""
    R, G, B, validos = pelicula.R, pelicula.G, pelicula.B, pelicula.validos
    y1 = validos.shape[0] if y1 is None else y1
    x1 = validos.shape[1] if x1 is None else x1
    salida = np.empty((y1 - y0, x1 - x0), bool)
    for f0 in range(y0, y1, FILAS_POR_BLOQUE):
        f1 = min(y1, f0 + FILAS_POR_BLOQUE)
        mas_oscura = np.minimum(np.minimum(R[f0:f1, x0:x1], G[f0:f1, x0:x1]), B[f0:f1, x0:x1])
        np.logical_and(mas_oscura < umbral_fondo, validos[f0:f1, x0:x1], out=salida[f0 - y0:f1 - y0])
    return salida


def _piso_distancias_al_campo(campo, x0, y0, x1, y1):
    """Para cada píxel de [y0, y1) x [x0, x1): (fuera, dentro) en píxeles. `fuera` es la distancia al cuadrilátero (0 dentro de él); `dentro`, la profundidad hasta el lado más cercano (0 fuera).
    Distancia analítica a los cuatro segmentos; el centro del primer píxel de la película es (0, 0)."""
    aristas = np.roll(campo, -1, axis=0) - campo
    largos = np.hypot(aristas[:, 0], aristas[:, 1])
    sentido = np.sign(aristas[0, 0] * aristas[1, 1] - aristas[0, 1] * aristas[1, 0])             # hacia qué lado de cada arista está el interior
    alto, ancho = y1 - y0, x1 - x0
    fuera = np.empty((alto, ancho), np.float32)
    dentro = np.empty((alto, ancho), np.float32)
    xs = np.arange(x0, x1, dtype=np.float64)[None, :]
    for f0 in range(0, alto, 2 * FILAS_POR_BLOQUE):
        f1 = min(alto, f0 + 2 * FILAS_POR_BLOQUE)
        ys = np.arange(y0 + f0, y0 + f1, dtype=np.float64)[:, None]
        mas_cerca = np.full((f1 - f0, ancho), np.inf)
        menos_profundo = np.full((f1 - f0, ancho), np.inf)
        for i in range(4):
            px, py = xs - campo[i, 0], ys - campo[i, 1]
            t = np.clip((px * aristas[i, 0] + py * aristas[i, 1]) / (largos[i] ** 2), 0.0, 1.0)
            np.minimum(mas_cerca, np.hypot(px - t * aristas[i, 0], py - t * aristas[i, 1]), out=mas_cerca)
            np.minimum(menos_profundo, sentido * (aristas[i, 0] * py - aristas[i, 1] * px) / largos[i], out=menos_profundo)
        es_interior = menos_profundo >= 0
        fuera[f0:f1] = np.where(es_interior, 0.0, mas_cerca)
        dentro[f0:f1] = np.where(es_interior, menos_profundo, 0.0)
    return fuera, dentro


def _piso_meseta_de_referencia(pelicula, campo, escala, p):
    """La mediana, por capa, de la película DENTRO del campo luminoso a más de `margen_campo_mm` de sus lados (la meseta contra la que se comprueba el piso), o None si ahí hay
    menos de `pixeles_minimos` píxeles de película (el campo no está sobre la película)."""
    alto, ancho = pelicula.validos.shape
    x0, x1 = max(0, int(np.floor(campo[:, 0].min()))), min(ancho, int(np.ceil(campo[:, 0].max())) + 1)
    y0, y1 = max(0, int(np.floor(campo[:, 1].min()))), min(alto, int(np.ceil(campo[:, 1].max())) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    _, dentro = _piso_distancias_al_campo(campo, x0, y0, x1, y1)
    interior = dentro * escala > p["margen_campo_mm"]
    interior &= _piso_mascara_de_pelicula(pelicula, p["umbral_fondo"], y0, y1, x0, x1)
    if int(interior.sum()) < p["pixeles_minimos"]:
        return None
    return {c: float(np.median(getattr(pelicula, c)[y0:y1, x0:x1][interior])) for c in CAPAS_DEL_PISO}


def _piso_sin_tinta(pelicula, ys, xs, delta_tinta):
    """Los índices de los píxeles (ys, xs) que NO son tinta: ninguno de R, G o B está por debajo de la mediana de la región en más de `delta_tinta` niveles."""
    tinta = np.zeros(len(ys), bool)
    for c in CAPAS:
        valores = getattr(pelicula, c)[ys, xs]
        tinta |= valores < np.median(valores) - delta_tinta
    return ~tinta


def _piso_region_automatica(pelicula, campo, escala, p):
    """La región del piso sin que nadie marque nada: (ys, xs, distancias en mm) en coordenadas de la película, o el motivo de «no medible» (un texto)."""
    pel = _piso_mascara_de_pelicula(pelicula, p["umbral_fondo"])
    cuantas, etiquetas, estadisticas, _ = cv2.connectedComponentsWithStats(pel.view(np.uint8), connectivity=8)
    if cuantas < 2:
        return MOTIVO_SIN_PELICULA
    k = 1 + int(np.argmax(estadisticas[1:, cv2.CC_STAT_AREA]))
    x, y, ancho_c, alto_c = (int(v) for v in estadisticas[k, :4])
    alto, ancho = pel.shape
    radio = p["margen_borde_mm"] / escala
    margen = int(np.ceil(radio)) + 2
    x0, y0, x1, y1 = max(0, x - margen), max(0, y - margen), min(ancho, x + ancho_c + margen), min(alto, y + alto_c + margen)
    componente = etiquetas[y0:y1, x0:x1] == k
    del etiquetas, pel
    # la erosion se mide contra todo lo que NO es esta componente dentro de la ventana; el borde de la imagen no cuenta (la pelicula sigue mas alla)
    lejos_del_borde = cv2.distanceTransform(componente.view(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) > radio
    fuera, _ = _piso_distancias_al_campo(campo, x0, y0, x1, y1)
    distancia_mm = fuera * escala
    elegibles = lejos_del_borde & (distancia_mm > p["margen_campo_mm"])
    if not elegibles.any():
        return MOTIVO_SIN_PISO
    corte = np.quantile(distancia_mm[elegibles], 1.0 - p["fraccion_lejana"])
    ys, xs = np.nonzero(elegibles & (distancia_mm >= corte))
    ys, xs = ys + y0, xs + x0
    quedan = _piso_sin_tinta(pelicula, ys, xs, p["delta_tinta"])
    ys, xs = ys[quedan], xs[quedan]
    if len(ys) < p["pixeles_minimos"]:
        return MOTIVO_SIN_PISO
    return ys, xs, distancia_mm[ys - y0, xs - x0]


def _piso_region_manual(pelicula, campo, escala, p, punto):
    """La región del sexto clic: el cuadrado de `lado_punto_manual_mm` centrado en el punto, solo con película (con dato, no fondo, y a más de `margen_borde_mm` del borde de la
    película), sin tinta. Devuelve (ys, xs, distancias en mm) o el motivo de «no medible». No pide la componente conexa más grande: el trozo sin irradiar es otro pedazo."""
    cx, cy = punto
    alto, ancho = pelicula.validos.shape
    if not (np.isfinite(cx) and np.isfinite(cy)):
        return MOTIVO_PUNTO_FUERA_DE_PELICULA
    ix, iy = int(np.floor(cx + 0.5)), int(np.floor(cy + 0.5))
    if not (0 <= ix < ancho and 0 <= iy < alto):
        return MOTIVO_PUNTO_FUERA_DE_PELICULA
    media = p["lado_punto_manual_mm"] / 2.0 / escala
    radio = p["margen_borde_mm"] / escala
    margen = int(np.ceil(radio)) + 2
    x0, x1 = max(0, int(np.floor(cx - media)) - margen), min(ancho, int(np.ceil(cx + media)) + margen + 1)
    y0, y1 = max(0, int(np.floor(cy - media)) - margen), min(alto, int(np.ceil(cy + media)) + margen + 1)
    pel = _piso_mascara_de_pelicula(pelicula, p["umbral_fondo"], y0, y1, x0, x1)
    if not pel[iy - y0, ix - x0]:
        return MOTIVO_PUNTO_FUERA_DE_PELICULA
    lejos_del_borde = cv2.distanceTransform(pel.view(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) > radio
    columnas, filas = np.arange(x0, x1)[None, :], np.arange(y0, y1)[:, None]
    cuadrado = (np.abs(columnas - cx) <= media) & (np.abs(filas - cy) <= media)
    ys, xs = np.nonzero(cuadrado & pel & lejos_del_borde)
    ys, xs = ys + y0, xs + x0
    if len(ys):
        quedan = _piso_sin_tinta(pelicula, ys, xs, p["delta_tinta"])
        ys, xs = ys[quedan], xs[quedan]
    if len(ys) < p["pixeles_minimos"]:
        return MOTIVO_POCA_PELICULA_EN_EL_PUNTO
    fuera, _ = _piso_distancias_al_campo(campo, x0, y0, x1, y1)
    return ys, xs, fuera[ys - y0, xs - x0] * escala


def _piso_fraccion_como_fondo(pelicula, ys, xs, umbral):
    """La fracción de los píxeles (ys, xs) cuya capa más oscura (el mínimo de R, G y B) llega a `umbral`: lo que la regla (7) compara con `fraccion_como_fondo`."""
    mas_oscura = np.minimum(np.minimum(pelicula.R[ys, xs], pelicula.G[ys, xs]), pelicula.B[ys, xs])
    return float(np.mean(mas_oscura >= umbral))


def _piso_resultado(pelicula, campo, campo_texto, escala, p, origen, ys, xs, distancias_mm):
    """De los píxeles de la región al `Piso`: la regla (7) (el piso no puede parecerse al fondo del escáner), la meseta de referencia, la mediana y el IQR de cada capa y la comprobación de
    coherencia. La regla (7) va primero: un piso del vacío es MÁS claro que la meseta, y la comprobación de la regla (5) no lo ve."""
    como_fondo = _piso_fraccion_como_fondo(pelicula, ys, xs, p["umbral_como_fondo"])
    if como_fondo >= p["fraccion_como_fondo"]:
        motivo = (f"{MOTIVO_PISO_COMO_EL_FONDO} (el {100 * como_fondo:.0f} % de sus píxeles llega a {p['umbral_como_fondo']:g} niveles hasta en su capa más oscura): "
                  f"revise la tapa y el vidrio del escáner y que el escaneo no lleve ajustes de brillo")
        return _piso_sin_numero(motivo, origen, campo_texto, escala, p)
    meseta = _piso_meseta_de_referencia(pelicula, campo, escala, p)
    if meseta is None:
        return _piso_sin_numero(MOTIVO_SIN_MESETA, origen, campo_texto, escala, p)
    n = int(len(ys))
    capas = {}
    for c in CAPAS_DEL_PISO:
        valores = getattr(pelicula, c)[ys, xs]
        mediana = float(np.median(valores))
        contraste = mediana - meseta[c]
        if contraste < p["contraste_minimo"]:
            motivo = (f"no medible: el piso de la capa {_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} no es más claro que la meseta en al menos {p['contraste_minimo']:g} niveles "
                      f"(piso {mediana:.1f}, meseta {meseta[c]:.1f})")
            capas[c] = CapaDelPiso(c, motivo, None, n, None, meseta[c], contraste)
            continue
        q1, q3 = np.percentile(valores, [25, 75])
        capas[c] = CapaDelPiso(c, "ok", mediana, n, float(q3 - q1), meseta[c], contraste)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    mascara = np.zeros((y1 - y0, x1 - x0), bool)
    mascara[ys - y0, xs - x0] = True
    mascara.setflags(write=False)
    region = RegionDelPiso(origen, (x0, y0, x1, y1), mascara, n, float(distancias_mm.mean()), float(distancias_mm.min()), float(distancias_mm.max()))
    return Piso("ok", origen, capas, region, escala, campo_texto, dict(p))


def piso_de_pelicula(pelicula, campo_luz, P, punto_manual=None):
    """El piso de una película: el nivel de la película FUERA del campo luminoso, por capa (R, G, B y gris), con la región de donde salió y su distancia al campo. Las reglas (1) a (7),
    el contrato de las entradas y lo que significa «no medible» están en el docstring del módulo. `P`: la escala del procedimiento (`CLAVES_DE_LA_ESCALA`) y, si se quieren cambiar,
    los parámetros del piso (`VALORES_DEL_PISO`; los que falten se ponen de fábrica y los usados quedan en `Piso.parametros`). `punto_manual`: el sexto clic (x, y) o None.
    `ValueError` solo si los argumentos tienen una forma equivocada (el campo no son 4 puntos, el punto no es (x, y), `P` sin la escala)."""
    P = {} if P is None else P
    faltan = [k for k in CLAVES_DE_LA_ESCALA if k not in P]
    if faltan:
        raise ValueError(f"P debe traer la escala del procedimiento: faltan {', '.join(faltan)}.")
    p = dict(VALORES_DEL_PISO)
    p.update({k: P[k] for k in VALORES_DEL_PISO if k in P})
    campo, crudos = _piso_cuadrilatero(campo_luz)
    punto = None if punto_manual is None else _piso_punto(punto_manual)
    origen = "automatico" if punto is None else "manual"
    dpi = getattr(pelicula, "dpi", None)
    escala = escala_mm(dpi, P)
    campo_texto = tuple((float(x), float(y)) for x, y in (crudos if campo is None else campo))
    if campo is None:
        return _piso_sin_numero(MOTIVO_CAMPO_INVALIDO, origen, campo_texto, escala, p)
    if escala is None:
        motivo = (f"no medible: la película se escaneó a otra resolución ({dpi:g} dpi) y sin la escala del procedimiento ({P['resolucion_escaneo_dpi']:g} dpi) "
                  f"no hay milímetros con que tomar el piso")
        return _piso_sin_numero(motivo, origen, campo_texto, escala, p)
    region = (_piso_region_automatica(pelicula, campo, escala, p) if punto is None else _piso_region_manual(pelicula, campo, escala, p, punto))
    if isinstance(region, str):
        return _piso_sin_numero(region, origen, campo_texto, escala, p)
    ys, xs, distancias_mm = region
    return _piso_resultado(pelicula, campo, campo_texto, escala, p, origen, ys, xs, distancias_mm)
