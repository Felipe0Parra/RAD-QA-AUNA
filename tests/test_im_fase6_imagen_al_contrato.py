"""Fase 6 -- IM4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IM): existe un lector -- `imagen_vigente(ref)` -- que devuelve la imagen del bloque VIGENTE de `preguntas`.

**G.1 (26-10-2026, PLAN_ANALISIS_PELICULAS_08-10.md)**: este archivo probaba cuatro subs de la Fase 6. IM1 (`crear_algo` reemplaza el bloque con `reemplazar_bloque` y hereda el texto vigente), IM2 (la
auditoria dice QUE imagen se guardo) e IM5 (`guardar_analisis_placa600` devuelve `True`/`False`) eran del camino de guardado del analisis mensual VIEJO, que G.1 retira con `crear_algo` y
`guardar_analisis_placa600`: sus 11 pruebas salen con el codigo que fijaban (el motivo de cada una, en `PLAN_ANALISIS_PELICULAS_08-10_anexo/logs/G1/pruebas_retiradas.md`). IM3 nunca tuvo archivo propio
(se probaba en `test_ux1_indicador_proceso.py`, que tambien sale). Lo que NO sale es IM4: `imagen_vigente` se queda (la usan la ventana de E.2 y el visor de la imagen vieja), y su garantia -- devuelve la
imagen de la generacion VIGENTE e ignora las anuladas -- sigue valiendo. Como `crear_algo` ya no existe, la imagen se SIEMBRA por SQL, con la misma forma que dejaba el reemplazo: la generacion anterior
anulada y una fila vigente nueva con su imagen (`test_ignora_las_generaciones_anuladas` sigue teniendo generaciones anuladas de verdad).

Lo que este archivo NO cubre, a proposito:
  - La atomicidad entre la fila de auditoria y la imagen ([[DP-43]], [[DA-64]]): el nuevo guardado de D.1 la cierra para la placa (una fila y una transaccion con su auditoria).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import imagen_vigente


@pytest.fixture(scope="module")
def app():
    instancia = QApplication.instance() or QApplication([])
    yield instancia


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = conexion.con
    con.execute("INSERT INTO users (fullname) VALUES ('fisico de prueba')")
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (952, 'Clinac 600', 'Mensual', '01/06/2026', 'fisico de prueba')")
    con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _guardar_imagen(ruta_db, ref, ruta_archivo):
    """Siembra la imagen por SQL, con la forma que dejaba el reemplazo del bloque (G.1: `crear_algo` ya no existe): la generacion vigente de `ref` se anula y entra una fila vigente nueva con la
    imagen de ese archivo."""
    imagen = open(ruta_archivo, "rb").read()
    con = sqlite3.connect(ruta_db)
    try:
        con.execute("UPDATE preguntas SET activo = 0 WHERE ref = ? AND (activo IS NULL OR activo = 1)", (ref,))
        con.execute("INSERT INTO preguntas (ref, iso_mec, imagen, activo) VALUES (?, 1.0, ?, 1)", (ref, imagen))
        con.commit()
    finally:
        con.close()


class TestIM4ElLectorQueNoExistia:

    def test_devuelve_la_imagen_del_bloque_vigente(self, app, bd_temporal, tmp_path):
        img = tmp_path / "placa.png"
        img.write_bytes(b"la imagen guardada")
        _guardar_imagen(bd_temporal, 952, img)

        assert imagen_vigente(952) == b"la imagen guardada"

    def test_ignora_las_generaciones_anuladas(self, app, bd_temporal, tmp_path):
        """La razón por la que el lector filtra `activo`: tras IM1 hay
        varias generaciones del mismo `ref`, y devolver una histórica
        mostraría al físico una imagen que él ya reemplazó."""
        for nombre in ("vieja", "nueva"):
            img = tmp_path / f"{nombre}.png"
            img.write_bytes(f"imagen {nombre}".encode())
            _guardar_imagen(bd_temporal, 952, img)

        assert imagen_vigente(952) == b"imagen nueva"

    def test_sin_imagen_devuelve_none(self, app, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        con.execute("INSERT INTO preguntas (ref, iso_mec, activo) VALUES (952, 1.0, 1)")
        con.commit()
        con.close()
        assert imagen_vigente(952) is None

    def test_sin_fila_devuelve_none(self, app, bd_temporal):
        assert imagen_vigente(952) is None
