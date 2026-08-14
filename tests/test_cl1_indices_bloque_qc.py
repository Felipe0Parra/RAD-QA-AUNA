"""CL1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-CL1, contrato regla 4): índices
UNIQUE parciales que declaran la clave de cada bloque del grupo C (+
equipos_medicion/control_cunas/control_conos, que ya versionan desde M2, +
dosimetriaMen) en el esquema.

Ya se validó empíricamente contra copia real de producción en §2.6 del
plan (21/21 creados) y contra `BaseDatosQA.db` real dentro de
`test_u2_indice_unico_controles.py` (vía SA1, que corre justo antes). Este
archivo prueba el mecanismo en aislamiento: qué se crea, que es
idempotente, y -- lo que de verdad importa -- que el índice BLOQUEA un
duplicado activo nuevo, sin bloquear filas superadas.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import crear_indices, nombre_indice, CLAVES_INDICE


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, activo) "
        "VALUES (30, 'Clinac 600', 'Mensual', '08/2026', 1)")
    conexion.con.commit()
    conexion.con.close()
    Conexion._instance = None
    yield ruta


def _indices_reales(ruta):
    con = sqlite3.connect(ruta)
    nombres = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    con.close()
    return nombres


def test_crea_las_22_tablas_incluida_preguntas_desde_pr1(bd_temporal):
    resultado = crear_indices(bd_temporal)

    assert all(r == "creado" for r in resultado.values()), (
        f"algún índice no se creó: "
        f"{[(t, r) for t, r in resultado.items() if r != 'creado']}")
    assert len(resultado) == 22

    nombres_reales = _indices_reales(bd_temporal)
    for tabla in resultado:
        assert nombre_indice(tabla) in nombres_reales


def test_segunda_corrida_es_idempotente(bd_temporal):
    crear_indices(bd_temporal)
    resultado2 = crear_indices(bd_temporal)

    for tabla, r in resultado2.items():
        assert r == "ya existía", f"{tabla}: {r}"


def test_el_indice_bloquea_un_duplicado_activo_nuevo(bd_temporal):
    crear_indices(bd_temporal)

    con = sqlite3.connect(bd_temporal)
    con.execute(
        "INSERT INTO control_cunas (ref, angulo, activo) VALUES (30, 45, 1)")
    con.commit()

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        con.execute(
            "INSERT INTO control_cunas (ref, angulo, activo) VALUES (30, 45, 1)")
    con.close()


def test_el_indice_no_bloquea_una_fila_superada_ni_entre_superadas(bd_temporal):
    """Con activo=0, dos filas de la misma clave conviven -- eso es
    justamente lo que CT2 va a necesitar (histórico acumulado)."""
    crear_indices(bd_temporal)

    con = sqlite3.connect(bd_temporal)
    con.execute(
        "INSERT INTO control_cunas (ref, angulo, activo) VALUES (30, 45, 1)")
    con.commit()
    # Superar la activa (anular) y luego re-insertar una nueva activa --
    # el mismo patrón que CT2 va a ejecutar.
    con.execute("UPDATE control_cunas SET activo = 0 WHERE ref = 30 AND angulo = 45")
    con.execute(
        "INSERT INTO control_cunas (ref, angulo, activo) VALUES (30, 45, 1)")
    con.commit()

    # Y una segunda superada más, misma clave -- dos activo=0 conviviendo.
    con.execute("UPDATE control_cunas SET activo = 0 WHERE ref = 30 AND angulo = 45 AND activo = 1")
    con.execute(
        "INSERT INTO control_cunas (ref, angulo, activo) VALUES (30, 45, 1)")
    con.commit()

    total = con.execute(
        "SELECT COUNT(*) FROM control_cunas WHERE ref = 30 AND angulo = 45").fetchone()[0]
    activas = con.execute(
        "SELECT COUNT(*) FROM control_cunas WHERE ref = 30 AND angulo = 45 "
        "AND activo = 1").fetchone()[0]
    con.close()
    assert total == 3
    assert activas == 1


def test_claves_coinciden_con_las_del_plan_para_las_8_de_h2():
    esperadas_h2 = {
        "control_cunas": ("ref", "angulo"),
        "control_conos": ("ref", "medida"),
        "equipos_medicion": ("ref", "tipo_camara"),
        "analisis_placa_franjas": ("ref", "franja"),
        "tamano_campo": ("ref", "campo_nominal"),
        "HC_indicadores_camilla": ("ref", "id_energia", "ubicacion", "desplazamiento"),
        "HC_indicadores_colimador": ("ref", "id_energia", "nivel"),
        "HC_indicadores_laser": ("ref", "id_energia", "ubicacion"),
    }
    for tabla, clave in esperadas_h2.items():
        assert CLAVES_INDICE[tabla] == clave

    assert len(CLAVES_INDICE) == 22  # 21 hijas + preguntas
