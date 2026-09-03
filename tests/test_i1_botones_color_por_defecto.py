"""I1 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase A): tras `_limpiar_widgets_
diaria`, los botones Funciona/No funciona quedan con el color PREDETERMINADO
(el mismo que un botón recién creado), no con el de "noselected".

Diagnóstico del físico: *"aunque sí se están limpiando bien los botones de
Funciona/No funciona, quedan sin color... como si ambos estuvieran
desactivados"*. `"noselected"` (`#ced876`/`#e69696` en `estilo.qss`,
comentado ahí mismo como "para disabled") es el color que `cambiar_estilo`
le pone al botón NO elegido -- ponérselo a los DOS botones a la vez (cuando
en realidad ninguno se ha respondido) pintaba la pregunta como "ya
respondida, en negativo".

Punto 1-bis del protocolo (CLAUDE.md): la aserción debe verificar lo que el
nombre del test promete. Este test se llama "color por defecto" -- así que
afirma sobre el COLOR EFECTIVO (muestreado con `grab()` sobre un pixel del
botón, con `resources/estilo.qss` cargado de verdad), no sobre el valor de
la propiedad `estado` (eso ya lo cubre `test_a4_limpieza_fecha_sin_registro.
py`). Ninguna otra prueba de esta suite carga la hoja de estilo real sobre
un widget aislado -- en producción solo se aplica en `MainWindow.estilo()`,
que las diarias no atraviesan cuando se construyen sueltas para test. Sin
cargarla, "noselected" y "" pintarían exactamente igual (ninguna regla
[estado] se resolvería nunca) y el test pasaría sin medir nada -- [medido]
verificado antes de escribir este archivo: con la hoja real cargada,
recién creado / estado="" -> mismo RGB en los dos botones; estado=
"noselected" -> RGB distinto en los dos.

Halcyon queda FUERA de la prueba de comportamiento real (no de la de
premisa): `I0` dejó constancia de que hereda `_limpiar_widgets_diaria` sin
usarla -- ni `df_bnt_funciona` ni `botones_finales` existen en una instancia
real de `PruebaDiariaHc` (su `initDATA` no pasa por `init_data()`, que es
quien los crea), así que llamarla ahí revienta con `AttributeError` por una
razón AJENA a I1. Igual que `test_i0`, se prueba lo que el plan cubre.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq
from ui.paginasControles.PruebasDiarias.seiscientos import PruebaDiaria600
from ui.paginasControles.PruebasDiarias.IX import PruebaDiariaIX

RUTA_QSS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources", "estilo.qss")


@pytest.fixture(scope="module")
def app():
    instancia = QApplication.instance() or QApplication([])
    # Sin esto NINGUNA regla [estado=...] de estilo.qss se resuelve nunca
    # -- ver el docstring del módulo. `MainWindow.estilo()` es el único
    # sitio de producción que la aplica, y las pruebas construyen las
    # diarias sueltas, sin pasar por `MainWindow`.
    with open(RUTA_QSS, encoding="utf-8") as f:
        instancia.setStyleSheet(f.read())
    return instancia


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _color_efectivo(app, boton):
    """Fuerza el repolinizado (sin esto Qt no recalcula la hoja de estilo
    tras cambiar una propiedad dinámica -- mismo mecanismo que
    `canvas.draw()` en H1) y muestrea el pixel central del botón renderizado
    offscreen."""
    boton.style().unpolish(boton)
    boton.style().polish(boton)
    boton.update()
    app.processEvents()
    pixmap = boton.grab()
    imagen = pixmap.toImage()
    return QColor(imagen.pixel(imagen.width() // 2, imagen.height() // 2)).getRgb()[:3]


class TestPremisaEstadoVacioIgualARecienCreado:
    """No depende de ninguna diaria concreta: es una propiedad de
    `estilo.qss` en sí mismo, la que hace que `I1` sea correcto."""

    def test_boton_funciona_recien_creado_y_estado_vacio_pintan_igual(self, app):
        fun = QPushButton("Funciona")
        fun.setObjectName("boton_funciona")
        fun.resize(150, 40)
        recien_creado = _color_efectivo(app, fun)

        fun.setProperty("estado", "")
        con_estado_vacio = _color_efectivo(app, fun)

        assert con_estado_vacio == recien_creado, (
            f'estado="" debe verse IDÉNTICO a un botón recién creado -- '
            f"recién creado={recien_creado}, con estado ''={con_estado_vacio}")

    def test_boton_nofunciona_recien_creado_y_estado_vacio_pintan_igual(self, app):
        nofun = QPushButton("No funciona")
        nofun.setObjectName("boton_nofunciona")
        nofun.resize(150, 40)
        recien_creado = _color_efectivo(app, nofun)

        nofun.setProperty("estado", "")
        con_estado_vacio = _color_efectivo(app, nofun)

        assert con_estado_vacio == recien_creado, (
            f'estado="" debe verse IDÉNTICO a un botón recién creado -- '
            f"recién creado={recien_creado}, con estado ''={con_estado_vacio}")


@pytest.mark.parametrize("clase", [PruebaDiariaBraq, PruebaDiaria600, PruebaDiariaIX])
class TestLimpiarDejaElColorPredeterminado:

    def test_limpiar_deja_el_color_predeterminado_no_el_de_noselected(
            self, app, bd_temporal, clase):
        d = clase(_UsuarioFalso())

        # Colores de referencia: RECIÉN CREADOS, antes de tocar nada --
        # el estado que "limpio" debe reproducir.
        primer_fun = getattr(d, list(d.df_bnt_funciona)[0])
        primer_nofun = getattr(d, list(d.df_bnt_nofunciona)[0])
        color_inicial_fun = _color_efectivo(app, primer_fun)
        color_inicial_nofun = _color_efectivo(app, primer_nofun)

        # Colores de "noselected", para demostrar que SÍ son distintos --
        # si no lo fueran, el resto del test no probaría nada.
        primer_fun.setProperty("estado", "noselected")
        primer_nofun.setProperty("estado", "noselected")
        color_noselected_fun = _color_efectivo(app, primer_fun)
        color_noselected_nofun = _color_efectivo(app, primer_nofun)
        assert color_noselected_fun != color_inicial_fun, (
            "premisa del test: 'noselected' debe pintarse distinto del "
            "color inicial, o esta prueba no mediría nada")
        assert color_noselected_nofun != color_inicial_nofun

        # Simular una respuesta marcada, y limpiar -- el camino real.
        primer_fun.setChecked(True)
        primer_fun.setProperty("estado", "selected")

        d._limpiar_widgets_diaria()

        assert _color_efectivo(app, primer_fun) == color_inicial_fun, (
            f"{clase.__name__}: tras limpiar, boton_funciona debe verse "
            f"como recién creado, no como 'noselected' -- inicial="
            f"{color_inicial_fun}, tras limpiar="
            f"{_color_efectivo(app, primer_fun)}")
        assert _color_efectivo(app, primer_nofun) == color_inicial_nofun, (
            f"{clase.__name__}: tras limpiar, boton_nofunciona debe verse "
            f"como recién creado, no como 'noselected'")
