"""F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): el formulario mensual
muestra y guarda el día real -- antes solo mes/año ("MM/yyyy"). Depende de
F2 (create_control identifica por mes/año, no por fecha exacta) ya
ejecutado -- sin eso, guardar el día real habría duplicado controles.

Cubre: `ui.util_fechas.fecha_control_a_qdate` (parser tolerante para
reconstruir el date_box al reabrir un control) y
`PruebaMensual600._fecha_real_del_control` /
`_fecha_control_para_nombre_archivo` (la fecha de sesión debe reflejar lo
guardado en la BD, no el día recién elegido para buscar).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.util_fechas import fecha_control_a_qdate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestFechaControlAQDate:

    def test_formato_nuevo_con_dia(self):
        d = fecha_control_a_qdate("15/07/2026")
        assert (d.year(), d.month(), d.day()) == (2026, 7, 15)

    def test_formato_viejo_sin_dia_usa_dia_1(self):
        d = fecha_control_a_qdate("07/2026")
        assert (d.year(), d.month(), d.day()) == (2026, 7, 1)

    def test_texto_irreconocible_no_lanza(self):
        d = fecha_control_a_qdate("no-es-una-fecha")
        assert isinstance(d, QDate)

    def test_vacio_no_lanza(self):
        d = fecha_control_a_qdate("")
        assert isinstance(d, QDate)


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
    import data.ManejoDatos.load as load_mod
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _DbManagerFalso:
    def obtener_conexion(self):
        return Conexion().conectar()


class _MensualDePrueba:
    """Instancia mínima de PruebaMensual600 -- solo lo que
    _fecha_real_del_control/_fecha_control_para_nombre_archivo necesitan,
    sin levantar toda la UI de widgets.xlsx (mismo patrón que
    test_mcc_autofill_mensual.py: QWidget pelado + los atributos puntuales)."""

    def __init__(self, equipo_f):
        self.equipo_f = equipo_f
        self.db_manager = _DbManagerFalso()


class TestFechaRealDelControl:
    """`limpiar_layout` (via _fecha_real_del_control) debe reflejar lo que
    de verdad quedó en `controles.fecha`, no el día recién elegido para
    buscar -- si create_control encontró un control de OTRO día del mismo
    mes, ese día (el guardado) es el que debe prevalecer."""

    def test_devuelve_la_fecha_real_guardada(self, app, bd_temporal):
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as sm
        instancia = _MensualDePrueba("Clinac iX")
        instancia._fecha_real_del_control = sm.PruebaMensual600._fecha_real_del_control.__get__(instancia)

        con = conection_mod.Conexion().con
        # X1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): create_control ya
        # no guarda el centinela " ---- " para "sin 2º físico" -- guarda NULL
        # (ese centinela violaba la FK de user_id_f2 a users(fullname)).
        cur = con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
            "VALUES (?,?,?,?,?)",
            ("Clinac iX", "Mensual", "05/07/2026", "Físico de Prueba", None))
        con.commit()
        control_id = cur.lastrowid

        assert instancia._fecha_real_del_control(control_id) == "05/07/2026"

    def test_id_inexistente_devuelve_none(self, app, bd_temporal):
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as sm
        instancia = _MensualDePrueba("Clinac iX")
        instancia._fecha_real_del_control = sm.PruebaMensual600._fecha_real_del_control.__get__(instancia)

        assert instancia._fecha_real_del_control(9999) is None

    def test_none_no_consulta_nada(self, app, bd_temporal):
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as sm
        instancia = _MensualDePrueba("Clinac iX")
        instancia._fecha_real_del_control = sm.PruebaMensual600._fecha_real_del_control.__get__(instancia)

        assert instancia._fecha_real_del_control(None) is None


class TestFechaControlParaNombreArchivo:

    def test_reemplaza_barras_por_guiones(self, app):
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as sm
        instancia = _MensualDePrueba("Clinac 600")
        instancia.fecha_control = "15/07/2026"
        metodo = sm.PruebaMensual600._fecha_control_para_nombre_archivo.__get__(instancia)

        assert metodo() == "15-07-2026"

    def test_sin_fecha_control_no_lanza(self, app):
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as sm
        instancia = _MensualDePrueba("Clinac 600")
        instancia.fecha_control = None
        metodo = sm.PruebaMensual600._fecha_control_para_nombre_archivo.__get__(instancia)

        assert metodo() == ""
