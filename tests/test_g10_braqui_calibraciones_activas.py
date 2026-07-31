"""G10 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md): F9 llevo el mensual/TAC y
la calculadora a "una entrada por calibracion activa, con fecha y vigencia
contra la fecha del formulario" (DA-22). Braquiterapia (diaria y mensual)
quedo fuera: sus 4 sitios (`braquiterapia.py::on_modelo_pozo_cambio/
on_modelo_elec_cambio`, `braq_mensual.py::on_modelo_pozo_cambio/
on_modelo_elec_cambio`) seguian usando `EquiposService.series_actuales`
(_FILA_ACTUAL, H2.10), que COLAPSA a una sola fila por serie -- justo la
vista donde viven las camaras de pozo. A092535 conserva activas la
calibracion de 2022 (id 17) y la de 2025 (id 77) a proposito, para
reproducir controles retroactivos con los parametros de esa epoca (doctrina
S8.4 de PLAN_F) -- y en braquiterapia solo se podia elegir la de 2025.

Nuevo `EquiposService.calibraciones_activas` (sin _FILA_ACTUAL, todas las
filas activas) + los 4 sitios reconstruyen el combo con el patron de F9:
texto de `etiqueta_equipo` + id en `currentData()`, resuelto por ID (nunca
por texto) al elegir.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.equipos_service import EquiposService
from ui.paginasControles.PruebasDiarias.braquiterapia import Linealidad
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq


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
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


def _poblar_a092535(ruta_bd):
    """Reproduce el caso real: dos calibraciones ACTIVAS de A092535
    (2022 y 2025), doctrina S8.4."""
    _insertar_equipo(ruta_bd, 17, equip_type="Cámara de pozo",
                     model="HDR1000 Plus", serie="A092535",
                     calibr_fact=46480, t_cal=22.0, p_cal=101.325,
                     h_cal=45.0, fecha_calibr="23/06/2022",
                     activo=1, vigente=0)
    _insertar_equipo(ruta_bd, 77, equip_type="Cámara de pozo",
                     model="HDR1000 Plus", serie="A092535",
                     calibr_fact=464700, t_cal=22.0, p_cal=101.325,
                     h_cal=50.0, fecha_calibr="28/07/2025",
                     activo=1, vigente=1)


def _poblar_electrometro_dos_activas(ruta_bd):
    _insertar_equipo(ruta_bd, 1, equip_type="Electrómetro",
                     model="Unidos-E", serie="002343", calibr_fact=1.0,
                     t_cal=22.0, p_cal=101.325, h_cal=50.0,
                     fecha_calibr="08/09/2022", activo=1, vigente=0)
    _insertar_equipo(ruta_bd, 2, equip_type="Electrómetro",
                     model="Unidos-E", serie="002343", calibr_fact=1.05,
                     t_cal=22.0, p_cal=101.325, h_cal=50.0,
                     fecha_calibr="17/03/2026", activo=1, vigente=1)


class TestServicioCalibracionesActivas:
    def test_devuelve_todas_las_activas_sin_colapsar_por_serie(self, bd_temporal):
        _poblar_a092535(bd_temporal)
        datos = EquiposService.calibraciones_activas(
            "Cámara de pozo", "HDR1000 Plus")
        ids = {fila[0] for fila in datos}
        assert ids == {17, 77}

    def test_no_incluye_filas_inactivas(self, bd_temporal):
        _poblar_a092535(bd_temporal)
        _insertar_equipo(bd_temporal, 57, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=46470, t_cal=22.0, p_cal=101.325,
                         h_cal=50.0, fecha_calibr="28/07/2025",
                         activo=0, vigente=0)
        datos = EquiposService.calibraciones_activas(
            "Cámara de pozo", "HDR1000 Plus")
        ids = {fila[0] for fila in datos}
        assert 57 not in ids

    def test_contrato_de_hechos_id_serie_fecha_tipo(self, bd_temporal):
        _poblar_a092535(bd_temporal)
        datos = EquiposService.calibraciones_activas(
            "Cámara de pozo", "HDR1000 Plus")
        assert (17, "A092535", "23/06/2022", "Cámara de pozo") in datos
        assert (77, "A092535", "28/07/2025", "Cámara de pozo") in datos


def _linealidad_pelada():
    """Linealidad (braquiterapia.py) sin su __init__ pesado -- solo los
    widgets de camara de pozo y electrometro que on_modelo_*_cambio/
    on_serie_*_cambio necesitan."""
    obj = Linealidad.__new__(Linealidad)
    QWidget.__init__(obj)
    obj.combo_modelo = QComboBox()
    obj.combo_serie = QComboBox()
    obj.line_cal = QLineEdit()
    obj.combo_modelo_elec = QComboBox()
    obj.combo_serie_elec = QComboBox()
    obj.line_cal_elec = QLineEdit()
    return obj


def _mensual_braq_pelado():
    """PruebaMensualBraq sin su __init__ pesado -- mismos widgets de pozo/
    electrometro, mas t0/p0/h0 (que on_serie_pozo_cambio tambien llena)."""
    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)
    obj.combo_modelo = QComboBox()
    obj.combo_serie = QComboBox()
    obj.line_cal = QLineEdit()
    obj.t0 = QLineEdit()
    obj.p0 = QLineEdit()
    obj.h0 = QLineEdit()
    obj.combo_modelo_elec = QComboBox()
    obj.combo_serie_elec = QComboBox()
    obj.line_cal_elec = QLineEdit()
    return obj


class TestBraquiterapiaDiariaComboPozo:
    """ROJO ANTES DEL FIX: on_modelo_pozo_cambio usaba series_actuales
    (_FILA_ACTUAL) -- el combo ofrecia UNA sola entrada para A092535 (la de
    mayor id entre las activas, id 77), nunca la de 2022 (id 17)."""

    def test_el_combo_ofrece_las_dos_calibraciones_activas(self, app, bd_temporal):
        _poblar_a092535(bd_temporal)
        obj = _linealidad_pelada()
        obj.on_modelo_pozo_cambio("HDR1000 Plus")
        # Excluye el placeholder "Seleccionar Serie..." (currentData=None,
        # convencion ya existente que se conserva a proposito -- fuerza
        # seleccion explicita, mismo patron que F9 en el mensual).
        ids_en_combo = {obj.combo_serie.itemData(i)
                        for i in range(obj.combo_serie.count())} - {None}
        assert ids_en_combo == {17, 77}

    def test_las_dos_entradas_tienen_texto_distinguible(self, app, bd_temporal):
        _poblar_a092535(bd_temporal)
        obj = _linealidad_pelada()
        obj.on_modelo_pozo_cambio("HDR1000 Plus")
        textos = [obj.combo_serie.itemText(i)
                  for i in range(obj.combo_serie.count())]
        assert len(set(textos)) == len(textos)  # sin duplicados

    def test_elegir_la_de_2022_resuelve_su_propio_factor(self, app, bd_temporal):
        _poblar_a092535(bd_temporal)
        obj = _linealidad_pelada()
        obj.on_modelo_pozo_cambio("HDR1000 Plus")

        indice_id17 = next(i for i in range(obj.combo_serie.count())
                           if obj.combo_serie.itemData(i) == 17)
        obj.combo_serie.setCurrentIndex(indice_id17)
        obj.on_serie_pozo_cambio()

        assert obj.line_cal.text() == "46480"

    def test_elegir_la_de_2025_resuelve_su_propio_factor(self, app, bd_temporal):
        _poblar_a092535(bd_temporal)
        obj = _linealidad_pelada()
        obj.on_modelo_pozo_cambio("HDR1000 Plus")

        indice_id77 = next(i for i in range(obj.combo_serie.count())
                           if obj.combo_serie.itemData(i) == 77)
        obj.combo_serie.setCurrentIndex(indice_id77)
        obj.on_serie_pozo_cambio()

        assert obj.line_cal.text() == "464700"


class TestBraquiterapiaDiariaComboElectrometro:
    def test_el_combo_ofrece_las_dos_calibraciones_activas(self, app, bd_temporal):
        _poblar_electrometro_dos_activas(bd_temporal)
        obj = _linealidad_pelada()
        obj.on_modelo_elec_cambio("Unidos-E")
        # Excluye el placeholder "Seleccionar Serie..." (currentData=None).
        ids_en_combo = {obj.combo_serie_elec.itemData(i)
                        for i in range(obj.combo_serie_elec.count())} - {None}
        assert ids_en_combo == {1, 2}

    def test_elegir_cada_una_resuelve_su_propio_factor(self, app, bd_temporal):
        _poblar_electrometro_dos_activas(bd_temporal)
        obj = _linealidad_pelada()
        obj.on_modelo_elec_cambio("Unidos-E")

        indice_id1 = next(i for i in range(obj.combo_serie_elec.count())
                          if obj.combo_serie_elec.itemData(i) == 1)
        obj.combo_serie_elec.setCurrentIndex(indice_id1)
        obj.on_serie_elec_cambio()
        # calibr_fact esta declarada INTEGER en el esquema (preexistente,
        # conection.py) -- SQLite guarda 1.0 como el entero 1 (afinidad de
        # columna, no truncamiento de este fix). Es el mismo valor que
        # muestra hoy el electrometro real TW41047 (kelec=1.000).
        assert obj.line_cal_elec.text() == "1"

        indice_id2 = next(i for i in range(obj.combo_serie_elec.count())
                          if obj.combo_serie_elec.itemData(i) == 2)
        obj.combo_serie_elec.setCurrentIndex(indice_id2)
        obj.on_serie_elec_cambio()
        assert obj.line_cal_elec.text() == "1.05"


class TestBraqMensualComboPozo:
    """Mismo defecto y mismo fix en braq_mensual.py -- verificado por
    separado porque es un archivo/clase distinto sin helpers compartidos
    con braquiterapia.py."""

    def test_el_combo_ofrece_las_dos_calibraciones_activas(self, app, bd_temporal):
        _poblar_a092535(bd_temporal)
        obj = _mensual_braq_pelado()
        obj.on_modelo_pozo_cambio("HDR1000 Plus")
        # Excluye el placeholder "Seleccionar Serie..." (currentData=None,
        # convencion ya existente que se conserva a proposito -- fuerza
        # seleccion explicita, mismo patron que F9 en el mensual).
        ids_en_combo = {obj.combo_serie.itemData(i)
                        for i in range(obj.combo_serie.count())} - {None}
        assert ids_en_combo == {17, 77}

    def test_elegir_la_de_2022_resuelve_factor_y_condiciones_propias(
            self, app, bd_temporal):
        _poblar_a092535(bd_temporal)
        obj = _mensual_braq_pelado()
        obj.on_modelo_pozo_cambio("HDR1000 Plus")

        indice_id17 = next(i for i in range(obj.combo_serie.count())
                           if obj.combo_serie.itemData(i) == 17)
        obj.combo_serie.setCurrentIndex(indice_id17)
        obj.on_serie_pozo_cambio()

        assert obj.line_cal.text() == "46480"
        assert obj.h0.text() == "45.0"

    def test_elegir_la_de_2025_resuelve_factor_y_condiciones_propias(
            self, app, bd_temporal):
        _poblar_a092535(bd_temporal)
        obj = _mensual_braq_pelado()
        obj.on_modelo_pozo_cambio("HDR1000 Plus")

        indice_id77 = next(i for i in range(obj.combo_serie.count())
                           if obj.combo_serie.itemData(i) == 77)
        obj.combo_serie.setCurrentIndex(indice_id77)
        obj.on_serie_pozo_cambio()

        assert obj.line_cal.text() == "464700"
        assert obj.h0.text() == "50.0"


class TestBraqMensualComboElectrometro:
    def test_el_combo_ofrece_las_dos_calibraciones_activas(self, app, bd_temporal):
        _poblar_electrometro_dos_activas(bd_temporal)
        obj = _mensual_braq_pelado()
        obj.on_modelo_elec_cambio("Unidos-E")
        # Excluye el placeholder "Seleccionar Serie..." (currentData=None).
        ids_en_combo = {obj.combo_serie_elec.itemData(i)
                        for i in range(obj.combo_serie_elec.count())} - {None}
        assert ids_en_combo == {1, 2}

    def test_elegir_cada_una_resuelve_su_propio_factor(self, app, bd_temporal):
        _poblar_electrometro_dos_activas(bd_temporal)
        obj = _mensual_braq_pelado()
        obj.on_modelo_elec_cambio("Unidos-E")

        indice_id2 = next(i for i in range(obj.combo_serie_elec.count())
                          if obj.combo_serie_elec.itemData(i) == 2)
        obj.combo_serie_elec.setCurrentIndex(indice_id2)
        obj.on_serie_elec_cambio()
        assert obj.line_cal_elec.text() == "1.05"
