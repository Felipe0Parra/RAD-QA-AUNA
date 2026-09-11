"""C.5 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4): pdf.py imprimía
"Promedio [mm]" sin decir promedio DE QUÉ. Petición directa del físico
sobre la tabla nueva de R6 (resumen de placa de braqui), su primera
revisión con datos reales delante.

El paréntesis aquí NO es una unidad -- es una aclaración ("de qué es el
promedio"), así que se conserva como paréntesis y la unidad sigue en
corchetes: "Promedio (distancia entre líneas) [mm]".

Va DESPUÉS de C.4 a propósito (el plan lo advierte): la etiqueta se
alarga y la columna del resumen (225 pt, sin Paragraph) tiene que poder
con ella al tamaño de letra que C.4 dejó fijado.
"""
from pathlib import Path

from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parent.parent
PDF_PY = ROOT / "models" / "PDF" / "pdf.py"

ANCHO_COLUMNA_RESUMEN_PT = 225 - 12  # colWidths=[225, 225], padding 6+6


class TestLasFilasDicenDeQueSonPromedioYDesviacion:
    def test_promedio_dice_de_que(self):
        texto = PDF_PY.read_text(encoding="utf-8")
        assert "'Promedio (distancia entre líneas) [mm]'" in texto
        assert "'Promedio [mm]'" not in texto

    def test_desviacion_dice_de_que(self):
        texto = PDF_PY.read_text(encoding="utf-8")
        assert "'Desviación estándar (distancia entre líneas) [mm]'" in texto
        assert "'Desviación estándar [mm]'" not in texto

    def test_las_dos_etiquetas_caben_en_la_columna_del_resumen(self):
        """C.4 dejó la tabla de resumen en CUERPO_TABLA_PT (8 pt) -- las
        etiquetas alargadas deben seguir cabiendo en una sola línea (esta
        tabla no envuelve en Paragraph)."""
        import models.PDF.pdf as pdf_mod
        for etiqueta in (
            "Promedio (distancia entre líneas) [mm]",
            "Desviación estándar (distancia entre líneas) [mm]",
        ):
            ancho = stringWidth(etiqueta, "Helvetica", pdf_mod.CUERPO_TABLA_PT)
            assert ancho <= ANCHO_COLUMNA_RESUMEN_PT, (
                f"{etiqueta!r} mide {ancho:.1f} pt, más que los "
                f"{ANCHO_COLUMNA_RESUMEN_PT} pt útiles de la columna")
