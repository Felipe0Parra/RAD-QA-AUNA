"""H8 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md, Fase 4 -- "que no vuelva a
pasar"): tripwire de clase, en el espíritu de C3/B4. Los cuatro síntomas del
handoff (filas 446-449) son UN SOLO defecto -- "estado de UI que se guarda y
nadie limpia" -- así que en vez de volver a probar cada síntoma por
separado, este archivo declara el CENSO completo del estado de la prueba de
imagen del diario y falla si, tras rotar a un día sin registro, cualquiera
de sus piezas conserva contenido del día anterior.

`ATRIBUTOS_ESTADO_IMAGEN` es el contrato explícito: si mañana alguien agrega
una pieza nueva de estado de imagen (otro QLabel, otro buffer, lo que sea),
agregarla aquí y ver este test ponerse rojo es la señal de que también hay
que agregarla a `resetear_imagen_ui`/`cargar_dailytest_desde_db` -- exactamente
la garantía que faltaba cuando se escribió `self.archivo` (H1) sin tocar
este test.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"

# El censo explícito -- H1 lo dejó así: self.archivo (el BLOB/ruta que
# add_info persiste) y self.resultado_label (la fuente de guardar_datos())
# son atributos simples; la figura del canvas se comprueba aparte porque su
# "vacío" es `figure.axes == []`, no `is None`.
ATRIBUTOS_ESTADO_IMAGEN = ["archivo", "imagen_path"]


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


def _poblar_estado_de_imagen(d, tmp_path):
    archivo_falso = str(tmp_path / "placa.jpg")
    open(archivo_falso, "wb").close()
    d.archivo = archivo_falso
    d.imagen_path = archivo_falso
    d.figure.add_subplot(111).plot([1, 2, 3])
    d.canvas.draw()
    d.mostrar_texto(["Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])


class TestH8NingunEstadoDeImagenSobreviveARotarDeDia:
    def test_censo_completo_queda_limpio_al_rotar_a_dia_sin_registro(
            self, app, bd_temporal, tmp_path):
        d = PruebaDiariaBraq(_UsuarioFalso())
        _poblar_estado_de_imagen(d, tmp_path)
        assert d.guardar_datos() != ("", None, None, "", None, None), (
            "precondición: debe haber algo real que perder")

        d.date_box.setDate(QDate(2026, 9, 9))  # día sin registro

        for atributo in ATRIBUTOS_ESTADO_IMAGEN:
            assert getattr(d, atributo) is None, (
                f"{atributo!r} sobrevivió a un cambio de día -- estado de "
                f"UI que se guarda y nadie limpia, la clase de defecto de "
                f"todo este plan")
        assert d.resultado_label.text() == "", (
            "resultado_label sobrevivió a un cambio de día")
        assert d.figure.axes == [], (
            "la figura del canvas sobrevivió a un cambio de día")
        assert d.guardar_datos() == ("", None, None, "", None, None), (
            "intuición de garantía de H8: guardar_datos() inmediatamente "
            "después de rotar de día no puede devolver nada del día "
            "anterior, sea cual sea la variable")

    def test_censo_completo_queda_limpio_al_rotar_a_dia_con_registro_sin_imagen(
            self, app, bd_temporal, tmp_path):
        """La otra rama (H2): un día CON registro pero SIN película -- el
        caso exacto que produjo la fila 447 del handoff."""
        conexion = Conexion()
        conexion.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, pelicula, activo) VALUES "
            "('2026-09-10', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
            "1.0,1.0,1.0,1.0, '', NULL, 1)")
        conexion.con.commit()

        d = PruebaDiariaBraq(_UsuarioFalso())
        _poblar_estado_de_imagen(d, tmp_path)

        d.date_box.setDate(QDate(2026, 9, 10))  # registro real, sin imagen

        for atributo in ATRIBUTOS_ESTADO_IMAGEN:
            assert getattr(d, atributo) is None, (
                f"{atributo!r} sobrevivió a un día con registro pero sin "
                f"imagen -- exactamente la fila 447 del handoff")
        assert d.resultado_label.text() == ""
        assert d.figure.axes == []
