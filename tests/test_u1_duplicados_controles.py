"""U1 (PLAN_NUCLEO_04-08.md, Bloque U): medición de solo lectura de
duplicados en `controles`, previa a U2 (el índice UNIQUE parcial).

Fija el contrato de `services/duplicados_control.py::duplicados_controles`:
agrupa por (equipo, control, mes/año) SOLO entre filas activas, tolera los
dos formatos de fecha reales (MM/yyyy y dd/MM/yyyy, F3), nunca escribe nada,
y se expone en el reporte de `scripts/migrar_bd_a_estandar.py`. El último
test corre contra una COPIA de la BD de producción real -- la precondición
que el plan exige verificar antes de crear el índice de U2 (0 duplicados
hoy).
"""
import shutil
import sqlite3
from pathlib import Path

import pytest

from services.duplicados_control import duplicados_controles

ROOT = Path(__file__).resolve().parent.parent
BD_PRODUCCION = ROOT.parent / "BaseDatosQA.db"


def _con_memoria(filas):
    """filas: lista de (id, equipo, control, fecha, activo)."""
    con = sqlite3.connect(":memory:")
    con.execute(
        "CREATE TABLE controles (id INTEGER PRIMARY KEY, equipo TEXT, "
        "control TEXT, fecha TEXT, activo INTEGER)"
    )
    con.executemany(
        "INSERT INTO controles (id, equipo, control, fecha, activo) "
        "VALUES (?,?,?,?,?)", filas
    )
    con.commit()
    return con


class TestDuplicadosControlesSintetico:
    def test_sin_duplicados_devuelve_lista_vacia(self):
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "01/2026", 1),
            (2, "Clinac 600", "Mensual", "02/2026", 1),
        ])
        assert duplicados_controles(con) == []

    def test_dos_filas_mismo_mes_mismo_equipo_son_duplicado(self):
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "01/2026", 1),
            (2, "Clinac 600", "Mensual", "01/2026", 1),
        ])
        dup = duplicados_controles(con)
        assert len(dup) == 1
        assert dup[0]["equipo"] == "Clinac 600"
        assert dup[0]["control"] == "Mensual"
        assert dup[0]["mes"] == 1 and dup[0]["anio"] == 2026
        assert dup[0]["ids"] == [1, 2]

    def test_tolera_dia_y_sin_dia_como_el_mismo_mes(self):
        """El caso real de las 3 fichas de diciembre/2025: dd/MM/yyyy y
        MM/yyyy del mismo mes deben colisionar entre sí."""
        con = _con_memoria([
            (1, "Clinac ix", "Mensual", "14/12/2025", 1),
            (2, "Clinac ix", "Mensual", "12/2025", 1),
        ])
        dup = duplicados_controles(con)
        assert len(dup) == 1
        assert dup[0]["ids"] == [1, 2]

    def test_distinto_equipo_no_es_duplicado(self):
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "01/2026", 1),
            (2, "Clinac ix", "Mensual", "01/2026", 1),
        ])
        assert duplicados_controles(con) == []

    def test_distinto_tipo_de_control_no_es_duplicado(self):
        con = _con_memoria([
            (1, "Clinac ix", "Mensual", "01/2026", 1),
            (2, "Clinac ix", "Anual", "01/2026", 1),
        ])
        assert duplicados_controles(con) == []

    def test_fila_anulada_no_cuenta_para_el_duplicado(self):
        """El caso excepcional que el físico pidió preservar: anular un
        control y crear otro del mismo mes NO debe reportarse como
        duplicado -- solo las filas activas entran en el conteo."""
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "01/2026", 0),  # anulado
            (2, "Clinac 600", "Mensual", "01/2026", 1),  # el vigente
        ])
        assert duplicados_controles(con) == []

    def test_dos_filas_anuladas_no_cuentan(self):
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "01/2026", 0),
            (2, "Clinac 600", "Mensual", "01/2026", 0),
        ])
        assert duplicados_controles(con) == []

    def test_activo_null_se_trata_como_activo(self):
        """`activo` es NULL en filas históricas anteriores a C2/E7 -- deben
        tratarse como activas (mismo criterio que el resto del proyecto,
        `WHERE activo IS NULL OR activo = 1`)."""
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "01/2026", None),
            (2, "Clinac 600", "Mensual", "01/2026", None),
        ])
        dup = duplicados_controles(con)
        assert len(dup) == 1
        assert dup[0]["ids"] == [1, 2]

    def test_fecha_no_reconocible_no_revienta_y_no_cuenta(self):
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "", 1),
            (2, "Clinac 600", "Mensual", "fecha-invalida", 1),
        ])
        assert duplicados_controles(con) == []

    def test_tres_filas_mismo_grupo_reporta_las_tres(self):
        con = _con_memoria([
            (1, "Clinac 600", "Mensual", "01/2026", 1),
            (2, "Clinac 600", "Mensual", "05/01/2026", 1),
            (3, "Clinac 600", "Mensual", "20/01/2026", 1),
        ])
        dup = duplicados_controles(con)
        assert len(dup) == 1
        assert dup[0]["ids"] == [1, 2, 3]


@pytest.mark.skipif(not BD_PRODUCCION.exists(), reason="BD de producción no disponible en este entorno")
class TestDuplicadosControlesContraBDReal:
    def test_precondicion_de_u2_cero_duplicados_hoy(self, tmp_path):
        """Precondición medida y documentada en PLAN_NUCLEO_04-08.md §1.4:
        0 duplicados por (equipo, control, mes/año) sobre las filas activas
        de producción, hoy. Este test corre sobre una COPIA (nunca abre la
        BD real en modo escritura) y sirve de tripwire: si algún día
        aparece un duplicado real, este test lo señala ANTES de que U2
        (el índice UNIQUE) pudiera fallar al crearse."""
        copia = tmp_path / "copia_solo_lectura.db"
        shutil.copy(BD_PRODUCCION, copia)
        con = sqlite3.connect(str(copia))
        try:
            dup = duplicados_controles(con)
        finally:
            con.close()
        assert dup == [], (
            f"Aparecieron duplicados en producción -- decisión del físico, "
            f"no del código, antes de crear el índice de U2: {dup}"
        )
