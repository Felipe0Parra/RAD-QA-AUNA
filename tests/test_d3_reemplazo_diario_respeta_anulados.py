"""D3 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, hallazgo S1): el
reemplazo diario (`add_info`/`conectarfueradeservicio`) no puede borrar
FÍSICAMENTE una fila diaria que estuviera ANULADA para esa fecha -- contra
E7/DA-03 (soft-delete, nunca borrado físico).

Antes de este fix, el `SELECT COUNT`/`DELETE` de reemplazo no filtraban
`activo`: guardar un control diario normal (o "fuera de servicio") para una
fecha con una fila anulada la habría eliminado de verdad.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QDateEdit, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import add_info, conectarfueradeservicio


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _BotonFalso:
    def __init__(self, estado="Funciona"):
        self._estado = estado

    def text(self):
        return self._estado


def _self_falso_600(fecha=QDate(2026, 8, 5)):
    self_falso = QWidget()
    self_falso.date_box = QDateEdit()
    self_falso.date_box.setDate(fecha)
    self_falso.user_id = _UsuarioFalso()
    # aceleradorlineal_600 tiene 17 columnas booleanas entre user_id y observaciones.
    self_falso.botones_ordenados = [(_BotonFalso(),) for _ in range(17)]
    self_falso.boolean_colums = list(range(17))
    self_falso.df_lines = []
    self_falso.df_lines_dosis = []
    self_falso.observaciones = None
    return self_falso


def _self_falso_ix(fecha=QDate(2026, 8, 5)):
    w = QWidget()
    w.user_id = _UsuarioFalso()
    w.date_box = QDateEdit()
    w.date_box.setDate(fecha)
    w.observaciones = QLineEdit("mantenimiento")
    return w


def _insertar_fila_anulada(ruta_bd, tabla, fecha_iso, cols_extra=""):
    con = sqlite3.connect(ruta_bd)
    if tabla == "aceleradorlineal_600":
        con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id, observaciones, activo) "
            "VALUES (?, ?, ?, 0)", (fecha_iso, "Otro Físico", "anulada"))
    else:
        con.execute(
            "INSERT INTO aceleradorlineal_ix (date, user_id, observaciones, activo) "
            "VALUES (?, ?, ?, 0)", (fecha_iso, "Otro Físico", "anulada"))
    con.commit()
    con.close()


def _filas(ruta_bd, tabla, fecha_iso):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        f"SELECT user_id, observaciones, activo FROM {tabla} WHERE DATE(date) = ?",
        (fecha_iso,)).fetchall()
    con.close()
    return filas


class TestD3AddInfoRespetaAnulados:

    def test_fila_anulada_sobrevive_a_guardado_normal(self, app, bd_temporal, monkeypatch):
        _insertar_fila_anulada(bd_temporal, "aceleradorlineal_600", "2026-08-05")

        def reventar(*a, **k):
            raise AssertionError("no debía preguntar -- lo único activo es nuevo, no hay reemplazo")
        monkeypatch.setattr(load_mod, "_confirmar_reemplazo_reporte_diario", reventar)
        monkeypatch.setattr(load_mod, "load_table", lambda *a, **k: None)

        add_info(_self_falso_600(), "aceleradorlineal_600", ["a", "b"])

        filas = _filas(bd_temporal, "aceleradorlineal_600", "2026-08-05")
        assert len(filas) == 2  # la anulada + la nueva activa
        anuladas = [f for f in filas if f[2] == 0]
        assert anuladas == [("Otro Físico", "anulada", 0)]

    def test_fila_activa_si_se_reemplaza(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod, "load_table", lambda *a, **k: None)
        add_info(_self_falso_600(), "aceleradorlineal_600", ["a", "b"])  # primera, activa

        preguntado = []
        monkeypatch.setattr(
            load_mod, "_confirmar_reemplazo_reporte_diario",
            lambda *a, **k: preguntado.append(True) or True)
        add_info(_self_falso_600(), "aceleradorlineal_600", ["a", "b"])  # segunda, reemplaza

        assert preguntado, "debía preguntar -- ya había una fila ACTIVA para esa fecha"
        filas = _filas(bd_temporal, "aceleradorlineal_600", "2026-08-05")
        # EB4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB4, 24-08): el reemplazo
        # ya no BORRA la fila anterior, la ANULA -- 1 sola VIGENTE, pero 2
        # en total (la primera sobrevive, recuperable).
        assert len([f for f in filas if f[2] == 1]) == 1, "una sola VIGENTE"
        assert len(filas) == 2, "la primera no se borró -- quedó anulada"


class TestD3ConectarFueraDeServicioRespetaAnulados:

    def test_fila_anulada_sobrevive_a_fuera_de_servicio(self, app, bd_temporal, monkeypatch):
        _insertar_fila_anulada(bd_temporal, "aceleradorlineal_ix", "2026-08-05")

        def reventar(*a, **k):
            raise AssertionError("no debía preguntar -- lo único activo es nuevo")
        monkeypatch.setattr(load_mod, "_confirmar_reemplazo_reporte_diario", reventar)

        conectarfueradeservicio(_self_falso_ix(), "aceleradorlineal_ix")

        filas = _filas(bd_temporal, "aceleradorlineal_ix", "2026-08-05")
        assert len(filas) == 2
        anuladas = [f for f in filas if f[2] == 0]
        assert anuladas == [("Otro Físico", "anulada", 0)]
