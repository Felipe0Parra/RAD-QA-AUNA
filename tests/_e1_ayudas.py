"""E.1: las ayudas de las pruebas de la ventana del analisis mensual (`ui/paginasControles/PruebasMensuales/placa_mensual.py`): las comparten `test_e1_ventana_placa_mensual.py` y
`test_e1_capa_no_medible.py`. Este archivo NO empieza por `test_`: pytest no lo colecciona; sus fixtures se importan por nombre en cada archivo de pruebas, como hacen las de PI.4.

Todo lo que toca la produccion se importa POR PRUEBA (`ventana_mod()`, `dibujo_mod()`, `svc()`...): en HEAD (sin E.1) los archivos de pruebas se colecciona y cada prueba cae con su error de
importacion, no con un error de coleccion que las tapa a todas (la regla del rojo real).

Trampa 2 (todo `QMessageBox` y todo cuadro de dialogo se parcha: la fixture `dialogos`), Trampa 9 (cada ventana se cierra con la receta completa y la huella no mira internos de Qt: `huella`,
`recorrer`), Trampa 10 (ningun `lru_cache`: los resultados caros son fixtures de modulo y nadie los muta).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import copy
import gc
import hashlib
import importlib
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from matplotlib.backend_bases import FigureCanvasBase, MouseEvent, NavigationToolbar2
from PyQt5 import sip
from PyQt5.QtCore import QEvent
from types import SimpleNamespace

from PyQt5.QtWidgets import (QAbstractScrollArea, QAbstractSlider, QApplication, QComboBox, QFileDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabBar,
                             QTableWidget, QTabWidget, QToolBar, QWidget)

RAIZ = Path(__file__).resolve().parent.parent
VENTANA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "placa_mensual.py"
DIBUJO_PY = RAIZ / "analisisImagenes" / "dibujo_placa_mensual.py"
MOTOR_PY = RAIZ / "analisisImagenes" / "placa_mensual.py"
PELICULA_PY = RAIZ / "analisisImagenes" / "pelicula.py"
SERVICIO_PY = RAIZ / "services" / "placa_mensual.py"
USUARIO = "Fisico de prueba"
EQUIPO = "Clinac de prueba"
SIMBOLOS_DA18 = "✓✗✔✘⚠❌✅❎☑☒"
CAPAS = ("R", "G", "B")
COLOR = {"R": "rojo", "G": "verde", "B": "azul"}               # lo que dice un MENU o una columna: el color a secas (escrito a mano: el ancla EXTERNA de `NOMBRE_DE_CAPA`)
ADJETIVO = {"R": "roja", "G": "verde", "B": "azul"}            # lo que dice una FRASE con «capa»: concuerda con el sustantivo (ancla EXTERNA de `ADJETIVO_DE_LA_CAPA`)
TAM = 25.4 / 600.0
PESTANAS = ("Imagen", "Capas", "Perfiles por capa", "Barridos", "Cuadratura")
FECHA_DE_PRUEBA = "2026-03-15"         # la fecha FIJA (en el pasado) con que se miden las referencias virgenes de las pruebas y que dice el menu «Piso»: ninguna prueba de E.1 lee el reloj (E1-R2-PRU-04, DP-94, DP-155)


class HoyFijo(date):
    """Un `date` cuyo `today()` es `FECHA_DE_PRUEBA`: para las pruebas que pasan por el codigo de la ventana que escribe la fecha de HOY (`monkeypatch.setattr(ventana_mod(), "date", HoyFijo)`). Una prueba que compara
    contra `date.today()` cae si la medianoche cruza entre construir la referencia y la asercion; esta no depende del reloj."""

    @classmethod
    def today(cls):
        return cls.fromisoformat(FECHA_DE_PRUEBA)


# ------------------------------------------------------------------------------------------------------ la produccion, importada por prueba

def ventana_mod():
    return importlib.import_module("ui.paginasControles.PruebasMensuales.placa_mensual")


def dibujo_mod():
    return importlib.import_module("analisisImagenes.dibujo_placa_mensual")


def svc():
    return importlib.import_module("services.placa_mensual")


def pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def pel():
    return importlib.import_module("analisisImagenes.pelicula")


def parametros():
    """Los parametros de fabrica del analisis, todos (una copia: nadie muta los del modulo)."""
    return copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)


def sin_la_base(texto, base=None):
    """OD.1: la linea del piso de la ventana (`etiqueta_piso`) empieza, con un analisis hecho, por la frase de la base con que se midio («Base de la medida: ...»), y tras ella viene la frase del piso de
    siempre. Esto quita la primera (y comprueba que esta) para mirar la segunda tal como la fijaban las pruebas de E.1. `base`: la del analisis (por omision el valor de pixel, la que fijan estas pruebas)."""
    frase = dibujo_mod().texto_de_la_base(pm().BASE_VALOR_DE_PIXEL if base is None else base)
    assert texto.startswith(frase + " "), texto[:240]
    return texto[len(frase) + 1:]


@pytest.fixture(scope="module")
def con_la_base_de_pixel():
    """OD.1: la base de VALOR DE PIXEL como base por omision del motor mientras dura el modulo que la pide (el diccionario de fabrica del motor se parcha y se restaura al terminar). Una prueba de la
    ventana que necesita las tres capas medibles (el rojo de la sintetica esta recortado en netOD) la pide con un `autouse` de modulo; la netOD la prueba `test_od1_densidad_optica.py`."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(pm().VALORES_DE_LA_GEOMETRIA, "base_de_la_medida", pm().BASE_VALOR_DE_PIXEL)
        yield


def resultado_directo(datos, puntos, modo="automatico", punto=None, referencia=None):
    """El `ResultadoPlacaMensual`, su barrido y las marcas refinadas que el MOTOR da sobre esos bytes y esos clics, por el camino de `guardar` (`leer_pelicula`, `refinar_marca` de cada clic, `analizar`,
    `barrido`): la verdad contra la que se mira la ventana, que no sale de ella."""
    P = parametros()
    pelicula = pel().leer_pelicula(datos)
    marcas = [pm().refinar_marca(pelicula.gris, c, P, pel().escala_mm(pelicula.dpi, P), pelicula.validos) for c in puntos]
    resultado = pm().analizar(pelicula, marcas, P, modo_piso=modo, punto_manual=punto, referencia_virgen=referencia)
    return resultado, pm().barrido(resultado), marcas


# ------------------------------------------------------------------------------------------------------ fixtures

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _cursor_limpio(app):
    """El cursor de espera de Qt es una PILA compartida por todo el proceso: una prueba que dejara uno sin restaurar contaminaria a las demas."""
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
    yield
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()


class Dialogos:
    """Lo que la ventana le pidio a Qt, en orden, con el cursor que habia en cada momento (ningun cuadro se abre con el cursor de espera puesto)."""

    def __init__(self):
        self.llamadas = []
        self.respuesta = QMessageBox.Yes          # lo que contesta una pregunta («¿Reemplazarlo?», «¿Reemplazarla?»)
        self.ruta = ""                            # lo que devuelve el cuadro de elegir archivo
        self.criticos_esperados = False
        self.cuadros_de_la_virgen = []            # los `DialogoPeliculaVirgen` que se abrieron
        self.accion_virgen = _guardar_si_se_puede # lo que «hace el fisico» dentro del cuadro de la virgen

    def anotar(self, tipo, args=()):
        cursor = QApplication.overrideCursor()
        self.llamadas.append({"tipo": tipo, "args": args, "titulo": args[1] if len(args) > 1 else None, "texto": args[2] if len(args) > 2 else None,
                              "botones": args[3] if len(args) > 3 else None, "por_omision": args[4] if len(args) > 4 else None, "cursor": cursor.shape() if cursor is not None else None})

    def de(self, tipo):
        return [c for c in self.llamadas if c["tipo"] == tipo]

    def orden(self):
        return [c["tipo"] for c in self.llamadas]


def _guardar_si_se_puede(cuadro):
    """El fisico pulsa «Guardar como referencia» si se puede; si no, cierra."""
    if cuadro.boton_guardar.isEnabled():
        cuadro.boton_guardar.click()
    else:
        cuadro.reject()


@pytest.fixture
def dialogos(monkeypatch):
    d = Dialogos()

    def sustituto(tipo, devuelve):
        def f(*args, **kwargs):
            d.anotar(tipo, args)
            return devuelve() if callable(devuelve) else devuelve
        return staticmethod(f)

    monkeypatch.setattr(QMessageBox, "warning", sustituto("warning", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "information", sustituto("information", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical", sustituto("critical", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", sustituto("question", lambda: d.respuesta))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (d.ruta, "")))
    try:
        cuadro = ventana_mod().DialogoPeliculaVirgen
    except ImportError:                                  # en HEAD la ventana no existe: cada prueba cae por su cuenta
        cuadro = None
    if cuadro is not None:
        def exec_falso(self):
            d.anotar("cuadro_de_la_virgen")
            d.cuadros_de_la_virgen.append(self)
            d.accion_virgen(self)
            return self.result()
        monkeypatch.setattr(cuadro, "exec_", exec_falso)
    yield d
    assert d.criticos_esperados or not d.de("critical"), f"un dialogo de error inesperado: {[c['texto'] for c in d.de('critical')]}"
    # DA-18 en TODO lo que la ventana le dice al fisico con un cuadro (aviso, pregunta, error), en cada prueba que abra alguno: el censo de textos de los widgets (`todos_los_textos`) no los ve.
    con_simbolos = [(c["tipo"], c["titulo"], c["texto"]) for c in d.llamadas if not all(sin_simbolos(t) for t in (c["titulo"], c["texto"]) if isinstance(t, str))]
    assert not con_simbolos, f"un cuadro de dialogo con simbolos de correcto o incorrecto (DA-18): {con_simbolos}"


def cerrar(w):
    """Libera la ventana DE VERDAD (Trampa 9): `deleteLater` + `gc.collect()` no bastan; las lambdas de las conexiones las retienen los proxies de PyQt, que se liberan con un `disable()` en cola que
    sin bucle de eventos nunca se procesa (cada ventana se quedaria viva con sus figuras, su imagen y su resultado, cientos de MB)."""
    if sip.isdeleted(w):                       # una ventana hija de otra se destruye con su madre
        return
    w.hide()
    w.close()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def fabrica(app, bd, dialogos):
    """`crear(ref=None, ...)` devuelve una ventana nueva sobre un control de la BD temporal (uno nuevo si no se da `ref`); todas se cierran al terminar la prueba. `crear.control()` siembra otro control."""
    from test_d1_guardado_placa_mensual import _control
    creadas = []

    def crear(ref=None, equipo=EQUIPO, usuario=USUARIO, **kwargs):
        ref = _control(bd) if ref is None else ref
        v = ventana_mod().VentanaPlacaMensual(ref, equipo, usuario, **kwargs)
        v.resize(1380, 880)
        v.ref_de_prueba = ref
        creadas.append(v)
        return v

    crear.control = lambda **k: _control(bd, **k)
    yield crear
    for v in creadas:
        cerrar(v)


@pytest.fixture
def ventana(fabrica):
    return fabrica()


def _virgen_sintetica(semilla):
    """El escaneo de una pelicula VIRGEN sintetica (la del generador con `meseta = virgen`, sin dosis ni tinta, el fondo del escaner puro)."""
    import _placa_mensual_sintetica as gen
    calibracion = dict(gen.CALIB, meseta_bgr=gen.CALIB["virgen_bgr"], fondo_escaner=255.0)
    arreglo, _ = gen.generar_arreglo(variante="A", theta_deg=0.0, bits=8, dpi=600, tinta=False, calib=calibracion, seed=semilla)
    arreglo = np.array(arreglo)
    arreglo[arreglo.min(axis=2) >= 235] = 255
    return gen.codificar(arreglo, "tiff", 600)


def _escaneo_virgen(semilla, nombre):
    datos = _virgen_sintetica(semilla)
    referencia = pel().piso_de_pelicula_virgen(datos, parametros(), nombre, fecha_calculo=FECHA_DE_PRUEBA)
    assert referencia.estado == "ok", referencia.estado
    return SimpleNamespace(datos=datos, referencia=referencia, nombre=nombre, fecha=FECHA_DE_PRUEBA)


@pytest.fixture(scope="module")
def escaneo_virgen():
    """El escaneo de una pelicula virgen sintetica con su referencia (valida), una vez por modulo."""
    return _escaneo_virgen(1, "virgen_lote.tif")


@pytest.fixture(scope="module")
def otro_escaneo_virgen():
    """OTRO escaneo virgen valido (otra semilla de ruido: otra huella): para probar que una referencia vigente distinta de la guardada se dice."""
    return _escaneo_virgen(7, "virgen_otro_lote.tif")


@pytest.fixture
def archivo_placa(tmp_path, placa):
    """La sintetica A de PF.0 escrita en un archivo (lo que el fisico elige en el cuadro de «Seleccionar imagen»)."""
    ruta = tmp_path / "placa.png"
    ruta.write_bytes(placa.datos)
    return str(ruta)


# ------------------------------------------------------------------------------------------------------ el camino del usuario

def cargar(v, dialogos, ruta):
    """El fisico pulsa «Seleccionar imagen» y elige ese archivo."""
    dialogos.ruta = ruta
    v.boton_imagen.click()


def clic(v, x, y, boton=1, doble=False, soltar=True):
    """Un clic REAL sobre la imagen: pulsar y soltar entregados por `callbacks.process` (la lupa y el desplazar quedan en modo y exigen soltar)."""
    lienzo = v.lienzo_imagen
    lienzo.draw()
    X, Y = v.eje_imagen.transData.transform((x, y))
    lienzo.callbacks.process("button_press_event", MouseEvent("button_press_event", lienzo, X, Y, button=boton, dblclick=doble))
    if soltar:
        lienzo.callbacks.process("button_release_event", MouseEvent("button_release_event", lienzo, X, Y, button=boton))


def marcar(v, clics):
    for x, y in clics:
        clic(v, x, y)


def analizada(v, dialogos, ruta, clics):
    """El fisico abre la imagen y marca los cinco puntos: la ventana analiza."""
    cargar(v, dialogos, ruta)
    marcar(v, clics)
    assert v.estado == "analizada", v.estado
    return v


def guardada(v, dialogos, ruta, clics):
    analizada(v, dialogos, ruta, clics)
    v.boton_guardar.click()
    assert v.estado == "registro", v.estado
    return v


def elegir_capa(v, capa):
    """El fisico abre el menu y elige esa capa (el mismo `currentIndexChanged` que emite un clic en la lista)."""
    v.selector_capa.setCurrentIndex(CAPAS.index(capa))


def elegir_piso(v, modo):
    v.selector_piso.setCurrentIndex(list(pel().MODOS_DEL_PISO).index(modo))


def por_gid(ax, gid):
    """Los artistas de ese eje con ese `gid` (los dibujos de la ventana los llevan para que una prueba los encuentre)."""
    return [a for a in ax.get_children() if a.get_gid() == gid]


def con_gid(ax, prefijo):
    return [a for a in ax.get_children() if (a.get_gid() or "").startswith(prefijo)]


def etiquetas(ax):
    return [t.get_text() for t in (ax.get_legend().get_texts() if ax.get_legend() else [])]


def texto_de_la_tabla(tabla):
    """Todas las celdas de una tabla como filas de texto."""
    return [[tabla.item(r, c).text() if tabla.item(r, c) else None for c in range(tabla.columnCount())] for r in range(tabla.rowCount())]


def todos_los_textos(v):
    """Cada texto que la ventana le muestra al fisico: etiquetas, botones, menus, pestanas, tablas, ayudas y los textos de las cinco figuras (titulos, ejes, leyendas, anotaciones)."""
    textos = []
    for w in recorrer(v):
        if isinstance(w, QLabel):
            textos.append(w.text())
        elif isinstance(w, QPushButton):
            textos.append(w.text())
            textos.append(w.toolTip())
        elif isinstance(w, QComboBox):
            textos += [w.itemText(i) for i in range(w.count())]
            textos.append(w.toolTip())
        elif isinstance(w, QTabWidget):
            textos += [w.tabText(i) for i in range(w.count())]
        elif isinstance(w, QTableWidget):
            textos += [w.horizontalHeaderItem(c).text() for c in range(w.columnCount())]
            textos += [t for fila in texto_de_la_tabla(w) for t in fila if t]
    for lienzo in (v.lienzo_imagen, v.lienzo_gris, v.lienzo_capas, v.lienzo_perfiles, v.lienzo_barridos, v.lienzo_cuadratura):
        for t in lienzo.figure.findobj(lambda a: hasattr(a, "get_text") and callable(a.get_text)):
            textos.append(t.get_text())
    return [t for t in textos if t]


# Los compuestos de Qt (y los lienzos y barras de matplotlib) son HOJAS de la huella: se observa su estado por el tipo y nunca se mira dentro (Trampa 9).
_HOJAS = (QComboBox, QTabBar, QAbstractScrollArea, QLineEdit, QToolBar, FigureCanvasBase)


def recorrer(raiz):
    """Cada widget NUESTRO (creado desde Python) bajo `raiz`, sin entrar en una hoja; las paginas de una pestana por su INDICE y el lienzo de un area de desplazamiento por `widget()`."""
    for hijo in raiz.children():
        if sip.ispycreated(hijo):
            if isinstance(hijo, QWidget):
                yield hijo
                if isinstance(hijo, QTabWidget):
                    for i in range(hijo.count()):
                        pagina = hijo.widget(i)
                        yield pagina
                        yield from recorrer(pagina)
                elif isinstance(hijo, QScrollArea):
                    interior = hijo.widget()
                    if interior is not None and sip.ispycreated(interior):
                        yield interior
                        yield from recorrer(interior)
                elif not isinstance(hijo, _HOJAS):
                    yield from recorrer(hijo)
        elif hijo.isWidgetType():
            yield from recorrer(hijo)


def _simple(valor):
    if valor is None or isinstance(valor, (bool, int, float, str, date)):
        return True
    return isinstance(valor, (tuple, list)) and all(_simple(v) for v in valor)


def _atributos(objeto):
    """Los atributos de Python de un objeto como la huella los observa: los simples por su valor, los bytes por su md5 y las colecciones por su tamano."""
    atributos = {}
    for nombre, valor in vars(objeto).items():
        if isinstance(valor, (bytes, bytearray)):
            atributos[nombre] = ("bytes", hashlib.md5(valor).hexdigest())
        elif _simple(valor):
            atributos[nombre] = valor
        elif isinstance(valor, (list, tuple, dict, set)):
            atributos[nombre] = ("coleccion", len(valor))
    return atributos


def huella(v):
    """Todo lo que se puede observar de una ventana, derivado del arbol de widgets y no de una lista de lo que 'Limpiar' limpia: cada widget (clase, habilitado, visible y su estado segun el tipo), cada
    barra de herramientas y cada lienzo (modo, historial, ejes, artistas, limites) y los atributos simples de la ventana (valores y nombres). Un widget, un lienzo o una barra nuevos entran solos."""
    todos = list(recorrer(v))
    modulo = ventana_mod().__name__
    widgets = []
    for w in todos:
        e = [type(w).__name__, w.objectName(), w.isEnabled(), w.isVisibleTo(v)]
        if isinstance(w, QLineEdit):
            e += [w.text(), w.isReadOnly()]
        elif isinstance(w, QLabel):
            e += [w.text()]
        elif isinstance(w, QComboBox):
            e += [w.count(), w.currentIndex(), w.currentText(), tuple(w.itemData(i) for i in range(w.count())), tuple(w.itemText(i) for i in range(w.count()))]
        elif isinstance(w, QPushButton):
            e += [w.text(), w.isChecked()]
        elif isinstance(w, QAbstractSlider):
            e += [w.value(), w.minimum(), w.maximum(), w.isSliderDown()]
        elif isinstance(w, QTabWidget):
            e += [w.count(), w.currentIndex(), tuple(w.tabText(i) for i in range(w.count()))]
        elif isinstance(w, QTableWidget):
            e += [w.rowCount(), w.columnCount(), w.currentRow(), tuple(tuple(w.item(r, c).text() if w.item(r, c) else None for c in range(w.columnCount())) for r in range(w.rowCount()))]
        if type(w).__module__ == modulo:
            e.append(tuple(sorted(_atributos(w).items(), key=lambda par: par[0])))
        widgets.append(tuple(e))
    barras = [w for w in todos if isinstance(w, NavigationToolbar2)]
    lienzos = [w for w in todos if isinstance(w, FigureCanvasBase)]
    infos_barras = [(i, str(b.mode), len(b._nav_stack), b._actions["zoom"].isChecked(), b._actions["pan"].isChecked(), b.canvas.widgetlock.locked()) for i, b in enumerate(barras)]
    figuras = []
    for i, lienzo in enumerate(lienzos):
        ejes = tuple((len(e.images), len(e.lines), len(e.patches), len(e.collections), len(e.texts), e.get_xlabel(), e.get_ylabel(), e.get_title(), (e.get_xlim(), e.get_ylim()))
                     for e in lienzo.figure.axes)
        figuras.append((i, ejes, tuple(sorted((evento, len(cb)) for evento, cb in lienzo.callbacks.callbacks.items()))))
    return {"widgets": widgets, "barras": infos_barras, "figuras": figuras, "atributos": _atributos(v), "nombres": sorted(vars(v))}


def sin_simbolos(texto):
    return not any(c in texto for c in SIMBOLOS_DA18)
