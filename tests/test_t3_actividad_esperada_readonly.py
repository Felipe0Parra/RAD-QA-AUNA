"""T3 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md §Fase 0): "el campo de
actividad esperada: solo lectura".

Decisión del físico (28-08): *"no nos pongamos a agregar funciones
inventadas solo porque 'puede fallar'"* -- se retiran las tres opciones de
`G7` (readOnly / editar auditado / columna de origen) y queda solo la
primera, sin adornos. `DP-66` midió que el campo era editable
(`readOnly=False`) y que eso ya se usó para teclear a mano la actividad
esperada de los 4 controles del 27-08 -- convirtiendo la tolerancia (que
compara la actividad esperada contra la reportada) en una comparación
contra sí misma.

`line_1_exp_act_ci` lo llena ÚNICAMENTE el cálculo (`actividad_braq_
automatica`, día nuevo) o la propia BD (T4/T8, al abrir un registro
guardado) -- nunca el teclado."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"


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
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class TestT3CampoDeSoloLectura:
    def test_line_1_exp_act_ci_es_readonly(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        assert d.line_1_exp_act_ci.isReadOnly(), (
            "DP-66: el campo era editable y eso ya se usó para teclear la "
            "actividad esperada a mano en 4 controles reales")

    def test_valor_guardado_es_siempre_el_calculado(self, app, bd_temporal):
        """El único camino disponible con el campo readOnly es dejar que
        el cálculo lo llene -- lo que se guarda en `tol_exp_act` debe ser
        EXACTAMENTE ese valor, bit a bit."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 7, 20), QTime(14, 0, 0)))

        valor_calculado = d.line_1_exp_act_ci.text()
        assert valor_calculado, "precondición: debe haber un cálculo con fuente registrada"

        d.line_1_rep_act_ci.setText("1.0")
        d.line_1_cyc_dummy.setText("10")
        d.line_1_cyc_rad.setText("10")
        d.ordenar_botones('braqui', False, "Diario")

        db = d.opeenDatabase()
        query = QSqlQuery(db)
        query.prepare(
            "SELECT tol_exp_act FROM braqui WHERE DATE(date) = :f ORDER BY id DESC LIMIT 1")
        query.bindValue(":f", "2026-07-20")
        query.exec()
        assert query.next()
        assert str(query.value(0)) == valor_calculado
