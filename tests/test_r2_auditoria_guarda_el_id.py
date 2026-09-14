"""R.2 (PLAN_PUNTEROS_A_EQUIPOS_11-09.md §3): `eliminarEquipo` audita los
12 campos de la fila borrada (Q.1/DA-74) pero NO el `id` -- `ref` es
`modelo/serie`. Sin el id, `audit_log` no sirve como evidencia del techo de
ids que R.1 reconstruye al arranque (§0.9 del plan): si algún día se
pierden a la vez el contador de `sqlite_sequence` Y los punteros vivos en
`equipos_medicion`/`calculadora_dosimetrica`, no habría forma de saber qué
ids se entregaron. Es una línea de texto y convierte la auditoría en
evidencia independiente.

Esta tarea nació más grande -- también elevaba el contador en el propio
borrado -- y la prueba de estrés de §0.11 del plan (15 semillas x 4
rondas de borrados aleatorios) demostró que esa parte es redundante: R.1
no puede fallar por construcción (su techo es
`max(..., MAX(columna puntero))`, que por definición ya es >= cualquier id
apuntado) y pasa 15/15 incluso con un rebuild que borra el contador a
mitad. Se retiró esa mitad; queda solo lo que ningún otro sitio cubre.
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
    """Trampa 2: warning/information/critical se mockean siempre; sin esto
    un QMessageBox real cuelga la suite bajo offscreen."""
    for tipo in ("warning", "information", "critical"):
        monkeypatch.setattr(equipos_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test_r2.db")
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
        def __init__(self, user):
            self.user = user

        def exec(self):
            return QDialog.DialogCode.Accepted if aceptado else QDialog.DialogCode.Rejected

    monkeypatch.setattr(equipos_mod, "DialogAdminPermisoEliminar", _DialogoFalso)


def _mock_confirmacion(monkeypatch, respuesta):
    monkeypatch.setattr(
        equipos_mod.QMessageBox, "question",
        staticmethod(lambda self_widget, titulo, texto, *a, **k: respuesta))


def _audit_log(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


class TestElIdQuedaEscritoEnLaAuditoria:
    """Rojo-antes-que-verde: contra el código de hoy, `detalle` lleva los
    12 campos pero ningún `id=`."""

    def test_el_detalle_incluye_id_igual_al_borrado(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal)
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        _, _, _, _, detalle = filas[0]
        assert f"id={id_equipo}" in detalle, (
            f"el id del equipo borrado ({id_equipo}) no aparece en el "
            f"detalle de auditoría: {detalle!r}")

    def test_los_12_campos_siguen_completos_y_ref_sigue_siendo_modelo_serie(
            self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(
            bd_temporal, calibr_fact=464700, fecha_calibr="28/07/2025")
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        filas = _audit_log(bd_temporal)
        _, _, tabla, ref, detalle = filas[0]
        assert tabla == "equipos"
        assert ref == "HDR1000 Plus/A092535"  # NO se toca: es lo que el físico lee
        for campo in ("equip_type=", "model=", "serie=", "calibr_fact=",
                      "calibr_fact2=", "fecha_calibr=", "fabricante=",
                      "t_cal=", "p_cal=", "h_cal=", "v1=", "activo="):
            assert campo in detalle, f"falta {campo!r} en {detalle!r}"
        assert "464700" in detalle
        assert "28/07/2025" in detalle

    def test_reconstruible_desde_solo_audit_log(self, app, bd_temporal, monkeypatch):
        """El id y los 12 campos alcanzan para reconstruir la fila borrada
        sin ningún otro rastro -- la garantía que motiva la tarea."""
        id_equipo = _preparar_equipo(
            bd_temporal, equip_type="Electrómetro", model="CDX-2000B",
            serie="B091982", calibr_fact=1, fecha_calibr="17/03/2026")
        _mock_dialogo_admin(monkeypatch, aceptado=True)
        _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        obj = _widget_con_fila_seleccionada(id_equipo)

        Config.eliminarEquipo(obj)

        _, _, _, _, detalle = _audit_log(bd_temporal)[0]
        pares = dict(
            campo.split("=", 1)
            for campo in detalle.split(" | ")[0].split("; ")
            if "=" in campo)
        assert int(pares["id"]) == id_equipo
        assert pares["model"] == "CDX-2000B"
        assert pares["serie"] == "B091982"
        assert pares["fecha_calibr"] == "17/03/2026"
