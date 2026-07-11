"""Tests del lector de .mcc reescrito (Fase D4.1a, PLAN_FASE_K_D4.md Seccion 3).

Dos capas, mismo patron que test_trs398_excel.py:

1. Fixtures SINTETICOS (.mcc minimos escritos en el momento): deterministas,
   corren en cualquier maquina. Cubren el parseo por SCAN_CURVETYPE (no por
   indice ni nombre de archivo), la agregacion por carpeta con "el MEAS_DATE
   mas reciente gana" a nivel (energia, curve_type) -- no a nivel de archivo
   completo -- y que un archivo roto no tumbe el resto de la carpeta.

2. Validacion OPCIONAL contra el corpus real del fisico (se salta sola con
   skipif si ~/Documents/Archivos_UseApp no esta): confirma que el caso real
   que motivo el diseno (IX/Electrones/Febrero, energia 6mev con un PDD
   repetido en archivo aparte, mas reciente que el PDDCRIN original) se
   resuelve exactamente como se documenta en el modulo.
"""
import os

import pytest

from mcc_PTW_read.mcc_read import (
    ErrorLecturaMCC, agregar_carpeta, leer_mcc, normalizar_energia,
)

CORPUS = os.path.expanduser("~/Documents/Archivos_UseApp/Archivos QA")
FEBRERO_FOTONES = os.path.join(CORPUS, "Febrero", "IX", "Fotones")
FEBRERO_ELECTRONES = os.path.join(CORPUS, "Febrero", "IX", "Electrones")
FEBRERO_600 = os.path.join(CORPUS, "Febrero", "600")
JUNIO_600 = os.path.join(CORPUS, "Junio", "600")


def _bloque_scan(numero, curve_type, energy, modality, meas_date, filas):
    # filas: tuplas de 2 (posicion, valor) o 3 (posicion, valor, referencia) --
    # el formato real trae ambas variantes (ver test_dos_columnas_sin_canal_referencia).
    datos = "\n".join("\t\t\t" + "\t\t".join(str(x) for x in fila) for fila in filas)
    return (
        f"\tBEGIN_SCAN  {numero}\n"
        f"\t\tMEAS_DATE={meas_date}\n"
        f"\t\tMODALITY={modality}\n"
        f"\t\tENERGY={energy}\n"
        f"\t\tSCAN_CURVETYPE={curve_type}\n"
        "\t\tBEGIN_DATA\n"
        f"{datos}\n"
        "\t\tEND_DATA\n"
        f"\tEND_SCAN  {numero}\n"
    )


def _escribir_mcc(tmp_path, nombre, bloques):
    ruta = tmp_path / nombre
    contenido = "BEGIN_SCAN_DATA\n" + "".join(bloques) + "END_SCAN_DATA\n"
    ruta.write_text(contenido)
    return str(ruta)


FILAS_PDD = [("0.00", "6.1990E+00", "292.27E-03"), ("10.00", "9.4380E+00", "296.57E-03")]
FILAS_PERFIL = [("-50.00", "1.20E+00", "290.00E-03"), ("0.00", "6.00E+00", "295.00E-03"),
                ("50.00", "1.19E+00", "291.00E-03")]


class TestNormalizarEnergia:
    def test_fotones(self):
        assert normalizar_energia(6.00, "X") == "6mv"

    def test_electrones(self):
        assert normalizar_energia(9.00, "EL") == "9mev"

    def test_redondea(self):
        assert normalizar_energia(5.98, "X") == "6mv"

    def test_radiacion_desconocida(self):
        with pytest.raises(ValueError):
            normalizar_energia(6.00, "PROTON")

    def test_energia_none(self):
        with pytest.raises(ValueError):
            normalizar_energia(None, "X")


class TestLeerMCCSintetico:
    def test_tres_scans_se_identifican_por_curvetype_no_por_indice(self, tmp_path):
        """El orden en el archivo se invierte a proposito (CROSSPLANE primero,
        PDD al final) para probar que la identificacion es por SCAN_CURVETYPE,
        no por posicion."""
        bloques = [
            _bloque_scan(1, "CROSSPLANE_PROFILE", "6.00", "X",
                         "28-Feb-2026 11:22:30", FILAS_PERFIL),
            _bloque_scan(2, "INPLANE_PROFILE", "6.00", "X",
                         "28-Feb-2026 11:21:02", FILAS_PERFIL),
            _bloque_scan(3, "PDD", "6.00", "X",
                         "28-Feb-2026 11:19:44", FILAS_PDD),
        ]
        ruta = _escribir_mcc(tmp_path, "test.mcc", bloques)

        escaneos = leer_mcc(ruta)

        assert len(escaneos) == 3
        tipos = {e.curve_type for e in escaneos}
        assert tipos == {"PDD", "INPLANE_PROFILE", "CROSSPLANE_PROFILE"}
        pdd = next(e for e in escaneos if e.curve_type == "PDD")
        assert pdd.energia == "6mv"
        assert pdd.posiciones == [0.00, 10.00]
        assert pdd.col2 == [6.1990, 9.4380]
        assert pdd.col3 == [0.29227, 0.29657]

    def test_un_solo_scan_pdd_sin_crin_no_falla(self, tmp_path):
        """Caso real: un CRIN de electrones puede no traer PDD, o viceversa."""
        ruta = _escribir_mcc(tmp_path, "solo_pdd.mcc", [
            _bloque_scan(1, "PDD", "9.00", "EL", "28-Feb-2026 12:07:24", FILAS_PDD)])

        escaneos = leer_mcc(ruta)

        assert len(escaneos) == 1
        assert escaneos[0].energia == "9mev"
        assert escaneos[0].modalidad == "EL"

    def test_dos_columnas_sin_canal_referencia(self, tmp_path):
        """Caso real (600/Junio): algunos archivos traen solo 2 columnas de
        datos (posicion, valor), sin la columna de referencia/monitor. Antes
        se descartaban en silencio (split() != 3 -> continue), dejando el
        escaneo vacio y reventando cualquier calculo posterior."""
        ruta = _escribir_mcc(tmp_path, "dos_columnas.mcc", [
            _bloque_scan(1, "PDD", "6.00", "X", "30-Jun-2026 18:53:59",
                         [("0.00", "1.7626E+00"), ("1.00", "1.8545E+00")])])

        escaneos = leer_mcc(ruta)

        assert len(escaneos) == 1
        assert escaneos[0].posiciones == [0.00, 1.00]
        assert escaneos[0].col2 == [1.7626, 1.8545]
        assert escaneos[0].col3 == []

    def test_scan_sin_curvetype_falla_ruidoso(self, tmp_path):
        contenido = (
            "BEGIN_SCAN_DATA\n\tBEGIN_SCAN  1\n\t\tMEAS_DATE=28-Feb-2026 11:19:44\n"
            "\t\tMODALITY=X\n\t\tENERGY=6.00\n\t\tBEGIN_DATA\n\t\t\t0.00 1.0 0.1\n"
            "\t\tEND_DATA\n\tEND_SCAN  1\nEND_SCAN_DATA\n"
        )
        ruta = tmp_path / "roto.mcc"
        ruta.write_text(contenido)

        with pytest.raises(ErrorLecturaMCC):
            leer_mcc(str(ruta))

    def test_curvetype_desconocido_falla_ruidoso(self, tmp_path):
        ruta = _escribir_mcc(tmp_path, "raro.mcc", [
            _bloque_scan(1, "DIAGONAL_PROFILE", "6.00", "X",
                         "28-Feb-2026 11:19:44", FILAS_PDD)])

        with pytest.raises(ErrorLecturaMCC):
            leer_mcc(ruta)

    def test_archivo_sin_ningun_scan_falla_ruidoso(self, tmp_path):
        ruta = tmp_path / "vacio.mcc"
        ruta.write_text("BEGIN_SCAN_DATA\nEND_SCAN_DATA\n")

        with pytest.raises(ErrorLecturaMCC):
            leer_mcc(str(ruta))


class TestAgregarCarpeta:
    def test_agrupa_por_energia_y_curvetype(self, tmp_path):
        _escribir_mcc(tmp_path, "a.mcc", [
            _bloque_scan(1, "PDD", "6.00", "X", "28-Feb-2026 11:00:00", FILAS_PDD),
            _bloque_scan(2, "INPLANE_PROFILE", "6.00", "X", "28-Feb-2026 11:01:00", FILAS_PERFIL),
        ])
        _escribir_mcc(tmp_path, "b.mcc", [
            _bloque_scan(1, "PDD", "15.00", "X", "28-Feb-2026 11:10:00", FILAS_PDD),
        ])

        resultado = agregar_carpeta(str(tmp_path))

        assert set(resultado["datos"].keys()) == {"6mv", "15mv"}
        assert set(resultado["datos"]["6mv"].keys()) == {"PDD", "INPLANE_PROFILE"}
        assert resultado["errores"] == []

    def test_meas_date_mas_reciente_gana_por_curvetype_no_por_archivo(self, tmp_path):
        """Reproduce el caso real IX/Electrones/Febrero, energia 6mev: un
        archivo con PDD+INPLANE+CROSSPLANE y otro archivo posterior con SOLO
        un PDD repetido (redo). El PDD final debe ser el del archivo nuevo;
        INPLANE/CROSSPLANE deben seguir viniendo del archivo viejo (el unico
        que los tiene) -- la agregacion no puede tratar el archivo b.mcc como
        "gana todo" ni "pierde todo"."""
        _escribir_mcc(tmp_path, "a_pddcrin.mcc", [
            _bloque_scan(1, "PDD", "6.00", "EL", "28-Feb-2026 11:45:15", FILAS_PDD),
            _bloque_scan(2, "INPLANE_PROFILE", "6.00", "EL", "28-Feb-2026 11:46:47", FILAS_PERFIL),
            _bloque_scan(3, "CROSSPLANE_PROFILE", "6.00", "EL", "28-Feb-2026 11:48:28", FILAS_PERFIL),
        ])
        _escribir_mcc(tmp_path, "b_pdd_redo.mcc", [
            _bloque_scan(1, "PDD", "6.00", "EL", "28-Feb-2026 11:56:22",
                         [("0.00", "7.0000E+00", "300.00E-03")]),
        ])

        resultado = agregar_carpeta(str(tmp_path))

        curvas = resultado["datos"]["6mev"]
        assert curvas["PDD"].archivo.endswith("b_pdd_redo.mcc")
        assert curvas["PDD"].col2 == [7.0]
        assert curvas["INPLANE_PROFILE"].archivo.endswith("a_pddcrin.mcc")
        assert curvas["CROSSPLANE_PROFILE"].archivo.endswith("a_pddcrin.mcc")

    def test_archivo_roto_no_tumba_el_resto_de_la_carpeta(self, tmp_path):
        _escribir_mcc(tmp_path, "bueno.mcc", [
            _bloque_scan(1, "PDD", "6.00", "X", "28-Feb-2026 11:00:00", FILAS_PDD)])
        ruta_rota = tmp_path / "malo.mcc"
        ruta_rota.write_text("esto no es un .mcc valido\n")

        resultado = agregar_carpeta(str(tmp_path))

        assert "6mv" in resultado["datos"]
        assert len(resultado["errores"]) == 1
        assert resultado["errores"][0][0].endswith("malo.mcc")

    def test_carpeta_vacia_no_falla(self, tmp_path):
        resultado = agregar_carpeta(str(tmp_path))
        assert resultado == {"datos": {}, "errores": []}


# ── Capa 2: validación opcional contra el corpus real ──────────────────────

@pytest.mark.skipif(not os.path.exists(FEBRERO_FOTONES),
                    reason="corpus real del físico no disponible en esta máquina")
class TestCorpusRealFotonesFebrero:
    def test_energias_repetidas_el_mismo_dia_no_revientan(self):
        """Fotones/Febrero trae 2 archivos de 6mv y 2 de 15mv el mismo dia
        (repeticion real, no sintetica) -- agregar_carpeta debe quedarse con
        uno solo por curve_type, sin lanzar excepcion."""
        resultado = agregar_carpeta(FEBRERO_FOTONES)

        assert resultado["errores"] == []
        assert set(resultado["datos"].keys()) == {"6mv", "15mv"}
        for energia in ("6mv", "15mv"):
            assert set(resultado["datos"][energia].keys()) == {
                "PDD", "INPLANE_PROFILE", "CROSSPLANE_PROFILE"}


@pytest.mark.skipif(not os.path.exists(FEBRERO_ELECTRONES),
                    reason="corpus real del físico no disponible en esta máquina")
class TestCorpusRealElectronesFebrero:
    def test_6mev_pdd_repetido_toma_el_mas_reciente(self):
        """El caso que motivo el diseno de agregar_carpeta (ver docstring del
        modulo): 6mev tiene un PDDCRIN a las 11:45-11:48 y un PDD suelto,
        posterior, a las 11:56. El PDD final debe ser el de las 11:56."""
        resultado = agregar_carpeta(FEBRERO_ELECTRONES)

        curvas = resultado["datos"]["6mev"]
        assert curvas["PDD"].meas_date.strftime("%H:%M:%S") == "11:56:22"
        assert curvas["INPLANE_PROFILE"].meas_date.strftime("%H:%M:%S") == "11:46:47"
        assert curvas["CROSSPLANE_PROFILE"].meas_date.strftime("%H:%M:%S") == "11:48:28"

    def test_todas_las_energias_electrones_presentes(self):
        resultado = agregar_carpeta(FEBRERO_ELECTRONES)
        assert set(resultado["datos"].keys()) >= {"6mev", "9mev", "12mev", "15mev"}


@pytest.mark.skipif(not os.path.exists(FEBRERO_600),
                    reason="corpus real del físico no disponible en esta máquina")
class TestCorpusReal600Febrero:
    def test_unico_archivo_trae_las_tres_curvas(self):
        resultado = agregar_carpeta(FEBRERO_600)

        assert resultado["errores"] == []
        assert set(resultado["datos"].keys()) == {"6mv"}
        assert set(resultado["datos"]["6mv"].keys()) == {
            "PDD", "INPLANE_PROFILE", "CROSSPLANE_PROFILE"}


@pytest.mark.skipif(not os.path.exists(JUNIO_600),
                    reason="corpus real del físico no disponible en esta máquina")
class TestCorpusReal600JunioDosColumnas:
    def test_archivo_de_2_columnas_no_queda_vacio(self):
        """El .mcc real de 600/Junio no trae canal de referencia (2 columnas,
        no 3) -- motivo del fix de leer_mcc. col2 debe traer los datos."""
        resultado = agregar_carpeta(JUNIO_600)

        assert resultado["errores"] == []
        for curva in resultado["datos"]["6mv"].values():
            assert len(curva.col2) > 0
            assert curva.col3 == []
