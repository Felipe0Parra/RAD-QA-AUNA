# ui/paginasGuia/console_logs.py
"""Visor de `audit_log` (A7, PLAN_AUDITORIA_DOS_EJES_21-07).

Antes de esta tarea, este archivo importaba `AuditEngine`
(`services/auditorias.py`, 100% comentado -- ese import ya fallaba con
`ImportError` antes de llegar a nada más) y consultaba columnas que nunca
existieron en el `audit_log` real (`username/action/module/status/detail` en
vez de `usuario/accion/tabla/ref/detalle`, el esquema real de
`services/audit_minimo.py`). El widget nunca estuvo conectado a la UI: la
pestaña "Registros" y el método que la crea siguen comentados en
`mainpages.py` -- arreglarlo aquí lo deja correcto y usable, pero activar la
pestaña es una decisión de producto aparte (¿quién debería poder ver esto?
¿todos o solo un admin?, y hoy no existe ningún concepto de rol de sesión
real para responderlo), no parte de esta limpieza.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QPushButton, QHeaderView, QLineEdit
)
from PyQt5.QtCore import Qt
import data.ManejoDatos.conection as con


class Registros(QWidget):

    COLUMNAS = ['Fecha/Hora', 'Usuario', 'Acción', 'Tabla', 'Ref', 'Detalle']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._cargar_historico()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        filtros = QHBoxLayout()

        self._input_buscar = QLineEdit()
        self._input_buscar.setPlaceholderText('Buscar acción, tabla o usuario...')
        self._input_buscar.returnPressed.connect(self._cargar_historico)

        btn_refresh = QPushButton('↻ Actualizar')
        btn_refresh.clicked.connect(self._cargar_historico)

        filtros.addWidget(QLabel('Buscar:'))
        filtros.addWidget(self._input_buscar)
        filtros.addWidget(btn_refresh)
        filtros.addStretch()

        self._tabla = QTableWidget()
        self._tabla.setColumnCount(len(self.COLUMNAS))
        self._tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self._tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setSortingEnabled(True)

        root.addLayout(filtros)
        root.addWidget(self._tabla)

    # ── Datos ────────────────────────────────────────────────────────────────

    def _cargar_historico(self):
        busqueda = self._input_buscar.text().strip()

        query = """
            SELECT timestamp, usuario, accion, tabla, ref, detalle
            FROM audit_log
            WHERE 1=1
        """
        params = []

        if busqueda:
            query += " AND (accion LIKE ? OR tabla LIKE ? OR usuario LIKE ?)"
            comodin = f'%{busqueda}%'
            params.extend([comodin, comodin, comodin])

        query += " ORDER BY timestamp DESC LIMIT 500"

        try:
            with con.Conexion().conectar() as db:
                filas = db.execute(query, params).fetchall()
            self._poblar_tabla(filas)
        except Exception as e:
            print(f"[Registros] Error cargando histórico: {e}")

    def _poblar_tabla(self, filas):
        self._tabla.setSortingEnabled(False)
        self._tabla.setRowCount(0)
        for fila in filas:
            idx = self._tabla.rowCount()
            self._tabla.insertRow(idx)
            for col, valor in enumerate(fila):
                item = QTableWidgetItem(str(valor if valor is not None else ''))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._tabla.setItem(idx, col, item)
        self._tabla.setSortingEnabled(True)
