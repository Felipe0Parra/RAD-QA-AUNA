"""INSERT-audit (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8, prerrequisito
de W2): auditando todo INSERT que escribe columnas con FK RESTRICT
(id_tipo/id_material/id_region/id_energia) se encontró que los catálogos que
esas FK referencian (`tipos_prueba`, `materiales_ct`, `regiones_uniformidad`,
`energias`) NUNCA se sembraban desde ningún punto del código -- solo se
CREABAN vacíos. Confirmado en código real: una BD nueva creada con
`Conexion()` (el arranque normal de la app) tenía las 4 tablas con 0 filas,
pese a que `mapeo_tipos`/`mapeo_materiales`/`mapeo_regiones`
(`catphan_db.py`) y `energia_ids`/`id_energia=0` (`ix_anual.py`,
`halcyon_*.py`) asumen ids fijos (1-7/1-7/1-5/0-5) ya sembrados. Inofensivo
hoy (FK apagado); bloquearía TODO guardado de CT/Halcyon/anuales de iX en
cuanto se active `PRAGMA foreign_keys=ON` (W2) sobre una BD nueva o traída de
otra sesión.

Estos tests verifican que el arranque ahora siembra los 4 catálogos con
exactamente los valores ya verificados contra la BD de producción real, de
forma idempotente y sin sobreescribir filas ya sembradas/editadas.
"""
import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    yield ruta
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = None
    for sufijo in ("", "-wal", "-shm"):
        if os.path.exists(ruta + sufijo):
            os.remove(ruta + sufijo)


class TestCatalogosSembradosAlArrancarBdNueva:

    def test_tipos_prueba_tiene_las_7_filas_reales(self, bd_temporal):
        Conexion()
        con = Conexion().conectar()
        filas = con.execute(
            "SELECT id_tipo, nombre_prueba FROM tipos_prueba ORDER BY id_tipo").fetchall()
        con.close()
        assert filas == [
            (1, "ESPESOR_CORTE"), (2, "TAMAÑO_PIXEL"),
            (3, "RESOLUCION_CONTRASTE"), (4, "RESOLUCION_ESPACIAL"),
            (5, "VALORES_CT"), (6, "LINEALIDAD_CT"), (7, "UNIFORMIDAD_RUIDO"),
        ]

    def test_materiales_ct_tiene_las_7_filas_reales(self, bd_temporal):
        Conexion()
        con = Conexion().conectar()
        filas = con.execute(
            "SELECT id_material, nombre_material FROM materiales_ct ORDER BY id_material").fetchall()
        con.close()
        assert filas == [
            (1, "Aire"), (2, "PMP"), (3, "LDPE"), (4, "Poliestireno"),
            (5, "Acrilico"), (6, "Delrin"), (7, "Teflon"),
        ]

    def test_regiones_uniformidad_tiene_las_5_filas_reales(self, bd_temporal):
        Conexion()
        con = Conexion().conectar()
        filas = con.execute(
            "SELECT id_region, nombre_region, angulo FROM regiones_uniformidad "
            "ORDER BY id_region").fetchall()
        con.close()
        assert filas == [
            (1, "Centro", 0), (2, "Superior", 270), (3, "Derecha", 0),
            (4, "Inferior", 90), (5, "Izquierda", 180),
        ]

    def test_energias_tiene_las_6_filas_reales_con_id_0(self, bd_temporal):
        """energia_ids en ix_anual.py mapea "6 MV" -> 0 -- el id empieza en
        0, no en 1 (AUTOINCREMENT normal habría empezado en 1)."""
        Conexion()
        con = Conexion().conectar()
        filas = con.execute("SELECT id, energia FROM energias ORDER BY id").fetchall()
        con.close()
        assert filas == [
            (0, "6 MV"), (1, "15 MV"), (2, "6 MeV"),
            (3, "9 MeV"), (4, "12 MeV"), (5, "15 MeV"),
        ]


class TestNoSobreescribeCatalogosYaSembrados:

    def test_no_pisa_una_fila_editada_a_mano(self, bd_temporal):
        """INSERT OR IGNORE: si alguien ya editó el texto de una fila (o una
        BD vieja ya la tenía con otro valor legítimo), reabrir la app no
        debe revertirlo."""
        Conexion()
        con = Conexion().conectar()
        con.execute(
            "UPDATE materiales_ct SET nombre_material = 'Poliestireno (editado)' "
            "WHERE id_material = 4")
        con.commit()
        con.close()

        Conexion._instance.con.close()
        Conexion._instance = None
        Conexion()  # simula reabrir la app

        con = Conexion().conectar()
        valor = con.execute(
            "SELECT nombre_material FROM materiales_ct WHERE id_material = 4").fetchone()[0]
        con.close()
        assert valor == "Poliestireno (editado)"

    def test_es_idempotente_no_duplica_filas(self, bd_temporal):
        Conexion()
        for _ in range(3):
            Conexion._instance.con.close()
            Conexion._instance = None
            Conexion()

        con = Conexion().conectar()
        n_tipos = con.execute("SELECT COUNT(*) FROM tipos_prueba").fetchone()[0]
        n_materiales = con.execute("SELECT COUNT(*) FROM materiales_ct").fetchone()[0]
        n_regiones = con.execute("SELECT COUNT(*) FROM regiones_uniformidad").fetchone()[0]
        n_energias = con.execute("SELECT COUNT(*) FROM energias").fetchone()[0]
        con.close()
        assert (n_tipos, n_materiales, n_regiones, n_energias) == (7, 7, 5, 6)


class TestBdViejaConCatalogosVaciosQuedaSembrada:

    def test_bd_con_tablas_creadas_pero_vacias_se_siembra_al_reabrir(self, bd_temporal):
        """Reproduce el estado real encontrado (una BD con las tablas ya
        creadas -- p.ej. por una versión anterior de la app -- pero sin
        ninguna fila sembrada, porque nada en el código las poblaba)."""
        con = sqlite3.connect(bd_temporal)
        con.execute("CREATE TABLE tipos_prueba (id_tipo INTEGER PRIMARY KEY, "
                     "nombre_prueba VARCHAR(100) NOT NULL UNIQUE, descripcion TEXT, "
                     "activo BOOLEAN DEFAULT 1)")
        con.commit()
        con.close()

        Conexion()

        con = Conexion().conectar()
        n = con.execute("SELECT COUNT(*) FROM tipos_prueba").fetchone()[0]
        con.close()
        assert n == 7
