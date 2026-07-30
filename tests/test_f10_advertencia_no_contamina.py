"""F10 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.5/§9): la advertencia de vencido
nunca toca el dato almacenado.

Antes de F10 (H2.6/K-fix.4), el combo del mensual escribía el marcador de
vencido DIRECTO en el texto del item ("⚠️ {serie} (VENCIDO)"), y el guardado
leía `currentText()` -- así quedaron 13 filas reales de `equipos_medicion`
con `serie='⚠️151251'` (electrómetro TW41047). F9 ya cierra la causa de raíz
(el guardado resuelve por `currentData()`/id, nunca por texto); este tripwire
fija el contrato para que la contaminación no reaparezca por otra vía.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QLineEdit, QWidget
from PyQt5.QtCore import QDate

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)

CARACTERES_DECORACION = ("⚠️", "✓", "✗", "✅", "—", "(vencida)", "(VENCIDO)")


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


def _insertar_equipo(ruta_bd, eq_id, **campos):
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


def _insertar_control(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Clinac 600", "Mensual", "06/2026"))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _instancia_pelada(fecha_control, ref):
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(fecha_control)
    obj.ref = ref

    obj.commenu = []
    for _ in range(3):
        combo_modelo = QComboBox()
        combo_modelo.addItems(["Seleccionar...", "N30013"])
        combo_serie = QComboBox()
        lineedit_calib = QLineEdit()
        obj.commenu.extend([combo_modelo, combo_serie, lineedit_calib])
        combo_modelo.currentTextChanged.connect(obj.setEquipoSeleccionado)
        combo_serie.currentTextChanged.connect(obj.setCalibracion)
    return obj


class TestGuardadoConEquipoVencidoNoContamina:
    def test_ninguna_columna_de_equipos_medicion_tiene_decoracion(self, app, bd_temporal):
        _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.0545,
                         fecha_calibr="05/02/2020",  # vencida hace años
                         activo=1, vigente=1)
        ref = _insertar_control(bd_temporal)

        # Control de HOY: la calibración de 2020 (2 años de vigencia) sale
        # vencida -- justo el caso que contaminaba antes de F9/F10.
        obj = _instancia_pelada(QDate(2026, 7, 30), ref)
        obj.commenu[0].setCurrentText("N30013")

        combo_serie = obj.commenu[1]
        idx = next(i for i in range(combo_serie.count())
                  if combo_serie.itemData(i) == 1)
        combo_serie.setCurrentIndex(idx)
        assert "(vencida)" in combo_serie.currentText(), (
            "precondición: el item elegido debe estar marcado vencido")

        datos = ["N30013", combo_serie.currentText(), obj.commenu[2].text(),
                "", "", "", "", "", ""]
        obj.subirtodo_modificado(datos)

        con = sqlite3.connect(bd_temporal)
        try:
            fila = con.execute(
                "SELECT tipo_camara, equip_type, model, serie, fecha_calibr "
                "FROM equipos_medicion WHERE ref=?", (ref,)).fetchone()
        finally:
            con.close()

        assert fila is not None
        for valor in fila:
            if valor is None:
                continue
            for marcador in CARACTERES_DECORACION:
                assert marcador not in str(valor), (
                    f"columna contaminada con {marcador!r}: {valor!r}")
        assert fila[3] == "2123"  # serie limpia, exacta


class TestLimpiezaDefensivaYaNoHaceFalta:
    """F10 punto 2: la limpieza defensiva de ⚠️/(VENCIDO) que existía en
    `setCalibracion` (H2.6/K-fix.4) se retiró en F9 -- ya no queda ninguna
    ruta en el archivo que resuelva la calibración por texto de combo, así
    que no hay nada que limpiar. Fija por código que no reaparezca."""

    def test_seiscientos_mensual_no_contiene_limpieza_de_simbolos(self):
        import inspect
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mod
        fuente = inspect.getsource(mod)
        assert "⚠️" not in fuente
        assert "VENCIDO" not in fuente
