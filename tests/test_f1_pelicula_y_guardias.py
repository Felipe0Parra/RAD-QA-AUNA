"""F.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, DA-83 a DA-89), segunda mitad: la PELICULA del PDF mensual con el recuadro del campo luminoso encima, la paginacion de la seccion y los GUARDIAS por AST.

LA PELICULA (cuarta respuesta del 11-10: «Quiero que el pdf mensual sí lleve dibujado el recuadro del campo luminoso sobre la imagen. De resto nada más»): la imagen tal como se guardo, conservando su
proporcion y en 384 x 360 pt como mucho, con encima SOLO los cuatro lados de `recuadro_luminoso` sobre los puntos guardados, como un trazo vectorial de 0.5 pt, del color de la pestana 1 y sin relleno. Sus
pixeles no se tocan: un JPEG se extrae del PDF con sus BYTES (MuPDF y Pillow decodifican el mismo JPEG distinto: hasta 20 niveles en el 28 % de los pixeles de ML0, medido), un PNG o un TIFF como el mapa de
`fitz.Pixmap` contra Pillow en 8 bits. Los vertices, llevados a pixeles con el rectangulo de la imagen en la pagina, son los de `recuadro_luminoso` (<= 0.01 px; medido < 0.0011 px) y en ML0 los clics se apartan
4.3 px de las marcas refinadas, asi que dibujarlo con los clics se ve. Una fila de mas de 429 pt tumba el PDF entero (`LayoutError`): la pelicula se encaja en 384 x 360 pt aunque la imagen sea de 2000 x 9000 px.

LA PAGINACION (medida en el generador real): cada tabla de la seccion va en `KeepTogether`, asi que el titulo esta en la misma pagina que su primera fila, la leyenda en la de la pelicula y la figura en la de
su titulo. LOS GUARDIAS: las claves de la seccion estan en `orden_tablas` de 600/iX y las de texto en la lista de estilos con SPAN; los modulos nuevos no escriben una capa a mano ni leen `CAPA_POR_OMISION`,
no importan Qt, `pyplot` ni `matplotlib.use`, no leen el dpi, no nombran los cinco nombres del piso de A.3, no llevan SQL, ni veredicto, ni simbolos (DA-18), ni unidades entre parentesis.
Se siembra todo antes de abrir QtSql (DP-147)."""
import ast
import gc
import inspect
import io
import json
import re
from pathlib import Path

import fitz
import numpy as np
import pandas as pd
import pytest
from PIL import Image as PILImage
from reportlab.platypus import Image as RLImage

import _corpus
from _f1_ayudas import (CLAVES_DE_LA_SECCION, COLOR_DEL_RECUADRO_RGB, GROSOR_DEL_RECUADRO_PT, LEYENDA_DEL_RECUADRO, SIMBOLOS_DA18, TITULO_DE_LA_PELICULA, TITULO_DE_LA_SECCION,  # noqa: F401
                        TITULO_DE_LOS_PARAMETROS, app, cerrar_mundo, dibujo, imagenes_de, mundo_nuevo, normal, paginas_de, parametros, pdf_mod, plantilla, pm,
                        recuadro, rm, seccion, texto_de)  # noqa: F401
from test_b6_pdf_capa_reportada_braqui import capas_escritas_a_mano, lee_capa_por_omision
from test_c2_perfiles_y_coincidencia import CLICS_REALES

pytestmark = pytest.mark.usefixtures("app")
RAIZ = Path(__file__).resolve().parent.parent
SECCION_PY = "models/PDF/Mensuales/seccion_placa_mensual.py"
PELICULA_PY = "models/PDF/Mensuales/pelicula_con_recuadro.py"
MENSUALES_PY = "models/PDF/Mensuales/reportes_mensuales.py"
PDF_PY = "models/PDF/pdf.py"
LOS_DOS_MODULOS = (SECCION_PY, PELICULA_PY)
ANCHO_MAXIMO_PT, ALTO_MAXIMO_PT = 384.0, 360.0


def _fuente(ruta):
    return (RAIZ / ruta).read_text(encoding="utf-8")


# ======================================================================================================================================================== el mundo de las peliculas reales

PELICULAS = {"ML0": "ML0", "EPSON008": "EPSON008_TIF", "EPSON027": "EPSON027", "REF40": "PLACA_REF40"}       # nombre del control -> clave del corpus (y de CLICS_REALES)


def _bytes(clave):
    ruta = _corpus.pelicula(clave)
    if ruta is None:
        pytest.skip(f"la pelicula real {clave} no esta (ImagenesDeReferencia/PlacasHistoricas)")
    return Path(ruta).read_bytes()


@pytest.fixture(scope="module")
def mundo(plantilla, tmp_path_factory):
    """Una BD con un control mensual por pelicula real, el analisis nuevo guardado con el escritor real (la capa verde, en la base por omision del motor) y, de ML0, una copia con otra version del algoritmo."""
    datos = {nombre: _bytes(clave) for nombre, clave in PELICULAS.items()}
    m, mp, previo = mundo_nuevo(plantilla, tmp_path_factory)
    try:
        for nombre, clave in PELICULAS.items():
            m.control(nombre, imagen=datos[nombre] if nombre == "REF40" else None, franjas=nombre == "REF40")
            m.guardar(nombre, datos[nombre], CLICS_REALES[clave], "G", parametros("netOD"), archivo=f"{clave}.bin")
        m.control("ML0_otra_version")
        m.guardar("ML0_otra_version", datos["ML0"], CLICS_REALES["ML0"], "G", parametros("netOD"))
        m.sql("UPDATE analisis_placa_mensual SET version = 'PM-0' WHERE ref = ?", (m.refs["ML0_otra_version"],))
        m.datos = datos
        yield m
    finally:
        cerrar_mundo(mp, previo)
        gc.collect()


def _puntos_guardados(m, nombre):
    return json.loads(m.consulta("SELECT puntos FROM analisis_placa_mensual WHERE ref = ? AND activo = 1", (m.refs[nombre],))[0][0])


def _la_pelicula(pdf, tamano_px):
    """(pagina, rect, xref, ancho_px, alto_px) de la pelicula NUEVA del PDF: la imagen del tamano en pixeles de la guardada que no es el cuadrado viejo de 180 x 180 pt."""
    candidatas = [i for i in imagenes_de(pdf) if (i[3], i[4]) == tamano_px and abs(i[1].width - 180) > 1]
    assert len(candidatas) == 1, [(i[0], i[1], i[3], i[4]) for i in imagenes_de(pdf)]
    return candidatas[0]


def _es_del_recuadro(d):
    """F1-R2-P01: True si el dibujo `d` (de `get_drawings()`) tiene el color, el grosor y la falta de relleno del recuadro. UNA definicion de «dibujo del recuadro» para las dos pruebas que lo cuentan
    (`_recuadro_dibujado`: cuatro lados exactos) y lo descartan (`test_nada_mas_se_dibuja_sobre_la_pelicula`): un dibujo del MISMO color pero de otro grosor o con relleno (unas diagonales finas, un
    reticulo) no es el recuadro, y ninguna de las dos lo dejaba pasar a la vez."""
    if not d.get("color") or not all(abs(a - b) < 0.01 for a, b in zip(d["color"], COLOR_DEL_RECUADRO_RGB)):
        return False
    return abs((d.get("width") or 0) - GROSOR_DEL_RECUADRO_PT) <= 1e-6 and d.get("fill") is None


def _recuadro_dibujado(pdf, imagen):
    """([vertices en puntos del PDF], lados) de los dibujos de la pagina del color y el ancho del recuadro que caen dentro del rectangulo de la imagen. PyMuPDF informa un recuadro girado como segmentos
    (`l`) y uno alineado con los ejes como un rectangulo (`re`): se aceptan los dos. La rejilla, los fondos de la tabla y las lineas de firma son otros dibujos de la pagina: se filtran."""
    pagina, rect, _, _, _ = imagen
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        vertices, lados, dibujos = [], 0, []
        for d in doc[pagina - 1].get_drawings():
            if not _es_del_recuadro(d):
                continue
            if not (rect + (-1, -1, 1, 1)).contains(fitz.Rect(d["rect"])):
                continue
            dibujos.append(d)
            for it in d["items"]:
                if it[0] == "l":
                    vertices += [(it[1].x, it[1].y), (it[2].x, it[2].y)]
                    lados += 1
                elif it[0] == "re":
                    r = it[1]
                    vertices += [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                    lados += 4
                elif it[0] == "qu":
                    q = it[1]
                    vertices += [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
                    lados += 4
        return vertices, lados, dibujos
    finally:
        doc.close()


def _a_pixeles(vertices, imagen):
    """Un punto del PDF -> pixeles de la imagen, con el rectangulo de la imagen en la pagina y el centro del pixel en el entero (como matplotlib): escrito aqui aparte, no tomado de F.1."""
    _, rect, _, ancho, alto = imagen
    return [((x - rect.x0) * ancho / rect.width - 0.5, (y - rect.y0) * alto / rect.height - 0.5) for x, y in vertices]


def _error_maximo(vertices_px, esquinas):
    """El mayor, sobre las esquinas esperadas, de la distancia al vertice dibujado mas cercano; y el mayor, sobre los vertices dibujados, de la distancia a la esquina mas cercana."""
    ida = max(min(float(np.hypot(px - ex, py - ey)) for px, py in vertices_px) for ex, ey in esquinas)
    vuelta = max(min(float(np.hypot(px - ex, py - ey)) for ex, ey in esquinas) for px, py in vertices_px)
    return max(ida, vuelta)


DPI_DEL_RENDER = 300
MUESTRAS_POR_LADO = (0.1, 0.3, 0.5, 0.7, 0.9)
TOLERANCIA_DE_COLOR = 40.0                     # distancia euclidiana en RGB (0 a 255): la linea de 0.5 pt mide ~2 px a 300 ppp y sus bordes se mezclan con la pelicula; en su centro es el color exacto


def _lados_de(dibujos):
    """[((x0, y0), (x1, y1))] en puntos de la pagina: los lados que trazan los dibujos del recuadro (PyMuPDF informa segmentos `l`, un rectangulo `re` o un cuadrilatero `qu`)."""
    lados = []
    for d in dibujos:
        for it in d["items"]:
            if it[0] == "l":
                lados.append(((it[1].x, it[1].y), (it[2].x, it[2].y)))
                continue
            if it[0] == "re":
                r = it[1]
                vs = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
            elif it[0] == "qu":
                q = it[1]
                vs = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
            else:
                continue
            lados += [(vs[k], vs[(k + 1) % 4]) for k in range(4)]
    return lados


def _muestras_con_el_color(pdf, pagina, lados):
    """REV-PROD-1 / F1R1-P01: [cuantas de las cinco muestras de cada lado tienen el color del recuadro a menos de 2 px en el RENDER de la pagina a 300 ppp]. `get_drawings()` informa el trazo aunque la
    imagen opaca lo tape o sea transparente; lo que ve quien abre el PDF firmado es el render. Se mira una ventana de 5 x 5 px alrededor de cada punto del lado (el redondeo a pixel no cae justo en la linea)."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        pix = doc[pagina - 1].get_pixmap(dpi=DPI_DEL_RENDER)
        render = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    finally:
        doc.close()
    objetivo = np.array([round(c * 255) for c in COLOR_DEL_RECUADRO_RGB])
    escala = DPI_DEL_RENDER / 72.0
    cuentas = []
    for (x0, y0), (x1, y1) in lados:
        n = 0
        for t in MUESTRAS_POR_LADO:
            cx, cy = int(round((x0 + (x1 - x0) * t) * escala)), int(round((y0 + (y1 - y0) * t) * escala))
            ventana = render[max(cy - 2, 0):cy + 3, max(cx - 2, 0):cx + 3].reshape(-1, 3).astype(int)
            n += int(ventana.size > 0 and np.sqrt(((ventana - objetivo) ** 2).sum(axis=1)).min() < TOLERANCIA_DE_COLOR)
        cuentas.append(n)
    return cuentas


def _indices_de_pintura(pdf, imagen):
    """REV-PROD-1 / F1R1-P01: ([posiciones de la imagen], [posiciones de los trazos que caen dentro de su rectangulo]) en el registro de pintura de la pagina (`get_bboxlog`, en orden de pintura: lo
    pintado despues tapa a lo pintado antes). La rejilla de la tabla y las lineas de firma quedan fuera del rectangulo de la pelicula (prueba `test_nada_mas_se_dibuja_sobre_la_pelicula`)."""
    pagina, rect = imagen[0], imagen[1]
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        registro = doc[pagina - 1].get_bboxlog()
    finally:
        doc.close()
    de_la_imagen = [k for k, (tipo, bb) in enumerate(registro) if tipo == "fill-image" and all(abs(a - b) < 0.5 for a, b in zip(bb, rect))]
    trazos = [k for k, (tipo, bb) in enumerate(registro) if tipo == "stroke-path" and (rect + (-1, -1, 1, 1)).contains(fitz.Rect(bb))]
    return de_la_imagen, trazos


def _palabras_sobre_la_pelicula(pdf, imagen):
    """F1-R2-P02: [palabra] del texto que la pagina de la imagen pinta DENTRO del rectangulo de la pelicula (achicado 1 pt por lado). `get_drawings()` no informa el texto: un rotulo encima de la pelicula
    solo se ve aqui (`get_text("words")`)."""
    pagina, dentro = imagen[0], fitz.Rect(imagen[1]) + (1, 1, -1, -1)
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return [p[4] for p in doc[pagina - 1].get_text("words") if fitz.Rect(p[:4]).intersects(dentro)]
    finally:
        doc.close()


class TestLaPeliculaDelPdfEsLaGuardadaConSuRecuadroEncima:
    @pytest.mark.parametrize("nombre", ["ML0", "REF40"])
    def test_un_jpeg_se_incrusta_con_sus_bytes(self, mundo, nombre):
        """F1-M13: reportlab incrusta el JPEG con sus bytes; recomprimirlo cambiaria la evidencia. MuPDF y Pillow decodifican el mismo JPEG distinto, asi que la identidad es la de los BYTES."""
        pdf = mundo.pdf(nombre)
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        imagen = _la_pelicula(pdf, (ancho, alto))
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            assert doc.extract_image(imagen[2])["image"] == mundo.datos[nombre]
        finally:
            doc.close()

    def test_un_tiff_rgba_de_8_bits_se_extrae_igual_a_pillow_en_8_bits(self, mundo):
        pdf = mundo.pdf("EPSON008")
        referencia = np.array(PILImage.open(io.BytesIO(mundo.datos["EPSON008"])).convert("RGB"))
        imagen = _la_pelicula(pdf, (referencia.shape[1], referencia.shape[0]))
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            pix = fitz.Pixmap(doc, imagen[2])
            arreglo = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        finally:
            doc.close()
        assert arreglo.shape[:2] == referencia.shape[:2] and not np.any(arreglo[:, :, :3] != referencia)

    @pytest.mark.parametrize("nombre", list(PELICULAS))
    def test_conserva_la_proporcion_y_cabe_en_384_x_360_pt_lo_mas_grande_posible(self, mundo, nombre):
        """F1-M03 / F1-M14: ni el cuadrado de 2.5 x 2.5 pulgadas de la imagen vieja ni mas alta que el maximo (una fila de mas de 429 pt tumba el PDF entero)."""
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        _, rect, _, _, _ = _la_pelicula(mundo.pdf(nombre), (ancho, alto))
        assert abs(rect.width / rect.height - ancho / alto) < 0.002 * ancho / alto, (rect, ancho, alto)
        assert rect.width <= ANCHO_MAXIMO_PT + 0.5 and rect.height <= ALTO_MAXIMO_PT + 0.5
        assert abs(rect.width - ANCHO_MAXIMO_PT) < 0.5 or abs(rect.height - ALTO_MAXIMO_PT) < 0.5, "encajada lo mas grande que cabe"

    @pytest.mark.parametrize("nombre", list(PELICULAS))
    def test_el_recuadro_son_exactamente_cuatro_lados_del_color_y_el_ancho_del_recuadro_sin_relleno(self, mundo, nombre):
        """F1-M12 / F1-M-diagonales: el trazo es de 0.5 pt y sin relleno (uno de 2 pt taparia el borde de la radiacion junto a la luz); ni diagonales, ni cruce, ni reticulo, ni rotulos: cuatro lados."""
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        imagen = _la_pelicula(mundo.pdf(nombre), (ancho, alto))
        vertices, lados, dibujos = _recuadro_dibujado(mundo.pdf(nombre), imagen)
        assert lados == 4 and len(dibujos) == 1, (lados, len(dibujos))

    @pytest.mark.parametrize("nombre", list(PELICULAS))
    def test_el_recuadro_se_pinta_despues_de_la_imagen_asi_que_queda_encima(self, mundo, nombre):
        """REV-PROD-1 / F1R1-P01: «encima de la imagen (una subclase de Image que dibuja la imagen y despues el trazo)». Si el trazo se pintara ANTES, existiria en el PDF con su color, su grosor y sus
        vertices exactos y los pixeles opacos de la pelicula lo taparian: ninguna prueba de geometria lo ve. El orden de pintura de la pagina (`get_bboxlog`) dice cual va despues."""
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        pdf = mundo.pdf(nombre)
        de_la_imagen, trazos = _indices_de_pintura(pdf, _la_pelicula(pdf, (ancho, alto)))
        assert len(de_la_imagen) == 1 and trazos, (de_la_imagen, trazos)
        assert min(trazos) > de_la_imagen[0], f"el trazo ({min(trazos)}) se pinta antes que la imagen ({de_la_imagen[0]}): queda debajo"

    @pytest.mark.parametrize("nombre", list(PELICULAS))
    def test_el_recuadro_se_ve_en_el_render_sobre_sus_cuatro_lados(self, mundo, nombre):
        """REV-PROD-1 / F1R1-P01: lo que importa es lo que se VE al abrir el PDF firmado. En el render a 300 ppp, sobre cada uno de los cuatro lados (cinco muestras por lado) hay pixeles del color del
        recuadro: un trazo debajo de la imagen, transparente o del color de la pelicula no pasa."""
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        pdf = mundo.pdf(nombre)
        imagen = _la_pelicula(pdf, (ancho, alto))
        lados = _lados_de(_recuadro_dibujado(pdf, imagen)[2])
        assert len(lados) == 4, lados
        assert _muestras_con_el_color(pdf, imagen[0], lados) == [len(MUESTRAS_POR_LADO)] * 4

    @pytest.mark.parametrize("nombre", list(PELICULAS))
    def test_los_vertices_son_los_de_recuadro_luminoso_sobre_los_puntos_guardados(self, mundo, nombre):
        """F1-M01, M02, y el eje y: llevados a pixeles con el rectangulo de la imagen en la pagina, los cuatro vertices son los de `recuadro_luminoso` (<= 0.01 px). Sin el +0.5 del centro del
        pixel el error es de 0.5 px; sin los `_offs_x` y `_offs_y` de la celda, de decenas de puntos; con el eje y sin invertir, de cientos de pixeles."""
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        imagen = _la_pelicula(mundo.pdf(nombre), (ancho, alto))
        vertices, _, _ = _recuadro_dibujado(mundo.pdf(nombre), imagen)
        esperadas = pm().recuadro_luminoso(_puntos_guardados(mundo, nombre)).esquinas
        assert len(esperadas) == 4
        assert _error_maximo(_a_pixeles(vertices, imagen), esperadas) < 0.01

    def test_el_recuadro_es_el_de_las_marcas_refinadas_y_no_el_de_los_clics(self, mundo):
        """P10: en ML0 los clics del cuaderno se apartan 4.3 px de las marcas refinadas: dibujarlo con los clics se ve."""
        imagen = _la_pelicula(mundo.pdf("ML0"), PILImage.open(io.BytesIO(mundo.datos["ML0"])).size)
        vertices, _, _ = _recuadro_dibujado(mundo.pdf("ML0"), imagen)
        desde_clics = _error_maximo(_a_pixeles(vertices, imagen), CLICS_REALES["ML0"][:4])
        assert desde_clics > 1.0, f"los vertices coinciden con los clics ({desde_clics:.2f} px): el recuadro debe salir de las marcas refinadas"

    def test_con_otra_version_guardada_el_recuadro_sale_igual_porque_es_de_los_puntos(self, mundo):
        """El recuadro es el con que se midio lo impreso: sale tambien cuando la version no es la de hoy (y no se vuelve a medir para dibujarlo)."""
        tamano = PILImage.open(io.BytesIO(mundo.datos["ML0"])).size
        imagen = _la_pelicula(mundo.pdf("ML0_otra_version"), tamano)
        vertices, lados, _ = _recuadro_dibujado(mundo.pdf("ML0_otra_version"), imagen)
        assert lados == 4
        assert _error_maximo(_a_pixeles(vertices, imagen), pm().recuadro_luminoso(_puntos_guardados(mundo, "ML0_otra_version")).esquinas) < 0.01

    @pytest.mark.parametrize("nombre", list(PELICULAS))
    def test_nada_mas_se_dibuja_sobre_la_pelicula(self, mundo, nombre):
        """La pelicula no es una grafica de medida: ningun otro dibujo vectorial cae dentro de su rectangulo (la rejilla de la tabla queda fuera de el). F1-R2-P01: «otro» es todo el que no tenga el color,
        el grosor Y la falta de relleno del recuadro (`_es_del_recuadro`): unas diagonales o un reticulo del color del recuadro pero de otro grosor ya no se descartan por el color."""
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        pdf = mundo.pdf(nombre)
        imagen = _la_pelicula(pdf, (ancho, alto))
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            dentro = fitz.Rect(imagen[1]) + (1, 1, -1, -1)
            otros = [d for d in doc[imagen[0] - 1].get_drawings() if dentro.contains(fitz.Rect(d["rect"])) and not _es_del_recuadro(d)]
        finally:
            doc.close()
        assert otros == [], f"{len(otros)} dibujo(s) ajenos al recuadro sobre la pelicula"

    @pytest.mark.parametrize("nombre", list(PELICULAS))
    def test_ningun_texto_cae_sobre_la_pelicula(self, mundo, nombre):
        """F1-R2-P02: «sin diagonales, cruce, reticulo, bandas ni rotulos»: ni una palabra se pinta dentro del rectangulo de la pelicula (el titulo y la leyenda van arriba y abajo, en su propia fila)."""
        ancho, alto = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        pdf = mundo.pdf(nombre)
        assert _palabras_sobre_la_pelicula(pdf, _la_pelicula(pdf, (ancho, alto))) == []

    @pytest.mark.parametrize("nombre", ["ML0", "EPSON008"])
    def test_la_base_de_la_medida_es_la_del_registro_densidad_optica_neta(self, mundo, nombre):
        """OD.1: la base viaja en los parametros guardados; el PDF la dice en su fila (la de la omision del motor en estas siembras es la densidad optica neta)."""
        texto = normal(texto_de(mundo.pdf(nombre)))
        assert f"Base de la medida {pm().BASE_DENSIDAD_OPTICA}" in texto

    @pytest.mark.parametrize("nombre", ["ML0", "EPSON008"])
    def test_la_leyenda_dice_que_es_el_recuadro(self, mundo, nombre):
        texto = normal(texto_de(mundo.pdf(nombre)))
        assert normal(LEYENDA_DEL_RECUADRO) in texto and TITULO_DE_LA_PELICULA in texto
        assert "Sin recuadro" not in texto

    def test_con_el_analisis_nuevo_y_la_imagen_vieja_van_las_dos_peliculas_cada_una_como_es(self, mundo):
        """Un control viejo vuelto a analizar (REF40: franjas, imagen vieja y analisis nuevo con la MISMA pelicula): la nueva con su recuadro y la vieja en su cuadrado de 2.5 pulgadas, sin recuadro."""
        pdf = mundo.pdf("REF40")
        tamano = PILImage.open(io.BytesIO(mundo.datos["REF40"])).size
        viejas = [i for i in imagenes_de(pdf) if abs(i[1].width - 180) < 1 and abs(i[1].height - 180) < 1]
        assert len(viejas) == 1 and (viejas[0][3], viejas[0][4]) == tamano, "la imagen vieja, re-codificada pero del mismo tamano en pixeles"
        nueva = _la_pelicula(pdf, tamano)
        assert _recuadro_dibujado(pdf, nueva)[1] == 4 and _recuadro_dibujado(pdf, viejas[0])[1] == 0, "el recuadro solo en la nueva"


# ======================================================================================================================================================== la subclase de Image, sin base

def _imagen_png(ancho, alto, modo="RGB", semilla=3):
    rng = np.random.default_rng(semilla)
    arreglo = rng.integers(0, 255, size=(alto, ancho, {"RGB": 3, "RGBA": 4}[modo]), dtype=np.uint8)
    buf = io.BytesIO()
    PILImage.fromarray(arreglo, modo).save(buf, format="PNG")
    return buf.getvalue(), arreglo


def _pdf_con(flujo, leyenda="leyenda de prueba"):
    tablas = {"placa_mensual_pelicula": pd.DataFrame([[flujo], [leyenda]], columns=[TITULO_DE_LA_PELICULA])}
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return bytes(pdf_mod().generar_reporte_pdf_multitabla_mensual(tablas, "07/2026", "Fisico de prueba", maquina="Clinac 600", logo_path=None, temp=True))


class TestPeliculaConRecuadro:
    def test_tamano_en_el_pdf_conserva_la_proporcion_y_cabe_en_el_maximo(self):
        r = recuadro()
        assert (r.ANCHO_MAXIMO_PT, r.ALTO_MAXIMO_PT, r.GROSOR_DEL_RECUADRO_PT) == (ANCHO_MAXIMO_PT, ALTO_MAXIMO_PT, GROSOR_DEL_RECUADRO_PT)
        for ancho_px, alto_px in ((2690, 2710), (5100, 6600), (2000, 9000), (9000, 2000), (100, 100), (3, 5)):
            w, h = r.tamano_en_el_pdf(ancho_px, alto_px)
            assert w <= ANCHO_MAXIMO_PT + 1e-9 and h <= ALTO_MAXIMO_PT + 1e-9
            assert abs(w / h - ancho_px / alto_px) < 1e-9 * max(1, ancho_px / alto_px)
            assert abs(w - ANCHO_MAXIMO_PT) < 1e-9 or abs(h - ALTO_MAXIMO_PT) < 1e-9, "lo mas grande que cabe"

    def test_punto_a_pdf_es_la_unica_conversion_el_centro_del_pixel_en_el_entero_y_el_eje_y_invertido(self):
        r = recuadro()
        u, v = r.punto_a_pdf(0, 0, 100, 50, 200.0, 100.0)
        assert (u, v) == (1.0, 99.0), "el pixel (0, 0) tiene su centro a medio pixel de la esquina superior izquierda: 0.5 px = 1 pt"
        u, v = r.punto_a_pdf(99, 49, 100, 50, 200.0, 100.0)
        assert (u, v) == (199.0, 1.0)
        u, v = r.punto_a_pdf(49.5, 24.5, 100, 50, 200.0, 100.0)
        assert (u, v) == (100.0, 50.0), "el centro de la imagen (49.5, 24.5) en pixeles es el centro del rectangulo"

    def test_es_una_subclase_de_image_de_reportlab_y_no_lee_el_dpi(self):
        r = recuadro()
        assert issubclass(r.PeliculaConRecuadro, RLImage)
        datos, _ = _imagen_png(40, 30)
        flujo = r.PeliculaConRecuadro(datos, ((1, 1), (38, 1), (38, 28), (1, 28)))
        assert tuple(map(tuple, flujo.esquinas)) == ((1, 1), (38, 1), (38, 28), (1, 28))
        assert abs(flujo.drawWidth / flujo.drawHeight - 40 / 30) < 1e-9

    @pytest.mark.parametrize("esquinas", [((10.0, 5.0), (90.0, 5.0), (90.0, 45.0), (10.0, 45.0)), ((10.0, 8.0), (88.0, 3.0), (92.0, 44.0), (12.0, 47.0))])
    def test_los_vertices_dibujados_son_las_esquinas_a_menos_de_una_centesima_de_pixel(self, esquinas):
        """El eje y, el +0.5 y los desplazamientos de la celda, sobre un recuadro alineado (rectangulo) y uno girado (segmentos)."""
        datos, _ = _imagen_png(100, 50)
        pdf = _pdf_con(recuadro().PeliculaConRecuadro(datos, esquinas))
        imagen = imagenes_de(pdf)
        imagen = [i for i in imagen if (i[3], i[4]) == (100, 50)][0]
        vertices, lados, dibujos = _recuadro_dibujado(pdf, imagen)
        assert lados == 4 and len(dibujos) == 1
        assert _error_maximo(_a_pixeles(vertices, imagen), esquinas) < 0.01

    def test_el_recuadro_sigue_el_desplazamiento_de_la_imagen(self):
        """F1-M02: `Image.draw` dibuja la imagen en (`_offs_x`, `_offs_y`) (un gancho de los contenedores que ponen la imagen fuera del origen) y el recuadro tiene que salir del MISMO origen: con la imagen
        corrida, el recuadro corrido igual. (En una celda del generador esos dos valen cero: sin esta prueba la mutacion «sin offsets» seria indistinguible.)"""
        from reportlab.pdfgen import canvas as lienzo_mod
        datos, _ = _imagen_png(100, 50)
        esquinas = ((10.0, 8.0), (88.0, 3.0), (92.0, 44.0), (12.0, 47.0))
        buffer = io.BytesIO()
        lienzo = lienzo_mod.Canvas(buffer, pagesize=(600, 700))
        flujo = recuadro().PeliculaConRecuadro(datos, esquinas)
        flujo.canv = lienzo
        flujo._offs_x, flujo._offs_y = 37.0, 91.0
        flujo.draw()
        lienzo.showPage()
        lienzo.save()
        pdf = buffer.getvalue()
        imagen = imagenes_de(pdf)[0]
        assert abs(imagen[1].x0 - 37.0) < 0.01 and abs(imagen[1].y1 - (700 - 91.0)) < 0.01, imagen[1]
        vertices, lados, _ = _recuadro_dibujado(pdf, imagen)
        assert lados == 4 and _error_maximo(_a_pixeles(vertices, imagen), esquinas) < 0.01

    def test_sobre_una_imagen_opaca_el_recuadro_queda_encima_y_se_ve_y_sin_esquinas_el_render_no_trae_su_color(self):
        """REV-PROD-1 / F1R1-P01, sin base: una imagen gris OPACA (sin ningun pixel del color del recuadro) con cuatro esquinas. El trazo se pinta despues de la imagen y se ve en el render; sin esquinas, las
        MISMAS muestras sobre el MISMO diseno dan cero: el instrumento sabe leer un cero, asi que los cinco por lado miden el trazo y no el fondo."""
        buf = io.BytesIO()
        PILImage.fromarray(np.full((50, 100, 3), 128, np.uint8)).save(buf, format="PNG")
        esquinas = ((10.0, 8.0), (88.0, 3.0), (92.0, 44.0), (12.0, 47.0))
        con = _pdf_con(recuadro().PeliculaConRecuadro(buf.getvalue(), esquinas))
        sin = _pdf_con(recuadro().PeliculaConRecuadro(buf.getvalue(), ()))
        imagen_con = [i for i in imagenes_de(con) if (i[3], i[4]) == (100, 50)][0]
        imagen_sin = [i for i in imagenes_de(sin) if (i[3], i[4]) == (100, 50)][0]
        assert imagen_con[:2] == imagen_sin[:2], "el mismo diseno: la pelicula en el mismo sitio de la misma pagina"
        de_la_imagen, trazos = _indices_de_pintura(con, imagen_con)
        assert len(de_la_imagen) == 1 and trazos and min(trazos) > de_la_imagen[0], (de_la_imagen, trazos)
        lados = _lados_de(_recuadro_dibujado(con, imagen_con)[2])
        assert len(lados) == 4
        assert _muestras_con_el_color(con, imagen_con[0], lados) == [len(MUESTRAS_POR_LADO)] * 4
        assert _muestras_con_el_color(sin, imagen_sin[0], lados) == [0] * 4
        assert _indices_de_pintura(sin, imagen_sin)[1] == [], "sin esquinas no se traza nada sobre la pelicula"

    def test_el_detector_de_texto_sobre_la_pelicula_ve_un_rotulo_y_sin_el_no_ve_nada(self):
        """F1-R2-P02, sin base: el instrumento de `test_ningun_texto_cae_sobre_la_pelicula` sabe leer un texto. La MISMA pelicula con una subclase que escribe un rotulo en el centro del campo da sus palabras
        (`get_drawings()` no las informa); la `PeliculaConRecuadro` de produccion, sobre el mismo diseno, da cero."""
        datos, _ = _imagen_png(100, 50)
        esquinas = ((10.0, 8.0), (88.0, 3.0), (92.0, 44.0), (12.0, 47.0))

        class ConRotulo(recuadro().PeliculaConRecuadro):
            def draw(self):
                super().draw()
                self.canv.setFont("Helvetica", 6)
                self.canv.drawString(self.drawWidth / 2 - 20, self.drawHeight / 2, "Campo luminoso")

        con = _pdf_con(ConRotulo(datos, esquinas))
        sin = _pdf_con(recuadro().PeliculaConRecuadro(datos, esquinas))
        imagen_con = [i for i in imagenes_de(con) if (i[3], i[4]) == (100, 50)][0]
        imagen_sin = [i for i in imagenes_de(sin) if (i[3], i[4]) == (100, 50)][0]
        assert imagen_con[:2] == imagen_sin[:2], "el mismo diseno: la pelicula en el mismo sitio de la misma pagina"
        assert _palabras_sobre_la_pelicula(con, imagen_con) == ["Campo", "luminoso"]
        assert _palabras_sobre_la_pelicula(sin, imagen_sin) == []

    def test_sin_esquinas_la_pelicula_sale_sola(self):
        datos, _ = _imagen_png(100, 50)
        pdf = _pdf_con(recuadro().PeliculaConRecuadro(datos, ()))
        imagen = [i for i in imagenes_de(pdf) if (i[3], i[4]) == (100, 50)][0]
        assert _recuadro_dibujado(pdf, imagen)[1] == 0

    @pytest.mark.parametrize("modo", ["RGB", "RGBA"])
    def test_un_png_se_extrae_igual_a_pillow_en_8_bits(self, modo):
        datos, _ = _imagen_png(120, 80, modo)
        pdf = _pdf_con(recuadro().PeliculaConRecuadro(datos, ((5, 5), (110, 5), (110, 70), (5, 70))))
        referencia = np.array(PILImage.open(io.BytesIO(datos)).convert("RGB"))
        imagen = [i for i in imagenes_de(pdf) if (i[3], i[4]) == (120, 80)][0]
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            pix = fitz.Pixmap(doc, imagen[2])
            arreglo = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        finally:
            doc.close()
        assert not np.any(arreglo[:, :, :3] != referencia)

    @pytest.mark.parametrize("bits", [8, 16])
    def test_un_tiff_de_8_o_16_bits_se_extrae_igual_a_pillow_en_8_bits(self, bits):
        """Un TIFF de 16 bits (A.1 lo admite y P12 lo guarda tal cual) entra al PDF en 8, como lo abre Pillow, que es el lector de reportlab: se compara contra Pillow y no contra `leer_pelicula`."""
        rng = np.random.default_rng(5)
        base = rng.integers(0, 2 ** bits - 1, size=(80, 120, 3), dtype=np.uint16 if bits == 16 else np.uint8)
        import cv2
        ok, codificado = cv2.imencode(".tif", base[:, :, ::-1])
        assert ok
        datos = codificado.tobytes()
        pdf = _pdf_con(recuadro().PeliculaConRecuadro(datos, ((5, 5), (110, 5), (110, 70), (5, 70))))
        referencia = np.array(PILImage.open(io.BytesIO(datos)).convert("RGB"))
        imagen = [i for i in imagenes_de(pdf) if (i[3], i[4]) == (120, 80)][0]
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            pix = fitz.Pixmap(doc, imagen[2])
            arreglo = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        finally:
            doc.close()
        assert not np.any(arreglo[:, :, :3] != referencia)

    def test_una_imagen_de_2000_x_9000_px_no_tumba_el_pdf_y_queda_en_360_pt(self):
        """F1-M14: una fila de mas de 429 pt es un `LayoutError` que tumba el PDF entero; la pelicula se encaja."""
        arreglo = np.full((9000, 2000, 3), 128, dtype=np.uint8)
        buf = io.BytesIO()
        PILImage.fromarray(arreglo).save(buf, format="PNG")
        pdf = _pdf_con(recuadro().PeliculaConRecuadro(buf.getvalue(), ((100, 100), (1900, 100), (1900, 8900), (100, 8900))))
        imagen = [i for i in imagenes_de(pdf) if (i[3], i[4]) == (2000, 9000)][0]
        assert imagen[1].height <= ALTO_MAXIMO_PT + 0.5 and abs(imagen[1].width / imagen[1].height - 2000 / 9000) < 1e-3

    def test_el_color_del_recuadro_es_el_de_la_pestana_1_de_e1_importado(self):
        from reportlab.lib.colors import HexColor
        r = recuadro()
        assert HexColor(dibujo().COLOR_RECUADRO) == r.COLOR_DEL_RECUADRO and abs(r.COLOR_DEL_RECUADRO.red - COLOR_DEL_RECUADRO_RGB[0]) < 1e-9
        assert dibujo().COLOR_RECUADRO.lower() == "#d81b8c", "el color escrito aqui a mano es el de la pestana 1"


# ======================================================================================================================================================== la paginacion

def _pagina_de_la_imagen(pdf, imagen):
    return imagen[0]


def _juntos(pdf, *marcas):
    """True si todas las marcas aparecen en alguna misma pagina."""
    return bool(set.intersection(*(set(paginas_de(pdf, m)) for m in marcas)))


class TestPaginacion:
    """Medida en el generador real: el marco util es de 520 x 435 pt; cada tabla va en `KeepTogether` y el titulo es la cabecera de su tabla."""

    @pytest.mark.parametrize("nombre", ["ML0", "EPSON027"])
    def test_cada_titulo_esta_en_la_pagina_de_su_primera_fila_y_la_pelicula_con_su_leyenda(self, mundo, nombre):
        pdf = mundo.pdf(nombre)
        assert _juntos(pdf, f"{TITULO_DE_LA_SECCION}, capa verde", "Capa reportada capa verde")
        assert _juntos(pdf, "Medidas estadísticas del barrido, capa verde", "Corte central [mm]")
        assert _juntos(pdf, "Perfiles de la capa verde")
        assert _juntos(pdf, TITULO_DE_LA_PELICULA, LEYENDA_DEL_RECUADRO)
        assert _juntos(pdf, TITULO_DE_LOS_PARAMETROS, "Parámetros fijos del método (se guardan")

    @pytest.mark.parametrize("nombre", ["ML0", "EPSON027"])
    def test_la_figura_esta_en_la_pagina_de_su_titulo_y_la_pelicula_en_la_de_su_leyenda(self, mundo, nombre):
        pdf = mundo.pdf(nombre)
        figura = [i for i in imagenes_de(pdf) if abs(i[1].width - 384) < 1 and abs(i[1].height - 340) < 1]
        assert len(figura) == 1 and figura[0][0] in paginas_de(pdf, "Perfiles de la capa verde")
        tamano = PILImage.open(io.BytesIO(mundo.datos[nombre])).size
        pelicula = _la_pelicula(pdf, tamano)
        assert pelicula[0] in paginas_de(pdf, TITULO_DE_LA_PELICULA) and pelicula[0] in paginas_de(pdf, LEYENDA_DEL_RECUADRO)

    @pytest.mark.parametrize("nombre", ["ML0", "EPSON027"])
    def test_la_seccion_ocupa_el_numero_de_paginas_medido(self, mundo, nombre):
        """Medido en el mundo de estas pruebas (`logs/F1/corrector_ronda2/medida_paginas.log` del anexo): la seccion va de la pagina 4 a la 8 en las cuatro peliculas, UNA tabla por pagina (el barrido no cabe
        junto a los valores, ni los perfiles junto al barrido, ni la pelicula junto a los perfiles): cinco paginas. Una regresion de paginacion que sume una pagina cae. (Las 3 o 4 paginas del informe son el
        crecimiento neto del PDF, que cambia las dos tablas viejas por esta seccion; no es esta medida.)"""
        pdf = mundo.pdf(nombre)
        assert paginas_de(pdf, TITULO_DE_LA_SECCION) and paginas_de(pdf, TITULO_DE_LOS_PARAMETROS), "el PDF trae la seccion nueva"
        primera = min(paginas_de(pdf, TITULO_DE_LA_SECCION))
        ultima = max(paginas_de(pdf, TITULO_DE_LOS_PARAMETROS))
        assert ultima - primera + 1 <= 5, f"la seccion va de la pagina {primera} a la {ultima}"

    def test_las_tablas_de_la_seccion_siguen_el_orden_de_las_claves(self, mundo):
        pdf = mundo.pdf("ML0")
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            posiciones = []
            for marca in (f"{TITULO_DE_LA_SECCION}, capa verde", "Medidas estadísticas del barrido", "Perfiles de la capa verde", TITULO_DE_LA_PELICULA, TITULO_DE_LOS_PARAMETROS):
                for p in doc:
                    r = p.search_for(marca)
                    if r:
                        posiciones.append((p.number, r[0].y0))
                        break
        finally:
            doc.close()
        assert len(posiciones) == 5 and posiciones == sorted(posiciones), posiciones


# ======================================================================================================================================================== los guardias

def _importados(ruta):
    arbol = ast.parse(_fuente(ruta))
    modulos = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            modulos.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            modulos.add(n.module)
            modulos.update(f"{n.module}.{a.name}" for a in n.names)
    return modulos


def _constantes_de_texto(ruta):
    arbol = ast.parse(_fuente(ruta))
    docstrings = {id(n.value) for n in ast.walk(arbol) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    return [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


def _orden_de_600_y_ix():
    """El `orden_tablas` del 600 y del iX de `generar_reporte_pdf_multitabla_mensual` (la lista que trae 'analisis_imagen'), leida por AST."""
    arbol = ast.parse(_fuente(PDF_PY))
    funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "generar_reporte_pdf_multitabla_mensual")
    listas = [ast.literal_eval(n.value) for n in ast.walk(funcion) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "orden_tablas" for t in n.targets)
              and isinstance(n.value, ast.List)]
    return next(l for l in listas if "analisis_imagen" in l and "tamanos_campo" in l and "dosimetricos" in l)


def _lista_de_estilos_de_analisis_imagen():
    """La lista de nombres del `elif nombre_tabla in [...]` de `generar_reporte_pdf_multitabla_mensual` donde esta 'analisis_imagen' (la de los estilos con SPAN y la fila 1 resaltada)."""
    arbol = ast.parse(_fuente(PDF_PY))
    funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "generar_reporte_pdf_multitabla_mensual")
    for n in ast.walk(funcion):
        if isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.In) and isinstance(n.comparators[0], ast.List):
            lista = [e.value for e in n.comparators[0].elts if isinstance(e, ast.Constant)]
            if "analisis_imagen" in lista and "seguridad_cunas" in lista:
                return lista
    raise AssertionError("no se encontro la lista de estilos con SPAN de 'analisis_imagen'")


class TestLosGuardias:
    def test_las_claves_de_la_seccion_son_las_cinco_y_en_ese_orden(self):
        assert tuple(seccion().CLAVES) == CLAVES_DE_LA_SECCION

    def test_las_claves_estan_en_orden_tablas_de_600_y_ix_en_orden_entre_los_tamanos_de_campo_y_la_imagen(self):
        """F1-M10: una clave producida y no listada no se imprime (el bucle salta lo que no esta en `orden_tablas`)."""
        orden = _orden_de_600_y_ix()
        i = orden.index("tamanos_campo")
        assert orden[i + 1:i + 1 + len(CLAVES_DE_LA_SECCION)] == list(seccion().CLAVES)
        assert orden[i + 1 + len(CLAVES_DE_LA_SECCION):] == ["imagen", "analisis_imagen", "dosimetricos"], "las dos tablas de siempre detras, en su orden"

    def test_las_tablas_de_texto_estan_en_la_lista_de_estilos_con_span_para_que_el_titulo_abarque_la_tabla(self):
        lista = _lista_de_estilos_de_analisis_imagen()
        for clave in ("placa_mensual_valores", "placa_mensual_barrido", "placa_mensual_parametros"):
            assert clave in lista, clave
        for clave in ("placa_mensual_perfiles", "placa_mensual_pelicula"):
            assert clave not in lista, f"{clave} es una figura: su fila 1 no se resalta"

    def test_pdf_py_no_gana_letra_ni_estilos_nuevos(self):
        texto = _fuente(PDF_PY)
        assert texto.count("CABECERA_TABLA_PT)") == 5 and texto.count("CUERPO_TABLA_PT)") == 4 and texto.count("ParagraphStyle(") == 2

    @pytest.mark.parametrize("ruta", [*LOS_DOS_MODULOS, MENSUALES_PY, PDF_PY])
    def test_ninguna_capa_escrita_a_mano(self, ruta):
        """La capa sale del registro y de `pelicula.CAPAS`: ni «G», ni «verde», ni `_g_`, ni las otras dos (incluidos los modulos nuevos)."""
        assert capas_escritas_a_mano(_fuente(ruta)) == [], f"{ruta} escribe una capa a mano"

    @pytest.mark.parametrize("ruta", [*LOS_DOS_MODULOS, MENSUALES_PY, PDF_PY])
    def test_ningun_pdf_lee_la_capa_por_omision(self, ruta):
        assert lee_capa_por_omision(_fuente(ruta)) == [], f"{ruta} lee CAPA_POR_OMISION"

    @pytest.mark.parametrize("ruta", LOS_DOS_MODULOS)
    def test_los_modulos_nuevos_estan_en_la_lista_de_b6_de_donde_no_se_elige_la_capa_a_mano(self, ruta):
        import test_b6_pdf_capa_reportada_braqui as b6
        assert ruta in b6.DONDE_NO_SE_ELIGE_LA_CAPA_A_MANO

    @pytest.mark.parametrize("ruta", LOS_DOS_MODULOS)
    def test_no_importan_qt_ni_pyplot_ni_llaman_matplotlib_use(self, ruta):
        malos = {m for m in _importados(ruta) if m.startswith(("PyQt", "PySide")) or m in ("matplotlib.pyplot", "pyplot")}
        assert not malos, malos
        assert not [n for n in ast.walk(ast.parse(_fuente(ruta))) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "use"], "matplotlib.use"

    def test_el_modulo_de_la_pelicula_no_trae_el_motor_ni_el_servicio(self):
        malos = {m for m in _importados(PELICULA_PY) if m.startswith(("analisisImagenes.placa_mensual", "services", "ui.", "data."))}
        assert not malos, malos

    @pytest.mark.parametrize("ruta", LOS_DOS_MODULOS)
    def test_no_leen_el_dpi_ni_nombran_el_piso_de_a3(self, ruta):
        texto = _fuente(ruta)
        assert re.search(r"\binfo\b\s*\[\s*['\"]dpi", texto) is None and "resolucion_declarada" not in texto and ".dpi" not in texto, "PI.10 cuenta los lectores de la resolucion declarada"
        for nombre in ("piso_de_pelicula", "piso_de_pelicula_virgen", "guardar_referencia_virgen", "leer_referencia_virgen", "MODO_DEL_PISO_POR_OMISION"):
            assert nombre not in texto, f"{ruta} nombra {nombre} (test_a3::test_k busca por TEXTO, tambien en un comentario)"

    @pytest.mark.parametrize("ruta", [*LOS_DOS_MODULOS, MENSUALES_PY])
    def test_ningun_sql_nombra_la_tabla_del_analisis_nuevo_fuera_del_servicio(self, ruta):
        for texto in _constantes_de_texto(ruta):
            if "analisis_placa_mensual" in texto:
                assert not re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM)\b", texto, re.IGNORECASE), f"{ruta}: SQL sobre la tabla del analisis nuevo: {texto[:80]!r}"

    @pytest.mark.parametrize("ruta", LOS_DOS_MODULOS)
    def test_sin_veredicto_ni_simbolos_ni_unidades_entre_parentesis(self, ruta):
        for texto in _constantes_de_texto(ruta):
            assert not re.search(r"\bno cumple\b|\bcumple\b", texto, re.IGNORECASE), f"un veredicto: {texto[:60]!r}"
            assert not any(s in texto for s in SIMBOLOS_DA18), f"un simbolo de DA-18: {texto[:60]!r}"
            assert not re.search(r"(?<=\s)\((mm|cm|%|px|dpi|nivel|niveles)\)", texto), f"una unidad entre parentesis: {texto[:60]!r}"

    def test_procesar_datos_para_reporte_no_lee_el_analisis_nuevo(self):
        """F1-M04: para 600/iX es una funcion pura que `test_t5_cunas_en_pdf_ix` llama sin base ni `ref_id`; la lectura va en la fase de datos."""
        fuente = inspect.getsource(rm()._procesar_datos_para_reporte)
        assert "svc" not in fuente and ".leer(" not in fuente and "placa_mensual" not in fuente.replace("_secciones_de_la_placa", "")

    def test_la_lectura_esta_en_el_return_de_recopilar_datos_completos(self):
        fuente = inspect.getsource(rm()._recopilar_datos_completos)
        assert fuente.rstrip().endswith("return _con_el_analisis_nuevo(datos_completos)")

    def test_el_codigo_nuevo_de_reportes_mensuales_va_al_final_del_archivo(self):
        """Cero citas por linea movidas (Trampa 5): lo nuevo se agrega AL FINAL; las tres ediciones de adentro cambian lineas, no las insertan."""
        arbol = ast.parse(_fuente(MENSUALES_PY))
        nombres = [n.name if isinstance(n, ast.FunctionDef) else next((t.id for t in n.targets if isinstance(t, ast.Name)), "") for n in arbol.body if isinstance(n, (ast.FunctionDef, ast.Assign))]
        assert nombres[-3:] == ["CLAVE_DEL_ANALISIS_NUEVO", "_con_el_analisis_nuevo", "_secciones_de_la_placa"], nombres[-4:]

    def test_los_modulos_nuevos_no_importan_el_motor_de_otra_forma_que_por_su_nombre_publico(self):
        """La seccion usa el motor solo para `VERSION_ALGORITMO`, `recuadro_luminoso`, `barrido` y `EJES` (la API de las pistas)."""
        arbol = ast.parse(_fuente(SECCION_PY))
        usados = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "motor"}
        assert usados <= {"VERSION_ALGORITMO", "recuadro_luminoso", "barrido", "EJES"}, usados
