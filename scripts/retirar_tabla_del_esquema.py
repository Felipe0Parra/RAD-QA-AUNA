"""MI5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI5, DA-44) + EB7 (§6-EB7,
DA-50): retira del esquema una tabla de una lista blanca CERRADA -- la
única categoría de operación IRREVERSIBLE de todo el plan, por eso va al
final de la fase que la autoriza (después de que los índices/saneamiento
ya corrieron) y detrás del respaldo con fecha que
`migrar_bd_a_estandar.py` ya hace antes de tocar nada.

Generaliza lo que hasta EB7 era `retirar_equipos_anual.py` (una función
por tabla, duplicada) -- el docstring original de esa función argumentaba
"un script de una sola tabla, deliberadamente, para que 'retirar del
esquema' siga siendo una decisión explícita por tabla, no un mecanismo
genérico que alguien pueda apuntar a la tabla equivocada". Esa propiedad
se conserva intacta aquí: `TABLAS_RETIRABLES` es una lista blanca CERRADA
de nombres literales, no un parámetro libre -- `retirar_tabla_del_esquema`
RECHAZA cualquier tabla que no esté declarada en ella, exactamente igual
que `TABLAS_ANULABLES` rechaza cualquier tabla fuera de su propio
inventario. Añadir una tercera tabla exige editar este archivo a mano,
igual de explícito que crear un script nuevo -- lo único que cambia es
que dos casos estructuralmente idénticos (DROP condicionado a estar
vacía) no se copian y pegan.

Cada tabla lleva su propio motivo documentado, igual que
`EXCEPCIONES_INVENTARIO` (`services/anulacion.py`) documentaba por qué
esa tabla nunca versionaría:
  - `equipos_anual` (DA-44, MI5): 0 filas en las 3 BD de referencia,
    ninguna consulta SQL la nombra en el código vivo (el anual ya guarda
    sus equipos en `equipos_medicion`, G-3).
  - `posicionamiento_reposicionamiento` (DA-50, EB7): huérfana -- ningún
    código de producción la crea, lee ni escribe (ni siquiera tiene
    `CREATE TABLE`); el dato que guardaría ya lo recibe correctamente
    `CondicionesMedicion.desplazamiento_ini` por una ruta viva y
    verificada (§4.8 del plan).
"""
import sqlite3

TABLAS_RETIRABLES = frozenset({
    "equipos_anual",
    "posicionamiento_reposicionamiento",
})


def retirar_tabla_del_esquema(ruta_db, tabla):
    """Devuelve un dict {"estado", "filas"}:
      - "no existe": la tabla no está en esta BD (el caso común -- ninguna
        BD nueva la crea, ninguna de las dos tiene `CREATE TABLE` vivo en
        `conection.py`).
      - "retirada": existía, estaba vacía, se hizo DROP TABLE.
      - "NO RETIRADA -- ...": existía con filas -- no se toca, se reporta
        el conteo para que el físico decida.
    Nunca lanza por un DROP fallido (p.ej. permisos): se reporta igual que
    una tabla con filas, no revienta la migración completa. SÍ lanza
    `ValueError` si `tabla` no está en `TABLAS_RETIRABLES` -- llamar esto
    con una tabla arbitraria es un error de programación, no un caso a
    tolerar en silencio.
    """
    if tabla not in TABLAS_RETIRABLES:
        raise ValueError(
            f"'{tabla}' no está en la lista blanca de retiro "
            "(scripts/retirar_tabla_del_esquema.py::TABLAS_RETIRABLES) -- "
            "retirar una tabla del esquema es una decisión explícita, no "
            "un mecanismo genérico apuntable a cualquier nombre.")
    con = sqlite3.connect(ruta_db)
    try:
        existe = bool(con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (tabla,)).fetchone())
        if not existe:
            return {"estado": "no existe", "filas": 0}

        total = con.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
        if total > 0:
            return {
                "estado": (
                    f"NO RETIRADA -- tiene {total} fila(s) en esta BD, no se "
                    f"toca (solo se autoriza el DROP sobre una tabla vacía)"),
                "filas": total,
            }

        try:
            con.execute(f'DROP TABLE "{tabla}"')
            con.commit()
        except sqlite3.DatabaseError as e:
            return {"estado": f"NO RETIRADA -- {e}", "filas": 0}
        return {"estado": "retirada", "filas": 0}
    finally:
        con.close()
