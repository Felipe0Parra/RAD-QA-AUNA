"""A5 (PLAN_AUDITORIA_DOS_EJES_21-07): vocabulario cerrado de acciones.

Antes de esta tarea cada call-site de `registrar()` escribía su propio
string suelto ("guardar", "eliminar"...) -- un typo nuevo (p.ej. "elimnar")
habría quedado invisible en `audit_log`, sin que nada lo detectara ni en
tests ni en el visor. Las constantes deben mantener el valor EXACTO que ya
usan las filas históricas de producción (`audit_log` ya tiene filas reales
con "guardar"/"reemplazo"/"actualizar") -- cambiar el valor rompería la
continuidad del historial, no solo el código nuevo.
"""
from services.audit_minimo import (
    ACCION_ACTUALIZAR,
    ACCION_EDITAR,
    ACCION_ELIMINAR,
    ACCION_GUARDAR,
    ACCION_LOGIN,
    ACCION_LOGOUT,
    ACCION_REEMPLAZO,
)


def test_valores_identicos_a_los_strings_historicos_de_produccion():
    assert ACCION_GUARDAR == "guardar"
    assert ACCION_REEMPLAZO == "reemplazo"
    assert ACCION_ACTUALIZAR == "actualizar"
    assert ACCION_EDITAR == "editar"
    assert ACCION_ELIMINAR == "eliminar"
    assert ACCION_LOGIN == "login"
    assert ACCION_LOGOUT == "logout"


def test_todas_distintas_entre_si():
    valores = [ACCION_GUARDAR, ACCION_REEMPLAZO, ACCION_ACTUALIZAR, ACCION_EDITAR,
               ACCION_ELIMINAR, ACCION_LOGIN, ACCION_LOGOUT]
    assert len(valores) == len(set(valores))
