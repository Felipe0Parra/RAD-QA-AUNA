"""L2a (PLAN_CIERRE_LECTURAS_02-09.md §5.2/§6): `equipos.py::Config.
abrir_certificado` -- el `SELECT imagen_certificado ... ; conn.close()`
vive en código LINEAL, antes de que empiece el `try` (línea 646, que solo
cubre la apertura del visor). Si la fila ya no existe (equipo anulado o
borrado entre pintar la tabla y hacer doble clic), `cursor.fetchone()[0]`
revienta con `TypeError: 'NoneType' object is not subscriptable` -- fallo
REAL y alcanzable, no artificial -- y la excepción sube al slot de Qt
(`itemDoubleClicked`), que la traga en silencio. La conexión queda abierta.

`with` acotado a las 3 líneas que usan `conn` (P3); el `conn.close()`
explícito se retira -- `_ConexionUnaVez.__exit__` lo hace al salir del
bloque, incluso cuando `fetchone()[0]` revienta dentro.

P10 (blindaje, PLAN_CIERRE_LECTURAS_02-09.md): este sitio SÍ tiene red --
`tests/test_c1_certificado_calibracion.py::TestAbrirCertificado` lo
ejercita de verdad (PDF, imagen, "sin certificado válido") y sigue verde
sin cambios. Este archivo solo añade el fallo de P2, que esa clase no
cubre."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QWidget

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.equipos as equipos_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasGuia.equipos import Config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _obj_con_item(texto, id_equipo):
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem(texto)
    item.setData(Qt.UserRole, id_equipo)
    obj.table.setItem(0, 0, item)
    return obj, item


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestL2aAbrirCertificadoCierraSiempre:
    def test_fila_inexistente_revienta_y_aun_asi_se_invoca_exit(
            self, app, bd_temporal, monkeypatch):
        """id_equipo=999 no existe en la BD temporal (vacía) -- SELECT no
        encuentra nada, cursor.fetchone() devuelve None, None[0] revienta.
        Fallo real (equipo anulado entre pintar la tabla y el doble clic),
        no fabricado."""
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj, item = _obj_con_item("PDF", id_equipo=999)

        with pytest.raises(TypeError):
            Config.abrir_certificado(obj, item)

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando fetchone()[0] revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_leyendo_el_blob_igual(self, app, bd_temporal, monkeypatch):
        """Confirma, con el mismo espía, que el camino normal (fila real)
        sigue invocando __exit__ una vez -- no solo el camino de fallo."""
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        # `subprocess` se importa DENTRO de abrir_certificado (línea 626) --
        # se parchea el módulo real (mismo patrón que
        # test_c1_certificado_calibracion.py), no `equipos_mod.subprocess`
        # (no existe: no hay import a nivel de módulo).
        import subprocess
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)
        monkeypatch.setattr(equipos_mod.sys, "platform", "linux")

        con = Conexion().con
        cur = con.execute(
            "INSERT INTO equipos (equip_type, model, serie, activo, vigente) "
            "VALUES ('Cámara de ionización', 'N30013', '2123', 1, 0)")
        id_equipo = cur.lastrowid
        con.execute(
            "UPDATE equipos SET imagen_certificado = ? WHERE id = ?",
            (b"%PDF-1.4 contenido de prueba", id_equipo))
        con.commit()

        obj, item = _obj_con_item("PDF", id_equipo=id_equipo)
        Config.abrir_certificado(obj, item)

        assert _ConexionUnaVezEspia.llamadas == ["exit"]
