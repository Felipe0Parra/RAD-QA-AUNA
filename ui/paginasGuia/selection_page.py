from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMainWindow
)
from PyQt5.QtCore import Qt, pyqtSignal
from resources.imagenes import RoundImageWidget
from PyQt5.QtGui import QPixmap, QIcon
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise 
import sys

class SelectionPage(QMainWindow):
    Start_QA = pyqtSignal(object)
    def __init__(self, user_id):
        #print("SelectionPage          __init__ called")
        super().__init__()
        self.user_id = user_id
        self.background_label = None  # Inicializar la variable
        self.iniGUI()
    
    def iniGUI(self):
        fondo = resource_path('resources/images/FondoRegistro.png')
        logo = resource_path('resources/icons/icono.png')
        self.setWindowIcon(QIcon(str(logo)))
        self.setWindowTitle("Seleccionar Actividad")
        #self.setGeometry(100, 100, 650, 500)
        self.showMaximized()
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Cargar la imagen de fondo
        self.pixmap = QPixmap(str(fondo))  # Guardar la imagen en self.pixmap
        self.background_label = QLabel(central_widget)
        self.background_label.setPixmap(self.pixmap)
        self.background_label.setScaledContents(True)  
        self.background_label.setGeometry(self.rect()) 
        
        # Crear el frame contenedor
        frame_contenedor = QFrame(central_widget)
        frame_contenedor.setStyleSheet("""
            QFrame {
                background-color: rgba(48, 180, 201, 0.2);
                border: none;
                border-radius: 20px;
            }
        """)
        frame_contenedor.setFixedSize(800, 500)

        # Layout principal del frame
        layout_principal = QHBoxLayout(frame_contenedor)
        layout_principal.setContentsMargins(20, 20, 20, 20)  # Margen interno del frame
        
        # Título
        titulo = QLabel("Seleccione la actividad a realizar")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
                QLabel {
                    color: #c1df08; 
                    font-size: 18px; 
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }
        """)
        
        # Layout para contener los botones e imágenes
        layout_contenido = QVBoxLayout()
        layout_contenido.addWidget(titulo)
        
        # Sección para el botón y la imagen de 'Pruebas'
        layout1 = QVBoxLayout()

        #ruta_imagen1 = resource_path('resources/images/daily_check.png')
        round_imagen = RoundImageWidget(resource_path('resources/images/daily_check.png'), size=230)
        layout1.addWidget(round_imagen, alignment=Qt.AlignCenter)
        
        
        option1_button = QPushButton("Pruebas")
        option1_button.setStyleSheet("""
            QPushButton {
                background-color: #c1df08;
                color: white;
                border-radius: 18px;
                font-size: 16px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: rgb(153, 176, 6);
            }
        """)
        option1_button.clicked.connect(self.selec)

        #layout1.addWidget(imagen1)
        layout1.addWidget(option1_button)

        # Añadir al layout principal del frame
        layout_principal.addLayout(layout1)
        
        # Sección para el botón y la imagen de 'Pacientes'
        layout2 = QVBoxLayout()
        round_imagen2 = RoundImageWidget(resource_path('resources/images/oncologypatients.jpg'), size=230)
        layout2.addWidget(round_imagen2, alignment=Qt.AlignCenter)
        
        option2_button = QPushButton("Pacientes")
        option2_button.setStyleSheet("""
            QPushButton {
                background-color: #c1df08;
                color: white;
                border-radius: 18px;
                font-size: 16px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: rgb(153, 176, 6);
            }
        """)
        option2_button.setEnabled(False)
        
        layout2.addWidget(option2_button)

        # Añadir al layout principal del frame
        layout_principal.addLayout(layout2)

        # Sección para el botón y la imagen de 'Imágenes'
        layout3 = QVBoxLayout()
        round_imagen3 = RoundImageWidget(resource_path('resources/images/medical_imagin.png'), size=230)
        layout3.addWidget(round_imagen3, alignment=Qt.AlignCenter)
        
        option3_button = QPushButton("Imágenes")
        option3_button.setStyleSheet("""
            QPushButton {
                background-color: #c1df08;
                color: white;
                border-radius: 18px;
                font-size: 16px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: rgb(153, 176, 6);
            }
        """)
        option3_button.setEnabled(False)

        layout3.addWidget(option3_button)

        # Añadir al layout principal del frame
        layout_principal.addLayout(layout3)

        # Añadir el frame al layout principal de la ventana
        layout_ventana = QVBoxLayout(central_widget)
        layout_ventana.addWidget(frame_contenedor, alignment=Qt.AlignCenter)

        # Establecer el layout de la ventana
        central_widget.setLayout(layout_ventana)
    
    def resizeEvent(self, event):
        """Actualizar el tamaño del QLabel cuando la ventana cambie de tamaño."""
        if self.background_label:
            self.background_label.setGeometry(self.rect())
            scaled_pixmap = self.pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.background_label.setPixmap(scaled_pixmap)
            super().resizeEvent(event)      

    def selec(self):
        user_id = self.user_id
        #print(f"Usuario autenticado con ID: {user_id}")
        self.Start_QA.emit(user_id)