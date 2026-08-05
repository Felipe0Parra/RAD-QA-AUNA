"""F4b (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4, tarea C1 del plan de
auditoría): un control de QC mensual solo admite edición ("Subir" hace
UPDATE) dentro de una ventana de 2 meses calendario desde que se creó --
decisión del físico (2026-07-23). Fuera de esa ventana el registro se
puede seguir CONSULTANDO (cargar, ver, generar PDF) -- nunca se bloquea la
lectura, solo el guardado.

El ancla NO puede ser `controles.fecha`: es un campo que el propio
formulario guarda y el usuario elige, así que retrodatarlo reabriría la
ventana a voluntad (riesgo ya identificado en
PLAN_AUDITORIA_DOS_EJES_21-07.md SS7, P3). El ancla real es el timestamp
de `audit_log` de la PRIMERA vez que `create_control` (F4c) creó ese
control -- un reloj que la app nunca deja tocar al usuario.

Los 24 controles que ya existían en producción ANTES de que F4c empezara
a auditar no tienen ninguna fila en `audit_log` con tabla='controles'.
Para esos (y solo para esos) se usa una regla de respaldo: el ÚLTIMO DÍA
del mes que el propio control declara en `controles.fecha`. No inventa un
dato más preciso del que existe -- y como la ventana es de 2 meses, deja
cerrados los controles antiguos (2025) y abiertos los recientes (2026)
sin ningún ALTER TABLE ni backfill.
"""
import calendar
import sqlite3
from datetime import date, datetime

from data.ManejoDatos import conection as _conection
from services.fechas_control import mes_anio_de_fecha

MESES_VENTANA_EDICION = 2


def _ultimo_dia_del_mes(mes, anio):
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def _sumar_meses(fecha, meses):
    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def limite_edicion(fecha_ancla):
    """Último día en que un control con esa fecha ancla admite edición."""
    return _sumar_meses(fecha_ancla, MESES_VENTANA_EDICION)


def fecha_ancla_de_control(control_id):
    """(fecha_ancla, origen) para `control_id` -- origen es "auditoria"
    (el caso normal, desde F4c) o "respaldo" (controles creados antes de
    F4c, sin fila en audit_log). (None, "desconocido") si no hay ninguna
    fecha reconocible ni en audit_log ni en controles.fecha -- en ese caso
    `puede_editarse` NO bloquea (ante un dato sucio aislado, se prioriza no
    interrumpir un flujo de trabajo real)."""
    con = sqlite3.connect(_conection.ruta_base_datos())
    try:
        fila = con.execute(
            "SELECT MIN(timestamp) FROM audit_log "
            "WHERE tabla = 'controles' AND accion = 'guardar' AND ref = ?",
            (str(control_id),)
        ).fetchone()
        marca = fila[0] if fila else None
        fecha_control = None
        if not marca:
            fila_control = con.execute(
                "SELECT fecha FROM controles WHERE id = ?", (control_id,)
            ).fetchone()
            fecha_control = fila_control[0] if fila_control else None
    finally:
        con.close()

    if marca:
        try:
            return datetime.strptime(marca, "%Y-%m-%d %H:%M:%S").date(), "auditoria"
        except ValueError:
            pass

    mes, anio = mes_anio_de_fecha(fecha_control)
    if mes is not None:
        return _ultimo_dia_del_mes(mes, anio), "respaldo"

    return None, "desconocido"


def _estado_control(control_id):
    """(existe, activo) para `control_id`. Si no hay fila, (False, False).

    W1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): el incidente real del
    23-07 -- el físico anuló/eliminó un control desde la vista de registros
    mientras el formulario mensual seguía abierto sobre ese mismo id, y
    "Subir" siguió escribiendo dosimetría huérfana porque `puede_editarse`
    solo miraba la franja de 2 meses, nunca si el control seguía existiendo.
    Con C2, "eliminado" es `activo=0` (soft-delete) -- un control anulado
    sigue teniendo fila, así que "existe" por sí solo ya no basta.
    """
    con = sqlite3.connect(_conection.ruta_base_datos())
    try:
        fila = con.execute(
            "SELECT activo FROM controles WHERE id = ?", (control_id,)
        ).fetchone()
    finally:
        con.close()
    if fila is None:
        return False, False
    activo = fila[0]
    return True, (activo is None or activo == 1)


def _motivo_estructural(control_id):
    """Parte de la clasificación que NO depende del reloj: si el control
    existe y si sigue activo. Separada a propósito de la parte TEMPORAL (la
    ventana de 2 meses) porque `mensaje_bloqueo_edicion` necesita la primera
    y NO debe evaluar la segunda -- ver su docstring."""
    existe, activo = _estado_control(control_id)
    if not existe:
        return "inexistente"
    if not activo:
        return "anulado"
    return None


def motivo_bloqueo(control_id, hoy=None):
    """Por qué `control_id` no admite edición ahora mismo, o None si sí la
    admite: "inexistente" | "anulado" | "fuera_de_ventana" | None.

    N3 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): los dos puntos de
    "Subir" necesitan DISTINGUIR el motivo -- solo "anulado" ofrece
    reactivar (DA-34); "fuera_de_ventana" debe seguir bloqueando sin más
    (F4b/C1).
    """
    if not control_id:
        return None
    motivo = _motivo_estructural(control_id)
    if motivo is not None:
        return motivo
    ancla, _ = fecha_ancla_de_control(control_id)
    if ancla is None:
        return None
    hoy = hoy or date.today()
    return None if hoy <= limite_edicion(ancla) else "fuera_de_ventana"


def puede_editarse(control_id, hoy=None):
    """True si `control_id` existe, sigue activo (no anulado) y está dentro
    de la ventana de 2 meses. Sin ancla resoluble (ver
    fecha_ancla_de_control) pero con el control existente y activo, no
    bloquea por fecha.

    Fuente ÚNICA con `motivo_bloqueo`: si divergieran, un call-site podría
    bloquear sin saber por qué -- y N3 nunca ofrecería reactivar.
    """
    return motivo_bloqueo(control_id, hoy=hoy) is None


def mensaje_bloqueo_edicion(control_id):
    """Texto explicando por qué un control ya no admite edición, y desde
    cuándo se cuenta el plazo -- para mostrarlo tal cual en el aviso de
    'Subir' bloqueado.

    NO vuelve a comprobar la fecha, a propósito: se invoca SIEMPRE detrás de
    un `if not puede_editarse(ref)`, así que el llamador ya decidió que está
    bloqueado y aquí solo se redacta la explicación. Por eso se construye
    sobre `_motivo_estructural` y no sobre `motivo_bloqueo`: con un control
    existente y activo el único motivo posible es la ventana, y se describe
    con su fecha límite sin volver a compararla contra el reloj (mismo
    comportamiento que fijan los tests de F4b desde el 23-07).
    """
    motivo = _motivo_estructural(control_id)
    if motivo == "inexistente":
        return (
            "Este control ya no existe en la base de datos (fue "
            "eliminado desde otra pestaña) -- no se pueden guardar datos "
            "nuevos sobre un registro que ya no está."
        )
    if motivo == "anulado":
        return (
            "Este control fue anulado -- no se pueden guardar más datos "
            "sobre un registro eliminado."
        )
    ancla, _ = fecha_ancla_de_control(control_id)
    if ancla is None:
        return ("Este control ya no admite edición.")
    limite = limite_edicion(ancla)
    return (
        f"Este control ya superó la ventana de edición de "
        f"{MESES_VENTANA_EDICION} meses (vigente hasta el "
        f"{limite.strftime('%d/%m/%Y')}). Los datos se pueden seguir "
        f"consultando, pero ya no se pueden modificar."
    )
