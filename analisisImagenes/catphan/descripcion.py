"""E.2 (PLAN_HANDOFF_IMAGENES_22-09.md): las filas de IDENTIDAD y de ADQUISICIÓN de una serie, en un
solo sitio.

`adquisicion_de_serie` (`serie.py`) define QUÉ datos identifican de dónde salió un volumen; este módulo
define CÓMO se rotulan y se escriben para una persona. Los consumen dos lugares que tienen que decir lo
mismo -- la ventana de metadatos de la carga (A.3) y la tabla de parámetros del informe PDF (E.2) --, y por
eso las etiquetas se escriben aquí y solo aquí (una prueba lo exige).

Sin Qt: se puede probar y usar desde el PDF sin arrastrar diálogos.
"""
from __future__ import annotations

from typing import Optional

# Lo que el equipo no publica se DICE: no se deja en blanco ni se escribe "None" (el iX no trae descripción
# de la serie, CTDIvol ni filtro, [medido]).
NO_PUBLICADO = "(no lo publica el equipo)"

# (clave de `adquisicion_de_serie`, etiqueta)
IDENTIDAD = (
    ("fabricante", "Fabricante"),
    ("modelo", "Modelo"),
    ("estacion", "Estación"),
    ("numero_serie_equipo", "Número de serie del equipo"),
    ("software", "Software"),
)
ADQUISICION = (
    ("descripcion_serie", "Descripción de la serie"),
    ("fecha_adquisicion", "Fecha de adquisición"),
    ("kv", "kV"),
    ("ma", "mA"),
    ("mas", "mAs"),
    ("tiempo_exposicion_ms", "Tiempo de exposición [ms]"),
    ("ctdi_vol_mgy", "CTDIvol [mGy]"),
    ("espesor_mm", "Espesor de corte [mm]"),
    ("kernel", "Kernel"),
    ("filtro", "Filtro"),
    ("fov_mm", "FOV [mm]"),
    ("pixel_mm", "Píxel [mm]"),
    ("n_cortes", "Cortes"),
)


# B.3: lo que la aplicación MIDE en los píxeles (no lo publica el equipo). Van aparte de `ADQUISICION`: cuando falta, no
# se dice "(no lo publica el equipo)" sino que no se midió, o que el control es anterior a la medición.
MEDIDOS = (
    ("desplazamiento_hu", "Corrimiento de escala [HU]"),
)


def texto_valor(valor) -> str:
    """Un valor DICOM para mostrar."""
    if valor is None or valor == "":
        return NO_PUBLICADO
    if isinstance(valor, float):
        return str(int(valor)) if valor == int(valor) else f"{valor:g}"
    return str(valor)


def _filas(definicion, adq: dict, claves: Optional[tuple]) -> list:
    return [(etiqueta, texto_valor(adq.get(clave)))
            for clave, etiqueta in definicion if claves is None or clave in claves]


def filas_identidad(adq: dict, claves: Optional[tuple] = None) -> list:
    """[(etiqueta, texto)] del equipo tal como lo dice el DICOM."""
    return _filas(IDENTIDAD, adq or {}, claves)


def filas_medidas(adq: dict, ausente: Optional[str] = None) -> list:
    """[(etiqueta, texto)] de lo que la aplicación midió en la serie (hoy, el corrimiento de la escala de HU).

    Una clave AUSENTE del diccionario (un control anterior a la medición, o una comparación solo con encabezados) da
    `ausente` (la fila se omite si es `None`); una clave presente con valor `None` es una medición que no se pudo hacer.
    El valor lleva su signo: `+475`, `-35`."""
    adq = adq or {}
    filas = []
    for clave, etiqueta in MEDIDOS:
        if clave not in adq:
            if ausente is not None:
                filas.append((etiqueta, ausente))
        elif adq[clave] is None:
            filas.append((etiqueta, "no se pudo medir"))
        else:
            filas.append((etiqueta, f"{float(adq[clave]):+.0f}"))
    return filas


def filas_adquisicion(adq: dict, claves: Optional[tuple] = None) -> list:
    """[(etiqueta, texto)] de la adquisición. `claves` restringe a algunas filas (un control anterior a
    A.1 solo tiene kV, mA y espesor guardados)."""
    return _filas(ADQUISICION, adq or {}, claves)
