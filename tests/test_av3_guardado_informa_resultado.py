"""AV3 (PLAN_CONTRATO_GUARDADO_13-08.md §6-AV): tripwire de las dos mitades
de la FASE AV -- ningún guardado del bloque de QC puede fallar en silencio.

Antes de AV1/AV2, dos caminos distintos llegaban al mismo síntoma (H3, H4):
la pantalla se veía igual si el guardado salía bien o si fallaba/no hacía
nada.

1. AV1: si `loadtablacomplex` falla (rollback), `guardar_todas_fse` (anual
   600 -- compartido con Halcyon anual por herencia) debe avisar con
   `QMessageBox.critical` Y no debe auditar una acción que en realidad no
   ocurrió.
2. AV2: si un combo/lineedit de la sección de Equipos del mensual queda sin
   completar, `subir()` debe avisar CUÁL falta con `QMessageBox.warning`
   (nombrando el campo, no en silencio), no debe llamar
   `subirtodo_modificado`, y no debe auditar nada.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QGridLayout, QHBoxLayout, QLineEdit,
    QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasAnuales.seiscientos_anual as anual_mod
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
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


def _audit_log(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute("SELECT accion, tabla, ref FROM audit_log").fetchall()
    con.close()
    return filas


def _boton_de(layout):
    """Los botones de _agregar_botones_tabla van dentro de un QHBoxLayout
    anidado (layout.addLayout(button_layout)), no directo."""
    return layout.itemAt(0).layout().itemAt(0).widget()


# --------------------------------------------------------------------
# AV1 -- guardar_todas_fse (anual) avisa si loadtablacomplex falla
# --------------------------------------------------------------------

def _anual_pelado(clase):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    obj.anual = True
    return obj


class TestAV1FalloDeGuardadoAvisaYNoAudita:
    def test_loadtablacomplex_falla_avisa_critical_y_no_audita(
            self, app, bd_temporal, monkeypatch):
        avisos_error = []
        avisos_exito = []
        # CLAUDE.md, trampa #3: nunca levantar (pytest.fail/raise) dentro de
        # un mock invocado desde un signal de Qt -- la excepción no puede
        # cruzar la frontera C++ del slot y aborta el proceso entero. Se
        # graba y se afirma DESPUÉS de btn.click(), nunca durante.
        monkeypatch.setattr(anual_mod, "loadtablacomplex", lambda *a, **k: False)
        monkeypatch.setattr(
            anual_mod.QMessageBox, "critical",
            staticmethod(lambda *a, **k: avisos_error.append(a)))
        monkeypatch.setattr(
            anual_mod.QMessageBox, "information",
            staticmethod(lambda *a, **k: avisos_exito.append(a)))

        obj = _anual_pelado(PruebaAnual600)
        obj.ref = 21
        layout = QHBoxLayout()
        tabla = object()

        obj._agregar_botones_tabla(layout, tabla, "tabla_fc", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        assert avisos_error, (
            "loadtablacomplex falló pero guardar_todas_fse no avisó con "
            "QMessageBox.critical -- volvió a fallar en silencio (H3)")
        assert not avisos_exito, "no debe confirmar éxito -- loadtablacomplex devolvió False"
        assert _audit_log(bd_temporal) == [], (
            "se auditó ACCION_GUARDAR para un guardado que en realidad falló")

    def test_loadtablacomplex_exitoso_no_dispara_critical(
            self, app, bd_temporal, monkeypatch):
        """Contraparte: el camino feliz no debe volverse ruidoso por error."""
        avisos_error = []
        monkeypatch.setattr(anual_mod, "loadtablacomplex", lambda *a, **k: True)
        monkeypatch.setattr(
            anual_mod.QMessageBox, "critical",
            staticmethod(lambda *a, **k: avisos_error.append(a)))
        monkeypatch.setattr(
            anual_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))

        obj = _anual_pelado(PruebaAnual600)
        obj.ref = 22
        layout = QHBoxLayout()
        tabla = object()

        obj._agregar_botones_tabla(layout, tabla, "tabla_fta", obj.ref)
        btn = _boton_de(layout)
        btn.click()

        assert not avisos_error, "no debía avisar error -- loadtablacomplex devolvió True"
        assert len(_audit_log(bd_temporal)) == 1, (
            "un guardado exitoso sí debe quedar auditado")


# --------------------------------------------------------------------
# AV2 -- subir() (Equipos, mensual) avisa y nombra el combo vacío
# --------------------------------------------------------------------

def _mensual_pelado(ref):
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.ref = ref
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 6, 1))
    return obj


def _categoria_con_layout():
    w = QWidget()
    w.setLayout(QGridLayout())
    return w


def _boton_subir(categoria):
    layout = categoria.layout()
    item = layout.itemAtPosition(23, 0)
    sub = item.layout()
    return sub.itemAt(0).widget()


def _insertar_control(ruta_bd, equipo="Clinac 600", fecha="06/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, "Mensual", fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _insertar_equipo(ruta_bd, eq_id, model, serie, equip_type="Cámara de ionización"):
    """`conectarDB` puebla el combo de modelos SOLO con lo que encuentra en
    `equipos` (activo=1) -- un ítem agregado a mano antes de llamarla se
    pierde: `conectarDB` hace `grupo[0].clear()` primero (mismo mecanismo
    que ya usa `_insertar_equipo` de test_e2e3_seccion_equipos.py)."""
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO equipos (id, equip_type, model, serie, activo, vigente) "
        "VALUES (?, ?, ?, ?, 1, 1)",
        (eq_id, equip_type, model, serie))
    con.commit()
    con.close()


class TestAV2ComboFaltanteAvisaYNoGuarda:
    def test_combo_vacio_nombra_el_campo_y_no_guarda(
            self, app, bd_temporal, monkeypatch):
        ref = _insertar_control(bd_temporal)
        _insertar_equipo(bd_temporal, 1, "ModeloA", "S1")

        avisos_faltante = []
        avisos_exito = []
        # CLAUDE.md, trampa #3: nunca levantar (pytest.fail/raise) dentro de
        # un mock invocado desde un signal de Qt -- la excepción no puede
        # cruzar la frontera C++ del slot y aborta el proceso entero. Se
        # graba y se afirma DESPUÉS de btn.click(), nunca durante.
        monkeypatch.setattr(
            mensual_mod.QMessageBox, "warning",
            staticmethod(lambda *a, **k: avisos_faltante.append(a)))
        monkeypatch.setattr(
            mensual_mod.QMessageBox, "information",
            staticmethod(lambda *a, **k: avisos_exito.append(a)))

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        # `conectarDB` (dentro de botonescombobox) puebla el combo de
        # modelos desde la BD -- se llama ANTES de tocar los widgets a
        # mano, igual que en producción.
        combo_modelo = QComboBox()
        combo_modelo.setObjectName("combo_modelo_600_1")
        combo_serie = QComboBox()
        combo_serie.setObjectName("combo_serie_600_1")
        lineedit_calib = QLineEdit()
        lineedit_calib.setObjectName("lineedit_calib_600_1")

        obj.combo_menu = [combo_modelo, combo_serie, lineedit_calib]

        llamadas_guardado = []
        obj.subirtodo_modificado = lambda datos: llamadas_guardado.append(datos)
        obj._actualizar_tabla_despues_subida = lambda: None

        obj.botonescombobox(categoria, obj.combo_menu, None)

        # Modelo SÍ seleccionado y calibración SÍ diligenciada -- solo la
        # serie (H4: el combo que en producción queda en 'Seleccionar...'
        # tras repoblarse) se deja sin tocar.
        combo_modelo.setCurrentText("ModeloA")
        lineedit_calib.setText("1.0")

        btn = _boton_subir(categoria)
        btn.click()

        assert avisos_faltante, (
            "faltaba un combo por seleccionar pero subir() no avisó -- "
            "volvió a fallar en silencio (H4)")
        assert "combo_serie_600_1" in avisos_faltante[0][2], (
            f"el aviso no nombra el combo vacío: {avisos_faltante[0]}")
        assert not avisos_exito, "no debe confirmar éxito -- falta un combo"
        assert llamadas_guardado == [], (
            "no debía escribir nada con un combo sin completar")
        assert _audit_log(bd_temporal) == []

    def test_todos_los_combos_completos_guarda_normal(
            self, app, bd_temporal, monkeypatch):
        """Contraparte: el camino feliz no debe volverse ruidoso por error."""
        ref = _insertar_control(bd_temporal)
        _insertar_equipo(bd_temporal, 1, "ModeloA", "S1")

        avisos_faltante = []
        avisos_exito = []
        monkeypatch.setattr(
            mensual_mod.QMessageBox, "warning",
            staticmethod(lambda *a, **k: avisos_faltante.append(a)))
        monkeypatch.setattr(
            mensual_mod.QMessageBox, "information",
            staticmethod(lambda *a, **k: avisos_exito.append(a)))

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        combo_modelo = QComboBox()
        combo_modelo.setObjectName("combo_modelo_600_1")
        combo_serie = QComboBox()
        combo_serie.setObjectName("combo_serie_600_1")
        lineedit_calib = QLineEdit()
        lineedit_calib.setObjectName("lineedit_calib_600_1")

        obj.combo_menu = [combo_modelo, combo_serie, lineedit_calib]

        llamadas_guardado = []
        obj.subirtodo_modificado = lambda datos: llamadas_guardado.append(datos)
        obj._actualizar_tabla_despues_subida = lambda: None

        obj.botonescombobox(categoria, obj.combo_menu, None)

        combo_modelo.setCurrentText("ModeloA")
        combo_serie.addItem("S1")  # `conectarDB` no repuebla el de serie
        lineedit_calib.setText("1.0")

        btn = _boton_subir(categoria)
        btn.click()

        assert not avisos_faltante, (
            f"no debía avisar de campos faltantes -- todos están completos: "
            f"{avisos_faltante}")
        assert avisos_exito, "un guardado completo sí debe confirmarse"
        assert llamadas_guardado == [["ModeloA", "S1", "1.0"]]
