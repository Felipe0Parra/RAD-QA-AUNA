"""R2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): la pregunta del físico fue
"¿cómo garantizo que las rutas sobreviven cualquier configuración o
procedimiento que se realiza en la aplicación, y que no hay pérdida de
información?". Esta suite verifica, con evidencia (no solo lectura de
código), tres invariantes que tienen que sostenerse SIEMPRE:

1. `ruta_base_datos()`/`ruta_datos()` resuelven de forma estable y correcta
   tanto en desarrollo como en el ejecutable congelado (PyInstaller).
2. Los 4 caminos de conexión que coexisten hoy en la app (singleton
   `Conexion().con`, `Conexion().conectar()`, `DosisService._get_connection()`,
   el pool `DatabaseManager`) apuntan SIEMPRE al mismo archivo -- nunca hay
   "split-brain" (dos copias divergentes de la BD, el incidente histórico del
   2026-07-03 que motivó `ruta_base_datos()` en primer lugar).
3. La trampa real de WAL: mover/copiar la BD copiando SOLO el archivo `.db`
   (sin `-wal`/`-shm`) pierde datos si no hubo un checkpoint antes -- y
   `checkpoint_wal()` (R2) lo evita.
"""
import os
import shutil
import sqlite3
import sys
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.dosis_service import DosisService

# El fixture autouse de sesión (tests/conftest.py, HI-1) reemplaza
# conection_mod.ruta_base_datos por un lambda ANTES de que corra el primer
# test -- necesario para aislar la suite de la BD real de desarrollo, pero
# eso mismo hace inalcanzable la función ORIGINAL desde dentro de un test.
# Capturarla aquí, a nivel de módulo, ocurre en la fase de COLECCIÓN (import
# de este archivo), que siempre es anterior a que el fixture de sesión se
# ejecute -- es la única forma de probar la lógica real de resolución de
# rutas (dev vs frozen) en vez de la que ya quedó parcheada por conftest.
_ruta_base_datos_original = conection_mod.ruta_base_datos
_ruta_datos_original = conection_mod.ruta_datos


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


class TestResolucionDeRutaPorEntorno:
    """ruta_base_datos()/ruta_datos() deben resolver de forma predecible en
    los DOS entornos reales en los que corre la app: desarrollo (python
    main.py) y congelado (RAD-QA.exe, PyInstaller)."""

    def test_dev_ancla_a_la_raiz_del_repo(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        ruta = _ruta_base_datos_original()
        raiz_repo = os.path.abspath(
            os.path.join(os.path.dirname(conection_mod.__file__), "..", ".."))
        assert ruta == os.path.join(raiz_repo, "BaseDatosQA.db")
        assert os.path.isabs(ruta)

    def test_frozen_ancla_al_directorio_del_ejecutable(self, monkeypatch, tmp_path):
        ejecutable_falso = str(tmp_path / "RAD-QA.exe")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", ejecutable_falso, raising=False)
        ruta = _ruta_base_datos_original()
        assert ruta == str(tmp_path / "BaseDatosQA.db")

    def test_ruta_datos_generica_sigue_el_mismo_criterio(self, monkeypatch, tmp_path):
        ejecutable_falso = str(tmp_path / "RAD-QA.exe")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", ejecutable_falso, raising=False)
        assert _ruta_datos_original("cualquier_archivo.json") == \
            str(tmp_path / "cualquier_archivo.json")

    def test_llamadas_repetidas_dan_siempre_la_misma_ruta(self, monkeypatch):
        """Ninguna llamada debe depender de un estado mutable oculto (cwd,
        variable global) -- llamar 5 veces seguidas da lo mismo."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        rutas = {_ruta_base_datos_original() for _ in range(5)}
        assert len(rutas) == 1

    def test_no_depende_del_directorio_de_trabajo_actual(self, monkeypatch, tmp_path):
        """El bug histórico (antes de ruta_base_datos()) era exactamente
        esto: 'BaseDatosQA.db' relativo cambiaba de archivo según el cwd
        del proceso. Cambiar el cwd hoy no debe mover la ruta resuelta."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        ruta_antes = _ruta_base_datos_original()
        cwd_original = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            ruta_despues = _ruta_base_datos_original()
        finally:
            os.chdir(cwd_original)
        assert ruta_antes == ruta_despues


class TestConsistenciaEntreLosCuatroCaminosDeConexion:
    """Los 4 patrones de conexión que coexisten en la app hoy (deuda
    documentada, "doble/triple patrón de conexión") deben apuntar SIEMPRE
    al mismo archivo -- sin importar cuál se use para escribir, cualquier
    otro debe ver el dato inmediatamente."""

    def test_singleton_y_conectar_y_dosis_service_comparten_archivo(self, bd_temporal):
        Conexion()  # arranque

        # Escribe por el singleton persistente
        Conexion().con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)", ("u1", "x", "Usuario Uno", 1, 1, "fisico"))
        Conexion().con.commit()

        # Visible por conectar() (conexión nueva por llamada)
        con_nueva = Conexion().conectar()
        n1 = con_nueva.execute(
            "SELECT COUNT(*) FROM users WHERE user='u1'").fetchone()[0]
        con_nueva.close()
        assert n1 == 1

        # Visible por DosisService._get_connection() (tercer camino)
        con_dosis = DosisService._get_connection()
        n2 = con_dosis.execute(
            "SELECT COUNT(*) FROM users WHERE user='u1'").fetchone()[0]
        con_dosis.close()
        assert n2 == 1

    def test_database_manager_pool_ve_lo_mismo_que_los_otros_tres(self, bd_temporal):
        """El pool DatabaseManager (seiscientos_mensual.py) es el 4to
        camino -- confirmarlo explícitamente, dado que es el que generó el
        ruido "Cannot operate on a closed database" (H-B)."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import DatabaseManager

        Conexion()
        Conexion().con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)", ("u2", "x", "Usuario Dos", 1, 1, "fisico"))
        Conexion().con.commit()

        dbm = DatabaseManager()
        dbm._connections.clear()  # aislar de otros tests que ya hayan poblado el pool
        con_pool = dbm.obtener_conexion()
        n = con_pool.execute(
            "SELECT COUNT(*) FROM users WHERE user='u2'").fetchone()[0]
        assert n == 1
        dbm.cerrar_conexiones()

    def test_escritura_por_dosis_service_es_visible_por_el_singleton(self, bd_temporal):
        """El sentido inverso: guardar un cálculo por DosisService (su
        propio camino de conexión) debe verse de inmediato desde
        Conexion().conectar() -- nunca dos archivos divergentes."""
        Conexion()
        ok = DosisService.guardar_datos({
            "Fecha": "15/07/2026", "Acelerador": "Clinac 600",
            "Tipo_de_radiacion": "Fotones", "energia": "6mv",
        })
        assert ok is True

        con = Conexion().conectar()
        n = con.execute(
            "SELECT COUNT(*) FROM calculadora_dosimetrica WHERE Fecha='15/07/2026'"
        ).fetchone()[0]
        con.close()
        assert n == 1


class TestTrampaWalAlMoverLaBD:
    """H-C capa 2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): en modo WAL el
    archivo .db por sí solo puede NO ser la base completa. Estas pruebas
    demuestran el riesgo real y verifican que checkpoint_wal() lo evita."""

    def test_copiar_solo_el_db_sin_checkpoint_puede_perder_datos_recientes(self, bd_temporal):
        """Demostración del riesgo (no un bug de la app, una propiedad de
        SQLite en modo WAL): sin checkpoint, un commit reciente puede vivir
        SOLO en el -wal, no en el .db principal."""
        Conexion()
        Conexion().con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)", ("wal_only", "x", "Solo En Wal", 1, 1, "fisico"))
        Conexion().con.commit()

        # Copiar ÚNICAMENTE el .db (como copiar un archivo entre máquinas
        # sin fijarse en -wal/-shm) SIN checkpoint previo.
        destino = bd_temporal + ".copia_sin_checkpoint"
        shutil.copyfile(bd_temporal, destino)

        con_copia = sqlite3.connect(destino)
        try:
            try:
                n = con_copia.execute(
                    "SELECT COUNT(*) FROM users WHERE user='wal_only'").fetchone()[0]
            except sqlite3.OperationalError:
                # Ni siquiera la TABLA llegó al .db -- en WAL, hasta el DDL
                # (CREATE TABLE) vive solo en el -wal hasta que se
                # checkpointea. Sin checkpoint, el .db recién creado puede
                # quedar casi vacío pese a tener datos "comprometidos".
                n = 0
        finally:
            con_copia.close()
            os.remove(destino)

        # Si esto llega a fallar (n==1) es porque SQLite ya hizo un
        # checkpoint automático por su cuenta (tamaño del WAL) -- no es
        # garantía, por eso la app necesita su PROPIO checkpoint explícito.
        assert n == 0, (
            "informativo: en esta corrida el WAL ya se autoconsolidó; "
            "de todas formas checkpoint_wal() es la garantía explícita")

    def test_checkpoint_wal_hace_que_copiar_solo_el_db_sea_seguro(self, bd_temporal):
        Conexion()
        Conexion().con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)", ("wal_seguro", "x", "Con Checkpoint", 1, 1, "fisico"))
        Conexion().con.commit()

        conection_mod.checkpoint_wal(Conexion().con)

        destino = bd_temporal + ".copia_con_checkpoint"
        shutil.copyfile(bd_temporal, destino)
        # El checkpoint deja el -wal vacío -- ni falta copiarlo.
        con_copia = sqlite3.connect(destino)
        try:
            n = con_copia.execute(
                "SELECT COUNT(*) FROM users WHERE user='wal_seguro'").fetchone()[0]
        finally:
            con_copia.close()
            os.remove(destino)
        assert n == 1

    def test_checkpoint_wal_es_inofensivo_si_se_llama_varias_veces(self, bd_temporal):
        Conexion()
        conection_mod.checkpoint_wal(Conexion().con)
        conection_mod.checkpoint_wal(Conexion().con)
        conection_mod.checkpoint_wal(Conexion().con)  # no debe lanzar

    def test_checkpoint_wal_no_lanza_con_conexion_cerrada(self):
        """Best-effort: si algo sale mal (conexión ya cerrada, None), no debe
        impedir que la app siga cerrando -- mismo principio que
        audit_minimo.registrar()."""
        conection_mod.checkpoint_wal(None)  # no debe lanzar


class _EventoFalso:
    def __init__(self):
        self.aceptado = False

    def accept(self):
        self.aceptado = True


class _MainWindowFalsaParaCierre:
    """Mismo criterio que _MainWindowFalsa en test_a4_auditar_sesion.py --
    closeEvent solo necesita poder llamar print() (nada especial) y
    event.accept(); no hace falta un QMainWindow real."""


class TestCierreDeLaAppHaceCheckpoint:
    """R2: MainWindow.closeEvent debe consolidar el WAL al cerrar (para que
    una copia posterior de solo el .db quede completa), sin bloquear el
    cierre si algo falla."""

    def test_close_event_hace_checkpoint_del_singleton(self, bd_temporal, monkeypatch):
        import ui.mainpages as mainpages_mod

        Conexion()
        Conexion().con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?,?,?,?,?,?)", ("wal_close", "x", "Cierre App", 1, 1, "fisico"))
        Conexion().con.commit()

        llamado = {}
        original = conection_mod.checkpoint_wal

        def _checkpoint_espia(con):
            llamado["con"] = con
            return original(con)

        monkeypatch.setattr(mainpages_mod, "checkpoint_wal", _checkpoint_espia)

        evento = _EventoFalso()
        mainpages_mod.MainWindow.closeEvent(_MainWindowFalsaParaCierre(), evento)

        assert llamado.get("con") is Conexion().con
        assert evento.aceptado is True

    def test_close_event_no_falla_si_no_hay_conexion_activa(self):
        """Cerrar la app sin haber llegado a instanciar Conexion() (p.ej. un
        cierre muy temprano) no debe reventar."""
        import ui.mainpages as mainpages_mod
        Conexion._instance = None

        evento = _EventoFalso()
        mainpages_mod.MainWindow.closeEvent(_MainWindowFalsaParaCierre(), evento)

        assert evento.aceptado is True
