"""RC.2 (PLAN_RECALCULO_CALIBRACION_BRAQUI_30-09.md): corregir un dato de
la calibración reconoce cada voltaje por su signo y escribe lo que
escribiría volver a guardar, entero o nada.

Es una prueba de la FUNCIÓN (`data/ManejoDatos/load.py::corregir_
calibracion`), no de un camino de la pantalla -- ese camino no existe
(§1.2 del plan). Se conduce con un `dlg` fabricado y metadata
`("TipoCalibracion", columna)`, mismo patrón que `test_a3_auditar_
edicion.py`, siempre sobre COPIAS.

Rojo real en HEAD: `data/ManejoDatos/load.py` no tiene ninguna función
`corregir_calibracion` -> `ImportError` al recolectar este archivo entero.
Y en HEAD, corregir "intensidad"/"conversion"/"fecha_cer" recalcula con
`max(voltajes, key=abs)` (D1), 300/150 fijo (D2), `promediosV` (D3) y K
sin redondear (D4) -- ver el cuadro §1.5 del plan.
"""
import os
import shutil
import sqlite3
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import (
    QApplication, QDialog, QMessageBox, QTableWidget, QTableWidgetItem, QWidget,
)

sys.path.insert(0, os.path.dirname(__file__))

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import guardarEdicion, corregir_calibracion, consulta_mesualBraq
from services.correccion_calibracion import CorreccionImposible
from services.lecturas_del_maximo import VoltajesInvalidos, lecturas_por_voltaje
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
from _bd_referencia import BD_QA, BD_REBUILD_21_09

REFS_SOLOS = (16, 23, 25, 29, 32, 35, 36)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _reset_qtsql_default_connection():
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


@pytest.fixture(autouse=True)
def _limpiar_conexion_tras_cada_test():
    yield
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None
    _reset_qtsql_default_connection()


@pytest.fixture
def dialogos(monkeypatch):
    """Captura lo que muestran los diálogos, sin bloquear -- `question`
    responde Sí por omisión; un test que necesite "No" lo cambia."""
    capturas = {
        "warning": [], "critical": [], "information": [],
        "question_llamadas": [], "question_respuesta": QMessageBox.Yes,
    }
    monkeypatch.setattr(load_mod.QMessageBox, "warning",
                         staticmethod(lambda *a, **k: capturas["warning"].append((a[1], a[2]))))
    monkeypatch.setattr(load_mod.QMessageBox, "critical",
                         staticmethod(lambda *a, **k: capturas["critical"].append((a[1], a[2]))))
    monkeypatch.setattr(load_mod.QMessageBox, "information",
                         staticmethod(lambda *a, **k: capturas["information"].append((a[1], a[2]))))

    def _question(*a, **k):
        capturas["question_llamadas"].append(a)
        return capturas["question_respuesta"]
    monkeypatch.setattr(load_mod.QMessageBox, "question", staticmethod(_question))
    return capturas


def _copia_de(monkeypatch, tmp_path, nombre, origen=BD_REBUILD_21_09):
    """Copia fresca de una BD de referencia bajo `nombre` -- para tener
    varias copias independientes en el mismo test."""
    if not origen.exists():
        pytest.skip(f"falta la BD de referencia {origen.name}")
    copia = tmp_path / nombre
    shutil.copy2(origen, copia)
    return copia


def _usar_bd(monkeypatch, ruta):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(ruta))
    conection_mod.Conexion._instance = None
    # Corre las migraciones idempotentes una vez (p.ej. `activo` en
    # CondicionesMedicion de BD_QA, la copia del 21-08) antes de dejar que
    # consulta_mesualBraq abra sus propias conexiones nuevas -- si no,
    # `filtro_activo` arma un WHERE con una columna que esa copia vieja
    # todavía no tiene.
    conexion = Conexion()
    conexion.con.close()
    conection_mod.Conexion._instance = None
    _reset_qtsql_default_connection()


class _UsuarioFalso:
    def __init__(self, nombre="Físico de Prueba"):
        self._nombre = nombre
        self.nombre = nombre
        self.id = 1

    def __getattr__(self, item):
        return None


class _DlgFalso(QWidget):
    def __init__(self, old_value, new_value, editing_col=0):
        super().__init__()
        self.user_id = _UsuarioFalso()
        self.old_value = old_value
        self.editing_row = 0
        self.editing_col = editing_col
        self.editing_item = QTableWidgetItem(new_value)
        self.accept_edit = QWidget()
        self.cancel_edit = QWidget()
        self.btn_delete = QWidget()
        self.edit_table = QWidget()
        # mostrar_db_mensualBraqui(dlg) (paso 4, tras un recálculo) necesita
        # dlg.table real -- si no lo tuviera, el refresco fallaría siempre
        # y el try/except de corregir_calibracion lo taparía sin que este
        # archivo probara nunca el camino real.
        self.table = QTableWidget()


def _tabla_con_metadata(row_id, col_data, col=0):
    tabla = QTableWidget(1, col + 1)
    item = QTableWidgetItem("x")
    item.setData(Qt.UserRole, row_id)
    item.setData(Qt.UserRole + 1, col_data)
    tabla.setItem(0, col, item)
    return tabla


def _corregir(app, dialogos, ref, columna, old_value, new_value):
    """Dispara la corrección por el camino real de `guardarEdicion`."""
    dlg = _DlgFalso(old_value=old_value, new_value=new_value)
    tabla = _tabla_con_metadata(row_id=ref, col_data=("TipoCalibracion", columna))
    guardarEdicion(dlg, tabla, "TipoCalibracion", id_ref=None)
    return dlg


def _resultados_actividad(ruta_db, ref):
    con = sqlite3.connect(f"file:{ruta_db}?mode=ro", uri=True)
    fila = con.execute(
        "SELECT Ks, Kp, Ktp, actividad_calculada, actividad_decaimiento "
        "FROM ResultadosActividad WHERE ref=? AND (activo IS NULL OR activo=1)",
        (ref,)).fetchone()
    con.close()
    return fila


def _tipo_calibracion(ruta_db, ref, columna):
    con = sqlite3.connect(f"file:{ruta_db}?mode=ro", uri=True)
    fila = con.execute(f"SELECT {columna} FROM TipoCalibracion WHERE id=?", (ref,)).fetchone()
    con.close()
    return fila[0] if fila else None


def _audit_log(ruta_db):
    con = sqlite3.connect(f"file:{ruta_db}?mode=ro", uri=True)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
    con.close()
    return filas


# ---------------------------------------------------------------------------
# (a) Como al volver a guardar, contra el formulario real (ref 36, el
# ejemplo completo del plan).
# ---------------------------------------------------------------------------

def test_a_ref36_intensidad_coincide_con_recargar_y_guardar(app, monkeypatch, tmp_path, dialogos):
    copia_a = _copia_de(monkeypatch, tmp_path, "copiaA.db")
    intensidad_original = _tipo_calibracion(copia_a, 36, "intensidad")
    nueva_intensidad = round(intensidad_original + 0.01, 2)

    # Copia A: corrige por guardarEdicion.
    _usar_bd(monkeypatch, copia_a)
    _corregir(app, dialogos, 36, "intensidad", str(intensidad_original), str(nueva_intensidad))
    resultado_a = _resultados_actividad(copia_a, 36)
    assert resultado_a is not None, dialogos["warning"] + dialogos["critical"]

    # Copia B: fija la misma intensidad con un UPDATE directo, recarga el
    # formulario y pulsa Guardar con el escritor espiado.
    copia_b = _copia_de(monkeypatch, tmp_path, "copiaB.db")
    con = sqlite3.connect(copia_b)
    con.execute("UPDATE TipoCalibracion SET intensidad=? WHERE id=36", (nueva_intensidad,))
    con.commit()
    con.close()
    _usar_bd(monkeypatch, copia_b)

    capturas = []
    monkeypatch.setattr(braq_mensual_mod, "guardar_resultado_CambioFuente",
                         lambda *a, **k: capturas.append((a, k)) or 999)
    con = sqlite3.connect(f"file:{copia_b}?mode=ro", uri=True)
    (fecha,) = con.execute("SELECT fecha FROM TipoCalibracion WHERE id=36").fetchone()
    con.close()
    obj = PruebaMensualBraq(_UsuarioFalso())
    obj.pri_cal.setChecked(True)
    qd = QDate.fromString(str(fecha)[:10], "yyyy-MM-dd")
    obj.date_box.setDate(qd.addDays(1))
    obj.date_box.setDate(qd)
    obj.guardar_DB()
    assert capturas, "el formulario no guardó nada"
    a, _k = capturas[0]
    resultado_b = (a[29], a[30], a[31], a[33], a[34])

    assert tuple(round(x, 3) for x in resultado_a) == tuple(round(x, 3) for x in resultado_b)
    # Cifras del plan (§0.3-2, el ejemplo del diálogo de confirmación).
    Ks, Kp, Ktp, A, dec = resultado_a
    assert (round(Ks, 3), round(Kp, 3)) == (1.001, 1.002)
    assert round(A, 3) == 6.139


# ---------------------------------------------------------------------------
# (a-2) Autoconsistencia en los 7 controles solos en su día: la corrección
# por `guardarEdicion` da lo mismo que recargar+Guardar, con el MISMO valor
# nuevo, en cada uno.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ref", REFS_SOLOS)
def test_a_todos_los_controles_solos_coinciden_con_recargar_y_guardar(app, monkeypatch, tmp_path, dialogos, ref):
    copia_a = _copia_de(monkeypatch, tmp_path, "copiaA.db")
    conv_original = _tipo_calibracion(copia_a, ref, "conversion")
    nueva_conv = round(conv_original + 0.001, 4)

    _usar_bd(monkeypatch, copia_a)
    _corregir(app, dialogos, ref, "conversion", str(conv_original), str(nueva_conv))
    resultado_a = _resultados_actividad(copia_a, ref)
    assert resultado_a is not None, (ref, dialogos["warning"], dialogos["critical"])

    copia_b = _copia_de(monkeypatch, tmp_path, "copiaB.db")
    con = sqlite3.connect(copia_b)
    con.execute("UPDATE TipoCalibracion SET conversion=? WHERE id=?", (nueva_conv, ref))
    con.commit()
    con.close()
    _usar_bd(monkeypatch, copia_b)

    capturas = []
    monkeypatch.setattr(braq_mensual_mod, "guardar_resultado_CambioFuente",
                         lambda *a, **k: capturas.append((a, k)) or 999)
    con = sqlite3.connect(f"file:{copia_b}?mode=ro", uri=True)
    (fecha,) = con.execute("SELECT fecha FROM TipoCalibracion WHERE id=?", (ref,)).fetchone()
    con.close()
    obj = PruebaMensualBraq(_UsuarioFalso())
    obj.pri_cal.setChecked(True)
    qd = QDate.fromString(str(fecha)[:10], "yyyy-MM-dd")
    obj.date_box.setDate(qd.addDays(1))
    obj.date_box.setDate(qd)
    obj.guardar_DB()
    assert capturas, (ref, "el formulario no guardó nada")
    a, _k = capturas[0]
    resultado_b = (a[29], a[30], a[31], a[33], a[34])

    assert tuple(round(x, 3) for x in resultado_a) == tuple(round(x, 3) for x in resultado_b), ref


# ---------------------------------------------------------------------------
# (b) El papel sale del signo, no del orden -- 6 permutaciones sobre datos
# reales, y las dos convenciones de orden real de la BD dan lo mismo.
# ---------------------------------------------------------------------------

def test_b_resultados_desde_lo_guardado_invariante_a_permutaciones_reales(app, monkeypatch, tmp_path):
    import itertools
    from services.correccion_calibracion import resultados_desde_lo_guardado
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    for ref in REFS_SOLOS:
        datos = consulta_mesualBraq(None, ref)
        base = resultados_desde_lo_guardado(datos)
        con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
        filas = con.execute(
            "SELECT voltaje, V_300, V_150, Vn_300, promediosV FROM LecturasMaximos "
            "WHERE ref=? AND (activo IS NULL OR activo=1)", (ref,)).fetchall()
        con.close()
        for permutacion in itertools.permutations(filas):
            datos_permutado = dict(datos)
            datos_permutado["lecturas"] = lecturas_por_voltaje(list(permutacion))
            assert resultados_desde_lo_guardado(datos_permutado) == base, ref


def test_b_orden_de_insercion_y_orden_de_texto_dan_lo_mismo(app, monkeypatch, tmp_path):
    from services.correccion_calibracion import resultados_desde_lo_guardado
    if not BD_QA.exists():
        pytest.skip(f"falta la BD de referencia {BD_QA.name}")
    copia_texto = _copia_de(monkeypatch, tmp_path, "texto.db", origen=BD_REBUILD_21_09)
    copia_insercion = _copia_de(monkeypatch, tmp_path, "insercion.db", origen=BD_QA)

    comunes = (16, 23, 25, 29, 32)
    _usar_bd(monkeypatch, copia_texto)
    resultados_texto = {ref: resultados_desde_lo_guardado(consulta_mesualBraq(None, ref)) for ref in comunes}
    _usar_bd(monkeypatch, copia_insercion)
    resultados_insercion = {ref: resultados_desde_lo_guardado(consulta_mesualBraq(None, ref)) for ref in comunes}
    for ref in comunes:
        assert resultados_texto[ref] == resultados_insercion[ref], ref


# ---------------------------------------------------------------------------
# (c) El cociente sale de los voltajes guardados -- sintético 300/50/-300
# escrito con el escritor REAL.
# ---------------------------------------------------------------------------

def test_c_sintetico_300_50_neg300_usa_el_cociente_correcto(app, monkeypatch, tmp_path, dialogos):
    from data.ManejoDatos.load import guardar_resultado_CambioFuente
    ruta = tmp_path / "sintetica.db"
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(ruta))
    conection_mod.Conexion._instance = None
    Conexion()  # DDL real

    alto = [5.00e-08, 5.00e-08, 5.00e-08]
    bajo = [4.90e-08, 4.90e-08, 4.90e-08]
    neg = [5.02e-08, 5.02e-08, 5.02e-08]
    ref = guardar_resultado_CambioFuente(
        "Físico de Prueba", "2026-09-29 10:00:00", "Control Mensual", "SERIE-X", "CERT-X",
        "2026-09-01 10:00:00", 10.0, 0.11,
        "HDR 1000 Plus", "A092535", 464700.0, "UNIDOS E", "002343", 1.0,
        22.0, 760, 50.0, 21.0, 640.0, 50.0,
        [127.5], [4.0], [4.0], [4.0],
        [300.0, 50.0, -300.0], alto, bajo, neg,
        [sum(alto) / 3, sum(bajo) / 3, sum(neg) / 3],
        1.0, 1.0, 1.0, 9.0, 9.0, 9.0, "No Aplica", "")

    _corregir(app, dialogos, ref, "intensidad", "10.0", "10.5")
    Ks, Kp, Ktp, A, dec = _resultados_actividad(ruta, ref)
    assert round(Ks, 3) == 1.001
    assert round(Kp, 3) == 1.002
    assert round(Ktp, 3) == 1.183
    assert round(A, 3) == 6.774


# ---------------------------------------------------------------------------
# (d) Todo o nada.
# ---------------------------------------------------------------------------

def test_d_bloque_invalido_no_escribe_nada(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    con = sqlite3.connect(copia)
    con.execute("DELETE FROM LecturasMaximos WHERE ref=36 AND voltaje='150.0'")
    con.commit()
    con.close()
    _usar_bd(monkeypatch, copia)

    antes_tc = _tipo_calibracion(copia, 36, "intensidad")
    antes_ra = _resultados_actividad(copia, 36)
    antes_audit = len(_audit_log(copia))

    dlg = _corregir(app, dialogos, 36, "intensidad", str(antes_tc), str(round(antes_tc + 0.01, 2)))

    assert _tipo_calibracion(copia, 36, "intensidad") == antes_tc
    assert _resultados_actividad(copia, 36) == antes_ra
    assert len(_audit_log(copia)) == antes_audit
    assert dialogos["warning"], "se esperaba un aviso"
    assert "lectura" in dialogos["warning"][-1][1].lower() or "fila" in dialogos["warning"][-1][1].lower()
    assert dlg.editing_item.text() == str(antes_tc), "la celda debe volver a mostrar lo guardado"


def test_d_fecha_ilegible_se_rechaza(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    row = con.execute("SELECT id, intensidad FROM TipoCalibracion WHERE fecha_cer LIKE '04-09-2025%'").fetchone()
    con.close()
    if row is None:
        pytest.skip("el ref 14 no está en esta copia")
    ref14, intensidad14 = row

    antes_ra = _resultados_actividad(copia, ref14)
    dlg = _corregir(app, dialogos, ref14, "intensidad", str(intensidad14), str(round(intensidad14 + 0.01, 2)))
    assert _tipo_calibracion(copia, ref14, "intensidad") == intensidad14
    assert _resultados_actividad(copia, ref14) == antes_ra
    assert dialogos["warning"]
    assert "04-09-2025 10:40:03" in dialogos["warning"][-1][1]
    assert dlg.editing_item.text() == str(intensidad14), "la celda debe volver a mostrar lo guardado"


def test_d_fallo_a_mitad_hace_rollback(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    con = sqlite3.connect(copia)
    con.execute("""
        CREATE TRIGGER trg_abortar_prueba BEFORE UPDATE ON ResultadosActividad
        BEGIN SELECT RAISE(ABORT, 'prueba'); END;
    """)
    con.commit()
    con.close()
    _usar_bd(monkeypatch, copia)

    antes_tc = _tipo_calibracion(copia, 36, "intensidad")
    antes_ra = _resultados_actividad(copia, 36)
    antes_audit = len(_audit_log(copia))

    dlg = _corregir(app, dialogos, 36, "intensidad", str(antes_tc), str(round(antes_tc + 0.01, 2)))

    assert _tipo_calibracion(copia, 36, "intensidad") == antes_tc
    assert _resultados_actividad(copia, 36) == antes_ra
    assert len(_audit_log(copia)) == antes_audit
    assert dialogos["critical"]
    assert dlg.editing_item.text() == str(antes_tc), "la celda debe volver a mostrar lo guardado"


def test_d_sin_fila_de_auditoria_no_se_aplica_nada(app, monkeypatch, tmp_path, dialogos):
    """§0.3-2 del plan: la auditoría es el único rastro de las cifras
    reemplazadas, y `registrar(con=)` se traga su propio fallo por diseño.
    Aquí, si la fila no quedó escrita dentro de la transacción, NO se
    aplica nada. Se simula con un trigger que descarta en silencio el
    INSERT en `audit_log` (`RAISE(IGNORE)`): el INSERT 'tiene éxito' y no
    inserta nada -- solo el conteo de filas lo delata."""
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    con = sqlite3.connect(copia)
    con.execute("""
        CREATE TRIGGER trg_descartar_audit BEFORE INSERT ON audit_log
        BEGIN SELECT RAISE(IGNORE); END;
    """)
    con.commit()
    con.close()
    _usar_bd(monkeypatch, copia)

    antes_tc = _tipo_calibracion(copia, 36, "intensidad")
    antes_ra = _resultados_actividad(copia, 36)

    dlg = _corregir(app, dialogos, 36, "intensidad", str(antes_tc), str(round(antes_tc + 0.01, 2)))

    assert _tipo_calibracion(copia, 36, "intensidad") == antes_tc
    assert _resultados_actividad(copia, 36) == antes_ra
    assert dialogos["critical"], "se esperaba un error por no poder dejar el rastro"
    assert "auditor" in dialogos["critical"][-1][1].lower()
    assert dlg.editing_item.text() == str(antes_tc), "la celda debe volver a mostrar lo guardado"


def test_d_el_fisico_dice_no(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    dialogos["question_respuesta"] = QMessageBox.No

    antes_tc = _tipo_calibracion(copia, 36, "intensidad")
    antes_ra = _resultados_actividad(copia, 36)
    antes_audit = len(_audit_log(copia))

    dlg = _corregir(app, dialogos, 36, "intensidad", str(antes_tc), str(round(antes_tc + 0.01, 2)))

    assert _tipo_calibracion(copia, 36, "intensidad") == antes_tc
    assert _resultados_actividad(copia, 36) == antes_ra
    assert len(_audit_log(copia)) == antes_audit
    assert dialogos["question_llamadas"]
    assert dlg.editing_item.text() == str(antes_tc), "la celda debe volver a mostrar lo guardado"


# ---------------------------------------------------------------------------
# (e) Rastro de auditoría.
# ---------------------------------------------------------------------------

def test_e_rastro_de_auditoria_ref36(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    antes = len(_audit_log(copia))

    _corregir(app, dialogos, 36, "intensidad", "13.65", "13.66")

    filas = _audit_log(copia)
    assert len(filas) == antes + 1
    usuario, accion, tabla, ref, detalle = filas[-1]
    assert accion == "editar"
    assert tabla == "TipoCalibracion"
    assert ref == "36"
    assert detalle.startswith("intensidad: '13.65' → 13.66")
    assert "recalculado" in detalle
    assert "Kp" in detalle and "1.002" in detalle
    assert "actividad_calculada" in detalle and "6.139" in detalle


# ---------------------------------------------------------------------------
# (f) Solo si la entrada cambia.
# ---------------------------------------------------------------------------

def test_f_sin_cambio_numerico_no_recalcula(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    antes_ra = _resultados_actividad(copia, 36)
    antes_audit = len(_audit_log(copia))

    _corregir(app, dialogos, 36, "intensidad", "13.65", "13.650")

    assert _resultados_actividad(copia, 36) == antes_ra
    assert not dialogos["question_llamadas"], "no debía preguntar: la entrada no cambió"
    filas = _audit_log(copia)
    assert len(filas) == antes_audit + 1
    assert "recalculado" not in filas[-1][4]


# ---------------------------------------------------------------------------
# (g) Columnas sin efecto en el cálculo.
# ---------------------------------------------------------------------------

def test_g_serie_no_recalcula_ni_pregunta(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    antes_ra = _resultados_actividad(copia, 36)

    _corregir(app, dialogos, 36, "serie", "A092535", "A092535-B")

    assert _tipo_calibracion(copia, 36, "serie") == "A092535-B"
    assert _resultados_actividad(copia, 36) == antes_ra
    assert not dialogos["question_llamadas"]
    filas = _audit_log(copia)
    assert "recalculado" not in filas[-1][4]


def test_g_serie_funciona_sin_condicionesmedicion(app, monkeypatch, tmp_path, dialogos):
    """Cambio nombrado en §2.5-4: hoy falla si al control le falta una
    tabla asociada (porque se lee todo antes); después no."""
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    con = sqlite3.connect(copia)
    con.execute("DELETE FROM CondicionesMedicion WHERE ref=36")
    con.commit()
    con.close()
    _usar_bd(monkeypatch, copia)

    _corregir(app, dialogos, 36, "serie", "A092535", "A092535-B")
    assert _tipo_calibracion(copia, 36, "serie") == "A092535-B"
    assert not dialogos["critical"]


# ---------------------------------------------------------------------------
# (h) No se corrigen en sitio.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("columna,valor_nuevo", [
    ("fecha", "2027-01-01 00:00:00"),
    ("tipo", "Otro Tipo"),
    ("id", "999"),
    ("activo", "0"),
])
def test_h_columnas_que_no_se_corrigen_en_sitio(app, monkeypatch, tmp_path, dialogos, columna, valor_nuevo):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    antes = _tipo_calibracion(copia, 36, columna)
    antes_audit = len(_audit_log(copia))

    dlg = _corregir(app, dialogos, 36, columna, str(antes), valor_nuevo)

    assert _tipo_calibracion(copia, 36, columna) == antes
    assert len(_audit_log(copia)) == antes_audit
    assert dialogos["warning"]
    assert dlg.editing_item.text() == str(antes), "la celda debe volver a mostrar lo guardado"


def test_i_conexiones_no_se_acumulan(app, monkeypatch, tmp_path, dialogos):
    """Mismo criterio que `test_t7_conexiones_no_se_acumulan.py` (PLAN_
    BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md): la PRIMERA operación tras
    recrear el singleton (`Conexion._instance = None` en `_usar_bd`)
    reabre su conexión persistente -- un costo de arranque legítimo, una
    sola vez, no una fuga (lo dispara `mostrar_db_mensualBraqui`, paso 4,
    con `Conexion().conectar()` sin `with` -- sitio ya revisado por R5,
    zona roja de este plan, no se toca).

    [medido] Bajo el interceptor de RT1 (`tests/conftest.py`, activo en
    TODA la suite) aparece un SEGUNDO costo de arranque de +1 descriptor,
    una sola vez, en algún punto de las primeras 2-3 correcciones -- no
    reproducible llamando `corregir_calibracion`/`guardarEdicion`
    directamente fuera de pytest (con o sin el interceptor activado a
    mano), así que es un artefacto de la instrumentación de sesión, no de
    `corregir_calibracion` -- misma familia que el "disk I/O error" que el
    propio `test_t7` ya documenta. Confirmado con 7 correcciones
    seguidas: la serie se ESTABILIZA (nunca sigue creciendo), no crece sin
    límite -- que es la garantía real que importa aquí. Por eso la
    comparación no es contra la operación #1 (como en test_t7, sin este
    segundo costo) sino contra la #3, una vez pasado ese arranque."""
    import glob
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)

    def _descriptores():
        try:
            objetivo = str(copia)
            enlaces = [os.readlink(p) for p in glob.glob("/proc/self/fd/*") if os.path.islink(p)]
            return sum(1 for e in enlaces if objetivo in e)
        except OSError:
            return -1

    descriptores_por_correccion = []
    # aplicada, rechazada, aplicada, fallida (trigger), aplicada, aplicada, aplicada
    _corregir(app, dialogos, 36, "intensidad", "13.65", "13.66")
    descriptores_por_correccion.append(_descriptores())
    dialogos["warning"].clear()
    _corregir(app, dialogos, 36, "fecha", "x", "y")  # rechazada, no recalcula
    descriptores_por_correccion.append(_descriptores())
    dialogos["warning"].clear()
    _corregir(app, dialogos, 23, "conversion", str(_tipo_calibracion(copia, 23, "conversion")), "10.5")
    descriptores_por_correccion.append(_descriptores())
    con = sqlite3.connect(copia)
    con.execute("""
        CREATE TRIGGER trg_abortar_prueba_i BEFORE UPDATE ON ResultadosActividad
        BEGIN SELECT RAISE(ABORT, 'prueba'); END;
    """)
    con.commit()
    con.close()
    dialogos["critical"].clear()
    _corregir(app, dialogos, 25, "intensidad", str(_tipo_calibracion(copia, 25, "intensidad")),
              str(round(_tipo_calibracion(copia, 25, "intensidad") + 0.01, 2)))
    assert dialogos["critical"], "se esperaba que el trigger abortara esta corrección"
    descriptores_por_correccion.append(_descriptores())
    con = sqlite3.connect(copia)
    con.execute("DROP TRIGGER trg_abortar_prueba_i")
    con.commit()
    con.close()
    _corregir(app, dialogos, 29, "intensidad", str(_tipo_calibracion(copia, 29, "intensidad")),
              str(round(_tipo_calibracion(copia, 29, "intensidad") + 0.01, 2)))
    descriptores_por_correccion.append(_descriptores())
    _corregir(app, dialogos, 32, "intensidad", str(_tipo_calibracion(copia, 32, "intensidad")),
              str(round(_tipo_calibracion(copia, 32, "intensidad") + 0.01, 2)))
    descriptores_por_correccion.append(_descriptores())
    _corregir(app, dialogos, 35, "intensidad", str(_tipo_calibracion(copia, 35, "intensidad")),
              str(round(_tipo_calibracion(copia, 35, "intensidad") + 0.01, 2)))
    descriptores_por_correccion.append(_descriptores())

    despues_de_la_3 = descriptores_por_correccion[2]
    despues_de_la_7 = descriptores_por_correccion[-1]
    assert despues_de_la_7 <= despues_de_la_3, (
        f"de la corrección #3 a la #7 el número de descriptores no debe "
        f"seguir creciendo -- serie completa: {descriptores_por_correccion}")


# ---------------------------------------------------------------------------
# (j) La única celda editable hoy, "Act. Monitor", no cambia de
# comportamiento.
# ---------------------------------------------------------------------------

def test_j_act_monitor_sigue_igual(app, monkeypatch, tmp_path, dialogos):
    copia = _copia_de(monkeypatch, tmp_path, "copia.db")
    _usar_bd(monkeypatch, copia)
    dlg = _DlgFalso(old_value="9.5", new_value="9.6")
    tabla = _tabla_con_metadata(row_id=36, col_data=("ResultadosActividad", "actividad_monitor"))
    guardarEdicion(dlg, tabla, "ResultadosActividad", id_ref=None)

    con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    (valor,) = con.execute(
        "SELECT actividad_monitor FROM ResultadosActividad WHERE ref=36 AND (activo IS NULL OR activo=1)").fetchone()
    con.close()
    assert valor == 9.6
    assert not dialogos["question_llamadas"]
    filas = _audit_log(copia)
    assert "recalculado" not in filas[-1][4]
