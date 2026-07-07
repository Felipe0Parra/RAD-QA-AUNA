"""Tests de caracterización del motor de física TRS-398 (Fase D1).

Estos tests fijan el comportamiento ACTUAL de services/dosis_service_calculations.py
antes de modificar la calculadora de dosis (Fases D2-D4). Dos capas:

1. Validación física: propiedades que exige el protocolo TRS-398 del OIEA
   (kTP=1 en condiciones de referencia, kQ=1 para la calidad del Co-60,
   ks=1 sin recombinación, ecuaciones de calidad de haz de electrones).
2. Caracterización: valores exactos calculados con el código actual, incluidos
   redondeos y guardas de división por cero. Si un cambio futuro altera un
   resultado numérico, estos tests lo detectan.

Los valores de referencia kQ marcados "TRS-398 Tabla 6.III" deben ser
confirmados por el físico médico contra su copia del protocolo.
"""
import pytest

import services.dosis_service_calculations as calc
from data.GraficasyTablas.calculadora_dosis_Tablas import COEFICIENTES_KS, KQ_TPR_TABLE

# Parámetros PTW 30013 Farmer (Q0_TABLE, clave "N30013"): kQ = f(TPR20,10)
A_30013, Q0_30013 = 9.6727, 1.1045


class TestFactorKTP:
    """kTP = (273.2+T)·P0 / ((273.2+T0)·P) — TRS-398 usa 273.2, no 273.15."""

    def test_condiciones_de_referencia_dan_uno(self):
        assert calc.factor_ktp(20.0, 101.325, 20.0, 101.325) == 1.0

    @pytest.mark.parametrize("t, p, esperado", [
        (22.0, 101.325, 1.0068),
        (18.0, 99.5, 1.0114),
        (25.0, 95.0, 1.0848),
    ])
    def test_valores_conocidos(self, t, p, esperado):
        assert calc.factor_ktp(t, p, 20.0, 101.325) == esperado

    def test_redondea_a_4_decimales(self):
        ktp = calc.factor_ktp(21.3, 100.2, 20.0, 101.325)
        assert ktp == round(ktp, 4)


class TestFactorPolaridad:
    """kpol = (|M+| + |M−|) / (2·M+)."""

    def test_lecturas_simetricas_dan_uno(self):
        assert calc.factor_polaridad(20.05, -20.05) == 1.0

    def test_valor_tipico(self):
        # (20.05 + 20.15) / (2·20.05) = 1.0024937... → 1.00249
        assert calc.factor_polaridad(20.05, -20.15) == 1.00249

    def test_guarda_mplus_cero(self):
        assert calc.factor_polaridad(0, -20.0) == 0


class TestCocientes:
    def test_ldv1_um(self):
        # round(round(20.15/200, 6), 5) → efectivamente 5 decimales
        assert calc.cociente_LDV1_UM(20.15, 200) == 0.10075

    def test_ldv1_um_guarda_um_cero(self):
        assert calc.cociente_LDV1_UM(20.15, 0) == 0

    def test_v1v2(self):
        assert calc.cociente_v1v2(400, 100) == 4.0

    def test_v1v2_guarda_cero(self):
        assert calc.cociente_v1v2(400, 0) == 0

    def test_m1m2_doble_redondeo(self):
        # round(round(1/3, 4), 5): el segundo round no agrega precisión
        assert calc.cociente_m1m2(1, 3) == 0.3333

    def test_m1m2_tipico(self):
        assert calc.cociente_m1m2(20.15, 20.05) == 1.005

    def test_m1m2_guarda_cero(self):
        assert calc.cociente_m1m2(1, 0) == 0


class TestFactorRecombinacionKs:
    """ks = a0 + a1·(M1/M2) + a2·(M1/M2)² — método de las dos tensiones."""

    def test_valor_realista(self):
        # Haz pulsado, V1/V2=4, M1/M2=1.006
        fila = COEFICIENTES_KS["pulsados"][4.0]
        assert calc.ks_factor(fila["a0"], fila["a1"], fila["a2"], 1.006) == 1.002

    @pytest.mark.parametrize("modo", ["pulsados", "pulsados_y_barridos"])
    def test_sin_recombinacion_ks_es_uno(self, modo):
        """Propiedad TRS-398: si M1=M2 no hay recombinación medible y ks≈1.

        Los coeficientes publicados (Tabla 4.VII) están redondeados, por eso
        a0+a1+a2 queda entre 1.000 y 1.003 en vez de exactamente 1.
        """
        for v1v2, fila in COEFICIENTES_KS[modo].items():
            ks = calc.ks_factor(fila["a0"], fila["a1"], fila["a2"], 1.0)
            assert 1.0 <= ks <= 1.003, f"{modo} V1/V2={v1v2}: ks(1)={ks}"


class TestInterpolarCoeficientesKs:
    def test_nodo_exacto_devuelve_fila_de_tabla(self):
        a0, a1, a2 = calc.interpolar_coeficientes_ks(COEFICIENTES_KS["pulsados"], 3.0)
        assert (a0, a1, a2) == pytest.approx((1.198, -0.8753, 0.6773))

    def test_punto_medio_interpola_linealmente(self):
        # c=2.25, mitad entre las filas 2.0 y 2.5 de "pulsados"
        a0, a1, a2 = calc.interpolar_coeficientes_ks(COEFICIENTES_KS["pulsados"], 2.25)
        assert (a0, a1, a2) == pytest.approx((1.9055, -2.6115, 1.7065))

    @pytest.mark.parametrize("c", [1.9, 5.1])
    def test_fuera_de_rango_lanza_valueerror(self, c):
        with pytest.raises(ValueError):
            calc.interpolar_coeficientes_ks(COEFICIENTES_KS["pulsados"], c)


class TestCalidadDeHazFotones:
    def test_charge_convierte_pdds_a_tpr2010(self):
        # TRS-398: TPR20,10 = 1.2661·(PDD20/PDD10) − 0.0595
        assert calc.charge(38.5, 66.6) == 0.6724

    def test_charge_guarda_pdd10_cero(self):
        assert calc.charge(38.5, 0) == 0

    def test_kq_normalizado_a_cobalto60(self):
        """Q = 0.57 (TPR20,10 del Co-60) debe dar kQ = 1 exacto."""
        assert calc.quality_kq0(Q0_30013, 0.57, A_30013) == 1.0

    @pytest.mark.parametrize("q, esperado", [
        (0.62, 0.9965),
        (0.68, 0.98939),
        (0.70, 0.98598),
        (0.76, 0.97101),
    ])
    def test_kq_caracterizacion_ptw30013(self, q, esperado):
        assert calc.quality_kq0(Q0_30013, q, A_30013) == esperado

    @pytest.mark.parametrize("q, kq_trs398", [
        (0.62, 0.9979),
        (0.68, 0.9896),
        (0.70, 0.9857),
        (0.76, 0.9714),
    ])
    def test_kq_coincide_con_trs398_tabla_6iii(self, q, kq_trs398):
        """El ajuste sigmoide reproduce los kQ tabulados del protocolo (±0.002)."""
        assert calc.quality_kq0(Q0_30013, q, A_30013) == pytest.approx(kq_trs398, abs=2e-3)

    @pytest.mark.parametrize("q", [0.62, 0.68, 0.70, 0.76])
    def test_kq_consistente_con_tabla_interna_30013(self, q):
        """Coherencia interna: el ajuste y KQ_TPR_TABLE["30013"] de la app
        describen la misma cámara; desviación máxima observada 0.004."""
        assert calc.quality_kq0(Q0_30013, q, A_30013) == pytest.approx(
            KQ_TPR_TABLE["30013"][q], abs=5e-3)


class TestKQBasadoEnTPR2010:
    # Parámetros de ajuste genuinos de N30013 en Q0_FIT_TABLE
    A_FIT, B_FIT = 1.18374, -0.13256

    def test_normalizado_a_cobalto60(self):
        assert calc.KQ_TPR2010_BASED(0.57, self.A_FIT, self.B_FIT) == 1.0

    @pytest.mark.parametrize("tpr, esperado", [
        (0.68, 0.98766),
        (0.76, 0.97008),
    ])
    def test_caracterizacion_n30013(self, tpr, esperado):
        assert calc.KQ_TPR2010_BASED(tpr, self.A_FIT, self.B_FIT) == esperado

    def test_hallazgo_d1h2_datos_corruptos_producen_kq_absurdo(self):
        """HALLAZGO D1-H2: varias filas de Q0_FIT_TABLE (N30001, N31002, ...)
        tienen copiados los valores A/Q0 de Q0_TABLE en los campos a/b.
        Con esos datos esta función devuelve kQ ≈ 1.105 para un haz de 6 MV
        (lo físico es ≈ 0.99): un error de dosis del ~11%.

        Hoy NO afecta al usuario: la UI calcula kQ con interpolar_kq0
        (KQ_TPR_TABLE) y get_ab solo alimenta prints de debug. Este test
        documenta el peligro; la tabla debe corregirse antes de conectar
        esta ruta en D2+.
        """
        assert calc.KQ_TPR2010_BASED(0.68, 9.8877, 1.1032) == 1.10483


class TestCalidadDeHazElectrones:
    def test_beam_quality_r50(self):
        # TRS-398: R50 = 1.029·R50,ion − 0.06  (R50,ion ≤ 10 g/cm²)
        assert calc.beam_quality_r50(4.0) == 4.056
        assert calc.beam_quality_r50(7.5) == 7.6575

    def test_zref_r50(self):
        # TRS-398: zref = 0.6·R50 − 0.1 g/cm²
        assert calc.zref_r50(4.0) == 2.3
        assert calc.zref_r50(7.5) == 4.4


class TestDosisAbsorbida:
    def test_dwref_es_producto_ndw_mq_kq(self):
        # TRS-398 ec. central: D_w,Q = M_Q · N_D,w,Q0 · k_Q,Q0
        assert calc.Dwref_calc(5.397, 12.437, 0.9896) == 66.4244151

    def test_dwqzmax_normaliza_por_pdd(self):
        assert calc.Dwqzmax_calc(66.43, 66.6) == 99.7447447

    def test_dwqzmax_guarda_pdd_cero(self):
        assert calc.Dwqzmax_calc(66.43, 0) == 0

    def test_dwqz_electrones_misma_formula_que_fotones(self):
        # Dwqz (SSD electrones) duplica la fórmula de Dwqzmax_calc
        assert calc.Dwqz(66.43, 66.6) == calc.Dwqzmax_calc(66.43, 66.6)

    def test_dwqz_guarda_pdd_cero(self):
        assert calc.Dwqz(66.43, 0) == 0

    def test_dwqzmax_sad_divide_por_tmr(self):
        assert calc.DwqzmaxSAD_calc(66.43, 0.776) == 85.60567

    def test_dwqzmax_sad_guarda_tmr_cero(self):
        assert calc.DwqzmaxSAD_calc(66.43, 0) == 0


class TestLecturaCorregidaMq:
    """Mq = M1 · kTP · kpol · ks (ke=1 fijo en el código actual)."""

    def test_fotones_redondea_a_6(self):
        assert calc.calcular_mq_fotones(12.345, 1.0068, 1.00249, 1.0021) == 12.48606

    def test_electrones_redondea_a_4(self):
        # Misma fórmula que fotones pero con redondeo distinto (4 decimales)
        assert calc.calcular_mq_electrones(12.345, 1.0068, 1.00249, 1.0021) == 12.4861


class TestCodigoMuertoGetAQ:
    @pytest.mark.parametrize("funcion", [calc.get_AQ, calc.get_ab])
    def test_hallazgo_d1h1_nameerror_con_cualquier_entrada(self, funcion):
        """HALLAZGO D1-H1: get_AQ/get_ab de ESTE módulo referencian Q0_TABLE y
        Q0_FIT_TABLE, que solo existen en calculadora_dosis_Tablas.py; cualquier
        llamada lanza NameError. Son código muerto: la app usa las versiones de
        DosisService, que sí resuelven las tablas vía import *.
        """
        with pytest.raises(NameError):
            funcion("N30013")
