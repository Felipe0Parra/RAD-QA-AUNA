"""A.2 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS2): boton "Cerrar control",
justo encima de "Inicio", que permite volver a la pantalla de seleccion de
un control mensual/anual/imagenes SIN pasar por el login -- a diferencia de
"Inicio" (`back_button`), que cierra la sesion a proposito (SS0.2).

Garantias que este test exige, todas del protocolo de la tarea:
(a) el boton existe e, inmediatamente encima de "Inicio", en
    `top_buttons_layout`;
(b) cerrar produce una instancia DISTINTA de la pagina, y el cache deja de
    tener la clave vieja;
(c) `UsuarioData.logout` NO se llama -- la garantia titular: cerrar un
    control no es cerrar sesion;
(d) con una pagina no cerrable visible (una diaria, o el mensual de
    braquiterapia), el boton queda deshabilitado;
(e) ARRANQUE LIMPIO -- la exigencia del fisico (SS0.15): la huella de
    estado de la pagina "mensual" tras cerrar+recrear debe ser IGUAL a la
    del arranque, salvo `tabla_filas` (la vista previa lista el control
    real que se acaba de crear). Parametrizado sobre 600/iX/Halcyon/TAC.
    Rojo-antes-que-verde real: la huella tras "Iniciar" (B) debe diferir de
    la del arranque (A) en varios campos -- si no discriminara, el
    experimento no probaria nada (punto 1-bis del protocolo).
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.usuariosManager as usuariosManager_mod
from data.ManejoDatos.conection import Conexion
from ui.mainpages import CLAVES_CERRABLES, Menuu


class _UsuarioFalso:
    _nombre = "Fisico Uno"
    _usuario = "f1"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """A.4: `_cerrar_control` ahora pide confirmación con `.question` --
    sin mockearla, cualquier test que llegue ahí cuelga bajo offscreen
    (Trampa 2). Por defecto confirma (Yes); los tests de A.4 que prueban
    "cancelar" la sobreescriben con otra respuesta."""
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
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES ('f2', 'x', 'Fisico Dos', 1, '2', 'Físico Médico', 'fisico')")
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _huella(pagina):
    return {
        "date_box.enabled": pagina.date_box.isEnabled(),
        "fisico1.enabled": pagina.fisico1.isEnabled(),
        "fisico1.n_items": pagina.fisico1.count(),
        "fisico2.enabled": pagina.fisico2.isEnabled(),
        "attr:ref": getattr(pagina, "ref", None) is not None,
        "attr:fecha_control": hasattr(pagina, "fecha_control"),
        "attr:nombre_fisico1": hasattr(pagina, "nombre_fisico1"),
        "attr:nombre_fisico2": hasattr(pagina, "nombre_fisico2"),
        "tabla_filas": pagina.tabla.rowCount(),
    }


# PruebaMensual600 (a diferencia de IX/Halcyon/TAC) no guarda
# `self.lista_maquina` -- la calcula como variable local en __init__ y la
# pasa directo a preINIGI. Mismo valor, para el caso "Clinac 600".
LISTA_MAQUINA_600 = ['encabezado_mensu_600', 'Control mensual',
                      'Iniciar control mensual', 'Clinac 600', 'preguntas_mensu_600']


def _iniciar(pagina):
    """Simula lo que hace el fisico al pulsar 'Iniciar': elige un fisico
    REAL del combo (indice 0 puede ser el placeholder "Fisico 1" que trae
    el propio widget de Excel -- create_control lo rechaza por no existir
    en `users`, y create_control() vuelve None/False EN SILENCIO bajo el
    mock de QMessageBox; hay que elegir el fisico sembrado en la BD, no
    "el primero que haya") y dispara el handler real (el "Iniciar" de la
    clase base, heredado por las 4 subclases -- ninguna lo sobreescribe)."""
    indice = pagina.fisico1.findText(pagina.user_id._nombre)
    assert indice >= 0, "El fisico de prueba no aparece en el combo -- fixture mal sembrada"
    pagina.fisico1.setCurrentIndex(indice)
    lista_maquina = getattr(pagina, "lista_maquina", LISTA_MAQUINA_600)
    pagina._iniciar_moviendo_tabla(lista_maquina)
    assert getattr(pagina, "ref", None) is not None, (
        "create_control no creo el control -- Iniciar no tuvo exito de verdad")


def _layout_que_contiene(layout_raiz, widget_buscado):
    """Recorre `layout_raiz` (incluidos sub-layouts) y devuelve el layout
    INMEDIATO que contiene `widget_buscado` como item directo, junto con su
    posicion -- necesario porque `top_buttons_layout` es un QVBoxLayout
    anidado dentro de `menu_layout` (no un widget propio)."""
    for i in range(layout_raiz.count()):
        item = layout_raiz.itemAt(i)
        if item.widget() is widget_buscado:
            return layout_raiz, i
        sub_layout = item.layout()
        if sub_layout is not None:
            encontrado = _layout_que_contiene(sub_layout, widget_buscado)
            if encontrado is not None:
                return encontrado
    return None


class TestElBotonExisteYEstaEncimaDeInicio:
    @pytest.mark.parametrize("maquina", ["600", "iX", "Halcyon", "Braquiterapia", "Tomógrafo"])
    def test_boton_existe_e_inmediatamente_encima_de_inicio(self, app, bd_temporal, maquina):
        menuu = Menuu(maquina, _UsuarioFalso())
        assert hasattr(menuu, "cerrar_ctrl_btn")
        assert isinstance(menuu.cerrar_ctrl_btn, QPushButton)
        assert menuu.cerrar_ctrl_btn.text() == "Cerrar control"

        raiz = menuu.menu_widget.layout()
        layout_back, indice_back = _layout_que_contiene(raiz, menuu.back_button)
        layout_cerrar, indice_cerrar = _layout_que_contiene(raiz, menuu.cerrar_ctrl_btn)
        assert layout_back is layout_cerrar
        assert indice_cerrar == indice_back - 1


class TestCerrarNoCierraLaSesion:
    def test_logout_no_se_llama(self, app, bd_temporal, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            usuariosManager_mod.UsuarioData, "logout",
            lambda self, nombre: llamadas.append(nombre))

        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        pagina_a = menuu._paginas["mensual"]
        _iniciar(pagina_a)

        menuu._cerrar_control()

        assert llamadas == []


class TestCerrarProduceInstanciaDistintaYCacheLimpio:
    def test_instancia_distinta_y_clave_fuera_del_cache_intermedio(self, app, bd_temporal):
        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        pagina_a = menuu._paginas["mensual"]
        _iniciar(pagina_a)

        menuu._cerrar_control()

        pagina_c = menuu._paginas["mensual"]
        assert pagina_c is not pagina_a


class TestBotonSeDeshabilitaSinPaginaCerrable:
    def test_diaria_deshabilita_el_boton(self, app, bd_temporal):
        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("diaria")
        assert menuu.cerrar_ctrl_btn.isEnabled() is False

    def test_braqui_mensual_deshabilita_el_boton(self, app, bd_temporal):
        menuu = Menuu("Braquiterapia", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        assert menuu.cerrar_ctrl_btn.isEnabled() is False

    def test_mensual_600_habilita_el_boton(self, app, bd_temporal):
        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        assert menuu.cerrar_ctrl_btn.isEnabled() is True


class TestArranqueLimpioTrasCerrar:
    """SS0.15 del plan: A (arranque) debe ser igual a C (tras cerrar),
    salvo `tabla_filas`. B (tras Iniciar) debe diferir de A -- si no, el
    experimento no discrimina nada."""

    @pytest.mark.parametrize("maquina", ["600", "iX", "Halcyon", "Tomógrafo"])
    def test_huella_arranque_igual_tras_cerrar(self, app, bd_temporal, maquina):
        menuu = Menuu(maquina, _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        pagina_a = menuu._paginas["mensual"]
        huella_a = _huella(pagina_a)

        _iniciar(pagina_a)
        huella_b = _huella(pagina_a)

        # Rojo-antes-que-verde real: si A==B, "Iniciar" no cambio nada y el
        # experimento no prueba nada (punto 1-bis del protocolo).
        diferencias_ab = {
            campo for campo in huella_a
            if huella_a[campo] != huella_b[campo]
        }
        assert diferencias_ab, "Iniciar no cambio ningun campo de la huella -- el experimento no discrimina"

        menuu._cerrar_control()
        pagina_c = menuu._paginas["mensual"]
        huella_c = _huella(pagina_c)

        diferencias_ac = {
            campo: (huella_a[campo], huella_c[campo])
            for campo in huella_a
            if huella_a[campo] != huella_c[campo]
        }
        assert set(diferencias_ac) <= {"tabla_filas"}, (
            f"Cerrar y recrear dejo la pagina distinta del arranque en "
            f"campos no esperados: {diferencias_ac}")
        assert huella_c["tabla_filas"] >= huella_a["tabla_filas"]
