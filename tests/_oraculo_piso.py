"""A.3 (PLAN_ANALISIS_PELICULAS_08-10.md): el ORACULO del piso -- la verdad de una pelicula sintetica de PF.0, calculada con OTROS algoritmos que la funcion que se prueba.

Lo usan `test_a2_piso_de_pelicula.py` y `test_a3_piso_por_esquinas_y_pelicula_virgen.py`. Este archivo NO empieza por `test_`, asi que pytest no lo colecciona.

QUE ES (y por que es independiente de `analisisImagenes/pelicula.py`):
  - la PELICULA es el rectangulo conocido del generador: un pixel es pelicula si su centro, llevado al sistema de la pelicula con el giro inverso del propio generador (`gen._uv`, la unica
    definicion de ese cambio de coordenadas), cae dentro de la pelicula de 115 x 116 mm (la misma desigualdad con que el generador la dibuja); su erosion sale de `cv2.distanceTransform` sobre
    esa mascara. La funcion, en cambio, umbraliza los colores (la capa mas oscura < 235), toma la componente conexa mas grande y erosiona esa. EL BORDE DE LA IMAGEN ES UN BORDE: la funcion de
    A.3 aparta tambien el borde de la imagen (V2 del diseño); un pixel pegado al borde de la imagen no cuenta como pelicula limpia. (Una version anterior rasterizaba el poligono de las
    esquinas con `cv2.fillConvexPoly`: sus bordes discrepan hasta un pixel del generador y en una pelicula girada eso desplazaba la franja de la esquina y bajaba la coincidencia de las
    regiones a 0.87;)
  - la DISTANCIA AL CAMPO se mide por rasterizacion (`_distancia_al_campo_mm`: transformada de distancia del poligono del campo), no con las distancias analiticas a los cuatro segmentos;
  - una CUÑA (la esquina k) es el conjunto de pixeles cuyo punto mas cercano del campo es el vertice C_k: el CONO NORMAL del vertice, la zona entre las dos perpendiculares a los lados que
    llegan a el, tirada hacia afuera. Aqui se CONSTRUYE ese cono como un poligono (el vertice, un punto lejano sobre cada perpendicular y otro sobre la bisectriz) y se rasteriza con
    `cv2.fillConvexPoly`; la funcion, en cambio, decide cada pixel con dos desigualdades de productos punto. (Dos intentos anteriores de este oraculo fallaron por el mismo motivo: comparaban
    la distancia al campo con la distancia al vertice, `|dcam - |p - C_k|| < 1 px`, banda que crece con la raiz de la distancia y metia en la cuña un 11 % de pixeles del costado; y usar
    el pixel del campo mas cercano de scipy daba un contorno en dientes de sierra.)
  - la REGION de cada cuña es el 20 % mas lejano de lo elegible (pelicula limpia a mas de 5 mm del campo) o, si eso es menos de 2000 pixeles, los 2000 mas lejanos (la funcion pide la posicion
    en un orden estable; aqui es un umbral por valor);
  - el PISO VERDADERO de una region es la mediana de la respuesta del generador SIN RUIDO en esos pixeles (`virgen - (virgen - meseta) * g(D)` con `D` el mapa de dosis del generador).

`Oraculo(s)` recibe una `Sint` de test_a2 (el arreglo, la verdad, la `Pelicula` y las cuatro esquinas del campo luminoso).
"""
import cv2
import numpy as np

import _placa_mensual_sintetica as gen

ESC = 25.4 / 600.0                                    # mm por pixel: la escala del procedimiento (600 dpi)
ESQUINAS = ("UL", "UR", "DR", "DL")                  # el orden de `_piso_cuadrilatero`: el angulo alrededor del centroide, en la imagen con y hacia abajo


def poligono(forma, puntos):
    m = np.zeros(forma, np.uint8)
    cv2.fillConvexPoly(m, np.rint(np.asarray(puntos, np.float64)).astype(np.int32), 1)
    return m.astype(bool)


def distancia_al_campo_mm(forma, campo):
    """Distancia (mm) de cada pixel al campo luminoso, por rasterizacion + transformada de distancia (NO las distancias analiticas de la funcion)."""
    dentro = poligono(forma, campo)
    return cv2.distanceTransform((~dentro).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * np.float32(ESC)


def cono_normal(forma, campo, k):
    """El cono normal del vertice k del cuadrilatero `campo` (la cuña: los pixeles cuyo punto mas cercano del campo es ese vertice), como poligono rasterizado: el vertice, un punto lejano
    sobre la perpendicular exterior de cada uno de los dos lados que llegan a el y otro sobre la bisectriz. `campo` en el orden UL, UR, DR, DL (alrededor del centro)."""
    c = np.asarray(campo, np.float64)
    centro = c.mean(axis=0)
    v = c[k]

    def hacia_afuera(a, b):
        e = b - a
        n = np.array([e[1], -e[0]]) / np.hypot(*e)
        return n if np.dot((a + b) / 2.0 - centro, n) > 0 else -n

    n1 = hacia_afuera(c[(k - 1) % 4], v)          # el lado que llega al vertice
    n2 = hacia_afuera(v, c[(k + 1) % 4])           # el lado que sale del vertice
    largo = 4.0 * max(forma)
    bis = (n1 + n2) / np.hypot(*(n1 + n2))
    return poligono(forma, [v, v + largo * n1, v + 2.0 * largo * bis, v + largo * n2])


def crudo_sin_ruido(D, capa):
    """La respuesta de la pelicula en esa capa SIN ruido: `virgen - (virgen - meseta) * g(D)` (el generador de PF.0; `_g` es privada y se usa a proposito)."""
    c = gen.CALIB
    i = gen.INDICE_CAPA[capa]
    virgen, meseta, k = c["virgen_bgr"][i], c["meseta_bgr"][i], c["k_bgr"][i]
    return virgen - (virgen - meseta) * gen._g(D, k)


class Oraculo:
    """La verdad de una sintetica (ver el docstring del modulo). Atributos:
      D              mapa de dosis (float32) del generador, sin ruido
      borde_mm       distancia (mm) de cada pixel de pelicula al borde de la pelicula o de la imagen (0 fuera de la pelicula)
      pelicula       bool: dentro del poligono de la pelicula
      dcam           distancia (mm) de cada pixel al campo luminoso
      valida         la pelicula a mas de `margen_borde_mm` de su borde y del borde de la imagen
      elegibles      valida y a mas de `margen_campo_mm` del campo
      cunas          {esquina: bool} los pixeles cuyo punto mas cercano del campo es ese vertice
      region_de      {esquina: bool} el 20 % mas lejano de la cuña elegible (o los `minimo` mas lejanos)
      n_cuna         {esquina: int} los pixeles elegibles de cada cuña
      region         la union de la region de las esquinas con `minimo` pixeles elegibles o mas (las que dan piso)
    """

    def __init__(self, s, margen_borde_mm=1.0, margen_campo_mm=5.0, fraccion=0.20, minimo=2000):
        v = s.verdad
        alto, ancho = s.forma
        D, _ = gen.mapa_dosis(v.variante, v.giro_deg, 600, s.kw.get("desplazamiento_px"), s.kw.get("beta", 0.0), s.kw.get("cupula_pct_40mm", 0.0))
        self.D = D.astype(np.float32)
        del D
        geom, pel = v._geom, v._geom["pel"]
        lienzo = np.zeros((alto + 2, ancho + 2), np.uint8)       # un pixel de «no pelicula» alrededor: el borde de la imagen es un borde
        for f0 in range(0, alto, 256):
            f1 = min(alto, f0 + 256)
            u, w = gen._uv(geom, f0, f1)
            lienzo[1 + f0:1 + f1, 1:-1] = (u >= pel["L"]) & (u <= pel["R"]) & (w >= pel["T"]) & (w <= pel["B"])
        self.borde_mm = cv2.distanceTransform(lienzo, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[1:-1, 1:-1] * np.float32(ESC)
        self.pelicula = self.borde_mm > 0
        self.dcam = distancia_al_campo_mm(s.forma, s.campo)
        self.valida = self.borde_mm > margen_borde_mm
        self.elegibles = self.valida & (self.dcam > margen_campo_mm)
        self.margen_campo_mm, self.fraccion, self.minimo = margen_campo_mm, fraccion, minimo
        columnas = np.arange(ancho, dtype=np.float32)[None, :]
        filas = np.arange(alto, dtype=np.float32)[:, None]
        self.cunas, self.region_de, self.n_cuna = {}, {}, {}
        for nombre, (cx, cy) in zip(ESQUINAS, s.campo):
            al_vertice = np.hypot(columnas - np.float32(cx), filas - np.float32(cy)) * np.float32(ESC)
            en_cuna = cono_normal(s.forma, s.campo, ESQUINAS.index(nombre))
            self.cunas[nombre] = en_cuna
            elegible = self.elegibles & en_cuna
            self.n_cuna[nombre] = int(elegible.sum())
            if self.n_cuna[nombre] >= minimo:
                d = al_vertice[elegible]
                corte = np.quantile(d, 1.0 - fraccion)
                if (d >= corte).sum() < minimo:
                    corte = np.sort(d)[-minimo]
                self.region_de[nombre] = elegible & (al_vertice >= corte)
            else:
                self.region_de[nombre] = elegible
        self.region = np.zeros(s.forma, bool)
        for nombre in ESQUINAS:
            if self.n_cuna[nombre] >= minimo:
                self.region |= self.region_de[nombre]

    def crudo(self, capa, mascara):
        """La respuesta sin ruido de esa capa en los pixeles de `mascara` (las del tamaño de la imagen)."""
        return crudo_sin_ruido(self.D[mascara].astype(np.float64), capa)

    def piso(self, excluir=None, region=None):
        """La mediana de la respuesta sin ruido, por capa B, G y R, en la region (por omision, la union de las esquinas que dan piso) menos `excluir`."""
        region = self.region if region is None else region
        region = region if excluir is None else region & ~excluir
        return {c: float(np.median(self.crudo(c, region))) for c in "BGR"}
