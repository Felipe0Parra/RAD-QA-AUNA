from PyQt5.QtWidgets import (QWidget, QPushButton, QToolBox, QSplitter)
from PyQt5.QtCore import Qt, QDate
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from data.ManejoDatos.load import mostrar_controles_mensuales

class PruebaMensualHc(PruebaMensual600):
    def __init__(self, user_id):
        #print("PruebaMensualHc        __init__ called")
        self.esHc = True
        super().__init__(user_id, equipo_f="Halcyon")  # Llamada correcta al constructor padre
        self.equipo_f = "Halcyon"
        self.lista_maquina=['encabezado_mensu_Halcyon', 'Control mensual', 'Iniciar control mensual', 'Halcyon', 'preguntas_mensu_Halcyon']
    
    def iniGUI(self, inputs_maquina = None):
        """
        Inicializa la interfaz gráfica para PruebaMensualIX,
        asegurando que el botón de guardar se conecte a guardar_todo_ix.
        """
        finalizar_proceso = QPushButton('Finalizar proceso')
        
        # Crear un separador horizontal que divide la ventana en dos columnas (controles y gráficos)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)  # Ancho del divisor

        # Crear layout izquierdo con el formulario de control
        test_control_layout = QWidget()
        
        # Esta llamada debe crear self.btn_guardar_ix
        _, _, self.commenu = self.controlTestWindow(sheet_name="preguntas_mensu_Halcyon")
        test_control_layout.setLayout(self.general_layout)

        if hasattr(self, 'fecha_control'):
            fecha = QDate.fromString(self.fecha_control, 'MM/yyyy')
            self.date_box.setDate(fecha)
        if hasattr(self, 'nombre_fisico1'):
            index = self.fisico1.findText(self.nombre_fisico1)
            if index >= 0:
                self.fisico1.setCurrentIndex(index)
            self.fisico1.setEnabled(False) 
        if hasattr(self, 'nombre_fisico2'):
            self.fisico2.setItemText(0, self.nombre_fisico2)  # Forzar actualización del texto
            self.fisico2.setEnabled(False)
        
        # Crear layout derecho con los gráficos u otros elementos visuales
        graphics_layout = self.graphicsWindow()

        # Agregar ambas columnas al splitter
        splitter.addWidget(test_control_layout)
        splitter.addWidget(graphics_layout)

        # Configurar que no se puedan colapsar
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # Ajustar proporciones
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # Agregar el splitter al layout principal
        self.main_layout.addWidget(splitter)

    def controlTestWindow(self, sheet_name):
        """
        Crea una ventana de control para pruebas mensuales.
        
        Parámetros:
            sheet_name: Nombre de la hoja de Excel con la definición de widgets.
                            Ej: "preguntas_mensu_600" o "preguntas_mensu_ix"
        """
        archivo = 'widgets.xlsx'
        toolbox = QToolBox()

        # Encabezado general
        _ = self.setupBox(archivo, self.lista_maquina[0])
        nea = self.date_box.date().toString('MM/yyyy')
        nueva_fecha = QDate.fromString(nea, 'MM/yyyy')
        self.date_box.setDate(nueva_fecha)
        self.date_box.setDisplayFormat("MM/yyyy")

        self.general_layout.addWidget(toolbox)

        # Cargar widgets de la hoja correspondiente
        df, _, layouts, comboboxe = self.setupBox(archivo, sheet_name, main=False)

        # Crear categorías base
        self.category1 = QWidget()
        self.category2 = QWidget()
        self.category3 = QWidget()
        self.category4 = QWidget()
        self.category5 = QWidget()

        for i, layout in enumerate(layouts, start=1):
            getattr(self, f'category{i}').setLayout(layout)

        # Filtrar widgets de tipo QComboBox o QLineEdit para el menú de equipos
        df_combo = df.loc[
            (df.prueba == 'equipo') &
            ((df.widget_type == 'QComboBox') | (df.widget_type == 'QLineEdit'))
        ]['nombres']

        self.combo_menu = [getattr(self, combo) for combo in df_combo]

        # Configurar categoría de equipos
        self.botonescombobox(self.category1, self.combo_menu, None)


        # Crear subtoolbox para aspectos mecánicos
        self.subtool = QToolBox()
        self.subtool1 = QToolBox()
        self.subtool2 = QToolBox()

        # -------------------------- Tablas de aspectos mecánicos --------------------------
        tabla_ig, tabla_ic, tabla_il, tabla_icam, tabla_isocentro = self._crear_tablas_aspectos_mecanicos()
            # Discrepancias de aspectos mecánicos}
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        grupo_tablas_angulares = [tabla_ig, tabla_ic]
        for tabla in grupo_tablas_angulares:
            self._configurar_eventos(tabla, callback=PruebaAnual600._calcular_discrepancias_tablas(self, tabla, 0, 1, 2, diferencia_tipo='angular'), 
                                    timer_key=f"debounce_{tabla.objectName()}", delay=300)
            
        grupo_tablas = [tabla_icam, tabla_isocentro]
        for tabla in grupo_tablas:
            self._configurar_eventos(tabla, callback=PruebaAnual600._calcular_discrepancias_tablas(self, tabla, 2, 1, 3, diferencia_tipo='porcentaje'), 
                                        timer_key=f"debounce_{tabla.objectName()}", delay=500)

        self.generar_reporte_btn = QPushButton('Generar reporte PDF')
        self.category3.layout().addWidget(self.generar_reporte_btn)
        self.generar_reporte_btn.clicked.connect(self.generar_reporte_pdf)

        # Tablas de aspectos dosimétricos
        tabla_tamanos_campo = self._crear_tablas_aspectos_dosimetricos(df)

        # Añadir al toolbox principal
        toolbox.addItem(self.category1, "EQUIPOS")
        toolbox.addItem(self.subtool, "ASPECTOS MECÁNICOS")
        toolbox.addItem(self.subtool1, "ASPECTOS DOSIMÉTRICOS")
        toolbox.addItem(self.category4, "MLCs")
        self.discrepancias()

        return toolbox, comboboxe, self.combo_menu
    
    def setupTap1(self):
        #print("Función setupTap1 en la clase PruebaMensualHc")
        super().setupTap1()
        mostrar_controles_mensuales(None, self.tabla, equipo_filtrar=self.equipo_f)

    def _crear_tablas_aspectos_mecanicos(self):
            """Crea las tablas de indicadores angulares"""
            try:
                headers = ["Nivel (°)", "Indicador consola (°)", "Diferencia (°)"]
                
                # Indicadores angulares del brazo
                datos_brazo = [["0", "", ""], ["90", "", ""], ["180", "", ""], ["270", "", ""]]
                widget1, tabla_ig = self.createSimpleTable1(4, 3, headers, datos_brazo, "HC_indicadores_brazo", self.ref,
                                                            id_energia=0, id=True)
                
                self.subtool.addItem(widget1, "Indicadores angulares del brazo")

                # Indicadores angulares del colimador
                datos_colimador = [["0", "", ""], ["90", "", ""], ["270", "", ""]]
                widget2, tabla_ic = self.createSimpleTable1(3, 3, headers, datos_colimador, "HC_indicadores_colimador",
                                                            self.ref, id_energia=0, id=True)
                self.subtool.addItem(widget2, "Indicadores angulares del colimador")


                # Localización de los láseres
                headers_laser = ["Ubicación Láser", "Concordancia \nDrump-Phantom", "Diferencia con \nisocentro (mm)"]
                datos_laser = [["Longitudinal", "", ""], ["Vertical", "", ""], ["Lateral", "", ""]]
                widget3, tabla_il = self.createSimpleTable1(3, 3, headers_laser, datos_laser, "HC_indicadores_laser", self.ref,
                                                            id_energia=0, id=True)
                self.subtool.addItem(widget3, "Localización de los láseres")

                # Indicadores de posicion de la camilla
                headers_camilla = ["", "Desplazamiento", "Medido (cm)", "Diferencia (%)"]
                datos_camilla = [["Longitudinal", "1", ""], ["Longitudinal", "5", ""], ["Longitudinal", "20", ""], 
                                ["Lateral", "1", ""], ["Lateral", "5", ""], ["Lateral", "20", ""],
                                ["Vertical", "1", ""], ["Vertical", "5", ""], ["Vertical", "20", ""]]
                widget4, tabla_icam = self.createSimpleTable1(9, 4, headers_camilla, datos_camilla, "HC_indicadores_camilla",
                                                            self.ref, id_energia=0, id=True)
                self.subtool.addItem(widget4, "Indicadores de posición de la camilla")
                tabla_icam.setSpan(0, 0, 3, 1) # Longitudinal
                tabla_icam.setSpan(3, 0, 3, 1) # Lateral
                tabla_icam.setSpan(6, 0, 3, 1) # Vertical

                # Desplazamiento al isocentro real
                headers_isocentro = ["Ubicación", "Teórico (cm)", "Medido (cm)", "Diferencia (%)"]
                datos_isocentro = [["Longitudinal", "", "", ""], ["Lateral", "", "", ""], ["Vertical", "", "", ""]]
                widget5, tabla_isocentro = self.createSimpleTable1(3, 4, headers_isocentro, datos_isocentro, "HC_desplazamiento_isocentro_mensual", 
                                                                self.ref, id_energia=0, id=True)
                self.subtool.addItem(widget5, "Desplazamiento al isocentro")

                return  tabla_ig, tabla_ic, tabla_il, tabla_icam, tabla_isocentro

            except Exception as e:
                print(f"Error creando tablas de indicadores: {e}")

    def _crear_tablas_aspectos_dosimetricos(self, df):
        """Crea las tablas de aspectos dosimétricos"""
        # 3. Tamaños de campo de radiación
        headers_tamanos_campo = ["Indicado - Inplane (cm)", "Indicado - Crossplane (cm)", "Medido - Inplane (cm)", "Medido - Crossplane (cm)"]
        datos_tamanos_campo = [["5", "5", "", ""], ["10", "10", "", ""], ["20", "20", "", ""]]
        widget_tamanos_campo, tabla_tamanos_campo = self.createSimpleTable1(3, 4, headers_tamanos_campo, datos_tamanos_campo,
                                                                            "HC_tamanos_campo_radiacion", self.ref, 
                                                                            id_energia=0, id=True)
        self.subtool1.addItem(widget_tamanos_campo, "Tamaños de campo de radiación")

        try:
            # 1. Constancia del haz de radiación
            # Configura los widgets en el layout de category5
            self.addsomething(self.category3, df, "dosimetria",
                            "dosimetria.json", "dosimetriaMen", 0, ref=self.ref)
            self.addsomething(self.category5, df, "mlcs",
                            "dosimetria.json", "dosimetriaMen", 0, ref=self.ref)
            # Agrega category5 como item al subtool3
            self.subtool1.addItem(self.category3, "Constancia del haz de radiación")
            self.subtool2.addItem(self.category5, "MLCs")
        except Exception as e:
            print(f"Error creando tablas dosimétricas: {e}")

