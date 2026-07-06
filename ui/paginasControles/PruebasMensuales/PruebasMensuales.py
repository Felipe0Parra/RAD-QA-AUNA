# PruebasMensuales.py
from .tac_mensual import PruebaMensualTAC
from .braq_mensual import PruebaMensualBraq
from .ix_mensual import PruebaMensualIX
from .halcyon_mensual import PruebaMensualHc
from .ix_imagenes_mensual import PruebaImagenesIX
from .HC_imagenes_mensual import PruebaImagenesHC

# Exportar las clases para mantener compatibilidad
__all__ = ['PruebaMensualTAC', 'PruebaMensualBraq', 'PruebaMensualIX', 'PruebaMensualHc', 'PruebaImagenesIX', 'PruebaImagenesHC']

