from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QMessageBox, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox, QDateEdit, QComboBox, QCheckBox, QButtonGroup, QFrame, QScrollArea, QAction, QToolBar, QMenuBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QPixmap, QIcon
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.usuariosManager import UsuarioData
from mcc_PTW_read import mcc_read
"   Creación de nuevas cuentas                                                                                                          "
class DialogAdminPermiso(QDialog):
    def __init__(self):
        #print(f"\n - Entrando a la clase: {self.__class__.__name__}")
        #print("-----------------------------------------------------")
        super().__init__()
        self.setWindowTitle("")
        self.resize(400, 250)        
        self.iniGUI()

    def iniGUI(self):
        #print(f"    Método iniGUI en la clase: {self.__class__.__name__}")
        # Quitar barra de título
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Layout principal
        main_layout = QVBoxLayout(self)

        # Grupo de información
        group_box = QGroupBox("Control de creación de cuenta")
        group_layout = QVBoxLayout(group_box)

        # Etiqueta de título
        title_label = QLabel("¿Deseas crear un usuario nuevo?")
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: rgb(153, 176, 6)")

        # Etiqueta informativa
        subtitle_label = QLabel("Para continuar ingrese la cuenta de administrador y su contraseña.")
        subtitle_label.setWordWrap(True)

        # Línea de usuario
        self.admin_user = QLineEdit(self)
        self.admin_user.setText("admin")
        self.admin_user.setReadOnly(True)

        # Línea de contraseña
        self.admin_password = QLineEdit(self)
        self.admin_password.setPlaceholderText("Contraseña")
        self.admin_password.setEchoMode(QLineEdit.Password)
        
        self.labelwarnign = QLabel(self)
        self.labelwarnign.setStyleSheet("""
            QLabel {
                color: #ff0000;                     /* Texto blanco */
                font-family: Arial, sans-serif;  /* Tipo de fuente */
            }""")

        # Botones de Sí y No
        buttons_layout = QHBoxLayout()
        self.yes_btn = QPushButton("Sí")
        self.yes_btn.clicked.connect(self.open_main_window)
        self.no_btn = QPushButton("No")
        self.no_btn.clicked.connect(self.reject)

        buttons_layout.addWidget(self.yes_btn)
        buttons_layout.addWidget(self.no_btn)

        # Agregar widgets al grupo
        group_layout.addWidget(title_label)
        group_layout.addWidget(subtitle_label)
        group_layout.addWidget(self.admin_user)
        group_layout.addWidget(self.admin_password)
        group_layout.addWidget(self.labelwarnign)

        # Agregar todo al layout principal
        main_layout.addWidget(group_box)
        main_layout.addLayout(buttons_layout)

        # Estilo
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 10px;
            }
            QGroupBox {
                font-size: 12px;
                margin-top: 10px;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 16px;
            }
            QLabel {
                color: #333;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #aaa;
                border-radius: 12px;
            }
            QPushButton {
                padding: 6px 12px;
                background-color: #6fb8c3;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #63a6b0;
            }
            QPushButton:pressed {
                background-color: #4e828a;
            }
        """)

    def open_main_window(self):
        print(f"    Método open_main_window en la clase: {self.__class__.__name__}")
        # Aquí puedes agregar la lógica para abrir otra ventana
        
        if not self.admin_password.text():
            self.labelwarnign.setText('Hace falta la contraseña')
            self.admin_password.setFocus()
        if self.admin_user.text() and self.admin_password.text():
            user = Usuario(self.admin_user.text(), self.admin_password.text())
            usuData = UsuarioData()
            self.res = usuData.login(user)
            if self.res:
                self.labelwarnign.setText('')
                self.accept()
            else:
                self.labelwarnign.setText('Verifique la contraseña por favor')
                self.admin_user.setFocus()

"   Cambio de contraseñas                                                                                                            "
class DialogAdminPermiso2(QDialog):
    def __init__(self):
        #print(f"\n - Entrando a la clase: {self.__class__.__name__}")
        #print("----------------------------------------------------")

        super().__init__()
        self.setWindowTitle("")
        self.resize(400, 250)
        self.iniGUI()

    def iniGUI(self):
        #print(f"    Método iniGUI en la clase: {self.__class__.__name__}")
        # Quitar barra de título
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Layout principal
        main_layout = QVBoxLayout(self)

        # Grupo de información
        group_box = QGroupBox("Control de cuentas")
        group_layout = QVBoxLayout(group_box)

        # Etiqueta de título
        title_label = QLabel("¿Deseas cambiar la contraseña?")
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: rgb(153, 176, 6)")

        # Etiqueta informativa
        subtitle_label = QLabel("Para continuar ingrese la cuenta de administrador y su contraseña.")
        subtitle_label.setWordWrap(True)

        # Línea de usuario
        self.admin_user = QLineEdit(self)
        self.admin_user.setText("admin")
        self.admin_user.setReadOnly(True)

        # Línea de contraseña
        self.admin_password = QLineEdit(self)
        self.admin_password.setPlaceholderText("Contraseña")
        self.admin_password.setEchoMode(QLineEdit.Password)
        
        self.labelwarnign = QLabel(self)
        self.labelwarnign.setStyleSheet("""
            QLabel {
                color: #ff0000;                     /* Texto blanco */
                font-family: Arial, sans-serif;  /* Tipo de fuente */
            }""")

        # Botones de Sí y No
        buttons_layout = QHBoxLayout()
        self.yes_btn = QPushButton("Sí")
        self.yes_btn.clicked.connect(self.open_main_window)
        self.no_btn = QPushButton("No")
        self.no_btn.clicked.connect(self.reject)

        buttons_layout.addWidget(self.yes_btn)
        buttons_layout.addWidget(self.no_btn)

        # Agregar widgets al grupo
        group_layout.addWidget(title_label)
        group_layout.addWidget(subtitle_label)
        group_layout.addWidget(self.admin_user)
        group_layout.addWidget(self.admin_password)
        group_layout.addWidget(self.labelwarnign)

        # Agregar todo al layout principal
        main_layout.addWidget(group_box)
        main_layout.addLayout(buttons_layout)

        # Estilo
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 10px;
            }
            QGroupBox {
                font-size: 12px;
                margin-top: 10px;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            QLabel {
                color: #333;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #aaa;
                border-radius: 4px;
            }
            QPushButton {
                padding: 6px 12px;
                background-color: #6fb8c3;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #63a6b0;
            }
            QPushButton:pressed {
                background-color: #4e828a;
            }
        """)

    def open_main_window(self):
        print(f"    Método open_main_window en la clase: {self.__class__.__name__}")
        # Aquí puedes agregar la lógica para abrir otra ventana
        
        if not self.admin_password.text():
            self.labelwarnign.setText('Hace falta la contraseña')
            self.admin_password.setFocus()
        if self.admin_user.text() and self.admin_password.text():
            user = Usuario(self.admin_user.text(), self.admin_password.text())
            usuData = UsuarioData()
            self.res = usuData.login(user)
            if self.res:
                self.labelwarnign.setText('')
                self.accept()
                
            else:
                self.labelwarnign.setText('Verifique la contraseña por favor')
                self.admin_user.setFocus()
    
"   Permiso de eliminar (eliminar datos de las tabla de base de datos de las pruebas diarias con usario y contraseña)                   "
class DialogAdminPermisoEliminar(QDialog):
    def __init__(self, user):
        #print(f"\n - Entrando a la clase: {self.__class__.__name__}")
        #print("----------------------------------------------------")
        super().__init__()
        self.setWindowTitle("")
        self.user = user
        self.resize(400, 250)        
        self.iniGUI()

    def iniGUI(self):
        #print(f"    Método iniGUI en la clase: {self.__class__.__name__}")
        # Quitar barra de título
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Layout principal
        main_layout = QVBoxLayout(self)

        # Grupo de información
        group_box = QGroupBox("Control de eliminación de datos")
        group_layout = QVBoxLayout(group_box)

        # Etiqueta de título
        title_label = QLabel("¿Deseas eliminar los datos?")
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: rgb(153, 176, 6)")

        # Etiqueta informativa
        subtitle_label = QLabel("Para continuar ingrese la cuenta de administrador y su contraseña.")
        subtitle_label.setWordWrap(True)

        # Línea de usuario
        self.admin_user = QLineEdit(self)
        self.admin_user.setText(self.user._usuario)
        self.admin_user.setReadOnly(True)

        # Línea de contraseña
        self.admin_password = QLineEdit(self)
        self.admin_password.setPlaceholderText("Contraseña")
        self.admin_password.setEchoMode(QLineEdit.Password)
        
        self.labelwarnign = QLabel(self)
        self.labelwarnign.setStyleSheet("""
            QLabel {
                color: #ff0000;                     /* Texto blanco */
                font-family: Arial, sans-serif;  /* Tipo de fuente */
            }""")

        # Botones de Sí y No
        buttons_layout = QHBoxLayout()
        self.yes_btn = QPushButton("Sí")
        self.yes_btn.clicked.connect(self.open_main_window)
        self.no_btn = QPushButton("No")
        self.no_btn.clicked.connect(self.reject)

        buttons_layout.addWidget(self.yes_btn)
        buttons_layout.addWidget(self.no_btn)

        # Agregar widgets al grupo
        group_layout.addWidget(title_label)
        group_layout.addWidget(subtitle_label)
        group_layout.addWidget(self.admin_user)
        group_layout.addWidget(self.admin_password)
        group_layout.addWidget(self.labelwarnign)

        # Agregar todo al layout principal
        main_layout.addWidget(group_box)
        main_layout.addLayout(buttons_layout)

        # Estilo
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 10px;
            }
            QGroupBox {
                font-size: 12px;
                margin-top: 10px;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            QLabel {
                color: #333;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #aaa;
                border-radius: 4px;
            }
            QPushButton {
                padding: 6px 12px;
                background-color: #6fb8c3;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #63a6b0;
            }
            QPushButton:pressed {
                background-color: #4e828a;
            }
        """)

    def open_main_window(self):
        print(f"    Método open_main_window en la clase: {self.__class__.__name__}")
        # Aquí puedes agregar la lógica para abrir otra ventana
        
        if not self.admin_password.text():
            self.labelwarnign.setText('Hace falta la contraseña')
            self.admin_password.setFocus()
        if self.admin_user.text() and self.admin_password.text():
            user = Usuario(self.admin_user.text(), self.admin_password.text())
            usuData = UsuarioData()
            self.res = usuData.login(user)
            if self.res:
                self.labelwarnign.setText('')
                self.accept()
            else:
                self.labelwarnign.setText('Verifique la contraseña por favor')
                self.admin_user.setFocus()

"   Permiso de editar (editar datos de las tabla de base de datos de las pruebas diarias con usario y contraseña)                   "
class DialogAdminPermisoEditar(QDialog):
    def __init__(self, user):
        #print(f"\n - Entrando a la clase: {self.__class__.__name__}")
        #print("----------------------------------------------------")
        super().__init__()
        self.setWindowTitle("")
        self.user = user
        self.resize(400, 250)        
        self.iniGUI()

    def iniGUI(self):
        #print(f"    Método iniGUI en la clase: {self.__class__.__name__}")
        # Quitar barra de título
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Layout principal
        main_layout = QVBoxLayout(self)

        # Grupo de información
        group_box = QGroupBox("Control de edición de datos")
        group_layout = QVBoxLayout(group_box)

        # Etiqueta de título
        title_label = QLabel("¿Deseas editar los datos?")
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: rgb(153, 176, 6)")

        # Etiqueta informativa
        subtitle_label = QLabel("Para continuar ingrese la cuenta de administrador y su contraseña.")
        subtitle_label.setWordWrap(True)

        # Línea de usuario
        self.admin_user = QLineEdit(self)
        self.admin_user.setText(self.user._usuario)
        self.admin_user.setReadOnly(True)

        # Línea de contraseña
        self.admin_password = QLineEdit(self)
        self.admin_password.setPlaceholderText("Contraseña")
        self.admin_password.setEchoMode(QLineEdit.Password)
        
        self.labelwarnign = QLabel(self)
        self.labelwarnign.setStyleSheet("""
            QLabel {
                color: #ff0000;                     /* Texto blanco */
                font-family: Arial, sans-serif;  /* Tipo de fuente */
            }""")

        # Botones de Sí y No
        buttons_layout = QHBoxLayout()
        self.yes_btn = QPushButton("Sí")
        self.yes_btn.clicked.connect(self.open_main_window)
        self.yes_btn.clicked.connect(lambda: print(f"    El usuario presionó Sí ({self.__class__.__name__})"))
        self.no_btn = QPushButton("No")
        self.no_btn.clicked.connect(self.reject)

        buttons_layout.addWidget(self.yes_btn)
        buttons_layout.addWidget(self.no_btn)

        # Agregar widgets al grupo
        group_layout.addWidget(title_label)
        group_layout.addWidget(subtitle_label)
        group_layout.addWidget(self.admin_user)
        group_layout.addWidget(self.admin_password)
        group_layout.addWidget(self.labelwarnign)

        # Agregar todo al layout principal
        main_layout.addWidget(group_box)
        main_layout.addLayout(buttons_layout)

        # Estilo
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 10px;
            }
            QGroupBox {
                font-size: 12px;
                margin-top: 10px;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            QLabel {
                color: #333;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #aaa;
                border-radius: 4px;
            }
            QPushButton {
                padding: 6px 12px;
                background-color: #6fb8c3;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #63a6b0;
            }
            QPushButton:pressed {
                background-color: #4e828a;
            }
        """)

    def open_main_window(self):
        print(f"    Método open_main_window en la clase: {self.__class__.__name__}")
        # Aquí puedes agregar la lógica para abrir otra ventana
        
        if not self.admin_password.text():
            self.labelwarnign.setText('Hace falta la contraseña')
            self.admin_password.setFocus()
        if self.admin_user.text() and self.admin_password.text():
            user = Usuario(self.admin_user.text(), self.admin_password.text())
            usuData = UsuarioData()
            self.res = usuData.login(user)
            if self.res:
                self.labelwarnign.setText('')
                self.accept()
                print(f"self.accept() = {self.accept()}")
            else:
                self.labelwarnign.setText('Verifique la contraseña por favor')
                self.admin_user.setFocus()

"   Subir la firma en la creación de usuarios                                                                                           "
class VentanaFirma(QWidget):
    def __init__(self, parent):
        #print(f"\n - Entrando a la clase: {self.__class__.__name__}")
        #print("----------------------------------------------------")
        super().__init__()
        self.parent = parent
        self.imagen_path = None
        self.initUI()

    def initUI(self):
        #print(f"    Método iniGUI en la clase: {self.__class__.__name__}")
        self.setWindowTitle("Subir Firma")
        self.setGeometry(150, 150, 400, 300)
        
        self.layout = QVBoxLayout()
        
        self.label_imagen = QLabel("Aquí se mostrará la firma", self)
        self.label_imagen.setAlignment(Qt.AlignCenter)
        
        self.btn_seleccionar = QPushButton("Seleccionar Firma")
        self.btn_seleccionar.clicked.connect(self.seleccionar_firma)
        
        self.btn_confirmar = QPushButton("Confirmar y Subir")
        self.btn_confirmar.setEnabled(False)
        self.btn_confirmar.clicked.connect(self.subir_firma)
        
        self.layout.addWidget(self.label_imagen)
        self.layout.addWidget(self.btn_seleccionar)
        self.layout.addWidget(self.btn_confirmar)
        
        self.setLayout(self.layout)

    def seleccionar_firma(self):
        print(f"    Método seleccionar_firma en la clase: {self.__class__.__name__}")

        """Abre el diálogo para seleccionar una imagen y la muestra."""
        archivo, _ = QFileDialog.getOpenFileName(self, "Seleccionar Firma", "", "Imágenes (*.png *.jpg *.jpeg)")

        if archivo:
            self.imagen_path = archivo
            self.parent.imagen_path = archivo
            pixmap = QPixmap(archivo).scaled(250, 150, Qt.KeepAspectRatio)
            self.label_imagen.setPixmap(pixmap)
            self.btn_confirmar.setEnabled(True)

    def subir_firma(self):
        print(f"    Método subir_firma en la clase: {self.__class__.__name__}")
        """Guarda la firma en la base de datos y cierra la ventana."""
        
        QMessageBox.information(self, "Éxito", "La firma se ha guardado correctamente.")
        self.parent.actualizar_boton()
        self.parent.enableVerification()
        self.close()
    
# Clase para generar pop up de seleccion de rango de fechas para la exportación a Excel
class DateRangeDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seleccionar Rango de Fechas")
        self.resize(300, 150)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addWidget(QLabel("Fecha inicio:"))
        layout.addWidget(self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addWidget(QLabel("Fecha fin:"))
        layout.addWidget(self.end_date)
        #set a default date just for testing
        self.start_date.setDate(self.start_date.date().currentDate().addDays(-7))
        self.end_date.setDate(self.end_date.date().currentDate())


        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)





from services.dosis_service import DosisService
from services.equipos_service import EquiposService   # <- BD

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal
import numpy as np
from services.dosis_service import DosisService
from services.equipos_service import EquiposService   # <- BD
from mcc_PTW_read import mcc_read

from models.PDF.reporte_calculadora_dos import generar_reporte_calibracion
import pandas as pd
class DialogCalculadoraDosis(QDialog):
    dosis_asignada = pyqtSignal(str, float)
    
    def crear_bloque(self, titulo, color="#e0e0e0"):
        """Crea un GroupBox estilizado con gradiente"""
        box = QGroupBox(titulo)
        box.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {color};
                border-radius: 20px;
                margin-top: 20px;
                padding-top: 15px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f4f4f4, stop:1 #f4f4f4);
                color: #0a0a0a;
                font-size: 14px;
                font-weight: bold;
                font-family: "Segoe UI";
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 4px 12px;
                color: white;
                background-color: {color};
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
            }}
        """)
        layout = QVBoxLayout(box)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 25, 15, 15)
        return box, layout
    
    def crear_bloque2(self, titulo, color="#e0e0e0"):
        """Crea un GroupBox estilizado con gradiente"""
        box = QGroupBox(titulo)
        box.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {color};
                border-radius: 20px;
                margin-top: 20px;
                padding-top: 15px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f4f4f4, stop:1 #f4f4f4);
                color: #0a0a0a;
                font-size: 14px;
                font-weight: bold;
                font-family: "Segoe UI";
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 4px 12px;
                color: white;
                background-color: {color};
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
            }}
        """)
        layout = QVBoxLayout(box)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 25, 15, 15)
        return box, layout

    def estilo_resultado(self, widget):
        """Estilo para resultados calculados (verde lima)"""
        widget.setStyleSheet("""
            QLineEdit {
                border: 2px solid #338e9e;
                border-radius: 12px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #c1df08
            }
            QLineEdit:focus {
                border: 1px solid #338e9e;
                background: #f4f4f4;
            }
        """)

    def estilo_calculado(self, widget):
        """Estilo para valores calculados intermedios (azul c                                                                   an claro)"""
        widget.setStyleSheet("""
            QLineEdit {
                border: 2px solid #338e9e;
                border-radius: 12px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #c1df08
            }
            QLineEdit:focus {
                border: 1px solid #338e9e;
                background: #f4f4f4;
            }
        """)

    def estilo_entrada(self, widget):
        """Estilo para campos de entrada (blanco con bordes grises)"""
        widget.setStyleSheet("""
            QLineEdit {
                border: 2px solid #338e9e;
                border-radius: 12px;
                background: white;
                padding: 8px;
                font-size: 16px;
                color: #2e5d66;
            }
            QLineEdit:hover {
                border: 2px solid #4a8892;
            }
            QLineEdit:focus {
                border: 2px solid #01b0ca;
                background: #f5f5f5;
            }
        """)

    def estilo_label(self, label, bold=False):
        """Estilo mejorado para labels"""
        weight = "bold" if bold else "normal"
        label.setStyleSheet(f"""
            QLabel {{
                color: #2e5d66;
                font-size: 16px;
                font-weight: {weight};
                padding: 2px;
            }}
        """)

    def estilo_checkbox(self, checkbox):
        """Estilo mejorado para checkboxes"""
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                border: 2px solid #00B2BC; 
                height: 16px;
                width: 16px;
                border-radius: 10px;
            }
            QCheckBox::indicator:checked {
                background: qradialgradient(
                    cx:.5, cy:.5, radius: .7,
                    fx:.5, fy:.5,
                    stop:0 '#749e26;', 
                    stop:0.45 'rgb(116, 158, 38);',
                    stop:0.5 transparent,
                    stop:1 transparent
                );
            }
           
        """)
    def estilo_combobox(self, combo, color = "#eaf4a7"):
        combo.setStyleSheet(""" 
                    QComboBox {
                        background-color: rgb(255, 253, 253);
                        padding: 5px;
                        font-size: 14px;
                        font-family: "Segoe UI";
                        color: #0a0a0a;
                        border: 1px solid #ccc;
                        border-radius: 18px;
                        outline: none; /* Elimina bordes azules de selección */
                    }

                    /* Cambia el color de fondo y texto mientras se está seleccionando */
                    QComboBox:on {
                        font-weight: bold;
                        background-color: #c1df08;
                        color: #ffffff;
                    }

                    /* Estilo del desplegable */
                    QComboBox::drop-down {
                        border-radius: 10px;
                        subcontrol-origin: padding;
                        subcontrol-position: right;
                        width: 20px;
                    }

                """)
    def estilo_boton(self, boton, color="#3a9bbe"):
        """Estilo mejorado para botones"""
        boton.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color}, stop:1 {self.oscurecer_color(color)});
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
                min-height: 35px;
            }}
            QPushButton:hover {{
                background: {self.oscurecer_color(color)};
            }}
            QPushButton:pressed {{
                background: {self.oscurecer_color(color, 0.8)};
                padding-top: 12px;
                padding-bottom: 8px;
            }}
            QPushButton:disabled {{
                background: #bdbdbd;
                color: #757575;
            }}
        """)

    def oscurecer_color(self, hex_color, factor=0.85):
        """Oscurece un color hexadecimal"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb_dark = tuple(int(c * factor) for c in rgb)
        return f"#{rgb_dark[0]:02x}{rgb_dark[1]:02x}{rgb_dark[2]:02x}"

    def __init__(self,energias=None, parent=None):
        super().__init__(parent)
        self.main_window = parent
        print("Dialog llamado desde:", type(self.main_window).__name__)
        self.datos_equipo = None
        self.energias = energias or []
        self.acelerador = type(self.main_window).__name__
     
   
        # Conectar al EventBus
        
        
        
        
        #######################
        # Aqui pongo los aceleradores para guardar en la base de datos y que se identifiquen
        if self.acelerador.endswith("IX"):
            self.acelerador_actual = "IX"
        elif self.acelerador.endswith("Hc"):
            self.acelerador_actual = "Hc"
        elif self.acelerador.endswith("600"):
            self.acelerador_actual = "Seiscientos"
            
        ####################### 
        self.setWindowTitle("Calculadora de Dosis de Referencia")
        self.dosis_calculada = None
        
        # Aplicar estilo general con colores personalizados
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e6f7fb, stop:1 #e6f7fb);
            }
            QComboBox {
                border: 2px solid #5C5C5C;
                border-radius: 6px;
                padding: 6px;
                background: white;
                min-height: 25px;
                color: #2e5d66;
            }
            QComboBox:hover {
                border: 2px solid #4a8892;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNOCAxMUw0IDcgMTIgN3oiIGZpbGw9IiMyZTVkNjYiLz48L3N2Zz4=);
            }
            QScrollArea {
                border: none;
            }
        """)
        
        self.initGUI()
        self.crear_menu()
        self.cargar_modelos_combobox()
        self.construir_botones_asignacion(self.energias)
       

    def initGUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        toolbar = QToolBar("Barra de herramientas")
        main_layout.addWidget(toolbar)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(15)
        container_layout.setContentsMargins(20, 20, 20, 20)
        
        # ========== COLUMNAS PRINCIPALES ==========
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        
        # COLUMNA 1: Configuración
        col1_widget, self.col1 = self.crear_bloque("Configuración", "#5b9ea8")
        
        # COLUMNA 2: Correcciones
        col2_widget, self.col2 = self.crear_bloque("Factores de Corrección", "#5b9ea8")
        
        # COLUMNA 3: Resultados
        col3_widget, self.col3 = self.crear_bloque2("Cálculos y Resultados", "#5b9ea8")
        
        columns_layout.addWidget(col1_widget)
        columns_layout.addWidget(col2_widget)
        columns_layout.addWidget(col3_widget)
        
        container_layout.addLayout(columns_layout)
        
        # ========== CONTENIDO COLUMNA 1 ==========
        self._setup_columna1()
        
        # ========== CONTENIDO COLUMNA 2 ==========
        self._setup_columna2()
        
        # ========== CONTENIDO COLUMNA 3 ==========
        self._setup_columna3()
        
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        self.setMinimumSize(1400, 900)
    def crear_menu(self):
        menubar = QMenuBar(self)

        # Menú principal
        menu_archivo = menubar.addMenu("Archivo")
        menu_analisis = menubar.addMenu("Análisis")
        menu_reporte = menubar.addMenu("Reporte")

        # Acciones
        self.act_importar = QAction("Importar MCC", self)
        self.act_graficar = QAction("Graficar perfiles", self)
        self.act_pdf = QAction("Generar reporte PDF", self)

        # Agregar a menús
        menu_archivo.addAction(self.act_importar)
        self.act_importar.triggered.connect(self.import_mcc)
        self.act_pdf.triggered.connect(self.generar_reporte_fecha_seleccionada)
        
        menu_analisis.addAction(self.act_graficar)
        menu_reporte.addAction(self.act_pdf)
    
    def lista_a_diccionario(self, lista):
        import pywintypes
        
        diccionario = {}
        i = 0
        
        while i < len(lista):
            elemento_actual = lista[i]
            
            # Si hay un siguiente elemento
            if i + 1 < len(lista):
                siguiente = lista[i + 1]
                
                es_valor = (
                    not isinstance(siguiente, str) or
                    isinstance(siguiente, pywintypes.TimeType)
                )
                
                # ✅ Verificar que el actual ES string antes de usarlo como clave
                if isinstance(elemento_actual, str) and es_valor:
                    clave = elemento_actual.strip()
                    diccionario[clave] = siguiente
                    i += 2
                    
                elif isinstance(elemento_actual, str):
                    # String seguido de string → título de sección
                    clave = elemento_actual.strip()
                    diccionario[clave] = None
                    i += 1
                    
                else:
                    # ✅ Es un float/int/bool suelto → saltar
                    i += 1
            else:
                # Último elemento
                if isinstance(elemento_actual, str):
                    diccionario[elemento_actual.strip()] = None
                i += 1  # ✅ saltar floats sueltos al final también
        
        return diccionario
          
    def import_mcc(self):
        
        import win32com.client
        try:
            archivo, _ = QFileDialog.getOpenFileName(self, "Seleccionar xslx", "",  "Archivos Excel ; Todos los archivos (*)")
            if archivo:
                ruta = archivo
        except Exception as e:
            QMessageBox.critical(self, "Archivo no valido", "Seleccione un archivo en formato MCC")
        self.ruta = ruta
        
        
        
     
        
        excel = win32com.client.Dispatch("Excel.Application")
        wb = excel.Workbooks.Open(self.ruta)
        ws = wb.Sheets(4)
        ws2 = wb.Sheets(5)
        ws3 = wb.Sheets(6)
        ws4 = wb.Sheets(7)
    
        hojas = wb.Sheets.Count 
        data = ws.UsedRange.Value
        
        
        
        print("Numero de hojas ", hojas)
        
        df1 = []
        df2 = []
        df3 = []
        df4 = []
        
        """ mapeo """
        for x in range(1,60):
            for y in range(1,230):
                val = ws.Cells(x, y).Value
                if val is not None:
                    
                    df1.append(val)
                    
        
      
                    
        

        
     
                    
                
            
        wb.Close(False)
        excel.Quit()

        dict1 = self.lista_a_diccionario(df1)
        dict2 = self.lista_a_diccionario(df2)
        dict3 = self.lista_a_diccionario(df3)
        dict4 = self.lista_a_diccionario(df4)

        print("\n=== Hoja 4 ===")
        for clave, valor in dict1.items():
            print(f"  {clave!r}: {valor}")

        print("\n=== Hoja 5 ===")
        for clave, valor in dict2.items():
            print(f"  {clave!r}: {valor}")
        self.mapear_excel_a_ui(dict1)
            
    
    def mapear_excel_a_ui(self, datos: dict):
        """
        Mapea los valores del diccionario importado del Excel
        a los campos correspondientes de la interfaz.
        """
        
        mapeo = {
            # Calibración de la cámara
            'Beam quality, Q (TPR20,10):':                  ('tpr2010',           'setText'),
            'Polarizing potential V1:':                     ('tension_v1',        'setText'),
            
            # Condiciones de referencia (calibración)
            'P0:':                                          ('pressure_0',        'setText'),
            'kPa                     T0:':                  ('temp_0',            'setText'),
            '°C              Rel. humidity:':               ('humr_cal',          'setText'),
            
            # Condiciones clínicas (medición)
            'P:':                                           ('pressure',          'setText'),
            'kPa                      T:':                  ('temp',              'setText'),
            
            # Profundidad de referencia
            'Reference depth zref :':                       ('Zref',              'setText'),
            
            # Lecturas del dosímetro
            'Uncorrected dosimeter reading at V1 and user polarity:': ('lDV1_prom',  'setText'),
            'Corresponding accelerator monitor units:':     ('unidades_monitor',  'setText'),
            'Uncorrected dosimeter reading at V1 and user polarity:': ('lect_m1',           'setText'),         
            'M+ =':                                         ('Mplus',             'setText'),
            'M- =':                                         ('Mminus',           'setText'),
            'V             V2 (reduced) =':                 ('tension_v2',         'setText'),
            'M2  =':                                          ('lect_m2',            'setText'),  
            # Factores de corrección
            
            
            # Número de serie cámara
            
        }
        
        for clave, (widget_name, metodo) in mapeo.items():
            valor = datos.get(clave)
            if valor is not None:
                widget = getattr(self, widget_name, None)
                if widget:
                    try:
                        getattr(widget, metodo)(str(valor))
                    except Exception as e:
                        print(f"Error al mapear '{clave}' -> {widget_name}: {e}")
        
    
        
        
        
    
       
        
        
    def _setup_columna1(self):
        """Configura el contenido de la columna 1"""
        # Selección de Equipo
        fecha_box, fecha_layout = self.crear_bloque("Selección de fecha", "#5b9ea8")
        
        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)   # abre calendario
        self.date_edit.setDate(QDate.currentDate())  
        fecha_layout.addWidget(self.date_edit)
        self.date_edit.dateChanged.connect(self.on_fecha_cambiada)
        self.col1.addWidget(fecha_box)
        
        equipo_box, equipo_layout = self.crear_bloque("Selección de Equipo", "#5b9ea8")
        
        lbl_modelo = QLabel("Modelo del equipo")
        #self.estilo_label(lbl_modelo, bold=True)
        equipo_layout.addWidget(lbl_modelo)
        
        self.combo_modelos = QComboBox()
        self.estilo_combobox(self.combo_modelos)
        equipo_layout.addWidget(self.combo_modelos)
        
        lbl_serie = QLabel("Número de serie")
        #self.estilo_label(lbl_serie, bold=True)
        equipo_layout.addWidget(lbl_serie)
        
        self.combo_series = QComboBox()
        self.combo_series.setEnabled(False)
        self.estilo_combobox(self.combo_series)
        equipo_layout.addWidget(self.combo_series)
        
        self.combo_modelos.currentIndexChanged.connect(self.on_modelo_cambiado)
        self.combo_modelos.currentTextChanged.connect(self.actualizar_kCharge)
        self.combo_series.currentIndexChanged.connect(self.on_serie_cambiada)
        
        self.col1.addWidget(equipo_box)
        
        # Tamaño de campo
        field_size_box, field_size_layout = self.crear_bloque("Tamaño de campo", "#5b9ea8")
        self.combo_fieldsize = QComboBox()
        self.combo_fieldsize.addItem("10x10 cm")
        self.combo_fieldsize.addItem("20x10 cm")
        self.combo_fieldsize.addItem("4x4 cm")
        field_size_layout.addWidget(self.combo_fieldsize)
        self.estilo_combobox(self.combo_fieldsize)
        self.col1.addWidget(field_size_box)
        
    
        # Tipo de Radiación
        radiacion_box, radiacion_layout = self.crear_bloque("Tipo de Radiación", "#5b9ea8")
        
        self.fotones = QCheckBox("Fotones")
        self.electrones = QCheckBox("Electrones")
        self.estilo_checkbox(self.fotones)
        self.estilo_checkbox(self.electrones)
        
        self.group_mode = QButtonGroup(self)
        self.group_mode.setExclusive(True)
        self.group_mode.addButton(self.fotones)
        self.group_mode.addButton(self.electrones)
        
        radiacion_layout.addWidget(self.fotones)
        radiacion_layout.addWidget(self.electrones)
        self.col1.addWidget(radiacion_box)
        
        ####################################################
        QualityR50_box, QualityR50_layout = self.crear_bloque("R50",  "#5b9ea8")
        self.QR50_box = QualityR50_box
        
        self.R50 = QLineEdit()
        self.r50Title = QLabel("R50 Medido g/cm^2")
        self.R50.setPlaceholderText("R50 Medido")
        QualityR50_layout.addWidget(self.r50Title)
        QualityR50_layout.addWidget(self.R50)
        
        
        self.QualityR50 = QLineEdit()
        self.QualityR50Title = QLabel("Calidad de haz Q(R50) g/cm^2")
        self.QualityR50.setPlaceholderText("Calidad de haz según R50")
        QualityR50_layout.addWidget(self.QualityR50Title)
        QualityR50_layout.addWidget(self.QualityR50)
        
        
        
        self.zrefR50 = QLineEdit()
        self.zrefR50Title = QLabel("Profundidad de referencia R50 g/cm^2")
        self.zrefR50.setPlaceholderText("Profundidad de referencia")
        
        
        self.boton_ayuda_R50 = QPushButton("?")
        self.boton_ayuda_R50.setToolTip("Presione para ver ayuda sobre los parámetros.") 
        self.setStyleSheet("""
            QToolTip {
                background-color: rgba(177, 241, 251, 0.64);
                color: black;
                border: 1px solid white;
                font-size: 14px;
            }
        """)
        self.boton_ayuda_R50.clicked.connect(self.mostrar_ayuda_parametros_R50)
        
        QualityR50_layout.addWidget(self.zrefR50Title)
        QualityR50_layout.addWidget(self.zrefR50)
        QualityR50_layout.addWidget(self.boton_ayuda_R50)
        
 
        
        
        
        self.QR50_box.setVisible(False)
        self.col1.addWidget(self.QR50_box)
        self.electrones.toggled.connect(lambda c: self.show_r50(c))
        self.R50.textChanged.connect(self.calcular_calidad_r50)
        self.R50.textChanged.connect(self.Kq0_r50)
        self.combo_modelos.currentTextChanged.connect(self.Kq0_r50)
        self.R50.textChanged.connect(self.calcular_profundidad_r50)
        
        
        ####################################################
        
        
        # Tipo de Escaneo
        escaneo_box, escaneo_layout = self.crear_bloque("Tipo de Escaneo", "#5b9ea8")
        
        self.pulse = QCheckBox("Pulse")
        self.pulse_scan = QCheckBox("Pulse-Scanned")
        self.estilo_checkbox(self.pulse)
        self.estilo_checkbox(self.pulse_scan)
        
        group_escaneo = QButtonGroup(self)
        group_escaneo.setExclusive(True)
        group_escaneo.addButton(self.pulse)
        group_escaneo.addButton(self.pulse_scan)
        
        escaneo_layout.addWidget(self.pulse)
        escaneo_layout.addWidget(self.pulse_scan)
        self.col1.addWidget(escaneo_box)
        
        # Geometría (Fotones)
        geometria_box, geometria_layout = self.crear_bloque(" Geometría de Medición", "#5b9ea8")
        self.geometry_box = geometria_box
        
        self.SSD = QCheckBox(" SSD (Source-Surface Distance)")
        #self.SAD = QCheckBox(" SAD (Source-Axis Distance)")
        self.estilo_checkbox(self.SSD)
        #self.estilo_checkbox(self.SAD)
        
        self.group_geometry = QButtonGroup(self)
        self.group_geometry.setExclusive(True)
        self.group_geometry.addButton(self.SSD)
        #self.group_geometry.addButton(self.SAD)
        
        geometria_layout.addWidget(self.SSD)
        #geometria_layout.addWidget(self.SAD)
        
        self.geometry_box.setVisible(False)
        self.fotones.toggled.connect(lambda c: self.geometry_box.setVisible(c))
        self.col1.addWidget(geometria_box)
        
        # Calibración
        calib_box, calib_layout = self.crear_bloque("Datos de Calibración", "#5b9ea8")
        
        lbl_fc = QLabel("Factor de calibración (Gy/nC)")
        #self.estilo_label(lbl_fc, bold=True)
        calib_layout.addWidget(lbl_fc)
        
        self.visualize_calib = QLineEdit()
        self.visualize_calib.setReadOnly(True)
        self.estilo_calculado(self.visualize_calib)
        calib_layout.addWidget(self.visualize_calib)
        lbl_pdd = QLabel("TPR2010")
        calib_layout.addWidget(lbl_pdd)
        self.tpr2010 = QLineEdit()
        #self.estilo_entrada(self.tpr2010)
        calib_layout.addWidget(self.tpr2010)
        
        self.mostrar_ayuda_tpr2010 = QPushButton('?')
        self.mostrar_ayuda_tpr2010.clicked.connect(self.mostrar_ayuda_parametros_tpr2010)
        self.tpr2010.textChanged.connect(self.actualizar_kCharge)
        calib_layout.addWidget(self.mostrar_ayuda_tpr2010)
        
        
        lbl_temp0 = QLabel("Temperatura de calibración (°C)")
        #self.estilo_label(lbl_temp0)
        calib_layout.addWidget(lbl_temp0)
        
        self.temp_0 = QLineEdit()
        self.temp_0.setPlaceholderText("Ej: 20.0")
        self.temp_0.textChanged.connect(self.actualizar_ktp)
        #self.estilo_entrada(self.temp_0)
        calib_layout.addWidget(self.temp_0)
        
        lbl_pres0 = QLabel("Presión de calibración (kPa)")
        #self.estilo_label(lbl_pres0)
        calib_layout.addWidget(lbl_pres0)
        
        self.pressure_0 = QLineEdit()
        self.pressure_0.setPlaceholderText("Ej: 101.325")
        self.pressure_0.textChanged.connect(self.actualizar_ktp)
        #self.estilo_entrada(self.pressure_0)
        calib_layout.addWidget(self.pressure_0)
        
        ###################################################
        lbl_humr = QLabel("Humedad relativa de calibración (%)")
        #self.estilo_label(lbl_humr)
        calib_layout.addWidget(lbl_humr)
        
        self.humr_cal = QLineEdit()
        self.humr_cal.setPlaceholderText("Ej: 40%")
        #self.estilo_entrada(self.humr_cal)
        calib_layout.addWidget(self.humr_cal)
        ###################################################
        
        
        self.boton_ayuda_calibracion = QPushButton("?")
        self.boton_ayuda_calibracion.setToolTip("Presione para ver ayuda sobre los parámetros.") 
        self.setStyleSheet("""
            QToolTip {
                background-color: rgba(177, 241, 251, 0.64);
                color: black;
                border: 1px solid white;
                font-size: 14px;
            }
        """)
        self.boton_ayuda_calibracion.clicked.connect(self.mostrar_ayuda_parametros_calibracion)
        calib_layout.addWidget(self.boton_ayuda_calibracion)
        self.col1.addWidget(calib_box)
        
        ##############################################################################3333
        # Condiciones Clínicas
        clinico_box, clinico_layout = self.crear_bloque("Condiciones en la clínica", "#5b9ea8")
        
        lbl_temp = QLabel("Temperatura actual (°C)")
        #self.estilo_label(lbl_temp)
        clinico_layout.addWidget(lbl_temp)
        
        self.temp = QLineEdit()
        self.temp.setPlaceholderText("Ej: 22.5 °C")
        #self.estilo_entrada(self.temp)
        clinico_layout.addWidget(self.temp)
        
        lbl_pres = QLabel("Presión actual (kPa)")
        #self.estilo_label(lbl_pres)
        clinico_layout.addWidget(lbl_pres)
        
        self.pressure = QLineEdit()
        self.pressure.setPlaceholderText("Ej: 100.5 kPa")
        #self.estilo_entrada(self.pressure)
        clinico_layout.addWidget(self.pressure)
        
        ######################################
        lbl_humedad_r = QLabel("Humedad relativa (%)")
        #self.estilo_label(lbl_humedad_r)
        clinico_layout.addWidget(lbl_humedad_r)
        
        self.humedad_r = QLineEdit()
        self.humedad_r.setPlaceholderText("50%")
        #self.estilo_entrada(self.humedad_r)
        clinico_layout.addWidget(self.humedad_r)        
        ######################################
        
        
        
        self.temp.textChanged.connect(self.actualizar_ktp)
        self.pressure.textChanged.connect(self.actualizar_ktp)
        
    
        self.col1.addWidget(clinico_box)
        
        self.col1.addStretch()

    def _setup_columna2(self):
        """Configura el contenido de la columna 2"""
        # Factor kTP
        ktp_box, ktp_layout = self.crear_bloque("Factor kTP", "#5b9ea8")
                                                                                                                                                                                
        lbl_ktp = QLabel("Factor de corrección por temperatura y presión")
        #self.estilo_label(lbl_ktp, bold=True)
        ktp_layout.addWidget(lbl_ktp)
        
        self.ktp = QLineEdit()
        self.ktp.setReadOnly(True)
        #self.estilo_resultado(self.ktp)
        ktp_layout.addWidget(self.ktp)
        
        self.boton_ayuda_parametros_ktp = QPushButton("?")
        self.boton_ayuda_parametros_ktp.setToolTip("Presione para ver ayuda sobre los parámetros.") 
        self.setStyleSheet("""
            QToolTip {
                background-color: rgba(177, 241, 251, 0.64);
                color: black;
                border: 1px solid white;
                font-size: 14px;
            }
        """)
        self.boton_ayuda_parametros_ktp.clicked.connect(self.mostrar_ayuda_parametros_ktp)
        ktp_layout.addWidget(self.boton_ayuda_parametros_ktp)
        
        self.col2.addWidget(ktp_box)
        
       
        
        
        # Lectura/UM
        lectura_box, lectura_layout = self.crear_bloque("Lectura del Dosímetro", "#5b9ea8")
        lbl_v1 = QLabel("V₁ - Voltaje nominal (V)")
        self.tension_v1 = QLineEdit()
        
        lbl_ld = QLabel("Lectura no corregida (nC)")
        #self.estilo_label(lbl_ld)
        lectura_layout.addWidget(lbl_v1)
        lectura_layout.addWidget(self.tension_v1)
        lectura_layout.addWidget(lbl_ld)
        
        self.lDV1_1 = QLineEdit()
        self.lDV1_1.setPlaceholderText("Q1 (nC)")
        #self.estilo_entrada(self.lDV1_1)
        lectura_layout.addWidget(self.lDV1_1)
        
        self.lDV1_2 = QLineEdit()
        self.lDV1_2.setPlaceholderText("Q2 (nC)")
        #self.estilo_entrada(self.lDV1_2)
        lectura_layout.addWidget(self.lDV1_2)
        
        self.lDV1_3 = QLineEdit()
        self.lDV1_3.setPlaceholderText("Q3 (nC)")
        #self.estilo_entrada(self.lDV1_3)
        lectura_layout.addWidget(self.lDV1_3)
        
        self.lDV1_prom = QLineEdit()
        self.lDV1_prom.setPlaceholderText("Qprom (nC)")
        
        self.estilo_calculado(self.lDV1_prom)
        lectura_layout.addWidget(self.lDV1_prom)
        self.lDV1_3.textChanged.connect(self.lectura_dosimetria_prom)
        self.lDV1_2.textChanged.connect(self.lectura_dosimetria_prom)
        self.lDV1_1.textChanged.connect(self.lectura_dosimetria_prom)
        
            
            
        
        lbl_um = QLabel("Unidades monitor (UM)")
       #self.estilo_label(lbl_um)
        lectura_layout.addWidget(lbl_um)
        
        self.unidades_monitor = QLineEdit()
        self.unidades_monitor.setPlaceholderText("Ej: 100")
        #self.estilo_entrada(self.unidades_monitor)
        lectura_layout.addWidget(self.unidades_monitor)
        
        
        lbl_coc = QLabel("nC/UM")
        #self.estilo_label(lbl_coc, bold=True)
        lectura_layout.addWidget(lbl_coc)
        
        self.cociente = QLineEdit()
        self.cociente.setReadOnly(True)
        self.estilo_calculado(self.cociente)
        lectura_layout.addWidget(self.cociente)
        
        self.lDV1_prom.textChanged.connect(self.actualizar_cociente)
        self.unidades_monitor.textChanged.connect(self.actualizar_cociente)
        ###################
        self.ayuda_dosimetro = QPushButton('?')
        self.ayuda_dosimetro.clicked.connect(self.mostrar_ayuda_parametros_lectDosimetro)
        lectura_layout.addWidget(self.ayuda_dosimetro)
        
        ###################
        self.col2.addWidget(lectura_box)
        
        # Polaridad
        
        tension_box, tension_layout = self.crear_bloque("Voltajes de Polarización", "#5b9ea8")
        
        
        #self.estilo_label(lbl_v1)
        #tension_layout.addWidget(lbl_v1)
        
        
        
        
       
        #self.estilo_entrada(self.tension_v1)
        #tension_layout.addWidget(self.tension_v1)
        
        
        
       
        
        self.ayuda_voltajes = QPushButton('?')
        self.ayuda_voltajes.clicked.connect(self.mostrar_ayuda_parametros_voltaje)
        tension_layout.addWidget(self.ayuda_voltajes)
        
        self.col2.addWidget(tension_box)
        
        
        pol_box, pol_layout = self.crear_bloque("Corrección por Polaridad", "#5b9ea8")
        
        lbl_mp = QLabel("M+ (Lectura positiva)")
        #self.estilo_label(lbl_mp)
        pol_layout.addWidget(lbl_mp)
        
        self.Mplus = QLineEdit()
        self.Mplus.setPlaceholderText("Ej: 15.5")
        self.estilo_calculado(self.Mplus)
        pol_layout.addWidget(self.Mplus)
        
        lbl_mm = QLabel(f"M- (Lectura negativa)")
        lbl_mm = QLabel(f"M- Voltaje netativo")
        self.tension_neg = QLineEdit()
        
        
        
        
        #self.estilo_label(lbl_mm)
        pol_layout.addWidget(lbl_mm)
        pol_layout.addWidget(self.tension_neg)
        
        #######################################################################33
        
        self.Mminus1 = QLineEdit()
        self.Mminus1.setPlaceholderText("M- lectura 1")
        #self.estilo_entrada(self.Mminus1)
        pol_layout.addWidget(self.Mminus1)
        
        self.Mminus2 = QLineEdit()
        self.Mminus2.setPlaceholderText("M- lectura 2")
        #self.estilo_entrada(self.Mminus2)
        pol_layout.addWidget(self.Mminus2)
        
        self.Mminus3 = QLineEdit()
        self.Mminus3.setPlaceholderText("M- lectura 3")
        #self.estilo_entrada(self.Mminus3)
        pol_layout.addWidget(self.Mminus3)
        
        self.Mminus = QLineEdit()
        self.Mminus.setPlaceholderText("M- lectura promedio")
        #self.estilo_entrada(self.Mminus)
        pol_layout.addWidget(self.Mminus)
        
        self.Mminus3.textChanged.connect(self.Mprom)
        self.Mminus2.textChanged.connect(self.Mprom)
        self.Mminus1.textChanged.connect(self.Mprom)
        
        ####################################################################
        
        
        
        lbl_kpol = QLabel("Kpol (Factor de polaridad)")
        self.ayuda_kpol = QPushButton('?')
        self.ayuda_kpol.clicked.connect(self.mostrar_ayuda_parametros_polaridad)
        #self.estilo_label(lbl_kpol, bold=True)
        pol_layout.addWidget(lbl_kpol)
        
        
        self.Kpol = QLineEdit()
        self.Kpol.setReadOnly(True)
        #self.estilo_resultado(self.Kpol)
        pol_layout.addWidget(self.Kpol)
        pol_layout.addWidget(self.ayuda_kpol)
        self.Mplus.textChanged.connect(self.actualizar_kpol)
        self.Mminus.textChanged.connect(self.actualizar_kpol)
        
        self.col2.addWidget(pol_box)
        
        pdd_box, pdd_layout = self.crear_bloque("PDD a profundidad", "#5b9ea8")
        self.pdd20 = QLineEdit()
        self.pdd10 = QLineEdit()
        self.layout_pdd = pdd_box
        self.fotones.toggled.connect(self.mostrarWidget_PDD_Fotones)
        lbl_pdd = QLabel("PDD a 20cm y a 10cm (%)")
        #self.estilo_label(lbl_pdd, bold=True)
        self.pdd20.setPlaceholderText("PDD a 20 cm (%)")
        self.pdd10.setPlaceholderText("PDD a 10 cm (%)")
        #self.estilo_entrada(self.pdd20)
        #self.estilo_entrada(self.pdd10)
        #pdd_layout.addWidget(lbl_pdd)
        #pdd_layout.addWidget(self.pdd20)
        #pdd_layout.addWidget(self.pdd10)
        #self.col2.addWidget(pdd_box)
        #self.layout_pdd.setVisible(False)
        
        #########################################################
        
        
        
        
        
        
        
        
        
        self.col2.addStretch()
        
        

    def _setup_columna3(self):
        """Configura el contenido de la columna 3"""
        # Tensiones
        
        
        # Recombinación
        recomb_box, recomb_layout = self.crear_bloque("Corrección por Recombinación", "#5b9ea8")
        lbl_v2 = QLabel("V₂ - Voltaje reducido (V)")
        #self.estilo_label(lbl_v2)

        
        #self.estilo_label(lbl_v2)
        recomb_layout.addWidget(lbl_v2)
        self.tension_v2 = QLineEdit()
        recomb_layout.addWidget(self.tension_v2)
        
      
        
        
        
        
        
        lbl_m1 = QLabel("M₁ (Lectura a V₁)")
        #self.estilo_label(lbl_m1)
        recomb_layout.addWidget(lbl_m1)
        
        self.tension_v1.textChanged.connect(self.actualizar_v1v2)
        self.tension_v2.textChanged.connect(self.actualizar_v1v2)
        
        self.lect_m1 = QLineEdit()
        self.lect_m1.setPlaceholderText("Ej: 15.8")
        self.estilo_calculado(self.lect_m1)
        recomb_layout.addWidget(self.lect_m1)
        
        lbl_m2 = QLabel(f"M₂ (Lectura a V₂)")
        #self.estilo_label(lbl_m2)
        recomb_layout.addWidget(lbl_m2)
        
        #########################################################################################################
        self.lect_m2_1 = QLineEdit()
        self.lect_m2_1.setPlaceholderText("M2 1")
        #self.estilo_entrada(self.lect_m2_1)
        recomb_layout.addWidget(self.lect_m2_1)
        
        self.lect_m2_2 = QLineEdit()
        self.lect_m2_2.setPlaceholderText("M2 2")
        #self.estilo_entrada(self.lect_m2_2)
        recomb_layout.addWidget(self.lect_m2_2)
        
        self.lect_m2_3 = QLineEdit()
        self.lect_m2_3.setPlaceholderText("M2 3")
        #self.estilo_entrada(self.lect_m2_3)
        recomb_layout.addWidget(self.lect_m2_3)
        
        self.lect_m2 = QLineEdit()
        self.lect_m2.setPlaceholderText("M2 Promedio")
        #self.estilo_entrada(self.lect_m2)
        recomb_layout.addWidget(self.lect_m2)
        self.lect_m2_3.textChanged.connect(self.m2_prom)
        self.lect_m2_2.textChanged.connect(self.m2_prom)
        self.lect_m2_1.textChanged.connect(self.m2_prom)
        #########################################################################################################
        
        lbl_m1m2 = QLabel("M₁/M₂")
        #self.estilo_label(lbl_m1m2, bold=True)
        recomb_layout.addWidget(lbl_m1m2)
        
        self.cociente_lecturas = QLineEdit()
        self.cociente_lecturas.setReadOnly(True)
        self.estilo_calculado(self.cociente_lecturas)
        recomb_layout.addWidget(self.cociente_lecturas)
        lbl_v1v2 = QLabel("V₁/V₂")
        #self.estilo_label(lbl_v1v2, bold=True)
        recomb_layout.addWidget(lbl_v1v2)
        
        self.cociente_tensiones = QLineEdit()
        self.cociente_tensiones.setReadOnly(True)
        self.estilo_calculado(self.cociente_tensiones)
        recomb_layout.addWidget(self.cociente_tensiones)
        self.lect_m1.textChanged.connect(self.actualizar_m1m2)
        self.lect_m2.textChanged.connect(self.actualizar_m1m2)
        
        # Coeficientes
        lbl_coef = QLabel("Coeficientes polinomiales (a₀, a₁, a₂)")
        #self.estilo_label(lbl_coef, bold=True)
        recomb_layout.addWidget(lbl_coef)
        
        coef_layout = QHBoxLayout()
        self.a0 = QLineEdit()
        self.a1 = QLineEdit()
        self.a2 = QLineEdit()
        
        for widget in [self.a0, self.a1, self.a2]:
            widget.setReadOnly(True)
            self.estilo_calculado(widget)
        
        self.a0.setPlaceholderText("a₀")
        self.a1.setPlaceholderText("a₁")
        self.a2.setPlaceholderText("a₂")
        
        coef_layout.addWidget(self.a0)
        coef_layout.addWidget(self.a1)
        coef_layout.addWidget(self.a2)
        recomb_layout.addLayout(coef_layout)
        
        lbl_ks = QLabel("Ks (Factor de recombinación)")
        #self.estilo_label(lbl_ks, bold=True)
        recomb_layout.addWidget(lbl_ks)
        
        self.ks = QLineEdit()
        self.ks.setReadOnly(True)
        #self.estilo_resultado(self.ks)
        recomb_layout.addWidget(self.ks)
        
        self.ayuda_recombinacion = QPushButton('?')
        self.ayuda_recombinacion.clicked.connect(self.mostrar_ayuda_parametros_recombinacion)
        recomb_layout.addWidget(self.ayuda_recombinacion)
        
        self.cociente_lecturas.textChanged.connect(self.coeficientes_ks_pulse)
        self.pulse.toggled.connect(self.coeficientes_ks_pulse)
        self.pulse_scan.toggled.connect(self.coeficientes_ks_pulse)
        self.cociente_tensiones.textChanged.connect(self.coeficientes_ks_pulse)
        self.a2.textChanged.connect(self.ks_polinomial)
        self.cociente_lecturas.textChanged.connect(self.ks_polinomial)
        
        self.col3.addWidget(recomb_box)
        
        # Mq y Resultados Finales
        result_box, result_layout = self.crear_bloque("Resultados Finales", "#5b9ea8")
        
        lbl_mq = QLabel("Mq (Lectura corregida)")
        #self.estilo_label(lbl_mq, bold=True)
        result_layout.addWidget(lbl_mq)
        self.ks.textChanged.connect(self.calcular_mq)
        self.a1.textChanged.connect(self.calcular_mq)
        self.MQvar = QLineEdit()
        self.MQvar.setReadOnly(True)
        #self.estilo_resultado(self.MQvar)
        result_layout.addWidget(self.MQvar)
        
        
        # Profundidades
        lbl_zref = QLabel("Zref - Profundidad de referencia (g/cm²)")
        #self.estilo_label(lbl_zref)
        result_layout.addWidget(lbl_zref)
        
        self.Zref = QLineEdit()
        self.Zref.setPlaceholderText("Ej: 10.0")
        #self.estilo_entrada(self.Zref)
        result_layout.addWidget(self.Zref)
        
        lbl_zmax = QLabel("Zmax - Profundidad de dosis máxima (g/cm²)")
        ##self.estilo_label(lbl_zmax)
        result_layout.addWidget(lbl_zmax)
        
        self.Zmax = QLineEdit()
        self.Zmax.setPlaceholderText("Ej: 1.5")
        #self.estilo_entrada(self.Zmax)
        result_layout.addWidget(self.Zmax)
        
        # Factor Kq
        lbl_kq = QLabel("kQ,Q₀ - Factor de calidad del haz")
        #self.estilo_label(lbl_kq)
        result_layout.addWidget(lbl_kq)
        self.Kq0r50_widget = QLineEdit()
        result_layout.addWidget(self.Kq0r50_widget)
        self.Kq_0 = QLineEdit()
        self.Kq_0.setPlaceholderText("Factor de calidad del haz (fotones),Ej: 0.998")
        self.Kq0r50_widget.setPlaceholderText("Factor de calidad del haz (electrones),Ej: 0.998")
        result_layout.addWidget(self.Kq_0)
        
        
        self.Kq_0.setVisible(False)
        self.Kq0r50_widget.setVisible(False)
        self.Kq0r50_widget.textChanged.connect(self.Dzref_calc)
        self.pdd10.textChanged.connect(self.actualizar_kCharge)
        self.pdd20.textChanged.connect(self.actualizar_kCharge)
        self.tpr2010.textChanged.connect(self.actualizar_kCharge)
        self.combo_modelos.currentTextChanged.connect(self.actualizar_kCharge)
        
        # Dosis en Zref
        lbl_dzref = QLabel("D(Zref) - Dosis en profundidad de referencia (Gy/UM)")
        #self.estilo_label(lbl_dzref, bold=True)
        result_layout.addWidget(lbl_dzref)
        
        self.Dzref = QLineEdit()
        self.Dzref.setReadOnly(True)
        self.Dzref.textChanged.connect(self.calcular_dosis_maxima)
        self.estilo_resultado(self.Dzref)
        result_layout.addWidget(self.Dzref)
        
        self.Kq_0.textChanged.connect(self.Dzref_calc)
        self.MQvar.textChanged.connect(self.Dzref_calc)
        
        # PDD para SSD (Fotones)
        self.pdd_zref = QLabel("PDD(Zref) - Porcentaje de dosis (%) - Campo 10×10 cm")
        #self.estilo_label(self.pdd_zref)
        self.pdd_zref.setVisible(False)
        result_layout.addWidget(self.pdd_zref)
        
        self.pddzref = QLineEdit()
        self.pddzref.setPlaceholderText("Ej: 66.7")
        #self.estilo_entrada(self.pddzref)
        self.pddzref.setVisible(False)
        result_layout.addWidget(self.pddzref)
        
        self.SSD.toggled.connect(self.mostrar_pdd)
        
        # TMR para SAD (Fotones)
        self.tmr_zref = QLabel("TMR(Zref) - Tissue Maximum Ratio - Campo 10×10 cm")
        #self.estilo_label(self.tmr_zref)
        self.tmr_zref.setVisible(False)
        result_layout.addWidget(self.tmr_zref)
        
        self.tmrzref = QLineEdit()
        self.tmrzref.setPlaceholderText("Ej: 0.790")
        #self.estilo_entrada(self.tmrzref)
        self.tmrzref.setVisible(False)
        result_layout.addWidget(self.tmrzref)
        
        #self.SAD.toggled.connect(self.mostrar_tmr)
        
        # PDD para Electrones
        self.pdd_zrefE = QLabel("PDD(Zref) - Porcentaje de dosis (%) - Campo 10×10 cm")
        #self.estilo_label(self.pdd_zrefE)
        self.pdd_zrefE.setVisible(False)
        result_layout.addWidget(self.pdd_zrefE)
        
        self.pddzrefE = QLineEdit()
        self.pddzrefE.setPlaceholderText("Ej: 95.0")
        #self.estilo_entrada(self.pddzrefE)
        self.pddzrefE.setVisible(False)
        result_layout.addWidget(self.pddzrefE)
        
        self.electrones.toggled.connect(self.mostrar_pddE)
        self.pddzrefE.textChanged.connect(self.calcular_dosis_maxima)
        
        # Dosis Máxima (RESULTADO FINAL)
        lbl_dmax = QLabel("D(Zmax) - DOSIS MÁXIMA (Gy/MU)")
        #self.estilo_label(lbl_dmax, bold=True)
   
        result_layout.addWidget(lbl_dmax)
        
        self.dosis_maxima = QLineEdit()
        self.dosis_maxima.setReadOnly(True)
        
        result_layout.addWidget(self.dosis_maxima)
        
        self.electrones.toggled.connect(self.calcular_dosis_maxima)
        self.fotones.toggled.connect(self.calcular_dosis_maxima)
        self.SSD.toggled.connect(self.calcular_dosis_maxima)
        #self.SAD.toggled.connect(self.calcular_dosis_maxima)
        self.tmrzref.textChanged.connect(self.calcular_dosis_maxima)
        self.pddzref.textChanged.connect(self.calcular_dosis_maxima)
        self.Kq0r50_widget.textChanged.connect(self.calcular_dosis_maxima)
        
        self.col3.addWidget(result_box)
        
        # Botones de Asignación
        
        result_layout.addWidget(QLabel("Asignar dosis a energía: "))
        self.frame_asignar = QWidget()
        self.layout_asignar = QHBoxLayout(self.frame_asignar)
        #self.layout_asignar.setContentsMargins(0, 0, 0, 0)
        #self.layout_asignar.setSpacing(1)
        
        result_layout.addWidget(self.frame_asignar)
        #self.col3.addWidget(asign_box)
        
        # Botón Aceptar
        self.btn_ok = QPushButton("✓ Aceptar y Cerrar")
        #self.estilo_boton(self.btn_ok, "#c1df08")
        self.btn_ok.clicked.connect(self.guardar_db)
        self.btn_ok.clicked.connect(self.accept)
        result_layout.addWidget(self.btn_ok)
        


    # =====================================================================
    # MÉTODOS DE SERVICIO Y LÓGICA
    # =====================================================================
    
    def cargar_modelos_combobox(self):
        """Llena el ComboBox de modelos"""
        try:
            modelos = EquiposService.obtener_modelos_unicos()
            
            self.combo_modelos.clear()
            self.combo_modelos.addItem("-- Seleccione un modelo --", None)
            
            for modelo in modelos:
                texto = f"{modelo['equip_type']} - {modelo['model']}"
                self.combo_modelos.addItem(texto, modelo['model'])
                
        except Exception as e:
            print(f"Error cargando modelos: {e}")
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los modelos: {e}")
    
    def on_modelo_cambiado(self, index):
        """Se ejecuta cuando el usuario selecciona un modelo"""
        modelo = self.combo_modelos.currentData()
        
        
        self.combo_series.clear()
        self.combo_series.setEnabled(False)
        self.limpiar_datos_equipo()
        
        if modelo is not None:
            try:
                equipos = EquiposService.obtener_series_por_modelo(modelo)
                
                if equipos:
                    self.combo_series.addItem("-- Seleccione una serie --", None)
                    
                    for equipo in equipos:
                        texto = f"Serie: {equipo['serie']}"
                        self.combo_series.addItem(texto, equipo['id'])
                    
                    self.combo_series.setEnabled(True)
                else:
                    QMessageBox.information(self, "Info", "No hay equipos registrados para este modelo")
                    
            except Exception as e:
                print(f"Error cargando series: {e}")
                QMessageBox.warning(self, "Error", f"No se pudieron cargar las series: {e}")
    
    def on_serie_cambiada(self, index):
        """Se ejecuta cuando el usuario selecciona una serie"""
        equipo_id = self.combo_series.currentData()
        
        if equipo_id is not None:
            self.equipo_id = equipo_id
            self.cargar_datos_equipo()
    def show_r50(self, checked):
        self.QR50_box.setVisible(checked)
        self.Kq0r50_widget.setVisible(checked)
    def seleccionar_equipo_por_id(self, equipo_id):
        """Selecciona un equipo específico en los ComboBox por su ID"""
        try:
            equipo = EquiposService.obtener_por_id(equipo_id)
            if equipo:
                index_modelo = self.combo_modelos.findData(equipo['model'])
                if index_modelo >= 0:
                    self.combo_modelos.setCurrentIndex(index_modelo)
                    
                    index_serie = self.combo_series.findData(equipo_id)
                    if index_serie >= 0:
                        self.combo_series.setCurrentIndex(index_serie)
        except Exception as e:
            print(f"Error seleccionando equipo: {e}")

    def cargar_datos_equipo(self):
        """Carga los datos del equipo seleccionado"""
        if self.equipo_id is None:
            return
            
        try:
            self.datos_equipo = EquiposService.obtener_por_id(self.equipo_id)
            
            if self.datos_equipo:
                self.visualize_calib.setText(str(self.datos_equipo["calibr_fact"]))
                self.temp_0.setText(str(self.datos_equipo["t_cal"]))
                self.pressure_0.setText(str(self.datos_equipo["p_cal"]))
                self.actualizar_ktp()
            else:
                QMessageBox.warning(self, "Error", "No se encontraron datos del equipo")
                
        except Exception as e:
            print(f"Error cargando datos del equipo: {e}")
            QMessageBox.warning(self, "Error", f"Error al cargar datos: {e}")
    
    def limpiar_datos_equipo(self):
        """Limpia los campos de datos de calibración"""
        self.visualize_calib.clear()
        self.temp_0.clear()
        self.pressure_0.clear()
        self.equipo_id = None
        self.datos_equipo = None
    def on_fecha_cambiada(self):
        """
        Executed when the date selector changes.
        Searches the database for data related to that date and maps values to UI fields.
        """
        try:
            # Get selected date in format 'dd/MM/yyyy'
            fecha_seleccionada = self.date_edit.date().toString("dd/MM/yyyy")
            
            # Get current equipment ID if selected
            equipo_id = self.combo_series.currentData() if self.combo_series.currentData() else None
            
            # Search database for data matching this date
            datos = DosisService.buscar_por_fecha(fecha_seleccionada, equipo_id)
            
            if datos:
                # Data found - populate the UI fields
                self.cargar_datos_desde_db(datos)
                print(f"Data loaded for date: {fecha_seleccionada}")
            else:
                # No data found
                print(f"No data found for date: {fecha_seleccionada}")
                
        except Exception as e:
            print(f"Error in date change handler: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Error loading data for selected date: {e}")


    def cargar_datos_desde_db(self, datos: dict):
        """
        Load dosimetry data from database into UI fields
        
        Args:
            datos: Dictionary containing dosimetry data from database
        """
        try:
            if datos.get('Acelerador') == self.acelerador_actual:
                # Block signals temporarily to avoid triggering calculations while loading
                self.blockSignals(True)
                
                # Configuration fields
                
                if datos.get('factor_calibracion'):
                    self.visualize_calib.setText(str(datos['factor_calibracion']))
                if datos.get('Modelo_equipo'):
                    # Buscar el índice del item que tiene este valor en su data
                    index = self.combo_modelos.findData(datos['Modelo_equipo'])
                    if index >= 0:  # Si se encontró
                        self.combo_modelos.setCurrentIndex(index)
                if datos.get('Numero_serie'):
                    # Buscar el índice del item que tiene este valor en su data
                    index = self.combo_series.findData(datos['Numero_serie'])
                    if index >= 0:  # Si se encontró
                        self.combo_series.setCurrentIndex(index)
                if datos.get('Tamano_campo'):
                    index = self.combo_fieldsize.findData(datos['Tamano_campo'])
                    if index > 0:
                        self.combo_fieldsize.setCurrentIndex(index)
                if datos.get('temperatura'):
                    self.temp_0.setText(str(datos['temperatura']))
                
                if datos.get('presion'):
                    self.pressure_0.setText(str(datos['presion']))
                
                if datos.get('temp_clinica'):
                    self.temp.setText(str(datos['temp_clinica']))
                
                if datos.get('presion_clinica'):
                    self.pressure.setText(str(datos['presion_clinica']))
                
                # Radiation type
                if datos.get('Tipo_de_radiacion') == 'Electrones':
                    self.electrones.setChecked(True)
                elif datos.get('Tipo_de_radiacion') == 'Fotones':
                    self.fotones.setChecked(True)
                
                # Scan type
                if datos.get('Tipo_de_escaneo') == 'Pulsed':
                    self.pulse.setChecked(True)
                elif datos.get('Tipo_de_escaneo') == 'Pulse scanned':
                    self.pulse_scan.setChecked(True)
                    
                if datos.get('Tipo_de_medicion') == 'SSD':
                    self.SSD.setChecked(True)
                # elif datos.get('Tipo_de_escaneo') == 'SAD':
                #     self.SAD.setChecked(True)
                
                if datos.get('lectura_Q1'):
                    self.lDV1_1.setText(str(datos['lectura_Q1']))
                if datos.get('lectura_Q2'):
                    self.lDV1_2.setText(str(datos['lectura_Q2']))
                if datos.get('lectura_Q3'):
                    self.lDV1_3.setText(str(datos['lectura_Q3']))
                # Dosimeter readings
                if datos.get('lectura_dosimetro'):
                    self.lDV1_prom.setText(str(datos['lectura_dosimetro']))
                
                if datos.get('unidades_monitor'):
                    self.unidades_monitor.setText(str(datos['unidades_monitor']))
                
                # Polarity correction
                if datos.get('Mplus'):
                    self.Mplus.setText(str(datos['Mplus']))
                
                if datos.get('Lectura_neg_1'):
                    self.Mminus1.setText(str(datos['Lectura_neg_1']))
                if datos.get('Lectura_neg_2'):
                    self.Mminus2.setText(str(datos['Lectura_neg_2']))
                if datos.get('Lectura_neg_3'):
                    self.Mminus3.setText(str(datos['Lectura_neg_3']))
                
                if datos.get('Lectura_neg_prom'):
                    self.Mminus.setText(str(datos['Lectura_neg_prom']))
                
                # Voltage data
                if datos.get('tension_v1'):
                    self.tension_v1.setText(str(datos['tension_v1']))
                
                if datos.get('tension_v2'):
                    self.tension_v2.setText(str(datos['tension_v2']))
                #
                
                # Recombination data
                if datos.get('lectura_m2_1'):
                    self.lect_m2.setText(str(datos['lectura_m2_1']))
                if datos.get('lectura_m2_1'):
                    self.lect_m2.setText(str(datos['lectura_m2_2']))
                if datos.get('lectura_m2_1'):
                    self.lect_m2.setText(str(datos['lectura_m2_3']))
                if datos.get('lectura_m2'):
                    self.lect_m2.setText(str(datos['lectura_m2']))
                
                if datos.get('Mq'):
                    self.MQvar.setText(str(datos['Mq']))
                
                # Results
                if datos.get('Zref'):
                    self.Zref.setText(str(datos['Zref']))
                
                if datos.get('Zmax'):
                    self.Zmax.setText(str(datos['Zmax']))
                
                if datos.get('Kq_0'):
                    self.Kq_0.setText(str(datos['Kq_0']))
                
                # PDD values
                if datos.get('pdd20'):
                    self.pdd20.setText(str(datos['pdd20']))
                
                if datos.get('pdd10'):
                    self.pdd10.setText(str(datos['pdd10']))
                
                if datos.get('pddzref'):
                    self.pddzref.setText(str(datos['pddzref']))
                
                if datos.get('tmrzref'):
                    self.tmrzref.setText(str(datos['tmrzref']))
                
                if datos.get('dosis_maxima'):
                    self.dosis_maxima.setText(str(datos['dosis_maxima']))
                
                
                # Re-enable signals
                self.blockSignals(False)
                
                # Show success message
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(self, "Data Loaded", 
                    f"Previous dosimetry data loaded successfully for {datos.get('Fecha', 'selected date')}")
            else:
                pass
            
        except Exception as e:
            print(f"Error loading data from database: {e}")
            self.blockSignals(False)


    def limpiar_campos_dosimetria(self):
        """
        Clear all dosimetry input fields
        """
        campos = [
            self.temp, self.pressure, self.lDV1_1, self.lDV1_2, self.lDV1_3,
            self.unidades_monitor, self.Mminus1, self.Mminus2, self.Mminus3,
            self.tension_v2, self.lect_m2, self.Zref, self.Zmax, self.Kq_0,
            self.pddzref, self.tmrzref, self.pddzrefE
        ]
        
        for campo in campos:
            if hasattr(campo, 'clear'):
                campo.clear()


    def guardar_db(self):
        """
        Save dosimetry data to database using the separate database service.
        Also generates the calibration report.
        """
        # Collect data from UI fields
        
        datos = {
            "Fecha": self.date_edit.date().toString("dd/MM/yyyy"),
            "Acelerador": self.acelerador_actual,
            "equipo_id": self.equipo_id,
            "Modelo_equipo": self.combo_modelos.currentData(),
            "Numero_serie": self.combo_series.currentData(),
            "factor_calibracion": self.visualize_calib.text(),
            "Tamano_campo": self.combo_fieldsize.currentText(),
            "Tipo_de_radiacion": "Electrones" if self.electrones.isChecked() else "Fotones",
            "Tipo_de_escaneo": "Pulsed" if self.pulse.isChecked() else "Pulse scanned",
            "Tipo_de_medicion": "SSD" if self.SSD.isChecked() else None,
            "temperatura": self.temp_0.text(),
            "presion": self.pressure_0.text(),
            "Humedad_calibracion": self.humr_cal.text(),
            "temp_clinica": self.temp.text(),
            "presion_clinica": self.pressure.text(),
            "Humedad_relativa": self.humedad_r.text(),
            "ktp": self.ktp.text(),
            "lectura_Q1": self.lDV1_1.text(),
            "lectura_Q2": self.lDV1_2.text(),
            "lectura_Q3": self.lDV1_3.text(),
            "lectura_dosimetro": self.lDV1_prom.text(),
            "unidades_monitor": self.unidades_monitor.text(),
            "cociente_ldv1_um": self.cociente.text(),
            "Mplus": self.Mplus.text(),
            "Lectura_neg_1": self.Mminus1.text(),
            "Lectura_neg_2": self.Mminus2.text(),
            "Lectura_neg_3": self.Mminus3.text(),
            "Lectura_neg_prom": self.Mminus.text(),
            "Kpol": self.Kpol.text(),
            "tension_v1": self.tension_v1.text(),
            "tension_v2": self.tension_v2.text(),
            "cociente_tensiones": self.cociente_tensiones.text(),
            "lectura_m1": self.lect_m1.text(),
            "lectura_m2_1": self.lect_m2_1.text(),
            "lectura_m2_2": self.lect_m2_2.text(),
            "lectura_m2_3": self.lect_m2_2.text(),
            "lectura_m2": self.lect_m2.text(),
            "cociente_lecturas": self.cociente_lecturas.text(),
            "a0": self.a0.text(),
            "a1": self.a1.text(),
            "a2": self.a2.text(),
            "ks": self.ks.text(),
            "Mq": self.MQvar.text(),
            "Zref": self.Zref.text(),
            "Zmax": self.Zmax.text(),
            "Kq_0": self.Kq0r50_widget.text() if not self.Kq_0.text() else self.Kq_0.text(),
            "Dzref": self.Dzref.text(),
            "pdd20": self.pdd20.text(),
            "pdd10": self.pdd10.text(),
            "pddzref": self.pddzref.text(),
            "tmrzref": self.tmrzref.text(),
            "dosis_maxima": self.dosis_maxima.text()
        }
            
            # Generate report
        if datos.get('Acelerador')==self.acelerador_actual:    
            generar_reporte_calibracion(
                parent=self,
                datos=datos,
                maquina=self.acelerador_actual,
                user = " ",
                role="Físico Médico",
                umbrales={
                    
                    "dosis_maxima": 2.0
                },
                guardar_como=False
            )
        
        # Save to database using the service
            exito = DosisService.guardar_datos(datos)
        else:
            exito = False
            pass
        
    
        
        if exito:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "Success", "Datos cargados exitosamente")
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Failed to save dosimetry data to database")
            

    def generar_reporte_fecha_seleccionada(self):
        """
        Generate a PDF report for a selected date from the database.
        Shows a dialog to select from available dates.
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QMessageBox, QHBoxLayout
        
        # Create dialog for date selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Generar Reporte de Fecha")
        dialog.setMinimumWidth(400)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout(dialog)
        
        # Title
        title = QLabel("Seleccione una fecha para generar el reporte:")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2e5d66;
                padding: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Get available dates from database
        try:
            # Get equipment ID if selected
            equipo_id = self.combo_series.currentData() if self.combo_series.currentData() else None
            
            # Get available dates
            fechas_disponibles = DosisService.obtener_fechas_disponibles(equipo_id)
            
            if not fechas_disponibles:
                QMessageBox.information(self, "Sin datos", 
                    "No hay fechas disponibles en la base de datos.")
                return
            
            # List widget for dates
            list_widget = QListWidget()
            list_widget.setStyleSheet("""
                QListWidget {
                    border: 2px solid #5b9ea8;
                    border-radius: 8px;
                    padding: 5px;
                    font-size: 13px;
                    background: white;
                }
                QListWidget::item {
                    padding: 8px;
                    border-radius: 4px;
                }
                QListWidget::item:selected {
                    background: #5b9ea8;
                    color: white;
                }
                QListWidget::item:hover {
                    background: #e0f2f7;
                }
            """)
            
            for fecha in fechas_disponibles:
                list_widget.addItem(f"{fecha}")
            
            layout.addWidget(list_widget)
            
            # Info label
            info_label = QLabel("Seleccione una fecha de la lista")
            info_label.setStyleSheet("""
                QLabel {
                    color: #666;
                    font-size: 12px;
                    padding: 5px;
                }
            """)
            layout.addWidget(info_label)
            
            # Buttons
            button_layout = QHBoxLayout()
            
            btn_generar = QPushButton(f"Generar Reporte. Equipo: {self.acelerador_actual}")
            btn_generar.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5b9ea8, stop:1 #4a8892);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: bold;
                    min-height: 35px;
                }
                QPushButton:hover {
                    background: #4a8892;
                }
                QPushButton:pressed {
                    background: #2e5d66;
                }
            """)
            
            btn_cancelar = QPushButton("Cancelar")
            btn_cancelar.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #bdbdbd, stop:1 #9e9e9e);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: bold;
                    min-height: 35px;
                }
                QPushButton:hover {
                    background: #9e9e9e;
                }
            """)
            
            button_layout.addWidget(btn_cancelar)
            button_layout.addWidget(btn_generar)
            layout.addLayout(button_layout)
            
            # Connect buttons
            btn_cancelar.clicked.connect(dialog.reject)
            
            def on_generar():
                selected_items = list_widget.selectedItems()
                if not selected_items:
                    QMessageBox.warning(dialog, "Advertencia", 
                        "Por favor seleccione una fecha de la lista")
                    return
                
                # Get selected date (remove emoji)
                fecha_text = selected_items[0].text()
                
                # Load data from database
                datos = DosisService.buscar_por_fecha(fecha_text, self.acelerador_actual)
                
                if datos:
                    # Generate report
                    self._generar_reporte_desde_datos(datos)
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "Error", 
                        f"No se encontraron datos para la fecha: {fecha_text}")
            
            btn_generar.clicked.connect(on_generar)
            
            # Show dialog
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                f"Error al obtener fechas disponibles: {e}")
            print(f"Error in generar_reporte_fecha_seleccionada: {e}")

    def _generar_reporte_desde_datos(self, datos: dict):
        """
        Generate a PDF report from database data
        
        Args:
            datos: Dictionary with dosimetry data from database
        """
        try:
            # Check if generar_reporte_calibracion exists
            try:
                # Call the existing report generation function
                generar_reporte_calibracion(
                    parent=self,
                    datos=datos,
                    maquina=self.acelerador_actual,  # You might want to get this from the equipment data
                    user= None,   # You might want to get this from somewhere
                    role="Físico Médico",
                    umbrales={
                        "pdd10": 75,
                        "pdd20": 65,
                        "dosis_maxima": 2.0
                    },
                    guardar_como=True  # Allow user to choose where to save
                )
                
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(self, "✓ Éxito", 
                    f"Reporte generado exitosamente para la fecha: {datos.get('Fecha', 'N/A')}")
                    
            except NameError:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", 
                    "La función 'generar_reporte_calibracion' no está disponible.\n"
                    "Asegúrese de que esté importada correctamente.")
                
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", 
                f"Error al generar el reporte: {e}")
            print(f"Error in _generar_reporte_desde_datos: {e}")

    def lectura_dosimetria_prom(self):
        try:
            q1 = float(self.lDV1_1.text())
            q2 = float(self.lDV1_2.text())
            q3 = float(self.lDV1_3.text())
            qprom = np.mean([q1,q2,q3])
            self.lDV1_prom.setText(str(round(qprom,5)))
            self.Mplus.setText(str(round(qprom,5)))
            self.lect_m1.setText(str(round(qprom,5)))
        except Exception as e:
            print(e)
            self.lDV1_prom.clear()
    def mostrar_pdd(self, checked):
        self.pdd_zref.setVisible(checked)
        self.pddzref.setVisible(checked)
    
    def mostrarWidget_PDD_Fotones(self, checked):
        
        self.Kq_0.setVisible(checked)
    
    def mostrar_pddE(self, checked):
        self.pdd_zrefE.setVisible(checked)
        self.pddzrefE.setVisible(checked)
        self.Kq0r50_widget.setVisible(checked)
    
    def mostrar_tmr(self, checked):
        self.tmr_zref.setVisible(checked)
        self.tmrzref.setVisible(checked)
        
    def calcular_calidad_r50(self):
        try:
            r50 = self.R50.text()
            q_r50 = DosisService.r50_quality(float(r50))
            self.QualityR50.setText(str(q_r50))
        except Exception as e:
            print(e)
            self.QualityR50.clear()
            
    def calcular_profundidad_r50(self):
        try:
            r50_z = self.R50.text()
            q_r50 = DosisService.r50_depth(float(r50_z))
            self.zrefR50.setText(str(q_r50))
        except Exception as e:
            print(e)
            self.zrefR50.clear()
        
    
    def calcular_dosis_maxima(self):
        try: 
            if self.electrones.isChecked():
                max_dose = DosisService.dwqzmax_calc(float(self.Dzref.text()), float(self.pddzrefE.text()))
                self.dosis_maxima.setText(str(max_dose))
            elif self.SSD.isChecked():
                max_dose = DosisService.dwqzmax_calc(float(self.Dzref.text()), float(self.pddzref.text()))
                self.dosis_maxima.setText(str(max_dose))
            # elif self.SAD.isChecked():
            #     max_dose = DosisService.dwqzmaxSAD_calc(float(self.Dzref.text()), float(self.tmrzref.text()))
            #     self.dosis_maxima.setText(str(max_dose))
        except Exception as e:
            print(e)
            self.dosis_maxima.clear()
         
    def coeficientes_ks_pulse(self):
        try:
            if self.pulse.isChecked():
                modo = "pulsados"
            elif self.pulse_scan.isChecked():
                modo = "pulsados_y_barridos"
            a0, a1, a2 = DosisService.obtener_coeficientes_ks(modo, float(self.cociente_tensiones.text()))
            self.a0.setText(str(a0))
            self.a1.setText(str(a1))
            self.a2.setText(str(a2))
        except Exception as e:
            print(e)
            self.a0.clear()
            self.a1.clear()
            self.a2.clear()
    
    
    def Kq0_r50(self):
        try:
            r50 = float(self.R50.text())
            print(self.combo_modelos.currentData())
            quality_result = DosisService.interpolar_r50(self.combo_modelos.currentData(), r50)
            self.Kq0r50_widget.setText(str(quality_result))
        except Exception as e:
            print(e)
            self.Kq0r50_widget.clear()
            
    def calcular_mq(self):
        try:
            if self.electrones.isChecked():
                self.MQvar.setText(str(DosisService.calcular_mq_elec(float(self.cociente.text()), 
                    float(self.ktp.text()), float(self.Kpol.text()), float(self.ks.text()))))
            elif self.fotones.isChecked():
                self.MQvar.setText(str(DosisService.calcular_mq_fot(float(self.cociente.text()),
                    float(self.ktp.text()), float(self.Kpol.text()), float(self.ks.text()))))
        except Exception as e:
            print(e)
            self.MQvar.clear()
    
    def Dzref_calc(self):
        try:
            if self.fotones.isChecked():
                self.Dzref.setText(str(DosisService.calcular_dwref(float(self.visualize_calib.text()), 
                    float(self.MQvar.text()), float(self.Kq_0.text()))))
            elif self.electrones.isChecked():
                self.Dzref.setText(str(DosisService.calcular_dwref(float(self.visualize_calib.text()), 
                float(self.MQvar.text()), float(self.Kq0r50_widget.text()))))
        except:
            self.Dzref.clear()
        
    def ks_polinomial(self):
        try:
            a0 = float(self.a0.text())
            a1 = float(self.a1.text())
            a2 = float(self.a2.text())
            self.ks.setText(str(DosisService.Ks_factor(a0, a1, a2, float(self.cociente_lecturas.text()))))
        except:
            self.ks.clear()
        
    def actualizar_ktp(self):
        try:
            ktp = DosisService.factor_tp(float(self.temp.text()), float(self.pressure.text()),
                float(self.temp_0.text()), float(self.pressure_0.text()))
            self.ktp.setText(str(ktp))
        except Exception as e:
            self.ktp.clear()

    def actualizar_cociente(self):
        try:
            self.cociente.setText(str(DosisService.cociente_ldv1_um(
                float(self.lDV1_prom.text()),
                float(self.unidades_monitor.text())
            )))
        except:
            self.cociente.clear()
    
    def Mprom(self):
        try:
            m1 = float(self.Mminus1.text())
            m2 = float(self.Mminus2.text())
            m3 = float(self.Mminus3.text())
            mprom = np.mean([m1,m2,m3])
            self.Mminus.setText(str(round(mprom,6)))
        except Exception as e:
            print(e)
            self.Mminus.clear()
        
    def m2_prom(self):
        try:
            m2_1 = float(self.lect_m2_1.text())
            m2_2 = float(self.lect_m2_2.text())
            m2_3 = float(self.lect_m2_3.text())
            m2_prom = np.mean([m2_1,m2_2,m2_3])
            self.lect_m2.setText(str(round(m2_prom,6)))
        except Exception as e:
            print(e)
            self.lect_m2.clear()
    def actualizar_kpol(self):
        try:
            self.Kpol.setText(str(DosisService.factor_k_polaridad(
                float(self.Mplus.text()),
                float(self.Mminus.text())
            )))
        except:
            self.Kpol.clear()
            
    def actualizar_kCharge(self):
        try:
            # pdd20 = float(self.pdd20.text())
            # pdd10 = float(self.pdd10.text())
            # Q = DosisService.calcular_Q0(pdd20, pdd10)
            print(self.combo_modelos.currentData())
            A, Q0 = DosisService.get_AQ(self.combo_modelos.currentData())
            a, b = DosisService.get_ab(self.combo_modelos.currentData())
            print("Factor A", A)
            print("Q", a)
            print("Q0", b)
            self.Kq_0.setText(str(round(DosisService.interpolar_kq0(self.combo_modelos.currentData(), float(self.tpr2010.text())), 5)))
           
            
            
            
                
            
        except Exception as e:
            print(f"Error en el calculo de kQ0, {e}")
            self.Kq_0.clear()

    def actualizar_v1v2(self):
        try:
            self.cociente_tensiones.setText(str(DosisService.cociente_V1V2(
                float(self.tension_v1.text()),
                float(self.tension_v2.text())
            )))
            print(self.tension_v1.text())
            v1v2=DosisService.cociente_V1V2(float(self.tension_v1.text()),float(self.tension_v2.text()))
            if v1v2 <3:
                QMessageBox.critical(self, "Advertencia", "El cociente entre voltaje nominal y voltaje reducido debe ser mayor a 3")
                
        except:
            self.cociente_tensiones.clear()

    def actualizar_m1m2(self):
        try:
            self.cociente_lecturas.setText(str(DosisService.cociente_M1M2(
                float(self.lect_m1.text()),
                float(self.lect_m2.text())
            )))
        except:
            self.cociente_lecturas.clear()
            
    def construir_botones_asignacion(self, energias):
        """Crea botones dinámicos de asignación con colores distintivos"""
        while self.layout_asignar.count():
            w = self.layout_asignar.takeAt(0).widget()
            if w:
                w.deleteLater()
        
        colores = ["#5b9ea8"]
        
        for i, energia in enumerate(energias):
            btn = QPushButton(f"{energia.upper()}")
            color = colores[i % len(colores)]
            #self.estilo_boton(btn, color)
            btn.clicked.connect(lambda _, e=energia: self.emitir_dosis(e))
            self.layout_asignar.addWidget(btn)
    
    def emitir_dosis(self, energia):
        QApplication.processEvents()  
        try:
            valor = 1 - float(self.dosis_maxima.text())
            self.dosis_asignada.emit(energia, valor)
            QMessageBox.information(self, "✓ Éxito", 
                f"Dosis asignada a {energia.upper()}: {valor:.6f} Gy/MU")
        except ValueError:
            QMessageBox.warning(self, "⚠ Error", "Dosis inválida o no calculada")
    
    def recibir_usuario(self, user_name):
        print(f"Se recibió el valor {user_name}")
        self.user = user_name
        print(self.user)
    
    def mostrar_ayuda_parametros_R50(self):
        texto = (
        "<b>R50:</b> 50% de la dosis máxima. "
        "Tomado de la tabla 9 en <a href='https://www.ptwdosimetry.com/en/support/downloads?downloadfile=1503&type=3451&cHash=390ad915264205500518c46e0bb18874'>Detectors for Ionizing Radiation PTW</a>, "
        "El algoritmo usa interpolación lineal para encontrar la calidad del haz según el R50 <br>"
        "Para profundidad de referencia: 0.6R50-0.1 (g/cm^2)"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: R50")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()
    def mostrar_ayuda_parametros_calibracion(self):
        texto = (
        "Información de calibración. <br>"
        "Los parámetros de calibración se traen desde la base de datos.  <br>"
        "Asegurese de que los datos sean correctos, en caso contrario, modifique los valores."
       
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: Calibración")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()
        
    def mostrar_ayuda_parametros_ktp(self):
        texto = (
        "Factor de temperatura y presión. <br>"
        "Ktp = ((273.2+T)*P_0)/((273.2+T_0)*P).  <br>"
        "Asegurese de que los datos sean correctos, en caso contrario, modifique los valores."
       
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: Factor de temperatura y presión Ktp")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()

    def mostrar_ayuda_parametros_lectDosimetro(self):
        texto = (
        "Lectura del dosímetro. <br>"
        "Haga tres lecturas del dosimetro del equipo y asegurese que sean coherentes. <br>"
        "Inserte las unidades monitor (200 por lo general), el programa hará los calculos correspondientes."
       
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: Lectura dosímetro")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()
        
    def mostrar_ayuda_parametros_polaridad(self):
        texto = (
        "Correcciones por polaridad. <br>"
        "Se lee la dosis a -100V, tres veces, se obtiene promedio. <br>"
        "Asegurese de que las tres medidas sean cercanas para obtener un promedio coherente. <br>"
        "Kpol = (|M+|-|M-|)/2M (M es la lectura positiva, la obtenida inicialmente con el dosímetro)."
       
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: Corrección por polaridad")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()
        
    
        
    def mostrar_ayuda_parametros_voltaje(self):
        texto = (
        "Voltajes de polarización. <br>"
        "Idealmente el voltaje V1 debería ser 300V y el voltaje V2 100V, para obtener un cociente de 3. <br>"
        "En caso contrario, la relación entre voltajes no debe ser menor a 3. <br>"
        
       
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: Voltajes")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()
        
        
        
    def mostrar_ayuda_parametros_recombinacion(self):
        texto = (
        "Parámetros de recombinación. <br>"
        "Los coeficientes a₀,a₁,a₂ se obtienen de la tabla 9 de <a href='https://www-pub.iaea.org/MTCD/Publications/PDF/TRS_398s_Web.pdf'>TRS-398</a> (. <br>"
        "ks = a₀ + a₁(M1/M2) + a₂(M1/M2)^2. <br>"
        
       
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: Recombinación")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()
    
    def mostrar_ayuda_parametros_tpr2010(self):
        texto = (
        "TPR2010. <br>"
        "TPR2010 = 1.2661*PDD20,10 - 0.0595 <a href='https://www-pub.iaea.org/MTCD/Publications/PDF/TRS_398s_Web.pdf'>TRS-398</a> <br>"
        
       
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda de parámetros: TPR2010")
        msg.setText(texto)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: rgba(255, 255, 255, 0.64);
                font-size: 15px;
            }
            QLabel {
                color: rgb(49, 61, 62);
                font-size: 15px;
            }
            QPushButton {
                background-color: #4a8892;
                color: white;
                border-radius: 10px;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #35707a;
            }
        """)
        msg.exec_()
        
        

   
