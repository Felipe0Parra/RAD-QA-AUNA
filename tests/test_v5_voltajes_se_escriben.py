"""V.5 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md): los tres voltajes de
"LECTURAS DEL MÁXIMO" se escriben; el alto y la polaridad opuesta comparten
una sola magnitud (se escribe uno, el otro se espeja). El tripwire de que
`factores_correccion`/`CalcularActividad` siempre reciben `v_alto`/`v_bajo`
vive en `test_v5_calculo_recibe_los_voltajes.py`; este archivo prueba el
COMPORTAMIENTO.

CAUSA (§V.5 del plan): las celdas de voltaje eran de solo lectura;
`Calculo_Actividad`/`guardar_DB` decidían el papel por el SIGNO/magnitud de
lo que hubiera, no por lo que el físico escribió, e ignoraban el voltaje al
calcular (300/150 fijo). Con V.1-V.4 hechas, abrir las celdas es seguro.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateTimeEdit, QLineEdit, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
import ui.paginasControles.PruebasDiarias.braquiterapia as braquiterapia_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import CalRedundanteFuente
from services.lecturas_del_maximo import VOLTAJES_POR_DEFECTO, VoltajesInvalidos
from services.combo_equipo_guardado import ROL_SERIE


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for modulo in (braq_mensual_mod, braquiterapia_mod):
        for tipo in ("information", "warning", "critical", "question"):
            monkeypatch.setattr(modulo.QMessageBox, tipo, staticmethod(lambda *a, **k: None))


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
    def __init__(self, nombre="Físico de Prueba"):
        self._nombre = nombre


# ---------------------------------------------------------------------------
# (a) Espejo con el TECLADO -- QTest.keyClicks, nunca setText (regla de
# sesión: un test de interacción se ejercita por el camino del usuario).
# ---------------------------------------------------------------------------

class TestEspejoTecladoEnElMensual:

    def test_secuencia_completa_del_plan(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso())
        alto = d.campos_lecturas[0][0]
        bajo = d.campos_lecturas[1][0]
        negativa = d.campos_lecturas[2][0]

        # Estado de fábrica: VOLTAJES_POR_DEFECTO.
        assert alto.text() == VOLTAJES_POR_DEFECTO[0]
        assert bajo.text() == VOLTAJES_POR_DEFECTO[1]
        assert negativa.text() == VOLTAJES_POR_DEFECTO[2]

        # Seleccionar todo y escribir 250 en la fila 0 -> la fila 2 pasa
        # por -2, -25, -250 (mientras se escribe, un carácter a la vez).
        alto.setFocus()
        alto.selectAll()
        QTest.keyClick(alto, '2')
        assert negativa.text() == "-2"
        QTest.keyClick(alto, '5')
        assert negativa.text() == "-25"
        QTest.keyClick(alto, '0')
        assert negativa.text() == "-250"

        # Escribir -400 en la fila 2 -> la fila 0 lee 400.
        negativa.selectAll()
        QTest.keyClicks(negativa, "-400")
        assert alto.text() == "400"

        # Escribir 300 en la fila 2 y Enter -> fila 2 -300, fila 0 300.
        negativa.selectAll()
        QTest.keyClicks(negativa, "300")
        QTest.keyClick(negativa, Qt.Key_Return)
        assert negativa.text() == "-300"
        assert alto.text() == "300"

        # Escribir 100 en la fila 1 no cambia las otras.
        bajo.selectAll()
        QTest.keyClicks(bajo, "100")
        assert bajo.text() == "100"
        assert alto.text() == "300"
        assert negativa.text() == "-300"

    def test_tambien_en_la_calibracion_redundante(self, app, bd_temporal):
        """(f): el espejo funciona igual en la redundante -- la hereda de
        PruebaMensualBraq sin cablear nada aparte (V.4)."""
        d = CalRedundanteFuente(_UsuarioFalso())
        alto = d.campos_lecturas[0][0]
        negativa = d.campos_lecturas[2][0]

        alto.setFocus()
        alto.selectAll()
        QTest.keyClicks(alto, "250")

        assert negativa.text() == "-250"


# ---------------------------------------------------------------------------
# (b) "Ok": Ks sale del cociente de los voltajes ESCRITOS.
# ---------------------------------------------------------------------------

def _reporte_de(monkeypatch, voltajes, lecturas_alto, lecturas_bajo, lecturas_neg,
                 t=21.0, p=758.0, t0=22.0, p0=760.0, calibracion=464700.0,
                 electrometro=1.0, conversion=1.0, intensidad=10.0, ref=5.0,
                 fecha_cer="2026-01-01 00:00:00", fecha_cal="2026-06-01 00:00:00"):
    """Objeto mínimo (patrón `test_t2_braqui_guarda_la_serie.py`) con
    exactamente lo que `Calculo_Actividad` necesita -- sin construir la UI
    real ni una BD, para aislar el cálculo."""
    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)

    def _fila(voltaje, medidas):
        return [QLineEdit(voltaje)] + [QLineEdit(str(m)) for m in medidas] + [QLineEdit("")]

    obj.campos_lecturas = [
        _fila(voltajes[0], lecturas_alto),
        _fila(voltajes[1], lecturas_bajo),
        _fila(voltajes[2], lecturas_neg),
    ]
    obj.campos_maximos = [[QLineEdit("100"), QLineEdit("1.0"), QLineEdit("1.1"), QLineEdit("")]]
    obj.t = QLineEdit(str(t))
    obj.p = QLineEdit(str(p))
    obj.t0 = QLineEdit(str(t0))
    obj.p0 = QLineEdit(str(p0))
    obj.calibracion = QLineEdit(str(calibracion))
    obj.electrometro = QLineEdit(str(electrometro))
    obj.conversion = QLineEdit(str(conversion))
    obj.intensidad = QLineEdit(str(intensidad))
    obj.ref = QLineEdit(str(ref))
    obj.fecha_cer = QDateTimeEdit()
    obj.fecha_cer.setDateTime(QDateTime.fromString(fecha_cer, "yyyy-MM-dd HH:mm:ss"))
    obj.fecha_cal = QDateTimeEdit()
    obj.fecha_cal.setDateTime(QDateTime.fromString(fecha_cal, "yyyy-MM-dd HH:mm:ss"))
    obj.canvas = None

    monkeypatch.setattr(braq_mensual_mod, "graficar_resultados", lambda *a, **k: None)
    capturado = {}
    monkeypatch.setattr(obj, "mostrar_resultados_actividad",
                         lambda reporte: capturado.setdefault("reporte", reporte))

    obj.Calculo_Actividad()
    return capturado.get("reporte")


LECTURAS_ALTO = (5.00e-08, 5.00e-08, 5.00e-08)
LECTURAS_BAJO = (4.90e-08, 4.90e-08, 4.90e-08)
LECTURAS_NEG = (5.00e-08, 5.00e-08, 5.00e-08)


class TestOkCalculaConLosVoltajesEscritos:
    """Los valores 0.996/0.993 que trae el texto original del plan (§V.5,
    punto b) vienen de la fórmula V.03 (cociente 2, forma
    `n2/(n2-1) - V_alto/((n2-1)*V_bajo)`, §1.6 -- ilustrativa, de ANTES de
    decidir TRS-398). La fórmula que V.1 ya dejó en producción es la de
    TRS-398 (`Ks = (n2-1)/(n2 - V_alto/V_bajo)`, DP-135/DP-137), que con
    estos mismos datos da 1.004/1.007 -- los RECÍPROCOS, misma familia de
    error que V.1 ya había encontrado y corregido en su propia prueba (f).
    Verificado con el cálculo manual (n2=(alto/bajo)**2, r=V_alto/V_bajo):
    250/100 -> (6.25-1)/(6.25-1.020408..) = 1.0039; 300/150 ->
    (4-1)/(4-1.020408..) = 1.0068. Lo que importa para V.5 -- que el Ks
    cambie según el voltaje ESCRITO, no que quede fijo en 300/150 -- se
    demuestra igual con los valores correctos."""

    def test_250_100_da_1_004(self, app, monkeypatch):
        reporte = _reporte_de(monkeypatch, ("250", "100", "-250"),
                               LECTURAS_ALTO, LECTURAS_BAJO, LECTURAS_NEG)
        assert reporte is not None
        assert "K<sub>s</sub> = 1.004" in "\n".join(reporte)

    def test_300_150_da_1_007(self, app, monkeypatch):
        """El valor de siempre (TRS-398, decidido en V.1), sin cambio,
        cuando se escribe 300/150."""
        reporte = _reporte_de(monkeypatch, ("300", "150", "-300"),
                               LECTURAS_ALTO, LECTURAS_BAJO, LECTURAS_NEG)
        assert reporte is not None
        assert "K<sub>s</sub> = 1.007" in "\n".join(reporte)


# ---------------------------------------------------------------------------
# (c)/(d) "Guardar": los voltajes escritos llegan al escritor; una entrada
# inválida no guarda nada y avisa nombrando la fila.
# ---------------------------------------------------------------------------

class _EspiaGuardado:
    def __init__(self):
        self.llamadas = []

    def __call__(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))
        return 999


def _combo_con_calibracion(eq_id, serie):
    combo = QComboBox()
    combo.addItem("Seleccionar Serie...")
    combo.addItem(f"Serie: {serie} — calibrado 01/01/2026", eq_id)
    combo.setItemData(1, serie, ROL_SERIE)
    combo.setCurrentIndex(1)
    return combo


def _pantalla_para_guardar(monkeypatch, voltajes, lecturas_alto, lecturas_bajo,
                            lecturas_neg, clase=PruebaMensualBraq, modulo=braq_mensual_mod):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)

    obj.serie = QLineEdit("SN-PRUEBA")
    obj.certificado = QLineEdit("CERT-1")
    obj.fecha_cer = QLineEdit("2026-01-01 00:00:00")
    obj.intensidad = QLineEdit("10.0")
    obj.conversion = QLineEdit("1.0")
    obj.modelo = QComboBox(); obj.modelo.addItem("TW33004")
    obj.modelo_elec = QComboBox(); obj.modelo_elec.addItem("CDX-2000B")
    obj.serie_cp = _combo_con_calibracion(17, "A092535")
    obj.serie_ele = _combo_con_calibracion(79, "002343")
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
    obj.campos_maximos = []

    def _fila(voltaje, medidas):
        return [QLineEdit(voltaje)] + [QLineEdit(str(m)) for m in medidas] + [QLineEdit("")]

    obj.campos_lecturas = [
        _fila(voltajes[0], lecturas_alto),
        _fila(voltajes[1], lecturas_bajo),
        _fila(voltajes[2], lecturas_neg),
    ]
    obj.ref = QLineEdit("5.0")
    obj.user_id = _UsuarioFalso()
    obj.es_calibracion_redundante = (clase is CalRedundanteFuente)

    monkeypatch.setattr(modulo, "graficar_resultados", lambda *a, **k: None)
    espia = _EspiaGuardado()
    monkeypatch.setattr(modulo, "guardar_resultado_CambioFuente", espia)
    return obj, espia


class TestGuardarConLosVoltajesEscritos:

    def test_guarda_250_100_250_y_ks_1_004(self, app, monkeypatch):
        """Ver la nota en `TestOkCalculaConLosVoltajesEscritos`: 1.004 es
        el TRS-398 correcto para 250/100 con estas lecturas, no el 0.996
        ilustrativo (fórmula V.03) del texto original del plan."""
        obj, espia = _pantalla_para_guardar(
            monkeypatch, ("250", "100", "-250"),
            LECTURAS_ALTO, LECTURAS_BAJO, LECTURAS_NEG)

        obj.guardar_DB()

        assert len(espia.llamadas) == 1
        args, kwargs = espia.llamadas[0]
        # Firma: ..., posiciones, medida1, medida2, promedios, [voltajes],
        # V_alto, V_bajo, V_neg, [promedios], Ks, Kp, Ktp, ...
        lista_voltajes = args[24]
        assert lista_voltajes == [250.0, 100.0, -250.0]
        Ks = args[29]
        assert round(Ks, 3) == 1.004

    def test_bajo_mayor_que_alto_avisa_y_no_guarda(self, app, monkeypatch):
        obj, espia = _pantalla_para_guardar(
            monkeypatch, ("250", "300", "-250"),
            LECTURAS_ALTO, LECTURAS_BAJO, LECTURAS_NEG)

        avisos = []
        monkeypatch.setattr(braq_mensual_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: avisos.append(a)))

        obj.guardar_DB()

        assert espia.llamadas == []
        assert avisos, "debía avisarse"
        assert "voltaje bajo" in avisos[0][2]

    def test_alto_no_numerico_avisa_y_no_guarda(self, app, monkeypatch):
        obj, espia = _pantalla_para_guardar(
            monkeypatch, ("abc", "150", "-300"),
            LECTURAS_ALTO, LECTURAS_BAJO, LECTURAS_NEG)

        avisos = []
        monkeypatch.setattr(braq_mensual_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: avisos.append(a)))

        obj.guardar_DB()

        assert espia.llamadas == []
        assert avisos, "debía avisarse"

    def test_alto_cero_avisa_y_no_guarda(self, app, monkeypatch):
        obj, espia = _pantalla_para_guardar(
            monkeypatch, ("0", "150", "-300"),
            LECTURAS_ALTO, LECTURAS_BAJO, LECTURAS_NEG)

        avisos = []
        monkeypatch.setattr(braq_mensual_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: avisos.append(a)))

        obj.guardar_DB()

        assert espia.llamadas == []
        assert avisos, "debía avisarse"

    def test_tambien_en_la_redundante_un_solo_aviso(self, app, monkeypatch):
        """(f): mismo bloqueo en la redundante, y un solo aviso (V.4 ya
        garantiza el cableado único)."""
        obj, espia = _pantalla_para_guardar(
            monkeypatch, ("250", "300", "-250"),
            LECTURAS_ALTO, LECTURAS_BAJO, LECTURAS_NEG,
            clase=CalRedundanteFuente, modulo=braq_mensual_mod)

        avisos = []
        monkeypatch.setattr(braq_mensual_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: avisos.append(a)))

        obj.guardar_DB()

        assert espia.llamadas == []
        assert len(avisos) == 1


# ---------------------------------------------------------------------------
# (e) "Limpiar" devuelve los voltajes a VOLTAJES_POR_DEFECTO.
# ---------------------------------------------------------------------------

class TestLimpiarDevuelveLosVoltajesPorDefecto:

    def test_limpiar_repone_300_150_neg300(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso())
        for fila in d.campos_lecturas:
            fila[0].setText("999")

        d.clean_info()

        assert [fila[0].text() for fila in d.campos_lecturas] == list(VOLTAJES_POR_DEFECTO)


# ---------------------------------------------------------------------------
# (g) Ciclo completo con el escritor real: escribir, guardar, recargar.
# ---------------------------------------------------------------------------

class TestCicloCompletoConLaBdReal:

    def test_guardar_y_recargar_muestra_los_voltajes_escritos(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso())

        # Fecha fija en el PASADO, nunca "hoy" (DP-94/F2 -- QDateEdit no
        # emite dateChanged si setDate recibe la misma fecha que ya
        # tenía, y `fecha_cal`/`date_box` nacen en la fecha real de hoy).
        d.fecha_cal.setDateTime(QDateTime.fromString("2020-05-15 10:00:00", "yyyy-MM-dd HH:mm:ss"))

        alto = d.campos_lecturas[0][0]
        bajo = d.campos_lecturas[1][0]
        negativa = d.campos_lecturas[2][0]
        alto.setFocus()
        alto.selectAll()
        QTest.keyClicks(alto, "250")
        bajo.selectAll()
        QTest.keyClicks(bajo, "100")

        for fila, medidas in zip(
                d.campos_lecturas, ([1e-8, 1e-8, 1e-8], [2e-8, 2e-8, 2e-8], [3e-8, 3e-8, 3e-8])):
            for celda, valor in zip(fila[1:4], medidas):
                celda.setText(str(valor))

        for fila in d.campos_maximos:
            fila[1].setText("1.0")
            fila[2].setText("1.1")

        d.serie.setText("SN-CICLO")
        d.certificado.setText("CERT-CICLO")
        d.intensidad.setText("10.0")
        d.conversion.setText("1.0")
        d.calibracion.setText("464700")
        d.electrometro.setText("1.0")
        d.t0.setText("22.0")
        d.p0.setText("760.0")
        d.h0.setText("50.0")
        d.t.setText("21.0")
        d.p.setText("758.0")
        d.h.setText("48.0")
        d.ref.setText("5.0")

        d.guardar_DB()
        ref_guardado = d.ref_bd
        assert ref_guardado is not None

        # Recarga (V.3): construir un formulario nuevo y moverse a la
        # misma fecha reconstruye las filas leyendo por PAPEL.
        d2 = PruebaMensualBraq(_UsuarioFalso())
        d2.date_box.setDate(d.fecha_cal.date())

        filas = [fila[0].text() for fila in d2.campos_lecturas]
        assert filas == ["250.0", "100.0", "-250.0"] or filas == ["250", "100", "-250"]


# ---------------------------------------------------------------------------
# (h) Lo viejo sigue igual: la huella del formulario al construir es la
# misma salvo isReadOnly/toolTip de las 3 celdas de voltaje.
# ---------------------------------------------------------------------------

class TestHuellaDeLaTablaSinCambiosAjenos:

    def test_solo_las_3_celdas_de_voltaje_cambian_de_solo_lectura(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso())

        for fila in d.campos_lecturas:
            voltaje, m1, m2, m3, promedio = fila
            # V.5: el voltaje deja de ser de solo lectura y trae tooltip.
            assert voltaje.isReadOnly() is False
            assert voltaje.toolTip() != ""
            # Lo viejo sigue igual: las medidas ya eran editables, el
            # promedio ya era de solo lectura -- ninguno de los dos lo
            # tocó esta tarea.
            assert m1.isReadOnly() is False
            assert m2.isReadOnly() is False
            assert m3.isReadOnly() is False
            assert promedio.isReadOnly() is True

    def test_los_titulos_de_columna_siguen_de_solo_lectura(self, app, bd_temporal):
        """Los encabezados ("Voltaje (V)", "Medida 1 (A)", ...) no son
        `campos_lecturas` -- viven aparte en la misma grilla y siguen
        readOnly, sin tocar."""
        d = PruebaMensualBraq(_UsuarioFalso())
        contenedor = d.tabla_lecturas_widget
        encabezados = [w for w in contenedor.findChildren(QLineEdit)
                       if w.isReadOnly() and w.text().endswith(")")]
        assert len(encabezados) == 5
        assert {e.text() for e in encabezados} == {
            "Voltaje (V)", "Medida 1 (A)", "Medida 2 (A)", "Medida 3 (A)", "Promedio (A)"}
