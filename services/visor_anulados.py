"""LR6 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR6, [[DA-49]]): capa de datos del
visor de registros anulados -- solo lectura, sin PyQt5, para poder probarse
sin levantar la interfaz.

Por qué existe: DA-49 retira la reactivación ([[DA-34]]) porque era el
parche de una lectura sin filtrar (W1) que `LR3` ya corrigió en la causa; lo
único que la reactivación seguía dando de verdad -- poder VER un registro
anulado -- lo cubre este visor sin necesitar deshacer la anulación. Es la
tercera categoría de `LR1` (censo/auditoría/visor): lee las dos ramas
(vigente e histórica) A PROPÓSITO, con la excepción declarada aquí mismo.

Alcance: `TABLAS_ANULABLES` (services/anulacion.py), derivado -- nunca una
lista a mano. Hoy son 29 tablas; crecerá solo cuando `MI1` amplíe el
frozenset, sin tocar este módulo.
"""
import sqlite3

from data.ManejoDatos.conection import Conexion
from services.anulacion import TABLAS_ANULABLES
from services.lectura_vigente import RAICES_QC, cierre_transitivo_fk


def secciones():
    """{raíz: [tablas...]} -- cada una de las 7 raíces de QC más las tablas
    de `TABLAS_ANULABLES` que descienden de ella por clave foránea (mismo
    mecanismo que `derivar_inventario_qc.py`/IV1, no una lista a mano).
    Hoy la mayoría de las 22 hijas cuelgan de `controles` -- las demás
    raíces solo tienen a sí mismas porque sus hijas siguen `PENDIENTE-LF`
    (MI1 no ha corrido) -- y eso es correcto: la agrupación se rebalancea
    sola en cuanto ese contrato avance, sin que este módulo cambie."""
    con = Conexion().conectar()
    try:
        resultado = {}
        for raiz in sorted(RAICES_QC):
            cierre = cierre_transitivo_fk(con, {raiz})
            hijas = sorted(cierre & TABLAS_ANULABLES)
            resultado[raiz] = [raiz] + hijas
        return resultado
    finally:
        con.close()


def columnas_de(tabla):
    """Nombres de columna de `tabla`, en el orden real del esquema
    (`PRAGMA table_info`) -- nunca una lista a mano por tabla."""
    if tabla not in TABLAS_ANULABLES:
        raise ValueError(
            f"'{tabla}' no está en TABLAS_ANULABLES -- fuera del alcance "
            "del visor (services/anulacion.py)")
    con = Conexion().conectar()
    try:
        info = con.execute(f'PRAGMA table_info("{tabla}")').fetchall()
        return [fila[1] for fila in info]
    finally:
        con.close()


def filas_de(tabla, busqueda=""):
    """Todas las filas de `tabla` -- vigentes E HISTÓRICAS, a propósito
    (LR1, categoría CENSO/VISOR: esta es la excepción declarada). Cada
    fila trae su `_rowid` (el `rowid` real de SQLite, universal exista o
    no una columna `id` declarada -- 5 de las 29 tablas del alcance no la
    tienen, ver `auditoria_de`) y su estado derivado de `activo`
    (`None`/`1` = vigente; cualquier otro valor = anulado -- mismo
    criterio que `filtro_activo`). `busqueda` filtra por substring
    case-insensitive sobre cualquier columna, aplicado en Python porque el
    conjunto de columnas varía por tabla.

    Devuelve (columnas, filas) -- `columnas` SIN `activo` (es metadato de
    anulación, ya representado por `estado`; mismo criterio de exclusión
    que `data/ManejoDatos/load.py::encontrar_columnas`, no un dato del
    registro). `filas`: lista de {'rowid', 'valores', 'estado'}."""
    columnas_reales = columnas_de(tabla)
    con = Conexion().conectar()
    try:
        cols_sql = ", ".join(f'"{c}"' for c in columnas_reales)
        filas_crudas = con.execute(
            f'SELECT rowid, {cols_sql} FROM "{tabla}" ORDER BY rowid DESC'
        ).fetchall()
    finally:
        con.close()

    idx_activo = (columnas_reales.index("activo")
                  if "activo" in columnas_reales else None)
    columnas = [c for c in columnas_reales if c != "activo"]
    resultado = []
    for fila in filas_crudas:
        rowid, valores_crudos = fila[0], list(fila[1:])
        activo = valores_crudos[idx_activo] if idx_activo is not None else 1
        estado = "vigente" if (activo is None or activo == 1) else "anulado"
        valores = [v for i, v in enumerate(valores_crudos) if i != idx_activo]
        resultado.append({"rowid": rowid, "valores": valores, "estado": estado})

    if busqueda:
        b = busqueda.lower()
        resultado = [f for f in resultado
                     if any(b in str(v).lower() for v in f["valores"])]
    return columnas, resultado


def auditoria_de(tabla, rowid):
    """Entrada de `audit_log` para la anulación de esta fila, si existe.

    Empareja por (`tabla`, `ref = str(rowid)`) -- la convención real de
    `anular_fila` (services/anulacion.py): con `id_where` por defecto,
    `ref` termina siendo `str(id_valor)`, y para toda tabla con `id
    INTEGER PRIMARY KEY` eso ES el `rowid` (alias nativo de SQLite).

    Deliberadamente NO intenta más que esto. Dos rutas de anulación reales
    usan una convención de `ref` distinta y NO se pueden reconstruir sin
    adivinar: (1) `eliminarRegistro`/`eliminarfilas` pasan un `ref`
    LEGIBLE explícito (p.ej. "6 MV/03-2026") para las 5 tablas sin `id`
    propio (`dosimetriaMen`, `tamano_campo`, `preguntas`,
    `analisis_placa_franjas`, y `equipos_medicion` pese a tener `id`
    porque `ref` no es la primera columna); (2) el saneamiento de
    duplicados (SA1/SA2, `scripts/saneamiento_bloque_qc.py`) audita con el
    `ref` del BLOQUE (compartido por varias filas hermanas), no con el
    `rowid` de la fila anulada individual -- ese dato solo vive en el
    texto libre de `detalle` ("... esta fila (rowid=Y) queda histórica"),
    y parsearlo sería exactamente el tipo de adivinanza que este proyecto
    evita. Sin coincidencia exacta, el visor dice que no hay auditoría
    encontrada -- nunca inventa una."""
    con = Conexion().conectar()
    try:
        fila = con.execute(
            "SELECT usuario, timestamp, detalle FROM audit_log "
            "WHERE tabla = ? AND accion = 'anular' AND ref = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (tabla, str(rowid))).fetchone()
    finally:
        con.close()
    if fila is None:
        return None
    return {"usuario": fila[0], "fecha": fila[1], "detalle": fila[2]}
