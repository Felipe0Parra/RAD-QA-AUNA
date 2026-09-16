"""T.6 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §6-bis): el mensual tampoco
adivina cuál calibración era.

CAUSA. Pedido del físico (16-09): aplicar el mismo principio de "la copia
guardada manda" a los aceleradores. Al medirlo, dos de las tres reglas ya se
cumplían (los valores salen de la copia; el guardado identifica por id) y
una no: con `equipo_id` en `NULL` (54 de 61 filas vigentes, anteriores a F9,
`DA-13`), `Traerinfo` elegía la serie con `findText(f"Serie: {serie}",
Qt.MatchStartsWith)` -- se queda con la PRIMERA que empieza igual -- y si eso
fallaba, con `SELECT id ... WHERE model=? AND serie=? AND activo=1 ORDER BY
id DESC LIMIT 1` -- adivina la calibración MÁS NUEVA y le asigna su id. Al
reguardar, ese id adivinado y su `fecha_calibr` se escriben.

**[medido] hoy está latente**: ninguna serie activa tiene más de una
calibración tras los borrados del 11-09 -- pero A092535 tuvo exactamente dos
(2022 y 2025) hasta esa fecha, y el caso vuelve en cuanto se registre una
recalibración de una serie ya usada.

CAMBIO quirúrgico: los dos respaldos (texto y "la más nueva") solo actúan si
hay EXACTAMENTE UNA candidata activa con ese (model, serie). Con más de una,
no se elige ninguna -- se añade la copia guardada como entrada propia
(data=None), el mismo respaldo que ya existía para el caso "cero
candidatas". Con una sola candidata, el comportamiento es IDÉNTICO al de
siempre -- es la razón de ACOTAR en vez de retirar.
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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


# ---------------------------------------------------------------------------
# 1. ROJO-ANTES-QUE-VERDE: el caso real de A092535 (dos calibraciones)
# ---------------------------------------------------------------------------

def test_dos_calibraciones_activas_no_se_desempatan(app, bd_temporal):
    """A092535 con calibración de 2022 (id 17, factor 464700) y de 2025
    (id 63, factor distinto). Un control guardado ANTES de F9
    (`equipo_id=NULL`) con la de 2022. Sin T.6, `Traerinfo` se posiciona en
    la de id más alto (63, la de 2025) -- con T.6, no elige ninguna y
    muestra la copia."""
    _insertar_equipo(bd_temporal, 17, equip_type="Cámara de ionización",
                     model="TW33004", serie="A092535", calibr_fact=464700.0,
                     fecha_calibr="23/06/2022", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 63, equip_type="Cámara de ionización",
                     model="TW33004", serie="A092535", calibr_fact=999999.0,
                     fecha_calibr="28/07/2025", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 20, equip_type="Electrómetro",
                     model="ModeloE", serie="S20", calibr_fact=4.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)

    ref = _insertar_control(bd_temporal)
    # Fila HISTÓRICA (equipo_id=NULL, anterior a F9) guardada con la
    # calibración de 2022 -- el factor y la fecha reales que se usaron ese
    # día, en `equipos_medicion` (independiente de `equipos`, el catálogo).
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "TW33004",
                               "A092535", 464700.0, equipo_id=None,
                               fecha_calibr="23/06/2022")
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE",
                               "S20", 4.0, equipo_id=20)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    _, serie_principal, calibr_principal = _grupo(obj, 0)

    assert serie_principal.currentData() is None, (
        f"con dos candidatas NO debía elegirse ninguna -- adoptó "
        f"{serie_principal.currentData()!r} (el id de la calibración 2025 "
        f"sería {63!r}: exactamente la adivinanza que T.6 impide)")
    # El factor MOSTRADO sigue siendo el guardado, no el del catálogo.
    assert calibr_principal.text() == "464700"

    # Reguardar: al no haber id, "Subir" arrastra la copia (T.3) -- la
    # fecha_calibr y el factor deben seguir siendo los de 2022, nunca los
    # de la calibración nueva (2025).
    btn = _boton_subir(categoria)
    btn.click()

    con = sqlite3.connect(bd_temporal)
    try:
        fila = con.execute(
            "SELECT fecha_calibr, equipo_id FROM equipos_medicion "
            "WHERE ref = ? AND tipo_camara = 'Principal' AND activo = 1",
            (ref,)).fetchone()
    finally:
        con.close()

    assert fila == ("23/06/2022", None), (
        f"reguardar escribió una fecha_calibr o un id que NADIE eligió: {fila}")


# ---------------------------------------------------------------------------
# 2. COMPUERTA DE CERO DIFERENCIAS: con una sola candidata, igual a siempre
# ---------------------------------------------------------------------------

def test_una_sola_candidata_se_comporta_igual_que_siempre(app, bd_temporal):
    """El escenario de `test_e2e3_seccion_equipos::
    test_restaura_por_texto_y_guarda_con_equipo_id_resuelto`, repetido aquí
    para fijar la compuerta explícitamente: con UNA sola candidata activa,
    T.6 no cambia nada."""
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
    _insertar_equipos_medicion(bd_temporal, ref, "Secundaria", "ModeloC", "S10", 3.0, equipo_id=None)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    _, serie_secundaria, _ = _grupo(obj, 1)
    assert serie_secundaria.currentData() == 10, (
        "con una sola candidata, debía resolverse igual que siempre "
        f"(currentData={serie_secundaria.currentData()})")

    btn = _boton_subir(categoria)
    btn.click()

    activos = _activos(bd_temporal, ref)
    assert activos == {"Principal": 1, "Secundaria": 10, "Electrómetro": 20}


# ---------------------------------------------------------------------------
# 3. Cero candidatas: igual que hoy, entrada de respaldo
# ---------------------------------------------------------------------------

def test_cero_candidatas_sigue_agregando_la_entrada_de_respaldo(app, bd_temporal):
    """Cámara borrada o anulada (cero candidatas activas) -- T.6 no toca
    este caso, ya cubierto por T.1/T.3."""
    _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                     model="ModeloA", serie="S1", calibr_fact=1.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 20, equip_type="Electrómetro",
                     model="ModeloE", serie="S20", calibr_fact=4.0,
                     fecha_calibr="01/01/2024", activo=1, vigente=1)
    ref = _insertar_control(bd_temporal)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
    # "Secundaria" -- serie que ya NO está en el catálogo (borrada).
    _insertar_equipos_medicion(bd_temporal, ref, "Secundaria", "ModeloBorrado", "S99", 3.0, equipo_id=None)
    _insertar_equipos_medicion(bd_temporal, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    _, serie_secundaria, calibr_secundaria = _grupo(obj, 1)
    assert serie_secundaria.currentData() is None
    assert serie_secundaria.currentText() == "Serie: S99"
    assert calibr_secundaria.text() == "3"


# ---------------------------------------------------------------------------
# 4. El factor mostrado sigue siendo el guardado en los TRES casos
# ---------------------------------------------------------------------------

def test_factor_mostrado_es_siempre_el_guardado(app, bd_temporal):
    """Compuerta explícita del principio: nunca el del catálogo."""
    # Caso "varias candidatas"
    _insertar_equipo(bd_temporal, 17, equip_type="Cámara de ionización",
                     model="TW33004", serie="A092535", calibr_fact=464700.0,
                     fecha_calibr="23/06/2022", activo=1, vigente=1)
    _insertar_equipo(bd_temporal, 63, equip_type="Cámara de ionización",
                     model="TW33004", serie="A092535", calibr_fact=999999.0,
                     fecha_calibr="28/07/2025", activo=1, vigente=1)
    ref = _insertar_control(bd_temporal)
    _insertar_equipos_medicion(bd_temporal, ref, "Principal", "TW33004",
                               "A092535", 464700.0, equipo_id=None)

    obj = _mensual_pelado(ref)
    categoria = _categoria_con_layout()
    obj.botonescombobox(categoria, obj.commenu, None)

    _, _, calibr_principal = _grupo(obj, 0)
    assert calibr_principal.text() == "464700", (
        "el factor mostrado debe ser el GUARDADO, no el del catálogo "
        "(999999.0 sería la calibración nueva, adivinada)")


# ---------------------------------------------------------------------------
# 5. Trampa 5: censo por AST de la función real -- que el bloque de conteo
#    exista de verdad, no solo en este test.
# ---------------------------------------------------------------------------

def test_traerinfo_cuenta_candidatas_antes_de_adivinar():
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parent.parent
    texto = (raiz / "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py"
             ).read_text(encoding="utf-8", errors="replace")
    assert "candidatas = cursor.fetchall()" in texto
    assert "len(candidatas) == 1" in texto
    assert "len(candidatas) > 1" in texto
