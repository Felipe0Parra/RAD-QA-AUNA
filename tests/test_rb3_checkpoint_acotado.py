"""RB.3 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-150): el cierre de un usuario no detiene los guardados de los demas.

Medido en M6 (E2): `closeEvent` hacia `PRAGMA wal_checkpoint(TRUNCATE)` con la espera general de la conexion (30 s). Ese checkpoint, mientras
espera a que otro termine una operacion abierta, RETIENE el turno de escritura: nadie puede guardar. 30.07 s de espera del que cierra, un guardado
detenido 30.08 s y cuatro guardados con la espera de QtSql (5 s) fallando con `database is locked`. Ocurre en cada cierre, haya o no respaldo.

Contrato nuevo: `checkpoint_wal(con, espera_ms=None)`. Con un valor, el checkpoint espera como mucho esos milisegundos y la espera de la conexion
vuelve a su valor anterior (tambien si el checkpoint lanza); sin el, exactamente como antes (el respaldo previo a una migracion, F1).
`closeEvent` pasa `ESPERA_CHECKPOINT_AL_CERRAR_MS` (500 ms).

Va DESPUES de RB.1 a proposito: un checkpoint a medias deja el `.db` sin su `-wal` danado si se copia como archivo (E5 de M6); con la copia por la
API de SQLite (RB.1) la copia sigue integra y completa. La ultima clase de pruebas lo comprueba.

Los lectores y escritores de las pruebas de concurrencia son PROCESOS o hilos con conexiones propias de la MISMA biblioteca SQLite (la de Python):
en Linux, la de Python y la de Qt dentro de un mismo proceso no se ven los bloqueos entre si.
"""
import ast
import contextlib
import inspect
import os
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time

import pytest

from data.ManejoDatos import conection as conection_mod
from data.ManejoDatos.conection import ESPERA_CHECKPOINT_AL_CERRAR_MS, checkpoint_wal
from services.respaldo import respaldar_bd


# ----------------------------------------------------------------------------------------------------------- ayudas
def _bd_wal(tmp_path, filas=3000):
    """Base en modo WAL con el autocheckpoint apagado; devuelve (ruta, conexion de ESCRITURA abierta)."""
    origen = str(tmp_path / "BaseDatosQA.db")
    con = sqlite3.connect(origen)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i}" * 20,) for i in range(filas)])
    con.commit()
    return origen, con


def _confirmar_mas_filas(con, lotes=5):
    for lote in range(lotes):
        con.executemany("UPDATE datos SET valor = ? WHERE id = ?", [(f"nuevo {lote} {i}" * 20, i + 1) for i in range(0, 3000, 3)])
        con.commit()
    con.execute("INSERT INTO datos (valor) VALUES ('ULTIMA FILA CONFIRMADA')")
    con.commit()
    return con.execute("SELECT COUNT(*) FROM datos").fetchone()[0]


_LECTOR = r'''
import sqlite3, sys
c = sqlite3.connect(sys.argv[1], timeout=30, isolation_level=None)
c.execute("BEGIN")
cur = c.execute("SELECT id, valor FROM datos")
cur.fetchone()
print("listo", flush=True)
sys.stdin.read()
'''


@contextlib.contextmanager
def _lector_a_medio_leer(origen):
    """Otro PROCESO con una consulta a medio leer: retiene su foto vieja y no deja que el checkpoint termine."""
    p = subprocess.Popen([sys.executable, "-c", _LECTOR, origen], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "listo"
        yield p
    finally:
        p.stdin.close()
        p.wait(timeout=15)


class _Escritor(threading.Thread):
    """Otro equipo que guarda con 1 s de espera (mas que los 5 s de QtSql seria irreal): intenta una escritura cada 10 ms."""

    def __init__(self, ruta, timeout_s=1.0):
        super().__init__(daemon=True)
        self.ruta, self.timeout_s = ruta, timeout_s
        self.parar = threading.Event()
        self.listo = threading.Event()
        self.latencias, self.fallos = [], []

    def run(self):
        con = sqlite3.connect(self.ruta, timeout=self.timeout_s, isolation_level=None)
        self.listo.set()
        while not self.parar.is_set():
            inicio = time.monotonic()
            try:
                con.execute("INSERT INTO datos (valor) VALUES ('guardado de otro equipo')")
            except sqlite3.OperationalError as ex:
                self.fallos.append(str(ex))
            self.latencias.append(time.monotonic() - inicio)
            time.sleep(0.01)
        con.close()


def _cierre_con_otro_guardando(origen, con_cierre, espera_ms):
    """Cierra (checkpoint) mientras otro equipo guarda; devuelve (segundos del checkpoint, escritor)."""
    escritor = _Escritor(origen)
    escritor.start()
    assert escritor.listo.wait(10)
    time.sleep(0.05)
    inicio = time.monotonic()
    if espera_ms is None:
        checkpoint_wal(con_cierre)
    else:
        checkpoint_wal(con_cierre, espera_ms=espera_ms)
    duracion = time.monotonic() - inicio
    time.sleep(0.2)
    escritor.parar.set()
    escritor.join(15)
    return duracion, escritor


class _Cursor:
    def __init__(self, filas):
        self._filas = filas

    def fetchone(self):
        return self._filas[0]


class _ConFalsa:
    """Una conexion que registra lo que se le pide y puede hacer fallar el checkpoint."""

    def __init__(self, falla=False, espera=30000):
        self.sentencias, self.espera, self.falla = [], espera, falla

    def execute(self, sql):
        self.sentencias.append(sql)
        if sql == "PRAGMA busy_timeout":
            return _Cursor([(self.espera,)])
        if sql.startswith("PRAGMA busy_timeout="):
            self.espera = int(sql.split("=")[1])
            return _Cursor([(self.espera,)])
        if "wal_checkpoint" in sql and self.falla:
            raise sqlite3.OperationalError("fallo simulado del checkpoint")
        return _Cursor([(0, 0, 0)])


# ------------------------------------------------------------------------------------- el checkpoint acotado
class TestElCheckpointAcotado:
    def test_vuelve_pronto_y_el_que_guarda_no_falla(self, tmp_path):
        """E4 de M6 en pequeño: un lector (otro proceso) deja el checkpoint a medias; con `espera_ms=200` vuelve en menos de un segundo
        y otro equipo que guarda con 1 s de espera no recibe `database is locked`."""
        origen, con = _bd_wal(tmp_path)
        try:
            con.execute("PRAGMA busy_timeout=3000")                      # la espera general del que cierra (la de la app es de 30 s)
            with _lector_a_medio_leer(origen):
                _confirmar_mas_filas(con)
                duracion, escritor = _cierre_con_otro_guardando(origen, con, espera_ms=200)
        finally:
            con.close()
        assert duracion < 1.0, f"el checkpoint acotado a 200 ms tardo {duracion:.2f} s"
        assert escritor.fallos == [], escritor.fallos
        assert len(escritor.latencias) > 5 and max(escritor.latencias) < 1.0

    def test_control_sin_acotar_el_que_guarda_falla(self, tmp_path):
        """CONTROL (el cierre de HEAD, con la espera de la conexion a 3 s): el mismo escenario hace que el que guarda reciba `database is
        locked`. Si SQLite cambiara y esto dejara de ocurrir, la prueba de arriba dejaria de discriminar y este control lo avisa."""
        origen, con = _bd_wal(tmp_path)
        try:
            con.execute("PRAGMA busy_timeout=3000")
            with _lector_a_medio_leer(origen):
                _confirmar_mas_filas(con)
                duracion, escritor = _cierre_con_otro_guardando(origen, con, espera_ms=None)
        finally:
            con.close()
        assert duracion >= 2.5, f"el checkpoint sin acotar debia esperar la espera de la conexion (3 s); tardo {duracion:.2f} s"
        assert escritor.fallos, "CONTROL: sin acotar, el que guarda debia fallar con `database is locked`; el escenario dejo de discriminar"
        assert any("locked" in f for f in escritor.fallos)

    def test_sin_ningun_lector_el_wal_queda_en_cero_bytes(self, tmp_path):
        """Cerrando sin nadie mas conectado, todo queda igual que hoy: el `.db` completo y el `-wal` vacio (R2)."""
        origen, con = _bd_wal(tmp_path, filas=200)
        try:
            con.execute("INSERT INTO datos (valor) VALUES ('solo en el wal')")
            con.commit()
            assert os.path.getsize(origen + "-wal") > 0
            checkpoint_wal(con, espera_ms=ESPERA_CHECKPOINT_AL_CERRAR_MS)
            assert os.path.getsize(origen + "-wal") == 0
        finally:
            con.close()


# --------------------------------------------------------------------------------- la espera de la conexion
class TestLaEsperaDeLaConexion:
    def test_vuelve_a_su_valor_anterior_en_una_conexion_real(self, tmp_path):
        origen, con = _bd_wal(tmp_path, filas=50)
        try:
            con.execute("PRAGMA busy_timeout=12345")
            checkpoint_wal(con, espera_ms=200)
            assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 12345
        finally:
            con.close()

    def test_vuelve_a_su_valor_anterior_aunque_el_checkpoint_lance(self):
        falsa = _ConFalsa(falla=True, espera=30000)
        checkpoint_wal(falsa, espera_ms=200)                    # no lanza: es best-effort
        assert falsa.espera == 30000
        assert falsa.sentencias[0] == "PRAGMA busy_timeout" and "PRAGMA busy_timeout=200" in falsa.sentencias
        assert falsa.sentencias[-1] == "PRAGMA busy_timeout=30000"

    def test_se_acota_solo_durante_el_checkpoint(self):
        falsa = _ConFalsa(espera=30000)
        checkpoint_wal(falsa, espera_ms=500)
        orden = [s for s in falsa.sentencias if s != "PRAGMA busy_timeout"]
        assert orden == ["PRAGMA busy_timeout=500", "PRAGMA wal_checkpoint(TRUNCATE)", "PRAGMA busy_timeout=30000"]

    def test_sin_espera_ms_no_se_toca_la_espera(self):
        falsa = _ConFalsa(espera=30000)
        checkpoint_wal(falsa)
        assert falsa.sentencias == ["PRAGMA wal_checkpoint(TRUNCATE)"]

    def test_con_conexion_nula_o_cerrada_no_lanza(self, tmp_path):
        checkpoint_wal(None)
        checkpoint_wal(None, espera_ms=500)
        origen, con = _bd_wal(tmp_path, filas=10)
        con.close()
        checkpoint_wal(con, espera_ms=500)                      # una conexion cerrada: best-effort, no lanza

    def test_la_constante_es_de_medio_segundo(self):
        assert ESPERA_CHECKPOINT_AL_CERRAR_MS == 500


# ------------------------------------------------------------------------------------------- el cierre real
class TestElCierreDeLaVentana:
    @staticmethod
    def _closeevent():
        import ui.mainpages as mainpages_mod
        return ast.parse(textwrap.dedent(inspect.getsource(mainpages_mod.MainWindow.closeEvent)))

    def test_close_event_pasa_la_espera_acotada_al_checkpoint(self):
        llamadas = [n for n in ast.walk(self._closeevent()) if isinstance(n, ast.Call)
                    and getattr(n.func, "id", getattr(n.func, "attr", "")) == "checkpoint_wal"]
        assert len(llamadas) == 1
        palabras = {k.arg: k.value for k in llamadas[0].keywords}
        assert "espera_ms" in palabras
        assert isinstance(palabras["espera_ms"], ast.Name) and palabras["espera_ms"].id == "ESPERA_CHECKPOINT_AL_CERRAR_MS"

    def test_el_cierre_real_llama_al_checkpoint_con_500_ms(self, monkeypatch):
        import ui.mainpages as mainpages_mod
        recibido = {}

        class _ConexionFalsa:
            class _instance:
                con = object()

        monkeypatch.setattr(mainpages_mod, "Conexion", _ConexionFalsa)
        monkeypatch.setattr(mainpages_mod, "checkpoint_wal", lambda con, espera_ms=None: recibido.update(con=con, espera_ms=espera_ms))
        monkeypatch.setattr(mainpages_mod, "respaldar_al_cerrar", lambda usuario=None: None)

        class _Evento:
            aceptado = False

            def accept(self):
                self.aceptado = True

        evento = _Evento()
        mainpages_mod.MainWindow.closeEvent(type("VentanaFalsa", (), {"user_id": None})(), evento)
        assert recibido["espera_ms"] == 500 and evento.aceptado


# ----------------------------------------------------------------------------- RB.3 solo es seguro con RB.1
class TestSoloEsSeguroConLaCopiaPorLaApi:
    def test_con_el_checkpoint_a_medias_el_respaldo_del_cierre_sigue_integro_y_completo(self, tmp_path):
        """E4 (checkpoint acotado + API) y no E5 (acotado + copia de archivo, que sale DAÑADA): el respaldo que se hace tras un checkpoint
        que quedo a medias abre, pasa integrity_check y trae todo lo confirmado."""
        origen, con = _bd_wal(tmp_path)
        try:
            with _lector_a_medio_leer(origen):
                total = _confirmar_mas_filas(con)
                checkpoint_wal(con, espera_ms=100)
                a_medias = con.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
                assert os.path.getsize(origen + "-wal") > 0, "el escenario no se armo: el lector debia dejar el WAL sin consolidar"
                control = str(tmp_path / "control_copia_de_archivo.db")
                shutil.copy2(origen, control)
                ruta = respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "respaldos_bd"))
        finally:
            con.close()
        c = sqlite3.connect(control)
        try:
            control_integro = (c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                               and c.execute("SELECT COUNT(*) FROM datos").fetchone()[0] == total)
        except sqlite3.DatabaseError:
            control_integro = False
        finally:
            c.close()
        assert not control_integro, "CONTROL: la copia de archivo ya sale completa; el escenario dejo de discriminar"
        assert ruta is not None
        r = sqlite3.connect(ruta)
        try:
            assert r.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert r.execute("SELECT COUNT(*) FROM datos").fetchone()[0] == total
            assert r.execute("SELECT valor FROM datos ORDER BY id DESC LIMIT 1").fetchone()[0] == "ULTIMA FILA CONFIRMADA"
        finally:
            r.close()
