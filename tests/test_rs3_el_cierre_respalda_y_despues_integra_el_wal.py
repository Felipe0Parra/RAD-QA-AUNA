"""RS.3 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, C3 de la auditoria): el cierre respalda primero y despues integra el `-wal`.

Antes `MainWindow.closeEvent` hacia el checkpoint y DESPUES `respaldar_al_cerrar`: la fila de auditoria del propio respaldo (la constancia de cuando se respaldo de verdad) se escribe al terminar,
asi que quedaba SOLO en el `-wal` (8 272 B tras el cierre real); tras «Inicio» o una caida, copiar solo el `.db` la perdia. V4 midio el orden invertido: el `.db` trae todo y el `-wal` queda en 0 B
(y un `-wal` vacio es inocuo al restaurar, RS.2). El respaldo mismo no cambia de contenido: desde RB.1 se copia con la API de SQLite, que lee a traves del `-wal`.

Sobre el rojo contra el codigo anterior: la prueba del orden y la de la auditoria en el `.db` caen por su aserción (todas usan API que ya existia).
"""
import os
import shutil
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.mainpages as mainpages_mod


class _Evento:
    def __init__(self):
        self.aceptado = False

    def accept(self):
        self.aceptado = True


class _VentanaFalsa:
    user_id = None


@pytest.fixture
def bd_en_su_carpeta(tmp_path, monkeypatch):
    """Una base real (el esquema completo, en modo WAL) en una carpeta propia: la carpeta de respaldos queda a su lado y no en /tmp."""
    carpeta = tmp_path / "equipo"
    carpeta.mkdir()
    ruta = str(carpeta / "BaseDatosQA.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    Conexion()
    Conexion._instance.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) VALUES (?,?,?,?,?,?)", ("rs3", "x", "Cierre RS3", 1, 1, "fisico"))
    Conexion._instance.con.commit()
    yield ruta
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None


def _solo_el_db(ruta, destino):
    """Lo que pasa si alguien copia SOLO el `.db` (sin `-wal` ni `-shm`) y lo abre."""
    copia = os.path.join(destino, "solo_el_db.db")
    shutil.copy2(ruta, copia)
    con = sqlite3.connect(copia)
    try:
        return con.execute("SELECT COUNT(*) FROM audit_log WHERE tabla = 'backup'").fetchone()[0]
    finally:
        con.close()


class TestElOrdenDelCierre:

    def _cerrar(self, monkeypatch, llamadas):
        class _ConexionFalsa:
            class _instance:
                con = object()
        monkeypatch.setattr(mainpages_mod, "Conexion", _ConexionFalsa)
        monkeypatch.setattr(mainpages_mod, "checkpoint_wal", lambda con, espera_ms=None: llamadas.append(("checkpoint", espera_ms)))
        monkeypatch.setattr(mainpages_mod, "respaldar_al_cerrar", lambda usuario=None: llamadas.append(("respaldo", None)))
        evento = _Evento()
        mainpages_mod.MainWindow.closeEvent(_VentanaFalsa(), evento)
        return evento

    def test_primero_el_respaldo_y_despues_el_checkpoint(self, monkeypatch):
        llamadas = []
        evento = self._cerrar(monkeypatch, llamadas)
        assert [n for n, _ in llamadas] == ["respaldo", "checkpoint"] and evento.aceptado

    def test_el_checkpoint_conserva_su_espera_acotada(self, monkeypatch):
        llamadas = []
        self._cerrar(monkeypatch, llamadas)
        assert ("checkpoint", mainpages_mod.ESPERA_CHECKPOINT_AL_CERRAR_MS) in llamadas, "RB.3: el checkpoint del cierre no espera mas de medio segundo"

    def test_si_el_respaldo_lanza_el_checkpoint_se_hace_igual_y_la_excepcion_no_se_traga(self, monkeypatch):
        """Con el orden de antes el checkpoint iba primero y no dependia del respaldo; con el nuevo, un `try/finally` conserva esa garantia. La excepcion (casi inalcanzable: `respaldar_al_cerrar` atrapa todo)
        sigue subiendo: asi llega al registro de errores en vez de esconderse."""
        llamadas = []

        class _ConexionFalsa:
            class _instance:
                con = object()
        monkeypatch.setattr(mainpages_mod, "Conexion", _ConexionFalsa)
        monkeypatch.setattr(mainpages_mod, "checkpoint_wal", lambda con, espera_ms=None: llamadas.append(("checkpoint", espera_ms)))

        def _respaldo_que_lanza(usuario=None):
            llamadas.append(("respaldo", None))
            raise RuntimeError("fallo inesperado del respaldo")
        monkeypatch.setattr(mainpages_mod, "respaldar_al_cerrar", _respaldo_que_lanza)
        with pytest.raises(RuntimeError, match="fallo inesperado del respaldo"):
            mainpages_mod.MainWindow.closeEvent(_VentanaFalsa(), _Evento())
        assert llamadas == [("respaldo", None), ("checkpoint", mainpages_mod.ESPERA_CHECKPOINT_AL_CERRAR_MS)]

    def test_sin_conexion_activa_se_respalda_y_se_cierra(self, monkeypatch):
        llamadas = []
        monkeypatch.setattr(Conexion, "_instance", None)
        monkeypatch.setattr(mainpages_mod, "respaldar_al_cerrar", lambda usuario=None: llamadas.append("respaldo"))
        evento = _Evento()
        mainpages_mod.MainWindow.closeEvent(_VentanaFalsa(), evento)
        assert llamadas == ["respaldo"] and evento.aceptado


class TestTrasElCierreElDbTraeTodoYElWalQuedaVacio:
    """El cierre REAL: la base viva, `respaldar_al_cerrar` y el checkpoint de verdad."""

    def test_la_fila_de_auditoria_del_respaldo_queda_en_el_db_y_el_wal_en_cero_bytes(self, bd_en_su_carpeta, tmp_path):
        evento = _Evento()
        mainpages_mod.MainWindow.closeEvent(_VentanaFalsa(), evento)
        assert evento.aceptado
        wal = bd_en_su_carpeta + "-wal"
        assert not os.path.exists(wal) or os.path.getsize(wal) == 0, f"el -wal deberia quedar vacio, mide {os.path.getsize(wal)} B"
        destino = tmp_path / "copia"
        destino.mkdir()
        assert _solo_el_db(bd_en_su_carpeta, str(destino)) == 1, "copiar solo el .db trae la constancia del respaldo"
        respaldos = os.path.join(os.path.dirname(bd_en_su_carpeta), "respaldos_bd")
        assert [n for n in os.listdir(respaldos) if n.startswith("BaseDatosQA_")], "y el respaldo existe"

    def test_control_con_el_orden_de_antes_la_fila_quedaba_solo_en_el_wal(self, bd_en_su_carpeta, tmp_path):
        """El defecto que se cierra, con el orden VIEJO armado a mano (checkpoint, luego respaldo): el `-wal` conserva la fila y copiar solo el `.db` la pierde. Demuestra que el escenario es real."""
        from services.respaldo import respaldar_al_cerrar
        conection_mod.checkpoint_wal(Conexion._instance.con, espera_ms=500)
        respaldar_al_cerrar()
        wal = bd_en_su_carpeta + "-wal"
        assert os.path.exists(wal) and os.path.getsize(wal) > 0, "con el orden viejo el -wal queda con contenido"
        destino = tmp_path / "copia"
        destino.mkdir()
        assert _solo_el_db(bd_en_su_carpeta, str(destino)) == 0, "y copiar solo el .db pierde la constancia del respaldo"

    def test_el_respaldo_trae_lo_ultimo_aunque_el_checkpoint_aun_no_haya_corrido(self, bd_en_su_carpeta, tmp_path):
        """Con el respaldo ANTES del checkpoint, el respaldo no puede depender de que el -wal ya este integrado (RB.1): trae la fila que vive solo en el -wal."""
        Conexion._instance.con.execute("PRAGMA wal_autocheckpoint=0")
        Conexion._instance.con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) VALUES (?,?,?,?,?,?)", ("rs3b", "x", "Solo en el wal", 1, 2, "fisico"))
        Conexion._instance.con.commit()
        assert os.path.getsize(bd_en_su_carpeta + "-wal") > 0
        evento = _Evento()
        mainpages_mod.MainWindow.closeEvent(_VentanaFalsa(), evento)
        respaldos = os.path.join(os.path.dirname(bd_en_su_carpeta), "respaldos_bd")
        copia = os.path.join(respaldos, sorted(n for n in os.listdir(respaldos) if n.startswith("BaseDatosQA_"))[-1])
        con = sqlite3.connect(copia)
        try:
            assert con.execute("SELECT COUNT(*) FROM users WHERE user = 'rs3b'").fetchone()[0] == 1
        finally:
            con.close()


def test_los_comentarios_de_cierre_no_afirman_el_orden_viejo():
    """El docstring de `respaldo.py` y el comentario de `closeEvent` decian «checkpoint PRIMERO, respaldo despues»: ya no."""
    import inspect
    import services.respaldo as respaldo
    for texto in (respaldo.__doc__, inspect.getsource(mainpages_mod.MainWindow.closeEvent)):
        assert "checkpoint_wal()` PRIMERO" not in texto and "DESPUÉS del checkpoint para que la copia salga completa" not in texto
