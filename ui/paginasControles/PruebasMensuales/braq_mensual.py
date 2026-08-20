from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QGridLayout, QDialog, QTableWidgetItem, QPushButton, 
                            QToolBox, QSplitter, QLineEdit, QComboBox, QMessageBox, QDateTimeEdit, QDateEdit)
from PyQt5.QtCore import Qt, QDate, QDateTime
from PyQt5.QtGui import QColor
from PyQt5.QtSql import QSqlQuery
from models.PDF.Mensuales.reportes_mensuales import guardarPDF_mensual
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from data.ManejoDatos.load import (mostrar_db_mensualBraqui, verificar_editar, verificar_eliminar, guardarEdicion,
                                    cancelarEdicion, guardar_resultado_CambioFuente, encontrar_columnas)
from data.ManejoDatos.conection import Conexion
from services.equipos_service import EquiposService
from services.etiqueta_equipo import etiqueta_equipo
from services.vigencia_equipo import es_vigente_en_fecha
from analisisImagenes.ActividadFuente import  *
from resources.utils.matplotlib_lazy import get_matplotlib_components
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_ACTUALIZAR
from services.anulacion import filtro_activo
import traceback

class PruebaMensualBraq(PruebaBasico):
    def __init__(self, user_id):
        #print("PruebaMensualBraq      __init__ called")
        super(PruebaMensualBraq, self).__init__()
        self.resultados_table = QTableWidget()
        self.resultados_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.observaciones_db()
        self.user_id = user_id
        self.desplazamiento_ini = None  # Aquí se almacena
        self.ref_bd = None  # ID de la sesión en la BD
        self.initDATA(user_id)
        self.initUI()
        self.cargar_datos_equipos()
        self.button_click()
        mostrar_db_mensualBraqui(self)
        self.normalizar_fechas_db()
        

        from ui.paginasControles.PruebasDiarias.braquiterapia import PosicionamientoInicial
        # Crear instancia de PosicionamientoInicial
        self.posicionamiento = PosicionamientoInicial(self.user_id)
        self.posicionamiento.desplazamientoReady.connect(self.actualizar_desplazamiento)
        
        #print(f"\n📌 Posicionamiento conectado desde: {id(self.posicionamiento)}")

    """ Conectar la señal de actualización de desplazamiento                                                                                                                                                       """
    def normalizar_fechas_db(self):
        conn = Conexion().conectar()
        cursor = conn.cursor()
        tablas_normalizar = ['ResultadosActividad', 'TipoCalibracion', 'SistemaMedicion', 'CondicionesMedicion', 'MaximosCamaras', 'LecturasMaximos']
        try:
            for tabla in tablas_normalizar:
                cursor.execute(f"""
                    UPDATE {tabla}
                    SET fecha =
                        SUBSTR(fecha, 7, 4) || '-' ||
                        SUBSTR(fecha, 4, 2) || '-' ||
                        SUBSTR(fecha, 1, 2) ||
                        SUBSTR(fecha, 11)
                    WHERE fecha LIKE '__-__-____ %'
                """)

            conn.commit()

            print(f"Fechas normalizadas: {cursor.rowcount}")

        except Exception as e:
            traceback.print_exc()
            print("Error normalizando fechas:", e)

        finally:
            conn.close()
    def actualizar_desplazamiento(self, valor):
        print(f"Desplazamiento recibido: {valor}")
        try:
            if isinstance(valor, list) and len(valor) > 0:
                self.desplazamiento_ini = float(valor[0])
            elif isinstance(valor, (float, int)):
                self.desplazamiento_ini = float(valor)
            else:
                raise ValueError("Formato de desplazamiento inválido")

            print("llamando a guardar_DB")
            self.actualizar_desplazamiento_en_db(self.desplazamiento_ini)

        except (ValueError, TypeError) as e:
            traceback.print_exc()
            print(f"Valor de desplazamiento inválido: {e}")

    """ Actualiza el desplazamiento en la base de datos                                                                                                                                                                 """
    def actualizar_desplazamiento_en_db(self, desplazamiento):
        print(f"ref existe: {hasattr(self, 'ref')}")
        print(f"ref_bd existe: {hasattr(self, 'ref_bd')}")
        print(f"ref_bd valor: {getattr(self, 'ref_bd', 'NO EXISTE')}")
        print(f"⏎ Actualizando desplazamiento_ini en BD: {desplazamiento}")
        if not hasattr(self, "ref") or self.ref_bd is None:
            print(" No hay ID de sesión definido.")
            return

        conn = Conexion().conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""
                UPDATE CondicionesMedicion
                SET desplazamiento_ini = ?
                WHERE ref = ?{filtro_activo('CondicionesMedicion')}
            """, (str(desplazamiento), self.ref_bd))
            conn.commit()
            print("Desplazamiento actualizado en base de datos.")
            # A6.6 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): sin auditar
            # hasta ahora.
            _registrar_auditoria(_usuario_actual(self), ACCION_ACTUALIZAR,
                                 "CondicionesMedicion", ref=self.ref_bd)
            QMessageBox.information(self, "Éxito", "El desplazamiento fue guardado correctamente en la base de datos.")
            

        except Exception as e:
            traceback.print_exc()   
            print("Error al actualizar desplazamiento:", e)
        finally:
            conn.close()

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

    def limpiar_todos_los_campos(self):
        """Limpia los campos de todas las categorías cuando no hay datos para la fecha seleccionada"""
        try:
            # Lista de campos de todas las categorías
            todos_los_campos = [
                # Categoría 1 - TipoCalibracion
                'serie', 'certificado', 'fecha_cer', 'intensidad', 'conversion',
                # Categoría 2 - SistemaMedicion  
                'modelo', 'serie_cp', 'calibracion', 'modelo_elec', 'serie_ele', 'electrometro',
                't0', 'p0', 'h0',
                # Categoría 3 - CondicionesMedicion
                't', 'p', 'h'
            ]
            
            for campo_nombre in todos_los_campos:
                if hasattr(self, campo_nombre):
                    campo = getattr(self, campo_nombre)
                    if hasattr(campo, 'setText'):  # QLineEdit
                        campo.setText("")
                        campo.setReadOnly(False)
                    elif hasattr(campo, 'setCurrentText'):  # QComboBox
                        campo.setCurrentIndex(0)
            
            print("Todos los campos limpiados")
        except Exception as e:
            print(f"Error al limpiar campos: {e}")
    def initDATA(self, user_id):
        self.diccionario_invertido = {
            'pri_cal': ['Primera Calibración', '', 'scatter'],
            'cambio_cal': ['Cambio de fuente', '', 'scatter'],
            'fecha_cal': ['Fecha del control', '', 'line'],
            'serie': ['Número de Serie de la fuente', '', 'line'],
            'certificado': ['Número del Cetficado de la fuente', '', 'line'],
            'fecha_cer': ['Fecha del certificado', '', 'line'], 
            'intensidad' : ['Intensidad de la Fuente', '', 'line'],
            'conversion' : ['Factor de conversión según el certificado', '', 'line'],
            'modelo' : ['Modeo de la cámara', '', 'line'],
            'serie_cp': ['Serie de la cámra de Pozo', '', 'line'],
            'calibracion' : ['Factor de calibración de la cámara de pozo', '', 'line'],
            'modelo_elec' : ['Modelo del electrómetro', '', 'line'],
            'serie_ele' : ['Serie del electrómetro', '', 'line'],
            'electrometro' : ['Factor de calibración del electrómetro', '', 'line'],
            't0' : ['Temperatura de Calibración (°C)', '', 'line'],
            'p0' : ['Presión de Calibración (mmHg)', '', 'line'],
            'h0' : ['Humedad de Calibración (%)', '', 'line'],
            't' : ['Temperatura de Medida (°C)', '', 'line'],
            'p' : ['Presión de Medida (mmHg)', '', 'line'],
            'h' : ['Humedad de Medida (%)', '', 'line'],
            'ref' : ['Actividad de la Fuente en el monitor', '', 'line'],
            'observaciones': ['Observaciones', '', 'line'],

        }
        
        self.init_data(user_id, self.diccionario_invertido)
        

    """ Crea la estructura visual general, usa QToolBox para organizar las secciones y prepara el area de gráficos                                                                                                      """
    def initUI(self):
        #print("\ninitUI de PruebaMensualBraq llamado")
        self.actividad = QLabel("Actividad calculada correctamente")
        self.layout_cambio = QHBoxLayout()

        archivo = 'widgets.xlsx'
        if hasattr(self, 'es_cambio_fuente') and self.es_calibracion_redundante:
            _ = self.setupBox(archivo, 'encabezado_ActividadBraqui')
        else: 
            _ = self.setupBox(archivo, 'encabezado_mensualBraqui')

        self.date_box.setDisplayFormat("dd/MM/yyyy")

        df, n, layouts, _ = self.setupBox(archivo, 'preguntas_mensualBraqui', main=False)
        self.comboBox_equipos()
        self.datos_tabla = self.storeDailyTests(df)

        self.category1 = QWidget()
        self.category2 = QWidget()
        self.category3 = QWidget()
        self.category4 = QWidget()
        self.category5 = QWidget()
        self.category6 = QWidget()

        toolbox = QToolBox()
        self.general_layout.addWidget(toolbox)
        seccion_names = ['category1', 'category2', 'category3', 'category6']
        for cat_name, layout in zip(seccion_names, layouts):
            getattr(self, cat_name).setLayout(layout)
        # for i, layout in enumerate(layouts, 1):
        #     getattr(self, f'category{i}').setLayout(layout)

        if self.category4.layout() is None:
            self.layout_camara = QVBoxLayout()
            self.category4.setLayout(self.layout_camara)
        else:
            self.layout_camara = self.category4.layout()

        if self.category5.layout() is None:
            self.layout_lecturas = QVBoxLayout()
            self.category5.setLayout(self.layout_lecturas)
        else:
            self.layout_lecturas = self.category5.layout()
            
        if self.category6.layout() is None:
            self.layout_observaciones = QVBoxLayout()
            self.category6.setLayout(self.layout_observaciones)
        else:
            self.layout_observaciones = self.category6.layout()
        self.generar_tabla_medidas()
        self.generar_tabla_lecturas()

        toolbox.addItem(self.category1, 'TIPO DE CALIBRACIÓN')
        toolbox.addItem(self.category2, 'SISTEMA DE MEDICIÓN')
        toolbox.addItem(self.category3, "CONDICIONES DE MEDICIÓN")
        toolbox.addItem(self.category4, "MEDIDAS MÁXIMO DE LA CÁMARA")
        toolbox.addItem(self.category5, "LECTURAS DEL MÁXIMO")
        toolbox.addItem(self.category6, "OBSERVACIONES")
        

        _ = self.setupBox(archivo, 'btn')
        self.btn_add.setObjectName("boton_nofunciona")
        self.btn_add.setEnabled(False)
        self.btn_add.setProperty("estado", "noselected")

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
        self.menu_graficar.setFixedWidth(100)
        
        # Crear layout para menús
        caja_menu_graficas = QHBoxLayout()

        # Grupo Fecha
        caja_menu_graficas.addWidget(QLabel("Fecha:"))
        self.date_grafica = QDateEdit()
        self.date_grafica.setMinimumWidth(200)  # Más ancho para la fecha
        self.date_grafica.setCalendarPopup(True)
        self.date_grafica.setDate(QDate.currentDate())
        caja_menu_graficas.addWidget(self.date_grafica)

        # Espaciado entre grupos
        caja_menu_graficas.addSpacing(80)  # Espacio entre Fecha y Gráfico

        # Grupo Gráfico
        caja_menu_graficas.addWidget(QLabel("Gráfico:"))
        caja_menu_graficas.addWidget(self.menu_graficar)
        self.menu_graficar.setMinimumWidth(200)  # Más ancho para el menú de gráficos

        # Añadir stretch al final para empujar todo hacia la izquierda
        #caja_menu_graficas.addStretch()
 
        # Crear widget contenedor
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
        if self.serie.text() is not None:
            self.serie.textChanged.connect(lambda _: self.obtener_fecha_desde_serial(self.serie.text()))
        else:
            pass
        
    def obtener_fecha_desde_serial(self, serie):
        try:
            datos_serie = serie.split("-")
            print(datos_serie)
            lista_datos = []
            conteo = 0
            for i in datos_serie:
                if len(i) == 6:
                    lista_datos.append(i)
            print(lista_datos)
            fecha = datetime.strptime(lista_datos[0].strip(), "%m%d%y")
            self.fecha_cer.setDate(fecha)
        except Exception as e:
            print(e)
            return
        
        
        
    def comboBox_equipos(self):
        #print("comboBox_equipos de Mensual llamado")
        # ----------- CÁMARA DE POZO -----------
        self.combo_modelo = self.widgets['modelo']        # QComboBox cámara de pozo
        self.combo_serie  = self.widgets['serie_cp']      # QComboBox serie cámara de pozo
        self.line_cal     = self.widgets['calibracion']   # QLineEdit calibración
        self.line_cal_elec = self.widgets['electrometro']  # QLineEdit calibración electómetro
        
        # Llenar modelos cámara de pozo (fila actual por vigente, H2.10)
        modelos_pozo = EquiposService.modelos_actuales('Cámara de pozo')
        self.combo_modelo.addItems(modelos_pozo)

        # Conectar señales
        self.combo_modelo.currentTextChanged.connect(self.on_modelo_pozo_cambio)
        self.combo_serie.currentTextChanged.connect(self.on_serie_pozo_cambio)


        # ----------- ELECTRÓMETRO -----------
        self.combo_modelo_elec = self.widgets['modelo_elec']   # QComboBox modelo electómetro
        self.combo_serie_elec  = self.widgets['serie_ele']     # QComboBox serie electómetro
        self.line_cal_elec     = self.widgets['electrometro']  # QLineEdit calibración electómetro

        # Llenar modelos electómetro (fila actual por vigente, H2.10)
        modelos_elec = EquiposService.modelos_actuales('Electrómetro')
        self.combo_modelo_elec.addItems(modelos_elec)

        # Conectar señales
        self.combo_modelo_elec.currentTextChanged.connect(self.on_modelo_elec_cambio)
        self.combo_serie_elec.currentTextChanged.connect(self.on_serie_elec_cambio)

    def on_modelo_pozo_cambio(self, modelo):
        """Cuando seleccionan un modelo de cámara de pozo, llenar las
        series. G10 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md): una
        entrada por CALIBRACIÓN activa, sin colapsar por serie -- antes
        usaba series_actuales/_FILA_ACTUAL (H2.10), que ocultaba la
        calibración de 2022 de A092535 (activa a propósito junto a la de
        2025, doctrina §8.4 de PLAN_F)."""
        self.combo_serie.clear()
        self.combo_serie.addItem("Seleccionar Serie...")

        calibraciones_activas = EquiposService.calibraciones_activas('Cámara de pozo', modelo)

        # F9 (PLAN_F_CIERRE_ESTANDAR_29-07.md §9 punto 5): la vigencia se
        # evalúa contra la fecha del FORMULARIO (self.date_box), no contra
        # hoy -- mismo criterio que el mensual/TAC (V1).
        fecha_referencia = (
            self.date_box.date() if hasattr(self, 'date_box') and self.date_box
            else QDate.currentDate()
        )
        for eq_id, serie, fecha_calibr, equip_type in calibraciones_activas:
            equipo = {"id": eq_id, "serie": serie, "fecha_calibr": fecha_calibr,
                      "equip_type": equip_type}
            texto, _ = etiqueta_equipo(equipo, fecha_referencia)
            self.combo_serie.addItem(texto, eq_id)
            if not es_vigente_en_fecha(fecha_calibr, equip_type, fecha_referencia):
                item = self.combo_serie.model().item(self.combo_serie.count() - 1)
                item.setForeground(QColor(255, 0, 0))  # Texto rojo, sin símbolos
                item.setToolTip("Calibración vencida - Requiere recalibración")

    def on_serie_pozo_cambio(self):
        """Cuando seleccionan serie de cámara de pozo, llenar valores de
        calibración. G10: resuelve por el ID guardado en `currentData()`,
        nunca por texto -- una serie puede tener varias calibraciones
        activas (A092535: 2022 y 2025)."""
        equipo_id = self.combo_serie.currentData()
        if equipo_id is None:
            return

        datos = EquiposService.obtener_por_id(equipo_id)
        if datos:
            calibr_fact = datos["calibr_fact"]
            t_cal, p_cal, h_cal = datos["t_cal"], datos["p_cal"], datos["h_cal"]
            p_cal = round(float(p_cal)*7.50062,2)
            self.line_cal.setText(str(calibr_fact))
            self.t0.setText(str(t_cal))
            self.p0.setText(str(p_cal))
            self.h0.setText(str(h_cal))

    def on_modelo_elec_cambio(self, modelo):
        """Cuando selecciona un modelo de electrómetro, llenar las series.
        G10: una entrada por calibración activa, mismo criterio que
        on_modelo_pozo_cambio."""
        self.combo_serie_elec.clear()
        self.combo_serie_elec.addItem("Seleccionar Serie...")

        calibraciones_activas = EquiposService.calibraciones_activas('Electrómetro', modelo)

        fecha_referencia = (
            self.date_box.date() if hasattr(self, 'date_box') and self.date_box
            else QDate.currentDate()
        )
        for eq_id, serie, fecha_calibr, equip_type in calibraciones_activas:
            equipo = {"id": eq_id, "serie": serie, "fecha_calibr": fecha_calibr,
                      "equip_type": equip_type}
            texto, _ = etiqueta_equipo(equipo, fecha_referencia)
            self.combo_serie_elec.addItem(texto, eq_id)
            if not es_vigente_en_fecha(fecha_calibr, equip_type, fecha_referencia):
                item = self.combo_serie_elec.model().item(self.combo_serie_elec.count() - 1)
                item.setForeground(QColor(255, 0, 0))  # Texto rojo, sin símbolos
                item.setToolTip("Calibración vencida - Requiere recalibración")

    def on_serie_elec_cambio(self):
        """Cuando seleccionan serie de electrómetro, llenar factor de
        calibración. G10: resuelve por el ID en `currentData()`, nunca por
        texto (mismo criterio que on_serie_pozo_cambio)."""
        equipo_id = self.combo_serie_elec.currentData()
        if equipo_id is None:
            return

        datos = EquiposService.obtener_por_id(equipo_id)
        if datos:
            self.line_cal_elec.setText(str(datos["calibr_fact"]))

    """Crea la tabla en la que se puede ingresar las medidas de los máximos de la cámara                                                                                                                                """
    def generar_tabla_medidas(self):
        try:
            ncam = 10
        except ValueError:
            return  

        if hasattr(self, 'tabla_medidas_widget'):
            self.tabla_medidas_widget.setParent(None)

        grid = QGridLayout()

        titulos = ["Posiciones (mm)", "Medida 1 (nA)", "Medida 2 (nA)", "Promedio (nA)"]
        posiciones = ["127.5", "127", "126.5", "126", "125.5", "125", "124.5", "124", "123.5", "123"]

        self.campos_maximos = []

        for col, titulo in enumerate(titulos):
            encabezado = QLineEdit(titulo)
            encabezado.setReadOnly(True)
            encabezado.setAlignment(Qt.AlignCenter)
            encabezado.setFixedWidth(130)
            encabezado.setStyleSheet("border: 1px solid #c1df08; border-radius: 10px; background-color: rgb(234, 244, 167);")
            grid.addWidget(encabezado, 0, col)

        for fila in range(ncam):
            fila_campos = []

            # Posición
            posicion = QLineEdit(posiciones[fila])
            posicion.setAlignment(Qt.AlignCenter)
            posicion.setFixedWidth(130)
            posicion.setReadOnly(True)
            posicion.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px; background-color: #f0f0f0;")
            grid.addWidget(posicion, fila + 1, 0)
            fila_campos.append(posicion)

            for col in range(2):  # Medidas 1 y 2
                entrada = QLineEdit()
                entrada.setAlignment(Qt.AlignCenter)
                entrada.setFixedWidth(130)
                entrada.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px;")
                grid.addWidget(entrada, fila + 1, col + 1)
                fila_campos.append(entrada)

                def avanzar_foco(f=entrada, r=fila, c=col):
                    def handler():
                        if r + 1 < ncam:
                            self.campos_maximos[r + 1][c + 1].setFocus()
                    return handler

                entrada.returnPressed.connect(avanzar_foco())

            # Promedio
            promedio = QLineEdit("-")
            promedio.setReadOnly(True)
            promedio.setAlignment(Qt.AlignCenter)
            promedio.setFixedWidth(130)
            promedio.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px; background-color: #f0f0f0;")
            grid.addWidget(promedio, fila + 1, 3)
            fila_campos.append(promedio)

            self.campos_maximos.append(fila_campos)

        boton_ok = QPushButton("Ok")
        boton_ok.setStyleSheet("border: 1px solid #c1df08; background-color: rgb(234, 244, 167); color:black;")
        boton_ok.setFixedWidth(60)
        grid.addWidget(boton_ok, ncam + 1, 0)

        boton_ok.clicked.connect(self.extraer_datos_medidas)

        contenedor = QWidget()
        contenedor.setLayout(grid)
        self.layout_camara.addWidget(contenedor)
        self.tabla_medidas_widget = contenedor

    """Crea la tabla en la que se puede ingresar las lecturas de los máximos                                                                                                                                            """
    def generar_tabla_lecturas(self):
        if hasattr(self, 'tabla_lecturas_widget'):
            self.tabla_lecturas_widget.setParent(None)

        grid = QGridLayout()
        grid.setVerticalSpacing(2)
        grid.setHorizontalSpacing(5)
        grid.setContentsMargins(0, 0, 0, 0)

        titulos = ["Voltaje (V)", "Medida 1 (A)", "Medida 2 (A)", "Medida 3 (A)", "Promedio (A)"]
        voltajes = ["300", "150", "-300"]

        self.campos_lecturas = []

        # Encabezados
        for col, titulo in enumerate(titulos):
            encabezado = QLineEdit(titulo)
            encabezado.setReadOnly(True)
            encabezado.setAlignment(Qt.AlignCenter)
            encabezado.setFixedWidth(130)
            encabezado.setStyleSheet(
                "border: 1px solid #c1df08; border-radius: 10px; "
                "background-color: rgb(234, 244, 167);"
            )
            grid.addWidget(encabezado, 0, col)

        # Filas de voltajes + medidas
        for fila in range(3):
            fila_campos = []

            # Voltaje editable con valor predeterminado
            voltaje = QLineEdit()
            voltaje.setText(voltajes[fila])   # valor inicial
            voltaje.setAlignment(Qt.AlignCenter)
            voltaje.setReadOnly(True)
            voltaje.setFixedWidth(130)
            voltaje.setStyleSheet(
                "border: 1px solid #4a8892; border-radius: 10px; "
                "background-color: #ffffff;"   # blanco para indicar editable
            )
            grid.addWidget(voltaje, fila + 1, 0)
            fila_campos.append(voltaje)

            # Medidas (3 columnas)
            for col in range(3):
                entrada = QLineEdit()
                entrada.setAlignment(Qt.AlignCenter)
                entrada.setFixedWidth(130)
                entrada.setStyleSheet("border: 1px solid #4a8892; border-radius: 10px;")
                grid.addWidget(entrada, fila + 1, col + 1)
                fila_campos.append(entrada)

                def avanzar_foco(f=entrada, r=fila, c=col):
                    def handler():
                        if r + 1 < 3:
                            self.campos_lecturas[r + 1][c + 1].setFocus()
                    return handler

                entrada.returnPressed.connect(avanzar_foco())

            # Promedio (solo lectura)
            promedio = QLineEdit("-")
            promedio.setReadOnly(True)
            promedio.setAlignment(Qt.AlignCenter)
            promedio.setFixedWidth(130)
            promedio.setStyleSheet(
                "border: 1px solid #4a8892; border-radius: 10px; "
                "background-color: #f0f0f0;"
            )
            grid.addWidget(promedio, fila + 1, 4)
            fila_campos.append(promedio)

            self.campos_lecturas.append(fila_campos)

        # Botón Aceptar
        self.aceptar = QPushButton("Ok")
        self.aceptar.setStyleSheet(
            "border: 1px solid #c1df08; background-color: rgb(234, 244, 167); color:black;"
        )
        self.aceptar.setFixedWidth(60)
        grid.addWidget(self.aceptar, 4, 0)

        self.aceptar.clicked.connect(self.extraer_datos_lecturas)
        self.aceptar.clicked.connect(self.Calculo_Actividad)

        contenedor = QWidget()
        contenedor.setLayout(grid)
        self.layout_lecturas.addWidget(contenedor)
        self.tabla_lecturas_widget = contenedor

    def clean_info(self, imagenes=False):
        """Z7 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): campos_maximos
        (MEDIDAS MÁXIMO DE LA CÁMARA) y campos_lecturas (LECTURAS DEL
        MÁXIMO) se crean con QLineEdit crudos en generar_tabla_medidas/
        generar_tabla_lecturas -- fuera de self.df_lines (que solo cubre lo
        que viene de widgets.xlsx) -- así que 'Limpiar datos' nunca los
        tocaba. Se limpian solo las celdas EDITABLES (las medidas); las
        columnas de posición/voltaje son etiquetas de referencia fijas
        (estado de fábrica desde la construcción de la tabla, no dato del
        físico) y el promedio vuelve a "-", su valor de fábrica."""
        super().clean_info(imagenes)
        for fila in getattr(self, "campos_maximos", []):
            # [posición(RO), medida1, medida2, promedio(RO)]
            fila[1].clear()
            fila[2].clear()
            fila[3].setText("-")
        for fila in getattr(self, "campos_lecturas", []):
            # [voltaje(RO), medida1, medida2, medida3, promedio(RO)]
            fila[1].clear()
            fila[2].clear()
            fila[3].clear()
            fila[4].setText("-")

    """Extrae la info ingresada en la tabla de los máximos de la cámara                                                                                                                                                 """
    def extraer_datos_medidas(self):
        posiciones = []
        medida1 = []
        medida2 = []
        promedios = []

        if not hasattr(self, 'campos_maximos'):
            return

        for fila in self.campos_maximos:
            try:
                d = float(fila[0].text())     # Posición
                m1 = float(fila[1].text())    # Medida 1
                m2 = float(fila[2].text())    # Medida 2
                prom = (m1 + m2) / 2
            except ValueError:
                continue

            posiciones.append(d)
            medida1.append(m1)
            medida2.append(m2)
            promedios.append(prom)
            # Mostrar el promedio en la tabla
            fila[3].setText(f"{prom:.2f}")  # Mostrar en campo promedio

        graficar_resultados(self.canvas, posiciones=posiciones, promedio=promedios)

        return posiciones, medida1, medida2, promedios

    """Extrae la info ingresada en la tabla de las lecturas de los máximos                                                                                                                                               """
    def extraer_datos_lecturas(self):
        """
        Extrae datos de la tabla de lecturas:
        - Obtiene el voltaje de cada fila (columna 0).
        - Obtiene las 3 medidas asociadas.
        - Calcula y muestra el promedio.
        - Devuelve un diccionario con voltajes como claves.
        """

        datos = {}  # {voltaje: {"medidas": [...], "promedio": valor}}

        if not hasattr(self, 'campos_lecturas'):
            return datos

        for fila in self.campos_lecturas:
            try:
                voltaje = float(fila[0].text())  # voltaje editable
                v1 = float(fila[1].text())
                v2 = float(fila[2].text())
                v3 = float(fila[3].text())
                promedio = (v1 + v2 + v3) / 3
            except ValueError:
                continue  # salta si alguna celda está vacía

            # Mostrar promedio en la columna 4
            fila[4].setText(f"{promedio:.2e}")

            # Guardar en el diccionario
            datos[voltaje] = {
                "medidas": [v1, v2, v3],
                "promedio": promedio
            }
        return datos

    """Llama a la función que calcula la actividad de la fuente y la grafica                                                                                                                                             """
    def Calculo_Actividad(self):
        # Extrae datos de lecturas (diccionario con voltajes dinámicos)
        datos_lecturas = self.extraer_datos_lecturas()
        if len(datos_lecturas) < 3:
            QMessageBox.warning(self, "Advertencia", "Faltan valores para calcular la actividad.")
            return

        # Identificar voltajes
        positivos = [v for v in datos_lecturas.keys() if v > 0]
        negativos = [v for v in datos_lecturas.keys() if v < 0]

        if not positivos or not negativos:
            QMessageBox.warning(self, "Advertencia", "Se requieren voltajes positivos y negativos para calcular la actividad.")
            return

        voltaje_alto = max(positivos)   # Ej. 300 o 250
        voltaje_bajo = min(positivos)   # Ej. 150 o 100
        voltaje_neg  = max(negativos)   # Ej. -300 o -250

        V_alto_prom = datos_lecturas[voltaje_alto]["promedio"]
        print(f"Voltaje alto, nA prom: {V_alto_prom}" )
        V_bajo_prom = datos_lecturas[voltaje_bajo]["promedio"]
        print(f"Voltaje bajo, nA prom: {V_bajo_prom}" )
        V_neg_prom  = datos_lecturas[voltaje_neg]["promedio"]

        # Extrae datos de medidas (para graficar)
        posiciones, medida1, medida2, promedios = self.extraer_datos_medidas()
        if not posiciones or not promedios:
            QMessageBox.warning(self, "Advertencia", "Faltan datos de la tabla de medidas máximas.")
            return

        try:
            t = float(self.t.text())
            p = float(self.p.text())
            t0 = float(self.t0.text())
            p0 = float(self.p0.text())
            calibracion_camara = float(self.calibracion.text())
            calibracion_electrometro = float(self.electrometro.text())
            conversion = float(self.conversion.text())
            intensidad = float(self.intensidad.text())
            fecha_cer = self.fecha_cer.dateTime().toString("yyyy-MM-dd HH:mm:ss")
            fecha_cal = self.fecha_cal.dateTime().toString("yyyy-MM-dd HH:mm:ss")
            ref = float(self.ref.text())
        except ValueError:
            QMessageBox.warning(self, "Advertencia", "Faltan datos numéricos para el cálculo.")
            return

        reporte = CalcularActividad(
            V_alto_prom, V_neg_prom, V_bajo_prom,
            t, p, t0, p0,
            calibracion_camara, calibracion_electrometro,
            conversion, ref, intensidad, fecha_cer, fecha_cal
        )
        graficar_resultados(self.canvas, posiciones=posiciones, promedio=promedios)
        self.mostrar_resultados_actividad(reporte)

    """Muestra los resultados en el área de gráficos en formato HTML                                                                                                                                                    """
    def mostrar_resultados_actividad(self, texto_lines):
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
                "<pre style='font-family: Segoe UI, monospace; font-size: 20px; font-weight: normal;'>"
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
        label.setMinimumHeight(150)
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

    """Guarda los datos en la base de datos, maneja errores y muestra mensajes de éxito o error                                                                                                                         """
    def guardar_DB(self):
        print(f"Entra a guardar_DB en {self.__class__.__name__}")

        try:
            # Determinar tipo de control
            if hasattr(self, 'pri_cal') and self.pri_cal.isChecked():
                tipo = "Control Mensual"
                print("Control mensual")
            elif hasattr(self, 'cambio_cal') and self.cambio_cal.isChecked():
                print(" Cambio de fuente ")
                tipo = "Cambio de fuente"
            elif hasattr(self, 'es_calibracion_redundante') and self.es_calibracion_redundante:
                tipo = "Calibración Redundante"
            else:
                
                tipo = "Cambio de fuente"
                print(tipo)

            # Datos de calibración
            serie = self.serie.text()
            certificado = self.certificado.text()
            
            fecha_cer = self.fecha_cer.text()
            intensidad = float(self.intensidad.text())
            conversion = float(self.conversion.text())

            # Sistema de medición
            if not hasattr(self, "modelo"):
                raise AttributeError("El campo 'modelo' no fue creado. Revisa tu setupBox, tu Excel y la inicialización de la interfaz.")
            modelo = self.modelo.currentText()
            serie_cp = self.serie_cp.currentText()
            calibracion = float(self.calibracion.text())
            serie_cp = self._limpiar_serie(self.serie_cp.currentText())
            serie_ele = self._limpiar_serie(self.serie_ele.currentText())
            modelo_elec = self.modelo_elec.currentText()
            electrometro = float(self.electrometro.text())
            t0 = float(self.t0.text())
            p0 = round(float(self.p0.text()))
            h0 = float(self.h0.text())
            t = float(self.t.text())
            p = float(self.p.text())
            h = float(self.h.text())
            observaciones = self.observaciones.text()

            fecha_cal = str(self.fecha_cal.dateTime().toString("yyyy-MM-dd HH:mm:ss"))

            # Datos de medida
            posiciones, medida1, medida2, promedios = self.extraer_datos_medidas()
            posiciones = [round(p, 3) for p in posiciones]
            medida1 = [round(m, 3) for m in medida1]
            medida2 = [round(m, 3) for m in medida2]
            promedios = [round(p, 3) for p in promedios]

            datos_lecturas = self.extraer_datos_lecturas()

            positivos = [v for v in datos_lecturas.keys() if v > 0]
            negativos = [v for v in datos_lecturas.keys() if v < 0]

            voltaje_alto = max(positivos)
            voltaje_bajo = min(positivos)
            voltaje_neg  = max(negativos)

            V_alto = datos_lecturas[voltaje_alto]["medidas"]
            V_bajo = datos_lecturas[voltaje_bajo]["medidas"]
            V_neg  = datos_lecturas[voltaje_neg]["medidas"]

            V_alto_prom = datos_lecturas[voltaje_alto]["promedio"]
            V_bajo_prom = datos_lecturas[voltaje_bajo]["promedio"]
            V_neg_prom  = datos_lecturas[voltaje_neg]["promedio"]

            # Cálculos de factores
            Ks, Kp, Ktp = factores_correccion(V_alto_prom, V_neg_prom, V_bajo_prom, t, p, t0, p0)

            Ks = round(Ks, 3)
            Kp = round(Kp, 3)
            Ktp = round(Ktp, 3)

            actividad_monitor = float(self.ref.text())
            actividad_calculada = round(actividad_fuente(Ks, Kp, Ktp, calibracion, electrometro, conversion, V_alto_prom), 3)
            actividad_decaimiento = round(calcular_decaimiento(fecha_cer, fecha_cal, intensidad, vida_media_dias=74.2), 3)
            usuario = self.user_id._nombre

            if tipo == 'Cambio de fuente':
                desplazamiento_ini = getattr(self, 'desplazamiento_ini', None)
            else:
                desplazamiento_ini = "No Aplica"

            print(f"Desplazamiento a guardar: {desplazamiento_ini}")

            # Guardar en BD y capturar ref
            ref_bd = guardar_resultado_CambioFuente(
            usuario, fecha_cal,
            tipo, serie, certificado, fecha_cer, intensidad, conversion,
            modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro,
            t0, p0, h0, t, p, h,
            posiciones, medida1, medida2, promedios,
            [voltaje_alto, voltaje_bajo, voltaje_neg],  # Lista de voltajes
            V_alto, V_bajo, V_neg,                      # Medidas asociadas
            [V_alto_prom, V_bajo_prom, V_neg_prom],     # Promedios asociados
            Ks, Kp, Ktp, actividad_monitor, actividad_calculada,
            actividad_decaimiento, desplazamiento_ini, observaciones
        )

            self.ref_bd = ref_bd
            #self.limpiar_todos_los_campos()
            QMessageBox.information(self, "Guardado", "Datos guardados correctamente.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Error al guardar en la base de datos:\n{e}")

        # Mostrar resultados usando ref
        #mostrar_db_mensualBraqui(self)

    """Carga los datos de los equipos del último de cambio de funte y los muestra en los campos correspondientes predeterminados                                                                                        """
    def _limpiar_serie(self, texto):
        # F9 (PLAN_F_CIERRE_ESTANDAR_29-07.md §9): sin símbolos -- el
        # marcador de vencida ahora es "{serie} (vencida)" en minúsculas.
        if texto.endswith(" (vencida)"):
            texto = texto[:-len(" (vencida)")]
        return texto.strip()
    def cargar_datos_equipos(self):
        #print("Entra a cargar_datos_equipos de la clase PruebaMensualBraq")
        
        # Verificar que los widgets estén inicializados
        if not hasattr(self, 'widgets') or not self.widgets:
            print("Los widgets no están inicializados aún. Programando nueva ejecución...")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(200, self.cargar_datos_equipos)  # Reintentar en 200ms
            return
        
        # Verificar que los widgets necesarios estén disponibles
        campos_necesarios = ['serie', 'certificado', 'fecha_cer', 'intensidad', 'conversion']
        widgets_encontrados = 0
        for campo in campos_necesarios:
            if (hasattr(self, campo) or 
                (hasattr(self, 'widgets') and campo in self.widgets)):
                widgets_encontrados += 1
        
        if widgets_encontrados < len(campos_necesarios):
            print(f"Solo se encontraron {widgets_encontrados}/{len(campos_necesarios)} widgets necesarios. Reintentando...")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(200, self.cargar_datos_equipos)  # Reintentar en 200ms
            return
            
        try:
            conn = Conexion().conectar() 
            if conn is None:
                print("No se pudo conectar a la base de datos.")
                return

            cursor = conn.cursor()

            # 1. Buscar última fecha con tipo = "Cambio de fuente"
            cursor.execute('''
                SELECT id, fecha FROM TipoCalibracion
                WHERE tipo = "Cambio de fuente"
                ORDER BY fecha DESC LIMIT 1
            ''')
            fila_fecha = cursor.fetchone()
            if not fila_fecha:
                print("No se encontró calibración previa.")
                return
            
            ref_id = fila_fecha[0]
            fecha = fila_fecha[1]

            # 2. Obtener datos de TipoCalibracion
            cursor.execute('SELECT serie, certificado, fecha_cer, intensidad, conversion FROM TipoCalibracion WHERE id = ?', (ref_id,))
            tipo_data = cursor.fetchone()
            if not tipo_data:
                print("No se encontraron datos para el registro de calibración.")
                return
                
            #print(f"Datos obtenidos de la BD: {tipo_data}")
            
            # Mapeo de campos y sus valores de la BD
            campos_bd = {
                'serie': tipo_data[0],
                'certificado': tipo_data[1], 
                'fecha_cer': tipo_data[2],
                'intensidad': tipo_data[3],
                'conversion': tipo_data[4]
            }

            # Poner informacion de la BD a los widgets correspondientes
            for campo, valor in campos_bd.items():
                if hasattr(self, campo):
                    widget = getattr(self, campo)
                elif hasattr(self, 'widgets') and campo in self.widgets:
                    widget = self.widgets[campo]
                else:
                    print(f"Widget para '{campo}' no encontrado.")
                    continue

                if isinstance(widget, QLineEdit):
                    widget.setText(str(valor))
                elif isinstance(widget, QDateTimeEdit) and campo == 'fecha_cer':
                    try:
                        fecha_str = str(valor).strip()
                        #print(f"Fecha recibida de BD: '{fecha_str}'")
                        
                        # Convertir directamente usando QDateTime con el formato correcto
                        fecha_dt = QDateTime.fromString(fecha_str, "yyyy-MM-dd HH:mm:ss")
                        
                        if fecha_dt.isValid():
                            widget.setDateTime(fecha_dt)
                            #print(f"Fecha establecida correctamente: {fecha_dt.toString('yyyy-MM-dd HH:mm:ss')}")
                        else:
                            print(f"Fecha inválida: '{fecha_str}'. Usando fecha actual como fallback.")
                            widget.setDateTime(QDateTime.currentDateTime())
                            
                    except Exception as e:
                        print(f"Error al convertir fecha '{valor}': {e}")
                        widget.setDateTime(QDateTime.currentDateTime())
                else:
                    print(f"Tipo de widget no manejado para '{campo}': {type(widget)}")
        
            #print("Proceso de carga de datos completado")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Error al cargar calibración previa:", e)

        finally:
            if conn:
                conn.close()
    
    """Muestra la tabla que es de varios campos en la base de datos, en una ventana emergente                                                                                                                      """                        
    def mostrar_tabla_maximos(self, ref):
        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT posicion, medida1, medida2, promedio
            FROM MaximosCamaras
            WHERE ref = ?{filtro_activo('MaximosCamaras')}
            ORDER BY posicion ASC
        """, (ref,))
        resultados = cursor.fetchall()
        conn.close()

        dialog = QDialog(self)
        dialog.setWindowTitle("Máximos de cámaras")
        dialog.setMinimumSize(550, 300)
        dialog.resize(650, 450)
        layout = QVBoxLayout()

        table = QTableWidget(len(resultados), 4)
        table.setHorizontalHeaderLabels(["Posición (mm)", "Medida 1 (nA)", "Medida 2 (nA)", "Promedio (nA)"])

        for i, fila in enumerate(resultados):
            for j, val in enumerate(fila):
                item = QTableWidgetItem(f"{float(val):.2f}" if val else "-")
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(i, j, item)

        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec_()

    """Muestra la tabla que es de varios campos en la base de datos, en una ventana emergente                                                                                                                      """                        
    def mostrar_tabla_lecturas(self, ref):
        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT voltaje, V_300, V_150, Vn_300, promediosV
            FROM LecturasMaximos
            WHERE ref = ?{filtro_activo('LecturasMaximos')}
        """, (ref,))
        resultados = cursor.fetchall()
        conn.close()

        dialog = QDialog(self)
        dialog.setWindowTitle("Lecturas con diferente voltaje")
        dialog.setMinimumSize(550, 200)
        dialog.resize(700, 220)
        layout = QVBoxLayout()

        table = QTableWidget(len(resultados), 5)
        table.setHorizontalHeaderLabels(["Voltaje (V)", "Medida 1 (A)", "Medida 2 (A)", "Medida 3 (A)", "Promedio (A)"])

        for i, fila in enumerate(resultados):
            for j, val in enumerate(fila):
                try:
                    val_float = float(val)
                    item = QTableWidgetItem(f"{val_float:.2e}")
                except (ValueError, TypeError):
                    item = QTableWidgetItem(str(val) if val else "-")
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(i, j, item)

        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec_()

    """ Crea los botones y conecta las acciones de los botones a sus respectivas funciones                                                                                                                        """
    def button_click(self):
        #print("Entra a la función button_click de la clase PruebaMensualBraq")

        self.mensual_braqui = "Mensual Braquiterapia"
        self.aceptar.clicked.connect(lambda _, line=None: self.checkBotonesFinales(line, braqui=True, otro=self.mensual_braqui))
        self.btn_add.clicked.connect(self.guardar_DB)
        self.btn_add.clicked.connect(lambda: mostrar_db_mensualBraqui(self))
        self.btn_clean.clicked.connect(lambda: self.clean_info(imagenes=False))
        
   
                        
        if hasattr(self, 'es_cambio_fuente') and self.es_calibracion_redundante:
            self.btn_submit.clicked.connect(
                lambda _, :
                    guardarPDF_mensual(self, fecha=self.date_box.date().toString('yyyy-MM-dd'), 
                            maquina='Braquiterapia', tipo_reporte='Calibración Redundante', )
                        )
        else:
            self.btn_submit.clicked.connect(
                lambda: guardarPDF_mensual(
                    self,
                    fecha=self.date_box.date().toString('yyyy-MM-dd'),
                    maquina='Braquiterapia',
                    tipo_reporte='Cambio de fuente' if (hasattr(self, 'cambio_cal') and self.cambio_cal.isChecked()) else 'Control Mensual'
                )
            )

        # Conexión ÚNICA para el menú de gráficas
        self.menu_graficar.currentTextChanged.connect(self.plotter_mensual_desde_menu)
        
        self.edit_table.clicked.connect(lambda: verificar_editar(self, self.table, "TipoCalibracion", "id", None))
        self.accept_edit.clicked.connect(lambda: guardarEdicion(self, self.table, "TipoCalibracion", None))
        self.cancel_edit.clicked.connect(lambda: cancelarEdicion(self))

        self.btn_delete.clicked.connect(lambda: verificar_eliminar(self, self.table, "TipoCalibracion", None)) 
        
        self.search_bar.textChanged.connect(self.filtrarTabla)
        if hasattr(self, 'date_box'):
            self.date_box.dateChanged.connect(self.cargar_monthtest_desde_db)
            self.date_box.dateChanged.connect(self.cargar_monthtest_desde_db_condiciones)
            self.date_box.dateChanged.connect(self.mapear_tabla_medidas)
            self.date_box.dateChanged.connect(self.cargar_monthtest_desde_db_parametros)
            self.date_box.dateChanged.connect(self.mapear_tabla_maximos)
            self.date_box.dateChanged.connect(self.actualizar_ref_bd)
            self.date_box.dateChanged.connect(self.cargar_monthtest_desde_db_act)
            

    def cargar_monthtest_desde_db(self, fecha=None):
        """ 
        
        Esta función accesa a las bases de datos asociadas con la prueba mensual, busca las lineas en las que está
        cada uno de los widgets, compara si hay un valor en la base de datos y finalmente mapea este valor. 
        Esto se hace con el fin de tener mayor control de los QA que se hacen mensualmente y si se requiere algún
        tipo de edición o validación.
        
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
                SELECT * FROM TipoCalibracion 
                WHERE DATE(fecha) = ? OR DATE(SUBSTR(fecha, 7, 4) || '-' || SUBSTR(fecha, 4, 2) || '-' || SUBSTR(fecha, 1, 2)) = ? 
                
            """)
            query.addBindValue((fecha_str))
            query.addBindValue((fecha_str))
            #query.addBindValue(str(self.user_id))
            print(fecha_str)
            if not query.exec():
                print(f"Error en consulta: {query.lastError().text()}")
                db.close()
                return
            
                
            if query.next():
                record = query.record()
                print(str(query.value(record.indexOf('fecha'))))
                columnas_numericas = ['serie', 'certificado', 'conversion', 'calibracion', 'electrometro', 't0', 'p0', 'h0', 'ref']
                print("Usted está está debugeando aquí: Prueba mensual braq, cargar monthtest")
                try:
                    if hasattr(self, 'fecha_cal'):
                        fecha_cal = QDateTime.fromString(str(query.value(record.indexOf('fecha'))), "yyyy-MM-dd HH:mm:ss")
                        self.fecha_cal.setDateTime(fecha_cal)
                    if hasattr(self, 'serie'):
                        self.serie.setText(str(query.value(record.indexOf('serie'))))
                    if hasattr(self, 'certificado'):
                        self.certificado.setText(str(query.value(record.indexOf('certificado'))))
                    if hasattr(self, 'conversion'):
                        self.conversion.setText(str(query.value(record.indexOf('conversion'))))
                    if hasattr(self, 'intensidad'):
                        self.intensidad.setText(str(query.value(record.indexOf('intensidad'))))
                    if hasattr(self, 'fecha_cer'):
                        qdatetime = QDateTime.fromString(str(query.value(record.indexOf('fecha_cer'))), "yyyy-MM-dd HH:mm:ss")
                        self.fecha_cer.setDateTime(qdatetime)
                except Exception as e:
                    print("Error garrafal: ", e)
                
            
            print("consultando db")
            # Preparar la consulta
           
                                
            
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "Atencion", "No hay controles para la fecha especificada")
    
    
    def cargar_monthtest_desde_db_condiciones(self, fecha=None):
        """   
        Esta función accesa a las bases de datos asociadas con la prueba mensual, busca las lineas en las que está
        cada uno de los widgets, compara si hay un valor en la base de datos y finalmente mapea este valor. 
        Esto se hace con el fin de tener mayor control de los QA que se hacen mensualmente y si se requiere algún
        tipo de edición o validación.
        
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
            # MI0 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI0): columnas explícitas
            # -- son las 4 que se leen más abajo (modelo, serie_cp,
            # modelo_elec, serie_ele), por nombre en los 4 casos.
            query.prepare(f"""
                SELECT modelo, serie_cp, modelo_elec, serie_ele FROM SistemaMedicion
                WHERE (DATE(fecha) = ?
                OR DATE(SUBSTR(fecha, 7, 4) || '-' || SUBSTR(fecha, 4, 2) || '-' || SUBSTR(fecha, 1, 2)) = ?){filtro_activo('SistemaMedicion')}

            """)
            query.addBindValue((fecha_str))
            query.addBindValue(str(self.user_id))
            print(fecha_str)
            if not query.exec():
                print(f"Error en consulta: {query.lastError().text()}")
              
                return
            
                
            if query.next():
                record = query.record()
                
                columnas_numericas = []
                try:
                    if hasattr(self, 'combo_modelo'):
    
                        self.combo_modelo.setCurrentText(str(query.value(record.indexOf('modelo'))))
                    if hasattr(self, 'combo_serie'):
                        self._set_combo_serie(self.combo_serie, query.value(record.indexOf('serie_cp')))
                        print(f"Serie combo de camara de pozo: {query.value(record.indexOf('serie_cp'))}")
                    if hasattr(self, 'combo_modelo_elec'):
                        self.combo_modelo_elec.setCurrentText(str(query.value(record.indexOf('modelo_elec'))))
                        print(f"El modelo del electrometro: {query.value(record.indexOf('modelo_elec'))}")
                    if hasattr(self, 'combo_serie_elec'):
                        self._set_combo_serie(self.combo_serie_elec, query.value(record.indexOf('serie_ele')))
                        print("La serie del electrometro es: ", query.value(record.indexOf('serie_ele')))
                except Exception as e:
                    print("Error en equipos: ", e)
               
            else:
                raise ValueError("Error")
        except Exception as e:
            print(e)
        finally:
            query.finish() 
            
    """ Función para limpiar las series porque a alguien le dio por guardarlas en la db con un emoji y un texto decorador .|. """
    def _set_combo_serie(self, combo, serie_bd):
        serie_limpia = self._limpiar_serie(str(serie_bd))
        for i in range(combo.count()):
            if self._limpiar_serie(combo.itemText(i)) == serie_limpia:
                combo.setCurrentIndex(i)
                return
        print(f"Serie '{serie_limpia}' no encontrada en el combo.")
        
        
    def cargar_monthtest_desde_db_parametros(self, fecha=None):
        if fecha is None:
            fecha = self.date_box.date()
        
        # Convertir QDate a string en formato compatible con la BD
        fecha_str = fecha.toString("yyyy-MM-dd")
        
        
        db = self.opeenDatabase()
        if not db:
            return
       
        query = QSqlQuery(db)
        query.prepare(f"""
            SELECT t,p,h FROM CondicionesMedicion
            WHERE (DATE(fecha) = ? OR DATE(SUBSTR(fecha, 7, 4) || '-' || SUBSTR(fecha, 4, 2) || '-' || SUBSTR(fecha, 1, 2)) = ?){filtro_activo('CondicionesMedicion')}

        """)
        query.addBindValue((fecha_str))
        query.addBindValue((fecha_str))
        if not query.exec():
            print(f"Error en consulta parametros: {query.lastError().text()}")
            
            return
        
        if query.next():
            record = query.record()
            print("temperatura para tin")
            print(query.value(record.indexOf('t')))
            print(f"widget t: {self.t}, visible: {self.t.isVisible()}, parent: {self.t.parent()}")
            self.t.setText(str(query.value(record.indexOf('t'))))
            print(f"texto después de set: {self.t.text()}")
                    
        
            self.p.setText(str(query.value(record.indexOf('p'))))
            
        
            self.h.setText(str(query.value(record.indexOf('h'))))
            
       
    def cargar_monthtest_desde_db_act(self, fecha=None):
        if fecha is None:
            fecha = self.date_box.date()
        
        # Convertir QDate a string en formato compatible con la BD
        fecha_str = fecha.toString("yyyy-MM-dd")
        
        
        db = self.opeenDatabase()
        if not db:
            return
       
        query = QSqlQuery(db)
        query.prepare(f"""
            SELECT actividad_monitor FROM ResultadosActividad
            WHERE (DATE(fecha) = ? OR DATE(SUBSTR(fecha, 7, 4) || '-' || SUBSTR(fecha, 4, 2) || '-' || SUBSTR(fecha, 1, 2)) = ?){filtro_activo('ResultadosActividad')}

        """)
        query.addBindValue((fecha_str))
        query.addBindValue((fecha_str))
        if not query.exec():
            
            print(f"Error en consulta parametros: {query.lastError().text()}")
            
            return
        
        if query.next():
            record = query.record()

            self.ref.setText(str(query.value(record.indexOf('actividad_monitor'))))
            
        
            
                                    
      
    
    def cargar_medidas_desde_db(self, fecha_str):
        
        db = self.opeenDatabase()
        if not db:
            return []

        query = QSqlQuery(db)
        query.prepare(f"""
            SELECT posicion, medida1, medida2, promedio
            FROM MaximosCamaras
            WHERE (DATE(fecha) = ? OR DATE(SUBSTR(fecha, 7, 4) || '-' || SUBSTR(fecha, 4, 2) || '-' || SUBSTR(fecha, 1, 2)) = ?){filtro_activo('MaximosCamaras')}
            ORDER BY posicion DESC
        """)
        query.addBindValue((fecha_str))
        query.addBindValue((fecha_str))
        
        

        if not query.exec():
            print(f"Error en consulta mapeo: {query.lastError().text()}")
            db.close()
            return

        registros = []
        while query.next():
            registros.append((
                query.value(0),
                query.value(1),
                query.value(2),
                query.value(3)
            ))
        

        return registros
    
    def mapear_tabla_medidas(self, fecha=None):
        if fecha is None:
            fecha = self.date_box.date()

        fecha_str = fecha.toString("yyyy-MM-dd")

        registros = self.cargar_medidas_desde_db(fecha_str)

        for fila, datos in enumerate(registros):
            if fila >= len(self.campos_maximos):
                break

            posicion, m1, m2, prom = datos

            self.campos_maximos[fila][0].setText(str(posicion))
            self.campos_maximos[fila][1].setText(str(m1))
            self.campos_maximos[fila][2].setText(str(m2))
            self.campos_maximos[fila][3].setText(str(prom))
            
    
    def cargar_maximos_desde_db(self, fecha_str):
        
        db = self.opeenDatabase()
        if not db:
            return []

        query = QSqlQuery(db)
        query.prepare(f"""
            SELECT voltaje, V_300, V_150, Vn_300, promediosV
            FROM LecturasMaximos
            WHERE (DATE(fecha) = ? OR DATE(SUBSTR(fecha, 7, 4) || '-' || SUBSTR(fecha, 4, 2) || '-' || SUBSTR(fecha, 1, 2)) = ?){filtro_activo('LecturasMaximos')}
            ORDER BY DATE(fecha) DESC
            LIMIT 3
        """)
        query.addBindValue((fecha_str))
        query.addBindValue((fecha_str))
        

        if not query.exec():
            print(f"Error en consulta mapeo maximos: {query.lastError().text()}")
            db.close()
            return

        registros = []
        while query.next():
            
           
            registros.append((
                query.value(0),
                query.value(1),
                query.value(2),
                query.value(3),
                query.value(4)
            ))

        return registros
    
    def mapear_tabla_maximos(self, fecha=None):
        if fecha is None:
            fecha = self.date_box.date()

        fecha_str = fecha.toString("yyyy-MM-dd")

        registros = self.cargar_maximos_desde_db(fecha_str)

        for fila, datos in enumerate(registros):
            if fila >= len(self.campos_maximos):
                break

            voltaje, v300, v150, vn300, prom = datos

            self.campos_lecturas[fila][0].setText(str(voltaje))
            self.campos_lecturas[fila][1].setText(str(v300))
            self.campos_lecturas[fila][2].setText(str(v150))
            self.campos_lecturas[fila][3].setText(str(vn300))
            self.campos_lecturas[fila][4].setText(str(prom))
    
    
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
            filtro_mc = filtro_activo('MaximosCamaras').replace("activo", "mc.activo")
            query.prepare(f"""
                SELECT mc.posicion, mc.promedio
                FROM MaximosCamaras mc
                JOIN TipoCalibracion tc ON mc.ref = tc.id
                WHERE DATE(tc.fecha) = ?{filtro_mc}
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

    def observaciones_db(self):
        conn = Conexion().conectar()
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE CondicionesMedicion ADD COLUMN observaciones TEXT")
            conn.commit()
        except Exception:
            pass  # La columna ya existe
        finally:
            conn.close()
        
    # Añade widgets de tipo QLineEdit a un layout específico, con funcionalidad de carga y guardado de datos
    def addsomething(self, layout, df, prueba, nombre_tabla, uid, ref):
        """ [1] Filtra campos QLineEdit desde DataFrame
                ↓
            [2] Intenta cargar desde BD
                ├── Sí → rellena, bloquea edición, termina
                └── No → crea botones Guardar/Subir
                            ↓
                    [3] Intenta cargar desde JSON
                            ↓
                    [4] Usuario edita campos
                            ↓
                    [5] Guardar = JSON local
                    [6] Subir   = BD
        """

        df_lines = df.loc[(df.widget_type.str.contains('QLineEdit')) & (df.prueba == f'{prueba}')]['nombres']
        df_lines = [line for line in df_lines]    #if line != "observaciones"
        layout = layout.layout()

        def consulta(nombre_tabla, uid = uid, ref = ref):
                #print('Entro a traer info')
                conn = Conexion().conectar()
                cursor = conn.cursor()

                # MI0 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI0): columnas
                # explícitas -- `nombre_tabla` es un parámetro, así que las
                # columnas se resuelven en tiempo de ejecución con
                # encontrar_columnas (PRAGMA table_info, quita el id y, si
                # existe, 'activo'), en vez de `SELECT *` + recorte
                # posicional fijo. El recorte fijo (`[1:-1]` para todas menos
                # dosimetriaMen) asumía que la ÚLTIMA columna siempre era
                # `activo` -- cierto en TipoCalibracion, falso hoy en
                # SistemaMedicion/CondicionesMedicion (sin esa columna
                # todavía): descartaba una columna real (`observaciones` en
                # CondicionesMedicion). encontrar_columnas solo excluye
                # `activo` cuando de verdad está presente.
                columnas_str, _ = encontrar_columnas(nombre_tabla, id=True, delete=0)
                # LF (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF): `nombre_tabla`
                # es dinámico -- SistemaMedicion/CondicionesMedicion son
                # PENDIENTE-LF hoy (no-op); TipoCalibracion es raíz (DP-31,
                # filtro_activo() es "" siempre, no-op también, sin cambiar
                # nada para esa rama).
                cursor.execute(
                    f"SELECT {columnas_str} FROM {nombre_tabla} WHERE {uid} = ?{filtro_activo(nombre_tabla)}",
                    (ref,))
                results = cursor.fetchall()
                return results

        prueba1 = consulta(nombre_tabla, ref)

        if prueba1 is not None and prueba1 != []:
            datos = list(prueba1[0])
            #print(f"Datos cargados en {nombre_tabla} desde la prueba: {datos}")

            for line_name, valor in zip(df_lines, datos):
                campo = getattr(self, line_name)
                # Permite editar los campos antes de subir
                campo.setText(str(valor))
            return
            #print("Datos cargados desde la prueba.")

    def generar_reporte_pdf(self):
        from models.PDF.Mensuales.reportes_mensuales import guardarPDF_mensual
        fecha = self.date_box.date().toString("MM/yyyy")  # O el formato de fecha que uses 
        print(fecha)
        guardarPDF_mensual(self, fecha, maquina='Braquiterapia', diccionario=None)

