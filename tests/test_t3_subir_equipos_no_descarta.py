"""T.3 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §4): "Subir" en Equipos no
descarta una cámara que ya no está en el catálogo.

CAUSA (§0.5 del plan): `Traerinfo` añade una entrada de respaldo
(`"Serie: {serie}"`, `data=None`) cuando el catálogo ya no puede explicar
una cámara guardada -- borrada o anulada. `subirtodo_modificado` descartaba
ese grupo en silencio (`equipo_id is None -> continue`), y si al menos otro
grupo sí resolvía, el bloque ENTERO se anulaba y se reinsertaba SIN la
cámara descartada -- el físico veía "Datos subidos correctamente" igual.

**[medido] 3 controles reales del iX en esa situación**: ref=1 (14/12/2025,
Principal Electrones `N34001/002426`), ref=30 (05/2026, electrómetro
`CDX-2000B/B091982`), ref=40 (07/2026, Principal Electrones
`TN34001/001069`). Ningún control del 600 está expuesto -- lo borrado el
11-09 fueron filas duplicadas de las mismas cámaras.

OBJETIVO: reguardar la sección de Equipos de un control antiguo NUNCA hace
desaparecer una cámara, y si algo impide guardar, no se escribe nada y se
dice por qué.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QGridLayout, QLineEdit, QMessageBox,
    QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
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
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _insertar_equipo(ruta_bd, eq_id, **campos):
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


def _insertar_control(ruta_bd, equipo="Clinac 600", control="Mensual", fecha="06/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _insertar_equipos_medicion(ruta_bd, ref, tipo_camara, model, serie,
                                calibr_fact, equipo_id, activo=1,
                                fecha_calibr="01/01/2020",
                                equip_type="Cámara de ionización"):
    con = sqlite3.connect(ruta_bd)
    con.execute("""
        INSERT INTO equipos_medicion
            (ref, tipo_camara, equip_type, model, serie, calibr_fact,
             fecha_calibr, equipo_id, activo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ref, tipo_camara, equip_type, model, serie, calibr_fact,
          fecha_calibr, equipo_id, activo))
    con.commit()
    con.close()


def _mensual_pelado(ref):
    """PruebaMensual600 pelado -- 3 grupos: Principal/Secundaria/
    Electrómetro (patrón estándar de `test_e2e3_seccion_equipos.py`)."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.ref = ref
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 6, 1))

    obj.commenu = []
    for _ in range(3):
        combo_modelo = QComboBox()
        combo_serie = QComboBox()
        lineedit_calib = QLineEdit()
        obj.commenu.extend([combo_modelo, combo_serie, lineedit_calib])
    obj.combo_menu = obj.commenu
    return obj


def _mensual_ix_pelado(ref):
    """Variante iX -- 4 grupos: Principal Fotones/Principal Electrones/
    Secundaria/Electrómetro. Es la clase real donde viven los 3 controles
    afectados en producción."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.ref = ref
    obj.esIX = True
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 5, 1))

    obj.commenu = []
    for _ in range(4):
        combo_modelo = QComboBox()
        combo_serie = QComboBox()
        lineedit_calib = QLineEdit()
        obj.commenu.extend([combo_modelo, combo_serie, lineedit_calib])
    obj.combo_menu = obj.commenu
    return obj


def _categoria_con_layout():
    w = QWidget()
    w.setLayout(QGridLayout())
    return w


def _boton_subir(categoria):
    layout = categoria.layout()
    item = layout.itemAtPosition(23, 0)
    if item is None:
        return None
    sub = item.layout()
    if sub is None or sub.count() == 0:
        return None
    return sub.itemAt(0).widget()


def _grupo(obj, i):
    return obj.commenu[i * 3], obj.commenu[i * 3 + 1], obj.commenu[i * 3 + 2]


def _activos(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    try:
        return dict(con.execute(
            "SELECT tipo_camara, equipo_id FROM equipos_medicion "
            "WHERE ref = ? AND activo = 1", (ref,)).fetchall())
    finally:
        con.close()


def _filas_de(ruta_bd, ref, tipo_camara, activo=None):
    con = sqlite3.connect(ruta_bd)
    try:
        if activo is None:
            return con.execute(
                "SELECT model, serie, calibr_fact, fecha_calibr, equipo_id, activo "
                "FROM equipos_medicion WHERE ref = ? AND tipo_camara = ?",
                (ref, tipo_camara)).fetchall()
        return con.execute(
            "SELECT model, serie, calibr_fact, fecha_calibr, equipo_id "
            "FROM equipos_medicion WHERE ref = ? AND tipo_camara = ? AND activo = ?",
            (ref, tipo_camara, activo)).fetchall()
    finally:
        con.close()


@pytest.fixture(autouse=True)
def _sin_dialogos_criticos(monkeypatch):
    """Trampa 2: nunca dejar un QMessageBox real bajo offscreen. `warning`
    se espía por test cuando hace falta verificar el aviso."""
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


# ---------------------------------------------------------------------------
# 1. ROJO-ANTES-QUE-VERDE: cámara BORRADA del catálogo -- hoy se descarta
# ---------------------------------------------------------------------------

def test_camara_borrada_no_desaparece_al_reguardar(app, bd_temporal):
    """El caso real de ref=1/ref=40 (Principal Electrones borrada). Con 3
    cámaras guardadas y una ya borrada del catálogo, "Subir" debe escribir
    LAS 3 -- hoy escribe 2 y la tercera desaparece."""
    _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                     model="ModeloA", serie="S1", calibr_fact=1.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 20, equip_type="Electrómetro",
                     model="ModeloE", serie="S20", calibr_fact=4.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    # La cámara "Secundaria" (equipo_id=99) NO existe en `equipos` --
    # borrada, como DA-74 permite.
    ref = _insertar_control(bd_temporal)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
    _insertar_equipos_medicion(bd_temporal, ref, "Secundaria", "ModeloBorrado", "S99", 3.0, equipo_id=99)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    _, serie_secundaria, _ = _grupo(obj, 1)
    assert serie_secundaria.currentData() is None, (
        "la entrada de respaldo debe tener data=None (no inventa un id)")

    btn = _boton_subir(categoria)
    assert btn is not None
    btn.click()

    activos = _activos(bd_temporal, ref)
    assert activos == {"Principal": 1, "Secundaria": 99, "Electrómetro": 20}, (
        f"la cámara borrada desapareció del bloque vigente: {activos}")

    # La fila nueva de "Secundaria" es idéntica a la copia que existía.
    filas_nuevas = _filas_de(bd_temporal, ref, "Secundaria", activo=1)
    assert filas_nuevas == [("ModeloBorrado", "S99", 3.0, "01/01/2020", 99)]


def test_camara_anulada_tampoco_desaparece(app, bd_temporal):
    """Igual con la cámara ANULADA (activo=0), no solo borrada."""
    _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                     model="ModeloA", serie="S1", calibr_fact=1.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 99, equip_type="Cámara de ionización",
                     model="ModeloC", serie="S99", calibr_fact=3.0,
                     fecha_calibr="01/01/2024", activo=0, vigente=0)
    _insertar_equipo(bd_temporal, 20, equip_type="Electrómetro",
                     model="ModeloE", serie="S20", calibr_fact=4.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    ref = _insertar_control(bd_temporal)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
    _insertar_equipos_medicion(bd_temporal, ref, "Secundaria", "ModeloC", "S99", 3.0, equipo_id=99)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    btn = _boton_subir(categoria)
    btn.click()

    activos = _activos(bd_temporal, ref)
    assert activos.get("Secundaria") == 99, (
        f"la cámara anulada desapareció del bloque vigente: {activos}")


# ---------------------------------------------------------------------------
# 2. COMPUERTA DE CERO DIFERENCIAS: con las 3 cámaras en catálogo, igual a hoy
# ---------------------------------------------------------------------------

def test_con_todas_en_catalogo_las_filas_son_identicas_a_hoy(app, bd_temporal):
    _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                     model="ModeloA", serie="S1", calibr_fact=1.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 10, equip_type="Cámara de ionización",
                     model="ModeloC", serie="S10", calibr_fact=3.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 20, equip_type="Electrómetro",
                     model="ModeloE", serie="S20", calibr_fact=4.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    ref = _insertar_control(bd_temporal)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
    _insertar_equipos_medicion(bd_temporal, ref, "Secundaria", "ModeloC", "S10", 3.0, equipo_id=10)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    btn = _boton_subir(categoria)
    btn.click()

    activos = _activos(bd_temporal, ref)
    assert activos == {"Principal": 1, "Secundaria": 10, "Electrómetro": 20}, (
        f"el bloque nuevo no es idéntico al restaurado: {activos}")


# ---------------------------------------------------------------------------
# 3. Grupo irresoluble: cero escrituras, aviso, bloque anterior intacto
# ---------------------------------------------------------------------------

def test_grupo_irresoluble_no_escribe_nada_y_avisa(app, bd_temporal, monkeypatch):
    """Ni catálogo ni copia -- ninguna candidata en absoluto para
    'Secundaria' (Traerinfo nunca vio esa fila, así que no hay copia
    recordada). El bloque anterior debe quedar exactamente igual, y el
    aviso debe nombrar el grupo."""
    _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                     model="ModeloA", serie="S1", calibr_fact=1.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 20, equip_type="Electrómetro",
                     model="ModeloE", serie="S20", calibr_fact=4.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    ref = _insertar_control(bd_temporal)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)
    # Nota: NO se inserta fila de "Secundaria" en equipos_medicion --
    # Traerinfo no la restaura, así que ese combo se queda en
    # "Seleccionar..." (sin copia recordada).

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    # Simular que el físico eligió algo para los TRES widgets de Secundaria
    # (para pasar la compuerta previa de AV2, que exige que ningún campo
    # quede en blanco/"Seleccionar...") pero con un `equipo_id` que ya no
    # resuelve en `equipos` NI tiene copia recordada por Traerinfo -- el
    # caso "ni catálogo ni copia".
    modelo_secundaria, serie_secundaria, calibr_secundaria = _grupo(obj, 1)
    modelo_secundaria.addItem("ModeloFantasma")
    modelo_secundaria.setCurrentIndex(modelo_secundaria.findText("ModeloFantasma"))
    calibr_secundaria.setText("9.9")
    serie_secundaria.addItem("Serie: Fantasma", 12345)
    idx = serie_secundaria.findText("Serie: Fantasma")
    serie_secundaria.setCurrentIndex(idx)

    llamadas_warning = []
    monkeypatch.setattr(
        "ui.paginasControles.PruebasMensuales.seiscientos_mensual.QMessageBox.warning",
        staticmethod(lambda *a, **k: llamadas_warning.append(a)))

    btn = _boton_subir(categoria)
    btn.click()

    activos = _activos(bd_temporal, ref)
    assert activos == {"Principal": 1, "Electrómetro": 20}, (
        f"el bloque anterior debía quedar INTACTO: {activos}")
    assert llamadas_warning, "debía avisarse que un grupo no se pudo resolver"
    assert "Secundaria" in llamadas_warning[0][2]
    for simbolo in ("✓", "✗", "⚠", "❌", "✔"):
        assert simbolo not in llamadas_warning[0][2], f"DA-18: sin símbolos ({simbolo!r})"


def test_mensaje_de_exito_no_aparece_cuando_no_se_escribio(app, bd_temporal, monkeypatch):
    _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                     model="ModeloA", serie="S1", calibr_fact=1.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 20, equip_type="Electrómetro",
                     model="ModeloE", serie="S20", calibr_fact=4.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    ref = _insertar_control(bd_temporal)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    # Forzar un grupo irresoluble en Secundaria (los 3 widgets con algo,
    # para pasar la compuerta previa de AV2 -- Principal y Electrómetro ya
    # quedaron llenos por Traerinfo).
    modelo_secundaria, serie_secundaria, calibr_secundaria = _grupo(obj, 1)
    modelo_secundaria.addItem("ModeloFantasma")
    modelo_secundaria.setCurrentIndex(modelo_secundaria.findText("ModeloFantasma"))
    calibr_secundaria.setText("9.9")
    serie_secundaria.addItem("Serie: Fantasma", 12345)
    serie_secundaria.setCurrentIndex(serie_secundaria.findText("Serie: Fantasma"))

    llamadas_info = []
    monkeypatch.setattr(
        "ui.paginasControles.PruebasMensuales.seiscientos_mensual.QMessageBox.information",
        staticmethod(lambda *a, **k: llamadas_info.append(a)))

    btn = _boton_subir(categoria)
    btn.click()

    assert llamadas_info == [], "no debía mostrarse el mensaje de éxito"


# ---------------------------------------------------------------------------
# 4. El escenario REAL del iX (ref=30, electrómetro CDX-2000B/B091982)
# ---------------------------------------------------------------------------

def test_escenario_real_ix_electrometro_anulado(app, bd_temporal):
    """[medido, producción real] ref=30 (05/2026, iX): el electrómetro
    CDX-2000B/B091982 se anuló el 11-09 al pasar a Unidos-E/002343.
    Reguardar la sección de Equipos hoy le hace perder esa cámara."""
    _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                     model="N30013", serie="152342", calibr_fact=1.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 2, equip_type="Cámara de ionización",
                     model="N31022", serie="152342", calibr_fact=1.5,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 3, equip_type="Cámara de ionización",
                     model="N34001", serie="002426", calibr_fact=2.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 79, equip_type="Electrómetro",
                     model="CDX-2000B", serie="B091982", calibr_fact=1.0,
                     fecha_calibr="17/03/2026", activo=0, vigente=0)

    ref = _insertar_control(bd_temporal, equipo="Clinac iX", fecha="05/2026")
    _insertar_equipos_medicion(bd_temporal, ref, "Principal Fotones", "N30013", "152342", 1.0, equipo_id=1)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal Electrones", "N34001", "002426", 2.0, equipo_id=3)
    _insertar_equipos_medicion(bd_temporal, ref, "Secundaria", "N31022", "152342", 1.5, equipo_id=2)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "CDX-2000B", "B091982", 1.0, equipo_id=79)

    obj = _mensual_ix_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    btn = _boton_subir(categoria)
    assert btn is not None
    btn.click()

    activos = _activos(bd_temporal, ref)
    assert activos.get("Electrómetro") == 79, (
        f"el electrómetro anulado desapareció al reguardar: {activos}")
    assert len(activos) == 4, f"algún grupo se perdió: {activos}"
