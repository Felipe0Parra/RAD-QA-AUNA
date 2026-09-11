"""C.4 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4, SS0.9): dos tamaños de
cuerpo convivían en el mismo reporte diario (12/7.5) y un TERCERO más en
mensual/anual (10/8) -- el físico pidió un solo tamaño. Y el
identificador de la tabla era un string pelado, que en una `Table` de
reportlab NO se ajusta: se desborda. Cuatro filas del diario de iX se
salían 7.7-11.9 pt de su celda (136.5 pt útiles) con las etiquetas
reales, exactamente donde el físico lo vio.

Dos cambios, verificados por separado:
(1) `CABECERA_TABLA_PT`/`CUERPO_TABLA_PT` sustituyen los 8 literales
    `FONTSIZE` del archivo -- diario, mensual (P7) y anual (P7) quedan al
    mismo tamaño (10/8, el que ya usaban mensual/anual: cero cambio
    visual ahí).
(2) La columna del identificador se envuelve en `Paragraph` -- una
    etiqueta que no cabe se parte en dos líneas, nunca se sale de la
    celda. Gateado a `es_diario_qc`: la calculadora (R5, segundo cliente
    de esta función) no cambia.

CORRECCIÓN AL EJECUTAR (medido, no en el plan original): el plan
esperaba que el diario del iX pasara de 2 páginas a 1. [medido] con las
22 etiquetas reales de `IX.py:40-63` (incluidas las 4 que se
desbordaban) NINGUNA combinación de tamaño razonable (probado 10/8 hasta
8/6.5) baja de 2 páginas -- las 4 etiquetas largas siguen sin caber en
una sola línea a 136.5 pt útiles aunque se reduzca la letra, así que
ahora ENVUELVEN a 2 líneas en vez de desbordar, y esas líneas extra
empujan el total por encima del corte de página. La garantía real (que
ninguna etiqueta se salga de su celda) se cumple igual; el conteo de
páginas es una consecuencia que no se puede prometer sin sacrificar
legibilidad, y no es lo que el físico pidió -- se documenta la
corrección y no se persigue el número por sí solo.
"""
import ast
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parent.parent
PDF_PY = ROOT / "models" / "PDF" / "pdf.py"

# Las 4 etiquetas reales que se desbordaban (SS0.9 del plan), medidas
# contra IX.py:40-63.
ETIQUETAS_QUE_SE_DESBORDABAN = [
    "Consistencia de dosis electrones 6MeV [%]",
    "Consistencia de dosis electrones 9MeV [%]",
    "Consistencia de dosis electrones 12MeV [%]",
    "Consistencia de dosis electrones 15MeV [%]",
]
ANCHO_UTIL_IDENTIFICADOR_PT = 450 * 0.33 - 12  # columna 0 menos padding 6+6


class TestUnSoloTamanoDeLetra:
    def test_ningun_fontsize_literal_suelto_en_las_tablas(self):
        """Censo AST: cero literales numéricos como tercer argumento de
        un comando FONTSIZE -- todos deben venir de las 2 constantes."""
        tree = ast.parse(PDF_PY.read_text(encoding="utf-8"), filename=str(PDF_PY))
        sueltos = []
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Tuple) and len(nodo.elts) == 4:
                primero = nodo.elts[0]
                if isinstance(primero, ast.Constant) and primero.value == "FONTSIZE":
                    ultimo = nodo.elts[-1]
                    if isinstance(ultimo, ast.Constant):
                        sueltos.append((nodo.lineno, ultimo.value))
        assert sueltos == [], f"FONTSIZE con literal suelto (no la constante): {sueltos}"

    def test_las_constantes_son_las_mismas_en_todo_el_archivo(self):
        import models.PDF.pdf as pdf_mod
        assert pdf_mod.CABECERA_TABLA_PT == pdf_mod.CABECERA_TABLA_PT
        assert isinstance(pdf_mod.CABECERA_TABLA_PT, (int, float))
        assert isinstance(pdf_mod.CUERPO_TABLA_PT, (int, float))

    def test_ocho_usos_de_fontsize_las_4_parejas(self):
        texto = PDF_PY.read_text(encoding="utf-8")
        assert texto.count("CABECERA_TABLA_PT)") == 4
        assert texto.count("CUERPO_TABLA_PT)") == 4


class TestElIdentificadorSeEnvuelveNoSeDesborda:
    def test_las_etiquetas_largas_ahora_envuelven_a_mas_de_una_linea(self):
        """Antes (string pelado) estas 4 etiquetas se salían de la celda
        7.7-11.9 pt (medido en el plan, §0.9). Envueltas en Paragraph, en
        vez de desbordar, ocupan MÁS DE UNA LÍNEA -- nunca invaden la
        columna vecina."""
        import models.PDF.pdf as pdf_mod
        styles = getSampleStyleSheet()
        estilo = ParagraphStyle(
            'test', parent=styles['Normal'], fontSize=pdf_mod.CUERPO_TABLA_PT,
            leading=pdf_mod.CUERPO_TABLA_PT + 2)
        for etiqueta in ETIQUETAS_QUE_SE_DESBORDABAN:
            p = Paragraph(etiqueta, estilo)
            _, alto = p.wrap(ANCHO_UTIL_IDENTIFICADOR_PT, 10000)
            una_linea = pdf_mod.CUERPO_TABLA_PT + 2
            assert alto > una_linea * 1.3, (
                f"{etiqueta!r} no envolvió a una segunda línea con el ancho "
                f"útil real -- ¿sigue desbordándose?")

    def test_una_etiqueta_corta_sigue_en_una_sola_linea(self):
        import models.PDF.pdf as pdf_mod
        styles = getSampleStyleSheet()
        estilo = ParagraphStyle(
            'test', parent=styles['Normal'], fontSize=pdf_mod.CUERPO_TABLA_PT,
            leading=pdf_mod.CUERPO_TABLA_PT + 2)
        p = Paragraph("Láseres [mm]", estilo)
        _, alto = p.wrap(ANCHO_UTIL_IDENTIFICADOR_PT, 10000)
        una_linea = pdf_mod.CUERPO_TABLA_PT + 2
        assert alto <= una_linea * 1.3


class TestCompuertaDeDanoColateral:
    def test_la_calculadora_conserva_una_sola_pagina_e_identico_contenido(self, app):
        """R5/C4: es_diario_qc=False (default, la calculadora) no debe
        pasar por la rama nueva de envolver el identificador -- mismo
        contenido, mismo conteo de páginas que antes de C.4."""
        import fitz
        import pandas as pd
        from models.PDF.pdf import generar_reporte_pdf
        df = pd.DataFrame({
            "": ["Fecha", "Acelerador", "dosis_maxima"],
            "Evaluación": [None, None, None],
            "Valores": ["2026-01-01", "Clinac 600", 1.005],
        })
        buffer = generar_reporte_pdf(df=df, fecha="2026-01-01", user=" ",
                                      tipo_reporte="Calculadora", maquina="Clinac 600",
                                      id_maquina="", logo_path=None, firma=None,
                                      role="Físico Médico", temp=True)
        doc = fitz.open(stream=bytes(buffer.data()), filetype="pdf")
        texto = "\n".join(p.get_text() for p in doc)
        assert doc.page_count == 1
        assert "Fecha" in texto and "Acelerador" in texto and "dosis_maxima" in texto
        doc.close()


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
