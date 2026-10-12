"""PF.0 (PLAN_ANALISIS_PELICULAS_08-10.md): placas SINTETICAS de la "posicion inicial de la fuente" de braquiterapia, con verdad conocida.

Dos generadores, los dos INDEPENDIENTES del motor de la aplicacion (paso 13 del protocolo del plan: no se valida un motor con su propio
generador). Este archivo no importa nada de `analisisImagenes`, `services`, `data` ni `ui` (lo fija un test por AST); las medidas auxiliares
que usa para calibrarse (cuerda de saturacion, contraste de la banda de transito) estan escritas aqui, con su definicion.

  1. INDEPENDIENTE (`generar_independiente`): el generador del anexo `scripts/med_braqui_generador_independiente.py` (modelo propio, escrito
     desde la fisica de la pelicula y la medicion de las placas reales). Mancha de dosis SATURADA con bordes en erf, elipse o rectangulo,
     linea de marcador tan oscura como la meseta, ruido, PNG y JPEG q=95. Mas: la elipse girada respecto de la linea (anexo
     `med_braqui_v3_generador_girada.py`) y la banda de transito de un solo lado (anexo `verif_replica_v3_generador.py`). La banda se mide entre 12 y 50 mm del centro de la mancha, asi
     que tiene que haber pelicula de ese lado: con la banda a la IZQUIERDA (`lado_transito` = -1) la escena va espejada, con la linea en `ancho - 1 - X_LINEA` (como `cable_izquierda` del
     modelo fisico), porque con la linea en x = 300 solo hay 12.7 mm de pelicula a su izquierda y el motor no podria ver esa banda.
  2. FISICO (`generar_fisico`): el modelo del anexo `scripts/med_braqui_filas_anisotropia.py`, calibrado contra la mancha real (cuerda de
     saturacion 6.40 mm y alto al 50 % de 5.0 mm, como braqui_00): fuente lineal de Ir-192 en el formalismo 2D de TG-43 con anisotropia
     (punta y cable) y banda de transito por el cable. La verdad es el centro GEOMETRICO de la fuente; el punto medio de la mancha que
     ve cualquier medida se corre unas decimas de mm por la anisotropia y el transito (fisica, no error de la medida): `punto_medio_aparente_mm`
     lo mide sobre la imagen sin ruido.

La verdad de los dos: `desfase_mm = x de la linea - x del centro de la mancha` (mm a 600 dpi; positivo = la mancha queda a la IZQUIERDA de la
linea), el mismo signo del motor y del cuaderno del fisico; y el sentido FISICO (antes o despues de la marca) que sale de la banda de transito:
la fuente entra por el cable, asi que una mancha del lado del cable esta ANTES de la marca.

LA VERDAD ES LA DE LA IMAGEN DEVUELTA, tambien con la pagina rotada (`rotar_k90`): el desfase y el lado de la banda (`VerdadBraqui.desfase_mm`, `.lado_transito`) se dan en el MARCO DEL
MOTOR, el que usa `analizar`: la imagen se gira el menor angulo que deja la linea vertical (angulo en (-90, 90], antihorario en pantalla; con la linea horizontal son +90 grados) y
"izquierda" es la izquierda de esa imagen girada (con la linea horizontal, ARRIBA de ella). Rotar la pagina k = 0, 1, 2, 3 veces 90 grados (antihorario) deja el desfase y el lado de la
banda como estaban (k = 0 y 3) o les cambia el signo (k = 1 y 2: `SIGNO_DE_LA_PAGINA_ROTADA`); el sentido FISICO no cambia, porque rotar la pelicula no la mueve respecto de su cable. El
argumento `desfase_mm` de los generadores es el de la escena tal como se construye, antes de ubicarla en la pagina y rotarla.

VARIANTES DIFICILES de B.2 (`VARIANTES_DIFICILES`, `generar(modelo, variante, desfase_mm)`): mancha corrida respecto de los clics, meseta plana en
JPEG, franja de transito de un solo lado, elipse 6 x 9 mm girada, mancha chica de 4.5 mm y pagina entera del escaner.

Este archivo NO empieza por `test_`, asi que pytest no lo colecciona: es un modulo auxiliar de pruebas (como `_corpus.py`).
"""
import io
import math
from dataclasses import dataclass

import numpy as np
import cv2

MM_POR_PX = 25.4 / 600.0
FORMA = (672, 1156)               # (alto, ancho) como EPSON009
X_LINEA = 300.37
Y_CENTRO = 308.5
MITAD_ENTRE_CLICS = 171.5         # filas 137 y 480 en el caso vertical
FONDO_EPSON009 = (53.0, 143.0, 93.0)       # B, G, R de la pelicula virgen
FONDO_BRAQUI00 = (53.0, 116.0, 47.0)
PAGINA_PX = (6600, 5100)          # (alto, ancho): la pagina entera del escaner (EPSON031)
FONDO_PAGINA = 250.0              # blanco del escaner fuera de la pelicula (mismo valor que el generador mensual)
DELTA_SATURACION = 2.5            # niveles sobre el minimo del gris que siguen contando como meseta saturada
CUERDA_OBJETIVO_MM = 6.40         # lo que mide el MOTOR en la mancha real: EPSON009 6.22, braqui_00 6.39, EPSON031 6.48
CONTRASTE_OBJETIVO = 12.7         # niveles de la banda de transito (11.7 en EPSON009, 13.2 en braqui_00.jpeg, 13.1 en EPSON031)
# El motor mide la cuerda sobre la ventana rotada con interpolacion bilineal, filtro de mediana 5x5 e imagen cuantizada; la medida
# independiente de este archivo (`cuerda_de_saturacion_mm`, sobre el flotante) lee unos 0.15 mm MENOS en las mismas placas (0.11 a 0.21 mm en
# los 19 escenarios del anexo; el motor ademas mide a saltos de un pixel, 0.042 mm). Los escenarios nuevos se calibran con ese desfase.
OFFSET_CUERDA_MM = 0.15
VARIANTES_DIFICILES = ("mancha_corrida", "meseta_plana_jpeg", "transito_un_lado", "elipse_girada", "mancha_chica", "pagina_entera")
# Signo con que cambian el desfase y el lado de la banda al rotar la pagina k veces 90 grados antihorario (np.rot90), en el marco del motor (ver el docstring del modulo). Rotar la pagina lleva la
# izquierda de la escena a: k = 0 la izquierda; k = 1 abajo; k = 2 la derecha; k = 3 arriba. En el marco del motor "izquierda" es la izquierda de la imagen una vez girada el menor angulo que deja la
# linea vertical: con k par la linea ya es vertical (se queda como esta); con k impar es horizontal y el giro son +90 grados antihorario, que lleva lo de ARRIBA a la izquierda. Asi el desfase y el lado
# de la banda conservan el signo con k = 0 y k = 3 (izquierda, arriba) y lo cambian con k = 1 y k = 2 (abajo, derecha).
SIGNO_DE_LA_PAGINA_ROTADA = (+1, -1, -1, +1)


# ============================================================================================================================
# 1. EL GENERADOR INDEPENDIENTE (anexo: med_braqui_generador_independiente.py, med_braqui_v3_generador_girada.py y
#    verif_replica_v3_generador.py)
# ============================================================================================================================
def _erf(x):
    """erf vectorizado (Abramowitz-Stegun 7.1.26, error < 1.5e-7): sin depender de scipy."""
    x = np.asarray(x, dtype=np.float64)
    s = np.sign(x)
    ax = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * ax)
    poly = ((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592
    return s * (1.0 - poly * t * np.exp(-ax * ax))


def render_independiente(desfase_mm, ancho_mm=6.0, alto_mm=6.0, inclinacion_deg=0.0, forma=FORMA, sigma_borde_mm=0.6,
                         fondo=FONDO_EPSON009, nivel_meseta=0.0, nivel_linea=0.0, ancho_linea_px=7.0, largo_linea_px=430.0,
                         ruido=1.5, semilla=0, x_linea=None, y_centro=Y_CENTRO, forma_mancha="elipse", dv_mancha_px=0.0,
                         giro_elipse_deg=0.0, transito=0.0, lado_transito=+1, transito_sigma_mm=0.6):
    """(imagen uint8 BGR, meta). Marco de la linea (u, v): u perpendicular a la linea (positivo a la derecha), v a lo largo; la mancha tiene
    su centro en u = -desfase, v = dv_mancha_px. `nivel_meseta` y `nivel_linea` son escalares o ternas BGR (0 = el piso del escaner; 1 =
    meseta plana en 1 como braqui_00). `giro_elipse_deg`: los ejes de la elipse (ancho_mm en u, alto_mm en v) girados respecto de la linea.
    `transito` (0 = sin banda): una franja a lo largo del cateter (perpendicular a la linea), de un solo lado de la mancha (`lado_transito`
    = +1 derecha, -1 izquierda), con la fraccion `transito` de la dosis de la meseta y ancho gaussiano `transito_sigma_mm` en v.
    `x_linea` (columna de la linea): por omision X_LINEA, salvo con una banda de transito a la IZQUIERDA, que va en la escena espejada (`ancho - 1 - X_LINEA`) para que haya pelicula
    entre 12 y 50 mm de la mancha de ese lado, donde se mide la banda."""
    alto, ancho = forma
    if x_linea is None:
        x_linea = ancho - 1 - X_LINEA if (transito > 0 and lado_transito < 0) else X_LINEA
    sig = sigma_borde_mm / MM_POR_PX
    wx, wy = ancho_mm / MM_POR_PX, alto_mm / MM_POR_PX
    d = desfase_mm / MM_POR_PX
    phi = np.radians(inclinacion_deg)
    X, Y = np.meshgrid(np.arange(ancho, dtype=np.float64), np.arange(alto, dtype=np.float64))
    dx, dy = X - x_linea, Y - y_centro
    u = dx * np.cos(phi) - dy * np.sin(phi)
    v = dx * np.sin(phi) + dy * np.cos(phi)
    uc = -d
    r2 = sig * np.sqrt(2.0)
    if forma_mancha == "rectangulo":
        px = 0.5 * (_erf((u - (uc - wx / 2)) / r2) - _erf((u - (uc + wx / 2)) / r2))
        vv = v - dv_mancha_px
        py = 0.5 * (_erf((vv + wy / 2) / r2) - _erf((vv - wy / 2) / r2))
        D = px * py
    else:                                              # elipse de semiejes a = wx/2 (u), b = wy/2 (v), girada `giro_elipse_deg`
        a, b = wx / 2.0, wy / 2.0
        uu = u - uc
        vv = v - dv_mancha_px
        g = np.radians(giro_elipse_deg)
        p = uu * np.cos(g) + vv * np.sin(g)            # ejes propios de la elipse
        q = -uu * np.sin(g) + vv * np.cos(g)
        rho = np.sqrt((p / a) ** 2 + (q / b) ** 2)
        grad = np.sqrt((p / a ** 2) ** 2 + (q / b ** 2) ** 2)
        s_dist = np.where(rho > 1e-9, (rho - 1.0) * rho / np.maximum(grad, 1e-12), -min(a, b))   # distancia con signo al borde
        D = 0.5 * (1.0 - _erf(s_dist / r2))
    if transito > 0:
        perfil_v = np.exp(-0.5 * ((v - dv_mancha_px) / (transito_sigma_mm / MM_POR_PX)) ** 2)
        D = np.maximum(D, transito * perfil_v * ((u - uc) * lado_transito > 0))
    cov = (np.clip(0.5 + (ancho_linea_px / 2 - np.abs(u)), 0, 1) * np.clip(0.5 + (largo_linea_px / 2 - np.abs(v)), 0, 1))
    fondo = np.broadcast_to(np.asarray(fondo, dtype=np.float64), (3,))
    niv_m = np.broadcast_to(np.asarray(nivel_meseta, dtype=np.float64), (3,))
    niv_l = np.broadcast_to(np.asarray(nivel_linea, dtype=np.float64), (3,))
    rng = np.random.default_rng(semilla)
    img = np.empty((alto, ancho, 3), np.float64)
    for c in range(3):
        s = fondo[c] * (1.0 - D) + niv_m[c] * D
        s = s * (1.0 - cov) + niv_l[c] * cov
        img[:, :, c] = s + rng.normal(0.0, ruido, (alto, ancho)) if ruido > 0 else s
    img = np.clip(np.rint(img), 0, 255).astype(np.uint8)
    # centro de la mancha en la imagen (px): (u, v) -> (x, y) con la rotacion inversa
    cxm = x_linea + uc * np.cos(phi) + dv_mancha_px * np.sin(phi)
    cym = y_centro - uc * np.sin(phi) + dv_mancha_px * np.cos(phi)
    meta = {"desfase_mm": float(desfase_mm), "desfase_px": float(d), "ancho_mm": ancho_mm, "alto_mm": alto_mm,
            "inclinacion_deg": inclinacion_deg, "sigma_borde_mm": sigma_borde_mm, "x_linea": x_linea, "y_centro": y_centro,
            "forma_mancha": forma_mancha, "dv_mancha_px": dv_mancha_px, "giro_elipse_deg": giro_elipse_deg,
            "transito": transito, "lado_transito": lado_transito if transito > 0 else None,
            "centro_mancha_px": (float(cxm), float(cym))}
    return img, meta


def clics_sobre_la_linea(inclinacion_deg=0.0, x_linea=X_LINEA, y_centro=Y_CENTRO, mitad=MITAD_ENTRE_CLICS, jitter=0, rng=None):
    """Dos clics enteros SOBRE la linea (v = -/+ `mitad` px), redondeados como un clic; `jitter`: +-px lateral al azar (con `rng`)."""
    phi = np.radians(inclinacion_deg)
    pts = []
    for s in (-1.0, +1.0):
        x = x_linea + s * mitad * np.sin(phi)
        y = y_centro + s * mitad * np.cos(phi)
        cx, cy = int(round(x)), int(round(y))
        if jitter and rng is not None:
            cx += int(rng.integers(-jitter, jitter + 1))
        pts.append([cx, cy])
    return pts


# ============================================================================================================================
# 2. EL MODELO FISICO (anexo: med_braqui_filas_anisotropia.py), calibrado SIN el motor
# ============================================================================================================================
FONDO_BGR = FONDO_EPSON009
F_SAT_BGR = (1.15, 1.00, 0.90)    # cada canal llega a 0.5 nivel (redondea a 0) a la dosis f_c: el R satura antes y el B despues

BASE = {"L_mm": 3.5, "z0_mm": 1.0, "F0": 0.75, "F180": 0.65, "w0": 20.0, "w180": 20.0, "transito": True,
        "factor_transito": 1.0, "psi_deg": 0.0, "alfa_deg": 0.0, "dv_mm": 0.0, "phi_deg": 0.0,
        "cuerda_mm": CUERDA_OBJETIVO_MM, "sigma_blur_px": 0.8, "ruido": 1.5, "ancho_linea_px": 7.0, "largo_linea_px": 430.0,
        "grano_sigma": 0.0, "grano_l_px": 6.0, "piso_escaner": 0.0, "lado_cable": +1}
ESCENARIOS = {
    "control": {"F0": 1.0, "F180": 1.0, "transito": False},
    "principal": {},
    "solo_anisotropia": {"transito": False},
    "solo_transito": {"F0": 1.0, "F180": 1.0},
    "anisotropia_simetrica": {"F0": 0.70, "F180": 0.70, "transito": False},
    "cable_estrecho": {"w180": 8.0},
    "aniso_ancha": {"w0": 35.0, "w180": 35.0},
    "z0_05": {"z0_mm": 0.5},
    "transito_x5": {"factor_transito": 5.0},
    "fuera_del_plano_5": {"psi_deg": 5.0},
    "fuera_del_plano_10": {"psi_deg": 10.0},
    "cateter_oblicuo_3": {"alfa_deg": 3.0},
    "cateter_oblicuo_15": {"alfa_deg": 15.0, "transito": False},     # sin banda: a 15 grados el transito se aleja de las filas de la mancha
    "clics_descentrados": {"dv_mm": 2.5},
    "mancha_chica": {"cuerda_mm": 4.5},
    "mancha_grande": {"cuerda_mm": 8.5},
    "inclinada": {"phi_deg": 1.5},
    "grano_pelicula": {"grano_sigma": 0.03},
    "grano_pelicula_control": {"F0": 1.0, "F180": 1.0, "transito": False, "grano_sigma": 0.03},
    "linea_13px": {"ancho_linea_px": 13.0},
    "linea_13px_control": {"F0": 1.0, "F180": 1.0, "transito": False, "ancho_linea_px": 13.0},
    # nuevos de PF.0
    "plana1": {"piso_escaner": 1.0, "ruido": 0.15},                    # meseta plana en 1 con casi nada de ruido, como braqui_00
    "cable_izquierda": {"lado_cable": -1},                             # el espejo del principal (la imagen invertida de izquierda a derecha): el cable sale por la izquierda
    "transito_x5_izquierda": {"factor_transito": 5.0, "lado_cable": -1},
}
# Lo que puede cambiarse sin recalibrar: no mueve ni la cuerda de saturacion ni el contraste de la banda de transito.
CAMBIOS_SIN_RECALIBRAR = ("ruido", "ancho_linea_px", "largo_linea_px", "grano_sigma", "grano_l_px")


def parametros_del_escenario(nombre):
    if nombre not in ESCENARIOS:
        raise KeyError(f"escenario fisico desconocido: {nombre!r} (hay {sorted(ESCENARIOS)})")
    return dict(BASE, **ESCENARIOS[nombre])


def _rejilla(forma=FORMA):
    alto, ancho = forma
    return np.meshgrid(np.arange(ancho, dtype=np.float64), np.arange(alto, dtype=np.float64))


def coordenadas_linea(par):
    """(u, v) de cada pixel en el marco de la linea (px)."""
    X, Y = _rejilla()
    phi = math.radians(par["phi_deg"])
    dx, dy = X - X_LINEA, Y - Y_CENTRO
    u = dx * math.cos(phi) - dy * math.sin(phi)
    v = dx * math.sin(phi) + dy * math.cos(phi)
    return u, v


def anisotropia(theta_deg, par):
    return (1.0 - (1.0 - par["F0"]) * np.exp(-(theta_deg / par["w0"]) ** 2)
            - (1.0 - par["F180"]) * np.exp(-((180.0 - theta_deg) / par["w180"]) ** 2))


def componentes_dosis(par, desfase_mm, u=None, v=None):
    """(G_L * F, nucleo del transito) en cada pixel (sin la escala A ni T_tr): fuente lineal de longitud activa L con anisotropia, y el
    recorrido por el cateter del lado del cable. La PUNTA mira a -u y el cable sale por +u. (El escenario con el cable a la izquierda
    no se calcula aqui: `generar_fisico` invierte de izquierda a derecha la escena con el cable a la derecha.)"""
    if u is None:
        u, v = coordenadas_linea(par)
    us, vs = -desfase_mm / MM_POR_PX, par["dv_mm"] / MM_POR_PX
    pu, pv = (u - us) * MM_POR_PX, (v - vs) * MM_POR_PX
    z0 = par["z0_mm"]
    alfa, psi = math.radians(par["alfa_deg"]), math.radians(par["psi_deg"])
    # direccion de la PUNTA (unitaria): hacia -u, girada alfa en el plano y psi hacia la pelicula
    e = (-math.cos(psi) * math.cos(alfa), -math.cos(psi) * math.sin(alfa), -math.sin(psi))
    pz = -z0
    a = pu * e[0] + pv * e[1] + pz * e[2]
    r2 = pu * pu + pv * pv + pz * pz
    h = np.sqrt(np.maximum(r2 - a * a, 1e-12))
    Lh = par["L_mm"] / 2.0
    beta = np.arctan((a + Lh) / h) - np.arctan((a - Lh) / h)
    G = beta / (par["L_mm"] * h)
    theta = np.degrees(np.arccos(np.clip(a / np.sqrt(r2), -1.0, 1.0)))
    GF = G * anisotropia(theta, par)
    # el transito recorre el CATETER, apoyado en la pelicula (altura z0, direccion en el plano alfa): la inclinacion psi es solo de la
    # fuente dentro de la luz del cateter (con psi = 0, a_c = a y h_c = h)
    ec = (-math.cos(alfa), -math.sin(alfa))
    a_c = pu * ec[0] + pv * ec[1]
    h_c = np.sqrt(np.maximum(pu * pu + pv * pv + z0 * z0 - a_c * a_c, 1e-12))
    nucleo_tr = (z0 / h_c) * (0.5 - np.arctan(a_c / h_c) / math.pi)
    return GF, nucleo_tr


def escanear(D, par, semilla=None, con_linea=True, cuantizar=True):
    """Dosis -> escaneo BGR (linea, desenfoque del escaner, ruido si `semilla` no es None). uint8 si `cuantizar`; float64 si no
    (las calibraciones miden sobre el flotante: la cuantizacion a niveles enteros haria escalonada la cuerda)."""
    u, v = coordenadas_linea(par)
    largo = np.clip(0.5 + (par["largo_linea_px"] / 2 - np.abs(v)), 0, 1)
    cov = (np.clip(0.5 + (par["ancho_linea_px"] / 2 - np.abs(u)), 0, 1) * largo) if con_linea else np.zeros_like(u)
    rng = np.random.default_rng(semilla) if semilla is not None else None
    if rng is not None and par["grano_sigma"] > 0:
        # sensibilidad local de la pelicula (grano / falta de uniformidad): D_eff = D (1 + eps), eps gaussiano correlacionado
        # (filtro gaussiano de grano_l_px), desviacion relativa grano_sigma; el mismo campo en los 3 canales
        eps = cv2.GaussianBlur(rng.normal(0.0, 1.0, FORMA), (0, 0), par["grano_l_px"])
        eps = eps / np.std(eps) * par["grano_sigma"]
        D = D * (1.0 + eps)
    piso = par["piso_escaner"]
    img = np.empty(FORMA + (3,), np.float64)
    for c in range(3):
        k = math.log(FONDO_BGR[c] / 0.5) / F_SAT_BGR[c]
        s = piso + (FONDO_BGR[c] - piso) * np.exp(-k * D)
        s = s * (1.0 - cov) + piso * cov
        if par["sigma_blur_px"] > 0:
            s = cv2.GaussianBlur(s, (0, 0), par["sigma_blur_px"])
        if rng is not None:
            s = s + rng.normal(0.0, par["ruido"], s.shape)
        img[:, :, c] = s
    return np.clip(np.rint(img), 0, 255).astype(np.uint8) if cuantizar else img


def clics_fisico(par):
    phi = math.radians(par["phi_deg"])
    pts = []
    for s in (-1.0, 1.0):
        x = X_LINEA + s * MITAD_ENTRE_CLICS * math.sin(phi)
        y = Y_CENTRO + s * MITAD_ENTRE_CLICS * math.cos(phi)
        pts.append([int(round(x)), int(round(y))])
    return pts


# ----------------------------------------------------------------------------------------------------------------------------
# Las dos medidas con que se CALIBRA el modelo fisico (definidas aqui, sin el motor):
#   cuerda de saturacion: sobre el gris sin ruido y SIN la linea, el ancho (mm, cruces subpixel) de la region contigua con gris <=
#       minimo + DELTA_SATURACION en cada fila; la cuerda de la mancha es la mas ancha.
#   contraste de la banda de transito: en el gris INVERTIDO (255 - gris), la mediana de las filas del cateter (cuerda >= 80 % de la
#       mas ancha) entre 12 mm (o 4 radios) y 50 mm del centro de la mancha del lado del cable, menos la mediana de las filas de pelicula
#       entre los clics por encima y por debajo de la mancha (a mas de un radio); el menor de los dos contrastes.
def gris_de(bgr):
    """Gris con los coeficientes de OpenCV (BGR a gris)."""
    return 0.114 * bgr[:, :, 0] + 0.587 * bgr[:, :, 1] + 0.299 * bgr[:, :, 2]


def cuerdas_de_saturacion_px(gris, delta=DELTA_SATURACION):
    """(y, cuerda_px, x_izq, x_der) de las filas con region saturada: gris <= minimo + delta en el tramo contiguo que contiene el minimo
    de la fila; los extremos con interpolacion lineal entre pixeles."""
    umbral = float(gris.min()) + delta
    filas = np.where(gris.min(axis=1) <= umbral)[0]
    ys, cuerdas, xi, xd = [], [], [], []
    for y in filas:
        f = gris[y]
        k = int(np.argmin(f))
        i = k
        while i > 0 and f[i - 1] <= umbral:
            i -= 1
        j = k
        while j < len(f) - 1 and f[j + 1] <= umbral:
            j += 1
        if i == 0 or j == len(f) - 1:
            continue
        a = (i - 1) + (umbral - f[i - 1]) / (f[i] - f[i - 1])
        b = j + (f[j] - umbral) / (f[j] - f[j + 1])
        ys.append(int(y))
        cuerdas.append(b - a)
        xi.append(a)
        xd.append(b)
    return np.array(ys), np.array(cuerdas), np.array(xi), np.array(xd)


def cuerda_de_saturacion_mm(bgr_float):
    y, cuerda, _, _ = cuerdas_de_saturacion_px(gris_de(bgr_float))
    return float(cuerda.max() * MM_POR_PX) if len(cuerda) else 0.0


def punto_medio_aparente_mm(bgr_float, x_linea=X_LINEA):
    """Desfase APARENTE (mm, positivo = a la izquierda de la linea vertical x_linea) segun la region saturada: la mediana, en las filas con
    cuerda >= 80 % de la mas ancha, de x_linea - punto medio de la cuerda. Sobre la imagen SIN ruido y SIN linea. No es la verdad (la verdad
    es el centro geometrico de la fuente): es lo que vale el punto medio de la mancha, con la anisotropia y el transito de por medio."""
    y, cuerda, xi, xd = cuerdas_de_saturacion_px(gris_de(bgr_float))
    sel = cuerda >= 0.8 * cuerda.max()
    return float(np.median(x_linea - (xi[sel] + xd[sel]) / 2.0) * MM_POR_PX)


def contraste_de_transito(bgr_float, lado_cable=+1, y_clics=(137, 480)):
    """Contraste (niveles) de la banda de transito: ver la definicion arriba. 0.0 si no hay filas o pelicula que medir."""
    gris = gris_de(bgr_float)
    y, cuerda, xi, xd = cuerdas_de_saturacion_px(gris)
    if not len(y):
        return 0.0
    sel = cuerda >= 0.8 * cuerda.max()
    filas = y[sel]
    centro = float(np.median((xi[sel] + xd[sel]) / 2.0))
    radio = float(np.median((xd[sel] - xi[sel]))) / 2.0
    inv = 255.0 - gris
    alto, ancho = inv.shape
    desde = max(int(round(12.0 / MM_POR_PX)), int(round(4 * radio)))
    hasta = int(round(50.0 / MM_POR_PX))
    if lado_cable > 0:
        cols = np.arange(min(ancho, int(centro) + desde), min(ancho, int(centro) + hasta))
    else:
        cols = np.arange(max(0, int(centro) - hasta), max(0, int(centro) - desde))
    arriba = np.arange(max(0, int(math.ceil(min(y_clics)))), max(0, int(filas.min() - radio)))
    abajo = np.arange(min(alto, int(filas.max() + radio) + 1), min(alto, int(math.floor(max(y_clics))) + 1))
    pelicula = inv > 60.0

    def mediana(f):
        if len(f) < 10 or len(cols) < 50:
            return None
        sub, msk = inv[np.ix_(f, cols)], pelicula[np.ix_(f, cols)]
        return float(np.median(sub[msk])) if msk.sum() >= 500 else None
    banda, sup, inf = mediana(filas), mediana(arriba), mediana(abajo)
    if banda is None or (sup is None and inf is None):
        return 0.0
    return float(min(banda - v for v in (sup, inf) if v is not None))


def _biseccion(f, lo, hi, objetivo, iteraciones, log=True):
    flo = f(lo) - objetivo
    for _ in range(iteraciones):
        mid = math.sqrt(lo * hi) if log else 0.5 * (lo + hi)
        fm = f(mid) - objetivo
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return math.sqrt(lo * hi) if log else 0.5 * (lo + hi)


def calibrar(par, cuerda_objetivo_mm=None):
    """{'A', 'T_tr'}: la escala de dosis A para que la cuerda de saturacion (sin ruido) mida `par['cuerda_mm']` en la escala del MOTOR (la
    medida independiente se corre OFFSET_CUERDA_MM; se puede pasar `cuerda_objetivo_mm` en la escala de la medida independiente), y la
    escala del transito T_tr para que el contraste de la banda sea CONTRASTE_OBJETIVO (si el escenario lleva transito), por rondas porque
    se afectan. `T_tr` ya incluye el `factor_transito` del escenario."""
    objetivo = par["cuerda_mm"] - OFFSET_CUERDA_MM if cuerda_objetivo_mm is None else cuerda_objetivo_mm
    par = dict(par, lado_cable=+1)       # el cable a la izquierda es la imagen invertida del cable a la derecha: las mismas constantes
    GF, NT = componentes_dosis(par, 0.0)

    def cuerda(A, T):
        return cuerda_de_saturacion_mm(escanear(A * GF + T * NT, par, con_linea=False, cuantizar=False))

    T_tr = 0.0
    A = 1.0
    for _ in range(4 if par["transito"] else 1):
        A = _biseccion(lambda a: cuerda(a, T_tr), 0.05, 200.0, objetivo, 26)
        if par["transito"]:
            T_tr = _biseccion(lambda t: contraste_de_transito(escanear(A * GF + t * NT, par, cuantizar=False), +1),
                              1e-4, 5.0, CONTRASTE_OBJETIVO, 24)
    T_final = T_tr * par["factor_transito"]
    if par["transito"] and par["factor_transito"] != 1.0:
        # mismo tamano de meseta con el transito multiplicado: se recalibra A con el T_tr final, en un intervalo acotado alrededor del A
        # ya calibrado (con A muy bajo la "meseta" pasaria a ser la banda de transito y la cuerda dejaria de ser monotona en A)
        A = _biseccion(lambda a: cuerda(a, T_final), 0.3 * A, 3.0 * A, objetivo, 26)
    return {"A": A, "T_tr": T_final}


# Calibraciones de los escenarios: A (escala de la dosis) y T_tr (escala del transito, ya multiplicada por `factor_transito`).
# "anexo": las del modelo calibrado contra la mancha real (anexo del plan, logs/MED_braqui/filas/sint_calibracion.json, 09-10-2026; cuerda de
# saturacion 6.39-6.44 mm y alto al 50 % de 5.0 mm medidos con el motor, como braqui_00; contraste de la banda 12-13 niveles); son las placas con
# las que se derivaron los criterios de B.2. "calibrar()": los escenarios nuevos de PF.0, calibrados con la medida independiente de este
# archivo. Una prueba recalibra algunos con `calibrar` y exige estas constantes (la medida independiente reproduce las del anexo a ~1 %):
# si el modelo cambia y esta tabla no se regenera, la prueba cae.
CALIBRACION_FISICA = {
    "control": {"A": 5.692014332426192, "T_tr": 0.0},  # anexo
    "principal": {"A": 6.489553457836126, "T_tr": 0.034488763983354626},  # anexo
    "solo_anisotropia": {"A": 6.604080915047717, "T_tr": 0.0},  # anexo
    "solo_transito": {"A": 5.597933218338916, "T_tr": 0.03268260620483624},  # anexo
    "anisotropia_simetrica": {"A": 6.626459085010985, "T_tr": 0.0},  # anexo
    "cable_estrecho": {"A": 5.925776429551458, "T_tr": 0.035969568985230446},  # anexo
    "aniso_ancha": {"A": 7.231325384207408, "T_tr": 0.03432217381694192},  # anexo
    "z0_05": {"A": 6.402902962207947, "T_tr": 0.04916164016835238},  # anexo
    "transito_x5": {"A": 5.724723831108499, "T_tr": 0.17244381991677313},  # anexo
    "fuera_del_plano_5": {"A": 6.419852139670481, "T_tr": 0.03376923642089673},  # anexo
    "fuera_del_plano_10": {"A": 6.471699561320172, "T_tr": 0.035456478668920176},  # anexo
    "cateter_oblicuo_3": {"A": 6.3465415358664865, "T_tr": 0.04818665561636749},  # anexo
    "cateter_oblicuo_15": {"A": 6.42796379313468, "T_tr": 0.0},  # calibrar()
    "clics_descentrados": {"A": 6.486559293288465, "T_tr": 0.03483711031444885},  # anexo
    "mancha_chica": {"A": 2.846517450126992, "T_tr": 0.0313107169733548},  # anexo
    "mancha_grande": {"A": 12.638419396760924, "T_tr": 0.04620536745760005},  # anexo
    "inclinada": {"A": 6.462722749080803, "T_tr": 0.03516275091556529},  # anexo
    "grano_pelicula": {"A": 6.484206788720314, "T_tr": 0.035073065452587406},  # anexo
    "grano_pelicula_control": {"A": 5.692014332426192, "T_tr": 0.0},  # anexo
    "linea_13px": {"A": 6.489553457836126, "T_tr": 0.034488763983354626},  # anexo
    "linea_13px_control": {"A": 5.692014332426192, "T_tr": 0.0},  # anexo
    "plana1": {"A": 6.426429121599198, "T_tr": 0.035768734531694525},  # calibrar()
    "cable_izquierda": {"A": 6.489553457836126, "T_tr": 0.034488763983354626},  # anexo (espejo de principal)
    "transito_x5_izquierda": {"A": 5.724723831108499, "T_tr": 0.17244381991677313},  # anexo (espejo de transito_x5)
}


def calibracion_del_escenario(nombre):
    """Las constantes (A, T_tr) del escenario: las de la tabla; si el escenario no esta calibrado todavia, se calibra en el acto (unos segundos)."""
    if nombre in CALIBRACION_FISICA:
        return CALIBRACION_FISICA[nombre]
    return calibrar(parametros_del_escenario(nombre))


# ============================================================================================================================
# 3. LA PLACA DEVUELTA: imagen codificada + verdad
# ============================================================================================================================
@dataclass(frozen=True)
class VerdadBraqui:
    modelo: str                      # 'independiente' | 'fisico'
    desfase_mm: float                # linea - centro de la mancha (geometrico); positivo = la mancha a la IZQUIERDA de la linea, en la IMAGEN DEVUELTA y en el marco del motor (con la pagina rotada
    #                                  k veces 90 grados: el de la escena por SIGNO_DE_LA_PAGINA_ROTADA[k]; con la linea horizontal, positivo = la mancha ARRIBA de ella)
    desfase_px: float                # el mismo, en px
    sentido_fisico: object           # 'antes de la marca' | 'despues de la marca' | 'en la marca' | None (sin banda de transito): un hecho de la pelicula, no cambia al rotar la pagina
    lado_transito: object            # +1 derecha | -1 izquierda | None (sin banda): en la IMAGEN DEVUELTA y en el marco del motor (el de `lado_del_transito`), como el desfase; en la escena
    #                                  sin rotar es el mismo (con la pagina rotada, el de la escena por SIGNO_DE_LA_PAGINA_ROTADA[k])
    centro_mancha_px: tuple          # (x, y) del centro de la mancha en la imagen devuelta (None si la pagina se rota 90, 180 o 270 grados)
    x_linea: float                   # columna de la linea en la fila y_centro de la ESCENA (con pagina, sumar el origen; rotada, ya no vale)
    y_centro: float
    inclinacion_deg: float
    clics: tuple                     # los dos clics enteros, en la imagen devuelta
    pagina: object                   # None | {'origen': (x, y), 'forma': (alto, ancho), 'rotar_k90': k}
    parametros: dict                 # lo que se pidio al generador


@dataclass(frozen=True)
class PlacaBraqui:
    datos: bytes
    formato: str                     # 'png' | 'jpeg'
    imagen: np.ndarray               # BGR uint8 antes de codificar (solo lectura)
    clics: list                      # [[x, y], [x, y]] en la imagen devuelta
    verdad: VerdadBraqui


def sentido_fisico_de(desfase_mm, lado_cable):
    """La fuente entra por el cable: una mancha del lado del cable esta ANTES de la marca. Con la linea vertical y desfase = x_linea - x_mancha,
    la mancha esta del lado del cable si lado_cable * desfase < 0."""
    if lado_cable is None:
        return None
    s = lado_cable * desfase_mm
    if abs(s) < 1e-12:
        return "en la marca"
    return "antes de la marca" if s < 0 else "despues de la marca"


def codificar(img, formato, dpi=600):
    """BGR uint8 -> bytes. PNG sin perdida; JPEG calidad 95 con submuestreo 4:2:0; el archivo declara `dpi` (como los escaneos reales)."""
    from PIL import Image
    sal = io.BytesIO()
    im = Image.fromarray(np.ascontiguousarray(img[:, :, ::-1]))
    if formato == "png":
        im.save(sal, format="PNG", dpi=(dpi, dpi))
    elif formato == "jpeg":
        im.save(sal, format="JPEG", quality=95, subsampling=2, dpi=(dpi, dpi))
    else:
        raise ValueError(f"formato desconocido: {formato!r} (png o jpeg)")
    return sal.getvalue()


def _en_pagina(img, clics, origen, forma, rotar_k90):
    """La pelicula (toda la escena) sobre la pagina del escaner (blanco), y la pagina rotada rotar_k90 veces 90 grados (antihorario)."""
    alto_p, ancho_p = forma
    alto, ancho = img.shape[:2]
    x0, y0 = origen
    if x0 < 0 or y0 < 0 or x0 + ancho > ancho_p or y0 + alto > alto_p:
        raise ValueError("la pelicula no cabe en la pagina con ese origen")
    pagina = np.full((alto_p, ancho_p, 3), np.uint8(FONDO_PAGINA), np.uint8)
    pagina[y0:y0 + alto, x0:x0 + ancho] = img
    pts = [[x + x0, y + y0] for x, y in clics]
    k = rotar_k90 % 4
    for _ in range(k):                                  # np.rot90 antihorario: (x, y) -> (y, ancho_actual - 1 - x)
        h_act, w_act = pagina.shape[:2]
        pts = [[y, w_act - 1 - x] for x, y in pts]
        pagina = np.rot90(pagina)
    return np.ascontiguousarray(pagina), pts


def _armar(modelo, img, clics, meta_geom, formato, pagina, rotar_k90, origen_pagina, parametros, desfase_mm, lado_transito):
    centro = meta_geom["centro_mancha_px"]
    pag = None
    if pagina or rotar_k90:
        origen = origen_pagina if origen_pagina is not None else ((PAGINA_PX[1] - img.shape[1]) // 2, (PAGINA_PX[0] - img.shape[0]) // 2)
        img, clics = _en_pagina(img, clics, origen, PAGINA_PX, rotar_k90)
        pag = {"origen": tuple(origen), "forma": PAGINA_PX, "rotar_k90": rotar_k90 % 4}
        if rotar_k90 % 4 == 0:
            centro = (centro[0] + origen[0], centro[1] + origen[1])
        else:
            centro = None                          # el centro en la imagen rotada depende del giro: no se declara
    img = np.ascontiguousarray(img)
    img.setflags(write=False)
    signo = SIGNO_DE_LA_PAGINA_ROTADA[rotar_k90 % 4]
    desfase_imagen = desfase_mm * signo                    # la verdad describe la imagen DEVUELTA, en el marco del motor (docstring del modulo)
    lado_imagen = None if lado_transito is None else lado_transito * signo
    verdad = VerdadBraqui(modelo, float(desfase_imagen), float(desfase_imagen / MM_POR_PX), sentido_fisico_de(desfase_mm, lado_transito),
                          lado_imagen, centro, float(meta_geom["x_linea"]), float(meta_geom["y_centro"]),
                          float(meta_geom["inclinacion_deg"]), tuple(tuple(c) for c in clics), pag, dict(parametros))
    return PlacaBraqui(codificar(img, formato), formato, img, [list(c) for c in clics], verdad)


def generar_independiente(desfase_mm, *, formato="png", semilla=0, pagina=False, rotar_k90=0, origen_pagina=None, jitter_clic=0, **modelo):
    """Una placa del generador INDEPENDIENTE + su verdad. `modelo`: los argumentos de `render_independiente` (ancho_mm, alto_mm,
    inclinacion_deg, dv_mancha_px, giro_elipse_deg, nivel_meseta, ruido, transito, lado_transito, x_linea, ...). Determinista por (argumentos, semilla).
    `desfase_mm` es el de la escena, antes de ubicarla en la pagina y rotarla; la VERDAD es la de la imagen devuelta, en el marco del motor: con la pagina rotada 1 o 2 veces 90 grados el
    desfase y el lado de la banda cambian de signo (docstring del modulo)."""
    img, meta = render_independiente(desfase_mm, semilla=semilla, **modelo)
    rng_clic = np.random.default_rng(1_000_003 * (semilla + 1)) if jitter_clic else None
    clics = clics_sobre_la_linea(meta["inclinacion_deg"], x_linea=meta["x_linea"], y_centro=meta["y_centro"], jitter=jitter_clic, rng=rng_clic)
    return _armar("independiente", img, clics, meta, formato, pagina, rotar_k90, origen_pagina,
                  dict(modelo, semilla=semilla, jitter_clic=jitter_clic), desfase_mm, meta["lado_transito"])


def generar_fisico(desfase_mm, *, escenario="principal", formato="png", semilla=None, pagina=False, rotar_k90=0, origen_pagina=None,
                   calibracion=None, **cambios):
    """Una placa del modelo FISICO calibrado + su verdad (el centro geometrico de la fuente). `semilla=None`: sin ruido. `cambios`: solo
    los que no obligan a recalibrar (CAMBIOS_SIN_RECALIBRAR); para cualquier otro, agregue un escenario y calibrelo.
    Con `lado_cable` = -1 la escena es la del cable a la derecha invertida de izquierda a derecha (la linea queda en x = ancho - 1 - 300.37 y
    hay pelicula a la izquierda para la banda); `desfase_mm` es el de la escena como queda antes de ubicarla en la pagina y rotarla (positivo = mancha a la izquierda de la linea; con el
    cable a la izquierda, el de esa imagen invertida). La VERDAD es la de la imagen devuelta, en el marco del motor: con la pagina rotada 1 o 2 veces 90 grados el desfase y el lado de la
    banda cambian de signo (docstring del modulo)."""
    malos = sorted(set(cambios) - set(CAMBIOS_SIN_RECALIBRAR))
    if malos:
        raise ValueError(f"{malos} obligan a recalibrar: defina un escenario nuevo en ESCENARIOS (solo se cambia sin recalibrar {CAMBIOS_SIN_RECALIBRAR})")
    par = dict(parametros_del_escenario(escenario), **cambios)
    if par["lado_cable"] not in (+1, -1):
        raise ValueError("lado_cable: +1 (derecha) o -1 (izquierda)")
    if par["lado_cable"] < 0 and par["phi_deg"]:
        raise ValueError("el cable a la izquierda (imagen invertida) no se combina con la linea inclinada")
    cal = calibracion if calibracion is not None else calibracion_del_escenario(escenario)
    ancho = FORMA[1]
    invertir = par["lado_cable"] < 0
    d0 = -desfase_mm if invertir else desfase_mm                      # el desfase de la escena con el cable a la derecha
    GF, NT = componentes_dosis(par, d0)
    img = escanear(cal["A"] * GF + cal["T_tr"] * NT, par, semilla)
    clics = clics_fisico(par)
    phi = math.radians(par["phi_deg"])
    uc, vc = -d0 / MM_POR_PX, par["dv_mm"] / MM_POR_PX
    centro = (X_LINEA + uc * math.cos(phi) + vc * math.sin(phi), Y_CENTRO - uc * math.sin(phi) + vc * math.cos(phi))
    x_linea = X_LINEA
    if invertir:
        img = np.ascontiguousarray(img[:, ::-1])
        clics = [[ancho - 1 - x, y] for x, y in clics]
        centro = (ancho - 1 - centro[0], centro[1])
        x_linea = ancho - 1 - X_LINEA
    meta = {"centro_mancha_px": centro, "x_linea": x_linea, "y_centro": Y_CENTRO, "inclinacion_deg": par["phi_deg"]}
    lado = par["lado_cable"] if par["transito"] else None
    return _armar("fisico", img, clics, meta, formato, pagina, rotar_k90, origen_pagina,
                  dict(par, escenario=escenario, semilla=semilla), desfase_mm, lado)


# ----------------------------------------------------------------------------------------------------------------------------
# VARIANTES DIFICILES de B.2: cada una dice, por modelo, con que argumentos se genera.
_DIFICILES_INDEPENDIENTE = {
    "mancha_corrida": dict(dv_mancha_px=60.0),                                        # la mancha 60 px (2.5 mm) por debajo del punto medio de los clics
    "meseta_plana_jpeg": dict(formato="jpeg", nivel_meseta=1.0, nivel_linea=1.0, ruido=0.15),   # como braqui_00: plana en 1, casi sin ruido
    "transito_un_lado": dict(transito=0.95, lado_transito=+1),                        # franja de transito de un solo lado al 90-97 % del tope
    "elipse_girada": dict(ancho_mm=6.0, alto_mm=9.0, giro_elipse_deg=15.0),           # elipse 6 x 9 mm girada 10-20 grados respecto de la linea
    "mancha_chica": dict(ancho_mm=4.5, alto_mm=4.5),
    "pagina_entera": dict(pagina=True),
}
_DIFICILES_FISICO = {
    "mancha_corrida": dict(escenario="clics_descentrados"),                           # la fuente a 2.5 mm del punto medio de los clics
    "meseta_plana_jpeg": dict(escenario="plana1", formato="jpeg", semilla=7),
    "transito_un_lado": dict(escenario="transito_x5"),                                # banda de transito 5 veces la calibrada, cable a la derecha
    "elipse_girada": dict(escenario="cateter_oblicuo_15"),                            # el analogo fisico: el cateter 15 grados fuera de la normal a la linea
    "mancha_chica": dict(escenario="mancha_chica"),
    "pagina_entera": dict(escenario="principal", pagina=True),
}


def argumentos_de_la_variante(modelo, variante):
    tabla = {"independiente": _DIFICILES_INDEPENDIENTE, "fisico": _DIFICILES_FISICO}[modelo]
    if variante not in tabla:
        raise KeyError(f"variante desconocida: {variante!r} (hay {sorted(tabla)})")
    return dict(tabla[variante])


def generar(modelo, variante, desfase_mm, **cambios):
    """Una placa de una variante dificil de B.2: `modelo` 'independiente' | 'fisico'; los `cambios` pisan los argumentos de la variante."""
    args = dict(argumentos_de_la_variante(modelo, variante), **cambios)
    return (generar_independiente if modelo == "independiente" else generar_fisico)(desfase_mm, **args)
