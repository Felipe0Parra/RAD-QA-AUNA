"""G8 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md): el catalogo de equipos
mostraba solo 1 fila por serie (`WHERE id IN (SELECT MAX(id) FROM equipos
GROUP BY serie)`), sin filtrar `activo` -- H2.10 ya habia migrado los
SERVICIOS (`EquiposService`, usados por la calculadora y los formularios) a
`_FILA_ACTUAL` (`activo=1`, la mas reciente), pero `cargartabla` (la
PANTALLA) se quedo con el patron viejo. Resultado medido contra la BD real
(2026-07-31): de 39 filas, solo 15 se veian, y 5 de las OCULTAS estaban
ACTIVAS -- exactamente las que la calculadora y los formularios SI usan
(ids 7, 13, 16, 17, 18). El catalogo mostraba una fila DISTINTA de la que
esta en uso, o ninguna.

DA-22 (decision del fisico, 2026-07-31): "en equipos se deben mostrar todas
las versiones que ha tenido cada camara y serie a lo largo del tiempo".
`cargartabla` deja de colapsar por serie -- lista las 39 filas.
"""
import os

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QTableWidget, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.equipos import Config

from _bd_referencia import BD_QA  # DP-104: fuente única de rutas de BD
DB = str(BD_QA)


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


def _config_pelado():
    """Config sin su __init__ pesado -- solo table, para poder llamar
    cargartabla() directamente (mismo patron que test_f7/test_e2, pero aqui
    NO se stubea cargartabla porque es justo lo que se prueba)."""
    obj = Config.__new__(Config)
    QWidget.__init__(obj)
    obj.table = QTableWidget()
    return obj


def _ids_visibles(obj):
    return {obj.table.item(fila, 0).data(Qt.UserRole)
            for fila in range(obj.table.rowCount())}


_CAMPOS_BASE = dict(
    equip_type="Cámara de ionización", model="N30013", fabricante="PTW",
    t_cal=22.0, p_cal=101.325, h_cal=50.0, v1=300.0,
)


class TestCatalogoListaTodasLasFilas:
    def test_no_colapsa_por_serie_fila_activa_antigua_queda_visible(
            self, app, bd_temporal):
        """Reproduce el caso real (2123/0453/A972662/A092535/B091982):
        una fila ACTIVA con id BAJO (la que esta en uso) convive con una
        fila INACTIVA de id ALTO (un duplicado historico de H2.6) de la
        misma serie. ROJO ANTES DEL FIX: con `MAX(id) GROUP BY serie`, la
        fila alta (inactiva) tapa a la baja (activa) -- la que esta en uso
        queda invisible."""
        _insertar_equipo(bd_temporal, 1, serie="2123", calibr_fact=0.0545,
                         fecha_calibr="05/02/2024", activo=1, vigente=1,
                         **_CAMPOS_BASE)
        _insertar_equipo(bd_temporal, 2, serie="2123", calibr_fact=0.0545,
                         fecha_calibr="05/02/2024", activo=0, vigente=0,
                         **_CAMPOS_BASE)

        obj = _config_pelado()
        obj.cargartabla()

        assert _ids_visibles(obj) == {1, 2}

    def test_conteo_de_filas_coincide_con_el_total_de_la_tabla(
            self, app, bd_temporal):
        """Verificacion de F9: conteo antes/despues -- ninguna fila puede
        faltar. Aqui, contra una BD temporal con 5 filas de mezcla
        activa/inactiva/misma-serie/serie-distinta."""
        _insertar_equipo(bd_temporal, 1, serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2020", activo=1, vigente=1,
                         **_CAMPOS_BASE)
        _insertar_equipo(bd_temporal, 2, serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2019", activo=0, vigente=0,
                         **_CAMPOS_BASE)
        _insertar_equipo(bd_temporal, 3, serie="S2", calibr_fact=2.0,
                         fecha_calibr="01/01/2021", activo=1, vigente=1,
                         **_CAMPOS_BASE)
        _insertar_equipo(bd_temporal, 4, serie="S3", calibr_fact=3.0,
                         fecha_calibr="01/01/2022", activo=0, vigente=0,
                         **_CAMPOS_BASE)
        _insertar_equipo(bd_temporal, 5, serie="S3", calibr_fact=3.5,
                         fecha_calibr="01/01/2023", activo=1, vigente=1,
                         **_CAMPOS_BASE)

        obj = _config_pelado()
        obj.cargartabla()

        assert obj.table.rowCount() == 5
        assert _ids_visibles(obj) == {1, 2, 3, 4, 5}

    def test_doctrina_a092535_dos_calibraciones_activas_ambas_visibles(
            self, app, bd_temporal):
        """Doctrina S8.4 de PLAN_F, F9, DA-22: varias calibraciones ACTIVAS
        de la misma serie es el diseno querido (llenar un control
        retroactivo con los parametros de esa epoca), NO un duplicado a
        "corregir". Con el fix, ambas se ven; efecto esperado y deseable,
        no un defecto."""
        _insertar_equipo(bd_temporal, 17, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=46480, fecha_calibr="23/06/2022",
                         activo=1, vigente=0, fabricante="Standard Imaging",
                         t_cal=22.0, p_cal=101.325, h_cal=45.0, v1=None)
        _insertar_equipo(bd_temporal, 77, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=464700, fecha_calibr="28/07/2025",
                         activo=1, vigente=1, fabricante="Standard Imaging",
                         t_cal=22.0, p_cal=101.325, h_cal=50.0, v1=300.0)

        obj = _config_pelado()
        obj.cargartabla()

        assert _ids_visibles(obj) == {17, 77}


class TestSeleccionPorFilaNoSeConfundeEntreVersionesDeLaMismaSerie:
    """El riesgo real que el plan senala: con varias filas de la MISMA serie
    visibles, editar/anular deben actuar sobre la fila exacta seleccionada,
    nunca sobre otra version de la misma serie. editarEquipo/eliminarEquipo
    resuelven el id EXCLUSIVAMENTE via
    `self.table.item(self.table.currentRow(), 0).data(Qt.UserRole)` -- este
    test fija que esa lectura por fila da el id correcto y distinto para
    cada version, no importa el orden de insercion ni cuantas compartan
    serie."""

    def test_cada_fila_visible_resuelve_su_propio_id_no_el_de_otra_version(
            self, app, bd_temporal):
        _insertar_equipo(bd_temporal, 13, serie="2123", calibr_fact=0.05451,
                         fecha_calibr="05/02/2024", activo=1, vigente=1,
                         **_CAMPOS_BASE)
        _insertar_equipo(bd_temporal, 67, serie="2123", calibr_fact=0.05451,
                         fecha_calibr="05/02/2024", activo=0, vigente=0,
                         **_CAMPOS_BASE)

        obj = _config_pelado()
        obj.cargartabla()

        assert obj.table.rowCount() == 2
        ids_por_fila = [obj.table.item(fila, 0).data(Qt.UserRole)
                        for fila in range(obj.table.rowCount())]
        # Ninguna fila puede resolver el id de la OTRA version de la
        # misma serie -- son valores exclusivos y correctos por fila.
        assert set(ids_por_fila) == {13, 67}
        assert ids_por_fila[0] != ids_por_fila[1]
        for fila in range(obj.table.rowCount()):
            obj.table.setCurrentCell(fila, 0)
            id_seleccionado = obj.table.item(
                obj.table.currentRow(), 0).data(Qt.UserRole)
            assert id_seleccionado == ids_por_fila[fila]


@pytest.mark.skipif(not os.path.exists(DB),
                    reason="BD de produccion no disponible en este entorno")
class TestConteoContraProduccionReal:
    """F9: verificacion adicional obligatoria -- conteo antes/despues
    contra la BD real en modo lectura. De 15 a 39, ninguna fila falta."""

    def test_el_total_de_equipos_en_produccion_es_39(self):
        import sqlite3
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            total = con.execute("SELECT COUNT(*) FROM equipos").fetchone()[0]
        finally:
            con.close()
        assert total == 39

    def test_las_5_filas_activas_antes_invisibles_existen_en_produccion(self):
        """ids 7, 13, 16, 17, 18: activas, pero ocultas por
        `MAX(id) GROUP BY serie` antes del fix. Documentado en el plan
        (S3/G8) -- si este test falla, la evidencia con la que se disenio
        G8 quedo desactualizada y hay que re-medir, no ignorarlo."""
        import sqlite3
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            activas = {r[0] for r in con.execute(
                "SELECT id FROM equipos WHERE activo=1")}
        finally:
            con.close()
        for id_esperado in (7, 13, 16, 17, 18):
            assert id_esperado in activas
