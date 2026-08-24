"""EB2c (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2c, 24-08, cierra G6):
`guardar_prueba_completa_catphan` mutaba `pruebas` en sitio (`UPDATE ...
WHERE id_prueba=?`) y borraba físicamente sus tablas hijas
(`eliminar_datos_especificos`) en cada reguardado de la misma
(`id_sesion`, `id_tipo`) -- mismo patrón que G1/G2 en braquiterapia/MLC,
sobre otra raíz del bloque de QC.

Reescrita: `pruebas` reemplaza su bloque (EB1) -- la fila anterior se
ANULA, la nueva entra con un `id_prueba` NUEVO -- y sus hijas (según la
categoría: `espesor_corte`, `tamaño_pixel`, ...) se anulan explícitamente
sobre el `id_prueba` ANTERIOR (`anular_datos_especificos`, ya no borra).
La imagen asociada (`imagen_path`/`imagen_resultado`) se conserva si el
reguardado no trae una nueva -- mismo criterio que el `UPDATE` original.

Un solo `try/except` con `rollback()` explícito sigue envolviendo toda la
función (ya lo tenía); lo nuevo es que `anular_datos_especificos` ya NO
traga sus propios fallos (G6) -- un error ahí debe propagar hasta ese
`rollback()`.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.catphan_TAC.catphan_db as catphan_db
from data.ManejoDatos.catphan_TAC.catphan_db import guardar_prueba_completa_catphan


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _con(ruta):
    return sqlite3.connect(ruta)


def _crear_control(ruta, equipo="Halcyon", fecha="06/2026"):
    con = _con(ruta)
    con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)",
        (equipo, fecha))
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


def _guardar(id_sesion, categorias, **kwargs):
    base = dict(
        user_id="fisico1", fecha="2026-06-01", equipo="Halcyon TAC",
        kv=120, ma=100, espesor_corte=1.5,
        resultados_por_categoria=categorias, id_sesion=id_sesion,
    )
    base.update(kwargs)
    return guardar_prueba_completa_catphan(**base)


class TestReguardarConservaHistoria:

    def test_pruebas_anterior_queda_anulada_no_borrada(self, bd_temporal):
        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.5}})
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 3.0}})

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT espesor_corte, activo FROM pruebas WHERE id_sesion=? AND id_tipo=1 "
            "ORDER BY id_prueba", (sesion,)).fetchall()
        con.close()

        assert len(filas) == 2, "2 generaciones, ninguna borrada"
        assert [f[1] for f in filas] == [0, 1]

    def test_hijas_del_id_prueba_anterior_quedan_anuladas(self, bd_temporal):
        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.5}})

        con = _con(bd_temporal)
        id_prueba_1 = con.execute(
            "SELECT id_prueba FROM pruebas WHERE id_sesion=? AND id_tipo=1",
            (sesion,)).fetchone()[0]
        con.close()

        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 3.0}})

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT espesor_promedio_mm, activo FROM espesor_corte "
            "ORDER BY id_prueba").fetchall()
        activo_viejo = con.execute(
            "SELECT activo FROM espesor_corte WHERE id_prueba=?", (id_prueba_1,)).fetchone()[0]
        con.close()

        assert len(filas) == 2, "las hijas del id_prueba anterior deben SOBREVIVIR, anuladas"
        assert activo_viejo == 0

    def test_categorias_distintas_no_interfieren_entre_si(self, bd_temporal):
        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {
            "espesor": {"espesor_promedio_mm": 2.5},
            "linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999},
        })

        con = _con(bd_temporal)
        tipos = con.execute(
            "SELECT id_tipo, activo FROM pruebas WHERE id_sesion=? ORDER BY id_tipo",
            (sesion,)).fetchall()
        con.close()
        assert tipos == [(1, 1), (6, 1)], "espesor (id_tipo=1) y linealidad_ct (id_tipo=6)"


class TestUnaSolaAuditoriaPorLlamada:

    def test_dos_categorias_en_un_click_dejan_una_sola_fila(self, bd_temporal):
        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {
            "espesor": {"espesor_promedio_mm": 2.5},
            "linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999},
        })

        con = _con(bd_temporal)
        total = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert total == 1, "A6.7: 1 fila para toda la acción, sin importar cuántas categorías"

    def test_reguardar_deja_una_fila_mas_por_llamada(self, bd_temporal):
        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.5}})
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 3.0}})

        con = _con(bd_temporal)
        total = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert total == 2


class TestImagenSeConserva:

    def test_sin_imagen_nueva_conserva_la_anterior(self, bd_temporal, monkeypatch):
        monkeypatch.setattr(
            catphan_db, "convertir_corte_dicom_a_blob",
            lambda *a, **k: b"imagen-original")

        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.5}},
                 info_dicom={"ruta_carpeta": "/x"}, output_blob=b"resultado-original")
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 3.0}})  # sin info_dicom

        con = _con(bd_temporal)
        fila = con.execute(
            "SELECT imagen_path, imagen_resultado FROM pruebas "
            "WHERE id_sesion=? AND activo=1", (sesion,)).fetchone()
        con.close()
        assert fila == (b"imagen-original", b"resultado-original"), (
            "sin imagen nueva, la generación nueva debe conservar la imagen "
            "de la anterior -- mismo criterio que el UPDATE original")

    def test_con_imagen_nueva_la_reemplaza(self, bd_temporal, monkeypatch):
        monkeypatch.setattr(
            catphan_db, "convertir_corte_dicom_a_blob",
            lambda *a, **k: b"imagen-A")

        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.5}},
                 info_dicom={"ruta_carpeta": "/x"}, output_blob=b"resultado-A")

        monkeypatch.setattr(
            catphan_db, "convertir_corte_dicom_a_blob",
            lambda *a, **k: b"imagen-B")
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 3.0}},
                 info_dicom={"ruta_carpeta": "/y"}, output_blob=b"resultado-B")

        con = _con(bd_temporal)
        fila = con.execute(
            "SELECT imagen_path, imagen_resultado FROM pruebas "
            "WHERE id_sesion=? AND activo=1", (sesion,)).fetchone()
        con.close()
        assert fila == (b"imagen-B", b"resultado-B")


class TestRollback:

    def test_fallo_en_una_categoria_revierte_todo(self, bd_temporal, monkeypatch):
        sesion = _crear_control(bd_temporal)
        _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.5}})

        def _falla(*a, **k):
            raise RuntimeError("fallo simulado (EB2c test)")

        monkeypatch.setattr(catphan_db, "guardar_linealidad_ct", _falla)

        resultado = _guardar(sesion, {
            "espesor": {"espesor_promedio_mm": 3.0},
            "linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999},
        })
        assert resultado is None, (
            "guardar_prueba_completa_catphan atrapa la excepción y devuelve "
            "None -- mismo contrato de siempre")

        con = _con(bd_temporal)
        filas_pruebas = con.execute(
            "SELECT activo FROM pruebas WHERE id_sesion=? AND id_tipo=1",
            (sesion,)).fetchall()
        con.close()
        assert filas_pruebas == [(1,)], (
            "un fallo en OTRA categoría (linealidad_ct) dentro de la misma "
            "transacción debe revertir TAMBIÉN lo que 'espesor' ya había "
            "hecho en esta llamada -- no debe quedar una generación nueva "
            "de espesor a medio camino")
