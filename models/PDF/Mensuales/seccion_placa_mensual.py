"""F.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, DA-83 a DA-89): la SECCION «Coincidencia del campo luz-radiación (película)» del PDF mensual del Clinac 600 y del Clinac iX -- el analisis nuevo (D.1,
`analisis_placa_mensual`) de la capa que GUARDO el registro (la elegida en el menu de la ventana, E.1; el PDF nunca lee la constante con que arranca el menu), con una sola capa y sin veredicto.

Es el par de `models/PDF/bloque_posicion_inicial.py` (B.6): el servicio (`services/placa_mensual.py`) lee, vuelve a medir y compara; los DIBUJOS por eje y los textos de las medidas viven en
`analisisImagenes/dibujo_placa_mensual.py` (E.1: una sola definicion de que muestra un perfil y de como se escribe un numero); y ESTE modulo arma las cinco tablas de la seccion con la disposicion propia del
PDF. No calcula un milimetro: no importa el motor mas que para la version del algoritmo, el recuadro del campo luminoso, el barrido y los ejes. Sin Qt, sin `pyplot` y sin `matplotlib.use`.

Las cinco tablas (`CLAVES`, en el orden de `orden_tablas` del PDF), que `reportes_mensuales._secciones_de_la_placa` pone con el analisis nuevo en el lugar de las dos de siempre:
  1. `placa_mensual_valores`: la capa, la base de la medida, el FWHM crossplane e inplane y el desfase de cada lado (radiacion - luz, positivo hacia afuera) -- lo GUARDADO, nunca lo recalculado --, el piso
     (`texto_breve_del_piso`), la referencia TG-142 (sin veredicto: lo evalua el fisico) y, si algo no se imprime, la frase que dice por que. «Estado» solo si la capa no se midio (F1R-7); lo que no se midio
     dice «no medible» (adenda 3, DA-88), nunca «sin dato»;
  2. `placa_mensual_barrido`: por eje, el corte central, la media, la mediana y la desviacion del FWHM del barrido y cuantas bandas se midieron, de ESA capa (las filas de la ventana, `filas_de_los_barridos`);
  3. `placa_mensual_perfiles`: los perfiles crossplane e inplane de ESA capa, apilados, con todo lo que se uso para medirlos (`dibujar_perfil` de E.1, el mismo de la ventana);
  4. `placa_mensual_pelicula`: la pelicula tal como se guardo con el recuadro del campo luminoso encima (`pelicula_con_recuadro.py`) y una linea que dice que es o por que no hay recuadro;
  5. `placa_mensual_parametros`: los parametros fijos con que se midio, como texto (el pie de la ventana; dentro de la figura no se lee: son mas de 1500 caracteres).
Las tablas 2, 3 y 5 se reconstruyen -las gráficas y las medidas estadisticas no se guardan (DA-84)- volviendo a medir la pelicula guardada con sus puntos, sus parametros y su piso guardados, y SOLO si la
version del algoritmo guardada es la de hoy y volver a medir da exactamente lo guardado (F1R-2, el criterio de B.6). Si no, el PDF trae los valores guardados, dice por que no trae lo demas y deja el detalle
en `error_log.txt`. La pelicula y su recuadro salen igual: son de los puntos guardados, no del motor.

Una parte que falla (volver a medir, el barrido, la figura, la pelicula que reportlab no abre) NO tumba el PDF (F1R-9): sale lo guardado, una frase sin texto tecnico y el detalle a `error_log.txt`. En
cambio si `svc.leer` falla (la base) la excepcion sube y el reporte no sale (regla de PI.8): quien llama lo lee antes. Las celdas son SOLO texto (un `Paragraph` propio, de la letra del cuerpo de las tablas,
para el texto largo) o una `Image`: una `Table` anidada u otro `Flowable` sale impreso como texto en el generador (medido)."""
import io
import textwrap
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph

from analisisImagenes import placa_mensual as motor
from analisisImagenes.dibujo_placa_mensual import base_de, dibujar_perfil, filas_de_los_barridos, nombre_de_la_capa, numero, texto_de_parametros
from analisisImagenes.pelicula import ADJETIVO_DE_LA_CAPA, texto_breve_del_piso
from models.PDF.Mensuales.pelicula_con_recuadro import PeliculaConRecuadro
from services import placa_mensual as svc
from services.medidas_placa_mensual import MEDIDAS_GUARDADAS
from services.registro_errores import registrar_error

CLAVES = ("placa_mensual_valores", "placa_mensual_barrido", "placa_mensual_perfiles", "placa_mensual_pelicula", "placa_mensual_parametros")

TITULO = "Coincidencia del campo luz-radiación (película)"
REFERENCIA_TG142 = "TG-142: 2 mm o 1 % por lado; lo evalúa el físico"
LEYENDA_DEL_RECUADRO = "Recuadro: el campo luminoso, entre las cuatro esquinas marcadas en la película"
TITULO_DE_LA_PELICULA = "La película, tal como se guardó"
TITULO_DE_LOS_PARAMETROS = "Parámetros fijos del análisis guardado"
# DA-89 (23-10): el analisis viejo se desconecto del PDF. Un control con franjas del analisis viejo y sin el analisis nuevo dice esta linea en lugar de la tabla vieja (el texto, lectura de Opus, vetable: F1-D-DA89).
LINEA_SIN_ANALISIS_NUEVO = "Análisis de la película: pendiente con la herramienta actual (el anterior quedó retirado)"

# Cada medida guardada de `MEDIDAS_GUARDADAS` (menos el estado, que tiene su propia fila) tiene aqui su rotulo, con su unidad entre corchetes: una medida nueva sin rotulo hace que la seccion falle ruidosamente
# en lugar de imprimirse sin nombre (una prueba exige un rotulo por nombre y la unidad de la lista).
ROTULOS = {
    "fwhm_crossplane_mm": "FWHM crossplane [mm]",
    "fwhm_inplane_mm": "FWHM inplane [mm]",
    "desfase_izquierdo_mm": "Desfase del lado izquierdo [mm]",
    "desfase_derecho_mm": "Desfase del lado derecho [mm]",
    "desfase_superior_mm": "Desfase del lado superior [mm]",
    "desfase_inferior_mm": "Desfase del lado inferior [mm]"}
CONVENCION_DEL_DESFASE = "radiación − luz; positivo hacia afuera"

_SIN_LO_DEMAS = "Las medidas estadísticas, los perfiles y los parámetros fijos no se imprimen: "
FRASE_OTRA_VERSION = _SIN_LO_DEMAS + "el análisis se guardó con la versión {guardada} del algoritmo y la de hoy es {hoy}."
FRASE_NO_COINCIDE = _SIN_LO_DEMAS + "al volver a medir la película guardada no salen los valores guardados."
FRASE_NO_SE_PUDO_VOLVER_A_MEDIR = _SIN_LO_DEMAS + "la película guardada no se pudo volver a medir."
FRASE_NO_SE_PUDO_EL_BARRIDO = "Las medidas estadísticas del barrido no se pudieron calcular."
FRASE_NO_SE_PUDIERON_DIBUJAR = "Los perfiles no se imprimen: no se pudieron dibujar."
FRASE_NO_SE_PUDO_EL_PIE = "Los parámetros fijos no se imprimen: no se pudieron escribir."
FRASE_SIN_PELICULA = "La película guardada no se pudo incluir en el PDF."

ANCHO_FIGURA_PT = 384
ALTO_FIGURA_PT = 340
DPI_FIGURA = 200
LETRA_DE_LA_FIGURA = {"font.size": 6, "axes.titlesize": 6.5, "axes.labelsize": 6, "xtick.labelsize": 5.5, "ytick.labelsize": 5.5, "legend.fontsize": 5.5}
CARACTERES_POR_RENGLON_DE_LA_LEYENDA = 40
LETRA_DE_LA_LEYENDA = 5
COLUMNAS_DE_LA_LEYENDA = 3


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- volver a medir lo guardado

def reconstruir(registro):
    """`(ResultadoPlacaMensual | None, frase | None)`: el analisis vuelto a medir con lo guardado, o `None` y la frase que dice por que no se imprime lo demas. Tres razones, en este orden: la version del algoritmo
    guardada no es la de hoy (`svc.recalcular` NO la compara: vuelve a medir con el motor de hoy, asi que la compara quien reconstruye, ANTES de medir), volver a medir falla (cualquier excepcion: el PDF no
    se cae) o volver a medir no da lo guardado (`svc.diferencias` no esta vacia, F1R-2). En las dos ultimas el detalle va a `error_log.txt`."""
    if registro["version"] != motor.VERSION_ALGORITMO:
        return None, FRASE_OTRA_VERSION.format(guardada=registro["version"], hoy=motor.VERSION_ALGORITMO)
    contexto = f"F.1: PDF mensual del control {registro.get('ref')}, capa {registro.get('capa')}"
    try:
        resultado = svc.recalcular(registro)
        diferencias = svc.diferencias(registro, resultado)
    except Exception as error:
        registrar_error(f"{contexto}: no se pudo volver a medir la película guardada; el PDF sale con lo guardado", error)
        return None, FRASE_NO_SE_PUDO_VOLVER_A_MEDIR
    if diferencias:
        registrar_error(f"{contexto}: al volver a medir la película guardada no salen los valores guardados; el PDF sale con lo guardado, sin medidas estadísticas, perfiles ni parámetros",
                        detalle="\n".join(diferencias))
        return None, FRASE_NO_COINCIDE
    return resultado, None


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- la figura de los perfiles

def componer_figura(figura, resultado, capa):
    """Compone sobre una `Figure` (de `matplotlib.figure`, con `layout='constrained'`) los DOS perfiles de la capa `capa` de un analisis, apilados -crossplane arriba, inplane debajo-, cada uno con
    `dibujar_perfil` de E.1 (el mismo que la ventana: una sola definicion de que muestra un perfil), y UNA leyenda debajo (tres columnas, etiquetas partidas, letra chica). Disposicion propia del PDF: la de la
    ventana, a este tamano, sale rota (titulos encimados y leyenda cortada; medido). No guarda ni rasteriza nada: `png_de_los_perfiles` lo hace. Se prueba sobre una `Figure`."""
    import matplotlib
    with matplotlib.rc_context(LETRA_DE_LA_FIGURA):
        ejes = list(figura.subplots(2, 1))
        for eje_, nombre in zip(ejes, motor.EJES):
            dibujar_perfil(eje_, getattr(resultado.capas[capa], nombre), capa, resultado.parametros, reportada=True)
        mejor = max(ejes, key=lambda a: len(a.get_legend_handles_labels()[0]))
        manejadores, etiquetas = mejor.get_legend_handles_labels()
        if manejadores:
            figura.legend(manejadores, [textwrap.fill(e, CARACTERES_POR_RENGLON_DE_LA_LEYENDA) for e in etiquetas], loc="outside lower center", ncol=COLUMNAS_DE_LA_LEYENDA, fontsize=LETRA_DE_LA_LEYENDA)


def png_de_los_perfiles(resultado, capa):
    """Los bytes del PNG (`DPI_FIGURA` dpi, de `ANCHO_FIGURA_PT` x `ALTO_FIGURA_PT` pt) de los perfiles de la capa `capa` de un analisis. Sin `pyplot`: `Figure` + `FigureCanvasAgg`, de modo que se libera al soltar la
    referencia y no toca el backend ni las figuras abiertas del proceso."""
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    with matplotlib.rc_context(LETRA_DE_LA_FIGURA):
        figura = Figure(figsize=(ANCHO_FIGURA_PT / 72.0, ALTO_FIGURA_PT / 72.0), layout="constrained")
        FigureCanvasAgg(figura)
        componer_figura(figura, resultado, capa)
        buffer = io.BytesIO()
        figura.savefig(buffer, format="png", dpi=DPI_FIGURA)
    return buffer.getvalue()


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- las tablas

def _estilo_del_texto():
    """El estilo de los textos largos de la seccion: a la izquierda y de la letra del cuerpo de las tablas del PDF (`CUERPO_TABLA_PT`, la misma de `pdf.py`: ni letra ni estilo nuevos alla)."""
    from models.PDF.pdf import CUERPO_TABLA_PT
    return ParagraphStyle("PlacaMensualTexto", parent=getSampleStyleSheet()["Normal"], fontSize=CUERPO_TABLA_PT, leading=CUERPO_TABLA_PT + 2, alignment=TA_LEFT)


def _parrafo(texto, estilo):
    """Un texto largo en una celda: un `Paragraph` (un string pelado en una `Table` se desborda de su celda) con lo que Paragraph lee como marcado escapado."""
    return Paragraph(escape(str(texto)), estilo)


def _tabla_de_valores(registro, notas, estilo):
    capa = registro["capa"]
    titulo = f"{TITULO}, capa {ADJETIVO_DE_LA_CAPA[capa]}"
    filas = [["Campo", "Valor"], ["Capa reportada", f"capa {ADJETIVO_DE_LA_CAPA[capa]}"], ["Base de la medida", base_de(registro["parametros"])]]
    if registro["estado"] != "ok":
        filas.append(["Estado", _parrafo(registro["estado"], estilo)])
    for medida in MEDIDAS_GUARDADAS:
        if medida.nombre == "estado":
            continue
        if medida.nombre.startswith("desfase") and not any(f[0] == "Desfase de cada lado" for f in filas):
            filas.append(["Desfase de cada lado", CONVENCION_DEL_DESFASE])
        filas.append([ROTULOS[medida.nombre], numero(registro[medida.nombre], 3, medida.nombre.startswith("desfase"))])
    filas.append(["Piso", _parrafo(texto_breve_del_piso(registro["piso"], capa), estilo)])
    filas.append(["Referencia", _parrafo(REFERENCIA_TG142, estilo)])
    filas += [["Nota", _parrafo(nota, estilo)] for nota in notas]
    return pd.DataFrame(filas, columns=[titulo, ""])


def _tabla_del_barrido(resultado, capa):
    """Una fila por eje de la capa, de las filas de la ventana (`filas_de_los_barridos`: una sola manera de escribir un numero): (capa, eje, estado, bandas, bandas medidas, media, mediana, desviacion, corte central, ...)."""
    propias = [f for f in filas_de_los_barridos(motor.barrido(resultado)) if f[0] == nombre_de_la_capa(capa)]
    filas = [["Eje", "Corte central [mm]", "Media [mm]", "Mediana [mm]", "Desviación [mm]", "Bandas medidas"]]
    filas += [[f[1], f[8], f[5], f[6], f[7], f"{f[4]} de {f[3]}"] for f in propias]
    return pd.DataFrame(filas, columns=[f"Medidas estadísticas del barrido, capa {ADJETIVO_DE_LA_CAPA[capa]}"] + [""] * 5)


def _tabla_de_los_perfiles(resultado, capa):
    figura = Image(io.BytesIO(png_de_los_perfiles(resultado, capa)), width=ANCHO_FIGURA_PT, height=ALTO_FIGURA_PT)
    return pd.DataFrame([[figura]], columns=[f"Perfiles de la capa {ADJETIVO_DE_LA_CAPA[capa]}"])


def _tabla_de_los_parametros(registro, estilo):
    texto = "<br/>".join(escape(linea) for linea in texto_de_parametros(registro["parametros"]).split("\n"))
    return pd.DataFrame([[Paragraph(texto, estilo)]], columns=[TITULO_DE_LOS_PARAMETROS])


def _tabla_de_la_pelicula(registro, estilo):
    """La pelicula guardada con su recuadro y la linea que dice que es. El recuadro sale de los PUNTOS guardados (`recuadro_luminoso`, la misma funcion que la ventana), no de volver a medir: sale tambien con otra
    version del algoritmo. Si los puntos no forman el campo, la pelicula sale sin recuadro y la linea dice por que. Lanza si la imagen guardada no es una imagen que reportlab abra y decodifique (una cabecera ilegible o un archivo cortado)."""
    try:
        recuadro = motor.recuadro_luminoso(registro["puntos"])
        esquinas, leyenda = (recuadro.esquinas, LEYENDA_DEL_RECUADRO) if recuadro.ok else ((), f"Sin recuadro: {recuadro.estado}")
    except Exception as error:
        registrar_error(f"F.1: PDF mensual del control {registro.get('ref')}: los puntos guardados no se pudieron leer; la película sale sin recuadro", error)
        esquinas, leyenda = (), "Sin recuadro: los puntos guardados no se pudieron leer"
    ImageReader(io.BytesIO(registro["imagen"])).getRGBData()                   # reportlab la DECODIFICA antes de armar la tabla (lo que hace `drawImage`): si no puede, falla AQUI y no a mitad del PDF
    pelicula = PeliculaConRecuadro(registro["imagen"], esquinas)
    return pd.DataFrame([[pelicula], [_parrafo(leyenda, estilo)]], columns=[TITULO_DE_LA_PELICULA])


def _intentar(registro, que, hacer):
    """`(tabla | None, fallo)`: `hacer()` y, si lanza lo que sea, `(None, True)` con el detalle en `error_log.txt` -- la seccion sale sin esa parte y el PDF no se cae (F1R-9)."""
    try:
        return hacer(), False
    except Exception as error:
        registrar_error(f"F.1: PDF mensual del control {registro.get('ref')}, capa {registro.get('capa')}: no se pudo armar {que}; el PDF sale con lo guardado", error)
        return None, True


def tablas_de_la_seccion(registro):
    """`{clave: DataFrame}` de la seccion del analisis nuevo `registro` (lo que devuelve `svc.leer`), en el orden de `CLAVES` y solo con las partes que se pudieron armar: la de los valores va siempre (lo
    GUARDADO, de la capa guardada); el barrido, los perfiles y los parametros solo si se reconstruyo el analisis (`reconstruir`) y se pudieron armar; la pelicula siempre que la imagen guardada se pueda
    incluir. Cada parte que no sale deja su frase en la tabla de los valores. Las celdas son texto, un `Paragraph` o una `Image`; las tablas son DataFrames de la forma que lee el generador de `pdf.py`:
    el titulo es el encabezado de la columna y la primera fila de las tablas de texto es su cabecera."""
    capa = registro["capa"]
    estilo = _estilo_del_texto()
    resultado, frase = reconstruir(registro)
    notas = [frase] if frase else []
    barrido = perfiles = parametros = None
    if resultado is not None:
        barrido, fallo = _intentar(registro, "las medidas estadísticas del barrido", lambda: _tabla_del_barrido(resultado, capa))
        notas += [FRASE_NO_SE_PUDO_EL_BARRIDO] if fallo else []
        perfiles, fallo = _intentar(registro, "la figura de los perfiles", lambda: _tabla_de_los_perfiles(resultado, capa))
        notas += [FRASE_NO_SE_PUDIERON_DIBUJAR] if fallo else []
        parametros, fallo = _intentar(registro, "el pie de parámetros fijos", lambda: _tabla_de_los_parametros(registro, estilo))
        notas += [FRASE_NO_SE_PUDO_EL_PIE] if fallo else []
    pelicula, fallo = _intentar(registro, "la película", lambda: _tabla_de_la_pelicula(registro, estilo))
    notas += [FRASE_SIN_PELICULA] if fallo else []
    tablas = {"placa_mensual_valores": _tabla_de_valores(registro, notas, estilo), "placa_mensual_barrido": barrido, "placa_mensual_perfiles": perfiles,
              "placa_mensual_pelicula": pelicula, "placa_mensual_parametros": parametros}
    return {clave: tabla for clave, tabla in tablas.items() if tabla is not None}
