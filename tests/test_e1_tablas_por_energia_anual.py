"""E1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 2): tablas del anual por
energía -- fotones y electrones dejan de compartir definición.

`F-3`/`AN-6`: `ix_anual.py` usaba UNA sola definición (tamaños de fotones,
PDDs de fotones, profundidades en cm) para las 6 energías -- los 4 ensayos
de electrones (6/9/12/15 MeV) no tenían dónde poner los factores de CONO
(6x6..25x25) ni las profundidades reales (en mm, distintas por energía).

`F-4`/el "descuadre de filas": `datos_fc` ya traía los 8 tamaños de
fotones (`3x3..40x40`) en ambos archivos, pero `createSimpleTable1` se
llamaba con `rows=6` a mano -- "35x35" y "40x40" quedaban creados en la
lista de datos pero NUNCA en la tabla (`table.setRowCount(6)` los corta).

Valores de referencia (medidos directamente del formato oficial 2025,
`IDC-F-RT-120 ... V2.xlsx`, hoja "Nuevo"): fotones 8 tamaños `3x3..40x40`,
PDD `10x10/15x15/20x20`, profundidad `5/10/20 cm`; electrones 5 conos
`6x6..25x25`, PDD `6x6/10x10/20x20`, profundidad 2 valores en mm por
energía (6 MeV: 12/23.3 · 9 MeV: 19/35.5 · 12 MeV: 25/49.4 · 15 MeV:
18/61.9); cámaras monitoras: "Tasa mínima 100 cGy/min", "Tasa máxima 400
cGy/min", "Tasa máxima 600 cGy/min" (igual para fotones y electrones).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QToolBox, QWidget

from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _ix_pelado():
    obj = PruebaAnualIX.__new__(PruebaAnualIX)
    QWidget.__init__(obj)
    obj.ref = "ref-test-e1"
    obj.anual = True
    # No se fija self.db_manager -- pruebatalas() falla con AttributeError
    # y cae al camino de datos por defecto, sin tocar ninguna BD real.
    obj.subtool = QToolBox()
    obj.subtool2 = QToolBox()
    obj.subtool3 = QToolBox()
    obj.subtool4 = QToolBox()
    return obj


def _seis_pelado():
    obj = PruebaAnual600.__new__(PruebaAnual600)
    QWidget.__init__(obj)
    obj.ref = "ref-test-e1"
    obj.anual = True
    obj.subtool = QToolBox()
    return obj


class TestDefinicionesPorEnergiaCorrectas:
    """La fuente única de verdad: el diccionario energía -> definición,
    contra los valores medidos del formato oficial."""

    def test_existen_las_seis_energias(self, app):
        defs = PruebaAnualIX.DEFINICIONES_ENERGIA
        assert set(defs.keys()) == {"6 MV", "15 MV", "6 MeV", "9 MeV", "12 MeV", "15 MeV"}

    @pytest.mark.parametrize("energia", ["6 MV", "15 MV"])
    def test_fotones_ocho_tamanos_de_campo(self, app, energia):
        defin = PruebaAnualIX.DEFINICIONES_ENERGIA[energia]
        assert defin["tamanos_campo"] == [
            "3x3", "10x10", "15x15", "20x20", "25x25", "30x30", "35x35", "40x40"]
        assert defin["profundidades"] == ["5", "10", "20"]
        assert defin["unidad_profundidad"] == "cm"

    @pytest.mark.parametrize("energia, profundidades", [
        ("6 MeV", ["12", "23.3"]),
        ("9 MeV", ["19", "35.5"]),
        ("12 MeV", ["25", "49.4"]),
        ("15 MeV", ["18", "61.9"]),
    ])
    def test_electrones_cinco_conos_y_profundidad_propia(self, app, energia, profundidades):
        defin = PruebaAnualIX.DEFINICIONES_ENERGIA[energia]
        assert defin["tamanos_campo"] == ["6x6", "10x10", "15x15", "20x20", "25x25"]
        assert defin["profundidades"] == profundidades
        assert defin["unidad_profundidad"] == "mm"


class TestIXFactorDeCampoPorEnergia:
    def test_fotones_tienen_ocho_filas_alcanzables(self, app):
        obj = _ix_pelado()
        tablas_fc, _, _, _ = obj._crear_tablas_pruebas()
        entrada_6mv = next(e for e in tablas_fc if e["id_energia"] == 0)
        tabla = entrada_6mv["tabla"]
        assert tabla.rowCount() == 8
        assert tabla.item(6, 0).text() == "35x35"
        assert tabla.item(7, 0).text() == "40x40"

    def test_electrones_tienen_cinco_conos_no_ocho_tamanos_de_fotones(self, app):
        obj = _ix_pelado()
        tablas_fc, _, _, _ = obj._crear_tablas_pruebas()
        entrada_6mev = next(e for e in tablas_fc if e["id_energia"] == 2)
        tabla = entrada_6mev["tabla"]
        assert tabla.rowCount() == 5
        assert [tabla.item(f, 0).text() for f in range(5)] == [
            "6x6", "10x10", "15x15", "20x20", "25x25"]


class TestIXFactoresSobreElEjePorEnergia:
    def test_fotones_pdd_y_profundidad_en_cm(self, app):
        obj = _ix_pelado()
        _, _, tablas_fse, _ = obj._crear_tablas_pruebas()
        tablas_6mv = tablas_fse[0]  # energias[0] == "6 MV"
        assert len(tablas_6mv) == 3
        pdds = {entry["pdd"] for entry in tablas_6mv}
        assert pdds == {"PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"}
        for entry in tablas_6mv:
            tabla = entry["tabla"]
            assert tabla.rowCount() == 3
            assert [tabla.item(f, 0).text() for f in range(3)] == ["5", "10", "20"]
            assert tabla.horizontalHeaderItem(0).text() == "Profundidad (cm)"

    def test_electrones_pdd_de_cono_y_profundidad_en_mm(self, app):
        obj = _ix_pelado()
        _, _, tablas_fse, _ = obj._crear_tablas_pruebas()
        tablas_6mev = tablas_fse[2]  # energias[2] == "6 MeV"
        assert len(tablas_6mev) == 3
        pdds = {entry["pdd"] for entry in tablas_6mev}
        assert pdds == {"PDD (6 x 6)", "PDD (10 x 10)", "PDD (20 x 20)"}
        for entry in tablas_6mev:
            tabla = entry["tabla"]
            assert tabla.rowCount() == 2
            assert [tabla.item(f, 0).text() for f in range(2)] == ["12", "23.3"]
            assert tabla.horizontalHeaderItem(0).text() == "Profundidad (mm)"

    @pytest.mark.parametrize("indice_energia, profundidades", [
        (3, ["19", "35.5"]),
        (4, ["25", "49.4"]),
        (5, ["18", "61.9"]),
    ])
    def test_cada_energia_de_electrones_tiene_su_propia_profundidad(self, app, indice_energia, profundidades):
        obj = _ix_pelado()
        _, _, tablas_fse, _ = obj._crear_tablas_pruebas()
        tablas_energia = tablas_fse[indice_energia]
        for entry in tablas_energia:
            tabla = entry["tabla"]
            assert [tabla.item(f, 0).text() for f in range(len(profundidades))] == profundidades


class TestCamarasMonitorasTasaCorrecta:
    @pytest.mark.parametrize("indice_energia", [0, 1, 2, 3, 4, 5])
    def test_ix_tasas_100_400_600_para_toda_energia(self, app, indice_energia):
        obj = _ix_pelado()
        _, _, _, tablas_ccm = obj._crear_tablas_pruebas()
        tabla = tablas_ccm[indice_energia]["tabla"]
        etiquetas = [tabla.item(f, 0).text() for f in range(tabla.rowCount())]
        assert "Tasa mínima 100 cGy/min" in etiquetas
        assert "Tasa máxima 400 cGy/min" in etiquetas
        assert "Tasa máxima 600 cGy/min" in etiquetas
        assert not any("80 cGy/min" in e or "160 cGy/min" in e for e in etiquetas)

    def test_seiscientos_tasas_100_400_600(self, app):
        obj = _seis_pelado()
        _, _, _, tabla_ccm = obj._crear_tablas_pruebas()
        etiquetas = [tabla_ccm.item(f, 0).text() for f in range(tabla_ccm.rowCount())]
        assert "Tasa mínima 100 cGy/min" in etiquetas
        assert "Tasa máxima 400 cGy/min" in etiquetas
        assert "Tasa máxima 600 cGy/min" in etiquetas
        assert not any("80 cGy/min" in e or "160 cGy/min" in e for e in etiquetas)


class TestPDFFactoresSobreElEjeIncluyeElectrones:
    """Extensión natural de E1: los datos de electrones ya se guardan
    (tabla nueva de PDD/profundidad por energía) -- el generador de PDF no
    puede seguir filtrando solo por los 3 PDD de fotones, o el dato
    quedaría guardado pero invisible en el informe firmado."""

    def _fila(self, id_energia, tam_pdd, profundidad):
        return {
            'id_energia': id_energia, 'tam_pdd': tam_pdd, 'profundidad': profundidad,
            'ppd': '98.0', 'ppd_esperado': '98.0', 'discrepancia': '0.00',
        }

    def test_electrones_generan_tabla_con_su_propio_pdd(self, app):
        from models.PDF.Anual.reportes_anuales import _crear_tablas_factores_sobre_eje_ix
        datos = [self._fila(2, "PDD (6 x 6)", "12")]
        tablas = _crear_tablas_factores_sobre_eje_ix(datos)
        assert len(tablas) == 1
        assert "6 MeV" in tablas[0]['titulo']
        assert "PDD (6 x 6)" in tablas[0]['titulo']
        assert tablas[0]['dataframe'].columns[0] == "Profundidad (mm)"

    def test_fotones_siguen_igual_que_antes(self, app):
        from models.PDF.Anual.reportes_anuales import _crear_tablas_factores_sobre_eje_ix
        datos = [self._fila(0, "PDD (10 x 10)", "5")]
        tablas = _crear_tablas_factores_sobre_eje_ix(datos)
        assert len(tablas) == 1
        assert "6 MV" in tablas[0]['titulo']
        assert tablas[0]['dataframe'].columns[0] == "Profundidad (cm)"


class TestSeiscientosFactorDeCampoOchoFilas:
    """`seiscientos_anual.py` es de una sola energía (fotones) -- mismo
    descuadre 6<->8 que ix_anual.py, misma reparación: filas = len(datos)."""

    def test_ocho_filas_alcanzables(self, app):
        obj = _seis_pelado()
        tabla_fc, _, _, _ = obj._crear_tablas_pruebas()
        assert tabla_fc.rowCount() == 8
        assert tabla_fc.item(6, 0).text() == "35x35"
        assert tabla_fc.item(7, 0).text() == "40x40"
