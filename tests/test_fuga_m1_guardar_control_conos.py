"""M1 (PLAN_FUGA_CONEXIONES_01-09.md §2.2/§4): `ix_mensual.py::
PruebaMensualIX.guardar_control_conos` -- RIESGO MEDIO: ya hace
`rollback()` en su `except` interno antes de re-lanzar, así que nunca deja
una transacción de escritura abierta (no bloquea a nadie); pero JAMÁS
cierra `conn` en ningún camino (ni el normal, ni el de "conos incompletos",
ni el de fallo) -- solo cuesta descriptores por llamada.

P2: `_filas_y_faltantes_conos` (ya diseñada sin efectos secundarios, según
su propio docstring) se sustituye por una que devuelve una fila con un
valor NO bindeable -- el `executemany` revienta DENTRO de la transacción
ya abierta por `BEGIN TRANSACTION`, ejercitando el `except` interno con
`rollback()` real."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

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
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _insertar_control(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Clinac ix", "Mensual", "06/2026"))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _instancia(ref):
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    obj.ref = ref
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestM1GuardarControlConosCierraSiempre:
    def test_executemany_revienta_y_aun_asi_se_invoca_exit(
            self, app, bd_temporal, monkeypatch):
        """Nota de alcance: el `except Exception as e:` EXTERNO de
        `guardar_control_conos` hace `traceback.print_exc(e)` -- un bug
        preexistente ajeno a este plan (`print_exc` toma `limit`, no la
        excepción, como primer posicional; pasarle `e` revienta con un
        `TypeError` distinto en cuanto CUALQUIER excepción llega ahí). No
        se toca (fuera de alcance -- P3 prohíbe mezclar clases de arreglo).
        Lo que importa para A/M1 es que, ANTES de llegar a ese bug
        preexistente, el `with` ya cerró la conexión -- se verifica el
        espía, no `resultado`."""
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        ref = _insertar_control(bd_temporal)

        obj = _instancia(ref)
        obj._filas_y_faltantes_conos = lambda: ([(ref, "6x6", ["no bindable"])], [])

        with pytest.raises(TypeError):  # el bug preexistente de print_exc(e)
            obj.guardar_control_conos()

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el executemany revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        obj = _instancia(ref)
        obj._filas_y_faltantes_conos = lambda: ([(ref, "6x6", 1)], [])

        resultado = obj.guardar_control_conos()

        assert resultado is True
        con = sqlite3.connect(bd_temporal)
        n = con.execute(
            "SELECT COUNT(*) FROM control_conos WHERE ref = ? AND activo = 1",
            (ref,)).fetchone()[0]
        con.close()
        assert n == 1
