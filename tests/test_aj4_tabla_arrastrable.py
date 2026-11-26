"""AJ.4 (PLAN_AJUSTES_MENSUAL_CATPHAN_24-11.md): en el analisis del Catphan, la tabla de resultados se agranda arrastrando un divisor, y la figura que se archiva no cambia por eso.

Palabras del fisico (24-11): «Que se pueda arrastrar la tabla que aparece Abajo de cada prueba del analysis del catphan para poder por ejemplo ver la tabal de valores del numero ct completa.»

Lo que se fija:
1. Cada pestana de prueba (`_crear_nueva_tab`) tiene un divisor vertical de tres partes y dos asas: arriba el grafico con su barra, en medio los resultados y abajo el criterio en su propia area con barra; ninguna parte se colapsa y el grafico baja hasta 150 [px].
2. Al abrir, y mientras nadie mueva el divisor, la pestana reparte el alto como antes del divisor, vacia, recargada y ANALIZADA (con su panel de criterio): se compara con una replica de la pestana de antes, armada aqui, con el mismo contenido; el criterio que llega con la pestana ya vista y escondida se reparte igual al volver a verla. Donde la pestana de antes no cabia (Valores CT analizada), la pagina ya no crece: el grafico abre con 400 [px], la tabla con su alto natural y el criterio con el resto y su barra.
3. El camino del usuario: el asa se arrastra con eventos de raton (`sendEvent` con el boton izquierdo en su estado; en `offscreen`, `QTest.mousePress/mouseMove/mouseRelease` no la mueven) y la tabla muestra todas sus filas (barra vertical en 0), al recargar (la sesion del 01/10/2026 de la copia 23-11) y al analizar (fantoma sintetico), en las cinco pantallas medidas; despues, al cambiar la ventana, solo cambia el grafico.
4. Las cuatro tablas de resultados ya no tienen tope de altura.
5. Linealidad, uniformidad y resolucion espacial archivan su figura a 1343 x 827 [px]: los bytes son los mismos con el divisor arriba o abajo, con la ventana grande o chica y con la pantalla escalada, y archivar no toca la pestana.
Trampa 1: `offscreen` antes de PyQt5. Trampa 2: los dialogos estan parchados (`sin_dialogos`). Trampa 9: cada pantalla se cierra con su receta.
"""
import ast
import gc
import hashlib
import io
import os
import shutil
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image
from PyQt5.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QSize, Qt
from PyQt5.QtGui import QMouseEvent, QResizeEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSplitter, QTableWidget, QVBoxLayout, QWidget

import _bd_referencia
import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from _formularios_imagenes import FORMULARIOS, app, bd_temporal, sin_dialogos  # noqa: F401

RAIZ = Path(__file__).resolve().parent.parent
ANALISIS_PY = RAIZ / "analisisImagenes" / "Analisis_Catphan_TAC.py"
CATPHAN_DB_PY = RAIZ / "data" / "ManejoDatos" / "catphan_TAC" / "catphan_db.py"

TAMANO_POR_OMISION = (2072, 1039)        # [px] la pagina con la que el grafico vacio mide 1365 x 827, el alto de las figuras archivadas de la copia 23-11
TAMANO_CHICO = (1500, 820)               # [px]
SESION_01_10 = 48                         # la sesion del Tomografo del 01/10/2026 (copia 23-11)
TAMANO_ARCHIVADO = (1343, 827)            # [px] AJ4-D2
SIN_TOPE = 16777215                       # QWIDGETSIZE_MAX
PANTALLAS = [(2072, 1039), (1920, 1017), (1920, 1200), (2072, 1400), (1366, 728)]   # [px] las ventanas medidas (a 1366 x 728 la pagina no baja de 838 por el panel de la izquierda)
DONDE_CABE = [(2072, 1039), (1920, 1017), (2072, 1400)]                         # [px] donde la pestana analizada de antes cabia (salvo Valores CT)

PESTANAS = {"Espesor de corte": "espesor", "Tamaño de Pixel": "tamano_pixel", "Resolución de Contraste": "resolucion_contraste",
            "Resolución Espacial": "resolucion_espacial", "Valores CT": "valores_ct", "Linealidad del CT": "linealidad_ct",
            "Uniformidad y Ruido": "uniformidad"}
CON_TABLA = {"Resolución de Contraste": "resolucion_contraste", "Resolución Espacial": "resolucion_espacial", "Valores CT": "valores_ct",
             "Uniformidad y Ruido": "uniformidad"}


# ================================================================================================ ayudas

def _md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _cerrar(widget):
    """Receta de cierre de la Trampa 9."""
    widget.hide()
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def _esperar():
    for _ in range(4):
        QApplication.processEvents()


def _conectar(monkeypatch, ruta):
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    return Conexion()


def _divisor(widgets):
    divisores = widgets["tab"].findChildren(QSplitter)
    assert len(divisores) == 1, f"la pestana debe tener UN divisor y tiene {len(divisores)}"
    return divisores[0]


def _tabla(widgets):
    tablas = widgets["tab"].findChildren(QTableWidget)
    assert len(tablas) == 1, f"se esperaba una tabla en la pestana y hay {len(tablas)}"
    return tablas[0]


def _filas_enteras(tabla):
    alto = tabla.viewport().height()
    return sum(1 for f in range(tabla.rowCount())
               if tabla.rowViewportPosition(f) >= 0 and tabla.rowViewportPosition(f) + tabla.rowHeight(f) <= alto)


def _area_del_criterio(widgets):
    area = _divisor(widgets).widget(2)
    assert isinstance(area, QScrollArea) and area.widget() is widgets["criterio"], "abajo va el criterio en su propia area"
    return area


def _arrastrar(divisor, y_destino, asa_n=1):
    """El fisico toma el asa `asa_n` (1: grafico | resultados; 2: resultados | criterio) y la suelta a `y_destino` [px] del borde de arriba del divisor (eventos de raton con `sendEvent`)."""
    asa = divisor.handle(asa_n)
    centro = QPoint(asa.width() // 2, asa.height() // 2)

    def enviar(tipo, local, boton, botones):
        QApplication.sendEvent(asa, QMouseEvent(tipo, QPointF(local), QPointF(local), QPointF(asa.mapToGlobal(local)), boton, botones, Qt.NoModifier))

    enviar(QEvent.MouseButtonPress, centro, Qt.LeftButton, Qt.LeftButton)
    destino = asa.mapFrom(divisor, QPoint(centro.x(), y_destino))
    enviar(QEvent.MouseMove, destino, Qt.NoButton, Qt.LeftButton)
    enviar(QEvent.MouseButtonRelease, destino, Qt.LeftButton, Qt.NoButton)
    _esperar()


def _geometria(widget, tab):
    p = widget.mapTo(tab, QPoint(0, 0))
    return (p.x(), p.y(), widget.width(), widget.height())


def _fantoma_uniforme():
    """Agua uniforme en un disco de 75 [mm] de radio sobre aire (el mismo de las pruebas de C.1)."""
    n, tam_px = 512, 0.5
    yy, xx = np.mgrid[:n, :n]
    r_mm = np.hypot(yy - n / 2, xx - n / 2) * tam_px
    hu = np.where(r_mm <= 75.0, 0.0, -1000.0).astype(np.float32)
    grafica = (np.clip(hu + 200.0, 0, 400) / 400.0 * 255.0).astype(np.uint8)
    return hu, grafica, tam_px


def _tamano_png(blob):
    return Image.open(io.BytesIO(blob)).size


def _analizar_en_la_pantalla(pagina, monkeypatch, categoria):
    """El camino de la app: `imagen_dicom_cargada` con el fantoma sintetico (escribe el resultado y el panel de criterio); los posicionadores manuales se cierran solos."""
    import data.ManejoDatos.catphan_TAC.posicionador_manual as PM
    monkeypatch.setattr(PM.PosicionadorDialog, "exec_", lambda self: QDialog.Rejected)
    monkeypatch.setattr(PM.PosicionadorDialogCT, "exec_", lambda self: QDialog.Rejected)
    pagina.visualizador_principal = types.SimpleNamespace(vol=types.SimpleNamespace(kv=120, ma=100, espesor_corte=2.0))
    pagina.pruebas_categorias = {categoria: types.SimpleNamespace(isVisible=lambda: True)}
    pagina.imagen_dicom_cargada(*_fantoma_uniforme())
    _esperar()


def _a_la_vista(pagina, pestana):
    w = pagina._widgets_de(pestana)
    pagina.tab_widget.setCurrentWidget(w["tab"])
    _esperar()
    return w


def _guardar_a_la_vista(w):
    botones = [b for b in w["tab"].findChildren(QPushButton) if "Guardar" in b.text()]
    assert len(botones) == 1, f"un boton de guardar y hay {len(botones)}"
    abajo = botones[0].mapTo(w["tab"], QPoint(0, 0)).y() + botones[0].height()
    assert botones[0].isVisible() and abajo <= w["tab"].height(), f"el boton de guardar se sale de la pestana ({abajo} > {w['tab'].height()})"
    return botones[0]


# ================================================================================================ fijaciones

@pytest.fixture(scope="module")
def copia_23_11(app, tmp_path_factory):
    """Los TRES archivos de la copia del 23-11 a un temporal; el original no se abre y su md5 no cambia."""
    original = _bd_referencia.BD_REBUILD_23_11
    if not original.exists():
        pytest.skip(f"HI-0: falta {original.name} en {_bd_referencia.CARPETA_BD}")
    destino = tmp_path_factory.mktemp("copia_23_11_aj4")
    nombres = [original.name, original.name + "-wal", original.name + "-shm"]
    antes = {n: _md5(original.parent / n) for n in nombres if (original.parent / n).exists()}
    for n in antes:
        shutil.copy2(original.parent / n, destino / n)
    yield str(destino / original.name)
    assert antes == {n: _md5(original.parent / n) for n in antes}, "el md5 de la base de referencia cambio"


@pytest.fixture
def pagina(app, bd_temporal, monkeypatch, tmp_path):
    """La pagina del Tomografo como la arma la app al pulsar «Iniciar» (la pestana vive dentro de la pagina), a su tamano por omision."""
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    obj = FORMULARIOS["tomografo"][0]()
    obj.fisico1.addItem("Fisico Real", 1)
    obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
    obj.user_id_f1 = "Fisico Real"
    obj.user_id_f2 = None
    obj._iniciar_moviendo_tabla(obj.lista_maquina)
    assert obj.ref is not None, "no se creo el control"
    obj.criterios_por_categoria = {}
    obj.resize(*TAMANO_POR_OMISION)
    obj.show()
    _esperar()
    yield obj
    visualizador = getattr(obj, "visualizador_principal", None)
    if visualizador is not None and hasattr(visualizador, "vol"):
        visualizador.vol = None
    _cerrar(obj)
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None


@pytest.fixture
def recargada(pagina, copia_23_11, monkeypatch):
    """Una pestana recargada de la sesion del 01/10/2026, por la funcion de la recarga (la etiqueta de la pestana es su destino)."""
    def abrir(pestana):
        _conectar(monkeypatch, copia_23_11)
        widgets = pagina._crear_nueva_tab(pestana)
        _esperar()
        from data.ManejoDatos.catphan_TAC.catphan_db import reconstruir_resultados_desde_bd
        reconstruir_resultados_desde_bd(SESION_01_10, categorias=[PESTANAS[pestana]], label=widgets["label"], canvas=widgets["canvas"])
        _esperar()
        return widgets
    return abrir


def _replica_de_antes(tab, titulo, contenido):
    """La pestana de antes del divisor (la estructura que armaba `_crear_nueva_tab` en la base), al tamano de `tab`, con `contenido(etiqueta, lienzo)`."""
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    mpl = get_matplotlib_components()
    marco = QWidget()
    capa_marco = QVBoxLayout(marco)
    capa_marco.setContentsMargins(0, 0, 0, 0)
    replica = QWidget()
    capa_marco.addWidget(replica)
    capa = QVBoxLayout(replica)
    capa.addWidget(QLabel(titulo))
    capa.itemAt(0).widget().setAlignment(Qt.AlignCenter)
    lienzo = mpl["FigureCanvas"](mpl["Figure"](figsize=(8, 5)))
    lienzo.setMinimumHeight(400)
    from PyQt5.QtWidgets import QSizePolicy
    lienzo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    capa.addWidget(lienzo, stretch=2)
    barra = mpl["NavigationToolbar"](lienzo, replica)
    capa.addWidget(barra)
    contenedor = QWidget()
    ranura = QVBoxLayout(contenedor)
    ranura.setContentsMargins(0, 0, 0, 0)
    etiqueta = QLabel()
    etiqueta.setWordWrap(True)
    ranura.addWidget(etiqueta)
    capa.addWidget(contenedor, stretch=0)
    criterio = QLabel()
    criterio.setWordWrap(True)
    criterio.setTextFormat(Qt.RichText)
    capa.addWidget(criterio, stretch=0)
    marco.resize(tab.size())
    marco.show()
    _esperar()
    contenido(etiqueta, lienzo)
    for tabla in contenedor.findChildren(QTableWidget):
        tabla.setMaximumHeight(min(tabla.maximumHeight(), 300))
    _esperar()
    return marco, replica, {"canvas": lienzo, "toolbar": barra, "resultados": contenedor, "criterio": criterio}


TABLAS_DE_ANTES = {"resolucion_contraste": ("tabla_resultados_resolucion_contraste", "resultados_resolucion_contraste", 250),
                   "resolucion_espacial": ("tabla_resultados_resolucion_espacial", "resultados_resolucion_espacial", 300),
                   "uniformidad_ruido": ("tabla_resultados_uniformidad", "resultados_uniformidad", 300)}


def _replica_analizada(pagina, w, pestana, categoria):
    """La pestana de antes con el MISMO resultado (texto copiado, o la tabla rehecha con su funcion y su tope de antes), el mismo criterio y la misma fila del boton de guardar."""
    from data.ManejoDatos.catphan_TAC import catphan_db
    marco, replica, r = _replica_de_antes(w["tab"], f"Resultados de {pestana}", lambda etiqueta, lienzo: None)
    etiqueta = r["resultados"].layout().itemAt(0).widget()
    real = w["resultados"].layout().itemAt(0).widget()
    if categoria in TABLAS_DE_ANTES and pestana != "Linealidad del CT":
        funcion, atributo, tope = TABLAS_DE_ANTES[categoria]
        etiqueta.setParent(None)
        contenido = getattr(catphan_db, funcion)(getattr(pagina, atributo))
        for tabla in ([contenido] if isinstance(contenido, QTableWidget) else contenido.findChildren(QTableWidget)):
            tabla.setMaximumHeight(tope)
        r["resultados"].layout().addWidget(contenido)
    else:
        assert isinstance(real, QLabel), type(real)
        etiqueta.setText(real.text())
        etiqueta.setStyleSheet(real.styleSheet())
    r["criterio"].setText(w["criterio"].text())
    boton = _guardar_a_la_vista(w)
    copia = QPushButton(boton.text())
    copia.setStyleSheet(boton.styleSheet())
    fila = QHBoxLayout()
    fila.addWidget(copia)
    replica.layout().addLayout(fila)
    _esperar()
    return marco, replica, r


# ================================================================================================ 1. el divisor

@pytest.mark.parametrize("pestana", list(PESTANAS))
def test_la_pestana_tiene_un_divisor_vertical_entre_el_grafico_y_los_resultados(pagina, pestana):
    w = pagina._crear_nueva_tab(pestana)
    _esperar()
    divisor = _divisor(w)
    assert divisor.orientation() == Qt.Vertical and divisor.count() == 3, f"tres partes y dos asas, no {divisor.count()}"
    arriba, medio = divisor.widget(0), divisor.widget(1)
    assert arriba.isAncestorOf(w["canvas"]) and arriba.isAncestorOf(w["toolbar"]), "arriba van el grafico y su barra"
    assert medio is w["resultados"] and not medio.isAncestorOf(w["criterio"]), "en medio van los resultados, solos"
    area = _area_del_criterio(w)
    assert area.frameShape() == QFrame.NoFrame and area.widgetResizable(), "el area del criterio sin marco y a lo ancho, como el criterio de antes"
    assert area.minimumHeight() == QLabel().sizeHint().height() > 0, "el criterio baja hasta el alto de una etiqueta vacia (una linea), no hasta cero"
    assert w["criterio"].alignment() == Qt.AlignLeft | Qt.AlignTop, "si su parte crece, el texto del criterio queda arriba"
    assert not divisor.childrenCollapsible() and not any(divisor.isCollapsible(i) for i in range(3)), "ninguna parte se colapsa"
    assert w["canvas"].minimumHeight() == 150, "el grafico puede bajar hasta 150 [px]"
    capa = w["tab"].layout()
    assert w["layout"] is capa, "widgets['layout'] sigue siendo el de la pestana"
    assert [capa.itemAt(i).widget() for i in range(capa.count())] == [w["titulo"], divisor], "de arriba abajo: el titulo y el divisor"
    assert w["titulo"].text() == f"Resultados de {pestana}"


def test_los_botones_de_guardar_quedan_en_la_pestana_debajo_del_divisor(pagina):
    from PyQt5.QtWidgets import QPushButton
    w = pagina._crear_nueva_tab("Uniformidad y Ruido")
    boton = QPushButton("Guardar de prueba")
    fila = QHBoxLayout()
    fila.addWidget(boton)
    w["layout"].addLayout(fila)
    _esperar()
    divisor = _divisor(w)
    assert not divisor.isAncestorOf(boton), "los botones de guardar van fuera del divisor"
    assert boton.mapTo(w["tab"], QPoint(0, 0)).y() >= divisor.mapTo(w["tab"], QPoint(0, 0)).y() + divisor.height()


# ================================================================================================ 2. al abrir, las proporciones de antes

def test_vacia_la_pestana_se_reparte_como_antes(pagina):
    w = pagina._crear_nueva_tab("Valores CT")
    _esperar()
    marco, replica, r = _replica_de_antes(w["tab"], "Resultados de Valores CT", lambda etiqueta, lienzo: None)
    try:
        for parte in ("canvas", "toolbar", "resultados", "criterio"):
            assert _geometria(w[parte], w["tab"]) == _geometria(r[parte], replica), parte
    finally:
        _cerrar(marco)


@pytest.mark.parametrize("pestana", list(PESTANAS))
def test_recargada_la_pestana_se_reparte_como_antes(recargada, pestana):
    from data.ManejoDatos.catphan_TAC.catphan_db import reconstruir_resultados_desde_bd
    w = recargada(pestana)
    marco, replica, r = _replica_de_antes(w["tab"], f"Resultados de {pestana}", lambda etiqueta, lienzo: reconstruir_resultados_desde_bd(
        SESION_01_10, categorias=[PESTANAS[pestana]], label=etiqueta, canvas=lienzo))
    try:
        for parte in ("canvas", "toolbar", "resultados", "criterio"):
            assert _geometria(w[parte], w["tab"]) == _geometria(r[parte], replica), parte
    finally:
        _cerrar(marco)


@pytest.mark.parametrize("tamano", DONDE_CABE, ids=lambda t: f"{t[0]}x{t[1]}")
@pytest.mark.parametrize("categoria,pestana", [("tamaño_pixel", "Tamaño de Pixel"), ("resolucion_contraste", "Resolución de Contraste"),
                                              ("resolucion_espacial", "Resolución Espacial"), ("uniformidad_ruido", "Uniformidad y Ruido"),
                                              ("valores_numero_ct", "Linealidad del CT")])
def test_analizada_la_pestana_se_reparte_como_antes(pagina, monkeypatch, categoria, pestana, tamano):
    """Con su resultado y su panel de criterio, sin tocar ningun asa: la geometria es la de la pestana de antes con el mismo contenido."""
    pagina.resize(*tamano)
    _esperar()
    _analizar_en_la_pantalla(pagina, monkeypatch, categoria)
    w = _a_la_vista(pagina, pestana)
    assert w["criterio"].text(), "el analisis escribe el panel de criterio"
    marco, replica, r = _replica_analizada(pagina, w, pestana, categoria)
    try:
        for parte in ("canvas", "toolbar", "resultados", "criterio"):
            assert _geometria(w[parte], w["tab"]) == _geometria(r[parte], replica), parte
    finally:
        _cerrar(marco)


def test_el_criterio_que_llega_despues_se_reparte_como_antes(pagina):
    """El panel de criterio se escribe con la pestana a la vista y sin otro cambio: la pestana se vuelve a repartir como la de antes con ese criterio."""
    w = pagina._crear_nueva_tab("Uniformidad y Ruido")
    _esperar()
    texto = "<b>Criterio y veredicto del equipo</b><br>" + "Criterio: linea de prueba con el largo de las de verdad, para que el panel ocupe varias lineas. " * 12
    w["criterio"].setText(texto)
    _esperar()
    marco, replica, r = _replica_de_antes(w["tab"], "Resultados de Uniformidad y Ruido", lambda etiqueta, lienzo: r_criterio(lienzo).setText(texto))
    try:
        for parte in ("canvas", "toolbar", "resultados", "criterio"):
            assert _geometria(w[parte], w["tab"]) == _geometria(r[parte], replica), parte
    finally:
        _cerrar(marco)


def test_un_resultado_de_texto_largo_se_reparte_como_antes(pagina):
    """Un resultado de texto de varias lineas (como el de espesor): su alto es el de su ancho real, como en la pestana de antes, no el que pide para un ancho angosto."""
    w = pagina._crear_nueva_tab("Espesor de corte")
    _esperar()
    texto = "Resultado de prueba con el largo de los de verdad, para que ocupe varias lineas a lo ancho de la pestana. " * 14
    real = pagina._escribir_resultado("Espesor de corte", texto)
    _esperar()

    def contenido(etiqueta, lienzo):
        etiqueta.setText(real.text())
        etiqueta.setStyleSheet(real.styleSheet())
    marco, replica, r = _replica_de_antes(w["tab"], "Resultados de Espesor de corte", contenido)
    try:
        for parte in ("canvas", "toolbar", "resultados", "criterio"):
            assert _geometria(w[parte], w["tab"]) == _geometria(r[parte], replica), parte
    finally:
        _cerrar(marco)


def r_criterio(lienzo):
    """El criterio de la replica (la etiqueta que sigue al contenedor en su layout)."""
    capa = lienzo.parentWidget().layout()
    return capa.itemAt(capa.count() - 1).widget()


def test_valores_ct_analizado_cabe_en_la_ventana(pagina, monkeypatch):
    """Donde la pestana de antes no cabia (la pagina crecia sola): el grafico abre con sus 400 [px], la tabla con su alto natural, el criterio con el resto y su barra, y el boton se ve."""
    _analizar_en_la_pantalla(pagina, monkeypatch, "valores_numero_ct")
    w = _a_la_vista(pagina, "Valores CT")
    tabla, area = _tabla(w), _area_del_criterio(w)
    assert pagina.size().height() == TAMANO_POR_OMISION[1], f"la pagina crecio a {pagina.size().height()} [px]"
    assert w["canvas"].height() == 400, w["canvas"].height()
    assert w["resultados"].height() == w["resultados"].sizeHint().height() == tabla.height(), "la tabla con su alto natural, antes que el criterio"
    assert area.verticalScrollBar().maximum() > 0 and w["criterio"].height() == w["criterio"].heightForWidth(w["criterio"].width()), "el criterio entero, con su barra"
    _guardar_a_la_vista(w)


class _Alto(QWidget):
    """Un resultado que pide mas alto que la pestana entera."""

    def sizeHint(self):
        return QSize(200, 2000)

    def minimumSizeHint(self):
        return QSize(50, 40)


def test_con_un_resultado_mas_alto_que_la_pestana_el_grafico_abre_con_sus_400_px(pagina):
    w = pagina._crear_nueva_tab("Valores CT")
    _esperar()
    pagina._escribir_resultado("Valores CT", _Alto())
    _esperar()
    assert w["canvas"].height() >= 400 and w["resultados"].height() > 100, (w["canvas"].height(), w["resultados"].height())
    pagina.resize(*TAMANO_CHICO)
    _esperar()
    assert w["canvas"].height() >= 400 and w["resultados"].height() > 100, "con la ventana chica, tambien"


def test_el_criterio_que_llega_con_la_pestana_escondida_se_reparte_al_volver(pagina):
    """El criterio solo, escrito en una pestana ya vista y ahora escondida, no le llega al divisor como pedido de layout ni como cambio de tamano: se reparte al volver a verla."""
    w = pagina._crear_nueva_tab("Uniformidad y Ruido")
    _esperar()
    pagina._crear_nueva_tab("Espesor de corte")
    _esperar()
    assert not w["tab"].isVisible(), "la pestana ya se vio y ahora hay otra a la vista"
    texto = "<b>Criterio y veredicto del equipo</b><br>" + "Criterio: linea de prueba con el largo de las de verdad, para que el panel ocupe varias lineas. " * 12
    w["criterio"].setText(texto)
    _esperar()
    w = _a_la_vista(pagina, "Uniformidad y Ruido")
    marco, replica, r = _replica_de_antes(w["tab"], "Resultados de Uniformidad y Ruido", lambda etiqueta, lienzo: r_criterio(lienzo).setText(texto))
    try:
        for parte in ("canvas", "toolbar", "resultados", "criterio"):
            assert _geometria(w[parte], w["tab"]) == _geometria(r[parte], replica), parte
    finally:
        _cerrar(marco)


# ================================================================================================ 3. el camino del usuario

@pytest.mark.parametrize("tamano", PANTALLAS, ids=lambda t: f"{t[0]}x{t[1]}")
def test_valores_ct_recargado_se_ve_completo_al_arrastrar_el_divisor(recargada, pagina, tamano):
    pagina.resize(*tamano)
    _esperar()
    w = recargada("Valores CT")
    tabla = _tabla(w)
    assert tabla.rowCount() == 7
    assert tabla.verticalScrollBar().maximum() > 0 and _filas_enteras(tabla) < tabla.rowCount(), "antes de arrastrar no se ve completa"
    divisor = _divisor(w)
    _arrastrar(divisor, -3000)
    assert tabla.verticalScrollBar().maximum() == 0, "con espacio, la tabla no necesita su barra"
    assert _filas_enteras(tabla) == tabla.rowCount(), "se ven las siete filas"
    assert w["canvas"].height() >= 150 and min(divisor.sizes()) > 0


@pytest.mark.parametrize("tamano", PANTALLAS, ids=lambda t: f"{t[0]}x{t[1]}")
def test_valores_ct_analizado_se_ve_completo_al_arrastrar_el_divisor(pagina, monkeypatch, tamano):
    """El caso que nombro el fisico, recien analizado (con su panel de criterio de 7 materiales): una sola asa, la de arriba, deja ver las 7 filas; el criterio sigue con su barra y el boton a la vista."""
    pagina.resize(*tamano)
    _esperar()
    _analizar_en_la_pantalla(pagina, monkeypatch, "valores_numero_ct")
    w = _a_la_vista(pagina, "Valores CT")
    tabla, area, divisor = _tabla(w), _area_del_criterio(w), _divisor(w)
    assert tabla.rowCount() == 7 and _filas_enteras(tabla) < 7, "antes de arrastrar no se ve completa"
    _arrastrar(divisor, -3000)
    assert tabla.verticalScrollBar().maximum() == 0 and _filas_enteras(tabla) == 7, \
        f"con el asa de arriba al tope se ven {_filas_enteras(tabla)} de 7 filas (tabla {tabla.height()} [px], criterio {area.height()} [px])"
    assert w["canvas"].height() == 150 and area.height() >= area.minimumHeight()
    _guardar_a_la_vista(w)
    _arrastrar(divisor, divisor.height() + 3000, asa_n=2)
    assert _filas_enteras(tabla) == 7 and area.height() == area.minimumHeight(), "el asa de abajo le da al criterio lo que el fisico quiera, sin quitarselo a la tabla entera"


def test_uniformidad_analizada_se_ve_completa_al_arrastrar_el_divisor(pagina):
    pagina.visualizador_principal = types.SimpleNamespace(vol=types.SimpleNamespace(kv=120, ma=100, espesor_corte=2.0))
    pagina.pruebas_categorias = {"uniformidad_ruido": types.SimpleNamespace(isVisible=lambda: True)}
    pagina.imagen_dicom_cargada(*_fantoma_uniforme())
    _esperar()
    w = pagina._widgets_de("Uniformidad y Ruido")
    tabla = _tabla(w)
    assert tabla.verticalScrollBar().maximum() > 0, "antes de arrastrar no se ve completa"
    _arrastrar(_divisor(w), 200)
    assert tabla.verticalScrollBar().maximum() == 0 and _filas_enteras(tabla) == tabla.rowCount()


def test_el_grafico_baja_hasta_150_px_y_no_desaparece(recargada):
    w = recargada("Valores CT")
    divisor = _divisor(w)
    _arrastrar(divisor, -2000)
    assert w["canvas"].height() == 150, f"el grafico debe quedar en su minimo de 150 [px], no en {w['canvas'].height()}"
    assert divisor.sizes()[0] > 0 and w["canvas"].isVisible()


def test_los_resultados_no_desaparecen_al_bajar_el_divisor(recargada):
    w = recargada("Valores CT")
    divisor = _divisor(w)
    _arrastrar(divisor, divisor.height() + 2000)
    medio, area = divisor.widget(1), _area_del_criterio(w)
    assert divisor.sizes()[1] > 0 and medio.height() >= medio.minimumSizeHint().height() > 0
    assert _tabla(w).height() > 0 and _tabla(w).isVisible()
    assert area.height() >= area.minimumHeight() > 0 and area.isVisible(), "el criterio tampoco desaparece"


def test_lo_que_dejo_el_fisico_se_conserva_al_escribir_otro_resultado(recargada, pagina):
    w = recargada("Valores CT")
    divisor = _divisor(w)
    _arrastrar(divisor, 200)
    elegidos = divisor.sizes()
    pagina._escribir_resultado("Valores CT", "Otro resultado")
    _esperar()
    assert divisor.sizes() == elegidos, "despues de arrastrar manda el fisico"


def test_despues_de_arrastrar_al_cambiar_la_ventana_solo_cambia_el_grafico(pagina, monkeypatch):
    """Lo que el fisico le dio a la tabla y al criterio no se les quita: al achicar o agrandar la ventana, la diferencia la toma el grafico."""
    pagina.resize(2072, 1400)
    _esperar()
    _analizar_en_la_pantalla(pagina, monkeypatch, "valores_numero_ct")
    w = _a_la_vista(pagina, "Valores CT")
    tabla, divisor = _tabla(w), _divisor(w)
    asa = divisor.handle(1)
    _arrastrar(divisor, asa.y() + asa.height() // 2 - 220)
    elegidos = divisor.sizes()
    assert tabla.rowCount() == 7 and _filas_enteras(tabla) == 7, f"con el asa arriba se ven las siete filas: {elegidos}"
    for alto in (1200, 1500):
        pagina.resize(2072, alto)
        _esperar()
        ahora = divisor.sizes()
        assert ahora[1:] == elegidos[1:] and ahora[0] == elegidos[0] + alto - 1400, f"a {alto} [px] de alto: {elegidos} -> {ahora}"
        assert tabla.verticalScrollBar().maximum() == 0 and _filas_enteras(tabla) == 7


def test_la_recarga_por_el_temporizador_pone_la_tabla_abajo(pagina, copia_23_11, monkeypatch):
    _conectar(monkeypatch, copia_23_11)
    monkeypatch.setattr(pagina, "ref", SESION_01_10)
    w = pagina._crear_nueva_tab("Valores CT")
    pagina.gestor_reconstruccion.reconstruir_categoria_async("Valores CT", w)
    for _ in range(60):
        QTest.qWait(50)
        if w["tab"].findChildren(QTableWidget):
            break
    _esperar()
    tabla = _tabla(w)
    divisor = _divisor(w)
    assert divisor.widget(1).isAncestorOf(tabla), "la recarga pone la tabla en la parte de los resultados"
    _arrastrar(divisor, 200)
    assert tabla.verticalScrollBar().maximum() == 0 and _filas_enteras(tabla) == tabla.rowCount()


# ================================================================================================ 4. sin topes

@pytest.mark.parametrize("pestana", list(CON_TABLA))
def test_la_tabla_de_resultados_no_tiene_tope_de_altura(recargada, pestana):
    tabla = _tabla(recargada(pestana))
    assert tabla.maximumHeight() == SIN_TOPE, f"tope de {tabla.maximumHeight()} [px]"


def test_solo_quedan_los_topes_de_los_avisos_sin_roi_visible():
    arbol = ast.parse(CATPHAN_DB_PY.read_text(encoding="utf-8"))
    topes = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "setMaximumHeight"]
    assert [ast.unparse(t.func.value) for t in topes] == ["no_visible_widget", "no_visible_widget"]


# ================================================================================================ 5. la figura archivada

def _analizar(prueba, canvas):
    from analisisImagenes import Analisis_Catphan_TAC as A
    hu, grafica, tam_px = _fantoma_uniforme()
    if prueba == "uniformidad":
        from analisisImagenes.catphan import criterios
        return A.uniformidad(grafica, hu, tam_px, visualizar=True, canvas=canvas, **criterios.parametros_de_analisis("uniformidad", "Tomógrafo"))["imagen_analisis"]
    if prueba == "linealidad":
        return A.linealidad_ct([0.0, 0.1, 0.19, 0.21, 0.24, 0.35, 0.47], [-1000.0, -95.0, -20.0, 4.0, 110.0, 340.0, 1010.0], visualizar=True, canvas=canvas)["imagen_analisis"]
    return A.resolucion_espacial(grafica, hu, tam_px, visualizar=True, canvas=canvas)["imagen_analisis"]


@pytest.mark.parametrize("prueba,pestana", [("uniformidad", "Uniformidad y Ruido"), ("linealidad", "Linealidad del CT"), ("resolucion_espacial", "Resolución Espacial")])
def test_la_figura_archivada_no_depende_del_divisor_ni_de_la_ventana(pagina, prueba, pestana):
    w = pagina._crear_nueva_tab(pestana)
    _esperar()
    alto_inicial = w["canvas"].size()
    grande = _analizar(prueba, w["canvas"])
    pagina.resize(*TAMANO_CHICO)
    _esperar()
    assert w["canvas"].size() != alto_inicial, "la ventana chica achica el grafico"
    chica = _analizar(prueba, w["canvas"])
    assert isinstance(grande, bytes) and grande and chica == grande, "la imagen archivada cambio con el tamano de la ventana"
    pagina.resize(*TAMANO_POR_OMISION)
    _esperar()
    _arrastrar(_divisor(w), 120)
    assert w["canvas"].height() < alto_inicial.height() - 300, "el grafico quedo bastante mas chico"
    assert _analizar(prueba, w["canvas"]) == grande, "la imagen archivada cambio con el divisor"
    assert _tamano_png(grande) == TAMANO_ARCHIVADO


def test_archivar_no_toca_la_pestana(pagina):
    from analisisImagenes import Analisis_Catphan_TAC as A
    w = pagina._crear_nueva_tab("Resolución Espacial")
    _esperar()
    _analizar("resolucion_espacial", w["canvas"])
    lienzo, figura = w["canvas"], w["canvas"].figure
    antes = (bytes(lienzo.buffer_rgba()), tuple(figura.get_size_inches()), lienzo.size(), [tuple(ax.get_position().bounds) for ax in figura.axes], figura.dpi)
    blob = A._png_de_tamano_fijo(figura, ajustar=True)
    _esperar()
    despues = (bytes(lienzo.buffer_rgba()), tuple(figura.get_size_inches()), lienzo.size(), [tuple(ax.get_position().bounds) for ax in figura.axes], figura.dpi)
    assert _tamano_png(blob) == TAMANO_ARCHIVADO
    assert antes == despues, "archivar no redibuja ni cambia el tamano de la pestana"
    assert figura.canvas is lienzo
    tamano_px = tuple(int(round(x)) for x in figura.get_size_inches() * figura.dpi)
    assert tamano_px == (lienzo.width(), lienzo.height()), f"la figura de la pestana quedo de {tamano_px} [px] en un lienzo de {lienzo.width()} x {lienzo.height()}"


def test_la_resolucion_espacial_archivada_ajusta_sus_margenes(pagina):
    from analisisImagenes import Analisis_Catphan_TAC as A
    w = pagina._crear_nueva_tab("Resolución Espacial")
    _esperar()
    blob = _analizar("resolucion_espacial", w["canvas"])
    from analisisImagenes.catphan.figura_archivada import MARCA_DE_LA_CURVA_SOLA
    curva = A.figura_de_la_curva_mtf({}, {})  # AJ.6b (25-11): se archiva solo la curva (con el fantoma uniforme, el aviso), no la figura de la pestana
    assert blob == A._png_de_tamano_fijo(curva, ajustar=True, metadatos=MARCA_DE_LA_CURVA_SOLA), "la resolucion espacial ajusta sus margenes al tamano fijo"
    assert blob != A._png_de_tamano_fijo(curva, metadatos=MARCA_DE_LA_CURVA_SOLA)


def test_las_tres_llamadas_que_archivan_usan_el_tamano_fijo():
    fuente = ANALISIS_PY.read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    usos = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_png_de_tamano_fijo"]
    assert len(usos) == 3
    assert "canvas.figure.savefig(" not in fuente, "ninguna figura de la pestana se archiva al tamano de la ventana"


@pytest.mark.parametrize("prueba,pestana,escala", [("uniformidad", "Uniformidad y Ruido", 1.25), ("linealidad", "Linealidad del CT", 1.5),
                                                   ("resolucion_espacial", "Resolución Espacial", 2.0)])
def test_la_figura_archivada_no_depende_de_la_escala_de_la_pantalla(pagina, prueba, pestana, escala):
    """En una pantalla escalada Qt sube el dpi de la figura de la pestana: se archivan los mismos bytes, a 1343 x 827 [px], y la pestana sigue escalada."""
    w = pagina._crear_nueva_tab(pestana)
    _esperar()
    sin_escala = _analizar(prueba, w["canvas"])
    lienzo = w["canvas"]
    lienzo._set_device_pixel_ratio(escala)                             # lo mismo que hace `FigureCanvasQT._update_pixel_ratio`
    lienzo.resizeEvent(QResizeEvent(lienzo.size(), lienzo.size()))
    _esperar()
    assert lienzo.figure.dpi == 100 * escala, "la figura de la pestana esta escalada"
    escalada = _analizar(prueba, lienzo)
    assert _tamano_png(escalada) == TAMANO_ARCHIVADO
    assert escalada == sin_escala, "la imagen archivada cambio con la escala de la pantalla"
    assert lienzo.figure.dpi == lienzo.figure.dpi_scale_trans.get_matrix()[0, 0] == 100 * escala, "archivar no toca la escala de la pestana"
