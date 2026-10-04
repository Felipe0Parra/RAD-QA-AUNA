"""PI.6 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md): el boton "Posicion inicial" de la barra lateral de braquiterapia y el retiro de
la entrada vieja ("Posicionamiento Inicial" del menu de "Cal. Fuente").

Garantias que este archivo exige (la intuicion del plan: *"en braquiterapia hay un boton 'Posicion inicial' y ya no queda el
camino viejo"*):
  (a) el boton existe SOLO en braquiterapia, justo debajo de "Cal. Fuente" y encima de "Cerrar control" (A.2 exige "Cerrar
      control" inmediatamente encima de "Inicio");
  (b) pulsarlo muestra una `PosicionInicialBraqui` (clave "posicion_inicial", una sola instancia en la cache);
  (c) el menu de "Cal. Fuente" queda con "Calibracion Redundante" y "Linealidad de la Fuente";
  (d) `_crear_pagina("posicionamiento")` devuelve `None` y ya no construye el mensual para ir a buscar la pagina vieja;
  (e) "Cerrar control" queda deshabilitado sobre la pagina nueva (no es cerrable);
  (f) compuerta SS6.5: la barra lateral de las 5 maquinas es la de HEAD (texto, orden y estado de cada boton) salvo el cambio
      declarado de braquiterapia; la huella esperada se capturo del HEAD de PI.5 (`logs/PI6/huella_antes.json` del anexo).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton

from ui.mainpages import CLAVES_CERRABLES, Menuu
from ui.paginasControles.PruebasMensuales.posicion_inicial_braqui import PosicionInicialBraqui
from test_nav_a2_cerrar_control import (  # noqa: F401  (fixtures y ayudas de A.2)
    _UsuarioFalso, _layout_que_contiene, app, bd_temporal)

MAQUINAS = ["600", "iX", "Halcyon", "Braquiterapia", "Tomógrafo"]

# La barra de HEAD (PI.5), tal como la dejo `pi6_huella_barra.py` antes de tocar nada: (texto, habilitado) por boton, en orden.
BARRA_DE_HEAD = {
    "600": [("Diaria", True), ("Mensual", True), ("Anual", True), ("Cerrar control", False), ("Inicio", True)],
    "iX": [("Diaria", True), ("Mensual", True), ("Anual", True), ("Imágenes\nMensual", True), ("Imágenes\nAnual", True),
           ("Cerrar control", False), ("Inicio", True)],
    "Halcyon": [("Diaria", True), ("Mensual", True), ("Anual", True), ("Imágenes\nMensual", True), ("Imágenes\nAnual", True),
                ("Cerrar control", False), ("Inicio", True)],
    "Braquiterapia": [("Diaria", True), ("Mensual", True), ("Cal. Fuente", True), ("Cerrar control", False), ("Inicio", True)],
    "Tomógrafo": [("Mensual", True), ("Anual", True), ("Cerrar control", True), ("Inicio", True)],
}
BARRA_NUEVA_DE_BRAQUITERAPIA = [("Diaria", True), ("Mensual", True), ("Cal. Fuente", True), ("Posición inicial", True),
                                ("Cerrar control", False), ("Inicio", True)]
MENU_DE_HEAD = ["Calibración Redundante", "Linealidad de la Fuente", "Posicionamiento Inicial"]
MENU_NUEVO = ["Calibración Redundante", "Linealidad de la Fuente"]


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture
def barra(app, bd_temporal):
    """Construye `Menuu` y lo cierra de verdad al terminar (Trampa 9: una pagina viva deja huellas en la siguiente prueba)."""
    creados = []

    def fabricar(maquina):
        menuu = Menuu(maquina, _UsuarioFalso())
        creados.append(menuu)
        return menuu

    yield fabricar
    for menuu in creados:
        menuu.hide()
        menuu.close()
        menuu.deleteLater()


def _botones(menuu):
    """(texto, habilitado) de cada `QPushButton` de la columna de botones, en el orden en que aparecen."""
    def recorrer(layout):
        filas = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if isinstance(item.widget(), QPushButton):
                filas.append((item.widget().text(), item.widget().isEnabled()))
            elif item.layout() is not None:
                filas.extend(recorrer(item.layout()))
        return filas
    return recorrer(menuu.menu_widget.layout())


class TestElBotonYSuPosicion:
    @pytest.mark.parametrize("maquina", [m for m in MAQUINAS if m != "Braquiterapia"])
    def test_01_solo_existe_en_braquiterapia(self, barra, maquina):
        menuu = barra(maquina)
        assert not hasattr(menuu, "pi_btn")
        assert "Posición inicial" not in [t for t, _ in _botones(menuu)]

    def test_02_en_braquiterapia_existe_justo_debajo_de_cal_fuente_y_encima_de_cerrar_control(self, barra):
        menuu = barra("Braquiterapia")
        assert isinstance(menuu.pi_btn, QPushButton)
        assert menuu.pi_btn.text() == "Posición inicial"
        raiz = menuu.menu_widget.layout()
        capa_pi, i_pi = _layout_que_contiene(raiz, menuu.pi_btn)
        capa_cf, i_cf = _layout_que_contiene(raiz, menuu.cf_btn)
        capa_cerrar, i_cerrar = _layout_que_contiene(raiz, menuu.cerrar_ctrl_btn)
        capa_inicio, i_inicio = _layout_que_contiene(raiz, menuu.back_button)
        assert capa_pi is capa_cf is capa_cerrar is capa_inicio
        assert (i_cf, i_pi, i_cerrar, i_inicio) == (i_pi - 1, i_cf + 1, i_pi + 1, i_pi + 2)

    def test_03_el_boton_nuevo_no_cambia_la_regla_de_a2(self, barra):
        # A.2 exige "Cerrar control" inmediatamente encima de "Inicio": sigue cumpliendose con el boton nuevo entre medias.
        menuu = barra("Braquiterapia")
        raiz = menuu.menu_widget.layout()
        capa_cerrar, i_cerrar = _layout_que_contiene(raiz, menuu.cerrar_ctrl_btn)
        capa_inicio, i_inicio = _layout_que_contiene(raiz, menuu.back_button)
        assert capa_cerrar is capa_inicio and i_cerrar == i_inicio - 1

    def test_04_el_orden_completo_de_la_barra_de_braquiterapia(self, barra):
        assert _botones(barra("Braquiterapia")) == BARRA_NUEVA_DE_BRAQUITERAPIA


class TestPulsarElBoton:
    def test_10_muestra_una_pagina_de_posicion_inicial(self, barra):
        menuu = barra("Braquiterapia")
        assert menuu._clave_actual == "diaria"
        menuu.pi_btn.click()
        assert menuu._clave_actual == "posicion_inicial"
        pagina = menuu.pages_widget.currentWidget()
        assert isinstance(pagina, PosicionInicialBraqui)
        assert menuu._paginas["posicion_inicial"] is pagina

    def test_11_la_pagina_recibe_el_objeto_de_usuario_de_la_sesion(self, barra):
        menuu = barra("Braquiterapia")
        menuu.pi_btn.click()
        assert menuu.pages_widget.currentWidget().user_id is menuu.user_id

    def test_12_pulsarlo_dos_veces_no_crea_otra_pagina(self, barra):
        menuu = barra("Braquiterapia")
        menuu.pi_btn.click()
        primera = menuu.pages_widget.currentWidget()
        menuu.pm_btn.click()
        assert menuu.pages_widget.currentWidget() is not primera
        menuu.pi_btn.click()
        assert menuu.pages_widget.currentWidget() is primera
        assert list(menuu._paginas).count("posicion_inicial") == 1

    def test_13_no_es_cerrable_y_cerrar_control_queda_deshabilitado(self, barra):
        assert "posicion_inicial" not in CLAVES_CERRABLES
        menuu = barra("Braquiterapia")
        menuu.pi_btn.click()
        assert menuu.cerrar_ctrl_btn.isEnabled() is False

    def test_14_no_construye_el_mensual_ni_toca_la_pagina_vieja(self, barra):
        menuu = barra("Braquiterapia")
        menuu.pi_btn.click()
        assert "mensual" not in menuu._paginas
        assert "posicionamiento" not in menuu._paginas

    @pytest.mark.parametrize("maquina", [m for m in MAQUINAS if m != "Braquiterapia"])
    def test_15_en_otra_maquina_la_clave_no_construye_nada(self, barra, maquina):
        menuu = barra(maquina)
        assert menuu._crear_pagina("posicion_inicial") is None


class TestYaNoQuedaElCaminoViejo:
    def test_20_el_menu_de_cal_fuente_ya_no_tiene_la_accion_vieja(self, barra):
        menuu = barra("Braquiterapia")
        assert [a.text() for a in menuu.cf_btn.menu().actions()] == MENU_NUEVO

    def test_21_crear_pagina_posicionamiento_devuelve_none_sin_construir_el_mensual(self, barra):
        menuu = barra("Braquiterapia")
        assert menuu._crear_pagina("posicionamiento") is None
        assert "mensual" not in menuu._paginas
        assert menuu._obtener_pagina("posicionamiento") is None
        assert "posicionamiento" not in menuu._paginas

    def test_22_el_selector_del_menu_no_sabe_ir_a_la_pagina_vieja(self, barra):
        menuu = barra("Braquiterapia")
        menuu.seleccionar_cambio_fuente("Posicionamiento Inicial")
        assert menuu._clave_actual == "diaria"
        assert "posicionamiento" not in menuu._paginas and "mensual" not in menuu._paginas

    def test_23_las_otras_dos_entradas_del_menu_siguen_funcionando(self, barra):
        menuu = barra("Braquiterapia")
        menuu.seleccionar_cambio_fuente("Calibración Redundante")
        assert menuu._clave_actual == "cal_fuente"
        menuu.seleccionar_cambio_fuente("Linealidad de la Fuente")
        assert menuu._clave_actual == "linealidad"

    def test_24_el_codigo_ya_no_nombra_la_entrada_vieja(self):
        import inspect
        import ui.mainpages as mp
        fuente = inspect.getsource(mp)
        for resto in ("posicionamiento_action", "Posicionamiento Inicial", 'clave == "posicionamiento"',
                      '_mostrar_pagina("posicionamiento")'):
            assert resto not in fuente, f"queda un resto del camino viejo: {resto}"


class TestCompuertaDeLaBarraLateral:
    """SS6.5: lo que el plan NO nombra no cambia. La huella (texto, orden, estado) de las 5 maquinas es la de HEAD."""

    @pytest.mark.parametrize("maquina", MAQUINAS)
    def test_30_la_barra_es_la_de_head_salvo_el_cambio_declarado(self, barra, maquina):
        esperado = BARRA_NUEVA_DE_BRAQUITERAPIA if maquina == "Braquiterapia" else BARRA_DE_HEAD[maquina]
        assert _botones(barra(maquina)) == esperado

    @pytest.mark.parametrize("maquina", MAQUINAS)
    def test_31_la_pagina_inicial_y_el_boton_de_cerrar_no_cambian(self, barra, maquina):
        menuu = barra(maquina)
        assert menuu._clave_actual == ("mensual" if maquina == "Tomógrafo" else "diaria")

    def test_32_solo_braquiterapia_tiene_menu_en_la_barra(self, barra):
        for maquina in MAQUINAS:
            menuu = barra(maquina)
            assert hasattr(menuu, "cf_btn") == (maquina == "Braquiterapia")

    def test_33_el_boton_nuevo_se_conecta_una_vez(self, barra):
        # Una conexion duplicada ejecutaria dos veces `_mostrar_pagina` por clic (Trampa de PI.4/test_26f).
        menuu = barra("Braquiterapia")
        llamadas = []
        original = menuu._mostrar_pagina
        menuu._mostrar_pagina = lambda clave: (llamadas.append(clave), original(clave))[1]
        # Las conexiones se hicieron con lambdas que resuelven `self._mostrar_pagina` en cada disparo: el espia las ve.
        menuu.pi_btn.click()
        assert llamadas == ["posicion_inicial"]
