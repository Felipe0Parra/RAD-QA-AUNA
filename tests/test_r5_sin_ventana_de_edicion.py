"""R.5 (PLAN_PUNTEROS_A_EQUIPOS_11-09.md §6): la ventana de 2 meses de F4b
(services/ventana_edicion.py, decisión del físico del 23-07-2026) se
desactiva por decisión del físico del 11-09-2026 -- un control mensual
admite "Subir" sin límite de tiempo. `motivo_bloqueo` deja de evaluar la
rama temporal; W1 (control inexistente o anulado) NO se toca, y es lo
único que sigue impidiendo guardar.
"""
import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.ventana_edicion import mensaje_bloqueo_edicion, motivo_bloqueo, puede_editarse


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


class TestSinLimiteDeTiempo:
    """Rojo-antes-que-verde: contra el código de ayer, un control anclado
    hace 5 meses (o el respaldo de 2025) daba `False`/"fuera_de_ventana"."""

    def test_control_creado_hace_5_meses_sigue_editable(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/04/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-04-05 10:30:00")

        assert puede_editarse(control_id, hoy=date(2026, 9, 11)) is True
        assert motivo_bloqueo(control_id, hoy=date(2026, 9, 11)) is None

    def test_control_2025_por_respaldo_sigue_editable(self, bd_temporal):
        """Sin fila en audit_log (anterior a F4c): ancla de respaldo, el
        último día del mes declarado en `controles.fecha`."""
        control_id = _crear_control(bd_temporal, "Clinac 600", "14/12/2025")

        assert puede_editarse(control_id, hoy=date(2026, 9, 11)) is True
        assert motivo_bloqueo(control_id, hoy=date(2026, 9, 11)) is None

    def test_ninguna_fecha_produce_fuera_de_ventana(self, bd_temporal):
        """Barrido de 0 a 60 meses atrás: `motivo_bloqueo` no devuelve
        'fuera_de_ventana' para NINGUNA combinación de fecha."""
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/07/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-07-05 10:30:00")

        for meses_despues in range(0, 61):
            anio = 2026 + (7 + meses_despues - 1) // 12
            mes = (7 + meses_despues - 1) % 12 + 1
            hoy = date(anio, mes, 5)
            motivo = motivo_bloqueo(control_id, hoy=hoy)
            assert motivo != "fuera_de_ventana", (
                f"a {meses_despues} meses ({hoy}): motivo={motivo!r}")


class TestW1SigueIntacto:
    """La guarda estructural (control inexistente o anulado) es la única
    que sigue bloqueando -- eso es lo que R.5 NO debía tocar."""

    def test_control_inexistente_sigue_bloqueado(self, bd_temporal):
        assert puede_editarse(99999, hoy=date(2026, 9, 11)) is False
        assert motivo_bloqueo(99999, hoy=date(2026, 9, 11)) == "inexistente"

    def test_control_anulado_sigue_bloqueado_aunque_sea_reciente(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/09/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-09-05 10:30:00")
        bd_temporal.execute(
            "UPDATE controles SET activo = 0 WHERE id = ?", (control_id,))
        bd_temporal.commit()

        assert puede_editarse(control_id, hoy=date(2026, 9, 11)) is False
        assert motivo_bloqueo(control_id, hoy=date(2026, 9, 11)) == "anulado"

    def test_control_activo_y_existente_nunca_bloquea_por_fecha(self, bd_temporal):
        """Contraste: el mismo control, activo, en cualquier fecha futura
        razonable -- sigue editable. La única diferencia con el anulado de
        arriba es `activo`, no la fecha."""
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/09/2026")
        _auditar_creacion(bd_temporal, control_id, "2026-09-05 10:30:00")

        assert puede_editarse(control_id, hoy=date(2026, 9, 11)) is True


class TestElAvisoSigueRedactandoseBien:
    """El aviso de 'Subir' bloqueado sigue funcionando para anulado e
    inexistente -- `mensaje_bloqueo_edicion` no se tocó."""

    def test_inexistente(self, bd_temporal):
        assert "ya no existe" in mensaje_bloqueo_edicion(99999)

    def test_anulado(self, bd_temporal):
        control_id = _crear_control(bd_temporal, "Clinac iX", "05/09/2026")
        bd_temporal.execute(
            "UPDATE controles SET activo = 0 WHERE id = ?", (control_id,))
        bd_temporal.commit()
        assert "anulado" in mensaje_bloqueo_edicion(control_id)
