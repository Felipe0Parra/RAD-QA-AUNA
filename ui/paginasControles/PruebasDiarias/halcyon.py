from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QSplitter, QWidget, QToolBox, QLineEdit, QDateEdit
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtCore import QDate, Qt
from data.GraficasyTablas.tablas import load_table, asignar_encabezados
from data.ManejoDatos.obtenerDatosHalcyon import previsualizar_halcyon, agregar_halcyon
from data.GraficasyTablas.unovsuno import graficarvstiempo
from models.PDF.reportes import reporte
import pandas as pd

class PruebaDiariaHc(PruebaBasico):
    def __init__(self, user_id):
        super(PruebaDiariaHc, self).__init__()
        #print("PruebaDiariaHc         __init__ called")
        self.initDATA(user_id)
        self.iniGUI()
        load_table(self, boolean_keys= None, dosis= None, maquina= 'halcyon')
        asignar_encabezados(self, 'halcyon')
        self.button_click()
        self.fueradeservicioHC = False
    def initDATA(self, user_id):
        self.user_id = user_id
        self.ganancia_cal = {"Ganancia. Cal", "Uniformidad. Cal"}
        self.graficos_mapeo1  = {
            "Tamaño del IsoCentro": "IsoCenterSize_name2",
            "Desviación MV del IsoCentro": "IsoCenterMVOffset",
            "Desviación KV del IsoCentro": "IsoCenterKVOffset",
            "Cambio en la salida del haz": "BeamOutputChange",
            "Cambio en la uniformidad del haz": "BeamUniformityChange",
            "Cambio en la ganancia de MU1 del haz": "BeamMu1GainChange",
            "Cambio en la ganancia de MU2 del haz": "BeamMu2GainChange",
            "Posición absoluta del gantry": "GantryAbsolute",
            "Posición relativa del gantry": "GantryRelative",
            "Posición lateral de la mesa": "CouchLat",
            "Posición longitudinal de la mesa": "CouchLng",
            "Posición vertical de la mesa": "CouchVrt",
            "Posición lateral en coordenadas largas de la mesa": "CouchLatLong",
            "Posición longitudinal en coordenadas largas de la mesa": "CouchLngLong",
            "Posición vertical en coordenadas largas de la mesa": "CouchVrtLong",
            "Desviación lateral virtual al IsoCentro": "VirtualToIsoLat",
            "Desviación longitudinal virtual al IsoCentro": "VirtualToIsoLng",
            "Desviación vertical virtual al IsoCentro": "VirtualToIsoVrt",
            "Ganancia de calibración de imagen MV": "MVImagerCalibrationGain",
            "Uniformidad de calibración de imagen MV": "MVImagerCalibrationUniformity"
        }
        self.boolean_columns = self.graficos_mapeo1.values()
        # Valores límite para cada métrica
        self.valores_limite = {
            "Tamaño del IsoCentro": 0.9,
            "Desviación MV del IsoCentro": 0.5,
            "Desviación KV del IsoCentro": 0.5,
            "Cambio en la salida del haz": 4,
            "Cambio en la uniformidad del haz": 2,
            "Cambio en la ganancia de MU1 del haz": 10,
            "Cambio en la ganancia de MU2 del haz": 10,
            "Posición absoluta del gantry": 0.5,
            "Posición relativa del gantry": 0.5,
            "Posición lateral de la mesa": 0.5,
            "Posición longitudinal de la mesa": 0.5,
            "Posición vertical de la mesa": 0.5,
            "Posición lateral en coordenadas largas de la mesa": 1,
            "Posición longitudinal en coordenadas largas de la mesa": 1,
            "Posición vertical en coordenadas largas de la mesa": 1,
            "Desviación lateral virtual al IsoCentro": 2,
            "Desviación longitudinal virtual al IsoCentro": 2,
            "Desviación vertical virtual al IsoCentro": 2
        }
        
        self.diccionario_invertido = {
            "IsoCenterSize_name2": ["Tamaño del IsoCentro", 0.9],
            "IsoCenterMVOffset": ["Desviación MV del IsoCentro", 0.5],
            "IsoCenterKVOffset": ["Desviación KV del IsoCentro", 0.5],
            "BeamOutputChange": ["Cambio en la salida del haz", 4.0],
            "BeamUniformityChange": ["Cambio en la uniformidad del haz", 2.0],
            "BeamMu1GainChange": ["Cambio en la ganancia de MU1 del haz", 10.0],
            "BeamMu2GainChange": ["Cambio en la ganancia de MU2 del haz", 10.0],
            "GantryAbsolute": ["Posición absoluta del gantry", 0.5],
            "GantryRelative": ["Posición relativa del gantry", 0.5],
            "CouchLat": ["Posición lateral de la mesa", 0.5],
            "CouchLng": ["Posición longitudinal de la mesa", 0.5],
            "CouchVrt": ["Posición vertical de la mesa", 0.5],
            "CouchLatLong": ["Posición lateral en coordenadas largas de la mesa", 1.0],
            "CouchLngLong": ["Posición longitudinal en coordenadas largas de la mesa", 1.0],
            "CouchVrtLong": ["Posición vertical en coordenadas largas de la mesa", 1.0],
            "VirtualToIsoLat": ["Desviación lateral virtual al IsoCentro", 2.0],
            "VirtualToIsoLng": ["Desviación longitudinal virtual al IsoCentro", 2.0],
            "VirtualToIsoVrt": ["Desviación vertical virtual al IsoCentro", 2.0],
            "MVImagerCalibrationGain": ["Ganancia de calibración de imagen MV", ""],
            "MVImagerCalibrationUniformity": ["Uniformidad de calibración de imagen MV", ""]
        }
        
    def convert_date_to_str(self):
        self.previsualizar_fecha_seleccionada()

    def previsualizar_fecha_seleccionada(self):
        """H3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §H3): elegir la
        fecha (dateChanged) localiza la carpeta MPC, lee el Results.csv y
        llena los campos -- CERO escrituras en la BD. Antes esto guardaba
        directamente (H1 conectó addInfo, que hacía las tres cosas de una
        sola pasada, a dateChanged Y al botón "Agregar"): el físico
        esperaba que elegir la fecha solo previsualizara y "Agregar"
        guardara, igual que el flujo de importar un .mcc -- ver
        agregar_fecha_seleccionada."""
        selected_date = self.date_box.date()
        date_str = selected_date.toString("yyyy-MM-dd")
        self.date_box.setDisplayFormat("yyyy/MM/dd")
        df = previsualizar_halcyon(self, date_str)
        if df is not None and not df.empty:
            self.update_lineedit_blocks(df)
        load_table(self, boolean_keys= None, dosis= None, maquina= 'halcyon')
        asignar_encabezados(self, 'halcyon')

    def agregar_fecha_seleccionada(self):
        """H3: "Agregar" -- toma la fecha elegida, guarda (localiza,
        comprueba que la fecha no exista, llama a createDB, audita) y avisa
        del resultado. Único punto de escritura del diario del Halcyon."""
        selected_date = self.date_box.date()
        date_str = selected_date.toString("yyyy-MM-dd")
        df = agregar_halcyon(self, date_str, self.user_id._nombre)
        if df is not None and not df.empty:
            self.update_lineedit_blocks(df)
        load_table(self, boolean_keys= None, dosis= None, maquina= 'halcyon')
        asignar_encabezados(self, 'halcyon')

    def update_lineedit_blocks(self, new_data):
        """
        Actualiza los valores de los QLineEdit block basados en un nuevo DataFrame.
        Args: new_data (DataFrame): DataFrame con las columnas 'nombres' y 'nuevo_valor'.
        """
        for index, row in new_data.iterrows():
            widget_name = row['nombres']  # Nombre del widget
            if hasattr(self, widget_name):  # Verifica si el widget existe
                widget = getattr(self, widget_name)  # Obtiene el widget
                if isinstance(widget, QLineEdit) and widget.isReadOnly():  # Verifica que sea QLineEdit y esté bloqueado
                    nuevo_valor = row['descripcion']  # Obtiene el nuevo valor
                    if pd.isna(nuevo_valor):  # Si el valor es NaN, lo sustituye
                        nuevo_valor = ""
                    widget.setText(str(nuevo_valor))  # Actualiza el texto del QLineEdit    
    
    def iniGUI(self):
        self.main_layout = QHBoxLayout()
        archivo = 'widgets.xlsx'
    
        ##ENCABEZADO
        self.mach_name2 = QLabel('HALCYON')
        self.code_1 = QLabel('HALCYON')
        
        self.date_box = QDateEdit()
        self.date_box.setCalendarPopup(True)  # Muestra un calendario desplegable
        self.date_box.setDate(QDate.currentDate())  # Fecha inicial: hoy
        self.date_box.dateChanged.connect(self.convert_date_to_str)  # Conexión al método
        
        #ingresar datos de encabezado
        self.general_layout.addWidget(self.date_box)
        
        ## PREGUNTAS
        df, n, layouts, _ = self.setupBox(archivo, 'preguntas_hal', main = False)
        
        #al usar toolbox no se pueden agregar directamente los grid, hay que meterlos en un widget
        self.canson1 = QWidget()       
        self.canson2 = QWidget()
        self.canson3 = QWidget()
        self.canson4 = QWidget()
        self.canson5 = QWidget()

        toolbox= QToolBox()
        
        i = 1
        for layout in layouts: 
            name = f'canson{i}'
            getattr(self, name).setLayout(layout)
            i+=1

        toolbox.addItem(self.canson1, 'ISOCENTRO')
        toolbox.addItem(self.canson2, 'HAZ')
        toolbox.addItem(self.canson3, 'GANTRY')
        toolbox.addItem(self.canson4, 'CAMILLA')
        toolbox.addItem(self.canson5, 'DETECTOR DE IMAGEN MV')

        self.general_layout.addWidget(toolbox)

        #BOTONES
        
        _ = self.setupBox(archivo, 'btn')
        self.btn_add.setText('Agregar')
        #self.btn_delete.setEnabled(False)
        
        ## GRAFICOS
        # tabla
        self.createTable(df)
        
        # Crear zona de graficas
        
        menu_graficas = ['Seleccione...', 'Isocentro', 'Haz', 'Gantry', 'Camilla', 'Detector de imagen MV']
        
        grafico1 = [
            'Seleccione...',
            "Tamaño del IsoCentro",
            "Desviación MV del IsoCentro",
            "Desviación KV del IsoCentro"]
        
        grafico2 = [
            'Seleccione...',
            "Cambio en la salida del haz",
            "Cambio en la uniformidad del haz",
            "Cambio en la ganancia de MU1 del haz",
            "Cambio en la ganancia de MU2 del haz"]
        
        gradico3 =[
            'Seleccione...',
            "Posición absoluta del gantry",
            "Posición relativa del gantry"]
        
        grafico4 = [
            'Seleccione...',
            "Posición lateral de la mesa",
            "Posición longitudinal de la mesa",
            "Posición vertical de la mesa",
            "Posición lateral en coordenadas largas de la mesa",
            "Posición longitudinal en coordenadas largas de la mesa",
            "Posición vertical en coordenadas largas de la mesa",
            "Desviación lateral virtual al IsoCentro",
            "Desviación longitudinal virtual al IsoCentro",
            "Desviación vertical virtual al IsoCentro"]
        
        grafico5 = [
            'Seleccione...',
            "Ganancia de calibración de imagen MV",
            "Uniformidad de calibración de imagen MV"
        ]

        graficos = [grafico1, grafico2, gradico3, grafico4, grafico5]
            
        date_limit, self.canvas, self.menu_graficar, self.graficar = self.plotterSpaceEX(menu_graficas, graficos)
        self.edit_table_tools = self.createTable(df=df, headers=None)
        caja_menu_graficas = QHBoxLayout()
        caja_menu_graficas.addWidget(self.menu_graficar)
        for grafica in self.graficar: 
            caja_menu_graficas.addWidget(grafica)
        
        self.settfigure = QHBoxLayout()
        self.settfigure.addLayout(caja_menu_graficas)
        
        # Design Our Layout
        self.col2 = QVBoxLayout()
        
        self.col2.addLayout(self.settfigure)
        self.col2.addLayout(date_limit)
        self.col2.addWidget(self.canvas)
        
        self.col2_1 = QVBoxLayout()
        self.col2_1.addWidget(self.table)
        
        self.wf2 = QSplitter(Qt.Vertical)
        
        self.widgetgrafica = QWidget()
        self.widgetgrafica.setLayout(self.col2)
        
        self.widgettabla = QWidget()
        self.widgettabla.setLayout(self.col2_1)
        
        self.wf2.addWidget(self.widgetgrafica)
        self.wf2.addWidget(self.widgettabla)
        
        self.wf = QWidget()
        self.wf.setLayout(self.general_layout)
        
        self.splitter_principal = QSplitter(Qt.Horizontal)
        self.splitter_principal.addWidget(self.wf)
        self.splitter_principal.addWidget(self.wf2)
        
        self.main_layout.addWidget(self.splitter_principal)
        
        #self.general_layout.removeWidget(self.btn_add)
        #self.btn_add.deleteLater()  # Opcional para liberar memoria
        self.col2_1.addLayout(self.edit_table_tools)
        self.setLayout(self.main_layout)

    def plotter(self, menu):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        db = self.opeenDatabase()
        selected_chart = menu.currentText()  # QComboBox con tipos de gráfica
        if selected_chart == "Seleccione...":
            return
        
        start_date = self.limit1.date().toString('yyyy-MM-dd')
        end_date = self.limit2.date().toString('yyyy-MM-dd')
        
        selected_column1 = self.graficos_mapeo1.get(selected_chart, None)
        limite = self.valores_limite.get(selected_chart, None)
        
        if selected_column1:
            query = QSqlQuery(db)
            graficarvstiempo(self, query, ax, 'halcyon', selected_column1, selected_chart, start_date, end_date, False, limite)    
        # Redibuja en el canvas
        self.canvas.draw()
        
        db.close()
    
    def button_click(self):
        #falta btn_clean
        #falta btn_delete (no se en que utilzarlo)

        # H1 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.4):
        # btn_add nunca estuvo conectado (comentario original de arriba,
        # "Falta btn_add (para el pdf)" -- git log -S"btn_add" confirma un
        # solo commit, el estado virgen).
        # H3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §H3): btn_add ya
        # NO comparte método con dateChanged -- dateChanged solo
        # previsualiza (previsualizar_fecha_seleccionada, cero escrituras);
        # "Agregar" es el único que guarda (agregar_fecha_seleccionada ->
        # agregar_halcyon -> createDB -> ACCION_GUARDAR).
        self.btn_add.clicked.connect(self.agregar_fecha_seleccionada)

        if self.btn_submit.clicked:
            self.btn_submit.clicked.connect(
                lambda _, maquina=self.mach_name2.text(), id_maquina=self.code_1.text(): 
                    reporte(self, fecha = self.date_box.date().toString('yyyy-MM-dd'), 
                            maquina = maquina, id_maquina=id_maquina, tipo_reporte='diario', 
                            diccionario=self.diccionario_invertido, umbrales= "si")
            )
        
        self.menu_graficar.currentIndexChanged.connect(self.mostrar_submenu)
        self.btn_delete.clicked.connect(lambda _, maquina='halcyon': self.verificar_eliminar(maquina, [self.boolean_columns, self.ganancia_cal]))

        for grafica in self.graficar:
            grafica.currentIndexChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))
            self.btn_submit.clicked.connect(lambda _, grafica = grafica: self.plotter(grafica)) 
            self.limit1.dateChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))
            self.limit2.dateChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))

        self.search_bar.textChanged.connect(self.filtrarTabla)  # Conectar evento de búsqueda


        # A10 (§8.1 H5, PLAN_AUDITORIA_DOS_EJES_21-07): sin edición manual en
        # el diario del Halcyon -- decisión del físico (2026-07-22): el
        # registro se carga solo desde los archivos MPC
        # (obtenerDatosHalcyon.py), así que no tiene sentido editarlo a mano.
        # Antes "editar" reusaba verificar_editar()/edicionTabla()
        # (PruebasDiarias.py), que revienta con AttributeError porque esta
        # clase nunca definió self.boolean_colums (existe en seiscientos.py/
        # IX.py, no aquí) -- el físico lo vio como "pide credenciales pero no
        # pasa". En vez de agregar ese atributo, se deshabilita el botón.
        self.edit_table.setEnabled(False)
        self.edit_table.setToolTip(
            "El registro diario del Halcyon se carga automáticamente desde "
            "los archivos MPC y no se edita manualmente.")

        
    def mostrar_submenu(self):
        
        for grafica in self.graficar:
            grafica.hide()
            grafica.setCurrentIndex(0)
        selection = self.menu_graficar.currentIndex()
        
        if selection > 0 and selection <= len(self.graficar):
            self.graficar[selection-1].show()