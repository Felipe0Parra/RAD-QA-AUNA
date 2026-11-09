"""UM.2 (PLAN_CALCULADORA_UM_05-11.md, DC17): la verdad conocida, un haz de 6 MV con primaria, dispersión de maniquí y dispersión de cabezal separadas.

Es el modelo físico del cuaderno de estudio (`Calculadora_UM_TG71.ipynb`, sección 3), reescrito aquí sin compartir nada con el
motor: no importa ninguna de sus funciones. Permite conocer Sc, Sp y la dosis exacta en cualquier geometría, cosa imposible con
datos medidos, y medir cuánto se equivoca el motor con una tabla de factores compilada.

UM.2 v2 (estudio A2 del 08-11): `Mundo` admite además otro efecto de intercambio de las mandíbulas, calibrado con la asimetría REAL de la tabla abierta del 600C
(«loglineal»: Sc(X, Y) = Sc_cuadrado(4A/P)·(Y/X)^α, α = 0.00515 − 0.00099·ln(√(XY)/10), residuo 0.23 % en sus 66 pares de nodos), y un maniquí que ve el campo
por su cuadrado equivalente («4A/P», el supuesto de la TG-71 en 2.A.2.b). Las funciones del módulo son las del mundo original (apéndice B con la geometría del
cabezal y el núcleo integrado sobre el rectángulo), sin cambio.
"""
import numpy as np

SAD = 100.0
DMAX = 1.5
MU, LAM, S0, S1, TAU, KAP = 0.0465, 7.5, 0.080, 0.2213, 4.0, 0.012
SC_K = 0.046
MAND_SUP, MAND_INF = 28.0, 36.7   # cm, de la fuente a las mandíbulas Y (superiores) y X (inferiores)
ALFA0, ALFA1 = 0.00515, -0.00099  # el intercambio «loglineal», ajustado a la tabla abierta real del 600C (logs/UM2_v2/estudio_A2/a2_01_tabla_real.txt)
TH = (np.arange(7200) + 0.5) * 2 * np.pi / 7200


def tmr0(d):
    return np.exp(-MU * (d - DMAX))


def s_inf(d):
    x = d - DMAX
    return S0 + S1 * (1 - np.exp(-x / TAU)) * np.exp(-KAP * x)


def g(x, y):
    """Fracción del núcleo de dispersión que cubre un rectángulo centrado."""
    r = np.minimum((x / 2) / np.abs(np.cos(TH)), (y / 2) / np.abs(np.sin(TH)))
    return float(1 - np.mean(np.exp(-r / LAM)))


G10 = g(10.0, 10.0)


def sc_cuadrado(s):
    return float(1 + SC_K * np.log(s / 10.0))


class Mundo:
    """Un haz simulado. `intercambio`: «geometria» (el original: Sc con el equivalente de vista desde el punto, apéndice B de la TG-71) o «loglineal» (arriba).
    `maniqui`: «rectangulo» (el original: el núcleo integrado sobre el campo) o «4A/P» (el campo visto por su cuadrado equivalente)."""

    def __init__(self, intercambio="geometria", maniqui="rectangulo"):
        assert intercambio in ("geometria", "loglineal") and maniqui in ("rectangulo", "4A/P")
        self.intercambio, self.maniqui = intercambio, maniqui

    def _g(self, x, y):
        s = 2 * x * y / (x + y)
        return g(x, y) if self.maniqui == "rectangulo" else g(s, s)

    def sp(self, x, y):
        return (1 + S0 * self._g(x, y)) / (1 + S0 * G10)

    def tmr(self, d, x, y):
        gg = self._g(x, y)
        return (tmr0(d) + s_inf(d) * gg) / (1 + S0 * gg)

    def sc_mandibulas(self, x, y):
        """x: mandíbulas X (inferiores); y: mandíbulas Y (superiores), en el isocentro."""
        if self.intercambio == "geometria":
            f = MAND_SUP * (SAD - MAND_INF) / (MAND_INF * (SAD - MAND_SUP))
            return sc_cuadrado((f + 1) * y * x / (f * y + x))
        return sc_cuadrado(2 * x * y / (x + y)) * float((y / x) ** (ALFA0 + ALFA1 * np.log(np.sqrt(x * y) / 10.0)))

    def dosis_por_um(self, x_j, y_j, x_ef, y_ef, ssd, d):
        """Dosis por UM (D'0 = 1 cGy/UM en 10 × 10, punto a 100 cm, dmax) en un punto del eje."""
        f = (ssd + d) / SAD
        return self.sc_mandibulas(x_j, y_j) * self.sp(x_ef * f, y_ef * f) * self.tmr(d, x_ef * f, y_ef * f) * (SAD / (ssd + d)) ** 2

    def tablas_medidas(self, lados_pdd, xs, ys, d0=5.0, ssd0=100.0, paso_mm=1):
        """Lo que se mediría en esa máquina, redondeado como las tablas reales: PDD a 0.1 % y factores a 0.001 (filas = Y, columnas = X)."""
        z = np.arange(DMAX, 30.0 + 1e-9, paso_mm / 10)
        pdd = np.array([[round(100 * self.dosis_por_um(s, s, s, s, ssd0, float(dz)) / self.dosis_por_um(s, s, s, s, ssd0, DMAX), 1) for dz in z] for s in lados_pdd])
        ref = self.dosis_por_um(10.0, 10.0, 10.0, 10.0, ssd0, d0)
        of = np.array([[round(self.dosis_por_um(x, y, x, y, ssd0, d0) / ref, 3) for x in xs] for y in ys])
        return z, pdd, of, self.dosis_por_um(10.0, 10.0, 10.0, 10.0, ssd0, DMAX)


_ORIGINAL = Mundo()
sp, tmr, sc_mandibulas, dosis_por_um, tablas_medidas = _ORIGINAL.sp, _ORIGINAL.tmr, _ORIGINAL.sc_mandibulas, _ORIGINAL.dosis_por_um, _ORIGINAL.tablas_medidas
