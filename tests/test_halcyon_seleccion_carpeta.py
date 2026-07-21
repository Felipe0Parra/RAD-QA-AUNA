"""J1 (PLAN_HALCYON_SELECCION_CARPETA_21-07): Halcyon elige la carpeta MPC
correcta por COMPLETITUD, no por la más tardía.

Antes de esta tarea, `addInfo` se quedaba con la carpeta de hora máxima entre
las de una fecha. Eso falla cuando la corrida completa NO es la última
cronológicamente -- confirmado con carpetas reales del 2026-06-27: la
completa es `...-11-29-43-0002` (163 archivos) pero existe una posterior
`...-11-39-45-0000` que es una corrida ABORTADA (solo trae Check.xml, sin
Results.csv). El código viejo elegía la abortada -> FileNotFoundError.

Marcador de completitud (confirmado con carpetas reales, ver
PLAN_HALCYON_SELECCION_CARPETA_21-07.md §2.1): Results.csv existe Y tiene al
menos una fila de datos además de la cabecera. Abortada -> no existe
Results.csv. Parcial -> Results.csv solo con cabecera. Completa -> cabecera +
filas de datos reales.

Todo esto con carpetas SINTÉTICAS en tmp_path -- no las carpetas reales de
~124 MB con imágenes .xim, que la lógica de selección no necesita leer.
"""
import pytest

from data.ManejoDatos.obtenerDatosHalcyon import (
    _results_csv_tiene_datos,
    carpetas_mpc_de_fecha,
    seleccionar_carpeta_mpc,
)

HEADER = "Name [Unit], Value, Threshold, Evaluation Result\n"
FILAS_DATOS = (
    "IsoCenterGroup/IsoCenterSize [mm], 0.67, 0.9, Pass\n"
    "BeamOutputGroup/BeamOutputChange [%], 0.3, 2.0, Pass\n"
)


def _crear_carpeta(base, nombre, estado):
    """estado: 'completa' | 'parcial' | 'abortada'."""
    carpeta = base / nombre
    carpeta.mkdir()
    if estado == "completa":
        (carpeta / "Results.csv").write_text(HEADER + FILAS_DATOS, encoding="utf-8")
    elif estado == "parcial":
        (carpeta / "Results.csv").write_text(HEADER, encoding="utf-8")
    elif estado == "abortada":
        (carpeta / "Check.xml").write_text("<Check/>", encoding="utf-8")
    else:
        raise ValueError(estado)
    return str(carpeta)


class TestResultsCsvTieneDatos:
    def test_completa_tiene_datos(self, tmp_path):
        c = _crear_carpeta(tmp_path, "carpeta_completa", "completa")
        assert _results_csv_tiene_datos(c) is True

    def test_parcial_solo_cabecera_no_tiene_datos(self, tmp_path):
        c = _crear_carpeta(tmp_path, "carpeta_parcial", "parcial")
        assert _results_csv_tiene_datos(c) is False

    def test_abortada_sin_results_csv_no_tiene_datos(self, tmp_path):
        c = _crear_carpeta(tmp_path, "carpeta_abortada", "abortada")
        assert _results_csv_tiene_datos(c) is False

    def test_carpeta_inexistente_no_lanza(self, tmp_path):
        assert _results_csv_tiene_datos(str(tmp_path / "no_existe")) is False


class TestCarpetasMpcDeFechaDiscriminaPorDiaPrimero:
    """Pedido explícito del físico: agrupar/discriminar por día ANTES de
    mirar completitud. Si esto fallara, una corrida de OTRO día podría
    filtrarse como candidata de la fecha pedida."""

    def test_solo_devuelve_carpetas_de_la_fecha_pedida(self, tmp_path):
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-06-27-11-29-43-0002-GeometryCheckTemplate6xFFFMVkV",
            "completa",
        )
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-06-28-09-00-00-0000-GeometryCheckTemplate6xFFFMVkV",
            "completa",
        )
        candidatas_27 = carpetas_mpc_de_fecha(str(tmp_path), "2026-06-27")
        candidatas_28 = carpetas_mpc_de_fecha(str(tmp_path), "2026-06-28")
        assert len(candidatas_27) == 1 and "2026-06-27" in candidatas_27[0]
        assert len(candidatas_28) == 1 and "2026-06-28" in candidatas_28[0]

    def test_ordena_de_mas_antigua_a_mas_reciente(self, tmp_path):
        tardia = _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-06-27-11-39-45-0000-GeometryCheckTemplate6xFFFMVkV",
            "abortada",
        )
        temprana = _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-06-27-10-25-48-0000-GeometryCheckTemplate6xFFFMVkV",
            "parcial",
        )
        assert carpetas_mpc_de_fecha(str(tmp_path), "2026-06-27") == [temprana, tardia]

    def test_ignora_archivos_sueltos_que_no_son_carpetas(self, tmp_path):
        (tmp_path / "HAL-TRT-SN1161-2026-06-27-11-29-43-0002.txt").write_text("x")
        assert carpetas_mpc_de_fecha(str(tmp_path), "2026-06-27") == []

    def test_ruta_base_inexistente_lanza(self, tmp_path):
        """A diferencia de seleccionar_carpeta_mpc, esta función SÍ deja
        propagar el error de listar -- addInfo lo usa para distinguir "red
        caída" de "no hay corrida completa" y mostrar el diálogo correcto."""
        with pytest.raises(OSError):
            carpetas_mpc_de_fecha(str(tmp_path / "no_existe"), "2026-07-01")


class TestSeleccionarCarpetaMpc:
    def test_regresion_exacta_2026_06_27_elige_completa_no_la_abortada_posterior(self, tmp_path):
        """Caso real que disparó el bug: la completa (...11-29-43-0002)
        queda ANTES cronológicamente que una abortada (...11-39-45-0000). El
        código viejo (máxima hora) elegía la abortada -- FileNotFoundError."""
        completa = _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-06-27-11-29-43-0002-GeometryCheckTemplate6xFFFMVkV",
            "completa",
        )
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-06-27-11-39-45-0000-GeometryCheckTemplate6xFFFMVkV",
            "abortada",
        )
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-06-27-10-25-48-0000-GeometryCheckTemplate6xFFFMVkV",
            "parcial",
        )
        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-06-27") == completa

    def test_solo_parciales_devuelve_none(self, tmp_path):
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-01-05-02-32-0000-GeometryCheckTemplate6xFFFMVkV",
            "parcial",
        )
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-01-05-07-10-0000-GeometryCheckTemplate6xFFFMVkV",
            "parcial",
        )
        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-01") is None

    def test_varias_completas_el_mismo_dia_elige_la_mas_reciente(self, tmp_path):
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-05-06-00-00-0000-GeometryCheckTemplate6xFFFMVkV",
            "completa",
        )
        mas_reciente = _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-05-14-00-00-0000-GeometryCheckTemplate6xFFFMVkV",
            "completa",
        )
        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-05") == mas_reciente

    def test_completa_en_medio_de_la_secuencia_se_elige_igual(self, tmp_path):
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-01-05-02-32-0000-GeometryCheckTemplate6xFFFMVkV",
            "parcial",
        )
        completa = _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-01-05-19-31-0000-GeometryCheckTemplate6xFFFMVkV",
            "completa",
        )
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-01-05-30-00-0001-GeometryCheckTemplate6xFFFMVkV",
            "abortada",
        )
        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-01") == completa

    def test_ruta_inexistente_devuelve_none_sin_lanzar(self, tmp_path):
        assert seleccionar_carpeta_mpc(str(tmp_path / "no_existe"), "2026-07-01") is None

    def test_carpeta_vacia_devuelve_none_sin_lanzar(self, tmp_path):
        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-01") is None

    def test_fecha_sin_ninguna_carpeta_asociada_devuelve_none(self, tmp_path):
        _crear_carpeta(
            tmp_path,
            "HAL-TRT-SN1161-2026-07-05-06-00-00-0000-GeometryCheckTemplate6xFFFMVkV",
            "completa",
        )
        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-01-01") is None
