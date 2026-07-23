"""F2 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): `create_control` identifica
un control mensual por (equipo, mes, anio, tipo) -- nunca por comparar
`fecha` como texto exacto.

Antes: `SELECT id FROM controles WHERE fecha = ? AND equipo = ? AND
control = ?`. Con esa comparacion, 3 fichas reales de produccion que
guardan el dia (formato "dd/MM/yyyy", ver H14/B5) quedaban inalcanzables
desde el formulario (que siempre genera "MM/yyyy") -- abrir ese mes creaba
un control NUEVO y vacio, dejando el original huerfano con sus datos de
dosimetriaMen/tamano_campo colgando. Este es el arreglo de raiz: F3 (mostrar
y guardar el dia) depende de que esto quede corregido primero.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def _self_falso():
    return QWidget()


class TestIdentificaPorMesSinImportarElFormatoDeFecha:

    def test_dia_distinto_mismo_mes_no_duplica(self, app, bd_temporal):
        primero = create_control(_self_falso(), "Clinac iX", "01/07/2026", "Físico de Prueba")
        segundo = create_control(_self_falso(), "Clinac iX", "15/07/2026", "Físico de Prueba")

        assert primero == segundo
        con = conection_mod.Conexion().con
        n = con.execute(
            "SELECT COUNT(*) FROM controles WHERE equipo='Clinac iX' AND control='Mensual'"
        ).fetchone()[0]
        assert n == 1

    def test_formato_viejo_sin_dia_encuentra_el_que_tiene_dia(self, app, bd_temporal):
        """La ficha real de diciembre/2025 (id 1, "14/12/2025") debe quedar
        alcanzable si alguien abre ese mes con el formato viejo "MM/yyyy"."""
        original = create_control(_self_falso(), "Clinac iX", "14/12/2025", "Físico de Prueba")

        encontrado = create_control(_self_falso(), "Clinac iX", "12/2025", "Físico de Prueba")

        assert encontrado == original
        con = conection_mod.Conexion().con
        n = con.execute(
            "SELECT COUNT(*) FROM controles WHERE equipo='Clinac iX' AND control='Mensual'"
        ).fetchone()[0]
        assert n == 1

    def test_dia_con_formato_nuevo_encuentra_el_que_tiene_formato_viejo(self, app, bd_temporal):
        original = create_control(_self_falso(), "Clinac 600", "12/2025", "Físico de Prueba")

        encontrado = create_control(_self_falso(), "Clinac 600", "22/12/2025", "Físico de Prueba")

        assert encontrado == original

    def test_distinto_mes_si_crea_registro_nuevo(self, app, bd_temporal):
        julio = create_control(_self_falso(), "Clinac iX", "01/07/2026", "Físico de Prueba")
        agosto = create_control(_self_falso(), "Clinac iX", "01/08/2026", "Físico de Prueba")

        assert julio != agosto
        con = conection_mod.Conexion().con
        n = con.execute(
            "SELECT COUNT(*) FROM controles WHERE equipo='Clinac iX' AND control='Mensual'"
        ).fetchone()[0]
        assert n == 2

    def test_distinto_equipo_mismo_mes_no_colisiona(self, app, bd_temporal):
        ix = create_control(_self_falso(), "Clinac iX", "01/07/2026", "Físico de Prueba")
        c600 = create_control(_self_falso(), "Clinac 600", "01/07/2026", "Físico de Prueba")

        assert ix != c600


class TestActualizaFisicoSobreElRegistroEncontrado:

    def test_reabrir_mismo_mes_actualiza_fisico_no_duplica(self, app, bd_temporal):
        create_control(_self_falso(), "Halcyon", "01/06/2026", "Físico de Prueba")

        con = conection_mod.Conexion().con
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)",
            ("fisico2", "x", "Segundo Físico", 1, 1, "fisico"))
        con.commit()

        create_control(_self_falso(), "Halcyon", "20/06/2026", "Segundo Físico")

        fila = con.execute(
            "SELECT user_id FROM controles WHERE equipo='Halcyon' AND control='Mensual'"
        ).fetchall()
        assert len(fila) == 1
        assert fila[0][0] == "Segundo Físico"
