import traceback, sqlite3
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import loadtablacomplex
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from PyQt5.QtWidgets import (QWidget, QToolBox, QMessageBox, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QPushButton)
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_GUARDAR
from services.fechas_control import mes_anio_de_fecha as _mes_anio_de_fecha

class PruebaAnual600(PruebaMensual600):
    def __init__(self, user_id, equipo_f='Clinac 600'):
        #print("PruebaAnual600         __init__ called")
        self.anual = True
        self.equipo_f = equipo_f
        super(PruebaAnual600, self).__init__(user_id, equipo_f=equipo_f)
        #self.preINIGI(user_id, lista_maquina)

    def create_control(self, maquina, fecha, user_id, user_id_f2=None):
        try:
            conn = Conexion().conectar()
            cursor = conn.cursor()

            # La fecha entra como 'MM/YYYY', convertir a objeto QDate
            fecha_formateada = fecha.split('/') # ['MM', 'YYYY']
            
            # Validar usuario
            user_id = self.user_id._nombre
            cursor.execute("SELECT fullname FROM users WHERE fullname = ?", (user_id,))
            if cursor.fetchone() is None:
                QMessageBox.critical(self, "Error", f"El usuario '{user_id}' no existe en la base de datos.")
                return
            
            # X1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): sin esta
            # inicialización, un control anual sin 2º físico (user_id_f2=None,
            # el caso común) dejaba _nombre_fisico2 sin asignar -->
            # UnboundLocalError al armar `lista` más abajo. None es además la
            # representación correcta de "sin 2º físico" (no el centinela de
            # texto " ---- " que sí usaba la versión mensual, load.py).
            _nombre_fisico2 = None
            if user_id_f2:
                cursor.execute("SELECT fullname FROM users WHERE id = ?", (user_id_f2,))
                row = cursor.fetchone()
                if row is None:
                    QMessageBox.critical(self, "Error", f"El usuario '{user_id_f2}' no existe en la base de datos.")
                    return
                _nombre_fisico2 = row[0]  # Obtener el nombre del físico 2

            # Verificar si ya existe registro para esa máquina y fecha
            cursor.execute(
                f"SELECT id FROM controles WHERE fecha LIKE ? AND equipo = ? AND control = 'Anual'",
                (f"%{fecha_formateada[1]}%", maquina) # Usar solo el año para controles anuales
            )
            old_id = cursor.fetchone()
            if old_id is not None:
                control_id = old_id[0]

                # B4 (PLAN_AUDITORIA_DOS_EJES_21-07.md SS7.2): actualizar
                # el(los) físico(s) aunque el control anual ya exista, igual
                # que ya hacía el mensual (data/ManejoDatos/load.py::
                # create_control) -- sin esto, reabrir el control anual del
                # mismo año para registrar el 2º físico nunca quedaba
                # guardado en `controles.user_id_f2`.
                cursor.execute(
                    "UPDATE controles SET user_id = ?, user_id_f2 = ? WHERE id = ?",
                    (user_id, _nombre_fisico2, control_id)
                )
                conn.commit()

                if hasattr(self, 'equipo_f') and self.equipo_f == 'Tomógrafo':
                    self.old_id = True
                QMessageBox.information(self, "Éxito", f"Puede seguir con el proceso de llenado de datos del {fecha_formateada[1]}.")
                return control_id

            # Insertar nuevo registro
            lista = [maquina, "Anual", fecha, user_id, _nombre_fisico2]
            sql = "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) VALUES (?,?,?,?,?)"
            cursor.execute(sql, lista)
            conn.commit()

            new_id = cursor.lastrowid
            if hasattr(self, 'equipo_f') and self.equipo_f == 'Tomógrafo' and new_id:
                self.old_id = False
            QMessageBox.information(self, "Éxito", "Datos insertados correctamente.")

            # A6.4 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): mismo patrón que
            # el create_control mensual (data/ManejoDatos/load.py) -- el
            # anual nunca dejaba rastro de la creación del control. Solo se
            # audita el alta (INSERT); la reapertura (UPDATE más arriba)
            # tampoco se audita en el mensual, por consistencia entre
            # hermanos.
            mes_creado, anio_creado = _mes_anio_de_fecha(fecha)
            if mes_creado is not None:
                detalle_legible = f"{maquina} -- Anual {mes_creado:02d}/{anio_creado}"
            else:
                detalle_legible = f"{maquina} -- Anual {fecha}"
            _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR, "controles",
                                 ref=new_id, detalle=detalle_legible)

            return new_id

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error", f"Error en la consulta: {e}")

    def limpiar_layout(self, layouts, user_id, maquina, user_id_f2=None,  nombre_fisico1=None, nombre_fisico2=None):
        fecha = self.date_box.date()
        fecha = fecha.toString("MM/yyyy")
        for layout in layouts:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        self.ref = self.create_control(maquina= maquina, fecha = fecha, user_id= user_id, user_id_f2=user_id_f2)
        self.fecha_control = fecha
        self.nombre_fisico1 = nombre_fisico1
        self.nombre_fisico2 = nombre_fisico2
        #print(f"ID Sesión: {self.ref}")

    def _configurar_categorias(self):
        """Configura las categorías base de widgets"""
        # Crear categorías base
        self.category1 = QWidget()
        self.category2 = QWidget()
        
        # Asignar layouts desde setupBox a las categorías
        if hasattr(self, 'layouts') and self.layouts:
            #print(f"Configurando {len(self.layouts)} layouts en categorías")
            for i, layout in enumerate(self.layouts, start=1):
                if i <= 4:  # Máximo 4 categorías
                    category = getattr(self, f'category{i}')
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

    def _configurar_toolbox_principal(self, toolbox):
        """Configura el toolbox principal con todas las categorías"""
        try:
            # Añadir categorías al toolbox
            toolbox.addItem(self.category1, "EQUIPOS DE MEDICIÓN")
            toolbox.addItem(self.subtool, "ASPECTOS DOSIMÉTRICOS")
            
        except Exception as e:
            print(f"Error configurando toolbox principal: {e}")

    def _configurar_subtoolbox(self):
        """Configura el subtoolbox para aspectos mecánicos"""
        try:
            # Crear subtoolbox para aspectos mecánicos
            self.subtool = QToolBox()
            
            # Configurar tablas de indicadores
            tabla_fc, tabla_fta, tabla_fse, _ = self._crear_tablas_pruebas()
            tablas = [tabla_fc, tabla_fta]
            for tabla in tablas:
                self._configurar_eventos(tabla, callback=self._calcular_discrepancias_tablas(tabla, 1, 2), 
                                        timer_key=f"debounce_{tabla.objectName()}", delay=300)

            for entry in tabla_fse:
                tabla_obj = entry['tabla']
                self._configurar_eventos(tabla_obj, callback=self._calcular_discrepancias_tablas(tabla_obj, 1, 2),
                                        timer_key=f"debounce_{tabla_obj.objectName()}", delay=300)
        except Exception as e:
            print(f"Error configurando subtoolbox: {e}")
            self.subtool = QWidget()

    def _crear_tablas_pruebas(self):
        try:
            # Tabla de factores de campo
            headers_fc = ["Tamaño de campo", "Factor de campo", "Factor esperado", "Discrepancia (%)"]
            datos_fc = [ ["3x3", "", "",""], ["10x10", "", "", ""], ["15x15", "", "", ""], ["20x20", "", "", ""], ["25x25", "", "", ""],
                            ["30x30", "", "", ""], ["35x35", "", "", ""], ["40x40", "", "", ""]]
            widget1, tabla_fc = PruebaMensual600.createSimpleTable1(self, 6, 4, headers_fc, datos_fc, "tabla_factor_campo", self.ref, id=True)

            # Tabla factores de transmisión de accesorios
            headers_fta = ["Cuña", "Factor de transmisión", "Factor esperado", "Discrepancia (%)"]
            datos_fta = [ ["15°", "", "",""], ["30°", "", "", ""], ["45°", "", "", ""], ["60°", "", "", ""], ["MLC", "", "", ""]]
            widget2, tabla_fta = PruebaMensual600.createSimpleTable1(self, 5, 4, headers_fta, datos_fta, "tabla_factores_transmision", self.ref, id=True)

            # Tabla factores sobre el eje
            PPDS = ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"]
            # Contenedor para las 3 tablas de factores sobre el eje
            contenedor_fse = QWidget()
            layout_contenedor = QVBoxLayout(contenedor_fse)

            self.tablas_fse = []
            for pdd in PPDS:
                # No crear botones a no ser de que se la ultima tabla
                if pdd == PPDS[-1]:
                    botones = True
                else:
                    botones = False
                headers_fse = ["Profundidad (cm)", f"{pdd}", "PPD esperado", "Discrepancia (%)"]
                datos_fse = [["5", "", "", ""], ["10", "", "", ""], ["15", "", "", ""]]
                widget3, tabla_fse = PruebaMensual600.createSimpleTable1(self, 3, 4, headers_fse, datos_fse, "tabla_factores_sobre_eje", 
                                                                        self.ref, botones=botones, pdd=pdd, id=True)
                layout_contenedor.addWidget(widget3)
                self.tablas_fse.append({'tabla': tabla_fse, 'pdd': pdd})

            # Tabla control de cámaras monitoras
            contenedor_cm = QWidget()                       # Para agregar el boton de reporte
            lay_contenedor_cm = QVBoxLayout(contenedor_cm)
            headers_ccm = ["Indicador", "Valor"]
            datos_ccm = [["Fac. Calibración", ""], ["Reproducibilidad", ""], ["Linealidad R2", ""], ["Tasa mínima 80 cGy/min", ""],
                        ["Tasa intermedia 160 cGy/min", ""], ["Tasa máxima 400 cGy/min", ""], ["Desviación estándar", ""]]
            widget4, tabla_ccm = PruebaMensual600.createSimpleTable1(self, 7, 2, headers_ccm, datos_ccm, "tabla_control_camaras_monitoras", self.ref, id=True)
            lay_contenedor_cm.addWidget(widget4)

            btn_reporte = QPushButton("Generar Reporte PDF")
            lay_contenedor_cm.addWidget(btn_reporte)
            btn_reporte.clicked.connect(self.generar_reporte_pdf)


            # Añadir tablas al subtoolbox
            self.subtool.addItem(widget1, "Medida de factor de campo")
            self.subtool.addItem(widget2, "Medida de factor de transmisión de accesorios")
            self.subtool.addItem(contenedor_fse, "Medida de factores sobre el eje")
            self.subtool.addItem(contenedor_cm, "Medida de control de cámaras monitoras")

            return tabla_fc, tabla_fta, self.tablas_fse, tabla_ccm

        except Exception as e:
            print(f"Error creando tablas de indicadores: {e}")
    
    def _agregar_botones_tabla(self, layout, table, nombre_tabla, ref, id = True, id_energia=False):
        """Agrega botones de acción a la tabla optimizadamente"""
        try:
            button_layout = QHBoxLayout()
            btn_guardar = QPushButton("Subir")
            # H2.7: el botón "Guardar" (borrador JSON local,
            # _guardar_tabla_optimizada) se eliminó -- BD única fuente.
            button_layout.addWidget(btn_guardar)
            layout.addLayout(button_layout)

            # --- MODIFICACIÓN: Guardar todas las tablas FSE si es la última ---
            def guardar_todas_fse():
                if hasattr(self, "tablas_fse") and table in [t['tabla'] for t in self.tablas_fse]:
                    for entry in self.tablas_fse:
                        tabla_fse = entry['tabla']
                        ppd = entry['pdd']
                        datos = []
                        loadtablacomplex(nombre_tabla, tabla_fse, datos, reference=ref, from_range=0, anual=getattr(self, "anual", False), pdd=ppd, id=id)
                else:
                    # Comportamiento normal para otras tablas
                    datos = []
                    print(f"Subiendo tabla {nombre_tabla} normalmente")
                    loadtablacomplex(nombre_tabla, table, datos, reference=ref, from_range=0, anual=getattr(self, "anual", False), id=id)

                # A6.4 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): uno de los
                # 3 puntos de cierre reales de loadtablacomplex -- un solo
                # click aquí puede subir VARIAS tablas FSE (una por energía)
                # en bucle; 1 fila de auditoría para la acción completa, no
                # una por tabla. Cubre también Halcyon anual, que hereda
                # este método sin sobreescribirlo.
                _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR,
                                     nombre_tabla, ref=ref)

                # Z5 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): el botón
                # ya NO se bloquea tras el primer guardado -- la protección
                # real contra un guardado indebido es la ventana de 2 meses
                # (F4b/C1), la verificación de control activo (W1) y la
                # auditoría de arriba (A6.4), no este botón. Bloquearlo solo
                # impedía corregir un dato mal tecleado sin cerrar y reabrir
                # el formulario (mismo criterio ya aplicado en ix_mensual.py,
                # donde la llamada análoga está comentada desde antes).
                self._actualizar_tabla_despues_subida()
                print(f"Tabla(s) {nombre_tabla} subida(s) correctamente")

            btn_guardar.clicked.connect(guardar_todas_fse)
        except Exception as e:
            print(f"Error agregando botones: {e}")

    def _configurar_elementos_adicionales(self):
        """Configura elementos adicionales del subtoolbox"""
        try:
            # Añadir más categorías al subtoolbox
            self.subtool.addItem(self.category2, 'Haces de fotones')
            self.subtool.addItem(self.category2, 'Factores de transmisión de accesorios')
            self.subtool.addItem(self.category2, 'Factores sobre el eje')
            self.subtool.addItem(self.category2, 'Control de las cámaras monitoras')            
        except Exception as e:
            print(f"Error configurando elementos adicionales: {e}")

    def controlTestWindow(self, sheet_name, lista_maquina = None):
        """
        Crea ventana de control optimizada dividida en submétodos
        
        Parámetros:
            sheet_name (str): Nombre de la hoja de Excel con la definición de widgets
        """
        try:
            #print(f"controlTestWindow desde la clase {self.__class__.__name__} llamada")
            # Inicialización básica
            toolbox = PruebaMensual600._inicializar_toolbox(self, sheet_name, inputs_maquina=lista_maquina)
            
            # Configurar categorías
            self._configurar_categorias()
            
            # Configurar menús de equipos y seguridad
            self._configurar_menus_equipos_seguridad()

            # Configurar categoría de equipos
            self.botonescombobox(self.category1, self.combo_menu, None)
            
            # Crear y configurar subtoolbox
            self._configurar_subtoolbox()
            
            # Configurar toolbox principal
            self._configurar_toolbox_principal(toolbox)

            if hasattr(self, 'equipo_f') and self.equipo_f == 'Halcyon':
                self.discrepancias()
                self._configurar_categoria_fantomas()
            
            # Retornar toolbox, comboboxes y combo_menu como esperaba el código original
            return toolbox, getattr(self, 'comboboxe', []), getattr(self, 'combo_menu', [])
            
        except Exception as e:
            print(f"Error en controlTestWindow: {e}")
            traceback.print_exc()
            return QToolBox(), [], []

    def _configurar_menus_equipos_seguridad(self):
        """Configura menús de equipos y seguridad"""
        try:
            # Filtrar widgets para equipos
            df_combo = self.df.loc[
                (self.df.prueba == 'equipo') &
                ((self.df.widget_type == 'QComboBox') | (self.df.widget_type == 'QLineEdit'))
            ]['nombres']

            # Crear listas de widgets
            self.combo_menu = [getattr(self, combo, None) for combo in df_combo if getattr(self, combo, None)]
    
        except Exception as e:
            print(f"Error configurando menús: {e}")
            self.combo_menu = []

    def _configurar_categoria_fantomas(self):
        """Configura la categoría de fantomas si es necesario"""
        try:
            # Configurar aspectos mecánicos
            self.addsomething(
                layout=self.category2, df=self.df, typee="fantomas",
                nombre_tabla='HC_fantomas',
                datos_eliminar=0, ref=self.ref, usarid=True, anual=True
            )
        except Exception as e:
            print(f"Error configurando categoría de fantomas: {e}")

    def button_click(self):  
        for combo in range(0, len(self.commenu), 3):
            self.commenu[combo].currentTextChanged.connect(self.setEquipoSeleccionado)
        for idx in range(1, len(self.commenu)+1, 3):
            self.commenu[idx].currentTextChanged.connect(self.setCalibracion)

    def _calcular_discrepancias_tablas(self, tabla, columna_real, columna_esperada, columna_discrepancia=3, diferencia_tipo='porcentaje'):
        """Retorna una función callback que calcula discrepancias en las tablas de indicadores"""
        def calcular():
            try:
                # Estructura de la tabla:      |      Medida      |      Valor Esperado     | Discrepancia
                # Ejemplo: ["Tamaño de campo", "Factor de campo", "Factor de campo esperado", "Discrepancia"]
                #          [[      "3x3",              "x",                  "y",                  "d"      ], ...]
                
                # Procesar cada fila de datos
                for fila in range(0, tabla.rowCount()):
                    try:
                        # Obtener valores de las celdas
                        item_medida = tabla.item(fila, columna_real)
                        item_esperado = tabla.item(fila, columna_esperada)

                        valor_medida = float(item_medida.text()) if item_medida and item_medida.text() else 0.0
                        valor_esperado = float(item_esperado.text()) if item_esperado and item_esperado.text() else 0.0
                        
                        # Calcular discrepancia
                        if valor_esperado != 0:
                            if diferencia_tipo == 'absoluta':
                                discrepancia = abs(valor_medida - valor_esperado)
                            if diferencia_tipo == 'porcentaje':  # Porcentaje
                               
                                discrepancia = (abs(valor_medida - valor_esperado)) / abs(valor_esperado)* 100
                            
                            if diferencia_tipo == 'promedio':
                                # Calcular promedio de las dos columnas
                                discrepancia = (valor_medida + valor_esperado) / 2
                                
                            if diferencia_tipo == 'angular':
                                if 355<(valor_esperado) < 360:
                                    valor_medida = 360-valor_medida
                                    discrepancia = (abs(valor_medida - valor_esperado))
                                else:
                                    discrepancia = (abs(valor_medida - valor_esperado))
                                    
                            tabla.setItem(fila, columna_discrepancia, QTableWidgetItem(f"{discrepancia:.2f}"))
                        else:
                            tabla.setItem(fila, columna_discrepancia, QTableWidgetItem("0.00"))

                        
                                
                    except (ValueError, AttributeError):
                        tabla.setItem(fila, columna_discrepancia, QTableWidgetItem("N/A"))

            except Exception as e:
                print(f"Error calculando discrepancias: {e}")
                import traceback
                traceback.print_exc()
        
        return calcular
    
    def generar_reporte_pdf(self):
        from models.PDF.Anual.reportes_anuales import guardarPDF_anual
        fecha = self.date_box.date().toString("MM/yyyy")  # O el formato de fecha que uses
        maquina = self.equipo_f  # O el atributo que corresponda a tu máquina
        guardarPDF_anual(self, fecha, maquina, tipo_reporte="Control Anual", diccionario=None)