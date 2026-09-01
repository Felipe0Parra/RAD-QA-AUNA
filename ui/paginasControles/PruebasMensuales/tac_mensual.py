
from PyQt5.QtWidgets    import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, 
                                QToolBox, QSplitter, QLineEdit, QComboBox, QSizePolicy, QHeaderView, QMessageBox, QDialog)
from PyQt5.QtCore import Qt, QDate, QTime, QTimer
from PyQt5.QtGui import QColor, QFont, QPixmap
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.util_fechas import fecha_control_a_qdate as _fecha_control_a_qdate
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.catphan_TAC.leer_dicom import VisualizadorDicom
from analisisImagenes.Analisis_Catphan_TAC import *
from data.ManejoDatos.catphan_TAC.catphan_db import (guardar_prueba_completa_catphan, validar_resultados_catphan)
from resources.utils.matplotlib_lazy import get_matplotlib_components
from datetime import datetime
from enum import Enum
from PyQt5.QtCore import QTimer
import traceback, os, json
import time    
import sys

class EstadoReconstruccion(Enum):
    """Enum para definir los estados de reconstrucción de la interfaz"""
    NUEVO = "nuevo"
    RECONSTRUYENDO = "reconstruyendo"
    DISPONIBLE = "disponible"
    
    def es_modo_carga_nueva(self):
        """Retorna True si el estado permite carga de nuevos datos"""
        return self == EstadoReconstruccion.NUEVO
    
    def requiere_reconstruccion(self):
        """Retorna True si el estado requiere reconstrucción desde BD"""
        return self == EstadoReconstruccion.RECONSTRUYENDO
    
    def tiene_datos_disponibles(self):
        """Retorna True si hay datos disponibles en BD"""
        return self == EstadoReconstruccion.DISPONIBLE

class CategoriasMapping:
    """Centraliza todos los mapeos de categorías para evitar duplicación"""
    
    MAPEO_COMPLETO = {
        'espesor': {
            'titulo_gui'        : 'ESPESOR DE CORTE',
            'pestaña'           : 'Espesor de corte',
            'id_tipo'           : 1,
            'categoria_bd'      : 'espesor',
            'widgets'           : {'param_lbl_esp', 'kv_lbl_esp', 'kv_val_esp', 'ma_lbl_esp', 'ma_val_esp', 'ec_lbl_esp', 'ec_val_esp'},
            'resultado_attr'    : 'resultados_espesor',
            'funcion_guardado'  : 'guardar_espesor_corte'
        },
        'tamano_pixel': {
            'titulo_gui'        : 'TAMAÑO DE PIXEL',
            'pestaña'           : 'Tamaño de Pixel',
            'id_tipo'           : 2,
            'categoria_bd'      : 'tamano_pixel',
            'widgets'           : {'param_lbl_tp', 'kv_lbl_tp', 'kv_val_tp', 'ma_lbl_tp', 'ma_val_tp', 'ec_lbl_tp', 'ec_val_tp'},
            'resultado_attr'    : 'resultados_tamano_pixel',
            'funcion_guardado'  : 'guardar_tamano_pixel'
        },
        'resolucion_contraste': {
            'titulo_gui'        : 'RESOLUCIÓN DE CONTRASTE',
            'pestaña'           : 'Resolución de Contraste',
            'id_tipo'           : 3,
            'categoria_bd'      : 'resolucion_contraste',
            'widgets'           : {'param_lbl_rc', 'kv_lbl_rc', 'kv_val_rc', 'ma_lbl_rc', 'ma_val_rc', 'ec_lbl_rc', 'ec_val_rc'},
            'resultado_attr'    : 'resultados_resolucion_contraste',
            'funcion_guardado'  : 'guardar_resolucion_contraste'
        },
        'resolucion_espacial': {
            'titulo_gui'        : 'RESOLUCIÓN ESPACIAL',
            'pestaña'           : 'Resolución Espacial',
            'id_tipo'           : 4,
            'categoria_bd'      : 'resolucion_espacial',
            'widgets'           : {'param_lbl_re', 'kv_lbl_re', 'kv_val_re', 'ma_lbl_re', 'ma_val_re', 'ec_lbl_re', 'ec_val_re'},
            'resultado_attr'    : 'resultados_resolucion_espacial',
            'funcion_guardado'  : 'guardar_resolucion_espacial'
        },
        'valores_ct': {
            'titulo_gui'        : 'VALORES DEL NÚMERO CT',
            'pestaña'           : 'Valores CT',
            'id_tipo'           : 5,
            'categoria_bd'      : 'valores_ct',
            'widgets'           : {'param_lbl_ct', 'kv_lbl_ct', 'kv_val_ct', 'ma_lbl_ct', 'ma_val_ct', 'ec_lbl_ct', 'ec_val_ct'},
            'resultado_attr'    : 'resultados_ct',
            'funcion_guardado'  : 'guardar_valores_ct'
        },
        'linealidad_ct': {
            'titulo_gui'        : 'LINEALIDAD DEL NÚMERO CT',
            'pestaña'           : 'Linealidad del CT',
            'id_tipo'           : 6,
            'categoria_bd'      : 'linealidad_ct',
            'widgets'           : {'param_lbl_lin', 'kv_lbl_lin', 'kv_val_lin', 'ma_lbl_lin', 'ma_val_lin', 'ec_lbl_lin', 'ec_val_lin'},
            'resultado_attr'    : 'resultados_linealidad_ct',
            'funcion_guardado'  : 'guardar_linealidad_ct'
        },
        'uniformidad': {
            'titulo_gui'        : 'UNIFORMIDAD Y RUIDO',
            'pestaña'           : 'Uniformidad y Ruido',
            'id_tipo'           : 7,
            'categoria_bd'      : 'uniformidad',
            'widgets'           : {'param_lbl_uni', 'kv_lbl_uni', 'kv_val_uni', 'ma_lbl_uni', 'ma_val_uni', 'ec_lbl_uni', 'ec_val_uni'},
            'resultado_attr'    : 'resultados_uniformidad',
            'funcion_guardado'  : 'guardar_uniformidad'
        }
    }
    
    @classmethod # 
    def categoria_por_titulo(cls, titulo):
        """Obtiene la categoría y su información basada en el título de la GUI"""
        for cat, info in cls.MAPEO_COMPLETO.items():
            if info['titulo_gui'] == titulo.upper().strip():
                return cat, info
        return None, None
    
    @classmethod
    def categoria_por_pestaña(cls, nombre_pestaña):
        """Obtiene la categoría y su información basada en el nombre de la pestaña"""
        for cat, info in cls.MAPEO_COMPLETO.items():
            if info['pestaña'] == nombre_pestaña:
                return cat, info
        return None, None
    
    @classmethod
    def obtener_widgets_categoria(cls, categoria):
        """Obtiene los widgets asociados a una categoría específica"""
        return cls.MAPEO_COMPLETO.get(categoria, {}).get('widgets', set())
    
    @classmethod
    def obtener_todas_las_categorias(cls):
        """Retorna todas las categorías disponibles"""
        return list(cls.MAPEO_COMPLETO.keys())

class GestorReconstruccion:
    """Gestiona toda la lógica relacionada con la reconstrucción de datos desde la base de datos"""
    
    def __init__(self, instancia_tac):
        self.tac = instancia_tac # Referencia a la instancia principal de PruebaMensualTAC (el "self" original)
    
    def determinar_estado(self):
        """
        Determina el estado actual basado en los datos disponibles:
        - RECONSTRUYENDO: old_id existe Y hay ref en BD (sesión existente a cargar automáticamente)
        - DISPONIBLE: Hay datos en BD pero NO es reconstrucción automática (mostrar "Resultados Disponibles")
        - NUEVO: No hay datos previos
        """
        if not hasattr(self.tac, 'ref') or not self.tac.ref:
            return EstadoReconstruccion.NUEVO
        
        # RECONSTRUYENDO: Sesión existente que debe cargarse automáticamente
        if hasattr(self.tac, 'old_id') and self.tac.old_id and self._existe_ref(self.tac.ref, self.tac.equipo_f):
            return EstadoReconstruccion.RECONSTRUYENDO
        
        # DISPONIBLE: Hay datos en BD pero no es reconstrucción automática
        if self._hay_datos_disponibles():
            return EstadoReconstruccion.DISPONIBLE
        
        return EstadoReconstruccion.NUEVO
    
    def _existe_ref(self, ref, equipo):
        """Verifica si existe un registro en la base de datos con el ID (ref) y el equipo dado"""
        try:
            conn = Conexion().conectar()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM controles WHERE id = ? AND equipo = ?",
                (ref, equipo)
            )
            existe = cursor.fetchone() is not None if self.tac.old_id else False
            conn.close()
            return existe
        except Exception as e:
            print(f"Error al verificar existencia de ref: {e}")
            return False
    
    def _hay_datos_disponibles(self):
        """Verifica si hay datos disponibles en la BD para la referencia actual"""
        try:
            from data.ManejoDatos.catphan_TAC.catphan_db import consultar_pruebas_disponibles
            info_bd = consultar_pruebas_disponibles(self.tac.ref)
            return bool(info_bd and "categorias" in info_bd and info_bd["categorias"])
        except Exception as e:
            print(f"Error al consultar datos disponibles: {e}")
            return False
    
    def puede_reconstruir(self, categoria):
        """Verifica si una categoría específica puede ser reconstruida"""
        if not hasattr(self.tac, 'ref') or not self.tac.ref:
            return False
        return self._categoria_disponible_en_bd(categoria)
    
    def _categoria_disponible_en_bd(self, categoria):
        """Verifica si una categoría específica está disponible en la BD"""
        try:
            from data.ManejoDatos.catphan_TAC.catphan_db import consultar_pruebas_disponibles
            info_bd = consultar_pruebas_disponibles(self.tac.ref)
            return bool(info_bd and "categorias" in info_bd and categoria in info_bd["categorias"])
        except Exception as e:
            print(f"Error al verificar disponibilidad de categoría {categoria}: {e}")
            return False
    
    def obtener_categorias_disponibles_para_reconstruir(self):
        """Obtiene todas las categorías que tienen datos disponibles para reconstruir"""
        try:
            from data.ManejoDatos.catphan_TAC.catphan_db import consultar_pruebas_disponibles
            
            if not hasattr(self.tac, 'ref') or not self.tac.ref:
                return []
            
            info_bd = consultar_pruebas_disponibles(self.tac.ref)
            if not info_bd or "categorias" not in info_bd:
                return []
            
            # Obtener ID de prueba disponible
            id_prueba_disponible = info_bd.get("pruebas_disponibles", {}).get("id_tipo")
            
            categorias_disponibles = []
            for categoria, info in CategoriasMapping.MAPEO_COMPLETO.items():
                if id_prueba_disponible == info['id_tipo']:
                    categorias_disponibles.append(categoria)
            
            return categorias_disponibles
            
        except Exception as e:
            print(f"Error al obtener categorías disponibles: {e}")
            return []
    
    def tiene_datos_categoria_especifica(self, categoria):
        """
        Verifica si una categoría específica tiene datos disponibles en BD
        Esta es la nueva función clave para verificación por categoría
        """
        try:
            from data.ManejoDatos.catphan_TAC.catphan_db import consultar_pruebas_disponibles
            
            if not hasattr(self.tac, 'ref') or not self.tac.ref:
                return False
            
            info_bd = consultar_pruebas_disponibles(self.tac.ref)
            if not info_bd or "categorias" not in info_bd:
                return False
            
            # Verificar si la categoría específica está disponible
            return categoria in info_bd["categorias"]
            
        except Exception as e:
            print(f"Error al verificar datos para categoría {categoria}: {e}")
            return False
    
    def reconstruir_categoria_async(self, nombre_pestaña, tab_info):
        """Reconstrucción mejorada de categoría sin delays arbitrarios"""
        try:
            categoria, info_categoria = CategoriasMapping.categoria_por_pestaña(nombre_pestaña)
            if not categoria or not info_categoria:
                print(f"No se encontró mapeo para la pestaña: {nombre_pestaña}")
                return
            
            #print(f"Reconstruyendo resultados para la categoría: {categoria}")
            
            # Verificar que la categoría está disponible
            if not self.puede_reconstruir(categoria):
                print(f"La categoría {categoria} no está disponible para reconstruir")
                return
            
            # Usar QTimer con un callback más robusto
            QTimer.singleShot(50, lambda: self._ejecutar_reconstruccion(
                categoria, 
                tab_info['label'], 
                tab_info['canvas']
            ))
            
        except Exception as e:
            print(f"Error en reconstrucción asíncrona de {nombre_pestaña}: {e}")
            traceback.print_exc()
    
    def _ejecutar_reconstruccion(self, categoria, label, canvas):
        """Ejecuta la reconstrucción efectiva de la categoría"""
        try:
            from data.ManejoDatos.catphan_TAC.catphan_db import reconstruir_resultados_desde_bd
            
            reconstruir_resultados_desde_bd(
                self.tac.ref, 
                categorias=[categoria], 
                label=label,
                canvas=canvas
            )
            #print(f"    Reconstrucción completada para {categoria}")
            
        except Exception as e:
            print(f"    Error al ejecutar reconstrucción de {categoria}: {e}")
            traceback.print_exc()

class ConfiguradorUI:
    """Maneja la configuración de la interfaz de usuario basada en el estado actual"""
    
    def __init__(self, instancia_tac):
        self.tac = instancia_tac
    
    def configurar_por_estado(self, estado):
        """Configura la UI basada en el estado de reconstrucción"""
        if estado == EstadoReconstruccion.NUEVO:
            pass
        elif estado == EstadoReconstruccion.RECONSTRUYENDO:
            self._configurar_ui_reconstruccion()
        elif estado == EstadoReconstruccion.DISPONIBLE:
            self._configurar_ui_disponible()
    
    def _configurar_ui_reconstruccion(self):
        """Configuración para modo de reconstrucción desde BD"""
        # Conectar la señal de cambio de pestaña para reconstrucción
        if hasattr(self.tac, 'graficar'):
            self.tac.graficar.currentTextChanged.connect(self.tac.createTab)
    
    def _configurar_ui_disponible(self):
        """Configuración para modo de datos disponibles (sin conexión automática)"""
        # En modo DISPONIBLE, NO conectamos la señal automática
        # Los datos se cargarán solo cuando el usuario abra manualmente cada pestaña
        pass
    
    def ocultar_widgets_categoria(self, categoria):
        """Oculta los widgets específicos de una categoría (Oculta los campos de los parametros de adquisición de la tomografía)"""
        widgets_categoria = CategoriasMapping.obtener_widgets_categoria(categoria)
        for nombre_widget in widgets_categoria:
            widget = getattr(self.tac, nombre_widget, None)
            if widget is not None:
                widget.hide()
    
    def mostrar_mensaje_resultados_disponibles(self, layout_categoria, categoria):
        """Muestra un mensaje indicando que hay resultados disponibles"""
        msg = QLabel("Resultados Disponibles \n Seleccione la pestaña correspondiente para verlos")
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("""
            QLabel {
                color: #2980b9;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid #2980b9;
                border-radius: 8px;
                background-color: #eaf6fb;
                padding: 20px;
                margin-top: 15px;
            }
        """)
        layout_categoria.addWidget(msg)
        
        # Ocultar widgets específicos de la categoría
        self.ocultar_widgets_categoria(categoria)
    
    def mostrar_mensaje_categoria_especifica(self, layout_categoria, categoria, tiene_datos):
        """
        Muestra mensaje específico basado en si la categoría tiene datos o no
        """
        if tiene_datos:
            # Mostrar "Resultados Disponibles"
            msg = QLabel("📊 Resultados Disponibles\nSeleccione la pestaña correspondiente para verlos")
            msg.setAlignment(Qt.AlignCenter)
            msg.setStyleSheet("""
                QLabel {
                    color: #2980b9;
                    font-size: 16px;
                    font-weight: bold;
                    border: 2px solid #2980b9;
                    border-radius: 8px;
                    background-color: #eaf6fb;
                    padding: 20px;
                    margin-top: 15px;
                }
            """)
            layout_categoria.addWidget(msg)
            
            # Ocultar widgets específicos de la categoría
            self.ocultar_widgets_categoria(categoria)
            return True  # Se mostró mensaje de resultados disponibles
        else:
            # No mostrar nada aquí, permitir que se muestre el área de carga
            return False  # No se mostró mensaje, mostrar área de carga

class PruebaMensualTAC(PruebaMensual600):
    def __init__(self, user_id):
        #print("PruebaMensualTAC       __init__ called")
        
        super(PruebaMensual600, self).__init__(user_id)
       
        if not hasattr(self, 'general_layout'):
            self.general_layout = QVBoxLayout()
            self.setLayout(self.general_layout)
        self.esTAC = False
        if not hasattr(self, 'esiX_images') or not self.esiX_images:
            self.esTAC = True
        if not hasattr(self, 'esiX_images_mensu') or not self.esiX_images_mensu:
            self.esTAC = True
        if not hasattr(self, 'esHC_images_mensu') or not self.esHC_images_mensu:
            self.esTAC = True
        if not hasattr(self, 'esHC_images') or not self.esHC_images:
            self.esTAC = True
        
        
        
        #self.equipo_f=None
        # Variables para almacenar los resultados de análisis CatPhan
        self.user_id = user_id
        self.ref = None
        self.resultados_espesor = None
        self.resultados_tamano_pixel = None
        self.resultados_resolucion_contraste = None
        self.resultados_resolucion_espacial = None
        self.resultados_ct = None
        self.resultados_linealidad_ct = None
        self.resultados_uniformidad = None
        self.kv_actual = None
        self.ma_actual = None
        self.tam_px_teorico = None
        self.resultados_texto = None
        self.reconstruido = False  # Mantenemos para compatibilidad backwards
        
        # Inicializar gestores de reconstrucción
        self.gestor_reconstruccion = GestorReconstruccion(self)
        self.configurador_ui = ConfiguradorUI(self)
        self.estado_actual = EstadoReconstruccion.NUEVO
        
        if hasattr(self, 'esIX'):
            print("control de AI EX")
        
        if hasattr(self, 'anual') and self.anual and hasattr(self, 'esHc') and self.esHc:
            self.equipo_f = 'esHC'
            self.lista_maquina=['encabezado_anual_Halcyon', 'Control del sistema de imagenes anual', 'Iniciar control del sistema de imágenes', 'Halcyon', 'preguntas_mensu_TAC']
        #     #self.preINIGI(user_id, self.lista_maquina)
        
        if hasattr(self, 'esTAC') and self.esTAC:
            self.equipo_f = 'Tomógrafo'
            self.lista_maquina=['encabezado_mensu_TAC', 'Control mensual', 'Iniciar control mensual', 'Tomógrafo', 'preguntas_mensu_TAC']
            #self.preINIGI(user_id, self.lista_maquina)
        if hasattr(self, "esiX_images") and self.esiX_images:
            self.equipo_f = 'Clinac ix' 
            self.lista_maquina=['encabezado_images_ix', 'Control anual', 'Iniciar Imagenes anual', 'Clinac ix', 'preguntas_mensu_TAC']
            
            print("control de AI EX")
        if hasattr(self, "esiX_images_mensu") and self.esiX_images_mensu:
            self.equipo_f = 'Clinac ix' 
            self.lista_maquina=['encabezado_images_ix', 'Control mensual', 'Iniciar Imagenes mensual', 'Clinac ix', 'preguntas_mensu_TAC']
            print("control de AI EX")
            
        if hasattr(self, "esHC_images_mensu") and self.esHC_images_mensu:
            self.equipo_f = 'Halcyon' 
            self.lista_maquina=['encabezado_images_HC', 'Control mensual', 'Iniciar Imagenes mensual HC', 'Halcyon', 'preguntas_mensu_TAC']
            print("control de Halcyon")
            
        elif hasattr(self, "esHC_images") and self.esHC_images:
            self.equipo_f = 'Halcyon' 
            self.lista_maquina=['encabezado_images_HC', 'Control Anual', 'Iniciar Imagenes anual HC', 'Halcyon', 'preguntas_mensu_TAC']
            print("control de Halcyon")
        
        
        self.preINIGI(user_id, self.lista_maquina)
        
        
        
        
        # Consultar la referencia almacenada en la base de datos segun la fecha

    def iniGUI(self, inputs_maquina = None):
        """
        Versión específica de iniGUI para TAC que evita conflictos de layout
        """
        # Crear un separador horizontal
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)

        # Crear layout izquierdo con el formulario de control
        test_control_layout = QWidget()
        
        # Crear layout derecho con los gráficos
        graphics_layout = self.graphicsWindow()

        # Llamar a nuestra implementación específica de controlTestWindow
        _, _, _ = self.controlTestWindow(sheet_name="preguntas_mensu_TAC")
        test_control_layout.setLayout(self.general_layout)

        if hasattr(self, 'fecha_control'):
            # F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS4.7): TAC hereda de
            # PruebaMensual600 y comparte date_box/fecha_control -- mismo
            # parser tolerante que el resto de mensuales, para que un
            # fecha_control con o sin día se muestre bien.
            fecha = _fecha_control_a_qdate(self.fecha_control)
            self.date_box.setDate(fecha)
            # R7 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase D): esta clase
            # sobreescribe iniGUI completo sin heredar del de
            # PruebaMensual600 -- el bloqueo de fecha aplicado ahí no
            # llegaba aquí. En TAC además tiene consecuencia real: sin
            # bloquear, `fecha_actual = self.date_box.date()...` (usado al
            # guardar sesiones Catphan) podía quedar distinta de
            # `controles.fecha` del mismo control si el físico la cambiaba
            # tras iniciar.
            self.date_box.setEnabled(False)
        if hasattr(self, 'nombre_fisico1'):
            index = self.fisico1.findText(self.nombre_fisico1)
            if index >= 0:
                self.fisico1.setCurrentIndex(index)
            self.fisico1.setEnabled(False) 
        if hasattr(self, 'nombre_fisico2'):
            self.fisico2.setItemText(0, self.nombre_fisico2)  # Forzar actualización del texto
            #self.fisico2.setReadOnly(True)
        
        # Configurar splitter
        splitter.addWidget(test_control_layout)
        splitter.addWidget(graphics_layout)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # Agregar el splitter al layout principal
        self.main_layout.addWidget(splitter)

        # Determinar estado usando el nuevo gestor de reconstrucción
        self.estado_actual = self.gestor_reconstruccion.determinar_estado()
        
        # Actualizar variable de compatibilidad
        self.reconstruido = self.estado_actual.requiere_reconstruccion()
        
        if hasattr(self, "ref") and self.ref and self.equipo_f:
            #print(f"Ref creada con ID: {self.ref}")
            #print(f"Estado determinado: {self.estado_actual.value}")
            # Configurar UI basada en el estado
            self.configurador_ui.configurar_por_estado(self.estado_actual)
        else:
            print("⚠️ No hay referencia disponible - datos no se cargarán automáticamente")
         
    
    def setupTap1(self):
        # Combo de selección de gráfica
        self.graficar = QComboBox()
        self.graficar.addItems([
            'Ver resultados de...',
            'Espesor de corte',
            'Tamaño de Pixel',
            'Resolución de Contraste',
            'Resolución Espacial', 
            'Valores CT',
            'Linealidad del CT',
            'Uniformidad y Ruido'
        ])

        # Tabla vacía inicial (se llena después)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(0)
        self.tabla.setRowCount(0)

        # Canvas para gráficas
        mpl = get_matplotlib_components()
        FigureCanvas = mpl['FigureCanvas']
        Figure = mpl['Figure']
        self.canvas = FigureCanvas(Figure(figsize=(10, 20)))

        # Contenedor superior con combo y gráfica
        contenedor_superior = QWidget()
        self.col2 = QVBoxLayout(contenedor_superior)
        self.col2.setContentsMargins(0, 0, 0, 0)  # Eliminar márgenes
        self.col2.setSpacing(0)  # Eliminar espacio entre widgets
        self.col2.addWidget(self.graficar)
        self.col2.addWidget(self.canvas)

        # Layout principal de la pestaña
        layout_tab = QVBoxLayout()
        layout_tab.addWidget(contenedor_superior)

        self.tab1.setLayout(layout_tab)

    def controlTestWindow(self, sheet_name):
        """
        Implementación específica para TAC que evita conflictos de layout
        """
        archivo = 'widgets.xlsx'
        self.toolbox = QToolBox()
        
        # Encabezado general
        _ = self.setupBox(archivo, self.lista_maquina[0])
        self.date_box.setDisplayFormat("yyyy/MM")
        
        # Cargar widgets de la hoja correspondiente
        self.df_tac, n, layouts, _ = self.setupBox(archivo, sheet_name, main=False)

        self.datos_tabla = self.storeDailyTests(self.df_tac)

        # Crear widgets para las categorías específicas de TAC con títulos
        self.category1 = self.imagenUpLoader("ESPESOR DE CORTE")
        self.category2 = self.imagenUpLoader("TAMAÑO DE PIXEL")
        self.category3 = self.imagenUpLoader("RESOLUCIÓN DE CONTRASTE")
        self.category4 = self.imagenUpLoader("RESOLUCIÓN ESPACIAL")
        self.category5 = self.imagenUpLoader("VALORES DEL NÚMERO CT")
        self.category6 = QWidget()
        self.category7 = self.imagenUpLoader("UNIFORMIDAD Y RUIDO")
        self.category8 = QWidget()
       
        # Importante: Agregar toolbox al layout general existente (no crear uno nuevo)
        self.general_layout.addWidget(self.toolbox)
        self.btn_cargar_dicom = QPushButton("🔍 Seleccionar Carpeta DICOM")
        self.btn_cargar_dicom.clicked.connect(self._cargar_carpeta_dicom)
        self.reporte_btn = QPushButton("Generar reporte pdf")
        self.general_layout.addWidget(self.btn_cargar_dicom)
        self.general_layout.addWidget(self.reporte_btn)
        # ----- Construir la tabla estática para la categoría 6 -----
        category6_layout = QVBoxLayout(self.category6)
        category6_layout.setContentsMargins(5, 25, 5, 5)
        category6_layout.setSpacing(15) 

        # Título de la categoría 6
        titulo_category6 = QLabel("📊 LINEALIDAD DEL NÚMERO CT")
        titulo_category6.setAlignment(Qt.AlignCenter)
        category6_layout.addWidget(titulo_category6)
        # categoría 8
        titulo_category = QLabel("Cortes recomendados")

        
        # Agregar al layout de la categoría 6
        contenedor_energia, self.tabla_linealidad_ct = self.crear_tabla_linealidad_ct()

        category6_layout.addLayout(contenedor_energia if contenedor_energia else QVBoxLayout())
        category6_layout.addWidget(self.tabla_linealidad_ct)
        #-----------------------------------------------------------

        # Asignar layouts a categorías
        for i, layout in enumerate(layouts, 1):
            category_widget = getattr(self, f'category{i}')
            
            combined_widget = QWidget()
            combined_layout = QVBoxLayout(combined_widget)
            combined_layout.setContentsMargins(5, 5, 5, 5)
            combined_layout.setSpacing(2)
            
            # Nuestro widget (para cat.6 ya contiene la tabla)
            combined_layout.addWidget(category_widget)
            
            # Para la categoría 6, opcionalmente omite añadir el layout del Excel
            if i != 6:
                original_widget = QWidget()
                original_widget.setLayout(layout)
                combined_layout.addWidget(original_widget)
            
            setattr(self, f'category{i}', combined_widget)

        # Añadir categorías al toolbox
        self.toolbox.addItem(self.category1, '1. ESPESOR DE CORTE')
        self.toolbox.addItem(self.category2, '2. TAMAÑO DE PIXEL')
        self.toolbox.addItem(self.category3, '3. RESOLUCIÓN DE CONTRASTE')
        self.toolbox.addItem(self.category4, '4. RESOLUCIÓN ESPACIAL')
        self.toolbox.addItem(self.category5, '5. VALORES DEL NÚMERO CT')
        self.toolbox.addItem(self.category6, '6. LINEALIDAD DEL NÚMERO CT Y ESCALA DE CONTRASTE')
        self.toolbox.addItem(self.category7, '7. UNIFORMIDAD Y RUIDO')
        self.toolbox.addItem(self.category8, '8. CORTES DE REFERENCIA')
        
        index = self.toolbox.currentIndex()
        texto = self.toolbox.itemText(index)
        
        if hasattr(self, 'btn_espesor_ref') and self.btn_espesor_ref:
           self.btn_espesor_ref.clicked.connect(self.mostrar_espesor_referencia)
        #self.toolbox.currentChanged.connect(self.automatizacion)
        if hasattr(self, 'btn_tam_pix') and self.btn_tam_pix:
           self.btn_tam_pix.clicked.connect(self.mostrar_pixel_referencia)
           
        if hasattr(self, 'btn_contrast_ref') and self.btn_contrast_ref:
           self.btn_contrast_ref.clicked.connect(self.mostrar_contraste_referencia)
           
        if hasattr(self, 'btn_ref_espacial') and self.btn_ref_espacial:
           self.btn_ref_espacial.clicked.connect(self.mostrar_resp_referencia)
           
        if hasattr(self, 'btn_ct') and self.btn_ct:
           self.btn_ct.clicked.connect(self.mostrar_ct_referencia)
           
        if hasattr(self, 'btn_unif') and self.btn_unif:
           self.btn_unif.clicked.connect(self.mostrar_uniformidad_referencia)
        
       

        self.pruebas_categorias = {
            'espesor': self.category1,
            'tamaño_pixel': self.category2,
            'resolucion_contraste': self.category3,
            'resolucion_espacial': self.category4,
            'valores_numero_ct': self.category5,
            'linealidad_numero_ct': self.category6,
            'uniformidad_ruido': self.category7,
            'cortes': self.category8,
        }
        # Devolver lo que se espera que devuelva este método
        
        self.reporte_btn.clicked.connect(self.generar_reporte_pdf)
        
        
        

        return self.toolbox, None, None
    
    def _cargar_carpeta_dicom(self):
        # Un solo visualizador, una sola carga
        # dispatch según toolbox.currentIndex()
        categoria = list(self.pruebas_categorias.keys())[self.toolbox.currentIndex()]
        self._procesar_para_categoria(categoria)
        dicom = True
        print(categoria)
        return dicom
    def _procesar_para_categoria(self, categoria):
        if not hasattr(self, 'visualizador_principal'):
            print("Error: No hay visualizador principal inicializado")
            return
        self.visualizador_principal.sel_imagen_btn.click()
    def crear_tabla_linealidad_ct(self):
        """
        Crea la tabla de Linealidad del CT con datos predeterminados.
        """
        tabla = QTableWidget()
        headers = ["Material", "MeV", "μ/ρ (cm²/g)", "ρ (g/cm³)", "μ (1/cm)", "HU"]
        datos = [
            ["Aire",        "", "", "", "", ""],
            ["PMP",         "", "", "", "", ""],
            ["LDPE",        "", "", "", "", ""],
            ["Poliestireno","", "", "", "", ""],
            ["Acrílico",    "", "", "", "", ""],
            ["Delrin",      "", "", "", "", ""],
            ["Teflón",      "", "", "", "", ""],
        ]

        tabla.setColumnCount(len(headers))
        tabla.setRowCount(len(datos))
        tabla.setHorizontalHeaderLabels(headers)
        tabla.verticalHeader().setVisible(False)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for fila, fila_datos in enumerate(datos):
            for columna, dato in enumerate(fila_datos):
                item = QTableWidgetItem(str(dato))
                # Columna Material solo lectura
                if columna == 0:
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                tabla.setItem(fila, columna, item)

        # --- Mostrar mensaje si hay resultados disponibles en BD ---
        from data.ManejoDatos.catphan_TAC.catphan_db import consultar_pruebas_disponibles

        info_bd = consultar_pruebas_disponibles(self.ref)
        if info_bd and "categorias" in info_bd and "linealidad_ct" in info_bd["categorias"]:
            # Mostrar solo mensaje de resultados disponibles
            msg = QLabel("Resultados Disponibles")
            msg.setAlignment(Qt.AlignCenter)
            msg.setStyleSheet(""" QLabel {color: #2980b9; border: 2px solid #2980b9;
                                    border-radius: 8px; background-color: #eaf6fb;
                                    padding: 20px; margin-top: 15px;}""")
            
            return None, msg  # Retorna el mensaje en lugar de la tabla 
        else:
            # *** NUEVA LÓGICA: Cargar valores CT desde BD si existen pero no hay datos de linealidad ***
            if (info_bd and "categorias" in info_bd and "valores_ct" in info_bd["categorias"] 
                and "linealidad_ct" not in info_bd["categorias"]):
                # Hay valores CT guardados pero no linealidad, cargar automáticamente
                valores_ct_cargados = self.cargar_valores_ct_desde_bd()
                if valores_ct_cargados:
                    print("🔄 Valores CT cargados desde BD, se usarán para poblar la tabla de linealidad")
                else:
                    print("⚠️ No se pudieron cargar valores CT desde BD")
            # Entrada para Energía
            contenedor_energia = QHBoxLayout()
            energia_lin_ct = QLabel("Energía (MeV):")
            
            self.energia_lin_ct_val = QLineEdit()

                # Elegir para confirmar la energía ingresada ↓
            opciones = ["Seleccionar Energía", "0.12 MeV"]
            self.energia_select = QComboBox()
            self.energia_select.setFixedWidth(300)
            self.energia_select.addItems(opciones)

            self.energia_select.currentTextChanged.connect(self.on_energia_linealidad_cambio)

            # Configurar el espacio para la energía
            contenedor_energia.addWidget(energia_lin_ct)
            contenedor_energia.addWidget(self.energia_select)
            contenedor_energia.addStretch()
            return contenedor_energia, tabla # Retorna el layout de selección de energía y la tabla

    def imagenUpLoader(self, titulo_prueba):
        # Crear una NUEVA instancia de visualizador DICOM para cada categoría
        visualizador = VisualizadorDicom(target_canvas=self.canvas)
        
        
        # Inicializar el visualizador principal si no existe (para self.col2)
        if not hasattr(self, 'visualizador_principal'):
            self.visualizador_principal = VisualizadorDicom(target_canvas=self.canvas)
            # Agregar solo los controles (sliders y botón elegir corte) a self.col2
            self.col2.addWidget(self.visualizador_principal.contenedor_grafica)
            # Conectar señales del visualizador principal
            self.visualizador_principal.corte_seleccionado.connect(self.procesar_corte_seleccionado)
            self.visualizador_principal.imagen_cargada.connect(self.asignar_parametros_adquisicion)
            self.visualizador_principal.imagen_cargada.connect(
        lambda: self.mapear_a_cortes(self.visualizador_principal)  # Aquí
    )
        
        # Inicializar la lista de visualizadores si no existe
        if not hasattr(self, 'visualizadores'):
            self.visualizadores = []
            
        
        # Agregar el visualizador a la lista
        self.visualizadores.append(visualizador)
        
        # Conectar señales desde el visualizador 
        visualizador.corte_seleccionado.connect(self.procesar_corte_seleccionado)

        # Crear un widget con título específico para cada categoría
        widget_categoria = QWidget()
        layout_categoria = QVBoxLayout(widget_categoria)
        layout_categoria.setContentsMargins(10, 10, 10, 10)  # Márgenes internos
        layout_categoria.setSpacing(8)  # Espacio entre elementos
        
        # TÍTULO DE LA PRUEBA
        titulo_label = QLabel(f"📊 {titulo_prueba}")
        titulo_label.setAlignment(Qt.AlignCenter)
        layout_categoria.addWidget(titulo_label)

        # --- NUEVA LÓGICA HÍBRIDA POR CATEGORÍA ---
        categoria_bd, info_categoria = CategoriasMapping.categoria_por_titulo(titulo_prueba)

        mostrar_area_carga = True
        
        if categoria_bd:
            # Verificar si ESTA CATEGORÍA ESPECÍFICA tiene datos en BD
            tiene_datos_categoria = self.gestor_reconstruccion.tiene_datos_categoria_especifica(categoria_bd)
            
            if tiene_datos_categoria:
                # Esta categoría tiene datos → Mostrar "Resultados Disponibles"
                mensaje_mostrado = self.configurador_ui.mostrar_mensaje_categoria_especifica(
                    layout_categoria, categoria_bd, True
                )
                mostrar_area_carga = not mensaje_mostrado
                #print(f"✅ Categoría {categoria_bd}: Tiene datos en BD - Mostrar 'Resultados Disponibles'")
            else:
                # Esta categoría NO tiene datos → Mostrar área de carga
                #print(f"🆕 Categoría {categoria_bd}: Sin datos en BD - Mostrar área de carga")
                mostrar_area_carga = True

        # Si no hay resultados, mostrar área de carga de imagen como siempre
        if mostrar_area_carga:
            # ÁREA DE CARGA DE IMAGEN
            frame_imagen = QWidget()
            frame_imagen.setStyleSheet(""" QWidget {border: 2px dashed #95a5a6; border-radius: 10px;
                                                    background-color: #f8f9fa; padding: 15px; } """)
            
            frame_layout = QVBoxLayout(frame_imagen)
            frame_layout.setAlignment(Qt.AlignCenter)
            
            # Etiqueta de instrucción
            instruccion_label = QLabel("📁 Cargar imagen DICOM para análisis")
            instruccion_label.setAlignment(Qt.AlignCenter)
            instruccion_label.setStyleSheet("""
                QLabel {
                    color: #7f8c8d;
                    font-size: 12px;
                    font-style: italic;
                    border: none;
                    background: transparent;
                    padding: 5px;
                }
            """)
            #frame_layout.addWidget(instruccion_label)
            
            # Agregar la etiqueta y el botón del visualizador
            visualizador.lbl_imagen.setText("Esperando imagen...")
            visualizador.lbl_imagen.setStyleSheet("""
                QLabel {
                    color: #34495e;
                    font-size: 11px;
                    padding: 5px;
                    border: none;
                    background: transparent;
                }
            """)
            frame_layout.addWidget(visualizador.lbl_imagen)
            
            # Personalizar el botón
            # visualizador.sel_imagen_btn.setText("🔍 Seleccionar Carpeta DICOM")
            # visualizador.sel_imagen_btn.setStyleSheet("""
            #     QPushButton { background-color: #3498db; color: white; border: none;
            #         border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: bold;}

            #     QPushButton:hover {background-color: #2980b9;}

            #     QPushButton:pressed {background-color: #1c5985;}""")
            
            #frame_layout.addWidget(visualizador.sel_imagen_btn)
            
            layout_categoria.addWidget(frame_imagen)
            print("Imagen subida")
            
            print("VISUALIZADOR QUE CONECTA:", id(visualizador))
            
            
            
            
            self.visualizador_principal.imagen_cargada.connect(lambda: visualizador.lbl_imagen.setText("✅ Imagen cargada correctamente"))
          
            try:
                print("Resultados: ")
                print(visualizador.resultados)
            except Exception as e:
                print("no cap: ", e)
            
            def sincronizar_con_principal(self, vol):
                print("Entra a sincronizar con principal")
                
            
                
                if visualizador.vol is not None:
                    
                    # Transferir volumen y ruta
                    self.visualizador_principal.vol = visualizador.vol
                    self.visualizador_principal.ruta_carpeta = visualizador.ruta_carpeta
                    
                    self.visualizador_principal.idx_actual = 0
                    print("Imagen subida")
                    visualizador.lbl_imagen.setText("✅ Imagen cargada correctamente")
                    #QTimer.singleShot(600, self.automatizacion)
       

                    #self.mapear_a_cortes(visualizador.resultados, visualizador.cortes)
                    
            
                    visualizador.lbl_imagen.setStyleSheet("""
                            QLabel {
                                color: #27ae60;
                                font-size: 11px;
                                font-weight: bold;
                                padding: 5px;
                                border: none;
                                background: transparent;
                            }
                        """)
                    
                    if (self.visualizador_principal.vol.volumen_hu is not None and 
                        self.visualizador_principal.vol.volumen_hu.size > 0):
                        try:
                            fig = self.canvas.figure
                            fig.clear()
                            self.visualizador_principal.actualizar_ventana()
                            self.visualizador_principal.slider_wl.show()
                            self.visualizador_principal.slider_ww.show()
                            self.visualizador_principal.slider_wl_label.show()
                            self.visualizador_principal.slider_ww_label.show()
                            self.visualizador_principal.info_label.show()
                            self.visualizador_principal.elegir_corte_btn.show()
                            
                            visualizador.lbl_imagen.setText("✅ Imagen cargada correctamente")
                            #QTimer.singleShot(600, self.automatizacion)
                            
                            visualizador.lbl_imagen.setStyleSheet("""
                                QLabel {
                                    color: #27ae60;
                                    font-size: 11px;
                                    font-weight: bold;
                                    padding: 5px;
                                    border: none;
                                    background: transparent;
                                }
                            """)
                        except Exception as e:
                            print(f"Error en actualizar_ventana durante sincronización: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print("Error: Volumen inválido durante sincronización")
            
            visualizador.imagen_cargada.connect(lambda: sincronizar_con_principal())
            visualizador.imagen_cargada.connect(lambda: print("    ⪧ Imagen Recibida"))
            #QTimer.singleShot(600, self.automatizacion)
            visualizador.imagen_cargada.connect(self.asignar_parametros_adquisicion)
        
        return widget_categoria
    
    # Asigna los parámetros de adquisición (kv, ma, espesor de corte) desde el visualizador principal
    def asignar_parametros_adquisicion(self, reconstruido=False):
        if not hasattr(self, 'visualizador_principal'):
            print("Error: No hay visualizador principal para asignar parámetros.")
            return

        visualizador = self.visualizador_principal
        if visualizador.vol is None:
            print("Error: No hay volumen cargado en el visualizador principal para asignar parámetros.")
            return
        
        kv = getattr(visualizador.vol, 'kv', None)
        ma = getattr(visualizador.vol, 'ma', None)
        espesor_corte = round(getattr(visualizador.vol, 'espesor_corte', None), 1) if getattr(visualizador.vol, 'espesor_corte', None) is not None else None
        #contrast_resolution = getattr(visualizador.vol, 'corte', None) if getattr(visualizador.vol, 'espesor_corte', None) is not None else None
        # Guardar parámetros para uso posterior y guardado en BD
        self.espesor_corte_val = espesor_corte
        self.kv_actual = kv
        self.ma_actual = ma
        #QTimer.singleShot(600, self.automatizacion)

        #print(f"Parámetros obtenidos - kV: {kv}, mA: {ma}, Espesor de corte: {espesor_corte}")

        # categoria_activa = self.obtener_categoria_activa()  # Determina la categoría activa

        # if categoria_activa is None:
        #     print("Error: No se pudo determinar la categoría activa.")
        #     return

        #print(f"Categoría activa detectada: {categoria_activa}")

        mapeo_widgets = {
            'espesor':              {'kv_val': 'kv_val_esp', 'ma_val': 'ma_val_esp', 'ec_val': 'ec_val_esp'},
            'tamaño_pixel':         {'kv_val': 'kv_val_tp' , 'ma_val': 'ma_val_tp' , 'ec_val': 'ec_val_tp' },
            'resolucion_contraste': {'kv_val': 'kv_val_rc' , 'ma_val': 'ma_val_rc' , 'ec_val': 'ec_val_rc' },
            'resolucion_espacial':  {'kv_val': 'kv_val_re' , 'ma_val': 'ma_val_re' , 'ec_val': 'ec_val_re' },
            'valores_numero_ct':    {'kv_val': 'kv_val_ct' , 'ma_val': 'ma_val_ct' , 'ec_val': 'ec_val_ct' },
            'linealidad_numero_ct': {'kv_val': 'kv_val_lin', 'ma_val': 'ma_val_lin', 'ec_val': 'ec_val_lin'},
            'uniformidad_ruido':    {'kv_val': 'kv_val_uni', 'ma_val': 'ma_val_uni', 'ec_val': 'ec_val_uni'}
        }
        #QTimer.singleShot(600, self.automatizacion)
        

        # if categoria_activa not in mapeo_widgets:
        #     print(f"Error: No se encontró mapeo para la categoría {categoria_activa}")
        #     return

        #widgets_categoria = mapeo_widgets[categoria_activa]
        parametro_por_prueba = []
        for categoria, widgets in mapeo_widgets.items():
            for tipo_widget, nombre_widget in widgets.items():
                try:
                    widget = getattr(self, nombre_widget)
                    widget.setReadOnly(False)
                    if 'kv_val' in tipo_widget:
                        widget.setText(f"{str(kv)} kV" if kv is not None else "")
                    elif 'ma_val' in tipo_widget:
                        widget.setText(f"{str(ma)} mA" if ma is not None else "")
                    elif 'ec_val' in tipo_widget:
                        widget.setText(f"{str(espesor_corte)} mm" if espesor_corte is not None else "")
                    widget.setReadOnly(True)
                    
                except AttributeError:
                    pass
        # try:
        #     for tipo_widget, nombre_widget in widgets_categoria.items():
        #         try:
        #             widget = getattr(self, nombre_widget)
        #             widget.setReadOnly(False)
        #             widget.setText("")
        #             if 'kv_val' in tipo_widget:
        #                 widget.setText(f"{str(kv)} kV" if kv is not None else "")
        #             elif 'ma_val' in tipo_widget:
        #                 widget.setText(f"{str(ma)} mA" if ma is not None else "")
        #             elif 'ec_val' in tipo_widget:
        #                 widget.setText(f"{str(espesor_corte)} mm" if espesor_corte is not None else "")
        #             widget.setReadOnly(True)
        #             #print(f"✅ Widget {nombre_widget} actualizado correctamente")
        #         except AttributeError:
        #             print(f"⚠️ Widget {nombre_widget} no encontrado en la interfaz")

        #         except Exception as e:
        #             print(f"❌ Error al actualizar widget {nombre_widget}: {e}")
        #     parametro_por_prueba.append((categoria_activa, [kv, ma, espesor_corte]))
        #     #print(f"Parámetros asignados para {categoria_activa}: {parametro_por_prueba}")

        # except Exception as e:
        #     print(f"❌ Error al asignar parámetros: {e}")

    # Determina en qué categoría se acaba de cargar la carpeta de archivos DICOM
    def obtener_categoria_activa(self):
        """
        Determina la categoría activa usando self.pruebas_categorias y mapeo_categorias.
        Devuelve el nombre mapeado para usar en el resto del flujo.
        """
        mapeo_categorias = {
            'espesor'               :   'espesor',
            'tamaño_pixel'          :   'tam_px',
            'resolucion_contraste'  :   'res_con',
            'resolucion_espacial'   :   'res_esp',
            'valores_numero_ct'     :   'num_ct',
            'linealidad_numero_ct'  :   'lin_ct',
            'uniformidad_ruido'     :   'uniformidad'
        }

        for categoria, widget in self.pruebas_categorias.items():
            if widget is not None and widget.isVisible():
                nombre_mapeado = mapeo_categorias.get(categoria, categoria)
                #print(f"Categoría activa detectada: {categoria} → {nombre_mapeado}")
                return categoria

        # Fallback: primera categoría del mapeo
        primera_categoria = list(mapeo_categorias.values())[0]
        print(f"No se encontró una categoría activa, usando predeterminada: {primera_categoria}")
        return primera_categoria

    def procesar_corte_seleccionado(self, corte):
        """
        Procesa el corte seleccionado y extrae información del volumen DICOM.
        """
        # Usar el visualizador principal que tiene los controles en self.col2
        visualizador_activo = getattr(self, 'visualizador_principal', None)
        
        if not visualizador_activo or not visualizador_activo.vol:
            print("Error: No hay volumen cargado en el visualizador principal.")
            return None, None, None

        # Obtener los valores actuales de los sliders
        wl = visualizador_activo.slider_wl.value()
        ww = visualizador_activo.slider_ww.value()

        #print(f"Valores actuales - WL: {wl}, WW: {ww}")

        # Obtener el volumen HU y el corte seleccionado
        try:
            imagen_analisis = visualizador_activo.vol.volumen_hu[corte]
            imagen_grafica = visualizador_activo.vol.get_volumen_normalizado(wl, ww)[corte]
            tam_px = visualizador_activo.vol.get_pixel_spacing()
        except IndexError:
            print(f"Error: El índice de corte {corte} está fuera de rango.")
            return None, None, None
            
        # Almacenar información del corte seleccionado para guardado posterior
        self.corte_seleccionado_info = {
            'indice_corte': corte,
            'ruta_carpeta_dicom': getattr(visualizador_activo, 'ruta_carpeta', None),
            'imagen_analisis': imagen_analisis,
            'wl': wl,
            'ww': ww
        }
        #print(f"Corte seleccionado: {corte}, Ruta DICOM: {self.corte_seleccionado_info['ruta_carpeta_dicom']}")
        
        if (imagen_analisis is not None and imagen_analisis.size > 0 and
            imagen_grafica is not None and imagen_grafica.size > 0 and 
            tam_px and len(tam_px) > 0 and tam_px[0] is not None):
            self.imagen_dicom_cargada(imagen_analisis, imagen_grafica, tam_px[0])
        else:
            print("Error: No se pudo procesar el corte seleccionado correctamente.")
            return None, None, None
    

        return imagen_analisis, imagen_grafica, tam_px[0]

    # Estos métodos son específicos para crear la tabla de linealidad del CT 
    # (Energia, material, μ/ρ, ρ, μ, HU en la categoría 6 ▮▯)
    def on_energia_linealidad_cambio(self, texto):
        """
        Carga desde JSON las propiedades de materiales para la energía seleccionada
        y rellena la tabla de linealidad (μ/ρ, ρ, μ).
        """
        if not hasattr(self, "tabla_linealidad_ct"):
            return
        if not texto or "Seleccionar" in texto:
            # Limpia columnas excepto Material
            for i in range(self.tabla_linealidad_ct.rowCount()):
                for j in range(1, self.tabla_linealidad_ct.columnCount()):
                    self.tabla_linealidad_ct.setItem(i, j, QTableWidgetItem(""))
            return

        energia_num = texto.replace(" MeV", "").strip()  # p.ej. "0.12"
        energia_key = f"energia_{energia_num}MeV"        # p.ej. "energia_0.12MeV"

        # Resolver ruta del JSON de forma robusta
        base_dir = os.path.dirname(__file__)
        json_path = None
        self.mu_lista = []
        for up in range(1, 6):
            candidate = os.path.abspath(os.path.join(base_dir, *[".."]*up, "resources", "archivos_json", "poder_frenado_materiales.json"))
            if os.path.exists(candidate):
                json_path = candidate
                break
        if not json_path:
            QMessageBox.warning(self, "Error", "No se encontró el archivo de materiales poder_frenado_materiales.json")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo leer el archivo:\n{e}")
            return

        materiales_por_energia = data.get(energia_key)
        if not materiales_por_energia:
            QMessageBox.information(self, "Aviso", f"No hay datos para la energía {texto} en el archivo JSON.")
            # Limpia columnas excepto Material
            for i in range(self.tabla_linealidad_ct.rowCount()):
                for j in range(1, self.tabla_linealidad_ct.columnCount()):
                    self.tabla_linealidad_ct.setItem(i, j, QTableWidgetItem(""))
            return

        # Mapeo nombres de tabla -> nombres en JSON
        normalizar = { "Acrílico": "Acrilico", "Teflón": "Teflon"}

        self.mu_lista = []  # reinicia μ (1/cm) en orden de la tabla

        # Rellenar tabla
        for fila in range(self.tabla_linealidad_ct.rowCount()):
            mat_item = self.tabla_linealidad_ct.item(fila, 0)
            if not mat_item:
                continue
            nombre_tabla = mat_item.text().strip()
            nombre_json = normalizar.get(nombre_tabla, nombre_tabla)

            props = materiales_por_energia.get(nombre_json)

            # Escribe MeV
            self.tabla_linealidad_ct.setItem(fila, 1, QTableWidgetItem(energia_num))
            if not props:
                # Vaciar propiedades si el material no existe en JSON para esa energía
                self.tabla_linealidad_ct.setItem(fila, 2, QTableWidgetItem(""))
                self.tabla_linealidad_ct.setItem(fila, 3, QTableWidgetItem(""))
                self.tabla_linealidad_ct.setItem(fila, 4, QTableWidgetItem(""))
                continue

            # μ/ρ (cm²/g) ← poder_frenado
            mu_rho = props.get("poder_frenado", "")
            # ρ (g/cm³) ← densidad
            rho = props.get("densidad", "")
            # μ (1/cm) ← coeficiente_atenuacion
            mu = props.get("coeficiente_atenuacion", "")

            def fmt(x, nd=4):
                try:
                    return f"{float(x):.{nd}f}"
                except Exception:
                    return str(x) if x is not None else ""

            self.tabla_linealidad_ct.setItem(fila, 2, QTableWidgetItem(fmt(mu_rho)))
            self.tabla_linealidad_ct.setItem(fila, 3, QTableWidgetItem(fmt(rho)))
            self.tabla_linealidad_ct.setItem(fila, 4, QTableWidgetItem(fmt(mu)))

            # Guarda μ (1/cm) como float o None
            try:
                self.mu_lista.append(float(mu))
            except Exception:
                self.mu_lista.append(None)

        # Deja self.mu listo para usar en el análisis ↓
        self.mu = [m for m in self.mu_lista if m is not None]  # copia limpia
        
        # *** NUEVA LÓGICA: Si no hay HU en memoria pero sí valores CT en BD, cargarlos automáticamente ***
        if self.resultados_ct is None:
            valores_ct_cargados = self.cargar_valores_ct_desde_bd()
            if valores_ct_cargados:
                #print("🔄 Actualizando HU en tabla de linealidad con valores CT cargados desde BD")
                pass
        # Actualizar HU desde resultados CT (ya sea en memoria o recién cargados desde BD)
        if self.resultados_ct is not None:
            self.actualizar_hu_desde_resultados_ct()
        
        # Intentar actualizar la gráfica de Linealidad si ya hay HU
        self.try_actualizar_linealidad_ct()

    def actualizar_hu_desde_resultados_ct(self):
        """
        Copia a la columna 'HU' (col 5) de la tabla de linealidad los promedios HU
        obtenidos en self.resultados_ct (categoría 'Valores del número CT').
        """
        try:
            tabla = getattr(self, "tabla_linealidad_ct", None)
            resultado_completo = getattr(self, "resultados_ct", None)
            if tabla is None or resultado_completo is None:
                return

            # Extraer la lista de resultados
            if isinstance(resultado_completo, dict) and "resultados" in resultado_completo:
                resultados = resultado_completo["resultados"]
            else:
                # Compatibilidad hacia atrás si se pasa directamente la lista
                resultados = resultado_completo

            import unicodedata

            def norm(s: str) -> str:
                # Sirve para convertir (sin acentos y minúsculas)
                s = unicodedata.normalize("NFKD", s)
                s = s.encode("ascii", "ignore").decode("ascii")
                return s.strip().lower()

            # Construir mapa normalizado material -> promedio_hu
            hu_por_material = {}
            for res in resultados:
                mat = res.get("material")
                hu = res.get("promedio_hu")
                if mat is None or hu is None:
                    continue
                key = norm(str(mat))
                # Sinónimos/typos frecuentes
                if key == "derlin":
                    key = "delrin"
                hu_por_material[key] = hu

            # Rellenar la columna HU (índice 5) en la tabla
            for fila in range(tabla.rowCount()):
                mat_item = tabla.item(fila, 0)
                if not mat_item:
                    continue
                key = norm(mat_item.text())
                # Sinónimos con/ sin acento
                if key in ("acrilico", "acrilica"):
                    key = "acrilico"
                if key in ("teflon", "teflon."):
                    key = "teflon"
                if key == "derlin":
                    key = "delrin"

                hu = hu_por_material.get(key)
                if hu is None:
                    tabla.setItem(fila, 5, QTableWidgetItem(""))
                else:
                    try:
                        tabla.setItem(fila, 5, QTableWidgetItem(f"{float(hu):.1f}"))
                    except Exception:
                        tabla.setItem(fila, 5, QTableWidgetItem(str(hu)))
        except Exception as e:
            print("Error actualizando HU en tabla de linealidad:", e)

        # Si ya hay energía y μ cargados, intenta el análisis
        self.try_actualizar_linealidad_ct()

    def cargar_valores_ct_desde_bd(self):
        """
        Carga los valores CT desde la base de datos para la referencia actual
        y los asigna a self.resultados_ct si no existen en memoria.
        """
        try:
            # Solo cargar si no hay datos en memoria pero sí hay ref
            if self.resultados_ct is not None or not hasattr(self, 'ref') or not self.ref:
                return False
            
            from data.ManejoDatos.catphan_TAC.catphan_db import consultar_pruebas_disponibles, reconstruir_resultados_desde_bd
            
            # Verificar si hay datos de valores_ct disponibles en BD
            info_bd = consultar_pruebas_disponibles(self.ref)
            if not (info_bd and "categorias" in info_bd and "valores_ct" in info_bd["categorias"]):
                return False
            
            #print("📊 Cargando valores CT desde base de datos para usar en linealidad...")
            
            # Usar la función de reconstrucción para obtener los datos
            resultados_reconstruidos = reconstruir_resultados_desde_bd(
                self.ref, 
                categorias=['valores_ct']
            )
            
            if resultados_reconstruidos and 'valores_ct' in resultados_reconstruidos:
                # Asignar los resultados reconstruidos a la variable de instancia
                self.resultados_ct = resultados_reconstruidos['valores_ct']
                #print(f"✅ Valores CT cargados desde BD: {len(self.resultados_ct) if isinstance(self.resultados_ct, list) else 'datos disponibles'}")
                return True
            else:
                print("❌ No se pudieron reconstruir los valores CT desde BD")
                return False
                
        except Exception as e:
            print(f"❌ Error al cargar valores CT desde BD: {e}")
            return False

    def tabla_resultados_linealidad(self, resultados):
        """
        Formatea los resultados de linealidad del CT para mostrar en texto.
        """
        if not resultados:
            return "No hay resultados de linealidad disponibles."
        
        lines = []
        lines.append("Resultados de Linealidad del Número CT:")
        lines.append("-------------------------------------------------------------")
        lines.append("  Ecuación de la recta: HU = {:.4f} * (μ) + {:.4f}".format(
            resultados.get("pendiente", 0), resultados.get("intercepto", 0)))
        lines.append("  Coeficiente de determinación (R²): {:.4f}".format(resultados.get("r_squared", 0)))
        lines.append("  Referencia: {:.4f}".format(resultados.get("referencia", 0)))
        lines.append("  Escala de contraste = {:.9f}".format(resultados.get("escala_contraste", 0)))
        lines.append("-------------------------------------------------------------")
        return "\n".join(lines)
    
    # Intenta actualizar la gráfica de Linealidad del CT si hay energía, μ y HU
    def try_actualizar_linealidad_ct(self):
        """
        Si hay energía seleccionada, μ cargados y HU disponibles, calcula y muestra Linealidad del CT.
        """
        # Requisitos básicos
        if not hasattr(self, "tabla_linealidad_ct"):
            return None
        if not hasattr(self, "energia_select") or "Seleccionar Energía" in self.energia_select.currentText():
            return None

        # Asegurar que el canvas esté disponible
        try:
            self.graficar.setCurrentText("Linealidad del CT")
        except Exception as e:
            print(f" Error al cambiar tab: {e}")

        # Extrae μ y HU desde la tabla (en el mismo orden de filas)
        mu_vals = []
        hu_vals = []
        for fila in range(self.tabla_linealidad_ct.rowCount()):
            mu_item = self.tabla_linealidad_ct.item(fila, 4)  # μ (1/cm)
            hu_item = self.tabla_linealidad_ct.item(fila, 5)  # HU
            
            material_item = self.tabla_linealidad_ct.item(fila, 0)
            material = material_item.text() if material_item else f"Material_{fila}"
            
            try:
                mu_v = float(mu_item.text()) if mu_item and mu_item.text().strip() != "" else None
            except Exception:
                mu_v = None
            try:
                hu_v = float(hu_item.text()) if hu_item and hu_item.text().strip() not in ("", "None") else None
            except Exception:
                hu_v = None

            #print(f"  {material}: μ={mu_v}, HU={hu_v}")
            
            if (mu_v is not None) and (hu_v is not None):
                mu_vals.append(mu_v)
                hu_vals.append(hu_v)

        # Si no hay datos suficientes de HU, intentar cargar desde BD
        if len(hu_vals) < 2 and self.resultados_ct is None:
            print("🔍 Insuficientes datos HU, intentando cargar valores CT desde BD...")
            valores_ct_cargados = self.cargar_valores_ct_desde_bd()
            if valores_ct_cargados:
                print("🔄 Actualizando HU con valores CT cargados desde BD...")
                self.actualizar_hu_desde_resultados_ct()
                # Recalcular HU después de actualizar
                mu_vals.clear()
                hu_vals.clear()
                for fila in range(self.tabla_linealidad_ct.rowCount()):
                    mu_item = self.tabla_linealidad_ct.item(fila, 4)  # μ (1/cm)
                    hu_item = self.tabla_linealidad_ct.item(fila, 5)  # HU
                    
                    try:
                        mu_v = float(mu_item.text()) if mu_item and mu_item.text().strip() != "" else None
                        hu_v = float(hu_item.text()) if hu_item and hu_item.text().strip() not in ("", "None") else None
                        
                        if (mu_v is not None) and (hu_v is not None):
                            mu_vals.append(mu_v)
                            hu_vals.append(hu_v)
                    except Exception:
                        continue

        # Si todavía no hay datos suficientes, salir
        if len(mu_vals) < 2 or len(hu_vals) < 2 or len(mu_vals) != len(hu_vals):
            print(f" Datos insuficientes para linealidad: μ={len(mu_vals)}, HU={len(hu_vals)} (mínimo 2 puntos)")
            return None

        #print(f" Datos válidos encontrados: {len(mu_vals)} puntos")
        #print(f"   μ: {mu_vals}")
        #print(f"   HU: {hu_vals}")

        # Ejecuta el análisis y muestra resultados
        try:
            linealidad = linealidad_ct(datos=mu_vals, hu_promedio=hu_vals, visualizar=True, canvas=self.canvas_resultados)
            texto = self.tabla_resultados_linealidad(linealidad)
            self.resultados_texto.setText(texto)
            self.resultados_texto.setStyleSheet("""QLabel { font-family: 'Segoe UI'; font-size: 15px; 
                                                            color: #2c3e50; background-color: #f8f9fa;
                                                            padding: 10px; border: 1px solid #dee2e6;
                                                            border-radius: 5px; }""")
            
            #print(" Análisis de Linealidad del CT completado")
            #print(f"   Resultados: {linealidad}")
            self.resultados_linealidad_ct = linealidad  # Almacenar para guardado
            if linealidad:
                self._agregar_botones_guardado_post_analisis("linealidad_numero_ct")
            return linealidad
        except Exception as e:
            print(f" Error en analizar_linealidad_ct: {e}")
            import traceback
            traceback.print_exc()
            return None

    def reemplazar_resultados_texto_con_tabla(self, tabla_widget):
        """
        Reemplaza self.resultados_texto (QLabel) con una tabla (QTableWidget) en el layout activo.
        """
        try:
            if not hasattr(self, 'resultados_texto') or self.resultados_texto is None:
                print("❌ No hay resultados_texto para reemplazar")
                return
            
            # Obtener el layout padre del QLabel actual
            parent_layout = self.resultados_texto.parent().layout()
            if parent_layout is None:
                print("❌ No se pudo obtener el layout padre")
                return
            
            # Obtener la posición del QLabel en el layout
            index = -1
            for i in range(parent_layout.count()):
                item = parent_layout.itemAt(i)
                if item and item.widget() == self.resultados_texto:
                    index = i
                    break
            
            if index == -1:
                print("❌ No se encontró la posición del QLabel en el layout")
                return
            
            # Remover el QLabel actual
            self.resultados_texto.setParent(None)
            
            # Insertar la tabla en la misma posición
            parent_layout.insertWidget(index, tabla_widget)
            
            # Actualizar la referencia
            self.resultados_texto = tabla_widget
            
            #print("✅ Tabla insertada correctamente en lugar del QLabel")
            
        except Exception as e:
            print(f"❌ Error al reemplazar resultados_texto: {e}")
            import traceback
            traceback.print_exc()

    # Sucede cuando ya se elegió un corte, acá se llama a las funciones de análisis
    # y se muestran los resultados en consola
    def imagen_dicom_cargada(self, imagen_analisis, imagen_grafica, tam_px):
        """
        Maneja el evento cuando se carga una imagen DICOM.
        """
        # Funciones para escribir resultados en tablas de texto
        def tabla_resultados_espesor(resultados):
            if not resultados:
                return "No hay resultados de espesor disponibles."
            lines = []
            lines.append("🔍 RESULTADOS DE ESPESOR DE CORTE")
            lines.append("-" * 50)
            lines.append(f"  Espesor promedio: {resultados.get('espesor_promedio_mm', 'N/A')} mm")
            lines.append(f"  Espesor teórico: {resultados.get('espesor_teorico_mm', 'N/A')} mm") 
            lines.append(f"  Diferencia: {resultados.get('diferencia_mm', 'N/A')} mm")
            lines.append(f"  Factor corrección: {resultados.get('factor_correccion', 'N/A')}")
            
            # Mostrar espesores individuales
            espesores_ind = resultados.get("espesores_individuales", {})
            if espesores_ind:
                lines.append("")
                lines.append("  📏 Espesores individuales:")
                for direccion, valor in espesores_ind.items():
                    lines.append(f"    {direccion}: {valor} mm")

            lines.append("-" * 50)
            return "\n".join(lines)

        def tabla_resultados_tamano_pixel(resultados):
            if not resultados:
                return "No hay resultados de tamaño de pixel disponibles."
                
            lines = []
            lines.append("📐 RESULTADOS DE TAMAÑO DE PIXEL")
            lines.append("-" * 50)

            # Mostrar medidas individuales
            lines.append(f"  X: {resultados.get('X', 'N/A')} mm")
            lines.append(f"  Y: {resultados.get('Y', 'N/A')} mm")
            
            # Mostrar valor teórico y diferencias - TAMBIÉN VERIFICAR AQUÍ
            tam_px_teorico = resultados.get('tam_px_teorico')
            if tam_px_teorico is not None and isinstance(tam_px_teorico, (int, float)):
                lines.append(f"  Teórico: {tam_px_teorico:.3f} mm")
            else:
                lines.append(f"  Teórico: {tam_px_teorico if tam_px_teorico is not None else 'N/A'}")
                
            diferencia_x = resultados.get('diferencia_x')
            if diferencia_x is not None and isinstance(diferencia_x, (int, float)):
                lines.append(f"  Diferencia X: {diferencia_x:.3f} mm")
            else:
                lines.append(f"  Diferencia X: {diferencia_x if diferencia_x is not None else 'N/A'}")
                
            diferencia_y = resultados.get('diferencia_y')
            if diferencia_y is not None and isinstance(diferencia_y, (int, float)):
                lines.append(f"  Diferencia Y: {diferencia_y:.3f} mm")
            else:
                lines.append(f"  Diferencia Y: {diferencia_y if diferencia_y is not None else 'N/A'}")

            error_pct = resultados.get('error_pct')
            lines.append(f"  Error porcentual: {error_pct:.3f}%" if error_pct is not None else "  Error porcentual: N/A")
            
            lines.append("-" * 50)
            return "\n".join(lines)

        def tabla_resultados_resolucion_contraste(resultados):
            """
            Crea una tabla simplificada mostrando solo los círculos visibles
            con su diámetro y valor de contraste/visibilidad.
            """
            # Obtener datos de los resultados
            resultados_roi = resultados.get("resultados_roi", {})
            resumen = resultados.get("resumen", {})
            
            # Filtrar solo ROIs visibles según el método recomendado (visibilidad)
            rois_visibles = {}
            for nombre, roi_data in resultados_roi.items():
                if roi_data.get("pasa_visibilidad_lim", False):
                    rois_visibles[nombre] = roi_data
            
            # Crear tabla si hay ROIs visibles
            if rois_visibles:
                headers = ["Diámetro (mm)", "Contraste", "Visibilidad", "Estado"]
                tabla_contraste = QTableWidget()
                tabla_contraste.setColumnCount(len(headers))
                tabla_contraste.setRowCount(len(rois_visibles))
                tabla_contraste.setHorizontalHeaderLabels(headers)
                
                # Configurar estilo de la tabla
                tabla_contraste.setAlternatingRowColors(True)
                tabla_contraste.setSelectionBehavior(QTableWidget.SelectRows)
                tabla_contraste.setEditTriggers(QTableWidget.NoEditTriggers)
                tabla_contraste.setStyleSheet("""
                    QTableWidget {
                        gridline-color: #d0d0d0;
                        background-color: white;
                        font-family: 'Segoe UI';
                        color: #2c3e50;
                        alternate-background-color: #f5f5f5;
                    }
                    QHeaderView::section {
                        background-color: #e8f4f8;
                        border: 1px solid #d0d0d0;
                        padding: 8px;
                        font-weight: bold;
                        color: #34495e;
                    }
                """)
                
                # Configurar redimensionamiento de columnas
                for i in range(len(headers)):
                    tabla_contraste.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
                
                # Llenar datos - ordenar por diámetro descendente
                rois_ordenados = sorted(rois_visibles.items(), 
                                      key=lambda x: x[1].get("diametro_mm", 0), 
                                      reverse=True)
                
                for i, (nombre, roi_data) in enumerate(rois_ordenados):
                    diametro = roi_data.get("diametro_mm", "N/A")
                    contraste = roi_data.get("contraste_michelson", "N/A")
                    visibilidad = roi_data.get("visibilidad_lim", "N/A")
                    
                    # Formatear valores
                    diametro_str = f"{diametro}" if diametro != "N/A" else "N/A"
                    contraste_str = f"{contraste:.3f}" if contraste != "N/A" and contraste is not None else "N/A"
                    visibilidad_str = f"{visibilidad:.3f}" if visibilidad != "N/A" and visibilidad is not None else "N/A"
                    
                    # Insertar datos con centrado
                    item_diametro = QTableWidgetItem(diametro_str)
                    item_diametro.setTextAlignment(Qt.AlignCenter)
                    tabla_contraste.setItem(i, 0, item_diametro)
                    
                    item_contraste = QTableWidgetItem(contraste_str)
                    item_contraste.setTextAlignment(Qt.AlignCenter)
                    tabla_contraste.setItem(i, 1, item_contraste)
                    
                    item_visibilidad = QTableWidgetItem(visibilidad_str)
                    item_visibilidad.setTextAlignment(Qt.AlignCenter)
                    tabla_contraste.setItem(i, 2, item_visibilidad)
                    
                    # Estado (siempre visible ya que filtramos)
                    item_estado = QTableWidgetItem("✓ Visible")
                    item_estado.setTextAlignment(Qt.AlignCenter)
                    item_estado.setForeground(QColor("#27ae60"))  # Verde
                    font_estado = item_estado.font()
                    font_estado.setBold(True)
                    item_estado.setFont(font_estado)
                    tabla_contraste.setItem(i, 3, item_estado)
                
                # Ajustar altura
                tabla_contraste.resizeRowsToContents()
                tabla_contraste.setMaximumHeight(250)
                
                # Crear widget contenedor con información adicional
                contenedor = QWidget()
                layout_contenedor = QVBoxLayout(contenedor)
                
                # Agregar información de resumen
                info_resumen = QLabel(
                    f"✅ Círculos detectados: {len(rois_visibles)}/{resumen.get('total_rois', 'N/A')} | "
                    f"Método: Visibilidad (Rose) | "
                    f"Umbral: {resumen.get('visibility_threshold', 'N/A')}"
                )
                info_resumen.setAlignment(Qt.AlignCenter)
                info_resumen.setStyleSheet("""
                    QLabel {
                        color: #27ae60;
                        font-size: 12px;
                        font-weight: bold;
                        padding: 8px;
                        background-color: #eafaf1;
                        border: 2px solid #a9dfbf;
                        border-radius: 6px;
                        margin-bottom: 5px;
                    }
                """)
                
                layout_contenedor.addWidget(info_resumen)
                layout_contenedor.addWidget(tabla_contraste)
                layout_contenedor.setContentsMargins(0, 0, 0, 0)
                layout_contenedor.setSpacing(5)
                
                return contenedor
            else:
                # Si no hay ROIs visibles, crear un widget con mensaje
                no_visible_widget = QWidget()
                layout = QVBoxLayout(no_visible_widget)
                
                mensaje = QLabel("⚠️ No se detectaron círculos de contraste visibles")
                mensaje.setAlignment(Qt.AlignCenter)
                mensaje.setStyleSheet("""
                    QLabel {
                        color: #e74c3c;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 20px;
                        background-color: #fdf2f2;
                        border: 2px solid #fadbd8;
                        border-radius: 8px;
                    }
                """)
                
                # Agregar información del resumen
                info_resumen = QLabel(
                    f"Método: Visibilidad (Rose) | "
                    f"Umbral: {resumen.get('visibility_threshold', 'N/A')} | "
                    f"ROIs analizados: {resumen.get('total_rois', 'N/A')}"
                )
                info_resumen.setAlignment(Qt.AlignCenter)
                info_resumen.setStyleSheet("""
                    QLabel {
                        color: #7f8c8d;
                        font-size: 11px;
                        padding: 10px;
                    }
                """)
                
                layout.addWidget(mensaje)
                layout.addWidget(info_resumen)
                no_visible_widget.setMaximumHeight(120)
                
                return no_visible_widget

        def tabla_resultados_resolucion_espacial(resultados):
            headers = ["Región", "lp/cm", "N° Picos","N° Valles", "Gap Size (cm)"]
            tabla_ct = QTableWidget()
            
            # Obtener datos válidos primero
            region_results = resultados.get("region_results", {})
            regiones = {"region 1": "Región 1", "region 2": "Región 2", "region 3": "Región 3", "region 4": "Región 4",
                        "region 5": "Región 5", "region 6": "Región 6", "region 7": "Región 7", "region 8": "Región 8"}
            
            # FILTRAR SOLO REGIONES CON DATOS VÁLIDOS
            regiones_validas = {}
            max_lp_mm = -1
            region_maxima = None
            
            for region, res in region_results.items():
                lp_mm = res.get('lp/cm', -1)
                num_peaks = res.get("n_peaks_used", "N/A")
                num_valleys = res.get("n_valleys_used", "N/A")
                gap_size_cm = res.get("gap_size_cm", "N/A")
                
                # Verificar que todos los datos sean válidos (no N/A) y que lp/mm sea un número
                datos_completos = (
                    isinstance(lp_mm, (int, float)) and lp_mm > 0 and
                    num_peaks != "N/A" and isinstance(num_peaks, (int, float)) and
                    num_valleys != "N/A" and isinstance(num_valleys, (int, float)) and
                    gap_size_cm != "N/A" and isinstance(gap_size_cm, (int, float))
                )
                
                # SOLO AGREGAR SI TIENE DATOS COMPLETOS
                if datos_completos:
                    regiones_validas[region] = res
                    if lp_mm > max_lp_mm:
                        max_lp_mm = lp_mm
                        region_maxima = region
            
            #print(f"Regiones con datos válidos: {list(regiones_validas.keys())}")
            #print(f"Región máxima detectada: {region_maxima} con lp/mm = {max_lp_mm}")
            
            # Usar solo las regiones válidas para crear la tabla
            tabla_ct.setColumnCount(len(headers))
            tabla_ct.setRowCount(len(regiones_validas))  # ← Solo regiones válidas
            tabla_ct.setHorizontalHeaderLabels(headers)
            
            # Configurar el estilo de la tabla
            tabla_ct.setAlternatingRowColors(True)
            tabla_ct.setSelectionBehavior(QTableWidget.SelectRows)
            tabla_ct.setEditTriggers(QTableWidget.NoEditTriggers)
            tabla_ct.setStyleSheet("""
                QTableWidget {
                    gridline-color: #d0d0d0;
                    background-color: white;
                    font-family: 'Segoe UI';
                    color: #2c3e50;
                    alternate-background-color: #f5f5f5;
                }
                QHeaderView::section {
                    background-color: #e8f4f8;
                    border: 1px solid #d0d0d0;
                    padding: 8px;
                    font-weight: bold;
                    color: #34495e;
                }
            """)
            
            # Configurar redimensionamiento de columnas
            for i in range(len(headers)):
                tabla_ct.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

            # Llenar datos SOLO CON REGIONES VÁLIDAS
            for i, (region, res) in enumerate(regiones_validas.items()):
                lp_mm = res.get('lp/cm','N/A')
                num_peaks = res.get("n_peaks_used", "N/A")
                num_valleys = res.get("n_valleys_used", "N/A")
                gap_size_cm = res.get("gap_size_cm", "N/A")
                
                # Formatear valores (ya sabemos que son válidos)
                lp_mm_str = f"{round(lp_mm, 2)}"
                num_peaks_str = str(num_peaks)
                num_valleys_str = str(num_valleys)
                gap_size_str = f"{round(gap_size_cm, 2)}"

                # Insertar datos en la tabla CON CENTRADO
                item_region = QTableWidgetItem(str(regiones.get(region, region)))
                item_region.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 0, item_region)
                
                item_lp = QTableWidgetItem(lp_mm_str)
                item_lp.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 1, item_lp)
                
                item_peaks = QTableWidgetItem(num_peaks_str)
                item_peaks.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 2, item_peaks)
                
                item_valleys = QTableWidgetItem(num_valleys_str)
                item_valleys.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 3, item_valleys)
                
                item_gap = QTableWidgetItem(gap_size_str)
                item_gap.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 4, item_gap)

                # RESALTAR SOLO LA REGIÓN MÁXIMA
                if region == region_maxima:
                    print(f"Resaltando región: {region} (fila {i}) - MÁXIMA resolución con datos completos")
                    for col in range(len(headers)):
                        item = tabla_ct.item(i, col)
                        if item is not None:
                            item.setBackground(QColor("#9aedc8"))  # Verde claro
                            item.setFont(QFont("Segoe UI", weight=QFont.Bold))
                            item.setForeground(QColor("#24c950"))  # Texto verde

            # Ajustar altura de filas al contenido
            tabla_ct.resizeRowsToContents()
            tabla_ct.setMaximumHeight(300)
            return tabla_ct

        def tabla_resultados_ct(resultado_completo):
            """
            Crea una QTableWidget con los resultados de Valores CT.
            """
            # Extraer la lista de resultados del diccionario
            if isinstance(resultado_completo, dict) and "resultados" in resultado_completo:
                resultados = resultado_completo["resultados"]
            else:
                # Compatibilidad hacia atrás si se pasa directamente la lista
                resultados = resultado_completo
                
            headers = ["Material", "Promedio HU", "Rango HU Ref.", "Error Abs. (HU)", "Rango"]
            tabla_ct = QTableWidget()
            tabla_ct.setColumnCount(len(headers))
            tabla_ct.setRowCount(len(resultados) - 1) 
            tabla_ct.setHorizontalHeaderLabels(headers)
            
            # Configurar el estilo de la tabla
            tabla_ct.setAlternatingRowColors(True)
            tabla_ct.setSelectionBehavior(QTableWidget.SelectRows)
            tabla_ct.setEditTriggers(QTableWidget.NoEditTriggers)
            tabla_ct.setStyleSheet("""
                QTableWidget {
                    gridline-color: #d0d0d0;
                    background-color: white;
                    font-family: 'Segoe UI';
                    color: #2c3e50;
                    alternate-background-color: #f5f5f5;
                }
                QHeaderView::section {
                    background-color: #e8f4f8;
                    border: 1px solid #d0d0d0;
                    padding: 8px;
                    font-weight: bold;
                    color: #34495e;
                }
            """)
            
            # Configurar redimensionamiento de columnas
            for i in range(len(headers)):
                tabla_ct.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

            materiales = {"Acrilico": "Acrílico", "Teflon": "Teflón"}

            # Llenar datos CON CENTRADO
            for i, res in enumerate(resultados[:-1]):
                material = materiales.get(str(res.get("material", "")), str(res.get("material", "")))
                promedio = res.get("promedio_hu", "")
                rango = res.get("rango_hu", ["N/A", "N/A"])
                err_abs = res.get("error_abs", "N/A")
                err_rel = res.get("error_rel", "N/A")
                
                # Formatear valores
                promedio_str = f"{round(promedio, 1)}" if promedio else "N/A"
                rango_str = f"{rango[0]} a {rango[1]}" if rango[0] is not None and rango[1] is not None else "N/A"
                err_abs_str = str(err_abs) if err_abs is not None else "N/A"
                err_rel_str = str(err_rel) if err_rel is not None else "N/A"

                # Insertar datos en la tabla CON CENTRADO
                item_material = QTableWidgetItem(material)
                item_material.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 0, item_material)
                
                item_promedio = QTableWidgetItem(promedio_str)
                item_promedio.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 1, item_promedio)
                
                item_rango = QTableWidgetItem(rango_str)
                item_rango.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 2, item_rango)
                
                item_err_abs = QTableWidgetItem(err_abs_str)
                item_err_abs.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 3, item_err_abs)
                
                item_err_rel = QTableWidgetItem(err_rel_str)
                item_err_rel.setTextAlignment(Qt.AlignCenter)
                tabla_ct.setItem(i, 4, item_err_rel)

            # Ajustar altura de filas al contenido
            tabla_ct.resizeRowsToContents()
            tabla_ct.setMaximumHeight(300)
            
            return tabla_ct
        
        def tabla_resultados_uniformidad(uniformidad):
            headers = ["Posición", "Promedio HU", "Desviación"]
            tabla_un = QTableWidget()
            
            # Filtrar datos válidos excluyendo "Uniformidad"
            datos_validos = {k: v for k, v in uniformidad.items() 
                            if k != "Uniformidad" and isinstance(v, dict) and 
                            "promedio_hu" in v and "desviacion" in v and 
                            v["promedio_hu"] is not None}
            
            tabla_un.setColumnCount(len(headers))
            tabla_un.setRowCount(len(datos_validos) + 3)  # +3 para filas adicionales
            tabla_un.setHorizontalHeaderLabels(headers)

            # Configurar el estilo de la tabla
            tabla_un.setAlternatingRowColors(True)
            tabla_un.setSelectionBehavior(QTableWidget.SelectRows)
            tabla_un.setEditTriggers(QTableWidget.NoEditTriggers)
            tabla_un.setStyleSheet("""
                QTableWidget {
                    gridline-color: #d0d0d0;
                    background-color: white;
                    font-family: 'Segoe UI';
                    color: #2c3e50;
                    alternate-background-color: #f5f5f5;
                }
                QHeaderView::section {
                    background-color: #e8f4f8;
                    border: 1px solid #d0d0d0;
                    padding: 8px;
                    font-weight: bold;
                    color: #34495e;
                }
            """)
            
            # Configurar redimensionamiento de columnas
            for i in range(len(headers)):
                tabla_un.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
            
            # Llenar datos usando índices enteros
            fila_actual = 0
            for pos, res in datos_validos.items():
                item_pos = QTableWidgetItem(str(pos))
                item_pos.setTextAlignment(Qt.AlignCenter)
                tabla_un.setItem(fila_actual, 0, item_pos)
                
                item_promedio = QTableWidgetItem(str(round(res["promedio_hu"], 1)))
                item_promedio.setTextAlignment(Qt.AlignCenter)
                tabla_un.setItem(fila_actual, 1, item_promedio)
                
                item_desviacion = QTableWidgetItem(str(round(res["desviacion"], 1)))
                item_desviacion.setTextAlignment(Qt.AlignCenter)
                tabla_un.setItem(fila_actual, 2, item_desviacion)
                
                fila_actual += 1

            # Agregar datos de uniformidad global si existe
            if "Uniformidad" in uniformidad:
                u = uniformidad["Uniformidad"]
                inu_pct = u.get("integral_non_uniformity_pct")
                ui_max = u.get("uniformity_index_max")

                # ---------------------------- Fila para "No uniformidad integral" ----------------------------
                tabla_un.setSpan(fila_actual, 0, 1, 3)  # Combinar columnas 0 y 1
                item_inu = QTableWidgetItem(f"No uniformidad integral: {inu_pct:.2f}%" if isinstance(inu_pct, (int, float)) else "No uniformidad integral: N/A")
                item_inu.setTextAlignment(Qt.AlignCenter)
                # Poner el texto en negrita y azul:
                font_inu = item_inu.font()
                font_inu.setBold(True)
                item_inu.setFont(font_inu)
                item_inu.setForeground(QColor("#00B2BC"))  # Azul
                tabla_un.setItem(fila_actual, 0, item_inu)

                fila_actual += 1
                # -------------------------------------------------------------------------------------------

                # ---------------------------- Fila para "Índice de uniformidad" ----------------------------
                tabla_un.setSpan(fila_actual, 0, 1, 3)  # Combinar columnas 0 y 1
                item_ui = QTableWidgetItem(f"Índice de uniformidad (|UI|max): {ui_max:.2f}%" if isinstance(ui_max, (int, float)) else "Índice de uniformidad (|UI|max): N/A")
                item_ui.setTextAlignment(Qt.AlignCenter)
                tabla_un.setItem(fila_actual, 0, item_ui)
                font_ui = item_ui.font()
                font_ui.setBold(True)
                item_ui.setFont(font_ui)
                item_ui.setForeground(QColor("#00B2BC"))  # Azul
                fila_actual += 1

                # -------------------------------------------------------------------------------------------

                # Fila adicional con información extra (máx diferencia, desviación global, pasa)
                tabla_un.setSpan(fila_actual, 0, 1, 3)  # Combinar las 3 columnas
                info_extra = (f"Máx diferencia: {u.get('max_diferencia','N/A')} HU | "
                            f"Desv. global: {u.get('desviacion_global','N/A')} | "
                            f"Pasa (UI/INU): {u.get('pasa_global','N/A')}")
                item_extra = QTableWidgetItem(info_extra)
                item_extra.setTextAlignment(Qt.AlignCenter)
                font_extra = item_extra.font()
                font_extra.setBold(True)
                item_extra.setFont(font_extra)
                item_extra.setForeground(QColor("#00B2BC"))  # Azul
                # -------------------------------------------------------------------------------------------

                tabla_un.setItem(fila_actual, 0, item_extra)
                
            tabla_un.setMaximumHeight(300)  # Limitar altura máxima
            return tabla_un

        # Verificar si el visualizador principal tiene volumen cargado
        visualizador_principal = getattr(self, 'visualizador_principal', None)
        if not visualizador_principal or not visualizador_principal.vol:
            print("Error: No se pudo cargar el volumen DICOM en el visualizador principal.")
            return

        if imagen_analisis is None or imagen_grafica is None or tam_px is None:
            print("Error: No se pudo procesar el corte seleccionado.")
            return
        # Determinar la categoría asociada al corte

        for categoria, widget in self.pruebas_categorias.items():
            if widget is not None and widget.isVisible():  # Verifica si el widget está visible
                #print(f"El corte pertenece a la categoría: {categoria}")
                
                

                # -------------------------------    ESPESOR DE CORTE         ------------------------------- #
                if categoria == 'espesor':
                    self.graficar.setCurrentText("Espesor de corte")
                    #print("\nProcesando corte para la categoría de ESPESOR DE CORTE")

                    resultados_espesor = espesor_corte(imagen_grafica, imagen_analisis, tam_px, visualizar=True, 
                                                                canvas=self.canvas_resultados)
                    
                    self.resultados_espesor = resultados_espesor  # Almacenar para guardado
                    error = (abs((self.espesor_corte_val) - resultados_espesor.get("espesor_promedio_mm", None)) / self.espesor_corte_val) * 100 if self.espesor_corte_val and resultados_espesor.get("espesor_promedio_mm", None) else None
                    espesor_teorico_mm = self.espesor_corte_val if self.espesor_corte_val else None
                    resultados_espesor['espesor_teorico_mm'] = espesor_teorico_mm
                    resultados_espesor['diferencia_mm'] = round(abs(espesor_teorico_mm - resultados_espesor.get("espesor_promedio_mm", 0)), 3) if espesor_teorico_mm else None
                    texto = tabla_resultados_espesor(resultados_espesor)
                    self.resultados_texto.setText(texto)
                    self.resultados_texto.setStyleSheet("""QLabel{ font-family: 'Segoe UI'; font-size: 15px; 
                                                                color: #2c3e50; background-color: #f8f9fa;
                                                                padding: 10px; border: 1px solid #dee2e6;
                                                                border-radius: 5px; }""")
                    #print(texto)
                    #print(f"Espesor de corte esperado: {self.espesor_corte_val} mm, Espesor calculado: {resultados_espesor.get('espesor_promedio_mm', None)} mm, Error relativo: {error:.2f}%")
                    # Agregar botones de guardado después del análisis completado
                    self._crear_boton_guardado_individual(categoria)

                # -------------------------------    TAMAÑO DE PIXEL          ------------------------------- #
                elif categoria == 'tamaño_pixel':
                    self.graficar.setCurrentText("Tamaño de Pixel")
                    #print("\nProcesando corte para la categoría de TAMAÑO DE PIXEL")

                    resultados_tamano_pixel = tamano_pixel(imagen_grafica, tam_px, visualizar=True, canvas=self.canvas_resultados)
                    self.resultados_tamano_pixel = resultados_tamano_pixel  # Almacenar para guardado
                    self.tam_px_teorico = tam_px  # Almacenar valor teórico

                    # Calcular promedio de los valores medidos (x_arriba, x_abajo, y_izquierda, y_derecha)
                    valores_medidos = [v for v in resultados_tamano_pixel.values() if isinstance(v, (int, float))]
                    error_x = abs(round(tam_px, 3) - round(valores_medidos[0], 3)) if tam_px and valores_medidos[0] else None
                    error_y = abs(round(tam_px, 3) - round(valores_medidos[1], 3)) if tam_px and valores_medidos[1] else None
                    import numpy as np
                    error = (abs(np.mean(valores_medidos) - (round(tam_px, 3))) / (round(tam_px, 3))) * 100 if tam_px and valores_medidos else None
                    
                    self.resultados_tamano_pixel['diferencia_x'] = error_x
                    self.resultados_tamano_pixel['diferencia_y'] = error_y
                    self.resultados_tamano_pixel['tam_px_teorico'] = round(tam_px, 3)
                    self.resultados_tamano_pixel['error_pct'] = error

                    texto = tabla_resultados_tamano_pixel(resultados_tamano_pixel)
                    self.resultados_texto.setText(texto)
                    self.resultados_texto.setStyleSheet("""QLabel{ font-family: 'Segoe UI'; font-size: 15px; 
                                                                color: #2c3e50; background-color: #f8f9fa;
                                                                padding: 10px; border: 1px solid #dee2e6;
                                                                border-radius: 5px; }""")
                    #print(texto)
                    #print(f"Tamaño pixel teórico: {round(tam_px, 3)} mm, Error relativo: {error:.2f}%" if error else "Error: No se pudo calcular")
                    # Agregar botones de guardado después del análisis completado
                    self._agregar_botones_guardado_post_analisis(categoria)

                # -------------------------------    RESOLUCIÓN ESPACIAL      ---------------------------- #
                elif categoria == 'resolucion_espacial':
                    self.graficar.setCurrentText("Resolución Espacial")
                    #print("Procesando corte para la categoría de RESOLUCIÓN DE ESPACIAL")

                    resultados_resolucion = resolucion_espacial(imagen_grafica, tam_px, visualizar=True, canvas=self.canvas_resultados)
                    self.resultados_resolucion_espacial = resultados_resolucion  # Almacenar para guardado
                    texto = tabla_resultados_resolucion_espacial(resultados_resolucion)
                    self.reemplazar_resultados_texto_con_tabla(texto)
                    # Agregar botones de guardado después del análisis completado
                    self._agregar_botones_guardado_post_analisis(categoria)

                # -------------------------------    RESOLUCIÓN DE CONTRASTE  ---------------------------- #
                elif categoria == 'resolucion_contraste':
                    self.graficar.setCurrentText("Resolución de Contraste")
                    
                    # 1. Crear GeometriaCatphan UNA sola vez
                    from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
                    catphan = GeometriaCatphan(imagen_grafica, tam_px)
                    
                    # 2. Abrir posicionador — bloquea hasta que el usuario confirme o cancele
                    from data.ManejoDatos.catphan_TAC.posicionador_manual import PosicionadorDialog
                    dlg = PosicionadorDialog(catphan, imagen_grafica, parent=self)
                    
                    resultado_dlg = dlg.exec_()
                    
                    visibilidad = None
                    if resultado_dlg == QDialog.Accepted:
                        visibilidad = dlg.visibilidad_manual
                    # No importa si acepta o cancela: los offsets son 0 si no tocó nada
                    # Si aceptó, catphan.offset_x/y/ang tienen los ajustes del usuario
                    
                    # 3. Pasar la instancia ya ajustada a resolucion_contraste
                    resolucion = resolucion_contraste(
                        imagen_grafica, imagen_analisis, tam_px,
                        catphan=catphan,          # ← instancia con offsets aplicados
                        visibilidad_manual=dlg.visibilidad_manual,
                        visualizar=True,
                        canvas=self.canvas_resultados,
                        cnr_lim=1.0,
                        visibilidad_lim=0.1
                    )
                    self.resultados_resolucion_contraste = resolucion
                    imprimir_resultados_contraste_bajo(resolucion)
                    tabla_widget = tabla_resultados_resolucion_contraste(resolucion)
                    self.reemplazar_resultados_texto_con_tabla(tabla_widget)
                    self._agregar_botones_guardado_post_analisis(categoria)

                # -------------------------------    VALORES DEL NÚMERO CT    ------------------------------- #
                elif categoria == 'valores_numero_ct':
                    self.graficar.setCurrentText("Valores CT")
                
                    # 1. Construir geometría CT UNA sola vez
                    from data.ManejoDatos.catphan_TAC.posicionador_manual import (
                        GeometriaCatphanCT,
                        PosicionadorDialogCT,
                    )
                    catphan_ct = GeometriaCatphanCT(imagen_grafica, tam_px)
                
                    # 2. Abrir posicionador — bloquea hasta confirmar o cancelar
                    dlg = PosicionadorDialogCT(catphan_ct, imagen_grafica, parent=self)
                    dlg.exec_()
                    # Si el usuario canceló o no tocó nada, los offsets son 0.0 → sin efecto.
                    # Si confirmó, catphan_ct.offset_x/y/ang contienen los ajustes.
                
                    # 3. Pasar instancia ya ajustada al análisis
                    self.resultados_ct = valor_numero_ct(
                        imagen_grafica,
                        imagen_analisis,
                        tam_px,
                        catphan=catphan_ct,        # ← instancia con offsets aplicados
                        visualizar=True,
                        canvas=self.canvas_resultados,
                    )
                
                    tabla_widget = tabla_resultados_ct(self.resultados_ct)
                    self.reemplazar_resultados_texto_con_tabla(tabla_widget)
                    self.actualizar_hu_desde_resultados_ct()
                    self._agregar_botones_guardado_post_analisis(categoria)
                
                


                # -------------------------------    LINEALIDAD DEL NÚMERO CT ------------------------------- #
                elif categoria == 'linealidad_numero_ct':
                    #print("*** ENTRANDO EN CONDICIÓN DE LINEALIDAD CT ***")
                    #print(f"Canvas disponible: {hasattr(self, 'canvas_resultados')}")
                    #print(f"ResultadosTexto disponible: {hasattr(self, 'resultados_texto')}")
                    
                    resultados_linealidad = self.try_actualizar_linealidad_ct()
                    # Agregar botones de guardado después del análisis completado

                    if resultados_linealidad:
                        self._agregar_botones_guardado_post_analisis(categoria)
                    
                # -------------------------------    UNIFORMIDAD Y RUIDO      ------------------------------- #
                elif categoria == 'uniformidad_ruido':
                    self.graficar.setCurrentText("Uniformidad y Ruido")
                    #print("Procesando corte para la categoría de UNIFORMIDAD Y RUIDO")
                    uniformidad_resultados = uniformidad(imagen_grafica, imagen_analisis, tam_px, visualizar=True, 
                                                        canvas=self.canvas_resultados)
                    self.resultados_uniformidad = uniformidad_resultados  # Almacenar para guardado
                    
                    # Reemplazar el QLabel con QTableWidget
                    tabla_widget = tabla_resultados_uniformidad(uniformidad_resultados)
                    self.reemplazar_resultados_texto_con_tabla(tabla_widget)
                    #print("Tabla de uniformidad creada y mostrada")
                
                # Agregar botones de guardado después del análisis completado
                self._agregar_botones_guardado_post_analisis(categoria)
                break
        else:
            print("No se encontró una categoría asociada al corte seleccionado.")
    
    def button_click(self):
        self.graficar.currentTextChanged.connect(self.createTab)
        pass

    def createTab(self, text):
        #print(f'\nEntro a createTab con {text} en la clase {self.__class__.__name__}')
        if text == 'Seleccionar...' or text == 'Ver resultados de...':
            return

        if text in self.dynamic_tabs:
            self._activar_tab_existente(text)
            return
        
        # Crear nueva pestaña
        tab_info = self._crear_nueva_tab(text)
        
        # NUEVA LÓGICA: Verificar si HAY DATOS PARA ESTA PESTAÑA ESPECÍFICA
        categoria, info_categoria = CategoriasMapping.categoria_por_pestaña(text)
        
        if categoria and self.gestor_reconstruccion.tiene_datos_categoria_especifica(categoria):
            # Esta pestaña específica tiene datos → Cargar desde BD
            #print(f"📊 Pestaña {text} tiene datos en BD - Cargando...")
            self.gestor_reconstruccion.reconstruir_categoria_async(text, tab_info)
        elif self.estado_actual.es_modo_carga_nueva():
            # No hay datos para esta pestaña → Agregar controles de guardado
            #print(f"🆕 Pestaña {text} sin datos - Agregando controles guardado...")
            self._agregar_controles_guardado(text, tab_info)
        else:
            #print(f"⚪ Pestaña {text} - Sin acción específica")
            pass
    def mapear_a_cortes(self, visualizador):
        try:
            print("mapeoooooooooooooooooooooooo")
            cortes = visualizador.cortes
            resultados = visualizador.resultados
            mapeo = {"CTP404" : "ln_espesor", "CTP515" : "ln_contrast_res", "CTP528": "ln_resolucion_esp", "CTP486": "ln_uni"}
            for nombre_modulo, nombre_widget in mapeo.items():
                widget = getattr(self, nombre_widget, None)
                print(nombre_widget)
                if widget is None:
                    print(f"widget {widget} no encontrado")
                    continue
                idx_corte = cortes.get(nombre_modulo)
                
                if idx_corte is not None:
                    widget.setText(str(idx_corte+1))
                else:
                    resultado = resultados.get(nombre_modulo)
                    if resultado and resultado.error:
                        widget.setText(f"Error: {resultado.error}")
                    else: 
                        widget.setText("No detectado")
        except Exception as e:
            print(", error ", e)
    def _activar_tab_existente(self, text):
        """Activa una pestaña que ya existe"""
        index = self.tab_widget.indexOf(self.dynamic_tabs[text])
        self.tab_widget.setCurrentIndex(index)

    def _crear_nueva_tab(self, text):
        """Crea una nueva pestaña con su layout básico"""
        new_tab = QWidget()
        new_tab_layout = QVBoxLayout()
        new_tab.setLayout(new_tab_layout)

        # Título
        titulo = QLabel(f"Resultados de {text}")
        titulo.setAlignment(Qt.AlignCenter)
        new_tab_layout.addWidget(titulo)

        # Canvas y toolbar
        mpl = get_matplotlib_components()
        Figure = mpl['Figure']
        FigureCanvas = mpl['FigureCanvas']
        NavigationToolbar = mpl['NavigationToolbar']
        
        canvas_resultados = FigureCanvas(Figure(figsize=(8, 5)))
        canvas_resultados.setMinimumHeight(400)
        canvas_resultados.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        new_tab_layout.addWidget(canvas_resultados, stretch=2)

        toolbar_tac = NavigationToolbar(canvas_resultados, self)
        new_tab_layout.addWidget(toolbar_tac)

        # Label para resultados de texto
        resultados_texto = QLabel()
        resultados_texto.setWordWrap(True)
        new_tab_layout.addWidget(resultados_texto, stretch=0)

        # Agregar pestaña al widget
        self.tab_widget.addTab(new_tab, text)
        self.dynamic_tabs[text] = new_tab
        self.tab_widget.setCurrentWidget(new_tab)

        # Guardar referencias
        self.canvas_resultados = canvas_resultados
        self.toolbar_tac = toolbar_tac
        self.resultados_texto = resultados_texto

        return {
            'tab': new_tab,
            'layout': new_tab_layout,
            'canvas': canvas_resultados,
            'toolbar': toolbar_tac,
            'label': resultados_texto,
            'titulo': titulo
        }

    def _agregar_controles_guardado(self, nombre_pestaña, tab_info):
        """Agrega controles de guardado para modo de carga nueva"""
        botones_layout = QHBoxLayout()
        
        # Botón de guardado individual específico para esta pestaña
        boton_individual = self._crear_boton_guardado_individual(nombre_pestaña)
        if boton_individual:
            botones_layout.addWidget(boton_individual)
            tab_info['layout'].addLayout(botones_layout)
    
    def _agregar_botones_guardado_post_analisis(self, categoria):
        """
        Agrega botones de guardado a la pestaña activa después de completar un análisis
        """
        try:    
            # Obtener la pestaña actual
            current_tab = self.tab_widget.currentWidget()
            
            # Obtener el layout de la pestaña actual
            tab_layout = current_tab.layout()
            
            # Verificar si ya existe un layout de botones para evitar duplicados
            for i in range(tab_layout.count()):
                item = tab_layout.itemAt(i)
                if item and isinstance(item, QHBoxLayout):
                    # Buscar si ya hay botones de guardado
                    for j in range(item.count()):
                        widget = item.itemAt(j).widget() if item.itemAt(j) else None
                        if widget and isinstance(widget, QPushButton) and "💾 Guardar" in widget.text():
                            return
            
            # Crear layout para botones si no existe
            botones_layout = QHBoxLayout()
            
            # Mapear categoria interna a nombre de pestaña para crear el botón
            categoria_a_pestana = {
                'espesor': 'Espesor de corte',
                'tamaño_pixel': 'Tamaño de Pixel', 
                'resolucion_espacial': 'Resolución Espacial',
                'resolucion_contraste': 'Resolución de Contraste',
                'valores_numero_ct': 'Valores CT',
                'linealidad_numero_ct': 'Linealidad del CT',
                'uniformidad_ruido': 'Uniformidad y Ruido'
            }
            
            nombre_pestana = categoria_a_pestana.get(categoria)
            if not nombre_pestana:
                print(f"❌ No se encontró mapeo para la categoría: {categoria}")
                return

            # Crear botón de guardado individual
            boton_individual = self._crear_boton_guardado_individual(nombre_pestana)
            if boton_individual:
                botones_layout.addWidget(boton_individual)                
                # Agregar el layout de botones al final de la pestaña
                tab_layout.addLayout(botones_layout)
            else:
                print(f"❌ No se pudo crear botón de guardado para '{nombre_pestana}'")
                
        except Exception as e:
            print(f"❌ Error al agregar botones de guardado post-análisis: {e}")
            import traceback
            traceback.print_exc()

    def guardar_resultado_individual(self, categoria, resultados, output_blob=None):
        """
        Función para guardar un resultado individual de análisis CatPhan.
        
        Args:
            categoria (str): Tipo de análisis ('espesor', 'tamano_pixel', etc.)
            resultados: Datos del análisis específico
        """
        try:
            #print(f"🔄 Iniciando guardado individual de {categoria}...")
            
            # Verificar datos básicos
            if not self._verificar_datos_basicos():
                return False
            
            # Crear diccionario con solo esta categoría
            resultados_por_categoria = {categoria: resultados}
            
            # Validar resultados EN MODO INDIVIDUAL
            es_valido, errores = validar_resultados_catphan(resultados_por_categoria, modo="individual")
            if not es_valido:
                error_msg = f"Errores de validación para {categoria}:\n" + "\n".join(errores)
                QMessageBox.warning(self, "Validación fallida", error_msg)
                print(f"❌ Errores de validación en {categoria}: {errores}")
                return False
            
            # Guardar en base de datos
            fecha_actual = self.date_box.date().toString("yyyy-MM-dd")
            print(fecha_actual)
            
            # IMPORTANTE: Usar context manager para evitar locks
            try:
                # Obtener información completa de imagen DICOM para guardado como BLOB
                info_dicom = self._obtener_info_imagen_dicom()
                
                id_sesion = guardar_prueba_completa_catphan(
                    user_id = self.user_id, fecha = fecha_actual, equipo = self.equipo_f,
                    kv = self.kv_actual, ma = self.ma_actual, espesor_corte = self.espesor_corte_val,
                    resultados_por_categoria = resultados_por_categoria, tam_px_teorico = self.tam_px_teorico,
                    id_sesion = self.ref, info_dicom = info_dicom, output_blob = output_blob
                )
            except Exception as db_error:
                print(f"❌ Error específico de base de datos: {db_error}")
                if "database is locked" in str(db_error).lower():
                    QMessageBox.warning(self, "Base de datos ocupada", 
                                    "La base de datos está ocupada. Espera unos segundos e intenta nuevamente.")
                else:
                    QMessageBox.critical(self, "Error de base de datos", f"Error en la base de datos:\n{str(db_error)}")
                return False
            
            if id_sesion:
                QMessageBox.information(self, "Guardado exitoso", 
                                    f"✅ {categoria.replace('_', ' ').title()} guardado correctamente.\n"
                                    f"ID de sesión: {self.ref}")
                #print(f"{categoria} guardado exitosamente con ID de sesión: {self.ref}")
                
                # Limpiar solo esta categoría después del guardado exitoso
                self.limpiar_resultados_catphan(categoria)
                return True
            else:
                QMessageBox.critical(self, "Error de guardado", 
                                    f"❌ Error al guardar {categoria} en la base de datos.")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "Error inesperado", 
                                f"❌ Error al guardar {categoria}:\n{str(e)}")
            print(f"❌ Error inesperado al guardar {categoria}: {e}")
            traceback.print_exc()
            return False

    def _verificar_datos_basicos(self):
        """Verifica que tenemos los datos básicos necesarios para guardar"""
        if not self.user_id:
            QMessageBox.warning(self, "Error", "No se encontró el ID de usuario.")
            return False
            
        if not hasattr(self, 'ref') or not self.ref:
            QMessageBox.warning(self, "Error", "No se encontró el ID de sesión.\nAsegúrate de haber iniciado el control mensual correctamente.")
            return False
            
        if not (self.kv_actual and self.ma_actual and self.espesor_corte_val):
            QMessageBox.warning(self, "Error", "Faltan parámetros de adquisición (kV, mA, espesor).\nAsegúrate de haber cargado una imagen DICOM.")
            return False
            
        return True

    def _obtener_info_imagen_dicom(self):
        """
        Obtiene la información completa del corte DICOM seleccionado para guardar como BLOB
        
        Returns:
            dict: Información del corte con 'ruta_carpeta', 'indice_corte', 'wl', 'ww'
        """
        try:
            if hasattr(self, 'corte_seleccionado_info') and self.corte_seleccionado_info:
                info = self.corte_seleccionado_info
                ruta_carpeta = info.get('ruta_carpeta_dicom')
                indice_corte = info.get('indice_corte')
                wl = info.get('wl')
                ww = info.get('ww')
                
                if ruta_carpeta:
                    #print(f"✅ Info DICOM completa encontrada:")
                    #print(f"   Ruta: {ruta_carpeta}")
                    #print(f"   Corte: {indice_corte}")
                    #print(f"   WL/WW: {wl}/{ww}")
                    
                    return {
                        'ruta_carpeta': ruta_carpeta,
                        'indice_corte': indice_corte,
                        'wl': wl,
                        'ww': ww
                    }
                    
            # Fallback: intentar obtener del visualizador principal
            if hasattr(self, 'visualizador_principal') and self.visualizador_principal:
                ruta_carpeta = getattr(self.visualizador_principal, 'ruta_carpeta', None)
                if ruta_carpeta:
                    #print(f"✅ Ruta DICOM desde visualizador principal: {ruta_carpeta}")
                    #print("⚠️ Usando valores por defecto para corte y ventana")
                    
                    return {
                        'ruta_carpeta': ruta_carpeta,
                        'indice_corte': None,  # Usará corte central
                        'wl': None,
                        'ww': None
                    }
                    
            print("⚠️ No se encontró información de DICOM")
            return None
            
        except Exception as e:
            print(f"❌ Error al obtener info DICOM: {e}")
            return None

    def guardar_resultados_catphan(self):
        """
        Función para guardar todos los resultados disponibles de análisis CatPhan en la base de datos.
        """
        try:
            #print("🔄 Iniciando guardado de todos los resultados CatPhan disponibles...")
            
            # Verificar datos básicos
            if not self._verificar_datos_basicos():
                return
            
            # Recopilar todos los resultados disponibles
            resultados_por_categoria = {}
            
            if self.resultados_espesor:
                resultados_por_categoria["espesor"] = self.resultados_espesor
                #print("  ✓ Resultados de espesor de corte disponibles")
                
            if self.resultados_tamano_pixel:  
                resultados_por_categoria["tamano_pixel"] = self.resultados_tamano_pixel
                #print("  ✓ Resultados de tamaño de pixel disponibles")
                
            if self.resultados_resolucion_contraste:
                resultados_por_categoria["resolucion_contraste"] = self.resultados_resolucion_contraste  
                #print("  ✓ Resultados de resolución de contraste disponibles")
                
            if self.resultados_resolucion_espacial:
                resultados_por_categoria["resolucion_espacial"] = self.resultados_resolucion_espacial
                #print("  ✓ Resultados de resolución espacial disponibles")

            if self.resultados_ct:
                resultados_por_categoria["valores_ct"] = self.resultados_ct
                #print("  ✓ Resultados de valores CT disponibles")
                
            if self.resultados_linealidad_ct:
                resultados_por_categoria["linealidad_ct"] = self.resultados_linealidad_ct
                #print("  ✓ Resultados de linealidad CT disponibles")
                
            if self.resultados_uniformidad:
                resultados_por_categoria["uniformidad"] = self.resultados_uniformidad
                #print("  ✓ Resultados de uniformidad disponibles")
            
            # Verificar que tengamos al menos algunos resultados
            if not resultados_por_categoria:
                QMessageBox.warning(self, "Sin resultados", 
                                "No hay resultados de análisis para guardar.\n"
                                "Realiza al menos una prueba antes de guardar.")
                return
            
            #print(f"📊 Total de categorías con resultados: {len(resultados_por_categoria)}")
            
            # Validar resultados antes de guardar EN MODO COMPLETO
            es_valido, errores = validar_resultados_catphan(resultados_por_categoria, modo="completo")
            if not es_valido:
                # En modo completo, mostrar advertencia pero permitir guardado parcial
                respuesta = QMessageBox.question(
                    self, "Validación parcial", 
                    f"Advertencias encontradas:\n" + "\n".join(errores) + 
                    "\n\n¿Deseas guardar los resultados disponibles de todas formas?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if respuesta == QMessageBox.No:
                    return
            
            # Deshabilitar botón para evitar doble guardado
            self.guardar_catphan.setEnabled(False)
            self.guardar_catphan.setText("💾 Guardando...")
            
            # Guardar en base de datos usando el self.ref como id_sesion
            fecha_actual = self.date_box.date().toString("yyyy-MM-dd")
            
            # Usar try-catch específico para manejo de locks
            try:
                # Obtener información completa de imagen DICOM para guardado como BLOB
                info_dicom = self._obtener_info_imagen_dicom()
                
                id_sesion = guardar_prueba_completa_catphan(
                    user_id=self.user_id,
                    fecha=fecha_actual,
                    equipo=self.equipo_f,
                    kv=self.kv_actual,
                    ma=self.ma_actual, 
                    espesor_corte=self.espesor_corte_val,
                    resultados_por_categoria=resultados_por_categoria,
                    tam_px_teorico=self.tam_px_teorico,
                    id_sesion=self.ref,  # Usar el self.ref como id_sesion
                    info_dicom=info_dicom
                )
            except Exception as db_error:
                print(f"❌ Error específico de base de datos: {db_error}")
                if "database is locked" in str(db_error).lower():
                    QMessageBox.warning(self, "Base de datos ocupada", 
                                    "La base de datos está ocupada. Espera unos segundos e intenta nuevamente.")
                else:
                    QMessageBox.critical(self, "Error de base de datos", f"Error en la base de datos:\n{str(db_error)}")
                return
            
            if id_sesion:
                # Éxito
                QMessageBox.information(self, "Guardado exitoso", 
                                    f"✅ Resultados guardados correctamente.\n"
                                    f"ID de sesión: {self.ref}\n"
                                    f"Fecha: {fecha_actual}\n"
                                    f"Categorías guardadas: {len(resultados_por_categoria)}")
                #print(f"Resultados CatPhan guardados exitosamente con ID de sesión: {self.ref}")
                
                # Limpiar todos los resultados después del guardado completo
                self.limpiar_resultados_catphan()
                
            else:
                QMessageBox.critical(self, "Error de guardado", 
                                    "❌ Error al guardar los resultados en la base de datos.\n"
                                    "Revisa la consola para más detalles.")
                print("❌ Error al guardar resultados CatPhan")
                
        except Exception as e:
            QMessageBox.critical(self, "Error inesperado", 
                                f"❌ Error inesperado al guardar:\n{str(e)}")
            print(f"❌ Error inesperado en guardar_resultados_catphan: {e}")
            traceback.print_exc()
            
        finally:
            # Rehabilitar botón
            self.guardar_catphan.setEnabled(True)
            self.guardar_catphan.setText("💾 Guardar Todos")
    
    # Funciones de guardado individual para cada categoría
    def guardar_espesor_corte(self):
        """Guarda solo los resultados de espesor de corte"""
        if self.resultados_espesor:
            output_blob = self.resultados_espesor.get("imagen_analisis")
            return self.guardar_resultado_individual("espesor", self.resultados_espesor, output_blob=output_blob)
        else:
            QMessageBox.warning(self, "Sin datos", "No hay resultados de espesor de corte para guardar.\nRealiza el análisis primero.")
            return False
    
    def guardar_tamano_pixel(self):
        """Guarda solo los resultados de tamaño de pixel"""
        if self.resultados_tamano_pixel:
            output_blob = self.resultados_tamano_pixel.get("imagen_analisis")
            return self.guardar_resultado_individual("tamano_pixel", self.resultados_tamano_pixel, output_blob=output_blob)
        else:
            QMessageBox.warning(self, "Sin datos", "No hay resultados de tamaño de pixel para guardar.\nRealiza el análisis primero.")
            return False
    
    def guardar_resolucion_contraste(self):
        """Guarda solo los resultados de resolución de contraste"""
        if self.resultados_resolucion_contraste:
            output_blob = self.resultados_resolucion_contraste["resumen"].get("imagen_analisis")
            return self.guardar_resultado_individual("resolucion_contraste", self.resultados_resolucion_contraste, output_blob=output_blob)
        else:
            QMessageBox.warning(self, "Sin datos", "No hay resultados de resolución de contraste para guardar.\nRealiza el análisis primero.")
            return False
    
    def guardar_resolucion_espacial(self):
        """Guarda solo los resultados de resolución espacial"""
        if self.resultados_resolucion_espacial:
            output_blob = self.resultados_resolucion_espacial.get("imagen_analisis")
            return self.guardar_resultado_individual("resolucion_espacial", self.resultados_resolucion_espacial, output_blob=output_blob)
        else:
            QMessageBox.warning(self, "Sin datos", "No hay resultados de resolución espacial para guardar.\nRealiza el análisis primero.")
            return False
    
    def guardar_valores_ct(self):
        """Guarda solo los resultados de valores CT"""
        if self.resultados_ct:
            if isinstance(self.resultados_ct, list):
                # Buscar el elemento de metadatos en la lista
                for item in self.resultados_ct:
                    if isinstance(item, dict):
                        output_blob = item.get("imagen_analisis")
            return self.guardar_resultado_individual("valores_ct", self.resultados_ct, output_blob=output_blob)
        else:
            QMessageBox.warning(self, "Sin datos", "No hay resultados de valores CT para guardar.\nRealiza el análisis primero.")
            return False
    
    def guardar_linealidad_ct(self):
        """Guarda solo los resultados de linealidad CT"""
        if self.resultados_linealidad_ct:
            output_blob = self.resultados_linealidad_ct.get("imagen_analisis")
            return self.guardar_resultado_individual("linealidad_ct", self.resultados_linealidad_ct, output_blob=output_blob)
        else:
            QMessageBox.warning(self, "Sin datos", "No hay resultados de linealidad CT para guardar.\nRealiza el análisis primero.")
            return False
    
    def guardar_uniformidad(self):
        """Guarda solo los resultados de uniformidad"""
        if self.resultados_uniformidad:
            output_blob = self.resultados_uniformidad.get("imagen_analisis")
            return self.guardar_resultado_individual("uniformidad", self.resultados_uniformidad, output_blob=output_blob)
        else:
            QMessageBox.warning(self, "Sin datos", "No hay resultados de uniformidad para guardar.\nRealiza el análisis primero.")
            return False

    def _crear_boton_guardado_individual(self, nombre_pestana):
        """
        Crea un botón de guardado individual específico para cada pestaña de análisis.
        Args:
            nombre_pestana (str): Nombre de la pestaña
            
        Returns:
            QPushButton o None: Botón configurado o None si no aplica
        """
        # Usar el mapping centralizado para obtener información de la categoría
        categoria, info_categoria = CategoriasMapping.categoria_por_pestaña(nombre_pestana)
        
        if not categoria or not info_categoria:
            print(f"⚠️ No se encontró configuración para la pestaña: {nombre_pestana}")
            return None
            
        # Obtener función de guardado desde el mapping
        funcion_guardado_nombre = info_categoria.get('funcion_guardado')
        funcion_guardado = getattr(self, funcion_guardado_nombre, None)
        
        if not funcion_guardado:
            print(f"⚠️ No se encontró la función de guardado: {funcion_guardado_nombre}")
            return None
        
        # Crear texto del botón
        texto_boton = f"💾 Guardar {categoria.replace('_', ' ').title()}"
        
        boton = QPushButton(texto_boton)
        boton.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        boton.clicked.connect(funcion_guardado)
        
        return boton

    def limpiar_resultados_catphan(self, categoria=None):
        """
        Limpia los resultados almacenados después de un guardado exitoso.
        
        Args:
            categoria (str, optional): Si se especifica, limpia solo esa categoría.
                                        Si es None, limpia todos los resultados.
        """
        if categoria is None:
            # Limpiar todos los resultados (guardado completo)
            self.resultados_espesor = None
            self.resultados_tamano_pixel = None
            self.resultados_resolucion_contraste = None
            self.resultados_resolucion_espacial = None
            self.resultados_ct = None
            self.resultados_linealidad_ct = None
            self.resultados_uniformidad = None
            #print("🧹 Todos los resultados CatPhan limpiados")
        else:
            # Limpiar solo la categoría específica (guardado individual)
            if categoria == "espesor":
                self.resultados_espesor = None
            elif categoria == "tamano_pixel":
                self.resultados_tamano_pixel = None
            elif categoria == "resolucion_contraste":
                self.resultados_resolucion_contraste = None
            elif categoria == "resolucion_espacial":
                self.resultados_resolucion_espacial = None
            elif categoria == "valores_ct":
                self.resultados_ct = None
            elif categoria == "linealidad_ct":
                self.resultados_linealidad_ct = None
            elif categoria == "uniformidad":
                self.resultados_uniformidad = None
            #print(f"🧹 Resultado de {categoria} limpiado")

    def generar_reporte_pdf(self):
        from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
        # F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS4.3): reportes_control_sistema_imagenes
        # busca el control con "fecha = ?" EXACTA -- usar la fecha REAL del
        # registro (self.fecha_control), no una derivada sin día de date_box.
        fecha = self.fecha_control if hasattr(self, 'fecha_control') else self.date_box.date().toString("dd/MM/yyyy")
        maquina = self.equipo_f  # O el atributo que corresponda a tu máquina
        usuario = str(self.user_id)  # O el atributo que corresponda a tu usuario
        generar_reporte_sistema_imagenes(self, fecha, maquina, usuario, ref=self.ref, sistema_imagenes=True)
    
    def mostrar_espesor_referencia(self):
        ruta_imagen = self.resource_path(r'analisisImagenes\espesor_corte.jpg')
        ventana = QWidget(self, Qt.Window)
        ventana.setWindowTitle("Corte de referencia")
        ventana.resize(600, 500)

        lbl = QLabel(ventana)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: #1a1a1a;")

        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)

        if os.path.exists(ruta_imagen):
            pix = QPixmap(ruta_imagen).scaled(580, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
        else:
            lbl.setText(f"No encontrado:\n{ruta_imagen}")

        ventana.show()
        ventana.activateWindow()
    
    def mostrar_pixel_referencia(self):
        ruta_imagen = self.resource_path(r'analisisImagenes\espesor_corte.jpg')
        ventana = QWidget(self, Qt.Window)
        ventana.setWindowTitle("Corte de referencia")
        ventana.resize(600, 500)

        lbl = QLabel(ventana)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: #1a1a1a;")

        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)

        if os.path.exists(ruta_imagen):
            pix = QPixmap(ruta_imagen).scaled(580, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
        else:
            lbl.setText(f"No encontrado:\n{ruta_imagen}")

        ventana.show()
        ventana.activateWindow()
    
    def mostrar_contraste_referencia(self):
        ruta_imagen = self.resource_path(r'analisisImagenes\resolucion_contraste.jpg')
        ventana = QWidget(self, Qt.Window)
        ventana.setWindowTitle("Corte de referencia")
        ventana.resize(600, 500)

        lbl = QLabel(ventana)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: #1a1a1a;")

        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)

        if os.path.exists(ruta_imagen):
            pix = QPixmap(ruta_imagen).scaled(580, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
        else:
            lbl.setText(f"No encontrado:\n{ruta_imagen}")

        ventana.show()
        ventana.activateWindow()
    
    def mostrar_resp_referencia(self):
        ruta_imagen = self.resource_path(r'analisisImagenes\resolucion_espacial.jpg')
        ventana = QWidget(self, Qt.Window)
        ventana.setWindowTitle("Corte de referencia")
        ventana.resize(600, 500)

        lbl = QLabel(ventana)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: #1a1a1a;")

        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)

        if os.path.exists(ruta_imagen):
            pix = QPixmap(ruta_imagen).scaled(580, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
        else:
            lbl.setText(f"No encontrado:\n{ruta_imagen}")

        ventana.show()
        ventana.activateWindow()
    
    def mostrar_ct_referencia(self):
        ruta_imagen = self.resource_path(r'analisisImagenes\espesor_corte.jpg')
        ventana = QWidget(self, Qt.Window)
        ventana.setWindowTitle("Corte de referencia")
        ventana.resize(600, 500)

        lbl = QLabel(ventana)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: #1a1a1a;")

        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)

        if os.path.exists(ruta_imagen):
            pix = QPixmap(ruta_imagen).scaled(580, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
        else:
            lbl.setText(f"No encontrado:\n{ruta_imagen}")

        ventana.show()
        ventana.activateWindow()
        
    
    def mostrar_uniformidad_referencia(self):
        ruta_imagen = self.resource_path(r'analisisImagenes\uniformidad_ruido.jpg')
        ventana = QWidget(self, Qt.Window)
        ventana.setWindowTitle("Corte de referencia")
        ventana.resize(600, 500)

        lbl = QLabel(ventana)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: #1a1a1a;")

        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(lbl)

        if os.path.exists(ruta_imagen):
            pix = QPixmap(ruta_imagen).scaled(580, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
        else:
            lbl.setText(f"No encontrado:\n{ruta_imagen}")

        ventana.show()
        ventana.activateWindow()
        

    def resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)
            
    def automatizacion(self):
        """
        Detectar si ya hay visualizador
        Leer los widgets de cortes
        Mover a categoria X
        estando en categoria X invocar botón elegir corte 
        volver a graficos
        cambiar categoria
        repeat
        """
        index = self.toolbox.currentIndex()
        texto = self.toolbox.itemText(index)
        print("Entra a automatizar")
        print(f" Ubicación de categoría: {texto}, en index {index}")
            
        def automatizar_espesor():
            if hasattr(self, 'visualizador_principal') and self.visualizador_principal:
                # Begin the process
                self.toolbox.setCurrentIndex(0)
                if hasattr(self, 'ln_espesor') and self.ln_espesor:
                    corte_espesor = int(self.ln_espesor.text())
                    self.visualizador_principal.slider_corte.setValue(corte_espesor-1)
                    self.visualizador_principal.elegir_corte()
            
        def automatizar_pixel():
           
            
            if hasattr(self, 'ln_espesor') and self.ln_espesor:
                corte_espesor = int(self.ln_espesor.text())
                self.visualizador_principal.slider_corte.setValue(corte_espesor-1)
                self.visualizador_principal.elegir_corte()
        
        def automatizar_con_res():  
            if hasattr(self, 'ln_contrast_res') and self.ln_contrast_res:
                con_res = int(self.ln_contrast_res.text())
                self.visualizador_principal.slider_corte.setValue(con_res-1)
                self.visualizador_principal.elegir_corte()
            
               
                
        def automatizar_res_esp():  
            if hasattr(self, 'ln_resolucion_esp') and self.ln_resolucion_esp:
                res_esp = int(self.ln_resolucion_esp.text())
                self.visualizador_principal.slider_corte.setValue(res_esp-1)
                self.visualizador_principal.elegir_corte()
                
        def automatizar_ct():
            if hasattr(self, 'ln_espesor') and self.ln_espesor:
                corte_espesor = int(self.ln_espesor.text())
                self.visualizador_principal.slider_corte.setValue(corte_espesor-1)
                self.visualizador_principal.elegir_corte()
                
        def automatizar_energia():
            self.energia_select.setCurrentIndex(1)
        
        def automatizar_uniformidad():
            if hasattr(self, 'ln_uni') and self.ln_uni:
                corte_uniformidad = int(self.ln_uni.text())
                self.visualizador_principal.slider_corte.setValue(corte_uniformidad-1)
                self.visualizador_principal.elegir_corte()
            
                
        if index==0:
            automatizar_espesor()
        self.tab_widget.setCurrentIndex(0)
        
        if index==1:
            automatizar_pixel()
        self.tab_widget.setCurrentIndex(0)
        
        if index==2:
            automatizar_con_res()
        self.tab_widget.setCurrentIndex(0)
        
        if index == 3:
            automatizar_res_esp()
        self.tab_widget.setCurrentIndex(0)
        
        if index == 4:
            automatizar_ct()
        self.tab_widget.setCurrentIndex(0)
        
        if index == 5:
            automatizar_energia()
        self.tab_widget.setCurrentIndex(0)
        
        if index == 6:
            automatizar_uniformidad()
        self.tab_widget.setCurrentIndex(0)
        
        
        
