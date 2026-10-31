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

C.2 (R9, pasos 4 a 12) agrega, sobre la película ya girada: `girar` (recorta a la película y gira solo eso, con la misma matriz que los puntos), `perfil_central` (la banda de 1 mm por el cruce de diagonales),
`medir_perfil` (la meseta de la zona central sin la marca del retículo, la altura media, los bordes DESDE la meseta hacia afuera con interpolación lineal, el FWHM, el centro de radiación y la penumbra 80-20),
`bordes_luz` (la intersección analítica de la línea del perfil con los lados), `coincidencia` (por lado, positiva hacia afuera), `analizar` (arma todo con UNA llamada a `piso_de_pelicula`) y `valores_medidos` (la
única definición de lo que se guarda). Cada capa, R, G, B y el gris, se mide por separado con UNA base, la misma para las cuatro (PD3: ninguna regla las compara): desde OD.1 (DA-87, 21-10) la densidad óptica neta normalizada entre el piso y la
meseta por omisión (`BASE_POR_OMISION`, un parámetro más, `base_de_la_medida`, que viaja con cada análisis) o, si el parámetro lo pide o el registro no lo trae, el valor de píxel normalizado de antes; con la netOD, una
capa con la meseta recortada por el escáner (el rojo a 800 UM) es «no medible». El
resultado trae la película recortada y girada, que el barrido de C.3 reutiliza, y nunca la página. Sigue siendo la versión `PM-1`: C.1, C.2 y C.3 son las tres entregas de un mismo motor y ningún análisis
guardado usa todavía otra. La raíz del resultado dice «ok» si al menos una capa se midió por completo (si no, `MOTIVO_NINGUNA_CAPA`); los bordes luminosos y luz - retículo salen de la geometría y
se entregan aunque el piso o las capas no se puedan medir. La meseta es el nivel medio de la zona central (el plan): con la cúpula de las películas reales el 50 % de esa media no es el 50 % de la
dosis del centro del campo (ver `medir_perfil`).

C.3 (R9, paso 11) agrega `barrido(resultado)`: con la película ya girada, el piso y los bordes luminosos que `analizar` trae (no gira, no vuelve a calcular el piso y no cambia el resultado), mide con la MISMA
`medir_perfil` bandas de `banda_perfil_mm` ancladas en el cruce de diagonales (la banda 0 es EXACTAMENTE el perfil central), las del crossplane sobre las filas y las del inplane sobre las columnas, en la misma
zona central de la meseta para las cuatro capas: ±`fraccion_meseta` / 2 de la distancia entre los bordes luminosos de la línea central PERPENDICULAR, alrededor del cruce (79 bandas en un 10 x 10). No tiene ningún
parámetro ni descarta ninguna banda (las que no se pueden medir quedan en la lista con su motivo); del FWHM de las medibles da la media, la mediana, la desviación estándar (la de la población, la `np.std` del
resto de la aplicación) y cuántas son. El barrido se muestra y no se guarda: quien lo necesite lo vuelve a calcular con esta misma función.

CD.6 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md; DA-92) agrega la TERCERA base, `BASE_DOSIS`: con la curva de dosis de una calibración (`analisisImagenes.curva_dosis`, CD.3) cada perfil se mide en DOSIS,
convertida píxel a píxel desde la netOD con la curva de SU capa (`curva_de_la_capa`), y el borde está donde la dosis vale la mitad de la de la meseta (H4: no es el borde a la mitad de la netOD). Se pide
con `parametros["base_de_la_medida"] = BASE_DOSIS` y `analizar(..., curva=, cadena=)`; una capa se mide en dosis solo si cumple las cinco condiciones de DC8 (`base_de_la_capa`, UNA regla) y, si no,
queda «no medible en dosis: <motivo>» (una vista nunca mezcla las dos bases: sus números en netOD son los del análisis en netOD). `se_puede_pasar_a_dosis` es la regla del botón «Ver en dosis» sobre la
capa reportada y `curva_efectiva` la curva que usa un análisis (la válida más reciente con la cadena de captura de la película). Sin curva y con las bases de siempre, todo es idéntico a OD.1 bit a bit.
El motor no lee la base: las calibraciones le llegan como argumento.

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
from dataclasses import dataclass, field, replace

import cv2
import numpy as np
from scipy import ndimage as ndi

from analisisImagenes.pelicula import CAPAS_DEL_PISO, CLAVES_DE_LA_ESCALA, ESQUINAS, FRACCION_DE_RECORTE_MAXIMA, MARGEN_DEL_RECORTE, MOTIVO_MESETA_RECORTADA, NIVEL_DE_RECORTE, PARAMETROS_DEL_PISO, escala_mm, meseta_recortada, piso_de_pelicula
from analisisImagenes.pelicula import ADJETIVO_DE_LA_CAPA, _abrir_con_pillow, _equipo_de_la_imagen, leer_pelicula          # CD.6: el nombre de cada capa en los motivos y la cadena de captura de la película
from analisisImagenes.curva_dosis import ESTADO_VALIDA, PREFIJO_GUIA, CurvaDeDosis, _texto_de_la_cadena, cadena_de_captura, curva_desde_dict          # CD.6: la curva de dosis (CD.3), su ÚNICA definición

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


# ============================================================================= C.2: los perfiles por capa, el FWHM, la coincidencia por lado, los tres centros y la penumbra (R9, pasos 4 a 12)

# OD.1 (DA-87, 21-10): las DOS bases del análisis. Cada perfil se normaliza entre el piso (0) y la meseta (1) y su borde de radiación está donde la señal vale `altura_media` (0.5):
#   valor de píxel: n = (piso - v) / (piso - meseta); el 0.5 está en el nivel de la media ARITMÉTICA entre el piso y la meseta (la base del 09-10);
#   densidad óptica neta: n = log10(piso / v) / log10(piso / meseta), la netOD de Devic et al. 2004 con el piso como I0 (Vargas-Segura et al. 2023, ec. 1); el 0.5 está en la media GEOMÉTRICA.
# Y la banda de 1 mm de cada perfil se promedia EN ESA BASE (`perfil_central(base=)`; decisión OD1-REV-D1, 22-10): en netOD, como la imagen ya convertida píxel a píxel (la media de log10 por píxel).
# La netOD es la base por omisión (decisión del físico del 21-10); `BASE_VALOR_DE_PIXEL` sigue siendo una opción y la base de todo registro guardado sin el parámetro `base_de_la_medida`.
BASE_VALOR_DE_PIXEL = "valor de píxel normalizado"
BASE_DENSIDAD_OPTICA = "densidad óptica neta"
BASE_DOSIS = "dosis"                                           # CD.6 (DA-92): la dosis de la curva de cada capa, desde la netOD; solo con una curva (`curva_de_la_capa`) y nunca por omisión
BASES = (BASE_DENSIDAD_OPTICA, BASE_VALOR_DE_PIXEL, BASE_DOSIS)
BASE_POR_OMISION = BASE_DENSIDAD_OPTICA                        # EL lugar para cambiar la base del análisis (una línea): viaja como `PARAMETROS["base_de_la_medida"]` y cada análisis guarda la que usó
VP_MINIMO = 0.5                                                # medio nivel de 8 bits: por debajo, el escáner recortó y log10(piso / v) no existe; se toma este piso del logaritmo (el del pre-vuelo `od_prevuelo.py`)
# CD.2: la regla del recorte de la netOD (NIVEL_DE_RECORTE, FRACCION_DE_RECORTE_MAXIMA, MARGEN_DEL_RECORTE y MOTIVO_MESETA_RECORTADA, de OD.1 y OD.1c) vive en `pelicula.meseta_recortada`, la
# ÚNICA definición: la usan `medir_perfil` y la medición de una pieza de calibración (`pelicula.medir_pieza_uniforme`). Este módulo re-exporta las cuatro constantes con su nombre (el import
# de arriba: `placa_mensual.NIVEL_DE_RECORTE` sigue valiendo 1.5); sus comentarios (los límites, la reapertura y lo medido en las 8 películas reales) se mudaron con ellas a `pelicula.py`.
# Estas cuatro líneas ocupan las de sus antiguas definiciones: ninguna otra línea del módulo se mueve (Trampa 5).
EJES = ("crossplane", "inplane")                            # crossplane = horizontal (recorre x, la banda promedia filas); inplane = vertical (recorre y, la banda promedia columnas)
LADOS_DEL_EJE = {"crossplane": ("izquierdo", "derecho"), "inplane": ("superior", "inferior")}     # (menor, mayor) a lo largo del eje
LADOS_DE_LA_COINCIDENCIA = ("izquierdo", "derecho", "superior", "inferior")
SIGNO_DEL_LADO = {"izquierdo": -1.0, "derecho": 1.0, "superior": -1.0, "inferior": 1.0}          # positivo hacia afuera: con x a la derecha e y hacia abajo, afuera es -x, +x, -y y +y
CLAVES_DE_VALORES_MEDIDOS = ("estado", "fwhm_crossplane_mm", "fwhm_inplane_mm", "desfase_izquierdo_mm", "desfase_derecho_mm", "desfase_superior_mm", "desfase_inferior_mm")      # lo que se guarda (D.1)
AVISO_PENUMBRA_INCOMPLETA = "incompleta: el perfil llega al borde de la película antes del {porcentaje:g} %"
AVISO_PENUMBRA_NO_MONOTONA = "no monótona: el perfil no cruza el {alto:g} %, el {medio:g} % y el {bajo:g} % en ese orden"
MOTIVO_NINGUNA_CAPA = "no medible: ninguna de las cuatro capas se pudo medir por completo; cada capa dice su motivo"      # el estado de la raíz cuando el piso y la geometría son buenos pero ninguna capa quedó con sus dos perfiles medidos
PASO_DE_LA_CAJA = 8                                           # la caja de la película se busca en una versión de la imagen con 1 píxel de cada 8 (sin copiar la página)
UMBRAL_DE_VALIDEZ = 0.999                                     # un píxel girado tiene dato si el 99.9 % de lo que lo forma (los 4 vecinos de la interpolación) lo tenía

PARAMETROS_DE_LA_MEDIDA = {
    "margen_recorte_mm": {
        "valor": 2.0, "unidad": "mm",
        "motivo": "Antes de girar se recorta la imagen a la caja de la película más este margen por cada lado: lo bastante para que el borde de la película y los vecinos que usa la interpolación del giro queden "
                  "dentro del recorte, y lo bastante poco para no girar la página (girar una página de 6600 x 5100 en cuatro capas costó 984 MB de más y recortando antes 352 MB). No cambia ninguna medida mientras "
                  "supere a `margen_borde_mm`."},
    "banda_perfil_mm": {
        "valor": 1.0, "unidad": "mm",
        "motivo": "Cada perfil es el promedio de las filas (o columnas) cuyo centro cae a 0.5 mm o menos del cruce de diagonales: una sola fila deja de 0.15 a 0.4 mm de ruido en el FWHM del azul (N5 de R3) y "
                  "una banda de 1 mm lo baja a menos de 0.05 mm sin mezclar la forma del campo (el borde es recto en esa distancia). Es también el ancho de las bandas del barrido de C.3."},
    "fraccion_meseta": {
        "valor": 0.80, "unidad": "fracción",
        "motivo": "La zona central de la meseta va de -40 % a +40 % de la distancia entre los dos bordes luminosos de esa línea, alrededor del cruce de diagonales: en un 10 x 10, 1 cm hacia dentro de cada lado, la "
                  "distancia que IEC 60976 usa en los ejes para su zona aplanada (aquí es un criterio geométrico, no la evaluación de planitud de la norma). Sale de las marcas y no es un número libre (PD1); "
                  "llevarla a 44.45 mm como en el cuaderno cambia el FWHM 0.016 mm o menos."},
    "excepcion_centro_mm": {
        "valor": 3.8, "unidad": "mm",
        "motivo": "La marca del retículo (tinta o anillo de presión) está dentro de la meseta y no es dosis: se excluye de la media de la meseta 3.8 mm a cada lado del RETÍCULO REFINADO (90 píxeles a 600 dpi, la "
                  "excepción del cuaderno), no del cruce: con el retículo corrido 4 mm del cruce una exclusión centrada en el cruce dejaría la tinta dentro."},
    "muestras_minimas_de_la_meseta": {
        "valor": 200, "unidad": "muestras",
        "motivo": "Con menos de 200 muestras de perfil en la zona central (8 mm a 600 dpi, una décima parte de lo que mide en un 10 x 10) la media de la meseta no es estable ni distingue una mota de un nivel: "
                  "se prefiere decir «no medible». Es un valor del implementador, sin medición que lo respalde: vetable."},
    "altura_media": {
        "valor": 0.5, "unidad": "fracción",
        "motivo": "El borde de radiación está a mitad de camino entre el piso y la meseta: (piso - v) / (piso - meseta) = 0.5, la definición del ancho a media altura (R9, paso 7). Con la base de valor de píxel "
                  "no es el 50 % de la dosis (R6): sin la curva del lote ninguna capa es dosis."},
    "penumbra_alta": {
        "valor": 0.8, "unidad": "fracción",
        "motivo": "La penumbra se mide entre el 80 % y el 20 % de la señal (0 en el piso, 1 en la meseta), el rango que usa el cuaderno en la celda 93. Sin calibración no es la penumbra dosimétrica de TG-142."},
    "penumbra_baja": {
        "valor": 0.2, "unidad": "fracción",
        "motivo": "El 20 % de la señal es el extremo de afuera de la penumbra: si el perfil llega al borde de la película antes de cruzarlo, la penumbra de ese lado queda «incompleta» y no se inventa."},
    "suavizado_perfil_mm": {
        "valor": 0.5, "unidad": "mm",
        "motivo": "Antes de buscar los cruces el perfil se promedia con una ventana de 0.5 mm: una mota fina sobre la línea central (EPSON007, azul inplane: 96.04 mm sin suavizar y 99.3 con él) deja de cruzar la altura media "
                  "y el borde no se pierde. Medido otra vez en C.2 sobre diez películas reales y la sintética: sin sesgo (el borde es simétrico alrededor de su cruce) y con menos ruido. Con 0 no se suaviza. "
                  "Vetable: es el único valor que no estaba en el plan sino en su obstáculo 7."},
}
PARAMETROS.update(copy.deepcopy(PARAMETROS_DE_LA_MEDIDA))
VALORES_DE_LA_GEOMETRIA.update({nombre: copy.deepcopy(parametro["valor"]) for nombre, parametro in PARAMETROS_DE_LA_MEDIDA.items()})      # el diccionario plano crece solo: lleva TODOS los parámetros del análisis

# OD.1: la base del análisis es un parámetro más (el número 41): viaja con cada análisis guardado y al reabrirlo (o al imprimirlo) se mide con ESA base aunque `BASE_POR_OMISION` cambie (la copia guardada
# manda, DA-81). No la pide `analizar` por nombre: un registro guardado antes de OD.1 no la tiene y se mide como se midió, en valor de píxel.
PARAMETROS_DE_LA_BASE = {
    "base_de_la_medida": {
        "valor": BASE_POR_OMISION, "unidad": "base (texto)",
        "motivo": "La base en que se normaliza cada perfil antes de buscar sus bordes: «densidad óptica neta» (por omisión: log10(piso / valor), la netOD de Devic et al. 2004 con el piso como I0, normalizada a 0 en el piso y "
                  "1 en la meseta; su altura media está en la media geométrica del piso y la meseta; la banda de 1 mm de cada perfil se promedia como la imagen ya convertida píxel a píxel, con la media de log10 por píxel) "
                  "o «valor de píxel normalizado» ((piso - valor) / (piso - meseta), la base de antes, con la media aritmética) o, desde CD.6, «dosis» (la dosis de la curva de cada capa desde la netOD: solo con una "
                  "curva de dosis, `analizar(..., curva=, cadena=)`, y nunca por omisión). Se cambia en UNA "
                  "línea, `BASE_POR_OMISION` de este archivo, y cada análisis guarda la que usó: reabrirlo o imprimirlo lo mide con ESA base aunque la constante cambie; uno guardado sin este parámetro se mide en valor de píxel. "
                  "Medido el 21-10 en ocho escaneos: el verde en valor de píxel sale de +1.0 a +2.8 mm más ancho que el campo luminoso y en netOD de -0.6 a +1.0 mm (logs/OD/); el rojo a 800 UM está recortado por el "
                  "escáner y en netOD es «no medible»."},
}
PARAMETROS.update(copy.deepcopy(PARAMETROS_DE_LA_BASE))
VALORES_DE_LA_GEOMETRIA.update({nombre: copy.deepcopy(parametro["valor"]) for nombre, parametro in PARAMETROS_DE_LA_BASE.items()})

# CD.6: el parámetro 42. Solo lo lee un análisis en dosis (no está en `CLAVES_QUE_PIDE_ANALIZAR`): un registro guardado antes de CD.6 no lo trae y se mide con el de fábrica, como OD.1 hizo con la base.
PARAMETROS_DE_LA_DOSIS = {
    "diferencia_virgen_maxima_pct": {
        "valor": 2.0, "unidad": "%",
        "motivo": "En un análisis en dosis, si el piso de una capa (el valor de la película virgen montada) y el I0 del cero de la curva (sus piezas de 0 cGy o la virgen con que se calibró) difieren "
                  "más que esto, la ventana lo avisa sin bloquear: la netOD del análisis se mide contra su virgen y la de la curva contra su cero, y si no son la misma película la dosis se corre (otro "
                  "lote, otra sesión de escaneo). Es la propuesta del plan (§9), sin una medición detrás: se recalibra con la primera calibración real (CD.10). Vetable."},
}
PARAMETROS.update(copy.deepcopy(PARAMETROS_DE_LA_DOSIS))
VALORES_DE_LA_GEOMETRIA.update({nombre: copy.deepcopy(parametro["valor"]) for nombre, parametro in PARAMETROS_DE_LA_DOSIS.items()})
CLAVES_QUE_PIDE_LA_MEDIDA = tuple(PARAMETROS_DE_LA_MEDIDA) + ("umbral_fondo", "margen_borde_mm", "delta_tinta", "contraste_minimo")      # lo que `medir_perfil` y `perfil_central` leen de `P`
CLAVES_QUE_PIDE_ANALIZAR = CLAVES_QUE_PIDE_LA_MEDIDA + CLAVES_DE_LA_ESCALA


# ----------------------------------------------------------------------------- lo que devuelven las funciones de C.2

@dataclass(frozen=True, eq=False)
class CapaGirada:
    """Una capa de la película ya girada, con lo necesario para sacar un perfil: `nombre` (R, G, B o gris), `datos` (float32, alto x ancho, en niveles de 8 bits), `validos` (bool: el píxel tiene dato),
    `pelicula` (bool: tiene dato y no es el fondo del escáner), `origen` (x, y: la coordenada en el MARCO GIRADO del elemento [0, 0] del arreglo), `cruce` (x, y: el cruce de diagonales en el marco girado)
    y `tam_mm` (milímetros por píxel). Es una vista de `PeliculaGirada`: no copia nada."""
    nombre: str
    datos: np.ndarray = field(repr=False)
    validos: np.ndarray = field(repr=False)
    pelicula: np.ndarray = field(repr=False)
    origen: tuple
    cruce: tuple
    tam_mm: float


@dataclass(frozen=True, eq=False)
class PeliculaGirada:
    """La película recortada y girada: lo que C.2 mide y lo que C.3, la ventana y el PDF reutilizan SIN volver a girar la página (el resultado conserva esto y nunca la página).

    `capas`: {R, G, B, gris} -> float32 (alto, ancho), solo lectura, en el marco girado. `validos`: ninguno de los píxeles que forman cada uno faltaba (lo que entra por el borde del giro es «sin dato»).
    `pelicula`: con dato y no fondo del escáner. `origen`: (x, y) en el marco girado del elemento [0, 0]; la coordenada de cada píxel (columna i, fila j) es (origen[0] + i, origen[1] + j). `matriz`: la
    de 2 x 3 que lleva un punto de la imagen al marco girado (la de `GeometriaLuz`). `caja`: (x0, y0, x1, y1) lo que se recortó de la imagen original antes de girar (x1 e y1 exclusivos). `cruce`: el
    cruce de diagonales en el marco girado. `tam_mm`: milímetros por píxel."""
    capas: dict = field(repr=False)
    validos: np.ndarray = field(repr=False)
    pelicula: np.ndarray = field(repr=False)
    origen: tuple
    matriz: tuple
    caja: tuple
    cruce: tuple
    tam_mm: float

    def capa(self, nombre):
        return CapaGirada(nombre, self.capas[nombre], self.validos, self.pelicula, self.origen, self.cruce, self.tam_mm)

    def memoria_bytes(self):
        return int(sum(a.nbytes for a in self.capas.values()) + self.validos.nbytes + self.pelicula.nbytes)


@dataclass(frozen=True, eq=False)
class PerfilCentral:
    """Un perfil: el promedio de una banda de `n_filas` filas (crossplane) o columnas (inplane) de una capa girada, en la base con que se pidió (`perfil_central(base=)`: aritmético en valor de píxel, la media de
    log10 por píxel en netOD). `valores` (float64, uno por columna o fila de la capa, en niveles de 8 bits) vale NaN
    donde algún píxel de la banda no tiene dato o no es película, y hasta `margen_borde_mm` de ellos (el borde de la película no es película limpia). `desde_px`: la coordenada, en el marco girado, de
    `valores[0]` a lo largo del eje. `filas_px`: (primera, fin) de la banda perpendicular al eje, en el marco girado, `fin` exclusivo. `banda`: 0 es el perfil central; k, la banda k de un milímetro."""
    capa: str
    eje: str
    banda: int
    valores: np.ndarray = field(repr=False)
    desde_px: int
    filas_px: tuple
    n_filas: int
    tam_mm: float


@dataclass(frozen=True, eq=False)
class MedidaDePerfil:
    """Lo que `medir_perfil` midió en un perfil. `estado`: «ok» o «no medible: perfil <eje>: <motivo>». Las posiciones son coordenadas del marco girado a lo largo del eje, en píxeles; el par de cada
    medida es (menor, mayor): (izquierdo, derecho) en crossplane y (superior, inferior) en inplane.

    `centro_px`: el cruce de diagonales a lo largo del eje. `piso`, `meseta` (el nivel medio de la zona central sin la exclusión del retículo y sin la tinta), `altura_media`, `nivel_penumbra_alta` y
    `nivel_penumbra_baja`: niveles de 8 bits. `zona_px` y `exclusion_px`: los límites de la zona central y de la exclusión del retículo (None si no hay retículo). `muestras_meseta`: cuántas muestras
    entraron a la media. `bordes_luz_px`: los bordes luminosos de esa línea. `bordes_rad_px`: los bordes de radiación al 50 % (None si no se alcanzó). `fwhm_mm` y `centro_rad_px`: solo si están los dos
    bordes. `penumbras_mm`: la penumbra 80 a 20 % de cada lado (None si quedó incompleta). `avisos`: los de la penumbra. `perfil` y `suavizado`: el perfil medido y el que se usó para buscar los cruces."""
    estado: str
    capa: str
    eje: str
    tam_mm: float | None
    centro_px: float | None
    perfil: PerfilCentral | None = field(default=None, repr=False)
    piso: float | None = None
    meseta: float | None = None
    altura_media: float | None = None
    nivel_penumbra_alta: float | None = None
    nivel_penumbra_baja: float | None = None
    zona_px: tuple | None = None
    exclusion_px: tuple | None = None
    muestras_meseta: int = 0
    bordes_luz_px: tuple | None = None
    bordes_rad_px: tuple = (None, None)
    fwhm_mm: float | None = None
    centro_rad_px: float | None = None
    penumbras_mm: tuple = (None, None)
    avisos: tuple = ()
    suavizado: np.ndarray | None = field(default=None, repr=False)
    desviacion_meseta: float | None = None          # CD.6: la desviación estándar de las muestras de la meseta (solo en dosis: entra en la U de la dosis de la meseta); no va en `como_dict`

    @property
    def ok(self):
        return self.estado == "ok"

    def como_dict(self):
        def par(p):
            return None if p is None else [None if x is None else float(x) for x in p]

        return {"estado": self.estado, "capa": self.capa, "eje": self.eje, "tam_mm": None if self.tam_mm is None else float(self.tam_mm), "centro_px": None if self.centro_px is None else float(self.centro_px),
                "banda_px": None if self.perfil is None else [float(self.perfil.filas_px[0]), float(self.perfil.filas_px[1])],
                "piso": self.piso, "meseta": self.meseta, "altura_media": self.altura_media, "nivel_penumbra_alta": self.nivel_penumbra_alta, "nivel_penumbra_baja": self.nivel_penumbra_baja,
                "zona_px": par(self.zona_px), "exclusion_px": par(self.exclusion_px), "muestras_meseta": int(self.muestras_meseta), "bordes_luz_px": par(self.bordes_luz_px),
                "bordes_rad_px": par(self.bordes_rad_px), "fwhm_mm": self.fwhm_mm, "centro_rad_px": self.centro_rad_px, "penumbras_mm": par(self.penumbras_mm), "avisos": list(self.avisos)}


@dataclass(frozen=True, eq=False)
class MedidaDeCapa:
    """Todo lo que se midió en UNA capa (R, G, B o gris), sin compararla con ninguna otra. `estado`: «ok» o el motivo (el del piso de esa capa o el del primer perfil que no se pudo medir). `piso`: su nivel
    de piso. `crossplane` e `inplane`: sus dos `MedidaDePerfil`. `coincidencia_mm`: {izquierdo, derecho, superior, inferior} = borde de radiación - borde luminoso, positivo hacia afuera (None si no se midió
    ese borde). `centro_radiacion_px`: (x, y) en el marco girado. `radiacion_menos_luz_mm` y `radiacion_menos_reticulo_mm`: (x, y), contra el MISMO cruce de diagonales y el retículo girado."""
    capa: str
    estado: str
    piso: float | None
    crossplane: MedidaDePerfil
    inplane: MedidaDePerfil
    coincidencia_mm: dict
    centro_radiacion_px: tuple
    radiacion_menos_luz_mm: tuple
    radiacion_menos_reticulo_mm: tuple
    base: str | None = None                 # CD.6: solo en un análisis en dosis: `BASE_DOSIS` si la capa se midió en dosis o `BASE_DENSIDAD_OPTICA` si no (con su motivo); None en las bases de siempre
    motivo_de_la_base: str | None = None    # CD.6: por qué esa capa no se mide en dosis (la primera condición de DC8 que falla), o None
    dosis_meseta_cgy: float | None = None   # CD.6 (DC10): la dosis de la meseta (la media de las de sus dos perfiles, cGy contados desde el cero de la curva), o None
    u_dosis_meseta_cgy: float | None = None  # CD.6 (DC10): su U (k = 2, cGy), o None

    @property
    def ok(self):
        return self.estado == "ok"

    def como_dict(self):
        def par(p):
            return [None if x is None else float(x) for x in p]

        d = {"capa": self.capa, "estado": self.estado, "piso": self.piso, "crossplane": self.crossplane.como_dict(), "inplane": self.inplane.como_dict(),
             "coincidencia_mm": dict(self.coincidencia_mm), "centro_radiacion_px": par(self.centro_radiacion_px), "radiacion_menos_luz_mm": par(self.radiacion_menos_luz_mm),
             "radiacion_menos_reticulo_mm": par(self.radiacion_menos_reticulo_mm)}
        if self.base is not None:          # CD.6: solo un análisis en dosis lleva estas claves; en las bases de siempre el diccionario es el de OD.1
            d.update(base=self.base, motivo_de_la_base=self.motivo_de_la_base, dosis_meseta_cgy=self.dosis_meseta_cgy, u_dosis_meseta_cgy=self.u_dosis_meseta_cgy)
        return d


@dataclass(frozen=True, eq=False)
class ResultadoPlacaMensual:
    """El resultado de `analizar`: lo que C.3 (el barrido), D.1 (lo que se guarda), E.1 (la ventana) y F.1 (el PDF) necesitan, sin la página.

    `version`: `VERSION_ALGORITMO`. `estado`: «ok» si al menos una capa se midió por completo (sus dos perfiles) o el motivo por el que no se pudo medir ninguna (los puntos no forman el campo, no hay escala, el piso no es medible, o
    `MOTIVO_NINGUNA_CAPA`: el piso y la geometría son buenos pero ninguna capa quedó medida por completo); cada capa dice el suyo. `parametros`: copia de los `P` con que se
    midió (se guarda con el análisis: al reabrir se recalcula con ESTOS, no con los de hoy; incluye `base_de_la_medida`). `base`: una de `BASES`, la base con que se midió (OD.1). `tam_mm`: milímetros por píxel (None sin escala). `marcas`: los cinco puntos tal como
    llegaron, en el orden en que llegaron, como datos (un par [x, y] o el diccionario de `MarcaRefinada.como_dict()`). `puntos`: su clasificación (`PuntosClasificados`). `geometria`: la de C.1 (`GeometriaLuz`).
    `piso`: el `Piso` de la UNICA llamada a `piso_de_pelicula` (todas las capas y el barrido de C.3 usan ese). `girada`: la película recortada y girada (None si no se midió). `capas`: {R, G, B, gris} ->
    `MedidaDeCapa`. `bordes_luz_px`: {crossplane, inplane} -> (menor, mayor) los bordes luminosos de las líneas centrales, en el marco girado (None si la línea no cruza el campo).
    `luz_menos_reticulo_mm`: (x, y) del centro luminoso menos el retículo en el marco girado (el de C.1). Estos dos salen de la geometría y no de la película (R9): con el piso «no medible» siguen ahí; solo
    faltan (None) cuando la geometría misma no se pudo calcular (los puntos no forman el campo o no hay escala)."""
    version: str
    estado: str
    parametros: dict
    base: str
    tam_mm: float | None
    marcas: tuple
    puntos: PuntosClasificados | None
    geometria: GeometriaLuz | None
    piso: object
    girada: PeliculaGirada | None = field(repr=False)
    capas: dict
    bordes_luz_px: dict
    luz_menos_reticulo_mm: tuple | None
    curva: CurvaDeDosis | None = field(default=None, repr=False)      # CD.6: la curva con que se midió en dosis (None en las bases de siempre)
    cadena: dict | None = None                                        # CD.6: la cadena de captura de la película con que se juzgó la condición 3 de DC8 (None en las bases de siempre)
    avisos_de_la_dosis: tuple = ()                                    # CD.6: la película virgen del análisis contra el cero de la curva (`diferencia_virgen_maxima_pct`); no bloquean

    @property
    def ok(self):
        return self.estado == "ok"

    def memoria_bytes(self):
        """Lo que el resultado retiene en arreglos: la película girada y los perfiles medidos (la página no)."""
        total = 0 if self.girada is None else self.girada.memoria_bytes()
        for medida in self.capas.values():
            for m in (medida.crossplane, medida.inplane):
                if m.perfil is not None:
                    total += m.perfil.valores.nbytes
                if m.suavizado is not None:
                    total += m.suavizado.nbytes
        return int(total)

    def como_dict(self):
        """Solo números y textos (JSON): sin la película girada ni los perfiles."""
        def par(p):
            return None if p is None else [None if x is None else float(x) for x in p]

        d = {"version": self.version, "estado": self.estado, "parametros": copy.deepcopy(self.parametros), "base": self.base, "tam_mm": self.tam_mm, "marcas": copy.deepcopy(list(self.marcas)),
             "puntos": None if self.puntos is None else self.puntos.como_dict(), "geometria": None if self.geometria is None else self.geometria.como_dict(),
             "piso": None if self.piso is None else self.piso.como_dict(), "capas": {nombre: medida.como_dict() for nombre, medida in self.capas.items()},
             "bordes_luz_px": {eje: par(b) for eje, b in self.bordes_luz_px.items()}, "luz_menos_reticulo_mm": par(self.luz_menos_reticulo_mm)}
        if self.base == BASE_DOSIS:          # CD.6: solo un análisis en dosis lleva la curva, la cadena y los avisos; en las bases de siempre el diccionario es el de OD.1
            d.update(curva=None if self.curva is None else self.curva.como_dict(), cadena=copy.deepcopy(self.cadena), avisos_de_la_dosis=list(self.avisos_de_la_dosis))
        return d


# ----------------------------------------------------------------------------- la base y las claves

def _pedir(P, claves, para):
    faltan = [k for k in claves if k not in P]
    if faltan:
        raise ValueError(f"A `P` le faltan los parámetros {faltan} que pide {para}.")


def _exigir_la_base(base):
    if base not in BASES:
        raise ValueError(f"La base de la medida es «{BASE_DENSIDAD_OPTICA}», «{BASE_VALOR_DE_PIXEL}» o «{BASE_DOSIS}»; «{base}» no está implementada.")


def _exigir_la_curva(base, curva):
    """CD.6: la base dosis pide la curva de la capa (`curva_de_la_capa`) y las otras dos no la admiten (una curva que nadie usa sería un argumento ignorado)."""
    if base == BASE_DOSIS and not isinstance(curva, CurvaDeLaCapa):
        raise ValueError(f"La base «{BASE_DOSIS}» necesita la curva de dosis de la capa (`curva_de_la_capa(curva, capa)`), no {type(curva).__name__}.")
    if base != BASE_DOSIS and curva is not None:
        raise ValueError(f"La curva de dosis solo se usa con la base «{BASE_DOSIS}», no con «{base}».")


def normalizar(base, valores, piso, meseta, curva=None):
    """Los niveles de 8 bits `valores` normalizados entre el piso (0) y la meseta (1) en la base pedida, la ÚNICA definición de la base del análisis (OD.1): en `BASE_VALOR_DE_PIXEL`,
    (piso - v) / (piso - meseta) (0.5 en la media aritmética); en `BASE_DENSIDAD_OPTICA`, log10(piso / max(v, VP_MINIMO)) / log10(piso / max(meseta, VP_MINIMO)) (0.5 en la media geométrica;
    monótona: a menor valor de píxel, mayor netOD); en `BASE_DOSIS` (CD.6), D(netOD(v)) / D(netOD(meseta)) con la curva de la capa `curva` (0.5 donde la dosis vale la mitad de la de la meseta; monótona
    porque la curva lo es). Un NaN sigue siendo NaN. Cualquier otra base es `ValueError`, y también la dosis sin curva o una curva con otra base."""
    _exigir_la_base(base)
    _exigir_la_curva(base, curva)
    v = np.asarray(valores, dtype=np.float64)
    if base == BASE_VALOR_DE_PIXEL:
        return (piso - v) / (piso - meseta)
    if base == BASE_DOSIS:
        return valores_en_la_base(base, v, piso, curva) / float(valores_en_la_base(base, meseta, piso, curva))
    return np.log10(piso / np.maximum(v, VP_MINIMO)) / np.log10(piso / max(float(meseta), VP_MINIMO))


def nivel_de_la_base(base, fraccion, piso, meseta, curva=None):
    """El nivel de 8 bits donde la señal normalizada vale `fraccion` (0 en el piso, 1 en la meseta): la altura media y los niveles de la penumbra, para dibujarlos y decirlos en niveles. En valor de pixel,
    piso - fraccion · (piso - meseta); en netOD, piso · (meseta / piso)^fraccion (la media geométrica para 0.5); en dosis (CD.6), piso · 10^(−x) con x la netOD de la dosis fraccion · D(netOD(meseta))
    (la inversa de la curva, `CurvaDeDosis.netod`). Es la inversa de `normalizar` en esa base."""
    _exigir_la_base(base)
    _exigir_la_curva(base, curva)
    if base == BASE_VALOR_DE_PIXEL:
        return piso - fraccion * (piso - meseta)
    if base == BASE_DOSIS:
        return float(piso) * 10.0 ** (-curva.netod(fraccion * float(valores_en_la_base(base, meseta, piso, curva))))
    return piso * (max(float(meseta), VP_MINIMO) / piso) ** fraccion


def valores_en_la_base(base, valores, piso, curva=None):
    """Los niveles de 8 bits `valores` en la unidad de la base, para DIBUJAR un perfil con la base con que se midió: en valor de píxel los mismos niveles; en netOD la densidad óptica neta absoluta
    log10(piso / max(v, VP_MINIMO)) (0 en el piso; sin normalizar a la meseta); en dosis (CD.6) la dosis de esa netOD con la curva de la capa, en cGy contados desde el cero de la curva (0 en el piso).
    Acepta un arreglo o un escalar."""
    _exigir_la_base(base)
    _exigir_la_curva(base, curva)
    v = np.asarray(valores, dtype=np.float64)
    if base == BASE_VALOR_DE_PIXEL:
        return v
    if base == BASE_DOSIS:
        return curva.dosis(np.log10(float(piso) / np.maximum(v, VP_MINIMO)))
    return np.log10(float(piso) / np.maximum(v, VP_MINIMO))


# ----------------------------------------------------------------------------- girar

def _caja_de_la_pelicula(pelicula, P, tam_mm):
    """(x0, y0, x1, y1) en píxeles de la imagen original, x1 e y1 exclusivos: la caja de la componente conexa más grande de lo que es película (tiene dato y su capa más oscura baja de `umbral_fondo`, la
    definición de A.2) más `margen_recorte_mm` por cada lado y el paso de la búsqueda, dentro de la imagen. Se busca en una versión con 1 píxel de cada `PASO_DE_LA_CAJA` (no se copia la página). None si
    no hay película."""
    paso = PASO_DE_LA_CAJA
    mas_oscura = np.minimum(np.minimum(pelicula.R[::paso, ::paso], pelicula.G[::paso, ::paso]), pelicula.B[::paso, ::paso])
    es_pelicula = (mas_oscura < P["umbral_fondo"]) & np.asarray(pelicula.validos[::paso, ::paso], dtype=bool)
    cuantas, _, estadisticas, _ = cv2.connectedComponentsWithStats(es_pelicula.view(np.uint8), connectivity=8)
    if cuantas < 2:
        return None
    k = 1 + int(np.argmax(estadisticas[1:, cv2.CC_STAT_AREA]))
    x, y, ancho, alto = (int(v) for v in estadisticas[k, :4])
    margen = int(math.ceil(P["margen_recorte_mm"] / tam_mm)) + 2 * paso
    alto_imagen, ancho_imagen = pelicula.validos.shape
    return (max(0, x * paso - margen), max(0, y * paso - margen), min(ancho_imagen, (x + ancho) * paso + margen), min(alto_imagen, (y + alto) * paso + margen))


def girar(pelicula, M, P, cruce):
    """Recorta la película y la gira con la matriz `M` (2 x 3, imagen -> marco girado: la de `GeometriaLuz.matriz_de_giro`) -> `PeliculaGirada`.

    Gira SOLO la película: recorta antes a su caja (más `margen_recorte_mm`) y gira ese recorte; las cuatro capas y la máscara de píxeles con dato salen de `cv2.warpAffine` en flotante (interpolación
    bilineal; lo que entra por el borde es «sin dato»). El arreglo de salida cubre el recorte girado completo. La matriz es UNA para la imagen (aquí) y para los puntos (`transformar_puntos`). `cruce`: el
    cruce de diagonales en la imagen original; la salida lo trae llevado al marco girado. `ValueError` si la película no tiene escala (el archivo declara otra resolución que la del procedimiento), no hay
    película en la imagen o `M` no es de 2 x 3."""
    _pedir(P, ("umbral_fondo", "margen_recorte_mm") + CLAVES_DE_LA_ESCALA, "`girar`")
    tam_mm = escala_mm(getattr(pelicula, "dpi", None), P)
    if tam_mm is None:
        raise ValueError(MOTIVO_SIN_ESCALA)
    m = np.asarray(M, dtype=np.float64)
    if m.shape != (2, 3):
        raise ValueError(f"La matriz de giro es de 2 x 3, no de forma {m.shape}.")
    cruce = _punto(cruce, "cruce de diagonales")
    caja = _caja_de_la_pelicula(pelicula, P, tam_mm)
    if caja is None:
        raise ValueError("No hay película en la imagen: todo es fondo del escáner o no tiene dato.")
    x0, y0, x1, y1 = caja
    esquinas = transformar_puntos(m, [(x0, y0), (x1 - 1, y0), (x1 - 1, y1 - 1), (x0, y1 - 1)])
    ox = int(math.floor(min(e[0] for e in esquinas))) - 1
    oy = int(math.floor(min(e[1] for e in esquinas))) - 1
    ancho = int(math.ceil(max(e[0] for e in esquinas))) - ox + 2
    alto = int(math.ceil(max(e[1] for e in esquinas))) - oy + 2
    lineal, traslado = m[:, :2], m[:, 2]
    del_recorte = np.hstack([lineal, (lineal @ np.array([x0, y0], dtype=np.float64) + traslado - np.array([ox, oy], dtype=np.float64))[:, None]])     # del índice del recorte al índice de la salida
    capas = {}
    for nombre in CAPAS_DEL_PISO:
        fuente = np.ascontiguousarray(getattr(pelicula, nombre)[y0:y1, x0:x1], dtype=np.float32)
        capas[nombre] = cv2.warpAffine(fuente, del_recorte, (ancho, alto), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        capas[nombre].setflags(write=False)
        del fuente
    con_dato = cv2.warpAffine(np.ascontiguousarray(pelicula.validos[y0:y1, x0:x1], dtype=np.float32), del_recorte, (ancho, alto), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    validos = con_dato > UMBRAL_DE_VALIDEZ
    del con_dato
    es_pelicula = validos & (np.minimum(np.minimum(capas["R"], capas["G"]), capas["B"]) < P["umbral_fondo"])
    validos.setflags(write=False)
    es_pelicula.setflags(write=False)
    return PeliculaGirada(capas=capas, validos=validos, pelicula=es_pelicula, origen=(ox, oy), matriz=tuple(tuple(float(v) for v in fila) for fila in m), caja=caja,
                          cruce=transformar_puntos(m, [cruce])[0], tam_mm=tam_mm)


# ----------------------------------------------------------------------------- el perfil

def perfil_central(capa, eje, P, banda=0, base=BASE_VALOR_DE_PIXEL, curva=None, piso=None):
    """El perfil de `capa` (una `CapaGirada`) por el cruce de diagonales -> `PerfilCentral`: la fila (crossplane) o la columna (inplane) que pasa por él en el marco girado, PROMEDIADA en una banda de
    `banda_perfil_mm` de ancho. La banda `banda` es la de las filas (columnas) cuyo centro cae en [cruce + (banda - 1/2) mm, cruce + (banda + 1/2) mm): las vecinas no se solapan ni dejan huecos y la 0
    es el perfil central. El crossplane recorre x y promedia filas, el inplane recorre y y promedia columnas, nunca cruzados. Un punto del perfil solo vale si TODAS las filas de la banda tienen ahí película
    con dato y no está a menos de `margen_borde_mm` de lo que no lo es (el fleco del corte); el borde del arreglo cuenta como borde. `ValueError` si el eje no existe, la base no es una de `BASES` o la
    banda queda vacía o fuera del arreglo.

    CÓMO SE PROMEDIA LA BANDA SEGÚN LA BASE (OD.1, decisión OD1-REV-D1, opción B de Opus, vetable por el físico): `base`, una de `BASES`, dice cómo se promedian las filas para que la banda sea la de la
    imagen que esa base mide. En `BASE_VALOR_DE_PIXEL` (por omisión, la conducta de siempre) es la media ARITMÉTICA de los niveles de 8 bits. En `BASE_DENSIDAD_OPTICA` es la de la imagen CONVERTIDA PÍXEL A
    PÍXEL a densidad óptica: la media de log10(max(v, VP_MINIMO)) de las filas, devuelta a niveles de 8 bits (10 ** esa media: la media GEOMÉTRICA), de modo que log10(piso / valor del perfil) es el promedio de la
    netOD de cada píxel de la banda (lo que `dibujar_perfil` traza) y una mota brillante dentro de la banda no la acorta más de lo que acorta a la imagen convertida (con el logaritmo del promedio LINEAL el azul
    inplane de EPSON007 y de EPSON008.TIF salía casi 3 mm más angosto). El piso de VP_MINIMO se aplica POR PÍXEL, antes del logaritmo (un píxel en 0 no da infinito). La máscara de píxeles con película y dato, el
    margen del borde y las filas de la banda son los mismos en las dos bases.

    EN DOSIS (CD.6): `curva` (la de ESTA capa, `curva_de_la_capa`) y `piso` (el nivel de piso de la capa) son obligatorios. La banda es la de la imagen CONVERTIDA PÍXEL A PÍXEL a dosis: la media de
    D(log10(piso / max(v, VP_MINIMO))) de sus filas, devuelta a niveles de 8 bits con la inversa de la curva (piso · 10^(−x), x = `CurvaDeDosis.netod` de esa media), de modo que la dosis del valor del perfil es
    el promedio de la dosis de cada píxel de la banda, como OD1-REV-D1 en netOD. Con una curva lineal (D = k·x) es EXACTAMENTE la banda de netOD."""
    if eje not in EJES:
        raise ValueError(f"El eje es uno de {EJES}, no {eje!r}.")
    _exigir_la_base(base)
    _pedir(P, ("banda_perfil_mm", "margen_borde_mm"), "`perfil_central`")
    _exigir_la_curva(base, curva)
    if base == BASE_DOSIS and (piso is None or not np.isfinite(piso) or not piso > 0):
        raise ValueError(f"La banda en dosis necesita el nivel de piso de la capa (positivo), no {piso!r}.")
    ancho_px = P["banda_perfil_mm"] / capa.tam_mm
    if eje == "crossplane":
        centro_perpendicular, origen_perpendicular, origen_del_eje = capa.cruce[1], capa.origen[1], capa.origen[0]
        datos, validos, pelicula = capa.datos, capa.validos, capa.pelicula
    else:
        centro_perpendicular, origen_perpendicular, origen_del_eje = capa.cruce[0], capa.origen[0], capa.origen[1]
        datos, validos, pelicula = capa.datos.T, capa.validos.T, capa.pelicula.T
    primera = int(math.ceil(centro_perpendicular + banda * ancho_px - ancho_px / 2))
    fin = int(math.ceil(centro_perpendicular + banda * ancho_px + ancho_px / 2))
    a, b = primera - origen_perpendicular, fin - origen_perpendicular
    if fin <= primera:
        raise ValueError(f"La banda de {P['banda_perfil_mm']:g} mm no contiene el centro de ninguna fila con esta escala.")
    if a < 0 or b > datos.shape[0]:
        raise ValueError(f"La banda {banda} del perfil {eje} (de {primera} a {fin}) queda fuera de la película girada.")
    if base == BASE_DENSIDAD_OPTICA:
        valores = 10.0 ** np.log10(np.maximum(datos[a:b], VP_MINIMO), dtype=np.float64).mean(axis=0)
    elif base == BASE_DOSIS:
        netod = math.log10(float(piso)) - np.log10(np.maximum(datos[a:b], VP_MINIMO), dtype=np.float64)          # en float64 desde el logaritmo (el cociente en float32 perdería 1e-7)
        dosis = np.asarray(curva.dosis(netod), dtype=np.float64).mean(axis=0)
        valores = float(piso) * 10.0 ** (-np.asarray(curva.netod(dosis), dtype=np.float64))
    else:
        valores = datos[a:b].mean(axis=0, dtype=np.float64)
    bueno = pelicula[a:b].all(axis=0) & validos[a:b].all(axis=0)
    radio = int(math.ceil(P["margen_borde_mm"] / capa.tam_mm))
    bueno = ndi.binary_erosion(bueno, structure=np.ones(2 * radio + 1, dtype=bool), border_value=0)
    valores[~bueno] = np.nan
    return PerfilCentral(capa=capa.nombre, eje=eje, banda=int(banda), valores=valores, desde_px=int(origen_del_eje), filas_px=(primera, fin), n_filas=fin - primera, tam_mm=float(capa.tam_mm))


# ----------------------------------------------------------------------------- los bordes luminosos y la coincidencia

def _cruce_de_diagonales(ul, ur, dr, dl):
    """El cruce de las diagonales UL-DR y UR-DL (la misma fórmula de `geometria_luz`, para esquinas ya giradas)."""
    d = (ul[0] - dr[0]) * (ur[1] - dl[1]) - (ul[1] - dr[1]) * (ur[0] - dl[0])
    a, b = ul[0] * dr[1] - ul[1] * dr[0], ur[0] * dl[1] - ur[1] * dl[0]
    return ((a * (ur[0] - dl[0]) - (ul[0] - dr[0]) * b) / d, (a * (ur[1] - dl[1]) - (ul[1] - dr[1]) * b) / d)


def _en_el_lado(a, b, eje_fijo, valor):
    """La coordenada del lado a-b donde la otra coordenada vale `valor`: eje_fijo 1 da x en la fila y = valor, eje_fijo 0 da y en la columna x = valor. None si el lado no cruza esa línea."""
    d = b[eje_fijo] - a[eje_fijo]
    if d == 0 or not min(a[eje_fijo], b[eje_fijo]) <= valor <= max(a[eje_fijo], b[eje_fijo]):
        return None
    return a[1 - eje_fijo] + (valor - a[eje_fijo]) * (b[1 - eje_fijo] - a[1 - eje_fijo]) / d


def bordes_luz(eje, esquinas_giradas, linea_px=None):
    """Los dos bordes luminosos de la línea de un perfil: la intersección ANALÍTICA de esa línea con los lados del cuadrilátero luminoso, (menor, mayor) en píxeles del marco girado (no rasterizados: son
    fraccionarios). `esquinas_giradas`: UL, UR, DR, DL ya en el marco girado. crossplane: la fila y = `linea_px` con los lados izquierdo (UL-DL) y derecho (UR-DR), da x; inplane: la columna x =
    `linea_px` con los lados superior (UL-UR) e inferior (DL-DR), da y. `linea_px` por omisión es la que pasa por el cruce de diagonales. None si la línea no cruza alguno de los dos lados."""
    if eje not in EJES:
        raise ValueError(f"El eje es uno de {EJES}, no {eje!r}.")
    esquinas = [_punto(p, "esquina") for p in esquinas_giradas]
    if len(esquinas) != 4:
        raise ValueError(f"Las esquinas del campo luminoso son cuatro, no {len(esquinas)}.")
    ul, ur, dr, dl = esquinas
    cruce = _cruce_de_diagonales(ul, ur, dr, dl)
    if eje == "crossplane":
        linea = cruce[1] if linea_px is None else float(linea_px)
        menor, mayor = _en_el_lado(ul, dl, 1, linea), _en_el_lado(ur, dr, 1, linea)
    else:
        linea = cruce[0] if linea_px is None else float(linea_px)
        menor, mayor = _en_el_lado(ul, ur, 0, linea), _en_el_lado(dl, dr, 0, linea)
    if menor is None or mayor is None:
        return None
    return (float(menor), float(mayor))


def coincidencia(bordes_rad, bordes_luz, tam_mm):
    """La coincidencia por lado: borde de radiación - borde luminoso, POSITIVO HACIA AFUERA en los cuatro lados (R9, paso 9). Con x a la derecha e y hacia abajo: izquierdo x_luz - x_rad, derecho x_rad -
    x_luz, superior y_luz - y_rad, inferior y_rad - y_luz. `bordes_rad` y `bordes_luz`: {izquierdo, derecho, superior, inferior} -> posición en píxeles del marco girado (None o ausente si no se midió).
    Devuelve {lado: milímetros o None} con los cuatro lados."""
    salida = {}
    for lado in LADOS_DE_LA_COINCIDENCIA:
        rad, luz = bordes_rad.get(lado), bordes_luz.get(lado)
        salida[lado] = None if rad is None or luz is None else float(SIGNO_DEL_LADO[lado] * (rad - luz) * tam_mm)
    return salida


# ----------------------------------------------------------------------------- medir un perfil

def _suavizar(valores, muestras):
    """El promedio móvil centrado de `muestras` (impar) muestras; NaN donde la ventana no está completa o toca un NaN. Con 1 muestra no cambia nada."""
    if muestras <= 1:
        return valores
    finito = np.isfinite(valores)
    ventana = np.ones(muestras)
    suma = np.convolve(np.where(finito, valores, 0.0), ventana, mode="same")
    cuenta = np.convolve(finito.astype(np.float64), ventana, mode="same")
    salida = np.full(valores.shape, np.nan)
    completo = cuenta > muestras - 1
    salida[completo] = suma[completo] / muestras
    return salida


def _primer_cruce(normalizado, inicio, paso, nivel):
    """El índice (fraccionario, por interpolación lineal) del PRIMER cruce de `nivel` yendo desde `inicio` en la dirección `paso` (+1 o -1) sobre el perfil normalizado, que baja de 1 en la meseta a 0 en el
    piso. None si el tramo no empieza por encima del nivel, o si llega a un NaN o al final del arreglo antes de cruzarlo."""
    tramo = normalizado[inicio:] if paso > 0 else normalizado[inicio::-1]
    if not len(tramo) or not tramo[0] > nivel:
        return None
    debajo = ~(tramo > nivel)
    if not debajo.any():
        return None
    k = int(np.argmax(debajo))
    if k == 0 or not np.isfinite(tramo[k]):
        return None
    return inicio + paso * (k - 1 + (tramo[k - 1] - nivel) / (tramo[k - 1] - tramo[k]))


def _no_medible(perfil, centro, motivo, **extra):
    return MedidaDePerfil(estado=f"no medible: perfil {perfil.eje}: {motivo}", capa=perfil.capa, eje=perfil.eje, tam_mm=perfil.tam_mm, centro_px=float(centro), perfil=perfil, **extra)


def medir_perfil(perfil, centro_px, piso, base, P, bordes_luz, reticulo_px=None, curva=None):
    """Mide un perfil -> `MedidaDePerfil`: meseta, altura media, bordes de radiación, FWHM, centro de radiación y penumbras.

    ZONA CENTRAL: [centro - e, centro + e] con e = `fraccion_meseta` / 2 x la distancia entre los dos bordes luminosos de esa línea (`bordes_luz`, el resultado de la función del mismo nombre), alrededor del cruce de
    diagonales `centro_px`; sin los `excepcion_centro_mm` alrededor del RETÍCULO REFINADO `reticulo_px` (que no es dosis). MESETA: el nivel medio de esa zona, con la tinta rechazada como en A.2 (lo que baja
    de la mediana más de `delta_tinta`). Con una meseta que no es plana (la cúpula de las películas reales, de -2 a -5.7 % a 40 mm del centro) el 50 % de ESTA meseta no es el 50 % de la dosis
    del centro del campo: en el azul, la única capa lineal en la dosis, el FWHM sale más ancho unos 0.0225 mm por cada 1 % de cúpula, 0.13 mm con -5.7 % (C2-D15, medido contra el generador de PF.0). Es la
    definición del plan y no un defecto de la medida; los 0.15 mm del protocolo contra la dosis valen con la meseta plana (en netOD la meseta sigue siendo el nivel medio de la zona, no la media de las densidades). BASE
    (OD.1): `base`, una de `BASES`, normaliza el perfil entre el piso (0) y la meseta (1) con `normalizar` (netOD: n = log10(piso / v) / log10(piso / meseta); valor de píxel: (piso - v) / (piso - meseta)); el `perfil` ya viene promediado en esa base (`perfil_central(base=)`: en netOD, la media de log10 por píxel de la banda); la altura media es
    n = `altura_media` y los niveles de la altura media y de la penumbra, en niveles de 8 bits, salen de `nivel_de_la_base`. SOLO EN netOD, si la MEDIANA de la zona central vale `NIVEL_DE_RECORTE` más `MARGEN_DEL_RECORTE` niveles o menos (una meseta cerca del negro del escáner, el único lugar donde el escáner la
    puede recortar) y más de `FRACCION_DE_RECORTE_MAXIMA` de las muestras de la zona central valen `NIVEL_DE_RECORTE` niveles o menos, la meseta está recortada por el escáner (`MOTIVO_MESETA_RECORTADA`) y el perfil
    es «no medible». Una muestra de ese nivel dentro de una meseta más clara es tinta, polvo o un rayón y la regla no la mira: la tinta se trata como en valor de píxel (la aparta de la meseta lo que baja de la
    mediana más de `delta_tinta`). BORDES: se buscan DESDE LA MESETA HACIA
    AFUERA, el primer cruce al salir de la zona central (nunca el punto más cercano a la altura media de todo el perfil), con interpolación lineal subpíxel, sobre el perfil suavizado
    `suavizado_perfil_mm`. La penumbra de cada lado va del `penumbra_alta` al `penumbra_baja` de la señal; si el perfil llega al borde de la película antes de cruzar el segundo queda «incompleta» (None y el aviso),
    nunca un número inventado. Lo que no se puede medir NO lanza: la medida dice «no medible» con su motivo y trae lo que sí se midió (por ejemplo un solo borde). `ValueError` solo si la base no existe o a
    `P` le falta un parámetro.

    EN DOSIS (CD.6, `curva` = la de esta capa): la zona, la tinta (apartada en niveles), el contraste y la regla del recorte son los de netOD (la dosis sale de la netOD: una meseta recortada sigue «no
    medible»); la meseta es la DOSIS MEDIA de esas muestras (P4 de la curva: el 50 % de la media de la meseta; decisión CD6-D3), devuelta a su nivel; si su netOD pasa la netOD más alta del rango útil
    de la curva, el perfil es «no medible en dosis» (DC8, condición 4: no se extrapola, `motivo_del_rango`); y la altura media y la penumbra son el 50 % y el 80 y 20 % de la DOSIS de la meseta
    (`normalizar` y `nivel_de_la_base` con la curva)."""
    _exigir_la_base(base)
    _pedir(P, CLAVES_QUE_PIDE_LA_MEDIDA, "`medir_perfil`")
    _exigir_la_curva(base, curva)
    tam = perfil.tam_mm
    centro = float(centro_px)
    if piso is None or not np.isfinite(piso):
        return _no_medible(perfil, centro, "no hay piso de esta capa")
    piso = float(piso)
    if bordes_luz is None:
        return _no_medible(perfil, centro, "la línea del perfil no cruza el campo luminoso", piso=piso)
    luz_menor, luz_mayor = (float(b) for b in bordes_luz)
    if not luz_mayor > luz_menor:
        return _no_medible(perfil, centro, "los bordes luminosos de la línea no tienen ancho", piso=piso)
    extremo = P["fraccion_meseta"] / 2 * (luz_mayor - luz_menor)
    zona = (centro - extremo, centro + extremo)
    exclusion = None if reticulo_px is None else (float(reticulo_px) - P["excepcion_centro_mm"] / tam, float(reticulo_px) + P["excepcion_centro_mm"] / tam)
    v = perfil.valores
    x = perfil.desde_px + np.arange(len(v), dtype=np.float64)
    datos = dict(piso=piso, zona_px=zona, exclusion_px=exclusion, bordes_luz_px=(luz_menor, luz_mayor))
    en_zona = (x >= zona[0]) & (x <= zona[1])
    excluida = np.zeros(len(v), dtype=bool) if exclusion is None else (x >= exclusion[0]) & (x <= exclusion[1])
    usables = en_zona & ~excluida
    if not len(v) or x[0] > zona[0] or x[-1] < zona[1] or not np.isfinite(v[usables]).all():
        return _no_medible(perfil, centro, "la zona central de la meseta no está sobre la película", **datos)
    if int(usables.sum()) < P["muestras_minimas_de_la_meseta"]:
        return _no_medible(perfil, centro, f"la zona central de la meseta tiene menos de {P['muestras_minimas_de_la_meseta']} muestras", **datos)
    mediana = float(np.median(v[usables]))
    sin_tinta = usables & (v >= mediana - P["delta_tinta"])
    meseta = float(v[sin_tinta].mean())
    contraste = piso - meseta
    datos.update(meseta=meseta, muestras_meseta=int(sin_tinta.sum()))
    if not contraste >= P["contraste_minimo"]:
        return _no_medible(perfil, centro, f"el piso no es más claro que la meseta en al menos {P['contraste_minimo']:g} niveles (piso {piso:.1f}, meseta {meseta:.1f})", **datos)
    if base in (BASE_DENSIDAD_OPTICA, BASE_DOSIS):
        recortada = meseta_recortada(v[usables])          # CD.2: la regla del recorte es UNA (`pelicula.meseta_recortada`): la mediana de la zona central cerca del negro del escáner y más de FRACCION_DE_RECORTE_MAXIMA de sus muestras en él
        if recortada is not None:          # el escáner recortó la meseta (el rojo a 800 UM): el logaritmo de un valor recortado no es la densidad óptica y ninguna capa «con netOD» se inventa
            return _no_medible(perfil, centro, f"{MOTIVO_MESETA_RECORTADA}: el {100 * recortada:.0f} % de la zona central de la meseta vale {NIVEL_DE_RECORTE:g} niveles o menos y la densidad óptica no existe", **datos)
    if base == BASE_DOSIS:
        # CD.6 (CD6-D3): en dosis la meseta es la DOSIS MEDIA de las mismas muestras (las de la zona central sin la tinta, apartada en niveles como siempre), devuelta a su nivel con la inversa de la
        # curva: el 50 % es el de la dosis de la meseta, como en la imagen convertida a dosis. En netOD la meseta sigue siendo el nivel medio (OD.1); con la meseta plana y sin ruido son el mismo nivel.
        meseta = float(piso * 10.0 ** (-curva.netod(float(np.mean(valores_en_la_base(base, v[sin_tinta], piso, curva))))))
        datos["meseta"] = meseta
        fuera = motivo_del_rango(curva, math.log10(piso / max(meseta, VP_MINIMO)))          # DC8, condición 4: la netOD de la meseta no pasa el rango útil de la curva; no se extrapola
        if fuera is not None:
            return MedidaDePerfil(estado=f"{PREFIJO_NO_MEDIBLE_EN_DOSIS}perfil {perfil.eje}: {fuera}", capa=perfil.capa, eje=perfil.eje, tam_mm=perfil.tam_mm, centro_px=centro, perfil=perfil, **datos)
        datos["desviacion_meseta"] = float(np.std(v[sin_tinta]))
    datos.update(altura_media=nivel_de_la_base(base, P["altura_media"], piso, meseta, curva), nivel_penumbra_alta=nivel_de_la_base(base, P["penumbra_alta"], piso, meseta, curva),
                 nivel_penumbra_baja=nivel_de_la_base(base, P["penumbra_baja"], piso, meseta, curva))
    muestras = 2 * int(round((P["suavizado_perfil_mm"] / tam - 1) / 2)) + 1
    if base == BASE_DOSIS:          # CD.6 (CD6-D3): en dosis se suaviza la DOSIS (la imagen convertida), y el perfil suavizado vuelve a niveles con la inversa de la curva
        suave = float(piso) * 10.0 ** (-np.asarray(curva.netod(_suavizar(valores_en_la_base(base, v, piso, curva), max(muestras, 1))), dtype=np.float64))
    else:
        suave = _suavizar(v, max(muestras, 1))
    datos["suavizado"] = suave
    n = normalizar(base, suave, piso, meseta, curva)
    if np.any(n[usables] <= P["altura_media"]):
        return _no_medible(perfil, centro, "la zona central de la meseta no está toda dentro del campo de radiación (hay muestras bajo la altura media)", **datos)
    indices = np.flatnonzero(en_zona)
    inicios = {-1: int(indices[0]), 1: int(indices[-1])}
    bordes, penumbras, avisos, faltan = [], [], [], []
    for paso, lado in zip((-1, 1), LADOS_DEL_EJE[perfil.eje]):
        inicio = inicios[paso]
        medio = _primer_cruce(n, inicio, paso, P["altura_media"])
        if medio is None:
            bordes.append(None)
            penumbras.append(None)
            faltan.append(lado)
            continue
        bordes.append(float(perfil.desde_px + medio))
        alto = _primer_cruce(n, inicio, paso, P["penumbra_alta"])
        bajo = _primer_cruce(n, inicio, paso, P["penumbra_baja"])
        if bajo is None:
            penumbras.append(None)
            avisos.append(AVISO_PENUMBRA_INCOMPLETA.format(porcentaje=P["penumbra_baja"] * 100))
        elif alto is None or not (alto - inicio) * paso <= (medio - inicio) * paso <= (bajo - inicio) * paso:
            penumbras.append(None)
            avisos.append(AVISO_PENUMBRA_NO_MONOTONA.format(alto=P["penumbra_alta"] * 100, medio=P["altura_media"] * 100, bajo=P["penumbra_baja"] * 100))
        else:
            penumbras.append(float(abs(bajo - alto) * tam))
    datos.update(bordes_rad_px=tuple(bordes), penumbras_mm=tuple(penumbras), avisos=tuple(avisos))
    if faltan:
        return _no_medible(perfil, centro, f"no se encuentra el borde {' ni el borde '.join(faltan)} al {P['altura_media'] * 100:g} %: el perfil llega al borde de la película o a una zona sin dato antes de cruzar la altura media", **datos)
    return MedidaDePerfil(estado="ok", capa=perfil.capa, eje=perfil.eje, tam_mm=tam, centro_px=centro, perfil=perfil, fwhm_mm=float((bordes[1] - bordes[0]) * tam),
                          centro_rad_px=float((bordes[0] + bordes[1]) / 2), **datos)


# ----------------------------------------------------------------------------- analizar

def _sin_medir_la_capa(nombre, estado, tam_mm):
    """Una `MedidaDeCapa` que no se midió, con el motivo."""
    vacias = {eje: MedidaDePerfil(estado=estado, capa=nombre, eje=eje, tam_mm=tam_mm, centro_px=None) for eje in EJES}
    return MedidaDeCapa(capa=nombre, estado=estado, piso=None, crossplane=vacias["crossplane"], inplane=vacias["inplane"], coincidencia_mm={lado: None for lado in LADOS_DE_LA_COINCIDENCIA},
                        centro_radiacion_px=(None, None), radiacion_menos_luz_mm=(None, None), radiacion_menos_reticulo_mm=(None, None))


def _medir_la_capa(girada, nombre, piso, geometria, luz, P, base=BASE_VALOR_DE_PIXEL, curva=None):
    """Las dos medidas de perfil de una capa, la coincidencia por lado y los tres centros, en la base `base`. El nivel de piso es el de ESE `Piso`; si esa capa no tiene piso no se mide y se dice por qué.
    En dosis (CD.6) `curva` es la de ESTA capa y la medida trae además la base, la dosis de la meseta y su U (`_dosis_de_la_meseta`)."""
    del_piso = piso.capas[nombre]
    if del_piso.estado != "ok" or del_piso.mediana is None:
        return _sin_medir_la_capa(nombre, del_piso.estado, girada.tam_mm)
    capa = girada.capa(nombre)
    cruce = girada.cruce
    reticulo = geometria.reticulo_girado
    medidas = {}
    for i, eje in enumerate(EJES):
        try:
            perfil = perfil_central(capa, eje, P, base=base, curva=curva, piso=del_piso.mediana)
        except ValueError as motivo:
            medidas[eje] = MedidaDePerfil(estado=f"no medible: perfil {eje}: {motivo}", capa=nombre, eje=eje, tam_mm=girada.tam_mm, centro_px=float(cruce[i]), piso=float(del_piso.mediana))
            continue
        medidas[eje] = medir_perfil(perfil, cruce[i], del_piso.mediana, base, P, luz[eje], reticulo[i], curva=curva)
    rad, luminoso = {}, {}
    for eje in EJES:
        for j, lado in enumerate(LADOS_DEL_EJE[eje]):
            rad[lado] = medidas[eje].bordes_rad_px[j]
            luminoso[lado] = None if luz[eje] is None else luz[eje][j]
    centro = (medidas["crossplane"].centro_rad_px, medidas["inplane"].centro_rad_px)
    tam = girada.tam_mm
    menos_luz = tuple(None if c is None else float((c - cruce[i]) * tam) for i, c in enumerate(centro))
    menos_reticulo = tuple(None if c is None else float((c - reticulo[i]) * tam) for i, c in enumerate(centro))
    fallas = [m.estado for m in medidas.values() if not m.ok]
    en_dosis = {} if base != BASE_DOSIS else dict(zip(("base", "dosis_meseta_cgy", "u_dosis_meseta_cgy"), (BASE_DOSIS,) + _dosis_de_la_meseta(curva, del_piso.mediana, medidas)))
    return MedidaDeCapa(capa=nombre, estado="ok" if not fallas else fallas[0], piso=float(del_piso.mediana), crossplane=medidas["crossplane"], inplane=medidas["inplane"],
                        coincidencia_mm=coincidencia(rad, luminoso, tam), centro_radiacion_px=centro, radiacion_menos_luz_mm=menos_luz, radiacion_menos_reticulo_mm=menos_reticulo, **en_dosis)


def _del_campo_luminoso(geometria):
    """Lo que el resultado dice del campo luminoso y NO depende de la película (R9): los bordes luminosos de las líneas centrales en el marco girado ({eje: (menor, mayor), o None si la línea no cruza el
    campo}) y luz - retículo en ese marco. Salen de la geometría de C.1: un piso o una capa que no se pueden medir no los quitan. UNA definición para el resultado completo y para el que no se midió."""
    luz = {eje: bordes_luz(eje, geometria.esquinas_giradas) for eje in EJES}
    return luz, tuple(geometria.luz_menos_reticulo_girado_mm)


def _marca_como_dato(marca):
    """Un punto tal como llegó, como dato guardable: el diccionario de una marca refinada o [x, y]."""
    if isinstance(marca, MarcaRefinada):
        return marca.como_dict()
    if isinstance(marca, dict):
        return copy.deepcopy(marca)
    x, y = _punto(marca)
    return [x, y]


def analizar(pelicula, puntos, parametros, modo_piso=None, punto_manual=None, referencia_virgen=None, curva=None, cadena=None):
    """El análisis mensual de una película -> `ResultadoPlacaMensual`: los cinco puntos, la geometría del campo luminoso (C.1), UNA llamada a `piso_de_pelicula` (todas las capas usan ese `Piso`), la película
    recortada y girada y, para R, G, B y el gris por separado, los perfiles centrales, el FWHM, los bordes, la coincidencia por lado y los tres centros.

    `pelicula`: la `Pelicula` de `leer_pelicula` (no se modifica y el resultado no la retiene). `puntos`: los cinco puntos en cualquier orden; cada uno un par (x, y), una `MarcaRefinada` o el diccionario de su
    `como_dict()` (`punto_de_medida`): reabrir un análisis guardado pasa los guardados, no se vuelve a refinar nada. `parametros`: los `P` con que se mide, que viajan con el resultado (al reabrir se recalcula con los
    guardados, no con los de hoy); la BASE sale de `P["base_de_la_medida"]` (OD.1) y, si el registro no la trae (uno guardado antes de OD.1), es el valor de píxel: se mide como se midió.
    `modo_piso`, `punto_manual` y `referencia_virgen` pasan tal cual a `piso_de_pelicula` (A.3): sin `modo_piso`, la regla de `modo_efectivo` decide (la película virgen si hay referencia y las esquinas si no). Lo que no se puede medir NO lanza: el resultado y cada capa dicen «no medible»
    con su motivo; los bordes luminosos y luz - retículo, que no dependen de la película, se entregan siempre que la geometría sea buena. La raíz es «ok» si al menos una capa se midió
    por completo (`MOTIVO_NINGUNA_CAPA` si ninguna). `ValueError` solo si los argumentos tienen una forma equivocada (no son cinco puntos, a `P` le falta un parámetro, el modo no existe).

    EN DOSIS (CD.6): `P["base_de_la_medida"] = BASE_DOSIS`, `curva` (la `CurvaDeDosis` de `curva_efectiva` o la copia guardada de un registro; None dice «no hay curva de dosis» en cada capa) y `cadena`
    (la de `cadena_de_la_pelicula`, para la condición 3). Cada capa pasa por `base_de_la_capa`: si cumple las condiciones 1, 2, 3 y 5 de DC8 se mide en dosis con la curva de ESA capa (la 4, el rango, la
    juzga `medir_perfil` en cada perfil) y si no queda «no medible en dosis: <motivo>», sin números (sus números en netOD son los del análisis en netOD: una vista nunca mezcla bases). El resultado trae la
    curva, la cadena y los avisos de la película virgen (`diferencia_virgen_maxima_pct`, que no bloquean). Una curva o una cadena con otra base es `ValueError` (no se ignora un argumento)."""
    P = parametros
    _pedir(P, CLAVES_QUE_PIDE_ANALIZAR, "`analizar`")
    base = P.get("base_de_la_medida", BASE_VALOR_DE_PIXEL)
    _exigir_la_base(base)
    try:
        lista = list(puntos)
    except TypeError:
        raise ValueError("Los puntos son una lista de cinco pares (x, y).") from None
    clasificados = clasificar_puntos(lista)
    tam_mm = escala_mm(getattr(pelicula, "dpi", None), P)
    marcas = tuple(_marca_como_dato(m) for m in lista)
    usados = copy.deepcopy(dict(P))
    usados.setdefault("base_de_la_medida", base)              # los parámetros que viajan dicen la base con que SE MIDIÓ (un registro de antes de OD.1 no la traía)
    if base != BASE_DOSIS and (curva is not None or cadena is not None):
        raise ValueError(f"La curva de dosis y la cadena de captura solo se usan con la base «{BASE_DOSIS}», no con «{base}».")
    if curva is not None and not isinstance(curva, CurvaDeDosis):
        raise ValueError(f"La curva de un análisis en dosis es una `CurvaDeDosis` (`curva_desde_dict` de la copia), no {type(curva).__name__}.")
    en_dosis = {}
    if base == BASE_DOSIS:
        usados.setdefault("diferencia_virgen_maxima_pct", PARAMETROS_DE_LA_DOSIS["diferencia_virgen_maxima_pct"]["valor"])      # CD.6: el de fábrica si el registro no lo trae
        en_dosis = dict(curva=curva, cadena=None if cadena is None else copy.deepcopy(dict(cadena)))

    def sin_medir(estado, **extra):
        return ResultadoPlacaMensual(version=VERSION_ALGORITMO, estado=estado, parametros=usados, base=base, tam_mm=tam_mm, marcas=marcas, puntos=extra.get("puntos"),
                                     geometria=extra.get("geometria"), piso=extra.get("piso"), girada=None, capas={n: _sin_medir_la_capa(n, estado, tam_mm) for n in CAPAS_DEL_PISO},
                                     bordes_luz_px=extra.get("bordes_luz_px") or {eje: None for eje in EJES}, luz_menos_reticulo_mm=extra.get("luz_menos_reticulo_mm"), **en_dosis)

    if not clasificados.ok:
        return sin_medir(clasificados.estado, puntos=clasificados)
    geometria = geometria_luz(clasificados.esquinas, clasificados.reticulo, tam_mm)
    if not geometria.ok:
        return sin_medir(geometria.estado, puntos=clasificados, geometria=geometria)
    luz, luz_menos_reticulo = _del_campo_luminoso(geometria)
    piso = piso_de_pelicula(pelicula, geometria.esquinas, P, punto_manual=punto_manual, modo=modo_piso, referencia_virgen=referencia_virgen)
    if piso.estado != "ok":
        return sin_medir(piso.estado, puntos=clasificados, geometria=geometria, piso=piso, bordes_luz_px=luz, luz_menos_reticulo_mm=luz_menos_reticulo)
    girada = girar(pelicula, geometria.matriz_de_giro, P, geometria.cruce)
    if base == BASE_DOSIS:
        capas = {nombre: _medir_la_capa_en_dosis(girada, nombre, piso, geometria, luz, P, curva, cadena) for nombre in CAPAS_DEL_PISO}
        en_dosis["avisos_de_la_dosis"] = avisos_de_la_virgen(curva, piso, usados["diferencia_virgen_maxima_pct"])
    else:
        capas = {nombre: _medir_la_capa(girada, nombre, piso, geometria, luz, P, base) for nombre in CAPAS_DEL_PISO}
    estado = "ok" if any(medida.ok for medida in capas.values()) else MOTIVO_NINGUNA_CAPA
    return ResultadoPlacaMensual(version=VERSION_ALGORITMO, estado=estado, parametros=usados, base=base, tam_mm=tam_mm, marcas=marcas, puntos=clasificados, geometria=geometria,
                                 piso=piso, girada=girada, capas=capas, bordes_luz_px=luz, luz_menos_reticulo_mm=luz_menos_reticulo, **en_dosis)


def valores_medidos(resultado, capa):
    """La ÚNICA definición de lo que se guarda de un análisis (D.1): de la capa que se le pasa (R, G, B o gris), su `estado` («ok» o el motivo por el que no se midió: sin él un vacío se confundiría con un
    cero), el FWHM crossplane e inplane y el desfase de cada lado (radiación - luz, positivo hacia afuera), en `CLAVES_DE_VALORES_MEDIDOS` y en milímetros (None lo que no se midió). Las demás capas, el piso, la
    meseta, las penumbras, los centros, el campo luminoso y el barrido se miden y se muestran, no se guardan. `ValueError` si la capa no existe."""
    if capa not in CAPAS_DEL_PISO:
        raise ValueError(f"La capa es una de {CAPAS_DEL_PISO}, no {capa!r}.")
    m = resultado.capas[capa]
    valores = (m.estado, m.crossplane.fwhm_mm, m.inplane.fwhm_mm) + tuple(m.coincidencia_mm[lado] for lado in LADOS_DE_LA_COINCIDENCIA)
    return {clave: (v if clave == CLAVES_DE_VALORES_MEDIDOS[0] or v is None else float(v)) for clave, v in zip(CLAVES_DE_VALORES_MEDIDOS, valores)}


# ============================================================================= C.3: el barrido, sin parámetro, en la misma zona central, con sus medidas estadísticas (R9, paso 11)

EJE_PERPENDICULAR = {"crossplane": "inplane", "inplane": "crossplane"}     # la línea central de donde sale la zona del barrido de un eje es la del OTRO eje
MOTIVO_BARRIDO_SIN_LINEA = "no medible: la línea central perpendicular no cruza el campo luminoso, así que el barrido no tiene zona"
MOTIVO_BARRIDO_SIN_BANDA = "no medible: la zona central del barrido es más angosta que una banda"
MOTIVO_BARRIDO_SIN_PELICULA = "no medible: el resultado no trae la película girada que barrer"
MOTIVO_NINGUNA_BANDA = "no medible: ninguna banda del barrido se pudo medir; cada capa y cada eje dice su motivo"      # el estado de la raíz cuando ninguna capa de ningún eje tuvo una sola banda medible


def _par_como_lista(p):
    """Un par (o None) como lista de floats para JSON; None donde falte un valor."""
    return None if p is None else [None if x is None else float(x) for x in p]


@dataclass(frozen=True, eq=False)
class BandaDelBarrido:
    """Una banda del barrido. `k`: su número (0 es el perfil central; positivo hacia abajo en el crossplane y hacia la derecha en el inplane, en el marco girado). `posicion_mm`: k x `banda_perfil_mm`, su distancia
    nominal al cruce de diagonales. `linea_px`: su línea central en el marco girado (cruce + k bandas), la que cruza los lados del campo luminoso para dar SUS bordes luminosos. `medida`: la `MedidaDePerfil` de
    `medir_perfil` (con sus bordes, su centro y su estado; las filas que usó están en `medida.perfil.filas_px`, o `perfil` es None si la banda quedó fuera de la película girada)."""
    k: int
    posicion_mm: float
    linea_px: float
    medida: MedidaDePerfil

    @property
    def ok(self):
        return self.medida.ok

    @property
    def fwhm_mm(self):
        return self.medida.fwhm_mm

    def como_dict(self):
        m = self.medida
        return {"k": int(self.k), "posicion_mm": float(self.posicion_mm), "linea_px": float(self.linea_px), "estado": m.estado, "fwhm_mm": m.fwhm_mm, "centro_rad_px": m.centro_rad_px,
                "bordes_rad_px": _par_como_lista(m.bordes_rad_px), "bordes_luz_px": _par_como_lista(m.bordes_luz_px),
                "banda_px": None if m.perfil is None else _par_como_lista(m.perfil.filas_px)}


@dataclass(frozen=True)
class EstadisticaDelBarrido:
    """El FWHM de las bandas MEDIBLES de una capa y un eje, sin descartar ninguna: `n_bandas` (las del barrido, medibles o no), `n_medibles`, la media, la mediana y la desviación estándar (de la población, como
    `np.std`) en milímetros; None si no hay ninguna medible."""
    n_bandas: int
    n_medibles: int
    media_mm: float | None
    mediana_mm: float | None
    desviacion_mm: float | None

    def como_dict(self):
        return {"n_bandas": int(self.n_bandas), "n_medibles": int(self.n_medibles), "media_mm": self.media_mm, "mediana_mm": self.mediana_mm, "desviacion_mm": self.desviacion_mm}


@dataclass(frozen=True, eq=False)
class BarridoDeCapa:
    """El barrido de UNA capa en UN eje. `estado`: «ok» si al menos una banda se pudo medir, o el motivo (el del piso de esa capa, o que ninguna de sus bandas se midió). `bandas`: TODAS, de -K a +K, en orden
    (vacía si la capa no se barrió). `estadistica`: la de sus bandas medibles."""
    capa: str
    eje: str
    estado: str
    bandas: tuple
    estadistica: EstadisticaDelBarrido

    @property
    def ok(self):
        return self.estado == "ok"

    @property
    def central(self):
        """La banda 0, que es el perfil central de `analizar` (None si la capa no se barrió)."""
        return next((b for b in self.bandas if b.k == 0), None)

    def como_dict(self):
        return {"estado": self.estado, "estadistica": self.estadistica.como_dict(), "bandas": [b.como_dict() for b in self.bandas]}


@dataclass(frozen=True, eq=False)
class BarridoDeEje:
    """El barrido de un eje: la REGIÓN (la misma para las cuatro capas, sale de los bordes luminosos y de ningún perfil medido) y el de cada capa. `perpendicular`: el eje de la línea central de donde sale la zona.
    `longitud_perpendicular_mm`: la distancia entre sus dos bordes luminosos. `k_maximo`: K, la mayor banda cuyo borde de afuera cabe en la zona (floor(fraccion_meseta / 2 x L / banda - 1/2)). `zona_px` y
    `zona_mm`: los límites de la zona, en el marco girado y en milímetros desde el cruce (la zona central de la meseta del perfil perpendicular). `banda_mm`: el ancho de cada banda. Si no hay región
    (la línea no cruza el campo, la zona no alcanza para una banda o no hay película girada) todo eso es None, `estado` dice por qué y las capas no tienen bandas."""
    eje: str
    estado: str
    perpendicular: str
    longitud_perpendicular_mm: float | None
    k_maximo: int | None
    zona_px: tuple | None
    zona_mm: tuple | None
    banda_mm: float
    capas: dict

    @property
    def ok(self):
        return self.estado == "ok"

    @property
    def ks(self):
        """Los números de banda del barrido, de -K a +K (vacío si no hay región)."""
        return () if self.k_maximo is None else tuple(range(-self.k_maximo, self.k_maximo + 1))

    def como_dict(self):
        return {"estado": self.estado, "perpendicular": self.perpendicular, "longitud_perpendicular_mm": self.longitud_perpendicular_mm, "k_maximo": self.k_maximo,
                "zona_px": _par_como_lista(self.zona_px), "zona_mm": _par_como_lista(self.zona_mm), "banda_mm": self.banda_mm, "capas": {nombre: c.como_dict() for nombre, c in self.capas.items()}}


@dataclass(frozen=True, eq=False)
class BarridoPlacaMensual:
    """El resultado de `barrido`: `version`, `estado` («ok» si alguna banda de alguna capa se pudo medir; si no, el motivo), `tam_mm` y `ejes` ({crossplane, inplane} -> `BarridoDeEje`, cada uno con sus cuatro
    capas). No retiene la película girada ni el resultado que barrió; sí los perfiles de sus bandas (`memoria_bytes`)."""
    version: str
    estado: str
    tam_mm: float | None
    ejes: dict

    @property
    def ok(self):
        return self.estado == "ok"

    def memoria_bytes(self):
        """Lo que el barrido retiene en arreglos: el perfil y el perfil suavizado de cada banda (la película girada no). Un arreglo que aparece dos veces se cuenta UNA: con `suavizado_perfil_mm` en 0 no se
        suaviza y el perfil suavizado ES el perfil."""
        arreglos = {}
        for e in self.ejes.values():
            for c in e.capas.values():
                for b in c.bandas:
                    for a in (None if b.medida.perfil is None else b.medida.perfil.valores, b.medida.suavizado):
                        if a is not None:
                            arreglos[id(a)] = a.nbytes
        return int(sum(arreglos.values()))

    def como_dict(self):
        """Solo números y textos (JSON): sin los arreglos de los perfiles."""
        return {"version": self.version, "estado": self.estado, "tam_mm": self.tam_mm, "ejes": {eje: e.como_dict() for eje, e in self.ejes.items()}}


def _estadistica(fwhm, n_bandas):
    """La media, la mediana y la desviación estándar (de la población, la `np.std` del resto de la aplicación) de los FWHM de las bandas medibles `fwhm`, y cuántas son; ninguna se descarta. Con ninguna, None."""
    if not len(fwhm):
        return EstadisticaDelBarrido(n_bandas=int(n_bandas), n_medibles=0, media_mm=None, mediana_mm=None, desviacion_mm=None)
    v = np.asarray(fwhm, dtype=np.float64)
    return EstadisticaDelBarrido(n_bandas=int(n_bandas), n_medibles=int(v.size), media_mm=float(np.mean(v)), mediana_mm=float(np.median(v)), desviacion_mm=float(np.std(v)))


def _barrido_de_capa_sin_barrer(nombre, eje, motivo):
    """Una capa que no se barrió: el motivo, ninguna banda y la estadística vacía."""
    return BarridoDeCapa(capa=nombre, eje=eje, estado=motivo, bandas=(), estadistica=_estadistica([], 0))


def _barrido_de_eje_sin_zona(eje, motivo, P):
    """Un eje sin región que barrer: el motivo en el eje y en cada una de sus cuatro capas."""
    return BarridoDeEje(eje=eje, estado=motivo, perpendicular=EJE_PERPENDICULAR[eje], longitud_perpendicular_mm=None, k_maximo=None, zona_px=None, zona_mm=None, banda_mm=P["banda_perfil_mm"],
                        capas={nombre: _barrido_de_capa_sin_barrer(nombre, eje, motivo) for nombre in CAPAS_DEL_PISO})


def _barrido_sin_medir(resultado, motivo):
    """El barrido de un resultado que no trae la película girada: nada que barrer, y el motivo en todas partes."""
    return BarridoPlacaMensual(version=VERSION_ALGORITMO, estado=motivo, tam_mm=resultado.tam_mm,
                               ejes={eje: _barrido_de_eje_sin_zona(eje, motivo, resultado.parametros) for eje in EJES})


def _banda_del_barrido(resultado, capa, eje, i, k, cruce_luz, mediana):
    """La banda `k` de `capa` en `eje` (i: 0 si recorre la x, 1 si recorre la y): el perfil de `perfil_central(banda=k)` medido con `medir_perfil`, el piso de esa capa, el cruce a lo largo del eje, los bordes
    luminosos de SU línea (cruce de diagonales + k bandas, perpendicular al eje: las esquinas pueden quedar inclinadas) y el retículo girado. Una banda fuera de la película girada no se tira: queda «no medible»."""
    P = resultado.parametros
    girada = resultado.girada
    linea = cruce_luz[1 - i] + k * (P["banda_perfil_mm"] / girada.tam_mm)
    curva = None if resultado.base != BASE_DOSIS else curva_de_la_capa(resultado.curva, capa.nombre)          # CD.6: en dosis, la curva de ESTA capa
    try:
        perfil = perfil_central(capa, eje, P, banda=k, base=resultado.base, curva=curva, piso=mediana)
    except ValueError as motivo:
        medida = MedidaDePerfil(estado=f"no medible: perfil {eje}: {motivo}", capa=capa.nombre, eje=eje, tam_mm=girada.tam_mm, centro_px=float(girada.cruce[i]), piso=float(mediana))
    else:
        medida = medir_perfil(perfil, girada.cruce[i], mediana, resultado.base, P, bordes_luz(eje, resultado.geometria.esquinas_giradas, linea_px=linea), resultado.geometria.reticulo_girado[i], curva=curva)
    return BandaDelBarrido(k=k, posicion_mm=float(k * P["banda_perfil_mm"]), linea_px=float(linea), medida=medida)


def _motivo_del_barrido_sin_piso(del_piso):
    """Por qué no se barre una capa: el motivo de su piso (o, si el piso dice «ok» pero no trae nivel, que no lo tiene)."""
    return del_piso.estado if del_piso.estado != "ok" else "no medible: la capa no tiene nivel de piso"


def _barrer_la_capa(resultado, nombre, eje, i, ks, cruce_luz):
    """Las bandas `ks` de una capa en un eje y su estadística. Una capa sin piso medido no se barre (su motivo es el de su piso); si ninguna banda se midió lo dice con el motivo de la central."""
    del_piso = resultado.piso.capas[nombre]
    if del_piso.estado != "ok" or del_piso.mediana is None:
        return _barrido_de_capa_sin_barrer(nombre, eje, _motivo_del_barrido_sin_piso(del_piso))
    if resultado.base == BASE_DOSIS and resultado.capas[nombre].base != BASE_DOSIS:          # CD.6: una capa que no se mide en dosis tampoco se barre en dosis (su motivo es el de la capa)
        return _barrido_de_capa_sin_barrer(nombre, eje, resultado.capas[nombre].estado)
    capa = resultado.girada.capa(nombre)
    bandas = tuple(_banda_del_barrido(resultado, capa, eje, i, k, cruce_luz, del_piso.mediana) for k in ks)
    estadistica = _estadistica([b.fwhm_mm for b in bandas if b.ok], len(bandas))
    if estadistica.n_medibles:
        return BarridoDeCapa(capa=nombre, eje=eje, estado="ok", bandas=bandas, estadistica=estadistica)
    central = next(b for b in bandas if b.k == 0)
    return BarridoDeCapa(capa=nombre, eje=eje, estado=f"no medible: ninguna de las {len(bandas)} bandas del barrido se pudo medir (la central: {central.medida.estado})", bandas=bandas, estadistica=estadistica)


def _barrer_el_eje(resultado, eje, i, cruce_luz):
    """El barrido de un eje: la región (±`fraccion_meseta` / 2 de la distancia entre los bordes luminosos de la línea central PERPENDICULAR, alrededor del cruce: la misma zona central de la meseta del perfil
    perpendicular, para las cuatro capas) y las bandas de cada capa. Sin línea perpendicular, o con una zona más angosta que una banda, el eje queda «no medible» y no se inventa ninguna región."""
    P = resultado.parametros
    luz = resultado.bordes_luz_px[EJE_PERPENDICULAR[eje]]
    if luz is None:
        return _barrido_de_eje_sin_zona(eje, MOTIVO_BARRIDO_SIN_LINEA, P)
    tam = resultado.girada.tam_mm
    centro = resultado.girada.cruce[1 - i]
    extremo = P["fraccion_meseta"] / 2 * (luz[1] - luz[0])
    k_maximo = math.floor(extremo * tam / P["banda_perfil_mm"] - 1 / 2)
    if k_maximo < 0:
        return _barrido_de_eje_sin_zona(eje, MOTIVO_BARRIDO_SIN_BANDA, P)
    ks = range(-k_maximo, k_maximo + 1)
    return BarridoDeEje(eje=eje, estado="ok", perpendicular=EJE_PERPENDICULAR[eje], longitud_perpendicular_mm=float((luz[1] - luz[0]) * tam), k_maximo=int(k_maximo),
                        zona_px=(centro - extremo, centro + extremo), zona_mm=(-extremo * tam, extremo * tam), banda_mm=P["banda_perfil_mm"],
                        capas={nombre: _barrer_la_capa(resultado, nombre, eje, i, ks, cruce_luz) for nombre in CAPAS_DEL_PISO})


def barrido(resultado):
    """El barrido del análisis mensual (R9, paso 11) -> `BarridoPlacaMensual`: por eje y por capa, las bandas de `banda_perfil_mm` ancladas en el cruce de diagonales sobre la zona central de la meseta del eje
    perpendicular (±`fraccion_meseta` / 2 de la distancia entre los bordes luminosos de su línea central, alrededor del cruce; la misma para las cuatro capas y para el eje), cada una medida con la MISMA
    `medir_perfil` que el corte central, y de las medibles la media, la mediana, la desviación estándar y cuántas son. La banda 0 es EXACTAMENTE el perfil central de `analizar`.

    UN solo argumento, el resultado de `analizar`, y ningún parámetro nuevo: usa `resultado.parametros` (los mismos del corte central), su película girada (no se vuelve a girar), el `Piso` que trae (no se vuelve a
    calcular: el nivel de cada capa es el de `resultado.piso`) y sus bordes luminosos. No descarta ninguna banda ni juzga ninguna: una banda que no se pudo medir queda en la lista con su motivo. No modifica
    el resultado. Sin película girada (los puntos no forman el campo, no hay escala, el piso no se midió) el barrido es «no medible» con el motivo del resultado; una capa sin piso medido no se barre. Cuando el
    corte central no se midió pero la película sí está, las bandas se prueban igual (la región no depende de ningún perfil medido). `ValueError` si el argumento no es un `ResultadoPlacaMensual` o a sus
    parámetros les falta alguno."""
    if not isinstance(resultado, ResultadoPlacaMensual):
        raise ValueError(f"`barrido` recibe el `ResultadoPlacaMensual` que devuelve `analizar`, no {type(resultado).__name__}.")
    _pedir(resultado.parametros, CLAVES_QUE_PIDE_LA_MEDIDA, "`barrido`")
    if resultado.girada is None or resultado.geometria is None:
        return _barrido_sin_medir(resultado, resultado.estado if not resultado.ok else MOTIVO_BARRIDO_SIN_PELICULA)
    cruce_luz = _cruce_de_diagonales(*resultado.geometria.esquinas_giradas)
    ejes = {eje: _barrer_el_eje(resultado, eje, i, cruce_luz) for i, eje in enumerate(EJES)}
    ok = any(c.ok for e in ejes.values() for c in e.capas.values())
    return BarridoPlacaMensual(version=VERSION_ALGORITMO, estado="ok" if ok else MOTIVO_NINGUNA_BANDA, tam_mm=resultado.girada.tam_mm, ejes=ejes)


# ============================================================================= CD.6: la base «dosis», la regla por capa, la regla del botón y la curva efectiva (DC7, DC8, DC10; DA-92)

PREFIJO_NO_MEDIBLE_EN_DOSIS = "no medible en dosis: "        # el estado de una capa (o de un perfil) que no se mide en dosis: «no medible», como manda DA-88, y en qué base
MOTIVO_SIN_CURVA = "no hay curva de dosis"
FUENTES_DEL_CERO_QUE_PASAN_A_DOSIS = ("piezas_de_0_cgy", "pelicula_virgen")      # DC8, condición 5 (DA-90): el cero de la pieza de menor dosis es una guía y nunca pasa a dosis
TEXTO_DEL_ORIGEN_DEL_PISO = {"automatico": "el de las esquinas de la película", "manual": "el del punto marcado"}
CONDICIONES_PARA_PASAR_A_DOSIS = ("Una capa se mide en dosis solo si la curva de esa capa es «válida», su cero es una pieza de 0 cGy o la película virgen montada (no la pieza de menor dosis), el piso "
                                  "del análisis es el de la película virgen, la película se escaneó con la misma cadena de captura que la calibración (escáner, bits, resolución y formato) y la netOD de "
                                  "la meseta no pasa el rango útil de la curva (no se extrapola).")          # DC8 entera, para la ayuda del botón (CD.7): los motivos dicen la primera que falla
REGLA_DE_LA_CURVA = "la curva de un análisis es la de la calibración vigente más reciente con al menos una capa «válida» escaneada con la misma cadena de captura que la película"


@dataclass(frozen=True, eq=False)
class CurvaDeLaCapa:
    """La curva de dosis de UNA capa: lo que `normalizar`, `nivel_de_la_base`, `valores_en_la_base`, `perfil_central` y `medir_perfil` reciben en dosis. Es una vista de la `CurvaDeDosis` de CD.3: la
    dosis y su inversa son SUS `dosis(capa, x)` y `netod(capa, d)` (las únicas definiciones), con la capa fija para que ninguna llamada pueda pedir la de otra."""
    curva: CurvaDeDosis
    capa: str

    def dosis(self, netod):
        return self.curva.dosis(self.capa, netod)

    def netod(self, dosis):
        return self.curva.netod(self.capa, dosis)

    @property
    def netod_maxima(self):
        return self.curva.capas[self.capa]["netod_maxima"]

    @property
    def rango_cgy(self):
        return self.curva.rango(self.capa)


def _exigir_la_capa(capa):
    if capa in CAPAS_DEL_PISO:
        return
    raise ValueError(f"La capa es una de {CAPAS_DEL_PISO}, no {capa!r}.")


def curva_de_la_capa(curva, capa):
    """La `CurvaDeLaCapa` de `capa` (R, G, B o gris) en la `CurvaDeDosis` `curva`. `ValueError` si no es una curva, la capa no existe o la curva no tiene parámetros en esa capa."""
    if not isinstance(curva, CurvaDeDosis):
        raise ValueError(f"La curva de dosis es una `CurvaDeDosis`, no {type(curva).__name__}.")
    _exigir_la_capa(capa)
    if curva.capas[capa]["parametros"] is None:
        raise ValueError(f"La curva de la capa {ADJETIVO_DE_LA_CAPA[capa]} no tiene parámetros: {curva.estado(capa)}.")
    return CurvaDeLaCapa(curva, capa)


def motivo_del_rango(curva, netod_meseta):
    """DC8, condición 4 (no se extrapola): None si la netOD de la meseta no pasa la netOD más alta del rango útil de la curva de la capa (`CurvaDeLaCapa`), o el motivo con los dos números."""
    maxima = curva.netod_maxima
    if maxima is None:
        return f"la curva de la capa {ADJETIVO_DE_LA_CAPA[curva.capa]} no tiene rango útil"
    if netod_meseta > maxima:
        return (f"la meseta (netOD {netod_meseta:.3f}) pasa el rango útil de la curva de la capa {ADJETIVO_DE_LA_CAPA[curva.capa]} (hasta netOD {maxima:.3f}, {curva.rango_cgy:g} cGy): "
                f"no se extrapola")
    return None


def base_de_la_capa(curva, capa, piso, cadena, netod_meseta=None):
    """LA regla de la base de una capa (DC8, UNA): (`BASE_DOSIS`, None) si la capa se puede medir en dosis, o (`BASE_DENSIDAD_OPTICA`, motivo) con el motivo de la PRIMERA condición que falla, en
    este orden: hay curva; la curva de esa capa es «válida» (una «guía» lo dice así); su cero es una pieza de 0 cGy o la película virgen montada (condición 5); el piso es el de la película virgen
    (condición 2, P8); la cadena de captura de la película (`cadena_de_la_pelicula`) es la de la calibración (condición 3); y, si se da `netod_meseta`, la meseta no pasa el rango útil (condición 4,
    `motivo_del_rango`; sin ella la juzga `medir_perfil` perfil a perfil). `curva`: una `CurvaDeDosis` o None; `piso`: el `Piso` del análisis; `cadena`: un diccionario de `cadena_de_captura` o None."""
    _exigir_la_capa(capa)
    nombre = ADJETIVO_DE_LA_CAPA[capa]
    if curva is None:
        return BASE_DENSIDAD_OPTICA, MOTIVO_SIN_CURVA
    estado = curva.estado(capa)
    if estado.startswith(PREFIJO_GUIA):
        return BASE_DENSIDAD_OPTICA, f"la curva de la capa {nombre} es una guía: {estado[len(PREFIJO_GUIA):]}"
    if estado != ESTADO_VALIDA:
        return BASE_DENSIDAD_OPTICA, f"la curva de la capa {nombre} no es válida: {estado}"
    cero = curva.cero or {}
    if cero.get("fuente") not in FUENTES_DEL_CERO_QUE_PASAN_A_DOSIS:
        return BASE_DENSIDAD_OPTICA, f"la curva de la capa {nombre} es una guía: su cero no es una pieza de 0 cGy ni la película virgen montada ({cero.get('detalle') or 'sin cero'})"
    if piso is None or piso.estado != "ok" or piso.origen != "virgen":
        origen = "no se midió" if piso is None or piso.estado != "ok" else TEXTO_DEL_ORIGEN_DEL_PISO.get(piso.origen, piso.origen)
        return BASE_DENSIDAD_OPTICA, f"el piso no es el de la película virgen ({origen}): la dosis lo exige"
    if cadena is None:
        return BASE_DENSIDAD_OPTICA, "no se conoce la cadena de captura de la película"
    if dict(cadena) != curva.cadena:
        return BASE_DENSIDAD_OPTICA, f"la película se escaneó con otra cadena de captura que la calibración: {_texto_de_la_cadena(cadena)} contra {_texto_de_la_cadena(curva.cadena)}"
    if netod_meseta is not None:
        fuera = motivo_del_rango(CurvaDeLaCapa(curva, capa), netod_meseta)
        if fuera is not None:
            return BASE_DENSIDAD_OPTICA, fuera
    return BASE_DOSIS, None


def _sin_medir_en_dosis(nombre, motivo, tam_mm):
    """La capa de un análisis en dosis que no se mide en dosis: «no medible en dosis: <motivo>», sin números, con su base (netOD) y su motivo."""
    return replace(_sin_medir_la_capa(nombre, PREFIJO_NO_MEDIBLE_EN_DOSIS + motivo, tam_mm), base=BASE_DENSIDAD_OPTICA, motivo_de_la_base=motivo)


def _medir_la_capa_en_dosis(girada, nombre, piso, geometria, luz, P, curva, cadena):
    """Una capa de un análisis en dosis: `base_de_la_capa` decide (condiciones 1, 2, 3 y 5) y, si pasa, se mide con la curva de ESA capa; si un perfil queda fuera del rango útil (condición 4), la capa
    entera es «no medible en dosis» con ese motivo y sin números (nunca un perfil en dosis y el otro sin medir: lo que se guarda en dosis, CD.6b, es de una capa medida por completo)."""
    base, motivo = base_de_la_capa(curva, nombre, piso, cadena)
    if base != BASE_DOSIS:
        return _sin_medir_en_dosis(nombre, motivo, girada.tam_mm)
    medida = _medir_la_capa(girada, nombre, piso, geometria, luz, P, BASE_DOSIS, curva_de_la_capa(curva, nombre))
    for eje in EJES:
        estado = getattr(medida, eje).estado
        if estado.startswith(PREFIJO_NO_MEDIBLE_EN_DOSIS):
            return _sin_medir_en_dosis(nombre, estado[len(PREFIJO_NO_MEDIBLE_EN_DOSIS):].split(": ", 1)[1], girada.tam_mm)
    return medida


def _dosis_de_la_meseta(curva, piso, medidas):
    """DC10: (la dosis de la meseta, su U) de una capa medida en dosis, o (None, None) si alguno de sus dos perfiles no se midió. La dosis es la media de las de las mesetas de sus dos perfiles (cGy
    contados desde el cero de la curva); su U (k = 2) es `CurvaDeDosis.incertidumbre` en la netOD de esa dosis con la u de la película = la dispersión relativa de las muestras de las dos mesetas (la raíz de
    la media de sus cuadrados) / ln 10. Lectura de Opus, vetable (CD6-D7)."""
    perfiles = [medidas[eje] for eje in EJES]
    if not all(m.ok and m.desviacion_meseta is not None for m in perfiles):
        return None, None
    dosis = float(np.mean([curva.dosis(math.log10(piso / max(m.meseta, VP_MINIMO))) for m in perfiles]))
    relativa = math.sqrt(float(np.mean([(m.desviacion_meseta / m.meseta) ** 2 for m in perfiles])))
    return dosis, float(curva.curva.incertidumbre(curva.capa, curva.netod(dosis), relativa / math.log(10.0)))


def avisos_de_la_virgen(curva, piso, maximo_pct):
    """§9 del plan: un aviso por capa en que el piso del análisis (la película virgen montada) y el I0 del cero de la curva difieren más que `maximo_pct` (`diferencia_virgen_maxima_pct`). No bloquea.
    () sin curva, sin cero, sin piso o con un piso que NO es el de una película virgen (las esquinas o el punto marcado: no hay virgen que comparar; la regla de la base ya deja esas capas «no medible en dosis»)."""
    if curva is None or curva.cero is None or piso is None or piso.estado != "ok" or piso.origen != "virgen":
        return ()
    avisos = []
    for c in CAPAS_DEL_PISO:
        i0 = curva.cero["capas"][c]["i0"]
        valor = piso.capas[c].mediana
        if valor is None or not i0:
            continue
        diferencia = 100.0 * (float(valor) - float(i0)) / float(i0)
        if abs(diferencia) > maximo_pct:
            avisos.append(f"La película virgen del análisis difiere {diferencia:+.2f} % del cero de la curva en la capa {ADJETIVO_DE_LA_CAPA[c]} (piso {float(valor):.2f} contra I0 {float(i0):.2f} "
                          f"[nivel]; se avisa a más de {maximo_pct:g} %): la netOD del análisis y la de la curva no salen de la misma película virgen (otro lote u otra sesión de escaneo).")
    return tuple(avisos)


@dataclass(frozen=True, eq=False)
class CurvaEfectiva:
    """La curva que usa un análisis (DC7, `curva_efectiva`): `curva` (la `CurvaDeDosis` de la copia guardada, o None), `id`, `lote` y `fecha_irradiacion` de su calibración (None sin curva) y `motivo`
    (por qué no hay curva, con la regla entera; None si la hay)."""
    curva: CurvaDeDosis | None
    id: int | None = None
    lote: str | None = None
    fecha_irradiacion: str | None = None
    motivo: str | None = None


def curva_efectiva(calibraciones, cadena):
    """LA regla de qué curva usa un análisis (DC7, como `modo_efectivo` del piso): de `calibraciones` (lo que da `services.curva_dosis.vigentes_validas()`: las vigentes con una capa «válida», completas
    y en SU orden, la más reciente primero; el motor no lee la base ni vuelve a ordenar), la PRIMERA cuya copia de la curva (`ajuste`, leída con `curva_desde_dict`) tiene al menos una capa «válida» y la
    misma cadena de captura que la película (`cadena`, de `cadena_de_la_pelicula`). No mira la capa reportada: la curva es una por análisis y la regla del botón juzga la capa. Una copia dañada no se usa
    y el motivo la cuenta. -> `CurvaEfectiva`."""
    if cadena is None:
        return CurvaEfectiva(None, motivo=f"{MOTIVO_SIN_CURVA}: no se conoce la cadena de captura de la película ({REGLA_DE_LA_CURVA})")
    leidas, danadas = [], 0
    for registro in calibraciones:
        try:
            curva = curva_desde_dict(registro["ajuste"])
        except ValueError:
            danadas += 1
            continue
        if any(curva.estado(c) == ESTADO_VALIDA for c in CAPAS_DEL_PISO):
            leidas.append((registro, curva))
    for registro, curva in leidas:
        if curva.cadena == dict(cadena):
            return CurvaEfectiva(curva, registro["id"], registro["lote"], registro["fecha_irradiacion"])
    if leidas:
        registro, curva = leidas[0]
        cuantas = f"{len(leidas)} calibración vigente con una capa válida, de otra cadena" if len(leidas) == 1 else f"{len(leidas)} calibraciones vigentes con una capa válida, todas de otra cadena"
        motivo = (f"{MOTIVO_SIN_CURVA} para la cadena de captura de esta película ({_texto_de_la_cadena(cadena)}): hay {cuantas} (la más reciente, el lote «{registro['lote']}» irradiado el "
                  f"{registro['fecha_irradiacion']}: {_texto_de_la_cadena(curva.cadena)})")
    else:
        motivo = f"{MOTIVO_SIN_CURVA}: no hay ninguna calibración vigente con una capa válida (se hace con «Curva de dosis...»)"
    if danadas:
        motivo += f"; {danadas} con la copia de la curva dañada, que no se puede leer"
    return CurvaEfectiva(None, motivo=f"{motivo} ({REGLA_DE_LA_CURVA})")


def se_puede_pasar_a_dosis(resultado, efectiva, capa, cadena):
    """LA regla del botón «Ver en dosis» (DA-92, DC8 sobre la CAPA REPORTADA): (True, None) si la capa `capa` del análisis en densidad óptica neta `resultado` se puede medir en dosis con la curva de
    `efectiva` (`curva_efectiva`, o la copia guardada de un registro en una `CurvaEfectiva`), o (False, motivo) con el de la primera condición que falla: no hay curva (el motivo entero de `curva_efectiva`),
    las condiciones 1, 5, 2 y 3 de `base_de_la_capa`, la capa no se midió en netOD (sin meseta no hay dosis: la roja recortada) y la 4 con la meseta más oscura de sus dos perfiles. `ValueError` si el
    resultado no es un análisis en netOD, la capa no existe o `efectiva` no es una `CurvaEfectiva`. `CONDICIONES_PARA_PASAR_A_DOSIS` dice la regla entera."""
    if not isinstance(resultado, ResultadoPlacaMensual) or resultado.base != BASE_DENSIDAD_OPTICA:
        raise ValueError(f"La regla del botón se juzga sobre el análisis en «{BASE_DENSIDAD_OPTICA}» (el que la ventana muestra al abrir).")
    _exigir_la_capa(capa)
    if not isinstance(efectiva, CurvaEfectiva):
        raise ValueError(f"La curva del botón es una `CurvaEfectiva` (`curva_efectiva`), no {type(efectiva).__name__}.")
    if efectiva.curva is None:
        return False, efectiva.motivo or MOTIVO_SIN_CURVA
    base, motivo = base_de_la_capa(efectiva.curva, capa, resultado.piso, cadena)
    if base != BASE_DOSIS:
        return False, motivo
    medida = resultado.capas[capa]
    if not medida.ok:
        return False, f"la capa {ADJETIVO_DE_LA_CAPA[capa]} no se midió en densidad óptica neta, así que tampoco en dosis: {medida.estado}"
    netod = max(math.log10(m.piso / max(m.meseta, VP_MINIMO)) for m in (medida.crossplane, medida.inplane))
    base, motivo = base_de_la_capa(efectiva.curva, capa, resultado.piso, cadena, netod_meseta=netod)
    return (True, None) if base == BASE_DOSIS else (False, motivo)


def cadena_de_la_pelicula(datos, pelicula=None):
    """La cadena de captura de una película mensual (DC8, condición 3): el escáner que declara su EXIF, los bits, la resolución declarada y el formato, con la MISMA forma que la de una pieza de
    calibración (`curva_dosis.cadena_de_captura` de la procedencia de CD.2; una prueba fija que coinciden). `datos`: los bytes del escaneo; `pelicula`: su `Pelicula` si ya se leyó (no se vuelve a leer)."""
    datos = bytes(datos)
    pel = leer_pelicula(datos) if pelicula is None else pelicula
    imagen = _abrir_con_pillow(datos)
    return cadena_de_captura({"equipo": None if imagen is None else _equipo_de_la_imagen(imagen), "bits": pel.bits, "dpi_declarado": None if pel.dpi is None else float(pel.dpi),
                              "formato": pel.formato})
