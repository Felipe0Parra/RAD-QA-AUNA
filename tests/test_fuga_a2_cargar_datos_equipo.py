"""A2 (PLAN_FUGA_CONEXIONES_01-09.md §2.1/§4): `equipos.py::Config.cargarDatos`
(alta de un equipo) hacía `INSERT` + `commit`, **sin `try` y sin `close`**.
Si algo revienta entre el `INSERT` y el `commit`, la excepción sube sin que
nada la atrape -- la conexión queda zombi, posiblemente con la transacción
del INSERT sin resolver.

P2, nota de método: la primera versión de este test intentó medir el
síntoma "un escritor nuevo se bloquea" cronometrando un segundo escritor
tras el fallo -- **[medido] no discrimina**: incluso SIN el `with`, un
`ProgrammingError` lanzado dentro de una única llamada de función (una
sola cadena de frames, sin ciclo de referencias formado) se libera por
refcount casi de inmediato, y el escritor nuevo entra rápido de todos
modos. El mecanismo de reciclado tardío que sí bloquea (§1.2-1.3 del plan)
depende de CUÁNTOS frames y qué ciclos se forman al propagar la excepción
-- una condición de carrera de la que este test no debe depender. Se
verifica en su lugar el invariante ESTRUCTURAL y determinista: que
`_ConexionUnaVez.__exit__` (ya probado correcto en R1) se INVOCA en el
camino de excepción -- eso es lo único que garantiza el cierre pase lo que
pase con el GC, y es exactamente lo que agrega el `with`."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
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
    conexion = Conexion()  # corre el DDL real
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"


class _ConexionUnaVezEspia(_ConexionUnaVez):
    """Subclase de la envoltura REAL (no una reinvención) que solo agrega
    un registro de si `__exit__` se invocó -- todo lo demás (rollback si
    in_transaction, close, nunca commit) sigue siendo el código de R1,
    sin duplicar su lógica."""
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


LISTA_ALTA = [
    "Cámara de ionización", "TN31010", "1822", "0.3034", None,
    "16/03/2026", "PTW", 22.0, 101.325, 50.0, 400.0, 1, 1, None,
]


class TestA2CargarDatosCierraSiempre:
    def test_insert_revienta_y_aun_asi_se_invoca_exit(
            self, app, bd_temporal, monkeypatch):
        """P2: el INSERT revienta por un desajuste de bindings (una `lista`
        con un valor de menos, algo tan simple como pasar un dato mal
        formado desde el formulario). Antes de A2 esto dejaba la conexión
        sin ningún cierre estructural; después, el `with` garantiza que
        `_ConexionUnaVez.__exit__` se invoque en TODOS los caminos."""
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioActualFalso()

        with pytest.raises(sqlite3.ProgrammingError, match="bindings"):
            Config.cargarDatos(obj, LISTA_ALTA[:-1])  # un valor de menos

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el INSERT revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_guardando_igual(self, app, bd_temporal, monkeypatch):
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioActualFalso()

        Config.cargarDatos(obj, LISTA_ALTA)

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM equipos WHERE serie = ?", ("1822",)).fetchone()[0]
        con.close()
        assert n == 1
