"""AJ.6-1: el PDF del Catphan, mensual y anual, pone cada prueba en su pagina, con sus imagenes de su forma, al ancho util, sin bordes blancos y sin salirse del margen.
Datos reales: una COPIA de los tres archivos de la copia 23-11 (Tomografo 01/10/2026, 01/2026 vertical y 28/09/2026 con pruebas sin imagenes, Halcyon 06/2026, iX 05/2026); el anual, con la seccion de imagenes de una sesion real.
Y otra COPIA con la imagen original del espesor del 01/10/2026 ilegible (un dato danado): el PDF sale y la imagen del analisis queda en su columna."""
import ast
import importlib
import io
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image as ImagenPIL  # noqa: E402
from PyQt5.QtSql import QSqlDatabase  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

import data.ManejoDatos.conection as conection_mod  # noqa: E402
import models.PDF.Anual.reportes_anuales as rep_anual  # noqa: E402
import models.PDF.Imagenes.reportes_control_sistema_imagenes as rep_mod  # noqa: E402
import models.PDF.pdf as pdf_mod  # noqa: E402
from _bd_referencia import BD_REBUILD_23_11  # noqa: E402
from _informe_imagenes import FalsoVisor, Padre  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
MARCO = (40.0, 245.0, 572.0, 692.0)  # margenes de la pagina carta [pt]
ANCHO_UTIL = 520.0  # 612 - 40 - 40 - 2 x 6 del marco [pt]
ALTO_UTIL = 435.0  # 792 - 245 - 100 - 2 x 6 [pt]
TITULOS = {"Espesor de corte": "espesor", "Tamaño de pixel": "tamano_pixel", "Resolución de contraste": "resolucion_contraste",
           "Resolución espacial": "resolucion_espacial", "Valores CT": "valores_ct", "Linealidad CT": "linealidad_ct",
           "Uniformidad y ruido": "uniformidad", "Uniformidad": "uniformidad"}
MENSUALES = [(48, "Tomógrafo", "01/10/2026"), (8, "Tomógrafo", "01/2026"), (34, "Halcyon", "06/2026"), (30, "Clinac ix", "05/2026"), (49, "Tomógrafo", "28/09/2026")]
ANUALES = [(48, "Halcyon"), (30, "Clinac ix"), (49, "Halcyon")]  # 49: tres pruebas sin imagenes, cortas, que cabrian juntas
ILEGIBLES = [("mensual_48_original_ilegible", (48, "Tomógrafo", "01/10/2026")), ("anual_48_original_ilegible", (48, "Halcyon"))]
AZUL_DE_CABECERA = (0x01 / 255, 0xb0 / 255, 0xca / 255)  # el fondo del encabezado de las tablas de los dos generadores


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _maqueta():
    try:
        return importlib.import_module("models.PDF.Imagenes.maqueta_catphan")
    except ImportError as e:
        pytest.fail(f"no existe la maqueta del PDF del Catphan: {e}")


def _copia(tmp):
    for sufijo in ("", "-wal", "-shm"):
        origen = Path(str(BD_REBUILD_23_11) + sufijo)
        if origen.exists():
            shutil.copy2(origen, tmp / (BD_REBUILD_23_11.name + sufijo))
    return str(tmp / BD_REBUILD_23_11.name)


def _con_la_original_ilegible(ruta):
    """La copia con la imagen original del espesor de la sesion 48 cambiada por bytes que no son una imagen."""
    con = sqlite3.connect(ruta)
    try:
        n = con.execute("UPDATE pruebas SET imagen_path = ? WHERE id_sesion = 48 AND id_tipo = 1 AND (activo IS NULL OR activo = 1)", (b"no es una imagen",)).rowcount
        con.commit()
    finally:
        con.close()
    assert n == 1, n
    return ruta


@pytest.fixture(scope="module")
def pdfs(app, tmp_path_factory):
    """Los PDF reales, sobre una copia de los tres archivos y otra con la original ilegible, con todo QMessageBox parchado (Trampa 2) y el visor sustituido."""
    if not BD_REBUILD_23_11.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_23_11.name}")
    salida = {}
    sana = _copia(tmp_path_factory.mktemp("copia_23_11"))  # una sola copia por base: generar un PDF solo lee
    danada = _con_la_original_ilegible(_copia(tmp_path_factory.mktemp("copia_danada")))
    trabajos = [(f"mensual_{r}", (r, e, f), sana) for r, e, f in MENSUALES] + [(f"anual_{r}", (r, m), sana) for r, m in ANUALES] + [(c, h, danada) for c, h in ILEGIBLES]
    with pytest.MonkeyPatch.context() as mp:
        for nombre in ("critical", "warning", "information", "question"):
            mp.setattr(QMessageBox, nombre, staticmethod(lambda *a, **k: QMessageBox.Ok))
        mp.setattr(rep_mod, "PdfViewer", FalsoVisor)
        anterior = None
        for clave, hacer, ruta in trabajos:
            if ruta != anterior and QSqlDatabase.contains("qt_sql_default_connection"):  # la de Padre apunta a otra base
                QSqlDatabase.database("qt_sql_default_connection").close()
                QSqlDatabase.removeDatabase("qt_sql_default_connection")
            anterior = ruta
            mp.setattr(conection_mod, "ruta_base_datos", lambda ruta=ruta: ruta)
            conection_mod.Conexion._instance = None
            conection_mod.Conexion()
            if clave.startswith("mensual"):
                FalsoVisor.ultimo = {}
                assert rep_mod.generar_reporte_sistema_imagenes(Padre(ruta), hacer[2], hacer[1], "x", ref=hacer[0], sistema_imagenes=True)
                salida[clave] = FalsoVisor.ultimo["pdf"]
            else:
                tablas = rep_anual.obtener_tablas_sistema_imagenes_y_motivo(Padre(ruta).opeenDatabase(), hacer[0]).tablas
                tablas = {"equipos": __import__("pandas").DataFrame({"Tipo de equipo": ["Cámara"], "Modelo": ["X"], "Serie": ["1"], "Factor": ["1.0"]}),
                          pdf_mod.CLAVE_TITULO_IMAGENES: rep_mod.titulo_del_informe(), **tablas}
                pdf = pdf_mod.generar_reporte_pdf_multitabla_anual(tablas_dict=tablas, fecha="2026", user="Físico", tipo_reporte="Anual",
                                                                   maquina=hacer[1], id_maquina=hacer[1], temp=True)
                salida[clave] = bytes(pdf.data())
            conection_mod.Conexion._instance.con.close()
            conection_mod.Conexion._instance = None
    return salida


def _lineas(pagina):
    for b in pagina.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            yield "".join(s["text"] for s in l["spans"]).strip(), l["bbox"]


def pruebas_de(pagina):
    """Las pruebas con tablas en la pagina: el titulo centrado de sus resultados o de sus imagenes, o el que sigue a «Imagen original» (el anual no lo centra)."""
    vistas, despues_de_imagen = [], False
    for texto, (x0, y0, x1, _) in _lineas(pagina):
        if not MARCO[1] <= y0 <= MARCO[3]:
            continue
        if texto in TITULOS and (abs((x0 + x1) / 2 - 306) < 3 or despues_de_imagen):
            vistas.append(TITULOS[texto])
        despues_de_imagen = texto == "Imagen original" or (despues_de_imagen and texto == "Imagen del análisis")
    return vistas


def imagenes_de(doc, pagina):
    """(rectangulo, ancho y alto en pixeles, pixeles) de cada imagen dentro del marco (el logo y las firmas van fuera)."""
    salida = []
    for info in pagina.get_image_info(xrefs=True):
        x0, y0, x1, y1 = info["bbox"]
        if MARCO[1] < (y0 + y1) / 2 < MARCO[3]:
            pix = np.asarray(ImagenPIL.open(io.BytesIO(doc.extract_image(info["xref"])["image"])).convert("RGB"))
            salida.append((fitz.Rect(info["bbox"]), (info["width"], info["height"]), pix))
    return salida


def paginas_de_pruebas(pdf):
    doc = fitz.open(stream=pdf, filetype="pdf")
    por_pagina = [(i, pruebas_de(p), imagenes_de(doc, p)) for i, p in enumerate(doc)]
    primera = next(i for i, vistas, _ in por_pagina if vistas)
    return doc, por_pagina[primera:]


CASOS = [f"mensual_{r}" for r, _, _ in MENSUALES] + [f"anual_{r}" for r, _ in ANUALES] + [c for c, _ in ILEGIBLES]


# 1. UNA PRUEBA POR PAGINA

@pytest.mark.parametrize("clave", CASOS)
def test_cada_pagina_desde_la_primera_prueba_trae_una_sola_prueba(pdfs, clave):
    _, paginas = paginas_de_pruebas(pdfs[clave])
    mezcladas = [(i, sorted(set(v))) for i, v, _ in paginas if len(set(v)) > 1]
    assert not mezcladas, f"{clave}: paginas con dos pruebas {mezcladas}"


@pytest.mark.parametrize("clave", CASOS)
def test_ninguna_pagina_queda_en_blanco(pdfs, clave):
    doc = fitz.open(stream=pdfs[clave], filetype="pdf")
    vacias = [i for i, p in enumerate(doc) if not [w for w in p.get_text("words") if MARCO[1] <= w[1] <= MARCO[3]]]
    assert not vacias, f"{clave}: paginas sin nada en el marco {vacias}"


@pytest.mark.parametrize("clave", CASOS)
def test_cada_prueba_empieza_arriba_de_su_pagina(pdfs, clave):
    doc, paginas = paginas_de_pruebas(pdfs[clave])
    empezadas = set()
    for i, vistas, _ in paginas:
        for prueba in set(vistas) - empezadas:
            arriba = min((caja[1], texto) for texto, caja in _lineas(doc[i]) if texto and MARCO[1] <= caja[1] <= MARCO[3])[1]
            assert TITULOS.get(arriba) == prueba, f"{clave} p{i}: encima de {prueba} hay otra cosa: {arriba!r}"
        empezadas |= set(vistas)
    assert empezadas, clave


def test_las_pruebas_cortas_sin_imagenes_del_28_09_2026_van_cada_una_en_su_pagina(pdfs):
    _, paginas = paginas_de_pruebas(pdfs["mensual_49"])
    primeras = [v[0] for _, v, _ in paginas if v]
    assert primeras[:3] == ["espesor", "tamano_pixel", "resolucion_contraste"], primeras


@pytest.mark.parametrize("clave", CASOS)
def test_cada_prueba_empieza_pagina_y_sus_imagenes_van_con_ella_o_en_la_siguiente(pdfs, clave):
    _, paginas = paginas_de_pruebas(pdfs[clave])
    orden = []
    for i, vistas, imagenes in paginas:
        prueba = vistas[0] if vistas else (orden[-1][1] if orden else None)
        orden.append((i, prueba, len(imagenes)))
    primeras = {}
    for i, prueba, _ in orden:
        primeras.setdefault(prueba, i)
    assert len(primeras) == len({p for _, p, _ in orden}) and list(primeras) == sorted(primeras, key=primeras.get)
    for i, prueba, n in orden:
        if n:
            assert prueba in primeras and i - primeras[prueba] <= 2, f"{clave}: imagenes de {prueba} en la pagina {i}"


def test_el_tomografo_del_01_10_2026_pone_las_siete_pruebas_con_sus_imagenes(pdfs):
    _, paginas = paginas_de_pruebas(pdfs["mensual_48"])
    con_imagenes = {v[0] for _, v, im in paginas if im and v}
    assert len([1 for _, _, im in paginas for _ in im]) == 14 and len(con_imagenes | {"resolucion_espacial"}) == 7


def test_en_el_01_10_2026_espesor_tamano_de_pixel_y_linealidad_comparten_pagina_con_sus_resultados(pdfs):
    _, paginas = paginas_de_pruebas(pdfs["mensual_48"])
    juntas = {v[0] for _, v, im in paginas if im and v and v.count(v[0]) == 2}
    assert juntas >= {"espesor", "tamano_pixel", "linealidad_ct"}, juntas


def test_la_primera_pagina_lleva_los_parametros_como_hoy(pdfs):
    doc = fitz.open(stream=pdfs["mensual_48"], filetype="pdf")
    assert "Parámetros de adquisición" in doc[0].get_text() and not pruebas_de(doc[0])


# 2. LAS IMAGENES CON SU FORMA, AL ANCHO UTIL Y DENTRO DEL MARGEN

@pytest.mark.parametrize("clave", CASOS)
def test_cada_imagen_conserva_su_forma(pdfs, clave):
    doc, paginas = paginas_de_pruebas(pdfs[clave])
    for i, _, imagenes in paginas:
        for rect, (w, h), _ in imagenes:
            assert abs((rect.width / rect.height) / (w / h) - 1) < 0.005, f"{clave} p{i}: {w}x{h} en {rect.width:.1f}x{rect.height:.1f}"


@pytest.mark.parametrize("clave", CASOS)
def test_ninguna_imagen_sale_del_margen(pdfs, clave):
    doc, paginas = paginas_de_pruebas(pdfs[clave])
    for i, _, imagenes in paginas:
        for rect, _, _ in imagenes:
            assert rect.x0 >= MARCO[0] - 0.5 and rect.x1 <= MARCO[2] + 0.5 and rect.y0 >= MARCO[1] - 0.5 and rect.y1 <= MARCO[3] + 0.5, f"{clave} p{i}: {rect}"


@pytest.mark.parametrize("clave", CASOS)
def test_las_dos_de_una_fila_van_a_la_misma_altura_y_llenan_el_ancho_o_comparten_lo_que_deja_su_tabla(pdfs, clave):
    doc, paginas = paginas_de_pruebas(pdfs[clave])
    filas = 0
    for i, _, imagenes in paginas:
        if len(imagenes) != 2:
            continue
        (a, _, _), (b, _, _) = imagenes
        filas += 1
        assert abs(a.y0 - b.y0) < 0.5 and abs(a.height - b.height) < 0.5, f"{clave} p{i}: {a} {b}"
        llena_el_ancho = abs(a.width + b.width - ANCHO_UTIL) <= 2
        comparte_lo_que_queda = a.height >= 180 - 0.5 and a.y1 >= MARCO[3] - 6 - 3  # achicadas solo para caber con su tabla: llegan al pie del marco
        assert llena_el_ancho or comparte_lo_que_queda, f"{clave} p{i}: ancho {a.width + b.width:.1f}, alto {a.height:.1f}, pie {a.y1:.1f}"
        assert abs((a.x0 + b.x1) / 2 - 306) < 1, f"{clave} p{i}: la fila no va centrada"
    assert filas >= 1


@pytest.mark.parametrize("clave", [c for c, _ in ILEGIBLES])
def test_con_la_imagen_original_ilegible_el_pdf_sale_y_la_del_analisis_llena_su_columna(pdfs, clave):
    _, paginas = paginas_de_pruebas(pdfs[clave])
    del_espesor = [im for _, v, im in paginas if "espesor" in v and im]
    assert len(del_espesor) == 1 and len(del_espesor[0]) == 1, del_espesor
    r, (w, h), _ = del_espesor[0][0]
    assert abs(r.x0 - 306) < 0.5 and abs(r.width - ANCHO_UTIL / 2) < 0.5 and abs((r.width / r.height) / (w / h) - 1) < 0.005, r
    assert sum(len(im) for _, _, im in paginas) == 13, "solo falta la original del espesor"


@pytest.mark.parametrize("clave", CASOS)
def test_ninguna_imagen_conserva_un_borde_blanco_uniforme(pdfs, clave):
    doc, paginas = paginas_de_pruebas(pdfs[clave])
    for i, _, imagenes in paginas:
        for _, _, pix in imagenes:
            blancas = np.all(pix == 255, axis=-1)
            for borde in (blancas[:3, :], blancas[-3:, :], blancas[:, :3].T, blancas[:, -3:].T):
                assert not borde.all(), f"{clave} p{i}: borde blanco de mas de 2 px"


def test_una_imagen_de_forma_1_65_no_se_dibuja_en_un_cuadrado(pdfs):
    doc, paginas = paginas_de_pruebas(pdfs["mensual_48"])
    anchas = [rect for _, _, im in paginas for rect, (w, h), _ in im if w / h > 1.4]
    assert anchas and all(r.width / r.height > 1.4 for r in anchas)


@pytest.mark.parametrize("clave", CASOS)
def test_cada_tabla_de_imagenes_lleva_su_encabezado_azul_su_reticula_y_los_titulos_de_hoy(pdfs, clave):
    doc, paginas = paginas_de_pruebas(pdfs[clave])
    tablas = 0
    for i, _, imagenes in paginas:
        dibujos = doc[i].get_drawings()
        azules = [d["rect"] for d in dibujos if d.get("fill") and max(abs(a - b) for a, b in zip(d["fill"], AZUL_DE_CABECERA)) < 0.01]
        rayas = [d["rect"] for d in dibujos if d.get("color") == (0.0, 0.0, 0.0)]
        for r, _, _ in imagenes:
            for x in (r.x0, r.x1):
                assert any(abs(v.x0 - x) < 0.6 and v.width < 0.1 and v.y0 <= r.y0 + 0.6 and v.y1 >= r.y1 - 0.6 for v in rayas), f"{clave} p{i}: sin raya a un lado de {r}"
            assert any(abs(h.y0 - r.y1) < 0.6 and h.height < 0.1 and h.x0 <= r.x0 + 0.6 and h.x1 >= r.x1 - 0.6 for h in rayas), f"{clave} p{i}: sin raya bajo {r}"
            assert any(0 <= r.y0 - a.y1 <= 24 and a.x0 <= r.x0 + 0.6 and a.x1 >= r.x1 - 0.6 for a in azules), f"{clave} p{i}: sin encabezado azul sobre {r}"
        filas = len({round(r.y0) for r, _, _ in imagenes})  # cada tabla de imagenes de estos informes es una sola fila
        texto = doc[i].get_text(clip=fitz.Rect(*MARCO))
        esperados = (filas, filas if clave.startswith("mensual") else 0)  # como hoy: el anual funde su encabezado y no dice «Imagen del análisis»
        assert (texto.count("Imagen original"), texto.count("Imagen del análisis")) == esperados, f"{clave} p{i}: {texto!r}"
        tablas += filas
    assert tablas, clave


# 3. LA MAQUETA, CON IMAGENES SINTETICAS DE VERDAD CONOCIDA

def _png(tmp_path, nombre, w, h, modo="RGB", borde=0, color=(0, 0, 0)):
    lienzo = ImagenPIL.new("RGB", (w + 2 * borde, h + 2 * borde), (255, 255, 255))
    lienzo.paste(ImagenPIL.new("RGB", (w, h), color), (borde, borde))
    imagen = lienzo.convert(modo) if modo != "RGB" else lienzo
    ruta = tmp_path / nombre
    imagen.save(ruta)
    return str(ruta)


def _pdf_con(tabla, antes_pt=0):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Spacer
    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=245, bottomMargin=100)
    doc.build(([Spacer(1, antes_pt)] if antes_pt else []) + [tabla])
    return fitz.open(stream=salida.getvalue(), filetype="pdf")


def _datos(rutas, titulo="Prueba"):
    """Como lo arman los dos generadores: las cabeceras son parrafos, que se parten al angostarse su columna."""
    return [[_celda("Imagen original"), _celda("Imagen del análisis")], [_celda(titulo), _celda()], list(rutas)]


def test_el_ancho_y_el_alto_util_son_los_del_marco_de_los_dos_generadores():
    m = _maqueta()
    assert (m.ANCHO_UTIL_PT, m.ALTO_UTIL_PT) == (ANCHO_UTIL, ALTO_UTIL)
    assert [x for par in m.PRUEBAS for x in par] == pdf_mod.TABLAS_INFORME_IMAGENES[2:]


def test_el_recorte_quita_solo_el_blanco_uniforme_y_nunca_un_pixel_de_otro_color():
    m = _maqueta()
    base = np.full((60, 80, 3), 255, np.uint8)
    base[10:50, 20:70] = 0
    assert m.recortar_margen_blanco(ImagenPIL.fromarray(base)).size == (50, 40)
    base[0, 0] = (254, 255, 255)
    assert m.recortar_margen_blanco(ImagenPIL.fromarray(base)).size == (70, 50)
    blanca = ImagenPIL.new("RGB", (30, 20), (255, 255, 255))
    assert m.recortar_margen_blanco(blanca).size == (30, 20)


@pytest.mark.parametrize("modo", ["RGBA", "P", "L", "LA"])
def test_el_recorte_admite_paleta_y_transparencia(tmp_path, modo):
    m = _maqueta()
    datos, tam = m.imagen_preparada(_png(tmp_path, f"x_{modo}.png", 40, 30, modo, borde=7))
    assert tam == (40, 30) and datos.startswith(b"\x89PNG")
    transparente = ImagenPIL.new("RGBA", (50, 50), (0, 0, 0, 0))
    transparente.paste(ImagenPIL.new("RGBA", (10, 20), (200, 0, 0, 255)), (5, 5))
    assert m.recortar_margen_blanco(transparente).size == (10, 20)


@pytest.mark.parametrize("alfa", [1, 128, 254])
def test_el_recorte_no_quita_un_pixel_semitransparente_que_no_es_blanco(alfa):
    m = _maqueta()
    imagen = ImagenPIL.new("RGBA", (50, 50), (0, 0, 0, 0))
    imagen.paste(ImagenPIL.new("RGBA", (10, 20), (200, 0, 0, 255)), (5, 5))
    imagen.putpixel((40, 45), (128, 128, 128, alfa))  # un gris apenas visible fuera del resto: es contenido
    recortada = m.recortar_margen_blanco(imagen)
    assert recortada.size == (36, 41) and recortada.getpixel((35, 40)) == (128, 128, 128, alfa), recortada.size


def test_la_regla_de_la_fila_misma_altura_anchos_proporcionales_y_apiladas_por_debajo_de_150_pt():
    m = _maqueta()
    apiladas, medidas = m.tamanos_de_fila([(512, 512), (1323, 802)])
    assert not apiladas and abs(medidas[0][1] - medidas[1][1]) < 1e-9 and abs(sum(w for w, _ in medidas) - ANCHO_UTIL) < 1e-9
    assert abs(medidas[1][0] / medidas[1][1] - 1323 / 802) < 1e-9
    apiladas, medidas = m.tamanos_de_fila([(512, 512), (2000, 500)])
    assert apiladas and all(abs(w - ANCHO_UTIL) < 1e-9 for w, _ in medidas)
    assert not m.tamanos_de_fila([(100, 100), (246, 100)])[0] and m.tamanos_de_fila([(100, 100), (247, 100)])[0]


def test_dos_imagenes_muy_altas_no_pasan_del_alto_de_una_pagina(tmp_path):
    m = _maqueta()
    tabla = m.TablaDeImagenes(_datos([_png(tmp_path, "a.png", 100, 400), _png(tmp_path, "b.png", 100, 400)]), [])
    doc = _pdf_con(tabla)
    rects = [fitz.Rect(i["bbox"]) for i in doc[0].get_image_info()]
    assert doc.page_count == 1 and len(rects) == 2 and all(r.y1 <= MARCO[3] + 0.5 and abs(r.width / r.height - 0.25) < 0.001 for r in rects)


def test_apiladas_cada_una_al_ancho_util_y_con_su_forma(tmp_path):
    m = _maqueta()
    doc = _pdf_con(m.TablaDeImagenes(_datos([_png(tmp_path, "a.png", 300, 300), _png(tmp_path, "b.png", 900, 300)]), []))
    rects = sorted((fitz.Rect(i["bbox"]) for i in doc[0].get_image_info()), key=lambda r: r.y0)
    assert len(rects) == 2 and rects[0].y1 <= rects[1].y0 + 0.5
    assert doc.page_count == 1 and abs(rects[0].width - rects[1].width) < 0.5 and rects[0].width <= ANCHO_UTIL + 0.5
    assert abs(rects[1].width / rects[1].height - 3) < 0.005 and abs(rects[0].width / rects[0].height - 1) < 0.005
    assert abs(rects[1].y1 - (MARCO[3] - 6)) <= 2, rects  # no caben a todo el ancho: se achican lo justo y llegan al pie del marco
    doc = _pdf_con(m.TablaDeImagenes(_datos([_png(tmp_path, "c.png", 1000, 250), _png(tmp_path, "d.png", 1500, 250)]), []))
    rects = sorted((fitz.Rect(i["bbox"]) for i in doc[0].get_image_info()), key=lambda r: r.y0)
    assert doc.page_count == 1 and len(rects) == 2 and rects[0].y1 <= rects[1].y0 + 0.5 and all(abs(r.width - ANCHO_UTIL) < 0.5 for r in rects), rects  # si caben, a todo el ancho


def test_con_sitio_para_180_pt_comparte_la_pagina_y_si_no_pasa_entera_a_la_siguiente(tmp_path):
    m = _maqueta()
    rutas = [_png(tmp_path, "a.png", 200, 200), _png(tmp_path, "b.png", 200, 200)]
    junto = _pdf_con(m.TablaDeImagenes(_datos(rutas), []), antes_pt=140)
    assert junto.page_count == 1
    alto = [fitz.Rect(i["bbox"]) for i in junto[0].get_image_info()][0].height
    assert 180 <= alto < 260
    aparte = _pdf_con(m.TablaDeImagenes(_datos(rutas), []), antes_pt=260)
    assert aparte.page_count == 2 and not aparte[0].get_image_info()
    assert abs(sum(fitz.Rect(i["bbox"]).width for i in aparte[1].get_image_info()) - ANCHO_UTIL) <= 2


def test_una_tabla_de_resultados_mas_alta_que_el_marco_tras_una_pagina_llena_no_deja_una_en_blanco():
    m = _maqueta()
    from reportlab.platypus import Spacer, Table
    alta = Table([[f"fila {i}"] for i in range(60)])
    elementos = [Spacer(1, ALTO_UTIL - 2), Spacer(1, 0.3 * 72)] + m.colocar("resolucion_espacial", alta)
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate
    salida = io.BytesIO()
    SimpleDocTemplate(salida, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=245, bottomMargin=100).build(elementos)
    doc = fitz.open(stream=salida.getvalue(), filetype="pdf")
    assert "fila 0" in doc[1].get_text(), [p.get_text()[:20] for p in doc]


def test_unas_imagenes_que_llegan_al_pie_de_la_ultima_pagina_no_dejan_otra_en_blanco(tmp_path):
    m = _maqueta()
    from reportlab.platypus import Spacer
    rutas = [_png(tmp_path, "a.png", 200, 200), _png(tmp_path, "b.png", 200, 200)]
    elementos = [Spacer(1, 140), m.TablaDeImagenes(_datos(rutas), []), m.espacio_entre_tablas("imagen_espesor")]
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate
    salida = io.BytesIO()
    SimpleDocTemplate(salida, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=245, bottomMargin=100).build(elementos)
    assert fitz.open(stream=salida.getvalue(), filetype="pdf").page_count == 1
    assert m.espacio_entre_tablas("equipos").wrap(100, 5)[1] == pytest.approx(0.3 * 72) and m.espacio_entre_tablas("imagen_espesor").wrap(100, 5)[1] == 5


def _celda(texto=""):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    return Paragraph(texto, getSampleStyleSheet()["Normal"])


@pytest.mark.parametrize("falta", [0, 1])
def test_si_falta_una_imagen_la_otra_queda_en_su_columna_a_lo_ancho_de_ella_con_su_forma(tmp_path, falta):
    m = _maqueta()
    doc = _pdf_con(m.TablaDeImagenes(_datos([_celda() if i == falta else _png(tmp_path, f"{i}.png", 300, 200) for i in (0, 1)]), []))
    rects = [fitz.Rect(i["bbox"]) for i in doc[0].get_image_info()]
    assert doc.page_count == 1 and len(rects) == 1, rects
    r = rects[0]
    assert abs(r.x0 - (MARCO[0] + 6 + (1 - falta) * ANCHO_UTIL / 2)) < 0.5 and abs(r.width - ANCHO_UTIL / 2) < 0.5 and abs(r.width / r.height - 1.5) < 0.005, r
    assert "Imagen original" in doc[0].get_text() and "Imagen del análisis" in doc[0].get_text()


def test_la_celda_sin_imagen_queda_como_la_trae_el_informe_en_su_columna(tmp_path):
    m = _maqueta()
    doc = _pdf_con(m.TablaDeImagenes(_datos([_celda("celda-del-informe"), _png(tmp_path, "b.png", 300, 200)]), []))
    palabra = [w for w in doc[0].get_text("words") if w[4] == "celda-del-informe"]
    assert len(palabra) == 1 and palabra[0][2] <= 306.5, palabra


def test_sin_ninguna_imagen_el_pdf_sale_con_sus_dos_encabezados():
    m = _maqueta()
    doc = _pdf_con(m.TablaDeImagenes(_datos([_celda(), _celda()]), []))
    assert doc.page_count == 1 and not doc[0].get_image_info() and "Imagen original" in doc[0].get_text() and "Imagen del análisis" in doc[0].get_text()


def test_sin_ninguna_imagen_y_sin_sitio_pasa_a_la_pagina_siguiente_sin_fallar():
    m = _maqueta()
    doc = _pdf_con(m.TablaDeImagenes(_datos([_celda(), _celda()]), []), antes_pt=ALTO_UTIL - 5)
    assert doc.page_count == 2 and "Imagen original" in doc[1].get_text()


def test_una_imagen_sola_que_no_cabe_se_achica_en_su_columna_sin_pasar_del_pie(tmp_path):
    m = _maqueta()
    doc = _pdf_con(m.TablaDeImagenes(_datos([_celda(), _png(tmp_path, "c.png", 100, 400)]), []))
    rects = [fitz.Rect(i["bbox"]) for i in doc[0].get_image_info()]
    assert doc.page_count == 1 and len(rects) == 1, rects
    assert rects[0].x0 >= 305.5 and rects[0].y1 <= MARCO[3] + 0.5 and abs(rects[0].width / rects[0].height - 0.25) < 0.005, rects[0]


# (ancho, alto) [px] de la imagen original y de la del analisis; None: falta. Estrechas: al angostar sus columnas, las cabeceras se parten
FORMAS_EXTREMAS = {"estrechas": ((80, 400), (80, 400)), "muy_estrechas": ((4, 400), (4, 400)), "una_estrecha_sola": ((40, 400), None),
                   "estrecha_y_ancha": ((8, 400), (1200, 400)), "apiladas_con_una_muy_baja": ((400, 400), (800, 16))}


def _pdf_del_generador(generador, rutas, filas):
    """El PDF real, mensual o anual, de una prueba con `filas` filas de resultados y su tabla de imagenes."""
    pandas = importlib.import_module("pandas")
    tablas = {"espesor": pandas.DataFrame([["Espesor de corte", ""]] + [[f"fila {i}", "1.0"] for i in range(filas)], columns=["Prueba", "Valor"]),
              "imagen_espesor": pandas.DataFrame([["Espesor de corte", ""], list(rutas)], columns=["Imagen original", "Imagen del análisis"])}
    if generador == "mensual":
        pdf = pdf_mod.generar_reporte_pdf_multitabla_mensual(tablas, "01/10/2026", "Físico", maquina="Tomógrafo", id_maquina="Tomógrafo", temp=True, sistema_imagenes=True)
    else:
        pdf = pdf_mod.generar_reporte_pdf_multitabla_anual(tablas_dict=tablas, fecha="2026", user="Físico", tipo_reporte="Anual", maquina="Halcyon", id_maquina="Halcyon", temp=True)
    return fitz.open(stream=bytes(pdf.data()), filetype="pdf")


@pytest.mark.parametrize("filas", [1, 9])  # con 1 las imagenes pueden compartir la pagina; con 9 pasan a la siguiente
@pytest.mark.parametrize("formas", list(FORMAS_EXTREMAS.values()), ids=list(FORMAS_EXTREMAS))
@pytest.mark.parametrize("generador", ["mensual", "anual"])
def test_con_formas_extremas_el_pdf_sale_y_sus_imagenes_caben_en_el_marco(app, tmp_path, generador, formas, filas):
    rutas = [None if f is None else _png(tmp_path, f"{c}.png", *f, color=(90 * c, 0, 0)) for c, f in enumerate(formas)]
    doc = _pdf_del_generador(generador, rutas, filas)
    imagenes = [im for pagina in doc for im in imagenes_de(doc, pagina)]
    assert len(imagenes) == sum(f is not None for f in formas), imagenes
    for r, (w, h), _ in imagenes:
        assert abs((r.width / r.height) / (w / h) - 1) < 0.005, (w, h, r)
        assert r.x0 >= MARCO[0] - 0.5 and r.x1 <= MARCO[2] + 0.5 and r.y0 >= MARCO[1] - 0.5 and r.y1 <= MARCO[3] + 0.5, r
    fuera = [p for pagina in doc for p in pagina.get_text("words") if MARCO[1] <= p[1] <= MARCO[3] and (p[0] < MARCO[0] - 0.5 or p[2] > MARCO[2] + 0.5 or p[3] > MARCO[3] + 0.5)]
    assert not fuera, fuera


@pytest.mark.parametrize("filas", [1, 9])
@pytest.mark.parametrize("formas", [((32, 400), (660, 400)), ((660, 400), (40, 400)), ((80, 400), (660, 400))], ids=["estrecha_32", "estrecha_40_a_la_derecha", "estrecha_80"])
@pytest.mark.parametrize("generador", ["mensual", "anual"])
def test_una_imagen_estrecha_no_parte_las_palabras_de_las_cabeceras(app, tmp_path, generador, formas, filas):
    rutas = [_png(tmp_path, f"{c}.png", *f, color=(90 * c, 0, 0)) for c, f in enumerate(formas)]
    doc = _pdf_del_generador(generador, rutas, filas)
    pagina = next(p for p in doc if imagenes_de(doc, p))
    tope = min(r.y0 for r, _, _ in imagenes_de(doc, pagina))
    palabras = [w[4] for w in pagina.get_text("words") if MARCO[1] <= w[1] < tope]
    assert set(palabras) <= {"Imagen", "original", "del", "análisis", "Espesor", "de", "corte", "Prueba", "fila", "1.0"} | {str(i) for i in range(filas)}, palabras


def test_con_columnas_de_ancho_fijo_cada_imagen_va_centrada_en_la_suya(tmp_path):
    m = _maqueta()
    rutas = [_png(tmp_path, "a.png", 40, 400), _png(tmp_path, "b.png", 80, 400, color=(90, 0, 0))]
    doc = _pdf_con(m.TablaDeImagenes(_datos(rutas), []))
    rects = sorted((fitz.Rect(i["bbox"]) for i in doc[0].get_image_info()), key=lambda r: r.x0)
    assert doc.page_count == 1 and len(rects) == 2 and abs(rects[0].height - rects[1].height) < 0.5, rects
    centros = [(r.x0 + r.x1) / 2 for r in rects]
    assert abs(centros[0] - (MARCO[0] + 6 + ANCHO_UTIL / 4)) < 0.5 and abs(centros[1] - (MARCO[0] + 6 + 3 * ANCHO_UTIL / 4)) < 0.5, centros


# a pagina entera las palabras caben; a 180 pt de alto no (la primera solo contando el relleno de la celda; la segunda solo en el titulo)
@pytest.mark.parametrize("estrecha, titulo", [(88, "Prueba"), (112, "Uniformidad y ruido")], ids=["relleno_de_la_celda", "titulo_de_la_prueba"])
def test_si_a_180_pt_una_palabra_de_las_cabeceras_no_cabria_las_columnas_son_iguales(tmp_path, estrecha, titulo):
    m = _maqueta()
    rutas = [_png(tmp_path, "a.png", estrecha, 400), _png(tmp_path, "b.png", 660, 400, color=(90, 0, 0))]
    doc = _pdf_con(m.TablaDeImagenes(_datos(rutas, titulo), []))
    centros = sorted((r.x0 + r.x1) / 2 for r in (fitz.Rect(i["bbox"]) for i in doc[0].get_image_info()))
    assert doc.page_count == 1 and len(centros) == 2 and abs(centros[0] - (MARCO[0] + 6 + ANCHO_UTIL / 4)) < 0.5 and abs(centros[1] - (MARCO[0] + 6 + 3 * ANCHO_UTIL / 4)) < 0.5, centros


# 4. DONDE ENTRA LA MAQUETA

def test_pdf_py_llama_a_la_maqueta_solo_en_las_ramas_del_catphan_y_build_exe_la_lista_una_vez():
    _maqueta()
    arbol = ast.parse((RAIZ / "models/PDF/pdf.py").read_text(encoding="utf-8"))
    usos = {}
    for funcion in [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)]:
        for n in ast.walk(funcion):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "maqueta_catphan":
                usos.setdefault(funcion.name, []).append(n.attr)
    assert {k: sorted(v) for k, v in usos.items()} == {"generar_reporte_pdf_multitabla_mensual": ["TABLAS_DE_IMAGENES", "colocar", "espacio_entre_tablas", "uniones_de_criterio"],
                                                       "generar_reporte_pdf_multitabla_anual": ["colocar", "espacio_entre_tablas"],
                                                       "_crear_tabla_pdf_anual": ["TABLAS_DE_IMAGENES", "TablaDeImagenes", "uniones_de_criterio"]}, usos
    texto = (RAIZ / "build_exe.py").read_text(encoding="utf-8")
    assert texto.count('"models.PDF.Imagenes.maqueta_catphan"') == 1
