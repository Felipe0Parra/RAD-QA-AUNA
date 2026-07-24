"""R3 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): cierra el resto de la
deuda de ALTER TABLE ad-hoc que quedaba FUERA del arranque -- mismo patrón de
riesgo que H-C/R1 (una columna que solo se agrega dentro de una función de
listado/guardado específica revienta cualquier lectura anterior sobre una BD
"vieja" que nunca pasó por ahí), pero para otras tablas:

- `pruebas.mes_control`/`.equipo`: antes solo se agregaban dentro de las
  funciones de listado anual de imágenes (IX/Halcyon/TAC) o del guardado de
  CT -- una BD que nunca abrió esas vistas seguía sin la columna.
- `CondicionesMedicion.observaciones`: antes solo dentro de
  `observaciones_db` de braquiterapia.
- `equipos.imagen_certificado`/`.h_cal` y `dosimetriaMen.energia`: YA están en
  el CREATE TABLE actual (cubren BD nuevas), pero el ALTER que las agregaba a
  una BD ya desplegada quedó comentado/inerte -- una BD genuinamente antigua
  (anterior a que esas columnas existieran) las seguiría sin tener.

Reproduce el escenario real: instanciar Conexion() (arranque) sobre una BD
"vieja" con estas tablas ya creadas pero SIN las columnas nuevas, y verificar
que quedan agregadas sin tocar los datos existentes -- sin depender de que
alguien abra esa pantalla o guarde ese registro primero.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion


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


def _crear_bd_vieja(ruta):
    """Tablas ya desplegadas, ANTERIORES a las 6 columnas de R3, con una fila
    de datos real en cada una -- para probar que migrar no las toca."""
    con = sqlite3.connect(ruta)
    con.execute("""
        CREATE TABLE pruebas (
            id_prueba INTEGER PRIMARY KEY AUTOINCREMENT,
            id_sesion TEXT,
            created_at TEXT
        )
    """)
    con.execute(
        "INSERT INTO pruebas (id_sesion, created_at) VALUES ('20240101_1', '2024-01-15')")
    con.execute("""
        CREATE TABLE CondicionesMedicion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref TEXT
        )
    """)
    con.execute("INSERT INTO CondicionesMedicion (ref) VALUES ('9')")
    con.execute("""
        CREATE TABLE equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT,
            serie TEXT
        )
    """)
    con.execute("INSERT INTO equipos (model, serie) VALUES ('N31010', '1822')")
    con.execute("""
        CREATE TABLE dosimetriaMen (
            ref INTEGER,
            dosis_ref_cgy_um INTEGER
        )
    """)
    con.execute("INSERT INTO dosimetriaMen (ref, dosis_ref_cgy_um) VALUES (16, 1)")
    con.commit()
    con.close()


class TestMigracionesAdHocAlArranque:

    def test_columnas_nuevas_existen_sin_abrir_ninguna_pantalla(self, bd_temporal):
        _crear_bd_vieja(bd_temporal)

        Conexion()  # arranque; nunca se llamó a ninguna función de listado/guardado

        con = Conexion().conectar()
        cols_pruebas = [c[1] for c in con.execute("PRAGMA table_info(pruebas)").fetchall()]
        cols_cond = [c[1] for c in con.execute("PRAGMA table_info(CondicionesMedicion)").fetchall()]
        cols_equipos = [c[1] for c in con.execute("PRAGMA table_info(equipos)").fetchall()]
        cols_dosim = [c[1] for c in con.execute("PRAGMA table_info(dosimetriaMen)").fetchall()]
        con.close()

        assert "mes_control" in cols_pruebas
        assert "equipo" in cols_pruebas
        assert "observaciones" in cols_cond
        assert "imagen_certificado" in cols_equipos
        assert "h_cal" in cols_equipos
        assert "energia" in cols_dosim

    def test_datos_preexistentes_intactos(self, bd_temporal):
        _crear_bd_vieja(bd_temporal)
        Conexion()

        con = Conexion().conectar()
        fila_pruebas = con.execute(
            "SELECT id_sesion, created_at FROM pruebas").fetchone()
        fila_cond = con.execute("SELECT ref FROM CondicionesMedicion").fetchone()
        fila_equipos = con.execute("SELECT model, serie FROM equipos").fetchone()
        fila_dosim = con.execute(
            "SELECT ref, dosis_ref_cgy_um FROM dosimetriaMen").fetchone()
        con.close()

        assert fila_pruebas == ("20240101_1", "2024-01-15")
        assert fila_cond == ("9",)
        assert fila_equipos == ("N31010", "1822")
        assert fila_dosim == (16, 1)

    def test_es_idempotente_tras_reiniciar_varias_veces(self, bd_temporal):
        _crear_bd_vieja(bd_temporal)
        Conexion()
        con = Conexion().conectar()
        n_cols_primera_vez = len(con.execute("PRAGMA table_info(pruebas)").fetchall())
        con.close()

        for _ in range(3):
            Conexion._instance.con.close()
            Conexion._instance = None
            Conexion()  # simula reabrir la app

        con = Conexion().conectar()
        n_cols_tras_reabrir = len(con.execute("PRAGMA table_info(pruebas)").fetchall())
        con.close()

        # reabrir varias veces no duplica columnas ni falla
        assert n_cols_tras_reabrir == n_cols_primera_vez

    def test_sin_ninguna_de_las_tablas_no_falla_bd_vacia(self, bd_temporal):
        """Una BD completamente nueva (sin ninguna de estas tablas creada a
        mano) arranca igual -- _asegurar_migraciones_ad_hoc no debe reventar
        cuando las tablas ya existen vía el CREATE TABLE normal de la app."""
        Conexion()  # BD nueva, createTable()/crearTablas* crean todo desde cero

        con = Conexion().conectar()
        cols_equipos = [c[1] for c in con.execute("PRAGMA table_info(equipos)").fetchall()]
        cols_dosim = [c[1] for c in con.execute("PRAGMA table_info(dosimetriaMen)").fetchall()]
        con.close()

        assert "imagen_certificado" in cols_equipos
        assert "energia" in cols_dosim
