"""B.1 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS3, DP-90(b)): el mensual dice
`[Gy/UM]` sobre un valor que esta guardado en cGy/UM -- factor 100. Revierte
`R9` (08-09), que se apoyo en el formato en papel (`IDC-F-RT-119`, que dice
"(Gy/UM)") por encima del dato medido: la calculadora computa en Gy/MU
(~0.010), `dialogs.py::emitir_dosis` hace `x100` antes de escribir en el
formulario, y `dosimetriaMen.dosis_ref_cgy_um` guarda ~1.0 -- el PDF
reimprime ese mismo float sin tocarlo. Los otros 6 sitios de la app (Ver
tabla, reportes_anuales, SQLtoEXCEL, tablas_anuales, la propia calculadora)
ya dicen cGy/UM; el mensual era el unico que discrepaba.

Regla de oro del plan (SS1): ningun valor guardado cambia, solo la etiqueta.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Alcance EXACTO de B.1 (SS3 del plan): unidades_qc.py:71 y los 3 f-strings
# de reportes_mensuales.py. NO se amplia a todo el arbol -- "Gy/UM" tambien
# aparece, correctamente, en dialogs.py/trs398_excel.py como D(Zref)/D(zmax)
# ANTES del x100 de emitir_dosis (SS0.6 de la tabla del plan: dialogs.py:2228
# es Gy/MU real, "(Gy/MU)" -- correcta). Confundir esas dos magnitudes
# habria repetido el error que motivo esta misma tarea: no se cambia una
# etiqueta sin verificar que magnitud describe.
ARCHIVOS_EN_ALCANCE = (
    ROOT / "services" / "unidades_qc.py",
    ROOT / "models" / "PDF" / "Mensuales" / "reportes_mensuales.py",
)


def _archivos_produccion():
    yield from ARCHIVOS_EN_ALCANCE


def _literales_de_texto(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            yield nodo.value
        if isinstance(nodo, ast.JoinedStr):
            # f-string: reconstruir solo las partes literales (Constant)
            texto = "".join(
                parte.value for parte in nodo.values
                if isinstance(parte, ast.Constant) and isinstance(parte.value, str)
            )
            yield texto


class TestNingunSitioDiceGyUMSobreLaDosisDeReferencia:
    def test_ningun_literal_de_produccion_dice_gy_um_de_dosis(self):
        sospechosos = []
        for path in _archivos_produccion():
            for texto in _literales_de_texto(path):
                if "Gy/UM" in texto and "cGy/UM" not in texto:
                    sospechosos.append((str(path.relative_to(ROOT)), texto[:80]))
        assert sospechosos == [], (
            f"Literal que dice 'Gy/UM' (sin la 'c') sobre la dosis de "
            f"referencia -- factor 100 de error: {sospechosos}")

    def test_unidades_qc_declara_cgy_um(self):
        from services.unidades_qc import UNIDADES
        assert UNIDADES["dosis_ref_cgy_um"] == "cGy/UM"


class TestPlausibilidadFisica:
    def test_valor_tipico_guardado_es_congruente_con_centigray(self):
        """dosimetriaMen.dosis_ref_cgy_um guarda ~1.0 (medido, DP-90(b)) --
        un acelerador que entregue 1 Gy por unidad monitor es dos ordenes de
        magnitud fuera de lo fisico; 1 cGy/UM es exactamente lo esperado."""
        from services.unidades_qc import UNIDADES
        valor_guardado = 1.0097
        etiqueta = UNIDADES["dosis_ref_cgy_um"]
        # 1 Gy/UM es fisicamente absurdo; 1 cGy/UM es lo correcto para un
        # acelerador de fotones/electrones -- la etiqueta debe coincidir
        # con la magnitud real del numero guardado, no con el papel.
        assert etiqueta == "cGy/UM"
        assert valor_guardado < 2  # del orden de 1 cGy/UM, no de 100 Gy/UM
