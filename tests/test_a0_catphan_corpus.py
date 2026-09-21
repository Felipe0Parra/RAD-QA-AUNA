"""A.0 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): las series Catphan
reales entran al corpus de los tests.

Objetivo: las rutas viven en un solo sitio (_corpus.py); si faltan, los
tests de Catphan saltan de forma honesta (skip), igual que el resto del
corpus (HI-0). Este archivo verifica solo eso -- la carga real y el
análisis de pylinac los verifican A.1/A.2/B.1.
"""
import os

import pytest

from _corpus import CATPHAN, CATPHAN_RAIZ, serie_catphan
from _catphan_oro import N_ARCHIVOS


@pytest.mark.parametrize("clave", sorted(N_ARCHIVOS))
def test_serie_existe_y_cuenta_dcm_correcta(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible en este entorno: {clave}")
    n = sum(
        1
        for f in os.listdir(ruta)
        if f.lower().endswith(".dcm")
    )
    assert n == N_ARCHIVOS[clave], (
        f"{clave}: se esperaban {N_ARCHIVOS[clave]} .dcm, hay {n}"
    )


def test_todas_las_claves_de_n_archivos_estan_en_catphan():
    assert set(N_ARCHIVOS) == set(CATPHAN)


def test_con_raiz_inexistente_todas_las_series_dan_none(monkeypatch):
    import _corpus

    monkeypatch.setattr(_corpus, "CATPHAN_RAIZ", "/ruta/que/no/existe/nunca")
    for clave in CATPHAN:
        ruta = os.path.join("/ruta/que/no/existe/nunca", CATPHAN[clave])
        assert not os.path.isdir(ruta)
        assert _corpus.serie_catphan(clave) is None
