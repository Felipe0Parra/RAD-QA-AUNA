"""Tests de caracterización de la capa DosisService (Fase D1).

Cubre lo que la calculadora de dosis de la UI llama realmente
(ui/paginasGuia/dialogs.py): delegaciones, tablas de cámaras e
interpolaciones. Los métodos de base de datos (guardar_datos,
buscar_por_fecha, ...) quedan fuera del alcance de D1: se cubrirán
cuando D2 toque la persistencia de la calculadora.
"""
import pytest

from services.dosis_service import DosisService
from data.GraficasyTablas.calculadora_dosis_Tablas import Q0_TABLE, Q0_FIT_TABLE


class TestTablasDeCamaras:
    def test_q0_table_completa(self):
        assert len(Q0_TABLE) == 16
        for camara, fila in Q0_TABLE.items():
            assert set(fila) == {"A", "Q0"}, camara
            # Q0 es un TPR20,10 extrapolado del ajuste; siempre ≈ 1.0-1.6
            assert 1.0 < fila["Q0"] < 1.6, camara

    def test_hallazgo_d1h2_filas_corruptas_en_q0_fit_table(self):
        """Las filas genuinas del ajuste kQ(TPR20,10) tienen a≈1.1-1.3 y b<0.
        Estas 8 tienen copiados A/Q0 de Q0_TABLE en los campos a/b: usarlas en
        KQ_TPR2010_BASED da kQ ≈ 1.1 (error ~11%). Hoy son inertes (la UI usa
        interpolar_kq0); si este test falla porque se corrigió la tabla,
        actualizarlo y recién entonces habilitar esa ruta de cálculo.
        """
        corruptas = {c for c, f in Q0_FIT_TABLE.items()
                     if not (0 < f["a"] < 2 and f["b"] < 0)}
        assert corruptas == {
            "N30001", "N31002", "N31006", "N31013 0.3 cm3 Semiflex",
            "N31014", "N31016", "N34001", "TN34001",
        }

    def test_get_aq_camara_conocida(self):
        assert DosisService.get_AQ("N30013") == (9.6727, 1.1045)

    def test_get_aq_camara_desconocida(self):
        assert DosisService.get_AQ("no-existe") == (0, 0)

    def test_get_ab_camara_conocida(self):
        assert DosisService.get_ab("N30013") == (1.18374, -0.13256)

    def test_get_ab_camara_desconocida(self):
        assert DosisService.get_ab("no-existe") == (0, 0)


class TestCoeficientesKs:
    def test_nodo_exacto(self):
        assert DosisService.obtener_coeficientes_ks("pulsados", 3.0) == \
            pytest.approx((1.198, -0.8753, 0.6773))

    def test_punto_medio_redondeado_a_6(self):
        assert DosisService.obtener_coeficientes_ks("pulsados", 2.25) == \
            pytest.approx((1.9055, -2.6115, 1.7065))

    def test_modo_invalido_lanza_valueerror(self):
        with pytest.raises(ValueError, match="Modo invalido"):
            DosisService.obtener_coeficientes_ks("continuos", 3.0)

    def test_ks_factor_delegacion(self):
        assert DosisService.Ks_factor(1.022, -0.3632, 0.3413, 1.006) == 1.002


class TestGuardaCamaraTieneKq:
    """Guarda D2: la UI la consulta antes de interpolar kQ. Es puro
    membership en KQ_TPR_TABLE: al agregar la fila de una cámara, la
    guarda se desactiva sola para ese modelo."""

    def test_camara_con_datos(self):
        assert DosisService.camara_tiene_kq("N31010") is True

    @pytest.mark.parametrize("modelo", [
        "N31014", "N31022", "TN31022", "N34001", "TN34001",
        "N30013",  # su fila existe pero con la clave "30013" — sin verificar aún
        None,
    ])
    def test_camaras_activas_sin_datos(self, modelo):
        assert DosisService.camara_tiene_kq(modelo) is False


class TestInterpolacionKQ:
    """interpolar_kq0 (redondeo 4) e interpolar_r50 (redondeo 5) comparten
    lógica y tabla KQ_TPR_TABLE; la UI usa la primera para el kQ mostrado."""

    def test_nodo_exacto(self):
        assert DosisService.interpolar_kq0("N30010", 0.68) == 0.99

    def test_punto_medio(self):
        # mitad entre 0.68 (0.990) y 0.70 (0.988)
        assert DosisService.interpolar_kq0("N30010", 0.69) == 0.989

    def test_hallazgo_d1h4_fuera_de_rango_recorta_en_silencio(self):
        """HALLAZGO D1-H4: una calidad de haz fuera de la tabla devuelve el kQ
        del borde sin avisar. TPR20,10=0.40 no es un haz clínico válido y aun
        así se obtiene un kQ "normal". D2 debe validar el rango en la UI.
        """
        assert DosisService.interpolar_kq0("N30010", 0.40) == 1.004
        assert DosisService.interpolar_kq0("N30010", 0.90) == 0.943

    def test_interpolar_r50_misma_tabla_redondeo_5(self):
        assert DosisService.interpolar_r50("N30010", 0.69) == 0.989

    def test_camara_desconocida_lanza_keyerror(self):
        with pytest.raises(KeyError):
            DosisService.interpolar_kq0("no-existe", 0.68)


class TestDelegaciones:
    """La UI llama estos métodos de clase; verificamos la cadena completa."""

    def test_factor_tp(self):
        assert DosisService.factor_tp(22.0, 101.325, 20.0, 101.325) == 1.0068

    def test_factor_k_polaridad(self):
        assert DosisService.factor_k_polaridad(20.05, -20.15) == 1.00249

    def test_calcular_q0(self):
        assert DosisService.calcular_Q0(38.5, 66.6) == 0.6724

    def test_r50_quality_y_depth(self):
        assert DosisService.r50_quality(4.0) == 4.056
        assert DosisService.r50_depth(4.0) == 2.3

    def test_calcular_mq_fot_funciona_sin_staticmethod(self):
        """calcular_mq_fot no tiene @staticmethod pero la UI lo llama vía la
        clase (dialogs.py:2590), lo que en Python 3 funciona igual."""
        assert DosisService.calcular_mq_fot(12.345, 1.0068, 1.00249, 1.0021) == 12.48606

    def test_calcular_mq_elec(self):
        assert DosisService.calcular_mq_elec(12.345, 1.0068, 1.00249, 1.0021) == 12.4861


class TestDispatcherCalcularMq:
    """calcular_mq(modo, **params) NO se usa desde la UI (que llama
    calcular_mq_fot/elec directo); se caracteriza por ser API pública."""

    def test_modo_fotones(self):
        assert DosisService.calcular_mq(
            "fotones", M1=12.345, ktp=1.0068, kpol=1.00249, ks=1.0021) == 12.48606

    def test_hallazgo_d1h3_modo_electrones_lanza_typeerror(self):
        """HALLAZGO D1-H3: la rama de electrones pasa 5 argumentos (incluye
        "hs") a calcular_mq_electrones, que acepta 4: TypeError garantizado.
        Código muerto hoy; corregir si D2+ decide usar el dispatcher.
        """
        with pytest.raises(TypeError):
            DosisService.calcular_mq(
                "electrones", M1=12.345, ktp=1.0068, kpol=1.00249, ks=1.0021, hs=1.0)

    def test_modo_invalido_lanza_valueerror(self):
        with pytest.raises(ValueError):
            DosisService.calcular_mq("gamma", M1=1, ktp=1, kpol=1, ks=1)
