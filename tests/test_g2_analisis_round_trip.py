"""G2 (PLAN_BRAQUI_ANALISIS_PERSISTE_28-08.md §Fase 1): "el test de
round-trip: guardar no puede perder dato".

Es el test que habría cazado `DP-64` el 28-08 si se hubiera escrito en vez
de `assert filas` (ver `G3`/`CLAUDE.md` 1-bis): sembrar una fila con los 6
valores del análisis de imagen, cargar el día, guardar SIN re-analizar, y
exigir que las 6 columnas sigan siendo EXACTAMENTE las sembradas.

Antes de `G1`, `self.resultado_label` no se repoblaba al cargar un
registro -- un "Añadir" sin volver a pulsar "Analizar" escribía NULL sobre
las 6 columnas, en silencio, mostrando "Datos insertados correctamente"."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"

DISTANCIAS = "[10.03, 10.16]"
PROMEDIO = 10.1
DESVIACION = 0.07
DESPLAZAMIENTOS = "[1.0, 2.0]"
PROMEDIO_DES = 1.5
DESVIACION_DES = 0.5


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "critical", "warning"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.Yes))


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
    conexion.con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
        "certificado, fecha_cer, intensidad, conversion, activo) "
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, 10.0, "
        "1.0, 1)",
        (FECHA_FUENTE, FECHA_FUENTE))
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, distancias, promedio, desviacion, desplazamientos, "
        "promedio_des, desviacion_des, activo) VALUES "
        "('2026-04-15', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "3.0,3.0,10.0,10.0, '', ?, ?, ?, ?, ?, ?, 1)",
        (DISTANCIAS, PROMEDIO, DESVIACION, DESPLAZAMIENTOS, PROMEDIO_DES, DESVIACION_DES))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _fila_braqui(d, fecha_like):
    # [medido] (test_h6_hora_se_guarda.py::_filas_braqui): una conexión
    # sqlite3 aparte, mientras la pantalla mantiene abierta la suya
    # (QSqlDatabase) y `add_info` acaba de escribir por una tercera
    # (`Conexion().conectar()`, nunca cerrada -- DP-67), da "disk I/O
    # error" en este sandbox. Se lee por la MISMA conexión que usa la
    # pantalla, igual que hace H6.
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(
        "SELECT distancias, promedio, desviacion, desplazamientos, "
        "promedio_des, desviacion_des, activo FROM braqui "
        "WHERE date LIKE :p ORDER BY id DESC LIMIT 1")
    query.bindValue(":p", fecha_like)
    query.exec()
    if not query.next():
        return None
    return tuple(query.value(i) for i in range(7))


class TestG2RoundTripSinReanalizar:
    def test_cargar_y_reguardar_sin_reanalizar_preserva_las_6_columnas(
            self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.date_box.setDate(QDate(2026, 4, 15))  # carga el día sembrado

        assert hasattr(d, "resultado_label") and d.resultado_label is not None, (
            "G1: cargar un día con análisis guardado debe repoblar "
            "resultado_label, igual que un análisis fresco")

        # "Añadir" SIN volver a pulsar "Analizar" -- el escenario exacto de DP-64
        d.ordenar_botones('braqui', False, "Diario")

        fila = _fila_braqui(d, "2026-04-15%")
        assert fila is not None, "el reguardado no debe perder la fila"
        distancias, promedio, desviacion, desplazamientos, promedio_des, desviacion_des, activo = fila

        assert distancias == DISTANCIAS
        assert promedio == pytest.approx(PROMEDIO)
        assert desviacion == pytest.approx(DESVIACION)
        assert desplazamientos == DESPLAZAMIENTOS
        assert promedio_des == pytest.approx(PROMEDIO_DES)
        assert desviacion_des == pytest.approx(DESVIACION_DES)

    def test_sin_reanalizar_el_veredicto_no_es_el_defecto_de_dp64(
            self, app, bd_temporal):
        """Reproduce literalmente la tabla de DP-64 §1: antes de G1, un
        reguardado sin reanalizar escribía `('', None, None, '', None,
        None)` sobre las 6 columnas -- este test falla si eso vuelve a
        pasar. [medido] `QSqlQuery.value()` devuelve '' (no None) para un
        NULL de SQLite sin importar el tipo de columna, así que la firma
        del defecto leída por este camino es seis cadenas vacías."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 4, 15))
        d.ordenar_botones('braqui', False, "Diario")

        fila = _fila_braqui(d, "2026-04-15%")
        distancias, promedio, desviacion, desplazamientos, promedio_des, desviacion_des, activo = fila
        defecto_dp64 = (distancias, promedio, desviacion, desplazamientos, promedio_des, desviacion_des)
        assert defecto_dp64 != ("", "", "", "", "", ""), (
            "DP-64 revivió: reguardar sin reanalizar volvió a poner NULL "
            "sobre el análisis guardado")
