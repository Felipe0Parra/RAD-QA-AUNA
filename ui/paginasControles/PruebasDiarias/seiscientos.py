from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.util_formato import codigo_de_formato
from PyQt5.QtWidgets import QToolBox, QSplitter, QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlQuery
from data.GraficasyTablas.unovsuno import graficarvstiempo
from data.GraficasyTablas.tablas import load_table, asignar_encabezados
#from data.ManejoDatos.load import add_info
from models.PDF.reportes import reporte
from services.anulacion import filtro_activo
#from PyQt5.QtGui import QColor

#import datetime

class PruebaDiaria600(PruebaBasico):
    def __init__(self, user_id):
        super(PruebaDiaria600, self).__init__()
        #print("PruebaDiaria600        __init__ called")
        self.initDATA(user_id)
        self.iniGUI()
        load_table(self, self.boolean_colums, self.dosis,  "aceleradorlineal_600")
        asignar_encabezados(self, 'aceleradorlineal_600')
        self.button_click()

    def initDATA(self, user_id):
        self.botones_ordenados = []
        self.botones_finales = set()
        self.user_id = user_id
        #print(f'User en init dataseicientos :{self.user_id}')
        self.fueradeservicio = False

        self.graficos_mapeo1 = {}
        self.graficos_mapeo2 = {}

        self.diccionario_invertido = {
            "luces_consola": ["Luces consola", '', "scatter"],
            "luces_puerta": ["Luces puerta", '', "scatter"],
            "luces_irradiacion": ["Luces irradiacion",'', "scatter"],
            "sistema_visualizacion": ["Sistema visualizacion",'', "scatter"],
            "sistema_anticolision": ["Sistema anticolision",'', "scatter"],
            "interruptor_radiacion_puerta": ["Interruptor radiacion en puerta",'', "scatter"],
            "interruptor_radiacion_panel": ["Interruptor radiacion en panel",'', "scatter"],
            "interrupcion_um": ["Interrupcion por UM",'', "scatter"],
            "verificacion_monitoras": ["Verificacion monitoras",'', "scatter"],
            "movimiento_brazo": ["Movimiento brazo",'', "scatter"],
            "movimiento_colimador": ["Movimiento colimador",'', "scatter"],
            "movimientos_camilla": ["Movimientos camilla",'', "scatter"],
            "laseres": ["Laseres", 2.0, "line"],
            "telemetro": ["Telemetro", 2.0, "line"],
            "tamano_campo": ["Tamano campo", 2.0, "line"],
            "centrado_reticulo": ["Centrado de reticulo", 2.0, "line"],
            "dosis_referencia": ["Constancia de dosis para 6MV", 3, "line"],
            "observaciones": ["Observaciones", "", "Na"]
        }

        for k, v in self.diccionario_invertido.items():
            if v[2] == "scatter":
                self.graficos_mapeo1[v[0]] = k
            elif v[2] == "line":
                self.graficos_mapeo2[v[0]] = k
            else:
                pass

        self.boolean_colums = self.graficos_mapeo1.values()
        self.dosis = ['dosis_referencia']

    def iniGUI(self):
        self.main_layout = QHBoxLayout() #la mama

        archivo = 'widgets.xlsx'
        _ = self.setupBox(archivo, 'encabezado_600') #ME CREA LA COLUMNA Y SU VAINA
        self.date_box.setDisplayFormat("dd/MM/yyyy")
        df, n, layouts, _ = self.setupBox(archivo, 'preguntas_600', main = False)
        self.datos_tabla = self.storeDailyTests(df)

        self.canson1 = QWidget()
        self.canson2 = QWidget()
        self.canson3 = QWidget()
        self.canson4 = QWidget()

        toolbox= QToolBox()
        self.general_layout.addWidget(toolbox)

        i = 1
        for layout in layouts:
            name = f'canson{i}'
            getattr(self, name).setLayout(layout)
            i+=1

        toolbox.addItem(self.canson1, 'SEGURIDAD')
        toolbox.addItem(self.canson2, 'ASPECTOS MECÁNICOS')
        toolbox.addItem(self.canson3, 'ASPECTOS DOSIMÉTRICOS')
        toolbox.addItem(self.canson4, 'OBSERVACIONES')

        # botones
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
        graf_3 = ['Seleccione...', "Constancia de dosis para 6MV"]
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

        self.splitter_principal = QSplitter(Qt.Horizontal)
        self.splitter_principal.addWidget(self.wf)
        self.splitter_principal.addWidget(self.wf2)

        self.main_layout.addWidget(self.splitter_principal)

        #self.general_layout.removeWidget(self.btn_add)
        #self.btn_add.deleteLater()  # Opcional para liberar memoria

        self.setLayout(self.main_layout)

        self.setupButtonConnections(df, maquina = 'ix')
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
            # LR3 (DA-47/DA-48): lectura de BLOQUE por fecha. El ORDER BY
            # acompaña al filtro: con EB4 (anular+insertar en las diarias)
            # una fecha puede tener varias generaciones y `LIMIT 1` sin
            # orden devuelve la más antigua.
            query.prepare(f"""
                SELECT * FROM aceleradorlineal_600
                WHERE date = ?{filtro_activo('aceleradorlineal_600')}
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
                columnas_numericas = ['laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'dosis_referencia']

                for columna_db in columnas_numericas:
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
                # I2 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md): un solo
                # limpiador, igual que el botón "Limpiar" -- imagen=False,
                # 600 no tiene `resetear_imagen_ui`.
                self._restablecer_formulario_diario(imagen=False)
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

    def button_click(self):

        self.fuera_servicio.clicked.connect(self.reasignar_botonySERVICIO)
        self.btn_add.clicked.connect(lambda _, maquina='aceleradorlineal_600' : self.ordenar_botones(maquina, self.fueradeservicio))
        #self.btn_add.clicked.connect(lambda _, maquina='aceleradorlineal_600' : add_info(self, maquina, [self.boolean_colums, self.dosis]))

            #self.btn_add.clicked.connect(self.clean_info)

        if self.btn_clean.clicked:
            self.btn_clean.clicked.connect(lambda _: self.clean_info(imagenes=False))

        if self.btn_submit.clicked:
            self.btn_submit.clicked.connect(
                lambda _, maquina=self.mach_name2.text(), id_maquina=codigo_de_formato(self):
                    reporte(self, fecha = self.date_box.date().toString('yyyy-MM-dd'),
                            maquina = maquina, id_maquina=id_maquina, tipo_reporte='diario',
                            diccionario=self.diccionario_invertido, umbrales= "si")
            )

        for line in self.df_lines:
            dato = getattr(self, line)
            dato.textChanged.connect(self.checkBotonesFinales)

        self.btn_delete.clicked.connect(lambda _, maquina = 'aceleradorlineal_600' : self.verificar_eliminar(maquina, [self.boolean_colums, self.dosis]))
        self.menu_graficar.currentIndexChanged.connect(self.mostrar_submenu)
        for grafica in self.graficar:
            grafica.currentIndexChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))
            self.btn_submit.clicked.connect(lambda _, grafica = grafica: self.plotter(grafica))
            self.limit1.dateChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))
            self.limit2.dateChanged.connect(lambda _, grafica = grafica: self.plotter(grafica))

        if self.search_bar.textChanged:
            self.search_bar.textChanged.connect(self.filtrarTabla)  # Conectar evento de búsqueda
        #print(self.botones_ordenados)  # Para ver el resultado

        if self.edit_table.clicked:
            self.edit_table.clicked.connect(self.verificar_editar)

        if self.accept_edit.clicked:
            self.accept_edit.clicked.connect(lambda: self.cargarDatosEditados(self.item, self.old_value, "aceleradorlineal_600"))
            self.accept_edit.clicked.connect(lambda: load_table(self, self.boolean_colums, self.dosis,  "aceleradorlineal_600"))
            self.accept_edit.clicked.connect(lambda:asignar_encabezados(self, 'aceleradorlineal_600'))

        if self.cancel_edit.clicked:
            self.cancel_edit.clicked.connect(lambda: self.cancelarEdicion(self.item, self.old_value))
            self.cancel_edit.clicked.connect(lambda: load_table(self, self.boolean_colums, self.dosis,  "aceleradorlineal_600"))
            self.cancel_edit.clicked.connect(lambda:asignar_encabezados(self, 'aceleradorlineal_600'))

        # ✅ NUEVA CONEXIÓN: Cargar datos cuando cambie la fecha
        if hasattr(self, 'date_box'):
            self.date_box.dateChanged.connect(self.cargar_dailytest_desde_db)
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

    def plotter(self, menu):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        db = self.opeenDatabase()
        selected_chart = menu.currentText()  # QComboBox con tipos de gráfica
        if selected_chart == "Seleccione...":
            return
        #print(selected_chart)
        start_date = self.limit1.date().toString('yyyy-MM-dd')
        #print(start_date)
        end_date = self.limit2.date().toString('yyyy-MM-dd')
        #print(end_date)

        selected_column1 = self.graficos_mapeo1.get(selected_chart, None)
        selected_column2 = self.graficos_mapeo2.get(selected_chart, None)

        limite = self.diccionario_invertido.get(selected_column2, None)
        limite = limite[1] if limite else None

        if selected_column1 in [
            "luces_consola",
            "luces_puerta",
            "luces_irradiacion",
            "sistema_visualizacion",
            "sistema_anticolision",
            "interruptor_radiacion_puerta",
            "interruptor_radiacion_panel",
            "interrupcion_um",
            "verificacion_monitoras",
            "movimiento_brazo",
            "movimiento_colimador",
            "movimientos_camilla"
            ]:

            query = QSqlQuery(db)

            graficarvstiempo(self, query, ax, 'aceleradorlineal_600', selected_column1, selected_chart, start_date, end_date, True)

        elif selected_column2 in [
            "laseres",
            "telemetro",
            "tamano_campo",
            "centrado_reticulo",
            'dosis_referencia'
        ]:
            query = QSqlQuery(db)

            graficarvstiempo(self, query, ax, 'aceleradorlineal_600', selected_column2, selected_chart, start_date, end_date, False, limite)

        # Redibuja en el canvas
        self.canvas.draw()

        db.close()
