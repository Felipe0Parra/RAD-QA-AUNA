from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QSplitter, QMessageBox,QLabel, QFileDialog)
from PyQt5.QtCore import Qt, QDate
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from models.PDF.Mensuales.reportes_mensuales import guardarPDF_mensual
from data.ManejoDatos.load import mostrar_controles_mensuales, encontrar_columnas
from data.ManejoDatos.conection import Conexion, ruta_datos
import json, traceback
import os
from ui.paginasGuia.dialogs import DialogCalculadoraDosis


class PruebaMensualIX(PruebaMensual600):
    ENERGIAS = ["6mv", "15mv", "6mev", "9mev", "12mev", "15mev"]

    
    def __init__(self, user_id):
        #print("PruebaMensualIX        __init__ called")
        self.esIX = True
        self.equipo_f = "Clinac ix"
        super().__init__(user_id, equipo_f="Clinac ix")  # ✅ Llamada correcta al constructor padre
        self.lista_maquina=['encabezado_mensu_IX', 'Control mensual', 'Iniciar control mensual', 'Clinac ix', 'preguntas_mensu_ix']
        
   

    def iniGUI(self, inputs_maquina=None):
        """
        Inicializa la interfaz gráfica para PruebaMensualIX,
        asegurando que el botón de guardar se conecte a guardar_todo_ix.
        """
        
        # Crear un separador horizontal que divide la ventana en dos columnas (controles y gráficos)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)  # Ancho del divisor

        # Crear layout izquierdo con el formulario de control
        test_control_layout = QWidget()
        
        # Esta llamada debe crear self.btn_guardar_ix

        _, _, self.commenu = self.controlTestWindow(sheet_name="preguntas_mensu_ix", lista_maquina=self.lista_maquina)
        test_control_layout.setLayout(self.general_layout)
     
        # Crear layout derecho con los gráficos u otros elementos visuales
        graphics_layout = self.graphicsWindow()

        # Agregar ambas columnas al splitter
        splitter.addWidget(test_control_layout)
        splitter.addWidget(graphics_layout)
        
        #Configurar que no se puedan colapsar
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # Ajustar proporciones
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

  
        if hasattr(self, 'nombre_fisico1'):
            index = self.fisico1.findText(self.nombre_fisico1)
            if index >= 0:
                self.fisico1.setCurrentIndex(index)
            self.fisico1.setEnabled(False) 
        if hasattr(self, 'nombre_fisico2'):
            self.fisico2.setItemText(0, self.nombre_fisico2)  # Forzar actualización del texto
            self.fisico2.setEnabled(False)
            
        # Agregar el splitter al layout principal
        self.main_layout.addWidget(splitter)
        if hasattr(self, 'fecha_control'):
            fecha = QDate.fromString(self.fecha_control, 'MM/yyyy')
            self.date_box.setDate(fecha)
                
        # Desconectar todos las conexiones previas
        while self.btn_guardar_ix.receivers(self.btn_guardar_ix.clicked) > 0:
            try:
                self.btn_guardar_ix.clicked.disconnect()
                print(" - Desconectada una conexión previa en btn_guardar_ix")
            except Exception:
                break

        # Función para imprimir siempre que se ejecute (debug)
        def wrapper_guardar():
            #print(f"!! CLICK en btn_guardar_ix (clase {self.__class__.__name__})")
            self.guardar_todo_ix()

        self.btn_guardar_ix.clicked.connect(wrapper_guardar)
        
        
        #print(f"\n[DEBUG] En {self.__class__.__name__}, btn_guardar_ix conectado a:", self.btn_guardar_ix.receivers(self.btn_guardar_ix.clicked))
        #print(f"Bandera entre 600 e IX: {self.esIX}, Acá es IX")
        self.btn_guardar_ix.clicked.connect(lambda: print("\nSe presionó btn_guardar_ix"))
        self._configurar_mlcs_ix()
    def _configurar_mlcs_ix(self):
        """Configura widgets MLC específicos para IX"""
        try:
            # Verificar si los widgets MLC existen
            if hasattr(self, 'ln_tolerance_mlc'):
                print("ln tolerance encontrado")
            if hasattr(self, 'ln_action_tolerance_ix'):
                print("action tolerance encontrado")
            if hasattr(self, 'ln_action_tolerance_ix') and hasattr(self, 'ln_tolerance_mlc'):
                print("Widgets MLC encontrados y configurados")
            else:
                print("⚠️ Widgets MLC no encontrados - revisar creación desde Excel")
                
        except Exception as e:
            print(f"Error configurando MLCs para IX: {e}")
    def agregar_mcc(self):
        layout = QHBoxLayout()
        
        self.btn_mcc = QPushButton("Seleccionar archivo mcc")
        self.lbl_mcc = QLabel("Ningún archivo seleccionado")
        
        layout.addWidget(self.btn_mcc)
        layout.addWidget(self.lbl_mcc)
        
        self.general_layout.addLayout(layout)
        self.btn_mcc.clicked.connect(self.seleccionar_archivo_simetria)
        
    def setupTap1(self):
        #print("Función setupTap1 en la clase PruebaMensualIX")
        super().setupTap1()
        mostrar_controles_mensuales(None, self.tabla, equipo_filtrar=self.equipo_f)
    # def actualizar_fisicos(self):
    #     fecha = self.date_box.date()
    #     fecha = fecha.toString("MM/yyyy")
    #     print(fecha)
    #     try: 
    #         if hasattr(self, 'equipo_f') and self.equipo_f != 'Tomógrafo':
    #             conn = self.db_manager.obtener_conexion()
    #         else:
    #             conn = Conexion().conectar()
    #         cursor = conn.cursor()
    #         cursor.execute("SELECT fecha FROM controles WHERE equipo = 'Clinac ix' ")
    #         date = cursor.fetchone()
    #         print(date[0])
    #         if date[0] == fecha:
    #             cursor.execute(f"""SELECT user_id, user_id_f2 FROM controles WHERE fecha = '{fecha}' AND equipo = 'Clinac ix' """)
    #             fisicos = cursor.fetchall()
    #             print("fisico 1 ", fisicos[0][0], " Fisico 2 ", fisicos[0][1])
    #             self.fisico1.setText(fisicos[0][0])
    #             if fisicos[0][1] is not None:
    #                 self.fisico2.setCurrentText(fisicos[0][1])
    #     except Exception as e:
    #         print("ERRRRORRR: ", e)
    
    # def seleccionar_archivo_simetria(self):
    #     filenames, _ = QFileDialog.getOpenFileNames(self, "Seleccionar archivos MCC", "", "Archivos MCC (*.mcc)")
    #     if not filenames:
    #         return
    #     for filename in filenames:
    #         if not filename.lower().endswith(".mcc"):
    #             QMessageBox.critical(self, "Archivo inválido", "El archivo no tiene extensión (.mcc)")
    #     self.btn_mcc.setProperty("mcc_path", filenames)
    #     #self.lbl_mcc.setText(os.path.basename(filename))
    #     for filepath in filenames:
    #         self.procesar_mcc(filepath)
            
        
    # def procesar_mcc(self, filepath):
    #     try:
    #         self.reader = read_mcc()
    #         self.reader.load(filepath)
    #         self.mcc_results = {"simetria_inplane": self.reader.get_simmetry_percentage(self.reader.pos_1, self.reader.depth_calib_1), "planicidad_inplane": self.reader.flatness(self.reader.pos_1, self.reader.depth_calib_1), "simetria_crossplane": self.reader.get_simmetry_percentage(self.reader.pos_2, self.reader.depth_calib_2), "planicidad_crossplane": self.reader.flatness(self.reader.pos_2, self.reader.depth_calib_2)}
    #         self.actualizar_widgets_desde_mcc()
            
    #     except Exception as e:
    #         print(f"Error: {e}")
            
            
    # def actualizar_widgets_desde_mcc(self):
    #     if not hasattr(self, "mcc_results"):
    #         return
        
    #     energia_archivo = self.reader.energia
    #     if energia_archivo == "9mev":
    #         energia = "9mev"
    #         try:
    #             self.ln_simetria_inplane_9mev.setText(str(self.mcc_results["simetria_inplane"]))
    #             self.ln_planicidad_inplane_9mev.setText(str(self.mcc_results["planicidad_inplane"]))
    #             self.ln_simetria_crossplane_9mev.setText(str(self.mcc_results["simetria_crossplane"]))
    #             self.ln_planicidad_crossplane_9mev.setText(str(self.mcc_results["planicidad_crossplane"]))
            
    #         except Exception as e:
    #             QMessageBox.critical(self, "Error", f"Error al actualizar widgets desde MCC: {e}")
    #     if energia_archivo == "6mev":
    #         energia = "6mev"
    #         try:
    #             self.ln_simetria_inplane_6mev.setText(str(self.mcc_results["simetria_inplane"]))
    #             self.ln_planicidad_inplane_6mev.setText(str(self.mcc_results["planicidad_inplane"]))
    #             self.ln_simetria_crossplane_6mev.setText(str(self.mcc_results["simetria_crossplane"]))
    #             self.ln_planicidad_crossplane_6mev.setText(str(self.mcc_results["planicidad_crossplane"]))
            
    #         except Exception as e:
    #             QMessageBox.critical(self, "Error", f"Error al actualizar widgets desde MCC: {e}")
    #     if energia_archivo == "12mev":
    #         energia = "12mev"
    #         try:
    #             self.ln_simetria_inplane_12mev.setText(str(self.mcc_results["simetria_inplane"]))
    #             self.ln_planicidad_inplane_12mev.setText(str(self.mcc_results["planicidad_inplane"]))
    #             self.ln_simetria_crossplane_12mev.setText(str(self.mcc_results["simetria_crossplane"]))
    #             self.ln_planicidad_crossplane_12mev.setText(str(self.mcc_results["planicidad_crossplane"]))
            
    #         except Exception as e:
    #             QMessageBox.critical(self, "Error", f"Error al actualizar widgets desde MCC: {e}")
        
    #     if energia_archivo == "15mev":
    #         energia = "15mev"
    #         try:
    #             self.ln_simetria_inplane_15mev.setText(str(self.mcc_results["simetria_inplane"]))
    #             self.ln_planicidad_inplane_15mev.setText(str(self.mcc_results["planicidad_inplane"]))
    #             self.ln_simetria_crossplane_15mev.setText(str(self.mcc_results["simetria_crossplane"]))
    #             self.ln_planicidad_crossplane_15mev.setText(str(self.mcc_results["planicidad_crossplane"]))
            
    #         except Exception as e:
    #             QMessageBox.critical(self, "Error", f"Error al actualizar widgets desde MCC: {e}")
                
            
    def checkLineEdits_ix(self, df_lines=None): 
        if df_lines is None:
            return False

        campos_vacios = []
        leidos = []

        for line in df_lines:
            
      
            if line == "ln_observaciones_dosi":
                continue  # este no lo validamos

            dato = getattr(self, line)
            valor = dato.text().strip()
            leidos.append(f"{line}: '{valor}'")

            if not valor:  # si está vacío
                campos_vacios.append(line)

        # print(f"Valores revisados {leidos}")
        return not campos_vacios
    
    def subirlineasmensuales_ix(self, nombre_tabla, num_delet, ref, usarid, df_lines):
        print("\nEntra a subirlineasmensuales_ix de la clase PruebaMensualIX")
        
        ENERGIAS_IX = ["6mv", "15mv", "6mev", "9mev", "12mev", "15mev"]

        def normalizar_nombre(nombre, energia):
            """
            Quita prefijo 'ln_' y el sufijo '_energia' cuando corresponda.
            Mapea nombres especiales.
            Ej:
                ln_dosis_ref_cgy_um_6mv -> dosis_ref_cgy_um
                ln_tolerancia_dosis     -> tolerancia_dosis
                ln_calidad_j2_j1_6mv    -> calidad_pdd20_10
                val_teo_6mv             -> val_teo
            """
            # --- Casos especiales ---
            if nombre.startswith("ln_calidad_j2_j1_"):
                nombre = nombre.replace("ln_calidad_j2_j1_", "calidad_pdd20_10_")

            # --- Limpieza genérica ---
            nombre = nombre.replace("ln_", "")
            
            # Quitar sufijo de energía si existe
            if nombre.endswith("_" + energia):
                nombre = nombre[:-(len(energia)+1)]

            return nombre

        conn = Conexion().conectar()
        cursor = conn.cursor()

        for energia in ENERGIAS_IX:
            # --- 1. Filtrar los QLineEdit que corresponden a esta energía ---
            campos_energia = [
                c for c in df_lines
                if (c.endswith("_" + energia)) or
                (c.startswith("ln_tolerancia_")) or
                (c.startswith("val_teo_") and c.endswith("_" + energia)) or
                (c == "ln_observaciones_dosi")
            ]

            # --- 2. Convertirlos en {columna_sql: valor} ---
            campos_db = {}
            for line in campos_energia:
                col = normalizar_nombre(line, energia)
                dato = getattr(self, line).text().strip()
                if not dato:
                    campos_db[col] = None
                elif "observaciones_dosi" in col:
                    campos_db[col] = dato
                else:
                    try:
                        campos_db[col] = float(dato)
                    except (ValueError, TypeError):
                        campos_db[col] = None


            # --- 3. Obtener columnas reales de la tabla ---
            columnas_str, placeholders = encontrar_columnas(nombre_tabla, delete=num_delet, id=usarid)
            columnas = columnas_str.split(", ")
       
            if "ref" not in columnas:
                columnas = ["ref"] + columnas
            if "energia" not in columnas:
                columnas = ["energia"] + columnas

            columnas_str = ", ".join(columnas)
            placeholders = ", ".join(["?"] * len(columnas))

            # --- 4. Armar lista de datos en orden ---
            datos = []
            for col in columnas:
                if col == "ref":
                    datos.append(ref)
                elif col == "energia":
                    datos.append(energia)
                else:
                    datos.append(campos_db.get(col, None))

            # --- 5. Insertar o actualizar ---
            cursor.execute(
                f"SELECT ref FROM {nombre_tabla} WHERE ref = ? AND energia = ?",
                (ref, energia)
            )
            if cursor.fetchone() is None:
                sql = f"INSERT INTO {nombre_tabla} ({columnas_str}) VALUES ({placeholders})"
                cursor.execute(sql, datos)

            else:
                columnas_update = [col for col in columnas if col not in ("ref", "energia")]
                set_clause = ", ".join([f"{col} = ?" for col in columnas_update])

                sql = f"""
                    UPDATE {nombre_tabla}
                    SET {set_clause}
                    WHERE ref = ? AND energia = ?
                """

                datos_update = [campos_db.get(col, None) for col in columnas_update]
                datos_update.extend([ref, energia])

                cursor.execute(sql, datos_update)

        conn.commit()
        QMessageBox.information(self, "Éxito", "Datos guardados en la base de datos.")
        cursor.close()

    def addsomething_ix(self, layout, df, typee, filename, nombre_tabla, datos_eliminar, ref, usarid=False):
        print("\nEntra a addsomething_ix de la clase PruebaMensualIX")
        """
        Versión de addsomething para IX.
        Maneja las 5 energías distintas, guardando cada set de QLineEdit en la tabla con un campo extra 'energia'.
        Incluye campos de tolerancia (ln_tolerancia_*), que son comunes a todas las energías.
        """
        ENERGIAS_IX = ["6mv", "15mv", "6mev", "9mev", "12mev","15mev"]

        # [0] Anclar el JSON de campos junto a la BD (independiente del cwd)
        filename = ruta_datos(filename)

        # [1] Filtra QLineEdit para la prueba "dosimetria"
        df_lines = df.loc[(df.widget_type.str.contains('QLineEdit')) & (df.prueba == f'{typee}')]['nombres']
        df_lines = [line for line in df_lines]
        
        #print(f"\nPrueba: {typee}")
        #print(f"\nCampos QLineEdit para {typee} en {nombre_tabla} (IX):\n →:df_lines: {df_lines}")
        layout = layout.layout()

        # [2] Intentar cargar desde BD (para cada energía)
        conn = Conexion().conectar()
        cursor = conn.cursor()

        datos_existentes = {}
        for energia in ENERGIAS_IX:
            cursor.execute(f"SELECT * FROM {nombre_tabla} WHERE ref = ? AND energia = ?", (ref, energia))
            row = cursor.fetchone()
            #print(f"Consulta en addsomething_ix: {row}")
            if row:
                datos_existentes[energia] = row

        if datos_existentes:
            # rellenar y bloquear
            for energia in ENERGIAS_IX:
                if energia in datos_existentes:
                    row = datos_existentes[energia]
                    # row[1:14] son los campos de datos, row[14] es energia
                    datos = list(row)[1:14]  # campos de datos (sin ref y energia)
                    # Mapeo especial para calidad
                    campos_energia = [
                        f"val_teo_{energia}",
                        f"ln_dosis_ref_cgy_um_{energia}",
                        f"ln_discrepancia_dosis_{energia}",
                        f"ln_tolerancia_dosis_{energia}",
                        f"ln_calidad_pdd20_10_{energia}" if f"ln_calidad_pdd20_10_{energia}" in df_lines else f"ln_calidad_j2_j1_{energia}",
                        f"ln_discrepancia_calidad_{energia}",
                        f"ln_tolerancia_calidad_{energia}",
                        f"ln_simetria_inplane_{energia}",
                        f"ln_simetria_crossplane_{energia}",
                        f"ln_tolerancia_simetria_{energia}",
                        f"ln_planicidad_inplane_{energia}",
                        f"ln_planicidad_crossplane_{energia}",
                        f"ln_tolerancia_planicidad_{energia}",
                        'ln_observaciones_dosi'
                    ]
                    # Solo usa los widgets que existen en df_lines
                    campos_energia = [c for c in campos_energia if c in df_lines]
                    for line_name, valor in zip(campos_energia, datos):
                        campo = getattr(self, line_name)
                        #campo.setReadOnly(True)
                        campo.setText(str(valor) if valor is not None else "")
            #print(f"\nCampos energia: { campos_energia}")
            #print(f"\nDatos existentes: {datos_existentes}")
        
 
        # [3] Crear botones si no hay datos en BD
        if layout is not None:
            buttonLayout = QHBoxLayout()
            btn_guardar = QPushButton("Subir")
            btn_salvar = QPushButton("Guardar")
            self.btn_mcc = QPushButton("Subir mcc")
            buttonLayout.addWidget(btn_salvar)
            buttonLayout.addWidget(btn_guardar)
            #buttonLayout.addWidget(self.btn_mcc)
            btn_calculadora = QPushButton("Calculadora de Dosis")
        # 2. Connect it to the 'abrir_calculadora' method.
        #    This method is inherited "for free" from the parent PruebaMensual600 class.
            btn_calculadora.clicked.connect(self.abrir_calculadora)
            buttonLayout.addWidget(btn_calculadora)
            layout.addLayout(buttonLayout, 68, 0)
        else:
            print("No se definió ningún layout en category4 (IX)")

        #btn_guardar.setEnabled(False)
        #self.btn_mcc.clicked.connect(self.seleccionar_archivo_simetria)

        def updateSubirButton():
            if self.checkLineEdits_ix(df_lines=df_lines):
                btn_guardar.setEnabled(True)
            else:
                btn_guardar.setEnabled(True)

        # [4] Intentar cargar desde JSON (ahora dict)
        
        try:
            with open(filename, "r") as f:
                datos_cargados = json.load(f)
            if isinstance(datos_cargados, dict):
                for line_name, valor in datos_cargados.items():
                    
                    campo = getattr(self, line_name)
                    campo.setText(valor)
            elif isinstance(datos_cargados, list):
                for i, line_name in enumerate(df_lines):
                    
                    if i < len(datos_cargados):
                        valor = datos_cargados[i]
                        if hasattr(self, line_name):
                            campo = getattr(self, line_name)
                            campo.setText(str(valor))
        except Exception as e:          
            print("Error al cargar datos:", e)

        # [5] Guardar en JSON local (como dict, no lista)
        def guardar_lines():
            datos_guardar = {
                line: getattr(self, line).text().strip()
                for line in df_lines
            }
            with open(filename, "w") as f:
                json.dump(datos_guardar, f, indent=4)
            updateSubirButton()

        # [6] Subir a BD (para cada energía)
        def subir():
            try:
                subidos = []
                self.subirlineasmensuales_ix(nombre_tabla, datos_eliminar, ref=ref, usarid=usarid, df_lines=df_lines)
                for line in df_lines:
                  
                    dato = getattr(self, line)
                    dato.setReadOnly(False)
                    subidos.append(dato.text().strip() if dato.text().strip() else None)
                self._cargar_datos_tabla(nombre_tabla, ref, df_lines)
                #print(f"Datos subidos a {nombre_tabla} (IX): {subidos}")
            except Exception as e:
                print("Error al subir datos IX:", e)
                return
           # self.bloquearboton(btn_guardar)
            #btn_salvar.hide()
            mostrar_controles_mensuales(None, self.tabla, equipo_filtrar=self.equipo_f)

        btn_guardar.clicked.connect(subir)
        #btn_guardar.clicked.connect()
        # self._actualizar_tabla_despues_subida()
        # btn_guardar.clicked.connect(lambda: self.cargarDatosEditados(self.item, self.old_value, "aceleradorlineal_ix"))
        # btn_guardar.clicked.connect(lambda: load_table(self, self.boolean_colums, self.dosis_ix, 'aceleradorlineal_ix'))
        # accept_edit.clicked.connect(lambda:asignar_encabezados(self, 'aceleradorlineal_ix'))
        
        
        # self.cancel_edit.clicked.connect(lambda: self.cancelarEdicion(self.item, self.old_value))
        btn_salvar.clicked.connect(guardar_lines)
        
        for line in df_lines:
         
            if line != "observaciones":
                dato = getattr(self, line)
                dato.textChanged.connect(updateSubirButton)

    def guardar_control_conos(self):
        print(f"\n Función guardar_control_conos en IX")
        try:
            conn = Conexion().conectar()
            cursor = conn.cursor()

            # Lista de medidas y sus botones
            medidas = [
                ("6x6", self.btn_6_fun, self.btn_6_nofun),
                ("10x10", self.btn_10_fun, self.btn_10_nofun),
                ("15x15", self.btn_15_fun, self.btn_15_nofun),
                ("20x20", self.btn_20_fun, self.btn_20_nofun),
                ("25x25", self.btn_25_fun, self.btn_25_nofun)
            ]
            for medida, btn_fun, btn_nofun in medidas:
                if btn_fun.isChecked():
                    valor = 1
                elif btn_nofun.isChecked():
                    valor = 0
                else:
                    valor = None  # Ninguno seleccionado

                if valor is not None:
                    cursor.execute("""
                        INSERT INTO control_conos (ref, medida, valor)
                        VALUES (?, ?, ?)
                    """, (self.ref, medida, valor))

            conn.commit()
            #QMessageBox.information(self, "Éxito", "Datos de control de conos guardados correctamente.")
            #print("Datos de control de conos guardados correctamente")
        except Exception as e:
            QMessageBox.information(self, "Error", "No se pudo insertar los datos.")
            print(f"Error guardar_control_conos: {traceback.print_exc(e)}")
    
    def guardar_todo_ix(self):
        #print("\n ~~~~~~ Entrando en guardar_todo_ix de", self, "~~~~~~")
        #print("Método definido en clase:", self.__class__.__name__)
        try:
            # 1. Guardar cuñas (copiado de la lógica de botonescombobox del padre)
            if hasattr(self, "combos_seguridad") and self.combos_seguridad:
                datos_seguridad = []
                for angulo, posiciones in self.combos_seguridad.items():
                    for pos, widget in posiciones.items():
                        texto = widget.currentText()
                        valor = 1 if texto.lower() == "funciona" else 0
                        datos_seguridad.append((self.ref, angulo, pos, valor))
                self.subir_control_cunas(self.combos_seguridad, self.df_seg_line)
                #print("OK, Cuñas guardadas en IX")

            # 2. Guardar conos (tu lógica adicional)
            self.guardar_control_conos()
            #print("OK, Conos guardados en IX")

            #self.bloquearboton(self.btn_guardar_ix)
        except Exception as e:
            import traceback
            #print(f"Error guardar_todo_ix: {traceback.format_exc()}")
    
    