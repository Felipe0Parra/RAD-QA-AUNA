"""H3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §H3): en el diario del
Halcyon, elegir la fecha (dateChanged) SOLO previsualiza -- localiza la
carpeta MPC, lee el Results.csv y llena los campos, pero CERO escrituras
en la BD. Antes de esta tarea, `addInfo` estaba conectada A LA VEZ a
`dateChanged` y al botón "Agregar", y hacía las tres cosas (localizar, leer,
escribir) de una sola pasada -- para cuando el físico pulsaba "Agregar", el
registro ya estaba guardado (§2.5 del plan).

`previsualizar_fecha_seleccionada`/`previsualizar_halcyon` y
`agregar_fecha_seleccionada`/`agregar_halcyon` reemplazan ese único método
(ver test_h1_boton_agregar_halcyon.py para el guardado real vía "Agregar",
que no cambió de comportamiento -- solo de nombre).

Riesgo explícito del plan: "Agregar" sin una carpeta MPC para la fecha
elegida no debe escribir nada, y debe decirlo (no fallar en silencio).
"""
import os
import shutil
import sqlite3
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QLineEdit, QPushButton,
    QTableWidget, QWidget)

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.obtenerDatosHalcyon as halcyon_data_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.halcyon import PruebaDiariaHc
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    """Misma disciplina que test_h1_boton_agregar_halcyon.py: BD real (DDL +
    migraciones) con un usuario sembrado, cwd aislado para infoWidgets.csv."""
    monkeypatch.chdir(tmp_path)
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES ('fisico_prueba', 'x', 'Físico de Prueba', 1, '1', 'Físico Médico', 'fisico')")
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _contar(bd, sql, *params):
    """Cuenta filas sobre una COPIA de la BD, no sobre el archivo vivo.

    Por qué no un `sqlite3.connect(bd)` normal (diagnosticado el 2026-08-11,
    al escribir este archivo): en ESTE proceso conviven DOS copias distintas
    de la librería SQLite -- la del módulo `sqlite3` de Python (libsqlite3
    del sistema, 3.45.1) y la que Qt enlaza estáticamente dentro de su
    driver `libqsqlite.so` (3.49.1). Todo el código de producción escribe
    por la de Python, pero `load_table`, que corre al final tanto de
    previsualizar como de agregar, lee por la de Qt.

    En modo WAL (H2.5, `aplicar_pragmas_conexion`) las conexiones se
    coordinan a través del índice-WAL del archivo "-shm" y de cerrojos
    POSIX, y en Unix esos cerrojos NUNCA entran en conflicto dentro de un
    mismo proceso: cada copia de la librería lleva su propia lista privada
    de conexiones abiertas y no ve las de la otra. Así, la copia de Qt
    concluye que es la última conexión viva, hace checkpoint y BORRA el
    "-wal"/"-shm" mientras la de Python todavía tiene conexiones abiertas
    apuntando a ese índice. Desde ese momento, CUALQUIER conexión nueva de
    `sqlite3` en este proceso revienta con "disk I/O error"
    (SQLITE_IOERR_SHORT_READ, busca marcos de un WAL que ya no existe) o,
    peor, contesta datos rancios sin avisar.

    No es corrupción ni pérdida de datos: el archivo en disco queda intacto
    -- leído desde OTRO proceso, `PRAGMA integrity_check` da 'ok' y los
    datos son los correctos. El daño es puramente el estado en memoria de
    la librería de Python. Por eso se lee una copia en otra ruta (otro
    inodo => índice-WAL limpio), que es exactamente lo que vería la app al
    reabrirse, sin desactivar WAL en producción (decisión de arquitectura
    ya tomada en H2.5/HI-3, ajena a H3).

    Tampoco afecta a producción, que corre en Windows: el VFS win32 usa
    cerrojos OBLIGATORIOS por handle (LockFileEx), que sí entran en
    conflicto entre copias de la librería dentro del mismo proceso, y
    además no deja borrar un archivo que otro handle tiene abierto.
    """
    copia = bd + ".copia-verificacion"
    for sobrante in (copia, copia + "-wal", copia + "-shm"):
        if os.path.exists(sobrante):
            os.remove(sobrante)
    shutil.copy(bd, copia)
    if os.path.exists(bd + "-wal"):
        # Un commit reciente puede vivir solo en el "-wal": se copia el par
        # completo (procedimiento documentado por SQLite), nunca el "-shm",
        # que SQLite reconstruye solo.
        shutil.copy(bd + "-wal", copia + "-wal")
    con = sqlite3.connect(copia)
    try:
        return con.execute(sql, params).fetchone()[0]
    finally:
        con.close()


HEADER = "Name [Unit], Value, Threshold, Evaluation Result\n"


def _csv_con_20_resultados():
    lineas = [HEADER]
    for i in range(20):
        lineas.append(f"TestGroup/G/S/Metric{i:02d}, {i}, 5, Pass\n")
    return "".join(lineas)


@pytest.fixture
def carpeta_mpc(tmp_path, monkeypatch):
    base = tmp_path / "mpc"
    base.mkdir()
    monkeypatch.setenv("RADQA_HALCYON_MPC", str(base))

    def _crear(fecha):
        carpeta = base / f"HAL-TRT-SN1161-{fecha}-05-19-31-0000-GeometryCheckTemplate"
        carpeta.mkdir()
        (carpeta / "Results.csv").write_text(_csv_con_20_resultados(), encoding="utf-8")
        return str(carpeta)

    return _crear


@pytest.fixture
def carpeta_mpc_vacia(tmp_path, monkeypatch):
    """RADQA_HALCYON_MPC apunta a una carpeta que existe pero sin NINGUNA
    subcarpeta para la fecha elegida -- el caso "sin carpeta" del riesgo."""
    base = tmp_path / "mpc_vacia"
    base.mkdir()
    monkeypatch.setenv("RADQA_HALCYON_MPC", str(base))
    return base


def _mockear_mensajes(monkeypatch):
    avisos = {"information": [], "warning": [], "critical": []}
    for nombre in avisos:
        monkeypatch.setattr(
            halcyon_data_mod.QMessageBox, nombre,
            staticmethod(lambda *a, tipo=nombre, **k: avisos[tipo].append(a[1:])))
    return avisos


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _construir_halcyon_real():
    """Mismo helper que test_h1_boton_agregar_halcyon.py -- objeto con los
    métodos REALES de PruebaDiariaHc enlazados."""
    obj = QWidget()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 7, 1))
    obj.user_id = _UsuarioFalso()
    obj.table = QTableWidget()
    obj.btn_add = QPushButton()
    obj.btn_submit = QPushButton()
    obj.mach_name2 = QLineEdit("Halcyon")
    obj.code_1 = QLineEdit("HAL1161")
    obj.diccionario_invertido = {}
    obj.menu_graficar = QComboBox()
    obj.btn_delete = QPushButton()
    obj.graficar = []
    obj.limit1 = QDateEdit()
    obj.limit2 = QDateEdit()
    obj.search_bar = QLineEdit()
    obj.edit_table = QPushButton("Editar")
    obj.accept_edit = QPushButton()
    obj.cancel_edit = QPushButton()

    obj.agregar_fecha_seleccionada = types.MethodType(
        PruebaDiariaHc.agregar_fecha_seleccionada, obj)
    obj.previsualizar_fecha_seleccionada = types.MethodType(
        PruebaDiariaHc.previsualizar_fecha_seleccionada, obj)
    obj.convert_date_to_str = types.MethodType(
        PruebaDiariaHc.convert_date_to_str, obj)
    obj.button_click = types.MethodType(PruebaDiariaHc.button_click, obj)
    obj.update_lineedit_blocks = types.MethodType(
        PruebaDiariaHc.update_lineedit_blocks, obj)
    obj.opeenDatabase = types.MethodType(PruebaBasico.opeenDatabase, obj)
    obj.mostrar_submenu = lambda *a, **k: None
    obj.filtrarTabla = lambda *a, **k: None
    return obj


class TestPrevisualizarNoEscribe:
    def test_cambiar_la_fecha_no_escribe_en_halcyon(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        """El caso central de H3: antes, dateChanged guardaba (compartía
        addInfo con "Agregar"). Ahora, con una carpeta MPC completa
        disponible, elegir la fecha NO debe dejar ninguna fila."""
        _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-10")
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 10))

        obj.convert_date_to_str()

        n = _contar(
            bd_temporal, "SELECT COUNT(*) FROM halcyon WHERE date=?", "2026-07-10")
        assert n == 0

    def test_cambiar_la_fecha_no_audita_nada(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-11")
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 11))

        obj.convert_date_to_str()

        n = _contar(bd_temporal, "SELECT COUNT(*) FROM audit_log WHERE tabla='halcyon'")
        assert n == 0

    def test_cambiar_la_fecha_si_llena_los_campos(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        """"Cero escrituras" no significa "no hace nada" -- localizar, leer
        y llenar los campos sigue siendo el trabajo de dateChanged."""
        _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-12")
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 12))

        llamadas = []
        obj.update_lineedit_blocks = lambda df: llamadas.append(df)

        obj.convert_date_to_str()

        assert len(llamadas) == 1
        assert not llamadas[0].empty

    def test_agregar_despues_de_previsualizar_si_guarda(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        """Las dos mitades encajan: previsualizar (dateChanged) no guarda,
        pero "Agregar" sobre la misma fecha sigue guardando -- el flujo
        completo de un uso real."""
        _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-13")
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 13))

        obj.convert_date_to_str()  # previsualiza, no guarda
        obj.agregar_fecha_seleccionada()  # ahora sí guarda

        n = _contar(
            bd_temporal, "SELECT COUNT(*) FROM halcyon WHERE date=?", "2026-07-13")
        assert n == 1


class TestAgregarSinCarpetaNoEscribeYLoDice:
    """Riesgo explícito del plan: "Agregar" sin haber seleccionado una
    fecha con carpeta MPC no debe escribir nada, y debe avisar -- no fallar
    en silencio."""

    def test_agregar_sin_carpeta_no_escribe_nada(
            self, app, bd_temporal, carpeta_mpc_vacia, monkeypatch):
        avisos = _mockear_mensajes(monkeypatch)
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 14))

        obj.agregar_fecha_seleccionada()

        n = _contar(bd_temporal, "SELECT COUNT(*) FROM halcyon")
        assert n == 0
        assert len(avisos["warning"]) == 1  # "No encontrada" -- lo dice, no calla

    def test_previsualizar_sin_carpeta_tampoco_escribe(
            self, app, bd_temporal, carpeta_mpc_vacia, monkeypatch):
        avisos = _mockear_mensajes(monkeypatch)
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 15))

        obj.convert_date_to_str()

        n = _contar(bd_temporal, "SELECT COUNT(*) FROM halcyon")
        assert n == 0
        assert len(avisos["warning"]) == 1
