"""H2.1 (auditoría 2026-07-14) -- borradores JSON con clave de contexto
(equipo+mes).

Antes: `dosimetria.json`/`tamano_campo.json` eran UN SOLO archivo por app,
sin distinguir mes ni equipo -- un borrador de junio "aparecía" al abrir
julio (hallazgo del físico en producción, PLAN_FASE_H sección 1.6.1). Ahora
todo borrador se guarda envuelto en `{"_contexto": {...}, "campos": {...}}`
y solo se carga si `_contexto` coincide con el equipo+mes actuales
(`_contexto_borrador`/`_extraer_campos_de_borrador`, definidos en
PruebaMensual600 y heredados por PruebaMensualIX/PruebaMensualHc).

De paso, `_guardar_optimizado` (600/Halcyon) pasó de guardar una LISTA
plana a un dict -- la lista nunca se podía releer correctamente
(`_rellenar_campos` usa `dict.get`, y `datos.get(...)` sobre una lista
lanza AttributeError, atrapado en silencio por el except de
`_cargar_json_cache`): el botón "Guardar" de ese formulario no restauraba
nada. Ver test_mensual_h1.py para H1.2/H1.3 (mismo patrón de objeto
"pelado": __new__ + QWidget.__init__).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QDateEdit, QLineEdit, QPushButton, QTableWidget, QWidget

import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
import data.ManejoDatos.conection as conection_mod


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _instancia_pelada(cls, equipo_f, fecha_mm_yyyy):
    obj = cls.__new__(cls)
    QWidget.__init__(obj)
    obj.equipo_f = equipo_f
    obj.date_box = QDateEdit()
    obj.date_box.setDisplayFormat("MM/yyyy")
    obj.date_box.setDate(QDate.fromString(fecha_mm_yyyy, "MM/yyyy"))
    return obj


class TestContextoBorrador:
    def test_contexto_refleja_equipo_y_mes_actuales(self, app):
        obj = _instancia_pelada(PruebaMensual600, "Clinac 600", "07/2026")
        assert obj._contexto_borrador() == {"equipo": "Clinac 600", "fecha": "07/2026"}

    def test_sin_date_box_no_revienta(self, app):
        """Defensivo: si _contexto_borrador se llamara antes de que exista
        date_box, no debe reventar -- debe devolver un contexto que nunca
        calza (más seguro que heredar datos)."""
        obj = PruebaMensual600.__new__(PruebaMensual600)
        QWidget.__init__(obj)
        obj.equipo_f = "Clinac 600"
        assert obj._contexto_borrador() == {"equipo": "Clinac 600", "fecha": None}

    def test_ix_hereda_el_mismo_helper(self, app):
        obj = _instancia_pelada(PruebaMensualIX, "Clinac ix", "07/2026")
        assert obj._contexto_borrador() == {"equipo": "Clinac ix", "fecha": "07/2026"}


class TestExtraerCamposDeBorrador:
    def test_contexto_igual_devuelve_los_campos(self, app):
        obj = _instancia_pelada(PruebaMensual600, "Clinac 600", "07/2026")
        borrador = {"_contexto": {"equipo": "Clinac 600", "fecha": "07/2026"},
                    "campos": {"a": "1"}}
        assert obj._extraer_campos_de_borrador(borrador) == {"a": "1"}

    def test_contexto_de_otro_mes_no_se_carga(self, app):
        obj = _instancia_pelada(PruebaMensual600, "Clinac 600", "07/2026")
        borrador = {"_contexto": {"equipo": "Clinac 600", "fecha": "06/2026"},
                    "campos": {"a": "1"}}
        assert obj._extraer_campos_de_borrador(borrador) is None

    def test_contexto_de_otro_equipo_no_se_carga(self, app):
        obj = _instancia_pelada(PruebaMensual600, "Clinac 600", "07/2026")
        borrador = {"_contexto": {"equipo": "Halcyon", "fecha": "07/2026"},
                    "campos": {"a": "1"}}
        assert obj._extraer_campos_de_borrador(borrador) is None

    def test_formato_viejo_dict_plano_no_revienta_y_no_carga(self, app):
        obj = _instancia_pelada(PruebaMensual600, "Clinac 600", "07/2026")
        borrador_viejo = {"a": "1", "b": "2"}  # sin "_contexto" (formato pre-H2.1)
        assert obj._extraer_campos_de_borrador(borrador_viejo) is None

    def test_formato_viejo_lista_no_revienta_y_no_carga(self, app):
        obj = _instancia_pelada(PruebaMensual600, "Clinac 600", "07/2026")
        assert obj._extraer_campos_de_borrador(["1", "2", "3"]) is None


class TestGuardarOptimizadoCargarJsonCache:
    """600 (heredado por iX/Halcyon vía addsomething): round-trip real de
    _guardar_optimizado -> _cargar_json_cache."""

    def _construir(self, equipo_f, fecha, monkeypatch, tmp_path):
        obj = _instancia_pelada(PruebaMensual600, equipo_f, fecha)
        obj.file_cache = mensual_mod.FileCache()
        obj.ln_campo_a = QLineEdit()
        obj.ln_campo_b = QLineEdit()
        # HI-1: seiscientos_mensual.py ya no re-exporta ruta_datos por valor
        # -- parchear conection_mod (unico punto necesario ahora).
        monkeypatch.setattr(conection_mod, "ruta_datos", lambda nombre: str(tmp_path / nombre))
        return obj

    def test_guardar_y_recargar_mismo_contexto_restaura_los_campos(self, app, tmp_path, monkeypatch):
        obj = self._construir("Clinac 600", "07/2026", monkeypatch, tmp_path)
        obj.ln_campo_a.setText("1.23")
        obj.ln_campo_b.setText("4.56")
        filename = conection_mod.ruta_datos("dosimetria.json")
        obj._guardar_optimizado(["ln_campo_a", "ln_campo_b"], filename, lambda: None)

        otro = self._construir("Clinac 600", "07/2026", monkeypatch, tmp_path)
        otro._cargar_json_cache(["ln_campo_a", "ln_campo_b"], filename)
        assert otro.ln_campo_a.text() == "1.23"
        assert otro.ln_campo_b.text() == "4.56"

    def test_guardar_y_recargar_en_otro_mes_no_hereda_el_borrador(self, app, tmp_path, monkeypatch):
        obj = self._construir("Clinac 600", "07/2026", monkeypatch, tmp_path)
        obj.ln_campo_a.setText("1.23")
        filename = conection_mod.ruta_datos("dosimetria.json")
        obj._guardar_optimizado(["ln_campo_a"], filename, lambda: None)

        otro_mes = self._construir("Clinac 600", "08/2026", monkeypatch, tmp_path)
        otro_mes._cargar_json_cache(["ln_campo_a"], filename)
        assert otro_mes.ln_campo_a.text() == ""

    def test_formato_viejo_en_disco_no_revienta_al_cargar(self, app, tmp_path, monkeypatch):
        """Un dosimetria.json de ANTES de H2.1 (lista plana) sigue en disco
        -- no debe reventar, y (a propósito) no se carga."""
        obj = self._construir("Clinac 600", "07/2026", monkeypatch, tmp_path)
        filename = conection_mod.ruta_datos("dosimetria.json")
        os.makedirs(tmp_path, exist_ok=True)
        with open(filename, "w") as f:
            import json
            json.dump(["9.99", "8.88"], f)  # formato viejo, pre-H2.1

        obj._cargar_json_cache(["ln_campo_a", "ln_campo_b"], filename)

        assert obj.ln_campo_a.text() == ""
        assert obj.ln_campo_b.text() == ""


class TestFieldSizeContexto:
    """fieldSize (600/iX, H1.3+H2.1 combinados): sin borrador o con
    contexto distinto, nace vacío (H1.3); con el MISMO contexto, restaura
    las mediciones guardadas."""

    def _construir(self, equipo_f, fecha, monkeypatch, tmp_path):
        obj = _instancia_pelada(PruebaMensual600, equipo_f, fecha)
        obj.ref = 999999
        # HI-1: seiscientos_mensual.py ya no re-exporta ruta_datos por valor
        # -- parchear conection_mod (unico punto necesario ahora).
        monkeypatch.setattr(conection_mod, "ruta_datos", lambda nombre: str(tmp_path / nombre))
        return obj

    def _boton(self, widget, texto):
        for btn in widget.findChildren(QPushButton):
            if btn.text() == texto:
                return btn
        raise AssertionError(f"no se encontró el botón {texto!r}")

    def test_guardar_y_reabrir_mismo_contexto_restaura_mediciones(self, app, tmp_path, monkeypatch):
        obj = self._construir("Clinac 600", "07/2026", monkeypatch, tmp_path)
        widget = obj.fieldSize("tamano_campo", obj.ref)
        tabla = widget.findChild(QTableWidget)
        tabla.item(3, 1).setText("5.1")  # fila "5 x 5", columna Y1 (equipo)
        self._boton(widget, "Guardar").clicked.emit()

        otro = self._construir("Clinac 600", "07/2026", monkeypatch, tmp_path)
        widget2 = otro.fieldSize("tamano_campo", otro.ref)
        tabla2 = widget2.findChild(QTableWidget)
        assert tabla2.item(3, 1).text() == "5.1"

    def test_guardar_y_reabrir_otro_mes_no_hereda_las_mediciones(self, app, tmp_path, monkeypatch):
        obj = self._construir("Clinac 600", "07/2026", monkeypatch, tmp_path)
        widget = obj.fieldSize("tamano_campo", obj.ref)
        tabla = widget.findChild(QTableWidget)
        tabla.item(3, 1).setText("5.1")
        self._boton(widget, "Guardar").clicked.emit()

        otro_mes = self._construir("Clinac 600", "08/2026", monkeypatch, tmp_path)
        widget2 = otro_mes.fieldSize("tamano_campo", otro_mes.ref)
        tabla2 = widget2.findChild(QTableWidget)
        assert tabla2.item(3, 1).text() == ""  # H1.3: nace vacío, no heredó julio
