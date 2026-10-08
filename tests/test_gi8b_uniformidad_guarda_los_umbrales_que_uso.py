"""GI.8b (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, anotada por GI.1): `uniformidad_global` guarda los umbrales con que SE JUZGO la uniformidad.

Antes `catphan_db.mapear_uniformidad` guardaba tres CONSTANTES (`ui_threshold_pct = 2.0`, `inu_threshold_pct = 2.0`, `hu_tolerancia = 40.0`), anteriores a `G.3`, aunque `uniformidad()` recibe esos tres
umbrales como argumentos obligatorios y la pantalla se los pasa segun el equipo: el tomografo corre con 5.0 y el Halcyon y el iX no tienen tolerancia de HU, y «Ver tabla» y la exportacion decian 40 en los tres.
Los veredictos no cambian; lo que miente es el criterio escrito junto al veredicto. Regla del proyecto: la copia guardada manda, y un veredicto sin el umbral contra el que se juzgo no se puede auditar.

Lo que fija esta prueba:
  1. el analisis devuelve en `resultados["Uniformidad"]` los tres umbrales que recibio (y los veredictos se calculan con ellos);
  2. el mapeador lleva a la fila esos y no constantes; un resultado que no los trae (uno reconstruido) queda en `None`, nunca en 2.0 / 2.0 / 40.0;
  3. con el escritor real y el analisis REAL de una serie por equipo, la fila guarda lo que la pantalla le paso al analisis (tomografo: 2.0 / 2.0 / 5.0; Halcyon e iX: 2.0 / 2.0 / 40.0; un equipo sin regla de uniformidad: tolerancia de HU `None`, que el escritor guarda como «No disponible»).
  4. el escritor dice «No disponible» (las columnas son NOT NULL) donde el analisis no trajo el umbral -`None`: un equipo sin regla de uniformidad o un resultado reconstruido-: nunca una
     constante (la mutacion MB8 sobrevivia hasta que se probo esa rama: las tres series reales tienen tolerancia de HU);
  4b. cada umbral va a SU columna y cada veredicto se calcula con SU umbral (valores asimetricos y con decimales: un cruce o un redondeo se nota);
  5. «Ver tabla» de Uniformidad Global -lo unico que ve el fisico de estos tres numeros- muestra los umbrales guardados.
Sobre el rojo contra el codigo anterior: las tres pruebas del analisis y de la serie real caen por su aserto; las del mapeador con claves ausentes caen porque devolvia 2.0 / 2.0 / 40.0.
"""
import warnings

import pytest

from analisisImagenes.catphan import criterios
from data.ManejoDatos.catphan_TAC import catphan_db as C
from test_g3_criterios_por_equipo import _entrada_real
from test_gi1_guardado_claves_del_analisis import (  # noqa: F401  (helpers y fixtures de GI.1: una sola definicion de la forma del productor)
    _crear_control, _guardar, _id_prueba, _leer, _resultado_uniformidad, _una_fila, app, base_real, bd_nueva)


def _uniformidad(clave, **umbrales):
    from analisisImagenes.Analisis_Catphan_TAC import uniformidad
    c255, hu, tam_px = _entrada_real(clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return uniformidad(c255, hu, tam_px, visualizar=False, **umbrales)


class TestElAnalisisDiceConQueUmbralesJuzgo:

    def test_devuelve_los_tres_umbrales_que_recibio(self):
        """Con mas de un decimal y los tres DISTINTOS entre si: redondearlos o cruzarlos se nota (revision de GI.8b, PR-4)."""
        u = _uniformidad("TOMOGRAFO", hu_tolerancia=12.375, ui_threshold_pct=3.55, inu_threshold_pct=4.45)["Uniformidad"]
        assert (u["ui_threshold_pct"], u["inu_threshold_pct"], u["hu_tolerancia"]) == (3.55, 4.45, 12.375)

    def test_sin_tolerancia_de_hu_devuelve_none_y_no_una_constante(self):
        u = _uniformidad("TOMOGRAFO", hu_tolerancia=None, ui_threshold_pct=2.0, inu_threshold_pct=2.0)["Uniformidad"]
        assert u["hu_tolerancia"] is None

    def test_cada_veredicto_se_calcula_con_su_propio_umbral(self):
        """Umbrales ASIMETRICOS: el de UI decide `pasa_ui` y el de INU decide `pasa_inu` (con ui == inu un cruce entre ellos no se nota; revision de GI.8b, PR-3)."""
        solo_inu_cumple = _uniformidad("TOMOGRAFO", hu_tolerancia=None, ui_threshold_pct=0.0, inu_threshold_pct=1000.0)["Uniformidad"]
        solo_ui_cumple = _uniformidad("TOMOGRAFO", hu_tolerancia=None, ui_threshold_pct=1000.0, inu_threshold_pct=0.0)["Uniformidad"]
        assert (solo_inu_cumple["pasa_ui"], solo_inu_cumple["pasa_inu"]) == (False, True)
        assert (solo_ui_cumple["pasa_ui"], solo_ui_cumple["pasa_inu"]) == (True, False)

    def test_los_veredictos_se_calculan_con_los_umbrales_que_dice(self):
        """El umbral que se guarda es el que decidio: con uno imposible de cumplir el veredicto es «no pasa», con uno holgado es «pasa»."""
        estricto = _uniformidad("TOMOGRAFO", hu_tolerancia=None, ui_threshold_pct=0.0, inu_threshold_pct=0.0)["Uniformidad"]
        holgado = _uniformidad("TOMOGRAFO", hu_tolerancia=None, ui_threshold_pct=1000.0, inu_threshold_pct=1000.0)["Uniformidad"]
        assert (estricto["ui_threshold_pct"], estricto["pasa_ui"], estricto["pasa_inu"]) == (0.0, False, False)
        assert (holgado["inu_threshold_pct"], holgado["pasa_ui"], holgado["pasa_inu"]) == (1000.0, True, True)


class TestElMapeadorLlevaLosUmbralesDelAnalisis:

    def test_lleva_los_del_resultado(self):
        datos, _ = C.mapear_uniformidad({"Uniformidad": {"max_diferencia": 1.0, "ui_threshold_pct": 3.5, "inu_threshold_pct": 4.5, "hu_tolerancia": 12.5}})
        assert (datos["ui_threshold_pct"], datos["inu_threshold_pct"], datos["hu_tolerancia"]) == (3.5, 4.5, 12.5)

    @pytest.mark.parametrize("resultado", [{"max_diferencia": 1.0}, {"max_diferencia": 1.0, "hu_tolerancia": None}])
    def test_un_resultado_sin_umbrales_queda_en_none(self, resultado):
        """Un resultado reconstruido de la base no los trae: ninguna constante inventada (antes 2.0 / 2.0 / 40.0)."""
        datos, _ = C.mapear_uniformidad({"Uniformidad": resultado})
        assert datos["ui_threshold_pct"] is None and datos["inu_threshold_pct"] is None and datos["hu_tolerancia"] is None

    def test_las_constantes_de_antes_no_quedan_en_el_mapeador(self):
        import ast
        import inspect
        arbol = ast.parse(inspect.getsource(C.mapear_uniformidad).lstrip())
        numeros = {n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, float) and n.value in (2.0, 40.0)}
        assert numeros == set(), f"el mapeador vuelve a escribir un umbral como constante: {numeros}"


def test_real_la_fila_guarda_los_umbrales_con_que_corrio_el_analisis(base_real):
    esperado = criterios.parametros_de_analisis("uniformidad", base_real.equipo)           # lo que la pantalla le pasa al analisis
    u = base_real.salidas["uniformidad"]["Uniformidad"]
    assert (u["ui_threshold_pct"], u["inu_threshold_pct"], u["hu_tolerancia"]) == (esperado["ui_threshold_pct"], esperado["inu_threshold_pct"], esperado["hu_tolerancia"])
    con = _leer(base_real.ruta)
    try:
        fila = _una_fila(con, "uniformidad_global", _id_prueba(con, base_real.sesion, "uniformidad"))
        assert fila["ui_threshold_pct"] == esperado["ui_threshold_pct"] and fila["inu_threshold_pct"] == esperado["inu_threshold_pct"]
        assert fila["hu_tolerancia"] == (esperado["hu_tolerancia"] if esperado["hu_tolerancia"] is not None else "No disponible")
    finally:
        con.close()


class TestElEscritorDiceNoDisponibleDondeNoHuboUmbral:

    def _fila_guardada(self, ruta, resultado):
        sesion = _crear_control(ruta)
        assert _guardar(sesion, {"uniformidad": resultado}) == sesion
        con = _leer(ruta)
        try:
            return dict(_una_fila(con, "uniformidad_global", _id_prueba(con, sesion, "uniformidad")))
        finally:
            con.close()

    def test_una_tolerancia_de_hu_none_se_guarda_como_no_disponible_y_los_otros_dos_umbrales_se_guardan(self, bd_nueva):
        resultado = _resultado_uniformidad(True, True)
        resultado["Uniformidad"]["hu_tolerancia"] = None                         # un equipo sin regla de uniformidad
        fila = self._fila_guardada(bd_nueva, resultado)
        assert fila["hu_tolerancia"] == "No disponible"
        assert (fila["ui_threshold_pct"], fila["inu_threshold_pct"]) == (3.5, 4.5)

    def test_un_resultado_sin_ninguna_de_las_tres_claves_no_inventa_una_constante(self, bd_nueva):
        resultado = _resultado_uniformidad(True, True)
        for clave in ("ui_threshold_pct", "inu_threshold_pct", "hu_tolerancia"):
            resultado["Uniformidad"].pop(clave)                                   # como uno reconstruido de una base anterior
        fila = self._fila_guardada(bd_nueva, resultado)
        assert (fila["ui_threshold_pct"], fila["inu_threshold_pct"], fila["hu_tolerancia"]) == ("No disponible",) * 3, "ni 2.0 ni 40.0: lo que el analisis no dijo no se inventa"

    @pytest.mark.parametrize("ui, inu, hu", [(3.5, 4.5, 12.5), (1.25, 7.75, 33.0)])
    def test_cada_umbral_se_guarda_en_su_propia_columna(self, bd_nueva, ui, inu, hu):
        """Tres valores DISTINTOS entre si por el escritor real: cruzar dos columnas del INSERT se nota (revision de GI.8b, PR-2; las series reales tienen ui == inu == 2.0)."""
        resultado = _resultado_uniformidad(True, True)
        resultado["Uniformidad"].update({"ui_threshold_pct": ui, "inu_threshold_pct": inu, "hu_tolerancia": hu})
        fila = self._fila_guardada(bd_nueva, resultado)
        assert (fila["ui_threshold_pct"], fila["inu_threshold_pct"], fila["hu_tolerancia"]) == (ui, inu, hu)

    def test_ver_tabla_muestra_los_umbrales_guardados(self, bd_nueva, monkeypatch):
        """Lo unico que ve el fisico de estos tres numeros es «Ver tabla» de Uniformidad Global (el lector y el PDF no los traen)."""
        import data.ManejoDatos.load as load_mod
        from PyQt5.QtWidgets import QDialog, QTableWidget
        resultado = _resultado_uniformidad(True, True)
        sesion = _crear_control(bd_nueva)
        assert _guardar(sesion, {"uniformidad": resultado}) == sesion
        capturados = []
        monkeypatch.setattr(QDialog, "exec_", lambda self: capturados.append(self) or 0)
        load_mod.mostrar_uniformidad_global(None, sesion)
        tabla = capturados[0].findChild(QTableWidget)
        fila = {tabla.horizontalHeaderItem(c).text(): tabla.item(0, c).text() for c in range(tabla.columnCount())}
        assert (fila["UI Threshold %"], fila["INU Threshold %"], fila["HU Tolerancia"]) == ("3.5", "4.5", "12.5")
