"""B4 (PLAN_FUGA_CONEXIONES_01-09.md §2.3/§4): `ix_mensual.py::
PruebaMensualIX._cargar_dosimetria_bd_ix` -- RIESGO BAJO, solo lectura:
nunca cerraba `conn` (solo `cursor.close()` al final, que no es lo mismo).
[medido] 3 descriptores por llamada, no bloquea a nadie.

P2: `ref` llega como una lista -- no bindeable -- el SELECT revienta
dentro del `with`. El resto del comportamiento (mapeo por columna,
round-trip) ya está cubierto por `test_h27_bd_unica_mensual.py` -- no se
repite aquí."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

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


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB4CargarDosimetriaBdIxCierraSiempre:
    def test_select_revienta_y_aun_asi_se_invoca_exit(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = PruebaMensualIX.__new__(PruebaMensualIX)
        QWidget.__init__(obj)

        import sqlite3
        with pytest.raises(sqlite3.ProgrammingError):
            obj._cargar_dosimetria_bd_ix(["ln_dosis_ref_cgy_um_6mv"], "dosimetriaMen", ["no bindable"])

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")
