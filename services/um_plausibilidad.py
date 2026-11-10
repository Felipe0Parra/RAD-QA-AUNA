"""Barreras de plausibilidad de los VALORES de las curvas y de las tablas de factores de Eclipse (UM.2 v2, estudio A1 del 08-11-2026). Sin Qt ni base.

Un valor que el lector acepta (un número bien escrito) puede ser físicamente imposible: un punto decimal borrado («+086.300» → «+086300») o una cifra perdida
(«+052.800» → «+05.800») daban UM equivocadas en órdenes de magnitud, sin aviso. Estas funciones reciben lo que ya se leyó (`Curva`, `TablaOF`, `PerfilOAR`) y, si
un valor no puede ser, lanzan `BarreraDePlausibilidad` (un `ArchivoNoReconocido`: la carga no deja guardar) nombrando la curva o la celda y el valor. Las
constantes salen de medir TODO lo que el cálculo lee de los datos reales (los 22 archivos del 600C y el paquete de Varian), con cero falsos rechazos
(medido sobre los archivos del 600C y del paquete de Varian, en el anexo del plan de la calculadora de UM). Lo que no se puede atrapar (un ruido del mismo tamaño que el real) está en las pistas de UM.2, §5 del estudio A1.
"""
import math

import numpy as np

from services import um_lector_eclipse as lector
from services import um_motor as motor

# PDD abiertos (OPD) y PDD con cuña (WDD): valores en puntos de PDD [%], profundidades en [cm].
TOLERANCIA_MAXIMO_PDD_PCT = 0.5    # |máximo − 100| de un PDD abierto. Medido: 0 en el 600C; hasta 0.4 en Varian (un decimal)
TOLERANCIA_MAXIMO_WDD_PCT = 1.0    # lo mismo con cuña (se normaliza a su propio máximo). Medido: de 99.5 a 100.0
ZONA_DEL_MAXIMO_CM = 1.5           # a menos de esto del máximo la curva es casi plana y manda el ruido
SALTO_EN_LA_ZONA_PCT = 1.0         # en esa zona, lo más que un punto se mueve contra la dirección esperada. Medido: <= 0.6
SALTO_FUERA_PCT = 0.3              # fuera de ella: antes del máximo no baja, pasado no sube, más que esto. Medido: <= 0.1
SALTO_FUERA_WDD_PCT = 0.6          # lo mismo con cuña (600C: un decimal en una rejilla de 1 mm). Medido: <= 0.4
DESVIO_COLA_PCT = 0.6              # pasada la zona: |v_i − la recta de sus dos vecinos|. Medido: <= 0.4
DESVIO_COLA_WDD_PCT = 1.3          # lo mismo con cuña. Medido: <= 0.95 (600C, 45° y 60°)
DESVIO_FINAL_PCT = 1.2             # el último punto, contra la recta de los dos anteriores. Medido: <= 0.8 con el archivo terminado en CUALQUIER punto de la cola
DESVIO_FINAL_WDD_PCT = 2.5         # lo mismo con cuña. Medido: <= 1.8 (600C, 30°, 4 × 4, terminado en 7 cm; el estudio A1 daba 0.8 mirando solo el último de verdad)
# Perfiles abiertos: el OAR de `PerfilOAR` (el eje entra como OAR 1); posiciones [cm] en el plano de la medida.
OAR_MAXIMO = motor.RANGO_OAR[1]    # lo más que puede valer un OAR escrito a mano. Medido: <= 1.085 (cuernos del 40 × 40 a 1.35 cm)
NUCLEO_HASTA_EL_BORDE_CM = 2.0     # el núcleo: a más de esto del borde geométrico del campo, proyectado a la profundidad del perfil
PICO_NUCLEO = 0.008                # en el núcleo, |OAR_i − la recta de sus vecinos|. Medido: <= 0.0048
PICO_OAR = 0.05                    # fuera del núcleo, ese desvío menos la fracción de abajo de |OAR_{i+1} − OAR_{i−1}|. Medido: <= 0.027 (600C, 4 × 4, cola)
PICO_FRACCION_DE_LA_PENDIENTE = 0.5   # lo que se admite de más en la penumbra, donde la pendiente es grande
# Tablas de factores: entre celdas vecinas de una fila o una columna, en logaritmos.
PENDIENTE_LOG_TABLA = (-0.08, 0.35)   # Δln(factor)/Δln(lado). Medido: de −0.040 a +0.21
DESVIO_LINEA_TABLA = 0.025         # |ln m − la recta de sus dos vecinas|, en el interior. Medido: <= 0.0172
DESVIO_BORDE_TABLA = 0.07          # en un borde, contra la recta de las dos de dentro. Medido: <= 0.042 (fila Y = 2 de las cuñas del 600C)


class BarreraDePlausibilidad(lector.ArchivoNoReconocido):
    """Un valor físicamente imposible en una curva o una tabla: el mensaje dice cuál, dónde y cuánto."""


def _recta(z, v, i, j, k):
    """El valor en z[i] de la recta que pasa por los puntos j y k."""
    return v[j] + (v[k] - v[j]) * (z[i] - z[j]) / (z[k] - z[j])


def _revisar_pdd(c, nombre, tolerancia, salto_fuera, desvio_cola, desvio_final):
    """Máximo 100 ± tolerancia; antes del máximo no baja ni pasado sube (más del ruido); en la cola, ningún punto fuera de la recta de sus vecinos."""
    z, v = c.z_cm, c.valor
    if np.any(np.diff(z) <= 0):
        i = int(np.argmin(np.diff(z)))
        raise BarreraDePlausibilidad(f"el {nombre}: sus puntos no van en profundidad creciente (z = {z[i]:g} [cm] y luego {z[i + 1]:g} [cm]): una profundidad está dañada")
    k = int(np.argmax(v))
    if abs(v[k] - 100.0) > tolerancia:
        raise BarreraDePlausibilidad(f"el {nombre} tiene su máximo en {motor.cifras(v[k], 100 + tolerancia if v[k] > 100 else 100 - tolerancia, 6, 'g')} [%] (a {z[k]:g} [cm]) y debe valer 100 ± {tolerancia:g} [%]: no está normalizado como se "
                                     "espera o un valor está dañado (¿un punto decimal perdido?)")
    for i in range(1, len(v)):
        contra = v[i - 1] - v[i] if i <= k else v[i] - v[i - 1]          # antes del máximo, bajar; pasado, subir
        umbral = SALTO_EN_LA_ZONA_PCT if min(abs(z[i] - z[k]), abs(z[i - 1] - z[k])) <= ZONA_DEL_MAXIMO_CM else salto_fuera
        if contra > umbral:
            raise BarreraDePlausibilidad(f"el {nombre} {'baja' if i <= k else 'sube'} {motor.cifras(contra, umbral, 3, 'g')} [%] entre z = {z[i - 1]:g} [cm] y z = {z[i]:g} [cm], {'antes de' if i <= k else 'pasado'} su "
                                         f"máximo (a {z[k]:g} [cm]); se admite {umbral:g} [%] de ruido: un valor está dañado")
    cola = [i for i in range(k + 1, len(v)) if z[i - 1] - z[k] > ZONA_DEL_MAXIMO_CM]
    for i in (q for q in cola if q + 1 < len(v)):
        if abs(v[i] - _recta(z, v, i, i - 1, i + 1)) > desvio_cola:
            raise BarreraDePlausibilidad(f"el {nombre} se aparta {motor.cifras(abs(v[i] - _recta(z, v, i, i - 1, i + 1)), desvio_cola, 3, 'g')} [%] de la recta de sus vecinos en z = {z[i]:g} [cm] "
                                         f"(se admite {desvio_cola:g} [%]): un valor está dañado")
    n = len(v) - 1
    if len(cola) >= 2 and abs(v[n] - _recta(z, v, n, n - 2, n - 1)) > desvio_final:
        raise BarreraDePlausibilidad(f"el último punto del {nombre} (z = {z[n]:g} [cm]) se aparta {motor.cifras(abs(v[n] - _recta(z, v, n, n - 2, n - 1)), desvio_final, 3, 'g')} [%] de la tendencia "
                                     f"de los dos anteriores (se admite {desvio_final:g} [%]): un valor está dañado")


def _lado(c):
    return f"{c.campo_cm[0]:g} × {c.campo_cm[1]:g} [cm]"


def revisar_pdd_abiertos(curvas):
    """Cada PDD abierto, en el orden del archivo."""
    for c in curvas:
        _revisar_pdd(c, f"PDD abierto de {_lado(c)}", TOLERANCIA_MAXIMO_PDD_PCT, SALTO_FUERA_PCT, DESVIO_COLA_PCT, DESVIO_FINAL_PCT)


def revisar_pdd_con_cuna(curvas, angulo):
    """Cada PDD con cuña del archivo, también los que no entran en el ajuste (el del campo entero)."""
    for c in curvas:
        _revisar_pdd(c, f"PDD con la cuña de {angulo}° de {_lado(c)}", TOLERANCIA_MAXIMO_WDD_PCT, SALTO_FUERA_WDD_PCT, DESVIO_COLA_WDD_PCT, DESVIO_FINAL_WDD_PCT)


def revisar_curvas_de_perfiles(curvas):
    """Lo que se mira en las curvas tal como vienen: una sola SSD en todos los perfiles (como en los PDD) y las posiciones en orden creciente (antes se
    reordenaban en silencio, y una x dañada movía un valor de sitio)."""
    ssds = sorted({c.ssd_cm for c in curvas} - {None})      # un perfil que no la dice lo rechaza `perfil_oar`, diciéndolo
    if len(ssds) > 1:
        raise BarreraDePlausibilidad(f"los perfiles abiertos deben decir una sola SSD y dicen {', '.join(f'{s:g} [cm]' for s in ssds)}: un %SSD está dañado")
    for c in curvas:
        if np.any(np.diff(c.x_cm) <= 0):
            i = int(np.argmin(np.diff(c.x_cm)))
            raise BarreraDePlausibilidad(f"el perfil abierto de {_lado(c)} a {np.median(c.z_cm):g} [cm] de profundidad: sus puntos no van en posición creciente "
                                         f"(x = {c.x_cm[i]:g} [cm] y luego {c.x_cm[i + 1]:g} [cm]): una posición está dañada")


def revisar_perfil(p):
    """Un `PerfilOAR`: OAR mayor que 0 y no más que OAR_MAXIMO; sin picos (estricto en el núcleo, que es lo que el motor usa, y laxo en la penumbra y la cola,
    que solo alimentan el aviso de la pérdida junto al borde)."""
    nombre = f"el perfil abierto de {p.lado:g} × {p.lado:g} [cm] a {p.prof:g} [cm] de profundidad"
    i = int(np.argmax(p.oar))
    if p.oar[i] > OAR_MAXIMO:
        raise BarreraDePlausibilidad(f"{nombre} tiene un OAR de {motor.cifras(p.oar[i], OAR_MAXIMO, 4, 'g')} en x = {p.x[i]:g} [cm], y no puede pasar de {OAR_MAXIMO:g}: un valor está dañado "
                                     "(¿un punto decimal perdido?)")
    i = int(np.argmin(p.oar))
    if not p.oar[i] > 0:
        raise BarreraDePlausibilidad(f"{nombre} tiene un OAR de {p.oar[i]:.4g} en x = {p.x[i]:g} [cm], y debe ser mayor que 0: un valor está dañado")
    borde = p.lado / 2 * (p.ssd + p.prof) / motor.SAD_CM
    for i in range(1, len(p.x)):
        j, k = (i - 1, i + 1) if i < len(p.x) - 1 else (i - 2, i - 1)
        desvio = abs(p.oar[i] - _recta(p.x, p.oar, i, j, k))
        if p.x[i] <= borde - NUCLEO_HASTA_EL_BORDE_CM and i < len(p.x) - 1:
            if desvio > PICO_NUCLEO:
                raise BarreraDePlausibilidad(f"{nombre} tiene un pico en x = {p.x[i]:g} [cm], dentro del campo: el OAR se aparta {motor.cifras(desvio, PICO_NUCLEO, 3, 'g')} de la recta de sus "
                                             f"vecinos (se admite {PICO_NUCLEO:g}): un valor está dañado")
        elif desvio - PICO_FRACCION_DE_LA_PENDIENTE * abs(p.oar[k] - p.oar[j]) > PICO_OAR:
            raise BarreraDePlausibilidad(f"{nombre} tiene un pico en x = {p.x[i]:g} [cm]: se aparta de sus vecinos {desvio:.3g}, más de lo que admite la pendiente "
                                         f"(se admite {PICO_OAR:g} más la mitad de la diferencia de sus vecinos): un valor está dañado")


def revisar_tabla(t, que):
    """Una tabla de factores (`que`: «la tabla abierta», «la tabla de la cuña de 30°»): entre celdas vecinas el factor no cambia más rápido que en las reales, y
    ninguna celda se aparta de la recta (en logaritmos) de sus dos vecinas de fila o de columna; en un borde, de las dos de dentro. El aviso de las celdas fuera
    de tendencia (`lector.valores_fuera_de_tendencia`, desde 0.6 %) sigue aparte: aquí solo se rechaza lo imposible."""
    m = np.log(t.m)
    for ejes, valores, celda in ((np.log(t.x), m, lambda o, i: (t.y[o], t.x[i])), (np.log(t.y), m.T, lambda o, i: (t.y[i], t.x[o]))):
        for o, fila in enumerate(valores):
            pendientes = np.diff(fila) / np.diff(ejes)
            for i, p in enumerate(pendientes):
                if not PENDIENTE_LOG_TABLA[0] <= p <= PENDIENTE_LOG_TABLA[1]:
                    (y0, x0), (y, x) = celda(o, i), celda(o, i + 1)     # UM.2 v2 (B3): las dos celdas; cuál está dañada no se sabe
                    raise BarreraDePlausibilidad(f"{que} salta entre la celda Y = {y0:g} [cm], X = {x0:g} [cm] (valor {math.exp(fila[i]):g}) y la Y = {y:g} [cm], "
                                                 f"X = {x:g} [cm] (valor {math.exp(fila[i + 1]):g}): entre celdas vecinas "
                                                 f"el factor cambia como el lado elevado a {motor.cifras(p, PENDIENTE_LOG_TABLA[0] if p < PENDIENTE_LOG_TABLA[0] else PENDIENTE_LOG_TABLA[1], 3, 'g')}, y en un haz real va de {PENDIENTE_LOG_TABLA[0]:g} a "
                                                 f"{PENDIENTE_LOG_TABLA[1]:g}: un valor está dañado")
            for i in range(len(fila) if len(fila) >= 3 else 0):
                j, k = (i - 1, i + 1) if 0 < i < len(fila) - 1 else (1, 2) if i == 0 else (i - 2, i - 1)
                umbral = DESVIO_LINEA_TABLA if 0 < i < len(fila) - 1 else DESVIO_BORDE_TABLA
                if abs(fila[i] - _recta(ejes, fila, i, j, k)) > umbral:
                    y, x = celda(o, i)
                    raise BarreraDePlausibilidad(f"{que}: el valor en Y = {y:g} [cm], X = {x:g} [cm] se aparta {motor.cifras(100 * abs(fila[i] - _recta(ejes, fila, i, j, k)), 100 * umbral, 3, 'g')} [%] "
                                                 f"de lo que dicen {'sus dos vecinas' if 0 < i < len(fila) - 1 else 'las dos celdas de dentro'} de la misma fila o "
                                                 f"columna (se admite {100 * umbral:g} [%]): un valor está dañado")
