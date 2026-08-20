"""MI0 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI0): regresión del defecto real
encontrado al construir el tripwire MI0-T (`test_mi0_select_star_no_posicional.py`).

`Linealidad.construir_tablas_reporte_linealidad` (braquiterapia.py) leía
`SELECT * FROM LinealidadBraquiterapia` por índice posicional con un desfase
de **+1 en los 34 valores** -- el esquema real tiene la columna `user` en la
posición 1 (antes de `fecha`), pero el código fue escrito asumiendo un
esquema sin ella. El PDF de reporte de linealidad de la fuente de
braquiterapia mostraba la FECHA bajo la etiqueta "Modelo cámara", y en
cascada cada valor bajo la etiqueta equivocada -- incluida una lectura de
"Tiempo parada (s)" mostrando ~3657 en vez de 0.1 (4 órdenes de magnitud).

Preexistente desde antes del commit inicial (`git log -S` sobre los índices
y la función solo devuelve `408090b`), verificado con un subagente Opus por
las implicaciones clínicas del reporte (nunca antes cubierto por un test).
Corregido a acceso por nombre vía `cursor.description` en el mismo commit
que este archivo.

Este test construye una fila SINTÉTICA con un valor DISTINTO Y RECONOCIBLE
por columna (para que un desfase de índice produzca un valor visiblemente
equivocado, no un falso verde por coincidencia numérica) y verifica que
cada `DataFrame` que arma el método trae el valor de la columna correcta.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    def __init__(self, nombre):
        self._nombre = nombre


def _insertar_fila_reconocible(ruta_bd, fecha):
    """Un valor DISTINTO por columna -- string único para las de texto,
    número único (multiplicado por una base grande) para las numéricas --
    así un desfase de índice trae un valor de OTRA columna, detectable."""
    con = sqlite3.connect(ruta_bd)
    columnas = [c[1] for c in con.execute(
        "PRAGMA table_info(LinealidadBraquiterapia)").fetchall()]
    columnas_dato = [c for c in columnas if c not in ("id", "activo")]

    valores = {}
    for i, col in enumerate(columnas_dato):
        if col == "user":
            valores[col] = "Físico de Prueba"
        elif col == "fecha":
            valores[col] = fecha
        elif col in ("modelo", "serie_cp", "modelo_elec", "serie_ele"):
            valores[col] = f"TEXTO_{col}"
        else:
            valores[col] = 1000.0 + i  # único y grande -- un desfase de
                                        # índice trae un número claramente
                                        # distinto, no una coincidencia

    cols_sql = ", ".join(f'"{c}"' for c in columnas_dato)
    placeholders = ", ".join("?" for _ in columnas_dato)
    con.execute(
        f"INSERT INTO LinealidadBraquiterapia ({cols_sql}) VALUES ({placeholders})",
        [valores[c] for c in columnas_dato])
    con.commit()
    con.close()
    return valores


class TestMapeoCorrectoDelReporteDeLinealidad:

    def test_sistema_medicion_trae_las_columnas_correctas(self, app, bd_temporal):
        valores = _insertar_fila_reconocible(bd_temporal, "2026-06-01")
        obj = Linealidad(_UsuarioFalso("Físico de Prueba"))

        resultado = obj.construir_tablas_reporte_linealidad("2026-06-01")
        assert resultado is not None
        df_sistema = resultado["sistema_medicion_linealidad"]

        esperado = [valores["modelo"], valores["serie_cp"], valores["calibracion"],
                    valores["modelo_elec"], valores["serie_ele"], valores["electrometro"]]
        assert list(df_sistema["Valor"]) == esperado

    def test_carga_colectada_trae_las_columnas_correctas(self, app, bd_temporal):
        valores = _insertar_fila_reconocible(bd_temporal, "2026-06-02")
        obj = Linealidad(_UsuarioFalso("Físico de Prueba"))

        df_carga = obj.construir_tablas_reporte_linealidad("2026-06-02")["carga_colectada"]

        esperado = [valores["q_est"], valores["t_integrado"], valores["i_est"],
                    valores["repro_m1"], valores["repro_m2"], valores["repro_m3"],
                    valores["repro_m4"], valores["repro_m5"], valores["repro_prom"]]
        assert list(df_carga["Valor"]) == esperado

    def test_resultados_trae_las_columnas_correctas(self, app, bd_temporal):
        valores = _insertar_fila_reconocible(bd_temporal, "2026-06-03")
        obj = Linealidad(_UsuarioFalso("Físico de Prueba"))

        df_resultados = obj.construir_tablas_reporte_linealidad("2026-06-03")["resultados_linealidad"]

        esperado = [valores["reproducibilidad"], valores["exactitud"], valores["tiempo_transito"]]
        assert list(df_resultados["Valor"]) == esperado

    def test_medidas_las_10_filas_y_recupera_lin_te_9(self, app, bd_temporal):
        """El bucle viejo usaba base=20+i*5 -- se comía lin_te_9 (nunca se
        leía). El correcto es base=21+i*5."""
        valores = _insertar_fila_reconocible(bd_temporal, "2026-06-04")
        obj = Linealidad(_UsuarioFalso("Físico de Prueba"))

        df_medidas = obj.construir_tablas_reporte_linealidad("2026-06-04")["medidas_linealidad"]

        assert len(df_medidas) == 10
        for i in range(10):
            fila = df_medidas.iloc[i]
            assert fila["Tiempo parada (s)"] == valores[f"lin_tp_{i}"]
            assert fila["Q1 (nC)"] == valores[f"lin_q1_{i}"]
            assert fila["Q2 (nC)"] == valores[f"lin_q2_{i}"]
            assert fila["Qprom (nC)"] == valores[f"lin_qprom_{i}"]
            assert fila["T. efectivo (s)"] == valores[f"lin_te_{i}"], (
                "fila 9 (i=9): el bucle viejo (base=20+i*5) nunca leía "
                "lin_te_9 -- si esto falla, volvió el desfase")

    def test_filtra_activo_y_toma_la_mas_reciente(self, app, bd_temporal):
        """MI0 también agregó filtro_activo() + ORDER BY id DESC -- sin
        esto, fetchone() sin ordenar podía tomar una fila anulada o
        arbitraria entre varias de la misma fecha."""
        con = sqlite3.connect(bd_temporal)
        columnas = [c[1] for c in con.execute(
            "PRAGMA table_info(LinealidadBraquiterapia)").fetchall()
            if c[1] not in ("id",)]
        con.close()

        _insertar_fila_reconocible(bd_temporal, "2026-06-05")
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "UPDATE LinealidadBraquiterapia SET activo = 0 WHERE fecha = ?",
            ("2026-06-05",))
        con.commit()
        con.close()

        valores_vigentes = _insertar_fila_reconocible(bd_temporal, "2026-06-05")

        obj = Linealidad(_UsuarioFalso("Físico de Prueba"))
        df_sistema = obj.construir_tablas_reporte_linealidad("2026-06-05")["sistema_medicion_linealidad"]

        assert list(df_sistema["Valor"])[0] == valores_vigentes["modelo"], (
            "trajo la fila anulada o una fila arbitraria, no la vigente")
