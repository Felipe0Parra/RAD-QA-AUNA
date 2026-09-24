"""D.0 (PLAN_HANDOFF_IMAGENES_22-09.md): la geometría del fantoma sale del
HU, nunca de la ventana de visualización.

Causa medida en §0.9 del plan: los sitios que construían `GeometriaCatphan`
le pasaban la imagen YA ventaneada a 8 bits (`get_volumen_normalizado(wl,
ww)[corte]`); el centro detectado se movía hasta 15 mm según dónde
estuviera el WL/WW del deslizador, y en 5-6 de cada 24 ventanas probadas la
detección fallaba en silencio y caía al centro geométrico de la imagen. De
ahí salían el anillo de resolución "excéntrico" que reportó el físico y la
mitad de los fallos de la resolución de contraste ("muchas veces no
funciona").

Los 5 puntos de verificación del plan, en orden:
  (a) invariancia -- el mismo corte, con tres ventanas de VISUALIZACIÓN muy
      distintas, da el mismo centro (a través de un sitio de producción
      real: `resolucion_contraste`, cuyo conteo de ROI visibles SÍ dependía
      de dónde cayera el centro absoluto -- a diferencia de una medida
      relativa como `tamano_pixel`, que sería ciega al defecto).
  (b) exactitud -- el centro que detecta la app queda a <= 0.5 mm del que
      da pylinac, en las 5 series reales del corpus.
  (c) el escenario del físico -- "Elegir corte" dos veces seguidas con el
      deslizador en sitios distintos da el mismo anillo y los mismos
      números, sobre un volumen real cargado con `DicomVolume`.
  (d) resolución de contraste -- `CatphanHalcyonJunio2026` pasa de 2/6 (el
      número medido en §0.9 con la ventana inicial y el código viejo) a
      >= 4/6, sin importar la ventana.
  (e) tripwire estructural -- `GeometriaCatphan`/`GeometriaCatphanCT`
      rechazan con `TypeError` una imagen de 8 bits, y un censo derivado
      del código (AST, no una lista copiada a mano) de todo sitio que las
      construya: si aparece uno nuevo, esta prueba lo nombra.
"""
import ast
import os
import types
import warnings
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from _catphan_oro import LIMITE_HOMOGENEIDAD_IX
from _corpus import serie_catphan
from analisisImagenes.catphan import motor
from analisisImagenes.catphan.serie import leer_serie
from analisisImagenes.catphan.criterios import PARAMETROS_HEREDADOS  # G.3: los umbrales viven en un solo sitio
from analisisImagenes.Analisis_Catphan_TAC import resolucion_contraste
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume, GeometriaCatphan
from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT

TOL_EXACTITUD_MM    = 0.5   # (b) -- contra el centro de pylinac
TOL_INVARIANCIA_MM  = 0.1   # (a) -- entre las tres ventanas de visualización

# Ventanas de visualización MUY distintas -- lo que el físico llama "WL/WW
# en el límite" (§0.9: con los rangos al máximo el error baja de 13-15 mm a
# 0.4-0.95 mm; aquí se exige que ni siquiera eso quede, porque D.0 saca la
# ventana por completo del camino de la geometría).
VENTANAS_MUY_DISTINTAS = ((40, 400), (500, 2000), (-200, 100))

# Límite de homogeneidad por serie -- igual que en test_b1 (B.1/B.2 del plan
# del 18-09): el iX no localiza sin él, los demás no cambian con él.
_LIMITE_POR_SERIE = {
    "TOMOGRAFO": None,
    "HALCYON_JUN": None,
    "HALCYON_SEP": None,
    "HALCYON_236": None,
    "IX_DIC": LIMITE_HOMOGENEIDAD_IX,
}

_MODULOS_PYLINAC = ("ctp404", "ctp486", "ctp515", "ctp528")


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


def _ct_analizado(clave):
    """El objeto pylinac ya analizado, con el volteo aplicado si el fantoma
    está invertido -- misma construcción que usa `motor.analizar` (B.1/B.2),
    para no duplicar la lógica de orientación: eso es D.1, no D.0. Aquí solo
    se necesita el objeto para leer, por módulo, en qué corte cae y dónde
    puso pylinac el centro -- ambos en pylinac 3.45.0.
    """
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    perfil = types.SimpleNamespace(
        limite_variacion_hu=_LIMITE_POR_SERIE[clave], nombre=clave
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = motor.analizar(serie, perfil)
        rutas = [c.ruta for c in serie.cortes]
        ct = motor._construir(rutas, _LIMITE_POR_SERIE[clave])
        if resultado.orientacion == "invertido":
            motor._voltear_volumen(ct)
        motor._analizar_una_vez(ct, None, {})
    return ct


def _hu_y_tam_px(ct, modulo):
    """(corte HU en float32, tam_px en mm) del corte que pylinac usó para
    `modulo` ('ctp404'/'ctp486'/'ctp515'/'ctp528'), en el MISMO marco que
    `ct` -- ya volteado si la serie está invertida. La traducción a los
    índices sin voltear (los que muestra la pantalla) es D.1, no D.0: aquí
    basta con un corte HU real y su centro de referencia de pylinac.
    """
    mod = getattr(ct, modulo)
    img = ct.dicom_stack[mod.slice_num]
    hu = np.asarray(img.array, dtype=np.float32)
    tam_px = float(img.dpmm) ** -1
    centro_pylinac = (float(mod.phan_center.x), float(mod.phan_center.y))
    return hu, tam_px, centro_pylinac


def _ventanear(hu, wl, ww):
    """Misma fórmula que `DicomVolume.get_volumen_normalizado`, para un solo
    corte -- construye exactamente la imagen que vería la pantalla con ese
    WL/WW. D.0 prohíbe que esta imagen llegue a `GeometriaCatphan`."""
    lo, hi = wl - ww / 2, wl + ww / 2
    return ((np.clip(hu, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────
# (a) Invariancia -- a través de un sitio de producción real
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("clave", sorted(_LIMITE_POR_SERIE))
def test_a_resolucion_contraste_no_depende_de_la_ventana(clave):
    """`resolucion_contraste` (real, de producción) recibe siempre las dos
    imágenes -- `corte_255` para dibujar, `corte_hu` para la geometría.
    Con tres ventanas de visualización MUY distintas, el número de ROI
    visibles (que depende de dónde cae el centro absoluto, no de una
    distancia relativa) tiene que salir IDÉNTICO las tres veces. Antes de
    D.0 no lo era: §0.9 midió `CatphanHalcyonJunio2026` en 2/6 con la
    ventana inicial y 4/6 con la del DICOM -- la misma imagen, dos
    veredictos.
    """
    ct = _ct_analizado(clave)
    hu, tam_px, _ = _hu_y_tam_px(ct, "ctp515")

    conteos = []
    for wl, ww in VENTANAS_MUY_DISTINTAS:
        corte_255 = _ventanear(hu, wl, ww)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resultado = resolucion_contraste(
                corte_255, hu, tam_px, visualizar=False,
                **PARAMETROS_HEREDADOS["resolucion_contraste"],
            )
        conteos.append(resultado["resumen"]["rois_visibles_cnr"])

    assert len(set(conteos)) == 1, (
        f"{clave}: rois_visibles_cnr cambió con la ventana de visualización "
        f"({conteos}) -- la geometría no puede depender de WL/WW (D.0)"
    )


# ─────────────────────────────────────────────────────────────────────────
# (b) Exactitud -- contra el centro que da pylinac
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("clave", sorted(_LIMITE_POR_SERIE))
@pytest.mark.parametrize("modulo", _MODULOS_PYLINAC)
def test_b_centro_exacto_contra_pylinac(clave, modulo):
    ct = _ct_analizado(clave)
    hu, tam_px, centro_pylinac = _hu_y_tam_px(ct, modulo)

    geo = GeometriaCatphan(hu, tam_px)

    error_mm = np.hypot(
        geo.centro[0] - centro_pylinac[0], geo.centro[1] - centro_pylinac[1]
    ) * tam_px
    assert error_mm <= TOL_EXACTITUD_MM, (
        f"{clave}/{modulo}: centro de la app a {error_mm:.3f} mm del de "
        f"pylinac (tope {TOL_EXACTITUD_MM} mm) -- método usado: "
        f"{geo.metodo_deteccion}"
    )
    assert geo.deteccion_confiable, (
        f"{clave}/{modulo}: la detección cayó al centro geométrico -- "
        "Otsu y Hough fallaron los dos sobre una serie real"
    )


# ─────────────────────────────────────────────────────────────────────────
# (c) El escenario del físico: "Elegir corte" dos veces, deslizador distinto
# ─────────────────────────────────────────────────────────────────────────

def test_c_elegir_corte_dos_veces_con_deslizador_distinto_da_lo_mismo():
    """Carga real de `DicomVolume` (la ruta que usa la pantalla), sobre la
    carpeta que el físico nombró en el rebuild del 23-09
    (`CatphanHalcyonJunio2026`). Simula el escenario exacto que reportó:
    "Elegir corte", mover el deslizador, "Elegir corte" otra vez -- mismo
    anillo, mismos números.
    """
    ruta = _requerir("HALCYON_JUN")
    vol = DicomVolume(ruta)
    assert vol.volumen_hu is not None, "el volumen no cargó (HU ausente)"

    tam_px = vol.get_pixel_spacing()[0]
    corte_idx = vol.volumen_hu.shape[0] // 2
    hu = vol.volumen_hu[corte_idx]

    resultados = []
    for wl, ww in VENTANAS_MUY_DISTINTAS:
        corte_255 = vol.get_volumen_normalizado(wl, ww)[corte_idx]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resultado = resolucion_contraste(
                corte_255, hu, tam_px, visualizar=False,
                **PARAMETROS_HEREDADOS["resolucion_contraste"],
            )
        resultados.append(resultado["resumen"]["rois_visibles_cnr"])

    assert len(set(resultados)) == 1, (
        f"'Elegir corte' con el deslizador en tres sitios distintos dio "
        f"resultados distintos: {resultados}"
    )


# ─────────────────────────────────────────────────────────────────────────
# (d) La resolución de contraste deja de fallar
# ─────────────────────────────────────────────────────────────────────────

def test_d_resolucion_contraste_halcyon_junio_pasa_a_ser_confiable():
    """§0.9 [medido]: `CatphanHalcyonJunio2026` con la ventana inicial daba
    2/6 (no cumple, umbral >= 4/6 de `pasa_test_cnr`); con el centro por
    Otsu debía subir a >= 4/6. Se verifica con la ventana INICIAL real de
    la app (WL 40 / WW 400, `leer_dicom.py:798-807`), la que reportó el
    físico.
    """
    ct = _ct_analizado("HALCYON_JUN")
    hu, tam_px, _ = _hu_y_tam_px(ct, "ctp515")
    corte_255_inicial = _ventanear(hu, 40, 400)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = resolucion_contraste(
            corte_255_inicial, hu, tam_px, visualizar=False,
            **PARAMETROS_HEREDADOS["resolucion_contraste"],
        )

    visibles = resultado["resumen"]["rois_visibles_cnr"]
    assert visibles >= 4, (
        f"CatphanHalcyonJunio2026 con la ventana inicial: {visibles}/6 ROI "
        "visibles (se esperaba >= 4/6 tras D.0; §0.9 medía 2/6 antes)"
    )


# ─────────────────────────────────────────────────────────────────────────
# (e) Tripwire estructural
# ─────────────────────────────────────────────────────────────────────────

def test_e_geometria_rechaza_imagen_ventaneada_de_8_bits():
    corte_uint8 = np.zeros((512, 512), dtype=np.uint8)
    with pytest.raises(TypeError):
        GeometriaCatphan(corte_uint8, 1.0)
    with pytest.raises(TypeError):
        GeometriaCatphanCT(corte_uint8, 1.0)


def test_e_geometria_acepta_hu_float():
    """El corte 255 quedó reservado para dibujar; HU (float) debe seguir
    funcionando -- que el tripwire de arriba no se convierta en un rechazo
    de todo."""
    corte_hu = np.full((256, 256), -1000.0, dtype=np.float32)
    geo = GeometriaCatphan(corte_hu, 1.0)
    assert geo.metodo_deteccion == "centro_geometrico"
    assert not geo.deteccion_confiable


_RAIZ_CODIGO = Path(__file__).resolve().parent.parent
_DIRS_EXCLUIDOS = {"tests", ".venv", "build", "dist", "__pycache__", ".git"}
_NOMBRES_GEOMETRIA = ("GeometriaCatphan", "GeometriaCatphanCT")


def _archivos_produccion():
    for dirpath, dirnames, filenames in os.walk(_RAIZ_CODIGO):
        dirnames[:] = [d for d in dirnames if d not in _DIRS_EXCLUIDOS]
        for nombre in filenames:
            if nombre.endswith(".py"):
                yield Path(dirpath) / nombre


def _funcion_contenedora(arbol, lineno):
    """El nombre de la función (def) más específica que contiene `lineno`,
    o '<módulo>' si no hay ninguna -- por RANGO (lineno/end_lineno), no por
    línea exacta: sobrevive a que el archivo gane o pierda líneas."""
    mejor = None
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ini = nodo.lineno
            fin = getattr(nodo, "end_lineno", ini)
            if ini <= lineno <= fin:
                ancho = fin - ini
                if mejor is None or ancho < mejor[0]:
                    mejor = (ancho, nodo.name)
    return mejor[1] if mejor else "<módulo>"


def _censo_construcciones_geometria():
    """(ruta relativa, función contenedora, clase construida) de TODO sitio
    del código de producción que llama `GeometriaCatphan(...)` o
    `GeometriaCatphanCT(...)` como invocación real (no la mención en un
    docstring, ni `class GeometriaCatphanCT(GeometriaCatphan):`, que en el
    AST es una base de clase, no una `Call`). Derivado del código -- si
    aparece un sitio nuevo, sale en el resultado y la prueba lo nombra.
    """
    sitios = set()
    for ruta in _archivos_produccion():
        try:
            fuente = ruta.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        try:
            arbol = ast.parse(fuente, filename=str(ruta))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Name)
                and nodo.func.id in _NOMBRES_GEOMETRIA
            ):
                rel = str(ruta.relative_to(_RAIZ_CODIGO))
                funcion = _funcion_contenedora(arbol, nodo.lineno)
                sitios.add((rel, funcion, nodo.func.id))
    return sitios


def test_e_censo_construcciones_geometria_derivado_del_codigo():
    """Los 9 sitios reales que D.0 corrigió, y ninguno más. Si un sitio
    nuevo construye la geometría en el futuro, este censo lo atrapa aquí
    -- antes de que llegue a un control real con la imagen equivocada."""
    esperados = {
        ("analisisImagenes/Analisis_Catphan_TAC.py", "espesor_corte", "GeometriaCatphan"),
        ("analisisImagenes/Analisis_Catphan_TAC.py", "tamano_pixel", "GeometriaCatphan"),
        ("analisisImagenes/Analisis_Catphan_TAC.py", "resolucion_contraste", "GeometriaCatphan"),
        ("analisisImagenes/Analisis_Catphan_TAC.py", "resolucion_espacial", "GeometriaCatphan"),
        ("analisisImagenes/Analisis_Catphan_TAC.py", "mostrar_regiones_anillo", "GeometriaCatphan"),
        ("analisisImagenes/Analisis_Catphan_TAC.py", "valor_numero_ct", "GeometriaCatphanCT"),
        ("analisisImagenes/Analisis_Catphan_TAC.py", "uniformidad", "GeometriaCatphan"),
        ("ui/paginasControles/PruebasMensuales/tac_mensual.py", "imagen_dicom_cargada", "GeometriaCatphan"),
        ("ui/paginasControles/PruebasMensuales/tac_mensual.py", "imagen_dicom_cargada", "GeometriaCatphanCT"),
    }
    encontrados = _censo_construcciones_geometria()

    nuevos = encontrados - esperados
    assert not nuevos, (
        f"Sitio(s) nuevo(s) construyendo GeometriaCatphan/GeometriaCatphanCT, "
        f"no censados: {nuevos}. Verificar que reciben HU (float), no la "
        f"imagen ventaneada -- el TypeError de la clase lo exige en runtime, "
        f"pero este censo es la señal en el momento de escribir el código."
    )
    faltantes = esperados - encontrados
    assert not faltantes, (
        f"Sitio(s) esperado(s) que ya no construyen la geometría (¿se "
        f"retiraron, o cambiaron de función contenedora?): {faltantes}"
    )
