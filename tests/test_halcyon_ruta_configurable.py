r"""J3 (companion de J1/J2, PLAN_HALCYON_SELECCION_CARPETA_21-07): la ruta del
MPC de Halcyon se puede sobreescribir con `RADQA_HALCYON_MPC` para poder
probar el flujo completo (p.ej. en Windows, sin el share \\VARIANDB\...)
sin tocar código ni arriesgar olvidar revertir un cambio manual antes de un
build. En producción nadie define esa variable -- `ruta_mpc_halcyon()`
sigue devolviendo la ruta de red real, byte-idéntica a la de antes.
"""
import data.ManejoDatos.obtenerDatosHalcyon as halcyon_mod
from data.ManejoDatos.obtenerDatosHalcyon import ruta_mpc_halcyon


def test_sin_variable_de_entorno_usa_la_ruta_de_red_real(monkeypatch):
    monkeypatch.delenv("RADQA_HALCYON_MPC", raising=False)
    assert ruta_mpc_halcyon() == r"\\VARIANDB\Va_Transfer\TDS\HAL1161\MPCChecks"


def test_con_variable_de_entorno_usa_la_ruta_local(monkeypatch, tmp_path):
    monkeypatch.setenv("RADQA_HALCYON_MPC", str(tmp_path))
    assert ruta_mpc_halcyon() == str(tmp_path)


def test_addInfo_respeta_la_ruta_configurada(monkeypatch, tmp_path):
    """addInfo no debe seguir usando la constante hardcodeada -- confirma que
    de verdad llama a ruta_mpc_halcyon() en vez de la ruta de red fija."""
    monkeypatch.setenv("RADQA_HALCYON_MPC", str(tmp_path))
    capturada = {}

    def _falsa(ruta_base, fecha):
        capturada["ruta_base"] = ruta_base
        return None

    monkeypatch.setattr(halcyon_mod, "seleccionar_carpeta_mpc", _falsa)
    monkeypatch.setattr(halcyon_mod, "carpetas_mpc_de_fecha", lambda *a, **k: [])
    monkeypatch.setattr(halcyon_mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    halcyon_mod.addInfo(None, "2026-07-01", "fisico_prueba")

    assert capturada["ruta_base"] == str(tmp_path)
