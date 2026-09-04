"""U2 (PLAN_PESTANA_USUARIOS_02-09.md, O-1/O-2): que `active=0` cierre de
verdad la puerta. Antes de esta tarea, `login()` no miraba `active` -- la
única palanca de baja que la pestaña de usuarios va a ofrecer habría sido
decorativa: el físico creería haber cerrado una cuenta que sigue entrando.

`COALESCE(active,1)=1` a propósito: un `active` NULL (histórico, nunca
tocado por ninguna migración) no debe cerrar la aplicación -- solo
`active=0` explícito bloquea.

U2-bis (O-7, hallado al verificar el plan antes de ejecutarlo): filtrar el
selector de físicos por `active` rompía la lectura de un control YA
FIRMADO por alguien hoy inactivo -- `findText` devolvía -1 y el combo se
quedaba mostrando a otra persona, en silencio. Se corrige agregando el
nombre guardado al combo si no está entre los candidatos activos.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.encriptarInfo import encrypt_data
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sembrar_usuario(ruta, user, fullname, active, clave="clave_real"):
    import sqlite3
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES (?, ?, ?, ?, '1', 'Físico Médico', 'fisico')",
        (user, encrypt_data(clave), fullname, active))
    con.commit()
    con.close()


def _ultima_fila_audit(ruta):
    import sqlite3
    con = sqlite3.connect(ruta)
    fila = con.execute(
        "SELECT usuario, accion, detalle FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    con.close()
    return fila


class TestActiveCierraLaPuerta:

    def test_usuario_activo_con_clave_correcta_entra(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", active=1)
        res = UsuarioData().login(Usuario("jjcastillo", "clave_real"))
        assert res is not None
        assert res._nombre == "Javier Castillo"

    def test_mismo_usuario_inactivo_con_la_misma_clave_correcta_no_entra(
            self, bd_temporal):
        """El caso central: NO es un problema de contraseña -- la misma
        clave que funcionaba deja de servir en cuanto active=0."""
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", active=0)
        res = UsuarioData().login(Usuario("jjcastillo", "clave_real"))
        assert res is None

        usuario, accion, detalle = _ultima_fila_audit(bd_temporal)
        assert detalle == "cuenta inactiva"
        # A4: se audita con el fullname, no con el login intentado.
        assert usuario == "Javier Castillo"

    def test_no_revela_si_la_clave_era_correcta(self, bd_temporal):
        """El detalle de auditoría es el mismo para clave correcta e
        incorrecta sobre una cuenta inactiva -- se audita ANTES de
        comparar la contraseña, a propósito."""
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", active=0)
        UsuarioData().login(Usuario("jjcastillo", "clave_incorrecta"))
        _, _, detalle_mala = _ultima_fila_audit(bd_temporal)

        UsuarioData().login(Usuario("jjcastillo", "clave_real"))
        _, _, detalle_buena = _ultima_fila_audit(bd_temporal)

        assert detalle_mala == detalle_buena == "cuenta inactiva"

    def test_active_null_historico_si_entra(self, bd_temporal):
        """O-2: un NULL histórico (cuenta nunca tocada por una migración de
        `active`) no debe cerrar la aplicación."""
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", active=None)
        res = UsuarioData().login(Usuario("jjcastillo", "clave_real"))
        assert res is not None

    def test_cuenta_esta_activa_distingue_para_el_mensaje_de_login(self, bd_temporal):
        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", active=0)
        assert UsuarioData().cuenta_esta_activa("jjcastillo") is False

        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", active=1)
        assert UsuarioData().cuenta_esta_activa("dmesa") is True

        assert UsuarioData().cuenta_esta_activa("no_existe") is None


class TestSelectorDeFisicosNoListaAlInactivo:

    def test_consultar_fisicos_bd_no_ofrece_al_inactivo(self, app, bd_temporal):
        from PyQt5.QtCore import QDate
        from PyQt5.QtWidgets import QDateEdit

        from services.db_pool import DatabaseManager
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600

        _sembrar_usuario(bd_temporal, "jjcastillo", "Javier Castillo", active=1)
        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", active=0)

        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj.equipo_f = "Clinac 600"
        obj.db_manager = DatabaseManager()
        obj.date_box = QDateEdit()
        obj.date_box.setDate(QDate(2026, 6, 15))
        fisicos, _ = obj.consultar_fisicos_bd(id_f1=None)

        nombres = [f[1] for f in fisicos]
        assert "Javier Castillo" in nombres
        assert "Daniela Mesa" not in nombres, (
            "un físico dado de baja no debe ofrecerse como candidato para "
            "un control nuevo")


class TestU2BisReabrirControlNoPierdeAlResponsableInactivo:
    """O-7: filtrar el selector por `active` no puede romper la lectura de
    un control YA firmado por alguien hoy inactivo."""

    def test_actualizar_fisicos_agrega_al_responsable_inactivo_si_falta(
            self, app, bd_temporal):
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        from data.ManejoDatos.conection import Conexion as ConexionReal

        _sembrar_usuario(bd_temporal, "dmesa", "Daniela Mesa", active=0)

        con = ConexionReal().con
        con.execute(
            "INSERT INTO controles (equipo, fecha, user_id, activo) "
            "VALUES ('Clinac 600', '15/06/2026', 'Daniela Mesa', 1)")
        con.commit()

        from PyQt5.QtWidgets import QDateEdit
        from PyQt5.QtCore import QDate
        from services.db_pool import DatabaseManager

        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj.equipo_f = "Clinac 600"
        obj.db_manager = DatabaseManager()
        obj.date_box = QDateEdit()
        obj.date_box.setDate(QDate(2026, 6, 15))

        # El combo arranca SOLO con los candidatos activos -- "Daniela
        # Mesa" (inactiva) no está, reproduciendo el estado real tras U2.
        obj.fisico1 = QComboBox()
        obj.fisico2 = QComboBox()

        assert obj.fisico1.findText("Daniela Mesa") == -1, (
            "precondición: el combo no debe traer al inactivo todavía")

        obj.actualizar_fisicos()

        indice = obj.fisico1.findText("Daniela Mesa")
        assert indice >= 0, (
            "reabrir un control ya firmado por alguien hoy inactivo debe "
            "mostrar su nombre real, no dejar el combo en otra selección")
        assert obj.fisico1.currentText() == "Daniela Mesa"
