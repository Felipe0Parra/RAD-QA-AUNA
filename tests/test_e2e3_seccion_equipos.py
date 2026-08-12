"""E2+E3 (PLAN_CONOS_MENSUAL_12-08.md §4-E2/E3): reabrir un control mensual
no mutila la sección de Equipos, y la restauración respeta `activo` y el
tipo de cámara.

Cuatro defectos combinados en `PruebaMensual600` (afecta por herencia a
600/iX/Halcyon mensual y a los tres anuales):

E-D2: `botonescombobox` hacía `subido = self.Traerinfo(combobox); if subido:
return` -- cuando el control tenía equipos guardados, la función salía
ANTES de `conectarDB` (los combos de modelo quedaban con un único ítem, el
que `Traerinfo` había añadido) y ANTES de crear el botón "Subir" (la
sección se quedaba sin forma de guardar un cambio). Fix: `conectarDB` y la
creación del botón corren SIEMPRE; `Traerinfo` pasa a seleccionar sobre una
lista ya completa, en vez de decidir si poblarla.

E-D3: `Traerinfo` no filtraba `activo` y ordenaba `ORDER BY id` ascendente,
asignando por POSICIÓN (`base_index = i*3`) -- tras M2 (anular+insertar) un
`ref` puede tener varios bloques, y restauraba el más viejo, en el hueco
equivocado si el orden de inserción no coincidía con el de los widgets.

E-D4: `Traerinfo` hacía `serie_widget.addItem(str(serie))` sin `userData` --
`subirtodo_modificado` resuelve el equipo por `currentData()` (F9), así que
lo restaurado por `Traerinfo` no era ni seleccionable con sentido ni
guardable: `equipo_id` salía `None` y el grupo se saltaba en silencio.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QGridLayout, QLineEdit, QMessageBox,
    QPushButton, QWidget,
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
                                fecha_calibr="01/01/2020"):
    con = sqlite3.connect(ruta_bd)
    con.execute("""
        INSERT INTO equipos_medicion
            (ref, tipo_camara, equip_type, model, serie, calibr_fact,
             fecha_calibr, equipo_id, activo)
        VALUES (?, ?, 'Cámara de ionización', ?, ?, ?, ?, ?, ?)
    """, (ref, tipo_camara, model, serie, calibr_fact, fecha_calibr,
          equipo_id, activo))
    con.commit()
    con.close()


def _mensual_pelado(ref):
    """PruebaMensual600 pelado (600 -> 3 grupos: Principal/Secundaria/
    Electrómetro, tipos_camara real de la clase no-iX)."""
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


def _conectar_señales(obj):
    """Simula el cableado de `button_click()` -- en producción corre
    DESPUÉS de `botonescombobox`/`Traerinfo`, así que solo se conecta
    cuando el test necesita simular una interacción del físico posterior
    a la restauración (caso 5)."""
    for i in range(0, len(obj.commenu), 3):
        obj.commenu[i].currentTextChanged.connect(obj.setEquipoSeleccionado)
        obj.commenu[i + 1].currentTextChanged.connect(obj.setCalibracion)


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


class TestElCasoDelFisico:
    """§5.3 caso 4: control CON equipos guardados -- el combo de modelos
    tiene la lista completa Y el modelo guardado seleccionado; el combo de
    series tiene todas las calibraciones activas de ese modelo Y la
    guardada seleccionada; el botón "Subir" existe. Rojo sin E2 en los
    tres puntos (el `return` temprano de `botonescombobox` impide que
    `conectarDB` y la creación del botón corran)."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloA", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 2, equip_type="Cámara de ionización",
                         model="ModeloA", serie="S1B", calibr_fact=1.5,
                         fecha_calibr="01/02/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 3, equip_type="Cámara de ionización",
                         model="ModeloB", serie="S2", calibr_fact=2.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "ModeloA",
                                   "S1", 1.0, equipo_id=1)

    def test_lista_completa_y_seleccion_guardada(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)

        modelo_widget, serie_widget, _ = _grupo(obj, 0)

        # Lista completa de modelos (ModeloA Y ModeloB, no solo el guardado).
        textos_modelo = [modelo_widget.itemText(i) for i in range(modelo_widget.count())]
        assert "ModeloA" in textos_modelo
        assert "ModeloB" in textos_modelo, (
            f"combo de modelos incompleto tras reabrir: {textos_modelo}")

        # Modelo guardado seleccionado.
        assert modelo_widget.currentText() == "ModeloA"

        # Combo de series con TODAS las calibraciones activas de ModeloA
        # (S1 y S1B) y la guardada (equipo_id=1) seleccionada.
        assert serie_widget.count() >= 3  # 'Seleccionar...' + S1 + S1B
        assert serie_widget.currentData() == 1

        # El botón "Subir" existe.
        assert _boton_subir(categoria) is not None


class TestCambiarDeEquipoYGuardar:
    """§5.3 caso 5: seleccionar otro modelo/serie y pulsar "Subir" ⇒
    `equipos_medicion` tiene un bloque nuevo activo con el equipo nuevo, el
    anterior anulado (M2 intacto), y `equipo_id` NO nulo en las filas
    nuevas. Rojo sin E-D4 (sin userData el guardado quedaría vacío)."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloA", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 2, equip_type="Cámara de ionización",
                         model="ModeloB", serie="S2", calibr_fact=2.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 10, equip_type="Cámara de ionización",
                         model="ModeloC", serie="S10", calibr_fact=3.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 20, equip_type="Electrómetro",
                         model="ModeloE", serie="S20", calibr_fact=4.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Secundaria", "ModeloC", "S10", 3.0, equipo_id=10)
        _insertar_equipos_medicion(ruta_bd, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    def test_cambiar_equipo_anula_el_bloque_anterior_e_inserta_uno_nuevo(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)
        _conectar_señales(obj)  # simula button_click() ya cableado

        modelo0, serie0, _ = _grupo(obj, 0)
        modelo0.setCurrentText("ModeloB")  # dispara setEquipoSeleccionado
        idx = serie0.findData(2)
        assert idx != -1, "ModeloB/S2 no quedó en el combo de series tras cambiar de modelo"
        serie0.setCurrentIndex(idx)  # dispara setCalibracion

        btn = _boton_subir(categoria)
        assert btn is not None
        btn.click()

        con = sqlite3.connect(bd_temporal)
        try:
            activos = con.execute(
                "SELECT tipo_camara, equipo_id FROM equipos_medicion "
                "WHERE ref = ? AND activo = 1", (ref,)).fetchall()
            inactivos = con.execute(
                "SELECT tipo_camara, equipo_id FROM equipos_medicion "
                "WHERE ref = ? AND activo = 0", (ref,)).fetchall()
        finally:
            con.close()

        activos_dict = dict(activos)
        assert activos_dict.get("Principal") == 2, (
            f"el bloque activo no refleja el equipo nuevo: {activos}")
        assert all(eq_id is not None for _, eq_id in activos), (
            f"equipo_id nulo en el bloque nuevo: {activos}")
        assert ("Principal", 1) in inactivos, (
            f"el bloque anterior (ModeloA/S1) no quedó anulado: {inactivos}")


class TestGuardarSinTocarNadaTrasReabrir:
    """§5.3 caso 6: reabrir y pulsar "Subir" sin cambiar nada ⇒ el bloque
    nuevo es IDÉNTICO al anterior (mismos equipo_id), no vacío. El caso que
    E-D4 rompería en silencio (equipo_id=None -> todos los grupos se
    saltarían -> "no se insertaron registros")."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloA", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 10, equip_type="Cámara de ionización",
                         model="ModeloC", serie="S10", calibr_fact=3.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 20, equip_type="Electrómetro",
                         model="ModeloE", serie="S20", calibr_fact=4.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Secundaria", "ModeloC", "S10", 3.0, equipo_id=10)
        _insertar_equipos_medicion(ruta_bd, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    def test_bloque_nuevo_identico_al_anterior(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)
        # SIN conectar señales ni tocar ningún combo -- exactamente el
        # estado que deja Traerinfo.

        btn = _boton_subir(categoria)
        assert btn is not None
        btn.click()

        con = sqlite3.connect(bd_temporal)
        try:
            activos = dict(con.execute(
                "SELECT tipo_camara, equipo_id FROM equipos_medicion "
                "WHERE ref = ? AND activo = 1", (ref,)).fetchall())
        finally:
            con.close()

        assert activos == {"Principal": 1, "Secundaria": 10, "Electrómetro": 20}, (
            f"el bloque nuevo no es idéntico al restaurado: {activos}")


class TestFilaHistoricaConEquipoIdNulo:
    """§5.3 caso 7: fila histórica con `equipo_id = NULL` -- se restaura
    por texto y, al guardar, la fila nueva SÍ lleva `equipo_id` resuelto.
    Sin reescribir nada histórico (DA-02/DA-28: la fila vieja de
    equipos_medicion no se toca, solo se anula como cualquier bloque)."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloA", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 10, equip_type="Cámara de ionización",
                         model="ModeloC", serie="S10", calibr_fact=3.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 20, equip_type="Electrómetro",
                         model="ModeloE", serie="S20", calibr_fact=4.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        # Fila histórica de la Secundaria: equipo_id NULL (anterior a F9).
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Secundaria", "ModeloC", "S10", 3.0, equipo_id=None)
        _insertar_equipos_medicion(ruta_bd, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    def test_restaura_por_texto_y_guarda_con_equipo_id_resuelto(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)

        _, serie1, _ = _grupo(obj, 1)
        assert serie1.currentData() == 10, (
            "la fila con equipo_id=NULL no se restauró por texto contra "
            f"el catálogo (currentData={serie1.currentData()})")

        btn = _boton_subir(categoria)
        btn.click()

        con = sqlite3.connect(bd_temporal)
        try:
            fila_vieja = con.execute(
                "SELECT equipo_id, activo FROM equipos_medicion "
                "WHERE ref = ? AND tipo_camara = 'Secundaria' AND equipo_id IS NULL",
                (ref,)).fetchone()
            fila_nueva = con.execute(
                "SELECT equipo_id FROM equipos_medicion "
                "WHERE ref = ? AND tipo_camara = 'Secundaria' AND activo = 1",
                (ref,)).fetchone()
        finally:
            con.close()

        # La fila histórica sigue existiendo tal cual (anulada, no reescrita).
        assert fila_vieja is not None and fila_vieja[1] == 0
        # La fila nueva SÍ lleva equipo_id resuelto.
        assert fila_nueva is not None and fila_nueva[0] == 10


class TestDosBloquesActivosPorTipoCamara:
    """§5.3 caso 8 (E3): ref con dos bloques activos del mismo tipo_camara
    (el caso real de ref=30, acumulación legítima previa a M2) ⇒ se
    restaura el de id MÁS ALTO, y cada equipo cae en el hueco de su
    tipo_camara -- no en el de su posición de inserción (se insertan las
    filas en orden Electrómetro, Principal, Secundaria a propósito, para
    que el código POSICIONAL viejo las hubiera colocado mal)."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloViejo", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2020", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 2, equip_type="Cámara de ionización",
                         model="ModeloNuevo", serie="S1B", calibr_fact=1.5,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 10, equip_type="Cámara de ionización",
                         model="ModeloC", serie="S10", calibr_fact=3.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 20, equip_type="Electrómetro",
                         model="ModeloE", serie="S20", calibr_fact=4.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        # Orden de inserción DELIBERADAMENTE distinto del orden de
        # tipos_camara (Principal, Secundaria, Electrómetro):
        _insertar_equipos_medicion(ruta_bd, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "ModeloViejo", "S1", 1.0, equipo_id=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Secundaria", "ModeloC", "S10", 3.0, equipo_id=10)
        # Segundo bloque activo de Principal, id más alto -- el vigente.
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "ModeloNuevo", "S1B", 1.5, equipo_id=2)

    def test_restaura_el_de_id_mas_alto_en_el_hueco_correcto(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)

        modelo0, serie0, _ = _grupo(obj, 0)
        modelo1, serie1, _ = _grupo(obj, 1)
        modelo2, serie2, _ = _grupo(obj, 2)

        # Principal (grupo 0): el bloque de id MÁS ALTO (ModeloNuevo/2).
        assert modelo0.currentText() == "ModeloNuevo"
        assert serie0.currentData() == 2

        # Secundaria (grupo 1) y Electrómetro (grupo 2): en su propio
        # hueco, no en el hueco de la posición en que se insertaron.
        assert modelo1.currentText() == "ModeloC"
        assert serie1.currentData() == 10
        assert modelo2.currentText() == "ModeloE"
        assert serie2.currentData() == 20


class TestAntiRegresionM2W1:
    """§5.3 caso 9: reabrir un control REACTIVADO (activo 0->1 en
    `controles`, sin tocar `equipos_medicion`) restaura el mismo bloque que
    un control nunca anulado -- M2/E7 anulan la RAÍZ (`controles`), nunca
    tocan las filas hijas; Traerinfo no consulta `controles.activo` en
    absoluto, así que su resultado es indistinguible antes y después del
    ciclo anular/reactivar."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloA", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 10, equip_type="Cámara de ionización",
                         model="ModeloC", serie="S10", calibr_fact=3.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 20, equip_type="Electrómetro",
                         model="ModeloE", serie="S20", calibr_fact=4.0,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "ModeloA", "S1", 1.0, equipo_id=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Secundaria", "ModeloC", "S10", 3.0, equipo_id=10)
        _insertar_equipos_medicion(ruta_bd, ref, "Electrómetro", "ModeloE", "S20", 4.0, equipo_id=20)

    def _estado_restaurado(self, ref):
        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)
        modelo0, serie0, _ = _grupo(obj, 0)
        return modelo0.currentText(), serie0.currentData()

    def test_reactivado_restaura_igual_que_nunca_anulado(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        antes = self._estado_restaurado(ref)

        con = sqlite3.connect(bd_temporal)
        con.execute("UPDATE controles SET activo = 0 WHERE id = ?", (ref,))
        con.execute("UPDATE controles SET activo = 1 WHERE id = ?", (ref,))
        con.commit()
        con.close()

        despues = self._estado_restaurado(ref)
        assert antes == despues == ("ModeloA", 1)
