"""EB2b (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2b, 24-08): cierra §2.3 del
plan -- el peligro que E7 nombró y que seguía abierto tras E7:

    «Anular la calibración ya no la borra. Volver a guardarla, sí.»

`guardar_resultado_CambioFuente` (data/ManejoDatos/load.py) reguardaba una
calibración de braquiterapia con `UPDATE TipoCalibracion ... WHERE id=?` +
`DELETE` físico de sus 5 tablas hijas (`SistemaMedicion`,
`CondicionesMedicion`, `MaximosCamaras`, `LecturasMaximos`,
`ResultadosActividad`) -- destruyendo sin rastro la actividad calculada
anterior de la fuente. EB2b lo convierte en anular+insertar (`reemplazar_
bloque`, EB1): la calibración anterior se ANULA (nunca se muta en sitio),
sus 5 hijas se anulan explícitamente sobre su `ref` viejo, y todo el
bloque nuevo se inserta bajo un `ref` (id) nuevo.

Verifica también que sigue habiendo UNA sola fila de auditoría por acción
(A6.6, ya probado en test_a6_6_auditoria_braquiterapia.py) y que el
rollback es real: un fallo a mitad de las 5 hijas no deja la calibración
anterior anulada sin su reemplazo completo.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import guardar_resultado_CambioFuente


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


ARGS_BASE = dict(
    tipo="Cambio de fuente", serie="A092535", certificado="HDR12899",
    fecha_cer="2025-07-28", intensidad=1.1, conversion=1.0,
    modelo="HDR1000 Plus", serie_cp="1825", calibracion=464700,
    modelo_elec="Unidos-E", serie_ele="2343", electrometro="T10010",
    t0=22.0, p0=101.325, h0=50.0, t=22.0, p=101.325, h=50.0,
    posiciones=["A", "B"], medida1=[1.0, 2.0], medida2=[1.1, 2.1],
    promedios=[1.05, 2.05], voltaje=[400, 100],
    V_300=[1e-9, 2e-9], V_150=[1e-9, 2e-9], Vn_300=[1e-9, 2e-9],
    promediosV=[1.0, 1.0], Ks=1.0, Kp=1.0, Ktp=1.0,
    actividad_monitor=1.0, actividad_calculada=1.0,
    actividad_decaimiento=1.0, desplazamiento_ini="No Aplica",
    observaciones="sin observaciones",
)


def _guardar(user, fecha, actividad_calculada):
    kwargs = dict(ARGS_BASE)
    kwargs["actividad_calculada"] = actividad_calculada
    return guardar_resultado_CambioFuente(user, fecha, **kwargs)


def _con(ruta):
    return sqlite3.connect(ruta)


class TestReguardarNoDestruye:

    def test_resultadosactividad_anterior_sobrevive_anulada(self, bd_temporal):
        """El peligro exacto de §2.3: reguardar la MISMA calibración
        (misma fecha+tipo) no debe destruir la actividad calculada
        anterior -- debe quedar anulada, recuperable."""
        ref1 = _guardar("Físico A", "2026-08-04", actividad_calculada=10.0)
        ref2 = _guardar("Físico A", "2026-08-04", actividad_calculada=20.0)

        assert ref2 != ref1, "el reguardado debe crear una generación NUEVA"

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT ref, actividad_calculada, activo FROM ResultadosActividad "
            "ORDER BY ref").fetchall()
        con.close()

        assert filas == [
            (ref1, 10.0, 0),
            (ref2, 20.0, 1),
        ], "la generación anterior debe seguir en la BD, anulada -- nunca borrada"

    def test_tipocalibracion_anterior_queda_anulada_no_mutada(self, bd_temporal):
        ref1 = _guardar("Físico A", "2026-08-05", actividad_calculada=1.0)
        ref2 = _guardar("Físico A", "2026-08-05", actividad_calculada=2.0)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT id, activo FROM TipoCalibracion ORDER BY id").fetchall()
        con.close()

        assert (ref1, 0) in filas
        assert (ref2, 1) in filas

    def test_las_5_hijas_del_bloque_anterior_quedan_anuladas(self, bd_temporal):
        ref1 = _guardar("Físico A", "2026-08-06", actividad_calculada=1.0)
        ref2 = _guardar("Físico A", "2026-08-06", actividad_calculada=2.0)

        con = _con(bd_temporal)
        for tabla in ("SistemaMedicion", "CondicionesMedicion",
                      "MaximosCamaras", "LecturasMaximos"):
            activos_ref1 = con.execute(
                f"SELECT COUNT(*) FROM {tabla} WHERE ref=? AND activo=1",
                (ref1,)).fetchone()[0]
            assert activos_ref1 == 0, (
                f"{tabla}: filas del ref anterior ({ref1}) no deberían "
                f"seguir activas")
            filas_ref1 = con.execute(
                f"SELECT COUNT(*) FROM {tabla} WHERE ref=?", (ref1,)).fetchone()[0]
            assert filas_ref1 > 0, (
                f"{tabla}: las filas del ref anterior deben SEGUIR EN LA BD "
                f"(anuladas, no borradas)")
            activos_ref2 = con.execute(
                f"SELECT COUNT(*) FROM {tabla} WHERE ref=? AND activo=1",
                (ref2,)).fetchone()[0]
            assert activos_ref2 > 0, f"{tabla}: el bloque nuevo debe estar activo"
        con.close()

    def test_primera_vez_no_ref_anterior_no_anula_nada(self, bd_temporal):
        """Sin generación previa, el UPDATE de sql_anular_bloque no debe
        afectar a ninguna fila -- primer guardado limpio."""
        ref = _guardar("Físico A", "2026-08-07", actividad_calculada=1.0)

        con = _con(bd_temporal)
        activo = con.execute(
            "SELECT activo FROM TipoCalibracion WHERE id=?", (ref,)).fetchone()[0]
        con.close()
        assert activo == 1

    def test_distinta_fecha_no_interfiere(self, bd_temporal):
        ref1 = _guardar("Físico A", "2026-08-08", actividad_calculada=1.0)
        ref2 = _guardar("Físico A", "2026-08-09", actividad_calculada=2.0)

        con = _con(bd_temporal)
        activos = con.execute(
            "SELECT activo FROM TipoCalibracion WHERE id IN (?, ?)",
            (ref1, ref2)).fetchall()
        con.close()
        assert set(activos) == {(1,)}, (
            "calibraciones de fechas distintas no deben anularse entre sí")


class TestAuditoriaUnaFilaPorAccion:

    def test_reguardado_sigue_siendo_una_sola_fila_de_auditoria(self, bd_temporal):
        ref1 = _guardar("Físico A", "2026-08-10", actividad_calculada=1.0)
        ref2 = _guardar("Físico A", "2026-08-10", actividad_calculada=2.0)

        con = _con(bd_temporal)
        filas = con.execute(
            "SELECT usuario, accion, tabla, ref, detalle FROM audit_log "
            "ORDER BY id").fetchall()
        con.close()

        assert filas == [
            ("Físico A", "guardar", "TipoCalibracion", str(ref1),
             "cambio de fuente (braquiterapia)"),
            ("Físico A", "guardar", "TipoCalibracion", str(ref2),
             "cambio de fuente (braquiterapia)"),
        ], "cada guardado (incluido un reguardado) debe dejar EXACTAMENTE una fila"


class TestRollback:

    def test_fallo_a_mitad_no_dana_el_bloque_anterior(self, bd_temporal):
        """Si algo falla insertando las hijas nuevas, la transacción entera
        debe revertirse -- la calibración anterior debe seguir EXACTAMENTE
        como estaba (activa), no anulada-sin-reemplazo. Fallo inyectado
        renombrando `LecturasMaximos` para que su INSERT falle de verdad
        con un `OperationalError` genuino (sin tocar sqlite3 por dentro)."""
        ref1 = _guardar("Físico A", "2026-08-11", actividad_calculada=1.0)

        con = _con(bd_temporal)
        con.execute("ALTER TABLE LecturasMaximos RENAME TO LecturasMaximos_oculta")
        con.commit()
        con.close()

        try:
            with pytest.raises(sqlite3.OperationalError):
                _guardar("Físico A", "2026-08-11", actividad_calculada=2.0)
        finally:
            con = _con(bd_temporal)
            con.execute("ALTER TABLE LecturasMaximos_oculta RENAME TO LecturasMaximos")
            con.commit()
            con.close()

        con = _con(bd_temporal)
        activo_ref1 = con.execute(
            "SELECT activo FROM TipoCalibracion WHERE id=?", (ref1,)).fetchone()[0]
        total_tipocalibracion = con.execute(
            "SELECT COUNT(*) FROM TipoCalibracion").fetchone()[0]
        con.close()
        assert activo_ref1 == 1, (
            "un fallo a mitad del reguardado debe revertirse ENTERO -- la "
            "calibración anterior no debe quedar anulada sin su reemplazo")
        assert total_tipocalibracion == 1, (
            "tampoco debe quedar huérfana la fila NUEVA de TipoCalibracion "
            "-- el rollback deshace también el INSERT que sí alcanzó a "
            "correr antes del fallo")
