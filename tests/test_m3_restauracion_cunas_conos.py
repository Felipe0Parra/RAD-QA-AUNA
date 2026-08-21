"""M3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §M3): el formulario
restaura cuñas y conos.

Dos mitades con distinto punto de partida (§2.2 del plan): cuñas YA
restauraba (`Traerinfo_cunas` existía y funcionaba) -- solo le faltaban dos
garantías, obligatorias tras M2 (que deja el historial anulado acumulado en
la misma tabla): filtrar `activo = 1` y desempatar de forma determinista.
Conos NUNCA tuvo lectura -- se escribe `Traerinfo_conos` desde cero, con la
misma simetría.

Debe funcionar en los tres caminos que nombró el físico: reabrir el
formulario, cerrar y volver a entrar, y reactivar un control anulado. Este
archivo cubre los tres, más el contrato conjunto M1+M2+M3 de §6.2: guardar 3
veces con valores distintos en la 3a deja un bloque activo con esos valores,
y reabrir muestra ese bloque -- igual en cuñas que en conos.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QDialog, QGridLayout, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QWidget,
)

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
import ui.paginasGuia.dialogs as dialogs_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import create_control
from data.ManejoDatos.user import Usuario
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


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


class _ComboFalso:
    def __init__(self, texto="Funciona"):
        self._texto = texto

    def currentText(self):
        return self._texto


def _insertar_control(ruta_bd, equipo="Clinac ix", control="Mensual", fecha="06/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _mensual_pelado(ref, clase=PruebaMensual600, esIX=False):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.ref = ref
    if esIX:
        obj.esIX = True
    return obj


def _combos_cunas(valor="Funciona"):
    return {ang: {k: _ComboFalso(valor) for k in ("in", "out", "right", "left")}
            for ang in (15, 30, 45, 60)}


def _instancia_ix_con_botones_conos(ref, valor):
    obj = _mensual_pelado(ref, clase=PruebaMensualIX, esIX=True)
    for medida in ("6", "10", "15", "20", "25"):
        fun, nofun = QPushButton(), QPushButton()
        fun.setCheckable(True)
        nofun.setCheckable(True)
        if valor == 1:
            fun.setChecked(True)
        elif valor == 0:
            nofun.setChecked(True)
        setattr(obj, f"btn_{medida}_fun", fun)
        setattr(obj, f"btn_{medida}_nofun", nofun)
    return obj


def _crear_botones_conos_vacios(obj):
    """Widgets de conos sin marcar -- el estado que deja `iniGUI` recién
    construido, antes de restaurar nada."""
    for medida in ("6", "10", "15", "20", "25"):
        fun, nofun = QPushButton(), QPushButton()
        fun.setCheckable(True)
        nofun.setCheckable(True)
        setattr(obj, f"btn_{medida}_fun", fun)
        setattr(obj, f"btn_{medida}_nofun", nofun)


class TestTraerinfoCunasFiltraActivoYDesempata:
    def test_ignora_un_bloque_anulado_y_restaura_el_activo(self, app, bd_temporal, monkeypatch):
        mensual_mod = __import__(
            "ui.paginasControles.PruebasMensuales.seiscientos_mensual", fromlist=["x"])
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        ref = _insertar_control(bd_temporal, equipo="Clinac 600")

        obj = _mensual_pelado(ref)
        obj.subir_control_cunas(_combos_cunas("Funciona"))   # queda anulado
        obj.subir_control_cunas(_combos_cunas("No funciona"))  # el activo

        # Formulario "nuevo" -- combos recién creados, sin valor.
        from PyQt5.QtWidgets import QComboBox
        for ang in (15, 30, 45, 60):
            for pos, attr in (("in", "in"), ("out", "out"), ("right", "ri"), ("left", "le")):
                combo = QComboBox()
                combo.addItems(["Seleccionar...", "Funciona", "No funciona"])
                setattr(obj, f"cuna_{ang}_{attr}", combo)

        assert obj.Traerinfo_cunas() is True
        for ang in (15, 30, 45, 60):
            assert getattr(obj, f"cuna_{ang}_in").currentText() == "No funciona"
            assert getattr(obj, f"cuna_{ang}_out").currentText() == "No funciona"
            assert getattr(obj, f"cuna_{ang}_ri").currentText() == "No funciona"
            assert getattr(obj, f"cuna_{ang}_le").currentText() == "No funciona"

    def test_fila_anulada_desde_ver_tabla_no_se_restaura_aunque_sea_la_mas_reciente(
            self, app, bd_temporal, monkeypatch):
        """El caso real que exige el filtro `activo`, distinto del orden de
        escritura de M2: una fila del bloque ACTIVO se anula puntualmente
        desde el popup "Ver tabla" (`anular_fila`, por id, no por bloque) --
        sigue siendo la fila de mayor id para ese ángulo, así que SIN el
        filtro `activo = 1` un `ORDER BY angulo` (sin desempate) la
        seguiría devolviendo como si fuera vigente."""
        mensual_mod = __import__(
            "ui.paginasControles.PruebasMensuales.seiscientos_mensual", fromlist=["x"])
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        ref = _insertar_control(bd_temporal, equipo="Clinac 600")

        obj = _mensual_pelado(ref)
        obj.subir_control_cunas(_combos_cunas("Funciona"))  # único bloque, activo

        con = sqlite3.connect(bd_temporal)
        id_fila_15 = con.execute(
            "SELECT id FROM control_cunas WHERE ref = ? AND angulo = 15", (ref,)
        ).fetchone()[0]
        # Simula el "Ver tabla" -> anular UNA fila puntual (services.anulacion
        # .anular_fila hace exactamente este UPDATE por id).
        con.execute("UPDATE control_cunas SET activo = 0 WHERE id = ?", (id_fila_15,))
        con.commit()
        con.close()

        from PyQt5.QtWidgets import QComboBox
        obj_reabierto = _mensual_pelado(ref)
        for ang in (15, 30, 45, 60):
            for attr in ("in", "out", "ri", "le"):
                combo = QComboBox()
                combo.addItems(["Seleccionar...", "Funciona", "No funciona"])
                setattr(obj_reabierto, f"cuna_{ang}_{attr}", combo)

        # El ángulo 15 quedó sin ninguna fila activa -- no debe restaurarse
        # como "Funciona" (lo que devolvería un ORDER BY angulo sin filtro).
        obj_reabierto.Traerinfo_cunas()
        assert getattr(obj_reabierto, "cuna_15_in").currentText() != "Funciona"
        # Los otros 3 ángulos, intactos, sí se restauran.
        assert getattr(obj_reabierto, "cuna_30_in").currentText() == "Funciona"


class TestTraerinfoConosFiltraActivoYDesempata:
    def test_ignora_un_bloque_anulado_y_restaura_el_activo(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        _instancia_ix_con_botones_conos(ref, 1).guardar_control_conos()   # queda anulado
        obj_v2 = _instancia_ix_con_botones_conos(ref, 0)
        obj_v2.guardar_control_conos()  # el activo

        obj_nuevo = _mensual_pelado(ref, clase=PruebaMensualIX, esIX=True)
        _crear_botones_conos_vacios(obj_nuevo)

        assert obj_nuevo.Traerinfo_conos() is True
        for medida in ("6", "10", "15", "20", "25"):
            assert getattr(obj_nuevo, f"btn_{medida}_fun").isChecked() is False
            assert getattr(obj_nuevo, f"btn_{medida}_nofun").isChecked() is True


class TestBotonescomboboxRestauraConosDesdeElArmadoDelFormulario:
    """Confirma en el punto real del armado (botonescombobox, el mismo que
    llama a Traerinfo_cunas) que conos se restaura -- no solo que la función
    aislada funciona."""

    def test_conos_se_restaura_al_llamar_botonescombobox(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        _instancia_ix_con_botones_conos(ref, 1).guardar_control_conos()

        obj = _mensual_pelado(ref, clase=PruebaMensualIX, esIX=True)
        _crear_botones_conos_vacios(obj)
        obj.combos_seguridad = _combos_cunas("Funciona")

        categoria = QWidget()
        categoria.setLayout(QGridLayout())

        obj.botonescombobox(categoria, None, obj.combos_seguridad)

        for medida in ("6", "10", "15", "20", "25"):
            assert getattr(obj, f"btn_{medida}_fun").isChecked() is True
            assert getattr(obj, f"btn_{medida}_nofun").isChecked() is False

    def test_600_no_intenta_restaurar_conos_pues_no_tiene_esos_widgets(self, app, bd_temporal):
        """600 no es iX -- botonescombobox no debe reventar buscando
        Traerinfo_conos, que ni siquiera existe en esa clase."""
        ref = _insertar_control(bd_temporal, equipo="Clinac 600")
        obj = _mensual_pelado(ref)
        obj.combos_seguridad = _combos_cunas("Funciona")

        categoria = QWidget()
        categoria.setLayout(QGridLayout())

        obj.botonescombobox(categoria, None, obj.combos_seguridad)  # no debe lanzar


class TestContratoM1M2M3CunasYConos:
    """§6.2 del plan: guardar 3 veces con valores distintos en la 3a ->
    un bloque activo con los valores de la 3a, dos anulados, y reabrir
    muestra los de la 3a. Igual en cuñas que en conos."""

    def test_cunas(self, app, bd_temporal, monkeypatch):
        mensual_mod = __import__(
            "ui.paginasControles.PruebasMensuales.seiscientos_mensual", fromlist=["x"])
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        ref = _insertar_control(bd_temporal, equipo="Clinac 600")

        obj = _mensual_pelado(ref)
        obj.subir_control_cunas(_combos_cunas("Funciona"))
        obj.subir_control_cunas(_combos_cunas("Funciona"))
        obj.subir_control_cunas(_combos_cunas("No funciona"))

        con = sqlite3.connect(bd_temporal)
        activos = con.execute(
            "SELECT COUNT(*) FROM control_cunas WHERE ref = ? AND activo = 1", (ref,)
        ).fetchone()[0]
        anulados = con.execute(
            "SELECT COUNT(*) FROM control_cunas WHERE ref = ? AND activo = 0", (ref,)
        ).fetchone()[0]
        con.close()
        assert activos == 4
        assert anulados == 8

        # "Reabrir": formulario nuevo, combos vacíos.
        from PyQt5.QtWidgets import QComboBox
        obj_reabierto = _mensual_pelado(ref)
        for ang in (15, 30, 45, 60):
            for attr in ("in", "out", "ri", "le"):
                combo = QComboBox()
                combo.addItems(["Seleccionar...", "Funciona", "No funciona"])
                setattr(obj_reabierto, f"cuna_{ang}_{attr}", combo)

        assert obj_reabierto.Traerinfo_cunas() is True
        for ang in (15, 30, 45, 60):
            assert getattr(obj_reabierto, f"cuna_{ang}_in").currentText() == "No funciona"

    def test_conos(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        _instancia_ix_con_botones_conos(ref, 1).guardar_control_conos()
        _instancia_ix_con_botones_conos(ref, 1).guardar_control_conos()
        _instancia_ix_con_botones_conos(ref, 0).guardar_control_conos()

        con = sqlite3.connect(bd_temporal)
        activos = con.execute(
            "SELECT COUNT(*) FROM control_conos WHERE ref = ? AND activo = 1", (ref,)
        ).fetchone()[0]
        anulados = con.execute(
            "SELECT COUNT(*) FROM control_conos WHERE ref = ? AND activo = 0", (ref,)
        ).fetchone()[0]
        con.close()
        assert activos == 5
        assert anulados == 10

        obj_reabierto = _mensual_pelado(ref, clase=PruebaMensualIX, esIX=True)
        _crear_botones_conos_vacios(obj_reabierto)
        assert obj_reabierto.Traerinfo_conos() is True
        for medida in ("6", "10", "15", "20", "25"):
            assert getattr(obj_reabierto, f"btn_{medida}_fun").isChecked() is False
            assert getattr(obj_reabierto, f"btn_{medida}_nofun").isChecked() is True


class _UsuarioAdminFalso:
    _nombre = "Administrador"


class _DlgEliminarFalso:
    user_id = _UsuarioAdminFalso()


def _formulario_para_create_control():
    w = QWidget()
    w.user_id = Usuario(username="fisico", fullname="Físico de Prueba")
    return w


class TestReactivarRestauraCunasYConos:
    """El tercer camino que nombró el físico -- anular un control y volver
    a abrir el mes -- **reescrito por LR7** (PLAN_CONTRATO_COMPLETO_19-08.md
    §6-LR7, [[DA-49]]): ya no se reactiva. `create_control` ignora el
    anulado y crea uno NUEVO al lado (legal: el índice único de U2 es
    parcial sobre las filas activas). Cuñas/conos son tablas HIJAS de
    `controles` -- anular la raíz nunca las toca (E7/DA-03) -- así que el
    invariante que importa ahora es el mismo de siempre leído al revés:
    los datos del control anulado NO se pierden (siguen en la BD, visibles
    desde el visor de LR6), y el control NUEVO empieza sin ellos -- nunca
    los hereda."""

    def test_anular_y_reabrir_crea_control_nuevo_sin_perder_los_datos_del_anulado(
            self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        mensual_mod = __import__(
            "ui.paginasControles.PruebasMensuales.seiscientos_mensual", fromlist=["x"])
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))

        # 1. Crear el control y guardar cuñas + conos.
        control_id = create_control(
            _formulario_para_create_control(), "Clinac ix", "05/08/2026", "Físico de Prueba")
        assert control_id is not None

        obj = _mensual_pelado(control_id, clase=PruebaMensualIX, esIX=True)
        obj.subir_control_cunas(_combos_cunas("Funciona"), auditar=False)
        _instancia_ix_con_botones_conos(control_id, 1).guardar_control_conos()

        # 2. Anular el control (misma vía que "Registros" -> Eliminar).
        monkeypatch.setattr(load_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.Yes))
        tabla = QTableWidget(1, 1)
        item = QTableWidgetItem("fila")
        item.setData(Qt.UserRole, control_id)
        tabla.setItem(0, 0, item)
        tabla.setCurrentCell(0, 0)
        load_mod.eliminarRegistro(_DlgEliminarFalso(), tabla, "controles")

        con = sqlite3.connect(bd_temporal)
        assert con.execute(
            "SELECT activo FROM controles WHERE id = ?", (control_id,)
        ).fetchone()[0] == 0
        con.close()

        # 3. Reabrir el mismo mes: LR7 retiró la reactivación -- se ignora
        #    el anulado y se crea un control NUEVO al lado.
        control_id_nuevo = create_control(
            _formulario_para_create_control(), "Clinac ix", "20/08/2026", "Físico de Prueba")
        assert control_id_nuevo != control_id, (
            "DA-49: debe crear un control NUEVO, no reactivar el anulado")

        con = sqlite3.connect(bd_temporal)
        activo_viejo = con.execute(
            "SELECT activo FROM controles WHERE id = ?", (control_id,)).fetchone()[0]
        activo_nuevo = con.execute(
            "SELECT activo FROM controles WHERE id = ?", (control_id_nuevo,)).fetchone()[0]
        con.close()
        assert activo_viejo == 0, "el control anulado nunca se toca -- nunca se reactiva"
        assert activo_nuevo == 1

        # 4. Los datos del control ANULADO siguen intactos en la BD -- E7/
        #    DA-03, soft-delete de la raíz nunca borra las hijas.
        con = sqlite3.connect(bd_temporal)
        n_cunas = con.execute(
            "SELECT COUNT(*) FROM control_cunas WHERE ref = ?", (control_id,)).fetchone()[0]
        n_conos = con.execute(
            "SELECT COUNT(*) FROM control_conos WHERE ref = ?", (control_id,)).fetchone()[0]
        con.close()
        assert n_cunas == 4, "las 4 cuñas del control anulado deben seguir ahí"
        assert n_conos == 5, "los 5 conos del control anulado deben seguir ahí"

        # 5. ... y son visibles desde el visor de LR6, el reemplazo de la
        #    reactivación como forma de "llegar" a un registro anulado.
        import services.visor_anulados as visor
        _, filas_cunas = visor.filas_de("control_cunas")
        _, filas_conos = visor.filas_de("control_conos")
        assert all(f["estado"] == "vigente" for f in filas_cunas), (
            "las cuñas cuelgan del control anulado, pero ellas mismas no "
            "se anulan -- E7/DA-03 anula la raíz, no sus hijas")
        assert len(filas_cunas) == 4
        assert len(filas_conos) == 5

        # 6. El control NUEVO, sin cuñas/conos propios, no hereda nada del
        #    anulado -- Traerinfo_* debe reportar que no hay nada que
        #    restaurar para ESTE id.
        obj_nuevo = _mensual_pelado(control_id_nuevo, clase=PruebaMensualIX, esIX=True)
        from PyQt5.QtWidgets import QComboBox
        for ang in (15, 30, 45, 60):
            for attr in ("in", "out", "ri", "le"):
                combo = QComboBox()
                combo.addItems(["Seleccionar...", "Funciona", "No funciona"])
                setattr(obj_nuevo, f"cuna_{ang}_{attr}", combo)
        _crear_botones_conos_vacios(obj_nuevo)

        assert obj_nuevo.Traerinfo_cunas() is False
        assert obj_nuevo.Traerinfo_conos() is False
        for ang in (15, 30, 45, 60):
            assert getattr(obj_nuevo, f"cuna_{ang}_in").currentText() == "Seleccionar..."
