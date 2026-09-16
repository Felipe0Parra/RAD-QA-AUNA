"""T.1 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §2): braqui muestra los
equipos que el control guardó, estén activos, anulados o borrados.

CAUSA (DP-105): la recarga comparaba el TEXTO VISIBLE del combo con lo
guardado. Desde G10 ese texto lleva decoración
(`"Serie: A092535 — calibrado 28/07/2025"`) y la BD guardó `"A092535"`, así
que **ningún** control anterior al 31-07 encontraba su serie -- ni siquiera
con la cámara ACTIVA en el catálogo. Y los combos solo listan calibraciones
activas, así que una cámara anulada o borrada no tenía dónde caer.

EL PRINCIPIO QUE SE VERIFICA AQUÍ (decisión del físico, 16-09-2026):

  - lo que se muestra sale SIEMPRE de la copia guardada;
  - el catálogo solo posiciona el combo, y **ante más de una candidata no se
    elige ninguna** -- se muestra la copia como entrada propia, para que una
    calibración NUEVA de la misma serie no pueda contaminar un control viejo;
  - el `id` identifica, no aporta valores.

La compuerta que de verdad importa es la 3: un control cuyo factor guardado
difiere del vigente del catálogo tiene que seguir mostrando **el guardado**.
Es la regresión que §0.4 anticipó -- `on_serie_pozo_cambio` sobrescribe
factor, T0, P0 y H0 con los del catálogo en cuanto el combo cambia, y hoy no
se ve sólo porque la recarga nunca acierta. Arreglar la recarga sin bloquear
señales habría pisado el histórico de todos los controles de braquiterapia.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox

from services.combo_equipo_guardado import (
    ROL_SERIE, agregar_item_calibracion, posicionar_en_guardado,
    posicionar_modelo, serie_de_item)
from services.etiqueta_equipo import etiqueta_equipo, serie_de_etiqueta


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


FECHA = None  # se rellena en la fixture (QDate necesita QApplication viva)


@pytest.fixture
def fecha_ref(app):
    from PyQt5.QtCore import QDate
    return QDate(2026, 8, 31)


def _combo_con(app, calibraciones, fecha_ref):
    """Combo poblado como lo hace la producción: marcador + una entrada por
    calibración activa."""
    combo = QComboBox()
    combo.addItem("Seleccionar Serie...")
    for eq_id, serie, fecha_calibr in calibraciones:
        agregar_item_calibracion(
            combo,
            {"id": eq_id, "serie": serie, "fecha_calibr": fecha_calibr,
             "equip_type": "Cámara de pozo"},
            fecha_ref)
    return combo


# ---------------------------------------------------------------------------
# El inverso de la etiqueta (la pieza que faltaba)
# ---------------------------------------------------------------------------

class TestSerieDeEtiqueta:
    """Rojo-antes-que-verde: `_limpiar_serie` solo quitaba `" (vencida)"`, así
    que de estos 6 casos acertaba 2."""

    @pytest.mark.parametrize("texto,esperado", [
        ("Serie: A092535 — calibrado 28/07/2025 (vencida)", "A092535"),
        ("Serie: A092535 — calibrado 28/07/2025", "A092535"),
        ("Serie: A092535", "A092535"),
        ("A092535 (vencida)", "A092535"),
        ("A092535", "A092535"),
        ("Seleccionar Serie...", ""),
        (None, ""),
        ("", ""),
    ])
    def test_casos(self, texto, esperado):
        assert serie_de_etiqueta(texto) == esperado

    def test_es_inverso_exacto_de_etiqueta_equipo(self, fecha_ref):
        """La garantía de fondo: sea cual sea la decoración que
        `etiqueta_equipo` añada, el inverso devuelve la serie. Si alguien
        cambia el formato y no el inverso, esto se pone rojo -- que es
        exactamente lo que G10 hizo sin que nadie se enterara."""
        for serie, fecha_calibr in (("A092535", "28/07/2025"),
                                    ("B091982", "17/03/2026"),
                                    ("002343", None),
                                    ("151251", "01/01/2020")):
            texto, _ = etiqueta_equipo(
                {"id": 1, "serie": serie, "fecha_calibr": fecha_calibr,
                 "equip_type": "Electrómetro"}, fecha_ref)
            assert serie_de_etiqueta(texto) == serie


# ---------------------------------------------------------------------------
# 1. El caso que el físico reportó: cámara ACTIVA y aun así no se encontraba
# ---------------------------------------------------------------------------

def test_camara_activa_con_serie_limpia_se_encuentra(app, fecha_ref):
    combo = _combo_con(app, [(17, "A092535", "28/07/2025")], fecha_ref)

    motivo = posicionar_en_guardado(combo, "A092535")

    assert motivo == "por_serie"
    assert serie_de_item(combo, combo.currentIndex()) == "A092535"
    assert combo.currentData() == 17


def test_fila_decorada_ref36_tambien_se_encuentra(app, fecha_ref):
    """El caso real de `SistemaMedicion` ref 36 (31-08): el guardado escribió
    la etiqueta completa. Hoy acierta por casualidad -- debe seguir verde."""
    combo = _combo_con(app, [(17, "A092535", "28/07/2025")], fecha_ref)

    motivo = posicionar_en_guardado(
        combo, "Serie: A092535 — calibrado 28/07/2025")

    assert motivo == "por_serie"
    assert combo.currentData() == 17


# ---------------------------------------------------------------------------
# 2. Cámara anulada o borrada: entrada de respaldo, no campo vacío
# ---------------------------------------------------------------------------

def test_camara_fuera_del_catalogo_se_agrega_como_copia(app, fecha_ref):
    """El electrómetro CDX-2000B/B091982 se anuló el 11-09: 14 de 15
    registros no lo encontrarían en el combo."""
    combo = _combo_con(app, [(79, "002343", "17/03/2026")], fecha_ref)
    n_antes = combo.count()

    motivo = posicionar_en_guardado(combo, "B091982")

    assert motivo == "copia_sin_candidata"
    assert combo.count() == n_antes + 1
    assert combo.currentIndex() == combo.count() - 1
    assert serie_de_item(combo, combo.currentIndex()) == "B091982"
    assert combo.currentData() is None, (
        "la copia de respaldo no puede inventarse un id del catálogo")


def test_modelo_fuera_del_catalogo_tambien_se_agrega(app):
    combo = QComboBox()
    combo.addItems(["TW33004", "TM32002"])

    motivo = posicionar_modelo(combo, "CDX-2000B")

    assert motivo == "copia_sin_candidata"
    assert combo.currentText() == "CDX-2000B"


# ---------------------------------------------------------------------------
# 3. LA REGLA DEL FÍSICO: con varias candidatas no se elige NINGUNA
# ---------------------------------------------------------------------------

def test_dos_calibraciones_de_la_misma_serie_no_se_desempatan(app, fecha_ref):
    """El caso que motivó el principio: A092535 tuvo DOS calibraciones activas
    (2022 y 2025) hasta el 11-09. Sin id que las distinga, elegir una es
    adivinar -- y elegir "la más nueva" es exactamente cómo una recalibración
    contamina un control viejo."""
    combo = _combo_con(app, [(17, "A092535", "23/06/2022"),
                             (63, "A092535", "28/07/2025")], fecha_ref)
    n_antes = combo.count()

    motivo = posicionar_en_guardado(combo, "A092535")

    assert motivo == "copia_por_ambiguedad"
    assert combo.count() == n_antes + 1
    assert combo.currentData() is None, (
        "con dos candidatas NO se puede adoptar el id de ninguna")
    assert serie_de_item(combo, combo.currentIndex()) == "A092535"


def test_con_id_guardado_si_se_elige_la_exacta(app, fecha_ref):
    """El id (T.0) rompe el empate sin adivinar: identifica, no aporta
    valores. Es para lo que se añadieron las dos columnas."""
    combo = _combo_con(app, [(17, "A092535", "23/06/2022"),
                             (63, "A092535", "28/07/2025")], fecha_ref)

    motivo = posicionar_en_guardado(
        combo, "A092535", equipo_id=17, model="TW33004",
        resolver_guardado=lambda eid, model, serie: eid)

    assert motivo == "por_id"
    assert combo.currentData() == 17, "debe quedarse en la de 2022, no en la nueva"


def test_un_id_que_resuelve_a_otro_equipo_no_se_adopta(app, fecha_ref):
    """R.3: si el id resuelve HOY a otro modelo/serie, no se usa -- se cae al
    respaldo. Aquí hay dos candidatas, así que el respaldo es la copia."""
    combo = _combo_con(app, [(17, "A092535", "23/06/2022"),
                             (63, "A092535", "28/07/2025")], fecha_ref)

    motivo = posicionar_en_guardado(
        combo, "A092535", equipo_id=17, model="TW33004",
        resolver_guardado=lambda eid, model, serie: None)

    assert motivo == "copia_por_ambiguedad"
    assert combo.currentData() is None


# ---------------------------------------------------------------------------
# 4. COMPUERTA DEL HISTÓRICO: la regresión que §0.4 anticipó
# ---------------------------------------------------------------------------

def test_posicionar_no_dispara_las_senales_que_pisan_el_historico(app, fecha_ref):
    """`on_serie_pozo_cambio` está conectado a `currentTextChanged` y
    sobrescribe factor/T0/P0/H0 con los del CATÁLOGO. Si `T.1` posicionara el
    combo sin bloquear señales, todo control de braqui perdería sus valores
    históricos al abrirlo -- un daño mucho mayor que el defecto que arregla.

    Se cuentan las emisiones reales del widget, no se confía en el diseño."""
    combo = _combo_con(app, [(17, "A092535", "28/07/2025")], fecha_ref)
    disparos = []
    combo.currentTextChanged.connect(lambda texto: disparos.append(texto))

    posicionar_en_guardado(combo, "A092535")

    assert combo.currentData() == 17, "el combo sí se posicionó"
    assert disparos == [], (
        "posicionar el combo emitió currentTextChanged: el handler habría "
        f"pisado el factor histórico con el del catálogo. Emisiones: {disparos}")


def test_agregar_la_copia_tampoco_dispara_senales(app, fecha_ref):
    combo = _combo_con(app, [(79, "002343", "17/03/2026")], fecha_ref)
    disparos = []
    combo.currentTextChanged.connect(lambda texto: disparos.append(texto))

    posicionar_en_guardado(combo, "B091982")

    assert disparos == []


def test_el_bloqueo_de_senales_se_restaura(app, fecha_ref):
    """No debe dejar el combo mudo para siempre: quien elige después sí tiene
    que disparar la cascada."""
    combo = _combo_con(app, [(17, "A092535", "28/07/2025")], fecha_ref)
    assert combo.signalsBlocked() is False

    posicionar_en_guardado(combo, "A092535")

    assert combo.signalsBlocked() is False
    disparos = []
    combo.currentTextChanged.connect(lambda texto: disparos.append(texto))
    combo.setCurrentIndex(0)
    assert disparos, "tras posicionar, el combo debe volver a emitir"


# ---------------------------------------------------------------------------
# 5. El rol no rompe a ningún lector actual
# ---------------------------------------------------------------------------

def test_current_data_sigue_siendo_el_id(app, fecha_ref):
    """`currentData()` es lo que leen `on_serie_pozo_cambio`,
    `guardar_DB` y los 18 sitios del censo de R.4. El rol nuevo va en
    `UserRole + 1`, aparte, y no puede desplazarlo."""
    combo = _combo_con(app, [(17, "A092535", "28/07/2025")], fecha_ref)
    combo.setCurrentIndex(1)

    assert combo.currentData() == 17
    assert combo.itemData(1, ROL_SERIE) == "A092535"


def test_el_texto_visible_no_cambia(app, fecha_ref):
    """Compuerta de cero diferencias sobre lo que el físico VE: `T.1` añade un
    rol, no toca la etiqueta. `test_g10_braqui_calibraciones_activas` y
    `test_v1_selector_series_vigencia_por_fecha` fijan este texto."""
    combo = _combo_con(app, [(17, "A092535", "28/07/2025")], fecha_ref)

    esperado, _ = etiqueta_equipo(
        {"id": 17, "serie": "A092535", "fecha_calibr": "28/07/2025",
         "equip_type": "Cámara de pozo"}, fecha_ref)
    assert combo.itemText(1) == esperado


# ---------------------------------------------------------------------------
# 6. Los tres sitios de recarga pasan por la misma lógica
# ---------------------------------------------------------------------------

class _RecordFalso:
    def __init__(self, columnas):
        self._columnas = list(columnas)

    def indexOf(self, nombre):
        return self._columnas.index(nombre) if nombre in self._columnas else -1


class _QueryFalsa:
    """Doble mínimo de `QSqlQuery` -- solo `value(i)`, que es todo lo que el
    método real usa. La lógica que se ejercita es la de PRODUCCIÓN."""

    def __init__(self, columnas, valores):
        self._valores = list(valores)
        self.record_ = _RecordFalso(columnas)

    def value(self, indice):
        return self._valores[indice]


COLUMNAS_SM = ('modelo', 'serie_cp', 'modelo_elec', 'serie_ele',
               'calibracion', 'electrometro', 't0', 'p0', 'h0',
               'equipo_id_cp', 'equipo_id_ele')


def _pantalla_braqui_minima(app, fecha_ref, calibraciones_pozo):
    """Objeto REAL de `PruebaMensualBraq` sin su `__init__` pesado -- el
    patrón estándar de este proyecto (`Clase.__new__` + `QWidget.__init__`)."""
    from PyQt5.QtWidgets import QLineEdit, QWidget
    from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq

    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)

    obj.combo_modelo = QComboBox()
    obj.combo_modelo.addItems(["TW33004"])
    obj.combo_serie = _combo_con(app, calibraciones_pozo, fecha_ref)
    obj.combo_modelo_elec = QComboBox()
    obj.combo_modelo_elec.addItems(["CDX-2000B"])
    obj.combo_serie_elec = _combo_con(app, [(79, "002343", "17/03/2026")], fecha_ref)
    for nombre in ("line_cal", "line_cal_elec", "t0", "p0", "h0"):
        setattr(obj, nombre, QLineEdit())
    return obj


class TestLaRecargaRealDeBraqui:
    """Ejercita `PruebaMensualBraq._restaurar_equipos_guardados`, el método de
    PRODUCCIÓN que `T.1` introduce. Contra el código anterior estos tests dan
    `AttributeError`: el método no existe y la recarga comparaba textos."""

    def test_muestra_la_serie_guardada_con_camara_activa(self, app, fecha_ref):
        obj = _pantalla_braqui_minima(app, fecha_ref, [(17, "A092535", "28/07/2025")])
        query = _QueryFalsa(COLUMNAS_SM, [
            "TW33004", "A092535", "CDX-2000B", "002343",
            464700.0, 1.0, 22.0, 760.0, 50.0, None, None])

        obj._restaurar_equipos_guardados(query, query.record_)

        assert obj.combo_serie.currentData() == 17
        assert serie_de_item(obj.combo_serie, obj.combo_serie.currentIndex()) == "A092535"

    def test_el_factor_historico_gana_sobre_el_del_catalogo(self, app, fecha_ref):
        """LA COMPUERTA. Se simula `on_serie_pozo_cambio` conectado de verdad:
        si el posicionamiento emitiera la señal, el factor del CATÁLOGO
        (999999) pisaría el guardado (464700) -- §0.4 del plan."""
        obj = _pantalla_braqui_minima(app, fecha_ref, [(17, "A092535", "28/07/2025")])

        def simular_cascada_del_catalogo(_texto):
            obj.line_cal.setText("999999.0")   # el vigente del catálogo
            obj.t0.setText("21.0")
            obj.p0.setText("999.0")
            obj.h0.setText("40.0")

        obj.combo_serie.currentTextChanged.connect(simular_cascada_del_catalogo)

        query = _QueryFalsa(COLUMNAS_SM, [
            "TW33004", "A092535", "CDX-2000B", "002343",
            464700.0, 1.0, 22.0, 760.0, 50.0, None, None])
        obj._restaurar_equipos_guardados(query, query.record_)

        assert obj.line_cal.text() == "464700.0", (
            "el factor mostrado es el del CATÁLOGO, no el que el control "
            "guardó: la recarga pisó el histórico")
        assert obj.t0.text() == "22.0"
        assert obj.p0.text() == "760.0"
        assert obj.h0.text() == "50.0"

    def test_con_dos_candidatas_y_sin_id_muestra_la_copia(self, app, fecha_ref):
        obj = _pantalla_braqui_minima(
            app, fecha_ref, [(17, "A092535", "23/06/2022"),
                             (63, "A092535", "28/07/2025")])
        query = _QueryFalsa(COLUMNAS_SM, [
            "TW33004", "A092535", "CDX-2000B", "002343",
            464700.0, 1.0, 22.0, 760.0, 50.0, None, None])

        obj._restaurar_equipos_guardados(query, query.record_)

        assert obj.combo_serie.currentData() is None
        assert obj.line_cal.text() == "464700.0"

    def test_camara_borrada_no_deja_el_combo_en_el_marcador(self, app, fecha_ref):
        """El escenario de los 14 registros con el CDX-2000B anulado."""
        obj = _pantalla_braqui_minima(app, fecha_ref, [(63, "A972662", "07/02/2024")])
        query = _QueryFalsa(COLUMNAS_SM, [
            "TW33004", "A092535", "CDX-2000B", "B091982",
            464700.0, 1.0, 22.0, 760.0, 50.0, None, None])

        obj._restaurar_equipos_guardados(query, query.record_)

        assert obj.combo_serie.currentText() != "Seleccionar Serie..."
        assert serie_de_item(obj.combo_serie, obj.combo_serie.currentIndex()) == "A092535"
        assert serie_de_item(obj.combo_serie_elec,
                             obj.combo_serie_elec.currentIndex()) == "B091982"


def test_los_tres_sitios_usan_el_criterio_compartido():
    """Corolario 1 (*una operación, una definición*) y 4 (*contar las
    copias*): son TRES pantallas sin ancestro común. Si una vuelve a
    resolver por texto a mano, el defecto reaparece solo ahí y en silencio,
    que es como nació DP-105."""
    import ast
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    for archivo in ("ui/paginasControles/PruebasMensuales/braq_mensual.py",
                    "ui/paginasControles/PruebasDiarias/braquiterapia.py"):
        texto = (raiz / archivo).read_text(encoding="utf-8", errors="replace")
        assert "posicionar_en_guardado" in texto, archivo
        assert "agregar_item_calibracion" in texto, archivo

    # y ninguna de las dos resuelve ya la serie por findText exacto sobre el
    # texto decorado
    braqui = (raiz / "ui/paginasControles/PruebasDiarias/braquiterapia.py"
              ).read_text(encoding="utf-8", errors="replace")
    arbol = ast.parse(braqui)
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.FunctionDef) and nodo.name == "set_combo"):
            raise AssertionError(
                "`set_combo` (findText exacto sobre la etiqueta decorada) "
                "sigue vivo en Linealidad: es el defecto de DP-105")
