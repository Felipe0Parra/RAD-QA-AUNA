"""PD.1 (PLAN_PELICULA_DIARIA_BRAQUI_13-11.md, cierra DP-141): la película diaria se mide con la escala del escaneo (600 ppp), no con la que escribe el editor.
La verdad la da un generador independiente del motor (11 líneas cada 236 px, 9.99 mm a 600 ppp); las listas `*_600` son lo que mide `analizar_lineas` con 600 declarados, igual en 96d2129 y con PD.1.
Rojo contra 96d2129: caen todas salvo las de 600 declarados, la del texto de la ventana del mensual y la de los transparentes (la base no avisa)."""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re

import numpy as np
import pytest
from PIL import Image
from PyQt5.QtWidgets import QMessageBox

import analisisImagenes.Analisis_PlacaRC as rc
from analisisImagenes import pelicula
from analisisImagenes.dibujo_placa_mensual import texto_de_la_imagen

PASO_PX = 236
VERDAD_MM = PASO_PX * 25.4 / 600.0                   # 9.9907 mm entre líneas
DESPLAZAMIENTOS_MM = (0.30, 0.55, -0.40, 0.20, 0.65, -0.30, 0.45, 0.10, -0.55, 0.35, 0.25)
DISTANCIAS_600 = [9.95, 10.03, 9.99, 9.99, 10.12, 9.86, 9.99, 9.99, 9.99, 9.99]
ALINEACION_600 = [0.34, 0.59, 0.47, 0.25, 0.68, 0.47, 0.47, 0.13, 0.55, 0.38, 0.3]
TITULO = "<b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;RESULTADO DE ANÁLISIS DE LA IMAGEN</b>"
NADA_GUARDADO = ("", None, None, "", None, None)
FRASE_DE_LA_CLASE = {"editor": "lo que escribe un editor", "sin_dato": "no declara su resolución", "otra": "sin esa escala no hay milímetros"}


def tira():
    """La tira sintética (RGB uint8): fondo 205, una mancha gaussiana de 70 niveles por parada y una línea de 7 px a 35, con una textura fija (sin azar)."""
    n, x0, alto = 11, 170, 300
    ancho = x0 + (n - 1) * PASO_PX + 170
    x = np.arange(ancho, dtype=float)
    perfil = np.full(ancho, 205.0)
    for i, d in enumerate(DESPLAZAMIENTOS_MM):
        perfil -= 70.0 * np.exp(-0.5 * ((x - (x0 + i * PASO_PX + d * 600 / 25.4)) / 38.0) ** 2)
    img = np.repeat(perfil[None, :], alto, axis=0)
    for i in range(n):
        img[:, x0 + i * PASO_PX - 3:x0 + i * PASO_PX + 4] = 35.0
    img = img + ((np.arange(alto)[:, None] * 7 + np.arange(ancho)[None, :] * 3) % 5 - 2) * 0.8
    gris = np.clip(np.rint(img), 0, 255).astype(int)
    return np.stack([np.clip(gris - 40, 0, 255), gris, np.clip(gris - 70, 0, 255)], axis=2).astype(np.uint8)


def tira_con_esquina_transparente():
    """(RGBA, RGB): la tira con una esquina negra, transparente en la primera y opaca en la segunda, como la que deja un giro en un editor."""
    rgb = tira()
    yy, xx = np.mgrid[:rgb.shape[0], :rgb.shape[1]]
    esquina = (xx < 420) & (yy < 300 - xx * 0.7)
    rgb[esquina] = 0
    return np.dstack([rgb, np.where(esquina, 0, 255).astype(np.uint8)]), rgb


def _guardar(ruta, formato, dpi=None, exif_sin_resolucion=False, fecha=False):
    kw = {} if dpi is None else {"dpi": (dpi, dpi)}
    if fecha:                            # etiqueta 306 del TIFF: la fecha del escaneo
        kw["tiffinfo"] = {306: "2026:03:05 09:30:00"}
    if formato == "JPEG":
        kw["quality"] = 95
        if exif_sin_resolucion:          # EXIF sin las etiquetas 282/283: Pillow rellena 72 ppp (DP-141)
            exif = Image.Exif()
            exif[0x010F], exif[0x0110] = "EPSON", "WF-6590 Series"
            kw["exif"] = exif.tobytes()
    Image.fromarray(tira()).save(ruta, format=formato, **kw)
    return str(ruta)


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """Un diálogo modal bajo offscreen cuelga el proceso: aquí hace caer la prueba."""
    def modal(*args, **kwargs):
        raise AssertionError(f"se abrió un diálogo modal: {args[1:3]}")
    for tipo in ("information", "critical", "warning", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(modal))


@pytest.fixture(scope="module")
def archivos(tmp_path_factory):
    d = tmp_path_factory.mktemp("pd1")
    rgba, rgb = tira_con_esquina_transparente()
    Image.fromarray(rgba, "RGBA").save(d / "png_alfa.png")
    Image.fromarray(rgb).save(d / "png_opaco.png")
    return {
        "t600": _guardar(d / "t600.tif", "TIFF", 600),
        "t599_999": _guardar(d / "t599_999.tif", "TIFF", 599.999),
        "t96_fecha": _guardar(d / "t96_fecha.tif", "TIFF", 96.012, fecha=True),
        "png_alfa": str(d / "png_alfa.png"),
        "png_opaco": str(d / "png_opaco.png"),
        "t96": _guardar(d / "t96.tif", "TIFF", 96.012),
        "t72": _guardar(d / "t72.tif", "TIFF", 72),
        "t300": _guardar(d / "t300.tif", "TIFF", 300),
        "png_sin": _guardar(d / "png_sin.png", "PNG"),
        "png600": _guardar(d / "png600.png", "PNG", 600),
        "jpg600": _guardar(d / "jpg600.jpg", "JPEG", 600),
        "jpg_sin": _guardar(d / "jpg_sin.jpg", "JPEG"),
        "jpg_exif": _guardar(d / "jpg_exif.jpg", "JPEG", exif_sin_resolucion=True),
    }


def analizar(ruta, canvas=None):
    return rc.analizar_lineas(ruta, metodo=True, umbral_relativo=1.0, distancia_minima=40, mostrar=canvas is not None, filtro="clahe", canvas=canvas)


def _lista(informe, rotulo):
    m = re.search(re.escape(rotulo) + r"</b> <span style='font-weight:normal'>\[([^\]]*)\]", informe)
    assert m, informe
    return [float(v) for v in m.group(1).split(",")]


def distancias(informe):
    return _lista(informe, "Distancias entre líneas(mm):")


def alineacion(informe):
    return _lista(informe, "Desplazamientos entre líneas y centros circulares (mm):")


def promedios(informe):
    return [float(v) for v in re.findall(r"Promedio =</b> <span style='font-weight:normal'>([\d.]+) mm", informe)]


def aviso_esperado(ruta):
    """El texto de la ventana del mensual para ese archivo (la misma función, con lo que lee `leer_pelicula`)."""
    with open(ruta, "rb") as f:
        p = pelicula.leer_pelicula(f.read())
    P = {"resolucion_escaneo_dpi": 600.0, "resoluciones_de_editor_dpi": [72.0, 96.0], "tolerancia_dpi_relativa": 0.01}
    return texto_de_la_imagen(p.formato, p.bits, p.validos.shape, p.dpi, pelicula.clase_resolucion(p.dpi, P), p.fecha_escaneo, p.transparentes, 600.0)


def sin_el_aviso(informe, ruta):
    linea = f"<br>{aviso_esperado(ruta)}<br>"
    assert informe.count(linea) == 1, informe[:400]
    return informe.replace(linea, "", 1)


def figura(canvas):
    """Lo que se dibujó, eje por eje: títulos, rótulos, curvas (datos exactos y estilo) e imágenes."""
    ejes = []
    for ax in canvas.figure.axes:
        lineas = [(l.get_label(), l.get_color(), l.get_linestyle(), l.get_marker(), np.asarray(l.get_xydata(), float).tobytes()) for l in ax.get_lines()]
        imagenes = [(np.asarray(i.get_array()).tobytes(), tuple(i.get_extent())) for i in ax.get_images()]
        ejes.append((ax.get_title(), ax.get_xlabel(), ax.get_ylabel(), lineas, imagenes))
    return ejes


def lienzo():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    return FigureCanvasAgg(Figure())


class TestLaEscalaEsLaDelEscaneo:
    def test_la_tira_de_600_ppp_guardada_con_96_ppp_mide_10_mm_y_no_62(self, archivos):
        informe = analizar(archivos["t96"])
        assert distancias(informe) == DISTANCIAS_600
        assert promedios(informe)[0] == pytest.approx(VERDAD_MM, abs=0.05)

    def test_la_ventana_de_1_mm_de_la_alineacion_usa_la_misma_escala(self, archivos):
        assert alineacion(analizar(archivos["t96"])) == ALINEACION_600

    def test_la_misma_tira_con_600_declarados_no_cambia_y_no_lleva_aviso(self, archivos):
        informe = analizar(archivos["t600"])
        assert (distancias(informe), alineacion(informe)) == (DISTANCIAS_600, ALINEACION_600)
        assert informe.startswith(TITULO + "<br><b>Líneas Detectadas:</b><br>") and "dpi" not in informe

    def test_un_png_de_600_ppp_declara_599_9988_y_cuenta_como_600(self, archivos):
        informe = analizar(archivos["png600"])
        assert (distancias(informe), alineacion(informe)) == (DISTANCIAS_600, ALINEACION_600) and "dpi" not in informe

    @pytest.mark.parametrize("nombre", ["png600", "t599_999"])
    def test_la_cabecera_de_599_9988_o_599_999_cuenta_como_600_exactos(self, archivos, nombre):
        esperada = (pytest.approx(25.4 / 600 / 10, rel=1e-12), None)
        assert rc.metadata(archivos["t600"]) == esperada and rc.metadata(archivos[nombre]) == esperada
        a, b = lienzo(), lienzo()
        analizar(archivos["t600"], a)
        analizar(archivos[nombre], b)
        assert figura(b) == figura(a)

    @pytest.mark.parametrize("nombre", ["t72", "png_sin"])
    def test_72_declarados_y_un_png_sin_dato_se_miden_a_600(self, archivos, nombre):
        informe = analizar(archivos[nombre])
        assert (distancias(informe), alineacion(informe)) == (DISTANCIAS_600, ALINEACION_600)

    @pytest.mark.parametrize("nombre", ["jpg_sin", "jpg_exif"])
    def test_un_jpeg_sin_resolucion_mide_lo_mismo_que_con_600_declarados(self, archivos, nombre):
        con_600, sin = analizar(archivos["jpg600"]), analizar(archivos[nombre])
        assert (distancias(sin), alineacion(sin), promedios(sin)) == (distancias(con_600), alineacion(con_600), promedios(con_600))
        assert promedios(sin)[0] == pytest.approx(VERDAD_MM, abs=0.05)

    def test_un_tiff_de_300_ppp_declarados_no_da_milimetros_ni_medidas(self, archivos):
        assert analizar(archivos["t300"]) == TITULO + f"<br>{aviso_esperado(archivos['t300'])}<br>"


class TestElAvisoEsElTextoDeLaVentanaDelMensual:
    @pytest.mark.parametrize("nombre, clase", [("t96", "editor"), ("t72", "editor"), ("png_sin", "sin_dato"), ("jpg_sin", "sin_dato"), ("jpg_exif", "sin_dato"),
                                               ("t300", "otra")])
    def test_el_informe_lleva_una_linea_con_el_texto_de_texto_de_la_imagen(self, archivos, nombre, clase):
        esperado = aviso_esperado(archivos[nombre])
        assert FRASE_DE_LA_CLASE[clase] in esperado, esperado
        assert analizar(archivos[nombre]).startswith(TITULO + f"<br>{esperado}<br>")

    @pytest.mark.parametrize("nombre", ["t96", "t72", "png_sin"])
    def test_sin_el_aviso_el_informe_es_el_de_600_ppp_byte_a_byte(self, archivos, nombre):
        assert sin_el_aviso(analizar(archivos[nombre]), archivos[nombre]) == analizar(archivos["t600"])

    def test_el_aviso_lleva_la_fecha_del_escaneo_que_trae_el_archivo(self, archivos):
        esperado = aviso_esperado(archivos["t96_fecha"])
        assert "escaneada el 2026-03-05" in esperado, esperado
        assert analizar(archivos["t96_fecha"]).startswith(TITULO + f"<br>{esperado}<br>")

    def test_el_aviso_no_llama_sin_dato_a_los_pixeles_transparentes_que_el_diario_mide(self, archivos):
        with open(archivos["png_alfa"], "rb") as f:
            assert pelicula.leer_pelicula(f.read()).transparentes > 0
        informe = analizar(archivos["png_alfa"])
        assert "transparentes" not in informe, informe[:400]
        assert informe == analizar(archivos["png_opaco"])

    def test_el_aviso_no_trae_lo_que_la_pagina_raspa(self, archivos):
        for nombre in ("t96", "png_sin", "jpg_exif", "t300"):
            texto = aviso_esperado(archivos[nombre])
            assert not re.search(r"Promedio|Desviaci|Distancias|Desplazamientos|\bmm\b", texto), texto


class TestLaFiguraUsaLaMismaEscala:
    def test_la_figura_de_la_tira_con_96_ppp_es_la_de_600(self, archivos):
        a, b = lienzo(), lienzo()
        analizar(archivos["t600"], a)
        analizar(archivos["t96"], b)
        assert len(a.figure.axes) == 3 and figura(b) == figura(a)

    def test_otra_no_dibuja_y_el_lienzo_no_conserva_la_pelicula_anterior(self, archivos, monkeypatch):
        c = lienzo()
        analizar(archivos["t600"], c)
        assert len(c.figure.axes) == 3
        llamadas = []
        monkeypatch.setattr(rc, "graficar_resultados", lambda *a, **k: llamadas.append(1))
        analizar(archivos["t300"], c)
        assert c.figure.axes == [] and llamadas == []
        assert len(np.unique(np.asarray(c.buffer_rgba()).reshape(-1, 4), axis=0)) == 1, "lo que se ve sigue siendo la película anterior: falta redibujar"


@pytest.fixture(scope="module")
def pagina():
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QLabel, QWidget
    from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq
    app = QApplication.instance() or QApplication([])
    obj = PruebaDiariaBraq.__new__(PruebaDiariaBraq)
    QWidget.__init__(obj)
    obj._widgets_lazy = {}          # lo pide su limpieza al destruirse
    obj.resultado_label = QLabel()
    obj.resultado_label.setTextFormat(Qt.RichText)
    yield obj, app
    from PyQt5.QtCore import QCoreApplication, QEvent
    for w in (obj.resultado_label, obj):
        w.hide()
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def raspar(pagina, informe):
    obj, _ = pagina
    obj.resultado_label.setText(informe)
    return obj.guardar_datos()


class TestLaPaginaGuardaLosMismosSeisNumeros:
    def test_el_aviso_no_cambia_lo_que_guarda_anadir(self, archivos, pagina):
        guardado = raspar(pagina, analizar(archivos["t96"]))
        assert guardado == raspar(pagina, analizar(archivos["t600"]))
        assert guardado[0] == str(DISTANCIAS_600) and guardado[3] == str(ALINEACION_600) and guardado[1] == pytest.approx(VERDAD_MM, abs=0.05)

    def test_otra_guarda_null_en_los_seis(self, archivos, pagina):
        assert raspar(pagina, analizar(archivos["t300"])) == NADA_GUARDADO


class TestLaCopiaDeLaEscalaDelProcedimiento:
    def test_es_la_misma_del_mensual_y_de_la_posicion_inicial(self):
        from analisisImagenes import placa_mensual, posicion_inicial_braqui
        assert set(rc.ESCALA_DEL_PROCEDIMIENTO) == set(pelicula.CLAVES_DE_LA_ESCALA)
        for k in pelicula.CLAVES_DE_LA_ESCALA:
            assert rc.ESCALA_DEL_PROCEDIMIENTO[k] == placa_mensual.VALORES_DE_LA_GEOMETRIA[k] == posicion_inicial_braqui.PARAMETROS[k], k
