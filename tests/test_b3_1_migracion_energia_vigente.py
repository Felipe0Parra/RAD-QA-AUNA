"""B3.1 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7): agrega `energia` y
`vigente` a calculadora_dosimetrica sobre una BD de esquema viejo, como
sería cualquier copia de producción desplegada antes de esta fase. Mismo
patrón que TestMigracionColumnaProtocolo (K3) / TestMigracionColumnaR50Pdd
Electrones (E4): idempotente, integrity_check=ok, conteos intactos, filas
preexistentes leen el DEFAULT/NULL esperado sin romper la carga.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from services.dosis_service import DosisService


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


class TestMigracionColumnasEnergiaVigente:

    def test_migracion_idempotente_sobre_esquema_viejo(self, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        con.execute("""
            CREATE TABLE calculadora_dosimetrica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Fecha TEXT, Acelerador TEXT, protocolo_trs398 TEXT DEFAULT '2000',
                r50_medido TEXT, pdd_zref_electrones TEXT
            )
        """)
        con.execute(
            "INSERT INTO calculadora_dosimetrica (Fecha, Acelerador) "
            "VALUES ('01/01/2026', 'Clinac ix')")
        con.commit()
        con.close()

        assert DosisService.crear_tabla() is True
        con = sqlite3.connect(bd_temporal)
        cols_1 = [c[1] for c in con.execute(
            "PRAGMA table_info('calculadora_dosimetrica')").fetchall()]
        assert "energia" in cols_1
        assert "vigente" in cols_1
        assert con.execute(
            "SELECT COUNT(*) FROM calculadora_dosimetrica").fetchone()[0] == 1
        fila = con.execute(
            "SELECT energia, vigente FROM calculadora_dosimetrica").fetchone()
        assert fila == (None, 0)  # energia sin DEFAULT -> NULL; vigente DEFAULT 0
        con.close()

        # Segunda corrida: idempotente, no duplica columnas ni pierde datos.
        assert DosisService.crear_tabla() is True
        con = sqlite3.connect(bd_temporal)
        cols_2 = [c[1] for c in con.execute(
            "PRAGMA table_info('calculadora_dosimetrica')").fetchall()]
        assert cols_2.count("energia") == 1
        assert cols_2.count("vigente") == 1
        assert con.execute(
            "SELECT COUNT(*) FROM calculadora_dosimetrica").fetchone()[0] == 1
        integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
        assert integridad == "ok"
        con.close()

    def test_fila_legacy_real_no_pierde_ningun_valor(self, bd_temporal):
        """Ancla contra la fila real de producción (id=1, 53 columnas,
        verificada 2026-07-22): la migración no debe tocar NINGUNO de sus
        valores existentes, solo agregar las 2 columnas nuevas en NULL/0."""
        con = sqlite3.connect(bd_temporal)
        con.execute("""
            CREATE TABLE calculadora_dosimetrica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Fecha TEXT, Acelerador TEXT, equipo_id INTEGER,
                Modelo_equipo TEXT, Numero_serie TEXT, factor_calibracion TEXT,
                Tamano_campo TEXT, Tipo_de_radiacion TEXT, Tipo_de_escaneo TEXT,
                Tipo_de_medicion TEXT, dosis_maxima TEXT,
                protocolo_trs398 TEXT DEFAULT '2000',
                r50_medido TEXT, pdd_zref_electrones TEXT
            )
        """)
        con.execute("""
            INSERT INTO calculadora_dosimetrica
                (Fecha, Acelerador, Tipo_de_radiacion, Tipo_de_escaneo, Tamano_campo)
            VALUES ('09/04/2026', 'Seiscientos', 'Fotones', 'Pulse scanned', '10x10 cm')
        """)
        con.commit()
        con.close()

        valores_antes = _dump_fila(bd_temporal, excluir=("energia", "vigente"))

        assert DosisService.crear_tabla() is True

        valores_despues = _dump_fila(bd_temporal, excluir=("energia", "vigente"))
        assert valores_antes == valores_despues, (
            "la migración modificó una columna preexistente de la fila legacy")

        con = sqlite3.connect(bd_temporal)
        energia, vigente = con.execute(
            "SELECT energia, vigente FROM calculadora_dosimetrica WHERE id = 1"
        ).fetchone()
        assert energia is None
        assert vigente == 0
        con.close()


def _dump_fila(ruta_db, excluir=()):
    con = sqlite3.connect(ruta_db)
    con.row_factory = sqlite3.Row
    cols = [c[1] for c in con.execute(
        "PRAGMA table_info('calculadora_dosimetrica')").fetchall()
        if c[1] not in excluir]
    fila = con.execute(
        f"SELECT {', '.join(cols)} FROM calculadora_dosimetrica WHERE id = 1"
    ).fetchone()
    con.close()
    return dict(zip(cols, fila))
