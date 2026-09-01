"""B7 (PLAN_FUGA_CONEXIONES_01-09.md §2.3/§4): `seiscientos_mensual.py::
_fecha_real_del_control` -- RIESGO BAJO, solo lectura: nunca cerraba
`conn`. [medido] 3 descriptores por llamada, no bloquea a nadie.

Mismo patrón de ternario que B6. P2: `control_id` llega como una lista --
no bindeable -- el SELECT revienta dentro del `with`."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod


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


class _MensualDePrueba:
    def __init__(self, equipo_f="Tomógrafo"):
        self.equipo_f = equipo_f  # 'Tomógrafo' fuerza Conexion().conectar(), sin db_manager
        self._fecha_real_del_control = mensual_mod.PruebaMensual600._fecha_real_del_control.__get__(self)


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB7FechaRealDelControlCierraSiempre:
    def test_select_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        instancia = _MensualDePrueba()
        resultado = instancia._fecha_real_del_control(["no bindable"])

        assert resultado is None  # el except propio lo traga y avisa
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_leyendo_igual(self, app, bd_temporal):
        con = Conexion().con
        cur = con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
            ("Clinac iX", "Mensual", "05/07/2026"))
        con.commit()
        control_id = cur.lastrowid

        instancia = _MensualDePrueba()
        assert instancia._fecha_real_del_control(control_id) == "05/07/2026"
