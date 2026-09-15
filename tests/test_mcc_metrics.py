"""Tests de services/mcc_metrics.py (Fase D4.1b).

Dos capas:

1. Sintetico (perfiles trapezoidales construidos a mano): confirma que la
   implementacion es sensata -- perfil plano y simetrico -> 0; perfil con
   una inclinacion deliberada -> valor claramente distinto de cero, del
   orden de magnitud esperado. No prueba que la formula sea LA de PTW (eso
   es la capa 2), solo que no esta rota.

2. Validacion contra el patron de oro real: dosimetriaMen (BaseDatosQA.db,
   solo lectura) cruzado con el corpus .mcc real, para las 6 referencias que
   PLAN_FASE_K_D4.md identifica como pares verificables (16, 13, 30, 35 de
   iX; 22, 38 de 600). Se salta sola si falta el corpus o la BD.

   La tolerancia por-fila es generosa (±1.5) a proposito: son transcripciones
   MANUALES del software PTW (no una exportacion exacta), y el propio plan
   autoriza tolerar outliers puntuales. Lo que SI se exige estricto es el
   agregado (MAE y fracción dentro de ±1.0) -- eso es lo que protege contra
   una regresión real de la fórmula/ratio, sin que un test se vuelva
   quebradizo por un dato mal transcrito puntual. Ver docstring de
   services/mcc_metrics.py para las cifras exactas encontradas al calibrar.
"""
import os
import sqlite3
from datetime import datetime

import numpy as np
import pytest

from mcc_PTW_read.mcc_read import EscaneoMCC, agregar_carpeta
from services.mcc_metrics import (
    calcular_planicidad, calcular_simetria, calcular_simetria_planicidad,
    calcular_calidad_fotones,
)
from _corpus import mes_primeros  # HI-0: fuente única de rutas del corpus

from _bd_referencia import BD_QA  # DP-104: fuente única de rutas de BD
DB = str(BD_QA)

# ref -> (carpeta_mes, nombre_carpeta_ix_o_None_si_es_600)
# La may/min de "IX"/"iX" no es consistente en el corpus real entre meses.
REFS_ORO = {
    16: ("Febrero", "IX"),
    13: ("Marzo", "IX"),
    30: ("Mayo", "iX"),
    35: ("Junio", "iX"),
    22: ("Abril", None),
    38: ("Junio", None),
}


def _escaneo(col2, x):
    return EscaneoMCC(curve_type="INPLANE_PROFILE", meas_date=datetime(2026, 1, 1),
                       energia="6mv", modalidad="X", posiciones=list(x),
                       col2=list(col2), col3=[], archivo="sintetico")


def _perfil_trapezoidal(x, medio_ancho=50.0, rampa=5.0, meseta=10.0, base=1.0, pendiente=0.0):
    """Perfil de haz idealizado: meseta plana (o con una pendiente lineal
    deliberada) entre bordes con rampa lineal -- suficiente para que FWXM
    detecte bordes al 50% de forma estable."""
    y = np.full_like(x, base, dtype=float)
    for i, xi in enumerate(x):
        bi, bd = -medio_ancho, medio_ancho
        if bi + rampa <= xi <= bd - rampa:
            y[i] = meseta + pendiente * xi
        elif bi - rampa < xi < bi + rampa:
            frac = (xi - (bi - rampa)) / (2 * rampa)
            y[i] = base + frac * (meseta - base)
        elif bd - rampa < xi < bd + rampa:
            frac = ((bd + rampa) - xi) / (2 * rampa)
            y[i] = base + frac * (meseta - base)
    return y


class TestSinteticoSensato:
    X = np.arange(-100, 100.5, 0.5)

    def test_perfil_plano_y_simetrico_da_cero(self):
        e = _escaneo(_perfil_trapezoidal(self.X, pendiente=0.0), self.X)

        assert calcular_simetria(e) == 0.0
        assert calcular_planicidad(e) == 0.0

    def test_perfil_inclinado_da_asimetria_no_nula(self):
        e = _escaneo(_perfil_trapezoidal(self.X, pendiente=0.02), self.X)

        assert calcular_simetria(e) > 1.0
        assert calcular_planicidad(e) > 1.0

    def test_inclinar_al_reves_no_cambia_la_magnitud_de_simetria(self):
        e_pos = _escaneo(_perfil_trapezoidal(self.X, pendiente=0.02), self.X)
        e_neg = _escaneo(_perfil_trapezoidal(self.X, pendiente=-0.02), self.X)

        assert calcular_simetria(e_pos) == pytest.approx(calcular_simetria(e_neg), abs=0.01)

    def test_calcular_simetria_planicidad_arma_las_4_claves(self):
        curvas = {
            "INPLANE_PROFILE": _escaneo(_perfil_trapezoidal(self.X, pendiente=0.0), self.X),
            "CROSSPLANE_PROFILE": _escaneo(_perfil_trapezoidal(self.X, pendiente=0.02), self.X),
        }

        resultado = calcular_simetria_planicidad(curvas)

        assert set(resultado.keys()) == {
            "simetria_inplane", "simetria_crossplane",
            "planicidad_inplane", "planicidad_crossplane"}
        assert resultado["simetria_inplane"] == 0.0
        assert resultado["simetria_crossplane"] > 1.0

    def test_falta_una_curva_falla_ruidoso(self):
        curvas = {"INPLANE_PROFILE": _escaneo(_perfil_trapezoidal(self.X), self.X)}

        with pytest.raises(KeyError):
            calcular_simetria_planicidad(curvas)


def _pdd(posiciones_mm, col2):
    return EscaneoMCC(curve_type="PDD", meas_date=datetime(2026, 1, 1),
                       energia="6mv", modalidad="X", posiciones=list(posiciones_mm),
                       col2=list(col2), col3=[], archivo="sintetico")


class TestCalidadFotonesSintetico:
    """H4.1 (auditoría 2026-07-16): a diferencia de simetría/planicidad, esta
    fórmula ES un protocolo publicado (IAEA TRS-398 -- ver docstring de
    calcular_calidad_fotones), así que aquí SÍ se puede verificar el
    resultado exacto a mano, no solo "sensato"."""

    def test_valor_exacto_con_puntos_justo_en_100_y_200mm(self):
        # M10 = 100.0 en pos=100mm, M20 = 66.0 en pos=200mm (sin necesidad de
        # interpolar -- los puntos caen exactos): TPR20,10 = 1.2661*0.66 -
        # 0.0595 = 0.776126 -> 0.7761.
        pdd = _pdd([0, 50, 100, 150, 200, 250], [100.0, 100.0, 100.0, 80.0, 66.0, 55.0])

        assert calcular_calidad_fotones(pdd) == 0.7761

    def test_interpola_cuando_no_hay_punto_exacto(self):
        # M10 interpolado entre (90,100.0) y (110,90.0) -> 95.0 en pos=100.
        # M20 interpolado entre (190,70.0) y (210,60.0) -> 65.0 en pos=200.
        pdd = _pdd([0, 90, 110, 190, 210], [100.0, 100.0, 90.0, 70.0, 60.0])

        m10, m20 = 95.0, 65.0
        esperado = round(1.2661 * (m20 / m10) - 0.0595, 4)
        assert calcular_calidad_fotones(pdd) == esperado

    def test_orden_de_las_posiciones_no_importa(self):
        """np.interp exige x creciente -- el cálculo debe ordenar primero
        (los .mcc reales no siempre traen las posiciones ya ordenadas)."""
        pdd_ordenado = _pdd([0, 100, 200], [100.0, 100.0, 66.0])
        pdd_desordenado = _pdd([200, 0, 100], [66.0, 100.0, 100.0])

        assert calcular_calidad_fotones(pdd_ordenado) == calcular_calidad_fotones(pdd_desordenado)


REFS_ORO_FOTONES = {16: ("Febrero", "IX"), 13: ("Marzo", "IX"), 30: ("Mayo", "iX"),
                     35: ("Junio", "iX"), 22: ("Abril", None), 38: ("Junio", None)}


def _valores_oro_calidad():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute("""SELECT ref, energia, calidad_pdd20_10 FROM dosimetriaMen
                       WHERE ref IN (16,13,30,35,22,38) AND energia LIKE '%mv'""")
        return cur.fetchall()
    finally:
        con.close()


def _carpeta_fotones_de(ref):
    mes, ix_nombre = REFS_ORO_FOTONES[ref]
    if ix_nombre is None:
        return mes_primeros(mes, "600")
    return mes_primeros(mes, "IX", "Fotones")


def _corpus_oro_fotones_disponible():
    if not os.path.exists(DB):
        return False
    for ref, (mes, ix_nombre) in REFS_ORO_FOTONES.items():
        maquina = "600" if ix_nombre is None else "IX"
        sub = None if ix_nombre is None else "Fotones"
        if mes_primeros(mes, maquina, sub) is None:
            return False
    return True


@pytest.mark.skipif(not _corpus_oro_fotones_disponible(),
                    reason="corpus de oro (PrimerosMeses/Fotones) y/o BD no disponibles en esta máquina")
class TestCalidadFotonesContraDosimetriaMenReal:
    """H4.1: validación contra las mismas 6 referencias de oro que D4.1b,
    filtradas a fotones (calidad de electrones es H4.4, sin fórmula
    todavía). Ver services/mcc_metrics.py para el detalle de la
    calibración (8/10 exactas a 4 decimales; ref 16/Febrero difiere por
    escaneos de PDD repetidos el mismo día, no por un error de fórmula)."""

    @staticmethod
    @pytest.fixture(scope="class")
    def comparaciones():
        _cache = {}
        resultado = []
        for ref, energia, calidad_ptw in _valores_oro_calidad():
            carpeta = _carpeta_fotones_de(ref)
            if carpeta not in _cache:
                _cache[carpeta] = agregar_carpeta(carpeta)
            curvas = _cache[carpeta]["datos"].get(energia)
            if not curvas or "PDD" not in curvas:
                continue
            calc = calcular_calidad_fotones(curvas["PDD"])
            resultado.append((ref, energia, calc, calidad_ptw))
        return resultado

    def test_hay_datos_para_las_10_filas_de_oro_de_fotones(self, comparaciones):
        assert len(comparaciones) == 10

    def test_al_menos_8_de_10_exactas_a_4_decimales(self, comparaciones):
        exactas = [(ref, energia) for ref, energia, calc, ptw in comparaciones
                   if abs(calc - ptw) < 1e-4]
        assert len(exactas) >= 8, (
            f"solo {len(exactas)}/10 exactas -- revisar fórmula/interpolación: {comparaciones}")

    def test_ninguna_desviacion_mayor_a_1_porciento(self, comparaciones):
        """Cota floja: protege contra una regresión gorda (formula/columna
        equivocada), no contra el ruido de escaneos repetidos puntuales."""
        peores = [(ref, energia, calc, ptw) for ref, energia, calc, ptw in comparaciones
                  if abs(calc - ptw) > 0.01]
        assert peores == [], f"desviaciones > 1% (revisar fórmula): {peores}"


# ── Capa 2: validación contra dosimetriaMen (patrón de oro real) ──────────

def _valores_oro():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute("""SELECT ref, energia, simetria_inplane, simetria_crossplane,
                              planicidad_inplane, planicidad_crossplane
                       FROM dosimetriaMen WHERE ref IN (16,13,30,35,22,38)""")
        return cur.fetchall()
    finally:
        con.close()


def _carpeta_de(ref, energia):
    # HI-0: mes_primeros resuelve la grafía IX/iX y devuelve None si la carpeta
    # no está (protegido aguas arriba por el skipif granular de la clase).
    mes, ix_nombre = REFS_ORO[ref]
    if ix_nombre is None:
        return mes_primeros(mes, "600")
    sub = "Electrones" if energia.endswith("mev") else "Fotones"
    return mes_primeros(mes, "IX", sub)


def _corpus_oro_disponible():
    """HI-0 (granularidad de skip, TEMA D): las 6 carpetas de oro CONCRETAS
    deben existir, no solo la raíz del corpus. Si alguna no está -> SKIP
    honesto, nunca fallo (una mudanza de archivos no es una regresión). El
    guard `len == 26*4` de más abajo sigue detectando datos incompletos como
    fallo real -- esto solo evita el falso rojo por corpus ausente/movido."""
    if not os.path.exists(DB):
        return False
    for ref, (mes, ix_nombre) in REFS_ORO.items():
        maquina = "600" if ix_nombre is None else "IX"
        if mes_primeros(mes, maquina) is None:
            return False
    return True


@pytest.mark.skipif(not _corpus_oro_disponible(),
                    reason="corpus de oro (PrimerosMeses) y/o BD no disponibles en esta máquina")
class TestValidacionContraDosimetriaMenReal:
    @staticmethod
    @pytest.fixture(scope="class")
    def comparaciones():
        """Lista de (ref, energia, eje, valor_calculado, valor_ptw) para las
        4 métricas de las 26 filas de oro disponibles."""
        _cache = {}
        resultado = []
        for ref, energia, sim_in_t, sim_cr_t, flat_in_t, flat_cr_t in _valores_oro():
            carpeta = _carpeta_de(ref, energia)
            if carpeta not in _cache:
                _cache[carpeta] = agregar_carpeta(carpeta)
            curvas = _cache[carpeta]["datos"].get(energia)
            if not curvas or "INPLANE_PROFILE" not in curvas or "CROSSPLANE_PROFILE" not in curvas:
                continue
            calc = calcular_simetria_planicidad(curvas)
            resultado.append((ref, energia, "sim_in", calc["simetria_inplane"], sim_in_t))
            resultado.append((ref, energia, "sim_cr", calc["simetria_crossplane"], sim_cr_t))
            resultado.append((ref, energia, "flat_in", calc["planicidad_inplane"], flat_in_t))
            resultado.append((ref, energia, "flat_cr", calc["planicidad_crossplane"], flat_cr_t))
        return resultado

    def test_hay_datos_para_las_26_filas_de_oro(self, comparaciones):
        # 26 filas * 4 valores (sim_in, sim_cr, flat_in, flat_cr)
        assert len(comparaciones) == 26 * 4

    def test_ninguna_comparacion_se_desvia_mas_de_1_5(self, comparaciones):
        """Cota floja: protege contra una regresión gorda (formula rota,
        columna/ratio equivocados), no contra el ruido de transcripción
        manual normal."""
        peores = [(ref, energia, eje, calc, ptw) for ref, energia, eje, calc, ptw in comparaciones
                  if abs(calc - ptw) > 1.5]
        assert peores == [], f"desviaciones > 1.5 (revisar fórmula/ratio): {peores}"

    def test_agregado_mae_y_cobertura(self, comparaciones):
        """Cota estricta pero agregada (ver services/mcc_metrics.py para la
        calibración original): MAE <= 0.4 y al menos 90% de los valores
        dentro de ±1.0 del valor PTW."""
        errores = np.array([abs(calc - ptw) for _, _, _, calc, ptw in comparaciones])

        assert errores.mean() <= 0.4
        assert (errores <= 1.0).mean() >= 0.90

    def test_simetria_especificamente_muy_ajustada(self, comparaciones):
        """La simetría (point-difference @ 0.70) ajustó mejor que la
        planicidad en la calibración (MAE 0.13 vs 0.30) -- se exige aparte,
        más estricta."""
        errores_sim = np.array([abs(calc - ptw) for _, _, eje, calc, ptw in comparaciones
                                 if eje.startswith("sim")])

        assert errores_sim.mean() <= 0.25


class TestCorpusHelperNoneSafe:
    """HI-0: el helper de rutas nunca revienta por ausencia -> devuelve None,
    para que el skipif del llamador haga SKIP honesto. Corre en cualquier
    máquina (no depende de que el corpus del físico esté presente)."""

    def test_mes_inexistente_devuelve_none(self):
        assert mes_primeros("__no_existe__", "IX", "Fotones") is None
        assert mes_primeros("__no_existe__", "600") is None
        assert mes_primeros("__no_existe__", "Halcyon") is None
