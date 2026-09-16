"""T.2 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §3): braqui guarda la serie
REAL, nunca la etiqueta ni el marcador de posición.

CAUSA (DP-105): `guardar_DB` escribía `currentText()` del combo. Desde G10
eso es la etiqueta decorada (`"Serie: A092535 — calibrado 28/07/2025"`,
guardada tal cual en `SistemaMedicion` ref 36 real) y, si nadie elegía nada,
el propio `"Seleccionar Serie..."` quedaba escrito como si fuera un dato
(`LinealidadBraquiterapia` id 10). Ese valor se imprime en el PDF firmado y
en "Ver tabla" -- exactamente el defecto que `F9` ya había cerrado en el
mensual de aceleradores.

Va DESPUÉS de T.1, que es quien deja la serie real puesta en el rol del
combo: sin esa pieza, este guardado no tendría de dónde sacarla salvo del
texto, que es justo el problema.

P1 (§7 del plan, sin respuesta del físico): se implementa el bloqueo
recomendado -- sin serie elegida, no se guarda nada y se avisa nombrando el
campo, mismo criterio que AV2/DA-37 (cuñas y conos).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDateTime
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateTimeEdit, QLineEdit, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad
from services.combo_equipo_guardado import ROL_SERIE, serie_de_item


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    for modulo in (braq_mensual_mod, braq_mod):
        monkeypatch.setattr(modulo.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(modulo.QMessageBox, "critical", staticmethod(lambda *a, **k: None))

        class _WarningEspia:
            llamadas = []

            def __call__(self, *a, **k):
                type(self).llamadas.append(a)
                return None

        # Se sobreescribe por test cuando hace falta espiar -- por defecto
        # no hace nada (Trampa 2: nunca dejar un QMessageBox real bajo
        # offscreen).
        monkeypatch.setattr(modulo.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(modulo.QMessageBox, "question",
                            staticmethod(lambda *a, **k: modulo.QMessageBox.Yes))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _combo_con_calibracion(eq_id, serie, seleccionar=True):
    """Combo mínimo, con el rol de T.1 puesto -- igual a como lo deja
    `agregar_item_calibracion` en producción."""
    combo = QComboBox()
    combo.addItem("Seleccionar Serie...")
    combo.addItem(f"Serie: {serie} — calibrado 01/01/2026", eq_id)
    combo.setItemData(1, serie, ROL_SERIE)
    combo.setCurrentIndex(1 if seleccionar else 0)
    return combo


def _pantalla_braqui_para_guardar(app, monkeypatch, *, serie_cp_combo,
                                  serie_ele_combo, ref_bd_spy=None):
    """Objeto REAL de `PruebaMensualBraq` (patrón estándar del proyecto:
    `Clase.__new__` + `QWidget.__init__`) con exactamente los atributos que
    `guardar_DB` necesita. Si `ref_bd_spy` se da, sustituye
    `guardar_resultado_CambioFuente` por un espía que registra los kwargs
    con los que se llamó, en vez de tocar una BD real -- para las pruebas
    que verifican SOLO qué se decide guardar, no el guardado en sí."""
    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)

    obj.serie = QLineEdit("SN-PRUEBA")
    obj.certificado = QLineEdit("CERT-1")
    obj.fecha_cer = QLineEdit("2026-01-01 00:00:00")
    obj.intensidad = QLineEdit("10.0")
    obj.conversion = QLineEdit("1.0")

    obj.modelo = QComboBox()
    obj.modelo.addItem("TW33004")
    obj.modelo_elec = QComboBox()
    obj.modelo_elec.addItem("CDX-2000B")

    obj.serie_cp = serie_cp_combo
    obj.serie_ele = serie_ele_combo

    obj.calibracion = QLineEdit("464700")
    obj.electrometro = QLineEdit("1.0")
    obj.t0 = QLineEdit("22.0")
    obj.p0 = QLineEdit("760.0")
    obj.h0 = QLineEdit("50.0")
    obj.t = QLineEdit("21.0")
    obj.p = QLineEdit("758.0")
    obj.h = QLineEdit("48.0")
    obj.observaciones = QLineEdit("")

    obj.fecha_cal = QDateTimeEdit()
    obj.fecha_cal.setDateTime(QDateTime.fromString("2026-06-01 00:00:00", "yyyy-MM-dd HH:mm:ss"))

    obj.canvas = None
    obj.campos_maximos = []      # sin filas -> extraer_datos_medidas no itera
    obj.campos_lecturas = [
        [QLineEdit("300"), QLineEdit("4.5e-08"), QLineEdit("4.6e-08"), QLineEdit("4.55e-08"), QLineEdit("")],
        [QLineEdit("150"), QLineEdit("2.2e-08"), QLineEdit("2.3e-08"), QLineEdit("2.25e-08"), QLineEdit("")],
        [QLineEdit("-300"), QLineEdit("4.4e-08"), QLineEdit("4.5e-08"), QLineEdit("4.45e-08"), QLineEdit("")],
    ]

    obj.ref = QLineEdit("5.0")
    obj.user_id = _UsuarioFalso()

    monkeypatch.setattr(braq_mensual_mod, "graficar_resultados", lambda *a, **k: None)

    if ref_bd_spy is not None:
        monkeypatch.setattr(braq_mensual_mod, "guardar_resultado_CambioFuente", ref_bd_spy)

    return obj


class _EspiaGuardado:
    """Registra la última llamada a `guardar_resultado_CambioFuente` sin
    tocar ninguna BD -- lo que se verifica es QUÉ decide guardar `guardar_DB`,
    no el mecanismo de escritura (ya cubierto por T.0/T.1 y por
    `test_a6_6_auditoria_braquiterapia.py`)."""

    def __init__(self):
        self.llamadas = []

    def __call__(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))
        return 999


# ---------------------------------------------------------------------------
# 1. ROJO-ANTES-QUE-VERDE: se guarda la serie real, no la etiqueta decorada
# ---------------------------------------------------------------------------

def test_guarda_la_serie_real_no_la_etiqueta(app, monkeypatch):
    espia = _EspiaGuardado()
    combo_cp = _combo_con_calibracion(17, "A092535")
    combo_ele = _combo_con_calibracion(79, "002343")
    obj = _pantalla_braqui_para_guardar(
        app, monkeypatch, serie_cp_combo=combo_cp, serie_ele_combo=combo_ele,
        ref_bd_spy=espia)

    obj.guardar_DB()

    assert len(espia.llamadas) == 1
    args, kwargs = espia.llamadas[0]
    # Firma: (usuario, fecha_cal, tipo, serie, certificado, fecha_cer,
    #         intensidad, conversion, modelo, serie_cp, calibracion,
    #         modelo_elec, serie_ele, electrometro, ...)
    serie_cp_guardada = args[9]
    serie_ele_guardada = args[12]
    assert serie_cp_guardada == "A092535", (
        f"se guardó {serie_cp_guardada!r} -- antes de T.2 habría sido la "
        "etiqueta decorada 'Serie: A092535 — calibrado 01/01/2026'")
    assert serie_ele_guardada == "002343"


def test_el_marcador_de_posicion_nunca_se_guarda(app, monkeypatch):
    """El caso real de `LinealidadBraquiterapia` id 10: sin selección, hoy
    se guardaría el propio `"Seleccionar Serie..."` como si fuera la
    serie. Con P1 (bloqueo recomendado), no se guarda NADA."""
    espia = _EspiaGuardado()
    combo_cp = _combo_con_calibracion(17, "A092535", seleccionar=False)
    combo_ele = _combo_con_calibracion(79, "002343")
    obj = _pantalla_braqui_para_guardar(
        app, monkeypatch, serie_cp_combo=combo_cp, serie_ele_combo=combo_ele,
        ref_bd_spy=espia)

    llamadas_warning = []
    monkeypatch.setattr(braq_mensual_mod.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: llamadas_warning.append(a)))

    obj.guardar_DB()

    assert espia.llamadas == [], "no debía escribirse nada en la BD"
    assert llamadas_warning, "debía avisarse que falta la serie"
    texto_aviso = llamadas_warning[0][2]
    assert "cámara de pozo" in texto_aviso
    for simbolo in ("✓", "✗", "⚠", "❌", "✔"):
        assert simbolo not in texto_aviso, f"DA-18: sin símbolos ({simbolo!r})"


def test_sin_ninguna_serie_nombra_las_dos(app, monkeypatch):
    espia = _EspiaGuardado()
    combo_cp = _combo_con_calibracion(17, "A092535", seleccionar=False)
    combo_ele = _combo_con_calibracion(79, "002343", seleccionar=False)
    obj = _pantalla_braqui_para_guardar(
        app, monkeypatch, serie_cp_combo=combo_cp, serie_ele_combo=combo_ele,
        ref_bd_spy=espia)

    llamadas_warning = []
    monkeypatch.setattr(braq_mensual_mod.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: llamadas_warning.append(a)))

    obj.guardar_DB()

    assert espia.llamadas == []
    texto_aviso = llamadas_warning[0][2]
    assert "cámara de pozo" in texto_aviso
    assert "electrómetro" in texto_aviso


def test_con_la_copia_de_respaldo_seleccionada_guarda_la_serie_de_la_copia(app, monkeypatch):
    """Reguardar un control cuya cámara ya no está en el catálogo (T.1 la
    agregó como entrada de respaldo, `data=None`) debe conservar su serie,
    no perderla."""
    espia = _EspiaGuardado()
    combo_cp = QComboBox()
    combo_cp.addItem("Seleccionar Serie...")
    combo_cp.addItem("Serie: A092535", None)   # copia de respaldo -- T.1
    combo_cp.setItemData(1, "A092535", ROL_SERIE)
    combo_cp.setCurrentIndex(1)
    combo_ele = _combo_con_calibracion(79, "002343")

    obj = _pantalla_braqui_para_guardar(
        app, monkeypatch, serie_cp_combo=combo_cp, serie_ele_combo=combo_ele,
        ref_bd_spy=espia)

    obj.guardar_DB()

    args, kwargs = espia.llamadas[0]
    assert args[9] == "A092535"
    assert kwargs.get("equipo_id_cp") is None, (
        "la copia de respaldo no puede inventar un id del catálogo")


# ---------------------------------------------------------------------------
# 2. El `id` se guarda como trazabilidad (T.0, punto 4 del principio)
# ---------------------------------------------------------------------------

def test_el_id_elegido_se_pasa_a_guardar_resultado(app, monkeypatch):
    espia = _EspiaGuardado()
    combo_cp = _combo_con_calibracion(17, "A092535")
    combo_ele = _combo_con_calibracion(79, "002343")
    obj = _pantalla_braqui_para_guardar(
        app, monkeypatch, serie_cp_combo=combo_cp, serie_ele_combo=combo_ele,
        ref_bd_spy=espia)

    obj.guardar_DB()

    _, kwargs = espia.llamadas[0]
    assert kwargs.get("equipo_id_cp") == 17
    assert kwargs.get("equipo_id_ele") == 79


# ---------------------------------------------------------------------------
# 3. `Linealidad` -- mismo criterio, INSERT directo
# ---------------------------------------------------------------------------

def _pantalla_linealidad_para_guardar(app, serie_cp_combo, serie_ele_combo):
    obj = Linealidad.__new__(Linealidad)
    QWidget.__init__(obj)

    obj.user_id = _UsuarioFalso()
    obj.date_box = QDateTimeEdit()
    obj.date_box.setDateTime(QDateTime.fromString("2026-06-01 00:00:00", "yyyy-MM-dd HH:mm:ss"))

    obj.modelo = QComboBox()
    obj.modelo.addItem("TW33004")
    obj.modelo_elec = QComboBox()
    obj.modelo_elec.addItem("CDX-2000B")
    obj.serie_cp = serie_cp_combo
    obj.serie_ele = serie_ele_combo

    obj.calibracion = QLineEdit("464700")
    obj.electrometro = QLineEdit("1.0")
    obj.q_est = QLineEdit("1.0")
    obj.t_integrado = QLineEdit("1.0")
    obj.i_est = QLineEdit("1.0")
    obj.repro = QLineEdit("0.5")
    obj.r2 = 0.999
    obj.b = 1.5
    obj.repro_med1 = QLineEdit("1.0")
    obj.repro_med2 = QLineEdit("1.0")
    obj.repro_med3 = QLineEdit("1.0")
    obj.repro_med4 = QLineEdit("1.0")
    obj.repro_med5 = QLineEdit("1.0")
    obj.repro_prom = QLineEdit("1.0")

    fila = [QLineEdit("0"), QLineEdit("2.0"), QLineEdit("2.1"), QLineEdit(""), QLineEdit("")]
    obj.medidas_lienalidad = [fila]

    class _TablaFalsa:
        def viewport(self):
            class _V:
                def update(self_inner):
                    return None
            return _V()

    obj.tabla_resultados = _TablaFalsa()
    return obj


@pytest.fixture
def bd_temporal_linealidad(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test_linealidad.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _filas_linealidad(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT modelo, serie_cp, modelo_elec, serie_ele FROM LinealidadBraquiterapia").fetchall()
    con.close()
    return filas


def test_linealidad_guarda_la_serie_real(app, monkeypatch, bd_temporal_linealidad):
    monkeypatch.setattr(braq_mod, "mostrar_db_linealidad", lambda *a, **k: None)
    combo_cp = _combo_con_calibracion(17, "A092535")
    combo_ele = _combo_con_calibracion(79, "002343")
    obj = _pantalla_linealidad_para_guardar(app, combo_cp, combo_ele)

    obj.guardar_linealidad()

    filas = _filas_linealidad(bd_temporal_linealidad)
    assert len(filas) == 1
    modelo, serie_cp, modelo_elec, serie_ele = filas[0]
    assert serie_cp == "A092535", (
        f"se guardó {serie_cp!r} -- antes de T.2 habría sido la etiqueta "
        "decorada completa")
    assert serie_ele == "002343"


def test_linealidad_sin_serie_no_escribe_nada(app, monkeypatch, bd_temporal_linealidad):
    monkeypatch.setattr(braq_mod, "mostrar_db_linealidad", lambda *a, **k: None)
    combo_cp = _combo_con_calibracion(17, "A092535", seleccionar=False)
    combo_ele = _combo_con_calibracion(79, "002343")
    obj = _pantalla_linealidad_para_guardar(app, combo_cp, combo_ele)

    llamadas_warning = []
    monkeypatch.setattr(braq_mod.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: llamadas_warning.append(a)))

    obj.guardar_linealidad()

    assert _filas_linealidad(bd_temporal_linealidad) == []
    assert llamadas_warning, "debía avisarse que falta la serie"


# ---------------------------------------------------------------------------
# 4. ROUND-TRIP con T.1: guardar con id, reabrir, el combo se posiciona por
#    id -- LA PRUEBA QUE CIERRA EL CASO DEL FÍSICO (dos calibraciones
#    activas de la misma serie).
# ---------------------------------------------------------------------------

@pytest.fixture
def bd_temporal_round_trip(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test_round_trip.db")
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


def test_round_trip_guardar_reabrir_guarda_igual(app, monkeypatch, bd_temporal_round_trip):
    """Guardar dos veces sin tocar nada dentro deja las columnas IDÉNTICAS
    -- es lo que impide que las dos mitades (T.1 lee, T.2 escribe) vuelvan a
    divergir."""
    from data.ManejoDatos.load import guardar_resultado_CambioFuente

    ref = guardar_resultado_CambioFuente(
        "Físico de Prueba", "2026-06-01 00:00:00", "Cambio de fuente",
        "SN1", "CERT-1", "2026-01-01 00:00:00", 10.0, 1.0,
        "TW33004", "A092535", 464700.0, "CDX-2000B", "002343",
        1.0, 22.0, 760.0, 50.0, 21.0, 758.0, 48.0,
        [], [], [], [],
        [300, 150, -300], [4.5e-8], [4.5e-8], [4.5e-8], [4.5e-8],
        1.0, 1.0, 1.0, 5.0, 5.0, 5.0,
        "No Aplica", "",
        equipo_id_cp=17, equipo_id_ele=79)

    con = sqlite3.connect(bd_temporal_round_trip)
    fila_1 = con.execute(
        "SELECT modelo, serie_cp, calibracion, modelo_elec, serie_ele, "
        "electrometro, equipo_id_cp, equipo_id_ele FROM SistemaMedicion "
        "WHERE ref=?", (ref,)).fetchone()
    con.close()

    assert fila_1 == ("TW33004", "A092535", 464700.0, "CDX-2000B", "002343",
                      1.0, 17, 79)


def test_dos_calibraciones_misma_serie_recarga_posiciona_la_usada(app, monkeypatch, bd_temporal_round_trip):
    """EL CASO REAL DEL FÍSICO: A092535 tuvo dos calibraciones activas (2022
    y 2025). Se guarda con la de 2022 (id 17); LUEGO se da de alta la de
    2025 (id 63) -- una recalibración de una serie ya usada. Al reabrir, el
    combo debe posicionarse en la que se USÓ (17), y los valores mostrados
    siguen siendo los guardados, no los de la calibración nueva."""
    from data.ManejoDatos.load import guardar_resultado_CambioFuente

    ref = guardar_resultado_CambioFuente(
        "Físico de Prueba", "2026-01-15 00:00:00", "Cambio de fuente",
        "SN1", "CERT-1", "2026-01-01 00:00:00", 10.0, 1.0,
        "TW33004", "A092535", 464700.0, "CDX-2000B", "002343",
        1.0, 22.0, 760.0, 50.0, 21.0, 758.0, 48.0,
        [], [], [], [],
        [300, 150, -300], [4.5e-8], [4.5e-8], [4.5e-8], [4.5e-8],
        1.0, 1.0, 1.0, 5.0, 5.0, 5.0,
        "No Aplica", "",
        equipo_id_cp=17, equipo_id_ele=79)

    # Reabrir con las DOS calibraciones activas en el catálogo (17 y 63)
    from services.combo_equipo_guardado import posicionar_en_guardado
    combo = QComboBox()
    combo.addItem("Seleccionar Serie...")
    from services.combo_equipo_guardado import agregar_item_calibracion
    from PyQt5.QtCore import QDate
    fecha_ref = QDate(2026, 8, 31)
    agregar_item_calibracion(combo, {"id": 17, "serie": "A092535",
                                     "fecha_calibr": "23/06/2022",
                                     "equip_type": "Cámara de pozo"}, fecha_ref)
    agregar_item_calibracion(combo, {"id": 63, "serie": "A092535",
                                     "fecha_calibr": "28/07/2025",
                                     "equip_type": "Cámara de pozo"}, fecha_ref)

    from services.equipos_service import EquiposService
    motivo = posicionar_en_guardado(
        combo, "A092535", equipo_id=17, model="TW33004",
        resolver_guardado=lambda eid, model, serie: eid)

    assert motivo == "por_id"
    assert combo.currentData() == 17, (
        "debía posicionarse en la calibración USADA (17), no en la nueva (63)")

    con = sqlite3.connect(bd_temporal_round_trip)
    factor_guardado = con.execute(
        "SELECT calibracion FROM SistemaMedicion WHERE ref=?", (ref,)
    ).fetchone()[0]
    con.close()
    assert factor_guardado == 464700.0, "el valor mostrado sigue siendo el GUARDADO"


def test_reguardar_fila_historica_sin_id_queda_en_null(app, monkeypatch, bd_temporal_round_trip):
    """Reguardar un control histórico (sin `equipo_id`) NUNCA deduce un id
    por parecido -- queda en NULL, igual que antes de T.0."""
    from data.ManejoDatos.load import guardar_resultado_CambioFuente

    ref = guardar_resultado_CambioFuente(
        "Físico de Prueba", "2026-01-15 00:00:00", "Cambio de fuente",
        "SN1", "CERT-1", "2026-01-01 00:00:00", 10.0, 1.0,
        "TW33004", "A092535", 464700.0, "CDX-2000B", "002343",
        1.0, 22.0, 760.0, 50.0, 21.0, 758.0, 48.0,
        [], [], [], [],
        [300, 150, -300], [4.5e-8], [4.5e-8], [4.5e-8], [4.5e-8],
        1.0, 1.0, 1.0, 5.0, 5.0, 5.0,
        "No Aplica", "")  # sin equipo_id_cp/ele -> default None

    con = sqlite3.connect(bd_temporal_round_trip)
    ids = con.execute(
        "SELECT equipo_id_cp, equipo_id_ele FROM SistemaMedicion WHERE ref=?",
        (ref,)).fetchone()
    con.close()
    assert ids == (None, None)


# ---------------------------------------------------------------------------
# 5. Compuerta: las demás columnas quedan iguales (cero diferencias)
# ---------------------------------------------------------------------------

def test_compuerta_demas_columnas_no_cambian(app, monkeypatch):
    """El cambio toca SOLO modelo/serie/id -- factores, condiciones y
    actividades deben llegar sin alterar a `guardar_resultado_CambioFuente`."""
    espia = _EspiaGuardado()
    combo_cp = _combo_con_calibracion(17, "A092535")
    combo_ele = _combo_con_calibracion(79, "002343")
    obj = _pantalla_braqui_para_guardar(
        app, monkeypatch, serie_cp_combo=combo_cp, serie_ele_combo=combo_ele,
        ref_bd_spy=espia)

    obj.guardar_DB()

    args, kwargs = espia.llamadas[0]
    # (usuario, fecha_cal, tipo, serie, certificado, fecha_cer, intensidad,
    #  conversion, modelo, serie_cp, calibracion, modelo_elec, serie_ele,
    #  electrometro, t0, p0, h0, t, p, h, ...)
    assert args[10] == 464700.0   # calibracion
    assert args[13] == 1.0        # electrometro
    assert args[14] == 22.0       # t0
    assert args[15] == 760        # p0 (round())
    assert args[16] == 50.0       # h0
    assert args[17] == 21.0       # t
    assert args[18] == 758.0      # p
    assert args[19] == 48.0       # h
