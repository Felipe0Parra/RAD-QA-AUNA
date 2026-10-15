"""B.3 (PLAN_ANALISIS_PELICULAS_08-10.md): lo que el motor de la POSICION INICIAL de braquiterapia lee, y lo que NO. Modulo auxiliar de pruebas (no empieza por `test_`: pytest no lo coleccio-
na) de `test_b3_braqui_no_depende_del_piso.py`.

QUE LEE `analizar` (medido leyendo `analisisImagenes/posicion_inicial_braqui.py`): los desfases de gris, R, G y B se miden SOLO dentro de la ventana de `ventana_rotada` (la imagen girada para dejar
la linea vertical: +-`ventana_mm` = 20 mm alrededor de la linea y las filas entre los clics +- `margen_filas_mm` = 3 mm), y el lado del transito se decide en una SEGUNDA ventana, la «larga» (+-(`tran-
sito_hasta_mm` + 2) = 52 mm, solo gris), con los pixeles que son pelicula. Nada mas de la imagen entra en la medida (el piso NO se usa: `piso_de_pelicula` vive en `pelicula.py` y nadie del braqui lo
llama).

Este modulo da (la ventana declarada y lo que se pinta NO usan el motor; las escenas lo llaman, con `Escena.medir`, para analizar tal como lo hace la aplicacion, y `lo_medido_de_los_desfases` recibe el que le pasa la prueba):
  * la ventana DECLARADA por los parametros y los clics (un rectangulo girado): `ventana_declarada`, `mascara_dentro`, `franjas_del_transito`: de ahi sale lo que cae «fuera» (se pinta con un margen
    de `MARGEN_PX`, porque el giro interpola: sin margen el borde de la ventana si ve lo de fuera, y `test_b3` lo mide);
  * pintar de blanco, de negro o con el nivel de la pelicula (`pintar`, `niveles_de_la_pelicula`);
  * el FONDO LEJANO inerte (`zona_protegida`, `cambiar_el_fondo_lejano`): cambiar el nivel de la pelicula solo en los pixeles que el motor no puede leer (lejos de la meseta y de la linea, y muy por
    debajo del umbral de la meseta de su capa);
  * comparar dos analisis bit a bit (`diferencias`) y lo medido de los desfases (`lo_medido_de_los_desfases`);
  * las escenas: una placa real o sintetica con sus clics, sola o en una pagina entera del escaner (`en_pagina`);
  * las ventanas que `analizar` arma DE VERDAD (`ventanas_que_arma_analizar`: una espia sobre `ventana_rotada` del motor, que no cambia lo que devuelve): la prueba de la ventana larga mira la que usa la
    aplicacion, no una que arme con su propia cuenta.
"""
import math
from dataclasses import dataclass
from unittest import mock

import cv2
import numpy as np

CAPAS = ("gris", "R", "G", "B")
MARGEN_PX = 3                          # lo de fuera se pinta a 3 px de la ventana: el giro (bilineal) alimenta el borde con los pixeles de afuera hasta ~1.4 px, y la ventana real esta a ~1.1 px de la declarada
FONDO_DE_LA_PAGINA = 250               # el blanco del escaner (el mismo de los generadores de PF.0)
PAGINA_PX = (6600, 5100)               # (alto, ancho) de la pagina entera del escaner (EPSON031)
DISTANCIA_A_LA_MESETA_PX = 150         # el fondo lejano empieza a 6.4 mm de la meseta de cualquier capa (y de las filas que se miden)
DISTANCIA_A_LA_LINEA_PX = 80           # ... y a 3.4 mm de la linea
HOLGURA_BAJO_EL_TOPE = 20.0            # solo se toca la pelicula que esta 20 niveles (invertidos) por debajo del tope de su capa (el umbral de la meseta es tope - 2.5)
TOPE_DEL_FONDO_CAMBIADO = 30.0         # y se deja siempre 30 niveles por debajo del tope: ningun pixel llega al umbral de la meseta (tope - 2.5)
FILAS_POR_BLOQUE = 512                 # el fondo lejano se cambia por bloques de filas: una pagina entera (6600 x 5100) no pide cientos de MB de temporales
LADOS = ("izquierda", "derecha")
UMBRAL_DE_PELICULA = 60.0              # el umbral de pelicula del motor (invertido: por debajo es fondo del escaner): para elegir el nivel de la pelicula con que se pinta
GROSOR_DEL_MARCO_PX = 25               # el marco del escaner que el motor pone en cero


@dataclass(frozen=True)
class LoDeclarado:
    """La ventana de medida tal como el plan y los parametros la DECLARAN (mm y dpi). Son constantes de esta prueba, NO se leen del motor: si un cambio del motor (un parametro, una cuenta) ensancha la
    ventana, la ventana real se aleja de la declarada y la prueba lo ve, y lo que se pinta «fuera» sigue siendo lo que de verdad queda fuera."""
    ventana_mm: float                  # +- alrededor de la linea, para los desfases
    transito_mm: float                 # +- alrededor de la linea, para el lado del transito (transito_hasta_mm = 50 mas 2)
    margen_filas_mm: float             # por encima y por debajo de los clics
    resolucion_dpi: float              # la del procedimiento de escaneo


LO_DECLARADO = LoDeclarado(20.0, 52.0, 3.0, 600.0)


# ============================================================================================================================ la ventana DECLARADA
@dataclass(frozen=True)
class Rectangulo:
    """Un rectangulo girado de la imagen ORIGINAL: `centro` (x, y), `d` la direccion de la linea, `n` la perpendicular, y los semiejes en px (`mitad_larga` a lo largo de la linea, `mitad_ancha` a lo ancho)."""
    centro: tuple
    d: tuple
    n: tuple
    mitad_larga: float
    mitad_ancha: float

    def esquinas(self, margen=0.0):
        """Las 4 esquinas (x, y), en orden de contorno, del rectangulo ensanchado `margen` px por los cuatro lados."""
        c, d, n = np.array(self.centro), np.array(self.d), np.array(self.n)
        hl, hw = self.mitad_larga + margen, self.mitad_ancha + margen
        return np.array([c - hl * d - hw * n, c - hl * d + hw * n, c + hl * d + hw * n, c + hl * d - hw * n])


def ventana_declarada(clics, medio_ancho_mm, margen_filas_mm=LO_DECLARADO.margen_filas_mm, resolucion_dpi=LO_DECLARADO.resolucion_dpi):
    """La ventana que `analizar` DECLARA medir, sacada de lo declarado y de los clics (sin el motor): el rectangulo girado cuyo eje largo es la linea de los clics, con +- `medio_ancho_mm` a lo ancho
    (la escala es la del procedimiento de escaneo) y las filas entre los clics +- `margen_filas_mm` a lo largo."""
    p0, p1 = np.asarray(clics[0], float), np.asarray(clics[1], float)
    v = p1 - p0
    largo = float(np.hypot(v[0], v[1]))
    d = v / largo
    escala = 25.4 / resolucion_dpi
    margen = round(margen_filas_mm / escala)
    return Rectangulo(tuple((p0 + p1) / 2.0), (float(d[0]), float(d[1])), (float(-d[1]), float(d[0])), largo / 2.0 + margen, float(round(medio_ancho_mm / escala)))


def ventana_corta(clics, declarado=LO_DECLARADO):
    """La ventana de los desfases (gris, R, G y B): +- 20 mm."""
    return ventana_declarada(clics, declarado.ventana_mm, declarado.margen_filas_mm, declarado.resolucion_dpi)


def ventana_larga(clics, declarado=LO_DECLARADO):
    """La ventana del transito (solo gris): +- 52 mm."""
    return ventana_declarada(clics, declarado.transito_mm, declarado.margen_filas_mm, declarado.resolucion_dpi)


def esquinas_de_la_ventana_real(matriz, forma):
    """Las 4 esquinas (x, y) de la ORIGINAL que corresponden a los pixeles de las 4 esquinas de una ventana de `forma` (alto, ancho) que el motor armo con `matriz` (original -> ventana)."""
    alto, ancho = forma
    inversa = cv2.invertAffineTransform(np.asarray(matriz, np.float64))
    return np.array([inversa @ np.array([x, y, 1.0]) for x, y in ((0, 0), (ancho - 1, 0), (ancho - 1, alto - 1), (0, alto - 1))])


def desviacion_de_la_ventana(esquinas_reales, rectangulo):
    """La mayor distancia (px) de una esquina real a la esquina declarada mas cercana: la ventana que el motor usa es la declarada a ~1 px (el redondeo de floor/ceil de su recorte)."""
    declaradas = rectangulo.esquinas()
    return float(max(min(math.hypot(*(r - e)) for e in declaradas) for r in esquinas_reales))


def mascara_dentro(rectangulo, forma, margen=0.0):
    """Mascara booleana (forma de la imagen) de los pixeles que caen dentro del rectangulo ensanchado `margen` px (subpixel: el contorno se rasteriza con 4 bits de fraccion)."""
    m = np.zeros(forma, np.uint8)
    cv2.fillConvexPoly(m, np.round(rectangulo.esquinas(margen) * 16.0).astype(np.int32), 1, lineType=cv2.LINE_8, shift=4)
    return m > 0


def marco_del_motor(forma, grosor=GROSOR_DEL_MARCO_PX):
    """Los pixeles que `ventana_rotada` pone en cero (el marco del escaner): a `grosor` px del borde de la imagen."""
    m = np.zeros(forma, bool)
    m[:grosor, :] = True
    m[-grosor:, :] = True
    m[:, :grosor] = True
    m[:, -grosor:] = True
    return m


def fuera_de_las_dos_ventanas(clics, forma, margen=MARGEN_PX, declarado=LO_DECLARADO):
    """Lo que cae fuera de la UNION de las dos ventanas DECLARADAS (la larga contiene a la corta) a `margen` px de ellas."""
    return ~(mascara_dentro(ventana_corta(clics, declarado), forma, margen) | mascara_dentro(ventana_larga(clics, declarado), forma, margen))


def franjas_del_transito(clics, forma, matriz, margen=MARGEN_PX, declarado=LO_DECLARADO):
    """{'izquierda': mascara, 'derecha': mascara, 'ambas': mascara}: lo que cae DENTRO de la ventana larga declarada y FUERA de la corta declarada (a `margen` px de ella), repartido en el lado izquierdo
    o derecho de la linea. «Izquierda» y «derecha» son las del marco del motor (la imagen girada para dejar la linea vertical): `matriz` es la `matriz_ventana` del analisis (su primera fila es la
    direccion de «derecha»)."""
    ambas = mascara_dentro(ventana_larga(clics, declarado), forma, 0.0) & ~mascara_dentro(ventana_corta(clics, declarado), forma, margen)
    ys, xs = np.nonzero(ambas)
    cx, cy = ventana_corta(clics, declarado).centro
    ex, ey = float(matriz[0][0]), float(matriz[0][1])
    hacia_la_derecha = (xs - cx) * ex + (ys - cy) * ey > 0
    izquierda = np.zeros(forma, bool)
    derecha = np.zeros(forma, bool)
    izquierda[ys[~hacia_la_derecha], xs[~hacia_la_derecha]] = True
    derecha[ys[hacia_la_derecha], xs[hacia_la_derecha]] = True
    return {"izquierda": izquierda, "derecha": derecha, "ambas": ambas}


# ============================================================================================================================ pintar
def pintar(gris, color, mascara, niveles):
    """Copias de (gris, color) con los pixeles de `mascara` pintados: `niveles` = {'gris': n, 'B': n, 'G': n, 'R': n} (niveles de 8 bits; el color es BGR)."""
    g2, c2 = gris.copy(), color.copy()
    np.copyto(g2, np.asarray(niveles["gris"], g2.dtype), where=mascara)                     # copyto con `where`: una asignacion con mascara sobre la pagina entera pide ~500 MB de indices
    np.copyto(c2, np.asarray([niveles["B"], niveles["G"], niveles["R"]], c2.dtype), where=mascara[:, :, None])
    return g2, c2


def niveles_de(valor):
    return {"gris": valor, "B": valor, "G": valor, "R": valor}


BLANCO = niveles_de(255)
NEGRO = niveles_de(0)
_FUENTE = {"gris": lambda g, c: g, "B": lambda g, c: c[:, :, 0], "G": lambda g, c: c[:, :, 1], "R": lambda g, c: c[:, :, 2]}


def niveles_de_la_pelicula(gris, color, resultado, paso=7):
    """El nivel de la PELICULA de cada capa, tomado de la propia imagen: la mediana (de una muestra de 1 pixel de cada `paso` x `paso`) de los pixeles que son pelicula sin dosis -invertidos entre
    el umbral de pelicula y su tope menos `HOLGURA_BAJO_EL_TOPE`-, es decir, lo que vale la pelicula lejos de la mancha. Es un entero de 8 bits por capa."""
    niveles = {}
    for capa in CAPAS:
        canal = _FUENTE[capa](gris, color)[::paso, ::paso]
        inv = 255.0 - canal.astype(np.float32)
        pelicula = (inv > UMBRAL_DE_PELICULA) & (inv < resultado["perfiles"][capa]["tope"] - HOLGURA_BAJO_EL_TOPE)
        if not pelicula.any():
            raise ValueError(f"la imagen no tiene pelicula sin dosis en la capa {capa}")
        niveles[capa] = int(round(float(np.median(canal[pelicula]))))
    return niveles


# ============================================================================================================================ el fondo LEJANO
def zona_protegida(resultado, forma, distancia_a_la_meseta=DISTANCIA_A_LA_MESETA_PX, distancia_a_la_linea=DISTANCIA_A_LA_LINEA_PX):
    """Mascara (forma de la ORIGINAL) de lo que el motor PUEDE leer para medir los desfases: una caja alrededor de la meseta de las capas que se miden (las filas que se usan +- `distancia_a_la_meseta`
    px y las columnas de la meseta +- lo mismo) y una franja alrededor de la linea (+- `distancia_a_la_linea` px) en todas las filas de la ventana; llevada a la imagen original con la matriz de la ventana.
    Todo lo demas (lo de fuera de la ventana incluido) es «lejano»."""
    ventana = resultado["imagenes"]["gris"]
    alto, ancho = ventana.shape
    protegida = np.zeros((alto, ancho), np.uint8)
    for y in range(alto):
        x = int(round(float(resultado["x_ref"][y])))
        protegida[y, max(0, x - distancia_a_la_linea):x + distancia_a_la_linea + 1] = 1
    medidas = [resultado["perfiles"][capa] for capa in CAPAS if resultado["perfiles"][capa]["estado"] == "ok"]
    if not medidas:
        raise ValueError("ninguna capa se mide: no hay meseta que proteger")
    y0 = max(0, min(int(p["filas"].min()) for p in medidas) - distancia_a_la_meseta)
    y1 = min(alto, max(int(p["filas"].max()) for p in medidas) + distancia_a_la_meseta + 1)
    x0 = max(0, min(int(p["m"]["inicio"][p["filas"]].min()) for p in medidas) - distancia_a_la_meseta)
    x1 = min(ancho, max(int(p["m"]["fin"][p["filas"]].max()) for p in medidas) + distancia_a_la_meseta + 1)
    protegida[y0:y1, x0:x1] = 1
    return cv2.warpAffine(protegida, np.asarray(resultado["matriz_ventana"], np.float64), (forma[1], forma[0]), flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0


def cambiar_el_fondo_lejano(gris, color, resultado, protegida, modo, valor, dentro_de_la_ventana=None):
    """Copias de (gris, color) con el nivel de la pelicula cambiado SOLO donde el motor no puede leerlo: fuera de `protegida` y en los pixeles cuyo nivel invertido esta `HOLGURA_BAJO_EL_TOPE` por
    debajo del tope de su capa. Modo 'desplazar': el nivel invertido sube `valor` (negativo: baja); modo 'plano': todos pasan a valer `valor` (invertido). En los dos casos el nuevo nivel invertido se
    deja a `TOPE_DEL_FONDO_CAMBIADO` o mas por debajo del tope (nunca llega a la meseta, a la caida de borde ni a ningun umbral). Devuelve (gris, color, {capa: pixeles cambiados}, {capa: de ellos, dentro
    de `dentro_de_la_ventana`})."""
    g2, c2 = gris.copy(), color.copy()
    cambiados = {capa: 0 for capa in CAPAS}
    en_la_ventana = {capa: (0 if dentro_de_la_ventana is not None else None) for capa in CAPAS}
    alto = gris.shape[0]
    for capa in CAPAS:
        tope = float(resultado["perfiles"][capa]["tope"])
        canal = _FUENTE[capa](g2, c2)                                   # vistas: se escribe en g2 / c2
        limite = 255.0 - (tope - HOLGURA_BAJO_EL_TOPE)                  # nivel invertido < tope - HOLGURA  <=>  canal > limite
        techo = tope - TOPE_DEL_FONDO_CAMBIADO
        for y0 in range(0, alto, FILAS_POR_BLOQUE):
            y1 = min(alto, y0 + FILAS_POR_BLOQUE)
            bloque = canal[y0:y1]
            seleccion = (~protegida[y0:y1]) & (bloque > limite)
            if not seleccion.any():
                continue
            inv = 255.0 - bloque[seleccion].astype(np.float32)
            nuevo = np.minimum(np.clip(inv + valor, 0.0, None), techo) if modo == "desplazar" else np.full(inv.shape, min(float(valor), techo), np.float32)
            bloque[seleccion] = np.clip(np.rint(255.0 - nuevo), 0, 255).astype(bloque.dtype)
            cambiados[capa] += int(seleccion.sum())
            if dentro_de_la_ventana is not None:
                en_la_ventana[capa] += int((seleccion & dentro_de_la_ventana[y0:y1]).sum())
    return g2, c2, cambiados, en_la_ventana


# ============================================================================================================================ comparar
def diferencias(a, b, ignorar=(), ruta=""):
    """Las diferencias (rutas) entre dos estructuras de resultados, BIT A BIT: dicts, listas, arreglos, flotantes (un NaN es igual a otro NaN) y todo lo demas por igualdad. `ignorar`: claves del
    PRIMER nivel que no se comparan."""
    if isinstance(a, dict):
        if not isinstance(b, dict) or set(a) != set(b):
            return [f"{ruta or '/'}: no tienen las mismas claves"]
        return [d for k in a if not (not ruta and k in ignorar) for d in diferencias(a[k], b[k], ignorar, f"{ruta}/{k}")]
    if isinstance(a, (list, tuple)):
        if not isinstance(b, (list, tuple)) or len(a) != len(b):
            return [f"{ruta}: largo distinto"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diferencias(x, y, ignorar, f"{ruta}[{i}]")]
    if isinstance(a, np.ndarray):
        if not isinstance(b, np.ndarray) or a.shape != b.shape or a.dtype != b.dtype:
            return [f"{ruta}: arreglo de otra forma o tipo"]
        return [] if np.array_equal(a, b, equal_nan=a.dtype.kind == "f") else [f"{ruta}: {int(np.count_nonzero(a != b))} elementos distintos"]
    if isinstance(a, (float, np.floating)):
        return [] if (a == b or (np.isnan(a) and isinstance(b, (float, np.floating)) and np.isnan(b))) else [f"{ruta}: {a!r} != {b!r}"]
    return [] if a == b else [f"{ruta}: {a!r} != {b!r}"]


def lo_medido_de_los_desfases(r, motor):
    """Todo lo que el motor MIDE de los desfases, sin las imagenes ni el filtrado (que contienen el fondo) y sin lo que sale del transito: la linea (`x_ref`, `linea`, `u_linea_px`, `mensaje_linea`), el
    angulo, y por capa el estado, las filas, el desfase, su dispersion, la incertidumbre de las filas, la comprobacion de cruces, los centros, el tope, lo que se GUARDA (`valores_medidos`: px, mm,
    incertidumbre, filas) y lo que se MUESTRA (`resumen`: mm, U, veredicto). Sin `lado_transito`, `sentido` ni `desfase_fisico_mm`: salen de la banda del transito."""
    valores = motor.valores_medidos(r)
    valores.pop("lado_transito")
    medida = {"angulo": r["angulo"], "x_ref": r["x_ref"], "linea": r["linea"], "u_linea_px": r["u_linea_px"], "mensaje_linea": r["mensaje_linea"], "valores": valores}
    for capa in CAPAS:
        p = r["perfiles"][capa]
        medida[capa] = {k: p[k] for k in ("estado", "filas", "desfase_px", "dispersion_px", "u_filas_px", "desfase_cruces_px", "centros", "desfases", "tope") if k in p}
        resumen = motor.resumen(r, capa)
        resumen.pop("desfase_fisico_mm", None)
        resumen.pop("sentido", None)
        medida[capa + "/resumen"] = resumen
    return medida


def fallos_del_lado(base, pintado):
    """El lado del transito de una placa con la pelicula de fuera tocada: el mismo que sin tocar o `None` («sin decidir»), NUNCA el contrario. `base` tiene que ser un lado decidido (si no, la
    prueba no probaria nada)."""
    if base not in LADOS:
        return [f"la placa sin tocar no decide el lado del transito ({base!r}): no hay nada que conservar"]
    if pintado is None or pintado == base:
        return []
    return [f"el lado del transito paso de {base!r} a {pintado!r}: solo puede quedar igual o sin decidir"]


# ============================================================================================================================ las escenas
@dataclass
class Escena:
    """Una placa lista para medir como la mide la aplicacion: los arreglos que entrega `leer_pelicula`, la resolucion que declara, los clics, y su analisis sin tocar."""
    nombre: str
    gris: np.ndarray
    color: np.ndarray
    validos: np.ndarray
    dpi: float
    clics: list
    resultado: dict
    lado_verdadero: object = None        # 'derecha' | 'izquierda' | None: el lado del transito que la verdad de la placa dice (solo las sinteticas con banda)
    desfase_verdadero_mm: object = None  # el desfase verdadero de la placa (solo las sinteticas)

    def medir(self, gris=None, color=None, motor=None):
        if motor is None:
            from analisisImagenes import posicion_inicial_braqui as motor
        return motor.analizar(self.gris if gris is None else gris, self.color if color is None else color, self.dpi, self.clics, validos=self.validos)


@dataclass(repr=False)
class VentanaArmada:
    """Una llamada de `analizar` a `ventana_rotada`: lo que pidio (`kwargs`) y lo que armo (`imagenes`, `clics`, `matriz`)."""
    kwargs: dict
    imagenes: dict
    clics: np.ndarray
    matriz: np.ndarray

    def __repr__(self):
        """Corto: lo que pidio (los nombres) y la forma de cada ventana; sin los arreglos de imagen (un mensaje de aserciones que cae no puede imprimir cientos de MB)."""
        return f"VentanaArmada(pidio={sorted(self.kwargs)}, formas={ {k: tuple(v.shape) for k, v in self.imagenes.items()} })"


def ventanas_que_arma_analizar(escena, motor=None):
    """Las ventanas que `analizar` arma DE VERDAD al medir `escena`, en el orden en que las pide (la de los desfases y la larga del transito). Se observan por dentro: una espia sobre `ventana_rotada` del motor que
    devuelve lo mismo que la original y se retira al terminar. Asi la prueba mira la ventana que usa la aplicacion y no una que arme con su propia cuenta: una holgura de mas o de menos en `analizar` se ve aunque
    ninguna salida cambie lo bastante para que otra prueba lo note (R1-LD-03)."""
    if motor is None:
        from analisisImagenes import posicion_inicial_braqui as motor
    original = motor.ventana_rotada
    armadas = []

    def espia(*args, **kwargs):
        imagenes, clics, matriz = original(*args, **kwargs)
        armadas.append(VentanaArmada(dict(kwargs), imagenes, clics, matriz))
        return imagenes, clics, matriz
    with mock.patch.object(motor, "ventana_rotada", espia):
        escena.medir(motor=motor)
    return armadas


def escena_desde_bytes(nombre, datos, clics, lado_verdadero=None, motor=None):
    """La escena de un archivo de pelicula (bytes), leido con el lector unico de la aplicacion."""
    from analisisImagenes.pelicula import leer_pelicula
    pelicula = leer_pelicula(datos)
    gris, color = pelicula.en_bgr()
    escena = Escena(nombre, gris, color, pelicula.validos, pelicula.dpi, [tuple(int(v) for v in c) for c in clics], {}, lado_verdadero)
    escena.resultado = escena.medir(motor=motor)
    return escena


def en_pagina(escena, nombre, forma=PAGINA_PX, fondo=FONDO_DE_LA_PAGINA, origen=None, motor=None):
    """La misma pelicula (los mismos pixeles) sobre una pagina entera del escaner: blanca, `forma` (alto, ancho), con la pelicula en `origen` (x, y; por omision, centrada). Los clics se trasladan."""
    alto, ancho = escena.gris.shape
    if origen is None:
        origen = ((forma[1] - ancho) // 2, (forma[0] - alto) // 2)
    x0, y0 = origen
    gris = np.full(forma, fondo, escena.gris.dtype)
    color = np.full(forma + (3,), fondo, escena.color.dtype)
    gris[y0:y0 + alto, x0:x0 + ancho] = escena.gris
    color[y0:y0 + alto, x0:x0 + ancho] = escena.color
    validos = np.ones(forma, bool)
    validos[y0:y0 + alto, x0:x0 + ancho] = escena.validos
    pagina = Escena(nombre, gris, color, validos, escena.dpi, [(x + x0, y + y0) for x, y in escena.clics], {}, escena.lado_verdadero, escena.desfase_verdadero_mm)
    pagina.resultado = pagina.medir(motor=motor)
    return pagina
