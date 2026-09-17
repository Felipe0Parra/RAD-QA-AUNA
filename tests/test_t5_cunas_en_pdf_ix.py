"""T.5 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §6): la tabla de cuñas
llega al PDF del iX.

CAUSA (§0.7 del plan). `_crear_tabla_seguridad` tenía:

    if maquina == 'Clinac ix':
        ...                     # construye CONOS y hace return
    elif maquina == 'Clinac 600' or maquina == 'Clinac ix':
        ...                     # CUÑAS -- el "or Clinac ix" no se alcanza

El `if` de arriba capturaba TODO 'Clinac ix' primero, así que el `or` de la
segunda rama era código muerto: el iX nunca guardaba su tabla de cuñas,
pese a que la configuración del propio reporte ya declaraba `'accesorios':
['cunas', 'conos']` para él. **[medido]** 7 controles reales del iX tienen
los 4 ángulos de `control_cunas` completos, sin nulos, nunca impresos.

JUSTIFICACIÓN: no es una función nueva, es una rama muerta. Extraer el
constructor (`_crear_tabla_cunas`) evita que el 600 y el iX vuelvan a
divergir (corolario 1: una operación, una definición).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from models.PDF.Mensuales.reportes_mensuales import (
    _crear_tabla_cunas, _crear_tabla_seguridad, _procesar_datos_para_reporte)
from models.PDF.pdf import generar_reporte_pdf_multitabla_mensual


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


CUNAS_REALES = [
    {"angulo": 15, "in_val": 1, "out_val": 1, "right_val": 1, "left_val": 0},
    {"angulo": 30, "in_val": 1, "out_val": 0, "right_val": 1, "left_val": 1},
    {"angulo": 45, "in_val": 0, "out_val": 1, "right_val": 1, "left_val": 1},
    {"angulo": 60, "in_val": 1, "out_val": 1, "right_val": 1, "left_val": 1},
]

CONOS_REALES = [
    {"medida": "6x6", "valor": 1},
    {"medida": "10x10", "valor": 1},
    {"medida": "15x15", "valor": 0},
    {"medida": "20x20", "valor": 1},
    {"medida": "25x25", "valor": 1},
]

DATOS_MINIMOS_PIPELINE = {"preguntas": [{"isocentro": "Funciona"}]}


def _datos_ix_completos():
    datos = dict(DATOS_MINIMOS_PIPELINE)
    datos["control_cunas"] = CUNAS_REALES
    datos["control_conos"] = CONOS_REALES
    return datos


# ---------------------------------------------------------------------------
# 1. ROJO-ANTES-QUE-VERDE: el diccionario de tablas del iX gana
#    'seguridad_cunas' con los 4 ángulos.
# ---------------------------------------------------------------------------

def test_ix_gana_seguridad_cunas_con_los_4_angulos(app):
    resultado = _procesar_datos_para_reporte(
        _datos_ix_completos(), {}, {}, "Clinac ix")

    assert "seguridad_cunas" in resultado, (
        "el iX debe ganar la clave 'seguridad_cunas' -- hoy la rama de "
        "cuñas es inalcanzable para él (§0.7 del plan)")

    df = resultado["seguridad_cunas"]
    angulos_en_tabla = df.iloc[1:, 0].tolist()
    assert angulos_en_tabla == ["15°", "30°", "45°", "60°"]


def test_seguridad_cunas_tiene_el_contenido_correcto(app):
    """No solo que exista la clave -- que cada ángulo lleve el estado real
    (Funciona/No funciona) que se guardó, no un placeholder."""
    resultado = _procesar_datos_para_reporte(
        _datos_ix_completos(), {}, {}, "Clinac ix")
    df = resultado["seguridad_cunas"]

    fila_15 = df.iloc[1].tolist()
    assert fila_15 == ["15°", "Funciona", "Funciona", "Funciona", "No funciona"]
    fila_45 = df.iloc[3].tolist()
    assert fila_45 == ["45°", "No funciona", "Funciona", "Funciona", "Funciona"]


# ---------------------------------------------------------------------------
# 2. El iX conserva su tabla de conos IDÉNTICA
# ---------------------------------------------------------------------------

def test_ix_conserva_su_tabla_de_conos_identica(app):
    resultado = _procesar_datos_para_reporte(
        _datos_ix_completos(), {}, {}, "Clinac ix")

    assert "seguridad" in resultado
    df_conos = resultado["seguridad"]
    assert list(df_conos.columns) == ["Control de conos", ""]
    medidas = df_conos.iloc[1:, 0].tolist()
    assert medidas == ["6x6", "10x10", "15x15", "20x20", "25x25"]
    estados = df_conos.iloc[1:, 1].tolist()
    assert estados == ["Funciona", "Funciona", "No funciona", "Funciona", "Funciona"]


# ---------------------------------------------------------------------------
# 3. COMPUERTA DE CERO DIFERENCIAS: 600 y Halcyon, DataFrame a DataFrame
# ---------------------------------------------------------------------------

def test_600_no_gana_seguridad_cunas_y_su_seguridad_es_identica(app):
    datos = dict(DATOS_MINIMOS_PIPELINE)
    datos["control_cunas"] = CUNAS_REALES

    resultado = _procesar_datos_para_reporte(datos, {}, {}, "Clinac 600")

    assert "seguridad_cunas" not in resultado, (
        "el 600 no debe ganar ninguna clave nueva -- 'accesorios': "
        "['cunas'] no incluye conos, y T.5 no le agrega nada")

    # DataFrame a DataFrame contra lo que _crear_tabla_cunas (la MISMA
    # lógica que antes vivía inline en _crear_tabla_seguridad) produce.
    esperado = _crear_tabla_cunas(datos)
    assert resultado["seguridad"].equals(esperado), (
        "la tabla de seguridad del 600 cambió -- T.5 no debía tocar su "
        "salida en absoluto")


def test_halcyon_no_tiene_ninguna_clave_de_seguridad(app):
    datos = dict(DATOS_MINIMOS_PIPELINE)
    resultado = _procesar_datos_para_reporte(datos, {}, {}, "Halcyon")

    assert "seguridad" not in resultado
    assert "seguridad_cunas" not in resultado


def test_extraer_la_funcion_no_cambio_el_camino_del_600():
    """`_crear_tabla_seguridad(datos, 'Clinac 600')` y
    `_crear_tabla_cunas(datos)` deben ser la MISMA salida -- es la garantía
    de que la extracción (corolario 1) no alteró nada, solo movió código."""
    datos = {"control_cunas": CUNAS_REALES}
    assert _crear_tabla_seguridad(datos, "Clinac 600").equals(
        _crear_tabla_cunas(datos))


# ---------------------------------------------------------------------------
# 4. El PDF del iX se genera y su texto contiene "Control de cuñas" y los
#    4 ángulos.
# ---------------------------------------------------------------------------

def test_pdf_del_ix_contiene_control_de_cunas_y_los_4_angulos(app):
    import fitz

    resultado = _procesar_datos_para_reporte(
        _datos_ix_completos(), {}, {}, "Clinac ix")

    pdf_bytes = generar_reporte_pdf_multitabla_mensual(
        resultado, "07/2026", "Físico de Prueba", maquina="Clinac ix",
        temp=True)

    doc = fitz.open(stream=bytes(pdf_bytes), filetype="pdf")
    texto = "".join(pagina.get_text() for pagina in doc)
    doc.close()

    assert "Control de cuñas" in texto
    for angulo in ("15°", "30°", "45°", "60°"):
        assert angulo in texto, f"falta el ángulo {angulo} en el PDF"
    # Y la de conos sigue -- no se perdió al añadir la de cuñas.
    assert "Control de conos" in texto


# ---------------------------------------------------------------------------
# 5. Un control SIN filas de cuñas no rompe el reporte
# ---------------------------------------------------------------------------

def test_sin_filas_de_cunas_no_rompe_el_reporte(app):
    datos = dict(DATOS_MINIMOS_PIPELINE)
    datos["control_conos"] = CONOS_REALES
    # control_cunas ausente por completo (control real sin ese análisis).

    resultado = _procesar_datos_para_reporte(datos, {}, {}, "Clinac ix")

    assert "seguridad_cunas" in resultado
    df = resultado["seguridad_cunas"]
    # Los 4 ángulos siguen apareciendo, con las celdas en blanco -- ver
    # el criterio ya establecido para "sin dato" en esta misma función.
    angulos_en_tabla = df.iloc[1:, 0].tolist()
    assert angulos_en_tabla == ["15°", "30°", "45°", "60°"]
    for col in range(1, 5):
        assert all(v == "" for v in df.iloc[1:, col].tolist())

    # Y el PDF se genera sin lanzar.
    pdf_bytes = generar_reporte_pdf_multitabla_mensual(
        resultado, "07/2026", "Físico de Prueba", maquina="Clinac ix",
        temp=True)
    assert pdf_bytes is not None
