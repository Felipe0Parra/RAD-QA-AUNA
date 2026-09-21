"""A.3 (PLAN_REFERENCIAS_EDITABLES_21-09.md): el campo dice qué magnitud
espera, y deja de mandar escribir un `1`.

§0.4-bis: `val_teo_{energia}` (el campo de calidad de referencia) tenía --
medido en `data/widgets.xlsx` -- una etiqueta que no nombra la magnitud
("Valor teórico (Discrepancia):") y un placeholder que en las hojas del iX
decía literalmente **"Escribir 1"**: una instrucción de OTRO campo (la dosis
de referencia, 1 cGy/UM) pegada al de la calidad. Obedecerla da una
discrepancia del 38 % (`|100 × (1 − 0.62/1)|`). Medido también que el 600 y
el Halcyon tenían el mismo defecto con OTRO texto ("1" y "Resultado" --
ninguno nombra la magnitud PDD20/10/J2/J1 tampoco), corrigiendo la
caracterización inicial del plan (que asumía "Escribir 1" en las 3 hojas).

Además, 5 de las 6 etiquetas `tolerancia_calidad_{e}` del iX estaban en
blanco (`'                        '`); solo 12mev decía "Tolerancia (%)".

Rojo-antes-que-verde real: verificado contra el `.xlsx` de antes de este
commit (ninguna etiqueta afirmaba estos textos -- el rojo se fabricó
comparando manualmente el valor viejo/nuevo antes de escribir, ver el
propio commit). Round-trip de openpyxl + diff celda a celda de las 30 hojas
confirmado en la ejecución: exactamente 21 celdas cambiaron, ninguna otra.
"""
import pandas as pd
import pytest

RUTA = "data/widgets.xlsx"

FOTONES = ("6mv", "15mv")
ELECTRONES = ("6mev", "9mev", "12mev", "15mev")

LABEL_FOTON = "Calidad de referencia (PDD20/10):"
LABEL_ELECTRON = "Calidad de referencia (J2/J1):"
PLACEHOLDER_FOTON = "p. ej. 0.665"
PLACEHOLDER_ELECTRON = "p. ej. 0.483"
TOLERANCIA_OK = "Tolerancia (%)"


def _hoja(nombre):
    return pd.read_excel(RUTA, sheet_name=nombre)


def _valor(df, nombre_widget):
    fila = df.loc[df["nombres"] == nombre_widget, "descripcion"]
    assert not fila.empty, f"widget '{nombre_widget}' no existe en la hoja"
    return fila.iloc[0]


class TestNingunPlaceholderPideEscribirUn1:
    """La instrucción que pertenecía a la dosis de referencia ya no puede
    aparecer en el campo de calidad, en ninguna de las 3 hojas mensuales."""

    def test_ix_ninguna_energia_dice_escribir_1(self):
        df = _hoja("preguntas_mensu_ix")
        for energia in FOTONES + ELECTRONES:
            valor = _valor(df, f"val_teo_{energia}")
            assert valor != "Escribir 1", energia
            assert "escribir" not in str(valor).lower(), energia

    def test_600_no_dice_un_1_pelado(self):
        df = _hoja("preguntas_mensu_600")
        valor = _valor(df, "val_teo_6mv")
        assert str(valor).strip() != "1"

    def test_halcyon_no_dice_resultado(self):
        """'Resultado' es el placeholder que usan los campos de SALIDA
        (discrepancia, calidad medida) -- val_teo es un campo de ENTRADA."""
        df = _hoja("preguntas_mensu_Halcyon")
        valor = _valor(df, "val_teo_6mv")
        assert valor != "Resultado"


class TestElRotuloNombraLaMagnitud:
    """lbl_val_teo_{e} pasa a decir lo mismo que la magnitud medida dos
    filas más abajo (calidad_pdd20_10 / calidad_j2_j1), con 'de referencia'
    -- para que se vea que las dos se comparan entre sí."""

    @pytest.mark.parametrize("hoja,energias", [
        ("preguntas_mensu_600", ["6mv"]),
        ("preguntas_mensu_ix", list(FOTONES + ELECTRONES)),
        ("preguntas_mensu_Halcyon", ["6mv"]),
    ])
    def test_rotulo_correcto_por_tipo_de_haz(self, hoja, energias):
        df = _hoja(hoja)
        for energia in energias:
            valor = _valor(df, f"lbl_val_teo_{energia}")
            esperado = LABEL_ELECTRON if energia.endswith("mev") else LABEL_FOTON
            assert valor == esperado, f"{hoja}::lbl_val_teo_{energia}"


class TestElPlaceholderOrienta:
    """Un ejemplo del orden de magnitud correcto, distinto por tipo de haz."""

    @pytest.mark.parametrize("hoja,energias", [
        ("preguntas_mensu_600", ["6mv"]),
        ("preguntas_mensu_ix", list(FOTONES + ELECTRONES)),
        ("preguntas_mensu_Halcyon", ["6mv"]),
    ])
    def test_placeholder_correcto_por_tipo_de_haz(self, hoja, energias):
        df = _hoja(hoja)
        for energia in energias:
            valor = _valor(df, f"val_teo_{energia}")
            esperado = PLACEHOLDER_ELECTRON if energia.endswith("mev") else PLACEHOLDER_FOTON
            assert valor == esperado, f"{hoja}::val_teo_{energia}"


class TestTolerenciaCalidadRotulada:
    """Las 6 tolerancias de calidad del iX quedan rotuladas igual entre sí
    -- antes 5 de 6 estaban en blanco, solo 12mev ya decía 'Tolerancia (%)'."""

    @pytest.mark.parametrize("energia", FOTONES + ELECTRONES)
    def test_las_seis_energias_dicen_tolerancia_porciento(self, energia):
        df = _hoja("preguntas_mensu_ix")
        valor = _valor(df, f"tolerancia_calidad_{energia}")
        assert valor == TOLERANCIA_OK, energia

    def test_600_y_halcyon_ya_estaban_bien_y_siguen_igual(self):
        """600 y Halcyon (una sola energía, sin sufijo) YA decían
        'Tolerancia (%)' antes de esta tarea -- no se tocaron."""
        for hoja in ("preguntas_mensu_600", "preguntas_mensu_Halcyon"):
            df = _hoja(hoja)
            assert _valor(df, "tolerancia_calidad") == TOLERANCIA_OK, hoja


class TestFueraDeAlcance:
    """§0.1: preguntas_anual_Halcyon queda fuera de esta tarea a propósito
    (es del anual, que este plan no toca) -- su placeholder ambiguo es
    deuda declarada, no un descuido de esta tarea. [medido 21-09, corrige
    la caracterización previa de CLAUDE.md/DP-108: el placeholder real es
    'Resultado' -- el mismo texto que tenía la hoja mensual de Halcyon
    antes de A.3 -- no 'Escribir 1' (ese es el de las 6 hojas del iX)."""

    def test_anual_halcyon_conserva_su_placeholder_ambiguo(self):
        df = _hoja("preguntas_anual_Halcyon")
        valor = _valor(df, "val_teo_6mv")
        assert valor == "Resultado"
