"""PI.5 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md): la pestaña 'Imagen sintética' de la página de la posición inicial -- cuatro
deslizadores, la placa sintética con su línea y sus centros, su perfil y la gráfica real contra medido del barrido de
desfases --, probada POR EL CAMINO DEL USUARIO.

CAUSA. D6: el físico quiere ver cómo responde el método a anchos y saturación distintos, y su notebook empezó esa calibración
sin terminarla. Usa el MISMO `motor.analizar` que la imagen real (§5.2-1: validar una copia no validaría nada).

Lo que se prueba y por qué así (Trampas 1, 2, 3, 7 y 9 de CLAUDE.md):
  - El cálculo son varios segundos (la placa, su análisis y el barrido de 11 desfases: 12 análisis). Por eso NO corre en
    cada paso de un arrastre sino al soltar. Los gestos se entregan como los entrega Qt: un arrastre es `sliderPressed`, un
    `valueChanged` por paso con `isSliderDown()` verdadero y `sliderReleased` (y se prueba también con eventos de ratón
    REALES sobre el asa); el teclado, la rueda y el clic en la barra no tienen 'soltar' y se prueban con un temporizador
    de verdad. Un ESPÍA cuenta cuántas veces se le pide al motor la placa, el análisis y el barrido por gesto: el rojo del
    plan es conectar `valueChanged` directo al cálculo, y esa mutación hace que un arrastre dispare un cálculo por paso.
  - La gráfica se lee de la FIGURA (las líneas que de verdad se dibujaron), no de un atributo, y se compara con lo que da
    `barrido_sintetico` llamado aparte con los mismos parámetros.
  - Sin acceso a la BD: se prohíbe `sqlite3.connect` y `Conexion.conectar` mientras se usa la pestaña, y un censo por AST
    exige que ni la clase ni sus funciones nombren el servicio, el permiso ni SQL.
  - 'Limpiar = una página recién creada' se afirma con la huella genérica de PI.4 (que ahora ve los deslizadores y el
    estado de Python de la pestaña), no con una lista de lo que `reiniciar` limpia.

Lo medido al escribirla (y que el plan no decía): los valores por omisión (2.2 / 1.1 / 50 / -0.6) dan -0.602 mm para un real de
-0.6 (el '-0.635 ± 0.01' del plan es el desfase de la placa del notebook, -15 px, generada por OTRA función); un análisis son
0.3 s y el barrido 3.3 s (no 1-2 s); el barrido no depende del desfase elegido; con los extremos de los deslizadores el motor no
lanza nunca una excepción, pero 52 de 108 combinaciones son 'no medible' y 11 miden contra los puntos (la línea no se refina).
Compuertas de no vacuidad (Trampa 8): los casos 'no medible' y 'línea no refinada' afirman primero que la situación existe."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import sqlite3
from pathlib import Path

import pytest
from matplotlib.figure import Figure
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QWheelEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QAbstractSlider, QApplication, QStyle, QStyleOptionSlider

import data.ManejoDatos.conection as conection_mod
import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod
from analisisImagenes import posicion_inicial_braqui as motor
# Las fixtures de la página (la BD temporal, los diálogos sustituidos, el cursor) y la huella son las de PI.4: no se reescriben
# (precedente: PI.4 importa de PI.3 y PI.3 de PI.1).
from test_pi3_servicio_posicion_inicial import bd, plantilla  # noqa: F401
from test_pi4_pagina_posicion_inicial import (_cerrar, _cursor_limpio, _huella, app, archivo_braqui, dialogos, fabrica,  # noqa: F401
                                              pagina, _analizada)

RAIZ = Path(__file__).resolve().parent.parent
PAGINA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "posicion_inicial_braqui.py"
OMISION = {"ancho_x": 22, "ancho_y": 11, "saturacion": 50, "desfase": -6}
SINTETICA = pagina_mod.PESTANA_SINTETICA
TEXTO_DE_ESPERA = "Calculando la placa sintética..."


# ------------------------------------------------------------------------------------------------------------ espías

class _Espia:
    """Lo que le pidieron al motor, en orden: cada llamada con sus argumentos (y, del barrido, lo que devolvió)."""

    def __init__(self):
        self.placas, self.analisis, self.barridos = [], [], []
        self.real_barrido = motor.barrido_sintetico

    def reiniciar(self):
        self.placas.clear(), self.analisis.clear(), self.barridos.clear()

    def cuenta(self):
        return len(self.placas), len(self.analisis), len(self.barridos)


def _barrido_falso(ancho_x_mm, ancho_y_mm, saturacion, desfases_mm=tuple(range(-5, 6))):
    """Un barrido que no cuesta nada, DEPENDE de los tres parámetros de forma (una gráfica vieja se distingue de la nueva)
    y deja un punto no medible (+5), como el barrido real de los valores por omisión."""
    return [(float(d), None if d == 5 else round(d * saturacion + ancho_x_mm / 100 - ancho_y_mm / 1000, 6))
            for d in desfases_mm]


def _instalar(monkeypatch, barrido_falso):
    e = _Espia()
    real_placa, real_analizar, real_barrido = motor.placa_sintetica, motor.analizar, motor.barrido_sintetico

    def placa(*a, **k):
        e.placas.append((a, k))
        return real_placa(*a, **k)

    def analizar(*a, **k):
        e.analisis.append((a, k))
        return real_analizar(*a, **k)

    def barrido(*a, **k):
        resultado = (_barrido_falso if barrido_falso else real_barrido)(*a, **k)
        e.barridos.append((a, k, resultado))
        return resultado

    monkeypatch.setattr(motor, "placa_sintetica", placa)
    monkeypatch.setattr(motor, "analizar", analizar)
    monkeypatch.setattr(motor, "barrido_sintetico", barrido)
    return e


@pytest.fixture
def espia(monkeypatch):
    """Con el barrido REAL (3.3 s): para lo que afirma el plan sobre los datos de la gráfica."""
    return _instalar(monkeypatch, barrido_falso=False)


@pytest.fixture
def rapido(monkeypatch):
    """Con un barrido falso que no cuesta nada pero depende de los parámetros: para la mecánica de los gestos."""
    return _instalar(monkeypatch, barrido_falso=True)


@pytest.fixture(scope="module")
def barrido_omision():
    return motor.barrido_sintetico(2.2, 1.1, 0.5)


@pytest.fixture(scope="module")
def barrido_3_2():
    return motor.barrido_sintetico(3.2, 1.1, 0.5)


@pytest.fixture
def pestana(app, dialogos):
    """La pestaña sola (sin página ni BD)."""
    t = pagina_mod.PestanaSintetica()
    yield t
    _cerrar(t)


# ------------------------------------------------------------------------------------------------------------ gestos

def _arrastrar(deslizador, valores):
    """Un arrastre como lo entrega Qt: pulsar (`sliderPressed`), un `valueChanged` por paso con `isSliderDown()` verdadero y
    soltar (`sliderReleased`)."""
    deslizador.setSliderDown(True)
    for v in valores:
        deslizador.setValue(v)
    deslizador.setSliderDown(False)


def _centro_del_asa(deslizador):
    opcion = QStyleOptionSlider()
    opcion.initFrom(deslizador)
    opcion.orientation, opcion.minimum, opcion.maximum = Qt.Horizontal, deslizador.minimum(), deslizador.maximum()
    opcion.sliderPosition, opcion.sliderValue = deslizador.sliderPosition(), deslizador.value()
    opcion.singleStep, opcion.pageStep = deslizador.singleStep(), deslizador.pageStep()
    opcion.subControls, opcion.activeSubControls = QStyle.SC_All, QStyle.SC_None
    return deslizador.style().subControlRect(QStyle.CC_Slider, opcion, QStyle.SC_SliderHandle, deslizador).center()


def _arrastrar_con_raton(deslizador, desplazamientos):
    """El mismo arrastre con eventos de ratón REALES sobre el asa (el `QTest.mouseMove` de Qt 5 solo mueve el cursor y no
    genera el evento bajo la plataforma offscreen: se envía el evento de movimiento con el botón izquierdo apretado)."""
    centro = _centro_del_asa(deslizador)

    def raton(tipo, pos, boton, botones):
        QApplication.sendEvent(deslizador, QMouseEvent(tipo, QPointF(pos), boton, botones, Qt.NoModifier))

    raton(QEvent.MouseButtonPress, centro, Qt.LeftButton, Qt.LeftButton)
    for dx in desplazamientos:
        raton(QEvent.MouseMove, QPoint(centro.x() + dx, centro.y()), Qt.NoButton, Qt.LeftButton)
    raton(QEvent.MouseButtonRelease, QPoint(centro.x() + desplazamientos[-1], centro.y()), Qt.LeftButton, Qt.NoButton)


def _rueda(deslizador, hacia_arriba=True):
    evento = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120 if hacia_arriba else -120), 0, Qt.Vertical,
                         Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(deslizador, evento)


# ------------------------------------------------------------------------------------------------- lectura de la figura

def _datos(linea):
    return list(linea.get_xdata()), list(linea.get_ydata())


def _linea(figura, prefijo):
    """La línea del eje de la gráfica (el tercero de la figura) cuyo rótulo empieza así."""
    assert len(figura.axes) == 3, "la figura trae la ventana, el perfil y la gráfica"
    for linea in figura.axes[2].lines:
        if linea.get_label().startswith(prefijo):
            return linea
    raise AssertionError(f"ninguna línea '{prefijo}' en {[l.get_label() for l in figura.axes[2].lines]}")


def _hay_linea(figura, prefijo):
    return any(l.get_label().startswith(prefijo) for l in figura.axes[2].lines)


def _par(valores):
    return [(float(r), None if m is None else float(m)) for r, m in valores]


def _medidos(barrido):
    return [(r, m) for r, m in barrido if m is not None]


def _banda_y(parche):
    if hasattr(parche, "get_height"):                  # Rectangle (matplotlib 3.9 en adelante)
        return parche.get_y(), parche.get_y() + parche.get_height()
    ys = parche.get_xy()[:, 1]
    return float(min(ys)), float(max(ys))


# ======================================================================================== 1: las funciones puras

class TestValoresYTextos:
    def test_1_los_deslizadores_son_los_del_plan(self):
        d = pagina_mod.DESLIZADORES
        assert [x.clave for x in d] == ["ancho_x", "ancho_y", "saturacion", "desfase"]
        assert [x.rotulo for x in d] == ["Ancho en X [mm]", "Ancho en Y [mm]", "Saturación [%]", "Desfase real [mm]"]
        # (mínimo, máximo, omisión) en los enteros de Qt, y el divisor que los lleva a lo que recibe el motor
        assert [(x.minimo, x.maximo, x.omision, x.escala) for x in d] == [
            (5, 60, 22, 10), (5, 60, 11, 10), (30, 100, 50, 100), (-50, 50, -6, 10)]
        assert pagina_mod.PESTANA_SINTETICA == 3 and pagina_mod.PESTANA_IMAGEN == 0

    def test_1b_los_extremos_son_los_del_plan_en_unidades_del_motor(self):
        p = pagina_mod.parametros_sinteticos
        bajo = p({"ancho_x": 5, "ancho_y": 5, "saturacion": 30, "desfase": -50})
        alto = p({"ancho_x": 60, "ancho_y": 60, "saturacion": 100, "desfase": 50})
        assert bajo == {"ancho_x_mm": 0.5, "ancho_y_mm": 0.5, "saturacion": 0.3, "desfase_mm": -5.0}
        assert alto == {"ancho_x_mm": 6.0, "ancho_y_mm": 6.0, "saturacion": 1.0, "desfase_mm": 5.0}

    def test_1c_por_omision_son_los_de_la_placa_del_fisico(self):
        assert pagina_mod.parametros_sinteticos(OMISION) == {
            "ancho_x_mm": 2.2, "ancho_y_mm": 1.1, "saturacion": 0.5, "desfase_mm": -0.6}

    @pytest.mark.parametrize("clave,entero,texto", [
        ("ancho_x", 22, "2.2"), ("ancho_x", 5, "0.5"), ("ancho_x", 60, "6.0"), ("ancho_y", 11, "1.1"),
        ("saturacion", 50, "50"), ("saturacion", 30, "30"), ("saturacion", 100, "100"),
        ("desfase", -6, "-0.6"), ("desfase", 0, "0.0"), ("desfase", -50, "-5.0"), ("desfase", 50, "5.0")])
    def test_1d_el_valor_visible_lleva_su_decimal_y_nunca_menos_cero(self, clave, entero, texto):
        assert pagina_mod.texto_valor(clave, entero) == texto

    def test_2_el_texto_del_plan_con_los_valores_por_omision(self):
        resultado = pagina_mod.analizar_sintetica(pagina_mod.parametros_sinteticos(OMISION))
        assert pagina_mod.texto_sintetica(-0.6, resultado) == "Real -0.60 mm, medido -0.60 mm, error 0.00 mm"

    def test_2b_el_error_es_medido_menos_real_y_lleva_su_signo(self):
        p = pagina_mod.parametros_sinteticos({**OMISION, "desfase": 30})
        resultado = pagina_mod.analizar_sintetica(p)
        s = motor.resumen(resultado)
        assert s["estado"] == "ok" and resultado["mensaje_linea"] == pagina_mod.LINEA_REFINADA
        texto = pagina_mod.texto_sintetica(3.0, resultado)
        assert texto == f"Real 3.00 mm, medido {s['desfase_mm']:.2f} mm, error {s['desfase_mm'] - 3.0:.2f} mm"
        assert abs(s["desfase_mm"] - 3.0) > 0.001, "la prueba no es vacía: hay un error distinto de cero que firmar"

    def test_3_una_placa_que_no_se_puede_medir_dice_por_que(self):
        p = pagina_mod.parametros_sinteticos({"ancho_x": 5, "ancho_y": 5, "saturacion": 30, "desfase": -6})
        resultado = pagina_mod.analizar_sintetica(p)
        s = motor.resumen(resultado)
        assert s["estado"].startswith("no medible"), "la situación existe: con anchos de 0.5 mm y 30 % de saturación no se mide"
        assert pagina_mod.texto_sintetica(-0.6, resultado) == (
            "Real -0.60 mm, no medible: la linea tapa el borde de la meseta")

    def test_4_con_la_linea_no_refinada_el_numero_lo_dice(self):
        p = pagina_mod.parametros_sinteticos({"ancho_x": 22, "ancho_y": 60, "saturacion": 50, "desfase": -6})
        resultado = pagina_mod.analizar_sintetica(p)
        assert motor.resumen(resultado)["estado"] == "ok"
        assert resultado["mensaje_linea"] != pagina_mod.LINEA_REFINADA, \
            "la situación existe: con 6 mm de ancho en Y la meseta cubre la línea y no hay contraste para refinarla"
        assert pagina_mod.texto_sintetica(-0.6, resultado) == (
            "Real -0.60 mm, medido -0.58 mm, error 0.02 mm (la línea no se refinó: se midió contra los puntos)")

    def test_5_el_signo_de_la_nota_es_el_de_la_placa(self):
        """La nota dice que un desfase negativo pone la mancha a la derecha de la línea: se comprueba con la placa."""
        assert "línea - mancha" in pagina_mod.NOTA_SINTETICA and "negativo pone la mancha a la derecha" in pagina_mod.NOTA_SINTETICA
        resultado = pagina_mod.analizar_sintetica(pagina_mod.parametros_sinteticos(OMISION))
        gris = resultado["perfiles"]["gris"]
        assert gris["estado"] == "ok" and gris["desfase_px"] < 0
        assert float(gris["centros"].mean()) > float(resultado["x_ref"][gris["filas"]].mean()), "la mancha queda a la derecha"


class TestLaGrafica:
    BARRIDO = [(-5.0, -5.02), (-4.0, None), (-3.0, -2.97), (0.0, 0.01), (3.0, 3.04), (5.0, None)]

    def _dibujar(self, barrido=None, actual=(-0.6, -0.58), tolerancia=1.0):
        figura = Figure()
        ax = figura.add_subplot(111)
        pagina_mod.dibujar_barrido(ax, self.BARRIDO if barrido is None else barrido, actual, tolerancia)
        return ax

    def test_6_los_puntos_del_barrido_son_exactamente_los_medidos(self):
        ax = self._dibujar()
        x, y = _datos(next(l for l in ax.lines if l.get_label() == "barrido de 6 desfases"))
        assert list(zip(x, y)) == _medidos(self.BARRIDO)

    def test_6b_los_no_medibles_van_aparte_en_el_borde_inferior(self):
        ax = self._dibujar()
        x, y = _datos(next(l for l in ax.lines if l.get_label() == "no medible"))
        assert x == [-4.0, 5.0] and len(set(y)) == 1 and y[0] < min(m for _, m in _medidos(self.BARRIDO))
        assert ax.get_ylim()[0] < y[0] < ax.get_ylim()[0] + 1, "dentro del eje, pegado al borde inferior"

    def test_6c_sin_no_medibles_no_hay_marcas_aparte(self):
        ax = self._dibujar(barrido=_medidos(self.BARRIDO))
        assert not any(l.get_label() == "no medible" for l in ax.lines)

    def test_7_la_diagonal_la_franja_de_tolerancia_y_el_punto_resaltado(self):
        ax = self._dibujar()
        limite = ax.get_xlim()[1]
        x, y = _datos(next(l for l in ax.lines if l.get_label() == "medido = real"))
        assert x == [-limite, limite] and y == [-limite, limite], "la diagonal medido = real"
        assert len(ax.patches) == 1 and ax.patches[0].get_label() == "tolerancia ±1.0 mm"
        assert _banda_y(ax.patches[0]) == (-1.0, 1.0)
        assert _datos(next(l for l in ax.lines if l.get_label() == "placa mostrada")) == ([-0.6], [-0.58])

    def test_7b_la_tolerancia_sale_del_motor_no_de_un_literal(self):
        ax = self._dibujar(tolerancia=0.25)
        assert ax.patches[0].get_label() == "tolerancia ±0.25 mm" and _banda_y(ax.patches[0]) == (-0.25, 0.25)

    def test_7c_una_placa_mostrada_que_no_se_mide_se_marca_aparte_y_resaltada(self):
        ax = self._dibujar(actual=(2.5, None))
        x, y = _datos(next(l for l in ax.lines if l.get_label() == "placa mostrada, no medible"))
        marcas = _datos(next(l for l in ax.lines if l.get_label() == "no medible"))
        assert x == [2.5] and y == [marcas[1][0]] and not any(l.get_label() == "placa mostrada" for l in ax.lines)

    def test_8_el_eje_es_cuadrado_simetrico_y_contiene_todo(self):
        ax = self._dibujar()
        assert ax.get_xlim() == ax.get_ylim() and ax.get_xlim()[0] == -ax.get_xlim()[1] and ax.get_xlim()[1] >= 6.0
        lejos = self._dibujar(barrido=[(-5.0, -9.3), (0.0, 0.0), (5.0, 4.9)], actual=(0.0, 0.0))
        assert lejos.get_xlim()[1] >= 10.25, "un medido muy alejado no se sale del eje"
        assert lejos.get_aspect() in ("equal", 1.0)

    def test_8b_los_rotulos_llevan_la_unidad_entre_corchetes(self):
        ax = self._dibujar()
        assert ax.get_xlabel() == "desfase real [mm]" and ax.get_ylabel() == "desfase medido [mm]"
        assert ax.get_title() == "Medido contra real"


# =================================================================================== 2: la pestaña sola (sin página ni BD)

class TestLaPestanaSola:
    def test_10_nace_con_los_valores_del_plan_sin_calcular_y_sin_resultado(self, pestana, rapido):
        t = pestana
        assert {c: d.value() for c, d in t.deslizadores.items()} == OMISION
        assert [t.valores[c].text() for c in OMISION] == ["2.2", "1.1", "50", "-0.6"]
        assert [t.rotulos[c].text() for c in OMISION] == ["Ancho en X [mm]", "Ancho en Y [mm]", "Saturación [%]", "Desfase real [mm]"]
        assert all(d.orientation() == Qt.Horizontal for d in t.deslizadores.values())
        assert [(d.minimum(), d.maximum()) for d in t.deslizadores.values()] == [(5, 60), (5, 60), (30, 100), (-50, 50)]
        assert not t.calculada and t.recuadro.text() == "" and len(t.figura.axes) == 0
        assert rapido.cuenta() == (0, 0, 0), "construir la pestaña no calcula nada"
        assert not t._temporizador.isActive()

    def test_11_abrirla_calcula_una_vez_y_volver_no_recalcula(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        assert rapido.cuenta() == (1, 1, 1) and t.calculada
        t.al_mostrarse()
        t.al_mostrarse()
        assert rapido.cuenta() == (1, 1, 1)

    def test_12_un_arrastre_dispara_un_solo_calculo_al_soltar(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        deslizador = t.deslizadores["ancho_x"]
        deslizador.setSliderDown(True)
        for entero in range(23, 33):
            deslizador.setValue(entero)
            assert t.valores["ancho_x"].text() == f"{entero / 10:.1f}", "el valor visible sigue cada paso"
            assert rapido.cuenta() == (0, 0, 0), "arrastrando no se calcula"
            assert not t._temporizador.isActive(), "arrastrando tampoco se arma el temporizador"
        deslizador.setSliderDown(False)
        assert rapido.cuenta() == (1, 1, 1), "un análisis y un barrido por gesto"
        assert rapido.placas[0][0] == (-0.6, 3.2, 1.1, 0.5) and rapido.barridos[0][0] == (3.2, 1.1, 0.5)
        assert t.calculada and t.recuadro.text().startswith("Real -0.60 mm, medido ")

    def test_12b_el_mismo_arrastre_con_el_raton_real_sobre_el_asa(self, pestana, rapido):
        t = pestana
        t.resize(900, 800)
        t.show()
        QApplication.processEvents()
        t.al_mostrarse()
        rapido.reiniciar()
        deslizador = t.deslizadores["saturacion"]
        pasos = []
        deslizador.valueChanged.connect(lambda v: pasos.append((v, deslizador.isSliderDown())))
        _arrastrar_con_raton(deslizador, (20, 40, 80, 120))
        assert len(pasos) >= 3 and all(abajo for _, abajo in pasos), "el arrastre emitió un valueChanged por paso, con el asa apretada"
        assert deslizador.value() > 50 and t.parametros()["saturacion"] == deslizador.value() / 100
        assert rapido.cuenta() == (1, 1, 1), "un solo cálculo, al soltar el ratón"

    def test_13_soltar_sin_mover_no_recalcula(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        deslizador = t.deslizadores["desfase"]
        deslizador.setSliderDown(True)
        deslizador.setSliderDown(False)
        assert rapido.cuenta() == (0, 0, 0)
        _arrastrar(deslizador, [-3, -6])           # va y vuelve al valor calculado: tampoco hay nada que recalcular
        assert rapido.cuenta() == (0, 0, 0)

    def test_14_cambiar_solo_el_desfase_no_vuelve_a_barrer(self, pestana, rapido):
        """El barrido (3.3 s) no depende del desfase de la placa mostrada: se recuerda mientras no cambien los tres parámetros
        de forma. La gráfica conserva sus puntos y el punto resaltado sigue al deslizador."""
        t = pestana
        t.al_mostrarse()
        antes = _datos(_linea(t.figura, "barrido de"))
        _arrastrar(t.deslizadores["desfase"], [-3])
        assert rapido.cuenta() == (2, 2, 1), "un análisis más y ningún barrido más"
        assert _datos(_linea(t.figura, "barrido de")) == antes
        assert _datos(_linea(t.figura, "placa mostrada"))[0] == [-0.3]
        _arrastrar(t.deslizadores["desfase"], [40])
        assert rapido.cuenta() == (3, 3, 1) and _datos(_linea(t.figura, "placa mostrada"))[0] == [4.0]

    @pytest.mark.parametrize("clave,nuevo", [("ancho_x", 40), ("ancho_y", 20), ("saturacion", 60)])
    def test_14b_cambiar_un_parametro_de_forma_si_vuelve_a_barrer_y_la_grafica_es_la_nueva(self, pestana, rapido, clave, nuevo):
        t = pestana
        t.al_mostrarse()
        _arrastrar(t.deslizadores[clave], [nuevo])
        assert rapido.cuenta() == (2, 2, 2)
        p = t.parametros()
        esperado = _medidos(_barrido_falso(p["ancho_x_mm"], p["ancho_y_mm"], p["saturacion"]))
        assert list(zip(*_datos(_linea(t.figura, "barrido de")))) == esperado, "la gráfica NO es la del barrido anterior"
        assert rapido.barridos[-1][0] == (p["ancho_x_mm"], p["ancho_y_mm"], p["saturacion"])

    def test_14c_la_pestana_llama_al_motor_con_el_orden_de_argumentos_del_motor(self, pestana, rapido):
        t = pestana
        _arrastrar(t.deslizadores["ancho_x"], [31])
        _arrastrar(t.deslizadores["ancho_y"], [17])
        _arrastrar(t.deslizadores["saturacion"], [73])
        _arrastrar(t.deslizadores["desfase"], [-12])
        # placa_sintetica(desfase_mm, ancho_x_mm, ancho_y_mm, saturacion); barrido_sintetico(ancho_x_mm, ancho_y_mm, saturacion)
        assert rapido.placas[-1][0] == (-1.2, 3.1, 1.7, 0.73) and rapido.barridos[-1][0] == (3.1, 1.7, 0.73)
        assert rapido.analisis[-1][0][2] == 600.0, "se analiza a la resolución del procedimiento"

    @pytest.mark.parametrize("accion", [QAbstractSlider.SliderSingleStepAdd, QAbstractSlider.SliderPageStepAdd,
                                        QAbstractSlider.SliderSingleStepSub])
    def test_15_el_teclado_y_el_clic_en_la_barra_arman_un_temporizador_y_no_calculan_en_cada_paso(self, pestana, rapido, accion):
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        deslizador = t.deslizadores["ancho_y"]
        for _ in range(5):
            deslizador.triggerAction(accion)
        assert not deslizador.isSliderDown() and rapido.cuenta() == (0, 0, 0), "ni un cálculo por paso"
        assert t._temporizador.isActive() and t._temporizador.isSingleShot()
        assert t.valores["ancho_y"].text() == f"{deslizador.value() / 10:.1f}"
        t._temporizador.timeout.emit()
        assert rapido.cuenta() == (1, 1, 1), "al dejar de moverse, un solo cálculo"
        assert not t._temporizador.isActive()

    def test_15b_la_rueda_con_el_foco_arma_el_temporizador(self, pestana, rapido, monkeypatch):
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        monkeypatch.setattr(t.deslizadores["saturacion"], "hasFocus", lambda: True)
        _rueda(t.deslizadores["saturacion"])
        _rueda(t.deslizadores["saturacion"])
        assert t.deslizadores["saturacion"].value() > 50 and rapido.cuenta() == (0, 0, 0) and t._temporizador.isActive()

    def test_15e_la_rueda_sin_el_foco_no_mueve_el_deslizador_ni_calcula(self, pestana, rapido):
        """Como el combo de PI.4: un paso de rueda al pasar por la pestaña cambiaba un parámetro y lanzaba un cálculo."""
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        deslizador = t.deslizadores["saturacion"]
        assert not deslizador.hasFocus() and type(deslizador).__name__ == "_DeslizadorSinRueda"
        _rueda(deslizador)
        assert deslizador.value() == 50 and rapido.cuenta() == (0, 0, 0) and not t._temporizador.isActive()

    def test_15f_pulsar_un_asa_detiene_el_temporizador_que_dejo_armado_el_teclado(self, pestana, rapido):
        """Medido por Opus con eventos reales: tecla y luego arrastre calculaba a los 410 ms con el asa apretada y el gesto
        acababa en dos cálculos."""
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        t.deslizadores["ancho_x"].triggerAction(QAbstractSlider.SliderSingleStepAdd)
        assert t._temporizador.isActive()
        t.deslizadores["ancho_y"].setSliderDown(True)
        assert not t._temporizador.isActive(), "pulsar el asa lo detuvo"
        t.deslizadores["ancho_y"].setValue(30)
        t.deslizadores["ancho_y"].setSliderDown(False)
        assert rapido.cuenta() == (1, 1, 1), "un solo cálculo para todo el gesto"
        assert rapido.placas[0][0][1:3] == (2.3, 3.0), "con los dos cambios"

    def test_15g_si_el_temporizador_vence_con_el_raton_apretado_se_vuelve_a_armar(self, pestana, rapido, monkeypatch):
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        t.deslizadores["ancho_x"].triggerAction(QAbstractSlider.SliderSingleStepAdd)
        # (a) un asa apretada
        t.deslizadores["saturacion"].setSliderDown(True)
        t._temporizador.timeout.emit()
        assert rapido.cuenta() == (0, 0, 0) and t._temporizador.isActive(), "no calcula con el asa apretada"
        t.deslizadores["saturacion"].setSliderDown(False)       # (soltar calcula: es el gesto de siempre)
        assert rapido.cuenta() == (1, 1, 1)
        # (b) un clic mantenido en la barra: Qt repite el paso y no hay asa ni 'soltar' del asa
        t.deslizadores["ancho_y"].triggerAction(QAbstractSlider.SliderPageStepAdd)
        monkeypatch.setattr(QApplication, "mouseButtons", staticmethod(lambda: Qt.LeftButton))
        t._temporizador.timeout.emit()
        assert rapido.cuenta() == (1, 1, 1) and t._temporizador.isActive(), "no calcula con un botón apretado"
        monkeypatch.setattr(QApplication, "mouseButtons", staticmethod(lambda: Qt.NoButton))
        t._temporizador.timeout.emit()
        assert rapido.cuenta() == (2, 2, 2), "y calcula cuando ya no hay ninguno"

    def test_15c_el_temporizador_real_calcula_una_sola_vez_pasado_su_retraso(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        rapido.reiniciar()
        assert 200 <= t._temporizador.interval() <= 1000, "un retraso corto pero que junta los pasos de una ráfaga"
        for _ in range(6):
            t.deslizadores["ancho_x"].triggerAction(QAbstractSlider.SliderSingleStepAdd)
        QTest.qWait(t._temporizador.interval() + 400)
        assert rapido.cuenta() == (1, 1, 1) and not t._temporizador.isActive()
        assert rapido.placas[0][0][1] == 2.8, "con el valor final de la ráfaga"

    def test_15d_cada_paso_de_una_rafaga_reinicia_la_cuenta_atras(self, pestana, rapido):
        t = pestana
        deslizador = t.deslizadores["ancho_x"]
        deslizador.triggerAction(QAbstractSlider.SliderSingleStepAdd)
        primero = t._temporizador.remainingTime()
        QTest.qWait(150)
        espera = t._temporizador.remainingTime()
        deslizador.triggerAction(QAbstractSlider.SliderSingleStepAdd)
        assert espera < primero and t._temporizador.remainingTime() > espera, "el segundo paso volvió a armar el temporizador"
        t._temporizador.stop()

    def test_16_el_valor_visible_sigue_al_deslizador_en_todo_su_rango(self, pestana, rapido):
        t = pestana
        esperado = {"ancho_x": ("0.5", "6.0"), "ancho_y": ("0.5", "6.0"), "saturacion": ("30", "100"), "desfase": ("-5.0", "5.0")}
        for clave, (minimo, maximo) in esperado.items():
            t.deslizadores[clave].setValue(t.deslizadores[clave].minimum())
            assert t.valores[clave].text() == minimo
            t.deslizadores[clave].setValue(t.deslizadores[clave].maximum())
            assert t.valores[clave].text() == maximo
        t._temporizador.stop()

    def test_17_los_dibujos_son_la_ventana_el_perfil_y_la_grafica(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        ventana, perfil, grafica = t.figura.axes
        assert len(ventana.images) == 1 and ventana.get_ylabel() == "fila [px]"
        assert "Perfil de grises" in perfil.get_title() and perfil.get_ylabel() == "gris invertido"
        assert grafica.get_title() == "Medido contra real" and grafica.get_xlabel() == "desfase real [mm]"
        etiquetas = [l.get_label() for l in ventana.lines]
        assert "línea de referencia" in etiquetas and "centro de cada cuerda" in etiquetas, "la placa se ve con su línea y sus centros"
        assert t.recuadro.text() == "Real -0.60 mm, medido -0.60 mm, error 0.00 mm"

    def test_17e_se_dibuja_la_cuerda_central_y_la_grafica_lleva_leyenda(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        resultado = pagina_mod.analizar_sintetica(t.parametros())
        fila = pagina_mod.fila_representativa(resultado, "gris")
        assert fila > 0, "la cuerda central no es la primera fila"
        ventana, perfil, grafica = t.figura.axes
        assert [fila, fila] in [list(l.get_ydata()) for l in ventana.lines], "la línea punteada de la cuerda dibujada"
        crudo = next(l for l in perfil.lines if l.get_label() == "perfil crudo")
        assert list(crudo.get_ydata()) == list(resultado["imagenes"]["gris"][fila]), "el perfil es el de ESA cuerda"
        leyenda = grafica.get_legend()
        assert leyenda is not None and [x.get_text() for x in leyenda.get_texts()][:2] == ["tolerancia ±1.0 mm", "medido = real"]

    def test_17b_recalcular_reemplaza_los_dibujos_no_los_acumula(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        _arrastrar(t.deslizadores["ancho_x"], [30])
        _arrastrar(t.deslizadores["saturacion"], [70])
        assert len(t.figura.axes) == 3 and len(rapido.barridos) == 3, "tres cálculos y siempre tres ejes"

    def test_17d_la_franja_de_tolerancia_es_la_del_motor_no_un_literal(self, pestana, rapido, monkeypatch):
        monkeypatch.setitem(motor.PARAMETROS, "tolerancia_mm", 0.5)
        pestana.al_mostrarse()
        banda = pestana.figura.axes[2].patches[0]
        assert banda.get_label() == "tolerancia ±0.5 mm" and _banda_y(banda) == (-0.5, 0.5)

    def test_17c_el_historial_de_la_barra_se_vacia_al_dibujar_de_nuevo(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        t.barra.push_current()
        assert len(t.barra._nav_stack) == 1
        _arrastrar(t.deslizadores["desfase"], [-2])
        assert len(t.barra._nav_stack) == 0, "X5: sin barra.update() Home volvería a la vista de la figura anterior"

    def test_18_una_placa_que_no_se_mide_se_dibuja_aparte_y_lo_dice(self, pestana, rapido):
        t = pestana
        for clave, entero in (("ancho_x", 5), ("ancho_y", 5), ("saturacion", 30)):
            t.deslizadores[clave].blockSignals(True)
            t.deslizadores[clave].setValue(entero)
            t.deslizadores[clave].blockSignals(False)
        t.al_mostrarse()
        assert t.recuadro.text() == "Real -0.60 mm, no medible: la linea tapa el borde de la meseta"
        assert _hay_linea(t.figura, "placa mostrada, no medible")
        assert not any(l.get_label() == "placa mostrada" for l in t.figura.axes[2].lines), "no se dibuja como si se hubiera medido"

    def test_19_reiniciar_deja_la_pestana_como_recien_creada_sin_calcular(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        for clave, entero in (("ancho_x", 40), ("ancho_y", 20), ("saturacion", 70), ("desfase", 30)):
            _arrastrar(t.deslizadores[clave], [entero])
        t.barra.zoom()
        t.deslizadores["ancho_x"].triggerAction(QAbstractSlider.SliderSingleStepAdd)       # deja el temporizador armado
        assert t._temporizador.isActive() and t.barra.mode == "zoom rect"
        rapido.reiniciar()
        t.reiniciar()
        assert {c: d.value() for c, d in t.deslizadores.items()} == OMISION
        assert [t.valores[c].text() for c in OMISION] == ["2.2", "1.1", "50", "-0.6"]
        assert not t.calculada and t.recuadro.text() == "" and len(t.figura.axes) == 0 and t._barrido is None
        assert not t._temporizador.isActive() and t.barra.mode == "" and not t.lienzo.widgetlock.locked()
        assert rapido.cuenta() == (0, 0, 0), "reiniciar no es un gesto del físico: no dispara ningún cálculo"
        QTest.qWait(t._temporizador.interval() + 300)
        assert rapido.cuenta() == (0, 0, 0), "y el temporizador que estaba armado ya no calcula"

    def test_19b_despues_de_reiniciar_se_vuelve_a_barrer(self, pestana, rapido):
        t = pestana
        t.al_mostrarse()
        t.reiniciar()
        t.al_mostrarse()
        assert len(rapido.barridos) == 2, "la memoria del barrido también se reinicia"

    def test_19c_reiniciar_apaga_el_desplazar(self, pestana, rapido):
        t = pestana
        t.barra.pan()
        assert t.barra.mode == "pan/zoom"
        t.reiniciar()
        assert t.barra.mode == ""


class TestUnFalloNoDejaUnResultadoViejo:
    def test_20_un_fallo_se_avisa_con_su_titulo_y_borra_lo_anterior(self, pestana, rapido, dialogos, monkeypatch):
        dialogos.criticos_esperados = True
        t = pestana
        t.al_mostrarse()
        assert t.calculada and t.recuadro.text() != "" and len(t.figura.axes) == 3
        real = motor.analizar

        def revienta(*a, **k):
            raise RuntimeError("fallo de prueba")

        monkeypatch.setattr(motor, "analizar", revienta)
        _arrastrar(t.deslizadores["desfase"], [-3])
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["titulo"] == "Imagen sintética"
        assert "RuntimeError: fallo de prueba" in critico[0]["texto"]
        assert not t.calculada and t.recuadro.text() == "" and len(t.figura.axes) == 0, "IM3: nada viejo sobrevive"
        monkeypatch.setattr(motor, "analizar", real)
        _arrastrar(t.deslizadores["desfase"], [-4])
        assert t.calculada and t.recuadro.text().startswith("Real -0.40 mm"), "se recupera con el siguiente gesto"

    def test_20b_un_fallo_a_medio_dibujar_no_deja_medio_dibujo(self, pestana, rapido, dialogos, monkeypatch):
        dialogos.criticos_esperados = True
        t = pestana

        def revienta(*a, **k):
            raise RuntimeError("fallo al dibujar la grafica")

        monkeypatch.setattr(pagina_mod, "dibujar_barrido", revienta)     # la ventana y el perfil ya se dibujaron
        t.al_mostrarse()
        assert len(dialogos.de("critical")) == 1
        assert len(t.figura.axes) == 0 and not t.calculada and t.recuadro.text() == "" and t._ultimos is None

    def test_20c_descartar_repinta_el_lienzo(self, pestana, rapido, monkeypatch):
        t = pestana
        t.al_mostrarse()
        pintadas = []
        monkeypatch.setattr(t.lienzo, "draw_idle", lambda: pintadas.append(1))
        t._descartar()
        assert pintadas == [1], "sin repintar, tras un fallo la pantalla seguiría mostrando el dibujo viejo"

    @pytest.mark.parametrize("que,titulo", [("valor", "Imagen sintética"), ("mostrarse", "Imagen sintética"),
                                            ("soltar", "Imagen sintética")])
    def test_21_ningun_manejador_deja_escapar_una_excepcion(self, pestana, rapido, dialogos, monkeypatch, que, titulo):
        dialogos.criticos_esperados = True
        t = pestana

        def revienta(*a, **k):
            raise RuntimeError("fallo de prueba")

        if que == "valor":
            monkeypatch.setattr(pagina_mod, "texto_valor", revienta)
            t.deslizadores["ancho_x"].setValue(30)
        elif que == "mostrarse":
            monkeypatch.setattr(t, "_actualizar", revienta)
            t.al_mostrarse()
        else:
            monkeypatch.setattr(pagina_mod, "parametros_sinteticos", revienta)
            _arrastrar(t.deslizadores["ancho_x"], [30])
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["titulo"] == titulo and "RuntimeError: fallo de prueba" in critico[0]["texto"]
        t._temporizador.stop()


# ======================================================================== 3: la pestaña dentro de la página y de sus datos

class TestLaPaginaConLaPestana:
    def test_30_es_la_cuarta_pestana_y_la_pagina_no_calcula_al_construirse(self, fabrica, rapido):
        p = fabrica()
        assert p.pestanas.count() == 4 and p.pestanas.tabText(SINTETICA) == "Imagen sintética"
        assert p.pestanas.widget(SINTETICA) is p.sintetica and type(p.sintetica).__name__ == "PestanaSintetica"
        assert rapido.cuenta() == (0, 0, 0) and not p.sintetica.calculada
        assert p.sintetica._con_espera == p._con_espera, "la espera de la página (UX1)"

    def test_31_la_primera_vez_que_se_abre_calcula_y_despues_no(self, fabrica, rapido):
        p = fabrica()
        p.pestanas.setCurrentIndex(SINTETICA)
        assert rapido.cuenta() == (1, 1, 1) and p.sintetica.calculada
        for indice in (0, 1, 2, SINTETICA, 2, SINTETICA):
            p.pestanas.setCurrentIndex(indice)
        assert rapido.cuenta() == (1, 1, 1), "volver a la pestaña no recalcula"

    @pytest.mark.parametrize("indice", [0, 1, 2])
    def test_31b_las_otras_pestanas_no_disparan_ningun_calculo_sintetico(self, fabrica, rapido, indice):
        p = fabrica()
        p.pestanas.setCurrentIndex(3)
        p.sintetica.reiniciar()
        rapido.reiniciar()
        p.pestanas.setCurrentIndex(indice)
        assert rapido.cuenta() == (0, 0, 0)

    def test_32_la_espera_es_la_de_la_pagina_indicador_cursor_y_ningun_processEvents(self, fabrica, monkeypatch, rapido):
        p = fabrica()
        orden, durante, procesados = [], [], []
        monkeypatch.setattr(QApplication, "processEvents", staticmethod(lambda *a, **k: procesados.append(1)))
        monkeypatch.setattr(p.indicador, "repaint", lambda: orden.append("repaint"))
        placa = motor.placa_sintetica

        def espia(*a, **k):
            cursor = QApplication.overrideCursor()
            durante.append((cursor.shape() if cursor is not None else None, p.indicador.isHidden(), p.indicador.text()))
            orden.append("placa")
            return placa(*a, **k)

        monkeypatch.setattr(motor, "placa_sintetica", espia)
        p.pestanas.setCurrentIndex(SINTETICA)
        assert durante == [(Qt.WaitCursor, False, TEXTO_DE_ESPERA)], "cursor de espera e indicador durante el cálculo"
        assert orden[:2] == ["repaint", "placa"], "el indicador se repinta ANTES de calcular"
        assert QApplication.overrideCursor() is None and p.indicador.isHidden() and procesados == []

    def test_32b_un_fallo_restaura_el_cursor_y_el_aviso_sale_sin_el(self, fabrica, dialogos, monkeypatch, rapido):
        dialogos.criticos_esperados = True
        p = fabrica()

        def revienta(*a, **k):
            raise RuntimeError("fallo de prueba")

        monkeypatch.setattr(motor, "analizar", revienta)
        p.pestanas.setCurrentIndex(SINTETICA)
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["cursor"] is None, "X8: ningún diálogo con el cursor de espera"
        assert QApplication.overrideCursor() is None and p.indicador.isHidden() and not p.sintetica.calculada

    def test_33_sin_acceso_a_la_bd(self, fabrica, dialogos, rapido, monkeypatch):
        p = fabrica()
        intentos = []

        def prohibida(*a, **k):
            intentos.append(a)
            raise AssertionError("la pestaña sintética no abre ninguna BD")

        monkeypatch.setattr(sqlite3, "connect", prohibida)
        monkeypatch.setattr(conection_mod.Conexion, "conectar", prohibida)
        p.pestanas.setCurrentIndex(SINTETICA)
        s = p.sintetica
        _arrastrar(s.deslizadores["ancho_x"], [30, 35])
        _arrastrar(s.deslizadores["desfase"], [-20])
        s.deslizadores["saturacion"].triggerAction(QAbstractSlider.SliderSingleStepAdd)
        s._temporizador.timeout.emit()
        p.pestanas.setCurrentIndex(0)
        p.pestanas.setCurrentIndex(SINTETICA)
        s.reiniciar()
        assert intentos == [] and dialogos.llamadas == [] and rapido.cuenta()[2] == 3

    def test_34_la_imagen_subida_no_se_toca_y_recalcular_no_reinicia_la_sintetica(self, fabrica, dialogos, archivo_braqui, rapido):
        p = fabrica()
        _analizada(p, dialogos, archivo_braqui)
        antes = (p.estado, p.recuadro_gris.text(), p.recuadro_rgb.text(), p.boton_guardar.isEnabled(), p.puntos,
                 p.nombre_archivo.text(), p.selector_cambio.currentData())
        p.pestanas.setCurrentIndex(SINTETICA)
        _arrastrar(p.sintetica.deslizadores["ancho_x"], [30])
        _arrastrar(p.sintetica.deslizadores["desfase"], [-20])
        assert antes == (p.estado, p.recuadro_gris.text(), p.recuadro_rgb.text(), p.boton_guardar.isEnabled(), p.puntos,
                         p.nombre_archivo.text(), p.selector_cambio.currentData()), "la pestaña no depende de la imagen"
        p.boton_recalcular.click()
        assert p.sintetica.calculada and p.sintetica.deslizadores["ancho_x"].value() == 30, "Recalcular es de la imagen"
        assert p.pestanas.currentIndex() == 0

    def test_35_limpiar_deja_la_pagina_igual_a_una_recien_creada_con_la_sintetica_usada(self, fabrica, rapido):
        p = fabrica()
        p.pestanas.setCurrentIndex(SINTETICA)
        for clave, entero in (("ancho_x", 40), ("ancho_y", 20), ("saturacion", 70), ("desfase", 30)):
            _arrastrar(p.sintetica.deslizadores[clave], [entero])
        p.sintetica.barra.zoom()
        p.sintetica.deslizadores["ancho_x"].triggerAction(QAbstractSlider.SliderSingleStepAdd)
        nueva = fabrica()
        assert _huella(p) != _huella(nueva), "el ciclo cambió de verdad el estado (si no, la prueba no prueba nada)"
        p.boton_limpiar.click()
        assert _huella(p) == _huella(nueva)
        assert not p.sintetica._temporizador.isActive() and p.pestanas.currentIndex() == 0

    def test_35b_la_huella_ve_cada_cosa_de_la_sintetica_que_limpiar_debe_borrar(self, fabrica, rapido):
        """Prueba de la prueba: cada pieza del estado de la pestaña, estropeada una a una DESPUÉS de limpiar, cambia la huella."""
        p = fabrica()
        p.boton_limpiar.click()
        base = _huella(p)
        s = p.sintetica
        for estropear in (
                lambda: s.deslizadores["ancho_x"].setValue(30), lambda: s.deslizadores["ancho_y"].setValue(30),
                lambda: s.deslizadores["saturacion"].setValue(60), lambda: s.deslizadores["desfase"].setValue(0),
                lambda: s.valores["ancho_x"].setText("9.9"), lambda: s.recuadro.setText("algo"),
                lambda: s.figura.add_subplot(111), lambda: s.barra.zoom(), lambda: s.barra.push_current(),
                lambda: setattr(s, "_calculada", True), lambda: setattr(s, "_barrido", ((1.0, 1.0, 1.0), [])),
                lambda: setattr(s, "_ultimos", {"x": 1})):
            estropear()
            assert _huella(p) != base
            s._temporizador.stop()
            p.boton_limpiar.click()
            assert _huella(p) == base, "Limpiar repara lo estropeado"

    def test_36_el_ancho_minimo_de_la_pagina_no_crece_con_la_pestana(self, fabrica, rapido):
        p = fabrica()
        p.resize(1300, 900)
        p.show()
        QApplication.processEvents()
        base = p.minimumSizeHint().width()
        p.pestanas.setCurrentIndex(SINTETICA)
        QApplication.processEvents()
        assert base <= 800 and p.minimumSizeHint().width() <= base + 20, "PI.4: el QStackedWidget del menú toma el máximo"

    def test_37_cada_senal_de_la_pestana_tiene_exactamente_una_conexion(self, fabrica):
        p = fabrica()
        s = p.sintetica
        for clave, deslizador in s.deslizadores.items():
            assert deslizador.receivers(deslizador.valueChanged) == 1, clave
            assert deslizador.receivers(deslizador.sliderReleased) == 1, clave
            assert deslizador.receivers(deslizador.sliderPressed) == 1, clave
        assert s._temporizador.receivers(s._temporizador.timeout) == 1
        assert p.pestanas.receivers(p.pestanas.currentChanged) == 1

    def test_38_un_error_al_cambiar_de_pestana_se_avisa_y_no_escapa(self, fabrica, dialogos, monkeypatch):
        dialogos.criticos_esperados = True
        p = fabrica()

        def revienta(*a, **k):
            raise RuntimeError("fallo de prueba")

        monkeypatch.setattr(p.sintetica, "al_mostrarse", revienta)
        p.pestanas.setCurrentIndex(SINTETICA)
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["titulo"] == "Cambiar de pestaña"
        assert "RuntimeError: fallo de prueba" in critico[0]["texto"]


# ===================================== 4: con el motor REAL: lo que afirma el plan sobre los datos (lento: 3.6 s por cálculo)

class TestConElMotorReal:
    def test_40_por_omision_el_barrido_dibujado_es_exactamente_barrido_sintetico(self, pestana, espia, barrido_omision):
        t = pestana
        t.al_mostrarse()
        assert espia.cuenta() == (12, 12, 1), "la placa, su análisis y el barrido de 11 desfases (que son 11 análisis más)"
        assert espia.placas[0][0] == (-0.6, 2.2, 1.1, 0.5) and espia.barridos[0][0] == (2.2, 1.1, 0.5)
        assert [a[0][0] for a in espia.placas[1:]] == list(range(-5, 6)), "el barrido de -5 a 5 mm"
        assert _par(espia.barridos[0][2]) == _par(barrido_omision), "determinista: el mismo barrido llamado aparte"
        x, y = _datos(_linea(t.figura, "barrido de"))
        assert list(zip(x, y)) == _medidos(_par(barrido_omision))
        sin_medir = [r for r, m in barrido_omision if m is None]
        assert sin_medir, "compuerta: con los valores por omisión hay un desfase que no se mide"
        assert _datos(_linea(t.figura, "no medible"))[0] == sin_medir

    def test_41_por_omision_el_desfase_medido_es_el_real_y_el_punto_actual_esta_resaltado(self, pestana, espia, barrido_omision):
        t = pestana
        t.al_mostrarse()
        assert t.recuadro.text() == "Real -0.60 mm, medido -0.60 mm, error 0.00 mm"
        real, medido = (v[0] for v in _datos(_linea(t.figura, "placa mostrada")))
        assert real == -0.6 and abs(medido - (-0.6)) < 0.01, "el método recupera el desfase de la placa del físico"

    def test_42_un_gesto_dispara_un_analisis_y_un_barrido_y_la_grafica_es_la_nueva(self, pestana, espia, barrido_3_2):
        t = pestana
        t.al_mostrarse()
        espia.reiniciar()
        _arrastrar(t.deslizadores["ancho_x"], range(23, 33))
        assert espia.cuenta() == (12, 12, 1), "un análisis (la placa mostrada) y un barrido (11 análisis) por gesto"
        assert espia.placas[0][0] == (-0.6, 3.2, 1.1, 0.5) and espia.barridos[0][0] == (3.2, 1.1, 0.5)
        assert list(zip(*_datos(_linea(t.figura, "barrido de")))) == _medidos(_par(barrido_3_2))

    def test_43_el_unico_analisis_es_el_del_motor(self, pestana, espia):
        """§5.2-1: la pestaña no tiene un análisis propio: el que corre es el MISMO `motor.analizar` que usa la imagen real."""
        pestana.al_mostrarse()
        assert espia.analisis and all(llamada[0][2] == 600.0 for llamada in espia.analisis)


# ================================================================================================ 5: censos por AST

@pytest.fixture(scope="module")
def arbol():
    return ast.parse(PAGINA_PY.read_text(encoding="utf-8"))


def _clase(arbol, nombre):
    return next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == nombre)


def _funciones(arbol, nombres):
    return [n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name in nombres]


def _nombres_usados(nodos):
    usados = set()
    for nodo in nodos:
        usados |= {n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(nodo) if isinstance(n, ast.Attribute)}
    return usados


PURAS = {"texto_valor", "parametros_sinteticos", "analizar_sintetica", "texto_sintetica", "dibujar_barrido"}


class TestCensos:
    def test_50_la_pestana_no_nombra_ni_la_bd_ni_el_servicio_ni_el_permiso(self, arbol):
        nodos = [_clase(arbol, "PestanaSintetica")] + _funciones(arbol, PURAS)
        assert len(nodos) == 6, "compuerta: el censo encuentra la clase y las cinco funciones"
        prohibidos = {"svc", "usuario_actual", "DialogAdminPermisoEliminar", "QMessageBox", "QFileDialog", "Conexion", "sqlite3",
                      "execute", "executemany", "QSqlQuery", "QSqlDatabase", "plt", "pyplot", "processEvents", "guardar", "anular",
                      "listar", "leer", "existe_vigente", "cambios_de_fuente"}
        assert not (_nombres_usados(nodos) & prohibidos), _nombres_usados(nodos) & prohibidos

    def test_51_el_motor_se_usa_solo_por_la_puerta_del_motor(self, arbol):
        """Nada de análisis propio: la placa, el análisis, el resumen y el barrido son del motor."""
        llamadas = {n.func.attr for nodo in [_clase(arbol, "PestanaSintetica")] + _funciones(arbol, PURAS)
                    for n in ast.walk(nodo) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "motor"}
        assert llamadas == {"placa_sintetica", "analizar", "resumen", "barrido_sintetico"}

    def test_52_ninguna_senal_de_un_deslizador_calcula_directamente(self, arbol):
        """El rojo del plan: `valueChanged` conectado al cálculo dispara uno por paso de un arrastre (3.6 s cada uno)."""
        construir = next(n for n in _clase(arbol, "PestanaSintetica").body if isinstance(n, ast.FunctionDef) and n.name == "_construir")
        conexiones = [n for n in ast.walk(construir) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "connect"]
        por_senal = {}
        for c in conexiones:
            assert len(c.args) == 1 and isinstance(c.args[0], ast.Lambda), "cada señal por su pasarela (lambda)"
            por_senal[c.func.value.attr] = {n.func.attr for n in ast.walk(c.args[0]) if isinstance(n, ast.Call)
                                           and isinstance(n.func, ast.Attribute)}
        assert set(por_senal) == {"valueChanged", "sliderPressed", "sliderReleased", "timeout"}
        assert por_senal["valueChanged"] == {"_al_cambiar_valor"}, "valueChanged solo actualiza el valor visible y arma el temporizador"
        assert por_senal["sliderReleased"] == {"_actualizar"}
        assert por_senal["sliderPressed"] == {"_al_pulsar_deslizador"} and por_senal["timeout"] == {"_al_vencer_temporizador"}

    def test_53_los_manejadores_estan_protegidos(self, arbol):
        protegidos = {}
        for clase in ("PestanaSintetica", "PosicionInicialBraqui"):
            for n in _clase(arbol, clase).body:
                if isinstance(n, ast.FunctionDef):
                    for d in n.decorator_list:
                        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "_protegido":
                            protegidos[(clase, n.name)] = d.args[0].value
        assert protegidos[("PestanaSintetica", "_al_cambiar_valor")] == "Imagen sintética"
        assert protegidos[("PestanaSintetica", "al_mostrarse")] == "Imagen sintética"
        assert protegidos[("PestanaSintetica", "_actualizar")] == "Imagen sintética"
        assert protegidos[("PestanaSintetica", "_al_pulsar_deslizador")] == "Imagen sintética"
        assert protegidos[("PestanaSintetica", "_al_vencer_temporizador")] == "Imagen sintética"
        assert protegidos[("PosicionInicialBraqui", "_al_cambiar_pestana")] == "Cambiar de pestaña"

    def test_54_la_pagina_reinicia_la_pestana_dentro_de_restablecer_estado(self, arbol):
        """Una sola definición del estado de arranque: `__init__` y 'Limpiar' pasan por `_restablecer_estado`."""
        metodo = next(n for n in _clase(arbol, "PosicionInicialBraqui").body if isinstance(n, ast.FunctionDef)
                      and n.name == "_restablecer_estado")
        llamadas = [n.func.attr for n in ast.walk(metodo) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        assert "reiniciar" in llamadas
