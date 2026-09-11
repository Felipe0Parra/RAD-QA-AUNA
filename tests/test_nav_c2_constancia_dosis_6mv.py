"""C.2 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4): el diario del 600 rotula
el campo `dosis_referencia` como "Datos dosimetricos" (sin tilde) -- el
físico pide "Constancia de dosis para 6MV". El 600 es de una sola
energía, así que nombrarla en la fila la hace autoexplicativa; es el
mismo término que el físico ya usó para el formato oficial (R9).

La cadena vieja aparece en DOS sitios que deben quedar sincronizados:
el diccionario que arma el mapeo etiqueta->columna (`graficos_mapeo2`) y
el combo de gráficas (`graf_3`, literal aparte -- no se deriva de la
misma lista que graf_1/graf_2). La unidad ([%]) la sigue poniendo
`unidades_qc` vía `unovsuno.py`, sin cambio.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEISCIENTOS = ROOT / "ui" / "paginasControles" / "PruebasDiarias" / "seiscientos.py"


def _literales_de_produccion():
    """Todo el árbol de producción (excluye tests), como pide el
    protocolo de la tarea antes de tocar la cadena."""
    exclude = {".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache"}
    for path in ROOT.rglob("*.py"):
        if any(parte in exclude for parte in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                yield path, nodo.value


class TestNingunaComparacionPorIgualdadContraElLiteralViejo:
    def test_censo_ast_sin_comparaciones_literales_viejas(self):
        """Rojo-antes-que-verde inverso: hoy DEBE aparecer -- es lo que
        prueba que el censo encuentra el texto real antes de cambiarlo.
        Tras el cambio, cero apariciones."""
        sitios = [
            (str(path.relative_to(ROOT)), valor)
            for path, valor in _literales_de_produccion()
            if valor == "Datos dosimetricos"
        ]
        assert sitios == [], f"Todavía queda el literal viejo: {sitios}"


class TestElRotuloNuevo:
    def test_diccionario_invertido_usa_el_rotulo_nuevo(self):
        texto = SEISCIENTOS.read_text(encoding="utf-8")
        assert '"dosis_referencia": ["Constancia de dosis para 6MV", 3, "line"]' in texto

    def test_el_combo_de_graficas_usa_el_mismo_rotulo(self):
        """graf_3 es un literal APARTE, no derivado de la misma lista que
        graf_1/graf_2 -- si no se sincroniza, el combo mostraría un texto
        que ya no resuelve contra graficos_mapeo2 y el gráfico no
        graficaría nada al elegirlo."""
        texto = SEISCIENTOS.read_text(encoding="utf-8")
        assert "graf_3 = ['Seleccione...', \"Constancia de dosis para 6MV\"]" in texto

    def test_los_dos_sitios_dicen_exactamente_lo_mismo(self):
        """La garantía real: la etiqueta del diccionario Y la del combo
        son la MISMA cadena -- lo que hace que graficos_mapeo2 la
        resuelva de vuelta a 'dosis_referencia' cuando el físico la elige."""
        texto = SEISCIENTOS.read_text(encoding="utf-8")
        etiqueta_dict = texto.split('"dosis_referencia": [')[1].split(",")[0].strip()
        assert etiqueta_dict == '"Constancia de dosis para 6MV"'
