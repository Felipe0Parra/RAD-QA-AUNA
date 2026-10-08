"""OR.1 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, cierra DP-126): UNA sola transformacion de orientacion y giro para todos los modulos del Catphan.

La posicion de cada material, inserto o region de un modulo parte de un angulo NOMINAL (fantoma derecho y sin giro) y necesita su angulo real en la imagen. Esa cuenta estaba escrita en linea
TRES veces (`Analisis_Catphan_TAC._angulo_efectivo`, la inversa de `resolucion_espacial` y `GeometriaCatphan._calcular_roi_float`), las tres con el signo del giro mal para el fantoma INVERTIDO
(`180 - theta + R`: yerra exactamente 2R porque al voltear la imagen el giro que mide pylinac cambia de sentido), y CTP404 (`valor_numero_ct`, de donde sale la linealidad) no la usaba:
en `QA Halcyon Catphan`, la unica serie invertida del corpus, 6 de sus 7 materiales salian PERMUTADOS (Teflon en -180 HU, PMP en 892) y la linealidad daba r = 0.313.

Ahora `analisisImagenes/catphan/orientacion.py::angulo_en_imagen` es la unica definicion; las tres copias se retiran, `GeometriaCatphanCT` recibe orientacion y giro (decision D10: «giro completo»,
tambien en las series derechas) y `valor_numero_ct` mide en `catphan.obtener_roi(material)`, la misma fuente con que se dibuja.

El metodo de verificacion es el de D.1: el volumen COMPLETO girado psi grados, analizado por pylinac por el camino del motor, y la aplicacion medida en el corte original (leido con pydicom)
llevado al mismo marco.

Sobre el rojo contra el codigo anterior (revision de OR.1): la prueba usa API que el codigo anterior no tiene (`orientacion.py`, los parametros `orientacion`/`roll_deg` de
`GeometriaCatphanCT` y de `valor_numero_ct`), asi que contra `HEAD` una parte cae por `ImportError`/`TypeError` y no por su aserción; la lectura SUSTANTIVA (con `orientacion.py`
presente y solo la produccion de `HEAD`) y la lista de lo que pasa en ella (la funcion pura y los controles de lo que ya funcionaba) se miden en la bateria de mutaciones del anexo.
"""
import ast
import contextlib
import gc
import io
import os
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pydicom
import pytest
from PyQt5.QtWidgets import QMessageBox
from scipy import ndimage as ndi

from _catphan_oro import HU_MATERIALES
from _corpus import serie_catphan
from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401  (fixtures)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAT_APP = {  # nombre en la aplicacion -> nombre en pylinac
    "Teflon": "Teflon", "Delrin": "Delrin", "Acrilico": "Acrylic", "Poliestireno": "Poly", "LDPE": "LDPE", "PMP": "PMP", "Aire": "Air",
}
LC_APP_A_PYL = {"15mm": "15", "9mm": "9", "8mm": "8", "7mm": "7", "6mm": "6", "5mm": "5"}


def _nuevo():
    import analisisImagenes.catphan.orientacion as orientacion
    return orientacion


# ---------------------------------------------------------------------------------------------------- la funcion pura
class TestLaFuncion:

    def test_normal_suma_el_giro_e_invertido_lo_resta(self):
        f = _nuevo().angulo_en_imagen
        assert f(300, "normal", 0.92) == pytest.approx(300.92)
        assert f(300, "invertido", 0.92) == pytest.approx(-120.92)            # 180 - 300 - 0.92 (el signo de DP-126: antes 180 - 300 + 0.92)
        assert f(0, "invertido", 0.0) == pytest.approx(180.0)

    def test_el_giro_cambia_de_signo_entre_las_dos_orientaciones(self):
        """La razon de DP-126: voltear la imagen invierte el sentido del giro que mide pylinac."""
        f = _nuevo().angulo_en_imagen
        d_normal = f(45, "normal", 5.0) - f(45, "normal", 4.0)
        d_invertido = f(45, "invertido", 5.0) - f(45, "invertido", 4.0)
        assert d_normal == pytest.approx(1.0) and d_invertido == pytest.approx(-1.0)

    @pytest.mark.parametrize("orientacion", ["normal", "invertido"])
    def test_la_inversa_deshace_la_ida(self, orientacion):
        f = _nuevo().angulo_en_imagen
        rng = np.random.default_rng(7)
        for theta, giro in zip(rng.uniform(-360, 360, 200), rng.uniform(-30, 30, 200)):
            assert f(f(theta, orientacion, giro), orientacion, giro, inversa=True) == pytest.approx(theta, abs=1e-9)

    def test_acepta_arreglos(self):
        f = _nuevo().angulo_en_imagen
        angulos = np.array([0.0, 90.0, 180.0])
        assert np.allclose(f(angulos, "invertido", 3.0), [177.0, 87.0, -3.0])
        assert np.allclose(f(angulos, "normal", 3.0), [3.0, 93.0, 183.0])
        assert np.allclose(f(angulos, "normal", 3.0, inversa=True), [-3.0, 87.0, 177.0])

    @pytest.mark.parametrize("orientacion", ["Invertido", "INVERTIDO", "Normal", "flipped", "invertida", "", None, 1])
    def test_una_orientacion_que_no_es_normal_ni_invertido_se_rechaza(self, orientacion):
        """Revision de OR.1 (P3): antes todo lo que no era la cadena exacta «invertido» se tomaba por «normal» y devolvia `theta + R`: el error de espejo que esta tarea cierra."""
        with pytest.raises(ValueError, match="orientacion"):
            _nuevo().angulo_en_imagen(300, orientacion, 0.92)

    @pytest.mark.parametrize("giro", [None, float("nan"), float("inf"), float("-inf"), "abc", [1.0, 2.0]])
    def test_un_giro_que_no_es_un_numero_finito_se_rechaza(self, giro):
        """Revision de OR.1 (P3): `None` lanzaba `TypeError` y `nan` devolvia `nan`, que reventaba despues en `obtener_roi` con otro error."""
        for orientacion in ("normal", "invertido"):
            with pytest.raises(ValueError, match="giro"):
                _nuevo().angulo_en_imagen(300, orientacion, giro)

    def test_un_giro_numpy_o_entero_se_acepta(self):
        f = _nuevo().angulo_en_imagen
        assert f(10, "normal", np.float64(2.5)) == pytest.approx(12.5) and f(10, "invertido", 3) == pytest.approx(167.0)

    def test_sin_orientacion_ni_giro_es_la_identidad_de_antes_de_d1(self):
        f = _nuevo().angulo_en_imagen
        for theta in (-87.4, 0.0, 59.0, 300.0):
            assert f(theta) == theta and f(theta, "normal", 0.0) == theta and f(theta, "normal", 0.0, inversa=True) == theta


# --------------------------------------------------------------------------- las geometrias usan LA misma transformacion
def _disco_hu(tam=0.5, n=512):
    """Un fantoma sintetico: un disco de radio 100 mm a 0 HU sobre aire (-1000)."""
    yy, xx = np.mgrid[0:n, 0:n]
    r_px = 100.0 / tam
    return np.where((xx - n / 2) ** 2 + (yy - n / 2) ** 2 <= r_px ** 2, 0.0, -1000.0).astype(np.float32)


class TestLasGeometrias:

    @pytest.mark.parametrize("orientacion, giro", [("normal", 0.0), ("normal", 3.5), ("invertido", 0.0), ("invertido", 3.5), ("invertido", -7.0)])
    def test_ctp515_coloca_cada_inserto_donde_dice_la_funcion(self, orientacion, giro):
        from analisisImagenes.catphan.orientacion import angulo_en_imagen
        from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
        g = GeometriaCatphan(_disco_hu(), 0.5, orientacion=orientacion, roll_deg=giro)
        for nombre, info in g.ROI_CONFIG.items():
            (cx, cy), _ = g.obtener_roi_float(nombre)
            phi = np.radians(angulo_en_imagen(info["angulo"], orientacion, giro))
            assert cx == pytest.approx(g.centro[0] + g.ROI_DIST_MM / 0.5 * np.cos(phi), abs=1e-6)
            assert cy == pytest.approx(g.centro[1] + g.ROI_DIST_MM / 0.5 * np.sin(phi), abs=1e-6)

    @pytest.mark.parametrize("orientacion, giro", [("normal", 0.0), ("normal", 3.5), ("invertido", 0.0), ("invertido", 3.5), ("invertido", -7.0)])
    def test_ctp404_coloca_cada_material_donde_dice_la_funcion(self, orientacion, giro):
        from analisisImagenes.catphan.orientacion import angulo_en_imagen
        from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
        g = GeometriaCatphanCT(_disco_hu(), 0.5, orientacion=orientacion, roll_deg=giro)
        for nombre, info in g.ROI_CONFIG.items():
            (cx, cy), radio = g.obtener_roi_float(nombre)
            phi = np.radians(angulo_en_imagen(info["angulo"], orientacion, giro))
            assert cx == pytest.approx(g.centro[0] + info["distancia_mm"] / 0.5 * np.cos(phi), abs=1e-6), nombre
            assert cy == pytest.approx(g.centro[1] + info["distancia_mm"] / 0.5 * np.sin(phi), abs=1e-6), nombre

    @pytest.mark.parametrize("clase", ["GeometriaCatphan", "GeometriaCatphanCT"])
    @pytest.mark.parametrize("orientacion, giro", [("normal", 0.0), ("normal", 3.5), ("invertido", 3.5), ("invertido", -7.0)])
    def test_el_ajuste_global_del_posicionador_se_aplica_en_el_marco_de_la_imagen(self, clase, orientacion, giro):
        """Revision de OR.1 (H2): el ajuste que el fisico hace con los deslizadores globales (dx, dy y dtheta, en pixeles y grados de LA IMAGEN que ve) mueve cada inserto exactamente
        eso, tambien con el fantoma invertido y girado: el angulo de ajuste se suma DESPUES de la transformacion (sumado al giro antes, su sentido se invertiria en el invertido)."""
        from analisisImagenes.catphan.orientacion import angulo_en_imagen
        import data.ManejoDatos.catphan_TAC.leer_dicom as leer
        import data.ManejoDatos.catphan_TAC.posicionador_manual as pm
        g = getattr(leer if clase == "GeometriaCatphan" else pm, clase)(_disco_hu(), 0.5, orientacion=orientacion, roll_deg=giro)
        g.offset_x, g.offset_y, g.offset_ang = 3.0, -2.0, 1.5
        for nombre, info in g.ROI_CONFIG.items():
            (cx, cy), _ = g.obtener_roi_float(nombre)
            distancia = (info["distancia_mm"] if clase == "GeometriaCatphanCT" else g.ROI_DIST_MM) / 0.5
            phi = np.radians(angulo_en_imagen(info["angulo"], orientacion, giro) + 1.5)
            assert cx == pytest.approx(g.centro[0] + 3.0 + distancia * np.cos(phi), abs=1e-6), (clase, nombre)
            assert cy == pytest.approx(g.centro[1] - 2.0 + distancia * np.sin(phi), abs=1e-6), (clase, nombre)

    @pytest.mark.parametrize("clase", ["GeometriaCatphan", "GeometriaCatphanCT"])
    @pytest.mark.parametrize("orientacion, giro", [("normal", 0.0), ("invertido", 3.5)])
    def test_obtener_roi_es_el_redondeo_exacto_de_obtener_roi_float_con_todos_los_ajustes(self, clase, orientacion, giro):
        """Revision de OR.1 (la mutacion MR11 sobrevivia): `valor_numero_ct` mide en `obtener_roi` (la version entera) y el dibujo del posicionador tambien; las pruebas anteriores comparaban
        la posicion FLOTANTE con la formula, y las que miden con `valor_numero_ct` colocaban su disco sintetico con la misma `obtener_roi` que se estaba probando, asi que un
        `obtener_roi` que perdiera el ajuste global (o lo restara) seguia en verde. Aqui la version entera es el redondeo EXACTO de la flotante, con el ajuste global y el local puestos."""
        import data.ManejoDatos.catphan_TAC.leer_dicom as leer
        import data.ManejoDatos.catphan_TAC.posicionador_manual as pm
        g = getattr(leer if clase == "GeometriaCatphan" else pm, clase)(_disco_hu(), 0.5, orientacion=orientacion, roll_deg=giro)
        g.offset_x, g.offset_y, g.offset_ang = 4.0, -3.0, 2.0
        primero = next(iter(g.ROI_CONFIG))
        g.offsets_locales[primero] = [3.0, -2.0]
        for nombre in g.ROI_CONFIG:
            (fx, fy), fr = g.obtener_roi_float(nombre)
            assert g.obtener_roi(nombre) == ((int(round(fx)), int(round(fy))), int(round(fr))), (clase, nombre)
        sin_ajuste = getattr(leer if clase == "GeometriaCatphan" else pm, clase)(_disco_hu(), 0.5, orientacion=orientacion, roll_deg=giro)
        assert g.obtener_roi(primero)[0] != sin_ajuste.obtener_roi(primero)[0], "el control tiene que discriminar: el ajuste mueve el inserto"

    def test_ctp404_sin_orientacion_ni_giro_coloca_los_materiales_como_antes(self):
        """La conducta por omision no cambia: la posicion nominal."""
        from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
        g = GeometriaCatphanCT(_disco_hu(), 0.5)
        assert (g.orientacion, g.roll_deg) == ("normal", 0.0)
        for nombre, info in g.ROI_CONFIG.items():
            (cx, cy), _ = g.obtener_roi_float(nombre)
            assert cx == pytest.approx(g.centro[0] + info["distancia_mm"] / 0.5 * np.cos(np.radians(info["angulo"])), abs=1e-6)

    def test_valor_numero_ct_mide_donde_se_dibuja(self):
        """`valor_numero_ct` toma la posicion de `obtener_roi` (la fuente unica): con un material sintetico en la posicion de un fantoma INVERTIDO y girado, lo encuentra."""
        from analisisImagenes.Analisis_Catphan_TAC import valor_numero_ct
        from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
        base = _disco_hu()
        g = GeometriaCatphanCT(base, 0.5, orientacion="invertido", roll_deg=4.0)
        (cx, cy), r = g.obtener_roi("Teflon")
        yy, xx = np.mgrid[0:512, 0:512]
        imagen = base.copy()
        imagen[(xx - cx) ** 2 + (yy - cy) ** 2 <= (r + 2) ** 2] = 1000.0                   # «Teflon» en su sitio
        r_ct = valor_numero_ct((np.clip(imagen, -200, 400) * 0 + 128).astype(np.uint8), imagen, 0.5, visualizar=False, orientacion="invertido", roll_deg=4.0)
        teflon = next(d for d in r_ct if isinstance(d, dict) and d.get("material") == "Teflon")
        assert teflon["promedio_hu"] == pytest.approx(1000.0, abs=1.0)
        sin_orientacion = valor_numero_ct((np.clip(imagen, -200, 400) * 0 + 128).astype(np.uint8), imagen, 0.5, visualizar=False)
        assert next(d for d in sin_orientacion if isinstance(d, dict) and d.get("material") == "Teflon")["promedio_hu"] < 100.0, "el control tiene que discriminar"


class TestElAjusteManualDelFisicoSeMide:

    @pytest.mark.parametrize("global_", [False, True])
    @pytest.mark.parametrize("orientacion, giro", [("normal", 0.0), ("invertido", 3.5)])
    def test_valor_numero_ct_mide_donde_el_fisico_dejo_el_inserto(self, orientacion, giro, global_):
        """Efecto colateral de medir en `obtener_roi` (la fuente unica con que se dibuja): el posicionador manual de CTP404 deja un ajuste LOCAL por material (`offsets_locales`) que
        SE DIBUJABA pero que `valor_numero_ct` no medía (usaba `posicion_roi`, que solo conoce el ajuste global): lo que el fisico veia y lo que se media podian ser sitios distintos."""
        from analisisImagenes.Analisis_Catphan_TAC import valor_numero_ct
        from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
        base = _disco_hu()
        g = GeometriaCatphanCT(base, 0.5, orientacion=orientacion, roll_deg=giro)
        g.offsets_locales["Teflon"] = [6.0, -4.0]                                   # el fisico mueve ESE material (los ajustes locales estan limitados por MAX_OFFSET_LOCAL)
        if global_:
            g.offset_x, g.offset_y, g.offset_ang = 4.0, -3.0, 2.0                   # y, ademas, los tres deslizadores globales
        (cx, cy), r = g.obtener_roi("Teflon")
        yy, xx = np.mgrid[0:512, 0:512]
        imagen = base.copy()
        imagen[(xx - cx) ** 2 + (yy - cy) ** 2 <= (r + 2) ** 2] = 1000.0
        r_ct = _silencio(valor_numero_ct, np.full(imagen.shape, 128, dtype=np.uint8), imagen, 0.5, catphan=g, visualizar=False)
        teflon = next(d for d in r_ct if isinstance(d, dict) and d.get("material") == "Teflon")
        assert teflon["promedio_hu"] == pytest.approx(1000.0, abs=1.0), "se midio en el sitio nominal y no donde el fisico dejo el inserto"


class TestLosDemasSitiosQueColocanUnModulo:

    @pytest.mark.parametrize("orientacion, giro", [("normal", 3.5), ("invertido", 3.5), ("invertido", -7.0)])
    def test_el_circulo_de_referencia_del_posicionador_cae_en_el_inserto(self, orientacion, giro):
        """El posicionador manual de CTP515 dibuja, en modo individual, un circulo punteado de REFERENCIA en la posicion sin ajuste local: tiene que caer donde la geometria coloca el
        inserto (antes se dibujaba en el angulo NOMINAL: en espejo y sin el giro en un fantoma invertido)."""
        from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
        from data.ManejoDatos.catphan_TAC.posicionador_manual import PosicionadorDialog
        g = GeometriaCatphan(_disco_hu(), 0.5, orientacion=orientacion, roll_deg=giro)
        dlg = PosicionadorDialog(g, np.zeros((512, 512), dtype=np.uint8))
        try:
            dlg._modo = "individual"
            dlg._roi_seleccionado = "15mm"
            dlg._dibujar()
            punteados = [p for p in dlg.fig.axes[0].patches if p.get_linestyle() in (":", "dotted")]
            assert len(punteados) == 1
            (cx, cy), _ = g.obtener_roi("15mm")
            assert punteados[0].center == pytest.approx((cx, cy), abs=1.0)
        finally:
            dlg.close()
            dlg.deleteLater()

    @pytest.mark.parametrize("orientacion, giro", [("normal", 3.5), ("invertido", 3.5), ("invertido", -7.0)])
    def test_los_fondos_de_ctp515_se_colocan_con_la_orientacion_y_el_giro_de_la_serie(self, monkeypatch, orientacion, giro):
        """Las seis ROI de FONDO de CTP515 no pasan por `_calcular_roi_float`: se ubican con `catphan.posicion_roi(angulo, ...)`, y su angulo es el de cada inserto llevado por la funcion
        unica con la orientacion y el giro que recibe `resolucion_contraste` (D.1 ya las separo del inserto; aqui se fija que usan LA misma cuenta)."""
        from analisisImagenes.Analisis_Catphan_TAC import resolucion_contraste
        from analisisImagenes.catphan.orientacion import angulo_en_imagen
        from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
        hu = _disco_hu()
        g = GeometriaCatphan(hu, 0.5, orientacion=orientacion, roll_deg=giro)
        angulos = []
        original = g.posicion_roi
        monkeypatch.setattr(g, "posicion_roi", lambda angulo, *a, **k: (angulos.append(angulo), original(angulo, *a, **k))[1])
        with contextlib.suppress(Exception):                                       # sobre un disco sin insertos la medicion puede no concluir: aqui solo importa donde coloca los fondos
            _silencio(resolucion_contraste, np.zeros(hu.shape, dtype=np.uint8), hu, 0.5, catphan=g, visualizar=False, cnr_lim=1.0, visibilidad_lim=0.1, min_rois_visibles=4,
                      orientacion=orientacion, roll_deg=giro)
        esperados = {round(angulo_en_imagen(info["angulo"], orientacion, giro), 6) for info in g.ROI_CONFIG.values()}
        assert angulos and {round(a, 6) for a in angulos} == esperados, (sorted(set(angulos)), sorted(esperados))

    @pytest.mark.parametrize("orientacion, giro", [("normal", 3.5), ("invertido", 3.5)])
    def test_resolucion_espacial_pide_la_inversa_con_la_orientacion_y_el_giro_que_recibe(self, monkeypatch, orientacion, giro):
        """`resolucion_espacial` parte de DONDE ESTA cada muestra del anillo y pregunta que region nominal le corresponde: la inversa de la funcion unica, con la orientacion y el giro de la
        serie (el signo de un giro invertido era el defecto de DP-126; esta prueba fija que se pide la INVERSA y con los argumentos de la serie)."""
        import analisisImagenes.Analisis_Catphan_TAC as AC
        llamadas = []
        real = AC.angulo_en_imagen

        def espia(angulo, orientacion_=None, roll_deg=None, *, inversa=False):
            llamadas.append((orientacion_, roll_deg, inversa))
            return real(angulo, orientacion_, roll_deg, inversa=inversa)

        monkeypatch.setattr(AC, "angulo_en_imagen", espia)
        hu = _disco_hu()
        with contextlib.suppress(Exception):                                       # sobre un disco sin anillo la medicion puede no concluir: aqui solo importa a quien le pregunta
            _silencio(AC.resolucion_espacial, np.zeros(hu.shape, dtype=np.uint8), hu, 0.5, visualizar=False, orientacion=orientacion, roll_deg=giro)
        assert (orientacion, giro, True) in llamadas, llamadas


# --------------------------------------------------------------------------------- tripwires por AST (derivados del arbol)
def _fuentes_de_produccion():
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in (".venv", "tests", "build", "dist", "node_modules", "__pycache__", ".git", "scripts")]
        for a in archivos:
            if a.endswith(".py"):
                yield os.path.relpath(os.path.join(carpeta, a), RAIZ)


# donde una comparacion con «invertido» es LEGITIMA y no es la cuenta de un angulo
PERMITIDOS_INVERTIDO = {
    "analisisImagenes/catphan/orientacion.py": "la unica definicion de la transformacion",
    "data/ManejoDatos/catphan_TAC/slice_matcher.py": "traduce el INDICE del corte (n-1-i) cuando el volumen se volteo para analizarlo: no es un angulo",
}


def _comparaciones_de_orientacion(arbol):
    """Lineas de cada comparacion con la cadena «normal» o «invertido»: `== 'invertido'`, `!= 'normal'`, `in ('invertido',)`... cualquiera de ellas es el comienzo de una cuarta copia en
    linea de la transformacion. Sin mirar el NOMBRE de la variable (una copia puede llamarla `o`): hoy toda la produccion tiene exactamente dos, las declaradas."""
    sitios = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Compare):
            constantes = {c.value for c in ast.walk(nodo) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
            if constantes & {"invertido", "normal"}:
                sitios.append(nodo.lineno)
    return sitios


def test_ninguna_comparacion_con_la_orientacion_fuera_de_su_sitio():
    """El plan: «ningún `== "invertido"` fuera de `orientacion.py`». Revision de OR.1 (H7): vale para cualquier forma de comparar una orientacion con «normal»/«invertido» (tambien
    `!= 'normal'`). Las excepciones son las declaradas arriba, cada una con su motivo."""
    sitios = []
    for ruta in _fuentes_de_produccion():
        with open(os.path.join(RAIZ, ruta), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        sitios += [(ruta, n) for n in _comparaciones_de_orientacion(arbol)]
    fuera = [(r, n) for r, n in sitios if r not in PERMITIDOS_INVERTIDO]
    assert fuera == [], f"una comparacion de la orientacion fuera de su sitio (¿otra copia de la transformacion?): {fuera}"
    assert any(r == "analisisImagenes/catphan/orientacion.py" for r, _ in sitios), "la prueba no encuentra la definicion unica (vacua)"


def test_el_detector_de_comparaciones_ve_las_formas_equivalentes():
    """Control del tripwire: una cuarta copia escrita con `!= 'normal'` o con `in (...)` tambien se detecta."""
    for texto in ("def f(o, a, r):\n    return (180.0 - a - r) if o != 'normal' else (a + r)\n",
                  "def f(orientacion, a):\n    return a if orientacion in ('invertido',) else -a\n",
                  "def f(self):\n    return self.orientacion == 'invertido'\n"):
        assert _comparaciones_de_orientacion(ast.parse(texto)), texto


def test_las_copias_de_antes_ya_no_existen():
    for ruta in ("analisisImagenes/Analisis_Catphan_TAC.py", "data/ManejoDatos/catphan_TAC/leer_dicom.py"):
        with open(os.path.join(RAIZ, ruta), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        nombres = {n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}
        assert "_angulo_efectivo" not in nombres, ruta


def test_todo_lo_que_coloca_un_modulo_pasa_por_la_funcion_unica():
    """Las tres geometrias de posicion y la inversa de `resolucion_espacial` llaman a `angulo_en_imagen`."""
    esperado = {
        "data/ManejoDatos/catphan_TAC/leer_dicom.py": "_calcular_roi_float",
        "data/ManejoDatos/catphan_TAC/posicionador_manual.py": "_calcular_roi_float",
        "analisisImagenes/Analisis_Catphan_TAC.py": "resolucion_espacial",
    }
    for ruta, funcion in esperado.items():
        with open(os.path.join(RAIZ, ruta), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        cuerpos = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == funcion]
        assert cuerpos, (ruta, funcion)
        assert any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "angulo_en_imagen" for f_ in cuerpos for c in ast.walk(f_)), (ruta, funcion)
    with open(os.path.join(RAIZ, "analisisImagenes/Analisis_Catphan_TAC.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    resolucion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "resolucion_contraste")
    assert any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "angulo_en_imagen" for c in ast.walk(resolucion)), "los fondos de CTP515"


def test_valor_numero_ct_mide_con_obtener_roi_y_recibe_la_orientacion():
    with open(os.path.join(RAIZ, "analisisImagenes/Analisis_Catphan_TAC.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    f_ = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "valor_numero_ct")
    assert {a.arg for a in f_.args.args} >= {"orientacion", "roll_deg"}
    llamados = {getattr(c.func, "attr", None) for c in ast.walk(f_) if isinstance(c, ast.Call)}
    assert "obtener_roi" in llamados and "posicion_roi" not in llamados


def test_la_pantalla_pasa_la_orientacion_y_el_giro_a_la_geometria_de_ctp404():
    with open(os.path.join(RAIZ, "ui/paginasControles/PruebasMensuales/tac_mensual.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    llamadas = [c for c in ast.walk(arbol) if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "GeometriaCatphanCT"]
    assert llamadas and all({k.arg for k in c.keywords} >= {"orientacion", "roll_deg"} for c in llamadas)


# --------------------------------------------------------------------------- series reales frente a pylinac (el metodo de D.1)
def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


def _girar(arr, psi):
    arr = np.asarray(arr, dtype=np.float32)
    return arr if psi == 0.0 else ndi.rotate(arr, psi, reshape=False, order=1, cval=float(arr.min()))


def _ventanear(hu, wl=40, ww=400):
    lo, hi = wl - ww / 2, wl + ww / 2
    return ((np.clip(hu, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)


def _silencio(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*a, **k)


def _medir(clave, psi):
    """pylinac sobre la serie con el volumen COMPLETO girado `psi` grados (camino del motor) y los cortes crudos de los cuatro modulos, girados igual. Sin cache de modulo (revision de
    OR.1, H8): el objeto de pylinac lleva el volumen entero, y nueve de ellos vivos hasta el fin del proceso sumaban 3.3 GB; lo libera la fixture `medida`."""
    from analisisImagenes.catphan import motor
    from analisisImagenes.catphan.perfiles import PERFILES
    from analisisImagenes.catphan.serie import identificar_equipo, leer_serie
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    equipo, _ = identificar_equipo(serie)
    limite = getattr(PERFILES.get(equipo), "limite_variacion_hu", None)       # el iX no se localiza sin el limite de homogeneidad del equipo (extension validada, 150 HU)
    invertida = clave == "HALCYON_SEP"
    n = len(serie.cortes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ct = motor._construir([c.ruta for c in serie.cortes], limite)
        if psi != 0.0:
            for img in ct.dicom_stack.images:
                img.array = _girar(img.array, psi)
        if invertida:
            motor._voltear_volumen(ct)
        motor._analizar_una_vez(ct, None, {})
    ancho = int(np.asarray(ct.dicom_stack[0].array).shape[1])
    k = {m: int(getattr(ct, m).slice_num) for m in ("ctp404", "ctp515", "ctp528")}
    idx = {m: (n - 1 - k[m]) if invertida else k[m] for m in k}
    raw = {}
    for m in k:
        ds = pydicom.dcmread(serie.cortes[idx[m]].ruta)
        raw[m] = _girar(ds.pixel_array.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept), psi)
    tam = float(pydicom.dcmread(serie.cortes[0].ruta, stop_before_pixels=True).PixelSpacing[0])
    return {"ct": ct, "R": float(ct.catphan_roll), "invertida": invertida, "ancho": ancho, "raw": raw, "tam": tam, "equipo": equipo,
            "orientacion": "invertido" if invertida else "normal"}


def _al_marco_crudo(x, y, m):
    return ((m["ancho"] - 1) - x, y) if m["invertida"] else (x, y)


def _perfil_anillo(img, cx, cy, tam, angulos_img_deg, r_mm=(46.0, 50.0), paso_mm=0.5):
    """Media radial de la banda r_mm, muestreada en los angulos de imagen dados (marco de esa imagen)."""
    radios = np.arange(r_mm[0], r_mm[1] + 1e-9, paso_mm) / tam
    a = np.radians(np.asarray(angulos_img_deg))
    vals = [ndi.map_coordinates(img, [cy + rp * np.sin(a), cx + rp * np.cos(a)], order=1, mode="nearest") for rp in radios]
    return np.mean(vals, axis=0)


def _desfase_por_correlacion(ref, prueba, paso_deg, sector, max_lag_deg=40.0):
    """Lag (grados, sobre la rejilla nominal circular) que mejor alinea `prueba` con `ref` en `sector`."""
    lags = np.arange(-int(max_lag_deg / paso_deg), int(max_lag_deg / paso_deg) + 1)
    r0 = ref[sector] - ref[sector].mean()
    mejores = []
    for lag in lags:
        p = np.roll(prueba, lag)[sector]
        p = p - p.mean()
        den = np.sqrt((r0 ** 2).sum() * (p ** 2).sum())
        mejores.append((r0 * p).sum() / den if den > 0 else -1)
    return float(lags[int(np.argmax(mejores))] * paso_deg)


# El protocolo del plan: la serie invertida con el volumen COMPLETO girado 3/7/15/-7 grados, y las seis series reales sin girar (CTP404, valor_numero_ct y linealidad frente a
# pylinac), mas el tomografo girado 3 grados. Revision de OR.1 (H5): antes faltaban el iX (con el limite de homogeneidad de su perfil) y la carpeta mixta, la que mas cambia con D10.
CASOS_REALES = [("HALCYON_SEP", 0.0), ("HALCYON_SEP", 3.0), ("HALCYON_SEP", 7.0), ("HALCYON_SEP", 15.0), ("HALCYON_SEP", -7.0),
                ("TOMOGRAFO", 0.0), ("TOMOGRAFO", 3.0), ("HALCYON_JUN", 0.0), ("HALCYON_236", 0.0), ("IX_DIC", 0.0), ("MIXTA", 0.0)]
CASOS_DE_LA_SERIE_INVERTIDA = [c for c in CASOS_REALES if c[0] == "HALCYON_SEP"]


@pytest.fixture(scope="class", params=CASOS_REALES, ids=[f"{c}-{p:+g}" for c, p in CASOS_REALES])
def medida(request):
    """Una serie y un giro por vez (fixture de CLASE con parametros: pytest agrupa por parametro y libera el volumen al cambiar). Revision de OR.1 (H8)."""
    clave, psi = request.param
    m = _medir(clave, psi)
    yield clave, psi, m
    del m
    gc.collect()


class TestFrentePylinac:

    def test_ctp404_cada_material_se_mide_donde_esta(self, medida):
        """Posicion <= 0.8 mm y HU <= 5 frente a pylinac (el plan). Antes, a 3 grados: 8 mm y 833 HU en la serie invertida; 2.4 mm y 104 HU en el tomografo."""
        from analisisImagenes.Analisis_Catphan_TAC import valor_numero_ct
        from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
        clave, psi, m = medida
        geo = GeometriaCatphanCT(m["raw"]["ctp404"], m["tam"], orientacion=m["orientacion"], roll_deg=m["R"])
        r = _silencio(valor_numero_ct, _ventanear(m["raw"]["ctp404"]), m["raw"]["ctp404"], m["tam"], catphan=geo, visualizar=False)
        hu_app = {d["material"]: d["promedio_hu"] for d in r if isinstance(d, dict) and "material" in d}
        peor_mm, peor_hu = 0.0, 0.0
        for app, pyl in MAT_APP.items():
            roi = m["ct"].ctp404.rois[pyl]
            xp, yp = _al_marco_crudo(roi.center.x, roi.center.y, m)
            (xa, ya), _ = geo.obtener_roi_float(app)
            peor_mm = max(peor_mm, float(np.hypot(xa - xp, ya - yp) * m["tam"]))
            peor_hu = max(peor_hu, abs(hu_app[app] - float(roi.pixel_value)))
        assert peor_mm <= 0.8, f"{clave} psi={psi}: un material queda a {peor_mm:.2f} mm de pylinac"
        assert peor_hu <= 5.0, f"{clave} psi={psi}: un material difiere {peor_hu:.1f} HU de pylinac"
        # y la linealidad que sale de esos HU, como la calcula la aplicacion (revision de OR.1, H5: el protocolo la pide en las seis series)
        from analisisImagenes.Analisis_Catphan_TAC import linealidad_ct
        from analisisImagenes.catphan.atenuacion import energia_de_linealidad_mev, materiales_a_energia
        mu = materiales_a_energia(energia_de_linealidad_mev(m["equipo"]))
        lin = _silencio(linealidad_ct, [float(mu[x]["mu"]) for x in ORDEN_ORO], [float(f"{hu_app[x]:.1f}") for x in ORDEN_ORO], visualizar=False)
        assert lin["r_squared"] >= 0.99, f"{clave} psi={psi}: la linealidad da r = {lin['r_squared']}"

    def test_ctp515_cada_inserto_queda_donde_lo_pone_pylinac(self, medida):
        """<= 0.1 mm (el plan). Antes, a 3 grados en la serie invertida: 6.86 mm."""
        from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
        clave, psi, m = medida
        g = GeometriaCatphan(m["raw"]["ctp515"], m["tam"], orientacion=m["orientacion"], roll_deg=m["R"])
        peor = 0.0
        for app, pyl in LC_APP_A_PYL.items():
            c = m["ct"].ctp515.rois[pyl].center
            xp, yp = _al_marco_crudo(c.x, c.y, m)
            (xa, ya), _ = g.obtener_roi_float(app)
            peor = max(peor, float(np.hypot(xa - xp, ya - yp) * m["tam"]))
        assert peor <= 0.1, f"{clave} psi={psi}: un inserto queda a {peor:.2f} mm de pylinac"

    def test_ctp528_el_anillo_se_muestrea_donde_lo_hace_pylinac(self, medida):
        """Desfase angular del perfil del anillo frente al de pylinac <= 0.2 grados (el plan), por correlacion cruzada del perfil de la banda 46-50 mm. Antes, a 3 grados en la serie
        invertida: -7.9 grados; a 7 grados: -15.7."""
        from analisisImagenes.catphan.orientacion import angulo_en_imagen
        from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
        clave, psi, m = medida
        ct, R = m["ct"], m["R"]
        paso = 0.1
        theta = np.arange(0.0, 360.0, paso)
        pc = ct.ctp528.phan_center
        img_pyl = np.asarray(ct.dicom_stack[int(ct.ctp528.slice_num)].array, dtype=np.float32)
        referencia = _perfil_anillo(img_pyl, pc.x, pc.y, float(ct.mm_per_pixel), theta + R)                 # pylinac: nominal theta -> theta + R en SU marco
        g = GeometriaCatphan(m["raw"]["ctp528"], m["tam"])
        prueba = _perfil_anillo(m["raw"]["ctp528"], g.centro[0], g.centro[1], m["tam"],
                                np.array([angulo_en_imagen(t, m["orientacion"], R) for t in theta]))      # la aplicacion: la transformacion unica
        sector = (theta >= 7.0) & (theta <= 170.0)                                                          # donde la aplicacion define las regiones
        assert abs(_desfase_por_correlacion(referencia, prueba, paso, sector)) <= 0.2, f"{clave} psi={psi}: el anillo se muestrea desfasado"


@pytest.fixture(scope="class", params=CASOS_DE_LA_SERIE_INVERTIDA, ids=[f"{c}-{p:+g}" for c, p in CASOS_DE_LA_SERIE_INVERTIDA])
def medida_invertida(request):
    clave, psi = request.param
    m = _medir(clave, psi)
    yield clave, psi, m
    del m
    gc.collect()


class TestResolucionEspacialConLaSerieInvertida:
    """Revision de OR.1 (H1): la prueba del anillo por correlacion cruzada arma su propio perfil con la funcion unica y no llama a `resolucion_espacial`; sin esto un `resolucion_espacial`
    que calculara la inversa y descartara el resultado (o la pidiera sin la orientacion) pasaba todo. Aqui se mide su RESULTADO sobre el CTP528 real de la serie invertida con el volumen
    girado 0/3/7/15/-7 grados: con la orientacion y el giro de la serie mide las cuatro regiones que tiene (13 picos, 4 lp/cm); sin ellos, 2 a 10 picos y hasta 1 lp/cm."""

    def test_con_la_orientacion_de_la_serie_mide_las_cuatro_regiones(self, medida_invertida):
        from analisisImagenes.Analisis_Catphan_TAC import resolucion_espacial
        clave, psi, m = medida_invertida
        raw = m["raw"]["ctp528"]
        r = _silencio(resolucion_espacial, _ventanear(raw), raw, m["tam"], visualizar=False, orientacion=m["orientacion"], roll_deg=m["R"])
        assert r["resolucion_limite"]["lp_cm_maximo"] == 4 and r["resolucion_limite"]["ultima_region"] == "region 4", (psi, r["resolucion_limite"])
        assert [r["region_results"][f"region {k}"]["status"] for k in (1, 2, 3, 4)] == ["OK"] * 4, psi
        assert r["num_picos"] == 13, f"psi={psi}: {r['num_picos']} picos"

    def test_sin_la_orientacion_no_las_mide(self, medida_invertida):
        """El control que hace discriminar a la anterior: con una orientacion «normal» y sin giro, la misma imagen NO da el resultado de arriba."""
        from analisisImagenes.Analisis_Catphan_TAC import resolucion_espacial
        clave, psi, m = medida_invertida
        raw = m["raw"]["ctp528"]
        r = _silencio(resolucion_espacial, _ventanear(raw), raw, m["tam"], visualizar=False)
        assert r["num_picos"] < 13 and [r["region_results"][f"region {k}"]["status"] for k in (1, 2, 3, 4)] != ["OK"] * 4, psi


# ------------------------------------------------------------- extremo a extremo: la pantalla del fisico con la serie INVERTIDA real
ORDEN_ORO = ("Aire", "PMP", "LDPE", "Poliestireno", "Acrilico", "Delrin", "Teflon")      # el orden de `_catphan_oro.HU_MATERIALES`


@pytest.fixture(autouse=True)
def _hay_qapplication(app):
    """Las pruebas de pantalla construyen widgets: la QApplication tiene que existir antes (Trampa 1)."""
    return app


class TestPantallaConLaSerieInvertida:
    """`QA Halcyon Catphan` (septiembre) llega INVERTIDA 180 grados. Por el camino del fisico (cargar la carpeta, elegir el corte de CTP404 y analizar Valores CT y despues la
    Linealidad), los siete materiales tienen que medirse donde estan: antes de OR.1 seis de siete salian PERMUTADOS (Teflon en -180 HU, PMP en 892) y la linealidad daba r = 0.313."""

    @pytest.fixture
    def pantalla(self, bd_temporal, monkeypatch):
        carpeta = serie_catphan("HALCYON_SEP")
        if not carpeta:
            pytest.skip("sin el corpus real de Catphan (HI-0)")
        visto = []
        for tipo in ("warning", "critical", "information"):
            monkeypatch.setattr(QMessageBox, tipo, lambda parent, titulo, texto, *a, _t=tipo, **k: visto.append((_t, titulo, texto)))
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
        # Valores CT abre un posicionador manual (`dlg.exec_()`, modal) antes de medir: sin esto la prueba espera un clic que nunca llega (Trampa 2).
        monkeypatch.setattr("data.ManejoDatos.catphan_TAC.posicionador_manual.PosicionadorDialogCT.exec_", lambda self: 0)
        monkeypatch.setattr("data.ManejoDatos.catphan_TAC.posicionador_manual.PosicionadorDialog.exec_", lambda self: 0)
        obj = iniciar(FORMULARIOS["tomografo"][0]())
        obj.user_id = "Fisico Real"
        obj.show()
        vis = obj.visualizador_principal
        vis.mostrar_popup_cortes = lambda resultados: None
        vis.confirmador_de_carga = lambda parent, vol, equipo: True
        vis.visualizar_imagen_cargada(carpeta)
        yield obj, vis, dict(vis.cortes)
        vis.vol = None
        obj.corte_seleccionado_info = None
        obj.hide()
        obj.close()
        obj.deleteLater()
        from PyQt5.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()

    def _elegir(self, obj, vis, cortes, indice_toolbox, modulo="CTP404"):
        obj.toolbox.setCurrentIndex(indice_toolbox)
        vis.idx_actual = cortes[modulo]
        vis.elegir_corte()

    def test_la_serie_se_detecta_invertida_y_con_giro(self, pantalla):
        obj, vis, cortes = pantalla
        assert vis.orientacion == "invertido" and abs(vis.roll_deg) > 0.5, (vis.orientacion, vis.roll_deg)

    def test_valores_ct_mide_cada_material_donde_esta(self, pantalla):
        obj, vis, cortes = pantalla
        self._elegir(obj, vis, cortes, 4)                                           # Valores CT
        hu = {d["material"]: d["promedio_hu"] for d in obj.resultados_ct if isinstance(d, dict) and "material" in d}
        assert set(hu) == set(ORDEN_ORO)
        oro = dict(zip(ORDEN_ORO, HU_MATERIALES["HALCYON_SEP"]))
        peor = max(abs(hu[m] - oro[m]) for m in ORDEN_ORO)
        assert peor <= 8.0, f"un material queda a {peor:.1f} HU de pylinac: " + ", ".join(f"{m} {hu[m]:.0f}/{oro[m]:.0f}" for m in ORDEN_ORO)

    def test_la_pantalla_construye_la_geometria_de_ctp404_con_la_orientacion_y_el_giro_de_la_serie(self, pantalla, monkeypatch):
        """Los siete materiales se miden en HU casi iguales con 0.92 grados de giro o sin el (unos pocos HU), asi que los HU solos no delatan que la pantalla olvide el giro: se mira con
        que argumentos se construye la geometria."""
        import data.ManejoDatos.catphan_TAC.posicionador_manual as PM
        obj, vis, cortes = pantalla
        recibidos = []
        original = PM.GeometriaCatphanCT.__init__

        def registra(self, corte_hu, tam_px, orientacion="normal", roll_deg=0.0):
            recibidos.append((orientacion, roll_deg))
            original(self, corte_hu, tam_px, orientacion=orientacion, roll_deg=roll_deg)

        monkeypatch.setattr(PM.GeometriaCatphanCT, "__init__", registra)
        self._elegir(obj, vis, cortes, 4)
        assert vis.roll_deg != 0.0, "la serie tiene giro (si no, la prueba no discrimina)"
        assert recibidos == [(vis.orientacion, vis.roll_deg)], recibidos

    def test_la_pantalla_pasa_la_orientacion_y_el_giro_a_resolucion_espacial(self, pantalla, monkeypatch):
        """Revision de OR.1 (H3): el cableado hacia CTP528 (`resolucion_espacial`) tampoco lo cubria ninguna prueba: quitar los dos argumentos de la llamada de la pantalla dejaba pasar todo."""
        import ui.paginasControles.PruebasMensuales.tac_mensual as tac
        obj, vis, cortes = pantalla
        recibidos = []
        original = tac.resolucion_espacial

        def registra(*a, **k):
            recibidos.append((k.get("orientacion"), k.get("roll_deg")))
            return original(*a, **k)

        monkeypatch.setattr(tac, "resolucion_espacial", registra)
        self._elegir(obj, vis, cortes, 3, "CTP528")                                 # Resolucion espacial
        assert vis.roll_deg != 0.0 and recibidos == [(vis.orientacion, vis.roll_deg)], recibidos
        limite = obj.resultados_resolucion_espacial["resolucion_limite"]
        assert limite["lp_cm_maximo"] == 4, f"la serie invertida mide {limite} (con la orientacion bien puesta son 4 lp/cm)"

    def test_la_pantalla_pasa_la_orientacion_y_el_giro_a_la_geometria_y_a_resolucion_de_contraste(self, pantalla, monkeypatch):
        """Revision de OR.1 (H3): CTP515 recibe la orientacion y el giro por DOS caminos —la geometria que el posicionador ajusta y los argumentos aparte de `resolucion_contraste`,
        que usan los fondos— y los dos tienen que ser los de la serie."""
        import ui.paginasControles.PruebasMensuales.tac_mensual as tac
        obj, vis, cortes = pantalla
        recibidos = []
        original = tac.resolucion_contraste

        def registra(*a, **k):
            g = k.get("catphan")
            recibidos.append(((g.orientacion, g.roll_deg), (k.get("orientacion"), k.get("roll_deg"))))
            return original(*a, **k)

        monkeypatch.setattr(tac, "resolucion_contraste", registra)
        self._elegir(obj, vis, cortes, 2, "CTP515")                                 # Resolucion de contraste
        esperado = (vis.orientacion, vis.roll_deg)
        assert vis.roll_deg != 0.0 and recibidos == [(esperado, esperado)], recibidos

    def test_la_linealidad_de_la_serie_invertida_ya_es_lineal(self, pantalla):
        obj, vis, cortes = pantalla
        self._elegir(obj, vis, cortes, 4)                                           # Valores CT (de donde salen los HU)
        self._elegir(obj, vis, cortes, 5)                                           # Linealidad CT
        r = obj.resultados_linealidad_ct
        assert r and r["r_squared"] >= 0.99, f"r = {r and r['r_squared']} (antes de OR.1: 0.313)"

