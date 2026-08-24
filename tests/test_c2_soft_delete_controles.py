"""C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md / PLAN_AUDITORIA_DOS_EJES_21-07.md
§7 P4): el físico pidió soft-delete ("no veo ningún soft-delete, el registro
borrado dónde queda en caso de querer reponerlo").

Antes de esta tarea, `eliminarRegistroCT`/`eliminarRegistroCT_anual` hacían
DELETE físico en cascada: primero las 7 tablas de resultados CT + `pruebas`,
luego `controles` -- contra la regla del proyecto de nunca eliminar
registros históricos. Ahora anulan (`controles.activo = 0`) y NO tocan
ninguna tabla de detalle -- quedan colgadas del mismo `id_sesion`,
recuperables si el control se reactiva.

Esta suite cubre lo que test_a2_auditar_borrado.py (actualizado en la misma
tarea) no cubre: que las tablas de DETALLE sobreviven intactas al "borrado".
"""
import sqlite3

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import (
    eliminarRegistro, eliminarRegistroCT, eliminarRegistroCT_anual)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _reset_qtsql_default_connection():
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real
    conexion.con.close()
    Conexion._instance = None

    _reset_qtsql_default_connection()
    yield ruta
    _reset_qtsql_default_connection()


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _DlgFalso:
    user_id = _UsuarioFalso()


def _tabla_con_fila(id_valor, texto="fila"):
    tabla = QTableWidget(1, 1)
    item = QTableWidgetItem(texto)
    item.setData(Qt.UserRole, id_valor)
    tabla.setItem(0, 0, item)
    tabla.setCurrentCell(0, 0)
    return tabla


def _no_confirmar_qmessagebox(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "question",
                         staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))


class TestEliminarRegistroCTNoBorraTablasDeDetalle:
    """Antes: 7 DELETE (espesor_corte, tamano_pixel, resolucion_contraste,
    resolucion_espacial, valores_ct, linealidad_ct, uniformidad_ruido) +
    DELETE de `pruebas` + DELETE de `controles`. Ahora: solo UPDATE de
    `controles.activo` -- las mediciones reales NUNCA se tocan."""

    def test_pruebas_y_resultados_ct_sobreviven_a_la_anulacion(self, app, bd_temporal, monkeypatch):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (10, 'Tomógrafo', 'diario', '2026-05-01', 'Otro Fisico')")
        con.execute(
            "INSERT INTO pruebas (id_prueba, id_sesion, id_tipo, kv, ma, espesor_corte) "
            "VALUES (100, 10, 1, 120, 200, 5.0)")
        con.execute(
            "INSERT INTO espesor_corte "
            "(id_prueba, espesor_promedio_mm, espesor_teorico_mm, diferencia_mm, error_pct) "
            "VALUES (100, 5.0, 5.0, 0.0, 0.0)")
        con.execute(
            "INSERT INTO valores_ct "
            "(id_prueba, id_material, promedio_hu, error_absoluto, error_relativo) "
            "VALUES (100, 1, 0.0, 0.0, 0.0)")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(10, texto="Mayo 2026")

        eliminarRegistroCT(_DlgFalso(), tabla)

        con = sqlite3.connect(bd_temporal)
        activo = con.execute(
            "SELECT activo FROM controles WHERE id = 10").fetchone()[0]
        n_pruebas = con.execute(
            "SELECT COUNT(*) FROM pruebas WHERE id_sesion = 10").fetchone()[0]
        n_espesor = con.execute(
            "SELECT COUNT(*) FROM espesor_corte WHERE id_prueba = 100").fetchone()[0]
        n_valores = con.execute(
            "SELECT COUNT(*) FROM valores_ct WHERE id_prueba = 100").fetchone()[0]
        con.close()

        assert activo == 0, "el control debe quedar anulado"
        assert n_pruebas == 1, "pruebas NO debe borrarse -- antes se perdía"
        assert n_espesor == 1, "espesor_corte NO debe borrarse -- dato clínico real"
        assert n_valores == 1, "valores_ct NO debe borrarse -- dato clínico real"


class TestEliminarRegistroCTAnualNoBorraTablasDeDetalle:
    def test_pruebas_y_resultados_ct_sobreviven_a_la_anulacion(self, app, bd_temporal, monkeypatch):
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (11, 'Tomógrafo', 'anual', '2026-01-01', 'Otro Fisico')")
        con.execute(
            "INSERT INTO pruebas (id_prueba, id_sesion, id_tipo, kv, ma, espesor_corte) "
            "VALUES (101, 11, 1, 120, 200, 5.0)")
        con.execute(
            "INSERT INTO linealidad_ct (id_prueba, pendiente) VALUES (101, 1.0)")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(11, texto="2026")

        eliminarRegistroCT_anual(_DlgFalso(), tabla)

        con = sqlite3.connect(bd_temporal)
        activo = con.execute(
            "SELECT activo FROM controles WHERE id = 11").fetchone()[0]
        n_pruebas = con.execute(
            "SELECT COUNT(*) FROM pruebas WHERE id_sesion = 11").fetchone()[0]
        n_lineal = con.execute(
            "SELECT COUNT(*) FROM linealidad_ct WHERE id_prueba = 101").fetchone()[0]
        con.close()

        assert activo == 0
        assert n_pruebas == 1
        assert n_lineal == 1


class TestEliminarRegistroSoloAnulaControles:
    """El eliminarRegistro genérico sigue borrando físicamente cualquier
    OTRA tabla (subtablas vía "Ver tabla", catálogos) -- solo "controles"
    cambia a soft-delete."""

    def test_tabla_fuera_de_la_lista_blanca_sigue_con_delete_fisico(self, app, bd_temporal, monkeypatch):
        """E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11) AMPLIÓ la lista de
        tablas que anulan en vez de borrar (TipoCalibracion pasó a anular --
        ver test_e7_soft_delete_bloque_qc.py, que reemplaza esta afirmación
        para esa tabla en concreto). M1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_
        11-08.md) hizo que "control_conos" TAMBIÉN entrara a
        `services.anulacion.TABLAS_ANULABLES` (junto a su vecina
        "control_cunas"), y MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1)
        movió "HC_fantomas" (el ejemplo que usaba esta prueba hasta aquí) al
        frozenset con las otras 29 tablas PENDIENTE-LF -- ya no sirve como
        ejemplo de "fuera de la lista". Este test pasa a usar
        "calculadora_dosimetrica": NUNCA fue parte del bloque de QC (no
        cuelga de ninguna de las 7 raíces por clave foránea, versiona con su
        propia columna `vigente`, no `activo` -- ver
        `services/dosis_service.py`), así que es un ejemplo permanente de
        tabla fuera de la lista blanca, no uno que MI1 pueda volver a
        mover."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO calculadora_dosimetrica (id, Fecha, Acelerador) "
            "VALUES (99, '2026-01-01', 'equipo')")
        con.commit()
        con.close()

        _no_confirmar_qmessagebox(monkeypatch)
        tabla = _tabla_con_fila(99)

        eliminarRegistro(_DlgFalso(), tabla, "calculadora_dosimetrica")

        con = sqlite3.connect(bd_temporal)
        n = con.execute(
            "SELECT COUNT(*) FROM calculadora_dosimetrica WHERE id = 99").fetchone()[0]
        con.close()
        assert n == 0, "las tablas fuera de la lista blanca siguen con DELETE físico"

    def test_no_encontrar_el_control_a_anular_no_revienta_en_silencio(self, app, bd_temporal, monkeypatch):
        """id inexistente en 'controles' -- no debe reventar con un
        traceback opaco ni marcar éxito falso."""
        avisos = []
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                             staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "critical",
                             staticmethod(lambda *a, **k: avisos.append(a)))
        monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

        tabla = _tabla_con_fila(9999)
        eliminarRegistro(_DlgFalso(), tabla, "controles")

        assert len(avisos) == 1, "debe avisar el error, no fallar en silencio"
