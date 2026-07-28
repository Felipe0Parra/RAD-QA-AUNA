"""E9 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §17): el respaldo al cerrar
existe de verdad.

Antes de E9, `MainWindow.closeEvent` imprimía "Guardando datos o haciendo
respaldo..." con la llamada comentada: la app ANUNCIABA un respaldo que no
hacía. Esta suite fija el contrato nuevo:

- la copia es una BD SQLite válida y COMPLETA (incluye lo que vivía solo en
  el -wal, gracias al orden checkpoint -> respaldo);
- nombre fechado con rotación (quedan las N más recientes);
- un fallo de respaldo jamás impide cerrar la app;
- el origen sale de `conection.ruta_base_datos()`, no de una constante;
- cada respaldo exitoso queda auditado (guardar/backup) en la BD de origen.
"""

import os
import sqlite3

from data.ManejoDatos import conection as conection_mod
from data.ManejoDatos.conection import checkpoint_wal
from services.respaldo import (
    MAX_RESPALDOS,
    NOMBRE_CARPETA_RESPALDOS,
    carpeta_respaldos,
    respaldar_bd,
)
import ui.mainpages as mainpages_mod


def _crear_bd(ruta, filas=3):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)",
                    [(f"fila {i}",) for i in range(filas)])
    con.commit()
    con.close()


def _contar_filas(ruta, tabla="datos"):
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    finally:
        con.close()


class TestCopiaValidaYCompleta:
    def test_respaldo_incluye_lo_que_vivia_solo_en_el_wal(self, tmp_path):
        """La demostración central del orden checkpoint -> respaldo: una fila
        commiteada SOLO en el -wal (autocheckpoint apagado, técnica R2/M1) no
        aparece en una copia hecha sin checkpoint, y SÍ aparece tras
        `checkpoint_wal()` -- el orden que `closeEvent` garantiza."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen, filas=2)

        con = sqlite3.connect(origen)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_autocheckpoint=0")
        con.execute("INSERT INTO datos (valor) VALUES ('solo en el wal')")
        con.commit()
        try:
            assert os.path.getsize(origen + "-wal") > 0

            # Sin checkpoint: la copia del .db pierde la fila (por esto el
            # respaldo viejo, que corría antes del checkpoint, era defectuoso).
            incompleta = respaldar_bd(ruta_origen=origen,
                                      carpeta_destino=str(tmp_path / "sin_ckpt"))
            assert incompleta is not None
            assert _contar_filas(incompleta) == 2

            # Con checkpoint primero (el orden de closeEvent): copia completa.
            checkpoint_wal(con)
            completa = respaldar_bd(ruta_origen=origen,
                                    carpeta_destino=str(tmp_path / "con_ckpt"))
            assert completa is not None
            assert _contar_filas(completa) == 3
        finally:
            con.close()

        con_copia = sqlite3.connect(completa)
        try:
            assert con_copia.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            con_copia.close()

    def test_dos_respaldos_seguidos_no_se_pisan(self, tmp_path):
        """El defecto 1 del respaldo viejo era el nombre fijo (cada copia
        pisaba la anterior). Dos cierres en el mismo segundo deben producir
        DOS archivos distintos (contador de colisión)."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen)
        destino = str(tmp_path / "respaldos")

        r1 = respaldar_bd(ruta_origen=origen, carpeta_destino=destino)
        r2 = respaldar_bd(ruta_origen=origen, carpeta_destino=destino)

        assert r1 is not None and r2 is not None and r1 != r2
        assert len(os.listdir(destino)) == 2


class TestRotacion:
    def test_quedan_las_n_mas_recientes(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen)
        destino = str(tmp_path / "respaldos")

        creados = [respaldar_bd(ruta_origen=origen, carpeta_destino=destino,
                                max_copias=3) for _ in range(6)]
        assert all(c is not None for c in creados)

        restantes = sorted(os.listdir(destino))
        assert len(restantes) == 3
        # Las que quedan son exactamente las 3 ÚLTIMAS creadas.
        assert restantes == sorted(os.path.basename(c) for c in creados[-3:])

    def test_el_maximo_por_defecto_es_10(self):
        assert MAX_RESPALDOS == 10


class TestFalloAislado:
    def test_destino_no_escribible_no_lanza(self, tmp_path, capsys):
        """Si la carpeta de respaldos no se puede crear (aquí: su ruta está
        ocupada por un ARCHIVO), respaldar_bd avisa y devuelve None -- nunca
        lanza, el cierre de la app no se bloquea."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen)
        bloqueo = tmp_path / "respaldos"
        bloqueo.write_text("no soy una carpeta")

        resultado = respaldar_bd(ruta_origen=origen,
                                 carpeta_destino=str(bloqueo / "sub"))

        assert resultado is None
        assert "no se pudo respaldar" in capsys.readouterr().out

    def test_origen_inexistente_no_lanza(self, tmp_path, capsys):
        resultado = respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"))
        assert resultado is None
        assert "no existe la BD de origen" in capsys.readouterr().out


class TestOrigenDelResolutor:
    def test_sin_argumentos_respalda_la_bd_del_resolutor(self, tmp_path, monkeypatch):
        """El respaldo viejo copiaba desde una ruta de red codificada
        (defecto 3). El nuevo debe salir de `conection.ruta_base_datos()`:
        parchearla y comprobar que se respalda ESA base."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen, filas=5)
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: origen)

        resultado = respaldar_bd()

        assert resultado is not None
        esperada = os.path.join(str(tmp_path), NOMBRE_CARPETA_RESPALDOS)
        assert os.path.dirname(resultado) == esperada
        assert carpeta_respaldos() == esperada
        assert _contar_filas(resultado) == 5


class TestAuditoria:
    def test_respaldo_exitoso_queda_auditado_en_el_origen(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen)

        resultado = respaldar_bd(usuario="Físico de Prueba", ruta_origen=origen,
                                 carpeta_destino=str(tmp_path / "respaldos"))
        assert resultado is not None

        con = sqlite3.connect(origen)
        try:
            fila = con.execute(
                "SELECT usuario, accion, tabla, ref FROM audit_log").fetchone()
        finally:
            con.close()
        assert fila == ("Físico de Prueba", "guardar", "backup",
                        os.path.basename(resultado))

    def test_respaldo_fallido_no_audita(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen)
        bloqueo = tmp_path / "respaldos"
        bloqueo.write_text("no soy una carpeta")

        respaldar_bd(usuario="Físico de Prueba", ruta_origen=origen,
                     carpeta_destino=str(bloqueo / "sub"))

        con = sqlite3.connect(origen)
        try:
            tablas = {t[0] for t in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
        assert "audit_log" not in tablas


class TestCloseEventDeProduccion:
    """El cableado real de `MainWindow.closeEvent`: checkpoint PRIMERO,
    respaldo después, y `event.accept()` pase lo que pase."""

    class _Evento:
        def __init__(self):
            self.aceptado = False

        def accept(self):
            self.aceptado = True

    def _cerrar(self, monkeypatch, llamadas):
        class _ConexionFalsa:
            class _instance:
                con = object()

        monkeypatch.setattr(mainpages_mod, "Conexion", _ConexionFalsa)
        monkeypatch.setattr(mainpages_mod, "checkpoint_wal",
                            lambda con: llamadas.append("checkpoint"))
        monkeypatch.setattr(mainpages_mod, "respaldar_bd",
                            lambda usuario=None: llamadas.append("respaldo"))
        falso = type("VentanaFalsa", (), {"user_id": None})()
        evento = self._Evento()
        mainpages_mod.MainWindow.closeEvent(falso, evento)
        return evento

    def test_checkpoint_antes_del_respaldo_y_accept(self, monkeypatch):
        llamadas = []
        evento = self._cerrar(monkeypatch, llamadas)
        assert llamadas == ["checkpoint", "respaldo"]
        assert evento.aceptado

    def test_el_mensaje_enganoso_ya_no_existe(self):
        """La línea "Guardando datos o haciendo respaldo..." se imprimía con
        el respaldo comentado -- si reaparece sin respaldo real, esto avisa."""
        import inspect
        fuente = inspect.getsource(mainpages_mod.MainWindow.closeEvent)
        assert "Guardando datos o haciendo respaldo" not in fuente
        assert "respaldar_bd" in fuente
