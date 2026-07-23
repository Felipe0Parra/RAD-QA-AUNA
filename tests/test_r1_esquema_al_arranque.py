"""R1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): DosisService.crear_tabla()
(que asegura "energia"/"vigente" en calculadora_dosimetrica via ALTER TABLE)
antes solo se llamaba dentro de guardar_datos -- cualquier LECTURA previa
sobre una BD sin migrar (p.ej. el chequeo de duplicado F6b,
buscar_vigente_del_mes, que filtra "energia = ?") reventaba con "no such
column: energia" antes del primer guardado.

Esto es exactamente el síntoma del terminal del físico (2026-07-23,
HANDOFF_BUILD_WINDOWS(23-7-2026).md línea 313): el error y un "Data saved
successfully" conviviendo en la misma corrida -- la migración perezosa se
disparaba recién en el primer guardado.

Reproduce el escenario real: instanciar Conexion() (arranque de la app) SIN
llamar nunca a guardar_datos, y verificar que el esquema YA está completo y
que los buscar_* de lectura no fallan.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.dosis_service import DosisService


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    yield ruta
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None
    for sufijo in ("", "-wal", "-shm"):
        if os.path.exists(ruta + sufijo):
            os.remove(ruta + sufijo)


def _crear_bd_vieja_sin_energia_ni_vigente(ruta):
    """Simula una BD de producción REAL anterior a B3: la tabla
    calculadora_dosimetrica ya existe (con datos), pero sin las columnas
    "energia"/"vigente" que una versión más nueva de la app espera. Sin
    esto, una BD temporal vacía hace que falte la TABLA entera (error "no
    such table"), no la columna -- no reproduce el síntoma real del físico."""
    con = sqlite3.connect(ruta)
    con.execute("""
        CREATE TABLE calculadora_dosimetrica (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT,
            Acelerador TEXT,
            Tipo_de_radiacion TEXT
        )
    """)
    con.execute(
        "INSERT INTO calculadora_dosimetrica (Fecha, Acelerador, Tipo_de_radiacion) "
        "VALUES ('09/04/2026', 'Seiscientos', 'Fotones')")
    con.commit()
    con.close()


class TestEsquemaListoTrasSoloArrancar:

    def test_columnas_energia_y_vigente_existen_sin_guardar_nunca(self, bd_temporal):
        """El arranque (instanciar Conexion(), lo que hace la app al abrir)
        debe dejar el esquema completo -- sin depender de que alguien guarde
        un cálculo primero. BD "vieja" (fila legacy, sin las columnas nuevas),
        igual que la producción real."""
        _crear_bd_vieja_sin_energia_ni_vigente(bd_temporal)

        Conexion()  # arranque, NUNCA se llama a DosisService.guardar_datos

        con = Conexion().conectar()
        cols = [c[1] for c in con.execute(
            "PRAGMA table_info(calculadora_dosimetrica)").fetchall()]
        fila_legacy = con.execute(
            "SELECT Fecha, Acelerador FROM calculadora_dosimetrica").fetchone()
        con.close()

        assert "energia" in cols
        assert "vigente" in cols
        assert "protocolo_trs398" in cols
        # la fila legacy sigue intacta -- migrar no es reescribir datos
        assert fila_legacy == ("09/04/2026", "Seiscientos")

    def test_buscar_vigente_del_mes_no_falla_en_bd_vieja(self, bd_temporal, capsys):
        """Reproduce el síntoma exacto del terminal (línea 313 del handoff):
        el chequeo de duplicado (F6b) es la PRIMERA lectura que toca la
        tabla, antes de cualquier guardado nuevo. Sobre una BD con la fila
        legacy (sin energia/vigente), no debe imprimir 'no such column'."""
        _crear_bd_vieja_sin_energia_ni_vigente(bd_temporal)
        Conexion()

        resultado = DosisService.buscar_vigente_del_mes("Clinac iX", "6mv", 7, 2026)

        salida = capsys.readouterr().out
        assert "no such column" not in salida
        assert resultado is None  # no hay datos para esa clave, pero no crasheó

    def test_buscar_vigente_no_falla_en_bd_vieja(self, bd_temporal, capsys):
        _crear_bd_vieja_sin_energia_ni_vigente(bd_temporal)
        Conexion()
        resultado = DosisService.buscar_vigente("Clinac iX", "6mv")
        salida = capsys.readouterr().out
        assert "no such column" not in salida
        assert resultado is None

    def test_guardar_y_recuperar_funciona_sin_llamada_manual_a_crear_tabla(self, bd_temporal):
        """Con el esquema ya asegurado al arranque, guardar_datos y
        buscar_vigente_del_mes trabajan sobre la misma tabla sin que el
        físico tenga que "activarla" con un primer guardado especial."""
        Conexion()

        ok = DosisService.guardar_datos({
            "Fecha": "29/09/2024", "Acelerador": "Clinac iX",
            "Tipo_de_radiacion": "Electrones", "energia": "6mev",
        })
        assert ok is True

        vigente = DosisService.buscar_vigente_del_mes("Clinac iX", "6mev", 9, 2024)
        assert vigente is not None
        assert vigente["Fecha"] == "29/09/2024"

    def test_migracion_es_idempotente_tras_reiniciar_la_app_varias_veces(self, bd_temporal):
        """Re-arrancar la app (nueva instancia de Conexion, como pasa cada
        vez que el físico abre RAD-QA) no debe fallar ni perder datos ya
        guardados."""
        Conexion()
        DosisService.guardar_datos({
            "Fecha": "01/07/2026", "Acelerador": "Halcyon",
            "Tipo_de_radiacion": "Fotones", "energia": "6mv",
        })

        for _ in range(3):
            Conexion._instance.con.close()
            Conexion._instance = None
            Conexion()  # simula un nuevo arranque de la app

        con = Conexion().conectar()
        n = con.execute(
            "SELECT COUNT(*) FROM calculadora_dosimetrica WHERE Fecha='01/07/2026'"
        ).fetchone()[0]
        con.close()
        assert n == 1
