"""T5 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md §Fase 1): "que se pueda
modificar la hora: el widget es 54% más angosto de lo que muestra".

`DP-68`: `H7` (de `DP-63`) se aplicó a la rama `QDateTimeEdit` de
`PruebasDiarias.createInterface` -- braqui usa la rama `QDateEdit`, que
nunca recibió ningún piso de ancho para el momento en que
`braquiterapia.py:initUI` le cambia el formato a "dd/MM/yyyy HH:mm:ss" (19
caracteres, casi el doble de "dd/MM/yyyy"). El widget quedaba 72 px (54%)
más angosto de lo que su propio formato pedía -- las secciones HH:mm:ss
caían fuera del área alcanzable con el mouse.

Causa de clase: `ancho_minimo_fecha` se llamaba con un `formato=` literal
en createInterface, en vez de leer `displayFormat()` del widget -- y ese
cálculo corría ANTES de que braqui cambiara su propio formato más tarde.
Arreglo de dos partes: (1) `createInterface` deja de pasar el literal (ya
no puede divergir de lo que de verdad se fijó); (2) `braquiterapia.py`
reaplica el piso, con `ancho_minimo_fecha(self.date_box)` SIN argumento,
justo después de cambiar el formato -- la única forma de que el piso
refleje un formato fijado DESPUÉS de la creación del widget.

Este test es censal sobre los `date_box` de las diarias que SÍ pasan por
el mecanismo compartido (braqui, 600, iX) -- Halcyon crea su `date_box` a
mano (`halcyon.py:148`, fuera de `createInterface` por completo) y hasta
`H1` nunca tuvo este piso; documentado como deuda en `DP-72`, fuera de
alcance de T5 (que es la regresión de braqui, no una garantía nueva para
una pantalla que nunca la tuvo).

`H1` (PLAN_FUGA_CONEXIONES_01-09.md §5) cierra esa deuda: Halcyon gana el
mismo `setDisplayFormat`/`setMinimumWidth` en `iniGUI`, así que se suma
`PruebaDiariaHc` al censo de abajo -- las 4 diarias quedan cubiertas."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.util_fechas import ancho_minimo_fecha
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq
from ui.paginasControles.PruebasDiarias.seiscientos import PruebaDiaria600
from ui.paginasControles.PruebasDiarias.IX import PruebaDiariaIX
from ui.paginasControles.PruebasDiarias.halcyon import PruebaDiariaHc


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
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
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


@pytest.mark.parametrize("clase", [PruebaDiariaBraq, PruebaDiaria600, PruebaDiariaIX, PruebaDiariaHc])
class TestT5AnchoMinimoCubreElFormatoReal:
    def test_date_box_no_queda_mas_angosto_que_su_propio_formato(
            self, app, bd_temporal, clase):
        d = clase(_UsuarioFalso())
        esperado = ancho_minimo_fecha(d.date_box)  # sin formato=: lee displayFormat() actual
        assert d.date_box.minimumWidth() >= esperado, (
            f"{clase.__name__}.date_box tiene formato "
            f"{d.date_box.displayFormat()!r} pero minimumWidth()="
            f"{d.date_box.minimumWidth()} < {esperado} necesarios -- las "
            f"secciones finales del formato caerían fuera del área "
            f"alcanzable con el mouse")


class TestT5RojoAntesQueVerdeSintetico:
    """No depende de nada del proyecto: un QDateEdit con el piso calculado
    para un formato CORTO y luego cambiado a uno LARGO sin reaplicar debe
    marcar la misma violación que tenía braqui."""

    def test_ensanchar_el_formato_sin_reaplicar_el_piso_se_detecta(self, app):
        from PyQt5.QtWidgets import QDateEdit
        w = QDateEdit()
        w.setDisplayFormat("dd/MM/yyyy")
        w.setMinimumWidth(ancho_minimo_fecha(w))  # piso correcto para el formato CORTO

        w.setDisplayFormat("dd/MM/yyyy HH:mm:ss")  # se ensancha SIN reaplicar

        esperado = ancho_minimo_fecha(w)
        assert w.minimumWidth() < esperado, (
            "precondición del defecto: cambiar a un formato más largo sin "
            "reaplicar el piso debe dejarlo corto -- si esto no fuera "
            "cierto, el test de arriba no discriminaría nada")
