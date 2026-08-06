from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from PyQt5.QtWidgets import (QWidget, QToolBox, QVBoxLayout, QHBoxLayout, QPushButton)
from data.ManejoDatos.load import loadtablacomplex
from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
from data.ManejoDatos.catphan_TAC.slice_matcher import detectar_y_resolver_modulos
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_GUARDAR
class PruebaAnualIX(PruebaAnual600):
    def __init__(self, user_id):
        #print("PruebaAnualIX         __init__ called")
        self.anual = True
        self.esIX = True
        self.equipo_f = 'Clinac ix'
        super(PruebaAnualIX, self).__init__(user_id, equipo_f='Clinac ix')

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

    def _configurar_subtoolbox(self):
        """Configura el subtoolbox para aspectos mecánicos"""
        try:
            # Crear subtoolbox para aspectos mecánicos
            self.subtool = QToolBox()
            self.subtool2 = QToolBox()
            self.subtool3 = QToolBox()
            self.subtool4 = QToolBox()
            
            # Configurar tablas de indicadores
            tablas_fc, tablas_fta, tablas_fse, _ = self._crear_tablas_pruebas()
            grupo = [tablas_fc, tablas_fta]  # Solo las listas planas
            for tablas in grupo:
                for tabla in tablas:
                    tabla_obj = tabla['tabla']
                    self._configurar_eventos(tabla_obj, callback=self._calcular_discrepancias_tablas(tabla_obj, 1, 2), 
                                        timer_key=f"debounce_{tabla_obj.objectName()}", delay=300)

            # Ahora para tablas_fse, que es una lista de listas de diccionarios
            for tablas_por_energia in tablas_fse:
                for entry in tablas_por_energia:
                    tabla_obj = entry['tabla']
                    self._configurar_eventos(tabla_obj, callback=self._calcular_discrepancias_tablas(tabla_obj, 1, 2),
                                            timer_key=f"debounce_{tabla_obj.objectName()}", delay=300)

        except Exception as e:
            print(f"Error configurando subtoolbox: {e}")
            self.subtool = QWidget()
            self.subtool2 = QWidget()
            self.subtool3 = QWidget()
            self.subtool4 = QWidget()

    def _configurar_toolbox_principal(self, toolbox):
        """Configura el toolbox principal con todas las categorías"""
        try:
            # Añadir categorías al toolbox
            toolbox.addItem(self.category1, "EQUIPOS DE MEDICIÓN")
            toolbox.addItem(self.subtool, "FACTOR DE CAMPO")
            toolbox.addItem(self.subtool2, "FACTOR DE TRANSMISIÓN")
            toolbox.addItem(self.subtool3, "FACTOR SOBRE EL EJE")
            toolbox.addItem(self.subtool4, "CONTROL DE CÁMARAS")

        except Exception as e:
            print(f"Error configurando toolbox principal: {e}")

    def _crear_tablas_pruebas(self):
        try:

            # Diccionario con el id de la energía para Clinac ix
            energia_ids = {"6 MV": 0, "15 MV": 1, "6 MeV": 2, "9 MeV": 3, "12 MeV": 4, "15 MeV": 5}

            # ------------------------------ Tabla de factores de campo ---------------------------------
            headers_fc = ["Tamaño de campo", "Factor de campo", "Factor esperado", "Discrepancia (%)"]
            datos_fc = [ ["3x3", "", "",""], ["10x10", "", "", ""], ["15x15", "", "", ""], ["20x20", "", "", ""], ["25x25", "", "", ""],
                            ["30x30", "", "", ""], ["35x35", "", "", ""], ["40x40", "", "", ""]]
            energias = ["6 MV", "15 MV", "6 MeV", "9 MeV", "12 MeV", "15 MeV"]
            self.tablas_fc = []
            for energia in energias:
                self.id_energia = energia_ids.get(energia, None)
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, 6, 4, headers_fc, datos_fc, "tabla_factor_campo", self.ref, id_energia=self.id_energia, id=True
                )
                self.subtool.addItem(widget, f"Medida de factor de campo - {energia}")
                self.tablas_fc.append({'tabla': tabla, 'id_energia': self.id_energia})

            # ------------------------- Tabla factores de transmisión de accesorios -------------------------
            headers_fta = ["Accesorio", "Factor de transmisión", "Factor esperado", "Discrepancia (%)"]
            datos_fta = [ ["15°", "", "",""], ["30°", "", "", ""], ["45°", "", "", ""], ["60°", "", "", ""], ["MLC", "", "", ""]]
            self.tablas_fta = []
            for energia in energias:
                self.id_energia = energia_ids.get(energia, None)
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, 5, 4, headers_fta, datos_fta, "tabla_factores_transmision", self.ref, id_energia=self.id_energia, id=True
                )
                self.subtool2.addItem(widget, f"Medida de factor de transmisión de accesorios - {energia}")
                self.tablas_fta.append({'tabla': tabla, 'id_energia': self.id_energia})

            # ----------- Tabla factores sobre el eje (con varias tablas por energía, agrupadas en un contenedor) -----------
            PPDS = ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"]
            self.tablas_fse = []
            for energia in energias:
                contenedor_fse = QWidget()
                layout_contenedor = QVBoxLayout(contenedor_fse)
                tablas_por_energia = []
                for pdd in PPDS:
                    botones = (pdd == PPDS[-1])
                    headers_fse = ["Profundidad (cm)", f"{pdd}", "PPD esperado", "Discrepancia (%)"]
                    datos_fse = [["5", "", "", ""], ["10", "", "", ""], ["15", "", "", ""]]
                    widget3, tabla_fse = PruebaMensual600.createSimpleTable1(
                        self, 3, 4, headers_fse, datos_fse, "tabla_factores_sobre_eje", self.ref,
                        botones=botones, pdd=pdd, id_energia=energia_ids.get(energia, None), id=True
                    )
                    layout_contenedor.addWidget(widget3)
                    tablas_por_energia.append({'tabla': tabla_fse, 'pdd': pdd, 'id_energia': energia_ids.get(energia, None)})
                self.subtool3.addItem(contenedor_fse, f"Medida de factores sobre el eje - {energia}")
                self.tablas_fse.append(tablas_por_energia)

            # ------------------------------- Tabla control de cámaras monitoras ---------------------------
            headers_ccm = ["Indicador", "Valor"]
            datos_ccm = [["Fac. Calibración", ""], ["Reproducibilidad", ""], ["Linealidad R2", ""], ["Tasa mínima 80 cGy/min", ""],
                        ["Tasa intermedia 160 cGy/min", ""], ["Tasa máxima 400 cGy/min", ""], ["Desviación estándar", ""]]
            self.tablas_ccm = []
            for energia in energias:
                self.id_energia = energia_ids.get(energia, None)
                widget, tabla = PruebaMensual600.createSimpleTable1(self, 7, 2, headers_ccm, datos_ccm, "tabla_control_camaras_monitoras", 
                                                                    self.ref, id_energia=self.id_energia, id=True)
                
                # Si no es el ultimo, agregar solo la tabla
                if energia != energias[-1]:
                    self.subtool4.addItem(widget, f"Medida de control de cámaras monitoras - {energia}")
                else:
                    # Si es el último, agregar la tabla con botón de reporte PDF
                    contenedor_cm  = QWidget()
                    layout_contenedor_cm = QVBoxLayout(contenedor_cm)
                    layout_contenedor_cm.addWidget(widget)
                    btn_reporte_pdf = QPushButton("Generar Reporte PDF")
                    layout_contenedor_cm.addWidget(btn_reporte_pdf)
                    btn_reporte_pdf.clicked.connect(lambda: self.generar_reporte_pdf())
                    self.subtool4.addItem(contenedor_cm, f"Medida de control de cámaras monitoras - {energia} (con reporte)")


                self.tablas_ccm.append({'tabla': tabla, 'id_energia': self.id_energia})

            # Retornar las tablas pero sin el id
            # Forma de self.tablas_fc: [{'tabla': tabla1, 'id_energia': 0}, {'tabla': tabla2, 'id_energia': 1}, ...]

            return self.tablas_fc, self.tablas_fta, self.tablas_fse, self.tablas_ccm 

        except Exception as e:
            print(f"Error creando tablas de indicadores: {e}")

    def _agregar_botones_tabla(self, layout, table, nombre_tabla, ref, id=True, id_energia=False):
        """Agrega botones de acción a la tabla optimizadamente (adaptado para IX)"""
        try:
            button_layout = QHBoxLayout()
            btn_guardar = QPushButton("Subir")
            # H2.7: el botón "Guardar" (borrador JSON local,
            # _guardar_tabla_optimizada) se eliminó -- BD única fuente.
            button_layout.addWidget(btn_guardar)
            layout.addLayout(button_layout)

            def guardar_todas_fse():
                # Buscar si la tabla está en alguna sublista de self.tablas_fse
                found = False
                if hasattr(self, "tablas_fse"):
                    for tablas_por_energia in self.tablas_fse:
                        if table in [t['tabla'] for t in tablas_por_energia]:
                            found = True
                            for entry in tablas_por_energia:
                                tabla_fse = entry['tabla']
                                ppd = entry['pdd']
                                id_energia = entry.get('id_energia')
                                datos = []
                                loadtablacomplex(
                                    nombre_tabla, tabla_fse, datos, reference=ref, from_range=0,
                                    anual=getattr(self, "anual", False), pdd=ppd, id_energia=id_energia,
                                    id=True
                                )
                            break
                if not found:
                    # Buscar el id_energia correspondiente a la tabla individual
                    id_energia = None
                    if hasattr(self, "tablas_fc"):
                        for entry in self.tablas_fc:
                            if entry['tabla'] is table:
                                id_energia = entry.get('id_energia')
                                break
                    if id_energia is None and hasattr(self, "tablas_fta"):
                        for entry in self.tablas_fta:
                            if entry['tabla'] is table:
                                id_energia = entry.get('id_energia')
                                break
                    if id_energia is None and hasattr(self, "tablas_ccm"):
                        for entry in self.tablas_ccm:
                            if entry['tabla'] is table:
                                id_energia = entry.get('id_energia')
                                break

                    datos = []
                    loadtablacomplex(
                        nombre_tabla, table, datos, reference=ref, from_range=0,
                        anual=getattr(self, "anual", False), id_energia=id_energia, id=True
                    )

                # A6.4 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): uno de los
                # 3 puntos de cierre reales de loadtablacomplex -- un solo
                # click aquí puede subir VARIAS tablas FSE (una por energía)
                # en bucle; 1 fila de auditoría para la acción completa.
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

# P1 (PLAN_P1_POOL_CONEXIONES_27-07.md): la clase con estado que vivía aquí
# fue reemplazada por la fachada sin estado de services/db_pool.py.
from services.db_pool import DatabaseManager


class PruebaImagenesIX(PruebaMensualTAC):
    def __init__(self, user_id, ref=None):
        print("PruebaImagenesIX  __init__ called")
        self.esiX_images = True
        self.anual = True
        
        self.db_manager = DatabaseManager()
        self.equipo_f = "Clinac ix"
        self.img_analysis = True
        print(self.equipo_f)
        print("ENTRANDO A PRUEBA IMAGENES IX")
       
        super().__init__(user_id)
        self.ref = ref
        self.ref_ix_img = ref  # Ahora recibe el ref compartido
        if hasattr(self, 'datebox') and self.date_box:
            print("Cajita de fecha encontrada")
        print(f"PruebaImagenesIX received ref: {self.ref_ix_img}")
        
        
       
        
        

    # def limpiar_layout(self, layouts, user_id, maquina, user_id_f2=None,  nombre_fisico1=None, nombre_fisico2=None):
    #     fecha = self.date_box.date()
    #     fecha = fecha.toString("MM/yyyy")
    #     for layout in layouts:
    #         while layout.count():
    #             child = layout.takeAt(0)
    #             if child.widget():
    #                 child.widget().deleteLater()
    #     self.ref = self.ref_ix_img
    #     #print(f"ID Sesión: {self.ref}")
