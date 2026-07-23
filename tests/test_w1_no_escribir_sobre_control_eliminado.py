"""W1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): reproduce el incidente
real del handoff 23-07 -- el físico anuló/eliminó un control desde la vista
de registros mientras el formulario mensual seguía abierto sobre ese mismo
`ref`, y "Subir" seguía escribiendo `dosimetriaMen` huérfana porque
`subirlineasmensuales`/`_ix` solo miraban la franja de 2 meses (F4b), nunca
si el control seguía existiendo. Evidencia real: el `audit_log` de la BD que
trajo el físico muestra 6 guardados de `dosimetriaMen ref=42` DESPUÉS de
`eliminar controles id=42` (12:42:56 -> 12:46-12:50).

Con C2 (soft-delete) + la extensión de `puede_editarse`/`mensaje_bloqueo_
edicion` (services/ventana_edicion.py) a "existe y está activo", el MISMO
gate que ya usaban ambas rutas (`_puede_editarse_control(ref)`) ahora
también bloquea estos dos casos -- sin tocar `subirlineasmensuales`/`_ix`
en sí, solo lo que ya consultaban.
"""
import os
import sqlite3
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import subirlineasmensuales
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager)
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    DatabaseManager._connections.clear()
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None
    DatabaseManager._connections.clear()


def _crear_control(ruta_bd, control_id, activo=1):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id, activo) "
        "VALUES (?, 'Clinac ix', 'Mensual', '01/2026', 'Físico de Prueba', ?)",
        (control_id, activo))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


def _pelado_600():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    return obj


def _pelado_ix():
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    return obj


def _capturar_avisos(monkeypatch):
    avisos = []
    monkeypatch.setattr(load_mod.QMessageBox, "warning",
                         staticmethod(lambda *a, **k: avisos.append(a[1:])))
    monkeypatch.setattr(load_mod.QMessageBox, "information",
                         staticmethod(lambda *a, **k: None))
    return avisos


class TestSubirBloqueadoSiElControlYaNoExiste:
    """El caso EXACTO del incidente: se anula/borra el control desde otra
    vista y el formulario mensual, que sigue abierto con el ref viejo,
    intenta 'Subir' de todas formas."""

    def test_600_no_escribe_dosimetria_huerfana(self, app, bd_temporal, monkeypatch):
        avisos = _capturar_avisos(monkeypatch)
        # El control NUNCA se crea (o ya fue eliminado por completo) --
        # ref=999 no existe en absoluto en "controles".
        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        from PyQt5.QtWidgets import QLineEdit
        obj.ln_observaciones_dosi = QLineEdit("dato que no debería guardarse")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=999, usarid=False)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=999").fetchone()[0]
        con.close()
        assert n == 0, "no debe escribirse ninguna fila huérfana"
        assert len(avisos) == 1
        assert "Control cerrado" in avisos[0][0]

    def test_ix_no_escribe_dosimetria_huerfana_tras_eliminar_el_control(
            self, app, bd_temporal, monkeypatch):
        """Reproduce la secuencia real del audit_log: crear controles(42),
        eliminarlo (soft-delete via eliminarRegistro), y SOLO DESPUÉS
        intentar 'Subir' con el ref que el formulario aún conserva."""
        avisos = _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 42)

        # eliminarRegistro real -- el mismo camino de la vista de registros.
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem

        class _UsuarioFalso:
            _nombre = "Administrador"

        class _DlgFalso:
            user_id = _UsuarioFalso()

        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
        monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))

        tabla = QTableWidget(1, 1)
        item = QTableWidgetItem("fila")
        item.setData(Qt.UserRole, 42)
        tabla.setItem(0, 0, item)
        tabla.setCurrentCell(0, 0)
        load_mod.eliminarRegistro(_DlgFalso(), tabla, "controles")

        # el control quedó anulado (activo=0) -- sigue existiendo (C2)
        con = sqlite3.connect(bd_temporal)
        activo = con.execute("SELECT activo FROM controles WHERE id=42").fetchone()[0]
        con.close()
        assert activo == 0

        # el formulario mensual, que seguía abierto con self.ref=42, intenta Subir
        obj = _pelado_ix()
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=42, usarid=True, df_lines=[])

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=42").fetchone()[0]
        con.close()
        assert n == 0, (
            "el incidente real (handoff 23-07): 6 filas huérfanas se "
            "escribieron así -- ahora debe quedar bloqueado")

    def test_600_bloquea_si_el_control_fue_anulado(self, app, bd_temporal, monkeypatch):
        avisos = _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 43, activo=0)  # ya anulado

        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        from PyQt5.QtWidgets import QLineEdit
        obj.ln_observaciones_dosi = QLineEdit("no debería guardarse")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=43, usarid=False)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=43").fetchone()[0]
        con.close()
        assert n == 0
        assert "anulado" in avisos[0][1]

    def test_control_activo_dentro_de_la_ventana_sigue_permitiendo_subir(
            self, app, bd_temporal, monkeypatch):
        """Contraste: el gate no debe volverse un no-op general -- un
        control real, activo y dentro de la ventana, sigue aceptando Subir."""
        _capturar_avisos(monkeypatch)
        _crear_control(bd_temporal, 44, activo=1)

        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        from PyQt5.QtWidgets import QLineEdit
        obj.ln_observaciones_dosi = QLineEdit("dato legítimo")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=44, usarid=False)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=44").fetchone()[0]
        con.close()
        assert n == 1
