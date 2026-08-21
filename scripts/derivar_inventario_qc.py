"""IV1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV1, DA-40): deriva el inventario
de tablas versionables del bloque de QC a partir del grafo de claves foráneas,
en vez de mantenerlo a mano.

Origen del defecto que esto cierra: `TABLAS_ANULABLES` (services/anulacion.py)
nació respondiendo *"¿qué tabla tiene un botón de borrar alcanzable desde la
interfaz?"* (criterio de E7, 28-07). Desde `PLAN_CONTRATO_GUARDADO_13-08` el
propósito cambió a *"¿qué tabla participa en el reemplazo de bloque?"* -- y la
lista nunca se recalculó contra el propósito nuevo, solo se parchó a mano dos
veces (`control_conos`, `dosimetriaMen`). `analisis_placa_verificaciones` y
`_correcciones` son el mismo caso y nunca se parcharon -- el hallazgo que
originó este plan.

DA-40 (corregida antes de aceptarse): la derivación es en TIEMPO DE
DESARROLLO, no de ejecución. `TABLAS_ANULABLES` sigue siendo un
`frozenset({...})` LITERAL en el fuente -- lo exige el parseo AST de
`services/lectura_vigente.py::tablas_anulables()` (usado por ES1, RT1 y
`observador_contrato.py`, ninguno de los cuales importa PyQt5). Un inventario
calculado en runtime dejaría ciegas a las tres herramientas, y haría depender
la fuerza del contrato del estado de la BD (una BD sin migrar = cierre más
pequeño = contrato más débil, en silencio). Este script solo GENERA el texto
para pegar; la lista la sigue manteniendo el código, vigilada por el tripwire
IV2 (tests/test_iv2_completitud_inventario.py) para que no pueda divergir sin
que algo se ponga rojo.

Uso:
    python scripts/derivar_inventario_qc.py <ruta_a_BaseDatosQA.db>

Imprime tres cosas:
  1. El `frozenset({...})` literal completo, listo para pegar en
     `TABLAS_ANULABLES` (services/anulacion.py).
  2. Huecos: tablas del cierre transitivo que HOY no están ni en
     `TABLAS_ANULABLES` ni en `EXCEPCIONES_INVENTARIO` -- hay que clasificarlas
     (entran al frozenset, o se documentan como excepción con su motivo).
  3. Sobrantes: tablas en `TABLAS_ANULABLES` que ya NO están en el cierre
     transitivo (se retiró una raíz, o la tabla ya no tiene FK a ninguna) --
     señal de que hay que revisar por qué siguen ahí.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.lectura_vigente import (
    RAICES_QC, cierre_transitivo_fk, excepciones_inventario,
    tablas_anulables,
)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ruta_bd", help="Ruta a una BD SQLite del esquema vigente "
                         "(BaseDatosQA.db o una copia)")
    args = parser.parse_args()

    con = sqlite3.connect(f"file:{args.ruta_bd}?mode=ro", uri=True)
    try:
        cierre = cierre_transitivo_fk(con, RAICES_QC)
    finally:
        con.close()

    actuales = tablas_anulables() - RAICES_QC
    excepciones = set(excepciones_inventario())

    huecos = cierre - actuales - excepciones
    sobrantes = actuales - cierre

    print(f"--- Cierre transitivo desde las {len(RAICES_QC)} raíces de QC ---")
    print(f"{len(cierre)} tablas descendientes.\n")

    print("--- TABLAS_ANULABLES propuesto (pegar en services/anulacion.py) ---")
    print("frozenset({")
    for raiz in sorted(RAICES_QC):
        print(f'    "{raiz}",')
    for tabla in sorted(cierre - excepciones):
        print(f'    "{tabla}",')
    print("})\n")

    if huecos:
        print(f"--- HUECOS: {len(huecos)} tabla(s) del cierre sin clasificar ---")
        for tabla in sorted(huecos):
            print(f"  {tabla}")
        print("Clasifícalas: añádelas al frozenset de arriba, o documenta por qué "
              "NO deben versionar en EXCEPCIONES_INVENTARIO (services/anulacion.py) "
              "con su motivo.\n")
    else:
        print("--- Sin huecos: toda tabla del cierre está clasificada ---\n")

    if sobrantes:
        print(f"--- SOBRANTES: {len(sobrantes)} tabla(s) en TABLAS_ANULABLES "
              "que ya no están en el cierre ---")
        for tabla in sorted(sobrantes):
            print(f"  {tabla}")
        print("Revisa por qué: ¿se retiró una raíz, o la tabla perdió su FK?\n")
    else:
        print("--- Sin sobrantes ---\n")


if __name__ == "__main__":
    main()
