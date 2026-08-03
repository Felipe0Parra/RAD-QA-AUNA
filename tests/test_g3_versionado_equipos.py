"""G3 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-G3): no crear una fila
IDÉNTICA a otra ya activa en el catálogo de equipos.

DA-21 (2026-07-31): editar cualquier campo SIGUE bifurcando la fila -- esto
NO se toca ("Dejemos que bifurque con esos cambios"). Lo único que se
agrega: antes del INSERT de `guardarCambios`, si ya existe OTRA fila activa
de la misma (equip_type, serie) con el mismo certificado (calibr_fact,
calibr_fact2, fecha_calibr, t_cal, p_cal, h_cal, v1), se bloquea con un
aviso en vez de crear un duplicado. Caso real que motivó esto (rebuild
30-07): ids 82 y 84, idénticas en los 13 campos, ambas activas.

No se marca `activo=0` en ninguna fila existente -- varias calibraciones
activas por serie es el diseño querido (doctrina §8.4 de PLAN_F: A092535
tiene 2022 y 2025 activas a propósito, para llenar controles retroactivos).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QWidget,
)

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.equipos_service import EquiposService
from ui.paginasGuia.equipos import Config


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


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "accastellanos"


_CERT_DEFECTO = dict(
    equip_type="Cámara de ionización", model="N30013", serie="2123",
    calibr_fact=0.0545, calibr_fact2=None, fecha_calibr="30/07/2026",
    fabricante=None, t_cal=22.0, p_cal=101.325, h_cal=50.0, v1=None,
)


def _preparar_equipo(ruta, activo=1, **overrides):
    datos = dict(_CERT_DEFECTO, **overrides)
    con = sqlite3.connect(ruta)
    cur = con.execute("""
        INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2,
            fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1, activo, vigente)
        VALUES (:equip_type, :model, :serie, :calibr_fact, :calibr_fact2,
            :fecha_calibr, :fabricante, :t_cal, :p_cal, :h_cal, :v1, :activo, 0)
    """, dict(datos, activo=activo))
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


def _instancia_con_formulario(id_equipo, **overrides):
    """Config "pelada" -- solo los widgets que guardarCambios lee. Los
    valores de texto por defecto reflejan _CERT_DEFECTO (mismo formato que
    se ve en pantalla), para que `hay_cambios` salga False si nada se pasa
    en `overrides`."""
    datos = dict(
        tipo=_CERT_DEFECTO["equip_type"], modelo=_CERT_DEFECTO["model"],
        serie=_CERT_DEFECTO["serie"], factor=str(_CERT_DEFECTO["calibr_fact"]),
        fecha=_CERT_DEFECTO["fecha_calibr"], fabricante="",
        t_cal=str(_CERT_DEFECTO["t_cal"]), p_cal=str(_CERT_DEFECTO["p_cal"]),
        h_cal=str(_CERT_DEFECTO["h_cal"]), v1="", activo_marcado=True,
    )
    datos.update(overrides)

    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.user_id = _UsuarioActualFalso()
    obj.cargartabla = lambda: None
    obj.tipo = QComboBox()
    obj.tipo.addItem(datos["tipo"])
    obj.modelo = QLineEdit(datos["modelo"])
    obj.serie = QLineEdit(datos["serie"])
    obj.calib_factor = QLineEdit(datos["factor"])
    obj.calib_date = QLineEdit(datos["fecha"])
    obj.fabricante = QLineEdit(datos["fabricante"])
    obj.t_cal = QLineEdit(datos["t_cal"])
    obj.p_cal = QLineEdit(datos["p_cal"])
    obj.h_cal = QLineEdit(datos["h_cal"])
    obj.v1_cal = QLineEdit(datos["v1"])
    obj.sel_activo = QCheckBox()
    obj.sel_activo.setChecked(datos["activo_marcado"])

    obj.table = QTableWidget(1, 1)
    item = QTableWidgetItem()
    item.setData(Qt.UserRole, id_equipo)
    obj.table.setItem(0, 0, item)
    obj.table.setCurrentCell(0, 0)
    return obj


def _mock_messagebox(monkeypatch):
    import ui.paginasGuia.equipos as equipos_mod
    monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(equipos_mod.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))


def _filas_activas(ruta, equip_type="Cámara de ionización", serie="2123"):
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT id, fecha_calibr, fabricante FROM equipos "
        "WHERE equip_type = ? AND serie = ? AND activo = 1",
        (equip_type, serie)).fetchall()
    con.close()
    return filas


class TestNoRecreaFilaIdenticaAlVolverAlValorOriginal:
    """1. Reproducción exacta del caso 82/83/84: crear, editar la fecha,
    editar de vuelta a la fecha original -> NO aparece una tercera fila
    idéntica. Rojo antes del fix (hoy se crea sin más)."""

    def test_no_aparece_tercera_fila(self, app, bd_temporal, monkeypatch):
        id_x = _preparar_equipo(bd_temporal, fecha_calibr="30/07/2026")
        _mock_messagebox(monkeypatch)

        # Paso 1: editar la fecha -- bifurca, ambas quedan activas
        obj1 = _instancia_con_formulario(id_x, fecha="20/07/2026")
        Config.guardarCambios(obj1)

        filas = _filas_activas(bd_temporal)
        assert len(filas) == 2
        id_y = [f[0] for f in filas if f[0] != id_x][0]

        # Paso 2: editar la fila Y de vuelta a la fecha de X (certificado
        # idéntico al de X, que sigue activa) -> debe bloquearse
        obj2 = _instancia_con_formulario(id_y, fecha="30/07/2026")
        Config.guardarCambios(obj2)

        filas_final = _filas_activas(bd_temporal)
        assert len(filas_final) == 2, \
            "no debía crearse una tercera fila idéntica a la original"


class TestCertificadoNuevoSiCreaFilaYConservaLaAnterior:
    """2. Cambiar un campo de certificado a un valor NUEVO -> sí crea fila
    nueva, la anterior sigue activo=1 (anti-regresión de DA-21 y de la
    doctrina §8.4 de PLAN_F)."""

    def test_bifurca_y_conserva_ambas_activas(self, app, bd_temporal, monkeypatch):
        id_x = _preparar_equipo(bd_temporal)
        _mock_messagebox(monkeypatch)

        obj = _instancia_con_formulario(id_x, factor="0.0600")  # certificado nuevo
        Config.guardarCambios(obj)

        filas = _filas_activas(bd_temporal)
        assert len(filas) == 2
        assert id_x in [f[0] for f in filas]


class TestSoloFabricanteBifurcaSinBloquearContraSiMisma:
    """3a. Cambiar solo `fabricante` -> sí crea fila nueva (DA-21); la
    regla 3 NO la bloquea contra su propio certificado sin cambios."""

    def test_fabricante_distinto_bifurca(self, app, bd_temporal, monkeypatch):
        id_x = _preparar_equipo(bd_temporal)
        _mock_messagebox(monkeypatch)

        obj = _instancia_con_formulario(id_x, fabricante="PTW")
        Config.guardarCambios(obj)

        filas = _filas_activas(bd_temporal)
        assert len(filas) == 2


class TestFabricanteSiBloqueaSiCoincideConOtraFilaActiva:
    """3b. ...salvo que ya exista OTRA fila activa con el mismo
    certificado -- ahí sí se bloquea, aunque el cambio sea solo
    fabricante."""

    def test_bloquea_contra_duplicado_preexistente(self, app, bd_temporal, monkeypatch):
        id_x = _preparar_equipo(bd_temporal)
        _preparar_equipo(bd_temporal)  # id_w: certificado idéntico a id_x, ya activo
        _mock_messagebox(monkeypatch)

        obj = _instancia_con_formulario(id_x, fabricante="PTW")
        Config.guardarCambios(obj)

        filas = _filas_activas(bd_temporal)
        assert len(filas) == 2, "no debía crear una tercera fila"


class TestDoctrinaA092535SigueFuncionando:
    """4. El caso A092535: dos calibraciones DISTINTAS (2022 y 2025)
    coexisten activas y ambas aparecen en el selector -- anti-regresión de
    la doctrina de F9/G10, no negociable."""

    def test_dos_calibraciones_distintas_ambas_en_el_selector(
            self, app, bd_temporal, monkeypatch):
        id_2022 = _preparar_equipo(
            bd_temporal, model="A092535", serie="S1", fecha_calibr="15/06/2022")
        _mock_messagebox(monkeypatch)

        obj = _instancia_con_formulario(
            id_2022, modelo="A092535", serie="S1", fecha="20/07/2025")
        Config.guardarCambios(obj)

        activas = EquiposService.calibraciones_activas(
            "Cámara de ionización", "A092535")
        fechas = {fila[2] for fila in activas}
        assert fechas == {"15/06/2022", "20/07/2025"}
