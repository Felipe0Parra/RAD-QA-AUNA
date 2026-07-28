"""E5 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §6): el botón "Eliminar" de
Dosimetría estaba MUERTO -- se creaba y se añadía al layout, pero nunca se
conectaba. No era una decisión de diseño: un botón visible que no hacía
nada.

Se conecta DESPUÉS de E7 a propósito (dependencia de orden explícita en el
plan, D5): "dosimetriaMen" ya está en `services.anulacion.TABLAS_ANULABLES`,
así que `verificar_eliminar` (vía `eliminarRegistro`) anula en vez de
borrar. Conectarlo antes de E7 habría creado un DELETE físico sobre el
bloque de dosimetría, justo lo que D5 prohibió.
"""
import sqlite3

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import mostrar_dosimetria


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + todas las migraciones reales (incl. E7)
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "ffisico"


def _preparar_control_con_dosimetria(ruta):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) "
        "VALUES ('Clinac iX', 'Mensual', '07/2026')")
    ref = cur.lastrowid
    con.execute(
        "INSERT INTO dosimetriaMen (ref, energia, dosis_ref_cgy_um) "
        "VALUES (?, '6mv', 1.01)", (ref,))
    con.commit()
    con.close()
    return ref


def _mostrar_dosimetria_capturando_dialogo(monkeypatch, parent, ref):
    """`mostrar_dosimetria` termina en `dlg.exec_()` (modal, bloquearía el
    test) -- se parchea `QDialog.exec_` para capturar la instancia sin
    bloquear, mismo problema que cualquier función de este archivo que
    construye un diálogo y lo muestra al final."""
    capturados = []
    monkeypatch.setattr(QDialog, "exec_", lambda self: capturados.append(self))
    mostrar_dosimetria(parent, ref)
    return capturados[-1]


class TestBotonConectado:
    def test_btn_delete_tiene_al_menos_un_receptor(self, app, bd_temporal, monkeypatch):
        ref = _preparar_control_con_dosimetria(bd_temporal)
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()

        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)

        assert dlg.btn_delete.receivers(dlg.btn_delete.clicked) > 0


class TestLaAccionAnulaNoBorra:
    def test_click_en_eliminar_anula_la_fila_no_la_borra(self, app, bd_temporal, monkeypatch):
        ref = _preparar_control_con_dosimetria(bd_temporal)
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()

        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)

        # Selecciona la única fila de la tabla renderizada (energía 6mv) --
        # la clave compuesta (id_ref, energia) va en Qt.UserRole (ver
        # mostrar_dosimetria); eliminarRegistro busca la PRIMERA columna con
        # metadata en Qt.UserRole, que aquí es la fila "Dosis Ref".
        tabla = dlg.findChildren(__import__("PyQt5.QtWidgets", fromlist=["QTableWidget"]).QTableWidget)[0]
        tabla.setCurrentCell(1, 1)  # fila "Dosis Ref (cGy/UM)", columna Valor

        class _DialogoAdminFalso:
            def __init__(self, user):
                self.user = user
            def exec(self):
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(load_mod, "DialogAdminPermisoEliminar", _DialogoAdminFalso)
        monkeypatch.setattr(load_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "critical",
                            staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.Yes))
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                            staticmethod(lambda *a, **k: None))

        dlg.btn_delete.clicked.emit()

        con = sqlite3.connect(bd_temporal)
        try:
            fila = con.execute(
                "SELECT activo FROM dosimetriaMen WHERE ref = ?", (ref,)).fetchall()
            audit = con.execute(
                "SELECT usuario, accion, tabla FROM audit_log "
                "WHERE tabla='dosimetriaMen'").fetchall()
        finally:
            con.close()

        assert len(fila) == 1, "la fila NUNCA debe desaparecer (anular, no borrar)"
        assert fila[0][0] == 0
        assert audit == [("Físico de Prueba", "anular", "dosimetriaMen")]

    def test_ref_auditada_es_legible_no_la_tupla_cruda(self, app, bd_temporal, monkeypatch):
        ref = _preparar_control_con_dosimetria(bd_temporal)
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)
        tabla = dlg.findChildren(__import__("PyQt5.QtWidgets", fromlist=["QTableWidget"]).QTableWidget)[0]
        tabla.setCurrentCell(1, 1)

        class _DialogoAdminFalso:
            def __init__(self, user):
                self.user = user
            def exec(self):
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(load_mod, "DialogAdminPermisoEliminar", _DialogoAdminFalso)
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.Yes))
        monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

        dlg.btn_delete.clicked.emit()

        con = sqlite3.connect(bd_temporal)
        try:
            fila_ref = con.execute(
                "SELECT ref FROM audit_log WHERE tabla='dosimetriaMen'").fetchone()[0]
        finally:
            con.close()
        assert fila_ref == f"{ref}/6mv"
