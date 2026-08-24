"""EB2d (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2d, 24-08): las 8 funciones
de `services/MLCs_calibration_service.py` (Picket Fence + Starshot)
borraban físicamente cada tabla (`DELETE FROM ... WHERE ref=?`) seguido de
un `UPDATE ... WHERE ref=?` que -- por construcción -- NUNCA podía
matchear nada (el `DELETE` ya había vaciado esa tabla para ese `ref`), así
que la rama `INSERT`/`INSERT OR REPLACE` corría siempre. Reemplazadas por
`reemplazar_bloque` (EB1): la generación anterior se ANULA, la nueva se
inserta -- el `UPDATE` muerto desaparece solo, no hay nada que preservar
de él.

`auditar=False` en las 8: la única fila de auditoría de cada acción
(Picket Fence o Starshot) ya la escribe el llamador
(`_ejecutar_analisis_mlc`/`_ejecutar_analisis_starshot`, A6.8) al final,
después de que las 4 escrituras de su grupo terminan -- ver
`test_a6_8_auditoria_picket_fence_starshot.py` (sin cambios, sigue en
verde: prueba el cableado de auditoría con las 8 funciones mockeadas, no
su mecánica interna, que es lo que prueba este archivo).

Nota de alcance (defecto real, preexistente, NO tocado aquí): las FK de
`error_picket`/`leaf_error`/`highest_leaf_errors` apuntan a
`configuracion_picketfence(id)` -- NO a `controles(id)`, a diferencia de
`configuracion_picketfence.ref` (que sí apunta a `controles`). El código
de producción (`_ejecutar_analisis_mlc`) pasa el MISMO `self.ref`
(`controles.id`) a las 4 funciones del grupo -- funciona solo cuando
`configuracion_picketfence.id` coincide por casualidad con `controles.id`
(la primera vez, con una sola fila en cada tabla); en cualquier otro caso
el INSERT de las 3 tablas de detalle falla con `FOREIGN KEY constraint
failed`, atrapado en silencio por el `except` de cada función.
Reproducido y documentado como hallazgo nuevo (DP-42, CLAUDE.md) -- fuera
de alcance de este plan (defecto de modelado de datos, no de contrato de
guardado). Estos tests usan el `id` real de `configuracion_picketfence`
para los 3 grupos de detalle, no `controles.id`, precisamente para poder
probar el mecanismo de `reemplazar_bloque` sin tropezar con ese defecto
aparte.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.MLCs_calibration_service import (
    pf_db_insertion, pf_picket_error_insertion, pf_leaf_error_insertion,
    pf_highest_leaf_errors_insertion, starshot_insert,
    starshot_residual_statistics_insert, starshot_angles_insertion,
    starshot_angular_uniformity_insert,
)


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


def _con(ruta):
    return sqlite3.connect(ruta)


def _crear_control(ruta, equipo="Halcyon", fecha="06/2026"):
    con = _con(ruta)
    con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)",
        (equipo, fecha))
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


class TestPicketFence:

    def test_configuracion_anterior_queda_anulada_no_borrada(self, bd_temporal):
        control = _crear_control(bd_temporal)
        pf_db_insertion(control, "2026-06-01", "Halcyon", 1.0, 0.5, "F1", "F2", None)
        pf_db_insertion(control, "2026-06-02", "Halcyon", 1.5, 0.6, "F1", "F2", None)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT fecha, activo FROM configuracion_picketfence WHERE ref=? "
            "ORDER BY id", (control,)).fetchall()
        con.close()
        assert len(filas) == 2, "2 generaciones, ninguna borrada"
        assert [f[1] for f in filas] == [0, 1]

    def test_error_picket_anterior_sobrevive_anulado(self, bd_temporal):
        control = _crear_control(bd_temporal)
        pf_db_insertion(control, "2026-06-01", "Halcyon", 1.0, 0.5, "F1", "F2", None)
        con = _con(bd_temporal)
        cfg_id = con.execute(
            "SELECT id FROM configuracion_picketfence WHERE ref=?", (control,)
        ).fetchone()[0]
        con.close()

        pf_picket_error_insertion(
            cfg_id, {"picket_stats": [{"picket": 1, "picket_mean_error": 0.1,
                                        "picket_max_error": 0.2}]})
        pf_picket_error_insertion(
            cfg_id, {"picket_stats": [{"picket": 1, "picket_mean_error": 0.15,
                                        "picket_max_error": 0.25}]})

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT picket_mean_error, activo FROM error_picket WHERE ref=? "
            "ORDER BY id", (cfg_id,)).fetchall()
        con.close()
        assert filas == [(0.1, 0), (0.15, 1)], (
            "el error del picket anterior debe sobrevivir, anulado -- antes "
            "un DELETE lo destruía sin rastro")

    def test_leaf_error_anterior_sobrevive_anulado(self, bd_temporal):
        control = _crear_control(bd_temporal)
        pf_db_insertion(control, "2026-06-01", "Halcyon", 1.0, 0.5, "F1", "F2", None)
        con = _con(bd_temporal)
        cfg_id = con.execute(
            "SELECT id FROM configuracion_picketfence WHERE ref=?", (control,)
        ).fetchone()[0]
        con.close()

        pf_leaf_error_insertion(cfg_id, {"leafs": [{"leaf": 5, "leaf_error": 0.3}]})
        pf_leaf_error_insertion(cfg_id, {"leafs": [{"leaf": 5, "leaf_error": 0.4}]})

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT error, activo FROM leaf_error WHERE ref=? ORDER BY id",
            (cfg_id,)).fetchall()
        con.close()
        assert filas == [(0.3, 0), (0.4, 1)]

    def test_highest_leaf_errors_anterior_sobrevive_anulado(self, bd_temporal):
        control = _crear_control(bd_temporal)
        pf_db_insertion(control, "2026-06-01", "Halcyon", 1.0, 0.5, "F1", "F2", None)
        con = _con(bd_temporal)
        cfg_id = con.execute(
            "SELECT id FROM configuracion_picketfence WHERE ref=?", (control,)
        ).fetchone()[0]
        con.close()

        peor = {"leafs": [{"leaf": 7, "max_error": 0.5, "errors": [0.5, -0.1]}]}
        pf_highest_leaf_errors_insertion(cfg_id, peor, top_n=10)
        peor2 = {"leafs": [{"leaf": 7, "max_error": 0.6, "errors": [0.6, -0.1]}]}
        pf_highest_leaf_errors_insertion(cfg_id, peor2, top_n=10)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT desviacion, activo FROM highest_leaf_errors WHERE ref=? "
            "ORDER BY id", (cfg_id,)).fetchall()
        con.close()
        assert filas == [(0.5, 0), (0.6, 1)]

    def test_no_lanza_ante_fallo_de_fk_y_no_deja_filas_parciales(self, bd_temporal):
        """El hallazgo de alcance (DP-42): un `ref` que no matchea ningún
        `configuracion_picketfence.id` viola la FK -- el `except` de la
        función lo atrapa (comportamiento heredado, sin cambios) y no debe
        dejar ninguna fila a medias."""
        pf_picket_error_insertion(
            999999, {"picket_stats": [{"picket": 1, "picket_mean_error": 0.1,
                                        "picket_max_error": 0.2}]})
        con = _con(bd_temporal)
        total = con.execute("SELECT COUNT(*) FROM error_picket").fetchone()[0]
        con.close()
        assert total == 0


class TestStarshot:

    def test_configuracion_anterior_queda_anulada_no_borrada(self, bd_temporal):
        control = _crear_control(bd_temporal)
        starshot_insert(control, "2026-06-01", "Halcyon", 1000, 1.0, "F1", "F2", None)
        starshot_insert(control, "2026-06-02", "Halcyon", 1000, 1.5, "F1", "F2", None)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT fecha, activo FROM configuracion_starshot WHERE ref=? "
            "ORDER BY id", (control,)).fetchall()
        con.close()
        assert len(filas) == 2
        assert [f[1] for f in filas] == [0, 1]

    def test_estadisticas_anteriores_sobreviven_anuladas(self, bd_temporal):
        control = _crear_control(bd_temporal)
        estadisticas = {
            "residuos_interseccion": {"mean_mm": 0.1, "std_mm": 0.2, "rms_mm": 0.3, "p95_mm": 0.4},
            "uniformidad_angular": {"separaciones_deg": [1.0], "ideal_sep_deg": 90.0,
                                     "errores_sep_deg": [0.1]},
        }
        starshot_residual_statistics_insert(control, estadisticas)
        estadisticas2 = dict(estadisticas)
        estadisticas2["residuos_interseccion"] = dict(estadisticas["residuos_interseccion"])
        estadisticas2["residuos_interseccion"]["std_mm"] = 0.9
        starshot_residual_statistics_insert(control, estadisticas2)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT std_mm, activo FROM estadisticas_starshot WHERE ref=? "
            "ORDER BY id", (control,)).fetchall()
        con.close()
        assert filas == [(0.2, 0), (0.9, 1)]

    def test_angulos_anteriores_sobreviven_anulados(self, bd_temporal):
        control = _crear_control(bd_temporal)
        processed = {"spokes": [{"angle_deg": 0.0, "angle_real_deg": 0.1, "deviation_deg": 0.1}]}
        starshot_angles_insertion(control, processed)
        processed2 = {"spokes": [{"angle_deg": 0.0, "angle_real_deg": 0.2, "deviation_deg": 0.2}]}
        starshot_angles_insertion(control, processed2)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT angulo_real_deg, activo FROM angulo_starshot WHERE ref=? "
            "ORDER BY id", (control,)).fetchall()
        con.close()
        assert filas == [(0.1, 0), (0.2, 1)]

    def test_uniformidad_angular_anterior_sobrevive_anulada(self, bd_temporal):
        control = _crear_control(bd_temporal)
        estadisticas = {"uniformidad_angular": {
            "ideal_sep_deg": 90.0, "separaciones_deg": [89.5], "errores_sep_deg": [0.5]}}
        starshot_angular_uniformity_insert(control, estadisticas)
        estadisticas2 = {"uniformidad_angular": {
            "ideal_sep_deg": 90.0, "separaciones_deg": [89.9], "errores_sep_deg": [0.1]}}
        starshot_angular_uniformity_insert(control, estadisticas2)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT separacion_deg, activo FROM uniformidad_angular_starshot "
            "WHERE ref=? ORDER BY id", (control,)).fetchall()
        con.close()
        assert filas == [(89.5, 0), (89.9, 1)]


class TestRefDistintoNoInterfiere:

    def test_dos_controles_starshot_no_se_pisan(self, bd_temporal):
        c1 = _crear_control(bd_temporal, fecha="05/2026")
        c2 = _crear_control(bd_temporal, fecha="06/2026")
        starshot_insert(c1, "2026-05-01", "Halcyon", 1000, 1.0, "F1", "F2", None)
        starshot_insert(c2, "2026-06-01", "Halcyon", 1000, 1.0, "F1", "F2", None)
        starshot_insert(c1, "2026-05-02", "Halcyon", 1000, 1.2, "F1", "F2", None)

        con = _con(bd_temporal)
        activo_c2 = con.execute(
            "SELECT activo FROM configuracion_starshot WHERE ref=?", (c2,)).fetchall()
        con.close()
        assert all(a == 1 for (a,) in activo_c2)
