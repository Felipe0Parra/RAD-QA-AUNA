from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QMessageBox, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox, QDateEdit, QComboBox, QCheckBox, QButtonGroup, QFrame, QScrollArea, QAction, QToolBar, QMenuBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QPixmap, QIcon, QColor
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
from services.trs398_excel import leer_trs398, comparar_trs398
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import ACCION_GUARDAR
from ui.util_fechas import ancho_minimo_fecha  # I5
from data.ManejoDatos import conection as _conection_mod
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

    def __init__(self, energias=None, parent=None, fecha_inicial=None):
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
        else:
            # Padre de tipo no reconocido: sin esto, guardar_db y
            # cargar_datos_desde_db revientan con AttributeError al leer
            # self.acelerador_actual más adelante.
            self.acelerador_actual = self.acelerador

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
        self._poblar_combo_protocolo()
        self.construir_botones_asignacion(self.energias)

        # H3.4 (auditoría 2026-07-14): si el formulario mensual pasa su
        # fecha, la calculadora abre en el día 1 de ese mes en vez de
        # "hoy" (self.date_edit nace con QDate.currentDate() en initGUI).
        # El formulario mensual solo registra mes/año (MM/yyyy) -- fijar el
        # día ACTUAL del mes elegido sería arbitrario/confuso (ej. si hoy es
        # 31 pero el mes elegido no tiene 31 días), así que se usa el día 1.
        if fecha_inicial is not None:
            self.date_edit.setDate(QDate(fecha_inicial.year(), fecha_inicial.month(), 1))
       

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
        menu_reporte = menubar.addMenu("Reporte")

        # Acciones
        self.act_comparar_excel = QAction("Comparar con Excel TRS-398", self)
        self.act_pdf = QAction("Generar reporte PDF", self)

        # Agregar a menús
        # "Importar MCC" (win32com/Excel COM, import_mcc) se retiró del menú
        # 2026-07-09: crasheaba en los 3 casos probados en Windows (F5, ya
        # documentado en el handoff) -- Sheets(4) revienta con cualquier
        # archivo real (el .mcc es texto plano de 1 hoja, no un .xlsx de 7).
        # El método import_mcc queda en el código como referencia muerta;
        # D3 (trs398_excel.py) ya reemplazó su función real para hojas
        # Excel, y D4 hará lo propio para autollenar desde .mcc real.
        # "Análisis > Graficar perfiles" se retiró (G5, auditoría 2026-07-10):
        # el QAction se agregaba al menú pero su .triggered nunca se conectó
        # a nada -- ítem muerto. Se reintroducirá junto con D4, cuando el
        # .mcc autollene perfiles reales para graficar.
        menu_archivo.addAction(self.act_comparar_excel)
        self.act_comparar_excel.triggered.connect(self.comparar_con_excel)
        self.act_pdf.triggered.connect(self.generar_reporte_fecha_seleccionada)

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

    def comparar_con_excel(self):
        """Compara los resultados de la app con una hoja TRS-398 del OIEA.

        Lee el .xls/.xlsx/.xlsm (multiplataforma, vía services.trs398_excel:
        sin Excel ni win32com), recalcula las magnitudes con el mismo motor de
        la calculadora a partir de las entradas crudas del archivo, y muestra
        una tabla app-vs-Excel con estado por tolerancia. No modifica los
        campos de la calculadora: es una herramienta de validación.
        """
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar hoja TRS-398", "",
            "Hojas TRS-398 (*.xls *.xlsx *.xlsm);;Todos los archivos (*)")
        if not ruta:
            return
        try:
            datos = leer_trs398(ruta)
        except Exception as e:
            QMessageBox.critical(
                self, "No se pudo leer el archivo",
                f"No fue posible leer la hoja TRS-398:\n{e}")
            return

        modelo = self.combo_modelos.currentData()
        filas = comparar_trs398(datos, modelo_camara=modelo)
        self._mostrar_dialogo_comparacion(datos, filas, modelo)

    def _mostrar_dialogo_comparacion(self, datos, filas, modelo):
        dlg = QDialog(self)
        dlg.setWindowTitle("Comparación con hoja TRS-398")
        dlg.resize(640, 360)
        layout = QVBoxLayout(dlg)

        encabezado = QLabel(
            f"Archivo: <b>{datos['archivo']}</b><br>"
            f"Cámara para kQ: <b>{modelo or '— (ninguna seleccionada)'}</b>")
        encabezado.setTextFormat(Qt.RichText)
        layout.addWidget(encabezado)

        # H3.1 (auditoría 2026-07-14): la columna "App" recalcula con el
        # motor de la app usando las ENTRADAS DE LA HOJA (_recalcular_con_app,
        # services/trs398_excel.py) -- no los valores tecleados ahora mismo
        # en esta calculadora. Valida el motor de cálculo, no la sesión
        # actual. Desde H3.6 (P0/T0 crudos, sin redondeo) esta columna
        # coincide exacto con lo que mostraría la calculadora si se cargaran
        # las mismas entradas -- ya no hace falta un disclaimer de 4º decimal.
        aclaracion = QLabel(
            "La columna \"App\" recalcula con el motor de la app usando las "
            "entradas de la hoja -- no compara los valores tecleados en su "
            "sesión actual de la calculadora.")
        aclaracion.setWordWrap(True)
        aclaracion.setStyleSheet("color: #555;")
        layout.addWidget(aclaracion)

        # Pineado a "2000" a propósito (igual que trs398_excel._recalcular_con_app,
        # Fase K1): las hojas del físico están en TRS-398 2000, no en Rev.1 -
        # este aviso debe reflejar SIEMPRE esa tabla, sin importar en qué
        # protocolo esté el selector de la calculadora (combo_protocolo).
        #
        # La guarda de "tiene kQ" depende del tipo de haz de LA HOJA leída
        # (datos['tipo_haz'], detectado por trs398_excel -- E5, 2026-07-10):
        # una hoja de electrones se valida contra camara_tiene_kq_electrones
        # (tabla R50), no contra la de fotones (tabla TPR20,10).
        if datos.get("tipo_haz") == "electrones":
            tiene_kq = modelo is not None and DosisService.camara_tiene_kq_electrones(
                modelo, protocolo="2000")
        else:
            tiene_kq = modelo is not None and DosisService.camara_tiene_kq(
                modelo, protocolo="2000")
        if not tiene_kq:
            aviso = QLabel(
                "⚠ Sin una cámara con coeficientes kQ seleccionada, las filas "
                "kQ, D(zref) y D(zmax) no se pueden comparar.")
            aviso.setWordWrap(True)
            aviso.setStyleSheet("color: #a06a00;")
            layout.addWidget(aviso)

        # H3.2 (auditoría 2026-07-14): verificado contra el corpus real que
        # zref trae un valor clínico fijo (1.4) en vez de la fórmula en la
        # gran mayoría de las hojas de 6 MeV (15/73 hojas de electrones del
        # corpus 2024, todas 6 MeV, en casi todos los meses) -- convención
        # de esta institución, no un error de digitación. El comparador NO
        # oculta esa fila (mismo principio que H3.1: mostrar y explicar, no
        # silenciar), pero sin este aviso un "Difiere" en zref podría leerse
        # como un bug de la app.
        if datos.get("tipo_haz") == "electrones":
            nota_zref = QLabel(
                "ℹ En electrones, \"zref\" puede diferir de la fórmula "
                "0.6·Q(R50)−0.1 si la hoja usa un valor clínico fijo en su "
                "lugar (frecuente en 6 MeV) -- una diferencia aquí no es "
                "necesariamente un error.")
            nota_zref.setWordWrap(True)
            nota_zref.setStyleSheet("color: #555;")
            layout.addWidget(nota_zref)

        tabla = QTableWidget(len(filas), 5, dlg)
        tabla.setHorizontalHeaderLabels(
            ["Magnitud", "App (motor, entradas del Excel)", "Excel", "Dif.", "Estado"])
        tabla.verticalHeader().setVisible(False)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)

        verde, rojo, gris = QColor("#d6f5d6"), QColor("#f7d4d4"), QColor("#ececec")
        for i, f in enumerate(filas):
            app_txt = "—" if f["app"] is None else f"{f['app']:.5f}"
            exc_txt = "—" if f["excel"] is None else f"{f['excel']:.5f}"
            if not f["comparable"]:
                dif_txt, estado, color = "—", "No comparable", gris
            else:
                dif_txt = f"{f['diferencia_rel']*100:.3f}%"
                estado = "✓ OK" if f["ok"] else "✗ Difiere"
                color = verde if f["ok"] else rojo
            for col, texto in enumerate(
                    [f["etiqueta"], app_txt, exc_txt, dif_txt, estado]):
                item = QTableWidgetItem(texto)
                item.setBackground(color)
                tabla.setItem(i, col, item)

        tabla.resizeColumnsToContents()
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(tabla)

        n_ok = sum(1 for f in filas if f["ok"])
        n_comp = sum(1 for f in filas if f["comparable"])
        resumen = QLabel(f"Coinciden dentro de tolerancia: <b>{n_ok}/{n_comp}</b> "
                         f"magnitudes comparables (tolerancia 0.1 %).")
        resumen.setTextFormat(Qt.RichText)
        layout.addWidget(resumen)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(dlg.accept)
        layout.addWidget(btn_cerrar)

        dlg.exec_()

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
        # I4: formato SIEMPRE explícito. Sin esto, QDateEdit usa el formato
        # corto del locale del SO (en un Windows en inglés: "M/d/yy" ->
        # "7/1/26", que leído en español parece 7-ene-26). El registro se
        # guarda internamente como dd/MM/yyyy (on_fecha_cambiada/guardar_db)
        # -- lo mostrado ahora coincide con lo guardado en cualquier máquina.
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        # I5: piso calculado de la métrica de fuente real (este widget nunca
        # tuvo mínimo -- el reporte del físico 16-07 incluía la flecha del
        # calendario sobre el texto también aquí, no solo en el formulario).
        self.date_edit.setMinimumWidth(ancho_minimo_fecha(self.date_edit))
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
        # actualizar_kCharge se conecta a combo_modelos en _setup_columna3
        # (junto a tpr2010/pdds); conectarlo también aquí lo disparaba doble.
        self.combo_series.currentIndexChanged.connect(self.on_serie_cambiada)
        
        self.col1.addWidget(equipo_box)

        # Protocolo TRS-398 (Fase K): selecciona qué tabla kQ(TPR20,10) usar
        # para fotones. Se crea VACÍO aquí (señal conectada sin items todavía
        # -> no dispara nada) y se puebla en _poblar_combo_protocolo(), llamado
        # en __init__ DESPUÉS de initGUI(), cuando self.Kq_0 y self.combo_modelos
        # ya existen (mismo patrón que combo_modelos/cargar_modelos_combobox).
        protocolo_box, protocolo_layout = self.crear_bloque("Protocolo TRS-398 (kQ)", "#5b9ea8")
        self.combo_protocolo = QComboBox()
        self.estilo_combobox(self.combo_protocolo)
        protocolo_layout.addWidget(self.combo_protocolo)
        self.combo_protocolo.currentIndexChanged.connect(self.on_protocolo_cambiado)
        self.col1.addWidget(protocolo_box)

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
        # kQ y zref se encadenan desde la CALIDAD R50,w (no desde el R50 crudo):
        # el Cuadro 18/Table 20 indexan kQ por R50,w y zref = 0.6*R50,w - 0.1
        # (verificado contra las 53 hojas de electrones del corpus 2024; con el
        # R50 crudo la profundidad salía ~2% corta). Encadenar desde QualityR50
        # mantiene todo coherente también si el físico corrige la calidad a mano.
        self.QualityR50.textChanged.connect(self.Kq0_r50)
        self.combo_modelos.currentTextChanged.connect(self.Kq0_r50)
        self.QualityR50.textChanged.connect(self.calcular_profundidad_r50)
        
        
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

        # G4 (auditoría 2026-07-10): "Pulse" es el modo que usa el físico casi
        # siempre -- lo pidió marcado por defecto (sigue siendo cambiable).
        self.pulse.setChecked(True)
        
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

        # H1.1 (auditoría 2026-07-14): la dosimetría de referencia de
        # electrones es SIEMPRE SSD=100 cm (TRS-398 Rev.1 Tabla 19), pero el
        # checkbox SSD solo es visible con fotones (geometry_box oculto
        # arriba) -- el físico no podía marcarlo y "Tipo_de_medicion"
        # (siempre-requerido, ver _CAMPOS_SIEMPRE_REQUERIDOS) quedaba en
        # None, bloqueando el guardado para todo registro de electrones. Se
        # marca por código sin mostrar el box. QButtonGroup exclusivo no
        # permite desmarcar luego por código, pero no hace falta: volver a
        # fotones también usa SSD como caso normal.
        self.electrones.toggled.connect(lambda c: self.SSD.setChecked(True) if c else None)
        # I6 (pedido del físico 16-07): fotones también nace con SSD marcado
        # -- es la geometría de rutina en esta clínica -- pero SIN ocultar el
        # box (geometry_box se muestra con fotones, línea de arriba): el
        # físico lo ve marcado y puede constatarlo. A diferencia de
        # electrones (SSD obligatorio por Rev.1 Tabla 19), aquí es un default
        # de conveniencia. Con I2, marcar SSD+fotones muestra automáticamente
        # el campo PDD de fotones que la dosis máxima SSD necesita.
        self.fotones.toggled.connect(lambda c: self.SSD.setChecked(True) if c else None)
        
        # Calibración
        calib_box, calib_layout = self.crear_bloque("Datos de Calibración", "#5b9ea8")
        
        lbl_fc = QLabel("Factor de calibración (Gy/nC)")
        #self.estilo_label(lbl_fc, bold=True)
        calib_layout.addWidget(lbl_fc)
        
        self.visualize_calib = QLineEdit()
        self.visualize_calib.setReadOnly(True)
        self.estilo_calculado(self.visualize_calib)
        calib_layout.addWidget(self.visualize_calib)
        self.lbl_tpr2010 = QLabel("TPR2010")
        calib_layout.addWidget(self.lbl_tpr2010)
        self.tpr2010 = QLineEdit()
        #self.estilo_entrada(self.tpr2010)
        calib_layout.addWidget(self.tpr2010)

        self.mostrar_ayuda_tpr2010 = QPushButton('?')
        self.mostrar_ayuda_tpr2010.clicked.connect(self.mostrar_ayuda_parametros_tpr2010)
        self.tpr2010.textChanged.connect(self.actualizar_kCharge)
        calib_layout.addWidget(self.mostrar_ayuda_tpr2010)

        # G2 (auditoría 2026-07-10): TPR20,10 no aplica a electrones -- su kQ
        # sale de R50, no de TPR. Oculto por defecto (como QR50_box/geometry_box
        # arriba) hasta que se marque "Fotones"; ver _mostrar_tpr2010.
        self.lbl_tpr2010.setVisible(False)
        self.tpr2010.setVisible(False)
        self.mostrar_ayuda_tpr2010.setVisible(False)
        self.fotones.toggled.connect(self._mostrar_tpr2010)
        
        
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
        lbl_mm = QLabel(f"M- Voltaje negativo")
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
        # I3: promovido a self.* -- en electrones este campo se oculta (la
        # profundidad de referencia es la MISMA cantidad que zrefR50, ya
        # calculada de 0.6*R50,w - 0.1) y se necesita alternar su visibilidad.
        self.lbl_zref = QLabel("Zref - Profundidad de referencia (g/cm²)")
        #self.estilo_label(lbl_zref)
        result_layout.addWidget(self.lbl_zref)
        
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
        # I2: etiqueta diferenciada de la de electrones -- eran idénticas y
        # cuando ambos campos quedaban visibles a la vez (efecto lateral del
        # auto-SSD de H1.1) se veían como un campo duplicado.
        self.pdd_zref = QLabel("PDD(Zref) FOTONES - Porcentaje de dosis (%) - Campo 10×10 cm")
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
        self.pdd_zrefE = QLabel("PDD(Zref) ELECTRONES - Porcentaje de dosis (%) - Campo 10×10 cm")
        #self.estilo_label(self.pdd_zrefE)
        self.pdd_zrefE.setVisible(False)
        result_layout.addWidget(self.pdd_zrefE)
        
        self.pddzrefE = QLineEdit()
        self.pddzrefE.setPlaceholderText("Ej: 95.0")
        #self.estilo_entrada(self.pddzrefE)
        self.pddzrefE.setVisible(False)
        result_layout.addWidget(self.pddzrefE)
        
        self.electrones.toggled.connect(self.mostrar_pddE)
        # I2: fotones también recalcula la visibilidad -- al volver de
        # electrones a fotones, SSD sigue marcado (H1.1 no lo desmarca) y el
        # PDD de fotones debe reaparecer sin esperar otro clic en SSD.
        self.fotones.toggled.connect(self.mostrar_pdd)
        # I3: el Zref manual de Resultados se oculta/autollena en electrones.
        self.electrones.toggled.connect(self._actualizar_visibilidad_zref)
        self.fotones.toggled.connect(self._actualizar_visibilidad_zref)
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
        # F3 (auditoría 2026-07-10): decisión explícita del usuario -- este
        # botón y los de energía (ver construir_botones_asignacion) se dejan
        # SEPARADOS a propósito; el tooltip evita que se confundan.
        self.btn_ok.setToolTip(
            "Guarda este cálculo en el registro de la calculadora.\n"
            "NO asigna la dosis al formulario mensual -- para eso, use el "
            "botón de la energía correspondiente (p. ej. \"6 MV\").")
        # G1 (auditoría 2026-07-10): una sola conexión -- ver on_aceptar_y_cerrar.
        self.btn_ok.clicked.connect(self.on_aceptar_y_cerrar)
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

    def _poblar_combo_protocolo(self):
        """Puebla el selector de protocolo TRS-398 (Fase K). Se llama DESPUÉS
        de initGUI() para que el primer addItem (que dispara
        currentIndexChanged en cualquier QComboBox recién poblado) encuentre
        self.Kq_0 y self.combo_modelos ya creados. Default: "2000" (TRS-398
        original, validado en D3 contra hoja real del físico). Etiqueta
        "2000/2005": el protocolo original es de 2000 (inglés); la
        traducción oficial española que circula en la institución (el PDF
        que usa el físico) está fechada 2005 -- mismo protocolo, dos años
        de portada distintos, para evitar la confusión reportada
        2026-07-09 ("el PDF... dice 2005 no 2000")."""
        self.combo_protocolo.addItem("TRS-398 (2000/2005)", "2000")
        self.combo_protocolo.addItem("TRS-398 Rev.1 (2024)", "rev1")

    def _refrescar_guardia_kq(self, modelo):
        """Aviso/placeholder de kQ según si `modelo` tiene coeficientes en el
        protocolo TRS-398 actualmente seleccionado. Compartida por
        on_modelo_cambiado y on_protocolo_cambiado (Fase K4).

        ⚠️ NUNCA llamar a on_modelo_cambiado desde el handler del selector de
        protocolo: repoblaría combo_series y dispararía on_serie_cambiada ->
        cargar_datos_equipo, que pisa el factor de calibración vigente del
        catálogo sobre el histórico (bug corregido en D2.2).
        """
        protocolo = self.combo_protocolo.currentData() if hasattr(self, "combo_protocolo") else "2000"
        etiqueta_protocolo = self.combo_protocolo.currentText() if hasattr(self, "combo_protocolo") else "TRS-398 (2000/2005)"
        if not DosisService.camara_tiene_kq(modelo, protocolo):
            # Guarda D2 (extendida en K4 con el protocolo activo): sin fila en
            # la tabla del protocolo elegido no hay kQ automático. Al completar
            # esa tabla para este modelo, el aviso desaparece solo.
            self.Kq_0.setPlaceholderText("Sin coeficientes kQ para este modelo — ingrese el valor manualmente")
            # El campo Kq_0 solo es visible tras marcar "Fotones" (mostrarWidget_PDD_Fotones).
            # Si el usuario todavía no lo marcó, el mensaje genérico "ingréselo en el campo
            # correspondiente" describe un campo que no puede ver (bug reportado 2026-07-09:
            # "sale el mensaje... pero no hay ninguna casilla habilitada") -> instrucción explícita.
            # isHidden() (no isVisible()) a propósito: isVisible() exige que TODA la cadena de
            # ancestros esté mapeada en pantalla (falso en diálogos aún no mostrados con .show()),
            # mientras que isHidden() refleja el flag explícito de setVisible() sin esa dependencia.
            if not self.Kq_0.isHidden():
                instruccion = ("Puede ingresar el valor de kQ,Q0 manualmente en el campo "
                                "correspondiente; el resto del cálculo funciona normal.")
            else:
                instruccion = ('Marque "Fotones" en "Tipo de Radiación" para habilitar el '
                                "campo kQ,Q0 e ingresarlo manualmente; el resto del cálculo "
                                "funciona normal.")
            QMessageBox.information(
                self, "Modelo sin coeficientes kQ",
                f"El modelo {modelo} aún no tiene cargados los coeficientes "
                f"kQ(TPR20,10) en {etiqueta_protocolo}, por lo que el cálculo "
                "automático de kQ,Q0 no está disponible por ahora.\n\n"
                f"{instruccion}")
        else:
            self.Kq_0.setPlaceholderText("Factor de calidad del haz (fotones),Ej: 0.998")

    def on_protocolo_cambiado(self, index):
        """Cambiar el protocolo TRS-398 re-evalúa la guarda de kQ para el
        modelo actual y, si hay fotones activos y TPR ya tecleado, recalcula
        kQ con la tabla del protocolo recién elegido. Ver _refrescar_guardia_kq
        sobre por qué esto NO reusa on_modelo_cambiado."""
        modelo = self.combo_modelos.currentData()
        if modelo is not None:
            self._refrescar_guardia_kq(modelo)
        if self.fotones.isChecked():
            self.actualizar_kCharge()
        # El kQ de electrones también depende del protocolo (Cuadro 18 vs
        # Table 20 — auditoría 2026-07-09). Kq0_r50 trae sus propias guardas
        # (modelo con datos, R50,w tecleado), así que se refresca siempre.
        self.Kq0_r50()

    def on_modelo_cambiado(self, index):
        """Se ejecuta cuando el usuario selecciona un modelo"""
        modelo = self.combo_modelos.currentData()


        self.combo_series.clear()
        self.combo_series.setEnabled(False)
        self.limpiar_datos_equipo()

        if modelo is not None:
            self._refrescar_guardia_kq(modelo)
            try:
                equipos = EquiposService.obtener_series_por_modelo(modelo)
                
                if equipos:
                    self.combo_series.addItem("-- Seleccione una serie --", None)

                    for equipo in equipos:
                        # 2026-07-09: un mismo número de serie puede repetirse con
                        # varios factores de calibración (recalibraciones históricas)
                        # sin nada que los distinga en el desplegable -> se agrega
                        # la fecha del certificado y si es la calibración vigente.
                        # .get() defensivo: fixtures de test más viejos no traen
                        # estas claves y deben seguir mostrando solo "Serie: X".
                        texto = f"Serie: {equipo['serie']}"
                        fecha = equipo.get('fecha_calibr')
                        if fecha:
                            texto += f" — calibrado {fecha}"
                        vigente = equipo.get('vigente')
                        if vigente is not None:
                            texto += " ✓ vigente" if vigente else " (no vigente)"
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

    def _mostrar_tpr2010(self, checked):
        """G2 (auditoría 2026-07-10): visible solo con Fotones marcado."""
        self.lbl_tpr2010.setVisible(checked)
        self.tpr2010.setVisible(checked)
        self.mostrar_ayuda_tpr2010.setVisible(checked)
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
                # H3.6 (auditoría 2026-07-14, revierte G3): se muestra Y
                # calcula el valor CRUDO del certificado (p.ej. P0=101.325,
                # 1 atm estándar -- no una cifra espuria). G3 redondeaba a 1
                # decimal asumiendo que esa era la precisión real del
                # certificado; el comparador app-vs-Excel demostró que las
                # hojas SÍ traen la precisión completa y que redondear
                # introduce una diferencia estructural (~0.02% en ktp) entre
                # la calculadora y el motor/comparador. Decisión del físico:
                # lo mostrado debe ser igual a lo calculado, así que no se
                # separan -- se deja de redondear en el origen.
                self.temp_0.setText(str(self.datos_equipo["t_cal"]))
                self.pressure_0.setText(str(self.datos_equipo["p_cal"]))
                # G3 (auditoría 2026-07-10): antes NO se cargaba h_cal aunque
                # EquiposService.obtener_por_id ya lo devuelve -- el físico
                # tenía que teclearlo a mano cada vez que elegía la serie.
                h_cal = self.datos_equipo.get("h_cal")
                if h_cal is not None:
                    self.humr_cal.setText(str(h_cal))
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

            # I1: se busca filtrando por MÁQUINA (self.acelerador_actual), no
            # por el dato del combo de series -- el segundo parámetro de
            # buscar_por_fecha es el Acelerador ("IX"/"Seiscientos"/"Hc").
            # El código anterior pasaba equipo_id (un entero del catálogo):
            # al abrir el diálogo era None (traía registros de CUALQUIER
            # máquina) y con serie elegida nunca hacía match.
            datos = DosisService.buscar_por_fecha(
                fecha_seleccionada, self.acelerador_actual)

            if datos:
                # I1: NUNCA recargar en silencio. Antes, el setDate de
                # fecha_inicial (H3.4) disparaba esta ruta al abrir y el
                # registro recién guardado con "Aceptar y cerrar" reaparecía
                # completo ("valores pegados", reporte del físico 16-07).
                # Cargar un registro guardado ahora es una decisión explícita.
                if self._confirmar_carga_registro(fecha_seleccionada):
                    self.cargar_datos_desde_db(datos)
                    print(f"Data loaded for date: {fecha_seleccionada}")
            else:
                # No data found
                print(f"No data found for date: {fecha_seleccionada}")

        except Exception as e:
            print(f"Error in date change handler: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Error loading data for selected date: {e}")

    def _confirmar_carga_registro(self, fecha):
        """I1: hay un registro guardado para la fecha elegida en esta máquina
        -- pregunta antes de volcarlo sobre el formulario. Aislado en su
        propio método (mismo patrón que `_confirmar_registro_existente` de
        H2.3) para que los tests puedan sustituirlo sin disparar un
        QMessageBox modal real.

        Default No: el caso más frecuente es abrir la calculadora para un
        cálculo NUEVO (y "No" tampoco borra nada de lo ya tecleado); "Sí"
        cubre la consulta/edición de un registro histórico (D2.2/E4).
        """
        respuesta = QMessageBox.question(
            self, "Registro guardado",
            f"Ya existe un registro guardado del {fecha} para esta máquina.\n\n"
            "¿Cargarlo en la calculadora? Si va a hacer un cálculo nuevo, "
            "elija No (no se borra nada).",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return respuesta == QMessageBox.Yes


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

                # Restaurar el PROTOCOLO ANTES que cualquier otro campo (modelo,
                # TPR, etc.): combo_modelos.setCurrentIndex más abajo dispara
                # on_modelo_cambiado (blockSignals(True) en self NO bloquea
                # señales de widgets hijos - D2.2), que evalúa la guarda de kQ
                # contra el protocolo ACTUALMENTE seleccionado. Si el protocolo
                # se restaura después, esa evaluación usaría el protocolo
                # equivocado. El widget combo_protocolo nace en K4; hasta
                # entonces esto es un no-op defensivo.
                if hasattr(self, "combo_protocolo"):
                    protocolo_guardado = datos.get('protocolo_trs398') or '2000'
                    idx_protocolo = self.combo_protocolo.findData(protocolo_guardado)
                    if idx_protocolo >= 0:
                        self.combo_protocolo.setCurrentIndex(idx_protocolo)

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
                    self.lect_m2_1.setText(str(datos['lectura_m2_1']))
                if datos.get('lectura_m2_2'):
                    self.lect_m2_2.setText(str(datos['lectura_m2_2']))
                if datos.get('lectura_m2_3'):
                    self.lect_m2_3.setText(str(datos['lectura_m2_3']))
                if datos.get('lectura_m2'):
                    self.lect_m2.setText(str(datos['lectura_m2']))
                
                if datos.get('Mq'):
                    self.MQvar.setText(str(datos['Mq']))
                
                # Results
                if datos.get('Zref'):
                    self.Zref.setText(str(datos['Zref']))
                
                if datos.get('Zmax'):
                    self.Zmax.setText(str(datos['Zmax']))
                
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

                # R50 medido (electrones) y PDD de electrones (E4, 2026-07-10):
                # restaurar R50 dispara su cascada completa (calidad -> zref ->
                # kQ automático), igual que Modelo_equipo/Numero_serie más
                # arriba -- por eso va ANTES del bloque "al final" de abajo,
                # que re-aplica el kQ histórico y gana sobre esta cascada.
                if datos.get('r50_medido'):
                    self.R50.setText(str(datos['r50_medido']))

                if datos.get('pdd_zref_electrones'):
                    self.pddzrefE.setText(str(datos['pdd_zref_electrones']))

                # Re-aplicar factor_calibracion: seleccionar Modelo_equipo y
                # Numero_serie arriba dispara on_serie_cambiada -> cargar_datos_equipo(),
                # que trae el factor VIGENTE del catálogo (services/equipos_service.py) y
                # pisa el valor ya restaurado. Si el equipo fue recalibrado desde que se
                # guardó este registro, el histórico debe ganar.
                if datos.get('factor_calibracion'):
                    self.visualize_calib.setText(str(datos['factor_calibracion']))

                # Re-aplicar el kQ guardado AL FINAL, mismo patrón que
                # factor_calibracion: el cambio de Modelo_equipo/Numero_serie/
                # R50 arriba pudo disparar la cascada de kQ automático
                # (actualizar_kCharge o Kq0_r50) con el protocolo/TPR/R50 en
                # un estado intermedio y recalcular un valor distinto. El kQ
                # histórico guardado con el registro debe ganar siempre.
                #
                # Corregido en E4 (2026-07-10): "Kq_0" es la clave COMPARTIDA
                # con la que guardar_db persiste el kQ sin importar el tipo de
                # radiación (ver guardar_db). Antes esto SIEMPRE escribía en
                # self.Kq_0 (el widget de FOTONES) -- un registro de
                # electrones cargado dejaba su kQ real en el widget
                # equivocado y Kq0r50_widget (y por tanto Dzref) vacío.
                if datos.get('Kq_0'):
                    if datos.get('Tipo_de_radiacion') == 'Electrones':
                        self.Kq0r50_widget.setText(str(datos['Kq_0']))
                    else:
                        self.Kq_0.setText(str(datos['Kq_0']))

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


    # Campos exigidos completos antes de guardar (F3, auditoría 2026-07-10):
    # decisión explícita del usuario -- "todos los campos deben estar
    # completos", en respuesta al hallazgo de que el único registro real de
    # producción se guardó casi vacío (sin validación previa). Se EXCLUYEN 3
    # casos donde exigirlos sería imposible o incoherente:
    #   - pdd10/pdd20: los widgets existen pero su bloque completo
    #     (pdd_box/pdd_layout) nunca se agrega a ningún layout visible -- el
    #     físico no puede verlos ni llenarlos. Alimentan la ruta muerta de kQ0
    #     vía Q0/A (hallazgo D1-H2, congelada). No se activan aquí.
    #   - tmrzref: solo aplica a geometría SAD, desactivada (comentada en
    #     calcular_dosis_maxima) -- no tiene forma de llenarse hoy.
    #   - pddzref (fotones) / r50_medido+pdd_zref_electrones (electrones):
    #     mutuamente excluyentes según Tipo_de_radiacion.
    _CAMPOS_SIEMPRE_REQUERIDOS = (
        "Fecha", "Acelerador", "equipo_id", "Modelo_equipo", "Numero_serie",
        "factor_calibracion", "Tamano_campo", "Tipo_de_radiacion",
        "Tipo_de_escaneo", "Tipo_de_medicion",
        "temperatura", "presion", "Humedad_calibracion",
        "temp_clinica", "presion_clinica", "Humedad_relativa",
        "ktp", "lectura_Q1", "lectura_Q2", "lectura_Q3", "lectura_dosimetro",
        "unidades_monitor", "cociente_ldv1_um",
        "Mplus", "Lectura_neg_1", "Lectura_neg_2", "Lectura_neg_3",
        "Lectura_neg_prom", "Kpol",
        "tension_v1", "tension_v2", "cociente_tensiones",
        "lectura_m1", "lectura_m2_1", "lectura_m2_2", "lectura_m2_3", "lectura_m2",
        "cociente_lecturas", "a0", "a1", "a2", "ks", "Mq",
        "Zref", "Zmax", "Kq_0", "Dzref", "dosis_maxima",
    )

    # Etiquetas amigables para el aviso de campos faltantes (Fase G1,
    # auditoría 2026-07-10): el físico no debe leer claves crudas de columna
    # ("Tipo_de_medicion") sino el nombre del dato tal como lo conoce.
    _ETIQUETAS_CAMPOS = {
        "Fecha": "Fecha",
        "Acelerador": "Acelerador",
        "equipo_id": "Equipo (selección de cámara)",
        "Modelo_equipo": "Modelo de cámara",
        "Numero_serie": "Número de serie de la cámara",
        "factor_calibracion": "Factor de calibración (N_D,w)",
        "Tamano_campo": "Tamaño de campo",
        "Tipo_de_radiacion": "Tipo de radiación (Fotones/Electrones)",
        "Tipo_de_escaneo": "Tipo de escaneo (Pulse/Pulse scanned)",
        "Tipo_de_medicion": "Tipo de medición (SSD)",
        "temperatura": "Temperatura de calibración",
        "presion": "Presión de calibración",
        "Humedad_calibracion": "Humedad de calibración",
        "temp_clinica": "Temperatura clínica",
        "presion_clinica": "Presión clínica",
        "Humedad_relativa": "Humedad relativa clínica",
        "ktp": "Factor ktp",
        "lectura_Q1": "Lectura Q1",
        "lectura_Q2": "Lectura Q2",
        "lectura_Q3": "Lectura Q3",
        "lectura_dosimetro": "Lectura promedio del dosímetro",
        "unidades_monitor": "Unidades de monitor (UM)",
        "cociente_ldv1_um": "Cociente lectura/UM",
        "Mplus": "Lectura M+ (polaridad positiva)",
        "Lectura_neg_1": "Lectura M- 1 (polaridad negativa)",
        "Lectura_neg_2": "Lectura M- 2 (polaridad negativa)",
        "Lectura_neg_3": "Lectura M- 3 (polaridad negativa)",
        "Lectura_neg_prom": "Lectura M- promedio (polaridad negativa)",
        "Kpol": "Factor de polaridad Kpol",
        "tension_v1": "Tensión V1",
        "tension_v2": "Tensión V2",
        "cociente_tensiones": "Cociente de tensiones V1/V2",
        "lectura_m1": "Lectura M1 (recombinación)",
        "lectura_m2_1": "Lectura M2 (1)",
        "lectura_m2_2": "Lectura M2 (2)",
        "lectura_m2_3": "Lectura M2 (3)",
        "lectura_m2": "Lectura M2 promedio",
        "cociente_lecturas": "Cociente M1/M2",
        "a0": "Coeficiente a0",
        "a1": "Coeficiente a1",
        "a2": "Coeficiente a2",
        "ks": "Factor de recombinación Ks",
        "Mq": "Lectura corregida Mq",
        "Zref": "Profundidad de referencia (zref; en electrones se calcula sola del R50)",
        "Zmax": "Profundidad de dosis máxima (zmax)",
        "Kq_0": "Factor de calidad del haz (kQ)",
        "Dzref": "Dosis en zref",
        "dosis_maxima": "Dosis máxima (cGy/UM)",
        "r50_medido": "R50 medido (electrones)",
        "pdd_zref_electrones": "PDD en zref (electrones)",
        "pddzref": "PDD en zref (fotones)",
    }

    @classmethod
    def _campos_faltantes(cls, datos):
        """Claves de `datos` vacías/None entre las exigidas por guardar_db:
        las siempre-requeridas más la condicionada por Tipo_de_radiacion
        (PDD de fotones o de electrones, nunca ambas a la vez)."""
        requeridos = list(cls._CAMPOS_SIEMPRE_REQUERIDOS)
        if datos.get("Tipo_de_radiacion") == "Electrones":
            requeridos += ["r50_medido", "pdd_zref_electrones"]
        else:
            requeridos += ["pddzref"]
        return [c for c in requeridos if not datos.get(c)]

    def _avisar_formulario_incompleto(self, etiquetas):
        """Muestra los campos faltantes (nombres amigables) y pregunta si el
        físico quiere salir sin guardar. Devuelve True solo si elige
        explícitamente "Descartar y salir".

        Aislado en su propio método -- en vez de un QMessageBox.warning
        estático -- para que guardar_db/on_aceptar_y_cerrar puedan decidir
        si cierran el diálogo, y para que los tests puedan sustituirlo sin
        disparar un QMessageBox modal real (ver test_calculadora_dosis_g1.py).
        """
        aviso = QMessageBox(self)
        aviso.setIcon(QMessageBox.Warning)
        aviso.setWindowTitle("Formulario incompleto")
        aviso.setText(
            "No se puede guardar: faltan los siguientes campos por "
            "completar:\n\n" + "\n".join(f"• {e}" for e in etiquetas)
            + "\n\n¿Desea salir de la calculadora sin guardar?")
        btn_seguir = aviso.addButton("Seguir editando", QMessageBox.RejectRole)
        btn_salir = aviso.addButton("Descartar y salir", QMessageBox.DestructiveRole)
        aviso.setDefaultButton(btn_seguir)
        aviso.exec_()
        return aviso.clickedButton() is btn_salir

    def _confirmar_registro_existente(self, fecha, acelerador):
        """H2.3: ya existe un registro guardado para esta fecha+acelerador --
        pregunta antes de agregar una nueva versión. Aislado en su propio
        método (regla 5, mismo patrón que `_confirmar_reemplazo_reporte_
        diario` de H2.2) para que los tests puedan sustituirlo sin disparar
        un QMessageBox modal real.

        A diferencia del reporte diario (H2.2, que hace DELETE+INSERT),
        aquí NUNCA se borra nada: "Sí" agrega una fila nueva (conserva el
        historial; `buscar_por_fecha` ya toma la más reciente vía `ORDER BY
        id DESC LIMIT 1`); "No" cancela el guardado sin perder lo tecleado.
        """
        respuesta = QMessageBox.question(
            self, "Registro existente",
            f"Ya existe un registro de {fecha} para {acelerador}.\n\n"
            "¿Guardar una nueva versión? Se conserva el historial; la "
            "lectura más reciente será la que se guarde ahora.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return respuesta == QMessageBox.Yes

    def _usuario_actual(self):
        """Nombre del físico logueado, para el audit trail (H2.4).

        `self.main_window` es el formulario mensual que abrió la
        calculadora (`abrir_calculadora`, seiscientos_mensual.py) y trae
        `self.user_id._nombre` desde el login -- mismo dato que usa
        `add_info` (load.py). Puede no existir (tests con un QWidget
        genérico como padre, o si algún día se abre sin ese contexto):
        devolver None es preferible a reventar, la auditoría es best-effort.
        """
        try:
            return self.main_window.user_id._nombre
        except AttributeError:
            return None

    def guardar_db(self):
        """
        Save dosimetry data to database using the separate database service.
        Also generates the calibration report.

        Returns
        -------
        bool
            True si el registro quedó guardado en la base de datos. False si
            la validación falló (formulario incompleto) o si el guardado en
            sí falló. on_aceptar_y_cerrar usa este valor para decidir si
            cierra el diálogo -- ver Fase G1 (auditoría 2026-07-10): antes,
            "Aceptar y Cerrar" cerraba el diálogo aunque no se hubiera
            guardado nada, perdiendo los datos tecleados.
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
            "lectura_m2_3": self.lect_m2_3.text(),
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
            "dosis_maxima": self.dosis_maxima.text(),
            "protocolo_trs398": (self.combo_protocolo.currentData()
                                  if hasattr(self, "combo_protocolo") else "2000"),
            # E4 (auditoría 2026-07-10): sin esto, un registro de ELECTRONES
            # guardado no tenía de dónde restaurar R50/PDD al recargarlo (ver
            # cargar_datos_desde_db). QualityR50/zrefR50/Kq0r50_widget no se
            # persisten aparte: se derivan de R50 + modelo + protocolo.
            "r50_medido": self.R50.text(),
            "pdd_zref_electrones": self.pddzrefE.text(),
        }

        faltantes = self._campos_faltantes(datos)
        if faltantes:
            etiquetas = [self._ETIQUETAS_CAMPOS.get(c, c) for c in faltantes]
            if self._avisar_formulario_incompleto(etiquetas):
                self.reject()
            return False

        # H2.3 (versionado consciente): si ya existe un registro para esta
        # fecha+acelerador, preguntar ANTES de generar el reporte/guardar
        # (evita generar un PDF de un guardado que el físico termine
        # cancelando). No se borra nada aquí -- ver _confirmar_registro_existente.
        existente = DosisService.buscar_por_fecha(datos["Fecha"], datos["Acelerador"])
        if existente and not self._confirmar_registro_existente(
                datos["Fecha"], datos["Acelerador"]):
            return False

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
            # ruta_db explícita (defensiva, TEMA C del PLAN_HI): la calculadora
            # guarda vía DosisService (su propia conexión, no
            # Conexion().conectar() -- "doble patrón de conexión"). Desde
            # HI-3, DosisService también resuelve la ruta vía este mismo
            # módulo conection (ya no una copia por valor), así que esto es
            # la MISMA fuente que usó el guardado -- ya no dos caminos que
            # puedan divergir (bug real encontrado y corregido al implementar
            # H2.4 -- ver test_audit_minimo.py).
            _registrar_auditoria(
                self._usuario_actual(), ACCION_GUARDAR, "calculadora_dosimetrica",
                ref=f"{datos.get('Fecha')}|{datos.get('Acelerador')}",
                detalle=f"Tipo_de_radiacion={datos.get('Tipo_de_radiacion')}",
                ruta_db=_conection_mod.ruta_base_datos())
            QMessageBox.information(self, "Success", "Datos cargados exitosamente")
        else:
            QMessageBox.warning(self, "Error", "Failed to save dosimetry data to database")

        return bool(exito)

    def on_aceptar_y_cerrar(self):
        """Slot único de btn_ok (Fase G1, auditoría 2026-07-10).

        Antes, btn_ok conectaba guardar_db Y accept() como dos señales
        independientes: si guardar_db interrumpía sin guardar (formulario
        incompleto o fallo de guardado), accept() se ejecutaba de todas
        formas y cerraba el diálogo, perdiendo los datos tecleados -- así lo
        vivió el físico con una dosimetría de electrones completa. Ahora
        solo se cierra si guardar_db confirma que el guardado se completó;
        si no, el propio guardar_db ya preguntó (vía
        _avisar_formulario_incompleto) si se desea salir sin guardar.
        """
        if self.guardar_db():
            self.accept()

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
        self._actualizar_visibilidad_pdd()

    def mostrarWidget_PDD_Fotones(self, checked):

        self.Kq_0.setVisible(checked)

    def mostrar_pddE(self, checked):
        self._actualizar_visibilidad_pdd()

    def _actualizar_visibilidad_pdd(self):
        """I2: fuente única de la visibilidad de los dos campos PDD(Zref).

        Antes cada campo se mostraba por su propia señal aislada: SSD.toggled
        mostraba el de FOTONES sin mirar el tipo de haz, y el auto-SSD de
        H1.1 (electrones marca SSD por código) los dejaba VISIBLES A LA VEZ
        -- el "campo PDD duplicado" que reportó el físico el 16-07. Derivar
        ambos del estado completo hace imposible ese solape por construcción.
        """
        es_electrones = self.electrones.isChecked()
        self.pdd_zref.setVisible(self.SSD.isChecked() and self.fotones.isChecked())
        self.pddzref.setVisible(self.SSD.isChecked() and self.fotones.isChecked())
        self.pdd_zrefE.setVisible(es_electrones)
        self.pddzrefE.setVisible(es_electrones)
        self.Kq0r50_widget.setVisible(es_electrones)

    def _actualizar_visibilidad_zref(self, *_):
        """I3: el Zref de Resultados Finales se oculta en electrones (ahí es
        la misma cantidad que zrefR50, autollenada -- pedirlo a mano era
        re-teclear un valor ya calculado); en fotones sigue siendo entrada
        manual legítima (10.0 / 5.0 g/cm²).
        """
        es_electrones = self.electrones.isChecked()
        self.lbl_zref.setVisible(not es_electrones)
        self.Zref.setVisible(not es_electrones)
        if es_electrones:
            # Sincronizar ya, por si el R50 se tecleó antes de marcar el haz.
            if self.zrefR50.text():
                self.Zref.setText(self.zrefR50.text())
        else:
            # Al volver a fotones, si Zref quedó con el valor autollenado de
            # electrones (~1.3-3 g/cm²) se limpia: no es un zref de fotones.
            # Un valor tecleado a mano por el físico no se toca.
            if self.Zref.text() and self.Zref.text() == self.zrefR50.text():
                self.Zref.clear()
    
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
            # zref = 0.6*R50,w - 0.1 con la CALIDAD del haz (QualityR50), no el
            # R50 crudo del escaneo — corregido en la auditoría 2026-07-09.
            r50w = self.QualityR50.text()
            q_r50 = DosisService.r50_depth(float(r50w))
            self.zrefR50.setText(str(q_r50))
            # I3: en electrones, el "Zref" de Resultados Finales (metadato
            # que va a BD/PDF y que la validación F3 exige) es esta MISMA
            # cantidad -- se autollena para que el físico no re-teclee el
            # valor que la app acaba de calcular dos bloques más arriba.
            # OJO: nunca ocultar este campo sin llenarlo (campo requerido
            # invisible = guardado bloqueado, la trampa que H1.1 corrigió).
            if self.electrones.isChecked():
                self.Zref.setText(str(q_r50))
        except Exception as e:
            print(e)
            self.zrefR50.clear()
            if self.electrones.isChecked():
                self.Zref.clear()
        
    
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
            else:
                return  # sin tipo de escaneo elegido, "modo" quedaba sin asignar
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
        modelo = self.combo_modelos.currentData()
        protocolo = (self.combo_protocolo.currentData()
                     if hasattr(self, "combo_protocolo")
                     and self.combo_protocolo.currentData() else "2000")
        if modelo is None or not DosisService.camara_tiene_kq_electrones(
                modelo, protocolo=protocolo):
            # Guarda de ELECTRONES (corregida 2026-07-09): antes consultaba
            # camara_tiene_kq (tabla de FOTONES), que bloqueaba a la Roos y
            # habilitaba interpolar la tabla equivocada justo para las cámaras
            # de fotones. El kQ queda en ingreso manual y no se pisa lo que
            # escriba el físico.
            return
        try:
            # Se interpola a la CALIDAD R50,w (QualityR50), como el Cuadro 18.
            r50w = float(self.QualityR50.text())
            quality_result = DosisService.interpolar_r50(modelo, r50w,
                                                         protocolo=protocolo)
            self.Kq0r50_widget.setText(str(quality_result))
        except ValueError:
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
        modelo = self.combo_modelos.currentData()
        protocolo = self.combo_protocolo.currentData() if hasattr(self, "combo_protocolo") else "2000"
        if modelo is None or not DosisService.camara_tiene_kq(modelo, protocolo):
            # Sin modelo o sin datos kQ en el protocolo activo: no tocar el
            # campo, que queda en ingreso manual (antes esto borraba el valor
            # escrito a mano).
            return
        try:
            self.Kq_0.setText(str(round(
                DosisService.interpolar_kq0(modelo, float(self.tpr2010.text()), protocolo), 5)))
        except ValueError:
            self.Kq_0.clear()  # TPR20,10 vacío o no numérico: kQ auto pendiente

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

        grupo_anterior = None
        for i, energia in enumerate(energias):
            # H3.3 (auditoría 2026-07-14): etiqueta de grupo "Fotones:" /
            # "Electrones:" antes del primer botón de cada tipo -- las
            # energías de fotones (Nmv) y electrones (Nmev) venían mezcladas
            # sin distinción visual.
            grupo = "Electrones" if "mev" in energia.lower() else "Fotones"
            if grupo != grupo_anterior:
                lbl_grupo = QLabel(f"{grupo}:")
                lbl_grupo.setStyleSheet("font-weight: bold;")
                self.layout_asignar.addWidget(lbl_grupo)
                grupo_anterior = grupo

            # "6MV"/"6MEV" (energia.upper()) eran legibles pero fáciles de
            # confundir a primera vista -- ahora "6 MV"/"6 MeV". Sin conflicto
            # de orden entre los dos .replace: "mv" nunca aparece como
            # substring dentro de "Nmev" (las letras no son adyacentes:
            # m-e-v, no m-v), verificado contra las 6 energías reales.
            etiqueta = energia.replace("mev", " MeV").replace("mv", " MV")
            btn = QPushButton(etiqueta)
            color = colores[i % len(colores)]
            #self.estilo_boton(btn, color)
            # F3: ver tooltip de btn_ok -- este botón asigna la dosis al
            # formulario mensual pero NO guarda el registro de la calculadora.
            btn.setToolTip(
                f"Asigna la dosis calculada al campo de {etiqueta} del "
                "formulario mensual.\nNO guarda este cálculo en el registro "
                "de la calculadora -- para eso, use \"Aceptar y Cerrar\".")
            btn.clicked.connect(lambda _, e=energia: self.emitir_dosis(e))
            self.layout_asignar.addWidget(btn)
    
    def emitir_dosis(self, energia):
        """Asigna la dosis calculada al campo de `energia` en el formulario
        mensual (ln_dosis_ref_cgy_um_{energia}), en cGy/MU.

        Corregido en F2 (auditoría 2026-07-10, hallazgo H-F1): calculaba
        `1 - dosis_maxima`. `dosis_maxima` está en Gy/MU (≈0.010, verificado
        en las 4 configuraciones del corpus 2024); el campo destino espera
        cGy/MU (≈1.0, verificado contra las 37 filas reales de
        dosimetriaMen -- confirmado por el usuario). La fórmula vieja
        producía un valor cercano a 1 por coincidencia aritmética (1 - un
        número pequeño ≈ 1), pero con la magnitud y el signo equivocados
        -- se hace evidente con factores de calibración fuera del rango
        típico (puede dar hasta negativo). La transferencia correcta es
        `dosis_maxima * 100`.
        """
        QApplication.processEvents()
        try:
            dosis_gy_mu = float(self.dosis_maxima.text())
            if dosis_gy_mu <= 0:
                raise ValueError("dosis_maxima no positiva o no calculada")
            valor = dosis_gy_mu * 100
            self.dosis_asignada.emit(energia, valor)
            # H3.3: misma etiqueta legible de los botones ("6 MV"/"6 MeV"),
            # no energia.upper() ("6MV"/"6MEV").
            etiqueta = energia.replace("mev", " MeV").replace("mv", " MV")
            QMessageBox.information(self, "✓ Éxito",
                f"Dosis asignada a {etiqueta}: {valor:.4f} cGy/MU")
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
        
        

   
