"""Referencias de oro de pylinac 3.45.0 sobre las 5 series Catphan reales.

Medidas en CARACTERIZACION_CATPHAN_EQUIPOS_18-09.md y repetidas en
PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md §0.8. Sirven de referencia para
los tests de A.0-B.3: cuentas de archivos (carga), y valores de pylinac
"tal cual" o con las dos extensiones validadas (volteo del volumen, límite
de homogeneidad configurable) donde el motor de la app aún no existe.

Este archivo NO empieza por `test_`, así pytest no lo colecciona como test.
"""

# Cuenta de archivos .dcm por serie -- verificación de carga en A.0.
N_ARCHIVOS = {
    "TOMOGRAFO": 102,
    "HALCYON_SEP": 122,
    "HALCYON_JUN": 124,
    "HALCYON_236": 124,
    "IX_DIC": 71,
    "MIXTA": 401,
}

# Tolerancias numéricas de comparación (§0.9 / apéndice de A.0).
TOL_HU = 0.5
TOL_MM = 0.005
TOL_LPMM = 0.002

# HU medidos de los 7 materiales del CTP404, en el orden
# (Aire, PMP, LDPE, Poliestireno, Acrílico, Delrín, Teflón).
HU_MATERIALES = {
    "TOMOGRAFO": (-1000, -185, -95, -37, 121.5, 322, 916),
    "HALCYON_JUN": (-979.5, -201, -112, -59, 94, 312, 888.5),
    "HALCYON_236": (-994.5, -213, -115, -73, 90, 315, 870),
    # Serie de septiembre: el fantoma está invertido 180°; estos valores
    # son los que da pylinac YA VOLTEADO (extensión validada).
    "HALCYON_SEP": (-965, -180, -93, -46, 103, 312.5, 894.5),
    # iX: pylinac no localiza sin el límite de homogeneidad configurable
    # (extensión validada, límite 150 HU); estos son los HU con esa
    # extensión aplicada. El desplazamiento grande frente a los otros
    # equipos es real (cupping/miscalibración del iX, D-05/H3).
    "IX_DIC": (-605, 207, 290, 379, 601, 874, 1539),
}

# Espesor medido (mm) y espesor nominal (mm) entre paréntesis en el plan.
ESPESOR_MM = {
    "TOMOGRAFO": (1.92, 2.0),
    "HALCYON_JUN": (1.823, 2.0),
    "HALCYON_236": (1.845, 1.99),
    "HALCYON_SEP": (1.859, 2.0),
    "IX_DIC": (2.336, 2.5),
}

# Precisión geométrica: promedio de las 4 distancias CTP404 (nominal 50 mm).
GEOMETRIA_MM = {
    "TOMOGRAFO": 50.019,
    "HALCYON_JUN": 50.003,
    "HALCYON_236": 50.041,
    "HALCYON_SEP": 50.009,
    "IX_DIC": 49.932,
}

# Índice de uniformidad (CTP486).
UI = {
    "TOMOGRAFO": 0.20,
    "HALCYON_JUN": 1.23,
    "HALCYON_236": -1.32,
    "HALCYON_SEP": 1.01,
    "IX_DIC": 3.47,
}

# MTF50 en lp/mm (CTP528).
MTF50_LPMM = {
    "TOMOGRAFO": 0.288,
    "HALCYON_JUN": 0.298,
    "HALCYON_236": 0.283,
    "HALCYON_SEP": 0.300,
    "IX_DIC": 0.433,
}

# Cuántas ROIs del grupo 1% de bajo contraste (CTP515) resultan visibles.
BAJO_CONTRASTE_VISIBLES = {
    "TOMOGRAFO": 2,
    "HALCYON_JUN": 4,
    "HALCYON_236": 5,
    "HALCYON_SEP": 4,
    "IX_DIC": 0,
}

# Correlación de Pearson HU-medido vs HU-nominal, orientación correcta y
# equivocada -- regla de orientación validada (umbral 0.95).
CORRELACION_ORIENTACION = {
    "TOMOGRAFO": (0.999, 0.266),
    "HALCYON_JUN": (1.000, 0.254),
    "HALCYON_236": (0.999, 0.256),
    "HALCYON_SEP": (1.000, 0.263),  # el primer valor es YA VOLTEADA
    "IX_DIC": (0.999, None),  # no se midió la rama equivocada para el iX
}
UMBRAL_CORRELACION_ORIENTACION = 0.95

# Límite de homogeneidad de find_origin_slice que hace localizable al iX
# (extensión validada B.1/B.2); el tomógrafo no cambia con este límite.
# Verificado empíricamente (A.0): con este límite, ctp404.slice_num del
# iX da 42 -- coincide exactamente con "origen 42" de §0.8 del plan.
LIMITE_HOMOGENEIDAD_IX = 150

# NOTA (A.0, hallazgo al verificar contra pylinac real): el "z=172"/"z=170"
# que D-02 (§0.5) cita para el tomógrafo NO es slice_num -- es la
# coordenada z física (mm) del corte en ese índice, no un índice ni un
# número de corte. Confirmado midiendo directamente: ctp404.slice_num del
# tomógrafo es 47 (0-based), y el criterio real y no ambiguo de la
# verificación es el de §15 (puerta de salida): "el corte sugerido para el
# CTP404 es el 48 (antes 47)" -- 47+1 tras el arreglo de A.2, 46+1=47 con
# el bug de hoy. Cada tarea (A.1/A.2) calcula su propio "rojo antes que
# verde" corriendo pylinac en vivo, no contra un número guardado aquí --
# los valores de posición dependen del orden exacto que A.1 construye.
