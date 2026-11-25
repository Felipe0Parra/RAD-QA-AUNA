"""AJ.5 (PLAN_AJUSTES_MENSUAL_CATPHAN_24-11.md): los ROI de Valores CT se ven del mismo color en la pantalla y en el PDF, y en verde los que estan en su rango.

Pregunta del fisico (24-11): «Decirme porque a veces aparece rojo, a veces Azul, a veces combinado con algunos verde los rois de la prueba de valores ct del catphan.»
Dos causas (H14 del plan): la regla `verde si error_abs and error_abs <= 20` contaba el 0.0 de un material DENTRO de su rango como falso (rojo), y la pestana mostraba la imagen en el orden
de canales de OpenCV (azul, verde, rojo) sin convertir, mientras que lo guardado (`cv2.imencode`) si respeta el orden: el mismo ROI se veia azul en vivo y rojo en el PDF.

Lo que se fija, con un corte sintetico de HU conocidos (la verdad: los HU que pone la prueba y su distancia al rango, calculada aqui):
1. El anillo y el texto de cada material: verde si su HU esta dentro de su rango o a 20 [HU] o menos (el cero incluido), rojo si esta mas lejos, gris si no hay valor medido.
2. Valores CT, espesor, tamano de pixel y contraste muestran en la pestana (y sin pestana) exactamente la imagen que se guarda, y espesor, tamano de pixel y contraste la guardan con
   los mismos colores que antes; la uniformidad se ve como hoy (AJ5-D2).
3. Los numeros no cambian; el circulo interior y el contorno del fantoma tampoco.
Trampa 1: `offscreen` antes de PyQt5. Sin dialogos: las funciones de analisis no abren ninguno; `plt.show` se parcha en la rama sin pestana.
"""
import ast
import contextlib
import io
import os
import warnings
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image
from PyQt5.QtWidgets import QApplication

RAIZ = Path(__file__).resolve().parent.parent
ANALISIS_PY = RAIZ / "analisisImagenes" / "Analisis_Catphan_TAC.py"
TAM, N = 0.5, 512
RGB_VERDE, RGB_ROJO, RGB_GRIS = (0, 255, 0), (255, 0, 0), (128, 128, 128)
# colores (rojo, verde, azul) que ya se guardaban con este corte: negro, contorno del fantoma (60, 60, 141), circulos de fondo (0, 255, 255) y el color de cada ROI
GUARDADOS = {"espesor": {(0, 0, 0), (60, 60, 141), RGB_ROJO}, "tamano_pixel": {(0, 0, 0), (60, 60, 141), RGB_VERDE}, "contraste": {(0, 0, 0), (60, 60, 141), (0, 255, 255), RGB_ROJO}}

# rango de cada material (copia literal de la tabla de `valor_numero_ct`; la prueba comprueba que no cambio) y el HU que se le pone
RANGOS = {"Teflon": (941, 1060), "Delrin": (344, 387), "Acrilico": (92, 137), "Poliestireno": (-65, -29), "LDPE": (-121, -87), "PMP": (-220, -172), "Aire": (-1046, -986)}
HU_PUESTO = {
    "Teflon": 1000.0,        # dentro del rango (el 0.0 que hoy sale rojo)
    "Delrin": 397.0,         # 10 [HU] fuera
    "Acrilico": 197.0,       # 60 [HU] fuera
    "Poliestireno": -85.0,   # 20 [HU] fuera: el limite, verde
    "LDPE": -141.001,        # 20.001 [HU] fuera (el error se redondea a 3 decimales): rojo
    "PMP": -172.0,           # justo en el borde del rango: dentro
    "Aire": -1000.0,         # dentro
}


def _distancia_al_rango(v, rango):
    bajo, alto = rango
    return max(bajo - v, v - alto, 0.0)


def _color_esperado(material):
    return RGB_VERDE if _distancia_al_rango(HU_PUESTO[material], RANGOS[material]) <= 20 else RGB_ROJO


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _silencio(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*a, **k)


def _disco():
    yy, xx = np.mgrid[0:N, 0:N]
    return np.where((xx - N / 2) ** 2 + (yy - N / 2) ** 2 <= (100.0 / TAM) ** 2, 0.0, -1000.0).astype(np.float32)


def _corte_con_insertos():
    from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
    base = _disco()
    g = GeometriaCatphanCT(base, TAM)
    hu = base.copy()
    yy, xx = np.mgrid[0:N, 0:N]
    for material, v in HU_PUESTO.items():
        (cx, cy), r = g.obtener_roi(material)
        hu[(xx - cx) ** 2 + (yy - cy) ** 2 <= (r + 2) ** 2] = v
    return hu


def _lienzo():
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    return FigureCanvasQTAgg(Figure(figsize=(6, 6), dpi=100))


def _png_rgb(blob):
    return np.asarray(Image.open(io.BytesIO(blob)).convert("RGB"))


def _en_pantalla(lienzo):
    return np.asarray(lienzo.figure.axes[0].images[0].get_array())


def _colores(arreglo):
    return {tuple(int(x) for x in p) for p in np.asarray(arreglo)[..., :3].reshape(-1, 3)}


def _negro():
    return np.zeros((N, N), np.uint8)


@pytest.fixture(scope="module")
def valores_ct(qapp):
    """Valores CT analizado sobre el lienzo de una pestana: (resultados, guardado en rojo-verde-azul, lo que muestra la pestana, geometria)."""
    from analisisImagenes.Analisis_Catphan_TAC import valor_numero_ct
    from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
    hu = _corte_con_insertos()
    g = GeometriaCatphanCT(hu, TAM)
    lienzo = _lienzo()
    res = _silencio(valor_numero_ct, _negro(), hu, TAM, catphan=g, visualizar=True, canvas=lienzo)
    datos = {"res": res, "guardado": _png_rgb(res[-1]["imagen_analisis"]), "pantalla": _en_pantalla(lienzo).copy(), "g": g}
    lienzo.figure.clear()
    lienzo.deleteLater()
    return datos


def _pixel_del_anillo(datos, material):
    (cx, cy), r = datos["g"].obtener_roi(material)
    return tuple(int(x) for x in datos["guardado"][cy, cx + r]), tuple(int(x) for x in datos["pantalla"][cy, cx + r])


# ---------------------------------------------------------------------------------------------------- 1. el color de cada ROI
class TestElColorDeCadaROI:

    def test_los_numeros_son_los_del_corte_y_no_cambian(self, valores_ct):
        """La verdad del corte sintetico: cada material mide el HU que se le puso, su rango es el de la tabla y su error es la distancia al rango (0 dentro)."""
        materiales = [d for d in valores_ct["res"] if "material" in d]
        assert [d["material"] for d in materiales] == list(HU_PUESTO)
        for d in materiales:
            m = d["material"]
            assert d["promedio_hu"] == pytest.approx(HU_PUESTO[m], abs=1e-3), m
            assert tuple(d["rango_hu"]) == RANGOS[m], m
            assert d["error_abs"] == pytest.approx(_distancia_al_rango(HU_PUESTO[m], RANGOS[m]), abs=1e-3), m
            assert d["error_rel"] == ("Dentro del Rango" if d["error_abs"] == 0 else "Fuera de Rango"), m

    @pytest.mark.parametrize("material", list(HU_PUESTO))
    def test_el_anillo_guardado_tiene_el_color_de_su_distancia_al_rango(self, valores_ct, material):
        guardado, pantalla = _pixel_del_anillo(valores_ct, material)
        assert guardado == _color_esperado(material), (f"{material}: {HU_PUESTO[material]} [HU], a {_distancia_al_rango(HU_PUESTO[material], RANGOS[material])} [HU] de su rango "
                                                       f"{RANGOS[material]}: el anillo guardado es {guardado} y debe ser {_color_esperado(material)}")
        assert pantalla == guardado, f"{material}: la pestana muestra el anillo {pantalla} y lo guardado es {guardado}"

    def test_el_texto_del_roi_tiene_el_color_de_su_anillo(self, valores_ct):
        """El nombre del material, encima del anillo, y su cifra de HU, debajo, tienen el color de su anillo y ningun pixel del otro juicio."""
        for material in HU_PUESTO:
            (cx, cy), r = valores_ct["g"].obtener_roi(material)
            cajas = {"el nombre": valores_ct["guardado"][max(0, cy - r - 20):cy - r - 2, max(0, cx - 32):cx + 75],
                     "la cifra de HU": valores_ct["guardado"][cy + 24:cy + 40, cx - 33:cx + 14]}
            esperado = _color_esperado(material)
            otro = RGB_ROJO if esperado == RGB_VERDE else RGB_VERDE
            for que, caja in cajas.items():
                colores = _colores(caja)
                assert esperado in colores and otro not in colores, f"{material}: {que} debe ser {esperado} (colores en su caja: {sorted(colores)[:8]})"

    def test_el_circulo_interior_y_el_contorno_no_cambian(self, valores_ct):
        """El circulo interior de cada ROI es (255, 255, 0) para OpenCV y el contorno del fantoma (141, 60, 60): guardados, en rojo-verde-azul, (0, 255, 255) y (60, 60, 141)."""
        g = valores_ct["g"]
        for material in HU_PUESTO:
            (cx, cy), r = g.obtener_roi(material)
            assert tuple(int(x) for x in valores_ct["guardado"][cy, cx + int(r * 0.8)]) == (0, 255, 255), material
        cx, cy = g.centro_int
        assert tuple(int(x) for x in valores_ct["guardado"][cy, cx + g.radio_int]) == (60, 60, 141)

    def test_sin_valor_medido_el_roi_es_gris(self, qapp):
        """Un ROI sin pixeles que medir (aqui el Aire, con su centro fuera del corte) no tiene valor: su anillo y su nombre son grises. Con el centro a la izquierda asoma el anillo; con el centro abajo, tambien el nombre."""
        from analisisImagenes.Analisis_Catphan_TAC import valor_numero_ct
        from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
        hu = _corte_con_insertos()

        def con_el_aire_en(centro):
            class _AireFuera(GeometriaCatphanCT):
                def obtener_roi(self, nombre):
                    return (centro, 10) if nombre == "Aire" else super().obtener_roi(nombre)

            lienzo = _lienzo()
            try:
                res = _silencio(valor_numero_ct, _negro(), hu, TAM, catphan=_AireFuera(hu, TAM), visualizar=True, canvas=lienzo)
                aire = next(d for d in res if d.get("material") == "Aire")
                assert aire["promedio_hu"] is None and aire["error_abs"] is None
                return _png_rgb(res[-1]["imagen_analisis"]), _en_pantalla(lienzo).copy()
            finally:
                lienzo.figure.clear()
                lienzo.deleteLater()

        guardado, pantalla = con_el_aire_en((-9, N // 2))
        for x in (0, 1):
            assert tuple(int(v) for v in guardado[N // 2, x]) == RGB_GRIS, f"anillo sin valor en x={x}: {tuple(guardado[N // 2, x])}"
            assert tuple(int(v) for v in pantalla[N // 2, x]) == RGB_GRIS
        for imagen in con_el_aire_en((N // 2, N + 8)):
            colores = _colores(imagen[N - 22:N - 4, N // 2 - 32:N // 2 + 20])      # la caja del nombre, sobre el anillo que asoma
            assert RGB_GRIS in colores and RGB_ROJO not in colores and RGB_VERDE not in colores, f"nombre sin valor: colores en su caja {sorted(colores)[:8]}"


# ---------------------------------------------------------------------------------------------------- 2. la pantalla muestra lo que se guarda
def _analizar(nombre, lienzo):
    import analisisImagenes.Analisis_Catphan_TAC as AN
    from analisisImagenes.catphan.criterios import PARAMETROS_HEREDADOS
    from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
    hu = _corte_con_insertos()
    if nombre == "valores_ct":
        res = _silencio(AN.valor_numero_ct, _negro(), hu, TAM, catphan=GeometriaCatphanCT(hu, TAM), visualizar=True, canvas=lienzo)
        return res[-1]["imagen_analisis"]
    if nombre == "espesor":
        return _silencio(AN.espesor_corte, _negro(), hu, TAM, visualizar=True, canvas=lienzo)["imagen_analisis"]
    if nombre == "tamano_pixel":
        return _silencio(AN.tamano_pixel, _negro(), hu, TAM, visualizar=True, canvas=lienzo)["imagen_analisis"]
    if nombre == "contraste":
        return _silencio(AN.resolucion_contraste, _negro(), _disco(), TAM, visualizar=True, canvas=lienzo, **PARAMETROS_HEREDADOS["resolucion_contraste"])["resumen"]["imagen_analisis"]
    raise AssertionError(nombre)


class TestLaPantallaMuestraLoQueSeGuarda:

    @pytest.mark.parametrize("nombre", ["valores_ct", "espesor", "tamano_pixel", "contraste"])
    def test_la_pestana_muestra_los_colores_que_se_guardan(self, qapp, nombre):
        lienzo = _lienzo()
        try:
            guardado = _png_rgb(_analizar(nombre, lienzo))
            pantalla = _en_pantalla(lienzo)
            assert pantalla.shape == guardado.shape
            assert np.array_equal(pantalla, guardado), f"{nombre}: la pestana muestra {int((pantalla != guardado).any(axis=-1).sum())} pixeles con otro color que lo guardado"
        finally:
            lienzo.figure.clear()
            lienzo.deleteLater()

    @pytest.mark.parametrize("nombre", ["valores_ct", "espesor", "tamano_pixel", "contraste"])
    def test_sin_pestana_la_figura_muestra_los_colores_que_se_guardan(self, nombre, monkeypatch):
        """La rama sin lienzo (`plt.subplots` y `plt.show`, la de las llamadas sin pestana) muestra tambien lo que se guarda."""
        import matplotlib.pyplot as plt
        monkeypatch.setattr(plt, "show", lambda *a, **k: None)
        antes = set(plt.get_fignums())
        try:
            guardado = _png_rgb(_analizar(nombre, None))
            nuevas = [n for n in plt.get_fignums() if n not in antes]
            assert len(nuevas) == 1, nuevas
            pantalla = np.asarray(plt.figure(nuevas[0]).axes[0].images[0].get_array())
            assert np.array_equal(pantalla, guardado), f"{nombre}: sin pestana se muestran {int((pantalla != guardado).any(axis=-1).sum())} pixeles con otro color que lo guardado"
        finally:
            for n in set(plt.get_fignums()) - antes:
                plt.close(n)

    @pytest.mark.parametrize("con_pestana", [True, False], ids=["con_pestana", "sin_pestana"])
    @pytest.mark.parametrize("nombre", list(GUARDADOS))
    def test_lo_guardado_conserva_sus_colores(self, qapp, nombre, con_pestana, monkeypatch):
        """Pantalla igual a lo guardado no basta: cruzar los canales antes de mostrar y guardar dejaria las dos iguales e invertidas."""
        import matplotlib.pyplot as plt
        monkeypatch.setattr(plt, "show", lambda *a, **k: None)
        antes = set(plt.get_fignums())
        lienzo = _lienzo() if con_pestana else None
        try:
            colores = _colores(_png_rgb(_analizar(nombre, lienzo)))
            assert colores == GUARDADOS[nombre], f"{nombre}: se guarda con {sorted(colores)} y debe ser {sorted(GUARDADOS[nombre])}"
        finally:
            if lienzo is not None:
                lienzo.figure.clear()
                lienzo.deleteLater()
            for n in set(plt.get_fignums()) - antes:
                plt.close(n)

    @pytest.mark.parametrize("con_pestana", [True, False])
    def test_la_uniformidad_se_ve_como_hoy(self, qapp, con_pestana, monkeypatch):
        """AJ5-D2: la uniformidad guarda la MISMA figura que muestra, asi que su pantalla y su PDF ya coinciden; no se convierte. Se ve el contorno (141, 60, 60) y el circulo interior
        (255, 255, 0) tal como los escribe el codigo, no (60, 60, 141) ni (0, 255, 255)."""
        import matplotlib.pyplot as plt
        from analisisImagenes.Analisis_Catphan_TAC import uniformidad
        monkeypatch.setattr(plt, "show", lambda *a, **k: None)
        antes = set(plt.get_fignums())
        lienzo = _lienzo() if con_pestana else None
        try:
            _silencio(uniformidad, _negro(), _disco(), TAM, visualizar=True, canvas=lienzo, hu_tolerancia=4.0, ui_threshold_pct=5.0, inu_threshold_pct=5.0)
            figura = lienzo.figure if con_pestana else plt.figure([n for n in plt.get_fignums() if n not in antes][0])
            colores = _colores(figura.axes[0].images[0].get_array())
            assert (141, 60, 60) in colores and (255, 255, 0) in colores
            assert (60, 60, 141) not in colores and (0, 255, 255) not in colores
        finally:
            if lienzo is not None:
                lienzo.figure.clear()
                lienzo.deleteLater()
            for n in set(plt.get_fignums()) - antes:
                plt.close(n)

    def test_una_sola_funcion_lleva_cada_imagen_de_opencv_a_la_pantalla(self):
        """Cada `imshow` de una imagen de OpenCV pasa UNA vez por `_imagen_para_pantalla` (dos veces la dejaria cruzada); la uniformidad no la usa; ninguna otra conversion de orden."""
        arbol = ast.parse(ANALISIS_PY.read_text(encoding="utf-8"))
        funciones = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}
        assert "_imagen_para_pantalla" in funciones

        def llamadas(nodo):
            return [c for c in ast.walk(nodo) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "_imagen_para_pantalla"]

        esperado = {"valor_numero_ct": 2, "espesor_corte": 1, "tamano_pixel": 2, "resolucion_contraste": 2, "uniformidad": 0}
        assert {f: len(llamadas(funciones[f])) for f in esperado} == esperado
        for c in llamadas(arbol):
            assert not any(isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == "_imagen_para_pantalla" for a in c.args), "conversion aplicada dos veces"
        assert ANALISIS_PY.read_text(encoding="utf-8").count("COLOR_BGR2RGB") == 1
