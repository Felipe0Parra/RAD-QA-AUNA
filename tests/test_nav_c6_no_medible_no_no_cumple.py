"""C.6 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4, SS0.7, "P5" decidido SÍ):
`Analisis_PlacaCuadrada.py::format_val` (dentro de
`html_doble_columna`) decía "No cumple" cuando `calcular_penumbras`
devuelve `None` -- un hecho de la placa (el perfil no cruza el 20% del
máximo por ese lado), no un incumplimiento. Y la guarda
`valor and abs(valor) > 1e-4` mandaba un `0.0` legítimo a la misma rama.

Única excepción autorizada del protocolo de contención de este plan a
tocar zona roja: `format_val` es una función de PRESENTACIÓN, no entra
en ningún cálculo ni en nada que se guarde. Se toca esa función y nada
más del archivo -- `format_val_mm` (línea 785-786) tiene el mismo patrón
pero mide una magnitud distinta (excesos de franja, no penumbras) y
queda fuera de lo que el plan autorizó, documentado como hallazgo
lateral en el propio plan.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVO = ROOT / "analisisImagenes" / "Analisis_PlacaCuadrada.py"


class TestFormatValDistingueNoMedibleDeUnNumero:
    def test_none_es_no_medible(self):
        assert _con_conversion(1)(None) == "No medible"

    def test_cero_es_un_valor_real_no_no_medible(self):
        assert _con_conversion(1)(0.0) == "0.000 mm"

    def test_un_numero_normal_se_formatea(self):
        assert _con_conversion(1)(1.234) == "1.234 mm"

    def test_ya_no_existe_no_cumple_en_format_val(self):
        """AST, no texto plano -- un comentario que EXPLIQUE el defecto
        corregido (citando la cadena vieja entre comillas) no cuenta
        como un literal de presentación que todavía diga "No cumple"."""
        tree = ast.parse(ARCHIVO.read_text(encoding="utf-8"), filename=str(ARCHIVO))
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.FunctionDef) and nodo.name == "html_doble_columna":
                for sub in nodo.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name == "format_val":
                        literales = [
                            n.value for n in ast.walk(sub)
                            if isinstance(n, ast.Constant) and n.value == "No cumple"
                        ]
                        assert literales == []
                        return
        raise AssertionError("No se encontró format_val en html_doble_columna")


def _con_conversion(conversion):
    """Extrae por AST el `format_val` REAL anidado en `html_doble_columna`
    (no una reimplementación de prueba) y lo ejecuta con `conversion`
    ligada en su closure -- envolviéndolo en una función sintética que
    declara `conversion` como parámetro, para no tener que invocar
    `generar_reporte_completo` entero (que exige un `resultados_dict` con
    dependencias pesadas de análisis de imagen)."""
    tree = ast.parse(ARCHIVO.read_text(encoding="utf-8"), filename=str(ARCHIVO))
    nodo_format_val = None
    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "html_doble_columna":
            for sub in nodo.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == "format_val":
                    nodo_format_val = sub
                    break
    assert nodo_format_val is not None, "No se encontró format_val en html_doble_columna"

    envoltura = ast.FunctionDef(
        name="_fabrica",
        args=ast.arguments(
            posonlyargs=[], args=[ast.arg(arg="conversion")], vararg=None,
            kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[nodo_format_val, ast.Return(value=ast.Name(id="format_val", ctx=ast.Load()))],
        decorator_list=[], returns=None, lineno=1, col_offset=0)
    modulo = ast.Module(body=[envoltura], type_ignores=[])
    ast.fix_missing_locations(modulo)
    espacio = {}
    exec(compile(modulo, filename=str(ARCHIVO), mode="exec"), espacio)
    return espacio["_fabrica"](conversion)


class TestCensoNoCumpleFueraDeFormatValMm:
    def test_no_cumple_solo_sobrevive_en_format_val_mm(self):
        """format_val_mm (otra magnitud, excesos de franja) queda fuera
        del alcance autorizado por el plan -- se documenta, no se toca.
        Si "No cumple" aparece en CUALQUIER OTRO sitio, es una regresión
        o un sitio nuevo que hay que revisar."""
        tree = ast.parse(ARCHIVO.read_text(encoding="utf-8"), filename=str(ARCHIVO))
        sitios = []
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Constant) and nodo.value == "No cumple":
                sitios.append(nodo.lineno)
        # Debe quedar EXACTAMENTE una: la de format_val_mm.
        assert len(sitios) == 1, f"'No cumple' aparece en {len(sitios)} sitios: {sitios}"
