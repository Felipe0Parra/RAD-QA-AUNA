"""E2 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §3): el catálogo de equipos ya
no se borra sin permiso y sin vuelta atrás.

Antes, `Config.eliminarEquipo` solo tenía un `QMessageBox.question` (sin
diálogo de autorización -- el ÚNICO borrado de la app sin barrera) y hacía
`DELETE FROM equipos` físico sobre el catálogo curado a mano en H2.6/H2.10.
Ahora exige `DialogAdminPermisoEliminar` (admin o física jefe, E6) y anula
con `activo = 0` en vez de borrar.
"""
import sqlite3

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QTableWidget, QTableWidgetItem, QWidget

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.equipos as equipos_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.equipos import Config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales (incluye E6: rol_sistema)
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


def _widget_con_fila_seleccionada(id_equipo):
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioActualFalso()
    obj.cargartabla = lambda: None  # refresco de tabla, fuera de alcance aquí
    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem()
    item.setData(Qt.UserRole, id_equipo)
    obj.table.setItem(0, 0, item)
    obj.table.setCurrentCell(0, 0)
    return obj


def _mock_dialogo(monkeypatch, aceptado):
    """El gate real es DialogAdminPermisoEliminar.exec(); se parchea la
    CLASE completa para no depender de login()/es_admin_equivalente aquí
    (ya cubiertos por test_c3_permisos_admin_jefe.py) -- este archivo prueba
    el CABLEADO de eliminarEquipo con el resultado del diálogo, no la lógica
    de permisos en sí."""
    class _DialogoFalso:
        instancias = []

        def __init__(self, user):
            self.user = user
            _DialogoFalso.instancias.append(self)

        def exec(self):
            return QDialog.DialogCode.Accepted if aceptado else QDialog.DialogCode.Rejected

    monkeypatch.setattr(equipos_mod, "DialogAdminPermisoEliminar", _DialogoFalso)
    return _DialogoFalso


def _audit_log(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestSinAutorizacionNoBorraNiAnula:
    def test_dialogo_rechazado_no_toca_la_fila(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo(monkeypatch, aceptado=False)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        activo = con.execute(
            "SELECT activo FROM equipos WHERE id = ?", (id_equipo,)).fetchone()[0]
        n_audit = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert activo == 1
        assert n_audit == 0

    def test_se_pide_el_dialogo_con_la_identidad_del_fisico(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        dialogo_cls = _mock_dialogo(monkeypatch, aceptado=False)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert len(dialogo_cls.instancias) == 1
        assert dialogo_cls.instancias[0].user is obj.user_id


class TestConAutorizacionAnulaSinBorrar:
    def test_la_fila_sigue_existiendo_con_activo_cero(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo(monkeypatch, aceptado=True)
        monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT model, serie, activo FROM equipos WHERE id = ?", (id_equipo,)).fetchone()
        con.close()
        assert fila == ("Clinac iX", "SN-123", 0)  # NUNCA desaparece

    def test_audita_anular_con_modelo_y_serie(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo(monkeypatch, aceptado=True)
        monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert _audit_log(bd_temporal) == [
            ("Físico de Prueba", "anular", "equipos", "Clinac iX/SN-123", "tipo: Acelerador")]


class TestEquipoAnuladoDesapareceDeSelectoresPeroResuelveHistorico:
    def test_no_aparece_en_series_del_modelo(self, app, bd_temporal, monkeypatch):
        from services.equipos_service import EquiposService
        id_equipo = _preparar_equipo(bd_temporal, model="TN31010", serie="1822")
        _mock_dialogo(monkeypatch, aceptado=True)
        monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        series = EquiposService.obtener_series_por_modelo("TN31010")
        assert series == []

    def test_control_historico_sigue_resolviendo_modelo_y_serie(self, app, bd_temporal, monkeypatch):
        """Un control mensual/anual que referencia el equipo por su id lo
        sigue encontrando -- anular no es borrar."""
        id_equipo = _preparar_equipo(bd_temporal, model="TN31010", serie="1822")
        _mock_dialogo(monkeypatch, aceptado=True)
        monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj = _widget_con_fila_seleccionada(id_equipo)
        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT model, serie FROM equipos WHERE id = ?", (id_equipo,)).fetchone()
        con.close()
        assert fila == ("TN31010", "1822")
