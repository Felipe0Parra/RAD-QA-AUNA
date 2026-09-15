"""G1 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md): la fecha de calibracion de
un equipo se guardaba con `.text()` de un QDateEdit sin `setDisplayFormat`
explicito -- heredaba el formato corto del locale del sistema operativo
("M/d/yyyy" en Windows ingles). `equipos.py::calib_date` nace en el
constructor generico (`PruebasDiarias.createInterface`, rama QDateEdit) y
nunca fija el formato en ningun otro punto: era el ultimo QDateEdit de la app
que dependia del locale (I4 arreglo el de la calculadora el 16-07).

Reproducido con datos reales (2026-07-31): `QDate(2026, 30, 7)` (mes=30 al
interpretar "7/30/2026" como dd/MM) NO lanza excepcion -- produce un QDate
invalido (`isValid() == False`). `addYears()` sobre un QDate invalido sigue
invalido, y `hoy <= invalido` es `False` -- por eso un equipo recien creado
con la fecha de HOY aparecia "vencido": la guarda documentada de
`es_vigente_en_fecha` ("formato invalido -> vigente") nunca se activaba
porque no habia excepcion que atrapar.

NOTA DE INFRAESTRUCTURA DE TEST (leer antes de tocar este archivo): la
fixture `app` de alcance de modulo NO es decorativa y NO se puede sustituir
por una llamada suelta a `QApplication.instance() or QApplication([])` dentro
del test. Si el valor de retorno se descarta, nadie mantiene una referencia
Python viva a la QApplication, el recolector la destruye (verificado:
`QApplication.instance()` devuelve `None` inmediatamente despues) y el
siguiente `QWidget.__init__` aborta el interprete con SIGABRT -- un "Fatal
Python error: Aborted", no un fallo de pytest. El sintoma es no
determinista: depende de si algun otro modulo de la suite dejo una
QApplication viva antes. Pedir `app` como parametro hace que pytest guarde la
referencia durante todo el modulo. Es la convencion ya establecida en la
suite (test_h35, test_a6_2, test_calculadora_dosis_h1, y ~10 archivos mas).
"""
import os
import sqlite3

import pandas as pd
import pytest
from PyQt5.QtCore import QDate, QLocale
from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

from services.vigencia_equipo import es_vigente_en_fecha
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.paginasGuia.equipos import Config

from _bd_referencia import BD_QA  # DP-104: fuente única de rutas de BD
DB = str(BD_QA)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _instancia_pelada():
    """PruebaBasico sin su __init__ pesado (BD/Excel), solo el QWidget --
    mismo patron que test_h35_date_edit_ancho_minimo.py."""
    obj = PruebaBasico.__new__(PruebaBasico)
    QWidget.__init__(obj)
    return obj


def _fila_date_edit(nombre="calib_date", prueba="edit_tabla"):
    """Una fila de widgets.xlsx equivalente a la que crea `calib_date` en la
    hoja 'edit_tabla' (la del formulario de equipos)."""
    return pd.DataFrame([{
        "prueba": prueba, "nombres": nombre, "widget_type": "QDateEdit",
        "descripcion": None, "pose": (0, 0, 1, 1),
    }])


class TestFormatoFechaWidgetIndependienteDeLocale:
    def test_qdateedit_de_createinterface_usa_dd_mm_yyyy_bajo_locale_ingles(self, app):
        """Reproduce el Windows del fisico: locale global en-US, cuyo formato
        corto es M/d/yyyy. El QDateEdit creado por createInterface -- el mismo
        punto unico que produce `equipos.py::calib_date` -- debe mostrar
        dd/MM/yyyy igual. ROJO ANTES DEL FIX: sin `setDisplayFormat` el widget
        hereda el locale y `.text()` devuelve '7/30/26'."""
        previo = QLocale()
        QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
        try:
            obj = _instancia_pelada()
            obj.createInterface(_fila_date_edit(), 1)
            obj.calib_date.setDate(QDate(2026, 7, 30))
            assert obj.calib_date.text() == "30/07/2026"
        finally:
            QLocale.setDefault(previo)

    def test_tambien_con_locale_por_widget(self, app):
        """Misma garantia por la otra via (locale del widget, sin tocar el
        default global): `displayFormat` manda sobre el locale en ambos
        casos."""
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(), 1)
        obj.calib_date.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        obj.calib_date.setDate(QDate(2026, 7, 30))
        assert obj.calib_date.text() == "30/07/2026"

    def test_formularios_que_fijan_otro_formato_despues_lo_conservan(self, app):
        """Anti-regresion: los formularios que cambian el formato DESPUES de
        createInterface (Halcyon diario -> yyyy/MM/dd, TAC -> yyyy/MM, los
        mensuales -> dd/MM/yyyy) siguen ganando. El fix solo fija un valor
        por defecto en la creacion, nunca fuerza nada despues."""
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(nombre="date_box", prueba="encabezado"), 1)
        obj.date_box.setDisplayFormat("yyyy/MM/dd")
        obj.date_box.setDate(QDate(2026, 7, 30))
        assert obj.date_box.text() == "2026/07/30"

    def test_el_ancho_minimo_no_cambia_con_el_fix(self, app):
        """El fix inserta setDisplayFormat ANTES del calculo de
        `ancho_minimo_fecha`, que recibe el formato por parametro explicito
        ("dd/MM/yyyy") -- verificar que sigue dando el mismo piso y que I5 no
        se degrada."""
        obj = _instancia_pelada()
        obj.createInterface(_fila_date_edit(nombre="date_box", prueba="encabezado"), 1)
        fm = obj.date_box.fontMetrics()
        # Decoracion dura sin la holgura (mismo criterio que test_h35).
        necesario = fm.horizontalAdvance("00/00/0000") + 34
        assert obj.date_box.minimumWidth() >= necesario


class TestGuardaFechaInvalidaEsVigenteEnFecha:
    def test_fecha_mes_dia_invertidos_produce_qdate_invalido_sin_excepcion(self):
        """Ancla el hallazgo que explica por que la guarda documentada no se
        activaba: QDate(2026, 30, 7) no lanza ValueError -- es un QDate nulo
        silencioso, asi que el `except (ValueError, AttributeError)` de
        es_vigente_en_fecha nunca lo veia."""
        assert QDate(2026, 30, 7).isValid() is False

    def test_es_vigente_en_fecha_con_mes_invalido_devuelve_true_tras_el_fix(self):
        """ROJO ANTES DEL FIX: devuelve False (la comparacion
        `hoy <= invalido.addYears(n)` es False), que es la alarma falsa de
        "vencido" que reporto el fisico. Con la guarda, cumple el contrato ya
        documentado en el docstring de la funcion desde V1."""
        hoy = QDate(2026, 7, 31)
        assert es_vigente_en_fecha("7/30/2026", "Cámara de ionización", hoy) is True

    def test_la_misma_fecha_bien_formada_sigue_evaluando_vigencia_normal(self):
        """Anti-regresion: '30/07/2026' (dd/MM/yyyy correcto) pasa por la via
        normal, no por la guarda nueva."""
        hoy = QDate(2026, 7, 31)
        assert es_vigente_en_fecha("30/07/2026", "Cámara de ionización", hoy) is True

    def test_dia_sin_cero_a_la_izquierda_sigue_parseando_bien(self):
        """RESTRICCION EXPLICITA DEL PLAN (G7 clase B / DA-23): el split
        tolerante manual acepta '5/02/2024'. 10 filas reales de produccion
        llevan ese formato y son datos CORRECTOS, solo sin cero (una de ellas,
        id 72, esta ACTIVA). Si alguien "moderniza" esta funcion a
        `QDate.fromString(t, "dd/MM/yyyy")` -- que SI rechaza el dia sin
        cero -- esas 10 filas se volverian invalidas de golpe y, por el mismo
        mecanismo de este bug, apareceria "vencida" en silencio. Este test
        debe seguir verde con cualquier refactor de la funcion."""
        hoy = QDate(2026, 7, 31)
        # 05/02/2024 + 2 anios = 05/02/2026, anterior a hoy -> vencida.
        # Lo que importa es que PARSEA (False por vigencia real, no True por
        # la guarda de formato invalido).
        assert es_vigente_en_fecha("5/02/2024", "Cámara de ionización", hoy) is False
        # Con una referencia dentro de la ventana, sigue vigente.
        assert es_vigente_en_fecha(
            "5/02/2024", "Cámara de ionización", QDate(2024, 6, 1)) is True


def _config_pelado(texto_fecha):
    """Config (equipos.py) sin su __init__ pesado (BD/tabla), solo el
    QLineEdit que verificar_vigencia necesita -- mismo patron que
    test_f7_reactivar_equipo.py::_instancia_con_formulario. Un QLineEdit
    basta: verificar_vigencia solo llama .text() y .setStyleSheet(), que
    QLineEdit tiene igual que QDateEdit."""
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.calib_date = QLineEdit(texto_fecha)
    return obj


class TestG4UnaSolaFuenteDeVigencia:
    """G4 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md): `verificar_vigencia`
    (el formulario de edicion) tenia su PROPIA logica -- parseo manual +
    `daysTo <= 365*vigencia` (la aproximacion que F8 ya habia retirado de
    `es_vigente_en_fecha` el 29-07) -- mientras `verificar_vigencia_equipo`
    (la tabla del catalogo, F8) ya usaba la fuente unica. Dos calculos
    distintos para la MISMA pregunta, con codigo duplicado y con una
    aproximacion menos precisa que la que el propio proyecto ya habia
    corregido en el otro lado."""

    def test_formulario_y_tabla_coinciden_equipo_claramente_vigente(self, app):
        obj = _config_pelado("01/01/2026")
        veredicto_form = obj.verificar_vigencia(("Cámara de ionización",))
        veredicto_tabla = obj.verificar_vigencia_equipo(
            "01/01/2026", "Cámara de ionización")
        assert veredicto_form == veredicto_tabla

    def test_formulario_y_tabla_coinciden_equipo_claramente_vencido(self, app):
        obj = _config_pelado("01/01/2020")
        veredicto_form = obj.verificar_vigencia(("Cámara de ionización",))
        veredicto_tabla = obj.verificar_vigencia_equipo(
            "01/01/2020", "Cámara de ionización")
        assert veredicto_form == veredicto_tabla

    def test_formulario_y_tabla_coinciden_con_fecha_invalida(self, app):
        """Ambas rutas ya delegan en la misma guarda de G1 -- ninguna
        "adivina" un veredicto propio para un formato invalido."""
        obj = _config_pelado("7/30/2026")
        veredicto_form = obj.verificar_vigencia(("Cámara de ionización",))
        veredicto_tabla = obj.verificar_vigencia_equipo(
            "7/30/2026", "Cámara de ionización")
        assert veredicto_form == veredicto_tabla is True

    def test_diverge_por_la_aproximacion_de_365_dias_rojo_antes_del_fix(
            self, app, monkeypatch):
        """ROJO ANTES DEL FIX -- reproduce el caso EXACTO que F8 documento
        (PLAN_F_CIERRE_ESTANDAR_29-07.md): una calibracion cuyo intervalo de
        vigencia contiene un 29 de febrero bisiesto. `fecha_cal=01/01/2024`,
        vigencia=2 anios, referencia=01/01/2026 (el bisiesto 2024 cae DENTRO
        del intervalo).

        - Aniversario exacto (unica fuente, F8): 01/01/2026 <= 01/01/2026
          -> VIGENTE.
        - Aproximacion `daysTo <= 365*2` (la que tenia `verificar_vigencia`
          ANTES de este fix): daysTo=731 (731 > 730) -> NO VIGENTE.

        Se fuerza `QDate.currentDate()` (via monkeypatch, en vez de
        depender de la fecha real del dia en que corra la suite) porque la
        divergencia solo existe para referencias que caen exactamente en
        esa ventana de 1 dia -- el propio F8 midio que HOY (31-07) ninguna
        fila real cae ahi.
        """
        monkeypatch.setattr(QDate, "currentDate",
                            staticmethod(lambda: QDate(2026, 1, 1)))

        obj = _config_pelado("01/01/2024")
        veredicto_form = obj.verificar_vigencia(("Cámara de ionización",))
        veredicto_tabla = obj.verificar_vigencia_equipo(
            "01/01/2024", "Cámara de ionización")

        assert veredicto_tabla is True  # aniversario exacto, ya via F8
        assert veredicto_form == veredicto_tabla, (
            f"El formulario ({veredicto_form}) y la tabla ({veredicto_tabla}) "
            f"deben coincidir SIEMPRE -- son la misma pregunta."
        )

    def test_borde_verde_cuando_vigente(self, app):
        obj = _config_pelado("01/01/2026")
        obj.verificar_vigencia(("Cámara de ionización",))
        assert "138, 189, 44" in obj.calib_date.styleSheet()

    def test_borde_rojo_cuando_no_vigente(self, app):
        obj = _config_pelado("01/01/2020")
        obj.verificar_vigencia(("Cámara de ionización",))
        assert "red" in obj.calib_date.styleSheet()


@pytest.mark.skipif(not os.path.exists(DB),
                    reason="BD de produccion no disponible en este entorno")
class TestTripwireFechasNoParseablesEnProduccion:
    """Patron de allowlist verificable de A6.1: no es una exencion silenciosa.
    Si aparece una fila NUEVA con fecha_calibr no parseable, la suite se pone
    roja y senala el id -- no se auto-repara ni se ignora.

    G7 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md, DA-23, 2026-07-31)
    normalizo los ids 57/58 ('7/28/2025' -> '28/07/2025', confirmado contra
    el certificado HDR12899) -- la allowlist queda vacia. El segundo assert
    de abajo sigue de guardia: si algun dia aparece una fila nueva no
    parseable, la señala igual."""

    ALLOWLIST_IDS_FECHA_NO_PARSEABLE = set()

    def test_filas_con_fecha_no_parseable_son_exactamente_la_allowlist(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            malas = set()
            cur = con.execute(
                "SELECT id, fecha_calibr FROM equipos "
                "WHERE fecha_calibr IS NOT NULL AND trim(fecha_calibr) <> ''"
            )
            for id_, fecha in cur.fetchall():
                try:
                    dia, mes, anio = map(int, fecha.split("/"))
                    if not QDate(anio, mes, dia).isValid():
                        malas.add(id_)
                except (ValueError, AttributeError):
                    malas.add(id_)
        finally:
            con.close()

        nuevas = malas - self.ALLOWLIST_IDS_FECHA_NO_PARSEABLE
        assert not nuevas, (
            f"Fila(s) nueva(s) con fecha_calibr no parseable, fuera de la "
            f"allowlist conocida: ids {sorted(nuevas)}. Verificar contra el "
            f"certificado antes de decidir si es un dato real o un defecto "
            f"del formulario."
        )
        desaparecidas = self.ALLOWLIST_IDS_FECHA_NO_PARSEABLE - malas
        assert not desaparecidas, (
            f"La(s) fila(s) {sorted(desaparecidas)} ya no tienen fecha no "
            f"parseable -- si se ejecuto G7, vaciar esta allowlist en el "
            f"mismo commit."
        )
