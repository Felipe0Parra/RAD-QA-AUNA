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
import html
import json
import math
import numbers
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
from data.ManejoDatos.catphan_TAC.catphan_db import _bandera_guardada, reconstruir_resultados_desde_bd
from services.anulacion import filtro_activo
from analisisImagenes.catphan.descripcion import NO_PUBLICADO, filas_adquisicion, filas_identidad, filas_medidas
from analisisImagenes.catphan.escala import CLAVE_EN_ADQUISICION as CLAVE_ESCALA, nota_escala
from analisisImagenes.catphan.criterios import Juicio, texto_fuente, texto_valor

# GI.3: lo que el informe dice donde la base no trae el valor. Nunca «None» ni una marca de correcto/incorrecto (DA-18): palabras.
NO_DISPONIBLE = "N/A"
SI, NO = "Sí", "No"


def _celda_numero(valor, formato=None, vacio=NO_DISPONIBLE):
    """El número con `formato` (el de `str.format`: '{:.2f}'; sin formato, `str`); `vacio` si no es un número (None, el texto centinela 'No disponible'
    o cualquier texto). Acepta los escalares de numpy."""
    if not isinstance(valor, numbers.Real) or isinstance(valor, bool):
        return vacio
    try:
        if not math.isfinite(valor):                     # el infinito no es una medida: «N/A», no «inf»
            return vacio
        return formato.format(valor) if formato else str(valor)
    except (OverflowError, TypeError, ValueError):       # un entero tan grande que no cabe en un float, o un «número» que str.format no sabe dar
        return vacio


def _celda_valor(valor, formato=None, vacio=NO_DISPONIBLE):
    """Como `_celda_numero`, pero un texto guardado se dice tal cual (los Valores CT guardan «Fuera de Rango» en `error_relativo`, una columna numérica)."""
    if valor is None:
        return vacio
    return _celda_numero(valor, formato, vacio) if isinstance(valor, numbers.Real) and not isinstance(valor, bool) else str(valor)


def _celda_texto(valor, vacio=NO_DISPONIBLE):
    return vacio if valor is None or str(valor).strip() == "" else str(valor)


def _celda_veredicto(valor):
    """«Sí»/«No» por el veredicto guardado; «N/A» si no hay veredicto (NULL) o no se entiende. Nunca una marca por que haya un número. La bandera se lee por su
    VALOR con la misma función que los lectores (`_bandera_guardada`): un BLOB de antes de GI.1 o un texto («No») no son verdaderos por existir."""
    veredicto = _bandera_guardada(valor)
    return NO_DISPONIBLE if veredicto is None else (SI if veredicto else NO)


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
            usuario_info2 = self._obtener_info_segundo_fisico(db, info_sesion.get('user_id_f2'))
            
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
                sistema_imagenes=sistema_imagenes,
                usuario_info2=usuario_info2
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
        query.prepare(f"""
            SELECT id FROM controles 
            WHERE fecha = ? AND equipo = ? AND control = 'Mensual'{filtro_activo('controles')}
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
        query.prepare(f"SELECT COUNT(*) FROM pruebas WHERE id_sesion = ?{filtro_activo('pruebas')}") # COUNT es para verificar existencia
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
        # LR3/LR4: lectura de IDENTIDAD (WHERE c.id = ?) -- NO lleva filtro
        # de `activo` a propósito (DA-47). El `LIMIT 1` sobraba: la clave
        # primaria ya devuelve como mucho una fila, y un LIMIT sin ORDER BY
        # sobre una tabla versionada es justo lo que AN1 marca.
        query.prepare("""
            SELECT c.equipo, c.fecha, c.user_id, c.user_id_f2
            FROM controles c
            WHERE c.id = ?
        """)
        query.addBindValue(ref)
        
        info = {
            'equipo': 'N/A',
            'fecha': 'N/A',
            'user_id': 'N/A',
            'user_id_f2': None
        }
        info['db'] = db
        info['ref'] = ref
        if query.exec() and query.next():
            info['equipo'] = query.value(0)
            info['fecha'] = query.value(1)
            info['user_id'] = query.value(2)
            info['user_id_f2'] = query.value(3)

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
        # MI0 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI0): columnas explícitas,
        # las mismas 13 que devuelve el dict de abajo. Un campo nuevo se
        # agrega en los DOS sitios -- aquí y en el dict --, no solo en uno.
        # E.2: las 5 últimas son lo que A.1/A.2 guardan por prueba (identidad
        # DICOM y desviación del protocolo); el PDF imprime LO GUARDADO.
        query.prepare(f"""
            SELECT id_prueba, id_tipo, kv, ma, espesor_corte, imagen_path, imagen_resultado,
                   equipo_dicom, serie_uid, fecha_adquisicion, adquisicion_dicom, desviacion_protocolo,
                   criterio_veredicto
            FROM pruebas
            WHERE id_sesion = ? AND id_tipo = ?{filtro_activo('pruebas')}
            ORDER BY id_prueba DESC
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
                'equipo_dicom': query.value('equipo_dicom'),
                'serie_uid': query.value('serie_uid'),
                'fecha_adquisicion': query.value('fecha_adquisicion'),
                'adquisicion_dicom': query.value('adquisicion_dicom'),
                'desviacion_protocolo': query.value('desviacion_protocolo'),
                'criterio_veredicto': query.value('criterio_veredicto'),      # G.3
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
        filtro_p = filtro_activo('pruebas').replace("activo", "p.activo")
        query.prepare(f"""
            SELECT p.id_prueba, p.id_tipo, p.imagen_path, p.imagen_resultado, tp.nombre_prueba
            FROM pruebas p
            JOIN tipos_prueba tp ON p.id_tipo = tp.id_tipo
            WHERE p.id_sesion = ? AND p.imagen_resultado IS NOT NULL{filtro_p}
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
        query.prepare("SELECT firma, role FROM users WHERE TRIM(fullname) = TRIM(?)")
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
    
    def _obtener_info_segundo_fisico(self, db, user_id_f2):
        """E.3: nombre, rol y firma del segundo físico del control, o None si no hubo.

        `controles.user_id_f2` es NULL cuando no hubo segundo físico; una BD vieja puede traer el
        centinela `' ---- '` (la migración lo normaliza a NULL): tampoco cuenta como un físico. El
        nombre se recorta solo para MOSTRARLO -- el dato de la BD no se toca, `users.fullname` tiene
        un caso real con espacio inicial -- y `_obtener_info_usuario` lo busca comparando con TRIM."""
        nombre = str(user_id_f2 or '').strip()
        if not nombre or set(nombre) == {'-'}:
            return None
        return self._obtener_info_usuario(db, nombre)

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
        infos_prueba = []   # E.2: (nombre de la categoría, info de su prueba) -> UNA tabla de parámetros

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
            infos_prueba.append(("Espesor de corte", self._obtener_info_prueba(db, ref, mapeo_id_tipo['espesor'])))
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
            infos_prueba.append(("Tamaño de pixel", self._obtener_info_prueba(db, ref, mapeo_id_tipo['tamano_pixel'])))
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
            infos_prueba.append(("Resolución de contraste", self._obtener_info_prueba(db, ref, mapeo_id_tipo['resolucion_contraste'])))
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
            infos_prueba.append(("Resolución espacial", self._obtener_info_prueba(db, ref, mapeo_id_tipo['resolucion_espacial'])))
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
            infos_prueba.append(("Valores CT", self._obtener_info_prueba(db, ref, mapeo_id_tipo['valores_ct'])))
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
            info_lin = self._obtener_info_prueba(db, ref, mapeo_id_tipo['linealidad_ct'])
            infos_prueba.append(("Linealidad CT", info_lin))
            tablas_reporte['linealidad_ct'] = self._crear_tabla_linealidad_ct(
                resultados['linealidad_ct'], con_criterio=bool(info_lin.get('criterio_veredicto'))
            )
            # Agregar imagen si está disponible
            if 'linealidad_ct' in imagenes_originales and 'linealidad_ct' in imagenes_resultados:
                tablas_reporte['imagen_linealidad_ct'] = self._crear_tabla_imagen(
                    imagenes_originales['linealidad_ct'], imagenes_resultados['linealidad_ct'], 'Linealidad CT'
                )
        
        # Tabla de uniformidad
        if 'uniformidad' in resultados and resultados['uniformidad']:
            info_uni = self._obtener_info_prueba(db, ref, mapeo_id_tipo['uniformidad'])
            infos_prueba.append(("Uniformidad", info_uni))
            tablas_reporte['uniformidad'] = self._crear_tabla_uniformidad(
                resultados['uniformidad'], con_criterio=bool(info_uni.get('criterio_veredicto'))
            )
            # Agregar imagen si está disponible
            if 'uniformidad' in imagenes_originales and 'uniformidad' in imagenes_resultados:
                tablas_reporte['imagen_uniformidad'] = self._crear_tabla_imagen(
                    imagenes_originales['uniformidad'], imagenes_resultados['uniformidad'], 'Uniformidad'
                )
        
        if infos_prueba:
            # E.2: la tabla de parámetros va UNA vez, al inicio (anotación 10 del físico).
            tablas_reporte = {
                'parametros_adquisicion': self._crear_tabla_parametros_adquisicion(
                    infos_prueba, info_sesion.get('equipo')),
                **tablas_reporte,
            }
            # G.3: el criterio y el veredicto de cada prueba, una sola tabla, tal como se archivaron. Un control
            # anterior a G.3 no trae ninguno: no sale la tabla y su informe queda igual que antes.
            tabla_criterios = self._crear_tabla_criterios(infos_prueba)
            if tabla_criterios is not None:
                tablas_reporte['criterios_veredictos'] = tabla_criterios     # su sitio lo fija TABLAS_INFORME_IMAGENES
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
    
    # E.2: kV, mA y espesor de corte se guardan como columnas propias en TODA prueba (también en las
    # anteriores a A.1); la identidad y el resto de la adquisición, solo desde A.1 (23-09-2026).
    _CLAVES_ANTERIORES_A_A1 = ('kv', 'ma', 'espesor_mm')
    LEGADO = 'no registrado (control anterior al 23-09-2026)'
    ENERGIA_NO_REGISTRADA = 'no registrada (control anterior al 24-09-2026)'   # G.2
    ESCALA_NO_REGISTRADA = 'no registrado (control anterior al 25-09-2026)'    # B.3

    def _filas_de_una_adquisicion(self, info, equipo):
        """Una adquisición tal como está GUARDADA en `pruebas` (§12.4: el documento de un control
        reabierto dice lo mismo que el del día). Devuelve `(pares, anchas)`: los pares (etiqueta, valor)
        que van lado a lado y las filas de ancho completo -- el veredicto (o lo que no se guardó) y, si la serie
        no está en HU calibrados (B.3), la nota que lo declara."""
        crudo = info.get('adquisicion_dicom')
        adq = None
        if crudo:
            try:
                adq = json.loads(crudo)
            except (TypeError, ValueError):
                adq = None
            if not isinstance(adq, dict):
                adq = None
        if adq is not None:
            desviacion = info.get('desviacion_protocolo')
            anchas = [('Frente al protocolo', desviacion or (
                f"Sin desviación registrada respecto del protocolo de {equipo or 'su equipo'}"))]
            nota = nota_escala(adq.get(CLAVE_ESCALA))            # B.3: la escala del OBI se declara, no se corrige
            if nota:
                anchas.append(('Escala de HU', nota))
            return (filas_identidad(adq) + filas_adquisicion(adq) + filas_medidas(adq, self.ESCALA_NO_REGISTRADA),
                    anchas)

        # Sin identidad DICOM: un control anterior a A.1 o una fila ilegible. Lo que SÍ se guardó
        # (kV, mA, espesor) se conserva; lo demás se dice, no se inventa ni se rellena con lo de hoy.
        basicos = {'kv': info.get('kv'), 'ma': info.get('ma'), 'espesor_mm': info.get('espesor_corte')}
        pares = [(etiqueta, 'N/A' if valor == NO_PUBLICADO else valor)
                 for etiqueta, valor in filas_adquisicion(basicos, self._CLAVES_ANTERIORES_A_A1)]
        return pares, [('Identidad y adquisición DICOM',
                        'no se pudo leer lo guardado' if crudo else self.LEGADO)]

    @staticmethod
    def _en_cuatro_columnas(pares, anchas):
        """Los pares (etiqueta, valor) en dos columnas de pares -- se leen de arriba abajo por la
        izquierda y luego por la derecha -- y las filas anchas (el veredicto, y la nota de escala de HU si
        corresponde) al final. Ver `_spans_de_filas_completas`."""
        mitad = (len(pares) + 1) // 2
        izquierda, derecha = pares[:mitad], pares[mitad:]
        filas = []
        for i, (etiqueta, valor) in enumerate(izquierda):
            etiqueta2, valor2 = derecha[i] if i < len(derecha) else ('', '')
            filas.append([etiqueta, valor, etiqueta2, valor2])
        for etiqueta, texto in anchas:
            filas.append([etiqueta, texto, None, None])
        return filas

    def _crear_tabla_parametros_adquisicion(self, infos_prueba, equipo):
        """E.2: la tabla de parámetros, UNA vez al inicio, con la información general del equipo
        como sale de la metadata (identidad, adquisición) y el veredicto del protocolo.

        Si las pruebas de la sesión se corrieron con adquisiciones DISTINTAS (kV, mA, espesor,
        identidad o desviación), no se funden: la tabla lo dice y lista cada adquisición con las
        categorías a las que corresponde -- es justo el caso que §0.4 del plan destapó.

        Args:
            infos_prueba: [(nombre de la categoría, dict de `_obtener_info_prueba`)]
            equipo: el equipo del control, para el texto del veredicto
        """
        grupos = []   # [(firma, [categorías], info)]
        for categoria, info in infos_prueba:
            firma = tuple(info.get(c) for c in (
                'kv', 'ma', 'espesor_corte', 'adquisicion_dicom', 'desviacion_protocolo'))
            for grupo in grupos:
                if grupo[0] == firma:
                    grupo[1].append(categoria)
                    break
            else:
                grupos.append((firma, [categoria], info))

        tabla = [['Parámetro', 'Valor', 'Parámetro', 'Valor']]
        if len(grupos) > 1:
            tabla.append(['Atención', 'Las pruebas de esta sesión se corrieron con adquisiciones distintas',
                          None, None])
            for n, (_firma, categorias, info) in enumerate(grupos, 1):
                tabla.append([f'Adquisición {n}', ', '.join(categorias), None, None])
                tabla.extend(self._en_cuatro_columnas(*self._filas_de_una_adquisicion(info, equipo)))
        else:
            tabla.extend(self._en_cuatro_columnas(*self._filas_de_una_adquisicion(grupos[0][2], equipo)))

        # Cada celda se vuelve un Paragraph en el generador: sin escapar, un `<` o un `&` de la
        # metadata (o de una desviación archivada) rompería el marcado. Los `None` se conservan:
        # marcan las filas de ancho completo.
        tabla = [[None if celda is None else html.escape(str(celda)) for celda in fila] for fila in tabla]
        return pd.DataFrame(tabla, columns=['Parámetros de adquisición', '', '', ''], dtype=object)

    @staticmethod
    def _juicios_guardados(info):
        """Los `Juicio` que se archivaron con la prueba (o [] si no hay o no se pueden leer)."""
        crudo = info.get('criterio_veredicto')
        if not crudo:
            return []
        try:
            lista = json.loads(crudo)
        except (TypeError, ValueError):
            return []
        campos = set(Juicio.__dataclass_fields__)
        return [Juicio(**{k: v for k, v in d.items() if k in campos}) for d in lista if isinstance(d, dict)]

    def _crear_tabla_criterios(self, infos_prueba):
        """G.3: UNA tabla con el criterio del equipo y el veredicto de cada prueba, LEÍDOS de lo archivado (§12.4: el
        documento de un control reabierto dice lo mismo que el del día; no se recalcula con el perfil de hoy). Lleva la
        fuente de cada regla y si es norma, propuesta o confirmada. `None` si ninguna prueba trae criterio."""
        filas = [['Prueba', 'Métrica', 'Valor', 'Criterio', 'Veredicto', 'Fuente']]
        for categoria, info in infos_prueba:
            for j in self._juicios_guardados(info):
                filas.append([categoria, j.etiqueta, texto_valor(j) or '---', j.criterio, j.estado, texto_fuente(j) or '---'])
        if len(filas) == 1:
            return None
        filas = [[html.escape(str(c)) for c in fila] for fila in filas]
        return pd.DataFrame(filas, columns=['Criterio y veredicto del equipo', '', '', '', '', ''], dtype=object)

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
        
        # GI.3: un valor que falta se dice «N/A», nunca «None».
        tabla.append(['Espesor promedio medido', _celda_valor(resultado.get('espesor_promedio_mm'), "{:.3f} mm")])
        tabla.append(['Espesor teórico', _celda_valor(resultado.get('espesor_teorico_mm'), "{:.3f} mm")])
        tabla.append(['Diferencia', _celda_valor(resultado.get('diferencia_mm'), "{:.3f} mm")])
        
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
        
        # GI.3: un valor que falta se dice «N/A», nunca «None».
        for rotulo, valor in (('Tamaño teórico', resultado.get('tam_px_teorico')), ('X medido', resultado.get('X')), ('Y medido', resultado.get('Y')),
                              ('Diferencia X', resultado.get('diferencia_x')), ('Diferencia Y', resultado.get('diferencia_y'))):
            tabla.append([rotulo, _celda_valor(valor, "{:.3f} mm")])
        
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
        tabla.append(['Diámetro ROI [mm]', 'Visibilidad', 'Pasa Visibilidad'])

        # Datos por ROI
        resultados_roi = resultado.get('resultados_roi', {})
        
        # Ordenar ROIs por diámetro (de mayor a menor)
        rois_ordenados = sorted(
            resultados_roi.items(),
            key=lambda x: float(x[0].replace('mm', '')),
            reverse=True
        )
        
        for diametro_str, roi_data in rois_ordenados:
            diametro = diametro_str.replace('mm', '')
            tabla.append([diametro,
                          _celda_numero(roi_data.get('visibilidad_lim'), "{:.2f}"),
                          _celda_veredicto(roi_data.get('pasa_visibilidad_lim'))])
        
        # Agregar resumen al final. GI.3: el conteo y el veredicto son los del análisis (`rois_visibles_visibilidad`, `pasa_test_visibilidad`; el lector
        # los deriva del detalle por ROI cuando el control los guardó vacíos) y las DOS filas llevan el veredicto de la prueba, no «hay un número».
        veredicto = _celda_veredicto(resumen.get('pasa_test_visibilidad'))
        tabla.append(['--- RESUMEN ---', '---', '---'])
        tabla.append(['ROIs visibles', _celda_numero(resumen.get('rois_visibles_visibilidad'), "{:g}"), veredicto])
        tabla.append(['Diámetro mínimo visible [mm]', _celda_numero(resumen.get('diametro_minimo_visible'), "{:g}"), veredicto])
        
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
        
        # Encabezados. GI.3: la frecuencia sale en lp/cm, la unidad del fantoma (la región N vale N lp/cm); el lector la entrega ya en lp/cm
        # también para los controles de enero a abril, guardados en lp/mm.
        tabla.append(['Región', 'Frecuencia [lp/cm]', 'Gap size [cm]', 'Picos', 'Valles', 'Estado'])
        
        # Datos por región
        region_results = resultado.get('region_results', {})
        
        # Ordenar regiones por frecuencia
        regiones_ordenadas = sorted(
            region_results.items(),
            key=lambda x: x[1].get('lp/cm', 0) if isinstance(x[1].get('lp/cm'), (int, float)) else 0
        )
        
        # Gap, Picos, Valles y Estado de una región que el análisis no midió no están guardados: el informe dice «N/A», no «None».
        for region_nombre, region_data in regiones_ordenadas:
            tabla.append([
                _celda_texto(region_nombre),
                _celda_numero(region_data.get('lp/cm'), "{:.2f}"),
                _celda_numero(region_data.get('gap_size_cm'), "{:.4f}"),
                _celda_numero(region_data.get('n_peaks_used')),
                _celda_numero(region_data.get('n_valleys_used')),
                _celda_texto(region_data.get('status'))
            ])
        
        # Agregar resumen
        tabla.append(['--- RESUMEN ---', '---', '---', '---', '---', '---'])
        resolucion_limite = resultado.get('resolucion_limite', {})
        mtf_lp_cm = resultado.get('mtf_lp_cm', {})
        
        lp_cm_max = resolucion_limite.get('lp_cm_maximo')
        if isinstance(lp_cm_max, numbers.Real) and not isinstance(lp_cm_max, bool) and lp_cm_max <= 0:
            lp_cm_max_str = "Sin región medible"      # el centinela -1 del análisis: ninguna región se pudo medir (no es una frecuencia)
        else:
            lp_cm_max_str = _celda_numero(lp_cm_max, "{:.2f}")
        
        tabla.append(['Resolución máxima', lp_cm_max_str, '---', '---', '---', _celda_texto(resolucion_limite.get('ultima_region'))])
        
        # MTF
        tabla.append(['MTF 10%', _celda_numero(mtf_lp_cm.get('10'), "{:.2f}"), '---', '---', '---', '---'])
        tabla.append(['MTF 50%', _celda_numero(mtf_lp_cm.get('50'), "{:.2f}"), '---', '---', '---', '---'])
        
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
            nombre = _celda_texto(material_data.get('material'))
            promedio = material_data.get('promedio_hu', 'N/A')
            rango = material_data.get('rango_hu', ['N/A', 'N/A'])
            error_abs = material_data.get('error_abs', 'N/A')
            error_rel = material_data.get('error_rel', 'N/A')

            # Formatear valores
            promedio_str = _celda_valor(promedio, "{:.1f}")
            if isinstance(rango, (list, tuple)) and len(rango) == 2 and all(isinstance(v, (int, float)) for v in rango):
                rango_str = f"{rango[0]:.1f} a {rango[1]:.1f}"
            else:
                rango_str = "N/A"
            error_abs_str = _celda_valor(error_abs, "{:.1f}")
            error_rel_str = _celda_valor(error_rel, "{:.2f}")      # puede ser un texto («Fuera de Rango», DP-107): se dice tal cual

            tabla.append([nombre, promedio_str, rango_str, error_abs_str, error_rel_str])

        return pd.DataFrame(tabla, columns=['Valores CT', '', '', '', ''])
    
    def _crear_tabla_linealidad_ct(self, resultado, con_criterio=False):
        """
        Crea tabla con resultados de linealidad CT
        
        Args:
            resultado (dict): Resultados de linealidad CT reconstruidos
        
        Returns:
            pd.DataFrame: Tabla formateada con los resultados
        """
        tabla = []
        tabla.append(['Métrica', 'Valor'])
        
        pendiente = resultado.get('pendiente')
        intercepto = resultado.get('intercepto')
        r_cuadrado = resultado.get('r_squared')
        escala_contraste = resultado.get('escala_contraste')
        linealidad_ok = resultado.get('linealidad_aceptable')
        
        # Formatear valores (GI.3: un valor que falta se dice «N/A», nunca «None»)
        pendiente_str = _celda_valor(pendiente, "{:.6f}")
        intercepto_str = _celda_valor(intercepto, "{:.3f}")
        r2_str = _celda_valor(r_cuadrado, "{:.6f}")
        escala_str = _celda_valor(escala_contraste, "{:.6f}")
        
        # G.2: la energía con la que se ajustó la curva, tal como quedó GUARDADA con la prueba
        energia_mev = resultado.get('energia_mev')
        energia_str = _celda_numero(energia_mev, "{:g}", self.ENERGIA_NO_REGISTRADA)

        tabla.append(['Energía [MeV]', energia_str])
        tabla.append(['Pendiente', pendiente_str])
        tabla.append(['Intercepto', intercepto_str])
        if con_criterio:
            # G.3: el valor guardado es el coeficiente de correlación r (D-30), no R²; la regla juzga R² = r².
            tabla.append(['r (coeficiente de correlación)', r2_str])
            if isinstance(r_cuadrado, numbers.Real) and not isinstance(r_cuadrado, bool):
                tabla.append(['R² (r al cuadrado)', _celda_numero(r_cuadrado * r_cuadrado, "{:.6f}")])
            tabla.append(['Escala de contraste', escala_str])
        else:
            tabla.append(['R² (coef. correlación)', r2_str])
            tabla.append(['Escala de contraste', escala_str])
            tabla.append(['Linealidad aceptable (R²≥0.99)', _celda_veredicto(linealidad_ok)])
        
        return pd.DataFrame(tabla, columns=['Linealidad CT', ''])
    
    def _crear_tabla_uniformidad(self, resultado, con_criterio=False):
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
        
        # GI.3: el HU de cada región es `promedio_hu` (el nombre del análisis y de lo que reabre el lector); una región sin dato dice «N/A».
        for region in regiones:
            if region in resultado:
                region_data = resultado[region]
                tabla.append([region,
                              _celda_numero(region_data.get('promedio_hu'), "{:.1f}"),
                              _celda_numero(region_data.get('desviacion'), "{:.2f}")])
        
        # Agregar métricas globales
        tabla.append(['--- MÉTRICAS GLOBALES ---', '---', '---'])
        
        max_dif_str = _celda_numero(uniformidad_global.get('max_diferencia'), "{:.1f} HU")
        desv_g_str = _celda_numero(uniformidad_global.get('desviacion_global'), "{:.2f}")
        ui_str = _celda_numero(uniformidad_global.get('uniformity_index_max'), "{:.2f}%")
        inu_str = _celda_numero(uniformidad_global.get('integral_non_uniformity_pct'), "{:.2f}%")
        
        # G.3: con criterio archivado, "Diferencia máxima" (máx - mín entre las cinco regiones) no es la métrica del
        # veredicto (máx |región - centro|, en la tabla de criterios): el rótulo lo dice.
        tabla.append(['Diferencia máxima entre regiones' if con_criterio else 'Diferencia máxima', max_dif_str, '---'])
        tabla.append(['Desviación global', desv_g_str, '---'])
        tabla.append(['Uniformity Index (UI)', ui_str, '---'])
        tabla.append(['Integral Non-Uniformity (INU)', inu_str, '---'])
        
        # Estado final
        pasa_global = uniformidad_global.get('pasa_global')
        if con_criterio:
            # G.3: el veredicto está en la tabla de criterios; UI/INU con su umbral heredado quedan como dato.
            tabla.append(['UI/INU con el umbral heredado (informativo)', _celda_veredicto(pasa_global), '---'])
        else:
            tabla.append(['Pasa prueba de uniformidad', _celda_veredicto(pasa_global), '---'])
        
        return pd.DataFrame(tabla, columns=['Uniformidad y ruido', '', ''])
    
    def _generar_mostrar_pdf(self, parent_widget, tablas_reporte, fecha, equipo,
                            tipo_reporte, usuario_info, info_sesion, sistema_imagenes=False,
                            usuario_info2=None):
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
                nombre_pdf=nombre_archivo_pdf(equipo, fecha),
                logo_path=logo_path,
                firma=usuario_info['firma_path'],
                role=usuario_info['rol'],
                user2=usuario_info2['usuario'] if usuario_info2 else None,
                firma2=usuario_info2['firma_path'] if usuario_info2 else None,
                role2=usuario_info2['rol'] if usuario_info2 else None,
                temp=True,
                sistema_imagenes=sistema_imagenes,
                # E.1: el generador solo lo usa si este informe imprime de verdad las
                # tablas de imágenes (mismo predicado que elige las tablas).
                titulo_informe=titulo_del_informe(),
                sesion=info_sesion.get('ref')
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

# E.1 (PLAN_HANDOFF_IMAGENES_22-09.md §6): la IDENTIDAD del informe, en un solo sitio.
# El documento decía "Control de calidad Control Sistema de Imágenes" y en ningún lado
# CatPhan. El título de la caja y del encabezado, el título de la sección de imágenes del
# PDF anual (`reportes_anuales.py`) y el nombre del archivo salen de estas líneas: si el
# análisis cambia de nombre, cambia aquí y en ningún otro sitio.
NOMBRE_ANALISIS = "CatPhan"
NOMBRE_CONTROL = "Control de calidad del sistema de imágenes"


def titulo_del_informe():
    """Título del informe: 'Análisis de CatPhan — Control de calidad del sistema de imágenes'."""
    return f"Análisis de {NOMBRE_ANALISIS} — {NOMBRE_CONTROL}"


def nombre_archivo_pdf(equipo, fecha):
    """Nombre del PDF, derivado del mismo nombre del análisis que el título."""
    return f"reporte_{NOMBRE_ANALISIS.lower()}_{equipo}_{fecha}.pdf"


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
