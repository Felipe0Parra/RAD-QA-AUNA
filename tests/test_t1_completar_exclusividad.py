"""T1 (PLAN_CONOS_MENSUAL_12-08.md §4-T1): los dos botones de un par
Funciona/No funciona se comportan como una elección real.

`completar()` (PruebasDiarias.py) solo cambiaba la propiedad de estilo y
actualizaba `botones_finales` -- nunca llamaba a `setChecked` sobre ninguno
de los dos botones. Como nacen `setCheckable(True)` sin `QButtonGroup`, eso
producía dos defectos que se combinan:

D1 -- No hay exclusión mutua: click Funciona -> click No funciona deja los
DOS marcados (`fun=True, nofun=True`); `guardar_control_conos` evalúa `fun`
primero y guarda 1 (el valor VIEJO), aunque el físico se corrigió a "No
funciona".

D2 -- El botón se desmarca solo al volver a pulsarlo: dos clicks en
Funciona lo apagan (`fun=False, nofun=False`) -- `guardar_control_conos`
salta la fila (`valor is None`). Es la explicación literal de "si no
cambia el valor, no lo guarda": no compara con lo anterior, el segundo
clic de confirmación lo apagó.

Fix: `completar` fuerza `selected_btn.setChecked(True)` /
`rejected_btn.setChecked(False)` antes de `cambiar_estilo` -- desde
cualquier estado, un clic aterriza siempre en exactamente
`(seleccionado=True, rechazado=False)`.

Riesgo de tocar una función compartida (48 botones de 3 formularios
diarios + 10 del mensual iX): ninguna ruta diaria lee `isChecked()` --
guardan desde `self.botones_finales`, que `completar` ya alimenta y que
este cambio no toca (§1.6 del plan). Este archivo cubre el mecanismo con
el cableado REAL de `setupButtonConnections` sobre los botones de conos
(el único consumidor de `isChecked()` en toda la capa de formularios); el
protocolo de cierre corre además los tests existentes de las 4 diarias.
"""
import os
import sqlite3

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO controles (id, equipo, control, fecha) "
        "VALUES (1, 'Clinac ix', 'Mensual', '06/2026')")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


DF_CONOS = pd.DataFrame({
    'descripcion': ['Funciona', 'No funciona'],
    'nombres': ['btn_6_fun', 'btn_6_nofun'],
    'widget_type': ['QPushButton', 'QPushButton'],
    'prueba': ['seguridad', 'seguridad'],
})


def _instancia_con_boton_conos(ref):
    """PruebaMensualIX pelada, con el par de botones de la medida 6x6
    creados y cableados por el mecanismo REAL de producción
    (`setupButtonConnections`), no botones sueltos."""
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.ref = ref
    obj.botones_finales = set()
    obj.esIX = True

    obj.btn_6_fun = QPushButton("Funciona")
    obj.btn_6_fun.setCheckable(True)
    obj.btn_6_nofun = QPushButton("No funciona")
    obj.btn_6_nofun.setCheckable(True)

    obj.setupButtonConnections(DF_CONOS, maquina=None)
    return obj


def _guardar_conos_solo_6x6(obj):
    """Envoltura de `guardar_control_conos` reducida a la única medida que
    este test cablea -- mismo cuerpo (M2: anular+insertar dentro de una
    transacción), sin depender de las otras 4 medidas."""
    valor = None
    if obj.btn_6_fun.isChecked():
        valor = 1
    elif obj.btn_6_nofun.isChecked():
        valor = 0

    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("BEGIN TRANSACTION")
    cursor.execute(
        "UPDATE control_conos SET activo = 0 "
        "WHERE ref = ? AND (activo IS NULL OR activo = 1)", (obj.ref,))
    if valor is not None:
        cursor.execute(
            "INSERT INTO control_conos (ref, medida, valor) VALUES (?, ?, ?)",
            (obj.ref, "6x6", valor))
    conn.commit()


def _fila_activa(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    try:
        return con.execute(
            "SELECT valor FROM control_conos WHERE ref = ? AND activo = 1",
            (ref,)).fetchall()
    finally:
        con.close()


class TestD1CorreccionSeGuardaBien:
    """§5.3 caso 10: click Funciona -> click No funciona ⇒ se guarda 0
    (hoy escribe 1, porque `guardar_control_conos` evalúa `fun` primero y
    D1 deja los dos botones marcados)."""

    def test_corregir_a_no_funciona_guarda_cero(self, app, bd_temporal):
        obj = _instancia_con_boton_conos(ref=1)
        obj.btn_6_fun.click()
        obj.btn_6_nofun.click()

        assert obj.btn_6_fun.isChecked() is False, (
            "D1 vivo: el botón rechazado por el clic sigue marcado")
        assert obj.btn_6_nofun.isChecked() is True

        _guardar_conos_solo_6x6(obj)
        assert _fila_activa(bd_temporal, 1) == [(0,)]


class TestD2SegundoClicNoBorraLaFila:
    """§5.3 caso 11: dos clicks en Funciona ⇒ la fila SIGUE guardándose
    con 1 (hoy desaparece -- el segundo clic apaga el botón porque nace
    checkable sin QButtonGroup)."""

    def test_doble_clic_en_funciona_mantiene_marcado(self, app, bd_temporal):
        obj = _instancia_con_boton_conos(ref=1)
        obj.btn_6_fun.click()
        obj.btn_6_fun.click()

        assert obj.btn_6_fun.isChecked() is True, (
            "D2 vivo: el segundo clic sobre el mismo botón lo apagó")
        assert obj.btn_6_nofun.isChecked() is False

        _guardar_conos_solo_6x6(obj)
        assert _fila_activa(bd_temporal, 1) == [(1,)]


class TestEstadosAlcanzablesQuedanReducidos:
    """§6 del plan: tras T1 toda transición por clic aterriza en (T,F) o
    (F,T) -- (T,T) deja de ser alcanzable, sea cual sea el estado previo."""

    @pytest.mark.parametrize("secuencia,esperado", [
        (["fun"], (True, False)),
        (["nofun"], (False, True)),
        (["fun", "nofun"], (False, True)),
        (["nofun", "fun"], (True, False)),
        (["fun", "fun"], (True, False)),
        (["nofun", "nofun"], (False, True)),
        (["fun", "nofun", "fun"], (True, False)),
    ])
    def test_secuencia_de_clics_nunca_deja_los_dos_marcados(
            self, app, bd_temporal, secuencia, esperado):
        obj = _instancia_con_boton_conos(ref=1)
        for paso in secuencia:
            (obj.btn_6_fun if paso == "fun" else obj.btn_6_nofun).click()

        estado = (obj.btn_6_fun.isChecked(), obj.btn_6_nofun.isChecked())
        assert estado == esperado, f"secuencia {secuencia} -> {estado}"
        # (T,T) nunca es alcanzable.
        assert estado != (True, True)
