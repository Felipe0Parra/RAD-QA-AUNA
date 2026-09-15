"""F5 (PLAN_F_CIERRE_ESTANDAR_29-07.md): fija por código lo que se verificó a
mano el 2026-07-29 (§1.2/§1.3 del plan) -- que CUALQUIER BD vieja del linaje
de producción, corrida por `scripts/migrar_bd_a_estandar.py`, llega
EXACTAMENTE al mismo estándar estructural que la BD de producción migrada:
0 CASCADE, 57 RESTRICT, los 4 triggers anti-borrado, roles asignados,
`activo` en el bloque de QC, cero `sqlite_sequence` duplicados, y ni una
fila perdida en ninguna tabla.

El número de RESTRICT bajó de 59 (original) a 57: `equipos_anual` (MI5,
DA-44) y `posicionamiento_reposicionamiento` (EB7, DA-50) se retiran del
esquema ANTES de que `_asegurar_fk_on_delete_restrict` convierta nada -- sus
FK con `ON DELETE CASCADE` desaparecen con la tabla, en vez de convertirse.

Corre sobre una COPIA de `AUNA_2026_2/BaseDatosQA(A_Ajustar).db` (nunca el
original -- `skipif` honesto si el archivo no está presente en este
entorno, mismo patrón que test_w2_foreign_keys_produccion_real.py).

Afirma INVARIANTES ESTRUCTURALES, no igualdad de texto del DDL: verificado
que `calculadora_dosimetrica` puede converger con las columnas en ORDEN
distinto entre dos BD igualmente "al estándar" (las 5 columnas añadidas por
ALTER TABLE en fases sucesivas quedan en el orden en que cada archivo las
recibió) -- inofensivo porque el único acceso es por nombre
(`conn.row_factory = sqlite3.Row` en `services/dosis_service.py`). Si algún
día alguien introdujera acceso posicional a esa tabla, sería sensible a
esto -- exactamente la clase de fallo que ya apareció una vez en E7
(`encontrar_columnas`).
"""
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts.migrar_bd_a_estandar import migrar
from services.anulacion import TABLAS_ANULABLES

from _bd_referencia import BD_A_AJUSTAR  # DP-104: fuente única de rutas de BD
RUTA_BD_VIEJA_REAL = str(BD_A_AJUSTAR)


@pytest.fixture
def copia_bd_vieja(tmp_path):
    if not os.path.exists(RUTA_BD_VIEJA_REAL):
        pytest.skip("BaseDatosQA(A_Ajustar).db no está presente en este entorno")
    ruta = str(tmp_path / "vieja_para_migrar.db")
    shutil.copy(RUTA_BD_VIEJA_REAL, ruta)
    return ruta


def _acciones_on_delete(con):
    acciones = {}
    for (t,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"):
        for fk in con.execute(f"PRAGMA foreign_key_list('{t}')"):
            acciones.setdefault(fk[6], []).append(t)
    return acciones


def _violaciones_fk(con):
    return len(con.execute("PRAGMA foreign_key_check").fetchall())


def _duplicados_sqlite_sequence(con):
    return len(con.execute(
        "SELECT name FROM sqlite_sequence GROUP BY name HAVING COUNT(*) > 1"
    ).fetchall())


def _conteo_todas_las_tablas(con):
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'").fetchall()]
    return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}


class TestConvergenciaEstructural:
    def test_migra_a_restrict_sin_ninguna_cascada_restante(self, copia_bd_vieja):
        con_antes = sqlite3.connect(copia_bd_vieja)
        try:
            acciones_antes = _acciones_on_delete(con_antes)
        finally:
            con_antes.close()
        assert "CASCADE" in acciones_antes, (
            "la BD de referencia debe nacer en CASCADE -- si esto falla, "
            "el archivo ya viene migrado y esta prueba no ejercita nada")

        migrar(copia_bd_vieja, aplicar=True)

        con = sqlite3.connect(copia_bd_vieja)
        try:
            acciones = _acciones_on_delete(con)
        finally:
            con.close()
        assert "CASCADE" not in acciones
        assert len(acciones.get("RESTRICT", [])) >= 57

    def test_crea_los_4_triggers_anti_borrado(self, copia_bd_vieja):
        migrar(copia_bd_vieja, aplicar=True)
        con = sqlite3.connect(copia_bd_vieja)
        try:
            triggers = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
        finally:
            con.close()
        assert triggers == {
            "trg_no_borrar_controles", "trg_no_borrar_TipoCalibracion",
            "trg_no_borrar_LinealidadBraquiterapia", "trg_no_borrar_users",
        }

    def test_integrity_check_ok_tras_migrar(self, copia_bd_vieja):
        migrar(copia_bd_vieja, aplicar=True)
        con = sqlite3.connect(copia_bd_vieja)
        try:
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            con.close()

    def test_violaciones_de_fk_no_aumentan(self, copia_bd_vieja):
        """Directriz del físico: el criterio es "no aumentan", nunca "son
        cero" -- los huérfanos heredados no son un objetivo de esta
        migración (son datos, no esquema)."""
        con_antes = sqlite3.connect(copia_bd_vieja)
        try:
            violaciones_antes = _violaciones_fk(con_antes)
        finally:
            con_antes.close()

        migrar(copia_bd_vieja, aplicar=True)

        con = sqlite3.connect(copia_bd_vieja)
        try:
            violaciones_despues = _violaciones_fk(con)
        finally:
            con.close()
        assert violaciones_despues <= violaciones_antes

    def test_sqlite_sequence_sin_duplicados(self, copia_bd_vieja):
        migrar(copia_bd_vieja, aplicar=True)
        con = sqlite3.connect(copia_bd_vieja)
        try:
            assert _duplicados_sqlite_sequence(con) == 0
        finally:
            con.close()

    def test_roles_de_sistema_asignados_a_todos_los_usuarios(self, copia_bd_vieja):
        migrar(copia_bd_vieja, aplicar=True)
        con = sqlite3.connect(copia_bd_vieja)
        try:
            sin_rol = con.execute(
                "SELECT COUNT(*) FROM users WHERE rol_sistema IS NULL").fetchone()[0]
            total = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        finally:
            con.close()
        assert total > 0
        assert sin_rol == 0

    def test_activo_presente_en_las_tablas_anulables(self, copia_bd_vieja):
        migrar(copia_bd_vieja, aplicar=True)
        con = sqlite3.connect(copia_bd_vieja)
        try:
            sin_activo = []
            for tabla in sorted(TABLAS_ANULABLES):
                cols = [c[1] for c in con.execute(
                    f"PRAGMA table_info('{tabla}')").fetchall()]
                if "activo" not in cols:
                    sin_activo.append(tabla)
        finally:
            con.close()
        assert sin_activo == []


class TestNingunaFilaSePierdeEnNingunaTabla:
    def test_censo_completo_no_baja_en_ninguna_tabla(self, copia_bd_vieja):
        con_antes = sqlite3.connect(copia_bd_vieja)
        try:
            censo_antes = _conteo_todas_las_tablas(con_antes)
        finally:
            con_antes.close()

        migrar(copia_bd_vieja, aplicar=True)

        con = sqlite3.connect(copia_bd_vieja)
        try:
            censo_despues = _conteo_todas_las_tablas(con)
        finally:
            con.close()

        bajaron = [(t, censo_antes[t], censo_despues[t]) for t in censo_antes
                   if censo_despues.get(t, 0) < censo_antes[t]]
        assert bajaron == []


class TestIdempotencia:
    def test_segunda_corrida_no_repite_ni_deshace_nada(self, copia_bd_vieja):
        migrar(copia_bd_vieja, aplicar=True)
        con = sqlite3.connect(copia_bd_vieja)
        try:
            esquema_1 = sorted((r[0], r[1] or "") for r in con.execute(
                "SELECT name, sql FROM sqlite_master"))
            censo_1 = _conteo_todas_las_tablas(con)
        finally:
            con.close()

        migrar(copia_bd_vieja, aplicar=True)

        con = sqlite3.connect(copia_bd_vieja)
        try:
            esquema_2 = sorted((r[0], r[1] or "") for r in con.execute(
                "SELECT name, sql FROM sqlite_master"))
            censo_2 = _conteo_todas_las_tablas(con)
        finally:
            con.close()
        assert esquema_1 == esquema_2
        assert censo_1 == censo_2
