"""P3 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase B): si el físico abre un
día, no re-analiza y guarda, `guardar_datos()` lee `resultado_label`
(restaurado por `G1`) y reescribe los mismos 6 números -- pero con `P1`
también debe reescribir los MISMOS parámetros (`umbral_relativo`/
`distancia_minima`), no los que el spin muestre en ese momento. Sin `P3`,
un "Añadir" sin volver a analizar habría escrito `1.0`/`40` (el valor de
fábrica del spin, ni siquiera creado hasta este cambio) ENCIMA de unos
parámetros guardados distintos -- la fila quedaría auto-inconsistente:
los parámetros no producirían los 6 números que tiene al lado. Mismo daño
que la fila 447 de DP-63, trasladado a las columnas nuevas.

`_reponer_parametros_analisis` (braquiterapia.py) hace esto con
`blockSignals` -- sin él, `spin_umbral.valueChanged`/`spin_dist.
valueChanged` (conectados a `analizar_imagen_con_debouncing`) lanzarían
un re-análisis real en cada cambio de día."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2020-01-01 00:00:00"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


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
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _llenar_campos_numericos(d, valor="1.0"):
    for campo in ("line_1_rep_act_ci", "line_1_exp_act_ci",
                  "line_1_cyc_dummy", "line_1_cyc_rad"):
        getattr(d, campo).setText(valor)


def _crear_jpeg_real(tmp_path, nombre="placa.jpg"):
    from PIL import Image
    ruta = str(tmp_path / nombre)
    Image.new("RGB", (37, 51), color=(200, 10, 10)).save(ruta, format="JPEG")
    return ruta


def _fake_analizar_lineas(canvas_axes=3):
    def _fake(**kwargs):
        canvas = kwargs.get("canvas")
        if canvas is not None:
            canvas.figure.clear()
            for i in range(canvas_axes):
                canvas.figure.add_subplot(canvas_axes, 1, i + 1)
            canvas.draw()
        return "TEXTO_FALSO"
    return _fake


def _leer_fila_completa(d, patron_fecha):
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(
        "SELECT distancias, promedio, desviacion, desplazamientos, "
        "promedio_des, desviacion_des, umbral_relativo, distancia_minima "
        "FROM braqui WHERE date LIKE :p ORDER BY id DESC LIMIT 1")
    query.bindValue(":p", patron_fecha)
    query.exec()
    assert query.next(), f"no hay fila para {patron_fecha!r}"
    return tuple(query.value(i) for i in range(8))


class TestReponerSpinsNoDisparaAnalisis:

    def test_cargar_el_registro_no_reanaliza(
            self, app, bd_temporal, monkeypatch, tmp_path):
        ruta_jpeg = _crear_jpeg_real(tmp_path)

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 8, 1))
        _llenar_campos_numericos(d)
        d.archivo = ruta_jpeg
        d.imagen_path = ruta_jpeg
        d._crear_interfaz_parametros()
        d.spin_umbral.setValue(1.4)
        d.spin_dist.setValue(55)
        d.mostrar_texto([
            "Distancias entre líneas(mm): [10.03, 10.16, 10.03]",
            "Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])
        d.ordenar_botones('braqui', False, "Diario")

        monkeypatch.setattr(
            "ui.paginasControles.PruebasDiarias.braquiterapia.analizar_lineas",
            _fake_analizar_lineas())
        llamadas = []
        d2 = PruebaDiariaBraq(_UsuarioFalso())
        monkeypatch.setattr(
            d2, "analizar_imagen_con_debouncing",
            lambda: llamadas.append("debouncing"))
        monkeypatch.setattr(
            d2, "analizar_imagen", lambda: llamadas.append("analizar") or None)

        d2.date_box.setDate(QDate(2026, 8, 1))

        assert llamadas == [], (
            "reponer los spins con blockSignals no debe disparar ningún "
            "re-análisis")
        assert d2.spin_umbral.value() == pytest.approx(1.4)
        assert d2.spin_dist.value() == 55


class TestRoundTripReguardarSinReanalizar:

    def test_guardar_cambiar_de_dia_volver_y_guardar_sin_tocar_nada(
            self, app, bd_temporal, monkeypatch, tmp_path):
        ruta_jpeg = _crear_jpeg_real(tmp_path)
        monkeypatch.setattr(
            "ui.paginasControles.PruebasDiarias.braquiterapia.analizar_lineas",
            _fake_analizar_lineas())

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 8, 2))
        _llenar_campos_numericos(d)
        d.archivo = ruta_jpeg
        d.imagen_path = ruta_jpeg
        d._crear_interfaz_parametros()
        d.spin_umbral.setValue(1.4)
        d.spin_dist.setValue(55)
        d.mostrar_texto([
            "Distancias entre líneas(mm): [10.03, 10.16, 10.03]",
            "Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])
        d.ordenar_botones('braqui', False, "Diario")

        fila_original = _leer_fila_completa(d, "2026-08-02%")

        # Cambiar de día y volver -- simula "abrir el control a corregir
        # otra cosa" sin tocar el análisis de imagen ni sus parámetros.
        d.date_box.setDate(QDate(2026, 8, 3))
        d.date_box.setDate(QDate(2026, 8, 2))

        # Reguardar SIN tocar nada del análisis.
        d.ordenar_botones('braqui', False, "Diario")

        fila_reguardada = _leer_fila_completa(d, "2026-08-02%")

        assert fila_reguardada == fila_original, (
            "reguardar sin volver a analizar debe ser un round-trip "
            "exacto de las 8 columnas (6 del análisis + 2 de P1)")
