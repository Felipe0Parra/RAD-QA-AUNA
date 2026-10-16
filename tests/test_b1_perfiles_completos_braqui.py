"""B.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, PD1): en la posición inicial de braquiterapia los perfiles se ven COMPLETOS y cada gráfica dibuja todo lo que se usó para tomar
sus medidas. Es DIBUJO: ningún número cambia.

CAUSA (H10). `dibujar_perfil` fijaba `set_xlim(x_izq - 120, x_der + 120)` y `set_ylim(tope - 40, tope + 3)`: ±5 mm alrededor de la meseta y los 40 niveles de arriba (el físico: «el zoom está
muy profundo... preferiría que se viera el perfil completo»). No dibujaba el TOPE del que sale el umbral de la meseta ni los dos bordes subpíxel, y la ventana no dibujaba las bandas donde se decide el
lado del tránsito (solo se decían en el texto del resultado).

Qué fija este archivo, y cómo:
  1. El eje x cubre la ventana entera (±20 mm alrededor de la línea) y el eje y va de 0 al tope + 5 %, en el gris y en las tres capas, sobre las dos películas reales (rojo contra HEAD: ±120 px y
     tope - 40). Un eje secundario arriba en mm desde la línea (0 = línea) que convierte con la escala del resultado (sin escala, sin eje). Lo que ya se dibujaba sigue en su sitio.
  2. El TOPE (con la regla del umbral, con el delta con que se midió, no el de fábrica) y los dos bordes subpíxel de la meseta, en su valor del motor. Los bordes NO van como `axvline` (los
     tests 8b y 8c cuentan verticales).
  3. La ventana dibuja las BANDAS del tránsito (la de la banda y las dos de película con que se compara) como polígonos (el test 8d cuenta líneas de más de dos puntos) y rotula la extensión
     completa de cada una y su contraste; el lado sin banda medible se rotula «no medible», sin geometría.
  4. EL MOTOR devuelve los límites de la banda DENTRO del detalle de cada lado medible (`columnas`, `filas_banda`, `filas_arriba`, `filas_abajo`, `desde_mm`, `hasta_mm`). Se prueban de dos formas
     independientes: (a) por CONSISTENCIA, recalculando con las MISMAS funciones públicas del motor la mediana sobre exactamente esas columnas y filas (si los límites no son la región medida, no
     da el `banda`, `arriba` y `abajo` del detalle); (b) contra VERDAD CONOCIDA: una página entera de PF.0 (independiente del motor) con el centro de la mancha conocido: la banda empieza a >= 12 mm de
     ese centro y termina a 50 mm, por los dos lados, y sus grupos de comparación quedan arriba y abajo de la mancha, entre los clics.
  5. CENSO por AST: cada clave de `PARAMETROS` que leen `analizar`, `medir_perfil`, `resumen` y todo lo que llaman tiene su entrada en `TRAZO_DE_PARAMETRO` (qué trazo o qué rótulo la muestra);
     ninguna entrada sobra; y cada entrada está de verdad en la figura de la página (un trazo con esa etiqueta, el eje secundario, una frase del pie, el recuadro o la etiqueta de la página).
     Un parámetro nuevo sin entrada hace caer la prueba y la nombra. Los que no tienen geometría que dibujar van en el pie de cada figura, con el valor con que se midió.
  6. LA DISPOSICIÓN. Las aserciones sobre los límites pasaron con un primer diseño que dejaba cada perfil de las capas en 35 px y hacía colapsar `constrained_layout`: lo vio la captura, no ellas.
     Las tres capas comparten el eje x (los mm solo arriba, los px solo abajo) y la leyenda de la ventana va fuera de la disposición; un guardia renderiza la página a 1500 x 1000 y a 1500 x 800 y
     exige que la disposición no colapse y que ningún dibujo baje de lo medido menos un margen.

  7. RONDA 1 DE REVISIÓN (12-10), cinco hallazgos reproducidos con una corrida real y corregidos en su causa:
     R1-A  sin escala (resolución 'otra') el motor da `desde_mm`/`hasta_mm` None y las distancias en px (`desde_px`/`hasta_px`) y la ventana rotula la banda en píxeles, como el recuadro (5j, 5k, 6c, 6d, 7).
     R1-B  el lienzo de las pestañas con dibujos tiene un alto mínimo y, por debajo, se desplaza dentro de un área: con una página de 750 px los ejes del gris medían 6 y 4 px; el pie, el eje en mm y los
           rótulos (~215 px) no dependen de la altura de la página (9f, 9g, 9i; 9e ahora también fija que la leyenda de la ventana va fuera de la disposición).
     R1-C  (anotado en obstaculos.md: B.1 toca funciones que el plan no le asigna; nada que probar).
     R1-D  el eje en mm solo está en la capa roja de la pila: es el MISMO eje para las tres (comparten x y la línea está en el mismo x); se fija la equivalencia, no solo `[1, 0, 0]` (9d2).
     R1-E  las resoluciones de editor y la tolerancia del dpi no se veían en ningún sitio aunque el censo decía que sí (la etiqueta tenía «algún texto»): van en el pie con su valor y el censo exige el VALOR
           de una entrada «pagina» en su etiqueta (8e, 8h, 8i).

Trampa 9: las páginas se cierran con la receta completa (la fixture `fabrica` de PI.4). Trampa 10: ningún `lru_cache`; los resultados caros son fixtures de módulo."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import copy
import io
import re
import warnings
from pathlib import Path

import cv2
import numpy as np
import pytest
from matplotlib.axes._secondary_axes import SecondaryAxis
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QApplication, QScrollArea

import _placa_braqui_sintetica as pf0
import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod
from analisisImagenes import posicion_inicial_braqui as motor
from services import posicion_inicial_braqui as svc
from test_pi1_motor_posicion_inicial import CLICS_EPSON009, CLICS_PLACA_REAL
from test_pi3_servicio_posicion_inicial import BRAQUI_00, DATOS, EPSON009, _a_300_dpi, bd, plantilla  # noqa: F401  (fixtures de PI.3)
from test_pi4_pagina_posicion_inicial import (CLICS_NO_MEDIBLE, _analizada, _cursor_limpio, app, archivo_braqui,  # noqa: F401  (fixtures de PI.4)
                                              dialogos, fabrica, pagina)

RAIZ = Path(__file__).resolve().parent.parent
MOTOR_PY = RAIZ / "analisisImagenes" / "posicion_inicial_braqui.py"
PELICULA_PY = RAIZ / "analisisImagenes" / "pelicula.py"
IMAGENES = {"braqui_00": (BRAQUI_00, CLICS_PLACA_REAL), "EPSON009": (EPSON009, CLICS_EPSON009)}
PERFILES = ("gris", "R", "G", "B")
TAM = 25.4 / 600.0


# ------------------------------------------------------------------------------------------------------ ayudas

@pytest.fixture(scope="module")
def resultados():
    """El análisis de las dos películas reales, una sola vez (los dibujos no lo modifican)."""
    return {nombre: svc.analizar_imagen(datos, clics) for nombre, (datos, clics) in IMAGENES.items()}


def _eje():
    """(figura, eje) con un lienzo de verdad: el eje secundario solo da sus límites al dibujar."""
    figura = Figure()
    FigureCanvasAgg(figura)
    return figura, figura.subplots()


def _perfil(resultado, perfil, fila=None, **kw):
    fila = pagina_mod.fila_representativa(resultado, "gris") if fila is None else fila
    figura, eje = _eje()
    pagina_mod.dibujar_perfil(eje, resultado, perfil, fila, **kw)
    return figura, eje, fila


def _ventana(resultado, perfil="gris", fila=None, **kw):
    fila = pagina_mod.fila_representativa(resultado, "gris") if fila is None else fila
    figura, eje = _eje()
    pagina_mod.dibujar_ventana(eje, resultado, perfil, fila, **kw)
    return figura, eje, fila


def _artistas(eje):
    return [*eje.lines, *eje.patches, *eje.collections]


def _con_etiqueta(eje, prefijo):
    return [a for a in _artistas(eje) if a.get_label().startswith(prefijo)]


def _secundario(eje):
    return [c for c in eje.child_axes if isinstance(c, SecondaryAxis)]


def _area_de(lienzo):
    """El área de desplazamiento (QScrollArea) que contiene al lienzo, o None: el lienzo cuelga del viewport del área."""
    viewport = lienzo.parentWidget()
    area = viewport.parentWidget() if viewport is not None else None
    return area if isinstance(area, QScrollArea) else None


def _sin_meseta(resultado):
    """Una fila de la ventana donde la cuerda no tiene meseta (el borde de arriba, que es marco): el caso en que `dibujar_perfil` no fijaba los límites."""
    inicio = resultado["perfiles"]["gris"]["m"]["inicio"]
    filas = np.where(inicio < 0)[0]
    assert len(filas), "compuerta: la ventana tiene alguna fila sin meseta"
    return int(filas[0])


def _de_la_ventana_a_la_imagen(resultado, columna, fila):
    """(x, y) en la imagen original de un punto (columna, fila) de la ventana rotada: la inversa de la matriz que devuelve el motor."""
    inversa = cv2.invertAffineTransform(resultado["matriz_ventana"])
    x, y = inversa @ np.array([columna, fila, 1.0])
    return float(x), float(y)


# ================================================================================ 1. el perfil se ve completo

class TestElPerfilSeVeCompleto:
    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    @pytest.mark.parametrize("perfil", PERFILES)
    def test_1_el_eje_x_cubre_la_ventana_entera_en_el_gris_y_en_las_tres_capas(self, resultados, nombre, perfil):
        r = resultados[nombre]
        _, eje, fila = _perfil(r, perfil)
        assert r["perfiles"]["gris"]["m"]["inicio"][fila] >= 0, "compuerta: la cuerda tiene meseta (el caso en que hoy se acerca a ±120 px)"
        ancho = r["imagenes"][perfil].shape[1]
        x0, x1 = eje.get_xlim()
        assert x0 <= 0 and x1 >= ancho - 1, f"el eje x ({x0:.1f}, {x1:.1f}) no cubre la ventana [0, {ancho - 1}]: se ve un acercamiento, no el perfil completo"
        assert x0 >= -1.0 and x1 <= ancho, f"el eje x ({x0:.1f}, {x1:.1f}) se pasa de la ventana [0, {ancho - 1}]"

    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    @pytest.mark.parametrize("perfil", PERFILES)
    def test_1b_el_eje_y_va_de_cero_al_tope_mas_cinco_por_ciento(self, resultados, nombre, perfil):
        r = resultados[nombre]
        _, eje, fila = _perfil(r, perfil)
        m = r["perfiles"][perfil]["m"]
        minimo = min(float(r["imagenes"][perfil][fila].min()), float(m["suave"][fila].min()))
        y0, y1 = eje.get_ylim()
        assert y0 == pytest.approx(min(0.0, minimo)), f"el eje y empieza en {y0:.1f}: hoy muestra solo los 40 niveles de arriba"
        assert y1 == pytest.approx(m["tope"] * 1.05), f"el eje y termina en {y1:.2f}, no en el tope ({m['tope']:.2f}) + 5 %"
        assert y0 <= minimo and y1 >= m["tope"]

    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    def test_1c_una_cuerda_sin_meseta_tambien_se_ve_completa(self, resultados, nombre):
        r = resultados[nombre]
        fila = _sin_meseta(r)
        _, eje, _ = _perfil(r, "gris", fila)
        ancho = r["imagenes"]["gris"].shape[1]
        x0, x1 = eje.get_xlim()
        assert x0 <= 0 and x1 >= ancho - 1 and x0 >= -1.0 and x1 <= ancho
        y0, y1 = eje.get_ylim()
        assert y0 <= 0.0 and y1 == pytest.approx(r["perfiles"]["gris"]["m"]["tope"] * 1.05)
        assert not _con_etiqueta(eje, "bordes de la meseta") and not eje.patches, "sin meseta en la cuerda, ni sombreado ni bordes"

    def test_1d_una_ventana_sin_nada_de_pelicula_no_da_limites_identicos(self):
        """Una página en blanco (el escáner sin película): el tope vale 0 y `tope + 5 %` daba el límite de arriba igual al de abajo (matplotlib avisa y expande a ±0.05)."""
        blanco = np.full((900, 1200), 255, np.uint8)
        r = motor.analizar(blanco, cv2.cvtColor(blanco, cv2.COLOR_GRAY2BGR), 600.0, [(600, 300), (601, 600)])
        assert r["perfiles"]["gris"]["m"]["tope"] == 0.0 and r["perfiles"]["gris"]["estado"].startswith("no medible"), "compuerta: la ventana no tiene película"
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            figura, eje, _ = _perfil(r, "gris")
            figura.canvas.draw()
        assert [str(a.message) for a in avisos if "identical" in str(a.message)] == [], "los límites del eje y son idénticos"
        y0, y1 = eje.get_ylim()
        assert y0 == 0.0 and y1 == 1.0, (y0, y1)

    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    @pytest.mark.parametrize("perfil", PERFILES)
    def test_2_el_eje_secundario_de_arriba_esta_en_mm_desde_la_linea_con_la_escala_del_resultado(self, resultados, nombre, perfil):
        r = resultados[nombre]
        figura, eje, fila = _perfil(r, perfil)
        sec = _secundario(eje)
        assert len(sec) == 1, "el perfil no tiene su eje secundario en mm"
        figura.canvas.draw()
        x0, x1 = eje.get_xlim()
        x_linea, tam = r["x_ref"][fila], r["tamano_pixel_mm"]
        assert tam == pytest.approx(TAM)
        assert sec[0].get_xlim() == pytest.approx(((x0 - x_linea) * tam, (x1 - x_linea) * tam)), "el eje en mm no convierte con (x - línea) * mm por píxel"
        lim0, lim1 = sec[0].get_xlim()
        assert lim0 < 0 < lim1, "el 0 del eje en mm tiene que estar en la línea de referencia"
        ventana = r["parametros"]["ventana_mm"]
        assert lim0 == pytest.approx(-ventana, abs=0.6) and lim1 == pytest.approx(ventana, abs=0.6), "el eje en mm no cubre ±ventana_mm alrededor de la línea"
        assert sec[0].get_xlabel().startswith("distancia a la línea de referencia") and sec[0].get_xlabel().endswith("[mm]")
        assert eje.get_xlabel() == "columna de la ventana [px]", "el eje de abajo sigue en píxeles de la ventana"

    def test_2b_sin_escala_no_hay_eje_en_mm(self):
        r = svc.analizar_imagen(_a_300_dpi(), CLICS_PLACA_REAL)
        assert r["tamano_pixel_mm"] is None, "compuerta: una resolución 'otra' no da milímetros"
        _, eje, _ = _perfil(r, "gris")
        assert _secundario(eje) == [], "sin escala, el eje en mm sería inventado"
        assert eje.get_xlabel() == "columna de la ventana [px]"

    def test_2c_los_dos_rotulos_de_x_se_pueden_quitar_para_una_pila_de_perfiles(self, resultados):
        r = resultados["braqui_00"]
        _, eje, _ = _perfil(r, "G", eje_en_mm=False, rotulo_en_px=False)
        assert _secundario(eje) == [] and eje.get_xlabel() == ""
        _, eje_c, _ = _perfil(r, "G")
        assert len(_secundario(eje_c)) == 1 and eje_c.get_xlabel() == "columna de la ventana [px]", "por omisión, el perfil completo"
        _, eje_l, _ = _perfil(r, "G", leyenda=True, columnas_de_la_leyenda=4)
        assert eje_l.get_legend() is not None and eje_l.get_legend()._ncols == 4
        _, eje_s, _ = _perfil(r, "G")
        assert eje_s.get_legend() is None, "por omisión, sin leyenda: la conducta de siempre"

    def test_3_el_tope_se_dibuja_con_la_regla_del_umbral(self, resultados):
        r = resultados["braqui_00"]
        for perfil in PERFILES:
            _, eje, fila = _perfil(r, perfil)
            m, delta = r["perfiles"][perfil]["m"], r["parametros"]["delta"]
            assert m["umbral"] == pytest.approx(m["tope"] - delta), "compuerta: el umbral sale del tope"
            topes = [l for l in eje.lines if len(l.get_ydata()) == 2 and l.get_ydata()[0] == l.get_ydata()[1] and l.get_ydata()[0] == pytest.approx(m["tope"])]
            assert len(topes) == 1, f"{perfil}: no hay un trazo horizontal en el tope ({m['tope']:.2f})"
            assert "tope" in topes[0].get_label() and f"umbral = tope − {delta:g} niveles" in topes[0].get_label(), topes[0].get_label()
            umbral = [l for l in eje.lines if l.get_label() == "umbral de la meseta"]
            assert len(umbral) == 1 and np.allclose(umbral[0].get_ydata(), m["umbral"]), "el trazo del umbral sigue donde estaba"

    def test_3b_la_regla_dice_el_delta_con_que_se_midio_no_el_de_fabrica(self):
        r = svc.analizar_imagen(BRAQUI_00, CLICS_PLACA_REAL, {"delta": 4.0})
        assert r["parametros"]["delta"] == 4.0 and r["perfiles"]["gris"]["estado"] == "ok"
        _, eje, _ = _perfil(r, "gris")
        tope = [l for l in eje.lines if l.get_label().startswith("tope")]
        assert len(tope) == 1 and "umbral = tope − 4 niveles" in tope[0].get_label() and "2.5" not in tope[0].get_label(), tope[0].get_label()

    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    @pytest.mark.parametrize("perfil", PERFILES)
    def test_3c_los_dos_bordes_subpixel_se_dibujan_en_su_valor_del_motor_y_no_como_axvline(self, resultados, nombre, perfil):
        r = resultados[nombre]
        _, eje, fila = _perfil(r, perfil)
        m = r["perfiles"][perfil]["m"]
        assert m["inicio"][fila] >= 0, "compuerta: la cuerda tiene meseta"
        bordes = _con_etiqueta(eje, "bordes de la meseta")
        assert len(bordes) == 1, f"{perfil}: no están los dos bordes subpíxel de la meseta"
        assert np.allclose(bordes[0].get_xdata(), [m["x_izq"][fila], m["x_der"][fila]]), "los bordes no están en x_izq y x_der del motor"
        assert np.allclose(bordes[0].get_ydata(), [m["umbral"]] * 2), "los bordes se cruzan con el umbral"
        assert bordes[0].get_linestyle() in ("None", "", " "), "los bordes se marcan con símbolos, no con una línea que una los dos"
        assert not any(len(l.get_xdata()) == 2 and l.get_xdata()[0] == l.get_xdata()[1] and tuple(l.get_ydata()) == (0, 1) and l.get_label() == bordes[0].get_label() for l in eje.lines), \
            "los bordes no son un axvline: los tests 8b y 8c cuentan las verticales"

    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    def test_4_lo_que_ya_se_dibujaba_sigue_en_su_sitio(self, resultados, nombre):
        r = resultados[nombre]
        for perfil in PERFILES:
            _, eje, fila = _perfil(r, perfil)
            m = r["perfiles"][perfil]["m"]
            crudo = [l for l in eje.lines if l.get_label() == "perfil crudo"]
            filtrado = [l for l in eje.lines if l.get_label() == "perfil con filtro de mediana"]
            assert len(crudo) == 1 and np.array_equal(crudo[0].get_ydata(), r["imagenes"][perfil][fila])
            assert len(filtrado) == 1 and np.array_equal(filtrado[0].get_ydata(), m["suave"][fila])
            meseta = [p for p in eje.patches if p.get_width() > 0]
            assert len(meseta) == 1 and meseta[0].get_x() == pytest.approx(m["x_izq"][fila])
            assert meseta[0].get_x() + meseta[0].get_width() == pytest.approx(m["x_der"][fila])
            verticales = sorted(float(l.get_xdata()[0]) for l in eje.lines if len(l.get_xdata()) == 2 and l.get_xdata()[0] == l.get_xdata()[1] and tuple(l.get_ydata()) == (0, 1))
            esperadas = [r["x_ref"][fila]] + ([(m["x_izq"][fila] + m["x_der"][fila]) / 2] if r["perfiles"][perfil]["estado"] == "ok" else [])
            assert verticales == pytest.approx(sorted(esperadas)), f"{perfil}: las verticales (línea y centro) tienen que ser las de siempre"


# ============================================================ 2. la ventana dibuja las bandas del tránsito

class TestLaVentanaDibujaLasBandasDelTransito:
    def test_5_la_banda_de_braqui_00_se_dibuja_con_los_limites_del_motor(self, resultados):
        r = resultados["braqui_00"]
        d = r["contrastes_transito"]["derecha"]
        assert d is not None and r["lado_transito"] == "derecha" and r["contrastes_transito"]["izquierda"] is None, "compuerta: braqui_00 tiene la banda a la derecha y nada a la izquierda"
        _, eje, _ = _ventana(r)
        ancho = r["imagenes"]["gris"].shape[1]
        bandas = _con_etiqueta(eje, "banda de tránsito a la derecha")
        assert len(bandas) == 1, "la ventana no dibuja la banda de tránsito de la derecha"
        xy = np.asarray(bandas[0].get_xy())
        c0, c1 = d["columnas"]
        f0, f1 = d["filas_banda"]
        assert xy[:, 0].min() == pytest.approx(max(c0, 0) - 0.5) and xy[:, 0].max() == pytest.approx(min(c1, ancho) - 0.5), "la banda no está en las columnas del motor (recortada a la ventana)"
        assert xy[:, 1].min() == pytest.approx(f0 - 0.5) and xy[:, 1].max() == pytest.approx(f1 - 0.5), "la banda no está en las filas del motor"
        etiqueta = bandas[0].get_label()
        assert f"{d['desde_mm']:.1f}" in etiqueta and f"{d['hasta_mm']:.1f}" in etiqueta, "se rotula la extensión completa de la banda en mm desde el centro"
        assert f"contraste {d['contraste']:.1f}" in etiqueta and f"mínimo {r['parametros']['contraste_transito']:g}" in etiqueta, "se rotula el contraste y el mínimo que se exige"
        assert f"nivel > {r['parametros']['umbral_pelicula']:g}" in etiqueta, "se rotula que solo cuentan los píxeles de película"
        # las dos bandas de película con que se compara: arriba y abajo de la mancha, en las mismas columnas
        comparacion = [p for p in eje.patches if p.get_label().lstrip("_").startswith("película de comparación")]
        assert len(comparacion) == 2, "faltan los dos grupos de película con que se compara (arriba y abajo)"
        rangos = sorted((np.asarray(p.get_xy())[:, 1].min() + 0.5, np.asarray(p.get_xy())[:, 1].max() + 0.5) for p in comparacion)
        assert np.allclose(np.array(rangos), np.array(sorted([tuple(d["filas_arriba"]), tuple(d["filas_abajo"])]))), (rangos, d["filas_arriba"], d["filas_abajo"])
        for p in comparacion:
            xy_p = np.asarray(p.get_xy())
            assert xy_p[:, 0].min() == pytest.approx(xy[:, 0].min()) and xy_p[:, 0].max() == pytest.approx(xy[:, 0].max())

    def test_5b_el_lado_sin_banda_medible_se_rotula_y_no_se_dibuja(self, resultados):
        r = resultados["braqui_00"]
        _, eje, _ = _ventana(r)
        izquierda = _con_etiqueta(eje, "banda de tránsito a la izquierda")
        assert len(izquierda) == 1 and "no medible" in izquierda[0].get_label(), "el lado sin banda medible tiene que decirlo"
        assert len(izquierda[0].get_xdata()) == 0 and not izquierda[0].get_xdata().size, "y no se inventa una geometría que el motor no devolvió"
        assert not [p for p in eje.patches if "izquierda" in p.get_label()], "ningún polígono para el lado sin banda"

    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    def test_5c_las_bandas_no_agregan_lineas_de_mas_de_dos_puntos_ni_imagenes(self, resultados, nombre):
        r = resultados[nombre]
        for perfil in ("gris", "R"):
            _, eje, _ = _ventana(r, perfil)
            assert len(eje.images) == 1
            # la referencia, y SOLO si el perfil se mide, los bordes izquierdo y derecho y los centros (test 8d): las bandas son polígonos, no líneas
            esperadas = 1 + (3 if r["perfiles"][perfil]["estado"] == "ok" else 0)
            assert len([l for l in eje.lines if len(l.get_xdata()) > 2]) == esperadas, perfil

    def test_5d_con_leyenda_la_ventana_dice_que_es_cada_cosa_y_sin_ella_queda_como_estaba(self, resultados):
        r = resultados["braqui_00"]
        _, eje, _ = _ventana(r)
        assert eje.get_legend() is None, "por omisión la ventana no lleva leyenda (la conducta de siempre)"
        _, eje_l, _ = _ventana(r, leyenda=True)
        textos = [" ".join(t.get_text().split()) for t in eje_l.get_legend().get_texts()]       # la leyenda ajusta las etiquetas largas a varias lineas
        assert any(t.startswith("banda de tránsito a la derecha") for t in textos)
        assert any(t.startswith("banda de tránsito a la izquierda") and "no medible" in t for t in textos)
        assert "línea de referencia" in textos and len(textos) == len(set(textos)), "sin entradas repetidas"

    def test_5e_las_bandas_se_dibujan_aunque_el_perfil_de_la_ventana_sea_el_de_una_capa(self, resultados):
        r = resultados["braqui_00"]
        for capa in ("R", "G", "B"):
            _, eje, _ = _ventana(r, capa)
            assert len(_con_etiqueta(eje, "banda de tránsito a la derecha")) == 1, capa

    def test_5g_una_banda_que_cae_fuera_de_la_ventana_se_rotula_y_no_se_dibuja(self, resultados):
        """La banda va de ~12 a 50 mm del centro y la ventana solo ve ±20 mm: con un radio de mancha grande (4 radios > 20 mm) la banda empieza fuera de la ventana. Se dice, no se dibuja."""
        r = copy.deepcopy(resultados["braqui_00"])
        ancho = r["imagenes"]["gris"].shape[1]
        r["contrastes_transito"]["derecha"]["columnas"] = (ancho + 50, ancho + 400)
        _, eje, _ = _ventana(r)
        bandas = _con_etiqueta(eje, "banda de tránsito a la derecha")
        assert len(bandas) == 1 and bandas[0].get_label().endswith("(fuera de la ventana)") and len(bandas[0].get_xdata()) == 0
        assert not eje.patches, "ni la banda ni sus grupos de comparación (que comparten sus columnas)"
        # y una banda que entra en la ventana solo en parte se dibuja recortada a ella
        r["contrastes_transito"]["derecha"]["columnas"] = (ancho - 100, ancho + 400)
        _, eje_p, _ = _ventana(r)
        banda = [p for p in eje_p.patches if p.get_label().startswith("banda de tránsito a la derecha")]
        assert len(banda) == 1 and np.asarray(banda[0].get_xy())[:, 0].max() == pytest.approx(ancho - 0.5) and np.asarray(banda[0].get_xy())[:, 0].min() == pytest.approx(ancho - 100.5)

    def test_5i_en_una_pagina_entera_se_dibujan_las_dos_bandas_recortadas_a_la_ventana(self, pagina_entera):
        """Con película a los dos lados (la página entera del escáner) los dos lados son medibles: las dos bandas, cada una con su contraste, recortadas a la ventana (la izquierda sale por la
        izquierda y la derecha por la derecha) y UNA sola etiqueta para los cuatro grupos de comparación."""
        _, r = pagina_entera
        ancho = r["imagenes"]["gris"].shape[1]
        _, eje, _ = _ventana(r)
        for lado in ("izquierda", "derecha"):
            d = r["contrastes_transito"][lado]
            assert d is not None and (d["columnas"][0] < 0 or d["columnas"][1] > ancho), f"compuerta: la banda de la {lado} sale de la ventana"
            banda = [p for p in eje.patches if p.get_label().startswith(f"banda de tránsito a la {lado}")]
            assert len(banda) == 1, lado
            xy = np.asarray(banda[0].get_xy())
            assert xy[:, 0].min() == pytest.approx(max(d["columnas"][0], 0) - 0.5) and xy[:, 0].max() == pytest.approx(min(d["columnas"][1], ancho) - 0.5), lado
            assert f"contraste {d['contraste']:.1f}" in banda[0].get_label()
        assert len([p for p in eje.patches if p.get_label().lstrip("_").startswith("película de comparación")]) == 4
        assert len([p for p in eje.patches if p.get_label().startswith("película de comparación")]) == 1, "una sola etiqueta visible para los cuatro"

    def test_5h_un_grupo_de_comparacion_sin_mediana_no_se_dibuja(self, resultados):
        r = copy.deepcopy(resultados["braqui_00"])
        d = r["contrastes_transito"]["derecha"]
        d["filas_abajo"], d["abajo"] = None, None
        _, eje, _ = _ventana(r)
        comparacion = [p for p in eje.patches if p.get_label().lstrip("_").startswith("película de comparación")]
        assert len(comparacion) == 1
        assert np.asarray(comparacion[0].get_xy())[:, 1].min() + 0.5 == pytest.approx(d["filas_arriba"][0])

    def test_5f_un_resultado_sin_perfil_medible_no_dibuja_bandas(self):
        r = svc.analizar_imagen(BRAQUI_00, CLICS_NO_MEDIBLE)
        assert r["perfiles"]["gris"]["estado"].startswith("no medible") and r["contrastes_transito"] == {}, "compuerta: sin gris medible no hay detalle del tránsito"
        _, eje, _ = _ventana(r, leyenda=True)
        assert not _con_etiqueta(eje, "banda de tránsito")

    def test_5j_sin_escala_la_banda_no_rotula_milimetros_inventados(self):
        """R1-A (revisión, ronda 1). Una imagen de resolución 'otra' (300 dpi declarados) no tiene escala: el recuadro dice «sin milímetros» y el eje en mm no existe. El motor dimensiona la banda con la
        escala de reserva de 600 dpi (necesita columnas) y la ventana la rotulaba «de 12.0 a 50.0 mm del centro»: milímetros que no son los de la película (con 300 dpi reales serían 24 a 100). Un
        número que no se puede interpretar no se muestra interpretado: sin escala la extensión se rotula en píxeles desde el centro de la mancha."""
        r = svc.analizar_imagen(_a_300_dpi(), CLICS_PLACA_REAL)
        assert r["tamano_pixel_mm"] is None and r["lado_transito"] == "derecha", "compuerta: una resolución 'otra' no da milímetros y la banda está a la derecha"
        d = r["contrastes_transito"]["derecha"]
        _, eje, _ = _ventana(r)
        bandas = _con_etiqueta(eje, "banda de tránsito a la derecha")
        assert len(bandas) == 1
        etiqueta = bandas[0].get_label()
        assert not re.search(r"\d\s*mm", etiqueta), f"la etiqueta de la banda dice milímetros sin escala: {etiqueta!r}"
        assert f"de {d['desde_px']} a {d['hasta_px']} px del centro" in etiqueta and "sin escala" in etiqueta, etiqueta
        _, eje_l, _ = _ventana(r, leyenda=True)
        assert not [t.get_text() for t in eje_l.get_legend().get_texts() if re.search(r"\d\s*mm", t.get_text())], "la leyenda de la ventana no dice milímetros sin escala"

    def test_5k_en_la_pagina_con_una_imagen_de_otra_resolucion_ningun_texto_contradice_al_recuadro(self, pagina, dialogos, tmp_path):
        """R1-A por la página real (la del guion de la revisión): el recuadro dice «sin milímetros», el perfil no tiene eje en mm y la leyenda de la ventana no rotula la banda en mm."""
        ruta = tmp_path / "otra.tif"
        ruta.write_bytes(_a_300_dpi())
        _analizada(pagina, dialogos, str(ruta), CLICS_PLACA_REAL)
        assert "sin milímetros" in pagina.recuadro_gris.text(), "compuerta: la página dice que no hay milímetros"
        ventana, perfil, _barrido = pagina._fig_gris.axes          # B.4: el eje del barrido por fila va ultimo
        leyenda = [" ".join(t.get_text().split()) for t in ventana.get_legend().get_texts()]
        assert any(t.startswith("banda de tránsito a la derecha") for t in leyenda), "compuerta: la leyenda rotula la banda"
        assert not [t for t in leyenda if re.search(r"\d\s*mm", t)], f"la leyenda dice milímetros que el recuadro niega: {leyenda}"
        assert _secundario(perfil) == []


# ====================================== 3. el motor devuelve los límites de la banda (consistencia y verdad conocida)

class TestElMotorDevuelveLosLimitesDeLasBandas:
    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    def test_6_los_limites_son_la_region_sobre_la_que_se_midio_cada_mediana(self, resultados, nombre):
        """CONSISTENCIA: recalcular con las funciones públicas del motor la mediana de la película sobre EXACTAMENTE las columnas y filas devueltas tiene que dar el `banda`, `arriba` y `abajo`
        del detalle: si los límites no fueran la región medida, no darían."""
        datos, clics = IMAGENES[nombre]
        r = resultados[nombre]
        gris, color, dpi, _ = motor.leer_imagen(datos)
        P = r["parametros"]
        larga, _, _ = motor.ventana_rotada(gris, color, clics, r["angulo"], P, r["tamano_pixel_mm"], medio_ancho_mm=P["transito_hasta_mm"] + 2.0, canales=("gris",))
        ventana_std = r["imagenes"]["gris"]
        desplazamiento = (larga["gris"].shape[1] - ventana_std.shape[1]) // 2
        pelicula = larga["gris"] > P["umbral_pelicula"]
        medidos = 0
        for lado, d in r["contrastes_transito"].items():
            if d is None:
                continue
            for clave in ("columnas", "filas_banda", "filas_arriba", "filas_abajo", "desde_mm", "hasta_mm"):
                assert clave in d, f"{lado}: el detalle no trae `{clave}`"
            c0, c1 = d["columnas"]
            cols = np.arange(c0 + desplazamiento, c1 + desplazamiento)
            grupos = {"banda": np.asarray(r["perfiles"]["gris"]["filas"]), "arriba": None, "abajo": None}
            for grupo, rango in (("arriba", d["filas_arriba"]), ("abajo", d["filas_abajo"])):
                grupos[grupo] = np.arange(*rango) if rango is not None else None
            assert (d["filas_banda"][0], d["filas_banda"][1]) == (int(grupos["banda"].min()), int(grupos["banda"].max()) + 1)
            for grupo, filas in grupos.items():
                if filas is None:
                    assert d[grupo] is None, f"{lado}/{grupo}: sin límites en las filas pero con una mediana"
                    continue
                sub, msk = larga["gris"][np.ix_(filas, cols)], pelicula[np.ix_(filas, cols)]
                assert d[grupo] == float(np.median(sub[msk])), f"{lado}/{grupo}: la mediana sobre los límites devueltos no es la del detalle"
                medidos += 1
        assert medidos >= 3, "compuerta: se comprobó al menos la banda y un grupo de comparación"

    @pytest.mark.parametrize("nombre", sorted(IMAGENES))
    def test_6b_el_lado_sin_pelicula_suficiente_sigue_siendo_none_y_los_contrastes_no_cambian(self, resultados, nombre):
        r = resultados[nombre]
        assert r["lado_transito"] == "derecha" and r["contrastes_transito"]["izquierda"] is None
        d = r["contrastes_transito"]["derecha"]
        assert d["contraste"] == pytest.approx(min(d["banda"] - v for v in (d["arriba"], d["abajo"]) if v is not None))
        assert isinstance(d["columnas"][0], int) and isinstance(d["columnas"][1], int) and isinstance(d["desde_mm"], float), "tipos de Python, listos para JSON"

    def test_6c_los_milimetros_son_las_columnas_por_la_escala(self, resultados):
        r = resultados["braqui_00"]
        d = r["contrastes_transito"]["derecha"]
        c0, c1 = d["columnas"]
        assert (c1 - c0) * r["tamano_pixel_mm"] == pytest.approx(d["hasta_mm"] - d["desde_mm"], abs=1e-9)
        assert d["desde_mm"] == pytest.approx(d["desde_px"] * r["tamano_pixel_mm"]) and d["hasta_mm"] == pytest.approx(d["hasta_px"] * r["tamano_pixel_mm"]), "los mm son los px por la escala"
        assert d["hasta_px"] - d["desde_px"] == c1 - c0, "el ancho de la banda en px es el de sus columnas"
        assert d["desde_mm"] >= r["parametros"]["transito_desde_mm"] - 0.05
        assert d["hasta_mm"] <= r["parametros"]["transito_hasta_mm"] + 0.05

    def test_6d_sin_escala_el_detalle_no_da_milimetros_pero_si_las_distancias_en_pixeles(self):
        """R1-A, en el motor: `desde_mm` y `hasta_mm` salían de la escala de reserva (600 dpi) también sin escala: milímetros que nadie puede interpretar. Sin escala son None y las distancias
        al centro de la mancha se dan en píxeles (`desde_px`, `hasta_px`: las columnas «respecto del centro» que pide el plan)."""
        r = svc.analizar_imagen(_a_300_dpi(), CLICS_PLACA_REAL)
        assert r["tamano_pixel_mm"] is None, "compuerta: una resolución 'otra' no da milímetros"
        d = r["contrastes_transito"]["derecha"]
        assert d is not None and r["lado_transito"] == "derecha"
        assert d["desde_mm"] is None and d["hasta_mm"] is None, f"milímetros sin escala: {d['desde_mm']!r}, {d['hasta_mm']!r}"
        assert isinstance(d["desde_px"], int) and isinstance(d["hasta_px"], int) and 0 < d["desde_px"] < d["hasta_px"]
        assert d["hasta_px"] - d["desde_px"] == d["columnas"][1] - d["columnas"][0]

    def test_7_contra_verdad_conocida_la_banda_empieza_a_12_mm_del_centro_y_termina_a_50_por_los_dos_lados(self, pagina_entera):
        placa, r = pagina_entera
        cx, cy = placa.verdad.centro_mancha_px
        assert placa.verdad.pagina is not None and r["perfiles"]["gris"]["estado"] == "ok"
        assert r["contrastes_transito"]["izquierda"] is not None and r["contrastes_transito"]["derecha"] is not None, "compuerta: en la página entera hay película a los dos lados"
        for lado, signo in (("derecha", +1), ("izquierda", -1)):
            d = r["contrastes_transito"][lado]
            c0, c1 = d["columnas"]
            fila_c = sum(d["filas_banda"]) / 2.0 - 0.5
            x_a, _ = _de_la_ventana_a_la_imagen(r, c0 - 0.5, fila_c)
            x_b, _ = _de_la_ventana_a_la_imagen(r, c1 - 0.5, fila_c)
            borde_cercano, borde_lejano = (x_a, x_b) if signo > 0 else (x_b, x_a)
            cerca_mm, lejos_mm = signo * (borde_cercano - cx) * TAM, signo * (borde_lejano - cx) * TAM
            assert d["desde_mm"] >= 12.0 - 0.05, f"{lado}: la banda empieza a {d['desde_mm']:.2f} mm: antes de los 12 mm del plan (con el redondeo a píxeles, 11.98)"
            assert cerca_mm == pytest.approx(d["desde_mm"], abs=0.4), f"{lado}: el borde cercano está a {cerca_mm:.2f} mm del centro verdadero, el motor dice {d['desde_mm']:.2f}"
            assert lejos_mm == pytest.approx(50.0, abs=0.4), f"{lado}: el borde lejano está a {lejos_mm:.2f} mm del centro verdadero, no a 50"
            assert d["hasta_mm"] == pytest.approx(50.0, abs=0.05)
            assert d["desde_px"] == pytest.approx(signo * (borde_cercano - cx), abs=1.0) and d["hasta_px"] == pytest.approx(signo * (borde_lejano - cx), abs=1.0), \
                f"{lado}: las distancias en px ({d['desde_px']}, {d['hasta_px']}) no son las verdaderas ({signo * (borde_cercano - cx):.1f}, {signo * (borde_lejano - cx):.1f})"
            # las filas: la banda comprende al centro de la mancha, los grupos de comparación quedan arriba y abajo de ella, dentro de los clics
            f0, f1 = d["filas_banda"]
            _, y_f0 = _de_la_ventana_a_la_imagen(r, c0, f0 - 0.5)
            _, y_f1 = _de_la_ventana_a_la_imagen(r, c0, f1 - 0.5)
            assert y_f0 < cy < y_f1, f"{lado}: las filas de la banda ({y_f0:.0f} a {y_f1:.0f}) no comprenden al centro de la mancha ({cy:.0f})"
            clics_y = sorted(c[1] for c in placa.clics)
            a0, a1 = d["filas_arriba"]
            b0, b1 = d["filas_abajo"]
            _, y_a0 = _de_la_ventana_a_la_imagen(r, c0, a0 - 0.5)
            _, y_a1 = _de_la_ventana_a_la_imagen(r, c0, a1 - 0.5)
            _, y_b0 = _de_la_ventana_a_la_imagen(r, c0, b0 - 0.5)
            _, y_b1 = _de_la_ventana_a_la_imagen(r, c0, b1 - 0.5)
            assert clics_y[0] - 1.5 <= y_a0 and y_a1 < y_f0 + 1.0, f"{lado}: el grupo de arriba ({y_a0:.0f} a {y_a1:.0f}) tiene que quedar sobre la banda y bajo el clic de arriba"
            assert y_f1 - 1.0 < y_b0 and y_b1 <= clics_y[1] + 1.5 + 1.0, f"{lado}: el grupo de abajo ({y_b0:.0f} a {y_b1:.0f}) tiene que quedar bajo la banda y sobre el clic de abajo"

    def test_7b_los_limites_son_la_region_nominal_y_la_pelicula_que_hay_dentro_es_la_que_cuenta(self):
        """En un recorte (braqui_00) la banda nominal (de ~12 a 50 mm del centro) sale por la derecha de la imagen: lo que cae fuera es negro (no es película) y no cuenta. Los límites
        son la región nominal y `hasta_mm` dice 50 aunque la imagen se acabe antes: lo que decide el contraste es la película dentro de ella, y por eso el lado de la izquierda (donde no hay
        casi nada) es None."""
        datos, clics = IMAGENES["braqui_00"]
        r = svc.analizar_imagen(datos, clics)
        d = r["contrastes_transito"]["derecha"]
        gris, color, _dpi, _ = motor.leer_imagen(datos)
        P = r["parametros"]
        larga, _, _ = motor.ventana_rotada(gris, color, clics, r["angulo"], P, r["tamano_pixel_mm"], medio_ancho_mm=P["transito_hasta_mm"] + 2.0, canales=("gris",))
        desplazamiento = (larga["gris"].shape[1] - r["imagenes"]["gris"].shape[1]) // 2
        cols = np.arange(d["columnas"][0] + desplazamiento, d["columnas"][1] + desplazamiento)
        filas = np.asarray(r["perfiles"]["gris"]["filas"])
        pelicula = (larga["gris"] > P["umbral_pelicula"])[np.ix_(filas, cols)]
        assert 0.5 < pelicula.mean() < 0.97, f"compuerta: parte de la banda nominal cae fuera de la imagen ({pelicula.mean():.2f} de película), no toda"
        assert d["hasta_mm"] == pytest.approx(P["transito_hasta_mm"], abs=0.05), "los límites son los nominales, no los de la película que haya"


@pytest.fixture(scope="module")
def pagina_entera():
    """Una página entera de PF.0 (la película con el escáner alrededor): película a los dos lados de la mancha. El generador es independiente del motor y da el centro verdadero de la mancha."""
    placa = pf0.generar("fisico", "pagina_entera", -1.0)
    return placa, svc.analizar_imagen(placa.datos, [tuple(c) for c in placa.clics])


# ============================================================ 4. cada parámetro tiene su trazo o su rótulo (censo)

def _funciones(texto):
    return {n.name: n for n in ast.parse(texto).body if isinstance(n, ast.FunctionDef)}


def claves_de_P_que_entran_en_la_medida(fuentes, raices=("analizar", "medir_perfil", "resumen")):
    """Las claves `P["..."]` que leen las funciones alcanzables (por llamadas por nombre) desde las raíces, en los módulos que se pasan (texto de cada uno)."""
    definidas = {}
    for texto in fuentes:
        for nombre, nodo in _funciones(texto).items():
            definidas.setdefault(nombre, nodo)
    vistas, cola = set(), list(raices)
    while cola:
        nombre = cola.pop()
        if nombre in vistas or nombre not in definidas:
            continue
        vistas.add(nombre)
        cola += [c.func.id for c in ast.walk(definidas[nombre]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in definidas]
    claves = set()
    for nombre in vistas:
        for c in ast.walk(definidas[nombre]):
            if isinstance(c, ast.Subscript) and isinstance(c.value, ast.Name) and c.value.id in ("P", "p") and isinstance(c.slice, ast.Constant) and isinstance(c.slice.value, str):
                claves.add(c.slice.value)
    return claves, vistas


TIPOS_DE_TRAZO = {"perfil", "ventana", "eje", "recuadro", "pagina", "pie"}


@pytest.fixture(scope="module")
def trazo():
    trazo = getattr(pagina_mod, "TRAZO_DE_PARAMETRO", None)
    assert trazo is not None, "la página no declara TRAZO_DE_PARAMETRO (qué trazo o qué rótulo muestra cada parámetro de la medida)"
    return trazo


def _frase_esperada(plantilla, valor):
    """La frase del pie con el valor con que se midió (una lista, como las resoluciones de editor, se dice con comas). Es el oráculo de la prueba: no llama a la producción."""
    if isinstance(valor, (list, tuple)):
        valor = ", ".join(f"{v:g}" for v in valor)
    return plantilla.format(valor)


def parametros_sin_su_trazo_en_la_pagina(pagina, trazo):
    """[(clave, donde, etiqueta)] de cada entrada de `trazo` cuyo trazo o rótulo NO está de verdad en las figuras de la página analizada: un trazo con esa etiqueta, el eje secundario, una frase del
    pie con el valor con que se midió, el recuadro o la etiqueta de la página con ese valor (R1-E: no basta con que la etiqueta tenga algún texto)."""
    resultado = pagina._resultado
    P = resultado["parametros"]
    gris_ventana, gris_perfil, _barrido = pagina._fig_gris.axes          # B.4: el eje del barrido por fila va ultimo (en las capas tambien: zip corta en las tres capas)
    perfiles = {"gris": gris_perfil, **dict(zip("RGB", pagina._fig_rgb.axes))}
    pies = [t.get_text() for fig in (pagina._fig_gris, pagina._fig_rgb) for t in fig.texts]
    assert len(pies) == 2, "cada figura (gris y capas) lleva su pie de parámetros fijos"
    faltan = []
    for clave, (donde, etiqueta) in sorted(trazo.items()):
        valor = P[clave]
        if donde == "perfil":
            ok = all(_con_etiqueta(eje, etiqueta) for eje in perfiles.values())
        elif donde == "ventana":
            ok = bool(_con_etiqueta(gris_ventana, etiqueta))
        elif donde == "eje":                                        # una por FIGURA: el eje de arriba de la pila de las tres capas sirve a las tres (comparten el eje x)
            ok = all(any(_secundario(eje) and _secundario(eje)[0].get_xlabel().startswith(etiqueta) for eje in ejes)
                     for ejes in ([gris_perfil], list(pagina._fig_rgb.axes)))
        elif donde == "recuadro":
            ok = f"{etiqueta} {pagina_mod._tolerancia(valor)} mm" in pagina.recuadro_gris.text()
        elif donde == "pagina":                                     # la etiqueta de la página DICE el valor (no basta con que tenga algún texto)
            texto = getattr(pagina, etiqueta).text()
            ok = bool(texto) and all(f"{v:g}" in texto for v in (valor if isinstance(valor, (list, tuple)) else [valor]))
        else:                                                       # "pie": la frase con el valor con que se midió, en el pie de cada figura
            ok = all(_frase_esperada(etiqueta, valor) in pie for pie in pies)
        if not ok:
            faltan.append((clave, donde, etiqueta))
    return faltan


class TestCadaParametroTieneSuTrazoOSuRotulo:
    def test_8_el_censo_encuentra_los_parametros_de_verdad(self):
        claves, funciones = claves_de_P_que_entran_en_la_medida([MOTOR_PY.read_text(encoding="utf-8"), PELICULA_PY.read_text(encoding="utf-8")])
        assert {"medir_perfil", "mesetas_por_fila", "lado_del_transito", "ventana_rotada", "escala_mm", "interpretar"} <= funciones, f"el censo no alcanza las funciones de la medida: {sorted(funciones)}"
        assert len(claves) >= 20 and claves <= set(motor.PARAMETROS), claves ^ set(motor.PARAMETROS)

    def test_8b_cada_parametro_que_entra_en_la_medida_tiene_su_entrada(self, trazo):
        claves, _ = claves_de_P_que_entran_en_la_medida([MOTOR_PY.read_text(encoding="utf-8"), PELICULA_PY.read_text(encoding="utf-8")])
        sin_entrada = sorted(claves - set(trazo))
        assert not sin_entrada, f"parámetros que entran en la medida y no dicen qué trazo o rótulo los muestra: {sin_entrada}"

    def test_8c_ninguna_entrada_sobra_y_cada_una_declara_un_tipo_conocido(self, trazo):
        assert set(trazo) <= set(motor.PARAMETROS), f"entradas de parámetros que no existen: {sorted(set(trazo) - set(motor.PARAMETROS))}"
        assert all(isinstance(v, tuple) and len(v) == 2 and v[0] in TIPOS_DE_TRAZO and isinstance(v[1], str) and v[1] for v in trazo.values()), trazo

    def test_8d_el_censo_nombra_un_parametro_nuevo_que_nadie_dibuja(self):
        """El censo es una función pura sobre texto: con un parámetro NUEVO leído por `medir_perfil` lo encuentra (la prueba de que no pasa en vacío)."""
        fuente = MOTOR_PY.read_text(encoding="utf-8")
        ancla = 'r = {"m": m, "filas": filas, "ancho": ancho, "tope": m["tope"]}'
        assert fuente.count(ancla) == 1, "compuerta: el ancla de la fuente sintética existe una sola vez"
        claves, _ = claves_de_P_que_entran_en_la_medida([fuente.replace(ancla, ancla + '\n    r["x"] = P["parametro_nuevo"]'), PELICULA_PY.read_text(encoding="utf-8")])
        assert "parametro_nuevo" in claves
        sin_cambio, _ = claves_de_P_que_entran_en_la_medida([fuente, PELICULA_PY.read_text(encoding="utf-8")])
        assert "parametro_nuevo" not in sin_cambio

    @pytest.mark.parametrize("nombre", ["braqui_00", "EPSON009"])
    def test_8e_cada_entrada_esta_de_verdad_en_la_figura_de_la_pagina(self, trazo, pagina, dialogos, nombre):
        datos_ruta, clics = {"braqui_00": (str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL), "EPSON009": (str(DATOS / "EPSON009.jpeg"), CLICS_EPSON009)}[nombre]
        _analizada(pagina, dialogos, datos_ruta, clics)
        faltan = parametros_sin_su_trazo_en_la_pagina(pagina, trazo)
        assert not faltan, f"parámetros cuyo trazo o rótulo declarado no está en la figura de {nombre}: {faltan}"

    def test_8h_una_entrada_de_pagina_cuya_etiqueta_no_muestra_el_valor_se_nombra(self, pagina, dialogos):
        """R1-E (revisión, ronda 1). El censo daba por visibles las resoluciones de editor y la tolerancia del dpi porque su etiqueta (`etiqueta_resolucion`) tenía CUALQUIER texto: ni la lista
        (72, 96) ni el 1 % se leen ahí. La comprobación de las entradas «pagina» exige el VALOR con que se midió en el texto de la etiqueta; con la asignación débil de antes las dos se nombran."""
        _analizada(pagina, dialogos, str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL)
        debil = {**pagina_mod.TRAZO_DE_PARAMETRO, "resoluciones_de_editor_dpi": ("pagina", "etiqueta_resolucion"), "tolerancia_dpi_relativa": ("pagina", "etiqueta_resolucion")}
        assert sorted(clave for clave, _, _ in parametros_sin_su_trazo_en_la_pagina(pagina, debil)) == ["resoluciones_de_editor_dpi", "tolerancia_dpi_relativa"]

    def test_8i_el_pie_dice_las_resoluciones_de_editor_y_la_tolerancia_del_dpi_con_sus_valores(self, resultados):
        """R1-E: los dos parámetros que deciden si un dpi declarado se toma por escala (o es de un editor, o es otra resolución y no hay milímetros) se ven, con su valor, en el pie de cada figura."""
        r = resultados["braqui_00"]
        assert r["parametros"]["resoluciones_de_editor_dpi"] == [72.0, 96.0] and r["parametros"]["tolerancia_dpi_relativa"] == 0.01, "compuerta: los valores de fábrica"
        pie = pagina_mod.texto_de_parametros(r)
        assert "dpi de editor (72, 96): se usa la resolución del escaneo" in pie, pie
        assert "tolerancia del dpi declarado ±1%" in pie, pie
        r2 = copy.deepcopy(r)
        r2["parametros"]["resoluciones_de_editor_dpi"], r2["parametros"]["tolerancia_dpi_relativa"] = [72.0, 96.0, 150.0], 0.05
        pie2 = pagina_mod.texto_de_parametros(r2)
        assert "dpi de editor (72, 96, 150)" in pie2 and "±5%" in pie2, "el pie dice los valores con que se midió, también si la lista cambia de largo"

    def test_8f_el_pie_dice_los_valores_con_que_se_midio_no_los_de_fabrica(self):
        r = svc.analizar_imagen(BRAQUI_00, CLICS_PLACA_REAL, {"grosor_marco": 30, "ancho_linea": 9, "hueco_max": 12})
        assert r["perfiles"]["gris"]["estado"] == "ok" and (r["parametros"]["grosor_marco"], r["parametros"]["ancho_linea"]) == (30, 9)
        figura = Figure(layout="constrained")
        pagina_mod.rotular_parametros(figura, r)
        pie = " ".join(t.get_text() for t in figura.texts)
        assert "marco del escaneo 30 px" in pie and "franja de la línea ±9 px" in pie and "huecos de hasta 12 px" in pie
        assert "25 px" not in pie and "±7 px" not in pie and "hasta 10 px" not in pie, pie

    def test_8g_el_pie_no_pasa_de_su_largo_y_ninguna_frase_queda_partida(self, resultados):
        """El pie va en líneas de `LARGO_DEL_PIE` caracteres: más largas se saldrían de una figura angosta. Y cada frase (con su valor) está entera en UNA línea."""
        r = resultados["braqui_00"]
        lineas = pagina_mod.texto_de_parametros(r).splitlines()
        assert len(lineas) >= 3, "compuerta: el pie ocupa varias líneas"
        assert all(len(l) <= pagina_mod.LARGO_DEL_PIE for l in lineas), [len(l) for l in lineas]
        for clave, (donde, frase) in pagina_mod.TRAZO_DE_PARAMETRO.items():
            if donde == "pie":
                assert sum(_frase_esperada(frase, r["parametros"][clave]) in l for l in lineas) == 1, (clave, lineas)


# ====================================================================== 5. la página real y la pestaña sintética

class TestEnLaPaginaReal:
    @pytest.mark.parametrize("nombre", ["braqui_00", "EPSON009"])
    def test_9_las_pestanas_del_gris_y_de_las_capas_muestran_el_perfil_completo(self, pagina, dialogos, nombre):
        ruta, clics = {"braqui_00": (str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL), "EPSON009": (str(DATOS / "EPSON009.jpeg"), CLICS_EPSON009)}[nombre]
        _analizada(pagina, dialogos, ruta, clics)
        r = pagina._resultado
        ancho = r["imagenes"]["gris"].shape[1]
        ejes = {"gris": pagina._fig_gris.axes[1], **dict(zip("RGB", pagina._fig_rgb.axes))}
        assert len(pagina._fig_gris.axes) == len(pagina_mod.EJES_DE_LA_PESTANA_DEL_GRIS) == 3 and len(pagina._fig_rgb.axes) == len(pagina_mod.EJES_DE_LA_PESTANA_DE_LAS_CAPAS) == 4, \
            "el eje secundario no es un eje de la figura (B.4: gris = ventana, perfil, barrido; capas = R, G, B, barrido)"
        for perfil, eje in ejes.items():
            x0, x1 = eje.get_xlim()
            y0, y1 = eje.get_ylim()
            assert x0 <= 0 and x1 >= ancho - 1, f"{perfil}: ({x0:.1f}, {x1:.1f})"
            assert y0 <= 0.0 and y1 == pytest.approx(r["perfiles"][perfil]["m"]["tope"] * 1.05), perfil

    @pytest.mark.parametrize("nombre", ["braqui_00", "EPSON009"])
    def test_9d_las_tres_capas_comparten_el_eje_x_con_los_mm_solo_arriba_y_los_pixeles_solo_abajo(self, pagina, dialogos, nombre):
        """Repetidos en cada capa, los dos rótulos y el eje en mm dejaban cada perfil en 35 px de alto (medido en la captura): la pila comparte el eje x. OJO, es una DESVIACIÓN del texto del plan
        («el eje en mm igual en las tres capas y el gris»): esta prueba fija la estructura ([1, 0, 0]) y `test_9d2` fija que el eje de arriba es el de las tres (obstaculos.md, R1-D; vetable por el físico)."""
        ruta, clics = {"braqui_00": (str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL), "EPSON009": (str(DATOS / "EPSON009.jpeg"), CLICS_EPSON009)}[nombre]
        _analizada(pagina, dialogos, ruta, clics)
        r_, g_, b_, _barrido = pagina._fig_rgb.axes          # B.4: el cuarto eje es el barrido (su x es la posicion de la fila, no las columnas)
        assert r_.get_shared_x_axes().joined(r_, g_) and r_.get_shared_x_axes().joined(g_, b_), "las tres capas comparten el eje x"
        assert [len(_secundario(e)) for e in (r_, g_, b_)] == [1, 0, 0], "el eje en mm solo arriba"
        assert [e.get_xlabel() for e in (r_, g_, b_)] == ["", "", "columna de la ventana [px]"], "el rótulo en píxeles solo abajo"
        assert [bool(e.get_legend()) for e in (r_, g_, b_)] == [True, False, False], "la leyenda, como siempre, solo en la roja"
        ventana, perfil, _barrido = pagina._fig_gris.axes
        assert ventana.get_legend() is not None and perfil.get_legend() is not None, "la pestaña del gris lleva la leyenda de la ventana y la del perfil"
        assert [len(_secundario(perfil))] == [1] and perfil.get_xlabel() == "columna de la ventana [px]"

    @pytest.mark.parametrize("ancho,alto,con_minimos", [(1500, 1000, True), (1500, 800, False)])
    def test_9e_la_disposicion_no_colapsa_y_a_tamano_habitual_ningun_dibujo_queda_aplastado(self, pagina, dialogos, ancho, alto, con_minimos):
        """El primer diseño (el eje en mm y el rótulo en px en cada capa, la leyenda de la ventana de 110 caracteres dentro de la disposición) dejaba cada perfil de las capas en 35 px de alto y
        `constrained_layout` se rendía con «axes sizes collapsed to zero»: las aserciones sobre los límites no lo veían, la captura sí. A 1500 x 800 (una ventana baja; con la leyenda de la ventana
        DENTRO de la disposición ya colapsa a 820) la disposición no colapsa aunque los dibujos queden chicos; a 1500 x 1000 (una pantalla de escritorio) ningún eje baja de lo medido en la captura menos un margen: ventana 160 px, perfil del gris 114 px y cada
        capa 96 px (HEAD: ~170 y ~100)."""
        pagina.resize(ancho, alto)
        pagina.show()
        QApplication.processEvents()
        _analizada(pagina, dialogos, str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL)
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            for indice in (pagina_mod.PESTANA_GRIS, pagina_mod.PESTANA_RGB):
                pagina.pestanas.setCurrentIndex(indice)
                QApplication.processEvents()
                pagina.grab()
            # el botón de guardar de la barra de herramientas vuelve a componer la figura (`print_figure`), a la resolución de la figura y a una mayor: a 1500 x 800 es donde la leyenda de la
            # ventana, si entrara en la disposición, hace colapsar los ejes (en la pantalla no se ve, al guardar la imagen sí)
            for dpi in (None, 140):
                for lienzo in (pagina.lienzo_gris, pagina.lienzo_rgb):
                    lienzo.print_figure(io.BytesIO(), format="png", **({} if dpi is None else {"dpi": dpi}))
        assert [str(a.message) for a in avisos if "constrained_layout" in str(a.message)] == [], "la disposición de la figura colapsó"
        leyenda = pagina._fig_gris.axes[0].get_legend()
        assert leyenda is not None and leyenda.get_in_layout() is False, \
            "la leyenda de la ventana va fuera de la disposición (no le quita sitio a los ejes; con el alto mínimo del lienzo su efecto ya no se ve en la altura, y a 1000 px de ancho todavía quita 5 px)"
        if not con_minimos:
            return
        ventana, perfil, _barrido = pagina._fig_gris.axes          # B.4: sus alturas las mide el guardia de la disposicion (test_9g)
        alturas = {"ventana": ventana.get_window_extent().height, "perfil del gris": perfil.get_window_extent().height,
                   **{f"capa {c}": e.get_window_extent().height for c, e in zip("RGB", pagina._fig_rgb.axes)}}
        minimas = {"ventana": 120, "perfil del gris": 90, "capa R": 75, "capa G": 75, "capa B": 75}          # B.4: la pila de las capas gana el eje del barrido (cada capa 80 -> 75; medido 76)
        aplastados = {k: round(v) for k, v in alturas.items() if v < minimas[k]}
        assert not aplastados, f"dibujos aplastados (alto en px, mínimo): {aplastados} de {({k: round(v) for k, v in alturas.items()})}"
        # la ventana (la imagen es lo que se mira) es más alta que el perfil, que vive cerca del tope y deja vacía la mitad de abajo: 1.4 : 1 (con 1 : 1 serían iguales)
        assert alturas["ventana"] >= 1.2 * alturas["perfil del gris"], {k: round(v) for k, v in alturas.items()}

    @pytest.mark.parametrize("nombre", ["braqui_00", "EPSON009"])
    def test_9d2_el_eje_en_mm_de_arriba_de_la_pila_es_el_de_las_tres_capas(self, pagina, dialogos, nombre):
        """R1-D (revisión, ronda 1). El plan pide el eje en mm «igual en las tres capas y el gris»; en la página solo la capa roja lo dibuja (la pila comparte el eje x: repetido, cada perfil quedaba en
        35 px). Es el MISMO eje: las tres capas comparten límites y la línea de referencia está en el mismo x de las tres (la fila y la línea son de la ventana, no de la capa), así que el 0 y los mm de
        arriba valen para G y B. Esta prueba fija esa equivalencia (lo que el plan quiere) y no solo `[1, 0, 0]`. Repetirlo en cada capa es `eje_en_mm=True` en la llamada de `_mostrar` (una línea),
        a cambio de unos 45 px por capa. DECISIÓN DE DISEÑO DEL IMPLEMENTADOR, VETABLE POR EL FÍSICO (obstaculos.md, ítem 7 y R1-D)."""
        ruta, clics = {"braqui_00": (str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL), "EPSON009": (str(DATOS / "EPSON009.jpeg"), CLICS_EPSON009)}[nombre]
        _analizada(pagina, dialogos, ruta, clics)
        r = pagina._resultado
        fila = pagina_mod.fila_representativa(r, "gris")
        x_linea, tam = float(r["x_ref"][fila]), r["tamano_pixel_mm"]
        pagina.pestanas.setCurrentIndex(pagina_mod.PESTANA_RGB)
        pagina.lienzo_rgb.draw()
        capas = dict(zip("RGB", pagina._fig_rgb.axes))
        mm = _secundario(capas["R"])[0]
        assert capas["R"].get_xlim() == capas["G"].get_xlim() == capas["B"].get_xlim(), "las tres capas comparten el eje x"
        for capa, eje in capas.items():
            x0, x1 = eje.get_xlim()
            assert mm.get_xlim() == pytest.approx(((x0 - x_linea) * tam, (x1 - x_linea) * tam)), f"el eje en mm de arriba no convierte los x de la capa {capa}"
            linea = [l for l in eje.lines if l.get_label() == "línea de referencia"]
            assert len(linea) == 1 and float(linea[0].get_xdata()[0]) == pytest.approx(x_linea), f"la línea de referencia de la capa {capa} no está en el 0 del eje en mm"

    @pytest.mark.parametrize("alto", [650, 700, 750, 800])
    def test_9f_en_una_pagina_baja_ningun_dibujo_queda_aplastado_ni_colapsa_la_disposicion(self, fabrica, dialogos, alto):
        """R1-B (revisión, ronda 1). Lo fijo de cada figura (el eje en mm de arriba, los títulos, los rótulos y el pie de parámetros: unos 210 px) no depende de la altura de la página y los ejes se
        reparten lo que sobra: con una página de 750 px de alto el lienzo mide 218 px y los ejes del gris medían 6 y 4 px (HEAD: 46 y 46; con 700 la disposición colapsaba también en el gris). El
        lienzo tiene un alto mínimo y, por debajo, se desplaza en vez de aplastarse. La guarda de test_9e solo miraba el aviso de colapso y por eso pasaba a 800 sin ver ejes de 6 px a 750."""
        pagina = fabrica()
        pagina.resize(1500, alto)
        pagina.show()
        QApplication.processEvents()
        _analizada(pagina, dialogos, str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL)
        alturas = {}
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            for indice, lienzo, figura, nombres in ((pagina_mod.PESTANA_GRIS, pagina.lienzo_gris, pagina._fig_gris, ("ventana", "perfil del gris", "barrido del gris")),
                                                    (pagina_mod.PESTANA_RGB, pagina.lienzo_rgb, pagina._fig_rgb, ("capa R", "capa G", "capa B", "barrido de las capas"))):
                pagina.pestanas.setCurrentIndex(indice)
                QApplication.processEvents()
                lienzo.draw()
                pagina.grab()
                alturas.update({n: e.get_window_extent().height for n, e in zip(nombres, figura.axes)})
        assert [str(a.message) for a in avisos if "constrained_layout" in str(a.message)] == [], "la disposición de la figura colapsó"
        pisos = {"ventana": 70, "perfil del gris": 50, "capa R": 50, "capa G": 50, "capa B": 50, "barrido del gris": 50, "barrido de las capas": 50}      # B.4: los dos ejes del barrido tambien
        assert set(alturas) == set(pisos), "compuerta: se midieron los siete ejes"
        aplastados = {k: round(v) for k, v in alturas.items() if v < pisos[k]}
        assert not aplastados, f"a {alto} px de alto de página, dibujos aplastados (alto en px, piso {pisos}): {aplastados} de {({k: round(v) for k, v in alturas.items()})}"

    @pytest.mark.parametrize("alto", [650, 700, 750])
    def test_9i_la_pestana_sintetica_tampoco_se_aplasta_en_una_pagina_baja(self, fabrica, dialogos, alto):
        """R1-B en la pestaña sintética (misma causa, medida al corregir: con 750 de página sus ejes de la izquierda bajaban de 83 px a 42 y con 650 la disposición colapsaba, HEAD no)."""
        pagina = fabrica()
        pagina.resize(1500, alto)
        pagina.show()
        QApplication.processEvents()
        sintetica = pagina.sintetica
        sintetica._barrido = ((2.2, 1.1, 0.5), [(-1.0, -1.0), (0.0, 0.0), (1.0, 1.0)])      # el barrido es lo caro (unos segundos): la forma por omisión de los deslizadores
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            pagina.pestanas.setCurrentIndex(pagina_mod.PESTANA_SINTETICA)                  # la primera vez que se abre calcula la placa sintética
            QApplication.processEvents()
            assert sintetica.calculada, "compuerta: la pestaña calculó"
            sintetica.lienzo.draw()
            pagina.grab()
        assert [str(a.message) for a in avisos if "constrained_layout" in str(a.message)] == [], "la disposición de la figura colapsó"
        ventana, perfil, _ = sintetica.figura.axes
        alturas = {"ventana": ventana.get_window_extent().height, "perfil": perfil.get_window_extent().height}
        pisos = {"ventana": 70, "perfil": 50}
        aplastados = {k: round(v) for k, v in alturas.items() if v < pisos[k]}
        assert not aplastados, f"a {alto} px de alto de página, dibujos aplastados (alto en px, piso {pisos}): {aplastados} de { {k: round(v) for k, v in alturas.items()} }"

    def test_9g_el_alto_minimo_del_lienzo_se_desplaza_sin_agrandar_la_pagina_ni_esconder_el_resultado(self, fabrica, dialogos):
        """El alto mínimo del lienzo (R1-B) vive en un área de desplazamiento: sin ella el mínimo agrandaría el alto mínimo de la página (588 px antes de la corrección) y la ventana principal
        crecería más que una pantalla pequeña. El recuadro del resultado queda FUERA del área (siempre a la vista) y, con una página alta, el lienzo llena el área y no hay barra."""
        pagina = fabrica()
        assert pagina.minimumSizeHint().height() <= 600, "el alto mínimo del lienzo agranda el alto mínimo de la página (588 px antes de la corrección)"
        assert _area_de(pagina.lienzo_imagen) is None, "la pestaña Imagen (la de marcar los puntos, que B.1 no toca) sigue como siempre: sin alto mínimo ni área de desplazamiento"
        pagina.resize(1500, 650)
        pagina.show()
        QApplication.processEvents()
        _analizada(pagina, dialogos, str(DATOS / "braqui_00.jpeg"), CLICS_PLACA_REAL)
        casos = ((pagina_mod.PESTANA_GRIS, pagina.lienzo_gris, pagina.recuadro_gris, 340), (pagina_mod.PESTANA_RGB, pagina.lienzo_rgb, pagina.recuadro_rgb, 380),
                 (pagina_mod.PESTANA_SINTETICA, pagina.sintetica.lienzo, pagina.sintetica.recuadro, 380))
        pagina.sintetica._barrido = ((2.2, 1.1, 0.5), [(-1.0, -1.0), (0.0, 0.0), (1.0, 1.0)])
        for indice, lienzo, recuadro, minimo in casos:
            pagina.pestanas.setCurrentIndex(indice)
            QApplication.processEvents()
            area = _area_de(lienzo)
            assert area is not None, f"el lienzo de la pestaña {indice} no está en un área de desplazamiento"
            assert lienzo.height() >= minimo and area.verticalScrollBar().maximum() > 0, f"con una página baja el lienzo ({lienzo.height()} px) se desplaza (mínimo {minimo})"
            assert not area.isAncestorOf(recuadro), "el recuadro del resultado queda dentro del área que se desplaza"
        pagina.resize(1500, 1300)
        QApplication.processEvents()
        for indice, lienzo, _, _ in casos:
            pagina.pestanas.setCurrentIndex(indice)
            QApplication.processEvents()
            area = _area_de(lienzo)
            assert area.verticalScrollBar().maximum() == 0 and lienzo.height() == area.viewport().height(), f"pestaña {indice}: con una página alta el lienzo llena el área y no hay barra"

    def test_9b_limpiar_y_recalcular_dejan_las_figuras_sin_pies_ni_ejes_de_la_imagen_anterior(self, pagina, dialogos, archivo_braqui):
        _analizada(pagina, dialogos, archivo_braqui)
        assert pagina._fig_gris.texts and pagina._fig_rgb.texts
        pagina.boton_recalcular.click()
        assert not pagina._fig_gris.texts and not pagina._fig_rgb.texts and not pagina._fig_gris.axes and not pagina._fig_rgb.axes

    def test_9c_la_pestana_sintetica_dibuja_lo_mismo(self, pagina):
        """La sintética comparte `dibujar_ventana` y `dibujar_perfil`: lo que cambia aquí tiene que verse también allí."""
        sintetica = pagina.sintetica
        p = {"desfase_mm": -0.6, "ancho_x_mm": 2.2, "ancho_y_mm": 1.1, "saturacion": 0.5}
        resultado = pagina_mod.analizar_sintetica(p)
        sintetica._descartar()
        sintetica._mostrar(p, resultado, [(-1.0, -1.0), (0.0, 0.0), (1.0, 1.0)])
        ventana, perfil, barrido = sintetica.figura.axes
        ancho = resultado["imagenes"]["gris"].shape[1]
        x0, x1 = perfil.get_xlim()
        assert x0 <= 0 and x1 >= ancho - 1 and len(_secundario(perfil)) == 1
        assert _con_etiqueta(perfil, "tope") and _con_etiqueta(perfil, "bordes de la meseta")
        assert [t.get_text() for t in sintetica.figura.texts], "la pestaña sintética también lleva el pie de parámetros fijos"
