"""D.1 (PLAN_HANDOFF_IMAGENES_22-09.md): centro y giro del fantoma.

D.0 cerró el centro (Otsu sobre HU). Esta tarea cierra lo que queda de la
causa original (`Analisis_Catphan_TAC.py:658-667`: el anillo usaba ángulos
CONSTANTES, sin ninguna estimación del giro ni de la orientación del
fantoma) reutilizando el motor pylinac ya validado (B.1/B.2,
`PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md`) en vez de escribir un
detector nuevo: `slice_matcher.py` pasa a llamar `motor.analizar`, que ya
mide orientación y giro (`roll_deg`) -- el fantoma es rígido, así que son
los mismos para los cuatro módulos.

La fórmula que traduce un ángulo NOMINAL a su posición real se validó
aquí de forma empírica, no analítica: un giro sintético GRANDE y conocido
aplicado a un corte real, contra el HU real de los 7 materiales de CTP404
en sus ángulos nominales. OJO (OR.1, 08-10): esa validación solo ejercitó
giros grandes en orientación NORMAL; el signo para el fantoma INVERTIDO (que
esta prueba no discrimina) estaba mal por 2R y lo corrigió OR.1 -- la
fórmula vive hoy en `analisisImagenes/catphan/orientacion.py` y su prueba
es `test_or1_una_transformacion_de_orientacion.py`.

Los 2 escenarios de verificación que pide el plan:
  (a) `QA Halcyon Catphan` (la única serie invertida del corpus) pasa de
      lo medido en §0.9 (0-1/6 ROI de contraste visibles, según la
      ventana) a >= 4/6 con la orientación aplicada.
  (b) Un corte real girado artificialmente 3°, 7° y 15° da el mismo
      resultado (ROI visibles / regiones con picos suficientes) que sin
      girar, una vez que se usa el giro que mide el motor.
"""
import os
import types
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from scipy import ndimage as ndi

from _catphan_oro import LIMITE_HOMOGENEIDAD_IX
from _corpus import serie_catphan
from analisisImagenes.catphan import motor
from analisisImagenes.catphan.serie import leer_serie
from analisisImagenes.catphan.criterios import PARAMETROS_HEREDADOS  # G.3: los umbrales viven en un solo sitio
from analisisImagenes.Analisis_Catphan_TAC import resolucion_contraste, resolucion_espacial
from data.ManejoDatos.catphan_TAC.slice_matcher import detectar_modulos_pylinac

_LIMITE_POR_SERIE = {
    "TOMOGRAFO": None,
    "HALCYON_JUN": None,
    "HALCYON_SEP": None,
    "HALCYON_236": None,
    "IX_DIC": LIMITE_HOMOGENEIDAD_IX,
}


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


# ─────────────────────────────────────────────────────────────────────────
# (a) QA Halcyon Catphan (invertida): 0-1/6 -> >= 4/6
# ─────────────────────────────────────────────────────────────────────────

def _resultado_y_slice_ctp515(clave):
    """El HU en el marco de la APP (sin voltear NUNCA) -- `_voltear_volumen`
    es una corrección INTERNA de pylinac para poder analizar un fantoma
    invertido; el volumen que la app muestra y con el que trabajan las
    funciones de análisis siempre es el original, tal como llega del
    disco. Usar `ct.dicom_stack` tras `_voltear_volumen` sería medir sobre
    el marco YA CORREGIDO por pylinac, no sobre el que ve la pantalla --
    justo el error que este ajuste corrigió al escribir esta prueba."""
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    n = len(serie.cortes)
    perfil = types.SimpleNamespace(limite_variacion_hu=_LIMITE_POR_SERIE[clave], nombre=clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = motor.analizar(serie, perfil)
    idx_pylinac = resultado.modulos["CTP515"].corte_indice
    idx_app = (n - 1 - idx_pylinac) if resultado.orientacion == "invertido" else idx_pylinac

    import pydicom
    ds = pydicom.dcmread(serie.cortes[idx_app].ruta)
    hu = ds.pixel_array.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
    tam_px = float(ds.PixelSpacing[0])
    return resultado, hu, tam_px


def _ventanear(hu, wl, ww):
    lo, hi = wl - ww / 2, wl + ww / 2
    return ((np.clip(hu, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)


def test_a_halcyon_sep_pasa_a_ser_confiable_con_orientacion():
    resultado, hu, tam_px = _resultado_y_slice_ctp515("HALCYON_SEP")
    assert resultado.orientacion == "invertido", (
        "esta prueba depende de que HALCYON_SEP siga siendo la serie "
        "invertida del corpus -- si el motor ya no la detecta así, revisar"
    )

    corte_255 = _ventanear(hu, 40, 400)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sin_orientacion = resolucion_contraste(
            corte_255, hu, tam_px, visualizar=False, **PARAMETROS_HEREDADOS["resolucion_contraste"],
        )
        con_orientacion = resolucion_contraste(
            corte_255, hu, tam_px, visualizar=False, **PARAMETROS_HEREDADOS["resolucion_contraste"],
            orientacion=resultado.orientacion, roll_deg=resultado.roll_deg,
        )

    visibles_sin = sin_orientacion["resumen"]["rois_visibles_cnr"]
    visibles_con = con_orientacion["resumen"]["rois_visibles_cnr"]
    assert visibles_con >= 4, (
        f"con orientación aplicada: {visibles_con}/6 (se esperaba >= 4/6; "
        f"sin ella: {visibles_sin}/6 -- §0.9 medía 0-1/6)"
    )
    assert visibles_con > visibles_sin, (
        "aplicar la orientación medida debería mejorar el conteo respecto "
        f"de no aplicarla (con={visibles_con}, sin={visibles_sin})"
    )


def test_a_slice_matcher_expone_orientacion_de_halcyon_sep():
    """El censo estructural: `detectar_modulos_pylinac` (slice_matcher,
    D.1) debe exponer la orientación/giro reales para la serie invertida,
    no los valores por defecto -- es la pieza que permite que `tac_mensual`
    los lea sin volver a correr pylinac."""
    ruta = _requerir("HALCYON_SEP")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultados = detectar_modulos_pylinac(ruta)
    assert resultados["CTP515"].confiable
    assert resultados["CTP515"].orientacion == "invertido"
    # Los 4 módulos comparten el mismo giro (fantoma rígido).
    rolls = {m.roll_deg for m in resultados.values() if m.confiable}
    assert len(rolls) == 1


# ─────────────────────────────────────────────────────────────────────────
# (b) Corte real girado artificialmente 3°, 7°, 15° -- mismo resultado
# ─────────────────────────────────────────────────────────────────────────

def _analizar_ctp515_rotado(giro_deg):
    """TOMOGRAFO, CTP515, rotado `giro_deg` grados (0 = sin girar). Devuelve
    (roll_medido, rois_visibles_cnr con orientación aplicada).

    El fantoma es rígido: rotarlo de verdad rota TODOS sus cortes por
    igual. Rotar solo 1-2 cortes sueltos (dejando el resto del volumen sin
    girar) confunde el propio algoritmo de pylinac a partir de cierto
    ángulo -- [medido] con 15° rotando solo el corte de CTP404 y el de
    CTP515, `catphan_roll` no se movía del valor sin girar (mismo síntoma
    que rotar solo CTP515). Rotando el volumen COMPLETO (igual método que
    la calibración empírica de este mismo bloque) sí es estable a 15°.
    `ct.catphan_roll` se mide sobre el corte de CTP404, no el de CTP515."""
    ruta = _requerir("TOMOGRAFO")
    serie = leer_serie(ruta)
    rutas = [c.ruta for c in serie.cortes]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ct = motor._construir(rutas, None)
        if giro_deg != 0.0:
            for img in ct.dicom_stack.images:
                arr = np.asarray(img.array, dtype=np.float32)
                arr_rot = ndi.rotate(arr, giro_deg, reshape=False, order=1, cval=float(arr.min()))
                img.array = arr_rot
        motor._analizar_una_vez(ct, None, {})
        roll_medido = float(ct.catphan_roll)
        img = ct.dicom_stack[ct.ctp515.slice_num]
        hu = np.asarray(img.array, dtype=np.float32)
        tam_px = float(img.dpmm) ** -1
        corte_255 = _ventanear(hu, 40, 400)
        resultado = resolucion_contraste(
            corte_255, hu, tam_px, visualizar=False, **PARAMETROS_HEREDADOS["resolucion_contraste"],
            orientacion="normal", roll_deg=roll_medido,
        )
    return roll_medido, resultado["resumen"]["rois_visibles_cnr"]


@pytest.mark.parametrize("giro_deg", [3.0, 7.0, 15.0])
def test_b_giro_artificial_da_el_mismo_conteo_que_sin_girar(giro_deg):
    roll_base, visibles_base = _analizar_ctp515_rotado(0.0)
    roll_rotado, visibles_rotado = _analizar_ctp515_rotado(giro_deg)

    # El giro que reporta pylinac tiene que moverse ~ el ángulo aplicado
    # (relativo al giro natural de esta serie sin rotar) -- confirma que
    # el motor sigue midiendo un giro coherente tras la rotación sintética.
    delta_medido = roll_base - roll_rotado
    assert abs(delta_medido - giro_deg) <= 1.0, (
        f"giro medido no coincide con el aplicado: aplicado={giro_deg}, "
        f"delta medido={delta_medido:.2f} (tolerancia 1°)"
    )

    # Y, una vez compensado con ese giro medido, el conteo de ROI visibles
    # es el MISMO que sin girar -- la garantía real que pide el plan.
    assert visibles_rotado == visibles_base, (
        f"girar {giro_deg}° cambió el resultado aun compensando con el giro "
        f"medido: sin girar={visibles_base}/6, girado={visibles_rotado}/6"
    )


def test_b_sin_compensar_el_giro_grande_si_cambia_el_resultado():
    """Control: si NO se aplica el giro medido (orientacion/roll_deg por
    defecto, el comportamiento de antes de D.1), un giro de 15° sí puede
    cambiar el conteo -- para confirmar que el test de arriba discrimina
    de verdad y no pasaría igual sin el arreglo."""
    ruta = _requerir("TOMOGRAFO")
    serie = leer_serie(ruta)
    rutas = [c.ruta for c in serie.cortes]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ct = motor._construir(rutas, None)
        motor._analizar_una_vez(ct, None, {})
        idx = ct.ctp515.slice_num
        arr = np.asarray(ct.dicom_stack[idx].array, dtype=np.float32).copy()
        arr_rot = ndi.rotate(arr, 15.0, reshape=False, order=1, cval=float(arr.min()))
        tam_px = 1.0 / float(ct.dicom_stack[idx].dpmm)

        corte_255_base = _ventanear(arr, 40, 400)
        corte_255_rot = _ventanear(arr_rot, 40, 400)
        sin_girar = resolucion_contraste(
            corte_255_base, arr, tam_px, visualizar=False, **PARAMETROS_HEREDADOS["resolucion_contraste"],
        )
        girado_sin_compensar = resolucion_contraste(
            corte_255_rot, arr_rot, tam_px, visualizar=False, **PARAMETROS_HEREDADOS["resolucion_contraste"],
        )

    assert (
        sin_girar["resumen"]["rois_visibles_cnr"]
        != girado_sin_compensar["resumen"]["rois_visibles_cnr"]
    ), "el control debería fallar sin compensar el giro -- si no, el test (b) no discrimina nada"
