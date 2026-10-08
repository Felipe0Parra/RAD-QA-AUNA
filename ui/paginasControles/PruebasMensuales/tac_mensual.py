
from PyQt5.QtWidgets    import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, 
                                QToolBox, QSplitter, QLineEdit, QComboBox, QSizePolicy, QHeaderView, QMessageBox, QDialog)
from PyQt5.QtCore import Qt, QDate, QTime, QTimer
from PyQt5.QtGui import QColor, QFont, QPixmap
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.util_fechas import fecha_control_a_qdate as _fecha_control_a_qdate
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.catphan_TAC.leer_dicom import VisualizadorDicom
from analisisImagenes.catphan.protocolos import comparar_con_protocolo, texto_encabezado, texto_origen
from analisisImagenes.catphan.atenuacion import energia_de_linealidad_mev, materiales_a_energia
from analisisImagenes.catphan import criterios
from analisisImagenes.Analisis_Catphan_TAC import *
from data.ManejoDatos.catphan_TAC.catphan_db import (guardar_prueba_completa_catphan, validar_resultados_catphan, tabla_resultados_espesor, tabla_resultados_tamano_pixel, tabla_resultados_resolucion_contraste, tabla_resultados_resolucion_espacial, tabla_resultados_ct, tabla_resultados_uniformidad)
from resources.utils.matplotlib_lazy import get_matplotlib_components
from datetime import datetime
from enum import Enum
from PyQt5.QtCore import QTimer
import traceback, os, json, html
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
            with Conexion().conectar() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM controles WHERE id = ? AND equipo = ?",
                    (ref, equipo)
                )
                existe = cursor.fetchone() is not None if self.tac.old_id else False
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

def _parametros_de_volumen(vol):
    """`(kv, ma, espesor_corte)` de un volumen, con el espesor redondeado a un
    decimal. Única definición: la usan `asignar_parametros_adquisicion` (lo
    que se muestra y valida al cargar) y `_registrar_adquisicion` (lo que se
    guarda con cada prueba), para que no puedan diferir en cómo se redondea."""
    espesor = getattr(vol, 'espesor_corte', None)
    return (getattr(vol, 'kv', None), getattr(vol, 'ma', None),
            round(espesor, 1) if espesor is not None else None)


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
        # A.1 (23-09): adquisicion del volumen CON EL QUE SE CORRIO cada prueba,
        # por categoria -- ver `_registrar_adquisicion`.
        self.adquisicion_por_categoria = {}
        self.tam_px_teorico = None
        self.criterios_por_categoria = {}      # G.3: criterio y veredicto de cada prueba (se guarda con ella)
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
        # G.1: el protocolo obligatorio en el encabezado de la pantalla previa
        # (donde se elige fecha y físicos), ANTES de irradiar.
        self._escribir_protocolo_en_encabezado()
        
        
        
        
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
        # G.1: `setupBox` reconstruye el encabezado (DP-54) y con él `Subtittle1`:
        # se vuelve a escribir el protocolo obligatorio en el widget nuevo.
        self._escribir_protocolo_en_encabezado()
        
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
        # G.2: la energía la fija el protocolo del equipo; la tabla de μ se llena sin que nadie elija nada
        self._aplicar_energia_de_linealidad(con_analisis=False)
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
            # G.2: la energía NO se elige -- es la del protocolo del equipo (catálogo de A.2). Se muestra
            # como texto; antes había un selector con una sola opción, la del tomógrafo, para los tres equipos.
            contenedor_energia = QHBoxLayout()
            energia_lin_ct = QLabel("Energía [MeV]:")
            self.energia_linealidad_texto = QLabel(self._texto_energia_de_linealidad())
            self.energia_linealidad_texto.setObjectName("energia_linealidad_texto")
            self.energia_linealidad_texto.setWordWrap(True)
            self.energia_linealidad_texto.setToolTip(
                "La energía de la linealidad es la del protocolo del equipo (E [keV] = kV): una convención de "
                "constancia, igual para todos los controles del equipo; no es la energía efectiva del haz.")

            contenedor_energia.addWidget(energia_lin_ct)
            contenedor_energia.addWidget(self.energia_linealidad_texto)
            contenedor_energia.addStretch()
            return contenedor_energia, tabla # Retorna el layout con la energía del protocolo y la tabla

    def imagenUpLoader(self, titulo_prueba):
        # Crear una NUEVA instancia de visualizador DICOM para cada categoría
        visualizador = VisualizadorDicom(target_canvas=self.canvas)
        
        
        # Inicializar el visualizador principal si no existe (para self.col2)
        if not hasattr(self, 'visualizador_principal'):
            self.visualizador_principal = VisualizadorDicom(target_canvas=self.canvas)
            # A.3: la ventana de metadatos compara contra ESTE equipo
            self.visualizador_principal.equipo_seleccionado = getattr(self, 'equipo_f', None)
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
    
    def _escribir_protocolo_en_encabezado(self):
        """G.1 (PLAN_HANDOFF_IMAGENES_22-09.md, ajuste 23-09): el protocolo
        obligatorio del equipo, arriba de la fecha, EN LUGAR de la frase "Atencion
        en Radioterapia" que la hoja de encabezado trae para las nueve pantallas.

        Solo las tres hojas de imágenes llegan aquí (esta clase y sus cuatro
        subclases). El texto sale del catálogo de `A.2` -- nunca de las celdas del
        Excel, que serían una segunda copia --, así que cambia con el equipo y con
        el catálogo. Los formularios de dosimetría no pasan por aquí y siguen
        diciendo lo que decían. Lleva un enlace, "de dónde sale", con el origen del
        valor, cuándo se fijó y lo que falta confirmar en la consola."""
        etiqueta = getattr(self, 'Subtittle1', None)
        if etiqueta is None:
            return
        etiqueta.setTextFormat(Qt.RichText)
        etiqueta.setWordWrap(True)
        etiqueta.setText(
            f"{html.escape(texto_encabezado(getattr(self, 'equipo_f', None)))}"
            f" · <a href='origen'>de dónde sale</a>")
        # `setupBox` crea un QLabel NUEVO cada vez: se conecta una vez por widget
        # (llamarlo dos veces sobre el mismo no debe duplicar el aviso).
        if not etiqueta.property("g1_enlace"):
            etiqueta.linkActivated.connect(self._mostrar_origen_protocolo)
            etiqueta.setProperty("g1_enlace", True)

    def _mostrar_origen_protocolo(self, _enlace=None):
        equipo = getattr(self, 'equipo_f', None)
        QMessageBox.information(self, f"Protocolo de {equipo}", texto_origen(equipo))

    def _registrar_adquisicion(self, categoria):
        """A.1 (PLAN_HANDOFF_IMAGENES_22-09.md §0.4, "segundo camino"): fija la
        adquisición del volumen CON EL QUE SE ACABA DE CORRER la prueba
        `categoria` (nombre de la BD: `espesor`, `tamano_pixel`, ...).

        `kv_actual`/`ma_actual`/`espesor_corte_val` se fijan una sola vez, al
        cargar, y se aplicaban a TODAS las pruebas que se guardaran después:
        con dos carpetas en la misma sesión, las pruebas de la primera
        quedaban grabadas con los parámetros de la segunda (la sesión 47 del
        22-09 salió toda con 125/100/2.0 habiendo mezclado iX y Halcyon). Aquí
        se toma en el momento de correrla, y es lo que el guardado usa."""
        vol = getattr(getattr(self, 'visualizador_principal', None), 'vol', None)
        if vol is None:
            self.adquisicion_por_categoria.pop(categoria, None)
            return
        kv, ma, espesor_corte = _parametros_de_volumen(vol)
        adquisicion = getattr(vol, 'adquisicion', None)
        self.adquisicion_por_categoria[categoria] = {
            "kv": kv, "ma": ma, "espesor_corte": espesor_corte,
            "adquisicion": adquisicion,
            # A.2: contra el protocolo fijo del equipo SELECCIONADO. No bloquea:
            # se archiva con la prueba, que queda marcada como no comparable.
            "desviacion_protocolo": comparar_con_protocolo(
                getattr(self, 'equipo_f', None), adquisicion).desviacion_texto(),
        }

    def _mostrar_criterio(self, categoria, resultados):
        """G.3: juzga la prueba `categoria` con la regla de SU equipo (`perfiles.py`, vía `criterios.py`), la muestra
        debajo de los resultados y la deja lista para guardarse con la prueba. Nunca lanza: una falla aquí no debe
        impedir mostrar el resultado que el físico acaba de calcular."""
        try:
            juicios = criterios.juzgar(getattr(self, 'equipo_f', None), categoria, resultados)
        except Exception as e:                                         # pragma: no cover - defensivo
            print(f"Error juzgando {categoria}: {e}")
            return None
        self.criterios_por_categoria[categoria] = criterios.a_json_ready(juicios)
        # C.1: el panel es el de la pestaña de ESTA prueba (por su nombre), no el de la pestaña que esté a la vista
        widgets = self._widgets_de(CategoriasMapping.MAPEO_COMPLETO.get(categoria, {}).get('pestaña'))
        if widgets is not None:
            widgets['criterio'].setText(criterios.texto_html(juicios))
        return juicios

    def _registrar_adquisicion_linealidad(self):
        """La linealidad sale de los HU de `valores_ct`, así que su adquisición
        es la de ESA prueba si se corrió en esta sesión (aunque después se haya
        cargado otra carpeta); solo si no hay, la del volumen activo."""
        adq_valores_ct = self.adquisicion_por_categoria.get('valores_ct')
        if adq_valores_ct:
            self.adquisicion_por_categoria['linealidad_ct'] = adq_valores_ct
        else:
            self._registrar_adquisicion('linealidad_ct')

    # Asigna los parámetros de adquisición (kv, ma, espesor de corte) desde el visualizador principal
    def asignar_parametros_adquisicion(self, reconstruido=False):
        if not hasattr(self, 'visualizador_principal'):
            print("Error: No hay visualizador principal para asignar parámetros.")
            return

        visualizador = self.visualizador_principal
        if visualizador.vol is None:
            print("Error: No hay volumen cargado en el visualizador principal para asignar parámetros.")
            return
        
        kv, ma, espesor_corte = _parametros_de_volumen(visualizador.vol)
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
    def _energia_linealidad_mev(self):
        """La energía de la linealidad de ESTE equipo: la de su protocolo (G.2), o None si no tiene."""
        return energia_de_linealidad_mev(getattr(self, 'equipo_f', None))

    def _texto_energia_de_linealidad(self):
        energia = self._energia_linealidad_mev()
        if energia is None:
            return "Sin energía definida para este equipo: no hay protocolo de imagen en el catálogo"
        return f"{energia:g} (fija, protocolo de {self.equipo_f})"

    def _aplicar_energia_de_linealidad(self, con_analisis=True):
        """G.2: rellena la tabla de linealidad (μ/ρ, ρ, μ) con la energía del protocolo del equipo.

        Antes esto lo disparaba un selector con una sola opción ("0.12 MeV") para los tres equipos; ahora la
        energía es un dato del catálogo, y la tabla se llena al construir la pantalla (`con_analisis=False`:
        solo rellena, sin cambiar de pestaña ni intentar el ajuste, que llega cuando llegan los HU)."""
        tabla = getattr(self, "tabla_linealidad_ct", None)
        if not isinstance(tabla, QTableWidget):
            return          # los resultados ya están guardados: en su lugar hay un aviso, no una tabla
        energia = self._energia_linealidad_mev()
        self.energia_linealidad_mev = energia
        self.mu_lista = []

        def vaciar():
            for i in range(tabla.rowCount()):
                for j in range(1, tabla.columnCount()):
                    tabla.setItem(i, j, QTableWidgetItem(""))

        if energia is None:
            vaciar()
            return
        try:
            materiales_por_energia = materiales_a_energia(energia)
        except (FileNotFoundError, KeyError, ValueError) as e:
            QMessageBox.warning(self, "Error", f"No se pudo leer la tabla de materiales:\n{e}")
            vaciar()
            return
        energia_num = f"{energia:g}"

        # Mapeo nombres de tabla -> nombres en JSON
        normalizar = { "Acrílico": "Acrilico", "Teflón": "Teflon"}

        self.mu_lista = []  # reinicia μ (1/cm) en orden de la tabla

        # Rellenar tabla
        for fila in range(tabla.rowCount()):
            mat_item = tabla.item(fila, 0)
            if not mat_item:
                continue
            nombre_tabla = mat_item.text().strip()
            nombre_json = normalizar.get(nombre_tabla, nombre_tabla)

            props = materiales_por_energia.get(nombre_json)

            # Escribe MeV
            tabla.setItem(fila, 1, QTableWidgetItem(energia_num))
            if not props:
                # Vaciar propiedades si el material no existe en el JSON para esa energía
                tabla.setItem(fila, 2, QTableWidgetItem(""))
                tabla.setItem(fila, 3, QTableWidgetItem(""))
                tabla.setItem(fila, 4, QTableWidgetItem(""))
                continue

            # μ/ρ (cm²/g), ρ (g/cm³) y μ (1/cm) de la tabla generada por scripts/generar_tabla_mu.py
            mu_rho = props.get("mu_rho", "")
            rho = props.get("densidad", "")
            mu = props.get("mu", "")

            def fmt(x, nd=4):
                try:
                    return f"{float(x):.{nd}f}"
                except Exception:
                    return str(x) if x is not None else ""

            tabla.setItem(fila, 2, QTableWidgetItem(fmt(mu_rho)))
            tabla.setItem(fila, 3, QTableWidgetItem(fmt(rho)))
            tabla.setItem(fila, 4, QTableWidgetItem(fmt(mu)))

            # Guarda μ (1/cm) como float o None
            try:
                self.mu_lista.append(float(mu))
            except Exception:
                self.mu_lista.append(None)

        # Deja self.mu listo para usar en el análisis ↓
        self.mu = [m for m in self.mu_lista if m is not None]  # copia limpia
        if not con_analisis:
            return

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
        
        import numbers

        def _n(clave, formato):
            # GI.3: un valor que falta o que no es un número se dice «N/A»; no tumba el texto ni se escribe un 0 que el análisis no dio.
            valor = resultados.get(clave)
            return format(valor, formato) if isinstance(valor, numbers.Real) and not isinstance(valor, bool) else "N/A"

        lines = []
        lines.append("Resultados de Linealidad del Número CT:")
        lines.append("-------------------------------------------------------------")
        lines.append("  Ecuación de la recta: HU = {} * (μ) + {}".format(_n("pendiente", ".4f"), _n("intercepto", ".4f")))
        lines.append("  Coeficiente de determinación (R²): {}".format(_n("r_squared", ".4f")))
        lines.append("  Referencia: {}".format(_n("referencia", ".4f")))
        lines.append("  Escala de contraste = {}".format(_n("escala_contraste", ".9f")))
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
        if getattr(self, "energia_linealidad_mev", None) is None:
            return None     # G.2: sin energía de protocolo no hay μ con qué ajustar

        # Asegurar que la pestaña (y su canvas) esté disponible
        pestana = "Linealidad del CT"
        try:
            self._abrir_pestana(pestana)
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
            linealidad = linealidad_ct(datos=mu_vals, hu_promedio=hu_vals, visualizar=True, canvas=self._canvas_de(pestana))
            if isinstance(linealidad, dict):
                linealidad["energia_mev"] = self.energia_linealidad_mev   # G.2: se guarda con la prueba
            texto = self.tabla_resultados_linealidad(linealidad)
            self._escribir_resultado(pestana, texto)
            
            #print(" Análisis de Linealidad del CT completado")
            #print(f"   Resultados: {linealidad}")
            self.resultados_linealidad_ct = linealidad  # Almacenar para guardado
            self._registrar_adquisicion_linealidad()
            self._mostrar_criterio('linealidad_ct', linealidad)      # G.3
            if linealidad:
                self._agregar_botones_guardado_post_analisis("linealidad_numero_ct")
            return linealidad
        except Exception as e:
            print(f" Error en analizar_linealidad_ct: {e}")
            import traceback
            traceback.print_exc()
            return None

    # Sucede cuando ya se elegió un corte, acá se llama a las funciones de análisis
    # y se muestran los resultados en consola
    def imagen_dicom_cargada(self, imagen_analisis, imagen_grafica, tam_px):
        """
        Maneja el evento cuando se carga una imagen DICOM.
        """
        # D.1 (23-09): orientación y giro medidos por el motor para la
        # serie del visualizador principal ("un solo visualizador, una
        # sola carga", C.2) -- "normal"/0.0 si aún no se detectaron.
        _vis_activo = getattr(self, 'visualizador_principal', None)
        orientacion_serie = getattr(_vis_activo, 'orientacion', 'normal')
        roll_deg_serie = getattr(_vis_activo, 'roll_deg', 0.0)

        # GI.3: UNA sola definición de lo que se ve de las SEIS pruebas de abajo, la de `catphan_db` (importada arriba): lo recién analizado y lo reabierto de la
        # base se muestran con el mismo código. La séptima (linealidad) NO: su texto del análisis recién hecho es otro (`tabla_resultados_linealidad`, sin energía ni veredicto).

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
                    pestana = "Espesor de corte"
                    self._abrir_pestana(pestana)
                    #print("\nProcesando corte para la categoría de ESPESOR DE CORTE")

                    # E.1 (PLAN_ESPESOR_CORTE_24-09.md): como pylinac, el corte elegido y sus dos
                    # vecinos si el nominal es < 3.5 mm (la regla vive en `cortes_vecinos_espesor`).
                    # Solo si `imagen_analisis` ES el corte `indice_corte` del volumen del visor.
                    import numpy as np
                    _idx_espesor = (getattr(self, 'corte_seleccionado_info', None) or {}).get('indice_corte')
                    _vol_hu = visualizador_principal.vol.volumen_hu
                    _vecinos_espesor = []
                    if _idx_espesor is not None and np.shares_memory(_vol_hu[_idx_espesor], imagen_analisis):
                        _vecinos_espesor = cortes_vecinos_espesor(_vol_hu, _idx_espesor, self.espesor_corte_val)
                    resultados_espesor = espesor_corte(imagen_grafica, imagen_analisis, tam_px, visualizar=True,
                                                       combinar_slices=bool(_vecinos_espesor),
                                                       slices_adyacentes=_vecinos_espesor,
                                                       canvas=self._canvas_de(pestana))
                    if resultados_espesor.get("espesor_promedio_mm") is None:
                        # Guarda de E.1: sin alambre medible en este corte no hay número (ni guardado).
                        self.resultados_espesor = None
                        self._escribir_resultado(
                            pestana,
                            "Espesor de corte: no se detectaron las rampas de alambre en este corte "
                            f"({resultados_espesor.get('num_rampas_detectadas', 0)} de 4 válidas; hacen falta 3). "
                            "Elija el corte del módulo CTP404 que sugiere la detección automática.")
                        continue

                    self.resultados_espesor = resultados_espesor  # Almacenar para guardado
                    self._registrar_adquisicion('espesor')
                    error = (abs((self.espesor_corte_val) - resultados_espesor.get("espesor_promedio_mm", None)) / self.espesor_corte_val) * 100 if self.espesor_corte_val and resultados_espesor.get("espesor_promedio_mm", None) else None
                    espesor_teorico_mm = self.espesor_corte_val if self.espesor_corte_val else None
                    resultados_espesor['espesor_teorico_mm'] = espesor_teorico_mm
                    resultados_espesor['diferencia_mm'] = round(abs(espesor_teorico_mm - resultados_espesor.get("espesor_promedio_mm", 0)), 3) if espesor_teorico_mm else None
                    self._mostrar_criterio('espesor', resultados_espesor)      # G.3
                    texto = tabla_resultados_espesor(resultados_espesor)
                    self._escribir_resultado(pestana, texto)
                    #print(texto)
                    #print(f"Espesor de corte esperado: {self.espesor_corte_val} mm, Espesor calculado: {resultados_espesor.get('espesor_promedio_mm', None)} mm, Error relativo: {error:.2f}%")
                    # Agregar botones de guardado después del análisis completado
                    self._crear_boton_guardado_individual(categoria)

                # -------------------------------    TAMAÑO DE PIXEL          ------------------------------- #
                elif categoria == 'tamaño_pixel':
                    pestana = "Tamaño de Pixel"
                    self._abrir_pestana(pestana)
                    #print("\nProcesando corte para la categoría de TAMAÑO DE PIXEL")

                    resultados_tamano_pixel = tamano_pixel(imagen_grafica, imagen_analisis, tam_px, visualizar=True, canvas=self._canvas_de(pestana))
                    self.resultados_tamano_pixel = resultados_tamano_pixel  # Almacenar para guardado
                    self._registrar_adquisicion('tamano_pixel')
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
                    self._mostrar_criterio('tamano_pixel', resultados_tamano_pixel)      # G.3

                    texto = tabla_resultados_tamano_pixel(resultados_tamano_pixel)
                    self._escribir_resultado(pestana, texto)
                    #print(texto)
                    #print(f"Tamaño pixel teórico: {round(tam_px, 3)} mm, Error relativo: {error:.2f}%" if error else "Error: No se pudo calcular")
                    # Agregar botones de guardado después del análisis completado
                    self._agregar_botones_guardado_post_analisis(categoria)

                # -------------------------------    RESOLUCIÓN ESPACIAL      ---------------------------- #
                elif categoria == 'resolucion_espacial':
                    pestana = "Resolución Espacial"
                    self._abrir_pestana(pestana)
                    #print("Procesando corte para la categoría de RESOLUCIÓN DE ESPACIAL")

                    resultados_resolucion = resolucion_espacial(imagen_grafica, imagen_analisis, tam_px, visualizar=True, canvas=self._canvas_de(pestana), orientacion=orientacion_serie, roll_deg=roll_deg_serie)
                    self.resultados_resolucion_espacial = resultados_resolucion  # Almacenar para guardado
                    self._registrar_adquisicion('resolucion_espacial')
                    self._mostrar_criterio('resolucion_espacial', resultados_resolucion)      # G.3
                    texto = tabla_resultados_resolucion_espacial(resultados_resolucion)
                    self._escribir_resultado(pestana, texto)
                    # Agregar botones de guardado después del análisis completado
                    self._agregar_botones_guardado_post_analisis(categoria)

                # -------------------------------    RESOLUCIÓN DE CONTRASTE  ---------------------------- #
                elif categoria == 'resolucion_contraste':
                    pestana = "Resolución de Contraste"
                    self._abrir_pestana(pestana)
                    
                    # 1. Crear GeometriaCatphan UNA sola vez (D.0: geometría desde HU)
                    from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
                    catphan = GeometriaCatphan(imagen_analisis, tam_px, orientacion=orientacion_serie, roll_deg=roll_deg_serie)
                    
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
                        canvas=self._canvas_de(pestana),
                        # G.3: qué cuenta como ROI visible (parámetros heredados, sin fuente normativa): un solo
                        # sitio, `criterios.PARAMETROS_HEREDADOS`; el veredicto de esta prueba está pendiente de métrica
                        **criterios.parametros_de_analisis('resolucion_contraste', self.equipo_f),
                        # D.1: mismos orientacion/roll_deg con los que se
                        # construyó `catphan` arriba -- las ROI de fondo
                        # los necesitan aparte (no pasan por `catphan`).
                        orientacion=orientacion_serie,
                        roll_deg=roll_deg_serie,
                    )
                    self.resultados_resolucion_contraste = resolucion
                    self._registrar_adquisicion('resolucion_contraste')
                    self._mostrar_criterio('resolucion_contraste', resolucion)      # G.3
                    imprimir_resultados_contraste_bajo(resolucion)
                    tabla_widget = tabla_resultados_resolucion_contraste(resolucion)
                    self._escribir_resultado(pestana, tabla_widget)
                    self._agregar_botones_guardado_post_analisis(categoria)

                # -------------------------------    VALORES DEL NÚMERO CT    ------------------------------- #
                elif categoria == 'valores_numero_ct':
                    pestana = "Valores CT"
                    self._abrir_pestana(pestana)
                
                    # 1. Construir geometría CT UNA sola vez
                    from data.ManejoDatos.catphan_TAC.posicionador_manual import (
                        GeometriaCatphanCT,
                        PosicionadorDialogCT,
                    )
                    catphan_ct = GeometriaCatphanCT(imagen_analisis, tam_px)  # D.0: geometría desde HU
                
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
                        canvas=self._canvas_de(pestana),
                    )
                    self._registrar_adquisicion('valores_ct')
                    self._mostrar_criterio('valores_ct', self.resultados_ct)      # G.3
                
                    tabla_widget = tabla_resultados_ct(self.resultados_ct)
                    self._escribir_resultado(pestana, tabla_widget)
                    self.actualizar_hu_desde_resultados_ct()
                    self._agregar_botones_guardado_post_analisis(categoria)
                
                


                # -------------------------------    LINEALIDAD DEL NÚMERO CT ------------------------------- #
                elif categoria == 'linealidad_numero_ct':
                    #print("*** ENTRANDO EN CONDICIÓN DE LINEALIDAD CT ***")
                    
                    resultados_linealidad = self.try_actualizar_linealidad_ct()
                    # Agregar botones de guardado después del análisis completado

                    if resultados_linealidad:
                        self._agregar_botones_guardado_post_analisis(categoria)
                    
                # -------------------------------    UNIFORMIDAD Y RUIDO      ------------------------------- #
                elif categoria == 'uniformidad_ruido':
                    pestana = "Uniformidad y Ruido"
                    self._abrir_pestana(pestana)
                    #print("Procesando corte para la categoría de UNIFORMIDAD Y RUIDO")
                    # G.3: la tolerancia sale de la regla de uniformidad del equipo (`perfiles.py`)
                    uniformidad_resultados = uniformidad(imagen_grafica, imagen_analisis, tam_px, visualizar=True, 
                                                        canvas=self._canvas_de(pestana),
                                                        **criterios.parametros_de_analisis('uniformidad', self.equipo_f))
                    self.resultados_uniformidad = uniformidad_resultados  # Almacenar para guardado
                    self._registrar_adquisicion('uniformidad')
                    self._mostrar_criterio('uniformidad', uniformidad_resultados)      # G.3
                    
                    # Reemplazar el QLabel con QTableWidget
                    tabla_widget = tabla_resultados_uniformidad(uniformidad_resultados)
                    self._escribir_resultado(pestana, tabla_widget)
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

        if self._widgets_de(text) is not None:
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
        widgets = self._widgets_de(text)
        if widgets is not None:
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(widgets['tab']))

    # C.1 (PLAN_HANDOFF_IMAGENES_22-09.md): la pestaña es la dueña de sus widgets. Antes `_crear_nueva_tab` dejaba el
    # lienzo, la barra y el texto de la ÚLTIMA pestaña creada en atributos únicos de la pantalla y todo el análisis
    # escribía ahí: en la pestaña equivocada si el físico había cambiado de pestaña, en un widget destruido si la
    # había cerrado, y con `.setText` sobre una tabla si el resultado anterior había convertido el texto en tabla.
    # Ahora el ÚNICO camino a un widget de resultados es la pestaña que lo contiene, por su nombre.
    def _widgets_de(self, text):
        """Los widgets de la pestaña `text` ({tab, layout, canvas, toolbar, label, resultados, criterio, titulo}), o
        None si esa pestaña no existe. Una pestaña cuyo widget ya fue destruido (`deleteLater` de `limpiar_recursos`,
        por ejemplo) es una pestaña que no existe: se retira del registro, así nadie recibe un widget muerto.
        `label` es la etiqueta con la que nace la pestaña, la que recibe la reconstrucción desde la BD
        (`GestorReconstruccion`); NO es el destino de los resultados: ese es `resultados`, la ranura."""
        widgets = getattr(self, 'dynamic_tabs', {}).get(text)
        if widgets is None:
            return None
        try:
            widgets['tab'].objectName()             # RuntimeError si el objeto C++ ya no existe
        except RuntimeError:
            self.dynamic_tabs.pop(text, None)
            return None
        return widgets

    def _abrir_pestana(self, text):
        """Deja abierta y a la vista la pestaña de resultados `text` y devuelve sus widgets. El combo dice qué
        resultado se ve; si la pestaña no existe (nunca se abrió, se cerró o su widget murió) se crea por el mismo
        camino que el combo (`createTab`: reconstruir desde la BD o agregar los controles de guardado); si existe,
        solo se activa. Antes se dependía de que el cambio del combo creara la pestaña, y con el combo ya en ese
        texto no emite nada: el resultado se escribía en el último widget que se hubiera creado."""
        self.graficar.setCurrentText(text)
        widgets = self._widgets_de(text)
        if widgets is None:
            self.createTab(text)
            widgets = self._widgets_de(text)
            if widgets is None:
                raise RuntimeError(f"No se pudo abrir la pestaña de resultados '{text}'")
        else:
            self._activar_tab_existente(text)
        return widgets

    def _canvas_de(self, text):
        """El lienzo de la pestaña `text` (abriéndola si hace falta): donde dibuja el análisis de esa prueba."""
        return (self._widgets_de(text) or self._abrir_pestana(text))['canvas']

    ESTILO_RESULTADOS = ("QLabel { font-family: 'Segoe UI'; font-size: 15px; color: #2c3e50; "
                         "background-color: #f8f9fa; padding: 10px; border: 1px solid #dee2e6; border-radius: 5px; }")

    def _escribir_resultado(self, text, contenido):
        """Único punto por el que el resultado de una prueba llega a la pantalla. `contenido` es texto o un widget
        (una tabla): que el destino sea un QLabel o un QTableWidget deja de ser una suposición del llamador, porque
        la ranura de resultados de cada pestaña es un contenedor y aquí se cambia lo que hay dentro."""
        widgets = self._widgets_de(text) or self._abrir_pestana(text)
        ranura = widgets['resultados'].layout()
        actual = ranura.itemAt(0).widget() if ranura.count() else None
        if isinstance(contenido, str) and isinstance(actual, QLabel):
            actual.setText(contenido)              # texto sobre texto: la misma etiqueta, como siempre
            actual.setStyleSheet(self.ESTILO_RESULTADOS)
            return actual
        while ranura.count():
            viejo = ranura.takeAt(0).widget()
            if viejo is not None and viejo is not contenido:
                viejo.setParent(None)
        if isinstance(contenido, str):
            etiqueta = QLabel()
            etiqueta.setWordWrap(True)
            etiqueta.setText(contenido)
            etiqueta.setStyleSheet(self.ESTILO_RESULTADOS)
            contenido = etiqueta
        ranura.addWidget(contenido)
        return contenido

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

        # Ranura de resultados: un contenedor que pertenece al layout de la pestaña y no se reemplaza nunca; lo que
        # cambia es su contenido (el texto o la tabla de cada resultado), y eso lo hace `_escribir_resultado`.
        contenedor_resultados = QWidget()
        contenedor_resultados.setObjectName("contenedor_resultados")
        ranura = QVBoxLayout(contenedor_resultados)
        ranura.setContentsMargins(0, 0, 0, 0)
        resultados_texto = QLabel()
        resultados_texto.setWordWrap(True)
        ranura.addWidget(resultados_texto)
        new_tab_layout.addWidget(contenedor_resultados, stretch=0)

        # G.3: criterio y veredicto del equipo, debajo de los resultados. Es un widget propio: sobrevive cuando
        # `_escribir_resultado` cambia lo que hay en la ranura de resultados (texto o tabla).
        criterio_texto = QLabel()
        criterio_texto.setObjectName("criterio_texto")
        criterio_texto.setWordWrap(True)
        criterio_texto.setTextFormat(Qt.RichText)
        new_tab_layout.addWidget(criterio_texto, stretch=0)

        # Los widgets de la pestaña viajan con ella: `dynamic_tabs[text]` los guarda completos y se van con su entrada
        # cuando la pestaña se cierra (`closeTab`) o se destruye (`limpiar_recursos`). No queda ningún puntero suelto.
        widgets = {
            'tab': new_tab,
            'layout': new_tab_layout,
            'canvas': canvas_resultados,
            'toolbar': toolbar_tac,
            'label': resultados_texto,
            'resultados': contenedor_resultados,
            'criterio': criterio_texto,
            'titulo': titulo
        }
        self.tab_widget.addTab(new_tab, text)
        self.dynamic_tabs[text] = widgets
        self.tab_widget.setCurrentWidget(new_tab)

        return widgets

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
            # Mapear categoria interna a nombre de pestaña
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

            # C.1: el layout es el de la pestaña de ESTA prueba, no el de la que esté a la vista
            widgets = self._widgets_de(nombre_pestana)
            if widgets is None:
                print(f"❌ No hay pestaña abierta para '{nombre_pestana}'")
                return
            tab_layout = widgets['layout']
            
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
                    id_sesion = self.ref, info_dicom = info_dicom, output_blob = output_blob,
                    adquisicion_por_categoria = self.adquisicion_por_categoria,
                    criterios_por_categoria = self.criterios_por_categoria
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
                    info_dicom=info_dicom,
                    adquisicion_por_categoria=self.adquisicion_por_categoria,
                    criterios_por_categoria=self.criterios_por_categoria
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
            self.adquisicion_por_categoria = {}
            self.criterios_por_categoria = {}
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
            self.adquisicion_por_categoria.pop(categoria, None)
            self.criterios_por_categoria.pop(categoria, None)
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
            self._aplicar_energia_de_linealidad()    # G.2: ya no hay selector; la energía es la del protocolo
        
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
        
        
        
