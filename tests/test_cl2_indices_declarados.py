"""CL2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-CL2): tripwire permanente de
CL1 -- verifica que las 22 tablas del bloque de QC tienen su índice y que
la DEFINICIÓN real en `sqlite_master` coincide con la clave documentada en
`scripts/indices_bloque_qc.py::CLAVES_INDICE`, no solo que "algún índice"
existe. Distinto de `test_cl1_indices_bloque_qc.py` (que prueba el
mecanismo de creación): esto es el guardián de que una migración futura no
los pierda ni los recree con otra clave en silencio.
"""
import os
import re
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.anulacion import TABLAS_ANULABLES
from scripts.indices_bloque_qc import crear_indices, nombre_indice, CLAVES_INDICE


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_con_indices(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.close()
    Conexion._instance = None
    crear_indices(ruta)  # las 22, incluida `preguntas` desde PR1
    yield ruta


# Independiente de CLAVES_INDICE a propósito: copiado directo de §2.3 del
# plan. Si alguien corrompe CLAVES_INDICE en scripts/indices_bloque_qc.py,
# comparar la implementación contra SÍ MISMA no lo detectaría -- este es el
# ancla externa que sí lo hace.
CLAVES_ESPERADAS_DEL_PLAN = {
    "control_cunas": ("ref", "angulo"),
    "control_conos": ("ref", "medida"),
    "equipos_medicion": ("ref", "tipo_camara"),
    "analisis_placa_franjas": ("ref", "franja"),
    "tamano_campo": ("ref", "campo_nominal"),
    "HC_indicadores_camilla": ("ref", "id_energia", "ubicacion", "desplazamiento"),
    "HC_indicadores_colimador": ("ref", "id_energia", "nivel"),
    "HC_indicadores_laser": ("ref", "id_energia", "ubicacion"),
    "dosimetriaMen": ("ref", "energia"),
    "tabla_factor_campo": ("ref", "id_energia", "tamano_campo"),
    "tabla_factores_transmision": ("ref", "id_energia", "angulo"),
    "tabla_control_camaras_monitoras": ("ref", "id_energia", "indicador_medir"),
    "tabla_factores_sobre_eje": ("ref", "id_energia", "tam_pdd", "profundidad"),
    "HC_indicadores_brazo": ("ref", "id_energia", "nivel"),
    "HC_desplazamiento_isocentro_mensual": ("ref", "id_energia", "ubicacion"),
    "HC_tamanos_campo_radiacion": ("ref", "id_energia", "indicado_inplane"),
    "HC_dosimetria_anual": ("ref", "id_energia"),
    "HC_imagen_perfil_mlc_anual": ("ref", "id_energia"),
    "HC_linealidad_unidades_monitor_anual": ("ref", "id_energia", "UM"),
    "HC_velocidad_multilaminas_anual": ("ref", "id_energia", "banco"),
    "HC_precision_posicion_multilaminas_anual": ("ref", "id_energia", "medida"),
    "preguntas": ("ref",),
}


def test_claves_indice_coinciden_con_el_plan():
    assert CLAVES_INDICE == CLAVES_ESPERADAS_DEL_PLAN


def _sql_de(ruta, indice):
    con = sqlite3.connect(ruta)
    fila = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
        (indice,)).fetchone()
    con.close()
    return fila[0] if fila else None


def test_las_22_tablas_tienen_su_indice_con_las_columnas_declaradas(bd_con_indices):
    faltantes = []
    con_columnas_distintas = []
    for tabla, clave in CLAVES_INDICE.items():
        sql = _sql_de(bd_con_indices, nombre_indice(tabla))
        if sql is None:
            faltantes.append(tabla)
            continue
        # Columnas dentro del primer paréntesis: `ON "tabla" (a, b, c) WHERE ...`
        columnas_sql = re.search(r"\(([^)]*)\)", sql).group(1)
        columnas_reales = tuple(c.strip().strip('"') for c in columnas_sql.split(","))
        if columnas_reales != clave:
            con_columnas_distintas.append((tabla, clave, columnas_reales))

    assert not faltantes, f"tablas sin su índice: {faltantes}"
    assert not con_columnas_distintas, (
        f"índices con columnas distintas a la clave documentada: "
        f"{con_columnas_distintas}")


def test_los_indices_son_unique_y_parciales_sobre_activo(bd_con_indices):
    for tabla in CLAVES_INDICE:
        sql = _sql_de(bd_con_indices, nombre_indice(tabla))
        assert sql is not None, tabla
        assert "UNIQUE" in sql.upper(), f"{tabla}: {sql}"
        assert "activo" in sql, f"{tabla}: sin condición sobre activo: {sql}"


def test_toda_tabla_indexada_esta_en_tablas_anulables():
    """Guardia de coherencia: si `TABLAS_ANULABLES` cambiara y una de estas
    22 tablas dejara de estar ahí, este test lo señala -- CLAVES_INDICE no
    debe quedar desincronizado de la lista blanca real."""
    for tabla in CLAVES_INDICE:
        assert tabla in TABLAS_ANULABLES, (
            f"{tabla} tiene clave de índice declarada pero ya no está en "
            f"TABLAS_ANULABLES -- revisar CLAVES_INDICE")


def test_preguntas_tiene_su_indice_desde_pr1():
    assert "preguntas" in CLAVES_INDICE
    assert CLAVES_INDICE["preguntas"] == ("ref",)
