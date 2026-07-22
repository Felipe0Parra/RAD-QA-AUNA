"""Equivalencia de permisos administrativos (C3, PLAN_AUDITORIA_DOS_EJES_21-07.md
§7.3/§7.7a).

El físico en jefe (Luz Adriana Maya, usuario "lamaya") debe poder ejercer las
mismas decisiones administrativas que la cuenta "admin". Hoy `users.role` no
distingue jefe de físico raso -- es NULL para admin y 'Físico Médico' para
los 6 físicos por igual, incluida lamaya --, así que la equivalencia se
resuelve por nombre de usuario hasta que exista un modelo de roles real.
"""

USUARIOS_ADMIN_EQUIVALENTE = {"admin", "lamaya"}


def es_admin_equivalente(username):
    """True si `username` tiene permisos administrativos plenos."""
    if not username:
        return False
    return username.strip().lower() in USUARIOS_ADMIN_EQUIVALENTE
