"""T1 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS1.3): los campos PDD 20/10
existían creados pero su bloque completo nunca se agregaba a ningún
layout visible -- entradas fantasma que se guardaban/restauraban sin que
el físico pudiera verlas ni tocarlas. Ahora alimentan el cálculo
automático de TPR20,10 (T2) y son visibles solo en fotones, EXCEPTO en el
Halcyon (FFF, decisión del físico 2026-07-23 -- la ecuación 4-2 de TRS-398
está validada solo para haces aplanados).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import data.ManejoDatos.conection as conection_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO = {"id": 1, "equip_type": "Cámara de ionización", "model": "N31010",
          "serie": "1822", "calibr_fact": 0.3045, "t_cal": 22.0,
          "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en 'IX' -> acelerador_actual='IX'."""


class VentanaHc(QWidget):
    """Padre falso cuyo nombre termina en 'Hc' -> acelerador_actual='Hc'."""


class Ventana600(QWidget):
    """Padre falso cuyo nombre termina en '600' -> acelerador_actual='Seiscientos'."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    yield ruta


@pytest.fixture
def dialogo_factory(app, bd_temporal, monkeypatch):
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": EQUIPO["model"], "equip_type": EQUIPO["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [EQUIPO] if m == EQUIPO["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: EQUIPO if i == EQUIPO["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))

    def _crear(parent_cls=VentanaIX, energias=("6mv", "15mv", "6mev")):
        return DialogCalculadoraDosis(energias=list(energias), parent=parent_cls())

    return _crear


class TestBloqueAgregadoAlLayout:

    def test_pdd20_pdd10_estan_en_un_layout_real(self, dialogo_factory):
        d = dialogo_factory()
        assert d.pdd20.parent() is not None
        assert d.pdd10.parent() is not None
        assert d.layout_pdd.parent() is not None


class TestVisibilidadPorTipoDeHazYAcelerador:

    def test_fotones_ix_visible(self, dialogo_factory):
        d = dialogo_factory(parent_cls=VentanaIX)
        d.fotones.setChecked(True)
        assert d.layout_pdd.isHidden() is False

    def test_fotones_600_visible(self, dialogo_factory):
        d = dialogo_factory(parent_cls=Ventana600)
        d.fotones.setChecked(True)
        assert d.layout_pdd.isHidden() is False

    def test_fotones_halcyon_oculto(self, dialogo_factory):
        """Decisión del físico (2026-07-23): sin TPR automático en el
        Halcyon (haz FFF, fuera del alcance validado de la ecuación 4-2)."""
        d = dialogo_factory(parent_cls=VentanaHc)
        d.fotones.setChecked(True)
        assert d.layout_pdd.isHidden() is True

    def test_electrones_oculto_en_cualquier_acelerador(self, dialogo_factory):
        d = dialogo_factory(parent_cls=VentanaIX)
        d.electrones.setChecked(True)
        assert d.layout_pdd.isHidden() is True

    def test_volver_a_fotones_desde_electrones_reaparece(self, dialogo_factory):
        d = dialogo_factory(parent_cls=VentanaIX)
        d.electrones.setChecked(True)
        assert d.layout_pdd.isHidden() is True

        d.fotones.setChecked(True)
        assert d.layout_pdd.isHidden() is False

    def test_nunca_visible_a_la_vez_que_pdd_electrones(self, dialogo_factory):
        """Regresión de I2: dos bloques PDD visibles a la vez confundió al
        físico ("PDD duplicado") -- este bloque nuevo debe respetar la misma
        exclusión mutua."""
        d = dialogo_factory(parent_cls=VentanaIX)
        d.electrones.setChecked(True)
        assert not (not d.layout_pdd.isHidden() and not d.pdd_zrefE.isHidden())

        d.fotones.setChecked(True)
        assert not (not d.layout_pdd.isHidden() and not d.pdd_zrefE.isHidden())
