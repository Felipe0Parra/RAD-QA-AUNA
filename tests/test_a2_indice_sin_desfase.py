"""A.2 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): el corte sugerido es
el que pylinac analizó.

D-02: `slice_matcher.py` restaba 1 a `slice_num`, que ya es 0-based (solo
los TÍTULOS de las figuras de pylinac suman 1) -- la app mostraba un corte
antes del que pylinac realmente usó. Verificado contra §15 (puerta de
salida) del plan: "el corte sugerido para el CTP404 es el 48 (antes 47)".
"""
import os
import warnings

import pytest

from _corpus import serie_catphan
from analisisImagenes.catphan.serie import leer_serie
from data.ManejoDatos.catphan_TAC.slice_matcher import detectar_modulos_pylinac


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


def test_tomografo_ctp404_corte_humano_es_48():
    ruta = _requerir("TOMOGRAFO")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultados = detectar_modulos_pylinac(ruta)
    ctp404 = resultados["CTP404"]
    assert ctp404.confiable
    assert ctp404.idx_corte == 47
    assert ctp404.idx_corte + 1 == 48  # numeración para humanos (popup)


@pytest.mark.parametrize(
    "clave,modulo",
    [
        ("TOMOGRAFO", "CTP404"),
        ("TOMOGRAFO", "CTP486"),
        ("TOMOGRAFO", "CTP515"),
        ("TOMOGRAFO", "CTP528"),
        ("HALCYON_JUN", "CTP404"),
    ],
)
def test_idx_corte_coincide_con_slice_num_sin_resta(clave, modulo):
    """El índice que expone la app debe ser EXACTAMENTE `slice_num` (sin
    -1), y referirse al mismo archivo que pylinac usó -- verificado
    re-analizando con `CatPhan504` directamente sobre la misma lista de
    rutas que `detectar_modulos_pylinac` construye."""
    from pylinac.ct import CatPhan504

    ruta = _requerir(clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultados = detectar_modulos_pylinac(ruta)
        rutas = [c.ruta for c in leer_serie(ruta).cortes]
        ct = CatPhan504(rutas)
        ct.analyze()
    modulo_a_attr = {"CTP404": "ctp404", "CTP486": "ctp486", "CTP515": "ctp515", "CTP528": "ctp528"}
    slice_num_directo = int(getattr(ct, modulo_a_attr[modulo]).slice_num)
    assert resultados[modulo].idx_corte == slice_num_directo


def test_catphan504_recibe_lista_no_carpeta(monkeypatch):
    """Censo mínimo: `detectar_modulos_pylinac` debe construir la lista de
    rutas vía `leer_serie`, no pasar la carpeta cruda a `CatPhan504` (D-06:
    así los índices no pueden referirse a un archivo distinto del que
    ordenó A.1 si la carpeta tuviera una segunda serie)."""
    import pylinac

    ruta = _requerir("TOMOGRAFO")
    capturado = {}
    original = pylinac.CatPhan504.__init__

    def espia(self, folderpath, *a, **kw):
        capturado["folderpath"] = folderpath
        return original(self, folderpath, *a, **kw)

    monkeypatch.setattr(pylinac.CatPhan504, "__init__", espia)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        detectar_modulos_pylinac(ruta)
    assert isinstance(capturado["folderpath"], list)
    assert all(os.path.isfile(p) for p in capturado["folderpath"])
