"""A7 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `load.py::
subirlineasmensuales` NUNCA cerraba `conn` en ningún camino -- ni en sus 2
`return` tempranos (que solo cierran el `cursor`), ni en el `finally`
final (que también solo cierra el `cursor`, no `conn`). Su propio
`except Exception as ex: traceback.print_exc(); print(...)` traga
cualquier fallo del guardado real (`DP-46`, deuda de otro plan, no se
toca aquí) -- ese camino tampoco cerraba nada.

P2: uno de los widgets del formulario (`ln_observaciones_dosi`, en la
lista de campos que se guardan como texto plano) se sustituye por uno
cuyo `.text()` devuelve un objeto sin `.strip()` -- el mismo tipo de
fallo que un dato mal formado real, y ocurre bien dentro del `with`."""
import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from data.ManejoDatos.load import subirlineasmensuales
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager)


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


@pytest.fixture(autouse=True)
def _sin_avisos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _crear_control_activo(ruta_bd, control_id):
    """El ancla de la ventana de edición (F4b) se resuelve por el
    `audit_log` de la creación, no por la fecha clínica del control --
    sin esta fila, `puede_editarse` cae fuera de la ventana de 2 meses
    (la `fecha` del control es de enero, "hoy" es 2026-09-01)."""
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, 'Clinac 600', 'Mensual', '01/2026', 'Físico de Prueba')",
        (control_id,))
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
    obj.user_id = _UsuarioFalso()
    obj.ln_dosis_ref_cgy_um_6mv = QLineEdit()
    obj.ln_observaciones_dosi = QLineEdit()
    return obj


class _WidgetRoto:
    def text(self):
        return object()  # sin .strip() -- AttributeError dentro del with


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA7SubirlineasmensualesCierraSiempre:
    def test_widget_roto_revienta_y_aun_asi_se_invoca_exit(
            self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        _crear_control_activo(bd_temporal, 900)

        obj = _pelado_600()
        obj.df_lines = ["ln_observaciones_dosi"]
        obj.ln_observaciones_dosi = _WidgetRoto()

        with pytest.raises(AttributeError, match="strip"):
            subirlineasmensuales(obj, "dosimetriaMen", 0, ref=900, usarid=False)

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el guardado revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        _crear_control_activo(bd_temporal, 901)
        obj = _pelado_600()
        obj.df_lines = ["ln_dosis_ref_cgy_um_6mv"]
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=901, usarid=False)

        con = Conexion().conectar()
        n = con.execute(
            "SELECT COUNT(*) FROM dosimetriaMen WHERE ref = ? AND activo = 1",
            (901,)).fetchone()[0]
        con.close()
        assert n == 1
