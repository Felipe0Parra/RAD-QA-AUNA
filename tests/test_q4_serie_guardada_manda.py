"""Q.4 (PLAN_EQUIPOS_BORRADO_Y_VIGENCIA_10-09.md SS4-bis): el reporte de la
calculadora sobrescribia "Numero_serie" INCONDICIONALMENTE desde el
catalogo -- si `equipo_id` ya no resolvia, borraba la fila entera, incluso
cuando la copia guardada (C1, 11-08, PLAN_REPARACION_MENSUAL_Y_HALCYON_
11-08.md) ya tenia la serie REAL, no el id.

Los 4 casos de SS0.10 del plan, la matriz completa que separa "post-C1"
(Numero_serie != equipo_id, es la serie real) de "pre-C1" (Numero_serie
== equipo_id, el id crudo -- Z3/F1):

  (a) post-C1 + equipo BORRADO    -> debe SALIR la serie guardada  [rojo hoy]
  (b) post-C1 + equipo presente   -> sale la del catalogo (sin cambio)
  (c) pre-C1  + equipo presente   -> sale la del catalogo (sin cambio)
  (d) pre-C1  + equipo BORRADO    -> la fila se omite (sin cambio, un id
                                     crudo no significa nada para el fisico)

La guarda que distingue (b)/(c) de la version "no resuelve" es
`str(numero_serie) != str(equipo_id)`: antes de C1 esa columna guardaba
EXACTAMENTE el mismo valor que equipo_id (verificado en SS0.10: ninguna de
las 13 series reales del catalogo coincide con ningun id existente).

Coincide con TestZ3NoTocaDatos ya existente en test_z3_reporte_serie_real.py
(que este cambio no debe romper): esos tests fijan (b), (c) sin equipo_id
(caso legacy real, Numero_serie=None) y la no-mutacion del dict.
"""
import ast
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

# Import circular (dialogs.py:663 importa generar_reporte_calibracion de
# vuelta) -- dialogs primero, igual que hicieron las mediciones del plan.
import ui.paginasGuia.dialogs as dialogs_mod  # noqa: F401
import services.equipos_service as equipos_service_mod
from models.PDF.reporte_calculadora_dos import datos_a_dataframe

EQUIPO_1822 = {"id": 81, "equip_type": "Cámara de ionización",
               "model": "N31010", "serie": "1822"}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _serie_en_reporte(datos):
    df = datos_a_dataframe(datos)
    fila = df[df[""] == "Numero_serie"]
    if len(fila) == 0:
        return None
    return fila["Valores"].iloc[0]


class TestLaSerieGuardadaMandaCuandoElCatalogoNoResuelve:

    def test_a_post_c1_equipo_borrado_sale_la_serie_guardada(self, app, monkeypatch):
        """El caso que hoy falla: la copia (C1) ya tenia la serie real
        ('1822'), el equipo se borro del catalogo (DA-74) -- antes de Q.4
        esto borraba la fila entera, tirando un dato correcto."""
        monkeypatch.setattr(
            equipos_service_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: None))

        datos = {"Fecha": "06/08/2026", "equipo_id": 81, "Numero_serie": "1822"}
        assert _serie_en_reporte(datos) == "1822"

    def test_b_post_c1_equipo_presente_sale_la_del_catalogo(self, app, monkeypatch):
        monkeypatch.setattr(
            equipos_service_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: EQUIPO_1822 if i == 81 else None))

        datos = {"Fecha": "06/08/2026", "equipo_id": 81, "Numero_serie": "1822"}
        assert _serie_en_reporte(datos) == "1822"

    def test_c_pre_c1_equipo_presente_resuelve_del_catalogo(self, app, monkeypatch):
        """Numero_serie == equipo_id (formato F1, anterior a C1): el id
        crudo se descarta a favor de la serie real del catalogo."""
        monkeypatch.setattr(
            equipos_service_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: EQUIPO_1822 if i == 81 else None))

        datos = {"Fecha": "06/08/2026", "equipo_id": 81, "Numero_serie": "81"}
        assert _serie_en_reporte(datos) == "1822"

    def test_d_pre_c1_equipo_borrado_la_fila_se_omite(self, app, monkeypatch):
        """Un id crudo sin catalogo que lo resuelva no significa nada para
        el fisico -- se sigue omitiendo, como siempre."""
        monkeypatch.setattr(
            equipos_service_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: None))

        datos = {"Fecha": "06/08/2026", "equipo_id": 9999, "Numero_serie": "9999"}
        assert _serie_en_reporte(datos) is None

    def test_sin_numero_serie_no_revienta(self, app, monkeypatch):
        """Compuerta: un dict sin la clave 'Numero_serie' (algunos
        llamadores no la incluyen) no debe alcanzar la guarda nueva."""
        monkeypatch.setattr(
            equipos_service_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: None))

        datos = {"Fecha": "06/08/2026"}
        df = datos_a_dataframe(datos)  # no debe lanzar
        assert (df[""] == "Numero_serie").sum() == 0


class TestCierreDeClase:
    """Q.4 tiene que cerrar la clase entera, no solo el caso medido: censo
    AST de que `EquiposService.obtener_por_id` se llama desde exactamente
    UN sitio de produccion en models/ -- si un segundo reporte nace
    re-resolviendo contra el catalogo, este test lo señala."""

    ROOT = Path(__file__).resolve().parent.parent
    EXCLUDE_DIRS = {".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache"}

    def _archivos_models(self):
        models_dir = self.ROOT / "models"
        for path in sorted(models_dir.rglob("*.py")):
            rel = path.relative_to(self.ROOT)
            if any(parte in self.EXCLUDE_DIRS for parte in rel.parts):
                continue
            yield rel, path

    def _llama_a_obtener_por_id(self, tree):
        llamadas = []
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Call):
                func = nodo.func
                nombre = None
                if isinstance(func, ast.Attribute):
                    nombre = func.attr
                elif isinstance(func, ast.Name):
                    nombre = func.id
                if nombre == "obtener_por_id":
                    llamadas.append(nodo.lineno)
        return llamadas

    def test_un_solo_sitio_en_models_resuelve_contra_el_catalogo(self):
        # Deliberadamente NO se fija el numero de linea (Trampa 5, CLAUDE.md):
        # la garantia es "un solo archivo, una sola llamada", no una linea
        # exacta que cualquier comentario futuro desplazaria sin motivo.
        sitios = []
        for rel, path in self._archivos_models():
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for _linea in self._llama_a_obtener_por_id(tree):
                sitios.append(str(rel))

        assert sitios == ["models/PDF/reporte_calculadora_dos.py"], (
            f"censo de obtener_por_id en models/ cambio: {sitios} -- "
            "si aparecio un segundo sitio, revisar que no reintroduzca "
            "el mismo defecto que Q.4 cerro (borrar una fila del reporte "
            "cuando el catalogo ya no resuelve, aunque haya copia guardada)")
