"""B.1 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): el motor -- una
serie y un perfil entran, números con unidad salen.

El motor actual (funciones propias, `Analisis_Catphan_TAC.py`) tiene los
defectos D-09 a D-14. Pylinac ya corría en cada carga pero solo se usaba
su número de corte (§0.4). Aquí se verifica que `analizar()` reproduce
las referencias de oro de §0.8 en las 5 series reales, dentro de las
tolerancias de A.0.
"""
import os
import types
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pylinac
import pytest

from _catphan_oro import (
    ESPESOR_MM,
    GEOMETRIA_MM,
    HU_MATERIALES,
    LIMITE_HOMOGENEIDAD_IX,
    MTF50_LPMM,
    TOL_HU,
    TOL_LPMM,
    TOL_MM,
    BAJO_CONTRASTE_VISIBLES,
)
from _corpus import serie_catphan
from analisisImagenes.catphan import motor
from analisisImagenes.catphan.motor import VERSION_PYLINAC_VALIDADA, CatPhan504Radqa
from analisisImagenes.catphan.serie import leer_serie

_ORDEN_MATERIALES = ("aire", "pmp", "ldpe", "poliestireno", "acrilico", "delrin", "teflon")
_MATERIALES_PYLINAC = ("Air", "PMP", "LDPE", "Poly", "Acrylic", "Delrin", "Teflon")

# Las 5 series con sus parámetros de motor por equipo (§0.9). HALCYON_SEP
# entra en orientación invertida -- el motor la voltea solo (B.2); aquí
# solo se pide el límite de homogeneidad, no la orientación.
_LIMITE_POR_SERIE = {
    "TOMOGRAFO": None,
    "HALCYON_JUN": None,
    "HALCYON_236": None,
    "HALCYON_SEP": None,
    "IX_DIC": LIMITE_HOMOGENEIDAD_IX,
}


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


def _analizar(clave):
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    perfil = types.SimpleNamespace(limite_variacion_hu=_LIMITE_POR_SERIE[clave], nombre=clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return motor.analizar(serie, perfil)


@pytest.mark.parametrize("clave", sorted(HU_MATERIALES))
def test_hu_materiales_dentro_de_tolerancia(clave):
    resultado = _analizar(clave)
    m404 = resultado.modulos["CTP404"].metricas
    for nombre, esperado in zip(_ORDEN_MATERIALES, HU_MATERIALES[clave]):
        obtenido = m404[f"hu_{nombre}"].valor
        assert obtenido == pytest.approx(esperado, abs=TOL_HU), (
            f"{clave}/{nombre}: {obtenido} vs {esperado}"
        )


@pytest.mark.parametrize("clave", sorted(ESPESOR_MM))
def test_espesor_dentro_de_tolerancia(clave):
    resultado = _analizar(clave)
    esperado_medido, _esperado_nominal = ESPESOR_MM[clave]
    obtenido = resultado.modulos["CTP404"].metricas["espesor_mm"].valor
    assert obtenido == pytest.approx(esperado_medido, abs=TOL_MM)


@pytest.mark.parametrize("clave", sorted(GEOMETRIA_MM))
def test_geometria_promedio_dentro_de_tolerancia(clave):
    resultado = _analizar(clave)
    m404 = resultado.modulos["CTP404"].metricas
    distancias = [m404[k].valor for k in ("geo_x1_mm", "geo_x2_mm", "geo_y1_mm", "geo_y2_mm")]
    promedio = sum(distancias) / 4
    assert promedio == pytest.approx(GEOMETRIA_MM[clave], abs=TOL_MM)


@pytest.mark.parametrize("clave", sorted(MTF50_LPMM))
def test_mtf50_dentro_de_tolerancia(clave):
    resultado = _analizar(clave)
    mtf50_lpcm = resultado.modulos["CTP528"].metricas["mtf50_lpcm"].valor
    assert mtf50_lpcm / 10 == pytest.approx(MTF50_LPMM[clave], abs=TOL_LPMM)


@pytest.mark.parametrize("clave", sorted(BAJO_CONTRASTE_VISIBLES))
def test_bajo_contraste_visibles(clave):
    resultado = _analizar(clave)
    visibles = resultado.modulos["CTP515"].metricas["lc_visibles_1pct"].valor
    assert int(visibles) == BAJO_CONTRASTE_VISIBLES[clave]


def test_version_pylinac_tripwire():
    """Si esto falla, pylinac se actualizó -- CatPhan504Radqa copia código
    interno de la 3.45.0 y hay que re-validar la subclase antes de seguir."""
    assert pylinac.__version__ == VERSION_PYLINAC_VALIDADA


def test_catphan504radqa_sin_limite_es_identico_a_catphan504_puro():
    """Compuerta de daño colateral: `limite_variacion_hu=None` debe
    delegar en `super()` sin cambiar ningún resultado."""
    from pylinac.ct import CatPhan504

    ruta = _requerir("TOMOGRAFO")
    rutas = [c.ruta for c in leer_serie(ruta).cortes]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ct_a = CatPhan504Radqa(rutas)
        ct_a.limite_variacion_hu = None
        ct_a.analyze()
        ct_b = CatPhan504(rutas)
        ct_b.analyze()
    assert ct_a.origin_slice == ct_b.origin_slice
    for material in _MATERIALES_PYLINAC:
        assert ct_a.ctp404.rois[material].pixel_value == ct_b.ctp404.rois[material].pixel_value


def test_rojo_ix_sin_el_limite_de_homogeneidad_no_localiza():
    """D-04: sin el límite configurable, pylinac falla la localización en
    el iX (variación 109-114 HU contra el límite fijo de 100). El motor
    no debe inventar un resultado -- debe fallar de forma explícita."""
    ruta = _requerir("IX_DIC")
    serie = leer_serie(ruta)
    perfil = types.SimpleNamespace(limite_variacion_hu=None, nombre="IX_DIC")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(motor.OrientacionIndeterminada):
            motor.analizar(serie, perfil)


def test_ix_con_limite_localiza_en_el_origen_esperado():
    resultado = _analizar("IX_DIC")
    assert resultado.origen_indice == 42
