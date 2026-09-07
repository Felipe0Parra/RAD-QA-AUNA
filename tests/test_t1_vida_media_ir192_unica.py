"""T1 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md §Fase 0): "una sola vida
media, y la correcta".

Antes del arreglo la app usaba DOS vidas medias distintas para la misma
fuente de Ir-192: el diario (`braquiterapia.py:844`, número reubicado por
`E4`/`E5` de `PLAN_BRAQUI_HORA_EDITABLE_07-09.md` -- la línea citada aquí
es una prosa histórica, no un censo, así que solo se corrige por
completitud) pasaba `vida_media_dias=73.83`; el mensual (`braq_mensual.py:977`),
`CalcularActividad` (`ActividadFuente.py:112`) y `load.py:4373` pasaban
`vida_media_dias=74.2`. Divergían hasta 1.416% a 300 días contra una
tolerancia del 3%. `74.2` no corresponde a ningún valor aceptado (NNDC/IAEA
da 73.827 d); `73.83` era ese valor redondeado.

Este test censa, por AST y contra el código fuente vigente (no contra el
número de línea), TODAS las llamadas de producción a `calcular_decaimiento`
y falla si alguna pasa `vida_media_dias=` con un literal -- el parámetro
deja de tener valor por defecto distinto en cada llamada; o se omite
(usa `VIDA_MEDIA_IR192_DIAS` por defecto) o se pasa la constante por
nombre. Más un test de valor que fija 73.827 y se pone rojo si alguien la
cambia sin tocar este archivo."""
import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

ARCHIVOS_CENSADOS = [
    "analisisImagenes/ActividadFuente.py",
    "ui/paginasControles/PruebasDiarias/braquiterapia.py",
    "ui/paginasControles/PruebasMensuales/braq_mensual.py",
    "data/ManejoDatos/load.py",
]


def censar_literales(fuente):
    """Devuelve [(lineno, valor)] de cada llamada a `calcular_decaimiento`
    cuyo argumento `vida_media_dias` (posicional 4to o keyword) sea un
    literal numérico -- no un `Name` (variable/constante) ni una
    expresión."""
    arbol = ast.parse(fuente)
    violaciones = []

    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and (
                (isinstance(nodo.func, ast.Name) and nodo.func.id == "calcular_decaimiento")
                or (isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "calcular_decaimiento"))):
            continue

        valor_nodo = None
        for kw in nodo.keywords:
            if kw.arg == "vida_media_dias":
                valor_nodo = kw.value
        if valor_nodo is None and len(nodo.args) >= 4:
            valor_nodo = nodo.args[3]

        if valor_nodo is not None and isinstance(valor_nodo, ast.Constant) and isinstance(valor_nodo.value, (int, float)):
            violaciones.append((nodo.lineno, valor_nodo.value))

    return violaciones


def contar_llamadas_totales(fuente):
    """Guarda contra que un refactor rompa el parseo por AST y el censo
    quede vacío en silencio (falso verde)."""
    arbol = ast.parse(fuente)
    return sum(
        1 for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call) and (
            (isinstance(nodo.func, ast.Name) and nodo.func.id == "calcular_decaimiento")
            or (isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "calcular_decaimiento")))


class TestLaTrampaSeDetectaEnUnCasoSintetico:
    """Rojo antes que verde: reproduce el patrón exacto de antes del
    arreglo (literal pasado por keyword o posicional) y confirma que el
    censo lo marca; confirma también que la forma correcta (sin el
    argumento, o con la constante por nombre) queda exenta."""

    def test_literal_por_keyword_se_marca(self):
        fuente = "dec = calcular_decaimiento(a, b, c, vida_media_dias=74.2)\n"
        violaciones = censar_literales(fuente)
        assert violaciones == [(1, 74.2)]

    def test_literal_posicional_se_marca(self):
        fuente = "dec = calcular_decaimiento(a, b, c, 73.83)\n"
        violaciones = censar_literales(fuente)
        assert violaciones == [(1, 73.83)]

    def test_sin_el_argumento_queda_exento(self):
        fuente = "dec = calcular_decaimiento(a, b, c)\n"
        assert censar_literales(fuente) == []

    def test_constante_por_nombre_queda_exenta(self):
        fuente = "dec = calcular_decaimiento(a, b, c, vida_media_dias=VIDA_MEDIA_IR192_DIAS)\n"
        assert censar_literales(fuente) == []


@pytest.mark.parametrize("ruta_relativa", ARCHIVOS_CENSADOS)
class TestCensoRealDeLosCuatroArchivos:
    def test_ninguna_llamada_pasa_un_literal(self, ruta_relativa):
        fuente = (RAIZ / ruta_relativa).read_text(encoding="utf-8")
        violaciones = censar_literales(fuente)
        assert not violaciones, (
            f"{ruta_relativa}: calcular_decaimiento recibe un vida_media_dias "
            f"literal (línea, valor): {violaciones} -- debe omitirse o pasar "
            f"VIDA_MEDIA_IR192_DIAS por nombre")


def test_el_censo_encuentra_llamadas_de_verdad():
    # Guarda contra que un refactor rompa el parseo por AST y el censo
    # quede vacío en silencio (falso verde) en los 4 archivos juntos.
    total = sum(
        contar_llamadas_totales((RAIZ / ruta).read_text(encoding="utf-8"))
        for ruta in ARCHIVOS_CENSADOS)
    assert total >= 4, (
        f"solo se encontraron {total} llamadas a calcular_decaimiento en "
        f"los 4 archivos censados -- ¿falló el parseo por AST?")


def test_vida_media_ir192_es_73_827_dias():
    """Fija el valor: si alguien lo cambia sin tocar este test, se pone
    rojo. NNDC/IAEA da 73.827 d para el Ir-192; 74.2 no corresponde a
    ningún valor aceptado."""
    from analisisImagenes.ActividadFuente import VIDA_MEDIA_IR192_DIAS
    assert VIDA_MEDIA_IR192_DIAS == 73.827
