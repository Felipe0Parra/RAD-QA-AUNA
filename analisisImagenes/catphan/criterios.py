"""G.3 (PLAN_HANDOFF_IMAGENES_22-09.md §7bis): cada prueba juzga con el criterio de SU equipo.

CAUSA. Los criterios eran constantes iguales para tres equipos cuyo ruido va de 4.95 a 17.63 HU, cuyo píxel limita la
resolución a 4.65 / 5.21 / 7.68 lp/cm y cuya escala de HU difiere ≈ 490. En el código: `cnr_lim=1.0` y
`visibilidad_lim=0.1` escritos en la pantalla, `>= 4` de 6 ROI dentro de la función, `hu_tolerancia=40.0`, umbrales de UI e
INU de 2 %, rangos nominales de HU de un CT calibrado. La matriz por equipo existía (`perfiles.py`, con su censo) y
nadie la leía.

Este módulo es el PUENTE: recibe lo que la aplicación mide en cada categoría y lo juzga con la regla que
`perfiles.PERFILES[equipo]` tiene para esa prueba, dejando a la vista de dónde sale el criterio y qué tan firme es
(`norma` / `propuesta` / `confirmada`). Tres reglas de diseño:

  1. UNA SOLA FUENTE DE CRITERIO. Ningún umbral de juicio se escribe en la pantalla: sale de `perfiles.py`.
  2. NO SE INVENTAN EQUIVALENCIAS. `perfiles.py` nombra métricas del motor pylinac. Solo se juzga con una regla cuando la
     función de la app produce EXACTAMENTE esa métrica (`EQUIVALENCIAS`); donde no, el estado es
     `criterio pendiente de métrica` y se dice por qué. Nunca se conecta un umbral a una métrica dudosa.
  3. SIN LÍNEA BASE NO HAY VEREDICTO. Una regla contra línea base sin línea base sale `Sin línea base`, nunca `Cumple` ni
     `No cumple` (las líneas base de imagen no existen todavía: F.1 del plan del 18-09).

`PARAMETROS_HEREDADOS` guarda, en UN sitio y marcados como tales, los parámetros de MEDICIÓN de la métrica actual que
no tienen fuente normativa (D-18): qué cuenta como ROI visible y los umbrales de UI/INU que las columnas `pasa_*` de la BD
siguen guardando. NO son veredicto.
"""
from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from typing import Optional

from analisisImagenes.catphan.perfiles import PERFILES, ReglaPrueba, evaluar

ESTADO_PENDIENTE = "Criterio pendiente de métrica"
ESTADO_SIN_PERFIL = "Sin criterio definido"
CUMPLE = "Cumple"
NO_CUMPLE = "No cumple"
SIN_LINEA_BASE = "Sin línea base"
INFORMATIVO = "Informativo"
NO_APLICA = "No aplica"

# Estados que NO son un veredicto de cumple / no cumple.
ESTADOS_SIN_VEREDICTO = (SIN_LINEA_BASE, INFORMATIVO, NO_APLICA, ESTADO_PENDIENTE, ESTADO_SIN_PERFIL)

# Categorías de la aplicación (las de `pruebas` / `_registrar_adquisicion`) -> prueba de `perfiles.PRUEBAS`.
CATEGORIA_A_PRUEBAS = {
    "espesor": ("espesor",),
    "tamano_pixel": ("geometria",),
    "resolucion_contraste": ("bajo_contraste",),
    "resolucion_espacial": ("resolucion_espacial",),
    "valores_ct": ("numeros_ct",),
    "linealidad_ct": ("linealidad",),
    "uniformidad": ("uniformidad", "ruido"),
}

# Las métricas de la regla que la aplicación SÍ produce igual que el motor. Lo que no está aquí queda pendiente.
#   hu_<material>     <- `promedio_hu` de cada ROI de `valor_numero_ct`
#   linealidad_r2     <- r² de `linealidad_ct` (la app guarda el coeficiente de correlación r, D-30; R² = r²)
#   unif_max_dif_hu   <- máx |ROI - centro| sobre los cuatro ROI periféricos de `uniformidad`
#   ruido_centro_hu   <- desviación estándar del ROI central de `uniformidad`
#   espesor_mm        <- `espesor_promedio_mm` de `espesor_corte` (E.1/E.2, 24-09: mismo algoritmo y cortes que
#                        pylinac, ±0.005 mm en las 5 series); la referencia es el nominal DICOM de la serie
EQUIVALENCIAS = {
    "espesor": ("espesor_mm",),
    "numeros_ct": ("hu_aire", "hu_pmp", "hu_ldpe", "hu_poliestireno", "hu_acrilico", "hu_delrin", "hu_teflon"),
    "linealidad": ("linealidad_r2",),
    "uniformidad": ("unif_max_dif_hu",),
    "ruido": ("ruido_centro_hu",),
}

# Por qué cada una de las pruebas SIN equivalencia queda pendiente de métrica.
MOTIVO_PENDIENTE = {
    "geometria": (
        "la regla mide cuatro distancias de 50 mm; la función actual mide el tamaño del píxel, no esas distancias"),
    "bajo_contraste": (
        "la regla cuenta los insertos de 1 % visibles con la métrica de pylinac; la función actual cuenta ROI por CNR "
        "(≥ 1: 5 o 6 de 6 en todas las series, también con 17.6 HU de ruido) y por visibilidad, y el físico decide cuál "
        "es el criterio (tabla ROI por ROI de G.3)"),
    "resolucion_espacial": (
        "la regla pide la MTF al 10 %; la función actual reporta las regiones de pares de líneas que resuelve, y con el "
        "píxel del Halcyon ese método no demuestra el criterio de 5 lp/cm (B.1)"),
}

# ---------------------------------------------------------------------------
# Parámetros de MEDICIÓN heredados (D-18): sin fuente normativa, NO son veredicto
# ---------------------------------------------------------------------------
PARAMETROS_HEREDADOS = {
    # Qué cuenta como ROI visible en `resolucion_contraste` y cuántos hacen falta para el `pasa_test_*` heredado
    # que la BD sigue guardando. El veredicto de esta prueba NO sale de aquí: está pendiente de métrica.
    "resolucion_contraste": {"cnr_lim": 1.0, "visibilidad_lim": 0.1, "min_rois_visibles": 4},
    # Umbrales de UI e INU (pylinac) con los que se calculan las columnas `pasa_ui`/`pasa_inu`/`pasa_global` de la
    # BD. El veredicto de uniformidad sale de `perfiles.py` (diferencia máxima con el centro), no de estos.
    "uniformidad": {"ui_threshold_pct": 2.0, "inu_threshold_pct": 2.0},
}


@dataclass
class Juicio:
    """Una fila de criterio y veredicto: qué se juzgó, con qué regla y qué salió."""
    categoria: str
    prueba: str
    metrica: str
    etiqueta: str
    valor: Optional[float]
    unidad: str
    estado: str                 # CUMPLE | NO_CUMPLE | SIN_LINEA_BASE | INFORMATIVO | NO_APLICA | ESTADO_PENDIENTE | ...
    criterio: str               # texto legible del criterio
    fuente: str
    estado_regla: str           # 'norma' | 'propuesta' | 'confirmada' | ''
    referencia: Optional[float] = None
    tolerancia: Optional[float] = None

    def a_dict(self) -> dict:
        return asdict(self)

    @property
    def es_veredicto(self) -> bool:
        return self.estado in (CUMPLE, NO_CUMPLE)


def _fmt(x) -> str:
    if x is None:
        return "?"
    return str(int(x)) if float(x) == int(x) else f"{float(x):g}"


def texto_criterio(regla: ReglaPrueba, metrica: str, referencia: Optional[float] = None) -> str:
    """El criterio de una regla, en palabras (sin símbolos de correcto/incorrecto, DA-18)."""
    if regla.aplica == "no":
        return regla.motivo_no_aplica or "no aplica"
    if regla.aplica == "informativo":
        return "informativo, sin umbral"
    t = regla.tolerancia
    tol = t.get(metrica) if isinstance(t, dict) else t
    unidad = f" {regla.unidad}" if regla.unidad and regla.unidad != "1" else ""
    tipo = regla.tipo_tolerancia
    if tipo == "abs_nominal":
        nominal = regla.nominal if regla.nominal is not None else referencia
        base = _fmt(nominal) if nominal is not None else "el nominal de la serie"
        return f"{base} ± {_fmt(tol)}{unidad}"
    if tipo == "max":
        return f"como máximo {_fmt(tol)}{unidad}"
    if tipo == "min":
        return f"como mínimo {_fmt(tol)}{unidad}"
    if tipo == "linea_base_abs":
        return f"± {_fmt(tol)}{unidad} de la línea base"
    if tipo == "linea_base_rel":
        return f"± {_fmt(tol * 100)} % de la línea base"
    if tipo == "linea_base_min":
        return f"no menos de la línea base − {_fmt(tol)}{unidad}"
    return "criterio no definido"


def _regla(equipo: Optional[str], prueba: str) -> Optional[ReglaPrueba]:
    perfil = PERFILES.get(equipo)
    return None if perfil is None else perfil.reglas.get(prueba)


def _norm(texto: str) -> str:
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()


_MATERIAL_A_METRICA = {
    "aire": "hu_aire", "pmp": "hu_pmp", "ldpe": "hu_ldpe", "poliestireno": "hu_poliestireno",
    "acrilico": "hu_acrilico", "delrin": "hu_delrin", "derlin": "hu_delrin", "teflon": "hu_teflon",
}
_ETIQUETAS = {
    "espesor": "Espesor de corte",
    "linealidad_r2": "Linealidad (R²)",
    "unif_max_dif_hu": "Máxima diferencia con el centro",
    "ruido_centro_hu": "Ruido (desviación del ROI central)",
    "geometria": "Geometría",
    "bajo_contraste": "Bajo contraste",
    "resolucion_espacial": "Resolución espacial",
}
_METRICA_PENDIENTE = {"espesor": "espesor_mm", "geometria": "geo_x1_mm", "bajo_contraste": "lc_visibles_1pct",
                      "resolucion_espacial": "mtf10_lpcm"}


def _juicio(categoria, prueba, metrica, etiqueta, valor, regla, referencia=None, linea_base=None) -> Juicio:
    """Aplica `perfiles.evaluar` y lo envuelve con el texto del criterio y su fuente. Sin valor medido no hay nada
    que juzgar: la regla se muestra `Informativo`, nunca `Cumple`."""
    criterio = texto_criterio(regla, metrica, referencia)
    if valor is None:
        return Juicio(categoria, prueba, metrica, etiqueta, None, regla.unidad, INFORMATIVO,
                      criterio + " (sin valor medido)", regla.fuente, regla.estado, referencia, None)
    v = evaluar(regla, valor, metrica=metrica, referencia=referencia, linea_base=linea_base)
    return Juicio(categoria, prueba, metrica, etiqueta, valor, regla.unidad, v.estado, criterio, v.fuente,
                  regla.estado, v.referencia, v.tolerancia)


def _pendiente(categoria, prueba, regla: Optional[ReglaPrueba]) -> Juicio:
    metrica = _METRICA_PENDIENTE.get(prueba, prueba)
    if regla is not None and regla.aplica == "no":     # la regla dice que no aplica: eso manda
        return Juicio(categoria, prueba, metrica, _ETIQUETAS.get(prueba, prueba), None, "", NO_APLICA,
                      regla.motivo_no_aplica or "no aplica", regla.fuente, regla.estado)
    criterio = texto_criterio(regla, metrica) if regla is not None else "sin regla"
    return Juicio(categoria, prueba, metrica, _ETIQUETAS.get(prueba, prueba), None,
                  regla.unidad if regla else "", ESTADO_PENDIENTE,
                  f"{criterio}. Pendiente de métrica: {MOTIVO_PENDIENTE[prueba]}",
                  regla.fuente if regla else "", regla.estado if regla else "")


# ---------------------------------------------------------------------------
# Valores que la aplicación mide, en la métrica de la regla
# ---------------------------------------------------------------------------

def _hu_por_metrica(resultados_ct) -> dict:
    """{'hu_pmp': promedio_hu, ...} desde el resultado de `valor_numero_ct` (lista, o dict con 'resultados')."""
    if isinstance(resultados_ct, dict) and "resultados" in resultados_ct:
        resultados_ct = resultados_ct["resultados"]
    salida = {}
    for r in resultados_ct or []:
        clave = _MATERIAL_A_METRICA.get(_norm(r.get("material", "")))
        if clave and r.get("promedio_hu") is not None:
            salida[clave] = float(r["promedio_hu"])
    return salida


def unif_max_dif_hu(resultados_uniformidad: dict) -> Optional[float]:
    """Máx |ROI − centro| sobre los cuatro ROI periféricos: la métrica `unif_max_dif_hu` del motor."""
    centro = (resultados_uniformidad.get("Centro") or {}).get("promedio_hu")
    if centro is None:
        return None
    difs = [abs(resultados_uniformidad[n]["promedio_hu"] - centro)
            for n in ("Arriba", "Abajo", "Izquierda", "Derecha")
            if (resultados_uniformidad.get(n) or {}).get("promedio_hu") is not None]
    return float(max(difs)) if difs else None


def ruido_centro_hu(resultados_uniformidad: dict) -> Optional[float]:
    valor = (resultados_uniformidad.get("Centro") or {}).get("desviacion")
    return None if valor is None else float(valor)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def juzgar(equipo: Optional[str], categoria: str, resultados, linea_base: Optional[dict] = None) -> list:
    """Los `Juicio` de una categoría para `equipo`. Nunca falla en silencio: un equipo sin perfil, una categoría sin
    valor o una prueba sin equivalencia salen con su estado (`Sin criterio definido`, `Informativo`, `Criterio
    pendiente de métrica`), no como un `Cumple` por omisión.

    `resultados`: lo que devuelve la función de análisis de la categoría (para `linealidad_ct`, el dict con `r_squared`). `linea_base`: `{metrica: valor}`; hoy no existe ninguna."""
    if categoria not in CATEGORIA_A_PRUEBAS:
        raise KeyError(f"categoría desconocida: {categoria!r}")
    linea_base = linea_base or {}
    pruebas = CATEGORIA_A_PRUEBAS[categoria]
    if equipo not in PERFILES:
        return [Juicio(categoria, p, _METRICA_PENDIENTE.get(p, p), _ETIQUETAS.get(p, p), None, "",
                       ESTADO_SIN_PERFIL, f"el equipo {equipo!r} no tiene perfil de criterios", "", "")
                for p in pruebas]

    juicios = []
    for prueba in pruebas:
        regla = _regla(equipo, prueba)
        if prueba in MOTIVO_PENDIENTE:
            juicios.append(_pendiente(categoria, prueba, regla))
            continue
        if regla is None:
            juicios.append(Juicio(categoria, prueba, prueba, prueba, None, "", ESTADO_SIN_PERFIL,
                                  "el perfil no trae regla para esta prueba", "", ""))
            continue
        if regla.aplica == "no":
            juicios.append(Juicio(categoria, prueba, EQUIVALENCIAS[prueba][0], _ETIQUETAS.get(prueba, prueba),
                                  None, regla.unidad, NO_APLICA, regla.motivo_no_aplica or "no aplica",
                                  regla.fuente, regla.estado))
            continue

        if prueba == "numeros_ct":
            hu = _hu_por_metrica(resultados)
            for metrica in EQUIVALENCIAS["numeros_ct"]:
                material = metrica[len("hu_"):]
                juicios.append(_juicio(categoria, prueba, metrica, f"HU de {material}", hu.get(metrica), regla,
                                       linea_base=linea_base.get(metrica)))
        elif prueba == "linealidad":
            r = (resultados or {}).get("r_squared")
            valor = None if r is None else float(r) ** 2      # la app guarda r; la regla pide R² = r²
            juicios.append(_juicio(categoria, prueba, "linealidad_r2", _ETIQUETAS["linealidad_r2"], valor, regla))
        elif prueba == "uniformidad":
            juicios.append(_juicio(categoria, prueba, "unif_max_dif_hu", _ETIQUETAS["unif_max_dif_hu"],
                                   unif_max_dif_hu(resultados or {}), regla))
        elif prueba == "ruido":
            juicios.append(_juicio(categoria, prueba, "ruido_centro_hu", _ETIQUETAS["ruido_centro_hu"],
                                   ruido_centro_hu(resultados or {}), regla,
                                   linea_base=linea_base.get("ruido_centro_hu")))
        elif prueba == "espesor":
            valor = (resultados or {}).get("espesor_promedio_mm")
            nominal = (resultados or {}).get("espesor_teorico_mm")
            if valor is not None and nominal is None:      # sin nominal DICOM no hay contra qué juzgar
                juicios.append(Juicio(categoria, prueba, "espesor_mm", _ETIQUETAS["espesor"], float(valor),
                                      regla.unidad, INFORMATIVO, texto_criterio(regla, "espesor_mm")
                                      + " (la serie no trae espesor nominal)", regla.fuente, regla.estado))
            else:
                juicios.append(_juicio(categoria, prueba, "espesor_mm", _ETIQUETAS["espesor"],
                                       None if valor is None else float(valor), regla, referencia=nominal))
    return juicios


def parametros_de_analisis(categoria: str, equipo: Optional[str]) -> dict:
    """Los argumentos de umbral que la pantalla le pasa a la función de análisis de `categoria`: ninguno escrito a
    mano en la pantalla. `hu_tolerancia` (uniformidad) sale de la regla del equipo; el resto son los parámetros de
    medición heredados (`PARAMETROS_HEREDADOS`), que no son veredicto."""
    parametros = dict(PARAMETROS_HEREDADOS.get(categoria, {}))
    if categoria == "uniformidad":
        regla = _regla(equipo, "uniformidad")
        parametros["hu_tolerancia"] = regla.tolerancia if regla is not None and regla.aplica == "si" else None
    return parametros


def a_json_ready(juicios) -> list:
    return [j.a_dict() for j in juicios]


# ---------------------------------------------------------------------------
# Texto para la persona (pantalla y PDF): palabras y color, sin símbolos (DA-18)
# ---------------------------------------------------------------------------
_COLOR = {CUMPLE: "#1e8449", NO_CUMPLE: "#c0392b"}
_COLOR_OTROS = "#566573"


def texto_valor(juicio: Juicio) -> str:
    """El valor medido con su unidad, o '' si no hay."""
    if juicio.valor is None:
        return ""
    unidad = f" {juicio.unidad}" if juicio.unidad and juicio.unidad != "1" else ""
    return f"{juicio.valor:.4g}{unidad}"


def texto_fuente(juicio: Juicio) -> str:
    """La fuente de la regla y qué tan firme es (norma / propuesta / confirmada)."""
    if not juicio.fuente:
        return ""
    return f"{juicio.fuente} ({juicio.estado_regla})" if juicio.estado_regla else juicio.fuente


def texto_html(juicios) -> str:
    """El panel de criterio y veredicto de una categoría, para un QLabel RichText. Todo lo que viene del perfil o de la
    medición se escapa: una fuente con `<` o `&` no rompe el marcado."""
    import html as _html
    esc = _html.escape
    if not juicios:
        return ""
    bloques = []
    for j in juicios:
        color = _COLOR.get(j.estado, _COLOR_OTROS)
        valor = texto_valor(j)
        linea = f"<b>{esc(j.etiqueta)}</b>" + (f": {esc(valor)}" if valor else "")
        linea += f" &mdash; <b style='color:{color}'>{esc(j.estado)}</b>"
        detalle = f"Criterio: {esc(j.criterio)}."
        if j.fuente:
            detalle += f" Fuente: {esc(texto_fuente(j))}."
        bloques.append(f"<div style='margin-bottom:4px'>{linea}<br>"
                       f"<span style='color:{_COLOR_OTROS}'>{detalle}</span></div>")
    return "<div><b>Criterio y veredicto del equipo</b>" + "".join(bloques) + "</div>"
