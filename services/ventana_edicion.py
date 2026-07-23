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


def puede_editarse(control_id, hoy=None):
    """True si `control_id` sigue dentro de la ventana de 2 meses. Sin
    ancla resoluble (ver fecha_ancla_de_control), no bloquea."""
    if not control_id:
        return True
    ancla, _ = fecha_ancla_de_control(control_id)
    if ancla is None:
        return True
    hoy = hoy or date.today()
    return hoy <= limite_edicion(ancla)


def mensaje_bloqueo_edicion(control_id):
    """Texto explicando por qué un control ya no admite edición, y desde
    cuándo se cuenta el plazo -- para mostrarlo tal cual en el aviso de
    'Subir' bloqueado."""
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
