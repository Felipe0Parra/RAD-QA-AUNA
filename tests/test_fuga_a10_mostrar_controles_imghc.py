"""A10 (PLAN_FUGA_CONEXIONES_01-09.md §9, hallazgo del propio tripwire R5):
`load.py::mostrar_controles_imgHC` -- gemelo exacto de A9 (Halcyon en vez
de Clinac ix). RIESGO ALTO: mismo `ALTER TABLE pruebas ADD COLUMN
mes_control` + `UPDATE pruebas SET mes_control = ...` sin ningún
`try`/`except`.

Mismo tratamiento que A9: `with` acotado a la parte que usa `conn`; P2 con
`filtro_activo` reventando."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QTableWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
import data.ManejoDatos.load as load_mod


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


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestA10MostrarControlesImgHCCierraSiempre:
    def test_filtro_activo_revienta_y_aun_asi_se_invoca_exit(
            self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        def _filtro_que_revienta(tabla):
            raise RuntimeError("fallo inyectado por el test")

        monkeypatch.setattr(load_mod, "filtro_activo", _filtro_que_revienta)

        with pytest.raises(RuntimeError, match="fallo inyectado"):
            load_mod.mostrar_controles_imgHC(None, QTableWidget(), "Físico de Prueba")

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando la función revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_funcionando_igual(self, app, bd_temporal):
        con = Conexion().con
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)",
            ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
        con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id) "
            "VALUES (?, ?, ?, ?)",
            ("Halcyon", "Mensual", "01/2026", "Físico de Prueba"))
        con.commit()

        tabla = QTableWidget()
        load_mod.mostrar_controles_imgHC(None, tabla, "Físico de Prueba")

        assert tabla.rowCount() == 1
