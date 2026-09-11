"""C.3 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4, SS0.10): el bloque de firma
se dibujaba UNA sola vez, al final -- por construcción caía solo en la
última página. El diario de braqui pagina cuando la placa no cabe; su
primera página salía sin firma.

`_dibujar_firma_en_pagina_actual` se extrae y se llama antes de CADA
`c.showPage()` además de al final -- gateado a `es_diario_qc=True`, para
no tocar el comportamiento de la calculadora de dosis (segundo cliente de
esta misma función, R5/C4 -- compuerta de cero diferencias).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pandas as pd
import pytest
from PyQt5.QtWidgets import QApplication

from models.PDF.pdf import generar_reporte_pdf


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _df_forzar_paginacion(n_filas=60):
    """Muchas filas con identificadores/valores simples, más
    'promedio'/'desviacion' (R6: dispara el bloque de resumen de la
    placa de braqui) -- [medido] con esta combinación produce 3 páginas,
    no 2: la tabla principal sola solo llega a 2 (reportlab reparte el
    excedente en un único segundo bloque, sin volver a paginar), así que
    hace falta el bloque R6 para que haya una página INTERMEDIA -- sin
    firma de encabezado (que solo está en la página 1) ni de cierre (que
    antes de C.3 solo estaba en la última) -- donde el defecto era visible."""
    filas = [f"Prueba número {i} de la lista de verificación diaria" for i in range(n_filas)]
    valores = ["Funciona"] * n_filas
    evaluacion = [None] * n_filas
    filas += ["promedio", "desviacion"]
    valores += [1.234, 0.056]
    evaluacion += [None, None]
    return pd.DataFrame({"": filas, "Evaluación": evaluacion, "Valores": valores})


class TestFirmaEnTodasLasPaginasDelDiario:
    def test_el_diario_pagina_de_verdad(self, app):
        """Rojo-antes-que-verde para el propio experimento: si esto diera
        1 sola página, el test no probaría nada."""
        buffer = generar_reporte_pdf(
            df=_df_forzar_paginacion(), fecha="2026-01-01", user="Físico de Prueba",
            tipo_reporte="Diario", maquina="Clinac 600", id_maquina="",
            logo_path=None, firma=None, role="Físico Médico", temp=True,
            es_diario_qc=True)
        doc = fitz.open(stream=bytes(buffer.data()), filetype="pdf")
        paginas = doc.page_count
        doc.close()
        assert paginas >= 3, (
            "menos de 3 páginas -- sin una página INTERMEDIA (sin el "
            "encabezado de la página 1 ni el cierre de la última), el "
            "experimento no discrimina el defecto que C.3 corrige")

    def test_firma_aparece_en_cada_pagina(self, app):
        usuario = "Físico de Prueba Firma Unica"
        buffer = generar_reporte_pdf(
            df=_df_forzar_paginacion(), fecha="2026-01-01", user=usuario,
            tipo_reporte="Diario", maquina="Clinac 600", id_maquina="",
            logo_path=None, firma=None, role="Físico Médico", temp=True,
            es_diario_qc=True)
        doc = fitz.open(stream=bytes(buffer.data()), filetype="pdf")
        assert doc.page_count >= 2
        total_paginas = doc.page_count
        paginas_sin_firma = [
            i for i in range(total_paginas)
            if usuario not in doc[i].get_text()
        ]
        doc.close()
        assert paginas_sin_firma == [], (
            f"páginas sin firma: {paginas_sin_firma} de {total_paginas}")


class TestLaCalculadoraNoCambia:
    def test_calculadora_una_pagina_sigue_con_una_sola_firma(self, app):
        """Compuerta de daño colateral: es_diario_qc=False (default) no
        pasa por ninguna de las llamadas nuevas -- solo dibuja al final,
        como siempre. Con una sola página no hay forma de que difiera,
        pero lo afirma explícitamente para que quede escrito."""
        df = pd.DataFrame({
            "": ["Fecha", "Acelerador", "dosis_maxima"],
            "Evaluación": [None, None, None],
            "Valores": ["2026-01-01", "Clinac 600", 1.005],
        })
        usuario = "Físico Calculadora"
        buffer = generar_reporte_pdf(
            df=df, fecha="2026-01-01", user=usuario, tipo_reporte="Calculadora",
            maquina="Clinac 600", id_maquina="", logo_path=None, firma=None,
            role="Físico Médico", temp=True)
        doc = fitz.open(stream=bytes(buffer.data()), filetype="pdf")
        assert doc.page_count == 1
        apariciones = sum(1 for i in range(doc.page_count) if usuario in doc[i].get_text())
        doc.close()
        assert apariciones == 1
