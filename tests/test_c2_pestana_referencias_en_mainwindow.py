"""C.2 (PLAN_REFERENCIAS_EDITABLES_21-09.md): la pestaña "Referencias" entra
a `MainWindow` AL FINAL de `_tab_definiciones` -- `_cargar_pestania_diferida`
indexa esa lista por POSICIÓN y `block()` referencia índices comentados, así
que insertar en medio movería pestañas existentes (precedente: U6).

Garantía: *"la pestaña nueva no mueve ninguna de las que ya estaban."* Lista
literal de las 10 pestañas previas (las 9 de U6 más "Usuarios"): mover o
reordenar cualquiera de ellas pone este test en rojo.
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
    "Equipos", "Excel", "Registros", "Visor BD", "Usuarios",
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """Trampa 2: los cuatro tipos, incluidos los de éxito."""
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    for user, fullname, rol in (("lamaya", "Luz Adriana Maya", "jefe"),
                                ("jjcastillo", "Javier Castillo", "fisico")):
        con.execute(
            "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
            "VALUES (?, 'x', ?, 1, '1', 'Físico Médico', ?)", (user, fullname, rol))
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _ventana(user="lamaya", fullname="Luz Adriana Maya"):
    return MainWindow(Usuario(username=user, fullname=fullname))


class TestPestanaReferenciasEnMainWindow:
    def test_las_diez_previas_conservan_titulo_e_indice(self, app, bd_temporal):
        w = _ventana()
        titulos = [w.tabs.tabText(i) for i in range(len(TITULOS_PREVIOS))]
        assert titulos == TITULOS_PREVIOS

    def test_referencias_es_la_ultima_y_no_hay_otra_nueva(self, app, bd_temporal):
        w = _ventana()
        assert w.tabs.tabText(w.tabs.count() - 1) == "Referencias"
        assert w.tabs.count() == len(TITULOS_PREVIOS) + 1

    def test_la_lista_de_definiciones_coincide_con_las_pestanas_visibles(
            self, app, bd_temporal):
        """`_cargar_pestania_diferida` indexa la lista por posición: si
        divergiera de las pestañas mostradas, abrir una cargaría otra."""
        w = _ventana()
        assert [t for t, _ in w._tab_definiciones] == [
            w.tabs.tabText(i) for i in range(w.tabs.count())]

    def test_la_pestana_carga_el_widget_real_al_visitarla(self, app, bd_temporal):
        """No solo el título: el factory debe devolver la pantalla real (no
        el QWidget vacío de fallback de una excepción tragada en silencio)."""
        from ui.paginasGuia.referencias import Referencias as PestanaReferencias

        w = _ventana()
        indice = w.tabs.count() - 1
        w._cargar_pestania_diferida(indice)
        assert isinstance(w._tab_instancias[indice], PestanaReferencias)

    def test_el_jefe_llega_con_los_controles_habilitados(self, app, bd_temporal):
        w = _ventana("lamaya", "Luz Adriana Maya")
        indice = w.tabs.count() - 1
        w._cargar_pestania_diferida(indice)
        assert w._tab_instancias[indice].btn_fijar.isEnabled()

    def test_un_fisico_llega_en_solo_lectura(self, app, bd_temporal):
        """La identidad de la sesión llega a la pantalla (`self.user_id`),
        no solo el widget."""
        w = _ventana("jjcastillo", "Javier Castillo")
        indice = w.tabs.count() - 1
        w._cargar_pestania_diferida(indice)
        pantalla = w._tab_instancias[indice]
        assert not pantalla.btn_fijar.isEnabled()
        assert hasattr(pantalla, "banda_solo_lectura")

    def test_visitar_la_pestana_no_carga_ninguna_otra(self, app, bd_temporal):
        """Carga diferida intacta: solo la visitada (y la inicial) se crean."""
        w = _ventana()
        antes = set(w._tab_instancias)
        w._cargar_pestania_diferida(w.tabs.count() - 1)
        assert set(w._tab_instancias) - antes == {w.tabs.count() - 1}
