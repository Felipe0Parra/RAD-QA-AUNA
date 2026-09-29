"""L.2 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, segunda ronda -- versión
con "exactitud = pendiente", decisión del físico): lo que se guarda de la
linealidad sale de las medidas que se guardan.

CAUSA (§1.9): (1) una fila vacía en medio desplazaba todo lo que venía
después al tiempo de parada anterior (`extraer_datos_medidas` saltaba la
fila en vez de dejar `None` en su lugar); (2) la exactitud y el tiempo de
tránsito archivados salían del último "Ok" (`self.r2`/`self.b`), no de las
medidas que `guardar_linealidad` estaba a punto de guardar.

Este archivo prueba `services/linealidad_fuente.py` (la función pura) y su
uso real en `extraer_datos_medidas`/`guardar_linealidad`.
"""
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QLineEdit, QTableWidget, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad
from services.linealidad_fuente import (
    TIEMPOS_PARADA, ajuste_linealidad, DatosInsuficientes, reproducibilidad,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(braq_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(braq_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(braq_mod, "mostrar_db_linealidad", lambda *a, **k: None)


class _UsuarioFalso:
    def __init__(self, nombre="Físico de Prueba"):
        self._nombre = nombre


def _linealidad_pelada():
    obj = Linealidad.__new__(Linealidad)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 8, 4))

    for nombre in ("modelo", "serie_cp", "modelo_elec", "serie_ele"):
        combo = QComboBox()
        combo.addItem("valor")
        setattr(obj, nombre, combo)

    for nombre, valor in (
        ("calibracion", "464700"), ("electrometro", "1.0"),
        ("q_est", "1.0"), ("t_integrado", "60.0"), ("i_est", "1.0"),
        ("repro", "0.5"),
        ("repro_med1", "1.0"), ("repro_med2", "1.0"), ("repro_med3", "1.0"),
        ("repro_med4", "1.0"), ("repro_med5", "1.0"), ("repro_prom", "1.0"),
    ):
        setattr(obj, nombre, QLineEdit(valor))

    obj.exactitud = QLineEdit()
    obj.tiempo_transito = QLineEdit()
    # Valores de un "Ok" DE OTRAS medidas -- deliberadamente distintos de
    # lo que las filas reales darán, para probar que guardar_linealidad
    # ya no los usa.
    obj.r2 = 1.0
    obj.b = 0.30
    obj.tabla_resultados = QTableWidget()
    return obj


def _fila(v1="", v2=""):
    """Una fila de `medidas_lienalidad` tal como la deja
    `generar_tabla_medidas`: [tiempo(RO), Q1, Q2, Qprom(RO), t_efectivo(RO)].
    El tiempo de parada no se lee de `fila[0]` (se toma de
    `TIEMPOS_PARADA[i]`), así que su texto no importa aquí."""
    return [QLineEdit("-"), QLineEdit(str(v1)), QLineEdit(str(v2)),
            QLineEdit("-"), QLineEdit("-")]


# Q1/Q2 reales, EXCEPTO la fila 3 (0.8 s), que llega vacía -- el caso del
# plan (a). Con i_est=1.0, tiempo_efectivo = promedio(Q1,Q2).
MEDIDAS_CON_HUECO = {
    0: (1.0, 1.2), 1: (2.0, 2.2), 2: (3.0, 3.2),
    # 3: vacía (0.8 s)
    4: (5.0, 5.2), 5: (6.0, 6.2), 6: (7.0, 7.2),
    7: (8.0, 8.2), 8: (9.0, 9.2), 9: (10.0, 10.2),
}


def _con_medidas(obj, medidas):
    obj.medidas_lienalidad = [
        _fila(*medidas[i]) if i in medidas else _fila()
        for i in range(10)
    ]
    return obj


# ---------------------------------------------------------------------------
# services/linealidad_fuente.py -- la función pura, aislada.
# ---------------------------------------------------------------------------

class TestAjusteLinealidadPuro:
    def test_ajusta_solo_los_pares_completos_misma_aritmetica_de_siempre(self):
        tp = [0.1, 0.2, None, 0.4]
        te = [1.0, 2.0, None, 4.0]
        pendiente, intercepto = ajuste_linealidad(tp, te)

        x = np.array([0.1, 0.2, 0.4])
        y = np.array([1.0, 2.0, 4.0])
        m_esperado, b_esperado = np.polyfit(x, y, 1)
        assert pendiente == pytest.approx(m_esperado)
        assert intercepto == pytest.approx(b_esperado)

    def test_menos_de_2_pares_da_datosinsuficientes(self):
        with pytest.raises(DatosInsuficientes):
            ajuste_linealidad([0.1, None, None], [1.0, None, None])

    def test_cero_pares_da_datosinsuficientes(self):
        with pytest.raises(DatosInsuficientes):
            ajuste_linealidad([None, None], [None, None])

    def test_reproducibilidad_es_100_menos_desviacion_estandar(self):
        valores = [1.0, 1.1, 0.9, 1.05, 0.95]
        assert reproducibilidad(valores) == pytest.approx(100 - np.std(valores, ddof=1))


# ---------------------------------------------------------------------------
# (a) Una fila vacía en medio NO desplaza lo que viene después.
# ---------------------------------------------------------------------------

class TestFilaVaciaNoDesplaza:
    def test_extraer_datos_medidas_deja_none_en_su_puesto(self, app, bd_temporal):
        obj = _con_medidas(_linealidad_pelada(), MEDIDAS_CON_HUECO)

        tp, q1, q2, qprom, te = obj.extraer_datos_medidas()

        assert len(tp) == len(q1) == len(q2) == len(qprom) == len(te) == 10
        assert q1[3] is None, "la fila 0.8 s (índice 3) debe quedar vacía"
        assert q2[3] is None
        # La fila de 1.6 s (índice 4) NO se corrió -- sigue siendo SU
        # propia carga, no la que faltó en 0.8 s.
        assert q1[4] == 5.0
        assert q2[4] == 5.2

    def test_guardar_archiva_lin_q1_3_nulo_y_lin_q1_4_su_propia_carga(self, app, bd_temporal):
        obj = _con_medidas(_linealidad_pelada(), MEDIDAS_CON_HUECO)

        obj.guardar_linealidad()

        con = Conexion().conectar()
        fila = con.execute(
            "SELECT lin_q1_3, lin_q1_4 FROM LinealidadBraquiterapia").fetchone()
        con.close()
        assert fila == (None, 5.0), (
            f"lin_q1_3 debía quedar NULL y lin_q1_4 debía ser 5.0 (su "
            f"propia carga, la de 1.6 s) -- salió {fila}")


# ---------------------------------------------------------------------------
# (b) Exactitud/tránsito salen de lo que se guarda, no del último "Ok".
# ---------------------------------------------------------------------------

class TestExactitudYTransitoSonLosDeLoGuardado:
    def test_guardar_ignora_self_r2_y_self_b_y_calcula_de_nuevo(self, app, bd_temporal):
        obj = _con_medidas(_linealidad_pelada(), MEDIDAS_CON_HUECO)
        # self.r2/self.b (fijados en el fixture, 1.0/0.30) simulan un "Ok"
        # de OTRAS medidas, nunca actualizado tras el hueco de la fila 3.

        obj.guardar_linealidad()

        tp, q1, q2, qprom, te = obj.extraer_datos_medidas()
        pendiente_esperada, intercepto_esperado = ajuste_linealidad(tp, te)

        con = Conexion().conectar()
        exactitud, tiempo_transito = con.execute(
            "SELECT exactitud, tiempo_transito FROM LinealidadBraquiterapia").fetchone()
        con.close()

        assert exactitud == pytest.approx(round(pendiente_esperada, 5))
        assert tiempo_transito == pytest.approx(round(intercepto_esperado, 2))
        # Y NO son los del "Ok" viejo.
        assert exactitud != 1.0
        assert tiempo_transito != 0.30

    def test_la_pantalla_muestra_lo_mismo_que_se_guarda(self, app, bd_temporal):
        obj = _con_medidas(_linealidad_pelada(), MEDIDAS_CON_HUECO)

        obj.guardar_linealidad()

        con = Conexion().conectar()
        exactitud, tiempo_transito = con.execute(
            "SELECT exactitud, tiempo_transito FROM LinealidadBraquiterapia").fetchone()
        con.close()

        assert float(obj.exactitud.text()) == pytest.approx(exactitud, abs=0.01)
        assert float(obj.tiempo_transito.text()) == pytest.approx(tiempo_transito, abs=0.01)

    def test_menos_de_2_medidas_avisa_y_no_guarda(self, app, bd_temporal, monkeypatch):
        avisos = []
        monkeypatch.setattr(braq_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: avisos.append(a)))
        obj = _con_medidas(_linealidad_pelada(), {0: (1.0, 1.2)})  # 1 sola fila

        obj.guardar_linealidad()

        con = Conexion().conectar()
        n = con.execute("SELECT COUNT(*) FROM LinealidadBraquiterapia").fetchone()[0]
        con.close()
        assert n == 0
        assert avisos, "debía avisarse 'No se ingresaron datos válidos.'"
        assert "No se ingresaron datos válidos" in avisos[0][2]


# ---------------------------------------------------------------------------
# Lo viejo sigue igual: con las 10 filas completas, el registro que se
# guarda coincide con el de siempre (misma aritmética, mismas columnas).
# ---------------------------------------------------------------------------

class TestConLasDiezFilasCompletasNoCambiaNada:
    def test_guardar_con_diez_filas_completas(self, app, bd_temporal):
        medidas = {i: (float(i + 1), float(i + 1) + 0.2) for i in range(10)}
        obj = _con_medidas(_linealidad_pelada(), medidas)

        obj.guardar_linealidad()

        con = Conexion().conectar()
        n, exactitud, tiempo_transito = con.execute(
            "SELECT COUNT(*), exactitud, tiempo_transito FROM LinealidadBraquiterapia"
        ).fetchone()
        con.close()
        assert n == 1

        tp = list(TIEMPOS_PARADA)
        te = [round((v1 + v2) / 2, 3) for v1, v2 in medidas.values()]
        pendiente_esperada, intercepto_esperado = ajuste_linealidad(tp, te)
        assert exactitud == pytest.approx(round(pendiente_esperada, 5))
        assert tiempo_transito == pytest.approx(round(intercepto_esperado, 2))
