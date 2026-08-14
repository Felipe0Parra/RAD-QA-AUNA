"""CT2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-CT2): `loadtablacomplex`
reemplaza el `DELETE` físico por `UPDATE ... SET activo = 0` para las 17
tablas del grupo C -- la misma transformación que M2 (11-08) ya aplicó a
control_cunas/control_conos/equipos_medicion.

Complementa a `test_fg2_delete_respeta_anuladas.py` (que prueba que una
fila YA anulada por el físico sobrevive un "Subir" posterior) con lo que
CT2 añade de nuevo:

    1. El mecanismo central: dos "Subir" seguidos, SIN anulación manual
       de por medio, dejan el bloque viejo histórico (activo=0) y el
       nuevo vigente (activo=1) -- nunca los dos activos ni el viejo
       borrado.
    2. Invariante 3 del contrato: si el segundo "Subir" no trae ningún
       dato válido (la tabla del widget quedó vacía), el bloque vigente
       NO se anula -- se queda como estaba.
    3. Contraparte de alcance: una tabla que NO está en TABLAS_ANULABLES
       (indicadores_brazo, mensual 600/iX) sigue con DELETE físico sin
       cambios -- este plan no la toca.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import loadtablacomplex, encontrar_columnas

TABLAS_GRUPO_C = [
    "tamano_campo",
    "analisis_placa_franjas",
    "tabla_factor_campo",
    "tabla_factores_transmision",
    "tabla_factores_sobre_eje",
    "tabla_control_camaras_monitoras",
    "HC_indicadores_brazo",
    "HC_indicadores_colimador",
    "HC_indicadores_laser",
    "HC_indicadores_camilla",
    "HC_desplazamiento_isocentro_mensual",
    "HC_velocidad_multilaminas_anual",
    "HC_precision_posicion_multilaminas_anual",
    "HC_imagen_perfil_mlc_anual",
    "HC_dosimetria_anual",
    "HC_linealidad_unidades_monitor_anual",
    "HC_tamanos_campo_radiacion",
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.close()
    Conexion._instance = None
    yield ruta


def _parametros_bloque(ruta_bd, tabla):
    con = sqlite3.connect(ruta_bd)
    columnas = [f[1] for f in con.execute(f"PRAGMA table_info({tabla})")]
    con.close()

    id_flag = "id" in columnas
    tiene_id_energia = "id_energia" in columnas
    tiene_tam_pdd = "tam_pdd" in columnas

    return {
        "id": id_flag,
        "id_energia": 0 if tiene_id_energia else None,
        "anual": tiene_tam_pdd,
        "pdd": "10x10" if tiene_tam_pdd else None,
    }


def _construir_tabla_widget(tabla, id_flag, valor, n_filas=1):
    columnas_str, _ = encontrar_columnas(tabla, delete=0, id=id_flag)
    columnas_insert = [c.strip() for c in columnas_str.split(",")]
    columnas_widget = [c for c in columnas_insert
                        if c not in ("ref", "id_energia", "tam_pdd")]

    widget = QTableWidget()
    widget.setRowCount(n_filas)
    widget.setColumnCount(len(columnas_widget))
    for fila in range(n_filas):
        for col in range(len(columnas_widget)):
            widget.setItem(fila, col, QTableWidgetItem(f"{valor}_{fila}"))
    return widget


def _subir_bloque(tabla, ref, params, valor, n_filas=1):
    tabla_widget = _construir_tabla_widget(tabla, params["id"], valor, n_filas)
    return loadtablacomplex(
        tabla, tabla_widget, [], reference=ref, from_range=0,
        id_energia=params["id_energia"], anual=params["anual"],
        pdd=params["pdd"], id=params["id"])


def _filas_de(ruta_bd, tabla, ref):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        f"SELECT rowid, activo FROM {tabla} WHERE ref=?", (ref,)).fetchall()
    con.close()
    return filas


def _insertar_controles(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, activo) "
        "VALUES (?, 'Clinac ix', 'Anual', '08/2026', 1)", (ref,))
    con.commit()
    con.close()


@pytest.mark.parametrize("tabla", TABLAS_GRUPO_C)
def test_dos_subir_seguidos_dejan_uno_historico_y_uno_vigente(bd_temporal, tabla):
    ref = 700
    params = _parametros_bloque(bd_temporal, tabla)
    _insertar_controles(bd_temporal, ref)

    ok1 = _subir_bloque(tabla, ref, params, "primero")
    filas1 = _filas_de(bd_temporal, tabla, ref)
    assert ok1 is True
    assert len(filas1) == 1
    rowid_viejo = filas1[0][0]
    assert filas1[0][1] == 1

    ok2 = _subir_bloque(tabla, ref, params, "segundo")
    filas2 = dict(_filas_de(bd_temporal, tabla, ref))

    assert ok2 is True
    assert rowid_viejo in filas2, f"{tabla}: el bloque viejo desapareció (se borró)"
    assert filas2[rowid_viejo] == 0, (
        f"{tabla}: el bloque viejo debía quedar histórico (activo=0), "
        f"sigue en {filas2[rowid_viejo]}")
    activos = [rowid for rowid, activo in filas2.items() if activo == 1]
    assert len(activos) == 1, (
        f"{tabla}: debía quedar UN solo bloque vigente, hay {len(activos)}")
    assert activos[0] != rowid_viejo


@pytest.mark.parametrize("tabla", TABLAS_GRUPO_C)
def test_invariante_3_datos_vacios_no_anula_el_vigente(bd_temporal, tabla):
    ref = 701
    params = _parametros_bloque(bd_temporal, tabla)
    _insertar_controles(bd_temporal, ref)

    _subir_bloque(tabla, ref, params, "vigente")
    filas_antes = _filas_de(bd_temporal, tabla, ref)
    assert len(filas_antes) == 1 and filas_antes[0][1] == 1

    # Widget con 0 filas -> loadtablacomplex arma `datos = []`.
    tabla_vacia = QTableWidget()
    tabla_vacia.setRowCount(0)
    tabla_vacia.setColumnCount(1)
    ok = loadtablacomplex(
        tabla, tabla_vacia, [], reference=ref, from_range=0,
        id_energia=params["id_energia"], anual=params["anual"],
        pdd=params["pdd"], id=params["id"])

    filas_despues = _filas_de(bd_temporal, tabla, ref)
    assert ok is True
    assert filas_despues == filas_antes, (
        f"{tabla}: un guardado sin datos válidos anuló el bloque vigente "
        f"-- {filas_antes} -> {filas_despues}")


def test_tabla_fuera_del_bloque_qc_sigue_con_delete_fisico(bd_temporal):
    """indicadores_brazo (mensual 600/iX) no está en TABLAS_ANULABLES --
    fuera de alcance de CT2, debe seguir borrando de verdad."""
    ref = 702
    _insertar_controles(bd_temporal, ref)

    columnas_str, _ = encontrar_columnas("indicadores_brazo", delete=0, id=False)
    columnas_widget = [c.strip() for c in columnas_str.split(",") if c.strip() != "ref"]
    widget1 = QTableWidget()
    widget1.setRowCount(1)
    widget1.setColumnCount(len(columnas_widget))
    for col in range(len(columnas_widget)):
        widget1.setItem(0, col, QTableWidgetItem("primero"))
    loadtablacomplex("indicadores_brazo", widget1, [], reference=ref,
                      from_range=0, id_energia=None, anual=False, id=False)

    widget2 = QTableWidget()
    widget2.setRowCount(1)
    widget2.setColumnCount(len(columnas_widget))
    for col in range(len(columnas_widget)):
        widget2.setItem(0, col, QTableWidgetItem("segundo"))
    loadtablacomplex("indicadores_brazo", widget2, [], reference=ref,
                      from_range=0, id_energia=None, anual=False, id=False)

    con = sqlite3.connect(bd_temporal)
    total = con.execute(
        "SELECT COUNT(*) FROM indicadores_brazo WHERE ref=?", (ref,)).fetchone()[0]
    con.close()
    assert total == 1, (
        "indicadores_brazo no está en el bloque de QC -- debía seguir "
        f"reemplazando físicamente (1 fila), hay {total}")
