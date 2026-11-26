"""La marca que lleva en su PNG la figura archivada de la resolucion espacial cuando es solo la curva MTF; la otra mitad del par es el corte, la imagen original."""
import io

from PIL import Image

CLAVE_DEL_CONTENIDO = "Contenido"
CURVA_SOLA = "curva MTF de la resolucion espacial"
MARCA_DE_LA_CURVA_SOLA = {CLAVE_DEL_CONTENIDO: CURVA_SOLA}


def es_la_curva_sola(imagen):
    """Si una imagen archivada (bytes PNG, ruta o imagen de PIL) es solo la curva MTF, por su marca; la figura combinada que se guardaba antes no la lleva."""
    if isinstance(imagen, Image.Image):
        return getattr(imagen, "text", {}).get(CLAVE_DEL_CONTENIDO) == CURVA_SOLA
    try:
        with Image.open(io.BytesIO(imagen) if isinstance(imagen, (bytes, bytearray)) else imagen) as abierta:
            return es_la_curva_sola(abierta)
    except (OSError, ValueError, TypeError, AttributeError):
        return False
