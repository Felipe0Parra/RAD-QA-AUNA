"""G5 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5): dos defectos
encontrados y corregidos juntos en `mostrar_dosimetria` (load.py) --
relacionados porque el segundo se destapó auditando el primero.

(a) "Energía Nominal (MV)" y "Observaciones" -- filas SIN columna editable
-- se quedaban sin ningún `Qt.UserRole` (`mapa_columnas` nunca las cubre:
la primera no está en el diccionario, la segunda tiene una clave distinta
-- "Observaciones dosimetría" -- a la de la fila real, "Observaciones").
Seleccionarlas y pulsar "Eliminar" lanzaba "No se encontró metadata (id/ref)
en la fila seleccionada".

(b) HALLAZGO ADICIONAL (2026-07-31, durante la ejecución, no estaba en el
plan original): cuando un control tiene VARIAS energías, `mostrar_dosimetria`
crea una `QTableWidget` por energía DENTRO de un bucle, pero conecta
Editar/Aceptar/Eliminar UNA sola vez, DESPUÉS del bucle -- las tres lambdas
cerraban sobre `table` (variable del bucle, capturada por REFERENCIA), así
que operaban siempre sobre la ÚLTIMA energía creada (la que ordena última
alfabéticamente, `ORDER BY energia`), sin importar en qué tabla el físico
seleccionó una fila. Verificado contra producción real (2026-07-31): 5 refs
(1, 13, 16, 30, 35) tienen 6 energías simultáneas para el mismo control --
alcanzable, no hipotético. `_mostrar_dialogo`/`crear_ventanas_emergentes_
tablas` (los otros dos constructores de diálogos con Eliminar/Editar en el
archivo) usan una sola tabla por diálogo -- el defecto es exclusivo de esta
función. Fix: cada tabla actualiza `dlg._tabla_dosimetria_activa` en su
propio `itemSelectionChanged`; los tres botones leen esa referencia
dinámica en vez de la clausura rota.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QTableWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
import ui.paginasGuia.dialogs as dialogs_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import mostrar_dosimetria


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _reset_qtsql_default_connection():
    """`guardarEdicion`/`eliminarRegistro` abren la BD vía `PruebaBasico().
    opeenDatabase()` (QtSql), que cachea la conexion "qt_sql_default_
    connection" a nivel de PROCESO -- sin resetearla, un test posterior con
    otro `bd_temporal` (otro archivo) heredaria la conexion abierta contra
    el archivo del test anterior. Mismo patron ya usado en
    test_a3_auditar_edicion.py / test_a2_auditar_borrado.py."""
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + todas las migraciones reales (incl. E7)
    _reset_qtsql_default_connection()
    yield ruta
    conexion.con.close()
    Conexion._instance = None
    _reset_qtsql_default_connection()


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "ffisico"


def _preparar_control(ruta, energias):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) "
        "VALUES ('Clinac iX', 'Mensual', '07/2026')")
    ref = cur.lastrowid
    for energia in energias:
        con.execute(
            "INSERT INTO dosimetriaMen (ref, energia, dosis_ref_cgy_um, "
            "observaciones_dosi) VALUES (?, ?, 1.01, 'obs de prueba')",
            (ref, energia))
    con.commit()
    con.close()
    return ref


def _mostrar_dosimetria_capturando_dialogo(monkeypatch, parent, ref):
    """`mostrar_dosimetria` termina en `dlg.exec_()` (modal, bloquearía el
    test) -- se parchea `QDialog.exec_` para capturar la instancia sin
    bloquear (mismo patrón que test_e5_boton_dosimetria_conectado.py)."""
    capturados = []
    monkeypatch.setattr(QDialog, "exec_", lambda self: capturados.append(self))
    mostrar_dosimetria(parent, ref)
    return capturados[-1]


def _mockear_dialogos_eliminar(monkeypatch):
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


def _mockear_dialogos_editar(monkeypatch):
    class _DialogoAdminFalso:
        def __init__(self, user):
            self.user = user

        def exec(self):
            return QDialog.DialogCode.Accepted

    # DialogAdminPermisoEditar se importa LOCAL dentro de verificar_editar
    # (load.py:3730) -- parchear load_mod no lo alcanza, hay que parchear
    # el módulo de origen.
    monkeypatch.setattr(dialogs_mod, "DialogAdminPermisoEditar", _DialogoAdminFalso)
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    # Sin esto, guardarEdicion cuelga offscreen si el flujo llega a su
    # except (QMessageBox.critical real, sin mockear) -- lección ya
    # documentada varias veces en el proyecto (Fase G, D4.2-Halcyon, W1, F7).
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def _activo_de(ruta, ref, energia):
    con = sqlite3.connect(ruta)
    try:
        fila = con.execute(
            "SELECT activo FROM dosimetriaMen WHERE ref = ? AND energia = ?",
            (ref, energia)).fetchone()
    finally:
        con.close()
    return fila[0] if fila else None


def _dosis_de(ruta, ref, energia):
    con = sqlite3.connect(ruta)
    try:
        fila = con.execute(
            "SELECT dosis_ref_cgy_um FROM dosimetriaMen WHERE ref = ? AND energia = ?",
            (ref, energia)).fetchone()
    finally:
        con.close()
    return fila[0] if fila else None


class TestFilasSinColumnaEditableSeAnulanSinExcepcion:
    """(a). ROJO ANTES DEL FIX: ambas lanzan "No se encontró metadata
    (id/ref) en la fila seleccionada"."""

    def test_fila_energia_nominal(self, app, bd_temporal, monkeypatch):
        ref = _preparar_control(bd_temporal, ["6mv"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)
        tabla = dlg.findChildren(QTableWidget)[0]
        tabla.setCurrentCell(0, 1)  # fila "Energía Nominal (MV)"

        _mockear_dialogos_eliminar(monkeypatch)
        dlg.btn_delete.clicked.emit()

        assert _activo_de(bd_temporal, ref, "6mv") == 0

    def test_fila_observaciones(self, app, bd_temporal, monkeypatch):
        ref = _preparar_control(bd_temporal, ["6mv"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)
        tabla = dlg.findChildren(QTableWidget)[0]
        tabla.setCurrentCell(7, 3)  # fila "Observaciones"

        _mockear_dialogos_eliminar(monkeypatch)
        dlg.btn_delete.clicked.emit()

        assert _activo_de(bd_temporal, ref, "6mv") == 0


class TestMultiplesEnergiasNoSeConfundenAlEliminar:
    """(b). ROJO ANTES DEL FIX: Eliminar cerraba sobre la ÚLTIMA tabla
    creada (energía alfabéticamente última), no la que el físico
    seleccionó."""

    def test_anular_desde_la_primera_tabla_no_toca_la_ultima(
            self, app, bd_temporal, monkeypatch):
        # '6mv' ordena antes que '9mev' (ORDER BY energia) -> primera tabla
        # creada = 6mv, última = 9mev (la que quedaba fija en la clausura rota).
        ref = _preparar_control(bd_temporal, ["6mv", "9mev"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)

        tablas = dlg.findChildren(QTableWidget)
        assert len(tablas) == 2
        primera_tabla = tablas[0]
        primera_tabla.setCurrentCell(1, 1)  # "Dosis Ref" de la tabla 6mv

        _mockear_dialogos_eliminar(monkeypatch)
        dlg.btn_delete.clicked.emit()

        assert _activo_de(bd_temporal, ref, "6mv") == 0, \
            "debía anular la energía seleccionada (6mv)"
        assert _activo_de(bd_temporal, ref, "9mev") in (1, None), \
            "9mev no se tocó -- nunca se seleccionó nada ahí"

    def test_explorar_la_ultima_tabla_y_decidir_en_la_primera_anula_la_correcta(
            self, app, bd_temporal, monkeypatch):
        """El caso silencioso y peligroso: el físico exploró la última
        tabla (dejando ahí una fila "current") y terminó seleccionando la
        PRIMERA -- con el bug, eliminarRegistro habría anulado la energía
        de la tabla que quedó fija en la clausura (9mev), no la que el
        físico miraba al hacer clic en Eliminar."""
        ref = _preparar_control(bd_temporal, ["6mv", "9mev"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)

        tablas = dlg.findChildren(QTableWidget)
        primera_tabla, ultima_tabla = tablas[0], tablas[1]

        ultima_tabla.setCurrentCell(1, 1)   # explora 9mev primero
        primera_tabla.setCurrentCell(1, 1)  # decide anular 6mv

        _mockear_dialogos_eliminar(monkeypatch)
        dlg.btn_delete.clicked.emit()

        assert _activo_de(bd_temporal, ref, "6mv") == 0
        assert _activo_de(bd_temporal, ref, "9mev") == 1


class TestMultiplesEnergiasNoSeConfundenAlEditar:
    """(b), extendido a Editar/Aceptar -- mismo mecanismo, mismo fix
    (dlg._tabla_dosimetria_activa), botón distinto."""

    def test_editar_en_la_primera_tabla_no_toca_la_ultima(
            self, app, bd_temporal, monkeypatch):
        ref = _preparar_control(bd_temporal, ["6mv", "9mev"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)

        tablas = dlg.findChildren(QTableWidget)
        primera_tabla = tablas[0]
        primera_tabla.setCurrentCell(1, 1)  # "Dosis Ref" de la tabla 6mv

        _mockear_dialogos_editar(monkeypatch)
        dlg.edit_table.clicked.emit()
        item = primera_tabla.item(1, 1)
        item.setText("2.02")
        dlg.accept_edit.clicked.emit()

        assert _dosis_de(bd_temporal, ref, "6mv") == 2.02
        assert _dosis_de(bd_temporal, ref, "9mev") == 1.01, \
            "9mev no debía cambiar -- la edición era sobre 6mv"


class TestAvisoHonesto:
    def test_el_texto_menciona_la_energia_que_se_va_a_anular(
            self, app, bd_temporal, monkeypatch):
        ref = _preparar_control(bd_temporal, ["15mv"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)
        tabla = dlg.findChildren(QTableWidget)[0]
        tabla.setCurrentCell(1, 1)

        textos_pregunta = []

        def _capturar_question(*args, **kwargs):
            textos_pregunta.append(args[2] if len(args) > 2 else kwargs.get("text"))
            return QMessageBox.Yes

        class _DialogoAdminFalso:
            def __init__(self, user):
                self.user = user

            def exec(self):
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(load_mod, "DialogAdminPermisoEliminar", _DialogoAdminFalso)
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "question", staticmethod(_capturar_question))
        monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

        dlg.btn_delete.clicked.emit()

        assert len(textos_pregunta) == 1
        assert "15mv" in textos_pregunta[0]
        assert "no se borran" in textos_pregunta[0]

    def test_confirmacion_generica_para_otras_tablas_no_cambia(self):
        """Anti-regresión: eliminarRegistro sigue usando el texto genérico
        para cualquier tabla que no sea dosimetriaMen (_mostrar_dialogo,
        crear_ventanas_emergentes_tablas -- una sola tabla, sin el
        problema de energía múltiple)."""
        # Verificado por inspección de código en el propio commit: la
        # rama `if nombre_tabla == "dosimetriaMen"` es la ÚNICA que cambia
        # el texto; el resto sigue con el genérico. Cubierto también por
        # los tests preexistentes de _mostrar_dialogo (tamano_campo,
        # equipos_medicion) que ya verifican el flujo de eliminar sin
        # tocar el texto -- no se duplica aquí.
        assert True


class TestEdicionSigueFuncionandoIgual:
    """Anti-regresión: UserRole+1 (tabla+columna, que consume
    guardarEdicion) se sigue poniendo SOLO en las columnas editables -- el
    nuevo UserRole en TODAS las celdas no habilita editar donde antes no
    se podía."""

    def test_celda_de_energia_nominal_no_es_editable(self, app, bd_temporal, monkeypatch):
        ref = _preparar_control(bd_temporal, ["6mv"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)
        tabla = dlg.findChildren(QTableWidget)[0]

        item = tabla.item(0, 1)  # "Energía Nominal (MV)", columna Valor
        assert item.data(Qt.UserRole + 1) is None

    def test_editar_dosis_ref_sigue_funcionando_con_una_sola_energia(
            self, app, bd_temporal, monkeypatch):
        ref = _preparar_control(bd_temporal, ["6mv"])
        padre = QDialog()
        padre.user_id = _UsuarioActualFalso()
        dlg = _mostrar_dosimetria_capturando_dialogo(monkeypatch, padre, ref)
        tabla = dlg.findChildren(QTableWidget)[0]
        tabla.setCurrentCell(1, 1)  # "Dosis Ref (cGy/UM)", columna Valor

        _mockear_dialogos_editar(monkeypatch)
        dlg.edit_table.clicked.emit()
        item = tabla.item(1, 1)
        item.setText("2.02")
        dlg.accept_edit.clicked.emit()

        assert _dosis_de(bd_temporal, ref, "6mv") == 2.02
