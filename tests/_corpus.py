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

# Series Catphan reales (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md, A.0).
# CATPHAN_RAIZ es distinto de RAIZ: estas series viven directo bajo
# Archivos_UseApp, no bajo "Archivos QA". Referencias de oro (pylinac
# 3.45.0 sobre cada una) en tests/_catphan_oro.py.
CATPHAN_RAIZ = os.path.expanduser("~/Documents/Archivos_UseApp")
CATPHAN = {
    "TOMOGRAFO": "QA tomografo Catphan",
    "HALCYON_SEP": "QA Halcyon Catphan",
    "HALCYON_JUN": os.path.join("DICOM", "CatphanHalcyonJunio2026"),
    # PR.0 (05-10-2026, DP-151): estas dos carpetas se renombraron (`CATPHANKV` -> `CATPHANKV-Halcyon`,
    # `Catphandiciembre` -> `Catphandiciembre-iX`) y 133 pruebas se saltaron en silencio. Si vuelve a pasar,
    # `tests/test_pr0_corpus_completo.py` falla nombrando la serie que falta.
    "HALCYON_236": os.path.join("DICOM", "CATPHANKV-Halcyon"),
    "IX_DIC": os.path.join("DICOM", "Catphandiciembre-iX"),
    "MIXTA": "Catphan",
}


def serie_catphan(clave):
    """Ruta a una serie Catphan real, o None si no existe (skip honesto).

    `clave`: una de las llaves de CATPHAN ('TOMOGRAFO', 'HALCYON_SEP',
    'HALCYON_JUN', 'HALCYON_236', 'IX_DIC', 'MIXTA').
    """
    ruta = os.path.join(CATPHAN_RAIZ, CATPHAN[clave])
    return ruta if os.path.isdir(ruta) else None


# SE.0 (05-10-2026, DP-149): carpetas reales que llegaron del hospital con un caso que la app tiene que seguir resolviendo. Van APARTE de CATPHAN
# a proposito: CATPHAN son las seis series con referencias de oro de pylinac, y de ella iteran pruebas que exigen un valor esperado por cada
# clave (`sorted(CATPHAN)` en test_b2, test_b3 y test_a0); una clave nueva ahi las obligaria a declarar expectativas que nadie midio.
# La regla de PR.0 (si el corpus esta, tienen que estar TODAS las series declaradas) cubre los dos registros.
CORPUS_HOSPITAL = {
    # 20260928: la serie axial (151 cortes, 120 kV / 343 mA / 2.0 mm) MAS un topograma (`LOCALIZER`, `SliceLocation` -135.5, espesor vacio)
    # en la misma carpeta: la que no dejaba guardar en la version desplegada.
    "TOMOGRAFO_SEP26": os.path.join("DICOM", "QA Tac Septiembre 2026", "20260928 QA Tomografo Septiembre"),
}


def todas_las_series_declaradas():
    """`{clave: ruta relativa a CATPHAN_RAIZ}` de TODAS las series del corpus de imagenes (CATPHAN y CORPUS_HOSPITAL): la que mira la regla de PR.0
    (`tests/test_pr0_corpus_completo.py`: si el corpus esta, tienen que estar todas)."""
    return {**CATPHAN, **CORPUS_HOSPITAL}


def serie_hospital(clave):
    """Ruta a una carpeta real del hospital (CORPUS_HOSPITAL), o None si no existe (skip honesto)."""
    ruta = os.path.join(CATPHAN_RAIZ, CORPUS_HOSPITAL[clave])
    return ruta if os.path.isdir(ruta) else None


# PF.0 (12-10-2026, PLAN_ANALISIS_PELICULAS_08-10.md): las PELICULAS radiocromicas reales del físico. Viven FUERA del repo, en su propia raíz
# (no bajo `RAIZ` ni bajo `CATPHAN_RAIZ`): `ImagenesDeReferencia/PlacasHistoricas` (SOLO LECTURA; paso 14 del protocolo del plan). El repo no guarda
# imágenes grandes (el hook admite 1 MB solo en `tests/datos/`; ML0.JPG pesa 2.8 MB), así que las pruebas con películas reales leen este corpus
# y las sintéticas (`_placa_mensual_sintetica.py`, `_placa_braqui_sintetica.py`) se generan en memoria con semilla fija.
# La regla de PR.0 se aplica a esta raíz (`tests/test_pr0_corpus_completo.py::verificar_peliculas`): si la carpeta existe y falta una película
# declarada, FALLA nombrándola; si la carpeta no existe, salta.
PELICULAS_RAIZ = os.path.expanduser("~/Documents/CodigosPython/ImagenesDeReferencia/PlacasHistoricas")
# clave -> archivo (relativo a PELICULAS_RAIZ). Control MENSUAL de aceleradores (campo luminoso de 10 x 10 cm sobre película radiocrómica).
PELICULAS_MENSUALES = {
    "ML0": "ML0.JPG",                          # la película del cuaderno del físico, recortada: 2690 x 2710 px a 600 dpi
    "EPSON027": "EPSON027.JPG",                # la PÁGINA entera del escáner de la que sale ML0 (5100 x 6600)
    "EPSON007": "EPSON007.JPG",
    "EPSON008_TIF": "EPSON008.TIF",            # TIFF RGBA de 8 bits con alfa opaco (H9)
    "EPSON030": "EPSON030.JPG",                # página entera
    "EPSON001_JPG": "EPSON001.jpg",
    "EPSON001_TIF": "EPSON001.TIF",            # la misma película que EPSON001.jpg, en TIFF RGBA de 8 bits
    "PLACA_REF40": "placa_ref40.jpeg",         # la imagen que se subió en el control ref 40
    "EPSON028": "EPSON028.JPG",                # página entera
    "EPSON029": "EPSON029.JPG",                # página entera
    "PLACA_REF6": "placa_ref6.jpeg",           # la imagen del control ref 6: es EXACTAMENTE EPSON001.jpg (mismo md5; ver MISMO_ARCHIVO)
}
# Posición inicial de la fuente de braquiterapia (película recortada o página entera). Son las que usan los tests de PI.*, que guardan
# copias en `tests/datos/` (ver COPIAS_EN_EL_REPO) porque no pasan del límite de 1 MB de ese directorio.
PELICULAS_BRAQUI = {
    "BRAQUI_00_JPEG": "braqui_00.jpeg",        # 1328 x 467, escaneada a 600 dpi y retocada en gThumb
    "BRAQUI_00_JPG": "braqui_00.JPG",          # otro recorte de la misma página: 1337 x 473
    "EPSON009": "EPSON009.jpeg",               # la TÍPICA: un TIFF RGBA de Paint con la extensión .jpeg y 96.012 dpi declarados
    "EPSON031": "EPSON031.JPG",                # el escaneo crudo (página entera) de la que sale braqui_00
}
# OD.1 (21-10-2026, DA-87; ronda 1 de revision, OD1-REV-PRU-02): las DOS peliculas VIRGENES TIFF que el fisico escaneo el 21-10, el ORACULO de la pelicula virgen de `tests/test_od1_densidad_optica.py`:
# EPSON178 (ajustes automaticos del escaner: R 193, G 240, gris 212, fuera del rango de una pelicula sin irradiar: se rechaza solo por el rango) y EPSON179 (la cadena de las mensuales: una hoja de 210.9 x 279.1 mm en una
# pagina carta; su media por capa R 152.12, G 194.11, B 86.77, gris 169.30 y las cuatro piezas de 10 x 10 cm y la hoja sin fondo que se arman con trozos suyos). Pesan 99 MB cada una. Registro APARTE de los dos
# de arriba a proposito (igual que CORPUS_HOSPITAL junto a CATPHAN): las pruebas de A.1 y de PF.0 iteran `todas_las_peliculas_declaradas()` y exigen su forma, sus 23 nombres y sus capturas de HEAD. La regla de PR.0 las
# mira igual (`peliculas_vigiladas_por_pr0()`): si la carpeta de peliculas existe y falta una, FALLA nombrandola. Antes de declararlas, un renombre apagaba 13 pruebas de OD.1 sin un solo rojo (la clase de DP-151).
PELICULAS_VIRGENES = {
    "VIRGEN_EPSON178": "EPSON178.TIF",
    "VIRGEN_EPSON179": "EPSON179.TIF",
}
# Lo que se midió de cada película (12-10-2026) y que las pruebas dan por sentado: (ancho, alto, formato real según Pillow). Si el físico
# reemplaza un archivo por otro distinto, la prueba lo nombra y se corrige AQUÍ.
FORMA_DE_LAS_PELICULAS = {
    "ML0": (2690, 2710, "JPEG"), "EPSON027": (5100, 6600, "JPEG"), "EPSON007": (2736, 2704, "JPEG"), "EPSON008_TIF": (2728, 2720, "TIFF"),
    "EPSON030": (5100, 6600, "JPEG"), "EPSON001_JPG": (2720, 2860, "JPEG"), "EPSON001_TIF": (2720, 2860, "TIFF"),
    "PLACA_REF40": (2633, 2673, "JPEG"), "EPSON028": (5100, 6600, "JPEG"), "EPSON029": (5100, 6600, "JPEG"), "PLACA_REF6": (2720, 2860, "JPEG"),
    "BRAQUI_00_JPEG": (1328, 467, "JPEG"), "BRAQUI_00_JPG": (1337, 473, "JPEG"), "EPSON009": (1156, 672, "TIFF"), "EPSON031": (5100, 6600, "JPEG"),
}
# Dos claves que son el MISMO archivo (mismo contenido byte a byte) bajo dos nombres.
MISMO_ARCHIVO = {"PLACA_REF6": "EPSON001_JPG"}
# Las películas de braqui que `tests/datos/` ya guarda (nombre del archivo en `tests/datos/`): deben ser idénticas a las del corpus.
COPIAS_EN_EL_REPO = {"BRAQUI_00_JPEG": "braqui_00.jpeg", "EPSON009": "EPSON009.jpeg", "EPSON031": "EPSON031.JPG"}


def peliculas_vigiladas_por_pr0():
    """`{clave: archivo relativo a PELICULAS_RAIZ}` de TODAS las peliculas que la regla de PR.0 vigila (si la carpeta existe, tienen que estar todas): las declaradas (mensuales y de braqui) MAS las virgenes de OD.1 (`PELICULAS_VIRGENES`,
    registro aparte para no entrar a las pruebas que iteran `todas_las_peliculas_declaradas()`)."""
    return {**todas_las_peliculas_declaradas(), **PELICULAS_VIRGENES}


def todas_las_peliculas_declaradas():
    """`{clave: archivo relativo a PELICULAS_RAIZ}` de TODAS las películas del corpus externo (mensuales y de braqui): la que mira la regla de
    PR.0 aplicada a PELICULAS_RAIZ (`tests/test_pr0_corpus_completo.py::verificar_peliculas`). Aparte de `todas_las_series_declaradas()`: son
    otra raíz y otro tipo de dato (archivos, no carpetas)."""
    return {**PELICULAS_MENSUALES, **PELICULAS_BRAQUI}


def pelicula(clave):
    """Ruta a una película real del corpus, o None si no existe (skip honesto)."""
    ruta = os.path.join(PELICULAS_RAIZ, peliculas_vigiladas_por_pr0()[clave])
    return ruta if os.path.isfile(ruta) else None


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
