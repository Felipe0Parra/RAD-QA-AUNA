"""B.3 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS3, DP-96-E3, P1 del físico
confirmado): `_crear_tabla_tipo_calibracion` rotula la intensidad de la
fuente como `(GBq)` -- `R13` ya había corregido las tres unidades de
`_crear_tabla_resultados_actividad` (U/U/GBq -> [Ci]) pero esta función
quedó fuera de ese alcance. Confirmado con el propio número de serie
(`...-13659-19` -> 13.659 Ci): la misma página del PDF dice `(GBq)` arriba
y `[Ci]` abajo sobre magnitudes del mismo orden.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTES = ROOT / "models" / "PDF" / "Mensuales" / "reportes_mensuales.py"


def _docstrings(tree):
    """Nodos de docstring reales (primer statement de module/clase/función)
    -- para no confundir un párrafo que EXPLICA el historial de un arreglo
    con un literal de UI que todavía diga la unidad vieja."""
    contenedores = [tree] + [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for contenedor in contenedores:
        if contenedor.body and isinstance(contenedor.body[0], ast.Expr):
            valor = contenedor.body[0].value
            if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                yield valor


class TestIntensidadDeLaFuenteEnCi:
    def test_ninguna_actividad_del_reporte_de_braqui_dice_gbq(self):
        """AST, no texto plano: un docstring que EXPLIQUE el historial de
        la corrección (como el de _crear_tabla_resultados_actividad, de
        R13) no cuenta como un literal de UI que mienta."""
        tree = ast.parse(REPORTES.read_text(encoding="utf-8"), filename=str(REPORTES))
        ids_docstrings = {id(n) for n in _docstrings(tree)}
        sospechosos = [
            nodo.value for nodo in ast.walk(tree)
            if isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and "(GBq)" in nodo.value
            and id(nodo) not in ids_docstrings
        ]
        assert sospechosos == [], (
            f"El reporte de braqui todavía rotula una actividad en GBq -- "
            f"el resto de la página (R13) ya usa Ci: {sospechosos}")

    def test_intensidad_de_la_fuente_dice_ci(self):
        texto = REPORTES.read_text(encoding="utf-8")
        assert "'Intensidad de la fuente [Ci]'" in texto
