"""T3 (PLAN_CONOS_MENSUAL_12-08.md §4-T3, DA-37): nada se pierde en
silencio -- los 5 conos son obligatorios.

DECISIÓN DEL FÍSICO (2026-08-12) -> DA-37: "Bloquear hasta estar los 5 con
algún valor seleccionado." Se descarta la alternativa "avisar y guardar el
resto". `guardar_control_conos` acumula las medidas que quedaron con
`valor is None` y, si hay alguna, no escribe nada -- avisa nombrándolas y
retorna False antes de abrir la transacción.

Consecuencias verificadas aquí:
1. El bloqueo es de la tabla de conos, no del guardado entero: las cuñas
   del mismo click SÍ se guardan aunque los conos queden incompletos, y el
   bloque activo anterior de conos NO se anula sin tener con qué
   reemplazarlo (coherente con M2 -- nunca anular sin insertar).
2. El aviso nombra EXACTAMENTE las medidas que faltan.
3. La auditoría sigue siendo una sola fila por acción (DA-16), con el
   detalle diciendo si los conos entraron o no -- sin verbo nuevo.
4. Interacción con T1 (§4-T3 punto 4): tras T1 el bloqueo solo puede
   dispararse con conos NUNCA tocados, nunca con uno que el físico marcó y
   la app perdió -- no se re-verifica aquí (ya lo cubre T1), se deja
   documentado.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

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


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _ComboFalso:
    def __init__(self, texto="Funciona"):
        self._texto = texto

    def currentText(self):
        return self._texto


MEDIDAS = ("6", "10", "15", "20", "25")


def _combos_cunas(valor="Funciona"):
    return {ang: {k: _ComboFalso(valor) for k in ("in", "out", "right", "left")}
            for ang in (15, 30, 45, 60)}


def _instancia_ix(ref, valores_conos):
    """valores_conos: dict medida("6".."25") -> "fun"/"nofun"/None (sin
    marcar). Botones creados y cableados por el mecanismo REAL
    (setupButtonConnections), como T1/T2."""
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.ref = ref
    obj.user_id = _UsuarioFalso()
    obj.combos_seguridad = _combos_cunas("Funciona")
    obj.df_seg_line = None

    for medida in MEDIDAS:
        fun = QPushButton("Funciona")
        fun.setCheckable(True)
        nofun = QPushButton("No funciona")
        nofun.setCheckable(True)
        estado = valores_conos.get(medida)
        if estado == "fun":
            fun.setChecked(True)
        elif estado == "nofun":
            nofun.setChecked(True)
        setattr(obj, f"btn_{medida}_fun", fun)
        setattr(obj, f"btn_{medida}_nofun", nofun)
    return obj


def _filas_activas_conos(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    try:
        return con.execute(
            "SELECT medida, valor FROM control_conos "
            "WHERE ref = ? AND activo = 1", (ref,)).fetchall()
    finally:
        con.close()


def _filas_activas_cunas(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    try:
        return con.execute(
            "SELECT COUNT(*) FROM control_cunas "
            "WHERE ref = ? AND activo = 1", (ref,)).fetchone()[0]
    finally:
        con.close()


class TestLos5MarcadosGuardaNormal:
    def test_5_conos_guardan_5_filas(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

        valores = {"6": "fun", "10": "nofun", "15": "fun", "20": "nofun", "25": "fun"}
        obj = _instancia_ix(ref=1, valores_conos=valores)
        obj.guardar_todo_ix()

        activas = _filas_activas_conos(bd_temporal, 1)
        assert len(activas) == 5
        assert _filas_activas_cunas(bd_temporal, 1) == 4  # 1 fila por ángulo (in/out/right/left son columnas, no filas)


class TestDosSinMarcarNoEscribeNadaYAvisaExacto:
    def test_bloquea_conos_pero_guarda_cunas(self, app, bd_temporal, monkeypatch):
        avisos = []
        monkeypatch.setattr(
            QMessageBox, "warning",
            lambda self_, titulo, texto, *a, **k: avisos.append(texto))
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

        # 6x6 y 20x20 quedan sin marcar; las otras 3 sí.
        valores = {"6": None, "10": "fun", "15": "nofun", "20": None, "25": "fun"}
        obj = _instancia_ix(ref=1, valores_conos=valores)
        obj.guardar_todo_ix()

        # No escribe ninguna fila nueva de conos (bloque completo, no parcial).
        assert _filas_activas_conos(bd_temporal, 1) == []

        # El aviso nombra EXACTAMENTE las 2 medidas faltantes.
        assert len(avisos) == 1
        assert "6x6" in avisos[0]
        assert "20x20" in avisos[0]
        assert "10x10" not in avisos[0]
        assert "15x15" not in avisos[0]
        assert "25x25" not in avisos[0]
        for simbolo in ("✓", "✗", "⚠️", "✅"):
            assert simbolo not in avisos[0], f"símbolo {simbolo!r} en el aviso (DA-18)"

        # Las cuñas del mismo click SÍ se guardaron.
        assert _filas_activas_cunas(bd_temporal, 1) == 4

    def test_bloque_activo_anterior_sigue_activo(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO control_conos (ref, medida, valor, activo) "
            "VALUES (1, '6x6', 1, 1)")
        con.commit()
        con.close()

        valores = {"6": None, "10": "fun", "15": "nofun", "20": "fun", "25": "fun"}
        obj = _instancia_ix(ref=1, valores_conos=valores)
        obj.guardar_todo_ix()

        # El bloque activo anterior NO se anuló sin tener con qué
        # reemplazarlo -- sigue siendo el mismo, íntegro.
        assert _filas_activas_conos(bd_temporal, 1) == [("6x6", 1)]


class TestAuditoriaUnaFilaConDetalleHonesto:
    def test_detalle_dice_si_los_conos_entraron(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

        valores = {"6": None, "10": "fun", "15": "nofun", "20": "fun", "25": "fun"}
        obj = _instancia_ix(ref=1, valores_conos=valores)
        obj.guardar_todo_ix()

        con = sqlite3.connect(bd_temporal)
        try:
            filas = con.execute(
                "SELECT accion, tabla, detalle FROM audit_log "
                "WHERE ref = '1'").fetchall()
        finally:
            con.close()

        assert len(filas) == 1, f"debe seguir siendo UNA sola fila: {filas}"
        accion, tabla, detalle = filas[0]
        assert accion == "guardar"
        assert tabla == "control_cunas"  # M4: tabla real, no la inventada
        assert "incompletos" in detalle
