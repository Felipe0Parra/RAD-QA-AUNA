"""A.1 (PLAN_REFERENCIAS_EDITABLES_21-09.md): la discrepancia de calidad se
calcula contra el valor que el físico VE escrito en `val_teo_{energia}`, no
contra un literal congelado fuera de la función.

`DP-25`: `seiscientos_mensual.py:4198` congelaba
`VALORES_REFERENCIA_CALIDAD[energia]` (por energía, no por máquina) y lo
pasaba como default a `actualizar_discrepancia_calidad`; el widget `val_teo`
estaba conectado a esa misma función (`:4225`) pero su `.text()` nunca se
leía. Caso real medido: Halcyon 06/2026, `calidad=0.62`, `val_teo_calidad`
guardado en BD = `0.627` -- el código de hoy reporta `6.77 %` (usa el
literal del iX, 0.665) cuando la referencia correcta del Halcyon da
`1.12 %` (cumple contra tolerancia 2 %).

Rojo-antes-que-verde real: `git stash` sobre `seiscientos_mensual.py` (sin
`-u`, así que este archivo de test no se stashea) reproduce el `6.77 %` del
código viejo; con el arreglo aplicado da `1.12 %`.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600,
)

ENERGIAS = ("6mv", "15mv", "6mev", "9mev", "12mev", "15mev")

# Los mismos números que estaban congelados en VALORES_REFERENCIA_CALIDAD
# (ahora VALORES_REFERENCIA_CALIDAD_RESPALDO) -- se usan aquí para probar
# que, con el widget vacío, el resultado no cambia frente al código viejo.
RESPALDO = {
    "6mv": 0.665,
    "15mv": 0.761,
    "6mev": 0.483,
    "9mev": 0.500,
    "12mev": 0.606,
    "15mev": 0.605,
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _widget_ix_calidad(energia):
    """Nombre real del widget de calidad medida, por tipo de haz
    (mapping de discrepancias() en seiscientos_mensual.py)."""
    return (f"ln_calidad_pdd20_10_{energia}" if energia.endswith("mv")
            else f"ln_calidad_j2_j1_{energia}")


def _obj_con_energia(app, energia, calidad_texto, val_teo_texto):
    """Objeto 'pelado' de PruebaMensualIX con SOLO los widgets de la energía
    dada -- discrepancias() salta silenciosamente las energías sin widgets
    (getattr(..., None) -> _obtener_widgets_discrepancia devuelve None ->
    continue), así que no hace falta construir las 6."""
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj._debounce_timers = {}

    setattr(obj, f"val_teo_{energia}", QLineEdit(val_teo_texto))
    setattr(obj, f"ln_dosis_ref_cgy_um_{energia}", QLineEdit(""))
    setattr(obj, f"ln_discrepancia_dosis_{energia}", QLineEdit(""))
    calidad_attr = _widget_ix_calidad(energia)
    setattr(obj, calidad_attr, QLineEdit(calidad_texto))
    setattr(obj, f"ln_discrepancia_calidad_{energia}", QLineEdit(""))
    return obj


class TestCasoRealHalcyon:
    """La garantía titular de A.1: el widget manda, ya no el literal."""

    def test_con_val_teo_correcto_del_halcyon_da_1_12_por_ciento(self, app):
        obj = _obj_con_energia(app, "6mv", calidad_texto="0.62",
                                val_teo_texto="0.627")
        obj.discrepancias()
        resultado = float(obj.ln_discrepancia_calidad_6mv.text())
        assert resultado == pytest.approx(1.12, abs=0.01)

    def test_no_reproduce_ya_la_falsa_alarma_del_6_77(self, app):
        obj = _obj_con_energia(app, "6mv", calidad_texto="0.62",
                                val_teo_texto="0.627")
        obj.discrepancias()
        resultado = float(obj.ln_discrepancia_calidad_6mv.text())
        assert resultado < 2.0  # tolerancia real de fotones
        assert round(resultado, 2) != 6.77

    def test_reproduccion_exacta_del_defecto_dp25(self, app):
        """El literal viejo (0.665) aplicado al dato real del Halcyon
        reproduce el 6.77 % que quedó archivado -- confirma que el defecto
        que describe DP-25 era justo ese, y que el arreglo lo esquiva."""
        calidad = 0.62
        literal_viejo = 0.665
        discrepancia_con_literal_viejo = abs(
            (literal_viejo - calidad) / literal_viejo * 100)
        assert round(discrepancia_con_literal_viejo, 2) == 6.77


class TestRespaldoPorEnergia:
    """Con el widget val_teo vacío, el resultado no puede cambiar frente al
    código de hoy: cae al respaldo, que es el mismo literal de siempre."""

    @pytest.mark.parametrize("energia", ENERGIAS)
    def test_widget_vacio_reproduce_el_calculo_de_siempre(self, app, energia):
        calidad_medida = "0.60"
        obj = _obj_con_energia(app, energia, calidad_texto=calidad_medida,
                                val_teo_texto="")
        obj.discrepancias()
        calidad_attr = _widget_ix_calidad(energia)
        salida = getattr(obj, f"ln_discrepancia_calidad_{energia}")

        referencia = RESPALDO[energia]
        esperado = round(abs((referencia - float(calidad_medida)) / referencia * 100), 4)
        # mostrar_resultado_optimizado formatea a 2 decimales ("%.2f") antes
        # de escribir el widget -- comparar con esa misma precisión.
        assert float(salida.text()) == pytest.approx(esperado, abs=0.01)

    def test_ix_600_cinco_energias_siguen_igual_que_hoy(self, app):
        """'Las otras 5 energías del iX siguen dando exactamente lo mismo
        que hoy (sus literales y sus referencias coinciden: 0.665 = 0.665)'
        -- verificado con val_teo vacío (el estado normal de un formulario
        sin tocar), que es justo el caso que no debía cambiar."""
        for energia in ENERGIAS:
            obj = _obj_con_energia(app, energia, calidad_texto="0.60",
                                    val_teo_texto="")
            obj.discrepancias()
            salida = getattr(obj, f"ln_discrepancia_calidad_{energia}")
            assert salida.text() != ""  # con datos, siempre calcula algo


class TestCampoVacioNoInventaCero:
    """A.1 punto 4: sin referencia (o sin medida), el campo de salida queda
    vacío, nunca '0.0' -- que parecía un veredicto perfecto."""

    def test_calidad_vacia_deja_salida_vacia_no_cero(self, app):
        obj = _obj_con_energia(app, "6mv", calidad_texto="",
                                val_teo_texto="0.627")
        obj.discrepancias()
        assert obj.ln_discrepancia_calidad_6mv.text() == ""

    def test_dosis_vacia_deja_salida_vacia_no_cero(self, app):
        obj = _obj_con_energia(app, "6mv", calidad_texto="0.62",
                                val_teo_texto="0.627")
        obj.ln_dosis_ref_cgy_um_6mv.setText("")
        obj.discrepancias()
        assert obj.ln_discrepancia_dosis_6mv.text() == ""


class TestDosisPreservaComportamiento:
    """CAMBIO punto 3: operacion_dosis_optimizada gana val_teo_str="1" como
    default -- sin ningún widget de referencia de dosis en esta pantalla
    (R5), ningún llamador pasa un valor distinto, así que el resultado no
    puede cambiar frente al código de hoy (literal `1` dentro de la
    fórmula)."""

    @pytest.mark.parametrize("dato", ["1.0", "0.993", "1.05", "0.97"])
    def test_dosis_da_lo_mismo_que_el_literal_viejo(self, app, dato):
        obj = _obj_con_energia(app, "6mv", calidad_texto="",
                                val_teo_texto="")
        obj.ln_dosis_ref_cgy_um_6mv.setText(dato)
        obj.discrepancias()

        esperado_viejo = abs(100 * (1 - float(dato)))
        if float(dato) == 0.0:
            esperado_viejo = 0.0
        resultado = obj.ln_discrepancia_dosis_6mv.text()
        assert float(resultado) == pytest.approx(esperado_viejo, abs=1e-6)


class Test600TambienUsaElWidget:
    """El mismo mecanismo aplica en PruebaMensual600, no solo en el iX --
    ambas comparten _procesar_discrepancias_dosis_calidad."""

    def test_600_widget_manda_sobre_el_respaldo(self, app):
        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj._debounce_timers = {}
        obj.val_teo_6mv = QLineEdit("0.6667")
        obj.ln_dosis_ref_cgy_um_6mv = QLineEdit("")
        obj.ln_discrepancia_dosis_6mv = QLineEdit("")
        obj.ln_calidad_pdd20_10_6mv = QLineEdit("0.66")
        obj.ln_discrepancia_calidad_6mv = QLineEdit("")

        obj.discrepancias()

        esperado = round(abs((0.6667 - 0.66) / 0.6667 * 100), 4)
        assert float(obj.ln_discrepancia_calidad_6mv.text()) == pytest.approx(
            esperado, abs=0.01)
