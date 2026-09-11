"""C.7 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4, SS0.12-E7, "P6" decidido
SÍ, mínimo): cuatro gráficas rotulaban el eje Y como 'Dosis' sin serlo --
braquiterapia.py traza actividad (:1840/:4196) y ciclos (:1880/:4236,
duplicado exacto de la primera pareja -- corolario 4, hay que arreglar
las CUATRO o volverán a divergir); IX.py traza consistencia de dosis de
6 energías combinadas (:489).

Límite explícito del físico: *"ese dosis, solo agregar por ejemplo la
energía y ya, o como lo que te dije del 600 que es constancia de dosis a
6MV y ya"* -- nombrar la MAGNITUD, no inventarle una unidad ni corchetes
nuevos. `unovsuno.py:50` (compartida por las 4 diarias) usa el nombre de
columna seleccionado dinámicamente -- ya es correcto, no se toca.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAQUI = ROOT / "ui" / "paginasControles" / "PruebasDiarias" / "braquiterapia.py"
IX = ROOT / "ui" / "paginasControles" / "PruebasDiarias" / "IX.py"
UNOVSUNO = ROOT / "data" / "GraficasyTablas" / "unovsuno.py"


def _llamadas_set_ylabel(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for nodo in ast.walk(tree):
        if (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "set_ylabel"):
            yield nodo


class TestNingunEjeDiceDosisSobreOtraMagnitud:
    def test_censo_ast_ningun_set_ylabel_literal_dice_dosis(self):
        """Rojo-antes-que-verde inverso: hoy debe haber 4 sitios en
        braquiterapia.py + IX.py que digan 'Dosis' -- confirma que el
        censo encuentra el texto real antes de cambiarlo."""
        sospechosos = []
        for archivo in (BRAQUI, IX):
            for nodo in _llamadas_set_ylabel(archivo):
                if nodo.args and isinstance(nodo.args[0], ast.Constant) and nodo.args[0].value == "Dosis":
                    sospechosos.append((str(archivo.relative_to(ROOT)), nodo.lineno))
        assert sospechosos == [], f"Todavía dice 'Dosis' sobre otra magnitud: {sospechosos}"

    def test_las_cuatro_parejas_de_braqui_dicen_actividad_o_ciclos(self):
        texto = BRAQUI.read_text(encoding="utf-8")
        assert texto.count("ax.set_ylabel('Actividad')") == 2, (
            "las 2 copias (diario + su duplicado) deben decir 'Actividad'")
        assert texto.count("ax.set_ylabel('Ciclos')") == 2, (
            "las 2 copias (diario + su duplicado) deben decir 'Ciclos'")

    def test_ix_dice_consistencia_de_dosis_sin_corchetes(self):
        texto = IX.read_text(encoding="utf-8")
        assert "ax.set_ylabel('Consistencia de dosis')" in texto
        # Límite explícito del físico: nombrar la magnitud, no inventar
        # una unidad -- sin corchetes.
        assert "ax.set_ylabel('Consistencia de dosis [%]')" not in texto

    def test_unovsuno_no_se_toca(self):
        """Ya es correcto (usa el nombre de columna elegido
        dinámicamente) -- fuera de alcance de C.7."""
        texto = UNOVSUNO.read_text(encoding="utf-8")
        assert "ax.set_ylabel(selected_chart)" in texto
