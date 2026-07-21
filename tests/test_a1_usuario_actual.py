"""A1 (PLAN_AUDITORIA_DOS_EJES_21-07): helper único para resolver el usuario
actual en los puntos de guardado.

Antes de esta tarea, `getattr(getattr(self, "user_id", None), "_nombre",
None)` estaba copiado igual en 5 sitios (load.py:subirlineasmensuales,
equipos.py x2, ix_mensual.py, seiscientos_mensual.py) -- riesgo de que un
call-site nuevo lo resuelva distinto y termine con `usuario=NULL` en
`audit_log`. `usuario_actual()` centraliza ese patrón; los 5 call-sites
ahora lo llaman en vez de repetir el getattr anidado.
"""
from services.audit_minimo import usuario_actual


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _ConUsuario:
    user_id = _UsuarioFalso()


class _SinUserId:
    pass


class _UserIdNone:
    user_id = None


class _UserIdSinNombre:
    class user_id:
        pass


def test_devuelve_el_nombre_cuando_existe():
    assert usuario_actual(_ConUsuario()) == "Físico de Prueba"


def test_sin_atributo_user_id_devuelve_none():
    assert usuario_actual(_SinUserId()) is None


def test_user_id_none_devuelve_none():
    assert usuario_actual(_UserIdNone()) is None


def test_user_id_sin_nombre_devuelve_none():
    assert usuario_actual(_UserIdSinNombre()) is None
