"""PF.0 (PLAN_ANALISIS_PELICULAS_08-10.md): peliculas radiocromicas del control MENSUAL, SINTETICAS, con verdad conocida.

Es el generador calibrado del anexo (`scripts/med_mensual_sintetica.py`, calibrado en ML0.JPG) con su fisica sin cambiar, MAS
DOS EXTENSIONES declaradas que las peliculas reales tienen y el generador del anexo no podia producir (H18):

  1. un FWHM que varia linealmente con la posicion:  w_x(v) = w_x0 + beta * v   (v = mm hacia abajo desde el centro del campo;
     `beta` en mm por mm; con beta = 0 es el generador del anexo). La verdad por banda se calcula del MODELO (`fwhm_x_en(v)`).
  2. una meseta en forma de CUPULA: la dosis del campo se multiplica por  1 + (cupula_pct_40mm / 100) * (r / 40 mm)^2,  r = distancia al
     centro del campo; las peliculas reales dan -2 a -5 % a 40 mm (con un porcentaje positivo el perfil tendria cuernos, no cupula). Con 0 es el del anexo.

Este archivo NO empieza por `test_`, asi que pytest no lo colecciona: es un modulo auxiliar de pruebas (como `_corpus.py`).
Es INDEPENDIENTE del motor de la aplicacion (paso 13 del protocolo del plan: no se valida un motor con su propio generador): no importa
nada de `analisisImagenes`, `services`, `data` ni `ui` (lo fija un test por AST).

MODELO (mm; x/u a la derecha, y/v hacia abajo; origen = centro del campo de RADIACION)
  D(u, v) = [ Fx(u; w_x(v)) * Fy(v) + (1 - Fx*Fy) * s * exp(-d / lam) ] * C(u, v)       dosis relativa; meseta = 1 en el centro
  F(u; w) = 0.5 [ erf((u + w/2)/(sqrt2 sigma)) - erf((u - w/2)/(sqrt2 sigma)) ]
  d       = distancia al rectangulo nominal (0 dentro);   s = 0.04, lam = 15 mm: cola de dispersion
  C(u, v) = max(0, 1 + (cupula_pct_40mm/100) * (u^2 + v^2) / 40^2)
  crudo_c = virgen_c - (virgen_c - meseta_c) * g_c(D)       g_c(D) = (1 - exp(-k_c D)) / (1 - exp(-k_c))     (k = 0: lineal)
  + ruido gaussiano sigma = 1.5 por capa y pixel, redondeo y recorte a [0, 255]
  w_x0 y w_y se resuelven para que el ancho al 50 % de la dosis (cola y cupula incluidas) en los EJES CENTRALES sea EXACTAMENTE
  100.0 x 99.0 mm.  Marcas de tinta (puntos oscuros) en las 4 esquinas del campo LUMINOSO y en el reticulo.
  La pelicula (115 x 116 mm, con el campo descentrado) puede girar theta y colocarse sobre un recorte o una pagina del escaner.

LA VERDAD
  FWHM de la DOSIS: el ancho de la FILA (columna) al 50 % del valor que la fila (columna) tiene en SU centro, que para la cupula es su
  maximo. Los bordes de cada CAPA son los que predice la respuesta del propio generador sin ruido: el cruce del 50 % de
  g_c(D), con el piso en la pelicula virgen y el tope en el centro de la fila. Solo el azul es lineal en la dosis (k = 0): con el se valida
  el algoritmo, no se elige capa (H18 d). Los anchos por capa difieren (azul < verde < rojo) porque la respuesta satura.

CD.6 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, H7): UNA VARIANTE con la respuesta definida en DENSIDAD OPTICA NETA. La respuesta de arriba (g_c en el valor de pixel) expresada en netOD es
concava y el modelo de Devic (convexo) no la puede representar; para probar la base «dosis» del motor hace falta una pelicula cuya respuesta sea la de una curva de calibracion. Con
`respuestas_netod` = {"R": r, "G": g, "B": b} (objetos con `dosis(x)` vectorizable, como `RespuestaDevic` de `_piezas_de_calibracion_sinteticas`) y `dosis_meseta_cgy` (la dosis de D = 1, el centro
del campo), el crudo de cada capa es  virgen_c * 10^(-x_c(D * dosis_meseta_cgy)),  con x_c la inversa de la respuesta por biseccion PROPIA y vectorizada (`_netod_de`); el resto (la dosis D(u, v),
la geometria, la tinta, el ruido, el redondeo) no cambia. La verdad en DOSIS es la de siempre (100.0 x 99.0 mm en los ejes centrales); la verdad por capa de `VerdadMensual.capas` es la del valor de pixel
y en la variante queda VACIA ({}): no se usa. Sin `respuestas_netod` el generador es el de PF.0 byte a byte (`respuestas_netod=None` no toca ninguna linea de su camino).

Uso:   import _placa_mensual_sintetica as G
       placa = G.generar("tiff", bits=16, alfa=True, variante="A", theta_deg=0.4, seed=1, dpi=150, beta=0.02, cupula_pct_40mm=-3.5)
       placa.datos (bytes del archivo), placa.verdad (VerdadMensual), placa.imagen (arreglo BGR/BGRA antes de codificar)
"""
import io
import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.special import erf

MM_POR_PULGADA = 25.4
DPI_REAL = 600
FILAS_POR_BLOQUE = 256           # el arreglo se arma por bloques de filas para no pedir cientos de MB; la salida NO depende de este numero
RADIO_CUPULA_MM = 40.0           # distancia a la que se da la caida de la cupula
CAPAS = ("B", "G", "R")          # orden de OpenCV: el arreglo de la imagen es BGR
INDICE_CAPA = {"B": 0, "G": 1, "R": 2}

# ----------------------------------------------------------------------------------------------------------------------------
# Calibracion medida en ML0.JPG (anexo: med_mensual_calibrar.py). Valores BGR (orden de OpenCV). Identica a la del anexo.
CALIB = dict(
    virgen_bgr=(82.0, 174.0, 105.5),     # mediana cruda de la pelicula fuera del campo (4 esquinas de la pelicula)
    meseta_bgr=(39.0, 32.0, 1.0),        # mediana cruda de la meseta central (sin la marca del centro)
    k_bgr=(0.0, 0.7, 3.6),               # saturacion g_c: azul lineal, verde moderada, rojo fuerte (cerrado con el cuaderno en ML0)
    sigma_mm=2.3,                        # penumbra (sigma de la erf de la dosis)
    s_cola=0.04, lam_mm=15.0,            # cola de dispersion
    ruido=1.5,                           # sigma del ruido crudo por capa
    fondo_escaner=250.0,                 # blanco del escaner fuera de la pelicula
    tinta_radio_mm=0.50, tinta_borde_mm=0.10, tinta_nucleo_bgr=(4.0, 4.0, 4.0),
    # geometria de verdad
    campo_rad_mm=(100.0, 99.0),          # FWHM_x, FWHM_y de la dosis al 50 %
    campo_luz_mm=(99.6, 99.8),           # campo luminoso (ancho, alto)
    luz_desplazada_mm=(-0.6, 0.4),       # centro luminoso - centro radiacion
    reticulo_mm=(0.3, -0.2),             # reticulo - centro luminoso
    pelicula_mm=(115.0, 116.0),          # ancho, alto de la pelicula
    campo_en_pelicula_mm=(57.3, 55.3),   # posicion del centro del campo desde la esquina sup. izq. de la pelicula
)
# variantes de encuadre (a 600 dpi): nombre -> (tipo, pagina_px, descentrado_px)
#   A: recorte AJUSTADO = rectangulo inscrito en la pelicula girada (sin fondo de escaner)
#   L: recorte SUELTO = caja envolvente de la pelicula girada (con las cunas blancas de las esquinas)
#   B/C/D/E: pagina blanca con la pelicula centrada / descentrada (-250,-200) / muy descentrada (+800, 0) / (+345,-200)
ENCUADRES = {"A": ("inscrito", None, (0, 0)), "L": ("caja", None, (0, 0)),
             "B": ("pagina", (3300, 3300), (0, 0)), "C": ("pagina", (3300, 3300), (-250, -200)),
             "D": ("pagina", (4400, 3300), (800, 0)), "E": ("pagina", (3300, 3300), (345, -200))}

CUPULA_REAL_MIN_PCT = -2.0       # las peliculas reales: -2 a -5 % a 40 mm (H18 b)
CUPULA_REAL_MAX_PCT = -5.0


# ----------------------------------------------------------------------------------------------------------------------------
def _dosis_1d(u, w, sig):
    return 0.5 * (erf((u + w / 2) / (math.sqrt(2) * sig)) - erf((u - w / 2) / (math.sqrt(2) * sig)))


def _g(D, k):
    return D if k < 1e-9 else (1.0 - np.exp(-k * D)) / (1.0 - math.exp(-k))


ITERACIONES_DE_LA_INVERSA = 80      # CD.6: la biseccion vectorizada de la variante en netOD (80 mitades de un intervalo de netOD de orden 1: por debajo de la resolucion de un float64)


def _netod_de(respuesta, dosis):
    """CD.6: la densidad optica neta x >= 0 con respuesta.dosis(x) = dosis, por biseccion PROPIA del generador sobre un arreglo (no usa el motor). `respuesta.dosis` es creciente y vale 0 en 0."""
    d = np.maximum(np.asarray(dosis, dtype=np.float64), 0.0)
    alto = np.ones_like(d)
    while np.any(respuesta.dosis(alto) < d):
        alto = np.where(respuesta.dosis(alto) < d, alto * 2.0, alto)
    bajo = np.zeros_like(d)
    for _ in range(ITERACIONES_DE_LA_INVERSA):
        medio = (bajo + alto) / 2.0
        debajo = respuesta.dosis(medio) < d
        bajo, alto = np.where(debajo, medio, bajo), np.where(debajo, alto, medio)
    return (bajo + alto) / 2.0


def _factor_cupula(u, v, cupula_pct_40mm):
    return np.maximum(1.0 + (cupula_pct_40mm / 100.0) * (u * u + v * v) / RADIO_CUPULA_MM ** 2, 0.0)


def _resolver_w(ancho_objetivo, sig, s_cola, lam, cupula_pct_40mm):
    """w nominal tal que el cruce al 50 % de la dosis total (cola y cupula incluidas) en el eje caiga en +-ancho_objetivo/2.
    El otro eje esta en su meseta (F ~ 1) y el 100 % es el centro del campo (donde la cupula vale 1)."""
    u = ancho_objetivo / 2.0
    c = float(_factor_cupula(np.array(u), np.array(0.0), cupula_pct_40mm))

    def f(w):
        F = _dosis_1d(u, w, sig)
        d = max(0.0, u - w / 2.0)
        return (F + (1.0 - F) * s_cola * math.exp(-d / lam)) * c - 0.5

    return brentq(f, ancho_objetivo - 6 * sig, ancho_objetivo + 6 * sig, xtol=1e-13)


class Campo:
    """El campo de RADIACION: dosis relativa D(u, v) y las magnitudes que se miden de ella (bordes, FWHM), todo en mm."""

    def __init__(self, calib=None, beta=0.0, cupula_pct_40mm=0.0):
        self.c = CALIB if calib is None else calib
        self.beta = float(beta)
        self.cupula_pct_40mm = float(cupula_pct_40mm)
        sig = self.c["sigma_mm"]
        self.wx0 = _resolver_w(self.c["campo_rad_mm"][0], sig, self.c["s_cola"], self.c["lam_mm"], self.cupula_pct_40mm)
        self.wy = _resolver_w(self.c["campo_rad_mm"][1], sig, self.c["s_cola"], self.c["lam_mm"], self.cupula_pct_40mm)

    # -- la dosis -------------------------------------------------------------------------------------------------------------
    def ancho_x(self, v):
        """Ancho nominal de la rendija en x a la altura v: w_x(v) = w_x0 + beta * v."""
        return self.wx0 + self.beta * v

    def dosis(self, u, v):
        c = self.c
        sig = c["sigma_mm"]
        wx = self.ancho_x(v)
        Fx = _dosis_1d(u, wx, sig)
        Fy = _dosis_1d(v, self.wy, sig)
        F = Fx * Fy
        d = np.hypot(np.maximum(0.0, np.abs(u) - wx / 2.0), np.maximum(0.0, np.abs(v) - self.wy / 2.0))
        base = F + (1.0 - F) * c["s_cola"] * np.exp(-d / c["lam_mm"])
        return base * _factor_cupula(u, v, self.cupula_pct_40mm)

    def respuesta_normalizada(self, D, capa=None):
        """n(D): la dosis misma (capa None) o la respuesta g_c(D) de la capa, normalizada a 1 en D = 1 y 0 en la pelicula virgen."""
        if capa is None:
            return D
        return _g(D, self.c["k_bgr"][INDICE_CAPA[capa]])

    # -- los bordes al 50 % ---------------------------------------------------------------------------------------------------
    def _raiz(self, f, lado, media_anchura):
        """Raiz de f a lo largo de un eje, en el lado `lado` (+1/-1) del centro, entre 'bien adentro' y 'bien afuera' de la penumbra."""
        sig = self.c["sigma_mm"]
        a, b = lado * (media_anchura - 6 * sig), lado * (media_anchura + 8 * sig)
        fa, fb = f(a), f(b)
        if not (fa > 0 > fb):
            raise ValueError(f"no hay cruce del 50 % entre {a:.2f} y {b:.2f} mm (f = {fa:.4g}, {fb:.4g}): parametros fuera del modelo")
        return brentq(f, min(a, b), max(a, b), xtol=1e-12)

    def borde_fila(self, v, lado, capa=None):
        """u (mm) del borde izquierdo (lado = -1) o derecho (+1) de la FILA v, al 50 % de lo que la fila vale en su centro (u = 0)."""
        v = float(v)
        ref = 0.5 * float(self.respuesta_normalizada(self.dosis(np.array(0.0), np.array(v)), capa))
        return self._raiz(lambda u: float(self.respuesta_normalizada(self.dosis(np.array(u), np.array(v)), capa)) - ref,
                          lado, self.ancho_x(v) / 2.0)

    def limite_columna_mm(self):
        """Hasta que |u| la columna es plana en y: mas afuera, con beta != 0, el borde lateral del trapecio cruza la columna y su perfil ya no
        tiene meseta (4 sigmas de la penumbra por dentro del ancho minimo de la rendija)."""
        return (self.wx0 - abs(self.beta) * self.wy / 2.0) / 2.0 - 4.0 * self.c["sigma_mm"]

    def borde_columna(self, u, lado, capa=None):
        """v (mm) del borde superior (lado = -1) o inferior (+1) de la COLUMNA u, al 50 % de lo que la columna vale en su centro (v = 0)."""
        u = float(u)
        if abs(u) > self.limite_columna_mm():
            raise ValueError(f"la verdad por columna solo vale dentro de la meseta (|u| <= {self.limite_columna_mm():.1f} mm), no en u = {u:g}")
        ref = 0.5 * float(self.respuesta_normalizada(self.dosis(np.array(u), np.array(0.0)), capa))
        return self._raiz(lambda v: float(self.respuesta_normalizada(self.dosis(np.array(u), np.array(v)), capa)) - ref,
                          lado, self.wy / 2.0)

    def fwhm_x_en(self, v, capa=None):
        """FWHM crossplane (mm) de la fila a la altura v."""
        return self.borde_fila(v, +1, capa) - self.borde_fila(v, -1, capa)

    def fwhm_y_en(self, u, capa=None):
        """FWHM inplane (mm) de la columna a la distancia u del centro."""
        return self.borde_columna(u, +1, capa) - self.borde_columna(u, -1, capa)


# ----------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CapaVerdad:
    """Lo que predice la respuesta del generador (sin ruido) para UNA capa, en los ejes centrales del campo de radiacion."""
    nombre: str
    k: float
    lineal: bool                 # solo el azul (k = 0) es lineal en la dosis
    FWHM_x: float
    FWHM_y: float
    bordes: dict                 # L, R, T, B en mm (sistema de la pelicula)


class VerdadMensual:
    """La verdad de una pelicula sintetica: geometria en mm (sistema de la pelicula, origen en el centro del campo de radiacion), su
    posicion en la imagen (px) y, por capa, los bordes que predice la respuesta del generador. Las funciones `*_en(...)` evaluan el
    MODELO en cualquier fila o columna (la verdad por banda)."""

    def __init__(self, campo, geometria, calib, parametros):
        self.campo = campo
        c = calib
        self.parametros = dict(parametros)
        self.beta = campo.beta
        self.cupula_pct_40mm = campo.cupula_pct_40mm
        self.w_nominal_mm = (campo.wx0, campo.wy)
        # -- la dosis en los ejes centrales (v = 0 y u = 0): los 100.0 x 99.0 mm de la construccion
        xL, xR = campo.borde_fila(0.0, -1), campo.borde_fila(0.0, +1)
        yT, yB = campo.borde_columna(0.0, -1), campo.borde_columna(0.0, +1)
        self.FWHM_x, self.FWHM_y = xR - xL, yB - yT
        self.bordes_rad = dict(L=xL, R=xR, T=yT, B=yB)
        luz, self.marcas_mm = _luz_y_marcas(c)
        lcx, lcy = c["luz_desplazada_mm"]
        self.bordes_luz = luz
        # radiacion - luz, positivo hacia afuera (lado izquierdo/superior: hacia -; derecho/inferior: hacia +)
        self.exceso = dict(L=luz["L"] - xL, R=xR - luz["R"], T=luz["T"] - yT, B=yB - luz["B"])
        self.centro_rad_menos_luz = (((xL + xR) / 2) - lcx, ((yT + yB) / 2) - lcy)
        self.reticulo_menos_luz = tuple(c["reticulo_mm"])
        self.centro_luz = (lcx, lcy)
        # -- por capa: la respuesta del propio generador, sin ruido
        self.capas = {}
        for nombre in CAPAS:
            bx = (campo.borde_fila(0.0, -1, nombre), campo.borde_fila(0.0, +1, nombre))
            by = (campo.borde_columna(0.0, -1, nombre), campo.borde_columna(0.0, +1, nombre))
            k = c["k_bgr"][INDICE_CAPA[nombre]]
            self.capas[nombre] = CapaVerdad(nombre, k, k < 1e-9, bx[1] - bx[0], by[1] - by[0],
                                            dict(L=bx[0], R=bx[1], T=by[0], B=by[1]))
        # -- la imagen
        self.variante = geometria["variante"]
        self.giro_deg = geometria["theta_deg"]
        self.dpi = geometria["dpi"]
        self.ancho, self.alto = geometria["W"], geometria["H"]
        self.centro_campo_px = (float(geometria["cx"]), float(geometria["cy"]))
        self._geom = geometria
        self.marcas_px = {n: self.mm_a_px(*m) for n, m in self.marcas_mm.items()}
        pel = geometria["pel"]
        self.esquinas_pelicula_px = {"UL": self.mm_a_px(pel["L"], pel["T"]), "UR": self.mm_a_px(pel["R"], pel["T"]),
                                     "DL": self.mm_a_px(pel["L"], pel["B"]), "DR": self.mm_a_px(pel["R"], pel["B"])}
        self.pelicula_mm = pel

    # -- geometria ------------------------------------------------------------------------------------------------------------
    def mm_a_px(self, u, v):
        """Punto (u, v) del sistema de la pelicula (mm) -> (x, y) de la imagen (px, float)."""
        return _mm_a_px(self._geom, u, v)

    def clics(self):
        """Los centros verdaderos de las marcas, redondeados a entero como los clics del fisico (orden del cuaderno: UL, UR, C, DR, DL)."""
        return {k: (int(round(p[0])), int(round(p[1]))) for k, p in self.marcas_px.items()}

    def clics_del_cuaderno(self):
        m = self.clics()
        return [m["UL"], m["UR"], m["C"], m["DR"], m["DL"]]

    # -- la verdad por banda --------------------------------------------------------------------------------------------------
    def fwhm_x_en(self, v_mm, capa=None):
        return self.campo.fwhm_x_en(v_mm, capa)

    def fwhm_y_en(self, u_mm, capa=None):
        return self.campo.fwhm_y_en(u_mm, capa)

    def bordes_fila_en(self, v_mm, capa=None):
        return (self.campo.borde_fila(v_mm, -1, capa), self.campo.borde_fila(v_mm, +1, capa))

    def bordes_columna_en(self, u_mm, capa=None):
        return (self.campo.borde_columna(u_mm, -1, capa), self.campo.borde_columna(u_mm, +1, capa))

    def fwhm_x_por_banda(self, bandas_mm, capa=None):
        """{v: FWHM crossplane} para las alturas `bandas_mm` (mm desde el centro del campo de radiacion)."""
        return {float(v): self.campo.fwhm_x_en(v, capa) for v in bandas_mm}

    def fwhm_x_en_el_cruce(self, capa=None):
        """FWHM crossplane en la fila que pasa por el CRUCE DE DIAGONALES de las marcas luminosas (la que miden los cuadernos y la app)."""
        return self.campo.fwhm_x_en(self.centro_luz[1], capa)

    def fwhm_y_en_el_cruce(self, capa=None):
        return self.campo.fwhm_y_en(self.centro_luz[0], capa)

    def resumen(self):
        """Un diccionario plano con lo principal (para registrar o comparar)."""
        return dict(variante=self.variante, giro_deg=self.giro_deg, dpi=self.dpi, ancho=self.ancho, alto=self.alto,
                    FWHM_x=self.FWHM_x, FWHM_y=self.FWHM_y, bordes_rad=self.bordes_rad, bordes_luz=self.bordes_luz,
                    exceso=self.exceso, centro_rad_menos_luz=self.centro_rad_menos_luz,
                    reticulo_menos_luz=self.reticulo_menos_luz, centro_campo_px=self.centro_campo_px, marcas_px=self.marcas_px,
                    beta=self.beta, cupula_pct_40mm=self.cupula_pct_40mm,
                    capas={n: dict(FWHM_x=c.FWHM_x, FWHM_y=c.FWHM_y, bordes=c.bordes) for n, c in self.capas.items()})


@dataclass(frozen=True)
class PlacaMensual:
    datos: bytes                 # el archivo codificado (jpeg / png / tiff)
    formato: str                 # 'jpeg' | 'png' | 'tiff'
    bits: int                    # 8 o 16 por canal
    alfa: object                 # False | True (alfa opaco) | 'sin_pelicula' (transparente fuera de la pelicula)
    dpi: int                     # la resolucion con que se genero (y que declara el archivo)
    imagen: np.ndarray           # el arreglo antes de codificar: BGR o BGRA, uint8 o uint16 (solo lectura)
    verdad: VerdadMensual


# ----------------------------------------------------------------------------------------------------------------------------
def _luz_y_marcas(c):
    """Los bordes del campo LUMINOSO y las marcas (esquinas luminosas y reticulo) en el sistema de la pelicula (mm)."""
    lw, lh = c["campo_luz_mm"]
    lcx, lcy = c["luz_desplazada_mm"]
    luz = dict(L=lcx - lw / 2, R=lcx + lw / 2, T=lcy - lh / 2, B=lcy + lh / 2)
    marcas = dict(UL=(luz["L"], luz["T"]), UR=(luz["R"], luz["T"]), DL=(luz["L"], luz["B"]), DR=(luz["R"], luz["B"]),
                  C=(lcx + c["reticulo_mm"][0], lcy + c["reticulo_mm"][1]))
    return luz, marcas


def _mm_a_px(geom, u, v):
    """Punto (u, v) del sistema de la pelicula (mm) -> (x, y) de la imagen (px, float). La UNICA definicion de esa transformacion."""
    return (float(geom["cx"] + (u * geom["ct"] - v * geom["st"]) / geom["px"]),
            float(geom["cy"] + (u * geom["st"] + v * geom["ct"]) / geom["px"]))


def _uv(geom, y0, y1):
    """(u, v) en mm, en el sistema de la pelicula, de cada pixel de las filas y0..y1-1 de la imagen (arreglos de (y1 - y0, ancho)): el giro inverso.
    La UNICA definicion de ese cambio de coordenadas: la usan la imagen (`_construir`) y el mapa de dosis (`mapa_dosis`)."""
    X = np.arange(geom["W"], dtype=np.float64)[None, :]
    Y = np.arange(y0, y1, dtype=np.float64)[:, None]
    dx = (X - geom["cx"]) * geom["px"]
    dy = (Y - geom["cy"]) * geom["px"]
    return dx * geom["ct"] + dy * geom["st"], -dx * geom["st"] + dy * geom["ct"]


def _geometria(variante, theta_deg, dpi, desplazamiento_px, c):
    px = MM_POR_PULGADA / dpi
    th = math.radians(theta_deg)
    ct, st = math.cos(th), math.sin(th)
    fw, fh = c["pelicula_mm"]
    fcx, fcy = c["campo_en_pelicula_mm"]
    # esquinas de la pelicula en el sistema del campo (u, v) [mm]: origen = centro del campo
    pel = dict(L=-fcx, R=fw - fcx, T=-fcy, B=fh - fcy)
    esq = np.array([(pel["L"], pel["T"]), (pel["R"], pel["T"]), (pel["L"], pel["B"]), (pel["R"], pel["B"])])
    # a pixeles de imagen relativos al centro del campo, con giro theta (sentido horario en pantalla, y hacia abajo)
    rel = np.stack([(esq[:, 0] * ct - esq[:, 1] * st), (esq[:, 0] * st + esq[:, 1] * ct)], axis=1) / px
    minx, miny = rel.min(axis=0)
    maxx, maxy = rel.max(axis=0)
    tipo, pagina, desc = ENCUADRES[variante]
    escala = dpi / DPI_REAL
    if tipo in ("inscrito", "caja"):
        if tipo == "inscrito":
            ix = int(math.ceil(fh / px * abs(st))) + 3
            iy = int(math.ceil(fw / px * abs(st))) + 3
        else:
            ix = iy = 0
        x0, x1 = minx + ix, maxx - ix
        y0, y1 = miny + iy, maxy - iy
        W = int(math.floor(x1 - x0))
        H = int(math.floor(y1 - y0))
        cx, cy = -x0, -y0                           # centro del campo en la imagen
    else:
        W, H = int(round(pagina[0] * escala)), int(round(pagina[1] * escala))
        bx = (minx + maxx) / 2.0
        by = (miny + maxy) / 2.0
        cx = W / 2.0 + desc[0] * escala - bx
        cy = H / 2.0 + desc[1] * escala - by
    if desplazamiento_px is not None:
        cx += desplazamiento_px[0]
        cy += desplazamiento_px[1]
    return dict(variante=variante, theta_deg=float(theta_deg), dpi=dpi, px=px, ct=ct, st=st, W=W, H=H, cx=cx, cy=cy, pel=pel)


def _ventana_de_marca(mx, my, W, H, rad, borde, px):
    r0 = int(math.ceil((rad + 6 * borde) / px)) + 2
    return max(0, int(mx) - r0), min(W, int(mx) + r0 + 1), max(0, int(my) - r0), min(H, int(my) + r0 + 1)


def _construir(campo, geom, c, tinta, ruido, fondo, defectos, seed, bits, alfa, filas_por_bloque):
    """El arreglo (H, W, 3 o 4) BGR/BGRA, uint8 o uint16, armado por bloques de filas. Devuelve (arreglo, marcas_px). CD.6: si la calibracion `c` trae `respuestas_netod` y `dosis_meseta_cgy`, la
    variante en netOD (ver el docstring del modulo)."""
    respuestas_netod, dosis_meseta_cgy = c.get("respuestas_netod"), c.get("dosis_meseta_cgy")
    W, H, px, cx, cy = geom["W"], geom["H"], geom["px"], geom["cx"], geom["cy"]
    pel = geom["pel"]
    V = np.array(c["virgen_bgr"])
    P = np.array(c["meseta_bgr"])
    ks = c["k_bgr"]
    rng = np.random.default_rng(seed)
    sig_n = c["ruido"] if ruido is None else ruido
    # marcas de tinta (esquinas luminosas y reticulo): posiciones en la imagen
    marcas_px = {n: _mm_a_px(geom, mu, mv) for n, (mu, mv) in _luz_y_marcas(c)[1].items()}
    n_canales = 4 if alfa else 3
    salida = np.empty((H, W, n_canales), np.uint16 if bits == 16 else np.uint8)
    rad, borde = c["tinta_radio_mm"], c["tinta_borde_mm"]
    nuc = np.array(c["tinta_nucleo_bgr"])
    for y0 in range(0, H, filas_por_bloque):
        y1 = min(H, y0 + filas_por_bloque)
        u, v = _uv(geom, y0, y1)                        # imagen -> pelicula: giro inverso
        D = campo.dosis(u, v)
        if fondo == "pelicula":
            en_pelicula = np.ones(D.shape, bool)
        else:
            en_pelicula = (u >= pel["L"]) & (u <= pel["R"]) & (v >= pel["T"]) & (v <= pel["B"])
        img = np.empty((y1 - y0, W, 3), np.float64)
        for ch in range(3):
            if respuestas_netod is None:
                raw = V[ch] - (V[ch] - P[ch]) * _g(D, ks[ch])
            else:          # CD.6: la variante en netOD
                raw = V[ch] * 10.0 ** (-_netod_de(respuestas_netod[CAPAS[ch]], D * dosis_meseta_cgy))
            img[:, :, ch] = np.where(en_pelicula, raw, c["fondo_escaner"])
        if tinta:
            for nombre, (mx, my) in marcas_px.items():
                xa, xb, ya, yb = _ventana_de_marca(mx, my, W, H, rad, borde, px)
                ya, yb = max(ya, y0), min(yb, y1)
                if xb <= xa or yb <= ya:
                    continue
                xs, ys = np.meshgrid(np.arange(xa, xb), np.arange(ya, yb))
                rr = np.hypot(xs - mx, ys - my) * px
                m = 0.5 * (1.0 - erf((rr - rad) / (math.sqrt(2) * borde)))     # 1 dentro, 0 fuera
                sub = img[ya - y0:yb - y0, xa:xb, :]
                for ch in range(3):
                    sub[:, :, ch] = sub[:, :, ch] * (1 - m) + nuc[ch] * m
        for d in (defectos or []):
            # rayones claros (valor crudo alto) en coordenadas de IMAGEN relativas al centro del campo (mm)
            if d["tipo"] == "rayon_v":
                xx = int(round(cx + d["u_mm"] / px))
                ya, yb = int(cy - d["largo_mm"] / 2 / px), int(cy + d["largo_mm"] / 2 / px)
                xa, xb = max(0, xx), xx + d.get("ancho_px", 2)
            elif d["tipo"] == "rayon_h":
                yy = int(round(cy + d["v_mm"] / px))
                xa, xb = int(cx - d["largo_mm"] / 2 / px), int(cx + d["largo_mm"] / 2 / px)
                ya, yb = max(0, yy), yy + d.get("ancho_px", 2)
                xa = max(0, xa)
            else:
                raise ValueError(f"defecto desconocido: {d['tipo']!r}")
            ya, yb = max(ya, 0, y0), min(yb, y1)
            if yb > ya and xb > xa:
                img[ya - y0:yb - y0, xa:xb, :] = d["valor"]
        if sig_n:
            img += rng.normal(0.0, sig_n, img.shape)
        if bits == 16:
            bloque = np.clip(np.rint(img * 257.0), 0, 65535).astype(np.uint16)
            opaco = 65535
        else:
            bloque = np.clip(np.rint(img), 0, 255).astype(np.uint8)
            opaco = 255
        salida[y0:y1, :, :3] = bloque
        if alfa:
            salida[y0:y1, :, 3] = np.where(en_pelicula, opaco, 0) if alfa == "sin_pelicula" else opaco
    salida.setflags(write=False)
    return salida, marcas_px


# ----------------------------------------------------------------------------------------------------------------------------
def codificar(imagen, formato, dpi=DPI_REAL):
    """Arreglo BGR/BGRA (uint8 o uint16) -> bytes. JPEG q=95 4:2:0; PNG de 8 bits; TIFF de 8 o 16 bits sin compresion (alfa 'unassociated'
    como los TIFF del Epson). El archivo declara `dpi`. Determinista: los mismos bytes en dos llamadas."""
    from PIL import Image
    import tifffile
    n = imagen.shape[2]
    sal = io.BytesIO()
    if formato == "tiff":
        rgb = imagen[:, :, [2, 1, 0] + ([3] if n == 4 else [])]
        tifffile.imwrite(sal, np.ascontiguousarray(rgb), photometric="rgb", resolution=(dpi, dpi), resolutionunit="INCH",
                         compression=None, extrasamples=["unassalpha"] if n == 4 else None)
        return sal.getvalue()
    if imagen.dtype != np.uint8:
        raise ValueError(f"{formato} solo guarda 8 bits por canal aqui; para 16 bits use 'tiff'")
    if formato == "jpeg":
        if n == 4:
            raise ValueError("un JPEG no lleva canal alfa")
        Image.fromarray(np.ascontiguousarray(imagen[:, :, ::-1])).save(sal, format="JPEG", quality=95, subsampling=2, dpi=(dpi, dpi))
    elif formato == "png":
        rgb = imagen[:, :, [2, 1, 0] + ([3] if n == 4 else [])]
        Image.fromarray(np.ascontiguousarray(rgb)).save(sal, format="PNG", dpi=(dpi, dpi))
    else:
        raise ValueError(f"formato desconocido: {formato!r} (jpeg, png o tiff)")
    return sal.getvalue()


def generar_arreglo(*, bits=8, alfa=False, variante="A", theta_deg=0.0, seed=1, dpi=DPI_REAL, tinta=True, ruido=None,
                    desplazamiento_px=None, fondo="blanco", defectos=None, beta=0.0, cupula_pct_40mm=0.0, calib=None,
                    filas_por_bloque=FILAS_POR_BLOQUE, respuestas_netod=None, dosis_meseta_cgy=None):
    """La pelicula sintetica sin codificar: (arreglo BGR/BGRA uint8 o uint16 de solo lectura, verdad). Para pruebas que no necesitan el archivo.

    bits: 8 | 16.  alfa: False | True (canal alfa opaco, como los TIFF del Epson) | 'sin_pelicula' (alfa 0 fuera de la pelicula: 'sin dato').
    variante: encuadre A/L/B/C/D/E (ver ENCUADRES).  theta_deg: giro de la pelicula (horario en pantalla).  seed: semilla del ruido
    (determinista: los mismos argumentos dan el mismo arreglo).  dpi: resolucion de la imagen (600 es la real; menos acelera las pruebas).
    beta / cupula_pct_40mm: las dos extensiones (0 = el generador del anexo).  fondo: 'blanco' (escaner) | 'pelicula'.
    respuestas_netod / dosis_meseta_cgy (CD.6): la variante con la respuesta en netOD; las dos o ninguna."""
    if bits not in (8, 16):
        raise ValueError("bits debe ser 8 o 16")
    if alfa not in (False, True, "sin_pelicula"):
        raise ValueError("alfa: False, True o 'sin_pelicula'")
    if (respuestas_netod is None) != (dosis_meseta_cgy is None):
        raise ValueError("la variante en netOD pide `respuestas_netod` y `dosis_meseta_cgy` juntas")
    if respuestas_netod is not None and (set(respuestas_netod) != set(CAPAS) or not dosis_meseta_cgy > 0):
        raise ValueError("`respuestas_netod` trae una respuesta por capa (R, G y B) y `dosis_meseta_cgy` es positiva")
    c = CALIB if calib is None else calib
    if respuestas_netod is not None:          # CD.6: la variante viaja en la calibracion (como la respuesta de PF.0, `k_bgr`)
        c = dict(c, respuestas_netod=dict(respuestas_netod), dosis_meseta_cgy=float(dosis_meseta_cgy))
    campo = Campo(c, beta=beta, cupula_pct_40mm=cupula_pct_40mm)
    geom = _geometria(variante, theta_deg, dpi, desplazamiento_px, c)
    imagen, _ = _construir(campo, geom, c, tinta, ruido, fondo, defectos, seed, bits, alfa, filas_por_bloque)
    verdad = VerdadMensual(campo, geom, c, dict(seed=seed, tinta=tinta, ruido=ruido, fondo=fondo, desplazamiento_px=desplazamiento_px,
                                                 bits=bits, alfa=alfa, formato=None))
    if respuestas_netod is not None:          # CD.6: en la variante la verdad es la de la DOSIS; la de cada capa en valor de pixel no vale
        verdad.capas = {}
        verdad.parametros.update(respuestas_netod=dict(respuestas_netod), dosis_meseta_cgy=float(dosis_meseta_cgy))
    return imagen, verdad


def generar(formato="png", *, bits=8, alfa=False, dpi=DPI_REAL, **opciones):
    """Una pelicula mensual sintetica codificada + su verdad. `formato`: 'jpeg' (q=95, 4:2:0) | 'png' (8 bits) | 'tiff' (8 o 16 bits). El resto de las
    opciones son las de `generar_arreglo`. El archivo declara `dpi`. Determinista: los mismos argumentos dan los mismos bytes."""
    if bits == 16 and formato != "tiff":
        raise ValueError("16 bits por canal solo en tiff")
    if formato == "jpeg" and alfa:
        raise ValueError("un JPEG no lleva canal alfa")
    imagen, verdad = generar_arreglo(bits=bits, alfa=alfa, dpi=dpi, **opciones)
    verdad.parametros["formato"] = formato
    return PlacaMensual(codificar(imagen, formato, dpi), formato, bits, alfa, dpi, imagen, verdad)


def mapa_dosis(variante="A", theta_deg=0.0, dpi=DPI_REAL, desplazamiento_px=None, beta=0.0, cupula_pct_40mm=0.0, calib=None):
    """La dosis relativa D (float64, sin ruido ni respuesta de la pelicula) en cada pixel de la imagen que `generar` arma con los mismos
    argumentos, y su verdad. Es lo que las pruebas integran de forma independiente para comparar con la verdad por construccion."""
    c = CALIB if calib is None else calib
    campo = Campo(c, beta=beta, cupula_pct_40mm=cupula_pct_40mm)
    geom = _geometria(variante, theta_deg, dpi, desplazamiento_px, c)
    u, v = _uv(geom, 0, geom["H"])
    verdad = VerdadMensual(campo, geom, c, dict(seed=None, tinta=False, ruido=0, fondo="blanco", desplazamiento_px=desplazamiento_px,
                                                 bits=None, alfa=False, formato=None))
    return campo.dosis(u, v), verdad
