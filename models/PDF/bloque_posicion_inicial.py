"""B.6 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, DA-83/DA-85, decisión de Opus `borradores/B6/decision_figura_pdf_Opus.md`): el bloque de la posición inicial de la fuente de braquiterapia que
imprimen los DOS PDF (el diario, debajo de R6, y el mensual, una sección propia tras «Condiciones de medición»): la capa que guardó el registro, sus medidas estadísticas guardadas y su perfil.

Tres capas, cada una en su sitio: el SERVICIO (`services/posicion_inicial_braqui.py`) arma el contenido (datos, sin dibujar) y reconstruye el análisis; los DIBUJOS por eje viven en
`analisisImagenes/dibujo_posicion_inicial.py` (mudados de la página con su cuerpo sin cambiar: una sola definición de qué muestra un perfil); y ESTE módulo compone la figura con la disposición propia
del PDF y entrega el bloque a los dos generadores. No importa el motor (el análisis ya viene reconstruido), ni Qt, ni `pyplot`, y nunca llama `matplotlib.use`: una figura de `matplotlib.figure.Figure`
con `FigureCanvasAgg` no toca el backend del proceso (el cargador diferido de la aplicación importa `pyplot`, y los dos gráficos del mensual de braquiterapia llaman `matplotlib.use('Agg')`: no se
agrava).

La figura no es la de la pantalla: las funciones con su disposición de pantalla, a 420 x 380 pt, dan una figura rota (la leyenda de la ventana se recorta, la del perfil tapa la curva, letra de 10 pt;
medido por Opus). Aquí `componer_figura` llama a los TRES dibujos de un perfil (la ventana con la línea, los bordes y las bandas del tránsito; el perfil de la cuerda dibujada con el tope, el umbral, la
meseta y el eje en mm; el barrido de filas) con `leyenda=False`, pone cada leyenda FUERA de su eje y dentro de la figura, con letra de 5.5 a 7 pt, y el pie de parámetros fijos re-partido al ancho de la
figura. La cuerda dibujada es la del GRIS (`fila_representativa(resultado, "gris")`, la misma con que la pestaña de capas dibuja R, G y B). Tamaño de 420 x 400 pt, PNG a 200 dpi (el texto de 5.5 pt
mide 15 px). La figura es siempre de la capa guardada y se construye al imprimir: las gráficas no se guardan (D8).

Un fallo al dibujar no tumba el PDF: sale con lo guardado, la fila «Perfil» lo dice sin texto técnico y el detalle va a `error_log.txt`."""
import io
import textwrap

import pandas as pd
from reportlab.platypus import Image

from analisisImagenes.dibujo_posicion_inicial import (COLOR_CAPA, NOMBRE_DE_PERFIL, TINTA, TINTA_SUAVE, _numero, dibujar_barrido_de_filas, dibujar_perfil, dibujar_ventana,
                                                      fila_representativa, texto_de_parametros)
from analisisImagenes.pelicula import ADJETIVO_DE_LA_CAPA, CAPAS
from services import posicion_inicial_braqui as svc
from services.registro_errores import registrar_error

TITULO = "Posición inicial de la fuente"
ANCHO_FIGURA_PT = 420
ALTO_FIGURA_PT = 400
DPI_FIGURA = 200
CLAVE_SECCION = "posicion_inicial"                  # la sección del mensual (la tabla de las medidas)
CLAVE_GRAFICO = "grafico_posicion_inicial"          # la sección del gráfico del mensual (la figura)

ALTOS_DE_LOS_EJES = (1.35, 1.0, 0.9)               # ventana, perfil, barrido: la ventana (la imagen es lo que se mira) algo más alta
LETRA_DE_LA_FIGURA = {"font.size": 6, "axes.labelsize": 6, "axes.titlesize": 6.5, "xtick.labelsize": 5.5, "ytick.labelsize": 5.5, "legend.fontsize": 5.5}
CARACTERES_POR_RENGLON_DE_LA_LEYENDA = 42
CARACTERES_POR_RENGLON_DEL_PIE = 135                # a 175 el pie se cortaba por los dos lados (medido por Opus); se mira en la captura
LETRA_DEL_PIE, LETRA_DEL_TITULO = 5, 7


def _leyenda_fuera(eje):
    """La leyenda de un eje, FUERA de él (a su derecha) y dentro de la figura: dentro tapa la curva o se recorta (la disposición `constrained` le deja el sitio)."""
    manejadores, etiquetas = eje.get_legend_handles_labels()
    if manejadores:
        eje.legend(manejadores, [textwrap.fill(e, CARACTERES_POR_RENGLON_DE_LA_LEYENDA) for e in etiquetas], loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=5.5,
                   borderaxespad=0.0, framealpha=0.9)


def componer_figura(figura, resultado, perfil):
    """Compone sobre una `Figure` (de `matplotlib.figure`, con `layout='constrained'`) los tres dibujos del perfil `perfil` (`gris`, `R`, `G` o `B`) de un análisis, con la disposición del PDF:
    ventana (con las bandas del tránsito), perfil de la cuerda dibujada y barrido de filas, cada una con su leyenda fuera de su eje, y el pie de parámetros fijos al ancho de la figura. No guarda
    ni dibuja nada más: `png_del_perfil` la rasteriza. Se prueba sobre una `Figure`."""
    import matplotlib
    with matplotlib.rc_context(LETRA_DE_LA_FIGURA):
        fila = fila_representativa(resultado, "gris")
        ventana, eje_perfil, barrido = figura.subplots(3, 1, height_ratios=ALTOS_DE_LOS_EJES)
        color = COLOR_CAPA.get(perfil, TINTA)
        dibujar_ventana(ventana, resultado, perfil, fila, leyenda=False)
        _leyenda_fuera(ventana)
        dibujar_perfil(eje_perfil, resultado, perfil, fila, color, leyenda=False)
        _leyenda_fuera(eje_perfil)
        dibujar_barrido_de_filas(barrido, resultado, (perfil,))
        pie = " · ".join(texto_de_parametros(resultado).split("\n"))       # las líneas del pie se unen con el mismo separador que sus frases
        figura.supxlabel(textwrap.fill(pie, CARACTERES_POR_RENGLON_DEL_PIE), fontsize=LETRA_DEL_PIE, color=TINTA_SUAVE)
        reportada = " (la reportada)" if perfil in CAPAS else ""
        figura.suptitle(f"{NOMBRE_DE_PERFIL[perfil]}{reportada}: ventana, perfil de la cuerda dibujada y barrido de filas", fontsize=LETRA_DEL_TITULO)


def png_del_perfil(resultado, perfil):
    """Los bytes del PNG (`DPI_FIGURA` dpi, de `ANCHO_FIGURA_PT` x `ALTO_FIGURA_PT` pt) de la figura del perfil `perfil` de un análisis. Sin `pyplot`: `Figure` + `FigureCanvasAgg`, de modo que se
    libera al soltar la referencia y no toca el backend ni las figuras abiertas del proceso."""
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    with matplotlib.rc_context(LETRA_DE_LA_FIGURA):
        figura = Figure(figsize=(ANCHO_FIGURA_PT / 72.0, ALTO_FIGURA_PT / 72.0), layout="constrained")
        FigureCanvasAgg(figura)
        componer_figura(figura, resultado, perfil)
        buffer = io.BytesIO()
        figura.savefig(buffer, format="png", dpi=DPI_FIGURA)
    return buffer.getvalue()


# ----------------------------------------------------------------------------------------------------------------------------------- las filas

SIN_DATO = "sin dato"


def _fila_de_medida(rotulo, px, tam, mm=None):
    """(rótulo, valor) de una medida en píxeles de la imagen (la guardada): con escala, en mm (`mm` si se guardó; si no, px x la escala guardada) y con sus px; sin escala (resolución «otra»), solo
    píxeles; sin dato (una capa que no se midió), «sin dato»."""
    if px is None:
        return f"{rotulo} [{'mm' if tam is not None else 'px'}]", SIN_DATO
    if tam is None:
        return f"{rotulo} [px]", _numero(px, 2)
    return f"{rotulo} [mm]", f"{_numero(px * tam if mm is None else mm, 3)} = {_numero(px, 2)} px"


def filas_del_bloque(bloque):
    """LA definición de las filas de la tabla del bloque, para los dos PDF: [(rótulo, valor)] con la capa reportada, la mediana de las filas (el desfase de la imagen, el guardado), la media, la desviación
    estándar, el número de filas, la resolución del escaneo con que se midió y, solo si el perfil NO se dibuja, «Perfil» con la frase de por qué. Todo es lo GUARDADO: las medidas en mm son los px guardados
    por la escala guardada (sin escala, solo px). La línea (desfase ± U, sentido y veredicto) no es una fila: va aparte en `bloque['linea']`. Las filas dicen el desfase EN LA IMAGEN; la línea, el físico
    (con el lado del tránsito conocido los signos pueden diferir: el recuadro de la pantalla distingue lo mismo)."""
    medidas, tam = bloque["medidas"], bloque["tamano_pixel_mm"]
    capa = bloque["capa"]
    nombre = f"capa {ADJETIVO_DE_LA_CAPA[capa]}" if bloque["capa_guardada"] else "perfil de grises (el registro no guardó la capa reportada)"
    filas = [("Capa reportada", nombre)]
    filas.append(_fila_de_medida("Mediana de las filas (el desfase en la imagen)", medidas["desfase_px"], tam, medidas["desfase_mm"]))
    filas.append(_fila_de_medida("Media de las filas", medidas["media_px"], tam))
    filas.append(_fila_de_medida("Desviación estándar de las filas", medidas["dispersion_px"], tam))
    filas.append(("Número de filas", SIN_DATO if medidas["filas"] is None else str(medidas["filas"])))
    filas.append(("Resolución del escaneo [dpi]", f"{bloque['parametros']['resolucion_escaneo_dpi']:g}"))
    if bloque["sin_perfil"]:
        filas.append(("Perfil", bloque["sin_perfil"]))
    return filas


# ------------------------------------------------------------------------------------------------------------------------------ los dos PDF

def _contenido(bloque):
    """Del bloque del servicio al contenido que imprimen los PDF: `titulo`, `linea`, `filas`, `png` (None si el perfil no se dibuja), `ancho_pt` y `alto_pt`. Si el dibujo falla, el PDF sale con lo
    guardado, la fila «Perfil» lo dice sin texto técnico y el detalle va a `error_log.txt`."""
    png = None
    if bloque["resultado"] is not None:
        try:
            png = png_del_perfil(bloque["resultado"], bloque["capa"])
        except Exception as error:
            registrar_error(f"B.6: no se pudo dibujar el perfil de la posición inicial (capa {bloque['capa']}, cambio de fuente del {bloque['fecha']})", error)
            bloque = {**bloque, "sin_perfil": svc.FRASE_NO_SE_PUDO_DIBUJAR}
    return {"titulo": TITULO, "linea": bloque["linea"], "filas": filas_del_bloque(bloque), "png": png, "ancho_pt": ANCHO_FIGURA_PT, "alto_pt": ALTO_FIGURA_PT}


def bloque_del_diario(fecha):
    """Lo que el PDF diario de braquiterapia imprime como posición inicial en `fecha` (debajo de R6): `{titulo, linea, filas, png, ancho_pt, alto_pt}` o None si no hay prueba aplicable. La regla de vigencia
    y el contenido son del servicio (`bloque_para_pdf`, sin serie: el diario no la guarda). Si la base falla, la excepción sube y el PDF no se genera (regla de PI.8)."""
    bloque = svc.bloque_para_pdf(fecha)
    return None if bloque is None else _contenido(bloque)


def tablas_del_mensual(fecha, serie):
    """Lo que el PDF mensual de braquiterapia imprime como posición inicial para la calibración de `fecha` y `serie` (DD8): `{}` si no hay prueba aplicable o
    `{CLAVE_SECCION: DataFrame de las medidas, CLAVE_GRAFICO: DataFrame con la figura}` (la figura solo si el perfil se dibuja). Las dos tablas llevan la cabecera de sus hermanas (la primera fila, `Campo | Valor`)."""
    bloque = svc.bloque_para_pdf(fecha, serie)
    if bloque is None:
        return {}
    contenido = _contenido(bloque)
    filas = [["Campo", "Valor"], ["Resultado", contenido["linea"]]] + [[rotulo, valor] for rotulo, valor in contenido["filas"]]
    tablas = {CLAVE_SECCION: pd.DataFrame(filas, columns=[TITULO, ""])}
    if contenido["png"] is not None:
        figura = Image(io.BytesIO(contenido["png"]), width=ANCHO_FIGURA_PT, height=ALTO_FIGURA_PT)
        nombre = NOMBRE_DE_PERFIL[bloque["capa"]]
        tablas[CLAVE_GRAFICO] = pd.DataFrame([[figura]], columns=[f"{nombre} (la reportada)" if bloque["capa_guardada"] else nombre])
    return tablas
