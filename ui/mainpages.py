from PyQt5.QtWidgets import (QMessageBox, QSizePolicy, QTabWidget, QAction, QMainWindow, QMenuBar, QPushButton,
                            QWidget, QVBoxLayout,  QStackedWidget, QHBoxLayout, QMenu)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise
import sys, os, shutil, importlib
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from data.ManejoDatos.usuariosManager import UsuarioData
from services.audit_minimo import usuario_actual as _usuario_actual

class Menuu(QWidget):
    finished = pyqtSignal()
    def __init__(self, maquina, user_id):
        super(Menuu, self).__init__()
        self.maquina = maquina
        self.user_id = user_id
        
        # Cache para clases importadas dinámicamente
        self._imported_classes = {}
        self.iniGUI()

        
        

    def _importar_clase(self, nombre_modulo, nombre_clase):
        """
        Importa una clase dinámicamente desde un módulo.
        Utiliza cache para evitar reimportar módulos ya cargados.
        
        Args:
            nombre_modulo (str): Ruta completa del módulo (ej: 'ui.paginasControles.PruebasDiarias.halcyon')
            nombre_clase (str): Nombre de la clase a importar (ej: 'PruebaDiariaHc')
        
        Returns:
            class: La clase importada, o None si falla la importación
        """
        # Crear clave única para el cache
        cache_key = f"{nombre_modulo}.{nombre_clase}"

        # Verificar si ya está en cache
        if cache_key in self._imported_classes:
            return self._imported_classes[cache_key]

        try:
            # Importar el módulo dinámicamente
            modulo = importlib.import_module(nombre_modulo)

            # Obtener la clase del módulo
            clase = getattr(modulo, nombre_clase)

            # Guardar en cache
            self._imported_classes[cache_key] = clase

            #print(f"✓ Clase '{nombre_clase}' importada exitosamente desde '{nombre_modulo}'")
            return clase

        except ModuleNotFoundError as e:
            print(f"✗ Error: No se encontró el módulo '{nombre_modulo}': {e}")
            return None
        except AttributeError as e:
            print(f"✗ Error: La clase '{nombre_clase}' no existe en el módulo '{nombre_modulo}': {e}")
            return None
        except Exception as e:
            print(f"✗ Error inesperado al importar '{nombre_clase}' desde '{nombre_modulo}': {e}")
            return None

    def iniGUI(self):
        master_layout = QHBoxLayout(self)
        master_layout.setContentsMargins(0, 0, 0, 0)

        self.menu_widget = QWidget()
        menu_layout = QVBoxLayout(self.menu_widget)

        # Layout para los botones de arriba
        top_buttons_layout = QVBoxLayout()
        if self.maquina != "Tomógrafo":
            self.pd_btn = QPushButton('Diaria')
            top_buttons_layout.addWidget(self.pd_btn)

        self.pm_btn = QPushButton('Mensual')
        self.pa_btn = QPushButton('Anual')
        if self.maquina in ("Halcyon", "iX"):
            self.pm_img_btn = QPushButton("Imágenes\nMensual")
            self.pa_img_btn = QPushButton("Imágenes\nAnual")
        self.back_button = QPushButton('Inicio')

        top_buttons_layout.addWidget(self.pm_btn)
        if self.maquina != "Braquiterapia":
            top_buttons_layout.addWidget(self.pa_btn)

        if self.maquina in ("Halcyon", "iX"):
            top_buttons_layout.addWidget(self.pm_img_btn)
            top_buttons_layout.addWidget(self.pa_img_btn)

        if self.maquina == "Braquiterapia":
            self.cf_btn = QPushButton("Cal. Fuente")

            # Crear menú desplegable
            menu = QMenu(self)
            actividad_action = menu.addAction("Calibración Redundante")
            linealidad_action = menu.addAction("Linealidad de la Fuente")
            posicionamiento_action = menu.addAction("Posicionamiento Inicial")
            self.cf_btn.setMenu(menu)

            # Conexión de acciones del menú
            actividad_action.triggered.connect(lambda: self.seleccionar_cambio_fuente("Calibración Redundante"))
            linealidad_action.triggered.connect(lambda: self.seleccionar_cambio_fuente("Linealidad de la Fuente"))
            posicionamiento_action.triggered.connect(lambda: self.seleccionar_cambio_fuente("Posicionamiento Inicial"))

            top_buttons_layout.addWidget(self.cf_btn)

        top_buttons_layout.addWidget(self.back_button)

        menu_layout.addLayout(top_buttons_layout)
        menu_layout.addStretch()

        self.pages_widget = QStackedWidget()

        # Estructura para almacenar referencias diferidas de cada vista
        self._paginas = {}

        # Conectamos los botones para cargar cada sección solo cuando el usuario la solicita
        if self.maquina != "Tomógrafo":
            self.pd_btn.clicked.connect(lambda: self._mostrar_pagina("diaria"))

        self.pm_btn.clicked.connect(lambda: self._mostrar_pagina("mensual"))

        self.pa_btn.clicked.connect(lambda: self._mostrar_pagina("anual"))
        if self.maquina in ("Halcyon", "iX"):
            self.pa_img_btn.clicked.connect(lambda: self._mostrar_pagina("imagen_anual"))
            self.pm_img_btn.clicked.connect(lambda: self._mostrar_pagina("imagen_mensual"))
        # Layout principal
        master_layout.addWidget(self.menu_widget, 5)
        master_layout.addWidget(self.pages_widget, 95)

        # Conectar botones
        self.back_button.clicked.connect(self.entrada)

        self.menu_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.pages_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Mostramos la primera vista disponible en función de la máquina
        if self.maquina != "Tomógrafo":
            self._mostrar_pagina("diaria")
        else:
            self._mostrar_pagina("mensual")

    # Método auxiliar dentro de la clase
    def seleccionar_cambio_fuente(self, opcion):
        self.cf_btn.setText(f"{opcion}")
        if opcion == "Calibración Redundante":
            self._mostrar_pagina("cal_fuente")
        elif opcion == "Linealidad de la Fuente":
            self._mostrar_pagina("linealidad")
        elif opcion == "Posicionamiento Inicial":
            self._mostrar_pagina("posicionamiento")

    def block(self):
        #self.pd_btn.setEnabled(False)
        #self.pm_btn.setEnabled(False)
        self.pa_btn.setEnabled(False)

    def entrada(self):
        self.finished.emit()

    def _mostrar_pagina(self, clave):
        """Muestra la vista solicitada, creándola si aún no existe."""
        widget = self._obtener_pagina(clave)
        if widget is not None:
            self.pages_widget.setCurrentWidget(widget)

    def _obtener_pagina(self, clave):
        """Devuelve la vista asociada a la clave, utilizando carga diferida."""
        if clave in self._paginas:
            return self._paginas[clave]

        widget = self._crear_pagina(clave)
        if widget is None:
            return None

        self._paginas[clave] = widget
        self.pages_widget.addWidget(widget)
        return widget

    def _crear_pagina(self, clave):
        """Construye la vista correspondiente a la clave indicada."""
        if clave == "diaria":
            if self.maquina == "Halcyon":
                PruebaDiariaHc = self._importar_clase(
                    "ui.paginasControles.PruebasDiarias.halcyon",
                    "PruebaDiariaHc"
                )
                if PruebaDiariaHc:
                    return PruebaDiariaHc(self.user_id)

            if self.maquina == "iX":
                PruebaDiariaIX = self._importar_clase(
                    "ui.paginasControles.PruebasDiarias.IX",
                    "PruebaDiariaIX"
                )
                if PruebaDiariaIX:
                    return PruebaDiariaIX(self.user_id)

            if self.maquina == "600":
                PruebaDiaria600 = self._importar_clase(
                    "ui.paginasControles.PruebasDiarias.seiscientos",
                    "PruebaDiaria600"
                )
                if PruebaDiaria600:
                    return PruebaDiaria600(self.user_id)

            if self.maquina == "Braquiterapia":
                PruebaDiariaBraq = self._importar_clase(
                    "ui.paginasControles.PruebasDiarias.braquiterapia",
                    "PruebaDiariaBraq"
                )
                if PruebaDiariaBraq:
                    return PruebaDiariaBraq(self.user_id)
            return None

        if clave == "mensual":
            if self.maquina == "Halcyon":
                PruebaMensualHc = self._importar_clase(
                    "ui.paginasControles.PruebasMensuales.PruebasMensuales",
                    "PruebaMensualHc"
                )
                if PruebaMensualHc:
                    return PruebaMensualHc(self.user_id)

            if self.maquina == "iX":
                PruebaMensualIX = self._importar_clase(
                    "ui.paginasControles.PruebasMensuales.PruebasMensuales",
                    "PruebaMensualIX"
                )
                if PruebaMensualIX:
                    return PruebaMensualIX(self.user_id)

            if self.maquina == "600":
                PruebaMensual600 = self._importar_clase(
                    "ui.paginasControles.PruebasMensuales.seiscientos_mensual",
                    "PruebaMensual600"
                )
                if PruebaMensual600:
                    return PruebaMensual600(self.user_id, equipo_f="Clinac 600")

            if self.maquina == "Braquiterapia":
                PruebaMensualBraq = self._importar_clase(
                    "ui.paginasControles.PruebasMensuales.PruebasMensuales",
                    "PruebaMensualBraq"
                )
                if PruebaMensualBraq:
                    return PruebaMensualBraq(self.user_id)

            if self.maquina == "Tomógrafo":
                PruebaMensualTAC = self._importar_clase(
                    "ui.paginasControles.PruebasMensuales.PruebasMensuales",
                    "PruebaMensualTAC"
                )
                if PruebaMensualTAC:
                    return PruebaMensualTAC(self.user_id)
            return None

        if clave == "anual":    
            if self.maquina == "600":
                PruebaAnual600 = self._importar_clase(
                    "ui.paginasControles.PruebasAnuales.seiscientos_anual",
                    "PruebaAnual600"
                )
                if PruebaAnual600:
                    return PruebaAnual600(self.user_id, equipo_f="Clinac 600")

            if self.maquina == "iX":
                PruebaAnualIX = self._importar_clase(
                    "ui.paginasControles.PruebasAnuales.ix_anual",
                    "PruebaAnualIX"
                )
                if PruebaAnualIX:
                    self._pagina_anual_ix = PruebaAnualIX(self.user_id)
                    return self._pagina_anual_ix

            if self.maquina == "Halcyon":
                # Guarda la instancia anual para compartir ref
                PruebaAnualHalcyon = self._importar_clase(
                    "ui.paginasControles.PruebasAnuales.halcyon_anual",
                    "PruebaAnualHalcyon"
                )
                if PruebaAnualHalcyon:
                    self._pagina_anual_hc = PruebaAnualHalcyon(self.user_id)
                    return self._pagina_anual_hc
            return None
        if clave == "imagen_mensual":
            if self.maquina == "iX":
                PruebaImagenesIX = self._importar_clase(
                    "ui.paginasControles.PruebasMensuales.PruebasMensuales",
                    "PruebaImagenesIX"
                )
                if PruebaImagenesIX:
                    return PruebaImagenesIX(self.user_id)
            if self.maquina == "Halcyon":
                PruebaImagenesHC = self._importar_clase("ui.paginasControles.PruebasMensuales.PruebasMensuales",
                    "PruebaImagenesHC")
                if PruebaImagenesHC:
                    return PruebaImagenesHC(self.user_id)

        if clave == "imagen_anual":
            if self.maquina == "Halcyon":
                # Usa el ref de la instancia anual si existe
                ref = getattr(self, "_pagina_anual_hc", None)
                ref_val = ref.ref if ref is not None else None
                #print("Creando PruebaImagenesHalcyon con ref:", ref_val)
                
                PruebaImagenesHalcyon = self._importar_clase(
                    "ui.paginasControles.PruebasAnuales.halcyon_anual",
                    "PruebaImagenesHalcyon"
                )
                if PruebaImagenesHalcyon:
                    return PruebaImagenesHalcyon(self.user_id, ref=ref_val)

            if self.maquina == "iX":
                ref = getattr(self, "_pagina_anual_ix", None)
                ref_val = ref.ref if ref is not None else None
                #print("Creando PruebaImagenesIX con ref:", ref_val)

                PruebaImagenesIX = self._importar_clase(
                    "ui.paginasControles.PruebasAnuales.ix_anual",
                    "PruebaImagenesIX"
                )
                if PruebaImagenesIX:
                    return PruebaImagenesIX(self.user_id, ref=ref_val)
            return None

        if self.maquina != "Braquiterapia":
            return None

        if clave == "cal_fuente":
            CalRedundanteFuente = self._importar_clase(
                "ui.paginasControles.PruebasDiarias.braquiterapia",
                "CalRedundanteFuente"
            )
            if CalRedundanteFuente:
                return CalRedundanteFuente(self.user_id)

        if clave == "linealidad":
            Linealidad = self._importar_clase(
                "ui.paginasControles.PruebasDiarias.braquiterapia",
                "Linealidad"
            )
            if Linealidad:
                return Linealidad(self.user_id)

        if clave == "posicionamiento":
            mensual = self._obtener_pagina("mensual")
            if mensual is not None and hasattr(mensual, "posicionamiento"):
                return mensual.posicionamiento
            return None
        return None

class MainWindow(QMainWindow):
    reRun_signal = pyqtSignal()
    def __init__(self, user_id):
        #print("MainWindow             __init__ called")
        super().__init__()
        # A4 (PLAN_AUDITORIA_DOS_EJES_21-07): antes quedaba comentado -- sin
        # esto, cerrar() no tenía forma de saber quién cierra sesión.
        self.user_id = user_id

        self.Tab(user_id)
        self.estilo()
        self.showMaximized()
        self.settings()
        #self.block()
        #self.back_button = QPushButton('Volver al inicio')
        #self.back_button.clicked.connect(lambda: switch_page_callback('login'))

    def settings(self):
        self.setWindowTitle("Graficador de pruebas")
        self.showMaximized()
        ICONO =  resource_path('resources/icons/icono.png')
        self.setWindowIcon(QIcon(ICONO))
        #self._old_pos = None

    def Tab(self, user_id):
        #self.layout = QVBoxLayout(self) malooooo
        widget_central = QWidget(self)
        widget_central.setContentsMargins(0, 0, 0, 0)


        self.setCentralWidget(widget_central)
        self.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout(widget_central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        #layout.addWidget(self.barra_superior)

        # Inicializamos el contenedor de pestañas
        self.tabs = QTabWidget()

        # Definimos las pestañas con carga diferida; cada lambda crea la vista cuando sea necesaria
        self._tab_definiciones = [
            ("600", lambda: Menuu("600", user_id)),
            ("iX", lambda: Menuu("iX", user_id)),
            ("Halcyon", lambda: Menuu("Halcyon", user_id)),
            ("Braquiterapia", lambda: Menuu("Braquiterapia", user_id)),
            ("Tomógrafo", lambda: Menuu("Tomógrafo", user_id)),
            ("Equipos", lambda: self._crear_config()),
            ("Excel", lambda: self.ExportarExcel()),  # Ejemplo de otra pestaña
            #("Registros", lambda: self.Registros())
        ]
        self._tab_instancias = {}

        # Añadimos contenedores vacíos para mantener la estructura del QTabWidget
        for titulo, _ in self._tab_definiciones:
            marcador = QWidget()
            marcador.setLayout(QVBoxLayout())  # Evita advertencias de Qt al reemplazar el widget más tarde
            self.tabs.addTab(marcador, titulo)

        layout.addWidget(self.tabs)

        # Conectamos el cambio de pestaña al cargador diferido y cargamos la primera pestaña visible
        self.tabs.currentChanged.connect(self._cargar_pestania_diferida)
        self._cargar_pestania_diferida(0)

    def block(self):    
        # Deshabilitar la segunda pestaña (índice 1)
        #self.tabs.setTabEnabled(2, False)
        #self.tabs.setTabEnabled(4, False)
        return

    def _crear_config(self):
        """Importa y crea la configuración de equipos dinámicamente."""
        try:
            modulo = importlib.import_module("ui.paginasGuia.equipos")
            Config = getattr(modulo, "Config")
            #print("✓ Clase 'Config' importada exitosamente desde 'ui.paginasGuia.equipos'")
            return Config()
        except Exception as e:
            print(f"✗ Error importando Config: {e}")
            return QWidget()  # Widget vacío como fallback
    def ExportarExcel(self):
        """Importa y crea la vista de exportación a Excel."""
        try: 
            modulo = importlib.import_module("ui.paginasGuia.SQLtoEXCEL")
            ExportarExcel = getattr(modulo, "ExportarExcel")
            return ExportarExcel()
        except Exception as e:
            print(f"✗ Error importando ExportarExcel: {e}")
            return QWidget()  # Widget vacío como fallback
        
    # def Registros(self):
    #     """Importa y crea la vista de exportación a Excel."""
    #     try: 
    #         modulo = importlib.import_module("ui.paginasGuia.console_logs")
    #         Console_logs = getattr(modulo, "Registros")
    #         return Console_logs()
    #     except Exception as e:
    #         print(f"✗ Error registros auditorias: {e}")
    #         return QWidget()  # Widget vacío como fallback

    def _cargar_pestania_diferida(self, indice):
        """Carga la pestaña solicitada únicamente cuando el usuario la visita."""
        if indice < 0 or indice >= len(self._tab_definiciones):
            return

        if indice in self._tab_instancias:
            return

        titulo, fabrica = self._tab_definiciones[indice]
        try:
            widget_real = fabrica()
        except Exception as error:
            # Mostramos un mensaje claro en consola en caso de que la creación falle.
            print(f"Error al crear la pestaña '{titulo}': {error}")
            return

        self._tab_instancias[indice] = widget_real
        self.tabs.removeTab(indice)
        self.tabs.insertTab(indice, widget_real, titulo)
        self.tabs.setCurrentIndex(indice)

        if isinstance(widget_real, Menuu):
            widget_real.finished.connect(self.cerrar)

    def cerrar(self):
        UsuarioData().logout(_usuario_actual(self))
        self.reRun_signal.emit()
        self.close()

    def estilo(self):

        dpi = self.screen().logicalDotsPerInch()
        font_size = int(dpi * 0.145)

        ESTILO = resource_path('resources/estilo.qss')
        try:
            with open(ESTILO, "r") as f:
                hoja_estilos = f.read()
                self.setStyleSheet(hoja_estilos)
        except Exception as e:
                print(f"Error loading stylesheet: {e}")

    def menuperonalizado(self):
        #self.maximizado = True
        #self.setGeometry(100, 100, 1040, 780)
        self.barra_superior = QWidget(self)
        self.barra_superior.setFixedHeight(30)
        self.barra_superior.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) #sabra jesus de donde sale eso
        #self.barra_superior.setStyleSheet("background-color: white; color:black;")
        #self.barra_superior.setContentsMargins(0, 0, 0, 0)
        #layout_barra.setSpacing(0)   

        layout_barra = QHBoxLayout(self.barra_superior)
        layout_barra.setContentsMargins(0, 0, 0, 0)
        layout_barra.setSpacing(0)

        #MENU
        self.menu_bar = QMenuBar(self)
        self.menu_bar.setStyleSheet("background-color: white ; color:black;")
        self.menu_bar.setNativeMenuBar(False)

        menu_archivo = self.menu_bar.addMenu("Archivo")
        accion_sali = QAction("Salir", self)
        accion_sali.triggered.connect(self.close)
        menu_archivo.addAction(accion_sali)

        # Botones personalizados
        self.btn_minimizar = QPushButton(self.barra_superior)


        self.btn_minimizar.setObjectName("btn_minimizar")
        self.btn_minimizar.clicked.connect(self.showMinimized)

        self.btn_maximizar = QPushButton(self.barra_superior)
        self.btn_maximizar.setObjectName("btn_restaurar")
        self.btn_maximizar.clicked.connect(self.maximizar_restaurar)

        self.btn_cerrar = QPushButton(self.barra_superior)
        self.btn_cerrar.setObjectName("btn_cerrar")
        self.btn_cerrar.clicked.connect(self.close)

        # Estilo y tamaño de los botones
        for btn in (self.btn_minimizar, self.btn_maximizar, self.btn_cerrar):
            btn.setFixedSize(40, 16)
            btn.setAttribute(Qt.WA_Hover, True)
            #btn.setContentsMargins(0, 0, 0, 0)
            #btn.setStyleSheet("background: none; border: none; font-size: 18px; color: white;")

        # Agregar menú y botones a la barra
        layout_barra.addWidget(self.menu_bar)
        layout_barra.addStretch(1)
        layout_barra.addWidget(self.btn_minimizar)
        layout_barra.addWidget(self.btn_maximizar)
        layout_barra.addWidget(self.btn_cerrar)

    def closeEvent(self, event):
        print("Guardando datos o haciendo respaldo...")
        #self.hacer_respaldo()
        event.accept() 

    def hacer_respaldo(self):
        ruta_bd_red = r"\\VARIANDB\Va_Transfer\BaseDatosQA.db"
        carpeta_destino_local = os.path.expanduser("~\\Desktop\\BackupsRadioterapia")

        # Verificar que el archivo de origen exista
        if not os.path.exists(ruta_bd_red):
            QMessageBox.critical(
                self,
                "Error de respaldo",
                f"No se encontró el archivo de origen:\n{ruta_bd_red}\nLa aplicación se cerrará."
            )
            sys.exit(1)

        # Crear carpeta si no existe
        os.makedirs(carpeta_destino_local, exist_ok=True)

        # Crear nombre con fecha si se desea (se dejó fijo)
        nombre_backup = "BaseDatosQA.db"
        destino_backup = os.path.join(carpeta_destino_local, nombre_backup)

        # Copiar
        shutil.copy(ruta_bd_red, destino_backup)
        print(f"Copia realizada en: {destino_backup}")

if __name__ == "__main__":

    app = QApplication(sys.argv)
    #init_db_CambioFuente()
    window = MainWindow("JADIAZ") 
    sys.exit(app.exec_())