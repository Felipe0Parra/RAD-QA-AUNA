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
)

CORPUS = os.path.expanduser("~/Documents/Archivos_UseApp/Archivos QA")
DB = "/home/felipepp/Documents/CodigosPython/AUNA_2026_2/BaseDatosQA.db"

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
    mes, ix_nombre = REFS_ORO[ref]
    if ix_nombre is None:
        return os.path.join(CORPUS, mes, "600")
    sub = "Electrones" if energia.endswith("mev") else "Fotones"
    return os.path.join(CORPUS, mes, ix_nombre, sub)


@pytest.mark.skipif(not (os.path.exists(CORPUS) and os.path.exists(DB)),
                    reason="corpus real y/o BD de producción no disponibles en esta máquina")
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
