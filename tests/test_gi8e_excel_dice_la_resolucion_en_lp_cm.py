"""GI.8e (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, anotada por GI.1): la exportación a Excel dice la resolución espacial en lp/cm y la linealidad con palabras.

CAUSA: `ui/paginasGuia/SQLtoEXCEL.py::exportar` hace `SELECT *` de la tabla elegida y la vuelca tal cual. En `resolucion_espacial` y `resolucion_espacial_regiones` los controles de enero a abril se guardaron en
lp/mm (0.2 a 0.3; los de después en lp/cm), así que el Excel traía números de dos unidades bajo un mismo encabezado en lp/cm (`GI.0`); y `linealidad_ct.linealidad_aceptable` sale como 1 / 0, texto o BLOB
según cuándo se guardó. «Ver tabla» y el PDF YA convierten fila por fila (`unidad_de_la_fila_espacial` + `en_lp_cm`, `_bandera_guardada`); el Excel no.

GARANTIAS, una por bloque:

  1. LA FUNCION -- `catphan_db.preparar_tabla_de_imagenes_para_excel(df, tabla)`: la máxima y la MTF de cada fila de `resolucion_espacial` salen en lp/cm con la unidad en que se guardó esa fila, y el `lp_cm` de
     cada región es el que muestra el lector (`_lp_cm_de_la_region`, región por región: lo guardado manda si es un lp/cm utilizable, y se deriva del nombre cuando falta); las primitivas son las MISMAS que usan «Ver tabla»
     y el PDF; el NULL y el texto «No disponible» de la máxima y la MTF no se convierten; la bandera de la linealidad sale «Sí» / «No» por su VALOR (un BLOB de antes de GI.1 o un texto no son verdaderos por
     existir), un NULL queda vacío y lo que no se entiende queda como se guardó; no muta lo recibido; el resto de las tablas, y las columnas que una base vieja no tenga, pasan sin tocarse.
  1b. LO QUE NO SE NOMBRA NO CAMBIA -- con las columnas REALES de cada tabla (leídas del esquema y de las filas de la copia del 21-09), toda columna que la función no nombra sale idéntica, y las demás tablas
     del esquema pasan sin tocarse (revisión de GI.8e: una función que pisara `ultima_region_exitosa` o sumara a `num_picos_totales` pasaba las pruebas).
  2. UNA SOLA CONVERSION -- por AST: la función no multiplica por 10 ni compara unidades por su cuenta; usa `unidad_de_la_fila_espacial`, `en_lp_cm` y `_bandera_guardada`; y `exportar` la llama una vez,
     justo después de `changeColumnNames`.
  3. DE PUNTA A PUNTA -- el `exportar` REAL sobre una COPIA de la BD del 21-09 (sesiones de enero a abril en lp/mm y de después en lp/cm): el archivo .xlsx dice 3 lp/cm donde se guardó 0.3, deja tal cual lo
     que ya estaba en lp/cm, y la linealidad sale «Sí»; ningún aviso de error.
  4. EL EXCEL DICE LO MISMO QUE EL LECTOR -- en TODAS las pruebas de la copia real, la máxima, la MTF y la frecuencia de cada región del Excel son las que entrega `reconstruir_resolucion_espacial` (lo que
     muestran «Ver tabla» y el PDF), incluidas las regiones guardadas sin valor.
  5. LA VISTA PREVIA NO SE VACIA -- si la conversión fallara (o su módulo no se pudiera importar), la vista previa de cualquier tabla muestra las filas como están en la base y la causa queda en
     `error_log.txt`; antes de la revisión de GI.8e un fallo ahí vaciaba en silencio la vista previa de TODAS las tablas.

Nunca se conecta a una BD de referencia: se copia a un temporal primero.
"""
import ast
import importlib
import inspect
import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pandas as pd
import pytest

from data.ManejoDatos.catphan_TAC import catphan_db as C
from test_gi1_guardado_claves_del_analisis import app  # noqa: F401  (fixture)
from test_gi2_lectura_es_lo_guardado import bd_copia_real  # noqa: F401  (copia de la BD del 21-09 abierta con la app)

PREPARAR = C.preparar_tabla_de_imagenes_para_excel


# ---------------------------------------------------------------------------
# 1. LA FUNCION
# ---------------------------------------------------------------------------

def _resumen(filas):
    return pd.DataFrame(filas, columns=["id_prueba", "lp_cm_maximo", "ultima_region_exitosa", "mtf_10_pct", "mtf_20_pct", "mtf_50_pct", "otra"])


class TestResolucionEspacialResumen:

    def test_cada_fila_sale_en_lp_cm_con_la_unidad_en_que_se_guardo(self):
        df = _resumen([
            (1, 0.3, "region 3", None, None, 0.2628, "a"),                  # guardada en lp/mm (enero a abril)
            (2, 7.0, "region 7", None, 3.5, 2.7071917808219164, "b"),      # guardada en lp/cm
            (3, 0.2, "region 2", 0.35, 0.3, 0.25, "c"),                    # lp/mm con MTF 10 / 20 / 50
        ])
        r = PREPARAR(df, "resolucion_espacial")
        assert r["lp_cm_maximo"].tolist() == [pytest.approx(3.0), 7.0, pytest.approx(2.0)]
        assert r["mtf_50_pct"].tolist() == [pytest.approx(2.628), pytest.approx(2.7071917808219164), pytest.approx(2.5)]
        assert r["mtf_20_pct"].tolist()[1:] == [3.5, pytest.approx(3.0)] and pd.isna(r["mtf_20_pct"].tolist()[0])
        assert r["mtf_10_pct"].tolist()[2] == pytest.approx(3.5)
        assert r["otra"].tolist() == ["a", "b", "c"] and r["id_prueba"].tolist() == [1, 2, 3]

    @pytest.mark.parametrize("fila", [
        (1, "No disponible", "region 3", "No disponible", None, "No disponible", "x"),
        (1, None, None, None, None, None, "x"),
        (1, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), "x"),
    ], ids=["texto", "nulos", "nan"])
    def test_lo_que_no_es_una_frecuencia_no_se_convierte(self, fila):
        df = _resumen([fila])
        r = PREPARAR(df, "resolucion_espacial")
        for columna in ("lp_cm_maximo", "mtf_10_pct", "mtf_20_pct", "mtf_50_pct"):
            a, b = df[columna].tolist()[0], r[columna].tolist()[0]
            assert (a == b) or (pd.isna(a) and pd.isna(b)), (columna, a, b)

    @pytest.mark.parametrize("centinela", [-1, -1.0, 0, 0.0])
    def test_ninguna_region_medible_sale_con_las_palabras_del_informe_y_la_unidad_de_las_otras_filas_no_cambia(self, centinela):
        """El centinela de `lp_cm_maximo` (el analisis guarda -1) no es una frecuencia: en el Excel dice lo mismo que el informe PDF (una sola definicion) y no contamina un promedio. Las
        otras columnas de esa fila (MTF) y las demas filas no cambian."""
        df = _resumen([(1, centinela, None, None, None, None, "a"), (2, 0.3, "region 3", None, None, 0.2628, "b")])
        r = PREPARAR(df, "resolucion_espacial")
        assert C.TEXTO_SIN_REGION_MEDIBLE == "Sin región medible", "las palabras que el informe PDF ya imprimia"
        assert r["lp_cm_maximo"].tolist() == [C.TEXTO_SIN_REGION_MEDIBLE, pytest.approx(3.0)]
        assert r["mtf_50_pct"].tolist()[1] == pytest.approx(2.628) and pd.isna(r["mtf_50_pct"].tolist()[0]) and r["otra"].tolist() == ["a", "b"]

    def test_las_palabras_del_centinela_son_las_mismas_del_informe_pdf(self):
        ruta = Path(__file__).resolve().parent.parent / "models/PDF/Imagenes/reportes_control_sistema_imagenes.py"
        fuente = ruta.read_text(encoding="utf-8")
        assert "Sin región medible" not in fuente and "TEXTO_SIN_REGION_MEDIBLE" in fuente and "es_sin_region_medible" in fuente
        assert C.es_sin_region_medible(-1) and C.es_sin_region_medible(0) and not C.es_sin_region_medible(0.3) and not C.es_sin_region_medible(None) and not C.es_sin_region_medible("x")

    def test_sin_ultima_region_la_fila_se_toma_en_lp_cm(self):
        """Sin nada que deducir vale la convencion de hoy (lp/cm): no se multiplica a ciegas."""
        r = PREPARAR(_resumen([(1, 0.3, None, None, None, 0.2, "x")]), "resolucion_espacial")
        assert r["lp_cm_maximo"].tolist() == [0.3] and r["mtf_50_pct"].tolist() == [0.2]

    def test_no_muta_lo_recibido_y_devuelve_una_copia(self):
        df = _resumen([(1, 0.3, "region 3", None, None, 0.2628, "a")])
        antes = df.copy()
        r = PREPARAR(df, "resolucion_espacial")
        assert df.equals(antes) and r is not df
        assert r["lp_cm_maximo"].tolist() == [pytest.approx(3.0)]

    def test_una_base_vieja_sin_las_columnas_nuevas_pasa_tal_cual(self):
        df = pd.DataFrame({"id_prueba": [1], "lp_mm_maximo": [0.3], "ultima_region_exitosa": ["region 3"]})
        assert PREPARAR(df, "resolucion_espacial").equals(df)

    def test_una_base_vieja_sin_algunas_columnas_no_lanza_y_convierte_lo_que_puede(self):
        """Una BD anterior a ciertas migraciones puede no traer `ultima_region_exitosa` ni las MTF: se convierte lo que hay y no se inventa ni se lanza."""
        solo_maxima = pd.DataFrame({"id_prueba": [1, 2], "lp_cm_maximo": [0.3, 7.0]})
        r = PREPARAR(solo_maxima, "resolucion_espacial")
        assert r["lp_cm_maximo"].tolist() == [0.3, 7.0]                         # sin ultima region no hay con que deducir la unidad: se toma en lp/cm
        sin_mtf = pd.DataFrame({"lp_cm_maximo": [0.3], "ultima_region_exitosa": ["region 3"]})
        assert PREPARAR(sin_mtf, "resolucion_espacial")["lp_cm_maximo"].tolist() == [pytest.approx(3.0)]

    def test_tablas_vacias(self):
        for tabla in C.TABLAS_DE_IMAGENES_PARA_EXCEL:
            r = PREPARAR(pd.DataFrame({"id_prueba": [], "lp_cm_maximo": [], "lp_cm": [], "region_nombre": [], "linealidad_aceptable": []}), tabla)
            assert len(r) == 0


def _regiones(filas):
    return pd.DataFrame(filas, columns=["id", "id_prueba", "region_nombre", "lp_cm", "status"])


class TestResolucionEspacialRegiones:

    def test_cada_prueba_sale_en_lp_cm_con_la_unidad_de_sus_propias_regiones(self):
        df = _regiones([
            (1, 10, "region 1", 0.1, "OK"), (2, 10, "region 2", 0.2, "OK"), (3, 10, "region 3", 0.3, "OK"),          # prueba 10: lp/mm
            (4, 20, "region 1", 1.0, "OK"), (5, 20, "region 2", 2.0, "OK"), (6, 20, "region 3", 3.0, "OK"),          # prueba 20: lp/cm
        ])
        r = PREPARAR(df, "resolucion_espacial_regiones")
        assert r["lp_cm"].tolist() == [pytest.approx(1.0), pytest.approx(2.0), pytest.approx(3.0), 1.0, 2.0, 3.0]
        assert r["status"].tolist() == ["OK"] * 6 and r["id_prueba"].tolist() == [10] * 3 + [20] * 3

    def test_la_region_n_vale_n_lp_cm_en_todas_las_pruebas(self):
        """El oraculo independiente de GI.3: la region N vale N lp/cm sea cual sea la unidad en que se guardo."""
        df = _regiones([(i, 10, f"region {i}", i / 10, "OK") for i in range(1, 9)] + [(10 + i, 20, f"region {i}", float(i), "OK") for i in range(1, 9)])
        r = PREPARAR(df, "resolucion_espacial_regiones")
        for nombre, valor in zip(r["region_nombre"].tolist(), r["lp_cm"].tolist()):
            assert valor == pytest.approx(int(nombre.split()[-1])), (nombre, valor)

    def test_lo_que_falta_o_no_es_una_frecuencia_se_deriva_del_nombre_como_lo_hace_el_lector(self):
        """Una region guardada sin valor (NULL: los controles de 05/2026 a GI.1), con texto o con un valor no positivo (0 / -1 no son una frecuencia) dice N lp/cm en el Excel, igual que en «Ver tabla» y en el
        PDF: la region N vale N lp/cm por construccion del analisis. Lo guardado como lp/cm utilizable manda."""
        df = _regiones([(1, 10, "region 1", 0.1, "OK"), (2, 10, "region 2", "No disponible", "x"), (3, 10, "region 3", None, "x"), (4, 10, "region 4", -1, "x"), (5, 10, "region 5", 0, "x"),
                        (6, 10, "region 6", 6.0, "OK")])
        r = PREPARAR(df, "resolucion_espacial_regiones")
        assert r["lp_cm"].tolist() == [pytest.approx(1.0), 2.0, 3.0, 4.0, 5.0, 6.0]
        assert r["status"].tolist() == ["OK", "x", "x", "x", "x", "OK"], "el estado de cada region (medida o no) sigue diciendo lo que se guardo"

    def test_las_regiones_sin_valor_dicen_n_lp_cm_igual_que_el_lector(self):
        """Revision de GI.8e (P1): antes el Excel las dejaba vacias y el lector las mostraba como N; ahora son la misma funcion (`_lp_cm_de_la_region`)."""
        df = _regiones([(i, 10, f"region {i}", None, "OK") for i in range(1, 9)])
        r = PREPARAR(df, "resolucion_espacial_regiones")
        assert r["lp_cm"].tolist() == [float(i) for i in range(1, 9)]
        assert r["lp_cm"].tolist() == [C._lp_cm_de_la_region(n, None) for n in r["region_nombre"].tolist()]

    def test_cada_region_se_resuelve_por_su_cuenta_aunque_una_prueba_mezcle_unidades(self):
        """Revision de GI.8e: la regla es POR REGION, como la del lector -- una prueba con regiones en lp/mm y otras en lp/cm no se decide de un solo golpe."""
        df = _regiones([(1, 10, "region 1", 0.1, "OK"), (2, 10, "region 2", 0.2, "OK"), (3, 10, "region 5", 5.0, "OK"), (4, 10, "region 6", 6.0, "OK")])
        r = PREPARAR(df, "resolucion_espacial_regiones")
        assert r["lp_cm"].tolist() == [pytest.approx(1.0), pytest.approx(2.0), 5.0, 6.0]
        assert r["lp_cm"].tolist() == [C._lp_cm_de_la_region(n, v) for n, v in zip(df["region_nombre"].tolist(), df["lp_cm"].tolist())]

    def test_no_depende_del_id_de_prueba(self):
        """Ni de que falte (None / NaN): la unidad ya no se decide por grupos."""
        df = _regiones([(1, None, "region 1", 0.1, "OK"), (2, None, "region 2", 0.2, "OK"), (3, 10, "region 3", 0.3, "OK"), (4, float("nan"), "region 4", 4.0, "OK")])
        assert df["id_prueba"].dtype.kind == "f"
        assert [round(v, 6) for v in PREPARAR(df, "resolucion_espacial_regiones")["lp_cm"].tolist()] == [1.0, 2.0, 3.0, 4.0]

    def test_una_base_vieja_sin_nombre_de_region_ni_id_de_prueba_no_lanza(self):
        df = pd.DataFrame({"lp_cm": [0.3, 0.2]})
        assert PREPARAR(df, "resolucion_espacial_regiones")["lp_cm"].tolist() == [0.3, 0.2]       # sin nombres no hay con que deducir la unidad

    def test_sin_valores_que_deducir_queda_tal_cual(self):
        df = _regiones([(1, 10, "sin numero", 5.0, "OK")])
        assert PREPARAR(df, "resolucion_espacial_regiones")["lp_cm"].tolist() == [5.0]


class TestBanderaDeLaLinealidad:

    def test_la_bandera_sale_en_palabras_por_su_valor(self):
        valores = [b"\x01", b"\x00", 1, 0, True, False, "1", "0", "Sí", "No", "true", "false", np.int64(1), np.int64(0)]
        df = pd.DataFrame({"id_prueba": range(len(valores)), "linealidad_aceptable": pd.Series(valores, dtype=object), "r_cuadrado": [0.99] * len(valores)})
        r = PREPARAR(df, "linealidad_ct")
        assert r["linealidad_aceptable"].tolist() == [C.PALABRA_SI, C.PALABRA_NO] * 7
        assert r["r_cuadrado"].tolist() == [0.99] * len(valores) and r["id_prueba"].tolist() == list(range(len(valores)))

    def test_un_nulo_queda_vacio_y_lo_que_no_se_entiende_queda_como_se_guardo(self):
        df = pd.DataFrame({"linealidad_aceptable": pd.Series([None, float("nan"), "texto raro", b"", 2.5], dtype=object)})
        r = PREPARAR(df, "linealidad_ct")["linealidad_aceptable"].tolist()
        assert r[0] is None and pd.isna(r[1]) and r[2] == "texto raro" and r[3] == b"" and r[4] in (C.PALABRA_SI, 2.5)

    def test_una_base_sin_la_columna_pasa_tal_cual(self):
        df = pd.DataFrame({"id_prueba": [1], "r_cuadrado": [0.99]})
        assert PREPARAR(df, "linealidad_ct").equals(df)

    def test_las_palabras_no_llevan_simbolos(self):
        assert (C.PALABRA_SI, C.PALABRA_NO) == ("Sí", "No")                  # DA-18: palabras, nunca marcas de correcto / incorrecto


@pytest.mark.parametrize("tabla", ["valores_ct", "uniformidad_global", "resolucion_contraste_rois", "pruebas", "braqui", "controles", "espesor_corte", "tamaño_pixel"])
def test_las_demas_tablas_pasan_sin_tocarse(tabla):
    df = pd.DataFrame({"a": [1, 2], "linealidad_aceptable": [b"\x01", 0], "lp_cm": [0.3, 0.2], "lp_cm_maximo": [0.3, 0.2]})
    assert PREPARAR(df, tabla) is df


# ---------------------------------------------------------------------------
# 1b. LO QUE NO SE NOMBRA NO CAMBIA (revision de GI.8e)
# ---------------------------------------------------------------------------

# Lo UNICO que la funcion puede cambiar de cada tabla; todo lo demas (derivado del esquema real) tiene que salir identico.
COLUMNAS_QUE_LA_FUNCION_CONVIERTE = {
    "resolucion_espacial": {"lp_cm_maximo", "mtf_10_pct", "mtf_20_pct", "mtf_50_pct"},
    "resolucion_espacial_regiones": {"lp_cm"},
    "linealidad_ct": {"linealidad_aceptable"},
}


@pytest.mark.parametrize("tabla", sorted(COLUMNAS_QUE_LA_FUNCION_CONVIERTE))
def test_toda_columna_real_que_la_funcion_no_nombra_sale_identica(tabla, bd_copia_real):
    """Con TODAS las filas y columnas REALES de la copia del 21-09 (los resumenes, las 72 regiones, las 5 linealidades): la funcion no cambia el orden ni el numero de filas ni de columnas, y cada columna que
    no nombra (`ultima_region_exitosa`, `num_picos_totales`, `regiones_exitosas`, `status`, `r_cuadrado`...) sale igual, valor por valor; lo que si cambia esta dentro del conjunto declarado."""
    assert set(COLUMNAS_QUE_LA_FUNCION_CONVIERTE) == set(C.TABLAS_DE_IMAGENES_PARA_EXCEL)
    con = sqlite3.connect(bd_copia_real)
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{tabla}"', con)
    finally:
        con.close()
    assert len(df) >= 4 and len(df.columns) >= 6, (tabla, df.shape)
    assert COLUMNAS_QUE_LA_FUNCION_CONVIERTE[tabla] <= set(df.columns), "el esquema real tiene las columnas que la funcion convierte"
    r = PREPARAR(df, tabla)
    assert list(r.columns) == list(df.columns) and len(r) == len(df) and r.index.equals(df.index)
    intactas = [c for c in df.columns if c not in COLUMNAS_QUE_LA_FUNCION_CONVIERTE[tabla]]
    assert len(intactas) >= 4, intactas
    for columna in intactas:
        pd.testing.assert_series_equal(r[columna], df[columna], obj=f"{tabla}.{columna}")
    cambiadas = [c for c in df.columns if not df[c].equals(r[c])]
    assert cambiadas and set(cambiadas) <= COLUMNAS_QUE_LA_FUNCION_CONVIERTE[tabla], (tabla, cambiadas)


def test_todas_las_demas_tablas_del_esquema_real_pasan_sin_tocarse(bd_copia_real):
    """Cada tabla de la base real que no es una de las tres, con SUS columnas reales (algunas llevan `lp_cm`, `activo`...): la funcion devuelve el mismo objeto."""
    con = sqlite3.connect(bd_copia_real)
    try:
        tablas = [f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        columnas = {t: [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')] for t in tablas}
    finally:
        con.close()
    assert set(C.TABLAS_DE_IMAGENES_PARA_EXCEL) <= set(tablas)
    otras = [t for t in tablas if t not in C.TABLAS_DE_IMAGENES_PARA_EXCEL]
    assert len(otras) >= 60, len(otras)
    for tabla in otras:
        df = pd.DataFrame({c: [1] for c in columnas[tabla]})
        assert PREPARAR(df, tabla) is df, tabla


# ---------------------------------------------------------------------------
# 2. UNA SOLA CONVERSION
# ---------------------------------------------------------------------------

def _funcion_ast(modulo, nombre):
    fuente = inspect.getsource(modulo)
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            return nodo
    raise AssertionError(nombre)


def test_la_funcion_usa_las_primitivas_de_las_otras_dos_salidas_y_no_convierte_por_su_cuenta():
    nodo = _funcion_ast(C, "preparar_tabla_de_imagenes_para_excel")
    llamadas = {n.func.id for n in ast.walk(nodo) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"unidad_de_la_fila_espacial", "en_lp_cm", "_lp_cm_de_la_region", "_bandera_guardada"} <= llamadas
    # `[None] * n` (repetir una lista de huecos) no es una conversion de unidad: solo se cuentan los productos y cocientes entre numeros
    multiplicaciones = [n for n in ast.walk(nodo) if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Mult, ast.Div))
                        and not isinstance(n.left, ast.List) and not isinstance(n.right, ast.List)]
    assert multiplicaciones == [], "la funcion no puede multiplicar ni dividir: la unica conversion de unidad es `en_lp_cm`"
    assert not [n for n in ast.walk(nodo) if isinstance(n, ast.Constant) and n.value in (10, 10.0)], "ningun factor 10 escrito aqui"


def test_exportar_llama_una_vez_a_la_funcion_justo_despues_de_cambiar_los_nombres_de_columnas():
    modulo = importlib.import_module("ui.paginasGuia.SQLtoEXCEL")
    fuente = inspect.getsource(modulo.ExportarExcel.exportar)
    assert fuente.count("preparar_tabla_de_imagenes_para_excel(df, table)") == 1
    assert fuente.index("self.changeColumnNames(df, selected_table)") < fuente.index("preparar_tabla_de_imagenes_para_excel(df, table)") < fuente.index("df.to_excel(")


def test_la_vista_previa_llama_una_vez_a_la_misma_funcion_con_el_nombre_real_de_la_tabla():
    """La vista previa del dialogo y el archivo dicen lo mismo porque pasan por la MISMA funcion; ninguna de las dos tiene su propia conversion."""
    modulo = importlib.import_module("ui.paginasGuia.SQLtoEXCEL")
    fuente = inspect.getsource(modulo.ExportarExcel.update_preview)
    assert fuente.count("preparar_tabla_de_imagenes_para_excel(df, table_name)") == 1
    assert fuente.index("pd.read_sql_query(") < fuente.index("preparar_tabla_de_imagenes_para_excel(df, table_name)") < fuente.index("setHorizontalHeaderLabels")
    # nadie mas en el modulo convierte unidades de resolucion espacial por su cuenta
    todo = inspect.getsource(modulo)
    assert "en_lp_cm" not in todo and "lp_mm" not in todo and "* 10" not in todo


# ---------------------------------------------------------------------------
# 3. DE PUNTA A PUNTA: el `exportar` REAL
# ---------------------------------------------------------------------------

def _exportar(app, monkeypatch, tmp_path, ruta_bd, tabla):
    """El `exportar` real de la ventana, con el archivo a un temporal, y las filas del .xlsx que produce: (encabezados, [filas]), mas los avisos que vio el fisico."""
    import openpyxl
    X = importlib.import_module("ui.paginasGuia.SQLtoEXCEL")
    avisos = []
    conexion = sqlite3.connect(ruta_bd)
    monkeypatch.setattr(X, "connect", conexion)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    destino = str(tmp_path / f"{tabla}.xlsx")
    monkeypatch.setattr(X.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (destino, "")))
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(X.QMessageBox, nombre, staticmethod(lambda *a, _n=nombre, **k: avisos.append((_n, a[1:3])) or 0))
    ventana = X.ExportarExcel()
    try:
        indice = ventana.table_list.findData(tabla)
        assert indice >= 0, tabla
        ventana.table_list.setCurrentIndex(indice)
        ventana.exportar()
        libro = openpyxl.load_workbook(destino)
        hoja = libro.active
        filas = [[c.value for c in fila] for fila in hoja.iter_rows()]
        return filas[0], filas[1:], avisos
    finally:
        ventana.close()
        ventana.deleteLater()
        conexion.close()


def _columna(encabezados, filas, nombre):
    i = encabezados.index(nombre)
    return [f[i] for f in filas]


def test_el_excel_real_dice_3_lp_cm_donde_se_guardo_0_3_y_deja_lo_que_ya_estaba_en_lp_cm(app, bd_copia_real, tmp_path, monkeypatch):
    encabezados, filas, avisos = _exportar(app, monkeypatch, tmp_path, bd_copia_real, "resolucion_espacial")
    assert not [a for a in avisos if a[0] in ("critical", "warning")], avisos
    por_prueba = {f[encabezados.index("id_prueba")]: f for f in filas}
    maximo = lambda p: por_prueba[p][encabezados.index("lp_cm_maximo")]
    mtf50 = lambda p: por_prueba[p][encabezados.index("mtf_50_pct")]
    assert maximo(142) == pytest.approx(3.0) and mtf50(142) == pytest.approx(2.627968)          # sesion 12: guardada en lp/mm (0.3 y 0.2628)
    assert maximo(161) == pytest.approx(2.0)                                                   # sesion 6: 0.2 lp/mm
    assert maximo(172) == 7.0 and mtf50(172) == pytest.approx(2.7071917808219164)              # sesion 30: ya estaba en lp/cm
    assert maximo(191) == 6.0                                                                  # sesion 47: ya estaba en lp/cm


def test_el_excel_real_de_las_regiones_dice_la_region_n_vale_n_lp_cm(app, bd_copia_real, tmp_path, monkeypatch):
    """Las 72 regiones reales: 40 (5 pruebas de enero a abril) guardadas en lp/mm y 32 (4 pruebas de despues) sin valor (NULL: el mapeo de antes de GI.1). El Excel dice 'la region N vale N lp/cm' en las 72,
    igual que «Ver tabla» y el PDF (revision de GI.8e: antes dejaba vacias las 32 sin valor)."""
    encabezados, filas, avisos = _exportar(app, monkeypatch, tmp_path, bd_copia_real, "resolucion_espacial_regiones")
    assert not [a for a in avisos if a[0] in ("critical", "warning")], avisos
    nombres, valores = _columna(encabezados, filas, "region_nombre"), _columna(encabezados, filas, "lp_cm")
    assert len(valores) == 72 and None not in valores, (len(valores), valores.count(None))
    for nombre, valor in zip(nombres, valores):
        assert isinstance(valor, (int, float)) and valor == pytest.approx(int(nombre.split()[-1])), (nombre, valor)


def test_el_excel_real_de_la_linealidad_dice_si_y_no_un_blob(app, bd_copia_real, tmp_path, monkeypatch):
    encabezados, filas, avisos = _exportar(app, monkeypatch, tmp_path, bd_copia_real, "linealidad_ct")
    assert not [a for a in avisos if a[0] in ("critical", "warning")], avisos
    banderas = _columna(encabezados, filas, "linealidad_aceptable")
    assert len(banderas) == 5 and set(banderas) == {C.PALABRA_SI}, banderas


def test_la_vista_previa_real_dice_3_lp_cm_donde_se_guardo_0_3(app, bd_copia_real, monkeypatch):
    X = importlib.import_module("ui.paginasGuia.SQLtoEXCEL")
    conexion = sqlite3.connect(bd_copia_real)
    monkeypatch.setattr(X, "connect", conexion)
    ventana = X.ExportarExcel()
    try:
        ventana.table_list.setCurrentIndex(ventana.table_list.findData("resolucion_espacial"))
        ventana.update_preview()
        tabla = ventana.preview_table
        encabezados = [tabla.horizontalHeaderItem(c).text() for c in range(tabla.columnCount())]
        celdas = {int(tabla.item(r, encabezados.index("id_prueba")).text()): tabla.item(r, encabezados.index("lp_cm_maximo")).text() for r in range(tabla.rowCount())}
        assert float(celdas[142]) == pytest.approx(3.0) and float(celdas[172]) == 7.0
    finally:
        ventana.close()
        ventana.deleteLater()
        conexion.close()


def test_el_excel_real_de_otra_tabla_de_imagenes_sale_como_la_base_la_guarda(app, bd_copia_real, tmp_path, monkeypatch):
    """Control: `valores_ct` no pasa por la conversion (compara contra el SELECT * vigente, columna a columna)."""
    encabezados, filas, avisos = _exportar(app, monkeypatch, tmp_path, bd_copia_real, "valores_ct")
    assert not [a for a in avisos if a[0] in ("critical", "warning")], avisos
    con = sqlite3.connect(bd_copia_real)
    try:
        esperado = con.execute("SELECT promedio_hu FROM valores_ct WHERE activo IS NULL OR activo = 1").fetchall()
    finally:
        con.close()
    assert sorted(f[0] for f in esperado) == sorted(_columna(encabezados, filas, "promedio_hu"))


# ---------------------------------------------------------------------------
# 4. EL EXCEL DICE LO MISMO QUE EL LECTOR (lo que muestran «Ver tabla» y el PDF)
# ---------------------------------------------------------------------------

def test_el_excel_dice_lo_mismo_que_el_lector_en_todas_las_pruebas_reales(app, bd_copia_real, tmp_path, monkeypatch):
    """Revision de GI.8e (P1): la maxima, la MTF y la frecuencia de CADA region del Excel son las que entrega `reconstruir_resolucion_espacial` en todas las pruebas de la copia real (las de enero a abril en
    lp/mm, las de despues en lp/cm, las regiones guardadas sin valor)."""
    enc_resumen, filas_resumen, avisos_1 = _exportar(app, monkeypatch, tmp_path, bd_copia_real, "resolucion_espacial")
    enc_regiones, filas_regiones, avisos_2 = _exportar(app, monkeypatch, tmp_path, bd_copia_real, "resolucion_espacial_regiones")
    assert not [a for a in avisos_1 + avisos_2 if a[0] in ("critical", "warning")], (avisos_1, avisos_2)
    con = sqlite3.connect(bd_copia_real)
    try:
        cursor = con.cursor()
        ids = {fila[enc_resumen.index("id_prueba")] for fila in filas_resumen} | {fila[enc_regiones.index("id_prueba")] for fila in filas_regiones}
        lector = {i: C.reconstruir_resolucion_espacial(cursor, i, None) for i in ids}
    finally:
        con.close()
    assert len(filas_resumen) >= 4 and all(lector[fila[enc_resumen.index("id_prueba")]] for fila in filas_resumen), "cada prueba con resumen exportada se puede reabrir"
    for fila in filas_resumen:
        leido = lector[fila[enc_resumen.index("id_prueba")]]
        maxima = fila[enc_resumen.index("lp_cm_maximo")]
        esperada = leido["resolucion_limite"]["lp_cm_maximo"]
        if C.es_sin_region_medible(esperada):
            assert maxima == C.TEXTO_SIN_REGION_MEDIBLE, (fila, esperada)
        else:
            assert maxima == esperada if esperada is None else maxima == pytest.approx(esperada), (fila, esperada)
        for porcentaje in ("10", "20", "50"):
            en_excel = fila[enc_resumen.index(f"mtf_{porcentaje}_pct")]
            if porcentaje in leido["mtf_lp_cm"]:
                assert en_excel == pytest.approx(leido["mtf_lp_cm"][porcentaje]), (fila, porcentaje)
            else:
                assert not en_excel, (fila, porcentaje, en_excel)             # el lector no muestra una MTF vacia o en cero
    assert len(filas_regiones) == 72
    sin_resumen = 0
    for fila in filas_regiones:
        reabierta = lector[fila[enc_regiones.index("id_prueba")]]
        nombre = fila[enc_regiones.index("region_nombre")]
        if reabierta is None:               # una prueba cuyas regiones estan vigentes pero sin resumen vigente (la 156 de la copia): el lector no la reabre; el Excel dice lo que dice el nombre de la region
            sin_resumen += 1
            assert fila[enc_regiones.index("lp_cm")] == pytest.approx(int(nombre.split()[-1])), fila
        else:
            assert fila[enc_regiones.index("lp_cm")] == pytest.approx(reabierta["region_results"][nombre]["lp/cm"]), fila
    assert sin_resumen <= 8, "a lo sumo una prueba (8 regiones) escapa a la comparacion con el lector"


# ---------------------------------------------------------------------------
# 5. LA VISTA PREVIA NO SE VACIA SI LA CONVERSION FALLA
# ---------------------------------------------------------------------------

def _vista_previa(monkeypatch, ruta_bd, tabla):
    """(encabezados, {id_prueba: fila} o filas) de la vista previa REAL de la ventana para `tabla`, sobre la copia."""
    X = importlib.import_module("ui.paginasGuia.SQLtoEXCEL")
    conexion = sqlite3.connect(ruta_bd)
    monkeypatch.setattr(X, "connect", conexion)
    ventana = X.ExportarExcel()
    try:
        ventana.table_list.setCurrentIndex(ventana.table_list.findData(tabla))
        ventana.update_preview()
        tabla_qt = ventana.preview_table
        encabezados = [tabla_qt.horizontalHeaderItem(c).text() for c in range(tabla_qt.columnCount())]
        filas = [[tabla_qt.item(r, c).text() for c in range(tabla_qt.columnCount())] for r in range(tabla_qt.rowCount())]
        return encabezados, filas
    finally:
        ventana.close()
        ventana.deleteLater()
        conexion.close()


@pytest.mark.parametrize("falla", ["la_funcion_lanza", "no_se_puede_importar"])
def test_si_la_conversion_falla_la_vista_previa_muestra_las_filas_de_la_base_y_la_causa_queda_registrada(falla, app, bd_copia_real, tmp_path, monkeypatch):
    """Revision de GI.8e (P2): el `try` de `update_preview` vacia la tabla en silencio ante CUALQUIER error; la conversion nueva quedo dentro y un fallo suyo (o de su import) habria vaciado la vista previa de TODAS las
    tablas, tambien las que no convierte. Ahora la vista previa cae a las filas tal como estan en la base (lo que hacia antes de GI.8e), y la causa queda en `error_log.txt`; el archivo (`exportar`) si avisa."""
    registro = tmp_path / "error_log.txt"
    monkeypatch.setenv("RADQA_ERROR_LOG", str(registro))
    if falla == "la_funcion_lanza":
        def lanza(df, tabla):
            raise RuntimeError("fallo de prueba en la conversion")
        monkeypatch.setattr(C, "preparar_tabla_de_imagenes_para_excel", lanza)
    else:
        monkeypatch.setitem(sys.modules, "data.ManejoDatos.catphan_TAC.catphan_db", None)           # `from ... import ...` lanza ImportError
    enc, filas = _vista_previa(monkeypatch, bd_copia_real, "resolucion_espacial")
    assert len(filas) >= 4 and "lp_cm_maximo" in enc, "la vista previa de una tabla de imagenes no se vacia"
    por_prueba = {f[enc.index("id_prueba")]: f for f in filas}
    assert float(por_prueba["142"][enc.index("lp_cm_maximo")]) == pytest.approx(0.3), "sin conversion: la fila como esta en la base (guardada en lp/mm)"
    enc_otra, filas_otra = _vista_previa(monkeypatch, bd_copia_real, "valores_ct")
    assert len(filas_otra) >= 7 and "promedio_hu" in enc_otra, "tampoco se vacia la de una tabla que no se convierte"
    texto = registro.read_text(encoding="utf-8")
    assert "Vista previa de Exportar a Excel" in texto and "resolucion_espacial" in texto
    assert ("fallo de prueba en la conversion" in texto) if falla == "la_funcion_lanza" else ("ImportError" in texto or "ModuleNotFoundError" in texto)
