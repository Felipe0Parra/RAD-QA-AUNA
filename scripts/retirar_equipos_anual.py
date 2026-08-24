"""MI5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI5, DA-44): retira `equipos_anual`
del esquema -- la única operación IRREVERSIBLE de todo el plan, por eso va
al final de la Fase 4 (después de MI1/MI2/MI3, con los índices ya creados
y verificados) y detrás del respaldo con fecha que `migrar_bd_a_estandar.py`
ya hace antes de tocar nada.

Condición verificada por el físico el 19-08 (§4.2 del plan): la tabla no
tiene ninguna consulta SQL que la nombre en el código vivo (el único
acierto de texto es el nombre de la función `mostrar_tabla_equipos_anual`,
que en realidad lee `equipos_medicion` -- ver G-3), y las 3 BD de
referencia tienen 0 filas. Aun así, el `DROP` se ejecuta **solo si la
tabla está vacía en la BD que se está migrando** -- una BD ajena al
linaje esperado con filas reales en `equipos_anual` no se toca, se
reporta para revisión manual. Ninguna otra tabla se retira por este
camino: es un script de una sola tabla, deliberadamente, para que
"retirar del esquema" siga siendo una decisión explícita por tabla, no un
mecanismo genérico que alguien pueda apuntar a la tabla equivocada.
"""
import sqlite3


def retirar_equipos_anual(ruta_db):
    """Devuelve un dict {"estado", "filas"}:
      - "no existe": la tabla no está en esta BD (el caso común -- ninguna
        BD nueva la crea, `CREATE TABLE` no existe en conection.py).
      - "retirada": existía, estaba vacía, se hizo DROP TABLE.
      - "NO RETIRADA -- ...": existía con filas -- no se toca, se reporta
        el conteo para que el físico decida.
    Nunca lanza: un `DROP TABLE` fallido (p.ej. permisos) se reporta igual
    que una tabla con filas, no revienta la migración completa.
    """
    con = sqlite3.connect(ruta_db)
    try:
        existe = bool(con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='equipos_anual'"
        ).fetchone())
        if not existe:
            return {"estado": "no existe", "filas": 0}

        total = con.execute("SELECT COUNT(*) FROM equipos_anual").fetchone()[0]
        if total > 0:
            return {
                "estado": (
                    f"NO RETIRADA -- tiene {total} fila(s) en esta BD, no se "
                    f"toca (DA-44 solo autoriza el DROP sobre una tabla vacía)"),
                "filas": total,
            }

        try:
            con.execute("DROP TABLE equipos_anual")
            con.commit()
        except sqlite3.DatabaseError as e:
            return {"estado": f"NO RETIRADA -- {e}", "filas": 0}
        return {"estado": "retirada", "filas": 0}
    finally:
        con.close()
