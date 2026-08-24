"""EB2a (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2a, 24-08, cierra G5):
`guardar_analisis_placa600` guardaba `analisis_placa_verificaciones` y
`analisis_placa_correcciones` con `DELETE FROM ... WHERE ref = ?`
INCONDICIONAL -- ni siquiera tenían la guarda de invariante 4 que
`analisis_placa_franjas` (CT2) ya tenía. El comentario que decía que esas
dos tablas "NO están en TABLAS_ANULABLES... fuera de alcance" quedó
factualmente falso desde MI1 (§6-MI1): las tres tablas están en el
inventario desde entonces.

Las tres pasan a `reemplazar_bloque` (EB1): el bloque anterior de ese
`ref` se anula (nunca se muta ni se borra), y si no hay filas nuevas que
insertar el bloque anterior se conserva intacto (invariante 4, T3) -- una
corrección real de comportamiento para verificaciones/correcciones, que
antes se borraban aunque `datos` viniera vacío.

Auditoría: un solo clic de "Guardar análisis" sigue dejando comportamiento
consistente con A6.3 -- esta función audita 0 veces (delega en el
llamador, `guardar_analisis_e_imagen`); las tres llamadas a
`reemplazar_bloque` usan `auditar=False` a propósito.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import guardar_analisis_placa600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def _verificacion(base):
    return {
        "angulos": [base, base + 1, base + 2, base + 3],
        "lados_mm": {"arriba": base, "abajo": base + 1,
                     "izquierda": base + 2, "derecha": base + 3},
        "alineacion_mm": {"vertical_izquierda": base, "vertical_dererecha": base + 1,
                          "horizontal_arriba": base + 2, "horizontal_abajo": base + 3},
        "estado": {"ortogonal": True, "simetrico": True,
                   "alineado_horizontal": True, "alineado_vertical": True,
                   "torcido": False},
    }


def _datos(n_franjas=1, con_correcciones=True, base=1.0):
    franjas = [{
        "anchura": {"horizontal": 10.0 + i, "vertical": 20.0 + i},
        "penumbra_izquierda": {"horizontal": 1.0, "vertical": 2.0},
        "penumbra_derecha": {"horizontal": 1.5, "vertical": 2.5},
        "excesos": [0.1, 0.2, 0.3, 0.4],
    } for i in range(n_franjas)]

    correcciones = {}
    if con_correcciones:
        correcciones = {
            "arriba_izq": {"Δx": base, "Δy": base + 1},
            "arriba_der": {"Δx": base + 2, "Δy": base + 3},
        }

    return {
        "cm_por_pixel": 0.1,
        "franjas": franjas,
        "verificacion": {
            "verificacion_inicial": _verificacion(base),
            "verificacion_ideal": _verificacion(base + 10),
            "correcciones": correcciones,
            "excesos_ideal": {"arriba_izq": 0.1, "arriba_der": 0.2,
                              "abajo_izq": 0.3, "abajo_der": 0.4},
        },
    }


def _con(ruta):
    return sqlite3.connect(ruta)


def _crear_control(ruta, equipo="Clinac 600", fecha="06/2026"):
    """Las 3 tablas de placa tienen FK a `controles(id)` -- se necesita un
    control real para poder insertar. `idx_controles_unico_mes` exige
    (equipo, control, mes) distintos entre dos controles."""
    con = _con(ruta)
    con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)",
        (equipo, fecha))
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


class TestReguardarConservaHistoria:

    def test_verificaciones_anteriores_quedan_anuladas_no_borradas(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        guardar_analisis_placa600(ref, _datos(base=1.0))
        guardar_analisis_placa600(ref, _datos(base=100.0))

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT angulo1, activo FROM analisis_placa_verificaciones "
            "WHERE ref=? ORDER BY rowid", (ref,)).fetchall()
        con.close()

        assert len(filas) == 4, "2 generaciones x 2 tipos = 4 filas, ninguna borrada"
        assert [f[1] for f in filas] == [0, 0, 1, 1], (
            "la primera generación debe quedar anulada, la segunda vigente")
        assert filas[2][0] == 100.0 and filas[3][0] == 110.0

    def test_correcciones_anteriores_quedan_anuladas_no_borradas(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        guardar_analisis_placa600(ref, _datos(base=1.0))
        guardar_analisis_placa600(ref, _datos(base=100.0))

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT delta_x, activo FROM analisis_placa_correcciones "
            "WHERE ref=? ORDER BY rowid", (ref,)).fetchall()
        con.close()

        assert len(filas) == 4
        assert [f[1] for f in filas] == [0, 0, 1, 1]

    def test_franjas_siguen_su_comportamiento_ct2_de_siempre(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        guardar_analisis_placa600(ref, _datos(n_franjas=2, base=1.0))
        guardar_analisis_placa600(ref, _datos(n_franjas=2, base=1.0))

        con = _con(bd_temporal)
        activos = con.execute(
            "SELECT activo FROM analisis_placa_franjas WHERE ref=?", (ref,)).fetchall()
        con.close()
        assert sorted(a for (a,) in activos) == [0, 0, 1, 1]


class TestInvariante4:
    """Antes de EB2a, verificaciones/correcciones hacían DELETE
    incondicional -- ahora, sin filas nuevas, el bloque anterior debe
    sobrevivir intacto (mismo criterio que CT2 ya daba a franjas)."""

    def test_sin_correcciones_nuevas_las_anteriores_sobreviven_activas(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        guardar_analisis_placa600(ref, _datos(con_correcciones=True, base=1.0))
        guardar_analisis_placa600(ref, _datos(con_correcciones=False, base=1.0))

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT activo FROM analisis_placa_correcciones WHERE ref=?", (ref,)).fetchall()
        con.close()

        assert [f[0] for f in filas] == [1, 1], (
            "sin correcciones nuevas que insertar, las anteriores NO deben "
            "anularse -- invariante 4 (T3), antes violada por el DELETE "
            "incondicional")


class TestRefDistintoNoInterfiere:

    def test_otro_ref_no_se_toca(self, bd_temporal):
        ref1 = _crear_control(bd_temporal, equipo="Clinac 600")
        ref2 = _crear_control(bd_temporal, equipo="Clinac iX")
        guardar_analisis_placa600(ref1, _datos(base=1.0))
        guardar_analisis_placa600(ref2, _datos(base=1.0))
        guardar_analisis_placa600(ref1, _datos(base=100.0))

        con = _con(bd_temporal)
        activo_ref2 = con.execute(
            "SELECT activo FROM analisis_placa_verificaciones WHERE ref=?", (ref2,)
        ).fetchall()
        con.close()
        assert all(a == 1 for (a,) in activo_ref2)


class TestAuditoria:

    def test_no_audita_nada_por_si_misma(self, bd_temporal):
        """auditar=False en las tres llamadas -- el clic real lo audita
        guardar_analisis_e_imagen (A6.3), fuera de esta función."""
        ref = _crear_control(bd_temporal)
        guardar_analisis_placa600(ref, _datos(base=1.0))
        con = _con(bd_temporal)
        try:
            total = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        except sqlite3.OperationalError:
            total = 0
        con.close()
        assert total == 0
