"""H4+H5 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): el panel de imagen del
diario de braquiterapia tenía DOS defectos del mismo origen (llamar dos
veces al mismo constructor de widgets, en dos sitios distintos).

H4 -- el botón "Guardar" del panel de imagen (`_crear_parametros`) llamaba a
`guardar_datos()`, un extractor puro que no escribe nada en la BD: el físico
lo pulsaba y "no pasaba nada porque, literalmente, no pasaba nada". Se
retira: el único guardado del diario es "Añadir".

H5 -- `_cargar_imagen_pelicula` llamaba a `self._crear_parametros()` Y LUEGO
a `self._crear_interfaz_parametros()` (que YA llama a `_crear_parametros()`
internamente) -- `_crear_parametros()` corría dos veces, cada una
instanciando sus propios `QPushButton` y reasignando `self.analizar`, así
que el primer par quedaba huérfano pero VISIBLE ("con los botones
duplicados le di analizar").

Protocolo del plan: cargar un registro con imagen DOS veces seguidas y
contar `findChildren(QPushButton)` con texto "Analizar" (debe ser
exactamente 1) y "Guardar" (debe ser exactamente 0).
"""
import os
from io import BytesIO

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton

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
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, pelicula, activo) VALUES "
        "('2026-03-10', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "1.0,1.0,1.0,1.0, '', ?, 1)",
        (_png_1x1(),))
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, pelicula, activo) VALUES "
        "('2026-03-11', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "1.0,1.0,1.0,1.0, '', ?, 1)",
        (_png_1x1(),))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class TestH4H5UnSoloAnalizarYNingunGuardar:
    def test_dos_cargas_de_imagen_seguidas_no_duplican_ni_botones_muertos(
            self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.date_box.setDate(QDate(2026, 3, 10))   # 1ª carga con imagen
        d.date_box.setDate(QDate(2026, 3, 11))   # 2ª carga con imagen

        analizar = [b for b in d.findChildren(QPushButton)
                    if b.text() == "Analizar"]
        guardar = [b for b in d.findChildren(QPushButton)
                   if b.text() == "Guardar"]
        assert len(analizar) == 1, (
            f"H5: debe haber exactamente 1 botón 'Analizar' vivo en el "
            f"panel, hay {len(analizar)} (huérfanos de una segunda "
            f"creación)")
        assert len(guardar) == 0, (
            f"H4: el panel de imagen no debe tener ningún botón 'Guardar' "
            f"-- el único guardado del diario es 'Añadir', hay "
            f"{len(guardar)}")

    def test_analizar_sigue_funcionando_tras_la_carga(self, app, bd_temporal):
        """H1→H4 (acople §4.1): retirar el botón no debe dejar un panel que
        analiza y no guarda -- el flujo real (Analizar -> Añadir) debe
        seguir entregando los 6 números a la BD."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 3, 10))

        d.mostrar_texto(["Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])

        assert d.guardar_datos() != ("", None, None, "", None, None), (
            "tras 'analizar' (simulado), guardar_datos() debe seguir "
            "devolviendo los números -- el botón retirado no era el único "
            "camino hacia self.resultado_label")
