"""Coloca las filas guardadas de una tabla de niveles por su ángulo, no por su posición."""
import math


def angulo(valor):
    """El ángulo como número: «270°», «270», 270.0 y «270.0°» dan 270.0; lo que no es un ángulo da None."""
    try:
        numero = float(str(valor).replace("°", "").strip())
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def filas_por_nivel(filas, niveles, ancho):
    """Una fila por nivel, en el orden de `niveles`: la guardada de ese ángulo tal cual, o la vacía con su etiqueta."""
    guardadas = {}
    for fila in filas:
        clave = angulo(fila[0]) if len(fila) else None
        if clave is not None and clave not in guardadas:
            guardadas[clave] = fila
    return [guardadas.get(angulo(nivel), [nivel] + [""] * (ancho - 1)) for nivel in niveles]
