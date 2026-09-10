"""Q.1 (PLAN_EQUIPOS_BORRADO_Y_VIGENCIA_10-09.md SS2): "Eliminar" en el
catalogo de equipos borra la fila de verdad (DELETE), no la anula
(activo=0) -- revierte DA-02 (16-07), soft-delete original. La reversion
es legitima porque la premisa de DA-02 (que un control historico
NECESITABA la fila del catalogo) resulto FALSA al medirla en SS0.1 del
plan: los controles guardan una COPIA del equipo (equipos_medicion,
SistemaMedicion, calculadora_dosimetrica), nunca una referencia -- 0 FK
declaradas hacia `equipos` en las 72 tablas.

Pedido del fisico, verbatim (10-09): "quiero que la opcion eliminar
realmente desaparezca esa fila de la BD" y, en la segunda ronda:
"asegurarse de que el aviso permita retroceder, y no que si le doy
cancelar igual ejecute la accion".

Tres condiciones, ninguna decorativa (SS2 del plan):
  1. la puerta de admin se conserva (DialogAdminPermisoEliminar)
  2. aviso previo que cuenta las referencias y dice que se pierde --
     avisa, NO bloquea (DA-22: la decision es del fisico)
  3. la auditoria pasa a llevar la fila ENTERA (12 campos), porque sin
     la fila el rastro es lo unico que queda
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
    """Trampa 2 (CLAUDE.md): un QMessageBox real sin mockear cuelga la
    suite bajo offscreen esperando un clic que nunca llega -- confirmado
    en carne propia contra el código VIEJO (que llega a `.information()`
    sin pasar por `.question()`, dejando el mock de confirmación sin
    efecto). warning/information/critical se mockean SIEMPRE, sin
    excepción; `.question()` lo controla cada test via
    `_mock_confirmacion`."""
    for tipo in ("warning", "information", "critical"):
        monkeypatch.setattr(equipos_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test_q1.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "accastellanos"


def _preparar_equipo(ruta, equip_type="Cámara de pozo", model="HDR1000 Plus",
                     serie="A092535", calibr_fact=464700, fecha_calibr="28/07/2025"):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO equipos (equip_type, model, serie, calibr_fact, fecha_calibr, activo)"
        " VALUES (?, ?, ?, ?, ?, 1)",
        (equip_type, model, serie, calibr_fact, fecha_calibr))
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


def _widget_con_fila_seleccionada(id_equipo):
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioActualFalso()
    obj.cargartabla = lambda: None
    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem()
    item.setData(Qt.UserRole, id_equipo)
    obj.table.setItem(0, 0, item)
    obj.table.setCurrentCell(0, 0)
    return obj


def _mock_dialogo_admin(monkeypatch, aceptado):
    class _DialogoFalso:
        instancias = []

        def __init__(self, user):
            self.user = user
            _DialogoFalso.instancias.append(self)

        def exec(self):
            return QDialog.DialogCode.Accepted if aceptado else QDialog.DialogCode.Rejected

    monkeypatch.setattr(equipos_mod, "DialogAdminPermisoEliminar", _DialogoFalso)
    return _DialogoFalso


def _mock_confirmacion(monkeypatch, respuesta):
    """Espia QMessageBox.question -- captura el texto mostrado y devuelve
    `respuesta` (puede ser Yes, No, Cancel, NoButton -- simula tambien
    cerrar el dialogo con la X o con Escape, que Qt reporta como esos
    valores, nunca como No)."""
    llamadas = []

    def _question(self_widget, titulo, texto, *args, **kwargs):
        llamadas.append(texto)
        return respuesta

    monkeypatch.setattr(equipos_mod.QMessageBox, "question", staticmethod(_question))
    return llamadas


def _audit_log(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


def _equipo_existe(ruta, id_equipo):
    con = sqlite3.connect(ruta)
    fila = con.execute("SELECT COUNT(*) FROM equipos WHERE id = ?", (id_equipo,)).fetchone()
    con.close()
    return fila[0]


class TestSinAutorizacionNoBorra:
    def test_dialogo_admin_rechazado_la_fila_sigue_y_activa(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo_admin(monkeypatch, aceptado=False)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        con = sqlite3.connect(bd_temporal)
        activo = con.execute("SELECT activo FROM equipos WHERE id = ?", (id_equipo,)).fetchone()[0]
        con.close()
        assert activo == 1
        assert _audit_log(bd_temporal) == []


class TestBorradoRealConAutorizacionYConfirmacion:
    def test_autorizado_y_confirmado_la_fila_desaparece(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert _equipo_existe(bd_temporal, id_equipo) == 0, (
            "la fila debe desaparecer por completo -- 0, no 1 con activo=0")

    def test_audita_con_los_12_campos_reconstruibles(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal, calibr_fact=464700, fecha_calibr="28/07/2025")
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla, ref, detalle = filas[0]
        assert accion == "eliminar"
        assert tabla == "equipos"
        assert ref == "HDR1000 Plus/A092535"
        # reconstruible: el detalle trae el factor y la fecha, no solo el nombre
        assert "464700" in detalle
        assert "28/07/2025" in detalle


class TestElAvisoPermiteRetroceder:
    """Exigencia explicita del fisico: cancelar (de cualquier forma) NO
    debe ejecutar el borrado."""

    def test_confirmacion_no_la_fila_sigue_sin_auditoria(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, QMessageBox.No)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert _equipo_existe(bd_temporal, id_equipo) == 1
        assert _audit_log(bd_temporal) == []

    @pytest.mark.parametrize("respuesta_de_cierre", [
        QMessageBox.Cancel, QMessageBox.NoButton, QMessageBox.Escape,
    ])
    def test_cerrar_el_dialogo_sin_responder_no_borra(
            self, app, bd_temporal, monkeypatch, respuesta_de_cierre):
        """Un == QMessageBox.No NO pasaria este test: cerrar con la X o
        Escape devuelve Cancel/NoButton/Escape, nunca No -- exactamente
        el error que el fisico pidio evitar."""
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, respuesta_de_cierre)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert _equipo_existe(bd_temporal, id_equipo) == 1, (
            f"con respuesta={respuesta_de_cierre!r} la fila NO debe desaparecer")
        assert _audit_log(bd_temporal) == []


class TestElAvisoCuentaLasReferencias:
    def test_sin_referencias_el_aviso_no_menciona_conteos(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        llamadas = _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert len(llamadas) == 1
        assert "equipos de medición" not in llamadas[0]
        assert "cálculo" not in llamadas[0]

    def test_con_equipos_medicion_referenciandolo_el_aviso_nombra_el_conteo(
            self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, model, serie,"
            " calibr_fact, equipo_id) VALUES (1, 'Principal', 'Cámara de pozo',"
            " 'HDR1000 Plus', 'A092535', 464700, ?)", (id_equipo,))
        con.commit()
        con.close()

        _mock_dialogo_admin(monkeypatch, aceptado=True)
        llamadas = _mock_confirmacion(monkeypatch, QMessageBox.No)  # no hace falta borrar
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert len(llamadas) == 1
        assert "1" in llamadas[0]


class TestLaGarantiaQueLeImportaAlFisico:
    """Un control ya guardado no pierde nada: guarda su propia copia."""

    def test_equipos_medicion_conserva_su_copia_tras_borrar_el_equipo(
            self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, model, serie,"
            " calibr_fact, fecha_calibr, equipo_id) VALUES (1, 'Principal',"
            " 'Cámara de pozo', 'HDR1000 Plus', 'A092535', 464700, '28/07/2025', ?)",
            (id_equipo,))
        con.commit()
        antes = con.execute(
            "SELECT model, serie, calibr_fact, fecha_calibr FROM equipos_medicion"
            " WHERE ref = 1").fetchone()
        con.close()

        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        assert _equipo_existe(bd_temporal, id_equipo) == 0

        con = sqlite3.connect(bd_temporal)
        despues = con.execute(
            "SELECT model, serie, calibr_fact, fecha_calibr FROM equipos_medicion"
            " WHERE ref = 1").fetchone()
        con.close()
        assert despues == antes == ("HDR1000 Plus", "A092535", 464700, "28/07/2025")
