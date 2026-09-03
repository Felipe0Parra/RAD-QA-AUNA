"""I0 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase A): `_limpiar_widgets_diaria`
vivía copiada tres veces -- `braquiterapia.py`/`IX.py` byte-idénticas
[medido], `seiscientos.py` idéntica salvo una línea en blanco. `halcyon.py`
no la tenía. Se sube a `PruebaBasico` (`PruebasDiarias.py`); las tres copias
se borran.

Diff puramente MECÁNICO: mismo cuerpo exacto, sin cambio de comportamiento.
Este archivo prueba que las 4 diarias comparten ahora la MISMA función (no
tres copias más una nueva), y que la clase que tenía su PROPIA versión
homónima (`Linealidad`, sin relación de herencia con `PruebaBasico` en este
punto) no resultó tocada.

Este test NO decide todavía si "sin responder" debe verse con el color
predeterminado (`""`) o con el de "noselected" -- eso es `I1`, tarea
siguiente. Aquí solo se exige que las 4 diarias queden IDÉNTICAS entre sí,
sea cual sea ese valor -- el propio `test_a4_limpieza_fecha_sin_registro.py`
ya prueba el comportamiento línea por línea; este archivo prueba la
UNIFICACIÓN (identidad de función), que es lo que `I0` cambia de verdad.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq, Linealidad
from ui.paginasControles.PruebasDiarias.seiscientos import PruebaDiaria600
from ui.paginasControles.PruebasDiarias.IX import PruebaDiariaIX
from ui.paginasControles.PruebasDiarias.halcyon import PruebaDiariaHc


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


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


class TestLasCuatroDiariasComparteLaMismaFuncion:
    """Antes de `I0`: 3 objetos función DISTINTOS (uno por clase), más
    código muerto de mantenimiento (cualquier cambio futuro exigía tocar 3
    sitios, como de hecho pasó -- el color de `I1` habría requerido 3
    ediciones idénticas). Después: un solo objeto función, heredado."""

    def test_braqui_ix_600_resuelven_al_mismo_objeto_de_PruebaBasico(self):
        assert PruebaDiariaBraq._limpiar_widgets_diaria \
            is PruebaBasico._limpiar_widgets_diaria
        assert PruebaDiariaIX._limpiar_widgets_diaria \
            is PruebaBasico._limpiar_widgets_diaria
        assert PruebaDiaria600._limpiar_widgets_diaria \
            is PruebaBasico._limpiar_widgets_diaria

    def test_halcyon_la_hereda_aunque_hoy_no_la_use(self):
        """`halcyon.py` nunca llamó a `_limpiar_widgets_diaria` (no pasa por
        el mecanismo de `cargar_dailytest_desde_db` de las otras 3) -- I0
        no le agrega ninguna funcionalidad nueva, solo hace que el método
        exista en su MRO sin romper nada. Ver D-5/D-6 del plan: usarla desde
        halcyon queda fuera de este plan."""
        assert PruebaDiariaHc._limpiar_widgets_diaria \
            is PruebaBasico._limpiar_widgets_diaria

    def test_construir_halcyon_no_revienta(self, app, bd_temporal):
        """Que el método exista en la clase no ejecuta su cuerpo -- la
        construcción normal de Halcyon (que nunca lo invoca) debe seguir
        funcionando exactamente igual que antes de I0."""
        PruebaDiariaHc(_UsuarioFalso())

    def test_linealidad_no_fue_tocada_por_I0(self):
        """`Linealidad` (misma nombre de método, sin relación de herencia
        con `PruebaBasico` en este punto -- ver `test_acople_alcance_
        braqui_28_08.py::TestAlcanceLinealidadSinCambioDeComportamiento`)
        conserva su PROPIA función, distinta de la subida a la base."""
        assert Linealidad._limpiar_widgets_diaria \
            is not PruebaBasico._limpiar_widgets_diaria

    @pytest.mark.parametrize("clase", [PruebaDiariaBraq, PruebaDiaria600, PruebaDiariaIX])
    def test_las_tres_diarias_con_dia_registran_la_llamada_al_mismo_metodo(
            self, app, bd_temporal, clase):
        """Caracterización de comportamiento (no solo de identidad): la
        instancia real de cada clase, al llamar `_limpiar_widgets_diaria()`,
        ejecuta el cuerpo heredado sin lanzar -- construyendo la pantalla
        completa (no un doble artificial), que es lo más parecido a "antes
        y después" que se puede medir sin poder revertir el commit."""
        d = clase(_UsuarioFalso())
        d._limpiar_widgets_diaria()  # no debe lanzar
