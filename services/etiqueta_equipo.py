"""F9 (PLAN_F_CIERRE_ESTANDAR_29-07.md §9): etiqueta visible de una fila de
equipo, compartida por los tres selectores que necesitan mostrar "qué
calibración es esta y si sigue vigente" -- la calculadora de dosis, el
selector de equipos del formulario mensual/TAC, y (para el aviso de
vencido) braquiterapia diaria y mensual.

Antes de F9 cada selector construía su propio texto a mano, con símbolos
distintos entre sí (✓/⚠️/"(VENCIDO)") y comparando siempre contra la
columna `equipos.vigente` congelada (F8 ya la retiró del contrato). Un solo
punto de formato evita que un selector nuevo reintroduzca un símbolo o una
comparación contra la columna vieja.
"""
from services.vigencia_equipo import es_vigente_en_fecha


def etiqueta_equipo(equipo, fecha_referencia):
    """Dada una fila de equipo (mapping con al menos `id` y `serie`; si
    trae también `fecha_calibr`/`equip_type` se agrega la fecha y, si
    corresponde, la marca de vencida) y una fecha de referencia (QDate),
    devuelve `(texto_visible, id_equipo)`.

    Sin símbolos: "Serie: 1822 — calibrado 21/07/2025" o
    "Serie: 1822 — calibrado 21/07/2025 (vencida)". Sin `fecha_calibr` la
    etiqueta se queda en "Serie: X" (nunca marca vencida sin fecha con la
    que evaluarla -- mismo criterio permisivo de `es_vigente_en_fecha`).
    """
    serie = equipo["serie"]
    fecha_calibr = equipo.get("fecha_calibr")
    equip_type = equipo.get("equip_type")

    texto = f"Serie: {serie}"
    if fecha_calibr:
        texto += f" — calibrado {fecha_calibr}"
        if not es_vigente_en_fecha(fecha_calibr, equip_type, fecha_referencia):
            texto += " (vencida)"

    return texto, equipo["id"]


# Texto que los combos de serie usan como "todavía no se ha elegido nada".
# Se declara aquí, junto al formato, para que `serie_de_etiqueta` y el
# guardado (T.2) coincidan sobre qué NO es una serie.
MARCADOR_SERIE = "Seleccionar Serie..."


def serie_de_etiqueta(texto):
    """T.1 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §2): INVERSO de
    `etiqueta_equipo` -- de la etiqueta visible a la serie real.

        "Serie: A092535 — calibrado 28/07/2025 (vencida)" -> "A092535"
        "Serie: A092535 — calibrado 28/07/2025"           -> "A092535"
        "Serie: A092535"                                  -> "A092535"
        "A092535 (vencida)"                               -> "A092535"
        "A092535"                                         -> "A092535"
        "Seleccionar Serie..."                            -> ""

    Por qué vive aquí y no en el formulario: es la otra mitad del mismo
    formato (corolario 1, *una operación, una definición*). Mientras el
    inverso vivió en `braq_mensual._limpiar_serie` -- que solo quitaba un
    `" (vencida)"` final -- la recarga de braqui **no encontraba NINGÚN**
    control anterior al 31-07, ni siquiera con la cámara activa: comparaba
    `"Serie: A092535 — calibrado 28/07/2025"` contra `"A092535"`
    (`DP-105`). Un formato cuyo inverso vive en otro archivo diverge en
    cuanto el formato cambia, que es exactamente lo que pasó con `G10`.

    Tolerante a lo que YA está escrito en la BD: hay filas guardadas con la
    serie limpia (las 14 anteriores a `G10`), una con la etiqueta decorada
    completa (`SistemaMedicion` ref 36) y una con el propio marcador de
    posición (`LinealidadBraquiterapia` id 10). Las tres formas entran por
    aquí y salen bien -- el marcador sale como cadena VACÍA, que es lo
    honesto: no es una serie.

    No adivina: si el texto no tiene ninguna de las decoraciones conocidas
    se devuelve tal cual (solo recortado), nunca se parte por un separador
    que no se puso aquí.
    """
    if texto is None:
        return ""
    texto = str(texto).strip()

    if texto == MARCADOR_SERIE:
        return ""

    if texto.endswith(" (vencida)"):
        texto = texto[:-len(" (vencida)")]

    # El separador es el mismo em-dash que escribe `etiqueta_equipo`.
    if " — calibrado " in texto:
        texto = texto.split(" — calibrado ", 1)[0]

    if texto.startswith("Serie: "):
        texto = texto[len("Serie: "):]

    return texto.strip()
