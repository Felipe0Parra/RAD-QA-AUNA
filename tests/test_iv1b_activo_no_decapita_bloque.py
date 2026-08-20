"""IV1b (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV1b): una tabla ausente no
decapita el resto del bloque al asegurar `activo`.

Hallado auditando IV1 con un subagente Opus (regla de sesión: ningún
obstáculo nuevo se resuelve en silencio). `_asegurar_activo_bloque_qc`
(`data/ManejoDatos/conection.py`) recorría `TABLAS_ANULABLES` con un ÚNICO
`try/except` alrededor de TODO el bucle. `_asegurar_columna` hace `PRAGMA
table_info('tabla')` -- si la tabla no existe, devuelve una lista vacía (no
lanza), así que `_asegurar_columna` intenta igual `ALTER TABLE tabla ADD
COLUMN ...`, que sí lanza `OperationalError: no such table`. Con el
`try/except` envolviendo el bucle entero, esa excepción abortaba TODAS las
tablas alfabéticamente posteriores a la que faltaba, dejándolas sin `activo`
en silencio.

Caso real que lo dispara: `posicionamiento_reposicionamiento` (una de las
tablas del cierre transitivo de PLAN_CONTRATO_COMPLETO_19-08.md, DA-42) no
tiene `CREATE TABLE` en `conection.py` -- no existe en ninguna BD nueva. En
cuanto `TABLAS_ANULABLES` se amplíe (MI1) para incluirla, cualquier BD
temporal de test (o cualquier BD nueva en producción) dispararía esto.

Este test NO espera a que `TABLAS_ANULABLES` se amplíe: reproduce el patrón
con un `TABLAS_ANULABLES` de prueba, monkeypatcheado, que mezcla una tabla
real (`equipos_medicion`) con una inexistente -- así se verifica el arreglo
(`try/except` por tabla en vez de por bucle) antes de que MI1 lo necesite de
verdad.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
import services.anulacion as anulacion_mod
from data.ManejoDatos.conection import Conexion


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _tiene_columna(con, tabla, columna):
    return columna in {c[1] for c in con.execute(f"PRAGMA table_info('{tabla}')")}


class TestUnaTablaAusenteNoDecapitaElResto:

    def test_tabla_alfabeticamente_posterior_a_la_ausente_igual_recibe_activo(
        self, bd_temporal, monkeypatch
    ):
        """`aaa_tabla_inexistente` (ordena ANTES que `equipos_medicion` en
        `sorted()`) no existe -- antes del fix, su fallo abortaba el resto
        del bucle y `equipos_medicion` se quedaba sin `activo`."""
        conexion = Conexion()
        con = conexion.con
        con.execute("ALTER TABLE equipos_medicion DROP COLUMN activo") \
            if _tiene_columna(con, "equipos_medicion", "activo") else None
        con.commit()
        assert not _tiene_columna(con, "equipos_medicion", "activo"), (
            "precondición: equipos_medicion debía empezar sin 'activo' para "
            "esta prueba")

        monkeypatch.setattr(
            anulacion_mod, "TABLAS_ANULABLES",
            frozenset({"aaa_tabla_inexistente", "equipos_medicion", "controles"}),
        )
        conexion._asegurar_activo_bloque_qc()

        assert _tiene_columna(con, "equipos_medicion", "activo"), (
            "equipos_medicion se quedó sin 'activo' porque una tabla "
            "ANTERIOR en el orden alfabético (aaa_tabla_inexistente, que no "
            "existe) abortó el resto del bucle -- exactamente el defecto "
            "que IV1b corrige")

    def test_tabla_ausente_no_revienta_la_llamada(self, bd_temporal, monkeypatch):
        """La llamada entera no debe lanzar, aunque una tabla del inventario
        no exista -- coherente con el resto de `_asegurar_*` al arranque
        (best-effort, nunca bloquea abrir la app)."""
        conexion = Conexion()
        monkeypatch.setattr(
            anulacion_mod, "TABLAS_ANULABLES",
            frozenset({"zzz_tabla_inexistente", "controles"}),
        )
        conexion._asegurar_activo_bloque_qc()  # no debe lanzar

    def test_dos_tablas_reales_alrededor_de_una_inexistente_reciben_activo(
        self, bd_temporal, monkeypatch
    ):
        """Caso más parecido al real: una tabla inexistente en medio del
        orden alfabético, con tablas reales antes Y después."""
        conexion = Conexion()
        con = conexion.con
        for tabla in ("dosimetriaMen", "tamano_campo"):
            if _tiene_columna(con, tabla, "activo"):
                con.execute(f"ALTER TABLE {tabla} DROP COLUMN activo")
        con.commit()

        monkeypatch.setattr(
            anulacion_mod, "TABLAS_ANULABLES",
            frozenset({"dosimetriaMen", "mmm_tabla_inexistente", "tamano_campo", "controles"}),
        )
        conexion._asegurar_activo_bloque_qc()

        assert _tiene_columna(con, "dosimetriaMen", "activo"), (
            "la tabla ANTES de la inexistente (orden alfabético) debía recibir activo")
        assert _tiene_columna(con, "tamano_campo", "activo"), (
            "la tabla DESPUÉS de la inexistente debía recibir activo igual")
