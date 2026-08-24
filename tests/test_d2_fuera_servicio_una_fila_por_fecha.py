"""D2 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): `conectarfueradeservicio`
cumple el mismo contrato de reemplazo por fecha que `add_info` (H2.2):
**una fila VIGENTE por fecha**, no necesariamente una fila total.

Causa raíz: antes de este fix, `conectarfueradeservicio` hacía un INSERT sin
DELETE previo -- a diferencia de `add_info`, que desde H2.2 borra la fila
existente de esa fecha (con confirmación). Evidencia real del 2026-08-05:
7 filas vacías el mismo día en `aceleradorlineal_ix` porque el físico pulsó
"Fuera de servicio" y "Subir" varias veces.

EB4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB4, 24-08): el `DELETE` de H2.2/D2
pasó a `reemplazar_bloque` (EB1) -- el reemplazo ya NO borra la fila
anterior, la ANULA (`activo=0`). `_filas_tabla` cuenta solo las VIGENTES
por defecto (el invariante que este archivo siempre quiso probar); un
parámetro aparte permite contar el total cuando hace falta verificar que
la anterior sigue en la BD, recuperable.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QDateEdit, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import conectarfueradeservicio


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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _SelfFalso(QWidget):
    def __init__(self, fecha=QDate(2026, 8, 5)):
        super().__init__()
        self.user_id = _UsuarioFalso()
        self.date_box = QDateEdit()
        self.date_box.setDate(fecha)
        self.observaciones = QLineEdit("mantenimiento")


def _filas_tabla(ruta_bd, fecha_iso="2026-08-05", solo_vigentes=True):
    con = sqlite3.connect(ruta_bd)
    query = "SELECT COUNT(*) FROM aceleradorlineal_ix WHERE DATE(date) = ?"
    if solo_vigentes:
        query += " AND (activo IS NULL OR activo = 1)"
    n = con.execute(query, (fecha_iso,)).fetchone()[0]
    con.close()
    return n


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT accion, detalle FROM audit_log ORDER BY id").fetchall()
    con.close()
    return filas


class TestD2UnaFilaPorFecha:

    def test_dos_declaraciones_seguidas_dejan_una_sola_fila_vigente(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
        conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")
        conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")

        assert _filas_tabla(bd_temporal) == 1, "una sola fila VIGENTE por fecha"
        assert _filas_tabla(bd_temporal, solo_vigentes=False) == 2, (
            "EB4: la primera no se borró -- quedó anulada, recuperable")

    def test_reemplazo_pide_confirmacion_y_no_escribe_nada(self, app, bd_temporal, monkeypatch):
        conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")  # primera, sin preguntar

        preguntado = []
        monkeypatch.setattr(
            load_mod.QMessageBox, "question",
            staticmethod(lambda *a, **k: preguntado.append(True) or load_mod.QMessageBox.No))
        conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")  # segunda, declina

        assert preguntado, "debía preguntar -- ya había una fila para esa fecha"
        assert _filas_tabla(bd_temporal) == 1  # sigue la original, sin tocar

        filas_audit = _audit_log(bd_temporal)
        assert len(filas_audit) == 1  # solo la del primer guardado, ninguna del segundo intento

    def test_reemplazo_confirmado_deja_reemplazo_y_guardar_auditados(self, app, bd_temporal, monkeypatch):
        conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")

        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
        conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")

        filas_audit = _audit_log(bd_temporal)
        assert [a for a, _ in filas_audit] == ["guardar", "reemplazo", "guardar"]

    def test_detalle_de_guardar_dice_fuera_de_servicio(self, app, bd_temporal):
        conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")

        detalle = _audit_log(bd_temporal)[0][1]
        assert detalle == "equipo fuera de servicio"

    def test_fechas_distintas_siguen_conviviendo(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))
        conectarfueradeservicio(_SelfFalso(QDate(2026, 8, 5)), "aceleradorlineal_ix")
        conectarfueradeservicio(_SelfFalso(QDate(2026, 8, 6)), "aceleradorlineal_ix")

        assert _filas_tabla(bd_temporal, "2026-08-05") == 1
        assert _filas_tabla(bd_temporal, "2026-08-06") == 1
