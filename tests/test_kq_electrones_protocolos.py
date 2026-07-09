"""Tablas kQ(R50) de ELECTRONES por protocolo TRS-398 (auditoría 2026-07-09).

Contexto: la auditoría contra el corpus 2024 (104 hojas TRS-398 reales, 53 de
electrones) reveló que `Q0_R50_TABLE` es la Table 20 de la TRS-398 Rev.1 — NO
el Cuadro 18 de la TRS-398 original (2000) con el que están calculadas las
hojas del físico. Espejo exacto de la situación de fotones resuelta en Fase K.
Se agregó `Q0_R50_TABLE_2000` (fila Roos del Cuadro 18) y el registro
`Q0_R50_TABLAS_POR_PROTOCOLO`; la fila TN34001 de la tabla Rev.1 tenía
copiados por error los valores de la PTW 30013 (cilíndrica) y fue corregida.

Rigor de datos clínicos (patrón K2): además de los centinelas, ambas filas
Roos se verifican con una extracción INDEPENDIENTE contra el PDF oficial de
cada protocolo (se salta sola si el PDF no está en la máquina).
"""
import os

import pytest

from data.GraficasyTablas.calculadora_dosis_Tablas import (
    Q0_R50_TABLE,
    Q0_R50_TABLE_2000,
    Q0_R50_TABLAS_POR_PROTOCOLO,
)

NODOS_REV1 = [1.0, 1.4, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 10.0]
NODOS_2000 = NODOS_REV1 + [13.0, 16.0, 20.0]


class TestRegistroProtocolos:
    def test_registro_de_protocolos(self):
        assert set(Q0_R50_TABLAS_POR_PROTOCOLO.keys()) == {"2000", "rev1"}
        assert Q0_R50_TABLAS_POR_PROTOCOLO["2000"] is Q0_R50_TABLE_2000
        assert Q0_R50_TABLAS_POR_PROTOCOLO["rev1"] is Q0_R50_TABLE


class TestCentinelas2000:
    """Valores puntuales de la fila Roos del Cuadro 18 (TRS-398, 2000)."""

    def test_nodos_completos(self):
        assert sorted(Q0_R50_TABLE_2000["N34001"].keys()) == NODOS_2000

    def test_valores_extremos_y_medios(self):
        fila = Q0_R50_TABLE_2000["N34001"]
        assert fila[1.0] == 0.965
        assert fila[5.0] == 0.912
        assert fila[10.0] == 0.882
        assert fila[20.0] == 0.848

    def test_tn34001_es_la_misma_roos(self):
        assert Q0_R50_TABLE_2000["TN34001"] == Q0_R50_TABLE_2000["N34001"]

    def test_solo_roos_a_proposito(self):
        # Las cilíndricas del Cuadro 18 no tienen datos bajo R50=4: agregarlas
        # activaría el clamp silencioso (D1-H4) donde la Roos sí mide.
        assert set(Q0_R50_TABLE_2000.keys()) == {"N34001", "TN34001"}


class TestCentinelasRev1:
    """Valores puntuales de la Table 20 (TRS-398 Rev.1, 2024)."""

    def test_nodos_completos_roos(self):
        assert sorted(Q0_R50_TABLE["N34001"].keys()) == NODOS_REV1

    def test_valores_roos(self):
        fila = Q0_R50_TABLE["N34001"]
        assert fila[1.0] == 0.9743
        assert fila[5.0] == 0.9127
        assert fila[10.0] == 0.8907

    def test_tn34001_corregida_es_roos_no_farmer(self):
        # Antes de la corrección esta fila era una copia de la PTW 30013
        # (cilíndrica): una Roos con curva de Farmer y sin datos bajo R50=3.
        assert Q0_R50_TABLE["TN34001"] == Q0_R50_TABLE["N34001"]
        assert Q0_R50_TABLE["TN34001"] != Q0_R50_TABLE["N30013"]
        assert 1.0 in Q0_R50_TABLE["TN34001"]

    def test_fila_30013_intacta(self):
        fila = Q0_R50_TABLE["N30013"]
        assert fila[3.0] == 0.9300
        assert fila[10.0] == 0.9037


class TestPropiedadesFisicas:
    """kQ decrece monótonamente con R50 y vive en rango físico plausible."""

    @pytest.mark.parametrize("tabla", ["2000", "rev1"])
    def test_monotonia_decreciente(self, tabla):
        for camara, fila in Q0_R50_TABLAS_POR_PROTOCOLO[tabla].items():
            nodos = sorted(fila.keys())
            valores = [fila[n] for n in nodos]
            assert valores == sorted(valores, reverse=True), f"{tabla}/{camara}"

    @pytest.mark.parametrize("tabla", ["2000", "rev1"])
    def test_rango_fisico(self, tabla):
        for camara, fila in Q0_R50_TABLAS_POR_PROTOCOLO[tabla].items():
            for nodo, kq in fila.items():
                assert 0.83 <= kq <= 0.98, f"{tabla}/{camara}@{nodo}: {kq}"


# ── Verificación de transcripción: extracción DOBLE independiente ─────────

PDF_2000 = os.path.expanduser(
    "~/Documents/Archivos_UseApp/Archivos QA/TRS_398s_Web.pdf")
PDF_REV1 = os.path.expanduser(
    "~/Documents/Archivos_UseApp/Archivos QA/p15048-DOC-010-398-Rev1_web.pdf")


def _extraer_fila_roos(ruta_pdf, titulo_tabla, patron_numero, n_valores,
                       decimal_coma=False):
    """Extracción independiente: localiza la página cuyo texto contiene el
    título de la tabla, encuentra la etiqueta de la fila Roos y toma los
    números que la siguen."""
    import re
    import fitz

    doc = fitz.open(ruta_pdf)
    for pagina in doc:
        texto = pagina.get_text()
        if titulo_tabla in texto and "Roos" in texto:
            pos = texto.find("Roos", texto.find(titulo_tabla))
            # En el PDF 2000 hay una fila "Exradin 11a Roos type" previa a la
            # tabla; la fila buscada es la que va seguida de valores numéricos.
            while pos >= 0:
                resto = texto[pos:pos + 600]
                valores = re.findall(patron_numero, resto)[:n_valores]
                if len(valores) == n_valores:
                    if decimal_coma:
                        valores = [v.replace(",", ".") for v in valores]
                    return [float(v) for v in valores]
                pos = texto.find("Roos", pos + 1)
    raise AssertionError(f"fila Roos de '{titulo_tabla}' no encontrada en {ruta_pdf}")


@pytest.mark.skipif(not os.path.exists(PDF_2000),
                    reason="PDF TRS-398 (2000, español) no disponible en esta máquina")
class TestExtraccionDoble2000:
    def test_roos_cuadro18_coincide(self):
        # PDF español: decimales con coma ("0,965") y 17 nodos (1.0-20.0).
        extraido = _extraer_fila_roos(PDF_2000, "CUADRO 18", r"0,\d{3}", 17,
                                      decimal_coma=True)
        transcrito = [Q0_R50_TABLE_2000["N34001"][n] for n in NODOS_2000]
        assert transcrito == extraido


@pytest.mark.skipif(not os.path.exists(PDF_REV1),
                    reason="PDF TRS-398 Rev.1 no disponible en esta máquina")
class TestExtraccionDobleRev1:
    def test_roos_table20_coincide(self):
        extraido = _extraer_fila_roos(PDF_REV1, "TABLE 20", r"0\.\d{4}", 14)
        transcrito = [Q0_R50_TABLE["N34001"][n] for n in NODOS_REV1]
        assert transcrito == extraido
