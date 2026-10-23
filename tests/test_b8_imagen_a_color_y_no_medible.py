"""B.8 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-88, P8): la imagen de la posicion inicial de braquiterapia a color y «no medible» en la ventana del mensual.

CAUSA (DA-88, 22-10). (a) La pestana «Imagen» de la pagina de la posicion inicial pinta el GRIS en los tres canales (`np.dstack([gris8, gris8, gris8])`) y es en esa pestana donde el fisico marca los dos puntos: el pidio la
pelicula a color, la original. (b) La ventana del analisis mensual escribe «sin dato» (`dibujo_placa_mensual.numero(None)` y `_par`) para todo valor que no se midio: el fisico decidio que diga «no medible».
Es presentacion: el MOTOR sigue midiendo sobre el gris, ninguna medida ni nada de lo que se guarda cambia.

Que fija este archivo (todo por el camino del usuario: la pagina real, el boton «Seleccionar imagen» real, el escritor real del servicio y una BD temporal; nunca una BD de referencia):
  1. `imagen_rgb` vive en `analisisImagenes/pelicula.py` con el MISMO cuerpo (`ast.dump` igual al que tenia en el dibujo del mensual), `dibujo_placa_mensual` la re-exporta con el mismo nombre (el mismo objeto), hay UNA sola
     definicion en todo el arbol de produccion y los tres llamadores de la ventana del mensual siguen siendo `dibujo.imagen_rgb(...)`. Devuelve el RGB del archivo (en 8 bits, los mismos valores; en 16, los niveles de 8
     bits REDONDEADOS) con los canales en su orden (R, G, B): la verdad es PIL, un decodificador independiente de OpenCV (en las tres peliculas reales decodifican bit a bit lo mismo, medido).
  2. LOS DOS CAMINOS. Al CARGAR una imagen y al ABRIR un registro la pestana «Imagen» muestra el RGB del archivo, pixel a pixel (EPSON009, braqui_00, EPSON031, una de 16 bits y dos con alfa), `uint8`, con `nearest`; cada
     camino se prueba POR SEPARADO (una mutacion que deja uno solo en gris cae en el suyo). Los puntos siguen dibujandose encima.
  3. LO QUE RECIBE `_instalar_imagen`. El gris, el dpi y la fecha son BIT A BIT los de `motor.leer_imagen` (mismo tipo y mismos valores), y la `Pelicula` que recibe da, con `en_bgr()`, el mismo gris y el mismo color: la pagina
     decodifica UNA vez (cargar: 1; abrir: 2, la suya y la del servicio que recalcula, como en HEAD) y no guarda la `Pelicula` (ni un atributo nuevo, ni una `Pelicula` viva al terminar; «Limpiar» sigue dejando una pagina
     recien creada). La firma gana `pelicula=None` (corolario: valor por omision que reproduce la conducta de hoy: el gris en los tres canales) y los DOS llamadores de la pagina lo pasan (AST).
  4. EL MOTOR SIGUE MIDIENDO SOBRE EL GRIS: los numeros de control de las tres peliculas reales (los de PI.1) salen iguales por la pagina.
  5. «NO MEDIBLE» en la ventana del mensual: `numero(None)` y `_par` (con alguno de los dos None) dicen «no medible» y `SIN_DATO` se retiro; cada tabla de la ventana con un valor no medido (la capa roja a 800 UM no se mide
     en netOD) dice «no medible» exactamente donde el motor no midio y ninguna dice «sin dato»; ningun texto de la ventana entera (con la pelicula sintetica A, cuyos perfiles encuentran todos su borde) dice «sin dato».
  6. LO QUE NO CAMBIA (declarado): «pixeles transparentes, que son sin dato» (A.1: describe pixeles), el motivo del motor de un perfil que no encuentra su borde («...o a una zona sin dato antes de cruzar la altura
     media»: es parte del `estado` que se guarda y describe una zona, no un valor que no se midio) y el `SIN_DATO` del PDF de braqui (zona roja).
  7. RONDA 1 DE LA REVISION (23-10). B8-R1-02: el punto 5 vale para una pelicula donde todo perfil encuentra su borde (el nombre de la prueba lo dice y su premisa lo comprueba); con una pelicula cortada donde un
     perfil NO lo encuentra (8c, en valor de pixel: en netOD estas escenas no llegan a la frase), la frase del motor llega TAL CUAL a la celda del estado de cada uno de esos perfiles y, quitada la frase, ningun texto
     de la ventana dice «sin dato»; los valores que el motor no dio dicen «no medible» tambien ahi. B8-R1-01: la tabla de valores del cuadro «Pelicula virgen...» de una referencia RECHAZADA (8b) no dice
     «no medible» (la pelicula SI se midio: el resumen cita sus cifras y la uniformidad muestra su centro) sino la palabra del estado de cada capa, «no válida», en el valor, los pixeles y la dispersion.

Trampa 2 (todo QMessageBox y todo dialogo se parcha: la fixture `dialogos` de PI.4), Trampa 9 (las paginas y las ventanas se cierran con la receta completa), Trampa 10 (ningun `lru_cache` ni contenedor de modulo que una
funcion llene: los resultados caros son fixtures de modulo y nadie los muta). Los textos de las pruebas no llevan simbolos de correcto o incorrecto (DA-18)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import dataclasses
import gc
import inspect
import io
import re
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

import _placa_braqui_sintetica as gen_braqui
import _placa_mensual_sintetica as gen_mensual
import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod
from _e1_ayudas import TAM, analizada, cerrar, escaneo_virgen, parametros, resultado_directo, todos_los_textos, ventana_mod  # noqa: F401  (`escaneo_virgen`: fixture de E.1)
from analisisImagenes import dibujo_placa_mensual as dibujo
from analisisImagenes import placa_mensual as pm
from analisisImagenes import pelicula as pel
from analisisImagenes import posicion_inicial_braqui as motor
from services import posicion_inicial_braqui as svc
from test_a1_lector_de_peliculas import _alfa, _codificar, _planos
from test_c2_perfiles_y_coincidencia import medir as medir_perfil_a_mano, perfil_erf       # un perfil de dosis ideal y el motor real que lo mide (C.2)
from test_d1_guardado_placa_mensual import _control
from test_pi1_motor_posicion_inicial import CLICS_EPSON009, CLICS_EPSON031, CLICS_PLACA_REAL
from test_pi3_servicio_posicion_inicial import DATOS, USUARIO, _consulta, bd, plantilla  # noqa: F401  (fixtures de PI.3)
from test_pi4_pagina_posicion_inicial import (_cargar, _cursor_limpio, _huella, _marcar, app, dialogos, fabrica,  # noqa: F401  (fixtures y ayudas de PI.4)
                                              pagina)

RAIZ = Path(__file__).resolve().parent.parent
PELICULA_PY = RAIZ / "analisisImagenes" / "pelicula.py"
DIBUJO_PY = RAIZ / "analisisImagenes" / "dibujo_placa_mensual.py"
PAGINA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "posicion_inicial_braqui.py"
VENTANA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "placa_mensual.py"
BLOQUE_PDF_PY = RAIZ / "models" / "PDF" / "bloque_posicion_inicial.py"
EQUIPO = "Clinac de prueba"
FLAGS_DE_LA_PRIMERA_LECTURA = cv2.IMREAD_UNCHANGED | cv2.IMREAD_IGNORE_ORIENTATION        # la primera de las tres lecturas de `leer_pelicula`: una por pelicula decodificada

# Las tres peliculas reales del plan, con los numeros de control del gris (PI.1: lo que mide el motor sobre el gris, con los clics de la suite). Escritos aqui a mano: el ancla EXTERNA del motor.
REALES = {
    "EPSON009": dict(archivo="EPSON009.jpeg", clics=CLICS_EPSON009, desfase_px=-2.603247238117774, desfase_mm=-0.11020413308031911, capas={"R": 3.8303270806542287, "G": -2.3023533771105065, "B": -3.343512347861463}),
    "braqui_00": dict(archivo="braqui_00.jpeg", clics=CLICS_PLACA_REAL, desfase_px=-8.553322072889898, desfase_mm=-0.3620906344190057, capas={}),
    "EPSON031": dict(archivo="EPSON031.JPG", clics=CLICS_EPSON031, desfase_px=-8.471734685899605, desfase_mm=-0.35863676836974995, capas={}),
}

# El cuerpo de `imagen_rgb` TAL COMO ESTABA en `dibujo_placa_mensual.py` en HEAD 85c9e14 (la prueba de «mismo cuerpo»: el `ast.dump` de la funcion que vive hoy en `pelicula.py` es identico al de este texto).
CUERPO_DE_HEAD = '''def imagen_rgb(pelicula):
    """La película como RGB uint8 (alto, ancho, 3) para mostrarla en su color original. En 8 bits son los mismos valores del archivo (el color BGR de OpenCV puesto en orden R, G, B, una sola copia); en 16 bits,
    los niveles de 8 bits redondeados de cada capa (así se muestra la de 16 bits, A.1). Un RGB uint8 con `nearest` cuesta 101 MB para una página del escáner (6600 x 5100); un gris 2D con mapa de color, 2 GB."""
    if pelicula.bits == 8:
        _gris, bgr = pelicula.en_bgr()
        return np.ascontiguousarray(bgr[:, :, ::-1])
    rgb = np.empty(pelicula.validos.shape + (3,), np.uint8)
    for k, capa in enumerate(CAPAS):
        rgb[:, :, k] = np.clip(np.rint(getattr(pelicula, capa)), 0, 255)
    return rgb
'''


# ------------------------------------------------------------------------------------------------------ ayudas

def _bytes(nombre):
    return (DATOS / nombre).read_bytes()


def rgb_del_archivo(datos):
    """El RGB del archivo segun PIL, un decodificador INDEPENDIENTE de OpenCV (medido en B.8: en las tres peliculas reales decodifican bit a bit lo mismo, 0 pixeles distintos)."""
    with Image.open(io.BytesIO(datos)) as imagen:
        return np.asarray(imagen.convert("RGB"))


def niveles_de_8_bits(v):
    """Verdad independiente de la conversion de 16 bits: valor x 255 / 65535 REDONDEADO (en float64; los empates no existen: la fraccion mas cercana a .5 es 128/257, a 0.002 de el)."""
    return np.clip(np.rint(v.astype(np.float64) * 255.0 / 65535.0), 0, 255).astype(np.uint8)


def _tres_canales_distintos(forma=(24, 40)):
    """RGB de 16 bits con los tres canales DISTINTOS y cuyos niveles de 8 bits caen siempre en k + 0.778 (v = 257 k + 200): redondear los sube un nivel y truncar no. Devuelve (v, k)."""
    k = np.random.default_rng(5).integers(0, 255, forma + (3,)).astype(np.uint16)
    k[0, 0] = (50, 100, 200)
    return (k * 257 + 200).astype(np.uint16), k


def _archivo(tmp_path, nombre, datos, dia=(2026, 9, 30)):
    """Un archivo con la fecha de modificacion que DD7 usa para proponer el cambio de fuente (por omision 2026-09-30, tres dias despues de `CAMBIO`). Una prueba que mira la FECHA que recibe `_instalar_imagen`
    pide otro dia: si el archivo declara la suya (EXIF o etiqueta del TIFF) es esa y no la de modificacion, y solo asi se ve que la fecha del escaneo llega."""
    ruta = tmp_path / nombre
    ruta.write_bytes(datos)
    marca = datetime(*dia, 12, 0).timestamp()
    os.utime(ruta, (marca, marca))
    return str(ruta)


def mostrada(p):
    """La imagen que la pestana «Imagen» muestra HOY (una sola en el eje)."""
    imagenes = p.eje_imagen.images
    assert len(imagenes) == 1, f"el eje de la imagen tiene {len(imagenes)} imagenes"
    return np.asarray(imagenes[0].get_array())


def es_gris(rgb):
    return bool((rgb[:, :, 0] == rgb[:, :, 1]).all() and (rgb[:, :, 1] == rgb[:, :, 2]).all())


@pytest.fixture(scope="module")
def placa_braqui():
    """La placa sintetica independiente del motor (PF.0) de la posicion inicial: 672 x 1156, PNG, con su verdad (los clics que la miden)."""
    return gen_braqui.generar_independiente(0.8, formato="png")


@pytest.fixture(scope="module")
def placa_mensual():
    """La pelicula sintetica A de PF.0 del analisis mensual (un PNG de 8 bits a 600 dpi, ~9 MB). En netOD (la base por omision) la capa roja esta recortada: no se mide."""
    return gen_mensual.generar("png", variante="A", seed=1)


@pytest.fixture
def instalaciones(monkeypatch):
    """Cada llamada a `PosicionInicialBraqui._instalar_imagen` como {nombre del parametro: valor} (la verdadera se ejecuta). Sirve para mirar lo que los dos llamadores le pasan sin depender de la forma de la firma."""
    llamadas = []
    real = pagina_mod.PosicionInicialBraqui._instalar_imagen

    def espia(self, *args, **kwargs):
        llamadas.append(dict(inspect.signature(real).bind(self, *args, **kwargs).arguments))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(pagina_mod.PosicionInicialBraqui, "_instalar_imagen", espia)
    return llamadas


@pytest.fixture
def decodificaciones(monkeypatch):
    """Cuantas peliculas se decodifican (UNA por cada primera lectura de `leer_pelicula`: `cv2.imdecode(..., IMREAD_UNCHANGED)`)."""
    cuenta = {"n": 0}
    real = cv2.imdecode

    def espia(buf, flags):
        if flags == FLAGS_DE_LA_PRIMERA_LECTURA:
            cuenta["n"] += 1
        return real(buf, flags)

    monkeypatch.setattr(cv2, "imdecode", espia)
    return cuenta


def _guardar_y_limpiar(p, dialogos, bd, ruta, clics):
    """El fisico abre la imagen, marca los dos puntos, guarda y limpia la pagina. Devuelve el id del registro guardado."""
    _cargar(p, dialogos, ruta)
    _marcar(p, clics)
    assert p.estado == "analizada", p.estado
    p.boton_guardar.click()
    assert p.estado == "registro", p.estado
    filas = _consulta(bd, "SELECT id FROM braqui_posicion_inicial WHERE activo = 1")
    assert len(filas) == 1
    p.boton_limpiar.click()
    assert p.estado == "vacia" and not p.eje_imagen.images
    return filas[0][0]


def _imagenes_del_caso(tmp_path, caso, placa_braqui, dia=(2026, 9, 30)):
    """(ruta del archivo, bytes, el RGB que la pagina debe mostrar, clics que la miden o None) de cada imagen que el plan pide: las tres reales, una de 16 bits y dos con alfa."""
    if caso in REALES:
        r = REALES[caso]
        datos = _bytes(r["archivo"])
        return _archivo(tmp_path, r["archivo"], datos, dia), datos, rgb_del_archivo(datos), r["clics"]
    if caso == "16 bits":
        v = placa_braqui.imagen[:, :, ::-1].astype(np.uint16) * 257 + 3
        datos = _codificar("tiff", 16, v)
        return _archivo(tmp_path, "placa16.tif", datos, dia), datos, niveles_de_8_bits(v), placa_braqui.clics
    if caso == "alfa 8":
        rgb = np.ascontiguousarray(placa_braqui.imagen[:, :, ::-1])
        alfa = np.full(rgb.shape[:2], 255, np.uint8)
        alfa[:12, :12] = 0                                                  # un bloque transparente lejos de la mancha y de la linea
        datos = _codificar("png", 8, rgb, alfa=alfa)
        return _archivo(tmp_path, "placa_alfa.png", datos, dia), datos, rgb, placa_braqui.clics
    raise AssertionError(caso)


CASOS = list(REALES) + ["16 bits", "alfa 8"]


# ======================================================================================================== 1. imagen_rgb vive en pelicula.py

class TestImagenRgbVivePorUnaSolaDefinicionEnPelicula:
    def test_imagen_rgb_existe_en_pelicula(self):
        assert callable(getattr(pel, "imagen_rgb", None)), "analisisImagenes.pelicula.imagen_rgb no existe"

    def test_el_cuerpo_es_el_mismo_que_tenia_en_el_dibujo_del_mensual(self):
        """El plan pide el MISMO cuerpo: el `ast.dump` de la funcion (con su docstring) es identico al de HEAD."""
        esperado = ast.dump(ast.parse(CUERPO_DE_HEAD).body[0])
        nodos = [n for n in ast.parse(PELICULA_PY.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == "imagen_rgb"]
        assert len(nodos) == 1, "pelicula.py tiene que definir imagen_rgb exactamente una vez"
        assert ast.dump(nodos[0]) == esperado

    def test_el_dibujo_la_reexporta_con_el_mismo_nombre_y_es_el_mismo_objeto(self):
        assert dibujo.imagen_rgb is pel.imagen_rgb
        assert dibujo.imagen_rgb.__module__ == "analisisImagenes.pelicula" and dibujo.imagen_rgb.__name__ == "imagen_rgb"

    def test_en_todo_el_arbol_de_produccion_hay_una_sola_definicion(self):
        definiciones, leidos = [], 0
        for ruta in sorted(RAIZ.rglob("*.py")):
            partes = ruta.relative_to(RAIZ).parts
            if partes[0] in {".venv", "build", "dist", "tests", "__pycache__", ".git"}:
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            leidos += 1
            definiciones += [str(ruta.relative_to(RAIZ)) for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "imagen_rgb"]
        assert leidos >= 100, "compuerta de no vacuidad: el censo lee el arbol de produccion"
        assert definiciones == ["analisisImagenes/pelicula.py"], definiciones

    def test_los_tres_llamadores_de_la_ventana_del_mensual_siguen_siendo_dibujo_imagen_rgb(self):
        """Sus tres llamadores (abrir, elegir y reabrir) no cambian: `dibujo.imagen_rgb(...)` por la re-exportacion."""
        llamadas = [n for n in ast.walk(ast.parse(VENTANA_PY.read_text(encoding="utf-8")))
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "imagen_rgb"]
        assert len(llamadas) == 3
        assert all(isinstance(n.func.value, ast.Name) and n.func.value.id == "dibujo" for n in llamadas)


# ======================================================================================================== 1b. lo que devuelve

class TestImagenRgbDevuelveElColorDelArchivo:
    @pytest.mark.parametrize("nombre", list(REALES))
    def test_en_8_bits_son_los_valores_del_archivo_en_orden_r_g_b(self, nombre):
        datos = _bytes(REALES[nombre]["archivo"])
        rgb = pel.imagen_rgb(pel.leer_pelicula(datos))
        esperado = rgb_del_archivo(datos)
        assert rgb.dtype == np.uint8 and rgb.shape == esperado.shape and rgb.flags["C_CONTIGUOUS"]
        assert np.array_equal(rgb, esperado), "el RGB del archivo (PIL), pixel a pixel"
        assert not es_gris(rgb), "compuerta: la pelicula real tiene color"

    def test_los_canales_no_se_cruzan(self):
        """Un color con tres canales distintos (R 200, G 100, B 50): las capas cruzadas (BGR) se ven."""
        rgb = np.empty((6, 8, 3), np.uint8)
        rgb[:] = (200, 100, 50)
        salida = pel.imagen_rgb(pel.leer_pelicula(_codificar("png", 8, rgb)))
        assert salida.dtype == np.uint8 and (salida == (200, 100, 50)).all()

    def test_la_salida_es_una_copia_contigua_y_no_una_vista_de_la_pelicula(self):
        pelicula = pel.leer_pelicula(_bytes("braqui_00.jpeg"))
        rgb = pel.imagen_rgb(pelicula)
        assert rgb.flags["C_CONTIGUOUS"] and not np.shares_memory(rgb, pelicula.en_bgr()[1])

    def test_en_16_bits_son_los_niveles_de_8_bits_redondeados_de_cada_capa(self):
        v, k = _tres_canales_distintos()
        assert np.array_equal(niveles_de_8_bits(v), k + 1), "premisa de la prueba: redondear sube un nivel y truncar no"
        rgb = pel.imagen_rgb(pel.leer_pelicula(_codificar("tiff", 16, v)))
        assert rgb.dtype == np.uint8 and rgb.shape == v.shape
        assert np.array_equal(rgb, k + 1), "redondeado (truncado dejaria k)"
        assert (rgb[0, 0] == (51, 101, 201)).all(), "R, G y B en su orden"

    def test_en_16_bits_con_canales_independientes_coincide_con_la_verdad(self):
        v = _planos(16, forma=(40, 60), semilla=3)
        rgb = pel.imagen_rgb(pel.leer_pelicula(_codificar("tiff", 16, v)))
        assert np.array_equal(rgb, niveles_de_8_bits(v))

    @pytest.mark.parametrize("formato,bits", [("png", 8), ("tiff", 16)])
    def test_el_alfa_no_entra_en_la_imagen_mostrada(self, formato, bits):
        rgb = _planos(bits, forma=(24, 40), semilla=1)
        salida = pel.imagen_rgb(pel.leer_pelicula(_codificar(formato, bits, rgb, alfa=_alfa(bits))))
        assert salida.shape == (24, 40, 3)
        assert np.array_equal(salida, rgb if bits == 8 else niveles_de_8_bits(rgb))


# ======================================================================================================== 2. la pagina: CARGAR

class TestLaPaginaMuestraElColorAlCargar:
    @pytest.mark.parametrize("caso", CASOS)
    def test_cargar_muestra_el_rgb_del_archivo_pixel_a_pixel(self, caso, pagina, dialogos, tmp_path, placa_braqui):
        ruta, _datos, esperado, _clics = _imagenes_del_caso(tmp_path, caso, placa_braqui)
        _cargar(pagina, dialogos, ruta)
        assert pagina.estado == "imagen" and not dialogos.de("warning")
        vista = mostrada(pagina)
        assert vista.dtype == np.uint8 and vista.shape == esperado.shape and pagina.eje_imagen.images[0].get_interpolation() == "nearest"
        assert not es_gris(vista), "la pestana «Imagen» no se ve en gris"
        assert np.array_equal(vista, esperado)

    @pytest.mark.parametrize("caso", list(REALES))
    def test_cargar_deja_igual_lo_que_no_es_la_imagen(self, caso, pagina, dialogos, tmp_path, placa_braqui):
        ruta, datos, _esperado, _clics = _imagenes_del_caso(tmp_path, caso, placa_braqui)
        _cargar(pagina, dialogos, ruta)
        alto, ancho = rgb_del_archivo(datos).shape[:2]
        assert pagina._forma == (alto, ancho) and pagina._bytes == datos and pagina.nombre_archivo.text() == os.path.basename(ruta)
        assert pagina._resultado is None and pagina.puntos == () and not pagina.boton_guardar.isEnabled()

    def test_los_puntos_siguen_dibujandose_encima_de_la_imagen_a_color(self, pagina, dialogos, tmp_path, placa_braqui):
        ruta, _d, esperado, clics = _imagenes_del_caso(tmp_path, "braqui_00", placa_braqui)
        _cargar(pagina, dialogos, ruta)
        _marcar(pagina, clics)
        assert pagina.estado == "analizada" and len(pagina.eje_imagen.lines) == 2, "un clic = una marca"
        for marca, (x, y) in zip(pagina.eje_imagen.lines, clics):
            assert marca.get_zorder() > pagina.eje_imagen.images[0].get_zorder() and (marca.get_xdata()[0], marca.get_ydata()[0]) == (float(x), float(y))
            assert marca.get_color() == pagina_mod.COLOR_REFERENCIA
        assert np.array_equal(mostrada(pagina), esperado), "marcar no toca la imagen"

    def test_limpiar_con_la_imagen_a_color_deja_una_pagina_recien_creada(self, fabrica, dialogos, tmp_path, placa_braqui):
        ruta, _d, _e, clics = _imagenes_del_caso(tmp_path, "EPSON009", placa_braqui)
        p = fabrica()
        _cargar(p, dialogos, ruta)
        _marcar(p, clics)
        assert p.estado == "analizada"
        p.boton_limpiar.click()
        assert _huella(p) == _huella(fabrica()), "corolario 3: Limpiar = una pagina recien creada (nada de la imagen a color queda)"


# ======================================================================================================== 3. la pagina: ABRIR un registro

class TestLaPaginaMuestraElColorAlAbrir:
    @pytest.mark.parametrize("caso", CASOS)
    def test_abrir_un_registro_muestra_el_rgb_de_lo_guardado_pixel_a_pixel(self, caso, pagina, dialogos, bd, tmp_path, placa_braqui):
        ruta, _datos, esperado, clics = _imagenes_del_caso(tmp_path, caso, placa_braqui)
        id_registro = _guardar_y_limpiar(pagina, dialogos, bd, ruta, clics)
        assert pagina.abrir_registro(id_registro) is True and pagina.estado == "registro", dialogos.de("warning")
        vista = mostrada(pagina)
        assert vista.dtype == np.uint8 and pagina.eje_imagen.images[0].get_interpolation() == "nearest"
        assert not es_gris(vista), "al abrir un registro la pestana «Imagen» tampoco se ve en gris"
        assert np.array_equal(vista, esperado)
        assert len(pagina.eje_imagen.lines) == 2, "los dos puntos guardados se dibujan encima"

    def test_abrir_con_un_registro_cuya_imagen_es_de_16_bits_tambien_es_a_color(self, pagina, dialogos, bd, tmp_path, placa_braqui):
        """Era lo que fijaba test_a1 (el gris redondeado en los tres canales): ahora son los niveles de 8 bits redondeados de CADA capa."""
        ruta, _d, esperado, clics = _imagenes_del_caso(tmp_path, "16 bits", placa_braqui)
        id_registro = _guardar_y_limpiar(pagina, dialogos, bd, ruta, clics)
        assert pagina.abrir_registro(id_registro) is True
        vista = mostrada(pagina)
        canales = [vista[:, :, k] for k in range(3)]
        assert not (np.array_equal(canales[0], canales[1]) and np.array_equal(canales[1], canales[2]))
        assert np.array_equal(vista, esperado)


# ======================================================================================================== 4. lo que recibe _instalar_imagen

class TestLoQueRecibeInstalarImagenEsLoDeSiempreMasLaPelicula:
    @pytest.mark.parametrize("caso", CASOS)
    def test_cargar_pasa_el_gris_el_dpi_y_la_fecha_de_leer_imagen_bit_a_bit_y_la_pelicula(self, caso, pagina, dialogos, instalaciones, tmp_path, placa_braqui):
        ruta, datos, _e, _c = _imagenes_del_caso(tmp_path, caso, placa_braqui, dia=(2020, 1, 2))      # otro dia que el de la fecha que declaran las peliculas reales
        gris, color, dpi, fecha = motor.leer_imagen(datos)
        _cargar(pagina, dialogos, ruta)
        assert len(instalaciones) == 1
        recibido = instalaciones[0]
        assert recibido["gris"].dtype == gris.dtype and np.array_equal(recibido["gris"], gris)
        assert recibido["dpi"] == dpi
        assert recibido["fecha"] == (fecha if fecha is not None else date(2020, 1, 2)), "la fecha del escaneo si el archivo la declara y, si no, la de modificacion"
        assert recibido["datos"] == datos and recibido["nombre"] == os.path.basename(ruta)
        self._la_pelicula_es_la_de_los_mismos_bytes(recibido.get("pelicula"), gris, color, dpi, fecha)

    @pytest.mark.parametrize("caso", ["EPSON009", "braqui_00", "16 bits", "alfa 8"])
    def test_abrir_pasa_el_gris_el_dpi_y_la_fecha_de_leer_imagen_bit_a_bit_y_la_pelicula(self, caso, pagina, dialogos, bd, instalaciones, tmp_path, placa_braqui):
        ruta, datos, _e, clics = _imagenes_del_caso(tmp_path, caso, placa_braqui)
        id_registro = _guardar_y_limpiar(pagina, dialogos, bd, ruta, clics)
        instalaciones.clear()
        gris, color, dpi, fecha = motor.leer_imagen(datos)
        assert pagina.abrir_registro(id_registro) is True
        assert len(instalaciones) == 1
        recibido = instalaciones[0]
        assert recibido["gris"].dtype == gris.dtype and np.array_equal(recibido["gris"], gris)
        assert recibido["dpi"] == dpi and recibido["fecha"] is None and recibido["origen_fecha"] is None
        assert recibido["datos"] == datos
        self._la_pelicula_es_la_de_los_mismos_bytes(recibido.get("pelicula"), gris, color, dpi, fecha)

    @staticmethod
    def _la_pelicula_es_la_de_los_mismos_bytes(pelicula, gris, color, dpi, fecha):
        assert isinstance(pelicula, pel.Pelicula), "_instalar_imagen recibe la Pelicula ademas del gris"
        g2, c2 = pelicula.en_bgr()
        assert g2.dtype == gris.dtype and np.array_equal(g2, gris) and c2.dtype == color.dtype and np.array_equal(c2, color)
        assert pelicula.dpi == dpi and pelicula.fecha_escaneo == fecha


# ======================================================================================================== 5. sin decodificar dos veces, sin guardar la Pelicula

class TestSinDecodificarDosVecesNiGuardarLaPelicula:
    def test_cargar_decodifica_la_pelicula_una_sola_vez(self, pagina, dialogos, decodificaciones, tmp_path, placa_braqui):
        ruta, _d, _e, _c = _imagenes_del_caso(tmp_path, "EPSON009", placa_braqui)
        _cargar(pagina, dialogos, ruta)
        assert pagina.estado == "imagen" and decodificaciones["n"] == 1

    def test_abrir_decodifica_dos_veces_la_suya_y_la_del_servicio_que_recalcula_como_en_head(self, pagina, dialogos, bd, decodificaciones, tmp_path, placa_braqui):
        ruta, _d, _e, clics = _imagenes_del_caso(tmp_path, "braqui_00", placa_braqui)
        id_registro = _guardar_y_limpiar(pagina, dialogos, bd, ruta, clics)
        decodificaciones["n"] = 0
        assert pagina.abrir_registro(id_registro) is True
        assert decodificaciones["n"] == 2, "una para leer lo que se muestra y otra en el servicio que recalcula: B.8 no suma una tercera"

    def test_la_pagina_no_guarda_la_pelicula(self, fabrica, dialogos, tmp_path, placa_braqui):
        ruta, _d, _e, _c = _imagenes_del_caso(tmp_path, "EPSON031", placa_braqui)
        nueva = fabrica()
        p = fabrica()
        gc.collect()
        antes = sum(isinstance(o, pel.Pelicula) for o in gc.get_objects())
        _cargar(p, dialogos, ruta)
        assert p.estado == "imagen"
        gc.collect()
        assert sum(isinstance(o, pel.Pelicula) for o in gc.get_objects()) == antes, "queda una Pelicula viva despues de cargar"
        assert not [n for n, v in vars(p).items() if isinstance(v, pel.Pelicula)]
        assert set(vars(p)) == set(vars(nueva)), "la pagina no gana ningun atributo por mostrar el color"

    def test_la_pagina_no_guarda_la_pelicula_al_abrir_un_registro(self, fabrica, dialogos, bd, tmp_path, placa_braqui):
        ruta, _d, _e, clics = _imagenes_del_caso(tmp_path, "EPSON009", placa_braqui)
        p = fabrica()
        id_registro = _guardar_y_limpiar(p, dialogos, bd, ruta, clics)
        gc.collect()
        antes = sum(isinstance(o, pel.Pelicula) for o in gc.get_objects())
        assert p.abrir_registro(id_registro) is True
        gc.collect()
        assert sum(isinstance(o, pel.Pelicula) for o in gc.get_objects()) == antes
        assert set(vars(p)) == set(vars(fabrica()))


# ======================================================================================================== 6. el motor sigue midiendo sobre el gris

class TestElMotorSigueMidiendoSobreElGris:
    @pytest.mark.parametrize("nombre", list(REALES))
    def test_los_numeros_de_control_del_gris_salen_iguales_por_la_pagina_a_color(self, nombre, pagina, dialogos, tmp_path, placa_braqui):
        ruta, _d, _e, clics = _imagenes_del_caso(tmp_path, nombre, placa_braqui)
        control = REALES[nombre]
        _cargar(pagina, dialogos, ruta)
        _marcar(pagina, clics)
        assert pagina.estado == "analizada"
        gris = pagina._resultado["perfiles"]["gris"]
        assert gris["estado"] == "ok" and gris["desfase_px"] == pytest.approx(control["desfase_px"], abs=1e-9)
        assert motor.valores_medidos(pagina._resultado)["desfase_gris_mm"] == pytest.approx(control["desfase_mm"], abs=1e-9)
        assert pagina.recuadro_gris.text().startswith(f"Desfase en la imagen: {control['desfase_px']:.2f} px = {control['desfase_mm']:.3f} mm")
        for capa, px in control["capas"].items():
            assert pagina._resultado["perfiles"][capa]["desfase_px"] == pytest.approx(px, abs=1e-9), capa

    def test_la_pagina_y_el_servicio_dan_lo_mismo_con_la_imagen_a_color(self, pagina, dialogos, tmp_path, placa_braqui):
        ruta, datos, _e, clics = _imagenes_del_caso(tmp_path, "EPSON009", placa_braqui)
        _cargar(pagina, dialogos, ruta)
        _marcar(pagina, clics)
        esperado = svc.analizar_imagen(datos, clics)
        for capa in ("gris", "R", "G", "B"):
            assert pagina._resultado["perfiles"][capa]["desfase_px"] == esperado["perfiles"][capa]["desfase_px"], capa


# ======================================================================================================== 7. los dos llamadores y la firma (AST)

class _Llamadas(ast.NodeVisitor):
    """Las llamadas a `<algo>._instalar_imagen(...)` y el nombre de la funcion que las contiene (la mas interna)."""

    def __init__(self):
        self.pila, self.llamadas = [], []

    def visit_FunctionDef(self, nodo):
        self.pila.append(nodo.name)
        self.generic_visit(nodo)
        self.pila.pop()

    def visit_Call(self, nodo):
        if isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "_instalar_imagen":
            self.llamadas.append((self.pila[-1] if self.pila else None, nodo))
        self.generic_visit(nodo)


class TestLosDosLlamadoresPasanLaPelicula:
    def test_la_pagina_tiene_exactamente_dos_llamadas_y_las_dos_pasan_la_pelicula(self):
        visita = _Llamadas()
        visita.visit(ast.parse(PAGINA_PY.read_text(encoding="utf-8")))
        assert sorted(nombre for nombre, _ in visita.llamadas) == ["_al_seleccionar_imagen", "abrir_registro"]
        for nombre, llamada in visita.llamadas:
            pasa_la_pelicula = len(llamada.args) >= 7 or "pelicula" in {k.arg for k in llamada.keywords}
            assert pasa_la_pelicula, f"{nombre} no le pasa la Pelicula a _instalar_imagen (la dejaria en gris)"

    def test_la_firma_gana_pelicula_con_valor_por_omision_y_conserva_el_orden_de_siempre(self):
        parametros = list(inspect.signature(pagina_mod.PosicionInicialBraqui._instalar_imagen).parameters.values())
        assert [p.name for p in parametros][:7] == ["self", "datos", "nombre", "gris", "dpi", "fecha", "origen_fecha"]
        assert [p.name for p in parametros][7:] == ["pelicula"] and parametros[-1].default is None, "todo parametro nuevo lleva un valor por omision que reproduce la conducta de hoy"

    def test_sin_la_pelicula_la_conducta_de_hoy_se_conserva_el_gris_en_los_tres_canales(self, pagina, dialogos):
        datos = _bytes("braqui_00.jpeg")
        gris, _color, dpi, fecha = motor.leer_imagen(datos)
        pagina._instalar_imagen(datos, "braqui_00.jpeg", gris, dpi, fecha, "fecha del escaneo")
        vista = mostrada(pagina)
        assert es_gris(vista) and np.array_equal(vista[:, :, 0], gris) and vista.dtype == np.uint8 and pagina.estado == "imagen"

    def test_sin_la_pelicula_la_de_16_bits_se_muestra_en_uint8_con_los_niveles_de_8_bits_redondeados(self, pagina, dialogos):
        """La rama sin Pelicula conserva TAMBIEN la conversion de hoy para una imagen de 16 bits (su gris llega en float32 de 0 a 255): uint8 y REDONDEADO, no truncado ni en float32 (un RGB float32 de 0 a 255 sale
        casi todo blanco en `imshow`). Ninguna ruta de produccion recorre esta rama (los dos llamadores pasan la Pelicula), asi que esta es la unica prueba que pisa esas lineas: sus mutaciones, G1 y G2 de la bateria
        de A.1, cayeron antes con `test_b_la_pagina_muestra_la_de_16_bits_en_uint8...` de A.1, que ahora fija el color (B.8, clase b)."""
        v, _k = _tres_canales_distintos()
        datos = _codificar("tiff", 16, v)
        gris, _color, dpi, fecha = motor.leer_imagen(datos)
        assert gris.dtype == np.float32 and (np.rint(gris) != np.floor(gris)).any(), "premisa: el gris de 16 bits trae fracciones y redondear no es truncar"
        pagina._instalar_imagen(datos, "dieciseis.tif", gris, dpi, fecha, "fecha del escaneo")
        vista = mostrada(pagina)
        assert vista.dtype == np.uint8 and es_gris(vista) and pagina.estado == "imagen"
        assert np.array_equal(vista[:, :, 0], np.clip(np.rint(gris), 0, 255).astype(np.uint8))

    def test_instalar_imagen_usa_imagen_rgb_y_no_arma_el_color_por_su_cuenta(self):
        arbol = ast.parse(PAGINA_PY.read_text(encoding="utf-8"))
        instalar = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "_instalar_imagen")
        nombres = {n.id for n in ast.walk(instalar) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(instalar) if isinstance(n, ast.Attribute)}
        assert "imagen_rgb" in nombres, "el color sale de la UNICA definicion (corolario 1)"
        assert "leer_pelicula" not in nombres and "leer_imagen" not in nombres, "_instalar_imagen no vuelve a decodificar"


# ======================================================================================================== 8. «no medible» en la ventana del mensual

TABLAS_DE_LA_VENTANA = ("tabla_desfases", "tabla_perfiles", "tabla_barridos", "tabla_cuadratura")
# La frase con que el MOTOR (`placa_mensual.py`) explica un perfil que no cruza la altura media: parte del `estado` que D.1 guarda tal cual y que la ventana muestra sin tocar. Describe una ZONA sin dato (fuera de
# la pelicula o transparente), no un valor que no se midio: es la UNICA aparicion de «sin dato» que la ventana conserva (O6, vetable por el fisico).
FRASE_DEL_MOTOR = "o a una zona sin dato antes de cruzar la altura media"


@pytest.fixture
def ventana_mensual(app, bd, dialogos):
    v = ventana_mod().VentanaPlacaMensual(_control(bd), EQUIPO, USUARIO)
    v.resize(1380, 880)
    yield v
    cerrar(v)


@pytest.fixture
def archivo_placa_mensual(tmp_path, placa_mensual):
    ruta = tmp_path / "placa_mensual.png"
    ruta.write_bytes(placa_mensual.datos)
    return str(ruta)


class TestNumeroYParDicenNoMedible:
    def test_numero_de_none_dice_no_medible_con_cualquier_formato(self):
        assert dibujo.NO_MEDIBLE == "no medible"
        assert dibujo.numero(None) == "no medible"
        assert dibujo.numero(None, 1) == "no medible" and dibujo.numero(None, 3, True) == "no medible"

    @pytest.mark.parametrize("par", [None, (None, 1.0), (1.0, None), (None, None), [None, 2.5]])
    def test_par_con_algun_valor_que_falta_dice_no_medible(self, par):
        assert dibujo._par(par) == "no medible"
        assert dibujo._par(par, 1) == "no medible"

    def test_los_numeros_medidos_se_dicen_igual_que_siempre(self):
        assert dibujo.numero(1.23456, 3) == "1.235" and dibujo.numero(2.0, 1) == "2.0" and dibujo.numero(1.5, 3, True) == "+1.500"
        assert dibujo.numero(0.0004, 3, True) == "0.000" and dibujo.numero(-0.0004, 3, True) == "0.000" and dibujo.numero(-0.0006, 3, True) == "-0.001"
        assert dibujo._par((1.0, -2.0)) == "+1.000; -2.000" and dibujo._par((0.0, 0.25), 2) == "0.00; +0.25"

    def test_la_constante_sin_dato_se_retiro_y_sus_docstrings_hablan_de_no_medible(self):
        assert not hasattr(dibujo, "SIN_DATO"), "nada mas usa SIN_DATO: se retira"
        nombres = {n.id for n in ast.walk(ast.parse(DIBUJO_PY.read_text(encoding="utf-8"))) if isinstance(n, ast.Name)}
        assert "SIN_DATO" not in nombres
        for funcion in (dibujo.numero, dibujo._par):
            assert "SIN_DATO" not in funcion.__doc__ and "NO_MEDIBLE" in funcion.__doc__, funcion.__name__


def _dice_lo_que_debe(celda, valor_crudo):
    """Una celda es «no medible» exactamente cuando el valor que el motor entrego es None (y nunca «sin dato»); si lo midio, no es ninguno de los dos. Devuelve si lo es."""
    assert "sin dato" not in celda.lower()
    assert (celda == "no medible") == (valor_crudo is None), f"celda {celda!r} con el valor crudo {valor_crudo!r}"
    return valor_crudo is None


def _no_medibles_de_los_perfiles(resultado):
    """Comprueba la tabla de los perfiles (`filas_de_los_perfiles`) contra el MOTOR, celda por celda, y devuelve cuantas dicen «no medible»."""
    no_medibles = 0
    for fila in dibujo.filas_de_los_perfiles(resultado, "G", None):
        capa = {"Capa roja": "R", "Capa verde": "G", "Capa azul": "B", "Gris": "gris"}[fila[0]]
        eje = fila[1]
        m = resultado.capas[capa]
        p = getattr(m, eje)
        lados = dibujo.LADOS_DE_CADA_EJE[eje]
        crudos = [p.fwhm_mm, m.coincidencia_mm.get(lados[0]), m.coincidencia_mm.get(lados[1]), p.penumbras_mm[0], p.penumbras_mm[1],
                  p.piso if p.piso is not None else m.piso, p.meseta]
        for celda, crudo in zip(fila[3:10], crudos):
            no_medibles += _dice_lo_que_debe(celda, crudo)
    return no_medibles


def _no_medibles_de_los_desfases(resultado):
    """Lo mismo con la tabla de los desfases de cada capa (`tabla_de_desfases`)."""
    no_medibles = 0
    for capa in ("R", "G", "B", "gris"):
        m = resultado.capas[capa]
        filas = dibujo.tabla_de_desfases(resultado, capa)
        crudos = [m.coincidencia_mm.get(lado) for lado in pm.LADOS_DE_LA_COINCIDENCIA]
        for (_rotulo, celda), crudo in zip(filas[:len(crudos)], crudos):
            no_medibles += _dice_lo_que_debe(celda, crudo)
        for (_rotulo, celda), par in zip(filas[len(crudos):], (m.radiacion_menos_luz_mm, resultado.luz_menos_reticulo_mm, m.radiacion_menos_reticulo_mm)):
            assert "sin dato" not in celda.lower()
            assert (celda == "no medible") == (par is None or any(v is None for v in par)), (capa, celda, par)
            no_medibles += celda == "no medible"
    return no_medibles


def _no_medibles_de_los_barridos(barrido):
    """Lo mismo con la tabla de los barridos (`filas_de_los_barridos`)."""
    no_medibles = 0
    for fila in dibujo.filas_de_los_barridos(barrido):
        capa = {"Capa roja": "R", "Capa verde": "G", "Capa azul": "B", "Gris": "gris"}[fila[0]]
        b = barrido.ejes[fila[1]].capas[capa]
        e = b.estadistica
        central = None if b.central is None else b.central.fwhm_mm
        lejos = None if central is None or e.mediana_mm is None else central - e.mediana_mm
        for celda, crudo in zip(fila[5:10], (e.media_mm, e.mediana_mm, e.desviacion_mm, central, lejos)):
            no_medibles += _dice_lo_que_debe(celda, crudo)
    return no_medibles


class TestCadaTablaConUnValorNoMedidoDiceNoMedible:
    @pytest.fixture(scope="class")
    def analisis(self, placa_mensual):
        """El analisis REAL de la sintetica A con la base por omision (netOD): la capa roja esta recortada y no se mide, asi que sus numeros son None; las otras dos capas y el gris se miden."""
        resultado, barrido, _marcas = resultado_directo(placa_mensual.datos, placa_mensual.verdad.clics_del_cuaderno())
        return resultado, barrido

    def test_la_premisa_la_capa_roja_no_se_mide_y_las_demas_si(self, analisis):
        resultado, _barrido = analisis
        assert resultado.capas["R"].crossplane.fwhm_mm is None and resultado.capas["R"].inplane.fwhm_mm is None
        assert resultado.capas["G"].crossplane.fwhm_mm is not None and resultado.capas["gris"].crossplane.fwhm_mm is not None

    def test_la_tabla_de_los_perfiles_dice_no_medible_donde_el_motor_no_midio(self, analisis):
        resultado, _barrido = analisis
        assert _no_medibles_de_los_perfiles(resultado) >= 6, "compuerta de no vacuidad: la capa roja (dos ejes) tiene valores sin medir"

    def test_la_tabla_de_los_desfases_dice_no_medible_donde_el_motor_no_midio(self, analisis):
        resultado, _barrido = analisis
        assert _no_medibles_de_los_desfases(resultado) >= 4, "compuerta de no vacuidad: la capa roja no tiene desfases"

    def test_la_tabla_de_los_barridos_dice_no_medible_donde_el_motor_no_midio(self, analisis):
        _resultado, barrido = analisis
        assert _no_medibles_de_los_barridos(barrido) >= 5, "compuerta de no vacuidad: el barrido de la capa roja no tiene estadistica"

    def test_la_tabla_de_la_cuadratura_no_dice_sin_dato(self, analisis):
        resultado, _barrido = analisis
        for fila in dibujo.filas_de_la_cuadratura(resultado.geometria):
            assert not any("sin dato" in celda.lower() for celda in fila), fila


class TestLaVentanaEnteraNoDiceSinDato:
    def test_con_una_pelicula_cuyos_perfiles_encuentran_todos_su_borde_ningun_texto_de_la_ventana_dice_sin_dato_y_los_no_medidos_dicen_no_medible(
            self, ventana_mensual, dialogos, archivo_placa_mensual, placa_mensual):
        """B8-R1-02: el nombre dice la CONDICION de lo que se afirma. Con una pelicula donde un perfil no encuentra su borde, el motivo del motor trae su frase «zona sin dato» (O6) y lo que vale
        entonces lo fija la clase `TestConUnPerfilQueNoEncuentraSuBordeLaVentanaSoloDiceSinDatoDentroDeLaFraseDelMotor`."""
        v = analizada(ventana_mensual, dialogos, archivo_placa_mensual, placa_mensual.verdad.clics_del_cuaderno())
        sin_borde = [(c, e) for c in ("R", "G", "B", "gris") for e in ("crossplane", "inplane") if FRASE_DEL_MOTOR in getattr(v._resultado.capas[c], e).estado]
        assert sin_borde == [], f"premisa del nombre: en esta pelicula todo perfil encuentra su borde y el motor dice su frase en {sin_borde}"
        textos = todos_los_textos(v)
        assert any(t == "no medible" for t in textos), "compuerta de no vacuidad: la capa roja deja celdas sin medir y la ventana las dice"
        assert [t for t in textos if "sin dato" in t.lower()] == []
        for tabla in TABLAS_DE_LA_VENTANA:
            celdas = [c for fila in _celdas(getattr(v, tabla)) for c in fila if c]
            assert celdas and not [c for c in celdas if "sin dato" in c.lower()], tabla

    def test_la_tabla_de_los_perfiles_de_la_ventana_dice_no_medible_en_las_celdas_de_la_capa_roja(self, ventana_mensual, dialogos, archivo_placa_mensual, placa_mensual):
        v = analizada(ventana_mensual, dialogos, archivo_placa_mensual, placa_mensual.verdad.clics_del_cuaderno())
        rojas = [fila for fila in _celdas(v.tabla_perfiles) if fila[0] == "Capa roja"]
        assert len(rojas) == 2
        for fila in rojas:
            assert fila[3] == "no medible", "el FWHM de la capa roja"


def _celdas(tabla):
    return [[tabla.item(r, c).text() if tabla.item(r, c) else None for c in range(tabla.columnCount())] for r in range(tabla.rowCount())]


# ======================================================================================================== 8b. el cuadro de la pelicula virgen RECHAZADA (B8-R1-01)

CAPAS_DE_LA_VIRGEN = (("R", "Capa roja"), ("G", "Capa verde"), ("B", "Capa azul"), ("gris", "Gris"))


@pytest.fixture(scope="module")
def virgen_rechazada(placa_mensual):
    """Una pelicula IRRADIADA usada como si fuera la virgen: se MIDE y el rango de una pelicula sin irradiar la rechaza («no válida: ...»), que es el caso de uso del cuadro (EPSON178, DA-87). Tras el rechazo
    la referencia no conserva ninguna cifra (HERR.1b)."""
    referencia = pel.piso_de_pelicula_virgen(placa_mensual.datos, parametros(), "irradiada_como_virgen.png", fecha_calculo="2026-10-21")
    assert referencia.estado.startswith("no válida: fuera del rango esperado de una película sin irradiar"), referencia.estado
    return referencia


class TestElCuadroDeLaVirgenRechazadaNoDiceQueLaPeliculaNoSeMidio:
    """B8-R1-01. Una virgen rechazada SI se midio: el resumen del cuadro cita sus cifras («rojo 2 fuera de [60, 170]») y la tabla de uniformidad muestra el centro de cada capa. Lo que no tiene es un VALOR:
    `_virgen_cerrar` descarta las cifras para que nadie use una referencia que no sirve. La tabla de valores de esa referencia no puede decir «no medible» (diria que la pelicula no se pudo medir, y el
    cuadro mismo la muestra medida) ni «sin dato» (B.8 lo retira de la ventana): dice la palabra del estado de la capa, «no válida»."""

    def test_la_premisa_la_pelicula_se_midio_y_la_referencia_no_conserva_ninguna_cifra(self, virgen_rechazada):
        r = virgen_rechazada
        assert all(r.valor(c) is None and r.capas[c].n == 0 and r.capas[c].iqr is None and r.capas[c].estado == r.estado for c, _ in CAPAS_DE_LA_VIRGEN), "HERR.1b: tras el rechazo ninguna capa trae numero"
        assert r.uniformidad and all(r.uniformidad["capas"][c]["centro"] is not None for c, _ in CAPAS_DE_LA_VIRGEN), "la pelicula SI se midio: su uniformidad trae el centro de cada capa"
        assert "rojo" in r.estado and "fuera de [" in r.estado, "y el resumen cita lo medido"

    def test_las_filas_de_una_referencia_rechazada_dicen_la_palabra_de_su_estado_en_el_valor_los_pixeles_y_la_dispersion(self, virgen_rechazada):
        filas = dibujo.filas_de_la_virgen(virgen_rechazada)
        assert [f[0] for f in filas] == [nombre for _, nombre in CAPAS_DE_LA_VIRGEN]
        for fila in filas:
            assert tuple(fila[1:]) == ("no válida",) * 3, fila

    def test_ninguna_celda_de_una_referencia_rechazada_dice_no_medible_sin_dato_ni_cero_pixeles(self, virgen_rechazada):
        for fila in dibujo.filas_de_la_virgen(virgen_rechazada):
            for celda in fila[1:]:
                assert "no medible" not in celda and "sin dato" not in celda.lower() and celda != "0", (fila, celda)

    def test_la_palabra_sale_del_estado_de_cada_capa_y_no_esta_escrita_en_la_tabla(self, virgen_rechazada):
        """Una sola fuente (corolario 1): si el estado de la capa dice otra cosa, la fila dice esa otra cosa."""
        capas = {c: dataclasses.replace(virgen_rechazada.capas[c], estado="no medible: otro motivo") for c, _ in CAPAS_DE_LA_VIRGEN}
        otra = dataclasses.replace(virgen_rechazada, capas=capas)
        for fila in dibujo.filas_de_la_virgen(otra):
            assert tuple(fila[1:]) == ("no medible",) * 3, fila

    def test_una_referencia_valida_sigue_diciendo_sus_numeros(self, escaneo_virgen):
        r = escaneo_virgen.referencia
        assert r.estado == "ok"
        esperadas = [(nombre, f"{r.valor(c):.1f}", str(r.capas[c].n), f"{r.capas[c].iqr:.1f}") for c, nombre in CAPAS_DE_LA_VIRGEN]
        assert dibujo.filas_de_la_virgen(r) == esperadas
        assert all(int(f[2]) > 0 for f in esperadas), "compuerta de no vacuidad: la valida trae sus pixeles"

    def test_el_cuadro_muestra_esas_filas_junto_al_resumen_con_sus_cifras_y_a_la_uniformidad_medida(self, app, virgen_rechazada, placa_mensual):
        cuadro = ventana_mod().DialogoPeliculaVirgen(virgen_rechazada, placa_mensual.datos, None, None)
        try:
            valores = _celdas(cuadro.tabla_valores)
            assert valores == [list(f) for f in dibujo.filas_de_la_virgen(virgen_rechazada)]
            assert all(f[1:] == ["no válida"] * 3 for f in valores)
            assert cuadro.resumen.text() == virgen_rechazada.descripcion() and "fuera del rango esperado" in cuadro.resumen.text()
            assert re.findall(r"\b(?:rojo|verde|azul|gris) \d+ fuera de \[\d+, \d+\]", cuadro.resumen.text()), "el resumen cita las cifras medidas de las capas que el rango rechazo"
            uniformidad = _celdas(cuadro.tabla_uniformidad)
            assert [f[0] for f in uniformidad] == [nombre for _, nombre in CAPAS_DE_LA_VIRGEN]
            assert all(float(f[1]) == pytest.approx(virgen_rechazada.uniformidad["capas"][c]["centro"], abs=0.006) for f, (c, _) in zip(uniformidad, CAPAS_DE_LA_VIRGEN)), \
                "lo que se midio se ve: el centro de cada capa es un numero, no «no válida» ni «no medible»"
            assert not cuadro.boton_guardar.isEnabled()
            textos = [t for fila in valores + uniformidad for t in fila] + [cuadro.resumen.text()]
            assert all("sin dato" not in t.lower() for t in textos)
        finally:
            cerrar(cuadro)


# ======================================================================================================== 8c. la ventana con un perfil que NO encuentra su borde (B8-R1-02)

# Las peliculas de la sintetica A cortadas por la derecha a u mm del centro de radiacion (las de E.1, `test_e1_capa_no_medible.py`) y los perfiles que, EN VALOR DE PIXEL, no cruzan la altura media: lo que el MOTOR
# dice (medido el 23-10, `logs/B8/correccion_ronda1/estados_recortada.log`; las premisas de la fixture lo comprueban cada vez). En netOD, la base por omision, estas peliculas dejan la capa roja no medible por su
# meseta recortada y las otras capas encuentran su borde: la frase no aparece; por eso la clase mide en valor de pixel, que es la base donde sale.
ESCENAS_SIN_BORDE = {53.0: {("R", "crossplane")}, 51.5: {("R", "crossplane"), ("G", "crossplane"), ("gris", "crossplane")}}
# Cuantas celdas «no medible» dan las tres tablas del analisis en cada escena (medido el 23-10, `contar_no_medibles.log`): la compuerta de no vacuidad de la prueba de las celdas.
NO_MEDIBLES_DE_LA_ESCENA = {53.0: dict(perfiles=6, desfases=3, barridos=5), 51.5: dict(perfiles=10, desfases=9, barridos=15)}
NOMBRE_DE_LA_FILA = {"R": "Capa roja", "G": "Capa verde", "B": "Capa azul", "gris": "Gris"}


class TestConUnPerfilQueNoEncuentraSuBordeLaVentanaSoloDiceSinDatoDentroDeLaFraseDelMotor:
    """B8-R1-02. El protocolo de B.8 dice que ninguna tabla del mensual dice «sin dato». Cuando un perfil no cruza la altura media, el MOTIVO del motor (el `estado` que D.1 guarda tal cual) habla de «una zona
    sin dato» (O6): B.8 es presentacion, no toca el motor ni lo guardado, y la ventana lo muestra dentro de su «no medible: ...». Esta clase fija ESA escena con la ventana real: la frase llega tal cual a la
    celda del estado de cada perfil sin borde, y quitada la frase NINGUN texto de la ventana (etiquetas, tablas, menus, ayudas ni los textos de las cinco figuras) dice «sin dato»."""

    @pytest.fixture(scope="class", autouse=True)
    def _en_valor_de_pixel(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setitem(pm.VALORES_DE_LA_GEOMETRIA, "base_de_la_medida", pm.BASE_VALOR_DE_PIXEL)
            yield

    @pytest.fixture(scope="class")
    def escenas(self, _en_valor_de_pixel, placa_mensual, tmp_path_factory):
        """Las peliculas cortadas, escritas en archivos, con lo que el MOTOR dice de cada perfil. Las premisas son `assert`, nunca un `skip`."""
        cx, _cy = placa_mensual.verdad.centro_campo_px
        clics = placa_mensual.verdad.clics_del_cuaderno()
        carpeta = tmp_path_factory.mktemp("b8_cortadas")
        salida = {}
        for u, esperado in ESCENAS_SIN_BORDE.items():
            datos = gen_mensual.codificar(np.ascontiguousarray(placa_mensual.imagen[:, :int(round(cx + u / TAM))]), "png", 600)
            ruta = carpeta / f"cortada_{u}.png"
            ruta.write_bytes(datos)
            resultado, barrido, _marcas = resultado_directo(datos, clics)
            sin_borde = {(c, e) for c in ("R", "G", "B", "gris") for e in ("crossplane", "inplane") if FRASE_DEL_MOTOR in getattr(resultado.capas[c], e).estado}
            assert sin_borde == esperado, f"premisa de la escena u = {u}: los perfiles sin borde son {sorted(esperado)} y el motor dice {sorted(sin_borde)}"
            salida[u] = SimpleNamespace(ruta=str(ruta), clics=clics, resultado=resultado, barrido=barrido, sin_borde=sin_borde)
        return salida

    @pytest.mark.parametrize("u", list(ESCENAS_SIN_BORDE))
    def test_la_frase_del_motor_llega_tal_cual_a_la_celda_del_estado_de_cada_perfil_que_no_encontro_su_borde(self, ventana_mensual, dialogos, escenas, u):
        e = escenas[u]
        v = analizada(ventana_mensual, dialogos, e.ruta, e.clics)
        filas = {(f[0], f[1]): f for f in _celdas(v.tabla_perfiles)}
        for capa in ("R", "G", "B", "gris"):
            for eje in ("crossplane", "inplane"):
                medida = getattr(e.resultado.capas[capa], eje)
                celda = filas[(NOMBRE_DE_LA_FILA[capa], eje)][2]
                assert celda == ("ok" if medida.ok else medida.estado), (u, capa, eje)
                assert (FRASE_DEL_MOTOR in celda) == ((capa, eje) in e.sin_borde), (u, capa, eje, celda)
                if (capa, eje) in e.sin_borde:
                    assert celda.startswith(f"no medible: perfil {eje}: no se encuentra el borde"), celda

    @pytest.mark.parametrize("u", list(ESCENAS_SIN_BORDE))
    def test_quitada_la_frase_del_motor_ningun_texto_de_la_ventana_dice_sin_dato(self, ventana_mensual, dialogos, escenas, u):
        e = escenas[u]
        v = analizada(ventana_mensual, dialogos, e.ruta, e.clics)
        textos = todos_los_textos(v)
        con_la_frase = [t for t in textos if FRASE_DEL_MOTOR in t]
        assert len(con_la_frase) >= len(e.sin_borde), "compuerta de no vacuidad: la frase esta en la celda de cada perfil sin borde (y en los textos que la citan)"
        assert [t for t in textos if "sin dato" in t.replace(FRASE_DEL_MOTOR, "").lower()] == []
        for tabla in TABLAS_DE_LA_VENTANA:
            celdas = [c for fila in _celdas(getattr(v, tabla)) for c in fila if c]
            assert celdas and not [c for c in celdas if "sin dato" in c.replace(FRASE_DEL_MOTOR, "").lower()], tabla

    @pytest.mark.parametrize("u", list(ESCENAS_SIN_BORDE))
    def test_los_valores_que_el_motor_no_dio_por_no_hallar_el_borde_dicen_no_medible_en_las_tablas(self, escenas, u):
        e = escenas[u]
        minimos = NO_MEDIBLES_DE_LA_ESCENA[u]
        assert _no_medibles_de_los_perfiles(e.resultado) >= minimos["perfiles"], "compuerta de no vacuidad de los perfiles"
        assert _no_medibles_de_los_desfases(e.resultado) >= minimos["desfases"], "compuerta de no vacuidad de los desfases"
        assert _no_medibles_de_los_barridos(e.barrido) >= minimos["barridos"], "compuerta de no vacuidad de los barridos"
        assert not any("sin dato" in celda.lower() for fila in dibujo.filas_de_la_cuadratura(e.resultado.geometria) for celda in fila)


# ======================================================================================================== 9. lo que NO cambia (declarado)

class TestLoQueNoCambia:
    def test_los_pixeles_transparentes_siguen_siendo_sin_dato(self):
        """A.1: describe PIXELES sin dato (la alfa), no un valor que no se midio. No se toca."""
        texto = dibujo.texto_de_la_imagen("TIFF", 8, (20, 10), 600.0, "coincide", date(2026, 10, 5), 7, 600.0)
        assert texto.endswith("7 píxeles transparentes, que son sin dato.")

    @pytest.mark.parametrize("lado, modificar", [("derecho", lambda x, v: np.where(x > 2400, 32.0, v)), ("izquierdo", lambda x, v: np.where(x < 1000, 32.0, v))])
    def test_el_motivo_del_motor_de_un_borde_que_no_se_encuentra_conserva_su_frase_zona_sin_dato(self, lado, modificar):
        """B.8 es presentacion y lo GUARDADO no cambia: el motivo de un perfil que no cruza la altura media es el `estado` que D.1 guarda tal cual y habla de una ZONA sin dato (fuera de la pelicula o
        transparente), no de un valor que no se midio. El motor no se toca: la ventana lo muestra dentro de su «no medible: ...» y la frase se queda como esta (un reemplazo global de «sin dato» la cambiaria)."""
        perfil, centro = perfil_erf(modificar=modificar)
        medida = medir_perfil_a_mano(perfil, centro)
        assert medida.fwhm_mm is None and medida.estado.startswith(f"no medible: perfil crossplane: no se encuentra el borde {lado} al 50 %")
        assert "a una zona sin dato antes de cruzar la altura media" in medida.estado, medida.estado

    def test_el_pdf_de_braqui_conserva_su_propio_sin_dato(self):
        """Zona roja: `models/PDF/bloque_posicion_inicial.py` tiene su SIN_DATO y no se toca."""
        from models.PDF import bloque_posicion_inicial
        assert bloque_posicion_inicial.SIN_DATO == "sin dato"

    def test_el_motor_de_la_posicion_inicial_sigue_entregando_las_cuatro_cosas_de_siempre(self):
        gris, color, dpi, fecha = motor.leer_imagen(_bytes("braqui_00.jpeg"))
        assert gris.ndim == 2 and color.shape == gris.shape + (3,) and dpi == 600.0 and fecha is not None
