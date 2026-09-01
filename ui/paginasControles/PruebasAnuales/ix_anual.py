from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from PyQt5 import sip
from PyQt5.QtWidgets import (QWidget, QToolBox, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox,
                              QTableWidgetItem)
from data.ManejoDatos.load import loadtablacomplex
from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
from data.ManejoDatos.catphan_TAC.slice_matcher import detectar_y_resolver_modulos
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import ACCION_GUARDAR
class PruebaAnualIX(PruebaAnual600):
    # E1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 2, F-3/F-4/AN-6): fotones y
    # electrones dejaban de compartir definición de tamaños/PDD/profundidad
    # -- los 4 ensayos de electrones (6/9/12/15 MeV) pedían tamaños y
    # profundidades de fotones, y no había dónde poner los factores de cono
    # ni las profundidades reales. Valores medidos directamente del formato
    # oficial 2025 (`IDC-F-RT-120 ... V2.xlsx`, hoja "Nuevo").
    _DEF_FOTON = {
        "tamanos_campo": ["3x3", "10x10", "15x15", "20x20", "25x25", "30x30", "35x35", "40x40"],
        "encabezado_tamano": "Tamaño de campo",
        "pdds": ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"],
        "profundidades": ["5", "10", "20"],
        "unidad_profundidad": "cm",
    }
    _DEF_ELECTRON_BASE = {
        "tamanos_campo": ["6x6", "10x10", "15x15", "20x20", "25x25"],
        "encabezado_tamano": "Tamaño Cono",
        "pdds": ["PDD (6 x 6)", "PDD (10 x 10)", "PDD (20 x 20)"],
        "unidad_profundidad": "mm",
    }
    DEFINICIONES_ENERGIA = {
        "6 MV": dict(_DEF_FOTON),
        "15 MV": dict(_DEF_FOTON),
        "6 MeV": dict(_DEF_ELECTRON_BASE, profundidades=["12", "23.3"]),
        "9 MeV": dict(_DEF_ELECTRON_BASE, profundidades=["19", "35.5"]),
        "12 MeV": dict(_DEF_ELECTRON_BASE, profundidades=["25", "49.4"]),
        "15 MeV": dict(_DEF_ELECTRON_BASE, profundidades=["18", "61.9"]),
    }

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
            self.subtool5 = QToolBox()  # R2: lecturas crudas de Linealidad

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

            # R1/R2/R3 (PLAN_REPARACION_ANUAL_27-08.md §Fase 3, F-5): las
            # lecturas crudas de la hoja "Linealidad" -- linealidad_um y
            # lecturas_fc derivan y rellenan su columna de factor (R3);
            # transmisión y tasa de dosis son captura pura, sin derivado.
            tablas_um, tablas_lfc, tablas_lt, _ = self._crear_tablas_linealidad()
            for entry in tablas_um:
                tabla_obj = entry['tabla']
                self._configurar_eventos(
                    tabla_obj, callback=self._derivar_factor_linealidad_um(tabla_obj),
                    timer_key=f"debounce_{tabla_obj.objectName()}", delay=300)
            for entry in tablas_lfc:
                tabla_obj = entry['tabla']
                self._configurar_eventos(
                    tabla_obj, callback=self._derivar_factor_lecturas_campo(tabla_obj),
                    timer_key=f"debounce_{tabla_obj.objectName()}", delay=300)
            for entry in tablas_lt:
                tabla_obj = entry['tabla']
                self._configurar_eventos(
                    tabla_obj, callback=self._derivar_factor_transmision(tabla_obj),
                    timer_key=f"debounce_{tabla_obj.objectName()}", delay=300)

        except Exception as e:
            print(f"Error configurando subtoolbox: {e}")
            self.subtool = QWidget()
            self.subtool2 = QWidget()
            self.subtool3 = QWidget()
            self.subtool4 = QWidget()
            self.subtool5 = QWidget()

    def _configurar_toolbox_principal(self, toolbox):
        """Configura el toolbox principal con todas las categorías"""
        try:
            # Añadir categorías al toolbox
            toolbox.addItem(self.category1, "EQUIPOS DE MEDICIÓN")
            toolbox.addItem(self.subtool, "FACTOR DE CAMPO")
            toolbox.addItem(self.subtool2, "FACTOR DE TRANSMISIÓN")
            toolbox.addItem(self.subtool3, "FACTOR SOBRE EL EJE")
            toolbox.addItem(self.subtool4, "CONTROL DE CÁMARAS")
            toolbox.addItem(self.subtool5, "LECTURAS DE LINEALIDAD")

        except Exception as e:
            print(f"Error configurando toolbox principal: {e}")

    def _crear_tablas_pruebas(self):
        try:

            # Diccionario con el id de la energía para Clinac ix
            energia_ids = {"6 MV": 0, "15 MV": 1, "6 MeV": 2, "9 MeV": 3, "12 MeV": 4, "15 MeV": 5}
            energias = ["6 MV", "15 MV", "6 MeV", "9 MeV", "12 MeV", "15 MeV"]

            # ------------------------------ Tabla de factores de campo (fotones) / cono (electrones) ---------------------------------
            # E1: cada energía trae su propia definición -- fotones (8
            # tamaños de campo) y electrones (5 conos) ya NO comparten
            # `datos_fc`. Las filas salen de `len(datos_fc)`, nunca de un
            # número escrito aparte: el descuadre 6<->8 (F-4/AN-6) deja de
            # ser posible, no solo deja de estar.
            self.tablas_fc = []
            for energia in energias:
                defin = self.DEFINICIONES_ENERGIA[energia]
                headers_fc = [defin["encabezado_tamano"], "Factor de campo", "Factor esperado", "Discrepancia (%)"]
                datos_fc = [[tamano, "", "", ""] for tamano in defin["tamanos_campo"]]
                self.id_energia = energia_ids.get(energia, None)
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, len(datos_fc), 4, headers_fc, datos_fc, "tabla_factor_campo", self.ref, id_energia=self.id_energia, id=True
                )
                self.subtool.addItem(widget, f"Medida de factor de campo - {energia}")
                self.tablas_fc.append({'tabla': tabla, 'id_energia': self.id_energia})

            # ------------------------- Tabla factores de transmisión de accesorios -------------------------
            # Fuera de alcance de E1 -- el formato pide lo mismo para las 6 energías.
            headers_fta = ["Accesorio", "Factor de transmisión", "Factor esperado", "Discrepancia (%)"]
            datos_fta = [ ["15°", "", "",""], ["30°", "", "", ""], ["45°", "", "", ""], ["60°", "", "", ""], ["MLC", "", "", ""]]
            self.tablas_fta = []
            for energia in energias:
                self.id_energia = energia_ids.get(energia, None)
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, len(datos_fta), 4, headers_fta, datos_fta, "tabla_factores_transmision", self.ref, id_energia=self.id_energia, id=True
                )
                self.subtool2.addItem(widget, f"Medida de factor de transmisión de accesorios - {energia}")
                self.tablas_fta.append({'tabla': tabla, 'id_energia': self.id_energia})

            # ----------- Tabla factores sobre el eje (PDD y profundidad, por energía) -----------
            # E1: los PDD y las profundidades (unidad incluida) salen de
            # DEFINICIONES_ENERGIA -- electrones ya no heredan los PDD ni
            # las profundidades en cm de fotones.
            self.tablas_fse = []
            for energia in energias:
                defin = self.DEFINICIONES_ENERGIA[energia]
                contenedor_fse = QWidget()
                layout_contenedor = QVBoxLayout(contenedor_fse)
                tablas_por_energia = []
                pdds = defin["pdds"]
                for pdd in pdds:
                    botones = (pdd == pdds[-1])
                    headers_fse = [f"Profundidad ({defin['unidad_profundidad']})", f"{pdd}", "PPD esperado", "Discrepancia (%)"]
                    datos_fse = [[prof, "", "", ""] for prof in defin["profundidades"]]
                    widget3, tabla_fse = PruebaMensual600.createSimpleTable1(
                        self, len(datos_fse), 4, headers_fse, datos_fse, "tabla_factores_sobre_eje", self.ref,
                        botones=botones, pdd=pdd, id_energia=energia_ids.get(energia, None), id=True
                    )
                    layout_contenedor.addWidget(widget3)
                    tablas_por_energia.append({'tabla': tabla_fse, 'pdd': pdd, 'id_energia': energia_ids.get(energia, None)})
                self.subtool3.addItem(contenedor_fse, f"Medida de factores sobre el eje - {energia}")
                self.tablas_fse.append(tablas_por_energia)

            # ------------------------------- Tabla control de cámaras monitoras ---------------------------
            # E1 (tasas de cámaras monitoras, "idem" en fotones y
            # electrones per el formato oficial): eran 80/160/400 cGy/min,
            # deben ser 100/400/600 cGy/min -- iguales para las 6 energías.
            headers_ccm = ["Indicador", "Valor"]
            # A1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 4, F-6): fila libre
            # de "Observaciones" -- el formato oficial trae contenido
            # clínicamente relevante ahí (ej. una desviación de protocolo)
            # y ninguna tabla anual del 600/iX tenía dónde ponerlo. Misma
            # tabla, sin columna nueva -- "Desviación estándar" ya
            # demuestra que esta tabla acepta texto libre en "Valor".
            datos_ccm = [["Fac. Calibración", ""], ["Reproducibilidad", ""], ["Linealidad R2", ""], ["Tasa mínima 100 cGy/min", ""],
                        ["Tasa máxima 400 cGy/min", ""], ["Tasa máxima 600 cGy/min", ""], ["Desviación estándar", ""],
                        ["Observaciones", ""]]
            self.tablas_ccm = []
            for energia in energias:
                self.id_energia = energia_ids.get(energia, None)
                widget, tabla = PruebaMensual600.createSimpleTable1(self, len(datos_ccm), 2, headers_ccm, datos_ccm, "tabla_control_camaras_monitoras",
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

    # Niveles/accesorios/tasas de la hoja "Linealidad" del formato oficial
    # (IDC-F-RT-120 V2.xlsx) -- iguales para las 6 energías salvo donde se
    # indica lo contrario.
    NIVELES_UM_LINEALIDAD = ["50", "100", "150", "200", "250", "300", "350", "400", "500", "600"]
    ACCESORIOS_TRANSMISION = ["Open", "15°", "30°", "45°", "60°", "MLC"]
    TASAS_DOSIS_UM_MIN = ["100", "300", "400", "600"]
    # F-5: la constancia de tasa de dosis solo se mide en el formato real
    # para las 2 energías de fotones -- no hay bloque de electrones en la
    # hoja "Linealidad" para este ensayo.
    ENERGIAS_CON_TASA_DOSIS = frozenset({"6 MV", "15 MV"})

    def _crear_tablas_linealidad(self):
        """R1/R2 (PLAN_REPARACION_ANUAL_27-08.md §Fase 3, F-5): paneles de
        captura para las lecturas crudas de la hoja "Linealidad" -- lo que
        hoy solo se guarda como factor final derivado. Mismo diccionario
        por energía que E1 (`DEFINICIONES_ENERGIA`) reusa aquí para que la
        tabla de factor de campo/cono de las lecturas pida exactamente los
        mismos tamaños/conos que su hermana ya construida. Sin lógica
        nueva de guardado: las 4 tablas usan loadtablacomplex/
        reemplazar_bloque como las que ya existen (ver la extensión de
        búsqueda de id_energia en _agregar_botones_tabla)."""
        try:
            energia_ids = {"6 MV": 0, "15 MV": 1, "6 MeV": 2, "9 MeV": 3, "12 MeV": 4, "15 MeV": 5}
            energias = ["6 MV", "15 MV", "6 MeV", "9 MeV", "12 MeV", "15 MeV"]

            # 1. Linealidad de unidades monitor: 6 energías x 10 niveles.
            headers_um = ["UM", "Q1 (nC)", "Q2 (nC)", "Q (nC)"]
            self.tablas_linealidad_um = []
            for energia in energias:
                datos_um = [[um, "", "", ""] for um in self.NIVELES_UM_LINEALIDAD]
                self.id_energia = energia_ids[energia]
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, len(datos_um), 4, headers_um, datos_um, "anual_linealidad_um",
                    self.ref, id_energia=self.id_energia, id=True)
                self.subtool5.addItem(widget, f"Linealidad de unidades monitor - {energia}")
                self.tablas_linealidad_um.append({'tabla': tabla, 'id_energia': self.id_energia})

            # 2. Lecturas de factor de campo (fotones) / cono (electrones):
            # mismos tamaños que la tabla de factor de campo de E1.
            self.tablas_lecturas_fc = []
            for energia in energias:
                defin = self.DEFINICIONES_ENERGIA[energia]
                es_cono = defin["encabezado_tamano"] == "Tamaño Cono"
                headers_lfc = [defin["encabezado_tamano"], "Q1 (nC)", "Q2 (nC)", "Q (nC)", "Factor"]
                datos_lfc = [[tamano, "", "", "", ""] for tamano in defin["tamanos_campo"]]
                self.id_energia = energia_ids[energia]
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, len(datos_lfc), 5, headers_lfc, datos_lfc, "anual_lecturas_factor_campo",
                    self.ref, id_energia=self.id_energia, id=True)
                titulo = "cono" if es_cono else "campo"
                self.subtool5.addItem(widget, f"Lecturas de factor de {titulo} - {energia}")
                self.tablas_lecturas_fc.append({'tabla': tabla, 'id_energia': self.id_energia})

            # 3. Lecturas de transmisión de cuñas: 6 energías x 6 accesorios
            # (incluye "Open", el denominador de T = Q(cuña)/Q(open)).
            headers_lt = ["Accesorio", "Q1 IN (nC)", "Q2 IN (nC)", "Q1 OUT (nC)", "Q2 OUT (nC)", "Q MED (nC)", "T"]
            self.tablas_lecturas_transmision = []
            for energia in energias:
                datos_lt = [[acc, "", "", "", "", "", ""] for acc in self.ACCESORIOS_TRANSMISION]
                self.id_energia = energia_ids[energia]
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, len(datos_lt), 7, headers_lt, datos_lt, "anual_lecturas_transmision",
                    self.ref, id_energia=self.id_energia, id=True)
                self.subtool5.addItem(widget, f"Lecturas de transmisión de cuñas - {energia}")
                self.tablas_lecturas_transmision.append({'tabla': tabla, 'id_energia': self.id_energia})

            # 4. Tasa de dosis (constancia): solo fotones (F-5, medido).
            headers_td = ["Tasa (UM/min)", "Med 1", "Med 2"]
            self.tablas_tasa_dosis = []
            for energia in energias:
                if energia not in self.ENERGIAS_CON_TASA_DOSIS:
                    continue
                datos_td = [[tasa, "", ""] for tasa in self.TASAS_DOSIS_UM_MIN]
                self.id_energia = energia_ids[energia]
                widget, tabla = PruebaMensual600.createSimpleTable1(
                    self, len(datos_td), 3, headers_td, datos_td, "anual_tasa_dosis",
                    self.ref, id_energia=self.id_energia, id=True)
                self.subtool5.addItem(widget, f"Tasa de dosis (constancia) - {energia}")
                self.tablas_tasa_dosis.append({'tabla': tabla, 'id_energia': self.id_energia})

            return (self.tablas_linealidad_um, self.tablas_lecturas_fc,
                    self.tablas_lecturas_transmision, self.tablas_tasa_dosis)

        except Exception as e:
            print(f"Error creando tablas de linealidad: {e}")
            return [], [], [], []

    # R3: _derivar_factor_linealidad_um / _derivar_factor_lecturas_campo /
    # _derivar_factor_transmision viven en PruebaAnual600 (seiscientos_anual.py)
    # -- son genéricas por tabla, sin nada específico de energía, y las
    # reusa el 600 igual que iX (mismo criterio que _calcular_discrepancias_tablas).

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
                # B1 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase B, R3): esta
                # copia de guardar_todas_fse no usaba el retorno de
                # loadtablacomplex -- mismo síntoma H3 que AV1 ya corrigió
                # en el gemelo (seiscientos_anual.py), sin tocar esta copia.
                # Medido en el rebuild: `ref=19`, `id_energia=1`, el índice
                # UNIQUE de CL1 rechazó el bloque (0 filas en
                # tabla_factor_campo) y esta función igual imprimía "subida
                # correctamente". Se copia la misma transformación: juntar
                # el resultado de cada loadtablacomplex y avisar si alguno
                # falló, antes de auditar.
                resultados = []
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
                                resultados.append(loadtablacomplex(
                                    nombre_tabla, tabla_fse, datos, reference=ref, from_range=0,
                                    anual=getattr(self, "anual", False), pdd=ppd, id_energia=id_energia,
                                    id=True
                                ))
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
                    # R2 (PLAN_REPARACION_ANUAL_27-08.md §Fase 3): mismo
                    # patrón de búsqueda para los 4 paneles nuevos de
                    # lecturas de Linealidad -- sin esto, id_energia se
                    # queda en None y el guardado deja de acotar el
                    # reemplazo de bloque a la energía correcta.
                    for nombre_lista in ("tablas_linealidad_um", "tablas_lecturas_fc",
                                         "tablas_lecturas_transmision", "tablas_tasa_dosis"):
                        if id_energia is not None:
                            break
                        for entry in getattr(self, nombre_lista, []):
                            if entry['tabla'] is table:
                                id_energia = entry.get('id_energia')
                                break

                    datos = []
                    resultados.append(loadtablacomplex(
                        nombre_tabla, table, datos, reference=ref, from_range=0,
                        anual=getattr(self, "anual", False), id_energia=id_energia, id=True
                    ))

                self._actualizar_tabla_despues_subida()

                if not all(resultados):
                    QMessageBox.critical(
                        self, "Error",
                        f"No se pudo guardar {nombre_tabla}. Revise la "
                        "consola para el detalle -- no se avisó nada antes "
                        "de este arreglo, así que si ve este mensaje, "
                        "vuelva a intentarlo.")
                    return

                # A6.4 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): uno de los
                # 3 puntos de cierre reales de loadtablacomplex -- un solo
                # click aquí puede subir VARIAS tablas FSE (una por energía)
                # en bucle; 1 fila de auditoría para la acción completa.
                # B1: solo se audita un guardado que de verdad ocurrió.
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
                print(f"Tabla(s) {nombre_tabla} subida(s) correctamente")
                # A2 (PLAN_REPARACION_ANUAL_27-08.md §Fase 4, AN-7): el
                # gemelo (seiscientos_anual.py) ya avisaba el éxito con un
                # QMessageBox además del print -- esta copia se había
                # quedado con el aviso de FALLO (B1, 26-08) sin el de
                # éxito. El físico pulsaba "Subir" y no veía nada si el
                # guardado salía bien.
                QMessageBox.information(self, "", "Datos subidos correctamente")

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
