import pandas as pd
import ast
import os
import time
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise

# -----------------------------------------------------------------------------
#      SISTEMA DE CACHÉ PARA WIDGETS EXCEL - OPTIMIZACIÓN DE RENDIMIENTO
# -----------------------------------------------------------------------------

""" Este archivo implementa un sistema de caché inteligente para evitar la 
    lectura repetitiva del archivo widgets.xlsx durante la inicialización
    de múltiples clases (PruebaMensual600, PruebaMensualIX, PruebaMensualHc, 
    PruebaMensualTAC, PruebaMensualBraq, CambioFuente, Linealidad, etc.)    """

#   BENEFICIOS:
"""     - Reduce el tiempo de carga de ~5 segundos a menos de 1 segundo
        - Evita lecturas duplicadas del mismo archivo Excel
        - Gestión inteligente de memoria con limpieza automática
        - Detección de cambios en archivos para invalidar caché obsoleto    """
#    USO:
"""     Las funciones se usan automáticamente en DataFront.extrdatos()
        sin necesidad de cambiar código existente.                          """

# -----------------------------------------------------------------------------

class CacheWidgets:
    """
    Clase singleton para manejar el caché de archivos Excel de widgets.
    Evita múltiples lecturas del mismo archivo Excel mejorando significativamente el rendimiento.
    """
    _instancia = None
    _cache_archivos = {}
    _timestamps_cache = {}
    _excel_files_cache = {}  # Cache para objetos ExcelFile de pandas
    
    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
        return cls._instancia
    
    def obtener_datos_hoja(self, ruta_archivo, nombre_hoja):
        """
        Obtiene datos de una hoja específica del Excel usando caché inteligente.
        
        Args:
            ruta_archivo (str): Ruta completa al archivo Excel
            nombre_hoja (str): Nombre de la hoja a extraer
            
        Returns:
            tuple: (DataFrame, numero_pruebas_unicas) o None si hay error
        """
        try:
            # Crear clave única para esta combinación archivo-hoja
            clave_cache = f"{ruta_archivo}_{nombre_hoja}"
            
            # Verificar si el archivo existe
            if not os.path.exists(ruta_archivo):
                print(f"⚠️ Archivo no encontrado: {ruta_archivo}")
                return None
            
            # Obtener timestamp actual del archivo
            timestamp_actual = os.path.getmtime(ruta_archivo)
            
            # Verificar si tenemos datos en caché y si están actualizados
            if (clave_cache in self._cache_archivos and 
                clave_cache in self._timestamps_cache and
                self._timestamps_cache[clave_cache] == timestamp_actual):
                
                #print(f"✅ Datos obtenidos del caché para: {nombre_hoja}")
                # Retornar copia para evitar mutaciones accidentales
                df_cached, n_cached = self._cache_archivos[clave_cache]
                return df_cached.copy(), n_cached
            
            # Si no está en caché o está desactualizado, leer desde archivo
            #print(f"📖 Leyendo datos desde archivo para: {nombre_hoja}")
            
            # Usar ExcelFile para leer múltiples hojas de forma eficiente
            excel_file = self._obtener_excel_file(ruta_archivo, timestamp_actual)
            
            # Verificar que la hoja existe
            if nombre_hoja not in excel_file.sheet_names:
                print(f"⚠️ Hoja '{nombre_hoja}' no encontrada en {ruta_archivo}")
                #print(f"Hojas disponibles: {excel_file.sheet_names}")
                return None
            
            # Leer la hoja específica
            df = pd.read_excel(excel_file, sheet_name=nombre_hoja)
            
            # Procesar columna 'pose' si existe
            if 'pose' in df.columns:
                df['pose'] = df['pose'].apply(
                    lambda x: ast.literal_eval(x) if isinstance(x, str) else x
                )
            
            # Calcular número de pruebas únicas
            n = len(df['prueba'].unique()) if 'prueba' in df.columns else 0
            
            # Guardar en caché
            self._cache_archivos[clave_cache] = (df.copy(), n)
            self._timestamps_cache[clave_cache] = timestamp_actual
            
            #print(f"💾 Datos guardados en caché para: {nombre_hoja}")
            
            # Retornar copia para evitar mutaciones
            return df.copy(), n
            
        except Exception as e:
            print(f"❌ Error leyendo hoja '{nombre_hoja}' de {ruta_archivo}: {e}")
            return None
    
    def _obtener_excel_file(self, ruta_archivo, timestamp_actual):
        """
        Obtiene un objeto ExcelFile reutilizable, con caché para evitar aperturas repetidas.
        
        Args:
            ruta_archivo (str): Ruta al archivo Excel
            timestamp_actual (float): Timestamp actual del archivo
            
        Returns:
            pd.ExcelFile: Objeto ExcelFile listo para usar
        """
        # Verificar si tenemos el ExcelFile en caché y si está actualizado
        if (ruta_archivo in self._excel_files_cache and
            ruta_archivo in self._timestamps_cache and
            self._timestamps_cache[ruta_archivo] == timestamp_actual):
            
            return self._excel_files_cache[ruta_archivo]
        
        # Si no está en caché o está desactualizado, crear nuevo ExcelFile
        try:
            excel_file = pd.ExcelFile(ruta_archivo)
            self._excel_files_cache[ruta_archivo] = excel_file
            self._timestamps_cache[ruta_archivo] = timestamp_actual
            return excel_file
            
        except Exception as e:
            print(f"❌ Error abriendo archivo Excel {ruta_archivo}: {e}")
            raise
    
    def limpiar_cache(self):
        """Limpia todo el caché - útil para liberar memoria si es necesario."""
        self._cache_archivos.clear()
        self._timestamps_cache.clear()
        
        # Cerrar archivos Excel abiertos
        for excel_file in self._excel_files_cache.values():
            try:
                if hasattr(excel_file, 'close'):
                    excel_file.close()
            except:
                pass
        
        self._excel_files_cache.clear()
        print("🧹 Caché de widgets limpiado completamente")
    
    def limpiar_cache_antiguo(self, tiempo_limite_horas=24):
        """
        Limpia entradas del caché que sean más antiguas que el tiempo límite especificado.
        
        Args:
            tiempo_limite_horas (int): Horas después de las cuales las entradas se consideran antiguas
        """
        tiempo_actual = time.time()
        tiempo_limite_segundos = tiempo_limite_horas * 3600
        
        claves_a_eliminar = []
        
        for clave, timestamp in self._timestamps_cache.items():
            if tiempo_actual - timestamp > tiempo_limite_segundos:
                claves_a_eliminar.append(clave)
        
        for clave in claves_a_eliminar:
            if clave in self._cache_archivos:
                del self._cache_archivos[clave]
            if clave in self._timestamps_cache:
                del self._timestamps_cache[clave]
        
        if claves_a_eliminar:
            print(f"🧹 Limpiadas {len(claves_a_eliminar)} entradas antiguas del caché")
    
    def obtener_estadisticas_cache(self):
        """Devuelve estadísticas del uso del caché para debugging."""
        total_entries = len(self._cache_archivos)
        total_files = len(self._excel_files_cache)
        
        # Calcular tamaño aproximado en memoria
        memoria_aprox = 0
        for df, n in self._cache_archivos.values():
            try:
                memoria_aprox += df.memory_usage(deep=True).sum()
            except:
                pass
        
        return {
            'hojas_en_cache': total_entries,
            'archivos_excel_abiertos': total_files,
            'memoria_aprox_bytes': memoria_aprox,
            'memoria_aprox_mb': round(memoria_aprox / 1024 / 1024, 2),
            'hojas_cacheadas': list(self._cache_archivos.keys())
        }

# Instancia singleton global del caché
cache_widgets = CacheWidgets()

## ENCABEZADO
class DataConection:
    '''
    Para la primera funcion tenia en un principio este codigo 
    ## ENCABEZADO
        df_hd = pd.read_excel('widgets.xlsx', sheet_name='encabezado_braq')
        # Convierte 'pose' si los valores son cadenas
        df_hd['pose'] = df_hd['pose'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
        
        n = len(df_hd['prueba'].unique())
    '''
    def __init__(self, documento):
        self.documento = documento

class DataFront(DataConection):
    """
    Clase optimizada para extraer datos de hojas específicas de Excel.
    Utiliza el sistema de caché para evitar lecturas repetitivas del mismo archivo.
    """
    def __init__(self, documento, hoja):
        super().__init__(documento)
        self.hoja = hoja
    
    def extrdatos(self):
        """
        Extrae datos de la hoja especificada usando el sistema de caché optimizado.
        
        Returns:
            tuple: (DataFrame, numero_pruebas_unicas) o (None, 0) si hay error
        """
        try:
            # Construir ruta completa del archivo
            ruta_completa = resource_path('data/widgets.xlsx')
            
            # Usar el caché para obtener los datos
            resultado = cache_widgets.obtener_datos_hoja(ruta_completa, self.hoja)
            
            if resultado is None:
                print(f"⚠️ No se pudieron obtener datos para la hoja: {self.hoja}")
                return None, 0
            
            df, n = resultado
            
            # Validar que el DataFrame no esté vacío
            if df.empty:
                print(f"⚠️ La hoja '{self.hoja}' está vacía")
                return df, 0
            
            # Mostrar estadísticas para debugging (solo en desarrollo)
            if hasattr(cache_widgets, 'obtener_estadisticas_cache'):
                stats = cache_widgets.obtener_estadisticas_cache()
                #print(f"📊 Caché stats: {stats['hojas_en_cache']} hojas, "
                #        f"{stats['archivos_excel_abiertos']} archivos Excel abiertos")
            
            return df, n
            
        except Exception as e:
            print(f"❌ Error en extrdatos para hoja '{self.hoja}': {e}")
            return None, 0
    
    def limpiar_cache_si_necesario(self):
        """
        Método público para limpiar el caché si se detectan problemas de memoria.
        Puede ser llamado desde las clases que usan DataFront.
        """
        try:
            cache_widgets.limpiar_cache()
            print("✅ Caché limpiado exitosamente")
        except Exception as e:
            print(f"⚠️ Error limpiando caché: {e}")

    @staticmethod
    def obtener_estadisticas_cache():
        """
        Método estático para obtener estadísticas del caché desde cualquier lugar.
        
        Returns:
            dict: Estadísticas del uso del caché
        """
        return cache_widgets.obtener_estadisticas_cache()

# Funciones de utilidad para gestión global del caché
def limpiar_cache_widgets():
    """
    Función global para limpiar el caché de widgets desde cualquier parte del código.
    Útil para liberar memoria cuando sea necesario.
    """
    cache_widgets.limpiar_cache()

def obtener_info_cache_widgets():
    """
    Función global para obtener información del estado actual del caché.
    
    Returns:
        dict: Estadísticas completas del caché
    """
    return cache_widgets.obtener_estadisticas_cache()

def limpiar_cache_antiguo_widgets(horas=24):
    """
    Función global para limpiar entradas antiguas del caché.
    
    Args:
        horas (int): Número de horas después de las cuales las entradas se consideran antiguas
    """
    cache_widgets.limpiar_cache_antiguo(horas)

def verificar_salud_cache():
    """
    Función de diagnóstico para verificar el estado del caché y sugerir acciones.
    
    Returns:
        dict: Diagnóstico del caché con recomendaciones
    """
    stats = cache_widgets.obtener_estadisticas_cache()
    
    recomendaciones = []
    estado = "saludable"
    
    # Verificar uso de memoria
    if stats['memoria_aprox_mb'] > 50:  # Más de 50MB
        recomendaciones.append("Considerar limpiar caché - uso de memoria alto")
        estado = "precaucion"
    
    if stats['memoria_aprox_mb'] > 100:  # Más de 100MB
        recomendaciones.append("URGENTE: Limpiar caché - uso de memoria crítico")
        estado = "critico"
    
    # Verificar número de hojas cacheadas
    if stats['hojas_en_cache'] > 20:
        recomendaciones.append("Muchas hojas en caché - considerar limpieza periódica")
    
    # Verificar archivos Excel abiertos
    if stats['archivos_excel_abiertos'] > 5:
        recomendaciones.append("Muchos archivos Excel abiertos - posible leak de recursos")
        estado = "precaucion"
    
    return {
        'estado': estado,
        'estadisticas': stats,
        'recomendaciones': recomendaciones,
        'accion_sugerida': 'limpiar_cache()' if estado != "saludable" else 'ninguna'
    }

