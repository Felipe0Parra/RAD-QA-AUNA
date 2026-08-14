"""N4 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): tripwire de la
secuencia completa -- crear control -> guardar dosimetría -> anular ->
reabrir el mismo mes -> reactivar -> el guardado vuelve a funcionar y las
filas hijas NO se perdieron.

Es la prueba de que reactivar es SIN PÉRDIDA -- el argumento con el que el
plan eligió reactivar frente a bifurcar el control (§10.2). El hueco que
este test cierra no era de código sino de COBERTURA: los tests de C2/W1
comprobaban que el listado ocultara el anulado y que "Subir" quedara
bloqueado -- ambos verifican justo lo que pasó en el incidente real del
2026-08-05; faltaba la secuencia completa anular -> reabrir -> reactivar.

La guarda de unicidad de `reactivar_control` (índice U2, "reactivar con
otro control activo presente") ya está cubierta en
`tests/test_n2_reactivar_control.py`
(`TestReactivarControl::test_guarda_de_unicidad_rechaza_si_ya_hay_otro_
activo_del_mismo_mes` / `test_no_viola_el_indice_unico_de_controles`) --
no se duplica aquí.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QDialog, QLineEdit, QMessageBox, QTableWidget,
    QTableWidgetItem, QWidget)

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
import ui.paginasGuia.dialogs as dialogs_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import create_control, subirlineasmensuales
from data.ManejoDatos.user import Usuario


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _DialogoAdminFalso:
    """Reautenticación personal (N2, DA-34) aceptada -- el mismo doble
    ficticio usado en test_n2_reactivar_control.py."""
    def __init__(self, user):
        self.user = user

    def exec(self):
        return QDialog.DialogCode.Accepted


class _UsuarioAdminFalso:
    _nombre = "Administrador"


class _DlgEliminarFalso:
    """El diálogo de la vista de registros que llama a eliminarRegistro --
    mismo doble que test_w1_no_escribir_sobre_control_eliminado.py."""
    user_id = _UsuarioAdminFalso()


def _formulario():
    """El mismo formulario mensual hace las tres cosas en producción real:
    crea el control, guarda dosimetría, y (al reabrir) recibe la oferta de
    reactivar. Aquí se usa un QWidget pelado equivalente para las tres
    llamadas, como haría self en PruebaMensual600/PruebaMensualIX."""
    w = QWidget()
    w.user_id = Usuario(username="fisico", fullname="Físico de Prueba")
    w.df_lines = ["ln_observaciones_dosi"]
    w.ln_observaciones_dosi = QLineEdit("dato de dosimetría")
    return w


def _dosimetria_de(ruta_bd, control_id):
    """Cuenta la dosimetría VIGENTE (activa) de este control. DO1
    (PLAN_CONTRATO_GUARDADO_13-08.md §6-DO1): un reguardado ya no hace
    UPDATE de la misma fila -- anula la vieja e inserta la nueva, así que
    sin este filtro un segundo "Subir" se vería como una fila de más
    aunque siga habiendo UNA sola vigente."""
    con = sqlite3.connect(ruta_bd)
    n = con.execute(
        "SELECT COUNT(*) FROM dosimetriaMen WHERE ref = ? "
        "AND (activo IS NULL OR activo = 1)", (control_id,)).fetchone()[0]
    con.close()
    return n


def _activo_de(ruta_bd, control_id):
    con = sqlite3.connect(ruta_bd)
    fila = con.execute(
        "SELECT activo FROM controles WHERE id = ?", (control_id,)).fetchone()
    con.close()
    return fila[0] if fila else None


class TestCicloAnularReactivar:

    def test_secuencia_completa_sin_perdida(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

        # 1. Crear el control mensual (agosto 2026, Clinac iX).
        control_id = create_control(_formulario(), "Clinac ix", "05/08/2026", "Físico de Prueba")
        assert control_id is not None

        # 2. Guardar dosimetría -- funciona normalmente, como cualquier mes.
        subirlineasmensuales(_formulario(), "dosimetriaMen", 0, ref=control_id, usarid=False)
        assert _dosimetria_de(bd_temporal, control_id) == 1

        # 3. Anular el control -- misma vía que "Registros" -> Eliminar, el
        #    incidente real del 2026-08-05 (audit_log del rebuild: anular
        #    controles id=42 -> el mes quedó inutilizable).
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.Yes))
        tabla = QTableWidget(1, 1)
        item = QTableWidgetItem("fila")
        item.setData(Qt.UserRole, control_id)
        tabla.setItem(0, 0, item)
        tabla.setCurrentCell(0, 0)
        load_mod.eliminarRegistro(_DlgEliminarFalso(), tabla, "controles")

        assert _activo_de(bd_temporal, control_id) == 0

        # 4. Reabrir el MISMO mes: create_control clasifica el control como
        #    anulado (N1) y ofrece reactivar (N2) -- se acepta, con la
        #    reautenticación personal (DA-34, no de administrador).
        monkeypatch.setattr(dialogs_mod, "DialogAdminPermisoEditar", _DialogoAdminFalso)
        control_id_reabierto = create_control(
            _formulario(), "Clinac ix", "20/08/2026", "Físico de Prueba")

        assert control_id_reabierto == control_id, (
            "reactivar debe reusar el MISMO control -- no bifurcar (§10.2)")
        assert _activo_de(bd_temporal, control_id) == 1

        # 5. SIN PÉRDIDA: la dosimetría guardada ANTES de anular sigue ahí
        #    -- anular solo tocó la raíz (controles), nunca sus hijas.
        assert _dosimetria_de(bd_temporal, control_id) == 1

        # 6. El guardado vuelve a funcionar sobre el control reactivado --
        #    el incidente real (el mes quedaba inutilizable) queda cerrado.
        subirlineasmensuales(_formulario(), "dosimetriaMen", 0, ref=control_id, usarid=False)
        assert _dosimetria_de(bd_temporal, control_id) == 1  # UPDATE de la misma fila, no un duplicado
