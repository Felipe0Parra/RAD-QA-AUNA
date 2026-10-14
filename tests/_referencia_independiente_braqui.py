"""B.2 (PLAN_ANALISIS_PELICULAS_08-10.md): la REFERENCIA INDEPENDIENTE de la posicion inicial de la fuente de braquiterapia, solo para juzgar quien acierta en las placas REALES, donde no hay
verdad conocida. Es `scripts/med_braqui_referencia_independiente.py` del anexo del plan, pasada a modulo auxiliar de pruebas SIN CAMBIAR su metodo (08-10); no es el motor ni el cuaderno
del fisico, y este archivo no importa nada de `analisisImagenes`, `services`, `data` ni `ui` (lo fija un test por AST: no se valida un motor con una copia de si mismo).

Idea (morfologia, sin `argmax` ni umbrales por fila):
  1. Gris crudo (cv2.imread(ruta, 0)); se recorta una ventana alrededor de los clics y se rota para dejar la linea vertical
     (angulo -atan2(dx, dy) desde los clics, centro FLOTANTE = punto medio de los clics, INTER_LINEAR en float32).
  2. LINEA: filas del segmento clicado FUERA de la mancha (a mas de 20 px del borde oscuro); por fila, centroide del exceso de
     oscuridad (gris invertido) sobre una linea base lineal entre los extremos de una ventana de +-20 px; ajuste robusto x(y).
  3. MANCHA: mascara gris_crudo <= T (T en {4, 8, 16} niveles: "meseta saturada" en el piso del escaner); apertura con elipse
     de 31 px (borra la linea, que mide ~7-10 px, y deja la mancha de ~150 px), cierre con elipse de 21 px (tapa los huecos del
     ruido), componente conexa que contiene el centro; centro = punto medio de los extremos de la mascara en las +-15 filas
     centrales DE LA MANCHA (no del punto medio de los clics), mediana.
  4. desfase = x_linea(y_central) - x_mancha  (px de la imagen rotada; mm con 25.4/600).
  5. Que T: `referencia_elegida` toma el umbral cuya mancha mide el ancho mas cercano a 6.4 mm (lo que mide el motor en las placas reales: 6.2-6.5 mm).
Validada en el anexo sobre las sinteticas independientes (PNG, semilla 0; verdad conocida): error maximo 0.155 / 0.069 / 0.021 mm con T = 4 / 8 / 16. No modifica ningun archivo.

LIMITE DECLARADO (ronda 1 de la revision de B.2, hallazgo DL-03; el metodo de arriba NO cambia): el acuerdo con el motor vale para la meseta que ESTA REGLA elige, no para cualquier definicion de la meseta.
El 6.4 mm es el ancho de la cuerda MAS ANCHA del motor (6.2-6.5 mm); la referencia reporta el ancho de las 31 filas centrales de su mascara, y el del motor en esas mismas filas mide 5.9 a 6.3 mm. Medido el
14-10 (guiones `sensibilidad_T.py` y `b2_corr_r1_ancho_meseta.py`, logs en `logs/B2/`): en EPSON009 T = 4 y T = 8 dan manchas de 3.1 y 3.9 mm (la mitad de la del motor) y difieren de el 0.70 y 0.77 mm,
y solo T = 16 (6.39 mm) es comparable (0.019 / 0.021 mm); en braqui_00.jpeg, EPSON031 y braqui_00.JPG T = 8 (6.56 mm) difiere 0.013 / 0.038 / 0.040 mm pero T = 4 (6.01 mm, mas cerca del ancho central del
motor) difiere 0.072 / 0.067 / 0.088 mm. Son dos estimadores del CENTRO sobre una meseta definida casi igual: no validan la definicion de la meseta (su ancho es una propiedad de la pelicula). Las pruebas lo
dicen y lo fijan en `test_b2_braqui_placas_reales.py`: la premisa (la mancha elegida es de ancho comparable a la del motor) y el limite conocido (0.12 mm con cualquier mancha de ancho comparable).
"""
import numpy as np
import cv2

MM_POR_PX = 25.4 / 600.0
ANCHO_ESPERADO_MM = 6.4          # el ancho de la mancha saturada en las placas reales de braqui (6.2-6.5 mm): con ese se elige el umbral T


def _ventana_rotada(gris_crudo, clics, medio=900):
    (x1, y1), (x2, y2) = clics
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    alto, ancho = gris_crudo.shape
    x0, y0 = max(0, int(cx) - medio), max(0, int(cy) - medio)
    x1_, y1_ = min(ancho, int(cx) + medio), min(alto, int(cy) + medio)
    sub = gris_crudo[y0:y1_, x0:x1_]
    ang = -np.degrees(np.arctan2(float(x2 - x1), float(y2 - y1)))
    while ang > 90.0:
        ang -= 180.0
    while ang <= -90.0:
        ang += 180.0
    c = (cx - x0, cy - y0)
    M = cv2.getRotationMatrix2D(c, ang, 1.0)
    rot = cv2.warpAffine(sub.astype(np.float32), M, (sub.shape[1], sub.shape[0]), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REPLICATE)
    clics_r = cv2.transform(np.array(clics, np.float64).reshape(-1, 1, 2) - np.array([x0, y0], np.float64), M).reshape(-1, 2)
    return rot, clics_r, ang


def _linea(rot, clics_r, filas_excluidas):
    inv = 255.0 - rot
    ys = np.arange(int(np.ceil(clics_r[:, 1].min())), int(np.floor(clics_r[:, 1].max())) + 1)
    x_aprox = float(clics_r[:, 0].mean())
    filas, centros = [], []
    for y in ys:
        if y in filas_excluidas:
            continue
        a = int(round(x_aprox)) - 20
        w = inv[y, a:a + 41]
        if len(w) < 41:
            continue
        base = np.linspace(w[:5].mean(), w[-5:].mean(), len(w))
        exc = np.clip(w - base, 0, None)
        if exc.sum() < 150:                       # sin linea visible en esta fila
            continue
        filas.append(y)
        centros.append(a + (np.arange(len(w)) * exc).sum() / exc.sum())
    filas, centros = np.array(filas, float), np.array(centros, float)
    if len(filas) < 10:
        return None
    usadas = np.ones(len(filas), bool)
    for _ in range(5):
        p = np.polyfit(filas[usadas], centros[usadas], 1)
        res = centros - np.polyval(p, filas)
        mad = np.median(np.abs(res[usadas] - np.median(res[usadas])))
        nuevas = np.abs(res) <= max(3 * 1.4826 * mad, 0.4)
        if np.array_equal(nuevas, usadas):
            break
        usadas = nuevas
    p = np.polyfit(filas[usadas], centros[usadas], 1)
    return p, int(usadas.sum())


def _mancha(rot, T, centro_xy):
    mask = (rot <= T).astype(np.uint8)
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k_close)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    cx, cy = int(round(centro_xy[0])), int(round(centro_xy[1]))
    et = lab[cy, cx]
    if et == 0:                                   # el centro no cae en la mancha: la componente mas grande cerca del centro
        sub = lab[max(0, cy - 150):cy + 150, max(0, cx - 150):cx + 150]
        cand = [e for e in np.unique(sub) if e != 0]
        if not cand:
            return None
        et = max(cand, key=lambda e: stats[e, cv2.CC_STAT_AREA])
    comp = lab == et
    return comp


def referencia(ruta, clics, umbrales=(4, 8, 16), semialto=15):
    """Devuelve {T: {'desfase_mm', 'desfase_px', 'ancho_mm', 'x_mancha', 'x_linea', ...} | None} sobre el gris crudo del archivo `ruta`."""
    gris = cv2.imread(ruta, 0)
    return referencia_de_la_imagen(gris, clics, umbrales, semialto)


def referencia_de_la_imagen(gris, clics, umbrales=(4, 8, 16), semialto=15):
    """Lo mismo que `referencia` sobre un gris ya leido (uint8, el que se obtendria con `cv2.imread(ruta, 0)`)."""
    rot, clics_r, ang = _ventana_rotada(gris, [tuple(c) for c in clics])
    cx, cy = float(clics_r[:, 0].mean()), float(clics_r[:, 1].mean())
    out = {}
    for T in umbrales:
        comp = _mancha(rot, T, (cx, cy))
        if comp is None:
            out[T] = None
            continue
        filas = np.where(comp.any(axis=1))[0]
        ymin, ymax = filas.min(), filas.max()
        excl = set(range(int(ymin) - 20, int(ymax) + 21))
        lin = _linea(rot, clics_r, excl)
        if lin is None:
            out[T] = None
            continue
        p, n_usadas = lin
        yc = int(round((ymin + ymax) / 2.0))        # fila central de la MANCHA (no el punto medio de los clics)
        xs, anchos = [], []
        for y in range(yc - semialto, yc + semialto + 1):
            cols = np.where(comp[y])[0]
            if len(cols) == 0:
                continue
            xs.append((cols.min() + cols.max()) / 2.0)
            anchos.append(cols.max() - cols.min() + 1)
        if not xs:
            out[T] = None
            continue
        x_mancha = float(np.median(xs))
        x_linea = float(np.polyval(p, yc))
        d = x_linea - x_mancha
        out[T] = {"desfase_px": d, "desfase_mm": d * MM_POR_PX, "ancho_mm": float(np.median(anchos)) * MM_POR_PX,
                  "x_mancha": x_mancha, "x_linea": x_linea, "filas_linea": n_usadas, "filas_mancha": [int(ymin), int(ymax)]}
    return out


def elegida_de_la_imagen(gris, clics):
    """(T elegido, desfase_mm) de la referencia con el umbral cuyo ancho de mancha se acerca mas a `ANCHO_ESPERADO_MM`, o (None, None) si ningun umbral dio mancha."""
    r = referencia_de_la_imagen(gris, clics)
    validos = {T: v for T, v in r.items() if v is not None}
    if not validos:
        return None, None
    T = min(validos, key=lambda k: abs(validos[k]["ancho_mm"] - ANCHO_ESPERADO_MM))
    return T, validos[T]["desfase_mm"]


def referencia_elegida(ruta, clics):
    """Lo mismo que `elegida_de_la_imagen` sobre el archivo `ruta` (gris crudo, `cv2.imread(ruta, 0)`)."""
    return elegida_de_la_imagen(cv2.imread(ruta, 0), clics)
