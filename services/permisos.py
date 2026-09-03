"""Permisos administrativos por rol de sistema (E6,
PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §10; antes C3,
PLAN_AUDITORIA_DOS_EJES_21-07.md §7.3/§7.7a).

El rol de PERMISOS vive en `users.rol_sistema` ('admin' / 'jefe' /
'fisico'), poblado por la migración idempotente del arranque
(`Conexion._asegurar_roles_de_sistema`). Es una columna aparte de
`users.role` a propósito: `role` es el CARGO MOSTRADO ('Físico Médico') que
imprimen los reportes PDF clínicos en el bloque de firma y que compara la
recuperación de contraseña -- reescribirlo habría cambiado los PDF y roto
la recuperación.

`es_admin_equivalente()` conserva nombre y firma desde C3: sus llamadores
(DialogAdminPermisoEliminar y quien se sume) no cambian. Si el rol no se
puede resolver (BD sin migrar, fallo transitorio de conexión), se cae al
conjunto codificado histórico {"admin", "lamaya"} CON aviso por consola --
denegar dejaría a la física en jefe sin permisos en un turno clínico por un
fallo pasajero, que es peor. Nunca se concede un permiso que un rol
resuelto no dé: el fallback solo aplica cuando NO hay rol legible.

DA-35 (2026-08-06, PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.1,
decisión TEMPORAL del físico -- "por ahora asignar a todos el mismo nivel de
permiso que administrador"): "fisico" se agregó a ROLES_ADMIN_EQUIVALENTE.
Para revertir: quitar "fisico" de ese conjunto; no hay ningún otro punto que
tocar. El respaldo legado USUARIOS_ADMIN_EQUIVALENTE NO cambia -- sigue
aplicando solo cuando el rol no es resoluble.
"""

import sqlite3

from data.ManejoDatos import conection as _conection

ROLES_VALIDOS = {"admin", "jefe", "fisico"}
# DA-35: temporal, ver docstring del módulo.
ROLES_ADMIN_EQUIVALENTE = {"admin", "jefe", "fisico"}

# Fallback legado (C3): solo se consulta cuando el rol no se puede resolver.
USUARIOS_ADMIN_EQUIVALENTE = {"admin", "lamaya"}


def rol_de(username):
    """Rol de sistema de `username` ('admin'/'jefe'/'fisico'), o None si no
    se puede resolver (usuario inexistente, BD sin migrar, error de BD)."""
    if not username:
        return None
    try:
        con = sqlite3.connect(_conection.ruta_base_datos())
        try:
            fila = con.execute(
                "SELECT rol_sistema FROM users WHERE lower(user) = ?",
                (str(username).strip().lower(),)).fetchone()
        finally:
            con.close()
    except Exception as ex:
        print(f"[permisos] no se pudo leer el rol de '{username}': {ex}")
        return None
    if fila is None:
        return None
    rol = fila[0]
    return rol if rol in ROLES_VALIDOS else None


def es_admin_equivalente(username):
    """True si `username` tiene permisos administrativos plenos."""
    if not username:
        return False
    rol = rol_de(username)
    if rol is not None:
        return rol in ROLES_ADMIN_EQUIVALENTE
    limpio = str(username).strip().lower()
    if limpio in USUARIOS_ADMIN_EQUIVALENTE:
        print(f"[permisos] rol de '{username}' no resoluble; se usa la "
              "equivalencia codificada legada (BD sin migrar o fallo de BD)")
        return True
    return False


# U1 (PLAN_PESTANA_USUARIOS_02-09.md): quién administra USUARIOS (alta/baja),
# deliberadamente distinto de quién es admin-equivalente para el resto de la
# app. "fisico" NO entra aquí -- DA-35 lo agregó a ROLES_ADMIN_EQUIVALENTE de
# forma TEMPORAL, y la gestión de usuarios no debe heredar esa apertura.
ROLES_GESTION_USUARIOS = {"admin", "jefe"}


def es_fisico_jefe(username):
    """True si `username` puede dar de alta y de baja usuarios.

    Deliberadamente SEPARADO de es_admin_equivalente(): DA-35 metió
    "fisico" en ROLES_ADMIN_EQUIVALENTE de forma temporal, y la gestión
    de usuarios no debe heredar esa apertura. Aquí NO hay fallback
    legado: si el rol no se puede resolver se DENIEGA. Es lo contrario
    del criterio de es_admin_equivalente(), y a propósito -- allí
    denegar dejaba a la física en jefe sin permisos en un turno clínico
    (peor que conceder de más); aquí conceder de más significa que
    cualquiera pueda crear cuentas, y no hay ninguna urgencia clínica en
    dar de alta a un usuario.
    """
    if not username:
        return False
    rol = rol_de(username)
    return rol in ROLES_GESTION_USUARIOS
