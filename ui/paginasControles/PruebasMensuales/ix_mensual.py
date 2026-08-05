from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QSplitter, QMessageBox)
from PyQt5.QtCore import Qt, QDate
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from models.PDF.Mensuales.reportes_mensuales import guardarPDF_mensual
from data.ManejoDatos.load import mostrar_controles_mensuales, encontrar_columnas, widget_a_columna
from data.ManejoDatos.conection import Conexion
import traceback
from ui.paginasGuia.dialogs import DialogCalculadoraDosis
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_GUARDAR
from ui.util_fechas import fecha_control_a_qdate as _fecha_control_a_qdate
from services.ventana_edicion import puede_editarse as _puede_editarse_control
from services.ventana_edicion import mensaje_bloqueo_edicion as _mensaje_bloqueo_edicion


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
            # F3 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): parser
            # tolerante -- fecha_control puede traer día (nuevo) o no
            # (registros históricos).
            fecha = _fecha_control_a_qdate(self.fecha_control)
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
    
    def _campos_de_energia(self, df_lines, energia):
        """Widgets de dosimetría que pertenecen a UNA energía del iX: los que
        llevan su sufijo (todos lo llevan en la hoja del iX, tolerancias y
        val_teo incluidos) más el de observaciones, que es compartido.

        H2.7: antes el filtro incluía ln_tolerancia_* de TODAS las energías
        (con la vieja normalización local eran claves inertes que no
        colisionaban); con la normalización compartida `widget_a_columna`
        (que quita CUALQUIER sufijo de energía) habrían colisionado entre
        energías -- por eso el filtro exige el sufijo de ESTA energía."""
        return [
            c for c in df_lines
            if c.endswith("_" + energia) or c == "ln_observaciones_dosi"
        ]

    def subirlineasmensuales_ix(self, nombre_tabla, num_delet, ref, usarid, df_lines):
        print("\nEntra a subirlineasmensuales_ix de la clase PruebaMensualIX")

        # F4b (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4, tarea C1): mismo
        # guard que subirlineasmensuales (load.py) -- ventana de 2 meses
        # desde la creación del control, decisión del físico.
        if not _puede_editarse_control(ref):
            QMessageBox.warning(self, "Control cerrado", _mensaje_bloqueo_edicion(ref))
            return

        conn = Conexion().conectar()
        cursor = conn.cursor()

        for energia in self.ENERGIAS:
            # --- 1. Filtrar los QLineEdit que corresponden a esta energía ---
            campos_energia = self._campos_de_energia(df_lines, energia)

            # --- 2. Convertirlos en {columna_sql: valor} ---
            # widget_a_columna: la MISMA normalización que usa la recarga
            # (_cargar_dosimetria_bd_ix) y el guardado del 600 -- H2.7.
            campos_db = {}
            for line in campos_energia:
                col = widget_a_columna(line)
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
                # H2.8 (auditoría 2026-07-16): UPDATE solo de columnas con
                # widget presente en ESTA energía -- mismo fix que
                # subirlineasmensuales (load.py); ver ahí el caso concreto
                # (panel MLCS de Halcyon) que motivó el cambio.
                columnas_update = [col for col in columnas
                                    if col not in ("ref", "energia") and col in campos_db]
                if not columnas_update:
                    continue
                set_clause = ", ".join([f"{col} = ?" for col in columnas_update])

                sql = f"""
                    UPDATE {nombre_tabla}
                    SET {set_clause}
                    WHERE ref = ? AND energia = ?
                """

                datos_update = [campos_db[col] for col in columnas_update]
                datos_update.extend([ref, energia])

                cursor.execute(sql, datos_update)

        conn.commit()
        _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR, nombre_tabla, ref=ref,
                             detalle="mensual iX (todas las energías)")
        QMessageBox.information(self, "Éxito", "Datos guardados en la base de datos.")
        cursor.close()

    def _cargar_dosimetria_bd_ix(self, df_lines, nombre_tabla, ref):
        """Rellena los widgets de dosimetría del iX desde la BD, POR NOMBRE
        de columna (H2.7). Devuelve True si había al menos una energía
        guardada.

        Antes este mapeo era POSICIONAL (una lista fija de 14 nombres de
        widget contra row[1:14], que son solo 13 valores) y además asumía un
        orden de columnas que no es el de la BD de producción (que tiene
        val_teo_dosis Y val_teo_calidad): al reabrir un control guardado,
        TODOS los campos después de val_teo se mostraban corridos una
        posición -- p. ej. la "calidad" mostraba la tolerancia de dosis. Ese
        es el "dato que se carga solo en calidad y no es lo que guardé" que
        el físico reportó el 14-07. Mapear por nombre con la misma
        `widget_a_columna` del guardado hace imposible que vuelvan a
        divergir."""
        conn = Conexion().conectar()
        cursor = conn.cursor()
        encontrado = False
        for energia in self.ENERGIAS:
            cursor.execute(
                f"SELECT * FROM {nombre_tabla} WHERE ref = ? AND energia = ?",
                (ref, energia))
            row = cursor.fetchone()
            if row is None:
                continue
            encontrado = True
            fila = dict(zip([d[0] for d in cursor.description], row))
            for line_name in self._campos_de_energia(df_lines, energia):
                col = widget_a_columna(line_name)
                if col in fila and hasattr(self, line_name):
                    valor = fila[col]
                    getattr(self, line_name).setText(
                        str(valor) if valor is not None else "")
        cursor.close()
        return encontrado

    def addsomething_ix(self, layout, df, typee, nombre_tabla, datos_eliminar, ref, usarid=False):
        print("\nEntra a addsomething_ix de la clase PruebaMensualIX")
        """
        Versión de addsomething para IX: maneja las 6 energías, guardando
        cada set de QLineEdit en la tabla con un campo extra 'energia'.

        H2.7 (decisión del físico 2026-07-15): se eliminó el borrador JSON
        local (botón "Guardar" + carga al abrir). La BD, vía "Subir"
        (INSERT/UPDATE por ref+energia), es la ÚNICA fuente. De paso esto
        elimina de raíz la inconsistencia que tenía el iX: el borrador se
        cargaba DESPUÉS de la BD y la pisaba (en 600/Halcyon la BD ganaba).
        """
        # [1] Filtra QLineEdit para la prueba "dosimetria"
        df_lines = df.loc[(df.widget_type.str.contains('QLineEdit')) & (df.prueba == f'{typee}')]['nombres']
        df_lines = [line for line in df_lines]

        layout = layout.layout()

        # [2] Cargar lo ya guardado en BD (si existe), por nombre de columna
        self._cargar_dosimetria_bd_ix(df_lines, nombre_tabla, ref)

        # [3] Crear botones
        if layout is not None:
            buttonLayout = QHBoxLayout()
            btn_guardar = QPushButton("Subir")
            # D4.2 (PLAN_FASE_K_D4.md): autollenado de simetría/planicidad
            # desde .mcc -- seleccionar_carpeta_mcc es de PruebaMensual600
            # (compartido con 600, ver docstring ahí).
            self.btn_mcc = QPushButton("Cargar carpeta .mcc")
            self.btn_mcc.clicked.connect(self.seleccionar_carpeta_mcc)
            buttonLayout.addWidget(btn_guardar)
            buttonLayout.addWidget(self.btn_mcc)
            btn_calculadora = QPushButton("Calculadora de Dosis")
        # 2. Connect it to the 'abrir_calculadora' method.
        #    This method is inherited "for free" from the parent PruebaMensual600 class.
            btn_calculadora.clicked.connect(self.abrir_calculadora)
            buttonLayout.addWidget(btn_calculadora)
            layout.addLayout(buttonLayout, 68, 0)
        else:
            print("No se definió ningún layout en category4 (IX)")

        def updateSubirButton():
            if self.checkLineEdits_ix(df_lines=df_lines):
                btn_guardar.setEnabled(True)
            else:
                btn_guardar.setEnabled(True)

        # [4] Subir a BD (para cada energía)
        def subir():
            if not self._confirmar_campos_mcc_sin_revisar():
                return
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
            mostrar_controles_mensuales(None, self.tabla, equipo_filtrar=self.equipo_f)

        btn_guardar.clicked.connect(subir)

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
                # A6.3: auditar=False -- esta acción (guardar_todo_ix) audita
                # UNA sola vez para cuñas+conos, más abajo; subir_control_cunas
                # no debe auditarse a sí mismo aquí (sí lo hace cuando el 600
                # la llama directo desde su propio botón, solo-cuñas).
                self.subir_control_cunas(self.combos_seguridad, self.df_seg_line,
                                         auditar=False)
                #print("OK, Cuñas guardadas en IX")

            # 2. Guardar conos (tu lógica adicional)
            self.guardar_control_conos()
            #print("OK, Conos guardados en IX")

            # A6.3 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): una sola acción
            # de usuario dispara cuñas Y conos -- 1 fila para las dos.
            _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR,
                                 "control_cunas_y_conos", ref=getattr(self, "ref", None),
                                 detalle="mensual iX: cuñas + conos")

            #self.bloquearboton(self.btn_guardar_ix)
        except Exception as e:
            import traceback
            #print(f"Error guardar_todo_ix: {traceback.format_exc()}")
    
    