"""B3.4/B3.5 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7): recuperación por la
clave REAL (Acelerador, energia), no solo (Fecha, Acelerador).

El hallazgo original P1/B3 documentaba que fotones y electrones del mismo
día+máquina se pisaban al recargar (buscar_por_fecha solo filtraba por
Fecha+Acelerador). Ahora buscar_por_fecha admite un filtro opcional de
energia (compatible con todos los llamadores existentes, que no lo pasan),
y buscar_vigente resuelve directamente "cuál es el cálculo vigente de esta
clave", sin importar cuándo se guardó -- la consulta que necesita el botón
"Cargar cálculo" (B3-e).
"""
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.dialogs as dialogs_mod
from services.dosis_service import DosisService
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

REGISTRO_BASE = {
    "Fecha": "22/07/2026", "Acelerador": "IX",
    "Tipo_de_radiacion": "Fotones",
}


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


class TestBuscarPorFechaConEnergia:

    def test_sin_energia_se_comporta_como_antes(self, bd_temporal):
        """Compatibilidad: energia=None (default, todos los llamadores
        anteriores a B3) sigue siendo Fecha+Acelerador nada más -- toma la
        más reciente por id, sin distinguir energía."""
        assert DosisService.guardar_datos(dict(REGISTRO_BASE, energia="6mv")) is True
        assert DosisService.guardar_datos(dict(REGISTRO_BASE, energia="15mv")) is True

        recuperado = DosisService.buscar_por_fecha(REGISTRO_BASE["Fecha"], "IX")
        assert recuperado["energia"] == "15mv"  # la más reciente por id

    def test_con_energia_distingue_fotones_de_electrones_mismo_dia(self, bd_temporal):
        """El hallazgo P1/B3 original: 6mv y 6mev del mismo día+máquina ya
        no se pisan si se pide la energía exacta."""
        assert DosisService.guardar_datos(
            dict(REGISTRO_BASE, energia="6mv", Tipo_de_radiacion="Fotones")) is True
        assert DosisService.guardar_datos(
            dict(REGISTRO_BASE, energia="6mev", Tipo_de_radiacion="Electrones")) is True

        fotones = DosisService.buscar_por_fecha(REGISTRO_BASE["Fecha"], "IX", "6mv")
        electrones = DosisService.buscar_por_fecha(REGISTRO_BASE["Fecha"], "IX", "6mev")

        assert fotones["Tipo_de_radiacion"] == "Fotones"
        assert electrones["Tipo_de_radiacion"] == "Electrones"

    def test_energia_inexistente_devuelve_none(self, bd_temporal):
        assert DosisService.guardar_datos(dict(REGISTRO_BASE, energia="6mv")) is True
        assert DosisService.buscar_por_fecha(REGISTRO_BASE["Fecha"], "IX", "15mev") is None


class TestBuscarVigente:

    def test_encuentra_la_vigente_sin_importar_la_fecha(self, bd_temporal):
        assert DosisService.guardar_datos(
            dict(REGISTRO_BASE, Fecha="01/06/2026", energia="6mv")) is True
        assert DosisService.guardar_datos(
            dict(REGISTRO_BASE, Fecha="15/07/2026", energia="6mv")) is True  # nueva version

        vigente = DosisService.buscar_vigente("IX", "6mv")
        assert vigente["Fecha"] == "15/07/2026"

    def test_nombre_corto_o_canonico_encuentran_lo_mismo(self, bd_temporal):
        assert DosisService.guardar_datos(dict(REGISTRO_BASE, energia="6mv")) is True

        assert DosisService.buscar_vigente("IX", "6mv")["Fecha"] == REGISTRO_BASE["Fecha"]
        assert DosisService.buscar_vigente("Clinac iX", "6mv")["Fecha"] == REGISTRO_BASE["Fecha"]

    def test_sin_ningun_guardado_devuelve_none(self, bd_temporal):
        assert DosisService.buscar_vigente("IX", "6mv") is None

    def test_clave_distinta_no_interfiere(self, bd_temporal):
        assert DosisService.guardar_datos(dict(REGISTRO_BASE, energia="6mv")) is True
        assert DosisService.buscar_vigente("IX", "15mv") is None
        assert DosisService.buscar_vigente("Seiscientos", "6mv") is None


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestMensajeIncluyeEnergia:
    """B3.4/B3.5: la pregunta de "ya existe un registro" debe mostrar CON
    QUÉ energía, para que el físico entienda cuál cálculo colisiona."""

    @pytest.fixture
    def dialogo(self, app, bd_temporal, monkeypatch):
        for tipo in ("information", "warning", "critical"):
            monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
        d = DialogCalculadoraDosis(energias=["6mv"], parent=QWidget())
        yield d
        d.deleteLater()

    def test_mensaje_con_energia_la_menciona(self, dialogo, monkeypatch):
        capturado = {}
        monkeypatch.setattr(
            dialogs_mod.QMessageBox, "question",
            staticmethod(lambda *a, **k: capturado.update(texto=a[2]) or dialogs_mod.QMessageBox.No))

        dialogo._confirmar_registro_existente("22/07/2026", "Clinac iX", "6mv")

        assert "6mv" in capturado["texto"]
        assert "Clinac iX" in capturado["texto"]

    def test_mensaje_sin_energia_no_la_menciona(self, dialogo, monkeypatch):
        capturado = {}
        monkeypatch.setattr(
            dialogs_mod.QMessageBox, "question",
            staticmethod(lambda *a, **k: capturado.update(texto=a[2]) or dialogs_mod.QMessageBox.No))

        dialogo._confirmar_registro_existente("22/07/2026", "Clinac iX")

        assert "Clinac iX" in capturado["texto"]
        assert "(" not in capturado["texto"]
