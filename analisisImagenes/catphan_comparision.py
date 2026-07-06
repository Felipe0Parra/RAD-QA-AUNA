""" 
En este modulo, se guardan algunas imagenes que son las referencias para el corte a seleccionar
es decir, se guardan las imagenes "base" y se señaliza el corte para cada análisis
Procedimiento:
Leer imagen referencia
Leer DICOM
Normalizar las imagenes DICOM
Convertir a RGB
Comparar con algún algoritmo de ML o alguno más simple
Crear una lista de porcentaje de similitud entre cada imagen
Obtener lista con posiciones con porcentaje más alto
Señalar al usuario
"""
from pylinac.core import io
import inspect

from pylinac.core.io import get_url
from pylinac import CatPhan504
import pylinac

# Ver el directorio de caché de pylinac
print(pylinac.__file__)  # te dice dónde está instalado pylinac
print(inspect.getsource(io.retrieve_demo_file))

print(CatPhan504._demo_url)  # te muestra la URL del zip