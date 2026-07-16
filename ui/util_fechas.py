"""Utilidades de widgets de fecha (I5, PLAN_FASE_I 2026-07-16).

Por qué existe: H3.5 protegió el "combo de mes" con `setMinimumWidth(100)`
-- un valor ABSOLUTO calibrado con la fuente del entorno de desarrollo
(Noto Sans, texto "07/2026" ≈ 53px). En el Windows real del físico (Segoe
UI, escala 125% típica) el mismo texto es más ancho y el campo siguió
viéndose cortado. Cualquier constante en px repite el problema en la
próxima pantalla/fuente/escala: el mínimo debe salir de la MÉTRICA DE
FUENTE del propio widget en runtime.
"""
import re

# Decoración fija alrededor del texto, según resources/estilo.qss:
# QDateEdit::drop-down width 20px + padding 5px por lado + borde 2px por
# lado, más una holgura pequeña contra redondeos de DPI fraccionario.
_DROP_DOWN_PX = 20
_PADDING_PX = 10
_BORDES_PX = 4
_HOLGURA_PX = 8
RESERVA_DECORACION_PX = _DROP_DOWN_PX + _PADDING_PX + _BORDES_PX + _HOLGURA_PX


def ancho_minimo_fecha(date_edit, formato=None):
    """Ancho mínimo (px) para que un QDateEdit muestre completo el texto de
    su formato junto a la flecha del calendario, con la fuente REAL del
    widget.

    formato: si se omite se usa el displayFormat() actual del widget. Los
    formularios mensuales cambian el formato a "MM/yyyy" DESPUÉS de crear el
    widget (seiscientos_mensual), así que el creador genérico pasa el más
    ancho de los formatos en uso ("dd/MM/yyyy") para cubrir ambos casos.
    """
    fmt = formato or date_edit.displayFormat()
    # "dd/MM/yyyy" -> "00/00/0000": cada letra de formato ocupa ~1 dígito.
    muestra = re.sub(r"[A-Za-z]", "0", fmt)
    fm = date_edit.fontMetrics()
    return fm.horizontalAdvance(muestra) + RESERVA_DECORACION_PX
