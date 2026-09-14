"""R.3 (PLAN_PUNTEROS_A_EQUIPOS_11-09.md §4): tres lectores resuelven un
`equipo_id` guardado en el pasado contra el catálogo de HOY sin comprobar
que sigue siendo el mismo equipo -- `Traerinfo` (mensual), el reporte de la
calculadora y la restauración de `dialogs.py`. Basta con que un id se
recicle (R.1 lo impide por la vía normal, pero no depende de eso -- el
contador ya se perdió una vez en una reconstrucción real, §0.3 del plan)
dentro del MISMO modelo para que `findData(equipo_id)` adopte una cámara
que nunca se usó en ese control -- medido en §0.4: id=81 pasó de N31010/
1822 a N31010/1825, y `findData(81)` seguía acertando.

`EquiposService.resolver_guardado(equipo_id, model, serie)` corta esto:
solo confía en el id si el equipo que resuelve HOY coincide con lo que la
propia fila guardó. Si no, cada sitio cae a su propio respaldo (texto por
serie, o la copia guardada) en vez de adoptar al intruso.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QGridLayout, QLineEdit, QWidget,
)

import data.ManejoDatos.conection as conection_mod
import services.equipos_service as equipos_service_mod
from data.ManejoDatos.conection import Conexion

# Import circular (dialogs.py:663 importa generar_reporte_calibracion de
# vuelta) -- dialogs primero, mismo orden que test_q4_serie_guardada_manda.py.
import ui.paginasGuia.dialogs as dialogs_mod  # noqa: F401
from models.PDF.reporte_calculadora_dos import datos_a_dataframe
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)


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


def _insertar_equipo(ruta_bd, eq_id, **campos):
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


def _insertar_control(ruta_bd, equipo="Clinac 600", control="Mensual", fecha="06/2026"):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _insertar_equipos_medicion(ruta_bd, ref, tipo_camara, model, serie,
                                calibr_fact, equipo_id, activo=1,
                                fecha_calibr="01/01/2020"):
    con = sqlite3.connect(ruta_bd)
    con.execute("""
        INSERT INTO equipos_medicion
            (ref, tipo_camara, equip_type, model, serie, calibr_fact,
             fecha_calibr, equipo_id, activo)
        VALUES (?, ?, 'Cámara de ionización', ?, ?, ?, ?, ?, ?)
    """, (ref, tipo_camara, model, serie, calibr_fact, fecha_calibr,
          equipo_id, activo))
    con.commit()
    con.close()


def _mensual_pelado(ref):
    """PruebaMensual600 pelado -- mismo patrón que test_e2e3_seccion_
    equipos.py (3 grupos: Principal/Secundaria/Electrómetro)."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.user_id = _UsuarioFalso()
    obj.ref = ref
    obj.date_box = QDateEdit()
    obj.date_box.setDate(QDate(2026, 6, 1))

    obj.commenu = []
    for _ in range(3):
        combo_modelo = QComboBox()
        combo_serie = QComboBox()
        lineedit_calib = QLineEdit()
        obj.commenu.extend([combo_modelo, combo_serie, lineedit_calib])
    obj.combo_menu = obj.commenu
    return obj


def _categoria_con_layout():
    w = QWidget()
    w.setLayout(QGridLayout())
    return w


def _grupo(obj, i):
    return obj.commenu[i * 3], obj.commenu[i * 3 + 1], obj.commenu[i * 3 + 2]


class TestElCasoMedidoEnSS04:
    """Réplica exacta de la simulación del plan: el control guardó
    N31010/1822 (equipo_id=81); ese equipo se borró (DA-74) y el id 81 se
    RECICLÓ a una recalibración distinta de la MISMA cámara, N31010/1825
    -- el escenario donde `findData(equipo_id)` acierta pero está
    acertando a la cámara equivocada."""

    def _poblar(self, ruta_bd, ref):
        # el equipo VIVO hoy bajo el id reciclado: mismo modelo, otra serie
        _insertar_equipo(ruta_bd, 81, equip_type="Cámara de ionización",
                         model="N31010", serie="1825", calibr_fact=0.31,
                         fecha_calibr="02/09/2026", activo=1, vigente=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "N31010",
                                   "1822", 0.3036, equipo_id=81)

    def test_no_adopta_la_camara_reciclada(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)

        _, serie_widget, _ = _grupo(obj, 0)
        seleccionado = serie_widget.currentText()

        assert "1822" in seleccionado, (
            f"debía mostrar la serie guardada (1822); mostró {seleccionado!r} "
            f"-- adoptó la cámara reciclada bajo el mismo id")
        assert "1825" not in seleccionado


class TestElIdQueSiResuelveSigueGanando:
    """Obstáculo esperado del plan: no romper el caso legítimo (A092535 --
    dos calibraciones de la MISMA serie, elegir la correcta por id)."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 17, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=46480, fecha_calibr="23/06/2022",
                         activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 81, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=464700, fecha_calibr="28/07/2025",
                         activo=1, vigente=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "HDR1000 Plus",
                                   "A092535", 46480, equipo_id=17)

    def test_elige_la_calibracion_guardada_no_la_mas_reciente(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)

        _, serie_widget, _ = _grupo(obj, 0)
        assert serie_widget.currentData() == 17


class TestFilaLegacySinEquipoIdSigueRestaurandoPorTexto:
    """equipo_id=NULL (anterior a F9): el respaldo por texto no depende de
    resolver_guardado en absoluto -- sigue igual."""

    def _poblar(self, ruta_bd, ref):
        _insertar_equipo(ruta_bd, 5, equip_type="Cámara de ionización",
                         model="N31010", serie="1825", calibr_fact=0.31,
                         fecha_calibr="01/01/2024", activo=1, vigente=1)
        _insertar_equipos_medicion(ruta_bd, ref, "Principal", "N31010",
                                   "1825", 0.31, equipo_id=None)

    def test_restaura_por_serie_sin_equipo_id(self, app, bd_temporal):
        ref = _insertar_control(bd_temporal)
        self._poblar(bd_temporal, ref)

        obj = _mensual_pelado(ref)
        categoria = _categoria_con_layout()
        obj.botonescombobox(categoria, obj.commenu, None)

        _, serie_widget, _ = _grupo(obj, 0)
        assert serie_widget.currentData() == 5


class TestReporteDeLaCalculadoraConIdReciclado:
    """Punto 5 del protocolo: id reciclado a OTRO modelo -- el reporte debe
    imprimir la serie guardada, no la del intruso."""

    def test_modelo_distinto_imprime_la_serie_guardada(self, app, monkeypatch):
        # el id 81 hoy resuelve a un equipo de OTRO modelo -- el reciclaje
        equipo_intruso = {"id": 81, "equip_type": "Cámara de ionización",
                         "model": "OTRO_MODELO", "serie": "9999"}
        monkeypatch.setattr(
            equipos_service_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: equipo_intruso if i == 81 else None))

        datos = {"Fecha": "06/08/2026", "equipo_id": 81,
                 "Modelo_equipo": "N31010", "Numero_serie": "1822"}
        df = datos_a_dataframe(datos)

        fila = df[df[""] == "Numero_serie"]
        assert len(fila) == 1
        assert fila["Valores"].iloc[0] == "1822"  # NO "9999"

    def test_modelo_coincide_igual_imprime_del_catalogo(self, app, monkeypatch):
        """Contraste: si el id resuelve al MISMO modelo/serie que se
        guardó, sigue imprimiendo del catálogo (sin cambio de fondo)."""
        equipo_real = {"id": 81, "equip_type": "Cámara de ionización",
                       "model": "N31010", "serie": "1822"}
        monkeypatch.setattr(
            equipos_service_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: equipo_real if i == 81 else None))

        datos = {"Fecha": "06/08/2026", "equipo_id": 81,
                 "Modelo_equipo": "N31010", "Numero_serie": "1822"}
        df = datos_a_dataframe(datos)

        fila = df[df[""] == "Numero_serie"]
        assert fila["Valores"].iloc[0] == "1822"
