from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
from PyQt5.QtWidgets import QWidget, QToolBox, QVBoxLayout, QPushButton, QMessageBox
from resources.utils.matplotlib_lazy import get_matplotlib_components
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_GUARDAR

class PruebaAnualHalcyon(PruebaAnual600):
    def __init__(self, user_id):
        #print("PruebaAnualHalcyon     __init__ called")
        self.anual = True
        self.equipo_f = 'Halcyon'
        super(PruebaAnualHalcyon, self).__init__(user_id, equipo_f='Halcyon')
    
    def _configurar_categorias(self):
        """Configura las categorías base de widgets"""
        # Crear categorías base
        self.category1 = QWidget()
        self.category2 = QWidget()
        self.category3 = QWidget()
        self.category4 = QWidget()
        self.category5 = QWidget()

        # Asignar layouts desde setupBox a las categorías
        if hasattr(self, 'layouts') and self.layouts:
            #print(f"Configurando {len(self.layouts)} layouts en categorías")
            for i, layout in enumerate(self.layouts, start=1):
                if i <= 5:  # Máximo 5 categorías
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
            toolbox.addItem(self.category2, "FANTOMAS USADOS")
            toolbox.addItem(self.subtool1, "ASPECTOS MECÁNICOS")
            toolbox.addItem(self.subtool2, "ASPECTOS DEL SISTEMA MLC")
            toolbox.addItem(self.subtool3, "ASPECTOS DOSIMÉTRICOS")

        except Exception as e:
            print(f"Error configurando toolbox principal: {e}")

    def _configurar_subtoolbox(self):
        """Configura el subtoolbox para aspectos mecánicos"""
        try:
            # Crear subtoolbox para aspectos mecánicos
            self.subtool1 = QToolBox()
            self.subtool2 = QToolBox()
            self.subtool3 = QToolBox()

            # Crear tablas para aspectos mecánicos (indicadores angulares, láseres, camilla)
            tabla_ig, tabla_ic, _, tabla_icam  = self._crear_tablas_aspectos_mecanicos()
            _, tabla_precision = self._crear_tablas_aspectos_mlc()
            tabla_linealidadUM, _ =self._crear_tablas_aspectos_dosimetricos()

            grupo_tablas_mecanicos = [tabla_ig, tabla_ic, tabla_icam]
            for tabla in grupo_tablas_mecanicos:
                self._configurar_eventos(tabla, callback=self._calcular_discrepancias_tablas(tabla, 0, 1, 2, diferencia_tipo='absoluta'), 
                                        timer_key=f"debounce_{tabla.objectName()}", delay=300)

            self._configurar_eventos(tabla_icam, callback=self._calcular_discrepancias_tablas(tabla_icam, 1, 2, 3, diferencia_tipo='porcentaje'), 
                                        timer_key=f"debounce_{tabla_icam.objectName()}", delay=300)

            self._configurar_eventos(tabla_precision, callback=self._calcular_discrepancias_tablas(tabla_precision, 0, 1, 2, diferencia_tipo='porcentaje'), 
                                        timer_key=f"debounce_{tabla_precision.objectName()}", delay=300)
            
            self._configurar_eventos(tabla_linealidadUM, callback=self._calcular_discrepancias_tablas(tabla_linealidadUM, 1, 2, 3, diferencia_tipo='promedio'), 
                                        timer_key=f"debounce_{tabla_linealidadUM.objectName()}", delay=300)

        except Exception as e:
            print(f"Error configurando subtoolbox: {e}")
            self.subtool1 = QWidget()
            self.subtool2 = QWidget()
            self.subtool3 = QWidget()
            self.subtool4 = QWidget()

    def _crear_tablas_aspectos_mecanicos(self):
        """Crea las tablas de indicadores angulares"""
        try:
            headers = ["Nivel (°)", "Indicador consola (°)", "Diferencia (°)"]
            
            # Indicadores angulares del brazo
            datos_brazo = [["0", "", ""], ["90", "", ""], ["180", "", ""], ["270", "", ""]]
            widget1, tabla_ig = self.createSimpleTable1(4, 3, headers, datos_brazo, "HC_indicadores_brazo", self.ref, id_energia=0, id=True)
            self.subtool1.addItem(widget1, "Indicadores angulares del brazo")

            # Indicadores angulares del colimador
            datos_colimador = [["0", "", ""], ["90", "", ""], ["270", "", ""]]
            widget2, tabla_ic = self.createSimpleTable1(3, 3, headers, datos_colimador, "HC_indicadores_colimador", self.ref, id_energia=0, id=True)
            self.subtool1.addItem(widget2, "Indicadores angulares del colimador")


            # Localización de los láseres
            headers_laser = ["Ubicación Láser", "Concordancia \nDrump-Phantom", "Diferencia con \nisocentro (mm)"]
            datos_laser = [["Longitudinal", "", ""], ["Vertical", "", ""], ["Lateral", "", ""]]
            widget3, tabla_il = self.createSimpleTable1(3, 3, headers_laser, datos_laser, "HC_indicadores_laser", self.ref, id_energia=0, id=True)
            self.subtool1.addItem(widget3, "Localización de los láseres")

            # Indicadores de posicion de la camilla
            headers_camilla = ["", "Desplazamiento", "Medido (cm)", "Diferencia (%)"]
            datos_camilla = [["Longitudinal", "1", ""], ["Longitudinal", "5", ""], ["Longitudinal", "20", ""], 
                            ["Lateral", "1", ""], ["Lateral", "5", ""], ["Lateral", "20", ""],
                            ["Vertical", "1", ""], ["Vertical", "5", ""], ["Vertical", "20", ""]]

            widget4, tabla_icam = self.createSimpleTable1(9, 4, headers_camilla, datos_camilla, "HC_indicadores_camilla", self.ref, id_energia=0, id=True)
            self.subtool1.addItem(widget4, "Indicadores de posición de la camilla")
            tabla_icam.setSpan(0, 0, 3, 1) # Longitudinal
            tabla_icam.setSpan(3, 0, 3, 1) # Lateral
            tabla_icam.setSpan(6, 0, 3, 1) # Vertical
            
            return  tabla_ig, tabla_ic, tabla_il, tabla_icam

        except Exception as e:
            print(f"Error creando tablas de indicadores: {e}")

    def _crear_tablas_aspectos_mlc(self): 
        """Crea las tablas de aspectos dosimétricos"""
        try:
            # 1.  Tabla velocidad de las multilaminas, contiene 4 tablas internas
                # 1. Banco A proximal
                # 2. Banco A distal
                # 3. Banco B proximal
                # 4. Banco B distal 

            # Cada una con dos columnas: Velocidad promedio (cm/s) y Desviación media (cm/s)
            headers_velocidad = ["Banco", "Velocidad promedio (cm/s)", "Desviación media (cm/s)"]
            datos_banco_a_prox = [["A Proximal", "", ""]]
            datos_banco_a_dist = [["A Distal", "", ""]]
            datos_banco_b_prox = [["B Proximal", "", ""]]
            datos_banco_b_dist = [["B Distal", "", ""]]
            widget_velocidad, tabla_velocidad = self.createSimpleTable1(4, 3, headers_velocidad, 
                                                                        datos_banco_a_prox + datos_banco_a_dist + 
                                                                        datos_banco_b_prox + datos_banco_b_dist,
                                                                        "HC_velocidad_multilaminas_anual", self.ref, id_energia=0, id=True)
            self.subtool2.addItem(widget_velocidad, "Velocidad de las multiláminas")

            # 2. Tabla precisión de la posición de las multilaminas
            headers_mlc = ["Medida (cm)", "Esperada (cm)", "Diferencia (%)"]
            datos_precision = [["", "", ""] for _ in range(5)]  # 5 filas de datos
            widget_precision, tabla_precision = self.createSimpleTable1(5, 3, headers_mlc, datos_precision,
                                                                        "HC_precision_posicion_multilaminas_anual", self.ref, id_energia=0, id=True)

            self.subtool2.addItem(widget_precision, "Precisión de la posición de las multilaminas")

            # Imagen
            imagen = self.imagenUpLoader(analisis=True)
            self.subtool2.addItem(imagen, "Imagen de la prueba")

            return tabla_velocidad, tabla_precision

        except Exception as e:
            print(f"Error creando tablas dosimétricas: {e}")

    def _crear_tablas_aspectos_dosimetricos(self):
        """Crea las tablas de aspectos dosimétricos"""

        # 2. Linealidad de las unidades monitor
        headers_linealidadUM = ["UM", "Q1 (nC)", "Q2 (nC)", "Qprom (nC)"]
        datos_linealidadUM = [["50", "", "", ""], ["100", "", "", ""], ["150", "", "", ""], ["200", "", "", ""],
                            ["250", "", "", ""], ["300", "", "", ""], ["350", "", "", ""], ["400", "", "", ""]]
        widget_linealidadUM, tabla_linealidadUM = self.createSimpleTable1(8, 4, headers_linealidadUM, datos_linealidadUM,
                                                                        "HC_linealidad_unidades_monitor_anual", self.ref, id_energia=0, id=True)
        self.subtool3.addItem(widget_linealidadUM, "Linealidad de las unidades monitor")

        # 3. Tamaños de campo de radiación
        headers_tamanos_campo = ["Indicado - Inplane (cm)", "Indicado - Crossplane (cm)", "Medido - Inplane (cm)", "Medido - Crossplane (cm)"]
        datos_tamanos_campo = [["6", "6", "", ""], ["8", "8", "", ""], ["10", "10", "", ""], ["20", "20", "", ""],
                            ["28", "28", "", ""]]
        widget_tamanos_campo, tabla_tamanos_campo = self.createSimpleTable1(5, 4, headers_tamanos_campo, datos_tamanos_campo,
                                                                            "HC_tamanos_campo_radiacion", self.ref, id_energia=0, id=True)
        self.subtool3.addItem(widget_tamanos_campo, "Tamaños de campo de radiación")

        try:
            # 1. Constancia del haz de radiación
            # Contenedor para agregar el botón de reporte en la misma categoría

            # Asegúrate de que category5 tenga un layout
            if self.category5.layout() is None:
                lay_contenedor_ad = QVBoxLayout()
                self.category5.setLayout(lay_contenedor_ad)
            else:
                lay_contenedor_ad = self.category5.layout()

            self.addsomething(self.category5, self.df, "aspectos_dosimetricos",
                            "HC_dosimetria_anual", 0, ref=self.ref, usarid=True, anual=True)

            btn_reporte = QPushButton("Generar Reporte PDF")
            lay_contenedor_ad.addWidget(btn_reporte)
            btn_reporte.clicked.connect(self.generar_reporte_pdf)

            # Agrega category5 como item al subtool3
            self.subtool3.addItem(self.category5, "Constancia del haz de radiación")
        except Exception as e:
            print(f"Error creando tablas dosimétricas: {e}")

        return tabla_linealidadUM, tabla_tamanos_campo

    # Analisis de la imagen del mlc (picket fence)
    def analizar_imagen(self):
        import cv2, numpy as np
        from scipy.signal import find_peaks

        if not self.imagen_path:
            Warning("Advertencia", "Primero selecciona una imagen.")
            return None
        
        imagen = cv2.imread(self.imagen_path, cv2.IMREAD_GRAYSCALE)

        perfil = np.mean(imagen[imagen.shape[0]//2 - 10:imagen.shape[0]//2 + 10], axis=0)
        picos, _ = find_peaks(perfil, distance=20, prominence=10)
        posiciones = picos

        # Plotear el perfil y los picos detectados
        # Graficar la imagen en el canvas
        fig = self.canvas.figure
        fig.clear()  # Limpia el canvas antes de graficar
        ax1 = fig.add_subplot(211)
        ax1.imshow(imagen, cmap='gray')
        ax1.set_title('Imagen MLC')
        ax1.axis('off')

        # Graficar el perfil y los picos detectados
        ax2 = fig.add_subplot(212)
        ax2.plot(perfil, label='Perfil de Intensidad')
        ax2.plot(picos, perfil[picos], "x", label='Picos Detectados')
        ax2.set_title('Perfil de Intensidad')
        ax2.set_xlabel('Posición (pixels)')
        ax2.legend()

        fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        mpl = get_matplotlib_components()
        NavigationToolbar = mpl['NavigationToolbar']

        # Elimina toolbar anterior si existe
        if hasattr(self, 'toolbar') and self.toolbar is not None:
            self.toolbar.setParent(None)

        self.toolbar = NavigationToolbar(self.canvas, self)

        # Z6 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): analizar_imagen
        # puede llamarse más de una vez en la misma sesión (re-analizar tras
        # elegir otra imagen) -- antes creaba un botón "Subir" NUEVO cada
        # vez y lo apilaba en canvas_layout sin quitar el anterior (mismo
        # síntoma que el toolbar de arriba, que sí tiene la guarda). Dos
        # botones "Subir" casi uno encima del otro, cada uno conectado a su
        # propia llamada -- exactamente lo que muestra audit_log con dos
        # filas de HC_imagen_perfil_mlc_anual a 4 segundos de diferencia.
        if hasattr(self, 'btn_subir_imagen_mlc') and self.btn_subir_imagen_mlc is not None:
            self.btn_subir_imagen_mlc.setParent(None)
        self.btn_subir_imagen_mlc = QPushButton("Subir")

        # Agrega el toolbar al layout del canvas
        canvas_layout = self.canvas.parent().layout()  # O usa el layout correcto si es diferente
        if canvas_layout is not None:
            canvas_layout.addWidget(self.toolbar)
            canvas_layout.addWidget(self.btn_subir_imagen_mlc)

        # Convertir imagenes a blob y subir a la base de datos
        img_blob = cv2.imencode('.png', imagen)[1].tobytes()
        
        # Convertir el subplot ax2 a imagen
        fig.canvas.draw()
        # Usar buffer_rgba() en lugar de tostring_rgb()
        buf = fig.canvas.buffer_rgba()
        perfil_img = np.asarray(buf)
        # Convertir RGBA a RGB
        perfil_img = cv2.cvtColor(perfil_img, cv2.COLOR_RGBA2RGB)
        perfil_blob = cv2.imencode('.png', perfil_img)[1].tobytes()
        
        picos_str = ','.join(map(str, posiciones))  

        self.canvas.draw()
        self.btn_subir_imagen_mlc.clicked.connect(lambda: self.subir_imagen_perfil_mlc_db(img_blob, perfil_blob, picos_str))

        QMessageBox.information(self, "Éxito", "Imagen MLC analizada y perfil graficado.")
        return posiciones

    def subir_imagen_perfil_mlc_db(self, imagen, imagen_perfil_horiz, picos_perfil):
        """Sube la imagen y el perfil del MLC a la base de datos"""
        try:
            from data.ManejoDatos.conection import Conexion
            conn = Conexion().conectar()
            cursor = conn.cursor()

            query = """
            INSERT INTO HC_imagen_perfil_mlc_anual (ref, id_energia, imagen, imagen_perfil_horiz, picos_perfil)
            VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(query, (self.ref, 0, imagen, imagen_perfil_horiz, picos_perfil))
            conn.commit()
            print("Imagen y perfil del MLC subidos exitosamente a la base de datos.")
            # A6.4 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): archivo entero
            # sin ninguna auditoría -- escritura aparte, no pasa por
            # loadtablacomplex.
            _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR,
                                 "HC_imagen_perfil_mlc_anual", ref=self.ref)
            QMessageBox.information(self, "Éxito", "Imagen y perfil del MLC subidos exitosamente a la base de datos.")
        except Exception as e:
            print(f"Error subiendo imagen y perfil del MLC a la base de datos: {e}")
            
# P1 (PLAN_P1_POOL_CONEXIONES_27-07.md): la clase con estado que vivía aquí
# fue reemplazada por la fachada sin estado de services/db_pool.py.
from services.db_pool import DatabaseManager


class PruebaImagenesHalcyon(PruebaMensualTAC):
    def __init__(self, user_id, ref=None):
        print("PruebaImagenesIX  __init__ called")
        self.esHC_images = True
        self.anual = True
        
        self.db_manager = DatabaseManager()
        self.equipo_f = "Halcyon"
        self.img_analysis = True
        print(self.equipo_f)
        print("ENTRANDO A PRUEBA IMAGENES HC")
       
        super().__init__(user_id)
        self.ref = ref
        self.ref_HC_img = ref  # Ahora recibe el ref compartido
        if hasattr(self, 'datebox') and self.date_box:
            print("Cajita de fecha encontrada")
        print(f"PruebaImagenesHC received ref: {self.ref_HC_img}")
        
        