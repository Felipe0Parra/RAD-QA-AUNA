"""CD.3 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md): el motor de la curva de dosis de las películas radiocrómicas. Sin Qt y sin base de datos: funciones puras y dataclasses congeladas.

De unas piezas de película irradiadas a dosis conocidas (medidas con la cámara de ionización) y medidas con LA medición de CD.2 (`pelicula.medir_pieza_uniforme`), sale para cada capa (R, G, B y gris)
la curva que lleva la densidad óptica neta a dosis, y dice hasta dónde se le puede creer:

  - el CERO (DC3, CD-Z1 del 23-10, una sola regla y en este orden): las piezas de 0 cGy de la calibración; si no hay, la película virgen montada (la referencia de OD.1) si es válida, se escaneó con la
    misma cadena de captura que las piezas y trae la región central de su tabla de uniformidad (sin ella no hay con qué medir su incertidumbre, DC2: una virgen angosta es «ok» sin esa región); y si tampoco,
    la pieza de menor dosis, con las dosis de las demás contadas desde ella: esa curva es una GUÍA y nunca pasa a dosis (condición 5 de DC8);
  - la netOD de cada pieza contra el cero, netOD = log10(I0 / I), con su u por la ecuación 2 de Vargas-Segura (DC3);
  - el modelo de Devic et al. 2004, D(x) = a·x + b·x^n con a ≥ 0, b ≥ 0 y 1 ≤ n ≤ 4 (DC4): pasa por el origen y es monótono por construcción. Se ajusta por mínimos cuadrados de los residuos
    RELATIVOS (cada dosis pesa por su porcentaje) y es determinista: para cada uno de unos arranques fijos de n, a y b salen exactos de unos mínimos cuadrados no negativos, y el mejor arranque se afina
    en su vecindad; se elige el de menor costo;
  - el rango útil, el estado y el límite de cada capa (DC5), y dos avisos que no cambian el estado (el fondo del escáner y el lugar del vidrio, H2).

`CurvaDeDosis.dosis` y `CurvaDeDosis.netod` son las ÚNICAS definiciones de la curva y de su inversa: quien convierta una densidad óptica en dosis (CD.6, CD.7) las llama, nunca escribe la fórmula.
Los umbrales viven en `PARAMETROS_DE_LA_CURVA`, con su nombre, su unidad y su motivo (PD1), y son una PROPUESTA sin una calibración real detrás: los recalibra CD.10 (deuda declarada).
"""
import math
from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import minimize_scalar, nnls

from analisisImagenes.pelicula import (CAPAS_DEL_PISO, PROFUNDIDAD_MAXIMA_DE_LO_LIBRE, MedidaDePieza, ReferenciaVirgen, _anida_mas_de, _es_entero, _es_numero, _json_normal)

# ============================================================================================================================================ los parámetros (PD1)

PARAMETROS_DE_LA_CURVA = {
    "piezas_minimas": {
        "valor": 6, "unidad": "dosis distintas",
        "motivo": "Una curva es «válida» con 6 dosis irradiadas distintas o más dentro de su rango útil, además del cero: con 3 parámetros (a, b y n) y menos puntos el ajuste no se puede comprobar "
                  "(las réplicas de una misma dosis nominal cuentan una vez) [propuesta de DC5, para recalibrar en CD.10]."},
    "residuo_maximo_pct": {
        "valor": 3.0, "unidad": "%",
        "motivo": "Cada pieza del rango útil tiene que quedar a ±3 % de su dosis medida (Vargas-Segura 2023: la mayor incertidumbre, 1.4 % a 51.5 cGy; la cámara, 2 %) [propuesta de DC5]."},
    "residuo_maximo_bajas_pct": {
        "valor": 5.0, "unidad": "%",
        "motivo": "Por debajo de `dosis_baja_cgy` la tolerancia es ±5 %: la misma incertidumbre de la densidad óptica es un porcentaje mayor de una dosis chica [propuesta de DC5]."},
    "dosis_baja_cgy": {
        "valor": 100.0, "unidad": "cGy",
        "motivo": "Las piezas de menos de 100 cGy (contadas desde el cero) se juzgan con `residuo_maximo_bajas_pct` [propuesta de DC5]."},
    "resolucion_maxima_pct": {
        "valor": 3.0, "unidad": "%",
        "motivo": "El rango útil termina en la dosis más alta cuya resolución en dosis, δD / D = u(netOD) · D′(x) / D, es de 3 % o menos: más arriba la película se satura y una diferencia de "
                  "densidad óptica dentro de su incertidumbre son muchos cGy [propuesta de DC5]."},
    "separacion_minima_u": {
        "valor": 2.0, "unidad": "incertidumbres estándar (u)",
        "motivo": "Y donde la netOD de una dosis ya no supera a la de la dosis anterior en más de 2 u (la u de esa diferencia): las dos dosis no se distinguen. Si la netOD BAJA más de 2 u los datos no "
                  "son monótonos (una pieza cambiada de fila, o mal irradiada) y la curva de esa capa no es válida [propuesta de DC5]."},
    "distancia_en_el_vidrio_mm": {
        "valor": 20.0, "unidad": "mm",
        "motivo": "Una pieza cuyo centro está a más de 20 mm del centro del cero en la página del escáner se escaneó en otro lugar del vidrio: la respuesta lateral del escáner (H2: de 1.3 a 6.7 % "
                  "por 10 cm) cambia su valor. Solo avisa [propuesta del bloque de CD.3]."},
    "diferencia_de_fondo_blanco": {
        "valor": 0.005, "unidad": "fracción",
        "motivo": "Si la fracción del fondo del escáner que está en el blanco máximo (la prueba C3 de CD.2) de una pieza se aparta más de 0.005 de la del cero, el escáner pudo ajustar la exposición "
                  "entre escaneos: es la misma holgura con que la película virgen avisa (`fondo_blanco_minimo`, 0.995). Solo avisa [propuesta del pre-vuelo de CD.3]."},
    "modelo": {
        "valor": "devic", "unidad": "nombre",
        "motivo": "D(x) = a·x + b·x^n (Devic et al. 2004), con a ≥ 0, b ≥ 0 y 1 ≤ n ≤ 4: el que eligió el físico el 23-10 (P6 de la curva, DA-90). Es UNO, declarado y guardado con la curva."},
    "version": {
        "valor": "CD-1", "unidad": "nombre",
        "motivo": "La versión de la curva (DC13): viaja con cada curva guardada y una de otra versión se rechaza al leerla."},
}
VALORES_DE_LA_CURVA = {nombre: _json_normal(parametro["valor"]) for nombre, parametro in PARAMETROS_DE_LA_CURVA.items()}
VERSION_CURVA = PARAMETROS_DE_LA_CURVA["version"]["valor"]
MODELO_DEVIC = PARAMETROS_DE_LA_CURVA["modelo"]["valor"]

# El modelo mismo (DC4), no umbrales que CD.10 recalibre: las cotas de n y los arranques fijos del ajuste.
COTAS_DE_N = (1.0, 4.0)
ARRANQUES_DE_N = tuple(round(COTAS_DE_N[0] + 0.05 * k, 2) for k in range(61))          # n de 1.00 a 4.00 cada 0.05: para cada uno, a y b exactos (mínimos cuadrados no negativos)
TOLERANCIA_DEL_AFINADO = 1e-10                                                           # el afinado de n alrededor del mejor arranque (Brent acotado, `xatol`)
PARAMETROS_MINIMOS_DEL_AJUSTE = 3                                                        # con menos piezas que parámetros no se ajusta (a, b y n)
TOLERANCIA_DE_LA_INVERSA = 1e-12                                                         # la bisección de `netod` para cuando su intervalo mide esto o menos (en netOD)
ITERACIONES_MAXIMAS_DE_LA_INVERSA = 200

FUENTES_DEL_CERO = ("piezas_de_0_cgy", "pelicula_virgen", "pieza_de_menor_dosis")
ESTADO_VALIDA = "válida"
OK_SIN_VALOR = "es «ok» y no trae su valor y su u como números de 0 o más"          # CD3-REV1-03: una pieza «ok» siempre los trae (`pieza_de_calibracion`) y `ajustar` los necesita
PREFIJO_INCOMPLETA = "incompleta: "
PREFIJO_NO_VALIDA = "no válida: "
PREFIJO_GUIA = "guía: "
MOTIVO_SIN_CERO = "falta la película virgen (0 cGy)"
MOTIVO_GUIA = "el cero es la pieza de {nominal:g} cGy"          # CD3-REV1-04: una pieza se nombra por su dosis NOMINAL en todos los textos; la medida, con que se cuentan las demás, va en el detalle del cero
MOTIVO_FALTA_DOSIS = "falta la dosis medida de la pieza {orden} ({nominal:g} cGy)"
MOTIVO_DOSIS_NO_POSITIVA = "la dosis medida de la pieza {orden} ({nominal:g} cGy) no es positiva"
MOTIVO_POCAS_DOSIS = "quedan {n} dosis en el rango útil (hacen falta {minimo})"
MOTIVO_NO_MONOTONOS = "datos no monótonos: la pieza de {nominal:g} cGy tiene menos densidad óptica que la de {anterior:g} cGy"
MOTIVO_RESIDUO = "el residuo de la pieza de {nominal:g} cGy es {residuo:+.2f} % (la tolerancia es ±{tolerancia:g} %)"
MOTIVO_NO_CONVERGE = "el ajuste no converge"
MOTIVO_OTRA_CADENA = "las piezas no se escanearon con la misma cadena de captura ({cadenas})"
LIMITE_RECORTE = "la capa está recortada por el escáner desde la pieza de {nominal:g} cGy"
LIMITE_SEPARACION = ("la pieza de {nominal:g} cGy no se distingue de la de {anterior:g} cGy: su netOD sube {subida:.4f} y hacen falta más de {minimo:g} u ({umbral:.4f})")
LIMITE_RESOLUCION = "la resolución en dosis pasa de {maximo:g} % desde la pieza de {nominal:g} cGy (δD / D = {resolucion:.2f} %)"
LIMITE_SIN_RESOLUCION = "la resolución en dosis pasa de {maximo:g} % en todas las piezas"
AVISO_FUERA_DE_LA_CURVA = "la pieza {orden} ({nominal:g} cGy) no entra en la curva: {estado}"
AVISO_EXPOSICION = ("pieza {orden} ({nominal:g} cGy): el escáner pudo ajustar la exposición entre escaneos: el {fraccion:.2f} % de su fondo está en el blanco máximo y el {cero:.2f} % del "
                    "fondo del cero")
AVISO_OTRO_LUGAR = ("pieza {orden} ({nominal:g} cGy): la pieza se escaneó en otro lugar del vidrio: su centro está a {distancia:.1f} mm del centro del cero (más de {maximo:g} mm)")
AVISO_VIRGEN_NO_SIRVE = "la película virgen montada no sirve de cero: {motivo}"
MOTIVO_VIRGEN_SIN_CENTRO = "no tiene la región central de la tabla de uniformidad y ruido, y sin ella no hay con qué medir su incertidumbre (DC2)"          # CD3-REV1-01
MOTIVO_SIN_VALOR_POSITIVO = "su valor no es positivo en {capas} y sin un valor positivo no hay densidad óptica neta"          # CD3-PROD-D1: netOD = log10(I0 / I) pide I0 > 0
AVISO_NO_SIRVE_DE_CERO = "la pieza {orden} ({nominal:g} cGy) no sirve de cero: {motivo}"          # CD3-PROD-D1
MOTIVO_REPLICA_DEL_CERO = "es una réplica de la pieza que hace de cero (la pieza {orden})"          # CD3-PROD-D2
MOTIVO_NO_SUPERA_AL_CERO = "su dosis medida ({medida:g} cGy) no supera la del cero ({cero:g} cGy)"          # CD3-PROD-D2

# La prueba C3 de CD.2 deja la fracción del fondo en el blanco máximo SOLO en su texto («el 99.98 % del fondo está en el blanco máximo…»); se lee de ahí con su forma exacta. Un texto de otra forma es
# un cambio de CD.2 que esta lectura no conoce: se lanza `ValueError` (falla una prueba) en lugar de apagar el aviso en silencio.
_TEXTO_DEL_FONDO = "% del fondo está en el blanco máximo"
_SIN_FONDO = "no se ve fondo del escáner; no se juzga"


# ============================================================================================================================================ las piezas

@dataclass(frozen=True, eq=False)
class PiezaDeCalibracion:
    """Una pieza de una calibración (DC1, CD.3): su `orden` (la fila del formulario), su `dosis_nominal_cgy` (0 para la película sin irradiar) y su `dosis_medida_cgy` (la de la cámara de ionización;
    None si no se dio), el `estado` de su medida (el de CD.2: «ok» o «no medible: …») y, por capa (R, G, B y gris), `capas[capa]` = {"valor": I, la media de su región central de 10 × 10 mm (DC2);
    "u": su incertidumbre (DC2: la desviación estándar de las medias de sus cinco regiones de uniformidad si caben, y si no la de los píxeles del centro); "recortada": la fracción en el negro del
    escáner o None (CD2-D5); "netod" y "u_netod": su densidad óptica neta contra el cero de la curva y su u (DC3), None hasta que `ajustar` la pone o si no se pudo calcular; "dosis_cgy": la dosis contada
    desde el cero con que entra al ajuste; "residuo_pct": (D(x) − D) / D en %, o None; "en_el_rango": si está dentro del rango útil de esa capa}. `posicion_mm`: {"x", "y"}, el centro de la pieza en
    la página del escáner, en mm (H2); `fondo_blanco`: la fracción de su fondo en el blanco máximo (C3) o None si no se ve fondo; `archivo` y `sha256`: de dónde salió; `cadena`: su cadena de captura
    (`cadena_de_captura`), que viaja con la pieza para que una curva rehecha desde lo guardado (sin los escaneos, CD.4) la siga comparando; `medida`: la `MedidaDePieza` de CD.2 (None en una curva leída
    de su copia, `curva_desde_dict`)."""
    orden: int
    dosis_nominal_cgy: float
    dosis_medida_cgy: float | None
    estado: str
    capas: dict
    posicion_mm: dict | None
    fondo_blanco: float | None
    archivo: str
    sha256: str | None
    cadena: dict | None
    medida: MedidaDePieza | None = None


_CLAVES_DE_LA_CAPA_DE_UNA_PIEZA = ("valor", "u", "recortada", "netod", "u_netod", "dosis_cgy", "residuo_pct", "en_el_rango")


def _incertidumbre_del_valor(tabla, desviacion_del_centro, capa):
    """DC2: la u del valor de una capa, la desviación estándar (muestral) de las medias de las cinco regiones de uniformidad si caben todas; si no, la de los píxeles de la región central
    (`desviacion_del_centro`), o None si esa región no cupo en la película (una virgen angosta es «ok» sin ella, CD3-REV1-01). La ÚNICA definición: la de una pieza y la de la virgen montada."""
    if tabla is not None and tabla.get("cabe"):
        medias = [m for m in tabla["capas"][capa]["regiones"].values() if m is not None]
        return float(np.std(medias, ddof=1))
    return None if desviacion_del_centro is None else float(desviacion_del_centro)


def fondo_blanco_de(pruebas):
    """La fracción del fondo del escáner que está en el blanco máximo, leída de la prueba «C3 fondo» de una medición (CD.2), o None si no se ve fondo o la medición no llegó a mirarlo. `ValueError` si
    el texto de la prueba no tiene ninguna de sus dos formas: CD.2 lo cambió y esta lectura tiene que cambiar con él."""
    for prueba in pruebas:
        if prueba.nombre != "C3 fondo":
            continue
        if prueba.texto == _SIN_FONDO:
            return None
        cabeza, separador, cola = prueba.texto.partition(" " + _TEXTO_DEL_FONDO)
        cifra = cabeza[3:]
        if not separador or not cabeza.startswith("el ") or not (cola == "" or cola.startswith(":")) or not cifra.replace(".", "", 1).isdigit():
            raise ValueError(f"La prueba «C3 fondo» no tiene la forma que conoce la curva de dosis: {prueba.texto!r}.")
        return float(cifra) / 100.0
    return None


def pieza_de_calibracion(orden, dosis_nominal_cgy, dosis_medida_cgy, medida):
    """Una `PiezaDeCalibracion` desde la `MedidaDePieza` de CD.2 (`medir_pieza_uniforme`, con `escala="declarada"` en una calibración, DC15). `orden`: un entero (la fila); `dosis_nominal_cgy`: un
    número de 0 o más (0 = la película sin irradiar); `dosis_medida_cgy`: un número o None (si falta en una pieza irradiada la curva queda «incompleta», `ajustar`). Lo que la pieza no tiene (una medida
    «no medible») queda en None. `ValueError` si los argumentos no son de esos tipos (un error de quien llama, no del contenido)."""
    if not _es_entero(orden):
        raise ValueError(f"El orden de una pieza es un entero, no {orden!r}.")
    if not _es_numero(dosis_nominal_cgy) or dosis_nominal_cgy < 0:
        raise ValueError(f"La dosis nominal de una pieza es un número de 0 o más, no {dosis_nominal_cgy!r}.")
    if dosis_medida_cgy is not None and not _es_numero(dosis_medida_cgy):
        raise ValueError(f"La dosis medida de una pieza es un número o None, no {dosis_medida_cgy!r}.")
    if not isinstance(medida, MedidaDePieza):
        raise ValueError("La medida de una pieza es la `MedidaDePieza` de `pelicula.medir_pieza_uniforme`.")
    ok = medida.estado == "ok"
    capas = {}
    for c in CAPAS_DEL_PISO:
        capas[c] = dict.fromkeys(_CLAVES_DE_LA_CAPA_DE_UNA_PIEZA)
        if ok:
            capas[c].update(valor=float(medida.valor(c)), u=_incertidumbre_del_valor(medida.uniformidad, medida.centro[c]["desviacion"], c),
                            recortada=None if medida.recortadas[c] is None else float(medida.recortadas[c]))
        capas[c]["en_el_rango"] = False
    posicion = None
    if ok and medida.region and medida.region.get("pelicula_mm"):
        caja = medida.region["pelicula_mm"]
        posicion = {"x": round(caja["x"] + caja["ancho"] / 2.0, 2), "y": round(caja["y"] + caja["alto"] / 2.0, 2)}
    return PiezaDeCalibracion(int(orden), float(dosis_nominal_cgy), None if dosis_medida_cgy is None else float(dosis_medida_cgy), medida.estado, capas, posicion,
                              fondo_blanco_de(medida.pruebas) if ok else None, medida.procedencia.get("archivo") or "", medida.procedencia.get("sha256"),
                              cadena_de_captura(medida.procedencia), medida)


def cadena_de_captura(procedencia):
    """La cadena de captura de una medición (la condición 3 de DC8): el escáner que declara el archivo, los bits por canal, la resolución declarada y el formato, de la procedencia de CD.2. Dos
    mediciones son de la misma cadena si estos cuatro coinciden."""
    return {"equipo": procedencia.get("equipo"), "bits": procedencia.get("bits"), "dpi": procedencia.get("dpi_declarado"), "formato": procedencia.get("formato")}


def _texto_de_la_cadena(cadena):
    equipo = cadena["equipo"] or "escáner sin declarar"
    dpi = "sin resolución" if cadena["dpi"] is None else f"{cadena['dpi']:g} ppp"
    return f"{equipo}, {cadena['bits']} bits, {dpi}, {cadena['formato']}"


# ============================================================================================================================================ el modelo y el ajuste

def _devic(x, a, b, n):
    """D(x) = a·x + b·x^n para x ≥ 0, y la extensión IMPAR para x < 0: D(−x) = −D(x). El ruido bajo la virgen da una densidad óptica negativa pequeña y su dosis es una dosis negativa pequeña, sin
    romper: para x ≥ 0 la extensión no cambia nada."""
    x = np.asarray(x, float)
    ax = np.abs(x)
    return np.sign(x) * (a * ax + b * ax ** n)


def _derivada_de_devic(x, a, b, n):
    """D′(x) = a + n·b·x^(n−1), par (la derivada de una función impar): D′(−x) = D′(x)."""
    ax = np.abs(np.asarray(x, float))
    return a + n * b * ax ** (n - 1.0)


def _ab_para_n(x, d, n):
    """Para un n fijo, (a, b) ≥ 0 que minimizan la suma de los residuos RELATIVOS al cuadrado, Σ ((a·x + b·x^n − D) / D)², y ese costo: mínimos cuadrados no negativos, exactos y deterministas."""
    matriz = np.column_stack((x / d, x ** n / d))
    (a, b), norma = nnls(matriz, np.ones_like(d))
    return float(a), float(b), float(norma) ** 2


def _ajustar_devic(x, d):
    """El ajuste de Devic de una capa: los arranques fijos de n (`ARRANQUES_DE_N`), a y b exactos para cada uno, el de menor costo y su afinado acotado entre sus dos vecinos (Brent). Devuelve
    (a, b, n, costo) o None si no converge (un costo o unos parámetros no finitos, o a = b = 0)."""
    costos = [_ab_para_n(x, d, n)[2] for n in ARRANQUES_DE_N]
    k = int(np.argmin(costos))
    n, costo = ARRANQUES_DE_N[k], costos[k]
    bajo, alto = ARRANQUES_DE_N[max(k - 1, 0)], ARRANQUES_DE_N[min(k + 1, len(ARRANQUES_DE_N) - 1)]
    afinado = minimize_scalar(lambda m: _ab_para_n(x, d, m)[2], bounds=(bajo, alto), method="bounded", options={"xatol": TOLERANCIA_DEL_AFINADO})
    if afinado.success and np.isfinite(afinado.fun) and afinado.fun < costo:
        n = float(afinado.x)
    a, b, costo = _ab_para_n(x, d, n)
    if not all(np.isfinite(v) for v in (a, b, n, costo)) or a + b <= 0.0:
        return None
    return a, b, float(n), costo


# ============================================================================================================================================ la curva

@dataclass(frozen=True, eq=False)
class CurvaDeDosis:
    """La curva de dosis de una calibración (CD.3). `version` («CD-1») y `modelo` («devic»); `cero`: {"fuente": una de `FUENTES_DEL_CERO`, "detalle": el texto, "dosis_cgy": la dosis del cero (0, o
    la de la pieza de menor dosis), "capas": {capa: {"i0", "u_i0"}}}, o None si no hay con qué hacer el cero; `capas`: {capa: {"estado", "parametros": {"a", "b", "n"} o None, "rango_cgy": la dosis más
    alta del rango útil (contada desde el cero) o None, "netod_maxima": la netOD de esa dosis o None, "rms_pct": el RMS de los residuos del rango útil o None, "costo", "dosis_en_el_rango": cuántas dosis
    distintas, "limite": por qué termina el rango (texto) o None}}; `piezas`: las `PiezaDeCalibracion` con su netOD; `avisos`; `parametros`: los de `PARAMETROS_DE_LA_CURVA` con que se ajustó;
    `u_dosis_medida_pct`: la incertidumbre declarada de la dosis medida (k = 1, en %) o None (P13); `cadena`: la cadena de captura de las piezas, o None si no hay piezas medibles o no es una sola."""
    version: str
    modelo: str
    cero: dict | None
    capas: dict
    piezas: tuple
    avisos: tuple
    parametros: dict
    u_dosis_medida_pct: float | None
    cadena: dict | None

    def _parametros_de(self, capa):
        p = self.capas[capa]["parametros"]
        if p is None:
            raise ValueError(f"La capa {capa} no tiene curva: {self.capas[capa]['estado']}.")
        return p["a"], p["b"], p["n"]

    def dosis(self, capa, x):
        """La dosis (cGy, contada desde el cero de la curva) de una densidad óptica neta `x` (un número o un arreglo) en una capa: D(x) = a·x + b·x^n, con la extensión impar para x < 0. Es la ÚNICA
        definición. No mira el rango útil: si la dosis se puede usar lo decide quien llama (DC8, condición 4: no se extrapola). `ValueError` si la capa no tiene curva."""
        a, b, n = self._parametros_de(capa)
        d = _devic(x, a, b, n)
        return float(d) if np.ndim(d) == 0 else d

    def netod(self, capa, d):
        """La inversa de `dosis`: la densidad óptica neta de una dosis `d` (cGy, un número o un arreglo), por BISECCIÓN sobre la curva, la ÚNICA definición; impar como `dosis`. La curva es monótona
        (a ≥ 0, b ≥ 0, n ≥ 1 y a + b > 0), así que la inversa existe y es una sola; la bisección para cuando su intervalo mide `TOLERANCIA_DE_LA_INVERSA` o menos."""
        a, b, n = self._parametros_de(capa)
        objetivo = np.abs(np.asarray(d, float))
        alto = np.ones_like(objetivo)
        for _ in range(ITERACIONES_MAXIMAS_DE_LA_INVERSA):
            corto = _devic(alto, a, b, n) < objetivo
            if not corto.any():
                break
            alto = np.where(corto, alto * 2.0, alto)
        bajo = np.zeros_like(objetivo)
        for _ in range(ITERACIONES_MAXIMAS_DE_LA_INVERSA):
            if np.all(alto - bajo <= TOLERANCIA_DE_LA_INVERSA):
                break
            medio = (bajo + alto) / 2.0
            debajo = _devic(medio, a, b, n) < objetivo
            bajo, alto = np.where(debajo, medio, bajo), np.where(debajo, alto, medio)
        x = np.sign(np.asarray(d, float)) * (bajo + alto) / 2.0
        return float(x) if np.ndim(x) == 0 else x

    def rango(self, capa):
        """La dosis más alta del rango útil de una capa (cGy, contada desde el cero; el rango va de 0 a ella), o None si la capa no tiene rango útil (DC5)."""
        return self.capas[capa]["rango_cgy"]

    def estado(self, capa):
        """El estado de la curva de una capa: «válida», «guía: …», «incompleta: …» o «no válida: …» (DC5, DC3)."""
        return self.capas[capa]["estado"]

    def incertidumbre(self, capa, x, u_x):
        """La U (k = 2, en cGy) de la dosis de una densidad óptica `x` con su u `u_x` (DC10): 2 · √((D · RMS)² + (D · u_dosis)² + (u_x · D′(x))²), con el RMS de los residuos del rango útil de la capa,
        la incertidumbre declarada de la dosis medida (si no se declaró, no entra: P13) y la de la película. En x = 0 queda la de la película sola."""
        a, b, n = self._parametros_de(capa)
        d = abs(float(_devic(x, a, b, n)))
        rms = (self.capas[capa]["rms_pct"] or 0.0) / 100.0
        declarada = (self.u_dosis_medida_pct or 0.0) / 100.0
        pelicula = float(u_x) * float(_derivada_de_devic(x, a, b, n))
        return 2.0 * math.sqrt((d * rms) ** 2 + (d * declarada) ** 2 + pelicula ** 2)

    def como_dict(self):
        """La curva como JSON (listas, números, textos y None): la copia que guarda una calibración y cada análisis (DA-81). `curva_desde_dict` es su inversa."""
        return {"version": self.version, "modelo": self.modelo, "cero": _json_normal(self.cero), "capas": _json_normal(self.capas),
                "piezas": [{"orden": p.orden, "dosis_nominal_cgy": p.dosis_nominal_cgy, "dosis_medida_cgy": p.dosis_medida_cgy, "estado": p.estado, "capas": _json_normal(p.capas),
                            "posicion_mm": _json_normal(p.posicion_mm), "fondo_blanco": p.fondo_blanco, "archivo": p.archivo, "sha256": p.sha256, "cadena": _json_normal(p.cadena)}
                           for p in self.piezas],
                "avisos": list(self.avisos), "parametros": _json_normal(self.parametros), "u_dosis_medida_pct": self.u_dosis_medida_pct, "cadena": _json_normal(self.cadena)}


def _capas_sin_valor_positivo(valores):
    """CD3-PROD-D1: las capas (en el orden de `CAPAS_DEL_PISO`, como texto «R, G, B, gris») en que una medida no tiene un valor positivo, o None si lo tiene en las cuatro. Una medida sirve de cero solo
    si lo tiene en las cuatro: netOD = log10(I0 / I) pide I0 > 0, y un escaneo negro mide «ok» con valor 0 en CD.2."""
    capas = [c for c in CAPAS_DEL_PISO if not (_es_numero(valores[c]) and valores[c] > 0)]
    return ", ".join(capas) if capas else None


def _cero(piezas_ok, virgen, cadena):
    """El cero de la calibración (DC3, CD-Z1): (fuente, detalle, dosis del cero, {capa: (I0, u_I0)}, la pieza que hace de cero o None, avisos), o None si no hay con qué. Una sola regla y en este
    orden: las piezas de 0 cGy (I0 = la media de sus valores; u = la raíz de la media de sus u al cuadrado), la película virgen montada si es válida, de la misma cadena de captura y con la región central
    de su tabla de uniformidad (su u, DC2: sin ella no sirve y se avisa, CD3-REV1-01), o la pieza irradiada de menor dosis medida. CD3-PROD-D1: una medida sirve de cero solo si su valor es positivo en las
    cuatro capas (`_capas_sin_valor_positivo`): una pieza de 0 cGy que no lo cumple no entra en la media y deja `AVISO_NO_SIRVE_DE_CERO`, y la pieza de menor dosis se escoge entre las que lo cumplen; la virgen no lleva
    esta condición (A.3 ya rechaza una virgen negra, CD3-PROD-D4)."""
    avisos = []
    ceros = []
    for p in piezas_ok:
        if p.dosis_nominal_cgy != 0:
            continue
        sin_valor = _capas_sin_valor_positivo({c: p.capas[c]["valor"] for c in CAPAS_DEL_PISO})
        if sin_valor is None:
            ceros.append(p)
        else:
            avisos.append(AVISO_NO_SIRVE_DE_CERO.format(orden=p.orden, nominal=p.dosis_nominal_cgy, motivo=MOTIVO_SIN_VALOR_POSITIVO.format(capas=sin_valor)))
    if ceros:
        capas = {c: (float(np.mean([p.capas[c]["valor"] for p in ceros])), float(np.sqrt(np.mean([p.capas[c]["u"] ** 2 for p in ceros])))) for c in CAPAS_DEL_PISO}
        detalle = "las piezas de 0 cGy (" + ", ".join(f"pieza {p.orden}" for p in ceros) + ")"
        return "piezas_de_0_cgy", detalle, 0.0, capas, None, avisos
    if virgen is not None:
        motivo = None
        if virgen.estado != "ok":
            motivo = virgen.estado
        elif cadena is None or cadena_de_captura(virgen.procedencia) != cadena:
            motivo = (f"se escaneó con otra cadena de captura ({_texto_de_la_cadena(cadena_de_captura(virgen.procedencia))}"
                      + ("" if cadena is None else f" contra {_texto_de_la_cadena(cadena)}") + ")")
        if motivo is None:
            tabla = virgen.uniformidad
            incertidumbres = {c: _incertidumbre_del_valor(tabla, tabla["capas"][c]["ruido"] if tabla else None, c) for c in CAPAS_DEL_PISO}
            if any(u is None for u in incertidumbres.values()):
                motivo = MOTIVO_VIRGEN_SIN_CENTRO
        if motivo is None:
            capas = {c: (float(virgen.valor(c)), incertidumbres[c]) for c in CAPAS_DEL_PISO}
            nombre = virgen.procedencia.get("archivo") or "sin nombre"
            return "pelicula_virgen", f"la película virgen montada «{nombre}» (huella {virgen.procedencia['sha256'][:8]})", 0.0, capas, None, avisos
        avisos.append(AVISO_VIRGEN_NO_SIRVE.format(motivo=motivo))
    irradiadas = [p for p in piezas_ok if p.dosis_nominal_cgy > 0 and p.dosis_medida_cgy is not None and p.dosis_medida_cgy > 0
                  and _capas_sin_valor_positivo({c: p.capas[c]["valor"] for c in CAPAS_DEL_PISO}) is None]
    if irradiadas:
        menor = min(irradiadas, key=lambda p: (p.dosis_medida_cgy, p.orden))
        capas = {c: (menor.capas[c]["valor"], menor.capas[c]["u"]) for c in CAPAS_DEL_PISO}
        medida = "" if menor.dosis_medida_cgy == menor.dosis_nominal_cgy else f"medida en {menor.dosis_medida_cgy:g} cGy, "      # CD3-REV1-04: la dosis con que se cuentan las demás, si no es la nominal
        return ("pieza_de_menor_dosis", f"la pieza {menor.orden} ({menor.dosis_nominal_cgy:g} cGy, {medida}la de menor dosis): solo guía", float(menor.dosis_medida_cgy), capas, menor, avisos)
    return None, None, None, None, None, avisos


def _con_netod(pieza, cero_capas, dosis_cero):
    """La pieza con su netOD contra el cero (DC3) y su dosis contada desde el cero, por capa. Una capa con valor 0 (o negativo) no tiene logaritmo: queda en None. Lo DERIVADO (netOD y su u, dosis, residuo y
    si está en el rango) se rehace desde lo MEDIDO (valor, u y recorte) y no se hereda de la pieza: una pieza que viene de una copia guardada (`curva_desde_dict`, CD.4) o de una curva anterior puede traerlo
    desfasado o inconsistente con su valor (CD3-REV1-03)."""
    capas = {}
    for c in CAPAS_DEL_PISO:
        fila = {**dict.fromkeys(_CLAVES_DE_LA_CAPA_DE_UNA_PIEZA), "valor": pieza.capas[c]["valor"], "u": pieza.capas[c]["u"], "recortada": pieza.capas[c]["recortada"], "en_el_rango": False}
        i0, u0 = cero_capas[c]
        if fila["valor"] is not None and fila["valor"] > 0 and i0 > 0:
            fila["netod"] = math.log10(i0 / fila["valor"])
            fila["u_netod"] = math.sqrt((u0 / i0) ** 2 + (fila["u"] / fila["valor"]) ** 2) / math.log(10.0)
        if pieza.dosis_medida_cgy is not None:
            fila["dosis_cgy"] = pieza.dosis_medida_cgy - dosis_cero if pieza.dosis_nominal_cgy > 0 else 0.0
        capas[c] = fila
    return replace(pieza, capas=capas)


def _niveles(piezas, capa):
    """Las dosis irradiadas de una capa, de menor a mayor: [(dosis nominal, [piezas])], las réplicas (misma dosis nominal) juntas."""
    por_dosis = {}
    for p in piezas:
        por_dosis.setdefault(p.dosis_nominal_cgy, []).append(p)
    return sorted(por_dosis.items(), key=lambda item: (float(np.mean([p.capas[capa]["dosis_cgy"] for p in item[1]])), item[0]))


def _media_del_nivel(nivel, capa):
    """(netOD, u relativa de la medida sin el cero, u de la netOD con el cero) de una dosis: la media de sus piezas; las u, la raíz de la media de sus cuadrados."""
    netods = [p.capas[capa]["netod"] for p in nivel]
    relativas = [p.capas[capa]["u"] / p.capas[capa]["valor"] for p in nivel]
    return float(np.mean(netods)), float(np.sqrt(np.mean(np.square(relativas)))), float(np.sqrt(np.mean(np.square([p.capas[capa]["u_netod"] for p in nivel]))))


def _rango_candidato(niveles, capa, u_relativa_del_cero, v):
    """Las dosis que cumplen (a) y (b) de DC5, de la menor hacia arriba, y por qué se detiene: ([niveles], límite o None, motivo de no válida o None). (a) ninguna pieza de la dosis está recortada en la
    capa; (b) su netOD supera a la de la dosis anterior (la primera, al cero) en más de `separacion_minima_u` u de esa diferencia (la u de las dos medidas; el cero no entra salvo en la primera, que se
    mide contra él). Si la netOD BAJA más de esas u, los datos no son monótonos."""
    aceptados, anterior_x, anterior_u, anterior_nominal = [], 0.0, u_relativa_del_cero, 0.0
    for nominal, nivel in niveles:
        if any(p.capas[capa]["recortada"] is not None for p in nivel) or any(p.capas[capa]["netod"] is None for p in nivel):
            return aceptados, LIMITE_RECORTE.format(nominal=nominal), None
        x, u_rel, _ = _media_del_nivel(nivel, capa)
        subida = x - anterior_x
        umbral = v["separacion_minima_u"] * math.sqrt(anterior_u ** 2 + u_rel ** 2) / math.log(10.0)
        if subida <= umbral:
            motivo = MOTIVO_NO_MONOTONOS.format(nominal=nominal, anterior=anterior_nominal) if subida < -umbral else None
            return aceptados, LIMITE_SEPARACION.format(nominal=nominal, anterior=anterior_nominal, subida=subida, minimo=v["separacion_minima_u"], umbral=umbral), motivo
        aceptados.append((nominal, nivel))
        anterior_x, anterior_u, anterior_nominal = x, u_rel, nominal
    return aceptados, None, None


def _ajustar_la_capa(niveles, capa, u_relativa_del_cero, v):
    """Una capa: el rango candidato por (a) y (b), el ajuste sobre sus piezas y el recorte por (c) (la resolución en dosis), repetidos hasta que el rango no cambia (cada vuelta lo acorta o lo deja)."""
    usados, limite, no_monotonos = _rango_candidato(niveles, capa, u_relativa_del_cero, v)
    ajuste, rango_niveles = None, []
    while True:
        piezas = [p for _, nivel in usados for p in nivel]
        if len(piezas) < PARAMETROS_MINIMOS_DEL_AJUSTE:
            break
        x = np.array([p.capas[capa]["netod"] for p in piezas])
        d = np.array([p.capas[capa]["dosis_cgy"] for p in piezas])
        ajuste = _ajustar_devic(x, d)
        if ajuste is None:
            rango_niveles = []
            break
        a, b, n, _ = ajuste
        ultimo = None
        for k, (nominal, nivel) in enumerate(usados):
            xk, _, uk = _media_del_nivel(nivel, capa)
            resolucion = 100.0 * uk * float(_derivada_de_devic(xk, a, b, n)) / float(_devic(xk, a, b, n))
            if resolucion <= v["resolucion_maxima_pct"]:
                ultimo = (k, nominal, resolucion)
        if ultimo is None:
            limite = LIMITE_SIN_RESOLUCION.format(maximo=v["resolucion_maxima_pct"])
            rango_niveles = []                 # el rango y el ajuste son siempre de la MISMA vuelta
            break
        k = ultimo[0]
        rango_niveles = usados[:k + 1]
        if k == len(usados) - 1:
            break
        nominal = usados[k + 1][0]
        xk, _, uk = _media_del_nivel(usados[k + 1][1], capa)
        limite = LIMITE_RESOLUCION.format(maximo=v["resolucion_maxima_pct"], nominal=nominal, resolucion=100.0 * uk * float(_derivada_de_devic(xk, a, b, n)) / float(_devic(xk, a, b, n)))
        usados = rango_niveles
    return ajuste, rango_niveles, limite, no_monotonos


def ajustar(piezas, P=None, virgen=None, u_dosis_medida_pct=None):
    """La curva de dosis de una calibración (CD.3) -> `CurvaDeDosis`. `piezas`: las `PiezaDeCalibracion` (`pieza_de_calibracion`), en cualquier orden; `P`: los parámetros que se quieran cambiar de
    `PARAMETROS_DE_LA_CURVA` (los que falten, de fábrica); `virgen`: la `ReferenciaVirgen` montada (OD.1), que hace de cero solo si no hay piezas de 0 cGy, es válida, se escaneó con la misma cadena
    que las piezas (DC3) y trae la región central de su tabla de uniformidad (si no, se avisa y no sirve, CD3-REV1-01); `u_dosis_medida_pct`: la incertidumbre declarada de la dosis medida con la cámara (k = 1, %), o None (P13).

    Por capa (R, G, B y gris): la netOD de cada pieza contra el cero, el ajuste de Devic (DC4) con sus parámetros, el residuo de cada pieza en %, el rango útil (DC5: de 0 a la dosis más alta que
    cumple (a) sin recorte, (b) se distingue de la anterior y (c) su resolución en dosis no pasa de `resolucion_maxima_pct`; el ajuste se hace con las piezas del rango) y el estado, en este orden de
    precedencia: «incompleta: …» (sin cero, una dosis medida que falta o no es positiva, o menos de `piezas_minimas` dosis en el rango útil), «no válida: …» (piezas de otra cadena de captura, datos
    no monótonos, un ajuste que no converge o un residuo fuera de la tolerancia), «guía: el cero es la pieza de N cGy» (N, su dosis nominal; una curva que sería válida pero cuyo cero es la pieza de menor dosis: nunca pasa
    a dosis) o «válida». Una pieza «no medible» no entra en la curva y se avisa. Además avisa, sin cambiar ningún estado, de una pieza cuyo fondo del escáner se aparta del del cero (el escáner pudo
    ajustar la exposición) o que está a más de `distancia_en_el_vidrio_mm` del cero en el vidrio (H2). CD3-PROD-D1: una medida sirve de cero solo con valor positivo en las cuatro capas (si no, se
    avisa y sigue la regla del cero). CD3-PROD-D2 y D3: en el modo guía, las réplicas de la pieza que hace de cero (la misma dosis nominal) y lo que no supera su dosis medida no entran al ajuste, no traen
    residuo y se avisan. NUNCA lanza por el contenido; `ValueError` si `piezas` no son `PiezaDeCalibracion`."""
    if any(not isinstance(p, PiezaDeCalibracion) for p in piezas):
        raise ValueError("Las piezas de una curva son `PiezaDeCalibracion` (`pieza_de_calibracion`).")
    if virgen is not None and not isinstance(virgen, ReferenciaVirgen):
        raise ValueError("La película virgen de una curva es una `ReferenciaVirgen` (la referencia de la película virgen montada, OD.1).")          # sin nombrar las funciones del piso: la curva no las consume (el censo de A.3 busca sus nombres por texto)
    v = {**VALORES_DE_LA_CURVA, **(P or {})}
    piezas = sorted(piezas, key=lambda p: p.orden)
    avisos = [AVISO_FUERA_DE_LA_CURVA.format(orden=p.orden, nominal=p.dosis_nominal_cgy, estado=p.estado) for p in piezas if p.estado != "ok"]
    ok = [p for p in piezas if p.estado == "ok"]
    incompleta = None
    for p in ok:
        if p.dosis_nominal_cgy > 0 and p.dosis_medida_cgy is None:
            incompleta = incompleta or MOTIVO_FALTA_DOSIS.format(orden=p.orden, nominal=p.dosis_nominal_cgy)
        elif p.dosis_nominal_cgy > 0 and p.dosis_medida_cgy <= 0:
            incompleta = incompleta or MOTIVO_DOSIS_NO_POSITIVA.format(orden=p.orden, nominal=p.dosis_nominal_cgy)
    cadenas = []
    for p in ok:
        if p.cadena not in cadenas:
            cadenas.append(p.cadena)
    cadena = cadenas[0] if len(cadenas) == 1 else None
    otra_cadena = MOTIVO_OTRA_CADENA.format(cadenas="; ".join(_texto_de_la_cadena(c) for c in cadenas if c is not None)) if len(cadenas) > 1 else None
    fuente, detalle, dosis_cero, cero_capas, pieza_cero, avisos_del_cero = _cero(ok, virgen, cadena)
    avisos += avisos_del_cero
    if fuente is None:
        capas = {c: {"estado": PREFIJO_INCOMPLETA + MOTIVO_SIN_CERO, "parametros": None, "rango_cgy": None, "netod_maxima": None, "rms_pct": None, "costo": None, "dosis_en_el_rango": 0,
                     "limite": None} for c in CAPAS_DEL_PISO}
        return CurvaDeDosis(VERSION_CURVA, MODELO_DEVIC, None, capas, tuple(piezas), tuple(avisos), dict(v), u_dosis_medida_pct, cadena)
    cero = {"fuente": fuente, "detalle": detalle, "dosis_cgy": dosis_cero, "capas": {c: {"i0": i0, "u_i0": u0} for c, (i0, u0) in cero_capas.items()}}
    medidas = [_con_netod(p, cero_capas, dosis_cero) if p.estado == "ok" else p for p in piezas]
    en_juego = [p for p in medidas if p.estado == "ok" and p.dosis_nominal_cgy > 0 and p.dosis_medida_cgy is not None and p.dosis_medida_cgy > dosis_cero
                and (pieza_cero is None or p.dosis_nominal_cgy != pieza_cero.dosis_nominal_cgy)]
    if pieza_cero is not None:          # CD3-PROD-D2: en el modo guía, lo que no entra al ajuste por estar junto al cero se dice
        for p in medidas:
            if (p.estado != "ok" or p.orden == pieza_cero.orden or p.dosis_nominal_cgy <= 0 or p.dosis_medida_cgy is None or p.dosis_medida_cgy <= 0
                    or any(p is q for q in en_juego)):
                continue
            motivo = (MOTIVO_REPLICA_DEL_CERO.format(orden=pieza_cero.orden) if p.dosis_nominal_cgy == pieza_cero.dosis_nominal_cgy
                      else MOTIVO_NO_SUPERA_AL_CERO.format(medida=p.dosis_medida_cgy, cero=dosis_cero))
            avisos.append(AVISO_FUERA_DE_LA_CURVA.format(orden=p.orden, nominal=p.dosis_nominal_cgy, estado=motivo))
    avisos += _avisos_del_escaneo(medidas, pieza_cero, fuente, virgen, v)
    capas, rangos = {}, {}
    for c in CAPAS_DEL_PISO:
        u_relativa_del_cero = cero_capas[c][1] / cero_capas[c][0]
        niveles = _niveles([p for p in en_juego if p.capas[c]["netod"] is not None or p.capas[c]["recortada"] is not None], c)
        ajuste, rango_niveles, limite, no_monotonos = _ajustar_la_capa(niveles, c, u_relativa_del_cero, v)
        fila = {"estado": None, "parametros": None, "rango_cgy": None, "netod_maxima": None, "rms_pct": None, "costo": None, "dosis_en_el_rango": len(rango_niveles), "limite": limite}
        residuos = []
        if ajuste is not None:
            a, b, n, costo = ajuste
            fila.update(parametros={"a": a, "b": b, "n": n}, costo=costo)
            if rango_niveles:
                fila["rango_cgy"] = float(np.mean([p.capas[c]["dosis_cgy"] for p in rango_niveles[-1][1]]))
                fila["netod_maxima"] = _media_del_nivel(rango_niveles[-1][1], c)[0]
                residuos = [(p, 100.0 * (float(_devic(p.capas[c]["netod"], a, b, n)) - p.capas[c]["dosis_cgy"]) / p.capas[c]["dosis_cgy"]) for _, nivel in rango_niveles for p in nivel]
                fila["rms_pct"] = float(np.sqrt(np.mean(np.square([r for _, r in residuos]))))
        rangos[c] = {p.orden for _, nivel in rango_niveles for p in nivel}
        fila["estado"] = _estado_de_la_capa(c, incompleta, otra_cadena, no_monotonos, ajuste, rango_niveles, residuos, fuente, pieza_cero, v)
        capas[c] = fila
    final = []
    for p in medidas:
        if p.estado != "ok":
            final.append(p)
            continue
        filas = {}
        for c in CAPAS_DEL_PISO:
            fila = dict(p.capas[c])
            parametros = capas[c]["parametros"]
            if parametros is not None and fila["netod"] is not None and fila["dosis_cgy"] and any(p is q for q in en_juego) and fila["dosis_cgy"] > 0:
                fila["residuo_pct"] = 100.0 * (float(_devic(fila["netod"], parametros["a"], parametros["b"], parametros["n"])) - fila["dosis_cgy"]) / fila["dosis_cgy"]
            fila["en_el_rango"] = p.orden in rangos[c]
            filas[c] = fila
        final.append(replace(p, capas=filas))
    return CurvaDeDosis(VERSION_CURVA, MODELO_DEVIC, cero, capas, tuple(final), tuple(avisos), dict(v), u_dosis_medida_pct, cadena)


def _estado_de_la_capa(capa, incompleta, otra_cadena, no_monotonos, ajuste, rango_niveles, residuos, fuente, pieza_cero, v):
    """El estado de una capa (DC5), con su precedencia: incompleta, no válida, guía, válida."""
    if incompleta is not None:
        return PREFIJO_INCOMPLETA + incompleta
    if otra_cadena is not None:
        return PREFIJO_NO_VALIDA + otra_cadena
    if no_monotonos is not None:
        return PREFIJO_NO_VALIDA + no_monotonos
    if len(rango_niveles) < v["piezas_minimas"]:
        return PREFIJO_INCOMPLETA + MOTIVO_POCAS_DOSIS.format(n=len(rango_niveles), minimo=v["piezas_minimas"])
    if ajuste is None:
        return PREFIJO_NO_VALIDA + MOTIVO_NO_CONVERGE
    for pieza, residuo in residuos:
        tolerancia = v["residuo_maximo_bajas_pct"] if pieza.capas[capa]["dosis_cgy"] < v["dosis_baja_cgy"] else v["residuo_maximo_pct"]
        if abs(residuo) > tolerancia:
            return PREFIJO_NO_VALIDA + MOTIVO_RESIDUO.format(nominal=pieza.dosis_nominal_cgy, residuo=residuo, tolerancia=tolerancia)
    if fuente == "pieza_de_menor_dosis":
        return PREFIJO_GUIA + MOTIVO_GUIA.format(nominal=pieza_cero.dosis_nominal_cgy)
    return ESTADO_VALIDA


def _avisos_del_escaneo(medidas, pieza_cero, fuente, virgen, v):
    """Los dos avisos que no cambian el estado (CD.3), cada uno con su pieza: el fondo del escáner que se aparta del del cero (el escáner pudo ajustar la exposición) y el lugar del vidrio a más de
    `distancia_en_el_vidrio_mm` del cero. La referencia es el cero de la curva: la media de las piezas de 0 cGy, la película virgen montada o la pieza de menor dosis."""
    if fuente == "piezas_de_0_cgy":
        referencias = [p for p in medidas if p.estado == "ok" and p.dosis_nominal_cgy == 0 and _capas_sin_valor_positivo({c: p.capas[c]["valor"] for c in CAPAS_DEL_PISO}) is None]
        fondos = [p.fondo_blanco for p in referencias if p.fondo_blanco is not None]
        posiciones = [p.posicion_mm for p in referencias if p.posicion_mm is not None]
    elif fuente == "pelicula_virgen":
        fondo = fondo_blanco_de(virgen.pruebas)
        fondos = [] if fondo is None else [fondo]
        caja = (virgen.region or {}).get("pelicula_mm")
        posiciones = [] if not caja else [{"x": caja["x"] + caja["ancho"] / 2.0, "y": caja["y"] + caja["alto"] / 2.0}]
    else:
        fondos = [] if pieza_cero.fondo_blanco is None else [pieza_cero.fondo_blanco]
        posiciones = [] if pieza_cero.posicion_mm is None else [pieza_cero.posicion_mm]
    fondo_del_cero = float(np.mean(fondos)) if fondos else None
    centro_del_cero = (float(np.mean([q["x"] for q in posiciones])), float(np.mean([q["y"] for q in posiciones]))) if posiciones else None
    avisos = []
    for p in medidas:
        if p.estado != "ok" or p.dosis_nominal_cgy == 0 or (pieza_cero is not None and p.orden == pieza_cero.orden):
            continue
        if fondo_del_cero is not None and p.fondo_blanco is not None and abs(p.fondo_blanco - fondo_del_cero) > v["diferencia_de_fondo_blanco"]:
            avisos.append(AVISO_EXPOSICION.format(orden=p.orden, nominal=p.dosis_nominal_cgy, fraccion=100.0 * p.fondo_blanco, cero=100.0 * fondo_del_cero))
        if centro_del_cero is not None and p.posicion_mm is not None:
            distancia = math.hypot(p.posicion_mm["x"] - centro_del_cero[0], p.posicion_mm["y"] - centro_del_cero[1])
            if distancia > v["distancia_en_el_vidrio_mm"]:
                avisos.append(AVISO_OTRO_LUGAR.format(orden=p.orden, nominal=p.dosis_nominal_cgy, distancia=distancia, maximo=v["distancia_en_el_vidrio_mm"]))
    return avisos


# ============================================================================================================================================ la copia guardada

_CLAVES_DE_LA_CURVA = ("version", "modelo", "cero", "capas", "piezas", "avisos", "parametros", "u_dosis_medida_pct", "cadena")
_CLAVES_DE_LA_CAPA = ("estado", "parametros", "rango_cgy", "netod_maxima", "rms_pct", "costo", "dosis_en_el_rango", "limite")
_CLAVES_DEL_CERO = ("fuente", "detalle", "dosis_cgy", "capas")
_CLAVES_DE_UNA_PIEZA = ("orden", "dosis_nominal_cgy", "dosis_medida_cgy", "estado", "capas", "posicion_mm", "fondo_blanco", "archivo", "sha256", "cadena")


def _exige_la_curva(condicion, que):
    """`ValueError` con el motivo si no se cumple `condicion`: una curva guardada que no es como `CurvaDeDosis.como_dict()` la escribe está dañada."""
    if not condicion:
        raise ValueError(f"La curva de dosis está dañada: {que}.")


def _numero_o_nada(valor):
    return valor is None or _es_numero(valor)


def _exige_las_claves(d, claves, que):
    _exige_la_curva(isinstance(d, dict), f"{que} no es un diccionario")
    _exige_la_curva(set(d) == set(claves), f"{que} no trae exactamente sus claves: {', '.join(claves)}")


_CLAVES_DE_LA_CADENA = ("equipo", "bits", "dpi", "formato")


def _exige_la_cadena(cadena, que):
    """La forma de una cadena de captura guardada, la de la curva o la de una pieza, tal como `cadena_de_captura` la escribe (CD3-REV1-03): exactamente `_CLAVES_DE_LA_CADENA`; el escáner y el formato un texto
    o nada; los bits un entero positivo o nada; la resolución un número de 0 o más o nada. Con esa forma no queda nada libre que pueda anidarse (el tope de profundidad se revisa antes, donde `cadena` aún
    puede ser cualquier cosa) y `_texto_de_la_cadena` puede escribirla: una copia que `ajustar(copia.piezas)` no pueda comparar se rechaza AQUÍ, no lejos de donde se leyó."""
    _exige_las_claves(cadena, _CLAVES_DE_LA_CADENA, que)
    equipo, bits, dpi, formato = (cadena[k] for k in _CLAVES_DE_LA_CADENA)
    _exige_la_curva((equipo is None or isinstance(equipo, str)) and (formato is None or isinstance(formato, str)) and (bits is None or (_es_entero(bits) and bits > 0))
                    and (dpi is None or (_es_numero(dpi) and dpi >= 0)),
                    f"{que} no trae sus valores del tipo que se escribe (el escáner y el formato, un texto o nada; los bits, un entero positivo o nada; la resolución, un número de 0 o más o nada)")


def curva_desde_dict(d):
    """La inversa de `CurvaDeDosis.como_dict()`, con validación ESTRICTA, como `pelicula.referencia_virgen_desde_dict`: `ValueError` con el motivo si no es un diccionario, si la versión o el modelo no
    son los de esta aplicación, si falta o sobra una clave (de la curva, del cero, de una capa o de una pieza), si un valor no es del TIPO que `como_dict()` escribe (un número de texto, un booleano por
    un número, NaN o infinito), si los parámetros de una capa no son los de una curva monótona por el origen (a ≥ 0, b ≥ 0, 1 ≤ n ≤ 4, a + b > 0), si una capa «válida» no trae parámetros ni rango, o si
    lo que no tiene forma fija (los parámetros y la cadena de la curva y de cada pieza) anida más de `PROFUNDIDAD_MAXIMA_DE_LO_LIBRE` niveles. La cadena de captura, la de la curva y la de cada pieza, es exactamente la que escribe
    `cadena_de_captura` (cuatro claves, con sus tipos: `_exige_la_cadena`), y una pieza «ok» trae su valor y su u como números en cada capa: lo que `ajustar(copia.piezas)` (CD.4) necesita para rehacer la curva
    (CD3-REV1-03). Una copia dañada se rechaza AQUÍ, con su motivo. Las piezas vuelven sin su `medida`."""
    if not isinstance(d, dict):
        raise ValueError("La curva de dosis debe ser un diccionario.")
    if d.get("version") != VERSION_CURVA:
        raise ValueError(f"La curva de dosis es de la versión {d.get('version')!r} y esta aplicación lee la {VERSION_CURVA!r}.")
    if d.get("modelo") != MODELO_DEVIC:
        raise ValueError(f"La curva de dosis es del modelo {d.get('modelo')!r} y esta aplicación usa el {MODELO_DEVIC!r}.")
    _exige_las_claves(d, _CLAVES_DE_LA_CURVA, "la curva")
    _exige_la_curva(isinstance(d["avisos"], list) and all(isinstance(a, str) for a in d["avisos"]), "los avisos no son una lista de textos")
    _exige_la_curva(isinstance(d["parametros"], dict), "los parámetros no son un diccionario")
    for nombre, contenido in (("los parámetros", d["parametros"]), ("la cadena de captura", d["cadena"])):
        _exige_la_curva(not _anida_mas_de(contenido, PROFUNDIDAD_MAXIMA_DE_LO_LIBRE), f"{nombre} anidan demasiados niveles (más de {PROFUNDIDAD_MAXIMA_DE_LO_LIBRE})")
    if d["cadena"] is not None:
        _exige_la_cadena(d["cadena"], "la cadena de captura")
    _exige_la_curva(d["u_dosis_medida_pct"] is None or (_es_numero(d["u_dosis_medida_pct"]) and d["u_dosis_medida_pct"] >= 0), "la incertidumbre de la dosis medida no es un número de 0 o más")
    cero = d["cero"]
    if cero is not None:
        _exige_las_claves(cero, _CLAVES_DEL_CERO, "el cero")
        _exige_la_curva(cero["fuente"] in FUENTES_DEL_CERO, f"la fuente del cero no es una de {', '.join(FUENTES_DEL_CERO)}")
        _exige_la_curva(isinstance(cero["detalle"], str), "el detalle del cero no es un texto")
        _exige_la_curva(_es_numero(cero["dosis_cgy"]) and cero["dosis_cgy"] >= 0, "la dosis del cero no es un número de 0 o más")
        _exige_las_claves(cero["capas"], CAPAS_DEL_PISO, "las capas del cero")
        for c, fila in cero["capas"].items():
            _exige_las_claves(fila, ("i0", "u_i0"), f"el cero de la capa {c}")
            _exige_la_curva(_es_numero(fila["i0"]) and fila["i0"] > 0 and _es_numero(fila["u_i0"]) and fila["u_i0"] >= 0, f"el I0 o su u de la capa {c} no son números válidos")
    _exige_las_claves(d["capas"], CAPAS_DEL_PISO, "las capas")
    for c, fila in d["capas"].items():
        _exige_las_claves(fila, _CLAVES_DE_LA_CAPA, f"la capa {c}")
        _exige_la_curva(isinstance(fila["estado"], str) and fila["estado"] != "", f"el estado de la capa {c} no es un texto")
        _exige_la_curva(fila["limite"] is None or isinstance(fila["limite"], str), f"el límite de la capa {c} no es un texto")
        _exige_la_curva(_es_entero(fila["dosis_en_el_rango"]) and fila["dosis_en_el_rango"] >= 0, f"las dosis en el rango de la capa {c} no son un entero de 0 o más")
        for clave in ("rango_cgy", "netod_maxima", "rms_pct", "costo"):
            _exige_la_curva(_numero_o_nada(fila[clave]) and (fila[clave] is None or fila[clave] >= 0), f"{clave} de la capa {c} no es un número de 0 o más")
        p = fila["parametros"]
        if p is not None:
            _exige_las_claves(p, ("a", "b", "n"), f"los parámetros de la capa {c}")
            _exige_la_curva(all(_es_numero(p[k]) for k in ("a", "b", "n")), f"los parámetros de la capa {c} no son números")
            _exige_la_curva(p["a"] >= 0 and p["b"] >= 0 and p["a"] + p["b"] > 0 and COTAS_DE_N[0] <= p["n"] <= COTAS_DE_N[1],
                            f"los parámetros de la capa {c} no son los de una curva monótona por el origen (a ≥ 0, b ≥ 0, a + b > 0 y {COTAS_DE_N[0]:g} ≤ n ≤ {COTAS_DE_N[1]:g})")
        _exige_la_curva(fila["rango_cgy"] is None or p is not None, f"la capa {c} trae rango útil sin parámetros")
        _exige_la_curva(fila["estado"] != ESTADO_VALIDA or (p is not None and fila["rango_cgy"] is not None), f"la capa {c} es «válida» sin parámetros o sin rango útil")
    _exige_la_curva(isinstance(d["piezas"], list), "las piezas no son una lista")
    piezas = []
    for i, q in enumerate(d["piezas"]):
        que = f"la pieza {i + 1} de la lista"
        _exige_las_claves(q, _CLAVES_DE_UNA_PIEZA, que)
        _exige_la_curva(_es_entero(q["orden"]), f"el orden de {que} no es un entero")
        _exige_la_curva(_es_numero(q["dosis_nominal_cgy"]) and q["dosis_nominal_cgy"] >= 0, f"la dosis nominal de {que} no es un número de 0 o más")
        _exige_la_curva(_numero_o_nada(q["dosis_medida_cgy"]), f"la dosis medida de {que} no es un número")
        _exige_la_curva(isinstance(q["estado"], str) and isinstance(q["archivo"], str) and (q["sha256"] is None or isinstance(q["sha256"], str)), f"el estado, el archivo o la huella de {que} no son textos")
        _exige_la_curva(_numero_o_nada(q["fondo_blanco"]) and (q["fondo_blanco"] is None or 0 <= q["fondo_blanco"] <= 1), f"el fondo blanco de {que} no es una fracción")
        if q["posicion_mm"] is not None:
            _exige_las_claves(q["posicion_mm"], ("x", "y"), f"la posición de {que}")
            _exige_la_curva(all(_es_numero(q["posicion_mm"][k]) for k in ("x", "y")), f"la posición de {que} no son números")
        if q["cadena"] is not None:
            _exige_la_curva(not _anida_mas_de(q["cadena"], PROFUNDIDAD_MAXIMA_DE_LO_LIBRE), f"la cadena de captura de {que} anida demasiados niveles (más de {PROFUNDIDAD_MAXIMA_DE_LO_LIBRE})")
            _exige_la_cadena(q["cadena"], f"la cadena de captura de {que}")
        _exige_las_claves(q["capas"], CAPAS_DEL_PISO, f"las capas de {que}")
        for c, fila in q["capas"].items():
            _exige_las_claves(fila, _CLAVES_DE_LA_CAPA_DE_UNA_PIEZA, f"la capa {c} de {que}")
            _exige_la_curva(all(_numero_o_nada(fila[k]) for k in _CLAVES_DE_LA_CAPA_DE_UNA_PIEZA if k != "en_el_rango") and isinstance(fila["en_el_rango"], bool),
                            f"un valor de la capa {c} de {que} no es un número (o «en_el_rango» no es verdadero o falso)")
            _exige_la_curva(q["estado"] != "ok" or (_es_numero(fila["valor"]) and fila["valor"] >= 0 and _es_numero(fila["u"]) and fila["u"] >= 0),
                            f"la capa {c} de {que} {OK_SIN_VALOR}")
        piezas.append(PiezaDeCalibracion(q["orden"], float(q["dosis_nominal_cgy"]), q["dosis_medida_cgy"], q["estado"], _json_normal(q["capas"]), _json_normal(q["posicion_mm"]),
                                         q["fondo_blanco"], q["archivo"], q["sha256"], _json_normal(q["cadena"])))
    return CurvaDeDosis(d["version"], d["modelo"], _json_normal(cero), _json_normal(d["capas"]), tuple(piezas), tuple(d["avisos"]), _json_normal(d["parametros"]), d["u_dosis_medida_pct"],
                        _json_normal(d["cadena"]))
