"""A6.7 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): TAC/Catphan deja rastro en
`audit_log`. De las 9 funciones de `catphan_db.py`,
`guardar_prueba_completa_catphan` es el ÚNICO punto de entrada real (los 2
llamadores de `tac_mensual.py` no escriben directo, solo la llaman); las
otras 8 (`anular_datos_especificos` + 7 `guardar_<categoria>`) se llaman
EXCLUSIVAMENTE desde dentro de ella -- 1 fila de auditoría para toda la
acción, sin importar cuántas categorías se guarden en el mismo click.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from data.ManejoDatos.catphan_TAC.catphan_db import guardar_prueba_completa_catphan
import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    cur = conexion.con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Tomógrafo", "Mensual", "08/2026"))
    conexion.con.commit()
    id_sesion = cur.lastrowid
    yield ruta, id_sesion
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestGuardarPruebaCompletaCatphanAudita:
    def test_una_categoria_audita_una_vez(self, bd_temporal):
        ruta, id_sesion = bd_temporal
        resultado = guardar_prueba_completa_catphan(
            user_id=_UsuarioFalso(), fecha="2026-08-04", equipo="Tomógrafo",
            kv=120, ma=200, espesor_corte=5.0,
            resultados_por_categoria={"espesor": {"espesor_promedio_mm": 5.1}},
            id_sesion=id_sesion)

        assert resultado == id_sesion
        filas = _audit_log(ruta)
        assert filas == [
            ("Físico de Prueba", "guardar", "pruebas", str(id_sesion),
             "CatPhan: espesor")]

    def test_varias_categorias_en_un_solo_guardado_auditan_una_sola_vez(self, bd_temporal):
        """El caso que justifica el diseño: un solo click puede guardar
        VARIAS categorías (espesor, linealidad CT...) -- 1 fila, no una
        por categoría."""
        ruta, id_sesion = bd_temporal
        guardar_prueba_completa_catphan(
            user_id=_UsuarioFalso(), fecha="2026-08-04", equipo="Tomógrafo",
            kv=120, ma=200, espesor_corte=5.0,
            resultados_por_categoria={
                "espesor": {"espesor_promedio_mm": 5.1},
                "linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0,
                                  "r_squared": 0.999},
            },
            id_sesion=id_sesion)

        filas = _audit_log(ruta)
        assert len(filas) == 1
        assert filas[0][:4] == (
            "Físico de Prueba", "guardar", "pruebas", str(id_sesion))
        assert "espesor" in filas[0][4]
        assert "linealidad_ct" in filas[0][4]
