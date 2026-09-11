"""A.4 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS2): cerrar un control destruye
el formulario en pantalla -- lo ya subido está a salvo (cada sección tiene
su "Subir"), pero lo tecleado y no subido se pierde. "Cerrar control" está
justo encima de "Inicio" en la barra lateral: un clic de más no debe costar
un formulario. `QMessageBox.question` antes de descartar, sin símbolos
(DA-18).
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
def _sin_dialogos_bloqueantes(monkeypatch):
    for tipo in ("information", "warning", "critical"):
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


def _mock_confirmacion(monkeypatch, respuesta):
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: respuesta))


class TestResponderNoDejaLaInstanciaIntacta:
    def test_no_deja_la_misma_instancia_y_el_cache_intacto(self, app, bd_temporal, monkeypatch):
        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        pagina_antes = menuu._paginas["mensual"]

        _mock_confirmacion(monkeypatch, QMessageBox.No)
        menuu._cerrar_control()

        assert menuu._paginas["mensual"] is pagina_antes

    @pytest.mark.parametrize("respuesta_de_cierre", [
        QMessageBox.Cancel, QMessageBox.NoButton, QMessageBox.Escape,
    ])
    def test_cerrar_el_aviso_sin_aceptar_tampoco_ejecuta_la_accion(
            self, app, bd_temporal, monkeypatch, respuesta_de_cierre):
        """Exigencia explícita del físico: cancelar el aviso NO debe
        ejecutar el cierre -- de ninguna de las formas en que Qt reporta
        un diálogo cerrado sin aceptar (nunca comparar == No, siempre
        != Yes)."""
        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        pagina_antes = menuu._paginas["mensual"]

        _mock_confirmacion(monkeypatch, respuesta_de_cierre)
        menuu._cerrar_control()

        assert menuu._paginas["mensual"] is pagina_antes


class TestResponderSiReemplazaLaInstancia:
    def test_si_descarta_y_recrea(self, app, bd_temporal, monkeypatch):
        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        pagina_antes = menuu._paginas["mensual"]

        _mock_confirmacion(monkeypatch, QMessageBox.Yes)
        menuu._cerrar_control()

        assert menuu._paginas["mensual"] is not pagina_antes


class TestElAvisoNoUsaSimbolos:
    def test_el_texto_del_aviso_no_lleva_simbolos(self, app, bd_temporal, monkeypatch):
        """DA-18: sin chulito/equis/advertencia en los textos que ve el
        físico."""
        capturado = {}

        def _question_espia(self_widget, titulo, texto, *a, **k):
            capturado["texto"] = texto
            return QMessageBox.Yes

        monkeypatch.setattr(QMessageBox, "question", _question_espia)

        menuu = Menuu("600", _UsuarioFalso())
        menuu._mostrar_pagina("mensual")
        menuu._cerrar_control()

        texto = capturado["texto"]
        for simbolo in ("✓", "✗", "⚠", "❌", "✔"):
            assert simbolo not in texto
