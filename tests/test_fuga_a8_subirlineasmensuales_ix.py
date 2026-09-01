"""A8 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `ix_mensual.py::
PruebaMensualIX.subirlineasmensuales_ix` es idéntico a A7 (`DP-51`):
NINGÚN camino cerraba `conn` -- ni `cursor.close()` (que cierra el cursor,
no la conexión) al final, ni ningún camino intermedio. Sin `try` alrededor
del bucle de escrituras: cualquier fallo en cualquier energía sube sin que
nada cierre nada.

P2: mismo método que A7 -- un widget cuyo `.text()` devuelve un objeto sin
`.strip()`, que revienta bien dentro del `with` (la llamada `.text().
strip()` ocurre ANTES de cualquier rama de conversión)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


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
    """Ancla de la ventana de edición (F4b, mismo motivo que en A7)."""
    import sqlite3
    from datetime import datetime
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, 'Clinac ix', 'Mensual', '01/2026', 'Físico de Prueba')",
        (control_id,))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


def _pelado_ix(energias=("6mv",)):
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    df_lines = []
    for e in energias:
        for campo in ("ln_dosis_ref_cgy_um", "ln_calidad_pdd20_10"):
            nombre = f"{campo}_{e}"
            setattr(obj, nombre, QLineEdit())
            df_lines.append(nombre)
    obj.ln_observaciones_dosi = QLineEdit()
    df_lines.append("ln_observaciones_dosi")
    return obj, df_lines


class _WidgetRoto:
    def text(self):
        return object()  # sin .strip() -- AttributeError dentro del with


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA8SubirlineasmensualesIXCierraSiempre:
    def test_widget_roto_revienta_y_aun_asi_se_invoca_exit(
            self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        _crear_control_activo(bd_temporal, 900)

        obj, df_lines = _pelado_ix()
        obj.ln_observaciones_dosi = _WidgetRoto()

        with pytest.raises(AttributeError, match="strip"):
            obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=900, usarid=True, df_lines=df_lines)

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el guardado revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        _crear_control_activo(bd_temporal, 901)
        obj, df_lines = _pelado_ix()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")

        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=901, usarid=True, df_lines=df_lines)

        con = Conexion().conectar()
        n = con.execute(
            "SELECT COUNT(*) FROM dosimetriaMen WHERE ref = ? AND energia = '6mv' AND activo = 1",
            (901,)).fetchone()[0]
        con.close()
        assert n == 1
