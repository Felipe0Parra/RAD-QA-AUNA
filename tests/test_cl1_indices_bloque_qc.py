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


# MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1) movió las 30 tablas
# PENDIENTE-LF a TABLAS_ANULABLES y les dio `activo` -- 52 de las 56 tablas
# de CLAVES_INDICE (IV3+MI3) ya tienen columna `activo` desde el arranque.
# Sobre una BD temporal recién creada (sin datos, sin duplicados) las 56
# deben crearse de verdad; MI2 (saneamiento de duplicados reales) es lo que
# hace falta antes de crear estos índices sobre una BD CON datos históricos.
# EB6 (24-08) añadió una 57ª: TipoCalibracion (DATE(fecha), tipo) -- raíz
# desde E7, ya tiene `activo` desde siempre.


def test_crea_los_62_tras_mi1_mi3_eb6_r1_b1(bd_temporal):
    resultado = crear_indices(bd_temporal)

    # R1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 3, 27-08): +4 sobre las 57
    # que dejó EB6 -- las lecturas crudas de Linealidad entran directo a
    # TABLAS_ANULABLES, sin pasar por un estado "declarada, pendiente".
    # B.1 (PLAN_REFERENCIAS_EDITABLES_21-09.md, 21-09): +1 (referencias_qc).
    assert len(resultado) == 62
    for tabla, r in resultado.items():
        assert r == "creado", (
            f"{tabla}: se esperaba 'creado' -- tras MI1/MI3/EB6/R1 las 61 "
            f"tablas de CLAVES_INDICE ya tienen 'activo' y no hay datos en "
            f"esta BD que produzcan duplicados; dio: {r}")

    nombres_reales = _indices_reales(bd_temporal)
    for tabla in CLAVES_INDICE:
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


def test_duplicado_activo_reporta_no_creado_en_vez_de_reventar(bd_temporal):
    """MI1: `CREATE UNIQUE INDEX` sobre una tabla con un duplicado activo
    lanza `sqlite3.IntegrityError`, no `OperationalError` -- son ramas
    hermanas de `DatabaseError`. `crear_indices()` solo capturaba la
    segunda; la primera se propagaba sin capturar y abortaba `migrar()`
    entero en vez de reportar "NO CREADO" (que es justo lo que
    `migrar_bd_a_estandar.py::fallos_indices` espera poder leer). Se
    reproduce con un duplicado real en `control_cunas`, sin pasar por
    `sanear_bloque_qc` (MI2) -- exactamente el estado de una BD real antes
    de sanear."""
    con = sqlite3.connect(bd_temporal)
    con.execute(
        "INSERT INTO control_cunas (ref, angulo, activo) VALUES (30, 45, 1)")
    con.execute(
        "INSERT INTO control_cunas (ref, angulo, activo) VALUES (30, 45, 1)")
    con.commit()
    con.close()

    resultado = crear_indices(bd_temporal)  # no debe lanzar

    assert resultado["control_cunas"].startswith("NO CREADO"), (
        f"se esperaba un 'NO CREADO' legible, dio: {resultado['control_cunas']}")
    assert "UNIQUE constraint failed" in resultado["control_cunas"]


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

    # IV3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV3): 22 originales (21 hijas +
    # preguntas) + 30 nuevas del bloque de QC (§2.8 del plan) = 52. MI3
    # (§6-MI3) añadió las 4 diarias (clave por expresión DATE(date)) = 56.
    # EB6 (24-08, hallazgo G3) añadió TipoCalibracion = 57. R1
    # (PLAN_REPARACION_ANUAL_27-08.md §Fase 3, 27-08) añadió las 4 lecturas
    # crudas de Linealidad = 61. B.1 (PLAN_REFERENCIAS_EDITABLES_21-09.md,
    # 21-09) añadió referencias_qc = 62.
    assert len(CLAVES_INDICE) == 62
