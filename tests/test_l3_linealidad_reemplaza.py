"""L.3 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, tercera ronda): guardar la
linealidad de un día que ya tiene registro lo REEMPLAZA, como el mensual.

CAUSA (§1.9 / DP-40 / DP-136): `guardar_linealidad` hacía un `INSERT` liso
-- "HOY no existe ningún mecanismo de reemplazo para esta tabla" -- así que
cada "Guardar" sumaba un registro nuevo en vez de sustituir el vigente.

Este archivo prueba el mecanismo de reemplazo en sí (`reemplazar_bloque`,
EB1) aplicado a `LinealidadBraquiterapia`: guardar dos veces la misma
fecha deja UNA sola fila vigente (la anterior se ANULA, nunca se borra) y
la auditoría lleva dos filas `guardar` (una por guardado, ver el
`accion=ACCION_GUARDAR` explícito del `CAMBIO`); una fecha nueva no toca
ninguna otra fila; un guardado que no pasa la validación no anula nada
(invariante 4 de `reemplazar_bloque`: sin filas nuevas que insertar, no
se anula el bloque anterior).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QLineEdit, QTableWidget, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import mostrar_db_linealidad as _mostrar_db_linealidad_real
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad


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


def _linealidad_pelada(fecha=QDate(2026, 8, 4)):
    obj = Linealidad.__new__(Linealidad)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(fecha)

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
    obj.r2 = 1.0
    obj.b = 0.30
    obj.tabla_resultados = QTableWidget()
    return obj


def _con_medidas(obj, q1, q2):
    """2 medidas completas (índices 0 y 1), el resto vacío -- basta para
    pasar la validación de `ajuste_linealidad` (>=2 pares)."""
    obj.extraer_datos_medidas = lambda: (
        [0.1, 0.2], list(q1), list(q2),
        [round((a + b) / 2, 3) for a, b in zip(q1, q2)],
        [round((a + b) / 2, 3) for a, b in zip(q1, q2)])
    return obj


def _audit_log_guardar(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref FROM audit_log "
        "WHERE tabla = 'LinealidadBraquiterapia' ORDER BY id").fetchall()
    con.close()
    return filas


# ---------------------------------------------------------------------------
# (a) Guardar la misma fecha dos veces -> una sola fila vigente, la
# segunda; la primera anulada; 2 filas de auditoría 'guardar'.
# ---------------------------------------------------------------------------

class TestGuardarMismaFechaReemplazaComoElMensual:
    def test_dos_guardados_mismo_dia_dejan_una_sola_vigente(self, app, bd_temporal):
        obj1 = _con_medidas(_linealidad_pelada(), [1.0, 2.0], [1.0, 2.0])
        obj1.guardar_linealidad()

        obj2 = _con_medidas(_linealidad_pelada(), [3.0, 4.0], [3.0, 4.0])
        obj2.guardar_linealidad()

        con = Conexion().conectar()
        filas = con.execute(
            "SELECT id, activo, lin_q1_0 FROM LinealidadBraquiterapia ORDER BY id"
        ).fetchall()
        n_vigentes = con.execute(
            "SELECT COUNT(*) FROM LinealidadBraquiterapia "
            "WHERE activo IS NULL OR activo = 1").fetchone()[0]
        con.close()

        assert len(filas) == 2, "el registro anterior se ANULA, no se borra"
        assert filas[0][1] == 0, "la primera fila debe quedar anulada (activo=0)"
        assert filas[1][1] in (None, 1), "la segunda fila debe quedar vigente"
        assert filas[1][2] == 3.0, "la fila vigente debe ser la del segundo guardado"
        assert n_vigentes == 1, "solo debe quedar UNA fila vigente para esa fecha"

    def test_dos_guardados_dejan_dos_filas_de_auditoria_guardar(self, app, bd_temporal):
        obj1 = _con_medidas(_linealidad_pelada(), [1.0, 2.0], [1.0, 2.0])
        obj1.guardar_linealidad()
        obj2 = _con_medidas(_linealidad_pelada(), [3.0, 4.0], [3.0, 4.0])
        obj2.guardar_linealidad()

        filas = _audit_log_guardar(bd_temporal)
        assert len(filas) == 2, (
            "una fila de auditoría por guardado -- reemplazar_bloque la "
            "escribe en la misma transacción, ya no hay llamada aparte")
        for usuario, accion, tabla, ref in filas:
            assert usuario == "Físico de Prueba"
            assert accion == "guardar", (
                "CAMBIO: accion=ACCION_GUARDAR explícito -- conserva el "
                "verbo histórico, no pasa a 'reemplazo'")
            assert tabla == "LinealidadBraquiterapia"
        # Cada fila de auditoría referencia un `ref` (id) distinto -- el
        # de la fila que insertó, no el que anuló.
        assert filas[0][3] != filas[1][3]

    def test_tabla_lateral_muestra_una_sola_fila_de_ese_dia(self, app, bd_temporal):
        obj1 = _con_medidas(_linealidad_pelada(), [1.0, 2.0], [1.0, 2.0])
        obj1.guardar_linealidad()
        obj2 = _con_medidas(_linealidad_pelada(), [3.0, 4.0], [3.0, 4.0])
        obj2.guardar_linealidad()

        obj2.table = QTableWidget()
        _mostrar_db_linealidad_real(obj2)

        assert obj2.table.rowCount() == 1, (
            "mostrar_db_linealidad ya filtra por activo (WHERE activo IS "
            "NULL OR activo = 1) -- con la fila anterior anulada, la "
            "tabla lateral debe mostrar una sola fila de ese día")


# ---------------------------------------------------------------------------
# (b) Guardar una fecha nueva no toca ninguna otra fila.
# ---------------------------------------------------------------------------

class TestGuardarFechaNuevaNoTocaOtrasFilas:
    def test_fila_de_otro_dia_queda_byte_a_byte_igual(self, app, bd_temporal):
        obj1 = _con_medidas(_linealidad_pelada(QDate(2026, 8, 4)), [1.0, 2.0], [1.0, 2.0])
        obj1.guardar_linealidad()

        con = Conexion().conectar()
        fila_antes = con.execute(
            "SELECT * FROM LinealidadBraquiterapia WHERE id = 1").fetchone()
        con.close()

        obj2 = _con_medidas(_linealidad_pelada(QDate(2026, 8, 5)), [3.0, 4.0], [3.0, 4.0])
        obj2.guardar_linealidad()

        con = Conexion().conectar()
        fila_despues = con.execute(
            "SELECT * FROM LinealidadBraquiterapia WHERE id = 1").fetchone()
        n_total = con.execute(
            "SELECT COUNT(*) FROM LinealidadBraquiterapia").fetchone()[0]
        n_vigentes = con.execute(
            "SELECT COUNT(*) FROM LinealidadBraquiterapia "
            "WHERE activo IS NULL OR activo = 1").fetchone()[0]
        con.close()

        assert fila_antes == fila_despues, (
            "una fecha nueva no debe tocar ni un byte de la fila de otra fecha")
        assert n_total == 2
        assert n_vigentes == 2, "las dos fechas distintas quedan vigentes, ninguna se anula"


# ---------------------------------------------------------------------------
# (c) Un guardado que no pasa la validación no anula nada.
# ---------------------------------------------------------------------------

class TestGuardadoInvalidoNoAnulaNada:
    def test_menos_de_dos_medidas_no_anula_la_vigente(self, app, bd_temporal):
        obj1 = _con_medidas(_linealidad_pelada(), [1.0, 2.0], [1.0, 2.0])
        obj1.guardar_linealidad()

        # Segundo intento, MISMA fecha, con una sola medida completa --
        # ajuste_linealidad exige >= 2 pares y lanza DatosInsuficientes
        # ANTES de llegar a reemplazar_bloque.
        obj2 = _linealidad_pelada()
        obj2.extraer_datos_medidas = lambda: (
            [0.1], [1.0], [1.0], [1.0], [1.0])
        obj2.guardar_linealidad()

        con = Conexion().conectar()
        n = con.execute("SELECT COUNT(*) FROM LinealidadBraquiterapia").fetchone()[0]
        n_vigentes = con.execute(
            "SELECT COUNT(*) FROM LinealidadBraquiterapia "
            "WHERE activo IS NULL OR activo = 1").fetchone()[0]
        con.close()

        assert n == 1, "el intento inválido no debió insertar nada"
        assert n_vigentes == 1, "la fila del primer guardado sigue vigente, sin anular"


# ---------------------------------------------------------------------------
# El registro 8 de producción tiene `fecha` CON hora (2026-01-07
# 16:37:43): la clave de reemplazo va con DATE(fecha), o una fecha con
# hora nunca se reconocería como "el mismo día".
# ---------------------------------------------------------------------------

class TestFechaConHoraSeReconoceComoMismoDia:
    def test_reguardar_el_mismo_dia_anula_la_fila_con_hora(self, app, bd_temporal):
        # Fila sembrada a mano, simulando un registro real con hora en
        # `fecha` (igual que el registro 8 de producción).
        con = Conexion().conectar()
        con.execute(
            "INSERT INTO LinealidadBraquiterapia (user, fecha, lin_q1_0) "
            "VALUES (?, ?, ?)",
            ("Otro físico", "2026-01-07 16:37:43", 9.0))
        con.commit()
        con.close()

        obj = _con_medidas(_linealidad_pelada(QDate(2026, 1, 7)), [1.0, 2.0], [1.0, 2.0])
        obj.guardar_linealidad()

        con = Conexion().conectar()
        filas = con.execute(
            "SELECT activo, lin_q1_0 FROM LinealidadBraquiterapia ORDER BY id"
        ).fetchall()
        con.close()

        assert len(filas) == 2
        assert filas[0][0] == 0, (
            "la fila sembrada con hora en `fecha` debe reconocerse como "
            "del mismo día y quedar anulada -- la clave usa DATE(fecha)")
        assert filas[1][0] in (None, 1)
        assert filas[1][1] == 1.0
