"""B.2 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS3, DP-96-E2): el reporte
mensual de braquiterapia dice `(U/A)` para el factor de calibracion de la
camara de pozo -- `U` es una unidad REAL de braquiterapia (1 U = 1
uGy*m2/h), asi que el error es plausible y peligroso. La propia app ya
declara la unidad correcta en `equipos.py` (Gy*m2/h*A, fijada por
certificado en DA-26): el PDF debe decir lo mismo que el catalogo, no
inventar una cadena aparte.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTES = ROOT / "models" / "PDF" / "Mensuales" / "reportes_mensuales.py"
EQUIPOS = ROOT / "ui" / "paginasGuia" / "equipos.py"


def _unidad_canonica_de_equipos():
    """La cadena real que equipos.py ya usa para el factor de pozo
    (setPlaceholderText) -- fuente unica, no un literal copiado a mano."""
    texto = EQUIPOS.read_text(encoding="utf-8")
    match = re.search(r'Unidades:\s+([A-Za-z·²/]+)"\)', texto)
    assert match, "No se encontró la unidad del factor de pozo en equipos.py"
    return match.group(1)


class TestFactorDeCalibracionDePozo:
    def test_ningun_literal_dice_u_sobre_a(self):
        tree = ast.parse(REPORTES.read_text(encoding="utf-8"), filename=str(REPORTES))
        sospechosos = []
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                if "Factor de calibración" in nodo.value and "(U/A)" in nodo.value:
                    sospechosos.append(nodo.value)
        assert sospechosos == [], (
            f"Factor de calibración de pozo rotulado (U/A) -- U es una "
            f"unidad real de braquiterapia, el error es peligroso: {sospechosos}")

    def test_el_pdf_dice_la_misma_unidad_que_el_catalogo_de_equipos(self):
        unidad = _unidad_canonica_de_equipos()
        texto = REPORTES.read_text(encoding="utf-8")
        etiqueta = f"Factor de calibración [{unidad}]"
        assert texto.count(etiqueta) == 2, (
            f"Se esperaban 2 apariciones de {etiqueta!r} (una por función "
            f"duplicada, el reporte de calibración y el de cambio de fuente)")
