# ui/paginasGuia/console_logs.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QComboBox, QPushButton,
    QHeaderView, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QColor
import data.ManejoDatos.conection as con
from services.auditorias import AuditEngine


class Registros(QWidget):

    STATUS_COLORS = {
        'OK':       QColor('#1a6b1a'),
        'ERROR':    QColor('#8b1a1a'),
        'CRITICAL': QColor('#4a0000'),
    }

    COLUMNAS = ['Fecha/Hora', 'Usuario', 'Acción', 'Módulo', 'Estado', 'Detalle']

    def __init__(self, parent=None):
        super().__init__(parent)
        engine = AuditEngine()
        self._username = engine._current_user
        self._role     = getattr(engine, '_current_role', None)
        self._setup_ui()
        engine.new_entry.connect(self._on_new_entry)
        self._cargar_historico()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # Filtros
        filtros = QHBoxLayout()

        self._combo_estado = QComboBox()
        self._combo_estado.addItems(['Todos', 'OK', 'ERROR', 'CRITICAL'])
        self._combo_estado.currentTextChanged.connect(self._cargar_historico)

        self._input_buscar = QLineEdit()
        self._input_buscar.setPlaceholderText('Buscar acción o módulo...')
        self._input_buscar.returnPressed.connect(self._cargar_historico)

        btn_refresh = QPushButton('↻ Actualizar')
        btn_refresh.clicked.connect(self._cargar_historico)

        filtros.addWidget(QLabel('Estado:'))
        filtros.addWidget(self._combo_estado)
        filtros.addSpacing(10)
        filtros.addWidget(self._input_buscar)
        filtros.addWidget(btn_refresh)
        filtros.addStretch()

        # Tabla
        self._tabla = QTableWidget()
        self._tabla.setColumnCount(len(self.COLUMNAS))
        self._tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self._tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setSortingEnabled(True)

        root.addLayout(filtros)
        root.addWidget(self._tabla)

    # ── Datos ────────────────────────────────────────────────────────────────

    def _cargar_historico(self):
        estado    = self._combo_estado.currentText()
        busqueda  = self._input_buscar.text().strip()

        query  = """
            SELECT timestamp, username, action, module, status, detail
            FROM audit_log
            WHERE 1=1
        """
        params = []

        # Usuarios normales solo ven sus propias acciones
        if self._role != 'admin':
            query += " AND username = ?"
            params.append(self._username)

        if estado != 'Todos':
            query += " AND status = ?"
            params.append(estado)

        if busqueda:
            query += " AND (action LIKE ? OR module LIKE ?)"
            params.extend([f'%{busqueda}%', f'%{busqueda}%'])

        query += " ORDER BY timestamp DESC LIMIT 500"

        try:
            with con.Conexion().conectar() as db:
                filas = db.execute(query, params).fetchall()
            self._poblar_tabla(filas)
        except Exception as e:
            print(f"[AuditPanel] Error cargando histórico: {e}")

    def _poblar_tabla(self, filas):
        self._tabla.setSortingEnabled(False)
        self._tabla.setRowCount(0)
        for fila in filas:
            idx = self._tabla.rowCount()
            self._tabla.insertRow(idx)
            estado = fila[4]
            color  = self.STATUS_COLORS.get(estado)
            for col, valor in enumerate(fila):
                item = QTableWidgetItem(str(valor or ''))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if color:
                    item.setForeground(color)
                self._tabla.setItem(idx, col, item)
        self._tabla.setSortingEnabled(True)

    # ── Tiempo real ──────────────────────────────────────────────────────────

    @pyqtSlot(dict)
    def _on_new_entry(self, entry: dict):
        # Filtro de visibilidad
        if self._role != 'admin' and entry.get('username') != self._username:
            return

        estado_filtro = self._combo_estado.currentText()
        if estado_filtro != 'Todos' and entry.get('status') != estado_filtro:
            return

        self._tabla.setSortingEnabled(False)
        self._tabla.insertRow(0)
        valores = [
            entry.get('timestamp', ''),
            entry.get('username',  ''),
            entry.get('action',    ''),
            entry.get('module',    ''),
            entry.get('status',    ''),
            entry.get('detail',    '') or '',
        ]
        color = self.STATUS_COLORS.get(entry.get('status', ''))
        for col, valor in enumerate(valores):
            item = QTableWidgetItem(str(valor))
            if color:
                item.setForeground(color)
            self._tabla.setItem(0, col, item)
        self._tabla.setSortingEnabled(True)