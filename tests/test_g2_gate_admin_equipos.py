"""G2 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-G2, DA-01): modificar el
catálogo de equipos exige administrador -- se corrige el ÚNICO botón de
edición de la app sin ninguna barrera.

Evidencia del rebuild 30-07: `habilitar2` (el botón "Editar") habilitaba el
formulario y cargaba los datos sin preguntar nada; `guardarCambios` solo
gateaba la dirección `activo 0->1` (F7) -- la dirección `1->0` (justo lo que
E2 protegió en el botón "Eliminar") quedaba abierta. Secuencia real capturada
en audit_log: "activo: 0->1" con autorizacion OK, seguida 20s después de
"activo: 1->0" SIN ninguna autorizacion en medio.

El gate se movió a la ENTRADA (`habilitar2`), antes de habilitar cualquier
widget: `DialogAdminPermisoEliminar` ya valida login + es_admin_equivalente()
y audita el intento denegado por sí sola (C3) -- mismo patrón que
`eliminarEquipo`. Mecanismo real de protección verificado en el código: el
botón "Guardar" (`self.tios`) solo se conecta a `guardarCambios` DENTRO de
`habilitar2`, después del gate -- si el diálogo se deniega, la función
retorna antes de esa conexión, así que el botón queda sin conectar para esa
sesión (no hace falta ningún flag adicional de "modo edición").
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDialog, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
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


def _preparar_equipo(ruta, activo=1):
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


def _instancia_para_habilitar2(id_equipo=None):
    """`Config` "pelada" -- solo lo que `habilitar2` toca, sin pasar por
    `__init__` (BD real, widgets.xlsx). `editarEquipo`/
    `actualizar_unidades_calibracion` se espían como atributos de instancia
    en vez de invocar la lógica real de carga -- no es lo que este test
    verifica."""
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

    llamadas = {"editar_equipo": 0, "guardado": 0}
    obj.actualizar_unidades_calibracion = lambda texto: None
    obj.editarEquipo = lambda: llamadas.__setitem__("editar_equipo", llamadas["editar_equipo"] + 1)
    obj.guardarCambios = lambda: llamadas.__setitem__("guardado", llamadas["guardado"] + 1)

    if id_equipo is not None:
        obj.table = QTableWidget(1, 1)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, id_equipo)
        obj.table.setItem(0, 0, item)
        obj.table.setCurrentCell(0, 0)

    return obj, llamadas


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


class TestDialogoDenegadoNoHabilitaNiCarga:
    """1. Diálogo denegado en `habilitar2` -> los widgets del formulario
    siguen deshabilitados y no se cargaron los datos del equipo. Rojo antes
    del fix (hoy nunca se pregunta nada)."""

    def test_no_llama_editarEquipo(self, app, monkeypatch):
        _mock_dialogo(monkeypatch, aceptado=False)
        obj, llamadas = _instancia_para_habilitar2()

        Config.habilitar2(obj)

        assert llamadas["editar_equipo"] == 0

    def test_dialogo_si_se_instancio(self, app, monkeypatch):
        dialogo_falso = _mock_dialogo(monkeypatch, aceptado=False)
        obj, _llamadas = _instancia_para_habilitar2()

        Config.habilitar2(obj)

        assert len(dialogo_falso.instancias) == 1


class TestDialogoAceptadoHabilitaYCarga:
    """2. Diálogo aceptado -> el formulario se habilita y carga, como
    siempre (anti-regresión: G2 no debe romper el camino feliz)."""

    def test_llama_editarEquipo(self, app, monkeypatch):
        _mock_dialogo(monkeypatch, aceptado=True)
        obj, llamadas = _instancia_para_habilitar2()

        Config.habilitar2(obj)

        assert llamadas["editar_equipo"] == 1


class TestIncidenteDelFisicoYaNoOcurre:
    """3. La prueba que reproduce el incidente real: con el diálogo
    denegado, el botón "Guardar" (`self.tios`) nunca queda conectado a
    `guardarCambios` para esa sesión -- ni pulsándolo físicamente cambia
    nada en la BD. Hoy (antes del fix) el flujo completo "editar ->
    desmarcar Activo -> guardar" deja `activo` en 0 sin preguntar nada."""

    def test_boton_guardar_no_hace_nada_tras_denegar(self, app, bd_temporal, monkeypatch):
        id_equipo = _preparar_equipo(bd_temporal, activo=1)
        _mock_dialogo(monkeypatch, aceptado=False)
        obj, llamadas = _instancia_para_habilitar2(id_equipo)

        Config.habilitar2(obj)
        obj.tios.clicked.emit()

        assert llamadas["guardado"] == 0
        assert _activo_actual(bd_temporal, id_equipo) == 1


class TestActivoQuedaAuditadoConNombreDelFisico:
    """4. `activo: 1->0` y `activo: 0->1` siguen apareciendo en audit_log
    con el nombre del físico (no del administrador que autorizó -- decisión
    ya tomada el 28-07). Verificado contra guardarCambios real (la
    autorización ya ocurrió en habilitar2, previo a llegar aquí)."""

    def test_detalle_activo_lleva_el_nombre_del_fisico(self, app, bd_temporal, monkeypatch):
        from PyQt5.QtWidgets import QCheckBox, QLineEdit

        id_equipo = _preparar_equipo(bd_temporal, activo=1)
        monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(equipos_mod.QMessageBox, "warning",
                            staticmethod(lambda *a, **k: None))

        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioActualFalso()
        obj.cargartabla = lambda: None
        obj.tipo = QComboBox()
        obj.tipo.addItem("Cámara de ionización")
        obj.modelo = QLineEdit("N30013")
        obj.serie = QLineEdit("2123")
        obj.calib_factor = QLineEdit("0.0545")
        obj.calib_date = QLineEdit("05/02/2024")
        obj.fabricante = QLineEdit("")
        obj.t_cal = QLineEdit("22.0")
        obj.p_cal = QLineEdit("101.325")
        obj.h_cal = QLineEdit("50.0")
        obj.v1_cal = QLineEdit("")
        obj.sel_activo = QCheckBox()
        obj.sel_activo.setChecked(False)  # desmarca -- 1->0
        obj.table = QTableWidget(1, 1)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, id_equipo)
        obj.table.setItem(0, 0, item)
        obj.table.setCurrentCell(0, 0)

        Config.guardarCambios(obj)

        filas = _audit_log(bd_temporal)
        assert len(filas) == 1
        usuario, accion, tabla, ref, detalle = filas[0]
        assert usuario == "Físico de Prueba"
        assert "activo: 1→0" in detalle
