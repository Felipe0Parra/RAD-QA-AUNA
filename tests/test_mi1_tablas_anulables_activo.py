"""MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1, DA-40): `TABLAS_ANULABLES` se
amplía de verdad -- las 30 tablas que esperaban en `EXCEPCIONES_INVENTARIO`
con motivo `"PENDIENTE-LF"` se mueven al frozenset. Ya no hace falta esperar
más: LF (Fase 3, `LF1`-`LF5`) filtró las 74 lecturas del bloque y LR4 (Fase
3-bis, DA-48) cerró el alcance de AN1/RT1 sobre el bloque de QC completo.

Este test verifica el EFECTO, no solo la forma:
  1. El frozenset y las excepciones quedan exactamente como predice §4.4 del
     plan (59 = 52 hijas + 7 raíces; solo 2 excepciones, ninguna PENDIENTE-LF).
  2. Sobre una BD temporal recién creada (mismo mecanismo que IV2/IV1b:
     `Conexion()` real, nunca un archivo de referencia -- regla de sesión),
     las 30 tablas reciben `activo INTEGER DEFAULT 1` al arrancar, sin que
     ninguna fila se reescriba y sin decapitar el resto del bloque (IV1b ya
     lo protege; aquí se comprueba sobre el inventario REAL, no uno de
     prueba).
  3. `angulos_entre_lineas_starshot` gana además `par_index` (DA-45),
     declarada como parte de su clave en `CLAVES_INDICE` desde IV3 pero sin
     columna real hasta ahora.
  4. Las 7 tablas cuyo `CREATE TABLE` ya declaraba `activo BOOLEAN DEFAULT 1`
     de antemano (rama braquiterapia + placa) no quedan con una columna
     duplicada ni de otro tipo -- `_asegurar_columna` es idempotente.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.anulacion import EXCEPCIONES_INVENTARIO, TABLAS_ANULABLES
from services.lectura_vigente import RAICES_QC, tablas_pendientes_lf

# Las 30 tablas que MI1 mueve (§2.7/§4.4 del plan) -- literal, para que un
# descuido que deje una fuera (o una de más) se note aquí mismo, no solo en
# el conteo agregado.
TABLAS_MI1 = frozenset({
    "CondicionesMedicion", "SistemaMedicion", "MaximosCamaras",
    "LecturasMaximos", "ResultadosActividad",
    "analisis_placa_verificaciones", "analisis_placa_correcciones",
    "indicadores_brazo", "indicadores_angulares_colimador",
    "pruebas", "espesor_corte", "linealidad_ct", "resolucion_contraste",
    "resolucion_contraste_rois", "resolucion_espacial",
    "resolucion_espacial_regiones", "tamaño_pixel", "uniformidad_global",
    "uniformidad_ruido", "valores_ct",
    "HC_fantomas", "configuracion_picketfence", "error_picket",
    "leaf_error", "highest_leaf_errors", "configuracion_starshot",
    "estadisticas_starshot", "angulo_starshot",
    "angulos_entre_lineas_starshot", "uniformidad_angular_starshot",
})

# Ya declaraban `activo BOOLEAN DEFAULT 1` en su propio CREATE TABLE antes de
# MI1 (adelantado en el esquema, pero inerte hasta que la tabla entrara al
# frozenset -- `_asegurar_activo_bloque_qc` solo actúa sobre
# `TABLAS_ANULABLES`). El resto de TABLAS_MI1 no tenía la columna en absoluto.
TABLAS_MI1_CON_ACTIVO_YA_EN_EL_DDL = frozenset({
    "CondicionesMedicion", "SistemaMedicion", "MaximosCamaras",
    "LecturasMaximos", "ResultadosActividad",
    "analisis_placa_verificaciones", "analisis_placa_correcciones",
})


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield conexion
    conexion.con.close()
    Conexion._instance = None


def _columnas(con, tabla):
    return [c[1] for c in con.execute(f"PRAGMA table_info('{tabla}')").fetchall()]


class TestInventarioTrasMI1:

    def test_las_30_tablas_de_mi1_estan_en_el_frozenset(self):
        faltantes = TABLAS_MI1 - TABLAS_ANULABLES
        assert not faltantes, (
            f"MI1 debía mover estas tablas a TABLAS_ANULABLES y no aparecen: "
            f"{faltantes}")

    def test_el_frozenset_tiene_59_entradas(self):
        assert len(TABLAS_ANULABLES) == 59, (
            f"52 hijas + 7 raíces tras MI1 (§4.4 del plan) -- hay "
            f"{len(TABLAS_ANULABLES)}. Si el cambio es deliberado, "
            f"actualiza este número a la vez que TABLAS_ANULABLES.")

    def test_solo_quedan_las_dos_excepciones_definitivas(self):
        assert set(EXCEPCIONES_INVENTARIO) == {
            "equipos_anual", "posicionamiento_reposicionamiento"}, (
            f"tras MI1 solo deben quedar en EXCEPCIONES_INVENTARIO las dos "
            f"tablas que NUNCA van a versionar -- hay: "
            f"{sorted(EXCEPCIONES_INVENTARIO)}")

    def test_ninguna_tabla_sigue_pendiente_lf(self):
        """`tablas_pendientes_lf()` deriva del motivo en
        EXCEPCIONES_INVENTARIO -- con las 30 movidas, debe quedar vacía. Es
        lo que hace que `tablas_con_filtro_no_op()` (RT1, DA-46) se vacíe
        solo y RT1 recupere el fallo duro sobre las 30 sin tocar el
        interceptor."""
        assert tablas_pendientes_lf() == frozenset()

    def test_las_raices_siguen_dentro(self):
        assert RAICES_QC <= TABLAS_ANULABLES


class TestActivoLlegaALasTreintaTablas:

    def test_cada_tabla_de_mi1_recibe_activo_al_arrancar(self, bd_temporal):
        con = bd_temporal.con
        sin_columna = [t for t in sorted(TABLAS_MI1)
                       if "activo" not in _columnas(con, t)]
        assert not sin_columna, (
            f"estas tablas de MI1 arrancaron sin 'activo': {sin_columna} -- "
            f"_asegurar_activo_bloque_qc no las cubrió")

    def test_activo_aparece_una_sola_vez_por_tabla(self, bd_temporal):
        """Las 7 que ya declaraban `activo` en su CREATE TABLE no deben
        terminar con una columna duplicada -- `_asegurar_columna` debe
        seguir siendo un no-op cuando la columna ya existe."""
        con = bd_temporal.con
        for tabla in sorted(TABLAS_MI1_CON_ACTIVO_YA_EN_EL_DDL):
            cols = _columnas(con, tabla)
            assert cols.count("activo") == 1, (
                f"{tabla} terminó con {cols.count('activo')} columnas "
                f"'activo' -- debía tener exactamente 1")

    def test_las_filas_existentes_se_leen_como_vigentes_sin_reescritura(
        self, bd_temporal,
    ):
        """DEFAULT 1 hace que una fila insertada ANTES de que `activo`
        exista (simulado insertando antes de correr la migración de nuevo)
        siga leyéndose como vigente sin ningún UPDATE. Se ensaya sobre
        `pruebas`, que no tenía la columna en el DDL."""
        con = bd_temporal.con
        con.execute("INSERT INTO users (fullname) VALUES ('fisico de prueba')")
        con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id) "
            "VALUES ('equipo', 'control', '01/2026', 'fisico de prueba')")
        # tipos_prueba ya viene sembrado por _asegurar_catalogos_base --
        # se reusa el primero en vez de insertar uno nuevo.
        id_tipo = con.execute(
            "SELECT id_tipo FROM tipos_prueba LIMIT 1").fetchone()[0]
        con.execute(
            "INSERT INTO pruebas (id_sesion, id_tipo, kv, ma, espesor_corte) "
            "VALUES (1, ?, 120, 100, 1.0)", (id_tipo,))
        con.commit()
        fila = con.execute(
            "SELECT activo FROM pruebas WHERE id_sesion = 1 AND id_tipo = ?",
            (id_tipo,)).fetchone()
        assert fila is not None
        assert fila[0] in (1, None), (
            "una fila nueva sobre una tabla recién migrada debe leerse como "
            "vigente (activo=1, o NULL bajo el mismo criterio que "
            "filtro_activo usa: 'activo IS NULL OR activo = 1')")

    def test_par_index_llega_a_angulos_entre_lineas_starshot(self, bd_temporal):
        con = bd_temporal.con
        assert "par_index" in _columnas(con, "angulos_entre_lineas_starshot"), (
            "DA-45 (§4.3 del plan): angulos_entre_lineas_starshot debía "
            "ganar la columna ordinal par_index en MI1")

    def test_posicionamiento_reposicionamiento_no_se_toca(self, bd_temporal):
        """Sigue bloqueada en DP-38 (huérfana, sin CREATE TABLE) -- MI1 no
        la mueve al frozenset, así que _asegurar_activo_bloque_qc ni
        siquiera la intenta: no debe existir en la BD nueva."""
        con = bd_temporal.con
        tablas = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "posicionamiento_reposicionamiento" not in tablas

    def test_equipos_anual_no_se_crea_en_una_bd_nueva(self, bd_temporal):
        """DA-44: `equipos_anual` no tiene NINGÚN `CREATE TABLE` en
        `conection.py` -- solo existe (vacía) en BD antiguas ya desplegadas.
        Sigue fuera de TABLAS_ANULABLES (se retira en MI5, no se versiona),
        así que en una BD nueva ni siquiera aparece."""
        con = bd_temporal.con
        tablas = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "equipos_anual" not in tablas
