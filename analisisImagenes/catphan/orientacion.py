"""OR.1 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, cierra DP-126): LA transformacion de un angulo NOMINAL del fantoma a su posicion en la imagen que muestra la aplicacion.

El fantoma Catphan puede estar girado (el giro `R` que mide el motor pylinac, `catphan_roll`) y, en el Halcyon de septiembre, invertido (la serie llega al reves y el motor la
voltea para analizarla). Todo lo que se mide en una posicion fija del fantoma -- los 6 insertos y los fondos de CTP515, las regiones del anillo de CTP528, los 7 materiales de
CTP404 -- parte de un angulo NOMINAL (el del fantoma derecho y sin giro) y necesita su angulo real en la imagen. Esa cuenta vivia escrita en linea tres veces
(`Analisis_Catphan_TAC._angulo_efectivo`, la inversa dentro de `resolucion_espacial` y `GeometriaCatphan._calcular_roi_float`), las tres con el signo del giro mal para el fantoma
invertido (`180 - theta + R` en lugar de `180 - theta - R`: yerra exactamente 2R, porque al voltear la imagen el giro que mide pylinac cambia de sentido), y CTP404 no la usaba.
Aqui esta UNA sola, sin dependencias (evita el import circular entre el analisis y la geometria); un tripwire por AST impide que vuelva a escribirse en otro sitio.

Convencion de pylinac: x = cos, y = sin, y hacia abajo. `roll_deg` es el `catphan_roll` del motor, medido en el marco que analizo pylinac (volteado si la serie es invertida).
"""

import math

ORIENTACIONES = ("normal", "invertido")


def angulo_en_imagen(angulo, orientacion="normal", roll_deg=0.0, *, inversa=False):
    """Angulo NOMINAL (fantoma derecho y sin giro) -> angulo en el corte SIN voltear que muestra la aplicacion.

      normal   : phi = theta + R
      invertido: phi = 180 - theta - R      (voltear en x convierte el angulo `a` de pylinac en 180 - a, y a = theta + R)

    `inversa=True` da theta a partir de phi: normal, `phi - R`; invertido, la misma formula (la reflexion es su propia inversa).
    Acepta escalares o arreglos de numpy. Con ("normal", 0.0) devuelve el angulo tal cual (la conducta anterior a D.1).

    Revision de OR.1: una orientacion que no sea exactamente «normal» o «invertido» (otra capitalizacion, `None`...) o un giro que no sea un numero finito se RECHAZAN con
    `ValueError`. Antes todo lo que no era la cadena exacta «invertido» se tomaba por «normal» sin aviso: justo el error de espejo que esta tarea cierra."""
    if orientacion not in ORIENTACIONES:
        raise ValueError(f"orientacion desconocida: {orientacion!r} (debe ser 'normal' o 'invertido')")
    try:
        giro = float(roll_deg)
    except (TypeError, ValueError):
        raise ValueError(f"el giro del fantoma debe ser un numero, no {roll_deg!r}") from None
    if not math.isfinite(giro):
        raise ValueError(f"el giro del fantoma debe ser un numero finito, no {roll_deg!r}")
    if orientacion == "invertido":
        return 180.0 - angulo - giro
    return (angulo - giro) if inversa else (angulo + giro)
