from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QSplitter, QToolBox, QVBoxLayout, QLabel, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlQuery
from data.GraficasyTablas.unovsuno import graficarvstiempo
from data.GraficasyTablas.tablas import load_table, asignar_encabezados
from models.PDF.reportes import reporte
from services.anulacion import filtro_activo
import datetime

class PruebaDiariaIX(PruebaBasico):
    def __init__(self, user_id):
        
        import time
        t0 = time.time()
        super(PruebaDiariaIX, self).__init__()
        print(f"super().__init__: {time.time()-t0:.3f}s")
        #print("PruebaDiariaIX         __init__ called")
        self.initDATA(user_id)
        print(f"initDATA: {time.time()-t0:.3f}s")
        self.iniGUI()
        print(f"iniGUI: {time.time()-t0:.3f}s")
        load_table(self, self.boolean_colums, self.dosis_ix, 'aceleradorlineal_ix')
        print(f"load table: {time.time()-t0:.3f}s")
        asignar_encabezados(self, 'aceleradorlineal_ix')
        print(f"asignar_encabezados: {time.time()-t0:.3f}s")
        self.button_click()
        print(f"button_click: {time.time()-t0:.3f}s")

    def initDATA(self, user_id):
        self.botones_ordenados = []
        self.dosis_ix = {"tol_fot_6mv", 'tol_fot_15mv', 'tol_ele_6mev',
            'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev'} #nombre de la variable en l a base de datos no en el gui
        self.botones_finales = set()
        self.user_id = user_id
        self.graficos_mapeo1 = {}
        self.graficos_mapeo2 = {}
        self.fueradeservicio = False
        
        self.diccionario_invertido = {
            "luces_consola": ["Luces consola", "", "scatter"],
            "luces_puerta": ["Luces puerta", "", "scatter"],
            "luces_irradiacion": ["Luces irradiación", "", "scatter"],
            "sistema_visualizacion": ["Sistema visualización", "", "scatter"],
            "sistema_anticolision": ["Sistema anticolisión", "", "scatter"],
            "interruptor_radiacion_puerta": ["Interruptor radiación en puerta", "", "scatter"],
            "interruptor_radiacion_panel": ["Interruptor radiación en panel", "", "scatter"],
            "interrupcion_um": ["Interrupción por UM", "", "scatter"],
            "verificacion_monitoras": ["Verificación monitoras", "", "scatter"],
            "movimiento_brazo": ["Movimiento brazo", "", "scatter"],
            "movimiento_colimador": ["Movimiento colimador", "", "scatter"],
            "movimientos_camilla": ["Movimientos camilla", "", "scatter"],
            "laseres": ["Láseres", 2.0, "line" ],
            "telemetro": ["Telémetro", 2.0, "line"],
            "tamano_campo": ["Tamaño de campo", 2.0, "line"],
            "centrado_reticulo": ["Centrado de retículo", 2.0, "line" ],
            "tol_fot_6mv": ["Consistencia de dosis fotones 6MV", 3, "line"],
            "tol_fot_15mv": ["Consistencia de dosis fotones 15MV", 3, "line"],
            "tol_ele_6mev": ["Consistencia de dosis electrones 6MeV", 3, "line"],
            "tol_ele_9mev": ["Consistencia de dosis electrones 9MeV", 3, "line"],
            "tol_ele_12mev": ["Consistencia de dosis electrones 12MeV", 3, "line"],
            "tol_ele_15mev": ["Consistencia de dosis electrones 15MeV", 3, "line"],
            'observaciones' : ['Observaciones', '', "Na"]
        }
        
        for k, v in self.diccionario_invertido.items():
            if v[2] == "scatter":
                self.graficos_mapeo1[v[0]] = k
            elif v[2] == "line":
                self.graficos_mapeo2[v[0]] = k
            else:
                pass
        
        self.boolean_colums = self.graficos_mapeo1.values()
        print(self.boolean_colums)
    def iniGUI(self):
        self.main_layout = QHBoxLayout() #la mama
        
        archivo = 'widgets.xlsx'
        _ = self.setupBox(archivo, sheet_name = 'encabezado_ix') # me crea una box con la indo de documento widget y la hoja 
        self.date_box.setDisplayFormat("dd/MM/yyyy")
        df, n, layouts, _ = self.setupBox(archivo, 'preguntas_ix', main = False)
        self.datos_tabla = self.storeDailyTests(df)
        
        self.category1 = QWidget()       
        self.category2 = QWidget()
        self.category3 = QWidget()
        self.category4 = QWidget()
        
        toolbox= QToolBox()
        self.general_layout.addWidget(toolbox)
        
        i = 1
        for layout in layouts: 
            name = f'category{i}'
            getattr(self, name).setLayout(layout)
            i+=1
        
        toolbox.addItem(self.category1, 'SEGURIDAD')
        toolbox.addItem(self.category2, 'ASPECTOS MECÁNICOS')
        toolbox.addItem(self.category3, 'ASPECTOS DOSIMÉTRICOS')
        toolbox.addItem(self.category4, 'OBSERVACIONES')
        
        _ = self.setupBox(archivo, 'btn')
                
        self.btn_add.setObjectName("boton_nofunciona")
        self.btn_add.setEnabled(False)
        self.btn_add.setProperty("estado", "noselected")
        
        ## GRAFICOS
        self.edit_table_tools = self.createTable(df=df, headers=None)
        
        # Crear zona de graficas
        menu_graficas = ['Seleccione...','Seguridad', 'Aspectos mecánicos', 'Aspectos dosimétricos']
        lista = [valor[0] for valor in  self.diccionario_invertido.values()]
        graf_1 = lista[:9]
        graf_1.insert(0, 'Seleccione...')    
        graf_2 = lista[9:16]
        graf_2.insert(0, 'Seleccione...')
        graf_3 = lista[16:22]
        graf_3.insert(0, 'Seleccione...')
        graf_3.append("Datos dosimétricos vs tiempo")
        graficos = [graf_1, graf_2, graf_3]
        
        date_limit, self.canvas, self.menu_graficar, self.graficar = self.plotterSpaceEX(menu_graficas, graficos)
        
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
        self.col2_1.addLayout(self.edit_table_tools)
        
        self.wf2 = QSplitter(Qt.Orientation.Vertical)
        
        self.widgetgrafica = QWidget()
        self.widgetgrafica.setLayout(self.col2)
        
        self.widgettabla = QWidget()
        self.widgettabla.setLayout(self.col2_1)
        
        self.wf2.addWidget(self.widgetgrafica)
        self.wf2.addWidget(self.widgettabla)
        
        self.wf = QWidget()
        self.wf.setLayout(self.general_layout)
        
        self.splitter_principal = QSplitter(Qt.Orientation.Horizontal)
        self.splitter_principal.addWidget(self.wf)
        self.splitter_principal.addWidget(self.wf2)
        
        self.main_layout.addWidget(self.splitter_principal)
        
        self.setLayout(self.main_layout)
        
        self.setupButtonConnections(df, maquina= 'ix')

    def mostrar_submenu(self):
        self.graficar[0].hide()
        self.graficar[0].setCurrentIndex(0)
        self.graficar[1].hide()
        self.graficar[1].setCurrentIndex(0)
        self.graficar[2].hide()
        self.graficar[2].setCurrentIndex(0)
        selection = self.menu_graficar.currentIndex()
        
        if selection == 1:
            self.graficar[0].show()
            self.graficar[1].hide()
            self.graficar[2].hide()
        elif selection == 2:
            self.graficar[0].hide()
            self.graficar[1].show()
            self.graficar[2].hide() 
        elif selection == 3:    
            self.graficar[0].hide()
            self.graficar[1].hide()
            self.graficar[2].show()
        else:
            self.graficar[0].hide()
            self.graficar[1].hide()
            self.graficar[2].hide()

    
    
    def button_click(self):
        
        self.fuera_servicio.clicked.connect(self.reasignar_botonySERVICIO)
        self.btn_add.clicked.connect(lambda _, maquina='aceleradorlineal_ix' :self.ordenar_botones(maquina, self.fueradeservicio))
        #self.btn_add.clicked.connect(lambda _, maquina='aceleradorlineal_ix' : add_info(self, maquina, [self.boolean_colums, self.dosis_ix]))
        #self.btn_add.clicked.connect(self.clean_info)
        #self.btn_clean.clicked.connect(lambda _: self.clean_info(imagenes=False))
        if self.btn_clean.clicked:
            self.btn_clean.clicked.connect(lambda _: self.clean_info(imagenes=False))
        
        self.btn_submit.clicked.connect(
            lambda _, maquina=self.mach_name2.text(), id_maquina=self.code_1.text(): 
                reporte(self, fecha = self.date_box.date().toString('yyyy-MM-dd'), 
                        maquina = maquina, id_maquina=id_maquina, tipo_reporte='diario', 
                        diccionario=self.diccionario_invertido, umbrales= "si")
        )
        
        for line in self.df_lines:
            dato = getattr(self, line)
            dato.textChanged.connect(lambda _, line=line: self.checkBotonesFinales(line, ix = True))
        
        self.btn_delete.clicked.connect(lambda _, maquina = 'aceleradorlineal_ix' : self.verificar_eliminar(maquina, [self.boolean_colums, self.dosis_ix]))
        self.menu_graficar.currentIndexChanged.connect(self.mostrar_submenu)
        for grafica in self.graficar:
            grafica.currentIndexChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))
            self.btn_submit.clicked.connect(lambda _, grafica = grafica: self.plotter(grafica)) 
            self.limit1.dateChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))
            self.limit2.dateChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))
        
        
        self.search_bar.textChanged.connect(self.filtrarTabla)  # Conectar evento de búsqueda
        
        
        self.edit_table.clicked.connect(self.verificar_editar)
        
        
        self.accept_edit.clicked.connect(lambda: self.cargarDatosEditados(self.item, self.old_value, "aceleradorlineal_ix"))
        self.accept_edit.clicked.connect(lambda: load_table(self, self.boolean_colums, self.dosis_ix, 'aceleradorlineal_ix'))
        self.accept_edit.clicked.connect(lambda:asignar_encabezados(self, 'aceleradorlineal_ix'))
        
        
        self.cancel_edit.clicked.connect(lambda: self.cancelarEdicion(self.item, self.old_value))
        
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
            print("consultando db")
            # Preparar la consulta
            # LR3 (DA-47/DA-48): lectura de BLOQUE por fecha, mismo criterio
            # que seiscientos.py (filtro + ORDER BY, ver allí).
            query.prepare(f"""
                SELECT * FROM aceleradorlineal_ix 
                WHERE date = ?{filtro_activo('aceleradorlineal_ix')}
                ORDER BY id DESC
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
                columnas_numericas = ['laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv',  'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
                if record.indexOf('tol_fot_6mv') != -1:
                    valor_rad_6mv = query.value('tol_fot_6mv')
                    
                    if hasattr(self, 'line_2_fot_6mv'):
                        self.line_2_fot_6mv.setText(str(valor_rad_6mv))
                        
                if record.indexOf('tol_fot_15mv') != -1:
                    valor_rad_15mv = query.value('tol_fot_15mv')
                    
                    if hasattr(self, 'line_2_fot_15mv'):
                        self.line_2_fot_15mv.setText(str(valor_rad_15mv))
                        
                if record.indexOf('tol_ele_6mev') != -1:
                    valor_rad_6mev = query.value('tol_ele_6mev')
                    
                    if hasattr(self, 'line_2_ele_6mev'):
                        self.line_2_ele_6mev.setText(str(valor_rad_6mev))
                
                if record.indexOf('tol_ele_9mev') != -1:
                    valor_rad_9mev = query.value('tol_ele_9mev')
                    
                    if hasattr(self, 'line_2_ele_9mev'):
                        self.line_2_ele_9mev.setText(str(valor_rad_9mev))
                        
                if record.indexOf('tol_ele_12mev') != -1:
                    valor_rad_12mev = query.value('tol_ele_12mev')
                    if hasattr(self, 'line_2_ele_6mev'):
                        self.line_2_ele_12mev.setText(str(valor_rad_12mev))
                        
                if record.indexOf('tol_ele_15mev') != -1:
                    valor_rad_15mev = query.value('tol_ele_15mev')
                   
                    if hasattr(self, 'line_2_ele_15mev'):
                        self.line_2_ele_15mev.setText(str(valor_rad_15mev))
                        
                        
                
                for columna_db in columnas_numericas:
                    print(self.df_lines)
                    if record.indexOf(columna_db) == -1:
                        continue
                        
                    valor = query.value(columna_db)
                    if valor is not None and str(valor).strip() != '':
                        # Buscar el widget en df_lines que corresponda
                        for line_name in self.df_lines:
                            if hasattr(self, line_name):
                                # Intentar match por nombre
                                if (columna_db in line_name.lower() or 
                                    line_name.lower() in columna_db or
                                    columna_db.replace('_', '') in line_name.lower()):
                                    
                                    line_widget = getattr(self, line_name)
                                    line_widget.setText(str(valor))
                                    print(f"✓ Cargado {columna_db}: {valor} en {line_name}")
                                    break
                
                # 3. Cargar observaciones
                if record.indexOf('observaciones') != -1:
                    obs_valor = query.value('observaciones')
                    if obs_valor and hasattr(self, 'observaciones'):
                        self.observaciones.setText(str(obs_valor))
                        print(f"✓ Cargadas observaciones")
                
                # 4. Actualizar el date_box con la fecha cargada (sin disparar señal)
                self.date_box.blockSignals(True)
                self.date_box.setDate(fecha)
                self.date_box.blockSignals(False)
                
                # 5. Verificar si se debe habilitar el botón de añadir
                self.checkBotonesFinales()
                
                print(f"✓ Datos del {fecha_str} cargados correctamente.")
                print(f"  - Botones finales: {len(self.botones_finales)}")
                
            else:
                # A4 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase A, R11): sin
                # esta rama, la pantalla conservaba los datos de la fecha
                # anterior -- guardar entonces los persistía bajo la fecha
                # nueva (dato que nadie introdujo para este día). Limpia
                # los widgets para que el físico llene desde cero.
                self._limpiar_widgets_diaria()
                self.date_box.blockSignals(True)
                self.date_box.setDate(fecha)
                self.date_box.blockSignals(False)
                self.checkBotonesFinales()
                print(f"ℹ No hay datos registrados para la fecha {fecha_str}.")

        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f"✗ Error al cargar datos: {str(ex)}")
        finally:
            db.close()

    def _limpiar_widgets_diaria(self):
        """A4: deja el formulario diario en blanco -- ni "Funciona" ni "No
        funciona" marcado, campos numéricos y observaciones vacíos. Se usa
        al llegar a una fecha sin registro (no hay dato que restaurar)."""
        self.botones_finales.clear()
        for fun, nofun in zip(self.df_bnt_funciona, self.df_bnt_nofunciona):
            btn_fun = getattr(self, fun, None)
            btn_nofun = getattr(self, nofun, None)
            if btn_fun and btn_nofun:
                btn_fun.setChecked(False)
                btn_nofun.setChecked(False)
                for boton in (btn_fun, btn_nofun):
                    boton.setProperty("estado", "noselected")
                    boton.style().unpolish(boton)
                    boton.style().polish(boton)
                    boton.update()
        for line_name in self.df_lines:
            if hasattr(self, line_name):
                getattr(self, line_name).setText("")
        if hasattr(self, 'observaciones'):
            self.observaciones.setText("")

    def plotter(self, menu):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        db = self.opeenDatabase()
        selected_chart = menu.currentText()  # QComboBox con tipos de gráfica
        if selected_chart == 'Seleccione...':
            return
        #print(selected_chart)
        start_date = self.limit1.date().toString('yyyy-MM-dd')
        #print(start_date)
        end_date = self.limit2.date().toString('yyyy-MM-dd')
        #print(end_date)

        selected_column1 = self.graficos_mapeo2.get(selected_chart, None)
        selected_column2 = self.graficos_mapeo1.get(selected_chart, None)

        limite = self.diccionario_invertido.get(selected_column1, None)
        limite = limite[1] if limite else None
        
        if selected_chart == "Datos dosimétricos vs tiempo":
            #print("Entro a datos dosimetricos vs tiempo")
            query = QSqlQuery(db)
            query.prepare(f"""
                SELECT date, tol_fot_6mv, tol_fot_15mv, tol_ele_6mev, tol_ele_9mev, tol_ele_12mev, tol_ele_15mev
                FROM aceleradorlineal_ix
                WHERE date BETWEEN :start_date AND :end_date{filtro_activo('aceleradorlineal_ix')}
                ORDER BY date ASC
            """)
            query.bindValue(":start_date", start_date)
            query.bindValue(":end_date", end_date)
            query.exec()

            x_data = []
            y_data_6mv = []
            y_data_15mv = []
            y_data_6mev = []
            y_data_9mev = []
            y_data_12mev = []
            y_data_15mev = []

            while query.next():
                val = query.value(1)
                if val is None or val == '':
                    continue
                x_data.append(query.value(0))  # la fecha
                y_data_6mv.append(float(query.value(1)))  # tol_fot_6mv
                y_data_15mv.append(float(query.value(2)))  # tol_fot_15mv
                y_data_6mev.append(float(query.value(3)))  # tol_ele_6mev
                y_data_9mev.append(float(query.value(4)))  # tol_ele_9mev
                y_data_12mev.append(float(query.value(5)))  # tol_ele_12mev
                y_data_15mev.append(float(query.value(6)))  # tol_ele_15mev
            
            date =[datetime.datetime.strptime(str(date), '%Y-%m-%d').date() for date in x_data]
            
            ax.plot(date, y_data_6mv, marker='o', label='tol_fot_6mv')
            ax.plot(date, y_data_15mv, marker='o', label='tol_fot_15mv')
            ax.plot(date, y_data_6mev, marker='o', label='tol_ele_6mev')
            ax.plot(date, y_data_9mev, marker='o', label='tol_ele_9mev')
            ax.plot(date, y_data_12mev, marker='o', label='tol_ele_12mev')
            ax.plot(date, y_data_15mev, marker='o', label='tol_ele_15mev')

            self.figure.autofmt_xdate()
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Dosis')
            ax.set_title('Datos dosimétricos vs tiempo')
            ax.grid(True)
            ax.legend()

        elif selected_column1 in [ 'laseres',
            'telemetro',
            'tamano_campo',
            'centrado_reticulo',
            'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 
            'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev'
            ]:
            #print("Entro a datos dosimetricos vs tiempo")
            query = QSqlQuery(db)
            
            graficarvstiempo(self, query, ax, 'aceleradorlineal_ix', selected_column1, selected_chart, start_date, end_date, False, limite)
        
        elif selected_column2 in [
            "luces_consola", "luces_puerta", "luces_irradiacion",
            "sistema_visualizacion", "sistema_anticolision", "interruptor_radiacion_puerta",
            "interruptor_radiacion_panel", "interrupcion_um", "verificacion_monitoras",
            "movimiento_brazo", "movimiento_colimador","movimientos_camilla"
        ]:
            query = QSqlQuery(db)
            
            graficarvstiempo(self, query, ax, 'aceleradorlineal_ix', selected_column2, selected_chart, start_date, end_date, True)
        
        # Redibuja en el canvas
        self.canvas.draw()
    
        db.close()


