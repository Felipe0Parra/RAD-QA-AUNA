"""A12 (PLAN_FUGA_CONEXIONES_01-09.md §9, último hallazgo del propio
tripwire R5 -- confirmado por R5 como el único sitio pendiente tras
A9/A10/A11): `equipos.py::Config.eliminarEquipo` -- RIESGO ALTO, mismo
patrón que A6 (`guardarCambios`) sobre la misma tabla: `SELECT` + `UPDATE
... SET activo = 0` + `commit` + `close` explícito, sin ningún `try`/
`except`. Si el `UPDATE` (o el `SELECT` previo) revienta, la conexión queda
abierta con lo que alcanzó a ejecutar.

El `with` cubre exactamente la parte que usa `conn` (líneas 998-1006 antes
del arreglo): `cursor = conn.cursor()` hasta el `conn.commit()`. El
`conn.close()` explícito (redundante bajo `with`) se retira -- la lógica de
auditoría/aviso que sigue después no toca `conn`, se queda fuera del bloque
tal cual estaba.

Este archivo (`equipos.py`) no aparece en ninguno de los 4 censos AST
(`test_lr1`/`test_le4`/`test_eb5`/`_rt1_interceptor_sql`) -- la tabla
`equipos` no es una raíz del bloque de QC que esos tripwires vigilan (es el
catálogo de equipos, tratado aparte por diseño, DA-01/DA-24). Ningún ajuste
de Trampa 5/6 aplica aquí.

P2: `id_equipo` viaja directo como parámetro de bind al `SELECT` inicial
(`cursor.execute("SELECT ... WHERE id = ?", (id_equipo,))`) -- un valor NO
bindeable (una lista) revienta ahí mismo, dentro del `with`, sin necesidad
de mockear ningún helper."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QTableWidget, QTableWidgetItem, QWidget

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.equipos as equipos_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasGuia.equipos import Config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "accastellanos"


def _preparar_equipo(ruta, equip_type="Acelerador", model="Clinac iX", serie="SN-123"):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO equipos (equip_type, model, serie, activo) VALUES (?, ?, ?, 1)",
        (equip_type, model, serie))
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


def _widget_con_fila_seleccionada(id_para_el_widget):
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioActualFalso()
    obj.cargartabla = lambda: None
    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem()
    item.setData(Qt.UserRole, id_para_el_widget)
    obj.table.setItem(0, 0, item)
    obj.table.setCurrentCell(0, 0)
    return obj


def _mock_dialogo_aceptado(monkeypatch):
    class _DialogoFalso:
        def __init__(self, user):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(equipos_mod, "DialogAdminPermisoEliminar", _DialogoFalso)


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA12EliminarEquipoCierraSiempre:
    def test_select_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        _preparar_equipo(bd_temporal)
        _mock_dialogo_aceptado(monkeypatch)

        obj = _widget_con_fila_seleccionada(["no bindeable"])

        with pytest.raises(sqlite3.ProgrammingError):
            Config.eliminarEquipo(obj)

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_anulando_igual(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo_aceptado(monkeypatch)
        monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                             staticmethod(lambda *a, **k: None))
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT model, serie, activo FROM equipos WHERE id = ?", (id_equipo,)).fetchone()
        n_audit = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert fila == ("Clinac iX", "SN-123", 0)
        assert n_audit == 1
