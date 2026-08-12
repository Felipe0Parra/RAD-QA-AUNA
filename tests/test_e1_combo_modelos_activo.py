"""E1 (PLAN_CONOS_MENSUAL_12-08.md §4-E1): `buscarModeloActivo` deja de
esconder modelos cuya serie tiene la fila de id MAS ALTO en `activo=0`.

`buscarModeloActivo` (seiscientos_mensual.py) consultaba:

    SELECT DISTINCT {selected_column} FROM equipos
    WHERE {filter_column} = ? AND activo = 1
    AND id IN (SELECT MAX(id) FROM equipos GROUP BY serie)

El `activo = 1` está en el WHERE exterior, pero la subconsulta
`MAX(id) GROUP BY serie` no lo aplica: si la fila de id más alto de una
serie está `activo=0` (duplicado histórico, patrón H2.6), la serie entera
se cae del combo -- y con ella su modelo, aunque exista otra fila ACTIVA de
esa misma serie con id más bajo.

Es el mismo patrón que F9 (obtenerSeriesConVigencia), H2.10 (braquiterapia)
y G8 (cargartabla) ya eliminaron en todos los demás sitios que leen
`equipos`. Medido contra la BD real: N30013/2123 (id13, activo=1) tapada
por id67 (activo=0); N31014/0453 (id7, activo=1) tapada por id68
(activo=0) -- las dos cámaras que el mensual sigue sin ofrecer en la
sección de Equipos pese a estar activas.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)

DB = "/home/felipepp/Documents/CodigosPython/AUNA_2026_2/BaseDatosQA.db"


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


def _instancia_pelada():
    """PruebaMensual600 pelada -- solo lo que buscarModeloActivo necesita:
    db_manager. Instancia NUEVA por test para que el @lru_cache (que
    incluye `self` en la clave) y `self._model_cache` no arrastren
    resultados de otro caso."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    return obj


class TestModeloYaNoSeEscondePorDuplicadoInactivo:
    """§5.3 caso 1: serie con fila activa de id BAJO + fila activa=0 de id
    ALTO -- el modelo debe aparecer en el combo (rojo sin el fix)."""

    CASOS = [
        (13, 67, "Cámara de ionización", "N30013", "2123"),
        (7, 68, "Cámara de ionización", "N31014", "0453"),
    ]

    def _poblar(self, ruta_bd, id_bueno, id_duplicado, equip_type, model, serie):
        _insertar_equipo(ruta_bd, id_bueno, equip_type=equip_type, model=model,
                         serie=serie, calibr_fact=1.0, fecha_calibr="05/02/2024",
                         activo=1, vigente=1)
        _insertar_equipo(ruta_bd, id_duplicado, equip_type=equip_type, model=model,
                         serie=serie, calibr_fact=99.0, fecha_calibr="01/01/2025",
                         activo=0, vigente=0)

    @pytest.mark.parametrize("caso", CASOS, ids=["N30013", "N31014"])
    def test_modelo_aparece_en_el_combo(self, app, bd_temporal, caso):
        id_bueno, id_duplicado, equip_type, model, serie = caso
        self._poblar(bd_temporal, id_bueno, id_duplicado, equip_type, model, serie)

        obj = _instancia_pelada()
        modelos = obj.buscarModeloActivo(filter_column='equip_type',
                                          selected_column='model',
                                          valor_ref=equip_type)
        assert model in modelos, (
            f"{model} no aparece pese a tener una fila activa (id{id_bueno}): "
            f"{modelos}")


class TestNingunModeloDesaparece:
    """§5.3 caso 2: comparación de CONJUNTOS antes/después del fix (mismo
    método que validó F9) -- levantar el colapso solo puede AÑADIR
    modelos, nunca quitar ninguno."""

    def test_conjunto_sin_colapso_incluye_al_conjunto_colapsado(self, app, bd_temporal):
        # Tres series del mismo equip_type: una sin duplicado (siempre
        # visible), y dos con duplicado activo=0 de id más alto (antes
        # invisibles).
        _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                         model="ModeloSinDuplicado", serie="S1",
                         calibr_fact=1.0, fecha_calibr="01/01/2020",
                         activo=1, vigente=1)
        _insertar_equipo(bd_temporal, 13, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=1.0,
                         fecha_calibr="05/02/2024", activo=1, vigente=1)
        _insertar_equipo(bd_temporal, 67, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=99.0,
                         fecha_calibr="01/01/2025", activo=0, vigente=0)
        _insertar_equipo(bd_temporal, 7, equip_type="Cámara de ionización",
                         model="N31014", serie="0453", calibr_fact=1.0,
                         fecha_calibr="07/02/2024", activo=1, vigente=1)
        _insertar_equipo(bd_temporal, 68, equip_type="Cámara de ionización",
                         model="N31014", serie="0453", calibr_fact=99.0,
                         fecha_calibr="01/01/2025", activo=0, vigente=0)

        obj = _instancia_pelada()
        modelos = obj.buscarModeloActivo(filter_column='equip_type',
                                          selected_column='model',
                                          valor_ref="Cámara de ionización")
        # Lo que el patrón COLAPSANTE (MAX(id) GROUP BY serie) sí veía:
        # solo la serie sin duplicado, porque en las otras dos el id más
        # alto es activo=0.
        modelos_colapsados = {"ModeloSinDuplicado"}
        assert modelos_colapsados <= modelos
        assert modelos == {"ModeloSinDuplicado", "N30013", "N31014"}


@pytest.mark.skipif(not os.path.exists(DB),
                    reason="BD de produccion no disponible en este entorno")
class TestContraProduccionReal:
    """§5.3 caso 3: los 5 modelos de cámara de ionización esperados en la
    BD real (N30013, N31010, N31014, N31022, N34001) -- antes del fix solo
    aparecían 3 (N31010, N31022, N34001); N30013 y N31014 quedaban tapados
    por sus duplicados `activo=0` de id más alto."""

    def test_los_5_modelos_de_camara_de_ionizacion(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            rows = con.execute("""
                SELECT DISTINCT model FROM equipos
                WHERE equip_type = 'Cámara de ionización' AND activo = 1
                ORDER BY model
            """).fetchall()
        finally:
            con.close()
        modelos = {r[0] for r in rows}
        assert modelos == {"N30013", "N31010", "N31014", "N31022", "N34001"}
