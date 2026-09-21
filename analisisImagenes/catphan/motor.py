"""B.1/B.2 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): el motor pylinac,
encapsulado y sin interfaz.

Pylinac ya corría en cada carga (`slice_matcher.py`), pero solo se usaba
su número de corte -- toda la medición la hacían funciones propias con
los defectos D-09 a D-14 (`Analisis_Catphan_TAC.py`). Este módulo hace la
medición real, leyendo los atributos que pylinac ya calculó -- no
`results_data()` (pydantic), para no meter esa dependencia en la ruta de
ejecución del `.exe` (B.1, justificación).

`analizar(serie, perfil, ajustes=None, corte_origen=None)` es el único
punto de entrada; lo usan la pantalla (D.1), el guardado (C.2) y el PDF
(E.1) con la misma definición (corolario 1 de CLAUDE.md).
"""
from __future__ import annotations

import io
import warnings

import numpy as np
import pylinac
from pylinac.core.profile import CollapsedCircleProfile
from pylinac.ct import CatPhan504, Slice

from analisisImagenes.catphan.resultado import (
    Metrica,
    ResultadoCatphan,
    ResultadoModulo,
)

# La subclase de abajo copia código interno de esta versión exacta de
# pylinac (`find_origin_slice`, `ct.py`). Un cambio de versión puede
# cambiar esa implementación en silencio -- de ahí el tripwire de B.1.
VERSION_PYLINAC_VALIDADA = "3.45.0"

# Regla de orientación (B.2, validada en la caracterización): correlación
# de Pearson entre los HU medidos de los 7 materiales y estos nominales,
# más el HU del centro del CTP486. Separa 0.999 (correcta) de 0.26
# (invertida) con margen amplio, y es independiente del nivel absoluto de
# HU del equipo (funciona incluso con el iX, que no está calibrado).
NOMINALES_HU_ORIENTACION = {
    "Air": -1000,
    "PMP": -196,
    "LDPE": -104,
    "Poly": -47,
    "Acrylic": 115,
    "Delrin": 365,
    "Teflon": 1000,
}
UMBRAL_CORRELACION_ORIENTACION = 0.95
CENTRO486_MINIMO_HU = -900

# pylinac -> nombre canónico de metrica (español, B.1 §4)
_MATERIAL_A_METRICA = {
    "Air": "aire",
    "PMP": "pmp",
    "LDPE": "ldpe",
    "Poly": "poliestireno",
    "Acrylic": "acrilico",
    "Delrin": "delrin",
    "Teflon": "teflon",
}
_CTP486_ROI_A_METRICA = {
    "Center": "centro",
    "Top": "superior",
    "Bottom": "inferior",
    "Left": "izquierda",
    "Right": "derecha",
}
_CTP404_LINEA_A_METRICA = {
    "Top-Horizontal": "geo_x1_mm",
    "Bottom-Horizontal": "geo_x2_mm",
    "Left-Vertical": "geo_y1_mm",
    "Right-Vertical": "geo_y2_mm",
}
_MTF_PORCENTAJES = (10, 20, 30, 40, 50, 60, 70, 80, 90)


class OrientacionIndeterminada(Exception):
    """El fantoma no se pudo juzgar ni en orientación normal ni invertida
    (ninguna de las dos correlaciona con los HU nominales). El motor NO
    inventa una orientación -- la pantalla debe ofrecer el camino manual."""


class CatPhan504Radqa(CatPhan504):
    """Copia fiel de `CatPhan504` (3.45.0) que añade un límite de
    homogeneidad CONFIGURABLE a `find_origin_slice` (D-04: el límite fijo
    de pylinac, 100 HU, hace que la localización falle en el iX por 9-14
    HU). Con `limite_variacion_hu=None` el comportamiento es IDÉNTICO al
    de pylinac sin modificar (delega en `super()`).

    Validado en la caracterización (script `origen_ix.py`): con 130 y con
    150 HU encuentra el mismo origen que forzarlo a mano; en el tomógrafo
    no cambia nada (origen idéntico con y sin el parámetro).
    """

    limite_variacion_hu = None

    def find_origin_slice(self):
        if self.limite_variacion_hu is None:
            return super().find_origin_slice()
        hu_slices = []
        for n in range(0, self.num_images, 2):
            s = Slice(self, n, combine=False, clear_borders=self.clear_borders)
            if s.is_phantom_in_view():
                prof = CollapsedCircleProfile(
                    s.phan_center,
                    radius=self.localization_radius / self.mm_per_pixel,
                    image_array=s.image,
                    width_ratio=0.05,
                    num_profiles=5,
                ).values
                lo, hi = np.percentile(prof, [2, 98])
                med = np.median(prof)
                mid = np.percentile(prof, 80) - np.percentile(prof, 20)
                if (
                    lo < med - self.hu_origin_slice_variance
                    and hi > med + self.hu_origin_slice_variance
                    and mid < self.limite_variacion_hu
                ):
                    hu_slices.append(n)
        if not hu_slices:
            raise ValueError("No slices were found that resembled the HU linearity module")
        hu_slices = np.array(hu_slices)
        c = int(round(float(np.median(hu_slices))))
        ln = len(hu_slices)
        hu_slices = hu_slices[((c + ln / 2) >= hu_slices) & (hu_slices >= (c - ln / 2))]
        centro = int(round(float(np.median(hu_slices))))
        if self._is_within_image_extent(centro):
            return centro


def _voltear_volumen(ct):
    """Volteo con atributos PÚBLICOS únicamente (validado en la
    caracterización: reproduce los mismos números que voltear con el
    atributo privado `_image_path_keys`, que no hace falta)."""
    st = ct.dicom_stack
    st.images = st.images[::-1]
    st.metadatas = st.metadatas[::-1]
    for img in st.images:
        img.fliplr()


def _construir(rutas, limite_variacion_hu):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        ct = CatPhan504Radqa(rutas)
    ct.limite_variacion_hu = limite_variacion_hu
    return ct


def _analizar_una_vez(ct, corte_origen, ajustes):
    kwargs = dict(ajustes or {})
    if corte_origen is not None:
        kwargs["origin_slice"] = corte_origen
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        ct.analyze(**kwargs)


def _correlacion_y_centro(ct):
    """Pearson entre HU medidos y nominales (7 materiales) + HU del
    centro del CTP486. Mide orden relativo, no valor absoluto -- por eso
    funciona incluso con el iX, que no está calibrado en HU."""
    materiales = list(NOMINALES_HU_ORIENTACION)
    medidos = [ct.ctp404.rois[m].pixel_value for m in materiales]
    nominales = [NOMINALES_HU_ORIENTACION[m] for m in materiales]
    r = float(np.corrcoef(medidos, nominales)[0, 1])
    centro486 = float(ct.ctp486.rois["Center"].pixel_value)
    return r, centro486


def _png_subimagen(ct, clave):
    import matplotlib.pyplot as plt

    fig = None
    try:
        buf = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fig = ct.save_analyzed_subimage(buf, subimage=clave)
        if fig is None:
            return None
        return buf.getvalue()
    except Exception:
        return None
    finally:
        # save_analyzed_subimage no cierra su propia figura -- sin esto,
        # cada análisis deja 5 figuras de matplotlib abiertas (fuga de
        # memoria en una sesión larga de la app). Se cierra SOLO la
        # figura propia, nunca las del resto del proceso (`plt.close("all")`
        # cerraría también canvases ajenos, p. ej. los del visor).
        if fig is not None:
            plt.close(fig)


def _extraer_ctp404(ct, geometria_perfil=None):
    metricas = {}
    for material, sufijo in _MATERIAL_A_METRICA.items():
        roi = ct.ctp404.rois[material]
        metricas[f"hu_{sufijo}"] = Metrica(f"hu_{sufijo}", float(roi.pixel_value), "HU")
        metricas[f"sd_{sufijo}"] = Metrica(f"sd_{sufijo}", float(roi.std), "HU")
    for linea, nombre in _CTP404_LINEA_A_METRICA.items():
        metricas[nombre] = Metrica(nombre, float(ct.ctp404.lines[linea].length_mm), "mm")
    metricas["espesor_mm"] = Metrica("espesor_mm", float(ct.ctp404.meas_slice_thickness), "mm")
    return ResultadoModulo(
        modulo="CTP404",
        corte_indice=int(ct.ctp404.slice_num),
        corte_z_mm=None,
        sop_uid=None,
        metricas=metricas,
        imagen_png=_png_subimagen(ct, "hu"),
    )


def _extraer_ctp486(ct):
    metricas = {}
    for clave, sufijo in _CTP486_ROI_A_METRICA.items():
        metricas[f"unif_{sufijo}"] = Metrica(
            f"unif_{sufijo}", float(ct.ctp486.rois[clave].pixel_value), "HU"
        )
    centro = ct.ctp486.rois["Center"].pixel_value
    max_dif = max(
        abs(ct.ctp486.rois[clave].pixel_value - centro)
        for clave in ("Top", "Bottom", "Left", "Right")
    )
    metricas["unif_max_dif_hu"] = Metrica("unif_max_dif_hu", float(max_dif), "HU")
    metricas["ruido_centro_hu"] = Metrica(
        "ruido_centro_hu", float(ct.ctp486.rois["Center"].std), "HU"
    )
    metricas["ui_pct"] = Metrica("ui_pct", float(ct.ctp486.uniformity_index), "%")
    metricas["inu_pct"] = Metrica(
        "inu_pct", float(ct.ctp486.integral_non_uniformity) * 100, "%"
    )
    return ResultadoModulo(
        modulo="CTP486",
        corte_indice=int(ct.ctp486.slice_num),
        corte_z_mm=None,
        sop_uid=None,
        metricas=metricas,
        imagen_png=_png_subimagen(ct, "un"),
    )


def _extraer_ctp528(ct):
    metricas = {}
    for pct in _MTF_PORCENTAJES:
        lp_mm = float(ct.ctp528.mtf.relative_resolution(pct))
        metricas[f"mtf{pct}_lpcm"] = Metrica(f"mtf{pct}_lpcm", lp_mm * 10, "lp/cm")
    return ResultadoModulo(
        modulo="CTP528",
        corte_indice=int(ct.ctp528.slice_num),
        corte_z_mm=None,
        sop_uid=None,
        metricas=metricas,
        imagen_png=_png_subimagen(ct, "sp"),
    )


def _extraer_ctp515(ct):
    metricas = {
        "lc_visibles_1pct": Metrica("lc_visibles_1pct", float(ct.ctp515.rois_visible), "conteo")
    }
    for diam, roi in ct.ctp515.rois.items():
        prefijo = f"lc_{diam}mm"
        metricas[f"{prefijo}_contraste"] = Metrica(f"{prefijo}_contraste", float(roi.contrast), "1")
        metricas[f"{prefijo}_cnr"] = Metrica(f"{prefijo}_cnr", float(roi.contrast_to_noise), "1")
        metricas[f"{prefijo}_visibilidad"] = Metrica(
            f"{prefijo}_visibilidad", float(roi.visibility), "1"
        )
        metricas[f"{prefijo}_visible"] = Metrica(
            f"{prefijo}_visible", float(bool(roi.passed_visibility)), "bool"
        )
    return ResultadoModulo(
        modulo="CTP515",
        corte_indice=int(ct.ctp515.slice_num),
        corte_z_mm=None,
        sop_uid=None,
        metricas=metricas,
        imagen_png=_png_subimagen(ct, "lc"),
    )


def _resultado_desde_ct(ct, equipo_detectado, orientacion, advertencias):
    return ResultadoCatphan(
        equipo_detectado=equipo_detectado,
        orientacion=orientacion,
        roll_deg=float(ct.catphan_roll),
        origen_indice=int(ct.origin_slice),
        modulos={
            "CTP404": _extraer_ctp404(ct),
            "CTP486": _extraer_ctp486(ct),
            "CTP528": _extraer_ctp528(ct),
            "CTP515": _extraer_ctp515(ct),
        },
        version_motor=VERSION_PYLINAC_VALIDADA,
        advertencias=list(advertencias),
    )


def analizar(serie, perfil, ajustes=None, corte_origen=None) -> ResultadoCatphan:
    """Analiza `serie` (una `SerieCT` de `serie.py`) con pylinac, detecta la
    orientación del fantoma automáticamente (B.2) y devuelve un
    `ResultadoCatphan` con números con unidad explícita.

    `perfil` debe exponer `limite_variacion_hu` (puede ser `None`) y,
    opcionalmente, `visibility_threshold` -- el resto de `PerfilEquipo`
    (B.3) no lo usa el motor. `ajustes` es un dict con las claves de
    `pylinac.CatPhan504.analyze` que se quieran forzar (`x_adjustment`,
    `y_adjustment`, `angle_adjustment`, `roi_size_factor`,
    `scaling_factor`...). `corte_origen`, si se da, se usa SOLO en el
    primer intento (orientación normal): tras un volteo el índice ya no
    se refiere al mismo corte físico, así que el segundo intento siempre
    localiza el origen automáticamente.
    """
    rutas = [c.ruta for c in serie.cortes]
    limite = getattr(perfil, "limite_variacion_hu", None)
    ajustes = dict(ajustes or {})
    if getattr(perfil, "visibility_threshold", None) is not None:
        ajustes.setdefault("visibility_threshold", perfil.visibility_threshold)

    ct = _construir(rutas, limite)
    esperado = [c.sop_uid for c in serie.cortes]
    obtenido = [str(m.SOPInstanceUID) for m in ct.dicom_stack.metadatas]
    if obtenido != esperado:
        raise ValueError(
            "El orden de cortes de pylinac no coincide con el de leer_serie "
            f"para {serie.carpeta!r} -- no se puede confiar en los índices."
        )

    try:
        _analizar_una_vez(ct, corte_origen, ajustes)
        r_normal, centro_normal = _correlacion_y_centro(ct)
    except Exception:
        r_normal, centro_normal = None, None

    if (
        r_normal is not None
        and r_normal >= UMBRAL_CORRELACION_ORIENTACION
        and centro_normal > CENTRO486_MINIMO_HU
    ):
        advertencias = [f"correlación orientación normal: r={r_normal:.3f}"]
        equipo = getattr(perfil, "nombre", None)
        return _resultado_desde_ct(ct, equipo, "normal", advertencias)

    ct_volteado = _construir(rutas, limite)
    _voltear_volumen(ct_volteado)
    try:
        _analizar_una_vez(ct_volteado, None, ajustes)
        r_volteado, centro_volteado = _correlacion_y_centro(ct_volteado)
    except Exception:
        r_volteado, centro_volteado = None, None

    if (
        r_volteado is not None
        and r_volteado >= UMBRAL_CORRELACION_ORIENTACION
        and centro_volteado > CENTRO486_MINIMO_HU
    ):
        advertencias = [
            f"correlación orientación normal: r={r_normal}",
            f"correlación orientación invertida: r={r_volteado:.3f}",
            "fantoma detectado INVERTIDO -- volumen volteado antes de medir",
        ]
        equipo = getattr(perfil, "nombre", None)
        return _resultado_desde_ct(ct_volteado, equipo, "invertido", advertencias)

    raise OrientacionIndeterminada(
        f"Ninguna orientación del fantoma en {serie.carpeta!r} correlaciona con los HU "
        f"nominales (normal: r={r_normal}, invertido: r={r_volteado}, umbral="
        f"{UMBRAL_CORRELACION_ORIENTACION})."
    )
