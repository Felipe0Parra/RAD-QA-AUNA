"""PI.8 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md, DA-82 D2): el PDF DIARIO de braquiterapia lleva un bloque breve con la posición inicial
de la fuente en uso, debajo del bloque R6 ("Análisis de la placa" y su película): una tabla aparte de una columna, con el texto en un
`Paragraph` (si no, se desborda de la celda, DP-97), solo si la fuente en uso tiene prueba. No es una columna de la tabla diaria (no
toca el censo `R2`). 600, iX, Halcyon y la calculadora de dosis no lo tienen ni consultan el servicio.

Lo que se garantiza, cada cosa con su prueba:
  - el generador (`generar_reporte_pdf(..., posicion_inicial=None)`): con `None` es el de siempre (mismos bytes que sin el argumento);
    con un texto, el título sale UNA vez, DESPUÉS de "Análisis de la placa" y de la película, la firma sigue en CADA página (se cuenta
    el CARGO, que solo vive en el bloque de firma: el nombre ya está en el encabezado de la página 1 y no prueba nada), el bloque
    no invade la franja de la firma y su texto no se sale de la celda -- para 0 a 70 filas y los tres casos de R6 (sin R6, R6 sin
    película, R6 con película), con el texto típico y con el más largo (el de «otra resolución»);
  - lo VISUAL, medido sobre el PDF y contra "Análisis de la placa" del mismo documento (la misma cabecera, a 10 pt de lo de arriba, la
    letra del cuerpo, color y negrita, dos líneas del texto sin superponerse), en cada colocación de un barrido FINO (de una fila en
    una fila: el de 5 en 5 deja pasar una invasión de decenas de pt entre dos muestras);
  - la regla de salto de página que R6 y el bloque comparten: solo salta si no cabía (frontera exacta: lo que cabe justo se queda),
    ninguna página queda con solo la firma, y en la franja de la firma no hay nada más que la firma;
  - lo no nombrado no cambia: el texto del PDF con el bloque es el del PDF sin él MÁS el bloque, y R6 (la tabla y su película) queda
    EXACTAMENTE donde estaba cuando no se pasa el bloque (medido contra HEAD: la regla de salto se extrajo a una función compartida y
    ninguna otra prueba fija dónde queda R6; los «mismos bytes con None» comparan el código consigo mismo, la equivalencia contra HEAD
    es la compuerta del anexo);
  - la unidad no se separa de su cifra: lo que imprime un PDF lleva un espacio duro entre la cifra y mm, px o dpi (`texto_para_pdf`,
    la única definición); sin él, en más de la mitad de los textos de la rama «sin banda de tránsito» el renglón se partía entre
    «1.0» y «mm).» (hallazgo V2 de la revisión independiente);
  - el cableado (`reportes.reporte()`): las cinco fechas del plan (2026-01-10, 03-01 y 04-14 con el bloque; 04-15 y 01-09 sin él),
    sin ninguna prueba y con la prueba anulada, ninguno; un fallo del servicio, de CUALQUIER tipo, avisa con su causa y no genera el
    PDF (un diario firmado no sale sin el dato); 600, iX y Halcyon no consultan el servicio (se CUENTA la consulta: un `raise` lo
    traga el `except` de `reporte()` y la prueba pasaría igual).
La compuerta de bytes contra HEAD (la calculadora y el diario sin prueba, byte a byte) es un script del anexo (`pi8_compuerta_diario.py`).
Se siembra TODO antes de abrir ninguna conexión de Qt (una escritura por sqlite3 entre aperturas de Qt rompe el reporte)."""
import ast
import base64
import inspect
import os
import re
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pandas as pd
import pytest
from PyQt5.QtWidgets import QMessageBox

# Import circular preexistente (ver test_r1_r6): `load` entero primero.
import data.ManejoDatos.load  # noqa: F401
import models.PDF.pdf as pdf_mod
from models.PDF import reportes as reportes_mod
from models.PDF.pdf import ALTO_RECUADRO_IMAGEN_BRAQUI, CUERPO_TABLA_PT, generar_reporte_pdf  # noqa: F401
from services import posicion_inicial_braqui as svc
from test_pi3_servicio_posicion_inicial import USUARIO, _sintetica
from test_r1_r6_reportes_diarios_legibles import (DICC_600, DICC_BRAQUI, DICC_HALCYON, _AutoDB, _capturar_pdf,  # noqa: F401
                                                  _sin_dialogos_modales, app, bd_temporal)

TITULO = "Posición inicial de la fuente"
TEXTO_TIPICO = "-0.36 ± 0.09 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-01-10"
TEXTO_LARGO = ("-8.55 ± 2.12 px (k = 2); la imagen declara 300 dpi y el procedimiento es de 600 dpi: parece escaneada a otra resolucion; "
               "escanee la pelicula a 600 dpi. Sin milimetros ni veredicto. Cambio de fuente del 2026-06-26")
FIRMANTE, CARGO = "Fisico Pi8 Firma", "Físico Médico"
PELICULA = (Path(__file__).resolve().parent / "datos" / "braqui_00.jpeg").read_bytes()
# JPEG de 1x1 px (el de test_r1_r6): el recuadro de la película es FIJO (450x130), así que la geometría de los barridos finos sale la
# misma que con la película real y cada PDF cuesta milisegundos en vez de décimas de segundo. La película real se usa en el barrido
# de 5 en 5 y en la prueba de cableado.
PELICULA_MINIMA = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkI"
    "CQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/wAALCAABAAEBAREA/8QAFQABAQAAAAAA"
    "AAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAA/AKAAAA==")
ALTO_PAGINA, X_IZQUIERDO, X_DERECHO = 792, 81, 81 + 450     # letter; la tabla ocupa de x = 81 a x = 531
Y_MAXIMO_DEL_CONTENIDO = ALTO_PAGINA - 125                  # ALTO_BLOQUE_FIRMA del diario: el contenido termina sobre la franja de la firma
Y_LINEA_DE_FIRMA = ALTO_PAGINA - 55                         # la línea sobre el nombre (Y_FIRMA_LINEA = 55 desde abajo), de 200 pt de ancho
AZUL = (1 / 255, 176 / 255, 202 / 255)                      # #01b0ca, la cabecera de las tablas de R6
SIN_ARGUMENTO = object()
# (R6, filas): páginas de 1, 2 y 3, con el bloque debajo de R6, saltando solo o con R6 saltando también
CASOS_DE_PAGINACION = [("sin", 10), ("sin", 15), ("sin_pelicula", 10), ("sin_pelicula", 35), ("con_pelicula", 5), ("con_pelicula", 10),
                       ("con_pelicula", 30)]


@pytest.fixture(autouse=True)
def _con_aplicacion_de_qt(app):
    """La película se decodifica con QPixmap: sin una QApplication viva el proceso aborta (Trampa 1), no falla una prueba."""


# ------------------------------------------------------------------------------------------------------- el generador

def _df(n_filas, r6, pelicula=PELICULA):
    """Un diario de braquiterapia: `n_filas` pruebas y, según `r6`, ninguna fila del análisis ('sin'), solo promedio y desviación
    ('sin_pelicula') o también la película ('con_pelicula')."""
    filas = [f"Prueba número {i} de la lista de verificación diaria" for i in range(n_filas)]
    valores, evaluacion = ["Funciona"] * n_filas, [None] * n_filas
    if r6 != "sin":
        filas += ["promedio", "desviacion"]
        valores += [9.99, 0.06]
        evaluacion += [None, None]
    if r6 == "con_pelicula":
        filas += ["pelicula"]
        valores += [pelicula]
        evaluacion += [None]
    return pd.DataFrame({"": filas, "Evaluación": evaluacion, "Valores": valores})


def _df_rapido(n_filas, r6):
    return _df(n_filas, r6, pelicula=PELICULA_MINIMA)


def _pdf(df, posicion=SIN_ARGUMENTO, diario=True):
    # `generar_reporte_pdf` modifica el df que recibe (drop in situ): cada PDF trabaja sobre su copia.
    argumentos = dict(df=df.copy(), fecha="2026-03-01", user=FIRMANTE, tipo_reporte="Diario", maquina="Gammamed Plus i X", id_maquina="",
                      logo_path=None, firma=None, role=CARGO, temp=True, es_diario_qc=diario)
    if posicion is not SIN_ARGUMENTO:
        argumentos["posicion_inicial"] = posicion
    return bytes(generar_reporte_pdf(**argumentos).data())


def _normal(texto):
    return " ".join(texto.split())


def _cabecera(doc, titulo):
    """(página, rectángulo del relleno azul que contiene el título): la cabecera de una tabla de R6 o del bloque."""
    for i, pagina in enumerate(doc):
        for rect in pagina.search_for(titulo):
            centro = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
            for d in pagina.get_drawings():
                if d.get("fill") and all(abs(a - b) < 0.01 for a, b in zip(d["fill"], AZUL)) and d["rect"].contains(centro):
                    return i, d["rect"]
    raise AssertionError(f"no hay una cabecera azul con {titulo!r}")


def _revisar(doc, texto, r6):
    """Todo lo que el plan exige del bloque, sobre un PDF real. Devuelve (pagina_del_bloque, pagina_de_r6 o None)."""
    titulos = [(i, r) for i, pagina in enumerate(doc) for r in pagina.search_for(TITULO)]
    assert len(titulos) == 1, f"el bloque debe salir UNA vez, salió {len(titulos)}"
    pagina, rect = titulos[0]
    # el título es EXACTAMENTE el nombre del bloque, sin unidad ni nada pegado (`search_for` también encuentra una subcadena)
    assert TITULO in [linea.strip() for linea in doc[pagina].get_text().splitlines()], "el título del bloque no es exactamente su nombre"
    pagina_r6 = None
    if r6 != "sin":
        encontrados = [(i, r) for i, p in enumerate(doc) for r in p.search_for("Análisis de la placa")]
        assert len(encontrados) == 1
        pagina_r6, rect_r6 = encontrados[0]
        assert (pagina, rect.y0) > (pagina_r6, rect_r6.y0), "el bloque debe ir DESPUÉS de 'Análisis de la placa'"
        if r6 == "con_pelicula":
            imagenes = doc[pagina_r6].get_image_info()
            assert len(imagenes) == 1
            assert pagina > pagina_r6 or rect.y0 >= imagenes[0]["bbox"][3] - 0.5, "el bloque debe ir DESPUÉS de la película"
    # el texto completo, en el orden de la lectura
    assert _normal(texto) in _normal(doc[pagina].get_text()), "el texto del bloque no está completo en su página"
    # la firma, UNA vez en cada página. Se cuenta el CARGO y no el nombre: la página 1 ya trae `Usuario: <nombre>` en el encabezado, y
    # buscar el nombre no ve una firma que falte justo ahí (la causa de C.3); el cargo solo vive en el bloque de firma
    for i, p in enumerate(doc):
        veces = p.get_text().count(CARGO)
        assert veces == 1, f"la página {i} de {doc.page_count} tiene el bloque de firma {veces} veces (debe ser una)"
    # geometría: nada del bloque invade la franja de la firma ni se sale de la celda
    firma = set(FIRMANTE.split()) | set(CARGO.split())
    bloque = [w for w in doc[pagina].get_text("words") if w[1] >= rect.y0 - 1 and w[4] not in firma]
    assert bloque, "no se encontraron las palabras del bloque"
    assert max(w[3] for w in bloque) <= Y_MAXIMO_DEL_CONTENIDO + 0.5, "el bloque invade la franja de la firma"
    assert max(w[2] for w in bloque) <= X_DERECHO + 0.5, "el texto se sale de la celda (¿sin Paragraph?)"
    return pagina, pagina_r6


class TestElGenerador:
    def test_con_none_son_los_mismos_bytes_que_sin_el_argumento(self, monkeypatch):
        from reportlab import rl_config
        monkeypatch.setattr(rl_config, "invariant", 1)
        df = _df(12, "sin_pelicula")
        assert _pdf(df, None) == _pdf(df) == _pdf(df, None)

    def test_none_no_dibuja_ningun_bloque(self):
        doc = fitz.open(stream=_pdf(_df(12, "con_pelicula"), None), filetype="pdf")
        assert TITULO not in "".join(p.get_text() for p in doc)

    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    @pytest.mark.parametrize("texto", [TEXTO_TIPICO, TEXTO_LARGO], ids=["tipico", "largo"])
    def test_barrido_de_filas_el_bloque_sale_una_vez_en_su_sitio_y_la_firma_en_cada_pagina(self, app, r6, texto):
        paginas_del_bloque, mismas_que_r6, despues_de_r6 = set(), 0, 0
        for n in range(0, 71, 5):
            doc = fitz.open(stream=_pdf(_df(n, r6), texto), filetype="pdf")
            try:
                pagina, pagina_r6 = _revisar(doc, texto, r6)
                paginas_del_bloque.add(doc.page_count)
                if pagina_r6 is not None:
                    mismas_que_r6 += pagina == pagina_r6
                    despues_de_r6 += pagina > pagina_r6
            finally:
                doc.close()
        assert len(paginas_del_bloque) >= 2, "el barrido no llegó a producir PDF de distinto número de páginas: no discrimina"
        if r6 != "sin":
            # Trampa 8: el barrido tiene que recorrer los dos casos que importan (el bloque cabe debajo de R6 y no cabe y salta)
            assert mismas_que_r6 >= 1 and despues_de_r6 >= 1, (mismas_que_r6, despues_de_r6)

    @pytest.mark.parametrize("r6,n", CASOS_DE_PAGINACION)
    def test_el_bloque_de_firma_esta_exactamente_una_vez_en_cada_pagina(self, app, r6, n):
        """Una firma que falta o que sale dos veces (dibujada otra vez tras el bloque) con el diario de 1, 2 y 3 páginas."""
        doc = fitz.open(stream=_pdf(_df_rapido(n, r6), TEXTO_LARGO), filetype="pdf")
        for i, p in enumerate(doc):
            assert p.get_text().count(CARGO) == 1, f"página {i} de {doc.page_count}: el bloque de firma sale {p.get_text().count(CARGO)} veces"

    def test_el_texto_largo_ocupa_varias_lineas_dentro_de_la_celda(self, app):
        doc = fitz.open(stream=_pdf(_df(5, "sin"), TEXTO_LARGO), filetype="pdf")
        pagina, _ = _revisar(doc, TEXTO_LARGO, "sin")
        # la primera y la última palabra del texto (la cifra y la fecha del cambio de fuente) no pueden estar en la misma línea
        palabras = [w for w in doc[pagina].get_text("words") if w[4] in ("-8.55", "2026-06-26")]
        assert len({round(w[1]) for w in palabras}) == 2, "el texto largo debía partirse en varias líneas"

    @pytest.mark.parametrize("n", [5, 15])
    def test_las_lineas_del_texto_largo_no_se_superponen(self, app, n):
        doc = fitz.open(stream=_pdf(_df_rapido(n, "sin"), TEXTO_LARGO), filetype="pdf")
        pagina, rect = _cabecera(doc, TITULO)
        lineas = sorted({round(w[1], 1) for w in doc[pagina].get_text("words") if w[1] > rect.y1})
        lineas = [y for y in lineas if y < Y_MAXIMO_DEL_CONTENIDO]            # sin las palabras de la firma, que están más abajo
        assert len(lineas) >= 2
        for a, b in zip(lineas, lineas[1:]):
            assert b - a >= CUERPO_TABLA_PT - 0.5, f"dos líneas del texto a {b - a:.1f} pt: se superponen"

    @pytest.mark.parametrize("r6,n", [("sin", 5), ("sin_pelicula", 5), ("con_pelicula", 10)])
    def test_la_tabla_del_bloque_mide_lo_que_la_tabla_principal(self, app, r6, n):
        doc = fitz.open(stream=_pdf(_df_rapido(n, r6), TEXTO_LARGO), filetype="pdf")
        _, rect = _cabecera(doc, TITULO)
        assert abs(rect.x0 - X_IZQUIERDO) < 0.6 and abs(rect.x1 - X_DERECHO) < 0.6, f"la cabecera del bloque va de x={rect.x0:.1f} a x={rect.x1:.1f}"

    @pytest.mark.parametrize("r6,n", [("sin_pelicula", 5), ("sin_pelicula", 30), ("con_pelicula", 10), ("con_pelicula", 25)])
    def test_el_bloque_no_pisa_lo_que_tiene_encima_y_deja_su_hueco(self, app, r6, n):
        """Nada de lo que empieza ARRIBA de la cabecera del bloque (la tabla principal, R6, el marco de la película) llega hasta ella."""
        doc = fitz.open(stream=_pdf(_df_rapido(n, r6), TEXTO_LARGO), filetype="pdf")
        pagina, rect = _cabecera(doc, TITULO)
        arriba = [d["rect"] for d in doc[pagina].get_drawings() if d["rect"].y0 < rect.y0 - 1 and d["rect"].width > 5 and d["rect"].height > 5]
        assert arriba, "no se encontró nada encima del bloque"
        hueco = rect.y0 - max(r.y1 for r in arriba)
        assert hueco >= 9.5, f"el bloque queda a {hueco:.1f} pt de lo de arriba (se esperaban los 10 pt del resto de bloques)"

    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    @pytest.mark.parametrize("texto", [TEXTO_TIPICO, TEXTO_LARGO], ids=["tipico", "largo"])
    def test_el_texto_y_la_cabecera_se_leen_en_toda_colocacion(self, app, r6, texto):
        """La cabecera (azul, letra blanca en negrita) y el texto (negro, la letra del cuerpo) se miden en TODAS las colocaciones del
        barrido, no solo en una: un texto blanco sobre blanco, una letra suelta o una cabecera sin fondo cuando el texto es largo dejan un
        documento firmado con el dato invisible o ilegible."""
        for n in range(0, 36, 5):
            doc = fitz.open(stream=_pdf(_df_rapido(n, r6), texto), filetype="pdf")
            pagina, rect = _cabecera(doc, TITULO)               # falla si la cabecera no tiene el relleno azul
            spans = [s for b in doc[pagina].get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"] if s["bbox"][1] >= rect.y0 - 1]
            titulo = [s for s in spans if TITULO in s["text"]]
            cuerpo = [s for s in spans if s["bbox"][1] > rect.y1 - 1 and s["bbox"][3] < Y_MAXIMO_DEL_CONTENIDO
                      and any(w in texto.split() for w in s["text"].split())]
            assert titulo and all(s["color"] == 0xFFFFFF and "Bold" in s["font"] for s in titulo), (n, titulo)
            assert cuerpo and all(s["color"] == 0 and round(s["size"], 2) == float(CUERPO_TABLA_PT) for s in cuerpo), (n, [(s["color"], s["size"]) for s in cuerpo])
            doc.close()

    def test_el_titulo_que_se_prueba_es_el_de_produccion_y_no_lleva_unidad(self):
        """El título se lee del código que genera el PDF (por AST), no de una constante de este archivo: una unidad entre paréntesis
        o corchetes en una etiqueta nueva dispararía el tripwire de D.1 (y el título es un nombre, no una magnitud)."""
        arbol = ast.parse(inspect.getsource(generar_reporte_pdf))
        titulos = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("Posición inicial")]
        assert titulos == [TITULO], titulos
        assert "(" not in titulos[0] and "[" not in titulos[0]

    def test_la_calculadora_no_cambia_con_el_argumento_por_omision(self, monkeypatch):
        from reportlab import rl_config
        monkeypatch.setattr(rl_config, "invariant", 1)
        df = pd.DataFrame({"": ["Fecha", "Acelerador", "dosis_maxima"], "Evaluación": [None, None, None],
                           "Valores": ["2026-01-01", "Clinac 600", 1.005]})
        a = bytes(generar_reporte_pdf(df=df.copy(), fecha="2026-01-01", user=FIRMANTE, tipo_reporte="Calculadora", maquina="Clinac 600",
                                      id_maquina="", logo_path=None, firma=None, role=CARGO, temp=True).data())
        b = bytes(generar_reporte_pdf(df=df.copy(), fecha="2026-01-01", user=FIRMANTE, tipo_reporte="Calculadora", maquina="Clinac 600",
                                      id_maquina="", logo_path=None, firma=None, role=CARGO, temp=True, posicion_inicial=None).data())
        assert a == b

    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    def test_pasar_el_bloque_no_cambia_nada_mas_del_diario(self, app, r6):
        """Lo no nombrado no cambia: el texto del PDF con el bloque es el del PDF sin él MÁS el bloque (título y texto), y en el mismo
        orden. La firma se repite en cada página, así que se compara sin ella. Un cambio que altere TODOS los PDF (un ancho de línea,
        una fila perdida) lo ve esta prueba y no la de «mismos bytes con None», que compara el código consigo mismo."""
        firma = {FIRMANTE, CARGO}
        texto_del_bloque = _normal(TEXTO_TIPICO).split()

        def lineas(pdf):
            doc = fitz.open(stream=pdf, filetype="pdf")
            salida = [l.strip() for p in doc for l in p.get_text().splitlines() if l.strip() and l.strip() not in firma]
            doc.close()
            return salida

        for n in (0, 5, 10, 15, 20, 25, 30, 35):
            con = lineas(_pdf(_df_rapido(n, r6), TEXTO_TIPICO))
            sin = lineas(_pdf(_df_rapido(n, r6), None))
            resto = [l for l in con if l != TITULO and not all(w in texto_del_bloque for w in l.split())]
            assert resto == sin, f"n={n}: con el bloque cambia otra cosa del PDF: {[l for l in resto if l not in sin][:3]} / {[l for l in sin if l not in resto][:3]}"


# ------------------------------------------------------------------------ el barrido fino, la franja de la firma y el salto de página

def _trazos_del_bloque(doc, pagina, rect):
    return [d["rect"] for d in doc[pagina].get_drawings() if d["rect"].y0 >= rect.y0 - 1 and d["rect"].y1 < 700]


class TestLaReglaDeSaltoDePagina:
    """R6 (la tabla y su película) y el bloque comparten UNA regla de salto (`_salto_si_no_cabe`)."""

    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    @pytest.mark.parametrize("nombre,texto", [("corto", "-0.36 ± 0.09 mm (k = 2), antes de la marca. Cumple"), ("tipico", TEXTO_TIPICO),
                                              ("largo", TEXTO_LARGO)], ids=["corto", "tipico", "largo"])
    def test_el_borde_de_la_tabla_del_bloque_nunca_entra_en_la_franja_de_la_firma(self, app, r6, nombre, texto):
        """El barrido de 5 en 5 filas salta ~130 pt: una invasión de decenas de pt cae entre dos muestras. Aquí se recorren TODAS las
        filas de 0 a 36 y se mide el borde de la TABLA (no el texto, que tiene ~4 pt de holgura) contra los 125 pt de la firma."""
        peores = []
        for n in range(0, 37):
            doc = fitz.open(stream=_pdf(_df_rapido(n, r6), texto), filetype="pdf")
            pagina, rect = _cabecera(doc, TITULO)
            peores.append((max(r.y1 for r in _trazos_del_bloque(doc, pagina, rect)), n))
            doc.close()
        fondo, n = max(peores)
        assert fondo <= Y_MAXIMO_DEL_CONTENIDO + 0.5, f"con n={n} el borde de la tabla del bloque llega a y={fondo:.1f} (límite {Y_MAXIMO_DEL_CONTENIDO}): invade la firma"

    @pytest.mark.parametrize("r6", ["sin_pelicula", "con_pelicula"])
    def test_la_franja_de_la_firma_solo_contiene_la_firma_en_cada_pagina(self, app, r6):
        """Las pruebas del bloque solo miran el bloque: si R6 invadiera la franja, o la película la pisara, nadie lo vería. En toda
        página, lo único que baja de y=667 (792-125) es la firma (su línea y sus palabras)."""
        firma = set(FIRMANTE.split()) | set(CARGO.split())
        for n in range(0, 37):
            doc = fitz.open(stream=_pdf(_df_rapido(n, r6), TEXTO_TIPICO), filetype="pdf")
            for i, p in enumerate(doc):
                intrusos = [d["rect"] for d in p.get_drawings()
                            if d["rect"].y1 > Y_MAXIMO_DEL_CONTENIDO + 0.5 and not (abs(d["rect"].y0 - Y_LINEA_DE_FIRMA) < 1.5 and d["rect"].width <= 201)]
                assert not intrusos, f"n={n} página {i}: dibujos dentro de la franja de la firma: {intrusos[:2]}"
                assert all(img["bbox"][3] <= Y_MAXIMO_DEL_CONTENIDO + 0.5 for img in p.get_image_info()), f"n={n} página {i}: la película entra en la franja"
                palabras = [w for w in p.get_text("words") if w[3] > Y_MAXIMO_DEL_CONTENIDO + 0.5 and w[4] not in firma]
                assert not palabras, f"n={n} página {i}: texto dentro de la franja de la firma: {[w[4] for w in palabras][:5]}"
            doc.close()

    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    def test_ninguna_pagina_queda_con_solo_la_firma(self, app, r6):
        firma = set(FIRMANTE.split()) | set(CARGO.split())
        for n in range(0, 36, 5):
            doc = fitz.open(stream=_pdf(_df_rapido(n, r6), TEXTO_LARGO), filetype="pdf")
            for i, p in enumerate(doc):
                assert [w for w in p.get_text("words") if w[4] not in firma], f"n={n}: la página {i + 1} de {doc.page_count} solo tiene la firma"
            doc.close()

    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    @pytest.mark.parametrize("texto", [TEXTO_TIPICO, TEXTO_LARGO], ids=["tipico", "largo"])
    def test_el_bloque_solo_salta_de_pagina_si_no_cabia(self, app, r6, texto):
        """Si el bloque está en una página POSTERIOR a la del último contenido que lo precede (la tabla principal, o R6 y su película),
        a esa página le faltaba sitio: libre < alto del bloque + 10. Un salto de más deja un diario firmado con una página casi vacía."""
        comprobados = 0
        for n in range(0, 37):
            doc = fitz.open(stream=_pdf(_df_rapido(n, r6), texto), filetype="pdf")
            pagina, rect = _cabecera(doc, TITULO)
            if r6 == "sin":
                marca = f"Prueba número {n - 1} de la lista" if n else None
                ultima = ([i for i, p in enumerate(doc) if marca and marca in " ".join(p.get_text().split())] or [0])[-1]
            elif r6 == "sin_pelicula":
                ultima = [i for i, p in enumerate(doc) if "Desviación estándar" in p.get_text()][0]
            else:
                ultima = [i for i, p in enumerate(doc) if p.get_image_info()][0]
            if pagina > ultima:
                trazos_bloque = _trazos_del_bloque(doc, pagina, rect)
                alto = max(r.y1 for r in trazos_bloque) - min(r.y0 for r in trazos_bloque)
                previos = [d["rect"].y1 for d in doc[ultima].get_drawings() if d["rect"].y1 < 700 and d["rect"].height + d["rect"].width > 5]
                libre = Y_MAXIMO_DEL_CONTENIDO - max(previos)
                assert libre < alto + 10 + 1.5, f"n={n}: el bloque saltó de página con {libre:.1f} pt libres y necesita {alto + 10:.1f}"
                comprobados += 1
            doc.close()
        assert comprobados >= 2, "el barrido no recorre saltos de página: la prueba no discrimina"

    @staticmethod
    def _elementos_del_diario(doc, r6):
        """[(nombre, página, y_arriba, y_abajo)] de R6 (tabla y película) y del bloque, medidos sobre lo DIBUJADO."""
        pagina_pi, cab_pi = _cabecera(doc, TITULO)
        dib = _trazos_del_bloque(doc, pagina_pi, cab_pi)
        elementos = [("bloque", pagina_pi, cab_pi.y0, max(r.y1 for r in dib))]
        if r6 != "sin":
            pagina_r6, cab_r6 = _cabecera(doc, "Análisis de la placa")
            if r6 == "con_pelicula":
                marco = [d["rect"] for d in doc[pagina_r6].get_drawings()
                         if abs(d["rect"].width - 450) < 1 and abs(d["rect"].height - ALTO_RECUADRO_IMAGEN_BRAQUI) < 1]
                abajo = marco[0].y1
            else:
                limite = cab_pi.y0 - 5 if pagina_pi == pagina_r6 else 700
                abajo = max(d["rect"].y1 for d in doc[pagina_r6].get_drawings() if d["rect"].y0 >= cab_r6.y0 - 1 and d["rect"].y1 < limite)
            elementos.append(("R6", pagina_r6, cab_r6.y0, abajo))
        return elementos

    def test_en_todo_el_barrido_lo_que_cabe_se_queda_y_lo_que_no_salta(self, app):
        """En cada PDF del barrido (0 a 36 filas, texto típico y largo, R6 con y sin película), un elemento (R6 o el bloque) que EMPIEZA una
        página nueva es porque no cabía en la anterior (margen < 0), y uno que no la empieza no pasa de la franja de la firma. Se mide
        sobre lo dibujado. La frontera EXACTA (cabe justo / le faltan décimas) la fabrica la prueba siguiente: aquí no se espera que el
        barrido pase por una coincidencia numérica, que cualquier cambio legítimo de letra o de alto movería."""
        for r6 in ("sin_pelicula", "con_pelicula"):
            for texto in (TEXTO_TIPICO, TEXTO_LARGO):
                for n in range(0, 37):
                    doc = fitz.open(stream=_pdf(_df_rapido(n, r6), texto), filetype="pdf")
                    for nombre, pagina, arriba, abajo in self._elementos_del_diario(doc, r6):
                        if arriba < 61 and pagina > 0:                      # arranca una página nueva: hubo salto
                            previos = [d["rect"].y1 for d in doc[pagina - 1].get_drawings() if d["rect"].y1 < 700 and d["rect"].height + d["rect"].width > 5]
                            margen = (Y_MAXIMO_DEL_CONTENIDO - max(previos)) - (abajo - arriba + 10)
                            assert margen < -1e-3, f"{r6} n={n}: {nombre} saltó de página aunque cabía (margen {margen:+.4f} pt en la página anterior)"
                        else:
                            assert abajo <= Y_MAXIMO_DEL_CONTENIDO + 1e-3, f"{r6} n={n}: {nombre} llega a y={abajo:.3f}, más allá de la franja de la firma"
                    doc.close()

    @staticmethod
    def _marco_de_la_pelicula(n):
        """(página de la cabecera de R6, borde inferior del recuadro de la película) con el alto de recuadro vigente en `pdf.py`."""
        doc = fitz.open(stream=_pdf(_df_rapido(n, "con_pelicula")), filetype="pdf")
        try:
            pagina_r6 = [i for i, p in enumerate(doc) if p.search_for("Análisis de la placa")][0]
            marco = [d["rect"] for d in doc[pagina_r6].get_drawings()
                     if abs(d["rect"].width - pdf_mod.ANCHO_RECUADRO_IMAGEN_BRAQUI) < 1 and abs(d["rect"].height - pdf_mod.ALTO_RECUADRO_IMAGEN_BRAQUI) < 1]
            assert marco, "no se encontró el recuadro de la película"
            return pagina_r6, marco[0].y1
        finally:
            doc.close()

    @pytest.mark.parametrize("n", [3, 5])
    def test_r6_que_cabe_exactamente_se_queda_y_una_decima_mas_salta(self, app, monkeypatch, n):
        """La frontera exacta de la regla de salto (la comparten R6 y el bloque), FABRICADA y no esperada de una coincidencia numérica: se
        ajusta el alto del recuadro de la película (un global de `pdf.py`, leído al generar) para que R6 termine EXACTAMENTE en y=667 (la
        franja de la firma). Ahí se queda; con una décima más le faltan 0.1 pt y salta. Un `<` cambiado por `<=` (o un umbral movido un
        punto) hace caer esto sin depender de qué número de filas llegue justo, y sigue valiendo si cambia la letra o el alto de una fila."""
        pagina0, y1_de_fabrica = self._marco_de_la_pelicula(n)
        assert pagina0 == 0 and y1_de_fabrica < Y_MAXIMO_DEL_CONTENIDO, "el caso de partida debe caber en la página 1 con holgura"
        alto_justo = pdf_mod.ALTO_RECUADRO_IMAGEN_BRAQUI + (Y_MAXIMO_DEL_CONTENIDO - y1_de_fabrica)     # el recuadro termina EXACTAMENTE en y=667
        monkeypatch.setattr(pdf_mod, "ALTO_RECUADRO_IMAGEN_BRAQUI", alto_justo)
        pagina, y1 = self._marco_de_la_pelicula(n)
        assert pagina == 0, "R6 cabe justo (su recuadro termina en la franja de la firma, sin pasarse) y NO debe saltar de página"
        assert abs(y1 - Y_MAXIMO_DEL_CONTENIDO) < 1e-6, f"el recuadro debía terminar en y={Y_MAXIMO_DEL_CONTENIDO} y termina en {y1}"
        monkeypatch.setattr(pdf_mod, "ALTO_RECUADRO_IMAGEN_BRAQUI", alto_justo + 0.1)
        pagina, _ = self._marco_de_la_pelicula(n)
        assert pagina == 1, "a R6 le faltan 0.1 pt: debe saltar de página (antes de invadir la franja de la firma)"


# -------------------------------------------------------------------------- R6 sin el bloque: lo que ya salía no se mueve (vs HEAD)

# Y de arranque del título de R6 en una página NUEVA (sin filas de la tabla principal): arriba de la página, o bajo la fila vacía de
# 'Observaciones' que reportlab deja sola en la página nueva. MEDIDO contra HEAD (c610cb9, antes de PI.8): un salto que mueva R6 aunque
# sea 1 pt cambia este conjunto.
Y0_R6_EN_PAGINA_NUEVA = {62.3, 80.3}
# (filas, con película). Salen del rastreo de la decisión de salto (margen = y_cursor - alto de R6 - 125, en pt): 0.0 en (30, True) -- el caso
# límite exacto --, -2 en (12, False), -12 en (7, True), +10 en (35, False) y +14 en (6, True); (15, *) son los dos únicos donde R6 arranca bajo
# la fila vacía de 'Observaciones' (80.3); el resto es de relleno.
CASOS_R6_SIN_BLOQUE = [(1, False), (1, True), (6, True), (7, True), (12, False), (15, False), (15, True), (20, True), (30, True), (35, False),
                       (45, False), (60, True)]


def _doc_sin_bloque(n, con_pelicula):
    return fitz.open(stream=_pdf(_df(n, "con_pelicula" if con_pelicula else "sin_pelicula")), filetype="pdf")      # sin el argumento


def _r6_en(doc):
    """(página, y0 del título, borde inferior de todo R6): el borde sale de las palabras de R6, de su recuadro y de su imagen."""
    firma = {FIRMANTE, "Físico", "Médico"} | set(FIRMANTE.split())
    for i, p in enumerate(doc):
        titulo = p.search_for("Análisis de la placa")
        if not titulo:
            continue
        y0 = titulo[0].y0
        palabras = [w[3] for w in p.get_text("words") if w[1] >= y0 - 1 and w[4] not in firma]
        recuadros = [d["rect"].y1 for d in p.get_drawings() if abs(d["rect"].width - 450) < 1 and d["rect"].y0 >= y0 - 1]
        return i, y0, max(palabras + recuadros + [im["bbox"][3] for im in p.get_image_info()])
    raise AssertionError("R6 no salió")


class TestR6QuedaDondeEstabaSinElBloque:
    """No usan `posicion_inicial`: la rama que NO debe cambiar. Pasan igual contra el generador de HEAD y contra el nuevo."""

    @pytest.mark.parametrize("n,con_pelicula", CASOS_R6_SIN_BLOQUE)
    def test_r6_termina_siempre_sobre_la_franja_de_la_firma(self, app, n, con_pelicula):
        _, _, borde_inferior = _r6_en(_doc_sin_bloque(n, con_pelicula))
        assert borde_inferior <= Y_MAXIMO_DEL_CONTENIDO + 0.01, f"R6 invade la franja de la firma: y1={borde_inferior:.2f} > {Y_MAXIMO_DEL_CONTENIDO}"

    def test_donde_arranca_r6_en_las_paginas_nuevas_es_lo_medido_contra_head(self, app):
        arranques = set()
        for n, con_pelicula in CASOS_R6_SIN_BLOQUE:
            doc = _doc_sin_bloque(n, con_pelicula)
            pagina, y0, _ = _r6_en(doc)
            if pagina >= 1 and not doc[pagina].search_for("Prueba número"):      # R6 en una página SIN filas de la tabla principal: hubo un salto
                arranques.add(round(y0, 2))
        assert arranques == Y0_R6_EN_PAGINA_NUEVA, f"R6 arranca en {sorted(arranques)}; HEAD: {sorted(Y0_R6_EN_PAGINA_NUEVA)}"


# ----------------------------------------------------------------------------------------------- lo visual, contra R6 en el mismo PDF

def _cabecera_con_span(doc, titulo):
    """(página, caja azul, rect del título, span del título) de la tabla que empieza con `titulo`."""
    pagina, caja = _cabecera(doc, titulo)
    rect = doc[pagina].search_for(titulo)[0]
    span = next(s for b in doc[pagina].get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"] if titulo in s["text"])
    return doc[pagina], caja, rect, span


def _anchos_de_trazo(pagina, caja, alto):
    """Grosores de línea de lo dibujado dentro de la tabla que empieza en `caja` (y llega `alto` pt más abajo)."""
    return {round(d["width"], 2) for d in pagina.get_drawings()
            if d.get("width") and d["rect"].y0 >= caja.y0 - 1 and d["rect"].y1 <= caja.y0 + alto and d["rect"].x0 >= 79 and d["rect"].x1 <= 533}


class TestElBloqueEsVisualmenteComoR6:
    """Lo que el plan llama «la cabecera de R6»: medido en el MISMO PDF contra «Análisis de la placa», no contra constantes del test."""

    def test_la_cabecera_es_la_de_r6_en_alto_ancho_margen_alineacion_y_letra(self):
        doc = fitz.open(stream=_pdf(_df(5, "sin_pelicula"), TEXTO_TIPICO), filetype="pdf")
        _, caja_r6, rect_r6, span_r6 = _cabecera_con_span(doc, "Análisis de la placa")
        _, caja_bl, rect_bl, span_bl = _cabecera_con_span(doc, TITULO)
        assert caja_bl.height == pytest.approx(caja_r6.height, abs=0.1)                         # BOTTOMPADDING y tamaño de letra
        assert (caja_bl.x0, caja_bl.width) == pytest.approx((caja_r6.x0, caja_r6.width), abs=0.1)  # mismo margen izquierdo y ancho
        assert rect_bl.x0 - caja_bl.x0 == pytest.approx(rect_r6.x0 - caja_r6.x0, abs=0.1)       # título alineado igual (a la izquierda)
        assert rect_bl.y0 - caja_bl.y0 == pytest.approx(rect_r6.y0 - caja_r6.y0, abs=0.1)       # y a la misma altura dentro de la caja
        assert (span_bl["font"], round(span_bl["size"], 2)) == (span_r6["font"], round(span_r6["size"], 2))

    @pytest.mark.parametrize("r6", ["sin", "sin_pelicula", "con_pelicula"])
    def test_diez_puntos_de_separacion_con_lo_de_arriba(self, r6):
        doc = fitz.open(stream=_pdf(_df(2, r6), TEXTO_TIPICO), filetype="pdf")
        pagina, caja, _, _ = _cabecera_con_span(doc, TITULO)
        previos = [d["rect"].y1 for d in pagina.get_drawings() if d["rect"].y1 < caja.y0 - 3 and d["rect"].width > 20]
        previos += [i["bbox"][3] for i in pagina.get_image_info() if i["bbox"][3] < caja.y0 - 3]
        assert caja.y0 - max(previos) == pytest.approx(10, abs=0.1), "la tabla del bloque debe quedar a 10 pt de lo de arriba"

    def test_la_rejilla_tiene_el_grosor_de_la_de_r6(self):
        doc = fitz.open(stream=_pdf(_df(5, "sin_pelicula"), TEXTO_TIPICO), filetype="pdf")
        pagina, caja_r6, _, _ = _cabecera_con_span(doc, "Análisis de la placa")
        _, caja_bl, _, _ = _cabecera_con_span(doc, TITULO)
        assert _anchos_de_trazo(pagina, caja_bl, 40) == _anchos_de_trazo(pagina, caja_r6, 40) != set()

    def test_la_cabecera_lleva_el_fondo_de_r6(self):
        """La cabecera del bloque es la de la tabla de R6 (el mismo estilo, no otro): fondo #01b0ca y letra blanca en negrita."""
        doc = fitz.open(stream=_pdf(_df(5, "sin_pelicula"), TEXTO_TIPICO), filetype="pdf")
        pagina, rect = _cabecera(doc, TITULO)
        spans = [s for b in doc[pagina].get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"] if TITULO in s["text"]]
        assert rect.height > 15 and spans and all(s["color"] == 0xFFFFFF and "Bold" in s["font"] for s in spans), spans


# ------------------------------------------------------------------------------------ la unidad no se separa de su cifra

def _registro_sin_banda(px, u_px=1.2):
    """Un registro guardado de la rama «sin banda de tránsito» (no se sabe de qué lado de la marca cae la línea): el texto más largo con
    milímetros (~160 caracteres, 2 renglones), el que partía «1.0» de «mm)»."""
    return {"estado_gris": "ok", "desfase_gris_px": px, "incertidumbre_gris_px": u_px, "tamano_pixel_mm": 25.4 / 600, "dpi": 600,
            "lado_transito": None, "fecha": "2026-06-26", "tolerancia_mm": 1.0}


def _renglones_del_bloque(pdf):
    """Los renglones del texto del bloque (debajo de su cabecera, sobre la franja de la firma), en orden, tal como los pinta el PDF."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        pagina, rect = _cabecera(doc, TITULO)
        lineas = [l for b in doc[pagina].get_text("dict")["blocks"] for l in b.get("lines", [])
                  if l["bbox"][1] > rect.y1 - 1 and l["bbox"][3] < Y_MAXIMO_DEL_CONTENIDO]
        return ["".join(s["text"] for s in l["spans"]) for l in sorted(lineas, key=lambda l: l["bbox"][1])]
    finally:
        doc.close()


def _cortes_entre_cifra_y_unidad(renglones):
    """Los pares de renglones consecutivos donde uno termina en una cifra y el siguiente empieza por su unidad."""
    return [(a, b) for a, b in zip(renglones, renglones[1:]) if re.search(r"\d$", a.rstrip()) and re.match(r"(mm|px|dpi)\b", b.lstrip())]


class TestLaUnidadNoSeSeparaDeSuCifra:
    ESPACIO_DURO = "\u00a0"

    def test_une_la_cifra_con_mm_px_y_dpi_y_nada_mas(self):
        assert svc.unir_numero_y_unidad("0.42 ± 0.08 mm (k = 2). Cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-06-26") == (
            "0.42 ± 0.08\u00a0mm (k = 2). Cumple (tolerancia 1.0\u00a0mm). Cambio de fuente del 2026-06-26")
        assert svc.unir_numero_y_unidad("-8.55 ± 2.12 px (k = 2); la imagen declara 300 dpi y el procedimiento es de 600 dpi") == (
            "-8.55 ± 2.12\u00a0px (k = 2); la imagen declara 300\u00a0dpi y el procedimiento es de 600\u00a0dpi")
        # lo que no es una cifra seguida de su unidad no se toca (la palabra «milimetros», una unidad sin cifra, una cifra sin unidad)
        for intacto in ("Sin milimetros ni veredicto", "la unidad mm sola", "(k = 2), antes de la marca", "No medible: la linea tapa el borde",
                        "5 mmx y 7 pxs", ""):                       # una unidad es la palabra entera (mm, px, dpi), no un prefijo
            assert svc.unir_numero_y_unidad(intacto) == intacto

    @pytest.mark.parametrize("estado,px,tam,dpi,lado", [
        ("ok", -14.3, 25.4 / 600, 600, None), ("ok", 7.5, 25.4 / 600, 600, "izquierda"), ("ok", -8.55, None, 300, None),
        ("ok", 3.0, None, None, None), ("no medible: la linea tapa el borde de la meseta", None, None, 600, None)])
    def test_solo_cambian_los_espacios_el_texto_es_el_mismo(self, estado, px, tam, dpi, lado):
        registro = dict(_registro_sin_banda(px), estado_gris=estado, tamano_pixel_mm=tam, dpi=dpi, lado_transito=lado)
        original = svc.texto_breve(registro)
        unido = svc.unir_numero_y_unidad(original)
        assert unido.replace(self.ESPACIO_DURO, " ") == original, "unir la cifra con su unidad solo puede cambiar espacios"

    def test_texto_para_pdf_es_el_texto_breve_con_la_unidad_unida(self, app, bd_temporal):
        _sembrar_fuentes(bd_temporal)
        crudo = svc.texto_breve(svc.posicion_inicial_para("2026-01-10"))
        impreso = svc.texto_para_pdf("2026-01-10")
        assert self.ESPACIO_DURO in impreso and self.ESPACIO_DURO not in crudo, "el texto del PDF debe llevar el espacio duro y el breve no"
        assert impreso == svc.unir_numero_y_unidad(crudo)

    def test_en_el_pdf_ninguna_unidad_queda_sola_al_principio_de_un_renglon(self, app):
        """Sobre el PDF real y un barrido de desfases de la rama más larga: con la unión no se parte ninguna cifra de su unidad; sin ella
        (control: el mismo barrido con el texto crudo) sí se parte, o la prueba no estaría viendo nada (Trampa 8)."""
        unidos, crudos = [], []
        for px in range(-30, 31):
            crudo = svc.texto_breve(_registro_sin_banda(px))
            unidos += _cortes_entre_cifra_y_unidad(_renglones_del_bloque(_pdf(_df_rapido(5, "sin"), svc.unir_numero_y_unidad(crudo))))
            crudos += _cortes_entre_cifra_y_unidad(_renglones_del_bloque(_pdf(_df_rapido(5, "sin"), crudo)))
        assert crudos, "el barrido no parte ninguna unidad sin la unión: no discrimina"
        assert not unidos, f"con la unión, {len(unidos)} unidades quedaron separadas de su cifra: {unidos[:2]}"


# --------------------------------------------------------------------------------------------------- el cableado de reporte()

def _insertar_braqui(bd, fecha, con_analisis=True):
    bd.con.execute("INSERT INTO braqui (date, user_id, int_con_box, tol_rep_act_ci, tol_cyc_dummy, promedio, desviacion, pelicula) "
                   "VALUES (?, 'Físico de Prueba', 1, 5.5, 100, ?, ?, ?)",
                   (fecha, 9.99 if con_analisis else None, 0.06 if con_analisis else None, PELICULA if con_analisis else None))
    bd.con.commit()


def _sembrar_fuentes(bd):
    """Dos cambios de fuente (S1 = 2026-01-10 serie A, S2 = 2026-04-15 serie B) y la prueba P1 de S1 guardada de verdad."""
    for fecha, serie in (("2026-01-10 15:03:03", "24-05-0001-A"), ("2026-04-15 09:30:00", "24-05-0002-B")):
        bd.con.execute("INSERT INTO TipoCalibracion (user, fecha, tipo, serie, activo) VALUES ('Siembra', ?, 'Cambio de fuente', ?, 1)",
                       (fecha, serie))
    bd.con.commit()
    imagen, puntos = _sintetica(-0.6)
    return svc.guardar(USUARIO, "2026-01-10", imagen, "placa.png", puntos)


FECHAS = ["2026-01-09", "2026-01-10", "2026-03-01", "2026-04-14", "2026-04-15"]


class TestElCableadoDeReporte:
    def test_las_cinco_fechas_del_plan(self, app, bd_temporal, monkeypatch):
        for fecha in FECHAS:
            _insertar_braqui(bd_temporal, fecha)
        _sembrar_fuentes(bd_temporal)
        esperado = _normal(svc.texto_breve(svc.posicion_inicial_para("2026-01-10")))
        for fecha, con_bloque in zip(FECHAS, (False, True, True, True, False)):
            texto, _ = _capturar_pdf(monkeypatch, fecha, "Gammamed Plus i X", DICC_BRAQUI, "si")
            normal = _normal(texto)
            assert normal.count(TITULO) == (1 if con_bloque else 0), fecha
            assert normal.count(esperado) == (1 if con_bloque else 0), fecha
            assert "Análisis de la placa" in texto
            if con_bloque:
                assert texto.index("Análisis de la placa") < texto.index(TITULO), "el bloque va DESPUÉS de R6"

    def test_sin_ninguna_prueba_no_hay_bloque(self, app, bd_temporal, monkeypatch):
        for fecha in FECHAS:
            _insertar_braqui(bd_temporal, fecha)
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-01", "Gammamed Plus i X", DICC_BRAQUI, "si")
        assert TITULO not in texto

    def test_con_la_prueba_anulada_ningun_diario_la_dice(self, app, bd_temporal, monkeypatch):
        for fecha in FECHAS:
            _insertar_braqui(bd_temporal, fecha)
        svc.anular(_sembrar_fuentes(bd_temporal), USUARIO, "prueba")
        for fecha in FECHAS:
            texto, _ = _capturar_pdf(monkeypatch, fecha, "Gammamed Plus i X", DICC_BRAQUI, "si")
            assert TITULO not in texto, fecha

    def test_un_diario_sin_analisis_ni_pelicula_tambien_lleva_el_bloque(self, app, bd_temporal, monkeypatch):
        _insertar_braqui(bd_temporal, "2026-03-01", con_analisis=False)
        _sembrar_fuentes(bd_temporal)
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-01", "Gammamed Plus i X", DICC_BRAQUI, "si")
        assert TITULO in texto and "Análisis de la placa" not in texto

    @pytest.mark.parametrize("error", [RuntimeError("la BD no responde"), sqlite3.OperationalError("database is locked"),
                                       ValueError("fecha ilegible"), KeyError("serie"), OSError("disco")], ids=lambda e: type(e).__name__)
    def test_un_fallo_del_servicio_de_cualquier_tipo_avisa_dice_la_causa_y_no_genera_el_pdf(self, app, bd_temporal, monkeypatch, error):
        """Si el `except` de `reporte()` atrapara solo un tipo de excepción, cualquier otro escaparía: en la app (sin consola) el slot
        de Qt la traga y el físico pulsa «Reporte» y no ve ni PDF ni aviso. Y el aviso tiene que decir CUÁL fue el fallo."""
        _insertar_braqui(bd_temporal, "2026-03-01")
        _sembrar_fuentes(bd_temporal)
        avisos, visores = [], []

        def revienta(*a, **k):
            raise error

        class _Visor:
            def __init__(self, *a, **k):
                visores.append(1)

            def show(self):
                visores.append(1)

        monkeypatch.setattr(svc, "texto_para_pdf", revienta)
        monkeypatch.setattr(reportes_mod, "PdfViewer", _Visor)
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a)))
        reportes_mod.reporte(_AutoDB(), fecha="2026-03-01", maquina="Gammamed Plus i X", id_maquina="", tipo_reporte="diario",
                             diccionario=DICC_BRAQUI, umbrales="si", file_name="")
        assert visores == [] and len(avisos) == 1 and "posición inicial" in avisos[0][2]
        assert str(error) in avisos[0][2], "el aviso no dice cuál fue el fallo"

    @pytest.mark.parametrize("maquina,tabla,dicc,columnas", [
        ("Clinac 600", "aceleradorlineal_600", DICC_600, "(date, user_id, luces_consola, laseres, dosis_referencia) VALUES ('2026-03-01','Físico de Prueba',1,1,2.0)"),
        ("iX", "aceleradorlineal_ix", {"observaciones": ["Observaciones", "", "Na"]}, "(date, user_id) VALUES ('2026-03-01','Físico de Prueba')"),
        ("HALCYON", "halcyon", DICC_HALCYON, "(date, user_id, BeamOutputChange, CouchLat) VALUES ('2026-03-01','Físico de Prueba', 0.0, 0.0)"),
    ])
    def test_las_otras_maquinas_no_consultan_el_servicio_ni_llevan_el_bloque(self, app, bd_temporal, monkeypatch, maquina, tabla, dicc, columnas):
        bd_temporal.con.execute(f"INSERT INTO {tabla} {columnas}")
        bd_temporal.con.commit()
        _sembrar_fuentes(bd_temporal)
        consultas = []
        # CUENTA la consulta: lanzar una excepción la traga el `except` de `reporte()` y el PDF saldría igual sin el bloque
        monkeypatch.setattr(svc, "texto_para_pdf", lambda *a, **k: consultas.append(a))
        texto, _ = _capturar_pdf(monkeypatch, "2026-03-01", maquina, dicc, "si")
        assert consultas == [], f"el diario de {maquina} consultó la posición inicial {len(consultas)} vez/veces"
        assert TITULO not in texto
