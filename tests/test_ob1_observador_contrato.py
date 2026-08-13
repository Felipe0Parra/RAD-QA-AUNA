"""OB1 (PLAN_CONTRATO_GUARDADO_13-08.md §5): el observador secuencial es de
solo lectura y determinista -- capturar dos veces la misma BD, sin tocar
nada entre medio, debe dar el mismo snapshot byte a byte, y el archivo de
la BD no debe cambiar (ni su md5 ni su tamaño). Si esto fallara, ninguna
comparación posterior del plan (OB2 en adelante) sería confiable: el
"cambio" que reportara podría ser ruido del propio instrumento.

Se prueba también el lado `comparar`: una fila insertada se ve como fallo
no declarado (censo + vigente + foreign_key_check), y desaparece como
fallo si se declara en `--esperado` -- salvo que una tabla PIERDA filas,
que nunca se puede declarar (criterio de terminación del plan, §8-6).
"""
import hashlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.observador_contrato import capturar, comparar, _tablas_en_alcance


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + todas las migraciones reales
    conexion.con.close()
    Conexion._instance = None
    yield ruta


def _md5(ruta):
    with open(ruta, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def test_capturar_dos_veces_da_snapshot_identico_y_no_toca_la_bd(bd_temporal):
    md5_antes = _md5(bd_temporal)
    snap1 = capturar(bd_temporal)
    md5_entre = _md5(bd_temporal)
    snap2 = capturar(bd_temporal)
    md5_despues = _md5(bd_temporal)

    assert snap1 == snap2
    assert md5_antes == md5_entre == md5_despues


def test_capturar_cubre_todas_las_tablas_del_alcance(bd_temporal):
    snap = capturar(bd_temporal)
    assert set(snap["esquema"]) == set(_tablas_en_alcance())
    assert set(snap["censo"]) == set(_tablas_en_alcance())
    assert set(snap["vigente"]) == set(_tablas_en_alcance())


def test_capturar_bd_vacia_tiene_censo_cero_e_integridad_ok(bd_temporal):
    snap = capturar(bd_temporal)
    assert snap["integridad"]["integrity_check"] == "ok"
    for tabla, censo in snap["censo"].items():
        assert censo == {"total": 0, "activas": 0, "anuladas": 0}, tabla


def test_comparar_sin_cambios_no_reporta_fallos(bd_temporal):
    snap = capturar(bd_temporal)
    fallos, info = comparar(snap, snap)
    assert fallos == []
    assert info == []


def test_comparar_fila_nueva_no_declarada_es_fallo(bd_temporal):
    import sqlite3
    antes = capturar(bd_temporal)

    con = sqlite3.connect(bd_temporal)
    con.execute(
        "INSERT INTO control_conos (ref, medida, valor) VALUES (9999, 'x', 'y')")
    con.commit()
    con.close()

    despues = capturar(bd_temporal)
    fallos, info = comparar(antes, despues)

    assert any("control_conos" in f and "total" in f for f in fallos)
    assert any("ref=9999" in f and "aparece" in f for f in fallos)


def test_comparar_fila_nueva_declarada_no_es_fallo(bd_temporal):
    import sqlite3
    antes = capturar(bd_temporal)

    con = sqlite3.connect(bd_temporal)
    con.execute(
        "INSERT INTO control_conos (ref, medida, valor) VALUES (9999, 'x', 'y')")
    con.commit()
    con.close()

    despues = capturar(bd_temporal)
    esperado = {
        "vigente_cambios_esperados": {"control_conos": ["9999"]},
        "censo_total_incremento_esperado": ["control_conos"],
    }
    fallos, info = comparar(antes, despues, esperado)

    assert not any("control_conos" in f for f in fallos)
    assert any("control_conos" in i for i in info)


def test_comparar_censo_total_que_baja_siempre_es_fallo_aunque_se_declare(bd_temporal):
    antes = capturar(bd_temporal)
    despues = {**antes, "censo": dict(antes["censo"])}
    despues["censo"] = {**antes["censo"]}
    despues["censo"]["controles"] = {"total": -1, "activas": 0, "anuladas": 0}
    esperado = {"censo_total_incremento_esperado": ["controles"]}

    fallos, _info = comparar(antes, despues, esperado)

    assert any("bajó" in f for f in fallos)
