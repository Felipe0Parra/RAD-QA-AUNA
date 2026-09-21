"""U6 (PLAN_PESTANA_USUARIOS_02-09.md): la pestaña "Usuarios" se agrega a
`MainWindow` AL FINAL de `_tab_definiciones` -- `_cargar_pestania_diferida`
indexa esa lista por POSICIÓN, y `block()` referencia índices comentados
(`setTabEnabled(2/4)`); insertar en medio habría movido índices existentes.
Lista literal de las 9 pestañas previas, para que mover o reordenar
cualquiera de ellas ponga este test en rojo -- no solo que aparezca
"Usuarios".

C.2 (PLAN_REFERENCIAS_EDITABLES_21-09.md) añadió "Referencias" DESPUÉS de
"Usuarios", por la misma razón: por eso ya no se afirma que Usuarios sea la
última, sino que sigue en su índice y que las 9 previas no se movieron.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.user import Usuario
from ui.mainpages import MainWindow

TITULOS_PREVIOS = [
    "600", "iX", "Halcyon", "Braquiterapia", "Tomógrafo",
    "Equipos", "Excel", "Registros", "Visor BD",
]


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
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES (?, 'x', ?, 1, '1', 'Físico Médico', ?)",
        ("lamaya", "Luz Adriana Maya", "jefe"))
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class TestPestanaUsuariosEnMainWindow:

    def test_titulos_y_orden_de_las_nueve_previas_no_cambia(self, app, bd_temporal):
        w = MainWindow(Usuario(username="lamaya", fullname="Luz Adriana Maya"))
        titulos = [w.tabs.tabText(i) for i in range(len(TITULOS_PREVIOS))]
        assert titulos == TITULOS_PREVIOS

    def test_existe_una_pestana_titulada_usuarios(self, app, bd_temporal):
        w = MainWindow(Usuario(username="lamaya", fullname="Luz Adriana Maya"))
        titulos = [w.tabs.tabText(i) for i in range(w.tabs.count())]
        assert "Usuarios" in titulos

    def test_usuarios_sigue_justo_despues_de_las_nueve_previas(self, app, bd_temporal):
        w = MainWindow(Usuario(username="lamaya", fullname="Luz Adriana Maya"))
        assert w.tabs.tabText(len(TITULOS_PREVIOS)) == "Usuarios"
        assert w.tabs.count() == len(TITULOS_PREVIOS) + 2  # Usuarios + Referencias (C.2)

    def test_la_pestana_usuarios_carga_el_widget_real_al_visitarla(
            self, app, bd_temporal):
        """No solo el título -- el factory `Usuarios()` debe devolver el
        widget real (no el QWidget vacío de fallback de una excepción
        tragada en silencio)."""
        from ui.paginasGuia.usuarios import Usuarios as PestanaUsuarios

        w = MainWindow(Usuario(username="lamaya", fullname="Luz Adriana Maya"))
        indice_usuarios = len(TITULOS_PREVIOS)
        w._cargar_pestania_diferida(indice_usuarios)
        widget_real = w._tab_instancias[indice_usuarios]
        assert isinstance(widget_real, PestanaUsuarios)
