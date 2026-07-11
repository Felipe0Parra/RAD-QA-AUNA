"""Tests D4.2 (PLAN_FASE_K_D4.md Sección 3): autollenado de simetría/
planicidad desde .mcc en el formulario mensual, compartido entre
PruebaMensual600 (solo 6mv) y PruebaMensualIX (6 energías) -- ver el
docstring de seleccionar_carpeta_mcc en seiscientos_mensual.py.

PruebaMensual600.__init__ es pesado (UI generada desde Excel, conexión a
BD real) y no aporta nada a estos tests: los métodos nuevos solo tocan
atributos QLineEdit propios vía getattr/hasattr. Se prueban sobre una
instancia "pelada" (__new__, sin __init__) con únicamente los QLineEdit
que cada test necesita -- igual de reales que en producción para lo que
estos métodos usan.

El físico eligió explícitamente (2026-07-10) que los valores autollenados
queden "marcados como sugeridos": el mecanismo real de eso NO es un color
persistente (se pisa en ~1s por el color de tolerancia ya existente en
_procesar_discrepancias_simetria_planicidad, ver comentario en el código)
sino tooltip + aviso al cargar + el gate de _confirmar_campos_mcc_sin_revisar
antes de guardar. Estas pruebas cubren esa cadena completa.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _instancia_pelada(energias):
    """PruebaMensual600 sin su __init__ pesado (BD/Excel), con los
    QLineEdit ln_simetria_*/ln_planicidad_* de las energías dadas (simula
    600 con ["6mv"] o iX con las 6 energías, según lo que pase el test).

    PyQt5 exige que el objeto C++ subyacente quede construido -- __new__ a
    secas revienta con "super-class __init__() ... was never called" en
    cuanto se toca cualquier atributo. Se llama QWidget.__init__ (la base
    real, PruebaBasico(QWidget)) directamente, saltándose
    PruebaMensual600.__init__/PruebaBasico.__init__ (BD real, UI desde
    Excel) que no aportan nada a estos tests."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    for energia in energias:
        for prefijo in ("ln_simetria_inplane_", "ln_simetria_crossplane_",
                        "ln_planicidad_inplane_", "ln_planicidad_crossplane_"):
            setattr(obj, f"{prefijo}{energia}", QLineEdit())
    return obj


VALORES = {"simetria_inplane": 0.87, "simetria_crossplane": 0.8,
           "planicidad_inplane": 2.47, "planicidad_crossplane": 2.47}


class TestAutollenarEnergiaMCC:
    def test_llena_los_4_campos_y_los_marca_pendientes(self, app):
        obj = _instancia_pelada(["6mv"])

        aplico = obj._autollenar_energia_mcc("6mv", VALORES)

        assert aplico is True
        assert obj.ln_simetria_inplane_6mv.text() == "0.87"
        assert obj.ln_simetria_crossplane_6mv.text() == "0.8"
        assert obj.ln_planicidad_inplane_6mv.text() == "2.47"
        assert obj.ln_planicidad_crossplane_6mv.text() == "2.47"
        assert obj._campos_mcc_sugeridos == {
            "ln_simetria_inplane_6mv", "ln_simetria_crossplane_6mv",
            "ln_planicidad_inplane_6mv", "ln_planicidad_crossplane_6mv"}

    def test_pone_tooltip_de_aviso(self, app):
        obj = _instancia_pelada(["6mv"])

        obj._autollenar_energia_mcc("6mv", VALORES)

        assert "verifique" in obj.ln_simetria_inplane_6mv.toolTip().lower()

    def test_energia_sin_campos_en_este_formulario_devuelve_false(self, app):
        """Ej.: formulario de 600 (solo 6mv) recibiendo una energía de
        electrones que nunca tendrá ln_simetria_inplane_6mev."""
        obj = _instancia_pelada(["6mv"])  # solo 6mv, como un 600 real

        aplico = obj._autollenar_energia_mcc("6mev", VALORES)

        assert aplico is False
        assert not hasattr(obj, "_campos_mcc_sugeridos") or not obj._campos_mcc_sugeridos


class TestMarcarCampoRevisado:
    def test_editar_el_campo_lo_saca_de_pendientes_y_limpia_tooltip(self, app):
        obj = _instancia_pelada(["6mv"])
        obj._autollenar_energia_mcc("6mv", VALORES)
        campo = obj.ln_simetria_inplane_6mv

        campo.textEdited.emit("0.90")

        assert "ln_simetria_inplane_6mv" not in obj._campos_mcc_sugeridos
        assert campo.toolTip() == ""

    def test_programmatic_settext_no_cuenta_como_revision(self, app):
        """setText() (autollenado) dispara textChanged, NO textEdited --
        solo una edición real del físico debe limpiar el pendiente."""
        obj = _instancia_pelada(["6mv"])
        obj._autollenar_energia_mcc("6mv", VALORES)

        obj.ln_simetria_inplane_6mv.setText("0.90")

        assert "ln_simetria_inplane_6mv" in obj._campos_mcc_sugeridos


class TestConfirmarCamposSinRevisar:
    def test_sin_pendientes_pasa_sin_preguntar(self, app, monkeypatch):
        obj = _instancia_pelada(["6mv"])  # no llama a _autollenar -> no hay pendientes
        def reventar(*a, **k):
            raise AssertionError("no debería preguntar si no hay pendientes")
        monkeypatch.setattr(mensual_mod.QMessageBox, "question", reventar)

        assert obj._confirmar_campos_mcc_sin_revisar() is True

    def test_con_pendientes_y_usuario_confirma_devuelve_true(self, app, monkeypatch):
        obj = _instancia_pelada(["6mv"])
        obj._autollenar_energia_mcc("6mv", VALORES)
        monkeypatch.setattr(mensual_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.Yes))

        assert obj._confirmar_campos_mcc_sin_revisar() is True

    def test_con_pendientes_y_usuario_rechaza_devuelve_false(self, app, monkeypatch):
        obj = _instancia_pelada(["6mv"])
        obj._autollenar_energia_mcc("6mv", VALORES)
        monkeypatch.setattr(mensual_mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: QMessageBox.No))

        assert obj._confirmar_campos_mcc_sin_revisar() is False


# ── Flujo completo: seleccionar_carpeta_mcc contra archivos .mcc sintéticos ──

def _bloque_scan(numero, curve_type, energy, modality, meas_date, filas):
    datos = "\n".join("\t\t\t" + "\t\t".join(str(x) for x in fila) for fila in filas)
    return (
        f"\tBEGIN_SCAN  {numero}\n"
        f"\t\tMEAS_DATE={meas_date}\n"
        f"\t\tMODALITY={modality}\n"
        f"\t\tENERGY={energy}\n"
        f"\t\tSCAN_CURVETYPE={curve_type}\n"
        "\t\tBEGIN_DATA\n"
        f"{datos}\n"
        "\t\tEND_DATA\n"
        f"\tEND_SCAN  {numero}\n"
    )


def _escribir_mcc(tmp_path, nombre, bloques):
    ruta = tmp_path / nombre
    ruta.write_text("BEGIN_SCAN_DATA\n" + "".join(bloques) + "END_SCAN_DATA\n")
    return str(ruta)


FILAS_PERFIL_6MV = [(str(p), f"{v:.4f}E+00", "0.29") for p, v in
                     [(-50, 1.2), (-20, 7.5), (0, 7.7), (20, 7.4), (50, 1.5)]]


class TestSeleccionarCarpetaMCC:
    def test_cancelar_dialogo_no_hace_nada(self, app, tmp_path, monkeypatch):
        obj = _instancia_pelada(["6mv"])
        monkeypatch.setattr(mensual_mod.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *a, **k: ""))

        obj.seleccionar_carpeta_mcc()

        assert obj.ln_simetria_inplane_6mv.text() == ""

    def test_carpeta_valida_llena_los_campos_y_avisa(self, app, tmp_path, monkeypatch):
        _escribir_mcc(tmp_path, "seis.mcc", [
            _bloque_scan(1, "INPLANE_PROFILE", "6.00", "X", "28-Feb-2026 11:00:00", FILAS_PERFIL_6MV),
            _bloque_scan(2, "CROSSPLANE_PROFILE", "6.00", "X", "28-Feb-2026 11:01:00", FILAS_PERFIL_6MV),
        ])
        obj = _instancia_pelada(["6mv"])
        monkeypatch.setattr(mensual_mod.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *a, **k: str(tmp_path)))
        avisos = []
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: avisos.append(a)))

        obj.seleccionar_carpeta_mcc()

        assert obj.ln_simetria_inplane_6mv.text() != ""
        assert obj.ln_planicidad_crossplane_6mv.text() != ""
        assert len(avisos) == 1
        assert "6mv" in avisos[0][2]

    def test_energia_sin_campos_en_este_formulario_no_se_cuenta_pero_no_falla(self, app, tmp_path, monkeypatch):
        """Carpeta con una energía de electrones cargada en un formulario
        tipo 600 (solo 6mv): no debe reventar, debe avisar "sin energías"."""
        _escribir_mcc(tmp_path, "electrones.mcc", [
            _bloque_scan(1, "INPLANE_PROFILE", "9.00", "EL", "28-Feb-2026 11:00:00", FILAS_PERFIL_6MV),
            _bloque_scan(2, "CROSSPLANE_PROFILE", "9.00", "EL", "28-Feb-2026 11:01:00", FILAS_PERFIL_6MV),
        ])
        obj = _instancia_pelada(["6mv"])
        monkeypatch.setattr(mensual_mod.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *a, **k: str(tmp_path)))
        avisos_warning = []
        monkeypatch.setattr(mensual_mod.QMessageBox, "warning",
                            staticmethod(lambda *a, **k: avisos_warning.append(a)))
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                AssertionError("no debería confirmar autollenado"))))

        obj.seleccionar_carpeta_mcc()

        assert any("Sin energías" in a[1] for a in avisos_warning)

    def test_archivo_roto_avisa_pero_no_impide_el_resto(self, app, tmp_path, monkeypatch):
        _escribir_mcc(tmp_path, "bueno.mcc", [
            _bloque_scan(1, "INPLANE_PROFILE", "6.00", "X", "28-Feb-2026 11:00:00", FILAS_PERFIL_6MV),
            _bloque_scan(2, "CROSSPLANE_PROFILE", "6.00", "X", "28-Feb-2026 11:01:00", FILAS_PERFIL_6MV),
        ])
        (tmp_path / "roto.mcc").write_text("esto no es un .mcc valido\n")
        obj = _instancia_pelada(["6mv"])
        monkeypatch.setattr(mensual_mod.QFileDialog, "getExistingDirectory",
                            staticmethod(lambda *a, **k: str(tmp_path)))
        avisos_warning = []
        monkeypatch.setattr(mensual_mod.QMessageBox, "warning",
                            staticmethod(lambda *a, **k: avisos_warning.append(a)))
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))

        obj.seleccionar_carpeta_mcc()

        assert obj.ln_simetria_inplane_6mv.text() != ""
        assert any("no se pudieron leer" in a[1].lower() for a in avisos_warning)
