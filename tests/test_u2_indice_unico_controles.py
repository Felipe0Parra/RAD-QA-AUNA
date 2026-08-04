"""U2 (PLAN_NUCLEO_04-08.md, Bloque U, DP-06): índice UNIQUE parcial sobre
expresión que impide dos controles activos del mismo (equipo, control,
mes/año).

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_controles_unico_mes
ON controles (
    equipo, control,
    CASE WHEN length(fecha)=10 THEN substr(fecha,4,7) ELSE fecha END
)
WHERE activo IS NULL OR activo = 1;
```

Creado al arranque (`Conexion._asegurar_indice_unico_controles`), precedido
SIEMPRE del conteo de U1 (`duplicados_control.duplicados_controles`): si hay
duplicados, no se crea y se reporta -- nunca se borra nada. Es defensa en
profundidad: `create_control` (load.py) ya busca-o-crea por la misma clave;
el índice garantiza que ninguna ruta futura pueda saltárselo.

Los 6 tests obligatorios del plan, en el mismo orden que el plan los lista.
"""
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.load import create_control
from scripts.migrar_bd_a_estandar import migrar

RUTA_PRODUCCION_REAL = os.path.join(
    os.path.dirname(__file__), "..", "..", "BaseDatosQA.db")
RUTA_BD_VIEJA_REAL = os.path.join(
    os.path.dirname(__file__), "..", "..", "BaseDatosQA(A_Ajustar).db")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(load_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(load_mod.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


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
    yield conexion
    conexion.con.close()
    Conexion._instance = None


def _self_falso():
    return QWidget()


class TestIndiceCreadoAlArranque:
    def test_el_indice_existe_tras_iniciar_conexion(self, app, bd_temporal):
        con = bd_temporal.con
        nombres = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        assert "idx_controles_unico_mes" in nombres


class TestUnDuplicadoDaIntegrityError:
    """1. Insertar un control duplicado del mismo mes -> IntegrityError."""

    def test_insertar_mismo_equipo_control_mes_revienta(self, app, bd_temporal):
        con = bd_temporal.con
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Clinac 600", "Mensual", "01/2026"))
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
                ("Clinac 600", "Mensual", "01/2026"))


class TestCreateControlSigueFuncionando:
    """2. create_control sigue funcionando: llamarlo dos veces devuelve el
    MISMO id."""

    def test_llamar_dos_veces_mismo_mes_devuelve_mismo_id(self, app, bd_temporal):
        primero = create_control(_self_falso(), "Clinac iX", "01/07/2026", "Físico de Prueba")
        segundo = create_control(_self_falso(), "Clinac iX", "15/07/2026", "Físico de Prueba")
        assert primero == segundo
        assert primero is not None


class TestAnularYRecrearMismoMesFunciona:
    """3. Anular un control y crear otro del mismo mes SÍ funciona -- el
    caso excepcional que el físico pidió preservar."""

    def test_anular_y_crear_uno_nuevo_mismo_mes(self, app, bd_temporal):
        con = bd_temporal.con
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Halcyon", "Mensual", "03/2026"))
        con.commit()
        id_viejo = con.execute(
            "SELECT id FROM controles WHERE equipo='Halcyon' AND control='Mensual'"
        ).fetchone()[0]

        con.execute("UPDATE controles SET activo = 0 WHERE id = ?", (id_viejo,))
        con.commit()

        # No debe reventar: la fila anulada ya no cuenta para el índice.
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Halcyon", "Mensual", "20/03/2026"))
        con.commit()

        filas = con.execute(
            "SELECT id, activo FROM controles WHERE equipo='Halcyon' "
            "AND control='Mensual' ORDER BY id"
        ).fetchall()
        assert len(filas) == 2
        assert filas[0] == (id_viejo, 0)
        assert filas[1][1] in (1, None)


class TestTresFormatosConviven:
    """4. Los tres formatos conviven: 06/2026 y 26/06/2026 colisionan entre
    sí (la expresión normaliza ambos al mismo mes/año)."""

    def test_mm_yyyy_y_dd_mm_yyyy_colisionan(self, app, bd_temporal):
        con = bd_temporal.con
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Clinac ix", "Mensual", "06/2026"))
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
                ("Clinac ix", "Mensual", "26/06/2026"))


class TestConDuplicadosNoCreaElIndiceNiBorraNada:
    """5. Con duplicados presentes, la migración NO crea el índice, NO
    borra nada y lo reporta."""

    def test_duplicados_preexistentes_bloquean_la_creacion(self, app, bd_temporal, capsys):
        con = bd_temporal.con
        # El índice ya existe (se creó al arrancar, sin duplicados) -- se
        # quita para simular una BD que llega con duplicados de otra
        # sesión/linaje, ANTES de que este arranque intente asegurarlo.
        con.execute("DROP INDEX idx_controles_unico_mes")
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Clinac 600", "Mensual", "07/2026"))
        con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES (?,?,?)",
            ("Clinac 600", "Mensual", "12/07/2026"))
        con.commit()
        conteo_antes = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]

        capsys.readouterr()
        bd_temporal._asegurar_indice_unico_controles()
        salida = capsys.readouterr().out

        nombres = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        assert "idx_controles_unico_mes" not in nombres, (
            "no debía crear el índice habiendo duplicados")
        assert "ALERTA" in salida
        assert "Clinac 600" in salida
        conteo_despues = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        assert conteo_despues == conteo_antes, "no debía borrar ninguna fila"


def _violaciones_fk(con):
    return len(con.execute("PRAGMA foreign_key_check").fetchall())


def _conteo_todas_las_tablas(con):
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'").fetchall()]
    return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}


class TestEnsayoSobreCopiaDeBDReales:
    """6. Ensayo sobre copia de BaseDatosQA.db y de
    BaseDatosQA(A_Ajustar).db: censo de filas idéntico, integrity_check=ok,
    foreign_key_check sin aumento, segunda corrida idempotente."""

    @pytest.mark.parametrize("ruta_real", [RUTA_PRODUCCION_REAL, RUTA_BD_VIEJA_REAL])
    def test_migrar_crea_el_indice_sin_perder_filas(self, ruta_real, tmp_path):
        if not os.path.exists(ruta_real):
            pytest.skip(f"{ruta_real} no está presente en este entorno")
        copia = str(tmp_path / "copia.db")
        shutil.copy(ruta_real, copia)

        con_antes = sqlite3.connect(copia)
        try:
            censo_antes = _conteo_todas_las_tablas(con_antes)
            violaciones_antes = _violaciones_fk(con_antes)
        finally:
            con_antes.close()

        migrar(copia, aplicar=True)

        con = sqlite3.connect(copia)
        try:
            nombres = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
            assert "idx_controles_unico_mes" in nombres

            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

            censo_despues = _conteo_todas_las_tablas(con)
            for tabla, antes in censo_antes.items():
                assert censo_despues.get(tabla, 0) == antes, (
                    f"{tabla}: {antes} -> {censo_despues.get(tabla)}")

            violaciones_despues = _violaciones_fk(con)
            assert violaciones_despues <= violaciones_antes
        finally:
            con.close()

        # Segunda corrida: idempotente, no revienta, el índice sigue ahí.
        migrar(copia, aplicar=True)
        con2 = sqlite3.connect(copia)
        try:
            nombres2 = {r[0] for r in con2.execute(
                "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
            assert "idx_controles_unico_mes" in nombres2
            censo_final = _conteo_todas_las_tablas(con2)
            assert censo_final == censo_despues
        finally:
            con2.close()
