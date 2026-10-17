"""C.1 (PLAN_ANALISIS_PELICULAS_08-10.md): el MOTOR MENSUAL (1/3) -- la geometría del campo luminoso desde los cinco puntos.

Es el análisis de la película del control MENSUAL de los aceleradores (campo luminoso de 10 x 10 cm con sus cuatro esquinas y el retículo marcados) escrito de nuevo a partir del proceso
del cuaderno del físico, con las correcciones medidas en R3 (PD4: su método donde es correcto, corregido donde falla). Este archivo es la primera de tres entregas (C.1 la geometría,
C.2 los perfiles y la coincidencia, C.3 el barrido); la ventana (E.1), el guardado (D.1) y el PDF (F.1) usarán estas mismas funciones. Versión `PM-1`.

QUÉ HACE (R9, pasos 2 y 3).
  * `clasificar_puntos(puntos)`: de los cinco puntos marcados, EN CUALQUIER ORDEN, cuál es el retículo (el más cercano al centroide de los otros cuatro) y cuáles son las cuatro esquinas
    (por su ángulo alrededor de ese centroide: superior izquierda, superior derecha, inferior derecha, inferior izquierda). Las cuatro tienen que formar un cuadrilátero convexo que contenga al
    retículo: si no, «no medible: los puntos no forman el campo». No mira el centro de la imagen ni su forma (el cuaderno comparaba x con el ALTO y y con el ANCHO, y exigía el retículo a
    100 píxeles del centro de la imagen: con la película a más de ~100 píxeles del centro no clasificaba, N2).
  * `refinar_marca(gris, punto, P)`: acerca cada clic al centro de su marca de TINTA (el centroide subpíxel de la mancha oscura a `radio_marca_mm` = 1.5 mm del clic o menos). Sin mancha de
    tinta el clic queda «sin refinar» y se usa tal cual. Trabaja sobre un recorte local alrededor del clic, nunca sobre la página entera.
  * `geometria_luz(esquinas, reticulo, tam_mm)`: el cruce de las diagonales (el centro del campo luminoso), el ángulo girado (el PROMEDIO, CON SIGNO, de los ángulos que forman las dos
    diagonales con la horizontal: no el mayor, N10), la desviación de cada diagonal, los lados con distancia EUCLÍDEA (no por proyección, N7), los cuatro ángulos interiores, las dos
    diagonales, la inclinación de cada lado en el marco girado y centro luminoso - retículo (x, y, módulo; en la imagen y en el marco girado).
  * `matriz_giro(centro, angulo)` y `transformar_puntos(M, puntos)`: la matriz de `cv2.getRotationMatrix2D` en flotante, UNA definición para la imagen (C.2: `warpAffine`) y para los puntos.
  * `recuadro_luminoso(puntos)`: las cuatro esquinas con que se midió (la refinada o, si quedó «sin refinar», el clic) en el orden superior izquierda, superior derecha, inferior derecha,
    inferior izquierda, o el motivo si los puntos no forman el campo. Es la ÚNICA definición del recuadro: la dibujan la ventana (E.1) y la película del PDF (F.1).

CONVENCIONES. Todo está en el marco de la imagen tal como la leyó `analisisImagenes.pelicula.leer_pelicula`: x a la derecha (columna), y hacia abajo (fila), el centro del primer píxel es
(0, 0). Los ángulos son en GRADOS y su signo es el de la pantalla: positivo = giro HORARIO (la y hacia abajo hace que `atan2(dy, dx)` crezca en el sentido de las agujas del reloj). Un campo
girado theta en ese sentido tiene el ángulo +theta y se corrige con `matriz_giro(cruce, theta)` (un ángulo positivo de `getRotationMatrix2D` gira en sentido antihorario). Las longitudes salen en
milímetros con `tam_mm` (milímetros por píxel: `pelicula.escala_mm`, la del procedimiento, 600 dpi).

NO DEPENDE DEL ORDEN. Las funciones ordenan los puntos de forma canónica (por coordenadas) antes de operar: cualquier permutación de los mismos cinco puntos da el MISMO resultado, bit a
bit en las coordenadas y los números (los índices de `PuntosClasificados` dicen en qué posición de la lista de entrada estaba cada punto, así que sí cambian con la permutación).

EL PIVOTE NO CAMBIA NINGUNA MEDIDA (R2.2). Girar alrededor del cruce de diagonales, del centro de la imagen o de la esquina (0, 0) da las mismas longitudes, ángulos y desfases;
`geometria_luz(..., pivote=)` lo permite para comprobarlo. Lo único que depende del pivote son las posiciones absolutas de los puntos girados (`esquinas_giradas`, `reticulo_girado`).

LA IMAGEN ENTRA POR `leer_pelicula`. Este módulo no lee archivos: recibe el arreglo `gris` que entrega `Pelicula.gris` (float32 en «niveles de 8 bits»), así que ninguna ruta, ningún
`cv2.imread` ni nada de Qt, de la base de datos o de los servicios entra aquí (un test por AST lo vigila). Una operación, una definición: la escala (`escala_mm`), el orden de las
esquinas (`ESQUINAS`) y los parámetros del piso salen de `pelicula.py`; aquí no se vuelve a dividir 25.4 entre nada.

PARAMETROS. Cada parámetro tiene su nombre, su unidad y su motivo (PD1: lo que decide un número vive escrito, no en el código) y `VALORES_DE_LA_GEOMETRIA` es el diccionario plano que se le
pasa a las funciones como `P` y que viaja con cada análisis (D.1 lo guarda). Lleva los de este archivo, las tres claves de la escala (`CLAVES_DE_LA_ESCALA`: `escala_mm` las pide en `P`) y los
22 del piso (`VALORES_DEL_PISO`): C.2 y C.3 agregan los suyos a `PARAMETROS` y el plano se deriva de él, de modo que nunca divergen.

Sin Qt, sin base de datos y sin `cv2.imread`."""
import copy
import math
import numbers
from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage as ndi

from analisisImagenes.pelicula import CLAVES_DE_LA_ESCALA, ESQUINAS, PARAMETROS_DEL_PISO, escala_mm

VERSION_ALGORITMO = "PM-1"

ESTADO_REFINADA = "refinada"
ESTADO_SIN_REFINAR = "sin refinar"
MOTIVO_NO_FORMAN_EL_CAMPO = "no medible: los puntos no forman el campo"
MOTIVO_SIN_ESCALA = "no medible: no hay escala en milímetros (el archivo declara otra resolución que la del procedimiento)"
LADOS = ("superior", "derecho", "inferior", "izquierdo")      # en el sentido de las agujas del reloj desde la esquina superior izquierda: UL-UR, UR-DR, DR-DL, DL-UL
ANGULO_DE_LA_ESQUINA_SUPERIOR_IZQUIERDA = -0.75 * math.pi      # la dirección (-1, -1) desde el centro, con la y hacia abajo: de ahí arranca el orden de las esquinas
CLAVES_DE_LA_MARCA = ("radio_marca_mm", "contraste_minimo_marca", "fraccion_del_contraste_marca", "gris_maximo_de_la_tinta", "borde_blando_marca_mm", "area_minima_marca_mm2")      # lo que `refinar_marca` le pide a `P`
RADIO_MAXIMO_EN_PIXELES = 1000                                # un radio de búsqueda mayor es un error de `P` (el cierre de la mancha costaría minutos y la ventana saldría de cualquier película)
TOLERANCIA_GEOMETRICA = 1e-9                                  # píxeles (puntos iguales) y seno del ángulo (tres puntos «colineales»): por debajo es ruido de redondeo, no geometría

# Los parámetros de este archivo, cada uno con su nombre, su unidad y su motivo. Los valores de la escala son los del procedimiento (los mismos que el motor de la posición inicial: una prueba
# lo comprueba). Los del piso son los de `pelicula.PARAMETROS_DEL_PISO`, copiados.
PARAMETROS = {
    "radio_marca_mm": {
        "valor": 1.5, "unidad": "mm",
        "motivo": "Un clic a mano cae a pocos píxeles de la marca (en ML0 el del retículo quedó a 10 píxeles, 0.44 mm, y los de las esquinas a 0.01 a 0.21 mm): la mancha de tinta se busca a 1.5 mm del clic "
                  "como máximo (35 píxeles a 600 dpi: el círculo de búsqueda que la ventana dibuja) y es lo más lejos que se acepta que se mueva el punto. Es también el radio del elemento con que se "
                  "separa la mancha de su fondo, así que una mancha de más de 3 mm de ancho no es una marca de punto y no se refina."},
    "contraste_minimo_marca": {
        "valor": 10.0, "unidad": "niveles (0 a 255)",
        "motivo": "La tinta tiene que ser al menos 10 niveles más oscura que la película de su entorno inmediato (la marca del retículo, sobre la meseta del campo, contrasta 20 a 34 niveles en ML0 y las "
                  "de las esquinas 70 a 110); el ruido del escáner (1.5) y el grano de la película quedan por debajo de 6. Sin este mínimo una película lisa «tendría» una mancha donde el ruido sea mayor."},
    "fraccion_del_contraste_marca": {
        "valor": 0.5, "unidad": "fracción",
        "motivo": "El borde de la mancha es donde su contraste cae a la mitad del máximo, como el borde de radiación cae a la mitad entre el piso y la meseta: la mancha mide lo mismo en una película clara "
                  "que en una oscura, y su centro no depende de cuánta tinta dejó el rotulador."},
    "gris_maximo_de_la_tinta": {
        "valor": 10.0, "unidad": "nivel (0 a 255)",
        "motivo": "La tinta negra casi no deja pasar la luz del escáner: el décimo más oscuro de los píxeles de la mancha vale 0 a 1 niveles en las cinco marcas de ML0 y 0 y 5 en las marcas de tinta "
                  "de EPSON028 y EPSON001 que se refinan; barridas enteras las películas reales, los puntos de rotulador de núcleo menos oscuro miden 7 y 9 (el final de la fecha escrita a mano de EPSON030, "
                  "contraste 130) y el borde negro de la propia película de EPSON028 9.7. Lo oscuro que no es tinta no baja de 10 en ese décimo: las motas y el ruido JPEG sobre película saturada de "
                  "EPSON029 y ref40 dieron 10 (contraste 13 a 15) y todo lo demás 11 o más; la propia meseta del campo vale 24 a 30, el centro de sus anillos de presión 16 a 18, y una tinta tenue como la "
                  "de la esquina superior derecha de EPSON001 (32) tampoco llega. Una mancha oscura cuyo núcleo LLEGA a 10 no es tinta (el límite no se incluye: 10 es justo lo que dan las motas) y el "
                  "clic queda «sin refinar»: el punto no se arrastra hacia algo que quizá no es la marca (en las películas con anillos de presión en lugar de tinta, el clic del físico manda). El margen "
                  "entre lo que se toma por tinta (hasta 9.7) y lo que no (desde 10) es de 0.3 niveles."},
    "borde_blando_marca_mm": {
        "valor": 0.15, "unidad": "mm",
        "motivo": "El borde de una mancha de tinta no es un escalón: pasa del negro al fondo en 0.1 a 0.25 mm (el rotulador, el papel de la película y el escáner). Para pesar la mancha sin cortar ese borde se le "
                  "suma este margen (4 píxeles a 600 dpi): dentro de él cada píxel pesa lo que tiene de tinta, de 0 a 1, medido contra el fondo de SU lugar, de modo que el degradado de la penumbra del campo no "
                  "corre el centro (con el umbral solo, un fondo que cambia 25 niveles por mm lo corría 0.02 a 0.03 mm)."},
    "area_minima_marca_mm2": {
        "valor": 0.1, "unidad": "mm²",
        "motivo": "Una mancha de menos de 0.1 mm² (56 píxeles a 600 dpi, unos 0.36 mm de diámetro) es una mota o polvo, no una marca: las cinco de ML0 miden 0.4 a 0.8 mm² (226 a 441 píxeles)."},
    "resolucion_escaneo_dpi": {
        "valor": 600.0, "unidad": "puntos por pulgada",
        "motivo": "La resolución del procedimiento de escaneo: la escala de los milímetros (D14 del 01-10: el físico la garantiza desde el escaneo; la resolución que declara el archivo solo se clasifica)."},
    "resoluciones_de_editor_dpi": {
        "valor": [72.0, 96.0], "unidad": "puntos por pulgada",
        "motivo": "Lo que un editor (Paint, Windows) escribe al guardar un recorte sin remuestrear: una resolución declarada de 72 o 96 dpi no es de escaneo y la escala sigue siendo la del procedimiento."},
    "tolerancia_dpi_relativa": {
        "valor": 0.01, "unidad": "fracción",
        "motivo": "599 y 599.999 (lo que escribe el Epson) cuentan como 600, y 96.012 (lo que deja Paint) como 96."},
}
PARAMETROS.update(copy.deepcopy(PARAMETROS_DEL_PISO))
VALORES_DE_LA_GEOMETRIA = {nombre: copy.deepcopy(parametro["valor"]) for nombre, parametro in PARAMETROS.items()}


# ----------------------------------------------------------------------------- lo que devuelven las funciones

@dataclass(frozen=True)
class PuntosClasificados:
    """Los cinco puntos de la película, cada uno con su papel. `estado`: «ok» o «no medible: los puntos no forman el campo (<qué falló>)» (entonces nada más trae valor). `reticulo`: (x, y).
    `esquinas`: ((x, y) superior izquierda, superior derecha, inferior derecha, inferior izquierda) en píxeles de la imagen. `indice_del_reticulo` e `indices_de_las_esquinas`: la posición
    de cada punto en la lista que se entregó (las coordenadas no dependen del orden de la lista; los índices sí, y dicen cuál era cuál)."""
    estado: str
    reticulo: tuple | None = None
    esquinas: tuple = ()
    indice_del_reticulo: int | None = None
    indices_de_las_esquinas: tuple = ()

    @property
    def ok(self):
        return self.estado == "ok"

    def como_dict(self):
        return {"estado": self.estado, "reticulo": None if self.reticulo is None else [float(self.reticulo[0]), float(self.reticulo[1])],
                "esquinas": [[float(x), float(y)] for x, y in self.esquinas],
                "indice_del_reticulo": self.indice_del_reticulo, "indices_de_las_esquinas": list(self.indices_de_las_esquinas)}


@dataclass(frozen=True)
class MarcaRefinada:
    """Un clic y lo que `refinar_marca` hizo con él. `estado`: «refinada» o «sin refinar». `clic`: (x, y) como se marcó. `punto`: (x, y) con que se mide (el centro de la mancha si se refinó y,
    si no, el clic). `desplazamiento_px` y `desplazamiento_mm`: lo que se movió el punto (0 si no se refinó). `motivo`: por qué quedó «sin refinar» (texto) o None. `radio_px`: el radio del círculo de
    búsqueda (lo que la ventana dibuja). `area_mm2`, `contraste` (niveles sobre su entorno) y `gris_del_nucleo` (el décimo más oscuro de la mancha, en niveles): de la mancha aceptada, o None."""
    estado: str
    clic: tuple
    punto: tuple
    desplazamiento_px: float
    desplazamiento_mm: float
    radio_px: float
    motivo: str | None = None
    area_mm2: float | None = None
    contraste: float | None = None
    gris_del_nucleo: float | None = None

    @property
    def refinada(self):
        return self.estado == ESTADO_REFINADA

    def como_dict(self):
        return {"estado": self.estado, "clic": [float(self.clic[0]), float(self.clic[1])], "punto": [float(self.punto[0]), float(self.punto[1])],
                "desplazamiento_px": float(self.desplazamiento_px), "desplazamiento_mm": float(self.desplazamiento_mm), "radio_px": float(self.radio_px),
                "motivo": self.motivo, "area_mm2": self.area_mm2, "contraste": self.contraste, "gris_del_nucleo": self.gris_del_nucleo}


@dataclass(frozen=True)
class RecuadroLuminoso:
    """El recuadro del campo luminoso: `esquinas` ((x, y) superior izquierda, superior derecha, inferior derecha, inferior izquierda) o () si los puntos no forman el campo, y `estado` («ok» o el motivo)."""
    estado: str
    esquinas: tuple = ()

    @property
    def ok(self):
        return self.estado == "ok"

    def como_dict(self):
        return {"estado": self.estado, "esquinas": [[float(x), float(y)] for x, y in self.esquinas]}


@dataclass(frozen=True)
class GeometriaLuz:
    """La geometría del campo luminoso. `estado`: «ok» o «no medible: <motivo>». Si los puntos no forman el campo, nada más trae valor. Sin escala (`tam_mm` es None) el estado es «no medible: no hay
    escala en milímetros» y trae solo `esquinas` y `reticulo` (ya ordenados) y ninguna medida: sin escala no se mide nada, tampoco los ángulos que no dependen de ella. Todo en el marco de la imagen
    salvo lo que dice «girado».

    `esquinas` y `reticulo`: los puntos con que se midió [px]. `cruce`: el cruce de las diagonales [px], el centro del campo luminoso. `tam_mm`: los mm por píxel. `angulo_grados`: el ángulo girado,
    el promedio con signo de `angulos_de_las_diagonales_grados` (la diagonal principal UL-DR y la secundaria DL-UR con la horizontal; +alfa y -alfa en un rectángulo sin girar, theta + alfa y
    theta - alfa si está girado theta). `desviacion_de_las_diagonales_grados`: lo que cada diagonal se aparta de las de un cuadrado (principal - 45 y secundaria + 45: la celda 18 del cuaderno);
    que no coincidan no es giro, es que el cuadrilátero marcado no es un cuadrado perfecto. `lados_mm` (superior, derecho, inferior, izquierdo; distancia euclídea), `angulos_interiores_grados`
    (por esquina, UL UR DR DL), `diagonales_mm` (principal, secundaria), `inclinacion_de_los_lados_grados` (de cada lado respecto a su eje en el marco girado; positiva = en el sentido de las
    agujas del reloj, como el ángulo girado), `luz_menos_reticulo_imagen_mm` y `luz_menos_reticulo_girado_mm` ((x, y) del cruce menos el retículo, en la imagen y en el marco girado) y
    `luz_menos_reticulo_modulo_mm`. `matriz_de_giro` (2 x 3 anidada), `pivote`, `esquinas_giradas` y `reticulo_girado`: el marco girado (C.2 lo usa para los bordes luminosos)."""
    estado: str
    esquinas: tuple = ()
    reticulo: tuple | None = None
    cruce: tuple | None = None
    tam_mm: float | None = None
    angulo_grados: float | None = None
    angulos_de_las_diagonales_grados: tuple | None = None
    desviacion_de_las_diagonales_grados: tuple | None = None
    lados_mm: dict | None = None
    angulos_interiores_grados: dict | None = None
    diagonales_mm: tuple | None = None
    inclinacion_de_los_lados_grados: dict | None = None
    luz_menos_reticulo_imagen_mm: tuple | None = None
    luz_menos_reticulo_girado_mm: tuple | None = None
    luz_menos_reticulo_modulo_mm: float | None = None
    matriz_de_giro: tuple | None = None
    pivote: tuple | None = None
    esquinas_giradas: tuple = ()
    reticulo_girado: tuple | None = None

    @property
    def ok(self):
        return self.estado == "ok"

    def como_dict(self):
        def par(p):
            return None if p is None else [float(p[0]), float(p[1])]

        def dic(d):
            return None if d is None else {k: float(v) for k, v in d.items()}

        return {"estado": self.estado, "esquinas": [par(p) for p in self.esquinas], "reticulo": par(self.reticulo), "cruce": par(self.cruce), "tam_mm": self.tam_mm,
                "angulo_grados": self.angulo_grados, "angulos_de_las_diagonales_grados": par(self.angulos_de_las_diagonales_grados),
                "desviacion_de_las_diagonales_grados": par(self.desviacion_de_las_diagonales_grados), "lados_mm": dic(self.lados_mm),
                "angulos_interiores_grados": dic(self.angulos_interiores_grados), "diagonales_mm": par(self.diagonales_mm),
                "inclinacion_de_los_lados_grados": dic(self.inclinacion_de_los_lados_grados), "luz_menos_reticulo_imagen_mm": par(self.luz_menos_reticulo_imagen_mm),
                "luz_menos_reticulo_girado_mm": par(self.luz_menos_reticulo_girado_mm), "luz_menos_reticulo_modulo_mm": self.luz_menos_reticulo_modulo_mm,
                "matriz_de_giro": None if self.matriz_de_giro is None else [[float(v) for v in fila] for fila in self.matriz_de_giro], "pivote": par(self.pivote),
                "esquinas_giradas": [par(p) for p in self.esquinas_giradas], "reticulo_girado": par(self.reticulo_girado)}


# ----------------------------------------------------------------------------- los puntos

def _punto(valor, que="punto"):
    """(x, y) en flotante de un par de números finitos; `ValueError` si no lo es."""
    try:
        a = np.asarray(valor, dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError(f"El {que} es un par (x, y) de números, en píxeles de la película.") from None
    if a.shape != (2,) or not np.isfinite(a).all():
        raise ValueError(f"El {que} es un par (x, y) de números finitos, en píxeles de la película; no {valor!r}.")
    return float(a[0]), float(a[1])


def _escala(tam_mm, permitir_none=False):
    """Los milímetros por píxel como float (`ValueError` si no son un número positivo y finito; None solo si `permitir_none`). Una sola definición de lo que es una escala válida."""
    if tam_mm is None and permitir_none:
        return None
    if not (isinstance(tam_mm, numbers.Real) and not isinstance(tam_mm, bool) and math.isfinite(tam_mm) and tam_mm > 0):
        raise ValueError(f"`tam_mm` es los milímetros por píxel (un número positivo), no {tam_mm!r}.")
    return float(tam_mm)


def punto_de_medida(marca):
    """El punto CON QUE SE MIDE una marca: el `punto` de una `MarcaRefinada` (el refinado, o el clic si quedó «sin refinar»), el `punto` de su diccionario (`como_dict()`, lo que D.1 guarda y
    F.1 lee) o el par (x, y) tal cual. Es la ÚNICA definición de «qué punto se mide»: `clasificar_puntos`, `recuadro_luminoso` y el análisis la usan, y nadie mide con el clic de una marca
    que se refinó."""
    if isinstance(marca, MarcaRefinada):
        return _punto(marca.punto)
    if isinstance(marca, dict):
        if "punto" not in marca:
            raise ValueError("Una marca guardada trae su `punto` (el refinado, o el clic si quedó «sin refinar»).")
        return _punto(marca["punto"])
    return _punto(marca)


def _ordenar_esquinas(esquinas):
    """(los cuatro índices de `esquinas` en el orden UL, UR, DR, DL, None) o (None, qué falló). `esquinas`: cuatro (x, y) ya en orden canónico de coordenadas. El orden es el del ángulo
    alrededor del centroide (con la y hacia abajo crece en sentido horario) empezando por la esquina cuya dirección está más cerca de la superior izquierda; tienen que formar un cuadrilátero
    convexo (los cuatro productos cruz de aristas consecutivas del mismo signo y no nulos)."""
    cx = sum(x for x, _ in esquinas) / 4.0
    cy = sum(y for _, y in esquinas) / 4.0
    angulos = [math.atan2(y - cy, x - cx) for x, y in esquinas]
    orden = sorted(range(4), key=lambda i: (angulos[i], i))

    def lejania_a_la_superior_izquierda(i):
        d = (angulos[i] - ANGULO_DE_LA_ESQUINA_SUPERIOR_IZQUIERDA + math.pi) % (2.0 * math.pi) - math.pi
        return abs(d)

    inicio = min(range(4), key=lambda j: (lejania_a_la_superior_izquierda(orden[j]), j))
    ciclo = [orden[(inicio + j) % 4] for j in range(4)]
    for i in range(4):
        a, b, c = esquinas[ciclo[i]], esquinas[ciclo[(i + 1) % 4]], esquinas[ciclo[(i + 2) % 4]]
        e1, e2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        cruz = e1[0] * e2[1] - e1[1] * e2[0]
        if not cruz > TOLERANCIA_GEOMETRICA * math.hypot(*e1) * math.hypot(*e2):
            return None, "las cuatro esquinas no forman un cuadrilátero convexo"
    return ciclo, None


def _reticulo_dentro(esquinas, reticulo):
    """True si el retículo cae estrictamente dentro del cuadrilátero convexo (UL, UR, DR, DL)."""
    for i in range(4):
        a, b = esquinas[i], esquinas[(i + 1) % 4]
        borde = (b[0] - a[0], b[1] - a[1])
        distancia = (borde[0] * (reticulo[1] - a[1]) - borde[1] * (reticulo[0] - a[0])) / math.hypot(*borde)
        if not distancia > TOLERANCIA_GEOMETRICA:
            return False
    return True


def clasificar_puntos(puntos):
    """Los cinco puntos marcados (en cualquier orden) -> `PuntosClasificados`. Cada punto es un par (x, y), una `MarcaRefinada` o su diccionario (`punto_de_medida`).

    El retículo es el punto más cercano al centroide de los otros cuatro (lo mismo que el más cercano al centroide de los cinco: la distancia al de los otros cuatro es 5/4 de la distancia al de
    los cinco); las esquinas se ordenan por su ángulo alrededor del centroide de las cuatro (UL, UR, DR, DL). Tienen que formar un cuadrilátero convexo que contenga al retículo: si no, el estado
    es «no medible: los puntos no forman el campo (<qué falló>)». No depende del orden de los puntos, del centro de la imagen ni de su forma. `ValueError` si no son cinco puntos o alguno no es
    un par de números finitos."""
    try:
        lista = list(puntos)
    except TypeError:
        raise ValueError("Los puntos son una lista de cinco pares (x, y).") from None
    if len(lista) != 5:
        raise ValueError(f"Los puntos son cinco (las cuatro esquinas del campo luminoso y el retículo), no {len(lista)}.")
    canonicos = sorted(((*punto_de_medida(p), i) for i, p in enumerate(lista)), key=lambda t: (t[0], t[1], t[2]))     # las coordenadas, no el orden de entrada, deciden todo lo que sigue
    xy = [(x, y) for x, y, _ in canonicos]

    def fallo(detalle):
        return PuntosClasificados(f"{MOTIVO_NO_FORMAN_EL_CAMPO} ({detalle})")

    for i in range(5):
        for j in range(i + 1, 5):
            if math.hypot(xy[i][0] - xy[j][0], xy[i][1] - xy[j][1]) <= TOLERANCIA_GEOMETRICA:
                return fallo("hay dos puntos en el mismo lugar")
    centro = (sum(x for x, _ in xy) / 5.0, sum(y for _, y in xy) / 5.0)
    distancias = [math.hypot(x - centro[0], y - centro[1]) for x, y in xy]
    por_distancia = sorted(range(5), key=lambda i: (distancias[i], i))
    if distancias[por_distancia[1]] - distancias[por_distancia[0]] <= TOLERANCIA_GEOMETRICA:
        return fallo("no se distingue cuál de los puntos es el retículo")
    k = por_distancia[0]
    otros = [canonicos[i] for i in range(5) if i != k]
    orden, falla = _ordenar_esquinas([(x, y) for x, y, _ in otros])
    if falla:
        return fallo(falla)
    esquinas = tuple((otros[i][0], otros[i][1]) for i in orden)
    if not _reticulo_dentro(esquinas, xy[k]):
        return fallo("el retículo no cae dentro del cuadrilátero de las cuatro esquinas")
    return PuntosClasificados("ok", xy[k], esquinas, canonicos[k][2], tuple(otros[i][2] for i in orden))


def recuadro_luminoso(puntos):
    """El recuadro del campo luminoso: las cuatro esquinas con que se midió (`punto_de_medida` de cada marca: la refinada o, si quedó «sin refinar», el clic) en el orden superior izquierda,
    superior derecha, inferior derecha, inferior izquierda, o el motivo si los puntos no forman el campo. `puntos`: los cinco, en cualquier orden, como en `clasificar_puntos`. Es la ÚNICA
    definición del recuadro: lo dibujan la ventana (E.1) y la película del PDF (F.1) sobre los puntos guardados."""
    clasificados = clasificar_puntos(puntos)
    if not clasificados.ok:
        return RecuadroLuminoso(clasificados.estado)
    return RecuadroLuminoso("ok", clasificados.esquinas)


# ----------------------------------------------------------------------------- la mancha de tinta

def _recorte(gris, punto, mitad):
    """(subimagen float32, x0, y0) de la ventana cuadrada de `mitad` píxeles a cada lado del píxel más cercano al clic, recortada a la imagen (x0, y0: su esquina en la imagen)."""
    alto, ancho = gris.shape
    cx, cy = int(round(punto[0])), int(round(punto[1]))
    x0, x1 = max(0, cx - mitad), min(ancho, cx + mitad + 1)
    y0, y1 = max(0, cy - mitad), min(alto, cy + mitad + 1)
    return np.asarray(gris[y0:y1, x0:x1], dtype=np.float32), x0, y0


def refinar_marca(gris, punto, P, tam_mm=None, validos=None):
    """Acerca el clic `punto` (x, y) al centro de su marca de tinta -> `MarcaRefinada`.

    La marca es una mancha oscura y compacta cuyo núcleo es casi negro (R3). Se separa de la película con el cierre morfológico (un círculo de `radio_marca_mm`: quita lo oscuro más angosto que
    3 mm y deja el fondo, también el degradado de la penumbra del campo) y se queda con lo que el cierre quitó: la «tinta» de cada píxel, `cierre - gris`. El borde de la mancha es donde esa tinta
    llega a `fraccion_del_contraste_marca` (la mitad) de su máximo junto al clic (y nunca a menos de `contraste_minimo_marca`). De las manchas valen las que miden al menos
    `area_minima_marca_mm2`, caben en un círculo de 3 mm, no tocan el borde de la imagen y tienen su décimo más oscuro POR DEBAJO de `gris_maximo_de_la_tinta` (el límite no se incluye); gana la que tiene su centro más
    cerca del clic. Su centro es el centroide subpíxel de la fracción de tinta de cada píxel (de 0 a 1, contra el fondo de su lugar, sobre la mancha y `borde_blando_marca_mm` a su alrededor): el
    degradado del fondo no lo corre. Si está a `radio_marca_mm` del clic o menos, el punto es ese centro; si no hay mancha de tinta, el clic queda «sin refinar» con su motivo y el punto es el clic.

    `gris`: el arreglo 2D de `Pelicula.gris` (cualquier tipo numérico; no se copia, solo se recorta alrededor del clic). `tam_mm`: mm por píxel (por omisión, la escala del procedimiento:
    `escala_mm(None, P)`). `P`: `VALORES_DE_LA_GEOMETRIA` (o una copia con otros valores). `validos`: la máscara `Pelicula.validos` (bool, la forma de `gris`; por omisión todo tiene dato): lo
    transparente (A.1) no es película ni tinta, así que no se toma por una mancha oscura y una mancha que lo toca está cortada y no se refina. `ValueError` si `gris` no es 2D, el clic no es un
    par finito, faltan claves en `P` o `validos` no tiene la forma de `gris`."""
    if not hasattr(gris, "shape"):
        gris = np.asarray(gris)
    if gris.ndim != 2:
        raise ValueError(f"El gris es un arreglo 2D (alto, ancho), no de forma {gris.shape}.")
    clic = _punto(punto, "clic")
    if validos is not None and np.shape(validos) != gris.shape:
        raise ValueError(f"La máscara de píxeles con dato tiene la forma {np.shape(validos)} y el gris {gris.shape}.")
    faltan = [k for k in CLAVES_DE_LA_MARCA if k not in P]
    if tam_mm is None:
        faltan += [k for k in CLAVES_DE_LA_ESCALA if k not in P]
    if faltan:
        raise ValueError(f"A `P` le faltan los parámetros {faltan}.")
    tam_mm = _escala(escala_mm(None, P) if tam_mm is None else tam_mm)
    radio_px = P["radio_marca_mm"] / tam_mm

    def sin_refinar(motivo):
        return MarcaRefinada(ESTADO_SIN_REFINAR, clic, clic, 0.0, 0.0, radio_px, motivo)

    sin_mancha = f"sin refinar: no hay una mancha de tinta a menos de {P['radio_marca_mm']:g} mm del clic"
    alto, ancho = gris.shape
    if not (0 <= clic[0] <= ancho - 1 and 0 <= clic[1] <= alto - 1):
        return sin_refinar("sin refinar: el clic está fuera de la imagen")
    if radio_px < 2.0:
        return sin_refinar(f"sin refinar: el radio de búsqueda ({P['radio_marca_mm']:g} mm) mide menos de 2 píxeles con esta escala")
    if radio_px > RADIO_MAXIMO_EN_PIXELES:
        raise ValueError(f"El radio de búsqueda ({P['radio_marca_mm']:g} mm) mide {radio_px:.0f} píxeles con esta escala: más de {RADIO_MAXIMO_EN_PIXELES}, el cierre de la mancha no es de ese tamaño.")
    elemento = int(math.ceil(radio_px))                       # el radio, en píxeles, del círculo del cierre
    mitad = int(math.ceil(2.0 * radio_px)) + 2                # la ventana donde se buscan manchas: el clic +- 2 radios (más lejos no se acepta nada)
    recorte, x0, y0 = _recorte(gris, clic, mitad + elemento)  # y alrededor de ella, lo que el cierre necesita; lo que queda fuera de la imagen no cuenta (el cierre lo ignora)
    sin_dato = None
    if validos is not None:
        con_dato = np.asarray(validos[y0:y0 + recorte.shape[0], x0:x0 + recorte.shape[1]], dtype=bool)
        if not con_dato.any():
            return sin_refinar("sin refinar: no hay píxeles con dato alrededor del clic")
        if not con_dato.all():
            recorte = recorte[tuple(ndi.distance_transform_edt(~con_dato, return_distances=False, return_indices=True))]    # sin dato: sigue la película de alrededor (el vecino con dato más cercano), no es tinta
            sin_dato = ~con_dato
    cierre = cv2.morphologyEx(recorte, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * elemento + 1, 2 * elemento + 1)))
    ya, xa = max(0, int(round(clic[1])) - mitad) - y0, max(0, int(round(clic[0])) - mitad) - x0
    yb, xb = min(alto, int(round(clic[1])) + mitad + 1) - y0, min(ancho, int(round(clic[0])) + mitad + 1) - x0
    gris_local, tinta = recorte[ya:yb, xa:xb], (cierre - recorte)[ya:yb, xa:xb]
    sin_dato = None if sin_dato is None else ndi.binary_dilation(sin_dato, structure=np.ones((3, 3), bool))[ya:yb, xa:xb]
    x0, y0 = x0 + xa, y0 + ya                                 # la esquina de la ventana de búsqueda en la imagen
    yy, xx = np.mgrid[y0:y0 + tinta.shape[0], x0:x0 + tinta.shape[1]]
    pico = float(tinta[np.hypot(xx - clic[0], yy - clic[1]) <= radio_px].max())
    if pico < P["contraste_minimo_marca"]:
        return sin_refinar(f"sin refinar: no hay una mancha más oscura que su entorno a menos de {P['radio_marca_mm']:g} mm del clic")
    umbral = max(P["contraste_minimo_marca"], P["fraccion_del_contraste_marca"] * pico)
    manchas, cuantas = ndi.label(ndi.binary_fill_holes(tinta >= umbral), structure=np.ones((3, 3), bool))
    area_minima = P["area_minima_marca_mm2"] / (tam_mm * tam_mm)
    mejor = None
    for numero in range(1, cuantas + 1):
        mancha = manchas == numero
        area = int(mancha.sum())
        filas, columnas = np.nonzero(mancha)
        if (area < area_minima or max(filas.max() - filas.min(), columnas.max() - columnas.min()) + 1 > 2.0 * radio_px
                or filas.min() == 0 or columnas.min() == 0 or filas.max() == mancha.shape[0] - 1 or columnas.max() == mancha.shape[1] - 1):
            continue    # una mota; más ancha que un círculo de 3 mm; o cortada por la ventana (donde la ventana termina en el borde de la imagen, por el borde de la imagen): su centro sería el de una parte
        if sin_dato is not None and (mancha & sin_dato).any():
            continue    # toca lo que no tiene dato: está cortada por la transparencia
        nucleo = float(np.percentile(gris_local[mancha], 10))
        if nucleo >= P["gris_maximo_de_la_tinta"]:
            continue    # oscura, pero no es tinta (un núcleo que LLEGA al límite tampoco lo es: 10.0 es lo que dan las motas de EPSON029 y ref40)
        lejos = math.hypot(float(xx[mancha].mean()) - clic[0], float(yy[mancha].mean()) - clic[1])
        if mejor is None or lejos < mejor[0]:
            mejor = (lejos, mancha, area, nucleo, float(tinta[mancha].max()))
    if mejor is None:
        return sin_refinar(sin_mancha)
    _, mancha, area, nucleo, contraste = mejor
    fraccion_de_tinta = np.clip(tinta / np.maximum(gris_local + tinta - nucleo, 1.0), 0.0, 1.0)     # el cierre (gris + tinta) es la película sin tinta; el núcleo, el nivel de la tinta
    vecindad = ndi.binary_dilation(mancha, structure=np.ones((3, 3), bool), iterations=max(1, int(math.ceil(P["borde_blando_marca_mm"] / tam_mm))))
    peso = np.where(vecindad, fraccion_de_tinta, 0.0).astype(np.float64)    # en doble precisión: la suma en float32 depende de cómo caiga el arreglo en la memoria (1e-7 relativo: 4e-5 px a 450 px de la esquina)
    suma = float(peso.sum())
    centro = (float((peso * xx).sum() / suma), float((peso * yy).sum() / suma))
    lejos = math.hypot(centro[0] - clic[0], centro[1] - clic[1])
    if lejos > radio_px:
        return sin_refinar(sin_mancha)
    return MarcaRefinada(ESTADO_REFINADA, clic, centro, lejos, lejos * tam_mm, radio_px, None, float(area * tam_mm * tam_mm), contraste, nucleo)


# ----------------------------------------------------------------------------- el giro

def _numero(valor, que):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"El {que} es un número finito, no {valor!r}.") from None
    if not math.isfinite(v):
        raise ValueError(f"El {que} es un número finito, no {valor!r}.")
    return v


def matriz_giro(centro, angulo):
    """La matriz 2 x 3 de `cv2.getRotationMatrix2D(centro, angulo, 1)` en float64 (la de OpenCV redondea el centro a float32): UNA definición para la imagen (`cv2.warpAffine(imagen, M, ...)`)
    y para los puntos (`transformar_puntos`). `angulo` en grados: positivo = giro en sentido ANTIHORARIO en la pantalla (la y hacia abajo); un campo girado theta en sentido horario (ángulo
    +theta de `geometria_luz`) se endereza con `matriz_giro(cruce, theta)`. El centro queda fijo."""
    cx, cy = _punto(centro, "centro del giro")
    a = _numero(angulo, "ángulo")
    radianes = math.radians(a)
    alfa, beta = math.cos(radianes), math.sin(radianes)
    return np.array([[alfa, beta, (1.0 - alfa) * cx - beta * cy], [-beta, alfa, beta * cx + (1.0 - alfa) * cy]], dtype=np.float64)


def transformar_puntos(M, puntos):
    """Los puntos (x, y) llevados por la matriz 2 x 3 `M`: [(x', y'), ...] en float64. La misma cuenta que `cv2.transform` y que `warpAffine` aplican a la imagen."""
    m = np.asarray(M, dtype=np.float64)
    if m.shape != (2, 3):
        raise ValueError(f"La matriz de giro es de 2 x 3, no de forma {m.shape}.")
    salida = []
    for p in puntos:
        x, y = _punto(p)
        salida.append((float(m[0, 0] * x + m[0, 1] * y + m[0, 2]), float(m[1, 0] * x + m[1, 1] * y + m[1, 2])))
    return salida


# ----------------------------------------------------------------------------- la geometría del campo

def _inclinacion(a, b, horizontal):
    """Cuánto se aparta de su eje el lado a -> b, en grados y positivo en sentido horario. Un lado horizontal va de izquierda a derecha y se mide contra la horizontal (`atan2(dy, dx)`); uno
    vertical va de arriba hacia abajo y se mide contra la vertical (`atan2(-dx, dy)`): girar todo el cuadrilátero un ángulo da ese mismo ángulo en los cuatro."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    return math.degrees(math.atan2(dy, dx) if horizontal else math.atan2(-dx, dy))


def geometria_luz(esquinas, reticulo, tam_mm, pivote=None):
    """La geometría del campo luminoso de las cuatro `esquinas` (en cualquier orden) y el `reticulo` (x, y en píxeles de la imagen) -> `GeometriaLuz`. `tam_mm`: mm por píxel (None: «no
    medible», sin escala). `pivote`: el centro del giro del marco girado (por omisión el cruce de diagonales; no cambia ninguna medida, solo las posiciones de los puntos girados).

    Las esquinas se ordenan igual que en `clasificar_puntos` y tienen que formar un cuadrilátero convexo que contenga al retículo (si no, «no medible: los puntos no forman el campo»).
    `ValueError` si las esquinas no son cuatro pares finitos o `tam_mm` no es un número positivo."""
    try:
        lista = list(esquinas)
    except TypeError:
        raise ValueError("Las esquinas son una lista de cuatro pares (x, y).") from None
    if len(lista) != 4:
        raise ValueError(f"Las esquinas del campo luminoso son cuatro, no {len(lista)}.")
    puntos = sorted(punto_de_medida(p) for p in lista)
    ret = punto_de_medida(reticulo)
    tam_mm = _escala(tam_mm, permitir_none=True)
    pivote = None if pivote is None else _punto(pivote, "pivote")
    orden, falla = _ordenar_esquinas(puntos)
    ordenadas = None if falla else tuple(puntos[i] for i in orden)
    if falla or not _reticulo_dentro(ordenadas, ret):
        return GeometriaLuz(f"{MOTIVO_NO_FORMAN_EL_CAMPO} ({falla or 'el retículo no cae dentro del cuadrilátero de las cuatro esquinas'})")
    if tam_mm is None:
        return GeometriaLuz(MOTIVO_SIN_ESCALA, ordenadas, ret)
    ul, ur, dr, dl = ordenadas
    # el cruce de las diagonales UL-DR y UR-DL
    d = (ul[0] - dr[0]) * (ur[1] - dl[1]) - (ul[1] - dr[1]) * (ur[0] - dl[0])
    a, b = ul[0] * dr[1] - ul[1] * dr[0], ur[0] * dl[1] - ur[1] * dl[0]
    cruce = ((a * (ur[0] - dl[0]) - (ul[0] - dr[0]) * b) / d, (a * (ur[1] - dl[1]) - (ul[1] - dr[1]) * b) / d)
    # el ángulo: el promedio, con signo, de los ángulos de las dos diagonales con la horizontal (R9, paso 3), y la desviación de cada una respecto a las de un cuadrado
    principal = math.degrees(math.atan2(dr[1] - ul[1], dr[0] - ul[0]))
    secundaria = math.degrees(math.atan2(ur[1] - dl[1], ur[0] - dl[0]))
    angulo = (principal + secundaria) / 2.0
    lados_mm = {nombre: math.hypot(q[0] - p[0], q[1] - p[1]) * tam_mm for nombre, (p, q) in zip(LADOS, ((ul, ur), (ur, dr), (dr, dl), (dl, ul)))}
    interiores = {}
    for i, nombre in enumerate(ESQUINAS):
        p, antes, despues = ordenadas[i], ordenadas[i - 1], ordenadas[(i + 1) % 4]
        v1, v2 = (antes[0] - p[0], antes[1] - p[1]), (despues[0] - p[0], despues[1] - p[1])
        interiores[nombre] = math.degrees(math.atan2(abs(v1[0] * v2[1] - v1[1] * v2[0]), v1[0] * v2[0] + v1[1] * v2[1]))
    diagonales = (math.hypot(dr[0] - ul[0], dr[1] - ul[1]) * tam_mm, math.hypot(ur[0] - dl[0], ur[1] - dl[1]) * tam_mm)
    # el marco girado: la misma matriz que girará la imagen (C.2); el pivote no cambia ninguna de estas medidas
    centro_del_giro = cruce if pivote is None else pivote
    M = matriz_giro(centro_del_giro, angulo)
    giradas = transformar_puntos(M, ordenadas)
    ret_girado = transformar_puntos(M, [ret])[0]
    gul, gur, gdr, gdl = giradas
    inclinacion = {"superior": _inclinacion(gul, gur, True), "derecho": _inclinacion(gur, gdr, False), "inferior": _inclinacion(gdl, gdr, True), "izquierdo": _inclinacion(gul, gdl, False)}
    luz_menos_reticulo = ((cruce[0] - ret[0]) * tam_mm, (cruce[1] - ret[1]) * tam_mm)
    girado = (float(M[0, 0] * luz_menos_reticulo[0] + M[0, 1] * luz_menos_reticulo[1]), float(M[1, 0] * luz_menos_reticulo[0] + M[1, 1] * luz_menos_reticulo[1]))
    return GeometriaLuz(
        estado="ok", esquinas=ordenadas, reticulo=ret, cruce=cruce, tam_mm=tam_mm, angulo_grados=angulo, angulos_de_las_diagonales_grados=(principal, secundaria),
        desviacion_de_las_diagonales_grados=(principal - 45.0, secundaria + 45.0), lados_mm=lados_mm, angulos_interiores_grados=interiores, diagonales_mm=diagonales,
        inclinacion_de_los_lados_grados=inclinacion, luz_menos_reticulo_imagen_mm=luz_menos_reticulo, luz_menos_reticulo_girado_mm=girado,
        luz_menos_reticulo_modulo_mm=math.hypot(*luz_menos_reticulo), matriz_de_giro=tuple(tuple(float(v) for v in fila) for fila in M), pivote=centro_del_giro,
        esquinas_giradas=tuple(giradas), reticulo_girado=ret_girado)
