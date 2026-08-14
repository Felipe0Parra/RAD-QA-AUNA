"""H2.7 (decisión del físico 2026-07-15) -- la BD, vía "Subir", es la ÚNICA
fuente del formulario mensual: se eliminó el borrador JSON local (botón
"Guardar" + generación + carga al abrir) porque podía pegar datos de otro
mes y, en el iX, PISABA el control ya guardado en BD.

La verificación previa de la tarea destapó ademas DOS bugs preexistentes en
la recarga BD->widgets (la ruta que queda como única fuente), corregidos
aquí mismo porque H2.7 depende de que "Subir parcial -> reabrir" funcione:

1. iX (`addsomething_ix` bloque [2]): mapeo POSICIONAL de una lista fija de
   14 nombres de widget contra row[1:14] (13 valores), y contra un orden de
   columnas que no es el de producción (val_teo_dosis + val_teo_calidad) --
   TODO campo después de val_teo se mostraba corrido una posición (la
   "calidad" mostraba tolerancia_dosis: el dato fantasma del HANDOFF 14-07).
   Fix: `_cargar_dosimetria_bd_ix` mapea POR NOMBRE con `widget_a_columna`,
   la misma normalización del guardado.

2. 600/Halcyon (`_rellenar_campos`): buscaba la columna con el nombre crudo
   del widget (ln_dosis_ref_cgy_um_6mv) -- no encontraba NINGÚN campo de
   dosimetría al reabrir (solo observaciones). Fix: espeja el despacho del
   guardado (widget_a_columna para dosimetriaMen, lbl_ para el resto).

De paso `widget_a_columna` ganó los casos especiales val_teo_* ->
val_teo_calidad (es la calidad teórica: 0.665/0.761/... coincide con
VALORES_REFERENCIA_CALIDAD y con la columna de producción) y
ln_calidad_j2_j1_* -> calidad_pdd20_10 (electrones y fotones comparten
columna), y el DDL de dosimetriaMen en conection.py se alineó con el
esquema real de producción (decía val_teo_discrepancia, columna que no
existe en la BD real).

Convenciones de la suite: `Conexion` es singleton de proceso -- se parchea
`ruta_base_datos` ANTES de instanciarla y se resetea `_instance` (patrón de
test_reporte_diario_h22.py). Objetos "pelados" via __new__ + QWidget.__init__
(patrón de test_mensual_h1.py). QMessageBox.information estático se parchea
(regla 5 del plan).
"""
import os
import sqlite3
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import widget_a_columna, subirlineasmensuales
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager)
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    """BD temporal con el esquema completo (DDL de Conexion). P1 (PLAN_P1_
    POOL_CONEXIONES_27-07.md): DatabaseManager ya no cachea conexiones a
    nivel de clase (fachada sin estado en services/db_pool.py), así que ya
    no hace falta limpiar ningún pool entre tests."""
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sin_avisos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))


def _crear_control_activo(ruta_bd, control_id):
    """W1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): subirlineasmensuales/_ix
    ahora exige que el control exista y esté activo (no solo dentro de la
    ventana de 2 meses) -- estos tests de round-trip usan un `ref` sintético
    que antes no necesitaba fila propia en `controles`. Se ancla la
    auditoría de creación a AHORA (no a una fecha fija) para que la ventana
    de edición de F4b quede siempre abierta, sin importar cuándo corra la
    suite -- de lo contrario "01/2026" quedaría cerrado (F4b) apenas pasen
    2 meses calendario desde esa fecha fija."""
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, 'Clinac ix', 'Mensual', '01/2026', 'Físico de Prueba')",
        (control_id,))
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(control_id)))
    con.commit()
    con.close()


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


# Widgets del 600 (hoja preguntas_mensu_600, typee=dosimetria) -- nombres
# reales de data/widgets.xlsx: las tolerancias del 600 NO llevan sufijo.
DF_LINES_600 = [
    "val_teo_6mv", "ln_dosis_ref_cgy_um_6mv", "ln_discrepancia_dosis_6mv",
    "ln_tolerancia_dosis", "ln_calidad_pdd20_10_6mv",
    "ln_discrepancia_calidad_6mv", "ln_tolerancia_calidad",
    "ln_simetria_inplane_6mv", "ln_simetria_crossplane_6mv",
    "ln_tolerancia_simetria", "ln_planicidad_inplane_6mv",
    "ln_planicidad_crossplane_6mv", "ln_tolerancia_planicidad",
    "ln_observaciones_dosi",
]


def _widgets_ix(energia):
    """Widgets de una energía del iX (hoja preguntas_mensu_ix): TODOS llevan
    sufijo; la calidad se llama pdd20_10 en fotones y j2_j1 en electrones
    (ver mapping de discrepancias())."""
    calidad = (f"ln_calidad_pdd20_10_{energia}" if energia.endswith("mv")
               else f"ln_calidad_j2_j1_{energia}")
    return [
        f"val_teo_{energia}", f"ln_dosis_ref_cgy_um_{energia}",
        f"ln_discrepancia_dosis_{energia}", f"ln_tolerancia_dosis_{energia}",
        calidad, f"ln_discrepancia_calidad_{energia}",
        f"ln_tolerancia_calidad_{energia}", f"ln_simetria_inplane_{energia}",
        f"ln_simetria_crossplane_{energia}",
        f"ln_tolerancia_simetria_{energia}",
        f"ln_planicidad_inplane_{energia}",
        f"ln_planicidad_crossplane_{energia}",
        f"ln_tolerancia_planicidad_{energia}",
    ]


def _pelado_600():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    for nombre in DF_LINES_600:
        setattr(obj, nombre, QLineEdit())
    return obj


def _pelado_ix(energias=("6mv", "6mev")):
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    df_lines = []
    for e in energias:
        for nombre in _widgets_ix(e):
            setattr(obj, nombre, QLineEdit())
            df_lines.append(nombre)
    obj.ln_observaciones_dosi = QLineEdit()
    df_lines.append("ln_observaciones_dosi")
    return obj, df_lines


def _insertar_fila_6mv(ruta_bd, ref, energia="6mv"):
    """Fila con valores TODOS DISTINTOS por columna: si algún widget mostrara
    el valor de otra columna (el desfase del iX), el test lo delata. Todos
    NO enteros: la afinidad INTEGER de SQLite guardaría 2.0 como 2 y el
    assert de texto compararía '2' contra '2.0'."""
    valores = {
        "val_teo_dosis": 1.05, "val_teo_calidad": 0.665,
        "dosis_ref_cgy_um": 0.993, "discrepancia_dosis": 0.7,
        "tolerancia_dosis": 2.5, "calidad_pdd20_10": 0.6676,
        "discrepancia_calidad": 0.391, "tolerancia_calidad": 2.1,
        "simetria_inplane": 0.87, "simetria_crossplane": 1.14,
        "tolerancia_simetria": 2.2, "planicidad_inplane": 2.43,
        "planicidad_crossplane": 2.45, "tolerancia_planicidad": 3.5,
        "observaciones_dosi": "obs de prueba",
    }
    con = sqlite3.connect(ruta_bd)
    cols = ", ".join(["ref"] + list(valores) + ["energia"])
    marcas = ", ".join("?" * (len(valores) + 2))
    con.execute(f"INSERT INTO dosimetriaMen ({cols}) VALUES ({marcas})",
                [ref] + list(valores.values()) + [energia])
    con.commit()
    con.close()
    return valores


class TestWidgetAColumna:
    """La normalización ÚNICA widget->columna (guardar Y cargar)."""

    @pytest.mark.parametrize("widget,columna", [
        ("ln_dosis_ref_cgy_um_6mv", "dosis_ref_cgy_um"),
        ("ln_tolerancia_dosis", "tolerancia_dosis"),          # 600, sin sufijo
        ("ln_tolerancia_dosis_15mev", "tolerancia_dosis"),    # iX, con sufijo
        ("ln_calidad_pdd20_10_15mv", "calidad_pdd20_10"),     # fotones
        ("ln_calidad_j2_j1_9mev", "calidad_pdd20_10"),        # electrones
        ("val_teo_6mv", "val_teo_calidad"),                   # calidad teórica
        ("ln_observaciones_dosi", "observaciones_dosi"),
        ("lbl_iso_mec", "iso_mec"),                           # tabla preguntas
    ])
    def test_mapeos(self, widget, columna):
        assert widget_a_columna(widget) == columna


class TestDdlIgualProduccion:
    """El DDL de conection.py crea dosimetriaMen con las MISMAS columnas de
    la BD de producción (antes: val_teo_discrepancia, que no existe allá)."""

    def test_columnas_de_bd_fresca(self, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        cols = [r[1] for r in con.execute("PRAGMA table_info(dosimetriaMen)")]
        con.close()
        assert cols == [
            "ref", "val_teo_dosis", "val_teo_calidad", "dosis_ref_cgy_um",
            "discrepancia_dosis", "tolerancia_dosis", "calidad_pdd20_10",
            "discrepancia_calidad", "tolerancia_calidad", "simetria_inplane",
            "simetria_crossplane", "tolerancia_simetria",
            "planicidad_inplane", "planicidad_crossplane",
            "tolerancia_planicidad", "observaciones_dosi", "energia",
            "activo"]  # E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11)


class TestSinRegistroNaceVacio:
    """Plan H2.7: abrir un mensual SIN control en BD deja los campos vacíos
    -- nada se autocarga (el borrador JSON ya no existe)."""

    def test_600_sin_registro(self, app, bd_temporal):
        obj = _pelado_600()
        assert obj._cargar_de_bd(DF_LINES_600, "dosimetriaMen", 999999) is False
        for nombre in DF_LINES_600:
            assert getattr(obj, nombre).text() == "", nombre

    def test_ix_sin_registro(self, app, bd_temporal):
        obj, df_lines = _pelado_ix()
        assert obj._cargar_dosimetria_bd_ix(df_lines, "dosimetriaMen", 999999) is False
        for nombre in df_lines:
            assert getattr(obj, nombre).text() == "", nombre

    def test_api_de_borrador_eliminada(self):
        """Tripwire: si alguien reintroduce el borrador, que truene aquí."""
        for atributo in ("_cargar_json_cache", "_guardar_optimizado",
                         "_guardar_tabla_optimizada", "_contexto_borrador",
                         "_extraer_campos_de_borrador", "JsonGuardado"):
            assert not hasattr(PruebaMensual600, atributo), atributo
        assert not hasattr(mensual_mod, "FileCache")


class TestRecargaBienMapeada600:
    """Bug 2: antes de H2.7, _rellenar_campos no encontraba NINGUNA columna
    de dosimetría (buscaba 'ln_dosis_ref_cgy_um_6mv' literal) -- reabrir un
    control guardado mostraba todo vacío salvo observaciones."""

    def test_cada_widget_muestra_su_propia_columna(self, app, bd_temporal):
        valores = _insertar_fila_6mv(bd_temporal, ref=777)
        obj = _pelado_600()

        assert obj._cargar_de_bd(DF_LINES_600, "dosimetriaMen", 777) is True

        assert obj.ln_dosis_ref_cgy_um_6mv.text() == str(valores["dosis_ref_cgy_um"])
        assert obj.ln_calidad_pdd20_10_6mv.text() == str(valores["calidad_pdd20_10"])
        assert obj.ln_discrepancia_calidad_6mv.text() == str(valores["discrepancia_calidad"])
        assert obj.ln_tolerancia_dosis.text() == str(valores["tolerancia_dosis"])
        assert obj.ln_simetria_crossplane_6mv.text() == str(valores["simetria_crossplane"])
        assert obj.val_teo_6mv.text() == str(valores["val_teo_calidad"])
        assert obj.ln_observaciones_dosi.text() == valores["observaciones_dosi"]


class TestRecargaBienMapeadaIX:
    """Bug 1 (el dato fantasma del HANDOFF 14-07): el mapeo posicional del iX
    corría todos los valores una posición -- la 'calidad' mostraba la
    tolerancia de dosis. Valores todos distintos: cualquier corrimiento
    truena."""

    def test_cada_widget_muestra_su_propia_columna(self, app, bd_temporal):
        valores = _insertar_fila_6mv(bd_temporal, ref=888, energia="6mv")
        obj, df_lines = _pelado_ix(energias=("6mv",))

        assert obj._cargar_dosimetria_bd_ix(df_lines, "dosimetriaMen", 888) is True

        # El caso exacto del reporte del físico: calidad muestra CALIDAD.
        assert obj.ln_calidad_pdd20_10_6mv.text() == str(valores["calidad_pdd20_10"])
        assert obj.ln_dosis_ref_cgy_um_6mv.text() == str(valores["dosis_ref_cgy_um"])
        assert obj.ln_discrepancia_dosis_6mv.text() == str(valores["discrepancia_dosis"])
        assert obj.ln_tolerancia_dosis_6mv.text() == str(valores["tolerancia_dosis"])
        assert obj.ln_discrepancia_calidad_6mv.text() == str(valores["discrepancia_calidad"])
        assert obj.ln_simetria_inplane_6mv.text() == str(valores["simetria_inplane"])
        assert obj.ln_planicidad_crossplane_6mv.text() == str(valores["planicidad_crossplane"])
        assert obj.ln_tolerancia_planicidad_6mv.text() == str(valores["tolerancia_planicidad"])
        assert obj.val_teo_6mv.text() == str(valores["val_teo_calidad"])
        assert obj.ln_observaciones_dosi.text() == valores["observaciones_dosi"]

    def test_energia_electrones_no_hereda_de_fotones(self, app, bd_temporal):
        """Solo hay fila de 6mv guardada: los widgets de 6mev deben quedar
        vacíos (cada energía carga SU fila, no la primera que exista)."""
        _insertar_fila_6mv(bd_temporal, ref=889, energia="6mv")
        obj, df_lines = _pelado_ix(energias=("6mv", "6mev"))

        obj._cargar_dosimetria_bd_ix(df_lines, "dosimetriaMen", 889)

        assert obj.ln_calidad_pdd20_10_6mv.text() != ""
        for nombre in _widgets_ix("6mev"):
            assert getattr(obj, nombre).text() == "", nombre


class TestSubirReabrirRoundTripIX:
    """Plan H2.7: 'Subir' parcial -> reabrir carga desde BD; segundo 'Subir'
    hace UPDATE sin duplicar. Round-trip REAL: subirlineasmensuales_ix
    escribe, _cargar_dosimetria_bd_ix (objeto fresco = reabrir) relee."""

    def _contar(self, ruta_bd, ref, energia):
        """Cuenta la fila VIGENTE. DO1 (PLAN_CONTRATO_GUARDADO_13-08.md
        §6-DO1): un segundo "Subir" ya no hace UPDATE de la misma fila --
        anula la vieja e inserta la nueva."""
        con = sqlite3.connect(ruta_bd)
        n = con.execute(
            "SELECT COUNT(*) FROM dosimetriaMen WHERE ref=? AND energia=? "
            "AND (activo IS NULL OR activo = 1)",
            (ref, energia)).fetchone()[0]
        con.close()
        return n

    def test_subir_parcial_reabrir_y_completar(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 555)
        obj, df_lines = _pelado_ix(energias=("6mv",))
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        obj.ln_calidad_pdd20_10_6mv.setText("0.6676")
        # el resto queda vacío: guardado PARCIAL

        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=555, usarid=True,
                                    df_lines=df_lines)

        # reabrir (objeto fresco): lo subido vuelve, lo no subido sigue vacío
        obj2, df_lines2 = _pelado_ix(energias=("6mv",))
        assert obj2._cargar_dosimetria_bd_ix(df_lines2, "dosimetriaMen", 555) is True
        assert obj2.ln_dosis_ref_cgy_um_6mv.text() == "0.993"
        assert obj2.ln_calidad_pdd20_10_6mv.text() == "0.6676"
        assert obj2.ln_simetria_inplane_6mv.text() == ""

        # completar y volver a subir: UPDATE, sin duplicar la fila
        obj2.ln_simetria_inplane_6mv.setText("0.87")
        obj2.subirlineasmensuales_ix("dosimetriaMen", 0, ref=555, usarid=True,
                                     df_lines=df_lines2)
        assert self._contar(bd_temporal, 555, "6mv") == 1

        obj3, df_lines3 = _pelado_ix(energias=("6mv",))
        obj3._cargar_dosimetria_bd_ix(df_lines3, "dosimetriaMen", 555)
        assert obj3.ln_dosis_ref_cgy_um_6mv.text() == "0.993"
        assert obj3.ln_simetria_inplane_6mv.text() == "0.87"

    def test_tolerancias_no_se_cruzan_entre_energias(self, app, bd_temporal, monkeypatch):
        """El filtro viejo metía ln_tolerancia_* de TODAS las energías en
        cada fila; con la normalización compartida eso habría guardado la
        tolerancia de 6mev en la fila de 6mv. El filtro por sufijo lo evita:
        cada fila recibe SU tolerancia."""
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 556)
        obj, df_lines = _pelado_ix(energias=("6mv", "6mev"))
        obj.ln_tolerancia_dosis_6mv.setText("2")
        obj.ln_tolerancia_dosis_6mev.setText("3")

        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=556, usarid=True,
                                    df_lines=df_lines)

        # Nota: subirlineasmensuales_ix escribe una fila por CADA energía de
        # self.ENERGIAS (en producción todas tienen widgets; aquí solo
        # construimos 2) -- se comparan solo las dos que nos interesan.
        con = sqlite3.connect(bd_temporal)
        filas = dict(con.execute(
            "SELECT energia, tolerancia_dosis FROM dosimetriaMen "
            "WHERE ref=556 AND energia IN ('6mv', '6mev')"))
        con.close()
        assert filas == {"6mv": 2, "6mev": 3}


class TestSubirReabrirRoundTrip600:
    """Mismo round-trip para el 600 (subirlineasmensuales de load.py +
    _cargar_de_bd), incluido val_teo: antes de H2.7 el widget val_teo_6mv no
    se persistía a NINGUNA columna (dependía solo del borrador JSON -- el
    caso exacto que la verificación previa del plan debía detectar)."""

    def test_subir_reabrir_update_sin_duplicar(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _crear_control_activo(bd_temporal, 444)
        obj = _pelado_600()
        obj.df_lines = DF_LINES_600
        obj.val_teo_6mv.setText("0.665")
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        obj.ln_observaciones_dosi.setText("parcial")

        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=444, usarid=False)

        obj2 = _pelado_600()
        assert obj2._cargar_de_bd(DF_LINES_600, "dosimetriaMen", 444) is True
        assert obj2.val_teo_6mv.text() == "0.665"
        assert obj2.ln_dosis_ref_cgy_um_6mv.text() == "0.993"
        assert obj2.ln_observaciones_dosi.text() == "parcial"
        assert obj2.ln_simetria_inplane_6mv.text() == ""

        # segundo Subir = UPDATE (completar sin duplicar)
        obj2.df_lines = DF_LINES_600
        obj2.ln_simetria_inplane_6mv.setText("0.9")
        subirlineasmensuales(obj2, "dosimetriaMen", 0, ref=444, usarid=False)

        con = sqlite3.connect(bd_temporal)
        # DO1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-DO1): el segundo "Subir"
        # ya no hace UPDATE de la misma fila -- anula la vieja e inserta la
        # nueva. "Sin duplicar" ahora significa UNA sola fila VIGENTE, no
        # una sola fila en total (la vieja sigue ahí, histórica).
        n = con.execute(
            "SELECT COUNT(*) FROM dosimetriaMen WHERE ref=444 "
            "AND (activo IS NULL OR activo = 1)").fetchone()[0]
        fila = con.execute(
            "SELECT val_teo_calidad, simetria_inplane FROM dosimetriaMen "
            "WHERE ref=444 AND (activo IS NULL OR activo = 1)").fetchone()
        total = con.execute(
            "SELECT COUNT(*) FROM dosimetriaMen WHERE ref=444").fetchone()[0]
        con.close()
        assert n == 1
        assert fila == (0.665, 0.9)
        assert total == 2, "el bloque anterior debía quedar histórico, no perdido"
