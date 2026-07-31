"""G6 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md): `limpiar_recursos`
accedia a `self._debounce_timers` sin guarda -- `PruebaMensualTAC` puede
llegar a cerrarse sin haber inicializado ese atributo (terminal del rebuild
30-07, linea 1938: "Error al limpiar recursos: 'PruebaMensualTAC' object has
no attribute '_debounce_timers'"). Atrapado por el `except` de la propia
funcion (no crasheaba), pero ensuciaba la terminal y podia enmascarar un
fallo real de limpieza. Mismo patron de guarda que ya usa
`_configurar_debounce` (seiscientos_mensual.py:902).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _instancia_sin_debounce_timers():
    """PruebaMensual600 sin su __init__ pesado -- reproduce el caso real:
    _debounce_timers nunca se asignó (normalmente lo hace __init__ en
    :114, pero PruebaMensualTAC puede llegar a limpiar_recursos sin haber
    pasado por ahí)."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    assert not hasattr(obj, '_debounce_timers')
    return obj


class TestLimpiarRecursosSinDebounceTimers:
    def test_no_lanza_excepcion(self, app):
        """ROJO ANTES DEL FIX: `self._debounce_timers.values()` lanza
        AttributeError; el except de limpiar_recursos lo atrapa, así que
        esto no falla como excepción propagada -- lo que hay que verificar
        es que no se imprime el error (siguiente test)."""
        obj = _instancia_sin_debounce_timers()
        obj.limpiar_recursos()  # no debe lanzar

    def test_no_imprime_error(self, app, capsys):
        """ROJO ANTES DEL FIX: imprime
        "Error al limpiar recursos: 'PruebaMensual600' object has no
        attribute '_debounce_timers'" -- el ruido real que veía el físico."""
        obj = _instancia_sin_debounce_timers()
        obj.limpiar_recursos()
        salida = capsys.readouterr().out
        assert "Error al limpiar recursos" not in salida

    def test_sigue_limpiando_cuando_si_existe(self, app):
        """Anti-regresión: con _debounce_timers presente, la guarda nueva
        no cambia el comportamiento -- se limpia igual que antes."""
        obj = _instancia_sin_debounce_timers()
        obj._debounce_timers = {"x": None}
        obj.limpiar_recursos()
        assert obj._debounce_timers == {}
