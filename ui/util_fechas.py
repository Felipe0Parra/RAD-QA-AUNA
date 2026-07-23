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

from PyQt5.QtCore import QDate

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
    formularios mensuales cambian el formato DESPUÉS de crear el widget
    (seiscientos_mensual) -- desde F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md) a
    "dd/MM/yyyy" (antes "MM/yyyy"), así que el creador genérico pasa el más
    ancho de los formatos en uso para cubrir ambos casos.
    """
    fmt = formato or date_edit.displayFormat()
    # "dd/MM/yyyy" -> "00/00/0000": cada letra de formato ocupa ~1 dígito.
    muestra = re.sub(r"[A-Za-z]", "0", fmt)
    fm = date_edit.fontMetrics()
    return fm.horizontalAdvance(muestra) + RESERVA_DECORACION_PX


def fecha_control_a_qdate(fecha_texto):
    """Convierte un texto de `controles.fecha` a QDate, tolerando el formato
    viejo sin día ("MM/yyyy", controles anteriores a F3) y el nuevo con día
    ("dd/MM/yyyy", PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4). Se prueba
    primero el formato con día porque Qt rechaza como inválido un texto que
    no calza exactamente ese patrón (verificado: "07/2026" contra
    "dd/MM/yyyy" da isValid()==False, nunca un día inventado) -- solo si
    falla se intenta el formato viejo, con día 1. Si ninguno calza, devuelve
    la fecha actual (mismo resultado que un `setDate` fallido dejaría antes
    de esta función: el widget no queda con una fecha inválida)."""
    fecha_con_dia = QDate.fromString(fecha_texto, "dd/MM/yyyy")
    if fecha_con_dia.isValid():
        return fecha_con_dia
    fecha_sin_dia = QDate.fromString(fecha_texto, "MM/yyyy")
    if fecha_sin_dia.isValid():
        return QDate(fecha_sin_dia.year(), fecha_sin_dia.month(), 1)
    return QDate.currentDate()
