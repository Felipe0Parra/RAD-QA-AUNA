"""SA1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-SA1, [[DA-38]]): saneamiento de
claves duplicadas activas del bloque de QC.

`scripts/saneamiento_bloque_qc.py::sanear_bloque_qc` resuelve, en las 8
tablas de H2 (§2.3 del plan), cada grupo de filas ACTIVAS que comparten la
misma clave natural: gana el bloque de mayor `rowid` (el más reciente), el
resto pasa a `activo = 0`. Nunca borra.

Ya se validó empíricamente contra copias reales de producción en
`tests/test_u2_indice_unico_controles.py::TestEnsayoSobreCopiaDeBDReales`
(57 filas, 41 claves, censo intacto salvo `audit_log`). Este archivo prueba
el algoritmo en aislamiento: qué gana, qué queda auditado, que nada se
borra, que dry-run no toca nada, y que una segunda corrida no encuentra
nada más que hacer.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.saneamiento_bloque_qc import sanear_bloque_qc, sanear_tabla, CLAVES_NATURALES


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales, incl. `activo` en las 8 tablas
    conexion.con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, activo) "
        "VALUES (30, 'Clinac 600', 'Mensual', '08/2026', 1)")
    conexion.con.commit()
    conexion.con.close()
    Conexion._instance = None
    yield ruta


def _insertar_cunas(ruta, ref, angulo, valor, activo=1):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO control_cunas (ref, angulo, observaciones, activo) VALUES (?, ?, ?, ?)",
        (ref, angulo, valor, activo))
    con.commit()
    rowid = cur.lastrowid
    con.close()
    return rowid


def _insertar_tamano_campo(ruta, ref, campo_nominal, valor, activo=1):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO tamano_campo (ref, campo_nominal, ie_largoy1, activo) "
        "VALUES (?, ?, ?, ?)",
        (ref, campo_nominal, valor, activo))
    con.commit()
    rowid = cur.lastrowid
    con.close()
    return rowid


def _filas(ruta, tabla, ref):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        f'SELECT rowid, activo FROM "{tabla}" WHERE ref = ?', (ref,)).fetchall()
    con.close()
    return dict(filas)


def _audit_log(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


def test_todas_las_claves_naturales_tienen_su_tabla_real(bd_temporal):
    con = sqlite3.connect(bd_temporal)
    for tabla, clave in CLAVES_NATURALES.items():
        columnas = {f[1] for f in con.execute(f'PRAGMA table_info("{tabla}")')}
        assert "activo" in columnas, f"{tabla} sin columna activo"
        for col in clave:
            assert col in columnas, f"{tabla}.{col} no existe"
    con.close()


def test_gana_el_rowid_mas_reciente_y_el_resto_queda_historico(bd_temporal):
    r1 = _insertar_cunas(bd_temporal, 30, 45, "1.0")
    r2 = _insertar_cunas(bd_temporal, 30, 45, "1.1")
    r3 = _insertar_cunas(bd_temporal, 30, 45, "1.2")  # el más reciente
    assert r3 > r2 > r1

    anuladas = sanear_bloque_qc(bd_temporal, usuario="Físico de Prueba")

    filas = _filas(bd_temporal, "control_cunas", 30)
    assert filas[r1] == 0
    assert filas[r2] == 0
    assert filas[r3] == 1  # el ganador sigue activo, sin tocar
    assert len(filas) == 3  # nadie se borró

    anuladas_cunas = [a for a in anuladas if a["tabla"] == "control_cunas"]
    assert {a["rowid"] for a in anuladas_cunas} == {r1, r2}
    assert all(a["gano_rowid"] == r3 for a in anuladas_cunas)


def test_audita_cada_fila_anulada_con_ref_y_motivo(bd_temporal):
    r1 = _insertar_cunas(bd_temporal, 30, 90, "2.0")
    r2 = _insertar_cunas(bd_temporal, 30, 90, "2.1")

    sanear_bloque_qc(bd_temporal, usuario="Físico de Prueba")

    filas = _audit_log(bd_temporal)
    assert len(filas) == 1
    accion, tabla, ref, detalle = filas[0]
    assert accion == "anular"
    assert tabla == "control_cunas"
    assert ref == "30"
    assert "duplicada" in detalle
    assert str(r2) in detalle  # nombra quién ganó


def test_claves_distintas_no_se_confunden(bd_temporal):
    """Dos ángulos distintos no son un duplicado -- ninguno debe tocarse."""
    r1 = _insertar_cunas(bd_temporal, 30, 45, "1.0")
    r2 = _insertar_cunas(bd_temporal, 30, 135, "1.0")

    anuladas = sanear_bloque_qc(bd_temporal, usuario="Físico de Prueba")

    assert anuladas == []
    filas = _filas(bd_temporal, "control_cunas", 30)
    assert filas[r1] == 1
    assert filas[r2] == 1


def test_fila_ya_anulada_no_cuenta_para_el_duplicado(bd_temporal):
    """Una fila activa + una ya anulada con la misma clave no es un
    duplicado ACTIVO -- SA1 resuelve activos, no reescribe historia."""
    r1 = _insertar_cunas(bd_temporal, 30, 45, "1.0", activo=0)
    r2 = _insertar_cunas(bd_temporal, 30, 45, "1.1", activo=1)

    anuladas = sanear_bloque_qc(bd_temporal, usuario="Físico de Prueba")

    assert anuladas == []
    filas = _filas(bd_temporal, "control_cunas", 30)
    assert filas[r1] == 0  # sigue como estaba
    assert filas[r2] == 1  # sigue activa, nadie la tocó


def test_dry_run_no_escribe_nada(bd_temporal):
    r1 = _insertar_tamano_campo(bd_temporal, 30, "10 x 10", "1.0")
    r2 = _insertar_tamano_campo(bd_temporal, 30, "10 x 10", "1.1")

    anuladas = sanear_tabla(sqlite3.connect(bd_temporal), "tamano_campo",
                             usuario="x", dry_run=True)

    assert len(anuladas) == 1
    assert anuladas[0]["rowid"] == r1
    filas = _filas(bd_temporal, "tamano_campo", 30)
    assert filas[r1] == 1  # dry-run: nada cambió de verdad
    assert filas[r2] == 1


def test_segunda_corrida_no_encuentra_nada_mas(bd_temporal):
    _insertar_cunas(bd_temporal, 30, 45, "1.0")
    _insertar_cunas(bd_temporal, 30, 45, "1.1")

    primera = sanear_bloque_qc(bd_temporal, usuario="Físico de Prueba")
    segunda = sanear_bloque_qc(bd_temporal, usuario="Físico de Prueba")

    assert len(primera) == 1
    assert segunda == []
