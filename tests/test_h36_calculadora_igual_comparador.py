"""H3.6 (auditoría 2026-07-14) -- fija la propiedad central de la
reconciliación calculadora == comparador.

Antes de H3.6, `cargar_datos_equipo` redondeaba t_cal/p_cal a 1 decimal (G3)
antes de calcular ktp, mientras que el comparador (`_recalcular_con_app`,
services/trs398_excel.py) usa el T0/P0 crudo de la celda del Excel. Con la
MISMA hoja real, eso hacía que la calculadora y el comparador dieran ktp
distinto en el 4º decimal (ver PLAN_FASE_H_AUDITORIA_Y_REVISION_14-07.md,
sección 1.2). Este test prueba que, alimentando la calculadora con las
mismas entradas crudas que lee el comparador de una hoja TRS-398 real, ktp
sale IDÉNTICO -- no solo "dentro de tolerancia".

Se limita a ktp (no a las 7 magnitudes del comparador) porque es la única
que H3.6 tocó: kpol/ks dependen de celdas (Mplus/M1_recomb) que la UI de la
calculadora deriva de lDV1_prom en vez de aceptarlas como entradas
independientes, así que reproducirlas fielmente desde una hoja arbitraria
no es robusto. Esa cadena completa (con tolerancia 0.1%, que ya cubre ese
acoplamiento) sigue verificada por test_corpus_2024_cross_check.py.
"""
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis
from services.trs398_excel import leer_trs398
from services.dosis_service import DosisService
from _corpus import CORPUS_2024  # HI-0: fuente única de rutas del corpus

CORPUS = Path(CORPUS_2024)  # 2024 intacto; ruta centralizada en tests/_corpus.py

pytestmark = pytest.mark.skipif(
    not CORPUS.exists(), reason="corpus 2024 no disponible en esta máquina")


class VentanaSeiscientos(QWidget):
    """Padre falso -- el nombre no importa para este test (ktp no depende
    del acelerador deducido)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _hojas_600():
    archivos = sorted(CORPUS.rglob("TRS*.xls"))
    return [r for r in archivos if r.relative_to(CORPUS).parts[1] == "600"]


class TestKtpCalculadoraIgualComparador:
    """Recorre TODAS las hojas de 600 disponibles (misma cámara/config en
    todo el corpus, sin las complicaciones de 15 MV/electrones) -- ktp debe
    coincidir exacto en cada una, no solo en una muestra elegida a mano."""

    def test_hay_hojas_600_para_probar(self):
        assert len(_hojas_600()) >= 5, "corpus 2024 incompleto para 600"

    def test_ktp_exacto_con_entradas_de_cada_hoja_600(self, app, monkeypatch):
        hojas = _hojas_600()
        assert hojas, "no se encontró ninguna hoja de 600 en el corpus"

        for tipo in ("information", "warning", "critical"):
            monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))

        for ruta in hojas:
            datos = leer_trs398(str(ruta))
            e = datos["entradas"]
            if any(e.get(k) in (None, "") for k in ("T0", "P0", "T_clinica", "P_clinica")):
                continue  # hoja sin las 4 entradas de ktp -- nada que comparar aquí
            t0, p0 = float(e["T0"]), float(e["P0"])
            t_cli, p_cli = float(e["T_clinica"]), float(e["P_clinica"])

            equipo = {"id": 1, "equip_type": "Cámara de ionización", "model": "N31010",
                      "serie": "1822", "calibr_fact": float(e["factor_calibracion"]),
                      "t_cal": t0, "p_cal": p0,
                      "h_cal": float(e["humedad_calib"]) if e.get("humedad_calib") not in (None, "") else 0.0}
            monkeypatch.setattr(
                dialogs_mod.EquiposService, "obtener_modelos_unicos",
                staticmethod(lambda: [{"model": equipo["model"], "equip_type": equipo["equip_type"]}]))
            monkeypatch.setattr(
                dialogs_mod.EquiposService, "obtener_series_por_modelo",
                staticmethod(lambda m: [equipo] if m == equipo["model"] else []))
            monkeypatch.setattr(
                dialogs_mod.EquiposService, "obtener_por_id",
                staticmethod(lambda i: equipo if i == equipo["id"] else None))

            d = DialogCalculadoraDosis(energias=["6mv"], parent=VentanaSeiscientos())
            try:
                idx = d.combo_modelos.findData(equipo["model"])
                d.combo_modelos.setCurrentIndex(idx)
                d.combo_series.setCurrentIndex(1)

                # H3.6: t_cal/p_cal cargan CRUDOS -- deben coincidir con
                # T0/P0 de la hoja, no con una versión redondeada.
                assert float(d.temp_0.text()) == t0, ruta.name
                assert float(d.pressure_0.text()) == p0, ruta.name

                d.temp.setText(str(t_cli))
                d.pressure.setText(str(p_cli))

                app_ktp = DosisService.factor_tp(t_cli, p_cli, t0, p0)
                assert d.ktp.text() == str(app_ktp), (
                    f"{ruta.name}: calculadora={d.ktp.text()!r} vs "
                    f"comparador(app)={app_ktp!r}")
            finally:
                d.deleteLater()
