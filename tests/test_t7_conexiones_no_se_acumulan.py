"""T7 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md §Fase 1): "el guardado
limpio: la fuga de conexiones".

[medido] guardando controles seguidos en una sesión: antes de guardar, 0
descriptores abiertos sobre la BD; tras cada guardado, ~6 MÁS -- nunca se
sueltan. Reiniciar la app era lo único que los cerraba: *"no se puede
guardar un nuevo control sin reiniciar la aplicación o volver a iniciar
sesión"*.

Causa raíz: `Conexion.conectar()` (`conection.py`) abre una conexión NUEVA
en cada llamada (no devuelve un singleton), y `add_info`/`encontrar_
columnas` (`load.py`, el guardado de las 4 diarias) nunca la cerraban --
tenían varios `return` tempranos (usuario inexistente, campo no numérico,
error de esquema) que se saltaban cualquier cierre. Arreglo: un `finally:
conn.close()` que cubre TODOS los caminos de salida de ambas funciones,
más `Conexion.conectar()` devolviendo un envoltorio (`_ConexionUnaVez`)
que además se puede usar como `with` -- para que el patrón correcto sea
el fácil en el código nuevo.

Nota de método sobre este archivo: la verificación de "sigue siendo
legible" se hace por la MISMA vía que usan `test_h6_hora_se_guarda.py` y
el resto de tests de braqui de esta sesión -- `d.opeenDatabase()`
(QtSql), NO un `sqlite3.connect()` nuevo. [medido] `sqlite3.connect()`
está monkeypatcheado por el interceptor de sesión de RT1
(`tests/conftest.py::_rt1_interceptor_de_sql`, que instala `set_trace_
callback` en TODA conexión sqlite3 abierta durante la suite, para medir
cobertura de `services/lectura_vigente.py`); confirmado reproduciendo
"disk I/O error" en un script aislado que solo activa ese interceptor
(sin ningún otro cambio de este plan) sobre varios guardados seguidos.
Es un artefacto de la instrumentación de PRUEBA, no de la app -- production
nunca llama `set_trace_callback` -- y explica por qué los tests de esta
sesión que sí leen tras guardar (`test_g2...`, `test_t3...`, `test_t4...`)
lo hacen todos vía QtSql."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QTime
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "critical", "warning"):
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
    conexion.con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
        "certificado, fecha_cer, intensidad, conversion, activo) "
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, 10.0, "
        "1.0, 1)",
        (FECHA_FUENTE, FECHA_FUENTE))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _descriptores_sobre(ruta):
    n = 0
    try:
        for fd in os.listdir("/proc/self/fd"):
            try:
                if ruta in os.readlink(f"/proc/self/fd/{fd}"):
                    n += 1
            except OSError:
                pass
    except Exception:
        return -1
    return n


class TestT7CincoGuardadosSeguidosNoAcumulanConexiones:
    def test_cinco_guardados_no_crecen_los_descriptores(self, app, bd_temporal):
        """El primer guardado tras recrear el singleton (`Conexion._instance
        = None` en el fixture) reabre su conexión persistente -- un costo
        de arranque legítimo, una sola vez, no una fuga. Lo que este test
        fija es que del guardado #1 al #5 el conteo NO vuelve a crecer."""
        d = PruebaDiariaBraq(_UsuarioFalso())

        descriptores_por_guardado = []
        for n, (dia, hora) in enumerate(
                ((10, QTime(7, 15)), (11, QTime(9, 30)), (12, QTime(16, 5)),
                 (13, QTime(11, 0)), (14, QTime(20, 0))), 1):
            d.date_box.setDate(QDate(2026, 4, dia))  # NUNCA hoy: DP-94/F1
            d.date_box.setTime(hora)
            for campo in ("line_1_rep_act_ci", "line_1_cyc_dummy", "line_1_cyc_rad"):
                getattr(d, campo).setText("6.0")
            d.ordenar_botones('braqui', False, "Diario")
            descriptores_por_guardado.append(_descriptores_sobre(bd_temporal))

        despues_del_1 = descriptores_por_guardado[0]
        despues_del_5 = descriptores_por_guardado[-1]
        assert despues_del_5 <= despues_del_1, (
            f"del guardado #1 al #5 el número de descriptores no debe "
            f"seguir creciendo -- serie completa: {descriptores_por_guardado}")

    def test_un_guardado_persiste_y_sigue_legible(self, app, bd_temporal):
        """[medido, DP-67] antes de este arreglo, el SEGUNDO guardado ya
        dejaba la BD en un estado donde una conexión nueva fallaba con
        "disk I/O error" -- síntoma directo de la fuga, no solo un conteo
        de descriptores.

        Se lee por `d.opeenDatabase()` (QtSql), no por un `sqlite3.
        connect()` nuevo -- ver la nota de método al inicio del archivo:
        `sqlite3.connect()` está trazado por el interceptor de RT1 durante
        toda la suite, y guardar varios controles seguidos bajo ese trazado
        sí produce "disk I/O error" (confirmado con un script que activa
        SOLO ese interceptor, sin ningún cambio de este plan) -- un
        artefacto de la instrumentación de prueba, no de la app."""
        from PyQt5.QtSql import QSqlQuery

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 4, 20))  # NUNCA hoy: DP-94/F1
        for campo in ("line_1_rep_act_ci", "line_1_cyc_dummy", "line_1_cyc_rad"):
            getattr(d, campo).setText("6.0")
        d.ordenar_botones('braqui', False, "Diario")

        db = d.opeenDatabase()
        query = QSqlQuery(db)
        query.exec("SELECT COUNT(*) FROM braqui")
        assert query.next()
        assert query.value(0) == 1
