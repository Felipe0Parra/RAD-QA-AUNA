"""T.4 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §5): el visor de auditoría
dice a qué control pertenece cada fila.

CAUSA. Pedido del handoff: *"Hace falta un detalle más específico en esta
sección de la tabla de auditoría de la app, que contenga información sobre
la fecha del control que se editó, es decir, fecha, equipo (600, iX,
Halcyon), tabla"*. Hoy el visor muestra `Tabla` y `Ref`, y `Ref` es un
número que no dice nada a quien lo lee.

Decisión del 09-09: un valor derivado de columnas ya guardadas no se
almacena, se construye al mostrarlo -- no se toca `audit_log` ni el
esquema, el visor sigue siendo de solo lectura.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.contexto_auditoria import contexto_de_auditoria
from ui.paginasGuia.console_logs import Registros


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield conexion.con, ruta
    conexion.con.close()
    Conexion._instance = None


def _insertar_control(con, id_, equipo, fecha, activo=1):
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (?, ?, 'Mensual', ?, 'Físico de Prueba')",
        (id_, equipo, fecha))
    con.execute("UPDATE controles SET activo = ? WHERE id = ?", (activo, id_))
    con.commit()


def _insertar_tipo_calibracion(con, id_, fecha, activo=1):
    con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, activo) "
        "VALUES (?, 'Físico de Prueba', ?, 'Cambio de fuente', ?)",
        (id_, fecha, activo))
    con.commit()


# ---------------------------------------------------------------------------
# 1. La función pura, caso por caso
# ---------------------------------------------------------------------------

class TestContextoDeAuditoriaCasoAcaso:
    def test_id_de_control_resuelve_equipo_y_fecha(self, bd_temporal):
        con, _ = bd_temporal
        _insertar_control(con, 6, "Clinac ix", "07/2026")

        contexto = contexto_de_auditoria([("tamano_campo", "6")], con)

        assert contexto[("tamano_campo", "6")] == ("Clinac iX", "07/2026"), (
            "el nombre debe normalizarse (DA-15): 'Clinac ix' -> 'Clinac iX'")

    def test_tabla_diaria_no_necesita_consulta(self, bd_temporal):
        con, _ = bd_temporal
        contexto = contexto_de_auditoria(
            [("braqui", "2026-08-15"), ("halcyon", "2026-07-01"),
             ("aceleradorlineal_600", "2026-06-10"),
             ("aceleradorlineal_ix", "2026-05-20")], con)

        assert contexto[("braqui", "2026-08-15")] == ("Braquiterapia", "2026-08-15")
        assert contexto[("halcyon", "2026-07-01")] == ("Halcyon", "2026-07-01")
        assert contexto[("aceleradorlineal_600", "2026-06-10")] == ("Clinac 600", "2026-06-10")
        assert contexto[("aceleradorlineal_ix", "2026-05-20")] == ("Clinac iX", "2026-05-20")

    def test_tipo_calibracion_resuelve_a_braquiterapia(self, bd_temporal):
        con, _ = bd_temporal
        _insertar_tipo_calibracion(con, 34, "2026-06-26 11:42:13")

        contexto = contexto_de_auditoria([("TipoCalibracion", "34")], con)

        assert contexto[("TipoCalibracion", "34")] == ("Braquiterapia", "2026-06-26 11:42:13")

    def test_hijas_de_tipo_calibracion_tambien_resuelven(self, bd_temporal):
        """El `ref` de una hija (SistemaMedicion, CondicionesMedicion...)
        apunta al `id` de TipoCalibracion, igual que ella misma (EB2b: "su
        id es el ref que heredan las 5 tablas hijas")."""
        con, _ = bd_temporal
        _insertar_tipo_calibracion(con, 34, "2026-06-26 11:42:13")

        contexto = contexto_de_auditoria([("SistemaMedicion", "34")], con)

        assert contexto[("SistemaMedicion", "34")] == ("Braquiterapia", "2026-06-26 11:42:13")

    def test_equipos_users_login_backup_quedan_en_blanco(self, bd_temporal):
        con, _ = bd_temporal
        contexto = contexto_de_auditoria(
            [("equipos", "5"), ("users", "1"), ("backup", None),
             ("login", None)], con)

        assert contexto[("equipos", "5")] == ("", "")
        assert contexto[("users", "1")] == ("", "")

    def test_tabla_desconocida_cae_en_blanco_sin_reventar(self, bd_temporal):
        """[medido en producción] 'analisis_placa600' aparece citada en
        audit_log.tabla, sin que exista tal tabla real -- no debe lanzar."""
        con, _ = bd_temporal
        contexto = contexto_de_auditoria([("analisis_placa600", "1")], con)
        assert contexto[("analisis_placa600", "1")] == ("", "")

    def test_ref_no_numerico_para_una_tabla_de_control_no_revienta(self, bd_temporal):
        con, _ = bd_temporal
        contexto = contexto_de_auditoria([("controles", "no-es-un-id")], con)
        assert contexto[("controles", "no-es-un-id")] == ("", "")

    def test_id_inexistente_cae_en_blanco(self, bd_temporal):
        con, _ = bd_temporal
        contexto = contexto_de_auditoria([("controles", "9999")], con)
        assert contexto[("controles", "9999")] == ("", "")

    def test_tabla_none_se_descarta_sin_clave(self, bd_temporal):
        con, _ = bd_temporal
        contexto = contexto_de_auditoria([(None, None)], con)
        assert contexto == {}


# ---------------------------------------------------------------------------
# 2. Control ANULADO -- DA-47, la lectura por id no filtra activo
# ---------------------------------------------------------------------------

def test_control_anulado_se_sigue_identificando(bd_temporal):
    con, _ = bd_temporal
    _insertar_control(con, 7, "Halcyon", "08/2026", activo=0)

    contexto = contexto_de_auditoria([("preguntas", "7")], con)

    assert contexto[("preguntas", "7")] == ("Halcyon", "08/2026"), (
        "un control anulado debe seguir identificándose en su propio "
        "rastro de auditoría (DA-47) -- filtrar aquí lo dejaría en blanco")


def test_tipo_calibracion_anulada_se_sigue_identificando(bd_temporal):
    con, _ = bd_temporal
    _insertar_tipo_calibracion(con, 40, "2026-01-15 09:00:00", activo=0)

    contexto = contexto_de_auditoria([("TipoCalibracion", "40")], con)

    assert contexto[("TipoCalibracion", "40")] == ("Braquiterapia", "2026-01-15 09:00:00")


# ---------------------------------------------------------------------------
# 3. ROJO-ANTES-QUE-VERDE en el widget real, con las dos columnas nuevas
# ---------------------------------------------------------------------------

class TestVisorMuestraElContexto:
    def test_las_columnas_nuevas_existen_despues_de_tabla(self, app, bd_temporal):
        widget = Registros()
        assert widget.COLUMNAS[3] == "Tabla"
        assert widget.COLUMNAS[4] == "Equipo"
        assert widget.COLUMNAS[5] == "Fecha del control"
        # Los índices que test_a7 ya fija (0-3) no se movieron.
        assert widget.COLUMNAS[:4] == ['Fecha/Hora', 'Usuario', 'Acción', 'Tabla']

    def test_fila_de_control_muestra_equipo_y_fecha(self, app, bd_temporal):
        con, _ = bd_temporal
        _insertar_control(con, 45, "Clinac 600", "04/2026")
        con.execute(
            "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
            "VALUES ('2026-04-15 10:00:00', 'Fisico X', 'guardar', "
            "'equipos_medicion', '45', 'x')")
        con.commit()

        widget = Registros()

        assert widget._tabla.rowCount() == 1
        assert widget._tabla.item(0, 3).text() == "equipos_medicion"
        assert widget._tabla.item(0, 4).text() == "Clinac 600"
        assert widget._tabla.item(0, 5).text() == "04/2026"

    def test_fila_de_braqui_muestra_braquiterapia_y_su_propia_fecha(self, app, bd_temporal):
        con, _ = bd_temporal
        con.execute(
            "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
            "VALUES ('2026-08-15 11:00:00', 'Fisico X', 'guardar', "
            "'braqui', '2026-08-15', 'x')")
        con.commit()

        widget = Registros()

        assert widget._tabla.item(0, 4).text() == "Braquiterapia"
        assert widget._tabla.item(0, 5).text() == "2026-08-15"

    def test_fila_sin_control_asociado_queda_en_blanco(self, app, bd_temporal):
        con, _ = bd_temporal
        con.execute(
            "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
            "VALUES ('2026-01-01 08:00:00', 'admin', 'crear', 'users', '1', 'x')")
        con.commit()

        widget = Registros()

        assert widget._tabla.item(0, 4).text() == ""
        assert widget._tabla.item(0, 5).text() == ""


# ---------------------------------------------------------------------------
# 4. Control anulado -- también en el WIDGET real, no solo en la función pura
# ---------------------------------------------------------------------------

def test_widget_identifica_un_control_anulado(app, bd_temporal):
    con, _ = bd_temporal
    _insertar_control(con, 8, "Halcyon", "09/2026", activo=0)
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES ('2026-09-01 12:00:00', 'Fisico X', 'eliminar', 'controles', '8', 'x')")
    con.commit()

    widget = Registros()

    assert widget._tabla.item(0, 4).text() == "Halcyon"
    assert widget._tabla.item(0, 5).text() == "09/2026"


# ---------------------------------------------------------------------------
# 5. Compuerta de SOLO LECTURA: abrir la pestaña no escribe nada
# ---------------------------------------------------------------------------

def _huella_audit_log(ruta):
    con = sqlite3.connect(ruta)
    try:
        filas = con.execute(
            "SELECT timestamp, usuario, accion, tabla, ref, detalle "
            "FROM audit_log ORDER BY id").fetchall()
        return len(filas), filas
    finally:
        con.close()


def test_abrir_la_pestana_no_escribe_nada(app, bd_temporal):
    con, ruta = bd_temporal
    _insertar_control(con, 50, "Clinac 600", "03/2026")
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES ('2026-03-10 09:00:00', 'Fisico X', 'guardar', 'preguntas', '50', 'x')")
    con.commit()

    antes = _huella_audit_log(ruta)
    Registros()
    despues = _huella_audit_log(ruta)

    assert antes == despues, "abrir el visor no debe escribir en audit_log"


# ---------------------------------------------------------------------------
# 6. Coste acotado -- independiente del número de filas
# ---------------------------------------------------------------------------

def test_coste_acotado_independiente_del_numero_de_filas(bd_temporal):
    """500 filas todas del mismo control -> el coste (número de consultas
    SQL disparadas) no debe crecer con el número de FILAS, solo con el
    número de tablas DISTINTAS y de ids DISTINTOS -- aquí, un puñado."""
    con, _ = bd_temporal
    _insertar_control(con, 60, "Clinac 600", "02/2026")

    contador = {"n": 0}
    execute_original = con.execute

    class _ConexionEspia:
        def execute(self, *a, **k):
            contador["n"] += 1
            return execute_original(*a, **k)

    filas = [("tamano_campo", "60")] * 500
    contexto_de_auditoria(filas, _ConexionEspia())

    # 1 PRAGMA foreign_key_list (una sola tabla distinta: tamano_campo) +
    # 1 SELECT en lote sobre controles -- nunca 500.
    assert contador["n"] <= 5, (
        f"el coste creció con el número de FILAS, no con el de tablas/ids "
        f"distintos: {contador['n']} consultas para 500 filas idénticas")
