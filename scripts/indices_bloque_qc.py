"""CL1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-CL1, contrato regla 4): declara
en el esquema la clave de cada bloque del grupo C -- más las 3 hijas que ya
versionan desde M2 (`equipos_medicion`, `control_cunas`, `control_conos`) y
`dosimetriaMen` -- con un índice UNIQUE parcial. Antes la clave quedaba
implícita en cada llamador (cada función "sabía" cuál era el bloque, pero
nada en el esquema lo garantizaba).

Ensayado con éxito sobre copia real en §2.6 del plan: 21/21 índices
creados sin fallos DESPUÉS de que SA1 saneara los 41 duplicados -- un
índice UNIQUE no puede crearse si hay duplicados, así que su creación
exitosa ES la prueba de que SA1 funcionó (la verificación va incorporada
en la operación, no hace falta un paso aparte).

`preguntas` (la 22ª) queda fuera hasta que PR1 le agregue la columna
`activo`.

El predicado del índice es `WHERE (activo IS NULL OR activo = 1)` -- el
MISMO que usa `services/anulacion.py::filtro_activo` en cada lectura, no
`WHERE activo = 1` a secas. Verificado que hoy ninguna fila tiene
`activo IS NULL` en las 21 tablas (todas pasaron por
`_asegurar_activo_bloque_qc`, `DEFAULT 1`), pero declarar el índice con un
predicado más estricto que el de lectura sería la clase exacta de
divergencia silenciosa que este plan existe para cerrar: dos filas
"activas" a ojos de cualquier lectura podrían coexistir sin que el índice
lo notara.

Claves (§2.3 del plan) -- las 8 primeras coinciden con
`saneamiento_bloque_qc.py::CLAVES_NATURALES` (mismo concepto de clave
natural; dos módulos con responsabilidad distinta -- uno resuelve
duplicados, este los declara en el esquema)."""
import re
import sqlite3

CLAVES_INDICE = {
    "control_cunas": ("ref", "angulo"),
    "control_conos": ("ref", "medida"),
    "equipos_medicion": ("ref", "tipo_camara"),
    "analisis_placa_franjas": ("ref", "franja"),
    "tamano_campo": ("ref", "campo_nominal"),
    "HC_indicadores_camilla": ("ref", "id_energia", "ubicacion", "desplazamiento"),
    "HC_indicadores_colimador": ("ref", "id_energia", "nivel"),
    "HC_indicadores_laser": ("ref", "id_energia", "ubicacion"),
    "dosimetriaMen": ("ref", "energia"),
    "tabla_factor_campo": ("ref", "id_energia", "tamano_campo"),
    "tabla_factores_transmision": ("ref", "id_energia", "angulo"),
    "tabla_control_camaras_monitoras": ("ref", "id_energia", "indicador_medir"),
    "tabla_factores_sobre_eje": ("ref", "id_energia", "tam_pdd", "profundidad"),
    "HC_indicadores_brazo": ("ref", "id_energia", "nivel"),
    "HC_desplazamiento_isocentro_mensual": ("ref", "id_energia", "ubicacion"),
    "HC_tamanos_campo_radiacion": ("ref", "id_energia", "indicado_inplane"),
    "HC_dosimetria_anual": ("ref", "id_energia"),
    "HC_imagen_perfil_mlc_anual": ("ref", "id_energia"),
    "HC_linealidad_unidades_monitor_anual": ("ref", "id_energia", "UM"),
    "HC_velocidad_multilaminas_anual": ("ref", "id_energia", "banco"),
    "HC_precision_posicion_multilaminas_anual": ("ref", "id_energia", "medida"),
    "preguntas": ("ref",),

    # IV3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV3): claves de las 30 tablas
    # nuevas del bloque de QC (§2.8 del plan), ensayadas contra los datos
    # reales del rebuild 19-08. Las 4 tablas diarias (clave DATE(date), una
    # EXPRESIÓN, no una columna) NO van aquí -- crear_indices() todavía no
    # sabe validar claves por expresión; eso y su ampliación van juntos en
    # MI3 (Fase 4), no aquí (IV3 solo "declara").
    #
    # EB6 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB6, hallazgo G3 del 24-08):
    # TipoCalibracion es una de las 7 raíces de QC y hasta aquí no tenía
    # NINGÚN índice -- daba igual mientras `guardar_resultado_CambioFuente`
    # la mutaba en sitio (UPDATE ... WHERE id=?), pero EB2b la convierte a
    # anular+insertar, y sin índice nada impediría dos generaciones
    # vigentes de la misma calibración. Clave = el propio WHERE con el que
    # ese guardado ya la busca (load.py:880-884): "la misma calibración" es
    # la del mismo día y tipo. Ensayada contra las 3 BD de referencia
    # (24-08): 13-14 filas cada una, CERO grupos con más de una fila por
    # (DATE(fecha), tipo) -- el índice se crea sin saneamiento previo.
    "TipoCalibracion": ("DATE(fecha)", "tipo"),
    # LinealidadBraquiterapia (la otra raíz sin índice, G3) queda FUERA
    # deliberadamente: medida contra las 3 BD de referencia (24-08) --
    # solo 3 filas en total, cero duplicados en (user, DATE(fecha)), pero
    # la muestra es demasiado chica para afirmar que nunca habrá más de
    # una legítima el mismo día. Más importante: HOY no existe ningún
    # mecanismo de reemplazo para esta tabla (braquiterapia.py:2669 es un
    # INSERT liso, sin DELETE ni UPDATE que EB2 deba convertir) -- forzar
    # un UNIQUE sin un reemplazo real detrás no protege nada observable y
    # sí podría bloquear en silencio un guardado futuro legítimo. Se
    # declara aquí como deuda, no como tarea de esta fase.
    #
    # Rama braquiterapia:
    "CondicionesMedicion": ("ref",),
    "SistemaMedicion": ("ref",),
    "ResultadosActividad": ("ref",),
    "MaximosCamaras": ("ref", "posicion"),
    "LecturasMaximos": ("ref", "voltaje"),
    # Rama placa (el hallazgo que originó el plan del 19-08):
    "analisis_placa_verificaciones": ("ref", "tipo"),
    "analisis_placa_correcciones": ("ref", "vertice"),
    # Mecánica mensual:
    "indicadores_brazo": ("ref", "nivel"),
    "indicadores_angulares_colimador": ("ref", "nivel"),
    # Rama TAC/Catphan (pruebas es la raíz de esta rama, ref = id_sesion+id_tipo):
    "pruebas": ("id_sesion", "id_tipo"),
    "espesor_corte": ("id_prueba",),
    "linealidad_ct": ("id_prueba",),
    "resolucion_contraste": ("id_prueba",),
    "resolucion_espacial": ("id_prueba",),
    "tamaño_pixel": ("id_prueba",),
    "uniformidad_global": ("id_prueba",),
    "resolucion_contraste_rois": ("id_prueba", "diametro_mm"),
    "resolucion_espacial_regiones": ("id_prueba", "region_nombre"),
    "uniformidad_ruido": ("id_prueba", "id_region"),
    "valores_ct": ("id_prueba", "id_material"),
    # Vacías hoy, con CREATE TABLE real (DA-42) -- se declaran para que la
    # ampliación futura de TABLAS_ANULABLES (MI1) no tenga huecos:
    "HC_fantomas": ("ref", "id_energia"),
    "configuracion_picketfence": ("ref",),
    "error_picket": ("ref", "picket"),
    "leaf_error": ("ref", "leaf"),
    "highest_leaf_errors": ("ref", "leaf_out"),
    "configuracion_starshot": ("ref",),
    "estadisticas_starshot": ("ref",),
    "angulo_starshot": ("ref", "spoke_index"),
    "uniformidad_angular_starshot": ("ref", "gap_index"),
    # angulos_entre_lineas_starshot gana la columna ordinal par_index en MI1
    # (DA-45) -- su clave anterior (una medida y una constante derivada) no
    # discriminaba filas.
    "angulos_entre_lineas_starshot": ("ref", "par_index"),

    # MI3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI3): las 4 diarias. Su clave
    # es una EXPRESIÓN (`DATE(date)`, normaliza la columna `date` TEXT antes
    # de comparar), no una columna -- por eso IV3 las dejó fuera y quedaron
    # para aquí. `crear_indices()` reconoce la forma `FUNC(columna)` con
    # `_columna_referenciada()`: valida la columna real que hay dentro, y
    # NO la entrecomilla como identificador al construir el índice (SQLite
    # soporta índices sobre expresiones desde 3.9.0).
    "aceleradorlineal_600": ("DATE(date)",),
    "aceleradorlineal_ix": ("DATE(date)",),
    "halcyon": ("DATE(date)",),
    "braqui": ("DATE(date)",),
}

_RE_EXPRESION_CLAVE = re.compile(r'^(\w+)\((\w+)\)$')


def _columna_referenciada(elemento_clave):
    """Si `elemento_clave` es una expresión `FUNC(columna)` (p.ej.
    `DATE(date)`, la clave de las 4 diarias -- MI3), devuelve el nombre de
    la columna real que referencia -- lo que hay que buscar en
    `PRAGMA table_info`, no el texto de la expresión. `None` si
    `elemento_clave` ya es un nombre de columna literal (el caso común,
    las otras 52 tablas de CLAVES_INDICE)."""
    m = _RE_EXPRESION_CLAVE.match(elemento_clave)
    return m.group(2) if m else None


def _funcion_de_expresion(elemento_clave):
    """Complemento de `_columna_referenciada`: si `elemento_clave` es una
    expresión `FUNC(columna)`, devuelve el nombre de la FUNCIÓN (`"DATE"`
    en `"DATE(date)"`). `None` si es un nombre de columna literal.

    EB1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB1, DA-52) lo usa para
    construir `sql_anular_bloque` con el placeholder envuelto en la MISMA
    función que envuelve la columna (`DATE(fecha)=DATE(?)`, no
    `DATE(fecha)=?`) -- así el llamador puede pasar el valor con o sin
    componente de hora (`'2026-06-01'` o `'2026-06-01 10:00:00'`) sin
    tener que darle el formato exacto que la expresión produce."""
    m = _RE_EXPRESION_CLAVE.match(elemento_clave)
    return m.group(1) if m else None


def nombre_indice(tabla):
    return f"idx_{tabla}_bloque_activo"


def crear_indices(ruta_db):
    """Crea los índices UNIQUE parciales declarados en CLAVES_INDICE sobre
    `ruta_db`. Devuelve dict tabla -> "creado" | "ya existía" |
    "NO CREADO -- <motivo>". Idempotente (CREATE INDEX IF NOT EXISTS: una
    segunda corrida no repite ni falla). Si alguna tabla de CLAVES_INDICE
    todavía no tuviera columna `activo` (como le pasó a `preguntas` hasta
    PR1) se salta con motivo explícito -- nunca falla en silencio, dice por
    qué no se creó.

    MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1): un `CREATE UNIQUE INDEX`
    contra una tabla con duplicados activos (el caso real de
    `analisis_placa_verificaciones`/`_correcciones`/`indicadores_brazo`/
    `indicadores_angulares_colimador` antes de que `MI2` los saneé) lanza
    `sqlite3.IntegrityError` ("UNIQUE constraint failed"), NO
    `OperationalError` -- son ramas hermanas de `sqlite3.DatabaseError`, no
    una subclase de la otra. `_reportar_indices_bloque_qc`/`migrar()`
    (scripts/migrar_bd_a_estandar.py) ya esperaban ver este motivo como un
    "NO CREADO" legible (`fallos_indices` lo busca explícitamente); solo
    capturar `OperationalError` dejaba que la excepción real se propagara
    sin capturar y abortara la migración entera. Descubierto al ejecutar
    MI1 sobre una copia de BD real con los duplicados que §2.8 del plan
    documentó.

    MI3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI3): la clave de las 4 diarias
    es una expresión (`DATE(date)`), no una columna -- `_columna_referenciada()`
    la reconoce y valida la columna REAL que hay dentro (`date`), y el SQL
    del índice usa la expresión tal cual, sin entrecomillarla como
    identificador (`CREATE UNIQUE INDEX ... ON tabla (DATE(date))` es un
    índice de expresión válido en SQLite, no una columna llamada
    "DATE(date)")."""
    con = sqlite3.connect(ruta_db)
    resultado = {}
    try:
        for tabla, clave in CLAVES_INDICE.items():
            columnas_reales = {f[1] for f in con.execute(f'PRAGMA table_info("{tabla}")')}
            if not columnas_reales:
                resultado[tabla] = "NO CREADO -- la tabla no existe en esta BD"
                continue
            if "activo" not in columnas_reales:
                resultado[tabla] = "NO CREADO -- la tabla aún no tiene columna activo"
                continue
            columnas_necesarias = [_columna_referenciada(c) or c for c in clave]
            if not all(c in columnas_reales for c in columnas_necesarias):
                faltantes = [c for c in columnas_necesarias if c not in columnas_reales]
                resultado[tabla] = f"NO CREADO -- faltan columnas de la clave: {faltantes}"
                continue

            nombre = nombre_indice(tabla)
            ya_existia = bool(con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                (nombre,)).fetchone())
            columnas_sql = ", ".join(
                c if _columna_referenciada(c) else f'"{c}"' for c in clave)
            try:
                con.execute(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "{nombre}" '
                    f'ON "{tabla}" ({columnas_sql}) '
                    f'WHERE (activo IS NULL OR activo = 1)')
                con.commit()
                resultado[tabla] = "ya existía" if ya_existia else "creado"
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                resultado[tabla] = f"NO CREADO -- {e}"
        return resultado
    finally:
        con.close()
