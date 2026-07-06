#...................................................................................................................................#
#                                                              BRAQUITERAPIA                                                        #
#...................................................................................................................................#
import io
from PyQt5.QtGui import QPixmap
from PIL import Image
from models.PDF.PDFWindow import PdfViewer
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
import tempfile
import pandas as pd
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.paginasControles.PruebasMensuales.PruebasMensuales import PruebaMensualBraq
from data.ManejoDatos.conection import Conexion
from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout, QWidget, QToolBox, QPushButton, QLabel, QComboBox, QTableWidget, 
                            QTableWidgetItem, QMessageBox, QDoubleSpinBox, QSpinBox, QLineEdit, QGridLayout, QDialog,
                            QDateEdit, QSplitter)
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtCore import pyqtSignal, Qt, QDate, QDateTime, QTimer
from PyQt5.QtGui import QFont, QColor
from resources.utils.matplotlib_lazy import get_matplotlib_components
from data.GraficasyTablas.unovsuno import graficarvstiempo
from data.GraficasyTablas.tablas import load_table, asignar_encabezados
from models.PDF.reportes import reporte
from models.PDF.pdf import generar_reporte_pdf_multitabla_mensual
from analisisImagenes.Analisis_PlacaRC import analizar_lineas
from analisisImagenes.ActividadFuente import graficar_linealidad, graficar_resultados, calcular_decaimiento
from data.ManejoDatos.load import (mostrar_db_linealidad, mostrar_db_mensualBraqui, verificar_eliminar, verificar_editar,
                                                guardarEdicion, cancelarEdicion, abrir_pelicula)
import datetime, sqlite3, html, re, traceback
import numpy as np
import time
import hashlib
from typing import Optional, Any, List, Tuple
import weakref
from contextlib import contextmanager


class GestorConexionDB:
    """Gestor centralizado de conexiones a base de datos con pool y reconexión automática"""
    _instancia = None
    _conexiones_activas = {}
    _cache_consultas = {}
    
    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
        return cls._instancia
    
    @contextmanager
    def obtener_conexion(self, reintentos: int = 3):
        """Context manager para obtener conexión con reintentos automáticos"""
        conn = None
        try:
            for intento in range(reintentos):
                try:
                    conn = Conexion().conectar()
                    if conn is not None:
                        break
                except Exception as e:
                    #logger.warning(f"Intento {intento + 1} de conexión falló: {e}")
                    if intento == reintentos - 1:
                        raise ConnectionError(f"No se pudo conectar después de {reintentos} intentos")
                    time.sleep(0.5)
            
            yield conn
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def ejecutar_consulta_con_cache(self, consulta: str, parametros: tuple = (), usar_cache: bool = True) -> List[Any]:
        """Ejecuta consulta con caché opcional"""
        cache_key = hashlib.md5(f"{consulta}_{parametros}".encode()).hexdigest()
        
        if usar_cache and cache_key in self._cache_consultas:
            #logger.debug(f"Consulta obtenida del caché: {cache_key}")
            return self._cache_consultas[cache_key]
        
        try:
            with self.obtener_conexion() as conn:
                cursor = conn.cursor()
                cursor.execute(consulta, parametros)
                resultado = cursor.fetchall()
                
                if usar_cache:
                    self._cache_consultas[cache_key] = resultado
                
                return resultado
        except Exception as e:
            #logger.error(f"Error en consulta: {e}")
            raise

class OptimizadorAnalisis:
    """Optimizador para análisis de imágenes sin caché innecesario"""
    def __init__(self):
        self._dependencias_cargadas = False
        self._modulos_importados = {}
    
    def precargar_dependencias(self):
        """Pre-carga librerías pesadas una sola vez al inicio"""
        if self._dependencias_cargadas:
            return
        
        try:
            import cv2
            import numpy as np
            self._modulos_importados['cv2'] = cv2
            self._modulos_importados['np'] = np
            self._dependencias_cargadas = True
            #print("✅ Dependencias pre-cargadas exitosamente")
        except ImportError as e:
            print(f"⚠️ Advertencia: No se pudieron pre-cargar algunas dependencias: {e}")
    
    def validar_imagen_rapida(self, ruta_imagen: str) -> bool:
        """Validación rápida de imagen antes de procesamiento pesado"""
        import os
        try:
            # Verificar que el archivo existe
            if not os.path.exists(ruta_imagen):
                return False
            
            # Verificar tamaño de archivo (evitar archivos corruptos)
            tamaño = os.path.getsize(ruta_imagen)
            if tamaño < 1000:  # Menor a 1KB, probablemente corrupto
                return False
            
            # Verificar extensión de imagen
            extensiones_validas = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
            _, ext = os.path.splitext(ruta_imagen.lower())
            if ext not in extensiones_validas:
                return False
            
            return True
        except Exception as e:
            
            print(f"Error validando imagen: {e}")
            return False

class GestorRecursos:
    """Gestor para reutilización de recursos como canvas y figuras"""
    def __init__(self):
        self._figuras_reutilizables = weakref.WeakSet()
        self._canvas_reutilizables = weakref.WeakSet()
    
    def obtener_figura_reutilizable(self):
        """Obtiene una figura reutilizable o crea una nueva"""
        for figura in self._figuras_reutilizables:
            if hasattr(figura, 'clear'):
                figura.clear()
                return figura
        # Si no hay figuras disponibles, crear nueva
        mpl = get_matplotlib_components()
        Figure = mpl['Figure']
        nueva_figura = Figure()
        self._figuras_reutilizables.add(nueva_figura)
        return nueva_figura
    
    def obtener_canvas_reutilizable(self, figura=None):
        """Obtiene un canvas reutilizable o crea uno nuevo"""
        if figura is None:
            figura = self.obtener_figura_reutilizable()
        
        for canvas in self._canvas_reutilizables:
            if hasattr(canvas, 'figure'):
                canvas.figure = figura
                return canvas
        
        # Si no hay canvas disponibles, crear nuevo
        mpl = get_matplotlib_components()
        FigureCanvas = mpl['FigureCanvas']
        nuevo_canvas = FigureCanvas(figura)
        self._canvas_reutilizables.add(nuevo_canvas)
        return nuevo_canvas

# Instancias globales
gestor_db = GestorConexionDB()
optimizador_analisis = OptimizadorAnalisis()
gestor_recursos = GestorRecursos()

# ---------------------------------------------------------  Prueba Diaria ---------------------------------------------------------- #

class PruebaDiariaBraq(PruebaBasico):
    """ 
    Inicialización de datos, construcción de la interfaz y definición de la tabla de la base de datos.
    Incluye mejoras de rendimiento: lazy loading, cache, debouncing y gestión de memoria.
    """
    def __init__(self, user_id):
        super(PruebaDiariaBraq, self).__init__()
        #print("PruebaDiariaBraq       __init__ called")
        
        # Pre-cargar dependencias para mejor rendimiento
        optimizador_analisis.precargar_dependencias()
        
        # Inicializar timers para debouncing
        self._timer_busqueda = QTimer()
        self._timer_busqueda.setSingleShot(True)
        self._timer_busqueda.timeout.connect(self._ejecutar_busqueda_filtrada)
        
        # Timer para debouncing de análisis cuando se cambian parámetros
        self._timer_analisis = QTimer()
        self._timer_analisis.setSingleShot(True)
        self._timer_analisis.timeout.connect(self._ejecutar_analisis_diferido)
        
        # Cache y gestión de recursos
        self._widgets_lazy = {}
        self._recursos_creados = set()
        
        
        try:
            self.initDATA(user_id)
            self.initUI()
            self._cargar_datos_iniciales()
            self.button_click()
            self._inicializar_tabla_resultados()
            self.actividad_braq_automatica()
            
            
        except Exception as e:
            print(f"Error en inicialización de PruebaDiariaBraq: {e}")
            self._mostrar_error_usuario("Error de Inicialización", 
                                    f"No se pudo inicializar la interfaz: {str(e)}")
    
    def _cargar_datos_iniciales(self):
        """Carga datos iniciales de forma optimizada"""
        try:
            load_table(self, self.boolean_colums, self.actividad_ciclos, 'braqui')
            asignar_encabezados(self, 'braqui')
        except Exception as e:
            #logger.error(f"Error cargando datos iniciales: {e}")
            raise
        self.parametros_creados = False
    def _inicializar_tabla_resultados(self):
        """Inicializa tabla de resultados con lazy loading"""
        if 'resultados_table' not in self._widgets_lazy:
            self.resultados_table = QTableWidget()
            self.resultados_table.setColumnCount(7)
            self.resultados_table.setHorizontalHeaderLabels([
                "User", "Fecha", "Tipo", "Distancias", "Promedio", "Desviación, Imagen"
            ])
            self.resultados_table.setEditTriggers(QTableWidget.NoEditTriggers)
            # Conectar el doble click para mostrar imágenes
            self.resultados_table.itemDoubleClicked.connect(self.abrir_imagen_resultado)
            self._widgets_lazy['resultados_table'] = self.resultados_table
    
    """ Diccionario con los nombres de las herramientas para los category (menu desplegable para ingresar).                                                                                     """
    def initDATA(self, user_id):
        
        self.diccionario_invertido = {
            'int_con_box': ['Interrupción desde consola', '', 'scatter'],
            'emerg_con': ['Parada de emergencia','', 'scatter'],
            'blq_puerta': ['Bloqueo de puerta','', 'scatter'],
            'pos_fuente': ['Indicador de posición','', 'scatter'],
            'res_fuente': ['Respaldo retorno de fuente','', 'scatter'],
            'key_fuente': ['Interruptor de llave','', 'scatter'],
            'mon_area': ['Monitor de área','', 'scatter'],
            'lum_puerta': ['Indicador luminoso', '', 'scatter'],
            'tub_guia': ['Conexión tubo guía', '', 'scatter'],
            'visual_sys': ['Sistema de visualización', '', 'scatter'],
            'intercom': ['Sistema de intercounicación', '', 'scatter'],
            'mon_rad_port': ['Monitor de radiación potátil', '', 'scatter'],
            'tol_rep_act_ci': ['Actividad reportada', '', 'line'],
            'tol_exp_act': ['Actividad esperada', '', 'line'],
            'tol_cyc_dummy': ['Ciclos del Dummy', '', 'line'],
            'tol_cyc_rad': ['Ciclos de la fuente', '', 'line'],
            'observaciones' : ['Observaciones', '', 'Na']
        }
        
        self.init_data(user_id, self.diccionario_invertido)

    """ Crea la estructura visual general, usa QToolBox para organizar las secciones y prepara el area de gráficos                                                                               """
    def initUI(self):
        self.main_layout = QHBoxLayout()

        archivo = 'widgets.xlsx'
        _ = self.setupBox(archivo, 'encabezado_braq')
        self.date_box.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.date_box.setDateTime(QDateTime.currentDateTime())
        df, n, layouts, _ = self.setupBox(archivo, 'preguntas_braq', main=False)

        self.datos_tabla = self.storeDailyTests(df)

        self.category1 = QWidget()
        self.category2 = QWidget()
        self.category3 = QWidget()
        self.category4 = self.imagenUpLoader()

        toolbox = QToolBox()
        self.general_layout.addWidget(toolbox)

        for i, layout in enumerate(layouts, 1):
            getattr(self, f'category{i}').setLayout(layout)

        toolbox.addItem(self.category1, 'SEGURIDAD')
        toolbox.addItem(self.category2, 'ASPECTOS DOSIMÉTRICOS')
        toolbox.addItem(self.category4, 'ANALIZAR IMÁGENES')
        toolbox.addItem(self.category3, 'OBSERVACIONES')

        _ = self.setupBox(archivo, 'btn')
        
        self.btn_add.setObjectName("boton_nofunciona")
        self.btn_add.setEnabled(True)
        self.btn_add.setProperty("estado", "noselected")

        # función compartida para crear los layouts y cosas espaciales
        self.init_ui(df, self.diccionario_invertido)

        self.setupButtonConnections(df, maquina='braqui')

        self.boton_volver = QPushButton("Volver")
        self.boton_volver.setFixedSize(100, 40)
        self.boton_volver.setStyleSheet("background-color: #4a8892; color: white; border-radius: 10px;")
        self.boton_volver.clicked.connect(self.mostrar_canvas)

        self.boton_eliminar = QPushButton("Eliminar fila")
        self.boton_eliminar.setFixedSize(100, 40)
        self.boton_eliminar.setStyleSheet("background-color: #d9534f; color: white; border-radius: 10px;")
        self.boton_eliminar.clicked.connect(self.eliminar_fila_resultado)
        

    """ Crea los botones y conecta las acciones de los botones a sus respectivas funciones                                                                                                        """
    def cargar_dailytest_desde_db(self, fecha=None):
        """
        Carga datos de pruebas diarias desde la base de datos y los mapea a los widgets de la GUI.
        
        Args:
            fecha: QDate object o None. Si es None, usa la fecha del date_box.
        """
        if fecha is None:
            fecha = self.date_box.date()
        
        # Convertir QDate a string en formato compatible con la BD
        fecha_str = fecha.toString("yyyy-MM-dd")
        
        db = self.opeenDatabase()
        if not db:
            return
        
        try:
            query = QSqlQuery(db)
            print("consultando db")
            # Preparar la consulta
            query.prepare("""
                SELECT * FROM braqui 
                WHERE date = ? 
                LIMIT 1
            """)
            query.addBindValue((fecha_str))
            #query.addBindValue(str(self.user_id))
            print(fecha_str)
            
            if not query.exec():
                print(f"Error en consulta: {query.lastError().text()}")
                db.close()
                return
            
            if query.next():
                # Limpiar datos actuales primero
                self.botones_finales.clear()
                
                # Obtener todos los nombres de columnas de la consulta
                record = query.record()
                
                # 1. Cargar botones Funciona/No Funciona (columnas booleanas)
                for columna_db in self.boolean_colums:
                    # Verificar si la columna existe en el resultado
                    if record.indexOf(columna_db) == -1:
                        continue
                        
                    valor = query.value(columna_db)
                    
                    # Buscar el par de botones correspondiente
                    found = False
                    for fun, nofun in zip(self.df_bnt_funciona, self.df_bnt_nofunciona):
                        # Verificar si este par de botones corresponde a esta columna
                        # Comparar con el nombre de la columna
                        if columna_db.replace('_', ' ') in fun.lower() or columna_db in fun:
                            btn_fun = getattr(self, fun, None)
                            btn_nofun = getattr(self, nofun, None)
                            
                            if btn_fun and btn_nofun:
                                if valor == 1 or valor == '1' or valor == True:
                                    # Activar "Funciona"
                                    btn_fun.setChecked(True)
                                    self.cambiar_estilo(btn_fun, btn_nofun)
                                    self.botones_finales.add((btn_fun, fun))
                                else:
                                    # Activar "No Funciona"
                                    btn_nofun.setChecked(True)
                                    self.cambiar_estilo(btn_nofun, btn_fun)
                                    self.botones_finales.add((btn_nofun, nofun))
                                found = True
                                break
                    
                    if not found:
                        print(f"⚠ No se encontraron botones para: {columna_db}")
                
                # 2. Cargar QLineEdit (datos numéricos)
                columnas_numericas = ['line_1_rep_act_ci', 'line_1_exp_act_ci', 'line_1_cyc_dummy', 'line_1_cyc_rad']
                
                """ 

                Querida futura persona que le hará mantenimiento a este código, solo tengo una cosa que decir: Que Dios se apiade de ti.
                
                
                """
                
                if record.indexOf('tol_rep_act_ci') != -1:
                    valor_rep = query.value('tol_rep_act_ci')
                    print(valor)
                    if hasattr(self, 'line_1_rep_act_ci'):
                        self.line_1_rep_act_ci.setText(str(valor_rep))
                        
                if record.indexOf('tol_exp_act') != -1:
                    valor_exp = query.value('tol_exp_act')
                    print(valor)
                    if hasattr(self, 'line_1_exp_act_ci'):
                        self.line_1_exp_act_ci.setText(str(valor_exp))
      
                if record.indexOf('tol_cyc_dummy') != -1:
                    valor_dumm = query.value('tol_cyc_dummy')
                    print(valor)
                    if hasattr(self, 'line_1_cyc_dummy'):
                        self.line_1_cyc_dummy.setText(str(valor_dumm))
                        
                if record.indexOf('tol_cyc_rad') != -1:
                    valor_rad = query.value('tol_cyc_rad')
                    print(valor)
                    if hasattr(self, 'line_1_cyc_rad'):
                        self.line_1_cyc_rad.setText(str(valor_rad))
                    
                # 3. Cargar observaciones
                if record.indexOf('observaciones') != -1:
                    obs_valor = query.value('observaciones')
                    if obs_valor and hasattr(self, 'observaciones'):
                        self.observaciones.setText(str(obs_valor))
                        print(obs_valor)
                        print(f"✓ Cargadas observaciones")
                if record.indexOf('pelicula') != -1:
                    img_path = query.value('pelicula')
                    if img_path and str(img_path).strip():
                        self._cargar_imagen_pelicula((img_path))
                        
                        
                    else:
                        # Si no hay imagen, limpiar el canvas
                        self._limpiar_canvas()
                
                # 4. Actualizar el date_box con la fecha cargada (sin disparar señal)
                self.date_box.blockSignals(True)
                self.date_box.setDate(fecha)
                self.date_box.blockSignals(False)
                
                # 5. Verificar si se debe habilitar el botón de añadir
                self.checkBotonesFinales()
                
                print(f"✓ Datos del {fecha_str} cargados correctamente.")
                print(f"  - Botones finales: {len(self.botones_finales)}")
                
            else:
                print(f"No hay datos registrados para la fecha {fecha_str}.")
                self._limpiar_canvas()
                
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f"✗ Error al cargar datos: {str(ex)}")
        finally:
            db.close()
    def _cargar_imagen_pelicula(self, imagen_blob):
        """
        Carga y muestra una imagen en el canvas desde un BLOB de la base de datos.
        
        Args:
            imagen_blob: Datos binarios de la imagen (BLOB de la BD)
        """
        from PyQt5.QtWidgets import QMessageBox
        from io import BytesIO
        
        try:
            # Verificar que hay datos
            
            if not imagen_blob:
                print("⚠ No hay datos de imagen en el BLOB")
                self._limpiar_canvas()
                return
            
            # Convertir a bytes usando la misma lógica que en tu código
            if isinstance(imagen_blob, bytes):
                img_data = imagen_blob
            elif isinstance(imagen_blob, str):
                img_data = imagen_blob.encode("latin1")
            else:
                # Intentar convertir QByteArray u otros tipos
                try:
                    img_data = bytes(imagen_blob)
                except:
                    print(f"⚠ Tipo de dato no reconocido: {type(imagen_blob)}")
                    self._limpiar_canvas()
                    return
            
            # Verificar que tenemos datos válidos
            if len(img_data) == 0:
                print("⚠ El BLOB de imagen está vacío")
                self._limpiar_canvas()
                return
            
            # Limpiar el canvas antes de mostrar nueva imagen
            
            
            # Cargar imagen desde bytes usando PIL/Pillow
            from PyQt5.QtGui import QPixmap
            from PIL import Image
            import numpy as np
            
            # Crear objeto de imagen desde bytes
            imagen_io = BytesIO(img_data)
            img = Image.open(imagen_io)
            
            # Convertir a RGB si es necesario (algunas imágenes pueden estar en otros modos)
            if img.mode != 'RGB':
                img = img.convert('RGB')
             
            # Convertir a array numpy para matplotlib
            img_array = np.array(img)
            from openpyxl.drawing.image import Image as Im
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(img_data)
                tmp.flush()
                tmp_path = tmp.name
            
            self.imagen_path = tmp_path
            
                # Asegurar que toolbar esté visible
        # Limpiar imagen previa del QLabel
           

            # Cargar imagen desde bytes usando PIL
        

            # Convertir PIL → QPixmap
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            pix = QPixmap()
            pix.loadFromData(buffer.read())

            # Mostrar en el QLabel
            #self.label_imagen.setAlignment(Qt.AlignCenter)
            #self.label_imagen.setScaledContents(True)
            self.label_imagen.setPixmap(pix)
            if not self.parametros_creados:
                
                self._crear_parametros()
                self._crear_interfaz_parametros()
                self.parametros_creados=True
                
            
            print(f"✓ Imagen cargada desde BLOB ({len(img_data)} bytes)")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"✗ Error cargando imagen desde BLOB: {e}")
            QMessageBox.warning(self, "Error", f"No se pudo cargar la imagen desde la base de datos:\n{str(e)}")
            self._limpiar_canvas()


    def _limpiar_canvas(self):
        """
        Limpia el canvas eliminando cualquier contenido mostrado.
        """
        try:
            if hasattr(self, 'figure'):
                self.figure.clear()
                self.canvas.draw()
            print("✓ Canvas limpiado")
        except Exception as e:
            print(f"⚠ Error limpiando canvas: {e}")

    def actividad_braq_automatica(self, fecha = None):
        """ 
        La idea es obtener los datos de registros anteriores y modificarlos y que se guarden con respecto a la fuente
        correspondiente a esa fecha, también, obtener la actividad esperada de una fuente pasada o presente según
        la selección de una fecha.
        - Crear una variable que almanece el serial actual o correspondiente a una fecha
        -Obtener la dosis inicial según el serial
        -Calcular el tiempo transcurrido entre ese instante y la fecha actual
        """
        try:
            conn = sqlite3.connect('BaseDatosQA.db')
            cursor = conn.cursor()
            if fecha is None:
                current_datetime = self.date_box.dateTime().toPyDateTime()
            else:
                current_datetime = fecha.toPyDateTime()
            # if fecha is None:
            #     current_datetime = self.date_box.dateTime().toPyDateTime()
            # else:
            #     current_datetime = fecha
            
            cursor.execute("""
                SELECT tc.fecha, tc.fecha_cer, tc.serie, tc.intensidad
                FROM TipoCalibracion tc
                WHERE tc.Tipo = 'Cambio de fuente'
                AND tc.fecha <= ?
                ORDER BY tc.fecha DESC
                LIMIT 1
            """, (current_datetime.strftime("%Y-%m-%d %H:%M:%S"),))

            row = cursor.fetchone()
            if not row:
                print("No existe fuente válida antes de esa fecha")

            fecha_instalacion, fecha_a0_str, serie, a0 = row

            fecha_a0 = datetime.datetime.fromisoformat(fecha_a0_str)

            dias = (current_datetime - fecha_a0).total_seconds() / (3600*24)

            periodo_medio = 73.83
            print(a0)
            actividad = calcular_decaimiento(fecha_a0.strftime("%Y-%m-%d %H:%M:%S"), current_datetime.strftime("%Y-%m-%d %H:%M:%S"), a0, vida_media_dias=73.83)
            #actividad = a0*np.exp((-np.log(2))*dias/periodo_medio)

            
            
            if actividad:
                actividad = round(actividad, 4)
                print(" La actividad es: ", actividad)
                if hasattr(self, 'line_1_exp_act_ci'):
                    self.line_1_exp_act_ci.setText(str(actividad))
            
        except Exception as e:
            print("Error no mayor ", e)
      
    def tolerancia(self):
        try:
        
            if hasattr(self, 'line_1_exp_act_ci') and hasattr(self, 'line_1_rep_act_ci'):
                expected = float(self.line_1_exp_act_ci.text())
                calculated = float(self.line_1_rep_act_ci.text())
                tol = abs(expected-calculated)/expected * 100
                if tol > 3:
                    self.line_1_rep_act_ci.setStyleSheet(
                "QLineEdit { background-color: #ffcccc; border: 1px solid red; }"
            )
                else:
                    self.line_1_rep_act_ci.setStyleSheet("")
        except Exception as e:
            print(e)



    def button_click(self):
        #print("Entra a la función button_click en la clase PruebaDiariaBraq en braquiterapia.py")
        self.fuera_servicio.clicked.connect(self.reasignar_botonySERVICIO)
        self.btn_add.clicked.connect(lambda _, maquina='braqui', otro = "Diario" : self.ordenar_botones(maquina, self.fueradeservicio, otro))
        self.btn_add.clicked.connect(lambda: load_table(self, self.boolean_colums, self.actividad_ciclos, 'braqui'))
        self.btn_add.clicked.connect(lambda:asignar_encabezados(self, 'braqui'))
        
        #self.btn_add.clicked.connect(lambda _: self.clean_info(imagenes=False))
        #self.btn_add.clicked.connect(lambda _:self.clean_info)

        self.btn_clean.clicked.connect(lambda _: self.clean_info(imagenes=True))
        
        self.btn_submit.clicked.connect(
            lambda _, maquina=self.mach_name2.text(), id_maquina=self.code_1.text(): 
                reporte(self, fecha=self.date_box.date().toString('yyyy-MM-dd'), 
                        maquina=maquina, id_maquina=id_maquina, tipo_reporte='diario', 
                        diccionario=self.diccionario_invertido, umbrales=None)
        )

        self.boton_aceptar.clicked.connect(self.subirlisto)
        self.posi_inicial = "Diario"
        self.boton_aceptar.clicked.connect(lambda _, line=None: self.checkBotonesFinales(line, braqui=True, otro=self.posi_inicial))
        self.no_control_day()
        self.boton_cancel.clicked.connect(self.cancelarbraqui)
        
        """for line in self.df_lines:
            dato = getattr(self, line)
            dato.textChanged.connect(lambda _, line=line: self.checkBotonesFinales(line, braqui=True))"""
        
        self.btn_delete.clicked.connect(lambda _, maquina='braqui': self.verificar_eliminar(maquina, [self.boolean_colums, self.actividad_ciclos]))

        self.menu_graficar.currentIndexChanged.connect(self.mostrar_submenu)
        
        for grafica in self.graficar:
            grafica.currentIndexChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
            self.btn_submit.clicked.connect(lambda _, grafica=grafica: self.plotter(grafica))
            self.limit1.dateChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
            self.limit2.dateChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
        
        self.search_bar.textChanged.connect(self._iniciar_busqueda_debounced)
        
        self.edit_table.clicked.connect(self.verificar_editar)

        self.accept_edit.clicked.connect(lambda: self.cargarDatosEditados(self.item, self.old_value, "braqui"))
        self.accept_edit.clicked.connect(lambda: load_table(self, self.boolean_colums, self.actividad_ciclos, 'braqui'))
        self.accept_edit.clicked.connect(lambda:asignar_encabezados(self, 'braqui'))
        
        self.cancel_edit.clicked.connect(lambda: self.cancelarEdicion(self.item, self.old_value))
        self.cancel_edit.clicked.connect(lambda: load_table(self, self.boolean_colums, self.actividad_ciclos, 'braqui'))
        self.cancel_edit.clicked.connect(lambda:asignar_encabezados(self, 'braqui'))
        
        if hasattr(self, 'date_box'):
            self.date_box.dateChanged.connect(self.cargar_dailytest_desde_db)
            self.date_box.dateTimeChanged.connect(self.actividad_braq_automatica)
        self.line_1_rep_act_ci.textChanged.connect(self.tolerancia)
        self.subir_sin_datos.clicked.connect(self._subir_vacio)
        

    """ Muestra el submenu de graficas dependiendo de la seleccion del menu principal 
    """
        
    def no_control_day(self):
        if hasattr(self, 'subir_sin_datos') and self.subir_sin_datos:
            print("Botón subir sin datos")
            self.subir_sin_datos.setEnabled(False)
        
        self.observaciones.textChanged.connect(lambda _: self.subir_sin_datos.setEnabled(True))
    def _subir_vacio(self):
        """Setea campos vacíos y luego guarda en la BD."""
        self._setear_estado_vacio()          # 1) poblar botones_finales con valores vacíos
        self.ordenar_botones(                # 2) guardar en la base de datos
            'braqui', 
            self.fueradeservicio, 
            "Diario"
        )
    def _setear_estado_vacio(self):
        """Pone todos los campos en cero o vacío."""
        # Limpiar botones funciona/no funciona
        self.botones_finales.clear()
        
        # Setear líneas numéricas a "0"
        for line_name in ['line_1_rep_act_ci', 'line_1_exp_act_ci',
                        'line_1_cyc_dummy', 'line_1_cyc_rad']:
            if hasattr(self, line_name):
                widget = getattr(self, line_name)
                widget.blockSignals(True)
                widget.setText("0")
                widget.blockSignals(False)
        
        # Limpiar observaciones
        
        # Setear botones booleanos a False (no funciona)
        


        
            
    def resetear_imagen_ui(self):
        # --- LIMPIAR LAYOUT DEL CANVAS ---
        # --- LIMPIAR FIGURA ---
        if hasattr(self, 'figure'):
            self.figure.clear()

        # --- RESTAURAR UPLOADER ---
        self.label_imagen.clear()
        
        # self.analizar.hide()
        # self.boton_guardar.hide()
        # self.spin_umbral.hide()
        # self.spin_dist.hide()
        # self.label_umbral.hide()
        # self.label_dist.hide()
        #self.parametros_creados=False

        
        

        self.imagen_path = None
        

    def mostrar_submenu(self):
        
        for grafica in self.graficar:
            grafica.hide()
            grafica.setCurrentIndex(0)
        selection = self.menu_graficar.currentIndex()
        
        if selection > 0 and selection <= len(self.graficar):
            self.graficar[selection-1].show()  

    """ Crea los parámetros de umbral y distancia mínima entre picos, y los botones de analizar y guardar                                                                                            """
    def _crear_parametros(self):
        layout = QHBoxLayout()
        self.label_umbral = QLabel("Umbral Relativo:")
        self.label_umbral.setFont(QFont("Arial", weight=QFont.Bold))
        self.spin_umbral = QDoubleSpinBox()
        self.spin_umbral.setRange(0.0,30.0)
        self.spin_umbral.setSingleStep(0.1)
        self.spin_umbral.setDecimals(1)
        self.spin_umbral.setValue(1.0)
        self.spin_umbral.setFixedSize(150, 40)
        layout.addWidget(self.label_umbral)
        layout.addWidget(self.spin_umbral)

        self.label_dist = QLabel("Distancia mínima \n entre picos:")
        self.label_dist.setFont(QFont("Arial", weight=QFont.Bold))
        self.spin_dist = QSpinBox()
        self.spin_dist.setRange(1, 2000)
        self.spin_dist.setValue(40)
        self.spin_dist.setFixedSize(150, 40)
        layout.addWidget(self.label_dist)
        layout.addWidget(self.spin_dist)
        layout.addStretch()
        
        # Conectar cambios de parámetros al debouncing (útil para ajustes en la misma imagen)
        self.spin_umbral.valueChanged.connect(self.analizar_imagen_con_debouncing)
        self.spin_dist.valueChanged.connect(self.analizar_imagen_con_debouncing)

        # Primero crea el layout vertical
        botones_vertical = QVBoxLayout()
        self.analizar = QPushButton("Analizar")
        self.analizar.setFixedSize(100, 40)
        botones_vertical.addWidget(self.analizar)
        self.analizar.clicked.connect(self.analizar_imagen)

        self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.setFixedSize(100, 40)
        self.boton_guardar.setStyleSheet("background-color: rgb(181, 212, 0); color: white; border-radius: 10px;")
        botones_vertical.addWidget(self.boton_guardar)

        self.boton_guardar.clicked.connect(self.guardar_datos)


        # Agrega el layout vertical de botones al layout horizontal principal
        layout.addLayout(botones_vertical)

        return layout  # <-- Devuelve el layout

    def analizar_imagen(self) -> Optional[str]:
        """
        Crea el layout para subir imágenes, analizar y llama la función de análisis.
        Incluye caché de resultados y manejo mejorado de errores.
        """
        ##logger.info("Iniciando análisis de imagen")

        if not self.imagen_path:
            self._mostrar_error_usuario("Advertencia", "Primero selecciona una imagen.")
            return None

        try:
            # Crear parámetros layout si no existe (lazy loading)
            if getattr(self, 'parametros_layout', None) is None:
                self._crear_interfaz_parametros()

            # Obtener parámetros actuales
            umbral = self.spin_umbral.value()
            distancia = self.spin_dist.value()

            # Validación rápida antes del procesamiento
            if not optimizador_analisis.validar_imagen_rapida(self.imagen_path):
                self._mostrar_error_usuario("Error de Imagen", 
                                           "La imagen seleccionada no es válida o está corrupta.")
                return None

            # Pre-cargar dependencias si es necesario
            optimizador_analisis.precargar_dependencias()
            
            # Ejecutar análisis optimizado (sin caché innecesario)
            #print(f"📸 Procesando imagen diaria: {self.imagen_path}")
            resultado = self._ejecutar_analisis_optimizado(umbral, distancia)

            if resultado:
                self.mostrar_texto(resultado)
                self._asegurar_toolbar_visible()
                self.btn_add.setEnabled(True)
                return resultado
            
        except Exception as e:
            #logger.error(f"Error en análisis de imagen: {e}")
            self._mostrar_error_usuario("Error de Análisis", 
                                    f"No se pudo analizar la imagen: {str(e)}")
        return None
    
    def _crear_interfaz_parametros(self):
        """Crea la interfaz de parámetros de forma lazy"""
        self.parametros_layout = self._crear_parametros()
        self.layout_imagen.addLayout(self.parametros_layout)

        self.boton_ayuda = QPushButton("?")
        self.boton_ayuda.setToolTip("Presione para ver ayuda sobre los parámetros.") 
        self.setStyleSheet("""
            QToolTip {
                background-color: rgba(177, 241, 251, 0.64);
                color: black;
                border: 1px solid white;
                font-size: 14px;
            }
        """)
        self.boton_ayuda.clicked.connect(self.mostrar_ayuda_parametros)
        self.botones_layout.addWidget(self.boton_ayuda)
    
    def _ejecutar_analisis_optimizado(self, umbral: float, distancia: int) -> Optional[str]:
        """Ejecuta análisis optimizado"""
        try:

            # Ejecutar análisis con imagen optimizada si está disponible
            return analizar_lineas(
                imagen_path=self.imagen_path,
                metodo=True,
                fila_especifica=None,
                umbral_relativo=umbral,
                distancia_minima=distancia,
                mostrar=True,
                filtro="clahe",
                canvas=self.canvas
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error ejecutando análisis: {e}")
            return None
    
    def _asegurar_toolbar_visible(self):
        """Asegura que la toolbar esté visible, reutilizando recursos"""
        if not hasattr(self, 'toolbar') or self.toolbar is None:
            mpl = get_matplotlib_components()
            NavigationToolbar = mpl['NavigationToolbar']
            self.toolbar = NavigationToolbar(self.canvas, self)
            self.col2.addWidget(self.toolbar)
        elif self.col2.indexOf(self.toolbar) == -1:
            self.col2.addWidget(self.toolbar)
    
    def analizar_imagen_con_debouncing(self):
        """Análisis con debouncing para ajustes de parámetros en la misma imagen"""
        if not hasattr(self, 'imagen_path') or not self.imagen_path:
            return
        
        # Cancelar análisis anterior si está en progreso
        if hasattr(self, '_timer_analisis'):
            self._timer_analisis.stop()
        
        # Timer para evitar análisis excesivos al cambiar parámetros
        self._timer_analisis.start(500)  # 500ms de delay
    
    def _ejecutar_analisis_diferido(self):
        """Ejecuta el análisis después del debouncing"""
        resultado = self.analizar_imagen()
        return resultado

    def mostrar_texto(self, texto_lines):
        # Elimina todo menos canvas y toolbar
        toolbar = getattr(self, 'toolbar', None)
        for i in reversed(range(self.col2.count())):
            item = self.col2.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            # Solo elimina widgets temporales (como QLabel de resultados)
            if widget is not None and widget not in (self.canvas, toolbar):
                self.col2.removeWidget(widget)
                widget.deleteLater()

        # Crear QLabel del texto
        if isinstance(texto_lines, list):
            texto = (
                "<pre style='font-family: Segoe UI, monospace; font-size: 18px; font-weight: normal;'>"
                + "\n".join(str(linea) for linea in texto_lines) +
                "</pre>"
            )
        else:
            texto = texto_lines  # Asume que ya viene en HTML
        label = QLabel()
        label.setTextFormat(Qt.RichText)
        label.setText(texto)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        label.setWordWrap(True)
        label.setMinimumHeight(80)
        self.resultado_label = label

        # Crear toolbar si no existe
        if not hasattr(self, 'toolbar') or self.toolbar is None:
            mpl = get_matplotlib_components()
            NavigationToolbar = mpl['NavigationToolbar']
            self.toolbar = NavigationToolbar(self.canvas, self)
            for action in self.toolbar.actions():
                if action.text() in ['Customize', 'Subplots']:
                    self.toolbar.removeAction(action)
            self.toolbar.setFixedHeight(25)
            self.toolbar.setStyleSheet("padding: 0px; margin: 0px;")

        for widget in (self.toolbar, label, self.canvas):
            if widget is not None and self.col2.indexOf(widget) == -1:
                self.col2.addWidget(widget)

        # Asegurar visibilidad
        self.toolbar.show()
        self.toolbar.update()
        self.canvas.setVisible(True)
        self.canvas.show()
        self.canvas.update()
        self.widgetgrafica.update()
        #self.wf2.setSizes([1, 0])
    
    def guardar_datos(self):
        """
        Extrae los resultados del análisis de imagen desde el texto mostrado en self.resultado.
        Devuelve: distancias (str), promedio (float), desviacion (float),
                desplazamientos (str), promedio_des (float), desviacion_des (float)
        """
        if not hasattr(self, "resultado_label") or self.resultado_label is None:
            return "", None, None, "", None, None

        resultado_html = self.resultado_label.text().strip()
        
        if not resultado_html:
            return "", None, None, "", None, None
        #print("Entra a la función guardar_datos (solo extracción) en braquiterapia.py")
        if hasattr(self, "resultado_label") and self.resultado_label is not None:
            resultado_html = self.resultado_label.text().strip()
            if not resultado_html:
                print(" NO HAY resultado_html EN LA FUNCIÓN guardar_datos ")
                QMessageBox.warning(self, "Advertencia", "No hay resultado para guardar.")
                return None, None, None, None, None, None

        # Limpiar HTML
        resultado = re.sub(r'<[^>]+>', '', resultado_html)  # Quita etiquetas <b>, <br>, etc.
        resultado = html.unescape(resultado)                # Convierte &aacute; → á, etc.

        # Inicializar variables
        distancias = ""
        promedio = None
        desviacion = None
        desplazamientos = ""
        promedio_des = None
        desviacion_des = None

        try:
            # Extraer distancias como texto plano
            match_dist = re.search(r'Distancias entre líneas\s*\(mm\)\s*:\s*\[([^\]]+)\]', resultado)
            if match_dist:
                distancias = "[" + match_dist.group(1).strip() + "]"

            # Extraer desplazamientos como texto plano
            match_despl = re.search(r'Desplazamientos entre líneas y centros circulares\s*\(mm\)\s*:\s*\[([^\]]+)\]', resultado)
            if match_despl:
                desplazamientos = "[" + match_despl.group(1).strip() + "]"

            # Buscar promedios (ambos bloques)
            promedios = re.findall(r'Promedio(?: desplazamiento)?\s*=\s*([\d.]+)\s*mm', resultado)
            if len(promedios) >= 1:
                promedio = float(promedios[0])
            if len(promedios) >= 2:
                promedio_des = float(promedios[1])

            # Buscar desviaciones estándar (ambos bloques)
            desvs = re.findall(r'Desviación estándar(?: desplazamiento)?\s*=\s*([\d.]+)\s*mm', resultado)
            if len(desvs) >= 1:
                desviacion = float(desvs[0])
            if len(desvs) >= 2:
                desviacion_des = float(desvs[1])

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"No se pudieron extraer los datos.\nError: {e}")
            return None, None, None, None, None, None

        #print("Resultados extraídos:", distancias, promedio, desviacion, desplazamientos, promedio_des, desviacion_des)
        return distancias, promedio, desviacion, desplazamientos, promedio_des, desviacion_des

    def verificar_columna_pelicula(self, item):
        col_pelicula = self.table.columnCount() - 1
        if item.column() == col_pelicula and item.text() == "Imagen cargada":
            id_registro = item.data(Qt.UserRole)
            abrir_pelicula(self, id_registro)

    """ Carga y muestra los resultados guardados en la base de datos SQLite en una tabla en col2                                                                                                """
    def cargar_y_mostrar_resultados(self):
        # Quitar el canvas si está en el layout
        if self.canvas is not None and self.col2.indexOf(self.canvas) != -1:
            self.col2.removeWidget(self.canvas)
            self.canvas.setParent(None)
        # Quitar la toolbar si está
        if hasattr(self, 'toolbar') and self.toolbar is not None and self.col2.indexOf(self.toolbar) != -1:
            self.col2.removeWidget(self.toolbar)
            self.toolbar.setParent(None)
        # Agregar la tabla si no está
        if self.col2.indexOf(self.resultados_table) == -1:
            self.col2.addWidget(self.resultados_table)

        # Llenar la tabla
        conexion = sqlite3.connect("resultados.db")
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM resultados")
        resultados = cursor.fetchall()
        conexion.close()

        self.resultados_table.setRowCount(len(resultados))

        for row_idx, fila in enumerate(resultados):
            user = str(fila[0])
            fecha = fila[1]
            tipo = fila[2]
            distancias = fila[3].replace("\\n", " ").replace("\n", " ")
            promedio = str(fila[4]) if fila[4] is not None else ""
            desviacion = str(fila[5]) if fila[5] is not None else ""
            imagen_path = fila[6] if len(fila) > 6 else ""

            self.resultados_table.setItem(row_idx, 0, QTableWidgetItem(user))
            self.resultados_table.setItem(row_idx, 1, QTableWidgetItem(fecha))
            self.resultados_table.setItem(row_idx, 2, QTableWidgetItem(tipo))
            self.resultados_table.setItem(row_idx, 3, QTableWidgetItem(distancias))
            self.resultados_table.setItem(row_idx, 4, QTableWidgetItem(promedio))
            self.resultados_table.setItem(row_idx, 5, QTableWidgetItem(desviacion))
            self.resultados_table.setItem(row_idx, 6, QTableWidgetItem(imagen_path))
        self.resultados_table.resizeColumnsToContents()

        if self.col2.indexOf(self.boton_volver) == -1:
            self.col2.addWidget(self.boton_volver)
        if self.col2.indexOf(self.boton_eliminar) == -1:
            self.col2.addWidget(self.boton_eliminar)

    """ Elimina una fila seleccionada de la tabla de resultados                                                                                                                                 """
    def eliminar_fila_resultado(self):
        fila_seleccionada = self.resultados_table.currentRow()
        if fila_seleccionada == -1:
            QMessageBox.warning(self, "Advertencia", "Selecciona una fila para eliminar.")
            return

        id_item = self.resultados_table.item(fila_seleccionada, 0)
        if not id_item:
            QMessageBox.warning(self, "Advertencia", "No se pudo obtener el ID de la fila.")
            return

        id_fila = id_item.text()
        respuesta = QMessageBox.question(self, "Confirmar", f"¿Seguro que deseas eliminar la fila con ID {id_fila}?",
                                        QMessageBox.Yes | QMessageBox.No)
        if respuesta == QMessageBox.Yes:
            conexion = sqlite3.connect("resultados.db")
            cursor = conexion.cursor()
            cursor.execute("DELETE FROM resultados WHERE id = ?", (id_fila,))
            conexion.commit()
            conexion.close()
            self.cargar_y_mostrar_resultados()  # Refresca la tabla

    """ Muestra el canvas de matplotlib y la toolbar si están disponibles, y quita la tabla de resultados si está presente                                                                      """
    def mostrar_canvas(self):
        # Quitar la tabla si está
        if self.col2.indexOf(self.resultados_table) != -1:
            self.col2.removeWidget(self.resultados_table)
            self.resultados_table.setParent(None)
        # Agregar el canvas si no está
        if self.col2.indexOf(self.canvas) == -1:
            self.col2.addWidget(self.canvas)
        # Agregar la toolbar si la usas
        if hasattr(self, 'toolbar') and self.toolbar is not None and self.col2.indexOf(self.toolbar) == -1:
            self.col2.addWidget(self.toolbar)
        if self.col2.indexOf(self.boton_eliminar) != -1:
            self.col2.removeWidget(self.boton_eliminar)
            self.boton_eliminar.setParent(None)

        if self.col2.indexOf(self.boton_volver) != -1:
            self.col2.removeWidget(self.boton_volver)
            self.boton_eliminar.setParent(None)

    """ Muestra un mensaje de ayuda sobre los parámetros de análisis                                                                                                                             """
    def mostrar_ayuda_parametros(self):
        texto = (
        "<b>Umbral Relativo:</b> Ajusta la sensibilidad del análisis. "
        "Un valor más alto detecta menos picos, "
        "así si la imagen es muy <span style='color:#1976d2;'>oscura</span>.<br>"
        "<span style='color:#1976d2;'>Disminuya el umbral</span> para detectar más picos.<br><br>"
        "<b>Distancia mínima entre picos:</b> Define la separación mínima entre picos detectados.<br>"
        "Si detecta <span style='color:#1976d2;'>demasiados picos</span>, "
        "<span style='color:#1976d2;'>aumente este valor</span> para filtrar los más cercanos."
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()

    """ Genera el espacio para graficar, incluyendo el canvas y los menús desplegables                                                                                                            """
    def plotter(self, menu):
    
        #Se limpia el espacio paa graficar y se configura
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        #Se abre la base de datos y se encuentra que se va a graficar
        db = self.opeenDatabase()
        selected_chart = menu.currentText()  # QComboBox con tipos de gráfica
        
        if selected_chart == "Seleccione...": #No se si sea necesario pero es para no tneer errores
            return
        
        #Se establecen los limites de l grafica 
        start_date = self.limit1.date().toString('yyyy-MM-dd')
        end_date = self.limit2.date().toString('yyyy-MM-dd')
        
        query = QSqlQuery(db)
        
        selected_column1 = self.graficos_mapeo1.get(selected_chart, None)
        selected_column2 = self.graficos_mapeo2.get(selected_chart, None)

        if selected_column2 in [
            'tol_rep_act_ci',
            'tol_exp_act',
            'tol_cyc_dummy',
            'tol_cyc_rad'
        ]:
            #print("Entro a datos dosimetricos vs tiempo")
            graficarvstiempo(self, query, ax, 'braqui', selected_column2, selected_chart, start_date, end_date)

        elif selected_chart == "Actividad vs tiempo":
            #print("Entro a datos dosimetricos vs tiempo")
            
            query.prepare("""
                SELECT date, tol_rep_act_ci, tol_exp_act
                FROM braqui
                WHERE date BETWEEN :start_date AND :end_date
                ORDER BY date ASC
            """)
            query.bindValue(":start_date", start_date)
            query.bindValue(":end_date", end_date)
            query.exec()

            x_data = []
            y_data1 = []
            y_data2 = []


            while query.next():
                val = query.value(1)
                if val is None or val == '':
                    continue
                x_data.append(query.value(0))  # la fecha
                y_data1.append(float(query.value(1)))  # tol_fot_6mv
                y_data2.append(float(query.value(2)))  # tol_fot_15mv
            
            date = [datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in x_data]

            ax.plot(date, y_data1, marker='o', label='actividad reportada')
            ax.plot(date, y_data2, marker='o', label='actividad esperada')

            self.figure.autofmt_xdate()  # Rotar las fechas para mejor visualización
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Dosis')
            ax.set_title('Actividad reportada vs actividad esperada')
            ax.grid(True)
            ax.legend()
        
        
        elif selected_chart == "Ciclos vs tiempo":
            #print("Entro a datos dosimetricos vs tiempo")
            
            query.prepare("""
                SELECT date, 
                tol_cyc_dummy,tol_cyc_rad
                FROM braqui
                WHERE date BETWEEN :start_date AND :end_date
                ORDER BY date ASC
            """)
            query.bindValue(":start_date", start_date)
            query.bindValue(":end_date", end_date)
            query.exec()

            x_data = []
            y_data1 = []
            y_data2 = []


            while query.next():
                val = query.value(1)
                if val is None or val == '':
                    continue
                x_data.append(query.value(0))  # la fecha
                y_data1.append(float(query.value(1)))  # tol_fot_6mv
                y_data2.append(float(query.value(2)))  # tol_fot_15mv
            
            date = [datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in x_data]

            ax.plot(date, y_data1, marker='o', label='Ciclos del dummy')
            ax.plot(date, y_data2, marker='o', label='Ciclos de la fuente')

            self.figure.autofmt_xdate()  # Rotar las fechas para mejor visualización
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Dosis')
            ax.set_title('Ciclos del dummy vs ciclos de la fuente')
            ax.grid(True)
            ax.legend()        

        elif selected_column1 in [
            'int_con_box', 'emerg_con', 'blq_puerta',
            'pos_fuente', 'res_fuente', 'key_fuente',
            'mon_area', 'lum_puerta', 'tub_guia',
            'visual_sys', 'intercom', 'mon_rad_port'
        ]:
            
            graficarvstiempo(self, query, ax, 'braqui', selected_column1, selected_chart, start_date, end_date, True)
        
        # Redibuja en el canvas
        self.canvas.draw()

        db.close()
    
    def cleanup_recursos(self):
        """Limpia recursos para liberar memoria"""
        #logger.info("Limpiando recursos de PruebaDiariaBraq")
        try:
            # Limpiar widgets lazy
            for nombre, widget in self._widgets_lazy.items():
                if widget and hasattr(widget, 'deleteLater'):
                    widget.deleteLater()
            self._widgets_lazy.clear()
            
            # Limpiar canvas y figuras
            if hasattr(self, 'canvas') and self.canvas:
                try:
                    self.canvas.figure.clear()
                except:
                    pass
            
            # Limpiar toolbar
            if hasattr(self, 'toolbar') and self.toolbar:
                try:
                    self.toolbar.deleteLater()
                    self.toolbar = None
                except:
                    pass
                    
            #print("Recursos limpiados exitosamente")
        except Exception as e:
            print(f"Error limpiando recursos: {e}")
    
    def _mostrar_error_usuario(self, titulo: str, mensaje: str):
        """Muestra errores al usuario de forma consistente"""
        #print(f"{titulo}: {mensaje}")
        try:
            QMessageBox.warning(self, titulo, mensaje)
        except Exception as e:
            print(f"Error mostrando mensaje al usuario: {e}")
    
    def _ejecutar_busqueda_filtrada(self):
        """Ejecuta búsqueda filtrada después del debouncing"""
        try:
            if hasattr(self, 'search_bar') and hasattr(self, 'filtrarTabla'):
                texto_busqueda = self.search_bar.text()
                print(f"Ejecutando búsqueda filtrada: {texto_busqueda}")
                self.filtrarTabla()
        except Exception as e:
            print(f"Error en búsqueda filtrada: {e}")
    
    def _iniciar_busqueda_debounced(self):
        """Inicia búsqueda con debouncing para evitar búsquedas excesivas"""
        self._timer_busqueda.stop()
        self._timer_busqueda.start(300)  # 300ms de delay
    
    def __del__(self):
        """Destructor para limpieza automática"""
        try:
            self.cleanup_recursos()
        except:
            pass
    
    def abrir_imagen_resultado(self, item):
        """Abre la imagen cuando se hace doble clic en la columna de imagen"""
        import os
        from pathlib import Path
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        
        # Verificar si es la columna de imagen (columna 6)
        if item.column() != 6:
            return
        
        imagen_path = item.text()
        if not imagen_path or imagen_path == "":
            QMessageBox.warning(self, "Advertencia", "No hay imagen asociada a este resultado.")
            return
        
        # Verificar si el archivo existe
        if not os.path.exists(imagen_path):
            QMessageBox.warning(self, "Error", f"La imagen no se encontró en:\n{imagen_path}")
            return
        
        try:
            # Crear dialog para mostrar la imagen
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Imagen - {os.path.basename(imagen_path)}")
            dialog.resize(800, 600)
            
            # Aplicar estilo si existe
            try:
                import sys
                if getattr(sys, 'frozen', False):
                    base_path = Path(sys._MEIPASS)
                else:
                    base_path = Path(__file__).parent.parent.parent
                qss_file = base_path / "resources" / "estilo.qss"
                if qss_file.exists():
                    dialog.setStyleSheet(qss_file.read_text(encoding="utf-8"))
            except Exception:
                pass  # Si no se puede cargar el estilo, continuar sin él
            
            layout = QVBoxLayout(dialog)
            
            # Crear scroll area para la imagen
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            
            # Cargar y mostrar imagen
            label_imagen = QLabel()
            pixmap = QPixmap(imagen_path)
            
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", "No se pudo cargar la imagen.")
                return
            
            # Escalar imagen si es muy grande
            if pixmap.width() > 1200 or pixmap.height() > 800:
                pixmap = pixmap.scaled(1200, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            label_imagen.setPixmap(pixmap)
            label_imagen.setAlignment(Qt.AlignCenter)
            scroll_area.setWidget(label_imagen)
            
            layout.addWidget(scroll_area)
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir la imagen:\n{str(e)}")

# -------------------------------------------------------- Cambio de Fuente --------------------------------------------------------- #
class CalRedundanteFuente(PruebaMensualBraq):
    """
    Clase para gestionar el cambio de fuente en braquiterapia.
    Incluye mejoras de conexión a BD y manejo de errores.
    """
    def __init__(self, user_id):
        #print("CambioFuente           __init__ called")
        self.es_calibracion_redundante = True
        super().__init__(user_id)
        #self.date_box.date
        self.button_click()
        

    def cargar_datos_ultima_calibracion(self) -> bool:
        """
        Carga datos de la última calibración con manejo mejorado de errores
        y uso del gestor de conexiones optimizado.
        
        Returns:
            bool: True si la carga fue exitosa, False en caso contrario
        """
        try:
            with gestor_db.obtener_conexion() as conn:
                return self._ejecutar_carga_calibracion(conn)
                
        except Exception as e:
            #logger.error(f"Error cargando datos de calibración: {e}")
            self._mostrar_error_usuario("Error de Carga", 
                                        f"No se pudieron cargar los datos de calibración: {str(e)}")
            return False
    
    def _ejecutar_carga_calibracion(self, conn) -> bool:
        """Ejecuta la lógica de carga de calibración con conexión establecida"""
        try:
            conn = Conexion().conectar() 
            if conn is None:
                print("No se pudo conectar a la base de datos.")
                return

            cursor = conn.cursor()

            # 1. Buscar última fecha con tipo = "Cambio de fuente"
            cursor.execute('''
                SELECT fecha FROM TipoCalibracion
                WHERE tipo = "Cambio de fuente"
                ORDER BY fecha DESC LIMIT 1
            ''')
            fila_fecha = cursor.fetchone()
            if not fila_fecha:
                print("No se encontró calibración previa.")
                return

            fecha = fila_fecha[0]

            # 2. Obtener datos de TipoCalibracion
            cursor.execute('SELECT serie, certificado, fecha_cer, intensidad, conversion FROM TipoCalibracion WHERE fecha = ?', (fecha,))
            tipo_data = cursor.fetchone()
            if tipo_data:
                self.serie.setText(tipo_data[0])
                self.certificado.setText(tipo_data[1])

                fecha_dt = QDate.fromString(tipo_data[2], "yyyy-MM-dd HH:mm:ss")
                if fecha_dt.isValid():
                    self.fecha_cer.setDate(fecha_dt)

                self.intensidad.setText(str(tipo_data[3]))
                self.conversion.setText(str(tipo_data[4]))

            # 3. SistemaMedicion
            cursor.execute('''
                SELECT modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0
                FROM SistemaMedicion WHERE fecha = ?
            ''', (fecha,))
            sis_data = cursor.fetchone()
            if sis_data:
                self.modelo.setCurrentText(sis_data[0])
                self.serie_cp.setCurrentText(sis_data[1])
                self.calibracion.setText(str(sis_data[2]))
                self.modelo_elec.setCurrentText(sis_data[3])
                self.serie_ele.setCurrentText(sis_data[4])
                self.electrometro.setText(str(sis_data[5]))
                self.t0.setText(str(sis_data[6]))
                self.p0.setText(str(sis_data[7]))
                self.h0.setText(str(sis_data[8]))

            # 4. CondicionesMedicion
            cursor.execute('SELECT t, p, h FROM CondicionesMedicion WHERE fecha = ?', (fecha,))
            cond_data = cursor.fetchone()

            cursor.execute('SELECT actividad_monitor FROM ResultadosActividad WHERE fecha = ?', (fecha,))
            actividad_data = cursor.fetchone()

            if cond_data and actividad_data:
                self.t.setText(str(cond_data[0]))
                self.p.setText(str(cond_data[1]))
                self.h.setText(str(cond_data[2]))
                self.ref.setText(str(actividad_data[0]))


            # 5. MaximosCamaras
            cursor.execute('SELECT posicion, medida1, medida2 FROM MaximosCamaras WHERE fecha = ?', (fecha,))
            filas_maximos = cursor.fetchall()
            ncam = len(filas_maximos)
            self.generar_tabla_medidas()

            for i, (pos, m1, m2) in enumerate(filas_maximos):
                self.campos_maximos[i][0].setText(str(pos))
                self.campos_maximos[i][1].setText(str(m1))
                self.campos_maximos[i][2].setText(str(m2))

            # 6. Obtener lecturas de voltaje asociadas a tipo = "Cambio de fuente"
            cursor.execute('''
                SELECT fecha FROM TipoCalibracion
                WHERE tipo = "Cambio de fuente"
                ORDER BY fecha DESC
                LIMIT 1
            ''')
            fila_fecha_cf = cursor.fetchone()

            if not fila_fecha_cf:
                print("No se encontró una fecha con tipo = 'Cambio de fuente'.")
                return

            fecha_cambio_fuente = fila_fecha_cf[0]

            # Obtener TODAS las lecturas asociadas a esa fecha
            cursor.execute('''
                SELECT voltaje, V_300, V_150, Vn_300
                FROM LecturasMaximos
                WHERE fecha = ?
            ''', (fecha_cambio_fuente,))
            filas_lecturas = cursor.fetchall()

            if not filas_lecturas:
                print(f"No se encontraron lecturas para la fecha '{fecha_cambio_fuente}'.")
                return

            # Ajustar tabla de lecturas visual si es necesario
            num_lecturas = len(filas_lecturas)

            # Si no hay suficientes campos visuales, los generas
            if len(self.campos_lecturas) < num_lecturas:
                self.generar_tabla_lecturas(num_lecturas)

            # Llenar los datos dinámicamente
            for i, fila in enumerate(filas_lecturas):
                voltaje, v1, v2, v3 = fila
                self.campos_lecturas[i][0].setText(str(voltaje))  # ← ahora correcto
                self.campos_lecturas[i][1].setText(str(v1))
                self.campos_lecturas[i][2].setText(str(v2))
                self.campos_lecturas[i][3].setText(str(v3))

        except Exception as e:
            traceback.print_exc()
            print("Error al cargar calibración previa:", e)

        finally:
            if conn:
                conn.close()
        
        

" Verificación de la Linealidad"
class Linealidad(PruebaBasico):
    """
    Verificación de la Linealidad con mejoras de rendimiento y gestión de errores.
    Incluye debouncing para cálculos automáticos y lazy loading.
    """
    def __init__(self, user_id):
        super(Linealidad, self).__init__()
        print("Linealidad             __init__ called")
        self.linealidad = True
        otro = "Linealidad Braquiterapia"
        braqui = True
        self.user_id = user_id
        # Inicializar componentes principales
        self.tabla_resultados = QTableWidget()
        #self.tabla_resultados.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Timers para debouncing
        self._timer_calculo = QTimer()
        self._timer_calculo.setSingleShot(True)
        self._timer_calculo.timeout.connect(self._calcular_corriente_estacionaria)
        
        # Timer para búsqueda
        self._timer_busqueda = QTimer()
        self._timer_busqueda.setSingleShot(True)
        self._timer_busqueda.timeout.connect(self._ejecutar_busqueda_filtrada)
        
        # Cache para cálculos
        self._cache_calculos = {}
        
        try:
            self.initDATA(user_id)
            self.initUI()
           
            
            self._configurar_campos_readonly()
            self._configurar_calculos_automaticos()
            #self._cargar_datos_iniciales()
            
            
            
            
            
            # Cargar datos de forma diferida
            QTimer.singleShot(100, self._cargar_datos_diferidos)
            self.button_click()
            
            
        except Exception as e:
            #logger.error(f"Error inicializando Linealidad: {e}")
            self._mostrar_error_usuario("Error de Inicialización", str(e))
    
    def _cargar_datos_diferidos(self):
        """Carga datos pesados de forma diferida"""
        try:
            mostrar_db_linealidad(self)
            self.cargar_nombres_tablas()
            self.generar_tabla_medidas()
           
            self.repro_med1 = getattr(self, 'repro_med1')
            self.repro_med2 = getattr(self, 'repro_med2')
            self.repro_med3 = getattr(self, 'repro_med3')
            self.repro_med4 = getattr(self, 'repro_med4')
            self.repro_med5 = getattr(self, 'repro_med5')
            self.repro_prom = getattr(self, 'repro_prom')
        except Exception as e:
            print(f"Error en carga diferida: {e}")
    
    def _configurar_campos_readonly(self):
        """Configura campos de solo lectura"""
        self.exactitud.setReadOnly(True)
        self.repro.setReadOnly(True)
        self.tiempo_transito.setReadOnly(True)
    
    def _configurar_calculos_automaticos(self):
        """Configura cálculos automáticos con debouncing"""
        self.q_est.textChanged.connect(self._iniciar_calculo_debounced)
        self.t_integrado.textChanged.connect(self._iniciar_calculo_debounced)
    
    def _iniciar_calculo_debounced(self):
        """Inicia cálculo con debouncing para evitar cálculos excesivos"""
        self._timer_calculo.stop()
        self._timer_calculo.start(300)  # 300ms de delay
    
    def _calcular_corriente_estacionaria(self):
        """Calcula la corriente estacionaria con manejo de errores"""
        try:
            q_text = self.q_est.text().strip()
            t_text = self.t_integrado.text().strip()
            
            if not q_text or not t_text:
                self.i_est.setText("")
                return
                
            q_val = float(q_text)
            t_val = float(t_text)
            
            if t_val == 0:
                self.i_est.setText("∞")
                return
                
            resultado = q_val / t_val
            self.i_est.setText(f"{resultado:.2f}")
            
        except ValueError as e:
            #logger.warning(f"Error en cálculo de corriente: {e}")
            self.i_est.setText("Error")
        except Exception as e:
            #logger.error(f"Error inesperado en cálculo: {e}")
            self.i_est.setText("")

        self.botones_layout = QHBoxLayout()
        
        self.col2.addLayout(self.botones_layout)
        
            
    def _mapear_repro_widgets(self):
        self.repro_fields = {
            k: getattr(self, k)
            for k in [
                'repro_med1','repro_med2','repro_med3',
                'repro_med4','repro_med5','repro_prom'
            ]
        }
    def _configurar_promedio_repro(self):
        def actualizar():
            try:
                vals = [float(self.repro_fields[k].text())
                        for k in self.repro_fields if k != 'repro_prom']
                self.repro_fields['repro_prom'].setText(f"{np.mean(vals):.2f}")
            except ValueError:
                self.repro_fields['repro_prom'].setText("")

        for k in self.repro_fields:
            if k != 'repro_prom':
                self.repro_fields[k].textChanged.connect(actualizar)  
    def cargar_nombres_tablas(self):
        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        
    
    def initDATA(self, user_id):
    
        self.diccionario_invertido = {
            'modelo' : ['Modeo de la cámara', '', 'line'],
            'serie_cp': ['Serie de la cámra de Pozo', '', 'line'],
            'calibracion' : ['Factor de calibración de la cámara de pozo', '', 'line'],
            'modelo_elec' : ['Modelo del electrómetro', '', 'line'],
            'serie_ele' : ['Serie del electrómetro', '', 'line'],
            'electrometro' : ['Factor de calibración del electrómetro', '', 'line'],
            'repro_med1' : ['Medicion 1', '', 'line'],
            'repro_med2' : ['Medicion 2', '', 'line'],
            'repro_med3' : ['Medicion 3', '', 'line'],
            'repro_med4' : ['Medicion 4', '', 'line'],
            'repro_med5' : ['Medicion 5', '', 'line'],
            'repro_prom' : ['promedio', '', 'line'],
            'q_est' : ['Carga Estacionaria (nC)', '', 'line'],
            't_integrado' : ['Tiempo integrado (s)', '', 'line'],
            'i_est' : ['Corriente Estacionaria (nA)', '', 'line'],
            'exactitud' : ['Exactitud en Linealidad', '', 'line'],
            'repro' : ['Reproducibilidad (%)', '', 'line'],
            'tiempo_transito' : ['Tiempo de Transito', '', 'line']
        }
        
        self.init_data(user_id, self.diccionario_invertido)
        print(hasattr(self, 'repro_med1'))
        for k in self.diccionario_invertido:
            print(k, hasattr(self, k))
       
        

    def initUI(self):
        self.layout_cambio = QHBoxLayout()

        archivo = 'widgets.xlsx'
        _ = self.setupBox(archivo, 'encabezado_LinealidadBraqui')
        self.date_box.setDisplayFormat("yyyy/MM/dd")
        df, n, layouts, _ = self.setupBox(archivo, 'preguntas_LinealidadBraqui', main=False)
        
        self.datos_tabla = self.storeDailyTests(df)
        
        self._mapear_repro_widgets()
        self._configurar_promedio_repro()

        self.comboBox_equipos()
        self._mapear_repro_widgets()
        self._configurar_promedio_repro()
       

        for k, w in self.widgets.items():
            setattr(self, k, w)

        self.category1 = QWidget()
        self.category2 = QWidget()
        self.category3 = QWidget()
        self.category4 = QWidget()
        self.category5 = QWidget()

        toolbox = QToolBox()
        
        self.general_layout.addWidget(toolbox)

        for i, layout in enumerate(layouts, 1):
            getattr(self, f'category{i}').setLayout(layout)

        if self.category5.layout() is None:
            self.layout_medicion_linealidad = QVBoxLayout()
            self.category5.setLayout(self.layout_medicion_linealidad)
        else:
            self.layout_medicion_linealidad = self.category5.layout()

        toolbox.addItem(self.category1, 'SISTEMA DE MEDICIÓN')
        toolbox.addItem(self.category2, 'CARGA COLECTADA EN 60s')
        toolbox.addItem(self.category3, 'LINEALIDAD')
        
        toolbox.addItem(self.category5, "MEDICIÓN")
        toolbox.addItem(self.category4, "RESULTADOS")

        _ = self.setupBox(archivo, 'btn')
        #self.btn_add.setObjectName("boton_nofunciona")
        self.btn_add.setEnabled(True)
        self.btn_add.setProperty("estado", "noselected")
        self.btn_add.clicked.connect(self.guardar_linealidad)
        print(self.date_box.date().toString('yyyy-MM-dd'))
        self.btn_submit.clicked.connect(
            lambda _, maquina=self.mach_name2.text(), id_maquina=self.code_1.text(): 
                mostrar_db_linealidad(self))

        # ------------------------------ GRÁFICOS Y TABLA EDITABLE -------------------------------------------------
        # Crear gráficos específicos para mensual manualmente (sin usar init_ui)
        menu_graficas = ["Seleccionar...", "Máximos de la cámara", "Linealidad de la fuente"]
        
        # Crear canvas y menús manualmente
        mpl = get_matplotlib_components()
        Figure = mpl['Figure']
        FigureCanvas = mpl['FigureCanvas']

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        
        # Crear menú principal
        self.menu_graficar = QComboBox()
        self.menu_graficar.addItems(menu_graficas)
        
        # Crear layout para menús
        caja_menu_graficas = QHBoxLayout()
        
        caja_menu_graficas.addWidget(QLabel("Fecha:"))
        self.date_grafica = QDateEdit()
        self.date_grafica.setCalendarPopup(True)
        self.date_grafica.setDate(QDate.currentDate())
        caja_menu_graficas.addWidget(self.date_grafica)

        caja_menu_graficas.addWidget(QLabel("Gráfico:"))
        caja_menu_graficas.addWidget(self.menu_graficar)

        
        self.settfigure = QHBoxLayout()
        self.settfigure.addLayout(caja_menu_graficas)

        # COLUMNA DERECHA - gráfica (Arriba)
        self.col2 = QVBoxLayout()
        self.col2.addLayout(self.settfigure)
        self.col2.addWidget(self.canvas)
        
        # COLUMNA DERECHA - tabla editable 
        self.edit_table_tools = self.createTable(df=df, headers=None)
        self.col2_1 = QVBoxLayout()
        self.col2_1.addWidget(self.table)
        self.col2_1.addLayout(self.edit_table_tools)

        # Panel vertical con ambas columnas
        self.wf2 = QSplitter(Qt.Orientation.Vertical)

        self.widgetgrafica = QWidget()
        self.widgetgrafica.setLayout(self.col2)

        self.widgettabla = QWidget()
        self.widgettabla.setLayout(self.col2_1)

        self.wf2.addWidget(self.widgetgrafica)
        self.wf2.addWidget(self.widgettabla)

        # Layout principal dividido
        self.wf = QWidget()
        self.wf.setLayout(self.general_layout)

        self.splitter_principal = QSplitter(Qt.Orientation.Horizontal)
        self.splitter_principal.addWidget(self.wf)
        self.splitter_principal.addWidget(self.wf2)

        # Final layout
        self.main_layout = QHBoxLayout()
        self.main_layout.addWidget(self.splitter_principal)
        self.setLayout(self.main_layout)

        self.actividad = QLabel("Verificación de la actividad de la fuente radioactiva")
        self.actividad.setWordWrap(True)
        self.actividad.setStyleSheet("color: #333; font-size: 14px;")

        self.setupButtonConnections(df, maquina='braqui')
        if hasattr(self, 'date_box'):
            self.date_box.dateChanged.connect(self.cargar_dailytest_desde_db)
            
        
    def cargar_dailytest_desde_db(self, fecha=None):
        """
        Carga datos de pruebas diarias desde la base de datos y los mapea a los widgets de la GUI.
        
        Args:
            fecha: QDate object o None. Si es None, usa la fecha del date_box.
        """
        if fecha is None:
            fecha = self.date_box.date()
        
        # Convertir QDate a string en formato compatible con la BD
        fecha_str = fecha.toString("yyyy-MM-dd")
        
        db = self.opeenDatabase()
        if not db:
            return
        
        try:
            query = QSqlQuery(db)
            print("consultando db en linealidad")
            # Preparar la consulta
            query.prepare("""
                SELECT * FROM LinealidadBraquiterapia 
                WHERE DATE(fecha) = ? 
                LIMIT 1
            """)
            query.addBindValue((fecha_str))
            #query.addBindValue(str(self.user_id))
            print(fecha_str)
            
            if not query.exec():
                print(f"Error en consulta: {query.lastError().text()}")
                db.close()
                return
            
            if query.next():
                record = query.record()

                def get(col):
                    return query.value(record.indexOf(col))

                # QComboBox
                def set_combo(widget_name, col):
                    val = get(col)
                    w = getattr(self, widget_name, None)
                    if w and val is not None:
                        idx = w.findText(str(val))
                        if idx >= 0:
                            w.setCurrentIndex(idx)

                set_combo('combo_modelo',      'modelo')
                set_combo('combo_serie',       'serie_cp')
                set_combo('combo_modelo_elec', 'modelo_elec')
                set_combo('combo_serie_elec',  'serie_ele')

                # QLineEdit
                mapeo = {
                    'repro_m1':        'repro_med1',
                    'repro_m2':        'repro_med2',
                    'repro_m3':        'repro_med3',
                    'repro_m4':        'repro_med4',
                    'repro_m5':        'repro_med5',
                    'repro_prom':      'repro_prom',
                    'q_est':           'q_est',
                    't_integrado':     't_integrado',
                    'i_est':           'i_est',
                    'exactitud':       'exactitud',
                    'reproducibilidad':'repro',
                    'tiempo_transito': 'tiempo_transito',
                    'calibracion':     'calibracion',
                    'electrometro':    'electrometro',
                }

                for col_bd, nombre_widget in mapeo.items():
                    val = get(col_bd)
                    widget = getattr(self, nombre_widget, None)
                    if widget and val is not None:
                        widget.setText(str(val))

                # Filas de medidas de linealidad
                for i, fila in enumerate(self.medidas_lienalidad):
                    q1    = get(f'lin_q1_{i}')
                    q2    = get(f'lin_q2_{i}')
                    qprom = get(f'lin_qprom_{i}')
                    te    = get(f'lin_te_{i}')

                    if q1    is not None: fila[1].setText(str(q1))
                    if q2    is not None: fila[2].setText(str(q2))
                    if qprom is not None: fila[3].setText(str(qprom))
                    if te    is not None: fila[4].setText(str(te))

                # Actualizar date_box sin disparar señal
                self.date_box.blockSignals(True)
                self.date_box.setDate(fecha)
                self.date_box.blockSignals(False)

                self.checkBotonesFinales()

            else:
                print(f"No hay datos registrados para la fecha {fecha_str}.")
               
                
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f"✗ Error al cargar datos: {str(ex)}")
        finally:
            db.close()

    def comboBox_equipos(self):
        """
        Configuración de combos de equipos con manejo mejorado de BD y errores.
        Utiliza el gestor de conexiones optimizado.
        """
        ##logger.info("Configurando combos de equipos")
        try:
            self._configurar_referencias_widgets()
            self._cargar_modelos_camara_pozo()
            self._cargar_modelos_electrometro()
            self._conectar_señales_equipos()
            
        except Exception as e:
            #logger.error(f"Error configurando equipos: {e}")
            self._mostrar_error_usuario("Error de Equipos", 
                                        f"No se pudieron cargar los equipos: {str(e)}")
    
    def _configurar_referencias_widgets(self):
        """Configura referencias a widgets de equipos"""
        # Cámara de pozo
        self.combo_modelo = self.widgets['modelo']
        self.combo_serie = self.widgets['serie_cp']
        self.line_cal = self.widgets['calibracion']
        
        # Electrómetro
        self.combo_modelo_elec = self.widgets['modelo_elec']
        self.combo_serie_elec = self.widgets['serie_ele']
        self.line_cal_elec = self.widgets['electrometro']
    
    def _cargar_modelos_camara_pozo(self):
        """Carga modelos de cámara de pozo usando gestor optimizado"""
        consulta = """
            SELECT DISTINCT model FROM equipos 
            WHERE equip_type='Cámara de pozo' AND activo=1
            AND id IN (SELECT MAX(id) FROM equipos GROUP BY serie)
        """
        try:
            resultados = gestor_db.ejecutar_consulta_con_cache(consulta, usar_cache=True)
            modelos_pozo = [row[0] for row in resultados]
            self.combo_modelo.addItems(modelos_pozo)
            #logger.debug(f"Cargados {len(modelos_pozo)} modelos de cámara de pozo")
        except Exception as e:
            #logger.error(f"Error cargando modelos de cámara: {e}")
            raise
    
    def _cargar_modelos_electrometro(self):
        """Carga modelos de electrómetro usando gestor optimizado"""
        consulta = """
            SELECT DISTINCT model FROM equipos 
            WHERE equip_type='Electrómetro' AND activo=1
            AND id IN (SELECT MAX(id) FROM equipos GROUP BY serie)
        """
        try:
            resultados = gestor_db.ejecutar_consulta_con_cache(consulta, usar_cache=True)
            modelos_elec = [row[0] for row in resultados]
            self.combo_modelo_elec.addItems(modelos_elec)
            #logger.debug(f"Cargados {len(modelos_elec)} modelos de electrómetro")
        except Exception as e:
            #logger.error(f"Error cargando modelos de electrómetro: {e}")
            raise
    
    def _conectar_señales_equipos(self):
        """Conecta señales de cambio de equipos"""
        self.combo_modelo.currentTextChanged.connect(self.on_modelo_pozo_cambio)
        self.combo_serie.currentTextChanged.connect(self.on_serie_pozo_cambio)
        self.combo_modelo_elec.currentTextChanged.connect(self.on_modelo_elec_cambio)
        self.combo_serie_elec.currentTextChanged.connect(self.on_serie_elec_cambio)

    def on_modelo_pozo_cambio(self, modelo: str):
        """
        Cuando seleccionan un modelo de cámara de pozo, llenar las series.
        Usa gestor de BD optimizado y manejo mejorado de errores.
        """
        #logger.debug(f"Cambio de modelo de pozo: {modelo}")
        
        try:
            self._limpiar_combo_series()
            
            if not modelo or modelo == "Seleccionar...":
                return
                
            series_data = self._obtener_series_equipo('Cámara de pozo', modelo)
            self._poblar_combo_series(series_data)
            
        except Exception as e:
            #logger.error(f"Error cambiando modelo de pozo: {e}")
            self._mostrar_error_usuario("Error de Equipos", 
                                       f"No se pudieron cargar las series: {str(e)}")
    
    def _limpiar_combo_series(self):
        """Limpia el combo de series"""
        self.combo_serie.clear()
        self.combo_serie.addItem("Seleccionar Serie...")
    
    def _obtener_series_equipo(self, tipo_equipo: str, modelo: str) -> List[Tuple]:
        """Obtiene series de un equipo específico usando BD optimizada"""
        consulta = """
            SELECT serie, activo, vigente FROM equipos 
            WHERE equip_type=? AND model=?
            AND id IN (SELECT MAX(id) FROM equipos GROUP BY serie)
        """
        return gestor_db.ejecutar_consulta_con_cache(consulta, (tipo_equipo, modelo))
    
    def _poblar_combo_series(self, series_data: List[Tuple]):
        """Puebla el combo de series con indicadores visuales"""
        series_activas = []
        series_no_vigentes = []
        
        for serie, activo, vigente in series_data:
            if activo == 1.0:  # Solo equipos activos
                series_activas.append(serie)
                if vigente == 0.0:  # Si no está vigente, recordarlo
                    series_no_vigentes.append(serie)
        
        self.combo_serie.addItems(series_activas)
        self._marcar_series_vencidas(series_no_vigentes)
    
    def _marcar_series_vencidas(self, series_vencidas: List[str]):
        """Marca visualmente las series con calibración vencida"""
        for serie in series_vencidas:
            index = self.combo_serie.findText(serie)
            if index != -1:
                item = self.combo_serie.model().item(index)
                item.setForeground(QColor(255, 0, 0))  # Texto rojo
                item.setText(f"⚠️ {serie} (VENCIDO)")
                item.setToolTip("⚠️ Calibración vencida - Requiere recalibración")

    def on_serie_pozo_cambio(self, serie):
        """Cuando seleccionan serie de cámara de pozo, llenar valores de calibración"""
        modelo = self.combo_modelo.currentText()
        if self.combo_serie.currentText().startswith("⚠️"):
            serie = serie.split(" ")[1]  # Extraer la serie real sin el prefijo de advertencia

        if not serie or serie == "Seleccionar Serie...":
            return

        conn = Conexion().conectar()
        cur = conn.cursor()
        cur.execute("""SELECT calibr_fact
                    FROM equipos 
                    WHERE equip_type='Cámara de pozo' AND model=? AND serie=?
                    AND id IN (
                    SELECT MAX(id) FROM equipos GROUP BY serie)
                    """,(modelo, serie))
        row = cur.fetchone()
        if row:
            calibr_fact = row[0]
            self.line_cal.setText(str(calibr_fact))

    def on_modelo_elec_cambio(self, modelo):
        """Cuando selecciona un modelo de electrómetro, llenar las series (solo última versión por serie)"""
        self.combo_serie_elec.clear()
        self.combo_serie_elec.addItem("Seleccionar Serie...")

        conn = Conexion().conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT serie, activo, vigente FROM equipos
            WHERE equip_type='Electrómetro' AND model=?
            AND id IN (
                SELECT MAX(id) FROM equipos GROUP BY serie
            )
        """, (modelo,))
        equipos_data = cur.fetchall()
        
        # Solo agregar equipos activos
        series_activas = []
        equipos_no_vigentes = []
        
        for row in equipos_data:
            serie, activo, vigente = row
            if activo == 1.0:  # Solo equipos activos
                series_activas.append(serie)
                if vigente == 0.0:  # Si no está vigente, recordarlo
                    equipos_no_vigentes.append(serie)
        
        self.combo_serie_elec.addItems(series_activas)
        
        # Marcar en rojo los no vigentes y agregar indicador visual
        for serie in equipos_no_vigentes:
            index = self.combo_serie_elec.findText(serie)
            if index != -1:
                item = self.combo_serie_elec.model().item(index)
                item.setForeground(QColor(255, 0, 0))  # Poner en rojo
                #item.setData(Qt.BackgroundRole, QColor(255, 240, 240))  # Fondo ligeramente rojizo
                item.setText(f"⚠️ {serie} (VENCIDO)")  # Modificar el texto para ser más visible
                item.setToolTip("⚠️ Calibración vencida - Requiere recalibración")  # Tooltip
        
        conn.close()
    def button_click(self):
        #print("Entra a la función button_click en la clase PruebaDiariaBraq en braquiterapia.py")
        #self.fuera_servicio.clicked.connect(self.reasignar_botonySERVICIO)
        #self.btn_add.clicked.connect(lambda _, maquina='braqui', otro = "Diario" : self.ordenar_botones(maquina, self.fueradeservicio, otro))
        #self.btn_add.clicked.connect(lambda: load_table(self, self.boolean_colums, self.actividad_ciclos, 'braqui'))
        self.btn_add.clicked.connect(lambda:asignar_encabezados(self, 'braqui'))
        
        #self.btn_add.clicked.connect(lambda _: self.clean_info(imagenes=False))
        #self.btn_add.clicked.connect(lambda _:self.clean_info)

        #self.btn_clean.clicked.connect(lambda _: self.clean_info(imagenes=True))
        

        #self.boton_aceptar.clicked.connect(self.subirlisto)
        self.posi_inicial = "Linealidad Braquiterapia"
        self.checkBotonesFinales(line=None, braqui=True, otro=self.posi_inicial)
        
        #self.boton_cancel.clicked.connect(self.cancelarbraqui)
        
        """for line in self.df_lines:
            dato = getattr(self, line)
            dato.textChanged.connect(lambda _, line=line: self.checkBotonesFinales(line, braqui=True))"""
                                                             
        self.btn_delete.clicked.connect(lambda: verificar_eliminar(self, self.table, "LinealidadBraquiterapia", None)) 

        #self.menu_graficar.currentIndexChanged.connect(self.mostrar_submenu)
        
        # for grafica in self.graficar:
        #     grafica.currentIndexChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
        #     self.btn_submit.clicked.connect(lambda _, grafica=grafica: self.plotter(grafica))
        #     self.limit1.dateChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
        #     self.limit2.dateChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
        
        self.search_bar.textChanged.connect(self._iniciar_busqueda_debounced)
        
        self.edit_table.clicked.connect(self.verificar_editar)

        self.accept_edit.clicked.connect(lambda: self.cargarDatosEditados(self.item, self.old_value, "braqui"))
        self.accept_edit.clicked.connect(lambda: load_table(self, self.boolean_colums, self.actividad_ciclos, 'braqui'))
        self.accept_edit.clicked.connect(lambda:asignar_encabezados(self, 'braqui'))
        
        self.cancel_edit.clicked.connect(lambda: self.cancelarEdicion(self.item, self.old_value))
        self.cancel_edit.clicked.connect(lambda: load_table(self, self.boolean_colums, self.actividad_ciclos, 'braqui'))
        self.cancel_edit.clicked.connect(lambda:asignar_encabezados(self, 'braqui'))
        self.btn_submit.clicked.connect(
        lambda: self._generar_reporte_linealidad()
        )
    
     
    
    
    def construir_tablas_reporte_linealidad(self, fecha):
        conn = Conexion().conectar()
        cur = conn.cursor()
        cur.execute("SELECT * FROM LinealidadBraquiterapia WHERE DATE(fecha) = ?", (fecha,))
        row = cur.fetchone()
        conn.close()

        if not row:
            QMessageBox.critical(self, "Error", f"No hay registros para la fecha {fecha}")
            return None

        # --- sistema_medicion_linealidad ---
        df_sistema = pd.DataFrame({
            "Campo": ["Modelo cámara", "Serie cámara", "Factor cal. cámara",
                    "Modelo electrómetro", "Serie electrómetro", "Factor cal. electrómetro"],
            "Valor": [row[2], row[3], row[4], row[5], row[6], row[7]]
        })

        # --- carga_colectada ---
        df_carga = pd.DataFrame({
            "Campo": ["Q estacionaria (nC)", "Tiempo integrado (s)", "Corriente estacionaria (nA)",
                    "M1 (nC)", "M2 (nC)", "M3 (nC)", "M4 (nC)", "M5 (nC)", "Promedio (nC)"],
            "Valor": [row[8], row[9], row[10], row[14], row[15], row[16], row[17], row[18], row[19]]
        })

        # --- medidas_linealidad ---
        # columnas desde índice 20: lin_tp_0, lin_q1_0, lin_q2_0, lin_qprom_0, lin_te_0, ...
        filas_medidas = []
        for i in range(10):
            base = 20 + i * 5
            filas_medidas.append([row[base], row[base+1], row[base+2], row[base+3], row[base+4]])
        df_medidas = pd.DataFrame(filas_medidas,
            columns=["Tiempo parada (s)", "Q1 (nC)", "Q2 (nC)", "Qprom (nC)", "T. efectivo (s)"])

        # --- resultados_linealidad ---
        df_resultados = pd.DataFrame({
            "Campo": ["Reproducibilidad (%)", "Exactitud (R²)", "Tiempo de tránsito (s)"],
            "Valor": [row[11], row[12], row[13]]
        })

        # --- grafico_linealidad ---
        # Capturar el canvas actual como base64
        buf = io.BytesIO()
        self.canvas.figure.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        import base64
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        df_grafico = pd.DataFrame({"Gráfico": [img_b64]})

        return {
            'sistema_medicion_linealidad': df_sistema,
            'carga_colectada':             df_carga,
            'medidas_linealidad':          df_medidas,
            'resultados_linealidad':       df_resultados,
            'grafico_linealidad':          df_grafico,
        }
    

    def _generar_reporte_linealidad(self):
        
        fecha = self.date_box.date().toString('yyyy-MM-dd')
        maquina = self.mach_name2.text()
        id_maquina = self.code_1.text()
        usuario = self.user_id._nombre
        

        tablas = self.construir_tablas_reporte_linealidad(fecha)
        if tablas is None:
            return

        db = self.opeenDatabase()
        temp_image_path, rol = self._obtener_firma_usuario(usuario, db)
        db.close()
        tablas = self.construir_tablas_reporte_linealidad(fecha)
        if tablas is None:
            return

        # Obtener firma igual que hace reporte()
        # ... (misma lógica de query a users que ya tienes)

        buffer = generar_reporte_pdf_multitabla_mensual(
            tablas=tablas,
            fecha=fecha,
            user=usuario,
            tipo_reporte='Linealidad',
            maquina='Braquiterapia',
            id_maquina=id_maquina,
            logo_path=resource_path('resources/icons/iconoPDF.png'),
            firma=temp_image_path,
            role=rol,
            temp=True
        )

        pdf_bytes = buffer.getvalue() if hasattr(buffer, 'getvalue') else bytes(buffer)
        self.window = PdfViewer(pdf_data=pdf_bytes, fecha=fecha,
                                maquina=maquina, tipo_reporte='Linealidad')
        self.window.show()
        
    def _obtener_firma_usuario(self, usuario, db):
        """Extrae firma y rol de un usuario desde la BD. Reutilizable."""
        temp_image_path = None
        rol = None
        query = QSqlQuery(db)
        query.prepare("SELECT firma, role FROM users WHERE fullname = ?")
        query.addBindValue(usuario)
        if query.exec() and query.next():
            firma = query.value(0)
            rol = query.value(1)
            if firma:
                try:
                    firma_bytes = base64.b64decode(firma) if isinstance(firma, str) else bytes(firma)
                    pixmap = QPixmap()
                    if pixmap.loadFromData(firma_bytes):
                        temp_fd, temp_image_path = tempfile.mkstemp(suffix=".png")
                        pixmap.save(temp_image_path, "PNG")
                except Exception as e:
                    print(f"Error procesando firma: {e}")
        return temp_image_path, rol  
    def on_serie_elec_cambio(self, serie):
        """Cuando seleccionan serie de electrómetro, llenar factor de calibración"""
        modelo = self.combo_modelo_elec.currentText()
        if self.combo_serie_elec.currentText().startswith("⚠️"):
            serie = serie.split(" ")[1]  # Extraer la serie real sin el prefijo de advertencia
        if not serie or serie == "Seleccionar Serie...":
            return

        conn = Conexion().conectar()
        cur = conn.cursor()
        cur.execute("""SELECT calibr_fact
                    FROM equipos 
                    WHERE equip_type='Electrómetro' AND model=? AND serie=?
                    AND id IN (
                        SELECT MAX(id) FROM equipos GROUP BY serie
                    )
                """,(modelo, serie))
        row = cur.fetchone()
        if row:
            calibr_fact = row[0]
            self.line_cal_elec.setText(str(calibr_fact))

    def generar_tablas(self, titulos):
        if hasattr(self, 'tabla_medidas_widget'):
            self.tabla_medidas_widget.setParent(None)

        grid = QGridLayout()

        # Títulos
        for col, titulo in enumerate(titulos):
            encabezado = QLineEdit(titulo)
            encabezado.setReadOnly(True)
            encabezado.setAlignment(Qt.AlignCenter)
            encabezado.setFixedWidth(145)
            encabezado.setStyleSheet("border: 1px solid #c1df08; border-radius: 10px; background-color: rgb(234, 244, 167);")
            grid.addWidget(encabezado, 0, col)

        contenedor = QWidget()
        contenedor.setLayout(grid)
        self.tabla_medidas_widget = contenedor

        return grid, contenedor

    def generar_tabla_medidas(self):
        titulos = ["Tiempo parada (s)", "Q1 (nC)", "Q2 (nC)", "Qpromedio (nC)", "Tiempo efectivo (s)"]
        grid, contenedor = self.generar_tablas(titulos=titulos)

        self.medidas_lienalidad = []
        tiempo_parada = [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6, 51.2]

        for fila, tp in enumerate(tiempo_parada):
            fila_campos = []

            # Columna 0: tiempo de parada (solo lectura)
            tiempo_widget = QLineEdit(f"{tp:.2f}")
            tiempo_widget.setReadOnly(True)
            tiempo_widget.setAlignment(Qt.AlignCenter)
            tiempo_widget.setFixedWidth(145)
            tiempo_widget.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px; background-color: #f0f0f0;")
            grid.addWidget(tiempo_widget, fila + 1, 0)
            fila_campos.append(tiempo_widget)

            # Columnas 1 y 2: entradas de usuario (Q1 y Q2)
            for col in range(1, 3):
                entrada = QLineEdit()
                entrada.setAlignment(Qt.AlignCenter)
                entrada.setFixedWidth(145)
                entrada.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px;")
                grid.addWidget(entrada, fila + 1, col)
                fila_campos.append(entrada)

                # Cambiar foco con Enter hacia la misma columna, fila siguiente
                def avanzar_foco(f=entrada, r=fila, c=col):
                    def handler():
                        if r + 1 < 10:
                            self.medidas_lienalidad[r + 1][c].setFocus()
                    return handler

                entrada.returnPressed.connect(avanzar_foco())

            # Columna 3: Qpromedio
            qprom = QLineEdit("-")
            qprom.setReadOnly(True)
            qprom.setAlignment(Qt.AlignCenter)
            qprom.setFixedWidth(145)
            qprom.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px; background-color: #f0f0f0;")
            grid.addWidget(qprom, fila + 1, 3)
            fila_campos.append(qprom)

            # Columna 4: Tiempo efectivo
            tef = QLineEdit("-")
            tef.setReadOnly(True)
            tef.setAlignment(Qt.AlignCenter)
            tef.setFixedWidth(145)
            tef.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px; background-color: #f0f0f0;")
            grid.addWidget(tef, fila + 1, 4)
            fila_campos.append(tef)

            self.medidas_lienalidad.append(fila_campos)

        # Botón para calcular
        self.aceptar = QPushButton("Ok")
        self.aceptar.setStyleSheet("border: 1px solid #c1df08; background-color: rgb(234, 244, 167); color: black;")
        self.aceptar.setFixedWidth(60)
        self.aceptar.clicked.connect(self.Calculo_Linealidad)
        grid.addWidget(self.aceptar, 11, 0)

        self.layout_medicion_linealidad.addWidget(contenedor)

    def extraer_datos_medidas(self):
        tiempo_parada = [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6, 51.2]
        q1 = []
        q2 = []
        qprom = []
        tiempo_efectivo = []

        try:
            i_est = float(self.i_est.text())
        except ValueError:
            QMessageBox.warning(self, "Advertencia", "Debes ingresar la corriente estacionaria (i_est).")
            return [], [], [], [], []

        for i, fila in enumerate(self.medidas_lienalidad):
            try:
                tp = tiempo_parada[i]
                v1 = float(fila[1].text())
                v2 = float(fila[2].text())
                prom = (v1 + v2) / 2
                tef = prom / i_est
            except ValueError:
                continue

            fila[3].setText(f"{prom:.2f}")
            fila[4].setText(f"{tef:.4f}")

            q1.append(v1)
            q2.append(v2)
            qprom.append(round(prom, 3))
            tiempo_efectivo.append(round(tef, 3))

        self.resultados_linealidad = {
            "tp": tiempo_parada,
            "q1": q1,
            "q2": q2,
            "qprom": qprom,
            "tef": tiempo_efectivo,
        }

        return tiempo_parada, q1, q2, qprom, tiempo_efectivo

    def Calculo_Linealidad(self):
        tiempo_parada = []  # Definir antes del try para evitar NameError en el except
        try:
            tiempo_parada, q1, q2, promedios, tiempo_efectivo = self.extraer_datos_medidas()
            
            x = np.array(tiempo_parada)
            y = np.array(tiempo_efectivo)
            m, b = np.polyfit(x, y, 1)

            y_pred = m * x + b
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            self.r2 = 1 - (ss_res / ss_tot)
            self.b = b

            graficar_linealidad(self.canvas, tiempo_efectivo, tiempo_parada)

            if hasattr(self, 'label_r2') and self.label_r2 is not None:
                if self.col2.indexOf(self.label_r2) != -1:
                    self.col2.removeWidget(self.label_r2)
                self.label_r2.setParent(None)
                self.label_r2.deleteLater()

            texto = "<pre style='font-family: Segoe UI, monospace; font-size: 20px;'>"
            texto += "<b>Linealidad de la Fuente</b>\n"
            texto += f"<b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Exactitud:</b> <span style='font-weight:normal'>{self.r2:.3f}</span><br>\n"
            texto += f"<b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tiempo de tránsito:</b> <span style='font-weight:normal'>{self.b:.3f}</span><br>\n"
            texto += "</pre>"

            self.label_r2 = QLabel()
            self.label_r2.setTextFormat(Qt.RichText)
            self.label_r2.setText(texto)
            self.label_r2.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.label_r2.setWordWrap(True)
            self.label_r2.setMinimumHeight(70)

            self.exactitud.setText(f"{self.r2:.2f}")

            # CORRECCIÓN 6: desviación estándar de los promedios
            # En Calculo_Linealidad, reemplaza la línea de reproducibilidad por:
            try:
                repro_vals = [
                    float(self.repro_med1.text()),
                    float(self.repro_med2.text()),
                    float(self.repro_med3.text()),
                    float(self.repro_med4.text()),
                    float(self.repro_med5.text()),
                ]
                reproducibilidad = 100 - float(np.std(repro_vals, ddof=1))
            except ValueError:
                reproducibilidad = 0.0

            self.repro.setText(f"{reproducibilidad:.4f}")
            self.tiempo_transito.setText(f"{self.b:.2f}")

            self.col2.addWidget(self.label_r2)

        except Exception as e:  # CORRECCIÓN 5: except específico
            traceback.print_exc()
            if not tiempo_parada:
                QMessageBox.warning(self, "Advertencia", "No se ingresaron datos válidos.")
                
    
    def guardar_linealidad(self):
        try:
            user = self.user_id._nombre
            fecha = self.date_box.date().toString("yyyy-MM-dd")

            # Datos generales
            modelo = self.modelo.currentText()
            serie_cp = self.serie_cp.currentText()
            calibracion = float(self.calibracion.text())
            modelo_elec = self.modelo_elec.currentText()
            serie_ele = self.serie_ele.currentText()
            electrometro = float(self.electrometro.text())

            q_est = float(self.q_est.text())
            t_integrado = float(self.t_integrado.text())
            i_est = float(self.i_est.text())

            reproducibilidad = round(float(self.repro.text()), 4)
            exactitud = round(self.r2, 5)
            tiempo_transito = round(self.b, 2)

            repro_med = [
                float(self.repro_med1.text()), float(self.repro_med2.text()), float(self.repro_med3.text()),
                float(self.repro_med4.text()), float(self.repro_med5.text()), float(self.repro_prom.text())
            ]

            # Datos de linealidad
            tp, q1, q2, qprom, te = self.extraer_datos_medidas()
            if not tp:
                QMessageBox.warning(self, "Advertencia", "No se pudieron extraer datos de medición.")
                return

            # Rellenar hasta 10 con None si hay menos
            def rellenar(lista, largo=10):
                return lista + [None] * (largo - len(lista))

            tp = rellenar(tp)
            q1 = rellenar(q1)
            q2 = rellenar(q2)
            qprom = rellenar(qprom)
            te = rellenar(te)

            # Construir lista de valores a insertar
            datos = [
                user, fecha,
                modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro,
                q_est, t_integrado, i_est,
                reproducibilidad, exactitud, tiempo_transito,
                *repro_med
            ]

            for i in range(10):
                datos += [tp[i], q1[i], q2[i], qprom[i], te[i]]

            # Columnas explícitas (sin id)
            columnas = '''
                user, fecha, modelo, serie_cp, calibracion,
                modelo_elec, serie_ele, electrometro,
                q_est, t_integrado, i_est,
                reproducibilidad, exactitud, tiempo_transito,
                repro_m1, repro_m2, repro_m3, repro_m4, repro_m5, repro_prom,
                lin_tp_0, lin_q1_0, lin_q2_0, lin_qprom_0, lin_te_0,
                lin_tp_1, lin_q1_1, lin_q2_1, lin_qprom_1, lin_te_1,
                lin_tp_2, lin_q1_2, lin_q2_2, lin_qprom_2, lin_te_2,
                lin_tp_3, lin_q1_3, lin_q2_3, lin_qprom_3, lin_te_3,
                lin_tp_4, lin_q1_4, lin_q2_4, lin_qprom_4, lin_te_4,
                lin_tp_5, lin_q1_5, lin_q2_5, lin_qprom_5, lin_te_5,
                lin_tp_6, lin_q1_6, lin_q2_6, lin_qprom_6, lin_te_6,
                lin_tp_7, lin_q1_7, lin_q2_7, lin_qprom_7, lin_te_7,
                lin_tp_8, lin_q1_8, lin_q2_8, lin_qprom_8, lin_te_8,
                lin_tp_9, lin_q1_9, lin_q2_9, lin_qprom_9, lin_te_9
            '''

            placeholders = ','.join(['?'] * len(datos))

            conn = Conexion().conectar()
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO LinealidadBraquiterapia ({columnas})
                VALUES ({placeholders})
            ''', datos)

            conn.commit()
            conn.close()
            QMessageBox.information(self, "Guardado", "Datos de linealidad almacenados correctamente.")
            mostrar_db_linealidad(self)
            self.tabla_resultados.viewport().update()

        except:
            traceback.print_exc()
            QMessageBox.warning(self, "Advertencia", "No se pudieron guardar los datos.")
            return

    def mostrar_db_Linealidad(self):
        # Quita canvas y toolbar si están
        if hasattr(self, 'canvas') and self.col2.indexOf(self.canvas) != -1:
            self.col2.removeWidget(self.canvas)
            self.canvas.setParent(None)

        # Quita la toolbar si está
        if hasattr(self, 'toolbar') and self.toolbar is not None and self.col2.indexOf(self.toolbar) != -1:
            self.col2.removeWidget(self.toolbar)
            self.toolbar.setParent(None)

        # Agrega la tabla si no está
        if self.col2.indexOf(self.tabla_resultados) == -1:
            self.col2.addWidget(self.tabla_resultados)


        mostrar_db_linealidad(self)

    def mostrar_tabla_carga(self, fila):
        repro = fila[15:20]  # de la medida 1 a la medida 5 de reproducibilidad
        repro_prom = fila[20]

        dialog = QDialog(self)
        dialog.setWindowTitle("Carga colectada en 60s - Reproducibilidad")
        dialog.setMinimumSize(870, 120)  # Ancho x Alto mínimo
        dialog.resize(270, 120)   
        layout = QVBoxLayout()

        table = QTableWidget(1, 6)
        table.setHorizontalHeaderLabels(["M1 (nC)", "M2 (nC)", "M3 (nC)", "M4 (nC)", "M5 (nC)", "Promedio"])
        for i, val in enumerate(list(repro) + [repro_prom]):
            item = QTableWidgetItem(f"{val:.2f}" if val is not None else "-")
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(0, i, item)
            

        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec_()

    def mostrar_tabla_linealidad(self, fila):
        linealidad = fila[21:]
        medidas = [linealidad[i:i+5] for i in range(0, len(linealidad), 5)]

        dialog = QDialog(self)
        dialog.setWindowTitle("Medidas de Linealidad")
        dialog.setMinimumSize(550, 500)  # Ancho x Alto mínimo
        dialog.resize(700, 500)   
        layout = QVBoxLayout()

        table = QTableWidget(10, 5)
        table.setHorizontalHeaderLabels(["Tiempo parada", "Q1", "Q2", "Qprom", "T. efectivo"])

        for i, fila_valores in enumerate(medidas):
            for j, val in enumerate(fila_valores):
                item = QTableWidgetItem(f"{val:.2f}" if val is not None else "-")
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(i, j, item)

        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec_()

    
    def plotter_mensual_desde_menu(self, selected_chart):
        """Método para graficar cuando se selecciona desde el menú"""
        if selected_chart == "Seleccionar...":
            return
        
        # Usar solo la fecha actual seleccionada
        fecha_seleccionada = self.date_grafica.date().toString('yyyy-MM-dd')
        self._ejecutar_grafico_mensual(selected_chart, fecha_seleccionada)

    def _ejecutar_grafico_mensual(self, selected_chart, fecha):
        """Método interno que ejecuta la gráfica"""
        # Limpiar el espacio para graficar
        self.figure.clear()
        
        # Funcion para graficar los datos de máximos de cámara
        def graficar_maximos_camara(canvas, query, fecha):
            """Grafica los datos de máximos de cámara para una fecha específica"""
            query.prepare("""
                SELECT mc.posicion, mc.promedio
                FROM MaximosCamaras mc
                JOIN TipoCalibracion tc ON mc.ref = tc.id
                WHERE DATE(tc.fecha) = ?
                ORDER BY mc.posicion ASC
            """)
            query.bindValue(0, fecha)
            query.exec_()
            
            posiciones = []
            promedios = []
            
        
            while query.next():
                # Convertir a float para evitar el error de numpy
                posiciones.append(float(query.value(0)))
                promedios.append(float(query.value(1)))

            #print(f"Graficando máximos de cámara para la fecha: {fecha}")
            #print(f"Posiciones: {posiciones}")
            #print(f"Promedios: {promedios}")
            graficar_resultados(canvas, posiciones=posiciones, promedio=promedios)

        # Funcion para graficar los datos de linealidad de la fuente
        def graficar_linealidad_fuente(canvas, query, fecha):
            """Grafica los datos de linealidad de la fuente para una fecha específica"""
            query.prepare("""
                SELECT lf.lin_tp_0,  lf.lin_te_0,
                    lf.lin_tp_1, lf.lin_te_1,
                    lf.lin_tp_2, lf.lin_te_2,
                    lf.lin_tp_3, lf.lin_te_3,
                    lf.lin_tp_4, lf.lin_te_4,
                    lf.lin_tp_5, lf.lin_te_5,
                    lf.lin_tp_6, lf.lin_te_6,
                    lf.lin_tp_7, lf.lin_te_7,
                    lf.lin_tp_8, lf.lin_te_8,
                    lf.lin_tp_9, lf.lin_te_9
                FROM LinealidadBraquiterapia lf
                WHERE DATE(lf.fecha) = ?
            """)
            query.bindValue(0, fecha)
            query.exec_()
            
            tiempo_parada = []    # Para valores _tp
            tiempo_efectivo = []  # Para valores _te
            
            while query.next():
                # Iterar por cada par tp/te (10 puntos total)
                for i in range(10):  # 10 puntos de medición
                    tp_index = i * 2      # Índices pares: 0, 2, 4, 6, 8, 10, 12, 14, 16, 18
                    te_index = i * 2 + 1  # Índices impares: 1, 3, 5, 7, 9, 11, 13, 15, 17, 19
                    
                    tp_value = query.value(tp_index)  # lin_tp_i
                    te_value = query.value(te_index)  # lin_te_i
                    
                    if tp_value is not None:
                        tiempo_parada.append(float(tp_value))
                    if te_value is not None:
                        tiempo_efectivo.append(float(te_value))

            if tiempo_efectivo and tiempo_parada:
                graficar_linealidad(canvas, tiempo_efectivo, tiempo_parada)
        
        # Abrir la base de datos
        db = self.opeenDatabase()
        query = QSqlQuery(db)
        
        if selected_chart == "Máximos de la cámara":
            graficar_maximos_camara(self.canvas, query, fecha)
        elif selected_chart == "Linealidad de la fuente":
            graficar_linealidad_fuente(self.canvas, query, fecha)

        # Redibujar en el canvas
        self.canvas.draw()
        db.close()
    
    def cleanup_recursos(self):
        """Limpia recursos de la clase Linealidad"""
        #logger.info("Limpiando recursos de Linealidad")
        try:
            # Detener timers
            if hasattr(self, '_timer_calculo'):
                self._timer_calculo.stop()
            
            # Limpiar cache
            if hasattr(self, '_cache_calculos'):
                self._cache_calculos.clear()
            
            # Limpiar widgets pesados
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.figure.clear()
                
            #print("Recursos de Linealidad limpiados")
        except Exception as e:
            print(f"Error limpiando recursos de Linealidad: {e}")
    
    def _mostrar_error_usuario(self, titulo: str, mensaje: str):
        """Muestra errores al usuario de forma consistente"""
        print(f"{titulo}: {mensaje}")
        try:
            QMessageBox.warning(self, titulo, mensaje)
        except Exception as e:
            print(f"Error mostrando mensaje al usuario: {e}")
    
    def _ejecutar_busqueda_filtrada(self):
        """Ejecuta búsqueda filtrada después del debouncing"""
        try:
            if hasattr(self, 'search_bar') and hasattr(self, 'filtrarTabla'):
                texto_busqueda = self.search_bar.text()
                print(f"Ejecutando búsqueda filtrada: {texto_busqueda}")
                self.filtrarTabla()
        except Exception as e:
            print(f"Error en búsqueda filtrada: {e}")
    
    def _iniciar_busqueda_debounced(self):
        """Inicia búsqueda con debouncing para evitar búsquedas excesivas"""
        self._timer_busqueda.stop()
        self._timer_busqueda.start(300)  # 300ms de delay

" Es el mismo analisis que en la prueba diaria pero para imagenes de una sola linea"
class PosicionamientoInicial(PruebaBasico):
    """
    Análisis de posicionamiento inicial de la fuente.
    Incluye mejoras de rendimiento, cache de resultados y manejo optimizado de errores.
    """
    desplazamientoReady = pyqtSignal(object)
    
    def __init__(self, user_id): 
        super(PosicionamientoInicial, self).__init__()
        #print("PosicionamientoInicial __init__ called")
        
        self.user_id = user_id
        self.ref_bd=None
        # Pre-cargar dependencias para mejor rendimiento
        optimizador_analisis.precargar_dependencias()
        
        # Inicializar timer para debouncing de búsqueda
        self._timer_busqueda = QTimer()
        self._timer_busqueda.setSingleShot(True)
        self._timer_busqueda.timeout.connect(self._ejecutar_busqueda_filtrada)
        
        # Timer para debouncing de análisis cuando se cambian parámetros
        self._timer_analisis = QTimer()
        self._timer_analisis.setSingleShot(True)
        self._timer_analisis.timeout.connect(self._ejecutar_analisis_diferido)
        
        # Inicializar componentes con lazy loading
        try:
            self.initDATA(user_id)
            self.initUI()
            
            self._inicializar_recursos()
            
            # Cargar BD de forma diferida para mejorar tiempo de inicialización
            QTimer.singleShot(50, lambda: mostrar_db_mensualBraqui(self))
            
        except Exception as e:
            print(f"Error inicializando PosicionamientoInicial: {e}")
            self._mostrar_error_usuario("Error de Inicialización", str(e))
    
    def _inicializar_recursos(self):
        """Inicializa recursos de forma lazy"""
        self.resultados_table = QTableWidget()
        self.resultados_table.setColumnCount(7)
        self.resultados_table.setEditTriggers(QTableWidget.NoEditTriggers)
    
    """ Diccionario con los nombres de las herramientas para los category (menu desplegable para ingresar).                                                                                        """
    def initDATA(self, user_id):

        self.diccionario_invertido = {
            'int_con_box': ['Interrupción desde consola', '', 'scatter'],
            'emerg_con': ['Parada de emergencia','', 'scatter'],
            'blq_puerta': ['Bloqueo de puerta','', 'scatter'],
            'pos_fuente': ['Indicador de posición','', 'scatter'],
            'res_fuente': ['Respaldo retorno de fuente','', 'scatter'],
            'key_fuente': ['Interruptor de llave','', 'scatter'],
            'mon_area': ['Monitor de área','', 'scatter'],
            'lum_puerta': ['Indicador luminoso', '', 'scatter'],
            'tub_guia': ['Conexión tubo guía', '', 'scatter'],
            'visual_sys': ['Sistema de visualización', '', 'scatter'],
            'intercom': ['Sistema de intercounicación', '', 'scatter'],
            'mon_rad_port': ['Monitor de radiación potátil', '', 'scatter'],
            'tol_rep_act_ci': ['Actividad reportada', '', 'line'],
            'tol_exp_act': ['Actividad esperada', '', 'line'],
            'tol_cyc_dummy': ['Ciclos del Dummy', '', 'line'],
            'tol_cyc_rad': ['Ciclos de la fuente', '', 'line'],
            'observaciones' : ['Observaciones', '', 'Na']
        }
        
        self.init_data(user_id, self.diccionario_invertido)
        

    """ Crea la estructura visual general, usa QToolBox para organizar las secciones y prepara el area de gráficos                                                                                  """
    def initUI(self):
        self.main_layout = QHBoxLayout()

        archivo = 'widgets.xlsx'
        _ = self.setupBox(archivo, 'encabezado_braq')
        self.date_box.setDisplayFormat("yyyy/MM/dd")

        # df, n, layouts, _ = self.setupBox(archivo, '', main=False)

        self.category1 = self.imagenUpLoader()

        toolbox = QToolBox()
        self.general_layout.addWidget(toolbox)
        toolbox.addItem(self.category1, 'ANALIZAR IMÁGENES')

        _ = self.setupBox(archivo, 'btn')
        self.btn_add.setObjectName("boton_nofunciona")
        self.btn_add.setEnabled(False)
        self.btn_add.setProperty("estado", "noselected")

        # Si sigues usando df o diccionario desde el Excel, necesitas recuperarlos antes
        df, _, _, _ = self.setupBox(archivo, 'preguntas_braq', main=False)
        self.datos_tabla = self.storeDailyTests(df)
        self.init_ui(df, self.diccionario_invertido)

        self.setupButtonConnections(df, maquina='braqui')

        self.boton_volver = QPushButton("Volver")
        self.boton_volver.setFixedSize(100, 40)
        self.boton_volver.setStyleSheet("background-color: #4a8892; color: white; border-radius: 10px;")
        self.boton_volver.clicked.connect(self.mostrar_canvas)

        self.boton_eliminar = QPushButton("Eliminar fila")
        self.boton_eliminar.setFixedSize(100, 40)
        self.boton_eliminar.setStyleSheet("background-color: #d9534f; color: white; border-radius: 10px;")
        self.boton_eliminar.clicked.connect(self.eliminar_fila_resultado)
        self.button_click()
        
        
    
    """ Crea los botones y conecta las acciones de los botones a sus respectivas funciones                                                                                  """
    
    
            
    
    def button_click(self):
        #print("Entra a la función button_click de la clase PosicionamientoInicial")
        self.fuera_servicio.clicked.connect(self.reasignar_botonySERVICIO)

        self.btn_clean.clicked.connect(lambda _: self.clean_info(imagenes=True))
        
        self.btn_submit.clicked.connect(
            lambda _, maquina=self.mach_name2.text(), id_maquina=self.code_1.text(): 
                reporte(self, fecha=self.date_box.date().toString('yyyy-MM-dd'), 
                        maquina=maquina, id_maquina=id_maquina, tipo_reporte='diario', 
                        diccionario=self.diccionario_invertido, umbrales=None)
        )

        self.boton_aceptar.clicked.connect(self.subirlisto)
        self.posi_inicial = "Posicionamiento Inicial"

        self.btn_add.clicked.connect(self.enviar_desplazamiento)
        self.boton_aceptar.clicked.connect(lambda _, line=None: self.checkBotonesFinales(line, braqui=True, otro = self.posi_inicial))
        self.btn_add.clicked.connect(lambda: mostrar_db_mensualBraqui(self))
        self.bloquearboton(self.btn_add)
        #print("Llama a la función checkBotonesFinales en button_click de la clase PosicionamientoInicial")

        self.boton_cancel.clicked.connect(self.cancelarbraqui)
        
        self.btn_delete.clicked.connect(lambda: verificar_eliminar(self, self.table, "TipoCalibracion", None)) 
        self.btn_delete.clicked.connect(lambda: mostrar_db_mensualBraqui(self))
        self.menu_graficar.currentIndexChanged.connect(self.mostrar_submenu)
        self.date_box.dateChanged.connect(self.actualizar_ref_bd)
        
        for grafica in self.graficar:
            grafica.currentIndexChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
            self.btn_submit.clicked.connect(lambda _, grafica=grafica: self.plotter(grafica))
            self.limit1.dateChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
            self.limit2.dateChanged.connect(lambda _, grafica=grafica: self.plotter(grafica))
        
        self.search_bar.textChanged.connect(self._iniciar_busqueda_debounced)
    
    def enviar_desplazamiento(self):
        print("Enviando desplazamiento...")
        desplazamientos = self.guardar_datos_ini()

        if desplazamientos:
            #print(f" Emitiendo desde Posicionamiento: {id(self)}")
            self.desplazamientoReady.emit(desplazamientos)

    """ Muestra el submenu de graficas dependiendo de la seleccion del menu principal                                                                                                               """
    def actualizar_ref_bd(self, fecha=None):
        """Actualiza self.ref_bd cuando cambia la fecha"""
        fecha = self.date_box.date()
        
        def consulta_db(fecha_consulta):
            # Pasar de el formato guardado "yyyy/MM/dd HH:mm:ss" a "yyyy/MM/dd"
            fecha_consulta = fecha_consulta.toString("yyyy-MM-dd")
            conn = Conexion().conectar()
            cursor = conn.cursor()
            
            # Usar DATE() para extraer solo la parte de fecha del campo en la BD
            cursor.execute("SELECT id FROM TipoCalibracion WHERE DATE(fecha) = ?", (fecha_consulta,))
            result = cursor.fetchone()
            print(f"Consulta para fecha {fecha_consulta}: {result}")
            
            if result:
                ref_bd = result[0]
            else:
                ref_bd = None
                
            conn.close()
            return ref_bd
        
        nuevo_ref_bd = consulta_db(fecha)
      
        if nuevo_ref_bd != self.ref_bd:
            self.ref_bd = nuevo_ref_bd
            print(f"ref_bd actualizado a: {self.ref_bd}")
            
            # Recargar los datos si hay un nuevo ref_bd
            if self.ref_bd is not None:
                print("Nuevo ref_bd encontrado, recargando datos...")
                # Recargar los datos en los widgets
                # Buscar el DataFrame correcto para esta clase
                df_para_recargar = None
                if hasattr(self, 'df_tac'):  # Para PruebaMensualTAC
                    df_para_recargar = self.df_tac
                elif hasattr(self, 'datos_tabla') and hasattr(self, 'diccionario_invertido'):  # Para PruebaMensualBraq
                    # Necesitamos el df original, vamos a buscarlo
                    archivo = 'widgets.xlsx'
                    df_para_recargar, _, _, _ = self.setupBox(archivo, 'preguntas_mensualBraqui', main=False)
                
                if df_para_recargar is not None:
                    # Cargar cada tabla en su categoría correcta
                    self.addsomething(self.category1, df_para_recargar, "tipo", "TipoCalibracion", "id", self.ref_bd)
                    self.addsomething(self.category2, df_para_recargar, "sistema", "SistemaMedicion", "ref", self.ref_bd)
                    self.addsomething(self.category3, df_para_recargar, "condiciones", "CondicionesMedicion", "ref", self.ref_bd)
                    self.addsomething(self.category6, df_para_recargar, "observaciones", "CondicionesMedicion", "ref", self.ref_bd)
                    print("Datos recargados exitosamente")
                else:
                    print("No se pudo encontrar el DataFrame para recargar")
            else:
                print("No se encontró ref_bd para la fecha seleccionada")
                # Limpiar los campos si no hay datos
                self.limpiar_todos_los_campos()

    def mostrar_submenu(self):
        
        for grafica in self.graficar:
            grafica.hide()
            grafica.setCurrentIndex(0)
        selection = self.menu_graficar.currentIndex()
        
        if selection > 0 and selection <= len(self.graficar):
            self.graficar[selection-1].show()

    """ Crea los parámetros de umbral y distancia mínima entre picos, y los botones de analizar y guardar                                                                                           """
    def _crear_parametros(self):
        layout = QHBoxLayout()
        self.label_umbral = QLabel("Umbral Relativo:")
        self.label_umbral.setFont(QFont("Arial", weight=QFont.Bold))
        self.spin_umbral = QDoubleSpinBox()
        self.spin_umbral.setRange(0.0,30.0)
        self.spin_umbral.setSingleStep(0.1)
        self.spin_umbral.setDecimals(1)
        self.spin_umbral.setValue(1.0)
        self.spin_umbral.setFixedSize(150, 40)
        layout.addWidget(self.label_umbral)
        layout.addWidget(self.spin_umbral)

        self.label_dist = QLabel("Distancia mínima \n entre picos:")
        self.label_dist.setFont(QFont("Arial", weight=QFont.Bold))
        self.spin_dist = QSpinBox()
        self.spin_dist.setRange(1, 2000)
        self.spin_dist.setValue(40)
        self.spin_dist.setFixedSize(150, 40)
        layout.addWidget(self.label_dist)
        layout.addWidget(self.spin_dist)
        layout.addStretch()
        
        # Conectar cambios de parámetros al debouncing para PosicionamientoInicial
        self.spin_umbral.valueChanged.connect(self.analizar_imagen_con_debouncing)
        self.spin_dist.valueChanged.connect(self.analizar_imagen_con_debouncing)

        # Primero crea el layout vertical
        botones_vertical = QVBoxLayout()
        self.analizar = QPushButton("Analizar")
        self.analizar.setFixedSize(100, 40)
        botones_vertical.addWidget(self.analizar)
        self.analizar.clicked.connect(self.analizar_imagen)

        """self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.setFixedSize(100, 40)
        self.boton_guardar.setStyleSheet("background-color: rgb(181, 212, 0); color: white; border-radius: 10px;")
        botones_vertical.addWidget(self.boton_guardar)

        self.boton_guardar.clicked.connect(self.guardar_datos)"""

        # Agrega el layout vertical de botones al layout horizontal principal
        layout.addLayout(botones_vertical)

        return layout  # <-- Devuelve el layout

    def analizar_imagen(self) -> Optional[str]:
        """
        Crea el layout para subir imágenes, analizar y llama la función de análisis.
        Implementa caché de resultados y manejo optimizado de errores.
        """
        ##logger.info("Iniciando análisis de posicionamiento inicial")

        if not self.imagen_path:
            self._mostrar_error_usuario("Advertencia", "Primero selecciona una imagen.")
            return None

        try:
            # Configurar interfaz si es necesario (lazy loading)
            if getattr(self, 'parametros_layout', None) is None:
                self._configurar_interfaz_analisis()

            # Obtener parámetros
            umbral = self.spin_umbral.value()
            distancia = self.spin_dist.value()

            # Validación rápida antes del procesamiento
            if not optimizador_analisis.validar_imagen_rapida(self.imagen_path):
                self._mostrar_error_usuario("Error de Imagen", "La imagen seleccionada no es válida o está corrupta.")
                return None

            # Pre-cargar dependencias si es necesario
            optimizador_analisis.precargar_dependencias()
            
            # Ejecutar análisis optimizado de posicionamiento
            #print(f"📸 Procesando imagen de posicionamiento: {self.imagen_path}")
            resultado = self._ejecutar_analisis_posicionamiento_optimizado(umbral, distancia)

            if resultado:
                self.mostrar_texto_ini(resultado)
                self._asegurar_toolbar_posicionamiento()
                return resultado

        except Exception as e:
            #logger.error(f"Error en análisis de posicionamiento: {e}")
            self._mostrar_error_usuario("Error de Análisis", f"No se pudo analizar la imagen: {str(e)}")
        return None
    
    def _configurar_interfaz_analisis(self):
        """Configura la interfaz de análisis de forma lazy"""
        self.parametros_layout = self._crear_parametros()
        self.layout_imagen.addLayout(self.parametros_layout)

        self.boton_ayuda = QPushButton("?")
        self.boton_ayuda.setToolTip("Presione para ver ayuda sobre los parámetros.") 
        self.setStyleSheet("""
            QToolTip {
                background-color: rgba(177, 241, 251, 0.64);
                color: black;
                border: 1px solid white;
                font-size: 14px;
            }
        """)
        
        self.boton_ayuda.clicked.connect(self.mostrar_ayuda_parametros)
        self.botones_layout.addWidget(self.boton_ayuda)
    
    def _ejecutar_analisis_posicionamiento_optimizado(self, umbral: float, distancia: int) -> Optional[str]:
        """Ejecuta análisis optimizado de posicionamiento sin caché innecesario"""
        try:
            
            # Ejecutar análisis con imagen optimizada si está disponible
            return analizar_lineas(
                imagen_path=self.imagen_path,
                metodo=True,
                fila_especifica=None,
                umbral_relativo=umbral,
                distancia_minima=distancia,
                mostrar=True,
                filtro="clahe",
                canvas=self.canvas
            )
        except Exception as e:
            print(f"Error ejecutando análisis de posicionamiento: {e}")
            return None
    
    def _asegurar_toolbar_posicionamiento(self):
        """Asegura que la toolbar esté visible para posicionamiento"""
        if not hasattr(self, 'toolbar') or self.toolbar is None:
            mpl = get_matplotlib_components()
            NavigationToolbar = mpl['NavigationToolbar']
            self.toolbar = NavigationToolbar(self.canvas, self)
            self.col2.addWidget(self.toolbar)
        elif self.col2.indexOf(self.toolbar) == -1:
            self.col2.addWidget(self.toolbar)
    
    def analizar_imagen_con_debouncing(self):
        """Análisis con debouncing para ajustes de parámetros en PosicionamientoInicial"""
        if not hasattr(self, 'imagen_path') or not self.imagen_path:
            return
        
        # Cancelar análisis anterior si está en progreso
        if hasattr(self, '_timer_analisis'):
            self._timer_analisis.stop()
        
        # Timer para evitar análisis excesivos al cambiar parámetros
        self._timer_analisis.start(500)  # 500ms de delay
    
    def _ejecutar_analisis_diferido(self):
        """Ejecuta el análisis después del debouncing para posicionamiento"""
        resultado = self.analizar_imagen()
        return resultado

    def mostrar_texto_ini(self, resultado):
        """
        Extrae y muestra solo los desplazamientos, promedio y desviación estándar del resultado HTML generado.
        """

        # Paso 1: limpiar interfaz como en mostrar_texto
        toolbar = getattr(self, 'toolbar', None)
        for i in reversed(range(self.col2.count())):
            item = self.col2.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            # Solo elimina widgets temporales (como QLabel de resultados)
            if widget is not None and widget not in (self.canvas, toolbar):
                self.col2.removeWidget(widget)
                widget.deleteLater()


        # Paso 2: limpiar HTML y extraer valores con regex
        texto_plano = re.sub(r'<[^>]+>', '', resultado)  # quita etiquetas HTML
        texto_plano = html.unescape(texto_plano)              # decodifica caracteres especiales

        # Inicializar
        desplazamientos = "No disponible"
        promedio_des = desviacion_des = None

        try:
            match_despl = re.search(r'Desplazamientos.*?:\s*\[([^\]]+)\]', texto_plano)
            if match_despl:
                desplazamientos = "[" + match_despl.group(1).strip() + "]"
        except Exception as e:
            print("Error al extraer resultados:", e)
            QMessageBox.warning(self, "Error", f"No se pudieron extraer los datos.\n{e}")
            return

        # Paso 3: construir texto para mostrar
        texto = "<pre style='font-family: Segoe UI, monospace; font-size: 20px;'>"
        texto += "<b>                                                              </b>"
        texto += "<b>                                                              </b>\n"
        texto += "<b>Resultados del posicionamiento Inicial de la fuente</b>\n"
        texto += f"<b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Desplazamiento:</b> <span style='font-weight:normal'>{desplazamientos} mm</span><br>\n"
        texto += "</pre>"

        # Paso 4: mostrar en QLabel
        label = QLabel()
        label.setTextFormat(Qt.RichText)
        label.setText(texto)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        label.setWordWrap(True)
        label.setMinimumHeight(70)
        self.resultado_label_ini = label

        # Crear toolbar si no existe
        if not hasattr(self, 'toolbar') or self.toolbar is None:
            mpl = get_matplotlib_components()
            NavigationToolbar = mpl['NavigationToolbar']
            self.toolbar = NavigationToolbar(self.canvas, self)
            for action in self.toolbar.actions():
                if action.text() in ['Customize', 'Subplots']:
                    self.toolbar.removeAction(action)
            self.toolbar.setFixedHeight(25)
            self.toolbar.setStyleSheet("padding: 0px; margin: 0px;")

        for widget in (self.toolbar, label, self.canvas):
            if widget is not None and self.col2.indexOf(widget) == -1:
                self.col2.addWidget(widget)

        # Asegurar visibilidad
        self.toolbar.show()
        self.toolbar.update()
        self.canvas.setVisible(True)
        self.canvas.show()
        self.canvas.update()
        self.widgetgrafica.update()

    """ Guarda los datos analizados en la base de datos SQLite                                                                                                                                      """
    def guardar_datos_ini(self):
        """
        Extrae el texto de desplazamientos desde self.resultado_label_ini.
        Devuelve: lista de floats (ej: [1.14, 0.76, 0.89]) o None si no se encuentra.
        """
        resultado_html = self.resultado_label_ini.text().strip()
        if not resultado_html:
            QMessageBox.warning(self, "Advertencia", "No hay resultado para extraer.")
            return None

        try:
            texto = re.sub(r'<[^>]+>', '', resultado_html)
            texto = html.unescape(texto)
            match = re.search(r'Desplazamiento.*?:\s*\[([^\]]+)\]', texto)
            if match:
                numeros_str = match.group(1).strip()  # "1.14, 0.76, 0.89"
                desplazamientos = [float(x.strip()) for x in numeros_str.split(",")]
                print("Desplazamientos extraídos:", desplazamientos)
                return desplazamientos
            else:
                return None
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"No se pudo extraer el desplazamiento.\nError: {e}")
            return None

    """ Carga y muestra los resultados guardados en la base de datos SQLite en una tabla en col2                                                                                                    """
    def cargar_y_mostrar_resultados(self):
        # Quitar el canvas si está en el layout
        if self.canvas is not None and self.col2.indexOf(self.canvas) != -1:
            self.col2.removeWidget(self.canvas)
            self.canvas.setParent(None)
        # Quitar la toolbar si está
        if hasattr(self, 'toolbar') and self.toolbar is not None and self.col2.indexOf(self.toolbar) != -1:
            self.col2.removeWidget(self.toolbar)
            self.toolbar.setParent(None)
        # Agregar la tabla si no está
        if self.col2.indexOf(self.resultados_table) == -1:
            self.col2.addWidget(self.resultados_table)

        # Llenar la tabla
        conexion = sqlite3.connect("resultados.db")
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM resultados ORDER BY Fecha")
        resultados = cursor.fetchall()
        conexion.close()

        self.resultados_table.setRowCount(len(resultados))

        for row_idx, fila in enumerate(resultados):
            user = str(fila[0])
            fecha = fila[1]
            tipo = fila[2]
            distancias = fila[3].replace("\\n", " ").replace("\n", " ")
            promedio = str(fila[4]) if fila[4] is not None else ""
            desviacion = str(fila[5]) if fila[5] is not None else ""
            imagen_path = fila[6] if len(fila) > 6 else ""

            self.resultados_table.setItem(row_idx, 0, QTableWidgetItem(user))
            self.resultados_table.setItem(row_idx, 1, QTableWidgetItem(fecha))
            self.resultados_table.setItem(row_idx, 2, QTableWidgetItem(tipo))
            self.resultados_table.setItem(row_idx, 3, QTableWidgetItem(distancias))
            self.resultados_table.setItem(row_idx, 4, QTableWidgetItem(promedio))
            self.resultados_table.setItem(row_idx, 5, QTableWidgetItem(desviacion))
            self.resultados_table.setItem(row_idx, 6, QTableWidgetItem(imagen_path))
        self.resultados_table.resizeColumnsToContents()

        if self.col2.indexOf(self.boton_volver) == -1:
            self.col2.addWidget(self.boton_volver)
        if self.col2.indexOf(self.boton_eliminar) == -1:
            self.col2.addWidget(self.boton_eliminar)

    """ Elimina una fila seleccionada de la tabla de resultados                                                                                                                                     """
    def eliminar_fila_resultado(self):
        fila_seleccionada = self.resultados_table.currentRow()
        if fila_seleccionada == -1:
            QMessageBox.warning(self, "Advertencia", "Selecciona una fila para eliminar.")
            return

        id_item = self.resultados_table.item(fila_seleccionada, 0)
        if not id_item:
            QMessageBox.warning(self, "Advertencia", "No se pudo obtener el ID de la fila.")
            return

        id_fila = id_item.text()
        respuesta = QMessageBox.question(self, "Confirmar", f"¿Seguro que deseas eliminar la fila con ID {id_fila}?",
                                        QMessageBox.Yes | QMessageBox.No)
        if respuesta == QMessageBox.Yes:
            conexion = sqlite3.connect("resultados.db")
            cursor = conexion.cursor()
            cursor.execute("DELETE FROM resultados WHERE id = ?", (id_fila,))
            conexion.commit()
            conexion.close()
            self.cargar_y_mostrar_resultados()  # Refresca la tabla

    """ Muestra el canvas de matplotlib y la toolbar si están disponibles, y quita la tabla de resultados si está presente                                                                          """
    def mostrar_canvas(self):
        # Quitar la tabla si está
        if self.col2.indexOf(self.resultados_table) != -1:
            self.col2.removeWidget(self.resultados_table)
            self.resultados_table.setParent(None)
        # Agregar el canvas si no está
        if self.col2.indexOf(self.canvas) == -1:
            self.col2.addWidget(self.canvas)
        # Agregar la toolbar si la usas
        if hasattr(self, 'toolbar') and self.toolbar is not None and self.col2.indexOf(self.toolbar) == -1:
            self.col2.addWidget(self.toolbar)
        if self.col2.indexOf(self.boton_eliminar) != -1:
            self.col2.removeWidget(self.boton_eliminar)
            self.boton_eliminar.setParent(None)

        if self.col2.indexOf(self.boton_volver) != -1:
            self.col2.removeWidget(self.boton_volver)
            self.boton_eliminar.setParent(None)

    """ Muestra un mensaje de ayuda sobre los parámetros de análisis                                                                                                                                """
    def mostrar_ayuda_parametros(self):
        texto = (
        "<b>Umbral Relativo:</b> Ajusta la sensibilidad del análisis. "
        "Un valor más alto detecta menos picos, "
        "así si la imagen es muy <span style='color:#1976d2;'>oscura</span>.<br>"
        "<span style='color:#1976d2;'>Disminuya el umbral</span> para detectar más picos.<br><br>"
        "<b>Distancia mínima entre picos:</b> Define la separación mínima entre picos detectados.<br>"
        "Si detecta <span style='color:#1976d2;'>demasiados picos</span>, "
        "<span style='color:#1976d2;'>aumente este valor</span> para filtrar los más cercanos."
    )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()

    """ Genera el espacio para graficar, incluyendo el canvas y los menús desplegables                                                                                                              """ 
    def plotter(self, menu):
    
        #Se limpia el espacio paa graficar y se configura
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        #Se abre la base de datos y se encuentra que se va a graficar
        db = self.opeenDatabase()
        selected_chart = menu.currentText()  # QComboBox con tipos de gráfica
        
        if selected_chart == "Seleccione...": #No se si sea necesario pero es para no tneer errores
            return
        
        #Se establecen los limites de l grafica 
        start_date = self.limit1.date().toString('yyyy-MM-dd')
        end_date = self.limit2.date().toString('yyyy-MM-dd')
        
        query = QSqlQuery(db)
        
        selected_column1 = self.graficos_mapeo1.get(selected_chart, None)
        selected_column2 = self.graficos_mapeo2.get(selected_chart, None)

        if selected_column2 in [
            'tol_rep_act_ci',
            'tol_exp_act',
            'tol_cyc_dummy',
            'tol_cyc_rad'
        ]:
            #print("Entro a datos dosimetricos vs tiempo")
            graficarvstiempo(self, query, ax, 'braqui', selected_column2, selected_chart, start_date, end_date)

        elif selected_chart == "Actividad vs tiempo":
            #print("Entro a datos dosimetricos vs tiempo")
            
            query.prepare("""
                SELECT date, tol_rep_act_ci, tol_exp_act
                FROM braqui
                WHERE date BETWEEN :start_date AND :end_date
                ORDER BY date ASC
            """)
            query.bindValue(":start_date", start_date)
            query.bindValue(":end_date", end_date)
            query.exec()

            x_data = []
            y_data1 = []
            y_data2 = []


            while query.next():
                val = query.value(1)
                if val is None or val == '':
                    continue
                x_data.append(query.value(0))  # la fecha
                y_data1.append(float(query.value(1)))  # tol_fot_6mv
                y_data2.append(float(query.value(2)))  # tol_fot_15mv
            
            date = [datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in x_data]

            ax.plot(date, y_data1, marker='o', label='actividad reportada')
            ax.plot(date, y_data2, marker='o', label='actividad esperada')

            self.figure.autofmt_xdate()  # Rotar las fechas para mejor visualización
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Dosis')
            ax.set_title('Actividad reportada vs actividad esperada')
            ax.grid(True)
            ax.legend()
        
        
        elif selected_chart == "Ciclos vs tiempo":
            #print("Entro a datos dosimetricos vs tiempo")
            
            query.prepare("""
                SELECT date, 
                tol_cyc_dummy,tol_cyc_rad
                FROM braqui
                WHERE date BETWEEN :start_date AND :end_date
                ORDER BY date ASC
            """)
            query.bindValue(":start_date", start_date)
            query.bindValue(":end_date", end_date)
            query.exec()

            x_data = []
            y_data1 = []
            y_data2 = []


            while query.next():
                val = query.value(1)
                if val is None or val == '':
                    continue
                x_data.append(query.value(0))  # la fecha
                y_data1.append(float(query.value(1)))  # tol_fot_6mv
                y_data2.append(float(query.value(2)))  # tol_fot_15mv
            
            date = [datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in x_data]

            ax.plot(date, y_data1, marker='o', label='Ciclos del dummy')
            ax.plot(date, y_data2, marker='o', label='Ciclos de la fuente')

            self.figure.autofmt_xdate()  # Rotar las fechas para mejor visualización
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Dosis')
            ax.set_title('Ciclos del dummy vs ciclos de la fuente')
            ax.grid(True)
            ax.legend()        

        elif selected_column1 in [
            'int_con_box', 'emerg_con', 'blq_puerta',
            'pos_fuente', 'res_fuente', 'key_fuente',
            'mon_area', 'lum_puerta', 'tub_guia',
            'visual_sys', 'intercom', 'mon_rad_port'
        ]:
            
            graficarvstiempo(self, query, ax, 'braqui', selected_column1, selected_chart, start_date, end_date, True)
        
        # Redibuja en el canvas
        self.canvas.draw()
        db.close()
    
    def cleanup_recursos(self):
        """Limpia recursos de PosicionamientoInicial"""
        #logger.info("Limpiando recursos de PosicionamientoInicial")
        try:
            # Limpiar tabla de resultados
            if hasattr(self, 'resultados_table') and self.resultados_table:
                self.resultados_table.clearContents()
                self.resultados_table.deleteLater()
            
            # Limpiar canvas y figuras
            if hasattr(self, 'canvas') and self.canvas:
                try:
                    self.canvas.figure.clear()
                except:
                    pass
            
            # Limpiar toolbar
            if hasattr(self, 'toolbar') and self.toolbar:
                try:
                    self.toolbar.deleteLater()
                    self.toolbar = None
                except:
                    pass
            #print("Recursos de PosicionamientoInicial limpiados")
        except Exception as e:
            print(f"Error limpiando recursos de PosicionamientoInicial: {e}")
    
    def _mostrar_error_usuario(self, titulo: str, mensaje: str):
        """Muestra errores al usuario de forma consistente"""
        print(f"{titulo}: {mensaje}")
        try:
            QMessageBox.warning(self, titulo, mensaje)
        except Exception as e:
            print(f"Error mostrando mensaje al usuario: {e}")
    
    def _ejecutar_busqueda_filtrada(self):
        """Ejecuta búsqueda filtrada después del debouncing"""
        try:
            if hasattr(self, 'search_bar') and hasattr(self, 'filtrarTabla'):
                texto_busqueda = self.search_bar.text()
                print(f"Ejecutando búsqueda filtrada: {texto_busqueda}")
                self.filtrarTabla()
        except Exception as e:
            print(f"Error en búsqueda filtrada: {e}")
    
    def _iniciar_busqueda_debounced(self):
        """Inicia búsqueda con debouncing para evitar búsquedas excesivas"""
        self._timer_busqueda.stop()
        self._timer_busqueda.start(300)  # 300ms de delay
    
    def __del__(self):
        """Destructor para limpieza automática"""
        try:
            self.cleanup_recursos()
        except:
            pass

