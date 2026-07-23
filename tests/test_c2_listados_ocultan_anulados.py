"""C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): un control anulado
(`controles.activo = 0`, ver eliminarRegistro/eliminarRegistroCT) sigue en la
BD (soft-delete) pero NO debe seguir apareciendo en ninguno de los listados
del mensual/anual/CT -- 13 sitios de consulta en total (`mostrar_controles_*`
en load.py + `mostrar_controles_anuales` en tablas_anuales.py), todos con el
mismo patrón `WHERE ... AND (c.activo IS NULL OR c.activo = 1)`.

Cada función se llama con un QTableWidget real y una BD temporal con 2
controles del mismo equipo/tipo: uno activo y uno anulado -- solo el activo
debe terminar en la tabla.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QTableWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
import data.ManejoDatos.Tablas_Anuales.tablas_anuales as tablas_anuales_mod
from data.ManejoDatos.conection import Conexion


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real -- incluye la migración activo
    yield conexion
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None


def _crear_controles(con, equipo, control, id_activo, id_anulado):
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id, activo) "
        "VALUES (?, ?, ?, '01/2026', 'Cristian Castellanos', 1)",
        (id_activo, equipo, control))
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id, activo) "
        "VALUES (?, ?, ?, '02/2026', 'Cristian Castellanos', 0)",
        (id_anulado, equipo, control))
    con.commit()


class TestMostrarControlesMensuales:
    """La tabla PRINCIPAL que ve el físico en el mensual (600/iX/Halcyon/
    Tomógrafo, todas heredan de PruebaMensual600) -- el hallazgo original
    del handoff (control 40 "fantasma") pasa por esta misma consulta."""

    def test_control_anulado_no_aparece_en_el_listado(self, app, bd_temporal):
        _crear_controles(bd_temporal.con, "Clinac 600", "Mensual", 1, 2)
        tabla = QTableWidget()

        load_mod.mostrar_controles_mensuales(None, tabla, equipo_filtrar="Clinac 600")

        assert tabla.rowCount() == 1

    def test_sin_filtro_de_equipo_tambien_oculta_anulados(self, app, bd_temporal):
        _crear_controles(bd_temporal.con, "Halcyon", "Mensual", 3, 4)
        tabla = QTableWidget()

        load_mod.mostrar_controles_mensuales(None, tabla, equipo_filtrar=None)

        ids_mostrados = {tabla.item(r, 0).data(load_mod.Qt.UserRole)
                         for r in range(tabla.rowCount())
                         if tabla.item(r, 0) is not None}
        assert 4 not in ids_mostrados


class TestMostrarControlesAnualesTablasAnuales:
    def test_control_anulado_no_aparece(self, app, bd_temporal):
        _crear_controles(bd_temporal.con, "Clinac 600", "Anual", 5, 6)
        tabla = QTableWidget()

        tablas_anuales_mod.mostrar_controles_anuales(None, tabla, equipo_filtrar="Clinac 600")

        assert tabla.rowCount() == 1


class TestListadosSistemaDeImagenes:
    """Las 5 funciones de imágenes (IX/Halcyon/Tomógrafo, anual/mensual) --
    cada una hace 2 SELECT internos (conteo + detalle); basta verificar el
    rowCount final de la tabla que arma cada una."""

    @pytest.mark.parametrize("funcion,equipo,control", [
        (load_mod.mostrar_controles_imgIX_anual, "Clinac ix", "Anual"),
        (load_mod.mostrar_controles_imgIX, "Clinac ix", "Mensual"),
        (load_mod.mostrar_controles_imgHC_anual, "Halcyon", "Anual"),
        (load_mod.mostrar_controles_imgHC, "Halcyon", "Mensual"),
        (load_mod.mostrar_controles_tac, "Tomógrafo", "Mensual"),
    ])
    def test_control_anulado_no_aparece(self, app, bd_temporal, funcion, equipo, control):
        _crear_controles(bd_temporal.con, equipo, control, 10, 11)
        tabla = QTableWidget()

        funcion(None, tabla, None, equipo_filtrar=equipo)

        ids_mostrados = set()
        for r in range(tabla.rowCount()):
            item = tabla.item(r, 0)
            if item is not None and item.data(load_mod.Qt.UserRole) is not None:
                ids_mostrados.add(item.data(load_mod.Qt.UserRole))
        # al menos no debe colarse el anulado -- distintas funciones guardan
        # el id en columnas/roles ligeramente distintos, así que el chequeo
        # robusto es sobre CANTIDAD de filas, no sobre el id exacto.
        assert tabla.rowCount() == 1
