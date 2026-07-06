"""
Módulo para carga diferida (lazy loading) de matplotlib.
Evita importar matplotlib hasta que realmente se necesite,
reduciendo significativamente el tiempo de inicio de la aplicación.

Uso:
    from utils.matplotlib_lazy import get_matplotlib_components
    
    # En el método donde necesitas matplotlib
    mpl = get_matplotlib_components()
    Figure = mpl['Figure']
    FigureCanvas = mpl['FigureCanvas']
    NavigationToolbar = mpl['NavigationToolbar']
"""

import importlib
from typing import Dict, Any, Optional


class MatplotlibLoader:
    """
    Singleton para cargar matplotlib bajo demanda con cache.
    """
    
    _instance: Optional['MatplotlibLoader'] = None
    _components_cache: Dict[str, Any] = {}
    _is_loaded: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa el loader sin cargar matplotlib."""
        pass
    
    def get_components(self) -> Dict[str, Any]:
        """
        Obtiene los componentes de matplotlib más comúnmente usados.
        Carga matplotlib solo la primera vez que se llama.
        
        Returns:
            dict: Diccionario con los componentes de matplotlib:
                - 'Figure': matplotlib.figure.Figure
                - 'FigureCanvas': FigureCanvasQTAgg
                - 'NavigationToolbar': NavigationToolbar2QT
                - 'pyplot': matplotlib.pyplot
                - 'numpy': numpy (ya que casi siempre se usa junto a matplotlib)
        """
        if self._is_loaded:
            return self._components_cache
        
        #print("⏳ Cargando matplotlib por primera vez...")
        import time
        start_time = time.time()
        
        try:
            # Importar matplotlib.figure
            from matplotlib.figure import Figure
            
            # Importar backends de Qt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
            
            # Importar pyplot (opcional, solo si se necesita)
            import matplotlib.pyplot as plt
            import matplotlib.gridspec as gridspec
            
            # Importar numpy (casi siempre se usa con matplotlib)
            import numpy as np
            
            # Cachear componentes
            self._components_cache = {
                'Figure': Figure,
                'FigureCanvas': FigureCanvas,
                'NavigationToolbar': NavigationToolbar,
                'pyplot': plt,
                'plt': plt,
                'GridSpec': gridspec.GridSpec,
                'Polygon': plt.Polygon,
                'numpy': np,
                'np': np,
            }
            
            self._is_loaded = True
            
            elapsed = time.time() - start_time
            #print(f"✓ Matplotlib cargado exitosamente en {elapsed:.2f}s")
            
            return self._components_cache
            
        except ImportError as e:
            print(f"✗ Error al importar matplotlib: {e}")
            raise
        except Exception as e:
            print(f"✗ Error inesperado al cargar matplotlib: {e}")
            raise
    
    def get_figure(self):
        """Atajo para obtener solo Figure."""
        return self.get_components()['Figure']
    
    def get_canvas(self):
        """Atajo para obtener solo FigureCanvas."""
        return self.get_components()['FigureCanvas']
    
    def get_toolbar(self):
        """Atajo para obtener solo NavigationToolbar."""
        return self.get_components()['NavigationToolbar']
    
    def get_pyplot(self):
        """Atajo para obtener solo pyplot."""
        return self.get_components()['pyplot']
    
    def get_numpy(self):
        """Atajo para obtener solo numpy."""
        return self.get_components()['numpy']
    
    def is_loaded(self) -> bool:
        """Verifica si matplotlib ya fue cargado."""
        return self._is_loaded


# Instancia global del loader
_loader = MatplotlibLoader()


# Funciones de conveniencia para usar en otros módulos
def get_matplotlib_components() -> Dict[str, Any]:
    """
    Función principal para obtener componentes de matplotlib.
    
    Returns:
        dict: Componentes de matplotlib (Figure, FigureCanvas, etc.)
    
    Example:
        mpl = get_matplotlib_components()
        Figure = mpl['Figure']
        FigureCanvas = mpl['FigureCanvas']
        
        # O desempaquetar directamente:
        mpl = get_matplotlib_components()
        self.figure = mpl['Figure']()
    """
    return _loader.get_components()


def get_figure_class():
    """Obtiene la clase Figure de matplotlib."""
    return _loader.get_figure()


def get_canvas_class():
    """Obtiene la clase FigureCanvas de matplotlib."""
    return _loader.get_canvas()


def get_toolbar_class():
    """Obtiene la clase NavigationToolbar de matplotlib."""
    return _loader.get_toolbar()


def get_pyplot():
    """Obtiene el módulo pyplot de matplotlib."""
    return _loader.get_pyplot()


def get_numpy():
    """Obtiene el módulo numpy."""
    return _loader.get_numpy()


def is_matplotlib_loaded() -> bool:
    """Verifica si matplotlib ya está cargado."""
    return _loader.is_loaded()
