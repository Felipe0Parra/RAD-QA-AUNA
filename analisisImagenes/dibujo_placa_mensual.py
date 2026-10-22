"""E.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-83 a DA-86, PD1): los DIBUJOS y los TEXTOS de la ventana del análisis mensual de aceleradores (`ui/paginasControles/PruebasMensuales/placa_mensual.py`).

Es lo que la ventana compone, separado de ella para probarlo sin Qt (como `analisisImagenes/dibujo_posicion_inicial.py` hace con la posición inicial de braquiterapia): cada función de dibujo recibe un eje
(o una figura) que le da quien llama y dibuja lo que el MOTOR midió (`analisisImagenes/placa_mensual.py`: `ResultadoPlacaMensual` y `BarridoPlacaMensual`); ninguna calcula una longitud, un FWHM, un piso ni
una banda: solo cambia de marco (de la película girada a la imagen) y lo pone en pantalla. Tampoco importa Qt ni `pyplot`; `matplotlib` entra solo dentro de las dos funciones que dibujan el mapa de color `jet`: `colorear`, que lo aplica, y `dibujar_capas`, que le pone su barra de color.

PD1 (nada escondido que cambie el número): cada gráfica dibuja TODO lo que se usó para tomar sus medidas. En la imagen: los cinco clics tal como se marcaron con su punto refinado y su círculo de búsqueda,
el recuadro del campo luminoso con sus diagonales, el cruce y el retículo, las dos bandas de 1 mm de donde salen los perfiles centrales, la zona central de la meseta y del barrido y la región de donde salió el
piso. En cada perfil: el perfil crudo y el suavizado con que se buscaron los cruces, el piso, la media de la meseta, la altura media, los niveles de la penumbra, los límites de la zona central y de la
exclusión del retículo, los bordes de radiación y los bordes luminosos de esa línea, en milímetros desde el cruce de diagonales y con la película completa a los dos lados del campo. `TRAZO_DE_PARAMETRO`
dice dónde se ve cada uno de los 40 parámetros del análisis (un trazo, una etiqueta o una frase del pie) y una prueba lo deriva del código del motor por AST.

Marcos. Los dibujos de la pestaña 1 (la imagen) están en el marco de la IMAGEN, el que el físico ve y en el que marca; los de las pestañas 2 a 5 en el marco GIRADO que usa el motor (la película recortada
y girada hasta que los ejes del campo quedan horizontal y vertical). `a_imagen(matriz, puntos)` es la inversa de la matriz de giro del motor y lleva un trazo del marco girado a la imagen.

Todo está en píxeles del marco que dice cada función, salvo lo que su nombre dice en milímetros. Sin símbolos de correcto o incorrecto (DA-18) y con las unidades entre corchetes. El color de una capa suelto
(un menú, una frase sin «capa») sale de `NOMBRE_DE_CAPA` y, en una frase con «capa», de `ADJETIVO_DE_LA_CAPA` (B.6, R1-PROD-01)."""
import math
import textwrap

import numpy as np

from analisisImagenes import placa_mensual as motor
from analisisImagenes.pelicula import ADJETIVO_DE_LA_CAPA, CAPAS, NOMBRE_DE_CAPA

# ----------------------------------------------------------------------------------------------------- constantes
TINTA = "#0b0b0b"
TINTA_SUAVE = "#898781"
COLOR_REJILLA = "#e1e0d9"
COLOR_CAPA = {"R": "#e34948", "G": "#008300", "B": "#2a78d6", "gris": "#4a4a4a"}
COLOR_CLIC = "#ff8c00"                 # el clic tal como se marcó
COLOR_REFINADO = "#00a6c8"             # el punto con que se mide cuando la marca se refinó
COLOR_RECUADRO = "#d81b8c"             # el recuadro del campo luminoso y sus diagonales
COLOR_CRUCE = "#ffe100"                # el cruce de diagonales (el centro luminoso)
COLOR_BANDA = "#f2c500"                # las dos bandas de 1 mm de los perfiles centrales
COLOR_ZONA = "#2a78d6"                 # la zona central de la meseta y del barrido
COLOR_PISO = "#00b050"                 # de dónde salió el piso
COLOR_LUZ = "#e07b00"                  # los bordes luminosos de la línea de un perfil
COLOR_EXCLUSION = "#7a4cc2"            # la exclusión del retículo
FACTOR_DE_AMPLIACION = 20              # PD1: las desviaciones del recuadro frente al cuadrado perfecto no se ven a escala real (0.4 grados y menos de 1 mm en 100 mm): el dibujo de la cuadratura las
                                       # amplía este factor FIJO y lo rotula («desviaciones × 20»); la tabla da los números sin ampliar
PUNTOS_DEL_CIRCULO = 73
ANCHO_DE_LA_LEYENDA = 34               # caracteres por línea de una etiqueta de la leyenda
_ESQUINA = {"UL": "superior izquierda", "UR": "superior derecha", "DR": "inferior derecha", "DL": "inferior izquierda"}
LADOS_DE_CADA_EJE = {"crossplane": ("izquierdo", "derecho"), "inplane": ("superior", "inferior")}
NOMBRE_DEL_EJE = {"crossplane": "crossplane", "inplane": "inplane"}
SIN_DATO = "sin dato"
NO_MEDIBLE = "no medible"
PREFIJO_DE_LA_REGLA = "No se puede guardar: "
TEXTO_DEL_FACTOR = f"desviaciones × {FACTOR_DE_AMPLIACION}"

# qué trazo o qué rótulo muestra CADA parámetro del análisis (los 40 de `motor.VALORES_DE_LA_GEOMETRIA`). `{clave: (dónde, texto)}`; una prueba deriva por AST qué claves leen el motor y el piso, exige que cada una
# tenga su entrada y comprueba que cada entrada está de verdad en la ventana. Dónde:
#   "marca"      el círculo de búsqueda de cada clic (la etiqueta del trazo empieza por `texto`);
#   "sexto"      el cuadrado del punto marcado sobre película sin irradiar (la etiqueta empieza por `texto`);
#   "banda"      las dos bandas de los perfiles centrales sobre la imagen;
#   "zona"       la zona central de la meseta y del barrido sobre la imagen;
#   "perfil"     un trazo de cada perfil cuya etiqueta empieza por `texto`;
#   "exclusion"  la exclusión del retículo en cada perfil;
#   "pagina"     la etiqueta de la ventana con ese nombre, que DICE el valor con que se midió (la resolución del escaneo);
#   "pie"        una frase del pie de parámetros fijos de la ventana; `texto` es su plantilla y se llena con el valor con que se midió.
TRAZO_DE_PARAMETRO = {
    "radio_marca_mm": ("marca", "círculo de búsqueda"),
    "contraste_minimo_marca": ("pie", "tinta: al menos {:g} niveles más oscura que su entorno"),
    "fraccion_del_contraste_marca": ("pie", "borde de la mancha al {:.0%} de su contraste"),
    "gris_maximo_de_la_tinta": ("pie", "núcleo de la tinta por debajo de {:g} niveles"),
    "borde_blando_marca_mm": ("pie", "borde blando de la marca {:g} mm"),
    "area_minima_marca_mm2": ("pie", "mancha de al menos {:g} mm²"),
    "resolucion_escaneo_dpi": ("pagina", "etiqueta_escaneo"),
    "resoluciones_de_editor_dpi": ("pie", "dpi de editor ({}): se usa la resolución del escaneo"),
    "tolerancia_dpi_relativa": ("pie", "tolerancia del dpi declarado ±{:.0%}"),
    "umbral_fondo": ("pie", "fondo del escáner desde {:g} niveles"),
    "margen_borde_mm": ("pie", "piso a {:g} mm o más de los bordes de la película"),
    "apartar_borde_de_la_imagen": ("pie", "se aparta del piso el borde de la imagen: {}"),
    "margen_campo_mm": ("pie", "piso a más de {:g} mm del campo luminoso"),
    "fraccion_lejana": ("pie", "se toma el {:.0%} más lejano de cada esquina"),
    "delta_tinta": ("pie", "tinta del piso: más de {:g} niveles bajo la mediana"),
    "pixeles_minimos": ("pie", "mínimo {} píxeles de piso"),
    "contraste_minimo": ("pie", "piso al menos {:g} niveles más claro que la meseta"),
    "lado_punto_manual_mm": ("sexto", "cuadrado del punto marcado"),
    "umbral_como_fondo": ("pie", "el piso se toma por fondo del escáner si llega a {:g} niveles"),
    "fraccion_como_fondo": ("pie", "en el {:.0%} o más de sus píxeles"),
    "piso_esperado": ("pie", "rango esperado del piso: {}"),
    "piso_esperado_sin_irradiar": ("pie", "rango esperado del punto marcado: {}"),
    "iqr_maximo": ("pie", "dispersión de una esquina hasta {:g} niveles"),
    "esquinas_minimas": ("pie", "al menos {} esquinas con piso válido"),
    "giro_respaldo_grados": ("pie", "respaldo de una esquina: giro de ±{:g} grados"),
    "s_respaldo": ("pie", "o lateral a {} del semilado"),
    "distancia_respaldo_maxima_mm": ("pie", "ventana de respaldo hasta {:g} mm del campo"),
    "paso_respaldo_mm": ("pie", "paso de {:g} mm de la ventana de respaldo hacia el campo"),
    "tolerancia_virgen_mas_oscura": ("pie", "película virgen: hasta {:g} niveles más oscura que la de fuera del campo"),
    "aviso_azul_virgen": ("pie", "aviso si el azul de la virgen difiere más de {:g} niveles"),
    "aviso_verde_virgen": ("pie", "aviso si el verde de la virgen está más de {:g} niveles más claro"),
    "margen_recorte_mm": ("pie", "se recorta a la película más {:g} mm antes de girar"),
    "banda_perfil_mm": ("banda", "banda del perfil"),
    "fraccion_meseta": ("zona", "zona central de la meseta"),
    "excepcion_centro_mm": ("exclusion", "exclusión del retículo"),
    "muestras_minimas_de_la_meseta": ("pie", "meseta con al menos {} muestras"),
    "altura_media": ("perfil", "altura media"),
    "penumbra_alta": ("perfil", "nivel de penumbra alta"),
    "penumbra_baja": ("perfil", "nivel de penumbra baja"),
    "suavizado_perfil_mm": ("perfil", "perfil suavizado"),
}
LARGO_DEL_PIE = 220                    # caracteres por línea del pie de parámetros fijos


# ----------------------------------------------------------------------------------------------------- textos y números (puros)

def numero(valor, decimales=3, con_signo=False):
    """El número con sus decimales y nunca '-0.000' (lo que redondea a cero no tiene signo); `SIN_DATO` si falta."""
    if valor is None:
        return SIN_DATO
    texto = f"{float(valor):{'+' if con_signo else ''}.{decimales}f}"
    if float(texto) == 0:
        texto = texto.lstrip("+-")
    return texto


def con_punto_final(texto):
    """El texto terminado en un signo final: agrega el punto solo si falta (si ya termina en «.», «?» o «!» lo devuelve tal cual). La UNICA definición de cerrar una frase: junta una frase que viene de otra capa con
    la que sigue («Piso: no medible: <motivo>» y lo que se puede hacer) y cierra un mensaje ajeno (el de un guardado rechazado) sin duplicar el punto que ya trae («...eliminado..»). Un texto vacío, o solo de
    espacios, queda como está."""
    fin = texto.rstrip()
    if not fin or fin.endswith((".", "?", "!")):
        return texto
    return fin + "."


def _par(valor, decimales=3):
    """'(x; y)' de un par de milímetros, o `SIN_DATO` si falta alguno."""
    if valor is None or any(v is None for v in valor):
        return SIN_DATO
    return f"{numero(valor[0], decimales, True)}; {numero(valor[1], decimales, True)}"


def marca_como_dict(marca):
    """Una marca como diccionario con `estado`, `clic`, `punto` y `radio_px`: una `MarcaRefinada`, su `como_dict()` (lo que se guarda) o un par (x, y) (sin refinar, sin círculo de búsqueda)."""
    if isinstance(marca, motor.MarcaRefinada):
        return marca.como_dict()
    if isinstance(marca, dict):
        return marca
    x, y = float(marca[0]), float(marca[1])
    return {"estado": motor.ESTADO_SIN_REFINAR, "clic": [x, y], "punto": [x, y], "radio_px": None, "motivo": None}


def texto_de_las_marcas(marcas, con_milimetros=True):
    """Lo que la ventana dice de las marcas, en pocas líneas: cuántas van, cuáles se refinaron (y entre cuánto se movió el punto del clic) y cuáles quedaron «sin refinar» con su motivo (el clic del físico
    manda). Las refinadas van juntas en una línea; cada una sin refinar, en la suya. `con_milimetros`: False cuando el archivo declara otra resolución y no hay escala en milímetros (`pelicula.escala_mm`
    es None; la línea de la imagen lo dice): lo que se movió el punto es un hecho de la imagen y se dice entonces en píxeles, no en milímetros de una escala que no hay (E1-PROD-02)."""
    if not marcas:
        return ""
    datos = [marca_como_dict(m) for m in marcas]
    refinadas = [(i, m) for i, m in enumerate(datos, 1) if m["estado"] == motor.ESTADO_REFINADA]
    sin_refinar = [(i, m) for i, m in enumerate(datos, 1) if m["estado"] != motor.ESTADO_REFINADA]
    lineas = []
    if refinadas:
        clave, unidad, decimales = ("desplazamiento_mm", "mm", 3) if con_milimetros else ("desplazamiento_px", "px", 2)
        movimientos = [m.get(clave) for _, m in refinadas if m.get(clave) is not None]
        rango = f"; el punto se movió de {numero(min(movimientos), decimales)} a {numero(max(movimientos), decimales)} {unidad} del clic" if movimientos else ""
        cuales = ", ".join(str(i) for i, _ in refinadas)
        lineas.append(f"Marcas {len(datos)} de 5. Refinadas: {cuales}{rango}.")
    else:
        lineas.append(f"Marcas {len(datos)} de 5. Ninguna refinada.")
    for i, m in sin_refinar:
        lineas.append(f"Marca {i}: {m.get('motivo') or 'sin refinar'}")
    return "\n".join(lineas)


def nombre_de_la_capa(capa):
    """«Capa roja», «Capa verde», «Capa azul» y «Gris»: el gris no es una capa de color (el menú «Capa reportada» no lo ofrece)."""
    return "Gris" if capa == "gris" else f"Capa {ADJETIVO_DE_LA_CAPA[capa]}"


def titulo_del_perfil(medida, capa, reportada=False):
    """El título de la gráfica de un perfil, definido en UN solo sitio: lo escribe `dibujar_perfil` al dibujar y lo vuelve a escribir la ventana, sin redibujar nada, cuando el físico cambia la capa
    reportada. Dice la capa, el eje y el FWHM, o que no se midió. `reportada` rotula «(reportada)» el nombre de la capa elegida en el menú «Capa reportada»."""
    nombre = nombre_de_la_capa(capa) + (" (reportada)" if reportada else "")
    if medida.ok:
        return f"{nombre}, {NOMBRE_DEL_EJE[medida.eje]}: FWHM {numero(medida.fwhm_mm, 3)} mm"
    return f"{nombre}, {NOMBRE_DEL_EJE[medida.eje]}: {NO_MEDIBLE}"


def texto_se_guarda(capa, reportada, motivo, registro=False):
    """Lo que dice, en la fila de una capa del panel de la pestaña 3, si esa capa se guarda. Solo la fila de la capa REPORTADA dice algo; las demás, vacío. `motivo` es lo que devuelve
    `services.placa_mensual.motivo_para_no_guardar(resultado, reportada)` (None si se puede guardar). Con un análisis guardado a la vista (`registro`) la fila dice «guardada» y, si en lo recalculado
    la capa ya no es medible, lo dice: nunca afirma que se guarda lo que el guardado rechaza (corolario 6)."""
    if capa != reportada:
        return ""
    if registro:
        return "guardada" if motivo is None else "guardada; en lo recalculado no es medible"
    return "se guarda" if motivo is None else "no se guarda: no es medible"


def _colores(capas):
    return [NOMBRE_DE_CAPA[c] for c in capas]


def _unir(elementos):
    elementos = list(elementos)
    return elementos[0] if len(elementos) == 1 else ", ".join(elementos[:-1]) + " y " + elementos[-1]


def texto_de_la_regla(motivo, guardables):
    """La línea que dice por qué NO se ofrece guardar (D.1b): el texto del servicio TAL CUAL, con el prefijo de la ventana, y qué más se puede hacer. `motivo`: el texto de
    `services.placa_mensual.motivo_para_no_guardar(resultado, capa elegida)`. `guardables`: las capas (R, G o B) para las que la MISMA función da None. Si hay alguna, las nombra («En esta película sí se
    pueden guardar: verde y azul; elija una en el menú «Capa reportada».»); si ninguna, lo dice UNA vez («Ninguna de las tres capas es medible...»). Nunca mueve el menú, ni guarda por su cuenta, ni agrega
    remedios propios: los del motor vienen en su motivo."""
    texto = con_punto_final(PREFIJO_DE_LA_REGLA + motivo)
    guardables = [c for c in CAPAS if c in guardables]
    if not guardables:
        return texto + " Ninguna de las tres capas es medible en esta película: de este análisis no se guarda nada, ni la imagen."
    if len(guardables) == 1:
        return texto + f" En esta película sí se puede guardar la capa {ADJETIVO_DE_LA_CAPA[guardables[0]]}; elíjala en el menú «Capa reportada»."
    return texto + f" En esta película sí se pueden guardar: {_unir(_colores(guardables))}; elija una en el menú «Capa reportada»."


def nota_de_la_pestana_1(motivo, reportada, registro=False):
    """La nota bajo la tabla de desfases del gris: o lo que se guarda y se imprime (la capa reportada, que se ve en la pestaña 3) o, si esa capa no es medible, el texto del servicio TAL CUAL (D.1b)."""
    if motivo is not None and not registro:
        return motivo
    capa = f"la capa {ADJETIVO_DE_LA_CAPA[reportada]}" if reportada in CAPAS else "ninguna capa"
    if registro:
        return (f"Estos son los desfases del perfil de grises. Lo guardado y lo que imprime el PDF es {capa}, que se ve en la pestaña 3." if reportada in CAPAS
                else "Estos son los desfases del perfil de grises. Este registro no guardó ninguna capa reportada.")
    return f"Estos son los desfases del perfil de grises. Lo que se guarda y se imprime es lo de {capa}, que se ve en la pestaña 3."


def tabla_de_desfases(resultado, capa="gris"):
    """Las filas (rótulo, valor) de la tabla de la pestaña 1: de la capa `capa` (el gris), respecto del campo luminoso el desfase de cada lado (radiación − luz, positivo hacia afuera) y, respecto del centro de
    radiación, los tres centros (radiación − cruce de diagonales, luz − retículo y radiación − retículo; x; y). Los números son los del motor, sin recalcular."""
    medida = resultado.capas[capa]
    filas = [(f"Lado {lado} (radiación − luz) [mm]", numero(medida.coincidencia_mm.get(lado), 3, True)) for lado in motor.LADOS_DE_LA_COINCIDENCIA]
    filas.append(("Radiación − cruce de diagonales (x; y) [mm]", _par(medida.radiacion_menos_luz_mm)))
    filas.append(("Luz − retículo (x; y) [mm]", _par(resultado.luz_menos_reticulo_mm)))
    filas.append(("Radiación − retículo (x; y) [mm]", _par(medida.radiacion_menos_reticulo_mm)))
    return filas


COLUMNAS_DE_LOS_PERFILES = ("Capa", "Eje", "Estado", "FWHM [mm]", "Desfase izquierdo o superior [mm]", "Desfase derecho o inferior [mm]", "Penumbra izquierda o superior [mm]",
                            "Penumbra derecha o inferior [mm]", "Piso [nivel]", "Meseta [nivel]", "Avisos", "Se guarda")


def filas_de_los_perfiles(resultado, reportada, motivo, registro=False):
    """Las filas del panel de la pestaña 3: una por capa (R, G, B y el gris, cada una por separado, sin ninguna marca que las compare) y eje: el estado, el FWHM, el desfase de los dos lados, las penumbras, el
    piso, la meseta y los avisos; la fila de la capa reportada dice si se guarda (`texto_se_guarda`). Cada fila es una tupla de `COLUMNAS_DE_LOS_PERFILES`, con los números como texto."""
    filas = []
    for capa in (*CAPAS, "gris"):
        m = resultado.capas[capa]
        for eje in motor.EJES:
            p = getattr(m, eje)
            lados = LADOS_DE_CADA_EJE[eje]
            filas.append((nombre_de_la_capa(capa), NOMBRE_DEL_EJE[eje], "ok" if p.ok else p.estado, numero(p.fwhm_mm, 3),
                          numero(m.coincidencia_mm.get(lados[0]), 3, True), numero(m.coincidencia_mm.get(lados[1]), 3, True),
                          numero(p.penumbras_mm[0], 3), numero(p.penumbras_mm[1], 3), numero(p.piso if p.piso is not None else m.piso, 1), numero(p.meseta, 1),
                          "; ".join(p.avisos), texto_se_guarda(capa, reportada, motivo, registro)))
    return filas


def lado_perfecto_mm(geometria):
    """El lado del cuadrado perfecto con el que se compara el recuadro: el medio de los cuatro lados medidos [mm]."""
    return float(np.mean(list(geometria.lados_mm.values())))


def filas_de_la_cuadratura(geometria):
    """Las filas (rótulo, valor, cuadrado perfecto, diferencia) de la pestaña 5, todo como texto: la longitud de cada lado [mm] y su diferencia con el lado del cuadrado perfecto (el medio de los cuatro), la
    inclinación de cada lado [°] (frente a 0), los cuatro ángulos interiores [°] (frente a 90), las dos diagonales [mm] (frente a la del cuadrado perfecto, lado × raíz de 2) y el ángulo girado [°] (frente a
    0). Los números son los de la geometría del campo luminoso (C.1); no dependen de la capa."""
    lado = lado_perfecto_mm(geometria)
    filas = []
    for nombre in motor.LADOS:
        valor = geometria.lados_mm[nombre]
        filas.append((f"Lado {nombre} [mm]", numero(valor, 3), numero(lado, 3), numero(valor - lado, 3, True)))
    for nombre in motor.LADOS:
        valor = geometria.inclinacion_de_los_lados_grados[nombre]
        filas.append((f"Inclinación del lado {nombre} [°]", numero(valor, 3, True), numero(0.0, 3), numero(valor, 3, True)))
    for nombre, valor in geometria.angulos_interiores_grados.items():
        filas.append((f"Ángulo interior {_ESQUINA[nombre]} [°]", numero(valor, 3), numero(90.0, 3), numero(valor - 90.0, 3, True)))
    diagonal = lado * math.sqrt(2.0)
    for nombre, valor in zip(("principal", "secundaria"), geometria.diagonales_mm):
        filas.append((f"Diagonal {nombre} [mm]", numero(valor, 3), numero(diagonal, 3), numero(valor - diagonal, 3, True)))
    filas.append(("Ángulo girado [°]", numero(geometria.angulo_grados, 3, True), numero(0.0, 3), numero(geometria.angulo_grados, 3, True)))
    return filas


COLUMNAS_DE_LA_CUADRATURA = ("Medida", "Valor", "Cuadrado perfecto", "Diferencia")
COLUMNAS_DE_LOS_BARRIDOS = ("Capa", "Eje", "Estado", "Bandas", "Bandas medidas", "Media [mm]", "Mediana [mm]", "Desviación [mm]", "Corte central [mm]", "Corte central menos mediana [mm]")


def filas_de_los_barridos(barrido):
    """Las filas de la tabla de la pestaña 4: por capa (R, G, B y el gris) y eje, cuántas bandas tiene el barrido y cuántas se midieron, la media, la mediana y la desviación estándar (de la población) del FWHM
    de las medibles, el corte central (la banda 0) y cuánto se aleja de la mediana. Ninguna banda se descarta; los números son los del motor."""
    filas = []
    for capa in (*CAPAS, "gris"):
        for eje in motor.EJES:
            b = barrido.ejes[eje].capas[capa]
            e = b.estadistica
            central = b.central
            central_mm = None if central is None else central.fwhm_mm
            lejos = None if central_mm is None or e.mediana_mm is None else central_mm - e.mediana_mm
            filas.append((nombre_de_la_capa(capa), NOMBRE_DEL_EJE[eje], "ok" if b.ok else b.estado, str(e.n_bandas), str(e.n_medibles),
                          numero(e.media_mm, 3), numero(e.mediana_mm, 3), numero(e.desviacion_mm, 3), numero(central_mm, 3), numero(lejos, 3, True)))
    return filas


def _valor_del_pie(valor):
    """Un parámetro como se dice en el pie: una lista con comas, un diccionario por capa («R 60 a 140, G 145 a 200...»), un booleano con sí o no."""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, dict):
        return ", ".join(f"{clave} {v[0]:g} a {v[1]:g}" for clave, v in valor.items())
    if isinstance(valor, (list, tuple)):
        return ", ".join(f"{v:g}" for v in valor)
    return valor


def texto_de_parametros(parametros=None):
    """El pie de parámetros fijos de la ventana (PD1): las frases de las entradas «pie» de `TRAZO_DE_PARAMETRO`, con el valor con que se midió (`parametros`: los del análisis, que se guardan con él; por omisión los
    de fábrica `motor.VALORES_DE_LA_GEOMETRIA`), en líneas de `LARGO_DEL_PIE` caracteres sin partir una frase."""
    P = motor.VALORES_DE_LA_GEOMETRIA if parametros is None else parametros
    titulo = "Parámetros fijos del método (se guardan con cada análisis; no se ajustan en pantalla):"
    lineas, linea = [], titulo
    for clave, (donde, plantilla) in TRAZO_DE_PARAMETRO.items():
        if donde != "pie":
            continue
        valor = _valor_del_pie(P[clave])
        frase = plantilla.format(valor)
        union = " " if linea == titulo else " · "
        if linea != titulo and len(linea) + len(union) + len(frase) > LARGO_DEL_PIE:
            lineas.append(linea)
            linea = frase
        else:
            linea += union + frase
    lineas.append(linea)
    return "\n".join(lineas)


# ----------------------------------------------------------------------------------------------------- marcos

def a_imagen(matriz, puntos):
    """Lleva `puntos` [(x, y)] del marco GIRADO al de la IMAGEN con la inversa de la matriz de giro del motor (2 x 3: imagen -> girado). Es la cuenta inversa de `motor.transformar_puntos`."""
    m = np.asarray(matriz, dtype=np.float64)
    inversa = np.linalg.inv(m[:, :2])
    traslado = m[:, 2]
    return [tuple(float(v) for v in inversa @ (np.asarray(p, dtype=np.float64) - traslado)) for p in puntos]


def _rectangulo(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _cerrado(puntos):
    return list(puntos) + [puntos[0]]


def imagen_rgb(pelicula):
    """La película como RGB uint8 (alto, ancho, 3) para mostrarla en su color original. En 8 bits son los mismos valores del archivo (el color BGR de OpenCV puesto en orden R, G, B, una sola copia); en 16 bits,
    los niveles de 8 bits redondeados de cada capa (así se muestra la de 16 bits, A.1). Un RGB uint8 con `nearest` cuesta 101 MB para una página del escáner (6600 x 5100); un gris 2D con mapa de color, 2 GB."""
    if pelicula.bits == 8:
        _gris, bgr = pelicula.en_bgr()
        return np.ascontiguousarray(bgr[:, :, ::-1])
    rgb = np.empty(pelicula.validos.shape + (3,), np.uint8)
    for k, capa in enumerate(CAPAS):
        rgb[:, :, k] = np.clip(np.rint(getattr(pelicula, capa)), 0, 255)
    return rgb


# ----------------------------------------------------------------------------------------------------- la pestaña 1: la imagen

def _etiqueta(primera, texto):
    """La etiqueta de la leyenda solo en el primer trazo de su clase."""
    return texto if primera else "_" + texto


def dibujar_imagen(ax, rgb):
    """La imagen cruda en su color original, sin interpolar (cada píxel es un píxel) y con los ejes en píxeles de la imagen."""
    ax.imshow(rgb, interpolation="nearest")
    ax.set_xlabel("columna de la imagen [px]")
    ax.set_ylabel("fila de la imagen [px]")


def dibujar_marcas(ax, marcas):
    """Los clics tal como se marcaron (un «+» naranja numerado en el orden en que se hicieron), el punto con que se mide cuando la marca se refinó (un círculo azul y el segmento desde el clic) y el círculo de
    búsqueda de `radio_marca_mm` alrededor del clic (la marca «sin refinar» trae el clic y su círculo, y el punto con que se mide es el clic). Cada trazo lleva su `gid` (`marca:clic`, `marca:punto`,
    `marca:desplazamiento`, `marca:circulo`, `marca:numero`) para que una prueba lo encuentre."""
    t = np.linspace(0.0, 2.0 * math.pi, PUNTOS_DEL_CIRCULO)
    hubo_refinada = False
    for i, marca in enumerate(marcas):
        m = marca_como_dict(marca)
        cx, cy = m["clic"]
        px, py = m["punto"]
        ax.plot([cx], [cy], "+", color=COLOR_CLIC, ms=12, mew=2, gid="marca:clic", label=_etiqueta(i == 0, "clic"))
        ax.annotate(str(i + 1), (cx, cy), xytext=(6, -6), textcoords="offset points", color=COLOR_CLIC, fontsize=8, gid="marca:numero")
        if m["estado"] == motor.ESTADO_REFINADA:
            ax.plot([cx, px], [cy, py], "-", color=COLOR_REFINADO, lw=0.8, gid="marca:desplazamiento", label="_desplazamiento")
            ax.plot([px], [py], "o", ms=5, mfc="none", mec=COLOR_REFINADO, mew=1.4, gid="marca:punto", label=_etiqueta(not hubo_refinada, "punto refinado"))
            hubo_refinada = True
        if m.get("radio_px"):
            r = float(m["radio_px"])
            ax.plot(cx + r * np.cos(t), cy + r * np.sin(t), "--", color=COLOR_CLIC, lw=0.8, gid="marca:circulo", label=_etiqueta(i == 0, TRAZO_DE_PARAMETRO["radio_marca_mm"][1]))


def dibujar_sexto_clic(ax, punto, lado_px):
    """El sexto clic, sobre película sin irradiar: un «+» y el cuadrado de `lado_punto_manual_mm` de lado (`lado_px`, en píxeles) con que se toma el piso."""
    x, y = float(punto[0]), float(punto[1])
    ax.plot([x], [y], "+", color=COLOR_PISO, ms=12, mew=2, gid="sexto:clic", label="punto sin irradiar (sexto clic)")
    mitad = lado_px / 2.0
    cuadrado = _cerrado(_rectangulo(x - mitad, x + mitad, y - mitad, y + mitad))
    ax.plot([p[0] for p in cuadrado], [p[1] for p in cuadrado], "-", color=COLOR_PISO, lw=1.2, gid="sexto:cuadrado", label=TRAZO_DE_PARAMETRO["lado_punto_manual_mm"][1])


def dibujar_recuadro(ax, esquinas, cruce=None, reticulo=None, etiquetas=True):
    """El recuadro del campo luminoso (`esquinas`: UL, UR, DR, DL, en el marco del eje), sus dos diagonales y, si se dan, el cruce de las diagonales (el centro luminoso) y el retículo."""
    cerrado = _cerrado(esquinas)
    ax.plot([p[0] for p in cerrado], [p[1] for p in cerrado], "-", color=COLOR_RECUADRO, lw=1.5, gid="recuadro", label=_etiqueta(etiquetas, "recuadro del campo luminoso"))
    ul, ur, dr, dl = esquinas
    ax.plot([ul[0], dr[0]], [ul[1], dr[1]], "--", color=COLOR_RECUADRO, lw=0.9, gid="diagonal", label=_etiqueta(etiquetas, "diagonales"))
    ax.plot([ur[0], dl[0]], [ur[1], dl[1]], "--", color=COLOR_RECUADRO, lw=0.9, gid="diagonal", label="_diagonales")
    if cruce is not None:
        ax.plot([cruce[0]], [cruce[1]], "x", color=COLOR_CRUCE, ms=11, mew=2, gid="cruce", label=_etiqueta(etiquetas, "cruce de diagonales (centro luminoso)"))
    if reticulo is not None:
        ax.plot([reticulo[0]], [reticulo[1]], "s", ms=6, mfc="none", mec=COLOR_RECUADRO, mew=1.4, gid="reticulo", label=_etiqueta(etiquetas, "retículo"))


def _bandas_de_los_perfiles(resultado):
    """{eje: (primera fila, fin)} de las bandas de 1 mm de los perfiles centrales, en el marco girado, tal como las usó el motor (`PerfilCentral.filas_px`); de la primera capa que tenga el perfil."""
    bandas = {}
    for eje in motor.EJES:
        for capa in ("gris", *CAPAS):
            perfil = getattr(resultado.capas[capa], eje).perfil
            if perfil is not None:
                bandas[eje] = tuple(perfil.filas_px)
                break
    return bandas


def zona_central(resultado, barrido):
    """((x0, x1), (y0, y1)) de la zona central de la meseta y del barrido en el marco girado: la del barrido (`BarridoDeEje.zona_px`: la del eje inplane es la de las columnas y la del crossplane la de las
    filas, que son las zonas centrales de los perfiles perpendiculares), o None si el barrido no tiene región."""
    if barrido is None:
        return None
    cruzado, inplane = barrido.ejes["crossplane"], barrido.ejes["inplane"]
    if cruzado.zona_px is None or inplane.zona_px is None:
        return None
    return tuple(inplane.zona_px), tuple(cruzado.zona_px)


def dibujar_geometria(ax, resultado, barrido, marcas):
    """Todo lo que se usó para medir, sobre la IMAGEN: el recuadro del campo luminoso (las esquinas con que se midió, que son `recuadro_luminoso(marcas)`, la misma función que dibujará el PDF), sus
    diagonales, el cruce y el retículo; las dos bandas de `banda_perfil_mm` de donde salen los perfiles centrales (crossplane e inplane, a todo lo ancho de la película) y la zona central de la meseta y del
    barrido (sombreada). Lo que viene de la película girada se lleva a la imagen con la inversa de la matriz de giro del motor."""
    recuadro = motor.recuadro_luminoso(marcas) if marcas else None
    if recuadro is None or not recuadro.ok:
        return
    geometria = resultado.geometria
    ok = geometria is not None and geometria.ok
    dibujar_recuadro(ax, recuadro.esquinas, geometria.cruce if ok else None, geometria.reticulo if ok else (resultado.puntos.reticulo if resultado.puntos is not None else None))
    girada = resultado.girada
    if girada is None or not ok:
        return
    M = geometria.matriz_de_giro
    ox, oy = girada.origen
    alto, ancho = girada.capas["gris"].shape
    for i, (eje, (primera, fin)) in enumerate(_bandas_de_los_perfiles(resultado).items()):
        esquinas = _rectangulo(ox - 0.5, ox + ancho - 0.5, primera - 0.5, fin - 0.5) if eje == "crossplane" else _rectangulo(primera - 0.5, fin - 0.5, oy - 0.5, oy + alto - 0.5)
        puntos = a_imagen(M, esquinas)
        ax.fill([p[0] for p in puntos], [p[1] for p in puntos], color=COLOR_BANDA, alpha=0.45, lw=0.6, gid=f"banda:{eje}", label=_etiqueta(i == 0, TRAZO_DE_PARAMETRO["banda_perfil_mm"][1] + " (1 mm)"))
    zona = zona_central(resultado, barrido)
    if zona is not None:
        (x0, x1), (y0, y1) = zona
        puntos = a_imagen(M, _rectangulo(x0, x1, y0, y1))
        ax.fill([p[0] for p in puntos], [p[1] for p in puntos], facecolor=COLOR_ZONA, alpha=0.15, edgecolor=COLOR_ZONA, lw=0.8, gid="zona", label=TRAZO_DE_PARAMETRO["fraccion_meseta"][1] + " y del barrido")


def dibujar_region_del_piso(ax, resultado, marco="imagen"):
    """De dónde salió el piso (R7). En la IMAGEN, los píxeles que se usaron (`Piso.region.mascara`, en verde) y, en los dos marcos, la caja de cada esquina usada y la del punto marcado (`Piso.esquinas[i].caja`
    y `region.caja`); una esquina que se tomó con un respaldo lleva su rótulo («giro +5 grados»). En el modo película virgen no hay región en la película y no se dibuja nada."""
    piso = resultado.piso
    geometria = resultado.geometria
    if piso is None or piso.region is None or geometria is None or geometria.matriz_de_giro is None:
        return
    M = geometria.matriz_de_giro
    if marco == "imagen":
        x0, y0, x1, y1 = piso.region.caja
        rgba = np.zeros(piso.region.mascara.shape + (4,), np.uint8)
        rgba[piso.region.mascara] = (0, 176, 80, 150)
        limites = ax.get_xlim(), ax.get_ylim()
        ax.imshow(rgba, extent=(x0 - 0.5, x1 - 0.5, y1 - 0.5, y0 - 0.5), interpolation="nearest", zorder=3, gid="piso:pixeles")
        ax.set_xlim(*limites[0])
        ax.set_ylim(*limites[1])
    partes = [(e.esquina, e.caja, e.origen) for e in piso.esquinas if e.estado in ("ok", "reemplazada") and e.caja is not None]
    if piso.origen == "manual":
        partes = [("punto", piso.region.caja, "punto marcado")]
    for i, (nombre, caja, origen) in enumerate(partes):
        x0, y0, x1, y1 = caja
        esquinas = _cerrado(_rectangulo(x0 - 0.5, x1 - 0.5, y0 - 0.5, y1 - 0.5))
        puntos = esquinas if marco == "imagen" else [tuple(p) for p in motor.transformar_puntos(M, esquinas)]
        ax.plot([p[0] for p in puntos], [p[1] for p in puntos], "-", color=COLOR_PISO, lw=1.2, gid=f"piso:caja:{nombre}", label=_etiqueta(i == 0, "región del piso"))
        if origen not in ("esquina", "punto marcado"):
            centro = ((x0 + x1) / 2.0 - 0.5, (y0 + y1) / 2.0 - 0.5)
            centro = centro if marco == "imagen" else tuple(motor.transformar_puntos(M, [centro])[0])
            ax.annotate(origen, centro, xytext=(8, 8), textcoords="offset points", color=COLOR_PISO, fontsize=8, gid=f"piso:rotulo:{nombre}")


def dibujar_leyenda_de_la_imagen(ax):
    """La leyenda de la imagen, a la DERECHA del eje (la imagen llena el eje y ningún rincón de adentro está libre; el alto es lo escaso, no el ancho)."""
    manejadores, etiquetas = ax.get_legend_handles_labels()
    if manejadores:
        caja = ax.legend(manejadores, [textwrap.fill(e, ANCHO_DE_LA_LEYENDA) for e in etiquetas], loc="center left", bbox_to_anchor=(1.02, 0.5), ncol=1, fontsize=7, borderaxespad=0.0)
        caja.set_gid("leyenda")


# ----------------------------------------------------------------------------------------------------- un perfil

def _mm(px, medida):
    """Una posición a lo largo del eje, en píxeles del marco girado, en milímetros desde el cruce de diagonales."""
    return (np.asarray(px, dtype=np.float64) - medida.centro_px) * medida.tam_mm


def _vertical(ax, px, medida, **estilo):
    return ax.axvline(float(_mm(px, medida)), **estilo)


def dibujar_perfil(ax, medida, capa, parametros=None, reportada=False):
    """El perfil de UNA capa en UN eje, COMPLETO (PD1): el eje x cubre la película entera a los dos lados del campo, en milímetros desde el cruce de diagonales; el y va de lo más bajo del perfil (la marca del
    retículo) a lo más alto. Dibuja el perfil crudo (la banda de 1 mm promediada) y el suavizado con que se buscaron los cruces, el piso (`-.`), la media de la meseta (discontinua), la altura media (continua),
    los niveles de la penumbra (finos), los límites de la zona central y de la exclusión del retículo (punteadas), los bordes de radiación (verticales continuas del color de la capa) y los bordes luminosos de
    esa línea (naranja). Lo que la medida no tiene (un perfil que no se pudo medir) no se dibuja; si no hay ni el perfil, dice por qué. `parametros`: los del análisis, solo para el porcentaje y la ventana de
    cada etiqueta. Cada trazo lleva su `gid` (`perfil:crudo`, `perfil:suavizado`, `perfil:piso`, `perfil:meseta`, `perfil:altura_media`, `perfil:penumbra_alta`, `perfil:penumbra_baja`, `perfil:zona`,
    `perfil:exclusion`, `perfil:borde_luz`, `perfil:borde_rad`, `perfil:cruce`)."""
    P = motor.VALORES_DE_LA_GEOMETRIA if parametros is None else parametros
    color = COLOR_CAPA[capa]
    ax.set_title(titulo_del_perfil(medida, capa, reportada), fontsize=8)
    ax.set_xlabel("posición desde el cruce de diagonales [mm]")
    ax.set_ylabel("valor de píxel [nivel]")
    perfil = medida.perfil
    if perfil is None or medida.centro_px is None:
        ax.text(0.5, 0.5, textwrap.fill(medida.estado, 55), transform=ax.transAxes, ha="center", va="center", fontsize=8, color=TINTA_SUAVE, gid="perfil:sin_medida")
        return
    x = _mm(perfil.desde_px + np.arange(len(perfil.valores)), medida)
    ax.plot(x, perfil.valores, color=TINTA_SUAVE, lw=0.7, gid="perfil:crudo", label="perfil, promedio de la banda")
    if medida.suavizado is not None:
        ax.plot(x, medida.suavizado, color=color, lw=1.2, gid="perfil:suavizado", label=f"{TRAZO_DE_PARAMETRO['suavizado_perfil_mm'][1]}, ventana de {P['suavizado_perfil_mm']:g} mm")
    if medida.piso is not None:
        ax.axhline(medida.piso, color=TINTA, ls="-.", lw=1, gid="perfil:piso", label="piso")
    if medida.meseta is not None:
        ax.axhline(medida.meseta, color=TINTA_SUAVE, ls="--", lw=1, gid="perfil:meseta", label="media de la meseta")
    if medida.altura_media is not None:
        ax.axhline(medida.altura_media, color=color, ls="-", lw=1, gid="perfil:altura_media", label=f"{TRAZO_DE_PARAMETRO['altura_media'][1]}, al {P['altura_media']:.0%} entre el piso y la meseta")
    for clave, nivel in (("penumbra_alta", medida.nivel_penumbra_alta), ("penumbra_baja", medida.nivel_penumbra_baja)):
        if nivel is not None:
            ax.axhline(nivel, color=color, ls=":", lw=0.6, gid=f"perfil:{clave}", label=f"{TRAZO_DE_PARAMETRO[clave][1]}, al {P[clave]:.0%}")
    if medida.zona_px is not None:
        for i, borde in enumerate(medida.zona_px):
            _vertical(ax, borde, medida, color=COLOR_ZONA, ls=":", lw=1, gid="perfil:zona", label=_etiqueta(i == 0, "límites de la zona central de la meseta"))
    if medida.exclusion_px is not None:
        for i, borde in enumerate(medida.exclusion_px):
            _vertical(ax, borde, medida, color=COLOR_EXCLUSION, ls=":", lw=1, gid="perfil:exclusion", label=_etiqueta(i == 0, TRAZO_DE_PARAMETRO["excepcion_centro_mm"][1]))
    if medida.bordes_luz_px is not None:
        for i, borde in enumerate(medida.bordes_luz_px):
            _vertical(ax, borde, medida, color=COLOR_LUZ, ls="-.", lw=1.2, gid="perfil:borde_luz", label=_etiqueta(i == 0, "bordes luminosos de esta línea"))
    for i, borde in enumerate(b for b in medida.bordes_rad_px if b is not None):
        _vertical(ax, borde, medida, color=color, ls="-", lw=1.6, gid="perfil:borde_rad", label=_etiqueta(i == 0, "bordes de radiación"))
    ax.axvline(0.0, color=COLOR_CRUCE, ls="-", lw=0.8, gid="perfil:cruce", label="cruce de diagonales")
    ax.set_xlim(float(x[0]), float(x[-1]))
    finitos = perfil.valores[np.isfinite(perfil.valores)]
    valores = ([float(finitos.min()), float(finitos.max())] if len(finitos) else []) + [v for v in (medida.piso, medida.meseta) if v is not None]
    if valores:
        holgura = 0.05 * max(max(valores) - min(valores), 1.0)
        ax.set_ylim(min(valores) - holgura, max(valores) + holgura)
    ax.grid(color=COLOR_REJILLA)


def dibujar_leyenda_de_los_perfiles(figura, ejes, columnas=4):
    """La leyenda de los perfiles, UNA para toda la figura (debajo, en `columnas` columnas): los trazos del eje de `ejes` que tiene más (el de un perfil medido tiene todos)."""
    mejor = max(ejes, key=lambda ax: len(ax.get_legend_handles_labels()[0]))
    manejadores, etiquetas = mejor.get_legend_handles_labels()
    if manejadores:
        caja = figura.legend(manejadores, etiquetas, loc="outside lower center", ncol=columnas, fontsize=7)
        caja.set_gid("leyenda")


def dibujar_perfiles_del_gris(figura, resultado):
    """Los dos perfiles del GRIS (crossplane arriba, inplane debajo) con todas sus líneas: lo que va al lado de la imagen en la pestaña 1. No cambian con el menú «Capa reportada»."""
    ejes = list(figura.subplots(2, 1))
    for ax, eje in zip(ejes, motor.EJES):
        dibujar_perfil(ax, getattr(resultado.capas["gris"], eje), "gris", resultado.parametros)
    dibujar_leyenda_de_los_perfiles(figura, ejes, columnas=2)
    return dict(zip(motor.EJES, ejes))


def dibujar_perfiles_por_capa(figura, resultado, reportada=None):
    """La pestaña 3: una columna con los perfiles crossplane y al lado la de los inplane, una gráfica por capa (R, G, B y el gris), cada una con todas sus líneas. Devuelve {(capa, eje): eje de la figura}.
    `reportada`: la capa que el menú «Capa reportada» tiene elegida (su título lleva «(reportada)»)."""
    ejes = figura.subplots(4, 2)
    salida = {}
    for fila, capa in enumerate((*CAPAS, "gris")):
        for columna, eje in enumerate(motor.EJES):
            ax = ejes[fila][columna]
            dibujar_perfil(ax, getattr(resultado.capas[capa], eje), capa, resultado.parametros, reportada=(capa == reportada))
            if capa != "gris":
                ax.set_xlabel("")                       # el eje x es el mismo en las cuatro filas: el rótulo va solo en la de abajo
            salida[(capa, eje)] = ax
    dibujar_leyenda_de_los_perfiles(figura, list(salida.values()))
    return salida


# ----------------------------------------------------------------------------------------------------- la pestaña 2: las capas

def colorear(normalizada):
    """El mapa de color `jet` aplicado a un arreglo normalizado entre 0 y 1 (lo de afuera se recorta; un NaN queda transparente): RGBA uint8. Se aplica ANTES de dibujar (una imagen 2D con mapa de color pedía
    2062 MB por dibujo en una página; en RGB uint8, 129 MB): `matplotlib` entra solo aquí y en `dibujar_capas`."""
    from matplotlib import colormaps
    return colormaps["jet"](np.clip(normalizada, 0.0, 1.0), bytes=True)


def capa_acondicionada(resultado, capa):
    """(arreglo, texto, meseta): la capa girada normalizada entre su piso y su meseta (0 en el piso, 1 en la meseta: `motor.normalizar`) para dibujarla, el texto que lo dice y la meseta usada. La meseta es el promedio
    de las de sus dos perfiles (o la del que la tiene). Lo que no tiene dato (lo que el giro dejó fuera de la película) queda NaN. Si la capa no tiene piso o ninguno de sus perfiles tiene meseta no se puede
    acondicionar: el arreglo es la capa tal cual dividida entre 255, el texto dice por qué y la meseta es None."""
    girada = resultado.girada
    datos = girada.capas[capa]
    m = resultado.capas[capa]
    mesetas = [p.meseta for p in (m.crossplane, m.inplane) if p.meseta is not None]
    if m.piso is None or not mesetas:
        motivo = m.estado if m.estado != "ok" else "la capa no tiene meseta medida"
        return np.asarray(datos, dtype=np.float32) / np.float32(255.0), f"sin acondicionar (0 a 255): {motivo}", None
    meseta = float(np.mean(mesetas))
    normalizada = motor.normalizar(motor.BASE_VALOR_DE_PIXEL, datos, m.piso, meseta).astype(np.float32)
    normalizada[~girada.validos] = np.nan
    return normalizada, f"0 es el piso ({numero(m.piso, 1)}) y 1 la meseta ({numero(meseta, 1)})", meseta


def dibujar_capas(figura, resultado):
    """La pestaña 2: las tres capas R, G y B de la película girada, cada una acondicionada (normalizada entre su piso y su meseta) en `jet` con su barra de color aparte; encima, la cruz de línea punteada blanca por el
    cruce de diagonales, la cuadrícula, el recuadro del campo luminoso (en el marco girado) y la región del piso. Devuelve {capa: eje}. Sin película girada dice por qué."""
    from matplotlib import cm
    from matplotlib.colors import Normalize
    if resultado.girada is None:
        ax = figura.subplots(1, 1)
        ax.axis("off")
        ax.text(0.5, 0.5, textwrap.fill(f"No hay imagen acondicionada: {resultado.estado}", 70), transform=ax.transAxes, ha="center", va="center", fontsize=9, gid="capas:sin_imagen")
        return {}
    girada = resultado.girada
    ox, oy = girada.origen
    ejes = figura.subplots(1, len(CAPAS))
    salida = {}
    for ax, capa in zip(ejes, CAPAS):
        normalizada, texto, meseta = capa_acondicionada(resultado, capa)
        alto, ancho = normalizada.shape
        ax.imshow(colorear(normalizada), extent=(ox - 0.5, ox + ancho - 0.5, oy + alto - 0.5, oy - 0.5), interpolation="nearest", gid="capas:imagen")
        cx, cy = girada.cruce
        ax.axvline(cx, color="white", ls=":", lw=1.2, gid="capas:cruz_vertical", label="_cruz")
        ax.axhline(cy, color="white", ls=":", lw=1.2, gid="capas:cruz_horizontal", label="_cruz")
        ax.grid(True, color="black", lw=0.4, alpha=0.5)
        geometria = resultado.geometria
        if geometria is not None and geometria.esquinas_giradas:
            dibujar_recuadro(ax, geometria.esquinas_giradas, None, geometria.reticulo_girado, etiquetas=False)
        dibujar_region_del_piso(ax, resultado, marco="girado")
        ax.set_xlim(ox - 0.5, ox + ancho - 0.5)
        ax.set_ylim(oy + alto - 0.5, oy - 0.5)
        ax.set_title(f"Capa {ADJETIVO_DE_LA_CAPA[capa]}: {texto}", fontsize=8)
        ax.set_xlabel("columna de la película girada [px]")
        ax.set_ylabel("fila de la película girada [px]")
        barra = figura.colorbar(cm.ScalarMappable(norm=Normalize(0.0, 1.0), cmap="jet"), ax=ax, location="bottom", shrink=0.9, pad=0.12)
        barra.set_label("normalizada: piso 0, meseta 1" if meseta is not None else "nivel de la capa entre 255")
        salida[capa] = ax
    return salida


# ----------------------------------------------------------------------------------------------------- la pestaña 4: los barridos

def dibujar_barridos(figura, barrido):
    """La pestaña 4: el FWHM de cada banda contra su posición [mm], crossplane arriba e inplane debajo, las cuatro capas en el mismo gráfico, cada una con su media (discontinua), su mediana (punteada), el corte
    central marcado (la banda 0) y los límites de la zona central en el eje. Todas las bandas: una que no se pudo medir queda como hueco y se marca al pie. Sin selector (PD2): el barrido no tiene parámetro.
    Devuelve {eje: eje de la figura}."""
    ejes = figura.subplots(2, 1)
    salida = {}
    for ax, eje in zip(ejes, motor.EJES):
        b = barrido.ejes[eje]
        salida[eje] = ax
        ax.set_title(f"Barrido {NOMBRE_DEL_EJE[eje]}: FWHM de cada banda de {numero(b.banda_mm, 1)} mm" if b.ok else f"Barrido {NOMBRE_DEL_EJE[eje]}: {b.estado}", fontsize=9)
        ax.set_xlabel("posición de la banda respecto del cruce de diagonales [mm]")
        ax.set_ylabel("FWHM [mm]")
        ax.grid(color=COLOR_REJILLA)
        if not b.ok:
            ax.text(0.5, 0.5, textwrap.fill(b.estado, 80), transform=ax.transAxes, ha="center", va="center", fontsize=9, color=TINTA_SUAVE, gid="barrido:sin_region")
            continue
        huecos = []
        rotulados = set()

        def una_vez(clave, texto):
            """El rótulo de la leyenda en el PRIMER trazo que dibuja ese elemento y oculto en los demás: cada elemento sale UNA vez por eje, sea cual sea la capa que lo dibuja primero (la roja puede no medirse: PD1,
            cada gráfica dibuja y explica todo lo que se usó)."""
            if clave in rotulados:
                return "_" + texto
            rotulados.add(clave)
            return texto
        for capa in (*CAPAS, "gris"):
            c = b.capas[capa]
            if not c.bandas:
                continue
            color = COLOR_CAPA[capa]
            posiciones = np.array([x.posicion_mm for x in c.bandas])
            valores = np.array([np.nan if x.fwhm_mm is None else x.fwhm_mm for x in c.bandas])
            ax.plot(posiciones, valores, "-o", ms=2.5, lw=0.9, color=color, gid=f"barrido:bandas:{capa}", label=f"capa {ADJETIVO_DE_LA_CAPA[capa]}" if capa != "gris" else "gris")
            if (~np.isfinite(valores)).any():
                huecos.append((capa, posiciones[~np.isfinite(valores)]))
            if c.central is not None and c.central.fwhm_mm is not None:
                ax.plot([c.central.posicion_mm], [c.central.fwhm_mm], "D", ms=7, mfc="none", mec=color, mew=1.6, gid=f"barrido:central:{capa}", label=una_vez("central", "corte central, banda 0"))
            e = c.estadistica
            if e.media_mm is not None:
                ax.axhline(e.media_mm, color=color, ls="--", lw=0.9, gid=f"barrido:media:{capa}", label=una_vez("media", "media, discontinua"))
                ax.axhline(e.mediana_mm, color=color, ls=":", lw=1.4, gid=f"barrido:mediana:{capa}", label=una_vez("mediana", "mediana, punteada"))
        for i, extremo in enumerate(b.zona_mm):
            ax.axvline(extremo, color=COLOR_ZONA, ls="-.", lw=1, gid="barrido:zona", label=_etiqueta(i == 0, "límites de la zona central"))
        bajo, alto = ax.get_ylim()
        for capa, donde in huecos:
            ax.plot(donde, np.full(len(donde), bajo), "x", color=COLOR_CAPA[capa], ms=6, mew=1.4, clip_on=False, gid=f"barrido:hueco:{capa}", label=_etiqueta(capa == huecos[0][0], "banda que no se pudo medir"))
        ax.set_ylim(bajo, alto)
        ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0)
    return salida


# ----------------------------------------------------------------------------------------------------- la pestaña 5: la cuadratura

def cuadrado_perfecto(geometria):
    """Las cuatro esquinas (UL, UR, DR, DL), en milímetros desde el cruce de diagonales, del cuadrado perfecto con el mismo centro, sin girar y de lado el medio de los cuatro lados medidos."""
    mitad = lado_perfecto_mm(geometria) / 2.0
    return [(-mitad, -mitad), (mitad, -mitad), (mitad, mitad), (-mitad, mitad)]


def recuadro_en_mm(geometria):
    """Las esquinas del recuadro (UL, UR, DR, DL) en milímetros desde el cruce de diagonales, en el marco de la imagen (sin girar): lo marcado tal como está."""
    return [((x - geometria.cruce[0]) * geometria.tam_mm, (y - geometria.cruce[1]) * geometria.tam_mm) for x, y in geometria.esquinas]


def recuadro_ampliado(geometria, factor=FACTOR_DE_AMPLIACION):
    """El recuadro con sus desviaciones frente al cuadrado perfecto AMPLIADAS `factor` veces (perfecto + factor x (marcado − perfecto)), en milímetros desde el cruce: así se ve a escala del dibujo lo que
    a escala real son décimas de grado y menos de un milímetro."""
    perfecto = cuadrado_perfecto(geometria)
    marcado = recuadro_en_mm(geometria)
    return [(px + factor * (mx - px), py + factor * (my - py)) for (px, py), (mx, my) in zip(perfecto, marcado)]


def dibujar_cuadratura(ax, geometria, factor=FACTOR_DE_AMPLIACION):
    """La pestaña 5: el recuadro del campo luminoso junto a un cuadrado perfecto con el mismo centro (el cruce de diagonales), el lado medio de los cuatro y sin girar. Las desviaciones se ven AMPLIADAS `factor`
    veces y rotuladas («desviaciones × 20»): a escala real no se ven. También se dibuja el recuadro tal como se marcó (fino). El ángulo girado frente al 0 del cuadrado perfecto va en el título; la tabla da los números
    sin ampliar. Eje en milímetros desde el cruce de diagonales, con la y hacia abajo como la imagen."""
    perfecto = _cerrado(cuadrado_perfecto(geometria))
    real = _cerrado(recuadro_en_mm(geometria))
    ampliado = _cerrado(recuadro_ampliado(geometria, factor))
    ax.plot([p[0] for p in perfecto], [p[1] for p in perfecto], "-", color=TINTA, lw=1.5, gid="cuadratura:perfecto", label="cuadrado perfecto, mismo centro, lado medio y sin girar")
    ax.plot([p[0] for p in real], [p[1] for p in real], "-", color=COLOR_RECUADRO, lw=0.7, alpha=0.6, gid="cuadratura:real", label="recuadro marcado, a escala real")
    ax.plot([p[0] for p in ampliado], [p[1] for p in ampliado], "-", color=COLOR_RECUADRO, lw=1.8, gid="cuadratura:ampliado", label=f"recuadro marcado, {TEXTO_DEL_FACTOR}")
    for forma, color, estilo, gid in ((perfecto, TINTA, ":", "cuadratura:diagonal_perfecta"), (ampliado, COLOR_RECUADRO, "--", "cuadratura:diagonal_ampliada")):
        ax.plot([forma[0][0], forma[2][0]], [forma[0][1], forma[2][1]], estilo, color=color, lw=0.8, gid=gid, label="_diagonal")
        ax.plot([forma[1][0], forma[3][0]], [forma[1][1], forma[3][1]], estilo, color=color, lw=0.8, gid=gid, label="_diagonal")
    ax.plot([0.0], [0.0], "x", color=COLOR_CRUCE, ms=10, mew=2, gid="cuadratura:centro", label="cruce de diagonales")
    ax.set_aspect("equal", adjustable="datalim")
    ax.invert_yaxis()
    ax.grid(color=COLOR_REJILLA)
    ax.set_xlabel("x desde el cruce de diagonales [mm]")
    ax.set_ylabel("y desde el cruce de diagonales [mm]")
    ax.set_title(f"Cuadratura del campo luminoso, {TEXTO_DEL_FACTOR}: ángulo girado {numero(geometria.angulo_grados, 3, True)}° frente a 0° del cuadrado perfecto", fontsize=9)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)


# ----------------------------------------------------------------------------------------------------- la película que se abre y la película virgen

def texto_de_la_imagen(formato, bits, forma, dpi, clase, fecha, transparentes, resolucion_escaneo):
    """Lo que la ventana dice de la imagen que se abrió, ANTES de analizar: el formato, los bits por canal, el tamaño, la resolución que el archivo declara frente a la del procedimiento (`clase`: lo que devuelve
    `pelicula.clase_resolucion`: la escala es SIEMPRE la del procedimiento y la declarada solo se clasifica), la fecha del escaneo si la trae y cuántos píxeles son transparentes (sin dato)."""
    alto, ancho = forma
    partes = [f"{formato or 'formato desconocido'}, {bits} bits por canal, {ancho} × {alto} px"]
    if clase == "coincide":
        partes.append(f"resolución declarada {dpi:.4g} dpi, igual que la del procedimiento")
    elif clase == "sin_dato":
        partes.append(f"el archivo no declara su resolución: se usa la del procedimiento, {resolucion_escaneo:g} dpi")
    elif clase == "editor":
        partes.append(f"el archivo declara {dpi:.4g} dpi, lo que escribe un editor al guardar un recorte: se usa la del procedimiento, {resolucion_escaneo:g} dpi")
    else:
        partes.append(f"el archivo declara {dpi:.4g} dpi y el procedimiento es de {resolucion_escaneo:g} dpi: sin esa escala no hay milímetros ni medidas")
    if fecha is not None:
        partes.append(f"escaneada el {fecha.isoformat()}")
    if transparentes:
        partes.append(f"{transparentes} píxeles transparentes, que son sin dato")
    return ". ".join(partes) + "."


COLUMNAS_DE_LA_VIRGEN = ("Capa", "Valor [nivel]", "Píxeles", "Dispersión, IQR [nivel]")
COLUMNAS_DE_LAS_PRUEBAS = ("Comprobación", "Resultado", "Cifra y límite")
RESULTADO_EN_PALABRAS = {"ok": "pasa", "aviso": "aviso", "rechazo": "rechazo"}
ORIENTACIONES_DE_LA_VIRGEN = ("misma que la película irradiada", "girada")


def filas_de_la_virgen(referencia):
    """Las filas del valor de la película virgen por capa (R, G, B y el gris, cada una por separado): su nivel (la mediana de la zona medida), los píxeles en que se basa y su dispersión."""
    return [(nombre_de_la_capa(capa), numero(referencia.capas[capa].mediana, 1), str(referencia.capas[capa].n), numero(referencia.capas[capa].iqr, 1)) for capa in (*CAPAS, "gris")]


def filas_de_las_pruebas(referencia):
    """Las filas de las comprobaciones hechas a la película virgen: cada una con su cifra y su límite y su resultado en palabras (pasa, aviso o rechazo)."""
    return [(p.nombre, RESULTADO_EN_PALABRAS.get(p.resultado, p.resultado), p.texto) for p in referencia.pruebas]


def _cuando_se_escaneo(procedencia):
    """«escaneada el <fecha>» si el archivo trae la fecha del escaneo y «sin fecha de escaneo» si no (nunca «escaneada el sin fecha»): la UNICA frase que lo dice, la del cuadro de la virgen y la de la
    fila de auditoría de su guardado."""
    fecha = procedencia.get("fecha_escaneo")
    return f"escaneada el {fecha}" if fecha else "sin fecha de escaneo"


def detalle_de_la_referencia_virgen(procedencia):
    """El detalle de la fila de auditoría de «Guardar como referencia»: el archivo, el formato, los bits, cuándo se escaneó (o que el archivo no trae la fecha) y la orientación declarada.
    `procedencia`: la de la `ReferenciaVirgen` (un diccionario)."""
    return (f"referencia de la película virgen «{procedencia.get('archivo')}»; {procedencia.get('formato')}; {procedencia.get('bits')} bits; {_cuando_se_escaneo(procedencia)}; "
            f"orientación {procedencia.get('orientacion_declarada')}")


def texto_de_la_procedencia(referencia):
    """De dónde salió el escaneo de la virgen: archivo, formato, bits, resolución, fecha del escaneo, huella y fecha de cálculo, y la orientación que el físico declaró (no se mide)."""
    pr = referencia.procedencia
    partes = [f"Archivo «{pr.get('archivo') or 'sin nombre'}»", f"formato {pr.get('formato') or 'desconocido'}", f"{pr.get('bits') or '?'} bits por canal"]
    if pr.get("dpi_declarado"):
        partes.append(f"{pr['dpi_declarado']:g} dpi declarados")
    partes.append(_cuando_se_escaneo(pr))
    partes.append(f"huella {str(pr.get('sha256') or '')[:8]}")
    partes.append(f"medida el {pr.get('fecha_calculo')}")
    if pr.get("orientacion_declarada"):
        partes.append(f"orientación declarada: {pr['orientacion_declarada']}")
    return ", ".join(partes) + "."


def dibujar_zona_de_la_virgen(ax, referencia):
    """La caja de la zona medida de la película virgen (`region["caja"]`, en píxeles de su escaneo; x1 e y1 exclusivos) sobre su imagen."""
    region = referencia.region
    if not region or not region.get("caja"):
        return
    x0, y0, x1, y1 = region["caja"]
    caja = _cerrado(_rectangulo(x0 - 0.5, x1 - 0.5, y0 - 0.5, y1 - 0.5))
    ax.plot([p[0] for p in caja], [p[1] for p in caja], "-", color=COLOR_PISO, lw=1.5, gid="virgen:zona", label="zona medida de la película virgen")
