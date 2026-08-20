"""CL2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-CL2): tripwire permanente de
CL1 -- verifica que las 22 tablas ORIGINALES del bloque de QC tienen su
índice y que la DEFINICIÓN real en `sqlite_master` coincide con la clave
documentada en `scripts/indices_bloque_qc.py::CLAVES_INDICE`, no solo que
"algún índice" existe. Distinto de `test_cl1_indices_bloque_qc.py` (que
prueba el mecanismo de creación): esto es el guardián de que una migración
futura no los pierda ni los recree con otra clave en silencio.

IV3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV3, 19-08): `CLAVES_INDICE` amplió
de 22 a 52 entradas -- las 30 nuevas están DECLARADAS (para que IV2 no tenga
huecos) pero sus tablas todavía no están en `TABLAS_ANULABLES` (eso es MI1,
Fase 4, después de LF -- ver §4.4 del plan). Sobre una BD nueva esas 30
tienen `CREATE TABLE` real pero SIN columna `activo` todavía, así que
`crear_indices()` las salta con motivo explícito (mismo comportamiento que
`test_cl1` ya verifica). Este archivo distingue "las 22 originales, con
índice real" de "las 30 nuevas, declaradas y pendientes" en cada test.
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
from services.lectura_vigente import excepciones_inventario
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
    # IV3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV3): las 30 tablas nuevas del
    # bloque de QC, § 2.8 del plan. Copiado a mano igual que las 22 de
    # arriba -- es el ancla externa, no debe derivarse de CLAVES_INDICE.
    "CondicionesMedicion": ("ref",),
    "SistemaMedicion": ("ref",),
    "ResultadosActividad": ("ref",),
    "MaximosCamaras": ("ref", "posicion"),
    "LecturasMaximos": ("ref", "voltaje"),
    "analisis_placa_verificaciones": ("ref", "tipo"),
    "analisis_placa_correcciones": ("ref", "vertice"),
    "indicadores_brazo": ("ref", "nivel"),
    "indicadores_angulares_colimador": ("ref", "nivel"),
    "pruebas": ("id_sesion", "id_tipo"),
    "espesor_corte": ("id_prueba",),
    "linealidad_ct": ("id_prueba",),
    "resolucion_contraste": ("id_prueba",),
    "resolucion_espacial": ("id_prueba",),
    "tamaño_pixel": ("id_prueba",),
    "uniformidad_global": ("id_prueba",),
    "resolucion_contraste_rois": ("id_prueba", "diametro_mm"),
    "resolucion_espacial_regiones": ("id_prueba", "region_nombre"),
    "uniformidad_ruido": ("id_prueba", "id_region"),
    "valores_ct": ("id_prueba", "id_material"),
    "HC_fantomas": ("ref", "id_energia"),
    "configuracion_picketfence": ("ref",),
    "error_picket": ("ref", "picket"),
    "leaf_error": ("ref", "leaf"),
    "highest_leaf_errors": ("ref", "leaf_out"),
    "configuracion_starshot": ("ref",),
    "estadisticas_starshot": ("ref",),
    "angulo_starshot": ("ref", "spoke_index"),
    "uniformidad_angular_starshot": ("ref", "gap_index"),
    "angulos_entre_lineas_starshot": ("ref", "par_index"),
}

# Tablas del bloque de QC que YA estaban en TABLAS_ANULABLES antes de IV1
# (19-08) -- las únicas con índice REALMENTE creado hoy. Las demás claves de
# CLAVES_INDICE están declaradas para las 30 nuevas, pendientes de MI1.
_ORIGINALES_CON_INDICE_REAL = set(CLAVES_INDICE) & TABLAS_ANULABLES
_NUEVAS_PENDIENTES_DE_MI1 = set(CLAVES_INDICE) - TABLAS_ANULABLES


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
    for tabla in _ORIGINALES_CON_INDICE_REAL:
        clave = CLAVES_INDICE[tabla]
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


def test_las_30_nuevas_declaradas_no_tienen_indice_todavia(bd_con_indices):
    """IV3: `CLAVES_INDICE` declara sus claves por adelantado (para que IV2
    no tenga huecos), pero sus tablas no están en `TABLAS_ANULABLES` todavía
    -- eso es MI1. Sobre una BD nueva no deben tener índice real."""
    con_indice = [tabla for tabla in _NUEVAS_PENDIENTES_DE_MI1
                  if _sql_de(bd_con_indices, nombre_indice(tabla)) is not None]
    assert not con_indice, (
        f"tabla(s) declarada(s) como pendientes de MI1 pero YA tienen "
        f"índice creado -- ¿se amplió TABLAS_ANULABLES sin actualizar este "
        f"test?: {con_indice}")


def test_los_indices_son_unique_y_parciales_sobre_activo(bd_con_indices):
    for tabla in _ORIGINALES_CON_INDICE_REAL:
        sql = _sql_de(bd_con_indices, nombre_indice(tabla))
        assert sql is not None, tabla
        assert "UNIQUE" in sql.upper(), f"{tabla}: {sql}"
        assert "activo" in sql, f"{tabla}: sin condición sobre activo: {sql}"


def test_toda_tabla_indexada_esta_clasificada():
    """Guardia de coherencia: toda tabla de `CLAVES_INDICE` debe estar
    clasificada -- ya activa en `TABLAS_ANULABLES`, o declarada por
    adelantado en `EXCEPCIONES_INVENTARIO` (IV1/IV3, pendiente de MI1). Si
    apareciera una tercera categoría (ninguna de las dos), `CLAVES_INDICE`
    se desincronizó del inventario real -- exactamente el defecto que este
    plan existe para cerrar."""
    excepciones = excepciones_inventario()
    for tabla in CLAVES_INDICE:
        assert tabla in TABLAS_ANULABLES or tabla in excepciones, (
            f"{tabla} tiene clave de índice declarada pero no está ni en "
            f"TABLAS_ANULABLES ni en EXCEPCIONES_INVENTARIO -- revisar "
            f"CLAVES_INDICE o services/anulacion.py")


def test_preguntas_tiene_su_indice_desde_pr1():
    assert "preguntas" in CLAVES_INDICE
    assert CLAVES_INDICE["preguntas"] == ("ref",)
