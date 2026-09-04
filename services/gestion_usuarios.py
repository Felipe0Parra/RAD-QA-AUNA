"""U3 (PLAN_PESTANA_USUARIOS_02-09.md): única puerta a `users` para la
pestaña de usuarios registrados -- alta (`U4`, reusa `add_user`), listar,
dar de baja, reactivar y cambiar de rol (`U4-bis`). Sin Qt, para poder
testear la regla de permisos sin construir un `QWidget` (mismo precedente
que `services/visor_anulados.py`, `LR6`).

El permiso se verifica AQUÍ, no solo en la UI: ocultar un botón no es un
control de acceso. Las tres operaciones que cambian estado verifican
`es_fisico_jefe(username_solicitante)` (services/permisos.py, U1) y
auditan tanto el éxito como el intento denegado -- mismo criterio que
`equipos.py:431` (DialogAdminPermisoEliminar audita el intento denegado
por sí sola).

`users` NO es una tabla del bloque de QC (no está en `TABLAS_ANULABLES`):
su soft-delete es la columna `active` que ya existe desde antes de este
plan, no el mecanismo de anular+insertar de `services/anulacion.py`.
"""
from data.ManejoDatos.conection import Conexion
from services.audit_minimo import (
    ACCION_ANULAR, ACCION_REACTIVAR, registrar as _registrar_auditoria)
from services.permisos import ROLES_GESTION_USUARIOS, es_fisico_jefe

DENEGADO_SIN_PERMISO = "denegado: sin permiso de gestión de usuarios"


def _nombre_completo(cursor, username):
    """Resuelve el fullname de `username` (columna `user`, login) para
    auditar con la MISMA identidad que el resto del audit_log (A6.2-bis)
    -- si no se resuelve (cuenta inexistente), se audita con el propio
    login en vez de perder el rastro."""
    cursor.execute("SELECT fullname FROM users WHERE user=?", (username,))
    fila = cursor.fetchone()
    return fila[0] if fila else username


def _quedaria_sin_jefes(cursor, username_objetivo):
    """True si, tras afectar a `username_objetivo` (dar de baja o
    quitarle el rol de gestión en `cambiar_rol_sistema`, U4-bis), no
    quedaría NINGUNA cuenta activa capaz de administrar usuarios.

    Compartida por `dar_de_baja` y `cambiar_rol_sistema` a propósito:
    dos copias de esta guarda es exactamente el patrón (dos limpiadores
    que discrepan) que produjo DP-79."""
    placeholders = ",".join("?" * len(ROLES_GESTION_USUARIOS))
    cursor.execute(
        f"SELECT COUNT(*) FROM users "
        f"WHERE lower(user) != ? AND rol_sistema IN ({placeholders}) "
        f"AND COALESCE(active,1)=1",
        (str(username_objetivo).strip().lower(), *ROLES_GESTION_USUARIOS))
    return cursor.fetchone()[0] == 0


def listar_usuarios():
    """Columnas EXPLÍCITAS -- nunca `SELECT *`: `password` (cifrada) y
    `firma` (imagen real de la persona) no salen de aquí (O-6). Devuelve
    una lista de dicts (no tuplas posicionales) para que un consumidor
    nunca dependa del ORDEN de las columnas."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, user, fullname, role, rol_sistema, "
            "COALESCE(active,1) AS active FROM users ORDER BY fullname")
        columnas = [d[0] for d in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def dar_de_baja(username_objetivo, username_solicitante):
    """`active=0`. NO borra: `trg_no_borrar_users` lo prohíbe y
    `fullname` es la identidad de todo el historial de QC (braqui.user_id,
    audit_log.usuario, controles.user_id/_f2)."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        nombre_solicitante = _nombre_completo(cursor, username_solicitante)

        if not es_fisico_jefe(username_solicitante):
            _registrar_auditoria(nombre_solicitante, ACCION_ANULAR, "users",
                                  ref=username_objetivo, detalle=DENEGADO_SIN_PERMISO)
            return False

        # O-3(i): nadie se da de baja a sí mismo -- ni el jefe.
        if str(username_objetivo).strip().lower() == str(username_solicitante).strip().lower():
            _registrar_auditoria(
                nombre_solicitante, ACCION_ANULAR, "users", ref=username_objetivo,
                detalle="denegado: no puede darse de baja a sí mismo")
            return False

        # O-3(ii): no se apaga la última cuenta capaz de administrar usuarios.
        if _quedaria_sin_jefes(cursor, username_objetivo):
            _registrar_auditoria(
                nombre_solicitante, ACCION_ANULAR, "users", ref=username_objetivo,
                detalle="denegado: quedaría sin nadie que administre usuarios")
            return False

        cursor.execute("UPDATE users SET active=0 WHERE user=?", (username_objetivo,))
        if cursor.rowcount == 0:
            return False  # la cuenta objetivo no existe -- nada que auditar
        db.commit()
        _registrar_auditoria(nombre_solicitante, ACCION_ANULAR, "users",
                              ref=username_objetivo, detalle="baja")
        return True


def reactivar(username_objetivo, username_solicitante):
    """La inversa de `dar_de_baja`. Existe porque una baja sin vuelta
    atrás, en una app donde el borrado físico es imposible, convertiría
    un clic equivocado en un daño permanente."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        nombre_solicitante = _nombre_completo(cursor, username_solicitante)

        if not es_fisico_jefe(username_solicitante):
            _registrar_auditoria(nombre_solicitante, ACCION_REACTIVAR, "users",
                                  ref=username_objetivo, detalle=DENEGADO_SIN_PERMISO)
            return False

        cursor.execute("UPDATE users SET active=1 WHERE user=?", (username_objetivo,))
        if cursor.rowcount == 0:
            return False
        db.commit()
        _registrar_auditoria(nombre_solicitante, ACCION_REACTIVAR, "users",
                              ref=username_objetivo, detalle="reactivado")
        return True
