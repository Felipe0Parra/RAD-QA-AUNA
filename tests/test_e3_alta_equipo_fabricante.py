"""E3 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §4): el alta de equipos guarda
el fabricante.

Antes, el INSERT de `Config.cargarDatos` enumeraba 13 columnas sin
`fabricante` y la `lista` de `anadir()` nunca leía `self.fabricante.text()`:
el campo quedaba NULL y la tabla lo pintaba "NA". La edición
(`guardarCambios`) SÍ lo manejaba -- asimetría pura de alta vs edición.

El riesgo real de esta corrección es el DESALINEAMIENTO (un valor cayendo en
la columna equivocada), así que el test central inserta una lista con todos
los valores distintos y verifica columna por columna.
"""
import inspect
import re
import sqlite3

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.equipos import Config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"


# El orden que arma anadir() y consume el INSERT de cargarDatos -- la fuente
# única de este test para detectar cualquier desfase futuro.
LISTA_ALTA = [
    "Cámara de ionización",   # equip_type
    "TN31010",                # model
    "1822",                   # serie
    "0.3034",                 # calibr_fact
    None,                     # calibr_fact2 (solo Electrómetro)
    "16/03/2026",             # fecha_calibr
    "PTW",                    # fabricante  <- lo que E3 añade
    22.0,                     # t_cal
    101.325,                  # p_cal
    50.0,                     # h_cal
    400.0,                    # v1
    1,                        # activo
    1,                        # vigente
    None,                     # imagen_certificado
]


class TestCargarDatosGuardaFabricante:
    def test_cada_valor_cae_en_su_columna(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioActualFalso()

        Config.cargarDatos(obj, LISTA_ALTA)

        con = sqlite3.connect(bd_temporal)
        try:
            fila = con.execute(
                "SELECT equip_type, model, serie, calibr_fact, calibr_fact2, "
                "fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1, activo, "
                "vigente, imagen_certificado FROM equipos").fetchone()
        finally:
            con.close()
        # v1 vuelve como texto: la columna es TEXT en el DDL (preexistente).
        assert list(fila) == [
            "Cámara de ionización", "TN31010", "1822", 0.3034, None,
            "16/03/2026", "PTW", 22.0, 101.325, 50.0, "400.0", 1, 1, None]

    def test_el_alta_sigue_auditando_modelo_y_serie(self, app, bd_temporal, monkeypatch):
        """La auditoría de H2.4 usa lista[1]/lista[2] (modelo/serie) -- E3
        insertó fabricante en la posición 6, así que esos índices no deben
        haberse corrido."""
        monkeypatch.setattr(QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioActualFalso()

        Config.cargarDatos(obj, LISTA_ALTA)

        con = sqlite3.connect(bd_temporal)
        try:
            fila = con.execute(
                "SELECT usuario, accion, tabla, ref FROM audit_log").fetchone()
        finally:
            con.close()
        assert fila == ("Físico de Prueba", "guardar", "equipos", "TN31010/1822")


class TestAnadirArmaLaListaEnElMismoOrden:
    def test_lista_de_anadir_alineada_con_el_insert(self):
        """`anadir()` es una clausura dentro de `habilitar1` (no invocable sin
        montar toda la pestaña), así que el alineamiento lista<->INSERT se fija
        estáticamente: la línea `lista = [...]` debe tener EXACTAMENTE las
        variables en el orden de las columnas del INSERT."""
        fuente = inspect.getsource(Config.habilitar1)
        m = re.search(r"lista = \[([^\]]+)\]", fuente)
        assert m, "no se encontró la construcción de `lista` en anadir()"
        variables = [v.strip() for v in m.group(1).split(",")]
        assert variables == [
            "tipo", "modelo", "serie", "factor_calibracion", "segundo_factor",
            "fecha_calibracion", "fabricante", "t_cal", "p_cal", "h_cal", "v1",
            "activo", "vigente", "imagen_blob"]

    def test_anadir_lee_el_widget_fabricante(self):
        fuente = inspect.getsource(Config.habilitar1)
        assert "self.fabricante.text()" in fuente
