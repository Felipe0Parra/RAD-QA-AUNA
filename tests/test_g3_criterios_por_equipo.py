"""G.3 (PLAN_HANDOFF_IMAGENES_22-09.md §7bis): cada prueba de imagen juzga con el criterio de SU equipo.

CAUSA. **[código + medido]** Los criterios eran constantes escritas en la pantalla e iguales para tres equipos cuyo
ruido va de 4.95 a 17.63 HU: `cnr_lim=1.0`, `visibilidad_lim=0.1`, `>= 4` de 6 ROI, `hu_tolerancia=40`, umbrales de UI e
INU de 2 %, rangos nominales de un CT calibrado. La matriz por equipo existía (`perfiles.py`) y nadie la leía. Lo que se
archivaba era un booleano (`pasa_*`) sin decir contra qué regla ni de qué fuente.

Lo que este archivo garantiza:

  1. LA REGLA DEL EQUIPO DECIDE -- la misma medición da veredictos distintos según el equipo, y cambiar la tolerancia
     del perfil cambia el veredicto Y lo que la pantalla le pasa a la función de análisis.
  2. SIN LÍNEA BASE NO HAY VEREDICTO -- ninguna regla `linea_base_*` devuelve "No cumple" sin línea base; con ella, sí.
  3. NO SE INVENTAN EQUIVALENCIAS -- lo que la función de la app no mide igual que la regla (geometría, espesor, bajo
     contraste, resolución espacial) queda "Criterio pendiente de métrica" y dice por qué; nunca "Cumple".
  4. NINGÚN UMBRAL DE JUICIO EN LA PANTALLA -- tripwire por AST derivado de las firmas: si reaparece un literal en una
     llamada a las funciones de análisis, la prueba lo nombra.
  5. LA PANTALLA LO MUESTRA Y LO GUARDA -- criterio, fuente y veredicto en pantalla; `pruebas.criterio_veredicto`
     (aditiva, idempotente, NULL histórico) y el informe PDF imprime LO ARCHIVADO (§12.4: no se recalcula).
  6. SERIES REALES -- el veredicto de uniformidad sobre las cinco series del corpus con la regla de cada equipo.
"""
import ast
import copy
import inspect
import json
import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from PyQt5.QtWidgets import QLabel

import data.ManejoDatos.conection as conection_mod
from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401  (fixtures)
from _informe_imagenes import avisos, bd_copia, generar, paginas  # noqa: F401  (fixtures)
from analisisImagenes.catphan import criterios, perfiles
from analisisImagenes.catphan.criterios import (
    CATEGORIA_A_PRUEBAS, CUMPLE, ESTADO_PENDIENTE, ESTADO_SIN_PERFIL, EQUIVALENCIAS, INFORMATIVO, MOTIVO_PENDIENTE,
    NO_APLICA, NO_CUMPLE, PARAMETROS_HEREDADOS, SIN_LINEA_BASE, Juicio, juzgar, parametros_de_analisis, texto_html)
from analisisImagenes.catphan.perfiles import PERFILES, PRUEBAS
from data.ManejoDatos.catphan_TAC.catphan_db import guardar_prueba_completa_catphan

RAIZ = Path(__file__).resolve().parent.parent
PANTALLA = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "tac_mensual.py"
EQUIPOS = ("Tomógrafo", "Clinac ix", "Halcyon")
SIMBOLOS = "✓✗✔✘⚠"


# ---------------------------------------------------------------------------
# Mediciones sintéticas con la forma exacta que devuelven las funciones de la app
# ---------------------------------------------------------------------------

def uniformidad_con(max_dif_hu, centro=0.0, ruido=5.0):
    """Resultado de `uniformidad()`: cuatro ROI periféricos a `centro`, uno de ellos `max_dif_hu` por encima. Los
    periféricos llevan OTRO ruido que el centro (el que se juzga es el del ROI central)."""
    return {"Centro": {"promedio_hu": centro, "desviacion": ruido},
            "Arriba": {"promedio_hu": centro + max_dif_hu, "desviacion": ruido * 3},
            "Abajo": {"promedio_hu": centro - max_dif_hu / 2, "desviacion": ruido * 3},
            "Izquierda": {"promedio_hu": centro, "desviacion": ruido * 3},
            "Derecha": {"promedio_hu": centro + max_dif_hu / 4, "desviacion": ruido * 3},
            "Uniformidad": {"max_diferencia": max_dif_hu, "pasa_global": True}}


MATERIALES = ("Aire", "PMP", "LDPE", "Poliestireno", "Acrílico", "Delrin", "Teflón")
HU_TOMOGRAFO = (-999.1, -186.0, -94.3, -36.5, 122.0, 322.8, 917.3)


def valores_ct_con(hu):
    return [{"material": m, "promedio_hu": v, "std_hu": 5.0, "rango_hu": (0, 0)} for m, v in zip(MATERIALES, hu)]


def por_prueba(juicios):
    return {j.prueba: j for j in juicios}


def estados(equipo, categoria, resultados, **kw):
    return {j.metrica: j.estado for j in juzgar(equipo, categoria, resultados, **kw)}


# ---------------------------------------------------------------------------
# 1. LA REGLA DEL EQUIPO DECIDE
# ---------------------------------------------------------------------------

def test_la_misma_medicion_da_veredicto_distinto_segun_el_equipo():
    """10 HU de diferencia con el centro: el tomógrafo (5 HU, TG-66) no cumple; el Halcyon y el iX (40 HU) sí."""
    res = uniformidad_con(10.0)
    veredictos = {e: por_prueba(juzgar(e, "uniformidad", res))["uniformidad"].estado for e in EQUIPOS}
    assert veredictos == {"Tomógrafo": NO_CUMPLE, "Clinac ix": CUMPLE, "Halcyon": CUMPLE}


def test_la_uniformidad_mide_la_diferencia_en_valor_absoluto_y_el_ruido_es_el_del_centro():
    """Una periferia solo POR DEBAJO del centro (cupping) también cuenta: |ROI - centro|."""
    res = {"Centro": {"promedio_hu": 100.0, "desviacion": 4.0},
           "Arriba": {"promedio_hu": 90.0, "desviacion": 9.0}, "Abajo": {"promedio_hu": 95.0, "desviacion": 9.0},
           "Izquierda": {"promedio_hu": 98.0, "desviacion": 9.0}, "Derecha": {"promedio_hu": 97.0, "desviacion": 9.0}}
    assert criterios.unif_max_dif_hu(res) == pytest.approx(10.0)
    assert criterios.ruido_centro_hu(res) == pytest.approx(4.0)
    assert por_prueba(juzgar("Tomógrafo", "uniformidad", res))["uniformidad"].estado == NO_CUMPLE


def test_cada_veredicto_lleva_la_fuente_y_la_firmeza_de_su_regla():
    for equipo in EQUIPOS:
        j = por_prueba(juzgar(equipo, "uniformidad", uniformidad_con(1.0)))["uniformidad"]
        regla = PERFILES[equipo].reglas["uniformidad"]
        assert j.fuente == regla.fuente and j.estado_regla == regla.estado
        assert j.estado_regla in ("norma", "propuesta", "confirmada")
        assert regla.fuente in criterios.texto_fuente(j) and regla.estado in criterios.texto_fuente(j)


@pytest.mark.parametrize("equipo, tolerancia", [("Tomógrafo", 5.0), ("Clinac ix", 40.0), ("Halcyon", 40.0)])
def test_el_limite_de_la_regla_es_inclusivo(equipo, tolerancia):
    assert por_prueba(juzgar(equipo, "uniformidad", uniformidad_con(tolerancia)))["uniformidad"].estado == CUMPLE
    assert por_prueba(juzgar(equipo, "uniformidad", uniformidad_con(tolerancia + 0.01)))["uniformidad"].estado == NO_CUMPLE


def test_cambiar_la_tolerancia_del_perfil_cambia_el_veredicto_y_lo_que_recibe_la_funcion(monkeypatch):
    """Verificación (b) del plan: el valor vive en `perfiles.py`; se cambia ahí y todo lo demás lo sigue."""
    res = uniformidad_con(10.0)
    assert por_prueba(juzgar("Tomógrafo", "uniformidad", res))["uniformidad"].estado == NO_CUMPLE
    assert parametros_de_analisis("uniformidad", "Tomógrafo")["hu_tolerancia"] == 5.0

    regla = copy.copy(PERFILES["Tomógrafo"].reglas["uniformidad"])
    regla.tolerancia = 20.0
    monkeypatch.setitem(PERFILES["Tomógrafo"].reglas, "uniformidad", regla)

    j = por_prueba(juzgar("Tomógrafo", "uniformidad", res))["uniformidad"]
    assert j.estado == CUMPLE and "20" in j.criterio
    assert parametros_de_analisis("uniformidad", "Tomógrafo")["hu_tolerancia"] == 20.0


def test_los_parametros_de_medicion_heredados_viven_en_un_solo_sitio_y_no_son_veredicto():
    assert PARAMETROS_HEREDADOS["resolucion_contraste"] == {"cnr_lim": 1.0, "visibilidad_lim": 0.1, "min_rois_visibles": 4}
    assert set(PARAMETROS_HEREDADOS["uniformidad"]) == {"ui_threshold_pct", "inu_threshold_pct"}
    for equipo in EQUIPOS:
        assert parametros_de_analisis("resolucion_contraste", equipo) == PARAMETROS_HEREDADOS["resolucion_contraste"]
        p = parametros_de_analisis("uniformidad", equipo)
        assert p["ui_threshold_pct"] == 2.0 and p["inu_threshold_pct"] == 2.0
        assert p["hu_tolerancia"] == PERFILES[equipo].reglas["uniformidad"].tolerancia


def test_un_equipo_sin_regla_de_uniformidad_no_recibe_un_umbral_inventado(monkeypatch):
    regla = copy.copy(PERFILES["Halcyon"].reglas["uniformidad"])
    regla.aplica = "no"
    monkeypatch.setitem(PERFILES["Halcyon"].reglas, "uniformidad", regla)
    assert parametros_de_analisis("uniformidad", "Halcyon")["hu_tolerancia"] is None
    assert parametros_de_analisis("uniformidad", "Equipo desconocido")["hu_tolerancia"] is None


def test_la_linealidad_se_juzga_con_r_al_cuadrado_no_con_r():
    """`linealidad_ct` guarda r (D-30); la regla del tomógrafo pide R² ≥ 0.99. Con r = 0.9949 el viejo `r >= 0.99`
    decía "aceptable" y R² = 0.98981 no cumple."""
    assert estados("Tomógrafo", "linealidad_ct", {"r_squared": 0.995})["linealidad_r2"] == CUMPLE
    assert estados("Tomógrafo", "linealidad_ct", {"r_squared": 0.9949})["linealidad_r2"] == NO_CUMPLE
    j = juzgar("Tomógrafo", "linealidad_ct", {"r_squared": 0.9949})[0]
    assert j.valor == pytest.approx(0.9949 ** 2)


@pytest.mark.parametrize("equipo", ["Clinac ix", "Halcyon"])
def test_la_linealidad_es_informativa_en_los_aceleradores(equipo):
    """TG-142 no la pide para CBCT (P8): el número se ve, pero no hay veredicto."""
    j = juzgar(equipo, "linealidad_ct", {"r_squared": 0.5})[0]
    assert j.estado == INFORMATIVO and not j.es_veredicto


# ---------------------------------------------------------------------------
# 2. SIN LÍNEA BASE NO HAY VEREDICTO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("equipo", EQUIPOS)
def test_sin_linea_base_los_numeros_ct_no_dan_veredicto_ni_con_hu_absurdos(equipo):
    """El iX marca -606 HU en el aire (la escala está corrida ≈ 490 HU): contra los rangos nominales de un CT calibrado
    era "fuera de rango" siempre. Sin línea base, informa el valor y no dice "No cumple"."""
    absurdos = valores_ct_con((-606.0, 205.0, 288.0, 376.0, 599.0, 874.0, 1541.0))
    juicios = juzgar(equipo, "valores_ct", absurdos)
    assert len(juicios) == 7
    assert {j.estado for j in juicios} == {SIN_LINEA_BASE}
    assert all(j.valor is not None for j in juicios)


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_sin_linea_base_el_ruido_no_da_veredicto(equipo):
    j = por_prueba(juzgar(equipo, "uniformidad", uniformidad_con(1.0, ruido=1000.0)))["ruido"]
    assert j.estado == SIN_LINEA_BASE


def test_ninguna_regla_de_linea_base_devuelve_no_cumple_sin_linea_base():
    """Barrido derivado de la matriz: TODA regla `linea_base_*` de TODO equipo, con valores extremos."""
    n = 0
    for equipo, perfil in PERFILES.items():
        for prueba, regla in perfil.reglas.items():
            if regla.aplica != "si" or not str(regla.tipo_tolerancia).startswith("linea_base"):
                continue
            metricas = [None] if not isinstance(regla.tolerancia, dict) else list(regla.tolerancia)
            for metrica in metricas:
                for extremo in (-1e9, 0.0, 1e9):
                    n += 1
                    assert perfiles.evaluar(regla, extremo, metrica=metrica).estado == SIN_LINEA_BASE, (equipo, prueba)
    assert n > 30, "el barrido no encontró las reglas de línea base (ya no es una prueba)"


def test_con_linea_base_si_se_juzga():
    """Cuando exista una línea base (F.1), la misma regla ya emite veredicto."""
    hu = valores_ct_con(HU_TOMOGRAFO)
    base = {"hu_pmp": -180.0, "hu_aire": -1000.0}
    est = estados("Tomógrafo", "valores_ct", hu, linea_base=base)
    assert est["hu_pmp"] == CUMPLE            # |-186.0 - -180| = 6 <= 20
    assert est["hu_aire"] == CUMPLE           # |-999.1 - -1000| = 0.9 <= 50
    assert est["hu_ldpe"] == SIN_LINEA_BASE   # sin base para ese material
    lejos = estados("Tomógrafo", "valores_ct", hu, linea_base={"hu_pmp": -150.0})
    assert lejos["hu_pmp"] == NO_CUMPLE       # |-186 - -150| = 36 > 20

    ruido = {"ruido_centro_hu": 5.0}
    assert por_prueba(juzgar("Tomógrafo", "uniformidad", uniformidad_con(1.0, ruido=5.5), linea_base=ruido))["ruido"].estado == CUMPLE
    assert por_prueba(juzgar("Tomógrafo", "uniformidad", uniformidad_con(1.0, ruido=7.0), linea_base=ruido))["ruido"].estado == NO_CUMPLE


# ---------------------------------------------------------------------------
# 3. NO SE INVENTAN EQUIVALENCIAS
# ---------------------------------------------------------------------------

RESULTADOS_ARBITRARIOS = {"espesor": {"espesor_promedio_mm": 2.82, "espesor_teorico_mm": 2.0},
                          "tamano_pixel": {"X": 1.07, "Y": 1.07, "tam_px_teorico": 1.074},
                          "resolucion_contraste": {"resumen": {"rois_visibles_cnr": 5}},
                          "resolucion_espacial": {"regiones": {}}}


@pytest.mark.parametrize("equipo", EQUIPOS)
@pytest.mark.parametrize("categoria", sorted(RESULTADOS_ARBITRARIOS))
def test_lo_que_la_funcion_no_mide_igual_que_la_regla_queda_pendiente_y_lo_dice(equipo, categoria):
    (j,) = juzgar(equipo, categoria, RESULTADOS_ARBITRARIOS[categoria])
    assert not j.es_veredicto
    if PERFILES[equipo].reglas[j.prueba].aplica == "no":
        assert j.estado == NO_APLICA
    else:
        assert j.estado == ESTADO_PENDIENTE
        assert "Pendiente de métrica" in j.criterio and MOTIVO_PENDIENTE[j.prueba] in j.criterio


def test_el_espesor_del_tomografo_sigue_pendiente_por_decision_del_fisico():
    """E.1 (24-09): la función ya mide el espesor como pylinac (±0.005 mm en las 5 series), así que el motivo de
    G.3 ("la función lo sobreestima") dejó de ser cierto y no puede seguir guardándose con cada control nuevo.
    El criterio TG-66 sigue sin conectarse hasta E.2; mientras tanto no hay veredicto, con la razón verdadera."""
    for medido, nominal in ((2.82, 2.0), (4.2, 3.0), (1.92, 2.0)):
        (j,) = juzgar("Tomógrafo", "espesor", {"espesor_promedio_mm": medido, "espesor_teorico_mm": nominal})
        assert j.estado == ESTADO_PENDIENTE
    assert "sobreestima" not in MOTIVO_PENDIENTE["espesor"]
    assert "E.1" in MOTIVO_PENDIENTE["espesor"] and "pylinac" in MOTIVO_PENDIENTE["espesor"]


@pytest.mark.parametrize("equipo", ["Clinac ix", "Halcyon"])
def test_el_espesor_no_aplica_a_los_aceleradores_y_dice_el_motivo(equipo):
    (j,) = juzgar(equipo, "espesor", {"espesor_promedio_mm": 3.2})
    assert j.estado == NO_APLICA and "acelerador" in j.criterio


def test_un_equipo_sin_perfil_o_una_categoria_desconocida_no_inventan_veredicto():
    for categoria in CATEGORIA_A_PRUEBAS:
        for equipo in (None, "Equipo que no existe"):
            juicios = juzgar(equipo, categoria, {})
            assert juicios and {j.estado for j in juicios} == {ESTADO_SIN_PERFIL}
    with pytest.raises(KeyError):
        juzgar("Halcyon", "categoria_inventada", {})


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_sin_valor_medido_nunca_es_cumple(equipo):
    for categoria, vacio in (("uniformidad", {}), ("linealidad_ct", {}), ("valores_ct", []),
                             ("uniformidad", {"Centro": {}, "Arriba": {"promedio_hu": 3.0}})):
        for j in juzgar(equipo, categoria, vacio):
            assert j.estado != CUMPLE and j.estado != NO_CUMPLE, (categoria, j.estado)


def test_toda_prueba_de_la_matriz_esta_juzgada_o_dice_por_que_no():
    """Censo derivado: cada prueba de `perfiles.PRUEBAS` la trae exactamente una categoría de la pantalla, y o tiene
    equivalencia con la métrica de la regla o tiene su motivo de pendiente -- ninguna se cae en silencio."""
    juntas = [p for ps in CATEGORIA_A_PRUEBAS.values() for p in ps]
    assert sorted(juntas) == sorted(PRUEBAS)
    for prueba in PRUEBAS:
        assert (prueba in EQUIVALENCIAS) != (prueba in MOTIVO_PENDIENTE), prueba


def test_las_metricas_del_puente_son_las_que_nombra_la_matriz():
    """Si `perfiles.py` renombra una métrica, el puente dejaría de juzgarla sin avisar: aquí se rompe."""
    for equipo, perfil in PERFILES.items():
        for prueba, metricas in EQUIVALENCIAS.items():
            regla = perfil.reglas[prueba]
            if regla.aplica != "si":
                continue
            assert set(metricas) <= set(regla.metricas), (equipo, prueba, metricas, regla.metricas)
    assert {j.metrica for j in juzgar("Tomógrafo", "valores_ct", valores_ct_con(HU_TOMOGRAFO))} == set(EQUIVALENCIAS["numeros_ct"])


def test_los_textos_no_llevan_simbolos_de_correcto_incorrecto():
    """DA-18: palabras y color, nunca ✓ ni ✗."""
    juicios = []
    for equipo in EQUIPOS + (None,):
        juicios += juzgar(equipo, "uniformidad", uniformidad_con(45.0))
        juicios += juzgar(equipo, "valores_ct", valores_ct_con(HU_TOMOGRAFO))
        juicios += juzgar(equipo, "linealidad_ct", {"r_squared": 0.9})
        for categoria, res in RESULTADOS_ARBITRARIOS.items():
            juicios += juzgar(equipo, categoria, res)
    assert len(juicios) > 40
    plano = texto_html(juicios) + json.dumps([j.a_dict() for j in juicios], ensure_ascii=False)
    assert not any(s in plano for s in SIMBOLOS)
    assert SIMBOLOS not in Path(criterios.__file__).read_text(encoding="utf-8")


def test_el_panel_escapa_lo_que_viene_del_perfil_y_de_la_medicion():
    j = Juicio("uniformidad", "uniformidad", "unif_max_dif_hu", "Uniformidad <b>", 3.0, "HU", CUMPLE,
               "como máximo 5 HU & más", "fuente <script>", "norma")
    html = texto_html([j])
    assert "<script>" not in html and "&lt;script&gt;" in html and "&amp;" in html
    assert texto_html([]) == ""


# ---------------------------------------------------------------------------
# 4. NINGÚN UMBRAL DE JUICIO EN LA PANTALLA (tripwires por AST)
# ---------------------------------------------------------------------------

def _llamadas_de_produccion(nombres):
    """[(ruta relativa, línea, Call)] de toda llamada de PRODUCCIÓN (fuera de tests, .venv, build) a `nombres`."""
    salida = []
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")):
            continue
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", getattr(nodo.func, "attr", None)) in nombres:
                salida.append((rel, nodo.lineno, nodo))
    return salida


def _parametros_de_juicio(funcion):
    """Los argumentos de solo palabra clave SIN valor por defecto de una función de análisis: los umbrales."""
    return {p.name for p in inspect.signature(funcion).parameters.values()
            if p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty}


def _funciones_de_analisis():
    from analisisImagenes import Analisis_Catphan_TAC as modulo
    return {"resolucion_contraste": modulo.resolucion_contraste, "uniformidad": modulo.uniformidad}


def test_las_funciones_de_analisis_no_traen_un_umbral_de_juicio_por_defecto():
    """Un umbral con valor por defecto es un umbral escondido: el llamador puede olvidarlo y nadie se entera."""
    esperado = {"resolucion_contraste": {"cnr_lim", "visibilidad_lim", "min_rois_visibles"},
                "uniformidad": {"hu_tolerancia", "ui_threshold_pct", "inu_threshold_pct"}}
    for nombre, funcion in _funciones_de_analisis().items():
        assert _parametros_de_juicio(funcion) == esperado[nombre], nombre
        firmas = inspect.signature(funcion).parameters
        for umbral in esperado[nombre]:
            assert firmas[umbral].default is inspect.Parameter.empty


def test_ninguna_llamada_de_produccion_escribe_un_umbral_literal_y_todas_los_piden_a_criterios():
    funciones = _funciones_de_analisis()
    llamadas = _llamadas_de_produccion(set(funciones))
    en_pantalla = [x for x in llamadas if x[0].endswith("tac_mensual.py")]
    assert {getattr(c.func, "id", getattr(c.func, "attr", None)) for _, _, c in en_pantalla} == set(funciones), \
        "el censo no encontró las dos llamadas de la pantalla (ya no es una prueba)"
    for rel, linea, llamada in llamadas:
        nombre = getattr(llamada.func, "id", getattr(llamada.func, "attr", None))
        umbrales = _parametros_de_juicio(funciones[nombre])
        literales = [k.arg for k in llamada.keywords if k.arg in umbrales and isinstance(k.value, ast.Constant)]
        assert not literales, f"{rel}:{linea} escribe un umbral de juicio a mano: {literales}"
        # los umbrales llegan por UN solo `**` cuyo origen es el puente (`criterios.parametros_de_analisis(cat, ...)`)
        # o el dict de parámetros heredados (`PARAMETROS_HEREDADOS[cat]`, el caso del script manual del módulo)
        estrellas = [k.value for k in llamada.keywords if k.arg is None]
        assert len(estrellas) == 1, f"{rel}:{linea} no pide sus umbrales a criterios (un solo **)"
        origen = estrellas[0]
        if isinstance(origen, ast.Call) and getattr(origen.func, "attr", None) == "parametros_de_analisis":
            assert origen.args[0].value == nombre, f"{rel}:{linea} pide los umbrales de otra categoría"
            provistos = set(parametros_de_analisis(nombre, "Halcyon"))
        else:
            assert (isinstance(origen, ast.Subscript) and getattr(origen.value, "id", None) == "PARAMETROS_HEREDADOS"
                    and origen.slice.value == nombre), f"{rel}:{linea} el ** no viene de criterios"
            provistos = set(PARAMETROS_HEREDADOS[nombre])
        propios = {k.arg for k in llamada.keywords if k.arg}
        assert umbrales <= (provistos | propios), f"{rel}:{linea} deja sin umbral: {umbrales - provistos - propios}"


def test_toda_categoria_que_la_pantalla_analiza_se_juzga():
    """Census derivado: las categorías de `_mostrar_criterio(...)` son EXACTAMENTE las del puente."""
    arbol = ast.parse(PANTALLA.read_text(encoding="utf-8"))
    juzgadas = {n.args[0].value for n in ast.walk(arbol) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "_mostrar_criterio" and isinstance(n.args[0], ast.Constant)}
    assert juzgadas == set(CATEGORIA_A_PRUEBAS)


def test_los_dos_guardados_de_la_pantalla_llevan_el_criterio():
    llamadores = _llamadas_de_produccion({"guardar_prueba_completa_catphan"})
    assert len(llamadores) >= 2
    sin = [(r, l) for r, l, c in llamadores if "criterios_por_categoria" not in {k.arg for k in c.keywords}]
    assert not sin, f"guardados sin `criterios_por_categoria`: {sin}"


def test_criterios_no_repite_ningun_umbral_del_perfil():
    """Los números de la matriz (5, 40, 50, 20, 0.99...) viven SOLO en `perfiles.py`; aquí solo se admiten 0, 2 (R²) y
    100 (porcentaje del texto), y los heredados dentro de su diccionario."""
    arbol = ast.parse(Path(criterios.__file__).read_text(encoding="utf-8"))
    heredados = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "PARAMETROS_HEREDADOS" for t in n.targets):
            heredados = {id(m) for m in ast.walk(n)}
    numeros = {m.value for m in ast.walk(arbol) if isinstance(m, ast.Constant)
               and isinstance(m.value, (int, float)) and not isinstance(m.value, bool) and id(m) not in heredados}
    assert numeros <= {0, 2, 100}, numeros


# ---------------------------------------------------------------------------
# 5. LA PANTALLA LO MUESTRA
# ---------------------------------------------------------------------------

def _panel(pestana):
    """El panel de criterio de una pestaña de resultados, buscado como lo busca la pantalla."""
    panel = pestana["tab"].findChild(QLabel, "criterio_texto")
    assert panel is not None, "la pestaña de resultados no construyó el panel de criterio"
    assert panel is pestana["criterio"]
    return panel


@pytest.mark.parametrize("clave", sorted(FORMULARIOS))
def test_la_pantalla_juzga_con_la_regla_de_su_equipo_y_lo_muestra(app, bd_temporal, clave):
    constructor, equipo, _hoja = FORMULARIOS[clave]
    obj = iniciar(constructor())
    obj.criterios_por_categoria = {}
    pestana = obj._crear_nueva_tab("Uniformidad y Ruido")        # la pestaña real de resultados, con su panel
    obj.tab_widget.setCurrentWidget(pestana["tab"])
    juicios = obj._mostrar_criterio("uniformidad", uniformidad_con(10.0))
    esperado = CUMPLE if equipo != "Tomógrafo" else NO_CUMPLE
    assert por_prueba(juicios)["uniformidad"].estado == esperado
    guardado = obj.criterios_por_categoria["uniformidad"]
    assert [d["prueba"] for d in guardado] == ["uniformidad", "ruido"]
    assert json.loads(json.dumps(guardado)) == guardado           # lo que se archiva es JSON puro
    texto = _panel(pestana).text()
    assert esperado in texto and PERFILES[equipo].reglas["uniformidad"].fuente in texto
    assert not any(s in texto for s in SIMBOLOS)


def test_una_falla_al_juzgar_no_impide_mostrar_el_resultado(app, bd_temporal, monkeypatch):
    obj = iniciar(FORMULARIOS["tomografo"][0]())
    monkeypatch.setattr(criterios, "juzgar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert obj._mostrar_criterio("uniformidad", uniformidad_con(1.0)) is None


def test_limpiar_los_resultados_limpia_sus_criterios(app, bd_temporal):
    obj = iniciar(FORMULARIOS["tomografo"][0]())
    obj.criterios_por_categoria = {}
    obj._mostrar_criterio("uniformidad", uniformidad_con(1.0))
    obj._mostrar_criterio("linealidad_ct", {"r_squared": 0.999})
    obj.limpiar_resultados_catphan("uniformidad")
    assert set(obj.criterios_por_categoria) == {"linealidad_ct"}
    obj.limpiar_resultados_catphan()
    assert obj.criterios_por_categoria == {}


# ---------------------------------------------------------------------------
# 6. SE GUARDA: migración, ida y vuelta, reemplazo
# ---------------------------------------------------------------------------

def _columnas(ruta, tabla):
    con = sqlite3.connect(ruta)
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({tabla})")]
    finally:
        con.close()


def test_una_bd_nueva_trae_la_columna(bd_temporal):
    assert "criterio_veredicto" in _columnas(conection_mod.ruta_base_datos(), "pruebas")


def test_la_migracion_es_aditiva_e_idempotente_sobre_una_copia_de_produccion(monkeypatch, tmp_path):
    from _bd_referencia import BD_REBUILD_21_09
    if not BD_REBUILD_21_09.exists():
        pytest.skip("falta la BD de referencia del 21-09")
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    assert "criterio_veredicto" not in _columnas(str(copia), "pruebas")
    antes = sqlite3.connect(copia).execute("SELECT COUNT(*) FROM pruebas").fetchone()[0]

    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    for _ in range(2):                                    # la segunda corrida no debe cambiar nada
        conection_mod.Conexion._instance = None
        conection_mod.Conexion().con.close()
        conection_mod.Conexion._instance = None
        assert _columnas(str(copia), "pruebas").count("criterio_veredicto") == 1
    con = sqlite3.connect(copia)
    assert con.execute("SELECT COUNT(*) FROM pruebas").fetchone()[0] == antes
    assert con.execute("SELECT COUNT(*) FROM pruebas WHERE criterio_veredicto IS NOT NULL").fetchone()[0] == 0
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()


LINEALIDAD = {"pendiente": 6146.9, "intercepto": -996.0, "r_squared": 0.99903, "referencia": 0.5,
              "escala_contraste": 1 / 6146.9}
UNIFORMIDAD = {"Uniformidad": {"max_diferencia": 1.0}, "Centro": {"promedio_hu": 1.0, "desviacion": 2.0}}


def _crear_control():
    con = sqlite3.connect(conection_mod.ruta_base_datos())
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('Halcyon', 'Mensual', '09/2026')")
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


def _guardar(sesion, categorias, criterios_por_categoria=None):
    kw = {} if criterios_por_categoria is None else {"criterios_por_categoria": criterios_por_categoria}
    return guardar_prueba_completa_catphan(
        user_id="Fisico Real", fecha="2026-09-24", equipo="Halcyon", kv=125, ma=80, espesor_corte=2.0,
        resultados_por_categoria=categorias, id_sesion=sesion, **kw)


def _filas(sesion, id_tipo):
    con = sqlite3.connect(conection_mod.ruta_base_datos())
    try:
        return con.execute("SELECT criterio_veredicto, activo FROM pruebas WHERE id_sesion=? AND id_tipo=? "
                           "ORDER BY id_prueba", (sesion, id_tipo)).fetchall()
    finally:
        con.close()


def test_cada_categoria_archiva_su_propio_criterio(app, bd_temporal):
    sesion = _crear_control()
    lin = criterios.a_json_ready(juzgar("Halcyon", "linealidad_ct", LINEALIDAD))
    uni = criterios.a_json_ready(juzgar("Halcyon", "uniformidad", uniformidad_con(3.0)))
    _guardar(sesion, {"linealidad_ct": LINEALIDAD, "uniformidad": UNIFORMIDAD},
             {"linealidad_ct": lin, "uniformidad": uni})
    (lin_bd, activo_l), = _filas(sesion, 6)
    (uni_bd, activo_u), = _filas(sesion, 7)
    assert activo_l == 1 and activo_u == 1
    assert json.loads(lin_bd) == lin and json.loads(uni_bd) == uni
    assert json.loads(lin_bd) != json.loads(uni_bd)
    # ida y vuelta: lo archivado vuelve a ser `Juicio`s idénticos
    assert [Juicio(**d) for d in json.loads(uni_bd)] == juzgar("Halcyon", "uniformidad", uniformidad_con(3.0))


def test_sin_criterio_se_guarda_null_y_las_columnas_heredadas_no_cambian(app, bd_temporal):
    sesion = _crear_control()
    _guardar(sesion, {"uniformidad": UNIFORMIDAD})                       # llamador anterior a G.3
    _guardar(sesion, {"linealidad_ct": LINEALIDAD}, {"linealidad_ct": []})  # lista vacía = nada que archivar
    assert _filas(sesion, 7) == [(None, 1)] and _filas(sesion, 6) == [(None, 1)]


def test_reguardar_anula_la_fila_anterior_y_conserva_su_criterio(app, bd_temporal):
    """§12.4 + EB2c: la generación anterior sigue siendo lo que se firmó ese día."""
    sesion = _crear_control()
    uno = criterios.a_json_ready(juzgar("Halcyon", "uniformidad", uniformidad_con(3.0)))
    dos = criterios.a_json_ready(juzgar("Halcyon", "uniformidad", uniformidad_con(45.0)))
    _guardar(sesion, {"uniformidad": UNIFORMIDAD}, {"uniformidad": uno})
    _guardar(sesion, {"uniformidad": UNIFORMIDAD}, {"uniformidad": dos})
    (vieja, a0), (nueva, a1) = _filas(sesion, 7)
    assert (a0, a1) == (0, 1)
    assert json.loads(vieja) == uno and json.loads(nueva) == dos and uno != dos


# ---------------------------------------------------------------------------
# 7. EL INFORME PDF IMPRIME LO ARCHIVADO
# ---------------------------------------------------------------------------

SESION_42 = (42, "Tomógrafo", "07/2026")      # las siete categorías
TIPO = {"espesor": 1, "tamano_pixel": 2, "resolucion_contraste": 3, "resolucion_espacial": 4, "valores_ct": 5,
        "linealidad_ct": 6, "uniformidad": 7}
TITULO_TABLA = "Criterio y veredicto del equipo"


def _texto(pdf):
    return re.sub(r"\s+", " ", "\n".join(paginas(pdf)))


def _archivar_criterios(ruta, sesion=42, equipo="Tomógrafo"):
    """Archiva en la copia lo que la pantalla del tomógrafo habría guardado con mediciones reales."""
    medidas = {"espesor": RESULTADOS_ARBITRARIOS["espesor"], "tamano_pixel": RESULTADOS_ARBITRARIOS["tamano_pixel"],
               "resolucion_contraste": RESULTADOS_ARBITRARIOS["resolucion_contraste"],
               "resolucion_espacial": RESULTADOS_ARBITRARIOS["resolucion_espacial"],
               "valores_ct": valores_ct_con(HU_TOMOGRAFO), "linealidad_ct": {"r_squared": 0.999},
               "uniformidad": uniformidad_con(2.0, ruido=5.0)}
    todos = []
    con = sqlite3.connect(ruta)
    for categoria, res in medidas.items():
        juicios = criterios.a_json_ready(juzgar(equipo, categoria, res))
        todos += juicios
        n = con.execute("UPDATE pruebas SET criterio_veredicto=? WHERE id_sesion=? AND id_tipo=? "
                        "AND (activo IS NULL OR activo=1)",
                        (json.dumps(juicios, ensure_ascii=False, sort_keys=True), sesion, TIPO[categoria])).rowcount
        assert n == 1, categoria
    con.commit()
    con.close()
    return todos


def test_un_control_anterior_a_g3_sale_como_antes_con_sus_filas_heredadas(app, avisos, bd_copia, monkeypatch):
    ok, visor = generar(bd_copia, monkeypatch, *SESION_42)
    plano = _texto(visor["pdf"])
    assert ok is True and avisos == []
    assert TITULO_TABLA not in plano
    assert "Pasa prueba de uniformidad" in plano and "Linealidad aceptable" in plano


def test_el_pdf_de_un_control_con_criterio_trae_la_tabla_una_vez_y_en_su_sitio(app, avisos, bd_copia, monkeypatch):
    juicios = _archivar_criterios(bd_copia)
    ok, visor = generar(bd_copia, monkeypatch, *SESION_42)
    plano = _texto(visor["pdf"])
    assert ok is True and avisos == []
    assert plano.count(TITULO_TABLA) == 1
    assert plano.index("Parámetros de adquisición") < plano.index(TITULO_TABLA) < plano.index("Espesor promedio medido")
    for j in juicios:
        for celda in (j["etiqueta"], j["estado"]):
            assert re.sub(r"\s+", " ", celda) in plano, celda
    # la fuente y su firmeza salen con el veredicto
    assert "AAPM TG-66 (uniformidad de campo, mensual) (norma)" in plano
    assert "(propuesta)" in plano and "Criterio pendiente de métrica" in plano and "Sin línea base" in plano


def test_con_criterio_los_veredictos_viejos_dejan_de_imprimirse_y_no_hay_simbolos(app, avisos, bd_copia, monkeypatch):
    _archivar_criterios(bd_copia)
    _ok, visor = generar(bd_copia, monkeypatch, *SESION_42)
    plano = _texto(visor["pdf"])
    assert "Pasa prueba de uniformidad" not in plano and "Linealidad aceptable" not in plano
    assert "UI/INU con el umbral heredado (informativo)" in plano
    assert "R² (r al cuadrado)" in plano and "r (coeficiente de correlación)" in plano
    assert "Diferencia máxima entre regiones" in plano
    tabla = plano[plano.index(TITULO_TABLA):plano.index("Espesor promedio medido")]
    assert not any(s in tabla for s in SIMBOLOS)


def test_el_informe_reabierto_imprime_lo_archivado_no_lo_que_diga_el_perfil_de_hoy(app, avisos, bd_copia, monkeypatch):
    """§12.4: cambiar la regla en el perfil NO reescribe el documento de un control ya firmado."""
    _archivar_criterios(bd_copia)
    _ok, antes = generar(bd_copia, monkeypatch, *SESION_42)
    regla = copy.copy(PERFILES["Tomógrafo"].reglas["uniformidad"])
    regla.tolerancia = 0.5
    regla.fuente = "OTRA FUENTE QUE NO SE ARCHIVÓ"
    monkeypatch.setitem(PERFILES["Tomógrafo"].reglas, "uniformidad", regla)
    _ok, despues = generar(bd_copia, monkeypatch, *SESION_42)
    assert _texto(antes["pdf"]) == _texto(despues["pdf"])
    assert "OTRA FUENTE" not in _texto(despues["pdf"])


def test_la_tabla_cabe_en_la_pagina_y_ninguna_palabra_se_parte(app, avisos, bd_copia, monkeypatch):
    import fitz
    juicios = _archivar_criterios(bd_copia)
    _ok, visor = generar(bd_copia, monkeypatch, *SESION_42)
    doc = fitz.open(stream=visor["pdf"], filetype="pdf")
    pagina = next(p for p in doc if TITULO_TABLA in p.get_text())
    cabecera = pagina.search_for(TITULO_TABLA)[0]
    palabras = [w for w in pagina.get_text("words") if w[1] >= cabecera.y0]
    assert palabras and max(w[2] for w in palabras) <= pagina.rect.width - 20      # nada fuera del margen derecho
    plano = _texto(visor["pdf"])
    # ninguna palabra de las columnas angostas se partió a mitad: cada palabra de cada etiqueta sigue entera
    for j in juicios:
        for palabra in re.findall(r"\S{5,}", f"{j['etiqueta']} {j['estado']}"):
            assert palabra in plano, palabra


def test_la_seccion_de_imagenes_del_pdf_anual_conoce_la_tabla_nueva():
    from models.PDF import pdf
    assert "criterios_veredictos" in pdf.TABLAS_INFORME_IMAGENES


# ---------------------------------------------------------------------------
# 8. SERIES REALES: el veredicto de uniformidad con la regla de cada equipo
# ---------------------------------------------------------------------------

_ENTRADAS = {}


def _entrada_real(clave):
    """(corte en 8 bits, corte en HU, píxel) del módulo de uniformidad de una serie real; salta si no hay corpus."""
    if clave not in _ENTRADAS:
        from test_d0_geometria_desde_hu import _ct_analizado, _hu_y_tam_px, _ventanear
        ct = _ct_analizado(clave)
        hu, tam_px, _ = _hu_y_tam_px(ct, "ctp486")
        _ENTRADAS[clave] = (_ventanear(hu, 40, 400), hu, tam_px)
    return _ENTRADAS[clave]


def _uniformidad_con_tolerancia(clave, tolerancia):
    import warnings
    from analisisImagenes.Analisis_Catphan_TAC import uniformidad
    c255, hu, tam_px = _entrada_real(clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return uniformidad(c255, hu, tam_px, visualizar=False, hu_tolerancia=tolerancia,
                           **PARAMETROS_HEREDADOS["uniformidad"])


def _uniformidad_real(clave, equipo):
    return _uniformidad_con_tolerancia(clave, parametros_de_analisis("uniformidad", equipo)["hu_tolerancia"])


@pytest.mark.parametrize("clave, equipo, estado, banda", [
    ("TOMOGRAFO", "Tomógrafo", CUMPLE, (0.0, 5.0)),         # medido 2.0 HU: entra en los 5 HU de TG-66
    ("HALCYON_SEP", "Halcyon", CUMPLE, (5.0, 40.0)),        # medido 8.8 HU: sí en 40, NO cumpliría 5 -> la regla importa
    ("HALCYON_JUN", "Halcyon", CUMPLE, (5.0, 40.0)),        # 11.4 HU
    ("IX_DIC", "Clinac ix", NO_CUMPLE, (40.0, 200.0)),      # 48.7 HU: el cupping del iX supera los 40 HU
])
def test_serie_real_uniformidad_con_la_regla_de_su_equipo(clave, equipo, estado, banda):
    res = _uniformidad_real(clave, equipo)
    j = por_prueba(juzgar(equipo, "uniformidad", res))["uniformidad"]
    assert banda[0] <= j.valor <= banda[1], (clave, j.valor)
    assert j.estado == estado, (clave, j.valor, j.criterio)
    # el umbral por ROI que la función marcó es el del perfil, no un 40 escrito a mano
    tolerancia = PERFILES[equipo].reglas["uniformidad"].tolerancia
    for region in ("Arriba", "Abajo", "Izquierda", "Derecha"):
        dif = abs(res[region]["promedio_hu"] - res["Centro"]["promedio_hu"])
        assert res[region]["pasa_tolerancia_rel_centro"] == (dif <= tolerancia), (clave, region)


@pytest.mark.parametrize("tolerancia", [1.0, 5.0, 1000.0])
def test_serie_real_la_tolerancia_que_se_le_pasa_a_la_funcion_es_la_que_se_aplica(tolerancia):
    """Sobre el HU real del Halcyon (diferencia máxima con el centro de 8.8 HU): la marca por ROI sigue la tolerancia recibida, no
    un valor escrito dentro de la función."""
    res = _uniformidad_con_tolerancia("HALCYON_SEP", tolerancia)
    marcas = []
    for region in ("Arriba", "Abajo", "Izquierda", "Derecha"):
        dif = abs(res[region]["promedio_hu"] - res["Centro"]["promedio_hu"])
        assert res[region]["pasa_tolerancia_rel_centro"] == (dif <= tolerancia), (region, dif, tolerancia)
        marcas.append(res[region]["pasa_tolerancia_rel_centro"])
    if tolerancia == 1.0:
        assert not all(marcas)       # la diferencia máxima medida (8.8 HU) supera 1 HU: alguna región no entra
    if tolerancia == 1000.0:
        assert all(marcas)


def test_serie_real_sin_regla_de_uniformidad_las_marcas_por_roi_quedan_sin_veredicto():
    res = _uniformidad_con_tolerancia("HALCYON_SEP", None)
    assert all(res[r]["pasa_tolerancia_rel_centro"] is None for r in ("Arriba", "Abajo", "Izquierda", "Derecha"))
