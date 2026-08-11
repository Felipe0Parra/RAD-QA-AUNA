"""H1 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.4): el botón
"Agregar" (btn_add) del diario del Halcyon nunca estuvo conectado (git log
-S"btn_add" confirma un solo commit, el estado virgen). Este archivo cubre
el protocolo de verificación completo de §3.4:

1. Rojo-antes-que-verde real (pulsar btn_add guarda una fila nueva).
2. Idempotencia: dos pulsaciones para la misma fecha -> una sola fila, una
   sola fila de auditoría, aviso visible la segunda vez.
3. La fila de auditoría lleva el usuario correcto.
4. RADQA_HALCYON_MPC (J3) para no depender del share del hospital.

**P1 (§8 del plan)**: el archivo original desapareció con un fake
(`_HalcyonDiarioFalso` con un stub contador de `importar_fecha_seleccionada`)
que SOMBREABA el método real bajo prueba -- `button_click()` conectaba el
stub, así que ninguna prueba de guardado ejecutaba código de producción.
Aquí se separan deliberadamente dos roles:

- `_HalcyonEspia`: fake con un stub CONTADOR de `agregar_fecha_seleccionada`
  -- solo para verificar el CABLEADO (que btn_add.clicked llega a ese
  método), nunca para verificar qué hace ese método.
- `_construir_halcyon_real`: objeto que enlaza los métodos REALES de
  `PruebaDiariaHc` (via `types.MethodType`) -- usado en todas las pruebas de
  guardado/idempotencia/auditoría, para que ejecuten producción de verdad.

Un tripwire (`test_no_esta_sombreado_por_un_stub`) deja explícito que el
objeto "real" de verdad resuelve al método de la clase, no a un stub -- si
alguien reintroduce un `def agregar_fecha_seleccionada(self): pass` en el
objeto "real" por error, este test lo delata antes que ningún otro.

H3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §H3), sesión posterior:
`importar_fecha_seleccionada` -- el método único que H1 conectó a la vez a
`dateChanged` Y a `btn_add`, y que por eso GUARDABA con solo cambiar la
fecha -- se partió en dos: `previsualizar_fecha_seleccionada` (dateChanged,
cero escrituras) y `agregar_fecha_seleccionada` (btn_add, el único que
guarda). Este archivo se actualizó para seguir probando btn_add/guardado
contra el método nuevo; `test_h3_previsualizar_no_escribe.py` cubre la mitad
que antes no existía como comportamiento separado (que elegir la fecha
NO guarde).
"""
import os
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
    """BD real (DDL + migraciones vía Conexion()) con un usuario sembrado
    -- `halcyon.user_id` tiene FK a users(fullname) con foreign_keys=ON
    (W2), así que el INSERT de createDB fallaría en silencio sin esto.

    `monkeypatch.chdir` aísla el `infoWidgets.csv` que addInfo escribe con
    ruta relativa (wart preexistente, ya documentado en J2) -- sin esto el
    archivo ensucia la raíz del repo cada vez que corre este test."""
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


HEADER = "Name [Unit], Value, Threshold, Evaluation Result\n"


def _csv_con_20_resultados():
    """20 filas -- createDB inserta POSICIONALMENTE (PRAGMA table_info menos
    'id' y 'activo' = 22 columnas = date + user_id + 20 de medición), así
    que basta con 20 entradas 'resultado' válidas, sin que su nombre/valor
    importe semánticamente (createDB no empareja por nombre de columna)."""
    lineas = [HEADER]
    for i in range(20):
        lineas.append(f"TestGroup/G/S/Metric{i:02d}, {i}, 5, Pass\n")
    return "".join(lineas)


@pytest.fixture
def carpeta_mpc(tmp_path, monkeypatch):
    """J3: RADQA_HALCYON_MPC apunta a una copia sintética -- no depende del
    share \\\\VARIANDB\\... del hospital."""
    base = tmp_path / "mpc"
    base.mkdir()
    monkeypatch.setenv("RADQA_HALCYON_MPC", str(base))

    def _crear(fecha):
        carpeta = base / f"HAL-TRT-SN1161-{fecha}-05-19-31-0000-GeometryCheckTemplate"
        carpeta.mkdir()
        (carpeta / "Results.csv").write_text(_csv_con_20_resultados(), encoding="utf-8")
        return str(carpeta)

    return _crear


def _mockear_mensajes(monkeypatch):
    avisos = {"information": [], "warning": [], "critical": []}
    for nombre in avisos:
        monkeypatch.setattr(
            halcyon_data_mod.QMessageBox, nombre,
            staticmethod(lambda *a, tipo=nombre, **k: avisos[tipo].append(a[1:])))
    return avisos


class _HalcyonEspia(QWidget):
    """Solo para el cableado -- el stub CONTADOR nunca debe usarse para
    verificar qué hace agregar_fecha_seleccionada, solo que se invoca."""

    def __init__(self):
        super().__init__()
        self.contador = 0
        self.btn_submit = QPushButton()
        self.mach_name2 = QLineEdit("Halcyon")
        self.code_1 = QLineEdit("HAL1161")
        self.date_box = QDateEdit()
        self.diccionario_invertido = {}
        self.menu_graficar = QComboBox()
        self.btn_delete = QPushButton()
        self.graficar = []
        self.limit1 = QDateEdit()
        self.limit2 = QDateEdit()
        self.search_bar = QLineEdit()
        self.edit_table = QPushButton("Editar")
        self.accept_edit = QPushButton()
        self.cancel_edit = QPushButton()
        self.btn_add = QPushButton()

    def mostrar_submenu(self):
        pass

    def filtrarTabla(self):
        pass

    def agregar_fecha_seleccionada(self):
        self.contador += 1


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _construir_halcyon_real():
    """Objeto QWidget con los métodos REALES de PruebaDiariaHc enlazados --
    ejecuta producción de verdad (agregar_halcyon -> createDB -> auditoría),
    a diferencia de _HalcyonEspia."""
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


def test_no_esta_sombreado_por_un_stub(app):
    """P1 (§8 del plan): tripwire -- si algo vuelve a definir un
    agregar_fecha_seleccionada propio sobre el objeto 'real', este test lo
    delata antes que cualquier prueba de guardado."""
    obj = _construir_halcyon_real()
    assert obj.agregar_fecha_seleccionada.__func__ is \
        PruebaDiariaHc.agregar_fecha_seleccionada


class TestCableadoBotonAgregar:
    """Verifica SOLO que btn_add.clicked llega a agregar_fecha_seleccionada
    -- con el fake espía, sin ejecutar producción real."""

    def test_click_dispara_agregar_fecha_seleccionada(self, app):
        espia = _HalcyonEspia()
        PruebaDiariaHc.button_click(espia)

        espia.btn_add.click()

        assert espia.contador == 1


class TestGuardadoReal:
    """Rojo-antes-que-verde real: pulsar btn_add guarda una fila nueva en
    `halcyon`, usando los métodos REALES de PruebaDiariaHc."""

    def test_click_guarda_fila_nueva_en_halcyon(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-01")
        obj = _construir_halcyon_real()
        obj.button_click()

        obj.btn_add.click()

        con = sqlite3.connect(bd_temporal)
        filas = con.execute(
            "SELECT date, user_id FROM halcyon WHERE date=?",
            ("2026-07-01",)).fetchall()
        con.close()
        assert filas == [("2026-07-01", "Físico de Prueba")]


class TestIdempotenciaYAviso:

    def test_dos_pulsaciones_una_sola_fila_una_sola_auditoria(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        avisos = _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-03")
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 3))
        obj.button_click()

        obj.btn_add.click()
        obj.btn_add.click()

        con = sqlite3.connect(bd_temporal)
        n_filas = con.execute(
            "SELECT COUNT(*) FROM halcyon WHERE date=?",
            ("2026-07-03",)).fetchone()[0]
        n_auditoria = con.execute(
            "SELECT COUNT(*) FROM audit_log WHERE accion='guardar' AND tabla='halcyon' AND ref=?",
            ("2026-07-03",)).fetchone()[0]
        con.close()
        assert n_filas == 1
        assert n_auditoria == 1

    def test_segunda_pulsacion_avisa_fecha_ya_importada(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        avisos = _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-04")
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 4))
        obj.button_click()

        obj.btn_add.click()
        assert not any("ya está importada" in a[1] for a in avisos["information"])
        obj.btn_add.click()

        assert any("ya está importada" in a[1] for a in avisos["information"])


class TestAuditoriaConUsuarioCorrecto:

    def test_fila_de_auditoria_lleva_el_usuario_correcto(
            self, app, bd_temporal, carpeta_mpc, monkeypatch):
        _mockear_mensajes(monkeypatch)
        carpeta_mpc("2026-07-05")
        obj = _construir_halcyon_real()
        obj.date_box.setDate(QDate(2026, 7, 5))
        obj.button_click()

        obj.btn_add.click()

        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT usuario, accion, tabla, ref FROM audit_log "
            "WHERE accion='guardar' AND tabla='halcyon' AND ref=?",
            ("2026-07-05",)).fetchone()
        con.close()
        assert fila == ("Físico de Prueba", "guardar", "halcyon", "2026-07-05")
