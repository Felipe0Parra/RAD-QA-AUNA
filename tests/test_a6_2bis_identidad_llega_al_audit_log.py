"""A6.2-bis: la identidad del físico LLEGA de verdad a `audit_log`.

Origen: rebuild del físico del 27-07-2026. Las 3 acciones de A6.2 dejaron
rastro, pero las dos filas de `equipos` salieron con `usuario` NULL:

    38 | eliminar | equipos | 99999/09999 | usuario NULL
    37 | guardar  | equipos | 99999/09999 | usuario NULL

Causa raíz (tres capas por debajo de la llamada a `registrar()`):
`PruebaBasico.__init__` RECIBÍA `user_id` y **nunca lo guardaba** -- solo
`init_data()` lo asignaba, y `Config` (pestaña Equipos) no la llama nunca.
Encima `Config.__init__` no declaraba el parámetro y `mainpages._crear_config`
instanciaba `Config()` sin argumentos. Resultado: `_usuario_actual(self)`
devolvía None en los 3 puntos de auditoría del catálogo -- **dos de ellos
anteriores a A6.2** (alta y edición, de H2.4/A5). A6.2 copió el patrón
existente, incluido su defecto.

POR QUÉ NINGUNO DE LOS 817 TESTS LO VIO -- y qué se corrige aquí:
`tests/test_a6_2_auditoria_identidad_catalogo.py` construye el objeto con
`Config.__new__(Config)` + `obj.user_id = _UsuarioActualFalso()`, es decir
INYECTA a mano el atributo que producción nunca ponía. Eso verifica "dado un
user_id, la auditoría lo escribe bien", pero nunca "un Config real tiene
user_id". El patrón `__new__` + inyección es la convención de la suite para
clases de UI (evita construir toda la GUI), y salta justo el constructor
donde vivía el bug.

Este archivo cubre el hueco por el otro lado: NO inyecta nada, construye por
el constructor real y verifica la cadena completa de identidad.
"""
import sqlite3

import pytest
from PyQt5.QtWidgets import QApplication, QDialog

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.audit_minimo import usuario_actual
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class TestPruebaBasicoConservaLaIdentidad:
    """La raíz del bug: el `user_id` que se pasa al constructor tiene que
    sobrevivir, sin depender de que la subclase llame a `init_data()`."""

    def test_init_guarda_el_user_id_recibido(self, app):
        usuario = _UsuarioFalso()
        obj = PruebaBasico(usuario)
        assert obj.user_id is usuario
        assert usuario_actual(obj) == "Físico de Prueba"

    def test_sin_user_id_queda_none_sin_reventar(self, app):
        # La auditoría es best-effort: mejor `usuario` NULL que una excepción
        # en mitad de un guardado clínico (docstring de audit_minimo).
        obj = PruebaBasico()
        assert obj.user_id is None
        assert usuario_actual(obj) is None


class TestConfigRecibeLaIdentidadComoEnProduccion:
    """Construye `Config` por el constructor REAL (sin `__new__` ni inyección
    de atributos) -- que es justo lo que ningún test hacía."""

    def test_config_construido_con_user_id_lo_resuelve(self, app, bd_temporal):
        from ui.paginasGuia.equipos import Config

        config = Config(_UsuarioFalso())
        try:
            assert usuario_actual(config) == "Físico de Prueba"
        finally:
            config.deleteLater()

    def test_mainpages_le_pasa_la_identidad_a_config(self, app, bd_temporal):
        """El call-site real: `MainWindow._crear_config()`. Antes hacía
        `Config()` a secas y por ahí se perdía la identidad."""
        from ui.mainpages import MainWindow

        # MainWindow.__init__ levanta toda la GUI (pestañas, estilos); aquí
        # solo interesa el método de fábrica, así que se invoca sobre un
        # objeto con lo mínimo que ese método lee.
        falso = MainWindow.__new__(MainWindow)
        falso.user_id = _UsuarioFalso()

        widget = MainWindow._crear_config(falso)
        try:
            assert usuario_actual(widget) == "Físico de Prueba", (
                "MainWindow._crear_config() no está pasando la identidad a "
                "Config -- las 3 auditorías del catálogo de equipos "
                "volverían a escribir usuario NULL."
            )
        finally:
            widget.deleteLater()


class TestDialogosEmergentesLlevanLaIdentidad:
    """Segundo foco del mismo defecto: `guardarEdicion` / `eliminarRegistro*`
    reciben un `dlg`. Desde el formulario mensual llega `self` (con
    identidad), pero los diálogos emergentes de "Ver tabla" creaban un
    `QDialog(parent)` pelado -> `usuario` NULL en cada edición/borrado hecho
    desde ahí."""

    def _padre_con_identidad(self):
        padre = QDialog()
        padre.user_id = _UsuarioFalso()
        return padre

    def test_mostrar_dosimetria_propaga_la_identidad_al_dialogo(self, app, bd_temporal, monkeypatch):
        import data.ManejoDatos.load as load_mod

        capturado = {}

        def _captura(dlg, *a, **k):
            capturado["usuario"] = usuario_actual(dlg)
            return None

        monkeypatch.setattr(load_mod, "guardarEdicion", _captura)

        padre = self._padre_con_identidad()
        dlg = load_mod._dialogo_con_identidad(QDialog(padre), padre)
        assert usuario_actual(dlg) == "Físico de Prueba"

    def test_dialogo_sin_padre_identificable_no_revienta(self, app):
        import data.ManejoDatos.load as load_mod

        dlg = load_mod._dialogo_con_identidad(QDialog(), QDialog())
        assert usuario_actual(dlg) is None
