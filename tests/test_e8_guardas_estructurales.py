"""E8 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §14): guardas estructurales --
un `TRIGGER BEFORE DELETE` para que la BASE DE DATOS misma rechace el
borrado físico, independientemente de lo que haga la aplicación.

ALCANCE AJUSTADO respecto al plan original (ver el docstring de
`Conexion._asegurar_triggers_anti_delete` en conection.py para el análisis
completo): el plan pedía un trigger por cada una de las 27 tablas de
`services.anulacion.TABLAS_ANULABLES` + `users`. Al implementarlo se
encontró que `loadtablacomplex`/`add_info` (load.py) usan DELETE+INSERT
como mecanismo de GUARDADO normal ("Subir") para ~20 tablas hijas
mensuales/anuales y las 4 diarias -- un trigger genérico ahí habría
bloqueado el guardado, no solo el borrado. Se limitó la protección a
`Conexion.TABLAS_CON_TRIGGER_ANTI_DELETE`: `controles`, `TipoCalibracion`,
`LinealidadBraquiterapia` y `users` -- las únicas 4 tablas del inventario
verificadas SIN ningún DELETE físico interno alcanzable. Cierra los dos
peligros más graves de §13.2 (TipoCalibracion arrastrando
ResultadosActividad en cascada; la regla de que los usuarios nunca se
eliminan), sin arriesgar el guardado normal del resto de la app.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta, conexion
    conexion.con.close()
    Conexion._instance = None


def _triggers(ruta):
    con = sqlite3.connect(ruta)
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'")}
    finally:
        con.close()


class TestAlcanceAjustado:
    def test_las_4_tablas_protegidas_son_exactamente_estas(self):
        assert Conexion.TABLAS_CON_TRIGGER_ANTI_DELETE == {
            "controles", "TipoCalibracion", "LinealidadBraquiterapia", "users"}

    def test_cada_tabla_protegida_tiene_su_trigger(self, bd_temporal):
        ruta, _ = bd_temporal
        triggers = _triggers(ruta)
        for tabla in Conexion.TABLAS_CON_TRIGGER_ANTI_DELETE:
            assert f"trg_no_borrar_{tabla}" in triggers, tabla


class TestDeleteBloqueadoUpdateEInsertFuncionan:
    @pytest.mark.parametrize("tabla,columnas,valores", [
        ("controles", "equipo, control, fecha", "'Clinac iX', 'Mensual', '01/2026'"),
        ("TipoCalibracion", "user, fecha, tipo", "'x', '01/01/2026', 'Cambio de fuente'"),
        ("LinealidadBraquiterapia", "user, fecha", "'x', '01/01/2026'"),
    ])
    def test_delete_lanza_integrity_error(self, bd_temporal, tabla, columnas, valores):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({valores})")
        id_fila = cur.lastrowid
        conexion.con.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cur.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_fila,))
        conexion.con.rollback()

        n = cur.execute(f"SELECT COUNT(*) FROM {tabla} WHERE id = ?", (id_fila,)).fetchone()[0]
        assert n == 1  # sigue ahí

    def test_anular_controles_sigue_funcionando(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute("INSERT INTO controles (equipo, control, fecha) "
                    "VALUES ('Clinac iX', 'Mensual', '01/2026')")
        ref = cur.lastrowid
        conexion.con.commit()

        cur.execute("UPDATE controles SET activo = 0 WHERE id = ?", (ref,))
        conexion.con.commit()

        activo = cur.execute("SELECT activo FROM controles WHERE id=?", (ref,)).fetchone()[0]
        assert activo == 0

    def test_insertar_sigue_funcionando_en_las_4_tablas(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('x','x','x')")
        cur.execute("INSERT INTO TipoCalibracion (user, fecha, tipo) VALUES ('x','x','x')")
        cur.execute("INSERT INTO LinealidadBraquiterapia (user, fecha) VALUES ('x','x')")
        conexion.con.commit()  # no debe lanzar


class TestHijasIntactasTrasIntentoDeBorradoDelPadre:
    def test_borrar_tipocalibracion_no_toca_las_hijas(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute("INSERT INTO TipoCalibracion (user, fecha, tipo) "
                    "VALUES ('x', '01/01/2026', 'Cambio de fuente')")
        ref = cur.lastrowid
        cur.execute("INSERT INTO SistemaMedicion (ref, user) VALUES (?, 'x')", (ref,))
        conexion.con.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("DELETE FROM TipoCalibracion WHERE id = ?", (ref,))
        conexion.con.rollback()

        n = cur.execute("SELECT COUNT(*) FROM SistemaMedicion WHERE ref=?", (ref,)).fetchone()[0]
        assert n == 1


class TestUsersNuncaSeBorra:
    def test_delete_sobre_users_bloqueado(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute("SELECT id FROM users LIMIT 1")
        id_admin = cur.fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("DELETE FROM users WHERE id = ?", (id_admin,))
        conexion.con.rollback()

        n = cur.execute("SELECT COUNT(*) FROM users WHERE id=?", (id_admin,)).fetchone()[0]
        assert n == 1


class TestMigracionIdempotente:
    def test_correr_dos_veces_no_cambia_nada(self, bd_temporal):
        ruta, conexion = bd_temporal
        triggers_1 = _triggers(ruta)
        conexion._asegurar_triggers_anti_delete()
        conexion._asegurar_triggers_anti_delete()
        assert _triggers(ruta) == triggers_1


class TestElReemplazoAlGuardarSigueFuncionando:
    """La razón de fondo del recorte de alcance: `add_info` (reporte diario)
    y `loadtablacomplex` (mensual/anual) hacen DELETE+INSERT como mecanismo
    de GUARDADO ("Subir"), no de borrado -- deben seguir funcionando
    exactamente igual después de E8, precisamente porque NO llevan
    trigger."""

    def test_add_info_puede_seguir_reemplazando_un_reporte_diario(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        # user_id referencia users(fullname) con RESTRICT (W2/E10): usar un
        # usuario real -- 'admin' ya existe (createAdmin, arranque).
        usuario = cur.execute(
            "SELECT fullname FROM users WHERE user='admin'").fetchone()[0]
        cur.execute("INSERT INTO aceleradorlineal_600 (date, user_id) "
                    "VALUES ('2026-07-01', ?)", (usuario,))
        conexion.con.commit()

        # el mismo patrón que add_info ejecuta al reemplazar (H2.2): DELETE
        # por fecha, sin trigger de por medio -- NO debe lanzar.
        cur.execute("DELETE FROM aceleradorlineal_600 WHERE DATE(date) = ?",
                    ("2026-07-01",))
        cur.execute("INSERT INTO aceleradorlineal_600 (date, user_id) "
                    "VALUES ('2026-07-01', ?)", (usuario,))
        conexion.con.commit()

        n = cur.execute("SELECT COUNT(*) FROM aceleradorlineal_600").fetchone()[0]
        assert n == 1

    def test_loadtablacomplex_puede_seguir_reemplazando_una_hija_mensual(self, bd_temporal):
        ruta, conexion = bd_temporal
        cur = conexion.con.cursor()
        cur.execute("INSERT INTO controles (equipo, control, fecha) "
                    "VALUES ('Clinac iX', 'Mensual', '01/2026')")
        ref = cur.lastrowid
        cur.execute("INSERT INTO equipos_medicion (ref, equip_type) VALUES (?, 'x')", (ref,))
        conexion.con.commit()

        # el mismo patrón que loadtablacomplex ejecuta en cada "Subir":
        # borra por ref y reinserta -- NO debe lanzar.
        cur.execute("DELETE FROM equipos_medicion WHERE ref=?", (ref,))
        cur.execute("INSERT INTO equipos_medicion (ref, equip_type) VALUES (?, 'y')", (ref,))
        conexion.con.commit()

        fila = cur.execute(
            "SELECT equip_type FROM equipos_medicion WHERE ref=?", (ref,)).fetchone()
        assert fila == ("y",)
