"""F7 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.2/§9): reactivar un equipo
(`activo` 0→1) exige autorización de administrador -- mismo gate que E2 puso
en la anulación (`DialogAdminPermisoEliminar`, admin o física jefe).

Reactivar es un flujo LEGÍTIMO y previsto (§8.3: llenar controles de años
anteriores con los parámetros que el equipo tenía entonces), no una
operación sospechosa -- el gate es una decisión explícita del físico.

ACTUALIZADO por G2 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-G2, DA-01,
2026-07-31): el gate CONDICIONAL que F7 puso dentro de `guardarCambios`
(solo si `activo` pasaba de 0 a 1) se retiró -- G2 exige administrador para
CUALQUIER edición del catálogo, desde la ENTRADA (`habilitar2`), no solo
para reactivar. La garantía de F7 ("reactivar no ocurre sin autorización")
sigue siendo cierta -- ahora la cubre el gate más amplio de G2, verificado
en `test_g2_gate_admin_equipos.py`. `TestReactivarSinAutorizacionNoCambiaActivo`
se reubicó para probarlo a través de `habilitar2` (el mecanismo real ahora);
`TestCambioQueNoTocaActivoNoPideAdministrador` se retiró porque su premisa
("editar un campo distinto de `activo` no pide administrador") es exactamente
lo que G2 invirtió -- ver `TestActivoQuedaAuditadoConNombreDelFisico` en
test_g2_gate_admin_equipos.py para la cobertura vigente. `TestReactivarConAutorizacion`
y `TestIntentoDenegadoQuedaAuditado` no dependían del gate condicional de F7
(prueban la propia actualización/auditoría de `guardarCambios` y el
comportamiento propio de `DialogAdminPermisoEliminar`) -- se conservan tal
cual, ya autorizados antes de llegar aquí.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QLineEdit, QTableWidget,
    QTableWidgetItem, QWidget,
)

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
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "accastellanos"


def _preparar_equipo(ruta, activo=0):
    con = sqlite3.connect(ruta)
    cur = con.execute("""
        INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2,
            fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1, activo, vigente)
        VALUES ('Cámara de ionización', 'N30013', '2123', 0.0545, NULL,
            '05/02/2024', NULL, 22.0, 101.325, 50.0, NULL, ?, 0)
    """, (activo,))
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


def _instancia_con_formulario(id_equipo, activo_marcado, mismos_datos=True):
    """Config sin su __init__ pesado -- solo los widgets que guardarCambios
    necesita, con los MISMOS valores que _preparar_equipo (para que
    hay_cambios salga False salvo por `activo`, igual que reactivar un
    equipo sin tocar ningún otro campo)."""
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioActualFalso()
    obj.cargartabla = lambda: None

    obj.tipo = QComboBox()
    obj.tipo.addItem("Cámara de ionización")
    obj.modelo = QLineEdit("N30013" if mismos_datos else "N30013-editado")
    obj.serie = QLineEdit("2123")
    obj.calib_factor = QLineEdit("0.0545")
    obj.calib_date = QLineEdit("05/02/2024")
    obj.fabricante = QLineEdit("")
    obj.t_cal = QLineEdit("22.0")
    obj.p_cal = QLineEdit("101.325")
    obj.h_cal = QLineEdit("50.0")
    obj.v1_cal = QLineEdit("")
    obj.sel_activo = QCheckBox()
    obj.sel_activo.setChecked(activo_marcado)

    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem()
    item.setData(Qt.UserRole, id_equipo)
    obj.table.setItem(0, 0, item)
    obj.table.setCurrentCell(0, 0)
    return obj


def _mock_dialogo(monkeypatch, aceptado):
    class _DialogoFalso:
        instancias = []

        def __init__(self, user):
            self.user = user
            _DialogoFalso.instancias.append(self)

        def exec(self):
            return QDialog.DialogCode.Accepted if aceptado else QDialog.DialogCode.Rejected

    monkeypatch.setattr(equipos_mod, "DialogAdminPermisoEliminar", _DialogoFalso)
    return _DialogoFalso


def _mock_messagebox(monkeypatch):
    """guardarCambios termina con QMessageBox.information("Éxito", ...) en
    el camino feliz -- sin mockear, .exec_() cuelga la suite offscreen
    esperando un clic que nunca llega (lección ya aprendida en Fase G/
    D4.2-Halcyon/W1: todo diálogo modal nuevo necesita su propio punto de
    inyección mockeable)."""
    monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(equipos_mod.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))


def _audit_log(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


def _activo_actual(ruta, id_equipo):
    con = sqlite3.connect(ruta)
    valor = con.execute(
        "SELECT activo FROM equipos WHERE id = ?", (id_equipo,)).fetchone()[0]
    con.close()
    return valor


class TestReactivarSinAutorizacionNoCambiaActivo:
    """Reubicada por G2: el gate ya no vive en `guardarCambios` (se llamaba
    directo, bypaseando `habilitar2`) -- ahora vive en `habilitar2`, así que
    la prueba pasa por ahí. Con el diálogo denegado, `habilitar2` retorna
    antes de conectar el botón "Guardar" a `guardarCambios` -- ni pulsándolo
    cambia nada. Cobertura completa (incluida esta) en
    test_g2_gate_admin_equipos.py."""

    def test_denegado_no_modifica_activo(self, app, bd_temporal, monkeypatch):
        from PyQt5.QtWidgets import QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

        id_equipo = _preparar_equipo(bd_temporal, activo=0)
        _mock_dialogo(monkeypatch, aceptado=False)

        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioActualFalso()
        obj.canson1 = QWidget()
        obj.canson1.setLayout(QVBoxLayout())
        obj.tios = QPushButton()
        obj.tios2 = QPushButton()
        obj.info_unidades = QWidget()
        obj.tipo = QComboBox()
        obj.tipo.addItem("Cámara de ionización")
        obj.actualizar_unidades_calibracion = lambda texto: None
        obj.editarEquipo = lambda: None
        obj.table = QTableWidget(1, 1)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, id_equipo)
        obj.table.setItem(0, 0, item)
        obj.table.setCurrentCell(0, 0)

        # `guardarCambios` como espía en vez de la real: lo que esta prueba
        # verifica es si el botón queda CONECTADO o no -- dejar correr la
        # función real sobre un objeto "pelado" (sin modelo/serie/etc.)
        # revienta con AttributeError sin try/except que lo atrape (a
        # diferencia de guardarEdicion en load.py), y eso aborta el
        # intérprete al propagarse a través del signal de Qt -- no es lo
        # que se está probando aquí.
        llamado = []
        obj.guardarCambios = lambda: llamado.append(True)

        Config.habilitar2(obj)
        obj.tios.clicked.emit()  # aunque se pulsara "Guardar", no está conectado

        assert llamado == []
        assert _activo_actual(bd_temporal, id_equipo) == 0


class TestReactivarConAutorizacion:
    def test_activo_pasa_a_1(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal, activo=0)
        _mock_dialogo(monkeypatch, aceptado=True)
        _mock_messagebox(monkeypatch)
        obj = _instancia_con_formulario(id_equipo, activo_marcado=True)

        Config.guardarCambios(obj)

        assert _activo_actual(bd_temporal, id_equipo) == 1

    def test_detalle_contiene_activo_0_flecha_1(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal, activo=0)
        _mock_dialogo(monkeypatch, aceptado=True)
        _mock_messagebox(monkeypatch)
        obj = _instancia_con_formulario(id_equipo, activo_marcado=True)

        Config.guardarCambios(obj)

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert accion == "actualizar"
        assert tabla == "equipos"
        assert "activo: 0→1" in detalle


class TestIntentoDenegadoQuedaAuditado:
    def test_intento_denegado_queda_auditado(self, app, bd_temporal, monkeypatch):
        """DialogAdminPermisoEliminar ya audita el intento denegado por sí
        mismo (C3) -- aquí se verifica con el gate real (sin mockear la
        clase completa), reproduciendo contraseña correcta pero sin
        permisos administrativos."""
        id_equipo = _preparar_equipo(bd_temporal, activo=0)

        def _login_sin_permiso(self, user, accion=None):
            from data.ManejoDatos.user import Usuario
            if user._usuario == "accastellanos":
                return Usuario(username="accastellanos", password="x")
            return None

        import ui.paginasGuia.dialogs as dialogs_mod
        monkeypatch.setattr(dialogs_mod.UsuarioData, "login", _login_sin_permiso)
        monkeypatch.setattr(
            dialogs_mod.QMessageBox, "information",
            staticmethod(lambda *a, **k: None))

        obj = _instancia_con_formulario(id_equipo, activo_marcado=True)

        dialogo = equipos_mod.DialogAdminPermisoEliminar(obj.user_id)
        dialogo.admin_user.setText("accastellanos")
        dialogo.admin_password.setText("cualquierclave")
        dialogo.open_main_window()

        assert dialogo.result() != QDialog.DialogCode.Accepted

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla, ref, detalle = filas[0]
        assert usuario == "accastellanos"
        assert accion == "autorizacion"
        assert "denegado" in detalle
