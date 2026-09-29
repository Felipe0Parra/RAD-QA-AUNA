"""L.2 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, segunda ronda): función
pura que ajusta la linealidad de la fuente desde los datos POR POSICIÓN,
para que "Ok" (`Calculo_Linealidad`) y "Guardar" (`guardar_linealidad`)
usen la MISMA aritmética sobre lo que cada uno lee en ese momento --
antes, "Guardar" archivaba lo que había calculado el último "Ok", no las
medidas que de verdad guardaba.

CAMBIO §R.3 (decisión del físico, 28-09): la "exactitud" que se archiva es
la PENDIENTE del ajuste, no la R² -- el formato oficial IDC-F-RT-144 V.03
la define así (su "Exactitud" 0.997 es la pendiente; la app guardaba la
R², 0.99999). El intercepto sigue siendo "tiempo de tránsito" (el `self.b`
de siempre, sin cambio de definición).
"""
import numpy as np

# El literal estaba repetido en `generar_tabla_medidas` (crea las 10 filas
# de la tabla lateral) y en `extraer_datos_medidas` (lee las medidas) --
# una sola definición.
TIEMPOS_PARADA = (0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6, 51.2)


class DatosInsuficientes(ValueError):
    """Menos de 2 pares (tiempo de parada, tiempo efectivo) completos --
    no se puede ajustar una recta. El mensaje va tal cual a un
    `QMessageBox` (castellano, sin símbolos, DA-18)."""


def ajuste_linealidad(tp, te):
    """`tp`/`te`: listas de 10 posiciones (`None` donde esa fila está
    incompleta -- el contrato que deja `extraer_datos_medidas`). Ajusta
    SOLO los pares completos con `np.polyfit(x, y, 1)` -- la misma
    aritmética de siempre (`Calculo_Linealidad`, antes de esta tarea).
    Devuelve `(pendiente, intercepto)`: `pendiente` es la "exactitud"
    (decisión del físico, arriba); `intercepto` es el "tiempo de
    tránsito". Exige al menos 2 pares completos, o `DatosInsuficientes`."""
    pares = [(x, y) for x, y in zip(tp, te) if x is not None and y is not None]
    if len(pares) < 2:
        raise DatosInsuficientes(
            f"Se necesitan al menos 2 medidas completas para ajustar la "
            f"linealidad (hay {len(pares)}).")
    x = np.array([p[0] for p in pares])
    y = np.array([p[1] for p in pares])
    pendiente, intercepto = np.polyfit(x, y, 1)
    return float(pendiente), float(intercepto)


def reproducibilidad(valores):
    """`100 - desviación estándar` (muestral, `ddof=1`) -- la fórmula de
    siempre (`Calculo_Linealidad`); sin cambio de valor, solo de lugar."""
    return 100 - float(np.std(valores, ddof=1))
