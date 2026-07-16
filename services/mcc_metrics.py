"""Simetría y planicidad desde perfiles .mcc (Fase D4.1b, PLAN_FASE_K_D4.md
Seccion 3, "Convencion de simetria/planicidad por DESCUBRIMIENTO EMPIRICO").

El software PTW que genera los .mcc no expone su formula interna de
simetria/planicidad. El patron de oro es la tabla `dosimetriaMen` de
`AUNA_2026_2/BaseDatosQA.db` (37 filas, transcritas a mano del software PTW).
Este modulo fue calibrado contra 6 pares BD<->corpus real (refs 16, 13, 30,
35 de Clinac iX; 22, 38 de Clinac 600 -- 26 filas, 104 valores individuales
simetria+planicidad in/crossplane) usando el corpus real de
~/Documents/Archivos_UseApp/Archivos QA/, NO datos sinteticos.

Candidatos probados (ver PLAN_FASE_K_D4.md): point-difference vs ratio para
simetria; IAEA-diff vs IEC-delta-ratio para planicidad; in_field_ratio
barrido en pasos finos de 0.55 a 0.90; con y sin filtro gaussiano previo;
columna 2 vs columna 3 de BEGIN_DATA como señal (columna 3 resulto ser un
canal de referencia/monitor casi constante en posicion -- NO el perfil; ver
docstring de EscaneoMCC en mcc_PTW_read/mcc_read.py).

Resultado (mejor ajuste encontrado, error medio absoluto sobre las 104
comparaciones):
  - Simetria: point-difference (pylinac SymmetryPointDifferenceMetric),
    in_field_ratio=0.70, SIN filtrar. MAE=0.13 (rango real de la BD: 0.2-2.2).
  - Planicidad: NO es la formula IAEA-diff estandar (100*(max-min)/(max+min)
    con in_field_ratio=0.70..0.80) -- esa da un sesgo sistematico de -0.5 a
    -1.4 en TODAS las filas (siempre por debajo del valor PTW), señal de que
    la ventana/formula real de PTW es otra, no solo un ajuste de ratio.
    La forma que SI reproduce sin sesgo sistematico es la "delta-ratio" IEC
    (100*(max/min - 1)), in_field_ratio=0.63, SIN filtrar. MAE=0.30, sesgo
    medio +0.10 (practicamente sin sesgo), 96% de los valores dentro de
    ±1.0 del valor PTW (rango real: 1.85-4.53). Los 2 valores fuera de ese
    margen son transcripciones aisladas (ver test_mcc_metrics.py), no un
    patron -- se documentan y toleran, no se persiguen mas (mismo criterio
    que autoriza el plan: "transcripciones manuales, tolerar outliers
    puntuales, decidir por mayoria").

Ambos ratios (0.70 y 0.63) son AJUSTES EMPIRICOS contra los 6 pares
disponibles, no vienen de un estandar publicado -- si en el futuro hay mas
filas de referencia (mas meses cargados), vale la pena re-correr el barrido
en tests/test_mcc_metrics.py::TestExploracion (o el script equivalente) y
confirmar que siguen siendo el mejor ajuste.
"""
import numpy as np
from pylinac.core.profile import FWXMProfile, SymmetryPointDifferenceMetric

RATIO_SIMETRIA = 0.70
RATIO_PLANICIDAD = 0.63


def _perfil(escaneo):
    return FWXMProfile(values=np.array(escaneo.col2, dtype=float),
                        x_values=np.array(escaneo.posiciones, dtype=float))


def calcular_simetria(escaneo):
    """Point-difference symmetry (%), ver docstring del modulo."""
    perfil = _perfil(escaneo)
    valor = perfil.compute(SymmetryPointDifferenceMetric(in_field_ratio=RATIO_SIMETRIA))
    return round(abs(valor), 2)


def calcular_planicidad(escaneo):
    """Delta-ratio IEC (%): 100*(max/min - 1) dentro de RATIO_PLANICIDAD.
    NO es FlatnessDifferenceMetric/FlatnessRatioMetric de pylinac tal cual
    -- ver docstring del modulo (la formula IAEA-diff no reproduce los
    valores de dosimetriaMen; esta si, dentro de tolerancia documentada)."""
    perfil = _perfil(escaneo)
    valores = perfil.field_values(in_field_ratio=RATIO_PLANICIDAD)
    return round(100 * (valores.max() / valores.min() - 1), 2)


def calcular_simetria_planicidad(curvas):
    """curvas: dict {curve_type: EscaneoMCC} (valor de agregar_carpeta()[energia]),
    debe traer INPLANE_PROFILE y CROSSPLANE_PROFILE. Devuelve los 4 numeros
    crudos listos para el formulario mensual (ln_simetria_inplane_<energia>,
    etc. -- el cableado UI y las tolerancias/discrepancias son de D4.2, este
    modulo solo calcula)."""
    inplane = curvas["INPLANE_PROFILE"]
    crossplane = curvas["CROSSPLANE_PROFILE"]
    return {
        "simetria_inplane": calcular_simetria(inplane),
        "simetria_crossplane": calcular_simetria(crossplane),
        "planicidad_inplane": calcular_planicidad(inplane),
        "planicidad_crossplane": calcular_planicidad(crossplane),
    }


def calcular_calidad_fotones(escaneo_pdd):
    """TPR20,10 (calidad de haces de FOTONES) desde un PDD medido -- H4.1,
    auditoría 2026-07-16.

    A diferencia de simetria/planicidad (ajuste EMPIRICO propio, sin
    protocolo publicado -- ver docstring del modulo), esta formula SI es un
    protocolo estandar publicado, citado textualmente en el catalogo PTW
    (~/Documents/Archivos_UseApp/Archivos QA/NormaYEquipos_pdf/
    DETECTORS_Cat_en_16522900_16.pdf, pag. 84, seccion "4.1 IAEA TRS-398",
    ec. 4-2) y en IAEA TRS-398 directamente:

        TPR20,10 = 1.2661 * PDD20,10 - 0.0595

    donde PDD20,10 = M20/M10, la razon entre las lecturas del PDD a 20 cm y
    10 cm de profundidad (SSD=100cm, campo 10x10 en la superficie del
    fantoma -- las mismas condiciones con las que se mide el PDD del .mcc).
    Como es una RAZON, la normalizacion al maximo de la curva se cancela
    algebraicamente -- por eso aqui se interpola col2 (dosis relativa cruda,
    ver EscaneoMCC) directamente a 200/100 mm sin normalizar.

    Valido SOLO para haces de fotones aplanados (FF); no se llama para
    electrones (calidad de electrones es R50, formula distinta, y los
    valores de "calidad" de electrones en dosimetriaMen -- H4.4 -- ni
    siquiera son R50: pregunta abierta al fisico, sin formula todavia).

    Validado (2026-07-16) contra las filas de oro de dosimetriaMen
    (refs 16/13/30/35/22/38, columna calidad_pdd20_10, fotones 6mv/15mv):
    8 de 10 exactas a 4 decimales; las 2 de ref 16/Febrero difieren en
    ~0.005 (esa carpeta tiene escaneos de PDD repetidos el mismo dia --
    ver docstring de mcc_PTW_read/mcc_read.py sobre el caso "E06 PDDCRIN" --
    la transcripcion manual del fisico pudo venir del otro escaneo)."""
    posiciones = np.asarray(escaneo_pdd.posiciones, dtype=float)
    valores = np.asarray(escaneo_pdd.col2, dtype=float)
    orden = np.argsort(posiciones)
    posiciones, valores = posiciones[orden], valores[orden]
    m10 = np.interp(100.0, posiciones, valores)
    m20 = np.interp(200.0, posiciones, valores)
    return round(1.2661 * (m20 / m10) - 0.0595, 4)
