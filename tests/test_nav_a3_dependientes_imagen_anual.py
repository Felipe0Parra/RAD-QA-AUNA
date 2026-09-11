"""A.3 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS2, DP-95 SS0.5b): cerrar el
Anual no debe dejar páginas huérfanas de "Imágenes Anual" escribiendo
contra el `ref` de un control ya destruido. `imagen_anual` copia el `ref`
de la página anual EN LA CONSTRUCCIÓN (`mainpages.py::_crear_pagina`,
clave "imagen_anual") -- si esa página sobrevive al cierre del anual
(el `QStackedWidget` reparenta lo que se le agrega, así que no muere sola
con su dueño), sigue apuntando al control viejo.

Orden peligroso, a propósito: abrir "Imágenes Anual" ANTES de cerrar el
Anual -- es el orden que expone el acoplamiento.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.mainpages import Menuu


class _UsuarioFalso:
    _nombre = "Fisico Uno"
    _usuario = "f1"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    """A.4: `_cerrar_control` pide confirmación con `.question` -- por
    defecto confirma (Yes), Trampa 2 (mockear o la suite cuelga)."""
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES ('f1', 'x', 'Fisico Uno', 1, '1', 'Físico Médico', 'fisico')")
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


# PruebaAnualIX no guarda self.lista_maquina -- lo calcula PruebaMensual600.
# __init__ como variable local, a partir de equipo_f="Clinac ix" + anual=True.
LISTA_MAQUINA_ANUAL_IX = ['encabezado_anual_ix', 'Control anual',
                          'Iniciar control anual', 'Clinac ix', 'preguntas_anual_ix']


def _iniciar(pagina):
    indice = pagina.fisico1.findText(pagina.user_id._nombre)
    assert indice >= 0, "El fisico de prueba no aparece en el combo"
    pagina.fisico1.setCurrentIndex(indice)
    lista_maquina = getattr(pagina, "lista_maquina", LISTA_MAQUINA_ANUAL_IX)
    pagina._iniciar_moviendo_tabla(lista_maquina)
    assert getattr(pagina, "ref", None) is not None, (
        "create_control no creo el control anual -- Iniciar no tuvo exito")


class TestCerrarAnualInvalidaImagenAnual:
    def test_orden_peligroso_imagen_anual_no_sobrevive_al_cierre(self, app, bd_temporal):
        menuu = Menuu("iX", _UsuarioFalso())

        menuu._mostrar_pagina("anual")
        pagina_anual_vieja = menuu._paginas["anual"]
        _iniciar(pagina_anual_vieja)

        # Orden peligroso: abrir "Imagenes Anual" ANTES de cerrar el Anual.
        menuu._mostrar_pagina("imagen_anual")
        pagina_img_vieja = menuu._paginas["imagen_anual"]
        assert pagina_img_vieja.ref == pagina_anual_vieja.ref

        menuu._mostrar_pagina("anual")  # volver a poner "anual" como visible
        menuu._cerrar_control()

        # La pagina dependiente no puede seguir en el cache -- ni la del
        # anual viejo.
        assert "imagen_anual" not in menuu._paginas
        assert "anual" in menuu._paginas
        pagina_anual_nueva = menuu._paginas["anual"]
        assert pagina_anual_nueva is not pagina_anual_vieja

        # La referencia que "imagen_anual" usaria para copiar el ref ya no
        # apunta a la instancia destruida.
        assert menuu._pagina_anual_ix is pagina_anual_nueva

        # Pedirla de nuevo es una instancia DISTINTA, y toma el ref de la
        # instancia anual actual (create_control es idempotente por
        # (equipo, mes, año) -- reabrir el mismo mes vuelve a dar el mismo
        # id, así que la garantía no es "otro número": es que resuelve
        # contra la página VIVA, no contra el objeto ya destruido).
        _iniciar(pagina_anual_nueva)
        menuu._mostrar_pagina("imagen_anual")
        pagina_img_nueva = menuu._paginas["imagen_anual"]
        assert pagina_img_nueva is not pagina_img_vieja
        assert pagina_img_nueva.ref == pagina_anual_nueva.ref
