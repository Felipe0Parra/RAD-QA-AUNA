"""F.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, DA-83 a DA-89): la PELICULA del PDF mensual del Clinac 600 y del Clinac iX con el recuadro del campo luminoso dibujado encima.

El fisico lo pidio el 11-10 (cuarta respuesta): «Quiero que el pdf mensual sí lleve dibujado el recuadro del campo luminoso sobre la imagen. De resto nada más». Revisa para este PDF lo del 09-09 (nada dibujado
sobre la pelicula) y conserva su razon -la pelicula es evidencia-: el recuadro va como un TRAZO VECTORIAL encima de la imagen y los pixeles de la imagen no se tocan (la pelicula se extrae del PDF identica a la
guardada: un JPEG con sus bytes, un PNG o un TIFF como el mapa de Pillow en 8 bits).

`PeliculaConRecuadro` es una subclase de `reportlab.platypus.Image`: el generador del PDF la deja pasar intacta por el bucle de celdas (solo convierte en texto lo que no es `Paragraph` ni `Image`). Dibuja la
imagen (`super().draw()`) y despues traza UN camino cerrado de cuatro lados con `stroke=1, fill=0`, de `GROSOR_DEL_RECUADRO_PT` y del color con que la pestana 1 de la ventana del analisis (E.1) dibuja el recuadro
-importado de su modulo de dibujo, no copiado-, y nada mas: sin diagonales, cruce, reticulo, bandas ni rotulos. Un trazo grueso taparia el borde de la radiacion junto a la luz: 0.5 pt.

`punto_a_pdf` es la UNICA conversion de un punto de la imagen a la pagina: el centro del pixel esta en el entero (la convencion de matplotlib, la de la ventana: el pixel (0, 0) tiene su centro a medio pixel
de la esquina) y el eje y esta invertido (en la imagen crece hacia abajo; en el PDF, hacia arriba). Medido en el generador real con seis peliculas: los vertices dibujados quedan a 0.0003 a 0.0011 px de
`recuadro_luminoso` sobre los puntos guardados.

La imagen se encaja en `ANCHO_MAXIMO_PT` x `ALTO_MAXIMO_PT` conservando su proporcion: una fila de mas de 429 pt tumba el PDF ENTERO (`LayoutError`), con 405 pt o mas el titulo queda solo al pie de una pagina
y la tabla de una columna del generador mide 396 pt (una imagen de 396 toca la rejilla y una de 432 la desborda; medido). El tamano en pixeles se lee con Pillow SIN decodificar la imagen y sin leer la resolucion
declarada. Sin motor, sin Qt y sin `pyplot`."""
import io

from PIL import Image as ImagenPillow
from reportlab.lib.colors import HexColor
from reportlab.platypus import Image

from analisisImagenes.dibujo_placa_mensual import COLOR_RECUADRO

ANCHO_MAXIMO_PT = 384.0
ALTO_MAXIMO_PT = 360.0
GROSOR_DEL_RECUADRO_PT = 0.5
COLOR_DEL_RECUADRO = HexColor(COLOR_RECUADRO)


def tamano_en_el_pdf(ancho_px, alto_px):
    """(ancho, alto) en puntos de una imagen de `ancho_px` x `alto_px` encajada en `ANCHO_MAXIMO_PT` x `ALTO_MAXIMO_PT` conservando su proporcion, lo mas grande que cabe."""
    escala = min(ANCHO_MAXIMO_PT / ancho_px, ALTO_MAXIMO_PT / alto_px)
    return ancho_px * escala, alto_px * escala


def punto_a_pdf(x, y, ancho_px, alto_px, ancho_pt, alto_pt):
    """(u, v) en puntos, en el marco local de la imagen dibujada (origen en su esquina inferior izquierda), del punto (x, y) en pixeles de la imagen (origen en su esquina superior izquierda, y hacia abajo).
    La UNICA conversion: el centro del pixel esta en el entero (u = (x + 0.5) * ancho_pt / ancho_px) y el eje y se invierte (v = alto_pt - (y + 0.5) * alto_pt / alto_px)."""
    return (x + 0.5) * ancho_pt / ancho_px, alto_pt - (y + 0.5) * alto_pt / alto_px


class PeliculaConRecuadro(Image):
    """La pelicula `datos` (los bytes de la imagen tal como se guardo) con, encima, el recuadro de `esquinas_px` (cuatro pares (x, y) en pixeles de la imagen, en el orden en que se unen; vacio = sin recuadro).
    Lanza si `datos` no es una imagen que Pillow o reportlab abran: quien la arma decide que hacer sin ella."""

    def __init__(self, datos, esquinas_px):
        with ImagenPillow.open(io.BytesIO(datos)) as imagen:
            ancho_px, alto_px = imagen.size
        ancho_pt, alto_pt = tamano_en_el_pdf(ancho_px, alto_px)
        super().__init__(io.BytesIO(datos), width=ancho_pt, height=alto_pt)
        self.tamano_px = (ancho_px, alto_px)
        self.esquinas = tuple((float(x), float(y)) for x, y in esquinas_px)

    def draw(self):
        super().draw()
        if not self.esquinas:
            return
        ancho_px, alto_px = self.tamano_px
        dx, dy = getattr(self, "_offs_x", 0), getattr(self, "_offs_y", 0)
        vertices = [punto_a_pdf(x, y, ancho_px, alto_px, self.drawWidth, self.drawHeight) for x, y in self.esquinas]
        lienzo = self.canv
        lienzo.saveState()
        lienzo.setStrokeColor(COLOR_DEL_RECUADRO)
        lienzo.setLineWidth(GROSOR_DEL_RECUADRO_PT)
        camino = lienzo.beginPath()
        camino.moveTo(dx + vertices[0][0], dy + vertices[0][1])
        for u, v in vertices[1:]:
            camino.lineTo(dx + u, dy + v)
        camino.close()
        lienzo.drawPath(camino, stroke=1, fill=0)
        lienzo.restoreState()
