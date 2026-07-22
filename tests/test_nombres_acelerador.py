"""B3-N (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7b): nombre canónico de
acelerador, compartido entre calculadora_dosimetrica y controles.equipo."""
from services.nombres_acelerador import (
    nombre_canonico, mismo_acelerador, NOMBRES_CANONICOS,
)


class TestNombreCanonico:

    def test_codigos_cortos_de_la_calculadora(self):
        assert nombre_canonico("IX") == "Clinac iX"
        assert nombre_canonico("Hc") == "Halcyon"
        assert nombre_canonico("Seiscientos") == "Clinac 600"

    def test_nombres_historicos_de_controles_equipo(self):
        assert nombre_canonico("Clinac ix") == "Clinac iX"
        assert nombre_canonico("Clinac 600") == "Clinac 600"
        assert nombre_canonico("Halcyon") == "Halcyon"

    def test_tolera_mayusculas_y_espacios(self):
        assert nombre_canonico(" ix ") == "Clinac iX"
        assert nombre_canonico("HALCYON") == "Halcyon"
        assert nombre_canonico("Clinac IX") == "Clinac iX"
        assert nombre_canonico("SEISCIENTOS") == "Clinac 600"

    def test_variante_desconocida_se_devuelve_sin_cambios(self):
        assert nombre_canonico("Tomógrafo") == "Tomógrafo"
        assert nombre_canonico("Cobalto-60") == "Cobalto-60"

    def test_none_y_vacio_no_lanzan(self):
        assert nombre_canonico(None) is None
        assert nombre_canonico("") == ""


class TestMismoAcelerador:

    def test_codigo_corto_contra_nombre_historico(self):
        assert mismo_acelerador("IX", "Clinac ix") is True
        assert mismo_acelerador("Hc", "Halcyon") is True
        assert mismo_acelerador("Seiscientos", "Clinac 600") is True

    def test_aceleradores_distintos(self):
        assert mismo_acelerador("Clinac 600", "Halcyon") is False
        assert mismo_acelerador("IX", "Seiscientos") is False

    def test_variante_desconocida_no_coincide_por_accidente(self):
        assert mismo_acelerador("Tomógrafo", "Halcyon") is False


class TestVocabularioCompleto:
    """Ancla contra corrimiento silencioso del vocabulario real (producción,
    verificado 2026-07-22): controles.equipo = {Clinac 600, Clinac ix,
    Halcyon, Tomógrafo}; calculadora = {IX, Hc, Seiscientos}."""

    def test_todos_los_valores_destino_son_los_tres_esperados(self):
        assert set(NOMBRES_CANONICOS.values()) == {
            "Clinac 600", "Clinac iX", "Halcyon"}
