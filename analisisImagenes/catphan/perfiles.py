"""B.3 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): perfiles por
equipo -- qué prueba aplica y con qué umbral.

Es el "definir todos estos parámetros" del pedido del físico. Hoy no
existe ningún parámetro por equipo (§0.3): hay dos definiciones de los
rangos de HU (D-15), rangos genéricos (D-16), umbrales sin fuente (D-18),
espesor sin criterio (D-17), y el espesor se juzga en los aceleradores
aunque no aplica (DA-78).

Los umbrales normativos viven en código versionado (cambian rara vez, y
un cambio debe revisarse y quedar en git con su motivo); las LÍNEAS BASE,
que sí cambian con cada servicio técnico, van a la BD (fase F, futura).

`test_b3_matriz_completa` (tests/) es el censo obligatorio: si una celda
equipo x prueba queda sin regla, un test falla -- una prueba nueva no
puede nacer sin criterio (regla del 08-09, "clasificar cada campo").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analisisImagenes.catphan.serie import identificar_equipo  # noqa: F401 (reexport, A.3->B.3)

# Los 8 nombres de "prueba" que exige el censo (§0.9 de PLAN_CATPHAN..18-09,
# filas 1-8; 1b y 5b son informativas y viven DENTRO de la regla de la 1 y
# la 5, no como pruebas propias).
PRUEBAS = (
    "geometria",
    "espesor",
    "numeros_ct",
    "linealidad",
    "uniformidad",
    "ruido",
    "bajo_contraste",
    "resolucion_espacial",
)

# Tipos de tolerancia (§0.9). Cada uno sabe cómo comparar `valor` contra
# `nominal`/`tolerancia`/`linea_base`, y evaluar() los interpreta.
TIPOS_TOLERANCIA = (
    "abs_nominal",  # |v - nominal| <= t
    "max",  # v <= t
    "min",  # v >= t
    "linea_base_abs",  # |v - base| <= t
    "linea_base_rel",  # |v - base| / |base| <= t
    "linea_base_min",  # v >= base - t
)


class ReglaPrueba:
    """Una celda de la matriz de §0.9: qué se juzga, con qué criterio, de
    dónde sale el número y qué tan firme es esa fuente.

    Clase simple (no `@dataclass`, a propósito): `tolerancia` acepta tanto
    un `float` como un `dict {nombre_metrica: float}` para las pruebas
    donde el umbral varía por métrica (p. ej. Números CT: unos materiales
    a ±20 HU, otros a ±50 HU) -- mezclar eso con la anotación de tipo de
    un dataclass ensuciaría más de lo que ordena.
    """

    def __init__(
        self,
        aplica,
        metricas,
        tipo_tolerancia=None,
        nominal=None,
        tolerancia=None,
        unidad="",
        fuente="",
        estado="",
        motivo_no_aplica=None,
    ):
        self.aplica = aplica  # 'si' | 'no' | 'informativo'
        self.metricas = tuple(metricas)
        self.tipo_tolerancia = tipo_tolerancia
        self.nominal = nominal  # fijo (p. ej. 50 mm); None = lo da el llamador (`referencia`)
        self.tolerancia = tolerancia  # float o dict {metrica: float}
        self.unidad = unidad
        self.fuente = fuente
        self.estado = estado  # 'confirmada' | 'norma' | 'propuesta'
        self.motivo_no_aplica = motivo_no_aplica


@dataclass
class Veredicto:
    estado: str  # 'Cumple' | 'No cumple' | 'Sin línea base' | 'No aplica' | 'Informativo'
    referencia: Optional[float]
    tolerancia: Optional[float]
    fuente: str


def _tolerancia_de(regla: ReglaPrueba, metrica: Optional[str]) -> Optional[float]:
    t = regla.tolerancia
    if isinstance(t, dict):
        if metrica is None or metrica not in t:
            raise ValueError(
                f"La regla necesita 'metrica' para resolver la tolerancia (opciones: {list(t)})"
            )
        return t[metrica]
    return t


def evaluar(
    regla: ReglaPrueba,
    valor: Optional[float],
    metrica: Optional[str] = None,
    referencia: Optional[float] = None,
    linea_base: Optional[float] = None,
) -> Veredicto:
    """Juzga `valor` contra `regla`. Nunca falla en silencio: sin línea
    base, las reglas de tipo línea base devuelven 'Sin línea base', nunca
    'Cumple' (§0.9)."""
    if regla.aplica == "no":
        return Veredicto("No aplica", None, None, regla.motivo_no_aplica or regla.fuente)
    if regla.aplica == "informativo":
        return Veredicto("Informativo", None, _tolerancia_de(regla, metrica), regla.fuente)

    tolerancia = _tolerancia_de(regla, metrica)
    tipo = regla.tipo_tolerancia

    if tipo == "abs_nominal":
        nominal = regla.nominal if regla.nominal is not None else referencia
        if nominal is None:
            raise ValueError("Esta regla exige una referencia (nominal) explícita")
        cumple = abs(valor - nominal) <= tolerancia
        return Veredicto("Cumple" if cumple else "No cumple", nominal, tolerancia, regla.fuente)

    if tipo == "max":
        cumple = valor <= tolerancia
        return Veredicto("Cumple" if cumple else "No cumple", None, tolerancia, regla.fuente)

    if tipo == "min":
        cumple = valor >= tolerancia
        return Veredicto("Cumple" if cumple else "No cumple", None, tolerancia, regla.fuente)

    if tipo in ("linea_base_abs", "linea_base_rel", "linea_base_min"):
        if linea_base is None:
            return Veredicto("Sin línea base", None, tolerancia, regla.fuente)
        if tipo == "linea_base_abs":
            cumple = abs(valor - linea_base) <= tolerancia
        elif tipo == "linea_base_rel":
            cumple = abs(valor - linea_base) / abs(linea_base) <= tolerancia
        else:  # linea_base_min
            cumple = valor >= linea_base - tolerancia
        return Veredicto("Cumple" if cumple else "No cumple", linea_base, tolerancia, regla.fuente)

    raise ValueError(f"tipo_tolerancia desconocido: {tipo!r}")


@dataclass
class PerfilEquipo:
    nombre: str  # 'Tomógrafo' | 'Clinac ix' | 'Halcyon' -- EXACTO (tac_mensual.py:428-447)
    limite_variacion_hu: Optional[float]
    visibility_threshold: Optional[float]
    min_imagenes: int
    combinar_cortes: str  # 'auto' | 'no_aplica'
    reglas: dict = field(default_factory=dict)  # {nombre_prueba: ReglaPrueba}


_MOTIVO_ESPESOR_NO_APLICA = (
    "No aplica a la CBCT de acelerador (criterio del jefe de física 18-09-2026; "
    "AAPM TG-142 Tabla VI no lo incluye)"
)

_HU_METRICAS = (
    "hu_aire",
    "hu_pmp",
    "hu_ldpe",
    "hu_poliestireno",
    "hu_acrilico",
    "hu_delrin",
    "hu_teflon",
)
_GEOMETRIA_METRICAS = ("geo_x1_mm", "geo_x2_mm", "geo_y1_mm", "geo_y2_mm")

PERFIL_TOMOGRAFO = PerfilEquipo(
    nombre="Tomógrafo",
    limite_variacion_hu=None,
    visibility_threshold=None,
    min_imagenes=39,
    combinar_cortes="auto",
    reglas={
        "geometria": ReglaPrueba(
            aplica="si",
            metricas=_GEOMETRIA_METRICAS,
            tipo_tolerancia="abs_nominal",
            nominal=50.0,
            tolerancia=1.0,
            unidad="mm",
            fuente="AAPM TG-66 (integridad espacial, 1 mm)",
            estado="norma",
        ),
        "espesor": ReglaPrueba(
            aplica="si",
            metricas=("espesor_mm",),
            tipo_tolerancia="abs_nominal",
            nominal=None,  # el nominal es el de CADA serie (serie.espesor_mm), no fijo
            tolerancia=1.0,
            unidad="mm",
            fuente="AAPM TG-66 (ancho del perfil de sensibilidad / espesor, ±1 mm)",
            estado="norma",
        ),
        "numeros_ct": ReglaPrueba(
            aplica="si",
            metricas=_HU_METRICAS,
            tipo_tolerancia="linea_base_abs",
            tolerancia={
                "hu_pmp": 20.0,
                "hu_ldpe": 20.0,
                "hu_poliestireno": 20.0,
                "hu_acrilico": 20.0,
                "hu_aire": 50.0,
                "hu_delrin": 50.0,
                "hu_teflon": 50.0,
            },
            unidad="HU",
            fuente=(
                "Propuesta del plan: TG-66 pide constancia mensual; 20 HU ≈ 1 % de dosis "
                "en tejido blando y 50 HU en pulmón/hueso"
            ),
            estado="propuesta",
        ),
        "linealidad": ReglaPrueba(
            aplica="si",
            metricas=("linealidad_r2",),
            tipo_tolerancia="min",
            tolerancia=0.99,
            unidad="1",
            fuente="Criterio actual de la app, sin fuente normativa (P8, requiere confirmación del físico)",
            estado="propuesta",
        ),
        "uniformidad": ReglaPrueba(
            aplica="si",
            metricas=("unif_max_dif_hu",),
            tipo_tolerancia="max",
            tolerancia=5.0,
            unidad="HU",
            fuente="AAPM TG-66 (uniformidad de campo, mensual)",
            estado="norma",
        ),
        "ruido": ReglaPrueba(
            aplica="si",
            metricas=("ruido_centro_hu",),
            tipo_tolerancia="linea_base_rel",
            tolerancia=0.20,
            unidad="1",
            fuente="Propuesta del plan (TG-66 remite al criterio del fabricante)",
            estado="propuesta",
        ),
        "bajo_contraste": ReglaPrueba(
            aplica="si",
            metricas=("lc_visibles_1pct",),
            tipo_tolerancia="linea_base_min",
            tolerancia=1.0,
            unidad="conteo",
            fuente="Propuesta del plan; el juicio visual del físico se conserva como complemento",
            estado="propuesta",
        ),
        "resolucion_espacial": ReglaPrueba(
            aplica="si",
            metricas=("mtf10_lpcm",),
            tipo_tolerancia="linea_base_min",
            tolerancia=0.0,
            unidad="lp/cm",
            fuente=(
                "Contra línea base (TG-66: según el fabricante). Techo físico ≈4.65 lp/cm "
                "con el FOV de 550 mm de la serie de QA (P4)"
            ),
            estado="propuesta",
        ),
    },
)

PERFIL_CLINAC_IX = PerfilEquipo(
    nombre="Clinac ix",
    limite_variacion_hu=150,
    visibility_threshold=None,
    min_imagenes=39,
    combinar_cortes="no_aplica",
    reglas={
        "geometria": ReglaPrueba(
            aplica="si",
            metricas=_GEOMETRIA_METRICAS,
            tipo_tolerancia="abs_nominal",
            nominal=50.0,
            tolerancia=2.0,
            unidad="mm",
            fuente="AAPM TG-142 Tabla VI (distorsión geométrica CBCT, ≤2 mm; ≤1 mm si SRS/SBRT, P5)",
            estado="norma",
        ),
        "espesor": ReglaPrueba(
            aplica="no",
            metricas=("espesor_mm",),
            motivo_no_aplica=_MOTIVO_ESPESOR_NO_APLICA,
            fuente="DA-78",
        ),
        "numeros_ct": ReglaPrueba(
            aplica="si",
            metricas=_HU_METRICAS,
            tipo_tolerancia="linea_base_abs",
            tolerancia=50.0,
            unidad="HU",
            fuente=(
                "AAPM TG-142 (constancia de HU) + TG-179. Los HU del iX no están calibrados "
                "(desplazamiento de +500 o -450 según el protocolo): nunca se juzgan en absoluto, "
                "solo contra su propia línea base"
            ),
            estado="norma",
        ),
        "linealidad": ReglaPrueba(
            aplica="informativo",
            metricas=("linealidad_r2",),
            fuente="AAPM TG-142 no la pide para CBCT (P8)",
            estado="norma",
        ),
        "uniformidad": ReglaPrueba(
            aplica="si",
            metricas=("unif_max_dif_hu",),
            tipo_tolerancia="max",
            tolerancia=40.0,
            unidad="HU",
            fuente="Especificación Varian / AAPM TG-142 (baseline)",
            estado="norma",
        ),
        "ruido": ReglaPrueba(
            aplica="si",
            metricas=("ruido_centro_hu",),
            tipo_tolerancia="linea_base_rel",
            tolerancia=0.20,
            unidad="1",
            fuente="AAPM TG-142 (baseline)",
            estado="norma",
        ),
        "bajo_contraste": ReglaPrueba(
            aplica="si",
            metricas=("lc_visibles_1pct",),
            tipo_tolerancia="linea_base_min",
            tolerancia=1.0,
            unidad="conteo",
            fuente="Propuesta del plan; el juicio visual del físico se conserva como complemento",
            estado="propuesta",
        ),
        "resolucion_espacial": ReglaPrueba(
            aplica="si",
            metricas=("mtf10_lpcm",),
            tipo_tolerancia="min",
            tolerancia=6.0,
            unidad="lp/cm",
            fuente=(
                "Especificación Varian (full-fan, ≥6 lp/cm). Métrica exacta del veredicto "
                "pendiente de confirmar (P7)"
            ),
            estado="norma",
        ),
    },
)

PERFIL_HALCYON = PerfilEquipo(
    nombre="Halcyon",
    limite_variacion_hu=None,
    visibility_threshold=None,
    min_imagenes=39,
    combinar_cortes="no_aplica",
    reglas={
        "geometria": ReglaPrueba(
            aplica="si",
            metricas=_GEOMETRIA_METRICAS,
            tipo_tolerancia="abs_nominal",
            nominal=50.0,
            tolerancia=0.5,
            unidad="mm",
            fuente="IDC-F-RT-120 (formato anual del servicio, 2025)",
            estado="confirmada",
        ),
        "espesor": ReglaPrueba(
            aplica="no",
            metricas=("espesor_mm",),
            motivo_no_aplica=_MOTIVO_ESPESOR_NO_APLICA,
            fuente="DA-78",
        ),
        "numeros_ct": ReglaPrueba(
            aplica="si",
            metricas=_HU_METRICAS,
            tipo_tolerancia="linea_base_abs",
            tolerancia={
                "hu_pmp": 30.0,
                "hu_ldpe": 30.0,
                "hu_poliestireno": 30.0,
                "hu_acrilico": 30.0,
                "hu_aire": 50.0,
                "hu_delrin": 50.0,
                "hu_teflon": 50.0,
            },
            unidad="HU",
            fuente="AAPM TG-179 (tejido-equivalente ±30 HU; pulmón/hueso ±50 HU) + Varian (±50 HU)",
            estado="norma",
        ),
        "linealidad": ReglaPrueba(
            aplica="informativo",
            metricas=("linealidad_r2",),
            fuente="Informativo (P8)",
            estado="propuesta",
        ),
        "uniformidad": ReglaPrueba(
            aplica="si",
            metricas=("unif_max_dif_hu",),
            tipo_tolerancia="max",
            tolerancia=40.0,
            unidad="HU",
            fuente="IDC-F-RT-120 (formato anual del servicio, 2025)",
            estado="confirmada",
        ),
        "ruido": ReglaPrueba(
            aplica="si",
            metricas=("ruido_centro_hu",),
            tipo_tolerancia="linea_base_rel",
            tolerancia=0.20,
            unidad="1",
            fuente="AAPM TG-142 (baseline)",
            estado="norma",
        ),
        "bajo_contraste": ReglaPrueba(
            aplica="si",
            metricas=("lc_visibles_1pct",),
            tipo_tolerancia="linea_base_min",
            tolerancia=1.0,
            unidad="conteo",
            fuente=(
                "Propuesta del plan; el formato IDC-F-RT-120 pide además \"menor círculo "
                "observable\" en los grupos 1 %/0.5 %/0.3 % (visual, P6)"
            ),
            estado="propuesta",
        ),
        "resolucion_espacial": ReglaPrueba(
            aplica="si",
            metricas=("mtf10_lpcm",),
            tipo_tolerancia="min",
            tolerancia=5.0,
            unidad="lp/cm",
            fuente=(
                "IDC-F-RT-120 (visual, ≥5 lp/cm) + AAPM TG-179. Techo físico ≈5.2 lp/cm con "
                "el FOV de 491 mm de la serie de QA (P4/P7)"
            ),
            estado="confirmada",
        ),
    },
)

PERFILES = {
    "Tomógrafo": PERFIL_TOMOGRAFO,
    "Clinac ix": PERFIL_CLINAC_IX,
    "Halcyon": PERFIL_HALCYON,
}
