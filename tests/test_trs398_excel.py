"""Tests del lector de hojas TRS-398 del OIEA (Fase D3).

Dos capas:

1. Fixture SINTÉTICO (.xlsx generado en el momento con openpyxl): reproduce
   el layout fijo de la plantilla poniendo valores conocidos en las celdas
   mapeadas. Es determinista y corre en cualquier máquina sin depender de
   archivos externos ni de datos clínicos reales.

2. Validación OPCIONAL contra los .xls/.xlsm reales del físico (se salta sola
   con skipif si la carpeta ~/Documents/Archivos_UseApp no está): comprueba el
   descifrado VelvetSweatshop, el mapeo real y que el motor de la app
   reproduce los factores calculados por el Excel oficial.
"""
import os

import openpyxl
import pytest

from services.trs398_excel import (
    leer_trs398, comparar_trs398, CELDAS_ENTRADAS, CELDAS_CALCULADAS,
    _ref_a_indices, _normalizar,
)

# Caso realista: entradas del Halcyon con sus valores calculados por el Excel.
# Sirve para probar comparar_trs398 sin depender del archivo real.
DATOS_HALCYON = {
    "archivo": "test.xls",
    "entradas": {
        "T_clinica": 21.1, "P_clinica": 85.13, "T0": 22.0, "P0": 101.325,
        "Mplus": 5.525, "Mminus": 5.6, "M1_recomb": 5.525, "M2_recomb": 5.447,
        "a0": 1.198, "a1": -0.8753, "a2": 0.6773,
        "lectura_V1": 5.525, "unidades_monitor": 200.0,
        "tpr2010": 0.626, "factor_calibracion": 0.3034, "PDD_zref": 100.0,
    },
    "calculados": {
        "ktp": 1.1866096830385666, "kpol": 1.006787330316742,
        "ks": 1.0070023695467674, "Mq": 0.03323367808333775,
        "kQ": 0.9964, "Dzref": 0.010046798777934927,
        "dosis_maxima": 0.010046798777934927,
    },
}

CARPETA_REAL = os.path.expanduser("~/Documents/Archivos_UseApp")
HALCYON = os.path.join(CARPETA_REAL, "TRS-398 6 MV FFF Halcyon Dmax.xls")


# ── Capa 1: fixture sintético determinista ────────────────────────────────

# Valores testigo por clave lógica (números fáciles de rastrear en asserts).
ENTRADAS_TESTIGO = {k: float(i + 1) for i, k in enumerate(CELDAS_ENTRADAS)}
CALCULADOS_TESTIGO = {k: round(1.0 + i / 100, 3) for i, k in enumerate(CELDAS_CALCULADAS)}


@pytest.fixture
def xlsx_sintetico(tmp_path):
    """Construye un .xlsx con la hoja 'Sheet' y los valores testigo en las
    celdas exactas del mapeo, más un '#NAME?' para probar la normalización."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    for clave, valor in ENTRADAS_TESTIGO.items():
        ws[CELDAS_ENTRADAS[clave]] = valor
    for clave, valor in CALCULADOS_TESTIGO.items():
        ws[CELDAS_CALCULADAS[clave]] = valor
    # Simular una celda con error de fórmula (como el .xlsm real en kQ)
    ws[CELDAS_CALCULADAS["kQ"]] = "#NAME?"
    ruta = tmp_path / "sintetico.xlsx"
    wb.save(ruta)
    return str(ruta)


class TestMapeoBasico:
    def test_lee_todas_las_entradas(self, xlsx_sintetico):
        datos = leer_trs398(xlsx_sintetico)
        for clave, esperado in ENTRADAS_TESTIGO.items():
            assert datos["entradas"][clave] == esperado, clave

    def test_lee_todos_los_calculados(self, xlsx_sintetico):
        datos = leer_trs398(xlsx_sintetico)
        for clave, esperado in CALCULADOS_TESTIGO.items():
            if clave == "kQ":
                continue  # sobrescrito por #NAME? en el fixture
            assert datos["calculados"][clave] == esperado, clave

    def test_error_de_formula_se_normaliza_a_none(self, xlsx_sintetico):
        datos = leer_trs398(xlsx_sintetico)
        assert datos["calculados"]["kQ"] is None

    def test_incluye_nombre_de_archivo(self, xlsx_sintetico):
        assert leer_trs398(xlsx_sintetico)["archivo"] == "sintetico.xlsx"


class TestManejoDeErrores:
    def test_archivo_inexistente(self):
        with pytest.raises(FileNotFoundError):
            leer_trs398("/no/existe.xls")

    def test_extension_no_soportada(self, tmp_path):
        p = tmp_path / "x.csv"
        p.write_text("a,b")
        with pytest.raises(ValueError, match="Formato no soportado"):
            leer_trs398(str(p))


class TestHelpers:
    @pytest.mark.parametrize("ref, esperado", [
        ("A1", (0, 0)), ("I43", (42, 8)), ("G70", (69, 6)), ("J48", (47, 9)),
    ])
    def test_ref_a_indices(self, ref, esperado):
        assert _ref_a_indices(ref) == esperado

    @pytest.mark.parametrize("entrada, esperado", [
        (None, None), ("", None), ("#NAME?", None), ("#REF!", None),
        ("  water  ", "water"), (1.5, 1.5), (0, 0),
    ])
    def test_normalizar(self, entrada, esperado):
        assert _normalizar(entrada) == esperado


class TestComparacion:
    def test_con_modelo_todo_comparable_y_ok(self):
        filas = comparar_trs398(DATOS_HALCYON, modelo_camara="N31010")
        assert len(filas) == len(CELDAS_CALCULADAS)
        for f in filas:
            assert f["comparable"], f["magnitud"]
            assert f["ok"], f"{f['magnitud']} difiere: {f['diferencia_rel']}"
            assert f["diferencia_rel"] < 0.001

    def test_sin_modelo_kq_y_dependientes_no_comparables(self):
        filas = {f["magnitud"]: f for f in comparar_trs398(DATOS_HALCYON)}
        # Sin modelo de cámara no hay kQ, y sin kQ no hay Dzref ni dosis
        assert filas["kQ"]["comparable"] is False
        assert filas["Dzref"]["comparable"] is False
        assert filas["dosis_maxima"]["comparable"] is False
        # Los que no dependen de kQ sí se comparan
        for clave in ("ktp", "kpol", "ks", "Mq"):
            assert filas[clave]["comparable"] is True
            assert filas[clave]["ok"] is True

    def test_detecta_discrepancia_fuera_de_tolerancia(self):
        datos = {
            "archivo": "x", "entradas": dict(DATOS_HALCYON["entradas"]),
            "calculados": dict(DATOS_HALCYON["calculados"]),
        }
        datos["calculados"]["ktp"] = 1.25  # ~5 % de diferencia, muy fuera
        filas = {f["magnitud"]: f for f in comparar_trs398(datos, modelo_camara="N31010")}
        assert filas["ktp"]["comparable"] is True
        assert filas["ktp"]["ok"] is False
        assert filas["ktp"]["diferencia_rel"] > 0.001

    def test_excel_con_valor_none_no_es_comparable(self):
        datos = {
            "archivo": "x", "entradas": dict(DATOS_HALCYON["entradas"]),
            "calculados": dict(DATOS_HALCYON["calculados"]),
        }
        datos["calculados"]["kQ"] = None  # como el .xlsm real (#NAME?)
        filas = {f["magnitud"]: f for f in comparar_trs398(datos, modelo_camara="N31010")}
        assert filas["kQ"]["comparable"] is False
        assert filas["kQ"]["app"] is not None  # la app sí lo calcula
        assert filas["kQ"]["excel"] is None

    def test_entrada_faltante_deja_magnitud_no_comparable(self):
        datos = {
            "archivo": "x", "entradas": dict(DATOS_HALCYON["entradas"]),
            "calculados": dict(DATOS_HALCYON["calculados"]),
        }
        datos["entradas"]["Mplus"] = None  # sin M+ no hay kpol
        filas = {f["magnitud"]: f for f in comparar_trs398(datos, modelo_camara="N31010")}
        assert filas["kpol"]["app"] is None
        assert filas["kpol"]["comparable"] is False


# ── Capa 2: validación opcional contra archivos reales ────────────────────

@pytest.fixture(scope="module")
def datos_halcyon():
    return leer_trs398(HALCYON)


@pytest.mark.skipif(not os.path.exists(HALCYON),
                    reason="archivos reales del físico no disponibles en esta máquina")
class TestArchivoRealHalcyon:
    @pytest.fixture
    def datos(self, datos_halcyon):
        return datos_halcyon

    def test_descifra_y_lee_identificacion(self, datos):
        assert datos["entradas"]["acelerador"] == "Halcyon"
        assert datos["entradas"]["serie_camara"] == 1825.0
        assert datos["entradas"]["tpr2010"] == 0.626

    def test_entradas_crudas_esperadas(self, datos):
        e = datos["entradas"]
        assert e["T_clinica"] == 21.1
        assert e["P_clinica"] == 85.13
        assert e["Mplus"] == 5.525
        assert e["Mminus"] == 5.6
        assert e["factor_calibracion"] == 0.3034

    def test_valores_calculados_del_excel(self, datos):
        c = datos["calculados"]
        assert round(c["ktp"], 4) == 1.1866
        assert round(c["kpol"], 5) == 1.00679
        assert round(c["ks"], 4) == 1.007
        assert c["kQ"] == 0.9964
        assert round(c["Dzref"], 6) == 0.010047

    def test_motor_de_la_app_reproduce_al_excel(self, datos):
        """El corazón de D3: recalcular con el motor de la app y confirmar
        que coincide con los factores que el Excel oficial ya trae."""
        from services.dosis_service import DosisService
        e, c = datos["entradas"], datos["calculados"]

        assert DosisService.factor_tp(
            e["T_clinica"], e["P_clinica"], e["T0"], e["P0"]) == round(c["ktp"], 4)
        assert DosisService.factor_k_polaridad(
            e["Mplus"], e["Mminus"]) == round(c["kpol"], 5)
        m1m2 = DosisService.cociente_M1M2(e["M1_recomb"], e["M2_recomb"])
        assert DosisService.Ks_factor(e["a0"], e["a1"], e["a2"], m1m2) == round(c["ks"], 4)
        assert DosisService.interpolar_kq0("N31010", e["tpr2010"]) == c["kQ"]
