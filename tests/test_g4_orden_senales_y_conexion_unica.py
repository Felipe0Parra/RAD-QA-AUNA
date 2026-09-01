"""G4 (PLAN_BRAQUI_ANALISIS_PERSISTE_28-08.md §Fase 1): tripwire del orden
de emisión de las señales del `date_box`.

Sale del hallazgo de §3-bis (DP-66): en el build del 26-08, sin `R-1`, el
`date_box` tenía DOS conexiones (`dateChanged` -> cargar; `dateTimeChanged`
-> recalcular). Cada cambio de FECHA emitía las dos señales, y [medido]
Qt emite SIEMPRE `dateTimeChanged` ANTES que `dateChanged` -- sin importar
el orden en que se conectaron los slots. El recalculador corría, escribía
la actividad esperada, y el cargador (que llegaba después) la borraba de
nuevo con `_limpiar_widgets_diaria` antes de releer la BD -- carrera que
dejaba el campo vacío y bloqueaba el guardado (DP-56).

`R-1` cerró esto con UNA sola conexión (`dateTimeChanged ->
_al_mover_el_date_box`, que decide internamente qué hacer). Este archivo
fija las dos mitades para que nadie vuelva a abrir la carrera:
  1. El hecho de Qt en sí (con un `QDateTimeEdit` desnudo, sin nada del
     proyecto) -- documenta un comportamiento de Qt, no de esta app.
  2. Que `PruebaDiariaBraq` cuelgue EXACTAMENTE una conexión de señal
     sobre su `date_box` -- dos conexiones (a `dateChanged` Y a
     `dateTimeChanged`) vuelven a abrir la carrera de DP-56."""
import ast
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtWidgets import QApplication, QDateTimeEdit

RAIZ = Path(__file__).resolve().parent.parent
RUTA_BRAQUITERAPIA = RAIZ / "ui/paginasControles/PruebasDiarias/braquiterapia.py"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestG4_1_HechoDeQtDesnudo:
    def test_datetimechanged_se_emite_antes_que_datechanged(self, app):
        w = QDateTimeEdit()
        w.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        w.setDateTime(QDateTime(QDate(2026, 1, 1), QTime(0, 0, 0)))

        orden = []
        w.dateTimeChanged.connect(lambda _: orden.append("dateTimeChanged"))
        w.dateChanged.connect(lambda _: orden.append("dateChanged"))

        w.setDateTime(QDateTime(QDate(2026, 1, 2), QTime(9, 30, 0)))  # cambia fecha Y hora

        assert orden == ["dateTimeChanged", "dateChanged"], (
            f"[medido] Qt debe emitir dateTimeChanged ANTES que dateChanged "
            f"al cambiar fecha y hora a la vez; orden real: {orden}")

    def test_el_orden_no_depende_de_cual_se_conecto_primero(self, app):
        """El mismo hecho, con el orden de CONEXIÓN invertido -- si el
        orden observado dependiera de la conexión y no fuera un
        comportamiento fijo de Qt, este test lo delataría."""
        w = QDateTimeEdit()
        w.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        w.setDateTime(QDateTime(QDate(2026, 1, 1), QTime(0, 0, 0)))

        orden = []
        w.dateChanged.connect(lambda _: orden.append("dateChanged"))
        w.dateTimeChanged.connect(lambda _: orden.append("dateTimeChanged"))

        w.setDateTime(QDateTime(QDate(2026, 1, 2), QTime(9, 30, 0)))

        assert orden == ["dateTimeChanged", "dateChanged"], (
            f"el orden de emisión es del widget, no de la conexión; "
            f"orden real: {orden}")

    def test_cambiar_solo_la_hora_no_emite_datechanged(self, app):
        w = QDateTimeEdit()
        w.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        w.setDateTime(QDateTime(QDate(2026, 1, 1), QTime(0, 0, 0)))

        orden = []
        w.dateTimeChanged.connect(lambda _: orden.append("dateTimeChanged"))
        w.dateChanged.connect(lambda _: orden.append("dateChanged"))

        w.setTime(QTime(9, 30, 0))  # SOLO la hora, mismo día

        assert orden == ["dateTimeChanged"], (
            "un cambio de SOLO la hora no debe emitir dateChanged -- es "
            "la razón por la que _al_mover_el_date_box se conecta a "
            f"dateTimeChanged y no a dateChanged; orden real: {orden}")


def _contar_conexiones_date_box(clase_node):
    """Cuenta llamadas `self.date_box.<algo>.connect(...)` dentro del
    cuerpo de una clase (no desciende a otras clases del mismo archivo)."""
    total = 0
    for nodo in ast.walk(clase_node):
        if isinstance(nodo, ast.ClassDef) and nodo is not clase_node:
            continue  # una clase anidada tendría su propio censo -- no aplica aquí
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "connect"):
            continue
        senal = nodo.func.value  # self.date_box.dateTimeChanged
        if not isinstance(senal, ast.Attribute):
            continue
        widget_expr = senal.value  # self.date_box
        if (isinstance(widget_expr, ast.Attribute) and widget_expr.attr == "date_box"
                and isinstance(widget_expr.value, ast.Name) and widget_expr.value.id == "self"):
            total += 1
    return total


def _clase_por_nombre(nombre):
    arbol = ast.parse(RUTA_BRAQUITERAPIA.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ClassDef) and nodo.name == nombre:
            return nodo
    raise AssertionError(f"no se encontró la clase {nombre!r} en {RUTA_BRAQUITERAPIA}")


class TestG4_2_UnaSolaConexionSobreElDateBox:
    def test_pruebadiariabraq_cuelga_exactamente_una_conexion(self):
        clase = _clase_por_nombre("PruebaDiariaBraq")
        assert _contar_conexiones_date_box(clase) == 1, (
            "PruebaDiariaBraq debe conectar UNA sola señal de su date_box "
            "-- dos conexiones (dateChanged + dateTimeChanged) reabren la "
            "carrera de DP-56/R-1")

    def test_el_censo_detecta_una_segunda_conexion_sintetica(self):
        """Rojo antes que verde: reproduce el patrón exacto de antes de
        R-1 (dos conexiones sobre el mismo date_box) y confirma que el
        censo lo marca -- si esta prueba no discriminara, la de arriba
        podría estar pasando por casualidad."""
        fuente = '''
class Falsa:
    def setupButtonConnections(self):
        self.date_box.dateTimeChanged.connect(self._al_mover_el_date_box)
        self.date_box.dateChanged.connect(self.cargar_dailytest_desde_db)
'''
        arbol = ast.parse(fuente)
        clase = arbol.body[0]
        assert _contar_conexiones_date_box(clase) == 2
