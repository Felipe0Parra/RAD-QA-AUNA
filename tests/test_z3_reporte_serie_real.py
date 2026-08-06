"""Z3 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): el reporte de la
calculadora resuelve la serie REAL de la cámara desde `equipo_id`, en vez de
mostrar `Numero_serie` -- que guarda el id interno del combo (F1,
2026-07-10), no la serie física grabada en el equipo. Antes, el PDF
mostraba ese id bajo la fila "Numero_serie" como si fuera la serie.

`Numero_serie` NO se reescribe en la BD (DA-02/DA-28, no tocar históricos)
-- el arreglo es en el REPORTE, así que corrige también los registros ya
guardados sin necesidad de ninguna migración de datos.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from models.PDF.reporte_calculadora_dos import datos_a_dataframe
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_N31010 = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                 "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (el diálogo deduce el acelerador)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestReporteSerieReal:

    def test_el_reporte_trae_la_serie_real_no_el_id(self, app, monkeypatch):
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: EQUIPO_N31010 if i == EQUIPO_N31010["id"] else None))

        datos = {"Fecha": "05/08/2026", "equipo_id": 76, "Numero_serie": "76"}
        df = datos_a_dataframe(datos)

        fila = df[df[""] == "Numero_serie"]
        assert len(fila) == 1
        assert fila["Valores"].iloc[0] == "1825"

    def test_equipo_id_nulo_omite_la_fila_sin_reventar(self, app):
        datos = {"Fecha": "09/04/2026", "equipo_id": None, "Numero_serie": None}

        df = datos_a_dataframe(datos)  # no debe lanzar

        assert (df[""] == "Numero_serie").sum() == 0

    def test_equipo_id_no_encontrado_en_el_catalogo_omite_la_fila(self, app, monkeypatch):
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_por_id", staticmethod(lambda i: None))

        datos = {"Fecha": "05/08/2026", "equipo_id": 999, "Numero_serie": "999"}
        df = datos_a_dataframe(datos)  # no debe lanzar

        assert (df[""] == "Numero_serie").sum() == 0

    def test_no_modifica_el_dict_original(self, app, monkeypatch):
        """datos_a_dataframe no debe mutar el dict que también usa
        guardar_datos -- confirma dict(datos) en la implementación."""
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: EQUIPO_N31010 if i == EQUIPO_N31010["id"] else None))

        datos = {"Fecha": "05/08/2026", "equipo_id": 76, "Numero_serie": "76"}
        datos_a_dataframe(datos)

        assert datos["Numero_serie"] == "76"  # sigue siendo el id -- no se reescribió


class TestCargaPorEquipoId:
    """El otro lado del mismo cambio: cargar_datos_desde_db restaura el
    combo por equipo_id (fuente autoritativa), con Numero_serie como
    fallback solo para registros anteriores a B3."""

    @pytest.fixture
    def dialogo_factory(self, app, monkeypatch, tmp_path):
        ruta = str(tmp_path / "test.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_modelos_unicos",
            staticmethod(lambda: [{"model": EQUIPO_N31010["model"],
                                  "equip_type": EQUIPO_N31010["equip_type"]}]))
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_series_por_modelo",
            staticmethod(lambda m: [EQUIPO_N31010] if m == EQUIPO_N31010["model"] else []))
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: EQUIPO_N31010 if i == EQUIPO_N31010["id"] else None))
        for tipo in ("information", "warning", "critical"):
            monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(dialogs_mod, "generar_reporte_calibracion", lambda **kw: None)

        def _crear():
            return DialogCalculadoraDosis(energias=[], parent=VentanaIX())

        return _crear

    def test_carga_por_equipo_id_restaura_la_misma_seleccion(self, dialogo_factory):
        original = dialogo_factory()
        idx = original.combo_modelos.findData(EQUIPO_N31010["model"])
        original.combo_modelos.setCurrentIndex(idx)
        original.combo_series.setCurrentIndex(1)
        assert original.equipo_id == EQUIPO_N31010["id"]

        cargado = dialogo_factory()
        # Modelo_equipo es obligatorio (_CAMPOS_SIEMPRE_REQUERIDOS): sin él
        # combo_modelos nunca dispara on_modelo_cambiado, combo_series nace
        # vacío, y equipo_id/Numero_serie no tendrían nada que seleccionar
        # -- un dict sin Modelo_equipo no puede venir de un guardado real.
        datos_bd = {"Acelerador": cargado.acelerador_actual,
                   "Modelo_equipo": EQUIPO_N31010["model"],
                   "equipo_id": EQUIPO_N31010["id"], "Numero_serie": str(EQUIPO_N31010["id"])}
        cargado.cargar_datos_desde_db(datos_bd)

        assert cargado.equipo_id == EQUIPO_N31010["id"]
        assert cargado.combo_series.currentData() == EQUIPO_N31010["id"]

    def test_registro_antiguo_sin_equipo_id_usa_numero_serie_como_fallback(self, dialogo_factory):
        cargado = dialogo_factory()
        datos_bd = {"Acelerador": cargado.acelerador_actual,
                   "Modelo_equipo": EQUIPO_N31010["model"],
                   "equipo_id": None, "Numero_serie": str(EQUIPO_N31010["id"])}
        cargado.cargar_datos_desde_db(datos_bd)  # sin equipo_id -- usa Numero_serie

        assert cargado.combo_series.currentData() == EQUIPO_N31010["id"]


class TestZ3NoTocaDatos:

    def test_ninguna_fila_se_modifica(self, app, monkeypatch, tmp_path):
        """El arreglo es de LECTURA (reporte): datos_a_dataframe solo hace
        un SELECT (EquiposService.obtener_por_id) -- confirma sobre una BD
        temporal real que ni `equipos` ni `calculadora_dosimetrica` cambian
        una sola fila ni un solo valor."""
        ruta = str(tmp_path / "test.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        conexion = Conexion()
        conexion.con.execute(
            "INSERT INTO equipos (id, equip_type, model, serie, activo) "
            "VALUES (76, 'Cámara de ionización', 'N31010', '1825', 1)")
        conexion.con.execute(
            "INSERT INTO calculadora_dosimetrica (id, Fecha, equipo_id, Numero_serie) "
            "VALUES (1, '05/08/2026', 76, '76')")
        conexion.con.commit()

        antes_equipos = list(conexion.con.execute("SELECT * FROM equipos"))
        antes_calc = list(conexion.con.execute("SELECT * FROM calculadora_dosimetrica"))
        conexion.con.close()
        Conexion._instance = None

        datos = {"Fecha": "05/08/2026", "equipo_id": 76, "Numero_serie": "76"}
        datos_a_dataframe(datos)

        con = sqlite3.connect(ruta)
        despues_equipos = list(con.execute("SELECT * FROM equipos"))
        despues_calc = list(con.execute("SELECT * FROM calculadora_dosimetrica"))
        con.close()

        assert antes_equipos == despues_equipos
        assert antes_calc == despues_calc
