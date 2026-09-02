"""L2b (PLAN_CIERRE_LECTURAS_02-09.md §5.3/§6): `equipos.py::Config.
editarEquipo` -- el `SELECT ... ; conn.close()` vive en código LINEAL,
antes de que empiece el `try` (más abajo, que solo cubre poblar los
widgets). Si `id_equipo` no es bindeable (una lista, p. ej. por un
`Qt.UserRole` corrupto), `cursor.execute(...)` revienta con
`sqlite3.ProgrammingError` -- sube directo al slot de Qt
(`self.tios6.clicked` -> `habilitar2` -> `editarEquipo`) y se traga en
silencio. La conexión queda abierta.

`with` acotado a las 3 líneas que usan `conn` (P3); el `conn.close()`
explícito se retira.

P10 (blindaje, PLAN_CIERRE_LECTURAS_02-09.md): este sitio NO tenía red --
sus 4 menciones previas en la suite eran 2 docstrings y 2 tests que lo
SUSTITUÍAN por un lambda (`obj.editarEquipo = lambda: None`), nunca
ejercitaban la función real. Este archivo construye esa red por primera
vez: un Config "pelado" con los widgets reales que `editarEquipo` puebla
(tipo/modelo/serie/calib_factor/calib_date/fabricante/t_cal/p_cal/h_cal/
v1_cal/sel_activo/btn_img_cert), verificado VERDE sobre el código de hoy
antes de tocar nada."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QWidget,
)

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.equipos as equipos_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasGuia.equipos import Config


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


_CERT_DEFECTO = dict(
    equip_type="Cámara de ionización", model="N30013", serie="2123",
    calibr_fact=0.0545, calibr_fact2=None, fecha_calibr="30/07/2026",
    fabricante="PTW", t_cal=22.0, p_cal=101.325, h_cal=50.0, v1=None,
)


def _preparar_equipo(ruta):
    con = sqlite3.connect(ruta)
    cur = con.execute("""
        INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2,
            fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1, activo, vigente)
        VALUES (:equip_type, :model, :serie, :calibr_fact, :calibr_fact2,
            :fecha_calibr, :fabricante, :t_cal, :p_cal, :h_cal, :v1, 1, 0)
    """, _CERT_DEFECTO)
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


def _instancia_con_formulario(id_para_el_widget, tipo_columna1="Cámara de ionización"):
    """Config "pelado" (sin __init__ pesado, BD real, widgets.xlsx) con los
    widgets REALES que editarEquipo puebla -- lo mínimo para que la función
    corra su camino normal completo sin caer en el `except AttributeError`
    que envuelve el poblado de widgets (eso ocultaría, no probaría, el
    comportamiento del bloque de conexión que P10 exige verificar)."""
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.tipo = QComboBox()
    obj.tipo.addItem(_CERT_DEFECTO["equip_type"])
    obj.modelo = QLineEdit()
    obj.serie = QLineEdit()
    obj.calib_factor = QLineEdit()
    obj.calib_date = QDateEdit()
    obj.calib_date.setDisplayFormat("dd/MM/yyyy")
    obj.fabricante = QLineEdit()
    obj.t_cal = QLineEdit()
    obj.p_cal = QLineEdit()
    obj.h_cal = QLineEdit()
    obj.v1_cal = QLineEdit()
    obj.sel_activo = QCheckBox()
    obj.btn_img_cert = QPushButton()

    obj.table = QTableWidget(1, 2)
    item_id = QTableWidgetItem()
    item_id.setData(Qt.UserRole, id_para_el_widget)
    obj.table.setItem(0, 0, item_id)
    obj.table.setItem(0, 1, QTableWidgetItem(tipo_columna1))
    obj.table.setCurrentCell(0, 0)
    return obj


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestL2bEditarEquipoCierraSiempre:
    def test_id_no_bindeable_revienta_y_aun_asi_se_invoca_exit(
            self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = _instancia_con_formulario(["no bindeable"])

        with pytest.raises(sqlite3.ProgrammingError):
            Config.editarEquipo(obj)

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el SELECT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_poblando_los_widgets_igual(
            self, app, bd_temporal, monkeypatch):
        """P10 paso 1 -- red de caracterización: ejercita editarEquipo por
        su camino REAL (no un mock) y afirma el comportamiento observable
        (los widgets quedan poblados con los datos de la fila). Debe pasar
        VERDE sobre el código de hoy, antes de la transformación P3."""
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        id_equipo = _preparar_equipo(bd_temporal)
        obj = _instancia_con_formulario(id_equipo)

        Config.editarEquipo(obj)

        assert obj.modelo.text() == _CERT_DEFECTO["model"]
        assert obj.serie.text() == _CERT_DEFECTO["serie"]
        assert obj.tipo.currentText() == _CERT_DEFECTO["equip_type"]
        assert obj.calib_factor.text() == str(_CERT_DEFECTO["calibr_fact"])
        assert obj.fabricante.text() == _CERT_DEFECTO["fabricante"]
        assert obj.calib_date.date() == QDate(2026, 7, 30)
        assert obj.sel_activo.isChecked() is True

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez en el "
            f"camino normal -- se registró: {_ConexionUnaVezEspia.llamadas}")
