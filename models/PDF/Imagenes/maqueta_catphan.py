"""Maqueta del PDF del Catphan, mensual y anual: cada prueba empieza su pagina y sus imagenes se dibujan con su forma, al ancho util."""
import io

import numpy as np
from PIL import Image as ImagenPIL
from reportlab.lib.pagesizes import letter
from reportlab.platypus import CondPageBreak, Flowable, Image, KeepTogether, Spacer, Table, TableStyle

MARGENES_PT = (40, 40, 245, 100)  # izquierdo, derecho, superior e inferior de los dos generadores
RELLENO_DEL_MARCO_PT = 6  # el que reportlab deja dentro del marco de cada pagina
ANCHO_UTIL_PT = letter[0] - MARGENES_PT[0] - MARGENES_PT[1] - 2 * RELLENO_DEL_MARCO_PT
ALTO_UTIL_PT = letter[1] - MARGENES_PT[2] - MARGENES_PT[3] - 2 * RELLENO_DEL_MARCO_PT
ALTO_MINIMO_DE_FILA_PT = 150  # por debajo, las dos imagenes van una debajo de la otra
ALTO_MINIMO_JUNTO_A_SUS_RESULTADOS_PT = 180  # 2.5 in, el tamano de hoy: mas chicas no se achican para caber con su tabla
HOLGURA_PT = 1  # margen contra el redondeo de reportlab al ver si la tabla cabe en una pagina
ESPACIO_ENTRE_TABLAS_PT = 0.3 * 72  # el que los generadores ponen despues de cada tabla
RELLENO_DE_CELDA_PT = 12  # el izquierdo mas el derecho de cada celda de reportlab

PRUEBAS = (
    ('espesor', 'imagen_espesor'),
    ('tamano_pixel', 'imagen_tamano_pixel'),
    ('resolucion_contraste', 'imagen_resolucion_contraste'),
    ('resolucion_espacial', 'imagen_resolucion_espacial'),
    ('valores_ct', 'imagen_valores_ct'),
    ('linealidad_ct', 'imagen_linealidad_ct'),
    ('uniformidad', 'imagen_uniformidad'),
)
TABLAS_DE_RESULTADOS = frozenset(resultados for resultados, _ in PRUEBAS)
TABLAS_DE_IMAGENES = frozenset(imagenes for _, imagenes in PRUEBAS)
TABLA_DE_LA_MTF = 'imagen_resolucion_espacial'  # solo su imagen del analisis se recorta a la curva
FRACCION_DEL_CORTE = 0.35  # una columna del corte tiene al menos esta fraccion de pixeles que no son blancos
ANCHO_MINIMO_DEL_CORTE = 0.05  # fraccion del ancho de la figura
COLUMNA_QUE_CUBRE_EL_CORTE = 0.25  # fraccion del ancho: el corte empieza antes de esa columna y acaba despues
FIN_MAXIMO_DEL_CORTE = 0.6  # fraccion del ancho antes de la que acaba el corte
ANCHO_DEL_CORTE_SOBRE_EL_ALTO = 0.3  # el corte es mas ancho que esta fraccion del alto de la figura
GRIS_DEL_CORTE = 128  # gris medio por debajo del cual el bloque es el corte
FRANJA_MAXIMA = 0.05  # la franja blanca empieza a menos de esta fraccion del ancho tras el corte
GRAFICO_MINIMO = 0.3  # el grafico a la derecha ocupa al menos esta fraccion del ancho


def recortar_margen_blanco(imagen):
    """La imagen sin las filas y columnas de su borde que son todas blancas o transparentes; nunca quita un pixel de otro color."""
    rgba = np.asarray(imagen.convert('RGBA'))
    contenido = (rgba[..., 3] > 0) & ~np.all(rgba[..., :3] == 255, axis=-1)
    filas, columnas = np.flatnonzero(contenido.any(axis=1)), np.flatnonzero(contenido.any(axis=0))
    if not filas.size:
        return imagen
    caja = (int(columnas[0]), int(filas[0]), int(columnas[-1]) + 1, int(filas[-1]) + 1)
    return imagen if caja == (0, 0) + imagen.size else imagen.crop(caja)


def panel_de_la_mtf(imagen):
    """La caja (x0, y0, x1, y1) [px] del panel de la MTF de una figura combinada guardada antes (corte oscuro a la izquierda, franja blanca, grafico a la derecha), o None si duda."""
    rgba = np.asarray(imagen.convert('RGBA')).astype(int)
    alto, ancho = rgba.shape[:2]
    contenido = ~np.all(rgba[..., :3] == 255, axis=-1) & (rgba[..., 3] > 0)  # lo mismo que en recortar_margen_blanco
    llenas = list(contenido.mean(axis=0) >= FRACCION_DEL_CORTE) + [False]
    tramos, inicio = [], None
    for x, llena in enumerate(llenas):
        if llena and inicio is None:
            inicio = x
        elif not llena and inicio is not None:
            tramos.append((inicio, x))
            inicio = None
    anchos = [t for t in tramos if t[1] - t[0] >= ANCHO_MINIMO_DEL_CORTE * ancho]  # los ejes del grafico dejan columnas llenas de 1 px: no son un corte
    if len(anchos) != 1:
        return None
    x0, x1 = anchos[0]
    if rgba[:, x0:x1, :3].mean(axis=-1)[contenido[:, x0:x1]].mean() >= GRIS_DEL_CORTE:
        return None
    if not (x0 < COLUMNA_QUE_CUBRE_EL_CORTE * ancho and COLUMNA_QUE_CUBRE_EL_CORTE * ancho < x1 < FIN_MAXIMO_DEL_CORTE * ancho and alto * ANCHO_DEL_CORTE_SOBRE_EL_ALTO < x1 - x0):
        return None
    blancas = np.flatnonzero(~contenido.any(axis=0)[x1:]) + x1
    if not blancas.size or blancas[0] > x1 + FRANJA_MAXIMA * ancho:
        return None
    fin = blancas[0]
    while fin + 1 < ancho and not contenido[:, fin + 1].any():
        fin += 1
    if ancho - fin - 1 < GRAFICO_MINIMO * ancho:
        return None
    return int((x1 + fin + 1) // 2), 0, ancho, alto  # desde la mitad de la franja blanca: el blanco que queda lo quita recortar_margen_blanco


def imagen_preparada(ruta, solo_la_curva=False):
    """Los bytes PNG de la imagen recortada y su tamano en pixeles; con `solo_la_curva`, de una figura combinada guardada antes solo su panel de la MTF, o entera si duda."""
    with ImagenPIL.open(ruta) as original:
        original.load()
        caja = panel_de_la_mtf(original) if solo_la_curva else None  # el PNG temporal del informe ya no trae la marca: se decide por el contenido
        recortada = recortar_margen_blanco(original if caja is None else original.crop(caja))
        salida = io.BytesIO()
        recortada.save(salida, 'PNG')
        return salida.getvalue(), recortada.size


def tamanos_de_fila(formas, ancho=ANCHO_UTIL_PT):
    """Si las imagenes van apiladas y el ancho y alto [pt] de cada una: a la misma altura y llenando el ancho, o una debajo de la otra si quedarian por debajo de 150 pt."""
    proporciones = [w / h for w, h in formas]
    alto = ancho / sum(proporciones)
    if len(formas) > 1 and alto < ALTO_MINIMO_DE_FILA_PT:
        return True, [(ancho, ancho / p) for p in proporciones]
    return False, [(alto * p, alto) for p in proporciones]


def tamanos_con_huecos(formas, columnas, ancho=ANCHO_UTIL_PT):
    """El ancho y alto [pt] de cada columna si falta alguna imagen: cada una en su columna, con su forma y al ancho de la columna; la columna sin imagen, del mismo alto."""
    columna = ancho / columnas
    alto = min((columna * h / w for w, h in formas.values()), default=0)
    return [(alto * formas[c][0] / formas[c][1], alto) if c in formas else (columna, alto) for c in range(columnas)]


def _parte_cabeceras(cabeceras, anchos):
    """Si alguna palabra de las cabeceras es mas ancha que su columna (reportlab la partiria). Recibe las cabeceras originales: al medir una tabla, reportlab reemplaza sus casillas."""
    return any(c.minWidth() > anchos[j] - RELLENO_DE_CELDA_PT for fila in cabeceras for j, c in enumerate(fila) if hasattr(c, 'minWidth'))


def _armar(cabeceras, preparadas, apiladas, medidas, estilo, columnas, huecos=None, anchos_fijos=None):
    datos = iter(d for d, _ in preparadas)
    imagenes = [huecos[c] if huecos and c in huecos else Image(io.BytesIO(next(datos)), width=w, height=h) for c, (w, h) in enumerate(medidas)]
    primera = len(cabeceras)
    if apiladas:
        filas = cabeceras + [[imagen] + [Spacer(0, 0) for _ in range(columnas - 1)] for imagen in imagenes]  # las casillas tapadas no piden alto
        anchos = [max(w for w, _ in medidas) / columnas] * columnas
        extra = [('SPAN', (0, f), (-1, f)) for f in range(primera, len(filas))]
    else:
        filas, anchos, extra = cabeceras + [imagenes], [w for w, _ in medidas], []
    extra += [(lado, (0, primera), (-1, -1), 0) for lado in ('LEFTPADDING', 'RIGHTPADDING', 'TOPPADDING', 'BOTTOMPADDING')]
    if anchos_fijos:
        anchos, extra = anchos_fijos, extra + [('ALIGN', (0, primera), (-1, -1), 'CENTER')]
    tabla = Table(filas, colWidths=anchos)
    tabla.setStyle(TableStyle(list(estilo) + extra))
    return tabla


class TablaDeImagenes(Flowable):
    """La tabla de imagenes de una prueba: comparte la pagina con sus resultados si asi cada imagen mide al menos 180 pt de alto; si no, pasa entera a la siguiente llenando el ancho."""

    def __init__(self, data, estilo, nombre_tabla=None):
        super().__init__()
        self._cabeceras = [list(f) for f in data[:-1]]
        ultima = len(data[-1]) - 1  # la columna de la imagen del analisis
        self._preparadas = [imagen_preparada(r, nombre_tabla == TABLA_DE_LA_MTF and c == ultima) for c, r in enumerate(data[-1]) if isinstance(r, str) and r]
        self._columnas, self._estilo = len(data[-1]), list(estilo)
        self._huecos = {c: r for c, r in enumerate(data[-1]) if not (isinstance(r, str) and r)}  # celdas sin imagen: quedan como vinieron, en su columna
        if self._huecos:
            formas = dict(zip([c for c in range(self._columnas) if c not in self._huecos], [t for _, t in self._preparadas]))
            self._apiladas, self._medidas = False, tamanos_con_huecos(formas, self._columnas)
        else:
            self._apiladas, self._medidas = tamanos_de_fila([t for _, t in self._preparadas])
        self._tabla = self._anchos = None
        pagina = self._que_cabe_en(ALTO_UTIL_PT)
        menor = min((h for _, h in self._medidas if h), default=0)
        junto = self._armada(min(1, ALTO_MINIMO_JUNTO_A_SUS_RESULTADOS_PT / menor)) if menor else pagina  # la mas angosta al compartir pagina
        if pagina.wrap(ANCHO_UTIL_PT, ALTO_UTIL_PT)[1] > ALTO_UTIL_PT or any(_parte_cabeceras(self._cabeceras, t._colWidths) for t in (pagina, junto)):
            self._en_columnas_fijas()  # imagenes tan estrechas que sus columnas partirian las cabeceras

    def _en_columnas_fijas(self):
        """Columnas iguales que no se angostan con las imagenes: cada una centrada en la suya (apiladas, a lo ancho de las dos) y no mas ancha que ella."""
        self._anchos = [ANCHO_UTIL_PT / self._columnas] * self._columnas
        celda = ANCHO_UTIL_PT if self._apiladas else self._anchos[0]
        factor = min([1] + [celda / w for w, _ in self._medidas])
        self._medidas = [(w * factor, h * factor) for w, h in self._medidas]

    def _armada(self, factor):
        medidas = [(w * factor, h * factor) for w, h in self._medidas]
        return _armar(self._cabeceras, self._preparadas, self._apiladas, medidas, self._estilo, self._columnas, self._huecos, self._anchos)

    def _que_cabe_en(self, alto):
        tabla = self._armada(1)
        _, alto_tabla = tabla.wrap(ANCHO_UTIL_PT, ALTO_UTIL_PT)
        alto_imagenes = sum(h for _, h in self._medidas) if self._apiladas else self._medidas[0][1]
        exceso = alto_tabla - alto + HOLGURA_PT
        if exceso <= 0:
            return tabla
        if not alto_imagenes:
            return tabla  # sin imagenes no hay que achicar: si no cabe, pasa entera a la pagina siguiente
        factor = (alto_imagenes - exceso) / alto_imagenes
        if alto < ALTO_UTIL_PT and factor * min(h for _, h in self._medidas) < ALTO_MINIMO_JUNTO_A_SUS_RESULTADOS_PT:
            return self._que_cabe_en(ALTO_UTIL_PT) if alto_tabla > ALTO_UTIL_PT - HOLGURA_PT else tabla
        return self._armada(factor)

    def wrap(self, ancho, alto):
        self._tabla = self._que_cabe_en(min(alto, ALTO_UTIL_PT))
        self.width, self.height = self._tabla.wrap(ancho, alto)
        return self.width, self.height

    def split(self, ancho, alto):
        return []

    def drawOn(self, canvas, x, y, _sW=0):
        self._tabla.drawOn(canvas, x, y, _sW)


def colocar(nombre_tabla, tabla, data=None, estilo=None):
    """Lo que el generador agrega por una tabla del informe del Catphan: un salto de pagina antes de los resultados de cada prueba y sus imagenes con su forma."""
    if nombre_tabla == TABLA_DE_LA_MTF and not isinstance(tabla, TablaDeImagenes):
        return [TablaDeImagenes(data, estilo, nombre_tabla)]  # solo su imagen del analisis se recorta a la curva
    if nombre_tabla in TABLAS_DE_IMAGENES:
        return [tabla if isinstance(tabla, TablaDeImagenes) else TablaDeImagenes(data, estilo)]
    if nombre_tabla in TABLAS_DE_RESULTADOS:
        salto = CondPageBreak(ALTO_UTIL_PT - ESPACIO_ENTRE_TABLAS_PT - HOLGURA_PT)  # pagina nueva salvo que en esta no haya mas que ese espacio
        return [salto, tabla]  # ya empieza pagina: sin KeepTogether, una tabla mas alta que el marco no deja otra en blanco
    return [KeepTogether(tabla)]


class EspacioQueNoPasa(Spacer):
    """El espacio entre dos tablas del Catphan: al pie de una pagina ocupa solo lo que queda y no pasa solo a la siguiente (no deja una pagina en blanco)."""

    def wrap(self, ancho, alto):
        return self.width, max(0, min(self.height, alto))


def espacio_entre_tablas(nombre_tabla):
    """El espacio que sigue a una tabla del informe: el que no pasa de pagina tras una prueba; el de siempre tras las demas."""
    if nombre_tabla in TABLAS_DE_RESULTADOS | TABLAS_DE_IMAGENES:
        return EspacioQueNoPasa(1, ESPACIO_ENTRE_TABLAS_PT)
    return Spacer(1, ESPACIO_ENTRE_TABLAS_PT)


COLUMNA_PRUEBA, COLUMNA_FUENTE = 0, 5  # de la tabla de criterio (Prueba, Metrica, Valor, Criterio, Veredicto, Fuente)
SIN_FUENTE = '---'  # lo que imprime la tabla cuando una regla no trae fuente


def uniones_de_criterio(df_tabla):
    """Las celdas unidas de la tabla de criterio: la fuente de filas seguidas de la misma prueba con la misma fuente se imprime una vez."""
    filas = df_tabla.values.tolist()[1:]  # sin la fila de cabeceras; la fila i va en la fila i + 2 de la tabla (titulo y cabeceras)
    uniones, inicio = [], 0
    for i in range(1, len(filas) + 1):
        igual = i < len(filas) and filas[i][COLUMNA_PRUEBA] == filas[inicio][COLUMNA_PRUEBA] and filas[i][COLUMNA_FUENTE] == filas[inicio][COLUMNA_FUENTE]
        if igual and filas[inicio][COLUMNA_FUENTE] != SIN_FUENTE:
            continue
        if i - inicio > 1:
            uniones.append(('SPAN', (COLUMNA_FUENTE, inicio + 2), (COLUMNA_FUENTE, i + 1)))
        inicio = i
    return uniones
