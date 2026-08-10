"""H2 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.3): la carpeta MPC
del Halcyon se elige por COMPLETITUD primero y, entre las empatadas, por ser
la ÚLTIMA corrida del día.

Petición del jefe de física (2026-08-10), que es la que fija el contrato:

    la prueba puede completarse pero con resultados incorrectos por errores
    del personal -- p.ej. un objeto olvidado en la zona de irradiación que
    genera artefactos -- así que se repite. Quedan DOS carpetas completas y
    la buena es la segunda. Hay que garantizar (1) que la carpeta elegida
    contiene toda la información y (2) que es la última corrida de ese día.

J1 (2026-07-21) ya elegía "la última entre las que tienen datos", pero su
noción de completitud era demasiado débil -- `Results.csv` con >= 1 fila --
y deja pasar las dos formas de carpeta incompleta que produce el MPC:

  * corrida PARCIAL: Results.csv truncado (2 filas en vez de 253).
  * REPUBLICACIÓN: el MPC reescribe el resultado ya cerrado en una carpeta de
    2-13 ficheros, con el Results.csv completo pero SIN las imágenes `.xim`.

Ambas suelen aparecer DESPUÉS de la corrida buena, así que "la última" se las
queda. Verificado sobre el corpus real (52 días importables):

  * 7 días con varias corridas completas de contenido distinto -- repeticiones
    reales. El 2026-07-20 tiene OCHO, con ocho md5 distintos.
  * 2026-07-02 y 2026-07-10 tienen una republicación (Results.csv byte-idéntico
    al de su corrida, 0 imágenes).
  * 5 días con corridas parciales de 2-6 filas; en los 5 la parcial cayó ANTES
    de la buena, así que hoy el orden salva el dato por suerte, no por diseño.

Grado de completitud = `(filas de datos, conserva imágenes)`, máximo del día.
Es relativo a las corridas de ese mismo día: ningún umbral fijo que envejezca
si Varian cambia la plantilla.
"""
import os

import pytest

from data.ManejoDatos.obtenerDatosHalcyon import (
    _contar_filas_datos,
    _tiene_imagenes_adquiridas,
    seleccionar_carpeta_mpc,
)

from _corpus import MPC_HALCYON  # HI-0: fuente única de rutas del corpus

HEADER = "Name [Unit], Value, Threshold, Evaluation Result\n"
FILA = "IsoCenterGroup/IsoCenterSize [mm], 0.67, 0.9, Pass\n"

PREFIJO = "HAL-TRT-SN1161-"
SUFIJO = "-GeometryCheckTemplate6xFFFMVkV"


def _carpeta(base, fecha, hora, *, filas, imagenes, marca=""):
    """Carpeta MPC sintética con la forma real del corpus.

    `filas`: filas de datos del Results.csv (0 = solo cabecera; None = sin
    Results.csv, corrida abortada). `imagenes`: cuántos `.xim` conserva.
    `marca` distingue el CONTENIDO de dos corridas distintas, para poder
    afirmar cuál se eligió.
    """
    nombre = f"{PREFIJO}{fecha}-{hora}-0000{SUFIJO}"
    ruta = base / nombre
    ruta.mkdir()
    if filas is not None:
        cuerpo = "".join(FILA.replace("0.67", f"0.{60 + i}") for i in range(filas))
        (ruta / "Results.csv").write_text(
            HEADER + cuerpo + (f"# {marca}\n" if marca else ""), encoding="utf-8")
    (ruta / "Check.xml").write_text("<Check/>", encoding="utf-8")
    for i in range(imagenes):
        (ruta / f"acquisition_{i}.xim").write_bytes(b"\x00imagen")
    return str(ruta)


class TestCriterio1CompletitudDescartaLasIncompletasPosteriores:
    """Primer criterio: la carpeta elegida debe contener toda la información."""

    def test_parcial_posterior_no_le_gana_a_la_completa(self, tmp_path):
        """EL caso que justifica H2: la corrida buena y, después, una parcial.

        Es el 2026-07-06 del corpus con el orden invertido -- allí la parcial
        (2 filas) cayó antes de la completa y el dato se salvó por suerte.
        """
        completa = _carpeta(tmp_path, "2026-07-06", "05-48-06",
                            filas=253, imagenes=51, marca="buena")
        _carpeta(tmp_path, "2026-07-06", "06-30-00",
                 filas=2, imagenes=2, marca="parcial")

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-06") == completa

    def test_republicacion_posterior_sin_imagenes_no_le_gana(self, tmp_path):
        """Caso real 2026-07-02: la republicación (2 ficheros, 0 `.xim`) llega
        una hora después con el Results.csv completo. Trae el mismo dato, pero
        no la información de la prueba -- el rastro de auditoría debe apuntar
        a la carpeta donde están las imágenes."""
        adquisicion = _carpeta(tmp_path, "2026-07-02", "05-17-44",
                               filas=253, imagenes=50)
        _carpeta(tmp_path, "2026-07-02", "06-26-58", filas=253, imagenes=0)

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-02") == adquisicion

    def test_abortada_posterior_sin_results_csv_no_le_gana(self, tmp_path):
        """Regresión de J1 (2026-06-27), que debe seguir cumpliéndose."""
        completa = _carpeta(tmp_path, "2026-06-27", "11-29-43",
                            filas=253, imagenes=50)
        _carpeta(tmp_path, "2026-06-27", "11-39-45", filas=None, imagenes=0)

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-06-27") == completa

    def test_mas_filas_gana_aunque_la_otra_tenga_imagenes(self, tmp_path):
        """El dato manda sobre las imágenes: una corrida con el juego completo
        de medidas es más completa que una truncada que sí guardó `.xim`."""
        completa = _carpeta(tmp_path, "2026-06-02", "05-53-59",
                            filas=253, imagenes=0)
        _carpeta(tmp_path, "2026-06-02", "05-43-14", filas=6, imagenes=5)

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-06-02") == completa


class TestCriterio2EntreLasCompletasLaUltima:
    """Segundo criterio, el que pidió el jefe: si empatan en completitud, la
    última -- porque la repetición es la que corrigió el error del personal."""

    def test_dos_corridas_completas_elige_la_repeticion(self, tmp_path):
        """Escenario textual del jefe. Caso real 2026-07-21 / 07-31."""
        _carpeta(tmp_path, "2026-07-21", "05-38-27",
                 filas=253, imagenes=51, marca="con-artefactos")
        repeticion = _carpeta(tmp_path, "2026-07-21", "20-12-26",
                              filas=253, imagenes=51, marca="repeticion-buena")

        elegida = seleccionar_carpeta_mpc(str(tmp_path), "2026-07-21")

        assert elegida == repeticion
        assert "repeticion-buena" in open(
            os.path.join(elegida, "Results.csv"), encoding="utf-8").read()

    def test_ocho_corridas_completas_elige_la_ultima(self, tmp_path):
        """Caso real 2026-07-20: ocho corridas completas, ocho contenidos
        distintos. La válida es la de las 21:15:25."""
        horas = ["12-10-32", "12-37-19", "12-59-42", "13-11-17",
                 "13-18-36", "13-28-33", "13-36-06", "21-15-25"]
        carpetas = [_carpeta(tmp_path, "2026-07-20", h, filas=253,
                             imagenes=50, marca=f"corrida-{h}") for h in horas]

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-20") == carpetas[-1]

    def test_la_ultima_elegida_esta_completa_aunque_haya_basura_despues(self, tmp_path):
        """Las dos condiciones a la vez: entre dos completas gana la segunda,
        y las incompletas posteriores no la desplazan."""
        _carpeta(tmp_path, "2026-06-04", "05-49-43", filas=253, imagenes=50)
        repeticion = _carpeta(tmp_path, "2026-06-04", "17-18-32",
                              filas=253, imagenes=51, marca="repeticion")
        _carpeta(tmp_path, "2026-06-04", "17-30-00", filas=2, imagenes=2)
        _carpeta(tmp_path, "2026-06-04", "17-40-00", filas=253, imagenes=0)
        _carpeta(tmp_path, "2026-06-04", "17-50-00", filas=None, imagenes=0)

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-06-04") == repeticion


class TestNoRompeLosCasosQueYaFuncionaban:
    def test_si_ninguna_tiene_imagenes_sigue_eligiendo_la_ultima_con_datos(self, tmp_path):
        """Degradación honesta: si algún día el share purga los `.xim` (pesan
        ~124 MB por corrida), el criterio es relativo, así que todas empatan y
        se conserva el comportamiento de J1 en vez de dejar de importar."""
        _carpeta(tmp_path, "2026-07-13", "10-00-00", filas=253, imagenes=0)
        ultima = _carpeta(tmp_path, "2026-07-13", "15-46-18",
                          filas=253, imagenes=0, marca="ultima")

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-13") == ultima

    def test_un_solo_dia_con_una_sola_corrida_completa(self, tmp_path):
        completa = _carpeta(tmp_path, "2026-06-30", "05-03-30",
                            filas=253, imagenes=51)
        _carpeta(tmp_path, "2026-06-30", "05-00-00", filas=0, imagenes=0)

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-06-30") == completa

    def test_sin_ninguna_corrida_con_datos_devuelve_none(self, tmp_path):
        _carpeta(tmp_path, "2026-06-10", "21-19-13", filas=0, imagenes=0)
        _carpeta(tmp_path, "2026-06-10", "21-21-04", filas=None, imagenes=0)

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-06-10") is None

    def test_no_cruza_fechas(self, tmp_path):
        """La completitud se evalúa DENTRO del día, nunca a través de días."""
        del_dia = _carpeta(tmp_path, "2026-07-08", "05-36-56",
                           filas=253, imagenes=51)
        _carpeta(tmp_path, "2026-07-09", "05-52-56", filas=253, imagenes=50)

        assert seleccionar_carpeta_mpc(str(tmp_path), "2026-07-08") == del_dia


class TestPrimitivas:
    def test_contar_filas_descuenta_la_cabecera(self, tmp_path):
        c = _carpeta(tmp_path, "2026-07-08", "05-36-56", filas=253, imagenes=0)
        assert _contar_filas_datos(c) == 253

    def test_contar_filas_solo_cabecera_es_cero(self, tmp_path):
        c = _carpeta(tmp_path, "2026-07-08", "05-36-56", filas=0, imagenes=0)
        assert _contar_filas_datos(c) == 0

    def test_contar_filas_sin_results_csv_es_cero(self, tmp_path):
        c = _carpeta(tmp_path, "2026-07-08", "05-36-56", filas=None, imagenes=0)
        assert _contar_filas_datos(c) == 0

    def test_contar_filas_carpeta_inexistente_no_lanza(self, tmp_path):
        assert _contar_filas_datos(str(tmp_path / "no_existe")) == 0

    def test_detecta_imagenes(self, tmp_path):
        con = _carpeta(tmp_path, "2026-07-08", "05-36-56", filas=253, imagenes=50)
        sin = _carpeta(tmp_path, "2026-07-08", "06-00-00", filas=253, imagenes=0)
        assert _tiene_imagenes_adquiridas(con) is True
        assert _tiene_imagenes_adquiridas(sin) is False

    def test_imagenes_carpeta_inexistente_no_lanza(self, tmp_path):
        assert _tiene_imagenes_adquiridas(str(tmp_path / "no_existe")) is False


@pytest.mark.skipif(not os.path.isdir(MPC_HALCYON),
                    reason="corpus de reportes MPC del Halcyon no disponible")
class TestContraElCorpusReal:
    """Solo LECTURA del corpus real, y solo de los Results.csv (~20 KB cada
    uno) -- ninguna imagen `.xim` se abre."""

    def test_dia_con_ocho_corridas_completas_elige_la_ultima(self):
        elegida = seleccionar_carpeta_mpc(MPC_HALCYON, "2026-07-20")
        assert elegida is not None
        assert "2026-07-20-21-15-25" in os.path.basename(elegida)

    def test_dia_con_republicacion_elige_la_que_tiene_las_imagenes(self):
        elegida = seleccionar_carpeta_mpc(MPC_HALCYON, "2026-07-02")
        assert elegida is not None
        assert "2026-07-02-05-17-44" in os.path.basename(elegida)
        assert _tiene_imagenes_adquiridas(elegida)

    def test_dia_con_corrida_parcial_elige_la_completa(self):
        elegida = seleccionar_carpeta_mpc(MPC_HALCYON, "2026-07-06")
        assert elegida is not None
        assert "2026-07-06-05-48-06" in os.path.basename(elegida)

    def test_todo_dia_importable_elige_una_carpeta_completa(self):
        """Barrido del corpus entero: la carpeta elegida cada día trae el
        máximo de filas de ese día. Nunca se importa una corrida truncada
        existiendo una completa."""
        import re
        patron = re.compile(r'(\d{4}-\d{2}-\d{2})-\d{2}-\d{2}-\d{2}-\d{4}')
        fechas = {m.group(1) for n in os.listdir(MPC_HALCYON)
                  if (m := patron.search(n))}
        assert len(fechas) > 40, "el corpus debería cubrir decenas de días"

        importables = 0
        for fecha in sorted(fechas):
            elegida = seleccionar_carpeta_mpc(MPC_HALCYON, fecha)
            if elegida is None:
                continue
            importables += 1
            filas_elegida = _contar_filas_datos(elegida)
            from data.ManejoDatos.obtenerDatosHalcyon import carpetas_mpc_de_fecha
            maximo = max(_contar_filas_datos(c)
                         for c in carpetas_mpc_de_fecha(MPC_HALCYON, fecha))
            assert filas_elegida == maximo, (
                f"{fecha}: se eligió una carpeta con {filas_elegida} filas "
                f"existiendo una de {maximo}")
        assert importables > 40
