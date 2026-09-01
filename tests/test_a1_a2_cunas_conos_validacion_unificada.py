"""A1/A2 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase A, R1):

**A1**: un combo de cuña dejado en "Seleccionar..." colapsaba en `0` ("No
funciona") -- `valor = 1 if texto.lower() == "funciona" else 0` no tenía
tercer estado. Evidencia real: `ref=50` del rebuild, 4 filas en
`control_cunas` con las 4 posiciones en `0` sin que el físico las hubiera
tocado. Ahora, igual que los conos (DA-37), si queda algún combo sin marcar
no se escribe NADA y se avisa nombrando ángulo+posición.

**A2**: antes, `guardar_todo_ix` guardaba conos y cuñas por separado -- si
faltaba un cono, esa tabla avisaba y no escribía, pero las cuñas se
guardaban igual (doble mensaje contradictorio: "falta un cono" seguido de
"cargados exitosamente"). Ahora se valida TODO antes de escribir NADA: un
solo aviso, y si falta cualquier cosa, ninguna de las dos tablas se toca.

El test negativo de A2 (`test_conos_incompletos_bloquea_tambien_las_cunas`)
es el que prueba lo que ya NO debe ocurrir -- la fila que antes se
fabricaba en `control_cunas` aunque `control_conos` bloqueara.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QMessageBox, QPushButton, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600

ANGULOS = (15, 30, 45, 60)
POSICIONES = ("in", "out", "right", "left")
MEDIDAS = ("6", "10", "15", "20", "25")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = conexion.con
    con.execute("INSERT INTO users (fullname) VALUES ('fisico de prueba')")
    # idx_controles_unico_mes es único por (equipo, mes/año, tipo) -- cada
    # ref usado en los tests va en un mes distinto para no chocar entre sí.
    for ref, mes in ((50, "01"), (77, "02"), (78, "03"), (79, "04"), (80, "05")):
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, user_id) "
            "VALUES (?, 'Clinac ix', 'Mensual', ?, 'fisico de prueba')",
            (ref, f"01/{mes}/2026"))
    con.commit()
    yield con
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def avisos(monkeypatch):
    """Trampa 2 de CLAUDE.md: mockea warning/information/critical y
    registra qué se llamó y con qué texto, para verificar tanto que NO se
    cuelgue el test como el contenido exacto del aviso (A2 exige un solo
    mensaje que nombre qué falta)."""
    capturados = {"warning": [], "information": [], "critical": []}
    for nombre in capturados:
        monkeypatch.setattr(
            QMessageBox, nombre,
            lambda *a, _n=nombre, **k: capturados[_n].append(a[1:]))
    return capturados


def _combos_seguridad(sin_marcar=()):
    combos = {}
    for angulo in ANGULOS:
        combos[angulo] = {}
        for pos in POSICIONES:
            combo = QComboBox()
            combo.addItems(["Seleccionar...", "Funciona", "No funciona"])
            if (angulo, pos) not in sin_marcar:
                combo.setCurrentText("Funciona")
            combos[angulo][pos] = combo
    return combos


def _boton_checkable():
    b = QPushButton()
    b.setCheckable(True)
    return b


def _obj_600(ref, sin_marcar=()):
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.ref = ref
    obj.user_id = None
    obj.combos_seguridad = _combos_seguridad(sin_marcar)
    obj.df_seg_line = []
    return obj


def _obj_ix(ref, cunas_sin_marcar=(), conos_sin_marcar=()):
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.ref = ref
    obj.user_id = None
    obj.combos_seguridad = _combos_seguridad(cunas_sin_marcar)
    obj.df_seg_line = []
    for medida in MEDIDAS:
        setattr(obj, f"btn_{medida}_fun", _boton_checkable())
        setattr(obj, f"btn_{medida}_nofun", _boton_checkable())
        if medida not in conos_sin_marcar:
            getattr(obj, f"btn_{medida}_fun").setChecked(True)
    return obj


def _filas_cunas(con, ref):
    return con.execute(
        "SELECT angulo, in_val, out_val, right_val, left_val "
        "FROM control_cunas WHERE ref = ? AND (activo IS NULL OR activo = 1)",
        (ref,)).fetchall()


def _filas_conos(con, ref):
    return con.execute(
        "SELECT medida, valor FROM control_conos "
        "WHERE ref = ? AND (activo IS NULL OR activo = 1)", (ref,)).fetchall()


class TestA1UnComboSinMarcarBloqueaTodoElGuardado:

    def test_no_escribe_ninguna_fila(self, app, bd_temporal, avisos):
        obj = _obj_600(ref=50, sin_marcar={(15, "in")})

        resultado = obj.subir_control_cunas(obj.combos_seguridad, obj.df_seg_line)

        assert resultado is False
        assert _filas_cunas(bd_temporal, 50) == []

    def test_avisa_nombrando_angulo_y_posicion(self, app, bd_temporal, avisos):
        obj = _obj_600(ref=50, sin_marcar={(15, "in")})

        obj.subir_control_cunas(obj.combos_seguridad, obj.df_seg_line)

        assert len(avisos["warning"]) == 1
        texto = " ".join(str(x) for x in avisos["warning"][0])
        assert "15" in texto and "in" in texto

    def test_varios_combos_sin_marcar_se_nombran_todos(self, app, bd_temporal, avisos):
        obj = _obj_600(ref=50, sin_marcar={(15, "in"), (30, "left")})

        obj.subir_control_cunas(obj.combos_seguridad, obj.df_seg_line)

        texto = " ".join(str(x) for x in avisos["warning"][0])
        assert "15" in texto and "30" in texto


class TestA1TodosMarcadosGuardaComoAntes:

    def test_escribe_las_4_filas_por_angulo(self, app, bd_temporal, avisos):
        obj = _obj_600(ref=50, sin_marcar=())

        resultado = obj.subir_control_cunas(obj.combos_seguridad, obj.df_seg_line)

        assert resultado is True
        filas = _filas_cunas(bd_temporal, 50)
        assert len(filas) == 4  # una por ángulo
        assert avisos["information"], "debe avisar éxito"
        assert not avisos["warning"]

    def test_no_funciona_se_guarda_como_0_de_verdad(self, app, bd_temporal, avisos):
        """Distingue el `0` FABRICADO (A1) del `0` REAL: si el físico
        marcó explícitamente "No funciona", eso SÍ debe guardarse como 0."""
        combos = _combos_seguridad()
        combos[15]["in"].setCurrentText("No funciona")
        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj.ref = 50
        obj.user_id = None
        obj.combos_seguridad = combos
        obj.df_seg_line = []

        obj.subir_control_cunas(obj.combos_seguridad, obj.df_seg_line)

        fila = bd_temporal.execute(
            "SELECT in_val FROM control_cunas WHERE ref = ? AND angulo = 15 "
            "AND (activo IS NULL OR activo = 1)", (50,)).fetchone()
        assert fila[0] == 0


class TestA2ValidacionUnificadaGuardarTodoIx:

    def test_todo_completo_escribe_ambas_tablas_y_un_solo_mensaje(
            self, app, bd_temporal, avisos):
        obj = _obj_ix(ref=77)

        obj.guardar_todo_ix()

        assert len(_filas_cunas(bd_temporal, 77)) == 4
        assert len(_filas_conos(bd_temporal, 77)) == 5
        assert len(avisos["information"]) == 1, "un solo mensaje de éxito"
        assert not avisos["warning"]

    def test_cunas_incompletas_bloquea_todo_y_avisa_una_vez(
            self, app, bd_temporal, avisos):
        obj = _obj_ix(ref=78, cunas_sin_marcar={(15, "in")})

        obj.guardar_todo_ix()

        assert _filas_cunas(bd_temporal, 78) == []
        assert _filas_conos(bd_temporal, 78) == [], (
            "conos completos, pero el guardado debe bloquearse ENTERO")
        assert len(avisos["warning"]) == 1
        assert not avisos["information"]
        texto = " ".join(str(x) for x in avisos["warning"][0])
        assert "cuñas" in texto or "cunas" in texto.lower()

    def test_conos_incompletos_bloquea_tambien_las_cunas(
            self, app, bd_temporal, avisos):
        """El test negativo de A2: antes de este arreglo, un cono faltante
        bloqueaba SOLO control_conos -- control_cunas se guardaba igual.
        Es exactamente la fila que ya no debe fabricarse."""
        obj = _obj_ix(ref=79, conos_sin_marcar={"6"})

        obj.guardar_todo_ix()

        assert _filas_conos(bd_temporal, 79) == []
        assert _filas_cunas(bd_temporal, 79) == [], (
            "las cuñas estaban completas, pero YA NO deben guardarse "
            "cuando los conos bloquean -- ese doble guardado era el bug")
        assert len(avisos["warning"]) == 1
        assert not avisos["information"]
        texto = " ".join(str(x) for x in avisos["warning"][0])
        assert "6x6" in texto or "conos" in texto.lower()

    def test_ambos_incompletos_un_solo_mensaje_nombra_los_dos(
            self, app, bd_temporal, avisos):
        obj = _obj_ix(ref=80, cunas_sin_marcar={(15, "in")},
                      conos_sin_marcar={"6"})

        obj.guardar_todo_ix()

        assert len(avisos["warning"]) == 1
        texto = " ".join(str(x) for x in avisos["warning"][0])
        assert "6x6" in texto or "conos" in texto.lower()
        assert "cuñas" in texto or "cunas" in texto.lower()
        assert _filas_cunas(bd_temporal, 80) == []
        assert _filas_conos(bd_temporal, 80) == []
