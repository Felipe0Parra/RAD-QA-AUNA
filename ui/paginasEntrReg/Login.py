from PyQt5.QtWidgets import QLabel, QPushButton, QLineEdit, QFrame, QMainWindow, QApplication, QDialog, QAction
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon, QCursor
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData
from ui.paginasGuia.dialogs import DialogAdminPermiso, DialogAdminPermiso2
from ui.paginasEntrReg.register_page import RegistrationPage
from ui.paginasEntrReg.recover_page import ForgotPasswordPage
import keyboard

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
import sys

class LoginPage(QMainWindow):
    
    login_successful = pyqtSignal(object)  # user_id como entero
    
    def __init__(self):
        #print("---------------------------------------------------------------------------------------------")
        #print("LoginPage              __init__ called")
        super().__init__()
        self.iniGUI()

    
    def iniGUI(self):
        
        # Rutas
        #print(f'la ruta actual es la siguiente:{ruta_actual}')
        fondo = resource_path('resources/images/FondoColor.png')
        logo = resource_path('resources/images/LogoInstitutoCancerologia.png')
        user = resource_path('resources/icons/user.jpg')
        contra = resource_path('resources/icons/password.jpg')
        icono = resource_path('resources/icons/icono.png')
        
        self.setWindowTitle("Login")
        self.setWindowIcon(QIcon(icono))
        ancho = 800 
        alto = 500
        self.setFixedSize(ancho, alto) # Establece el tamaño fijo de la ventana
        self.setWindowTitle('Inicio sesión RAD-QA') # Agregamos un título a la ventan
        
        #poner fondo
        self.background_label = QLabel(self)
        self.background_label.setPixmap(QPixmap(fondo).scaled(self.size(), Qt.KeepAspectRatioByExpanding))
        self.background_label.setGeometry(0, 0, ancho, alto)
        self.background_label.setStyleSheet("border: none;")        
        # Crear el recuadro para la información
        self.info_frame = QFrame(self)
        self.info_frame.setGeometry(264, 40, 272, 380) 
        self.info_frame.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.8);
            border-radius: 20px;
        """)
        #frame_layout = QVBoxLayout(self.info_frame)
        self.label = QLabel(self)
        self.label.setGeometry(342, 60, 115, 84)
        pixmap = QPixmap(logo)
        scaled_pixmap = pixmap.scaled(115, 84) 
        self.label.setPixmap(scaled_pixmap)
        '''--------------------------------------------------------------
        ----------------------- Label de Mensaje  -----------------------
        --------------------------------------------------------------'''
        self.labelwarnign = QLabel(self)
        self.labelwarnign.setAlignment(Qt.AlignLeft)
        self.labelwarnign.setGeometry(295, 180, 180, 15)
        self.labelwarnign.setStyleSheet("""
            QLabel {
                color: #ff0000;                     /* Texto blanco */
                
            }""")
        '''--------------------------------------------------------------
        ----------------------- Cajita de usuario -----------------------
        --------------------------------------------------------------'''
        self.usuario=QLineEdit(self)
        self.usuario.setPlaceholderText('Usuario')

        icon_action = QAction(QIcon(user), "Icon", self)
        self.usuario.addAction(icon_action, QLineEdit.LeadingPosition)
        self.usuario.setGeometry(288, 207, 225, 41)
        self.usuario.setStyleSheet("""
            QLineEdit {
                color: #0a0a0a;                     /* Texto blanco */
                border-radius: 18px;             /* Bordes redondeados */
                background-color: #f4f4f4;
            }
            
            QLineEdit:focus {
                border: 1px solid #c1df08; /* Borde azul */
            }

            QLineEdit[error="true"] {
                background-color: #ffe6e6; /* Fondo rojo claro si hay error */
                border: 1px solid #ff4d4d; /* Borde rojo */
                color: #ff0000; /* Texto rojo */
            }
            
        """)
        '''--------------------------------------------------------------
        ----------------------- Cajita de contraseña --------------------
        --------------------------------------------------------------'''
        self.contraseña=QLineEdit(self)
        self.contraseña.setPlaceholderText('Contrasena')
        w1=self.contraseña.frameGeometry().width()
        h1=self.contraseña.frameGeometry().height()
        self.contraseña.setGeometry(288, 257, 225, 41)
        #self.contraseña.setMaxLength(10)
        self.contraseña.setEchoMode(QLineEdit.Password) #EchoOnEdit
        self.contraseña.setClearButtonEnabled(True)
        icon_action = QAction(QIcon(contra), "Icon", self)
        self.contraseña.addAction(icon_action, QLineEdit.LeadingPosition)
        self.contraseña.setStyleSheet("""
            QLineEdit {
                color: #0a0a0a;                     /* Texto blanco */
                border-radius: 18px;             /* Bordes redondeados */
                background-color: #f4f4f4;
            }
            
            QLineEdit:focus {
                border: 1px solid #c1df08; /* Borde azul */
            }

            QLineEdit[error="true"] {
                background-color: #ffe6e6; /* Fondo rojo claro si hay error */
                border: 1px solid #ff4d4d; /* Borde rojo */
                color: #ff0000; /* Texto rojo */
            }
            
        """)
        self.contraseña.setObjectName("contraseña_ini")
        
        
        '''--------------------------------------------------------------
        -------------------  Olvidó su contraseña   ---------------------
        -------------------------------------------------------------'''
        self.forgot_label = QLabel('<a href="#">¿Olvidó su contraseña?</a>', self)
        self.forgot_label.setTextFormat(Qt.RichText)  # Para habilitar el HTML
        self.forgot_label.setAlignment(Qt.AlignCenter)
        self.forgot_label.setGeometry(270, 301, 260, 20)
        self.forgot_label.setOpenExternalLinks(False)  # Evita abrir en navegador
        self.forgot_label.setCursor(QCursor(Qt.PointingHandCursor))  # Cambia el cursor a una mano
        self.forgot_label.linkActivated.connect(self.resetLoginFields)
        '''--------------------------------------------------------------
        ------------------------Botón de inicio--------------------------
        --------------------------------------------------------------'''
        self.login_btn = QPushButton('Iniciar sesión', self)
        self.login_btn.setGeometry(288, 331, 225, 41)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #c1df08;  /* Fondo cuando el botón es presionado */
                color: white;               /* Texto blanco */
                border-radius: 18px;        /* Bordes redondeados */
                
            }
            QPushButton:hover {
                background-color:rgb(153, 176, 6);  /* Cambia el fondo cuando el mouse pasa por encima */
            }
            QPushButton:pressed {
                background-color:rgb(95, 109, 3);  /* Fondo cuando el botón es presionado */
            }
        """)
        '''--------------------------------------------------------------
        ----------------------- Botón DE REGISTRO -----------------------
        --------------------------------------------------------------'''
        self.registro = QLabel('<a href="#">Crear usuario </a>', self)
        self.registro.setAlignment(Qt.AlignCenter)
        self.registro.setGeometry(310, 375, 180, 20)
        self.registro.setOpenExternalLinks(False)  # Evita abrir en navegador
        self.registro.setCursor(QCursor(Qt.PointingHandCursor))  # Cambia el cursor a una mano
        self.registro.linkActivated.connect(self.displayAdminDialog)
        
        # ----------- triggers -----------
        
        self.login_btn.clicked.connect(self.authenticateUser)
        self.contraseña.returnPressed.connect(self.authenticateUser)
        
         
    
    def displayAdminDialog(self):
        # Crear y mostrar el diálogo
        
        self.usuario.clear()
        self.contraseña.clear()
        self.labelwarnign.clear()
        dialogo = DialogAdminPermiso()
        respuesta = dialogo.exec_()  # Bloquea la ejecución hasta que el usuario cierre la ventana
        self.openRegistration(respuesta)
    
    def openRegistration(self, respuesta):
        if respuesta == QDialog.Accepted:
            self.window = RegistrationPage()
            self.window.show()            
        else:
            print("El usuario canceló o cerró la ventana")
    
    def resetLoginFields(self):
        self.usuario.clear()
        self.contraseña.clear()
        self.labelwarnign.clear()
        dialogo = DialogAdminPermiso2()
        respuesta = dialogo.exec_()  # Bloquea la ejecución hasta que el usuario cierre la ventana
        self.opencambio(respuesta)
    
    def opencambio(self, respuesta):
        if respuesta == QDialog.Accepted:
            self.window = ForgotPasswordPage()
            self.window.show()            
        else:
            print("El usuario canceló o cerró la ventana")
    
    def authenticateUser(self):
        # A9 (§8.1 H4, PLAN_AUDITORIA_DOS_EJES_21-07): antes se llamaba
        # self.verify() DOS veces -- una en el `if` y otra para asignar
        # user_id --. Cada verify() ejecuta UsuarioData.login(), que audita,
        # así que cada inicio de sesión dejaba DOS filas `login` idénticas al
        # segundo en audit_log (pares 24/25, 26/27, 30/31... en la BD del
        # rebuild 22-07) y validaba la contraseña dos veces.
        user_id = self.verify()
        if user_id:
            #print(f"Usuario autenticado con ID: {user_id}")
            self.login_successful.emit(user_id)
            
           
        else:
            print("Credenciales inválidas")
    
    def verify(self):
        if not self.usuario.text():
            self.labelwarnign.setText('Por favor introducir el usuario')
            self.usuario.setFocus()
            return False
        if not self.contraseña.text():
            self.labelwarnign.setText('Hace falta la contraseña')
            self.contraseña.setFocus()
            return False
        if self.usuario.text() and self.contraseña.text():
            user = Usuario(self.usuario.text(), self.contraseña.text())
            usuData = UsuarioData()
            res = usuData.login(user)
        
            
            if res:
                self.labelwarnign.setText('Ok')
                return res
            else:
                self.labelwarnign.setText('Verifique el usuario y contraseña')
                self.usuario.setFocus()
        return False

