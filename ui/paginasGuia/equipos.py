from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from data.ManejoDatos.load import encontrar_columnas
from data.ManejoDatos.conection import Conexion
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_GUARDAR, ACCION_ACTUALIZAR, ACCION_ANULAR
from services.vigencia_equipo import es_vigente_en_fecha
from ui.paginasGuia.dialogs import DialogAdminPermisoEliminar
from PyQt5.QtWidgets import (QMessageBox, QGridLayout, QWidget, QSplitter, QHeaderView, QSizePolicy, QTableWidget, QTableWidgetItem,
                            QLabel, QVBoxLayout, QHBoxLayout, QGroupBox, QDialog, QLineEdit, QComboBox)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QPixmap, QColor, QBrush
from pathlib import Path
import sys # Para manejo de rutas en PyInstaller

_FIRMAS_IMAGEN = (
    b'\xff\xd8\xff',        # JPEG
    b'\x89PNG\r\n\x1a\n',   # PNG
    b'BM',                  # BMP
    b'II*\x00',             # TIFF little-endian
    b'MM\x00*',             # TIFF big-endian
)


def clasificar_certificado(blob):
    """Clasifica un blob de `imagen_certificado` por sus bytes mágicos --
    C1 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.5): antes la
    celda solo distinguía "hay blob o no", así que 12 filas con 3 bytes de
    basura (residuo del off-by-one corregido en aa767fd, "1.0"/"0.0") se
    anunciaban como "Imagen subida" igual que un certificado real. No se
    tocan esos datos (DA-02/DA-28) -- esto solo deja de mentir sobre ellos.
    """
    if not blob:
        return "Sin certificado válido"
    # Verificado contra producción: las 12 filas de basura NO son bytes
    # "1.0"/"0.0" literales -- son REAL (float) por afinidad dinámica de
    # SQLite (typeof='real'), mismo off-by-one histórico. `blob[:4]`
    # reventaría con TypeError si no se filtra el tipo primero.
    if not isinstance(blob, (bytes, bytearray)):
        return "Sin certificado válido"
    if blob[:4] == b'%PDF':
        return "PDF"
    if any(blob.startswith(firma) for firma in _FIRMAS_IMAGEN):
        return "Imagen"
    return "Sin certificado válido"


class ColoredTableWidgetItem(QTableWidgetItem):
    """Subclase de QTableWidgetItem que fuerza el color de fondo"""
    def __init__(self, text, bg_color=None, text_color=None):
        super().__init__(text)
        if bg_color:
            self.setBackground(QBrush(bg_color))
        if text_color:
            self.setForeground(QBrush(text_color))
        # Forzar que se aplique el estilo
        self.setData(Qt.BackgroundRole, QBrush(bg_color) if bg_color else None)
        self.setData(Qt.ForegroundRole, QBrush(text_color) if text_color else None)

class Config(PruebaBasico):
    def __init__(self, user_id=None):
        #print("Config                 __init__ called")
        #print("---------------------------------------------------------------------------------------------")
        # A6.2-bis: `user_id` es la identidad del físico con sesión abierta,
        # la que firma las 3 auditorías de este archivo (alta/edición/borrado
        # del catálogo). Antes no se recibía y `_usuario_actual(self)`
        # devolvía None -> `usuario` NULL en audit_log.
        super().__init__(user_id)
        self.iniGUI()
        self.cargartabla()
        self.button_click()
        
        # Conectar la señal de doble clic una sola vez después de la inicialización
        self.table.itemDoubleClicked.connect(self.abrir_certificado)   
        self.table.setEditTriggers(QTableWidget.NoEditTriggers) 

    def iniGUI(self):
        #print("iniGUI en equipos.py")
        # Layout principal
        self.main_layout = QGridLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Título
        title_label = QLabel("Configuración de equipos", self)
        title_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title_label, 0, 0, 1, 1)  # Ocupa la primera fila y dos columnas
        
        # Grupo de control
        self.group_box = QGroupBox("Control de creación de equipos")
        group_layout = QHBoxLayout()
        self.group_box.setLayout(group_layout)  # Asigna el layout al QGroupBox
        
        # Crear tabla
        self.table = self.tabla()
        table, label2 = self.panelEdicion(self.table)
        # Crear panel de edición
        
        # Agregar elementos al grupo
        splitter.addWidget(table)
        splitter.setStretchFactor(0, 3)  # La tabla ocupa 2 partes
        splitter.addWidget(label2)
        splitter.setStretchFactor(1, 1)  # El panel de edición ocupa 1 parte
        group_layout.addWidget(splitter)
        
        # Agregar el grupo al layout principal
        self.main_layout.addWidget(self.group_box, 1, 0, 10, 2)
        #self.main_layout.rowStretch()

        # **IMPORTANTE:** Establecer el layout principal de la ventana
        self.setLayout(self.main_layout)
        
        # Cargar datos de DB
    
    def button_click(self):    
        # Aquí puedes manejar el evento del botón
        self.tios5.clicked.connect(self.habilitar1)
        
        self.tios6.clicked.connect(self.habilitar2)
        
        self.tios7.clicked.connect(self.eliminarEquipo)
    
    def tabla(self):
        #print("Función tabla en equipos.py")
        
        columnas_str, placeholders = encontrar_columnas('equipos', id = True, delete = 0)

        headers = ["ID", "Tipo de equipo", "Modelo", "Serie", "Factor de calibración", "Fecha de calibración", "Fabricante","Temperatura (°C)", "Presión (kPa)", "Humedad (%)","V Cal.", "Activo", "Certificado", "Vigente"]


        table = QTableWidget(self)
        #table.setRowCount(row)
        table.setColumnHidden(0, True)  # Oculta la columna del ID
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        '''for fila, fila_datos in enumerate(datos):
            for columna, dato in enumerate(fila_datos):
                item = QTableWidgetItem(str(dato))
                if columna == 0:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                table.setItem(fila, columna, item)'''

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        
        return table
    
    def panelEdicion(self, table):
        #print("Función panelEdición en equips.py")
        layout = QVBoxLayout() # Para meter el panel de edición
        
        archivo = 'widgets.xlsx'
        df, n, layouts, _ = self.setupBox(archivo, 'edit_tabla', main = False)
        #print(f"{df}, {n}, {len(layouts)}")

        self.canson1 = QWidget()
        self.canson2 = QWidget()
        self.canson3 = QWidget()
        self.tabla_equipo = QWidget()
        self.tabla_equipo.setLayout(QVBoxLayout())
        self.tabla_equipo.layout().addWidget(table)
        self.tabla_equipo.layout().addWidget(self.canson3)
        
        i = 1
        for layout in layouts: 
            name = f'canson{i}'
            getattr(self, name).setLayout(layout)
            i+=1
        
        for i in range(self.canson1.layout().count()):
            item = self.canson1.layout().itemAt(i).widget()

            if item is not None:
                item.setDisabled(True)
        
        self.tios.hide()
        self.tios2.hide()
        self.tios3.hide()
        self.tios4.hide()
        
        self.general_layout.addWidget(self.canson1)
        self.general_layout.addStretch()
        self.general_layout.addWidget(self.canson2)

        texto_info_unidades = (
            """Unidades de Factor de Calibración:\n
                Cámara de inización:                      (Gy/nC)\n
                Cámara de pozo:                            (Gy·m²/h·A)\n
                Electrómetro (en externa):               (nC)\n
                Electrómetro (en braquiterapia):     (nA)\n
                Detector Rad.:                                  (nC/Gy)\n""")
        
        self.info_unidades = QLabel(texto_info_unidades)
        self.info_unidades.setStyleSheet("color: #686666; font-size: 15px; font-weight: normal;")
        self.general_layout.addWidget(self.info_unidades)

        self.panelEdicion = QWidget()
        self.panelEdicion.setLayout(self.general_layout)

        self.tipo.addItems(["Cámara de ionización", "Cámara de pozo", "Electrómetro", "Barómetro", "Termohigrómetro", "Detector Rad."])

        # Si el df ya definió el segundo factor o su etiqueta, ocultarlos por defecto (soporta nombres usados)
        if hasattr(self, "lb_calib_factor2"):
            self.lb_calib_factor2.hide()
        if hasattr(self, "lb_factor2"):
            self.lb_factor2.hide()
        if hasattr(self, "calib_factor2_label"):
            self.calib_factor2_label.hide()
        if hasattr(self, "calib_factor2"):
            self.calib_factor2.hide()

        # Sincronizar estado inicial según el tipo actual
        try:
            self.actualizar_unidades_calibracion(self.tipo.currentText())
        except Exception as e:
            import json
            print(e)
            console_log = "console_logs.json"
            datos ={"Error en clase Config -> Panel Equipos": e}
            with open(console_log, 'r') as f:
                error = json.load(f)
            error.append(datos)
            with open(console_log, "w") as f:
                json.dump(error, f, indent=4)
            
            pass
        return self.tabla_equipo, self.panelEdicion
    
    def cargarDatos(self, lista):
        print("Función cargarDatos en equipos.py")
        with Conexion().conectar() as conn:
            cursor = conn.cursor()
            # Calcular vigencia usando función existente
        
            # E3: fabricante en la MISMA posición relativa que usa guardarCambios
            # (tras fecha_calibr) -- antes el alta lo omitía y quedaba NULL ("NA").
            cursor.execute("""
                INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2, fecha_calibr,
                            fabricante, t_cal, p_cal, h_cal, v1, activo, vigente, imagen_certificado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, lista)
            conn.commit()
            # H2.4: alta de equipo -- ref = "modelo/serie" (lista[1]/lista[2]).
            _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR, "equipos",
                                 ref=f"{lista[1]}/{lista[2]}")
            QMessageBox.information(self, "Éxito", "Datos insertados correctamente en la base de datos.")

    def actualizar_unidades_calibracion(self, tipo=None):
        # Versión simple: ajustar placeholder/estilo y solo mostrar/ocultar widgets existentes del df
        if tipo is None:
            tipo = self.tipo.currentText()

        # Placeholder/estilo del primer factor según tipo
        if tipo == "Cámara de ionización":
            print("    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)")
            self.calib_factor.setPlaceholderText("Unidades:  1 x 10⁹ Gy/C → (Gy/nC)")
            self.calib_factor.setStyleSheet("color: #FF0000;")
        elif tipo == "Cámara de pozo":
            print("    - Equipo: Cámara de pozo, Unidades:  1 x 10⁵ Gy·m²/h·A")
            self.calib_factor.setPlaceholderText("Unidades:  1 x 10⁵ Gy·m²/h·A")
            self.calib_factor.setStyleSheet("color: #FF0000;")
        elif tipo == "Electrómetro":
            print("    - Unidades: nC")
            self.calib_factor.setPlaceholderText("Unidades:  nC")
            self.calib_factor.setStyleSheet("color: #FF0000;")
        elif tipo == "Barómetro":
            print("    - Equipo: Barómetro, Unidades: kPa")
            self.calib_factor.setPlaceholderText("Unidades:  kPa")
            self.calib_factor.setStyleSheet("color: #FF0000;")
        elif tipo == "Termohigrómetro":
            print("    - Equipo: Termohigrómetro, Unidades: ---")
            self.calib_factor.setPlaceholderText("Unidades:  ---")
            self.calib_factor.setStyleSheet("color: #FF0000;")
        elif tipo == "Detector Rad.":
            print("    - Equipo: Detector Rad., Unidades: nC/Gy")
            self.calib_factor.setPlaceholderText("Unidades:  nC/Gy")
            self.calib_factor.setStyleSheet("color: #FF0000;")
        else:
            self.calib_factor.clear()

        # Mostrar/ocultar segundo factor si está definido por el df (gestionar label y campo por separado)
        label_widget = None
        if hasattr(self, "lb_calib_factor2"):
            label_widget = self.lb_calib_factor2
        elif hasattr(self, "lb_factor2"):
            label_widget = self.lb_factor2
        elif hasattr(self, "calib_factor2_label"):
            label_widget = self.calib_factor2_label

        # Etiqueta
        if label_widget is not None:
            label_widget.setVisible(tipo == "Electrómetro")

        # Campo
        if hasattr(self, "calib_factor2"):
            if tipo == "Electrómetro":
                if not self.calib_factor2.placeholderText():
                    self.calib_factor2.setPlaceholderText("Unidades:  nA")
                self.calib_factor2.setStyleSheet("color: #FF0000;")
                self.calib_factor2.show()
            else:
                self.calib_factor2.hide()
                self.calib_factor2.clear()

    def habilitar1(self):
        print("Botón crear nuevo equipo clickeado (función habilitar1 en equipos.py)")
        for i in range(self.canson1.layout().count()):
            item = self.canson1.layout().itemAt(i).widget()
            if item is not None:
                item.setDisabled(False)
        self.tios3.show()
        self.tios4.show()
        self.info_unidades.hide()

        try:
            self.btn_img_cert.clicked.disconnect(self.imagen_certificado)
        except TypeError:
            pass
        self.btn_img_cert.clicked.connect(self.imagen_certificado)

        # Desconectar señal existente para evitar múltiples conexiones
        try:
            self.tios3.clicked.disconnect()
        except Exception:
            pass
        try:
            self.tios4.clicked.disconnect()
        except Exception:
            pass

        # Evita múltiples conexiones duplicadas
        try:
            self.tipo.currentTextChanged.disconnect(self.actualizar_unidades_calibracion)
        except Exception:
            pass
        self.tipo.currentTextChanged.connect(self.actualizar_unidades_calibracion)
        # Refrescar visibilidad/placeholder inicial
        self.actualizar_unidades_calibracion(self.tipo.currentText())

        def anadir():
            tipo = self.tipo.currentText()
            modelo = self.modelo.text()
            serie = self.serie.text()
            factor_calibracion = self.calib_factor.text()
            # Solo para Electrómetro
            segundo_factor = self.calib_factor2.text() if hasattr(self, "calib_factor2") and self.calib_factor2.isVisible() else None
            fecha_calibracion = self.calib_date.text()
            # E3: mismo criterio que guardarCambios (None si viene vacío).
            fabricante = self.fabricante.text() if self.fabricante.text() else None
            t_cal = float(self.t_cal.text()) if self.t_cal.text() else "No disponible"
            p_cal = float(self.p_cal.text()) if self.p_cal.text() else "No disponible"
            h_cal = float(self.h_cal.text()) if self.h_cal.text() else "No disponible"
            v1 = float(self.v1_cal.text()) if self.v1_cal.text() else "No disponible"
            # F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.4/§9): ya no se calcula
            # `vigente` al guardar -- columna retirada del contrato, nadie la
            # lee para decidir ni mostrar (services/vigencia_equipo.py la
            # deriva siempre en el punto de uso). Un equipo nuevo no tiene
            # valor histórico que conservar -> NULL, no un booleano inventado.
            vigente = None
            activo = 1 if self.sel_activo.isChecked() else 0

            imagen_blob = None
            if hasattr(self, "imagen_path") and self.imagen_path:
                with open(self.imagen_path, "rb") as f:
                    imagen_blob = f.read()

            if self.verificarCampos(self.canson1):
                lista = [tipo, modelo, serie, factor_calibracion, segundo_factor, fecha_calibracion, fabricante, t_cal, p_cal, h_cal, v1, activo, vigente, imagen_blob]
                self.cargarDatos(lista)
                self.cargartabla()
                deshabilitar() # Limpia y deshabilita los campos después de guardar

        def deshabilitar():
            for i in range(self.canson1.layout().count()):
                item = self.canson1.layout().itemAt(i).widget()
                if item is not None:
                    # Limpiar los campos
                    if isinstance(item, QLineEdit) and hasattr(item, "setText"):  # Evitar limpiar QLabel y QPushButton
                        item.setText("")
                    elif isinstance(item, QComboBox) and hasattr(item, "setItemText"):  # QComboBox
                        item.setCurrentIndex(0)  # Resetear al primer ítem  
                    elif hasattr(item, "setCurrentDate"):  # QDateEdit
                        item.setCurrentDate("dd/MM/yyyy")  # Poner solo el formato de fecha sin una fecha específica
                        self.calib_date.setStyleSheet("border: 1px solid #ccc;")  # Resetear estilo

                    item.setDisabled(True)  # Deshabilitar los widgets
            self.tios3.hide()
            self.tios4.hide()
            self.info_unidades.show()
            print("Botón deshabilitar clickeado")

        self.tios3.clicked.connect(anadir)
        self.tios4.clicked.connect(deshabilitar)

    def imagen_certificado(self):
                # Abre tu visor con scroll y zoom
                visor = QDialog()
                if getattr(sys, 'frozen', False):
                    # Ruta dentro del .exe
                    base_path = Path(sys._MEIPASS)
                else:
                    # Ruta normal cuando se ejecuta con Python
                    base_path = Path(__file__).parent.parent.parent

                qss_file = base_path / "resources" / "estilo.qss"
                visor.setStyleSheet(qss_file.read_text(encoding="utf-8"))
                visor.setWindowTitle("Vista previa del certificado")
                visor.resize(800, 600)

                layout = QVBoxLayout(visor)
                widget_imagen = self.imagenUpLoader(analisis=False)
                self.boton_cancel.clicked.connect(lambda: visor.close())
                self.boton_aceptar.clicked.connect(lambda: visor.close())

                
                layout.addWidget(widget_imagen)

                visor.exec_()

    def habilitar2(self):
        print("\nBotón editar equipo clickeado (función habilitar2 en equipos.py)")

        # G2 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-G2, DA-01): editar
        # el catálogo de equipos exige administrador -- antes era la única
        # tabla editable de la app sin ninguna barrera (las diarias usan
        # DialogAdminPermisoEliminar, el mensual también). Sin esto, un
        # físico raso podía desmarcar "Activo" y guardar sin que nadie
        # autorizara nada (evidencia: audit_log del rebuild, activo: 1->0
        # sin autorizacion en medio). DialogAdminPermisoEliminar ya valida
        # login + es_admin_equivalente() y audita el intento denegado por sí
        # sola (C3) -- mismo patrón que eliminarEquipo.
        dialogo_admin = DialogAdminPermisoEliminar(self.user_id)
        if dialogo_admin.exec() != QDialog.DialogCode.Accepted:
            return

        for i in range(self.canson1.layout().count()):
            item = self.canson1.layout().itemAt(i).widget()
            if item is not None:
                item.setDisabled(False)  # Habilitar los widgets para edición

        self.tios.show()
        self.tios2.show()
        self.info_unidades.hide()
        
        # Limpiar la variable imagen_path para que no interfiera con la conservación de imagen original
        if hasattr(self, "imagen_path"):
            self.imagen_path = None

        # Evita múltiples conexiones duplicadas y sincroniza estado inicial
        try:
            self.tipo.currentTextChanged.disconnect(self.actualizar_unidades_calibracion)
        except Exception:
            pass
        self.tipo.currentTextChanged.connect(self.actualizar_unidades_calibracion)
        self.actualizar_unidades_calibracion(self.tipo.currentText())

        # Cargar la información del equipo seleccionado en los widgets
        self.editarEquipo()

        def deshabilitar():
            for i in range(self.canson1.layout().count()):
                item = self.canson1.layout().itemAt(i).widget()
                if item is not None:
                    # Limpiar los campos
                    if isinstance(item, QLineEdit) and hasattr(item, "setText"):  # Evitar limpiar QLabel y QPushButton
                        item.setText("")
                    elif isinstance(item, QComboBox) and hasattr(item, "setItemText"):  # QComboBox
                        item.setCurrentIndex(0)  # Resetear al primer ítem
                        self.calib_factor.setPlaceholderText("") # Limpiar placeholder
                        if hasattr(self, "calib_factor2"):
                            self.calib_factor2.setPlaceholderText("") # Limpiar placeholder
                    elif hasattr(item, "setCurrentDate"):  # QDateEdit
                        item.setCurrentDate("dd/MM/yyyy") # Poner solo el formato de fecha sin una fecha específica
                        self.calib_date.setStyleSheet("border: 1px solid #ccc;")  # Resetear estilo

                    item.setDisabled(True)  # Deshabilitar los widgets
            self.tios.hide()
            self.tios2.hide()
            self.info_unidades.show()
            print("\nBotón deshabilitar clickeado")

        # Desconectar señales antes de conectar para evitar múltiples conexiones
        try:
            self.tios.clicked.disconnect(self.guardarCambios)
        except TypeError:
            pass
        try:
            self.tios2.clicked.disconnect()
        except Exception:
            pass
        self.tios.clicked.connect(self.guardarCambios)  # Botón para guardar los cambios
        self.tios2.clicked.connect(deshabilitar)  # Botón para cancelar la edición

    def verificarCampos(self, widget):
        for i in range(widget.layout().count()):
            item = widget.layout().itemAt(i).widget()
            if not item:
                continue
            # Obtener texto según el método disponible
            texto = item.text() if hasattr(item, "text") else \
                    item.currentText() if hasattr(item, "currentText") else None
            if texto is not None and texto == "" and item is not self.calib_factor2:  # Permitir que el segundo factor esté vacío
                print(f"El campo {item.objectName()} está vacío.")
                return False
        return True
    
    def verificar_vigencia_equipo(self, fecha_calibracion, tipo_equipo):
        """Verifica si la calibración de un equipo está vigente HOY.

        V1: delega en services.vigencia_equipo.es_vigente_en_fecha con
        fecha_referencia=hoy -- este catálogo siempre evalúa contra la
        fecha actual (no depende de ningún control en curso). El formulario
        mensual/anual usa la misma función con fecha_referencia=fecha del
        control (ver seiscientos_mensual.py::setEquipoSeleccionado).
        """
        return es_vigente_en_fecha(fecha_calibracion, tipo_equipo, QDate.currentDate())

    def cargartabla(self):
        # G8 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md, DA-22): antes
        # `WHERE id IN (SELECT MAX(id) FROM equipos GROUP BY serie)`
        # colapsaba a 1 fila por serie sin filtrar `activo` -- medido contra
        # producción: de 39 filas solo 15 se veían, y 5 de las ocultas
        # estaban ACTIVAS (justo las que la calculadora y los formularios
        # usan, vía EquiposService._FILA_ACTUAL desde H2.10). El catálogo
        # debe mostrar TODAS las versiones que ha tenido cada cámara/serie
        # -- es el histórico curado en H2.6/H2.10, no un resumen. Efecto
        # esperado y deseable: A092535 muestra sus dos calibraciones
        # activas (doctrina §8.4 de PLAN_F, ya visible en F9/G10) -- no es
        # un duplicado.
        # ORDER BY model/serie/id (no fecha_calibr: TEXT con ceros
        # inconsistentes, ordenaría lexicográficamente -- mismo criterio ya
        # documentado en equipos_service.py:196-202).
        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, equip_type, model, serie, calibr_fact, fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1,
                        activo, vigente, imagen_certificado
            FROM equipos
            ORDER BY model, serie, id
        """)
        rows = cursor.fetchall()
        conn.close()

        headers = ["ID", "Tipo", "Modelo", "Serie", "Fac. Cal.", "Fecha Cal.", "Fabricante", "Temp. (°C)", "Pres. (kPa)", "Hum. (%)", "V Cal.", 
                    "Activo", "Certificado"]
        self.table.setColumnHidden(0, True)  # Oculta la columna del ID
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        self.table.setRowCount(0)                                           # Limpia la tabla antes de cargar nuevos datos
        
        # Desactivar temporalmente el QSS para que los colores de fondo se vean
        self.table.setStyleSheet("")

        for row, r in enumerate(rows):
            self.table.insertRow(row)
            id_equipo = r[0]
            tipo_equipo = r[1]
            fecha_calibracion = r[5]
            es_activo = r[11] == 1
            # F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.4): ya no se lee la
            # columna `vigente` (r[12], congelada desde que se guardó la
            # fila) -- se calcula siempre contra la fecha de HOY, la única
            # referencia que tiene sentido para el catálogo de equipos.
            es_vigente = self.verificar_vigencia_equipo(fecha_calibracion, tipo_equipo)

            # Determinar colores según el estado
            if not es_activo:
                bg_color = QColor(255, 100, 100)  # Rojo claro - Equipo inactivo
                text_color = QColor(139, 0, 0)    # Rojo oscuro
                estado_bg = QColor(255, 99, 71)   # Rojo más intenso
                estado_text = QColor(255, 100, 100)  # 
            elif not es_vigente:
                bg_color = QColor(255, 215, 0)    # Amarillo - Calibración vencida
                text_color = QColor(184, 134, 11) # Amarillo oscuro
                estado_bg = QColor(144, 238, 144) # Verde para estado activo
                estado_text = QColor(0, 100, 0)   # Verde oscuro
            else:
                bg_color = QColor(144, 238, 144)  # Verde claro - Todo bien
                text_color = QColor(0, 100, 0)    # Verde oscuro
                estado_bg = QColor(144, 238, 144) # Verde
                estado_text = QColor(0, 100, 0)   # Verde oscuro

            # Insertar el ID en la columna 0
            id_item = ColoredTableWidgetItem(str(id_equipo), bg_color, text_color)
            id_item.setData(Qt.UserRole, id_equipo)
            self.table.setItem(row, 0, id_item)

            # Insertar el resto de los datos con colores de alerta (excluyendo activo, imagen_certificado y vigente)
            for col, value in enumerate(r[1:11], start=1):  # r[1:11] son las columnas desde equip_type hasta v1
                # Color especial para la fecha de calibración si está vencida
                if col == 5 and not es_vigente and fecha_calibracion:
                    item = ColoredTableWidgetItem(str(value) if value else "NA", 
                                                QColor(255, 99, 71), QColor(255, 100, 100))
                    item.setToolTip("Calibración vencida - Requiere actualización")
                else:
                    item = ColoredTableWidgetItem(str(value) if value else "NA", bg_color, text_color)
                
                item.setData(Qt.UserRole, id_equipo)
                self.table.setItem(row, col, item)

            # Insertar el estado del equipo (columna activo)
            activo_item = ColoredTableWidgetItem("Sí" if es_activo else "No", estado_bg, estado_text)
            activo_item.setFlags(activo_item.flags() & ~Qt.ItemIsEditable)
            activo_item.setData(Qt.UserRole, id_equipo)
            
            if not es_activo:
                activo_item.setToolTip("⚠️ Equipo inactivo")
            else:
                activo_item.setToolTip("✅ Equipo activo")
            
            self.table.setItem(row, self.table.columnCount() - 2, activo_item)

            # Insertar el estado del certificado
            certificado_blob = r[13]  # imagen_certificado
            etiqueta_certificado = clasificar_certificado(certificado_blob)
            cert_item = ColoredTableWidgetItem(etiqueta_certificado, bg_color, text_color)
            cert_item.setFlags(cert_item.flags() & ~Qt.ItemIsEditable)
            cert_item.setData(Qt.UserRole, id_equipo)
            if etiqueta_certificado in ("PDF", "Imagen"):
                cert_item.setToolTip("Doble clic para abrir el certificado")
            self.table.setItem(row, self.table.columnCount() - 1, cert_item)

    def abrir_certificado(self, item):
        import tempfile, os, subprocess, sys

        # C1: antes solo abría con el literal exacto "Imagen subida" --
        # ahora la celda dice "PDF"/"Imagen"/"Sin certificado válido"
        # (clasificar_certificado), así que el doble clic debe reconocer
        # las dos etiquetas que sí tienen algo que abrir. "Sin certificado
        # válido" (blob NULL o los 3 bytes de basura) no debe abrir nada.
        col_certificado = self.table.columnCount() - 1
        if item.column() == col_certificado and item.text() in ("PDF", "Imagen"):
            id_equipo = item.data(Qt.UserRole)

            with Conexion().conectar() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT imagen_certificado FROM equipos WHERE id = ?", (id_equipo,))
                blob = cursor.fetchone()[0]

            if not blob:
                return

            try:
                # Detectar tipo por magic bytes
                es_pdf = blob[:4] == b'%PDF'

                if es_pdf:
                    # Abrir PDF con visor del sistema (Acrobat, Evince, etc.)
                    suffix = ".pdf"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(blob)
                        tmp_path = tmp.name

                    if sys.platform == "win32":
                        os.startfile(tmp_path)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", tmp_path])
                    else:
                        subprocess.Popen(["xdg-open", tmp_path])

                else:
                    # Imagen: mostrar en QDialog con QLabel
                    visor = QDialog(self)
                    visor.setWindowTitle("Certificado")
                    visor.resize(800, 600)
                    layout = QVBoxLayout(visor)

                    pixmap = QPixmap()
                    pixmap.loadFromData(blob)
                    label = QLabel()
                    label.setPixmap(pixmap.scaled(780, 580, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    label.setAlignment(Qt.AlignCenter)
                    layout.addWidget(label)

                    visor.exec_()

            except Exception as e:
                print(f"Error al abrir certificado: {e}")
                QMessageBox.warning(self, "Error", f"No se pudo abrir el certificado:\n{e}")

    def editarEquipo(self):
        print("\nFunción editarEquipo en equipos.py")
        print("Datos a editar")
        print("----------------------------------------------------------------------")
        row = self.table.currentRow()
        print(f"Fila seleccionada: {row}")
        if row < 0:
            QMessageBox.warning(self, "Advertencia", "Selecciona un equipo para editar.")
            return
        
        # Recuperar el ID del equipo desde la columna oculta
        item = self.table.item(row, 0)
        if item is None:
            QMessageBox.warning(self, "Advertencia", "No se encontró información en la fila seleccionada.")
            return

        id_equipo = item.data(Qt.UserRole)
        print(f"ID del equipo seleccionado: {id_equipo}")

        # Consultar la base de datos para obtener los datos del equipo
        with Conexion().conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT equip_type, model, serie, calibr_fact, calibr_fact2, fecha_calibr, 
                        fabricante, t_cal, p_cal, h_cal, v1, activo, vigente, imagen_certificado
                FROM equipos
                WHERE id = ?
            """, (id_equipo,))
            equipo = cursor.fetchone()

        if not equipo:
            QMessageBox.warning(self, "Advertencia", "No se encontró el equipo en la base de datos.")
            return

        print(f"    - Datos del equipo recuperados: \n          {equipo[:12] + ('Imagen',)}")  # Evita imprimir el blob completo

        try:
            self.tipo.setCurrentText(equipo[0])
            self.actualizar_unidades_calibracion(equipo[0])  # <-- Asegura que el layout se actualice
            self.modelo.setText(equipo[1])
            self.serie.setText(equipo[2])
            self.calib_factor.setText(str(equipo[3]) if equipo[3] is not None else "")
            self.calib_factor.setStyleSheet("color: #000000;")  # Cambia el color del texto

            # Solo asigna el segundo factor si es Electrómetro; show/hide ya lo maneja actualizar_unidades_calibracion
            if equipo[0] == "Electrómetro":
                print("\nMostrando el segundo factor de calibración para Electrómetro.")
                if hasattr(self, "calib_factor2"):
                    self.calib_factor2.setText(str(equipo[4]) if equipo[4] is not None else "")
                    print(f"Segundo factor de calibración cargado: {self.calib_factor2.text()}")
                    self.calib_factor2.setStyleSheet("color: #000000;")  # Cambia el color del texto
                else:
                    print("Error: El campo calib_factor2 no existe en el layout.")
            else:
                if hasattr(self, "calib_factor2"):
                    print("Ocultando el segundo factor de calibración.")
                    self.calib_factor2.clear()

            # Fecha de calibración
            if hasattr(self, "calib_date"):
                if equipo[5]:
                    try:
                        # Parsear la fecha manualmente para manejar diferentes formatos
                        fecha_parts = equipo[5].split('/')
                        if len(fecha_parts) == 3:
                            dia = int(fecha_parts[0])
                            mes = int(fecha_parts[1])
                            anio = int(fecha_parts[2])
                            self.fecha_encontrada = QDate(anio, mes, dia)
                            self.calib_date.setDate(self.fecha_encontrada)
                            print(f"Fecha de calibración cargada: {self.calib_date.text()}")
                        else:
                            print(f"Formato de fecha no válido: {equipo[5]}")
                    except (ValueError, IndexError) as e:
                        print(f"Error al parsear la fecha {equipo[5]}: {e}")
                        # Si hay error, mantener la fecha actual como fallback
            self.verificar_vigencia(equipo)

            if hasattr(self, "fabricante"):
                self.fabricante.setText(str(equipo[6]) if equipo[6] is not None else "")
            if hasattr(self, "t_cal"):
                self.t_cal.setText(str(equipo[7]) if equipo[7] is not None else "")
            if hasattr(self, "p_cal"):
                self.p_cal.setText(str(equipo[8]) if equipo[8] is not None else "")
            if hasattr(self, "h_cal"):
                self.h_cal.setText(str(equipo[9]) if equipo[9] is not None else "")
            if hasattr(self, "v1_cal"):
                self.v1_cal.setText(str(equipo[10]) if equipo[10] is not None else "")
            if hasattr(self, "sel_activo"):
                self.sel_activo.setChecked(bool(equipo[11]))
            
            try:
                self.btn_img_cert.clicked.disconnect(self.imagen_certificado)
            except TypeError:
                pass
            self.btn_img_cert.clicked.connect(self.imagen_certificado)

            id_equipo, tipo_equipo = self.identificar_equipo_editar()

        except AttributeError as e:
            print(f"Error al cargar los datos en los widgets: {e}")

    def guardarCambios(self):
        print("Guardando cambios en el equipo...")
        
        # Obtener el ID del equipo que se está editando
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Advertencia", "No hay equipo seleccionado.")
            return
        
        item = self.table.item(row, 0)
        id_equipo = item.data(Qt.UserRole)
        print(f"ID del equipo a actualizar: {id_equipo}")
        
        # Obtener datos actuales del formulario
        tipo = self.tipo.currentText()
        modelo = self.modelo.text()
        serie = self.serie.text()
        factor_calibracion = self.calib_factor.text()
        segundo_factor = self.calib_factor2.text() if hasattr(self, "calib_factor2") and self.calib_factor2.isVisible() else None
        fecha_calibracion = self.calib_date.text()
        fabricante = self.fabricante.text() if self.fabricante.text() else None
        t_cal = float(self.t_cal.text()) if self.t_cal.text() else None
        p_cal = float(self.p_cal.text()) if self.p_cal.text() else None
        h_cal = float(self.h_cal.text()) if self.h_cal.text() else None
        v1 = float(self.v1_cal.text()) if self.v1_cal.text() else None
        activo = 1 if self.sel_activo.isChecked() else 0

        with Conexion().conectar() as conn:
            cursor = conn.cursor()

            # Obtener datos originales del equipo
            cursor.execute("""
                SELECT equip_type, model, serie, calibr_fact, calibr_fact2, fecha_calibr,
                        fabricante, t_cal, p_cal, h_cal, v1, activo, vigente, imagen_certificado
                FROM equipos
                WHERE id = ?
            """, (id_equipo,))
            datos_originales = cursor.fetchone()

            if not datos_originales:
                QMessageBox.warning(self, "Advertencia", "No se encontró el equipo original.")
                return

            # F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.4/§9): `vigente` ya no se
            # recalcula al editar -- columna retirada del contrato de los
            # servicios (nadie la lee para decidir ni mostrar). Se conserva el
            # valor histórico tal cual estaba, como dato inerte.
            vigente = datos_originales[12]
            activo_original = datos_originales[11]

            # G2 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-G2, DA-01): el
            # gate de F7 aquí (reactivar 0->1 exigía admin) se retiró -- ahora
            # TODA la edición del catálogo exige admin desde la entrada
            # (habilitar2, más arriba en este archivo), así que pedir la clave
            # otra vez al guardar era fricción sin ganancia. Se conserva el
            # detalle de auditoría con activo: X->Y (más abajo), que es lo que
            # hace reconstruible una reactivación.

            # Función para comparar valores de forma robusta
            def valores_iguales(nuevo, original):
                # Si ambos son None o vacíos
                if (nuevo is None or nuevo == "") and (original is None or original == ""):
                    return True
                # Si uno es None y el otro no
                if (nuevo is None or nuevo == "") != (original is None or original == ""):
                    return False
            
                # Convertir a string para comparación uniforme
                nuevo_str = str(nuevo).strip()
                original_str = str(original).strip() if original is not None else ""
            
                # Para fechas, normalizar formato (quitar ceros iniciales)
                if "/" in nuevo_str and "/" in original_str:
                    try:
                        # Dividir fecha y normalizar cada parte
                        nuevo_partes = [str(int(p)) for p in nuevo_str.split("/")]
                        original_partes = [str(int(p)) for p in original_str.split("/")]
                        return nuevo_partes == original_partes
                    except:
                        pass
            
                # Para números, comparar como float si es posible
                try:
                    return float(nuevo_str) == float(original_str)
                except:
                    pass
            
                # Comparación de strings normalizada
                return nuevo_str == original_str

            # Comparar cada campo individualmente
            datos_formulario = [tipo, modelo, serie, factor_calibracion, segundo_factor, fecha_calibracion, 
                                fabricante, t_cal, p_cal, h_cal, v1]
            datos_originales_sin_activo = list(datos_originales[:11])  # Excluye activo e imagen
        
            # Verificar si hay cambios reales
            hay_cambios = False
            cambios_detectados = []
            nueva_imagen_blob = None
            hay_nueva_imagen = hasattr(self, "imagen_path") and self.imagen_path
            if hay_nueva_imagen:
                with open(self.imagen_path, "rb") as f:
                    nueva_imagen_blob = f.read()
            nombres_campos = ["tipo", "modelo", "serie", "factor_calibracion", "segundo_factor", "fecha_calibracion", 
                                "fabricante", "t_cal", "p_cal", "h_cal", "v1"]
        
            for i, (nuevo, original, nombre) in enumerate(zip(datos_formulario, datos_originales_sin_activo, nombres_campos)):
                if not valores_iguales(nuevo, original):
                    hay_cambios = True
                    cambios_detectados.append(f" - {nombre}: '{original}' → '{nuevo}'")
        
            solo_cambio_activo = (not hay_cambios and not hay_nueva_imagen and activo != activo_original)

            # F7 punto 2: el detalle lleva los valores viejo->nuevo (mismo
            # formato que guardarEdicion, A3) -- aplica a cualquier cambio de
            # activo, no solo a la reactivación, porque sin valores el rastro
            # no permite reconstruir el estado.
            if activo != activo_original:
                cambios_detectados.append(f"activo: {int(activo_original)}→{int(activo)}")

            if solo_cambio_activo:
                cursor.execute("UPDATE equipos SET activo = ?, vigente = ? WHERE id = ?",
                            (activo, vigente, id_equipo))
            else:
                if hay_cambios or hay_nueva_imagen:
                    # G3 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-G3,
                    # DA-21): no crear una fila IDÉNTICA a otra ya activa --
                    # caso real 82/83/84 del rebuild 30-07. Editar SIGUE
                    # bifurcando siempre (DA-21, sin excepción); esto solo
                    # bloquea la fila resultante si su certificado (los 7
                    # campos clínicos, no fabricante/imagen) ya está activo en
                    # OTRA fila de la misma serie. `id != ?` excluye la propia
                    # fila que se edita -- cambiar solo `fabricante` no debe
                    # bloquearse contra su propio certificado sin cambios,
                    # solo contra el de OTRA fila ya activa.
                    cursor.execute("""
                        SELECT calibr_fact, calibr_fact2, fecha_calibr, t_cal, p_cal, h_cal, v1
                        FROM equipos WHERE equip_type = ? AND serie = ? AND activo = 1 AND id != ?
                    """, (tipo, serie, id_equipo))
                    campos_certificado_nuevos = [factor_calibracion, segundo_factor,
                                                fecha_calibracion, t_cal, p_cal, h_cal, v1]
                    for fila_activa in cursor.fetchall():
                        if all(valores_iguales(nuevo, original) for nuevo, original in
                                zip(campos_certificado_nuevos, fila_activa)):
                            QMessageBox.warning(
                                self, "Calibración duplicada",
                                f"Ya hay una calibración idéntica registrada para "
                                f"este equipo (fecha {fila_activa[2]}).")
                            return

                    # Bug de índice preexistente (anterior a F6-F10/F7, hallado
                    # al tocar la línea de al lado): `datos_originales[12]` es
                    # `vigente`, no `imagen_certificado` -- ese es el índice 13
                    # del SELECT de arriba. Sin este fix, editar un equipo SIN
                    # subir una imagen nueva escribía el valor de `vigente`
                    # (0/1/None) dentro de la columna BLOB de la imagen.
                    imagen_blob = nueva_imagen_blob if hay_nueva_imagen else datos_originales[13]
                    cursor.execute("""
                        INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2, fecha_calibr, 
                                            fabricante, t_cal, p_cal, h_cal, v1, activo, vigente, imagen_certificado)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (tipo, modelo, serie, factor_calibracion, segundo_factor, fecha_calibracion,
                        fabricante, t_cal, p_cal, h_cal, v1, activo, vigente, imagen_blob))
                else:
                    QMessageBox.information(self, "Información", "No se detectaron cambios en el equipo.")
                    conn.commit()
                    return

            conn.commit()

            # H2.4/F7: detalle con los campos cambiados; si `activo` cambió,
            # incluye el valor viejo->nuevo (punto 2) -- sin eso el rastro no
            # permite reconstruir el estado (p. ej. una reactivación).
            _registrar_auditoria(
                _usuario_actual(self), ACCION_ACTUALIZAR, "equipos", ref=f"{modelo}/{serie}",
                detalle="; ".join(cambios_detectados))

            QMessageBox.information(self, "Éxito", "Los cambios se han guardado correctamente.")
            self.cargartabla()


    def eliminarEquipo(self):
        # Verificar si hay una fila seleccionada
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Advertencia", "Selecciona un equipo para eliminar.")
            return

        # Recuperar el ID del equipo desde la columna oculta
        item = self.table.item(row, 0)  # Columna 0 contiene el ID
        if item is None:
            QMessageBox.warning(self, "Advertencia", "No se encontró información en la fila seleccionada.")
            return

        id_equipo = item.data(Qt.UserRole)  # Recupera el ID desde Qt.UserRole
        print(f"ID del equipo a eliminar: {id_equipo}")

        # E2 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §3): antes este era el
        # ÚNICO borrado de la app sin barrera de permiso (solo un
        # QMessageBox.question) sobre el catálogo curado a mano en H2.6/H2.10.
        # Mismo patrón que PruebasDiarias.py::verificar_eliminar.
        dialogo = DialogAdminPermisoEliminar(self.user_id)
        respuesta = dialogo.exec()
        if respuesta != QDialog.DialogCode.Accepted:
            return

        # E2: soft-delete -- la columna `activo` ya existe y guardarCambios
        # ya la usa. El catálogo nunca pierde una fila: un equipo anulado
        # deja de ofrecerse en los selectores (equipos_service.py ya filtra
        # activo=1) pero un control histórico que lo referencia sigue
        # resolviendo su modelo/serie.
        with Conexion().conectar() as conn:
            cursor = conn.cursor()
            # A6.2 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): identificación ANTES
            # de anular -- mismo patrón de ref que guardarCambios (f"{modelo}/{serie}").
            cursor.execute("SELECT equip_type, model, serie FROM equipos WHERE id = ?", (id_equipo,))
            fila_equipo = cursor.fetchone()
            cursor.execute("UPDATE equipos SET activo = 0 WHERE id = ?", (id_equipo,))
            conn.commit()

        if fila_equipo:
            equip_type, modelo, serie = fila_equipo
            _registrar_auditoria(_usuario_actual(self), ACCION_ANULAR, "equipos",
                                 ref=f"{modelo}/{serie}", detalle=f"tipo: {equip_type}")

        QMessageBox.information(self, "Éxito", "El equipo ha sido anulado correctamente.")

        # Actualizar la tabla
        self.cargartabla()

    def identificar_equipo_editar(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Advertencia", "Selecciona un equipo para editar.")
            return None

        item = self.table.item(row, 0)  # Columna 0 contiene el ID
        if item is None:
            QMessageBox.warning(self, "Advertencia", "No se encontró información en la fila seleccionada.")
            return None

        id_equipo = item.data(Qt.UserRole)  # Recupera el ID desde Qt.UserRole
        #print(f"ID del equipo seleccionado: {id_equipo}")

        tipo_equipo = self.table.item(row, 1).text()  # Columna 1 contiene el tipo de equipo
        #print(f"Tipo de equipo seleccionado: {tipo_equipo}")
        return id_equipo, tipo_equipo
    
    def verificar_vigencia(self, equipo):
        """G4 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md): sin lógica propia --
        el veredicto lo da la misma fuente única que usa la tabla del
        catálogo (`verificar_vigencia_equipo`, F8). Antes tenía su propio
        parseo manual + `daysTo <= 365*vigencia`, una aproximación que F8 ya
        había retirado del otro lado por desviarse 1 día en calibraciones que
        cruzan un 29 de febrero bisiesto -- dos cálculos distintos para la
        misma pregunta, que podían (y en ese caso concreto, lo hacían) dar
        veredictos opuestos.

        El único efecto que se conserva es el borde de color del campo.
        """
        vigente = self.verificar_vigencia_equipo(self.calib_date.text(), equipo[0])
        if vigente:
            self.calib_date.setStyleSheet("border: 2px solid rgb(138, 189, 44);")
        else:
            self.calib_date.setStyleSheet("border: 1px solid red;")
        return vigente

