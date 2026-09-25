"""B.2 (PLAN_HANDOFF_IMAGENES_22-09.md): el rango de los deslizadores de nivel (WL) y ventana (WW) sale del volumen.

Antes el visor fijaba `setRange(-1000, 500)` y `setRange(1, 2000)` y arrancaba siempre en 40/400. El volumen del OBI del
iX vive en ≈ +490 HU, así que su imagen quedaba fuera del rango (el físico "tiene que dejarlo en el límite de 500") y
arrancaba saturada en blanco. Cada serie trae puesta su propia ventana razonable (iX 402/364, Halcyon −21/144, tomógrafo
40/200) y el programa la ignoraba.

La regla, en una sola definición y sin Qt (el visor la aplica; las pruebas la miran sin pantalla):

- La extensión del volumen es su [p0.1, p99.9]: robusta a los pocos vóxeles de artefactos o metal (el Halcyon llega a
  7000 HU en el 0.02 % del volumen y una carpeta mixta a 30318). Un deslizador que llegara al máximo absoluto quedaría con
  100 HU por píxel: inutilizable para el uso normal.
- El rango de WL es esa extensión ampliada en **un cuarto del recorrido a cada lado**, sin quedar **nunca** por debajo del
  que había (−1000…500: quitar capacidad sería una regresión) y **sin dejar fuera** el nivel de la propia ventana del
  DICOM.
- El de WW llega hasta el recorrido total del rango de WL, con el mismo piso (2000).
- El valor inicial es la ventana del DICOM si la trae (primer valor si viene multivalor), y 40/400 si no.
"""
from dataclasses import dataclass
import math

import numpy as np

# Lo que tenía el visor antes de B.2. Son el PISO de la regla, no el techo.
WL_MIN_ANTERIOR = -1000
WL_MAX_ANTERIOR = 500
WW_MAX_ANTERIOR = 2000
WL_INICIAL_ANTERIOR = 40
WW_INICIAL_ANTERIOR = 400

PERCENTIL_BAJO = 0.1
PERCENTIL_ALTO = 99.9
MARGEN_FRACCION = 0.25          # del recorrido [p0.1, p99.9], a cada lado
PASO_DE_MUESTREO = 2            # un vóxel de cada 8: los percentiles no necesitan los 30 a 70 millones


@dataclass(frozen=True)
class RangoVentana:
    wl_min: int
    wl_max: int
    ww_max: int
    wl_inicial: int
    ww_inicial: int
    extension_bajo: float       # p0.1 del volumen [HU]
    extension_alto: float       # p99.9 del volumen [HU]
    origen_inicial: str         # "dicom" | "predeterminada"


def rango_de_ventana(volumen_hu, ventana_dicom=None):
    """El rango de los deslizadores y su valor inicial para `volumen_hu` (HU, 3D).

    `ventana_dicom` es `(WindowCenter, WindowWidth)` de la serie, o `None` si no la trae."""
    extension = _extension_del_volumen(volumen_hu)
    if extension is None:                       # un volumen que no se puede medir: el rango de antes, sin inventar
        bajo, alto = float(WL_MIN_ANTERIOR), float(WL_MAX_ANTERIOR)
        wl_min, wl_max = WL_MIN_ANTERIOR, WL_MAX_ANTERIOR
    else:
        bajo, alto = extension
        margen = (alto - bajo) * MARGEN_FRACCION
        wl_min = min(WL_MIN_ANTERIOR, math.floor(bajo - margen))
        wl_max = max(WL_MAX_ANTERIOR, math.ceil(alto + margen))
    if ventana_dicom is not None:
        wl_min = min(wl_min, math.floor(ventana_dicom[0]))
        wl_max = max(wl_max, math.ceil(ventana_dicom[0]))
    ww_max = max(WW_MAX_ANTERIOR, wl_max - wl_min)

    if ventana_dicom is not None:
        wl_inicial, ww_inicial, origen = round(ventana_dicom[0]), round(ventana_dicom[1]), "dicom"
    else:
        wl_inicial, ww_inicial, origen = WL_INICIAL_ANTERIOR, WW_INICIAL_ANTERIOR, "predeterminada"
    return RangoVentana(
        wl_min=wl_min,
        wl_max=wl_max,
        ww_max=ww_max,
        wl_inicial=wl_inicial,                  # dentro del rango por construcción: el rango incluye el nivel del DICOM
        ww_inicial=min(max(ww_inicial, 1), ww_max),
        extension_bajo=float(bajo),
        extension_alto=float(alto),
        origen_inicial=origen,
    )


def _extension_del_volumen(volumen_hu):
    """[p0.1, p99.9] del volumen, o `None` si no se puede medir (vacío, sin valores finitos)."""
    v = np.asarray(volumen_hu)
    if v.ndim == 3:
        v = v[::PASO_DE_MUESTREO, ::PASO_DE_MUESTREO, ::PASO_DE_MUESTREO]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return None
    bajo, alto = np.percentile(v, [PERCENTIL_BAJO, PERCENTIL_ALTO])
    return float(bajo), float(alto)
