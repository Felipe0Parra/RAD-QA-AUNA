"""E6 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §10): modelo de roles real.

`users.rol_sistema` ('admin'/'jefe'/'fisico') se puebla con una migración
idempotente al arranque; `es_admin_equivalente()` conserva nombre y firma
(C3) pero ahora resuelve por rol de BD, con fallback al conjunto codificado
{"admin","lamaya"} SOLO cuando el rol no es legible.

Decisión de implementación anclada aquí: `users.role` (el cargo mostrado,
'Físico Médico') NO se migra -- lo imprimen 5 reportes PDF clínicos en el
bloque de firma y lo compara literal la recuperación de contraseña
(get_user/recover_page). El rol de permisos vive en una columna aparte.
"""
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
import services.permisos as permisos_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.encriptarInfo import encrypt_data
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData
from services.permisos import es_admin_equivalente, rol_de

# El plantel real de producción (users de la BD del 28-07): admin con role
# NULL y 6 físicos con 'Físico Médico', incluida la jefe.
PLANTEL = [
    ("admin", "Administrador", None),
    ("accastellanos", "Cristian Castellanos", "Físico Médico"),
    ("adloaiza", "Andres David Loaiza Baena", "Físico Médico"),
    ("lamaya", "Luz Adriana Maya", "Físico Médico"),
    ("dmesa", "Daniela Mesa Lotero", "Físico Médico"),
    ("jjcastillo", "Javier Castillo", "Físico Médico"),
    ("JADIAZ", "José Antonio Diaz Merchán", "Físico Médico"),
]


def _sembrar_plantel_legado(ruta):
    """Deja `users` como en producción ANTES de E6 (sin rol_sistema poblado).

    Se insertan directo con sqlite3 (sin pasar por add_user, que ya asigna
    rol_sistema) y se borra lo que la migración del arranque haya puesto,
    para simular una BD legada real."""
    con = sqlite3.connect(ruta)
    for user, fullname, role in PLANTEL:
        con.execute(
            "INSERT OR IGNORE INTO users (user, password, fullname, active, idreal, role) "
            "VALUES (?, ?, ?, 1, '1', ?)",
            (user, encrypt_data("x"), fullname, role))
    con.execute("UPDATE users SET rol_sistema = NULL")
    con.commit()
    con.close()


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales
    yield ruta, conexion
    conexion.con.close()
    Conexion._instance = None


def _roles(ruta):
    con = sqlite3.connect(ruta)
    filas = dict(con.execute("SELECT user, rol_sistema FROM users").fetchall())
    con.close()
    return filas


class TestMigracion:
    def test_mapeo_admin_jefe_fisico(self, bd_temporal):
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)

        conexion._asegurar_roles_de_sistema()

        roles = _roles(ruta)
        assert roles["admin"] == "admin"
        assert roles["lamaya"] == "jefe"
        for user, _, _ in PLANTEL:
            if user not in ("admin", "lamaya"):
                assert roles[user] == "fisico", user

    def test_idempotente_dos_corridas_mismos_roles(self, bd_temporal):
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)

        conexion._asegurar_roles_de_sistema()
        antes = _roles(ruta)
        conexion._asegurar_roles_de_sistema()
        assert _roles(ruta) == antes

    def test_asignacion_manual_posterior_no_se_pisa(self, bd_temporal):
        """Si otra física asciende a jefe (asignación manual), la migración
        del siguiente arranque no debe devolverla a 'fisico'."""
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)
        conexion._asegurar_roles_de_sistema()

        con = sqlite3.connect(ruta)
        con.execute("UPDATE users SET rol_sistema='jefe' WHERE user='dmesa'")
        con.commit()
        con.close()

        conexion._asegurar_roles_de_sistema()
        assert _roles(ruta)["dmesa"] == "jefe"

    def test_no_se_pierde_ninguna_cuenta_y_role_mostrado_intacto(self, bd_temporal):
        """Los usuarios NUNCA se borran; y `role` (cargo de los PDF) no se
        reescribe: la jefe sigue siendo 'Físico Médico' de cara al reporte."""
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)
        con = sqlite3.connect(ruta)
        n_antes = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        con.close()

        conexion._asegurar_roles_de_sistema()

        con = sqlite3.connect(ruta)
        n_despues = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        cargo_jefe = con.execute(
            "SELECT role FROM users WHERE user='lamaya'").fetchone()[0]
        con.close()
        assert n_despues == n_antes
        assert cargo_jefe == "Físico Médico"


class TestEsAdminEquivalente:
    def test_mismo_contrato_que_c3_pero_por_rol(self, bd_temporal):
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)
        conexion._asegurar_roles_de_sistema()

        assert es_admin_equivalente("admin") is True
        assert es_admin_equivalente("lamaya") is True
        for user, _, _ in PLANTEL:
            if user not in ("admin", "lamaya"):
                assert es_admin_equivalente(user) is False, user
        assert es_admin_equivalente("") is False
        assert es_admin_equivalente(None) is False

    def test_resuelve_por_rol_no_por_nombre(self, bd_temporal):
        """La fragilidad que E6 elimina: si otra física asciende a jefe (solo
        cambiando su rol en BD), obtiene permisos SIN tocar código."""
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)
        conexion._asegurar_roles_de_sistema()

        con = sqlite3.connect(ruta)
        con.execute("UPDATE users SET rol_sistema='jefe' WHERE user='dmesa'")
        con.commit()
        con.close()

        assert es_admin_equivalente("dmesa") is True

    def test_fallback_bd_sin_migrar_conserva_a_lamaya(self, bd_temporal, capsys):
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)  # rol_sistema queda NULL

        assert es_admin_equivalente("lamaya") is True
        assert "[permisos]" in capsys.readouterr().out  # avisó
        assert es_admin_equivalente("dmesa") is False

    def test_rol_de_devuelve_el_rol_crudo(self, bd_temporal):
        ruta, conexion = bd_temporal
        _sembrar_plantel_legado(ruta)
        conexion._asegurar_roles_de_sistema()

        assert rol_de("lamaya") == "jefe"
        assert rol_de("admin") == "admin"
        assert rol_de("dmesa") == "fisico"
        assert rol_de("no_existe") is None


class TestAddUser:
    def test_usuario_nuevo_recibe_rol_valido(self, bd_temporal):
        ruta, _ = bd_temporal
        nuevo = Usuario(username="nfisico", password="clave", fullname="Nueva Física",
                        active=1, identificacion="9", role="Físico Médico", firma=b"")

        assert UsuarioData().add_user(nuevo) is not None

        con = sqlite3.connect(ruta)
        rol_sistema, role = con.execute(
            "SELECT rol_sistema, role FROM users WHERE user='nfisico'").fetchone()
        con.close()
        assert rol_sistema == "fisico"          # permisos: nunca NULL
        assert role == "Físico Médico"          # cargo mostrado: lo que eligió
        assert es_admin_equivalente("nfisico") is False
