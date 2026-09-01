"""H2 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): `cargar_dailytest_desde_db`
(`braquiterapia.py:339`) solo limpiaba el estado de imagen en la rama SIN
registro (usaba `_limpiar_canvas()`, que ni siquiera es la limpieza completa
de H1). Un día CON registro pero SIN película se quedaba con la imagen y el
análisis del día anterior -- el caso exacto que produjo la fila 447 del
handoff (2026-08-31 con los números de medición del 28, sin película).

"Limpiar siempre, restaurar después": las dos ramas de `cargar_dailytest_
desde_db` ahora llaman a `resetear_imagen_ui()` (H1) incondicionalmente
antes de decidir si hay imagen que reponer. Y cuando SÍ hay imagen,
`_cargar_imagen_pelicula` ahora también repone `self.archivo` (defecto c:
antes solo lo asignaba la subida manual, nunca cargar un registro) -- si no,
reguardar sin volver a subir el archivo perdía la película ya guardada.

Protocolo del plan: tres saltos sobre BD temporal -- (día con imagen → día
sin registro), (día con imagen → día con registro sin imagen), (día sin
registro → día con imagen). En los tres, lo que queda en pantalla debe ser
exactamente lo del día de destino.
Intuición de garantía: `self.archivo` después de aterrizar en un día es
siempre o `None` o la película DE ESE día -- nunca la del día anterior.
"""
import os
from io import BytesIO

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"


def _png_1x1():
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (1, 1), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


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

    imagen_28 = _png_1x1()
    # DIA_CON_IMAGEN (28-08): pelicula + análisis guardados
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, pelicula, distancias, promedio, desviacion, "
        "desplazamientos, promedio_des, desviacion_des, activo) VALUES "
        "('2026-03-10', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "1.0,1.0,1.0,1.0, '', ?, '[10.03, 10.16]', 10.01, 0.11, "
        "'[1.0, 2.0]', 1.5, 0.2, 1)",
        (imagen_28,))
    # DIA_SIN_IMAGEN (29-08): registro real, pelicula NULL
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, pelicula, activo) VALUES "
        "('2026-03-11', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "1.0,1.0,1.0,1.0, '', NULL, 1)")
    conexion.con.commit()
    yield ruta, imagen_28
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _texto_resultado(d):
    """`resultado_label` se crea tarde (solo tras un análisis real) -- si
    nunca se creó, no hay ningún número que mostrar, lo que también cuenta
    como "vacío" para este propósito."""
    return d.resultado_label.text() if hasattr(d, "resultado_label") else ""


class TestH2LimpiarSiempreRestaurarDespues:
    def test_dia_con_imagen_a_dia_sin_registro(self, app, bd_temporal):
        _, imagen_28 = bd_temporal
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 3, 10))
        assert d.archivo is not None, "precondición: el 28 debe traer imagen"
        d.mostrar_texto(["Promedio = 10.01 mm"])  # simula un análisis real

        d.date_box.setDate(QDate(2026, 3, 20))  # sin registro

        assert d.archivo is None, (
            "aterrizar en un día sin registro debe dejar self.archivo en "
            "None, nunca la película del día anterior")
        assert d.imagen_path is None
        assert _texto_resultado(d) == ""

    def test_dia_con_imagen_a_dia_con_registro_sin_imagen(self, app, bd_temporal):
        """El caso exacto de la fila 447: día de destino CON registro pero
        SIN película -- antes solo se limpiaba en la rama sin registro."""
        _, imagen_28 = bd_temporal
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 3, 10))
        assert d.archivo is not None
        d.mostrar_texto(["Promedio = 10.01 mm"])  # análisis del día 10

        d.date_box.setDate(QDate(2026, 3, 11))  # registro real, sin imagen

        assert d.archivo is None, (
            "la fila 447 del handoff: un día CON registro pero SIN imagen "
            "no debe quedarse con la película del día anterior")
        assert d.imagen_path is None
        assert _texto_resultado(d) == "", (
            "el análisis del día 10 no debe sobrevivir al aterrizar en el "
            "día 11 -- si sobreviviera, un 'Añadir' sin re-analizar "
            "guardaría el análisis del 10 bajo la fecha del 11")
        assert d.line_1_rep_act_ci.text() == "1", (
            "lo que SÍ pertenece al día 29 (sus propios campos numéricos) "
            "debe seguir cargándose con normalidad")

    def test_dia_sin_registro_a_dia_con_imagen(self, app, bd_temporal):
        """Intuición de garantía de H2: self.archivo, al aterrizar en un día
        con imagen, es la película DE ESE día -- nunca None por descuido ni
        la de otro día."""
        _, imagen_28 = bd_temporal
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 3, 20))  # sin registro
        assert d.archivo is None

        d.date_box.setDate(QDate(2026, 3, 10))  # con imagen

        assert d.archivo is not None, (
            "defecto (c) del plan: cargar un registro con película nunca "
            "reponía self.archivo, así que reguardar sin volver a subir el "
            "archivo perdía la imagen ya guardada (filas 448/449)")
        with open(d.archivo, "rb") as f:
            assert f.read() == imagen_28, (
                "self.archivo debe apuntar a los mismos bytes que la "
                "película guardada -- un resave debe ser un round-trip "
                "exacto, no una recompresión")
        assert d.imagen_path == d.archivo
