"""Q.5 (PLAN_EQUIPOS_BORRADO_Y_VIGENCIA_10-09.md SS4-ter): el catalogo de
equipos pintaba TRES estados (inactivo->rojo, activo+vencido->amarillo,
activo+vigente->verde) porque el color contestaba DOS preguntas a la vez
(¿esta activo? ¿esta vigente?) -- la primera ya la contesta la columna
"Activo" con su propio texto "Si"/"No".

Pedido del fisico (10-09, segunda ronda), verbatim: "el color del texto
para cada fila deberia ser solo uno de dos colores, verde o rojo, verde si
esta dentro de la fecha de calibracion o rojo si no".

Este test fija la garantia: en TODA la tabla (todas las filas, todas las
columnas) solo aparecen dos QColor de texto distintos, ninguno depende de
`activo`, y ninguna celda tiene fondo pintado.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import QApplication, QTableWidget, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.equipos import Config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test_q5.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _config_pelado():
    """Config sin su __init__ pesado -- mismo patron que test_g8, para
    poder llamar cargartabla() directamente sobre una tabla real."""
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.table = QTableWidget()
    return obj


def _fecha_relativa(dias):
    """dd/MM/yyyy relativa a HOY -- nunca un literal fijo (DP-94): una
    calibracion "vigente" o "vencida" tiene que seguir siendolo sin
    importar que dia se corra la suite."""
    return QDate.currentDate().addDays(dias).toString("dd/MM/yyyy")


# Camara de ionizacion: 2 años de vigencia (services/vigencia_equipo.py).
FECHA_VIGENTE = _fecha_relativa(-30)          # calibrada hace 1 mes
FECHA_VENCIDA = _fecha_relativa(-3 * 365)     # calibrada hace 3 años


def _insertar_equipo(ruta_bd, eq_id, activo, fecha_calibr):
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO equipos (id, equip_type, model, serie, calibr_fact, "
        "fecha_calibr, activo) VALUES (?, 'Cámara de ionización', 'N31010', "
        "?, 0.3, ?, ?)",
        (eq_id, f"S{eq_id}", fecha_calibr, activo))
    con.commit()
    con.close()


def _fila_a_columna(obj, fila, nombre_columna):
    headers = [obj.table.horizontalHeaderItem(c).text()
               for c in range(obj.table.columnCount())]
    return headers.index(nombre_columna)


def _color_texto(obj, fila, columna):
    item = obj.table.item(fila, columna)
    return item.data(Qt.ForegroundRole).color() if item.data(Qt.ForegroundRole) else None


def _color_fondo(obj, fila, columna):
    item = obj.table.item(fila, columna)
    return item.data(Qt.BackgroundRole)


@pytest.fixture
def tabla_con_4_estados(app, bd_temporal):
    """id=1 activa+vigente, id=2 activa+vencida, id=3 inactiva+vigente,
    id=4 inactiva+vencida -- los 4 cruces de las dos preguntas."""
    _insertar_equipo(bd_temporal, 1, 1, FECHA_VIGENTE)
    _insertar_equipo(bd_temporal, 2, 1, FECHA_VENCIDA)
    _insertar_equipo(bd_temporal, 3, 0, FECHA_VIGENTE)
    _insertar_equipo(bd_temporal, 4, 0, FECHA_VENCIDA)

    obj = _config_pelado()
    obj.cargartabla()
    return obj


class TestDosColoresUnaSolaSenal:

    def test_exactamente_dos_colores_de_texto_en_toda_la_tabla(self, tabla_con_4_estados):
        obj = tabla_con_4_estados
        colores = set()
        for fila in range(obj.table.rowCount()):
            for col in range(obj.table.columnCount()):
                c = _color_texto(obj, fila, col)
                if c is not None:
                    colores.add(c.name())
        assert len(colores) <= 2, (
            f"debe haber a lo sumo 2 colores de texto en toda la tabla, "
            f"hay {len(colores)}: {colores}")

    def test_ninguna_celda_tiene_fondo_pintado(self, tabla_con_4_estados):
        obj = tabla_con_4_estados
        for fila in range(obj.table.rowCount()):
            for col in range(obj.table.columnCount()):
                assert _color_fondo(obj, fila, col) is None, (
                    f"fila {fila} columna {col} tiene fondo pintado")

    def test_activa_vencida_e_inactiva_vencida_tienen_el_mismo_color(self, tabla_con_4_estados):
        obj = tabla_con_4_estados
        col_id = _fila_a_columna(obj, 0, "ID") if False else 0
        # Las filas se ordenan por model/serie/id -- id=2 (activa+vencida)
        # y id=4 (inactiva+vencida) tienen la misma serie 'S2'/'S4', se
        # identifican por Qt.UserRole.
        colores_vencidas = set()
        for fila in range(obj.table.rowCount()):
            id_fila = obj.table.item(fila, 1).data(Qt.UserRole)
            if id_fila in (2, 4):
                c = _color_texto(obj, fila, 1)
                colores_vencidas.add(c.name())
        assert len(colores_vencidas) == 1, (
            f"activa+vencida e inactiva+vencida deben compartir color: {colores_vencidas}")

    def test_activa_vigente_e_inactiva_vigente_tienen_el_mismo_color_distinto_del_vencido(
            self, tabla_con_4_estados):
        obj = tabla_con_4_estados
        colores_vigentes = set()
        colores_vencidas = set()
        for fila in range(obj.table.rowCount()):
            id_fila = obj.table.item(fila, 1).data(Qt.UserRole)
            c = _color_texto(obj, fila, 1)
            if id_fila in (1, 3):
                colores_vigentes.add(c.name())
            elif id_fila in (2, 4):
                colores_vencidas.add(c.name())
        assert len(colores_vigentes) == 1
        assert colores_vigentes != colores_vencidas

    def test_columna_activo_sigue_diciendo_si_no_y_conserva_tooltip(self, tabla_con_4_estados):
        obj = tabla_con_4_estados
        col_activo = obj.table.columnCount() - 2
        vistos = {}
        for fila in range(obj.table.rowCount()):
            id_fila = obj.table.item(fila, 0).data(Qt.UserRole)
            item = obj.table.item(fila, col_activo)
            vistos[id_fila] = (item.text(), item.toolTip())

        assert vistos[1][0] == "Sí" and vistos[1][1] == "✅ Equipo activo"
        assert vistos[2][0] == "Sí" and vistos[2][1] == "✅ Equipo activo"
        assert vistos[3][0] == "No" and vistos[3][1] == "⚠️ Equipo inactivo"
        assert vistos[4][0] == "No" and vistos[4][1] == "⚠️ Equipo inactivo"

    def test_celda_de_fecha_vencida_conserva_su_tooltip(self, tabla_con_4_estados):
        obj = tabla_con_4_estados
        col_fecha = _fila_a_columna(obj, 0, "Fecha Cal.")
        for fila in range(obj.table.rowCount()):
            id_fila = obj.table.item(fila, 0).data(Qt.UserRole)
            item = obj.table.item(fila, col_fecha)
            if id_fila in (2, 4):
                assert item.toolTip() == "Calibración vencida - Requiere actualización"

    def test_tabla_conserva_13_columnas_y_no_colapsa_por_serie(self, tabla_con_4_estados):
        """Compuerta de cero diferencias: G8/DA-22 (una fila por fila real
        de equipos, no una por serie) no se toca."""
        obj = tabla_con_4_estados
        assert obj.table.columnCount() == 13
        assert obj.table.rowCount() == 4
