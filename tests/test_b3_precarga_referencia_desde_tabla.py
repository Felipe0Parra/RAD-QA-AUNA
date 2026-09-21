"""B.3 (PLAN_REFERENCIAS_EDITABLES_21-09.md): el mensual precarga
`val_teo_{energia}` con la referencia VIGENTE de la tabla `referencias_qc`
para ESE equipo -- pero solo cuando el control aún no tiene copia guardada.

Garantía titular de toda la ronda (§B.3 del plan): *"un control nuevo llega
con la referencia que fijó el jefe; uno viejo se sigue viendo con la que
tenía cuando se firmó, aunque la hayan cambiado después."* Por eso el orden
importa: la BD se carga PRIMERO y la precarga solo llena lo que la BD dejó
vacío -- invertirlo pisaría el histórico (el error exacto que H2.7 corrigió
en el iX, cuyo borrador se cargaba después de la BD y la pisaba).

Rojo-antes-que-verde real: `git stash` (sin `-u`) sobre
`seiscientos_mensual.py`/`ix_mensual.py` deja el widget vacío en un control
nuevo, y el archivo de test (untracked) no se stashea.
"""
import os
import sqlite3

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import (QApplication, QGridLayout, QLineEdit, QMessageBox,
                             QWidget)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.referencias_qc import fijar_referencia
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    DatabaseManager, PruebaMensual600)

ENERGIAS_IX = ("6mv", "15mv", "6mev", "9mev", "12mev", "15mev")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES ('lamaya', 'x', 'Luz Adriana Maya', 1, '1', 'Físico Médico', 'jefe')")
    # el físico que abre el control en los tests de pantalla real (R7)
    con.execute("INSERT INTO users (fullname) VALUES ('Fisico Real')")
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sin_avisos(monkeypatch):
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, nombre,
                            staticmethod(lambda *a, **k: None))


def _fijar(equipo, energia, valor, magnitud="calidad"):
    ok, motivo = fijar_referencia(
        equipo, magnitud, energia, valor, "puesta en servicio",
        "valor medido en la puesta en servicio", "lamaya")
    assert ok, motivo


def _sembrar_fila_guardada(ruta, ref, energia, val_teo_calidad, activo=1):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO dosimetriaMen (ref, energia, val_teo_calidad, activo) "
        "VALUES (?, ?, ?, ?)", (ref, energia, val_teo_calidad, activo))
    con.commit()
    con.close()


def _calidad_attr(energia):
    return (f"ln_calidad_pdd20_10_{energia}" if energia.endswith("mv")
            else f"ln_calidad_j2_j1_{energia}")


def _pelado(clase, equipo_f, energias, val_teo_texto=""):
    """Objeto 'pelado' con SOLO los widgets de dosimetría de `energias`
    (mismo patrón que A.1: discrepancias() salta las energías sin widgets)."""
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj._debounce_timers = {}
    obj.equipo_f = equipo_f
    obj.ENERGIAS = list(energias)
    for e in energias:
        setattr(obj, f"val_teo_{e}", QLineEdit(val_teo_texto))
        setattr(obj, f"ln_dosis_ref_cgy_um_{e}", QLineEdit(""))
        setattr(obj, f"ln_discrepancia_dosis_{e}", QLineEdit(""))
        setattr(obj, _calidad_attr(e), QLineEdit(""))
        setattr(obj, f"ln_discrepancia_calidad_{e}", QLineEdit(""))
    return obj


def _df_lines(energias):
    lineas = []
    for e in energias:
        lineas += [f"val_teo_{e}", _calidad_attr(e),
                   f"ln_discrepancia_calidad_{e}"]
    return lineas


def _huella(obj, nombres):
    """Estado observable de cada widget: texto, solo-lectura y habilitado."""
    return {n: (getattr(obj, n).text(), getattr(obj, n).isReadOnly(),
                getattr(obj, n).isEnabled()) for n in nombres}


class TestControlNuevoPrecargaDesdeLaTabla:
    def test_halcyon_muestra_0_627_y_la_discrepancia_sale_1_12(self, app, bd_temporal):
        """El caso real medido (DP-25): Halcyon 06/2026, calidad 0.62 contra
        la referencia del Halcyon (0.627) da 1.12 % y cumple; con el literal
        del iX daba 6.77 %."""
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj.ln_calidad_pdd20_10_6mv.setText("0.62")

        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)

        assert obj.val_teo_6mv.text() == "0.627"
        obj.discrepancias()
        assert float(obj.ln_discrepancia_calidad_6mv.text()) == pytest.approx(1.12, abs=0.01)

    def test_600_recibe_la_del_600(self, app, bd_temporal):
        _fijar("Clinac 600", "6mv", 0.6667)
        obj = _pelado(PruebaMensual600, "Clinac 600", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == "0.6667"

    def test_ix_cada_energia_recibe_la_suya(self, app, bd_temporal):
        valores = {"6mv": 0.665, "15mv": 0.761, "6mev": 0.483,
                   "9mev": 0.500, "12mev": 0.606, "15mev": 0.605}
        for e, v in valores.items():
            _fijar("Clinac ix", e, v)
        obj = _pelado(PruebaMensualIX, "Clinac ix", ENERGIAS_IX)

        obj._precargar_referencia_calidad(_df_lines(ENERGIAS_IX), "dosimetriaMen", ref=1)

        for e, v in valores.items():
            assert float(getattr(obj, f"val_teo_{e}").text()) == pytest.approx(v), e

    def test_la_referencia_es_del_equipo_no_de_la_energia(self, app, bd_temporal):
        """DP-25 en una línea: la misma energía (6 MV) vale distinto por
        máquina, y la precarga distingue."""
        _fijar("Clinac ix", "6mv", 0.665)
        _fijar("Halcyon", "6mv", 0.627)
        halcyon = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        ix = _pelado(PruebaMensualIX, "Clinac ix", ["6mv"])

        halcyon._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        ix._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=2)

        assert halcyon.val_teo_6mv.text() == "0.627"
        assert ix.val_teo_6mv.text() == "0.665"

    def test_una_referencia_de_otra_energia_no_entra(self, app, bd_temporal):
        _fijar("Clinac ix", "15mv", 0.761)
        obj = _pelado(PruebaMensualIX, "Clinac ix", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == ""

    def test_solo_la_calidad_no_la_dosis_ni_otra_magnitud(self, app, bd_temporal):
        """R5: la pantalla muestra SOLO la referencia de calidad; una fila
        de otra magnitud para la misma clave no debe colarse en el campo."""
        _fijar("Halcyon", "6mv", 1.0009, magnitud="dosis")
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == ""


class TestSinReferenciaNoSeInventa:
    def test_sin_fila_en_la_tabla_el_widget_queda_vacio(self, app, bd_temporal):
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == ""

    def test_y_A1_cae_al_respaldo_con_el_widget_vacio(self, app, bd_temporal):
        """El widget vacío no deja al cálculo sin referencia: A.1 usa el
        respaldo por energía (mismo comportamiento de hoy)."""
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj.ln_calidad_pdd20_10_6mv.setText("0.60")
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        obj.discrepancias()
        esperado = round(abs((0.665 - 0.60) / 0.665 * 100), 2)
        assert float(obj.ln_discrepancia_calidad_6mv.text()) == pytest.approx(esperado, abs=0.01)

    def test_una_referencia_anulada_no_se_precarga(self, app, bd_temporal):
        """Solo la VIGENTE: la que el jefe reemplazó queda en el historial,
        no en el formulario."""
        _fijar("Halcyon", "6mv", 0.600)
        _fijar("Halcyon", "6mv", 0.627)  # anula la anterior
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == "0.627"


class TestLoTecleadoNoSePisa:
    def test_widget_con_texto_no_se_toca(self, app, bd_temporal):
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"], val_teo_texto="0.640")
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == "0.640"

    def test_solo_actua_sobre_dosimetriaMen(self, app, bd_temporal):
        """`addsomething` se llama también para `preguntas` y otras tablas
        con widgets que no tienen nada que ver."""
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "preguntas", ref=1)
        assert obj.val_teo_6mv.text() == ""

    def test_un_widget_fuera_de_df_lines_no_se_toca(self, app, bd_temporal):
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad([], "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == ""


class TestLaCopiaGuardadaManda:
    """LA garantía titular: un control ya firmado se sigue viendo con la
    referencia contra la que se juzgó, aunque el jefe la haya cambiado."""

    def test_600_control_guardado_con_0_627_y_referencia_cambiada_a_0_640(
            self, app, bd_temporal):
        _sembrar_fila_guardada(bd_temporal, ref=7, energia="6mv", val_teo_calidad=0.627)
        _fijar("Halcyon", "6mv", 0.640)  # cambiada DESPUÉS de firmar el control
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        df_lines = _df_lines(["6mv"])

        # Camino real del 600/Halcyon: primero la BD, luego la precarga.
        obj._cargar_de_bd(df_lines, "dosimetriaMen", 7)
        obj._precargar_referencia_calidad(df_lines, "dosimetriaMen", ref=7)

        assert float(obj.val_teo_6mv.text()) == pytest.approx(0.627)

    def test_ix_control_guardado_con_0_665_y_referencia_cambiada(
            self, app, bd_temporal):
        _sembrar_fila_guardada(bd_temporal, ref=8, energia="6mv", val_teo_calidad=0.665)
        _fijar("Clinac ix", "6mv", 0.700)
        obj = _pelado(PruebaMensualIX, "Clinac ix", ["6mv"])
        df_lines = _df_lines(["6mv"])

        obj._cargar_dosimetria_bd_ix(df_lines, "dosimetriaMen", 8)
        obj._precargar_referencia_calidad(df_lines, "dosimetriaMen", ref=8)

        assert float(obj.val_teo_6mv.text()) == pytest.approx(0.665)

    def test_fila_guardada_sin_referencia_no_se_rellena_con_la_de_hoy(
            self, app, bd_temporal):
        """[medido] `val_teo_calidad` es NULL en 4/5 filas del 600 (§0.3).
        Ese control se juzgó con lo que el código usaba entonces; ponerle
        ahora la referencia de la tabla lo haría parecer juzgado contra un
        número que nadie vio. Hay fila guardada -> la precarga no actúa."""
        _sembrar_fila_guardada(bd_temporal, ref=9, energia="6mv", val_teo_calidad=None)
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        df_lines = _df_lines(["6mv"])

        obj._cargar_de_bd(df_lines, "dosimetriaMen", 9)
        obj._precargar_referencia_calidad(df_lines, "dosimetriaMen", ref=9)

        assert obj.val_teo_6mv.text() == ""

    def test_ix_solo_la_energia_con_fila_queda_protegida(self, app, bd_temporal):
        """El iX guarda una fila POR energía: la guardada conserva su copia,
        la que aún no existe se precarga."""
        _sembrar_fila_guardada(bd_temporal, ref=10, energia="6mv", val_teo_calidad=0.665)
        _fijar("Clinac ix", "6mv", 0.700)
        _fijar("Clinac ix", "15mv", 0.761)
        obj = _pelado(PruebaMensualIX, "Clinac ix", ["6mv", "15mv"])
        df_lines = _df_lines(["6mv", "15mv"])

        obj._cargar_dosimetria_bd_ix(df_lines, "dosimetriaMen", 10)
        obj._precargar_referencia_calidad(df_lines, "dosimetriaMen", ref=10)

        assert float(obj.val_teo_6mv.text()) == pytest.approx(0.665)
        assert float(obj.val_teo_15mv.text()) == pytest.approx(0.761)

    def test_una_fila_anulada_no_cuenta_como_guardada(self, app, bd_temporal):
        """La generación superada (activo=0) no es la copia vigente: si no
        queda ninguna vigente para esa energía, el control está 'sin fila'."""
        _sembrar_fila_guardada(bd_temporal, ref=11, energia="6mv",
                               val_teo_calidad=0.500, activo=0)
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=11)
        assert obj.val_teo_6mv.text() == "0.627"

    def test_el_control_de_otro_ref_no_protege_al_mio(self, app, bd_temporal):
        _sembrar_fila_guardada(bd_temporal, ref=20, energia="6mv", val_teo_calidad=0.500)
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=21)
        assert obj.val_teo_6mv.text() == "0.627"


class TestPrecargaSilenciosaYAcotada:
    def test_no_emite_textChanged_mientras_rellena(self, app, bd_temporal):
        """blockSignals (precedente P3/DP-56): rellenar no debe disparar el
        recálculo a media precarga."""
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        emitidas = []
        obj.val_teo_6mv.textChanged.connect(emitidas.append)

        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)

        assert obj.val_teo_6mv.text() == "0.627"
        assert emitidas == []

    def test_las_senales_quedan_reactivadas_despues(self, app, bd_temporal):
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.signalsBlocked() is False
        emitidas = []
        obj.val_teo_6mv.textChanged.connect(emitidas.append)
        obj.val_teo_6mv.setText("0.630")
        assert emitidas == ["0.630"]

    def test_huella_de_las_demas_secciones_no_cambia(self, app, bd_temporal):
        """'La huella de estado de las demás secciones no cambia' (§B.3):
        solo se mueve val_teo_*; ningún otro widget cambia texto, modo de
        solo-lectura ni habilitación."""
        _fijar("Halcyon", "6mv", 0.627)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj.ln_calidad_pdd20_10_6mv.setText("0.62")
        obj.ln_observaciones_dosi = QLineEdit("sin novedad")
        otros = ["ln_calidad_pdd20_10_6mv", "ln_dosis_ref_cgy_um_6mv",
                 "ln_discrepancia_dosis_6mv", "ln_discrepancia_calidad_6mv",
                 "ln_observaciones_dosi"]
        antes = _huella(obj, otros)

        obj._precargar_referencia_calidad(
            _df_lines(["6mv"]) + ["ln_observaciones_dosi"], "dosimetriaMen", ref=1)

        assert _huella(obj, otros) == antes

    def test_un_fallo_de_la_tabla_no_rompe_la_pantalla(self, app, bd_temporal, monkeypatch):
        """addsomething envuelve todo en un try/except que, si algo lanza,
        se salta la creación de los botones: la precarga NO puede propagar."""
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mod

        def _falla(*a, **k):
            raise RuntimeError("tabla no disponible")

        monkeypatch.setattr(mod, "leer_referencia", _falla)
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        obj._precargar_referencia_calidad(_df_lines(["6mv"]), "dosimetriaMen", ref=1)
        assert obj.val_teo_6mv.text() == ""

    def test_registra_que_valor_vino_de_la_tabla(self, app, bd_temporal):
        """Insumo de B.4 (origen_referencia): al guardar hay que poder
        distinguir lo que llegó de la tabla de lo que se tecleó encima."""
        _fijar("Clinac ix", "6mv", 0.665)
        obj = _pelado(PruebaMensualIX, "Clinac ix", ["6mv", "15mv"])
        obj._precargar_referencia_calidad(
            _df_lines(["6mv", "15mv"]), "dosimetriaMen", ref=1)
        assert obj._referencia_precargada == {"6mv": "0.665"}


class TestOrdenBDPrimeroPrecargaDespues:
    """Invertir el orden pisaría el histórico (H2.7). Se afirma con espías
    sobre las dos rutas reales de carga."""

    def _espiar(self, obj, orden):
        obj._obtener_lineEdit = lambda df, typee: ["val_teo_6mv"]
        obj._cargar_de_bd = lambda *a, **k: orden.append("bd")
        obj._cargar_dosimetria_bd_ix = lambda *a, **k: orden.append("bd")
        obj._precargar_referencia_calidad = lambda *a, **k: orden.append("precarga")
        obj._crear_accion_botones = lambda layout: (orden.append("botones"), (None, None))[1]
        obj._configurar_eventos_campos = lambda *a, **k: orden.append("eventos")

    def test_600_halcyon_bd_luego_precarga_luego_botones(self, app):
        obj = _pelado(PruebaMensual600, "Halcyon", ["6mv"])
        orden = []
        self._espiar(obj, orden)
        obj.addsomething(QWidget(), pd.DataFrame(), "dosimetria", "dosimetriaMen", 0, ref=1)
        assert orden == ["bd", "precarga", "botones", "eventos"]

    def test_ix_bd_luego_precarga_luego_botones(self, app):
        obj = _pelado(PruebaMensualIX, "Clinac ix", ["6mv"])
        orden = []
        self._espiar(obj, orden)
        contenedor = QWidget()
        contenedor.setLayout(QGridLayout())
        df = pd.DataFrame({"widget_type": ["QLineEdit"], "prueba": ["dosimetria"],
                           "nombres": ["val_teo_6mv"]})
        # `addsomething_ix` no llama a _crear_accion_botones (arma los suyos):
        # el orden que importa aquí es BD -> precarga, antes de cualquier
        # widget nuevo.
        obj.addsomething_ix(contenedor, df, "dosimetria", "dosimetriaMen", 0, ref=1)
        assert orden[:2] == ["bd", "precarga"]


class TestEnLasPantallasRealesDeExtremoAExtremo:
    """Las tres pantallas reales, construidas por su `__init__` y arrancadas
    con "Iniciar" (el mismo camino del físico): el campo llega precargado
    con la referencia de SU equipo. Sin esto, los tests de arriba probarían
    el método pero no que las dos rutas de `addsomething` lo invoquen."""

    def _iniciar(self, obj, inputs):
        obj.fisico1.addItem("Fisico Real", 1)
        obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
        obj.user_id_f1 = "Fisico Real"
        obj.user_id_f2 = None
        obj._iniciar_moviendo_tabla(inputs)

    def test_600(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _fijar("Clinac 600", "6mv", 0.6667)
        obj = PruebaMensual600(user_id=None, equipo_f="Clinac 600")
        self._iniciar(obj, ["encabezado_mensu_600", "Control mensual",
                            "Iniciar control mensual", "Clinac 600",
                            "preguntas_mensu_600"])
        assert obj.val_teo_6mv.text() == "0.6667"

    def test_halcyon(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        _fijar("Halcyon", "6mv", 0.627)
        from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
        obj = PruebaMensualHc(user_id=None)
        self._iniciar(obj, ["encabezado_mensu_Halcyon", "Control mensual",
                            "Iniciar control mensual", "Halcyon",
                            "preguntas_mensu_Halcyon"])
        assert obj.val_teo_6mv.text() == "0.627"

    def test_ix_las_seis_energias(self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        valores = {"6mv": 0.665, "15mv": 0.761, "6mev": 0.483,
                   "9mev": 0.500, "12mev": 0.606, "15mev": 0.605}
        for e, v in valores.items():
            _fijar("Clinac ix", e, v)
        obj = PruebaMensualIX(user_id=None)
        self._iniciar(obj, ["encabezado_mensu_IX", "Control mensual",
                            "Iniciar control mensual", "Clinac ix",
                            "preguntas_mensu_ix"])
        for e, v in valores.items():
            assert float(getattr(obj, f"val_teo_{e}").text()) == pytest.approx(v), e

    def test_sin_referencia_el_formulario_arranca_vacio_como_hoy(
            self, app, bd_temporal, monkeypatch):
        _sin_avisos(monkeypatch)
        obj = PruebaMensual600(user_id=None, equipo_f="Clinac 600")
        self._iniciar(obj, ["encabezado_mensu_600", "Control mensual",
                            "Iniciar control mensual", "Clinac 600",
                            "preguntas_mensu_600"])
        assert obj.val_teo_6mv.text() == ""
