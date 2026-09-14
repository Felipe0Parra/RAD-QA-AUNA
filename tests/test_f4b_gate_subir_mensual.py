"""F4b (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4, tarea C1): "Subir" en el
mensual respeta la ventana de 2 meses -- alcance de esta tarea: los dos
puntos de escritura de dosimetría/energía (`subirlineasmensuales` en
load.py, usado por 600/Halcyon vía `_subir_optimizado`, y
`subirlineasmensuales_ix` en ix_mensual.py). Los "Subir" de otras
categorías del mensual (aspectos mecánicos, tamaños de campo, MLC, vía
`loadtablacomplex`) NO quedan cubiertos por esta tarea -- residual
documentado, no un olvido silencioso.

F0 (PLAN_BRAQUI_HORA_EDITABLE_07-09.md, 07-09-2026): el caso "dentro de la
ventana" anclaba el control en un timestamp LITERAL ("2026-07-05"), y la
ventana son 2 meses CALENDARIO desde el ancla -- ese literal caducó el
2026-09-05 y el test se puso rojo solo, por el paso del calendario, sin que
nadie tocara nada. Censo de los archivos que tocan
`puede_editarse`/`motivo_bloqueo`/`limite_edicion`/`ventana_edicion`, uno
por uno: `test_f4b_ventana_edicion.py` pasa `hoy=date(...)` explícito en
cada aserción -- inmune por diseño; `test_lr2_filas_anuladas_sinteticas.py`
solo CITA `services/ventana_edicion.py:100` en un censo de lecturas SQL por
línea (LR2), sin ejercitar la ventana -- fuera de este problema;
`test_fuga_a7_subirlineasmensuales.py` ancla con `datetime.now()` (no un
literal): se mueve con el reloj y por eso nunca caduca, aunque sigue
dependiendo de la hora real; `test_w1_no_escribir_sobre_control_eliminado.py`
prueba la extensión a "existe y está activo", no la ventana temporal. Este
archivo era el ÚNICO que afirmaba "dentro de la ventana" con una fecha
literal fija (`subirlineasmensuales` consulta la puerta sin recibir `hoy`,
así que usa la fecha del día real). El ancla de
`test_dentro_de_ventana_permite_escribir` pasa a calcularse relativa a HOY
-- ver el comentario en esa función."""
import os
import sqlite3
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import subirlineasmensuales
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager)
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
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _pelado_600():
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.val_teo_6mv = QLineEdit()
    obj.ln_dosis_ref_cgy_um_6mv = QLineEdit()
    obj.ln_observaciones_dosi = QLineEdit()
    obj.df_lines = ["val_teo_6mv", "ln_dosis_ref_cgy_um_6mv", "ln_observaciones_dosi"]
    return obj


def _pelado_ix():
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioFalso()
    obj.val_teo_6mv = QLineEdit()
    obj.ln_dosis_ref_cgy_um_6mv = QLineEdit()
    obj.ln_observaciones_dosi = QLineEdit()
    return obj, ["val_teo_6mv", "ln_dosis_ref_cgy_um_6mv", "ln_observaciones_dosi"]


def _crear_control_con_ancla(ruta_db, timestamp_creacion):
    con = sqlite3.connect(ruta_db)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Clinac iX", "Mensual", "05/07/2026"))
    con.commit()
    control_id = cur.lastrowid
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, 'Físico de Prueba', 'guardar', 'controles', ?, '')",
        (timestamp_creacion, str(control_id)))
    con.commit()
    con.close()
    return control_id


def _filas_dosimetria(ruta_db, ref):
    con = sqlite3.connect(ruta_db)
    n = con.execute("SELECT COUNT(*) FROM dosimetriaMen WHERE ref=?", (ref,)).fetchone()[0]
    con.close()
    return n


class TestGateSubirLineasMensuales600:

    def test_fecha_antigua_ya_no_bloquea_escribe_normalmente(self, app, bd_temporal, monkeypatch):
        """R.5 (PLAN_PUNTEROS_A_EQUIPOS_11-09.md §6, 11-09-2026): la
        ventana de 2 meses se desactivó por decisión del físico -- un
        control anclado en enero (muy fuera de la vieja ventana) ya no
        bloquea "Subir"; escribe normal, sin aviso."""
        control_id = _crear_control_con_ancla(bd_temporal, "2026-01-05 10:00:00")
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                 AssertionError("no debía bloquear -- R.5 desactivó la ventana"))))

        obj = _pelado_600()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=control_id, usarid=False)

        assert _filas_dosimetria(bd_temporal, control_id) == 1

    def test_dentro_de_ventana_permite_escribir(self, app, bd_temporal, monkeypatch):
        # F0: ancla RELATIVA a hoy, no un literal -- un literal caduca sin
        # avisar en cuanto pasan los 2 meses de ventana (ya ocurrió una
        # vez, ver el docstring del módulo). 15 días queda lejos de
        # cualquier borde de la ventana (que se cuenta en MESES
        # calendario, no en días), así que no hay riesgo de aterrizar
        # justo en el límite por el propio desfase elegido.
        ancla = (date.today() - timedelta(days=15)).strftime("%Y-%m-%d 10:00:00")
        control_id = _crear_control_con_ancla(bd_temporal, ancla)
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                 AssertionError("no debía bloquear -- está dentro de la ventana"))))

        obj = _pelado_600()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=control_id, usarid=False)

        assert _filas_dosimetria(bd_temporal, control_id) == 1

    def test_anual_no_se_bloquea(self, app, bd_temporal, monkeypatch):
        """Anual usa su propio create_control (sin ancla de auditoría) --
        el guard no debe aplicar la ventana ahí."""
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                 AssertionError("Anual no debía bloquearse"))))

        obj = _pelado_600()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        subirlineasmensuales(obj, "dosimetriaMen", 0, ref=999999, usarid=False, anual=True)


class TestGateSubirLineasMensualesIX:

    def test_fecha_antigua_ya_no_bloquea_escribe_normalmente(self, app, bd_temporal, monkeypatch):
        """R.5: mismo cambio que en 600 -- ver el test gemelo arriba.

        Trampa 2: `subirlineasmensuales_ix` avisa del ÉXITO con un
        `QMessageBox.information` (`ix_mensual.py:334`) que solo se alcanza
        cuando el guardado llega al commit. Mientras la ventana bloqueaba,
        este test moría en la línea 208 y ese diálogo nunca se abría; al
        desactivarla (R.5) pasa a abrirse modal y cuelga la suite entera sin
        lanzar ninguna excepción. Se mockea sobre la clase de PyQt5, no sobre
        el módulo, para no depender de desde dónde la importe producción."""
        control_id = _crear_control_con_ancla(bd_temporal, "2026-01-05 10:00:00")
        monkeypatch.setattr(QMessageBox, "information",
                             staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                 AssertionError("no debía bloquear -- R.5 desactivó la ventana"))))

        obj, df_lines = _pelado_ix()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=control_id, usarid=True, df_lines=df_lines)

        # El iX escribe UNA FILA POR ENERGÍA, no una sola como el 600 -- el
        # número se deriva de la declaración, no se copia, para que añadir
        # una energía no deje el test afirmando un conteo viejo.
        assert _filas_dosimetria(bd_temporal, control_id) == len(PruebaMensualIX.ENERGIAS)

    def test_dentro_de_ventana_escribe_lo_mismo(self, app, bd_temporal, monkeypatch):
        """ANCLA de R.5, gemelo del que el 600 ya tenía y al iX le faltaba.

        Un control DENTRO de la vieja ventana de 2 meses nunca estuvo
        bloqueado -- ni antes ni después de R.5 -- así que el número de filas
        que deja aquí es el comportamiento propio de
        `subirlineasmensuales_ix`, no una consecuencia de haber quitado la
        puerta. Que los dos casos (dentro y fuera) escriban EXACTAMENTE lo
        mismo es lo que demuestra que R.5 cambió *si* se escribe, nunca
        *cuánto* -- sin este test, el conteo del caso de arriba sería solo
        'lo que el código hace hoy'."""
        ancla = (date.today() - timedelta(days=15)).strftime("%Y-%m-%d 10:00:00")
        control_id = _crear_control_con_ancla(bd_temporal, ancla)
        monkeypatch.setattr(QMessageBox, "information",
                             staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(load_mod.QMessageBox, "warning",
                             staticmethod(lambda *a, **k: (_ for _ in ()).throw(
                                 AssertionError("no debía bloquear -- está dentro de la ventana"))))

        obj, df_lines = _pelado_ix()
        obj.ln_dosis_ref_cgy_um_6mv.setText("0.993")
        obj.subirlineasmensuales_ix("dosimetriaMen", 0, ref=control_id, usarid=True, df_lines=df_lines)

        assert _filas_dosimetria(bd_temporal, control_id) == len(PruebaMensualIX.ENERGIAS)
