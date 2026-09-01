"""B0/B1 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase B, R3/R4).

**B0**: causa raíz de `tamano_campo='1'` repetido, medida en el traceback
del handoff (`ref=19`). La columna 0 de una tabla anual (`"Tamaño de
campo"`, `"Accesorio"`, `"Banco"`...) es un identificador FIJO -- nunca
algo que el físico deba escribir -- salvo en
`HC_precision_posicion_multilaminas_anual`, cuyas 3 columnas (incluida la
0, `"Medida (cm)"`) nacen vacías porque ahí sí es un dato real. Antes,
`editar_primera_columna=True` se pasaba fijo para TODAS las tablas por
defecto, así que el físico podía sobreescribir el identificador -- lo que
el rebuild capturó como `tamano_campo='1'` en varias filas.

**B1**: `ix_anual.py::guardar_todas_fse` es una copia de la función que
`seiscientos_anual.py` ya tiene corregida (AV1) -- ignoraba el `bool` que
`loadtablacomplex` devuelve. Medido: `ref=19`, `id_energia=1`, el índice
UNIQUE de CL1 rechazó el bloque (la basura de B0/R4 lo produjo) y la
terminal igual imprimía "subida(s) correctamente". Se copió la misma
transformación que AV1 aplicó al gemelo.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

import ui.paginasControles.PruebasAnuales.ix_anual as ix_anual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _obj_ix_anual(ref=19):
    obj = ix_anual_mod.PruebaAnualIX.__new__(ix_anual_mod.PruebaAnualIX)
    QWidget.__init__(obj)
    obj.ref = ref
    obj.user_id = _UsuarioFalso()
    obj.anual = True
    obj.tablas_fc = []
    obj.tablas_fta = []
    obj.tablas_ccm = []
    return obj


def _click_subir(obj, monkeypatch, nombre_tabla="tabla_factor_campo", id_energia=1):
    """Llama _agregar_botones_tabla (que crea el closure guardar_todas_fse
    dentro) y simula el click en "Subir" -- guardar_todas_fse no es
    accesible directamente, es una función anidada."""
    layout = QVBoxLayout()
    table = QTableWidget()
    obj.tablas_fc = [{'tabla': table, 'id_energia': id_energia}]
    obj._agregar_botones_tabla(layout, table, nombre_tabla, obj.ref, id=True, id_energia=id_energia)
    # El botón "Subir" fue agregado a un button_layout dentro de layout.
    boton = layout.itemAt(0).layout().itemAt(0).widget()
    assert isinstance(boton, QPushButton) and boton.text() == "Subir"
    boton.click()


class TestB1UsaElRetornoDeLoadtablacomplex:

    def test_fallo_avisa_con_critical_y_no_audita(self, app, monkeypatch):
        monkeypatch.setattr(ix_anual_mod, "loadtablacomplex", lambda *a, **k: False)
        avisos = {"critical": []}
        monkeypatch.setattr(QMessageBox, "critical",
                            lambda *a, **k: avisos["critical"].append(a[1:]))
        auditorias = []
        monkeypatch.setattr(ix_anual_mod, "_registrar_auditoria",
                            lambda *a, **k: auditorias.append((a, k)))
        obj = _obj_ix_anual()
        obj._actualizar_tabla_despues_subida = lambda: None

        _click_subir(obj, monkeypatch)

        assert len(avisos["critical"]) == 1, (
            "un guardado rechazado por la BD debe avisarse -- antes se "
            "imprimía 'subida correctamente' sin importar el resultado")
        assert auditorias == [], "no se debe auditar un guardado que falló"

    def test_exito_audita_y_no_avisa_error(self, app, monkeypatch):
        monkeypatch.setattr(ix_anual_mod, "loadtablacomplex", lambda *a, **k: True)
        avisos = {"critical": []}
        monkeypatch.setattr(QMessageBox, "critical",
                            lambda *a, **k: avisos["critical"].append(a[1:]))
        # A2 (PLAN_REPARACION_ANUAL_27-08.md §Fase 4, AN-7): el camino de
        # éxito ahora SÍ muestra un QMessageBox (antes solo imprimía en
        # consola) -- sin mockearlo, el click real de este test dispararía
        # un diálogo modal de verdad bajo QT_QPA_PLATFORM=offscreen
        # (Trampa 2: cuelga la suite, no lanza ninguna excepción).
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
        auditorias = []
        monkeypatch.setattr(ix_anual_mod, "_registrar_auditoria",
                            lambda *a, **k: auditorias.append((a, k)))
        obj = _obj_ix_anual()
        obj._actualizar_tabla_despues_subida = lambda: None

        _click_subir(obj, monkeypatch)

        assert avisos["critical"] == []
        assert len(auditorias) == 1

    def test_una_energia_falla_entre_varias_fse_tambien_avisa(self, app, monkeypatch):
        """Caso 'varias tablas FSE en bucle' (una por PDD) -- si CUALQUIERA
        falla, se avisa; no basta con que la mayoría tenga éxito."""
        resultados = iter([True, True, False])
        monkeypatch.setattr(ix_anual_mod, "loadtablacomplex",
                            lambda *a, **k: next(resultados))
        avisos = {"critical": []}
        monkeypatch.setattr(QMessageBox, "critical",
                            lambda *a, **k: avisos["critical"].append(a[1:]))
        monkeypatch.setattr(ix_anual_mod, "_registrar_auditoria", lambda *a, **k: None)

        obj = _obj_ix_anual()
        obj._actualizar_tabla_despues_subida = lambda: None
        layout = QVBoxLayout()
        table = QTableWidget()
        obj.tablas_fse = [[
            {'tabla': table, 'pdd': 5, 'id_energia': 1},
            {'tabla': table, 'pdd': 10, 'id_energia': 1},
            {'tabla': table, 'pdd': 15, 'id_energia': 1},
        ]]
        obj._agregar_botones_tabla(layout, table, "tabla_factores_sobre_eje", obj.ref, id=True, id_energia=1)
        boton = layout.itemAt(0).layout().itemAt(0).widget()
        boton.click()

        assert len(avisos["critical"]) == 1


class TestB0ColumnaIdentificadoraNoEsEditable:

    def _tabla_llena(self, monkeypatch, nombre_tabla, datos, filas, columnas):
        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        monkeypatch.setattr(obj, "pruebatalas", lambda *a, **k: None)
        widget, tabla = obj.createSimpleTable1(
            filas, columnas, ["c0", "c1", "c2"], datos, nombre_tabla, ref=19,
            id_energia=1, id=True)
        self._widget_vivo = widget  # evita GC del contenedor (y de `tabla`)
        return tabla

    def test_tamano_campo_columna_0_no_editable(self, app, monkeypatch):
        datos = [["10x10", "", ""], ["15x15", "", ""], ["20x20", "", ""]]
        tabla = self._tabla_llena(monkeypatch, "tabla_factor_campo", datos, 3, 3)

        item = tabla.item(0, 0)
        assert item.text() == "10x10"
        assert not (item.flags() & Qt.ItemIsEditable), (
            "el identificador de tamaño de campo no debe ser editable -- "
            "sobreescribirlo produjo la basura medida en el rebuild")

    def test_multilaminas_posicion_columna_0_si_editable(self, app, monkeypatch):
        datos = [["", "", ""] for _ in range(5)]
        tabla = self._tabla_llena(
            monkeypatch, "HC_precision_posicion_multilaminas_anual", datos, 5, 3)

        item = tabla.item(0, 0)
        assert item.flags() & Qt.ItemIsEditable, (
            "esta tabla SÍ necesita la columna 0 editable -- es un dato "
            "real (Medida (cm)), no un identificador fijo")
