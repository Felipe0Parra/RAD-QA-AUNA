"""B.2 (PLAN_REFERENCIAS_EDITABLES_21-09.md): `services/referencias_qc.py`,
única puerta a `referencias_qc` -- el permiso se verifica DENTRO del
servicio, no solo en la UI (ocultar un botón no es un control de acceso;
patrón de `services/gestion_usuarios.py`, U3).

Decisiones del físico (21-09) que este archivo fija:
  - R4: *"Todos pueden ver pero solo el jefe puede editar, obvio el
    administrador también."* -> las lecturas no piden permiso;
    `fijar_referencia` exige `es_fisico_jefe` (jefe y admin).
  - Cambiar una referencia nunca borra la anterior (contrato anular+insertar):
    queda en `historial()` con quién y cuándo.

[medido, DP-82] hoy hay UN solo usuario con rol `jefe`: ningún test asume más
de uno.
"""
import math
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import services.anulacion as anulacion_mod
from services.referencias_qc import (
    DENEGADO_SIN_PERMISO, FUENTE_OBLIGATORIA, OBSERVACIONES_OBLIGATORIAS,
    VALOR_INVALIDO, fijar_referencia, historial, leer_referencia,
    listar_vigentes)


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + migraciones reales
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _sembrar_usuario(ruta, user, fullname, rol_sistema):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES (?, 'x', ?, 1, '1', 'Físico Médico', ?)",
        (user, fullname, rol_sistema))
    con.commit()
    con.close()


def _sembrar_los_tres(ruta):
    _sembrar_usuario(ruta, "lamaya", "Luz Adriana Maya", "jefe")
    _sembrar_usuario(ruta, "jjcastillo", "Javier Castillo", "fisico")
    _sembrar_usuario(ruta, "superadmin", "Administrador Prueba", "admin")


def _filas_ref(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute("SELECT * FROM referencias_qc ORDER BY id").fetchall()
    con.close()
    return filas


def _filas_audit_ref(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT usuario, accion, tabla, ref, detalle FROM audit_log "
        "WHERE tabla='referencias_qc' ORDER BY id").fetchall()
    con.close()
    return filas


def _fijar(usuario="lamaya", valor=0.627, energia="6mv", equipo="Halcyon",
           magnitud="calidad", fuente="puesta en servicio",
           observaciones="valor medido en la puesta en servicio"):
    return fijar_referencia(equipo, magnitud, energia, valor, fuente,
                             observaciones, usuario)


class TestLeerSinPermiso:
    """R4: todos pueden VER -- las lecturas no piden ningún usuario."""

    def test_sin_referencia_devuelve_none_no_un_valor_por_defecto(self, bd_temporal):
        assert leer_referencia("Halcyon", "calidad", "6mv") is None

    def test_listar_vigentes_vacio(self, bd_temporal):
        assert listar_vigentes() == []

    def test_historial_vacio(self, bd_temporal):
        assert historial("Halcyon", "calidad", "6mv") == []


class TestPermisoDentroDelServicio:

    def test_fisico_es_rechazado_y_no_escribe_nada(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        resultado = _fijar(usuario="jjcastillo")
        assert resultado == (False, DENEGADO_SIN_PERMISO)
        assert _filas_ref(bd_temporal) == []

    def test_fisico_rechazado_deja_rastro_del_intento(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(usuario="jjcastillo")
        (usuario, accion, tabla, ref, detalle), = _filas_audit_ref(bd_temporal)
        assert usuario == "Javier Castillo"
        assert tabla == "referencias_qc"
        assert ref == "Halcyon/calidad/6mv"
        assert detalle == DENEGADO_SIN_PERMISO

    def test_usuario_inexistente_es_rechazado(self, bd_temporal):
        """Fallback invertido de es_fisico_jefe: si el rol no resuelve, se
        DENIEGA."""
        _sembrar_los_tres(bd_temporal)
        assert _fijar(usuario="nadie") == (False, DENEGADO_SIN_PERMISO)
        assert _filas_ref(bd_temporal) == []

    def test_sin_usuario_es_rechazado(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        assert _fijar(usuario=None) == (False, DENEGADO_SIN_PERMISO)
        assert _fijar(usuario="") == (False, DENEGADO_SIN_PERMISO)

    def test_jefe_puede_fijar(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        assert _fijar(usuario="lamaya") == (True, None)

    def test_administrador_tambien_puede_fijar(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        assert _fijar(usuario="superadmin") == (True, None)


class TestFijarYLeer:

    def test_lo_fijado_se_lee_con_todos_sus_campos(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(valor=0.627)
        ref = leer_referencia("Halcyon", "calidad", "6mv")
        assert ref["valor"] == pytest.approx(0.627)
        assert ref["equipo"] == "Halcyon"
        assert ref["magnitud"] == "calidad"
        assert ref["energia"] == "6mv"
        assert ref["fuente"] == "puesta en servicio"
        assert ref["observaciones"] == "valor medido en la puesta en servicio"
        assert ref["fijada_por"] == "Luz Adriana Maya"
        assert ref["fecha"]

    def test_queda_una_sola_fila_de_auditoria_con_el_usuario_correcto(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(valor=0.627)
        (usuario, accion, tabla, ref, detalle), = _filas_audit_ref(bd_temporal)
        assert usuario == "Luz Adriana Maya"
        assert accion == "reemplazo"
        assert tabla == "referencias_qc"
        assert ref == "Halcyon/calidad/6mv"
        assert "0.627" in detalle

    def test_equipos_y_energias_son_independientes(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(equipo="Halcyon", energia="6mv", valor=0.627)
        _fijar(equipo="Clinac ix", energia="6mv", valor=0.665)
        _fijar(equipo="Clinac ix", energia="15mv", valor=0.761)
        assert leer_referencia("Halcyon", "calidad", "6mv")["valor"] == pytest.approx(0.627)
        assert leer_referencia("Clinac ix", "calidad", "6mv")["valor"] == pytest.approx(0.665)
        assert leer_referencia("Clinac ix", "calidad", "15mv")["valor"] == pytest.approx(0.761)
        assert len(listar_vigentes()) == 3

    def test_energia_none_se_guarda_como_cadena_vacia(self, bd_temporal):
        """§1.3: NULL dejaría la clave sin proteger en el índice UNIQUE."""
        _sembrar_los_tres(bd_temporal)
        _fijar(magnitud="tol_dosis", energia=None, valor=2.0)
        (fila,) = _filas_ref(bd_temporal)
        columnas = ["id", "equipo", "magnitud", "energia"]
        assert fila[columnas.index("energia")] == ""
        assert leer_referencia("Halcyon", "tol_dosis", None)["valor"] == pytest.approx(2.0)
        assert leer_referencia("Halcyon", "tol_dosis", "")["valor"] == pytest.approx(2.0)

    def test_unidad_opcional_se_guarda(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        fijar_referencia("Halcyon", "tol_dosis", "", 2.0, "TG-142", "criterio del servicio",
                          "lamaya", unidad="%")
        assert leer_referencia("Halcyon", "tol_dosis", "")["unidad"] == "%"


class TestCambiarNoBorra:
    """La garantía titular del contrato: la referencia anterior queda
    recuperable, con quién y cuándo."""

    def test_segunda_fijacion_anula_la_primera_no_la_borra(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(valor=0.627)
        _fijar(valor=0.640, fuente="recalibración 09/2026",
               observaciones="tras el servicio técnico")

        assert leer_referencia("Halcyon", "calidad", "6mv")["valor"] == pytest.approx(0.640)
        assert len(_filas_ref(bd_temporal)) == 2, "la anterior no debe desaparecer"

        hist = historial("Halcyon", "calidad", "6mv")
        assert [h["valor"] for h in hist] == pytest.approx([0.640, 0.627])
        assert [h["activo"] for h in hist] == [1, 0]
        assert hist[1]["fuente"] == "puesta en servicio"
        assert hist[1]["fijada_por"] == "Luz Adriana Maya"

    def test_solo_una_vigente_en_listar_vigentes(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(valor=0.627)
        _fijar(valor=0.640)
        vigentes = listar_vigentes()
        assert len(vigentes) == 1
        assert vigentes[0]["valor"] == pytest.approx(0.640)

    def test_una_fila_de_auditoria_por_cada_fijacion(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(valor=0.627)
        _fijar(valor=0.640)
        assert len(_filas_audit_ref(bd_temporal)) == 2

    def test_rollback_si_la_auditoria_falla_no_queda_nada_escrito(self, bd_temporal, monkeypatch):
        """La auditoría va en la MISMA transacción que el reemplazo: si
        falla, ni la anulación de la vigente ni el insert nuevo quedan."""
        _sembrar_los_tres(bd_temporal)
        _fijar(valor=0.627)

        def _auditoria_rota(*args, **kwargs):
            raise RuntimeError("auditoría caída")
        monkeypatch.setattr(anulacion_mod, "_registrar_auditoria", _auditoria_rota)

        with pytest.raises(RuntimeError):
            _fijar(valor=0.640)

        assert leer_referencia("Halcyon", "calidad", "6mv")["valor"] == pytest.approx(0.627)
        filas = _filas_ref(bd_temporal)
        assert len(filas) == 1


class TestValidacionDeEntrada:
    """Validado en el servicio, no solo en la pantalla -- por la misma
    razón que el permiso."""

    @pytest.mark.parametrize("fuente", ["", "   ", None])
    def test_fuente_obligatoria(self, bd_temporal, fuente):
        _sembrar_los_tres(bd_temporal)
        assert _fijar(fuente=fuente) == (False, FUENTE_OBLIGATORIA)
        assert _filas_ref(bd_temporal) == []

    @pytest.mark.parametrize("obs", ["", "   ", None])
    def test_observaciones_obligatorias(self, bd_temporal, obs):
        _sembrar_los_tres(bd_temporal)
        assert _fijar(observaciones=obs) == (False, OBSERVACIONES_OBLIGATORIAS)
        assert _filas_ref(bd_temporal) == []

    @pytest.mark.parametrize("valor", [0, -1, -0.5, "abc", None, "", math.nan, math.inf])
    def test_valor_debe_ser_numero_positivo_finito(self, bd_temporal, valor):
        _sembrar_los_tres(bd_temporal)
        assert _fijar(valor=valor) == (False, VALOR_INVALIDO)
        assert _filas_ref(bd_temporal) == []

    def test_valor_como_texto_numerico_se_acepta_como_numero(self, bd_temporal):
        """La pantalla entrega el texto de un QLineEdit."""
        _sembrar_los_tres(bd_temporal)
        assert _fijar(valor="0.627") == (True, None)
        assert leer_referencia("Halcyon", "calidad", "6mv")["valor"] == pytest.approx(0.627)

    def test_el_rechazo_por_validacion_no_deja_fila_de_auditoria(self, bd_temporal):
        _sembrar_los_tres(bd_temporal)
        _fijar(fuente="")
        assert _filas_audit_ref(bd_temporal) == []
