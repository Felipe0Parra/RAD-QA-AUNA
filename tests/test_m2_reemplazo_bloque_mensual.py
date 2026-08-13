"""M2 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §M2): el guardado mensual
reemplaza el bloque en vez de acumularlo, en las tres tablas de §2.1
(`control_cunas`, `control_conos`, `equipos_medicion`).

Contrato único (§3 del plan): guardar N veces deja exactamente UN bloque
activo por ref -- las filas anteriores quedan `activo = 0` (nunca DELETE
físico, D6/DA-03), y cambiar un valor y volver a guardar deja activo el
valor NUEVO (el caso real de los conos 115-119 del rebuild).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX


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
    _nombre = "Físico de Prueba"


class _ComboFalso:
    def __init__(self, texto="Funciona"):
        self._texto = texto

    def currentText(self):
        return self._texto


def _insertar_control(ruta_bd, equipo="Clinac 600", control="Mensual", fecha="06/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _mensual_pelado(clase=PruebaMensual600, esIX=False):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    if esIX:
        obj.esIX = True
    return obj


def _combos_cunas(valor="Funciona"):
    return {ang: {k: _ComboFalso(valor) for k in ("in", "out", "right", "left")}
            for ang in (15, 30, 45, 60)}


def _filas_cunas(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    filas = con.execute(
        "SELECT angulo, in_val, out_val, right_val, left_val, activo "
        "FROM control_cunas WHERE ref = ? ORDER BY id", (ref,)).fetchall()
    con.close()
    return filas


class TestReemplazoBloqueCunas:
    def test_guardar_3_veces_deja_un_bloque_activo_con_el_valor_de_la_3a(
            self, app, bd_temporal, monkeypatch):
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref

        obj.subir_control_cunas(_combos_cunas("Funciona"))
        obj.subir_control_cunas(_combos_cunas("Funciona"))
        obj.subir_control_cunas(_combos_cunas("No funciona"))  # el valor nuevo

        filas = _filas_cunas(bd_temporal, ref)
        assert len(filas) == 12, "3 guardados x 4 ángulos = 12 filas (historial, nunca se borra)"

        activas = [f for f in filas if f[5] == 1]
        anuladas = [f for f in filas if f[5] == 0]
        assert len(activas) == 4, "un solo bloque activo, sin importar cuántos guardados"
        assert len(anuladas) == 8
        assert all(f[1:5] == (0, 0, 0, 0) for f in activas), (
            "el bloque activo trae el valor de la 3a llamada (No funciona = 0)")
        assert all(f[1:5] == (1, 1, 1, 1) for f in anuladas), (
            "los bloques anulados conservan el valor con el que se guardaron")

    def test_no_usa_insert_or_replace_ni_choca_por_falta_de_indice_unico(
            self, app, bd_temporal, monkeypatch):
        """§2.1: INSERT OR REPLACE nunca reemplazaba porque la tabla no
        tiene índice UNIQUE -- causa raíz de la duplicación. M2 lo retira
        sin sustituirlo por un UNIQUE(ref, angulo) (chocaría con el
        soft-delete, ver §M2 del plan); el reemplazo es explícito
        (anular + insertar), no depende de ningún índice."""
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
        monkeypatch.setattr(mensual_mod.QMessageBox, "information",
                            staticmethod(lambda *a, **k: None))
        con = sqlite3.connect(bd_temporal)
        indices = con.execute("PRAGMA index_list(control_cunas)").fetchall()
        con.close()
        assert indices == []

        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref
        obj.subir_control_cunas(_combos_cunas())
        obj.subir_control_cunas(_combos_cunas())

        filas = _filas_cunas(bd_temporal, ref)
        assert len([f for f in filas if f[5] == 1]) == 4


class TestReemplazoBloqueConos:
    def _botones(self, valor):
        botones = {}
        for medida in ("6x6", "10x10", "15x15", "20x20", "25x25"):
            fun, nofun = QPushButton(), QPushButton()
            fun.setCheckable(True)
            nofun.setCheckable(True)
            if valor == 1:
                fun.setChecked(True)
            elif valor == 0:
                nofun.setChecked(True)
            botones[medida] = (fun, nofun)
        return botones

    def _instancia(self, bd_temporal, ref, valor):
        obj = _mensual_pelado(clase=PruebaMensualIX, esIX=True)
        obj.ref = ref
        botones = self._botones(valor)
        obj.btn_6_fun, obj.btn_6_nofun = botones["6x6"]
        obj.btn_10_fun, obj.btn_10_nofun = botones["10x10"]
        obj.btn_15_fun, obj.btn_15_nofun = botones["15x15"]
        obj.btn_20_fun, obj.btn_20_nofun = botones["20x20"]
        obj.btn_25_fun, obj.btn_25_nofun = botones["25x25"]
        return obj

    def _filas(self, ruta_bd, ref):
        con = sqlite3.connect(ruta_bd)
        filas = con.execute(
            "SELECT medida, valor, activo FROM control_conos WHERE ref = ? ORDER BY id",
            (ref,)).fetchall()
        con.close()
        return filas

    def test_guardar_3_veces_deja_un_bloque_activo_con_el_valor_de_la_3a(
            self, app, bd_temporal):
        ref = _insertar_control(bd_temporal, equipo="Clinac ix")
        self._instancia(bd_temporal, ref, 1).guardar_control_conos()
        self._instancia(bd_temporal, ref, 1).guardar_control_conos()
        self._instancia(bd_temporal, ref, 0).guardar_control_conos()  # el valor nuevo

        filas = self._filas(bd_temporal, ref)
        assert len(filas) == 15, "3 guardados x 5 medidas = 15 filas"

        activas = [f for f in filas if f[2] == 1]
        anuladas = [f for f in filas if f[2] == 0]
        assert len(activas) == 5
        assert len(anuladas) == 10
        assert all(f[1] == 0 for f in activas), "el bloque activo trae el valor de la 3a llamada"

    def test_guardado_sin_ninguna_medida_marcada_no_anula_el_bloque_activo(
            self, app, bd_temporal, monkeypatch):
        """T3 (PLAN_CONOS_MENSUAL_12-08.md §4-T3, DA-37) reforzó esta ruta:
        ya no es solo defensiva -- guardar con conos sin marcar está
        explícitamente bloqueado (los 5 o ninguno), y el aviso nombra
        cuáles faltan. El resultado que este test ya fijaba (nada nuevo se
        inserta, el bloque activo original sigue activo) sigue siendo
        válido porque T3 refuerza ese contrato, no lo cambia."""
        avisos = []
        monkeypatch.setattr(
            QMessageBox, "warning",
            staticmethod(lambda *a, **k: avisos.append(a[-1]) or QMessageBox.Ok))

        ref = _insertar_control(bd_temporal, equipo="Clinac ix")
        self._instancia(bd_temporal, ref, 1).guardar_control_conos()
        assert len([f for f in self._filas(bd_temporal, ref) if f[2] == 1]) == 5

        obj_vacio = _mensual_pelado(clase=PruebaMensualIX, esIX=True)
        obj_vacio.ref = ref
        botones = self._botones(None)
        obj_vacio.btn_6_fun, obj_vacio.btn_6_nofun = botones["6x6"]
        obj_vacio.btn_10_fun, obj_vacio.btn_10_nofun = botones["10x10"]
        obj_vacio.btn_15_fun, obj_vacio.btn_15_nofun = botones["15x15"]
        obj_vacio.btn_20_fun, obj_vacio.btn_20_nofun = botones["20x20"]
        obj_vacio.btn_25_fun, obj_vacio.btn_25_nofun = botones["25x25"]
        resultado = obj_vacio.guardar_control_conos()

        assert resultado is False, "T3/DA-37: bloqueado, no se guardó nada"
        assert len(avisos) == 1
        for medida in ("6x6", "10x10", "15x15", "20x20", "25x25"):
            assert medida in avisos[0], f"el aviso no nombra {medida}"

        filas = self._filas(bd_temporal, ref)
        assert len(filas) == 5, "nada nuevo que insertar -- nada se toca"
        assert all(f[2] == 1 for f in filas), "el bloque activo original sigue activo"


class TestReemplazoBloqueEquiposMedicion:
    def _poblar_equipo(self, ruta_bd, id_, serie, calibr_fact):
        con = sqlite3.connect(ruta_bd)
        con.execute(
            "INSERT INTO equipos (id, equip_type, model, serie, calibr_fact, "
            "fecha_calibr, activo, vigente) VALUES (?, 'Cámara de ionización', "
            "'N30013', ?, ?, '05/02/2024', 1, 1)", (id_, serie, calibr_fact))
        con.commit()
        con.close()

    def test_cambiar_el_electrometro_y_volver_a_guardar_deja_activo_el_nuevo(
            self, app, bd_temporal):
        """El caso real de equipos_medicion ref=44 ids 282-284 del rebuild:
        cambió el electrómetro entre dos guardados y el guardado viejo
        AÑADÍA en vez de reemplazar."""
        self._poblar_equipo(bd_temporal, 1, "1822", 0.3034)
        self._poblar_equipo(bd_temporal, 2, "2343", 1.0)
        ref = _insertar_control(bd_temporal)
        obj = _mensual_pelado()
        obj.ref = ref
        obj.commenu = [None, None, None] * 3
        import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod

        class _SerieWidget:
            def __init__(self, equipo_id):
                self._id = equipo_id

            def currentData(self):
                return self._id

        obj.commenu[1] = _SerieWidget(1)
        datos_v1 = ["N30013", "1822 — calibrado 05/02/2024", "0.3034",
                    "", "", "", "", "", ""]
        obj.subirtodo_modificado(datos_v1)

        obj.commenu[1] = _SerieWidget(2)
        datos_v2 = ["N30013", "2343 — calibrado 05/02/2024", "1.0",
                    "", "", "", "", "", ""]
        obj.subirtodo_modificado(datos_v2)

        con = sqlite3.connect(bd_temporal)
        filas = con.execute(
            "SELECT serie, activo FROM equipos_medicion WHERE ref = ? ORDER BY id",
            (ref,)).fetchall()
        con.close()

        assert filas == [("1822", 0), ("2343", 1)], (
            "el electrómetro viejo queda anulado (historial), el nuevo activo -- "
            "nunca los dos activos a la vez")
