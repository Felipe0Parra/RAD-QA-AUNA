"""PI.4 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md): la página de la posición inicial de braquiterapia -- subir la imagen, dos
clics, analizar, pestañas, guardar, anular, abrir, recalcular y limpiar --, probada POR EL CAMINO DEL USUARIO.

CAUSA. No existía la pantalla (D5-D9). La vieja `PosicionamientoInicial` heredaba la plantilla del diario y daba 0.13, 5.46
o 7.62 mm sobre la misma placa según el umbral.

Cómo se prueba (Trampas 1, 2, 3 y 7 de CLAUDE.md):
  - Los clics son `MouseEvent` REALES entregados por `lienzo.callbacks.process` (llegan al `mpl_connect` y traen `inaxes`,
    `xdata` con ruido de 1e-13 y `dblclick`): fijar `p.puntos` a mano o llamar al manejador con un evento falso no ejercita
    ni el cableado ni el redondeo. matplotlib se traga las excepciones de sus manejadores bajo Qt, así que las pruebas
    afirman ESTADO, no excepciones.
  - Todo `QMessageBox`, `QFileDialog.getOpenFileName` y el diálogo de permiso están sustituidos (la fixture `dialogos`
    anota además el estado del cursor en cada llamada: ningún diálogo debe abrirse con el cursor de espera puesto). Una
    fixture autouse vacía la pila del cursor antes y después de cada prueba (precedente de UX1).
  - Los botones se pulsan con `.click()` y la tabla se abre con `cellDoubleClicked.emit`: se ejercitan los `connect`.
  - 'Limpiar = una página recién creada' (corolario 3 del 02-09) se afirma con una HUELLA GENÉRICA derivada del árbol de
    widgets, de las figuras, de las barras de herramientas y de `vars(pagina)`; está en la PRUEBA y no en la página: un
    método de la página tendría el mismo punto ciego que el limpiador.
  - Todo contra una BD temporal copiada de la plantilla de PI.3: nunca se abre una BD de referencia. Los números salen de los
    valores de control de PI.1 (placa real braqui_00: -8.55 px = -0.362 mm; EPSON009: -0.110 mm) y de lo que la BD guarda.

Lo medido por la revisión de diseño de Opus (03-10, `pi4_informe_opus.md`) y fijado aquí: clics fuera de la imagen (X2),
empate en 472.5 con ruido de 1e-13 (X1), la imagen como RGB uint8 (memoria < 500 MB), un solo manejador de clics, el
historial de la barra vaciado al cargar y -- la pregunta P10 (DP-145) -- Guardar deshabilitado cuando el motor no refinó
la línea (con los clics a 4 px o más: -0.133 / -0.047 / +0.122 mm en vez de -0.362, sin ningún aviso en el veredicto).

Compuertas de no vacuidad (Trampa 8): las tablas de casos declaran cuántos corrieron, y los casos de 'no medible' y de
'línea no refinada' afirman primero que la situación existe de verdad antes de afirmar lo que la página hace con ella."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import difflib
import gc
import hashlib
import json
import re
import shutil
import tracemalloc
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from matplotlib.backend_bases import FigureCanvasBase, MouseEvent, NavigationToolbar2
from matplotlib.figure import Figure
from PyQt5 import sip
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QAbstractSlider, QApplication, QComboBox, QDialog,
                             QFileDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTabBar, QTabWidget,
                             QToolBar, QWidget)

import ui.paginasControles.PruebasMensuales.posicion_inicial_braqui as pagina_mod
import ui.paginasGuia.dialogs as dialogs_mod
from analisisImagenes import posicion_inicial_braqui as motor
from data.ManejoDatos.user import Usuario
from services import posicion_inicial_braqui as svc
from test_pi1_motor_posicion_inicial import CLICS_EPSON009, CLICS_EPSON031, CLICS_PLACA_REAL
# `bd` y `plantilla` son fixtures de PI.3 (la BD temporal con todo el esquema y los índices): se reutilizan, no se
# reescriben (precedente: test_pi3 importa de test_pi1).
from test_pi3_servicio_posicion_inicial import (BRAQUI_00, DATOS, EPSON009, SERIE_A, USUARIO, _a_300_dpi, _auditoria,
                                                _calibracion, _consulta, _filas, _hoja, _sembrar_prueba, _sintetica, _sql,
                                                bd, plantilla)  # noqa: F401

RAIZ = Path(__file__).resolve().parent.parent
PAGINA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "posicion_inicial_braqui.py"
TABLA = "braqui_posicion_inicial"
CAMBIO = "2026-09-27"            # tres días antes de la fecha del escaneo de braqui_00 (EXIF 2026-09-30): DD7 lo propone
SERIE_C = "24-05-0004-D"
CLICS_G1 = [(191, 377), (190, 56)]
CLICS_NO_MEDIBLE = [(191, 120), (190, 20)]      # solo cubren la parte alta de la película: el gris dice "no medible"
CLICS_LINEA_ALEJADA = [(197, 377), (196, 56)]   # +6 px: el motor descarta la línea y mide contra los clics (DP-145)
CLICS_LINEA_NO_REFINADA = [(191, 250), (190, 150)]   # un tramo corto: "no se pudo refinar la linea" (también se bloquea)
SIMBOLOS_DA18 = "✓✗✔✘⚠❌✅"


# ------------------------------------------------------------------------------------------------------ fixtures

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _cursor_limpio(app):
    """El cursor de espera de Qt es una PILA compartida por todo el proceso: un test que dejara uno sin restaurar
    contaminaría a los demás."""
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
    yield
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()


class _Dialogos:
    """Lo que la página le pidió a Qt, en orden, con el cursor que había en cada momento."""

    def __init__(self):
        self.llamadas = []
        self.respuesta = QMessageBox.Yes
        self.ruta = ""
        self.permiso = QDialog.DialogCode.Accepted
        self.permisos = []
        self.criticos_esperados = False

    def anotar(self, tipo, args=()):
        cursor = QApplication.overrideCursor()
        self.llamadas.append({"tipo": tipo, "args": args, "titulo": args[1] if len(args) > 1 else None,
                              "texto": args[2] if len(args) > 2 else None,
                              "cursor": cursor.shape() if cursor is not None else None})

    def de(self, tipo):
        return [c for c in self.llamadas if c["tipo"] == tipo]

    def orden(self):
        return [c["tipo"] for c in self.llamadas]


@pytest.fixture
def dialogos(monkeypatch):
    d = _Dialogos()

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

    class PermisoFalso:
        def __init__(self, user):
            d.permisos.append(user)
            d.anotar("permiso_construido")

        def exec(self):
            d.anotar("permiso")
            return d.permiso

    monkeypatch.setattr(pagina_mod, "DialogAdminPermisoEliminar", PermisoFalso)
    monkeypatch.setattr(dialogs_mod, "DialogAdminPermisoEliminar", PermisoFalso)
    yield d
    assert d.criticos_esperados or not d.de("critical"), \
        f"un diálogo de error inesperado: {[c['texto'] for c in d.de('critical')]}"


def _cerrar(p):
    """Libera la página DE VERDAD. `deleteLater` + `gc.collect()` no bastaban (medido por Opus, 03-10): las siete lambdas
    de las conexiones las retienen los proxies de PyQt, que se liberan con un `disable()` en cola que sin bucle de eventos
    nunca se procesa; cada página se quedaba viva con sus barras y sus figuras (y la imagen grande), y esas barras muertas
    eran las acciones obsoletas que ensuciaban la huella de las pruebas siguientes."""
    p.hide()
    p.close()
    p.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def fabrica(app, bd, dialogos):
    """`crear(cambios=(CAMBIO,))` siembra esos cambios de fuente en la BD temporal y devuelve una página nueva."""
    creadas, sembradas = [], set()

    def crear(cambios=(CAMBIO,), usuario=None):
        for fecha in cambios:
            if fecha not in sembradas:               # el índice único de EB6 no admite dos el mismo día
                sembradas.add(fecha)
                _calibracion(bd, f"{fecha} 10:00:00", "Cambio de fuente", SERIE_C)
        p = pagina_mod.PosicionInicialBraqui(usuario or Usuario(username="fisico1", fullname=USUARIO))
        creadas.append(p)
        return p

    yield crear
    for p in creadas:
        _cerrar(p)


@pytest.fixture
def pagina(fabrica):
    return fabrica()


@pytest.fixture
def archivo_braqui(tmp_path):
    ruta = tmp_path / "braqui_00.jpeg"
    shutil.copy(DATOS / "braqui_00.jpeg", ruta)
    return str(ruta)


@pytest.fixture
def espia_analisis(monkeypatch):
    """Cuenta las llamadas a `svc.analizar_imagen` y anota con qué parámetros y en qué estado estaba la página."""
    llamadas = []
    real = svc.analizar_imagen

    def espia(imagen_bytes, puntos, parametros=None):
        llamadas.append({"puntos": list(puntos), "parametros": parametros})
        return real(imagen_bytes, puntos, parametros)

    monkeypatch.setattr(svc, "analizar_imagen", espia)
    return llamadas


# ------------------------------------------------------------------------------------------------------- ayudas

def _cargar(p, dialogos, ruta):
    dialogos.ruta = ruta
    p.boton_imagen.click()


def _clic(p, x, y, boton=1, doble=False, soltar=True):
    """Un clic REAL sobre la imagen: pulsar y soltar entregados por `callbacks.process` (en modo lupa hay que soltar)."""
    lienzo = p.lienzo_imagen
    lienzo.draw()
    X, Y = p.eje_imagen.transData.transform((x, y))
    lienzo.callbacks.process("button_press_event",
                             MouseEvent("button_press_event", lienzo, X, Y, button=boton, dblclick=doble))
    if soltar:
        lienzo.callbacks.process("button_release_event", MouseEvent("button_release_event", lienzo, X, Y, button=boton))


def _marcar(p, clics=CLICS_G1):
    for x, y in clics:
        _clic(p, x, y)


def _analizada(p, dialogos, ruta, clics=CLICS_G1):
    _cargar(p, dialogos, ruta)
    _marcar(p, clics)
    assert p.estado == "analizada"


def _guardada(p, dialogos, ruta):
    _analizada(p, dialogos, ruta)
    p.boton_guardar.click()
    assert p.estado == "registro"


def _numero_de_filas(bd):
    return _consulta(bd, f"SELECT COUNT(*) FROM {TABLA}")[0][0]


def _simple(valor):
    if valor is None or isinstance(valor, (bool, int, float, str, date)):
        return True
    return isinstance(valor, (tuple, list)) and all(_simple(v) for v in valor)


# Los compuestos de Qt (y los lienzos y barras de matplotlib) son HOJAS de la huella: se observa su estado por el tipo y
# nunca se mira dentro. Sus internos (las barras de desplazamiento y la esquina de una tabla, el contenedor emergente de un
# combo, los botones de desplazamiento de las pestañas, el botón de desborde de una barra de herramientas) los crea Qt
# cuando quiere y dependen de la geometría. Y al envolverlos PyQt puede devolver un envoltorio OBSOLETO: el de una acción
# de una barra de matplotlib ya destruida cuya dirección de memoria se reutilizó (medido en el lote de tripwires: un
# `QScrollBar` cuyo padre aparecía como `QAction`; reproducido por Opus en 2 de 6 corridas de 181 pruebas). Por eso el
# recorrido distingue lo que creó PYTHON (nuestros widgets, que se devuelven) de lo que creó Qt (que se atraviesa con
# métodos de QObject, para llegar a las páginas de una pestaña, y NUNCA se devuelve).
_HOJAS = (QComboBox, QTabBar, QAbstractScrollArea, QLineEdit, QToolBar, FigureCanvasBase)


def _recorrer(raiz):
    """Cada widget NUESTRO (creado desde Python) bajo `raiz`, sin entrar en una hoja."""
    for hijo in raiz.children():
        if sip.ispycreated(hijo):
            if isinstance(hijo, QWidget):
                yield hijo
                if isinstance(hijo, QTabWidget):
                    # Las páginas por su ÍNDICE, no por `children()` del QStackedWidget interno: cada cambio de pestaña hace
                    # `raise()` de su página y Qt reordena ese hijo (orden de apilamiento).
                    for i in range(hijo.count()):
                        pagina = hijo.widget(i)
                        yield pagina
                        yield from _recorrer(pagina)
                elif not isinstance(hijo, _HOJAS):
                    yield from _recorrer(hijo)
        elif hijo.isWidgetType():
            yield from _recorrer(hijo)


def _atributos(objeto):
    """Los atributos de Python de un objeto como la huella los observa: los simples por su valor, los bytes por su md5 y las
    colecciones por su tamaño (lo demás son widgets y funciones, que la huella ya recorre por otro camino)."""
    atributos = {}
    for nombre, valor in vars(objeto).items():
        if isinstance(valor, (bytes, bytearray)):
            atributos[nombre] = ("bytes", hashlib.md5(valor).hexdigest())
        elif _simple(valor):
            atributos[nombre] = valor
        elif isinstance(valor, (list, tuple, dict, set)):
            atributos[nombre] = ("coleccion", len(valor))
    return atributos


def _huella(p, sin_vista_imagen=False):
    """Todo lo que se puede observar de una página, derivado del árbol de widgets y no de una lista de lo que 'Limpiar'
    limpia: cada widget (clase, habilitado, visible, y su estado según el tipo), cada barra de herramientas y cada lienzo
    que haya (modo, historial, botones marcados, bloqueo, ejes, artistas, límites, manejadores) y los atributos simples de
    la página (valores y nombres). Un widget, un lienzo o una barra nuevos de la página (PI.5 añade una pestaña) entran
    solos en la huella: no hay que declararlos.

    Las páginas de un QTabWidget se recorren por su índice y no por `children()`: cada cambio de pestaña hace `raise()` de su
    página y Qt reordena ese hijo (orden de apilamiento), así que dos páginas con el mismo estado salían en orden distinto. Hasta
    PI.4 no se notaba por un accidente de simetría (las pestañas del gris y de las capas tienen la misma estructura); la
    cuarta, distinta, lo rompió. Ordenar las listas lo arreglaba pero no veía el intercambio de estado entre dos widgets iguales
    (anchos X e Y cambiados: lo midió la revisión de Opus de PI.5)."""
    todos = list(_recorrer(p))
    widgets = []
    for w in todos:
        e = [type(w).__name__, w.objectName(), w.isEnabled(), w.isVisibleTo(p)]
        if isinstance(w, QLineEdit):
            e += [w.text(), w.isReadOnly()]
        elif isinstance(w, QLabel):
            e += [w.text()]
        elif isinstance(w, QComboBox):
            e += [w.count(), w.currentIndex(), w.currentText(), tuple(w.itemData(i) for i in range(w.count()))]
        elif isinstance(w, QPushButton):
            e += [w.text(), w.isChecked()]
        elif isinstance(w, QAbstractSlider):
            e += [w.value(), w.minimum(), w.maximum(), w.isSliderDown()]
        elif isinstance(w, QTabWidget):
            e += [w.count(), w.currentIndex(), tuple(w.tabText(i) for i in range(w.count()))]
        elif isinstance(w, QTableWidget):
            celdas = tuple(tuple(w.item(r, c).text() if w.item(r, c) else None for c in range(w.columnCount()))
                           for r in range(w.rowCount()))
            e += [w.rowCount(), w.columnCount(), w.currentRow(),
                  tuple(sorted(i.row() for i in w.selectionModel().selectedRows())), celdas]
        if type(w).__module__ == pagina_mod.__name__:
            # Un widget que DEFINE la pagina (la pestana sintetica de PI.5) lleva su propio estado de Python: que se calculo,
            # con que parametros, que barrido recuerda. Si 'Limpiar' lo dejara, la huella lo vería.
            e.append(tuple(sorted(_atributos(w).items(), key=lambda par: par[0])))
        widgets.append(tuple(e))

    barras = [w for w in todos if isinstance(w, NavigationToolbar2)]
    lienzos = [w for w in todos if isinstance(w, FigureCanvasBase)]
    infos_barras = []
    for i, barra in enumerate(barras):
        propia_vista = not (sin_vista_imagen and barra.canvas is p.lienzo_imagen)
        infos_barras.append((i, str(barra.mode), len(barra._nav_stack) if propia_vista else None,
                             barra._actions["zoom"].isChecked(), barra._actions["pan"].isChecked(),
                             barra.canvas.widgetlock.locked()))
    figuras, manejadores = [], []
    for i, lienzo in enumerate(lienzos):
        propia_vista = not (sin_vista_imagen and lienzo is p.lienzo_imagen)
        ejes = []
        for eje in lienzo.figure.axes:
            limites = (eje.get_xlim(), eje.get_ylim()) if propia_vista else None
            ejes.append((len(eje.images), len(eje.lines), len(eje.patches), len(eje.collections), len(eje.texts),
                         eje.get_xlabel(), eje.get_ylabel(), eje.get_title(), limites))
        figuras.append((i, tuple(ejes)))
        manejadores.append((i, tuple(sorted((evento, len(cb)) for evento, cb in lienzo.callbacks.callbacks.items()))))

    return {"widgets": widgets, "barras": infos_barras, "figuras": figuras, "lienzos": manejadores,
            "atributos": _atributos(p), "nombres": sorted(vars(p))}


def _resultado(imagen_bytes=BRAQUI_00, clics=CLICS_G1):
    return svc.analizar_imagen(imagen_bytes, clics)


def _texto_sin_simbolos(texto):
    return not any(c in texto for c in SIMBOLOS_DA18)


# =============================================================================================== 1-4: cargar la imagen

class TestCargarLaImagen:
    def test_1_el_nombre_es_visible_de_solo_lectura_y_sin_foco_y_dd7_propone_el_cambio(self, pagina, dialogos,
                                                                                    archivo_braqui):
        p = pagina
        assert p.estado == "vacia" and p.nombre_archivo.text() == "Ninguna imagen"
        assert p.nombre_archivo.isReadOnly() and p.nombre_archivo.focusPolicy() == Qt.NoFocus
        assert p.etiqueta_escaneo.text() == "Escanear a 600 dpi"
        assert p.selector_cambio.currentIndex() == 0 and p.selector_cambio.currentData() is None
        assert [p.selector_cambio.itemText(i) for i in range(p.selector_cambio.count())] == [
            "Elija el cambio de fuente", f"{CAMBIO} · fuente {SERIE_C}"]
        _cargar(p, dialogos, archivo_braqui)
        assert p.estado == "imagen" and p.nombre_archivo.text() == "braqui_00.jpeg"
        assert p.nombre_archivo.isReadOnly() and p.nombre_archivo.focusPolicy() == Qt.NoFocus
        assert p.etiqueta_fecha.text() == "Fecha: 2026-09-30, fecha del escaneo"
        assert p.etiqueta_resolucion.text() == "JPEG · Resolución: 600 dpi"
        assert p.selector_cambio.currentData() == CAMBIO       # DD7: a 3 días de la fecha del escaneo
        assert not dialogos.llamadas, "cargar una imagen buena no abre ningún diálogo"

    @pytest.mark.parametrize("cambio,dias,elegido", [
        ("2026-09-23", 7, True),          # exactamente a 7 días: entra (inclusive)
        ("2026-09-22", 8, False),         # a 8 días: sin elegir
        ("2026-09-30", 0, True),
        ("2026-10-05", 5, True)])         # posterior al escaneo: la distancia es simétrica
    def test_2_dd7_solo_propone_un_cambio_de_fuente_a_7_dias_o_menos(self, fabrica, dialogos, archivo_braqui, cambio,
                                                                      dias, elegido):
        p = fabrica((cambio,))
        _cargar(p, dialogos, archivo_braqui)
        assert abs((date.fromisoformat(cambio) - date(2026, 9, 30)).days) == dias
        assert (p.selector_cambio.currentData() == cambio) is elegido
        if not elegido:
            assert p.selector_cambio.currentIndex() == 0 and p.selector_cambio.currentData() is None

    def test_3_epson009_sin_exif_usa_la_fecha_de_modificacion_y_anota_los_96_dpi(self, fabrica, dialogos, tmp_path):
        ruta = tmp_path / "EPSON009.jpeg"
        shutil.copy(DATOS / "EPSON009.jpeg", ruta)
        marca = datetime(2026, 3, 3, 12, 0).timestamp()
        os.utime(ruta, (marca, marca))
        p = fabrica(("2026-03-01", "2026-09-27"))
        _cargar(p, dialogos, str(ruta))
        assert p.etiqueta_fecha.text() == "Fecha: 2026-03-03, fecha de modificación del archivo"
        assert p.selector_cambio.currentData() == "2026-03-01", "DD7 con la fecha del archivo, no con la de hoy"
        assert p.etiqueta_resolucion.text() == (
            "TIFF (extensión .jpeg) · Resolución: la imagen declara 96.012 dpi (lo escribe el editor al guardar); "
            "se usa la resolucion del escaneo: 600 dpi")

    def test_3b_una_imagen_de_otra_resolucion_dice_el_aviso_antes_de_marcar(self, pagina, dialogos, tmp_path):
        ruta = _a_300_con_mtime(tmp_path)
        _cargar(pagina, dialogos, str(ruta))
        assert pagina.etiqueta_resolucion.text().startswith("TIFF · Resolución: la imagen declara 300 dpi y el procedimiento "
                                                            "es de 600 dpi: parece escaneada a otra resolucion")

    def test_4_la_seleccion_automatica_no_pasa_a_otra_imagen_y_la_manual_si(self, fabrica, dialogos, archivo_braqui,
                                                                           tmp_path):
        epson = tmp_path / "EPSON009.jpeg"
        shutil.copy(DATOS / "EPSON009.jpeg", epson)
        marca = datetime(2026, 3, 3, 12, 0).timestamp()
        os.utime(epson, (marca, marca))
        p = fabrica(("2026-03-01", CAMBIO))
        _cargar(p, dialogos, archivo_braqui)
        assert p.selector_cambio.currentData() == CAMBIO
        _cargar(p, dialogos, str(epson))
        assert p.selector_cambio.currentData() == "2026-03-01", "la selección AUTOMÁTICA de la imagen anterior no se pega"
        # El físico elige a mano (`activated` solo lo emite el usuario, nunca un `setCurrentIndex`): esa SÍ se conserva.
        indice = p.selector_cambio.findData(CAMBIO)
        p.selector_cambio.setCurrentIndex(indice)
        p.selector_cambio.activated.emit(indice)
        _cargar(p, dialogos, archivo_braqui)
        _cargar(p, dialogos, str(epson))
        assert p.selector_cambio.currentData() == CAMBIO
        p.boton_limpiar.click()
        assert p.selector_cambio.currentIndex() == 0, "Limpiar devuelve el selector a su estado de arranque"
        _cargar(p, dialogos, str(epson))
        assert p.selector_cambio.currentData() == "2026-03-01", "tras Limpiar ya no hay selección manual que conservar"

    def test_4b_cancelar_el_dialogo_no_cambia_nada(self, pagina, dialogos):
        antes = _huella(pagina)
        dialogos.ruta = ""
        pagina.boton_imagen.click()
        assert _huella(pagina) == antes and not dialogos.llamadas


# ============================================================================================== 5-6: los dos clics

class TestLosDosClics:
    def test_5_dos_clics_analizan_con_espera_y_muestran_el_resultado(self, pagina, dialogos, archivo_braqui, monkeypatch):
        p = pagina
        _cargar(p, dialogos, archivo_braqui)
        orden, durante = [], []
        contador = {"poner": 0, "quitar": 0}
        real_poner, real_quitar = QApplication.setOverrideCursor, QApplication.restoreOverrideCursor
        monkeypatch.setattr(QApplication, "setOverrideCursor", staticmethod(
            lambda c: (contador.__setitem__("poner", contador["poner"] + 1), real_poner(c))[1]))
        monkeypatch.setattr(QApplication, "restoreOverrideCursor", staticmethod(
            lambda: (contador.__setitem__("quitar", contador["quitar"] + 1), real_quitar())[1]))
        procesados = []         # se REGISTRA (no se lanza): una excepción de pytest dentro de un slot de Qt aborta el proceso
        monkeypatch.setattr(QApplication, "processEvents", staticmethod(lambda *a, **k: procesados.append(1)))
        monkeypatch.setattr(p.indicador, "repaint", lambda: orden.append("repaint"))
        real = svc.analizar_imagen

        def espia(imagen_bytes, puntos, parametros=None):
            cursor = QApplication.overrideCursor()
            durante.append((cursor.shape() if cursor is not None else None, p.indicador.isHidden(),
                            p.boton_guardar.isEnabled(), p.indicador.text()))
            orden.append("analizar")
            return real(imagen_bytes, puntos, parametros)

        monkeypatch.setattr(svc, "analizar_imagen", espia)
        _clic(p, *CLICS_G1[0])
        assert p.estado == "imagen" and p.puntos == ((191.0, 377.0),) and not durante, "un solo clic no analiza"
        _clic(p, *CLICS_G1[1])
        assert durante == [(Qt.WaitCursor, False, False, "Analizando la imagen...")], \
            "durante el análisis: cursor de espera, indicador visible y Guardar deshabilitado"
        assert orden == ["repaint", "analizar"], "el indicador se repinta ANTES de analizar"
        assert contador == {"poner": 1, "quitar": 1} and QApplication.overrideCursor() is None
        assert procesados == [], "la espera no usa processEvents: dejaría entrar otro clic en mitad del análisis"
        assert p.indicador.isHidden()
        assert p.estado == "analizada" and p.pestanas.currentIndex() == 1
        assert p.puntos == ((191.0, 377.0), (190.0, 56.0)), "los clics se guardan redondeados a 3 decimales (X1)"
        assert p.recuadro_gris.text() == (
            "Desfase en la imagen: -8.55 px = -0.362 mm\n"
            "Incertidumbre (k = 2): 0.09 mm = 2.12 px (72 cuerdas)\n"
            "La fuente quedó 0.36 mm antes de la marca (banda de tránsito a la derecha de la imagen, 13 niveles)\n"
            "Tolerancia 1.0 mm: Cumple")
        capas = p.recuadro_rgb.text().split("\n")
        assert len(capas) == 3 and capas[0].startswith("Capa R: No medible: ")
        assert re.fullmatch(r"Capa G: desfase en la imagen -8\.\d\d px = -0\.35\d mm", capas[1]), capas[1]
        assert re.fullmatch(r"Capa B: desfase en la imagen -8\.\d\d px = -0\.35\d mm", capas[2]), capas[2]
        assert p.boton_guardar.isEnabled()
        assert len(p.eje_imagen.lines) == 2, "cada clic deja su marca"

    def test_5b_el_empate_del_pixel_472_5_no_depende_del_ruido_de_los_clics_reales(self, pagina, dialogos,
                                                                                archivo_braqui):
        """Con el ruido de 1e-13 de un `MouseEvent` real el motor daba -8.5251 en vez de -8.5533 (empate exacto en .5 de la
        ventana rotada). Redondear a 3 decimales lo deja exacto: el valor de la página es el de control del motor."""
        _analizada(pagina, dialogos, archivo_braqui)
        valores = motor.valores_medidos(_resultado())
        assert valores["desfase_gris_px"] == pytest.approx(-8.553322, abs=1e-6)
        assert "-8.55 px" in pagina.recuadro_gris.text()

    def test_6_los_clics_que_no_cuentan(self, pagina, dialogos, archivo_braqui, espia_analisis):
        p = pagina
        _cargar(p, dialogos, archivo_braqui)
        alto, ancho = 467, 1328
        # herramienta activa: la lupa y el desplazar bloquean el lienzo (`widgetlock`); un clic ahí no es un punto
        for herramienta in (p.barra_imagen.zoom, p.barra_imagen.pan):
            herramienta()
            assert p.lienzo_imagen.widgetlock.locked()
            _clic(p, 191, 377)
            herramienta()
            assert not p.lienzo_imagen.widgetlock.locked()
        assert p.puntos == (), "con la lupa o el desplazar activos no se marca nada"
        _clic(p, 191, 377, doble=True)
        _clic(p, 191, 377, boton=3)
        _clic(p, 191, 377, boton=2)
        assert p.puntos == (), "ni el doble clic ni los botones derecho y central"
        # fuera de la imagen: tras desplazar la vista los ejes muestran zona vacía, y ahí `inaxes` sí es el eje (X2)
        p.eje_imagen.set_xlim(-300, ancho + 300)
        p.eje_imagen.set_ylim(alto + 300, -300)
        for fuera in ((-50, -40), (-60, 300), (ancho + 20, 100), (100, alto + 20), (100, -20)):
            _clic(p, *fuera)
        assert p.puntos == () and not espia_analisis, f"fuera de la imagen no cuenta: {p.puntos}"
        _clic(p, 5.2, 5.2)       # cerca de la esquina, pero DENTRO
        assert p.puntos == ((5.2, 5.2),)

    def test_6b_un_tercer_clic_que_llega_durante_el_analisis_se_ignora(self, pagina, dialogos, archivo_braqui, monkeypatch):
        """Reentrada: un clic que llega mientras el análisis corre (por un bucle de eventos anidado) no puede añadir un
        tercer punto ni disparar otro análisis: el tope de dos puntos es lo que lo impide, porque el estado todavía es
        'imagen'."""
        p = pagina
        _cargar(p, dialogos, archivo_braqui)
        real = svc.analizar_imagen
        vistos = []

        def espia(imagen_bytes, puntos, parametros=None):
            vistos.append(len(puntos))
            _clic(p, 300, 100)               # llega a media análisis
            return real(imagen_bytes, puntos, parametros)

        monkeypatch.setattr(svc, "analizar_imagen", espia)
        _marcar(p)
        assert vistos == [2] and p.puntos == ((191.0, 377.0), (190.0, 56.0)) and p.estado == "analizada"

    def test_6c_despues_del_analisis_un_clic_mas_no_hace_nada(self, pagina, dialogos, archivo_braqui, espia_analisis):
        p = pagina
        _analizada(p, dialogos, archivo_braqui)
        antes = _huella(p)
        _clic(p, 300, 100)
        assert _huella(p) == antes and len(espia_analisis) == 1

    def test_6d_los_clics_antes_de_cargar_una_imagen_no_hacen_nada(self, pagina):
        antes = _huella(pagina)
        _clic(pagina, 0.5, 0.5)
        assert _huella(pagina) == antes and pagina.puntos == ()


# ============================================================================================== 7: los textos

class TestTextosDelRecuadro:
    def test_7_el_recuadro_de_la_placa_real_es_el_del_plan(self):
        assert pagina_mod.texto_recuadro(_resultado()) == (
            "Desfase en la imagen: -8.55 px = -0.362 mm\n"
            "Incertidumbre (k = 2): 0.09 mm = 2.12 px (72 cuerdas)\n"
            "La fuente quedó 0.36 mm antes de la marca (banda de tránsito a la derecha de la imagen, 13 niveles)\n"
            "Tolerancia 1.0 mm: Cumple")

    def test_7b_epson009_anade_la_nota_de_la_resolucion_del_editor(self):
        texto = pagina_mod.texto_recuadro(_resultado(EPSON009, CLICS_EPSON009))
        lineas = texto.split("\n")
        assert lineas[0] == "Desfase en la imagen: -2.60 px = -0.110 mm"
        assert lineas[1].startswith("Incertidumbre (k = 2): 0.18 mm = 4.25 px (") and lineas[1].endswith(" cuerdas)")
        assert lineas[2].startswith("La fuente quedó 0.11 mm antes de la marca (banda de tránsito a la derecha de la imagen")
        assert lineas[3] == "Tolerancia 1.0 mm: Cumple"
        assert lineas[4] == ("Resolución: la imagen declara 96.012 dpi (lo escribe el editor al guardar); "
                             "se usa la resolucion del escaneo: 600 dpi")
        assert len(lineas) == 5

    def test_7c_la_hoja_girada_180_cambia_el_signo_de_la_imagen_y_no_el_sentido_fisico(self):
        """El rótulo dice 'en la imagen': con la hoja girada el desfase de la imagen cambia de signo y el físico no (con el
        de la imagen el mismo PDF saldría con signos distintos según cómo se colocó la película)."""
        normal = pagina_mod.texto_recuadro(_resultado(*_hoja(False))).split("\n")
        girada = pagina_mod.texto_recuadro(_resultado(*_hoja(True))).split("\n")
        # la hoja es un PNG sin resolución declarada (la nota lo dice) y su gris sale del color: -8.87 px y no -8.55
        assert normal[0] == "Desfase en la imagen: -8.87 px = -0.375 mm"
        assert girada[0] == "Desfase en la imagen: 8.87 px = 0.375 mm"
        assert normal[2] == "La fuente quedó 0.38 mm antes de la marca (banda de tránsito a la derecha de la imagen, 13 niveles)"
        assert girada[2] == "La fuente quedó 0.38 mm antes de la marca (banda de tránsito a la izquierda de la imagen, 13 niveles)"
        for lineas in (normal, girada):
            assert lineas[3] == "Tolerancia 1.0 mm: Cumple" and lineas[1] == "Incertidumbre (k = 2): 0.10 mm = 2.44 px (75 cuerdas)"
            assert lineas[4].startswith("Resolución: la imagen no declara resolucion")

    def test_7d_sin_banda_de_transito_dice_el_sentido_de_la_imagen(self):
        imagen, puntos = _sintetica(-0.6)
        resultado = svc.analizar_imagen(imagen, puntos)
        assert resultado["lado_transito"] is None
        texto = pagina_mod.texto_recuadro(resultado)
        assert "La fuente quedó" not in texto
        assert "Sentido: a la derecha de la linea en la imagen (no se distingue la banda de transito)" in texto

    def test_7e_un_gris_no_medible_dice_por_que(self):
        resultado = _resultado(BRAQUI_00, CLICS_NO_MEDIBLE)
        assert resultado["perfiles"]["gris"]["estado"] == "no medible: la mancha se sale de la zona marcada", \
            "la situación tiene que existir antes de afirmar lo que la página hace con ella"
        assert pagina_mod.texto_recuadro(resultado) == "No medible: la mancha se sale de la zona marcada"
        assert pagina_mod.motivos_para_confirmar(resultado) == [
            "el perfil de grises no se pudo medir: la mancha se sale de la zona marcada"]

    def test_7f_una_resolucion_otra_da_pixeles_sin_milimetros_y_el_aviso(self):
        resultado = _resultado(_a_300_dpi(), CLICS_PLACA_REAL)
        assert resultado["clase_resolucion"] == "otra" and resultado["tamano_pixel_mm"] is None
        lineas = pagina_mod.texto_recuadro(resultado).split("\n")
        # el TIFF reescribe el color sin pérdida, pero su gris sale del color y no del JPEG: -8.56 px y no -8.55
        px = motor.valores_medidos(resultado)["desfase_gris_px"]
        assert abs(px - (-8.553322)) < 0.05 and lineas[0] == f"Desfase en la imagen: {px:.2f} px, sin milímetros"
        assert re.fullmatch(r"Incertidumbre \(k = 2\): \d\.\d\d px \(7\d cuerdas\)", lineas[1]), lineas[1]
        assert "parece escaneada a otra resolucion" in lineas[2] and lineas[2].endswith("Sin milimetros ni veredicto")
        assert len(lineas) == 3 and not any("mm =" in linea or "Tolerancia" in linea for linea in lineas)
        assert pagina_mod.motivos_para_confirmar(resultado) == [
            "no habrá milímetros ni veredicto: la imagen declara 300 dpi y el procedimiento es de 600 dpi"]

    @pytest.mark.parametrize("clics,mensaje", [
        (CLICS_LINEA_ALEJADA, "la linea refinada se aleja mas de 5 px de los clics: se usan los clics"),
        (CLICS_LINEA_NO_REFINADA, "no se pudo refinar la linea: se usan los clics")])
    def test_7g_una_linea_no_refinada_es_la_primera_linea_del_recuadro_y_no_se_puede_guardar(self, clics, mensaje):
        resultado = _resultado(BRAQUI_00, clics)
        assert resultado["mensaje_linea"] == mensaje and resultado["perfiles"]["gris"]["estado"] == "ok", \
            "la situación peligrosa (estado ok con la línea descartada) existe de verdad"
        motivo = pagina_mod.motivo_para_no_guardar(resultado)
        assert motivo == ("No se encontró la línea marcada cerca de los dos puntos (" + mensaje + "): el resultado se midió "
                          "contra los puntos, no contra la línea. Vuelva a marcarlos con la lupa (Recalcular)")
        # El recuadro dice el aviso y el desfase en píxeles SIN INTERPRETAR: ni milímetros, ni sentido, ni veredicto (con
        # +10 px decía "0.12 mm despues de la marca ... Cumple" sobre una película que mide -0.362 mm; medido por Opus).
        px = motor.valores_medidos(resultado)["desfase_gris_px"]
        assert pagina_mod.texto_recuadro(resultado) == (
            f"{motivo}\nDesfase medido contra los puntos, sin interpretar: {pagina_mod._numero(px, 2)} px")
        capas = pagina_mod.texto_recuadro_capas(resultado).split("\n")
        assert capas[0] == motivo and len(capas) == 4
        assert capas[1].startswith("Capa R: No medible: ")
        for linea, capa in ((capas[2], "G"), (capas[3], "B")):
            pxc = motor.valores_medidos(resultado)[f"desfase_{capa.lower()}_px"]
            assert linea == f"Capa {capa}: desfase medido contra los puntos, sin interpretar: {pagina_mod._numero(pxc, 2)} px"
        for texto in (pagina_mod.texto_recuadro(resultado), *capas):
            assert not any(palabra in texto for palabra in ("Cumple", "No cumple", "Tolerancia", "mm =", "La fuente quedó"))

    def test_7h_la_linea_refinada_literal_es_la_que_dice_el_motor(self):
        assert pagina_mod.LINEA_REFINADA == _resultado()["mensaje_linea"]
        assert pagina_mod.motivo_para_no_guardar(_resultado()) is None
        fuente = (RAIZ / "analisisImagenes" / "posicion_inicial_braqui.py").read_text(encoding="utf-8")
        assert f'"{pagina_mod.LINEA_REFINADA}"' in fuente

    def test_7i_nunca_menos_cero_y_nunca_simbolos_de_correcto_o_incorrecto(self):
        assert pagina_mod._numero(-0.001, 2) == "0.00" and pagina_mod._numero(-0.0004, 3) == "0.000"
        assert pagina_mod._numero(-0.005, 2) == "-0.01" and pagina_mod._numero(8.5533, 2) == "8.55"
        textos = [pagina_mod.texto_recuadro(_resultado()), pagina_mod.texto_recuadro(_resultado(EPSON009, CLICS_EPSON009)),
                  pagina_mod.texto_recuadro(_resultado(BRAQUI_00, CLICS_NO_MEDIBLE)),
                  pagina_mod.texto_recuadro(_resultado(_a_300_dpi(), CLICS_PLACA_REAL)),
                  pagina_mod.texto_recuadro(_resultado(BRAQUI_00, CLICS_LINEA_ALEJADA)),
                  *(pagina_mod.texto_capa(_resultado(), c) for c in "RGB"),
                  pagina_mod.texto_confirmacion(CAMBIO, True, ["el motivo"]),
                  pagina_mod.texto_resolucion(96.012), pagina_mod.texto_resolucion(None), pagina_mod.texto_resolucion(300.0),
                  pagina_mod.AVISO_SIN_CAMBIO]
        assert len(textos) == 13 and all(_texto_sin_simbolos(t) and "-0.00" not in t for t in textos)

    def test_7j_el_texto_de_la_resolucion_antes_de_analizar(self):
        assert pagina_mod.texto_resolucion(600.0) == "Resolución: 600 dpi"
        assert pagina_mod.texto_resolucion(599.999) == "Resolución: 600 dpi"
        assert pagina_mod.texto_resolucion(None) == ("Resolución: la imagen no declara resolucion; se usa la resolucion "
                                                     "del escaneo: 600 dpi")
        assert pagina_mod.texto_resolucion(72.0).startswith("Resolución: la imagen declara 72 dpi (lo escribe el editor")

    def test_7k_el_formato_se_muestra_por_el_contenido(self):
        assert pagina_mod.formato_de_la_imagen(EPSON009, "EPSON009.jpeg") == "TIFF (extensión .jpeg)"
        assert pagina_mod.formato_de_la_imagen(BRAQUI_00, "braqui_00.jpeg") == "JPEG"
        assert pagina_mod.formato_de_la_imagen(BRAQUI_00, "braqui_00.JPG") == "JPEG"
        assert pagina_mod.formato_de_la_imagen(b"no es una imagen", "x.png") is None

    @pytest.mark.parametrize("fecha,existe,motivos,esperado", [
        (CAMBIO, False, [], None),
        (CAMBIO, True, [], f"Ya hay una posición inicial guardada para el cambio de fuente del {CAMBIO}. ¿Reemplazarla?"),
        (CAMBIO, False, ["a"], "Antes de guardar:\n- a\n\n¿Guardar de todos modos?"),
        (CAMBIO, True, ["a", "b"], f"Antes de guardar:\n- ya hay una posición inicial guardada para el cambio de fuente "
                                   f"del {CAMBIO} (se reemplazará)\n- a\n- b\n\n¿Guardar de todos modos?")])
    def test_7l_la_pregunta_de_guardar_enumera_todo_lo_que_haya(self, fecha, existe, motivos, esperado):
        assert pagina_mod.texto_confirmacion(fecha, existe, motivos) == esperado


# =========================================================================================== 8: lo que se dibuja

@pytest.fixture(scope="module")
def resultado():
    return _resultado()


class TestLosDibujos:
    def _vertical(self, linea):
        x = linea.get_xdata()
        return len(x) == 2 and x[0] == x[1] and tuple(linea.get_ydata()) == (0, 1)

    def test_8_la_cuerda_central_de_la_placa_real_es_la_238(self, resultado):
        filas = resultado["perfiles"]["gris"]["filas"]
        assert len(filas) == 72 and pagina_mod.fila_representativa(resultado) == 238
        assert pagina_mod.fila_representativa(resultado) == int(filas[len(filas) // 2]) and 238 in filas

    def test_8b_el_perfil_sombrea_la_meseta_y_dibuja_los_dos_centros(self, resultado):
        fila = 238
        m = resultado["perfiles"]["gris"]["m"]
        ax = Figure().subplots()
        pagina_mod.dibujar_perfil(ax, resultado, "gris", fila)
        rectangulos = [p for p in ax.patches if p.get_width() > 0]
        assert len(rectangulos) == 1
        assert rectangulos[0].get_x() == pytest.approx(m["x_izq"][fila])
        assert rectangulos[0].get_x() + rectangulos[0].get_width() == pytest.approx(m["x_der"][fila])
        verticales = sorted(float(l.get_xdata()[0]) for l in ax.lines if self._vertical(l))
        centro_meseta = (m["x_izq"][fila] + m["x_der"][fila]) / 2
        assert len(verticales) == 2
        assert verticales == pytest.approx(sorted([centro_meseta, resultado["x_ref"][fila]]))
        # NO es el centro de los cruces: ese solo entra en la incertidumbre
        cruces = resultado["perfiles"]["gris"]["desfase_cruces_px"]
        assert abs(cruces - resultado["perfiles"]["gris"]["desfase_px"]) > 1e-6
        assert all(abs(v - (resultado["x_ref"][fila] - cruces)) > 1e-6 for v in verticales)

    def test_8c_un_perfil_que_no_se_mide_no_dibuja_el_centro(self, resultado):
        assert resultado["perfiles"]["R"]["estado"].startswith("no medible")
        ax = Figure().subplots()
        pagina_mod.dibujar_perfil(ax, resultado, "R", 238)
        verticales = [l for l in ax.lines if self._vertical(l)]
        assert len(verticales) == 1 and float(verticales[0].get_xdata()[0]) == pytest.approx(resultado["x_ref"][238])

    def test_8d_la_ventana_dibuja_la_referencia_los_bordes_y_el_centro_de_cada_cuerda(self, resultado):
        ax = Figure().subplots()
        pagina_mod.dibujar_ventana(ax, resultado, "gris", 238)
        assert len(ax.images) == 1
        no_horizontales = [l for l in ax.lines if len(l.get_xdata()) > 2]
        assert len(no_horizontales) == 4          # referencia, bordes izquierdo y derecho, centros
        ax_r = Figure().subplots()
        pagina_mod.dibujar_ventana(ax_r, resultado, "R", 238)
        assert len([l for l in ax_r.lines if len(l.get_xdata()) > 2]) == 1      # solo la referencia

    def test_8e_la_fila_sin_cuerdas_utiles_cae_en_la_fila_media_de_los_clics(self):
        resultado = _resultado(BRAQUI_00, CLICS_NO_MEDIBLE)
        resultado["perfiles"]["gris"]["filas"] = np.array([], int)
        fila = pagina_mod.fila_representativa(resultado)
        assert fila == int(round(float(np.mean(resultado["clics_ventana"][:, 1]))))


# =================================================================================== 9-13: guardar la prueba

class TestGuardar:
    def test_9_sin_cambio_de_fuente_elegido_avisa_y_no_guarda(self, fabrica, dialogos, archivo_braqui, bd, monkeypatch):
        p = fabrica(("2026-08-01",))                   # lejos de la fecha del escaneo: el selector queda sin elegir
        llamadas = []
        real = svc.guardar
        monkeypatch.setattr(svc, "guardar", lambda *a, **k: (llamadas.append(a), real(*a, **k))[1])
        _analizada(p, dialogos, archivo_braqui)
        assert p.selector_cambio.currentData() is None and p.boton_guardar.isEnabled()
        p.boton_guardar.click()
        assert [c["texto"] for c in dialogos.de("warning")] == [
            "Elija el cambio de fuente al que pertenece esta película. Si no aparece, guárdelo primero en el mensual de "
            "braquiterapia."]
        assert llamadas == [] and _numero_de_filas(bd) == 0 and p.estado == "analizada"
        assert not dialogos.de("question") and not dialogos.de("information")

    def test_10_guardar_deja_una_fila_con_los_bytes_la_serie_y_el_usuario(self, pagina, dialogos, archivo_braqui, bd,
                                                                         monkeypatch):
        p = pagina
        _analizada(p, dialogos, archivo_braqui)
        durante, real = [], svc.guardar

        def espia(*a, **k):
            cursor = QApplication.overrideCursor()
            durante.append((cursor.shape() if cursor is not None else None, p.indicador.isHidden(), p.indicador.text()))
            return real(*a, **k)

        monkeypatch.setattr(svc, "guardar", espia)
        p.boton_guardar.click()
        assert durante == [(Qt.WaitCursor, False, "Guardando...")], "guardar vuelve a analizar: va dentro de la espera"
        assert QApplication.overrideCursor() is None and p.indicador.isHidden()
        filas = _consulta(bd, "SELECT fecha, serie_fuente, user, imagen, imagen_nombre, imagen_md5, puntos, activo, "
                              "estado_gris, desfase_gris_px, dpi FROM braqui_posicion_inicial")
        assert len(filas) == 1
        fecha, serie, usuario, imagen, nombre, md5, puntos, activo, estado, desfase, dpi = filas[0]
        datos = Path(archivo_braqui).read_bytes()
        assert (fecha, serie, usuario, nombre, activo, estado, dpi) == (CAMBIO, SERIE_C, USUARIO, "braqui_00.jpeg", 1, "ok", 600.0)
        assert bytes(imagen) == datos and md5 == hashlib.md5(datos).hexdigest()
        assert json.loads(puntos) == [[191.0, 377.0], [190.0, 56.0]]
        assert desfase == pytest.approx(-8.553322, abs=1e-6)
        assert [(a[0], a[1]) for a in _auditoria(bd)] == [("guardar", USUARIO)]
        # la página: estado 'registro', sin Guardar, tabla refrescada, aviso con el cursor ya restaurado (X8)
        assert p.estado == "registro" and not p.boton_guardar.isEnabled() and p.tabla_registros.rowCount() == 1
        assert [c["texto"] for c in dialogos.de("information")] == [
            f"Posición inicial guardada para el cambio de fuente del {CAMBIO}."]
        assert dialogos.de("information")[0]["cursor"] is None
        assert p.etiqueta_registro.text() == f"Guardada: cambio de fuente del {CAMBIO}."
        celdas = [p.tabla_registros.item(0, c).text() for c in range(4)]
        assert celdas[:3] == [CAMBIO, SERIE_C, USUARIO]
        assert celdas[3].startswith("-0.36 ± 0.09 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm)")
        assert "Cambio de fuente" not in celdas[3]

    def test_10b_sin_usuario_no_se_guarda(self, fabrica, dialogos, archivo_braqui, bd):
        p = fabrica(usuario=Usuario(username="x", fullname=""))
        _analizada(p, dialogos, archivo_braqui)
        p.boton_guardar.click()
        assert _numero_de_filas(bd) == 0 and p.estado == "analizada"
        assert dialogos.de("warning")[0]["texto"] == "No se guardó: falta el usuario que guarda la prueba."

    def test_11_reguardar_pregunta_con_no_por_omision_y_el_si_reemplaza(self, pagina, dialogos, archivo_braqui, bd):
        p = pagina
        _guardada(p, dialogos, archivo_braqui)
        p.boton_recalcular.click()
        _marcar(p)
        assert p.estado == "analizada" and p.boton_guardar.isEnabled()
        dialogos.respuesta = QMessageBox.No
        p.boton_guardar.click()
        pregunta = dialogos.de("question")[-1]
        assert pregunta["texto"] == f"Ya hay una posición inicial guardada para el cambio de fuente del {CAMBIO}. ¿Reemplazarla?"
        assert pregunta["args"][3] == QMessageBox.Yes | QMessageBox.No and pregunta["args"][4] == QMessageBox.No
        assert pregunta["cursor"] is None
        assert [f[2] for f in _filas(bd)] == [1] and p.estado == "analizada", "contestar No no cambia nada"
        dialogos.respuesta = QMessageBox.Yes
        p.boton_guardar.click()
        assert [f[2] for f in _filas(bd)] == [0, 1] and p.estado == "registro"
        auditoria = _auditoria(bd)
        assert [a[0] for a in auditoria] == ["guardar", "reemplazo"] and "reemplaza id=1" in auditoria[1][3]
        assert p.tabla_registros.rowCount() == 1

    def test_11b_si_otro_guarda_justo_antes_no_se_reemplaza_en_silencio(self, pagina, dialogos, archivo_braqui, bd,
                                                                      monkeypatch):
        """La página pregunta con `existe_vigente` y pasa `reemplazar=existe`: si entre la pregunta y el guardado alguien
        guardó, el servicio rechaza (`PruebaYaGuardada`) y la página lo dice: nunca reemplaza sin que el físico lo haya
        confirmado."""
        _sembrar_prueba(bd, CAMBIO, SERIE_C)
        monkeypatch.setattr(svc, "existe_vigente", lambda fecha: False)       # la carrera
        _analizada(pagina, dialogos, archivo_braqui)
        pagina.boton_guardar.click()
        assert [f[2] for f in _filas(bd)] == [1] and pagina.estado == "analizada"
        assert dialogos.de("warning")[-1]["texto"] == (
            f"No se guardó: ya hay una posicion inicial guardada para el cambio de fuente del {CAMBIO}.")
        assert not dialogos.de("question")

    def test_12_un_gris_no_medible_se_guarda_solo_si_el_fisico_lo_confirma(self, pagina, dialogos, archivo_braqui, bd):
        p = pagina
        _analizada(p, dialogos, archivo_braqui, CLICS_NO_MEDIBLE)
        assert p.recuadro_gris.text() == "No medible: la mancha se sale de la zona marcada"
        assert p.boton_guardar.isEnabled(), "una línea refinada con el gris no medible se puede guardar, con confirmación"
        dialogos.respuesta = QMessageBox.No
        p.boton_guardar.click()
        pregunta = dialogos.de("question")[-1]
        assert pregunta["texto"] == ("Antes de guardar:\n- el perfil de grises no se pudo medir: la mancha se sale de la "
                                     "zona marcada\n\n¿Guardar de todos modos?")
        assert pregunta["args"][4] == QMessageBox.No
        assert _numero_de_filas(bd) == 0
        dialogos.respuesta = QMessageBox.Yes
        p.boton_guardar.click()
        assert len(dialogos.de("question")) == 2, "una sola pregunta por intento"
        assert _consulta(bd, "SELECT estado_gris, desfase_gris_px FROM braqui_posicion_inicial") == [
            ("no medible: la mancha se sale de la zona marcada", None)]

    def test_12b_una_resolucion_otra_se_guarda_en_pixeles_si_el_fisico_lo_confirma(self, pagina, dialogos, tmp_path, bd):
        ruta = _a_300_con_mtime(tmp_path)
        p = pagina
        _analizada(p, dialogos, str(ruta), CLICS_PLACA_REAL)
        assert "sin milímetros" in p.recuadro_gris.text()
        p.boton_guardar.click()
        assert dialogos.de("question")[-1]["texto"] == (
            "Antes de guardar:\n- no habrá milímetros ni veredicto: la imagen declara 300 dpi y el procedimiento es de "
            "600 dpi\n\n¿Guardar de todos modos?")
        fila = _consulta(bd, "SELECT dpi, tamano_pixel_mm, desfase_gris_mm, desfase_gris_px FROM braqui_posicion_inicial")
        assert len(fila) == 1 and fila[0][0] == 300.0 and fila[0][1] is None and fila[0][2] is None
        esperado = motor.valores_medidos(_resultado(_a_300_dpi(), CLICS_PLACA_REAL))["desfase_gris_px"]
        assert fila[0][3] == pytest.approx(esperado, abs=1e-9) and abs(esperado - (-8.553322)) < 0.05

    def test_12c_dos_motivos_y_la_prueba_ya_guardada_van_en_una_sola_pregunta(self, pagina, dialogos, tmp_path, bd):
        _sembrar_prueba(bd, CAMBIO, SERIE_C)
        ruta = _a_300_con_mtime(tmp_path)
        _analizada(pagina, dialogos, str(ruta), CLICS_PLACA_REAL)
        pagina.boton_guardar.click()
        assert len(dialogos.de("question")) == 1
        assert dialogos.de("question")[0]["texto"].startswith(
            f"Antes de guardar:\n- ya hay una posición inicial guardada para el cambio de fuente del {CAMBIO} (se "
            "reemplazará)\n- no habrá milímetros")

    @pytest.mark.parametrize("clics", [CLICS_LINEA_ALEJADA, CLICS_LINEA_NO_REFINADA])
    def test_13_con_la_linea_no_refinada_guardar_queda_deshabilitado(self, pagina, dialogos, archivo_braqui, bd, clics):
        p = pagina
        _analizada(p, dialogos, archivo_braqui, clics)
        assert not p.boton_guardar.isEnabled()
        assert p.recuadro_gris.text().startswith("No se encontró la línea marcada cerca de los dos puntos (")
        p._al_guardar()                              # ni siquiera llamando al manejador a la fuerza
        assert _numero_de_filas(bd) == 0 and not dialogos.llamadas and p.estado == "analizada"

    def test_13b_guardar_solo_se_habilita_en_un_analisis_bueno(self, pagina, dialogos, archivo_braqui):
        p = pagina
        assert not p.boton_guardar.isEnabled()                      # vacia
        _cargar(p, dialogos, archivo_braqui)
        assert not p.boton_guardar.isEnabled()                      # imagen, 0 puntos
        _clic(p, 191, 377)
        assert not p.boton_guardar.isEnabled() and p.estado == "imagen"        # imagen, 1 punto
        _clic(p, 190, 56)
        assert p.boton_guardar.isEnabled() and p.estado == "analizada"
        p.boton_guardar.click()
        assert not p.boton_guardar.isEnabled() and p.estado == "registro"
        for boton in (p.boton_imagen, p.boton_recalcular, p.boton_limpiar, p.boton_anular):
            assert boton.isEnabled()


# ====================================================================================================== 14: anular

class TestAnular:
    def test_14_sin_fila_elegida_avisa_y_no_pide_permiso(self, pagina, dialogos):
        pagina.boton_anular.click()
        assert dialogos.orden() == ["warning"] and dialogos.permisos == []
        assert dialogos.de("warning")[0]["texto"] == "Elija en la tabla la posición inicial que quiere anular."

    def test_14b_pregunta_primero_y_pide_el_permiso_despues(self, pagina, dialogos, archivo_braqui, bd):
        p = pagina
        _guardada(p, dialogos, archivo_braqui)
        dialogos.llamadas.clear()
        p.tabla_registros.selectRow(0)
        dialogos.respuesta = QMessageBox.No
        p.boton_anular.click()
        pregunta = dialogos.de("question")[0]
        assert pregunta["texto"] == f"¿Anular la posición inicial del cambio de fuente del {CAMBIO}?"
        assert pregunta["args"][3] == QMessageBox.Yes | QMessageBox.No and pregunta["args"][4] == QMessageBox.No
        assert dialogos.permisos == [] and _filas(bd)[0][2] == 1, "contestar No: ni permiso ni cambio (X12)"
        dialogos.respuesta = QMessageBox.Yes
        dialogos.permiso = QDialog.DialogCode.Rejected
        p.boton_anular.click()
        assert dialogos.orden() == ["question", "question", "permiso_construido", "permiso"], "primero lo concreto, después el permiso"
        assert _filas(bd)[0][2] == 1 and p.tabla_registros.rowCount() == 1, "permiso rechazado: sigue vigente"

    def test_14c_con_el_permiso_aceptado_anula_audita_y_vacia_la_tabla(self, pagina, dialogos, archivo_braqui, bd):
        p = pagina
        _guardada(p, dialogos, archivo_braqui)
        p.tabla_registros.selectRow(0)
        dialogos.respuesta = QMessageBox.Yes
        p.boton_anular.click()
        assert _filas(bd)[0][2] == 0 and p.tabla_registros.rowCount() == 0
        assert len(dialogos.permisos) == 1 and dialogos.permisos[0] is p.user_id, \
            "el permiso recibe el OBJETO de usuario, no su nombre"
        auditoria = _auditoria(bd)
        assert [(a[0], a[1]) for a in auditoria] == [("guardar", USUARIO), ("anular", USUARIO)]
        assert "anulada desde la página de posición inicial" in auditoria[1][3]
        assert p.etiqueta_registro.text() == "Registro anulado: ya no vale para ningún PDF.", \
            "el registro abierto (el recién guardado) dice que está anulado"

    def test_14d_un_registro_ya_anulado_por_otro_se_avisa(self, pagina, dialogos, archivo_braqui, bd):
        p = pagina
        _guardada(p, dialogos, archivo_braqui)
        p.tabla_registros.selectRow(0)
        _sql(bd, f"UPDATE {TABLA} SET activo = 0")
        p.boton_anular.click()
        assert dialogos.de("warning")[-1]["texto"] == "Esa posición inicial ya estaba anulada o ya no existe."
        assert p.tabla_registros.rowCount() == 0


# ========================================================================================= 15-16: limpiar y recalcular

class TestLimpiarYRecalcular:
    @staticmethod
    def _ciclo(p, dialogos, ruta, guardar):
        """Todo lo que un físico puede dejar puesto: selección manual, historial de las barras, la lupa y el desplazar
        activos, dos clics, las tres pestañas y, si se pide, un registro guardado y abierto."""
        _cargar(p, dialogos, ruta)
        indice = p.selector_cambio.findData(CAMBIO)
        p.selector_cambio.setCurrentIndex(indice)
        p.selector_cambio.activated.emit(indice)
        p.barra_imagen.push_current()
        p.barra_imagen.zoom()
        p.barra_imagen.zoom()
        _marcar(p)
        for barra in (p.barra_gris, p.barra_rgb):
            barra.push_current()
        p.barra_gris.pan()
        p.barra_rgb.zoom()
        p.pestanas.setCurrentIndex(2)
        if guardar:
            p.boton_guardar.click()
            p.tabla_registros.selectRow(0)
            p.tabla_registros.cellDoubleClicked.emit(0, 0)
            assert p.estado == "registro" and p._origen_seleccion == "registro"

    @pytest.mark.parametrize("guardar", [False, True])
    def test_15_limpiar_deja_una_pagina_igual_a_una_recien_creada(self, fabrica, dialogos, archivo_braqui, guardar):
        p = fabrica()
        self._ciclo(p, dialogos, archivo_braqui, guardar)
        sucia = _huella(p)
        assert sucia != _huella(fabrica()), "el ciclo cambió de verdad el estado (si no, la prueba no prueba nada)"
        p.boton_limpiar.click()
        nueva = fabrica()
        limpia, recien = _huella(p), _huella(nueva)
        for clave in recien:
            assert limpia[clave] == recien[clave], (f"'{clave}' no vuelve al estado de arranque:\n" + "\n".join(
                difflib.unified_diff([repr(x) for x in limpia[clave]], [repr(x) for x in recien[clave]],
                                     "limpia", "recien", lineterm="", n=2)) if isinstance(recien[clave], list) else clave)
        assert limpia == recien

    def test_15b_la_huella_ve_cada_cosa_que_limpiar_debe_borrar(self, fabrica, dialogos, archivo_braqui):
        """Prueba de la prueba: cada pieza del estado, estropeada una a una DESPUÉS de limpiar, cambia la huella."""
        p = fabrica()
        p.boton_limpiar.click()
        base = _huella(p)
        _cargar(p, dialogos, archivo_braqui)
        assert _huella(p) != base
        p.boton_limpiar.click()
        for estropear in (
                lambda: p._puntos.append((1.0, 1.0)),
                lambda: setattr(p, "_bytes", b"x"),
                lambda: p.selector_cambio.setCurrentIndex(1),
                lambda: p.barra_imagen.zoom(),
                lambda: p.barra_gris.push_current(),
                lambda: p.eje_imagen.plot([0, 1], [0, 1]),
                lambda: p.pestanas.setCurrentIndex(1),
                lambda: p.nombre_archivo.setText("otra"),
                lambda: p.boton_guardar.setEnabled(True),
                lambda: setattr(p, "_origen_seleccion", "manual")):
            estropear()
            assert _huella(p) != base
            p.boton_limpiar.click()
            assert _huella(p) == base, "Limpiar repara lo estropeado"

    def test_16_recalcular_conserva_imagen_nombre_y_selector_y_borra_lo_demas(self, fabrica, dialogos, archivo_braqui):
        p = fabrica(("2026-03-01", CAMBIO))
        _analizada(p, dialogos, archivo_braqui)
        indice = p.selector_cambio.findData("2026-03-01")
        p.selector_cambio.setCurrentIndex(indice)
        p.selector_cambio.activated.emit(indice)
        bytes_antes, nombre_antes = p._bytes, p._nombre
        p.boton_recalcular.click()
        assert p.estado == "imagen" and p.puntos == () and p._resultado is None
        assert p._bytes is bytes_antes and p._nombre == nombre_antes == "braqui_00.jpeg"
        assert p.selector_cambio.currentData() == "2026-03-01" and p._origen_seleccion == "manual"
        assert not p.boton_guardar.isEnabled() and p.pestanas.currentIndex() == 0
        assert len(p.eje_imagen.lines) == 0 and p.recuadro_gris.text() == "" and p.recuadro_rgb.text() == ""
        assert len(p.lienzo_gris.figure.axes) == 0 and len(p.lienzo_rgb.figure.axes) == 0
        assert len(p.eje_imagen.images) == 1, "la imagen sigue ahí"

    def test_16b_recalcular_converge_con_una_pagina_nueva_con_la_misma_imagen(self, fabrica, dialogos, archivo_braqui):
        p = fabrica()
        _analizada(p, dialogos, archivo_braqui)
        p.barra_gris.pan()
        p.barra_rgb.push_current()
        p.boton_recalcular.click()
        nueva = fabrica()
        _cargar(nueva, dialogos, archivo_braqui)
        assert _huella(p, sin_vista_imagen=True) == _huella(nueva, sin_vista_imagen=True)

    def test_16c_recalcular_sin_imagen_vuelve_a_vacia_y_apaga_las_herramientas(self, pagina):
        pagina.barra_imagen.zoom()
        assert pagina.lienzo_imagen.widgetlock.locked()
        pagina.boton_recalcular.click()
        assert pagina.estado == "vacia" and not pagina.lienzo_imagen.widgetlock.locked()

    def test_16d_tras_recalcular_se_puede_marcar_de_nuevo_y_guardar(self, pagina, dialogos, archivo_braqui, bd):
        p = pagina
        _analizada(p, dialogos, archivo_braqui, CLICS_LINEA_ALEJADA)
        assert not p.boton_guardar.isEnabled()
        p.boton_recalcular.click()
        _marcar(p)
        assert p.boton_guardar.isEnabled()
        p.boton_guardar.click()
        assert _numero_de_filas(bd) == 1


# ============================================================================================= 17-18: abrir un registro

class TestAbrirUnRegistro:
    def test_17_abrir_con_doble_clic_recalcula_con_los_parametros_guardados_sin_aviso(self, fabrica, dialogos,
                                                                                   archivo_braqui, bd, espia_analisis):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        valores_guardados = _consulta(bd, "SELECT parametros FROM braqui_posicion_inicial")[0][0]
        p.boton_limpiar.click()
        espia_analisis.clear()
        dialogos.llamadas.clear()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert not dialogos.llamadas, "lo recalculado coincide con lo guardado: ningún aviso"
        assert p.estado == "registro" and p.nombre_archivo.text() == "braqui_00.jpeg"
        assert p.puntos == ((191.0, 377.0), (190.0, 56.0)) and len(p.eje_imagen.lines) == 2
        assert p.selector_cambio.currentData() == CAMBIO and p._origen_seleccion == "registro"
        assert not p.boton_guardar.isEnabled() and p.pestanas.currentIndex() == 1
        assert p.recuadro_gris.text().startswith("Desfase en la imagen: -8.55 px = -0.362 mm")
        assert len(espia_analisis) == 1 and espia_analisis[0]["parametros"] == json.loads(valores_guardados), \
            "se recalcula con los PARÁMETROS guardados, no con los de hoy"
        assert p.etiqueta_registro.text() == f"Registro abierto: cambio de fuente del {CAMBIO}, guardado por {USUARIO}."
        assert p.etiqueta_fecha.text() == "" and "JPEG" in p.etiqueta_resolucion.text()

    def test_17b_abrir_por_la_api_publica_devuelve_true_y_un_id_inexistente_false(self, fabrica, dialogos, archivo_braqui,
                                                                               bd):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        id_registro = _filas(bd)[0][0]
        p.boton_limpiar.click()
        assert p.abrir_registro(id_registro) is True and p.estado == "registro"
        antes = _huella(p)
        assert p.abrir_registro(9999) is False
        assert dialogos.de("warning")[-1]["texto"] == "El registro ya no existe." and _huella(p) == antes

    def _alterar(self, bd, sql, parametros=()):
        _sql(bd, sql, parametros)

    def test_18_abrir_con_el_desfase_alterado_avisa_con_los_dos_valores(self, fabrica, dialogos, archivo_braqui, bd):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        tam = motor.PARAMETROS["resolucion_escaneo_dpi"]
        escala = 25.4 / tam
        px = _consulta(bd, "SELECT desfase_gris_px FROM braqui_posicion_inicial")[0][0] + 0.5
        _sql(bd, f"UPDATE {TABLA} SET desfase_gris_px = ?, desfase_gris_mm = ?", (px, px * escala))
        p.boton_limpiar.click()
        dialogos.llamadas.clear()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        aviso = dialogos.de("warning")
        assert len(aviso) == 1 and aviso[0]["texto"].startswith("Lo recalculado no coincide con lo guardado:\n")
        assert re.search(r"desfase del gris \[px\]: guardado -8\.05\d*, recalculado -8\.55\d*", aviso[0]["texto"])
        assert "desfase del gris [mm]: guardado" in aviso[0]["texto"]
        assert "Lo recalculado no coincide con lo guardado:" in p.etiqueta_registro.text(), "queda fijo en la etiqueta"
        assert p.estado == "registro", "se abre igual: el físico ve las dos cosas"

    def test_18b_abrir_con_otra_version_del_algoritmo_avisa(self, fabrica, dialogos, archivo_braqui, bd):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        _sql(bd, f"UPDATE {TABLA} SET version_algoritmo = 'PI-0'")
        p.boton_limpiar.click()
        dialogos.llamadas.clear()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert "versión del algoritmo: guardada PI-0, actual PI-2" in dialogos.de("warning")[0]["texto"]

    def test_18c_abrir_con_el_lado_del_transito_cambiado_avisa(self, fabrica, dialogos, archivo_braqui, bd):
        """El signo que imprime el PDF sale del lado del tránsito: comparar solo `desfase_*_px` lo dejaría pasar."""
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        _sql(bd, f"UPDATE {TABLA} SET lado_transito = 'izquierda'")
        p.boton_limpiar.click()
        dialogos.llamadas.clear()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert "lado de la banda de tránsito: guardado izquierda, recalculado derecha" in dialogos.de("warning")[0]["texto"]

    def test_18d_un_registro_cuyo_cambio_de_fuente_ya_no_existe_se_abre_y_lo_dice(self, fabrica, dialogos, archivo_braqui,
                                                                               bd):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        _sql(bd, "UPDATE TipoCalibracion SET activo = 0")
        p.boton_limpiar.click()
        assert p.tabla_registros.item(0, 0).text() == f"{CAMBIO}, sin cambio de fuente vigente en esa fecha"
        dialogos.llamadas.clear()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p.estado == "registro" and p.selector_cambio.currentIndex() == 0 and p._origen_seleccion is None
        assert p.selector_cambio.count() == 1, "no se inventan entradas falsas en el combo"
        assert "Su cambio de fuente ya no existe vigente" in p.etiqueta_registro.text()
        assert not dialogos.llamadas

    def test_18e_un_registro_anulado_se_abre_por_su_id_y_lo_dice(self, fabrica, dialogos, archivo_braqui, bd):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        id_registro = _filas(bd)[0][0]
        _sql(bd, f"UPDATE {TABLA} SET activo = 0")
        assert p.abrir_registro(id_registro) is True
        assert "Este registro está anulado: no vale para ningún PDF." in p.etiqueta_registro.text()

    @pytest.mark.parametrize("estropicio", ["imagen", "puntos", "parametros"])
    def test_18f_un_registro_ilegible_avisa_y_la_pagina_queda_como_estaba(self, fabrica, dialogos, archivo_braqui, bd,
                                                                         estropicio):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        id_registro = _filas(bd)[0][0]
        if estropicio == "imagen":
            _sql(bd, f"UPDATE {TABLA} SET imagen = ?", (b"esto no es una imagen",))
        else:
            _sql(bd, f"UPDATE {TABLA} SET {estropicio} = 'no es json'")
        p.boton_limpiar.click()
        antes = _huella(p)
        dialogos.llamadas.clear()
        assert p.abrir_registro(id_registro) is False
        assert _huella(p) == antes and len(dialogos.de("warning")) == 1


@pytest.fixture(scope="module")
def base():
    resultado = _resultado()
    registro = dict(motor.valores_medidos(resultado), version_algoritmo=resultado["version"])
    return resultado, registro


class TestDiferenciasConLoGuardado:
    def test_lo_recalculado_igual_no_da_diferencias(self, base):
        resultado, registro = base
        assert pagina_mod.diferencias_con_lo_guardado(registro, resultado) == []

    def test_cada_una_de_las_17_claves_y_la_version_se_compara(self, base):
        resultado, registro = base
        claves = sorted(motor.valores_medidos(resultado))
        assert len(claves) == 17
        con_numero = [c for c in claves if isinstance(registro[c], float)]
        sin_numero = [c for c in claves if not isinstance(registro[c], float)]
        assert len(con_numero) == 9 and len(sin_numero) == 8, "compuerta: la composición del registro de control"
        corridos = 0
        for clave in claves:
            alterado = dict(registro)
            if clave in con_numero:
                alterado[clave] = registro[clave] + (0.5 if clave.endswith("_px") else 0.05)
            elif clave == "filas_gris":
                alterado[clave] = registro[clave] + 1
            else:
                alterado[clave] = "otra cosa"
            diferencias = pagina_mod.diferencias_con_lo_guardado(alterado, resultado)
            rotulo = pagina_mod.ROTULOS_DE_LO_GUARDADO[clave]
            assert len(diferencias) == 1 and diferencias[0].startswith(f"{rotulo}: guardado "), (clave, diferencias)
            corridos += 1
        assert corridos == 17
        diferencias = pagina_mod.diferencias_con_lo_guardado(dict(registro, version_algoritmo="PI-0"), resultado)
        assert diferencias == ["versión del algoritmo: guardada PI-0, actual PI-2"]

    def test_las_tolerancias_son_001_px_y_001_px_en_milimetros(self, base):
        resultado, registro = base
        escala = resultado["tamano_pixel_mm"]
        for clave, justo_dentro, justo_fuera in (
                ("desfase_gris_px", 0.009, 0.011), ("desfase_gris_mm", 0.009 * escala, 0.011 * escala),
                ("incertidumbre_gris_px", 0.009, 0.011), ("tamano_pixel_mm", 1e-12, 1e-6)):
            dentro = dict(registro, **{clave: registro[clave] + justo_dentro})
            fuera = dict(registro, **{clave: registro[clave] + justo_fuera})
            assert pagina_mod.diferencias_con_lo_guardado(dentro, resultado) == [], clave
            assert len(pagina_mod.diferencias_con_lo_guardado(fuera, resultado)) == 1, clave

    def test_un_valor_guardado_nulo_contra_uno_calculado_es_una_diferencia(self, base):
        resultado, registro = base
        diferencias = pagina_mod.diferencias_con_lo_guardado(dict(registro, desfase_gris_px=None), resultado)
        assert len(diferencias) == 1 and diferencias[0].startswith("desfase del gris [px]: guardado None, recalculado -8.5533")


# ================================================================================ 19-21 y 25: lo que falla

class TestLoQueFalla:
    def test_19_un_analisis_que_lanza_restaura_el_cursor_avisa_y_deja_la_pagina_fallida(self, pagina, dialogos,
                                                                                     archivo_braqui, monkeypatch):
        dialogos.criticos_esperados = True
        p = pagina
        _cargar(p, dialogos, archivo_braqui)

        def revienta(*a, **k):
            raise RuntimeError("fallo del analisis")

        monkeypatch.setattr(svc, "analizar_imagen", revienta)
        _marcar(p)
        critico = dialogos.de("critical")
        assert len(critico) == 1 and "RuntimeError: fallo del analisis" in critico[0]["texto"]
        assert critico[0]["cursor"] is None, "el diálogo se abre con el cursor ya restaurado (X8)"
        assert QApplication.overrideCursor() is None and p.indicador.isHidden()
        assert p.estado == "fallida" and not p.boton_guardar.isEnabled() and p.pestanas.currentIndex() == 0
        assert p.recuadro_gris.text() == "" and p._resultado is None
        p.boton_recalcular.click()
        assert p.estado == "imagen"

    def test_19b_dos_puntos_iguales_son_un_aviso_y_no_un_error(self, pagina, dialogos, archivo_braqui):
        p = pagina
        _cargar(p, dialogos, archivo_braqui)
        _clic(p, 400, 200)
        _clic(p, 400, 200)
        aviso = dialogos.de("warning")
        assert len(aviso) == 1 and aviso[0]["texto"] == (
            "No se pudo analizar: los dos puntos coinciden: marque dos puntos distintos de la linea. "
            "Pulse Recalcular para marcar otra vez.")
        assert aviso[0]["cursor"] is None and p.estado == "fallida" and QApplication.overrideCursor() is None

    def test_20_un_analisis_que_falla_despues_de_uno_bueno_no_deja_el_resultado_anterior(self, pagina, dialogos,
                                                                                      archivo_braqui, monkeypatch):
        """IM3: antes de analizar se descarta el resultado anterior; si no, un fallo dejaría un resultado viejo (con
        Guardar habilitado) contra los puntos nuevos."""
        p = pagina
        _analizada(p, dialogos, archivo_braqui)
        assert p.boton_guardar.isEnabled() and p.recuadro_gris.text() != ""
        monkeypatch.setattr(svc, "analizar_imagen", lambda *a, **k: (_ for _ in ()).throw(ValueError("falla")))
        assert p._analizar(None) is None
        assert p._resultado is None and not p.boton_guardar.isEnabled() and p.estado == "fallida"
        assert p.recuadro_gris.text() == "" and p.recuadro_rgb.text() == "" and len(p.lienzo_gris.figure.axes) == 0

    # A.1 (12-10, P11 «medir»): el segundo caso («transparentes»: una imagen con la mitad transparente se rechazaba y la página quedaba igual) ya no existe: la
    # imagen con zonas transparentes se LEE y se mide lo que no toca (la prueba nueva está en tests/test_a1_lector_de_peliculas.py::
    # TestLaPaginaMuestraLos16BitsEnUint8::test_c_una_imagen_con_zonas_transparentes_se_carga_sin_avisos). Queda el de los bytes que no son una imagen.
    @pytest.mark.parametrize("contenido,fragmento", [
        (b"esto no es una imagen", "No se reconoce el formato de la imagen")])
    def test_21_una_imagen_ilegible_no_cambia_nada(self, pagina, dialogos, archivo_braqui, tmp_path, contenido, fragmento):
        p = pagina
        _analizada(p, dialogos, archivo_braqui)
        antes = _huella(p)
        ruta = tmp_path / "mala.png"
        ruta.write_bytes(contenido)
        dialogos.llamadas.clear()
        _cargar(p, dialogos, str(ruta))
        assert len(dialogos.de("warning")) == 1 and fragmento in dialogos.de("warning")[0]["texto"]
        assert _huella(p) == antes, "la carga es atómica: si falla, la página queda igual (X7)"

    def test_21b_un_archivo_que_no_existe_no_cambia_nada(self, pagina, dialogos, tmp_path):
        antes = _huella(pagina)
        _cargar(pagina, dialogos, str(tmp_path / "no_existe.png"))
        assert len(dialogos.de("warning")) == 1 and _huella(pagina) == antes

    def test_25_ningun_dialogo_se_abre_con_el_cursor_de_espera_puesto(self, pagina, dialogos, archivo_braqui, bd,
                                                                    monkeypatch):
        dialogos.criticos_esperados = True
        p = pagina
        _analizada(p, dialogos, archivo_braqui)
        p.boton_guardar.click()                                          # information
        p.boton_recalcular.click()
        _clic(p, 400, 200)
        _clic(p, 400, 200)                                               # warning (dos puntos iguales)
        p.boton_recalcular.click()
        _marcar(p, CLICS_NO_MEDIBLE)
        dialogos.respuesta = QMessageBox.No
        p.boton_guardar.click()                                          # question
        p.boton_recalcular.click()
        monkeypatch.setattr(svc, "analizar_imagen", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
        _marcar(p)                                                       # critical
        tipos = {c["tipo"] for c in dialogos.llamadas}
        assert {"information", "warning", "question", "critical"} <= tipos, tipos
        assert all(c["cursor"] is None for c in dialogos.llamadas), \
            [(c["tipo"], c["cursor"]) for c in dialogos.llamadas if c["cursor"] is not None]

    def test_25b_un_error_inesperado_en_un_manejador_no_escapa(self, pagina, dialogos, archivo_braqui, bd, monkeypatch):
        """X9: una excepción dentro de un slot no sale a Qt (aborta el proceso bajo pytest-qt y se pierde en la app):
        se imprime la traza y se avisa."""
        dialogos.criticos_esperados = True
        _analizada(pagina, dialogos, archivo_braqui)
        monkeypatch.setattr(svc, "existe_vigente", lambda fecha: (_ for _ in ()).throw(OSError("disco lleno")))
        pagina.boton_guardar.click()
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["titulo"] == "Guardar" and "OSError: disco lleno" in critico[0]["texto"]
        assert _numero_de_filas(bd) == 0 and pagina.estado == "analizada"


# ================================================================================ 22 y 24: el caché y la barra

class TestRefrescarYLaBarra:
    def test_22_showevent_trae_un_cambio_de_fuente_sembrado_despues_y_conserva_la_seleccion(self, pagina, bd):
        p = pagina
        assert p.selector_cambio.count() == 2
        _calibracion(bd, "2026-10-01 09:00:00", "Cambio de fuente", SERIE_A)
        p.show()
        assert p.selector_cambio.count() == 3
        assert p.selector_cambio.itemData(1) == "2026-10-01", "el más reciente primero"
        indice = p.selector_cambio.findData(CAMBIO)
        p.selector_cambio.setCurrentIndex(indice)
        p.selector_cambio.activated.emit(indice)
        p.hide()
        _calibracion(bd, "2026-10-02 09:00:00", "Cambio de fuente", SERIE_A)
        p.show()
        assert p.selector_cambio.count() == 4 and p.selector_cambio.currentData() == CAMBIO, "la elección manual se conserva"
        _sql(bd, "UPDATE TipoCalibracion SET activo = 0 WHERE fecha LIKE ?", (f"{CAMBIO}%",))
        p.refrescar()
        assert p.selector_cambio.currentIndex() == 0 and p._origen_seleccion is None, \
            "si su cambio de fuente ya no existe, queda sin elegir"

    def test_22b_refrescar_recalcula_la_seleccion_automatica_con_la_fecha_del_escaneo(self, fabrica, dialogos, archivo_braqui,
                                                                                    bd):
        p = fabrica(("2026-08-01",))
        _cargar(p, dialogos, archivo_braqui)
        assert p.selector_cambio.currentData() is None
        _calibracion(bd, "2026-09-29 09:00:00", "Cambio de fuente", SERIE_A)
        p.refrescar()
        assert p.selector_cambio.currentData() == "2026-09-29" and p._origen_seleccion == "automatica"

    def test_22c_refrescar_muestra_los_registros_nuevos(self, pagina, bd):
        assert pagina.tabla_registros.rowCount() == 0
        _sembrar_prueba(bd, CAMBIO, SERIE_C)
        pagina.refrescar()
        assert pagina.tabla_registros.rowCount() == 1 and pagina.tabla_registros.item(0, 0).text() == CAMBIO

    def test_24_dos_imagenes_seguidas_no_duplican_el_manejador_y_vacian_el_historial(self, pagina, dialogos, archivo_braqui,
                                                                                    tmp_path):
        p = pagina
        manejadores = lambda: len(p.lienzo_imagen.callbacks.callbacks.get("button_press_event", {}))
        antes = manejadores()
        segunda = tmp_path / "otra.jpeg"
        shutil.copy(DATOS / "braqui_00.jpeg", segunda)
        _cargar(p, dialogos, archivo_braqui)
        p.barra_imagen.push_current()
        assert len(p.barra_imagen._nav_stack) == 1
        _cargar(p, dialogos, str(segunda))
        assert manejadores() == antes, "un solo manejador de clics (hecho en la construcción)"
        assert len(p.barra_imagen._nav_stack) == 0, "sin barra.update() Home volvería a la vista de la imagen anterior"
        _marcar(p)
        assert p.estado == "analizada" and len(p.eje_imagen.lines) == 2, "un clic = una marca, no dos"
        p.barra_gris.push_current()
        p.boton_recalcular.click()
        _marcar(p)
        assert len(p.barra_gris._nav_stack) == 0

    def test_24b_cargar_otra_imagen_apaga_la_lupa_y_descarta_el_resultado_y_los_puntos(self, pagina, dialogos,
                                                                                     archivo_braqui, tmp_path):
        p = pagina
        _analizada(p, dialogos, archivo_braqui)
        p.barra_gris.pan()
        segunda = tmp_path / "otra.jpeg"
        shutil.copy(DATOS / "braqui_00.jpeg", segunda)
        _cargar(p, dialogos, str(segunda))
        assert p.estado == "imagen" and p.puntos == () and p._resultado is None and not p.boton_guardar.isEnabled()
        assert not p.barra_gris.mode and not p.lienzo_gris.widgetlock.locked()
        assert len(p.eje_imagen.lines) == 0 and p.recuadro_gris.text() == ""
        assert p.nombre_archivo.text() == "otra.jpeg"


# =========================================================================================== 23: la imagen grande

class TestMemoriaDeLaImagenGrande:
    def test_23_la_pagina_completa_del_escaner_se_dibuja_en_rgb_uint8_con_poca_memoria(self, pagina, dialogos):
        """EPSON031 (6600 x 5100): mostrada como gris 2D con colormap pedía 2062 MB y 732 ms por dibujo; como RGB uint8
        con `nearest`, 129 MB y 110 ms. Se mide MEMORIA (determinista); el tiempo es inestable (Trampa 7)."""
        p = pagina
        _cargar(p, dialogos, str(DATOS / "EPSON031.JPG"))
        assert p.estado == "imagen"
        matriz = p.eje_imagen.images[0].get_array()
        assert matriz.dtype == np.uint8 and matriz.shape == (6600, 5100, 3)
        assert p.eje_imagen.images[0].get_interpolation() == "nearest"
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            p.lienzo_imagen.draw()
            pico = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert pico < 500e6, f"dibujar la página completa pidió {pico / 1e6:.0f} MB"
        _marcar(p, CLICS_EPSON031)
        assert p.estado == "analizada" and p.recuadro_gris.text().startswith("Desfase en la imagen: -8.47 px = -0.359 mm")


# ========================================================================================= 26: por AST, lo que no hace

# ======================================================================== el cambio de fuente elegido (revisión de Opus)

def _a_300_con_mtime(tmp_path, nombre="a_300.tif"):
    """El TIFF a 300 dpi (sin EXIF) con una fecha de modificación FIJA, la del escaneo de braqui_00 (2026-09-30): sin EXIF, DD7 usa la fecha
    del archivo, y con la de HOY la prueba dependía del día en que corría (a 7 días de `CAMBIO` propone el cambio de fuente, a 8 ya no, y
    sin él no hay pregunta de resolución: la corrida de la suite que cruzó la medianoche del 04 al 05-10 las puso en rojo)."""
    ruta = tmp_path / nombre
    ruta.write_bytes(_a_300_dpi())
    marca = datetime(2026, 9, 30, 12, 0).timestamp()
    os.utime(ruta, (marca, marca))
    return ruta


def _con_mtime(tmp_path, nombre_origen, ano, mes, dia, destino=None):
    """Copia una placa real a `tmp_path` con la fecha de modificación pedida (la que usa DD7 cuando no hay EXIF)."""
    ruta = tmp_path / (destino or nombre_origen)
    shutil.copy(DATOS / nombre_origen, ruta)
    marca = datetime(ano, mes, dia, 12, 0).timestamp()
    os.utime(ruta, (marca, marca))
    return str(ruta)


class TestElCambioDeFuenteElegido:
    """Cuatro caminos medidos por Opus para guardar bajo un cambio de fuente lejano a la fecha de la película SIN que nada
    preguntara (la selección manual se pega a las imágenes siguientes, un cambio de fuente anulado desplaza la propuesta, el
    rótulo 'Elija...' apaga DD7, y un paso de la rueda del ratón sobre el combo cerrado lo cambia), más los huecos de la
    prueba de DD7 (mutaciones N12, N15 y N16)."""

    def test_4c_una_imagen_sin_cambio_de_fuente_cercano_no_hereda_la_automatica_de_la_anterior(self, fabrica, dialogos,
                                                                                            archivo_braqui, tmp_path):
        p = fabrica((CAMBIO,))
        _cargar(p, dialogos, archivo_braqui)
        assert p.selector_cambio.currentData() == CAMBIO and p._origen_seleccion == "automatica"
        _cargar(p, dialogos, _con_mtime(tmp_path, "EPSON009.jpeg", 2026, 6, 1))        # a 66 días de cualquier cambio de fuente
        assert p.selector_cambio.currentIndex() == 0 and p._origen_seleccion is None, \
            "el cambio de fuente de la imagen A queda pegado a la B: el riesgo que DD7 existe para evitar"

    def test_4d_la_seleccion_de_un_registro_abierto_no_se_pega_a_la_imagen_siguiente(self, fabrica, dialogos,
                                                                                  archivo_braqui, tmp_path):
        p = fabrica(("2026-03-01", CAMBIO))
        _guardada(p, dialogos, archivo_braqui)
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p._origen_seleccion == "registro" and p.selector_cambio.currentData() == CAMBIO
        _cargar(p, dialogos, _con_mtime(tmp_path, "EPSON009.jpeg", 2026, 3, 3))
        assert p.selector_cambio.currentData() == "2026-03-01", "abrir un registro no es elegir a mano"

    def test_4e_la_rueda_del_raton_no_cambia_el_cambio_de_fuente_si_el_combo_no_tiene_el_foco(self, fabrica, dialogos,
                                                                                            archivo_braqui):
        p = fabrica(("2026-03-01", CAMBIO))
        _cargar(p, dialogos, archivo_braqui)
        assert p.selector_cambio.currentData() == CAMBIO and not p.selector_cambio.hasFocus()
        rueda = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), 0, Qt.Vertical, Qt.NoButton,
                            Qt.NoModifier)
        QApplication.sendEvent(p.selector_cambio, rueda)
        assert p.selector_cambio.currentData() == CAMBIO and p._origen_seleccion == "automatica" and not rueda.isAccepted()

    def test_4f_el_selector_no_se_deja_enfocar_por_la_rueda(self, pagina):
        assert pagina.selector_cambio.focusPolicy() == Qt.StrongFocus and type(pagina.selector_cambio).__name__ == "_SelectorSinRueda"

    def test_9c_guardar_bajo_un_cambio_de_fuente_lejano_de_la_pelicula_pide_confirmar(self, fabrica, dialogos,
                                                                                    archivo_braqui, bd):
        p = fabrica(("2026-03-01", CAMBIO))
        _analizada(p, dialogos, archivo_braqui)
        indice = p.selector_cambio.findData("2026-03-01")
        p.selector_cambio.setCurrentIndex(indice)
        p.selector_cambio.activated.emit(indice)                    # el físico elige a mano un cambio de fuente de hace meses
        dias = (date(2026, 9, 30) - date(2026, 3, 1)).days
        assert dias == 213
        dialogos.respuesta = QMessageBox.No
        p.boton_guardar.click()
        pregunta = dialogos.de("question")[-1]
        assert pregunta["texto"] == ("Antes de guardar:\n- la película es del 2026-09-30 (fecha del escaneo) y el cambio de "
                                     f"fuente elegido es del 2026-03-01: {dias} días de diferencia\n\n¿Guardar de todos modos?")
        assert pregunta["args"][4] == QMessageBox.No and _numero_de_filas(bd) == 0
        dialogos.respuesta = QMessageBox.Yes
        p.boton_guardar.click()
        assert len(dialogos.de("question")) == 2 and _consulta(bd, f"SELECT fecha FROM {TABLA}") == [("2026-03-01",)]

    def test_9d_con_la_fecha_de_modificacion_la_pregunta_lo_dice(self, fabrica, dialogos, tmp_path):
        p = fabrica(("2026-03-01", CAMBIO))
        _analizada(p, dialogos, _con_mtime(tmp_path, "braqui_00.jpeg", 2026, 9, 30, destino="sin_exif.png"), CLICS_G1)
        # (el JPEG trae EXIF: el origen es 'fecha del escaneo'; con la EPSON009, que no lo trae, es la de modificación)
        p.boton_limpiar.click()
        _analizada(p, dialogos, _con_mtime(tmp_path, "EPSON009.jpeg", 2026, 9, 30), CLICS_EPSON009)
        indice = p.selector_cambio.findData("2026-03-01")
        p.selector_cambio.setCurrentIndex(indice)
        p.selector_cambio.activated.emit(indice)
        dialogos.respuesta = QMessageBox.No
        p.boton_guardar.click()
        assert "la película es del 2026-09-30 (fecha de modificación del archivo) y el cambio de fuente elegido" in \
            dialogos.de("question")[-1]["texto"]

    def test_9e_dentro_de_los_7_dias_no_se_pregunta_nada(self, fabrica, dialogos, archivo_braqui, bd):
        p = fabrica(("2026-09-23",))                                  # a exactamente 7 días de la fecha del escaneo
        _analizada(p, dialogos, archivo_braqui)
        assert p.selector_cambio.currentData() == "2026-09-23"
        p.boton_guardar.click()
        assert not dialogos.de("question") and _numero_de_filas(bd) == 1

    @pytest.mark.parametrize("dias", [0, 7, -7, 8, -8, 213])
    def test_9f_el_motivo_de_distancia_es_a_mas_de_7_dias_en_cualquier_sentido(self, dias):
        pelicula = date(2026, 9, 30)
        cambio = (pelicula + timedelta(days=dias)).isoformat()
        motivo = pagina_mod.motivo_de_distancia(cambio, pelicula, "fecha del escaneo")
        if abs(dias) <= 7:
            assert motivo is None
        else:
            assert motivo == (f"la película es del 2026-09-30 (fecha del escaneo) y el cambio de fuente elegido es del "
                              f"{cambio}: {abs(dias)} días de diferencia")

    def test_9g_sin_fecha_de_la_pelicula_o_sin_origen(self):
        assert pagina_mod.motivo_de_distancia("2026-03-01", None) is None            # un registro abierto no tiene fecha de escaneo
        assert pagina_mod.motivo_de_distancia("2026-03-01", date(2026, 9, 30)).startswith(
            "la película es del 2026-09-30 y el cambio de fuente elegido")

    def test_22d_refrescar_conserva_la_seleccion_de_un_registro_abierto(self, fabrica, dialogos, archivo_braqui):
        p = fabrica(("2026-03-01", CAMBIO))
        _guardada(p, dialogos, archivo_braqui)
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p._origen_seleccion == "registro" and p.selector_cambio.currentData() == CAMBIO
        p.refrescar()
        assert p.selector_cambio.currentData() == CAMBIO and p._origen_seleccion == "registro"

    def test_22e_con_la_bd_caida_refrescar_no_toca_la_pagina(self, pagina, monkeypatch):
        """Se lee todo antes de tocar un widget: con la BD caída, el combo no se queda vacío ni el origen inconsistente."""
        antes = _huella(pagina)
        monkeypatch.setattr(svc, "listar", lambda: (_ for _ in ()).throw(OSError("BD caida")))
        with pytest.raises(OSError):
            pagina.refrescar()
        assert _huella(pagina) == antes

    def test_22f_si_anulan_el_cambio_de_fuente_del_registro_abierto_la_etiqueta_lo_dice_una_sola_vez(
            self, fabrica, dialogos, archivo_braqui, bd):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert pagina_mod.LINEA_SIN_CAMBIO not in p.etiqueta_registro.text()
        _sql(bd, "UPDATE TipoCalibracion SET activo = 0")
        p.refrescar()
        p.refrescar()
        assert p.etiqueta_registro.text().count(pagina_mod.LINEA_SIN_CAMBIO) == 1 and p.selector_cambio.currentIndex() == 0

    def test_1b_una_nota_de_resolucion_larga_no_ensancha_la_pagina(self, fabrica, dialogos, archivo_braqui, tmp_path):
        """Medido por Opus: con la nota de EPSON009 la página exigía 1691 px de ancho (1960 con un TIFF a 300 dpi) y el
        QStackedWidget del menú toma el máximo de sus páginas: la ventana principal no podía estrecharse hasta Limpiar."""
        p = fabrica()
        p.resize(1300, 900)
        p.show()
        QApplication.processEvents()
        base = p.minimumSizeHint().width()
        a300 = _a_300_con_mtime(tmp_path)
        medidos = {}
        for nombre, ruta in (("braqui_00", archivo_braqui), ("EPSON009", _con_mtime(tmp_path, "EPSON009.jpeg", 2026, 9, 30)),
                             ("a 300 dpi", str(a300))):
            _cargar(p, dialogos, ruta)
            QApplication.processEvents()
            medidos[nombre] = p.minimumSizeHint().width()
        assert len(p.etiqueta_resolucion.text()) > 120, "la nota larga existe: la prueba no es vacía"
        assert len(medidos) == 3 and all(ancho <= base + 20 for ancho in medidos.values()), (base, medidos)
        assert p.etiqueta_resolucion.wordWrap() and p.etiqueta_fecha.wordWrap()

    def test_4g_la_tabla_de_registros_no_se_edita_y_elige_una_fila_entera(self, pagina):
        t = pagina.tabla_registros
        assert t.editTriggers() == QAbstractItemView.NoEditTriggers
        assert t.selectionBehavior() == QAbstractItemView.SelectRows and t.selectionMode() == QAbstractItemView.SingleSelection
        assert not t.isSortingEnabled() and t.minimumHeight() >= 120 and not t.verticalHeader().isVisible()

    def test_10d_la_celda_del_resultado_tiene_su_texto_completo_como_ayuda(self, pagina, dialogos, archivo_braqui):
        _guardada(pagina, dialogos, archivo_braqui)
        t = pagina.tabla_registros
        assert t.rowCount() == 1 and all(t.item(0, c).toolTip() == t.item(0, c).text() != "" for c in range(4))


# ================================================================ lo que se dibuja, dato por dato (huecos N1-N5 de Opus)

class TestLoQueSeDibujaDatoPorDato:
    def test_8f_la_pestana_de_grises_dibuja_los_datos_del_gris(self, pagina, dialogos, archivo_braqui, resultado):
        _analizada(pagina, dialogos, archivo_braqui)
        arriba, abajo = pagina._fig_gris.axes
        r, m = resultado["perfiles"]["gris"], resultado["perfiles"]["gris"]["m"]
        assert np.array_equal(np.asarray(arriba.images[0].get_array()), m["suave"]), "la ventana es la del GRIS"
        centros = [l for l in arriba.lines if l.get_label() == "centro de cada cuerda"]
        assert len(centros) == 1 and np.allclose(centros[0].get_xdata(), r["centros"]) \
            and np.allclose(centros[0].get_ydata(), r["filas"])
        bordes = [l for l in arriba.lines if l.get_label() == "bordes de la meseta"]
        assert len(bordes) == 1 and np.allclose(bordes[0].get_xdata(), m["x_izq"][r["filas"]])
        umbral = [l for l in abajo.lines if l.get_label() == "umbral de la meseta"]
        assert len(umbral) == 1 and np.allclose(umbral[0].get_ydata(), m["umbral"]), "el umbral, no el tope"
        assert abajo.get_ylabel() == "gris invertido"

    def test_8g_cada_capa_se_dibuja_con_sus_datos_sobre_la_cuerda_del_gris(self, pagina, dialogos, archivo_braqui,
                                                                          resultado):
        _analizada(pagina, dialogos, archivo_braqui)
        ejes = pagina._fig_rgb.axes
        assert len(ejes) == 3
        fila = pagina_mod.fila_representativa(resultado, "gris")
        filas_propias = {c: pagina_mod.fila_representativa(resultado, c) for c in "RGB"}
        assert any(f != fila for f in filas_propias.values()), \
            "compuerta: alguna capa tiene su propia cuerda central distinta de la del gris, o la prueba no distingue la fila"
        nombres = {"R": ("Capa roja", "rojo"), "G": ("Capa verde", "verde"), "B": ("Capa azul", "azul")}
        for eje, capa in zip(ejes, "RGB"):
            filtrado = [l for l in eje.lines if l.get_label() == "perfil con filtro de mediana"]
            crudo = [l for l in eje.lines if l.get_label() == "perfil crudo"]
            assert len(filtrado) == 1 and len(crudo) == 1, capa
            assert np.allclose(filtrado[0].get_ydata(), resultado["perfiles"][capa]["m"]["suave"][fila]), capa
            assert np.allclose(crudo[0].get_ydata(), resultado["imagenes"][capa][fila]), capa
            assert filtrado[0].get_color() == pagina_mod.COLOR_CAPA[capa]
            assert eje.get_ylabel() == f"{nombres[capa][1]} invertido" and eje.get_title().startswith(nombres[capa][0])

    def test_8h_los_titulos_dicen_las_dos_cifras_del_notebook(self, pagina, dialogos, archivo_braqui, resultado):
        _analizada(pagina, dialogos, archivo_braqui)
        m = resultado["perfiles"]["gris"]["m"]
        esperado = pagina_mod._numero(resultado["x_ref"][238] - (m["x_izq"][238] + m["x_der"][238]) / 2, 2)
        assert pagina._fig_gris.axes[1].get_title() == \
            f"Perfil de grises: en esta cuerda {esperado} px; mediana de 72 cuerdas -8.55 px"
        titulos = [eje.get_title() for eje in pagina._fig_rgb.axes]
        assert titulos[0] == "Capa roja: no medible"
        assert titulos[1].startswith("Capa verde: en esta cuerda ") and titulos[2].startswith("Capa azul: en esta cuerda ")

    def test_8i_con_la_linea_no_refinada_se_ve_la_que_el_motor_encontro_y_no_uso(self, pagina, dialogos, archivo_braqui):
        resultado = _resultado(BRAQUI_00, CLICS_LINEA_ALEJADA)
        assert resultado["linea"] is not None and resultado["mensaje_linea"] != pagina_mod.LINEA_REFINADA, \
            "compuerta: la línea existe y se descartó"
        _analizada(pagina, dialogos, archivo_braqui, CLICS_LINEA_ALEJADA)
        arriba, abajo = pagina._fig_gris.axes
        descartada = [l for l in arriba.lines if l.get_label() == "línea que se encontró (no se usa)"]
        filas = np.arange(len(resultado["x_ref"]))
        assert len(descartada) == 1
        assert np.allclose(descartada[0].get_xdata(), resultado["linea"]["pendiente"] * filas + resultado["linea"]["corte"])
        assert abajo.get_title() == "Perfil de grises: medido contra los puntos, no contra la línea"
        assert all(eje.get_title().endswith("medido contra los puntos, no contra la línea") for eje in pagina._fig_rgb.axes[1:])
        # con la línea refinada no hay línea descartada que dibujar
        pagina.boton_recalcular.click()
        _marcar(pagina)
        assert not [l for l in pagina._fig_gris.axes[0].lines if l.get_label() == "línea que se encontró (no se usa)"]

    def test_8j_la_pantalla_con_la_linea_no_refinada_no_interpreta_nada(self, pagina, dialogos, archivo_braqui):
        _analizada(pagina, dialogos, archivo_braqui, CLICS_LINEA_ALEJADA)
        resultado = _resultado(BRAQUI_00, CLICS_LINEA_ALEJADA)
        assert pagina.recuadro_gris.text() == pagina_mod.texto_recuadro(resultado)
        assert pagina.recuadro_rgb.text() == pagina_mod.texto_recuadro_capas(resultado)
        for texto in (pagina.recuadro_gris.text(), pagina.recuadro_rgb.text()):
            assert "Cumple" not in texto and "mm =" not in texto and "antes de la marca" not in texto
        assert pagina.recuadro_rgb.text().startswith("No se encontró la línea marcada"), "el recuadro RGB lleva el mismo aviso"
        assert not pagina.boton_guardar.isEnabled()

    def test_18i_cada_clave_comparada_tiene_su_rotulo_legible(self):
        rotulos = pagina_mod.ROTULOS_DE_LO_GUARDADO
        assert set(rotulos) == set(motor.valores_medidos(_resultado())) and len(rotulos) == 17
        assert len(set(rotulos.values())) == 17 and all(_texto_sin_simbolos(t) for t in rotulos.values())


# ================================================== abrir, recalcular y cargar sin dejar medias tintas (N6-N9, N17)

class TestAbrirRecalcularYCargarSinMediasTintas:
    def test_14e_anular_otro_registro_no_dice_que_el_abierto_esta_anulado(self, fabrica, dialogos, archivo_braqui, bd):
        p = fabrica(("2026-09-20", CAMBIO))
        _guardada(p, dialogos, archivo_braqui)
        p.boton_recalcular.click()
        _marcar(p)
        indice = p.selector_cambio.findData("2026-09-20")
        p.selector_cambio.setCurrentIndex(indice)
        p.selector_cambio.activated.emit(indice)
        p.boton_guardar.click()                                       # 10 días de diferencia: la pregunta contesta Sí
        assert p.tabla_registros.rowCount() == 2 and p.tabla_registros.item(0, 0).text() == CAMBIO
        p.tabla_registros.cellDoubleClicked.emit(0, 0)                # se abre el del CAMBIO
        abierto = p._registro_abierto
        p.tabla_registros.selectRow(1)                                # y se anula el OTRO
        p.boton_anular.click()
        assert [f[2] for f in _filas(bd)] == [1, 0] and p._registro_abierto == abierto
        assert p.etiqueta_registro.text().startswith(f"Registro abierto: cambio de fuente del {CAMBIO}")
        assert "anulado" not in p.etiqueta_registro.text()

    def test_16e_recalcular_olvida_el_registro_abierto(self, fabrica, dialogos, archivo_braqui):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        p.boton_limpiar.click()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        assert p._registro_abierto is not None and p.etiqueta_registro.text() != ""
        p.boton_recalcular.click()
        assert p._registro_abierto is None and p.etiqueta_registro.text() == ""

    def test_16f_cargar_otra_imagen_olvida_el_registro_abierto_y_vuelve_a_la_pestana_de_la_imagen(
            self, fabrica, dialogos, archivo_braqui, tmp_path):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        p.boton_limpiar.click()
        p.tabla_registros.cellDoubleClicked.emit(0, 0)
        p.pestanas.setCurrentIndex(2)
        assert p.estado == "registro" and p.etiqueta_registro.text() != ""
        _cargar(p, dialogos, _con_mtime(tmp_path, "braqui_00.jpeg", 2026, 9, 30, destino="otra.jpeg"))
        assert p._registro_abierto is None and p.etiqueta_registro.text() == ""
        assert p.pestanas.currentIndex() == 0 and p.estado == "imagen"

    def test_13c_el_manejador_a_la_fuerza_no_guarda_dos_veces(self, pagina, dialogos, archivo_braqui, bd):
        _guardada(pagina, dialogos, archivo_braqui)
        antes, filas = len(dialogos.llamadas), _filas(bd)
        pagina._al_guardar()                     # estado 'registro': Guardar está deshabilitado y el manejador no hace nada
        assert len(dialogos.llamadas) == antes and _filas(bd) == filas

    def test_10c_guardar_envia_los_clics_con_sus_decimales(self, pagina, dialogos, archivo_braqui, bd):
        clics = [(191.37, 377.62), (190.41, 56.23)]
        _analizada(pagina, dialogos, archivo_braqui, clics)
        assert pagina.puntos == ((191.37, 377.62), (190.41, 56.23)) and pagina.boton_guardar.isEnabled()
        pagina.boton_guardar.click()
        assert json.loads(_consulta(bd, f"SELECT puntos FROM {TABLA}")[0][0]) == [[191.37, 377.62], [190.41, 56.23]], \
            "lo que se guarda es lo que se analizó y se ve, no los clics redondeados al píxel"

    def test_18g_si_el_analisis_de_un_registro_falla_se_avisa_y_la_pagina_no_cambia(self, fabrica, dialogos, archivo_braqui,
                                                                                  bd, monkeypatch):
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        id_registro = _filas(bd)[0][0]
        p.boton_limpiar.click()
        _analizada(p, dialogos, archivo_braqui)
        antes = _huella(p)
        dialogos.llamadas.clear()
        monkeypatch.setattr(svc, "analizar_imagen", lambda *a, **k: (_ for _ in ()).throw(ValueError("no se puede")))
        assert p.abrir_registro(id_registro) is False
        assert dialogos.de("warning")[-1]["texto"] == "No se pudo analizar: no se puede. No se abrió el registro."
        assert _huella(p) == antes, "nada cambió: ni la imagen, ni los puntos, ni el resultado"

    def test_18h_si_dibujar_el_registro_falla_la_pagina_queda_fallida_y_sin_resultado(self, fabrica, dialogos,
                                                                                    archivo_braqui, bd, monkeypatch):
        dialogos.criticos_esperados = True
        p = fabrica()
        _guardada(p, dialogos, archivo_braqui)
        id_registro = _filas(bd)[0][0]
        p.boton_limpiar.click()
        monkeypatch.setattr(p, "_mostrar", lambda resultado: (_ for _ in ()).throw(RuntimeError("dibujo")))
        assert p.abrir_registro(id_registro) is False
        assert len(dialogos.de("critical")) == 1 and "RuntimeError: dibujo" in dialogos.de("critical")[0]["texto"]
        assert p.estado == "fallida" and p._resultado is None and not p.boton_guardar.isEnabled()


# ==================================================================== cada manejador está protegido (X9) y showEvent

class TestCadaManejadorEstaProtegido:
    @pytest.mark.parametrize("que,titulo", [("seleccionar", "Seleccionar imagen"), ("recalcular", "Recalcular"),
                                            ("limpiar", "Limpiar"), ("anular", "Anular"), ("abrir", "Abrir"),
                                            ("clic", "Marcar un punto"), ("guardar", "Guardar")])
    def test_25d_un_error_inesperado_se_avisa_con_su_titulo_y_no_escapa(self, pagina, dialogos, archivo_braqui, bd,
                                                                      monkeypatch, que, titulo):
        dialogos.criticos_esperados = True
        p = pagina

        def revienta(*a, **k):
            raise RuntimeError("fallo de prueba")

        if que == "seleccionar":
            monkeypatch.setattr(motor, "leer_imagen", revienta)
            _cargar(p, dialogos, archivo_braqui)
        elif que == "recalcular":
            monkeypatch.setattr(p, "_descartar_resultado", revienta)
            p.boton_recalcular.click()
        elif que == "limpiar":
            monkeypatch.setattr(p, "_restablecer_estado", revienta)
            p.boton_limpiar.click()
        elif que == "anular":
            _sembrar_prueba(bd, CAMBIO, SERIE_C)
            p.refrescar()
            p.tabla_registros.selectRow(0)
            monkeypatch.setattr(svc, "anular", revienta)
            p.boton_anular.click()
        elif que == "abrir":
            _sembrar_prueba(bd, CAMBIO, SERIE_C)
            p.refrescar()
            monkeypatch.setattr(svc, "leer", revienta)
            p.tabla_registros.cellDoubleClicked.emit(0, 0)
        elif que == "clic":
            _cargar(p, dialogos, archivo_braqui)
            monkeypatch.setattr(p, "_marcar", revienta)
            _clic(p, 191, 377)
        else:
            _analizada(p, dialogos, archivo_braqui)
            monkeypatch.setattr(svc, "existe_vigente", revienta)
            p.boton_guardar.click()
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["titulo"] == titulo and "RuntimeError: fallo de prueba" in critico[0]["texto"]

    def test_25c_una_bd_caida_al_mostrar_la_pagina_no_escapa_a_qt(self, pagina, dialogos, monkeypatch):
        """`showEvent` es un manejador de evento, no un slot, y también está protegido: una excepción que sale de él aborta
        el proceso bajo Qt."""
        dialogos.criticos_esperados = True
        monkeypatch.setattr(svc, "cambios_de_fuente", lambda: (_ for _ in ()).throw(OSError("BD caida")))
        pagina.show()
        critico = dialogos.de("critical")
        assert len(critico) == 1 and critico[0]["titulo"] == "Cambio de fuente" and "OSError: BD caida" in critico[0]["texto"]


@pytest.fixture(scope="module")
def fuente():
    return PAGINA_PY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def arbol(fuente):
    return ast.parse(fuente)


class TestLaPaginaNoHaceLoQueNoDebe:
    def test_26_ni_sql_ni_pyplot_ni_cajas_de_mensaje_instanciadas(self, arbol, fuente):
        nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | \
                  {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
        prohibidos = {"execute", "executemany", "Conexion", "sqlite3", "QSqlQuery", "QSqlDatabase", "plt", "pyplot",
                      "processEvents", "canvas_resultados", "toolbar_tac", "resultados_texto", "criterio_texto"}
        assert not (nombres & prohibidos), nombres & prohibidos
        assert "origen_referencia" not in fuente
        importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | \
                     {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
        assert not any(m and m.split(".")[0] in ("sqlite3", "matplotlib", "cv2") for m in importados), importados
        instanciadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "QMessageBox"]
        assert instanciadas == [], "las cajas de mensaje son solo las estáticas (una instancia se cuelga sin mock)"
        assert any(isinstance(n, ast.Attribute) and n.attr == "question" for n in ast.walk(arbol))

    def test_26b_no_define_lo_que_es_del_motor(self, arbol):
        definidas = {n.name for n in ast.walk(arbol) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        assert not (definidas & {"analizar", "mesetas_por_fila", "lado_del_transito", "medir_perfil", "resumen",
                                 "interpretar", "valores_medidos", "clase_resolucion", "escala_mm"})

    def test_26c_ningun_literal_ni_docstring_lleva_simbolos_de_correcto_o_incorrecto(self, arbol):
        literales = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert len(literales) > 60, "compuerta: el censo encuentra los textos de la página"
        assert [t for t in literales if not _texto_sin_simbolos(t)] == []

    def test_26d_ninguna_conexion_de_senal_cuelga_de_un_hasattr(self, arbol):
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.If) and any(isinstance(n, ast.Name) and n.id in ("hasattr", "getattr")
                                                for n in ast.walk(nodo.test)):
                assert not any(isinstance(n, ast.Attribute) and n.attr == "connect" for n in ast.walk(nodo))

    def test_26e_la_pagina_solo_importa_matplotlib_por_la_carga_diferida(self, fuente):
        assert "get_matplotlib_components()" in fuente and "from matplotlib" not in fuente and "import matplotlib" not in fuente

    def test_26f_cada_senal_tiene_exactamente_una_conexion(self, pagina):
        """Los manejadores protegidos se conectan por pasarelas: una conexión por señal (una de más guardaría dos veces; una de
        menos dejaría un botón mudo)."""
        senales = [(pagina.boton_imagen, "clicked"), (pagina.boton_recalcular, "clicked"), (pagina.boton_limpiar, "clicked"),
                   (pagina.boton_guardar, "clicked"), (pagina.boton_anular, "clicked"),
                   (pagina.selector_cambio, "activated"), (pagina.tabla_registros, "cellDoubleClicked"),
                   (pagina.pestanas, "currentChanged")]
        assert len(senales) == 8
        for objeto, nombre in senales:
            assert objeto.receivers(getattr(objeto, nombre)) == 1, (type(objeto).__name__, nombre)
        manejadores = [m() for m in pagina.lienzo_imagen.callbacks.callbacks["button_press_event"].values()]
        propios = [m for m in manejadores if getattr(m, "__self__", None) is pagina]
        assert len(propios) == 1 and propios[0].__name__ == "_al_pulsar", \
            "un solo `mpl_connect` propio (los otros son de la figura, el lienzo y la barra de herramientas)"
        assert pagina.pestanas.count() == 4 and [pagina.pestanas.tabText(i) for i in range(4)] == [
            "Imagen", "Perfil gris", "Capas RGB", "Imagen sintética"]
        assert [pagina.tabla_registros.horizontalHeaderItem(i).text() for i in range(4)] == [
            "Cambio de fuente", "Serie de la fuente", "Guardado por", "Resultado"]
