"""AJ.6b: la resolucion espacial se archiva en par. Un analisis nuevo guarda como imagen del analisis SOLO la curva MTF (el corte ya es la imagen original),
la recarga dibuja el corte y la curva lado a lado, y el PDF imprime de un analisis ya guardado solo el panel de su curva, recortado en memoria por su contenido
(o la figura entera si duda). Lo guardado no se toca; lo que se ve en vivo y las figuras archivadas de las otras pruebas no cambian.
Datos reales: una COPIA de los tres archivos de la copia 23-11 (Tomografo 01/10/2026, sesion 48; y las 9 figuras combinadas guardadas)."""
import ast
import gc
import hashlib
import importlib
import io
import os
import pickle
import shutil
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PyQt5.QtCore import QBuffer, QByteArray, QCoreApplication, QEvent, QIODevice  # noqa: E402
from PyQt5.QtWidgets import QApplication, QLabel, QMessageBox, QWidget  # noqa: E402

import data.ManejoDatos.conection as conection_mod  # noqa: E402
from _bd_referencia import BD_REBUILD_23_11  # noqa: E402
from _informe_imagenes import FalsoVisor, Padre  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
TAMANO_ARCHIVADO = (1343, 827)  # [px] el de AJ.4
SESION_01_10 = 48  # Tomografo del 01/10/2026
SESION_NUEVA = 34  # Halcyon 06/2026: en la copia de la prueba, con la curva sola (un analisis nuevo)
SESION_SIN_CORTE = 30  # Clinac iX 05/2026: en la copia de la prueba, la curva sola y sin corte guardado
SESION_CORTE_ILEGIBLE = 25  # en la copia de la prueba, la curva sola y un corte guardado que no es una imagen
FILTRO = "(activo IS NULL OR activo = 1)"
OTRAS = ["espesor", "tamano_pixel", "resolucion_contraste", "valores_ct", "linealidad_ct", "uniformidad"]
ID_TIPO = {"espesor": 1, "tamano_pixel": 2, "resolucion_contraste": 3, "resolucion_espacial": 4, "valores_ct": 5, "linealidad_ct": 6, "uniformidad": 7}
MARCO = (40.0, 245.0, 572.0, 692.0)  # margenes de la pagina carta [pt]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _modulo(nombre):
    try:
        return importlib.import_module(nombre)
    except ImportError as e:
        pytest.fail(f"no existe {nombre}: {e}")


def _A():
    return _modulo("analisisImagenes.Analisis_Catphan_TAC")


def _marca():
    return _modulo("analisisImagenes.catphan.figura_archivada").MARCA_DE_LA_CURVA_SOLA


def _m():
    return _modulo("models.PDF.Imagenes.maqueta_catphan")


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


def _lienzo(ancho=900, alto=500):
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    mpl = get_matplotlib_components()
    lienzo = mpl["FigureCanvas"](mpl["Figure"](figsize=(8, 5)))
    lienzo.resize(ancho, alto)
    lienzo.show()
    _esperar()
    return lienzo


@pytest.fixture
def lienzo(app):
    c = _lienzo()
    yield c
    _cerrar(c)


def fantoma_con_barras(n=512, tam_px=0.5, amplitudes=(190, 170, 140, 110, 80, 50, 30, 12)):
    """Agua en un disco de 100 [mm] con las 8 regiones de barras del anillo de 48 [mm], de modulacion decreciente: da una curva con sus marcas del 10 al 50 %."""
    yy, xx = np.mgrid[:n, :n].astype(float)
    r_mm = np.hypot(yy - n / 2, xx - n / 2) * tam_px
    hu = np.where(r_mm <= 100.0, 0.0, -1000.0)
    ang = np.mod(np.arctan2(yy - n / 2, xx - n / 2), 2 * np.pi) / (2 * np.pi)
    bordes = (0.470, 0.382, 0.320, 0.260, 0.220, 0.160, 0.120, 0.060, 0.020)
    picos = (2, 3, 4, 4, 4, 5, 5, 5)
    anillo = np.abs(r_mm - 48.0) <= 4.0
    for k in range(8):
        a0, a1 = bordes[k + 1], bordes[k]
        dentro = anillo & (ang >= a0) & (ang < a1)
        hu = np.where(dentro, 200.0 - amplitudes[k] * np.cos(2 * np.pi * (ang - a0) / (a1 - a0) * picos[k]), hu)
    hu = hu.astype(np.float32)
    return hu, (np.clip(hu + 200.0, 0, 600) / 600.0 * 255.0).astype(np.uint8), tam_px


def fantoma_uniforme():
    """Agua uniforme en un disco de 75 [mm]: ninguna region medible, sin curva."""
    n, tam_px = 512, 0.5
    yy, xx = np.mgrid[:n, :n]
    hu = np.where(np.hypot(yy - n / 2, xx - n / 2) * tam_px <= 75.0, 0.0, -1000.0).astype(np.float32)
    return hu, (np.clip(hu + 200.0, 0, 400) / 400.0 * 255.0).astype(np.uint8), tam_px


def _analizar(fantoma, canvas):
    hu, grafica, tam_px = fantoma()
    return _A().resolucion_espacial(grafica, hu, tam_px, visualizar=True, canvas=canvas)


def _rgba(blob_o_ruta):
    fuente = io.BytesIO(blob_o_ruta) if isinstance(blob_o_ruta, (bytes, bytearray)) else blob_o_ruta
    with Image.open(fuente) as im:
        return np.asarray(im.convert("RGBA"))


def trae_un_corte(pixeles):
    """La verdad de la prueba, independiente del detector: un corte es un bloque de al menos 20 columnas seguidas con mas del 30 % de sus filas oscuras (gris < 100)."""
    gris = pixeles[..., :3].mean(axis=-1)
    oscuras = (gris < 100).mean(axis=0) > 0.30
    seguidas = 0
    for o in oscuras:
        seguidas = seguidas + 1 if o else 0
        if seguidas >= 20:
            return True
    return False


def ventana_llena(pixeles, lado=40):
    """Si hay un cuadro de lado x lado [px] sin un solo pixel blanco (una imagen, no un grafico de lineas)."""
    llenos = ~np.all(pixeles[..., :3] == 255, axis=-1)
    suma = np.pad(llenos.astype(int).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    cuadros = suma[lado:, lado:] - suma[:-lado, lado:] - suma[lado:, :-lado] + suma[:-lado, :-lado]
    return bool((cuadros == lado * lado).any())


def azules(pixeles):
    """Pixeles del color de la curva de matplotlib (C0, #1f77b4)."""
    r, g, b = (pixeles[..., i].astype(int) for i in range(3))
    return int(((abs(r - 31) < 40) & (abs(g - 119) < 40) & (abs(b - 180) < 40)).sum())


def magentas(pixeles):
    """Pixeles magenta: el color de lo que habia en el lienzo antes de recargar (ni el corte ni la curva lo usan)."""
    r, g, b = (pixeles[..., i].astype(int) for i in range(3))
    return int(((r > 200) & (g < 50) & (b > 200)).sum())


def _pantalla(lienzo):
    """Lo que Qt pinta en el lienzo, como RGBA."""
    datos = QByteArray()
    memoria = QBuffer(datos)
    memoria.open(QIODevice.WriteOnly)
    lienzo.grab().save(memoria, "PNG")
    memoria.close()
    pix = _rgba(bytes(datos))
    assert pix.shape[1::-1] == tuple(lienzo.figure.bbox.size), "un pixel de la pantalla es un pixel de la figura"
    return pix


def _trozo(pantalla, eje, borde=3):
    """Lo que la pantalla muestra dentro de un eje, sin su borde."""
    x0, y0, x1, y1 = eje.get_window_extent().extents
    alto = pantalla.shape[0]
    return pantalla[int(alto - y1) + borde:int(alto - y0) - borde, int(x0) + borde:int(x1) - borde, :3].astype(int)


def _con_algo_antes(lienzo):
    """Deja el lienzo como puede estar antes de recargar: dos ejes con un cuadro magenta, ya pintados en la pantalla."""
    for n in (1, 2):
        lienzo.figure.add_subplot(1, 2, n).imshow(np.full((8, 8, 3), (255, 0, 255), np.uint8))
    lienzo.draw()
    _esperar()
    assert magentas(_pantalla(lienzo)) > 10000, "la pantalla muestra lo de antes"


# 1. LO QUE SE ARCHIVA

def test_un_analisis_nuevo_archiva_solo_la_curva_a_tamano_fijo_y_con_su_marca(lienzo):
    from analisisImagenes.catphan.figura_archivada import es_la_curva_sola
    r = _analizar(fantoma_con_barras, lienzo)
    blob = r["imagen_analisis"]
    assert r["mtf_values"] and r["mtf_lp_cm"], "el fantoma con barras tiene curva y marcas"
    assert Image.open(io.BytesIO(blob)).size == TAMANO_ARCHIVADO
    assert es_la_curva_sola(blob), "la figura archivada lleva la marca de la curva sola"
    pix = _rgba(blob)
    assert not trae_un_corte(pix) and not ventana_llena(pix), "la figura archivada no trae el corte"
    assert azules(pix) > 500, "la figura archivada trae la curva"


def test_lo_archivado_es_el_panel_de_la_curva_de_la_pestana_solo(lienzo):
    """La verdad: la figura de la pestana sin el corte, con el panel de la curva en toda la figura, archivada igual."""
    from matplotlib.gridspec import GridSpec
    A = _A()
    blob = _analizar(fantoma_con_barras, lienzo)["imagen_analisis"]
    copia = pickle.loads(pickle.dumps(lienzo.figure))
    for ax in [a for a in copia.axes if a.images]:
        copia.delaxes(ax)
    (curva,) = copia.axes
    curva.set_subplotspec(GridSpec(1, 1, figure=copia)[0])
    assert blob == A._png_de_tamano_fijo(copia, ajustar=True, metadatos=_marca())


def test_la_curva_archivada_dibuja_lo_mismo_que_la_pestana(lienzo):
    A = _A()
    r = _analizar(fantoma_con_barras, lienzo)
    vivo = [a for a in lienzo.figure.axes if not a.images]
    (archivado,) = A.figura_de_la_curva_mtf(r["mtf_values"], r["mtf_lp_cm"]).axes
    assert len(vivo) == 1

    def contenido(ax):
        return ([(tuple(map(tuple, l.get_xydata())), l.get_marker(), l.get_color()) for l in ax.lines], [(t.get_text(), t.get_position()) for t in ax.texts],
                ax.get_title(), ax.get_xlabel(), ax.get_ylabel(), ax.get_ylim())
    assert contenido(archivado) == contenido(vivo[0])
    assert len(archivado.texts) == 5, "las marcas del 10, 20, 30, 40 y 50 %"


@pytest.mark.parametrize("fantoma,ejes", [(fantoma_con_barras, 2), (fantoma_uniforme, 1)], ids=["con_curva", "sin_curva"])
def test_en_vivo_la_pestana_se_ve_como_hoy_con_el_corte_y_el_anillo(lienzo, fantoma, ejes):
    _analizar(fantoma, lienzo)
    figura = lienzo.figure
    assert len(figura.axes) == ejes
    assert figura.axes[0].images and figura.axes[0].get_title() == "Anillo resolución" and figura.axes[0].collections, "el corte con el anillo rojo"
    if ejes == 2:
        assert figura.axes[1].get_title() == "MTF normalizada"


def test_sin_dos_regiones_medibles_se_archiva_la_figura_que_lo_dice(lienzo):
    from analisisImagenes.catphan.figura_archivada import es_la_curva_sola
    A = _A()
    r = _analizar(fantoma_uniforme, lienzo)
    blob = r["imagen_analisis"]
    assert not r["mtf_values"]
    assert es_la_curva_sola(blob) and Image.open(io.BytesIO(blob)).size == TAMANO_ARCHIVADO
    assert blob == A._png_de_tamano_fijo(A.figura_de_la_curva_mtf({}, {}), ajustar=True, metadatos=_marca())
    (ax,) = A.figura_de_la_curva_mtf({}, {}).axes
    assert [t.get_text() for t in ax.texts] == [A.SIN_CURVA_MTF] and "menos de dos regiones medibles" in A.SIN_CURVA_MTF
    pix = _rgba(blob)
    assert not trae_un_corte(pix) and not ventana_llena(pix)
    _, (w, h) = _m().imagen_preparada(io.BytesIO(blob))
    assert 1.2 < w / h < 2.0, f"el aviso conserva su recuadro en el PDF y no queda en una tira: {w}x{h}"


def test_sin_lienzo_tambien_se_archiva_solo_la_curva(monkeypatch):
    import matplotlib.pyplot as plt
    from analisisImagenes.catphan.figura_archivada import es_la_curva_sola
    monkeypatch.setattr(plt, "show", lambda *a, **k: None)
    hu, grafica, tam_px = fantoma_con_barras()
    blob = _A().resolucion_espacial(grafica, hu, tam_px, visualizar=True, canvas=None)["imagen_analisis"]
    plt.close("all")
    assert es_la_curva_sola(blob) and not trae_un_corte(_rgba(blob))


def _como_antes_en_un_lienzo_nuevo(analizar):
    """Un lienzo NUEVO del tamano archivado con el mismo analisis y su figura guardada como se archivaba antes de AJ.4 (`figure.savefig`)."""
    lienzo = _lienzo()
    lienzo.setFixedSize(*TAMANO_ARCHIVADO)
    _esperar()
    try:
        analizar(lienzo)
        buf = io.BytesIO()
        lienzo.figure.savefig(buf, format="png")
        return buf.getvalue()
    finally:
        _cerrar(lienzo)


def _uniformidad(canvas):
    from analisisImagenes.catphan import criterios
    hu, grafica, tam_px = fantoma_uniforme()
    return _A().uniformidad(grafica, hu, tam_px, visualizar=True, canvas=canvas, **criterios.parametros_de_analisis("uniformidad", "Tomógrafo"))["imagen_analisis"]


def _linealidad(canvas):
    return _A().linealidad_ct([0.0, 0.1, 0.19, 0.21, 0.24, 0.35, 0.47], [-1000.0, -95.0, -20.0, 4.0, 110.0, 340.0, 1010.0], visualizar=True, canvas=canvas)["imagen_analisis"]


@pytest.mark.parametrize("analizar", [_uniformidad, _linealidad], ids=["uniformidad", "linealidad"])
def test_las_figuras_archivadas_de_las_otras_pruebas_son_las_de_antes_en_un_lienzo_de_1343_x_827(app, lienzo, analizar):
    """El hueco de AJ.4 (sus sondas S07 y S08): la linealidad y la uniformidad se archivan como antes, byte a byte, sin los margenes ajustados de la resolucion espacial."""
    assert analizar(lienzo) == _como_antes_en_un_lienzo_nuevo(analizar)


@pytest.mark.parametrize("analizar", [_uniformidad, _linealidad], ids=["uniformidad", "linealidad"])
def test_las_otras_figuras_archivadas_no_dependen_de_los_margenes_cambiados_en_la_pestana(app, analizar):
    """La barra de la pestana deja cambiar los margenes («Subplots»): lo archivado sigue saliendo con los margenes por omision."""
    limpio, cambiado = _lienzo(), _lienzo()
    try:
        cambiado.figure.subplots_adjust(left=0.35, bottom=0.30)
        assert analizar(cambiado) == analizar(limpio)
    finally:
        _cerrar(limpio)
        _cerrar(cambiado)


# 2. LA RECARGA (copia 23-11)

def _copiar(destino):
    destino.mkdir(parents=True, exist_ok=True)
    for sufijo in ("", "-wal", "-shm"):
        origen = Path(str(BD_REBUILD_23_11) + sufijo)
        if origen.exists():
            shutil.copy2(origen, destino / (BD_REBUILD_23_11.name + sufijo))
    return str(destino / BD_REBUILD_23_11.name)


def _fila(ruta, sesion, categoria):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(f"SELECT id_prueba, imagen_path, imagen_resultado FROM pruebas WHERE id_sesion = ? AND id_tipo = ? AND {FILTRO}",
                           (sesion, ID_TIPO[categoria])).fetchone()
    finally:
        con.close()


def _huella_de_pruebas(ruta):
    con = sqlite3.connect(ruta)
    try:
        h = hashlib.md5()
        for fila in con.execute("SELECT * FROM pruebas ORDER BY id_prueba"):
            h.update(repr(fila).encode())
        return h.hexdigest()
    finally:
        con.close()


@pytest.fixture(scope="module")
def curva_nueva(app):
    c = _lienzo()
    try:
        return _analizar(fantoma_con_barras, c)["imagen_analisis"]
    finally:
        _cerrar(c)


@pytest.fixture(scope="module")
def copias(app, tmp_path_factory, curva_nueva):
    """UNA copia de los tres archivos (el informe reusa su conexion de Qt): la sesion 48 queda como se guardo; la 34 pasa a tener un analisis nuevo (la curva sola) y la 30 la curva sola sin corte."""
    if not BD_REBUILD_23_11.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_23_11.name}")
    ruta = _copiar(tmp_path_factory.mktemp("copia_23_11_aj6b"))
    guardadas = _guardadas(ruta)  # las 9 figuras combinadas, antes de tocar la copia
    con = sqlite3.connect(ruta)
    try:
        con.execute("UPDATE pruebas SET imagen_resultado = ? WHERE id_prueba = ?", (curva_nueva, _fila(ruta, SESION_NUEVA, "resolucion_espacial")[0]))
        con.execute("UPDATE pruebas SET imagen_resultado = ?, imagen_path = NULL WHERE id_prueba = ?", (curva_nueva, _fila(ruta, SESION_SIN_CORTE, "resolucion_espacial")[0]))
        con.execute("UPDATE pruebas SET imagen_resultado = ?, imagen_path = ? WHERE id_prueba = ?", (curva_nueva, b"no es una imagen", _fila(ruta, SESION_CORTE_ILEGIBLE, "resolucion_espacial")[0]))
        con.commit()
    finally:
        con.close()
    return {"hoy": ruta, "nueva": ruta, "guardadas": guardadas}


def _conectar(monkeypatch, ruta):
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    conection_mod.Conexion._instance = None
    return conection_mod.Conexion()


@pytest.fixture
def recargar(app, monkeypatch):
    abiertos = []

    def hacer(ruta, sesion, categoria):
        from data.ManejoDatos.catphan_TAC.catphan_db import reconstruir_resultados_desde_bd
        _conectar(monkeypatch, ruta)
        padre = QWidget()
        etiqueta = QLabel(padre)
        lienzo = _lienzo()
        abiertos.extend([lienzo, padre])
        _con_algo_antes(lienzo)
        reconstruir_resultados_desde_bd(sesion, categorias=[categoria], label=etiqueta, canvas=lienzo)
        _esperar()
        return lienzo.figure
    yield hacer
    for w in abiertos:
        _cerrar(w)
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None


def _imagenes(figura):
    return [(ax.get_title(), ax.images[0].get_array()) for ax in figura.axes if ax.images]


def test_la_recarga_de_un_analisis_nuevo_dibuja_el_corte_y_la_curva_lado_a_lado(copias, recargar):
    _, corte, curva = _fila(copias["nueva"], SESION_NUEVA, "resolucion_espacial")
    figura = recargar(copias["nueva"], SESION_NUEVA, "resolucion_espacial")
    assert len(figura.axes) == 2, "el par reemplaza lo que habia en el lienzo"
    vistas = _imagenes(figura)
    assert [t for t, _ in vistas] == ["Imagen original", "Imagen del análisis"]
    assert np.array_equal(np.asarray(vistas[0][1]), np.asarray(Image.open(io.BytesIO(corte))))
    assert np.array_equal(np.asarray(vistas[1][1]), np.asarray(Image.open(io.BytesIO(curva))))
    izq, der = (ax.get_position() for ax in figura.axes)
    assert izq.x1 <= der.x0 + 1e-9 and abs(izq.y0 - der.y0) < 1e-9, "lado a lado"
    assert abs((der.width / izq.width) / (TAMANO_ARCHIVADO[0] / TAMANO_ARCHIVADO[1]) - 1) < 0.01, "cada una con el ancho de su forma"
    pantalla = _pantalla(figura.canvas)
    assert magentas(pantalla) == 0, "en la pantalla no queda nada de lo que habia antes"
    corte_visto, curva_vista = (_trozo(pantalla, ax) for ax in figura.axes)
    assert np.ptp(corte_visto, axis=-1).max() <= 2 and corte_visto.std() > 20, "a la izquierda se ve el corte, en gris"
    assert (curva_vista[..., 2] - curva_vista[..., 0] > 40).sum() > 100, "y a su lado la curva, en su azul"


def test_la_recarga_de_un_analisis_nuevo_sin_corte_guardado_muestra_la_curva_sola(copias, recargar):
    _, corte, curva = _fila(copias["nueva"], SESION_SIN_CORTE, "resolucion_espacial")
    assert corte is None
    vistas = _imagenes(recargar(copias["nueva"], SESION_SIN_CORTE, "resolucion_espacial"))
    assert [t for t, _ in vistas] == ["Imagen de Análisis Guardada"] and np.array_equal(np.asarray(vistas[0][1]), np.asarray(Image.open(io.BytesIO(curva))))


def test_con_el_corte_guardado_ilegible_la_recarga_muestra_la_curva_sola(copias, recargar):
    _, _, curva = _fila(copias["nueva"], SESION_CORTE_ILEGIBLE, "resolucion_espacial")
    vistas = _imagenes(recargar(copias["nueva"], SESION_CORTE_ILEGIBLE, "resolucion_espacial"))
    assert [t for t, _ in vistas] == ["Imagen de Análisis Guardada"] and np.array_equal(np.asarray(vistas[0][1]), np.asarray(Image.open(io.BytesIO(curva))))


def test_la_recarga_de_un_analisis_ya_guardado_no_cambia(copias, recargar):
    _, _, combinada = _fila(copias["hoy"], SESION_01_10, "resolucion_espacial")
    vistas = _imagenes(recargar(copias["hoy"], SESION_01_10, "resolucion_espacial"))
    assert [t for t, _ in vistas] == ["Imagen de Análisis Guardada"]
    assert np.array_equal(np.asarray(vistas[0][1]), np.asarray(Image.open(io.BytesIO(combinada))))


@pytest.mark.parametrize("categoria", OTRAS)
def test_la_recarga_de_las_otras_seis_pruebas_no_cambia(copias, recargar, categoria):
    _, _, guardada = _fila(copias["nueva"], SESION_NUEVA, categoria)
    vistas = _imagenes(recargar(copias["nueva"], SESION_NUEVA, categoria))
    assert [t for t, _ in vistas] == ["Imagen de Análisis Guardada"]
    assert np.array_equal(np.asarray(vistas[0][1]), np.asarray(Image.open(io.BytesIO(guardada))))


# 3. EL PDF

@pytest.fixture(scope="module")
def pdfs(app, copias):
    """El mensual del 01/10/2026 (lo guardado hoy), el del Halcyon 06/2026 con un analisis nuevo y el anual con la seccion de la sesion 48; todo QMessageBox parchado (Trampa 2)."""
    import pandas as pd
    import models.PDF.Anual.reportes_anuales as rep_anual
    import models.PDF.Imagenes.reportes_control_sistema_imagenes as rep_mod
    import models.PDF.pdf as pdf_mod
    salida, huellas = {}, {}
    with pytest.MonkeyPatch.context() as mp:
        for nombre in ("critical", "warning", "information", "question"):
            mp.setattr(QMessageBox, nombre, staticmethod(lambda *a, **k: QMessageBox.Ok))
        mp.setattr(rep_mod, "PdfViewer", FalsoVisor)
        for clave, ruta, sesion, equipo, fecha in (("mensual_hoy", copias["hoy"], SESION_01_10, "Tomógrafo", "01/10/2026"), ("mensual_nueva", copias["nueva"], SESION_NUEVA, "Halcyon", "06/2026"),
                                                   ("anual_hoy", copias["hoy"], SESION_01_10, "Halcyon", "2026")):
            huellas[clave] = _huella_de_pruebas(ruta)
            mp.setattr(conection_mod, "ruta_base_datos", lambda ruta=ruta: ruta)
            conection_mod.Conexion._instance = None
            conection_mod.Conexion()
            if clave.startswith("mensual"):
                FalsoVisor.ultimo = {}
                assert rep_mod.generar_reporte_sistema_imagenes(Padre(ruta), fecha, equipo, "x", ref=sesion, sistema_imagenes=True)
                salida[clave] = FalsoVisor.ultimo["pdf"]
            else:
                tablas = rep_anual.obtener_tablas_sistema_imagenes_y_motivo(Padre(ruta).opeenDatabase(), sesion).tablas
                tablas = {"equipos": pd.DataFrame({"Tipo de equipo": ["Cámara"], "Modelo": ["X"], "Serie": ["1"], "Factor": ["1.0"]}),
                          pdf_mod.CLAVE_TITULO_IMAGENES: rep_mod.titulo_del_informe(), **tablas}
                salida[clave] = bytes(pdf_mod.generar_reporte_pdf_multitabla_anual(tablas_dict=tablas, fecha="2026", user="Físico", tipo_reporte="Anual",
                                                                                     maquina="Halcyon", id_maquina="Halcyon", temp=True).data())
            conection_mod.Conexion._instance.con.close()
            conection_mod.Conexion._instance = None
            assert _huella_de_pruebas(ruta) == huellas[clave], "generar el PDF no cambia lo guardado"
    return salida


def par_de_la_resolucion(pdf):
    """(corte, imagen del analisis) en pixeles: la fila de dos imagenes que sigue al titulo «Resolución espacial» del marco."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    visto = False
    for pagina in doc:
        textos = [l for b in pagina.get_text("dict")["blocks"] for l in b.get("lines", [])]
        if any("".join(s["text"] for s in l["spans"]).strip() == "Resolución espacial" and MARCO[1] <= l["bbox"][1] <= MARCO[3] for l in textos):
            visto = True
        imagenes = sorted((i for i in pagina.get_image_info(xrefs=True) if MARCO[1] < (i["bbox"][1] + i["bbox"][3]) / 2 < MARCO[3]), key=lambda i: i["bbox"][0])
        if visto and len(imagenes) == 2:
            return [np.asarray(Image.open(io.BytesIO(doc.extract_image(i["xref"])["image"])).convert("RGBA")) for i in imagenes]
    pytest.fail("no se encontro el par de la resolucion espacial")


@pytest.mark.parametrize("clave", ["mensual_hoy", "anual_hoy"])
def test_el_pdf_de_un_analisis_ya_guardado_imprime_en_su_cuadro_solo_la_curva(pdfs, clave):
    corte, analisis = par_de_la_resolucion(pdfs[clave])
    assert trae_un_corte(corte), "el cuadro de la imagen original trae el corte"
    assert not trae_un_corte(analisis), f"{clave}: el cuadro de la resolucion espacial trae el corte"
    assert azules(analisis) > 300, "y trae la curva"


def test_el_recorte_en_memoria_conserva_toda_la_curva_de_la_figura_guardada(pdfs, copias):
    _, _, combinada = _fila(copias["hoy"], SESION_01_10, "resolucion_espacial")
    _, analisis = par_de_la_resolucion(pdfs["mensual_hoy"])
    assert azules(analisis) == azules(_rgba(combinada)), "ningun pixel de la curva se pierde al recortar"


def test_el_pdf_de_un_analisis_nuevo_pone_la_curva_entera_sin_recortarla(pdfs, curva_nueva):
    corte, analisis = par_de_la_resolucion(pdfs["mensual_nueva"])
    esperada = np.asarray(_m().recortar_margen_blanco(Image.open(io.BytesIO(curva_nueva))).convert("RGBA"))
    assert trae_un_corte(corte) and analisis.shape == esperada.shape and np.array_equal(analisis, esperada), "solo se le quita el blanco del borde"


# 4. EL DETECTOR DEL PANEL DE LA MTF (contra la verdad de matplotlib y en las 9 figuras guardadas)

def _figura_de_antes(tamano_px, con_curva=True, por_el_ayudante=False):
    """La figura combinada que dibujaba el analisis antes de AJ.6b (corte con anillo y curva), con un corte sintetico; (png, caja del eje de la MTF, caja del corte) [px desde arriba]."""
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    yy, xx = np.mgrid[:512, :512]
    corte = np.where((xx - 256) ** 2 + (yy - 230) ** 2 < 100 ** 2, 170, 0).astype(np.uint8)
    corte[400:405, 60:450] = 230
    fig = Figure(figsize=(tamano_px[0] / 100, tamano_px[1] / 100), dpi=100)
    ax1 = fig.add_subplot(1, 2, 1)
    ax1.imshow(corte, cmap="gray")
    ax1.contour((xx - 256) ** 2 + (yy - 230) ** 2 < 50 ** 2, colors='r', linewidths=0.4)
    ax1.set_title("Anillo resolución")
    ax1.axis("off")
    ax4 = None
    if con_curva:
        ax4 = fig.add_subplot(1, 2, 2)
        ax4.plot([1.0, 2.0, 3.0], [0.95, 0.6, 0.2], 'o-')
        for pct, val in (("20", 2.98), ("50", 2.23)):
            ax4.plot(val, int(pct) / 100, 'rx')
            ax4.text(val, int(pct) / 100, f"{pct}% {val:.2f}", fontsize=8)
        ax4.set_ylim(0, 1.05); ax4.grid(True)
        ax4.set_xlabel("lp/cm"); ax4.set_ylabel("MTF")
        ax4.set_title("MTF normalizada")
    fig.tight_layout()
    if por_el_ayudante:
        png = _A()._png_de_tamano_fijo(fig, ajustar=True)
        fig = pickle.loads(pickle.dumps(fig))
        fig.dpi_scale_trans.clear().scale(fig.dpi)
        fig.set_size_inches(TAMANO_ARCHIVADO[0] / 100, TAMANO_ARCHIVADO[1] / 100)
        fig.subplots_adjust(**{k: matplotlib.rcParams[f"figure.subplot.{k}"] for k in ("left", "right", "bottom", "top", "wspace", "hspace")})
        fig.tight_layout()
        ax1, ax4 = fig.axes[0], (fig.axes[1] if con_curva else None)
    lienzo = FigureCanvasAgg(fig)
    lienzo.draw()
    render, alto = lienzo.get_renderer(), fig.bbox.height

    def caja(bb):
        return (bb.x0, alto - bb.y1, bb.x1, alto - bb.y0)
    if not por_el_ayudante:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        png = buf.getvalue()
    return png, (caja(ax4.get_tightbbox(render)) if ax4 is not None else None), caja(ax1.images[0].get_window_extent(render))


TAMANOS = [(1188, 827), (1348, 827), (1343, 616), (1244, 807), (1323, 802), (1290, 827), (1343, 827), (800, 500), (1000, 700), (1600, 600), (900, 900)]


@pytest.mark.parametrize("con_curva", [True, False], ids=["con_curva", "sin_curva"])
@pytest.mark.parametrize("tamano", TAMANOS + ["ayudante"], ids=lambda t: t if isinstance(t, str) else f"{t[0]}x{t[1]}")
def test_el_panel_de_la_mtf_contiene_el_eje_entero_y_ningun_pixel_del_corte(tamano, con_curva):
    png, eje, corte = _figura_de_antes(TAMANO_ARCHIVADO if tamano == "ayudante" else tamano, con_curva, por_el_ayudante=tamano == "ayudante")
    caja = _m().panel_de_la_mtf(Image.open(io.BytesIO(png)))
    if not con_curva:
        assert caja is None, "sin curva no hay panel: va la figura entera"
        return
    assert caja is not None
    assert caja[0] <= eje[0] + 0.5 and caja[1] <= eje[1] + 0.5 and caja[2] >= eje[2] - 0.5 and caja[3] >= eje[3] - 0.5, f"{caja} no contiene el eje {eje}"
    assert caja[0] >= corte[2], f"{caja} empieza antes de que acabe el corte ({corte[2]:.1f})"


def _guardadas(ruta):
    con = sqlite3.connect(ruta)
    try:
        return con.execute("SELECT id_sesion, id_prueba, imagen_resultado FROM pruebas WHERE id_tipo = 4 AND imagen_resultado IS NOT NULL ORDER BY id_prueba").fetchall()
    finally:
        con.close()


def test_en_las_9_figuras_guardadas_se_encuentra_el_panel_y_el_recorte_no_trae_el_corte(copias):
    guardadas = copias["guardadas"]
    assert len(guardadas) == 9
    for sesion, prueba, blob in guardadas:
        with Image.open(io.BytesIO(blob)) as figura:
            figura.load()
            caja = _m().panel_de_la_mtf(figura)
            assert caja is not None, f"sesion {sesion}, prueba {prueba}"
            pix, recorte = np.asarray(figura.convert("RGBA")), np.asarray(figura.crop(caja).convert("RGBA"))
        assert trae_un_corte(pix) and not trae_un_corte(recorte), f"sesion {sesion}, prueba {prueba}"
        assert azules(recorte) == azules(pix), f"sesion {sesion}, prueba {prueba}: el recorte pierde parte de la curva"


# 5. EL RECORTE SOLO DONDE TOCA, Y ANTE LA DUDA LA FIGURA ENTERA

def _guardar(tmp_path, nombre, png):
    ruta = tmp_path / nombre
    ruta.write_bytes(png)
    return str(ruta)


def test_si_el_detector_duda_va_la_figura_entera(tmp_path):
    m = _m()
    sin_curva = _guardar(tmp_path, "sin.png", _figura_de_antes((1343, 827), con_curva=False)[0])
    reflejada = tmp_path / "reflejada.png"
    Image.open(io.BytesIO(_figura_de_antes((1343, 827))[0])).transpose(Image.FLIP_LEFT_RIGHT).save(reflejada)  # el corte a la derecha: no es la figura de antes
    for ruta in (sin_curva, str(reflejada)):
        with Image.open(ruta) as im:
            entera = m.recortar_margen_blanco(im.copy()).size
        assert m.imagen_preparada(ruta, solo_la_curva=True)[1] == entera


def _sintetica(claro=False, franja_lejos=False, corte=(80, 600), grafico=760):
    """Una figura RGBA de 1343 x 827 [px] hecha a mano: un bloque en las columnas `corte` (oscuro, o claro), la franja blanca (o un relleno gris ralo que la aleja) y lineas de un grafico desde la columna `grafico`."""
    pix = np.full((827, 1343, 4), 255, np.uint8)
    pix[60:760, corte[0]:corte[1], :3] = 200 if claro else 40
    if franja_lejos:
        pix[60:140, corte[1]:corte[1] + 100, :3] = 235  # poco relleno: no es parte del bloque, pero aleja la primera columna blanca
    pix[100:740, grafico, :3] = 0
    pix[740, grafico:1300, :3] = 0
    pix[300:310, grafico + 40:1250, 2] = 180
    return Image.fromarray(pix, "RGBA")


def test_un_bloque_claro_o_sin_franja_blanca_cerca_no_es_un_corte():
    m = _m()
    assert m.panel_de_la_mtf(_sintetica()) is not None, "control: con el bloque oscuro y la franja, hay panel"
    assert m.panel_de_la_mtf(_sintetica(claro=True)) is None, "un bloque claro no es un corte"
    assert m.panel_de_la_mtf(_sintetica(franja_lejos=True)) is None, "sin la franja blanca junto al bloque, duda"


# Sobre los 1343 x 827 [px]: el bloque cubre la columna del 25 % del ancho (335.75), acaba antes del 60 % (805.8) y mide a lo ancho mas del 30 % del alto (248.1).
@pytest.mark.parametrize("dentro,fuera,grafico", [((330, 600), (340, 600), 760), ((20, 340), (20, 330), 760), ((80, 800), (80, 810), 880), ((200, 452), (200, 445), 760)],
                         ids=["empieza_pasado_el_cuarto", "acaba_antes_del_cuarto", "acaba_muy_a_la_derecha", "angosto_para_su_alto"])
def test_un_bloque_oscuro_fuera_del_sitio_de_un_corte_no_es_un_corte(dentro, fuera, grafico):
    m = _m()
    assert m.panel_de_la_mtf(_sintetica(corte=dentro, grafico=grafico)) is not None, "control: unos pixeles por dentro del limite, hay panel"
    assert m.panel_de_la_mtf(_sintetica(corte=fuera, grafico=grafico)) is None, f"el bloque en las columnas {fuera} no esta en el sitio de un corte"


def test_solo_se_recorta_la_imagen_del_analisis_de_la_resolucion_espacial(tmp_path):
    m = _m()
    combinada = _guardar(tmp_path, "c.png", _figura_de_antes((1343, 827))[0])
    with Image.open(combinada) as im:
        entera = m.recortar_margen_blanco(im.copy()).size
        panel = m.recortar_margen_blanco(im.crop(m.panel_de_la_mtf(im))).size
    datos = [["Imagen original", "Imagen del análisis"], ["Prueba", ""], [combinada, combinada]]
    assert [t for _, t in m.TablaDeImagenes(datos, [], "imagen_resolucion_espacial")._preparadas] == [entera, panel], "solo la columna del analisis"
    for otra in ("imagen_uniformidad", "imagen_linealidad_ct", None):
        assert [t for _, t in m.TablaDeImagenes(datos, [], otra)._preparadas] == [entera, entera], otra
    assert [t for _, t in m.colocar("imagen_resolucion_espacial", None, datos, [])[0]._preparadas] == [entera, panel], "el mensual pasa el nombre"


def test_una_curva_nueva_y_el_aviso_no_tienen_panel_que_recortar(app, curva_nueva):
    """El PNG temporal del informe se vuelve a codificar sin la marca: el PDF decide por el contenido y una figura sin corte nunca se recorta."""
    A = _A()
    aviso = A._png_de_tamano_fijo(A.figura_de_la_curva_mtf({}, {}), ajustar=True)
    assert _m().panel_de_la_mtf(Image.open(io.BytesIO(curva_nueva))) is None and _m().panel_de_la_mtf(Image.open(io.BytesIO(aviso))) is None


def test_el_recorte_conserva_la_transparencia_rgba(tmp_path):
    png = _figura_de_antes((1343, 827))[0]
    assert Image.open(io.BytesIO(png)).mode == "RGBA"
    datos, _ = _m().imagen_preparada(_guardar(tmp_path, "r.png", png), solo_la_curva=True)
    assert Image.open(io.BytesIO(datos)).mode == "RGBA"


def test_la_marca_se_lee_de_bytes_ruta_e_imagen_y_falta_en_lo_viejo_y_en_lo_que_no_es_png(tmp_path, curva_nueva, copias):
    from analisisImagenes.catphan.figura_archivada import es_la_curva_sola
    ruta = _guardar(tmp_path, "n.png", curva_nueva)
    assert es_la_curva_sola(curva_nueva) and es_la_curva_sola(ruta) and es_la_curva_sola(Image.open(ruta))
    assert not any(es_la_curva_sola(blob) for _, _, blob in copias["guardadas"])
    assert not es_la_curva_sola(b"no es una imagen") and not es_la_curva_sola(None)


# 6. DONDE ENTRA

def test_el_anual_pasa_el_nombre_de_la_tabla_a_la_maqueta_y_build_exe_lista_el_modulo_nuevo_una_vez():
    arbol = ast.parse((RAIZ / "models/PDF/pdf.py").read_text(encoding="utf-8"))
    funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "_crear_tabla_pdf_anual")
    llamadas = [n for n in ast.walk(funcion) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "TablaDeImagenes"]
    assert len(llamadas) == 1 and [getattr(a, "id", None) for a in llamadas[0].args] == ["data", "style", "tipo_tabla"]
    assert (RAIZ / "build_exe.py").read_text(encoding="utf-8").count('"analisisImagenes.catphan.figura_archivada"') == 1
