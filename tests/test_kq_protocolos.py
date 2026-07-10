"""Tests del selector de protocolo TRS-398 (2000 / Rev.1) — Fase K.

KQ_TPR_TABLE (Cuadro 14, TRS-398 2000) sigue siendo la tabla default y
validada (D3: match exacto contra la hoja Excel real del físico).
KQ_TPR_TABLE_REV1 (Tabla 16, TRS-398 Rev.1) es la tabla nueva, provisional
(sin validar aún contra una hoja Rev.1 real — Fase K5, diferida).

Dos capas:
1. Centinelas + propiedades: deterministas, corren en cualquier máquina.
2. Verificación de transcripción por extracción DOBLE independiente contra
   el PDF real (se salta sola si el PDF no está en la máquina).
"""
import os

import pytest

from services.dosis_service import DosisService
from data.GraficasyTablas.calculadora_dosis_Tablas import (
    KQ_TPR_TABLE, KQ_TPR_TABLE_REV1, KQ_TABLAS_POR_PROTOCOLO,
)

NODOS_REV1 = (0.56, 0.59, 0.62, 0.65, 0.68, 0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82)


class TestCentinelasRev1:
    """Valores puntuales verificados a ojo contra la Tabla 16 (págs. 103-105)."""

    def test_n31010_0_62(self):
        assert DosisService.interpolar_kq0("N31010", 0.62, protocolo="rev1") == 0.9952

    def test_n31010_0_74(self):
        assert DosisService.interpolar_kq0("N31010", 0.74, protocolo="rev1") == 0.9750

    def test_30013_0_68(self):
        assert DosisService.interpolar_kq0("30013", 0.68, protocolo="rev1") == 0.9876

    def test_n31022_0_82(self):
        assert DosisService.interpolar_kq0("N31022", 0.82, protocolo="rev1") == 0.9540

    def test_interpolacion_intermedia_n31010(self):
        # Entre nodos 0.62 (0.9952) y 0.65 (0.9914): interpolación lineal.
        esperado = round(0.9952 + (0.9914 - 0.9952) * (0.626 - 0.62) / (0.65 - 0.62), 4)
        assert esperado == 0.9944
        assert DosisService.interpolar_kq0("N31010", 0.626, protocolo="rev1") == 0.9944
        # Documenta la diferencia real entre protocolos para la misma cámara/TPR:
        # 2000 usa la fila sustituta (N31002); rev1 usa los valores oficiales de la 31010.
        assert DosisService.interpolar_kq0("N31010", 0.626, protocolo="2000") == 0.9964


class TestPropiedadesTablaRev1:
    """Patrón D1: propiedades físicas de la tabla, no solo valores pineados."""

    @pytest.mark.parametrize("camara", list(KQ_TPR_TABLE_REV1.keys()))
    def test_nodos_completos(self, camara):
        assert set(KQ_TPR_TABLE_REV1[camara].keys()) == set(NODOS_REV1), camara

    @pytest.mark.parametrize("camara", list(KQ_TPR_TABLE_REV1.keys()))
    def test_estrictamente_decreciente(self, camara):
        valores = [KQ_TPR_TABLE_REV1[camara][n] for n in NODOS_REV1]
        assert all(a > b for a, b in zip(valores, valores[1:])), camara

    @pytest.mark.parametrize("camara", list(KQ_TPR_TABLE_REV1.keys()))
    def test_rango_fisico(self, camara):
        for v in KQ_TPR_TABLE_REV1[camara].values():
            assert 0.93 < v < 1.001, camara

    def test_tn31022_alias_de_n31022(self):
        assert KQ_TPR_TABLE_REV1["TN31022"] == KQ_TPR_TABLE_REV1["N31022"]

    def test_n30013_alias_de_30013(self):
        """E6 (auditoría 2026-07-10): "N30013" ya no está congelada -- la
        clave real de la BD (serie 2123) se confirmó con evidencia (hoja
        farmer real, 7/7 verdes) y ahora es alias de "30013" en ambos
        protocolos, no solo en KQ_TPR_TABLE (2000)."""
        assert KQ_TPR_TABLE_REV1["N30013"] == KQ_TPR_TABLE_REV1["30013"]

    def test_no_incluye_camaras_congeladas_o_ausentes(self):
        # N31014 no existe en Rev.1 (ausente también en el Cuadro 14 de 2000).
        assert "N31014" not in KQ_TPR_TABLE_REV1


class TestGuardasPorProtocolo:
    def test_n31022_sin_datos_en_2000(self):
        assert DosisService.camara_tiene_kq("N31022", "2000") is False

    def test_n31022_con_datos_en_rev1(self):
        assert DosisService.camara_tiene_kq("N31022", "rev1") is True

    def test_n31014_sin_datos_en_ningun_protocolo(self):
        assert DosisService.camara_tiene_kq("N31014", "2000") is False
        assert DosisService.camara_tiene_kq("N31014", "rev1") is False

    def test_n31002_no_esta_en_rev1(self):
        # N31002 (PTW 31002 flexible) es cámara 2000-only; Rev.1 no la publica.
        assert DosisService.camara_tiene_kq("N31002", "2000") is True
        assert DosisService.camara_tiene_kq("N31002", "rev1") is False

    def test_n31010_tiene_datos_en_ambos_protocolos(self):
        assert DosisService.camara_tiene_kq("N31010", "2000") is True
        assert DosisService.camara_tiene_kq("N31010", "rev1") is True


class TestDefaultYErrores:
    def test_default_sigue_siendo_2000(self):
        # Sin argumento explícito de protocolo, bit-idéntico al comportamiento pre-K.
        assert DosisService.interpolar_kq0("N31010", 0.626) == 0.9964

    def test_protocolo_invalido_lanza_keyerror(self):
        with pytest.raises(KeyError):
            DosisService.interpolar_kq0("N31010", 0.68, protocolo="no-existe")

    def test_registro_de_protocolos(self):
        assert set(KQ_TABLAS_POR_PROTOCOLO.keys()) == {"2000", "rev1"}
        assert KQ_TABLAS_POR_PROTOCOLO["2000"] is KQ_TPR_TABLE
        assert KQ_TABLAS_POR_PROTOCOLO["rev1"] is KQ_TPR_TABLE_REV1


# ── Verificación de transcripción: extracción DOBLE independiente ─────────

PDF_REV1 = os.path.expanduser(
    "~/Documents/Archivos_UseApp/Archivos QA/p15048-DOC-010-398-Rev1_web.pdf")

# Nombres de fila exactamente como aparecen en la Tabla 16 (para localizar la
# fila correcta con un parseo distinto al usado al transcribir KQ_TPR_TABLE_REV1).
_ETIQUETAS_TABLA16 = {
    "N30010": "PTW 30010",
    "N30011": "PTW 30011",
    "N30012": "PTW 30012",
    "30013": "PTW 30013",
    "N31010": "PTW 31010",
    "N31013": "PTW 31013",
    "N31016": "PTW 31016",
    "N31021": "PTW 31021",
    "N31022": "PTW 31022",
}


def _extraer_tabla16_independiente(ruta_pdf):
    """Segundo método de extracción (independiente del usado al transcribir
    KQ_TPR_TABLE_REV1): recorre el texto de las páginas 103-105, localiza cada
    etiqueta de cámara y toma los 12 números que la siguen como sus kQ."""
    import re
    import fitz

    doc = fitz.open(ruta_pdf)
    texto = "".join(doc[p].get_text() for p in (102, 103, 104))  # págs 103-105, 0-based
    numero = r"[01]\.\d{4}"

    resultado = {}
    for clave, etiqueta in _ETIQUETAS_TABLA16.items():
        pos = texto.find(etiqueta)
        assert pos >= 0, f"etiqueta no encontrada: {etiqueta}"
        resto = texto[pos:pos + 400]
        valores = re.findall(numero, resto)[:12]
        assert len(valores) == 12, f"{etiqueta}: solo {len(valores)} valores encontrados"
        resultado[clave] = [float(v) for v in valores]
    return resultado


@pytest.mark.skipif(not os.path.exists(PDF_REV1),
                    reason="PDF TRS-398 Rev.1 no disponible en esta máquina")
class TestExtraccionDobleContraPDFReal:
    def test_valores_transcritos_coinciden_con_extraccion_independiente(self):
        extraido = _extraer_tabla16_independiente(PDF_REV1)
        for clave, valores in extraido.items():
            fila = KQ_TPR_TABLE_REV1[clave]
            transcritos = [fila[n] for n in NODOS_REV1]
            assert transcritos == valores, (
                f"{clave}: transcrito={transcritos} vs extraído_independiente={valores}"
            )
