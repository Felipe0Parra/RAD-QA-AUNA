"""F2 (PLAN_FECHAS_FIJAS_EN_TESTS_09-09.md): ninguna prueba puede fijar el
`date_box` a una fecha literal que **todavía no ha pasado**.

Nace de `DP-94`: `test_h8_tripwire_estado_imagen_no_sobrevive.py` fijaba
`QDate(2026, 9, 9)` como "día sin registro" -- y hoy ES 2026-09-09.
`QDateEdit.setDate(X)` con `X == date()` no emite `dateChanged`, así que la
recarga que limpia el estado de imagen nunca corría, y el tripwire de
`DP-79` reportaba el defecto de otro (la fecha) como si fuera el suyo.

**La regla es objetiva y deliberadamente simple, no "exacta".** No se
intenta reproducir la condición precisa que hace fallar a un test concreto
(eso depende de la secuencia de `setDate`/`setDateTime` de cada archivo,
como demuestra que `test_e4_dia_sin_registro_hora_actual.py` y
`test_t7_conexiones_no_se_acumulan.py` usaban fechas futuras SIN ser
frágiles -- llegan a ellas con `setDateTime` desde otro día, que sí emite
señal). La regla es: **ninguna fecha literal puede ser hoy o una fecha que
aún no ha llegado**, punto. Una fecha ya pasada nunca puede volver a ser
"hoy"; una futura lo será. Eso avisa **el día en que se escribe** una fecha
peligrosa, no meses después cuando el calendario la alcance.

Censo por AST (no por `grep`): busca todo `QDate(a, m, d)` con literales
enteros que sea argumento -- directo o anidado dentro de un
`QDateTime(QDate(...), ...)` -- de una llamada a `.setDate(...)` o
`.setDateTime(...)`. Una fecha en un comentario o un docstring no cuenta
(por eso no basta un `grep`); una mención de la fecha en un string que no
sea argumento de esas dos llamadas tampoco.

Lista de excepciones declaradas: vacía. Si algún día una prueba necesita
legítimamente una fecha futura (p. ej. "no se admite una fecha posterior a
hoy"), se añade aquí con su motivo escrito -- igual que
`SITIOS_PERMITIDOS` en `test_e2_formato_de_fecha_no_miente.py`."""
import ast
import datetime
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent

# Excepciones declaradas -- (archivo, línea, fecha ISO) -- con su motivo.
# VACÍA a propósito: ninguna prueba de hoy necesita una fecha futura.
EXCEPCIONES_PERMITIDAS = set()


def _es_llamada_setdate_o_setdatetime(nodo):
    return (isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr in ("setDate", "setDateTime"))


def _fechas_qdate_en(nodo):
    """Devuelve [(año, mes, día, lineno)] de todo `QDate(a, m, d)` con los
    tres argumentos literales enteros, dentro de `nodo` (un argumento de
    `setDate`/`setDateTime` -- puede ser el propio `QDate(...)` o un
    `QDateTime(QDate(...), QTime(...))` que lo envuelve)."""
    encontradas = []
    for sub in ast.walk(nodo):
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                and sub.func.id == "QDate"):
            continue
        if len(sub.args) != 3:
            continue
        valores = []
        for arg in sub.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                valores.append(arg.value)
        if len(valores) == 3:
            encontradas.append((*valores, sub.lineno))
    return encontradas


def censar_archivo(ruta):
    """[(lineno, fecha_iso)] de toda fecha literal >= hoy que ruta fije
    vía setDate/setDateTime -- y el total de llamadas analizadas (para
    la guarda de completitud, test_el_censo_encuentra_llamadas_de_verdad)."""
    fuente = ruta.read_text(encoding="utf-8")
    arbol = ast.parse(fuente, filename=str(ruta))
    hoy = datetime.date.today()

    violaciones = []
    total_llamadas = 0
    for nodo in ast.walk(arbol):
        if not _es_llamada_setdate_o_setdatetime(nodo):
            continue
        total_llamadas += 1
        for anio, mes, dia, lineno in _fechas_qdate_en(nodo):
            try:
                fecha = datetime.date(anio, mes, dia)
            except ValueError:
                continue  # no es una fecha real (p. ej. QDate(0,0,0) sentinel)
            if fecha >= hoy:
                violaciones.append((lineno, fecha.isoformat()))
    return violaciones, total_llamadas


def _todos_los_tests():
    return sorted(RAIZ.glob("test_*.py"))


class TestF2NingunaFechaLiteralEsHoyOFutura:
    def test_ningun_archivo_de_test_fija_una_fecha_no_pasada(self):
        hallazgos = []
        for ruta in _todos_los_tests():
            violaciones, _ = censar_archivo(ruta)
            for lineno, fecha_iso in violaciones:
                clave = (ruta.name, lineno, fecha_iso)
                if clave in EXCEPCIONES_PERMITIDAS:
                    continue
                hallazgos.append(f"{ruta.name}:{lineno} -> {fecha_iso}")

        assert not hallazgos, (
            "fecha(s) literal(es) >= hoy fijadas con setDate/setDateTime -- "
            "una fecha así deja de ser inerte el día en que el calendario "
            "la alcanza (DP-94), y ese día el test se pone rojo por una "
            "razón ajena a lo que dice probar. Mover cada una a una fecha "
            "ya pasada, o añadir la excepción aquí con su motivo escrito:\n  "
            + "\n  ".join(hallazgos))

    def test_el_censo_encuentra_llamadas_de_verdad(self):
        """Guarda contra que un cambio en el parseo (p. ej. un archivo con
        un error de sintaxis, o un refactor de este propio test) deje el
        censo vacío en silencio -- el mismo criterio que T1/E2 exigen para
        sus propios censos."""
        total = sum(censar_archivo(r)[1] for r in _todos_los_tests())
        assert total > 100, (
            f"solo se contaron {total} llamadas a setDate/setDateTime en "
            f"toda la carpeta tests/ -- [medido] antes de este test había "
            f"128; si el número cae tan bajo, el censo dejó de ver algo")


class TestF2LaTrampaSeDetectaEnUnCasoSintetico:
    """Rojo-antes-que-verde sintético, sin depender de ningún archivo real
    de la suite: reproduce el patrón exacto de DP-94 y confirma que el
    censo lo marca; confirma también que una fecha pasada, y una mención
    dentro de un comentario o de un string que no es argumento de
    setDate/setDateTime, quedan exentas."""

    def _censar_texto(self, texto, tmp_path):
        ruta = tmp_path / "test_sintetico_temporal.py"
        ruta.write_text(texto, encoding="utf-8")
        return censar_archivo(ruta)

    def test_fecha_futura_literal_se_marca(self, tmp_path):
        violaciones, _ = self._censar_texto(
            "w.setDate(QDate(2099, 1, 1))\n", tmp_path)
        assert violaciones == [(1, "2099-01-01")]

    def test_fecha_de_hoy_literal_se_marca(self, tmp_path):
        hoy = datetime.date.today()
        violaciones, _ = self._censar_texto(
            f"w.setDate(QDate({hoy.year}, {hoy.month}, {hoy.day}))\n", tmp_path)
        assert violaciones == [(1, hoy.isoformat())]

    def test_fecha_pasada_literal_queda_exenta(self, tmp_path):
        violaciones, _ = self._censar_texto(
            "w.setDate(QDate(2020, 1, 1))\n", tmp_path)
        assert violaciones == []

    def test_fecha_futura_dentro_de_qdatetime_se_marca(self, tmp_path):
        violaciones, _ = self._censar_texto(
            "w.setDateTime(QDateTime(QDate(2099, 1, 1), QTime(8, 0)))\n",
            tmp_path)
        assert violaciones == [(1, "2099-01-01")]

    def test_fecha_futura_en_comentario_queda_exenta(self, tmp_path):
        """Es lo que exige censar por AST y no por `grep`: la fecha vive
        en un comentario, no en un argumento real de setDate/setDateTime."""
        violaciones, _ = self._censar_texto(
            "# w.setDate(QDate(2099, 1, 1))\n"
            "w.setDate(QDate(2020, 1, 1))\n", tmp_path)
        assert violaciones == []

    def test_fecha_futura_en_string_ajeno_queda_exenta(self, tmp_path):
        violaciones, _ = self._censar_texto(
            "assert texto == 'QDate(2099, 1, 1)'\n", tmp_path)
        assert violaciones == []

    def test_qdate_futura_que_no_es_argumento_de_setdate_queda_exenta(self, tmp_path):
        """`QDate(2099, 1, 1)` suelta (comparada, no fijada) no es lo que
        esta regla vigila -- el riesgo es FIJAR el widget a esa fecha,
        no mencionarla."""
        violaciones, _ = self._censar_texto(
            "assert w.date() == QDate(2099, 1, 1)\n", tmp_path)
        assert violaciones == []
