"""FG2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-FG2, hallazgo H1): tripwire
permanente para el arreglo de FG1.

Antes de FG1, el `DELETE` de `loadtablacomplex` ([load.py:527])
([load.py:198](../data/ManejoDatos/load.py), [load.py:782],
[seiscientos_mensual.py:3188]) borraba TODO el bloque de un `ref` -- sin
mirar `activo` -- así que una fila que el físico había anulado desde el
popup "Ver tabla" se destruía sin rastro en el siguiente "Subir" del mismo
control. `audit_log` quedaba con la anulación registrada apuntando a una
fila que ya no existía: incumplía DA-03 en las 17 tablas del grupo C
(§2.1-C del plan).

Reproduce la secuencia de §2.2 sobre CADA UNA de las 17 tablas -- no una
muestra -- y falla si alguna vuelve a perder su fila anulada:

    1. "Subir" un bloque -> 1 fila activa.
    2. Anular esa fila (activo=0), directo por SQL -- equivalente a lo que
       hace `anular_fila()` desde el popup, sin depender de las claves
       especiales por tabla del propio `anular_fila` (no hace falta para
       probar el DELETE de `loadtablacomplex`, que es lo que FG1 toca).
    3. "Subir" otra vez el MISMO bloque -> nueva fila activa.
    4. La fila anulada del paso 2 sigue existiendo (mismo `rowid`), y
       sigue con `activo=0` -- ni se borró ni se resucitó.
"""
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import loadtablacomplex, encontrar_columnas

# Grupo C del plan (§2.1): las 17 tablas cuyo DELETE no filtraba `activo`.
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
    conexion = Conexion()  # DDL + todas las migraciones reales (incl. FG1)
    conexion.con.close()
    Conexion._instance = None
    yield ruta


def _parametros_bloque(ruta_bd, tabla):
    """Deriva de la tabla, no de una lista a mano, los mismos parámetros
    que un llamador real le pasaría a `loadtablacomplex` -- `id=True` si la
    tabla tiene columna `id` propia (imita `_agregar_botones_tabla`,
    `id=True`, para las 15 con autoincremento; `id=False` para las 2 que no
    la tienen, `tamano_campo`/`analisis_placa_franjas`, imitando
    `_subir_tabla_optimizada`, `id=False` por defecto)."""
    con = sqlite3.connect(ruta_bd)
    columnas = [f[1] for f in con.execute(f"PRAGMA table_info({tabla})")]
    con.close()

    id_flag = "id" in columnas
    tiene_id_energia = "id_energia" in columnas
    tiene_tam_pdd = "tam_pdd" in columnas

    return {
        "id": id_flag,
        # FK real hacia `energias`, sembrada con ids 0-5 por
        # `_asegurar_catalogos_base` en cualquier BD nueva -- un id
        # inventado violaría la FK y el INSERT ni siquiera llegaría a
        # ejecutarse.
        "id_energia": 0 if tiene_id_energia else None,
        "anual": tiene_tam_pdd,
        "pdd": "10x10" if tiene_tam_pdd else None,
    }


def _construir_tabla_widget(ruta_bd, tabla, id_flag, valor):
    columnas_str, _ = encontrar_columnas(tabla, delete=0, id=id_flag)
    columnas_insert = [c.strip() for c in columnas_str.split(",")]
    columnas_widget = [c for c in columnas_insert
                        if c not in ("ref", "id_energia", "tam_pdd")]

    widget = QTableWidget()
    widget.setRowCount(1)
    widget.setColumnCount(len(columnas_widget))
    for col in range(len(columnas_widget)):
        widget.setItem(0, col, QTableWidgetItem(str(valor)))
    return widget


def _subir_bloque(ruta_bd, tabla, ref, params, valor):
    tabla_widget = _construir_tabla_widget(ruta_bd, tabla, params["id"], valor)
    loadtablacomplex(
        tabla, tabla_widget, [], reference=ref, from_range=0,
        id_energia=params["id_energia"], anual=params["anual"],
        pdd=params["pdd"], id=params["id"])


def _filas_de(ruta_bd, tabla, ref):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        f"SELECT rowid, activo FROM {tabla} WHERE ref=?", (ref,)).fetchall()
    con.close()
    return filas


@pytest.mark.parametrize("tabla", TABLAS_GRUPO_C)
def test_fg2_delete_respeta_anuladas(bd_temporal, tabla):
    ref = 555
    params = _parametros_bloque(bd_temporal, tabla)

    # `ref` tiene FK real hacia controles(id) -- sin esta fila padre, el
    # INSERT de loadtablacomplex fallaría por integridad referencial antes
    # de que el DELETE de FG1 entrara siquiera en juego.
    con = sqlite3.connect(bd_temporal)
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, activo) "
        "VALUES (?, 'equipo_test', 'Mensual', '08/2026', 1)", (ref,))
    con.commit()
    con.close()

    _subir_bloque(bd_temporal, tabla, ref, params, "primero")
    filas = _filas_de(bd_temporal, tabla, ref)
    assert len(filas) == 1, f"{tabla}: se esperaba 1 fila tras el primer Subir, hay {filas}"
    rowid_anulado = filas[0][0]

    con = sqlite3.connect(bd_temporal)
    con.execute(f"UPDATE {tabla} SET activo = 0 WHERE rowid = ?", (rowid_anulado,))
    con.commit()
    con.close()

    _subir_bloque(bd_temporal, tabla, ref, params, "segundo")

    filas_despues = dict(_filas_de(bd_temporal, tabla, ref))
    assert rowid_anulado in filas_despues, (
        f"{tabla}: el DELETE de loadtablacomplex destruyó la fila anulada "
        f"(rowid={rowid_anulado}) -- FG1 no está protegiendo esta tabla")
    assert filas_despues[rowid_anulado] == 0, (
        f"{tabla}: la fila anulada cambió de estado -- se esperaba que "
        f"siguiera activo=0, sin tocarla")
    assert len(filas_despues) >= 2, (
        f"{tabla}: se esperaban al menos 2 filas (la anulada + la nueva "
        f"activa), hay {filas_despues}")
