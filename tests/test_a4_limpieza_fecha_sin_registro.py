"""A4 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase A, R11): al navegar a una
fecha SIN registro, la diaria conservaba en pantalla los datos de la fecha
anterior -- guardar entonces los persistía bajo la fecha nueva, un dato que
el físico nunca introdujo para ese día. La causa: `cargar_dailytest_desde_db`
tenía `if query.next():` sin rama `else` (la limpieza vivía DENTRO del "sí
hay registro") en `seiscientos.py`, `IX.py` y `braquiterapia.py` (dos
clases: `PruebaDiariaBraq` y `Linealidad`, con widgets completamente
distintos entre sí).

Dos capas de prueba:
  - Unitaria: `_limpiar_widgets_diaria()` deja todo en blanco, construyendo
    solo los widgets mínimos que cada clase usa (test negativo: nada queda
    marcado ni con texto).
  - Integración: `cargar_dailytest_desde_db` con `QSqlQuery` sustituido por
    un doble controlable -- limpia SOLO cuando no hay fila para la fecha, y
    NUNCA cuando sí la hay (para no borrar un dato real por error).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (QApplication, QLineEdit, QMessageBox,
                             QPushButton, QWidget)

import ui.paginasControles.PruebasDiarias.seiscientos as seiscientos_mod
import ui.paginasControles.PruebasDiarias.IX as ix_mod
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.seiscientos import PruebaDiaria600
from ui.paginasControles.PruebasDiarias.IX import PruebaDiariaIX
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq, Linealidad


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _FakeRecord:
    def __init__(self, columnas):
        self._columnas = columnas

    def indexOf(self, nombre):
        return self._columnas.index(nombre) if nombre in self._columnas else -1


class _FakeQuery:
    """Doble de QSqlQuery: `_FakeQuery.resultados` (dict fecha -> lista de
    filas dict) se configura por test antes de llamar
    `cargar_dailytest_desde_db`."""
    resultados = {}
    error_texto = ""

    def __init__(self, db):
        self._filas = []
        self._idx = -1
        self._fecha = None

    def prepare(self, sql):
        pass

    def addBindValue(self, val):
        self._fecha = val

    def exec(self):
        self._filas = list(_FakeQuery.resultados.get(self._fecha, []))
        self._idx = -1
        return True

    def next(self):
        self._idx += 1
        return self._idx < len(self._filas)

    def record(self):
        cols = list(self._filas[self._idx].keys()) if self._filas else []
        return _FakeRecord(cols)

    def value(self, col):
        return self._filas[self._idx].get(col)

    def lastError(self):
        class _E:
            def text(self):
                return _FakeQuery.error_texto
        return _E()


class _FakeDb:
    def close(self):
        pass


@pytest.fixture(autouse=True)
def _reset_fake_query():
    _FakeQuery.resultados = {}
    yield
    _FakeQuery.resultados = {}


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """Trampa 2: bajo `QT_QPA_PLATFORM=offscreen` un `QMessageBox` real
    bloquea el proceso para siempre en su bucle modal -- pytest no lo mata,
    hay que matarlo a mano. Desde B1 la rama "sin registro" de
    `PruebaDiariaBraq.cargar_dailytest_desde_db` recalcula los campos
    derivados, y ese cálculo avisa por `QMessageBox.warning` cuando no
    encuentra fuente aplicable a la fecha (el caso de cualquier BD de test).
    Se mockean ANTES de ejercitar nada, y sobre la clase importada de
    `PyQt5.QtWidgets` -- inmune a desde qué módulo la importe producción
    (`seiscientos.py` ni siquiera la importa)."""
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


def _boton_checkable(marcado=False):
    b = QPushButton()
    b.setCheckable(True)
    b.setChecked(marcado)
    if marcado:
        b.setProperty("estado", "selected")
    return b


def _line_con_texto(texto):
    line = QLineEdit()
    line.setText(texto)
    return line


class TestLimpiarWidgetsDiariaUnitario:
    """`_limpiar_widgets_diaria` es una sola función, heredada de
    `PruebaBasico` (subida ahí por `I0`, `PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md`
    -- antes vivía copiada, byte a byte, en `PruebaDiaria600`/`IX`/`Braq`).
    `Linealidad` es la excepción: sus widgets son otros por completo (combos
    de modelo/serie, no Funciona/No funciona) y conserva su propia versión,
    sin relación de herencia con `PruebaBasico`."""

    def _obj_botones_lineas(self, clase):
        obj = clase.__new__(clase)
        QWidget.__init__(obj)
        obj.botones_finales = {("x", "y")}
        obj.df_bnt_funciona = ["btn_a_fun", "btn_b_fun"]
        obj.df_bnt_nofunciona = ["btn_a_nofun", "btn_b_nofun"]
        obj.btn_a_fun = _boton_checkable(marcado=True)
        obj.btn_a_nofun = _boton_checkable(marcado=False)
        obj.btn_b_fun = _boton_checkable(marcado=False)
        obj.btn_b_nofun = _boton_checkable(marcado=True)
        obj.df_lines = ["line_a", "line_b"]
        obj.line_a = _line_con_texto("12.3")
        obj.line_b = _line_con_texto("45.6")
        obj.observaciones = _line_con_texto("algo escrito ayer")
        return obj

    @pytest.mark.parametrize("clase", [PruebaDiaria600, PruebaDiariaIX, PruebaDiariaBraq])
    def test_deja_botones_lineas_y_observaciones_en_blanco(self, app, clase):
        obj = self._obj_botones_lineas(clase)

        obj._limpiar_widgets_diaria()

        assert obj.botones_finales == set()
        for nombre in ("btn_a_fun", "btn_a_nofun", "btn_b_fun", "btn_b_nofun"):
            boton = getattr(obj, nombre)
            assert boton.isChecked() is False
            # I1 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md): "" y no
            # "noselected" -- ese valor es el color de "descartado", que
            # cambiar_estilo le pone al botón NO elegido cuando el otro SÍ
            # se eligió; ponerlo a los dos a la vez (sin responder) pintaba
            # la pregunta como ya respondida en negativo. Ver
            # test_i1_botones_color_por_defecto.py para la verificación
            # sobre el COLOR efectivo, no solo la propiedad.
            assert boton.property("estado") == ""
        assert obj.line_a.text() == ""
        assert obj.line_b.text() == ""
        assert obj.observaciones.text() == ""

    def test_linealidad_deja_combos_y_medidas_en_blanco(self, app):
        from PyQt5.QtWidgets import QComboBox
        obj = Linealidad.__new__(Linealidad)
        QWidget.__init__(obj)
        for nombre in ("combo_modelo", "combo_serie", "combo_modelo_elec", "combo_serie_elec"):
            combo = QComboBox()
            combo.addItems(["A", "B", "C"])
            combo.setCurrentIndex(2)
            setattr(obj, nombre, combo)
        for nombre in ("repro_med1", "repro_prom", "q_est", "electrometro"):
            setattr(obj, nombre, _line_con_texto("9.9"))
        fila = [None, _line_con_texto("1"), _line_con_texto("2"),
                _line_con_texto("3"), _line_con_texto("4")]
        obj.medidas_lienalidad = [fila]

        obj._limpiar_widgets_diaria()

        for nombre in ("combo_modelo", "combo_serie", "combo_modelo_elec", "combo_serie_elec"):
            assert getattr(obj, nombre).currentIndex() == 0
        for nombre in ("repro_med1", "repro_prom", "q_est", "electrometro"):
            assert getattr(obj, nombre).text() == ""
        for campo in fila[1:5]:
            assert campo.text() == ""


class TestCargarDailytestLimpiaSoloSiNoHayRegistro:

    def _obj_seiscientos(self, monkeypatch):
        obj = PruebaDiaria600.__new__(PruebaDiaria600)
        QWidget.__init__(obj)
        obj.date_box = __import__("PyQt5.QtWidgets", fromlist=["QDateEdit"]).QDateEdit()
        obj.date_box.setDate(QDate(2026, 1, 1))
        obj.botones_finales = set()
        obj.boolean_colums = []
        obj.df_lines = []
        obj.opeenDatabase = lambda: _FakeDb()
        monkeypatch.setattr(seiscientos_mod, "QSqlQuery", _FakeQuery)
        return obj

    def test_sin_registro_limpia_y_actualiza_fecha(self, app, monkeypatch):
        obj = self._obj_seiscientos(monkeypatch)
        llamadas = []
        obj._limpiar_widgets_diaria = lambda: llamadas.append("limpio")
        _FakeQuery.resultados = {}  # ninguna fecha tiene fila

        obj.cargar_dailytest_desde_db(QDate(2026, 3, 15))

        assert llamadas == ["limpio"]
        assert obj.date_box.date() == QDate(2026, 3, 15)

    def test_con_registro_no_limpia(self, app, monkeypatch):
        obj = self._obj_seiscientos(monkeypatch)
        llamadas = []
        obj._limpiar_widgets_diaria = lambda: llamadas.append("limpio")
        fecha_str = QDate(2026, 3, 15).toString("yyyy-MM-dd")
        _FakeQuery.resultados = {
            fecha_str: [{"laseres": None, "telemetro": None, "tamano_campo": None,
                        "centrado_reticulo": None, "dosis_referencia": None}]
        }

        obj.cargar_dailytest_desde_db(QDate(2026, 3, 15))

        assert llamadas == [], "con registro existente no debe limpiarse nada"

    def test_ix_sin_registro_limpia(self, app, monkeypatch):
        obj = PruebaDiariaIX.__new__(PruebaDiariaIX)
        QWidget.__init__(obj)
        from PyQt5.QtWidgets import QDateEdit
        obj.date_box = QDateEdit()
        obj.date_box.setDate(QDate(2026, 1, 1))
        obj.botones_finales = set()
        obj.boolean_colums = []
        obj.df_lines = []
        obj.opeenDatabase = lambda: _FakeDb()
        monkeypatch.setattr(ix_mod, "QSqlQuery", _FakeQuery)
        llamadas = []
        obj._limpiar_widgets_diaria = lambda: llamadas.append("limpio")
        _FakeQuery.resultados = {}

        obj.cargar_dailytest_desde_db(QDate(2026, 4, 2))

        assert llamadas == ["limpio"]

    def test_braq_diario_sin_registro_limpia(self, app, monkeypatch):
        obj = PruebaDiariaBraq.__new__(PruebaDiariaBraq)
        QWidget.__init__(obj)
        from PyQt5.QtWidgets import QDateEdit
        obj.date_box = QDateEdit()
        obj.date_box.setDate(QDate(2026, 1, 1))
        obj.botones_finales = set()
        obj.boolean_colums = []
        obj.df_lines = []
        obj.opeenDatabase = lambda: _FakeDb()
        # H2 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): la rama "sin
        # registro" ahora llama a `resetear_imagen_ui()` (no ya solo a
        # `_limpiar_canvas()`) -- mismo motivo que el doble de
        # `_recalcular_campos_derivados_diaria` de abajo: este test es
        # unitario sobre el CARGADOR, no sobre el reseteo de imagen (que
        # tiene su propio test, test_h1_reseteo_imagen_ui_limpia_todo.py).
        obj.resetear_imagen_ui = lambda: None
        monkeypatch.setattr(braq_mod, "QSqlQuery", _FakeQuery)
        llamadas = []
        obj._limpiar_widgets_diaria = lambda: llamadas.append("limpio")
        # B1 (PLAN_ACTIVIDAD_ESPERADA_BRAQUI_27-08.md §B1): esta clase es la
        # única diaria con un campo DERIVADO (`line_1_exp_act_ci`, calculado
        # por decaimiento de la fuente). La limpieza de A4 lo vacía como a
        # cualquier otro, así que la misma rama lo recalcula acto seguido
        # para la fecha nueva. Se sustituye por un doble para que este test
        # siga siendo unitario sobre el CARGADOR: el recálculo real abre
        # sqlite3 y avisa por diálogo, y no es lo que aquí se prueba.
        obj._recalcular_campos_derivados_diaria = (
            lambda fecha: llamadas.append(("recalculo", fecha)))
        _FakeQuery.resultados = {}

        obj.cargar_dailytest_desde_db(QDate(2026, 5, 10))

        assert llamadas == ["limpio", ("recalculo", QDate(2026, 5, 10))], (
            "A4 debe seguir limpiando, y B1 debe recalcular DESPUÉS de "
            "limpiar (si recalculara antes, la limpieza borraría el valor)")

    def test_linealidad_sin_registro_limpia(self, app, monkeypatch):
        obj = Linealidad.__new__(Linealidad)
        QWidget.__init__(obj)
        from PyQt5.QtWidgets import QDateEdit
        obj.date_box = QDateEdit()
        obj.date_box.setDate(QDate(2026, 1, 1))
        obj.opeenDatabase = lambda: _FakeDb()
        monkeypatch.setattr(braq_mod, "QSqlQuery", _FakeQuery)
        llamadas = []
        obj._limpiar_widgets_diaria = lambda: llamadas.append("limpio")
        obj.checkBotonesFinales = lambda: None
        _FakeQuery.resultados = {}

        obj.cargar_dailytest_desde_db(QDate(2026, 6, 20))

        assert llamadas == ["limpio"]
