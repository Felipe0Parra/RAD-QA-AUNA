"""SA2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-SA2): tripwire permanente,
independiente del índice UNIQUE de CL1 (que todavía no existe en esta
fase) -- convierte el saneamiento de SA1 en una garantía que se puede
volver a comprobar, no en un arreglo de una sola vez.

`verificar_sin_duplicados_activos` es también el gate que
`migrar_bd_a_estandar.py::migrar` corre DESPUÉS de aplicar SA1, para que un
caso que SA1 no resolviera se vea como una ALERTA GRAVE en la migración,
no como un fallo silencioso de CL1 más adelante.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.saneamiento_bloque_qc import (
    sanear_bloque_qc, verificar_sin_duplicados_activos, CLAVES_NATURALES,
)


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


def _insertar_cunas(ruta, ref, angulo, activo=1):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO control_cunas (ref, angulo, activo) VALUES (?, ?, ?)",
        (ref, angulo, activo))
    con.commit()
    rowid = cur.lastrowid
    con.close()
    return rowid


def test_bd_limpia_no_reporta_violaciones(bd_temporal):
    con = sqlite3.connect(bd_temporal)
    assert verificar_sin_duplicados_activos(con) == []
    con.close()


def test_detecta_clave_duplicada_activa(bd_temporal):
    r1 = _insertar_cunas(bd_temporal, 30, 45)
    r2 = _insertar_cunas(bd_temporal, 30, 45)

    con = sqlite3.connect(bd_temporal)
    violaciones = verificar_sin_duplicados_activos(con)
    con.close()

    assert len(violaciones) == 1
    v = violaciones[0]
    assert v["tabla"] == "control_cunas"
    assert v["clave"] == {"ref": 30, "angulo": 45}
    assert set(v["rowids"]) == {r1, r2}


def test_sanear_bloque_qc_deja_la_verificacion_limpia(bd_temporal):
    _insertar_cunas(bd_temporal, 30, 45)
    _insertar_cunas(bd_temporal, 30, 45)

    con = sqlite3.connect(bd_temporal)
    assert verificar_sin_duplicados_activos(con) != []
    con.close()

    sanear_bloque_qc(bd_temporal, usuario="Físico de Prueba")

    con = sqlite3.connect(bd_temporal)
    assert verificar_sin_duplicados_activos(con) == []
    con.close()


def test_cubre_las_8_tablas_de_h2():
    """No una muestra -- las 8 tablas originales donde el hallazgo H2 (§2.3
    del plan del 13-08) encontró claves duplicadas, más las 4 que MI2 y las
    4 diarias que MI3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI2/§6-MI3)
    añadieron con los duplicados reales medidos en §2.8 de ese plan."""
    assert set(CLAVES_NATURALES) == {
        "control_cunas", "control_conos", "equipos_medicion",
        "analisis_placa_franjas", "tamano_campo",
        "HC_indicadores_camilla", "HC_indicadores_colimador",
        "HC_indicadores_laser",
        "analisis_placa_verificaciones", "analisis_placa_correcciones",
        "indicadores_brazo", "indicadores_angulares_colimador",
        "aceleradorlineal_600", "aceleradorlineal_ix", "halcyon", "braqui",
    }
