"""V1 (PLAN_AUDITORIA_DOS_EJES_21-07.md SS7.5): `es_vigente_en_fecha` es la
misma regla de `verificar_vigencia_equipo` (años de vigencia por tipo de
equipo), parametrizada por una fecha de referencia arbitraria en vez de
asumir siempre "hoy". Función pura, sin BD ni Qt más allá de QDate.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate

from services.vigencia_equipo import VIGENCIA_ANOS_POR_TIPO, es_vigente_en_fecha


class TestCasosPermisivosPorDefecto:
    """Mismos defaults que verificar_vigencia_equipo: sin fecha, tipo
    desconocido, vigencia_anos=None, o fecha con formato inválido -> True."""

    def test_sin_fecha_calibracion_es_vigente(self):
        assert es_vigente_en_fecha(None, "Cámara de ionización", QDate(2030, 1, 1))
        assert es_vigente_en_fecha("", "Cámara de ionización", QDate(2030, 1, 1))

    def test_tipo_desconocido_es_vigente(self):
        assert es_vigente_en_fecha("01/01/2020", "Tipo Inexistente", QDate(2030, 1, 1))

    def test_tipo_sin_vigencia_definida_es_vigente(self):
        assert VIGENCIA_ANOS_POR_TIPO["Detector Rad."] is None
        assert es_vigente_en_fecha("01/01/2000", "Detector Rad.", QDate(2030, 1, 1))

    def test_fecha_con_formato_invalido_es_vigente(self):
        assert es_vigente_en_fecha("no-es-una-fecha", "Cámara de ionización", QDate(2030, 1, 1))


class TestReglaDeVigenciaPorTipo:
    def test_dentro_de_la_ventana_es_vigente(self):
        # Cámara de ionización: 2 años de vigencia.
        calibr = "01/01/2024"
        un_anio_despues = QDate(2025, 1, 1)
        assert es_vigente_en_fecha(calibr, "Cámara de ionización", un_anio_despues)

    def test_fuera_de_la_ventana_no_es_vigente(self):
        calibr = "01/01/2024"
        tres_anios_despues = QDate(2027, 1, 1)
        assert not es_vigente_en_fecha(calibr, "Cámara de ionización", tres_anios_despues)

    def test_limite_exacto_365_por_anio_es_vigente(self):
        # 2 años = 730 días exactos (regla original: <=), sin bisiestos de por medio.
        calibr = QDate(2023, 1, 1)
        limite = calibr.addDays(730)
        assert es_vigente_en_fecha(calibr.toString("dd/MM/yyyy"), "Cámara de ionización", limite)

    def test_un_dia_despues_del_limite_no_es_vigente(self):
        calibr = QDate(2023, 1, 1)
        pasado_el_limite = calibr.addDays(731)
        assert not es_vigente_en_fecha(calibr.toString("dd/MM/yyyy"), "Cámara de ionización", pasado_el_limite)

    def test_barometro_vigencia_de_1_anio(self):
        calibr = "01/06/2024"
        assert es_vigente_en_fecha(calibr, "Barómetro", QDate(2025, 1, 1))
        assert not es_vigente_en_fecha(calibr, "Barómetro", QDate(2026, 1, 1))


class TestElCasoQueMotivoV1:
    """El escenario exacto del físico (SS7.5 del plan): una cámara que venció
    hace poco aparecía "vencida" aunque el control se hiciera, con fecha
    pasada, cuando aún estaba vigente. Misma fila de equipo, misma regla;
    solo cambia la fecha de referencia."""

    def test_vigente_en_la_fecha_del_control_pero_vencida_hoy(self):
        calibr = "10/01/2024"  # Cámara de ionización, vigente hasta 10/01/2026
        fecha_del_control = QDate(2024, 6, 15)  # control retroactivo, dentro de la ventana
        fecha_hoy_lejana = QDate(2026, 7, 27)  # "hoy" muy posterior, ya vencida

        assert es_vigente_en_fecha(calibr, "Cámara de ionización", fecha_del_control)
        assert not es_vigente_en_fecha(calibr, "Cámara de ionización", fecha_hoy_lejana)
