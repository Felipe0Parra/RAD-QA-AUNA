"""U1 (PLAN_NUCLEO_04-08.md, Bloque U): medición de solo lectura de
duplicados en `controles`, previa a U2 (el índice UNIQUE parcial).

Por qué va separada y primero: si alguna BD del linaje tiene duplicados por
(equipo, control, mes/año) entre sus filas activas, hay que VERLOS antes de
intentar crear el índice -- crear un UNIQUE index sobre datos con duplicados
falla, y decidir qué hacer con ellos es del físico, nunca del código (el
principio de esta ronda: "evitar siempre borrar información antes de
verificar").

Reutiliza `services/fechas_control.py::mes_anio_de_fecha` para el parseo de
fecha en vez de duplicarlo (mismo criterio que `consistencia_dosis.py` y
`nombres_acelerador.py`).
"""
from services.fechas_control import mes_anio_de_fecha


def duplicados_controles(con):
    """Agrupa las filas ACTIVAS de `controles` por (equipo, control,
    mes/año) y devuelve solo los grupos con más de una fila -- lista de
    dicts {equipo, control, mes, anio, ids: [...]}, ordenada por
    (equipo, control, mes, anio). Nunca escribe nada; `con` puede ser
    sqlite3 o cualquier objeto con `.execute(sql).fetchall()`.
    """
    filas = con.execute(
        "SELECT id, equipo, control, fecha FROM controles "
        "WHERE activo IS NULL OR activo = 1"
    ).fetchall()

    grupos = {}
    for fila_id, equipo, control, fecha in filas:
        mes, anio = mes_anio_de_fecha(fecha)
        if mes is None:
            continue  # fecha no reconocible -- no se puede agrupar, no es un duplicado
        clave = (equipo, control, mes, anio)
        grupos.setdefault(clave, []).append(fila_id)

    resultado = []
    for (equipo, control, mes, anio), ids in sorted(grupos.items()):
        if len(ids) > 1:
            resultado.append({
                "equipo": equipo, "control": control,
                "mes": mes, "anio": anio, "ids": sorted(ids),
            })
    return resultado
