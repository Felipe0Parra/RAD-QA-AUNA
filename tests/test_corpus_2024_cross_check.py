"""Cross-check del motor de producción contra el corpus 2024 COMPLETO,
desglosado por acelerador (Fase F4, auditoría 2026-07-10).

Motivación (hallazgo H-F4): la verificación de la Fase E contra las 104 hojas
TRS-398 reales (600/Halcyon/iX, fotones y electrones) vivió solo en un script
de scratchpad -- se perdió al cerrar la sesión y nunca quedó reproducible en
la suite. Este archivo la convierte en tests permanentes, con la garantía
explícita que le faltaba: 600 y Halcyon deben ser 100% verdes por sí solos
(no solo "en el agregado"), y iX no debe tener ninguna fila "no comparable".

Se salta entero si el corpus no está en la máquina (equipo distinto al de
desarrollo, o corpus movido/archivado).
"""
import os
from pathlib import Path

import pytest

from services.trs398_excel import leer_trs398, comparar_trs398

CORPUS = Path(os.path.expanduser("~/Documents/Archivos_UseApp/Archivos QA/2024"))

# Serie de cámara -> modelo (inventario real, BD de producción solo-lectura,
# verificado 2026-07-09/10). Config de oro (PLAN_FASE_F0_GATE.md §5): fotones
# siempre N31010/serie 1822 en las 3 máquinas -- las series 1825/2426 que
# aparecen abajo son recalibraciones/otras cámaras históricas del mismo
# corpus, no la config de oro vigente, pero deben seguir resolviendo bien.
SERIE_A_MODELO = {
    1822: "N31010", 1825: "N31010", 2123: "N30013",
    453: "N31014", 152342: "N31022", 1069: "N34001", 2426: "N34001",
}

# Grafías de carpeta observadas en el corpus real para el mismo acelerador
# (inconsistencia de organización del físico entre meses, no de la app).
GRAFIAS_IX = {"IX", "iX", "Cinac IX", "Clinac IX"}


def _acelerador_de_ruta(ruta):
    partes = ruta.relative_to(CORPUS).parts  # [mes, acelerador, ...]
    carpeta = partes[1]
    if carpeta in GRAFIAS_IX:
        return "iX"
    return carpeta  # "600" o "Halcyon"


def _comparar_archivo(ruta):
    datos = leer_trs398(str(ruta))
    serie = datos["entradas"].get("serie_camara")
    modelo = SERIE_A_MODELO.get(int(float(serie))) if serie else None
    return datos["tipo_haz"], comparar_trs398(datos, modelo_camara=modelo)


pytestmark = pytest.mark.skipif(
    not CORPUS.exists(), reason="corpus 2024 no disponible en esta máquina")


@pytest.fixture(scope="module")
def archivos_por_acelerador():
    archivos = sorted(CORPUS.rglob("TRS*.xls"))
    agrupados = {"600": [], "Halcyon": [], "iX": []}
    for ruta in archivos:
        agrupados[_acelerador_de_ruta(ruta)].append(ruta)
    return agrupados


class TestSeiscientosSiempreVerde:
    """600 (6 MV, cámara N31010/serie 1822 en la config de oro): sin
    electrones, sin las hojas de 15 MV que motivan las DIF conocidas de iX.
    Debe ser 100% verde por sí solo, no solo "en el agregado"."""

    def test_hay_archivos_600_en_el_corpus(self, archivos_por_acelerador):
        assert len(archivos_por_acelerador["600"]) >= 11, (
            "se esperaban ~11 hojas de 600 (una por mes) -- ¿corpus incompleto?")

    def test_todas_las_hojas_600_comparan_verde(self, archivos_por_acelerador):
        for ruta in archivos_por_acelerador["600"]:
            tipo_haz, filas = _comparar_archivo(ruta)
            assert tipo_haz == "fotones", ruta
            for f in filas:
                assert f["comparable"], f"{ruta.name}: {f['magnitud']} no comparable"
                assert f["ok"], f"{ruta.name}: {f['magnitud']} difiere ({f['diferencia_rel']:.3%})"


class TestHalcyonSiempreVerde:
    """Halcyon (6 MV FFF, misma cámara de fotones). Debe ser 100% verde."""

    def test_hay_archivos_halcyon_en_el_corpus(self, archivos_por_acelerador):
        assert len(archivos_por_acelerador["Halcyon"]) >= 11, (
            "se esperaban ~11 hojas de Halcyon -- ¿corpus incompleto?")

    def test_todas_las_hojas_halcyon_comparan_verde(self, archivos_por_acelerador):
        for ruta in archivos_por_acelerador["Halcyon"]:
            tipo_haz, filas = _comparar_archivo(ruta)
            assert tipo_haz == "fotones", ruta
            for f in filas:
                assert f["comparable"], f"{ruta.name}: {f['magnitud']} no comparable"
                assert f["ok"], f"{ruta.name}: {f['magnitud']} difiere ({f['diferencia_rel']:.3%})"


class TestIXElectronesSiempreVerde:
    """iX electrones (Roos/TN34001 en la config de oro, N34001 en filas
    históricas del corpus): las 53 hojas deben seguir siendo 100% verdes
    (E1-E3 ya lo corrigieron; este test evita que una regresión futura pase
    inadvertida)."""

    def test_hay_archivos_electrones_ix(self, archivos_por_acelerador):
        archivos = [r for r in archivos_por_acelerador["iX"] if "Electrones" in r.parts]
        assert len(archivos) >= 40, "se esperaban ~53 hojas de electrones iX"

    def test_todas_las_hojas_electrones_ix_comparan_verde(self, archivos_por_acelerador):
        for ruta in archivos_por_acelerador["iX"]:
            if "Electrones" not in ruta.parts:
                continue
            tipo_haz, filas = _comparar_archivo(ruta)
            assert tipo_haz == "electrones", ruta
            for f in filas:
                assert f["comparable"], f"{ruta.name}: {f['magnitud']} no comparable"
                assert f["ok"], f"{ruta.name}: {f['magnitud']} difiere ({f['diferencia_rel']:.3%})"


class TestIXFotonesSinNoComparables:
    """iX fotones (6 y 15 MV): las hojas de 15 MV difieren ~0.10-0.12% en kQ
    porque el Excel del físico usa OTRA fila de cámara sustituta para esa
    energía (hallazgo para el físico, no un bug de la app -- ver plan E4-E6
    §5 y el diario de CLAUDE.md). Esta suite NO exige que las 15 MV den
    verde, pero SÍ exige que nunca queden como "no comparable" (kQ es E6, ya
    resuelto para la Farmer)."""

    def test_hay_archivos_fotones_ix(self, archivos_por_acelerador):
        archivos = [r for r in archivos_por_acelerador["iX"] if "Fotones" in r.parts]
        assert len(archivos) >= 20, "se esperaban ~51 hojas de fotones iX"

    def test_ninguna_hoja_fotones_ix_queda_no_comparable(self, archivos_por_acelerador):
        for ruta in archivos_por_acelerador["iX"]:
            if "Fotones" not in ruta.parts:
                continue
            tipo_haz, filas = _comparar_archivo(ruta)
            assert tipo_haz == "fotones", ruta
            for f in filas:
                assert f["comparable"], f"{ruta.name}: {f['magnitud']} no comparable"

    def test_hojas_6mv_ix_comparan_verde(self, archivos_por_acelerador):
        """Las hojas de 6 MV (misma fila de cámara que 600/Halcyon) SÍ deben
        dar verde -- solo las de 15 MV tienen la discrepancia de datos."""
        for ruta in archivos_por_acelerador["iX"]:
            if "Fotones" not in ruta.parts or "6 MV" not in ruta.name:
                continue
            _, filas = _comparar_archivo(ruta)
            for f in filas:
                assert f["ok"], f"{ruta.name}: {f['magnitud']} difiere ({f['diferencia_rel']:.3%})"
