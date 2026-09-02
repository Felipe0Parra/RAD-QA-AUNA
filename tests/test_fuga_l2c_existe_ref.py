"""L2c (PLAN_CIERRE_LECTURAS_02-09.md §5.1/§6): `tac_mensual.py::
GestorReconstruccion._existe_ref` -- el caso CANÓNICO de fuga silenciosa
de todo el plan. El `try` SÍ envuelve la conexión, pero el `except
Exception` la traga con un `print` que nadie mira: un `ref` no bindeable
(`ProgrammingError`) o `self.tac.old_id` inexistente (`AttributeError`)
terminan igual -- `return False`, conexión abierta, nada en pantalla.

`with` acotado a las líneas que usan `conn` (P3); el `conn.close()`
explícito se retira. El `return existe` queda DENTRO del `try`, fuera del
`with` -- el `except` sigue cubriendo cualquier fallo posterior, igual
que hoy.

P10 (blindaje): este sitio NO tenía red -- su única mención previa en la
suite era un falso positivo de substring (`_existe_ref` casa dentro de
`test_no_existe_referencia_viva_a_boton_guardar`, de otro archivo, sobre
otra clase). `GestorReconstruccion` es una clase PLANA (no `QWidget`): se
instancia sin `__init__` pesado, solo `GestorReconstruccion(stub_tac)`.

Censo: `tests/test_lr1_censo_raices_qc.py` tiene una entrada IDENTIDAD
para `(tac_mensual.py, 164, "controles")` -- la línea 164 (el
`cursor.execute`) NO se mueve con este cambio (se sustituye la línea 162,
se borra la 169, ambas fuera del rango [164]); se corren los 4 censos
igual para confirmarlo, no se da por hecho."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from ui.paginasControles.PruebasMensuales.tac_mensual import GestorReconstruccion


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _TacFalso:
    """Stub mínimo -- GestorReconstruccion solo lee `self.tac.old_id` en
    `_existe_ref`, nada más de la instancia real de PruebaMensualTAC."""
    def __init__(self, old_id):
        self.old_id = old_id


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


def _insertar_control(con, equipo="Tomógrafo", control="Mensual"):
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha, user_id) "
        "VALUES (?, ?, ?, ?)",
        (equipo, control, "01/2026", "Físico de Prueba"))
    con.commit()
    return cur.lastrowid


class TestL2cExisteRefCierraSiempre:
    def test_ref_no_bindeable_no_revienta_hacia_afuera_pero_aun_asi_se_invoca_exit(
            self, bd_temporal, monkeypatch):
        """El `except Exception` de la propia función traga el fallo --
        no hay `pytest.raises` posible aquí, eso es justo lo que hace este
        sitio distinto de L2a/L2b/A12 (donde la excepción SÍ propaga)."""
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()

        gestor = GestorReconstruccion(_TacFalso(old_id=1))

        resultado = gestor._existe_ref(["no bindeable"], "Tomógrafo")

        assert resultado is False, (
            "el comportamiento observable (devolver False ante un fallo) "
            "debe seguir intacto -- P3 no toca la lógica")
        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando el execute revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_con_old_id_y_ref_existente_devuelve_true(
            self, bd_temporal, monkeypatch):
        """P10 paso 1 -- red de caracterización sobre el camino real que
        SÍ importa clínicamente: decide si el TAC reconstruye una sesión
        guardada. Verde sobre el código de hoy antes de tocar nada."""
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        con = Conexion().con
        ref = _insertar_control(con, equipo="Tomógrafo")

        gestor = GestorReconstruccion(_TacFalso(old_id=1))
        resultado = gestor._existe_ref(ref, "Tomógrafo")

        assert resultado is True
        assert _ConexionUnaVezEspia.llamadas == ["exit"]

    def test_sin_old_id_devuelve_false_aunque_el_ref_exista(
            self, bd_temporal, monkeypatch):
        """Rama `if self.tac.old_id else False` -- sin old_id, ni siquiera
        se mira si la fila existe de verdad."""
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        con = Conexion().con
        ref = _insertar_control(con, equipo="Tomógrafo")

        gestor = GestorReconstruccion(_TacFalso(old_id=None))
        resultado = gestor._existe_ref(ref, "Tomógrafo")

        assert resultado is False
        assert _ConexionUnaVezEspia.llamadas == ["exit"]

    def test_ref_de_otro_equipo_no_hace_falso_positivo(self, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        con = Conexion().con
        ref = _insertar_control(con, equipo="Clinac 600")

        gestor = GestorReconstruccion(_TacFalso(old_id=1))
        resultado = gestor._existe_ref(ref, "Tomógrafo")

        assert resultado is False
        assert _ConexionUnaVezEspia.llamadas == ["exit"]
