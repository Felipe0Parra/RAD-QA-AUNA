"""CD.2 (22-10-2026, CD2-D8): el generador de PIEZAS DE CALIBRACION sinteticas.

Una pieza de calibracion es un trozo de pelicula radiocromica uniforme (de unos 18 x 18 mm; irradiado a una dosis, o sin irradiar) que el fisico escanea y sube a la app, uno por imagen. Este
modulo arma esas piezas con el valor de cada capa CONOCIDO, para probar con verdad conocida la medicion de una pieza (`pelicula.medir_pieza_uniforme`, CD.2) y, despues, la curva de dosis (CD.3,
que le agrega la respuesta en dosis a este mismo archivo).

QUE SABE ARMAR (todo en niveles de 8 bits, la unidad en que el motor mide, y todo determinista: la misma semilla da los mismos bytes):
  - el valor de cada capa (R, G, B) en el CENTRO de la pieza, el ruido gaussiano de cada capa (`sigma`, con semilla) y un gradiente lineal (`pendiente_x`, `pendiente_y`, niveles por mm);
  - manchas de tinta (un rectangulo con un desplazamiento de nivel), motas y polvo en rejilla;
  - una capa en el negro del escaner (valores de 0 o 1), que el escaner recorta;
  - la pieza recortada a ras de la imagen (como las 21 de `ImagenesDeReferencia/Calibracion`) o sobre una pagina blanca; varias piezas en una pagina;
  - la resolucion con que se escaneo (la rejilla de pixeles) y la que el archivo DECLARA, que pueden ser distintas, o ninguna;
  - 8 o 16 bits por canal, en un TIFF sin compresion;
  - (CD.3) el blanco de la pagina (`blanco`, el fondo del escaner), un ruido por capa (`sigma` = (R, G, B)) y la RESPUESTA EN DOSIS: una pieza irradiada a D vale I0_c · 10^(−x_c(D)) en cada
    capa, con la respuesta de Devic exacta, una saturante o una lineal, y el ruido de EPSON179 (H2) por omision (`pieza_de_dosis`, al final del archivo).

INDEPENDENCIA. Este generador NO importa nada de `analisisImagenes`, `services`, `ui` ni `data`: la verdad con que se comprueba el motor no puede salir del motor. `test_cd2_medicion_de_una_pieza.py`
lo vigila por AST. La unica constante fisica es la definicion de la pulgada (25.4 mm); la conversion de milimetros a pixeles de AQUI (`pixeles`) es del generador, no del motor. El centro de una region
que el motor mide puede diferir a lo sumo un pixel del centro geometrico de la pieza (redondeos de media celda): las pruebas con gradiente eligen una pendiente que lo absorbe en su tolerancia.
"""
import io
from dataclasses import dataclass

import numpy as np
import tifffile

MM_POR_PULGADA = 25.4           # la definicion de la pulgada
BLANCO = 255.0                  # el fondo de un escaner con la tapa cerrada
CODIGOS_POR_NIVEL = 257         # un nivel de 8 bits son 257 codigos de 16 bits (65535 / 255)
PESOS_DEL_GRIS = (0.299, 0.587, 0.114)      # el gris de una imagen a color (ITU-R BT.601), el que define OpenCV
CAPAS = ("R", "G", "B")


def pixeles(mm, dpi):
    """Los pixeles que ocupan `mm` milimetros a `dpi` (el entero mas cercano)."""
    return int(round(mm * dpi / MM_POR_PULGADA))


def gris_de(valores):
    """El gris (ITU-R BT.601) de un (R, G, B)."""
    return sum(peso * v for peso, v in zip(PESOS_DEL_GRIS, valores))


@dataclass(frozen=True)
class Caja:
    """Un rectangulo de pixeles de la pagina: [x0, x1) por [y0, y1)."""
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def ancho(self):
        return self.x1 - self.x0

    @property
    def alto(self):
        return self.y1 - self.y0

    @property
    def centro(self):
        """(x, y) del centro, en coordenadas de indice de pixel (el centro de n pixeles que empiezan en 0 es (n - 1) / 2)."""
        return (self.x0 + self.x1 - 1) / 2.0, (self.y0 + self.y1 - 1) / 2.0


class Lienzo:
    """Una pagina del escaner: un arreglo (alto, ancho, 3) en R, G, B (niveles de 8 bits en float), blanca al empezar. Cada `pegar_*` devuelve la `Caja` que pinto."""

    def __init__(self, ancho_mm, alto_mm, dpi, semilla=1, blanco=BLANCO):
        self.dpi = float(dpi)
        self.alto, self.ancho = pixeles(alto_mm, dpi), pixeles(ancho_mm, dpi)
        self.rgb = np.full((self.alto, self.ancho, 3), float(blanco))          # CD.3: `blanco` = el fondo del escaner (255 por omision; menos, un escaner que ajusto la exposicion)
        self.rng = np.random.default_rng(semilla)

    def mm(self, milimetros):
        return pixeles(milimetros, self.dpi)

    def _caja(self, x_mm, y_mm, ancho_mm, alto_mm):
        x0, y0 = self.mm(x_mm), self.mm(y_mm)
        caja = Caja(x0, y0, x0 + self.mm(ancho_mm), y0 + self.mm(alto_mm))
        if caja.x0 < 0 or caja.y0 < 0 or caja.x1 > self.ancho or caja.y1 > self.alto:
            raise ValueError(f"la caja {caja} no cabe en la pagina de {self.ancho} x {self.alto} pixeles")
        return caja

    def pegar_pelicula(self, x_mm, y_mm, ancho_mm, alto_mm, valores, sigma=0.0, pendiente_x=0.0, pendiente_y=0.0):
        """Pega un rectangulo de pelicula: `valores` = el (R, G, B) de su CENTRO; `sigma` = el ruido gaussiano de cada capa (independiente por capa); `pendiente_x` y `pendiente_y` = el gradiente lineal
        en niveles por mm (positivo = mas claro hacia la derecha o hacia abajo). Todo se recorta a [0, 255] antes de redondear al codificar."""
        caja = self._caja(x_mm, y_mm, ancho_mm, alto_mm)
        por_mm = self.dpi / MM_POR_PULGADA
        columnas = (np.arange(caja.ancho) - (caja.ancho - 1) / 2.0) / por_mm
        filas = (np.arange(caja.alto) - (caja.alto - 1) / 2.0) / por_mm
        zona = np.asarray(valores, float)[None, None, :] + pendiente_x * columnas[None, :, None] + pendiente_y * filas[:, None, None]
        if np.ndim(sigma):                         # CD.3: un ruido por capa (R, G, B), como el de EPSON179 (H2); un numero sigue siendo el mismo para las tres, con los mismos bytes de antes
            zona = zona + self.rng.normal(0.0, 1.0, zona.shape) * np.asarray(sigma, float)[None, None, :]
        elif sigma:
            zona = zona + self.rng.normal(0.0, sigma, zona.shape)
        self.rgb[caja.y0:caja.y1, caja.x0:caja.x1] = np.clip(zona, 0.0, 255.0)
        return caja

    def pegar_mancha(self, x_mm, y_mm, ancho_mm, alto_mm, delta):
        """Suma `delta` niveles a las tres capas de un rectangulo ya pintado (negativo = tinta oscura; positivo = una mota clara). Devuelve su `Caja`."""
        caja = self._caja(x_mm, y_mm, ancho_mm, alto_mm)
        self.rgb[caja.y0:caja.y1, caja.x0:caja.x1] = np.clip(self.rgb[caja.y0:caja.y1, caja.x0:caja.x1] + delta, 0.0, 255.0)
        return caja

    def pegar_punteado(self, x_mm, y_mm, ancho_mm, alto_mm, paso_px, lado_px, delta):
        """Suma `delta` niveles a las tres capas de unos bloques de `lado_px` x `lado_px` repetidos cada `paso_px` pixeles dentro de un rectangulo ya pintado: motas claras en rejilla (polvo en toda la
        pelicula). Devuelve su `Caja`."""
        caja = self._caja(x_mm, y_mm, ancho_mm, alto_mm)
        zona = self.rgb[caja.y0:caja.y1, caja.x0:caja.x1]               # una vista: lo que se escribe aqui queda en la pagina
        marca = np.zeros(zona.shape[:2], bool)
        for dy in range(lado_px):
            for dx in range(lado_px):
                marca[dy::paso_px, dx::paso_px] = True
        zona[marca] = np.clip(zona[marca] + delta, 0.0, 255.0)
        return caja

    def codificar(self, bits=8, dpi_declarado="real"):
        """Los bytes de un TIFF sin compresion de 8 o 16 bits por canal. `dpi_declarado`: «real» (la rejilla de la pagina), un numero (lo que declara el archivo, p. ej. 96 de un editor) o None (el archivo
        no declara resolucion)."""
        if bits == 8:
            matriz = np.rint(self.rgb).astype(np.uint8)
        elif bits == 16:
            matriz = np.rint(self.rgb * CODIGOS_POR_NIVEL).astype(np.uint16)
        else:
            raise ValueError(f"bits debe ser 8 o 16, no {bits!r}")
        resolucion = {}
        if dpi_declarado is not None:
            declarado = self.dpi if dpi_declarado == "real" else float(dpi_declarado)
            resolucion = dict(resolution=(declarado, declarado), resolutionunit="INCH")
        salida = io.BytesIO()
        tifffile.imwrite(salida, np.ascontiguousarray(matriz), photometric="rgb", compression=None, **resolucion)
        return salida.getvalue()


@dataclass(frozen=True)
class Pieza:
    """Una pieza armada: sus bytes y la verdad con que se armo. `valores`: el (R, G, B) nominal del CENTRO de la pieza; `caja`: donde esta la pelicula en la pagina (pixeles); `dpi`: la rejilla de pixeles."""
    datos: bytes
    valores: tuple
    dpi: float
    bits: int
    lado_mm: float
    caja: Caja

    def nominal(self, capa):
        """El valor nominal de una capa (R, G, B o gris) en el centro de la pieza."""
        return gris_de(self.valores) if capa == "gris" else self.valores[CAPAS.index(capa)]


def pieza_uniforme(valores=(150.0, 120.0, 95.0), *, lado_mm=18.0, dpi=150.0, sigma=1.5, semilla=7, margen_mm=0.0, pagina_mm=None, posicion_mm=None, bits=8, dpi_declarado="real",
                   pendiente_x=0.0, pendiente_y=0.0, manchas=(), blanco=BLANCO):
    """Una pieza cuadrada de `lado_mm`, uniforme salvo el ruido, el gradiente y las manchas. Dos formas de ponerla: `margen_mm` = 0, recortada a ras de la imagen (como las 21 piezas de H9); mayor, sobre una
    pagina blanca con ese margen por lado; o en una pagina de `pagina_mm` = (ancho, alto) con la esquina superior izquierda de la pieza en `posicion_mm` = (x, y), para que el centro de la pieza no sea el de la
    imagen. `manchas`: [(x_mm, y_mm, ancho_mm, alto_mm, delta)] con (x, y) desde la esquina superior izquierda de la PIEZA."""
    if pagina_mm is None:
        pagina_mm, posicion_mm = (lado_mm + 2 * margen_mm, lado_mm + 2 * margen_mm), (margen_mm, margen_mm)
    elif posicion_mm is None:
        raise ValueError("con `pagina_mm` hay que decir donde va la pieza (`posicion_mm`)")
    x, y = posicion_mm
    lienzo = Lienzo(pagina_mm[0], pagina_mm[1], dpi, semilla, blanco)
    caja = lienzo.pegar_pelicula(x, y, lado_mm, lado_mm, valores, sigma, pendiente_x, pendiente_y)
    for mancha_x, mancha_y, ancho, alto, delta in manchas:
        lienzo.pegar_mancha(x + mancha_x, y + mancha_y, ancho, alto, delta)
    return Pieza(lienzo.codificar(bits, dpi_declarado), tuple(float(v) for v in valores), float(dpi), bits, float(lado_mm), caja)


# ============================================================================= CD.3: la respuesta en dosis (la verdad con que se prueba la curva de dosis)
#
# Una pieza irradiada a una dosis D tiene en cada capa el valor I0_c · 10^(−x_c(D)): la densidad optica neta x_c(D) la da una RESPUESTA elegible, definida AQUI y no en el motor (`analisisImagenes/curva_dosis.py`):
# la de Devic exacta (para recuperar sus parametros), una saturante que el modelo de Devic no puede representar (para ver el desajuste) o una lineal. El ruido por omision es el medido en EPSON179 (H2).
I0_EPSON179 = (152.12, 194.11, 86.77)       # H2: la media de cada capa (R, G, B) de la pelicula virgen EPSON179, la cadena de las mensuales
RUIDO_EPSON179 = (1.25, 0.66, 1.6)          # H2: el ruido del centro de EPSON179 (R, G, B), en niveles de 8 bits
NEGRO_DEL_ESCANER = 0.5                     # lo que lee el escaner en una capa que recorto (el rojo a 800 UM: la mediana de su meseta vale de 0.5 a 1.0)
ITERACIONES_DE_LA_INVERSA = 200             # la biseccion PROPIA del generador (la de Devic no tiene inversa cerrada)


@dataclass(frozen=True)
class RespuestaDevic:
    """D(x) = a·x + b·x^n (Devic et al. 2004): la dosis de una densidad optica; `netod(D)` la invierte por biseccion propia."""
    a: float
    b: float
    n: float

    def dosis(self, x):
        return self.a * x + self.b * x ** self.n

    def netod(self, d):
        if d <= 0:
            return 0.0
        bajo, alto = 0.0, 1.0
        while self.dosis(alto) < d:
            alto *= 2.0
        for _ in range(ITERACIONES_DE_LA_INVERSA):
            medio = (bajo + alto) / 2.0
            bajo, alto = (medio, alto) if self.dosis(medio) < d else (bajo, medio)
        return (bajo + alto) / 2.0


@dataclass(frozen=True)
class RespuestaSaturante:
    """x(D) = x_max · (1 − exp(−D / d0)): una pelicula que se satura hacia x_max. En dosis, D(x) = −d0 · ln(1 − x / x_max), que diverge en x_max: el modelo de Devic (un polinomio) no la puede
    representar entera y sus residuos lo dicen."""
    x_max: float
    d0: float

    def dosis(self, x):
        return -self.d0 * np.log1p(-x / self.x_max)

    def netod(self, d):
        return self.x_max * -np.expm1(-d / self.d0)


@dataclass(frozen=True)
class RespuestaLineal:
    """x(D) = D / pendiente: la de Devic con b = 0 (a = pendiente, en cGy por unidad de netOD)."""
    pendiente: float

    def dosis(self, x):
        return self.pendiente * x

    def netod(self, d):
        return d / self.pendiente


def valores_de_la_dosis(dosis_cgy, respuestas, i0=I0_EPSON179, negro_desde_cgy=None):
    """El (R, G, B) de una pieza irradiada a `dosis_cgy` (la verdad del generador): I0_c · 10^(−x_c(D)) por capa. `respuestas`: una respuesta para las tres capas o una por capa (R, G, B);
    `negro_desde_cgy`: {capa: dosis} desde la cual esa capa esta en el negro del escaner (`NEGRO_DEL_ESCANER`)."""
    if not isinstance(respuestas, (tuple, list)):
        respuestas = (respuestas,) * 3
    valores = []
    for capa, respuesta, inicial in zip(CAPAS, respuestas, i0):
        if negro_desde_cgy and capa in negro_desde_cgy and dosis_cgy >= negro_desde_cgy[capa]:
            valores.append(NEGRO_DEL_ESCANER)
        else:
            valores.append(float(inicial) * 10.0 ** (-float(respuesta.netod(float(dosis_cgy)))))
    return tuple(valores)


def pieza_de_dosis(dosis_cgy, respuestas, *, i0=I0_EPSON179, sigma=RUIDO_EPSON179, negro_desde_cgy=None, **opciones):
    """Una pieza uniforme irradiada a `dosis_cgy` con la respuesta `respuestas` (`valores_de_la_dosis`), el ruido `sigma` (por omision el de EPSON179, uno por capa; 0 = sin ruido) y lo demas de
    `pieza_uniforme` (`lado_mm`, `dpi`, `bits`, `margen_mm`, `pagina_mm` y `posicion_mm`, `pendiente_x`, `manchas`, `blanco`, `semilla`...)."""
    return pieza_uniforme(valores_de_la_dosis(dosis_cgy, respuestas, i0, negro_desde_cgy), sigma=sigma, **opciones)
