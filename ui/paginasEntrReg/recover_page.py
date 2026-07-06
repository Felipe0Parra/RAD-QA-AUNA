from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QFrame, QMainWindow
from PyQt5.QtGui import QIcon
from data.ManejoDatos.usuariosManager import UsuarioData
from PyQt5.QtGui import QPixmap
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


class ForgotPasswordPage(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Recuperar Contraseña")
        self.setMinimumSize(1200, 800)  # Ajusta el tamaño de la ventana
        self.initUI()

    def initUI(self):
        
        logo = resource_path('resources/icons/icono.png')
        icono = resource_path('resources/images/FondoRegistro.png')
        self.setWindowIcon(QIcon(str(logo)))
        # Crea un widget central
        widget_central = QWidget(self)  
        self.setCentralWidget(widget_central)
        
        # Cargar la imagen de fondo
        self.pixmap = QPixmap(str(icono))  # Guardar la imagen en self.pixmap
        self.background_label = QLabel(widget_central)
        self.background_label.setPixmap(self.pixmap)
        self.background_label.setScaledContents(True)  
        self.background_label.setGeometry(self.rect())  
        
        # Crear el frame contenedor
        frame_contenedor = QFrame(widget_central)
        frame_contenedor.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.8);
                border: 2px solid #c1df08;
                border-radius: 20px;
            }
        """)
        frame_contenedor.setFixedSize(400, 450)

        # Layout principal del frame
        layout = QVBoxLayout(frame_contenedor)
        layout.setContentsMargins(20, 20, 20, 20)  # Margen interno del frame

        # Título
        titulo = QLabel("Recuperar Contraseña", frame_contenedor)
        titulo.setAlignment(Qt.AlignCenter)
        
        titulo.setStyleSheet("""
                QLabel {
                color: #c1df08; 
                font-size: 18px; 
                font-weight: bold;
                background: transparent; /* Fondo transparente */
                border: none;            /* Sin borde */
            }""")
        layout.addWidget(titulo)

        self.labelwarnign = QLabel(frame_contenedor)
        self.labelwarnign.setAlignment(Qt.AlignLeft)
        self.labelwarnign.setStyleSheet("""
                QLabel {
                color: #ff0000; 
                font-size: 10px; 
                background: transparent; /* Fondo transparente */
                border: none;            /* Sin borde */
            }""")
        layout.addWidget(self.labelwarnign)

        # Campos de entrada
        self.user_ln = self.agregar_campo(layout, "Usuario")
        self.id_ln = self.agregar_campo(layout, "ID")
        self.role_ln = QComboBox()
        self.role_ln.addItems(["---- Selecciona tu rol", "Físico Médico", "Médico"])
        self.role_ln.setStyleSheet("""
            QComboBox {
                border-radius: 10px;
                background-color: #f4f4f4;
                padding: 10px;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.role_ln)

        self.new_pass_ln = self.agregar_campo(layout, "Nueva Contraseña", es_password=True)
        self.confirm_pass_ln = self.agregar_campo(layout, "Confirmar Contraseña", es_password=True)

        # Botón de restablecer
        self.boton_reset = QPushButton("Restablecer Contraseña", frame_contenedor)
        self.boton_reset.setEnabled(False)
        self.boton_reset.setStyleSheet("""
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
        self.boton_reset.clicked.connect(self.reset_password)
        layout.addWidget(self.boton_reset)

        # Botón "Volver"
        back_button = QPushButton("Volver", frame_contenedor)
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #6fb8c3;
                color: white;
                border-radius: 10px;
                font-size: 16px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #5da7b1;
            }
        """)
        back_button.clicked.connect(self.close)
        layout.addWidget(back_button)

        # Conectar cambios en los campos a la validación
        self.user_ln.textChanged.connect(self.verificar_campos)
        self.id_ln.textChanged.connect(self.verificar_campos)
        self.role_ln.currentTextChanged.connect(self.verificar_campos)
        self.new_pass_ln.textChanged.connect(self.verificar_campos)
        self.confirm_pass_ln.textChanged.connect(self.verificar_campos)

        # Posicionar el frame al centro de la ventana
        layout_principal = QVBoxLayout(widget_central)
        layout_principal.addWidget(frame_contenedor, alignment=Qt.AlignCenter)

    def agregar_campo(self, layout, placeholder, es_password=False):
        """Crea y devuelve un campo de entrada con estilos."""
        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setStyleSheet("""
            QLineEdit {
                border-radius: 10px;
                background-color: #f4f4f4;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #c1df08;
            }
        """)
        if es_password:
            campo.setEchoMode(QLineEdit.Password)
        layout.addWidget(campo)
        return campo

    def verificar_campos(self):
        """Habilita o deshabilita el botón si los campos están llenos."""
        campos_llenos = (
            bool(self.user_ln.text().strip()) and
            bool(self.id_ln.text().strip()) and
            self.role_ln.currentIndex() > 0 and
            bool(self.new_pass_ln.text().strip()) and
            bool(self.confirm_pass_ln.text().strip())
        )
        self.boton_reset.setEnabled(campos_llenos)

    def reset_password(self):
        """Verifica los datos y actualiza la contraseña en la base de datos."""
        usuario = self.user_ln.text()
        idreal = self.id_ln.text()
        role = self.role_ln.currentText()
        nueva_pass = self.new_pass_ln.text()
        confirm_pass = self.confirm_pass_ln.text()

        if nueva_pass != confirm_pass:
            self.labelwarnign.setText("Las contraseñas no coinciden")
            return

        usuData = UsuarioData()
        user = usuData.get_user(usuario, idreal, role)  # Necesitas agregar este método en `UsuarioData`

        if user:
            if usuData.update_password(usuario, nueva_pass):  # Método para actualizar la contraseña
                print("Contraseña actualizada con éxito")
                self.close()
            else:
                print("Error al actualizar la contraseña")
            
        else:
            self.labelwarnign.setText('Datos incorrectos, usuario no encontrado')
            print("Datos incorrectos, usuario no encontrado")

    def resizeEvent(self, event):
        """Actualizar el tamaño del QLabel cuando la ventana cambie de tamaño."""
        self.background_label.setGeometry(self.rect())
        scaled_pixmap = self.pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.background_label.setPixmap(scaled_pixmap)
        super().resizeEvent(event)