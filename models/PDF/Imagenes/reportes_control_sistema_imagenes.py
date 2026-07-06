"""
Módulo para generación de reportes PDF de Control de Calidad del Sistema de Imágenes (CatPhan/TAC)

Este módulo maneja la generación de reportes PDF para los análisis de control de calidad
realizados con el fantoma CatPhan en equipos de TAC (Tomografía Axial Computarizada).

Funcionalidades principales:
- Recuperación de datos desde la base de datos usando las funciones de reconstrucción
- Procesamiento de resultados en tablas formateadas para el PDF
- Generación del reporte PDF completo con múltiples secciones
- Manejo de imágenes BLOB almacenadas en la base de datos

Estructura de datos:
Los resultados se organizan en las siguientes categorías:
    - Espesor (espesor de corte)
    - Tamaño de pixel
    - Resolución de contraste
    - Resolución espacial
    - Valores CT por material
    - Linealidad CT
    - Uniformidad y ruido
"""

from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPixmap
import tempfile
import pandas as pd
from io import BytesIO
from PIL import Image

# Importar funciones de utilidad y generación de PDF
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise
from models.PDF.pdf import generar_reporte_pdf_multitabla_mensual
from models.PDF.PDFWindow import PdfViewer

# Importar funciones de reconstrucción desde catphan_db
from data.ManejoDatos.catphan_TAC.catphan_db import reconstruir_resultados_desde_bd

class ReporteControlSistemaImagenes:
    """
    Clase para generar reportes PDF de controles de calidad del sistema de imágenes (CatPhan/TAC)
    
    Esta clase maneja todo el proceso de generación de reportes:
    1. Consulta de datos desde la base de datos
    2. Reconstrucción de resultados usando las funciones de catphan_db
    3. Procesamiento y formateo de datos en tablas
    4. Generación del PDF final con todas las secciones
    
    Attributes:
        categorias_disponibles (list): Lista de categorías de análisis disponibles
    """
    
    def __init__(self):
        """Inicializa la clase con las categorías de análisis disponibles"""
        self.categorias_disponibles = [
            'espesor',
            'tamano_pixel',
            'resolucion_contraste_rois',
            'resolucion_contraste',
            'resolucion_espacial_regiones',
            'resolucion_espacial',
            'valores_ct',
            'linealidad_ct',
            'regiones_uniformidad',
            'uniformidad'
        ]
    
    def generar_reporte_catphan(self, parent_widget, fecha, equipo, user_id, 
                                tipo_reporte='Control Sistema de Imágenes',
                                ref=None, sistema_imagenes=True):
        """
        Genera el reporte PDF completo de control de calidad CatPhan/TAC
        
        Args:
            parent_widget: Widget padre para mostrar mensajes y el visor de PDF
            fecha (str): Fecha del control en formato 'YYYY-MM-DD'
            equipo (str): Nombre del equipo TAC
            user_id (str): ID del usuario que realiza el reporte
            tipo_reporte (str): Tipo de reporte (por defecto 'Control Sistema de Imágenes')
            ref (int, optional): ID de la sesión si ya se conoce
        
        Returns:
            bool: True si el reporte se generó exitosamente, False en caso contrario
        """
        try:
            # 1. Conectar a la base de datos
            db = parent_widget.opeenDatabase()
            
            # 2. Buscar el ID de sesión si no se proporciona
            if ref is None:
                ref = self._obtener_ref(db, fecha, equipo)
                if not ref:
                    QMessageBox.critical(
                        parent_widget, 
                        "Error", 
                        f"No se encontró control del sistema de imágenes para {equipo} en {fecha}"
                    )
                    db.close()
                    return False
            else:
                print(f"Usando ref proporcionada: {ref}")
        
            # 3. Verificar que existen pruebas CatPhan para esta sesión
            if not self._verificar_pruebas_disponibles(db, ref):
                QMessageBox.warning(
                    parent_widget,
                    "Sin datos",
                    f"No hay análisis CatPhan disponibles para la sesión {ref}"
                )
                db.close()
                return False
            
            # 4. Obtener información general de la sesión
            info_sesion = self._obtener_info_sesion(db, ref)

            datos_tabla_principal = self._obtener_datos_tabla_principal(db, ref)
            
            # 5. Obtener información del usuario (nombre completo y firma)
            usuario_info = self._obtener_info_usuario(db, datos_tabla_principal['user_id'])
            
            # 6. Obtener imágenes BLOB de la base de datos
            imagenes_originales, imagenes_resultados = self._obtener_imagenes_blob(db, ref)
            
            # 7. Reconstruir todos los resultados desde la base de datos
            resultados = reconstruir_resultados_desde_bd(
                ref, 
                categorias=self.categorias_disponibles,
                label=None,  # No necesitamos actualizar labels en el reporte
                canvas=None  # No necesitamos mostrar imágenes en canvas
            )

            print(f"Resultados reconstruidos: {resultados.keys()}")
            
            if not resultados:
                QMessageBox.warning(
                    parent_widget,
                    "Sin resultados",
                    "No se pudieron reconstruir los resultados desde la base de datos"
                )
                db.close()
                return False
            
            # 8. Procesar resultados en tablas para el PDF
            tablas_reporte = self._procesar_resultados_para_reporte(resultados, info_sesion, imagenes_originales, imagenes_resultados)
            
            # 9. Generar el PDF
            pdf_generado = self._generar_mostrar_pdf(
                parent_widget,
                tablas_reporte,
                fecha,
                equipo,
                tipo_reporte,
                usuario_info,
                info_sesion,
                sistema_imagenes=sistema_imagenes
            )
            
            db.close()
            return pdf_generado
            
        except Exception as e:
            QMessageBox.critical(
                parent_widget, 
                "Error", 
                f"Error generando reporte: {str(e)}"
            )
            print(f"Error en generar_reporte_catphan: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _obtener_ref(self, db, fecha, equipo):
        """
        Busca el ID de sesión en la tabla 'controles' para la fecha y equipo dados
        
        Args:
            db: Conexión a la base de datos
            fecha (str): Fecha del control
            equipo (str): Nombre del equipo
        
        Returns:
            int: ID de la sesión o None si no se encuentra
        """
        query = QSqlQuery(db)
        query.prepare("""
            SELECT id FROM controles 
            WHERE fecha = ? AND equipo = ? AND control = 'Mensual'
            ORDER BY id DESC
            LIMIT 1
        """)
        query.addBindValue(fecha)
        query.addBindValue(equipo)
        
        if query.exec() and query.next():
            return query.value(0)
        return None
    
    def _verificar_pruebas_disponibles(self, db, ref):
        """
        Verifica que existan pruebas CatPhan para la sesión dada
        
        Args:
            db: Conexión a la base de datos
            ref (int): ID de la sesión
        
        Returns:
            bool: True si hay pruebas disponibles, False en caso contrario
        """
        query = QSqlQuery(db)
        query.prepare("SELECT COUNT(*) FROM pruebas WHERE id_sesion = ?") # COUNT es para verificar existencia
        query.addBindValue(ref)
        
        if query.exec() and query.next():
            count = query.value(0)
            return count > 0
        return False
    
    # Retorna información general de la sesión (EQUIPOS, USUARIO, FECHA)
    def _obtener_info_sesion(self, db, ref):
        """
        Obtiene información general de la sesión (parámetros de adquisición, etc.)
        
        Args:
            db: Conexión a la base de datos
            ref (int): ID de la sesión
        
        Returns:
            dict: Diccionario con información de la sesión
        """
        query = QSqlQuery(db)
        query.prepare("""
            SELECT c.equipo, c.fecha, c.user_id
            FROM controles c
            WHERE c.id = ?  
            LIMIT 1
        """)
        query.addBindValue(ref)
        
        info = {
            'equipo': 'N/A',
            'fecha': 'N/A',
            'user_id': 'N/A'
        }
        info['db'] = db
        info['ref'] = ref
        if query.exec() and query.next():
            info['equipo'] = query.value(0)
            info['fecha'] = query.value(1)
            info['user_id'] = query.value(2)

        return info
    
    # Retorna información específica de una prueba (kv, ma, espesor de corte, imagen original, imagen análisis)
    def _obtener_info_prueba(self, db, ref, id_tipo):
        """
        Obtiene información específica de una prueba dada su sesión y tipo
        
        Args:
            db: Conexión a la base de datos
            ref (int): ID de la sesión
            id_tipo (int): ID del tipo de prueba
        
        Returns:
            dict: Diccionario con información de la prueba
        """
        query = QSqlQuery(db)
        query.prepare("""
            SELECT * FROM pruebas 
            WHERE id_sesion = ? AND id_tipo = ?
            LIMIT 1
        """)
        query.addBindValue(ref)
        query.addBindValue(id_tipo)
        
        if query.exec() and query.next():
            return {
                'id_prueba': query.value('id_prueba'),
                'id_tipo': query.value('id_tipo'),
                'kv': query.value('kv'),
                'ma': query.value('ma'),
                'espesor_corte': query.value('espesor_corte'),
                'imagen_original': query.value('imagen_path'),
                'imagen_resultado': query.value('imagen_resultado'),
                # Agregar más campos según sea necesario
            }
        return {}
    
    def _obtener_imagenes_blob(self, db, ref):
        """
        Obtiene las imágenes BLOB de la base de datos y las convierte a archivos temporales
        
        Args:
            db: Conexión a la base de datos
            ref (int): ID de la sesión
        
        Returns:
            dict: Diccionario con rutas a archivos temporales de las imágenes por categoría
        """
        imagenes_originales = {}
        imagenes_resultados = {}
        
        # Consultar todas las imágenes resultado de la sesión
        query = QSqlQuery(db)
        query.prepare("""
            SELECT p.id_prueba, p.id_tipo, p.imagen_path, p.imagen_resultado, tp.nombre_prueba
            FROM pruebas p
            JOIN tipos_prueba tp ON p.id_tipo = tp.id_tipo
            WHERE p.id_sesion = ? AND p.imagen_resultado IS NOT NULL
        """)
        query.addBindValue(ref)
        
        if query.exec():
            while query.next():
                id_prueba = query.value(0)
                id_tipo = query.value(1)
                imagen_original_blob = query.value(2)
                imagen_resultado_blob = query.value(3)
                nombre_prueba = query.value(4)

                if imagen_resultado_blob and imagen_original_blob:
                    try:
                        # Convertir BLOB a archivo temporal
                        original_path = self._blob_a_archivo_temporal(imagen_original_blob, nombre_prueba)
                        resultado_path = self._blob_a_archivo_temporal(imagen_resultado_blob, nombre_prueba)
                        if resultado_path:
                            # Mapear nombre de prueba a categoría
                            categoria = self._mapear_nombre_a_categoria(nombre_prueba)
                            imagenes_originales[categoria] = original_path
                            imagenes_resultados[categoria] = resultado_path
                    
                    except Exception as e:
                        print(f"Error procesando imagen de {nombre_prueba}: {e}")

        return imagenes_originales, imagenes_resultados

    def _blob_a_archivo_temporal(self, blob_data, nombre_prueba):
        """
        Convierte datos BLOB a un archivo temporal PNG
        
        Args:
            blob_data (bytes): Datos de imagen en formato BLOB
            nombre_prueba (str): Nombre de la prueba (para el nombre del archivo)
        
        Returns:
            str: Ruta al archivo temporal o None si hay error
        """
        if not blob_data:
            return None
        
        try:
            # Convertir bytes a imagen PIL
            imagen_pil = Image.open(BytesIO(blob_data))
            
            # Crear archivo temporal
            temp_fd, temp_path = tempfile.mkstemp(suffix=".png", prefix=f"{nombre_prueba}_")
            
            # Guardar imagen
            imagen_pil.save(temp_path, "PNG")
            
            return temp_path
            
        except Exception as e:
            print(f"Error convirtiendo BLOB a archivo temporal: {e}")
            return None
    
    def _mapear_nombre_a_categoria(self, nombre_prueba):
        """
        Mapea el nombre de la prueba en la base de datos a la categoría interna
        """
        mapeo = {
            'Espesor de corte': 'espesor',
            'ESPESOR_CORTE': 'espesor',
            'Tamaño de pixel': 'tamano_pixel',
            'TAMAÑO_PIXEL': 'tamano_pixel',
            'Resolución de contraste': 'resolucion_contraste',
            'RESOLUCION_CONTRASTE': 'resolucion_contraste',
            'Resolución espacial': 'resolucion_espacial',
            'RESOLUCION_ESPACIAL': 'resolucion_espacial',
            'Valores CT': 'valores_ct',
            'VALORES_CT': 'valores_ct',
            'Linealidad CT': 'linealidad_ct',
            'LINEALIDAD_CT': 'linealidad_ct',
            'Uniformidad': 'uniformidad',
            'UNIFORMIDAD_RUIDO': 'uniformidad'
        }
        return mapeo.get(nombre_prueba, nombre_prueba.lower().replace(' ', '_'))

    def _obtener_datos_tabla_principal(self, db, ref_id):
        """Obtiene datos de la tabla controles"""
        query = QSqlQuery(db)
        query.prepare("SELECT * FROM controles WHERE id = ?")
        query.addBindValue(ref_id)
        
        if query.exec() and query.next():
            return {
                'equipo': query.value('equipo'),
                'fecha': query.value('fecha'), 
                'user_id': query.value('user_id')
            }
        return {}
    
    def _obtener_info_usuario(self, db, user_id):
        """Obtiene información del usuario incluyendo firma"""
        query = QSqlQuery(db)
        query.prepare("SELECT firma, role FROM users WHERE fullname = ?")
        query.addBindValue(user_id)
        print(f"Buscando información del usuario: {user_id}")
        
        if query.exec() and query.next():
            firma = query.value(0)
            rol = query.value(1)
            
            # Procesar firma si existe
            temp_image_path = None
            if firma:
                pixmap = QPixmap()
                pixmap.loadFromData(firma)
                temp_fd, temp_image_path = tempfile.mkstemp(suffix=".png")
                pixmap.save(temp_image_path, "PNG")
            
            return {
                'usuario': user_id,
                'rol': rol,
                'firma_path': temp_image_path
            }
        print(f"Usuario {user_id} no encontrado en la base de datos.")
        
        return {'usuario': user_id, 'rol': '', 'firma_path': None}
    
    def _procesar_resultados_para_reporte(self, resultados, info_sesion, imagenes_originales, imagenes_resultados):
        """
        Procesa los resultados reconstruidos y los convierte en tablas para el PDF
        
        Args:
            resultados (dict): Diccionario con resultados reconstruidos por categoría
            info_sesion (dict): Información general de la sesión
            imagenes (dict): Diccionario con rutas a archivos temporales de imágenes
        
        Returns:
            dict: Diccionario con DataFrames listos para el PDF
        """
        tablas_reporte = {}

        # Mapeo de categoría a id_tipo (ajusta según tu base de datos)
        mapeo_id_tipo = {
            'espesor'         : 1,
            'tamano_pixel'          : 2,
            'resolucion_contraste'  : 3,
            'resolucion_espacial'   : 4,
            'valores_ct'            : 5,
            'linealidad_ct'         : 6,
            'uniformidad'           : 7
        }

        # Para cada categoría reconstruida
        # Obtener info específica de la prueba
        # Necesitas pasar la conexión y ref, así que pásalos en info_sesion o como argumentos
        db = info_sesion.get('db')
        ref = info_sesion.get('ref')

        # Tabla de espesor
        if 'espesor' in resultados and resultados['espesor']:
            info_prueba = self._obtener_info_prueba(db, ref, mapeo_id_tipo['espesor'])
            tablas_reporte[f'parametros_espesor'] = self._crear_tabla_parametros(info_prueba, "Espesor de corte")
            tablas_reporte['espesor'] = self._crear_tabla_espesor_corte(
                resultados['espesor']
            )
            # Agregar imagen si está disponible
            if 'espesor' in imagenes_originales and 'espesor' in imagenes_resultados:
                tablas_reporte['imagen_espesor'] = self._crear_tabla_imagen(
                    imagenes_originales['espesor'],
                    imagenes_resultados['espesor'], 'Espesor de corte'
                )
        
        # Tabla de tamaño de pixel
        if 'tamano_pixel' in resultados and resultados['tamano_pixel']:
            info_prueba = self._obtener_info_prueba(db, ref, mapeo_id_tipo['tamano_pixel'])
            tablas_reporte[f'parametros_tamano_pixel'] = self._crear_tabla_parametros(info_prueba, "Tamaño de pixel")
            tablas_reporte['tamano_pixel'] = self._crear_tabla_tamano_pixel(
                resultados['tamano_pixel']
            )
            # Agregar imagen si está disponible
            if 'tamano_pixel' in imagenes_originales and 'tamano_pixel' in imagenes_resultados:
                tablas_reporte['imagen_tamano_pixel'] = self._crear_tabla_imagen(
                    imagenes_originales['tamano_pixel'], imagenes_resultados['tamano_pixel'], 'Tamaño de pixel'
                )
        
        # Tabla de resolución de contraste
        if 'resolucion_contraste' in resultados and resultados['resolucion_contraste']:
            info_prueba = self._obtener_info_prueba(db, ref, mapeo_id_tipo['resolucion_contraste'])
            tablas_reporte[f'parametros_resolucion_contraste'] = self._crear_tabla_parametros(info_prueba, "Resolución de contraste")
            tablas_reporte['resolucion_contraste'] = self._crear_tabla_resolucion_contraste(
                resultados['resolucion_contraste']
            )
            # Agregar imagen si está disponible
            if 'resolucion_contraste' in imagenes_originales and 'resolucion_contraste' in imagenes_resultados:
                tablas_reporte['imagen_resolucion_contraste'] = self._crear_tabla_imagen(
                    imagenes_originales['resolucion_contraste'], imagenes_resultados['resolucion_contraste'], 'Resolución de contraste'
                )
        
        # Tabla de resolución espacial
        if 'resolucion_espacial' in resultados and resultados['resolucion_espacial']:
            info_prueba = self._obtener_info_prueba(db, ref, mapeo_id_tipo['resolucion_espacial'])
            tablas_reporte[f'parametros_resolucion_espacial'] = self._crear_tabla_parametros(info_prueba, "Resolución espacial")
            tablas_reporte['resolucion_espacial'] = self._crear_tabla_resolucion_espacial(
                resultados['resolucion_espacial']
            )
            # Agregar imagen si está disponible
            if 'resolucion_espacial' in imagenes_originales and 'resolucion_espacial' in imagenes_resultados:
                tablas_reporte['imagen_resolucion_espacial'] = self._crear_tabla_imagen(
                    imagenes_originales['resolucion_espacial'], imagenes_resultados['resolucion_espacial'], 'Resolución espacial'
                )
        
        # Tabla de valores CT
        if 'valores_ct' in resultados and resultados['valores_ct']:
            info_prueba = self._obtener_info_prueba(db, ref, mapeo_id_tipo['valores_ct'])
            tablas_reporte[f'parametros_valores_ct'] = self._crear_tabla_parametros(info_prueba, "Valores CT")
            tablas_reporte['valores_ct'] = self._crear_tabla_valores_ct(
                resultados['valores_ct']
            )
            # Agregar imagen si está disponible
            if 'valores_ct' in imagenes_originales and 'valores_ct' in imagenes_resultados:
                tablas_reporte['imagen_valores_ct'] = self._crear_tabla_imagen(
                    imagenes_originales['valores_ct'], imagenes_resultados['valores_ct'], 'Valores CT'
                )
        
        # Tabla de linealidad CT
        if 'linealidad_ct' in resultados and resultados['linealidad_ct']:
            info_prueba = self._obtener_info_prueba(db, ref, mapeo_id_tipo['linealidad_ct'])
            tablas_reporte[f'parametros_linealidad_ct'] = self._crear_tabla_parametros(info_prueba, "Linealidad CT")
            tablas_reporte['linealidad_ct'] = self._crear_tabla_linealidad_ct(
                resultados['linealidad_ct']
            )
            # Agregar imagen si está disponible
            if 'linealidad_ct' in imagenes_originales and 'linealidad_ct' in imagenes_resultados:
                tablas_reporte['imagen_linealidad_ct'] = self._crear_tabla_imagen(
                    imagenes_originales['linealidad_ct'], imagenes_resultados['linealidad_ct'], 'Linealidad CT'
                )
        
        # Tabla de uniformidad
        if 'uniformidad' in resultados and resultados['uniformidad']:
            info_prueba = self._obtener_info_prueba(db, ref, mapeo_id_tipo['uniformidad'])
            tablas_reporte[f'parametros_uniformidad'] = self._crear_tabla_parametros(info_prueba, "Uniformidad")
            tablas_reporte['uniformidad'] = self._crear_tabla_uniformidad(
                resultados['uniformidad']
            )
            # Agregar imagen si está disponible
            if 'uniformidad' in imagenes_originales and 'uniformidad' in imagenes_resultados:
                tablas_reporte['imagen_uniformidad'] = self._crear_tabla_imagen(
                    imagenes_originales['uniformidad'], imagenes_resultados['uniformidad'], 'Uniformidad'
                )
        
        return tablas_reporte

    def _crear_tabla_imagen(self, imagen_original, imagen_analisis, titulo):
        """
        Crea una tabla con una imagen para incluir en el PDF
        
        Args:
            ruta_imagen (str): Ruta al archivo temporal de la imagen
            titulo (str): Título descriptivo de la imagen
        
        Returns:
            pd.DataFrame: Tabla con la ruta de la imagen
        """
        tabla = []
        tabla.append([titulo, ""])
        tabla.append([imagen_original, imagen_analisis])  # La función de PDF detectará que es una ruta de imagen

        return pd.DataFrame(tabla, columns=['Imagen original', 'Imagen del análisis'])
    
    def _crear_tabla_parametros(self, info_prueba, categoria):
        """
        Crea tabla con parámetros de adquisición del TAC
        
        Args:
            info_prueba (dict): Información de la prueba
        
        Returns:
            pd.DataFrame: Tabla con parámetros de adquisición
        """
        tabla = []
        tabla.append(['Parámetro', 'Valor'])
        tabla.append(['Voltaje (kV)', f"{info_prueba.get('kv', 'N/A')}"])
        tabla.append(['Corriente (mA)', f"{info_prueba.get('ma', 'N/A')}"])
        tabla.append(['Espesor de corte (mm)', f"{info_prueba.get('espesor_corte', 'N/A')}"])

        return pd.DataFrame(tabla, columns=[f'Parámetros de adquisición {categoria}', ''])

    def _crear_tabla_espesor_corte(self, resultado):
        """
        Crea tabla con resultados de espesor de corte
        
        Args:
            resultado (dict): Resultados de espesor de corte reconstruidos
        
        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        tabla.append(['Métrica', 'Valor'])
        
        espesor_prom = resultado.get('espesor_promedio_mm', 'N/A')
        espesor_teo = resultado.get('espesor_teorico_mm', 'N/A')
        diferencia = resultado.get('diferencia_mm', 'N/A')
        
        # Formatear valores
        if isinstance(espesor_prom, (int, float)):
            espesor_prom_str = f"{espesor_prom:.3f} mm"
        else:
            espesor_prom_str = str(espesor_prom)
        
        if isinstance(espesor_teo, (int, float)):
            espesor_teo_str = f"{espesor_teo:.3f} mm"
        else:
            espesor_teo_str = str(espesor_teo)
        
        if isinstance(diferencia, (int, float)):
            diferencia_str = f"{diferencia:.3f} mm"
        else:
            diferencia_str = str(diferencia)
        
        tabla.append(['Espesor promedio medido', espesor_prom_str])
        tabla.append(['Espesor teórico', espesor_teo_str])
        tabla.append(['Diferencia', diferencia_str])
        
        return pd.DataFrame(tabla, columns=['Espesor de corte', ''])
    
    def _crear_tabla_tamano_pixel(self, resultado):
        """
        Crea tabla con resultados de tamaño de pixel
        
        Args:
            resultado (dict): Resultados de tamaño de pixel reconstruidos
        
        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        tabla.append(['Métrica', 'Valor'])
        
        tam_teorico = resultado.get('tam_px_teorico', 'N/A')
        x_medido = resultado.get('X', 'N/A')
        y_medido = resultado.get('Y', 'N/A')
        dif_x = resultado.get('diferencia_x', 'N/A')
        dif_y = resultado.get('diferencia_y', 'N/A')
        
        # Formatear valores
        if isinstance(tam_teorico, (int, float)):
            tabla.append(['Tamaño teórico', f"{tam_teorico:.3f} mm"])
        else:
            tabla.append(['Tamaño teórico', str(tam_teorico)])
        
        if isinstance(x_medido, (int, float)):
            tabla.append(['X medido', f"{x_medido:.3f} mm"])
        else:
            tabla.append(['X medido', str(x_medido)])
        
        if isinstance(y_medido, (int, float)):
            tabla.append(['Y medido', f"{y_medido:.3f} mm"])
        else:
            tabla.append(['Y medido', str(y_medido)])
        
        if isinstance(dif_x, (int, float)):
            tabla.append(['Diferencia X', f"{dif_x:.3f} mm"])
        else:
            tabla.append(['Diferencia X', str(dif_x)])
        
        if isinstance(dif_y, (int, float)):
            tabla.append(['Diferencia Y', f"{dif_y:.3f} mm"])
        else:
            tabla.append(['Diferencia Y', str(dif_y)])
        
        return pd.DataFrame(tabla, columns=['Tamaño de pixel', ''])
    
    def _crear_tabla_resolucion_contraste(self, resultado):
        """
        Crea tabla con resultados de resolución de contraste
        
        Args:
            resultado (dict): Resultados de resolución de contraste reconstruidos
        
        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        
        # Información del resumen
        resumen = resultado.get('resumen', {})
        
        # Encabezados
        tabla.append(['Diámetro ROI (mm)', 'Visibilidad', 'Pasa Visibilidad'])

        # Datos por ROI
        resultados_roi = resultado.get('resultados_roi', {})
        
        # Ordenar ROIs por diámetro (de mayor a menor)
        rois_ordenados = sorted(
            resultados_roi.items(),
            key=lambda x: int(x[0].replace('mm', '')),
            reverse=True
        )
        
        for diametro_str, roi_data in rois_ordenados:
            diametro = diametro_str.replace('mm', '')
            visibilidad = roi_data.get('visibilidad_lim', 'N/A')
            pasa_vis = '✓' if roi_data.get('pasa_visibilidad_lim', False) else '✗'
            
            # Formatear valores numéricos
            if isinstance(visibilidad, (int, float)):
                vis_str = f"{visibilidad:.2f}"
            else:
                vis_str = str(visibilidad)
            
            tabla.append([diametro, vis_str, pasa_vis])
        
        # Agregar resumen al final
        tabla.append(['--- RESUMEN ---', '---', '---'])
        tabla.append([
            'ROIs visibles',
            str(resumen.get('rois_visibles_visibilidad_lim', 'N/A')),
            '✓' if resumen.get('pasa_test_visibilidad_lim', False) else '✗'
        ])
        tabla.append([
            'Diámetro mínimo visible (mm)',
            str(resumen.get('diametro_minimo_visible', 'N/A')),
            '✓' if resumen.get('diametro_minimo_visible', False) else '✗'
        ])
        
        return pd.DataFrame(tabla, columns=['Resolución de contraste', '', ''])
    
    def _crear_tabla_resolucion_espacial(self, resultado):
        """
        Crea tabla con resultados de resolución espacial
        
        Args:
            resultado (dict): Resultados de resolución espacial reconstruidos
        
        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        
        # Encabezados
        tabla.append(['Región', 'lp/mm', 'Gap size (cm)', 'Picos', 'Valles', 'Estado'])
        
        # Datos por región
        region_results = resultado.get('region_results', {})
        
        # Ordenar regiones por lp/mm
        regiones_ordenadas = sorted(
            region_results.items(),
            key=lambda x: x[1].get('lp/mm', 0) if isinstance(x[1].get('lp/mm'), (int, float)) else 0
        )
        
        for region_nombre, region_data in regiones_ordenadas:
            lp_mm = region_data.get('lp/mm', 'N/A')
            gap_size = region_data.get('gap_size_cm', 'N/A')
            n_peaks = region_data.get('n_peaks_used', 'N/A')
            n_valleys = region_data.get('n_valleys_used', 'N/A')
            status = region_data.get('status', 'N/A')
            
            # Formatear valores numéricos
            if isinstance(lp_mm, (int, float)):
                lp_mm_str = f"{lp_mm:.2f}"
            else:
                lp_mm_str = str(lp_mm)
            
            if isinstance(gap_size, (int, float)):
                gap_str = f"{gap_size:.4f}"
            else:
                gap_str = str(gap_size)
            
            tabla.append([
                region_nombre,
                lp_mm_str,
                gap_str,
                str(n_peaks),
                str(n_valleys),
                status
            ])
        
        # Agregar resumen
        tabla.append(['--- RESUMEN ---', '---', '---', '---', '---', '---'])
        resolucion_limite = resultado.get('resolucion_limite', {})
        mtf_lp_mm = resultado.get('mtf_lp_mm', {})
        
        lp_mm_max = resolucion_limite.get('lp_mm_maximo', 'N/A')
        ultima_region = resolucion_limite.get('ultima_region', 'N/A')
        
        if isinstance(lp_mm_max, (int, float)):
            lp_mm_max_str = f"{lp_mm_max:.2f}"
        else:
            lp_mm_max_str = str(lp_mm_max)
        
        tabla.append(['Resolución máxima', lp_mm_max_str, '---', '---', '---', ultima_region])
        
        # MTF
        mtf_10 = mtf_lp_mm.get('10', 'N/A')
        mtf_50 = mtf_lp_mm.get('50', 'N/A')
        
        if isinstance(mtf_10, (int, float)):
            mtf_10_str = f"{mtf_10:.2f}"
        else:
            mtf_10_str = str(mtf_10)
        
        if isinstance(mtf_50, (int, float)):
            mtf_50_str = f"{mtf_50:.2f}"
        else:
            mtf_50_str = str(mtf_50)
        
        tabla.append(['MTF 10%', mtf_10_str, '---', '---', '---', '---'])
        tabla.append(['MTF 50%', mtf_50_str, '---', '---', '---', '---'])
        
        return pd.DataFrame(tabla, columns=['Resolución espacial', '', '', '', '', ''])
    
    def _crear_tabla_valores_ct(self, resultado):
        """
        Crea tabla con valores CT por material

        Args:
            resultado (list): Lista de resultados de valores CT por material

        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        # Encabezados
        tabla.append(['Material', 'HU promedio', 'HU esperado (min-max)', 'Error absoluto', 'Error relativo (%)'])

        # Filtrar si hay metadata (último elemento con "_metadata")
        resultados_materiales = [r for r in resultado if not isinstance(r, dict) or "_metadata" not in r]

        # Ordenar materiales por HU promedio (de menor a mayor)
        materiales_ordenados = sorted(
            resultados_materiales,
            key=lambda x: x.get('promedio_hu', 0) if isinstance(x.get('promedio_hu'), (int, float)) else 0
        )

        for material_data in materiales_ordenados:
            nombre = material_data.get('material', 'N/A')
            promedio = material_data.get('promedio_hu', 'N/A')
            rango = material_data.get('rango_hu', ['N/A', 'N/A'])
            error_abs = material_data.get('error_abs', 'N/A')
            error_rel = material_data.get('error_rel', 'N/A')

            # Formatear valores
            promedio_str = f"{promedio:.1f}" if isinstance(promedio, (int, float)) else str(promedio)
            if isinstance(rango, (list, tuple)) and len(rango) == 2 and all(isinstance(v, (int, float)) for v in rango):
                rango_str = f"{rango[0]:.1f} a {rango[1]:.1f}"
            else:
                rango_str = "N/A"
            error_abs_str = f"{error_abs:.1f}" if isinstance(error_abs, (int, float)) else str(error_abs)
            error_rel_str = f"{error_rel:.2f}" if isinstance(error_rel, (int, float)) else str(error_rel)

            tabla.append([nombre, promedio_str, rango_str, error_abs_str, error_rel_str])

        return pd.DataFrame(tabla, columns=['Valores CT', '', '', '', ''])
    
    def _crear_tabla_linealidad_ct(self, resultado):
        """
        Crea tabla con resultados de linealidad CT
        
        Args:
            resultado (dict): Resultados de linealidad CT reconstruidos
        
        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        tabla.append(['Métrica', 'Valor'])
        
        pendiente = resultado.get('pendiente', 'N/A')
        intercepto = resultado.get('intercepto', 'N/A')
        r_cuadrado = resultado.get('r_squared', 'N/A')
        escala_contraste = resultado.get('escala_contraste', 'N/A')
        linealidad_ok = resultado.get('linealidad_aceptable', False)
        
        # Formatear valores
        if isinstance(pendiente, (int, float)):
            pendiente_str = f"{pendiente:.6f}"
        else:
            pendiente_str = str(pendiente)
        
        if isinstance(intercepto, (int, float)):
            intercepto_str = f"{intercepto:.3f}"
        else:
            intercepto_str = str(intercepto)
        
        if isinstance(r_cuadrado, (int, float)):
            r2_str = f"{r_cuadrado:.6f}"
        else:
            r2_str = str(r_cuadrado)
        
        if isinstance(escala_contraste, (int, float)):
            escala_str = f"{escala_contraste:.6f}"
        else:
            escala_str = str(escala_contraste)
        
        tabla.append(['Pendiente', pendiente_str])
        tabla.append(['Intercepto', intercepto_str])
        tabla.append(['R² (coef. correlación)', r2_str])
        tabla.append(['Escala de contraste', escala_str])
        tabla.append(['Linealidad aceptable (R²≥0.99)', '✓' if linealidad_ok else '✗'])
        
        return pd.DataFrame(tabla, columns=['Linealidad CT', ''])
    
    def _crear_tabla_uniformidad(self, resultado):
        """
        Crea tabla con resultados de uniformidad
        
        Args:
            resultado (dict): Resultados de uniformidad reconstruidos
        
        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        
        # Información global
        uniformidad_global = resultado.get('Uniformidad', {})
        
        # Encabezados
        tabla.append(['Región', 'HU promedio', 'Desviación estándar'])
        
        # Regiones individuales
        regiones = ['Centro', 'Arriba', 'Derecha', 'Abajo', 'Izquierda']
        
        for region in regiones:
            if region in resultado:
                region_data = resultado[region]
                hu_prom = region_data.get('hu_promedio', 'N/A')
                desv = region_data.get('desviacion', 'N/A')
                
                # Formatear valores
                if isinstance(hu_prom, (int, float)):
                    hu_str = f"{hu_prom:.1f}"
                else:
                    hu_str = str(hu_prom)
                
                if isinstance(desv, (int, float)):
                    desv_str = f"{desv:.2f}"
                else:
                    desv_str = str(desv)
                
                tabla.append([region, hu_str, desv_str])
        
        # Agregar métricas globales
        tabla.append(['--- MÉTRICAS GLOBALES ---', '---', '---'])
        
        max_dif = uniformidad_global.get('max_diferencia', 'N/A')
        desv_global = uniformidad_global.get('desviacion_global', 'N/A')
        ui_max = uniformidad_global.get('uniformity_index_max', 'N/A')
        inu_pct = uniformidad_global.get('integral_non_uniformity_pct', 'N/A')
        
        if isinstance(max_dif, (int, float)):
            max_dif_str = f"{max_dif:.1f} HU"
        else:
            max_dif_str = str(max_dif)
        
        if isinstance(desv_global, (int, float)):
            desv_g_str = f"{desv_global:.2f}"
        else:
            desv_g_str = str(desv_global)
        
        if isinstance(ui_max, (int, float)):
            ui_str = f"{ui_max:.2f}%"
        else:
            ui_str = str(ui_max)
        
        if isinstance(inu_pct, (int, float)):
            inu_str = f"{inu_pct:.2f}%"
        else:
            inu_str = str(inu_pct)
        
        tabla.append(['Diferencia máxima', max_dif_str, '---'])
        tabla.append(['Desviación global', desv_g_str, '---'])
        tabla.append(['Uniformity Index (UI)', ui_str, '---'])
        tabla.append(['Integral Non-Uniformity (INU)', inu_str, '---'])
        
        # Estado final
        pasa_global = uniformidad_global.get('pasa_global', False)
        tabla.append(['Pasa prueba de uniformidad', '✓' if pasa_global else '✗', '---'])
        
        return pd.DataFrame(tabla, columns=['Uniformidad y ruido', '', ''])
    
    def _generar_mostrar_pdf(self, parent_widget, tablas_reporte, fecha, equipo,
                            tipo_reporte, usuario_info, info_sesion, sistema_imagenes=False):
        """
        Genera el PDF y lo muestra en el visor
        
        Args:
            parent_widget: Widget padre para mostrar el visor
            tablas_reporte (dict): Diccionario con todas las tablas procesadas
            fecha (str): Fecha del control
            equipo (str): Nombre del equipo
            tipo_reporte (str): Tipo de reporte
            usuario_info (dict): Información del usuario
            info_sesion (dict): Información de la sesión
        
        Returns:
            bool: True si se generó correctamente, False en caso contrario
        """
        try:
            # Ruta del logo

            logo_path = resource_path('resources/icons/iconoPDF.png')
            
            # Generar PDF en memoria (temp=True)
            pdf_bytes = generar_reporte_pdf_multitabla_mensual(
                tablas=tablas_reporte,
                fecha=fecha,
                user=usuario_info['usuario'],
                tipo_reporte=tipo_reporte,
                maquina=equipo,
                id_maquina=equipo,
                nombre_pdf=f"reporte_catphan_{equipo}_{fecha}.pdf",
                logo_path=logo_path,
                firma=usuario_info['firma_path'],
                role=usuario_info['rol'],
                temp=True,
                sistema_imagenes=sistema_imagenes
            )
            
            # Mostrar PDF en visor
            if hasattr(pdf_bytes, 'data'):
                pdf_bytes = bytes(pdf_bytes.data())
            # Mostrar PDF en visor
            pdf_viewer = PdfViewer(
                pdf_data=pdf_bytes,
                fecha=fecha,
                maquina=equipo,
                tipo_reporte=tipo_reporte
            )
            pdf_viewer.show()
            
            return True
            
        except Exception as e:
            print(f"Error generando/mostrando PDF: {e}")
            import traceback
            traceback.print_exc()
            return False

# Función de conveniencia para uso directo
def generar_reporte_sistema_imagenes(parent_widget, fecha, equipo, user_id, ref=None, sistema_imagenes=True):
    print("Generando reporte de sistema de imágenes..., sistema_imagenes =", sistema_imagenes)
    """
    Función de conveniencia para generar un reporte de sistema de imágenes
    
    Args:
        parent_widget: Widget padre para mostrar mensajes y el visor de PDF
        fecha (str): Fecha del control en formato 'YYYY-MM-DD'
        equipo (str): Nombre del equipo TAC
        user_id (str): ID del usuario que realiza el reporte
        ref (int, optional): ID de la sesión si ya se conoce
    
    Returns:
        bool: True si el reporte se generó exitosamente, False en caso contrario
    
    Example:
        >>> generar_reporte_sistema_imagenes(self, "2025-10-30", "TAC GE", "Dr. Juan Pérez")
    """
    reporte = ReporteControlSistemaImagenes()
    return reporte.generar_reporte_catphan(
        parent_widget=parent_widget,
        fecha=fecha,
        equipo=equipo,
        user_id=user_id,
        ref=ref,
        sistema_imagenes=sistema_imagenes
    )
