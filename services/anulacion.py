"""E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11): punto único de anulación
para el bloque de control de calidad.

Antes de esto, la app **no tenía una jerarquía, tenía cuatro raíces
independientes** (`controles`, `TipoCalibracion`, `LinealidadBraquiterapia`,
las 4 diarias) y solo `controles` tenía soft-delete (C2, `activo`). Cada
tabla hija se borraba físicamente por su propia ruta: `eliminarRegistro`
(load.py, mensual/anual), `eliminarfilas` (tablas.py, diarias) y los dos
botones de braquiterapia que apuntan a `TipoCalibracion`
(braq_mensual.py/braquiterapia.py). El peligro más grave: anular
`TipoCalibracion` arrastraba en cascada `ResultadosActividad` (la actividad
calculada de la fuente de braquiterapia) sin dejar nada recuperable.

`TABLAS_ANULABLES` es la lista blanca cerrada del inventario del plan
(§11.3): toda tabla del bloque de QC con una ruta de borrado alcanzable
desde la interfaz. Deliberadamente NO son las ~45 tablas del bloque
completo -- las demás no tienen forma de perder filas individualmente
(desaparecen de la vista cuando su raíz se anula) y añadirles `activo`
solo triplicaría el riesgo sin ganar nada (§11.5). Si una tabla nueva gana
un botón de borrado, entra a esta lista en ese momento -- el tripwire de
`tests/test_e7_soft_delete_bloque_qc.py` obliga a ello.

`anular_fila()` RECHAZA cualquier tabla fuera de la lista: nunca se anula
por error algo ajeno al bloque de QC (p.ej. un catálogo con DELETE físico
legítimo, ya auditado desde A2).
"""

from PyQt5.QtSql import QSqlQuery

from services.audit_minimo import ACCION_ANULAR
from services.audit_minimo import registrar as _registrar_auditoria

TABLAS_ANULABLES = frozenset({
    # Raíces (controles ya tenía `activo` desde C2; las demás lo ganan en E7)
    "controles",
    "TipoCalibracion",
    "LinealidadBraquiterapia",
    "aceleradorlineal_600",
    "aceleradorlineal_ix",
    "halcyon",
    "braqui",
    # Hijas mensuales con botón de borrado (_mostrar_dialogo, load.py)
    "equipos_medicion",
    "control_cunas",
    "tamano_campo",
    "analisis_placa_franjas",
    # Hijas anuales con botón de borrado (crear_ventanas_emergentes_tablas,
    # data/ManejoDatos/Tablas_Anuales/tablas_anuales.py)
    "tabla_factor_campo",
    "tabla_factores_transmision",
    "tabla_factores_sobre_eje",
    "tabla_control_camaras_monitoras",
    "HC_indicadores_brazo",
    "HC_indicadores_colimador",
    "HC_indicadores_laser",
    "HC_indicadores_camilla",
    "HC_desplazamiento_isocentro_mensual",
    "HC_velocidad_multilaminas_anual",
    "HC_precision_posicion_multilaminas_anual",
    "HC_imagen_perfil_mlc_anual",
    "HC_dosimetria_anual",
    "HC_linealidad_unidades_monitor_anual",
    "HC_tamanos_campo_radiacion",
    # D5: la calculadora/dosimetría más sensible NUNCA lleva delete físico.
    # dosimetriaMen no tiene ruta de borrado alcanzable todavía (el botón de
    # su diálogo -- E5 -- sigue sin conectar) pero ya nace preparada para
    # anular en vez de borrar en cuanto se conecte.
    "dosimetriaMen",
})


def anular_fila(db, tabla, id_valor, usuario, detalle="", id_where=None,
                valor_where=None, ref=None):
    """`UPDATE {tabla} SET activo = 0 WHERE ...`, auditado con
    `ACCION_ANULAR`. Nunca borra: todas las tablas del bloque de QC
    conservan su historial completo (D6).

    Por defecto la fila se localiza por `"id" = ?` (con `id_valor`) --
    válido para la mayoría del inventario. Dos tablas (`dosimetriaMen`,
    `tamano_campo`) no tienen columna "id": su identidad real es una clave
    compuesta (mismo criterio que ya usa `guardarEdicion`) -- el llamador
    pasa `id_where`/`valor_where` explícitos para esos casos (E5).

    `db` es una conexión `QSqlDatabase` ya abierta (mismo patrón que los
    llamadores `eliminarRegistro`/`eliminarfilas`, que reusan su propia
    conexión/transacción). Lanza `ValueError` si `tabla` no está en la lista
    blanca -- ver el docstring del módulo.
    """
    if tabla not in TABLAS_ANULABLES:
        raise ValueError(
            f"'{tabla}' no está en la lista blanca de anulación "
            "(services/anulacion.py::TABLAS_ANULABLES) -- fuera del bloque "
            "de control de calidad, no se anula por este camino.")
    if id_where is None:
        id_where = '"id" = ?'
        valor_where = [id_valor]
    query = QSqlQuery(db)
    query.prepare(f'UPDATE "{tabla}" SET activo = 0 WHERE {id_where}')
    for v in valor_where:
        query.addBindValue(v)
    if not query.exec_():
        raise Exception(query.lastError().text())
    _registrar_auditoria(usuario, ACCION_ANULAR, tabla,
                         ref=ref if ref is not None else str(id_valor), detalle=detalle)
