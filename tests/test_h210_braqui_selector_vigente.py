"""H2.10 (PLAN_FASE_H, 2026-07-16) -- braquiterapia (diaria y mensual) elegía
la cámara/electrómetro por `id IN (SELECT MAX(id) FROM equipos GROUP BY
serie)`, ignorando `vigente` por completo. Con datos sucios (duplicados,
correcciones que dejan una fila vieja con id más alto marcada histórica) esa
consulta podía elegir una fila inactiva y hacer desaparecer un equipo entero
del selector -- caso real: el pozo A972662 desapareció de braquiterapia tras
el saneamiento H2.6 porque la fila de mayor id de esa serie (id 71, un
duplicado corregido a `vigente=0`) es la que la consulta antigua leía.

Estos tests verifican los helpers nuevos de `EquiposService`
(`modelos_actuales`, `series_actuales`, `calibracion_actual`) que reemplazan
esas 12 consultas crudas -- sobre una BD temporal replicando los patrones de
datos reales encontrados en producción (ver CLAUDE.md, entrada "H2.10
EJECUTADA"). No se prueban los widgets de Qt directamente (braquiterapia.py/
braq_mensual.py no tenían ningún test antes de H2.10 y construirlos aisladamente
excede el alcance de esta tarea) -- se prueba la capa que sí es testeable y de
la que depende toda la lógica de selección.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion

from services.equipos_service import EquiposService


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _insertar_equipo(ruta_bd, eq_id, **campos):
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


class TestPozoA972662:
    """Caso real: id16 vigente (id bajo) vs id71 no-vigente (id más alto,
    duplicado corregido por H2.6). La consulta vieja MAX(id) elegía id71 y
    el equipo desaparecía; el helper nuevo debe elegir id16 por `vigente`."""

    def _poblar(self, ruta_bd):
        _insertar_equipo(ruta_bd, 16, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A972662",
                         calibr_fact=466700, t_cal=22.0, p_cal=101.325,
                         h_cal=38, fecha_calibr="07/02/2024",
                         activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 71, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A972662",
                         calibr_fact=4.667, t_cal=22.0, p_cal=101.325,
                         h_cal=38, fecha_calibr="7/02/2025",
                         activo=0, vigente=0)

    def test_modelo_sigue_apareciendo(self, bd_temporal):
        self._poblar(bd_temporal)
        assert "HDR1000 Plus" in EquiposService.modelos_actuales("Cámara de pozo")

    def test_serie_sigue_apareciendo_como_vigente(self, bd_temporal):
        self._poblar(bd_temporal)
        series = EquiposService.series_actuales("Cámara de pozo", "HDR1000 Plus")
        assert ("A972662", 1.0, 1.0) in series

    def test_calibracion_es_la_de_la_fila_vigente_no_la_de_mayor_id(self, bd_temporal):
        self._poblar(bd_temporal)
        datos = EquiposService.calibracion_actual(
            "Cámara de pozo", "HDR1000 Plus", "A972662")
        assert datos is not None
        assert datos["calibr_fact"] == 466700  # id16, NO 4.667 (id71)


class TestPozoA092535:
    """id77 es a la vez vigente Y el id más alto -- este caso ya funcionaba
    bien con MAX(id) y debe seguir funcionando igual con el helper nuevo."""

    def _poblar(self, ruta_bd):
        for eq_id in (57, 58, 63):
            _insertar_equipo(ruta_bd, eq_id, equip_type="Cámara de pozo",
                             model="HDR1000 Plus", serie="A092535",
                             calibr_fact=46470, activo=0, vigente=0)
        _insertar_equipo(ruta_bd, 77, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=464700, activo=1, vigente=1)

    def test_calibracion_correcta(self, bd_temporal):
        self._poblar(bd_temporal)
        datos = EquiposService.calibracion_actual(
            "Cámara de pozo", "HDR1000 Plus", "A092535")
        assert datos["calibr_fact"] == 464700


class TestPozoSomerRetirado:
    """Las 3 filas de la Somer quedaron activo=0/vigente=0 tras H2.6 (equipo
    prestado, devuelto). El helper hace fallback al id más alto (56) y lo
    devuelve como fila actual -- igual que la consulta original,
    `series_actuales` no filtra `activo` en SQL, devuelve la columna para
    que el llamador decida (así lo hacían ya `_poblar_combo_series` /
    `on_modelo_elec_cambio`, sin cambios en H2.10). Por eso el modelo
    "HDR1000 Plus" desaparece por completo (ninguna serie activa), pero la
    fila de la serie sí puede recuperarse con activo=0 para quien la pida."""

    def _poblar(self, ruta_bd):
        for eq_id in (54, 55, 56):
            _insertar_equipo(ruta_bd, eq_id, equip_type="Cámara de pozo",
                             model="HDR1000 Plus", serie="A132690 Somer",
                             calibr_fact=467900, activo=0, vigente=0)

    def test_no_aparece_en_modelos(self, bd_temporal):
        self._poblar(bd_temporal)
        assert EquiposService.modelos_actuales("Cámara de pozo") == []

    def test_serie_actual_es_la_de_mayor_id_pero_marcada_inactiva(self, bd_temporal):
        # El helper sigue devolviendo la fila (id56, la de mayor id entre
        # las 3) para que el llamador la filtre por `activo` -- igual que
        # el contrato original. Ningún dato desaparece de la capa de datos;
        # lo que desaparece es la entrada en el combo, decisión de la UI.
        self._poblar(bd_temporal)
        series = EquiposService.series_actuales("Cámara de pozo", "HDR1000 Plus")
        assert series == [("A132690 Somer", 0.0, 0.0)]
        # Y así es como el llamador (sin cambios en H2.10) la excluye del combo:
        series_activas = [s for s, activo, _ in series if activo == 1.0]
        assert series_activas == []


class TestElectrometroSinFilaVigente:
    """Un electrómetro cuya calibración nunca se marcó vigente (p.ej.
    T10010/BEAMSCAN en la BD real) no debe desaparecer: sigue activo, se
    hace fallback al id más alto, y sigue mostrándose (el llamador lo marca
    "⚠️ VENCIDO" porque vigente=0)."""

    def _poblar(self, ruta_bd):
        _insertar_equipo(ruta_bd, 10, equip_type="Electrómetro",
                         model="T10010", serie="000123",
                         calibr_fact=1.0, activo=1, vigente=0)
        _insertar_equipo(ruta_bd, 20, equip_type="Electrómetro",
                         model="T10010", serie="000123",
                         calibr_fact=1.05, activo=1, vigente=0)

    def test_sigue_visible_marcable_como_vencido(self, bd_temporal):
        self._poblar(bd_temporal)
        series = EquiposService.series_actuales("Electrómetro", "T10010")
        assert ("000123", 1.0, 0.0) in series

    def test_calibracion_toma_la_de_mayor_id_por_fallback(self, bd_temporal):
        self._poblar(bd_temporal)
        datos = EquiposService.calibracion_actual(
            "Electrómetro", "T10010", "000123")
        assert datos["calibr_fact"] == 1.05  # id20, el de mayor id


class TestElectrometroCDX2000BDobleVigente:
    """Caso encontrado en producción: dos filas de la MISMA serie quedaron
    vigente=1 a la vez (id18 de 2024 y id79, la recalibración 2026). Antes
    de que H2.10 corrija los datos (o si un descuido futuro repite el
    patrón), el helper debe seguir resolviendo de forma determinística: el
    id más alto desempata entre vigentes."""

    def _poblar(self, ruta_bd):
        _insertar_equipo(ruta_bd, 18, equip_type="Electrómetro",
                         model="CDX-2000B", serie="B091982",
                         calibr_fact=999, fecha_calibr="05/02/2024",
                         activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 79, equip_type="Electrómetro",
                         model="CDX-2000B", serie="B091982",
                         calibr_fact=111, fecha_calibr="17/03/2026",
                         activo=1, vigente=1)

    def test_elige_el_id_mas_alto_entre_los_dos_vigentes(self, bd_temporal):
        self._poblar(bd_temporal)
        datos = EquiposService.calibracion_actual(
            "Electrómetro", "CDX-2000B", "B091982")
        assert datos["calibr_fact"] == 111  # id79, no id18


class TestCalibracionActualSerieInexistente:
    def test_devuelve_none(self, bd_temporal):
        assert EquiposService.calibracion_actual(
            "Cámara de pozo", "HDR1000 Plus", "NO-EXISTE") is None
