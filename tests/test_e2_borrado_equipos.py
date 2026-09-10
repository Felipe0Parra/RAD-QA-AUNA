"""E2 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §3): el catálogo de equipos ya
no se borra sin permiso y sin vuelta atrás.

Antes de E2, `Config.eliminarEquipo` solo tenía un `QMessageBox.question`
(sin diálogo de autorización -- el ÚNICO borrado de la app sin barrera) y
hacía `DELETE FROM equipos` físico sobre el catálogo curado a mano en
H2.6/H2.10. E2 exigió `DialogAdminPermisoEliminar` (admin o física jefe,
E6) y cambió el borrado por un soft-delete (`activo = 0`).

CORRECCIÓN 10-09 (PLAN_EQUIPOS_BORRADO_Y_VIGENCIA_10-09.md §2, DA-74): el
soft-delete SE REVIERTE -- "Eliminar" vuelve a borrar la fila de verdad.
La reversión es legítima porque la premisa que motivó el soft-delete (que
un control histórico necesitaba la fila del catálogo para no perder nada)
resultó FALSA al medirla: los controles guardan una COPIA del equipo
(equipos_medicion/SistemaMedicion/calculadora_dosimetrica), nunca una
referencia -- 0 FK declaradas hacia `equipos` en las 72 tablas de la BD.
La puerta de admin (E2/E6) SE CONSERVA sin cambios; lo que cambia es qué
hace el botón una vez autorizado, y se añade una segunda puerta -- un
aviso de confirmación que cuenta las referencias y permite retroceder de
verdad (DA-74).
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


@pytest.fixture(autouse=True)
def _sin_dialogos_bloqueantes(monkeypatch):
    """Trampa 2 (CLAUDE.md): DA-74 añadió un QMessageBox.question real a
    eliminarEquipo -- sin mockearlo, cualquier test que llegue hasta ahí
    cuelga bajo offscreen. information/warning/critical se mockean siempre
    (no hacía falta antes de DA-74, porque el `.information` final era lo
    único que había); cada test controla `.question` con `_mock_confirmar`."""
    for tipo in ("warning", "information", "critical"):
        monkeypatch.setattr(equipos_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))


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


def _mock_confirmar(monkeypatch, respuesta=QMessageBox.Yes):
    """DA-74: segunda puerta, el aviso de borrado real. Por defecto
    confirma (Yes) -- los tests que necesitan probar "cancelar" pasan
    otra `respuesta` explícitamente."""
    monkeypatch.setattr(equipos_mod.QMessageBox, "question",
                        staticmethod(lambda *a, **k: respuesta))


def _audit_log(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestSinAutorizacionNoBorra:
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


class TestConAutorizacionYConfirmacionBorraDeVerdad:
    """DA-74: la fila desaparece por completo -- ya no sobrevive con
    activo=0. Dos puertas, las dos autorizadas, para que el borrado
    ocurra."""

    def test_la_fila_desaparece_por_completo(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo(monkeypatch, aceptado=True)
        _mock_confirmar(monkeypatch)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM equipos WHERE id = ?", (id_equipo,)).fetchone()[0]
        con.close()
        assert n == 0  # NUNCA sobrevive, ni con activo=0

    def test_audita_eliminar_con_modelo_y_serie(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo(monkeypatch, aceptado=True)
        _mock_confirmar(monkeypatch)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla, ref, detalle = filas[0]
        assert (usuario, accion, tabla, ref) == (
            "Físico de Prueba", "eliminar", "equipos", "Clinac iX/SN-123")
        # DA-74: sin la fila, el detalle es lo único que la reconstruye --
        # ya no basta "tipo: Acelerador" (E2 original), hace falta el resto
        # de los campos clínicos.
        assert "equip_type=Acelerador" in detalle


class TestElAvisoDeBorradoPermiteRetroceder:
    """Exigencia explícita del físico (10-09): cancelar el aviso NO debe
    ejecutar el borrado -- de ninguna de las formas en que Qt reporta un
    diálogo cerrado sin aceptar."""

    def test_confirmacion_no_la_fila_sigue_activa(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo(monkeypatch, aceptado=True)
        _mock_confirmar(monkeypatch, respuesta=QMessageBox.No)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        activo = con.execute(
            "SELECT activo FROM equipos WHERE id = ?", (id_equipo,)).fetchone()[0]
        con.close()
        assert activo == 1
        assert _audit_log(bd_temporal) == []


class TestEquipoBorradoDesapareceDeSelectores:
    def test_no_aparece_en_series_del_modelo(self, app, bd_temporal, monkeypatch):
        from services.equipos_service import EquiposService
        id_equipo = _preparar_equipo(bd_temporal, model="TN31010", serie="1822")
        _mock_dialogo(monkeypatch, aceptado=True)
        _mock_confirmar(monkeypatch)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        series = EquiposService.obtener_series_por_modelo("TN31010")
        assert series == []

    def test_control_historico_no_necesita_resolver_contra_el_catalogo(
            self, app, bd_temporal, monkeypatch):
        """CORRECCIÓN 10-09 (DA-74): antes esta prueba afirmaba que un
        control histórico "sigue encontrando" el equipo en el catálogo por
        su id -- eso era la garantía del SOFT-delete y ya no es cierta (la
        fila desaparece). La garantía nueva es otra, y más fuerte: un
        control histórico NO NECESITA resolver nada contra el catálogo,
        porque guarda su PROPIA copia (equipos_medicion) -- 0 FK
        declaradas hacia `equipos`, medido en el plan (§0.1)."""
        id_equipo = _preparar_equipo(bd_temporal, model="TN31010", serie="1822")
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, model, serie,"
            " calibr_fact, equipo_id) VALUES (1, 'Principal', 'Acelerador',"
            " 'TN31010', '1822', 0.3, ?)", (id_equipo,))
        con.commit()
        con.close()

        _mock_dialogo(monkeypatch, aceptado=True)
        _mock_confirmar(monkeypatch)
        obj = _widget_con_fila_seleccionada(id_equipo)
        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        # el catálogo ya NO resuelve -- eso es exactamente lo que cambia
        fila_catalogo = con.execute(
            "SELECT model, serie FROM equipos WHERE id = ?", (id_equipo,)).fetchone()
        # pero el control ya guardó su propia copia, y esa SÍ sigue intacta
        fila_control = con.execute(
            "SELECT model, serie, calibr_fact FROM equipos_medicion WHERE ref = 1").fetchone()
        con.close()
        assert fila_catalogo is None
        assert fila_control == ("TN31010", "1822", 0.3)
