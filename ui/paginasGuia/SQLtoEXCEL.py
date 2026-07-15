""" 
Esto tendrá la misma sintaxis que las otras páginas, pero se cargará dinámicamente cuando el usuario haga clic en la pestaña.
Aquí se tendrá la función que exporta datos de sql a excel.
"""
import sqlite3 as sql
import pandas as pd
from PyQt5.QtWidgets import QComboBox ,QWidget, QDialog, QGridLayout, QVBoxLayout, QHBoxLayout ,QPushButton, QTableWidget, QFileDialog, QListWidget, QLabel, QDateEdit, QHBoxLayout, QMessageBox, QListWidgetItem, QTableWidgetItem, QSizePolicy
from PyQt5.QtCore import Qt
import os
from openpyxl.drawing.image import Image 
from ui.paginasGuia.dialogs import DateRangeDialog
import openpyxl as exl
import io
import PIL
import numpy as np
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QWidget
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from data.ManejoDatos import conection as _conection  # HI-1: resolucion dinamica, no import por valor
connect = sql.connect(_conection.ruta_base_datos())
class Color(QWidget):
    def __init__(self, color):
        super().__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(color))
        self.setPalette(palette)
        
class ExportarExcel(QWidget):
    def __init__(self):
        super().__init__()
        # Whitelist of tables to show: {table_name: display_name}
        self.allowed_tables = {
            "aceleradorlineal_ix": "Acelerador Lineal IX",
            "aceleradorlineal_600": "Acelerador Lineal 600",
            "braqui": "Braquiterapia",
            "halcyon": "Halcyon",
            "hc_dosimetria_anual": "Dosimetria Anual",
            "CondicionesMedicion": "Condiciones de Medición",
            "MaximosCamaras" : "Máximos de Cámaras",
            "analisis_placa_correcciones": "Análisis Placa de Correcciones",
            "analisis_placa_franjas" : "Análisis Placa de Franjas",
            "control_conos" : "Control de Conos",
            "control_cunas": "Control de Cunas",
            "controles": "Controles",
            "dosimetriaMen": "Dosimetría Mensual",
            "equipos": "Equipos",
            "equipos_medicion": "Equipos de Medición",
            "espesor_corte": "Espesor de Corte",
            "HC_desplazamiento_isocentro_mensual": "HC Desplazamiento Isocentro Mensual",
            "HC_dosimetria_anual": "HC Dosimetría Anual",
            "HC_fantomas": "HC Fantomas",
            "HC_imagen_perfil_mlc_anual": "HC Imagen y Perfil MLC Anual",
            "HC_indicadores_brazo": "HC Indicadores de Brazo",
            "HC_indicadores_camilla": "HC Indicadores de Camilla",
            "HC_indicadores_colimador": "HC Indicadores de Colimador",
            "HC_indicadores_laser": "HC Indicadores de Láser",
            "HC_linealidad_unidades_monitor_anual": "HC Linealidad Unidades Monitor Anual",
            "HC_precision_posicion_multilaminas_anual": "HC Precisión de Posición Multiláminas Anual",
            "HC_tamanos_campo_radiacion": "HC Tamaño de Campo de Radiación",
            "HC_velocidad_multilaminas_anual": "HC Velocidad Multiláminas Anual",
            "indicadores_angulares_colimador": "Indicadores Angulares del Colimador",
            "indicadores_brazo": "Indicadores del Brazo",
            "LecturasMaximos": "Lecturas Máximos",
            "linealidad_ct" : "Linealidad CT",
            "LinealidadBraquiterapia": "Linealidad Braquiterapia",
            "materiales_ct" : "Materiales CT",
            "pruebas": "Pruebas",
            "regiones_uniformidad": "Regiones de Uniformidad",
            "resolucion_contraste": "Resolución de Contraste",
            "resolucion_contraste_rois": "Resolución de Contraste ROIs",
            "resolucion_espacial": "Resolución Espacial",
            "resolucion_espacial_regiones": "Resolución Espacial Regiones",
            "ResultadosActividad" : "Resultados de Actividad",
            "SistemaMedicion": "Sistema de Medición",
            "tabla_control_camaras_monitoras": "Tabla de Control de Cámaras Monitoras",
            "tabla_factor_campo" : "Tabla de Factor de Campo",
            "tabla_factores_eje": "Tabla de Factores de Eje",
            "tabla_factores_transmision" : "Tabla de Factores de Transmisión",
            "tamano_campo": "Tamaño de Campo",
            "tamaño_pixel"  : "Tamaño de Píxel",
            "TipoCalibracion": "Tipo de Calibración",
            "uniformidad_global"    : "Uniformidad Global",
            "uniformidad_ruido" : "Uniformidad del Ruido",
            "valores_ct": "Valores CT"



        }
     

        self.initUI()

    def initUI(self):
        # Main vertical layout
        main = QVBoxLayout()
        main.setContentsMargins(46, 16, 46,16)
        main.setSpacing(18)
        
        # Header label
        self.label = QLabel("Seleccione las tablas a exportar:")
        self.label.setStyleSheet("font-size:13px; font-weight:bold; margin-bottom:6px;")
        main.addWidget(self.label)
        
        # 2x2 Grid layout for aesthetic spacing
        grid = QGridLayout()
        grid.setSpacing(20)
        grid.setContentsMargins(46, 16, 46, 16)
        
        # Create placeholders for visual balance
        ph1 = QWidget()
        ph1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ph1.setStyleSheet("background-color: #f0f0f0; border-radius: 8px;")

        
        ph3 = QWidget()
        ph3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ph3.setStyleSheet("background-color: #f0f0f0; border-radius: 8px;")
        
        # Main combobox
        self.table_list = QComboBox()
     
        self.load_tables()
        
        # Selector (secondary) combobox
        self.selector = QComboBox()
        self.selector.setStyleSheet("QComboBox { padding:5px 8px; min-height:26px; font-size:11px; border-radius:4px; }")
        for i in range(self.table_list.count()):
            text = self.table_list.itemText(i)
            data = self.table_list.itemData(i)
            self.selector.addItem(text, data)
        self.selector.currentIndexChanged.connect(self.on_selector_changed)
        self.selector.currentIndexChanged.connect(self.update_preview)
        self.preview_table = QTableWidget()
        self.update_preview()
        self.preview_table.setMaximumHeight(1500)
        self.table_list.currentIndexChanged.connect(self.update_preview)
        
        # Add widgets to 2x2 grid
        grid.addWidget(self.table_list, 0, 0, 1, 2)
        grid.addWidget(self.preview_table, 1, 0, 2, 2)
        #grid.addWidget(ph3, 1, 1)
        
        # Set stretch factors for balanced layout
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        
        # Add grid to main layout
        main.addLayout(grid)
        main.addSpacing(12)  # small gap between grid and button
        
        # Export button at bottom
        self.export_button = QPushButton("Exportar a Excel")
        self.export_button.setStyleSheet(
            "QPushButton { padding:16px 16px; font-size:12px; font-weight:bold; "
            "background-color:#6fb8c3; color:white; border:none; border-radius:4px; }"
            "QPushButton:hover { background-color:#4a8892; }"
            "QPushButton:pressed { background-color:#2e5d66; }"
        )
        self.export_button.setMinimumHeight(36)
        self.export_button.clicked.connect(self.exportar)
        main.addWidget(self.export_button)
        
        # Set main layout
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setLayout(main)


        
        
    def on_selector_changed(self, index: int):
        if 0<=index < self.table_list.count():
            self.table_list.setCurrentIndex(index)
    
    def update_preview(self, index=None):
        table_name = self.table_list.currentData()
        if not table_name:
            self.preview_table.clear()
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return
        try:
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}" LIMIT 30', connect)
        except Exception:
            self.preview_table.clear()
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return

        
       
        self.preview_table.clear()
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setRowCount(len(df))
        self.preview_table.setHorizontalHeaderLabels(list(df.columns))
        for r, (_, row) in enumerate(df.iterrows()):
            for c, val in enumerate(row):
                text = '' if pd.isna(val) else str(val)
                self.preview_table.setItem(r, c, QTableWidgetItem(text))
        self.preview_table.resizeColumnsToContents()


            
            


    def load_tables(self):
        # Clear existing items
        self.table_list.clear()
        # If an allowed_tables whitelist is provided, show only those (with friendly names)
        if getattr(self, 'allowed_tables', None):
            for table_name, display_name in self.allowed_tables.items():
               
                self.table_list.addItem(display_name, table_name)
            return

        # Fallback: list all tables from the DB
        cursor = connect.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
       
        
    def changeColumnNames(self, df, table_name):
        df = df.copy()
        self.column_dict_ix = {
    'date': 'Fecha',
    'user_id': 'Usuario',
    'luces_consola': 'Luces en consola',
    'luces_puerta' : 'Luces de puerta',
    'luces_irradiacion' : 'Luces de irradiación en consola',
    'sistema_visualizacion': 'Sistema de visualización',
    'sistema_anticolision' : 'Sistema anticolisión',
    'interruptor_radiacion_puerta': 'Interrupción de radiación en puerta',
    'interruptor_radiacion_panel': 'Interrupción de radiación en panel',
    'interrupcion_um': 'Interrupción por UM',
    'verificacion_monitoras':'Verificación de ambas monitoras',
    'movimiento_brazo': 'Movimiento del brazo',
    'movimiento_colimador' : 'Movimiento del colimador',
    'movimientos_camilla' : 'Movimientos de la camilla',
    'laseres' : 'Láseres',
    'telemetro' : 'Telémetro',
    'tamano_campo' : 'Tamaño de campo',
    'centrado_reticulo' : 'Centrado del retículo',
    'tol_fot_6mv': 'Tolerancia Fotones 6MV',
    'tol_fot_15mv': 'Tolerancia Fotones 15MV',      
    'tol_ele_6mev': 'Tolerancia Electrones 6MeV',
    'tol_ele_9mev': 'Tolerancia Electrones 9MeV',
    'tol_ele_12mev': 'Tolerancia Electrones 12MeV',
    'tol_ele_15mev': 'Tolerancia Electrones 15MeV',
    'observaciones' : 'Observaciones'
        }
        self.column_dict_braqui = {
    'date': 'Fecha',
    'user_id': 'Usuario',
    'int_con_box': 'Interrupcion desde la consola',
    'emerg_con': 'Parada de emergencia cerca de la consola',    
    'blq_puerta': 'Bloqueo de la puerta',
    'pos_fuente': 'Indicador de posicion de la fuente', 
    'res_fuente': 'Sistema de respaldo',
    'key_fuente': 'Interruptor de llave de la fuente',
    'mon_area': 'Monitor de area',
    'lum_puerta': 'Indicador luminoso de la puerta',
    'tub_guia': 'Conexion correcta del tubo guia',
    'visual_sys': 'Sistema de visualizacion',
    'intercom': 'Sistema de intercomunicacion',
    'mon_rad_port': 'Monitor de radiacion portatil',
    'tol_rep_act_ci': 'Actividad reportada de la fuente',
    'tol_exp_act': 'Actividad esperada de la fuente',
    'tol_cyc_dummy': 'Ciclos de la fuente falsa',
    'tol_cyc_rad': 'Ciclos de la fuente radioactiva',
    'distancias' : 'Distancias',
    'promedio' : 'Promedio',
    'desviacion' : 'Desviación',
    'desplazamientos' : 'Desplazamientos',
    'promedio_des': 'Promedio de desplazamientos',
    'desviacion_des': 'Desviacion estandar de desplazamientos',
    'observaciones' : 'Observaciones'
        }
        self.column_dict_halcyon = {
            'date': 'Fecha',
            'user_id': 'Usuario',
            'IsoCenterSize_name2' : 'Tamaño del isocentro',
            'IsoCenterMVOffset' : 'Desviacion de proyeccion del detector de imagen MV',
            'IsoCenterKVOffset' : 'Desviacion de proyeccion del detector de imagen KV',
            'BeamOutputChange' : 'Cambio de salida del haz',
            'BeamUniformityChange' : 'Cambio de uniformidad del haz',
            'BeamMu1GainChange' : 'Cambio de ganancia UM1',
            'BeamMu2GainChange' : 'Cambio de ganancia UM2',
            'GantryAbsolute' : 'Posicion absoluta del gantry',
            'GantryRelative' : 'Posicion relativa del gantry',
            # CAMILLA
            'CouchLat' : 'Posicion lateral de la camilla',
            'CouchLng' : 'Posicion longitudinal de la camilla',
            'CouchVrt' : 'Posicion vertical de la camilla',
            'CouchLatLong' : 'Posicion lateral (largo) de la camilla',
            'CouchLngLong' : 'Posicion longitudinal (largo) de la camilla',
            'CouchVrtLong' : 'Posicion vertical (largo) de la camilla',
            'VirtualToIsoLat' : 'Posicion virtual a isocentro lateral',
            'VirtualToIsoLng': 'Posicion virtual a isocentro longitudinal',
            'VirtualToIsoVrt': 'Posicion virtual a isocentro vertical',
            'MVImagerCalibrationGain' : 'Ganancia de la calibracion',
            'MVImagerCalibrationUniformity' : 'Uniformidad de la calibracion',
            'observaciones' : 'Observaciones'
        }
        self.column_dict_HC = {
            'date': 'Fecha',
            'user_id': 'Usuario',
            'val_teo_discrepancia': 'Valor teórico de la discrepancia',
            'dosis_ref_cgy_um' : 'Dosis de referencia (cGy/UM)',
            'discrepancia_dosis': 'Discrepancia de dosis (%)',
            'tolerancia_dosis' : 'Tolerancia de dosis (%)',
            'calidad_pdd20_10': 'Calidad PDD 20/10',
            'discrepancia_calidad': 'Discrepancia de calidad (%)',
            'tolerancia_calidad': 'Tolerancia de calidad (%)',
            'simetria_inplane': 'Simetría Inplane (%)',
            'simetria_crossplane': 'Simetría Crossplane (%)',
            'tolerancia_simetria': 'Tolerancia de simetría (%)',
            'planicidad_inplane': 'Planicidad Inplane (%)',
            'planicidad_crossplane': 'Planicidad Crossplane (%)',
            'tolerancia_planicidad': 'Tolerancia de planicidad (%)',
            'observaciones_dosi'    : 'Observaciones de dosimetría',
        }
        self.column_dict_600 = {
            'date': 'Fecha',
            'user_id': 'Usuario',
            'luces_consola': 'Luces en consola',
            'luces_puerta' : 'Luces de puerta',
            'luces_irradiacion': 'Luces de irradiación en consola',
            'sistema_visualizacion': 'Sistema de visualización',
            'sistema_anticolision' : 'Sistema anticolisión',
            'interruptor_radiacion_puerta': 'Interrupción de radiación en puerta',
            'interruptor_radiacion_panel': 'Interrupción de radiación en panel',
            'interrupcion_um': 'Interrupción por UM',
            'verificacion_monitoras':'Verificación de ambas monitoras',
            'movimiento_brazo': 'Movimiento del brazo',
            'movimiento_colimador' : 'Movimiento del colimador',
            'movimientos_camilla' : 'Movimientos de la camilla',
            'laseres' : 'Láseres',
            'telemetro' : 'Telémetro',
            'tamano_campo' : 'Tamaño de campo',
            'centrado_reticulo' : 'Centrado del retículo',
            'dosis_referencia' : 'Dosis de referencia',
            'observaciones' : 'Observaciones'
        }
        self.column_dict_condicionesmedicion = {
            'fecha': 'Fecha',
            'user': 'Usuario',
            'desplazamiento_ini' : 'Desplazamiento inicial'
            }
        self.column_dict_MaxCam = {
            'fecha': 'Fecha',
            'user': 'Usuario',
            'posicion': 'Posición',
            'medida1': 'Medida 1',
            'medida2': 'Medida 2',
            'promedio': 'Promedio'
        }
        # Si la tabla seleccionada es ix:

        if table_name.lower() == "aceleradorlineal_ix":
            df.rename(columns=self.column_dict_ix, inplace=True)
        elif table_name.lower() == "braqui":
            df.rename(columns=self.column_dict_braqui, inplace=True)
        elif table_name.lower() == "halcyon":
            df.rename(columns = self.column_dict_halcyon, inplace=True)
        elif table_name.lower() == "hc_dosimetria_anual":
            df.rename(columns = self.column_dict_HC, inplace=True)
        elif table_name.lower() == "aceleradorlineal_600":
            df.rename(columns = self.column_dict_600, inplace=True)
        elif table_name.lower() == "CondicionesMedicion":
            df.rename(columns = self.column_dict_condicionesmedicion, inplace=True)
        elif table_name.lower() == "MaximosCamaras":
            df.rename(columns = self.column_dict_MaxCam, inplace = True)
        return df
    def exportar(self):
        # Validate table selection
        # Use the stored real table names (Qt.UserRole) for queries
        selected_table = self.table_list.currentData()
        if not selected_table:
            QMessageBox.warning(self, "Advertencia", "Por favor selecciona al menos una tabla para exportar.")
            return
        selected_tables = [selected_table]
        
        cursor = connect.cursor()
        
        # Check if any table has date columns and determine which column name to use
        has_date_column = False
        self.date_columns_map = {}  # Map table -> date column name
        # Limpiar tabla seleccionada
        # Limpiar filas con datos vacíos
        # Iterar sobre todas las columnas de la tabla y eliminar filas donde todas las columnas son NULL o cadenas vacías

        for table in selected_tables:
            try:
                cursor.execute(f"PRAGMA table_info(\"{table}\")")
                columns = [row[1].lower() for row in cursor.fetchall()]
                
                # Check which date column exists in this table
                if "date" in columns:
                    self.date_columns_map[table] = "date"
                    has_date_column = True
                if "fecha" in columns:
                    self.date_columns_map[table] = "fecha"
                    has_date_column = True
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al consultar la tabla {table}: {str(e)}")
                return
        
        # Show date dialog if any table has date columns
        self.start_date = None
        self.end_date = None
        if has_date_column:
            dialog = DateRangeDialog()
            if dialog.exec_() == QDialog.Accepted:
                self.start_date = dialog.start_date.text()
                self.end_date = dialog.end_date.text()
            else:
                return  # User cancelled
        # si dice fecha, entonces el start date tiene formato con hora

        # File selection
        nombre_archivo, _ = QFileDialog.getSaveFileName(self, "Guardar archivo", "", "Excel Files (*.xlsx)")
        if not nombre_archivo:
            return  # User cancelled file selection
        

        desktop_path = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        
        # Export each table
        try:
            for table in selected_tables:
                self.date_column = self.date_columns_map.get(table)
                
                if self.date_column and self.start_date and self.end_date:
                    query = f"SELECT * FROM {table} WHERE {self.date_column} BETWEEN '{self.start_date}' AND '{self.end_date}'"
                    print(self.date_column)
                else:
                    query = f"SELECT * FROM {table}"
                
                df = pd.read_sql_query(query, connect)
                # Cambiar nombres de columnas si es necesario
                df= self.changeColumnNames(df, selected_table)
                output_path = os.path.join(desktop_path, f"{nombre_archivo}")
                df.to_excel(output_path, index=False)
                # Editar el excel para agrandar las columnas y se vea lindo
                wb = exl.load_workbook(output_path)
                ws = wb.active
                

                # Delete col if the header is ID
                # Iterate through columns to find headers
                for col in ws.iter_cols(1, ws.max_column):
                    if col[0].value and str(col[0].value).strip().lower() == "id":
                        ws.delete_cols(col[0].column) 
                """  for col in ws.iter_cols(1, ws.max_column):
                    if col[0].value and str(col[0].value).strip().lower() == "pelicula":
                        ws.delete_cols(col[0].column) """
                for col in ws.iter_cols(1, ws.max_column):
                    if col[0].value and str(col[0].value).strip().lower() == "ref":
                        ws.delete_cols(col[0].column) 
                for col in ws.columns:
                    max_len = 0
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_len:
                                max_len = len(str(cell.value))
                        except: 
                            pass
                    adjusted_width = (max_len + 2) * 1.5
                    ws.column_dimensions[col[0].column_letter].width = adjusted_width
                
                # Formateo: celdas vacias se pintan de blanco, celdas con información se delinean
                empty_data_fill = PatternFill(fill_type="solid", start_color="FFFFFF")
                header_fill = PatternFill(fill_type="solid", start_color="6FB8C3")
                header_font = Font(bold=True, size=12, color="FFFFFF")
                thin_border = Border(left=Side(style="thin"),right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin") )
                cell_allignement = Alignment(horizontal="center")
                for fila in ws.iter_rows(max_col=ws.max_column):
                    for celda in fila:
                        if celda.row == 1:
                            celda.fill = header_fill
                            
     
                for fila in ws.iter_rows(max_col=ws.max_column-1, max_row=ws.max_row):
                    for cell in fila:
                        cell.border = thin_border
                        cell.alignment = cell_allignement
                        if cell.row == 1:
                            cell.font = header_font
                for fila in ws.iter_rows(min_col=ws.max_column, min_row=ws.max_row):
                    for cell in fila:
                        cell.fill = empty_data_fill
                
                if table == "braqui":
                    query = f"SELECT pelicula FROM braqui WHERE pelicula IS NOT NULL and {self.date_column} BETWEEN '{self.start_date}' AND '{self.end_date}'"
                    cursor = connect.cursor()
                    cursor.execute(query)
                    results = cursor.fetchall()
                    for row, pelicula in enumerate(results, start=2):
                        pelicula_data = pelicula[0]
                    
                        if pelicula_data:
                            try:
                                if isinstance(pelicula_data, bytes):
                                    img_data = pelicula_data
                                elif isinstance(pelicula_data, str):
                                    img_data = pelicula_data.encode("latin1")
                                
                                import tempfile
                                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                                    tmp.write(img_data)
                                    tmp.flush()
                                    tmp_path = tmp.name
                                image = Image(tmp_path)
                                from PIL import Image as PILImage

                                PILImage.open(tmp_path).verify()
                            
                                image.width = 200
                                image.height = 50
                                ws.add_image(image, f"T{row}")
                                try:
                                    for row_id, row in enumerate(ws.iter_rows(min_row=2), start=2):
                                        cell = ws.cell(row=row_id, column=20)  # Columna T es la 20
                                        cell.value = ""
                                        #Ajustar el tamaño de la fila para que se vea bien la imagen
                                        ws.row_dimensions[row_id].height = 50
                                        ws.column_dimensions['T'].width = 30
                                        cell.alignment = Alignment(horizontal="center", vertical="center")
                                except Exception as e:
                                    print(f"No se pudo centrar la imagen en celda T{row}, error: {e}")
                            except Exception as e:
                                print(f"No se pudo guardar imagen en celda A{row}, error: {e}")
                        else:
                            pass
                        
                # Convirtiendo data:
               
                data_change_ix = ["Luces en consola", "Luces de puerta", "Luces de irradiación en consola", "Sistema de visualización", "Sistema anticolisión", "Interrupción de radiación en puerta", "Interrupción de radiación en panel", "Interrupción por UM", "Verificación de ambas monitoras", "Movimiento del brazo", "Movimiento del colimador", "Movimientos de la camilla", "Láseres"]
                data_change_braqui = ["Interrupcion desde la consola", "Parada de emergencia cerca de la consola", "Bloqueo de la puerta", "Indicador de posicion de la fuente", "Sistema de respaldo", "Interruptor de llave de la fuente", "Monitor de area", "Indicador luminoso de la puerta", "Conexion correcta del tubo guia", "Sistema de visualizacion", "Sistema de intercomunicacion", "Monitor de radiacion portatil"]
                data_change_halcyon = ["Ganancia de la calibracion", "Uniformidad de la calibracion"]
                data_change_600 = ["Luces en consola", "Luces de puerta", "Luces de irradiación en consola", "Sistema de visualización", "Sistema anticolisión", "Interrupción de radiación en puerta", "Interrupción de radiación en panel", "Interrupción por UM", "Verificación de ambas monitoras", "Movimiento del brazo", "Movimiento del colimador", "Movimientos de la camilla", "Láseres"]
                #target_columns = {} #Defino las columnas que quiero cambiar en un diccionario
                #data_change_set = {s.strip().lower() for s in data_change_ix}
                '''for col in ws.iter_cols(1, ws.max_column):
                    header = col[0].value
                    if header and str(header).strip().lower() in data_change_set:
                        target_columns[header] = col[0].column

                for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), start = 2):
                    for col_num in target_columns.values():
                        cell = ws.cell(row=row_idx, column=col_num)
                        if cell.value == 0 or cell.value=="0":
                            cell.value = "No Funciona"
                        elif cell.value == "1" or cell.value==1:
                            cell.value = "Funciona" '''
                self.replacing_data(ws, data_change_ix)
                self.replacing_data(ws, data_change_braqui)
                self.replacing_data(ws, data_change_halcyon)
                self.replacing_data(ws, data_change_600)


                wb.save(output_path)
            
            QMessageBox.information(self, "Éxito", f"Datos exportados correctamente a {output_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error durante la exportación: {str(e)}")
    
    def replacing_data(self,ws, column_titles):
        target_columns = {} #Defino las columnas que quiero cambiar en un diccionario
        data_change_set = {s.strip().lower() for s in column_titles}
        for col in ws.iter_cols(1, ws.max_column):
            header = col[0].value
            if header and str(header).strip().lower() in data_change_set:
                target_columns[header] = col[0].column

        for row_id, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), start = 2):
            for col_num in target_columns.values():
                cell = ws.cell(row=row_id, column=col_num)
                if cell.value == 0 or cell.value=="0":
                    cell.value = "No Funciona"
                elif cell.value == "1" or cell.value==1:
                    cell.value = "Funciona"
        
        # Reemplazar e la columna "pelicula" por imagenes en formato visible
    
        # guardar las imagenes directamente de la base de sql y después insertarlas en el excel
     

          
        # for col in ws.iter_cols(1, ws.max_column):
        #     header = col[0].value
        #     if header and str(header).strip().lower() == "pelicula" or str(header).strip().lower()== "imagen_certificado":
        #         pelicula_column = col[0].column
        #         for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), start=2):
        #             cell = ws.cell(row=row_idx, column=pelicula_column)
        #             if cell.value is not None:
        #                 print(cell.value)
        #                 try:
        #                     if isinstance(cell.value, bytes):
        #                         img_data = cell.value
        #                     elif isinstance(cell.value, str):
        #                         img_data = cell.value.encode("latin1")
                            
        #                     import tempfile
        #                     with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        #                         tmp.write(img_data)
        #                         tmp.flush()
        #                         print(type(img_data))
        #                         tmp_path = tmp.name
        #                     image = Image(tmp_path)
        #                     from PIL import Image as PILImage

        #                     PILImage.open(tmp_path).verify()
        #                     #img = PIL.Image.open(image)
        #                     #img.show()
        #                     print(type(image))
        #                     ws.add_image(image, f"{col[0].column_letter}{row_idx}")
                            
        #                 except Exception as e:  
        #                     print(f"No se pudo guardar imagen en celda {col[0].column_letter}{row_idx}, error: {e}")
                            

                    
                       
                 



