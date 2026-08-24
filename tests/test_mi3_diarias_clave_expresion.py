"""MI3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI3): las 4 tablas diarias
(`aceleradorlineal_600`, `aceleradorlineal_ix`, `halcyon`, `braqui`) entran
al contrato de índices/saneamiento con una clave por EXPRESIÓN
(`DATE(date)`), no por columna -- IV3 las dejó fuera a propósito porque
`crear_indices()` (CL1) todavía no sabía validar ni construir una clave que
no fuera una lista de nombres de columna literales.

`_columna_referenciada()` (scripts/indices_bloque_qc.py) es el único punto
que reconoce la forma `FUNC(columna)`; lo usan tanto `crear_indices()`
(MI3) como `scripts/saneamiento_bloque_qc.py::_grupos_duplicados` (MI2/MI3,
mismo criterio, sin una segunda copia).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import (
    CLAVES_INDICE, _columna_referenciada, crear_indices, nombre_indice)
from scripts.saneamiento_bloque_qc import CLAVES_NATURALES, sanear_bloque_qc


DIARIAS = ("aceleradorlineal_600", "aceleradorlineal_ix", "halcyon", "braqui")


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.close()
    Conexion._instance = None
    yield ruta


class TestColumnaReferenciada:

    def test_reconoce_la_expresion_de_las_diarias(self):
        assert _columna_referenciada("DATE(date)") == "date"

    def test_una_columna_literal_no_es_una_expresion(self):
        assert _columna_referenciada("ref") is None
        assert _columna_referenciada("id_energia") is None


class TestClavesDeclaradas:

    def test_las_4_diarias_estan_en_claves_indice(self):
        for tabla in DIARIAS:
            assert CLAVES_INDICE[tabla] == ("DATE(date)",)

    def test_las_4_diarias_estan_en_claves_naturales(self):
        for tabla in DIARIAS:
            assert CLAVES_NATURALES[tabla] == ("DATE(date)",)

    def test_ninguna_clave_de_diaria_es_identidad(self):
        """LF5/DA-47: ninguna de las 56 claves de bloque puede usar
        id/rowid -- una expresión sobre `date` cumple esto trivialmente,
        pero se fija explícito para que un cambio futuro de columna no lo
        rompa en silencio."""
        for tabla in DIARIAS:
            assert not (set(CLAVES_INDICE[tabla]) & {"id", "rowid"})


class TestCrearIndicesSobreExpresion:

    def test_crea_el_indice_de_expresion_para_las_4_diarias(self, bd_temporal):
        resultado = crear_indices(bd_temporal)
        for tabla in DIARIAS:
            assert resultado[tabla] == "creado", f"{tabla}: {resultado[tabla]}"

        con = sqlite3.connect(bd_temporal)
        nombres_reales = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        con.close()
        for tabla in DIARIAS:
            assert nombre_indice(tabla) in nombres_reales

    def test_el_indice_bloquea_dos_fechas_iguales_activas(self, bd_temporal):
        crear_indices(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO braqui (date, activo) VALUES ('2026-01-15', 1)")
        con.commit()
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            con.execute(
                "INSERT INTO braqui (date, activo) VALUES ('2026-01-15', 1)")
        con.close()

    def test_el_indice_no_bloquea_una_fecha_historica(self, bd_temporal):
        crear_indices(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO braqui (date, activo) VALUES ('2026-01-15', 1)")
        con.execute(
            "UPDATE braqui SET activo = 0 WHERE date = '2026-01-15'")
        con.execute(
            "INSERT INTO braqui (date, activo) VALUES ('2026-01-15', 1)")
        con.commit()
        total = con.execute(
            "SELECT COUNT(*) FROM braqui WHERE date = '2026-01-15'").fetchone()[0]
        con.close()
        assert total == 2


class TestSaneamientoDeFechasDuplicadas:

    def test_sanea_fechas_duplicadas_de_una_diaria_real(self, bd_temporal):
        """Reproduce el hallazgo real de §2.8 del plan (aceleradorlineal_ix:
        30 fechas repetidas) a escala mínima: dos filas activas del mismo
        día, gana la más reciente (mayor rowid), la otra queda histórica."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO aceleradorlineal_ix (date, activo) VALUES ('2026-02-10', 1)")
        con.execute(
            "INSERT INTO aceleradorlineal_ix (date, activo) VALUES ('2026-02-10', 1)")
        con.commit()
        con.close()

        anuladas = sanear_bloque_qc(bd_temporal)
        de_ix = [a for a in anuladas if a["tabla"] == "aceleradorlineal_ix"]
        assert len(de_ix) == 1
        assert de_ix[0]["clave"] == {"DATE(date)": "2026-02-10"}

        con = sqlite3.connect(bd_temporal)
        activas = con.execute(
            "SELECT COUNT(*) FROM aceleradorlineal_ix "
            "WHERE date = '2026-02-10' AND activo = 1").fetchone()[0]
        total = con.execute(
            "SELECT COUNT(*) FROM aceleradorlineal_ix "
            "WHERE date = '2026-02-10'").fetchone()[0]
        con.close()
        assert activas == 1, "debe quedar exactamente una fila vigente"
        assert total == 2, "ninguna fila se borra -- la otra queda histórica"

    def test_saneamiento_deja_el_indice_creable_despues(self, bd_temporal):
        """La creación exitosa del índice ES la prueba de que el
        saneamiento funcionó -- mismo criterio que ya vale para las 12
        tablas no-diarias."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO halcyon (date, activo) VALUES ('2026-03-01', 1)")
        con.execute(
            "INSERT INTO halcyon (date, activo) VALUES ('2026-03-01', 1)")
        con.execute(
            "INSERT INTO halcyon (date, activo) VALUES ('2026-03-01', 1)")
        con.commit()
        con.close()

        sanear_bloque_qc(bd_temporal)
        resultado = crear_indices(bd_temporal)
        assert resultado["halcyon"] == "creado", resultado["halcyon"]

    def test_ref_de_auditoria_es_la_fecha_no_none(self, bd_temporal):
        """Las diarias no tienen columna "ref" -- sanear_tabla debe usar el
        único valor de la clave (la fecha) como ref de auditoría, no dejarlo
        en None (services/audit_minimo.py::registrar documenta ref como
        "identificador de la fila/registro (fecha+acelerador, id, etc.)")."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO aceleradorlineal_600 (date, activo) VALUES ('2026-04-05', 1)")
        con.execute(
            "INSERT INTO aceleradorlineal_600 (date, activo) VALUES ('2026-04-05', 1)")
        con.commit()
        con.close()

        anuladas = sanear_bloque_qc(bd_temporal, usuario="Fisico de Prueba")

        con = sqlite3.connect(bd_temporal)
        fila_audit = con.execute(
            "SELECT ref FROM audit_log WHERE tabla = 'aceleradorlineal_600' "
            "ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
        assert fila_audit is not None
        assert fila_audit[0] == "2026-04-05"
