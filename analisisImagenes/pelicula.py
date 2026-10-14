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

EL PISO (A.2, 12-10; A.3, 13-10). `piso_de_pelicula(pelicula, campo_luz, P, punto_manual=None, modo=None, referencia_virgen=None)` dice cuál es el nivel de la película FUERA del campo luminoso, de
dónde lo sacó y a qué distancia del campo: el 50 % del borde de radiación es el 50 % entre ese piso y la meseta, así que de él depende el FWHM. Una sola función para las cuatro capas (R, G, B
y el gris). Se llama «piso» y no «película virgen»: la película de fuera del campo recibe dosis periférica y se sigue aclarando con la distancia (R7, H18), por eso se toma LO MÁS LEJOS POSIBLE
del campo y se dice a qué distancia.

TRES MODOS (A.3, DA-86; `MODOS_DEL_PISO`). El argumento `modo` los elige; con None es «punto_manual» si hay un `punto_manual` y, si no, `MODO_DEL_PISO_POR_OMISION`, la ÚNICA definición del modo
con que arrancan todos los análisis (pasar de uno a otro es cambiar esa línea). «automatico»: por ESQUINAS, con un rango esperado y un respaldo. «punto_manual»: el sexto clic sobre un trozo
sin irradiar. «virgen»: el piso de la película virgen de `referencia_virgen`, que se midió aparte con `piso_de_pelicula_virgen`; sin referencia el piso es «no medible» (NUNCA cae al automático)
y con ella el piso automático de la misma película se calcula igual, solo para compararlo (`Piso.comparacion`, sin veredicto). Los valores están en `PARAMETROS_DEL_PISO`, con nombre, unidad y
motivo. Reglas:
  (1) máscara de película = `validos` y no fondo (el fondo es casi blanco en las tres capas) y la componente conexa más grande, erosionada `margen_borde_mm` (1.0 mm: el fleco del corte llega a
      1 mm, medido el 13-10) de todo lo que no es película (fondo, píxeles sin dato) y, con `apartar_borde_de_la_imagen`, también del borde de la IMAGEN (un recorte a ras puede cortar la película
      en el borde de la imagen y el fleco está ahí; A.2 no lo apartaba). «Fondo» es un umbral FIJO, `umbral_fondo` (235): el fondo de las diez páginas reales es 255 y la capa más oscura del piso
      de la película va de 73 a 86, así que del lado de la película el margen es de 149 niveles y del lado del fondo de 20 solamente (NO es un margen amplio a los dos lados). Un fondo por
      debajo de 235 (otro escáner, un vidrio sucio, la tapa abierta) contaría como película: de eso se ocupan la regla (7) y el rango esperado (8);
  (2) región, en el modo automático = por ESQUINAS. La cuña de la esquina k son los píxeles de película limpia cuyo punto más cercano del cuadrilátero luminoso es ese vértice (el cono normal:
      `(p - C_k)·(C_k+1 - C_k) <= 0` y `(p - C_k)·(C_k - C_k-1) >= 0`), a más de `margen_campo_mm` del campo. De la cuña se aparta la tinta (3) y se toma la fracción `fraccion_lejana` más
      lejana del vértice (o, si eso son menos de `pixeles_minimos`, los `pixeles_minimos` más lejanos). El centro de cada lado queda fuera de toda cuña a propósito: el rojo está allí 11 a 38
      niveles por debajo del de las esquinas (la causa de DA-86). Las esquinas se llaman UL, UR, DR y DL (`ESQUINAS`);
  (3) tinta: fuera los píxeles que estén por debajo de la mediana de la región (de la cuña, en el modo automático) en más de `delta_tinta` niveles en alguna capa (R, G o B);
  (4) al menos `pixeles_minimos` píxeles, o «no medible: no hay película suficiente fuera del campo»;
  (5) coherencia: en cada capa el piso más claro que la meseta (la mediana de la película dentro del campo, a más de `margen_campo_mm` de sus lados) en al menos `contraste_minimo`
      niveles; la capa que no lo cumple es «no medible» y las demás siguen. Sin meseta (el campo luminoso no está sobre la película) ningún modo da número: «no medible: la
      película no cubre el campo luminoso...»; en el automático eso se comprueba justo después de la regla (7) de la unión y ANTES de juzgar las esquinas, que se construyen
      desde el campo (decisión de Opus del 13-10 ante dos caídas de test_a2 que el diseño no preveía, vetable por el físico);
  (6) con `punto_manual` (el sexto clic, sobre un trozo sin irradiar escaneado junto) el piso es la mediana de un cuadrado de `lado_punto_manual_mm` centrado en el punto, con las
      reglas (3), (5), (7) y (8): ese trozo es OTRA componente conexa, así que la regla de la componente más grande es solo de la región automática;
  (7) el piso no puede parecerse al fondo del escáner (A2-R1-02, 12-10: DECISIÓN DE DISEÑO DE OPUS ante un obstáculo que el plan no preveía, VETABLE POR EL FÍSICO). Va ANTES de la meseta y vale para
      los tres orígenes, sobre los píxeles de la región (después de la tinta; en el modo automático, de la unión de las cuatro cuñas, y otra vez de los finales): con la capa MÁS OSCURA de cada píxel
      (el mínimo de R, G y B: la misma definición de fondo que la regla 1, a otro nivel), si la fracción `fraccion_como_fondo` (10 %) o más de ellos llega a `umbral_como_fondo` (170 niveles), TODO el
      piso es «no medible: el piso es tan claro como el fondo del escáner, no como película (el N % de sus píxeles llega a 170 niveles hasta en su capa más oscura): revise la tapa y el vidrio del
      escáner y que el escaneo no lleve ajustes de brillo»: las cuatro capas sin número y sin región. Es una guarda por FRACCIÓN y no por mediana: un fondo que se cuela en las esquinas de un recorte
      suelto sube la mediana 1 a 3 niveles sin que la mediana lo note. LÍMITE DECLARADO que cierra (8): un fondo NEUTRO por debajo de 170 no se distingue de la película por esta regla;
  (8) rango esperado (A.3): las cuatro medianas (R, G, B y gris) de cada esquina y de la unión deben caer en `piso_esperado` (límites inclusivos; lo medido en las diez reales más y menos 10 niveles),
      y las del sexto clic en `piso_esperado_sin_irradiar`; un gris neutro de 150 o de 100 ya no pasa por película. Es un dato declarado del procedimiento fijo (película EBT3, Epson WF-6590, 600 ppp,
      8 bits): la aplicación avisa y delimita, nunca se adapta en silencio;
  (9) las esquinas (A.3). Cada esquina se comprueba por separado: píxeles suficientes, regla (7), dispersión (IQR de cada capa de `iqr_maximo` niveles o menos) y rango (8). Con dos o más esquinas
      que fallan (más de `4 - esquinas_minimas`) el problema no es local y NO se intenta ningún respaldo: «no medible: la película no sobresale lo bastante del campo luminoso en sus esquinas»
      si todas fallan por falta de película (un recorte demasiado ajustado: escanee la película entera) o «no medible: dos o más esquinas de la película no dan un piso válido» si no. Con UNA que
      falla se prueban hasta seis respaldos, en este orden: giro +`giro_respaldo_grados` y giro -`giro_respaldo_grados` desde la dirección de la esquina (el cruce de diagonales a la esquina; el «+» es
      la rotación que se acerca a la esquina siguiente UL -> UR -> DR -> DL), y laterales a `s_respaldo` (0.05 y 0.10 del semilado: nunca más lejos del vértice, el centro de un lado está
      prohibido) del lado que sale de la esquina y del que llega a ella. Cada respaldo es una ventana de `lado_punto_manual_mm` puesta lo más lejos del campo que la película deje (de
      `distancia_respaldo_maxima_mm` hacia el campo de `paso_respaldo_mm` en `paso_respaldo_mm`, hasta `margen_campo_mm` más la mitad de su lado), sin tinta y con las mismas comprobaciones que una
      esquina; el primero que pasa la reemplaza. Si ninguno pasa, la esquina se quita y el piso sale de las otras. El piso es la mediana de la unión de lo válido, y `Piso.esquinas` dice qué pasó
      con cada una (`EsquinaDelPiso`: estado, motivo, origen, píxeles, medianas, distancia, caja e intentos de respaldo).

PELÍCULA VIRGEN (A.3). `piso_de_pelicula_virgen(datos, P, nombre_archivo, fecha_calculo, orientacion_declarada)` mide el escaneo de una película SIN IRRADIAR con las comprobaciones C1 a C7 de la
investigación de A.3: C1 la cadena de captura (resolución, formato y si parece vuelta a guardar por un editor), C2 la zona (película a 2 mm de los bordes, 400 mm² como mínimo), C3 el recorte y
el blanco del fondo, C7 el ruido y las rayas, C6 las motas y rayones (se apartan), el rango de una película sin irradiar y el azul testigo, C5 la uniformidad por bloques de 5 mm y el
gradiente. Devuelve una `ReferenciaVirgen` («ok» o «no válida: <el primer rechazo>») con sus pruebas, avisos y procedencia (archivo, huella, formato, bits, resolución, fecha). Todos sus umbrales
(`PARAMETROS_DE_LA_VIRGEN`) son PROPUESTAS sin una película virgen real detrás: hay que recalibrarlos con los primeros escaneos vírgenes (deuda declarada; la ranura de prueba mide cada
`VIRGEN*` que el físico deje en `ImagenesDeReferencia/PlacasHistoricas`). `guardar_referencia_virgen` y `leer_referencia_virgen` la guardan junto a la base como `piso_pelicula_virgen.json` (atómico,
con el escaneo y las anteriores archivados: nada se borra); cada análisis guarda la COPIA de la referencia con que se midió dentro de `Piso.como_dict()` y esa copia manda (DA-81). Un archivo
(o una copia) dañado, de otra versión o con un valor del TIPO equivocado se rechaza AL LEERLO con `ValueError` (`referencia_virgen_desde_dict` valida las claves y los tipos), nunca con otra
excepción más tarde, lejos de donde se leyó.

CONTRATO de las entradas: `pelicula` es una `Pelicula` o cualquier objeto con `R`, `G`, `B`, `gris` (float32 en niveles de 8 bits), `validos` (bool), `dpi` y `bits`; `campo_luz` son las 4 esquinas del
campo luminoso como (x, y) en PÍXELES de esos arreglos (x = columna, y = fila; el centro del primer píxel es (0, 0)), en cualquier orden, formando un cuadrilátero convexo; `P` trae la escala
del procedimiento (`resolucion_escaneo_dpi`, `resoluciones_de_editor_dpi` y `tolerancia_dpi_relativa`) y, si quiere cambiarlos, los parámetros del piso (los que falte los pone de fábrica).
Lo que no se puede medir NO lanza: el resultado dice «no medible» con su motivo; solo una forma equivocada de los argumentos (el campo que no son 4 puntos, un `P` sin la escala, un modo que
no existe, un punto con un modo que no es «punto_manual», una referencia que no es una `ReferenciaVirgen`) es un `ValueError`. Los motivos son TEXTOS y alguno lleva cifras: quien los consume
pregunta `estado != "ok"` o `startswith("no medible")`, nunca compara con una lista cerrada.

Sin Qt y sin base de datos."""
import hashlib
import io
import json
import os
import re
import time
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



# ============================================================================= A.2: el piso (nivel de la película fuera del campo luminoso) y A.3: por esquinas, con modos y película virgen

CAPAS_DEL_PISO = CAPAS + ("gris",)                       # el piso se da de las tres capas y del gris (C.2 mide las cuatro)
_NOMBRE_DE_LA_CAPA_DEL_PISO = dict(NOMBRE_DE_CAPA, gris="gris")
CLAVES_DE_LA_ESCALA = ("resolucion_escaneo_dpi", "resoluciones_de_editor_dpi", "tolerancia_dpi_relativa")      # lo que `escala_mm` le pide a `P`
FILAS_POR_BLOQUE = 256                                    # las operaciones por píxel de una página completa se hacen por bloques de filas: sin temporales de 135 MB

# A.3 (13-10): el selector de modo. `MODO_DEL_PISO_POR_OMISION` es la ÚNICA definición del modo con que arrancan todos los análisis: cambiarlo es esta línea («virgen» cuando haya una
# referencia verificada). `MODO_DE_ORIGEN` traduce `Piso.origen` (A.2 lo llama «manual») al nombre del modo.
MODOS_DEL_PISO = ("automatico", "punto_manual", "virgen")
MODO_DEL_PISO_POR_OMISION = "automatico"
MODO_DE_ORIGEN = {"automatico": "automatico", "manual": "punto_manual", "virgen": "virgen"}
ORIGEN_DE_MODO = {modo: origen for origen, modo in MODO_DE_ORIGEN.items()}
CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS = ("R", "G", "gris")      # el azul casi no responde a la dosis periférica: no se le pide a la virgen ser más clara que el piso
ESQUINAS = ("UL", "UR", "DR", "DL")                       # el orden de `_piso_cuadrilatero`: por el ángulo alrededor del centroide, en la imagen con y hacia abajo
NOMBRE_DE_ESQUINA = {"UL": "superior izquierda", "UR": "superior derecha", "DR": "inferior derecha", "DL": "inferior izquierda"}
ITERACIONES_DE_LA_BISECCION = 60                          # la bisección que busca el centro de una ventana girada: 60 pasos sobre cuatro diagonales de película dan menos de 1e-12 px
NIVEL_MAXIMO = 255.0                                      # el máximo de las capas, que están en «niveles de 8 bits» también cuando la película es de 16
FACTOR_MAD = 1.4826                                       # la desviación robusta: 1.4826 · MAD (igual a la sigma de una gaussiana)
SIGMAS_DE_LA_MEDIA_RECORTADA = 3.0                        # la media de un bloque descarta lo que está a más de 3 sigmas robustas de su mediana
MM_EN_10_CM = 100.0
VERSION_PISO_VIRGEN = "PV-1"
PREFIJO_NO_VALIDA = "no válida: "
ARCHIVO_REFERENCIA_VIRGEN = "piso_pelicula_virgen.json"
CARPETA_REFERENCIAS_VIRGEN_ANTERIORES = "piso_pelicula_virgen_anteriores"
CARPETA_ESCANEOS_VIRGEN = "piso_pelicula_virgen_escaneos"

# Los parámetros del piso, cada uno con su nombre, su unidad y su motivo (PD1: lo que decide un número vive escrito, no en el código). `VALORES_DEL_PISO` es el diccionario plano
# que se le pasa a la función dentro de `P` (el `PARAMETROS` de C.1 lo incluye). Los valores con forma de diccionario o de lista viajan como JSON (listas, nunca tuplas).
PARAMETROS_DEL_PISO = {
    "umbral_fondo": {
        "valor": 235.0, "unidad": "nivel (0 a 255)",
        "motivo": "Un píxel es fondo del escáner si hasta su capa más oscura llega a 235: el fondo es casi blanco en las tres capas (255 en las páginas reales) y la capa más oscura del "
                  "piso de la película va de 73 a 86 en las diez reales. Del lado de la película el margen es de 149 niveles, pero del lado del fondo es de 20: un fondo por debajo de 235 "
                  "(otro escáner, un vidrio sucio, la tapa abierta) se tomaría por película, y de eso se ocupan la regla (7) con `umbral_como_fondo` y `fraccion_como_fondo` y, desde A.3, el "
                  "rango esperado, no este umbral."},
    "margen_borde_mm": {
        "valor": 1.0, "unidad": "mm",
        "motivo": "El borde de la película (el corte, la mezcla con el fondo que deja la compresión JPEG) no es película limpia, y a 0.5 a 1.0 mm del corte, a igual distancia del campo, el rojo "
                  "baja 2 a 7 niveles, el verde 1 a 12 y el azul sube 2 a 24 (el fleco del corte, medido el 13-10 en las diez reales; A.2 tomaba 0.5 mm): se aparta un milímetro hacia "
                  "adentro de todo lo que no es película y, con `apartar_borde_de_la_imagen`, también del borde de la imagen. Con 2 mm la película de PLACA_REF40 pierde dos esquinas. "
                  "Decisión vetable V2 del diseño de A.3."},
    "apartar_borde_de_la_imagen": {
        "valor": True, "unidad": "sí o no",
        "motivo": "En un recorte el corte de la película puede coincidir con el borde de la imagen (en el centro del lado izquierdo de ML0 la banda de 7.0 a 7.5 mm del campo da 85/160/77 y la "
                  "siguiente, pegada al borde de la imagen, 72/146/70): el borde de la imagen cuenta como borde de la película y se aparta `margen_borde_mm` hacia adentro. A.2 no lo hacía. "
                  "Decisión vetable V2 del diseño de A.3."},
    "margen_campo_mm": {
        "valor": 5.0, "unidad": "mm",
        "motivo": "La película pegada al campo recibe la penumbra y la dispersión del haz; a menos de 5 mm del cuadrilátero luminoso no se toma el piso (R7, H18). Es también la distancia "
                  "a los lados del campo desde la que se toma la meseta de referencia de la comprobación de coherencia, y la distancia mínima de la ventana de un respaldo."},
    "fraccion_lejana": {
        "valor": 0.20, "unidad": "fracción",
        "motivo": "De la película de cada esquina a más de 5 mm del campo se toma el 20 % más lejano: la película de fuera del campo no es virgen, recibe dosis periférica y se sigue aclarando con "
                  "la distancia (R7: en ML0 el verde pasa de 159 a 175 entre 5 y 9 mm), así que el piso se toma lo más lejos posible y se dice a qué distancia."},
    "delta_tinta": {
        "valor": 25.0, "unidad": "niveles",
        "motivo": "Un píxel que esté más de 25 niveles por debajo de la mediana de la región, en el rojo, el verde o el azul, es tinta (el rótulo, las diagonales pintadas) y no cuenta: "
                  "25 es mucho más que el ruido del escáner (1.5) y que la dispersión de la película. Aparta también la cola oscura del gradiente del rojo, con efecto de 2 niveles o menos "
                  "sobre la mediana (A.2, logs/A2/explorar_tinta.log)."},
    "pixeles_minimos": {
        "valor": 2000, "unidad": "píxeles",
        "motivo": "Con menos de 2000 píxeles (3.6 mm² a 600 dpi) la mediana no es estable ni distingue una mota de un nivel de piso: se prefiere decir «no medible». Vale para el total, para cada "
                  "esquina y para la ventana de un respaldo."},
    "contraste_minimo": {
        "valor": 10.0, "unidad": "niveles",
        "motivo": "Sin al menos 10 niveles entre el piso y la meseta, la normalización (piso - valor)/(piso - meseta) divide el ruido (1.5 por píxel) por una diferencia casi nula: esa capa "
                  "no se puede normalizar y se declara «no medible»."},
    "lado_punto_manual_mm": {
        "valor": 3.0, "unidad": "mm",
        "motivo": "El sexto clic toma un cuadrado de 3 × 3 mm (71 × 71 píxeles a 600 dpi) centrado en el punto: bastante para una mediana estable y menor que un trozo de película "
                  "escaneado junto al campo. Es también la ventana de cada respaldo de una esquina."},
    "umbral_como_fondo": {
        "valor": 170.0, "unidad": "nivel (0 a 255)",
        "motivo": "Un píxel del piso cuya capa más oscura llega a 170 es tan claro como el fondo de un escáner, no como película: en las diez películas reales la mediana de la capa más "
                  "oscura del piso está entre 73 y 86 (en grises, 138) y el fondo en 255; 170 es la mitad de esa brecha. Un fondo neutro por debajo de 170 lo frena, desde A.3, el rango esperado."},
    "fraccion_como_fondo": {
        "valor": 0.10, "unidad": "fracción",
        "motivo": "Si el 10 % o más de los píxeles del piso llega a `umbral_como_fondo`, no se toma piso: en las películas reales esos píxeles (motas claras) son del 0 al 0.6 %; un fondo "
                  "gris que se cuela en las esquinas de un recorte no mueve la mediana hasta el 13.9 % y la sube 1 a 3 niveles desde el 19 % (medido el 12-10)."},
    "piso_esperado": {
        "valor": {"R": [60.0, 140.0], "G": [145.0, 200.0], "B": [65.0, 100.0], "gris": [110.0, 170.0]}, "unidad": "nivel (0 a 255) por capa, [mínimo, máximo]",
        "motivo": "El rango en que cae el piso de la película de fuera del campo en el procedimiento fijo (película EBT3, Epson WF-6590, 600 ppp, 8 bits): lo medido en las 40 esquinas de las "
                  "diez reales (R 74 a 127, G 155 a 189, B 76 a 87, gris 122 a 158) más y menos 10 niveles (la variación entre las esquinas de una misma película, mediana 9), redondeado a 5 "
                  "hacia afuera. Es un dato declarado del procedimiento, como el protocolo fijo del Catphan (DP-111): la app avisa y delimita, nunca se adapta en silencio. Vetable V5."},
    "piso_esperado_sin_irradiar": {
        "valor": {"R": [60.0, 170.0], "G": [145.0, 230.0], "B": [65.0, 130.0], "gris": [110.0, 200.0]}, "unidad": "nivel (0 a 255) por capa, [mínimo, máximo]",
        "motivo": "El rango de un trozo SIN irradiar (el sexto clic y la película virgen): los mismos inferiores (no puede ser más oscura que la película de fuera del campo más oscura medida) y "
                  "los superiores 30 niveles más [propuesta, sin una virgen real que lo respalde: la película de fuera del campo sigue aclarándose hacia su borde, así que la virgen será más "
                  "clara en un monto que no se puede medir sin una]. Vetable V5."},
    "iqr_maximo": {
        "valor": 15.0, "unidad": "niveles",
        "motivo": "El IQR de las esquinas aceptadas en las diez reales va de 1 a 8 niveles en cualquier capa; una mezcla de dos zonas (la esquina inferior izquierda de EPSON001, con una mancha "
                  "clara pegada al corte) da 24 en el azul. Pasado 15 la esquina es «dispersa» y se reemplaza. Vetable V4."},
    "esquinas_minimas": {
        "valor": 3, "unidad": "esquinas",
        "motivo": "Con dos o más esquinas fallidas el problema no es local (un recorte demasiado ajustado, otro lote, un ajuste de color) y no se intenta ningún respaldo; quitar una esquina "
                  "cambia el piso 0 [-4 a +3] niveles. Vetable V4."},
    "giro_respaldo_grados": {
        "valor": 5.0, "unidad": "grados",
        "motivo": "El giro del respaldo desde la dirección de la esquina (el cruce de diagonales a la esquina): a ±5° el rojo baja 8 niveles (de -18 a -3) y a ±10° ya baja 15, más que la "
                  "variación entre esquinas de una misma película; 5° no sale de la zona de la esquina (cae en s menor que 0.06). Vetable V3."},
    "s_respaldo": {
        "valor": [0.05, 0.10], "unidad": "fracción del semilado (0 en la esquina, 1 en el punto medio)",
        "motivo": "Las posiciones laterales del respaldo, junto a la esquina: el rojo y el verde bajan desde que se sale de la esquina (a s = 0.10 el rojo baja 12 y el verde 8) y en el centro "
                  "de cada lado el rojo está 11 a 38 niveles por debajo; s mayor que 0.10 es la zona prohibida. Vetable V3."},
    "distancia_respaldo_maxima_mm": {
        "valor": 11.0, "unidad": "mm",
        "motivo": "La ventana de un respaldo se pone lo más lejos del campo que la película deja, empezando por 11 mm (las esquinas reales se toman a 6.2 a 10.3 mm en promedio y la película llega a "
                  "8.7 a 13.7 mm de una esquina): el piso sube 1 a 3 niveles de rojo por mm entre 6 y 10 mm."},
    "paso_respaldo_mm": {
        "valor": 0.5, "unidad": "mm",
        "motivo": "La ventana de un respaldo se acerca al campo de medio en medio milímetro hasta que cabe (hasta `margen_campo_mm` más la mitad del lado de la ventana)."},
    "tolerancia_virgen_mas_oscura": {
        "valor": 3.0, "unidad": "niveles",
        "motivo": "Una película virgen no puede tener más dosis que la película irradiada de fuera del campo: si es más oscura que el piso automático en el rojo, el verde o el gris por más de "
                  "3 niveles, no sirve para esta película (1 de repetibilidad entre escaneos, 1 del JPEG y 1 de margen) [propuesta de la investigación de A.3, sin una virgen real]."},
    "aviso_azul_virgen": {
        "valor": 5.0, "unidad": "niveles",
        "motivo": "El azul casi no responde a la dosis periférica (de -3 a +3 entre la virgen y el piso en las películas medidas): si difiere más de 5 niveles del piso automático, se avisa de "
                  "que puede ser otro lote u otra cadena de escaneo [propuesta de la investigación de A.3, sin una virgen real]."},
    "aviso_verde_virgen": {
        "valor": 25.0, "unidad": "niveles",
        "motivo": "El verde de la virgen es al menos 4 a 11 niveles más claro que el piso automático; si lo supera por más de 25, la diferencia es mayor que la esperada y se avisa "
                  "[propuesta de la investigación de A.3, sin una virgen real]."},
}


def _json_normal(valor):
    """Una COPIA del valor con la forma que viaja como JSON: diccionarios de claves de texto, listas (nunca tuplas) y números de Python."""
    if isinstance(valor, dict):
        return {str(k): _json_normal(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_json_normal(v) for v in valor]
    if isinstance(valor, np.generic):
        return valor.item()
    return valor


VALORES_DEL_PISO = {nombre: _json_normal(parametro["valor"]) for nombre, parametro in PARAMETROS_DEL_PISO.items()}

# Los parámetros de la película virgen (A.3, diseño §4 y §7). TODOS los umbrales son [propuesta] de la investigación (borradores/A3/investigacion_pruebas_pelicula_virgen.md) sin una película
# virgen REAL detrás (el corpus no trae ninguna): se recalibran con los primeros escaneos vírgenes (deuda declarada, diseño §12).
PARAMETROS_DE_LA_VIRGEN = {
    "margen_borde_virgen_mm": {
        "valor": 2.0, "unidad": "mm",
        "motivo": "La película virgen se mide a 2 mm o más de todo corte y del borde de la imagen: el fleco del corte supera 1 nivel hasta 0.55 a 1.0 mm del corte en la mayoría de los bordes y "
                  "hasta 1.5 mm en algunos [propuesta, investigación de A.3]."},
    "area_minima_virgen_mm2": {
        "valor": 400.0, "unidad": "mm²",
        "motivo": "Con menos de 4 cm² (2 × 2 cm) de película a 2 mm de los bordes no hay muestra suficiente para uniformidad ni bloques [propuesta, investigación de A.3]."},
    "lado_bloque_virgen_mm": {
        "valor": 5.0, "unidad": "mm",
        "motivo": "La uniformidad se mide en bloques de 5 × 5 mm (118 × 118 píxeles a 600 dpi), enteros dentro de la zona medida [propuesta, investigación de A.3]."},
    "bloques_minimos_virgen": {
        "valor": 4, "unidad": "bloques",
        "motivo": "Con menos de 4 bloques la desviación entre bloques y el gradiente no significan nada [propuesta, investigación de A.3]."},
    "recorte_rechazo": {
        "valor": 0.001, "unidad": "fracción",
        "motivo": "La película de fuera del campo va de 73 a 183 niveles, lejos de 0 y de 255: si más del 0.1 % de la zona medida está en 0 o en el máximo, la exposición o los ajustes automáticos "
                  "del escáner son los equivocados [propuesta, investigación de A.3]."},
    "recorte_aviso": {
        "valor": 0.0001, "unidad": "fracción",
        "motivo": "Más del 0.01 % de la zona medida en 0 o en el máximo avisa [propuesta, investigación de A.3]."},
    "distancia_fondo_mm": {
        "valor": 2.0, "unidad": "mm",
        "motivo": "El fondo del escáner se mide a 2 mm o más de la película (lejos de su halo) [propuesta, investigación de A.3]."},
    "borde_imagen_fondo_mm": {
        "valor": 1.0, "unidad": "mm",
        "motivo": "Y a 1 mm o más del borde de la imagen [propuesta, investigación de A.3]."},
    "pixeles_fondo_minimos": {
        "valor": 10000, "unidad": "píxeles",
        "motivo": "Con menos de 10 000 píxeles de fondo no se juzga el fondo (un recorte no trae fondo) [propuesta, investigación de A.3]."},
    "fondo_blanco_minimo": {
        "valor": 0.995, "unidad": "fracción",
        "motivo": "El fondo es la tapa blanca saturada del escáner: medido 99.98 % de los píxeles en 255 en las tres capas de las cuatro páginas reales; menos del 99.5 % avisa de que la tapa, el vidrio "
                  "o los ajustes (quitar fondo, brillo) cambiaron."},
    "cv_aviso": {
        "valor": {"R": 0.015, "G": 0.010, "B": 0.015, "gris": 0.010}, "unidad": "fracción (desviación entre bloques / media)",
        "motivo": "Una virgen real da 0.2 a 0.7 % entre bloques de 5 mm (la literatura, con escáneres CCD de 16 bits); la película de fuera del campo, que incluye la estructura de dosis, da "
                  "de 0.4 a 2.9 % en el verde: se avisa pasado 1 % en el verde y el gris y 1.5 % en el rojo y el azul [propuesta, investigación de A.3]."},
    "cv_rechazo": {
        "valor": {"R": 0.03, "G": 0.02, "B": 0.03, "gris": 0.02}, "unidad": "fracción (desviación entre bloques / media)",
        "motivo": "El doble del umbral de aviso: una película con 2 % de desviación entre bloques en el verde no es uniforme (irradiada, velada o con huellas) [propuesta, investigación de A.3]."},
    "dev_aviso": {
        "valor": {"R": 0.03, "G": 0.02, "B": 0.03, "gris": 0.02}, "unidad": "fracción (bloque más lejano de la mediana de los bloques)",
        "motivo": "Un bloque a más del 2 % de la mediana en el verde (unos 4 niveles, 0.11 mm de FWHM si el piso saliera de ahí) avisa; 3 % en el rojo y el azul [propuesta, investigación de A.3]."},
    "dev_rechazo": {
        "valor": {"R": 0.06, "G": 0.04, "B": 0.06, "gris": 0.04}, "unidad": "fracción (bloque más lejano de la mediana de los bloques)",
        "motivo": "El doble del umbral de aviso: un bloque a más del 4 % de la mediana en el verde se rechaza [propuesta, investigación de A.3]."},
    "gradiente_aviso_pct_por_10cm": {
        "valor": 1.0, "unidad": "% de la media por 10 cm",
        "motivo": "Una pendiente mayor de 1 % por 10 cm avisa de respuesta lateral del escáner o de una película curvada [propuesta, investigación de A.3: no hay dato publicado de virgen ni de CIS]."},
    "extension_minima_gradiente_mm": {
        "valor": 60.0, "unidad": "mm",
        "motivo": "El gradiente solo se juzga en la dirección en que la zona medida mide 6 cm o más [propuesta, investigación de A.3]."},
    "ventana_motas_mm": {
        "valor": 1.3, "unidad": "mm",
        "motivo": "El residuo de motas, rayones y huellas es la imagen menos su mediana móvil de 1.3 mm (31 píxeles a 600 dpi) [propuesta, investigación de A.3]."},
    "motas_sigmas": {
        "valor": 6.0, "unidad": "sigmas robustas del ruido",
        "motivo": "Se marca el residuo mayor que 6 veces el ruido (y que `motas_niveles`) [propuesta, investigación de A.3]."},
    "motas_niveles": {
        "valor": 8.0, "unidad": "niveles",
        "motivo": "Y mayor que 8 niveles, para que el ruido no marque nada [propuesta, investigación de A.3]."},
    "motas_pixeles_grupo": {
        "valor": 3, "unidad": "píxeles",
        "motivo": "Solo cuentan los grupos de 3 píxeles o más (8-conectividad) [propuesta, investigación de A.3]."},
    "dilatacion_tinta_y_motas_mm": {
        "valor": 0.5, "unidad": "mm",
        "motivo": "La tinta y las motas se apartan dilatadas 0.5 mm [propuesta, investigación de A.3]."},
    "motas_aviso_fraccion": {
        "valor": 0.0005, "unidad": "fracción",
        "motivo": "Si las motas cubren más del 0.05 % de la zona medida se avisa [propuesta, investigación de A.3: en el interior de las películas reales casi no hay motas]."},
    "motas_aviso_grupo_mm2": {
        "valor": 0.2, "unidad": "mm²",
        "motivo": "O si algún grupo pasa de 0.2 mm² [propuesta, investigación de A.3]."},
    "motas_rechazo_fraccion": {
        "valor": 0.02, "unidad": "fracción",
        "motivo": "Si cubren más del 2 % la película está sucia o rayada y se rechaza [propuesta, investigación de A.3]."},
    "ventana_ruido_mm": {
        "valor": 0.5, "unidad": "mm",
        "motivo": "El ruido es 1.4826 veces la MAD del residuo de una media móvil de 0.5 mm (13 píxeles) [propuesta, investigación de A.3]."},
    "ruido_aviso": {
        "valor": {"R": 3.5, "G": 2.5, "B": 3.5}, "unidad": "niveles",
        "motivo": "El ruido medido de las películas reales es 1.2 a 1.8 (R), 1.0 a 1.6 (G) y 1.2 a 2.2 (B); se avisa a 1.5 veces el máximo [propuesta, investigación de A.3]."},
    "ventana_rayas_mm": {
        "valor": 2.0, "unidad": "mm",
        "motivo": "Las rayas son la amplitud de las medias por columna y por fila menos una media móvil de 2 mm [propuesta, investigación de A.3]."},
    "rayas_aviso_niveles": {
        "valor": 1.0, "unidad": "niveles",
        "motivo": "Una amplitud mayor de 1 nivel avisa (el doble del máximo medido, 0.56) [propuesta, investigación de A.3]."},
    "azul_testigo": {
        "valor": [75.0, 95.0], "unidad": "nivel (0 a 255)",
        "motivo": "El azul casi no responde a la dosis periférica: 81 a 85 en las cinco películas medidas; un azul fuera de 75 a 95 avisa de otro lote o de otra cadena de escaneo "
                  "[propuesta, investigación de A.3]."},
    "calidad_jpeg_editor": {
        "valor": 90.0, "unidad": "calidad JPEG estimada",
        "motivo": "El escáner entrega JPEG de calidad estimada 70 con croma 4:2:2; un JPEG 4:2:0 de calidad 90 o más es un archivo vuelto a guardar por un editor (medido en los recortes del físico: "
                  "calidad 94 a 99 con 4:2:0) [propuesta, investigación de A.3]."},
}
VALORES_DE_LA_VIRGEN = {nombre: _json_normal(parametro["valor"]) for nombre, parametro in PARAMETROS_DE_LA_VIRGEN.items()}

MOTIVO_SIN_PISO = "no medible: no hay película suficiente fuera del campo"
MOTIVO_PUNTO_FUERA_DE_PELICULA = "no medible: el punto no está sobre película"
MOTIVO_POCA_PELICULA_EN_EL_PUNTO = "no medible: no hay película suficiente alrededor del punto"
MOTIVO_CAMPO_INVALIDO = "no medible: el campo luminoso no forma un cuadrilátero convexo"
MOTIVO_SIN_PELICULA = "no medible: no hay película en la imagen (todo es fondo del escáner o no tiene dato)"
MOTIVO_SIN_MESETA = "no medible: la película no cubre el campo luminoso, así que no se puede comprobar el contraste con la meseta"
# Regla (7): es el comienzo del `estado` (lleva detrás, entre paréntesis, el porcentaje de píxeles del piso que llegan a `umbral_como_fondo` y el umbral, y qué revisar).
MOTIVO_PISO_COMO_EL_FONDO = "no medible: el piso es tan claro como el fondo del escáner, no como película"
# A.3: cada constante es el COMIENZO del `estado`; el detalle (las cifras y qué hacer) se añade detrás. Quien los consuma pregunta `estado != "ok"`, nunca una lista cerrada de motivos.
MOTIVO_ESQUINAS_SIN_PELICULA = "no medible: la película no sobresale lo bastante del campo luminoso en sus esquinas"
MOTIVO_ESQUINAS_SIN_PISO = "no medible: dos o más esquinas de la película no dan un piso válido"
MOTIVO_PISO_FUERA_DEL_RANGO = "no medible: el piso está fuera del rango esperado de la película de fuera del campo"
MOTIVO_PUNTO_FUERA_DEL_RANGO = "no medible: el punto marcado no tiene el nivel de una película sin irradiar"
MOTIVO_SIN_REFERENCIA_VIRGEN = "no medible: no hay película virgen de referencia"
MOTIVO_REFERENCIA_VIRGEN_NO_VALIDA = "no medible: la película virgen de referencia no es válida"
MOTIVO_VIRGEN_OTRA_CADENA = "no medible: la película virgen se escaneó con otra cadena de captura"
MOTIVO_VIRGEN_MAS_OSCURA = "no medible: la película virgen es más oscura que la película de fuera del campo"
# Lo que dice cada origen del rango esperado: (clave del parámetro, motivo, qué hacer). El automático se juzga contra la película de fuera del campo; el punto marcado, contra una sin irradiar.
_RANGO_DEL_PISO_AUTOMATICO = ("piso_esperado", MOTIVO_PISO_FUERA_DEL_RANGO, "revise el escaneo (otro lote, otro escáner o ajustes de color) o use la película virgen")
_RANGO_DEL_PUNTO_MARCADO = ("piso_esperado_sin_irradiar", MOTIVO_PUNTO_FUERA_DEL_RANGO, "marque un punto sobre película sin irradiar")


def _cifra(x):
    """Un número para un texto: sin decimales si es entero (152.0 -> 152) y con uno si no (131.5)."""
    texto = f"{x:.1f}"
    return texto[:-2] if texto.endswith(".0") else texto


def _con_signo(x):
    """+8, -2, 0 (sin decimales si es entero)."""
    return "0" if x == 0 else f"{x:+.1f}".replace(".0", "")


def _unir_con_y(elementos):
    """['a', 'b', 'c'] -> 'a, b y c'."""
    elementos = list(elementos)
    return elementos[0] if len(elementos) == 1 else ", ".join(elementos[:-1]) + " y " + elementos[-1]


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


@dataclass(frozen=True)
class IntentoDeRespaldo:
    """Un candidato del respaldo de una esquina. `nombre`: «giro +5 grados», «giro -5 grados» o «lateral s=0.05 del lado UL-UR»; `estado`: «ok», «falla» (la ventana se puso y no pasó las
    comprobaciones: `motivo` dice cuál) o «sin lugar» (la película no deja poner la ventana a más de `margen_campo_mm` del campo); `d_mm`: a qué distancia del campo quedó el centro de la ventana
    (la mayor que la película deja) y `centro` (x, y) en píxeles de la película; `n` y `medianas` (R, G, B, gris) de lo medido en la ventana, sin la tinta."""
    nombre: str
    estado: str
    motivo: str = ""
    d_mm: float | None = None
    centro: tuple | None = None
    n: int = 0
    medianas: dict | None = None

    def como_dict(self):
        return {"nombre": self.nombre, "estado": self.estado, "motivo": self.motivo, "d_mm": self.d_mm, "centro": None if self.centro is None else [float(self.centro[0]), float(self.centro[1])],
                "n": int(self.n), "medianas": None if self.medianas is None else dict(self.medianas)}


@dataclass(frozen=True)
class EsquinaDelPiso:
    """Qué pasó con UNA esquina del campo. `esquina`: «UL», «UR», «DR» o «DL»; `estado`: «ok», «reemplazada» (falló y la reemplazó un respaldo), «sin piso» (falló y ningún respaldo sirvió: el piso
    sale de las otras), «falla» (falló y no se probó ningún respaldo, porque fallaron dos o más) o «sin comprobar» (otro motivo frenó todo antes); `motivo`: por qué falló la esquina original
    («» si está bien); `origen`: «esquina» o el nombre del respaldo que la reemplazó; `n`, `medianas`, `iqr`, `distancia_media_mm` y `caja` de la parte que se USÓ (la esquina o su respaldo; o,
    si no hay parte, de la que falló); `respaldos`: los intentos, en orden."""
    esquina: str
    estado: str
    motivo: str = ""
    origen: str = "esquina"
    n: int = 0
    medianas: dict | None = None
    iqr: dict | None = None
    distancia_media_mm: float | None = None
    caja: tuple | None = None
    respaldos: tuple = ()

    def como_dict(self):
        return {"esquina": self.esquina, "estado": self.estado, "motivo": self.motivo, "origen": self.origen, "n": int(self.n),
                "medianas": None if self.medianas is None else dict(self.medianas), "iqr": None if self.iqr is None else dict(self.iqr),
                "distancia_media_mm": self.distancia_media_mm, "caja": None if self.caja is None else [int(v) for v in self.caja], "respaldos": [i.como_dict() for i in self.respaldos]}


def _frase_de_la_ventana(origen):
    """«giro +5 grados» -> «la ventana girada +5 grados»; «lateral s=0.1 del lado UR-DR» -> «la ventana lateral s=0.1 del lado UR-DR»."""
    return "la ventana girada " + origen[len("giro "):] if origen.startswith("giro ") else "la ventana " + origen


def _motivo_en_prosa(motivo):
    """«dispersa (IQR del azul 24 > 15)» -> «dispersa: IQR del azul 24 > 15»; «sin película suficiente (1506 píxeles)» -> «sin película suficiente: 1506 píxeles»."""
    return motivo[:-1].replace(" (", ": ", 1) if motivo.endswith(")") and " (" in motivo else motivo


def _motivo_corto(motivo):
    """«sin película suficiente (1506 píxeles)» -> «sin película suficiente»."""
    return motivo.split(" (")[0]


@dataclass(frozen=True, eq=False)
class Piso:
    """El piso de una película: `estado` («ok» si hubo piso; si no, «no medible: <motivo>» y ninguna capa trae número), `origen` («automatico», «manual» o «virgen»), `capas` (R, G, B y gris),
    `region` (de dónde salió, o None si no hay región en esta película: la virgen), `escala_mm` (la del procedimiento; None si el archivo declara otra resolución), `campo_luz` (las 4 esquinas con
    que se midió) y `parametros` (los del piso con que se midió, para guardarlos con el análisis). Se llama «piso» y no «película virgen»: la película de fuera del campo recibe dosis periférica (R7).

    A.3: `esquinas` (qué pasó con cada una de las cuatro, en el automático; () en los otros modos), `punto` (el sexto clic, (x, y)), `referencia` (la película virgen con que se midió),
    `comparacion` (en el modo virgen, el piso AUTOMÁTICO de esta película, solo informativo) y `avisos`. `modo` es el nombre del modo con que se pidió."""
    estado: str
    origen: str
    capas: dict
    region: RegionDelPiso | None
    escala_mm: float | None
    campo_luz: tuple
    parametros: dict
    esquinas: tuple = ()
    punto: tuple | None = None
    referencia: "ReferenciaVirgen | None" = None
    comparacion: "Piso | None" = None
    avisos: tuple = ()

    @property
    def modo(self):
        return MODO_DE_ORIGEN[self.origen]

    def valor(self, capa):
        """El nivel de piso de una capa (R, G, B o gris), o None si no se pudo medir."""
        return self.capas[capa].mediana

    @property
    def todas_medibles(self):
        return self.estado == "ok" and all(c.estado == "ok" for c in self.capas.values())

    def diferencia_con_el_automatico(self):
        """{capa: virgen - automatico} del modo virgen (siempre informativa, sin veredicto), o None si no hay con qué comparar."""
        if self.comparacion is None or self.comparacion.estado != "ok" or self.referencia is None:
            return None
        return {c: (None if self.comparacion.capas[c].mediana is None or self.referencia.valor(c) is None else float(self.referencia.valor(c) - self.comparacion.capas[c].mediana))
                for c in CAPAS_DEL_PISO}

    def descripcion(self):
        """Una frase que dice de dónde salió el piso (y qué capas no se pudieron medir). Sin símbolos de correcto o incorrecto (DA-18)."""
        if self.estado != "ok":
            return self.estado
        sin_piso = [f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]}: {capa.estado}" for c, capa in self.capas.items() if capa.estado != "ok"]
        cola = "" if not sin_piso else " " + "; ".join(sin_piso) + "."
        if self.origen == "virgen":
            texto = self.referencia.descripcion()
            nuevos = [a for a in self.avisos if a not in self.referencia.avisos]
            return texto + ("" if not nuevos else " " + " ".join(nuevos)) + cola
        if self.region is None:
            return self.estado
        r = self.region
        if self.origen == "manual":
            lado = self.parametros["lado_punto_manual_mm"]
            texto = f"Piso tomado en el punto marcado (un cuadrado de {lado:g} × {lado:g} mm, {r.n} píxeles), a {r.distancia_media_mm:.1f} mm del campo luminoso."
        else:
            usadas = sum(1 for e in self.esquinas if e.estado in ("ok", "reemplazada"))
            donde = "en sus cuatro esquinas" if usadas == len(ESQUINAS) else f"en {usadas} de sus cuatro esquinas"
            texto = (f"Piso tomado en {r.n} píxeles de película fuera del campo luminoso, a {r.distancia_media_mm:.1f} mm de él en promedio "
                     f"(de {r.distancia_minima_mm:.1f} a {r.distancia_maxima_mm:.1f} mm) {donde}. No es película sin irradiar: recibe dosis periférica.")
            for e in self.esquinas:
                if e.estado == "reemplazada":
                    ganador = e.respaldos[-1]
                    texto += (f" La esquina {NOMBRE_DE_ESQUINA[e.esquina]} se tomó con {_frase_de_la_ventana(e.origen)} a {_cifra(ganador.d_mm)} mm del campo "
                              f"({_motivo_en_prosa(e.motivo)}).")
                elif e.estado == "sin piso":
                    texto += f" La esquina {NOMBRE_DE_ESQUINA[e.esquina]} no dio piso ({_motivo_corto(e.motivo)}) y se usaron las otras tres."
        return texto + cola

    def como_dict(self):
        """Todo lo que dice el piso en un diccionario de números y textos (sin arreglos): viaja como JSON. Las siete claves de A.2 y las seis de A.3 (`modo`, `punto`, `esquinas`,
        `referencia_virgen`, `comparacion`, `avisos`), siempre presentes."""
        region = None
        if self.region is not None:
            r = self.region
            region = {"origen": r.origen, "caja": [int(v) for v in r.caja], "n": int(r.n), "distancia_media_mm": float(r.distancia_media_mm),
                      "distancia_minima_mm": float(r.distancia_minima_mm), "distancia_maxima_mm": float(r.distancia_maxima_mm)}
        return {"estado": self.estado, "origen": self.origen, "escala_mm": None if self.escala_mm is None else float(self.escala_mm),
                "campo_luz": [[float(x), float(y)] for x, y in self.campo_luz], "parametros": _json_normal(self.parametros),
                "capas": {c: {"estado": capa.estado, "mediana": capa.mediana, "n": int(capa.n), "iqr": capa.iqr, "meseta": capa.meseta, "contraste": capa.contraste}
                          for c, capa in self.capas.items()},
                "region": region,
                "modo": self.modo, "punto": None if self.punto is None else [float(self.punto[0]), float(self.punto[1])],
                "esquinas": [e.como_dict() for e in self.esquinas],
                "referencia_virgen": None if self.referencia is None else self.referencia.como_dict(),
                "comparacion": None if self.comparacion is None else {"piso_automatico": self.comparacion.como_dict(), "diferencia": self.diferencia_con_el_automatico()},
                "avisos": list(self.avisos)}


@dataclass(frozen=True)
class PruebaDeLaVirgen:
    """Una comprobación hecha a la película virgen. `nombre`: «C1 cadena», «C2 zona», «C3 recorte», «C3 fondo», «C7 ruido», «C6 motas», «rango», «azul testigo», «C5 uniformidad», «C5 gradiente»
    o «C7 rayas»; `resultado`: «ok», «aviso» o «rechazo»; `texto`: la cifra y el límite, sin símbolos (DA-18)."""
    nombre: str
    resultado: str
    texto: str


@dataclass(frozen=True, eq=False)
class ReferenciaVirgen:
    """El piso medido en el escaneo de una película VIRGEN (sin irradiar). `estado`: «ok» o «no válida: <motivo>» (el del primer rechazo); `capas`: R, G, B y gris (`CapaDelPiso` con la mediana, el
    n y el IQR de la zona medida; sin meseta ni contraste, que son de la película irradiada); `pruebas` y `avisos`: lo que se comprobó; `region`: {"caja", "n", "area_mm2"} en píxeles del ESCANEO de la
    virgen; `procedencia`: de dónde salió el archivo (nombre, huella, formato, bits, resolución...); `parametros`: los de la virgen y los del piso con que se midió."""
    estado: str
    capas: dict
    pruebas: tuple
    avisos: tuple
    region: dict | None
    procedencia: dict
    parametros: dict

    def valor(self, capa):
        """El valor (mediana) de una capa (R, G, B o gris) de la virgen, o None si no se pudo medir."""
        return self.capas[capa].mediana

    def como_dict(self):
        return {"version": VERSION_PISO_VIRGEN, "estado": self.estado,
                "capas": {c: {"estado": capa.estado, "mediana": capa.mediana, "n": int(capa.n), "iqr": capa.iqr, "meseta": capa.meseta, "contraste": capa.contraste}
                          for c, capa in self.capas.items()},
                "pruebas": [{"nombre": p.nombre, "resultado": p.resultado, "texto": p.texto} for p in self.pruebas], "avisos": list(self.avisos),
                "region": _json_normal(self.region), "procedencia": _json_normal(self.procedencia), "parametros": _json_normal(self.parametros)}

    def descripcion(self):
        """«Película virgen «archivo» (escaneada el …, huella 3fa9c2d1): rojo 106, verde 174, azul 82, gris 143 en N píxeles a 2 mm o más de sus bordes.» y los avisos."""
        pr = self.procedencia
        nombre = pr.get("archivo") or "sin nombre"
        if self.estado != "ok":
            return f"Película virgen «{nombre}»: {self.estado}."
        cuando = f"escaneada el {pr['fecha_escaneo']}" if pr.get("fecha_escaneo") else f"medida el {pr['fecha_calculo']}"
        valores = ", ".join(f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {_cifra(self.capas[c].mediana)}" for c in CAPAS_DEL_PISO)
        texto = (f"Película virgen «{nombre}» ({cuando}, huella {pr['sha256'][:8]}): {valores} en {self.region['n']} píxeles "
                 f"a {self.parametros['margen_borde_virgen_mm']:g} mm o más de sus bordes.")
        return texto + ("" if not self.avisos else " Avisos: " + "; ".join(self.avisos) + ".")


_HUELLA_SHA256 = re.compile(r"[0-9a-f]{64}")


def _es_numero(valor):
    """Un número real y finito, como lo escribe JSON: `true` no es una medida (los booleanos no cuentan) y NaN e infinito (que `json` sí lee) tampoco."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return False
    return not isinstance(valor, float) or bool(np.isfinite(valor))


def _es_entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def _exige_la_referencia(condicion, que):
    """`ValueError` con el motivo si no se cumple `condicion`: una referencia guardada que no es como `ReferenciaVirgen.como_dict()` la escribe está dañada."""
    if not condicion:
        raise ValueError(f"La referencia de la película virgen está dañada: {que}.")


def referencia_virgen_desde_dict(d):
    """La inversa de `ReferenciaVirgen.como_dict()`. `ValueError` con el motivo si no es un diccionario, si falta una clave, si la versión no es la actual (`VERSION_PISO_VIRGEN`) o si un valor no es
    del TIPO que `como_dict()` escribe (una lista de avisos que es `null`, una mediana de texto, unos píxeles negativos...): un archivo dañado o editado a mano se rechaza AQUÍ, con su motivo, y
    no revienta más tarde, lejos de donde se leyó, con otra excepción (RV-A3-3). Una referencia «ok» además debe poder USARSE: sus cuatro capas «ok» con mediana y píxeles, su región (píxeles,
    área y caja), la huella, el archivo y la fecha de su procedencia y el margen con que se midió. Del resto de la procedencia y de los parámetros solo se exige que sean un diccionario: nada
    de lo que se hace con una referencia lo calcula."""
    if not isinstance(d, dict):
        raise ValueError("La referencia de la película virgen debe ser un diccionario.")
    if d.get("version") != VERSION_PISO_VIRGEN:
        raise ValueError(f"La referencia de la película virgen es de la versión {d.get('version')!r} y esta aplicación lee la {VERSION_PISO_VIRGEN!r}.")
    faltan = [k for k in ("estado", "capas", "pruebas", "avisos", "region", "procedencia", "parametros") if k not in d]
    if faltan:
        raise ValueError(f"A la referencia de la película virgen le faltan: {', '.join(faltan)}.")
    try:
        capas = {c: CapaDelPiso(c, v["estado"], v["mediana"], v["n"], v["iqr"], v["meseta"], v["contraste"]) for c, v in d["capas"].items()}
        pruebas = tuple(PruebaDeLaVirgen(p["nombre"], p["resultado"], p["texto"]) for p in d["pruebas"])
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"La referencia de la película virgen está incompleta: {e!r}.") from None
    if set(capas) != set(CAPAS_DEL_PISO):
        raise ValueError("La referencia de la película virgen no trae las cuatro capas.")
    _exige_la_referencia(isinstance(d["estado"], str), "el estado no es un texto")
    for c, capa in capas.items():
        _exige_la_referencia(isinstance(capa.estado, str), f"el estado de la capa {c} no es un texto")
        _exige_la_referencia(_es_entero(capa.n) and capa.n >= 0, f"los píxeles (n) de la capa {c} no son un entero de 0 o más")
        _exige_la_referencia(all(x is None or _es_numero(x) for x in (capa.mediana, capa.iqr, capa.meseta, capa.contraste)),
                             f"la mediana, el IQR, la meseta o el contraste de la capa {c} no son un número")
    _exige_la_referencia(all(isinstance(x, str) for p in pruebas for x in (p.nombre, p.resultado, p.texto)), "el nombre, el resultado o el texto de una prueba no son un texto")
    _exige_la_referencia(isinstance(d["avisos"], list) and all(isinstance(a, str) for a in d["avisos"]), "los avisos no son una lista de textos")
    _exige_la_referencia(d["region"] is None or isinstance(d["region"], dict), "la región no es un diccionario")
    _exige_la_referencia(isinstance(d["procedencia"], dict), "la procedencia no es un diccionario")
    _exige_la_referencia(isinstance(d["parametros"], dict), "los parámetros no son un diccionario")
    if d["estado"] == "ok":
        region, procedencia = d["region"], d["procedencia"]
        _exige_la_referencia(all(capa.estado == "ok" and capa.mediana is not None and capa.n >= 1 for capa in capas.values()), "una referencia «ok» trae las cuatro capas «ok», con su mediana y sus píxeles")
        _exige_la_referencia(region is not None, "una referencia «ok» trae su región")
        _exige_la_referencia(_es_entero(region.get("n")) and region["n"] >= 1, "la región no dice cuántos píxeles midió (n)")
        _exige_la_referencia(_es_numero(region.get("area_mm2")), "la región no dice su área (area_mm2)")
        _exige_la_referencia(isinstance(region.get("caja"), list) and len(region["caja"]) == 4 and all(_es_numero(x) for x in region["caja"]), "la caja de la región no son 4 números")
        _exige_la_referencia(isinstance(procedencia.get("archivo"), str), "la procedencia no trae el nombre del archivo")
        _exige_la_referencia(isinstance(procedencia.get("fecha_calculo"), str) and procedencia["fecha_calculo"] != "", "la procedencia no trae la fecha de cálculo")
        _exige_la_referencia(isinstance(procedencia.get("sha256"), str) and _HUELLA_SHA256.fullmatch(procedencia["sha256"]) is not None, "la huella (sha256) de la procedencia no es una huella")
        _exige_la_referencia(_es_numero(d["parametros"].get("margen_borde_virgen_mm")), "los parámetros no traen el margen con que se midió (margen_borde_virgen_mm)")
    return ReferenciaVirgen(d["estado"], capas, pruebas, tuple(d["avisos"]), _json_normal(d["region"]), _json_normal(d["procedencia"]), _json_normal(d["parametros"]))


def texto_de_la_comparacion(piso):
    """La comparación del piso de la película virgen con el automático de la MISMA película (solo informativa, sin veredicto), o «» si el piso no es del modo virgen. Una sola definición."""
    auto = piso.comparacion
    if auto is None:
        return ""
    if auto.estado != "ok":
        return f"Comparación (solo informativa): no se pudo comparar con el piso automático de esta película: {auto.estado}."
    usadas = sum(1 for e in auto.esquinas if e.estado in ("ok", "reemplazada"))
    donde = "en sus cuatro esquinas" if usadas == len(ESQUINAS) else f"en {usadas} de sus cuatro esquinas"
    valores = ", ".join(f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {_cifra(auto.capas[c].mediana)}" for c in CAPAS_DEL_PISO if auto.capas[c].mediana is not None)
    inicio = f"Comparación (solo informativa): el piso automático de esta película ({donde}, a {auto.region.distancia_media_mm:.1f} mm del campo en promedio) es {valores}; "
    dif = {c: piso.referencia.valor(c) - auto.capas[c].mediana for c in CAPAS_DEL_PISO if auto.capas[c].mediana is not None and piso.referencia.valor(c) is not None}
    if not dif:
        return inicio + "la película virgen no tiene valores con que compararlo."
    if all(d >= 0 for d in dif.values()):
        return inicio + "la película virgen está " + " / ".join(_con_signo(d) for d in dif.values()) + " niveles más clara."
    mas_clara = ["el " + _NOMBRE_DE_LA_CAPA_DEL_PISO[c] for c, d in dif.items() if d > 0]
    mas_oscura = [f"{_cifra(-d)} {'nivel' if abs(d) == 1 else 'niveles'} más oscura en el {_NOMBRE_DE_LA_CAPA_DEL_PISO[c]}" for c, d in dif.items() if d < 0]
    partes = ([] if not mas_clara else ["más clara en " + _unir_con_y(mas_clara)]) + mas_oscura
    return inicio + "la película virgen está " + " y ".join(partes) + "."


_ADJETIVO_DE_LA_CAPA = {"R": "roja", "G": "verde", "B": "azul", "gris": "gris"}


def texto_breve_del_piso(piso, capa=None):
    """UNA línea que dice el piso de una capa y de dónde salió, para la ventana y para el PDF (una sola definición). Acepta un `Piso` o su `como_dict()` (lo que viaja guardado con el
    análisis). `capa`: R, G, B o gris (por omisión `CAPA_POR_OMISION`). Sin símbolos de correcto o incorrecto (DA-18)."""
    d = piso.como_dict() if isinstance(piso, Piso) else piso
    capa = CAPA_POR_OMISION if capa is None else capa
    if d["estado"] != "ok":
        return "Piso: " + d["estado"]
    c = d["capas"][capa]
    cabeza = f"Piso (capa {_ADJETIVO_DE_LA_CAPA[capa]}): "
    if c["estado"] != "ok":
        return cabeza + c["estado"]
    cabeza += f"{_cifra(c['mediana'])} niveles; "
    if d["modo"] == "virgen":
        pr = d["referencia_virgen"]["procedencia"]
        cuando = f"escaneada el {pr['fecha_escaneo']}" if pr.get("fecha_escaneo") else f"medida el {pr['fecha_calculo']}"
        return cabeza + f"película virgen «{pr['archivo']}», {cuando} (huella {pr['sha256'][:8]})."
    distancia = d["region"]["distancia_media_mm"]
    if d["modo"] == "punto_manual":
        return cabeza + f"punto marcado sobre película sin irradiar, a {distancia:.1f} mm del campo."
    usadas = sum(1 for e in d["esquinas"] if e["estado"] in ("ok", "reemplazada"))
    cuantas = "las cuatro esquinas" if usadas == len(ESQUINAS) else f"{usadas} de las {len(ESQUINAS)} esquinas"
    extras = []
    for e in d["esquinas"]:
        if e["estado"] == "reemplazada":
            extras.append(f"la esquina {NOMBRE_DE_ESQUINA[e['esquina']]} con {_frase_de_la_ventana(e['origen'])}")
        elif e["estado"] == "sin piso":
            extras.append(f"la esquina {NOMBRE_DE_ESQUINA[e['esquina']]} sin piso")
    return cabeza + f"automático, en {cuantas} de la película a {distancia:.1f} mm del campo" + "".join("; " + x for x in extras) + "."


def _piso_sin_numero(motivo, origen, campo, escala, p, **extra):
    """Un piso sin número en ninguna capa, con el motivo. `extra`: lo que se sabe aun así de A.3 (`esquinas`, `punto`, `referencia`, `comparacion`, `avisos`)."""
    return Piso(motivo, origen, {c: CapaDelPiso(c, motivo) for c in CAPAS_DEL_PISO}, None, escala, campo, dict(p), **extra)


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


def _piso_fraccion_como_fondo(pelicula, ys, xs, umbral):
    """La fracción de los píxeles (ys, xs) cuya capa más oscura (el mínimo de R, G y B) llega a `umbral`: lo que la regla (7) compara con `fraccion_como_fondo`."""
    mas_oscura = np.minimum(np.minimum(pelicula.R[ys, xs], pelicula.G[ys, xs]), pelicula.B[ys, xs])
    return float(np.mean(mas_oscura >= umbral))


def _piso_distancia_a_los_lados(campo, x, y):
    """Distancia en PÍXELES de los puntos (x, y) (arreglos o escalares, coordenadas de la película, no necesariamente enteras) al cuadrilátero luminoso; 0 dentro de él. Es la misma cuenta de
    segmentos que `_piso_distancias_al_campo`, pero para puntos sueltos y no para una rejilla de píxeles enteros: los respaldos buscan el centro de una ventana a una distancia dada y miden
    la distancia de los píxeles de su ventana."""
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    aristas = np.roll(campo, -1, axis=0) - campo
    mas_cerca = np.full(x.shape, np.inf)
    signos = []
    for i in range(len(aristas)):
        px, py = x - campo[i, 0], y - campo[i, 1]
        t = np.clip((px * aristas[i, 0] + py * aristas[i, 1]) / float(aristas[i] @ aristas[i]), 0.0, 1.0)
        mas_cerca = np.minimum(mas_cerca, np.hypot(px - t * aristas[i, 0], py - t * aristas[i, 1]))
        signos.append(aristas[i, 0] * py - aristas[i, 1] * px)
    signos = np.array(signos)
    dentro = np.all(signos >= 0, axis=0) | np.all(signos <= 0, axis=0)
    return np.where(dentro, 0.0, mas_cerca)


def _piso_cruce_de_diagonales(campo):
    """El cruce de las diagonales UL-DR y UR-DL del cuadrilátero (no su centroide): el centro desde el que se mide la dirección de cada esquina."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = campo
    d = (x1 - x3) * (y2 - y4) - (y1 - y3) * (x2 - x4)
    a, b = x1 * y3 - y1 * x3, x2 * y4 - y2 * x4
    return np.array([(a * (x2 - x4) - (x1 - x3) * b) / d, (a * (y2 - y4) - (y1 - y3) * b) / d])


def _piso_lejos_del_borde(binaria, radio, bordes_de_la_imagen):
    """Los píxeles de `binaria` (bool, una ventana de la película) que están a más de `radio` píxeles de todo lo que no es True. `bordes_de_la_imagen`: (izquierda, arriba, derecha, abajo),
    cuáles lados de la ventana son el borde de la IMAGEN: ahí se pone un píxel de «no película» (el borde de la imagen es un borde, A.3); los demás lados no cuentan (la película sigue más allá)."""
    izquierda, arriba, derecha, abajo = (int(b) for b in bordes_de_la_imagen)
    base = np.pad(binaria, ((arriba, abajo), (izquierda, derecha)), constant_values=False)
    lejos = cv2.distanceTransform(base.view(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) > radio
    return np.ascontiguousarray(lejos[arriba:lejos.shape[0] - abajo, izquierda:lejos.shape[1] - derecha])


def _piso_pelicula_limpia(pelicula, escala, p, margen_mm, apartar_borde, holgura_mm=0.0):
    """La regla (1): la película LIMPIA. Devuelve (limpia, componente, (x0, y0)) o el motivo (un texto) si no hay película: la máscara de película (con dato y no fondo), su componente
    conexa más grande y, de ella, lo que queda a más de `margen_mm` de todo lo que no es película y, con `apartar_borde`, también del borde de la IMAGEN (un recorte a ras corta la película en
    el borde de la imagen: el fleco del corte puede estar ahí). Ambas máscaras son de la ventana de la componente (su caja más `max(margen_mm, holgura_mm)` hacia afuera), con su esquina
    superior izquierda en (x0, y0) de la película; `componente` es la componente sin erosionar."""
    pel = _piso_mascara_de_pelicula(pelicula, p["umbral_fondo"])
    cuantas, etiquetas, estadisticas, _ = cv2.connectedComponentsWithStats(pel.view(np.uint8), connectivity=8)
    if cuantas < 2:
        return MOTIVO_SIN_PELICULA
    k = 1 + int(np.argmax(estadisticas[1:, cv2.CC_STAT_AREA]))
    x, y, ancho_c, alto_c = (int(v) for v in estadisticas[k, :4])
    alto, ancho = pel.shape
    radio = margen_mm / escala
    margen = int(np.ceil(max(radio, holgura_mm / escala))) + 2
    x0, y0, x1, y1 = max(0, x - margen), max(0, y - margen), min(ancho, x + ancho_c + margen), min(alto, y + alto_c + margen)
    componente = etiquetas[y0:y1, x0:x1] == k
    del etiquetas, pel
    bordes = (x0 == 0, y0 == 0, x1 == ancho, y1 == alto) if apartar_borde else (False, False, False, False)
    return _piso_lejos_del_borde(componente, radio, bordes), componente, (x0, y0)


def _piso_candidatos_por_esquina(campo, escala, p, limpia, origen):
    """Para cada esquina, los píxeles de película limpia de SU CUÑA (aquellos cuyo punto más cercano del cuadrilátero convexo es ese vértice: `(p - C_k)·(C_k+1 - C_k) <= 0` y `(p - C_k)·(C_k -
    C_k-1) >= 0`) a más de `margen_campo_mm` del campo: [(ys, xs, distancia en mm)] en el orden de lectura de la imagen. Por bloques de filas: ni cuatro arreglos de la página entera."""
    ox, oy = origen
    n = len(ESQUINAS)
    filas = np.flatnonzero(limpia.any(axis=1))
    acumulado = [([], [], []) for _ in range(n)]
    if len(filas):
        ultima = int(filas[-1]) + 1
        for f0 in range(int(filas[0]), ultima, FILAS_POR_BLOQUE):
            ys_b, xs_b = np.nonzero(limpia[f0:min(ultima, f0 + FILAS_POR_BLOQUE)])
            if not len(ys_b):
                continue
            ys_b, xs_b = ys_b + (f0 + oy), xs_b + ox
            fx, fy = xs_b.astype(np.float64), ys_b.astype(np.float64)
            for k in range(n):
                vertice = campo[k]
                siguiente = campo[(k + 1) % n] - vertice
                anterior = vertice - campo[(k - 1) % n]
                px, py = fx - vertice[0], fy - vertice[1]
                en_cuna = (px * siguiente[0] + py * siguiente[1] <= 0) & (px * anterior[0] + py * anterior[1] >= 0)
                distancia = np.hypot(px, py) * escala
                elegible = en_cuna & (distancia > p["margen_campo_mm"])
                acumulado[k][0].append(ys_b[elegible])
                acumulado[k][1].append(xs_b[elegible])
                acumulado[k][2].append(distancia[elegible])
    vacio = np.empty(0, np.int64)
    return [(np.concatenate(ys) if ys else vacio, np.concatenate(xs) if xs else vacio, np.concatenate(d) if d else np.empty(0)) for ys, xs, d in acumulado]


def _piso_conjunto_de_una_esquina(pelicula, ys, xs, distancia, p):
    """El conjunto de píxeles de una esquina (regla 2 de A.3): de su cuña se aparta la TINTA (regla 3, contra la mediana de ESA cuña) y de lo que queda se toma el `fraccion_lejana` más
    lejano del vértice o, si eso son menos de `pixeles_minimos`, los `pixeles_minimos` más lejanos. Si la cuña sin tinta tiene menos de `pixeles_minimos`, el conjunto es la cuña entera
    (y la comprobación de la esquina la hará fallar)."""
    if len(ys):
        quedan = _piso_sin_tinta(pelicula, ys, xs, p["delta_tinta"])
        ys, xs, distancia = ys[quedan], xs[quedan], distancia[quedan]
    if len(ys) >= p["pixeles_minimos"]:
        corte = np.quantile(distancia, 1.0 - p["fraccion_lejana"])
        elegidos = distancia >= corte
        if elegidos.sum() < p["pixeles_minimos"]:
            elegidos = np.zeros(len(distancia), bool)
            elegidos[np.argsort(distancia, kind="stable")[-int(p["pixeles_minimos"]):]] = True
        ys, xs = ys[elegidos], xs[elegidos]
    return ys, xs


def _piso_medidas(pelicula, ys, xs, p):
    """n, la fracción de píxeles que parecen fondo y, por capa (R, G, B y gris), la mediana y el IQR de los píxeles (ys, xs). Sin píxeles, solo n."""
    medidas = {"n": int(len(ys)), "fraccion_fondo": 0.0, "medianas": None, "iqr": None}
    if not len(ys):
        return medidas
    medidas["fraccion_fondo"] = _piso_fraccion_como_fondo(pelicula, ys, xs, p["umbral_como_fondo"])
    medianas, iqr = {}, {}
    for c in CAPAS_DEL_PISO:
        q1, q2, q3 = np.percentile(getattr(pelicula, c)[ys, xs], [25, 50, 75])
        medianas[c], iqr[c] = float(q2), float(q3 - q1)
    medidas["medianas"], medidas["iqr"] = medianas, iqr
    return medidas


def _piso_fuera_del_rango(medianas, rango):
    """['rojo 152 fuera de [60, 140]', ...]: las capas cuya mediana no cae en su rango (los límites son inclusivos)."""
    return [f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {_cifra(medianas[c])} fuera de [{rango[c][0]:g}, {rango[c][1]:g}]" for c in CAPAS_DEL_PISO if not rango[c][0] <= medianas[c] <= rango[c][1]]


def _piso_motivo_de_una_parte(medidas, p):
    """Por qué una parte (una esquina o la ventana de un respaldo) no sirve, o «» si sirve. El primer motivo que aparece es el de la parte: (i) píxeles suficientes, (ii) que no parezca el fondo
    del escáner (regla 7), (iii) IQR, (iv) las cuatro medianas en el rango esperado."""
    if medidas["n"] < p["pixeles_minimos"]:
        return f"sin película suficiente ({medidas['n']} píxeles)"
    if medidas["fraccion_fondo"] >= p["fraccion_como_fondo"]:
        return f"como el fondo del escáner ({100 * medidas['fraccion_fondo']:.0f} %)"
    dispersas = [f"del {_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {_cifra(medidas['iqr'][c])}" for c in CAPAS_DEL_PISO if medidas["iqr"][c] > p["iqr_maximo"]]
    if dispersas:
        return f"dispersa (IQR {_unir_con_y(dispersas)} > {p['iqr_maximo']:g})"
    fuera = _piso_fuera_del_rango(medidas["medianas"], p["piso_esperado"])
    if fuera:
        return "fuera del rango esperado: " + ", ".join(fuera)
    return ""


def _piso_esquina(nombre, estado, motivo, origen, ys, xs, medidas, campo, escala, respaldos=()):
    """El informe de una esquina sobre la parte (ys, xs) que se usó (o, si no hay parte, la que falló)."""
    caja = distancia = None
    if len(ys):
        caja = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        distancia = float(_piso_distancia_a_los_lados(campo, xs.astype(np.float64), ys.astype(np.float64)).mean() * escala)
    return EsquinaDelPiso(nombre, estado, motivo, origen, medidas["n"], medidas["medianas"], medidas["iqr"], distancia, caja, tuple(respaldos))


def _piso_candidatos_de_respaldo(campo, k, p):
    """Los seis candidatos del respaldo de la esquina k, en el orden fijo del diseño: giro +g, giro -g, lateral s1 del lado k, lateral s1 del lado k-1, lateral s2 del lado k, lateral s2 del
    lado k-1. [(nombre, ("giro", u) | ("lateral", j, t))]. El «+» del giro es la rotación de la dirección de la esquina (desde el cruce de diagonales) que se acerca a la esquina SIGUIENTE
    (UL -> UR -> DR -> DL); el lateral s del lado k (de C_k a C_k+1) es el punto t = s / 2 y el del lado k-1 (de C_k-1 a C_k), t = 1 - s / 2. Nunca entra a la zona prohibida (s mayor que
    el mayor de `s_respaldo` ni giros de más de `giro_respaldo_grados`)."""
    n = len(ESQUINAS)
    centro = _piso_cruce_de_diagonales(campo)
    u0 = (campo[k] - centro) / np.hypot(*(campo[k] - centro))
    hacia_la_siguiente = campo[(k + 1) % n] - centro
    g = np.radians(p["giro_respaldo_grados"])
    a = np.array([u0[0] * np.cos(g) - u0[1] * np.sin(g), u0[0] * np.sin(g) + u0[1] * np.cos(g)])
    b = np.array([u0[0] * np.cos(-g) - u0[1] * np.sin(-g), u0[0] * np.sin(-g) + u0[1] * np.cos(-g)])
    mas, menos = (a, b) if np.dot(a, hacia_la_siguiente) > np.dot(b, hacia_la_siguiente) else (b, a)
    candidatos = [(f"giro {p['giro_respaldo_grados']:+g} grados", ("giro", mas)), (f"giro {-p['giro_respaldo_grados']:+g} grados", ("giro", menos))]
    for s in p["s_respaldo"]:
        for j, t in ((k, s / 2), ((k - 1) % n, 1 - s / 2)):
            candidatos.append((f"lateral s={s:g} del lado {ESQUINAS[j]}-{ESQUINAS[(j + 1) % n]}", ("lateral", j, t)))
    return candidatos


def _piso_distancias_de_respaldo(p):
    """De `distancia_respaldo_maxima_mm` hacia el campo, de `paso_respaldo_mm` en `paso_respaldo_mm`, hasta que la ventana quepa a más de `margen_campo_mm` (su centro a `margen_campo_mm`
    más la mitad de su lado)."""
    minima = p["margen_campo_mm"] + p["lado_punto_manual_mm"] / 2.0
    distancias, d = [], p["distancia_respaldo_maxima_mm"]
    while d >= minima - 1e-9:
        distancias.append(round(d, 6))
        d -= p["paso_respaldo_mm"]
    return distancias


def _piso_centro_de_un_respaldo(campo, escala, centro, definicion, d_mm):
    """El centro (x, y) de la ventana de un candidato a `d_mm` del campo: sobre el rayo del giro (bisección) o junto al punto del lado (la normal exterior por la distancia)."""
    if definicion[0] == "giro":
        u = definicion[1]
        bajo, alto = 0.0, 4.0 * float(np.hypot(*(campo[0] - campo[2])))
        for _ in range(ITERACIONES_DE_LA_BISECCION):
            medio = (bajo + alto) / 2
            q = centro + medio * u
            if float(_piso_distancia_a_los_lados(campo, q[0], q[1])) * escala < d_mm:
                bajo = medio
            else:
                alto = medio
        cx, cy = centro + alto * u
        return float(cx), float(cy)
    _, j, t = definicion
    n = len(ESQUINAS)
    lado = campo[(j + 1) % n] - campo[j]
    normal = np.array([lado[1], -lado[0]]) / np.hypot(*lado)
    if np.dot((campo[j] + campo[(j + 1) % n]) / 2 - centro, normal) < 0:
        normal = -normal
    cx, cy = campo[j] + t * lado + normal * (d_mm / escala)
    return float(cx), float(cy)


def _piso_ventana_de_respaldo(limpia, origen, campo, escala, p, cx, cy):
    """Los píxeles (ys, xs) de la ventana cuadrada de `lado_punto_manual_mm` centrada en (cx, cy) que son película limpia y están a más de `margen_campo_mm` del campo, o None si son menos de
    `pixeles_minimos` (la película no deja poner la ventana ahí)."""
    ox, oy = origen
    media = p["lado_punto_manual_mm"] / 2.0 / escala
    alto, ancho = limpia.shape
    x0, x1 = max(0, int(np.floor(cx - media)) - ox), min(ancho, int(np.ceil(cx + media)) + 1 - ox)
    y0, y1 = max(0, int(np.floor(cy - media)) - oy), min(alto, int(np.ceil(cy + media)) + 1 - oy)
    if x1 <= x0 or y1 <= y0:
        return None
    columnas, filas = (np.arange(x0, x1) + ox)[None, :], (np.arange(y0, y1) + oy)[:, None]
    cuadrado = (np.abs(columnas - cx) <= media) & (np.abs(filas - cy) <= media) & limpia[y0:y1, x0:x1]
    ys, xs = np.nonzero(cuadrado)
    ys, xs = ys + (y0 + oy), xs + (x0 + ox)
    lejos = _piso_distancia_a_los_lados(campo, xs.astype(np.float64), ys.astype(np.float64)) * escala > p["margen_campo_mm"]
    if int(lejos.sum()) < p["pixeles_minimos"]:
        return None
    return ys[lejos], xs[lejos]


def _piso_probar_respaldos(pelicula, campo, escala, p, limpia, origen, k):
    """La secuencia de respaldos de la esquina k: (intentos, (ys, xs) del primero que pasa o None, su nombre o None). Cada candidato se pone a la MAYOR distancia del campo en que la película deja
    poner su ventana; después de la tinta se le piden las mismas comprobaciones que a una esquina."""
    centro = _piso_cruce_de_diagonales(campo)
    distancias = _piso_distancias_de_respaldo(p)
    intentos = []
    for nombre, definicion in _piso_candidatos_de_respaldo(campo, k, p):
        puesta = None
        for d in distancias:
            cx, cy = _piso_centro_de_un_respaldo(campo, escala, centro, definicion, d)
            ventana = _piso_ventana_de_respaldo(limpia, origen, campo, escala, p, cx, cy)
            if ventana is not None:
                puesta = (d, cx, cy, ventana)
                break
        if puesta is None:
            intentos.append(IntentoDeRespaldo(nombre, "sin lugar", f"sin lugar: la película no deja poner la ventana a más de {p['margen_campo_mm']:g} mm del campo"))
            continue
        d, cx, cy, (ys, xs) = puesta
        quedan = _piso_sin_tinta(pelicula, ys, xs, p["delta_tinta"])
        ys, xs = ys[quedan], xs[quedan]
        medidas = _piso_medidas(pelicula, ys, xs, p)
        motivo = _piso_motivo_de_una_parte(medidas, p)
        intentos.append(IntentoDeRespaldo(nombre, "ok" if not motivo else "falla", motivo, float(d), (cx, cy), medidas["n"], medidas["medianas"]))
        if not motivo:
            return intentos, (ys, xs), nombre
    return intentos, None, None


def _piso_region_automatica(pelicula, campo, escala, p):
    """La región del piso sin que nadie marque nada, POR ESQUINAS (A.3, diseño §3): (resultado, esquinas). `resultado` es (ys, xs, distancias en mm) en coordenadas de la película, o el motivo de
    «no medible» (un texto); `esquinas`, el informe de las cuatro (() si no se llegó a mirarlas). Las reglas, en orden: (1) película limpia; (2) el conjunto de cada esquina; (3) píxeles
    suficientes en total; (4) la regla (7) sobre la UNIÓN de los cuatro conjuntos; (4 bis) que el campo luminoso esté sobre la película (que haya meseta): si no, `MOTIVO_SIN_MESETA`
    y ninguna esquina se juzga, porque las cuñas se construyen desde el campo y sin meseta ningún modo da número (decisión de Opus del 13-10, vetable por el físico); (5) cada
    esquina; (6) dos o más esquinas que fallan: sin respaldos, «no medible»; (7) una esquina que
    falla: sus respaldos, y si ninguno sirve se quita y el piso sale de las otras; el piso es la unión de lo válido."""
    limpieza = _piso_pelicula_limpia(pelicula, escala, p, p["margen_borde_mm"], p["apartar_borde_de_la_imagen"])
    if isinstance(limpieza, str):
        return limpieza, ()
    limpia, _, origen = limpieza
    n = len(ESQUINAS)
    candidatos = _piso_candidatos_por_esquina(campo, escala, p, limpia, origen)
    conjuntos = [_piso_conjunto_de_una_esquina(pelicula, ys, xs, d, p) for ys, xs, d in candidatos]
    del candidatos
    medidas = [_piso_medidas(pelicula, ys, xs, p) for ys, xs in conjuntos]

    def informe(estados, motivos=None, intentos=None):
        return tuple(_piso_esquina(ESQUINAS[k], estados[k], "" if motivos is None else motivos[k], "esquina", conjuntos[k][0], conjuntos[k][1], medidas[k], campo, escala,
                                   () if intentos is None else intentos.get(k, ())) for k in range(n))

    if sum(m["n"] for m in medidas) < p["pixeles_minimos"]:
        return MOTIVO_SIN_PISO, informe(["sin comprobar"] * n)
    ys_u, xs_u = np.concatenate([c[0] for c in conjuntos]), np.concatenate([c[1] for c in conjuntos])
    como_fondo = _piso_fraccion_como_fondo(pelicula, ys_u, xs_u, p["umbral_como_fondo"])
    if como_fondo >= p["fraccion_como_fondo"]:
        return _piso_motivo_como_el_fondo(como_fondo, p), informe(["sin comprobar"] * n)
    if _piso_meseta_de_referencia(pelicula, campo, escala, p) is None:
        return MOTIVO_SIN_MESETA, informe(["sin comprobar"] * n)
    motivos = [_piso_motivo_de_una_parte(m, p) for m in medidas]
    fallan = [k for k in range(n) if motivos[k]]
    if len(fallan) > n - p["esquinas_minimas"]:
        esquinas = informe(["falla" if motivos[k] else "ok" for k in range(n)], motivos)
        if all(medidas[k]["n"] < p["pixeles_minimos"] for k in fallan):
            cuales = "; ".join(f"{NOMBRE_DE_ESQUINA[ESQUINAS[k]]}: {medidas[k]['n']} píxeles" for k in fallan)
            return (f"{MOTIVO_ESQUINAS_SIN_PELICULA} ({cuales}; hacen falta {p['pixeles_minimos']:g} a más de {p['margen_campo_mm']:g} mm del campo en cada una): "
                    f"escanee la película entera, con su margen, o use la película virgen o marque un punto sin irradiar"), esquinas
        cuales = "; ".join(f"{NOMBRE_DE_ESQUINA[ESQUINAS[k]]}: {motivos[k]}" for k in fallan)
        return (f"{MOTIVO_ESQUINAS_SIN_PISO} ({cuales}): no es un defecto de una sola esquina; revise el escaneo o use la película virgen o marque un punto sin irradiar"), esquinas
    partes = {k: conjuntos[k] for k in range(n) if not motivos[k]}
    esquinas = {k: _piso_esquina(ESQUINAS[k], "ok", "", "esquina", conjuntos[k][0], conjuntos[k][1], medidas[k], campo, escala) for k in partes}
    for k in fallan:
        intentos, parte, nombre = _piso_probar_respaldos(pelicula, campo, escala, p, limpia, origen, k)
        if parte is None:
            esquinas[k] = _piso_esquina(ESQUINAS[k], "sin piso", motivos[k], "esquina", conjuntos[k][0], conjuntos[k][1], medidas[k], campo, escala, intentos)
        else:
            partes[k] = parte
            esquinas[k] = _piso_esquina(ESQUINAS[k], "reemplazada", motivos[k], nombre, parte[0], parte[1], _piso_medidas(pelicula, parte[0], parte[1], p), campo, escala, intentos)
    ys_u, xs_u = np.concatenate([partes[k][0] for k in sorted(partes)]), np.concatenate([partes[k][1] for k in sorted(partes)])
    y0, x0 = int(ys_u.min()), int(xs_u.min())
    unica = np.zeros((int(ys_u.max()) - y0 + 1, int(xs_u.max()) - x0 + 1), bool)
    unica[ys_u - y0, xs_u - x0] = True
    ys, xs = np.nonzero(unica)
    ys, xs = ys + y0, xs + x0
    distancias = _piso_distancia_a_los_lados(campo, xs.astype(np.float64), ys.astype(np.float64)) * escala
    return (ys, xs, distancias), tuple(esquinas[k] for k in range(n))


def _piso_motivo_como_el_fondo(fraccion, p):
    """El `estado` de la regla (7): el motivo, el porcentaje de píxeles del piso que llega al umbral y qué revisar."""
    return (f"{MOTIVO_PISO_COMO_EL_FONDO} (el {100 * fraccion:.0f} % de sus píxeles llega a {p['umbral_como_fondo']:g} niveles hasta en su capa más oscura): "
            f"revise la tapa y el vidrio del escáner y que el escaneo no lleve ajustes de brillo")


def _piso_region_manual(pelicula, campo, escala, p, punto):
    """La región del sexto clic: el cuadrado de `lado_punto_manual_mm` centrado en el punto, solo con película (con dato, no fondo, y a más de `margen_borde_mm` del borde de la
    película y, con `apartar_borde_de_la_imagen`, también del borde de la imagen), sin tinta. Devuelve (ys, xs, distancias en mm) o el motivo de «no medible». No pide la componente
    conexa más grande: el trozo sin irradiar es otro pedazo."""
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
    bordes = (x0 == 0, y0 == 0, x1 == ancho, y1 == alto) if p["apartar_borde_de_la_imagen"] else (False, False, False, False)
    lejos_del_borde = _piso_lejos_del_borde(pel, radio, bordes)
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


def _piso_medidas_de_la_region(pelicula, ys, xs):
    """{capa: (mediana, n, IQR)} de los píxeles (ys, xs), en las cuatro capas (R, G, B y gris)."""
    n = int(len(ys))
    salida = {}
    for c in CAPAS_DEL_PISO:
        valores = getattr(pelicula, c)[ys, xs]
        q1, q3 = np.percentile(valores, [25, 75])
        salida[c] = (float(np.median(valores)), n, float(q3 - q1))
    return salida


def _piso_capas(pelicula, campo, escala, p, medidas):
    """Las cuatro `CapaDelPiso` con la comprobación de coherencia (regla 5): `medidas` = {capa: (mediana, n, IQR)} y la meseta de ESTA película; la capa cuyo piso no es más claro que la
    meseta en `contraste_minimo` niveles es «no medible» y las demás siguen. None si la película no cubre el campo (no hay meseta)."""
    meseta = _piso_meseta_de_referencia(pelicula, campo, escala, p)
    if meseta is None:
        return None
    capas = {}
    for c in CAPAS_DEL_PISO:
        mediana, n, iqr = medidas[c]
        contraste = mediana - meseta[c]
        if contraste < p["contraste_minimo"]:
            motivo = (f"no medible: el piso de la capa {_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} no es más claro que la meseta en al menos {p['contraste_minimo']:g} niveles "
                      f"(piso {mediana:.1f}, meseta {meseta[c]:.1f})")
            capas[c] = CapaDelPiso(c, motivo, None, n, None, meseta[c], contraste)
            continue
        capas[c] = CapaDelPiso(c, "ok", mediana, n, iqr, meseta[c], contraste)
    return capas


def _piso_resultado(pelicula, campo, campo_texto, escala, p, origen, ys, xs, distancias_mm, rango, esquinas=(), punto=None):
    """De los píxeles de la región al `Piso`: la regla (7) (el piso no puede parecerse al fondo del escáner), el rango esperado (A.3: `rango` = (clave del parámetro, motivo, qué hacer)), la meseta
    de referencia, la mediana y el IQR de cada capa y la comprobación de coherencia. La regla (7) va primero: un piso del vacío es MÁS claro que la meseta, y la comprobación de la regla (5)
    no lo ve; el rango hace falta porque un fondo neutro por debajo de `umbral_como_fondo` no lo ve ninguna de las dos. En el automático la meseta ya se comprobó antes de
    juzgar las esquinas (`_piso_region_automatica`) y aquí siempre la hay; con el sexto clic el rango se dice antes que la falta de meseta porque depende del punto y no del
    campo (`test_j_el_rango_del_punto_va_antes_que_la_meseta`)."""
    como_fondo = _piso_fraccion_como_fondo(pelicula, ys, xs, p["umbral_como_fondo"])
    if como_fondo >= p["fraccion_como_fondo"]:
        return _piso_sin_numero(_piso_motivo_como_el_fondo(como_fondo, p), origen, campo_texto, escala, p, esquinas=esquinas, punto=punto)
    medidas = _piso_medidas_de_la_region(pelicula, ys, xs)
    clave, motivo_del_rango, que_hacer = rango
    fuera = _piso_fuera_del_rango({c: m[0] for c, m in medidas.items()}, p[clave])
    if fuera:
        return _piso_sin_numero(f"{motivo_del_rango} ({', '.join(fuera)}): {que_hacer}", origen, campo_texto, escala, p, esquinas=esquinas, punto=punto)
    capas = _piso_capas(pelicula, campo, escala, p, medidas)
    if capas is None:
        return _piso_sin_numero(MOTIVO_SIN_MESETA, origen, campo_texto, escala, p, esquinas=esquinas, punto=punto)
    n = int(len(ys))
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    mascara = np.zeros((y1 - y0, x1 - x0), bool)
    mascara[ys - y0, xs - x0] = True
    mascara.setflags(write=False)
    region = RegionDelPiso(origen, (x0, y0, x1, y1), mascara, n, float(distancias_mm.mean()), float(distancias_mm.min()), float(distancias_mm.max()))
    return Piso("ok", origen, capas, region, escala, campo_texto, dict(p), esquinas=esquinas, punto=punto)


def _piso_medir_automatico(pelicula, campo, campo_texto, escala, p):
    """El piso automático (por esquinas) de la película: el modo «automatico» y, en el modo «virgen», la comparación."""
    region, esquinas = _piso_region_automatica(pelicula, campo, escala, p)
    if isinstance(region, str):
        return _piso_sin_numero(region, "automatico", campo_texto, escala, p, esquinas=esquinas)
    ys, xs, distancias_mm = region
    return _piso_resultado(pelicula, campo, campo_texto, escala, p, "automatico", ys, xs, distancias_mm, _RANGO_DEL_PISO_AUTOMATICO, esquinas)


def _piso_parametros(P):
    """Los parámetros del piso con que se mide: los de fábrica y, encima, los de `P` (una COPIA con la forma de JSON: listas, nunca tuplas)."""
    p = {nombre: _json_normal(valor) for nombre, valor in VALORES_DEL_PISO.items()}
    p.update({nombre: _json_normal(P[nombre]) for nombre in VALORES_DEL_PISO if nombre in P})
    return p


def _piso_validar_la_llamada(modo, punto, referencia_virgen):
    """`ValueError` si la forma de llamar es equivocada: un modo que no existe, un punto sin el modo «punto_manual» (o al revés) o una referencia que no es una `ReferenciaVirgen`."""
    if modo not in MODOS_DEL_PISO:
        raise ValueError(f"El modo del piso debe ser uno de {', '.join(MODOS_DEL_PISO)}, no {modo!r}.")
    if modo == "punto_manual" and punto is None:
        raise ValueError("El modo «punto_manual» necesita el punto marcado (punto_manual=(x, y)).")
    if modo != "punto_manual" and punto is not None:
        raise ValueError(f"Con el modo {modo!r} no se da un punto marcado: el punto es del modo «punto_manual».")
    if referencia_virgen is not None and not isinstance(referencia_virgen, ReferenciaVirgen):
        raise ValueError("La referencia de la película virgen debe ser una ReferenciaVirgen (la de piso_de_pelicula_virgen o la de leer_referencia_virgen).")


def _piso_con_virgen(pelicula, campo, campo_texto, escala, P, p, referencia):
    """El modo «virgen»: el piso es el de la película virgen de referencia, contra la meseta de ESTA película, con la comparación (solo informativa) con el piso automático de la misma
    película. Sin referencia o con una que no sirve, «no medible»: NUNCA cae al automático."""
    def sin_numero(motivo, **extra):
        return _piso_sin_numero(motivo, "virgen", campo_texto, escala, p, referencia=referencia, **extra)

    if referencia is None:
        return sin_numero(MOTIVO_SIN_REFERENCIA_VIRGEN + ": cárguela con «Película virgen...»")
    if referencia.estado != "ok":
        return sin_numero(f"{MOTIVO_REFERENCIA_VIRGEN_NO_VALIDA}: {referencia.estado.removeprefix(PREFIJO_NO_VALIDA)}")
    procedencia = referencia.procedencia
    if procedencia.get("bits") != pelicula.bits:
        return sin_numero(f"{MOTIVO_VIRGEN_OTRA_CADENA} ({procedencia.get('bits')} bits contra {pelicula.bits}): escanéela con el mismo escáner, la misma resolución y los mismos bits "
                          f"que la película irradiada")
    automatico = _piso_medir_automatico(pelicula, campo, campo_texto, escala, p)
    avisos = []
    if automatico.estado == "ok":
        diferencias = {c: referencia.valor(c) - automatico.capas[c].mediana for c in CAPAS_DEL_PISO}
        mas_oscuras = [f"en el {_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} ({_con_signo(diferencias[c])} niveles)" for c in CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS
                       if diferencias[c] < -p["tolerancia_virgen_mas_oscura"]]
        if mas_oscuras:
            return sin_numero(f"{MOTIVO_VIRGEN_MAS_OSCURA} {' y '.join(mas_oscuras)}: una película virgen no puede tener más dosis que la película irradiada de fuera del campo "
                              f"(¿otro lote, otra sesión de escaneo, o no es virgen?)", comparacion=automatico)
        if abs(diferencias["B"]) > p["aviso_azul_virgen"]:
            avisos.append(f"El azul de la película virgen difiere {_con_signo(diferencias['B'])} niveles del piso automático de esta película (más de {p['aviso_azul_virgen']:g}): puede ser "
                          f"otro lote u otra cadena de escaneo.")
        if diferencias["G"] > p["aviso_verde_virgen"]:
            avisos.append(f"El verde de la película virgen está {_cifra(diferencias['G'])} niveles más claro que el piso automático de esta película (más de {p['aviso_verde_virgen']:g}): "
                          f"la diferencia es mayor que la esperada.")
    else:
        avisos.append(f"La película virgen se usa sin comparar: no se pudo comparar con el piso automático de esta película ({automatico.estado}).")
    if (pelicula.formato == "JPEG") != (procedencia.get("formato") == "JPEG"):
        avisos.append(f"La película es un {pelicula.formato or 'archivo sin formato'} y la virgen un {procedencia.get('formato') or 'archivo sin formato'}: la compresión del JPEG cambia unos "
                      f"niveles; compárelas escaneadas de la misma forma.")
    clase_de_la_pelicula = clase_resolucion(getattr(pelicula, "dpi", None), P)
    if clase_de_la_pelicula != procedencia.get("clase_resolucion"):
        avisos.append(f"La resolución declarada de la película ({clase_de_la_pelicula}) y la de la virgen ({procedencia.get('clase_resolucion')}) son de clases distintas: compruebe que "
                      f"se escanearon a la misma resolución.")
    medidas = {c: (referencia.capas[c].mediana, referencia.capas[c].n, referencia.capas[c].iqr) for c in CAPAS_DEL_PISO}
    capas = _piso_capas(pelicula, campo, escala, p, medidas)
    if capas is None:
        return sin_numero(MOTIVO_SIN_MESETA, comparacion=automatico)
    return Piso("ok", "virgen", capas, None, escala, campo_texto, dict(p), referencia=referencia, comparacion=automatico, avisos=tuple(avisos))


def piso_de_pelicula(pelicula, campo_luz, P, punto_manual=None, modo=None, referencia_virgen=None):
    """El piso de una película: el nivel de la película FUERA del campo luminoso, por capa (R, G, B y gris), con de dónde salió y a qué distancia del campo. Las reglas, el contrato de las
    entradas y lo que significa «no medible» están en el docstring del módulo. `P`: la escala del procedimiento (`CLAVES_DE_LA_ESCALA`) y, si se quieren cambiar, los parámetros del piso
    (`VALORES_DEL_PISO`; los que falten se ponen de fábrica y los usados quedan en `Piso.parametros`).

    A.3: `modo` («automatico», «punto_manual» o «virgen»; None = «punto_manual» si hay un `punto_manual` y, si no, `MODO_DEL_PISO_POR_OMISION`): cómo se toma el piso. El automático es por
    esquinas, con un rango esperado y un respaldo junto a la esquina; «punto_manual» es el sexto clic (un cuadrado de 3 × 3 mm sobre película sin irradiar); «virgen» es el de la película virgen
    de `referencia_virgen` (una `ReferenciaVirgen`), sin referencia «no medible» (nunca cae al automático). `ValueError` solo si los argumentos tienen una forma equivocada (el campo no son
    4 puntos, el punto no es (x, y), `P` sin la escala, un modo que no existe, un punto con un modo que no es «punto_manual», una referencia que no es una `ReferenciaVirgen`)."""
    P = {} if P is None else P
    faltan = [k for k in CLAVES_DE_LA_ESCALA if k not in P]
    if faltan:
        raise ValueError(f"P debe traer la escala del procedimiento: faltan {', '.join(faltan)}.")
    p = _piso_parametros(P)
    campo, crudos = _piso_cuadrilatero(campo_luz)
    punto = None if punto_manual is None else _piso_punto(punto_manual)
    if modo is None:
        modo = "punto_manual" if punto is not None else MODO_DEL_PISO_POR_OMISION
    _piso_validar_la_llamada(modo, punto, referencia_virgen)
    origen = ORIGEN_DE_MODO[modo]
    dpi = getattr(pelicula, "dpi", None)
    escala = escala_mm(dpi, P)
    campo_texto = tuple((float(x), float(y)) for x, y in (crudos if campo is None else campo))
    extra = {} if punto is None else {"punto": punto}
    if modo == "virgen":
        extra["referencia"] = referencia_virgen
    if campo is None:
        return _piso_sin_numero(MOTIVO_CAMPO_INVALIDO, origen, campo_texto, escala, p, **extra)
    if escala is None:
        motivo = (f"no medible: la película se escaneó a otra resolución ({dpi:g} dpi) y sin la escala del procedimiento ({P['resolucion_escaneo_dpi']:g} dpi) "
                  f"no hay milímetros con que tomar el piso")
        return _piso_sin_numero(motivo, origen, campo_texto, escala, p, **extra)
    if modo == "virgen":
        return _piso_con_virgen(pelicula, campo, campo_texto, escala, P, p, referencia_virgen)
    if modo == "automatico":
        return _piso_medir_automatico(pelicula, campo, campo_texto, escala, p)
    region = _piso_region_manual(pelicula, campo, escala, p, punto)
    if isinstance(region, str):
        return _piso_sin_numero(region, origen, campo_texto, escala, p, punto=punto)
    ys, xs, distancias_mm = region
    return _piso_resultado(pelicula, campo, campo_texto, escala, p, origen, ys, xs, distancias_mm, _RANGO_DEL_PUNTO_MARCADO, punto=punto)


# ============================================================================= A.3: la película virgen (el piso medido en el escaneo de una película sin irradiar)

# La tabla de luminancia estándar de JPEG (calidad 50, la de la Tabla K.1 del estándar): la calidad que se estima de un archivo es la escala entre su tabla y esta. Vive aquí, fuera de
# las funciones, porque son números del estándar y no parámetros del piso.
TABLA_DE_LUMINANCIA_JPEG = (16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
                            18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99)
SUBMUESTREO_DE_JPEG = {0: "4:4:4", 1: "4:2:2", 2: "4:2:0"}
FRACCION_MINIMA_DE_PERFIL = 0.5                           # de las columnas (o filas) de la zona medida solo cuentan las que cubren la mitad o más de lo que cubre la que más
VENTANAS_MINIMAS_DEL_PERFIL = 3                           # un perfil más corto que 3 ventanas de la media móvil no se juzga
EXTENSIONES_DE_ESCANEO = {".tif": ".tif", ".tiff": ".tiff", ".jpg": ".jpg", ".jpeg": ".jpeg", ".png": ".png"}
EXTENSION_POR_FORMATO = {"TIFF": ".tif", "JPEG": ".jpg", "PNG": ".png"}


def _jpeg_calidad_y_submuestreo(imagen_pil):
    """(calidad IJG estimada, submuestreo de croma) de un JPEG, o (None, None) si no lo es. La calidad sale de la tabla de luminancia (la escala contra la estándar); el submuestreo, de Pillow."""
    tablas = getattr(imagen_pil, "quantization", None)
    if not tablas:
        return None, None
    tabla = np.array(sorted(tablas.items())[0][1], float)                 # la suma no depende del orden en que Pillow entregue la tabla
    escala = 100.0 * tabla.sum() / float(sum(TABLA_DE_LUMINANCIA_JPEG))
    calidad = (200.0 - escala) / 2.0 if escala <= 100.0 else 5000.0 / escala
    try:
        from PIL import JpegImagePlugin
        submuestreo = SUBMUESTREO_DE_JPEG.get(JpegImagePlugin.get_sampling(imagen_pil), "?")
    except Exception:
        submuestreo = None
    return round(float(min(100.0, max(1.0, calidad))), 1), submuestreo


def _equipo_de_la_imagen(imagen_pil):
    """«Marca Modelo» del escáner, de las etiquetas EXIF Make (271) y Model (272), o None si el archivo no las trae."""
    try:
        exif = imagen_pil.getexif()
        partes = [str(exif.get(etiqueta)).strip() for etiqueta in (271, 272) if exif.get(etiqueta)]
    except Exception:
        return None
    return " ".join(partes) or None


def _virgen_parametros(P):
    """Los parámetros de la virgen con que se mide: los de fábrica y, encima, los de `P` (una copia con la forma de JSON)."""
    v = {nombre: _json_normal(valor) for nombre, valor in VALORES_DE_LA_VIRGEN.items()}
    v.update({nombre: _json_normal(P[nombre]) for nombre in VALORES_DE_LA_VIRGEN if nombre in P})
    return v


def _virgen_lado_impar(pixeles):
    """El lado impar más cercano (en píxeles) de una ventana de filtro."""
    lado = int(round(pixeles))
    return lado if lado % 2 else lado + 1


def _virgen_cerrar(pruebas, procedencia, parametros, valores=None, region=None):
    """Arma la `ReferenciaVirgen`: «ok» si ninguna comprobación rechazó y hay valores; si no, «no válida: » + el texto del PRIMER rechazo y ninguna capa trae número."""
    avisos = tuple(x.texto for x in pruebas if x.resultado == "aviso")
    rechazos = [x.texto for x in pruebas if x.resultado == "rechazo"]
    if rechazos or valores is None:
        estado = PREFIJO_NO_VALIDA + (rechazos[0] if rechazos else "no se pudo medir la película")
        return ReferenciaVirgen(estado, {c: CapaDelPiso(c, estado) for c in CAPAS_DEL_PISO}, tuple(pruebas), avisos, None, procedencia, parametros)
    capas = {c: CapaDelPiso(c, "ok", mediana, n, iqr, None, None) for c, (mediana, n, iqr) in valores.items()}
    return ReferenciaVirgen("ok", capas, tuple(pruebas), avisos, region, procedencia, parametros)


def _virgen_cadena(pelicula, procedencia, calidad, submuestreo, v):
    """C1, la cadena de captura (con la resolución que sí tiene escala): un archivo vuelto a guardar por un editor o un JPEG avisan; un escaneo tal como lo entrega el escáner, ok."""
    editor = procedencia["clase_resolucion"] == "editor" or (calidad is not None and submuestreo == "4:2:0" and calidad >= v["calidad_jpeg_editor"])
    if editor:
        return PruebaDeLaVirgen("C1 cadena", "aviso", "el archivo parece vuelto a guardar por un editor (resolución de editor o JPEG 4:2:0 de calidad alta): suba el archivo tal como lo "
                                                        "entrega el escáner")
    if pelicula.formato == "JPEG":
        return PruebaDeLaVirgen("C1 cadena", "aviso", f"JPEG (calidad estimada {'?' if calidad is None else _cifra(calidad)}, {submuestreo}): se recomienda TIFF sin compresión")
    return PruebaDeLaVirgen("C1 cadena", "ok", f"{pelicula.formato}, {pelicula.bits} bits, resolución {procedencia['clase_resolucion']}")


def _virgen_recorte(planos, roi, v):
    """C3, el recorte: la mayor, entre R, G y B, de las fracciones de la zona medida en 0 o en el máximo. Más de `recorte_rechazo` rechaza; más de `recorte_aviso` avisa."""
    n = float(np.count_nonzero(roi))
    recorte = max(float(np.count_nonzero(((planos[c] <= 0) | (planos[c] >= NIVEL_MAXIMO)) & roi)) / n for c in CAPAS)
    if recorte > v["recorte_rechazo"]:
        return PruebaDeLaVirgen("C3 recorte", "rechazo", f"el {100 * recorte:.2f} % de la película está recortada en 0 o en el máximo: revise la exposición y los ajustes automáticos del escáner")
    if recorte > v["recorte_aviso"]:
        return PruebaDeLaVirgen("C3 recorte", "aviso", f"el {100 * recorte:.3f} % de la película está recortada en 0 o en el máximo")
    return PruebaDeLaVirgen("C3 recorte", "ok", f"recorte {100 * recorte:.3f} %")


def _virgen_fondo(pelicula, componente, origen, escala, v):
    """C3, el fondo: (píxeles de la zona de fondo, cuántos están en el blanco máximo en las tres capas). La zona de fondo son los píxeles que no son la película a `distancia_fondo_mm` o más de ella
    y a `borde_imagen_fondo_mm` o más del borde de la imagen. La película (su componente) está toda dentro de la ventana de `componente`, que llega más allá de `distancia_fondo_mm`: lo de
    fuera de la ventana es fondo sin más. Por bloques de filas: sin arreglos de la página entera."""
    alto, ancho = pelicula.validos.shape
    ox, oy = origen
    lejos = cv2.distanceTransform((~componente).view(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * escala >= v["distancia_fondo_mm"]
    borde = int(np.ceil(v["borde_imagen_fondo_mm"] / escala))
    en_la_zona, en_blanco = 0, 0
    for f0 in range(borde, alto - borde, FILAS_POR_BLOQUE):
        f1 = min(alto - borde, f0 + FILAS_POR_BLOQUE)
        zona = np.ones((f1 - f0, ancho), bool)
        a, b = max(f0, oy), min(f1, oy + componente.shape[0])
        if b > a:
            zona[a - f0:b - f0, ox:ox + componente.shape[1]] = lejos[a - oy:b - oy]
        zona[:, :borde] = False
        zona[:, ancho - borde:] = False
        blanco = (pelicula.R[f0:f1] >= NIVEL_MAXIMO) & (pelicula.G[f0:f1] >= NIVEL_MAXIMO) & (pelicula.B[f0:f1] >= NIVEL_MAXIMO)
        en_la_zona += int(np.count_nonzero(zona))
        en_blanco += int(np.count_nonzero(zona & blanco))
    return en_la_zona, en_blanco


def _virgen_dilatar(mascara, v, escala):
    """La máscara dilatada `dilatacion_tinta_y_motas_mm` (un disco): lo que se aparta alrededor de la tinta y de las motas."""
    radio = max(1, int(round(v["dilatacion_tinta_y_motas_mm"] / escala)))
    nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radio + 1, 2 * radio + 1))
    return cv2.dilate(mascara.view(np.uint8), nucleo).astype(bool)


def _virgen_tinta(planos, roi, p, v, escala):
    """La tinta (regla 3, contra la mediana de la zona medida, en R, G o B), dilatada. Bool de la ventana."""
    tinta = np.zeros(roi.shape, bool)
    for c in CAPAS:
        tinta |= roi & (planos[c] < np.median(planos[c][roi]) - p["delta_tinta"])
    return _virgen_dilatar(tinta, v, escala)


def _virgen_ruido(planos, valida, v, escala):
    """C7, el ruido: (sigma por capa, la prueba). sigma = 1.4826 · MAD del residuo contra una media móvil de `ventana_ruido_mm`, en la zona sin tinta. Avisa si alguna supera `ruido_aviso`."""
    lado = _virgen_lado_impar(v["ventana_ruido_mm"] / escala)
    sigma = {}
    for c in CAPAS:
        residuo = (planos[c] - cv2.blur(planos[c], (lado, lado)))[valida]
        sigma[c] = float(FACTOR_MAD * np.median(np.abs(residuo - np.median(residuo))))
    altas = [f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {sigma[c]:.2f}" for c in CAPAS if sigma[c] > v["ruido_aviso"][c]]
    if altas:
        return sigma, PruebaDeLaVirgen("C7 ruido", "aviso", "ruido alto (sigma en niveles): " + ", ".join(altas))
    return sigma, PruebaDeLaVirgen("C7 ruido", "ok", "sigma " + ", ".join(f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {sigma[c]:.2f}" for c in CAPAS))


def _virgen_motas(planos, roi, tinta, sigma, v, escala):
    """C6, las motas, rayones y huellas: (la máscara de lo que se aparta, la prueba). Residuo contra la mediana móvil de `ventana_motas_mm` (la capa en 8 bits) mayor que
    max(`motas_sigmas` · sigma, `motas_niveles`), en grupos de `motas_pixeles_grupo` píxeles o más, dilatados. Avisa o rechaza según la fracción de la zona medida que cubren."""
    lado = _virgen_lado_impar(v["ventana_motas_mm"] / escala)
    candidatas = np.zeros(roi.shape, bool)
    for c in CAPAS:
        plano8 = np.clip(np.rint(planos[c]), 0, NIVEL_MAXIMO).astype(np.uint8)
        residuo = plano8.astype(np.float32) - cv2.medianBlur(plano8, lado).astype(np.float32)
        candidatas |= np.abs(residuo) > max(v["motas_sigmas"] * sigma[c], v["motas_niveles"])
    candidatas &= roi & ~tinta
    cuantos, etiquetas, estadisticas, _ = cv2.connectedComponentsWithStats(candidatas.view(np.uint8), connectivity=8)
    areas = estadisticas[:, cv2.CC_STAT_AREA]
    grandes = areas >= v["motas_pixeles_grupo"]
    grandes[0] = False                                                       # la etiqueta 0 es el fondo de la imagen de etiquetas
    mayor_mm2 = float(areas[grandes].max() if grandes.any() else 0) * escala * escala
    motas = _virgen_dilatar(grandes[etiquetas], v, escala) & roi
    fraccion = float(np.count_nonzero(motas)) / float(np.count_nonzero(roi))
    if fraccion > v["motas_rechazo_fraccion"]:
        return motas, PruebaDeLaVirgen("C6 motas", "rechazo", f"película sucia o rayada: las motas cubren el {100 * fraccion:.2f} %")
    if fraccion > v["motas_aviso_fraccion"] or mayor_mm2 > v["motas_aviso_grupo_mm2"]:
        return motas, PruebaDeLaVirgen("C6 motas", "aviso", f"motas en el {100 * fraccion:.3f} % (la mayor, {mayor_mm2:.2f} mm²); se apartan del piso")
    return motas, PruebaDeLaVirgen("C6 motas", "ok", f"motas {100 * fraccion:.3f} %")


def _virgen_valores(planos, usar, p):
    """({capa: (mediana, n, IQR)} de la zona medida sin tinta ni motas, fracción de sus píxeles que parece fondo del escáner)."""
    n = int(np.count_nonzero(usar))
    valores = {}
    for c in CAPAS_DEL_PISO:
        q1, q2, q3 = np.percentile(planos[c][usar], [25, 50, 75])
        valores[c] = (float(q2), n, float(q3 - q1))
    mas_oscura = np.minimum(np.minimum(planos["R"][usar], planos["G"][usar]), planos["B"][usar])
    return valores, float(np.mean(mas_oscura >= p["umbral_como_fondo"]))


def _virgen_rango_y_testigo(valores, como_fondo, p, v):
    """(prueba «rango», prueba «azul testigo»): la regla (7) y el rango de una película sin irradiar rechazan; el azul fuera del testigo avisa."""
    medianas = {c: valores[c][0] for c in CAPAS_DEL_PISO}
    fuera = _piso_fuera_del_rango(medianas, p["piso_esperado_sin_irradiar"])
    partes = []
    if como_fondo >= p["fraccion_como_fondo"]:
        partes.append(f"es tan clara como el fondo del escáner (el {100 * como_fondo:.0f} % de sus píxeles llega a {p['umbral_como_fondo']:g} niveles hasta en su capa más oscura)")
    if fuera:
        partes.append("fuera del rango esperado de una película sin irradiar: " + ", ".join(fuera))
    if partes:
        rango = PruebaDeLaVirgen("rango", "rechazo", "; ".join(partes))
    else:
        rango = PruebaDeLaVirgen("rango", "ok", "dentro del rango: " + ", ".join(f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {_cifra(medianas[c])}" for c in CAPAS_DEL_PISO))
    azul, (bajo, alto) = medianas["B"], v["azul_testigo"]
    if bajo <= azul <= alto:
        return rango, PruebaDeLaVirgen("azul testigo", "ok", f"azul {_cifra(azul)}")
    return rango, PruebaDeLaVirgen("azul testigo", "aviso", f"azul {_cifra(azul)} fuera de [{bajo:g}, {alto:g}]: ¿otro lote u otra cadena de escaneo?")


def _virgen_bloques(planos, roi, usar, v, escala):
    """Los bloques de `lado_bloque_virgen_mm` ENTEROS dentro de la zona medida, desde la esquina superior izquierda de su caja: [{x_mm, y_mm, capa: media recortada}]. La media de un bloque
    descarta lo que está a más de 3 sigmas robustas de su mediana."""
    lado = int(round(v["lado_bloque_virgen_mm"] / escala))
    filas, columnas = np.flatnonzero(usar.any(axis=1)), np.flatnonzero(usar.any(axis=0))
    bloques = []
    if not len(filas):
        return bloques
    for by in range(int(filas[0]), int(filas[-1]) + 1 - lado + 1, lado):
        for bx in range(int(columnas[0]), int(columnas[-1]) + 1 - lado + 1, lado):
            if not roi[by:by + lado, bx:bx + lado].all():
                continue
            m = usar[by:by + lado, bx:bx + lado]
            if not m.any():
                continue
            bloque = {"x_mm": (bx + lado / 2) * escala, "y_mm": (by + lado / 2) * escala}
            for c in CAPAS_DEL_PISO:
                valores = planos[c][by:by + lado, bx:bx + lado][m]
                mediana = np.median(valores)
                mad = FACTOR_MAD * np.median(np.abs(valores - mediana)) or 1.0
                bloque[c] = float(valores[np.abs(valores - mediana) <= SIGMAS_DE_LA_MEDIA_RECORTADA * mad].mean())
            bloques.append(bloque)
    return bloques


def _virgen_uniformidad_y_gradiente(bloques, v):
    """(prueba «C5 uniformidad», prueba «C5 gradiente» o None). Uniformidad: el CV entre bloques y la desviación del bloque más lejano de la mediana, por capa. Gradiente: un plano ajustado
    por mínimos cuadrados a los bloques (en mm), en % de la media por 10 cm, solo en la dirección en que la zona mide `extension_minima_gradiente_mm` o más."""
    if len(bloques) < v["bloques_minimos_virgen"]:
        return PruebaDeLaVirgen("C5 uniformidad", "rechazo", f"no caben {v['bloques_minimos_virgen']} bloques de {v['lado_bloque_virgen_mm']:g} mm en la película"), None
    peor, textos = "ok", []
    for c in CAPAS_DEL_PISO:
        medias = np.array([b[c] for b in bloques])
        cv_ = float(medias.std() / medias.mean())
        desviacion = float(np.max(np.abs(medias - np.median(medias))) / np.median(medias))
        if cv_ > v["cv_rechazo"][c] or desviacion > v["dev_rechazo"][c]:
            peor = "rechazo"
        elif (cv_ > v["cv_aviso"][c] or desviacion > v["dev_aviso"][c]) and peor == "ok":
            peor = "aviso"
        textos.append(f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} CV {100 * cv_:.2f} % desviación {100 * desviacion:.2f} %")
    uniformidad = PruebaDeLaVirgen("C5 uniformidad", peor, ("no es uniforme (¿irradiada, velada o con huellas?): " if peor == "rechazo" else "") + "; ".join(textos) + f" ({len(bloques)} bloques)")
    diseno = np.array([[1.0, b["x_mm"], b["y_mm"]] for b in bloques])
    extension_x, extension_y = np.ptp(diseno[:, 1]) + v["lado_bloque_virgen_mm"], np.ptp(diseno[:, 2]) + v["lado_bloque_virgen_mm"]
    inclinadas = []
    for c in CAPAS:
        coeficientes, *_ = np.linalg.lstsq(diseno, np.array([b[c] for b in bloques]), rcond=None)
        media = float(np.mean([b[c] for b in bloques]))
        for eje, pendiente, extension in (("x", coeficientes[1], extension_x), ("y", coeficientes[2], extension_y)):
            por_ciento = abs(pendiente) * MM_EN_10_CM / media * 100.0
            if extension >= v["extension_minima_gradiente_mm"] and por_ciento > v["gradiente_aviso_pct_por_10cm"]:
                inclinadas.append(f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {por_ciento:.2f} % por 10 cm en {eje}")
    if inclinadas:
        return uniformidad, PruebaDeLaVirgen("C5 gradiente", "aviso", "gradiente (respuesta lateral del escáner o película curvada): " + ", ".join(inclinadas))
    return uniformidad, PruebaDeLaVirgen("C5 gradiente", "ok", f"sin gradiente (extensión {extension_x:.0f} × {extension_y:.0f} mm)")


def _virgen_rayas(planos, usar, sigma, v, escala):
    """C7, las rayas: la amplitud de las medias por columna y por fila de la zona medida menos una media móvil de `ventana_rayas_mm`, descontado el ruido. Avisa si supera `rayas_aviso_niveles`."""
    lado = _virgen_lado_impar(v["ventana_rayas_mm"] / escala)
    rayas = []
    for c in CAPAS:
        for eje in (0, 1):
            cuenta = usar.sum(axis=eje)
            suma = np.where(usar, planos[c], 0).sum(axis=eje)
            validas = cuenta >= FRACCION_MINIMA_DE_PERFIL * cuenta.max()
            perfil = suma[validas] / cuenta[validas]
            if len(perfil) < VENTANAS_MINIMAS_DEL_PERFIL * lado:
                continue
            residuo = (perfil - np.convolve(perfil, np.ones(lado) / lado, mode="same"))[lado:-lado]
            amplitud = float(np.sqrt(max(0.0, residuo.var() - sigma[c] ** 2 / float(np.median(cuenta[validas])))))
            if amplitud > v["rayas_aviso_niveles"]:
                rayas.append(f"{_NOMBRE_DE_LA_CAPA_DEL_PISO[c]} {amplitud:.2f} niveles ({'columnas' if eje == 0 else 'filas'})")
    if rayas:
        return PruebaDeLaVirgen("C7 rayas", "aviso", "rayas o bandas: " + ", ".join(rayas))
    return PruebaDeLaVirgen("C7 rayas", "ok", "sin rayas")


def piso_de_pelicula_virgen(datos, P, nombre_archivo="", fecha_calculo=None, orientacion_declarada=None):
    """El piso medido en el escaneo de una película VIRGEN (sin irradiar), con las comprobaciones C1 a C7 de la investigación de A.3 (`borradores/A3/investigacion_pruebas_pelicula_virgen.md`):
    una `ReferenciaVirgen` que dice si sirve («ok» o «no válida: <el primer rechazo>»), qué comprobó, de dónde salió el archivo y los parámetros con que lo midió. `datos`: los BYTES del
    escaneo tal como lo entrega el escáner. `P`: la escala del procedimiento (`CLAVES_DE_LA_ESCALA`) y, si se quieren cambiar, los parámetros del piso y de la virgen (los que falten, de
    fábrica). `fecha_calculo`: «AAAA-MM-DD» (por omisión, hoy). `orientacion_declarada`: la que declara el físico al cargarla («misma que la irradiada» o «girada»; no se mide).

    NUNCA lanza por el contenido: una imagen que no sirve da una referencia «no válida» con las pruebas que se pudieron hacer. `ValueError` solo si `P` no trae la escala.

    TODOS los umbrales de la virgen (`PARAMETROS_DE_LA_VIRGEN`) son PROPUESTAS de la investigación, sin una película virgen REAL detrás (el corpus no trae ninguna): hay que recalibrarlos con
    los primeros escaneos vírgenes (deuda declarada, diseño de A.3 §12). La prueba `test_m` mide cada `VIRGEN*` que el físico deje en `ImagenesDeReferencia/PlacasHistoricas`."""
    P = {} if P is None else P
    faltan = [k for k in CLAVES_DE_LA_ESCALA if k not in P]
    if faltan:
        raise ValueError(f"P debe traer la escala del procedimiento: faltan {', '.join(faltan)}.")
    datos = bytes(datos)
    p, v = _piso_parametros(P), _virgen_parametros(P)
    parametros = {**p, **v}
    procedencia = {"archivo": nombre_archivo, "sha256": hashlib.sha256(datos).hexdigest(), "bytes": len(datos), "formato": None, "bits": None, "dpi_declarado": None,
                   "clase_resolucion": None, "forma": None, "fecha_escaneo": None, "equipo": None, "calidad_jpeg": None, "submuestreo": None,
                   "orientacion_declarada": orientacion_declarada, "fecha_calculo": time.strftime("%Y-%m-%d") if fecha_calculo is None else fecha_calculo,
                   "version": VERSION_PISO_VIRGEN}
    pruebas = []
    try:
        pelicula = leer_pelicula(datos)
    except Exception as error:
        pruebas.append(PruebaDeLaVirgen("C1 cadena", "rechazo", f"no se pudo leer el archivo: {error}"))
        return _virgen_cerrar(pruebas, procedencia, parametros)
    imagen_pil = _abrir_con_pillow(datos)
    calidad, submuestreo = (None, None) if imagen_pil is None else _jpeg_calidad_y_submuestreo(imagen_pil)
    procedencia.update({"formato": pelicula.formato, "bits": pelicula.bits, "dpi_declarado": None if pelicula.dpi is None else float(pelicula.dpi),
                        "clase_resolucion": clase_resolucion(pelicula.dpi, P), "forma": [int(n) for n in pelicula.validos.shape],
                        "fecha_escaneo": None if pelicula.fecha_escaneo is None else pelicula.fecha_escaneo.isoformat(),
                        "equipo": None if imagen_pil is None else _equipo_de_la_imagen(imagen_pil), "calidad_jpeg": calidad, "submuestreo": submuestreo})
    escala = escala_mm(pelicula.dpi, P)
    if escala is None:
        pruebas.append(PruebaDeLaVirgen("C1 cadena", "rechazo", f"la película virgen se escaneó a otra resolución ({pelicula.dpi:g} dpi) y no a la del procedimiento "
                                                                f"({P['resolucion_escaneo_dpi']:g} dpi): sin esa escala no hay milímetros con que medirla"))
        return _virgen_cerrar(pruebas, procedencia, parametros)
    pruebas.append(_virgen_cadena(pelicula, procedencia, calidad, submuestreo, v))
    limpieza = _piso_pelicula_limpia(pelicula, escala, p, v["margen_borde_virgen_mm"], True, v["distancia_fondo_mm"])
    if isinstance(limpieza, str):
        pruebas.append(PruebaDeLaVirgen("C2 zona", "rechazo", "no hay película en la imagen (todo es fondo del escáner o no tiene dato)"))
        return _virgen_cerrar(pruebas, procedencia, parametros)
    roi, componente, origen = limpieza
    area = float(np.count_nonzero(roi)) * escala * escala
    if area < v["area_minima_virgen_mm2"]:
        pruebas.append(PruebaDeLaVirgen("C2 zona", "rechazo", f"no hay película virgen suficiente a {v['margen_borde_virgen_mm']:g} mm de los bordes ({area:.0f} mm²; hacen falta "
                                                              f"{v['area_minima_virgen_mm2']:g})"))
        return _virgen_cerrar(pruebas, procedencia, parametros)
    pruebas.append(PruebaDeLaVirgen("C2 zona", "ok", f"{area:.0f} mm² a {v['margen_borde_virgen_mm']:g} mm o más de los bordes"))
    ox, oy = origen
    alto_w, ancho_w = roi.shape
    planos = {c: np.ascontiguousarray(getattr(pelicula, c)[oy:oy + alto_w, ox:ox + ancho_w]) for c in CAPAS_DEL_PISO}
    pruebas.append(_virgen_recorte(planos, roi, v))
    en_la_zona, en_blanco = _virgen_fondo(pelicula, componente, origen, escala, v)
    if en_la_zona > v["pixeles_fondo_minimos"]:
        blanco = en_blanco / en_la_zona
        bien = blanco >= v["fondo_blanco_minimo"]
        pruebas.append(PruebaDeLaVirgen("C3 fondo", "ok" if bien else "aviso", f"el {100 * blanco:.2f} % del fondo está en el blanco máximo"
                                                                              + ("" if bien else ": revise la tapa, el vidrio o los ajustes (quitar fondo, brillo)")))
    del componente
    tinta = _virgen_tinta(planos, roi, p, v, escala)
    sigma, prueba_de_ruido = _virgen_ruido(planos, roi & ~tinta, v, escala)
    pruebas.append(prueba_de_ruido)
    motas, prueba_de_motas = _virgen_motas(planos, roi, tinta, sigma, v, escala)
    pruebas.append(prueba_de_motas)
    usar = roi & ~tinta & ~motas
    if not usar.any():
        pruebas.append(PruebaDeLaVirgen("rango", "rechazo", "no queda película limpia (sin tinta ni motas) en la zona medida"))
        return _virgen_cerrar(pruebas, procedencia, parametros)
    valores, como_fondo = _virgen_valores(planos, usar, p)
    prueba_de_rango, prueba_del_azul = _virgen_rango_y_testigo(valores, como_fondo, p, v)
    pruebas += [prueba_de_rango, prueba_del_azul]
    uniformidad, gradiente = _virgen_uniformidad_y_gradiente(_virgen_bloques(planos, roi, usar, v, escala), v)
    pruebas.append(uniformidad)
    if gradiente is not None:
        pruebas.append(gradiente)
    pruebas.append(_virgen_rayas(planos, usar, sigma, v, escala))
    filas, columnas = np.flatnonzero(usar.any(axis=1)), np.flatnonzero(usar.any(axis=0))
    region = {"caja": [int(columnas[0]) + ox, int(filas[0]) + oy, int(columnas[-1]) + 1 + ox, int(filas[-1]) + 1 + oy], "n": valores["G"][1], "area_mm2": round(area, 1)}
    return _virgen_cerrar(pruebas, procedencia, parametros, valores, region)


# ============================================================================= A.3: la referencia de la película virgen junto a la base de datos (un JSON, sin tabla nueva)

def _extension_del_escaneo(procedencia):
    """La extensión con que se copia el escaneo: la de su nombre si es de una imagen conocida y, si no, la de su formato."""
    propia = os.path.splitext(procedencia.get("archivo") or "")[1].lower()
    return EXTENSIONES_DE_ESCANEO.get(propia) or EXTENSION_POR_FORMATO.get(procedencia.get("formato"), ".bin")


def _escribir_sin_pisar(destino, contenido, binario):
    """Escribe `contenido` en `destino` de forma atómica (un temporal en la misma carpeta y `os.replace`); si falla, no deja el temporal y no toca lo que hubiera en `destino`."""
    temporal = f"{destino}.{os.getpid()}.tmp"
    try:
        with open(temporal, "wb" if binario else "w", **({} if binario else {"encoding": "utf-8"})) as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, destino)
    except BaseException:
        try:
            os.remove(temporal)
        except OSError:
            pass
        raise


def _copiar_el_escaneo(carpeta, referencia, datos):
    """Copia el escaneo a `carpeta/piso_pelicula_virgen_escaneos/<sha256><extensión>` si no está. Si ya hay un archivo con ese nombre se comprueba que su contenido sea el mismo: nunca se sobrescribe."""
    sha = referencia.procedencia["sha256"]
    carpeta_de_escaneos = os.path.join(carpeta, CARPETA_ESCANEOS_VIRGEN)
    os.makedirs(carpeta_de_escaneos, exist_ok=True)
    destino = os.path.join(carpeta_de_escaneos, sha + _extension_del_escaneo(referencia.procedencia))
    if os.path.exists(destino):
        with open(destino, "rb") as archivo:
            if hashlib.sha256(archivo.read()).hexdigest() != sha:
                raise ValueError(f"En {carpeta_de_escaneos} ya hay un archivo {os.path.basename(destino)} con otro contenido: no se sobrescribe.")
        return
    _escribir_sin_pisar(destino, datos, True)


def _archivar_la_anterior(carpeta, anterior, nuevo):
    """Copia los bytes del JSON que se va a reemplazar a `carpeta/piso_pelicula_virgen_anteriores/<fecha_calculo>_<sha8>.json` (si el nombre existe, `_2`, `_3`...: nunca se borra ni se
    sobrescribe nada). Se archiva SIEMPRE que el contenido cambie, también con la MISMA huella (A3-M2, 13-10, decisión de Opus vetable por el físico): la misma película con otro usuario, otra
    fecha de cálculo, otra orientación declarada, otros parámetros u otro instante de guardado es otra versión, y lo que se perdería sin rastro es justo quién fijó la referencia y cuándo. Solo NO
    se archiva si la anterior es IDÉNTICA, byte a byte, a lo que se va a escribir (`nuevo`: los bytes UTF-8 del JSON nuevo; el «\\r\\n» con que el modo texto de Windows escribe cada salto de
    línea cuenta como «\\n»): un duplicado exacto no guarda nada que no esté ya. Si la anterior no se puede leer, se archiva igual con un nombre propio."""
    if anterior.replace(b"\r\n", b"\n") == nuevo:
        return
    try:
        procedencia = json.loads(anterior.decode("utf-8"))["referencia"]["procedencia"]
        sha, fecha = procedencia["sha256"], procedencia["fecha_calculo"]
        nombre = f"{fecha}_{sha[:8]}"
    except (ValueError, KeyError, TypeError, AttributeError):
        nombre = "ilegible_" + time.strftime("%Y%m%dT%H%M%S")
    carpeta_de_anteriores = os.path.join(carpeta, CARPETA_REFERENCIAS_VIRGEN_ANTERIORES)
    os.makedirs(carpeta_de_anteriores, exist_ok=True)
    destino, repeticion = os.path.join(carpeta_de_anteriores, nombre + ".json"), 1
    while os.path.exists(destino):
        repeticion += 1
        destino = os.path.join(carpeta_de_anteriores, f"{nombre}_{repeticion}.json")
    _escribir_sin_pisar(destino, anterior, True)


def guardar_referencia_virgen(referencia, carpeta, datos=None, usuario=None):
    """Guarda la referencia de la película virgen en `carpeta/piso_pelicula_virgen.json` (la carpeta de la base de datos: la comparten todos los equipos que abren esa base) y devuelve la ruta
    del JSON. Solo una referencia «ok» (si no, `ValueError`). La escritura es atómica (un temporal en la misma carpeta y `os.replace`); si ya había un JSON y su contenido cambia (otra huella, o
    LA MISMA con otro usuario, otra fecha de cálculo, otra orientación declarada, otros parámetros u otro instante de guardado: A3-M2), antes se copia a
    `piso_pelicula_virgen_anteriores/<fecha_calculo>_<sha8>.json` y NADA se borra; solo un guardado IDÉNTICO, byte a byte, a lo que ya había no archiva nada. Con `datos` (los bytes del escaneo) se copia el escaneo a `piso_pelicula_virgen_escaneos/<sha256><extensión>`
    (y se comprueba que su sha256 sea el de la referencia). El JSON lleva la versión, la referencia entera, quién la guardó y cuándo. La copia guardada con cada análisis manda (DA-81): este
    archivo solo alimenta análisis nuevos."""
    if not isinstance(referencia, ReferenciaVirgen):
        raise ValueError("Lo que se guarda debe ser una ReferenciaVirgen.")
    if referencia.estado != "ok":
        raise ValueError(f"No se guarda una referencia de película virgen que no es válida: {referencia.estado}")
    if datos is not None and hashlib.sha256(datos).hexdigest() != referencia.procedencia["sha256"]:
        raise ValueError("Los datos del escaneo no son los de la referencia (su huella sha256 es otra).")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, ARCHIVO_REFERENCIA_VIRGEN)
    anterior = None
    if os.path.isfile(ruta):
        with open(ruta, "rb") as archivo:
            anterior = archivo.read()
    contenido = json.dumps({"version": VERSION_PISO_VIRGEN, "referencia": referencia.como_dict(), "guardada_por": usuario, "guardada_el": time.strftime("%Y-%m-%dT%H:%M:%S")},
                           ensure_ascii=False, indent=2)
    if datos is not None:
        _copiar_el_escaneo(carpeta, referencia, bytes(datos))
    if anterior is not None:
        _archivar_la_anterior(carpeta, anterior, contenido.encode("utf-8"))
    _escribir_sin_pisar(ruta, contenido, False)
    return ruta


def leer_referencia_virgen(carpeta):
    """La referencia de la película virgen guardada en `carpeta`, o None si no hay archivo. `ValueError` con el motivo (y el archivo) si el archivo está dañado, es de otra versión o trae un valor que
    no es del tipo que `ReferenciaVirgen.como_dict()` escribe (`referencia_virgen_desde_dict` lo comprueba): NUNCA otra excepción por el contenido, ni más tarde al usar lo leído."""
    ruta = os.path.join(carpeta, ARCHIVO_REFERENCIA_VIRGEN)
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            contenido = json.load(archivo)
    except ValueError as error:
        raise ValueError(f"El archivo de la referencia de la película virgen está dañado ({ruta}): {error}") from None
    if not isinstance(contenido, dict) or contenido.get("version") != VERSION_PISO_VIRGEN:
        version = contenido.get("version") if isinstance(contenido, dict) else None
        raise ValueError(f"El archivo de la referencia de la película virgen es de la versión {version!r} y esta aplicación lee la {VERSION_PISO_VIRGEN!r}: {ruta}")
    if "referencia" not in contenido:
        raise ValueError(f"Al archivo de la referencia de la película virgen le falta la referencia: {ruta}")
    try:
        return referencia_virgen_desde_dict(contenido["referencia"])
    except ValueError as error:
        raise ValueError(f"El archivo de la referencia de la película virgen no se puede usar ({ruta}): {error}") from None
