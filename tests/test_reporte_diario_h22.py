"""H2.2 (auditoría 2026-07-14) -- el reporte diario ya no se reemplaza en
silencio.

Antes: `add_info` (load.py) hacía `DELETE FROM {tabla} WHERE DATE(date)=?`
seguido de INSERT, sin verificar si ya existía un reporte para esa fecha --
reemplazo silencioso, sin rastro ni confirmación (hallazgo PLAN_FASE_H
sección 1.6.2). El reemplazo (con confirmación) se mantiene como decisión
de producto; EB4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB4, 24-08) cambió el
mecanismo de `DELETE+INSERT` a `reemplazar_bloque` (anula, nunca borra) --
el reporte anterior sigue en la BD, recuperable.

`Conexion` (data/ManejoDatos/conection.py) es un SINGLETON de proceso
(`__new__` cachea `_instance`) que en su primera creación corre TODO el
DDL de la app (`createTable` + 7 `crearTablas*` más). Como esta suite es
la primera en tocar `Conexion`, `ruta_base_datos` se parchea ANTES de
instanciarla -- si no, esa primera creación tocaría la BD real de
producción (violación directa de la regla "solo lectura").
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QDateEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import add_info, _confirmar_reemplazo_reporte_diario


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None  # fuerza reinicialización con la ruta parcheada
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _BotonFalso:
    def __init__(self, estado="Funciona"):
        self._estado = estado

    def text(self):
        return self._estado


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _self_falso():
    self_falso = QWidget()
    self_falso.date_box = QDateEdit()
    self_falso.date_box.setDisplayFormat("yyyy-MM-dd")
    self_falso.date_box.setDate(QDate(2026, 7, 14))
    self_falso.user_id = _UsuarioFalso()
    # aceleradorlineal_600 tiene 17 columnas booleanas entre user_id y observaciones.
    self_falso.botones_ordenados = [(_BotonFalso(),) for _ in range(17)]
    self_falso.boolean_colums = list(range(17))
    self_falso.df_lines = []
    self_falso.df_lines_dosis = []
    self_falso.observaciones = None
    return self_falso


class TestConfirmarReemplazoReporteDiario:
    """La función aislada -- mockeable sin QMessageBox real (regla 5)."""

    def test_usuario_confirma_devuelve_true(self, app, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
        assert _confirmar_reemplazo_reporte_diario(object(), "aceleradorlineal_600", "14/07/2026") is True

    def test_usuario_rechaza_devuelve_false(self, app, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.No))
        assert _confirmar_reemplazo_reporte_diario(object(), "aceleradorlineal_600", "14/07/2026") is False

    def test_boton_por_defecto_es_no(self, app, monkeypatch):
        capturado = {}

        def espia(*a, **k):
            capturado["default"] = a[4] if len(a) > 4 else k.get("defaultButton")
            return load_mod.QMessageBox.No
        monkeypatch.setattr(load_mod.QMessageBox, "question", staticmethod(espia))

        _confirmar_reemplazo_reporte_diario(object(), "aceleradorlineal_600", "14/07/2026")

        assert capturado["default"] == load_mod.QMessageBox.No


class TestAddInfoConfirmaAntesDeReemplazar:
    """Integración real contra una BD temporal (schema completo vía
    Conexion, ver docstring del módulo)."""

    def _guardar(self, monkeypatch, confirmar_devuelve):
        monkeypatch.setattr(load_mod, "load_table", lambda *a, **k: None)
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        llamado = []
        if confirmar_devuelve is None:
            def reventar(*a, **k):
                raise AssertionError("no debería preguntar sin registro previo para esa fecha")
            monkeypatch.setattr(load_mod, "_confirmar_reemplazo_reporte_diario", reventar)
        else:
            monkeypatch.setattr(
                load_mod, "_confirmar_reemplazo_reporte_diario",
                lambda *a, **k: llamado.append(True) or confirmar_devuelve)
        add_info(_self_falso(), "aceleradorlineal_600", ["a", "b"])
        return llamado

    def _contar_registros(self, ruta_db, solo_vigentes=True):
        conn = sqlite3.connect(ruta_db)
        query = "SELECT COUNT(*) FROM aceleradorlineal_600 WHERE DATE(date)='2026-07-14'"
        if solo_vigentes:
            query += " AND (activo IS NULL OR activo = 1)"
        n = conn.execute(query).fetchone()[0]
        conn.close()
        return n

    def test_sin_registro_previo_no_pregunta_y_guarda(self, app, bd_temporal, monkeypatch):
        llamado = self._guardar(monkeypatch, confirmar_devuelve=None)

        assert not llamado
        assert self._contar_registros(bd_temporal) == 1

    def test_con_registro_previo_y_no_no_toca_la_bd(self, app, bd_temporal, monkeypatch):
        self._guardar(monkeypatch, confirmar_devuelve=None)  # crea el primero, sin preguntar

        llamado = self._guardar(monkeypatch, confirmar_devuelve=False)

        assert llamado, "debía preguntar -- ya había un registro para esa fecha"
        assert self._contar_registros(bd_temporal) == 1  # sigue habiendo solo el original

    def test_con_registro_previo_y_si_reemplaza(self, app, bd_temporal, monkeypatch):
        self._guardar(monkeypatch, confirmar_devuelve=None)

        llamado = self._guardar(monkeypatch, confirmar_devuelve=True)

        assert llamado
        # EB4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB4, 24-08): el reemplazo
        # ya no BORRA el registro anterior, lo ANULA -- una sola VIGENTE,
        # pero el anterior sigue en la BD, recuperable.
        assert self._contar_registros(bd_temporal) == 1  # una sola VIGENTE
        assert self._contar_registros(bd_temporal, solo_vigentes=False) == 2
