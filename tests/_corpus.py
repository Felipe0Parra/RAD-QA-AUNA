"""Fuente única de rutas del corpus real del físico para los tests (HI-0).

El corpus vive FUERA del repo y FUERA de control de versiones; el físico lo
reorganiza legítimamente. Antes cada test hardcodeaba su ruta -> una mudanza
rompía N archivos y algunos FALLABAN en vez de SKIP. Aquí se centraliza:
cuando el corpus se mueva otra vez, se edita SOLO este archivo.

NAMING (importante, para no confundir dos conjuntos de datos distintos):
- "PrimerosMeses" son las PRIMERAS mediciones del físico (Ene-Jun). Son las que
  cruzan con la tabla `dosimetriaMen` y sirven de patrón de oro en mcc_metrics /
  D4.1b. El 2026-07-15 el físico las agrupó bajo `Archivos QA/PrimerosMeses/`
  (antes estaban sueltas como `Archivos QA/{Mes}/`).
- "2024" es OTRO conjunto de mediciones, intacto bajo `Archivos QA/2024/`. NO
  confundir `2024/{Mes}` con `PrimerosMeses/{Mes}` aunque compartan el nombre
  del mes: son datos diferentes y los usan tests diferentes.

Este archivo NO empieza por `test_`, así pytest no lo colecciona como test.
"""
import os

RAIZ = os.path.expanduser("~/Documents/Archivos_UseApp/Archivos QA")

# Primeras mediciones (Ene-Jun): agrupadas en PrimerosMeses/ el 2026-07-15.
# Cruzan con dosimetriaMen (oro de mcc_metrics / D4.1b).
MESES_PRIMEROS = os.path.join(RAIZ, "PrimerosMeses")
# Corpus 2024: intacto, directo bajo 2024/. Datos DISTINTOS de PrimerosMeses.
CORPUS_2024 = os.path.join(RAIZ, "2024")
# PDFs de normativa: movidos a NormaYEquipos_pdf/ el 2026-07-15.
PDF_REV1 = os.path.join(RAIZ, "NormaYEquipos_pdf", "p15048-DOC-010-398-Rev1_web.pdf")
PDF_2000 = os.path.join(RAIZ, "NormaYEquipos_pdf", "TRS_398s_Web.pdf")
# Hoja Halcyon suelta: movida a PrimerosArchivosPruebas/ el 2026-07-15.
# (El usuario corrigió el nombre de la carpeta de "PrimeosArchivosPrueba" a
# "PrimerosArchivosPruebas"; verificado en disco 2026-07-15.)
HALCYON_DMAX = os.path.join(
    RAIZ, "PrimerosArchivosPruebas", "TRS-398 6 MV FFF Halcyon Dmax.xls")
# Reportes MPC diarios del Halcyon (carpetas `HAL-TRT-SN1161-<fecha>-<hora>...`).
# Es el corpus que sostiene J1 y H2: la selección de carpeta por completitud.
# Solo se LEE, y solo el Results.csv de cada carpeta (~20 KB); las imágenes
# `.xim` pesan ~124 MB por corrida y ningún test las abre.
MPC_HALCYON = os.path.join(RAIZ, "ReportesDiariosQA001", "ReportesDiarioHalcyon")

# Grafía may/min inconsistente por mes en el corpus real (organización del
# físico, no de la app) -- igual que en test_corpus_2024_cross_check.
GRAFIAS_IX = ("IX", "iX", "Cinac IX", "Clinac IX")


def mes_primeros(mes, maquina, sub=None):
    """Ruta a una carpeta de un mes de PrimerosMeses, tolerando la grafía IX/iX.

    `maquina`: '600' | 'Halcyon' | 'IX'. `sub`: 'Fotones' | 'Electrones' | None.
    Devuelve la primera ruta existente, o None si ninguna existe -- para que el
    llamador haga SKIP honesto, nunca un fallo por ausencia de archivos.
    """
    candidatas = GRAFIAS_IX if maquina == "IX" else (maquina,)
    for gm in candidatas:
        base = os.path.join(MESES_PRIMEROS, mes, gm)
        ruta = os.path.join(base, sub) if sub else base
        if os.path.isdir(ruta):
            return ruta
    return None
