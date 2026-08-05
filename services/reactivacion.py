"""N2 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): punto único para
reactivar un control mensual/anual anulado.

Origen: el físico anuló un control mensual (C2, soft-delete) y descubrió que
`create_control` lo seguía encontrando y ofreciéndolo como "el control del
mes" -- con `puede_editarse` bloqueando cualquier "Subir" sobre él (W1). El
mes quedaba inutilizable; el físico tuvo que crear el control siguiente en
septiembre. Decisión del físico: la anulación debe ser reversible desde la
app, con la pregunta en la misma ventana que hoy da la advertencia y
**autenticación personal** (no de administrador -- DA-07, coherente con que
editar un QC ya es reautenticación del propio físico).

Solo `controles` -- deliberadamente NO se generaliza a
`services.anulacion.TABLAS_ANULABLES`. Cada raíz del bloque de QC tiene su
propia semántica de reactivación (o ninguna, si nunca se anula desde la
interfaz); ampliar el alcance sin una necesidad demostrada multiplicaría el
riesgo sin ganar nada.
"""
import sqlite3

from data.ManejoDatos.conection import Conexion
from services.audit_minimo import ACCION_REACTIVAR
from services.audit_minimo import registrar as _registrar_auditoria
from services.fechas_control import mismo_mes as _mismo_mes


def reactivar_control(control_id, usuario):
    """Reactiva `controles.id = control_id` (`activo` 0 -> 1) y audita.

    Guarda de unicidad OBLIGATORIA (índice parcial de U2,
    `idx_controles_unico_mes`): antes de reactivar, verifica que no exista
    ya OTRO control ACTIVO del mismo (equipo, control, mes/año) -- de lo
    contrario el UPDATE chocaría contra el índice único con un
    `IntegrityError` crudo en pantalla. Si la guarda se dispara, no escribe
    nada y devuelve el motivo.

    Idempotente: reactivar un control que ya está activo no escribe ni
    audita nada -- no es un error, simplemente no había nada que hacer.

    Returns:
        (True, None) si reactivó (o si ya estaba activo).
        (False, motivo) si no -- nunca lanza, ni por un id inexistente ni
        por colisión de unicidad.
    """
    conn = Conexion().conectar()
    cursor = conn.cursor()

    fila = cursor.execute(
        "SELECT equipo, control, fecha, activo FROM controles WHERE id = ?",
        (control_id,)).fetchone()
    if fila is None:
        return False, "el control ya no existe"

    equipo, control, fecha, activo = fila
    if activo is None or activo == 1:
        return True, None  # ya estaba activo -- idempotente, nada que hacer

    otros = cursor.execute(
        "SELECT fecha FROM controles WHERE equipo = ? AND control = ? "
        "AND id != ? AND (activo IS NULL OR activo = 1)",
        (equipo, control, control_id)).fetchall()
    for (otra_fecha,) in otros:
        if _mismo_mes(otra_fecha, fecha):
            return False, "ya hay un control activo para ese mes"

    cursor.execute("UPDATE controles SET activo = 1 WHERE id = ?", (control_id,))
    conn.commit()

    _registrar_auditoria(usuario, ACCION_REACTIVAR, "controles",
                         ref=control_id, detalle="activo: 0→1")

    return True, None
