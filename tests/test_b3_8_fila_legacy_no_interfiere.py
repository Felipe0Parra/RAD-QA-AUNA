"""B3.8 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.1): la fila legacy de
calculadora_dosimetrica (id=1, anterior a B3 -- Fecha='09/04/2026',
Acelerador='Seiscientos', energia=NULL, vigente=0 vía el DEFAULT de la
migración B3.1) no interfiere con ninguna de las funciones construidas
desde B3.3 en adelante: no aparece como "vigente" de ninguna energía real,
no estorba al guardar una versión nueva para el mismo acelerador, y B3.7
nunca la toca (no participa de dosimetriaMen).
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from services.dosis_service import DosisService
from services.consistencia_dosis import verificar_consistencia


@pytest.fixture
def bd_con_fila_legacy(monkeypatch):
    """Reproduce el escenario REAL verificado en producción (2026-07-22,
    B3.1): esquema nuevo (energia/vigente ya migrados) con la fila legacy
    ya existente, tal cual quedó tras la migración."""
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)

    assert DosisService.crear_tabla() is True
    con = sqlite3.connect(ruta)
    con.execute("""
        INSERT INTO calculadora_dosimetrica
            (Fecha, Acelerador, Tipo_de_radiacion, Tipo_de_escaneo, Tamano_campo)
        VALUES ('09/04/2026', 'Seiscientos', 'Fotones', 'Pulse scanned', '10x10 cm')
    """)
    con.execute("""
        CREATE TABLE controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, equipo TEXT,
            control TEXT, fecha TEXT, user_id TEXT, user_id_f2 TEXT
        )
    """)
    con.execute("""
        CREATE TABLE dosimetriaMen (
            ref INTEGER, dosis_ref_cgy_um REAL, energia TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id)
        )
    """)
    con.commit()
    con.close()

    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


class TestFilaLegacyQuedaComoSeVerificoEnB31:

    def test_energia_null_vigente_cero(self, bd_con_fila_legacy):
        con = sqlite3.connect(bd_con_fila_legacy)
        fila = con.execute(
            "SELECT energia, vigente FROM calculadora_dosimetrica WHERE id=1"
        ).fetchone()
        con.close()
        assert fila == (None, 0)


class TestNoApareceComoVigenteDeNingunaEnergia:

    @pytest.mark.parametrize("energia", ["6mv", "15mv", "6mev", "9mev", "12mev", "15mev"])
    def test_buscar_vigente_no_la_devuelve(self, bd_con_fila_legacy, energia):
        assert DosisService.buscar_vigente("Clinac 600", energia) is None
        assert DosisService.buscar_vigente("Seiscientos", energia) is None

    def test_buscar_vigente_del_mes_no_la_devuelve(self, bd_con_fila_legacy):
        # la fila legacy es de abril/2026 -- ni siquiera con ESE mes exacto
        # debe aparecer, porque su energia es NULL y nunca matchea `= ?`.
        assert DosisService.buscar_vigente_del_mes("Seiscientos", "6mv", 4, 2026) is None


class TestNoEstorbaAlGuardarVersionNueva:

    def test_nueva_version_del_mismo_acelerador_no_toca_la_legacy(self, bd_con_fila_legacy):
        assert DosisService.guardar_datos({
            "Fecha": "10/07/2026", "Acelerador": "Seiscientos", "energia": "6mv",
            "dosis_maxima": "0.0101",
        }) is True

        con = sqlite3.connect(bd_con_fila_legacy)
        filas = con.execute(
            "SELECT id, energia, vigente FROM calculadora_dosimetrica ORDER BY id"
        ).fetchall()
        con.close()

        assert filas[0] == (1, None, 0), "la fila legacy no debe cambiar"
        assert filas[1][1:] == ("6mv", 1), "la fila nueva sí queda vigente"

    def test_vigente_de_la_nueva_energia_se_encuentra_bien(self, bd_con_fila_legacy):
        DosisService.guardar_datos({
            "Fecha": "10/07/2026", "Acelerador": "Seiscientos", "energia": "6mv",
            "dosis_maxima": "0.0101",
        })
        vigente = DosisService.buscar_vigente("Clinac 600", "6mv")
        assert vigente is not None
        assert vigente["Fecha"] == "10/07/2026"


class TestB37NuncaLaToca:
    """La fila legacy no está enlazada a ningún control (no participa de
    dosimetriaMen) -- verificar_consistencia ni siquiera puede alcanzarla,
    pero se confirma que no genera ruido ni falsos positivos."""

    def test_consistencia_sin_dosimetriamen_no_reporta_nada(self, bd_con_fila_legacy):
        assert verificar_consistencia() == []

    def test_consistencia_de_otra_clave_no_se_confunde_con_la_legacy(
            self, bd_con_fila_legacy):
        con = sqlite3.connect(bd_con_fila_legacy)
        cur = con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
            ("Clinac 600", "Mensual", "04/2026"))
        ref = cur.lastrowid
        con.execute(
            "INSERT INTO dosimetriaMen (ref, energia, dosis_ref_cgy_um) VALUES (?, ?, ?)",
            (ref, "6mv", 1.05))
        con.commit()
        con.close()

        resultados = verificar_consistencia(mes=4, anio=2026)

        assert len(resultados) == 1
        # la legacy (energia=NULL) no puede ser "el vigente" de esta fila
        assert resultados[0]["dosis_calculadora_cgy_um"] is None
        assert resultados[0]["dentro_de_tolerancia"] is None
