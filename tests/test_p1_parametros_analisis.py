"""P1 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase B): `braqui` guarda los 6
números del análisis pero no el `umbral_relativo`/`distancia_minima` con los
que se obtuvieron. **[medido]**: recalcular con los valores por defecto
reproduce lo guardado en 5 de 8 días reales y difiere en 3 -- sin los
parámetros, el perfil recargado (`P2`) sería una curva distinta de los
números que tiene al lado, dato clínico incoherente consigo mismo.

Tres garantías:
  1. guardar con parámetros no-default los persiste tal cual.
  2. las otras 3 diarias (que nunca los tienen) siguen guardando sin
     reventar -- `add_info` es compartida.
  3. la migración (`_asegurar_parametros_analisis_braqui`) es aditiva e
     idempotente sobre una BD que no tiene las columnas todavía.

Las que releen DESPUÉS de que la pantalla ya escribió lo hacen por la MISMA
conexión QSqlDatabase que usa la pantalla (`d.opeenDatabase()`), no por una
conexión `sqlite3.connect()` aparte -- [medido, mismo hallazgo que
`test_h6_hora_se_guarda.py`]: una segunda conexión sqlite3 sobre el mismo
archivo, mientras `add_info` escribió por SU PROPIA conexión
(`Conexion().conectar()`) y la pantalla mantiene la suya abierta, no ve el
commit en este entorno ("disk I/O error") -- artefacto del sandbox de tests,
no del código de producción.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq
from ui.paginasControles.PruebasDiarias.seiscientos import PruebaDiaria600
from ui.paginasControles.PruebasDiarias.IX import PruebaDiariaIX

FECHA_FUENTE = "2020-01-01 00:00:00"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


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


def _llenar_campos_numericos(d, valor="1.0"):
    for campo in ("line_1_rep_act_ci", "line_1_exp_act_ci",
                  "line_1_cyc_dummy", "line_1_cyc_rad"):
        getattr(d, campo).setText(valor)


def _leer_parametros(d, patron_fecha):
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(
        "SELECT umbral_relativo, distancia_minima FROM braqui "
        "WHERE date LIKE :p ORDER BY id DESC LIMIT 1")
    query.bindValue(":p", patron_fecha)
    query.exec()
    assert query.next(), f"no hay fila para {patron_fecha!r}"
    return query.value(0), query.value(1)


def _contar_filas(d, tabla, patron_fecha):
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(f"SELECT COUNT(*) FROM {tabla} WHERE date LIKE :p")
    query.bindValue(":p", patron_fecha)
    query.exec()
    query.next()
    return query.value(0)


class TestGuardarPersisteLosParametrosDelAnalisis:

    def test_guardar_con_parametros_no_default_los_persiste(
            self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 10))
        _llenar_campos_numericos(d)

        # _crear_interfaz_parametros() es lo que analizar_imagen() llama la
        # primera vez -- crea spin_umbral/spin_dist. Se invoca directo
        # (mismo criterio que test_i3/test_i4: no hace falta una imagen
        # radiográfica real para probar que el VALOR del spin se guarda).
        d._crear_interfaz_parametros()
        d.spin_umbral.setValue(1.4)
        d.spin_dist.setValue(55)
        d.mostrar_texto(["Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])

        d.ordenar_botones('braqui', False, "Diario")

        umbral, distancia = _leer_parametros(d, "2026-07-10%")
        assert umbral == pytest.approx(1.4)
        assert distancia == 55

    def test_guardar_sin_haber_analizado_nada_deja_null(self, app, bd_temporal):
        """Un día sin película (nunca se llamó a `_crear_interfaz_
        parametros`) no debe reventar -- `spin_umbral`/`spin_dist` ni
        siquiera existen todavía."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 11))
        _llenar_campos_numericos(d)
        assert not hasattr(d, "spin_umbral")

        d.ordenar_botones('braqui', False, "Diario")

        umbral, distancia = _leer_parametros(d, "2026-07-11%")
        assert umbral in (None, ""), f"esperaba NULL, quedó {umbral!r}"
        assert distancia in (None, ""), f"esperaba NULL, quedó {distancia!r}"


class TestOtrasDiariasSiguenGuardandoSinReventar:
    """add_info es compartida por las 4 diarias -- ninguna de las otras 3
    tiene spin_umbral/spin_dist ni las columnas nuevas en su tabla. Los
    parámetros nuevos son argumentos con valor por defecto None: si nadie
    los pasa (como en estas 3 llamadas, sin cambios), el comportamiento
    debe ser IDÉNTICO al de antes de P1."""

    def test_600_guarda_sin_reventar(self, app, bd_temporal):
        d = PruebaDiaria600(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 12))
        for campo in d.df_lines:
            if hasattr(d, campo):
                getattr(d, campo).setText("1.0")

        d.ordenar_botones('aceleradorlineal_600', False)

        assert _contar_filas(d, "aceleradorlineal_600", "2026-07-12%") == 1

    def test_ix_guarda_sin_reventar(self, app, bd_temporal):
        d = PruebaDiariaIX(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 13))
        for campo in d.df_lines:
            if hasattr(d, campo):
                getattr(d, campo).setText("1.0")

        d.ordenar_botones('aceleradorlineal_ix', False)

        assert _contar_filas(d, "aceleradorlineal_ix", "2026-07-13%") == 1


class TestMigracionAditivaEIdempotente:

    def test_columnas_no_existen_antes_de_la_migracion(self, monkeypatch, tmp_path):
        """Construye una BD igual que las de producción HOY (sin las
        columnas de P1) para demostrar que la migración las agrega -- no
        que ya estaban."""
        ruta = str(tmp_path / "vieja.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        con_previa = Conexion()
        cur = con_previa.con.cursor()
        cur.execute("ALTER TABLE braqui DROP COLUMN umbral_relativo")
        cur.execute("ALTER TABLE braqui DROP COLUMN distancia_minima")
        con_previa.con.commit()
        columnas = [c[1] for c in cur.execute("PRAGMA table_info(braqui)")]
        assert "umbral_relativo" not in columnas
        assert "distancia_minima" not in columnas
        con_previa.con.close()
        Conexion._instance = None

        # Reabrir -- __init__ vuelve a correr _asegurar_parametros_analisis_braqui
        con_nueva = Conexion()
        columnas = [c[1] for c in con_nueva.con.execute("PRAGMA table_info(braqui)")]
        assert "umbral_relativo" in columnas
        assert "distancia_minima" in columnas
        con_nueva.con.close()
        Conexion._instance = None

    def test_correrla_dos_veces_no_falla(self, monkeypatch, tmp_path):
        ruta = str(tmp_path / "test.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        c1 = Conexion()
        c1.con.close()
        Conexion._instance = None

        c2 = Conexion()  # segunda pasada -- no debe reventar (idempotente)
        columnas = [c[1] for c in c2.con.execute("PRAGMA table_info(braqui)")]
        assert columnas.count("umbral_relativo") == 1
        assert columnas.count("distancia_minima") == 1
        c2.con.close()
        Conexion._instance = None

    def test_activo_sigue_excluida_del_insert_tras_el_corrimiento(
            self, app, bd_temporal):
        """El obstáculo real de P1: `activo` deja de ser la última columna
        física de `braqui` (umbral_relativo/distancia_minima quedan
        DESPUÉS de ella) -- si `encontrar_columnas` siguiera excluyéndola
        por POSICIÓN, `add_info` escribiría una columna de menos y el
        INSERT reventaría con 'table braqui has N columns but M values
        were supplied'. Este test es justamente ese guardado real."""
        con_temp = Conexion()
        columnas = [c[1] for c in con_temp.con.execute("PRAGMA table_info(braqui)")]
        assert columnas[-1] != "activo", (
            "precondición: activo debe haber quedado ANTES de las 2 "
            "columnas nuevas para que este test ejerza el caso real")
        assert columnas.index("activo") < columnas.index("umbral_relativo")

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 14))
        _llenar_campos_numericos(d)

        d.ordenar_botones('braqui', False, "Diario")  # no debe reventar

        assert _contar_filas(d, "braqui", "2026-07-14%") == 1
