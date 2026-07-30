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
