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
}


def nombre_indice(tabla):
    return f"idx_{tabla}_bloque_activo"


def crear_indices(ruta_db):
    """Crea los índices UNIQUE parciales declarados en CLAVES_INDICE sobre
    `ruta_db`. Devuelve dict tabla -> "creado" | "ya existía" |
    "NO CREADO -- <motivo>". Idempotente (CREATE INDEX IF NOT EXISTS: una
    segunda corrida no repite ni falla). `preguntas` se salta con motivo
    explícito hasta que tenga columna `activo` (PR1) -- nunca falla en
    silencio, dice por qué no se creó."""
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
            if not all(c in columnas_reales for c in clave):
                faltantes = [c for c in clave if c not in columnas_reales]
                resultado[tabla] = f"NO CREADO -- faltan columnas de la clave: {faltantes}"
                continue

            nombre = nombre_indice(tabla)
            ya_existia = bool(con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                (nombre,)).fetchone())
            columnas_sql = ", ".join(f'"{c}"' for c in clave)
            try:
                con.execute(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "{nombre}" '
                    f'ON "{tabla}" ({columnas_sql}) '
                    f'WHERE (activo IS NULL OR activo = 1)')
                con.commit()
                resultado[tabla] = "ya existía" if ya_existia else "creado"
            except sqlite3.OperationalError as e:
                resultado[tabla] = f"NO CREADO -- {e}"
        return resultado
    finally:
        con.close()
