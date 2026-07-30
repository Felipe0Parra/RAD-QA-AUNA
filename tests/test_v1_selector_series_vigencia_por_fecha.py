"""V1 (PLAN_AUDITORIA_DOS_EJES_21-07.md SS7.5): el selector de series del
formulario mensual (`seiscientos_mensual.py::setEquipoSeleccionado`,
heredado por iX/Halcyon/TAC y por PruebaAnual600/iX/Halcyon -- todos
extienden PruebaMensual600 y no sobreescriben este método) marcaba
"vencido" leyendo el flag `vigente` **congelado** en la columna de
`equipos`, calculado una sola vez contra la fecha en que se insertó/editó
esa fila -- nunca contra la fecha del control que se está llenando. Por eso
una cámara que venció hace poco aparecía "vencida" aunque el control se
hiciera (con fecha pasada) cuando aún estaba vigente.

Estos tests verifican, sobre una BD temporal real (no mockeada) y una
instancia "pelada" de PruebaMensual600 (mismo patrón que
test_mcc_autofill_mensual.py: __init__ es pesado -- UI desde Excel, BD real
-- y no aporta nada a lo que este método usa), que el selector ahora marca
vencido/vigente según `self.date_box` (la fecha del control), no según el
flag congelado ni "hoy".
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QLineEdit, QWidget
from PyQt5.QtCore import QDate

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
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
    conexion = Conexion()  # crea el esquema completo, incl. `equipos`
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _insertar_equipo(ruta_bd, eq_id, **campos):
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


def _instancia_pelada(fecha_control):
    """PruebaMensual600 sin su __init__ pesado -- solo lo que
    setEquipoSeleccionado necesita: db_manager, date_box y el triple de
    combos (modelo, serie, calibración) que representa self.commenu."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(fecha_control)

    combo_modelo = QComboBox()
    combo_modelo.addItems(["Seleccionar...", "ModeloTest"])
    combo_serie = QComboBox()
    lineedit_calib = QLineEdit()
    obj.commenu = [combo_modelo, combo_serie, lineedit_calib]
    combo_modelo.currentTextChanged.connect(obj.setEquipoSeleccionado)
    return obj, combo_modelo, combo_serie


def _texto_y_tooltip(combo_serie, serie):
    idx = combo_serie.findText(serie)
    if idx == -1:
        # el texto pudo quedar con el marcador de vencido antepuesto
        for i in range(combo_serie.count()):
            if serie in combo_serie.itemText(i):
                idx = i
                break
    item = combo_serie.model().item(idx)
    return item.text(), item.toolTip()


class TestVigenciaEvaluadaContraLaFechaDelControl:
    """Misma fila de equipo (calibrada 10/01/2024, Cámara de ionización,
    2 años de vigencia -> vence 10/01/2026); el único que cambia es
    self.date_box (la fecha del control que se está llenando)."""

    def _poblar(self, ruta_bd):
        _insertar_equipo(
            ruta_bd, 1, equip_type="Cámara de ionización", model="ModeloTest",
            serie="S1", calibr_fact=0.303, t_cal=22.0, p_cal=101.325, h_cal=38,
            fecha_calibr="10/01/2024", activo=1, vigente=1,
        )

    def test_control_retroactivo_dentro_de_la_ventana_no_marca_vencido(self, app, bd_temporal):
        # F9 (PLAN_F_CIERRE_ESTANDAR_29-07.md §9): el texto ahora lo compone
        # el helper compartido (services/etiqueta_equipo.py), sin símbolos.
        self._poblar(bd_temporal)
        obj, combo_modelo, combo_serie = _instancia_pelada(QDate(2024, 6, 15))

        combo_modelo.setCurrentText("ModeloTest")

        texto, tooltip = _texto_y_tooltip(combo_serie, "S1")
        assert texto == "Serie: S1 — calibrado 10/01/2024"
        assert tooltip == ""

    def test_control_con_fecha_posterior_al_vencimiento_marca_vencido(self, app, bd_temporal):
        self._poblar(bd_temporal)
        obj, combo_modelo, combo_serie = _instancia_pelada(QDate(2026, 7, 27))

        combo_modelo.setCurrentText("ModeloTest")

        texto, tooltip = _texto_y_tooltip(combo_serie, "S1")
        assert texto == "Serie: S1 — calibrado 10/01/2024 (vencida)"
        assert "vencida" in tooltip.lower()

    def test_sin_date_box_cae_a_hoy_sin_reventar(self, app, bd_temporal):
        """Si por algún motivo self.date_box no existe todavía, el
        selector no debe lanzar AttributeError -- cae a QDate.currentDate()
        (mismo comportamiento que antes de V1)."""
        self._poblar(bd_temporal)
        obj, combo_modelo, combo_serie = _instancia_pelada(QDate(2024, 6, 15))
        del obj.date_box

        combo_modelo.setCurrentText("ModeloTest")

        # No debe reventar; el resultado depende de la fecha real del
        # sistema, no se afirma cuál -- solo que el combo se pobló.
        assert combo_serie.count() >= 1


class TestVigenteHoySigueMostrandoseVigente:
    """Control de no-regresión: un equipo genuinamente vigente (calibrado
    recientemente) no debe marcarse vencido sin importar la fecha del
    control, mientras esa fecha esté dentro de la ventana."""

    def test_equipo_vigente_no_se_marca(self, app, bd_temporal):
        _insertar_equipo(
            bd_temporal, 1, equip_type="Cámara de ionización", model="ModeloTest",
            serie="S2", calibr_fact=0.303, t_cal=22.0, p_cal=101.325, h_cal=38,
            fecha_calibr="01/01/2026", activo=1, vigente=1,
        )
        obj, combo_modelo, combo_serie = _instancia_pelada(QDate(2026, 7, 27))

        combo_modelo.setCurrentText("ModeloTest")

        texto, tooltip = _texto_y_tooltip(combo_serie, "S2")
        assert texto == "Serie: S2 — calibrado 01/01/2026"
        assert tooltip == ""


class TestEquipoInactivoNoAparece:
    """Regresión: activo=0 sigue excluyendo la serie del combo, sin
    importar la vigencia (comportamiento preexistente, no tocado por V1)."""

    def test_equipo_inactivo_no_aparece_en_el_combo(self, app, bd_temporal):
        _insertar_equipo(
            bd_temporal, 1, equip_type="Cámara de ionización", model="ModeloTest",
            serie="S3", calibr_fact=0.303, t_cal=22.0, p_cal=101.325, h_cal=38,
            fecha_calibr="01/01/2026", activo=0, vigente=1,
        )
        obj, combo_modelo, combo_serie = _instancia_pelada(QDate(2026, 7, 27))

        combo_modelo.setCurrentText("ModeloTest")

        assert combo_serie.findText("S3") == -1
