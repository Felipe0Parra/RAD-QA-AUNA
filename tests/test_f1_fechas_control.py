"""F1 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md §2.4): módulo único de fechas para
`controles` -- formato de guardado, parser tolerante mes/año, comparador de
mes. Mueve el parseo que ya vivía en `consistencia_dosis._mes_anio_de_fecha`
(B3.7) para que `create_control` (F2) lo reutilice en vez de duplicarlo.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from services.fechas_control import (
    FORMATO_FECHA_CONTROL, mes_anio_de_fecha, mismo_mes,
)


class TestMesAnioDeFecha:

    def test_formato_mensual_sin_dia(self):
        assert mes_anio_de_fecha("07/2026") == (7, 2026)

    def test_formato_completo_con_dia(self):
        assert mes_anio_de_fecha("14/12/2025") == (12, 2025)

    def test_vacio_o_invalido_no_lanza(self):
        assert mes_anio_de_fecha("") == (None, None)
        assert mes_anio_de_fecha(None) == (None, None)
        assert mes_anio_de_fecha("no-es-una-fecha") == (None, None)

    def test_no_numerico_no_lanza(self):
        assert mes_anio_de_fecha("ab/cd") == (None, None)


class TestMismoMes:

    def test_mismo_mes_ambos_sin_dia(self):
        assert mismo_mes("07/2026", "07/2026") is True

    def test_mismo_mes_con_y_sin_dia(self):
        assert mismo_mes("15/07/2026", "07/2026") is True

    def test_mismo_mes_ambos_con_dia_distinto(self):
        assert mismo_mes("01/07/2026", "28/07/2026") is True

    def test_distinto_mes(self):
        assert mismo_mes("07/2026", "08/2026") is False

    def test_distinto_anio_mismo_mes_numerico(self):
        assert mismo_mes("07/2025", "07/2026") is False

    def test_invalida_no_es_igual_a_nada(self):
        assert mismo_mes("no-es-fecha", "07/2026") is False
        assert mismo_mes("07/2026", "no-es-fecha") is False


class TestFormatoFechaControl:

    def test_formato_incluye_el_dia(self):
        assert FORMATO_FECHA_CONTROL == "dd/MM/yyyy"
