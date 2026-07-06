from PyQt5.QtCore import Qt
from  PyQt5.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, QFrame, QComboBox, QSizePolicy
)
from  PyQt5.QtGui import QPixmap, QIcon
from ui.paginasGuia.dialogs import VentanaFirma
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData
from pathlib import Path
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

import os

class RegistrationPage(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Registro de Usuario")
        self.setMinimumSize(1200, 800)
        self.iniGUI()
        self.imagen_path = None

    def iniGUI(self):   
        ruta_actual = Path.cwd()
        logo = os.path.join(ruta_actual, 'resources', 'images', 'LogoInstitutoCancerologia.png')
        self.setWindowIcon(QIcon(os.path.join(ruta_actual, 'resources', 'icons', 'icono.png')))
        icono = resource_path('resources/images/FondoRegistro.png')
        subir = resource_path('resources/icons/upload.png')
        
        # Widget principal
        widget_central = QWidget(self)  # Crea un widget central
        self.setCentralWidget(widget_central)  # Lo establece como el widget principal
        
        # Cargar la imagen de fondo
        self.pixmap = QPixmap(str(icono))  # Guardar la imagen en self.pixmap
        self.background_label = QLabel(widget_central)
        self.background_label.setPixmap(self.pixmap)
        self.background_label.setScaledContents(True)  
        self.background_label.setGeometry(self.rect()) 
        
        # Layout principal
        layout_root = QHBoxLayout(widget_central)  # Aplica el layout al widget central
        
        # Contenedor elementos visules (no espacio)
        contenedor = QWidget()
        
        # Subtítulo
        subtitulo = QLabel("Bienvenido", contenedor)
        subtitulo.setGeometry(302, 20, 300, 84)
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet("color: #c1df08; font-size: 30px; font-weight: bold;")

        # Logo
        pixmap_logo = QPixmap(logo).scaled(115, 84)
        label = QLabel(contenedor)
        label.setPixmap(pixmap_logo)
        label.setGeometry(142, 30, 115, 84)
        
        # Layout principal
        layout_principal = QVBoxLayout(contenedor)
        layout_principal.setContentsMargins(70, 190, 50, 150)  
        
        # QFrame del formulario
        frame = QFrame()
        #frame.setFixedWidth(500)
        #frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        # frame 2 y 3 espacios en blancoo
        frame2 = QFrame()
        frame3 = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: rgba(190, 214, 0, 110);
                border-radius: 20px
            }
        """)
        frame_layout = QGridLayout(frame)
        frame_layout.setContentsMargins(18, 8, 18, 8)
        frame_layout.setSpacing(20) 
        
        # Campos de entrada
        self.campos = {}
        self.createErrorSignalField(frame_layout, 'user_ln', "Usuario", 0, 0)
        self.createErrorSignalField(frame_layout, 'pass_ln', "Contraseña", 3, 0, True)
        self.createErrorSignalField(frame_layout, 'pass2_ln', "Confirmar Contraseña", 6, 0, True)
        self.createErrorSignalField(frame_layout, 'fullname_ln', "Nombre Completo", 0, 1)
        self.createErrorSignalField(frame_layout, 'id_ln', "ID", 3, 1)
        self.createErrorSignalField(frame_layout, 'role_ln', "Rol", 6, 1)
        
        layout_principal.addWidget(frame, 60)
        #layout_principal.setAlignment(frame, Qt.AlignHCenter)
        # Botón de registro
        self.boton_registrar = QPushButton("Registrar")
        self.boton_registrar.setStyleSheet("""
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
            QPushButton:pressed {
                background-color: rgb(95, 109, 3); 
            }
        """)
        self.boton_registrar.setEnabled(False)
        frame_layout.addWidget(self.boton_registrar , 9, 1, 2, 1 )
        
        # Botón de registro
        self.boton_firma = QPushButton("   Subir firma")
        self.boton_firma.setStyleSheet("""
            QPushButton {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                color: #666666;
                border-radius: 10px;
                border: 1px solid #4e828a;
                font-size: 14px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #dddddd;
            }
            QPushButton:pressed {
                background-color: #c1df08;
            }
        """)
        self.boton_firma.setEnabled(True)
        self.boton_firma.setIcon(QIcon(subir))
        frame_layout.addWidget(self.boton_firma , 9, 0, 2, 1 )
        
        # Botón "Volver"
        back_button = QPushButton("Volver")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #6fb8c3;
                color: white;
                border-radius: 10px;
                font-size: 16px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #63a6b0;
            }
            QPushButton:pressed {
                background-color: #4e828a;
            }
        """)
        back_button.clicked.connect(self.close)
        layout_principal.addWidget(back_button)
        layout_principal.addWidget(frame3, 20)
        
        # Agregar el contenedor al layout principal
        layout_root.addWidget(contenedor, 60)
        layout_root.addWidget(frame2, 40)
        
        # Conectar los campos a la validación
        self.user_ln.textChanged.connect(self.enableVerification)
        self.pass_ln.textChanged.connect(self.enableVerification)
        self.pass2_ln.textChanged.connect(self.enableVerification)
        self.fullname_ln.textChanged.connect(self.enableVerification)
        self.id_ln.textChanged.connect(self.enableVerification)
        self.role_ln.currentTextChanged.connect(self.enableVerification)
        self.boton_firma.clicked.connect(self.abrir_ventana_firma)
        self.boton_registrar.clicked.connect(self.validateRegistration)  # Corrección de 'veriry' a 'verify'

    def enableVerification(self):
        # Verifica que todos los campos tengan información
        campos_llenos = (
        bool(self.user_ln.text().strip()) and
        bool(self.pass_ln.text().strip()) and
        bool(self.pass2_ln.text().strip()) and
        bool(self.fullname_ln.text().strip()) and
        bool(self.id_ln.text().strip()) and
        self.role_ln.currentIndex() and
        self.imagen_path is not None
    )

        # Habilita o deshabilita el botón
        self.boton_registrar.setEnabled(campos_llenos)

    def createErrorSignalField(self, layout, name, placeholder, fila, columna, es_password=False):
        """Agrega un campo de entrada con un placeholder al GridLayout."""
        
        if placeholder == 'Rol':
            setattr(self, name, QComboBox())
            getattr(self, name).addItems(['---- Selecciona tu role', 'Físico Médico', 'Medicos'])
            getattr(self, name).setStyleSheet("""
            QComboBox {
                border-radius: 10px;
                background-color: #f4f4f4;
                padding: 10px;
                font-size: 14px;
            }
        """)
        else:
            setattr(self, name, QLineEdit())
        
            getattr(self, name).setStyleSheet("""
                QLineEdit {
                    color: #0a0a0a;
                    font-family: Arial, sans-serif;
                    border-radius: 18px;
                    background-color: #f4f4f4;
                    padding: 10px;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #c1df08;
                }
                QLineEdit[error="true"] {
                    background-color: #ffe6e6;
                    border: 1px solid #ff4d4d;
                    color: #ff0000;
                }
            """)
            getattr(self, name).setPlaceholderText(placeholder)
            
        if es_password:
            getattr(self, name).setEchoMode(QLineEdit.Password)
            
        nombre = f'error_label{name}'
        setattr(self, nombre, QLabel(""))
        getattr(self, nombre).setStyleSheet("""
            QLabel {
                color: red; 
                font-size: 10px; 
                background: transparent; /* Fondo transparente */
                border: none;            /* Sin borde */
            }
        """)
        getattr(self, nombre).setFixedHeight(8)  # Ajustar la altura del QLabel de error
        getattr(self, nombre).setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        getattr(self, nombre).setVisible(True)  # Ocultar por defecto
        
        layout.addWidget(getattr(self, name), fila, columna, 2, 1)
        layout.addWidget(getattr(self, nombre), fila + 1, columna, 1, 1) 

    def validateRegistration(self):
        if self.verify():
            if self.createUser():
                #self.finished.emit() 
                self.close()
        else:
            print("Credenciales inválidas")

    def verify(self):
        """Verifica si los campos están llenos y aplica validaciones."""
        # Validar contraseña
        error_1= False
        error_2= False
        
        pass1 = self.pass_ln.text()
        pass2 = self.pass2_ln.text()
        
        if not self.id_ln.text().isdigit():
            print('Linea 199: id_ln no es un #')
            self.error_labelid_ln.setText("Solo se permiten números en el ID")
            self.error_labelid_ln.setVisible(True)
            error_1= True
        else:
            self.error_labelid_ln.setVisible(False)
            self.idtext = int(self.id_ln.text())

        if pass1 != pass2:
            self.error_labelpass2_ln.setText("Las contraseñas no coinciden")
            self.error_labelpass2_ln.setVisible(True)
            error_2 = True
        else:
            self.error_labelpass2_ln.setVisible(False)

        error = (error_1 or error_2)
        self.boton_registrar.setEnabled(not error)

        return not error
    
    def createUser(self):
        """Verifica que los datos sean correctos antes de proceder."""
        if not self.boton_registrar.isEnabled():
            return False  # No proceder si hay errores

        usuario = self.user_ln.text()
        contraseña = self.pass_ln.text()
        fullname = self.fullname_ln.text()
        idreal = self.id_ln.text()
        role = self.role_ln.currentText()
        with open(self.imagen_path, 'rb') as file:
            imagen_blob = file.read()
        
        if usuario and contraseña:
            
            
            user = Usuario(username=usuario, password=contraseña, fullname=fullname, active=1, identificacion=idreal, role=role, firma= imagen_blob)
            usuData = UsuarioData()
            res = usuData.add_user(user)

            if res:
                return True
            else:
                self.error_labeluser_ln.setText("Usuario existente")
                self.error_labeluser_ln.setVisible(True)

        return False

    def resizeEvent(self, event):
        """Actualizar el tamaño del QLabel cuando la ventana cambie de tamaño."""
        if self.background_label:
            self.background_label.setGeometry(self.rect())
            scaled_pixmap = self.pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.background_label.setPixmap(scaled_pixmap)
            super().resizeEvent(event)    

    def abrir_ventana_firma(self):
        """Abre la ventana emergente para subir la firma."""
        self.ventana_firma = VentanaFirma(self)
        self.ventana_firma.show()
        
    
    def actualizar_boton(self):
        """Cambia el texto del botón cuando la firma se ha subido."""
        self.boton_firma.setText("Firma subida ✅")