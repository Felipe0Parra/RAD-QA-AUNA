"""El colimador del mensual (600, iX y Halcyon) queda con 0°, 90° y 270°, como el formato oficial, y lo guardado se ve en la fila de su ángulo.

- La tabla del formulario tiene 3 filas; el brazo sigue con 4.
- Un control guardado se coloca por su ÁNGULO, no por su posición: la consulta devuelve las filas en el orden del índice (`0°`, `180°`, `270°`, `90°`).
- La fila de 180° de un control viejo no se ve y sigue en la base; «Subir» la deja anulada, no borrada.
- Un ángulo sin guardar queda vacío con su etiqueta, y «Subir» la guarda (en el Halcyon, como número real).
- Las demás tablas se llenan como antes (sin `niveles`); «Ver tabla» también queda en 0°, 90° y 270°.
- Datos reales: la copia del 23-11 (sus tres archivos, a un temporal).
"""
import ast
import gc
import hashlib
import inspect
import os
import shutil
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QCoreApplication, QEvent, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton, QTableWidget, QToolBox, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from services.db_pool import DatabaseManager
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc

import _bd_referencia

RAIZ = Path(__file__).resolve().parent.parent
MODULO = "ui.paginasControles.PruebasMensuales.filas_por_nivel"
SINTETICO = {"0°": "1.1", "90°": "2.2", "180°": "3.3", "270°": "4.4"}
HC_SINTETICO = {0.0: (1.1, 0.1), 90.0: (2.2, 0.2), 180.0: (3.3, 0.3), 270.0: (4.4, 0.4)}
ETIQUETA_HC = {0.0: "0", 90.0: "90", 270.0: "270"}
ORDENES = {
    "como se guardaron": ["0°", "90°", "180°", "270°"],
    "al reves": ["270°", "180°", "90°", "0°"],
    "revuelto": ["90°", "270°", "0°", "180°"],
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fpn():
    """El módulo nuevo; sin él, la prueba cae diciendo que falta."""
    import importlib
    try:
        return importlib.import_module(MODULO)
    except ImportError as error:
        pytest.fail(f"falta el módulo {MODULO}: {error}")


@pytest.fixture
def dialogos(monkeypatch):
    """Trampa 2: ningún modal se abre; los diálogos de «Ver tabla» se capturan."""
    abiertos = []
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QDialog, "exec_", lambda self: abiertos.append(self) or 0)
    return abiertos


def cerrar(widget):
    """Trampa 9: cierra la página y vacía la cola de borrado."""
    widget.hide()
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def bd(app, monkeypatch, tmp_path, dialogos):
    """Una base temporal con el esquema de la app."""
    ruta = str(tmp_path / "aj1.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    Conexion().con.close()
    Conexion._instance = None
    yield ruta
    Conexion._instance = previa


def control(ruta, ref, equipo="Clinac 600"):
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO controles (id, equipo, control, fecha, activo) VALUES (?, ?, 'Mensual', '24/11/2026', 1)", (ref, equipo))
    con.commit()
    con.close()


def sembrar(ruta, tabla, ref, filas):
    """Filas del 600 o del iX: (nivel, consola, equipo)."""
    con = sqlite3.connect(ruta)
    con.executemany(f"INSERT INTO {tabla} (ref, nivel, indicador_luminoso_consola, indicador_luminoso_equipo, activo) VALUES (?, ?, ?, ?, 1)",
                    [(ref, *f) for f in filas])
    con.commit()
    con.close()


def sembrar_hc(ruta, tabla, ref, filas):
    """Filas del Halcyon: (nivel REAL, medido, diferencia)."""
    con = sqlite3.connect(ruta)
    con.executemany(f"INSERT INTO {tabla} (ref, id_energia, nivel, valor_medido, discrepancia, activo) VALUES (?, 0, ?, ?, ?, 1)",
                    [(ref, *f) for f in filas])
    con.commit()
    con.close()


def consulta(ruta, sql, params=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def pelado(clase, ref):
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.ref = ref
    obj.subtool = QToolBox()
    obj.db_manager = DatabaseManager()
    if clase is PruebaMensualHc:
        obj.esHc = True
    return obj


def celdas(tabla):
    """Cada celda como texto; None si la celda no tiene elemento."""
    return [[tabla.item(f, c).text() if tabla.item(f, c) is not None else None for c in range(tabla.columnCount())]
            for f in range(tabla.rowCount())]


def tablas_600(clase, ref):
    obj = pelado(clase, ref)
    obj._crear_tablas_indicadores()
    brazo = obj.subtool.widget(0).findChild(QTableWidget)
    colimador = obj.subtool.widget(1).findChild(QTableWidget)
    return obj, brazo, colimador


def tablas_hc(ref):
    obj = pelado(PruebaMensualHc, ref)
    resultado = obj._crear_tablas_aspectos_mecanicos()
    assert resultado is not None, "la construcción de las tablas del Halcyon falló"
    return obj, resultado[0], resultado[1]


# ================================================================================================ la función pura

class TestLaFuncionColocaPorAngulo:

    @pytest.mark.parametrize("valor", ["270°", "270", 270, 270.0, "270.0°", "270.0", " 270 °", "270.00"])
    def test_el_angulo_se_lee_como_numero(self, fpn, valor):
        assert fpn.angulo(valor) == 270.0

    @pytest.mark.parametrize("valor", [None, "", "°", "abc", "nan", "inf", "-inf", "270 grados", object()])
    def test_lo_que_no_es_un_angulo_da_none(self, fpn, valor):
        assert fpn.angulo(valor) is None

    def test_cada_fila_va_a_su_nivel_y_la_de_180_no_se_muestra(self, fpn):
        filas = [("0°", "a", "b"), ("180°", "c", "d"), ("270°", "e", "f"), ("90°", "g", "h")]
        assert fpn.filas_por_nivel(filas, ["0°", "90°", "270°"], 3) == [("0°", "a", "b"), ("90°", "g", "h"), ("270°", "e", "f")]

    def test_la_fila_guardada_se_devuelve_tal_cual(self, fpn):
        fila = ("270", "x", "y")
        assert fpn.filas_por_nivel([fila], ["270°"], 3)[0] is fila

    def test_un_nivel_sin_fila_da_la_vacia_con_su_etiqueta_y_su_ancho(self, fpn):
        assert fpn.filas_por_nivel([("0°", "1", "1")], ["0°", "90°", "270°"], 3) == [("0°", "1", "1"), ["90°", "", ""], ["270°", "", ""]]
        assert fpn.filas_por_nivel([], ["0"], 4) == [["0", "", "", ""]]

    def test_sin_filas_y_sin_niveles(self, fpn):
        assert fpn.filas_por_nivel([], [], 3) == []
        assert fpn.filas_por_nivel([("0°", "1", "1")], [], 3) == []

    def test_formas_distintas_del_mismo_angulo(self, fpn):
        filas = [(0.0, 1, 2), ("90", 3, 4), ("270.0°", 5, 6)]
        assert fpn.filas_por_nivel(filas, ["0°", "90°", "270°"], 3) == filas
        assert fpn.filas_por_nivel(filas, ["0", "90", "270"], 3) == filas

    def test_se_compara_como_numero_no_como_texto(self, fpn):
        assert fpn.filas_por_nivel([("90.0", "a", "b")], ["90°"], 3) == [("90.0", "a", "b")]
        assert fpn.filas_por_nivel([("9", "a", "b"), ("2700", "c", "d")], ["90°", "270°"], 3) == [["90°", "", ""], ["270°", "", ""]]
        assert fpn.angulo("90.4") == 90.4 and fpn.filas_por_nivel([("90.4", "a", "b")], ["90°"], 3) == [["90°", "", ""]]

    def test_con_dos_filas_del_mismo_angulo_queda_la_primera(self, fpn):
        assert fpn.filas_por_nivel([("90°", "a", "b"), ("90", "c", "d")], ["90°"], 3) == [("90°", "a", "b")]

    def test_las_filas_que_no_son_angulo_o_vacias_se_ignoran(self, fpn):
        assert fpn.filas_por_nivel([(), ("abc", 1, 2), (None, 3, 4), ("0°", 5, 6)], ["0°"], 3) == [("0°", 5, 6)]

    def test_no_modifica_lo_que_recibe(self, fpn):
        filas, niveles = [("270°", "1", "2"), ("0°", "3", "4")], ["0°", "90°", "270°"]
        copia_f, copia_n = list(filas), list(niveles)
        fpn.filas_por_nivel(filas, niveles, 3)
        assert filas == copia_f and niveles == copia_n


# ================================================================================================ el formulario del 600 y del iX

@pytest.mark.parametrize("clase", [PruebaMensual600, PruebaMensualIX])
class TestFormulario600eIX:

    def test_un_control_nuevo_tiene_0_90_y_270_y_el_brazo_cuatro(self, bd, clase):
        obj, brazo, colimador = tablas_600(clase, 999999)
        assert celdas(colimador) == [["0°", "", ""], ["90°", "", ""], ["270°", "", ""]]
        assert celdas(brazo) == [["0°", "", ""], ["90°", "", ""], ["180°", "", ""], ["270°", "", ""]]
        cerrar(obj)

    @pytest.mark.parametrize("orden", list(ORDENES))
    def test_un_control_de_cuatro_filas_se_ve_cada_valor_en_su_angulo(self, bd, clase, orden):
        control(bd, 700)
        sembrar(bd, "indicadores_angulares_colimador", 700, [(n, SINTETICO[n], SINTETICO[n]) for n in ORDENES[orden]])
        obj, _, colimador = tablas_600(clase, 700)
        assert celdas(colimador) == [["0°", "1.1", "1.1"], ["90°", "2.2", "2.2"], ["270°", "4.4", "4.4"]]
        cerrar(obj)

    def test_un_control_de_tres_filas_se_ve_sin_fila_en_blanco(self, bd, clase):
        control(bd, 701)
        sembrar(bd, "indicadores_angulares_colimador", 701, [("270°", "4.4", "4.5"), ("0°", "1.1", "1.2"), ("90°", "2.2", "2.3")])
        obj, _, colimador = tablas_600(clase, 701)
        assert celdas(colimador) == [["0°", "1.1", "1.2"], ["90°", "2.2", "2.3"], ["270°", "4.4", "4.5"]]
        cerrar(obj)

    def test_un_angulo_sin_guardar_queda_vacio_con_su_etiqueta(self, bd, clase):
        control(bd, 702)
        sembrar(bd, "indicadores_angulares_colimador", 702, [("270°", "4.4", "4.4"), ("180°", "3.3", "3.3")])
        obj, _, colimador = tablas_600(clase, 702)
        assert celdas(colimador) == [["0°", "", ""], ["90°", "", ""], ["270°", "4.4", "4.4"]]
        assert not int(colimador.item(1, 0).flags()) & int(Qt.ItemIsEditable) and int(colimador.item(1, 1).flags()) & int(Qt.ItemIsEditable)
        cerrar(obj)

    def test_el_brazo_se_llena_como_antes_por_posicion(self, bd, clase):
        control(bd, 703)
        sembrar(bd, "indicadores_brazo", 703, [(n, SINTETICO[n], SINTETICO[n]) for n in ORDENES["revuelto"]])
        devuelto = consulta(bd, "SELECT nivel, indicador_luminoso_consola, indicador_luminoso_equipo FROM indicadores_brazo WHERE ref = ? AND (activo IS NULL OR activo = 1)", (703,))
        obj, brazo, _ = tablas_600(clase, 703)
        assert celdas(brazo) == [list(f) for f in devuelto]
        assert [f[0] for f in devuelto] != ["0°", "90°", "180°", "270°"], "la consulta ya no devuelve el orden del índice: la prueba del brazo no distingue"
        cerrar(obj)


def test_subir_deja_tres_filas_vigentes_y_la_de_180_anulada_no_borrada(bd):
    control(bd, 710)
    sembrar(bd, "indicadores_angulares_colimador", 710, [(n, SINTETICO[n], SINTETICO[n]) for n in ORDENES["como se guardaron"]])
    antes = consulta(bd, "SELECT rowid, nivel FROM indicadores_angulares_colimador WHERE ref = 710")
    obj, _, colimador = tablas_600(PruebaMensual600, 710)
    obj._actualizar_tabla_despues_subida = lambda: None
    obj._subir_tabla_optimizada(colimador, "indicadores_angulares_colimador", 710)
    vigentes = consulta(bd, "SELECT nivel, indicador_luminoso_consola, indicador_luminoso_equipo FROM indicadores_angulares_colimador WHERE ref = 710 AND (activo IS NULL OR activo = 1) ORDER BY rowid")
    assert vigentes == [("0°", "1.1", "1.1"), ("90°", "2.2", "2.2"), ("270°", "4.4", "4.4")]
    viejas = dict(consulta(bd, "SELECT rowid, activo FROM indicadores_angulares_colimador WHERE ref = 710"))
    assert all(viejas[rowid] == 0 for rowid, _ in antes), "la generación anterior debía quedar anulada (activo = 0), no borrada"
    assert consulta(bd, "SELECT activo, indicador_luminoso_consola FROM indicadores_angulares_colimador WHERE ref = 710 AND nivel = '180°'") == [(0, "3.3")]
    cerrar(obj)


# ================================================================================================ el formulario del Halcyon

class TestFormularioHalcyon:

    def test_un_control_nuevo_tiene_0_90_y_270_y_el_brazo_cuatro(self, bd):
        obj, brazo, colimador = tablas_hc(999999)
        assert celdas(colimador) == [["0", "", ""], ["90", "", ""], ["270", "", ""]]
        assert celdas(brazo) == [["0", "", ""], ["90", "", ""], ["180", "", ""], ["270", "", ""]]
        cerrar(obj)

    @pytest.mark.parametrize("orden", list(ORDENES))
    def test_un_control_con_180_se_ve_cada_valor_en_su_angulo(self, bd, orden):
        control(bd, 720, "Halcyon")
        sembrar_hc(bd, "HC_indicadores_colimador", 720, [(float(n[:-1]), float(SINTETICO[n]), 0.5) for n in ORDENES[orden]])
        obj, _, colimador = tablas_hc(720)
        assert celdas(colimador) == [["0.0", "1.1", "0.5"], ["90.0", "2.2", "0.5"], ["270.0", "4.4", "0.5"]]
        cerrar(obj)

    @pytest.mark.parametrize("guardados", [(90.0, 180.0, 270.0), (0.0, 180.0, 270.0), (0.0, 90.0, 180.0), (180.0,)],
                             ids=["sin el 0", "sin el 90", "sin el 270", "solo el 180"])
    def test_un_angulo_sin_guardar_queda_vacio_con_su_etiqueta(self, bd, guardados):
        control(bd, 722, "Halcyon")
        sembrar_hc(bd, "HC_indicadores_colimador", 722, [(a, *HC_SINTETICO[a]) for a in guardados])
        obj, _, colimador = tablas_hc(722)
        assert celdas(colimador) == [[str(a), *map(str, HC_SINTETICO[a])] if a in guardados else [ETIQUETA_HC[a], "", ""] for a in ETIQUETA_HC]
        for fila, angulo in enumerate(ETIQUETA_HC):
            if angulo not in guardados:
                assert not int(colimador.item(fila, 0).flags()) & int(Qt.ItemIsEditable) and int(colimador.item(fila, 1).flags()) & int(Qt.ItemIsEditable)
        cerrar(obj)

    def test_subir_deja_tres_filas_vigentes_con_el_nivel_real_y_la_de_180_anulada_no_borrada(self, bd):
        control(bd, 723, "Halcyon")
        sembrar_hc(bd, "HC_indicadores_colimador", 723, [(a, *HC_SINTETICO[a]) for a in (0.0, 180.0, 270.0)])
        antes = [fila[0] for fila in consulta(bd, "SELECT rowid FROM HC_indicadores_colimador WHERE ref = 723")]
        obj, _, _ = tablas_hc(723)
        obj._actualizar_tabla_despues_subida = lambda: None
        obj.subtool.widget(1).findChild(QPushButton).click()
        vigentes = consulta(bd, "SELECT nivel, typeof(nivel), valor_medido FROM HC_indicadores_colimador WHERE ref = 723 AND activo = 1 ORDER BY rowid")
        assert [fila[:2] for fila in vigentes] == [(0.0, "real"), (90.0, "real"), (270.0, "real")]
        assert [vigentes[0][2], vigentes[2][2]] == [1.1, 4.4]
        viejas = dict(consulta(bd, "SELECT rowid, activo FROM HC_indicadores_colimador WHERE ref = 723"))
        assert all(viejas.get(rowid) == 0 for rowid in antes), "la generación anterior debía quedar anulada (activo = 0), no borrada"
        assert consulta(bd, "SELECT activo, valor_medido FROM HC_indicadores_colimador WHERE ref = 723 AND nivel = 180.0") == [(0, 3.3)]
        cerrar(obj)

    def test_el_brazo_se_llena_como_antes_por_posicion(self, bd):
        control(bd, 721, "Halcyon")
        sembrar_hc(bd, "HC_indicadores_brazo", 721, [(270.0, 4.4, 0.1), (0.0, 1.1, 0.1), (180.0, 3.3, 0.1), (90.0, 2.2, 0.1)])
        devuelto = consulta(bd, "SELECT nivel, valor_medido, discrepancia FROM HC_indicadores_brazo WHERE ref = ? AND id_energia = 0 AND (activo IS NULL OR activo = 1)", (721,))
        obj, brazo, _ = tablas_hc(721)
        assert celdas(brazo) == [[str(v) for v in f] for f in devuelto]
        cerrar(obj)


# ================================================================================================ las demás tablas no cambian

class TestSinNivelesTodoComoAntes:

    def test_niveles_vale_none_por_omision(self):
        for metodo in (PruebaMensual600.createSimpleTable1, PruebaMensual600._llenar_tabla_bd):
            assert inspect.signature(metodo).parameters["niveles"].default is None

    def test_sin_niveles_se_llena_por_posicion_y_se_corta_en_las_filas_de_la_tabla(self, app):
        obj = pelado(PruebaMensual600, 1)
        tabla = QTableWidget(2, 3)
        obj._llenar_tabla_bd(tabla, [(9, "270°", "a", "b"), (9, "0°", "c", "d"), (9, "90°", "e", "f")], "indicadores_angulares_colimador")
        assert celdas(tabla) == [["270°", "a", "b"], ["0°", "c", "d"]]
        cerrar(obj)

    def test_sin_niveles_una_fila_corta_no_se_recorta(self, app):
        obj = pelado(PruebaMensual600, 1)
        tabla = QTableWidget(2, 3)
        obj._llenar_tabla_bd(tabla, [("a", "b", "c"), ("d", "e")], "indicadores_brazo")
        assert celdas(tabla) == [["a", "b", "c"], ["d", "e", None]]
        cerrar(obj)

    def test_con_niveles_vacios_no_se_muestra_ninguna_fila_guardada(self, app):
        obj = pelado(PruebaMensual600, 1)
        tabla = QTableWidget(2, 3)
        obj._llenar_tabla_bd(tabla, [(9, "270°", "a", "b")], "indicadores_angulares_colimador", niveles=[])
        assert celdas(tabla) == [[None, None, None], [None, None, None]]
        cerrar(obj)

    def test_en_el_anual_el_recorte_sigue_siendo_el_del_esquema(self, bd):
        obj = pelado(PruebaMensual600, 1)
        obj.anual = True
        tabla = QTableWidget(1, 3)
        obj._llenar_tabla_bd(tabla, [(1, 2, 0, "x", "y", "z")], "tabla_factor_campo")
        assert celdas(tabla) == [["x", "y", "z"]]
        cerrar(obj)

    def test_con_niveles_las_filas_del_anual_se_alinean_despues_del_recorte(self, bd, fpn):
        obj = pelado(PruebaMensual600, 1)
        obj.anual = True
        tabla = QTableWidget(2, 3)
        obj._llenar_tabla_bd(tabla, [(1, 2, 0, "90", "y", "z"), (1, 2, 0, "0", "u", "v")], "tabla_factor_campo", niveles=["0", "90"])
        assert celdas(tabla) == [["0", "u", "v"], ["90", "y", "z"]]
        cerrar(obj)


# ================================================================================================ «Ver tabla»

def _ver_tabla(dialogos, funcion, ref):
    funcion(None, ref)
    assert len(dialogos) == 1, "«Ver tabla» debía abrir un diálogo"
    tabla = dialogos[0].findChild(QTableWidget)
    return dialogos[0], tabla


def test_ver_tabla_600_coloca_el_colimador_por_angulo_en_tres_filas(bd, dialogos):
    control(bd, 730)
    sembrar(bd, "indicadores_angulares_colimador", 730, [(n, SINTETICO[n], SINTETICO[n]) for n in ORDENES["al reves"]])
    sembrar(bd, "indicadores_brazo", 730, [(n, SINTETICO[n], "b") for n in ORDENES["revuelto"]])
    dlg, tabla = _ver_tabla(dialogos, load_mod.mostrar_indc_angulares, 730)
    assert tabla.rowCount() == 7
    assert [r[1:] for r in celdas(tabla)] == [["0", "1.1", "b"], ["90", "2.2", "b"], ["180", "3.3", "b"], ["270", "4.4", "b"],
                                              ["0", "1.1", "1.1"], ["90", "2.2", "2.2"], ["270", "4.4", "4.4"]]
    assert (tabla.item(0, 0).text(), tabla.rowSpan(0, 0), tabla.item(4, 0).text(), tabla.rowSpan(4, 0)) == ("Brazo", 4, "Colimador", 3)
    cerrar(dlg)


def test_ver_tabla_halcyon_separa_los_cuatro_del_brazo_de_los_tres_del_colimador(bd, dialogos):
    control(bd, 731, "Halcyon")
    sembrar_hc(bd, "HC_indicadores_colimador", 731, [(270.0, 4.4, 0.4), (180.0, 3.3, 0.3), (0.0, 1.1, 0.1), (90.0, 2.2, 0.2)])
    sembrar_hc(bd, "HC_indicadores_brazo", 731, [(90.0, 9.2, 0.2), (0.0, 9.1, 0.1), (270.0, 9.4, 0.4), (180.0, 9.3, 0.3)])
    dlg, tabla = _ver_tabla(dialogos, load_mod.mostrar_indc_brazo_HC, 731)
    assert tabla.rowCount() == 7
    assert [r[1:] for r in celdas(tabla)] == [["0", "9.1", "0.1"], ["90", "9.2", "0.2"], ["180", "9.3", "0.3"], ["270", "9.4", "0.4"],
                                              ["0", "1.1", "0.1"], ["90", "2.2", "0.2"], ["270", "4.4", "0.4"]]
    assert (tabla.item(0, 0).text(), tabla.rowSpan(0, 0), tabla.item(4, 0).text(), tabla.rowSpan(4, 0)) == ("Brazo", 4, "Colimador", 3)
    cerrar(dlg)


def test_ver_tabla_halcyon_lee_solo_el_bloque_que_escribe_el_formulario(bd, dialogos):
    control(bd, 732, "Halcyon")
    sembrar_hc(bd, "HC_indicadores_colimador", 732, [(0.0, 1.1, 0.1), (90.0, 2.2, 0.2), (270.0, 4.4, 0.4)])
    con = sqlite3.connect(bd)
    con.executemany("INSERT INTO HC_indicadores_colimador (ref, id_energia, nivel, valor_medido, discrepancia, activo) VALUES (732, 1, ?, 7.7, 7.7, 1)", [(0.0,), (90.0,), (270.0,)])
    con.commit()
    con.close()
    dlg, tabla = _ver_tabla(dialogos, load_mod.mostrar_indc_brazo_HC, 732)
    assert [r[2:] for r in celdas(tabla)[4:]] == [["1.1", "0.1"], ["2.2", "0.2"], ["4.4", "0.4"]]
    cerrar(dlg)


# ================================================================================================ datos reales (copia del 23-11)

def _md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


@pytest.fixture(scope="module")
def copia_23_11(app, tmp_path_factory):
    """Los TRES archivos de la copia del 23-11 a un temporal; el original no se abre y su md5 no cambia."""
    original = _bd_referencia.BD_REBUILD_23_11
    if not original.exists():
        pytest.skip(f"HI-0: falta {original.name} en {_bd_referencia.CARPETA_BD}")
    destino = tmp_path_factory.mktemp("copia_23_11")
    nombres = [original.name, original.name + "-wal", original.name + "-shm"]
    antes = {n: _md5(original.parent / n) for n in nombres if (original.parent / n).exists()}
    for n in antes:
        shutil.copy2(original.parent / n, destino / n)
    assert antes == {n: _md5(original.parent / n) for n in antes}, "el md5 de la base de referencia cambió al copiarla"
    return str(destino / original.name)


@pytest.fixture
def real(copia_23_11, monkeypatch, tmp_path, dialogos):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia_23_11)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    yield copia_23_11
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = previa


def _por_sql(ruta, ref):
    """Lectura independiente: {ángulo: (consola, equipo)} de las filas vigentes."""
    filas = consulta(ruta, "SELECT nivel, indicador_luminoso_consola, indicador_luminoso_equipo FROM indicadores_angulares_colimador WHERE ref = ? AND (activo IS NULL OR activo = 1)", (ref,))
    return {int(n.replace("°", "")): (c, e) for n, c, e in filas}


@pytest.mark.parametrize("ref, clase, filas_guardadas", [(47, PruebaMensualIX, 4), (45, PruebaMensual600, 4), (1, PruebaMensualIX, 3), (41, PruebaMensual600, 3)])
def test_real_cada_valor_en_la_fila_de_su_angulo(real, ref, clase, filas_guardadas):
    esperado = _por_sql(real, ref)
    assert len(esperado) == filas_guardadas
    obj, _, colimador = tablas_600(clase, ref)
    assert celdas(colimador) == [[f"{a}°", *esperado[a]] for a in (0, 90, 270)]
    cerrar(obj)


def test_real_el_iX_del_28_09_no_muestra_su_180_y_la_base_lo_conserva(real):
    obj, _, colimador = tablas_600(PruebaMensualIX, 47)
    assert "180°" not in [f[0] for f in celdas(colimador)]
    assert consulta(real, "SELECT indicador_luminoso_consola FROM indicadores_angulares_colimador WHERE ref = 47 AND nivel = '180°' AND activo = 1") == [("180",)]
    cerrar(obj)


@pytest.mark.parametrize("ref", [33, 34])
def test_real_halcyon_cada_valor_en_su_angulo(real, ref):
    filas = consulta(real, "SELECT nivel, valor_medido, discrepancia FROM HC_indicadores_colimador WHERE ref = ? AND id_energia = 0 AND (activo IS NULL OR activo = 1)", (ref,))
    esperado = {float(n): (m, d) for n, m, d in filas}
    obj, _, colimador = tablas_hc(ref)
    assert celdas(colimador) == [[str(float(a)), *(str(v) for v in esperado[a])] for a in (0.0, 90.0, 270.0)]
    cerrar(obj)


def test_real_ver_tabla_del_iX_del_28_09_en_sus_filas(real, dialogos):
    esperado = _por_sql(real, 47)
    dlg, tabla = _ver_tabla(dialogos, load_mod.mostrar_indc_angulares, 47)
    assert [r[1:] for r in celdas(tabla)[4:]] == [[str(a), *esperado[a]] for a in (0, 90, 270)]
    cerrar(dlg)


# ================================================================================================ empaquetado y fuente

def test_el_modulo_esta_una_vez_en_hidden_imports_despues_de_la_calculadora():
    arbol = ast.parse((RAIZ / "build_exe.py").read_bytes().decode("utf-8"))
    lista = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
    nombres = [e.value for e in lista.elts]
    assert nombres.count(MODULO) == 1
    assert nombres.index(MODULO) == nombres.index("ui.paginasGuia.calculadora_um_json") + 1


def test_build_exe_sigue_en_crlf():
    crudo = (RAIZ / "build_exe.py").read_bytes()
    assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b""), "build_exe.py sigue en CRLF"


def test_el_formulario_importa_la_funcion_de_forma_estatica():
    arbol = ast.parse((RAIZ / "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py").read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.ImportFrom) and n.module == MODULO and [a.name for a in n.names] == ["filas_por_nivel"] for n in arbol.body)


def test_el_modulo_nuevo_es_puro_y_sus_textos_siguen_las_reglas():
    fuente = (RAIZ / "ui/paginasControles/PruebasMensuales/filas_por_nivel.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
    assert importados == {"math"}
    assert not any(c in fuente for c in "✓✔✗✘⚠✅❌")
    assert all(len(linea) <= 140 for linea in fuente.splitlines())
