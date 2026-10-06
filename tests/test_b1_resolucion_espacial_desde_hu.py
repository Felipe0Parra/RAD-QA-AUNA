"""B.1 (PLAN_HANDOFF_IMAGENES_22-09.md, reescrita el 22-09 y reducida el
23-09 tras D.0/D.1): `resolucion_espacial` medía su perfil sobre la imagen
YA ventaneada de 8 bits (`corte[ys, xs]`) -- la única de las seis funciones
de análisis que no leía de HU (§0.5 del plan). D.0 y D.1 ya sacaron la
GEOMETRÍA (dónde caen las 8 regiones del anillo) de esa dependencia; esta
tarea saca los VALORES.

Verificación (única, tras el ajuste del 23-09 -- la invariancia de la
geometría ya la exige D.0): el resultado de `resolucion_espacial` no puede
cambiar con la ventana de VISUALIZACIÓN, ni siquiera en el MTF -- antes sí
cambiaba, porque medía sobre datos saturados/reescalados por esa ventana.

Cuadro antes/después (§12.3, riesgo ALTO), medido sobre las 6 series
reales del corpus, entregado al físico en el propio plan: ningún veredicto
empeora; varios mejoran (Halcyon: 2→4 regiones OK; iX: de "ningún lp/cm
medible" a 7 lp/cm). Las regiones por encima del límite de Nyquist del
píxel pasan de "Picos insuficientes" (que sonaba a fallo) a "Fuera del
límite de muestreo" (que dice la causa física real).
"""
import os
import types
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from _catphan_oro import LIMITE_HOMOGENEIDAD_IX
from _corpus import serie_catphan
from analisisImagenes.catphan import motor
from analisisImagenes.catphan.serie import leer_serie
from analisisImagenes.Analisis_Catphan_TAC import resolucion_espacial

_LIMITE_POR_SERIE = {
    "TOMOGRAFO": None,
    "HALCYON_JUN": None,
    "HALCYON_SEP": None,
    "HALCYON_236": None,
    "IX_DIC": LIMITE_HOMOGENEIDAD_IX,
}

VENTANAS_MUY_DISTINTAS = ((40, 400), (400, 300), (-200, 2000))


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


def _ventanear(hu, wl, ww):
    lo, hi = wl - ww / 2, wl + ww / 2
    return ((np.clip(hu, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)


def _hu_ctp528(clave):
    """El corte de CTP528 en el marco de la APP (sin voltear nunca), más
    orientación/giro medidos -- mismo patrón que D.1."""
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    n = len(serie.cortes)
    perfil = types.SimpleNamespace(limite_variacion_hu=_LIMITE_POR_SERIE[clave], nombre=clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = motor.analizar(serie, perfil)
    idx_pylinac = resultado.modulos["CTP528"].corte_indice
    idx_app = (n - 1 - idx_pylinac) if resultado.orientacion == "invertido" else idx_pylinac

    import pydicom
    ds = pydicom.dcmread(serie.cortes[idx_app].ruta)
    hu = ds.pixel_array.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
    tam_px = float(ds.PixelSpacing[0])
    return hu, tam_px, resultado.orientacion, resultado.roll_deg


@pytest.mark.parametrize("clave", sorted(_LIMITE_POR_SERIE))
def test_a_valores_del_mtf_no_dependen_de_la_ventana(clave):
    hu, tam_px, orientacion, roll_deg = _hu_ctp528(clave)

    resultados = []
    for wl, ww in VENTANAS_MUY_DISTINTAS:
        corte_255 = _ventanear(hu, wl, ww)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resultado = resolucion_espacial(
                corte_255, hu, tam_px, visualizar=False,
                orientacion=orientacion, roll_deg=roll_deg,
            )
        estados = tuple(sorted(
            (k, v.get("status"), v.get("n_peaks_used")) for k, v in resultado["region_results"].items()
        ))
        resultados.append((estados, resultado["resolucion_limite"]["lp_cm_maximo"]))  # GI.0: la clave dice la unidad real (lp/cm)

    assert len(set(resultados)) == 1, (
        f"{clave}: resolucion_espacial cambió con la ventana de visualización -- "
        f"resultados distintos: {resultados}"
    )


def test_b_regiones_sobre_nyquist_se_declaran_fuera_de_muestreo():
    """El límite de Nyquist es un hecho físico del píxel, no un umbral de
    la app: para el tomógrafo (píxel más grueso del corpus, ≈1.074 mm) las
    últimas regiones deben decir explícitamente por qué no se miden."""
    hu, tam_px, orientacion, roll_deg = _hu_ctp528("TOMOGRAFO")
    corte_255 = _ventanear(hu, 40, 400)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = resolucion_espacial(
            corte_255, hu, tam_px, visualizar=False,
            orientacion=orientacion, roll_deg=roll_deg,
        )
    region_8 = resultado["region_results"]["region 8"]
    assert region_8["status"].startswith("Fuera del límite de muestreo")
    assert "Picos insuficientes" not in [
        v.get("status") for v in resultado["region_results"].values()
        if v.get("lp/cm", 0) > 4.65  # por encima del Nyquist medido del tomógrafo
    ]


def test_c_ix_pasa_de_no_medible_a_siete_lp_cm():
    """Cuadro antes/después medido (ver docstring del módulo): antes de
    B.1, el iX no lograba UNA sola región 'OK' (medía sobre datos
    saturados por su propio corrimiento de ≈+490 HU); después mide hasta
    7 lp/cm, con la región 8 (8 lp/cm) correctamente fuera del límite de
    Nyquist de su propio píxel (≈7.68 lp/cm)."""
    hu, tam_px, orientacion, roll_deg = _hu_ctp528("IX_DIC")
    corte_255 = _ventanear(hu, 40, 400)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = resolucion_espacial(
            corte_255, hu, tam_px, visualizar=False,
            orientacion=orientacion, roll_deg=roll_deg,
        )
    assert resultado["resolucion_limite"]["lp_cm_maximo"] == 7  # GI.0: antes `lp_mm_maximo`; guardaba lp/cm
    assert resultado["region_results"]["region 8"]["status"].startswith("Fuera del límite de muestreo")
