import sqlite3 as sql
import pandas as pd
from PyQt5.QtWidgets import QComboBox ,QWidget, QDialog, QInputDialog ,QGridLayout, QVBoxLayout, QHBoxLayout ,QPushButton, QTableWidget, QFileDialog, QListWidget, QLabel, QDateEdit, QHBoxLayout, QMessageBox, QListWidgetItem, QTableWidgetItem, QSizePolicy
from PyQt5.QtCore import Qt
import os
from openpyxl.drawing.image import Image 
from ui.paginasGuia.dialogs import DateRangeDialog
import openpyxl as exl
import io
import PIL
import numpy as np
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QWidget
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
connect = sql.connect('BaseDatosQA.db')
class Color(QWidget):
    def __init__(self, color):
        super().__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(color))
        self.setPalette(palette)
    def initUI(self):
        # Main vertical layout
        main = QVBoxLayout()
        main.setContentsMargins(46, 16, 46,16)
        main.setSpacing(18)
        
        # Header label
        self.label = QLabel("Describa detalladamente el error o fallo encontrado")
        self.label.setStyleSheet("font-size:13px; font-weight:bold; margin-bottom:6px;")
        main.addWidget(self.label)
        
        # 2x2 Grid layout for aesthetic spacing
        grid = QGridLayout()
        grid.setSpacing(20)
        grid.setContentsMargins(46, 16, 46, 16)
        
        # Create placeholders for visual balance
        ph1 = QWidget()
        ph1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ph1.setStyleSheet("background-color: #f0f0f0; border-radius: 8px;")

        
        ph3 = QWidget()
        ph3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ph3.setStyleSheet("background-color: #f0f0f0; border-radius: 8px;")
        
        # Main combobox
        self.text = QInputDialog()
     
        self.load_tables()
        
        # Selector (secondary) combobox
        self.selector = QComboBox()
        self.selector.setStyleSheet("QComboBox { padding:5px 8px; min-height:26px; font-size:11px; border-radius:4px; }")
        for i in range(self.table_list.count()):
            text = self.table_list.itemText(i)
            data = self.table_list.itemData(i)
            self.selector.addItem(text, data)
        self.selector.currentIndexChanged.connect(self.on_selector_changed)
        self.selector.currentIndexChanged.connect(self.update_preview)
        self.preview_table = QTableWidget()
        self.update_preview()
        self.preview_table.setMaximumHeight(1500)
        self.table_list.currentIndexChanged.connect(self.update_preview)
        
        # Add widgets to 2x2 grid
        grid.addWidget(self.table_list, 0, 0, 1, 2)
        grid.addWidget(self.preview_table, 1, 0, 2, 2)
        #grid.addWidget(ph3, 1, 1)
        
        # Set stretch factors for balanced layout
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        
        # Add grid to main layout
        main.addLayout(grid)
        main.addSpacing(12)  # small gap between grid and button
        
        # Export button at bottom
        self.export_button = QPushButton("Exportar a Excel")
        self.export_button.setStyleSheet(
            "QPushButton { padding:16px 16px; font-size:12px; font-weight:bold; "
            "background-color:#6fb8c3; color:white; border:none; border-radius:4px; }"
            "QPushButton:hover { background-color:#4a8892; }"
            "QPushButton:pressed { background-color:#2e5d66; }"
        )
        self.export_button.setMinimumHeight(36)
        self.export_button.clicked.connect(self.exportar)
        main.addWidget(self.export_button)
        
        # Set main layout
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setLayout(main)
