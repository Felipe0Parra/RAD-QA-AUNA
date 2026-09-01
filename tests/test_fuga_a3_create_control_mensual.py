"""A3 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `load.py::create_control`
(alta/reapertura de un control mensual) tenía un `try`/`except sqlite3.Error`
pero **sin `rollback` y sin `close`** -- el `except` avisa y traga, sin
tocar la conexión para nada.

P2 (nota de método, ver A2): se verifica el invariante ESTRUCTURAL --
`_ConexionUnaVez.__exit__` se invoca en el camino de excepción -- vía una
subclase-espía, no un cronómetro sobre un segundo escritor (no
discrimina de forma confiable para una excepción de una sola cadena de
frames)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import create_control


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


def _self_falso():
    return QWidget()


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA3CreateControlCierraSiempre:
    def test_insert_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        """P2: `maquina` llega como una lista -- un tipo que sqlite3 no
        puede bindear -- así que el INSERT revienta DENTRO del `with`. Un
        dato mal formado que llegara así desde la UI produciría el mismo
        fallo. `create_control` tiene su PROPIO `except sqlite3.Error`
        (que muestra un `QMessageBox.critical` y traga -- deuda de otro
        plan, no se toca aquí): la excepción NO escapa de la función, así
        que se mockea el diálogo (Trampa 2 de CLAUDE.md: uno real sin
        mockear cuelga la suite bajo offscreen) y se verifica el espía en
        vez de un `pytest.raises`."""
        monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        resultado = create_control(_self_falso(), ["no bindable"], "01/07/2026", "Físico de Prueba")

        assert resultado is None  # el except de la propia función lo traga
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el INSERT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal, monkeypatch):
        llamados = []
        monkeypatch.setattr(load_mod.QMessageBox, "information",
                             staticmethod(lambda *a, **k: llamados.append(a[2] if len(a) > 2 else k.get("text"))))

        ref = create_control(_self_falso(), "Clinac iX", "01/07/2026", "Físico de Prueba")

        assert ref is not None
        assert len(llamados) == 1
        assert "Datos insertados" in llamados[0]
