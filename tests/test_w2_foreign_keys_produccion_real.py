"""W2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): `PRAGMA foreign_keys=ON`
activado en `aplicar_pragmas_conexion` -- todas las conexiones sqlite3 de la
app rechazan ahora escrituras huérfanas (el defecto habilitante de H-A).

Estos tests corren sobre una COPIA de la BD de producción real (nunca el
archivo original) para dar la garantía que pidió el físico: "que las rutas
sobreviven cualquier configuración o procedimiento que se realiza en la
aplicación" -- probando los caminos de borrado/creación reales contra el
esquema y los datos reales, no solo contra un esquema sintético mínimo.
"""
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import create_control, eliminarRegistro


def _tabla_con_fila(id_valor, texto="fila"):
    tabla = QTableWidget(1, 1)
    item = QTableWidgetItem(texto)
    item.setData(Qt.UserRole, id_valor)
    tabla.setItem(0, 0, item)
    tabla.setCurrentCell(0, 0)
    return tabla


class _DlgFalso:
    pass

from _bd_referencia import BD_QA  # DP-104: fuente única de rutas de BD
RUTA_PRODUCCION_REAL = str(BD_QA)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "question",
                         staticmethod(lambda *a, **k: load_mod.QMessageBox.Yes))


def _reset_qtsql_default_connection():
    # eliminarRegistro usa PruebaBasico().opeenDatabase() (QSqlDatabase, un
    # patrón de conexión Qt aparte del sqlite3-vía-Conexion() del resto de la
    # app) -- "qt_sql_default_connection" es un registro GLOBAL de proceso
    # (no por test), mismo patrón de aislamiento que test_a2_auditar_borrado.py.
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


@pytest.fixture
def copia_produccion(monkeypatch, tmp_path):
    if not os.path.exists(RUTA_PRODUCCION_REAL):
        pytest.skip("BaseDatosQA.db real no está presente en este entorno")
    ruta = str(tmp_path / "copia_produccion_real.db")
    shutil.copy(RUTA_PRODUCCION_REAL, ruta)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # arranque real -- corre TODAS las migraciones
    _reset_qtsql_default_connection()
    yield conexion
    _reset_qtsql_default_connection()
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None


class TestSoftDeleteDeUnControlRealNoRompeConFkOn:

    def test_anular_un_control_real_existente_funciona(self, app, copia_produccion):
        con = copia_produccion.con
        control_id, activo_antes = con.execute(
            "SELECT id, activo FROM controles WHERE activo IS NULL OR activo = 1 LIMIT 1"
        ).fetchone()

        n_preguntas_antes = con.execute(
            "SELECT COUNT(*) FROM preguntas WHERE ref = ?", (control_id,)).fetchone()[0]

        eliminarRegistro(_DlgFalso(), _tabla_con_fila(control_id), "controles")

        activo_despues = con.execute(
            "SELECT activo FROM controles WHERE id = ?", (control_id,)).fetchone()[0]
        n_preguntas_despues = con.execute(
            "SELECT COUNT(*) FROM preguntas WHERE ref = ?", (control_id,)).fetchone()[0]

        assert activo_despues == 0  # anulado, no borrado
        assert n_preguntas_despues == n_preguntas_antes  # el detalle sobrevive intacto


class TestAnularTipoCalibracionYaNoArrastraHijosReal:
    """E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11) SUPERSEDE esta clase:
    antes de E7, TipoCalibracion se borraba FÍSICO y el FK CASCADE (W2) se
    llevaba a SistemaMedicion con él -- exactamente el "peligro #1" que el
    plan identificó (arrastraba en cascada ResultadosActividad, la actividad
    calculada de la fuente, sin dejar nada recuperable). Ahora
    TipoCalibracion está en `services.anulacion.TABLAS_ANULABLES`: anular ya
    NO es un DELETE, así que el CASCADE nunca se dispara y el hijo sobrevive.
    Verificado sobre una COPIA de la BD real (no un esquema sintético)."""

    def test_anular_preserva_padre_e_hijo(self, app, copia_produccion):
        con = copia_produccion.con
        fila = con.execute("SELECT id FROM TipoCalibracion LIMIT 1").fetchone()
        if fila is None:
            pytest.skip("no hay filas en TipoCalibracion en esta copia")
        tipo_id = fila[0]

        hijos_antes = con.execute(
            "SELECT COUNT(*) FROM SistemaMedicion WHERE ref = ?", (tipo_id,)).fetchone()[0]
        con.execute(
            "INSERT INTO SistemaMedicion (ref, user) VALUES (?, 'ensayo_w2')",
            (tipo_id,))
        con.commit()

        eliminarRegistro(_DlgFalso(), _tabla_con_fila(tipo_id), "TipoCalibracion")

        padre, activo = con.execute(
            "SELECT COUNT(*), MAX(activo) FROM TipoCalibracion WHERE id = ?",
            (tipo_id,)).fetchone()
        hijos_despues = con.execute(
            "SELECT COUNT(*) FROM SistemaMedicion WHERE ref = ?", (tipo_id,)).fetchone()[0]

        assert padre == 1  # el padre SOBREVIVE (E7: anular, no borrar)
        assert activo == 0
        # ninguna hija se pierde (antes se iban TODAS con el CASCADE, incluidas
        # las que ya existieran de antes en esta copia real de producción)
        assert hijos_despues == hijos_antes + 1


class TestCreateControlSobreDatosRealesConFkOn:

    def test_control_nuevo_sin_segundo_fisico_no_falla(self, app, copia_produccion):
        """X1 + W2 juntos: crear un control sin 2º físico (el caso común)
        debe seguir funcionando -- si X1 no hubiera corregido el centinela
        ' ---- ', esto habría fallado con FOREIGN KEY constraint failed en
        cuanto W2 activara la validación."""
        con = copia_produccion.con
        fullname = con.execute("SELECT fullname FROM users LIMIT 1").fetchone()[0]

        class _SelfFalso:
            pass

        ref = create_control(_SelfFalso(), "Clinac iX", "07/2027", fullname)

        assert ref is not None
        fila = con.execute(
            "SELECT user_id, user_id_f2 FROM controles WHERE id = ?", (ref,)).fetchone()
        assert fila == (fullname, None)


class TestElBeneficioDeW2RechazaEscriturasHuerfanas:

    def test_dosimetria_men_con_ref_de_control_borrado_es_rechazada(self, app, copia_produccion):
        """El caso exacto de H-A: escribir dosimetriaMen para un control que
        ya no existe. Antes de W2 esto pasaba en silencio (esa es la causa
        raíz del incidente); con FK ON, SQLite lo rechaza directamente,
        defensa en profundidad además del guard de W1 en la capa de
        aplicación."""
        con = copia_produccion.con
        ref_inexistente = 9_999_999
        existe = con.execute(
            "SELECT 1 FROM controles WHERE id = ?", (ref_inexistente,)).fetchone()
        assert existe is None  # confirma que de verdad no existe

        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO dosimetriaMen (ref, dosis_ref_cgy_um) VALUES (?, 1.0)",
                (ref_inexistente,))

    def test_dosimetria_men_con_ref_valido_sigue_funcionando(self, app, copia_produccion):
        con = copia_produccion.con
        control_id = con.execute(
            "SELECT id FROM controles WHERE activo IS NULL OR activo = 1 LIMIT 1").fetchone()[0]

        con.execute(
            "INSERT INTO dosimetriaMen (ref, dosis_ref_cgy_um) VALUES (?, 1.01)",
            (control_id,))
        con.commit()

        n = con.execute(
            "SELECT COUNT(*) FROM dosimetriaMen WHERE ref = ? AND dosis_ref_cgy_um = 1.01",
            (control_id,)).fetchone()[0]
        assert n == 1
