"""R2/R3 (PLAN_REPARACION_ANUAL_27-08.md §Fase 3, F-5): captura de las
lecturas crudas de la hoja "Linealidad" en el formulario, y derivación
del factor a partir de esas lecturas (sin quitarle el mando al físico --
la casilla sigue editable).

R2: cuatro paneles nuevos (linealidad de UM, lecturas de factor de
campo/cono, lecturas de transmisión de cuñas, tasa de dosis), recorriendo
el mismo diccionario por energía que E1 (`DEFINICIONES_ENERGIA`) para que
electrones pidan conos/PDD propios también aquí.

R3: `_derivar_factor_linealidad_um` (promedio puro),
`_derivar_factor_lecturas_campo` (OF = Q(campo)/Q(10x10)),
`_derivar_factor_transmision` (T = Q(cuña)/Q(open)) -- las tres viven en
`PruebaAnual600` (genéricas por tabla) y las reusa `PruebaAnualIX` por
herencia, sin redefinirlas.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QToolBox, QWidget

from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _ix_pelado():
    obj = PruebaAnualIX.__new__(PruebaAnualIX)
    QWidget.__init__(obj)
    obj.ref = "ref-test-r2"
    obj.anual = True
    obj.subtool = QToolBox()
    obj.subtool2 = QToolBox()
    obj.subtool3 = QToolBox()
    obj.subtool4 = QToolBox()
    obj.subtool5 = QToolBox()
    return obj


def _seis_pelado():
    obj = PruebaAnual600.__new__(PruebaAnual600)
    QWidget.__init__(obj)
    obj.ref = "ref-test-r2"
    obj.anual = True
    obj.subtool = QToolBox()
    return obj


class TestR2PanelesIXPorEnergia:
    def test_linealidad_um_diez_niveles_por_energia(self, app):
        obj = _ix_pelado()
        tablas_um, _, _, _ = obj._crear_tablas_linealidad()
        assert len(tablas_um) == 6
        for entry in tablas_um:
            assert entry["tabla"].rowCount() == 10
        niveles = [tablas_um[0]["tabla"].item(f, 0).text() for f in range(10)]
        assert niveles == ["50", "100", "150", "200", "250", "300", "350", "400", "500", "600"]

    def test_lecturas_factor_campo_usa_los_mismos_tamanos_que_e1(self, app):
        obj = _ix_pelado()
        _, tablas_lfc, _, _ = obj._crear_tablas_linealidad()
        entrada_6mv = next(e for e in tablas_lfc if e["id_energia"] == 0)
        assert entrada_6mv["tabla"].rowCount() == 8
        entrada_6mev = next(e for e in tablas_lfc if e["id_energia"] == 2)
        assert entrada_6mev["tabla"].rowCount() == 5
        assert [entrada_6mev["tabla"].item(f, 0).text() for f in range(5)] == [
            "6x6", "10x10", "15x15", "20x20", "25x25"]

    def test_lecturas_transmision_seis_accesorios_incluye_open(self, app):
        obj = _ix_pelado()
        _, _, tablas_lt, _ = obj._crear_tablas_linealidad()
        assert len(tablas_lt) == 6
        accesorios = [tablas_lt[0]["tabla"].item(f, 0).text() for f in range(6)]
        assert accesorios == ["Open", "15°", "30°", "45°", "60°", "MLC"]

    def test_tasa_dosis_solo_para_fotones(self, app):
        obj = _ix_pelado()
        _, _, _, tablas_td = obj._crear_tablas_linealidad()
        ids_con_tasa = {e["id_energia"] for e in tablas_td}
        assert ids_con_tasa == {0, 1}  # 6 MV, 15 MV
        assert tablas_td[0]["tabla"].rowCount() == 4


class TestR2PanelSeiscientosUnaEnergia:
    def test_las_cuatro_tablas_se_crean(self, app):
        obj = _seis_pelado()
        tabla_um, tabla_lfc, tabla_lt, tabla_td = obj._crear_tablas_linealidad()
        assert tabla_um.rowCount() == 10
        assert tabla_lfc.rowCount() == 8
        assert tabla_lt.rowCount() == 6
        assert tabla_td.rowCount() == 4


class TestR3DerivaLinealidadUM:
    def _tabla(self, filas):
        tabla = QTableWidget(len(filas), 4)
        for f, (um, q1, q2) in enumerate(filas):
            tabla.setItem(f, 0, QTableWidgetItem(um))
            if q1 is not None:
                tabla.setItem(f, 1, QTableWidgetItem(str(q1)))
            if q2 is not None:
                tabla.setItem(f, 2, QTableWidgetItem(str(q2)))
        return tabla

    def test_promedia_q1_q2(self, app):
        obj = _seis_pelado()
        tabla = self._tabla([("50", 0.93, 0.93)])
        calcular = obj._derivar_factor_linealidad_um(tabla)
        calcular()
        assert tabla.item(0, 3).text() == "0.9300"

    def test_fila_sin_ambas_lecturas_queda_vacia(self, app):
        obj = _seis_pelado()
        tabla = self._tabla([("50", 0.93, None)])
        calcular = obj._derivar_factor_linealidad_um(tabla)
        calcular()
        item = tabla.item(0, 3)
        assert item is None or item.text() == ""


class TestR3DerivaFactorLecturasCampo:
    def _tabla(self, filas):
        tabla = QTableWidget(len(filas), 5)
        for f, (tam, q1, q2) in enumerate(filas):
            tabla.setItem(f, 0, QTableWidgetItem(tam))
            tabla.setItem(f, 1, QTableWidgetItem(str(q1)))
            tabla.setItem(f, 2, QTableWidgetItem(str(q2)))
        return tabla

    def test_of_referencia_10x10_da_factor_uno(self, app):
        obj = _seis_pelado()
        tabla = self._tabla([
            ("3x3", 1.538, 1.538),
            ("10x10", 1.862, 1.859),
        ])
        calcular = obj._derivar_factor_lecturas_campo(tabla)
        calcular()
        assert tabla.item(1, 4).text() == "1.0000"

    def test_of_de_3x3_coincide_con_el_valor_medido_real(self, app):
        # Excel real (IDC-F-RT-120 V2, hoja Nuevo, 6 MV): factor de 3x3 =
        # 0.8266595001 (columna F21), calculado sobre Q(3x3)=1.538 y
        # Q(10x10)=Q1,Q2 promedio de C22/D22 = (1.862+1.859)/2 = 1.8605.
        obj = _seis_pelado()
        tabla = self._tabla([
            ("3x3", 1.538, 1.538),
            ("10x10", 1.862, 1.859),
        ])
        calcular = obj._derivar_factor_lecturas_campo(tabla)
        calcular()
        assert tabla.item(0, 4).text() == "0.8267"

    def test_funciona_igual_para_conos_de_electrones(self, app):
        # 6 MeV real: cono 10x10 -> Qm=10.59 (factor 1), cono 6x6 ->
        # Qm=10.35 -> factor 0.977 (medido).
        obj = _seis_pelado()
        tabla = self._tabla([
            ("6x6", 10.35, 10.35),
            ("10x10", 10.59, 10.59),
        ])
        calcular = obj._derivar_factor_lecturas_campo(tabla)
        calcular()
        assert tabla.item(1, 4).text() == "1.0000"
        assert tabla.item(0, 4).text() == "0.9773"

    def test_sin_fila_10x10_no_revienta_y_no_rellena_factor(self, app):
        obj = _seis_pelado()
        tabla = self._tabla([("3x3", 1.538, 1.538)])
        calcular = obj._derivar_factor_lecturas_campo(tabla)
        calcular()  # no debe lanzar
        item = tabla.item(0, 4)
        assert item is None or item.text() == ""


class TestR3DerivaFactorTransmision:
    def _tabla(self, filas):
        # filas: (accesorio, q1_in, q2_in, q1_out, q2_out)
        tabla = QTableWidget(len(filas), 7)
        for f, fila in enumerate(filas):
            for c, valor in enumerate(fila):
                if valor is not None:
                    tabla.setItem(f, c, QTableWidgetItem(str(valor)))
        return tabla

    def test_t_referencia_open_da_uno(self, app):
        obj = _seis_pelado()
        tabla = self._tabla([
            ("Open", 1.862, 1.859, None, None),
            ("15°", 1.428, 1.429, 1.429, 1.429),
        ])
        calcular = obj._derivar_factor_transmision(tabla)
        calcular()
        assert tabla.item(0, 6).text() == "1.0000"

    def test_t_de_15_grados_coincide_con_el_valor_medido_real(self, app):
        # Excel real, energía 6 MV, hoja "Linealidad" (AF6:AL7): T(15°) =
        # 0.7679387261 (AL7), sobre Q_med(Open)=1.8605 (promedio de
        # 1.862/1.859, AK6) y Q_med(15°)=1.42875 (promedio de las 4
        # lecturas 1.428/1.429/1.429/1.429, AK7).
        obj = _seis_pelado()
        tabla = self._tabla([
            ("Open", 1.862, 1.859, None, None),
            ("15°", 1.428, 1.429, 1.429, 1.429),
        ])
        calcular = obj._derivar_factor_transmision(tabla)
        calcular()
        assert tabla.item(1, 6).text() == "0.7679"

    def test_sin_fila_open_no_revienta(self, app):
        obj = _seis_pelado()
        tabla = self._tabla([("15°", 1.428, 1.429, 1.429, 1.429)])
        calcular = obj._derivar_factor_transmision(tabla)
        calcular()
        item = tabla.item(0, 6)
        assert item is None or item.text() == ""


class TestR2BotonGuardadoResuelveIdEnergiaParaLasCuatroListas:
    """Estructural: sin esta extensión, _agregar_botones_tabla de iX deja
    id_energia en None para las 4 tablas nuevas y el guardado deja de
    acotar el reemplazo de bloque a la energía correcta."""

    def test_ix_agregar_botones_tabla_busca_en_las_cuatro_listas_nuevas(self):
        import inspect
        fuente = inspect.getsource(PruebaAnualIX._agregar_botones_tabla)
        for nombre in ("tablas_linealidad_um", "tablas_lecturas_fc",
                       "tablas_lecturas_transmision", "tablas_tasa_dosis"):
            assert nombre in fuente, f"falta buscar id_energia en {nombre}"
