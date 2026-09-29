"""W.1 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, segunda ronda -- versión
MÍNIMA, §R.3 fila 5): en las dos tablas "Ver tabla" de braquiterapia, cada
celda con metadatos de edición (`Qt.UserRole`/`Qt.UserRole + 1`) muestra
EXACTAMENTE el dato que la BD tiene en esa columna -- ninguna celda editable
puede mostrar el valor de otra.

CAUSA medida (§1.10/§1.8 del plan):
- `load.py::mostrar_db_mensualBraqui` -- `col_mapeo` tenía la clave `27`
  (el índice de "Ktp" en `headers`) en vez de `28` ("Act. Monitor"): la
  única celda editable de la tabla quedaba bajo "Ktp" y escribía
  `actividad_monitor`.
- `load.py::mostrar_db_linealidad` -- `datos_visibles` traía
  `[id_pk, fecha, usuario, ...]` cuando `headers_lin` declara "Usuario"
  antes que "Fecha": la columna "Usuario" mostraba la fecha y viceversa.

Este tripwire NO lista celdas a mano: recorre TODA celda con metadatos de
las dos tablas y la compara contra `SELECT columna FROM tabla WHERE clave=?`
sobre una copia -- si cualquier celda editable (de cualquier columna, hoy o
en el futuro) deja de mostrar lo que su propia metadata dice que edita, el
test lo señala con la fila y la columna exactas.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QTableWidget

from data.ManejoDatos.load import mostrar_db_mensualBraqui, mostrar_db_linealidad
from _bd_referencia import BD_REBUILD_21_09


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _PantallaFalsa:
    """Lo único que `mostrar_db_mensualBraqui`/`mostrar_db_linealidad`
    necesitan de `self`: una `QTableWidget`. Los botones de las celdas
    "btn_*" capturan `self.mostrar_tabla_*` en un lambda sin resolverlo
    hasta que se hace clic -- no hace falta que existan para construir la
    tabla."""
    def __init__(self):
        self.table = QTableWidget()


def _celdas_con_metadata(table):
    """(fila, columna, clave, (tabla, columna_bd), texto_mostrado) de
    TODA celda que lleve las dos metadatas -- sin lista escrita a mano."""
    celdas = []
    for r in range(table.rowCount()):
        for c in range(table.columnCount()):
            item = table.item(r, c)
            if item is None:
                continue
            meta = item.data(Qt.UserRole + 1)
            clave = item.data(Qt.UserRole)
            if meta is None or clave is None:
                continue
            celdas.append((r, c, clave, meta, item.text()))
    return celdas


def _valor_real(con, tabla, columna, clave_columna, clave_valor):
    fila = con.execute(
        f"SELECT {columna} FROM {tabla} WHERE {clave_columna} = ?",
        (clave_valor,)).fetchone()
    assert fila is not None, (
        f"la celda apunta a {tabla}.{columna} con {clave_columna}="
        f"{clave_valor!r}, que ya no existe en la copia")
    return fila[0]


@pytest.fixture
def copia_sqlite(tmp_path):
    if not BD_REBUILD_21_09.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_21_09.name}")
    import shutil
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    return str(copia)


# ---------------------------------------------------------------------------
# mostrar_db_mensualBraqui -- clave de fila: TipoCalibracion.id == ref de
# ResultadosActividad/SistemaMedicion/CondicionesMedicion (EB6).
# ---------------------------------------------------------------------------

def test_mensual_braqui_toda_celda_editable_muestra_lo_que_la_bd_tiene(app, monkeypatch, copia_sqlite):
    import data.ManejoDatos.conection as conection_mod
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia_sqlite)
    conection_mod.Conexion._instance = None

    pantalla = _PantallaFalsa()
    mostrar_db_mensualBraqui(pantalla)

    assert pantalla.table.rowCount() > 0, "compuerta: la copia debe traer filas reales"

    con = sqlite3.connect(copia_sqlite)
    celdas = _celdas_con_metadata(pantalla.table)
    assert celdas, "compuerta: debe haber al menos una celda con metadata"

    desajustes = []
    for r, c, ref, (tabla, columna), texto in celdas:
        esperado = str(_valor_real(con, tabla, columna, "ref", ref))
        if texto != esperado:
            encabezado = pantalla.table.horizontalHeaderItem(c).text()
            desajustes.append((r, c, encabezado, tabla, columna, texto, esperado))
    con.close()

    assert not desajustes, (
        "celdas que NO muestran lo que su propia metadata dice que editan "
        "(fila, columna, encabezado, tabla, columna_bd, mostrado, "
        f"esperado_de_la_bd): {desajustes}")

    conection_mod.Conexion._instance = None


def test_mensual_braqui_la_columna_ktp_no_es_editable(app, monkeypatch, copia_sqlite):
    """Compuerta específica del defecto medido: "Ktp" (índice 26 de
    `headers`) no debe llevar metadata -- si la volviera a llevar, sería
    la regresión exacta que W.1 cerró (col_mapeo otra vez corrido)."""
    import data.ManejoDatos.conection as conection_mod
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia_sqlite)
    conection_mod.Conexion._instance = None

    pantalla = _PantallaFalsa()
    mostrar_db_mensualBraqui(pantalla)

    headers = [pantalla.table.horizontalHeaderItem(c).text()
               for c in range(pantalla.table.columnCount())]
    col_ktp = headers.index("Ktp")
    col_monitor = headers.index("Act. Monitor")

    for r in range(pantalla.table.rowCount()):
        item_ktp = pantalla.table.item(r, col_ktp)
        item_monitor = pantalla.table.item(r, col_monitor)
        if item_ktp is not None:
            assert item_ktp.data(Qt.UserRole + 1) is None, (
                f"fila {r}: 'Ktp' sigue llevando metadata de edición")
        if item_monitor is not None:
            assert item_monitor.data(Qt.UserRole + 1) == ("ResultadosActividad", "actividad_monitor"), (
                f"fila {r}: 'Act. Monitor' debería ser la celda editable")

    conection_mod.Conexion._instance = None


# ---------------------------------------------------------------------------
# mostrar_db_linealidad -- clave de fila: LinealidadBraquiterapia.id.
# ---------------------------------------------------------------------------

def test_linealidad_toda_celda_editable_muestra_lo_que_la_bd_tiene(app, monkeypatch, copia_sqlite):
    import data.ManejoDatos.conection as conection_mod
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia_sqlite)
    conection_mod.Conexion._instance = None

    pantalla = _PantallaFalsa()
    mostrar_db_linealidad(pantalla)

    assert pantalla.table.rowCount() > 0, "compuerta: la copia debe traer filas reales"

    con = sqlite3.connect(copia_sqlite)
    celdas = _celdas_con_metadata(pantalla.table)
    assert celdas, "compuerta: debe haber al menos una celda con metadata"

    desajustes = []
    for r, c, id_pk, (tabla, columna), texto in celdas:
        esperado = str(_valor_real(con, tabla, columna, "id", id_pk))
        if texto != esperado:
            encabezado = pantalla.table.horizontalHeaderItem(c).text()
            desajustes.append((r, c, encabezado, tabla, columna, texto, esperado))
    con.close()

    assert not desajustes, (
        "celdas que NO muestran lo que su propia metadata dice que editan "
        "(fila, columna, encabezado, tabla, columna_bd, mostrado, "
        f"esperado_de_la_bd): {desajustes}")

    conection_mod.Conexion._instance = None


def test_linealidad_usuario_y_fecha_no_estan_cruzados(app, monkeypatch, copia_sqlite):
    """Compuerta específica del defecto medido: la columna "Usuario" trae
    el nombre del físico (no una fecha), y "Fecha" trae la fecha (no un
    nombre) -- verificado contra la propia BD, fila por fila."""
    import data.ManejoDatos.conection as conection_mod
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia_sqlite)
    conection_mod.Conexion._instance = None

    pantalla = _PantallaFalsa()
    mostrar_db_linealidad(pantalla)

    con = sqlite3.connect(copia_sqlite)
    filas_bd = con.execute(
        "SELECT id, user, fecha FROM LinealidadBraquiterapia "
        "WHERE (activo IS NULL OR activo = 1) ORDER BY id DESC").fetchall()
    con.close()

    headers = [pantalla.table.horizontalHeaderItem(c).text()
               for c in range(pantalla.table.columnCount())]
    col_usuario = headers.index("Usuario")
    col_fecha = headers.index("Fecha")

    assert pantalla.table.rowCount() == len(filas_bd)
    for r, (id_pk, usuario_bd, fecha_bd) in enumerate(filas_bd):
        assert pantalla.table.item(r, col_usuario).text() == str(usuario_bd), (
            f"fila {r} (id={id_pk}): 'Usuario' no muestra el usuario")
        assert pantalla.table.item(r, col_fecha).text() == str(fecha_bd), (
            f"fila {r} (id={id_pk}): 'Fecha' no muestra la fecha")

    conection_mod.Conexion._instance = None
