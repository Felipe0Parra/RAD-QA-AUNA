"""FK1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-FK1, DA-43): línea base de los
huérfanos de integridad referencial preexistentes.

`BaseDatosQA.db` (producción) tiene 109 filas huérfanas -- hijas de `controles`
o `pruebas` cuyo padre ya no existe -- y `BaseDatosQA(A_Ajustar).db` tiene 116
(las 7 de más son `controles -> users` por el centinela histórico de 2º físico
`' ---- '`, que la migración normaliza a NULL con X1; de ahí la diferencia
116 -> 109). Son cicatrices de ANTES del soft-delete (C2) y de ANTES de
`foreign_keys=ON` (W2): controles borrados físicamente antes de que existiera
un contrato que lo impidiera, más una segunda numeración de `controles.id`
mezclada en el histórico (ids fuera del rango 1-45 que tiene la BD hoy).

Verificado (PLAN_CONTRATO_COMPLETO_19-08.md §2.9) que no son reparables sin
inventar información -- las filas hijas no tienen NINGUNA columna que las
identifique (`equipo`, `control`, `fecha` solo existen en `controles`) -- y
que no pueden CRECER: `foreign_keys=ON` en cada conexión (W2), las 58 tablas
migradas a `ON DELETE RESTRICT` (E10), y los triggers anti-borrado hacen que
un huérfano nuevo sea imposible hoy (probado en los dos sentidos: un INSERT
sin padre y un DELETE de un padre con hijas fallan ambos con
`IntegrityError`). Por eso DA-43 decide dejarlos como están, y este test fija
el número: **si alguna vez sube, es una regresión real** -- hoy quedaría
escondida entre las 109/116 viejas si nadie lo mide.

Esto formaliza como test lo que el protocolo de verificación de `CLAUDE.md`
(sección "Protocolo de verificación por tarea", punto 6) ya exige a mano:
*"`foreign_key_check` sin aumento (línea base 109 en producción, 116 en
`A_Ajustar`)"*.

Por qué va en la Fase 0 del plan y no más tarde: las Fases 4 (MI2, saneamiento)
y 5 (EB, reemplazo de bloque) MUEVEN filas del bloque de QC. Ancla el número
ANTES de que nada se mueva -- así la comparación vigila, en vez de solo medir
el resultado después.
"""
import os
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

RUTA_PRODUCCION_REAL = str(ROOT.parent / "BaseDatosQA.db")
RUTA_BD_VIEJA_REAL = str(ROOT.parent / "BaseDatosQA(A_Ajustar).db")

# Desglose por (tabla, padre_ausente) medido en PLAN_CONTRATO_COMPLETO_19-08.md
# §2.9. La diferencia entre las dos BD es exactamente (controles, users): 7 en
# A_Ajustar, 0 en producción -- ya migrada (X1 normalizó el centinela).
DESGLOSE_PRODUCCION = {
    ("tamano_campo", "controles"): 20,
    ("equipos_medicion", "controles"): 13,
    ("indicadores_brazo", "controles"): 12,
    ("control_cunas", "controles"): 12,
    ("indicadores_angulares_colimador", "controles"): 9,
    ("analisis_placa_correcciones", "controles"): 8,
    ("resolucion_espacial_regiones", "pruebas"): 8,
    ("resolucion_contraste_rois", "pruebas"): 6,
    ("analisis_placa_franjas", "controles"): 6,
    ("control_conos", "controles"): 5,
    ("analisis_placa_verificaciones", "controles"): 4,
    ("preguntas", "controles"): 4,
    ("tamaño_pixel", "pruebas"): 1,
    ("uniformidad_global", "pruebas"): 1,
}
TOTAL_PRODUCCION = 109

DESGLOSE_A_AJUSTAR = {**DESGLOSE_PRODUCCION, ("controles", "users"): 7}
TOTAL_A_AJUSTAR = 116


def _desglose_fk(con):
    desglose = {}
    for tabla, rowid, padre, fkid in con.execute("PRAGMA foreign_key_check"):
        clave = (tabla, padre)
        desglose[clave] = desglose.get(clave, 0) + 1
    return desglose


@pytest.mark.parametrize(
    "ruta,total_esperado,desglose_esperado,nombre",
    [
        (RUTA_PRODUCCION_REAL, TOTAL_PRODUCCION, DESGLOSE_PRODUCCION, "BaseDatosQA.db"),
        (RUTA_BD_VIEJA_REAL, TOTAL_A_AJUSTAR, DESGLOSE_A_AJUSTAR, "BaseDatosQA(A_Ajustar).db"),
    ],
)
def test_huerfanos_no_aumentan(ruta, total_esperado, desglose_esperado, nombre):
    if not os.path.exists(ruta):
        pytest.skip(f"{ruta} no está presente en este entorno")

    # PRAGMA foreign_key_check es una verificación de integridad
    # independiente -- no depende de que el PRAGMA foreign_keys esté ON en
    # esta conexión (a diferencia de la aplicación en vivo, W2, que sí lo
    # necesita para RECHAZAR escrituras que romperían una FK).
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        desglose = _desglose_fk(con)
        total = sum(desglose.values())
    finally:
        con.close()

    assert total <= total_esperado, (
        f"{nombre}: {total} violaciones de FK, más que la línea base "
        f"({total_esperado}) -- DA-43 asumía que un huérfano nuevo es "
        f"imposible (foreign_keys=ON + RESTRICT + triggers). Si esto falla, "
        f"algo rompió esa garantía: no es ruido esperado, es una regresión "
        f"real que hay que investigar antes de continuar cualquier tarea de "
        f"este plan."
    )
    nuevas = {k: v for k, v in desglose.items() if v > desglose_esperado.get(k, 0)}
    assert not nuevas, (
        f"{nombre}: aparecieron violaciones de FK en tablas/padres nuevos "
        f"respecto a la línea base -- {nuevas}"
    )


def test_produccion_no_puede_crecer_huerfanos_nuevos(tmp_path):
    """Confirma, sobre una copia, que las tres capas de protección (W2 +
    RESTRICT + triggers) hacen imposible un huérfano NUEVO -- la garantía
    concreta en la que se apoya DA-43 para decidir no reparar los 109
    existentes."""
    if not os.path.exists(RUTA_PRODUCCION_REAL):
        pytest.skip(f"{RUTA_PRODUCCION_REAL} no está presente en este entorno")

    import shutil
    copia = str(tmp_path / "copia.db")
    shutil.copy(RUTA_PRODUCCION_REAL, copia)

    con = sqlite3.connect(copia)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO preguntas (ref, iso_mec) VALUES (999999, 1.0)")

        con.execute("SELECT id FROM controles LIMIT 1")
        fila = con.execute(
            "SELECT c.id FROM controles c "
            "JOIN tamano_campo t ON t.ref = c.id LIMIT 1"
        ).fetchone()
        assert fila is not None, (
            "no se encontró un control con hijas en tamano_campo para probar "
            "el DELETE -- ajustar la tabla usada en la prueba"
        )
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("DELETE FROM controles WHERE id = ?", (fila[0],))
    finally:
        con.rollback()
        con.close()
