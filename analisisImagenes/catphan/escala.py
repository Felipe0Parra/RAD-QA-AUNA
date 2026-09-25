"""B.3 (PLAN_HANDOFF_IMAGENES_22-09.md): declarar la escala de HU de una serie, en una sola definición y sin Qt.

El OBI del Clinac iX entrega "números de CBCT", no HU calibrados: el material del fantoma da ≈ +490 donde un equipo
calibrado da ≈ 0 (§0.5 del plan; `Catphandiciembre`, dos protocolos distintos del mismo OBI dieron +490 y −410). Todo lo
que asume agua ≈ 0 y aire ≈ −1000 falla o engaña con esas imágenes. Esto NO las corrige: restar un número a un volumen de
CBCT y presentarlo como HU sería inventar una calibración que nadie midió. Solo **declara** la escala.

El corrimiento es la **moda del histograma del volumen sin el aire**: el HU del material dominante del fantoma. Se mide
sobre el volumen completo, no sobre un módulo, para no depender de haber encontrado el fantoma (en el iX esa detección es
justo lo que fallaba). Supone que el material dominante es equivalente al agua, como en el Catphan 504 (los módulos
CTP486 y CTP515, la mayor parte del volumen, dan ≈ 0-10 HU en un equipo calibrado [medido]; CTP404 y CTP528, ≈ +90, son
un segundo pico menor). Medido en las seis series reales (resolución de ±10 HU por el ancho de la moda): iX +475, tomógrafo
+15, Halcyon +5, −15 y −35, carpeta mixta +15; idéntico con un vóxel de cada uno, de cada 8 y de cada 27.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

AIRE_HASTA_HU = -900.0          # por debajo de esto es aire (o relleno de la reconstrucción): no es el fantoma
HU_MAXIMO_DEL_HISTOGRAMA = 3000.0
ANCHO_DE_CASILLA_HU = 10.0
CASILLAS_DE_SUAVIZADO = 5       # 50 HU: una moda ancha (el iX, por el cupping) no salta entre casillas vecinas
PASO_DE_MUESTREO = 2            # un vóxel de cada 8
MINIMO_DE_VOXELES = 10_000      # con menos, no hay fantoma que medir

# A partir de aquí se dice que las unidades no son HU calibrados. En el corpus real: iX 475; los equipos calibrados, ≤ 35
# (tres veces el mayor). El umbral no juzga el equipo (eso lo hace el catálogo): dice si sus números son comparables
# con los de un equipo calibrado.
UMBRAL_ESCALA_NO_CALIBRADA_HU = 100.0

CLAVE_EN_ADQUISICION = "desplazamiento_hu"


def desplazamiento_hu(volumen_hu) -> Optional[float]:
    """HU del material dominante del fantoma (moda del histograma sin el aire), o `None` si no hay fantoma que medir
    (volumen vacío, solo aire, sin valores finitos, o menos de `MINIMO_DE_VOXELES` vóxeles de material)."""
    v = np.asarray(volumen_hu)
    fraccion = 1                                    # qué parte de los vóxeles se mira
    if v.ndim == 3:
        v = v[::PASO_DE_MUESTREO, ::PASO_DE_MUESTREO, ::PASO_DE_MUESTREO]
        fraccion = PASO_DE_MUESTREO ** 3
    v = v[v > AIRE_HASTA_HU]                        # también descarta NaN y -inf (comparan como falso)
    if v.size * fraccion < MINIMO_DE_VOXELES:
        return None
    bordes = np.arange(AIRE_HASTA_HU, HU_MAXIMO_DEL_HISTOGRAMA + ANCHO_DE_CASILLA_HU, ANCHO_DE_CASILLA_HU)
    cuentas, _ = np.histogram(v, bins=bordes)
    suave = np.convolve(cuentas, np.ones(CASILLAS_DE_SUAVIZADO) / CASILLAS_DE_SUAVIZADO, mode="same")
    i = int(np.argmax(suave))
    return float((bordes[i] + bordes[i + 1]) / 2)


def es_escala_no_calibrada(desplazamiento: Optional[float]) -> bool:
    """Si el corrimiento medido es tan grande que los HU absolutos de la serie no son comparables con los de un
    equipo calibrado. Sin medición (`None`) no se afirma nada."""
    return desplazamiento is not None and abs(float(desplazamiento)) >= UMBRAL_ESCALA_NO_CALIBRADA_HU


def nota_escala(desplazamiento: Optional[float]) -> Optional[str]:
    """La nota que acompaña a una serie de escala no calibrada (ventana de la carga y PDF), o `None` si no aplica. Una
    sola redacción: sin símbolos (`DA-18`)."""
    if not es_escala_no_calibrada(desplazamiento):
        return None
    return (f"Las unidades de este volumen no son HU calibrados: el material del fantoma da {desplazamiento:+.0f} HU "
            f"donde un equipo calibrado da alrededor de 0. Los valores CT absolutos no son comparables con los de un "
            f"equipo calibrado (por ejemplo, el tomógrafo); solo se comparan con la línea base de este mismo equipo y "
            f"protocolo. No se corrigen las imágenes.")
