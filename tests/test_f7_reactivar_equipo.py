"""F7 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.2/§9): reactivar un equipo
(`activo` 0→1) exige autorización de administrador -- mismo gate que E2 puso
en la anulación (`DialogAdminPermisoEliminar`, admin o física jefe).

Reactivar es un flujo LEGÍTIMO y previsto (§8.3: llenar controles de años
anteriores con los parámetros que el equipo tenía entonces), no una
operación sospechosa -- el gate es una decisión explícita del físico. Los
demás cambios de la edición (no tocan `activo`) siguen sin pedir
administrador (D1 del Plan E).
"""
import sqlite3

import pytest
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
    def test_denegado_no_modifica_activo(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal, activo=0)
        _mock_dialogo(monkeypatch, aceptado=False)
        obj = _instancia_con_formulario(id_equipo, activo_marcado=True)

        Config.guardarCambios(obj)

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


class TestCambioQueNoTocaActivoNoPideAdministrador:
    """No romper D1: editar un campo distinto de `activo` sigue sin pedir
    administrador -- el diálogo ni se instancia."""

    def test_no_se_pide_administrador(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal, activo=1)  # ya activo
        dialogo_falso = _mock_dialogo(monkeypatch, aceptado=False)
        _mock_messagebox(monkeypatch)
        obj = _instancia_con_formulario(id_equipo, activo_marcado=True,
                                        mismos_datos=False)  # cambia el modelo

        Config.guardarCambios(obj)

        assert dialogo_falso.instancias == []  # nunca se instanció
        # el cambio de modelo sí se guardó (INSERT de nueva fila, no bloqueado)
        con = sqlite3.connect(bd_temporal)
        modelos = [r[0] for r in con.execute("SELECT model FROM equipos").fetchall()]
        con.close()
        assert "N30013-editado" in modelos


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
