"""B5 (PLAN_FUGA_CONEXIONES_01-09.md §2.3/§4): `seiscientos_mensual.py::
consultar_fisicos_bd` -- RIESGO BAJO, solo lectura: nunca cerraba `conn`
en ninguna de sus dos ramas (`obtener_conexion()`/`Conexion().conectar()`
según `equipo_f`). [medido] 3 descriptores por llamada, no bloquea a
nadie.

Transformación distinta de P3 estándar: la adquisición de `conn` es un
`if/else` (dos fábricas posibles), no una asignación simple -- se resuelve
primero a una variable (`_gestor_conn`, sin tocar la lógica de cuál rama
elige) y LUEGO se abre el `with` sobre ella, así que ambas ramas quedan
protegidas por el mismo `with` sin duplicar código.

No hay un parámetro bindeable que corromper en este SELECT (sin WHERE):
el invariante que importa es que el `with` invoque `__exit__` en el
camino normal, que es justo lo que faltaba. El resto del comportamiento
ya está cubierto por `test_z8_consulta_fisico1.py`."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


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


def _mensual_pelado():
    from PyQt5.QtCore import QDate
    from PyQt5.QtWidgets import QDateEdit
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.equipo_f = "Tomógrafo"  # fuerza la rama Conexion().conectar()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 6, 1))
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB5ConsultarFisicosBdCierraSiempre:
    def test_camino_normal_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _mensual_pelado()
        fisicos, nombre_f1 = obj.consultar_fisicos_bd()

        assert fisicos == []
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ tras el SELECT -- se registró: "
            f"{_ConexionUnaVezEspia.llamadas}")
