"""N1 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): `create_control`
deja de devolver un control ANULADO en silencio.

Causa raíz: la consulta de "¿ya existe un control este mes?" no filtraba
`activo` -- un control ANULADO se devolvía igual que uno activo, y como
"Subir" ya bloquea sobre un control anulado (W1), el mes quedaba
inutilizable sin que nadie lo explicara (el físico tuvo que crear el
siguiente control en el mes SIGUIENTE, 2026-08-05).

**Reescrito por LR7** (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR7, [[DA-49]]):
el arreglo original (N2) ofrecía reactivar el control anulado. DA-49
revierte esa decisión -- la reactivación era el parche de esta MISMA
lectura sin filtrar; con el filtro puesto (`filtro_activo('controles')`,
LR3), un control anulado deja de "aparecer" como candidato del mes, y
`create_control` simplemente crea uno NUEVO al lado (legal: el índice
único de U2 es parcial sobre las filas activas). El invariante que sigue
vivo -- lo que hace correcta a DA-49 -- es el mismo de siempre: **nunca
devolver un control anulado como si fuera usable**. Solo cambia CÓMO se
cumple: antes ofreciendo reactivar, ahora ignorando el anulado y creando
uno nuevo.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import create_control


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
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _self_falso():
    return QWidget()


def _anular(ruta_bd, control_id):
    con = sqlite3.connect(ruta_bd)
    con.execute("UPDATE controles SET activo = 0 WHERE id = ?", (control_id,))
    con.commit()
    con.close()


def _activo_de(ruta_bd, id_):
    con = sqlite3.connect(ruta_bd)
    fila = con.execute("SELECT activo FROM controles WHERE id = ?", (id_,)).fetchone()
    con.close()
    return fila[0] if fila else None


def _controles_del_equipo(ruta_bd, equipo):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT id, activo FROM controles WHERE equipo = ?", (equipo,)).fetchall()
    con.close()
    return filas


class TestCreateControlIgnoraAnulados:

    def test_control_activo_del_mes_se_reutiliza(self, app, bd_temporal, monkeypatch):
        """Anti-regresión: con un control ACTIVO del mes, una segunda
        llamada en el mismo mes debe devolver el MISMO id -- el 100% del
        camino normal (F4), sin crear uno nuevo de más."""
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Clinac iX", "05/08/2026", "Físico de Prueba")
        id_2 = create_control(_self_falso(), "Clinac iX", "20/08/2026", "Físico de Prueba")

        assert id_1 == id_2

    def test_solo_anulado_crea_uno_nuevo_al_lado(self, app, bd_temporal, monkeypatch):
        """El núcleo de DA-49: con el único control del mes anulado,
        create_control lo IGNORA (no lo devuelve, no pregunta nada) y crea
        un control nuevo -- el anulado sigue en la BD, sin tocar, legible
        desde el visor de LR6."""
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Clinac 600", "05/08/2026", "Físico de Prueba")
        _anular(bd_temporal, id_1)

        id_2 = create_control(_self_falso(), "Clinac 600", "20/08/2026", "Físico de Prueba")

        assert id_2 != id_1, "debe crear un control NUEVO, no reutilizar el anulado"
        assert _activo_de(bd_temporal, id_1) == 0, "el anulado no se toca -- nunca se reactiva"
        assert _activo_de(bd_temporal, id_2) == 1

    def test_el_anulado_y_el_nuevo_conviven_sin_violar_el_indice_unico(
            self, app, bd_temporal, monkeypatch):
        """Confirma la premisa estructural de DA-49: el índice UNIQUE de U2
        (`idx_controles_unico_mes`) es PARCIAL sobre las filas activas, así
        que el control nuevo no choca con el anulado del mismo mes."""
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Halcyon", "05/08/2026", "Físico de Prueba")
        _anular(bd_temporal, id_1)

        id_2 = create_control(_self_falso(), "Halcyon", "20/08/2026", "Físico de Prueba")

        filas = _controles_del_equipo(bd_temporal, "Halcyon")
        assert (id_1, 0) in filas
        assert (id_2, 1) in filas
        assert len(filas) == 2

    def test_reabrir_el_mes_del_nuevo_control_lo_reutiliza_no_crea_un_tercero(
            self, app, bd_temporal, monkeypatch):
        """Tras DA-49, el control nuevo se comporta como cualquier otro --
        una tercera llamada en el mismo mes reutiliza el nuevo, no crea
        otro más."""
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        id_1 = create_control(_self_falso(), "Clinac 600", "05/08/2026", "Físico de Prueba")
        _anular(bd_temporal, id_1)
        id_2 = create_control(_self_falso(), "Clinac 600", "20/08/2026", "Físico de Prueba")
        id_3 = create_control(_self_falso(), "Clinac 600", "25/08/2026", "Físico de Prueba")

        assert id_3 == id_2
        assert len(_controles_del_equipo(bd_temporal, "Clinac 600")) == 2

    def test_ningun_control_del_mes_crea_uno_nuevo(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))

        id_1 = create_control(_self_falso(), "Clinac 600", "05/08/2026", "Físico de Prueba")

        assert id_1 is not None
        assert _activo_de(bd_temporal, id_1) == 1
