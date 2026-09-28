"""Una sola definición de los tres voltajes de "LECTURAS DEL MÁXIMO"
(braquiterapia: mensual, cambio de fuente y calibración redundante).

V.1 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, tercera ronda): antes de esta
tarea, "¿cuál voltaje es el alto?" tenía DOS respuestas distintas en el
código (max/min de las lecturas en `braq_mensual.py`, `max(key=abs)` en
`load.py`), y la fórmula de Ks tenía el cociente 300/150 escrito a mano
(`(4/3) - .../(3*...)`). Este módulo es la única definición: cómo un texto
se vuelve voltaje, qué voltaje es alto/bajo/negativo, y cómo se reconstruye
un bloque guardado -- para que todos los caminos (calcular, guardar, leer)
usen la misma regla.

Contrato de almacenamiento (medido en `guardar_resultado_CambioFuente`,
`data/ManejoDatos/load.py`): la tabla `LecturasMaximos` guarda una fila por
VOLTAJE, con sus tres medidas repartidas por POSICIÓN entre las columnas
`V_300`/`V_150`/`Vn_300` -- esos nombres son HISTÓRICOS y significan el
PAPEL alto/bajo/negativo, no literalmente 300/150/-300 V. La fila del
voltaje de papel k guarda la medida k+1 de las tres medidas de CADA
voltaje. Ejemplo real (`ref` 24, Calibración Redundante del 29-12-2025,
BD de referencia):

    voltaje | V_300 (col. del alto) | V_150 (col. del bajo) | Vn_300 (col. del negativo)
    300.0   | medida 1 del alto     | medida 1 del bajo      | medida 1 del negativo
    150.0   | medida 2 del alto     | medida 2 del bajo      | medida 2 del negativo
    -300.0  | medida 3 del alto     | medida 3 del bajo      | medida 3 del negativo

`lecturas_por_voltaje` reconstruye esto sin depender del orden en que la
BD entregue las filas (con el índice único `idx_LecturasMaximos_bloque_
activo` llegan en orden de TEXTO del voltaje, no en el de inserción).
"""
import math

# V.5 (misma tarea, tercera ronda): valores por defecto, decisión del
# físico del 28-09 -- el formato vigente (IDC-F-RT-143 V.03, cambio de
# fuente del 27-09-2026) mide a 300 / 50 / -300 V, no a 300 / 150 / -300
# como hacía la app hasta hoy. El texto es exactamente el que escribe
# `generar_tabla_lecturas` en las celdas (sin ".0").
VOLTAJES_POR_DEFECTO = ("300", "50", "-300")

# Fila 0 = alto, fila 1 = bajo, fila 2 = polaridad opuesta (negativo).
FILA_ALTO, FILA_BAJO, FILA_NEGATIVO = 0, 1, 2


class VoltajesInvalidos(ValueError):
    """Un trío de voltajes -- escrito en el formulario o leído de un
    bloque guardado -- no describe una medida de braquiterapia válida:
    alto positivo, bajo positivo y menor que el alto, negativo la
    polaridad opuesta del alto. El mensaje va tal cual a un
    `QMessageBox`: en castellano, sin símbolos (DA-18)."""


def voltaje_de_texto(texto):
    """Convierte el texto de una celda de voltaje a `float`. Acepta el
    signo menos tipográfico (U+2212) además del ASCII. Rechaza vacío, no
    numérico, NaN, infinito y cero -- ninguno describe un voltaje real."""
    if texto is None:
        raise VoltajesInvalidos("Falta escribir un voltaje.")
    limpio = str(texto).strip().replace("−", "-")
    if not limpio:
        raise VoltajesInvalidos("Falta escribir un voltaje.")
    try:
        valor = float(limpio)
    except ValueError:
        raise VoltajesInvalidos(
            f"'{texto}' no es un voltaje válido (use punto decimal).")
    if not math.isfinite(valor):
        raise VoltajesInvalidos(f"'{texto}' no es un voltaje válido.")
    if valor == 0:
        raise VoltajesInvalidos("El voltaje no puede ser cero.")
    return valor


def validar_roles(alto, bajo, negativo):
    """Exige `alto > 0`, `0 < bajo < alto` y `negativo == -alto`. El
    mensaje describe SOLO la condición (sin nombrar "alto"/"bajo"): quien
    llama (`_voltajes_del_formulario`, en la pantalla) antepone la fila y
    el papel; `roles_de_voltajes` (sin pantalla detrás) lo deja tal cual."""
    if not (alto > 0):
        raise VoltajesInvalidos(f"debe ser positivo (se escribió {alto}).")
    if not (0 < bajo < alto):
        raise VoltajesInvalidos(
            f"debe ser positivo y menor que el alto ({alto}).")
    if negativo != -alto:
        raise VoltajesInvalidos(
            f"debe ser la polaridad opuesta del alto (se esperaba "
            f"{-alto}, se escribió {negativo}).")


def roles_de_voltajes(voltajes):
    """De tres voltajes en CUALQUIER orden (iterable de números), decide
    cuál es alto, bajo y negativo: dos positivos y uno negativo; alto =
    el positivo mayor, bajo = el positivo menor. Valida con
    `validar_roles` antes de devolver `(alto, bajo, negativo)`."""
    valores = list(voltajes)
    if len(valores) != 3:
        raise VoltajesInvalidos(
            f"Se necesitan exactamente tres voltajes (se encontraron "
            f"{len(valores)}).")
    if any(v == 0 for v in valores):
        raise VoltajesInvalidos("Ningún voltaje puede ser cero.")
    if len(set(valores)) != 3:
        raise VoltajesInvalidos("Los tres voltajes deben ser distintos.")
    positivos = sorted((v for v in valores if v > 0), reverse=True)
    negativos = [v for v in valores if v < 0]
    if len(positivos) != 2 or len(negativos) != 1:
        raise VoltajesInvalidos(
            "Se necesitan dos voltajes positivos (alto y bajo) y uno "
            "negativo (la polaridad opuesta).")
    alto, bajo = positivos
    negativo = negativos[0]
    validar_roles(alto, bajo, negativo)
    return alto, bajo, negativo


def lecturas_por_voltaje(filas):
    """De las filas que guarda `LecturasMaximos` para UN bloque -- cada
    una `(voltaje, V_300, V_150, Vn_300)` o `(voltaje, V_300, V_150,
    Vn_300, promediosV)`, en CUALQUIER orden -- reconstruye

        [(voltaje, [m1, m2, m3], promedio), ...]

    en orden alto, bajo, negativo, con las medidas de CADA voltaje en su
    propia fila (no las de la fila que la BD entregó). `V_300` -> alto,
    `V_150` -> bajo, `Vn_300` -> negativo (el contrato del módulo); la
    fila del voltaje de papel k guarda la medida k+1 de las tres. Sin
    `promediosV`, el promedio es `None`. El `voltaje` devuelto es el
    valor CRUDO de la fila (sin reformatear); las medidas, también.
    Si no hay exactamente 3 filas o los papeles no valen:
    `VoltajesInvalidos`."""
    filas = list(filas)
    if len(filas) != 3:
        raise VoltajesInvalidos(
            f"Se esperaban 3 filas de lecturas, se encontraron "
            f"{len(filas)}.")
    if any(len(f) < 4 for f in filas):
        raise VoltajesInvalidos(
            "Una fila de lecturas no tiene las 4 columnas mínimas "
            "(voltaje, V_300, V_150, Vn_300).")
    numeros = [voltaje_de_texto(f[0]) for f in filas]
    alto, bajo, negativo = roles_de_voltajes(numeros)
    por_voltaje = {n: f for n, f in zip(numeros, filas)}
    # Orden por PAPEL (no por orden de entrada): fila del alto, del bajo,
    # del negativo -- así "columna_de[v]" siempre lee la medida correcta,
    # sea cual sea el orden en que la BD entregó las filas.
    orden = [por_voltaje[alto], por_voltaje[bajo], por_voltaje[negativo]]
    columna_de = {alto: 1, bajo: 2, negativo: 3}  # V_300, V_150, Vn_300
    resultado = []
    for v in (alto, bajo, negativo):
        col = columna_de[v]
        medidas = [orden[k][col] for k in range(3)]
        fila_v = por_voltaje[v]
        promedio = fila_v[4] if len(fila_v) > 4 else None
        resultado.append((fila_v[0], medidas, promedio))
    return resultado


def texto_espejo(texto, signo):
    """La magnitud escrita en `texto`, sin signo (quita espacios, `+`,
    `-` y el signo menos tipográfico), precedida de `-` si `signo < 0`.
    Cadena vacía si no queda nada. Es una operación de TEXTO, no de
    número: no redondea ni reformatea los decimales escritos
    (`"250.5"` -> `"-250.5"`)."""
    if texto is None:
        return ""
    limpio = texto.strip()
    limpio = limpio.lstrip("+")
    if limpio[:1] in ("-", "−"):
        limpio = limpio[1:]
    limpio = limpio.strip()
    if not limpio:
        return ""
    return ("-" + limpio) if signo < 0 else limpio
