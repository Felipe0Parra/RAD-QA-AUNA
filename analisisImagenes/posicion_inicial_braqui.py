"""PI.1 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md): el motor de la "Posición inicial" de braquiterapia.

Es el análisis del notebook `Codigo_AnalisisImagen/Analisis_placa_inicial_braqui_corregido.ipynb` -- el
método del físico: dos clics sobre la línea de referencia, rotar para dejarla vertical, región del
máximo (meseta) por fila, centro de la meseta contra la línea -- con las correcciones medidas en §2.2
del plan (los cuatro defectos del método sin corregir y la mejora subpíxel):

  V1. ángulo canónico con atan2 (una línea horizontal ya no divide por cero);
  V2. una mancha cortada por el borde de la película se declara "no medible" (antes solo se detectaba
      si el corte caía dentro del marco);
  V3. solo cuentan las filas cuyos dos bordes de meseta se ven (la línea tapaba un borde y corría el
      centro hasta 6 px);
  V4. el sentido físico sale de la banda de tránsito (antes / después de la marca), no de cómo quedó
      la imagen;
  +   bordes de la meseta con interpolación subpíxel (peor caso geométrico 0.34 -> 0.09 px);
  +   ventana alrededor de la línea marcada: sirve igual para el recorte que para la página completa
      del escáner, que trae la hoja blanca alrededor;
  +   la escala (PI.1b): el procedimiento es de 600 dpi, garantizado desde el escaneo (el físico recorta con gThumb
      o con Paint, que reescribe la resolución declarada a 96 dpi sin remuestrear), y esa es la escala de
      `escala_mm`. La resolución que el archivo DECLARA (`resolucion_imagen.py`; Pillow rellena 72 dpi en un JPEG
      con EXIF sin resolución y 1 dpi en un TIFF) solo se CLASIFICA (`clase_resolucion`): coincide con 600, falta,
      la escribió un editor (72 o 96: se usa 600 y se avisa en pantalla) u otra (300, 200...: un escaneo a otra
      resolución, sin milímetros ni veredicto). La comprobación por el ancho de la meseta saturada (6.2-6.5 mm en
      las placas reales) queda como deuda (DP-143).
  +   la lectura (A.1, 12-10): `analisisImagenes/pelicula.py::leer_pelicula` es el ÚNICO lector de películas (8 o 16 bits por canal, capas con nombre, el alfa como "sin
      dato"); `leer_imagen` de aquí delega en él con la misma firma y, en 8 bits, los mismos arreglos de siempre. Una imagen con zonas transparentes ya no se rechaza:
      `analizar(..., validos=)` recibe la máscara de píxeles con dato y la trata como el marco (lo transparente no es película). `clase_resolucion` y `escala_mm` se
      mudaron a `pelicula.py` (una sola definición) y se re-exportan aquí con el mismo nombre. Versión PI-2.
  +   (A.1, ronda 1 de la revisión) la transparencia dice lo que hace: si la zona analizada tiene píxeles sin dato, el motivo de "no quedan filas con la mancha a la vista" y el
      de una línea que no se pudo ubicar lo anotan (`NOTA_DE_TRANSPARENCIA`) en vez de culpar a la línea; y `refinar_linea` ya no lanza cuando el recorte robusto rechaza todas
      las filas (una tira transparente de 1 px junto a la línea las partía en dos grupos): devuelve None y el motor mide contra los clics, como siempre que no ubica la línea.

  +   (B.1, 12-10) el detalle del transito de cada lado medible trae ademas los LIMITES de la region que midio (`columnas`, `filas_banda`, `filas_arriba`, `filas_abajo`, `desde_px`, `hasta_px`,
      `desde_mm`, `hasta_mm`), para que la pagina dibuje las bandas sin repetir la regla; sin escala (resolucion 'otra') los milimetros son None y quedan las distancias en pixeles al centro de
      la mancha. Es DIBUJO: ningun numero cambia (el lado y los contrastes son los de siempre; un lado sin pelicula suficiente sigue siendo None) y por eso la version sigue siendo PI-2.

Sin Qt y sin base de datos (lo comprueba un test por AST): lo usan la página, el recálculo de un
registro guardado, la pestaña sintética y los tests, todos con la misma función `analizar`. Cualquier
cambio de la lógica de este archivo obliga a subir `VERSION_ALGORITMO`: lo guardado se compara contra
lo recalculado al abrirlo (DD3).
"""
import numpy as np
import cv2
from scipy.ndimage import median_filter

from analisisImagenes.pelicula import clase_resolucion, escala_mm, leer_pelicula   # clase_resolucion y escala_mm: re-exportadas (A.1), mismo nombre

VERSION_ALGORITMO = "PI-2"

PARAMETROS = {
    "grosor_marco": 25,            # px que se ignoran junto a cada borde del escaneo
    "delta": 2.5,                  # niveles de gris bajo el tope que siguen contando como meseta
    "ancho_linea": 7,              # semiancho (px) de la franja de la linea de marcador
    "hueco_max": 10,               # huecos de hasta 10 px dentro de la meseta se puentean
    "filtro": 5,                   # filtro de mediana 5 x 5
    "fraccion_central": 0.8,       # cuerdas que miden al menos el 80 % del ancho maximo
    "fraccion_minima": 0.3,        # si faltan cuerdas limpias, se aceptan hasta el 30 %
    "minimo_filas": 10,
    "delta_cruces": 6,             # comprobacion independiente: bordes a tope - 6
    "caida_borde": 40,             # caida mayor en 3 px = borde de pelicula o del escaneo, no dosis
    "fraccion_filas_cortadas": 0.2,
    "ventana_mm": 20.0,            # medio ancho de la ventana alrededor de la linea
    "margen_filas_mm": 3.0,        # margen por encima y por debajo de los clics
    "refinar_linea": True,
    "contraste_transito": 5.0,     # niveles minimos de la banda de transito para decidir el lado
    "transito_desde_mm": 12.0,     # la banda se mide lejos de la mancha: ahi la cola propia ya no cuenta
    "transito_hasta_mm": 50.0,
    "umbral_pelicula": 60.0,       # invertido: por debajo es fondo del escaner, marco o fuera de la imagen
    "tolerancia_mm": 1.0,
    "resolucion_escaneo_dpi": 600.0,         # la resolución del procedimiento de escaneo: la escala de los milímetros
    "resoluciones_de_editor_dpi": [72.0, 96.0],   # lo que un editor (Paint, Windows) escribe al guardar un recorte
    "tolerancia_dpi_relativa": 0.01,         # 599 / 599.999 (lo que escribe el Epson) cuentan como 600; 96.012 como 96
}

DPI_SI_FALTA = 600.0               # solo para dimensionar la ventana cuando no hay escala (resolución "otra")

# Lo que el motor dice cuando la zona analizada tiene píxeles sin dato (lo transparente, A.1). Una sola definición de cada texto.
NOTA_DE_TRANSPARENCIA = "; la zona analizada tiene zonas transparentes"
ESTADO_SIN_FILAS_POR_TRANSPARENCIA = "no medible: no quedan filas con la mancha a la vista" + NOTA_DE_TRANSPARENCIA


# ----------------------------------------------------------------------------- lectura

def leer_imagen(datos):
    """Bytes del archivo tal como se subió -> (gris, color, dpi, fecha_escaneo): gris y color BGR, la resolución en puntos por pulgada que el archivo DECLARA
    (o None si no la trae: no la que Pillow rellena; es solo informativa, la escala la fija `escala_mm`) y la fecha del escaneo como `datetime.date` (o None).
    Delega en `analisisImagenes.pelicula.leer_pelicula`, el ÚNICO lector (A.1): en 8 bits los arreglos son uint8 y exactamente los de siempre (`IMREAD_GRAYSCALE`
    e `IMREAD_COLOR`); en 16 bits, float32 en niveles de 8 bits (valor x 255 / 65535, con sus decimales). Se decodifica desde bytes (no desde ruta: `cv2.imread` no abre
    rutas con tildes en Windows y la imagen se guarda en la BD como bytes); el formato se reconoce por el contenido, no por la extensión (un `.jpeg` puede ser un TIFF); y se
    ignora la orientación EXIF (DD3). Una imagen con zonas transparentes YA NO se rechaza: la máscara de píxeles con dato la entrega `leer_pelicula` (`validos`) y
    `analizar(..., validos=)` la aplica."""
    pelicula = leer_pelicula(datos)
    gris, color = pelicula.en_bgr()
    return gris, color, pelicula.dpi, pelicula.fecha_escaneo


# ----------------------------------------------------------------------------- geometria

def angulo_canonico(p0, p1):
    """Grados a rotar (convencion de cv2.getRotationMatrix2D) para dejar vertical la linea p0-p1.
    Igual a la formula del notebook donde esa funciona; definido tambien con la linea horizontal.
    Resultado en (-90, 90]: no depende del orden de los clics."""
    dx, dy = float(p1[0] - p0[0]), float(p1[1] - p0[1])
    angulo = -np.degrees(np.arctan2(dx, dy))
    while angulo > 90.0:
        angulo -= 180.0
    while angulo <= -90.0:
        angulo += 180.0
    return angulo


def ventana_rotada(gris, color, puntos, angulo, P, tam_mm, medio_ancho_mm=None, canales=("gris", "R", "G", "B"), validos=None):
    """Recorta y rota SOLO la ventana alrededor de la linea: filas entre los clics +- margen,
    columnas +- ventana_mm. Devuelve las imagenes invertidas (mas dosis = mas alto) en float32,
    los clics en coordenadas de la ventana y la matriz ventana <- original. `validos` (bool, la forma de la imagen; por omision
    None = todo valido) marca los pixeles CON DATO: lo transparente (A.1) se trata igual que el marco, `inv = 0`: no es pelicula."""
    alto_img, ancho_img = gris.shape
    if validos is not None and validos.shape != gris.shape:
        raise ValueError("La mascara de pixeles validos no tiene la forma de la imagen.")
    c = ((puntos[0][0] + puntos[1][0]) / 2.0, (puntos[0][1] + puntos[1][1]) / 2.0)
    R = cv2.getRotationMatrix2D(c, angulo, 1.0)
    clics_r = cv2.transform(np.array(puntos, np.float64).reshape(-1, 1, 2), R).reshape(-1, 2)
    escala = (tam_mm if tam_mm else 25.4 / DPI_SI_FALTA)
    medio_ancho = int(round((medio_ancho_mm or P["ventana_mm"]) / escala))
    margen = int(round(P["margen_filas_mm"] / escala))
    x_l = float(np.mean(clics_r[:, 0]))
    x0 = int(np.floor(x_l)) - medio_ancho
    y0 = int(np.floor(clics_r[:, 1].min())) - margen
    ancho_v = 2 * medio_ancho + 1
    alto_v = int(np.ceil(clics_r[:, 1].max())) + margen - y0 + 1
    M = R.copy()
    M[0, 2] -= x0
    M[1, 2] -= y0
    # recorte del original que cubre la ventana (esquinas llevadas atras) -- para no rotar la pagina entera
    inversa = cv2.invertAffineTransform(M)
    esquinas = np.array([[0, 0], [ancho_v, 0], [0, alto_v], [ancho_v, alto_v]], np.float64).reshape(-1, 1, 2)
    orig = cv2.transform(esquinas, inversa).reshape(-1, 2)
    bx0 = max(0, int(np.floor(orig[:, 0].min())) - 3)
    by0 = max(0, int(np.floor(orig[:, 1].min())) - 3)
    bx1 = min(ancho_img, int(np.ceil(orig[:, 0].max())) + 4)
    by1 = min(alto_img, int(np.ceil(orig[:, 1].max())) + 4)
    if bx1 <= bx0 or by1 <= by0:
        raise ValueError("Los puntos quedan fuera de la imagen.")
    M_recorte = M.copy()
    M_recorte[:, 2] += M[:, :2] @ np.array([bx0, by0], np.float64)
    g = P["grosor_marco"]
    yy, xx = np.mgrid[by0:by1, bx0:bx1]
    marco = (xx < g) | (xx >= ancho_img - g) | (yy < g) | (yy >= alto_img - g)
    if validos is not None:
        marco |= ~validos[by0:by1, bx0:bx1]

    def preparar(canal):
        inv = (255.0 - canal[by0:by1, bx0:bx1].astype(np.float32))
        inv[marco] = 0.0          # el marco del fisico: el borde del escaneo no cuenta
        return cv2.warpAffine(inv, M_recorte, (ancho_v, alto_v), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)

    fuentes = {"gris": lambda: gris, "B": lambda: color[:, :, 0], "G": lambda: color[:, :, 1], "R": lambda: color[:, :, 2]}
    imagenes = {nombre: preparar(fuentes[nombre]()) for nombre in canales}
    clics_v = clics_r - np.array([x0, y0], np.float64)
    return imagenes, clics_v, M


# ----------------------------------------------------------------------------- la linea

def centro_de_linea_en_fila(fila, x_aprox, semiancho=15, contraste_minimo=15):
    x0 = int(round(x_aprox)) - semiancho
    if x0 < 0 or x0 + 2 * semiancho + 1 > len(fila):
        return None
    ventana = fila[x0:x0 + 2 * semiancho + 1].astype(float)
    base = np.linspace(np.median(ventana[:4]), np.median(ventana[-4:]), len(ventana))
    contraste = ventana - base
    k = int(np.argmax(contraste))
    if contraste[k] < contraste_minimo:
        return None
    media = contraste[k] / 2
    izq = k
    while izq > 0 and contraste[izq - 1] >= media:
        izq -= 1
    der = k
    while der < len(contraste) - 1 and contraste[der + 1] >= media:
        der += 1
    if izq == 0 or der == len(contraste) - 1:
        return None
    x_izq = (izq - 1) + (media - contraste[izq - 1]) / (contraste[izq] - contraste[izq - 1])
    x_der = der + (contraste[der] - media) / (contraste[der] - contraste[der + 1])
    return x0 + (x_izq + x_der) / 2


def refinar_linea(imagen, clics):
    (xa, ya), (xb, yb) = sorted(np.asarray(clics, float).tolist(), key=lambda p: p[1])
    filas, centros = [], []
    for y in range(max(0, int(np.ceil(ya))), min(imagen.shape[0] - 1, int(np.floor(yb))) + 1):
        x_aprox = xa + (xb - xa) * (y - ya) / (yb - ya) if yb != ya else xa
        c = centro_de_linea_en_fila(imagen[y], x_aprox)
        if c is not None:
            filas.append(y)
            centros.append(c)
    if len(filas) < 3:
        return None
    filas, centros = np.array(filas), np.array(centros)
    usadas = np.ones(len(filas), bool)
    for _ in range(5):
        pendiente, corte = np.polyfit(filas[usadas], centros[usadas], 1)
        residuo = centros - (pendiente * filas + corte)
        mad = np.median(np.abs(residuo[usadas] - np.median(residuo[usadas])))
        nuevas = np.abs(residuo) <= max(3 * 1.4826 * mad, 0.5)
        if not nuevas.any():                    # el recorte rechazaria TODAS las filas (centros en dos grupos que ninguna recta junta, p. ej. una tira transparente junto a la
            return None                         # linea): no hay linea que ajustar. Antes `np.polyfit` recibia un vector vacio y lanzaba TypeError (A.1, ronda 1, G-03)
        if np.array_equal(nuevas, usadas):
            break
        usadas = nuevas
    pendiente, corte = np.polyfit(filas[usadas], centros[usadas], 1)
    dispersion = float(np.std(centros[usadas] - (pendiente * filas[usadas] + corte)))
    return {"pendiente": float(pendiente), "corte": float(corte), "filas": filas, "centros": centros,
            "usadas": usadas, "dispersion": dispersion}


def referencia_de_la_linea(imagen, clics, P, separacion_maxima=5, filas_minimas=10, nota=""):
    """x de la línea en cada fila (la refinada por su perfil o, si no se puede, la de los clics), la línea, su incertidumbre en píxeles y el mensaje de cómo se ubicó.
    `nota` (por omisión vacía: la conducta de siempre) se agrega a los dos mensajes de línea NO ubicada; el análisis la usa para decir que la zona tiene zonas transparentes."""
    alto = imagen.shape[0]
    clics = np.asarray(clics, float)
    x_clics = np.full(alto, float(np.mean(clics[:, 0])))
    if not P["refinar_linea"]:
        return x_clics, None, 1.0, "linea ubicada con los clics"
    linea = refinar_linea(imagen, clics)
    if linea is None or np.sum(linea["usadas"]) < filas_minimas:
        return x_clics, linea, 1.0, "no se pudo refinar la linea: se usan los clics" + nota
    x_ref = linea["pendiente"] * np.arange(alto) + linea["corte"]
    tramo = slice(max(0, int(clics[:, 1].min())), min(alto, int(clics[:, 1].max()) + 1))
    if np.max(np.abs(x_ref[tramo] - x_clics[tramo])) > separacion_maxima:
        return x_clics, linea, 1.0, "la linea refinada se aleja mas de 5 px de los clics: se usan los clics" + nota
    u = linea["dispersion"] / np.sqrt(max(np.sum(linea["usadas"]) / 8, 1))
    return x_ref, linea, float(u), "linea refinada por su perfil"


# ----------------------------------------------------------------------------- la meseta

def corridas(mascara, hueco_max):
    indices = np.where(mascara)[0]
    if len(indices) == 0:
        return np.array([], int), np.array([], int)
    cortes = np.where(np.diff(indices) > hueco_max + 1)[0]
    return np.r_[indices[0], indices[cortes + 1]], np.r_[indices[cortes], indices[-1]]


def mesetas_por_fila(imagen, x_ref, P):
    """Meseta de cada fila con todo lo necesario para decidir si la fila sirve."""
    suave = median_filter(imagen, size=P["filtro"]) if P["filtro"] else imagen
    alto, ancho = suave.shape
    al = P["ancho_linea"]
    fuera_linea = np.ones((alto, ancho), bool)
    for y in range(alto):
        x = int(round(x_ref[y]))
        fuera_linea[y, max(0, x - al):x + al + 1] = False
    tope = float(np.max(suave[fuera_linea]))
    umbral = tope - P["delta"]
    n = alto
    inicio = np.full(n, -1); fin = np.full(n, -1)
    x_izq = np.full(n, np.nan); x_der = np.full(n, np.nan)
    toca = np.zeros(n, bool); cortada = np.zeros(n, bool); oculto = np.zeros(n, bool)
    for y in range(alto):
        f = suave[y]
        mascara = f >= umbral
        x = int(round(x_ref[y]))
        a, b = max(0, x - al), min(ancho, x + al + 1)
        llena = bool(np.any(mascara[max(0, a - 3):a]) and np.any(mascara[b:b + 3]))
        mascara[a:b] = llena
        inis, fins = corridas(mascara, P["hueco_max"])
        if len(inis) == 0:
            continue
        k = int(np.argmax(fins - inis))
        i, j = int(inis[k]), int(fins[k])
        inicio[y], fin[y] = i, j
        toca[y] = i == 0 or j == ancho - 1
        oculto[y] = (not llena) and ((a - 3 <= j + 1 <= a) or (b <= i <= b + 2))

        def vecinos(desde, paso):
            k2, vals = desde, []
            while 0 <= k2 < ancho and len(vals) < 3:
                if not (a <= k2 < b):
                    vals.append(f[k2])
                k2 += paso
            return vals
        izq, der = vecinos(i - 1, -1), vecinos(j + 1, +1)
        cortada[y] = bool((izq and min(izq) < tope - P["caida_borde"]) or (der and min(der) < tope - P["caida_borde"]))
        # bordes subpixel al umbral (si el vecino es la franja de la linea, el borde queda en el pixel)
        if i > 0 and not (a <= i - 1 < b) and f[i] != f[i - 1]:
            x_izq[y] = (i - 1) + (umbral - f[i - 1]) / (f[i] - f[i - 1])
        else:
            x_izq[y] = i - 0.5
        if j < ancho - 1 and not (a <= j + 1 < b) and f[j] != f[j + 1]:
            x_der[y] = j + (f[j] - umbral) / (f[j] - f[j + 1])
        else:
            x_der[y] = j + 0.5
    return {"suave": suave, "tope": tope, "umbral": umbral, "inicio": inicio, "fin": fin,
            "x_izq": x_izq, "x_der": x_der, "toca": toca, "cortada": cortada, "oculto": oculto}


def filas_utiles(m, P):
    """Cuerdas centrales (bloque continuo alrededor de la mas ancha) con los dos bordes visibles;
    si quedan pocas, cuerdas mas cortas (sus bordes se alejan de la linea)."""
    inicio, fin, oculto = m["inicio"], m["fin"], m["oculto"]
    ancho = np.where(inicio >= 0, fin - inicio + 1, 0)
    if np.max(ancho) == 0:
        return np.array([], int), ancho
    candidatas = np.where(ancho >= P["fraccion_central"] * np.max(ancho))[0]
    inis, fins = corridas(np.isin(np.arange(len(ancho)), candidatas), 3)
    mas_ancha = int(np.argmax(ancho))
    k = int(np.where((inis <= mas_ancha) & (fins >= mas_ancha))[0][0])
    bloque = np.arange(inis[k], fins[k] + 1)
    filas = bloque[(ancho[bloque] > 0) & ~oculto[bloque]]
    if len(filas) < P["minimo_filas"]:
        filas = np.where((inicio >= 0) & ~oculto & (ancho >= P["fraccion_minima"] * np.max(ancho)))[0]
    return filas, ancho


def medir_perfil(imagen, x_ref, P, con_transparencia=False):
    """El perfil de una capa. `con_transparencia` (por omisión False: la conducta de siempre) dice que la zona analizada tiene píxeles sin dato: si no quedan filas con la
    mancha a la vista, el motivo lo dice en vez de culpar a la línea (A.1, ronda 1, G-04)."""
    m = mesetas_por_fila(imagen, x_ref, P)
    filas, ancho = filas_utiles(m, P)
    r = {"m": m, "filas": filas, "ancho": ancho, "tope": m["tope"]}
    alto = imagen.shape[0]
    if len(filas) < P["minimo_filas"]:
        r["estado"] = ESTADO_SIN_FILAS_POR_TRANSPARENCIA if con_transparencia else "no medible: la linea tapa el borde de la meseta"
        return r
    if np.any(m["toca"][filas]) or filas.min() == 0 or filas.max() == alto - 1:
        r["estado"] = "no medible: la mancha se sale de la zona marcada"
        return r
    if np.mean(m["cortada"][filas]) > P["fraccion_filas_cortadas"]:
        r["estado"] = "no medible: la mancha esta cortada por el borde de la pelicula"
        return r
    centros = (m["x_izq"][filas] + m["x_der"][filas]) / 2.0
    desfases = x_ref[filas] - centros
    # comprobacion independiente: bordes a tope - delta_cruces
    nivel = m["tope"] - P["delta_cruces"]
    otros = []
    for y in filas:
        f = m["suave"][y]
        i, j = m["inicio"][y], m["fin"][y]
        while i > 0 and f[i - 1] >= nivel:
            i -= 1
        while j < len(f) - 1 and f[j + 1] >= nivel:
            j += 1
        if i == 0 or j == len(f) - 1:
            continue
        xi = (i - 1) + (nivel - f[i - 1]) / (f[i] - f[i - 1])
        xd = j + (f[j] - nivel) / (f[j] - f[j + 1])
        otros.append(x_ref[y] - (xi + xd) / 2.0)
    n_eff = max(len(filas) / 8.0, 1.0)
    r.update({"estado": "ok", "centros": centros, "desfases": desfases,
              "desfase_px": float(np.median(desfases)), "dispersion_px": float(np.std(desfases)),
              "u_filas_px": float(1.2533 * np.std(desfases) / np.sqrt(n_eff)),
              "desfase_cruces_px": float(np.median(otros)) if otros else float("nan")})
    return r


# ----------------------------------------------------------------------------- transito y signo

def lado_del_transito(imagen_larga, desplazamiento_x, clics_y, r, P, tam_mm):
    """La banda de transito corre a lo largo del cateter hasta el borde de la pelicula, del lado por
    donde entra la fuente. Se mide LEJOS de la mancha (entre transito_desde_mm y transito_hasta_mm),
    donde la cola de la propia mancha ya no cuenta: las filas del cateter (las cuerdas centrales)
    contra las filas de pelicula ENTRE LOS CLICS que quedan por encima y por debajo de la mancha
    (a mas de un radio), cada grupo por separado. Hay banda de un lado si sobresale al menos
    `contraste_transito` niveles sobre los DOS grupos; el lado se decide solo si del otro lado no hay
    banda (o no hay pelicula para mirar). Solo pixeles de pelicula (fuera: marco, fondo del escaner).
    Devuelve ('derecha' | 'izquierda' | None, detalle por lado). El detalle de un lado medible trae, ademas de los
    niveles y el contraste, los LIMITES de la region medida (`columnas`, `filas_banda`, `filas_arriba`, `filas_abajo`,
    `desde_px`, `hasta_px`, `desde_mm`, `hasta_mm`: B.1); un lado sin pelicula suficiente sigue siendo None. Los milimetros son None
    sin escala (`tam_mm` None, resolucion 'otra'): la escala de reserva solo dimensiona la banda en columnas y no da milimetros que
    nadie pueda interpretar; las distancias en pixeles al centro de la mancha se dan siempre."""
    if r.get("estado") != "ok":
        return None, {}
    escala = tam_mm if tam_mm else 25.4 / DPI_SI_FALTA
    filas = r["filas"]
    centro = float(np.median(r["centros"])) + desplazamiento_x
    radio = float(np.median(r["m"]["fin"][filas] - r["m"]["inicio"][filas])) / 2.0
    alto, ancho = imagen_larga.shape
    desde = max(int(round(P["transito_desde_mm"] / escala)), int(round(4 * radio)))
    hasta = int(round(P["transito_hasta_mm"] / escala))
    y_a, y_b = int(np.ceil(min(clics_y))), int(np.floor(max(clics_y)))
    arriba = np.arange(max(0, y_a), max(0, int(filas.min() - radio)))
    abajo = np.arange(min(alto, int(filas.max() + radio) + 1), min(alto, y_b + 1))
    pelicula = imagen_larga > P["umbral_pelicula"]
    detalle = {}
    for lado, cols in (("izquierda", np.arange(max(0, int(centro) - hasta), max(0, int(centro) - desde))),
                       ("derecha", np.arange(min(ancho, int(centro) + desde), min(ancho, int(centro) + hasta)))):
        def mediana(filas_grupo):
            if len(filas_grupo) < 10 or len(cols) < 50:
                return None
            sub, msk = imagen_larga[np.ix_(filas_grupo, cols)], pelicula[np.ix_(filas_grupo, cols)]
            return float(np.median(sub[msk])) if msk.sum() >= 500 else None
        banda, sup, inf = mediana(filas), mediana(arriba), mediana(abajo)
        if banda is None or (sup is None and inf is None):
            detalle[lado] = None
            continue
        contrastes = [banda - v for v in (sup, inf) if v is not None]
        c0, c1 = int(cols[0]), int(cols[-1]) + 1            # [c0, c1): las columnas de la banda en la ventana larga (las que de verdad se midieron)
        cerca, lejos = (int(centro) - c1, int(centro) - c0) if lado == "izquierda" else (c0 - int(centro), c1 - int(centro))
        detalle[lado] = {"banda": banda, "arriba": sup, "abajo": inf, "contraste": float(min(contrastes)),
                         # B.1: los LIMITES de la banda, para dibujarla sin repetir la regla en la pagina. Columnas en las coordenadas de la ventana de analisis (la que se dibuja: la
                         # larga lleva `desplazamiento_x` columnas de mas a la izquierda); filas de cada grupo (las dos ventanas comparten filas), None si ese grupo no dio mediana; y la
                         # extension desde el centro de la mancha, en px y (solo con escala) en mm. Ningun numero anterior cambia.
                         "columnas": (c0 - desplazamiento_x, c1 - desplazamiento_x),
                         "filas_banda": (int(filas.min()), int(filas.max()) + 1),
                         "filas_arriba": (int(arriba[0]), int(arriba[-1]) + 1) if sup is not None else None,
                         "filas_abajo": (int(abajo[0]), int(abajo[-1]) + 1) if inf is not None else None,
                         "desde_px": int(cerca), "hasta_px": int(lejos),
                         "desde_mm": float(cerca * tam_mm) if tam_mm else None, "hasta_mm": float(lejos * tam_mm) if tam_mm else None}
    umbral = P["contraste_transito"]

    def hay_banda(lado):
        d = detalle.get(lado)
        return d is not None and d["contraste"] >= umbral

    def sin_banda(lado):
        d = detalle.get(lado)
        return d is None or d["contraste"] < umbral / 2
    if hay_banda("derecha") and sin_banda("izquierda"):
        return "derecha", detalle
    if hay_banda("izquierda") and sin_banda("derecha"):
        return "izquierda", detalle
    return None, detalle


# ----------------------------------------------------------------------------- todo junto

def pixeles_sin_dato_en_la_ventana(validos, M, forma):
    """Cuántos píxeles de la ventana de análisis NO tienen dato (lo transparente, A.1). `validos`: la máscara de la imagen entera (o None: 0), `M`: la matriz ventana <- imagen
    que devuelve `ventana_rotada`, `forma`: (alto, ancho) de la ventana. Lo que cae fuera de la imagen no cuenta (es el marco, no una transparencia)."""
    if validos is None:
        return 0
    llevada = cv2.warpAffine(np.ascontiguousarray(validos, dtype=bool).view(np.uint8), M, (forma[1], forma[0]), flags=cv2.INTER_NEAREST,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=1)
    return int(np.count_nonzero(llevada == 0))


def analizar(gris, color, dpi, puntos, parametros=None, validos=None):
    """El analisis completo. `puntos` en pixeles de la imagen tal como se subio. `validos`: la mascara de pixeles con dato que entrega `leer_pelicula` (A.1;
    por omision None = todo valido, la conducta de siempre): lo transparente no es pelicula, y si toca la mancha o sus bordes el perfil dice "no medible"."""
    P = dict(PARAMETROS, **(parametros or {}))
    tam_mm = escala_mm(dpi, P)
    angulo = angulo_canonico(puntos[0], puntos[1])
    imagenes, clics_v, M = ventana_rotada(gris, color, puntos, angulo, P, tam_mm, validos=validos)
    con_transparencia = pixeles_sin_dato_en_la_ventana(validos, M, imagenes["gris"].shape) > 0
    x_ref, linea, u_linea, mensaje = referencia_de_la_linea(imagenes["gris"], clics_v, P, nota=NOTA_DE_TRANSPARENCIA if con_transparencia else "")
    perfiles = {nombre: medir_perfil(imagenes[nombre], x_ref, P, con_transparencia) for nombre in ("gris", "R", "G", "B")}
    larga, _, _ = ventana_rotada(gris, color, puntos, angulo, P, tam_mm,
                                 medio_ancho_mm=P["transito_hasta_mm"] + 2.0, canales=("gris",), validos=validos)
    desplazamiento = (larga["gris"].shape[1] - imagenes["gris"].shape[1]) // 2
    lado, contrastes = lado_del_transito(larga["gris"], desplazamiento, clics_v[:, 1], perfiles["gris"], P, tam_mm)
    return {"version": VERSION_ALGORITMO, "parametros": P, "dpi": dpi, "clase_resolucion": clase_resolucion(dpi, P),
            "tamano_pixel_mm": tam_mm, "angulo": angulo, "matriz_ventana": M, "imagenes": imagenes, "clics_ventana": clics_v,
            "x_ref": x_ref, "linea": linea, "u_linea_px": u_linea, "mensaje_linea": mensaje,
            "perfiles": perfiles, "lado_transito": lado, "contrastes_transito": contrastes}


def incertidumbre_px(resultado, perfil="gris"):
    """Incertidumbre expandida (k = 2) del desfase de un perfil, en PÍXELES: dispersión de las filas, ajuste de la
    línea y diferencia entre los dos métodos de borde (rectangular, ÷√3). Es la ÚNICA definición de la suma:
    `resumen` la pasa a milímetros con la escala y PI.3 la guarda en píxeles (DD4). None si el perfil no se mide."""
    r = resultado["perfiles"][perfil]
    if r["estado"] != "ok":
        return None
    u_filas = r["u_filas_px"]
    u_linea = resultado["u_linea_px"]
    u_metodo = (abs(r["desfase_px"] - r["desfase_cruces_px"]) / np.sqrt(3)
                if np.isfinite(r["desfase_cruces_px"]) else u_filas)
    return 2 * float(np.sqrt(u_filas**2 + u_linea**2 + u_metodo**2))


CAPAS_GUARDADAS = (("gris", "gris"), ("R", "r"), ("G", "g"), ("B", "b"))   # (perfil del motor, sufijo de la columna)


def valores_medidos(resultado):
    """LO QUE SE GUARDA (PI.3): la ÚNICA definición de los valores medidos de un análisis, con las claves iguales a
    las columnas de `braqui_posicion_inicial`. Por perfil (gris y capas r, g, b): `estado_*`, `desfase_*_px` y
    `desfase_*_mm` (px es None si el perfil no se mide; mm = px * `tamano_pixel_mm`, SIN redondear, y None si falta px
    o la escala). Del gris además `incertidumbre_gris_px` (k = 2), `dispersion_gris_px` y `filas_gris`; y
    `tamano_pixel_mm` y `lado_transito`. Todo en tipos de Python (listo para SQLite y JSON). Sentido, veredicto y
    avisos NO se guardan: se construyen al mostrarlos (`resumen`)."""
    tam = resultado["tamano_pixel_mm"]
    valores = {"tamano_pixel_mm": tam, "lado_transito": resultado["lado_transito"]}
    for nombre, sufijo in CAPAS_GUARDADAS:
        p = resultado["perfiles"][nombre]
        px = float(p["desfase_px"]) if p["estado"] == "ok" else None
        valores[f"estado_{sufijo}"] = p["estado"]
        valores[f"desfase_{sufijo}_px"] = px
        valores[f"desfase_{sufijo}_mm"] = px * tam if (px is not None and tam is not None) else None
    g = resultado["perfiles"]["gris"]
    ok = g["estado"] == "ok"
    valores.update({
        "incertidumbre_gris_px": incertidumbre_px(resultado, "gris"),
        "dispersion_gris_px": float(g["dispersion_px"]) if ok else None,
        "filas_gris": int(len(g["filas"])) if ok else None,
    })
    return valores


def nota_de_resolucion(resultado):
    """Nota (texto o None) sobre lo que la imagen DECLARA frente al procedimiento de escaneo. Un editor (72 o 96) o la
    falta de dato se anotan (solo en pantalla: se usa la resolución del escaneo); coincidir con el procedimiento no se
    anota. (La comprobación por el ancho de la meseta saturada quedó como deuda, DP-143.)"""
    escaneo = resultado["parametros"]["resolucion_escaneo_dpi"]
    clase = resultado["clase_resolucion"]
    if clase == "editor":
        return (f"la imagen declara {resultado['dpi']:g} dpi (lo escribe el editor al guardar); "
                f"se usa la resolucion del escaneo: {escaneo:g} dpi")
    if clase == "sin_dato":
        return f"la imagen no declara resolucion; se usa la resolucion del escaneo: {escaneo:g} dpi"
    return None


def interpretar(estado, desfase_px, incertidumbre_px, tamano_pixel_mm, lado_transito, dpi, P):
    """De lo que se GUARDA (el estado del perfil, su desfase y su incertidumbre en pixeles, la escala, el lado del
    transito, la resolucion declarada y los parametros) a lo que se MUESTRA: milimetros, sentido fisico, veredicto y aviso.
    Es la UNICA definicion de esas cuatro cosas (PI.3): la usan `resumen` (la pantalla) y el texto breve del servicio (la
    tabla de registros y los PDF), asi que no pueden decir cosas distintas con los mismos numeros. Solo lee escalares: no
    hace falta el analisis completo para volver a interpretarlo."""
    if estado != "ok":
        return {"veredicto": "No medible"}
    if tamano_pixel_mm is None:
        escaneo = P["resolucion_escaneo_dpi"]
        return {"desfase_mm": None, "veredicto": "No medible", "aviso": (
            f"la imagen declara {dpi:g} dpi y el procedimiento es de {escaneo:g} dpi: parece escaneada a "
            f"otra resolucion; escanee la pelicula a {escaneo:g} dpi. Sin milimetros ni veredicto")}
    d_mm = desfase_px * tamano_pixel_mm
    if lado_transito == "derecha":
        fisico = d_mm
    elif lado_transito == "izquierda":
        fisico = -d_mm
    else:
        fisico = None
    if fisico is None:
        sentido = ("a la izquierda" if d_mm > 0 else "a la derecha") + " de la linea en la imagen (no se distingue la banda de transito)"
    else:
        sentido = "antes de la marca" if fisico < 0 else "despues de la marca"
    return {"desfase_mm": d_mm, "desfase_fisico_mm": fisico, "sentido": sentido, "U_mm": incertidumbre_px * tamano_pixel_mm,
            "U_px": incertidumbre_px, "veredicto": "Cumple" if abs(d_mm) <= P["tolerancia_mm"] else "No cumple"}


def resumen(resultado, perfil="gris"):
    """Lo que se MUESTRA (y lo que imprimen los PDF): se construye, no se guarda (DA del 09-09). Los milimetros, el sentido
    y el veredicto salen de `interpretar`, la unica definicion; aqui solo se completa con lo que necesita la pantalla."""
    r = resultado["perfiles"][perfil]
    tam = resultado["tamano_pixel_mm"]
    P = resultado["parametros"]
    if r["estado"] != "ok":
        return {"estado": r["estado"], **interpretar(r["estado"], None, None, tam, resultado["lado_transito"],
                                                     resultado["dpi"], P)}
    salida = {"estado": "ok", "desfase_px": r["desfase_px"], "filas": int(len(r["filas"]))}
    salida.update(interpretar("ok", r["desfase_px"], incertidumbre_px(resultado, perfil), tam, resultado["lado_transito"],
                              resultado["dpi"], P))
    if tam is not None:
        salida["dispersion_mm"] = r["dispersion_px"] * tam
        salida["nota_resolucion"] = nota_de_resolucion(resultado)
    return salida


# ----------------------------------------------------------------------------- placa sintetica

def placa_sintetica(desfase_mm, ancho_x_mm, ancho_y_mm, saturacion, dpi=600.0, ruido=1.2, semilla=0,
                    alto=467, ancho=1328):
    """Tu placa sintetica original, con deslizadores: gaussiana eliptica (anchos = sigma en mm) que se
    recorta en `saturacion` (fraccion del pico), linea de marcador tan oscura como la meseta, ruido y JPEG.
    Devuelve (gris, color, dpi, puntos) listo para `analizar`."""
    rng = np.random.default_rng(semilla)
    tam = 25.4 / dpi
    x_l, y_c = 190.0, 216.0
    xs = x_l - desfase_mm / tam
    X, Y = np.meshgrid(np.arange(ancho), np.arange(alto))
    f = np.exp(-((X - xs) ** 2 / (2 * (ancho_x_mm / tam) ** 2) + (Y - y_c) ** 2 / (2 * (ancho_y_mm / tam) ** 2)))
    s = 120 + 135 * np.minimum(f, saturacion) / saturacion + rng.normal(0, ruido, f.shape)
    s[20:450, 186:195] = 255
    escaneo = (255 - np.clip(s, 0, 255)).astype(np.uint8)
    _, comprimida = cv2.imencode(".jpg", escaneo, [cv2.IMWRITE_JPEG_QUALITY, 92])
    gris = cv2.imdecode(comprimida, cv2.IMREAD_GRAYSCALE)
    return gris, cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR), dpi, [(192, 56), (189, 377)]


def barrido_sintetico(ancho_x_mm, ancho_y_mm, saturacion, desfases_mm=(-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5)):
    """Real contra medido para la grafica de la pestana sintetica."""
    puntos = []
    for d in desfases_mm:
        g, c, dpi, pts = placa_sintetica(d, ancho_x_mm, ancho_y_mm, saturacion)
        r = analizar(g, c, dpi, pts)
        s = resumen(r)
        puntos.append((float(d), s.get("desfase_mm") if s["estado"] == "ok" else None))
    return puntos
