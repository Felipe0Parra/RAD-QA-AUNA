"""F4b (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4, tarea C1): ventana de 2
meses calendario para editar un control mensual, anclada al timestamp de
`audit_log` (F4c) -- nunca a `controles.fecha`, que el usuario puede
retrodatar.
"""
import os
import sqlite3
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.ventana_edicion import (
    MESES_VENTANA_EDICION, fecha_ancla_de_control, limite_edicion,
    mensaje_bloqueo_edicion, puede_editarse,
)


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield conexion.con
    conexion.con.close()
    Conexion._instance = None


def _crear_control(con, equipo, fecha, control="Mensual"):
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    return cur.lastrowid


def _auditar_creacion(con, control_id, timestamp):
    con.execute(
        "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
        "VALUES (?, ?, 'guardar', 'controles', ?, '')",
        (timestamp, "Físico de Prueba", str(control_id)))
    con.commit()


class TestLimiteEdicion:

    def test_suma_dos_meses(self):
        assert limite_edicion(date(2026, 5, 10)) == date(2026, 7, 10)

    def test_desborde_de_dia_recorta_al_ultimo_dia_del_mes(self):
        # 31 de diciembre + 2 meses -> febrero no tiene 31.
        assert limite_edicion(date(2025, 12, 31)) == date(2026, 2, 28)

    def test_cruza_anio(self):
        assert limite_edicion(date(2025, 11, 15)) == date(2026, 1, 15)


class TestFechaAnclaDeControl:

    def test_usa_la_auditoria_si_existe(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")

        ancla, origen = fecha_ancla_de_control(control_id)

        assert ancla == date(2026, 7, 5)
        assert origen == "auditoria"

    def test_usa_el_ultimo_dia_del_mes_sin_auditoria(self, bd_temporal):
        """Controles creados antes de F4c -- sin fila en audit_log."""
        control_id = _crear_control(bd_temporal, "Clinac 600", "14/12/2025")

        ancla, origen = fecha_ancla_de_control(control_id)

        assert ancla == date(2025, 12, 31)
        assert origen == "respaldo"

    def test_respaldo_con_formato_sin_dia(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Halcyon", "02/2026")

        ancla, origen = fecha_ancla_de_control(control_id)

        assert ancla == date(2026, 2, 28)
        assert origen == "respaldo"

    def test_toma_la_primera_auditoria_no_la_ultima(self, bd_temporal):
        """MIN(timestamp) -- la ventana cuenta desde la CREACIÓN, no desde
        la última vez que alguien reabrió el control."""
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")
        _auditar_creacion(bd_temporal, control_id, "2026-07-20 16:00:00")

        ancla, origen = fecha_ancla_de_control(control_id)

        assert ancla == date(2026, 7, 5)

    def test_id_inexistente_y_sin_fecha_reconocible(self, bd_temporal):
        ancla, origen = fecha_ancla_de_control(99999)
        assert ancla is None
        assert origen == "desconocido"


class TestPuedeEditarse:

    def test_dentro_de_la_ventana(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")

        assert puede_editarse(control_id, hoy=date(2026, 8, 1)) is True

    def test_justo_en_el_limite_es_editable(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")

        assert puede_editarse(control_id, hoy=date(2026, 9, 5)) is True

    def test_un_dia_despues_del_limite_no_es_editable(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")

        assert puede_editarse(control_id, hoy=date(2026, 9, 6)) is False

    def test_sin_ancla_no_bloquea(self, bd_temporal):
        """El control EXISTE (activo) pero no tiene ninguna fecha
        reconocible (ni auditoría, ni fecha parseable) -- "sin ancla" es
        distinto de "no existe" (ver W1: un id que no existe SÍ bloquea)."""
        control_id = _crear_control(bd_temporal, "Clinac iX", "sin-formato")
        assert puede_editarse(control_id, hoy=date(2026, 12, 1)) is True

    def test_control_id_none_no_bloquea(self, bd_temporal):
        assert puede_editarse(None) is True

    def test_historico_respaldo_2025_ya_cerrado(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac ix", "14/12/2025")

        assert puede_editarse(control_id, hoy=date(2026, 7, 23)) is False


class TestPuedeEditarseW1ExisteYActivo:
    """W1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): el incidente real del
    23-07 -- se anuló/eliminó un control desde otra vista mientras el
    formulario mensual seguía abierto con el mismo `ref`, y "Subir" seguía
    escribiendo dosimetría huérfana porque solo se miraba la franja de 2
    meses, nunca si el control seguía existiendo/activo."""

    def test_control_inexistente_no_es_editable(self, bd_temporal):
        assert puede_editarse(99999, hoy=date(2026, 12, 1)) is False

    def test_control_anulado_no_es_editable_aunque_este_en_la_ventana(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")
        bd_temporal.execute(
            "UPDATE controles SET activo = 0 WHERE id = ?", (control_id,))
        bd_temporal.commit()

        assert puede_editarse(control_id, hoy=date(2026, 7, 10)) is False

    def test_mensaje_distingue_inexistente_de_anulado_de_vencido(self, bd_temporal):
        assert "ya no existe" in mensaje_bloqueo_edicion(99999)

        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        bd_temporal.execute(
            "UPDATE controles SET activo = 0 WHERE id = ?", (control_id,))
        bd_temporal.commit()
        assert "anulado" in mensaje_bloqueo_edicion(control_id)


class TestMensajeBloqueoEdicion:

    def test_menciona_meses_y_fecha_limite(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")

        mensaje = mensaje_bloqueo_edicion(control_id)

        assert "05/09/2026" in mensaje
        assert str(MESES_VENTANA_EDICION) in mensaje

    def test_no_lanza_sin_ancla(self, bd_temporal):
        mensaje = mensaje_bloqueo_edicion(99999)
        assert isinstance(mensaje, str)
