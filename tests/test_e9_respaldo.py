"""E9 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §17): el respaldo al cerrar
existe de verdad.

Antes de E9, `MainWindow.closeEvent` imprimía "Guardando datos o haciendo
respaldo..." con la llamada comentada: la app ANUNCIABA un respaldo que no
hacía. Esta suite fija el contrato nuevo:

- la copia es una BD SQLite válida y COMPLETA (incluye lo que vivía solo en
  el -wal: desde RB.1 la API de respaldo de SQLite lo lee a través del -wal,
  haya o no un checkpoint antes);
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
    NOMBRE_LEEME_RESTAURAR,
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
        """Una fila commiteada SOLO en el -wal (autocheckpoint apagado, técnica
        R2/M1) aparece en la copia con y sin checkpoint. Antes de RB.1 (05-10-2026)
        la copia era del archivo `.db` y sin checkpoint PERDÍA la fila (por eso
        entonces `closeEvent` hacía el checkpoint primero); desde RB.1 la copia se
        hace con la API de respaldo de SQLite, que da una foto consistente de lo
        confirmado aunque el checkpoint no haya corrido -- el orden del cierre no
        sostiene la integridad de la copia (RS.3 lo invirtió: respaldo y después
        checkpoint)."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen, filas=2)

        con = sqlite3.connect(origen)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_autocheckpoint=0")
        con.execute("INSERT INTO datos (valor) VALUES ('solo en el wal')")
        con.commit()
        try:
            assert os.path.getsize(origen + "-wal") > 0

            # Sin checkpoint: RB.1 -- la copia por la API trae igual la fila que
            # vive solo en el -wal (con la copia de archivo de E9 traía 2).
            sin_checkpoint = respaldar_bd(ruta_origen=origen,
                                          carpeta_destino=str(tmp_path / "sin_ckpt"))
            assert sin_checkpoint is not None
            assert _contar_filas(sin_checkpoint) == 3

            # Con checkpoint antes (el orden que tenía closeEvent hasta RS.3): copia completa también.
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
        # RS.2: la carpeta lleva ademas el LEEME_RESTAURAR.txt, que no es un respaldo
        assert len([n for n in os.listdir(destino) if n != NOMBRE_LEEME_RESTAURAR]) == 2


class TestRotacion:
    def test_quedan_las_n_mas_recientes(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _crear_bd(origen)
        destino = str(tmp_path / "respaldos")

        creados = [respaldar_bd(ruta_origen=origen, carpeta_destino=destino,
                                max_copias=3) for _ in range(6)]
        assert all(c is not None for c in creados)

        restantes = sorted(n for n in os.listdir(destino) if n != NOMBRE_LEEME_RESTAURAR)      # RS.2: el LEEME no es un respaldo
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
    """El cableado real de `MainWindow.closeEvent`: respaldo PRIMERO,
    checkpoint después (RS.3: antes era al revés), y `event.accept()` pase lo que pase."""

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
        # RB.3: `closeEvent` pasa `espera_ms` (el checkpoint del cierre espera como mucho 500 ms).
        monkeypatch.setattr(mainpages_mod, "checkpoint_wal",
                            lambda con, espera_ms=None: llamadas.append("checkpoint"))
        # RB.2: `closeEvent` pide el respaldo por franja (`respaldar_al_cerrar`), no el respaldo directo.
        monkeypatch.setattr(mainpages_mod, "respaldar_al_cerrar",
                            lambda usuario=None: llamadas.append("respaldo"))
        falso = type("VentanaFalsa", (), {"user_id": None})()
        evento = self._Evento()
        mainpages_mod.MainWindow.closeEvent(falso, evento)
        return evento

    def test_respaldo_antes_del_checkpoint_y_accept(self, monkeypatch):
        """RS.3 (06-10-2026): el orden se INVIRTIO a proposito. El respaldo no depende del checkpoint desde RB.1 (la API de SQLite lee a traves del -wal) y, con el checkpoint antes,
        la fila de auditoria del propio respaldo quedaba solo en el -wal. Ver `tests/test_rs3_el_cierre_respalda_y_despues_integra_el_wal.py`."""
        llamadas = []
        evento = self._cerrar(monkeypatch, llamadas)
        assert llamadas == ["respaldo", "checkpoint"]
        assert evento.aceptado

    def test_el_mensaje_enganoso_ya_no_existe(self):
        """La línea "Guardando datos o haciendo respaldo..." se imprimía con
        el respaldo comentado -- si reaparece sin respaldo real, esto avisa."""
        import inspect
        fuente = inspect.getsource(mainpages_mod.MainWindow.closeEvent)
        assert "Guardando datos o haciendo respaldo" not in fuente
        assert "respaldar_al_cerrar" in fuente
