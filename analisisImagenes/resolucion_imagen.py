"""PI.1 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md, obstáculo del 01-10): la resolución que un archivo de imagen
DECLARA de verdad -- y nada más.

CAUSA. `Image.open(...).info["dpi"]` de Pillow no es una lectura del archivo: en JPEG y en TIFF Pillow RELLENA
el dato cuando falta. Medido el 01-10 (Pillow 12.3.0): un JPEG con bloque EXIF pero sin resolución sale con
72 dpi (`JpegImagePlugin` fija `info["dpi"] = 72, 72` en su `except`) y un TIFF sin la etiqueta 282 sale con 1.
Con eso el motor de "Posición inicial" habría convertido a milímetros con una escala inventada (0.353 mm/px en
vez de 0.0423 a 600 dpi) y habría dado un veredicto Cumple / No cumple sobre ella: justo lo que DD6 prohíbe
("nunca se inventa la escala").

QUÉ SE LEE. Solo lo que el archivo escribe con unidad física:
  - JPEG: las etiquetas EXIF 282/283 (resolución) y 296 (unidad) más el JFIF (APP0). Del JFIF cuentan solo las
    unidades 1 (puntos por pulgada) y 2 (por cm); la unidad 0 es solo proporción de píxel y no es resolución.
  - TIFF: las mismas etiquetas, de `tag_v2`.
  - PNG y BMP: `info["dpi"]`, que Pillow solo pone si el archivo la trae (pHYs / ppm).
  - Cualquier otro formato: None.
Si el archivo declara dos cifras que no coinciden (a 1 %) -- dos resoluciones distintas o píxel no cuadrado --, no
hay escala: None. Se prefiere la cifra racional de EXIF/TIFF a la entera del JFIF (el Epson escribe 599.999 y el
JFIF la trunca a 599: es la misma declaración).

Lo que esto NO resuelve (ni pretende): que la resolución declarada sea la real. Paint reescribe la declarada a 96
dpi al recortar sin remuestrear (EPSON009: 96.012), y un recorte reducido puede conservar "600" en la cabecera. Desde
PI.1b el motor NO usa este dato como escala: la escala es la del procedimiento de escaneo (600 dpi, que el físico
garantiza) y esta lectura solo sirve para CLASIFICAR la cabecera (`clase_resolucion` del motor: coincide, sin dato,
editor u otra) y para informar en pantalla.

Sin Qt y sin base de datos. Diseño y verificación: Opus, 01-10 (42 casos: 21 sintéticos y 21 archivos reales)."""
import math

TOLERANCIA_RELATIVA = 0.01      # 599 (JFIF, entero) frente a 599.999 (EXIF) es la MISMA declaración


def _positivo(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return numero if math.isfinite(numero) and numero > 0 else None


def _de_etiquetas(etiquetas):
    """IFD0 de EXIF (JPEG) o de TIFF: 282 XResolution, 283 YResolution, 296 ResolutionUnit.
    Sin 282 no hay resolución (el 72 'por defecto' de EXIF no es una medida). Unidad 2 = pulgada,
    3 = cm; sin 296, pulgada (TIFF 6.0); 1 ('sin unidad') u otra -> nada."""
    unidad = etiquetas.get(296, 2)
    if unidad not in (2, 3):
        return []
    x = _positivo(etiquetas.get(282))
    if x is None:
        return []
    factor = 2.54 if unidad == 3 else 1.0
    return [v * factor for v in (x, _positivo(etiquetas.get(283))) if v is not None]


def _de_jfif(info):
    """JFIF APP0: unidad 1 = puntos por pulgada, 2 = por cm; 0 = solo proporción (no es resolución)."""
    unidad, densidad = info.get("jfif_unit"), info.get("jfif_density")
    if unidad not in (1, 2) or not densidad:
        return []
    factor = 2.54 if unidad == 2 else 1.0
    return [v * factor for v in (_positivo(d) for d in densidad) if v is not None]


def resolucion_declarada(imagen):
    """dpi que el archivo ESCRIBE con unidad física, o None (no la trae, la trae sin unidad, o trae dos
    distintas / píxel no cuadrado). `imagen` es el objeto de Pillow ya abierto. Prefiere la racional
    (EXIF/TIFF) a la entera (JFIF)."""
    formato = (imagen.format or "").upper()
    if formato in ("JPEG", "MPO"):
        precisas = _de_etiquetas(imagen.getexif())
        valores = precisas + _de_jfif(imagen.info)
    elif formato == "TIFF":
        valores = _de_etiquetas(imagen.tag_v2)
    elif formato in ("PNG", "BMP"):        # Pillow solo pone 'dpi' si el archivo la trae (pHYs en metros; ppm del BMP)
        valores = [v for v in (_positivo(d) for d in (imagen.info.get("dpi") or ())) if v is not None]
    else:
        return None
    if not valores:
        return None
    if max(valores) > min(valores) * (1 + TOLERANCIA_RELATIVA):
        return None
    return valores[0]
