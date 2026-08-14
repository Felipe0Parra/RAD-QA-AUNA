"""B3.7 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7f): chequeo de consistencia
calculadora_dosimetrica vs dosimetriaMen. Solo reporta, nunca escribe en
dosimetriaMen (el oro transcrito del PTW).
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from services.dosis_service import DosisService
from services.consistencia_dosis import verificar_consistencia, _mes_anio_de_fecha


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)

    con = sqlite3.connect(ruta)
    con.execute("""
        CREATE TABLE controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, equipo TEXT,
            control TEXT, fecha TEXT, user_id TEXT, user_id_f2 TEXT
        )
    """)
    con.execute("""
        CREATE TABLE dosimetriaMen (
            ref INTEGER, val_teo_dosis REAL, val_teo_calidad REAL,
            dosis_ref_cgy_um REAL, energia TEXT, activo INTEGER DEFAULT 1,
            FOREIGN KEY (ref) REFERENCES controles(id)
        )
    """)
    con.commit()
    con.close()

    # calculadora_dosimetrica con el esquema REAL (energia+vigente) via el
    # propio código de producción, no una copia a mano del DDL.
    assert DosisService.crear_tabla() is True

    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


def _controles(ruta, equipo, fecha, control="Mensual"):
    con = sqlite3.connect(ruta)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _dosimetriamen(ruta, ref, energia, dosis_ref_cgy_um):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO dosimetriaMen (ref, energia, dosis_ref_cgy_um) VALUES (?, ?, ?)",
        (ref, energia, dosis_ref_cgy_um))
    con.commit()
    con.close()


def _calculo_vigente(acelerador, energia, fecha, dosis_maxima_gy_um):
    assert DosisService.guardar_datos({
        "Fecha": fecha, "Acelerador": acelerador, "energia": energia,
        "dosis_maxima": str(dosis_maxima_gy_um),
    }) is True


class TestMesAnioDeFecha:

    def test_formato_mensual(self):
        assert _mes_anio_de_fecha("07/2026") == (7, 2026)

    def test_formato_completo(self):
        assert _mes_anio_de_fecha("14/12/2025") == (12, 2025)

    def test_vacio_o_invalido_no_lanza(self):
        assert _mes_anio_de_fecha("") == (None, None)
        assert _mes_anio_de_fecha(None) == (None, None)
        assert _mes_anio_de_fecha("no-es-una-fecha") == (None, None)


class TestVerificarConsistencia:

    def test_dentro_de_tolerancia(self, bd_temporal):
        ref = _controles(bd_temporal, "Clinac ix", "07/2026")  # minúscula real
        _dosimetriamen(bd_temporal, ref, "6mv", 1.010)
        _calculo_vigente("Clinac iX", "6mv", "05/07/2026", 0.0101)  # *100 = 1.010

        resultados = verificar_consistencia(mes=7, anio=2026)

        assert len(resultados) == 1
        r = resultados[0]
        assert r["acelerador"] == "Clinac iX"  # normalizado, aunque venía "Clinac ix"
        assert r["dosis_calculadora_cgy_um"] == pytest.approx(1.01)
        assert r["dentro_de_tolerancia"] is True

    def test_fuera_de_tolerancia(self, bd_temporal):
        ref = _controles(bd_temporal, "Clinac ix", "07/2026")
        _dosimetriamen(bd_temporal, ref, "6mv", 1.50)
        _calculo_vigente("Clinac iX", "6mv", "05/07/2026", 0.0101)  # *100 = 1.01

        resultados = verificar_consistencia(mes=7, anio=2026)

        assert resultados[0]["dentro_de_tolerancia"] is False
        assert resultados[0]["discrepancia_pct"] > 0.10

    def test_sin_vigente_en_calculadora_no_compara_pero_reporta(self, bd_temporal):
        ref = _controles(bd_temporal, "Halcyon", "08/2026")
        _dosimetriamen(bd_temporal, ref, "15mev", 1.02)
        # sin ningún guardado en calculadora_dosimetrica para esa clave

        resultados = verificar_consistencia(mes=8, anio=2026)

        assert len(resultados) == 1
        assert resultados[0]["dosis_calculadora_cgy_um"] is None
        assert resultados[0]["dentro_de_tolerancia"] is None

    def test_energia_nula_se_excluye(self, bd_temporal):
        ref = _controles(bd_temporal, "Clinac 600", "09/2026")
        _dosimetriamen(bd_temporal, ref, None, 1.0)

        resultados = verificar_consistencia(mes=9, anio=2026)
        assert resultados == []

    def test_filtra_por_mes_y_anio(self, bd_temporal):
        ref_julio = _controles(bd_temporal, "Clinac ix", "07/2026")
        _dosimetriamen(bd_temporal, ref_julio, "6mv", 1.0)
        ref_agosto = _controles(bd_temporal, "Clinac ix", "08/2026")
        _dosimetriamen(bd_temporal, ref_agosto, "6mv", 1.0)

        resultados = verificar_consistencia(mes=7, anio=2026)

        assert len(resultados) == 1
        assert resultados[0]["mes"] == 7

    def test_sin_filtro_trae_todo_el_historico(self, bd_temporal):
        ref_julio = _controles(bd_temporal, "Clinac ix", "07/2026")
        _dosimetriamen(bd_temporal, ref_julio, "6mv", 1.0)
        ref_agosto = _controles(bd_temporal, "Clinac ix", "08/2026")
        _dosimetriamen(bd_temporal, ref_agosto, "15mv", 1.0)

        resultados = verificar_consistencia()

        assert {r["mes"] for r in resultados} == {7, 8}

    def test_nunca_escribe_en_dosimetriamen(self, bd_temporal):
        ref = _controles(bd_temporal, "Clinac ix", "07/2026")
        _dosimetriamen(bd_temporal, ref, "6mv", 1.50)  # a propósito, fuera de tolerancia
        _calculo_vigente("Clinac iX", "6mv", "05/07/2026", 0.0101)

        con = sqlite3.connect(bd_temporal)
        antes = con.execute("SELECT * FROM dosimetriaMen").fetchall()
        con.close()

        verificar_consistencia(mes=7, anio=2026)

        con = sqlite3.connect(bd_temporal)
        despues = con.execute("SELECT * FROM dosimetriaMen").fetchall()
        con.close()

        assert antes == despues, "verificar_consistencia jamas debe modificar dosimetriaMen"
