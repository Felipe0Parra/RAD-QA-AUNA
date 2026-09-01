"""A1 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `load.py::conectarfueradeservicio`
era gemelo exacto de `add_info` (ya cerrado en `T7`/`DP-67`) -- `BEGIN` +
`reemplazar_bloque` + `commit`, **sin `try` y sin `close`**. Si
`reemplazar_bloque` lanza DESPUÉS del `BEGIN`, la excepción sube al slot de
Qt (que la atrapa e imprime, sin matar la app) y la conexión queda zombi
CON LA TRANSACCIÓN ABIERTA -- el mecanismo medido en §1.3/1.4 del plan:
todo escritor nuevo se congela hasta agotar el `busy_timeout` (30 s reales)
y termina en "database is locked".

P2: se inyecta el fallo real (un `reemplazar_bloque` que revienta DESPUÉS
del `BEGIN`, no antes) y se verifica el síntoma con el criterio de P1 --
`con.in_transaction` --, no solo un conteo de descriptores (que no
distingue el caso inofensivo del grave)."""
import os
import sqlite3
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QDateEdit, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import conectarfueradeservicio


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


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


class _SelfFalso(QWidget):
    def __init__(self, fecha=QDate(2026, 8, 5)):
        super().__init__()
        self.user_id = _UsuarioFalso()
        self.date_box = QDateEdit()
        self.date_box.setDate(fecha)
        self.observaciones = QLineEdit("mantenimiento")


class TestA1ConectarfueradeservicioNoDejaTransaccionAbierta:
    def test_reemplazar_bloque_revienta_tras_begin_no_bloquea_al_siguiente_escritor(
            self, app, bd_temporal, monkeypatch):
        """P2: inyecta el fallo en `reemplazar_bloque` -- se llama DESPUÉS
        de `cursor.execute("BEGIN")`, así que hay una transacción de
        escritura genuinamente abierta cuando revienta. Antes de A1 esto
        dejaba la conexión zombi; después, `with` la cierra (y R1 la
        revierte) pase lo que pase."""
        def _reemplazar_bloque_que_revienta(*a, **k):
            raise RuntimeError("fallo inyectado por el test, tras BEGIN")

        monkeypatch.setattr(load_mod, "reemplazar_bloque", _reemplazar_bloque_que_revienta)

        with pytest.raises(RuntimeError, match="fallo inyectado"):
            conectarfueradeservicio(_SelfFalso(), "aceleradorlineal_ix")

        escritor_nuevo = sqlite3.connect(bd_temporal, isolation_level='', timeout=2)
        t0 = time.time()
        escritor_nuevo.execute(
            "INSERT INTO aceleradorlineal_ix (date, user_id) VALUES (?, ?)",
            ("2026-08-06", "Físico de Prueba"))
        escritor_nuevo.commit()
        transcurrido = time.time() - t0
        escritor_nuevo.close()
        assert transcurrido < 0.5, (
            f"un escritor nuevo no debe esperar el busy_timeout tras el "
            f"fallo -- tardó {transcurrido:.3f}s (síntoma real: "
            f"'database is locked' hasta reiniciar la app)")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal):
        """No basta con no bloquear -- el guardado normal (sin fallo
        inyectado) tiene que seguir guardando exactamente igual que antes
        de envolver en `with`."""
        conectarfueradeservicio(_SelfFalso(QDate(2026, 8, 7)), "aceleradorlineal_ix")

        con = sqlite3.connect(bd_temporal)
        n = con.execute(
            "SELECT COUNT(*) FROM aceleradorlineal_ix WHERE DATE(date) = ?",
            ("2026-08-07",)).fetchone()[0]
        con.close()
        assert n == 1
