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

`TABLAS_ANULABLES` nació (E7, §11.3) como la lista blanca de "toda tabla
del bloque de QC con una ruta de borrado alcanzable desde la interfaz" --
deliberadamente NO las ~45 del bloque completo. Ese criterio quedó
OBSOLETO: `PLAN_CONTRATO_GUARDADO_13-08.md` cambió el propósito real a
"¿qué tabla participa en el reemplazo de bloque?", y la lista se parchó a
mano dos veces (`control_conos`, `dosimetriaMen`) sin recalcularse contra
el propósito nuevo -- hasta que `analisis_placa_verificaciones`/
`_correcciones` se quedaron fuera sin que nadie lo notara (el hallazgo que
originó `PLAN_CONTRATO_COMPLETO_19-08.md`).

MI1 (§6-MI1 de ese plan, DA-40) cierra el defecto de raíz: el frozenset
pasó de 29 a **59** entradas -- las 30 tablas del cierre transitivo por
clave foránea desde las 7 raíces de QC que hasta entonces vivían en
`EXCEPCIONES_INVENTARIO` con motivo `"PENDIENTE-LF"` (esperaban a que sus
lecturas filtraran, Fase 3 del plan). Solo quedan dos excepciones
declaradas (`EXCEPCIONES_INVENTARIO`, más abajo): `equipos_anual` (se
retira del esquema, MI5) y `posicionamiento_reposicionamiento` (huérfana,
bloqueada en DP-38). Si una tabla nueva entra al cierre transitivo, el
tripwire de IV2 (`tests/test_iv2_completitud_inventario.py`) exige que se
clasifique en uno de los dos sitios -- no puede volver a colarse fuera de
los dos sin que algo se ponga rojo.

`anular_fila()` RECHAZA cualquier tabla fuera de la lista: nunca se anula
por error algo ajeno al bloque de QC (p.ej. un catálogo con DELETE físico
legítimo, ya auditado desde A2).

EB1 (§6-EB1 del mismo plan, DA-52) añade el punto único de REEMPLAZO de
bloque para la pila `sqlite3` (`reemplazar_bloque`, apoyado en
`sql_anular_bloque`) -- lo que hasta la Fase 5 hacían a mano, con `DELETE`
físico, los sitios de braquiterapia/TAC/MLC/diarias/placa. `EB1` no
commitea: participa en la transacción que abre el llamador.
"""

from PyQt5.QtSql import QSqlQuery

from scripts.indices_bloque_qc import _columna_referenciada, _funcion_de_expresion
from services.audit_minimo import ACCION_ANULAR, ACCION_REEMPLAZO
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
    # M1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md): control_conos no tiene
    # una ruta de borrado alcanzable desde la interfaz (a diferencia de
    # control_cunas, cuyo `activo` viene de ese criterio de E7) -- entra aquí
    # por una razón distinta: M2 convierte el guardado mensual en un
    # reemplazo de bloque (anular lo activo de ese `ref` e insertar el
    # nuevo), y eso exige que las dos mitades del mismo control -- cuñas y
    # conos -- puedan distinguir el bloque vigente del anterior de la misma
    # forma.
    "control_conos",
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
    # PR1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-PR1): mismo criterio que
    # dosimetriaMen -- preguntas tampoco tiene ruta de borrado alcanzable
    # desde la interfaz todavía, pero entra a la lista para que
    # `_asegurar_activo_bloque_qc` le agregue `activo` y su guardado
    # (subirlineasmensuales, mismo camino que dosimetriaMen desde DO1)
    # empiece a anular en vez de pisar el bloque anterior.
    "preguntas",

    # MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1, DA-40): las 30 tablas del
    # cierre transitivo por FK que hasta aquí esperaban en
    # `EXCEPCIONES_INVENTARIO` con motivo "PENDIENTE-LF" -- entran una vez
    # LF (Fase 3) ya filtra sus lecturas (74 sitios, LF1-LF5) y AN1/RT1
    # cubren el bloque completo (LR4). `_asegurar_activo_bloque_qc` les
    # agrega `activo INTEGER DEFAULT 1` sola en el siguiente arranque --
    # migración de coste cero, ninguna fila se reescribe.
    #
    # Rama braquiterapia:
    "CondicionesMedicion",
    "SistemaMedicion",
    "MaximosCamaras",
    "LecturasMaximos",
    "ResultadosActividad",
    # Rama placa (el hallazgo que originó el plan del 19-08):
    "analisis_placa_verificaciones",
    "analisis_placa_correcciones",
    # Mecánica mensual:
    "indicadores_brazo",
    "indicadores_angulares_colimador",
    # Rama TAC/Catphan (pruebas es la raíz de esta rama):
    "pruebas",
    "espesor_corte",
    "linealidad_ct",
    "resolucion_contraste",
    "resolucion_contraste_rois",
    "resolucion_espacial",
    "resolucion_espacial_regiones",
    "tamaño_pixel",
    "uniformidad_global",
    "uniformidad_ruido",
    "valores_ct",
    # Vacías hoy, con CREATE TABLE real (DA-42) -- MLC (picketfence/starshot)
    # y HC_fantomas:
    "HC_fantomas",
    "configuracion_picketfence",
    "error_picket",
    "leaf_error",
    "highest_leaf_errors",
    "configuracion_starshot",
    "estadisticas_starshot",
    "angulo_starshot",
    # angulos_entre_lineas_starshot gana la columna ordinal `par_index` en
    # este mismo MI1 (DA-45, §4.3 del plan): su clave anterior (una medida
    # y una constante derivada) no discriminaba filas -- ver
    # `_asegurar_migraciones_ad_hoc` (data/ManejoDatos/conection.py).
    "angulos_entre_lineas_starshot",
    "uniformidad_angular_starshot",
})


# IV1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV1, DA-40): clasificación explícita
# de toda tabla del cierre transitivo por FK desde las 7 raíces de QC que HOY
# no está en `TABLAS_ANULABLES`. IV2 (tests/test_iv2_completitud_inventario.py)
# exige que `cierre_transitivo == TABLAS_ANULABLES ∪ EXCEPCIONES_INVENTARIO`
# -- una tabla nueva sin clasificar en ninguno de los dos pone ese test en
# rojo. Es la garantía que compra DA-40: `analisis_placa_verificaciones` y
# `analisis_placa_correcciones` (el hallazgo que originó el plan del 19-08)
# no pueden volver a quedarse fuera sin que algo se note.
#
# Dos motivos posibles, cada tabla lleva el suyo -- un tercero
# ("PENDIENTE-LF: ...") existió entre LF (Fase 3) y MI1 (Fase 4, éste
# archivo): las 30 tablas que esperaban a que sus lecturas filtraran antes
# de entrar al frozenset. MI1 las movió todas -- ver el bloque de
# `TABLAS_ANULABLES` arriba. Solo quedan las dos que NUNCA van a versionar:
#   - "se retira, DA-44" -- la tabla se elimina del esquema (MI5), no se
#     versiona porque no vale la pena versionar algo que va a desaparecer.
#   - "huérfana, DP-38" -- existe en las BD reales pero ningún código de
#     producción la crea, lee ni escribe; decisión pendiente del físico.
EXCEPCIONES_INVENTARIO = {
    "equipos_anual": "se retira, DA-44 -- 0 filas en las 3 BD de referencia, ninguna consulta SQL la nombra en el código vivo, se elimina del esquema en MI5",
    "posicionamiento_reposicionamiento": "huérfana, DP-38 -- existe en las BD reales (FK a controles) pero NINGÚN código de producción la crea, lee ni escribe; ni siquiera tiene CREATE TABLE en conection.py (a diferencia de las otras 11 tablas vacías). Bloqueada hasta que el físico decida si se retira o se implementa la funcionalidad que la usaría",
}


def filtro_activo(tabla):
    """LE0 (PLAN_CONTRATO_GUARDADO_13-08.md §6-LE0): punto único del
    fragmento SQL que distingue una fila vigente de una superada. Antes
    existían DOS copias independientes del mismo concepto
    (`tablas_anuales.py::_FILTRO_ACTIVO`, `load.py:2824`) -- que es
    precisamente por qué el filtro se aplicó de forma desigual por el
    proyecto (§2.5 del plan). Cualquier lectura nueva sobre una tabla del
    bloque de QC debe filtrar por esto (contrato, regla 5).

    Devuelve `" AND (activo IS NULL OR activo = 1)"` si `tabla` está en la
    lista blanca de anulación; cadena vacía si no -- así un `WHERE` que lo
    use nunca queda con un `AND` colgando cuando la tabla no versiona.
    """
    return " AND (activo IS NULL OR activo = 1)" if tabla in TABLAS_ANULABLES else ""


# EB1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB1, DA-52): esqueleto de texto
# compartido por `anular_fila` (identidad física, pila QtSql) y
# `sql_anular_bloque` (clave de bloque + vigencia, pila sqlite3) -- un solo
# origen para "así se escribe SET activo = 0 sobre esta tabla".
_SQL_ANULAR = 'UPDATE "{tabla}" SET activo = 0 WHERE {where}'


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

    Nótese que aquí `id_where` identifica UNA fila física -- no lleva el
    `AND (activo IS NULL OR activo = 1)` que sí lleva `sql_anular_bloque`
    (EB1): anular por identidad ya selecciona una sola fila, filtrarla
    además por vigencia solo la convertiría en no-op silencioso si esa fila
    ya estuviera anulada.
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
    query.prepare(_SQL_ANULAR.format(tabla=tabla, where=id_where))
    for v in valor_where:
        query.addBindValue(v)
    if not query.exec_():
        raise Exception(query.lastError().text())
    _registrar_auditoria(usuario, ACCION_ANULAR, tabla,
                         ref=ref if ref is not None else str(id_valor), detalle=detalle)


def sql_anular_bloque(tabla, columnas_clave):
    """EB1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB1, DA-52): punto único del
    texto SQL "anular el bloque vigente que matchea esta clave" -- mismo
    papel que `filtro_activo()` cumple del lado de lectura (LE0). Ni PyQt
    ni sqlite3: solo compone texto, con placeholders posicionales en el
    mismo orden que `columnas_clave`.

    `columnas_clave` acepta tanto nombres de columna simples como
    expresiones tipo "DATE(fecha)" (mismo formato que `CLAVES_INDICE`/
    `CLAVES_NATURALES`) -- usa `_columna_referenciada` para decidir si el
    elemento se cita como identificador o se deja tal cual (una expresión
    ya es SQL válido, citarla la rompería). Para una expresión, el
    placeholder se envuelve en la MISMA función (`DATE(fecha)=DATE(?)`, no
    `DATE(fecha)=?`) -- así el llamador puede pasar el valor con o sin la
    parte de hora (`'2026-06-01'` o `'2026-06-01 10:00:00'`) sin tener que
    conocer el formato exacto que produce la expresión del lado izquierdo.

    Lanza `ValueError` si `tabla` no está en la lista blanca -- mismo
    criterio que `anular_fila`.
    """
    if tabla not in TABLAS_ANULABLES:
        raise ValueError(
            f"'{tabla}' no está en la lista blanca de anulación "
            "(services/anulacion.py::TABLAS_ANULABLES) -- fuera del bloque "
            "de control de calidad, no se reemplaza por este camino.")

    def _condicion(c):
        funcion = _funcion_de_expresion(c)
        if funcion:
            return f"{c}={funcion}(?)"
        if _columna_referenciada(c):
            return f"{c}=?"
        return f'"{c}"=?'

    condiciones = " AND ".join(_condicion(c) for c in columnas_clave)
    where = f"{condiciones} AND (activo IS NULL OR activo = 1)"
    return _SQL_ANULAR.format(tabla=tabla, where=where)


def reemplazar_bloque(cursor, tabla, clave, sql_insert, filas, usuario,
                       ref=None, detalle="", accion=None, auditar=True):
    """EB1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB1, DA-52): punto único de
    reemplazo de bloque para la pila `sqlite3` (EB2/EB4/EB6) -- sustituye
    a los `DELETE FROM ...; INSERT INTO ...` de las ramas de guardado del
    bloque de QC. El bloque anterior se ANULA (activo=0), nunca se borra.

    Args:
        cursor: cursor `sqlite3` de una conexión con transacción abierta
            (`Conexion().conectar()` + `BEGIN`). NO hace commit: lo decide
            el llamador -- un guardado lógico puede tocar varias tablas
            (`guardar_resultado_CambioFuente` toca 6, `guardar_prueba_
            completa_catphan` hasta 11); un commit por tabla partiría el
            bloque a mitad si algo falla a mitad de camino (G2, hallazgo
            de la auditoría del 24-08).
        tabla: debe estar en `TABLAS_ANULABLES` -- `ValueError` si no.
        clave: lista de tuplas `(columna_o_expresion, valor)` que
            identifican el bloque vigente a anular -- mismo formato de
            columna que `CLAVES_INDICE`/`CLAVES_NATURALES` (acepta
            expresiones como `"DATE(date)"`).
        sql_insert: sentencia INSERT completa, con columnas explícitas
            (MI0) -- se ejecuta con un `execute()` por fila (ver más abajo).
        filas: lista de tuplas de parámetros para el INSERT. Si está
            **vacía**, NO se anula el bloque vigente (invariante 4 del
            contrato, T3): sin bloque nuevo válido que insertar, el
            anterior se conserva intacto en vez de desaparecer.
        usuario, detalle: se pasan a `registrar()` (EB0, `con=
            cursor.connection`) -- la fila de auditoría se escribe en la
            MISMA transacción que el reemplazo, nunca en una conexión
            aparte (ver `services/audit_minimo.py::registrar`, DA-52).
        ref: identificador para la auditoría. Si es `None` (el caso común
            para una RAÍZ con autoincrement, p.ej. `TipoCalibracion`), se
            usa `cursor.lastrowid` -- el id de la fila recién insertada.
            Pásalo explícito cuando la identidad natural NO es ese id
            (p.ej. las diarias, cuyo `ref` legible es la fecha).
        accion: verbo de `services/audit_minimo.py` (por defecto
            `ACCION_REEMPLAZO`). Algunos llamadores prefieren conservar su
            propio verbo histórico -- p.ej. `guardar_resultado_
            CambioFuente` sigue auditando como `ACCION_GUARDAR`
            ("cambio de fuente"), no como un "reemplazo" genérico, para no
            romper el vocabulario que ya leen sus propios reportes/tests.
        auditar: `False` cuando esta llamada es solo UNA pieza de una
            acción real más grande que otro punto del código ya audita una
            vez por todas sus piezas (A6.3: "una acción, una fila", el
            mismo criterio que ya usan `guardar_analisis_e_imagen` o
            `guardar_prueba_completa_catphan`). P.ej. `guardar_analisis_
            placa600` (EB2a) llama a `reemplazar_bloque` tres veces
            (franjas/verificaciones/correcciones) para UN solo clic --
            auditar las tres sería 3 filas por 1 acción.

    Rechaza cualquier tabla fuera de la lista blanca, igual que
    `anular_fila`.
    """
    if tabla not in TABLAS_ANULABLES:
        raise ValueError(
            f"'{tabla}' no está en la lista blanca de anulación "
            "(services/anulacion.py::TABLAS_ANULABLES) -- fuera del bloque "
            "de control de calidad, no se reemplaza por este camino.")
    if not filas:
        return
    columnas_clave = [c for c, _ in clave]
    valores_clave = [v for _, v in clave]
    cursor.execute(sql_anular_bloque(tabla, columnas_clave), valores_clave)
    # NO `cursor.executemany(...)`: el módulo `sqlite3` de la librería
    # estándar NO actualiza `cursor.lastrowid` tras un `executemany` (queda
    # en `None` incluso con una sola fila -- verificado empíricamente,
    # 24-08) mientras que un `execute()` normal sí. Varios llamadores
    # (p.ej. `guardar_resultado_CambioFuente`, EB2b) necesitan el
    # `lastrowid` de la fila insertada -- el nuevo `id` de la raíz se
    # vuelve el `ref` de sus tablas hijas. Un bucle de `execute()` deja
    # `cursor.lastrowid` en el id de la ÚLTIMA fila insertada, igual que un
    # `executemany` haría si funcionara, sin perder esa capacidad.
    for fila in filas:
        cursor.execute(sql_insert, fila)
    if not auditar:
        return
    ref_auditoria = ref if ref is not None else cursor.lastrowid
    _registrar_auditoria(usuario, accion or ACCION_REEMPLAZO, tabla,
                         ref=ref_auditoria, detalle=detalle,
                         con=cursor.connection)
