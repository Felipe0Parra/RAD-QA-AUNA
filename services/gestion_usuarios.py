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
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData
from services.audit_minimo import (
    ACCION_ACTUALIZAR, ACCION_ANULAR, ACCION_GUARDAR, ACCION_REACTIVAR,
    registrar as _registrar_auditoria)
from services.permisos import ROLES_GESTION_USUARIOS, es_fisico_jefe

DENEGADO_SIN_PERMISO = "denegado: sin permiso de gestión de usuarios"

# U4-bis: lo único que se puede ASIGNAR desde la pestaña -- 'admin' NUNCA
# se concede desde la UI (es la cuenta de instalación, la crea la
# migración del arranque). Deliberadamente distinto de
# ROLES_GESTION_USUARIOS (quién puede ADMINISTRAR, incluye 'admin').
ROLES_ASIGNABLES_DESDE_UI = {"fisico", "jefe"}


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


# U4: motivos que `crear_usuario` distingue -- `add_user` (usuariosManager.py)
# colapsa "ya existe" / "fullname vacío" / "error de BD" en un solo `None`;
# sin distinguirlos aquí, la pestaña solo podría decir "no se pudo crear",
# sin que el físico sepa por qué (O-5).
MOTIVO_CREADO = "creado"
MOTIVO_SIN_PERMISO = "sin_permiso"
MOTIVO_FULLNAME_VACIO = "fullname_vacio"
MOTIVO_USUARIO_DUPLICADO = "usuario_duplicado"
MOTIVO_ERROR_BD = "error_bd"


def crear_usuario(datos, username_solicitante):
    """Alta desde la pestaña -- delega en `UsuarioData.add_user`, la MISMA
    operación que ya usa el registro público (E6, F3, A6.2), en vez de
    reescribir el cifrado de la contraseña, la validación de `fullname` o
    la auditoría (O-5).

    `datos`: dict con `user`, `password`, `fullname` y, opcionales,
    `active` (default 1), `idreal` (default ""), `role` (cargo mostrado,
    default "Físico Médico") y `firma` (BLOB, default b"").

    El `rol_sistema` del usuario nuevo SIEMPRE nace 'fisico' -- igual que
    el registro público; ascender a 'jefe' es `U4-bis`, una operación
    aparte y deliberada, nunca un campo más de este formulario.

    Devuelve `(True, MOTIVO_CREADO)` o `(False, <uno de los MOTIVO_*>)` --
    nunca un `None` mudo que deje al físico sin saber qué pasó."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        nombre_solicitante = _nombre_completo(cursor, username_solicitante)

        if not es_fisico_jefe(username_solicitante):
            _registrar_auditoria(nombre_solicitante, ACCION_GUARDAR, "users",
                                  ref=datos.get("user"), detalle=DENEGADO_SIN_PERMISO)
            return False, MOTIVO_SIN_PERMISO

        fullname = (datos.get("fullname") or "").strip()
        if not fullname:
            return False, MOTIVO_FULLNAME_VACIO

        cursor.execute("SELECT COUNT(*) FROM users WHERE user=?", (datos.get("user"),))
        if cursor.fetchone()[0] > 0:
            return False, MOTIVO_USUARIO_DUPLICADO

    # `add_user` abre y cierra SU PROPIA conexión (usuariosManager.py) --
    # fuera del `with` de arriba para no anidar dos conexiones de escritura
    # sobre el mismo archivo.
    nuevo = Usuario(
        username=datos.get("user"), password=datos.get("password"),
        fullname=fullname, active=datos.get("active", 1),
        identificacion=datos.get("idreal", ""),
        role=datos.get("role", "Físico Médico"), firma=datos.get("firma", b""))
    resultado = UsuarioData().add_user(nuevo)
    if resultado is None:
        return False, MOTIVO_ERROR_BD
    return True, MOTIVO_CREADO


def cambiar_rol_sistema(username_objetivo, rol_nuevo, username_solicitante):
    """U4-bis: promueve o degrada una cuenta entre 'fisico' y 'jefe'.

    Operación de GOBIERNO, deliberadamente SEPARADA del alta (`U4`): un
    campo más en el formulario de alta habría convertido el registro
    rutinario en el sitio donde por descuido se reparten permisos.
    `rol_nuevo` acotado a `ROLES_ASIGNABLES_DESDE_UI` -- 'admin' no se
    concede JAMÁS desde aquí, ni pedido por el propio jefe.

    Reusa `_quedaria_sin_jefes` -- la MISMA guarda de `dar_de_baja` -- en
    vez de una copia propia: dos copias de "no te quedes sin nadie que
    administre" es exactamente el patrón que produjo DP-79. Solo se
    evalúa al DEGRADAR (`rol_nuevo == 'fisico'`): promover nunca reduce
    el grupo que puede administrar, así que degradar al único jefe activo
    se rechaza -- incluido degradarse a sí mismo -- pero degradar a uno
    de DOS jefes activos se permite (el otro sigue pudiendo administrar).

    Audita con los DOS valores (`rol_sistema: fisico -> jefe`) -- sin
    ambos, el rastro no permite reconstruir la historia de permisos."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        nombre_solicitante = _nombre_completo(cursor, username_solicitante)

        if not es_fisico_jefe(username_solicitante):
            _registrar_auditoria(nombre_solicitante, ACCION_ACTUALIZAR, "users",
                                  ref=username_objetivo, detalle=DENEGADO_SIN_PERMISO)
            return False

        if rol_nuevo not in ROLES_ASIGNABLES_DESDE_UI:
            _registrar_auditoria(
                nombre_solicitante, ACCION_ACTUALIZAR, "users", ref=username_objetivo,
                detalle=f"denegado: rol_nuevo '{rol_nuevo}' no permitido (solo fisico/jefe)")
            return False

        cursor.execute("SELECT rol_sistema FROM users WHERE user=?", (username_objetivo,))
        fila = cursor.fetchone()
        if fila is None:
            return False
        rol_anterior = fila[0]

        if rol_nuevo == "fisico" and _quedaria_sin_jefes(cursor, username_objetivo):
            _registrar_auditoria(
                nombre_solicitante, ACCION_ACTUALIZAR, "users", ref=username_objetivo,
                detalle="denegado: quedaría sin nadie que administre usuarios")
            return False

        cursor.execute("UPDATE users SET rol_sistema=? WHERE user=?",
                        (rol_nuevo, username_objetivo))
        db.commit()
        _registrar_auditoria(
            nombre_solicitante, ACCION_ACTUALIZAR, "users", ref=username_objetivo,
            detalle=f"rol_sistema: {rol_anterior} -> {rol_nuevo}")
        return True
