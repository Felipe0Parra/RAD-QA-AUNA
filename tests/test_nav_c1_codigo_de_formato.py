"""C.1 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4, SS0.8): el código del
formato oficial (code_1) y su versión (code_2) están declarados por
pantalla en widgets.xlsx. Los diarios pasaban solo `self.code_1.text()`
(sin versión); mensuales y anuales ni siquiera pasaban `id_maquina` (se
quedaba en su valor por defecto " "). `codigo_de_formato(pantalla)` los
une en un solo sitio.
"""
import ast
from pathlib import Path

from ui.util_formato import codigo_de_formato

ROOT = Path(__file__).resolve().parent.parent

SITIOS_DIARIOS = [
    ROOT / "ui" / "paginasControles" / "PruebasDiarias" / "halcyon.py",
    ROOT / "ui" / "paginasControles" / "PruebasDiarias" / "seiscientos.py",
    ROOT / "ui" / "paginasControles" / "PruebasDiarias" / "IX.py",
    ROOT / "ui" / "paginasControles" / "PruebasDiarias" / "braquiterapia.py",
]

SITIOS_MENSUAL_ANUAL = [
    ROOT / "ui" / "paginasControles" / "PruebasMensuales" / "seiscientos_mensual.py",
    ROOT / "ui" / "paginasControles" / "PruebasMensuales" / "braq_mensual.py",
    ROOT / "data" / "ManejoDatos" / "load.py",
    ROOT / "models" / "PDF" / "Anual" / "reportes_anuales.py",
]


class _WidgetFalso:
    def __init__(self, texto):
        self._texto = texto

    def text(self):
        return self._texto


class TestCodigoDeFormatoUnitario:
    def test_une_codigo_y_version(self):
        pantalla = type("P", (), {})()
        pantalla.code_1 = _WidgetFalso("IDC-F-RT-118")
        pantalla.code_2 = _WidgetFalso("V.04")
        assert codigo_de_formato(pantalla) == "IDC-F-RT-118 V.04"

    def test_pantalla_sin_widgets_devuelve_vacio(self):
        """TAC y las hojas de imágenes no declaran code_1/code_2 -- se
        queda como estaba antes de esta tarea, no se inventa nada."""
        pantalla = type("P", (), {})()
        assert codigo_de_formato(pantalla) == ""

    def test_solo_codigo_sin_version(self):
        pantalla = type("P", (), {})()
        pantalla.code_1 = _WidgetFalso("IDC-F-RT-118")
        assert codigo_de_formato(pantalla) == "IDC-F-RT-118"


def _llamadas_con_keyword(path, nombre_funcion, keyword):
    """Censo AST: para cada llamada a `nombre_funcion` en `path`, ¿pasa el
    keyword `keyword=...`? Devuelve la lista de (linea, fuente_del_valor)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    resultados = []
    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.Call):
            nombre = nodo.func.id if isinstance(nodo.func, ast.Name) else (
                nodo.func.attr if isinstance(nodo.func, ast.Attribute) else None)
            if nombre == nombre_funcion:
                valor_kw = next(
                    (kw.value for kw in nodo.keywords if kw.arg == keyword), None)
                resultados.append((nodo.lineno, valor_kw))
    return resultados


class TestLosDiariosPasanCodigoYVersion:
    def test_ningun_diario_pasa_solo_code_1_text(self):
        """Antes: `id_maquina=self.code_1.text()` -- sin la versión.
        Censo por texto (más simple que AST para un patrón de atributo
        encadenado): ningún archivo de PruebasDiarias debe seguir
        escribiéndolo así."""
        sospechosos = []
        for path in SITIOS_DIARIOS:
            texto = path.read_text(encoding="utf-8")
            if "id_maquina=self.code_1.text()" in texto:
                sospechosos.append(str(path.relative_to(ROOT)))
        assert sospechosos == [], (
            f"Diario todavía pasa id_maquina sin la versión: {sospechosos}")

    def test_los_4_diarios_usan_codigo_de_formato(self):
        faltantes = []
        for path in SITIOS_DIARIOS:
            texto = path.read_text(encoding="utf-8")
            if "codigo_de_formato(self)" not in texto:
                faltantes.append(str(path.relative_to(ROOT)))
        assert faltantes == [], f"No usa codigo_de_formato: {faltantes}"


class TestMensualYAnualPasanIdMaquina:
    def test_guardarpdf_mensual_recibe_codigo_de_formato(self):
        """Los mensuales llamaban guardarPDF_mensual(self, fecha, maquina,
        diccionario=...) sin id_maquina -- quedaba en su default " "."""
        vistos = 0
        for path in (ROOT / "ui" / "paginasControles" / "PruebasMensuales" / "seiscientos_mensual.py",
                     ROOT / "ui" / "paginasControles" / "PruebasMensuales" / "braq_mensual.py",
                     ROOT / "data" / "ManejoDatos" / "load.py"):
            for lineno, valor in _llamadas_con_keyword(path, "guardarPDF_mensual", "id_maquina"):
                vistos += 1
                assert valor is not None, (
                    f"{path.relative_to(ROOT)}:{lineno} sigue sin pasar id_maquina")
                fuente = ast.dump(valor)
                assert "codigo_de_formato" in fuente, (
                    f"{path.relative_to(ROOT)}:{lineno} no usa codigo_de_formato")
        assert vistos >= 4, "Se esperaban al menos 4 llamadas a guardarPDF_mensual censadas"

    def test_anual_recibe_codigo_de_formato(self):
        """guardarPDF_anual solo tiene UN llamador real, en la UI del
        anual (seiscientos_anual.py) -- reportes_anuales.py solo declara
        la función que RECIBE id_maquina, no decide qué pasarle."""
        path = ROOT / "ui" / "paginasControles" / "PruebasAnuales" / "seiscientos_anual.py"
        texto = path.read_text(encoding="utf-8")
        assert "codigo_de_formato" in texto
        assert "guardarPDF_anual(self, fecha, maquina, id_maquina=codigo_de_formato(self)" in texto
