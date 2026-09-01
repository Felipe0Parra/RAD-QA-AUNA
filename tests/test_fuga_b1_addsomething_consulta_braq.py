"""B1 (PLAN_FUGA_CONEXIONES_01-09.md §2.3/§4): `braq_mensual.py::
addsomething::consulta` -- RIESGO BAJO, de solo lectura: nunca cierra
`conn` en ningún camino. [medido, §1.3 del plan] una lectura abandonada
cuesta 3 descriptores y no bloquea a nadie -- higiene, no urgencia.

P2: `ref` llega como una lista -- no bindeable -- el `SELECT` revienta
dentro del `with`."""
import os
import sqlite3

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq


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


def _braq_mensual_pelado(prueba, nombre_campo):
    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)
    setattr(obj, nombre_campo, QLineEdit())
    return obj, pd.DataFrame({
        "widget_type": ["QLineEdit"],
        "prueba": [prueba],
        "nombres": [nombre_campo],
    })


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB1AddsomethingConsultaCierraSiempre:
    def test_select_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj, df = _braq_mensual_pelado("tipo", "campo_user")

        with pytest.raises(sqlite3.ProgrammingError):
            obj.addsomething(QWidget(), df, "tipo", "TipoCalibracion", "id", ["no bindable"])

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_leyendo_igual(self, app, bd_temporal):
        con = Conexion().conectar()
        con.execute(
            "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
            "certificado, fecha_cer, intensidad, conversion, activo) "
            "VALUES (5, 'calibracion_pedida', '01/01/2024', 1.0, 'SN5', "
            "1.0, '01/01/2025', 1.0, 1.0, 1)")
        con.commit()
        con.close()

        obj, df = _braq_mensual_pelado("tipo", "campo_user")
        obj.addsomething(QWidget(), df, "tipo", "TipoCalibracion", "id", 5)

        assert obj.campo_user.text() == "calibracion_pedida"
