from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from PyQt5.QtWidgets import (QAbstractItemView, QComboBox, QLineEdit,  QPushButton, QTabWidget, QSizePolicy, QWidget, QVBoxLayout, 
                            QHBoxLayout, QSplitter, QLabel, QTableWidget,QTableWidgetItem, QHeaderView, QToolBox, QGroupBox, QMessageBox,
                            QScrollArea, QFileDialog)
import pydicom
from PyQt5.QtCore import QDate, Qt, QTimer
from PyQt5.QtGui import QColor
from models.PDF.pdf import generar_reporte_mlc_pdf, generar_reporte_starshot_pdf
from data.ManejoDatos.load import *
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.Tablas_Anuales.tablas_anuales import mostrar_controles_anuales
import os, traceback, sqlite3
from functools import lru_cache
from analisisImagenes.Analisis_PlacaCuadrada import analizar_cuadrado2,  generar_reporte_completo
from resources.utils.matplotlib_lazy import get_matplotlib_components
from matplotlib.figure import Figure
from ui.paginasGuia.dialogs import DialogCalculadoraDosis
from mcc_PTW_read.mcc_read import agregar_carpeta
from services.mcc_metrics import (
    calcular_simetria_planicidad, calcular_calidad_fotones,
    RATIO_SIMETRIA, RATIO_PLANICIDAD)
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_GUARDAR
from services.fechas_control import mismo_mes as _mismo_mes
from ui.util_fechas import fecha_control_a_qdate as _fecha_control_a_qdate
from services.vigencia_equipo import es_vigente_en_fecha
from services.MLCs_calibration_service import MLC_MEASSUREMENT, STARSHOT_MEASUREMENT
from services.MLCs_calibration_service import _dibujar_peine, _dibujar_picket_detalle, _dibujar_perfiles_picket, _conectar_interactividad, _error_color, procesar_data_starshot, dibujar_starshot_imagen, conectar_interactividad_starshot, _dibujar_varianza_interpicket, _dibujar_analisis_estadistico, pf_db_insertion, pf_picket_error_insertion, pf_leaf_error_insertion, pf_highest_leaf_errors_insertion, analisis_profundo_starshot, _dibujar_colinealidad_starshot, _dibujar_uniformidad_angular, _dibujar_residuos_starshot, starshot_angles_insertion, starshot_residual_statistics_insert, starshot_angular_uniformity_insert, starshot_insert                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
from services.MLCs_calibration_service import (
    _error_color,
    _style_ax,
    _COL_OK,     
    _COL_WARN,    
    _COL_FAIL,   
    _COL_BG,    
    _COL_GRID,   
    _COL_TEXT,   
    _COL_SUBTEXT, 
    _COL_LINE,   
    _COL_A,         # azul banco A
    _COL_B,        # naranja banco B
    _COL_ZERO   
    )
import numpy as np
# P1 (PLAN_P1_POOL_CONEXIONES_27-07.md): la clase con estado a nivel de
# CLASE que vivía aquí (pool compartido -> bug H-B, "Cannot operate on a
# closed database") fue reemplazada por la fachada sin estado de
# services/db_pool.py. Se re-exporta el nombre para no cambiar ningún
# call-site ni ningún import existente (~11 en este archivo, más tests).
from services.db_pool import DatabaseManager

# Clase principal para el control mensual del Clinac 600
class PruebaMensual600(PruebaBasico):
    # Constantes de configuración
    TOLERANCIA_FOTONES = 2
    TOLERANCIA_ELECTRONES = 3
    EQUIPO_NAME = "Clinac 600"
    ENERGIAS = ["6mv"]

    def consultar_fisicos_bd(self, id_f1=None):
        fecha = self.date_box.date()
        fecha = fecha.toString("MM/yyyy")
        """Consulta los físicos disponibles en la base de datos"""
        try:
            
            if hasattr(self, 'equipo_f') and (self.equipo_f != 'Tomógrafo'):
                conn = self.db_manager.obtener_conexion()
            else:
                conn = Conexion().conectar()
            
            cursor = conn.cursor()
            cursor.execute("SELECT id, fullname FROM users WHERE role = 'Físico Médico'")
            fisicos = cursor.fetchall()
            

            # Usa el parámetro id_f1, no self.id_f1

            id_f1_num = id_f1._nombre if hasattr(id_f1, "_nombre") else id_f1
            print(f"id_f1 recibido: {id_f1}, id_f1_num usado: {id_f1_num}")
            nombre_f1 = [fis[1] for fis in fisicos if fis[1] == id_f1_num] if id_f1_num is not None else []
            print(f"Consulta de físicos exitosa: Nombre F1: {nombre_f1}")
        
            
            return fisicos, nombre_f1
        except Exception as e:
            print(f"Error al consultar físicos: {e}")
          
            print(e)
            
            return None, []

    def __init__(self, user_id, equipo_f=None):
        
        #print("PruebaMensual600       __init__ called")
        super(PruebaMensual600, self).__init__()
        
        # Inicialización de componentes principales
        self.equipo_f = equipo_f if equipo_f else self.EQUIPO_NAME
        print(equipo_f)
        # Gestores optimizados
        self.db_manager = DatabaseManager()

        # Referencias débiles para evitar referencias circulares
        self._cleanup_refs = []
        
        # Estados y caché
        self._widget_cache = {}
        self._calculation_cache = {}
        
        # Debouncing timers
        self._debounce_timers = {}
        if self.equipo_f == "Clinac 600":
            if hasattr(self, 'anual') and self.anual:
                lista_maquina=['encabezado_anual_600', 'Control anual', 'Iniciar control anual', 'Clinac 600', 'preguntas_anual_600']
            else:
                lista_maquina=['encabezado_mensu_600', 'Control mensual', 'Iniciar control mensual', 'Clinac 600', 'preguntas_mensu_600']

        elif self.equipo_f == "Halcyon":
            if hasattr(self, 'anual') and self.anual:
                lista_maquina=['encabezado_anual_Halcyon', 'Control anual', 'Iniciar control anual', 'Halcyon', 'preguntas_anual_Halcyon']
                
            elif hasattr(self, 'anual') and self.anual and self.img_analysis:

                lista_maquina=['encabezado_images_ix', 'Control anual', 'Control mensual', 'Iniciar Imagenes anual', 'Halcyon', 'preguntas_mensu_TAC']
                
            else:
                lista_maquina=['encabezado_mensu_Halcyon', 'Control mensual', 'Iniciar control mensual', 'Halcyon', 'preguntas_mensu_Halcyon']

        elif self.equipo_f == "Clinac ix":
            if hasattr(self, 'anual') and self.anual:
                
                lista_maquina=['encabezado_anual_ix', 'Control anual', 'Iniciar control anual', 'Clinac ix', 'preguntas_anual_ix']
            elif hasattr(self, 'anual') and self.anual and self.img_analysis:

                lista_maquina=['encabezado_images_ix', 'Control anual', 'Control mensual', 'Iniciar Imagenes anual', 'Clinac ix', 'preguntas_mensu_TAC']
                
            else:
                lista_maquina=['encabezado_mensu_IX', 'Control mensual', 'Iniciar control mensual', 'Clinac ix', 'preguntas_mensu_ix']
                
        
            

        elif self.equipo_f == "Tomógrafo":
            lista_maquina=['encabezado_mensu_TAC', 'Control mensual', 'Iniciar control mensual', 'Tomógrafo', 'preguntas_mensu_TAC']
        self.preINIGI(user_id, lista_maquina)
    
    def limpiar_recursos(self):
        """Limpia recursos para evitar memory leaks"""
        try:
            # Limpiar timers de debouncing
            for timer in self._debounce_timers.values():
                if timer and timer.isActive():
                    timer.stop()
            self._debounce_timers.clear()

            # Limpiar caché de modelos
            if hasattr(self, '_model_cache'):
                self._model_cache.clear()
            
            # Limpiar caché de cálculos
            if hasattr(self, '_calculation_cache'):
                self._calculation_cache.clear()
            
            # Limpiar tabs dinámicas
            if hasattr(self, 'dynamic_tabs'):
                for tab in self.dynamic_tabs.values():
                    if tab:
                        tab.deleteLater()
                self.dynamic_tabs.clear()
            
            # Cerrar conexiones de BD
            if hasattr(self, 'db_manager'):
                self.db_manager.cerrar_conexiones()
            
            print("Recursos limpiados correctamente")
            
        except Exception as e:
            print(f"Error al limpiar recursos: {e}")
            
            
    def __del__(self):
        """Destructor optimizado"""
        self.limpiar_recursos()
    
    @property
    def es_control_anual(self):
        """Retorna True si es un control anual"""
        return hasattr(self, 'anual') and self.anual
    
    def _actualizar_tabla_despues_subida(self):
        """Actualiza la tabla principal según si es control mensual o anual"""
        # Determinar el nombre del atributo de tabla (puede ser 'tabla' o 'tabla_widget')
        tabla_widget = getattr(self, 'tabla_widget', None) or getattr(self, 'tabla', None)
        
        if not tabla_widget:
            return
        
        # Verificar si es control anual
        if hasattr(self, 'anual') and self.anual:
            print(f"Actualizando tabla de controles anuales para {self.equipo_f}")
            mostrar_controles_anuales(self, tabla_widget, equipo_filtrar=self.equipo_f)
        else:
            print(f"Actualizando tabla de controles mensuales para {self.equipo_f}")
            mostrar_controles_mensuales(None, tabla_widget, equipo_filtrar=self.equipo_f)
    
    def actualizar_fisicos(self):
        # F2 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): mismo criterio que
        # create_control -- la identidad es (equipo, mes, anio), nunca la
        # fecha completa como texto exacto.
        fecha_elegida = self.date_box.date().toString("MM/yyyy")
        try:
            conn = self.db_manager.obtener_conexion() if hasattr(self, 'equipo_f') and self.equipo_f != 'Tomógrafo' else Conexion().conectar()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT fecha, user_id, user_id_f2 FROM controles WHERE equipo = ?",
                (self.equipo_f,)
            )
            resultado = None
            for fecha_existente, user_id, user_id_f2 in cursor.fetchall():
                if _mismo_mes(fecha_existente, fecha_elegida):
                    resultado = (user_id, user_id_f2)
                    break

            if resultado:
                self.fisico1.setText(resultado[0])
                if resultado[1]:
                    self.fisico2.setCurrentText(resultado[1])
            conn.close()
        except Exception as e:
            print(f"Error: {e}")
           
                
    
    def actualizar_user_id_f2(self, fisicos_disponibles=None):
        self.user_id_f2 = self.fisico2.currentData()
        print(f"Físico 2 seleccionado: {self.fisico2.currentText()}, ID: {self.user_id_f2}")
        
    def actualizar_user_id_f1(self):
        self.user_id_f1 = self.fisico1.currentData()  # userData = id del físico
    # Inicializa la interfaz para el control mensual 
    def preINIGI(self, user_id, inputs_maquina):
        
        # Define el archivo Excel que contiene la configuración de widgets
        archivo = 'widgets.xlsx'
        
        # Configura el encabezado general para el control mensual y descarta el valor retornado
        _ = self.setupBox(archivo, inputs_maquina[0])
        
        # Crea el layout principal para la interfaz
        if not self.layout():
            self.main_layout = QVBoxLayout(self)
        else:
            self.main_layout = self.layout()
        
        # Configuración de la caja de selección de fecha:
        # F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): se muestra y guarda
        # el día real -- antes solo mes/año, lo que forzaba a la calculadora
        # abierta desde aquí a asumir siempre el día 1 (ver F5) y no dejaba
        # trazabilidad de en qué día se hizo el control.
        self.date_box.setDisplayFormat("dd/MM/yyyy")
        #self.date_box.setDate(QDate.currentDate())
        #self.date_box.setCalendarPopup(True)

        # Guarda el ID del usuario para utilizarlo posteriormente
        self.user_id = user_id
        #self.date_box.dateChanged.connect(self.actualizar_fisicos)
        fisicos_disponibles, nombre_f1 = self.consultar_fisicos_bd(id_f1=self.user_id)
        try:
            for fisico in fisicos_disponibles:
                self.fisico1.addItem(fisico[1], fisico[0])  # texto=nombre, userData=id
            
            # Preseleccionar el usuario actual
            if nombre_f1:
                index = self.fisico1.findText(nombre_f1[0])
                if index >= 0:
                    self.fisico1.setCurrentIndex(index)
            
            for fisico in fisicos_disponibles:
                self.fisico2.addItem(fisico[1], fisico[0])  # también guardar userData en fisico2

        except Exception as e:
            print(e)

        # Inicializar user_id_f1 con el usuario actual
        self.user_id_f1 = self.fisico1.currentData()
        self.user_id_f2 = None

        # Conectar señales
        self.fisico1.currentIndexChanged.connect(lambda: self.actualizar_user_id_f1())
        self.user_id_f2 = None
        self.fisico2.currentIndexChanged.connect(lambda: self.actualizar_user_id_f2(fisicos_disponibles))

        
        # Crea un QGroupBox para contener los controles del "Control mensual"
        # y lo agrega al layout principal
        self.group_box = QGroupBox(inputs_maquina[1])
        self.group_box.setLayout(self.general_layout)
        self.main_layout.addWidget(self.group_box)
        
        # Crea un botón para iniciar el control mensual y lo agrega al layout general
        self.iniciar = QPushButton(inputs_maquina[2])
        self.general_layout.addWidget(self.iniciar)
        self.iniciar.clicked.connect(lambda: print("Fecha seleccionada:", self.date_box.date().toString("dd/MM/yyyy"))) 
        # Agrega un stretch al layout principal para alinear los widgets hacia la parte superior
        self.main_layout.addStretch()
        
        # Conecta las señales del botón 'Iniciar' a las funciones correspondientes:
        # 1. Limpia los layouts para reiniciar la interfaz de control.
        
        self.iniciar.clicked.connect(lambda _: self.limpiar_layout([self.general_layout, self.main_layout], self.user_id_f1,   # ← ahora es el físico seleccionado en el combo
            inputs_maquina[3],
            self.user_id_f2,
            self.fisico1.currentText(),
            self.fisico2.currentText()))
        
        
        # 2. Inicializa la interfaz gráfica de usuario para pruebas.
        self.iniciar.clicked.connect(lambda _: self.iniGUI(inputs_maquina=inputs_maquina))
        # 3. Ejecuta la función adicional para manipulación del botón.
        self.iniciar.clicked.connect(self.button_click)
        ''' '''        
        
        self.tabla = QTableWidget()
        self.tabla.setAlternatingRowColors(True)
        if hasattr(self, 'anual') and self.anual:
            mostrar_controles_anuales(self, self.tabla, equipo_filtrar=self.equipo_f)
        else:
            mostrar_controles_mensuales(self, self.tabla, equipo_filtrar=self.equipo_f)
        
        if hasattr(self, 'esTAC') and self.esTAC:
            mostrar_controles_tac(self, self.tabla, self.user_id, self.equipo_f)
        if hasattr(self, 'esiX_images') and self.esiX_images:
            mostrar_controles_imgIX_anual(self, self.tabla, self.user_id, self.equipo_f)
            if hasattr(self, 'date_box') and self.date_box:
                print("Cajita de fechas")
                self.date_box.setDisplayFormat('yyyy')
        if hasattr(self, 'esiX_images_mensu') and self.esiX_images_mensu:
            mostrar_controles_imgIX(self, self.tabla, self.user_id, self.equipo_f)
        if hasattr(self, 'esHC_images_mensu') and self.esHC_images_mensu:
            mostrar_controles_imgHC(self, self.tabla, self.user_id, self.equipo_f)
        if hasattr(self, 'esHC_images') and self.esHC_images:
            mostrar_controles_imgHC_anual(self, self.tabla, self.user_id, self.equipo_f)
        
       
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar")
        self.search_bar.textChanged.connect(self.filtrarTabla)
        
        # Container temporal para preview
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.addWidget(self.search_bar)
        preview_layout.addWidget(self.tabla)
        
        self.main_layout.addWidget(preview_container)
        self.main_layout.addStretch()
        
        # Guardar referencia al container
        
        preview_toolbar = QHBoxLayout()

        self.btn_delete_preview = QPushButton('Eliminar')
        self.edit_table_preview = QPushButton('Editar')
        self.accept_edit_preview = QPushButton('Aceptar')
        self.accept_edit_preview.hide()
        self.cancel_edit_preview = QPushButton('Cancelar')
        self.cancel_edit_preview.hide()
        self.date_box.dateChanged.connect(self.actualizar_fisicos)

        preview_toolbar.addWidget(self.btn_delete_preview)
        preview_toolbar.addWidget(self.edit_table_preview)
        preview_toolbar.addWidget(self.accept_edit_preview)
        preview_toolbar.addWidget(self.cancel_edit_preview)
        preview_toolbar.addWidget(self.search_bar)

        preview_layout.addLayout(preview_toolbar)
        preview_layout.addWidget(self.tabla)

        # Conectar eventos (sin self.ref porque aún no existe)
        if hasattr(self, 'esTAC') and self.esTAC:
            self.btn_delete_preview.clicked.connect(lambda: verificar_eliminarCT(self, self.tabla, "controles", None))
        elif hasattr(self, 'esiX_images') and self.esiX_images:
            self.btn_delete_preview.clicked.connect(lambda: verificar_eliminarCT_anual(self, self.tabla, "controles", None))
            print("Verificar eliminar ANUAL WASCALL")
        elif hasattr(self, 'esiX_images_mensu') and self.esiX_images_mensu and hasattr(self, 'esiX'):
            self.btn_delete_preview.clicked.connect(lambda: verificar_eliminarCT(self, self.tabla, "controles", None))
        elif hasattr(self, 'esHC_images') and self.esHC_images:
            self.btn_delete_preview.clicked.connect(lambda: verificar_eliminarCT_anual(self, self.tabla, "controles", None))
            print("Verificar eliminar ANUAL WASCALL")
           
      
        else:
            self.edit_table_preview.clicked.connect(lambda: verificar_editar(self, self.tabla, "controles", "ref", None))
            self.accept_edit_preview.clicked.connect(lambda: guardarEdicion(self, self.tabla, "controles", None))
            self.cancel_edit_preview.clicked.connect(lambda: cancelarEdicion(self))
            self.btn_delete_preview.clicked.connect(lambda: verificar_eliminar(self, self.tabla, "controles", None))
        
            
        self._preview_container = preview_container
        
        # Modificar iniciar para MOVER (no destruir)
        self.iniciar.clicked.disconnect()
        self.iniciar.clicked.connect(lambda: self._iniciar_moviendo_tabla(inputs_maquina))

    def _iniciar_moviendo_tabla(self, inputs_maquina):
        # 1. REMOVER tabla de preINIGI (sin destruir)
        if hasattr(self, '_preview_container'):
            self.main_layout.removeWidget(self._preview_container)
            self._preview_container.hide()
            # NO llamar deleteLater(), solo ocultar
        
        # 2. Limpiar layouts
        self.limpiar_layout(
            [self.general_layout, self.main_layout],
            self.user_id_f1,   # ← ahora es el físico seleccionado en el combo
            inputs_maquina[3],
            self.user_id_f2,
            self.fisico1.currentText(),
            self.fisico2.currentText()
        )
        # 3. Inicializar GUI normal
        self.iniGUI(inputs_maquina=inputs_maquina)
        self.button_click()
            
    # Limpia los layouts y crea una nueva referencia de control en la base de datos
    def limpiar_layout(self, layouts, user_id, maquina, user_id_f2=None,  nombre_fisico1=None, nombre_fisico2=None):

        fecha = self.date_box.date()
        # F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): se guarda el día
        # real elegido -- antes se descartaba con "MM/yyyy". create_control
        # (F2) ya identifica el control por (equipo, mes, año), así que
        # elegir cualquier día del mes correcto encuentra el mismo registro.
        fecha = fecha.toString("dd/MM/yyyy")
        for layout in layouts:
            while layout.count():

                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        print(f"user_id_f2 antes de create_control: {user_id_f2}")
        self.ref = create_control(self, maquina=maquina, fecha=fecha, user_id=nombre_fisico1, user_id_f2=user_id_f2)
        # F3: si create_control encontró un control YA EXISTENTE (de otro
        # día del mismo mes, o de una fecha histórica en formato viejo),
        # self.fecha_control debe reflejar el día REAL guardado en la BD,
        # no el día que se acaba de elegir para buscar -- si no, reabrir un
        # control corrompería su día de referencia (nombres de PDF,
        # búsqueda del reporte, fecha mostrada) con el día de la reapertura.
        self.fecha_control = self._fecha_real_del_control(self.ref) or fecha
        self.nombre_fisico1 = nombre_fisico1
        self.nombre_fisico2 = nombre_fisico2

    def _fecha_real_del_control(self, control_id):
        """Lee `controles.fecha` tal como quedó guardada para `control_id`
        (F3) -- fuente de verdad para self.fecha_control, en vez de asumir
        que es la fecha recién elegida en date_box."""
        if not control_id:
            return None
        try:
            conn = self.db_manager.obtener_conexion() if hasattr(self, 'equipo_f') and self.equipo_f != 'Tomógrafo' else Conexion().conectar()
            cursor = conn.cursor()
            cursor.execute("SELECT fecha FROM controles WHERE id = ?", (control_id,))
            fila = cursor.fetchone()
            return fila[0] if fila else None
        except Exception as e:
            print(f"Error leyendo fecha real del control {control_id}: {e}")
            return None

    def _fecha_control_para_nombre_archivo(self):
        """`self.fecha_control` para usar en un nombre de archivo sugerido
        (F3, SS4.4): con el día incluido, la fecha trae dos "/" -- un
        QFileDialog los interpreta como separador de ruta, no como texto."""
        return (self.fecha_control or "").replace("/", "-")

        
        #print(f"ID Sesión: {self.ref}")
    
    # Inicializa la interfaz gráfica de usuario (GUI) principal de la aplicación 
    def iniGUI(self, inputs_maquina = None):
        """
        Inicializa la interfaz gráfica de usuario (GUI) principal de la aplicación.

        Crea un diseño dividido en dos columnas:
        - A la izquierda: controles de prueba (formularios, tablas, menús desplegables).
        - A la derecha: visualización gráfica (p. ej., imágenes o resultados visuales).

        La función configura la estructura usando QVBoxLayout y QSplitter,
        permitiendo que ambas columnas sean redimensionables y mantengan proporciones iguales.
        """
        btn_volver = QPushButton('← Volver')
        btn_volver.clicked.connect(lambda: self._volver_a_preINIGI(inputs_maquina))
        # Crear layout vertical principal donde se colocará todo el contenido
        #self.main_layout = QVBoxLayout(self)
        #self.main_layout = self.main_layout.layout()
        finalizar_proceso = QPushButton('Finalizar proceso')
        
        # Crear un separador horizontal que divide la ventana en dos columnas (controles y gráficos)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)  # Ancho del divisor 

        # Crear layout izquierdo con el formulario de control
        test_control_layout = QWidget()
        _, _, self.commenu = self.controlTestWindow(inputs_maquina[4], lista_maquina=inputs_maquina)  # Cargar combo boxes de equipos
        if test_control_layout.layout() is None:
            test_control_layout.setLayout(self.general_layout)
        else:
            for i in range(self.general_layout.count()):
                test_control_layout.layout().addItem(self.general_layout.itemAt(i))
        if hasattr(self, 'fecha_control'):
            # F3: parser tolerante -- fecha_control puede traer día (nuevo,
            # dd/MM/yyyy) o no (registros históricos, MM/yyyy).
            fecha = _fecha_control_a_qdate(self.fecha_control)
            self.date_box.setDate(fecha)
        if hasattr(self, 'nombre_fisico1'):
            index = self.fisico1.findText(self.nombre_fisico1)
            if index >= 0:
                self.fisico1.setCurrentIndex(index)
            self.fisico1.setEnabled(False) 
        if hasattr(self, 'nombre_fisico2'):
            self.fisico2.setItemText(0, self.nombre_fisico2)  # Forzar actualización del texto
            self.fisico2.setEnabled(False)
    

        #self.general_layout.addWidget(self.date_box)  # Agregar caja de fecha al layout general
        
        # Crear layout derecho con los gráficos u otros elementos visuales
        graphics_layout = self.graphicsWindow()

        # Agregar ambas columnas al splitter (estructura dividida)
        splitter.addWidget(test_control_layout)
        splitter.addWidget(graphics_layout)

        # Evitar que las columnas puedan colapsar (desaparecer)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # Establecer el mismo nivel de prioridad de redimensionamiento para ambas columnas
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # Agregar el splitter al layout principal de la ventana
        self.main_layout.addWidget(splitter)
        #self.main_layout.addWidget(btn_volver)
        # Agregar botón de finalizar al layout principal
                                                                                                                                                                                                                                                                                                               
        
        # Reconectar señales                                                                                                           
       
    # Crear la ventana de control para pruebas mensuales cargando widgets desde un archivo Excel
    def controlTestWindow(self, sheet_name, lista_maquina = None):
        """
        Crea ventana de control optimizada dividida en submétodos
        
        Parámetros:
            sheet_name (str): Nombre de la hoja de Excel con la definición de widgets
        """
        #print(f"\nCreando ventana de control optimizada para {sheet_name}")
        
        try:
            # Inicialización básica
            toolbox = self._inicializar_toolbox(sheet_name, inputs_maquina=lista_maquina)
            
            # Configurar categorías
            self._configurar_categorias()
            
            # Configurar widgets de seguridad
            self._configurar_widgets_seguridad(sheet_name)
            
            # Configurar menús de equipos y seguridad
            self._configurar_menus_equipos_seguridad()
            
            # Configurar aspectos mecánicos y dosimétricos
            self._configurar_aspectos_mecanicos_dosimetricos()
            
            # Crear y configurar subtoolbox
            self._configurar_subtoolbox()
            
            # Configurar toolbox principal
            self._configurar_toolbox_principal(toolbox)
            
            # Configuraciones finales
            
            self._configuraciones_finales()
            #self._configurar_mlcs()
            
            
            # Retornar toolbox, comboboxes y combo_menu como esperaba el código original
            return toolbox, getattr(self, 'comboboxe', []), getattr(self, 'combo_menu', [])
            
        except Exception as e:
            print(f"Error en controlTestWindow: {e}")
            traceback.print_exc()
           
            return QToolBox(), [], []

    def _inicializar_toolbox(self, sheet_name, inputs_maquina = None):
        """Inicializa el toolbox y configuraciones básicas"""
        archivo = 'data/widgets.xlsx'
        toolbox = QToolBox()
        
        #print(f"Inicializando toolbox con archivo: {archivo} y hoja: {sheet_name}")

        try:
            # Encabezado general
            encabezado_result = self.setupBox(archivo, inputs_maquina[0])
            #print(f"Encabezado configurado: {type(encabezado_result)}")
            
            # Configurar fecha (F3: ver preINIGI, mismo formato con día)
            # nea = self.date_box.date().toString('MM/yyyy')
            # nueva_fecha = QDate.fromString(nea, 'MM/yyyy')
            # self.date_box.setDate(nueva_fecha)
            self.date_box.setDisplayFormat("dd/MM/yyyy")

            self.general_layout.addWidget(toolbox)

            # Cargar widgets de la hoja correspondiente
            print(f"Cargando widgets desde hoja: {sheet_name}")
            result = self.setupBox(archivo, sheet_name, main=False)
            
            if result and len(result) < 6:
                self.df, self.n, self.layouts, self.comboboxe = result
                #print(f"✓ Carga exitosa:")
                print(f"  - DataFrame: {len(self.df) if hasattr(self.df, '__len__') else 'No disponible'} filas")
                #print(f"  - Layouts: {len(self.layouts) if self.layouts else 0}")
                #print(f"  - ComboBoxes: {len(self.comboboxe) if self.comboboxe else 0}")
            else:
                print(f"✗ Error en setupBox: resultado inesperado {result}")
                self.df, self.n, self.layouts, self.comboboxe = None, 0, [], []
            
        except Exception as e:
            print(f"✗ Error al inicializar toolbox: {e}")
            import traceback
            traceback.print_exc()
           
            self.df, self.n, self.layouts, self.comboboxe = None, 0, [], []
        
        return toolbox

    def _configurar_categorias(self):
        """Configura las categorías base de widgets"""
        # Crear categorías base
        self.category1 = QWidget()
        self.category2 = QWidget()
        self.category3 = QWidget()
        self.category4 = QWidget()
        self.category5 = QWidget()
        print(f"Layouts disponibles: {len(self.layouts) if hasattr(self, 'layouts') and self.layouts else 0}")
        # Asignar layouts desde setupBox a las categorías
        if hasattr(self, 'layouts') and self.layouts:
            #print(f"Configurando {len(self.layouts)} layouts en categorías")
            for i, layout in enumerate(self.layouts, start=1):
                if i <= 5:  # Máximo 5 categorías
                    category = getattr(self, f'category{i}')
                    print(layout)
                    #print(f"Asignando layout {i} a category{i}")
                    if category.layout() is None:
                        category.setLayout(layout)
                    else:
                        # Si ya tiene layout, agregar items del nuevo layout
                        for j in range(layout.count()):
                            item = layout.itemAt(j)
                            if item:
                                category.layout().addItem(item)
        else:
            print("Warning: No hay layouts disponibles para configurar categorías")

    def _configurar_widgets_seguridad(self, sheet_name):
        """Configura widgets de seguridad con verificación de observaciones"""
        try:
            # Filtrar campos de seguridad
            self.df_seg_line = self.df.loc[
                (self.df.prueba == 'seguridad') & (self.df.widget_type == 'QLineEdit')
            ]['nombres']

            #print(f"\nCampos QLineEdit para seguridad: {len(self.df_seg_line)}")

            # Conectar verificación de observaciones con debouncing
            for line in self.df_seg_line:
                widget = getattr(self, line, None)
                if widget:
                    def crear_verificador(nombre):
                        def verificar_observacion(texto):
                            #print(f"Verificando observaciones en {nombre}: '{texto}'")
                            pass
                        return verificar_observacion
                    
                    verificador = crear_verificador(line)
                    # Usar el método de configuración de eventos directo
                    widget.textChanged.connect(lambda text, verificador=verificador: verificador(text))
                    
        except Exception as e:
            
        
            print(f"Error configurando widgets de seguridad: {e}")

    def _configurar_menus_equipos_seguridad(self):
        """Configura menús de equipos y seguridad"""
        try:
            # Filtrar widgets para equipos
            df_combo = self.df.loc[
                (self.df.prueba == 'equipo') &
                ((self.df.widget_type == 'QComboBox') | (self.df.widget_type == 'QLineEdit'))
            ]['nombres']

            # Filtrar widgets para seguridad
            df_combo_seguridad = self.df.loc[
                (self.df.prueba == 'seguridad') &
                (self.df.widget_type == 'QComboBox')
            ]['nombres']

            # Crear listas de widgets
            self.combo_menu = [getattr(self, combo, None) for combo in df_combo if getattr(self, combo, None)]
            self.combo_menu_seguridad = [getattr(self, combo, None) for combo in df_combo_seguridad if getattr(self, combo, None)]

            # Configurar combos de seguridad (cuñas)
            self.combos_seguridad = self._diccionario_combos_seguridad()

            #print(f"Configurados {len(self.combo_menu)} widgets de equipos y {len(self.combo_menu_seguridad)} de seguridad")
            
        except Exception as e:
            
            print(f"Error configurando menús: {e}")
            self.combo_menu = []
            self.combo_menu_seguridad = []
            self.combos_seguridad = {}
            
#############################################################################################

    # def _configurar_mlcs(self):
    #     """Configura menús de equipos y seguridad"""
    #     try:
    #         # Filtrar widgets para equipos
    #         df_combo = self.df.loc[
    #             (self.df.prueba == 'mlcs') &
    #             ((self.df.widget_type == 'QLineEdit'))
    #         ]['nombres']

           
       
           
    #     except Exception as e:
    #         print(f"Error configurando menús: {e}")
           
    #         self.mlc_data = []

############################################################################################################      

    def _diccionario_combos_seguridad(self):
        """Crea diccionario de combos de seguridad de manera segura"""
        try:
            return {
                15: {   "in"    : getattr(self, 'cuna_15_in', None), "out"  : getattr(self, 'cuna_15_out', None), 
                        "right" : getattr(self, 'cuna_15_ri', None), "left" : getattr(self, 'cuna_15_le' , None)},
                30: {   "in"    : getattr(self, 'cuna_30_in', None), "out"  : getattr(self, 'cuna_30_out', None), 
                        "right" : getattr(self, 'cuna_30_ri', None), "left" : getattr(self, 'cuna_30_le' , None)},
                45: {   "in"    : getattr(self, 'cuna_45_in', None), "out"  : getattr(self, 'cuna_45_out', None), 
                        "right" : getattr(self, 'cuna_45_ri', None), "left" : getattr(self, 'cuna_45_le' , None)},
                60: {   "in"    : getattr(self, 'cuna_60_in', None), "out"  : getattr(self, 'cuna_60_out', None), 
                        "right" : getattr(self, 'cuna_60_ri', None), "left" : getattr(self, 'cuna_60_le' , None)}
            }
        except Exception as e:
            
            print(f"Error creando combos de seguridad: {e}")
            return {}

    def _configurar_aspectos_mecanicos_dosimetricos(self):
        """Configura aspectos mecánicos y dosimétricos"""
        try:
            # Configurar categoría de equipos
            self.botonescombobox(self.category1, self.combo_menu, None)

            # Configurar opciones de cuñas
            self.comboBox_seguridad(self.combo_menu_seguridad)
            self.botonescombobox(self.category2, None, self.combos_seguridad)

            # Configurar aspectos mecánicos
            self.addsomething(
                layout=self.category3, df=self.df, typee="aspectos mecanicos",
                nombre_tabla='preguntas', datos_eliminar=1, ref=self.ref
            )
            # self.addsomething(
            #     layout=self.category5, df=self.df, typee="mlcs",
            #     nombre_tabla='preguntas', datos_eliminar=1, ref=self.ref
            # )

            # Configurar dosimetría
            if hasattr(self, 'esIX') and self.esIX:
                print("Configurando dosimetría para equipo IX")
                self.addsomething_ix(self.category4, self.df, "dosimetria",
                                 "dosimetriaMen", 0, ref=self.ref, usarid=True)


            else:
                self.addsomething(self.category4, self.df, "dosimetria",
                                "dosimetriaMen", 0, ref=self.ref)
                
               
            
            self.generar_reporte_btn = QPushButton('Generar reporte PDF')
            self.general_layout.addWidget(self.generar_reporte_btn)

        except Exception as e:
            
            print(f"Error configurando aspectos mecánicos/dosimétricos: {e}")

    def _configurar_subtoolbox(self):
        """Configura el subtoolbox para aspectos mecánicos"""
        try:
            # Crear subtoolbox para aspectos mecánicos
            self.subtool = QToolBox()
            
            # Configurar tablas de indicadores
            self._crear_tablas_indicadores()
            
            # Añadir preguntas, tamaño de campo e imagen
            self._configurar_elementos_adicionales()
            
        except Exception as e:
            
            print(f"Error configurando subtoolbox: {e}")
            self.subtool = QWidget()

    def _crear_tablas_indicadores(self):
        """Crea las tablas de indicadores angulares"""
        try:
            headers = ["Nivel", "Indicador luminoso consola", "Indicador luminoso equipo"]
            
            # Indicadores angulares del brazo
            datos_brazo = [["0°", "", ""], ["90°", "", ""], ["180°", "", ""], ["270°", "", ""]]
            widget1, _ = self.createSimpleTable1(4, 3, headers, datos_brazo, "indicadores_brazo", self.ref)
            self.subtool.addItem(widget1, "Indicadores angulares del brazo")

            # Indicadores angulares del colimador (H1.2, auditoría 2026-07-14:
            # faltaba la fila 180° -- el brazo sí la tiene; el colimador
            # también gira las 4 posiciones en el control real).
            datos_colimador = [["0°", "", ""], ["90°", "", ""], ["180°", "", ""], ["270°", "", ""]]
            widget2, _ = self.createSimpleTable1(4, 3, headers, datos_colimador, "indicadores_angulares_colimador", self.ref)
            self.subtool.addItem(widget2, "Indicadores angulares del colimador")
            
        except Exception as e:
            
            
            print(f"Error creando tablas de indicadores: {e}")

    def _configurar_elementos_adicionales(self):
        """Configura elementos adicionales del subtoolbox"""
        try:
            # Preguntas
            self.subtool.addItem(self.category3, 'Resultados de aspectos mecánicos')

            # Tamaño de campo
            self.subtool.addItem(self.fieldSize('tamano_campo', self.ref), 'Tamaño de campo')

            # Imagen del campo
            self.imagen_campo = self.imagenUpLoader()
            self.boton_aceptar.clicked.connect(self.subirlisto)
            self.subtool.addItem(self.imagen_campo, 'Imagen del campo')
            
        except Exception as e:
           
            print(f"Error configurando elementos adicionales: {e}")

    def _configurar_toolbox_principal(self, toolbox):
        """Configura el toolbox principal con todas las categorías"""
        try:
            # Añadir categorías al toolbox
            toolbox.addItem(self.category1, "EQUIPOS")
            toolbox.addItem(self.category2, "SEGURIDAD")
            toolbox.addItem(self.subtool, "ASPECTOS MECÁNICOS")
            toolbox.addItem(self.category4, "ASPECTOS DOSIMÉTRICOS")
            toolbox.addItem(self.category5, "MLCS")
            
        except Exception as e:
           
            print(f"Error configurando toolbox principal: {e}")

    def _configuraciones_finales(self):
        """Configuraciones finales y optimizaciones"""
        try:
            # Configurar botones y conexiones finales
            self.botones_finales = set()
            self.setupButtonConnections(self.df, maquina=None)
            self.discrepancias()
            self.generar_reporte_btn.clicked.connect(self.generar_reporte_pdf)
            self._configurar_mlcs()
            self._configurar_starshot()
        except Exception as e:
           
            print(f"Error en configuraciones finales: {e}")

    def _configurar_eventos(self, widget, callback, timer_id):
        """Configura evento con debouncing para mejorar rendimiento de UI"""
        if not hasattr(self, '_debounce_timers'):
            self._debounce_timers = {}
            
        def debounced_callback():
            if timer_id in self._debounce_timers:
                self._debounce_timers[timer_id].stop()
            
            timer = QTimer()
            timer.timeout.connect(callback)
            timer.setSingleShot(True)
            timer.start(300)  # 300ms delay
            self._debounce_timers[timer_id] = timer
            
        widget.textChanged.connect(debounced_callback)
        return debounced_callback
    def _configurar_mlcs(self):
        try:
            self._mlc_analyzer = MLC_MEASSUREMENT()
            
            self._dcm_mlc_path = None
            
            btn_analizar = QPushButton("Analizar Picketfence")
            btn_analizar.setEnabled(True)
            self.category5.layout().addWidget(btn_analizar)
          
            
            self._btn_analizar_mlc = btn_analizar
            
            self.BotonSubir.clicked.connect(self._seleccionar_dcm)
            btn_analizar.clicked.connect(self._ejecutar_analisis_mlc)
        except Exception as e:
          
            print(e)
            
    def _seleccionar_dcm(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen DICOM", "", "DICOM (*.dcm)")
        if path:
            self._dcm_mlc_path = path
            self._btn_analizar_mlc.setEnabled(True)
            self.BotonSubir.setText(f"{path.split('/')[-1]}")
    def _ejecutar_analisis_mlc(self):
        print("Boton Ejecutar analisis activado")
        try:
            tolerance = float(self.ln_tolerance_mlc.text())
            action_tolerance = float(self.ln_action_tolerance.text())
            
            
            from pylinac.core.image_generator import generate_picketfence, GaussianFilterLayer, PerfectFieldLayer, RandomNoiseLayer, AS1200Image
            from pylinac.picketfence import Orientation
            pf_file = "erroneous_leaves.dcm"
            generate_picketfence(
                    simulator=AS1200Image(sid=1000),
                    field_layer=PerfectFieldLayer,  # this applies a non-uniform intensity about the CAX, simulating the horn effect
                    file_out=pf_file,
                    final_layers=[
                        PerfectFieldLayer(field_size_mm=(5, 10), cax_offset_mm=(2.5, 90)),  # a 10mm gap centered over the picket
                        PerfectFieldLayer(field_size_mm=(5, 5), cax_offset_mm=(12.5, -87.5)),  # a 2.5mm extra opening of one leaf
                        PerfectFieldLayer(field_size_mm=(5, 5), cax_offset_mm=(22.5, -49)),  # a 1mm extra opening of one leaf
                        GaussianFilterLayer(sigma_mm=1),
                        RandomNoiseLayer(sigma=0.03)  # add salt & pepper noise
                    ],
                    pickets=10,
                    picket_spacing_mm=20,
                    picket_width_mm=5,  # wide-ish gap
                    orientation=Orientation.UP_DOWN,
            )
            data = self._mlc_analyzer.picket_fence(self._dcm_mlc_path, tolerance, action_tolerance)
            p = data.pickets[0]
            print("dist2cax:", p.dist2cax)
            print("orientation:", p.orientation)
            imagen_mlc = (self._dcm_mlc_path)
           
            pf_db_insertion(self.ref, self.fecha_control, self.equipo_f , action_tolerance, tolerance, self.nombre_fisico1, self.nombre_fisico2, imagen_mlc)
            
            m = p.mlc_meas[0]
            z = p.mlc_meas[1]
            print("leaf_num:", m.leaf_num)
            print("leaf_center_px:", m.leaf_center_px)
            print("position:", m.position)
            print("position_mm:", m.position_mm[0], " ", z.position_mm)
            print("error:", m.error)
            print("passed:", m.passed)
            print("leaf_width_px:", m.leaf_width_px)
            print("picket_num:", m.picket_num)
            
            self._mostrar_resultados_mlc(data, tolerance, action_tolerance)
           # print(data)
        except Exception as e:
          
            print(e)
        
    def _procesar_data_mlc(self, data, tolerance, action_tolerance):
        results = data.results_data()
        errors_by_leaf = results.mlc_errors_by_leaf 
        positions_by_leaf = results.mlc_positions_by_leaf
        n_pickets = results.number_of_pickets
        
        leafs = []
        for leaf_str, errors in errors_by_leaf.items():
            if len(errors) != n_pickets:
                continue
            leaf_num = int(leaf_str)
            max_abs_error = max(abs(e) for e in errors)
            leafs.append({"leaf":        leaf_num,
            "errors":      errors,           # lista, una por picket
            "positions":   positions_by_leaf.get(leaf_str, []),
            "max_error":   max_abs_error,
            "over_tol":    max_abs_error > tolerance,
            "over_action": max_abs_error > action_tolerance,})
        leafs.sort(key = lambda x: x["leaf"])
        error_matrix = np.full((len(leafs), n_pickets), np.nan)
        for row_i, hoja in enumerate(leafs):
            for col_i, err in enumerate(hoja["errors"]):
                if col_i < n_pickets:
                    error_matrix[row_i, col_i] = err

        # Por picket → para tabla error_picket
        picket_stats = []
        for p_idx in range(n_pickets):
            col = error_matrix[:, p_idx]
            picket_stats.append({
                "picket":             p_idx,
                "picket_mean_error":  float(np.nanmean(np.abs(col))),
                "picket_max_error":   float(np.nanmax(np.abs(col))),
            })

        # Por lámina → para tabla leaf_error
        for row_i, hoja in enumerate(leafs):
            hoja["leaf_error"] = float(np.nanstd(error_matrix[row_i, :]))
        return {
            "leafs": leafs, "n_pickets": n_pickets, 
            "tolerance": tolerance, "action_tolerance": action_tolerance,
            "offsets_cax":     results.offsets_from_cax_mm,
            "max_error_mm":    results.max_error_mm,
            "max_error_leaf":  results.max_error_leaf,
            "max_error_picket": results.max_error_picket,
            "percent_passing": results.percent_leaves_passing,
            "passed":          results.passed,
            "skew":            results.mlc_skew,
            "spacing_mm":      results.mean_picket_spacing_mm,
            "cax": results.cax if hasattr(results, 'cax') else None,
            "picket_stats": picket_stats,
            }
        
    def _mostrar_resultados_mlc(self, data, tolerance, action_tolerance):
        processed = self._procesar_data_mlc(data, tolerance, action_tolerance)
 
        tab = QWidget()
        tab_layout = QHBoxLayout(tab)
 
        nombre_tab = f"MLC {QDate.currentDate().toString('MM/yyyy')}"
        self.tab_widget.addTab(tab, nombre_tab)
        self.tab_widget.setCurrentWidget(tab)
        print("PROCESSED")
        print(processed)
        # ── Panel izquierdo (visualización interactiva) ───────────────────────
        panel_izq = QWidget()
        panel_izq.setMinimumWidth(400)
        layout_izq = QVBoxLayout(panel_izq)
        layout_izq.setContentsMargins(0, 0, 0, 0)
        layout_izq.setSpacing(4)
 
        mpl = get_matplotlib_components()
        FigureCanvas      = mpl['FigureCanvas']
        NavigationToolbar = mpl['NavigationToolbar']
 
        fig    = Figure(figsize=(6, 8))
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, panel_izq)
        toolbar.setFixedHeight(28)
 
        layout_izq.addWidget(toolbar)
        layout_izq.addWidget(canvas)
 
        # ── Panel derecho (resumen + tabla) ──────────────────────────────────
        panel_der = QWidget()
        panel_der.setMaximumWidth(320)
        layout_der = QVBoxLayout(panel_der) 
 
        lbl_estado = QLabel("Aprobado" if processed["passed"] else "Fallido")
        lbl_estado.setProperty("mlc_estado", "passed" if processed["passed"] else "failed")
        lbl_estado.setAlignment(Qt.AlignCenter)
        lbl_estado.style().unpolish(lbl_estado)
        lbl_estado.style().polish(lbl_estado)
 
        lbl_resumen = QLabel(
            f"Láminas {processed['percent_passing']:.1f}%\n"
            f"Error máximo: {processed['max_error_mm']:.4f} mm\n"
            f" Picket {processed['max_error_picket']}, Hoja {processed['max_error_leaf']}\n"
            f"Tolerancia: {processed['tolerance']} mm\n"
            f"Tol. accion: {processed['action_tolerance']} mm\n"
            f"Espaciado: {processed['spacing_mm']:.2f} mm\n"
            f"Skew MLC: {processed['skew']:.6f}°"
        )
        lbl_resumen.setObjectName("lbl_resumen_mlc")
        lbl_resumen.setWordWrap(True)
        lbl_resumen.setAlignment(Qt.AlignTop | Qt.AlignLeft)
 
        criticas        = [h for h in processed["leafs"] if h["over_tol"]]
        criticas_sorted = sorted(criticas, key=lambda x: x["max_error"], reverse=True)
 
        lbl_tabla_titulo = QLabel(f"Láminas fuera de tolerancia: {len(criticas)}")
 
        tabla = QTableWidget(max(len(criticas), 1), 3)
        tabla.setObjectName("tabla_criticas")
        tabla.setHorizontalHeaderLabels(["Lámina", "Max error (mm)", "Picket"])
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabla.verticalHeader().setVisible(False)
        tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabla.setAlternatingRowColors(True)
        tabla.setMaximumHeight(220)
 
        if criticas_sorted:
            for row, hoja in enumerate(criticas_sorted):
                worst_picket = hoja["errors"].index(max(hoja["errors"], key=abs))
                for col, valor in enumerate([
                    str(hoja["leaf"]),
                    f"{hoja['max_error']:.4f}",
                    str(worst_picket)
                ]):
                    item = QTableWidgetItem(valor)
                    item.setTextAlignment(Qt.AlignCenter)
                    tabla.setItem(row, col, item)
        else:
            item = QTableWidgetItem("No hay láminas fuera de tolerancia")
            item.setTextAlignment(Qt.AlignCenter)
            tabla.setItem(0, 0, item)
            tabla.setSpan(0, 0, 1, 3)
        
        
        layout_der.addWidget(lbl_estado)
        layout_der.addSpacing(6)
        layout_der.addWidget(lbl_resumen)
        layout_der.addSpacing(8)
        layout_der.addWidget(lbl_tabla_titulo)
        layout_der.addWidget(tabla)
        layout_der.addStretch()
        btn_pdf = QPushButton("Generar PDF")
        btn_pdf.setObjectName("btn_generar_pdf")
        layout_der.addSpacing(12)
        layout_der.addWidget(btn_pdf)

        def _on_generar_pdf():
            from PyQt5.QtWidgets import QFileDialog, QMessageBox
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar reporte MLC",
                f"QA_MLC_{self._fecha_control_para_nombre_archivo()}.pdf",
                "PDF (*.pdf)"
            )
            if not path:
                return
            try:
                generar_reporte_mlc_pdf(self.ref, nombre_pdf=path, temp=False)
                QMessageBox.information(self, "Reporte generado",
                                        f"PDF guardado en:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

        btn_pdf.clicked.connect(_on_generar_pdf)
 
        # ── Ensamblar layout ──────────────────────────────────────────────────
        tab_layout.addWidget(panel_izq, stretch=3)
        tab_layout.addWidget(panel_der, stretch=1)
 
        # ── Conectar interactividad (peine + detalle por picket) ──────────────
        # Debe ir DESPUÉS de addWidget para que el canvas tenga tamaño de Qt
        
        btn_toggle = QPushButton("Ver imagen DICOM")
        btn_toggle.setCheckable(True)
        layout_izq.addWidget(btn_toggle)

        def _toggle_vista(checked):
            if checked:
                btn_toggle.setText("Ver peine")
                self._dibujar_mlc_imagen(fig, canvas, data, processed)
            else:
                btn_toggle.setText("Ver imagen DICOM")
                _dibujar_peine(fig, canvas, processed)

        btn_toggle.clicked.connect(_toggle_vista)
        
        tab_perfiles = QWidget()
        layout_perfiles = QVBoxLayout(tab_perfiles)
        fig_p = Figure(figsize=(12, 5))
        canvas_p = FigureCanvas(fig_p)
        toolbar_p = NavigationToolbar(canvas_p, tab_perfiles)
        layout_perfiles.addWidget(toolbar_p)
        layout_perfiles.addWidget(canvas_p)
        self.tab_widget.addTab(tab_perfiles, f"Perfiles {QDate.currentDate().toString('MM/yyyy')}")
        _dibujar_perfiles_picket(fig_p, canvas_p, processed)
        # ── Tab asimetría bancos ──────────────────────────────────────────────
        tab_bancos = QWidget()
        layout_bancos = QVBoxLayout(tab_bancos)
        fig_b = Figure(figsize=(11, 6))
        canvas_b = FigureCanvas(fig_b)
        toolbar_b = NavigationToolbar(canvas_b, tab_bancos)
        layout_bancos.addWidget(toolbar_b)
        layout_bancos.addWidget(canvas_b)
        #self.tab_widget.addTab(tab_bancos, f"Bancos A/B {QDate.currentDate().toString('MM/yyyy')}")
        #_dibujar_asimetria_bancos(fig_b, canvas_b, processed)
    
        # ── Tab varianza inter-picket ─────────────────────────────────────────
        tab_var = QWidget()
        layout_var = QVBoxLayout(tab_var)
        fig_v = Figure(figsize=(11, 7))
        canvas_v = FigureCanvas(fig_v)
        toolbar_v = NavigationToolbar(canvas_v, tab_var)
        layout_var.addWidget(toolbar_v)
        layout_var.addWidget(canvas_v)
        self.tab_widget.addTab(tab_var, f"Varianza {QDate.currentDate().toString('MM/yyyy')}")
        _dibujar_varianza_interpicket(fig_v, canvas_v, processed)
        
        
        # Ventana de analisis estadistico:
        tab_analisis = QWidget()
        layout_analisis = QVBoxLayout(tab_analisis)
        fig_a = Figure(figsize=(13, 9))
        canvas_a = FigureCanvas(fig_a)
        toolbar_a = NavigationToolbar(canvas_a, tab_analisis)
        layout_analisis.addWidget(toolbar_a)
        layout_analisis.addWidget(canvas_a)
        self.tab_widget.addTab(tab_analisis, f"Análisis {QDate.currentDate().toString('MM/yyyy')}")
        _dibujar_analisis_estadistico(fig_a, canvas_a, processed)
        
        #leaf_stats(processed)
        self._estado_viz_mlc = _conectar_interactividad(fig, canvas, data, processed)
        
        
        
        ###### INSERCIÓN DE DATOS ############
        
        pf_picket_error_insertion(self.ref, processed)
        pf_leaf_error_insertion(self.ref, processed)
        pf_highest_leaf_errors_insertion(self.ref, processed, 10)
    def _dibujar_mlc_imagen(self, fig, canvas, pf_obj, processed):
        from matplotlib.patches import FancyArrowPatch
        

        fig.clear()
        ax = fig.add_subplot(111)

        # ── Imagen DICOM ─────────────────────────────────────────────
        img_array = pf_obj.image.array
        ax.imshow(img_array, cmap='gray', origin='upper',
                aspect='equal', interpolation='lanczos')

        # ── Factor de magnificación ──────────────────────────────────
        ds = pydicom.dcmread(self._dcm_mlc_path)
        pixel_spacing = pf_obj.image.dpmm  # dots per mm → invertir para mm/px
        px_spacing_iso = 1 / pixel_spacing      # mm/px en isocentro

        tol    = processed["tolerance"]
        action = processed["action_tolerance"]

        # ── Overlay por lámina ───────────────────────────────────────
        for picket in pf_obj.pickets:
            for meas in picket.mlc_meas:
                x_ideal_px = meas.position[0]
                y_px       = meas.leaf_center_px
                width_px   = meas.leaf_width_px
                error_mm   = meas.error[0]          # con signo
                error_abs  = abs(error_mm)
                passed     = bool(meas.passed[0])

                color = _error_color(error_abs, tol, action)

                # Rectángulo en posición ideal (referencia)
                from matplotlib.patches import Rectangle
                rect = Rectangle(
                    (x_ideal_px - 2, y_px - width_px / 2),
                    4, width_px,
                    linewidth=0.8,
                    edgecolor=color,
                    facecolor='none',
                    alpha=0.6,
                    linestyle='--'
                )
                ax.add_patch(rect)

                # Flecha desde posición ideal hasta posición real
                delta_px   = error_mm / px_spacing_iso
                x_real_px  = x_ideal_px + delta_px
                ax.plot(
                    [x_ideal_px - 20, x_ideal_px + 20],
                    [y_px+4, y_px+4],
                    color=color,
                    linestyle='--',
                    linewidth=1
                )
                ax.annotate(
                    "",
                    xy=(x_real_px, y_px+4),
                    xytext=(x_ideal_px, y_px+4),
                    arrowprops=dict(
                        arrowstyle="<->",
                        color=color,
                        lw=1.2,
                        mutation_scale=12
                    )
                )

        # ── CAX ──────────────────────────────────────────────────────
        cax = processed.get("cax")
        if cax:
            ax.plot(cax.x, cax.y, '+', color='#c1df08',
                    markersize=14, markeredgewidth=2, label='CAX')

        # ── Leyenda ──────────────────────────────────────────────────
        import matplotlib.patches as mpatches
        
        legend_patches = [
            mpatches.Patch(color=_COL_OK,   label="Dentro de tol."),
            mpatches.Patch(color=_COL_WARN, label=f">{tol*0.8:.2f} mm"),
            mpatches.Patch(color=_COL_FAIL, label=f"Fuera (>{tol} mm)"),
        ]
        ax.legend(handles=legend_patches, loc='lower left',
                fontsize=7, framealpha=0.5, facecolor='#1a1a1a',
                labelcolor='white')

        ax.set_axis_off()
        ax.set_title("Imagen DICOM — Desplazamiento de láminas",
                    fontsize=11, fontweight='bold')
        fig.tight_layout()
        canvas.draw()
        
        
        
    def _dibujar_mlc(self, fig, canvas, processed):
        
        from matplotlib.patches import Rectangle

        fig.clear()
        ax = fig.add_subplot(111)

        hojas  = processed["leafs"]
        tol    = processed["tolerance"]
        n_pick = processed["n_pickets"]

        if not hojas:
            ax.text(0.5, 0.5, "Sin datos", transform=ax.transAxes,
                    ha='center', va='center')
            canvas.draw()
            return

        leaf_nums = [h["leaf"] for h in hojas]
        matrix = [
            [abs(h["errors"][p]) if p < len(h["errors"]) else float('nan')
            for p in range(n_pick)]
            for h in hojas
        ]

        mat = np.array(matrix)

        im = ax.imshow(mat, aspect='auto', cmap='RdYlGn_r',
                    vmin=-tol * 1.5, vmax=tol * 1.5,
                    interpolation='nearest')

        ax.set_yticks(range(len(leaf_nums)))
        ax.set_yticklabels(leaf_nums, fontsize=7)
        ax.set_xticks(range(n_pick))
        ax.set_xticklabels([f"P{i}" for i in range(n_pick)], fontsize=9)
        ax.set_xlabel("Picket", fontsize=10)
        ax.set_ylabel("Lámina", fontsize=10)
        ax.set_title("Error por lámina (mm)", fontsize=11, fontweight='bold')

        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
        cbar.ax.axhline(y=tol, color='#ec2022', linewidth=1.5, linestyle='--')
        cbar.set_label("Error (mm)", fontsize=9)

        for row_i, hoja in enumerate(hojas):
            for col_i, err in enumerate(hoja["errors"]):
                if abs(err) > tol:
                    ax.add_patch(Rectangle(
                        (col_i - 0.5, row_i - 0.5), 1, 1,
                        fill=False, edgecolor='#ec2022', linewidth=2
                    ))

        fig.tight_layout()
        canvas.draw()


    """Todo lo anterior es exclusivamente para el analisis de pylinac de picket fence, es decir, para colimadores en esa disposición y el QA ajustado a 50mm de cada uno """

    #################################################################################################                                               ANALISIS SPOKE SHOT (ANGULAR)
    

    def _configurar_starshot(self):
        """
        Inicializa el analizador de Starshot y conecta los botones de la UI.
        Llama este método desde __init__ o desde el método de configuración
        de tu pestaña mensual, igual que _configurar_mlcs.
        """
        try:
            self._starshot_analyzer = STARSHOT_MEASUREMENT()
            self._dcm_mlc_path = None
    
            btn_analizar_ss = QPushButton("Analizar Spoke Shot")
            btn_analizar_ss.setEnabled(False)
            # Agrega el botón al layout de la categoría correspondiente
            # Ajusta 'self.category_starshot' al widget correcto de tu UI
            self.category5.layout().addWidget(btn_analizar_ss)
    
            self._btn_analizar_starshot = btn_analizar_ss
    
            # Reutiliza un botón de subida independiente o crea uno nuevo
            # Si ya tienes self.BotonSubirStarshot en tu .ui:
            
            self._btn_analizar_starshot.setEnabled(True)
            btn_analizar_ss.clicked.connect(self._ejecutar_analisis_starshot)
    
        except Exception as e:
            print(f"[_configurar_starshot] {e}")
    
    
    def _seleccionar_dcm_starshot(self):
        """Abre diálogo para elegir el .dcm del spoke shot."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar DICOM Spoke Shot", "", "DICOM (*.dcm)"
        )
        if path:
            self._dcm_starshot_path = path
            self._btn_analizar_starshot.setEnabled(True)
            self.BotonSubirStarshot.setText(path.split("/")[-1])
    
    
    def _ejecutar_analisis_starshot(self):
        """Lee la tolerancia del campo de texto, corre el análisis y muestra resultados."""
        print("[Starshot] Ejecutando análisis...")
        
        
        try:
            print("Datos dicom: ", pydicom.dcmread(self._dcm_mlc_path))
            tolerance = float(self.ln_tolerance_starshot.text())

            # Leer SID — dejar vacío si el DICOM ya lo trae
            sid_text = self.ln_sid_starshot.text()
            print("EL SID ES: ")
            print(sid_text)
            sid = float(sid_text) if sid_text is not None else None

            ss_obj = self._starshot_analyzer.analyze(
                self._dcm_mlc_path,
                tolerance=tolerance,
                sid=sid,
            )
            rd           = ss_obj.results_data() 
            processed    = procesar_data_starshot(ss_obj, tolerance)
            starshot_insert(self.ref, self.fecha_control, self.equipo_f, sid, tolerance, self.nombre_fisico1, self.nombre_fisico2, self._dcm_mlc_path)
            print("Datos calculados")
            print(processed)
            estadisticas = analisis_profundo_starshot(ss_obj, rd)
            print("Diccionario con estadisticas")
            print(estadisticas)
            
            self._mostrar_resultados_starshot(ss_obj, tolerance)
            
            
    
        except Exception as e:
            if "sid" in str(e).lower() or "source-to-image" in str(e).lower():
                QMessageBox.warning(self, "SID requerido",
                    "El DICOM no contiene RTImageSID.\n"
                    "Ingresa el SID en mm (ej: 1000).")
            else:
                QMessageBox.critical(self, "Error en análisis", str(e))
    
    def _mostrar_resultados_starshot(self, ss_obj, tolerance: float):
        processed    = procesar_data_starshot(ss_obj, tolerance)
        rd           = ss_obj.results_data()
        
        estadisticas = analisis_profundo_starshot(ss_obj, rd)

        starshot_residual_statistics_insert(self.ref, estadisticas)
        starshot_angles_insertion(self.ref, processed)
        starshot_angular_uniformity_insert(self.ref, estadisticas)

        # ── Tab principal ─────────────────────────────────────────────
        tab = QWidget()
        tab_layout = QHBoxLayout(tab)
        nombre_tab = f"Starshot {QDate.currentDate().toString('MM/yyyy')}"
        self.tab_widget.addTab(tab, nombre_tab)
        self.tab_widget.setCurrentWidget(tab)

        panel_izq = QWidget()
        panel_izq.setMinimumWidth(400)
        layout_izq = QVBoxLayout(panel_izq)
        layout_izq.setContentsMargins(0, 0, 0, 0)
        layout_izq.setSpacing(4)

        mpl = get_matplotlib_components()
        FigureCanvas      = mpl["FigureCanvas"]
        NavigationToolbar = mpl["NavigationToolbar"]

        fig    = Figure(figsize=(6, 6))
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, panel_izq)
        toolbar.setFixedHeight(28)
        layout_izq.addWidget(toolbar)
        layout_izq.addWidget(canvas)

        # ── Panel derecho ─────────────────────────────────────────────
        panel_der = QWidget()
        panel_der.setMaximumWidth(320)
        layout_der = QVBoxLayout(panel_der)

        lbl_estado = QLabel(" " if processed["passed"] else " ")
        lbl_estado.setProperty("mlc_estado", "passed" if processed["passed"] else "failed")
        lbl_estado.setAlignment(Qt.AlignCenter)
        lbl_estado.style().unpolish(lbl_estado)
        lbl_estado.style().polish(lbl_estado)

        res = estadisticas["residuos_interseccion"]
        uni = estadisticas["uniformidad_angular"]

        lbl_resumen = QLabel(
            f"Radio convergencia: {processed['radius_mm']:.4f} mm\n"
            f"Tolerancia: {tolerance:.2f} mm\n"
            f"Centro: ({processed['center_x_mm']:+.3f}, {processed['center_y_mm']:+.3f}) mm\n"
            f"Rayos detectados: {processed['n_spokes']}\n"
            f"─────────────────────\n"
            f"RMS residuos: {res['rms_mm']:.4f} mm\n"
            f"Máx residuo: {res['max_mm']:.4f} mm\n"
            f"Max error sep.: {uni['max_error_sep_deg']:.3f}°\n"
            f"Intersecciones: {estadisticas['n_intersecciones_usadas']}"
        )
        lbl_resumen.setObjectName("lbl_resumen_starshot")
        lbl_resumen.setWordWrap(True)
        lbl_resumen.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        fallidos        = [s for s in processed["spokes"] if not s["passed"]]
        lbl_tabla_titulo = QLabel(f"Rayos fuera de tolerancia: {len(fallidos)}")

        tabla = QTableWidget(max(len(processed["spokes"]), 1), 2)
        tabla.setObjectName("tabla_criticas_starshot")
        tabla.setHorizontalHeaderLabels(["Ángulo (°)", "Desviación (°)"])
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabla.verticalHeader().setVisible(False)
        tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabla.setAlternatingRowColors(True)
        tabla.setMaximumHeight(220)

        for row, spoke in enumerate(processed["spokes"]):
            for col, valor in enumerate([
                f"{spoke['angle_deg']:.1f}",
                f"{spoke['deviation_deg']:+.4f}",
            ]):
                item = QTableWidgetItem(valor)
                item.setTextAlignment(Qt.AlignCenter)
                tabla.setItem(row, col, item)

        layout_der.addWidget(lbl_estado)
        layout_der.addSpacing(6)
        layout_der.addWidget(lbl_resumen)
        layout_der.addSpacing(8)
        layout_der.addWidget(lbl_tabla_titulo)
        layout_der.addWidget(tabla)
        layout_der.addStretch()

        # ── Botón PDF ─────────────────────────────────────────────────
        btn_pdf = QPushButton("Generar PDF")
        btn_pdf.setObjectName("btn_generar_pdf")
        layout_der.addSpacing(12)
        layout_der.addWidget(btn_pdf)

        def _on_generar_pdf():
            from PyQt5.QtWidgets import QFileDialog, QMessageBox
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar reporte Starshot",
                f"QA_Starshot_{self._fecha_control_para_nombre_archivo()}.pdf",
                "PDF (*.pdf)"
            )
            if not path:
                return
            try:
                generar_reporte_starshot_pdf(
                    self.ref,
                    radius_mm        = processed["radius_mm"],
                    max_residuo_mm   = res["max_mm"],
                    n_intersecciones = estadisticas["n_intersecciones_usadas"],
                    center_x_mm      = processed["center_x_mm"],
                    center_y_mm      = processed["center_y_mm"],
                    n_spokes         = processed["n_spokes"],
                    nombre_pdf       = path,
                    temp             = False,
                )
                QMessageBox.information(self, "Reporte generado",
                                        f"PDF guardado en:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

        btn_pdf.clicked.connect(_on_generar_pdf)

        # ── Ensamblar layout ──────────────────────────────────────────
        tab_layout.addWidget(panel_izq, stretch=3)
        tab_layout.addWidget(panel_der, stretch=1)

        btn_toggle = QPushButton("Ver imagen DICOM")
        btn_toggle.setCheckable(True)
        layout_izq.addWidget(btn_toggle)

        def _toggle_vista_ss(checked):
            if checked:
                btn_toggle.setText("Ver rueda de rayos")
                dibujar_starshot_imagen(fig, canvas, ss_obj, processed)
            else:
                btn_toggle.setText("Ver imagen DICOM")
                self._estado_viz_starshot = conectar_interactividad_starshot(
                    fig, canvas, ss_obj, processed)

        btn_toggle.clicked.connect(_toggle_vista_ss)
        self._estado_viz_starshot = conectar_interactividad_starshot(
            fig, canvas, ss_obj, processed)

        # ── Tab residuos ──────────────────────────────────────────────
        tab_res = QWidget()
        layout_res = QVBoxLayout(tab_res)
        fig_r = Figure(figsize=(12, 5))
        canvas_r = FigureCanvas(fig_r)
        toolbar_r = NavigationToolbar(canvas_r, tab_res)
        layout_res.addWidget(toolbar_r)
        layout_res.addWidget(canvas_r)
        self.tab_widget.addTab(tab_res, f"Residuos {QDate.currentDate().toString('MM/yyyy')}")
        _dibujar_residuos_starshot(fig_r, canvas_r, estadisticas)

        # ── Tab uniformidad angular ───────────────────────────────────
        tab_uni = QWidget()
        layout_uni = QVBoxLayout(tab_uni)
        fig_u = Figure(figsize=(10, 5))
        canvas_u = FigureCanvas(fig_u)
        toolbar_u = NavigationToolbar(canvas_u, tab_uni)
        layout_uni.addWidget(toolbar_u)
        layout_uni.addWidget(canvas_u)
        self.tab_widget.addTab(tab_uni, f"Uniformidad {QDate.currentDate().toString('MM/yyyy')}")
        _dibujar_uniformidad_angular(fig_u, canvas_u, estadisticas)
        
            
    
    
    # Añade widgets de tipo QLineEdit a un layout específico, con funcionalidad de carga y guardado de datos
    def addsomething(self, layout, df, typee, nombre_tabla, datos_eliminar, ref, usarid=False, anual=False):
        """Añade los QLineEdit de una prueba y los conecta al guardado en BD.

        H2.7 (decisión del físico 2026-07-15): se eliminó el borrador JSON
        local (botón "Guardar" + carga al abrir). La BD, vía el botón
        "Subir" (INSERT si no existe / UPDATE si existe), es la ÚNICA fuente:
        sin datos pegados de otro mes ni borradores que pisen lo guardado."""
        try:
            # [1] Filtrar campos QLineEdit desde DataFrame
            df_lines = self._obtener_lineEdit(df, typee)

            if not df_lines:
                print(f"No se encontraron campos QLineEdit para {typee}")
                return

            # [2] Cargar lo ya guardado en BD (si existe)
            self._cargar_de_bd(df_lines, nombre_tabla, ref)

            # [3] Crear botones UNA SOLA VEZ (después de cargar datos)
            btn_guardar, btn_calculadora = self._crear_accion_botones(layout)

            # [4] Configurar eventos SIEMPRE (sin importar si había datos o no)
            self._configurar_eventos_campos(df_lines, btn_guardar, nombre_tabla, datos_eliminar, ref, usarid, anual=anual)

        except ValueError as e:
            print(f"Error de validación en addsomething: {e}")
        except Exception as e:
            print(f"Error inesperado en addsomething: {e}")
            traceback.print_exc()

    def _obtener_lineEdit(self, df, typee):
        """Extrae y filtra líneas QLineEdit del DataFrame"""
        df_lines = df.loc[(df.widget_type.str.contains('QLineEdit')) & (df.prueba == f'{typee}')]['nombres']
        return [line for line in df_lines]
    def _create_calc_btn(self):
        btn_calc = QPushButton("Calculadora de dosis")
        btn_calc.clicked.connect(self.abrir_calculadora)
        return btn_calc
    def construir_mapping_dosis(self):
        mapping = {}
        for energia in self.ENERGIAS:
            attr = f"ln_dosis_ref_cgy_um_{energia}"
            if hasattr(self, attr):
                mapping[energia] = getattr(self, attr)
        return mapping
    def abrir_calculadora(self):
        # H3.4 (auditoría 2026-07-14): la calculadora abría siempre en la
        # fecha de hoy, sin relación con el mes que se está diligenciando en
        # el formulario mensual -- se pasa self.date_box.date() (MM/yyyy).
        dialogo = DialogCalculadoraDosis(
            self.ENERGIAS, self, fecha_inicial=self.date_box.date())
        dialogo.dosis_asignada.connect(self._mapear_dosis_a_energia)
        dialogo.setModal(False) 
        dialogo.show()
        dialogo.raise_()
        dialogo.activateWindow()

    def _mapear_dosis_a_energia(self, energia, valor):
        mapping = self.construir_mapping_dosis()

        if energia not in mapping:
            QMessageBox.warning(
                self,
                "Energía no válida",
                f"Esta máquina no usa {energia}"
            )
            return

        mapping[energia].setText(f"{valor:.4f}")
        

    
    def _cargar_de_bd(self, df_lines, nombre_tabla, ref):
        print("DF LINES: ")
        print(df_lines)
        try:
            # Obtener columnas del esquema
            conn = self.db_manager.obtener_conexion()
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({nombre_tabla})")
            nombres_columnas = [row[1] for row in cursor.fetchall()]

            prueba1 = self.pruebatalas(nombre_tabla, ref)
            if prueba1:
                fila = prueba1[0]  # primera fila
                datos_dict = dict(zip(nombres_columnas, fila))
                self._rellenar_campos(df_lines, datos_dict, readonly=False,
                                      nombre_tabla=nombre_tabla)
                return True
        except Exception as e:
            print(f"Error al cargar desde BD: {e}")
        return False

    def _rellenar_campos(self, df_lines, datos, readonly=False, nombre_tabla=None):
        """Rellena los widgets desde un dict {columna_bd: valor}. H2.7: el
        nombre de columna se deriva con la MISMA regla que usa el guardado
        (subirlineasmensuales): widget_a_columna para dosimetriaMen,
        removeprefix('lbl_') para el resto -- antes esta carga buscaba la
        columna con el nombre crudo del widget (ln_dosis_ref_cgy_um_6mv) y
        no encontraba NINGÚN campo de dosimetría al reabrir un control ya
        guardado (solo observaciones sobrevivía)."""
        for line_name in df_lines:
            if nombre_tabla == "dosimetriaMen":
                nombre_col = widget_a_columna(line_name)
            else:
                nombre_col = line_name.removeprefix("lbl_")
            valor = datos.get(nombre_col)

            campo = getattr(self, line_name, None)
            if campo and valor is not None:
                campo.setReadOnly(readonly)
                campo.setText(str(valor))

    def _crear_accion_botones(self, layout):
        """Crea los botones de acción. H2.7: solo queda "Subir" (guardado
        real en BD) -- el botón "Guardar" (borrador JSON local) se eliminó
        por decisión del físico (2026-07-15)."""
        layout = layout.layout()
        buttonLayout = QHBoxLayout()
        btn_guardar = QPushButton("Subir")
        btn_calculadora = None

# Verificar condiciones para mostrar calculadora
        btn_calculadora = None

# Verificar condiciones para mostrar calculadora
        if (self.__class__.__name__ in ["PruebaMensual600", "PruebaMensualIX"] and layout == self.category4.layout()) or \
        (self.equipo_f == "Halcyon" and layout == self.category3.layout()):
            btn_calculadora = QPushButton("Calculadora de Dosis")
            btn_calculadora.clicked.connect(self.abrir_calculadora)
            buttonLayout.addWidget(btn_calculadora)

        # D4.2 (PLAN_FASE_K_D4.md): autollenado de simetría/planicidad desde
        # .mcc -- iX/600/Halcyon (mismas condiciones que el botón de la
        # calculadora arriba; Halcyon se sumó al confirmar con el físico que
        # la dosimetría siempre se ha medido a 10x10, ver _TAMANO_CAMPO_MM).
        if (self.__class__.__name__ in ["PruebaMensual600", "PruebaMensualIX"] and layout == self.category4.layout()) or \
        (self.equipo_f == "Halcyon" and layout == self.category3.layout()):
            self.btn_cargar_mcc = QPushButton("Cargar carpeta .mcc")
            self.btn_cargar_mcc.clicked.connect(self.seleccionar_carpeta_mcc)
            buttonLayout.addWidget(self.btn_cargar_mcc)

        btn_guardar.setEnabled(True)

        buttonLayout.addWidget(btn_guardar)

        layout.addLayout(buttonLayout, 62, 0)

        return btn_guardar, btn_calculadora

    # ── D4.2: autollenado de simetría/planicidad desde .mcc ────────────────
    # Compartido entre PruebaMensual600 (6mv únicamente) y PruebaMensualIX
    # (6 energías): _autollenar_energia_mcc solo escribe los campos que
    # existan en self, así que el mismo flujo sirve para ambas máquinas sin
    # ramificar por self.esIX.

    _ESTILO_SUGERIDO_MCC = "background-color: #fff3b0; border: 1px solid #e0b400;"
    # Confirmado con el físico (2026-07-10): toda la dosimetría mensual --
    # iX, 600 y Halcyon-- se ha medido siempre a 10x10 (100mm x 100mm). En
    # Halcyon el corpus real mezcla 5x5/10x10/20x20 para la misma energía en
    # la misma carpeta; sin este filtro, agregar_carpeta podría quedarse con
    # el tamaño equivocado solo por tener un MEAS_DATE más reciente. Se
    # aplica igual a iX/600 por consistencia -- verificado que no cambia nada
    # ahí (todo el corpus usado para calibrar D4.1b ya era 10x10).
    _TAMANO_CAMPO_MM = 100.0

    def seleccionar_carpeta_mcc(self):
        """Autollena simetría/planicidad (y, para fotones, la calidad
        TPR20,10 -- H4.1) a partir de una carpeta de escaneos .mcc (un
        mes+máquina; en iX, Fotones y Electrones están en carpetas
        separadas -- se puede llamar dos veces, una por carpeta). Filtra a
        campo 10x10 (ver _TAMANO_CAMPO_MM).

        Simetría/planicidad: ajuste EMPÍRICO calibrado contra dosimetriaMen
        real, no un protocolo estándar publicado. Calidad (fotones): SÍ es
        IAEA TRS-398 (ver calcular_calidad_fotones) -- pero igual queda
        marcada como sugerida, por consistencia con el resto del autollenado
        y porque el .mcc puede traer un PDD de un escaneo repetido/erróneo.
        En ambos casos: tooltip + aviso al cargar, y
        _confirmar_campos_mcc_sin_revisar() exige confirmación antes de
        guardar si el físico no los tocó. NUNCA se llena la calculadora de
        dosis -- solo el formulario mensual (ver dialogs.py: sin relación)."""
        carpeta = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de escaneos .mcc "
            "(el explorador solo muestra carpetas, no los archivos .mcc — es normal)")
        if not carpeta:
            return

        resultado = agregar_carpeta(carpeta, tamano_campo_mm=self._TAMANO_CAMPO_MM)
        if resultado["errores"]:
            detalle = "\n".join(os.path.basename(ruta) for ruta, _ in resultado["errores"])
            QMessageBox.warning(
                self, "Algunos archivos no se pudieron leer",
                f"No se pudieron leer {len(resultado['errores'])} archivo(s):\n{detalle}")

        if not hasattr(self, "_campos_mcc_sugeridos"):
            self._campos_mcc_sugeridos = set()

        energias_sim_plan = []
        energias_calidad = []
        for energia, curvas in resultado["datos"].items():
            if "INPLANE_PROFILE" in curvas and "CROSSPLANE_PROFILE" in curvas:
                try:
                    valores = calcular_simetria_planicidad(curvas)
                except (ValueError, ZeroDivisionError, IndexError):
                    valores = None
                if valores is not None and self._autollenar_energia_mcc(energia, valores):
                    energias_sim_plan.append(energia)

            # H4.1: calidad (fotones) desde el PDD -- nunca para electrones
            # (calidad de electrones es H4.4, sin fórmula confirmada).
            if "PDD" in curvas and not energia.endswith("mev"):
                try:
                    calidad = calcular_calidad_fotones(curvas["PDD"])
                except (ValueError, ZeroDivisionError, IndexError):
                    calidad = None
                if calidad is not None and self._autollenar_calidad_mcc(energia, calidad):
                    energias_calidad.append(energia)

        if energias_sim_plan or energias_calidad:
            partes = []
            if energias_sim_plan:
                partes.append("simetría/planicidad (" + ", ".join(sorted(energias_sim_plan)) + ")")
            if energias_calidad:
                partes.append("calidad TPR20,10 (" + ", ".join(sorted(energias_calidad)) + ")")

            # H4.2: explicar el principio de cálculo -- solo de lo que
            # realmente se autollenó en ESTA carpeta. Se distingue a
            # propósito cuál fórmula es un ajuste propio (simetría/
            # planicidad) y cuál es un protocolo publicado (calidad, IAEA
            # TRS-398 -- confirmado H4.1 citado en el catálogo PTW de
            # detectores), para que el físico sepa cuánto pesa cada una.
            explicaciones = []
            if energias_sim_plan:
                explicaciones.append(
                    "• Simetría: diferencia de puntos espejo del perfil "
                    f"(zona central {int(RATIO_SIMETRIA*100)}% del campo). "
                    "Planicidad: 100·(máx/mín − 1) "
                    f"(zona central {int(RATIO_PLANICIDAD*100)}%). Ambas son "
                    "un AJUSTE CALIBRADO por este proyecto contra los "
                    "registros históricos de dosimetriaMen -- no un "
                    "protocolo publicado.")
            if energias_calidad:
                explicaciones.append(
                    "• Calidad (fotones): TPR20,10 = 1.2661·(M20/M10) − "
                    "0.0595, con M20/M10 del PDD a 200/100 mm de "
                    "profundidad. Esta SÍ es la fórmula publicada en IAEA "
                    "TRS-398 (citada en el catálogo de detectores PTW).")

            QMessageBox.information(
                self, "Autollenado desde .mcc",
                "Se autollenó (SUGERIDO, verifique antes de guardar): "
                + "; ".join(partes) + ".\n\n"
                + "\n\n".join(explicaciones) +
                "\n\nRevíselos igual que revisaría una medición manual "
                "antes de guardar.")
        else:
            QMessageBox.warning(
                self, "Sin energías reconocidas",
                "No se encontraron perfiles INPLANE y CROSSPLANE completos "
                "(ni un PDD de fotones) para ninguna energía de este "
                "formulario en la carpeta seleccionada.")

    def _autollenar_energia_mcc(self, energia, valores):
        """Escribe los 4 campos crudos de una energía si existen en este
        formulario. Devuelve True si la energía aplicaba (False para, ej.,
        una energía de electrones cargada en el formulario de 600)."""
        mapa = {
            "simetria_inplane": f"ln_simetria_inplane_{energia}",
            "simetria_crossplane": f"ln_simetria_crossplane_{energia}",
            "planicidad_inplane": f"ln_planicidad_inplane_{energia}",
            "planicidad_crossplane": f"ln_planicidad_crossplane_{energia}",
        }
        if not all(hasattr(self, nombre) for nombre in mapa.values()):
            return False
        if not hasattr(self, "_campos_mcc_sugeridos"):
            self._campos_mcc_sugeridos = set()

        for clave, nombre_campo in mapa.items():
            campo = getattr(self, nombre_campo)
            campo.setText(str(valores[clave]))
            # Nota: este estilo se pisa en ~1s por el color de tolerancia de
            # _procesar_discrepancias_simetria_planicidad (textChanged con
            # debounce) -- es intencional, no un bug: da una señal instantánea
            # de "esto se acaba de autollenar" y luego cede paso al color de
            # tolerancia, que es la señal de QA que de verdad importa. El
            # tooltip y la confirmación al guardar son los que persisten.
            campo.setStyleSheet(self._ESTILO_SUGERIDO_MCC)
            campo.setToolTip(
                "Autollenado desde .mcc (fórmula calibrada, no un protocolo "
                "oficial) -- verifique este valor. Editarlo confirma que lo revisó.")
            self._campos_mcc_sugeridos.add(nombre_campo)
            campo.textEdited.connect(
                lambda _texto, c=campo, n=nombre_campo: self._marcar_campo_mcc_revisado(c, n))
        return True

    def _autollenar_calidad_mcc(self, energia, valor):
        """H4.1 (auditoría 2026-07-16): autollena la calidad TPR20,10 de
        fotones desde el PDD del .mcc (calcular_calidad_fotones, IAEA
        TRS-398). Análogo a _autollenar_energia_mcc pero para un solo campo
        -- reusa el mismo mecanismo de "sugerido" (tooltip + pendientes +
        gate de confirmación). Devuelve True si el campo existe en este
        formulario (False si, ej., se llama para una energía de electrones
        o para un formulario que no la tiene)."""
        nombre_campo = f"ln_calidad_pdd20_10_{energia}"
        if not hasattr(self, nombre_campo):
            return False
        if not hasattr(self, "_campos_mcc_sugeridos"):
            self._campos_mcc_sugeridos = set()

        campo = getattr(self, nombre_campo)
        campo.setText(str(valor))
        campo.setStyleSheet(self._ESTILO_SUGERIDO_MCC)
        campo.setToolTip(
            "Autollenado desde .mcc (TPR20,10 = 1.2661*PDD20,10 - 0.0595, "
            "IAEA TRS-398) -- verifique este valor. Editarlo confirma que lo revisó.")
        self._campos_mcc_sugeridos.add(nombre_campo)
        campo.textEdited.connect(
            lambda _texto, c=campo, n=nombre_campo: self._marcar_campo_mcc_revisado(c, n))
        return True

    def _marcar_campo_mcc_revisado(self, campo, nombre_campo):
        campo.setToolTip("")
        self._campos_mcc_sugeridos.discard(nombre_campo)

    def _confirmar_campos_mcc_sin_revisar(self):
        """Si quedan campos autollenados desde .mcc que el físico no ha
        tocado, exige confirmación explícita antes de guardar. Devuelve True
        si el guardado debe continuar."""
        pendientes = getattr(self, "_campos_mcc_sugeridos", None)
        if not pendientes:
            return True
        respuesta = QMessageBox.question(
            self, "Valores autollenados sin revisar",
            f"Hay {len(pendientes)} campo(s) autollenados desde .mcc "
            "(simetría/planicidad y/o calidad) que no ha revisado.\n\n"
            "¿Guardar de todas formas?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return respuesta == QMessageBox.Yes

    def _configurar_eventos_campos(self, df_lines, btn_guardar, nombre_tabla, datos_eliminar, ref, usarid, anual=False):
        """Configura eventos de campos con debouncing"""
        def updateSubirButton():
            """Actualiza estado del botón subir con validación optimizada"""
            filtered_lines = [line for line in df_lines if line not in ("observaciones", "ln_observaciones_dosi")]
            self.df_lines = filtered_lines

            if self.checkLineEdits(): # Si todos los campos están llenos
                btn_guardar.setEnabled(True)
            else:
                btn_guardar.setEnabled(True)

        # Conectar eventos con debouncing
        for line in df_lines:
            if line not in ("observaciones", "ln_observaciones_dosi"):
                campo = getattr(self, line, None)
                if campo:
                    # Debouncing para evitar llamadas excesivas
                    self._configurar_eventos(campo, updateSubirButton, f"update_{line}")

        # Configurar acciones de botones
        btn_guardar.clicked.connect(lambda: self._subir_optimizado(df_lines, nombre_tabla, datos_eliminar, ref, usarid, anual=anual))
       # btn_calculadora.clicked.connect(self.abrir_calculadora)

    def _configurar_eventos(self, widget, callback, timer_key, delay=1000):
        """Configura evento con debouncing para evitar llamadas excesivas"""
        def debounced_callback():
            if timer_key in self._debounce_timers:
                self._debounce_timers[timer_key].stop()
            
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(callback)
            timer.start(delay)
            self._debounce_timers[timer_key] = timer

        if isinstance(widget, QTableWidget):
            widget.itemChanged.connect(debounced_callback)
        else:
            widget.textChanged.connect(debounced_callback)

    def _subir_optimizado(self, df_lines, nombre_tabla, datos_eliminar, ref, usarid, anual=False):
        """Método optimizado para subir datos con mejor manejo de errores"""
        if not self._confirmar_campos_mcc_sin_revisar():
            return
        try:
            self.df_lines = df_lines
            print(f"\nSubiendo datos para {nombre_tabla}")

            subirlineasmensuales(self, nombre_tabla, datos_eliminar, ref=ref, usarid=usarid, anual=anual)

            # Procesar líneas adicionales si es necesario
            for line in df_lines:
                campo = getattr(self, line, None)
                if campo:
                    campo.setReadOnly(False)

            # Actualizar tabla según el tipo de control
            self._actualizar_tabla_despues_subida()
            print("Datos subidos correctamente")
            QMessageBox.information(self, "", "Datos cargados correctamente")
            
        except ConnectionError as e:
           
            print(f"Error de conexión al subir datos: {e}")
            QMessageBox.warning(self, "Error de Conexión", "No se pudo conectar a la base de datos.")
        except ValueError as e:
            print(f"Error de validación al subir datos: {e}")
            traceback.print_exc()
            QMessageBox.warning(self, "Error de Validación", "Los datos no son válidos.")
        except Exception as e:
            print(f"Error inesperado al subir datos: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", "Error inesperado al subir datos.")

    def createSimpleTable1(self, rows, cols, headers, datos, nombre_tabla, ref, botones=True, pdd=None,
                            id_energia=None, id=False):
        """Crea tabla simple optimizada con lazy loading y mejor manejo de datos"""
        #print(f"\nCreando tabla optimizada: {nombre_tabla}")
        
        try:
            #print(f"Creando tabla {nombre_tabla} con {rows} filas y {cols} columnas")
            widget = QWidget()
            layout = QVBoxLayout(widget)
            table = QTableWidget(self)

            # Configuración básica de tabla
            table.setRowCount(rows)
            table.setColumnCount(cols)
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().setVisible(False)
            
            # Optimizaciones de rendimiento
            table.setAlternatingRowColors(True)
            table.setSortingEnabled(False)  # Desactivar mientras se cargan datos
            
            # Intentar cargar datos desde BD primero
            datos_tabla = self._cargar_datos_tabla(nombre_tabla, ref, datos, pdd=pdd, id_energia=id_energia, id=id)
            readonly_mode = False
            
            if datos_tabla['source'] == 'database':
                readonly_mode = False
                self._llenar_tabla_bd(table, datos_tabla['data'])
                #table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            else:
                self._llenar_tabla_defaults(table, datos_tabla['data'] if nombre_tabla != "HC_precision_posicion_multilaminas_anual" else datos, editar_primera_columna=True)
            
            # Configuración final de tabla|
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            # Centrar el contenido de las celdas
            for i in range(table.columnCount()):
                table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
            layout.addWidget(table)
            
            # Si los datos están en BD, no agregar botones
            if readonly_mode:
                return widget, table
            
            if not botones:
                return widget, table

            # Agregar botones solo si es necesario
            self._agregar_botones_tabla(layout, table, nombre_tabla, ref, id=id, id_energia=id_energia)
            
            return widget, table
            
        except Exception as e:
            print(f"Error creando tabla {nombre_tabla}: {e}")
            traceback.print_exc()
            # Crear tabla básica en caso de error
            return self._crear_tabla_fallback(rows, cols, headers, datos)

    def _cargar_datos_tabla(self, nombre_tabla, ref, datos_default, pdd=None, id_energia=None, id = False):
        """Carga datos desde BD o defaults (H2.7: el nivel intermedio de
        borrador JSON local se eliminó -- la BD es la única fuente)"""
        try:
            # 1. Intentar cargar desde BD
            datos_bd = self.pruebatalas(nombre_tabla, ref, pdd=pdd, id_energia=id_energia, id=id)
            #print(f"Datos desde BD para {nombre_tabla}: {datos_bd}")

            if datos_bd:
                return {'source': 'database', 'data': datos_bd}

            # 2. Usar datos por defecto
            return {'source': 'default', 'data': datos_default}

        except Exception as e:

            print(f"Error cargando datos para {nombre_tabla}: {e}")
            return {'source': 'default', 'data': datos_default}

    def _llenar_tabla_bd(self, table, datos_bd):
        """Llena tabla con datos de BD optimizadamente"""
        try:
            for fila, fila_datos in enumerate(datos_bd):
                if fila >= table.rowCount():
                    break
                # Omitir primer elemento (ID) si existe
                if hasattr(self, 'anual') and self.anual:
                    datos_fila =  fila_datos[3:] if len(fila_datos) > table.columnCount() else fila_datos
                else:
                    datos_fila = fila_datos[1:] if len(fila_datos) > table.columnCount() else fila_datos
                
                for columna, dato in enumerate(datos_fila[:table.columnCount()]):
                    item = QTableWidgetItem(str(dato))
                    if columna == 0:
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    else:
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                    table.setItem(fila, columna, item)
        except Exception as e:
           
            print(f"Error llenando tabla desde BD: {e}")

    def _llenar_tabla_defaults(self, table, datos_default, editar_primera_columna=False):
        """Llena tabla con datos por defecto optimizadamente"""
        try:

            for fila, fila_datos in enumerate(datos_default):
                if fila >= table.rowCount():
                    break
                for columna, dato in enumerate(fila_datos[:table.columnCount()]):
                    item = QTableWidgetItem(str(dato))
                    if columna == 0 and not editar_primera_columna:
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    table.setItem(fila, columna, item)
        except Exception as e:
           
            print(f"Error llenando tabla con defaults: {e}")

    def _agregar_botones_tabla(self, layout, table, nombre_tabla, ref, id=None, id_energia=None):
        """Agrega el botón de subida a BD (H2.7: el "Guardar" de borrador
        JSON local se eliminó)"""
        try:
            button_layout = QHBoxLayout()
            btn_guardar = QPushButton("Subir")

            button_layout.addWidget(btn_guardar)
            layout.addLayout(button_layout)

            btn_guardar.clicked.connect(lambda: self._subir_tabla_optimizada(table, nombre_tabla, ref, id=id, id_energia=id_energia))

        except Exception as e:
            print(f"Error agregando botones: {e}")

    def _crear_tabla_fallback(self, rows, cols, headers, datos):
        """Crea tabla básica en caso de error"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget()
        
        table.setRowCount(rows)
        table.setColumnCount(cols)
        table.setHorizontalHeaderLabels(headers)
        
        layout.addWidget(table)
        return widget, table
    
    def _subir_tabla_optimizada(self, table, nombre_tabla, ref, id=False, id_energia=None):
        """Sube datos de tabla a BD de manera optimizada"""
        try:
            datos = []
            anual = getattr(self, "anual", False)
            
            if anual:
                for group in [getattr(self, 'tablas_fc', []), getattr(self, 'tablas_fta', []), getattr(self, 'tablas_fse', []), getattr(self, 'tablas_ccm', [])]:
                    for entry in group:
                        if entry['tabla'] is table:
                            id_energia = entry.get('id_energia')
                            break
            if anual and id_energia is not None:
                loadtablacomplex(nombre_tabla, table, datos, reference=ref, from_range=0, anual=anual, id_energia=id_energia, id=id)
            else:
                print(f"Subiendo tabla {nombre_tabla} sin id_energia")
                print(f"Los argumentos son: nombre_tabla={nombre_tabla}, ref={ref}, anual={anual}, id={id}")
                loadtablacomplex(nombre_tabla, table, datos, reference=ref, from_range=0, anual=anual, id=id, id_energia=id_energia)

            # Actualizar tabla principal
            self._actualizar_tabla_despues_subida()
            QMessageBox.information(self, "", "Tabla cargada correctamente")
            print(f"Tabla {nombre_tabla} subida correctamente")

        except ConnectionError as e:
            print(f"Error de conexión subiendo tabla {nombre_tabla}: {e}")
            QMessageBox.warning(self, "Error de Conexión", "No se pudo conectar a la base de datos")
        except Exception as e:
            print(f"Error subiendo tabla {nombre_tabla}: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error al subir tabla: {str(e)}")
    
    @property
    def es_control_anual(self):
        """Retorna True si es un control anual"""
        return hasattr(self, 'anual') and self.anual
    
    def fieldSize(self, nombre_tabla, ref):
        reference = ref
        widget = QWidget()
        # Layout principal
        layout = QVBoxLayout()

        # Crear el QTableWidget
        table = QTableWidget()
        table.setRowCount(7)  # Incrementa el conteo de filas para encabezados simulados
        table.setColumnCount(9)

        # Ocultar encabezados predeterminados
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False) 

        # Encabezados principales (fila 0)
        table.setSpan(0, 1, 1, 4)  # Indicador del equipo
        table.setSpan(0, 5, 1, 4)  # Indicador de la consola
        table.setItem(0, 1, QTableWidgetItem("Indicador del equipo"))
        table.setItem(0, 5, QTableWidgetItem("Indicador de la consola"))
        
        # Encabezados principales (fila 0)
        table.setSpan(0, 0, 3, 1)  # Indicador del equipo
        table.setItem(0, 0, QTableWidgetItem("Campo nominal (cm x cm)"))

        # Sub-encabezados "Largo" y "Ancho" combinados verticalmente (fila 1 y 2)
        table.setSpan(1, 1, 1, 2)  # Largo (Equipo)
        table.setSpan(1, 3, 1, 2)  # Ancho (Equipo)
        table.setSpan(1, 5, 1, 2)  # Largo (Consola)
        table.setSpan(1, 7, 1, 2)  # Ancho (Consola)

        table.setItem(1, 1, QTableWidgetItem("Largo"))
        table.setItem(1, 3, QTableWidgetItem("Ancho"))
        table.setItem(1, 5, QTableWidgetItem("Largo"))
        table.setItem(1, 7, QTableWidgetItem("Ancho"))
        
        table.setItem(2, 1, QTableWidgetItem("Y1"))
        table.setItem(2, 2, QTableWidgetItem("Y2"))
        table.setItem(2, 3, QTableWidgetItem("X1"))
        table.setItem(2, 4, QTableWidgetItem("X2"))
        table.setItem(2, 5, QTableWidgetItem("Y1"))
        table.setItem(2, 6, QTableWidgetItem("Y2"))
        table.setItem(2, 7, QTableWidgetItem("X1"))
        table.setItem(2, 8, QTableWidgetItem("X2"))        
        
        # Rellenar datos en la tabla (H1.3, auditoría 2026-07-14: solo el
        # "Campo nominal" nace prellenado -- las 8 columnas de MEDICIÓN
        # nacían con el valor nominal repetido, como si ya se hubiera
        # medido; el físico vio números que no eran datos reales).
        datos = [
            ["5 x 5", "", "", "", "", "", "", "", ""],
            ["10 x 10", "", "", "", "", "", "", "", ""],
            ["15 x 15", "", "", "", "", "", "", "", ""],
            ["20 x 20", "", "", "", "", "", "", "", ""]
        ]
        
        prueba1 = self.pruebatalas(nombre_tabla, reference)
        #print(f'Prueba1 en {nombre_tabla} es: {prueba1}')

        # H2.7: sin fallback a borrador JSON -- o hay mediciones guardadas en
        # BD (Subir) o la tabla nace vacía (H1.3).
        if prueba1 is not None and prueba1 != []:
            datos = prueba1
            datos = [t[1:] for t in datos]

        for fila, fila_datos in enumerate(datos, start=3):
            for columna, dato in enumerate(fila_datos):
                item = QTableWidgetItem(str(dato)) 
                
                if columna == 0:
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                
                table.setItem(fila, columna, item)
                
        # Agregar la tabla al layout
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(table)
        
        # if prueba1 is not None and prueba1 != []:
        #     table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        #     widget.setLayout(layout)
        #     return widget
        
        # Botón de subida a BD (H2.7: el "Guardar" de borrador JSON local se
        # eliminó -- Subir es la única forma de persistir, y hace
        # DELETE+INSERT por ref vía loadtablacomplex).
        self.buttonLayout = QHBoxLayout()
        btn_guardar = QPushButton("Subir")
        self.buttonLayout.addWidget(btn_guardar)
        layout.addLayout(self.buttonLayout)

        def subir_tabla():
            print('Entra a subir tabla en fieldSize')
            datos = []
            loadtablacomplex(nombre_tabla, table, datos, reference=ref, from_range=3, anual=False, id=False, id_energia=None)
            # H2.4: registro de auditoría del guardado real en BD.
            _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR, nombre_tabla, ref=ref)
            self._actualizar_tabla_despues_subida()
            QMessageBox.information(self, "", "Tabla cargada correctamente")
            print(f"\nLa variable equipo_f en la función fieldSize es: {self.equipo_f}")

        btn_guardar.clicked.connect(subir_tabla)

        widget.setLayout(layout)
        return widget
    
    def graphicsWindow(self):
        # Columna derecha: QTabWidget (ventana con pestañas)
        self.tab_widget = QTabWidget() #crea el tab
        self.tab_widget.setTabsClosable(True)  # Habilita el cierre de pestañas
        self.tab_widget.tabCloseRequested.connect(self.closeTab)  # Conecta la señal de cerrar
        
        self.tab1 = QWidget()
        self.tab_widget.addTab(self.tab1, "Graficos")
        
        self.setupTap1()
        
        self.dynamic_tabs = {}
        
        return self.tab_widget
    
    def closeTab(self, index):
        # No permite cerrar la pestaña principal
        if index == 0:
            return
        tab_text = self.tab_widget.tabText(index)
        if tab_text in self.dynamic_tabs:
            del self.dynamic_tabs[tab_text]
        self.tab_widget.removeTab(index)    
    
    def limpiar_canvas(self, canvas):
        canvas.figure.clf()
        canvas.draw()

    def setupTap1(self):
        # Combo de selección de gráfica
        self.graficar = QComboBox()
        
        # Canvas para gráficas
        mpl = get_matplotlib_components()
        FigureCanvas = mpl['FigureCanvas']
        self.canvas = FigureCanvas(Figure(figsize=(10, 6.7)))

        # Tabla vacía inicial (se llena después)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(0)
        self.tabla.setRowCount(0)

        # Contenedor superior con combo y gráfica
        contenedor_superior = QWidget()
        self.col2 = QVBoxLayout(contenedor_superior)
        self.col2.addWidget(self.graficar)
        self.col2.addWidget(self.canvas)

        # Splitter para gráfica (arriba) y tabla (abajo)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(contenedor_superior)
        splitter.addWidget(self.tabla)
        splitter.setSizes([400, 200])  # Altura inicial

        #------------------------------------------------------
        #        Botones de navegación entre graficas
        #------------------------------------------------------
        self.boton_anterior = QPushButton("Anterior")
        self.boton_siguiente = QPushButton("Siguiente")
        self.boton_anterior.setEnabled(False)
        self.boton_siguiente.setEnabled(False)

        botones_layout = QHBoxLayout()
        botones_layout.addWidget(self.boton_anterior)
        botones_layout.addWidget(self.boton_siguiente)

        self.boton_anterior.hide()
        self.boton_siguiente.hide()

        #------------------------------------------------------
        #        Botones para la barra de herramientas
        #------------------------------------------------------
        self.btn_delete = QPushButton('Eliminar')    
        self.edit_table = QPushButton('Editar')
        self.accept_edit = QPushButton('Aceptar')
        self.accept_edit.hide()
        self.cancel_edit = QPushButton('Cancelar')
        self.cancel_edit.hide()
        
        # Barra de búsqueda
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar en la tabla...")

        edit_table_tools = QHBoxLayout()
        edit_table_tools.addWidget(self.btn_delete)
        edit_table_tools.addWidget(self.edit_table)
        edit_table_tools.addWidget(self.accept_edit)
        edit_table_tools.addWidget(self.cancel_edit)
        edit_table_tools.addWidget(self.search_bar)

        # Layout principal de la pestaña
        layout_tab = QVBoxLayout()
        layout_tab.addWidget(splitter)
        layout_tab.addLayout(botones_layout)   # Contiene los botones de navegacion entre graficas del analisis de imagen
        layout_tab.addLayout(edit_table_tools) # Contiene los botones de barra de herramientas

        self.tab1.setLayout(layout_tab)

        # Estado de navegación
        self.lista_graficas = []
        self.grafica_actual = 0

        self.boton_anterior.clicked.connect(self.mostrar_grafica_anterior)
        self.boton_siguiente.clicked.connect(self.mostrar_grafica_siguiente)

        # Mostrar tabla correcta según el tipo de control
        if hasattr(self, 'anual') and self.anual:
            mostrar_controles_anuales(self, self.tabla, equipo_filtrar=self.equipo_f)
        else:
            mostrar_controles_mensuales(None, self.tabla, equipo_filtrar=self.equipo_f)

    def analizar_imagen(self):
        self.boton_siguiente.show()
        self.boton_anterior.show()
         
        print("Analizando imagen...")
        try:
            if not self.imagen_path:
                QMessageBox.warning(self, "Advertencia", "Primero selecciona una imagen.")
                return

            if not hasattr(self, 'guardar_analisis') or self.guardar_analisis is None: 
                self.guardar_analisis = QPushButton("Guardar")
                self.guardar_analisis.setFixedSize(80, 35)
                self.botones_layout.addWidget(self.guardar_analisis)

            self.res = analizar_cuadrado2(
                imagen_path=self.imagen_path,
                filtro=None,
                mostrar=True,
                canvas=self.canvas
            )

            self.lista_graficas = self.res.get("graficas", [])
            self.grafica_actual = 0

            if self.lista_graficas:
                self.boton_siguiente.setEnabled(True)
                self.boton_anterior.setEnabled(False)
                self.mostrar_grafica_actual()

            resultado = generar_reporte_completo(self.res)
            self.mostrar_resultados_AnalisisImagen(resultado)

            if not hasattr(self, 'toolbar') or self.toolbar is None:
                mpl = get_matplotlib_components()
                NavigationToolbar = mpl['NavigationToolbar']
                self.toolbar = NavigationToolbar(self.canvas, self)
                self.col2.addWidget(self.toolbar)
            else:
                if self.col2.indexOf(self.toolbar) == -1:
                    self.col2.addWidget(self.toolbar)
        except Exception as e:
            print("Error al subir o al analizar imagen: ",e)
            

    def mostrar_resultados_AnalisisImagen(self, texto_lines):
        toolbar = getattr(self, 'toolbar', None)

        # Limpiar widgets extra
        for i in reversed(range(self.col2.count())):
            item = self.col2.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None and widget not in (self.canvas, toolbar, self.graficar):
                self.col2.removeWidget(widget)
                widget.deleteLater()

        # QLabel con el reporte
        label = QLabel()
        label.setTextFormat(Qt.RichText)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        label.setWordWrap(True)
        label.setText(texto_lines)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        label.setStyleSheet("padding: 5px;")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(label)
        scroll_area.setMinimumHeight(50)
        scroll_area.setStyleSheet("border: 1px solid #ccc;")

        self.resultado_scroll = scroll_area

        if not hasattr(self, 'toolbar') or self.toolbar is None:
            mpl = get_matplotlib_components()
            NavigationToolbar = mpl['NavigationToolbar']
            self.toolbar = NavigationToolbar(self.canvas, self)
            for action in self.toolbar.actions():
                if action.text() in ['Customize', 'Subplots']:
                    self.toolbar.removeAction(action)
            self.toolbar.setFixedHeight(25)
            self.toolbar.setStyleSheet("padding: 0px; margin: 0px;")

        for widget in (self.toolbar, scroll_area, self.canvas):
            if widget is not None and self.col2.indexOf(widget) == -1:
                self.col2.addWidget(widget)
        self.toolbar.show()
        self.toolbar.update()
        self.canvas.setVisible(True)
        self.canvas.show()
        self.canvas.update()

        if hasattr(self, 'guardar_analisis') and self.guardar_analisis is not None:
            self.guardar_analisis.clicked.connect(self.guardar_analsis)
            self.guardar_analisis.clicked.connect(lambda _: self.dbImagen(self.ref, self.imagen_path))

    def guardar_analsis(self):
            guardar_analisis_placa600(self.ref, self.res)

    def mostrar_grafica_actual(self):
        if self.lista_graficas:
            self.limpiar_canvas(self.canvas)
            self.lista_graficas[self.grafica_actual](self.canvas)
            self.canvas.draw()

        self.boton_anterior.setEnabled(self.grafica_actual > 0)
        self.boton_siguiente.setEnabled(self.grafica_actual < len(self.lista_graficas) - 1)

    def mostrar_grafica_anterior(self):
        if self.grafica_actual > 0:
            self.grafica_actual -= 1
            self.mostrar_grafica_actual()

    def mostrar_grafica_siguiente(self):
        if self.grafica_actual < len(self.lista_graficas) - 1:
            self.grafica_actual += 1
            self.mostrar_grafica_actual()

    def conectarDB(self, comboequipo):
        series = []
        if hasattr(self, "esIX") and self.esIX:
            me = ['Cámara de ionización', 'Cámara de ionización', 'Cámara de ionización', 'Electrómetro']
        else:
            me = ['Cámara de ionización', 'Cámara de ionización', 'Electrómetro']

        # Agrupar los widgets en sublistas de 3
        grupos = [comboequipo[i:i+3] for i in range(0, len(comboequipo), 3)]
        for grupo, modelo in zip(grupos, me):
            # Obtener solo modelos de equipos activos
            posibles_modelos = self.buscarModeloActivo(filter_column='equip_type', selected_column="model", valor_ref=modelo)

            series_1 = []
            for model in posibles_modelos:
                # Obtener series activas para cada modelo
                posibles_series = self.buscarModeloActivo(filter_column='model', selected_column='serie', valor_ref=model)
                series_1.append(posibles_series)
            series.append(series_1)
            
            posibles_modelos = list(posibles_modelos)
            posibles_modelos.insert(0, 'Seleccionar...')
            
            grupo[0].clear()
            grupo[0].addItems(posibles_modelos)
            
            grupo[1].setEnabled(True)
            grupo[2].setReadOnly(False)
        
        #### conecto a la creacion de combobox fin
        
        #si cp seleccionada, hago lo mismo con los modelos de cp
        '''equipo_widgets = [widget for widget, tipo in comboboxe if tipo == 'equipo']
            self.setEquipo(equipo_widgets)'''
        return

    @lru_cache(maxsize=50)
    def buscarModeloActivo(self, filter_column, selected_column, valor_ref):
        """
        Versión optimizada de buscarModelo que solo devuelve equipos activos con caché
        """
        cache_key = f"{filter_column}_{selected_column}_{valor_ref}"
        
        # Verificar caché local primero
        if hasattr(self, '_model_cache') and cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        try:
            conn = self.db_manager.obtener_conexion()
            cursor = conn.cursor()
            modelos = set()
            
            # Query optimizada con índices
            cursor.execute(f"""
            SELECT DISTINCT {selected_column}
            FROM equipos
            WHERE {filter_column} = ? AND activo = 1
            AND id IN (
                SELECT MAX(id) FROM equipos GROUP BY serie
            )
            ORDER BY {selected_column}
            """, (valor_ref,))
            
            rows = cursor.fetchall()
            for row in rows:
                if row[0]:  # Verificar que no sea None
                    modelos.add(row[0])
            
            # Guardar en caché local
            if not hasattr(self, '_model_cache'):
                self._model_cache = {}
            self._model_cache[cache_key] = modelos
            
            return modelos
            
        except sqlite3.Error as e:
            print(f"Error de base de datos en buscarModeloActivo: {e}")
            return set()
        except Exception as e:
            print(f"Error inesperado en buscarModeloActivo: {e}")
            traceback.print_exc()
            return set()

    @lru_cache(maxsize=30)
    def obtenerSeriesConVigencia(self, modelo):
        """
        Obtiene las series de un modelo específico con fecha_calibr/equip_type
        (V1, PLAN_AUDITORIA_DOS_EJES_21-07.md SS7.5: para que
        setEquipoSeleccionado pueda evaluar vigencia contra la fecha del
        CONTROL en vez del flag `vigente` congelado en la columna) y estado
        activo (optimizado con caché).
        """
        if not modelo or modelo == "Seleccionar...":
            return []

        cache_key = f"series_vigencia_{modelo}"

        # Verificar caché local
        if hasattr(self, '_series_cache') and cache_key in self._series_cache:
            return self._series_cache[cache_key]

        try:
            conn = self.db_manager.obtener_conexion()
            cursor = conn.cursor()
            series_data = []

            cursor.execute("""
                SELECT serie, vigente, activo, fecha_calibr, equip_type
                FROM equipos
                WHERE model = ?
                AND id IN (
                    SELECT MAX(id) FROM equipos GROUP BY serie
                )
                ORDER BY serie
            """, (modelo,))
            
            rows = cursor.fetchall()
            for row in rows:
                if row:  # Verificar que la fila no esté vacía
                    series_data.append(row)
            
            # Guardar en caché local
            if not hasattr(self, '_series_cache'):
                self._series_cache = {}
            self._series_cache[cache_key] = series_data
            
            return series_data
            
        except sqlite3.Error as e:
            print(f"Error de BD en obtenerSeriesConVigencia: {e}")
            return []
        except Exception as e:
            print(f"Error inesperado en obtenerSeriesConVigencia: {e}")
            traceback.print_exc()
            return []

    def button_click(self):  

        for combo in range(0, len(self.commenu), 3):
            self.commenu[combo].currentTextChanged.connect(self.setEquipoSeleccionado)
        for idx in range(1, len(self.commenu)+1, 3):
            self.commenu[idx].currentTextChanged.connect(self.setCalibracion)
        
        if hasattr(self, "esHc") and self.esHc:
                pass
 
                
        

        self.edit_table.clicked.connect(lambda: verificar_editar(self, self.tabla, "controles", "ref", self.ref))

        self.accept_edit.clicked.connect(lambda: guardarEdicion(self, self.tabla, "controles", self.ref))
        
        self.cancel_edit.clicked.connect(lambda: cancelarEdicion(self))

        self.btn_delete.clicked.connect(lambda: verificar_eliminar(self, self.tabla, "controles", self.ref)) 
        self.table = self.tabla 
        self.search_bar.textChanged.connect(self.filtrarTabla)

    def dbImagen(self, ref, imagen):
        self.boton_aceptar.hide()
        self.boton_cancel.hide()
        #print(ref)
        crear_algo(self, ref, imagen)
    
    def createTab(self, text):
        print(f'\nEntro a createTab con {text} en la clase {self.__class__.__name__}')
        if text == 'Seleccionar...' or text == 'Ver resultados de...':
            return
        
        if text in self.dynamic_tabs:
            index = self.tab_widget.indexOf(self.dynamic_tabs[text]) #Returns the index position of the page occupied by the widget w , or -1 if the widget cannot be found.
            self.tab_widget.setCurrentIndex(index)
            
        else:
            new_tab = QWidget() #creo la ventana
            new_tab_layout = QVBoxLayout() #su estructura
            new_tab.setLayout(new_tab_layout) #se mete la estructura a la ventana
            new_tab_layout.addWidget(QLabel(f'Holi, esta es la gráfica de {text}')) #le meto un label a la ventana
            self.tab_widget.addTab(new_tab, text) #y la ventana a eso
            
            self.dynamic_tabs[text] = new_tab
            self.tab_widget.setCurrentWidget(new_tab) 
    
    def setEquipoSeleccionado(self):
        sender_combo = self.sender()
        index = self.commenu.index(sender_combo)
        modelo = sender_combo.currentText()
        
        # Habilitar el siguiente combobox
        next_combo = self.commenu[index + 1]
        next_combo.setEnabled(True)
        
        # Bloquear señales para evitar que al limpiar y agregar items se emitan eventos
        next_combo.blockSignals(True)
        next_combo.clear()
        
        # Obtener series activas con información de vigencia
        series_data = self.obtenerSeriesConVigencia(modelo)
        series_activas = []
        series_no_vigentes = []

        # V1 (PLAN_AUDITORIA_DOS_EJES_21-07.md SS7.5): la vigencia se evalúa
        # contra la fecha del CONTROL que se está llenando (self.date_box),
        # no contra el flag `vigente` congelado en la BD (que se calculó una
        # sola vez, con la fecha de ESE momento) ni contra hoy -- así un
        # control retroactivo con fecha pasada no marca "vencido" un equipo
        # que sí estaba vigente en esa fecha. No escribe nada en `equipos`.
        fecha_referencia = (
            self.date_box.date() if hasattr(self, 'date_box') and self.date_box
            else QDate.currentDate()
        )

        for serie, vigente, activo, fecha_calibr, equip_type in series_data:
            if activo == 1:  # Solo equipos activos
                series_activas.append(serie)
                if not es_vigente_en_fecha(fecha_calibr, equip_type, fecha_referencia):
                    series_no_vigentes.append(serie)

        series_activas.insert(0, 'Seleccionar...')
        next_combo.addItems(series_activas)
        
        # Marcar en rojo los equipos no vigentes
        for serie in series_no_vigentes:
            index_serie = next_combo.findText(serie)
            if index_serie != -1:
                item = next_combo.model().item(index_serie)
                item.setForeground(QColor(255, 0, 0))  # Texto rojo
                item.setText(f"⚠️{serie}")  # Agregar indicador visual
                item.setToolTip("⚠️ Calibración vencida - Requiere recalibración")
        next_combo.blockSignals(False)
        
        # Configurar el QLineEdit siguiente
        self.commenu[index + 2].setReadOnly(True)
    
    def setCalibracion(self):
        #print('entro a calibracion')
        sender = self.sender()
        # Obtén el índice del combobox en la lista
        index = self.commenu.index(sender)
        # Busca el valor de calibración asociada a esa serie
        modelo = sender.currentText()
        
        # Limpiar el texto si contiene el marcador de vencido
        if "⚠️" in modelo:
            modelo = modelo.replace("⚠️", "").strip()
        if "(VENCIDO)" in modelo:
            modelo = modelo.replace("(VENCIDO)", "").strip()
        
        if modelo == 'Seleccionar...':
            #print('retorno')
            return 
        #calibracion = self.buscarCalibracion(serie_text)
        # Asigna el valor al QLineEdit siguiente (posición idx+1)
        #self.commenu[idx + 1].setText(str(calibracion))
        lista = self.buscarModeloActivo('serie', 'calibr_fact', modelo)
        #print(lista)
        lista = list(lista)
        str2 = str(lista[0])
        self.commenu[index + 1].setText(str2)
    
    def botonescombobox(self, categoria, combobox=None, combos_seguridad=None):
        #print(f"\n ~~~~~~ Entra a botonescombobox en la clase: {self.__class__.__name__}~~~~~~")

        # --------------------------------------------------------------------------------------
        # Caso: equipos (combo_menu)
        # --------------------------------------------------------------------------------------
        if combobox is not None and combos_seguridad is None:
            subido =  self.Traerinfo(combobox) #False
            if subido:
                #print('Ya se subieron los datos para equipos_mensual')
                return

            self.conectarDB(combobox)
            layout = categoria.layout()
            if layout is not None:
                buttonLayout = QHBoxLayout()
                btn_guardar = QPushButton("Subir")
                # H2.7: el "Guardar" de esta sección escribía un equipos.json
                # que NINGÚN código releía (borrador huérfano) -- eliminado.
                buttonLayout.addWidget(btn_guardar)
                layout.addLayout(buttonLayout, 23, 0)
                #print("Botones creados en condición combobox (equipos)")

                # ---- funciones locales ----
                def subir():
                    #print(f"\n ..... Entra a botonescombobox.subir() en {self.__class__.__name__} .....")
                    datos = []
                    for widget in combobox:
                        if isinstance(widget, QComboBox):
                            texto = widget.currentText()
                        elif isinstance(widget, QLineEdit):
                            texto = widget.text()
                        else:
                            return
                        if texto not in ('Seleccionar...', '', None):
                            datos.append(texto)
                        else:
                            return
                    self.subirtodo_modificado(datos)
                    QMessageBox.information(self, "", "Datos subidos correctamente")
                    self._actualizar_tabla_despues_subida()
                    #print(f"\nLa variable equipo_f en la función botonescomboboox equipos es: {self.equipo_f}")

                btn_guardar.clicked.connect(subir)

        # --------------------------------------------------------------------------------------
        # Caso: cuñas (combos_seguridad)
        # --------------------------------------------------------------------------------------
        if combos_seguridad is not None and combobox is None:
            subido_cunas = self.Traerinfo_cunas()
            
            layout = categoria.layout()
            if layout is not None:
                buttonLayout = QHBoxLayout()
                if hasattr(self, "esIX") and self.esIX:
                    self.btn_guardar_ix = QPushButton("Subir")
                    buttonLayout.addWidget(self.btn_guardar_ix)
                    layout.addLayout(buttonLayout, 23, 0)
                    #print("Botón especial IX creado")
                else:
                    btn_guardar = QPushButton("Subir")
                    # H2.7: el "Guardar" de cuñas era un no-op (pass) --
                    # eliminado junto con el resto de botones de borrador.
                    buttonLayout.addWidget(btn_guardar)
                    layout.addLayout(buttonLayout, 23, 0)
                    #print("Botones creados en condición combos_seguridad")

                    def subir():
                        print(f"\n ........ Entra a botonescombobox.subir() en {self.__class__.__name__} ........")
                        self.subir_control_cunas(self.combos_seguridad, self.df_seg_line)
                        print("Se llama a subir_control_cunas en 600")
                        self._actualizar_tabla_despues_subida()
                        print(f"\nLa variable equipo_f en la función bombobox cuñas es: {self.equipo_f}")

                    btn_guardar.clicked.connect(subir)

    def subirtodo_modificado(self, datos):
        """
        Versión optimizada para insertar datos de equipos con transacciones agrupadas
        Para cada grupo de 3 elementos en datos (model, serie, calibr_fact),
        busca en la tabla 'equipos' y luego inserta en equipos_mensual.
        """

        if hasattr(self, "esIX") and self.esIX:
            print("Insertando datos de equipos para IX")
            n = 9+3 # porque hay un equipo extra (cámara principal para electrones)
        else:
            n = 9

        if not datos or len(datos) < n:
            print("Datos insuficientes para procesar equipos")
            return
        
        try:
            conn = self.db_manager.obtener_conexion()
            cursor = conn.cursor()
            
            # Usar transacción para mejor rendimiento
            cursor.execute("BEGIN TRANSACTION")
            
            filas_a_insertar = []
            
            # Procesar grupos de 3 elementos
            grupos = [0, 3, 6, 9] if hasattr(self, "esIX") and self.esIX else [0, 3, 6]
            for base in grupos: 
                if hasattr(self, "esIX") and self.esIX:
                    tipo_camara = ('Principal Fotones' if base == 0 else 'Principal Electrones' if base == 3 else 'Secundaria' if base == 6 else 'Electrómetro')
                else:
                    tipo_camara = ('Principal' if base == 0 else 'Secundaria' if base == 3 else 'Electrómetro')
                try:
                    model = datos[base] if base < len(datos) else ""
                    serie = datos[base + 1] if (base + 1) < len(datos) else ""
                    calibr_fact = datos[base + 2] if (base + 2) < len(datos) else ""
                    
                    if not all([model, serie, calibr_fact]):
                        print(f"Datos incompletos en grupo {base//3 + 1}")
                        continue
                    
                    # Consulta optimizada en la tabla 'equipos'
                    cursor.execute("""
                        SELECT fecha_calibr, equip_type 
                        FROM equipos 
                        WHERE serie = ? 
                        AND id = (
                        SELECT MAX(id) FROM equipos WHERE serie = ?
                        )
                    """, (serie, serie))
                    
                    resultado = cursor.fetchone()
                    fecha_calibr, equip_type = resultado if resultado else (None, None)
                    
                    # Fallback: Si equip_type es None, determinarlo según el índice del grupo
                    if equip_type is None:
                        if hasattr(self, "esIX") and self.esIX:
                            equip_type = ('Cámara de ionización' if base in [0, 3, 6] else 'Electrómetro')
                        else:
                            equip_type = ('Cámara de ionización' if base in [0, 3] else 'Electrómetro')
                        print(f"Advertencia: equip_type no encontrado para serie {serie}, usando fallback: {equip_type}")
                    
                    # Preparar fila para inserción
                    fila = (self.ref, tipo_camara, equip_type, model, serie, calibr_fact, fecha_calibr)
                    filas_a_insertar.append(fila)
                    
                except (IndexError, ValueError) as e:
                    print(f"Error procesando grupo {base//3 + 1}: {e}")
                    continue
            
            # Inserción por lotes para mejor rendimiento
            if filas_a_insertar:
                cursor.executemany(f"""
                    INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, model, serie, calibr_fact, fecha_calibr) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, filas_a_insertar)
                
                cursor.execute("COMMIT")
                print(f"Insertados {len(filas_a_insertar)} registros de equipos correctamente")
                
                # Actualizar tabla si existe
                if hasattr(self, 'tabla'):
                    self._actualizar_tabla_despues_subida()
            else:
                cursor.execute("ROLLBACK")
                print("No se insertaron registros - datos insuficientes")
                
        except sqlite3.Error as e:
            try:
                cursor.execute("ROLLBACK")
            except:
                pass
            print(f"Error de BD al insertar equipos: {e}")
            QMessageBox.critical(self, "Error de Base de Datos", 
                                f"No se pudieron guardar los equipos: {str(e)}")
        except Exception as e:
            try:
                cursor.execute("ROLLBACK")
            except:
                pass
            print(f"Error inesperado al insertar equipos: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", "Error inesperado al guardar equipos")

    def verificacion_observaciones(self, line_edit):
        texto = line_edit.text().strip()
        if texto:
            print("Observaciones:", texto)
            return texto
        return None
    
    def subir_control_cunas(self, combos_seguridad, df_lines=None):
        """
        combos_seguridad es un diccionario con las llaves:
        {
            15: {"in": QComboBox, "out": QComboBox, "right": QComboBox, "left": QComboBox},
            30: {...},
            45: {...},
            60: {...}
        }
        Guarda 1 si es 'Funciona', 0 si es 'No funciona'.
        """
        print("\n -> Entra en subir_control_cunas en 600")
        conn = Conexion().conectar()
        cursor = conn.cursor()

        for angulo, posiciones in combos_seguridad.items():
            in_val    = 1 if posiciones["in"].currentText() == "Funciona" else 0
            out_val   = 1 if posiciones["out"].currentText() == "Funciona" else 0
            right_val = 1 if posiciones["right"].currentText() == "Funciona" else 0
            left_val  = 1 if posiciones["left"].currentText() == "Funciona" else 0

            cursor.execute("""
                INSERT OR REPLACE INTO control_cunas (ref, angulo, in_val, out_val, right_val, left_val)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (self.ref, angulo, in_val, out_val, right_val, left_val))

        if df_lines is not None:
            for line in df_lines:
                if line == "observaciones_segu":
                    line_edit = getattr(self, line, None)
                    print(f"line: {line}, widget: {line_edit}")
                    if line_edit is not None and isinstance(line_edit, QLineEdit):
                        print(f"Texto actual en {line}: '{line_edit.text()}'")
                        texto = line_edit.text().strip()
                        cursor.execute("""
                            UPDATE control_cunas
                            SET observaciones = ?
                            WHERE ref = ?
                        """, (texto, self.ref))


        conn.commit()
        #QMessageBox.information(self, "Éxito", "Datos de control de cuñas insertados correctamente.")
        print("Datos de control de cuñas insertados correctamente")
        QMessageBox.information(self, "", "Tabla cargada correctamente")
        # Actualizar tabla si existe
        if hasattr(self, 'tabla'):
            self._actualizar_tabla_despues_subida()
    
    def Traerinfo(self, combenu):
        """Función optimizada para cargar información de equipos desde BD"""
        #print("------ Función Traerinfo (optimizada)")
        
        try:
            conn = self.db_manager.obtener_conexion()
            cursor = conn.cursor()
            
            # Query optimizada con ordenamiento
            cursor.execute(f"""
                SELECT model, serie, calibr_fact 
                FROM equipos_medicion
                WHERE ref = ? 
                ORDER BY id
            """, (self.ref,))
            
            results = cursor.fetchall()
            
            if not results:
                return False
            
            # Procesar resultados de manera más segura
            for i, (model, serie, calibr_fact) in enumerate(results):
                base_index = i * 3 # Cada registro usa 3 widgets
                
                # Verificar que hay suficientes widgets
                if base_index + 2 >= len(combenu):
                    print(f"Advertencia: No hay suficientes widgets para el registro {i+1}")
                    break
                
                try:
                    # Configurar modelo (ComboBox)
                    modelo_widget = combenu[base_index]
                    if isinstance(modelo_widget, QComboBox):
                        modelo_widget.addItem(model)
                        modelo_widget.setCurrentText(model)
                        modelo_widget.setEnabled(True)
                    
                    # Configurar serie (ComboBox)
                    serie_widget = combenu[base_index + 1]
                    if isinstance(serie_widget, QComboBox):
                        serie_str = str(serie)
                        serie_widget.addItem(serie_str)
                        serie_widget.setCurrentText(serie_str)
                        serie_widget.setEnabled(True)
                    
                    # Configurar factor de calibración (LineEdit)
                    calibr_widget = combenu[base_index + 2]
                    if isinstance(calibr_widget, QLineEdit):
                        calibr_widget.setText(str(calibr_fact))
                        calibr_widget.setEnabled(True)
                    
                    #print(f"[DB equipos] Cargado: {model}, {serie}, {calibr_fact}")
                    
                except (IndexError, AttributeError) as e:
                    print(f"Error configurando widgets para registro {i+1}: {e}")
                    continue
            
            return True
            
        except sqlite3.Error as e:
            print(f"Error de BD en Traerinfo: {e}")
            return False
        except Exception as e:
            print(f"Error inesperado en Traerinfo: {e}")
            traceback.print_exc()
            return False
    
    def Traerinfo_cunas(self):
        """
        Función optimizada para leer datos de cuñas desde BD
        """
        #print("------ Función Traerinfo_cunas (optimizada)")
        
        try:
            conn = self.db_manager.obtener_conexion()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT angulo, in_val, out_val, right_val, left_val
                FROM control_cunas
                WHERE ref = ?
                ORDER BY angulo
            """, (self.ref,))
            
            results = cursor.fetchall()

            if not results:
                #print("No hay datos guardados de cuñas para esta ref:", self.ref)
                return False

            # Mapeo optimizado de ángulos a widgets
            combo_dict = {
                15: {"in": getattr(self, 'cuna_15_in', None), "out": getattr(self, 'cuna_15_out', None), 
                     "right": getattr(self, 'cuna_15_ri', None), "le": getattr(self, 'cuna_15_le', None)},
                30: {"in": getattr(self, 'cuna_30_in', None), "out": getattr(self, 'cuna_30_out', None), 
                     "right": getattr(self, 'cuna_30_ri', None), "le": getattr(self, 'cuna_30_le', None)},
                45: {"in": getattr(self, 'cuna_45_in', None), "out": getattr(self, 'cuna_45_out', None), 
                     "right": getattr(self, 'cuna_45_ri', None), "le": getattr(self, 'cuna_45_le', None)},
                60: {"in": getattr(self, 'cuna_60_in', None), "out": getattr(self, 'cuna_60_out', None), 
                     "right": getattr(self, 'cuna_60_ri', None), "le": getattr(self, 'cuna_60_le', None)},
            }

            # Mapeo de valores a textos
            valor_a_texto = {1: "Funciona", 0: "No funciona"}
            
            registros_procesados = 0
            
            for row in results:
                try:
                    angulo, in_val, out_val, right_val, left_val = row

                    if angulo not in combo_dict:
                        print(f"Ángulo {angulo} no reconocido")
                        continue

                    # Mapeo de posiciones a valores
                    mapping = {
                        "in": in_val,
                        "out": out_val,
                        "right": right_val,
                        "le": left_val,
                    }

                    # Configurar cada combo de este ángulo
                    for pos, val in mapping.items():
                        combo = combo_dict[angulo][pos]
                        if combo is not None and isinstance(combo, QComboBox):
                            combo.blockSignals(False)
                            texto = valor_a_texto.get(val, "Seleccionar...")
                            
                            # Buscar el texto en el combo o agregarlo
                            if combo.findText(texto) != -1:
                                combo.setCurrentText(texto)
                            else:
                                combo.addItem(texto)
                                combo.setCurrentText(texto)
                            
                            combo.setEnabled(True)  # Bloquear edición
                            combo.blockSignals(False)
                            
                            # Aplicar color según estado
                            self.actualizar_color(combo, texto)
                        else:
                            print(f"Widget no encontrado: cuna_{angulo}_{pos}")

                    registros_procesados += 1
                    
                except (ValueError, TypeError) as e:
                    print(f"Error procesando registro de cuña: {e}")
                    continue

            #print(f"Datos de cuñas cargados: {registros_procesados} registros")
            return registros_procesados > 0
            
        except sqlite3.Error as e:
            print(f"Error de BD en Traerinfo_cunas: {e}")
            return False
        except Exception as e:
            print(f"Error inesperado en Traerinfo_cunas: {e}")
            traceback.print_exc()
            return False

    def comboBox_seguridad(self, combenu):
        # Ya existe self.combos_seguridad como diccionario
        for angulo, posiciones in self.combos_seguridad.items():
            for key, combobox in posiciones.items():
                if isinstance(combobox, QComboBox):
                    combobox.clear()
                    combobox.addItems(["Seleccionar...", "Funciona", "No funciona"])
                    combobox.currentTextChanged.connect(
                        lambda text, cb=combobox: self.actualizar_color(cb, text)
                    )

    def actualizar_color(self, combobox, text):
        if text == "Funciona":
            combobox.setStyleSheet("""
                QComboBox {
                    padding: 5px;
                    min-width: 90px;
                    background-color: rgb(181, 212, 0);
                }
            """)
        elif text == "No funciona":
            combobox.setStyleSheet("""
                QComboBox {
                    padding: 5px;
                    min-width: 90px;
                    background-color: #FF4646;
                }
            """)
        else:  # "Seleccionar..." u otro
            combobox.setStyleSheet("""
                QComboBox {
                    padding: 5px;
                    min-width: 90px;
                    background-color: white;
                }
            """)

    @lru_cache(maxsize=50)
    def pruebatalas(self, nombre_tabla, ref, pdd = None, id_energia = None, id = False):
        """Consulta optimizada de tablas con caché y mejor manejo de errores"""
        try:
            # Usar pool de conexiones
            conn = self.db_manager.obtener_conexion()
            cursor = conn.cursor()
            # Query con parámetros seguros
            sql = f"SELECT * FROM {nombre_tabla} WHERE ref = ?"
            params = [ref]
            if id_energia is not None:
                sql += " AND id_energia = ?"
                params.append(id_energia)
            if pdd is not None:
                sql += " AND tam_pdd = ?"
                params.append(pdd)
            cursor.execute(sql, params)
            results = cursor.fetchall()
            if (id and hasattr(self, 'anual') and not self.anual) or (id and not hasattr(self, 'anual') and hasattr(self, 'esHc') and self.esHc):
                if id_energia is None:
                #Retornar los resultados sin el id
                    print(f"Retornando sin id_energia, {nombre_tabla}: ")
                    return [row[1:] for row in results] if results else []
                else:
                    return [row[2:] for row in results] if results else []
            else:
                return results if results else []
            
        
            
        except sqlite3.Error as e:
            print(f"Error de BD en pruebatalas ({nombre_tabla}): {e}")
            return []
        except Exception as e:
            print(f"Error inesperado en pruebatalas ({nombre_tabla}): {e}")
            traceback.print_exc()
            return []
    
    def discrepancias(self):
        """Calcula discrepancias de dosis y calidad con optimización y caché"""
        #print("..... Calculando discrepancias de dosis y calidad .....")
        
        try:
            # Configurar tolerancias desde constantes
            tolerancias = {
                'fotones': self.TOLERANCIA_FOTONES,
                'electrones': self.TOLERANCIA_ELECTRONES
            }
            
            # Procesar discrepancias de dosis y calidad
            self._procesar_discrepancias_dosis_calidad(tolerancias)
            self._procesar_discrepancias_simetria_planicidad(tolerancias)
            
            #print("Cálculo de discrepancias completado.")
            
        except Exception as e:
            print(f"Error en cálculo de discrepancias: {e}")
            traceback.print_exc()

    def _procesar_discrepancias_dosis_calidad(self, tolerancias):
        """Procesa discrepancias de dosis y calidad de manera optimizada"""
        
        @lru_cache(maxsize=100)
        def operacion_dosis_optimizada(dato_str):
            """Calcula discrepancia de dosis con caché y validación mejorada"""
            if not dato_str or dato_str == "":
                #print("Dato de dosis vacío o inválido")
                return None
            try:
                dato_float = float(dato_str)
                if dato_float == 0.0:
                    return 0.0                                                                                                            
                return abs(100 * (1 - dato_float) )
            except (ValueError, TypeError, ZeroDivisionError):
                return 0.0

        @lru_cache(maxsize=100)
        def operacion_calidad_optimizada(dato_str, val_teo_str):
            """Calcula discrepancia de calidad con caché y validación mejorada"""
            if not dato_str or dato_str == "" or not val_teo_str or val_teo_str == "":
                #print("Dato de calidad o valor teórico vacío o inválido")
                #print( f"dato_str: '{dato_str}', val_teo_str: '{val_teo_str}'" )
                return None
            try:
                dato_float = float(dato_str)
                val_teo_float = float(val_teo_str)
                if dato_float == 0.0:
                    return None
                return round(abs((val_teo_float - dato_float) / val_teo_float * 100), 4)
            except (ValueError, TypeError, ZeroDivisionError):
                return 0.0

        def mostrar_resultado_optimizado(valor, out_widget, tolerancia):
            """Muestra resultado con estilo optimizado"""
            if valor is None:
                out_widget.setText("0.0")
                out_widget.setStyleSheet("border: 1px solid rgb(51, 142, 158);")
                return
            
            texto = f"{valor:.2f}"
            out_widget.setText(texto)
            
            # Aplicar estilo según tolerancia
            if valor > tolerancia:
                out_widget.setStyleSheet("border: 1px solid #ff4d4d; color: #ff4d4d;")
            else:
                out_widget.setStyleSheet("border: 1px solid #c1df08;")

        # Mapeo optimizado para discrepancias de dosis y calidad
        mapping = {
            "6mv":  ("ln_dosis_ref_cgy_um_6mv",  "ln_calidad_pdd20_10_6mv",
                    "ln_discrepancia_dosis_6mv","ln_discrepancia_calidad_6mv", "val_teo_6mv"),
            "15mv": ("ln_dosis_ref_cgy_um_15mv", "ln_calidad_pdd20_10_15mv",
                    "ln_discrepancia_dosis_15mv","ln_discrepancia_calidad_15mv", "val_teo_15mv"),
            "6mev": ("ln_dosis_ref_cgy_um_6mev", "ln_calidad_j2_j1_6mev",
                    "ln_discrepancia_dosis_6mev","ln_discrepancia_calidad_6mev", "val_teo_6mev"),
            "9mev": ("ln_dosis_ref_cgy_um_9mev", "ln_calidad_j2_j1_9mev",
                    "ln_discrepancia_dosis_9mev","ln_discrepancia_calidad_9mev", "val_teo_9mev"),
            "12mev":("ln_dosis_ref_cgy_um_12mev","ln_calidad_j2_j1_12mev",
                    "ln_discrepancia_dosis_12mev","ln_discrepancia_calidad_12mev", "val_teo_12mev"),
            "15mev":("ln_dosis_ref_cgy_um_15mev","ln_calidad_j2_j1_15mev",
                    "ln_discrepancia_dosis_15mev","ln_discrepancia_calidad_15mev", "val_teo_15mev"),
        }
        VALORES_REFERENCIA_CALIDAD = {
            "6mv": 0.665,
            "15mv": 0.761,
            "6mev": 0.483,
            "9mev": 0.500,
            "12mev": 0.606,
            "15mev": 0.605,
            }

        for energia, (dosis_attr, calidad_attr, salida_dosis_attr, salida_calidad_attr, val_teo_attr) in mapping.items():
            try:
                # Obtener widgets con validación
                widgets = self._obtener_widgets_discrepancia(dosis_attr, calidad_attr, salida_dosis_attr, salida_calidad_attr, val_teo_attr)
                if not widgets:
                    continue
                
                dosis_ref, calidad, salida_dosis, salida_calidad, val_teo = widgets
                
                # Determinar tolerancia según tipo de energía
                tolerancia = tolerancias['electrones'] if energia.endswith('mev') else tolerancias['fotones']
                

                # Calcular y mostrar discrepancia inicial de dosis
                self._calcular_mostrar_discrepancia(
                    dosis_ref.text(), salida_dosis, tolerancia, operacion_dosis_optimizada, mostrar_resultado_optimizado
                )
                valor_ref = VALORES_REFERENCIA_CALIDAD[energia]
                # Función robusta para discrepancia de calidad
                def actualizar_discrepancia_calidad(
                    calidad=calidad,
                    salida_calidad=salida_calidad,
                    tolerancia=tolerancia,
                    valor_ref=valor_ref
                ):
                    calidad_val = calidad.text()

                    resultado = operacion_calidad_optimizada(
                        calidad_val,
                        valor_ref
                    )

                    mostrar_resultado_optimizado(
                        resultado,
                        salida_calidad,
                        tolerancia
                    )

                # Llama una vez al inicio para mostrar el valor correcto si ambos campos ya tienen valor
                #
                actualizar_discrepancia_calidad()

                # Conectar eventos para calidad y val_teo a la misma función
                self._configurar_eventos(calidad, actualizar_discrepancia_calidad, f"discrepancy_calidad_{energia}")
                self._configurar_eventos(val_teo, actualizar_discrepancia_calidad, f"discrepancy_valteo_{energia}")

                # Conectar eventos para dosis (esto sí puede quedarse igual)
                self._conectar_eventos_discrepancia(
                    dosis_ref, salida_dosis, tolerancia, operacion_dosis_optimizada, mostrar_resultado_optimizado
                )
                
            except Exception as e:
                print(f"Error procesando energía {energia}: {e}")
                continue

    def _obtener_widgets_discrepancia(self, *attr_names):
        widgets = []
        for attr_name in attr_names:
            widget = getattr(self, attr_name, None)
            
            #print(f"Buscando widget '{attr_name}': {widget}")
            if not widget:
                print(f"Widget '{attr_name}' no encontrado")
                return None
            widgets.append(widget)
        return widgets

    def _calcular_mostrar_discrepancia(self, valor_texto, widget_salida, tolerancia, funcion_calculo, funcion_mostrar):
        """Calcula y muestra discrepancia con manejo de errores"""
        try:
            resultado = funcion_calculo(valor_texto)
            funcion_mostrar(resultado, widget_salida, tolerancia)
        except Exception as e:
            print(f"Error en cálculo de discrepancia: {e}")
            widget_salida.setText("0.0")
            widget_salida.setStyleSheet("border:  1px solid rgb(51, 142, 158);")

    def _conectar_eventos_discrepancia(self, widget_entrada, widget_salida, tolerancia, funcion_calculo, funcion_mostrar):
        """Conecta eventos de cambio de texto con debouncing"""
        def actualizar_discrepancia():
            self._calcular_mostrar_discrepancia(
                widget_entrada.text(), widget_salida, tolerancia, funcion_calculo, funcion_mostrar
            )
        
        self._configurar_eventos(widget_entrada, actualizar_discrepancia, f"discrepancy_{id(widget_entrada)}")

    def _procesar_discrepancias_simetria_planicidad(self, tolerancias):
        """Procesa discrepancias de simetría y planicidad de manera optimizada"""
        
        @lru_cache(maxsize=100)
        def valor_2cifras_cached(valor_str):
            """Convierte texto a float con caché"""
            try:
                return float(valor_str) if valor_str and valor_str.strip() else None
            except (ValueError, AttributeError):
                return 0.0

        def mostrar_resultado_sim_plan_optimizado(valor, widget, tolerancia_simetria, tolerancia_planicidad, es_simetria=True):
            """Muestra resultado de simetría/planicidad con optimización"""
            tolerancia = tolerancia_simetria if es_simetria else tolerancia_planicidad
            
            if valor is None or valor == 0.0:
                widget.setText("")
                widget.setStyleSheet("border: 1px solid rgb(51, 142, 158);")
                return

            # Formatear a 4 decimales
            widget.setText(f"{valor:.4f}")
            
            if valor > tolerancia:
                widget.setStyleSheet("border: 1px solid #ff4d4d; color: #ff4d4d;")
            else:
                widget.setStyleSheet("border: 1px solid #c1df08;")

        # Mapeo optimizado para simetría y planicidad
        mapping_simetria_planicidad = {
            "6mv":   ("ln_simetria_inplane_6mv", "ln_simetria_crossplane_6mv",
                        "ln_planicidad_inplane_6mv", "ln_planicidad_crossplane_6mv"),
            "15mv":  ("ln_simetria_inplane_15mv", "ln_simetria_crossplane_15mv",
                        "ln_planicidad_inplane_15mv", "ln_planicidad_crossplane_15mv"),
            "6mev":  ("ln_simetria_inplane_6mev", "ln_simetria_crossplane_6mev",
                        "ln_planicidad_inplane_6mev", "ln_planicidad_crossplane_6mev"),
            "9mev":  ("ln_simetria_inplane_9mev", "ln_simetria_crossplane_9mev",
                        "ln_planicidad_inplane_9mev", "ln_planicidad_crossplane_9mev"),
            "12mev": ("ln_simetria_inplane_12mev", "ln_simetria_crossplane_12mev",
                        "ln_planicidad_inplane_12mev", "ln_planicidad_crossplane_12mev"),
            "15mev": ("ln_simetria_inplane_15mev", "ln_simetria_crossplane_15mev",
                        "ln_planicidad_inplane_15mev", "ln_planicidad_crossplane_15mev"),
        }
        
        for energia, (sim_in_attr, sim_cros_attr, plan_in_attr, plan_cros_attr) in mapping_simetria_planicidad.items():
            try:
                # Obtener widgets
                sim_in = getattr(self, sim_in_attr, None)
                sim_cros = getattr(self, sim_cros_attr, None)
                plan_in = getattr(self, plan_in_attr, None)
                plan_cros = getattr(self, plan_cros_attr, None)
                
                # Determinar tolerancias
                if energia.endswith('mev'):
                    tol_simetria = tolerancias['electrones']
                    tol_planicidad = 4.5
                else:
                    tol_simetria = tolerancias['fotones']
                    tol_planicidad = 3.0
                
                # Procesar widgets de simetría
                for widget in [sim_in, sim_cros]:
                    if widget:
                        valor_inicial = valor_2cifras_cached(widget.text())
                        mostrar_resultado_sim_plan_optimizado(valor_inicial, widget, tol_simetria, tol_planicidad, True)
                        
                        # Conectar evento con debouncing
                        def crear_callback_simetria(w, tol_s, tol_p):
                            def actualizar():
                                valor = valor_2cifras_cached(w.text())
                                mostrar_resultado_sim_plan_optimizado(valor, w, tol_s, tol_p, True)
                            return actualizar
                        
                        callback = crear_callback_simetria(widget, tol_simetria, tol_planicidad)
                        self._configurar_eventos(widget, callback, f"symmetry_{id(widget)}")
                
                # Procesar widgets de planicidad
                for widget in [plan_in, plan_cros]:
                    if widget:
                        valor_inicial = valor_2cifras_cached(widget.text())
                        mostrar_resultado_sim_plan_optimizado(valor_inicial, widget, tol_simetria, tol_planicidad, False)
                        
                        # Conectar evento con debouncing
                        def crear_callback_planicidad(w, tol_s, tol_p):
                            def actualizar():
                                valor = valor_2cifras_cached(w.text())
                                mostrar_resultado_sim_plan_optimizado(valor, w, tol_s, tol_p, False)
                            return actualizar
                        
                        callback = crear_callback_planicidad(widget, tol_simetria, tol_planicidad)
                        self._configurar_eventos(widget, callback, f"planarity_{id(widget)}")

            except Exception as e:
                print(f"Error procesando simetría/planicidad para {energia}: {e}")
                continue

    def generar_reporte_pdf(self):
        from models.PDF.Mensuales.reportes_mensuales import guardarPDF_mensual, obtener_diccionario_600
        # F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS4.3): reportes_mensuales
        # busca el control con "fecha = ?" EXACTA -- pasar aquí una fecha
        # derivada de date_box sin día ("MM/yyyy") ya no coincidiría con lo
        # guardado en `controles.fecha` (que ahora sí trae día). self.fecha_control
        # es la fecha REAL del registro (la escribió limpiar_layout leyendo
        # de la BD, no una nueva derivación), así que es la que hay que usar.
        fecha = self.fecha_control if hasattr(self, 'fecha_control') else self.date_box.date().toString("dd/MM/yyyy")
        maquina = self.equipo_f  # O el atributo que corresponda a tu máquina
        diccionario = obtener_diccionario_600()  # O el que corresponda
        guardarPDF_mensual(self, fecha, maquina, diccionario=diccionario)

    