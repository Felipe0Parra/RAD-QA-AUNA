"""F6 (PLAN_F_CIERRE_ESTANDAR_29-07.md): el respaldo previo a la migración
estructural (F1) no debe mentir sobre quién ni por qué lo disparó.

Antes de F6, `respaldar_bd` auditaba SIEMPRE con el texto fijo "respaldo al
cerrar la aplicacion", aunque lo disparara `_respaldar_antes_de_recrear` (un
evento sin ninguna relación con cerrar la app). Esta suite fija el contrato:

- el camino de E9 (cierre real, con sesión) sigue igual: usuario = el físico,
  detalle menciona el cierre;
- el camino de F1 disparado por el arranque normal de la app (sin sesión
  iniciada) audita con usuario NULL y un detalle que menciona la migración
  estructural, nunca el cierre;
- el mismo camino de F1, disparado por `scripts/migrar_bd_a_estandar.py`,
  audita con el `--usuario` recibido, o con una etiqueta de ejecución no
  interactiva si no se pasó ninguno -- nunca un nombre de persona inventado;
- la etiqueta de terminal es exclusiva del script: el arranque normal de la
  app JAMÁS debe verla (restricción dura del punto 4 del plan).
"""
import sqlite3

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.migrar_bd_a_estandar import ETIQUETA_EJECUCION_TERMINAL, migrar
from services.respaldo import carpeta_respaldos


def _bd_legada(tmp_path, monkeypatch, nombre="legada.db"):
    """Mismo subconjunto real del esquema PRE-E10 que
    test_f1_respaldo_previo_migracion.py -- dispara `_respaldar_antes_de_recrear`
    en el próximo `Conexion()`."""
    ruta = str(tmp_path / nombre)
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo TEXT, control TEXT, fecha TEXT,
            user_id TEXT, user_id_f2 TEXT);
        CREATE TABLE dosimetriaMen (
            ref INTEGER, energia TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE CASCADE ON UPDATE CASCADE);
    """)
    con.execute("INSERT INTO controles (equipo, control, fecha) "
                "VALUES ('Clinac iX', 'Mensual', '01/2026')")
    con.execute("INSERT INTO dosimetriaMen (ref, energia) VALUES (1, '6mv')")
    con.commit()
    con.close()
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    return ruta


def _cerrar(conexion):
    conexion.con.close()
    Conexion._instance = None


def _fila_backup(ruta):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(
            "SELECT usuario, detalle FROM audit_log WHERE tabla='backup'"
        ).fetchone()
    finally:
        con.close()


class TestRespaldoAlCerrarConSesion:
    def test_usuario_y_detalle_mencionan_el_cierre(self, tmp_path):
        from services.respaldo import respaldar_bd

        origen = str(tmp_path / "BaseDatosQA.db")
        con = sqlite3.connect(origen)
        con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()

        destino = respaldar_bd(usuario="Físico de Prueba", ruta_origen=origen,
                               carpeta_destino=str(tmp_path / "respaldos"))
        assert destino is not None

        usuario, detalle = _fila_backup(origen)
        assert usuario == "Físico de Prueba"
        assert "cerrar" in detalle
        assert "migracion" not in detalle


class TestRespaldoPrevioALaMigracionSinSesion:
    def test_arranque_normal_audita_usuario_null_y_menciona_la_migracion(
            self, tmp_path, monkeypatch):
        ruta = _bd_legada(tmp_path, monkeypatch)
        conexion = Conexion()  # arranque real de la app: dispara F1
        try:
            usuario, detalle = _fila_backup(ruta)
            assert usuario is None
            assert "migracion" in detalle.lower() or "migración" in detalle.lower()
            assert "cerrar" not in detalle
        finally:
            _cerrar(conexion)


class TestScriptDeMigracionPropagaIdentidad:
    def test_con_usuario_explicito(self, tmp_path, monkeypatch):
        ruta = _bd_legada(tmp_path, monkeypatch)

        migrar(ruta, aplicar=True, usuario="Luz Adriana Maya")

        usuario, _ = _fila_backup(ruta)
        assert usuario == "Luz Adriana Maya"

    def test_sin_usuario_usa_etiqueta_de_terminal(self, tmp_path, monkeypatch):
        ruta = _bd_legada(tmp_path, monkeypatch)

        migrar(ruta, aplicar=True, usuario=None)

        usuario, _ = _fila_backup(ruta)
        assert usuario == ETIQUETA_EJECUCION_TERMINAL


class TestTripwireEtiquetaDeTerminalNuncaEnElArranqueDeLaApp:
    def test_la_etiqueta_no_aparece_en_ningun_respaldo_del_arranque_normal(
            self, tmp_path, monkeypatch):
        """Aunque el script haya corrido antes en el mismo proceso (y por lo
        tanto haya fijado y restaurado USUARIO_RESPALDO_MIGRACION), un
        arranque posterior de la app por su cuenta debe seguir viendo el
        valor por defecto (None) -- nunca un residuo de la última corrida
        del script."""
        ruta_script = _bd_legada(tmp_path, monkeypatch, nombre="para_script.db")
        migrar(ruta_script, aplicar=True, usuario=None)
        assert conection_mod.USUARIO_RESPALDO_MIGRACION is None

        ruta_app = _bd_legada(tmp_path, monkeypatch, nombre="app.db")
        conexion = Conexion()  # arranque normal, sin sesión, DESPUÉS del script
        try:
            usuario, _ = _fila_backup(ruta_app)
            assert usuario is None
        finally:
            _cerrar(conexion)
