"""EB6 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB6, hallazgo G3 del 24-08):
`TipoCalibracion` (raíz de QC desde E7) no tenía NINGÚN índice declarado --
daba igual mientras `guardar_resultado_CambioFuente` la mutaba en sitio
(`UPDATE ... WHERE id=?`), pero en cuanto `EB2b` la convierta a
anular+insertar, sin índice nada impediría dos generaciones vigentes de la
misma calibración.

Clave elegida: `(DATE(fecha), tipo)` -- el mismo `WHERE` con el que
`guardar_resultado_CambioFuente` ya la busca (`load.py:880-884`). Ensayada
contra las 3 BD de referencia (24-08, sobre copias en el scratchpad de la
sesión, nunca los archivos originales): 13-14 filas cada una, CERO grupos
con más de una fila por esa clave -- el índice se crea sin saneamiento
previo, a diferencia de las 4 tablas de MI2.

`LinealidadBraquiterapia` (la otra raíz sin índice que señaló G3) queda
FUERA de esta tarea a propósito -- ver el comentario en
`scripts/indices_bloque_qc.py::CLAVES_INDICE` y `CLAUDE.md` (DP-40): solo
3 filas en total en las 3 BD de referencia, y sin ningún mecanismo de
reemplazo hoy que un índice deba proteger.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import CLAVES_INDICE, crear_indices, nombre_indice


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.close()
    Conexion._instance = None
    yield ruta


class TestClaveDeclarada:

    def test_tipocalibracion_tiene_clave(self):
        assert CLAVES_INDICE["TipoCalibracion"] == ("DATE(fecha)", "tipo")

    def test_linealidadbraquiterapia_sigue_sin_indice_deliberadamente(self):
        assert "LinealidadBraquiterapia" not in CLAVES_INDICE


class TestCreacionDelIndice:

    def test_se_crea_sobre_bd_vacia(self, bd_temporal):
        resultado = crear_indices(bd_temporal)
        assert resultado["TipoCalibracion"] == "creado"

        con = sqlite3.connect(bd_temporal)
        nombres = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        con.close()
        assert nombre_indice("TipoCalibracion") in nombres

    def test_rechaza_dos_calibraciones_vigentes_mismo_dia_y_tipo(self, bd_temporal):
        crear_indices(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
            "VALUES ('2026-06-01 00:00:00', 'HDR', 'A1')")
        con.commit()
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            con.execute(
                "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
                "VALUES ('2026-06-01 10:00:00', 'HDR', 'A2')")
        con.close()

    def test_permite_generacion_anulada_mas_una_vigente(self, bd_temporal):
        """El caso real que EB2b habilitará: anular la generación anterior
        (activo=0) y luego insertar la nueva del mismo día/tipo -- el
        índice parcial (WHERE activo IS NULL OR activo=1) no debe
        rechazarlo."""
        crear_indices(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
            "VALUES ('2026-06-01 00:00:00', 'HDR', 'A1')")
        con.commit()
        con.execute(
            "UPDATE TipoCalibracion SET activo = 0 WHERE serie = 'A1'")
        con.execute(
            "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
            "VALUES ('2026-06-01 10:00:00', 'HDR', 'A2')")
        con.commit()

        filas = con.execute(
            "SELECT serie, activo FROM TipoCalibracion ORDER BY id").fetchall()
        con.close()
        assert filas == [("A1", 0), ("A2", 1)]

    def test_distinto_tipo_mismo_dia_no_choca(self, bd_temporal):
        crear_indices(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
            "VALUES ('2026-06-01 00:00:00', 'HDR', 'A1')")
        con.execute(
            "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
            "VALUES ('2026-06-01 00:00:00', 'LDR', 'B1')")
        con.commit()
        filas = con.execute("SELECT COUNT(*) FROM TipoCalibracion").fetchone()[0]
        con.close()
        assert filas == 2

    def test_fecha_no_iso_no_protege_nada_hallazgo_real(self, bd_temporal):
        """Hallazgo real al escribir estos tests: `SQLite DATE()` solo
        parsea ISO8601 -- sobre `fecha` en formato DD-MM-YYYY (el legado
        que `braq_mensual.py::normalizar_fechas_db` corrige EN CADA
        apertura de la página, DP-32) devuelve NULL, y dos NULL nunca
        colisionan en un índice UNIQUE. El índice de `EB6` solo protege
        de verdad si `fecha` ya está en ISO -- que es lo que la UI viva
        escribe (`self.fecha_cal.dateTime().toString("yyyy-MM-dd HH:mm:ss")`,
        braq_mensual.py:929) y lo que `normalizar_fechas_db` garantiza para
        el legado con cada apertura de la página. Documentado aquí para que
        no se asuma silenciosamente que el índice cubre CUALQUIER formato
        de fecha."""
        crear_indices(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
            "VALUES ('01-06-2026 00:00:00', 'HDR', 'A1')")
        con.commit()
        # NO lanza: DATE('01-06-2026 00:00:00') = NULL, no colisiona.
        con.execute(
            "INSERT INTO TipoCalibracion (fecha, tipo, serie) "
            "VALUES ('01-06-2026 10:00:00', 'HDR', 'A2')")
        con.commit()
        filas = con.execute("SELECT COUNT(*) FROM TipoCalibracion").fetchone()[0]
        con.close()
        assert filas == 2, (
            "confirma el hallazgo: sin normalizar, el índice NO protege -- "
            "por eso EB2b depende de que normalizar_fechas_db ya haya "
            "corrido antes de guardar")
