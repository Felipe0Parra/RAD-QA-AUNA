"""A7 (PLAN_AUDITORIA_DOS_EJES_21-07): visor de `audit_log` arreglado + motor
muerto eliminado.

Antes de esta tarea, `console_logs.Registros` importaba `AuditEngine`
(`services/auditorias.py`, 100% comentado) -- `ImportError` garantizado
antes de llegar siquiera a instanciar nada -- y consultaba columnas que
nunca existieron en el `audit_log` real (`username/action/module/status/
detail` en vez de `usuario/accion/tabla/ref/detalle`, el esquema real de
`services/audit_minimo.py`). Esta tarea lo dejó importable, instanciable y
leyendo el esquema real; la pestaña "Registros" se habilitó después, en A11
(ver test_a11_pestana_registros.py).
"""
import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.console_logs import Registros


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # corre el DDL real -- crea audit_log entre las 69 tablas
    conexion.con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES ('2026-07-21 10:00:00', 'Fisico X', 'guardar', 'halcyon', '2026-07-01', 'x')")
    conexion.con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES ('2026-07-21 11:00:00', 'Fisico Y', 'eliminar', 'controles', '3', 'y')")
    conexion.con.commit()
    conexion.con.close()
    Conexion._instance = None
    yield ruta


class TestRegistrosVisorEsquemaReal:
    def test_se_instancia_sin_importerror(self, app, bd_temporal):
        # Antes de A7 esto ni siquiera importaba (AuditEngine no existe en
        # services.auditorias, 100% comentado) -- el solo hecho de que esta
        # línea no lance ya es la regresión que importa.
        widget = Registros()
        assert widget is not None

    def test_carga_filas_reales_con_las_columnas_correctas(self, app, bd_temporal):
        widget = Registros()

        assert widget._tabla.rowCount() == 2
        # ORDER BY timestamp DESC -- la más reciente primero.
        assert widget._tabla.item(0, 1).text() == "Fisico Y"
        assert widget._tabla.item(0, 2).text() == "eliminar"
        assert widget._tabla.item(0, 3).text() == "controles"
        assert widget._tabla.item(1, 1).text() == "Fisico X"
        assert widget._tabla.item(1, 2).text() == "guardar"

    def test_buscar_filtra_por_accion_tabla_o_usuario(self, app, bd_temporal):
        widget = Registros()
        widget._input_buscar.setText("halcyon")
        widget._cargar_historico()

        assert widget._tabla.rowCount() == 1
        assert widget._tabla.item(0, 3).text() == "halcyon"
