"""V.3 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md): las cuatro lecturas de
"LECTURAS DEL MÁXIMO" -- recarga del formulario, "Ver tabla", PDF y la
precarga de la redundante -- pasan a leer por PAPEL (alto/bajo/negativo),
no por FILA. El tripwire de nombre de función vive en
`test_v3_tripwire_lecturas_por_papel.py`; este archivo prueba el
COMPORTAMIENTO: lo guardado nunca estuvo mal, lo que se mostraba
estaba cruzado.

CAUSA medida en el plan (§1.3): el ref 24 (Calibración Redundante,
29-12-2025, presente en las 5 BD de referencia) imprime, leído por fila,
un promedio que no es la media de las medidas de su propia fila. Leído por
papel (esta tarea), sí.
"""
import copy
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import (
    QApplication, QDialog, QMessageBox, QTableWidget, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import guardar_resultado_CambioFuente
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
import models.PDF.Mensuales.reportes_mensuales as rep_mod
from models.PDF.Mensuales.reportes_mensuales import (
    _obtener_datos_tabla_relacionada, _crear_tabla_lecturas_maximos,
)
from _bd_referencia import BD_REBUILD_21_09

REF_24_ESPERADO = [
    ["300.0", "6.87e-08", "6.87e-08", "6.87e-08", "6.87e-08"],
    ["150.0", "6.83e-08", "6.86e-08", "6.86e-08", "6.85e-08"],
    ["-300.0", "6.87e-08", "6.87e-08", "6.87e-08", "6.87e-08"],
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_copia_real(monkeypatch, tmp_path):
    """Copia REAL de `Rebuild_21-09` (15 controles de braqui reales) --
    nunca se conecta directo a la BD de referencia."""
    if not BD_REBUILD_21_09.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_21_09.name}")
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    conection_mod.Conexion._instance = None
    yield copia
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None


@pytest.fixture
def qtsql_copia_real(bd_copia_real):
    """La misma copia, abierta por QtSql (lo que usan las funciones del
    PDF y `mostrar_tabla_lecturas`/`cargar_maximos_desde_db`)."""
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    db = QSqlDatabase.addDatabase("QSQLITE", "qt_sql_default_connection")
    db.setDatabaseName(str(bd_copia_real))
    assert db.open()
    yield db
    db.close()
    QSqlDatabase.removeDatabase("qt_sql_default_connection")


def _refs_reales(bd_copia_real):
    con = sqlite3.connect(f"file:{bd_copia_real}?mode=ro", uri=True)
    refs = [r[0] for r in con.execute(
        "SELECT DISTINCT ref FROM LecturasMaximos WHERE (activo IS NULL OR activo=1)")]
    con.close()
    return refs


# ---------------------------------------------------------------------------
# (a) PDF -- por la función real, sobre los 15 controles de Rebuild_21-09.
# ---------------------------------------------------------------------------

def test_pdf_las_45_filas_cumplen_promedio_es_media_de_sus_medidas(qtsql_copia_real, bd_copia_real):
    refs = _refs_reales(bd_copia_real)
    assert len(refs) == 15
    total_filas = 0
    for ref in refs:
        lecturas_data = _obtener_datos_tabla_relacionada(qtsql_copia_real, ref, "LecturasMaximos")
        assert len(lecturas_data) == 3, ref
        tabla = _crear_tabla_lecturas_maximos(lecturas_data)
        filas = tabla.values.tolist()[1:]  # se salta el encabezado
        for voltaje, m1, m2, m3, promedio in filas:
            total_filas += 1
            media = sum(float(x) for x in (m1, m2, m3)) / 3
            assert abs(media - float(promedio)) < 0.01e-08 + abs(float(promedio)) * 0.01, (
                ref, voltaje, m1, m2, m3, promedio)
    assert total_filas == 45


def test_pdf_ref_24_da_la_tabla_correcta(qtsql_copia_real):
    lecturas_data = _obtener_datos_tabla_relacionada(qtsql_copia_real, 24, "LecturasMaximos")
    tabla = _crear_tabla_lecturas_maximos(lecturas_data)
    filas = tabla.values.tolist()[1:]
    assert filas == REF_24_ESPERADO


def test_pdf_bloque_malformado_se_muestra_como_antes():
    """Compuerta: un bloque que `lecturas_por_voltaje` rechaza (aquí, solo
    2 filas) sigue mostrándose ordenado por voltaje descendente, como
    antes de esta tarea -- ningún dato desaparece de un PDF."""
    lecturas_data = [
        {"voltaje": "150.0", "V_300": "1e-08", "V_150": "2e-08", "Vn_300": "3e-08", "promediosV": "2e-08"},
        {"voltaje": "300.0", "V_300": "4e-08", "V_150": "5e-08", "Vn_300": "6e-08", "promediosV": "5e-08"},
    ]
    tabla = _crear_tabla_lecturas_maximos(lecturas_data)
    filas = tabla.values.tolist()[1:]
    assert filas[0][0] == "300.0"
    assert filas[1][0] == "150.0"


# ---------------------------------------------------------------------------
# (b) "Ver tabla" -- por el camino real de PruebaMensualBraq.mostrar_tabla_lecturas.
# ---------------------------------------------------------------------------

def test_ver_tabla_muestra_el_ref_24_correcto(app, qtsql_copia_real, bd_copia_real, monkeypatch):
    capturada = {}

    def _exec_capturando(self):
        tabla = self.findChild(QTableWidget)
        capturada["filas"] = [
            [tabla.item(r, c).text() if tabla.item(r, c) else None for c in range(tabla.columnCount())]
            for r in range(tabla.rowCount())]
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec_", _exec_capturando)

    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)
    obj.mostrar_tabla_lecturas(24)

    # "Ver tabla" formatea TODAS las columnas -- también el voltaje -- como
    # `.2e` (comportamiento preexistente, ajeno a V.3: no lo toca el diff de
    # esta tarea). El PDF (arriba) sí muestra el voltaje como "300.0"; son
    # dos funciones distintas con formatos distintos, cada una la suya.
    filas = capturada["filas"]
    assert [f[0] for f in filas] == ["3.00e+02", "1.50e+02", "-3.00e+02"]
    assert filas[1] == ["1.50e+02", "6.83e-08", "6.86e-08", "6.86e-08", "6.85e-08"]


# ---------------------------------------------------------------------------
# (c) Recarga del formulario -- por el camino del usuario: construir la
# pantalla real sobre una copia de la BD y mover la fecha (como el físico).
# ---------------------------------------------------------------------------

class _UsuarioFalso:
    def __init__(self, nombre="Físico de Prueba"):
        self._nombre = nombre
        self.nombre = nombre
        self.id = 1

    def __getattr__(self, item):
        return None


def test_recarga_del_formulario_muestra_cada_voltaje_con_sus_medidas(app, bd_copia_real):
    d = PruebaMensualBraq(_UsuarioFalso())
    d.date_box.setDate(QDate(2026, 8, 31))  # emite dateChanged, como el calendario

    filas = [[c.text() for c in fila] for fila in d.campos_lecturas]
    assert filas == [
        ["300.0", "4.52e-08", "4.52e-08", "4.52e-08", "4.52e-08"],
        ["150.0", "4.51e-08", "4.51e-08", "4.51e-08", "4.51e-08"],
        ["-300.0", "4.52e-08", "4.52e-08", "4.57e-08", "4.53e-08"],
    ]

    # Pulsar "Ok": los promedios recalculados son los guardados, dentro
    # del redondeo de `.2e` con que se muestran.
    # -300V (ref 36): medidas 4.52e-08, 4.52e-08, 4.57e-08 -> media
    # 4.536666...e-08, que redondea a "4.54e-08" (no "4.53e-08").
    d.aceptar.click()
    promedios_recalculados = [c[4].text() for c in d.campos_lecturas]
    assert promedios_recalculados == ["4.52e-08", "4.51e-08", "4.54e-08"]


# ---------------------------------------------------------------------------
# (d) Ida y vuelta con voltajes 250/100/-250, por las tres lecturas.
# ---------------------------------------------------------------------------

ARGS_BASE = dict(
    tipo="Cambio de fuente", serie="A092535", certificado="HDR12899",
    fecha_cer="2025-07-28", intensidad=1.1, conversion=1.0,
    modelo="HDR1000 Plus", serie_cp="1825", calibracion=464700,
    modelo_elec="Unidos-E", serie_ele="2343", electrometro="T10010",
    t0=22.0, p0=101.325, h0=50.0, t=22.0, p=101.325, h=50.0,
    posiciones=["A", "B"], medida1=[1.0, 2.0], medida2=[1.1, 2.1],
    promedios=[1.05, 2.05],
    Ks=1.0, Kp=1.0, Ktp=1.0,
    actividad_monitor=1.0, actividad_calculada=1.0,
    actividad_decaimiento=1.0, desplazamiento_ini="No Aplica",
    observaciones="sin observaciones",
)


@pytest.fixture
def bd_temporal_vacia(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def test_ida_y_vuelta_recarga_ver_tabla_y_pdf(app, monkeypatch, bd_temporal_vacia):
    medidas_alto = [1e-8, 2e-8, 3e-8]
    medidas_bajo = [4e-8, 5e-8, 6e-8]
    medidas_neg = [7e-8, 8e-8, 9e-8]
    kwargs = dict(ARGS_BASE)
    kwargs.update(
        voltaje=[250.0, 100.0, -250.0],
        V_300=medidas_alto, V_150=medidas_bajo, Vn_300=medidas_neg,
        promediosV=[sum(medidas_alto) / 3, sum(medidas_bajo) / 3, sum(medidas_neg) / 3])
    ref = guardar_resultado_CambioFuente("Físico de Prueba", "2026-01-01 00:00:00", **kwargs)

    # "Ver tabla" real.
    capturada = {}

    def _exec_capturando(self):
        tabla = self.findChild(QTableWidget)
        capturada["filas"] = [
            [tabla.item(r, c).text() for c in range(tabla.columnCount())]
            for r in range(tabla.rowCount())]
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec_", _exec_capturando)
    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)
    obj.mostrar_tabla_lecturas(ref)
    # "Ver tabla" formatea el voltaje como `.2e`, igual que las medidas
    # (comportamiento preexistente, ver la nota equivalente arriba).
    assert [f[0] for f in capturada["filas"]] == ["2.50e+02", "1.00e+02", "-2.50e+02"]
    assert capturada["filas"][0][1:4] == ["1.00e-08", "2.00e-08", "3.00e-08"]
    assert capturada["filas"][1][1:4] == ["4.00e-08", "5.00e-08", "6.00e-08"]
    assert capturada["filas"][2][1:4] == ["7.00e-08", "8.00e-08", "9.00e-08"]

    # PDF: mismo bloque, vía QtSql sobre la MISMA base temporal.
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")
    db = QSqlDatabase.addDatabase("QSQLITE", "qt_sql_default_connection")
    db.setDatabaseName(bd_temporal_vacia)
    assert db.open()
    lecturas_data = _obtener_datos_tabla_relacionada(db, ref, "LecturasMaximos")
    tabla = _crear_tabla_lecturas_maximos(lecturas_data)
    filas_pdf = tabla.values.tolist()[1:]
    assert [f[0] for f in filas_pdf] == ["250.0", "100.0", "-250.0"]
    db.close()
    QSqlDatabase.removeDatabase("qt_sql_default_connection")
