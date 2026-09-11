"""E.1 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §6, DP-99): el reporte mensual
de Halcyon SÍ se genera (9 tablas, sin errores) y el botón SÍ existe -- lo
que pasa es dónde está. `halcyon_mensual.py` lo añadía a
`self.category3.layout()`, que es la SEGUNDA página de un `QToolBox`
(`self.subtool1`, índice 1, "Constancia del haz de radiación") con el
toolbox exterior en `currentIndex = 0` -- plegado. El del 600 va en
`self.general_layout`, siempre a la vista. Mismo patrón que DP-83: dos
pantallas que deberían comportarse igual y divergen en silencio.

Reparación: una línea -- el botón pasa a `self.general_layout`, igual que
el 600. No toca la generación del reporte, que ya funciona.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QToolBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc


class _UsuarioFalso:
    _nombre = "Fisico Uno"
    _usuario = "f1"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
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
        "VALUES ('f1', 'x', 'Fisico Uno', 1, '1', 'Físico Médico', 'fisico')")
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


# PruebaMensual600 (a diferencia de PruebaMensualHc) no guarda
# self.lista_maquina -- la calcula como variable local en __init__.
LISTA_MAQUINA_600 = ['encabezado_mensu_600', 'Control mensual',
                      'Iniciar control mensual', 'Clinac 600', 'preguntas_mensu_600']


def _iniciar(pagina):
    """`generar_reporte_btn` solo existe tras 'Iniciar' -- lo crea
    `controlTestWindow`, llamado desde `iniGUI`, que preINIGI conecta al
    click del botón (nunca antes). El indice 0 del combo puede ser el
    placeholder "Fisico 1" que trae el propio widget de Excel -- hay que
    elegir el fisico REAL sembrado en la BD, o create_control lo rechaza
    en silencio bajo el mock de QMessageBox."""
    indice = pagina.fisico1.findText(pagina.user_id._nombre)
    assert indice >= 0, "El fisico de prueba no aparece en el combo -- fixture mal sembrada"
    pagina.fisico1.setCurrentIndex(indice)
    lista_maquina = getattr(pagina, "lista_maquina", LISTA_MAQUINA_600)
    pagina._iniciar_moviendo_tabla(lista_maquina)
    assert getattr(pagina, "ref", None) is not None, (
        "create_control no creo el control -- Iniciar no tuvo exito de verdad")


def _dentro_de_un_toolbox(widget):
    """Recorre la jerarquía de padres reales de Qt -- no la de layouts --
    buscando un QToolBox ancestro. Devuelve el título de la página si lo
    encuentra, o None si el botón está a la vista directa.

    `QToolBox.indexOf()` solo reconoce el widget EXACTO que se pasó a
    `addItem()` -- por dentro, cada página queda envuelta en un
    QScrollArea propio de Qt, así que comparar contra el padre inmediato
    nunca matchea. Hay que preguntarle a cada página del toolbox si ES
    ancestro (o el propio) del widget que se está buscando."""
    actual = widget.parentWidget()
    while actual is not None:
        if isinstance(actual, QToolBox):
            for i in range(actual.count()):
                pagina = actual.widget(i)
                if pagina is widget or pagina.isAncestorOf(widget):
                    return actual.itemText(i)
        actual = actual.parentWidget()
    return None


class TestBotonDeReporteNoEnterradoEnUnToolbox:
    def test_halcyon_el_boton_ya_no_esta_dentro_de_un_toolbox(self, app, bd_temporal):
        pagina = PruebaMensualHc(_UsuarioFalso())
        _iniciar(pagina)
        pagina_toolbox = _dentro_de_un_toolbox(pagina.generar_reporte_btn)
        assert pagina_toolbox is None, (
            f"El botón de reporte de Halcyon sigue enterrado en la página "
            f"{pagina_toolbox!r} de un QToolBox plegado")

    def test_600_el_boton_nunca_estuvo_dentro_de_un_toolbox(self, app, bd_temporal):
        pagina = PruebaMensual600(_UsuarioFalso(), equipo_f="Clinac 600")
        _iniciar(pagina)
        assert _dentro_de_un_toolbox(pagina.generar_reporte_btn) is None
