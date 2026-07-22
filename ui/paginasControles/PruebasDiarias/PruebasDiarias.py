from PyQt5.QtSql import QSqlDatabase, QSqlQuery
import math, os, traceback
from data.GraficasyTablas.tablas import eliminarfilas, load_table #ya
from models.images.imagenes import  ImagenInteractiva #ya
from resources.utils.matplotlib_lazy import get_matplotlib_components
from data.ManejoDatos.lectorWidgets import DataFront  #ya
from ui.paginasGuia.dialogs import DialogAdminPermisoEliminar, DialogAdminPermisoEditar
from data.ManejoDatos.load import add_info, conectarfueradeservicio
from data.ManejoDatos import conection as _conection  # HI-1: resolucion dinamica, no import por valor
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import ACCION_EDITAR, usuario_actual as _usuario_actual
from ui.util_fechas import ancho_minimo_fecha  # I5
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QRadioButton, QLabel, QLineEdit, 
                            QComboBox, QAbstractItemDelegate, QTableWidget, QTableWidgetItem, QHeaderView, 
                            QSizePolicy, QDateEdit, QDateTimeEdit, QSplitter, QMessageBox, QAbstractItemView, 
                            QGridLayout, QScrollArea, QFileDialog, QDialog)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import *


class PruebaBasico(QWidget):
    def __init__(self, user_id=None):
        super(PruebaBasico, self).__init__()
        self.general_layout = QVBoxLayout()
        self.archivo = None

    def setupBox(self, documento, sheet_name, main=True):
        if not hasattr(self, 'general_layout') or self.general_layout is None:
            self.general_layout = QVBoxLayout()
        datos = DataFront(documento, sheet_name )
        df, n = datos.extrdatos()
    
        layouts, comboboxes = self.createInterface(df, n)
        if main is True:
            for layout in layouts:
                self.general_layout.addLayout(layout)
            return comboboxes
        elif main is False:
            return df, n, layouts, comboboxes

    """Se hace en este archivo para que sea una función compartida entre las clases de braquiterapia.py (esta función solo cambia el diccionario a usar, por eso es una entrada)"""
    def init_data(self, user_id, diccionario):
        self.botones_ordenados = []
        self.graficos_mapeo1 = {}
        self.graficos_mapeo2 = {}
        self.botones_finales = set()
        self.user_id = user_id
        self.fueradeservicio = False
        self.diccionario_invertido = diccionario

        for k, v in diccionario.items():
            if v[2] == "scatter":
                self.graficos_mapeo1[v[0]] = k
            elif v[2] == "line":
                self.graficos_mapeo2[v[0]] = k

        self.boolean_colums = self.graficos_mapeo1.values()
        self.actividad_ciclos = {'tol_rep_act_ci', 'tol_exp_act', 'tol_cyc_dummy', 'tol_cyc_rad'}

    """ Construye todo el layout compartido entre PruebaDiariaBraq y CambioFuente:
        incluye menú de gráficas, canvas, tabla editable, y configuración del splitter principal."""
    def init_ui(self, df, diccionario_invertido, maquina='braqui', graficas_personalizadas=None, mostrar_fechas_limite=True):
        # Usar gráficas personalizadas si se proporcionan, sino usar las por defecto
        if graficas_personalizadas:
            menu_graficas, graficos = graficas_personalizadas
        else:
            # Menús de gráficas por defecto (para diarias)
            menu_graficas = ['Seleccione...', 'Seguridad', 'Aspectos dosimétricos']
            lista = [valor[0] for valor in diccionario_invertido.values() if valor[0] != 'Observaciones']
            graf_1 = ['Seleccione...'] + lista[:12]
            graf_2 = ['Seleccione...'] + lista[12:] + ['Actividad vs tiempo', 'Ciclos vs tiempo']
            graficos = [graf_1, graf_2]

        # Canvas y menús
        date_limit, self.canvas, self.menu_graficar, self.graficar = self.plotterSpaceEX(menu_graficas, graficos)

        # Ocultar fechas límite si no se necesitan
        if not mostrar_fechas_limite:
            self.limit1name.hide()
            self.limit1.hide()
            self.limit2name.hide()
            self.limit2.hide()

        caja_menu_graficas = QHBoxLayout()
        caja_menu_graficas.addWidget(self.menu_graficar)
        for grafica in self.graficar:
            caja_menu_graficas.addWidget(grafica)

        self.settfigure = QHBoxLayout()
        self.settfigure.addLayout(caja_menu_graficas)

        # COLUMNA DRECHA - gráfica (Arriba)
        self.col2 = QVBoxLayout()
        self.col2.addLayout(self.settfigure)
        self.col2.addLayout(date_limit)
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

    "Define el comportamiento de los widgets que vienen desde el excel (Es decir, que hacer cuando es QLineEdit o más)"
    def createInterface(self, matriz, n, sheet_name = None):
        layouts = {}
        comboboxes = []

        # Crear layouts por nombre único en vez de numerarlos
        pruebas = matriz['prueba'].unique()
        for prueba in pruebas:
            name = f'layout{prueba}'
            layout = QGridLayout()
            setattr(self, name, layout)
            layouts[prueba] = layout

        for index, row in matriz.iterrows():
            nombre = row['nombres']
            widget_type = row['widget_type']
            descripcion = row['descripcion']
            prueba = row['prueba']
            pose = row['pose']

            if widget_type == 'QPushButton':
                boton = QPushButton(descripcion)
                boton.setCheckable(True)  
                setattr(self, nombre, boton)

            elif widget_type == 'QRadioButton':
                boton = QRadioButton(descripcion)
                setattr(self, nombre, boton)

                if hasattr(self, 'es_calibracion_redundante') and self.es_calibracion_redundante:
                    boton.hide()
                    if not hasattr(self, 'label_tipo_calibracion'):
                        self.label_tipo_calibracion = QLabel("Calibración Redundante")
                        layouts[prueba].addWidget(self.label_tipo_calibracion, *pose)
                else:
                    layouts[prueba].addWidget(boton, *pose)

            elif widget_type in ['QLabel', 'QLabel no usable']:
                setattr(self, nombre, QLabel(descripcion))
                getattr(self, nombre).setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            elif row['widget_type'] == 'QLabel Soft':
                label = QLabel(descripcion)
                # Si descripcion puede traer HTML con <b>, descomenta la siguiente línea:
                # label.setTextFormat(Qt.PlainText)
                font = label.font()
                font.setBold(False)  # quitar negrita
                label.setFont(font)
                label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                label.setStyleSheet("color: #5C5C5C; font-weight: normal;")
                setattr(self, nombre, label)
            elif widget_type == 'QLineEdit':
                print(
                    "ANTES ADD:",
                    nombre,
                    hasattr(self, nombre)
                )
                setattr(self, nombre, QLineEdit())
                print("CREADO:", nombre)
                if isinstance(descripcion, float) and math.isnan(descripcion):
                    descripcion = ""
                getattr(self, nombre).setPlaceholderText(str(descripcion))

            elif row['widget_type'] == 'QLineEdit block':
                setattr(self, row['nombres'],  QLineEdit())

                if isinstance(row['descripcion'], float) and math.isnan(row['descripcion']):
                    row['descripcion'] = " "
                    getattr(self, row['nombres']).setText('N/a')
                else:
                    getattr(self, row['nombres']).setText(str(row['descripcion']))  # Convierte a str solo si no es NaN
                    
                getattr(self, row['nombres']).setReadOnly(True)
                
            elif widget_type == 'QComboBox':
                combo = QComboBox()
                combo.addItem(str(descripcion))
                comboboxes.append([combo, prueba])
                setattr(self, nombre, combo)

                if prueba and prueba.lower() == "seguridad":
                    layouts[prueba].setHorizontalSpacing(10)
                    layouts[prueba].setVerticalSpacing(10)

                layouts[prueba].addWidget(combo, *pose)
                
            elif widget_type == 'QDateEdit':
                setattr(self, nombre, QDateEdit())
                getattr(self, nombre).setCalendarPopup(True)
                getattr(self, nombre).setDate(QDate.currentDate())
                # H3.5/I5: sin un piso, la flecha del calendario se come el
                # espacio del texto cuando el layout aprieta el widget. Los
                # 100px fijos de H3.5 quedaron cortos con la fuente real de
                # Windows (reporte del físico 16-07): el mínimo se calcula
                # ahora de la métrica de fuente del propio widget, con el
                # formato más ancho en uso (dd/MM/yyyy) porque los
                # formularios mensuales cambian a "MM/yyyy" DESPUÉS de crear.
                getattr(self, nombre).setMinimumWidth(
                    ancho_minimo_fecha(getattr(self, nombre),
                                       formato="dd/MM/yyyy"))

            elif widget_type == 'QDateTimeEdit':
                setattr(self, nombre, QDateTimeEdit())
                getattr(self, nombre).setCalendarPopup(True)
                getattr(self, nombre).setDateTime(QDateTime.currentDateTime())
                getattr(self, nombre).setDisplayFormat("yyyy-MM-dd HH:mm:ss")

            # Finalmente, agregar al layout correspondiente (excepto QRadioButton que ya fue agregado antes)
            if widget_type != 'QRadioButton':
                layouts[prueba].addWidget(getattr(self, nombre), *pose)
            # al final de createInterface

            if not hasattr(self, "widgets"):
                self.widgets = {}
            self.widgets[nombre] = getattr(self, nombre)

        return list(layouts.values()), comboboxes

    def createTable(self, df=None, headers=None):
        if df is not None:
            self.table = QTableWidget ()
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)# crea la tabla
            
        elif headers is not None:  
            l = len(headers)
            self.table = QTableWidget ()       # crea la tabla
            self.table.setColumnCount(l) #numero de columnas 
            self.table.setHorizontalHeaderLabels(headers)
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
        self.table.verticalHeader().setVisible(False) 
        
        
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
        
        return edit_table_tools

    def filtrarTabla(self):
        texto_busqueda = str(self.search_bar.text()).lower()  # Obtener texto en minúsculas
        for fila in range(self.table.rowCount()):
            mostrar_fila = False
            for columna in range(self.table.columnCount()):
                item = self.table.item(fila, columna)
                if item and texto_busqueda in item.text().lower():
                    mostrar_fila = True
                    break  # Si encuentra una coincidencia en la fila, no sigue buscando

            # Mostrar u ocultar la fila según si hubo coincidencia
            self.table.setRowHidden(fila, not mostrar_fila)

    def storeDailyTests(self, df):
        todo = []
        self.df_bnt_funciona = df.loc[df.descripcion == 'Funciona']['nombres']
        self.df_bnt_nofunciona = df.loc[df.descripcion == 'No funciona']['nombres'] 
        self.df_lines = df.loc[df.widget_type == 'QLineEdit']['nombres']
        self.df_lines = [line for line in self.df_lines if line != "observaciones"]

        for btn_si, btn_no in zip(self.df_bnt_funciona, self.df_bnt_nofunciona): 
            dato = getattr(self, btn_si)
            dato = (dato, btn_si)
            todo.append(dato)
            dato1 = getattr(self, btn_no)
            dato1 = (dato1, btn_no)
            todo.append(dato1)
            
        return todo

    " Configura el estilo de los botones Funciona y No Funciona"
    def setupButtonConnections(self, df, maquina = None):
        self.df_bnt_funciona = df.loc[df.descripcion == 'Funciona']['nombres']
        self.df_bnt_nofunciona = df.loc[df.descripcion == 'No funciona']['nombres'] 
        self.df_lines_dosis = df.loc[(df.widget_type == 'QLineEdit') & (df.prueba == 'aspectos dosimetricos')]['nombres']
        self.df_lines_dosis = [line for line in self.df_lines_dosis]

        self.df_lines = df.loc[df.widget_type == 'QLineEdit']['nombres']
        self.df_lines = [line for line in self.df_lines if line != "observaciones"]

        for fun, nofun in zip(self.df_bnt_funciona, self.df_bnt_nofunciona):
            btn_fun = getattr(self, fun)
            btn_fun.setObjectName("boton_funciona")
            btn_nofun = getattr(self, nofun)
            btn_nofun.setObjectName("boton_nofunciona")
            if maquina == 'ix':
                btn_fun.clicked.connect(lambda _, a = (btn_fun, fun) , b = (btn_nofun, nofun): self.completar(a, b, maquina))
                btn_nofun.clicked.connect(lambda _, a=(btn_nofun, nofun), b=(btn_fun, fun) : self.completar(a, b, maquina))
            else:
                btn_fun.clicked.connect(lambda _, a = (btn_fun, fun) , b = (btn_nofun, nofun): self.completar(a, b))
                btn_nofun.clicked.connect(lambda _, a=(btn_nofun, nofun), b=(btn_fun, fun) : self.completar(a, b))

    def cargar_dailytest_desde_db(self):
        return 
        
    def completar(self, selected, rejected, maquina = None):
        selected_btn = selected[0]
        rejected_btn = rejected[0]
        self.cambiar_estilo(selected_btn, rejected_btn)
        self.otra_funcion(selected, rejected, maquina=maquina)

    # Cambia el estilo de los botones seleccionados y los que no se seleccionan también cambian
    def cambiar_estilo(self, selected, rejected):
        # Use setProperty AND style().polish() for more reliable styling
        selected.setProperty("estado", "selected")
        selected.style().unpolish(selected)
        selected.style().polish(selected)
        
        rejected.setProperty("estado", "noselected")
        rejected.style().unpolish(rejected)
        rejected.style().polish(rejected)
        
        # Force update of the widget
        selected.update()
        rejected.update() 

    def otra_funcion(self, selected, refected, maquina =None):
        # Extraemos solo los botones de las tuplas en el set
        botones_existentes = {boton for boton, _ in self.botones_finales}
        
        if refected[0] in botones_existentes:
            # Eliminamos la tupla con el botón refected
            self.botones_finales = {t for t in self.botones_finales if t[0] != refected[0]}
        
        # Agregamos la nueva tupla selected
        self.botones_finales.add(selected)
        
        if maquina == 'ix':
            self.checkBotonesFinales(ix = True)    

    def checkLineEdits(self, ix=False): 
        #print("Entra a checkLineEdits ")
        if ix:
            for line in self.df_lines : #and self.df_lines_parciales: #self.df_lines = df.loc[df.widget_type == 'QLineEdit']['nombres']
                if line not in self.df_lines_dosis:
                    dato = getattr(self, line)
                    if not dato.text().strip():
                        return False
            for line in self.df_lines_dosis:
                dato = getattr(self, line)
                if dato.text().strip():
                    return True
            return False
        else:  #####NO ES UN and CAMBIA ESO      
            for line in self.df_lines : #and self.df_lines_parciales: 
                dato = getattr(self, line)
                if not dato.text().strip():
                    return False
            return True
 
    def checkBotonesFinales(self, line = None, halcyon=False,ix = False, braqui = False, otro = None):
        #print("Entra a la función checkBotonesFinales ")
        if ix:
            #print(f"    - Entra a la condición maquina IX")
            if len(self.botones_finales) == 12 and self.checkLineEdits(ix=True):
                self.btn_add.setObjectName("")
                self.btn_add.style().unpolish(self.btn_add)
                self.btn_add.style().polish(self.btn_add)
                self.btn_add.update()
                self.btn_add.setEnabled(True)
                #self.btn_add.setProperty("estado", "noselected")
       
        elif halcyon:
            #print(f"    - Entra a la condición maquina IX")
            if len(self.botones_finales) == 12 and self.checkLineEdits(ix=False):
                self.btn_add.setObjectName("")
                self.btn_add.style().unpolish(self.btn_add)
                self.btn_add.style().polish(self.btn_add)
                self.btn_add.update()
                self.btn_add.setEnabled(True)
                self.btn_add.setProperty("estado", "noselected")

        # Para que se habilite el boton de añadir para la prueba diaria de braquiterapia
        elif braqui == True and otro == "Diario":
            #print(f"    - Entra a la condición de Braqui y Diario, Otro = {otro}")
            if len(self.botones_finales) == 12 and self.checkLineEdits(ix=False) and self.archivo is not None:
                print(f"        • Cumple las condiciones de habilitar: \n          - {len(self.botones_finales)} \n          - {self.checkLineEdits(ix=False)} \n          - {self.archivo}")
                self.btn_add.setObjectName("")
                self.btn_add.style().unpolish(self.btn_add)
                self.btn_add.style().polish(self.btn_add)
                self.btn_add.update()
                self.btn_add.setEnabled(True)

        # Para que se habilite el boton de añadir para el poscionamiento inicial de la fuente de braquiterapia
        elif braqui == True and otro == "Posicionamiento Inicial":
            #print(f"    - Entra a la condición de Braqui y Posicionamiento Inicial,  Otro = {otro}")
            if self.archivo is not None:
                self.btn_add.setObjectName("")
                self.btn_add.style().unpolish(self.btn_add)
                self.btn_add.style().polish(self.btn_add)
                self.btn_add.update() 
                self.btn_add.setEnabled(True)
        #Para que se habilite el boton de añadir para la lienalidad de braquiterapia
        elif braqui == True and otro == "Linealidad Braquiterapia":
            print(f"    - Entra a la condición de Braqui y Linealidad Braquiterapia, Otro = {otro}")
            self.btn_add.setObjectName("")
            self.btn_add.style().unpolish(self.btn_add)
            self.btn_add.style().polish(self.btn_add)
            self.btn_add.update()
            self.btn_add.setEnabled(True)

        # Para que se habilite el boton de añadir para la prueba mensual de braquiterapia
        elif braqui == True and otro == "Mensual Braquiterapia":
            print(f"    - Entra a la condición de Braqui y Mensual Braquiterapia, Otro = {otro}")
            self.btn_add.setObjectName("")
            self.btn_add.style().unpolish(self.btn_add)
            self.btn_add.style().polish(self.btn_add)
            self.btn_add.update()
            self.btn_add.setEnabled(True)
        else:
            #print("    - No condiciones en CheckBotonesFinales")
            if len(self.botones_finales) == 12 and self.checkLineEdits(ix=True):
                self.btn_add.setObjectName("")
                self.btn_add.style().unpolish(self.btn_add)
                #self.btn_add.style().polish(self.btn_add)
                self.btn_add.update()
                self.btn_add.setEnabled(True)

    def menuAnidado(self, menu_graficas, graficos):
        graficar= []
        
        menu_graficar = QComboBox()
        for item in menu_graficas:
            menu_graficar.addItem(item)
        menu_graficar.model().item(0).setEnabled(False)
        
        for submenu in graficos:
            grafica = QComboBox()
            for item in submenu:
                grafica.addItem(item)
            grafica.model().item(0).setEnabled(False)
            grafica.hide()
            graficar.append(grafica)
        
        return menu_graficar, graficar

    def plotterSpaceEX(self, menu_graficas, graficos):
        # plotter
        mpl = get_matplotlib_components()
        plt = mpl['plt']
        self.figure = plt.figure()
        FigureCanvas = mpl['FigureCanvas']
        canvas = FigureCanvas(self.figure)
        
        # caja para cambiar de grafica
        menu_graficar, graficar = self.menuAnidado(menu_graficas, graficos)
        
        # fechas limite
        date_limit = QHBoxLayout()
        
        self.limit1name = QLabel('Fecha de inicio:')
        self.limit1 = QDateEdit()
        self.limit1.setCalendarPopup(True)
        self.limit1.setDate(QDate.currentDate())
        
        self.limit2name = QLabel('Fecha de finalizacion:')
        self.limit2 = QDateEdit()
        self.limit2.setCalendarPopup(True)
        self.limit2.setDate(QDate.currentDate())
        
        date_limit.addWidget(self.limit1name)
        date_limit.addWidget(self.limit1)
        date_limit.addWidget(self.limit2name)
        date_limit.addWidget(self.limit2)
        
        return date_limit, canvas, menu_graficar, graficar

    def opeenDatabase(self):
        try:
            if not QSqlDatabase.contains("qt_sql_default_connection"):
                db = QSqlDatabase.addDatabase("QSQLITE")
                db.setDatabaseName(_conection.ruta_base_datos())
            else:
                db = QSqlDatabase.database("qt_sql_default_connection")

            if not db.open():
                raise Exception(f"No se pudo abrir la base de datos: {db.lastError().text()}")

            return db

        except Exception as ex:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error en conexión a la base de datos:\n{str(ex)}")
            return None

    def verificar_eliminar(self, maquina, lista): #APROBADO POR CHAYAN
        selected_row = self.table.currentRow()  # Revisa qué fila está seleccionada

        if selected_row == -1:
            QMessageBox.warning(self, 'Error', 'Por favor elija una fila para eliminar')
            return  
        
        dialogo = DialogAdminPermisoEliminar(self.user_id)
        respuesta = dialogo.exec()
        self.delete_info(maquina, lista) if respuesta == QDialog.DialogCode.Accepted else None

    def delete_info(self, maquina, listas):
        eliminarfilas(self, maquina)
        if isinstance(listas, list):
            load_table(self, listas[0], listas[1], maquina)
        else:
            load_table(self, listas[0], listas[1], maquina)

    def ordenar_botones(self, maquina, fueraservicio = False, otro = None):
        #print("Entra a la función ordenar_botones en PruebasDiarias.py")
        if fueraservicio != True:  
            #print(" ! Condición NO fuera de servicio")
            # Obtener la lista de referencia con el orden correcto
            lista_referencia = self.datos_tabla
            # Convertir la lista de referencia en un diccionario {objeto: índice} para ordenar rápido
            orden_referencia = {dato: i for i, dato in enumerate(lista_referencia)}
            # Filtrar `self.botones_finales` para conservar solo los que están en la referencia
            self.botones_ordenados = sorted(
                (boton for boton in self.botones_finales if boton in orden_referencia),
                key=lambda x: orden_referencia[x]  # Ordenar según la referencia
            )
            if maquina == 'braqui' and (otro == "Diario" or otro == "Mensual Braquiterapia"):
                print("    * Entra al if de si es braqui y Diario o Mensual en la función ordenar_botones")
                distancias, promedio, desviacion, desplazamientos, promedio_des, desviacion_des = self.guardar_datos()
                add_info(
                    self, 'braqui', [self.boolean_colums, self.actividad_ciclos], imagenes=self.archivo,
                    distancias=distancias, promedio=promedio, desviacion=desviacion,
                    desplazamientos=desplazamientos, promedio_des=promedio_des, desviacion_des=desviacion_des
                )
                #print("Después del add_info función ordenar_botones")
            if maquina == 'braqui' and (otro == "Posicionamiento Inicial"):
                #print("    * Entra al if de si es braqui y Posicionamiento Incial en la función ordenar_botones")
                
                #print("Después del add_info función ordenar_botones")
                pass
            elif maquina == 'aceleradorlineal_600':
                add_info(self, maquina, [self.boolean_colums, self.dosis])
            elif maquina == 'aceleradorlineal_ix':
                print('entro a la funcion de ordenacion')
                add_info(self, maquina, [self.boolean_colums, self.dosis_ix])
        else:
            #print(" ! Condición fuera de servicio")
            conectarfueradeservicio(self, maquina)
            if maquina == 'aceleradorlineal_600':
                load_table(self, self.boolean_colums, self.dosis, maquina)
            elif maquina == 'aceleradorlineal_ix':
                load_table(self, self.boolean_colums, self.dosis_ix, maquina)

    def clean_info(self, imagenes = False):
        for boton in self.datos_tabla:
            # Quitar propiedad 'estado'
            boton[0].setProperty("estado", "")
            boton[0].style().unpolish(boton[0])
            boton[0].style().polish(boton[0])
            boton[0].update()
        self.botones_finales.clear()
        print("Limpiando data")
        
        try:
            self.botones_ordenados.clear()
            
        except ValueError:
            pass   

        for line in self.df_lines:
            dato = getattr(self, line)
            dato.clear()
        
        self.btn_add.setObjectName("boton_nofunciona")
        self.btn_add.style().unpolish(self.btn_add)
        self.btn_add.style().polish(self.btn_add)
        self.btn_add.setEnabled(False)
        self.btn_add.setProperty("estado", "noselected")
        
        if imagenes:
            self.resetear_imagen_ui()

    

    def verificar_editar(self): 
        print(f"\n* Pide el usuario para editar")
        row = self.table.currentRow()
        col = self.table.currentColumn()

        if row == -1 or col == -1:
            QMessageBox.warning(self, 'Error', 'Por favor elija una celda para editar')
            return
        
        dialogo = DialogAdminPermisoEditar(self.user_id)
        respuesta = dialogo.exec()
        if respuesta == QDialog.DialogCode.Accepted:
            self.edicionTabla()


    def edicionTabla(self):
        print(f"¡ Método para editar pruebas diarias")
        row = self.table.currentRow()
        col = self.table.currentColumn()

        if row == -1 or col == -1:
            QMessageBox.warning(self, 'Error', 'Por favor elija una celda para editar')
            return

        # Verifica si la celda contiene un widget
        cell_widget = self.table.cellWidget(row, col)
        if cell_widget:
            # Suponiendo que el widget contiene un QLabel
            label = cell_widget.findChild(QLabel)
            if label:
                current_value = label.text()
                self.old_value = current_value
                # Remueve el widget
                self.table.removeCellWidget(row, col)
                # Crea un QTableWidgetItem editable con el texto actual
                self.item = QTableWidgetItem(current_value)
                self.item.setFlags(self.item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, self.item)
                self.table.editItem(self.item)
            else:
                QMessageBox.warning(self, 'Error', 'No se encontró un QLabel en el widget.')
                return
        else:
            # Si la celda no contiene widget, usar el comportamiento por defecto
            self.item = self.table.item(row, col)
            if self.item:
                self.old_value = self.item.text()
                # Evitar editar columnas no permitidas (ejemplo: id o booleanas)
                column_name = self.table.horizontalHeaderItem(col).text().lower()
                if column_name in ["id", "user_id"] or column_name in self.boolean_colums:
                    QMessageBox.warning(self, 'Error', 'No se puede editar la columna seleccionada')
                    return
                self.item.setFlags(self.item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.editItem(self.item)
            else:
                QMessageBox.warning(self, 'Error', 'Celda vacía o no editable')
                return

        self.btn_delete.hide()
        self.edit_table.hide()
        self.search_bar.hide()
        self.accept_edit.show()
        self.cancel_edit.show()

    def cancelarEdicion(self, item, old_value):
        # Bloquear señales para evitar disparos innecesarios
        self.table.blockSignals(True)
        # Revertir el texto al valor original
        item.setText(old_value)
        # Deshabilitar la edición para la celda
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.blockSignals(False)
        # Si el editor está activo, forzar su cierre
        self.table.closeEditor(self.table.focusWidget(), QAbstractItemDelegate.EndEditHint.NoHint)
        # Restaurar la interfaz
        self.btn_delete.show()
        self.edit_table.show()
        self.search_bar.show()
        self.accept_edit.hide()
        self.cancel_edit.hide()
        QMessageBox.information(self, "Cancelado", "Edición cancelada, cambios revertidos.")

    def cargarDatosEditados(self, item, old_value, database):  
        # Desconectar la señal para evitar llamadas múltiples
        try:
            self.table.itemChanged.disconnect(self.cargarDatosEditados)
        except TypeError:
            pass
        except Exception:
            import traceback
            traceback.print_exc()
            pass

        new_value = item.text()

        # Si el valor no cambió, se omite la actualización
        if new_value == old_value:
            QMessageBox.information(self, "Info", "No se realizaron cambios.")
            self.edit_table.show()
            self.search_bar.show()
            self.accept_edit.hide()
            self.cancel_edit.hide()
            self.btn_delete.show()
            return

        row = item.row()
        col = item.column()
        id_value = self.table.item(row, 0).text()  # Asumiendo que col 0 es siempre el ID

        # ✅ Usar el nombre real de columna desde el mapping
        column_name = self.encabezados_actuales.get(col)
        if not column_name:
            QMessageBox.critical(self, "Error", f"No se encontró mapeo para la columna {col}")
            return

        # Actualizar la base de datos
        db = self.opeenDatabase()
        query = QSqlQuery(db)
        query.prepare(f"UPDATE {database} SET {column_name} = ? WHERE id = ?")
        query.addBindValue(new_value)
        query.addBindValue(id_value)

        if not query.exec():
            QMessageBox.critical(self, "Error", f"Error al actualizar: {query.lastError().text()}")
        elif query.numRowsAffected() == 0:
            # Un UPDATE cuyo WHERE no coincide con ninguna fila no es error en SQL:
            # antes se reportaba "actualizado correctamente" sin haber cambiado nada.
            QMessageBox.warning(self, "Atención",
                                f"Ningún registro con id {id_value} fue modificado: "
                                "el cambio NO se guardó. Recargue la tabla e intente de nuevo.")
        else:
            db.commit()
            # A3-bis (§8.1 H2, PLAN_AUDITORIA_DOS_EJES_21-07): la edición
            # DIARIA no dejaba ningún rastro -- A3 solo cubrió editar_tablas
            # (load.py, rutas mensual/anual). El físico la veía aparecer como
            # un "login" (era la reautenticación de DialogAdminPermisoEditar,
            # ver A8) y sospechaba, con razón, que el cambio real no quedaba
            # registrado en ningún lado.
            _registrar_auditoria(
                _usuario_actual(self), ACCION_EDITAR, database,
                ref=str(id_value),
                detalle=f"{column_name}: '{old_value}' → {new_value}")
            QMessageBox.information(self, "Éxito", "Registro actualizado correctamente.")

        db.close()

        self.edit_table.show()
        self.search_bar.show()
        self.accept_edit.hide()
        self.cancel_edit.hide()
        self.btn_delete.show()

        # Recargar la tabla para reflejar el cambio
        # (si tienes función de recarga, la llamarías aquí)

    def imagenUpLoader(self, analisis = True):  
        widget_imagen = QWidget()
        layout_imagen = QVBoxLayout(widget_imagen)

        # Scroll area para la imagen
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.zoom_factor = 1.0
        
        # Imagen inicial (placeholder)
        self.label_imagen = ImagenInteractiva()
        self.label_imagen.setAlignment(Qt.AlignCenter)
        self.label_imagen.setText("Subir imagen")
        self.label_imagen.setStyleSheet("color: gray; font-size: 18px;")
        
        self.scroll_area.setWidget(self.label_imagen)
        layout_imagen.addWidget(self.scroll_area)
        
        # Botones principales
        self.boton_subir = QPushButton("Seleccionar Imagen")
        self.boton_aceptar = QPushButton("Aceptar")
        self.boton_cancel = QPushButton("Cancelar")
        self.boton_zoom_mas = QPushButton("Zoom +")
        self.boton_zoom_menos = QPushButton("Zoom -")

        # Estado inicial de los botones
        self.boton_aceptar.hide()
        self.boton_cancel.hide()
        self.boton_zoom_mas.setEnabled(False)
        self.boton_zoom_menos.setEnabled(False)
        self.boton_zoom_mas.hide()
        self.boton_zoom_menos.hide()

        # Layout de botones
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(self.boton_subir)
        botones.addWidget(self.boton_aceptar)
        botones.addWidget(self.boton_cancel)
        botones.addWidget(self.boton_zoom_mas)
        botones.addWidget(self.boton_zoom_menos)
        botones.addStretch()

        layout_imagen.addLayout(botones)
        self.botones_layout = botones

        self.layout_canvas = QVBoxLayout()
        layout_imagen.addLayout(self.layout_canvas) 
        self.layout_imagen = layout_imagen

        # Conexiones
        self.boton_zoom_mas.clicked.connect(self.zoom_mas)
        self.boton_zoom_menos.clicked.connect(self.zoom_menos)
        self.boton_subir.clicked.connect(lambda: self.subir_imagen(analisis=analisis))
        self.boton_subir.clicked.connect(lambda: print("Subir imagen activado en imagenUpLoader en PruebasDiarias.py"))

        return widget_imagen

    def subir_imagen(self, analisis = True):
        archivo, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.pdf *.tif)")
        if archivo: #cambiar nombre a imagen algo pero no es solo para braqui
            self.imagen_path = archivo
            self.archivo = archivo
            self.pixmap_original = QPixmap(archivo)
            self.zoom_factor = 0.5
            self.actualizar_imagen()
            #self.preguntar_parametros()

            if not hasattr(self, "zoomConnected") or not self.zoomConnected:
                self.label_imagen.ruedaScroll.connect(self.zoom_rueda)
                self.zoomConnected = True
            
            self.boton_subir.hide()
            self.boton_aceptar.show()
            if analisis:
                print("Analisis de imagen activado en subir_imagen en PruebasDiarias.py")
                self.boton_aceptar.clicked.connect(self.analizar_imagen)  
                print("analizando imagen") 
                self.boton_aceptar.clicked.connect(lambda:print("Aceptar imagen activado en PruebasDiarias.py"))
                #self.btn_add.clicked.connect(self.clean_info)
                
            else:
                self.boton_aceptar.clicked.connect(lambda:print("Archivo: ", archivo))   
            
            self.boton_cancel.show()
            self.boton_zoom_mas.setEnabled(True)
            self.boton_zoom_mas.show()
            self.boton_zoom_menos.setEnabled(True)
            self.boton_zoom_menos.show()

    def subirlisto(self):
        self.boton_aceptar.hide()
        self.boton_cancel.hide()

        if not hasattr(self, 'agregar_imagen') or self.agregar_imagen is None or self.agregar_imagen not in [self.botones_layout.itemAt(i).widget() for i in range(self.botones_layout.count())]:
            self.agregar_imagen = QPushButton("Seleccionar otra Imagen")
            self.agregar_imagen.setFixedSize(210, 35)
            self.agregar_imagen.setStyleSheet("background-color: rgb(58, 155, 190); color: white; font-size: 16px; border-radius: 5px;")
            self.agregar_imagen.clicked.connect(self.subir_imagen)
            self.botones_layout.insertWidget(0, self.agregar_imagen)


    
    def cancelarbraqui(self):
        self.archivo = None
        self.pixmap_original = QPixmap()

        atributos  = ["label_imagen", "boton_aceptar", "boton_cancel", "boton_zoom_mas", "boton_zoom_menos", "boton_seubir"]
        
        if any(hasattr(self, attr) for attr in atributos) and self.label_imagen is not None:
            self.label_imagen.clear()
            self.label_imagen.setText("Subir imagen")
            self.boton_aceptar.hide()
            self.boton_cancel.hide()
            self.boton_zoom_mas.hide()
            self.boton_zoom_menos.hide()
            self.boton_subir.show()
        if hasattr(self, 'parametros_layout') and self.parametros_layout is not None:
            # Elimina widgets del layout
            while self.parametros_layout.count():
                item = self.parametros_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            self.parametros_layout = None

    def actualizar_imagen(self):
        if not self.pixmap_original.isNull():
            ancho = int(self.pixmap_original.width() * self.zoom_factor)
            alto = int(self.pixmap_original.height() * self.zoom_factor)
            pixmap_zoom = self.pixmap_original.scaled(
                ancho, alto,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.label_imagen.setPixmap(pixmap_zoom)

    def upload_image(self, SAVE_FOLDER):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Imagen", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)")
        
        if file_path:
            filename = os.path.basename(file_path)
            save_path = os.path.join(SAVE_FOLDER, filename)
            
            with open(file_path, "rb") as f_in:
                with open(save_path, "wb") as f_out:
                    f_out.write(f_in.read())
            
            pixmap = QPixmap(save_path)
            #pixmap = pixmap.scaled(500, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            #image_label.setPixmap(pixmap)
            #scaled_pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            #image_label.setPixmap(scaled_pixmap)
            return pixmap
    
    def zoom_mas(self):
        self.zoom_factor += 0.1
        self.actualizar_imagen()

    def zoom_menos(self):
        if self.zoom_factor > 0.2:
            self.zoom_factor -= 0.1
            self.actualizar_imagen()

    def zoom_rueda(self, delta):
        if delta > 0:
            self.zoom_factor += 0.1
        elif delta < 0 and self.zoom_factor > 0.2:
            self.zoom_factor -= 0.1
        self.actualizar_imagen()

    def bloquearboton(self, boton):
        boton.setEnabled(False)
        boton.setObjectName("boton_nofunciona")
        boton.setProperty("estado", "noselected")
        boton.style().unpolish(boton)
        boton.style().polish(boton)
        boton.update()

    def reasignar_botonySERVICIO(self):
        self.btn_add.setObjectName("")
        self.btn_add.style().unpolish(self.btn_add)
        self.btn_add.style().polish(self.btn_add)
        self.btn_add.update()
        self.btn_add.setEnabled(True)
        self.fueradeservicio = True
