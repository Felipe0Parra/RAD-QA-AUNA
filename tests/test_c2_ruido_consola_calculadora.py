"""C2: la cascada de la calculadora no debe ensuciar la terminal cuando los
campos están vacíos (ValueError/TypeError esperados de float('')).

Reproduce lo que el físico veía en la terminal del rebuild ("could not
convert string to float: ''") al abrir la calculadora: los 8 slots de la
cascada (lect_m1, QualityR50, Zref, a2, MQvar, Mminus, lect_m2, dosis_maxima)
se disparan con texto vacío durante la construcción del diálogo real. No es
un fallo -- el campo simplemente queda vacío -- pero el print(e) desnudo
podía enmascarar un error real en la misma cascada. Este test fija que:
1. abrir el diálogo real offscreen con campos vacíos no imprime nada, y
2. una excepción DISTINTA de ValueError/TypeError en la misma cascada sí se
   reporta (el comportamiento de defecto real no se perdió).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_N31010 = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                 "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (el diálogo deduce el acelerador)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogo(app, monkeypatch):
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": EQUIPO_N31010["model"],
                                "equip_type": EQUIPO_N31010["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [EQUIPO_N31010]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: EQUIPO_N31010 if i == EQUIPO_N31010["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))

    d = DialogCalculadoraDosis(energias=[], parent=VentanaIX())
    yield d
    d.deleteLater()


class TestSinRuidoConCamposVacios:
    def test_construir_dialogo_no_imprime_nada(self, app, monkeypatch, capsys):
        """La cascada completa (lect_m1/QualityR50/Zref/a2/MQvar/Mminus/
        lect_m2/dosis_maxima) se dispara al construir con campos vacíos --
        antes de C2 esto imprimía 'could not convert string to float' 8
        veces en la terminal del físico."""
        for tipo in ("information", "warning", "critical"):
            monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_modelos_unicos",
            staticmethod(lambda: [{"model": EQUIPO_N31010["model"],
                                    "equip_type": EQUIPO_N31010["equip_type"]}]))
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_series_por_modelo",
            staticmethod(lambda m: [EQUIPO_N31010]))
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: EQUIPO_N31010 if i == EQUIPO_N31010["id"] else None))

        capsys.readouterr()  # limpia cualquier salida de imports previos
        d = DialogCalculadoraDosis(energias=[], parent=VentanaIX())
        salida = capsys.readouterr()
        # No se exige stdout vacío (hay un print de diagnóstico ajeno a C2,
        # "Dialog llamado desde: ..."): solo que el ruido de ValueError/
        # TypeError de la cascada con campos vacíos haya desaparecido.
        assert "could not convert string to float" not in salida.out, (
            f"la terminal no debía recibir el ruido de la cascada: {salida.out!r}"
        )
        d.deleteLater()

    def test_llamar_los_8_slots_directo_con_vacio_no_imprime(self, dialogo, capsys):
        """Ejercita cada uno de los 8 slots explícitamente (no solo lo que
        dispare la construcción) para no depender del orden de señales."""
        d = dialogo
        capsys.readouterr()
        d.lectura_dosimetria_prom()
        d.calcular_calidad_r50()
        d.calcular_profundidad_r50()
        d.calcular_dosis_maxima()
        d.coeficientes_ks_pulse()
        d.calcular_mq()
        d.Mprom()
        d.m2_prom()
        salida = capsys.readouterr()
        assert salida.out == "", f"no debía imprimir nada con campos vacíos: {salida.out!r}"


class TestExcepcionRealSiSeReporta:
    """Una excepción DISTINTA de ValueError/TypeError en la misma cascada
    debe seguir imprimiéndose -- C2 no debe volver silenciosa la detección
    de un defecto real."""

    def test_excepcion_no_esperada_se_imprime(self, dialogo, monkeypatch, capsys):
        d = dialogo
        for campo in (d.lDV1_1, d.lDV1_2, d.lDV1_3):
            campo.setText("12.437")

        def mean_roto(*a, **k):
            raise RuntimeError("fallo real, no entrada vacía")

        monkeypatch.setattr(dialogs_mod.np, "mean", mean_roto)
        capsys.readouterr()
        d.lectura_dosimetria_prom()
        salida = capsys.readouterr()
        assert "fallo real, no entrada vacía" in salida.out
