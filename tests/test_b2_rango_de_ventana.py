"""B.2 (PLAN_HANDOFF_IMAGENES_22-09.md): el rango de los deslizadores de nivel (WL) y ventana (WW) sale del volumen.

CAUSA: el visor fijaba `setRange(-1000, 500)` y `setRange(1, 2000)` y arrancaba siempre en 40/400. El volumen del OBI del
iX vive en ≈ +490 HU: quedaba fuera del rango (el físico "tiene que dejarlo en el límite de 500", anotación 2) y la
imagen arrancaba saturada en blanco. Cada serie trae su propia ventana razonable (iX 402/364, Halcyon -21/144, tomógrafo
40/200) y el programa la ignoraba.

Lo que este archivo garantiza:
  1. LA VENTANA DEL DICOM se lee de las seis series reales, y lo que no tiene sentido no se toma (multivalor: la
     primera; ancho no positivo, texto o vacío: ninguna).
  2. EL RANGO cubre el volumen: contiene el nivel del DICOM, la extensión robusta [p0.1, p99.9] del volumen y un margen,
     no es nunca menor que el de antes, llega a +1000 en el iX (la pregunta literal del físico) y NO persigue los pocos
     vóxeles de artefacto (el Halcyon llega a 7000 HU, una carpeta mixta a 30318).
  3. EL VISOR lo aplica al cargar una carpeta real: rango, valor inicial, rótulos y ayuda; una segunda carga lo vuelve a
     derivar; y la imagen del iX ya no arranca saturada.
  4. ESTRUCTURA -- se aplica después de confirmar la carga y antes de dibujar, y no queda ningún número escrito en los
     rangos de los deslizadores del visor.
"""
import ast
import os
import pathlib
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from analisisImagenes.catphan import ventana as ventana_mod
from analisisImagenes.catphan.serie import leer_serie, ventana_de_serie
from analisisImagenes.catphan.ventana import (
    WL_MAX_ANTERIOR, WL_MIN_ANTERIOR, WW_MAX_ANTERIOR, rango_de_ventana)
from data.ManejoDatos.catphan_TAC import leer_dicom as leer_dicom_mod
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume
from _corpus import CATPHAN, serie_catphan

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LEER_DICOM = RAIZ / "data" / "ManejoDatos" / "catphan_TAC" / "leer_dicom.py"

# Lo que trae el propio DICOM de cada serie (WindowCenter, WindowWidth) [medido 25-09].
VENTANA_DICOM = {
    "TOMOGRAFO": (40, 200), "HALCYON_SEP": (-21, 144), "HALCYON_JUN": (-18, 279),
    "HALCYON_236": (-61, 440), "IX_DIC": (402, 364), "MIXTA": (40, 200),
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


_CACHE = {}


def _datos(clave):
    """Lo que las pruebas necesitan de una serie real, calculado UNA vez y sin conservar el volumen (los seis pesan
    cientos de MB): la ventana del DICOM, el rango derivado y los estadísticos del volumen COMPLETO."""
    if clave not in _CACHE:
        ruta = _requerir(clave)
        ventana = ventana_de_serie(leer_serie(ruta))              # del encabezado, sin pasar por el visor
        v = DicomVolume(ruta).volumen_hu
        bajo, alto = np.percentile(v, [0.1, 99.9])
        _CACHE[clave] = types.SimpleNamespace(
            ventana=ventana, rango=rango_de_ventana(v, ventana),
            p_bajo=float(bajo), p_alto=float(alto), minimo=float(v.min()), maximo=float(v.max()))
    return _CACHE[clave]


CLAVES = sorted(CATPHAN)


# ---------------------------------------------------------------------------
# 1. LA VENTANA DEL DICOM
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", CLAVES)
def test_las_seis_series_traen_su_ventana_y_se_lee_la_del_dicom(clave):
    assert _datos(clave).ventana == pytest.approx(VENTANA_DICOM[clave])


@pytest.mark.parametrize("clave", CLAVES)
def test_el_volumen_lleva_la_ventana_de_su_serie(clave):
    """`DicomVolume` la expone: el visor la lee de ahí y no vuelve a abrir los archivos."""
    ruta = _requerir(clave)
    assert DicomVolume(ruta).ventana_dicom == ventana_de_serie(leer_serie(ruta))


def _serie_con(**etiquetas):
    return types.SimpleNamespace(etiquetas=etiquetas)


def test_una_ventana_multivalor_toma_el_primer_par():
    from pydicom.multival import MultiValue
    from pydicom.valuerep import DSfloat
    a = MultiValue(DSfloat, [DSfloat("40"), DSfloat("400")])
    b = MultiValue(DSfloat, [DSfloat("200"), DSfloat("2000")])
    assert ventana_de_serie(_serie_con(WindowCenter=a, WindowWidth=b)) == (40.0, 200.0)


@pytest.mark.parametrize("etiquetas", [
    {},                                                                # no la trae
    {"WindowCenter": 40},                                              # solo el nivel
    {"WindowWidth": 200},                                              # solo el ancho
    {"WindowCenter": 40, "WindowWidth": 0},                            # ancho cero
    {"WindowCenter": 40, "WindowWidth": -100},                         # ancho negativo
    {"WindowCenter": "basura", "WindowWidth": 200},                    # no es un número
    {"WindowCenter": 40, "WindowWidth": float("nan")},                 # no es finito
    {"WindowCenter": float("inf"), "WindowWidth": 200},
    {"WindowCenter": None, "WindowWidth": None},
    {"WindowCenter": [], "WindowWidth": []},                           # multivalor vacío
])
def test_una_ventana_que_no_tiene_sentido_no_se_toma(etiquetas):
    assert ventana_de_serie(_serie_con(**etiquetas)) is None


# ---------------------------------------------------------------------------
# 2. EL RANGO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", CLAVES)
def test_el_rango_contiene_el_nivel_del_dicom_y_arranca_en_su_ventana(clave):
    d = _datos(clave)
    wc, ww = VENTANA_DICOM[clave]
    assert d.rango.wl_min <= wc <= d.rango.wl_max
    assert (d.rango.wl_inicial, d.rango.ww_inicial) == (wc, ww)
    assert d.rango.origen_inicial == "dicom"


@pytest.mark.parametrize("clave", CLAVES)
def test_el_rango_cubre_la_extension_del_volumen_completo(clave):
    """[p0.1, p99.9] medidos sobre el volumen COMPLETO (la regla mide una muestra: el margen absorbe la diferencia), y
    existe una ventana que la abarca entera con los dos deslizadores."""
    d, r = _datos(clave), _datos(clave).rango
    assert r.wl_min <= d.p_bajo and d.p_alto <= r.wl_max
    centro, ancho = (d.p_bajo + d.p_alto) / 2, d.p_alto - d.p_bajo
    assert r.wl_min <= centro <= r.wl_max and 1 <= ancho <= r.ww_max


@pytest.mark.parametrize("clave", CLAVES)
def test_el_rango_nunca_es_menor_que_el_de_antes(clave):
    r = _datos(clave).rango
    assert r.wl_min <= WL_MIN_ANTERIOR and r.wl_max >= WL_MAX_ANTERIOR and r.ww_max >= WW_MAX_ANTERIOR
    assert 1 <= r.ww_inicial <= r.ww_max and r.wl_min <= r.wl_inicial <= r.wl_max


def test_el_ix_llega_a_mas_de_1000_que_era_la_pregunta_del_fisico():
    """Anotación 2: *"¿se puede ampliar el rango de WL hacia +1000?"*. El iX lo pide (su fondo está en +490); sale del
    volumen, no de una constante."""
    r = _datos("IX_DIC").rango
    assert r.wl_max >= 1000
    assert r.wl_max > _datos("HALCYON_SEP").rango.wl_max >= _datos("TOMOGRAFO").rango.wl_max


@pytest.mark.parametrize("clave", ["HALCYON_SEP", "MIXTA"])
def test_los_vóxeles_de_artefacto_no_arrastran_el_rango(clave):
    """El Halcyon llega a 7000 HU y la carpeta mixta a 30318 en menos del 0.03 % del volumen: un deslizador hasta ahí
    tendría decenas de HU por píxel. La extensión es la robusta, no el máximo."""
    d = _datos(clave)
    assert d.maximo > 5000
    assert d.rango.wl_max < 1500 and d.rango.ww_max < 3000


def _sintetico(fondo=0.0, forma=(20, 64, 64), seed=0):
    rng = np.random.default_rng(seed)
    v = rng.normal(fondo, 30.0, forma).astype(np.float32)
    v[: forma[0] // 2] += 900.0                                # hay algo de contraste
    v[0, 0, :3] = -1000.0                                      # y aire
    return v


def test_un_extremo_aislado_no_arrastra_el_rango():
    """El 0.02 % de los vóxeles en 30000 HU (metal, artefacto de borde) no mueve el rango: sin este control, un
    deslizador hasta el máximo absoluto tendría cientos de HU por píxel."""
    v = _sintetico()
    v.reshape(-1)[: int(v.size * 0.0002)] = 30000.0
    r = rango_de_ventana(v, None)
    assert r.wl_max < 2500 and r.ww_max < 4000


def test_un_volumen_muy_por_encima_amplia_el_rango():
    v = _sintetico(fondo=3000.0)
    r = rango_de_ventana(v, None)
    assert r.wl_max >= 3900 and r.ww_max >= r.wl_max - r.wl_min


def test_un_volumen_muy_por_debajo_amplia_el_rango():
    v = _sintetico(fondo=-4000.0)
    r = rango_de_ventana(v, None)
    assert r.wl_min <= -4000


def test_un_nivel_de_dicom_fuera_del_volumen_igual_queda_dentro():
    r = rango_de_ventana(_sintetico(), (5000.0, 300.0))
    assert r.wl_max >= 5000 and r.wl_inicial == 5000


def test_sin_ventana_de_dicom_arranca_donde_arrancaba_antes():
    r = rango_de_ventana(_sintetico(), None)
    assert (r.wl_inicial, r.ww_inicial, r.origen_inicial) == (
        ventana_mod.WL_INICIAL_ANTERIOR, ventana_mod.WW_INICIAL_ANTERIOR, "predeterminada")


def test_un_ancho_de_dicom_fuera_de_rango_se_acota_al_rango():
    r = rango_de_ventana(_sintetico(), (40.0, 50000.0))
    assert r.ww_inicial == r.ww_max
    r = rango_de_ventana(_sintetico(), (40.0, 0.2))
    assert r.ww_inicial == 1


@pytest.mark.parametrize("volumen", [np.zeros((0, 4, 4), np.float32), np.full((3, 4, 4), np.nan, np.float32)])
def test_un_volumen_que_no_se_puede_medir_deja_el_rango_de_antes(volumen):
    r = rango_de_ventana(volumen, None)
    assert (r.wl_min, r.wl_max, r.ww_max) == (WL_MIN_ANTERIOR, WL_MAX_ANTERIOR, WW_MAX_ANTERIOR)


def test_una_imagen_2d_tambien_se_mide():
    r = rango_de_ventana(_sintetico()[0], None)
    assert r.wl_min <= WL_MIN_ANTERIOR and r.wl_max >= WL_MAX_ANTERIOR


def test_el_rango_es_de_enteros_porque_los_deslizadores_lo_son():
    r = _datos("IX_DIC").rango
    assert all(isinstance(x, int) for x in (r.wl_min, r.wl_max, r.ww_max, r.wl_inicial, r.ww_inicial))


# ---------------------------------------------------------------------------
# 3. EL VISOR, CON UNA CARPETA REAL
# ---------------------------------------------------------------------------

def _visualizador():
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    mpl = get_matplotlib_components()
    canvas = mpl["FigureCanvas"](mpl["Figure"](figsize=(4, 4)))
    return leer_dicom_mod.VisualizadorDicom(target_canvas=canvas)


@pytest.fixture
def visualizador(app, monkeypatch):
    """El visor real, con la detección de módulos (pylinac, que tiene sus propias pruebas) y el cuadro de cortes
    sustituidos: lo que se prueba es la ventana. La confirmación de A.3 se acepta sin persona."""
    monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", lambda ruta_dicom: ({}, {}))
    v = _visualizador()
    monkeypatch.setattr(v, "mostrar_popup_cortes", lambda resultados: None)
    v.confirmador_de_carga = lambda parent, vol, equipo: True
    return v


def test_el_visor_arranca_con_el_rango_de_antes_y_sin_carpeta(visualizador):
    assert (visualizador.slider_wl.minimum(), visualizador.slider_wl.maximum()) == (WL_MIN_ANTERIOR, WL_MAX_ANTERIOR)
    assert (visualizador.slider_ww.minimum(), visualizador.slider_ww.maximum()) == (1, WW_MAX_ANTERIOR)
    assert (visualizador.slider_wl.value(), visualizador.slider_ww.value()) == (
        ventana_mod.WL_INICIAL_ANTERIOR, ventana_mod.WW_INICIAL_ANTERIOR)


@pytest.mark.parametrize("clave", ["IX_DIC", "HALCYON_SEP", "TOMOGRAFO"])
def test_al_cargar_una_carpeta_los_deslizadores_toman_su_rango_y_su_ventana(visualizador, clave):
    visualizador.visualizar_imagen_cargada(_requerir(clave))
    r, wc, ww = _datos(clave).rango, *VENTANA_DICOM[clave]
    assert (visualizador.slider_wl.minimum(), visualizador.slider_wl.maximum()) == (r.wl_min, r.wl_max)
    assert (visualizador.slider_ww.minimum(), visualizador.slider_ww.maximum()) == (1, r.ww_max)
    assert (visualizador.slider_wl.value(), visualizador.slider_ww.value()) == (wc, ww)
    # los rótulos dicen el número, no solo la posición del deslizador
    assert visualizador.slider_wl_label.text() == f"Nivel (brillo): {wc}"
    assert visualizador.slider_ww_label.text() == f"Ventana (contraste): {ww}"
    # y la ayuda dice de dónde sale el rango y el valor inicial
    ayuda = visualizador.slider_wl.toolTip()
    assert f"{r.wl_min} a {r.wl_max}" in ayuda and "ventana del DICOM" in ayuda and f"{wc} / {ww}" in ayuda
    assert f"1 a {r.ww_max}" in visualizador.slider_ww.toolTip()


def test_una_segunda_carpeta_vuelve_a_derivar_el_rango(visualizador):
    visualizador.visualizar_imagen_cargada(_requerir("HALCYON_SEP"))
    primero = (visualizador.slider_wl.maximum(), visualizador.slider_wl.value())
    visualizador.visualizar_imagen_cargada(_requerir("IX_DIC"))
    segundo = (visualizador.slider_wl.maximum(), visualizador.slider_wl.value())
    assert primero == (_datos("HALCYON_SEP").rango.wl_max, -21)
    assert segundo == (_datos("IX_DIC").rango.wl_max, 402) and segundo != primero


def test_ajustar_la_ventana_no_dispara_un_redibujado_por_su_cuenta(visualizador):
    """No es un cambio del físico: sin señales, así no se encola un redibujado más (lo hace `actualizar_ventana`)."""
    visualizador.visualizar_imagen_cargada(_requerir("IX_DIC"))
    visualizador.slider_wl.setValue(0)                          # el físico movió los deslizadores...
    visualizador.slider_ww.setValue(100)
    visualizador._pending_update = False                        # ...y ya se atendió
    visualizador._debounce_timer.stop()
    visualizador._ajustar_ventana_al_volumen()                  # los valores CAMBIAN de 0/100 al de la ventana del DICOM
    assert (visualizador.slider_wl.value(), visualizador.slider_ww.value()) == VENTANA_DICOM["IX_DIC"]
    assert visualizador._pending_update is False and not visualizador._debounce_timer.isActive()


def test_el_valor_inicial_puede_caer_fuera_del_rango_de_antes(visualizador):
    """Un equipo cuya escala vive muy por encima (nivel 3000): el deslizador arranca en 3000, no acotado al 500 de
    antes. Exige fijar el rango ANTES que el valor."""
    visualizador.vol = types.SimpleNamespace(volumen_hu=_sintetico(fondo=3000.0), ventana_dicom=(3000.0, 300.0))
    visualizador._ajustar_ventana_al_volumen()
    assert visualizador.slider_wl.value() == 3000 and visualizador.slider_wl.maximum() >= 3900
    assert visualizador.slider_ww.value() == 300


def test_la_imagen_del_ix_ya_no_arranca_saturada(visualizador):
    """La razón por la que el iX "se veía mal": con 40/400 su fondo (+490) queda por encima de la ventana y el
    fantoma entero es blanco puro. Con la ventana del propio DICOM el interior tiene tonos."""
    visualizador.visualizar_imagen_cargada(_requerir("IX_DIC"))
    vol = visualizador.vol
    z = vol.get_num_cortes() // 2
    cuerpo = (slice(150, 200), slice(150, 200))         # material del fantoma, sin insertos [medido]

    def saturado(wl, ww):
        norm = vol.get_corte_normalizado(z, wl - ww / 2, wl + ww / 2)
        return float(np.mean(np.asarray(norm)[cuerpo] == 255))

    assert saturado(ventana_mod.WL_INICIAL_ANTERIOR, ventana_mod.WW_INICIAL_ANTERIOR) > 0.95     # antes: blanco puro
    assert saturado(visualizador.slider_wl.value(), visualizador.slider_ww.value()) < 0.10         # ahora: con tonos


# ---------------------------------------------------------------------------
# 4. ESTRUCTURA
# ---------------------------------------------------------------------------

def _funcion(nombre):
    arbol = ast.parse(LEER_DICOM.read_text(encoding="utf-8"))
    (f,) = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == nombre]
    return f


def _linea_de_llamada(func, nombre):
    lineas = [n.lineno for n in ast.walk(func) if isinstance(n, ast.Call)
              and getattr(n.func, "attr", getattr(n.func, "id", None)) == nombre]
    return min(lineas) if lineas else None


def test_la_ventana_se_ajusta_despues_de_confirmar_y_antes_de_dibujar():
    f = _funcion("visualizar_imagen_cargada")
    confirmar = _linea_de_llamada(f, "confirmador_de_carga")
    ajustar = _linea_de_llamada(f, "_ajustar_ventana_al_volumen")
    dibujar = _linea_de_llamada(f, "actualizar_ventana")
    assert None not in (confirmar, ajustar, dibujar)
    assert confirmar < ajustar < dibujar


def test_ningun_rango_de_los_deslizadores_de_ventana_lleva_un_numero_escrito():
    """Los `setRange` de WL y WW salen de `ventana.py`: ni el rango de antes ni el de después se escriben en el visor.
    (El del deslizador de cortes es otro asunto: se fija con el número de cortes del volumen.)"""
    arbol = ast.parse(LEER_DICOM.read_text(encoding="utf-8"))
    sueltos = []
    for n in ast.walk(arbol):
        if (isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "setRange"
                and isinstance(n.func.value, ast.Attribute) and n.func.value.attr in ("slider_wl", "slider_ww")):
            for a in n.args:
                if isinstance(a, ast.Constant) and a.value not in (1,):        # el mínimo del ancho es 1: no hay ancho 0
                    sueltos.append((n.lineno, n.func.value.attr, a.value))
    assert not sueltos, sueltos
