# ui/paginasGuia/visor_anulados.py
"""Visor de registros anulados (LR6, PLAN_CONTRATO_COMPLETO_19-08.md §6-LR6,
[[DA-49]]).

Solo lectura, sin ningún botón de editar/eliminar/reactivar -- es lo que
sustituye a la reactivación ([[DA-34]], retirada en LR7) como forma de
"llegar" a un registro anulado. Alcance derivado de
`services/anulacion.py::TABLAS_ANULABLES` (nunca escrito a mano, ver
`services/visor_anulados.py::secciones`), cruzado con `audit_log` cuando la
convención de auditoría lo permite (ver docstring de `auditoria_de`).
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from services import visor_anulados as _datos

# Orden de presentación de las 7 raíces -- fijo a propósito (son 7,
# literales, la misma lista corta que `RAICES_QC`): "controles" primero
# porque hoy concentra casi todas las 22 hijas ya migradas (las demás
# raíces solo se muestran a sí mismas mientras MI1 no amplíe el contrato).
_ORDEN_SECCIONES = [
    "controles", "TipoCalibracion", "LinealidadBraquiterapia",
    "aceleradorlineal_600", "aceleradorlineal_ix", "halcyon", "braqui",
]


class VisorAnulados(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._secciones = _datos.secciones()
        self._seccion_actual = _ORDEN_SECCIONES[0]
        self._tabla_actual = self._secciones[self._seccion_actual][0]
        self._fila_seleccionada_rowid = None
        self._setup_ui()
        self._cargar_tabla()

    # ── UI ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        titulo = QLabel("Visor de registros anulados")
        titulo.setStyleSheet("font-size: 20px; font-weight: bold; color: #0a0a0a;")
        subtitulo = QLabel(
            "Recorre el historial completo de la base de datos, incluidos "
            "los registros anulados. No permite editar, eliminar ni "
            "reactivar nada.")
        subtitulo.setStyleSheet("font-size: 13px; color: #5b6570; font-weight: normal;")
        subtitulo.setWordWrap(True)
        root.addWidget(titulo)
        root.addWidget(subtitulo)

        banda = QWidget()
        banda.setObjectName("banda_solo_lectura")
        banda_layout = QHBoxLayout(banda)
        banda_layout.setContentsMargins(10, 6, 10, 6)
        lbl_banda = QLabel(
            "ⓘ Solo lectura -- ninguna acción de esta pantalla escribe en "
            "la base de datos.")
        banda_layout.addWidget(lbl_banda)
        root.addWidget(banda)

        root.addWidget(self._crear_seccion_chips())

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Tabla:"))
        self._combo_tabla = QComboBox()
        self._combo_tabla.currentTextChanged.connect(self._on_cambiar_tabla)
        filtros.addWidget(self._combo_tabla)

        self._input_buscar = QLineEdit()
        self._input_buscar.setPlaceholderText(
            "Buscar por fecha, equipo o referencia...")
        self._input_buscar.textChanged.connect(lambda _t: self._cargar_tabla())
        filtros.addWidget(self._input_buscar, stretch=1)

        btn_refresh = QPushButton("↻ Actualizar")
        btn_refresh.clicked.connect(self._on_actualizar)
        filtros.addWidget(btn_refresh)
        root.addLayout(filtros)

        self._lbl_resumen = QLabel("")
        self._lbl_resumen.setStyleSheet("font-size: 12.5px; color: #5b6570;")
        root.addWidget(self._lbl_resumen)

        cuerpo = QHBoxLayout()
        self._tabla = QTableWidget()
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla.cellClicked.connect(self._on_click_fila)
        cuerpo.addWidget(self._tabla, stretch=1)

        self._panel_detalle = self._crear_panel_detalle()
        self._panel_detalle.setVisible(False)
        cuerpo.addWidget(self._panel_detalle)

        root.addLayout(cuerpo, stretch=1)

        self._popular_combo_tabla()

    def _crear_seccion_chips(self):
        contenedor = QWidget()
        contenedor.setObjectName("chips_seccion_visor")
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel("SECCIÓN"))

        fila_chips = QHBoxLayout()
        fila_chips.setSpacing(6)
        self._grupo_chips = QButtonGroup(self)
        self._grupo_chips.setExclusive(True)
        for seccion in _ORDEN_SECCIONES:
            boton = QPushButton(seccion)
            boton.setCheckable(True)
            boton.setChecked(seccion == self._seccion_actual)
            boton.clicked.connect(
                lambda _checked, s=seccion: self._on_cambiar_seccion(s))
            self._grupo_chips.addButton(boton)
            fila_chips.addWidget(boton)
        fila_chips.addStretch()
        layout.addLayout(fila_chips)
        return contenedor

    def _crear_pill_estado(self, estado):
        """Insignia de color -- reutiliza la convención ya existente
        `QLabel[valor="1"/"0"]` de resources/estilo.qss (sin símbolos,
        DA-18). `WA_TransparentForMouseEvents`: deja pasar el clic al
        QTableWidget de debajo, para que `cellClicked` siga disparando
        aunque el usuario haga clic justo sobre el pill."""
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(6, 2, 6, 2)
        lbl = QLabel("Anulado" if estado == "anulado" else "Vigente")
        lbl.setProperty("valor", "0" if estado == "anulado" else "1")
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(lbl)
        layout.addStretch()
        contenedor.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return contenedor

    def _crear_panel_detalle(self):
        panel = QWidget()
        panel.setStyleSheet(
            "background: #f9fafb; border: 1px solid #ddd; border-radius: 8px;")
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        cabecera = QHBoxLayout()
        titulo = QLabel("Detalle de anulación")
        titulo.setStyleSheet("font-size: 13px; font-weight: bold;")
        cabecera.addWidget(titulo)
        cabecera.addStretch()
        btn_cerrar = QPushButton("×")
        btn_cerrar.setStyleSheet(
            "border: none; background: none; color: #5b6570; font-size: 16px;")
        btn_cerrar.clicked.connect(self._cerrar_detalle)
        cabecera.addWidget(btn_cerrar)
        layout.addLayout(cabecera)

        self._lbl_detalle_usuario = self._agregar_campo_detalle(layout, "Anulado por")
        self._lbl_detalle_fecha = self._agregar_campo_detalle(layout, "Fecha de anulación")
        self._lbl_detalle_texto = self._agregar_campo_detalle(layout, "Detalle registrado")
        self._lbl_detalle_texto.setWordWrap(True)

        pie = QLabel(
            "Tomado de audit_log -- este panel no ofrece reactivar el registro.")
        pie.setWordWrap(True)
        pie.setStyleSheet("font-size: 11px; color: #8a94a0; font-style: italic;")
        layout.addWidget(pie)
        layout.addStretch()
        return panel

    def _agregar_campo_detalle(self, layout, etiqueta):
        lbl_etiqueta = QLabel(etiqueta.upper())
        lbl_etiqueta.setStyleSheet(
            "font-size: 11px; color: #8a94a0; font-weight: bold;")
        layout.addWidget(lbl_etiqueta)
        lbl_valor = QLabel("")
        lbl_valor.setStyleSheet("font-size: 13px; color: #0a0a0a;")
        layout.addWidget(lbl_valor)
        return lbl_valor

    def _popular_combo_tabla(self):
        self._combo_tabla.blockSignals(True)
        self._combo_tabla.clear()
        self._combo_tabla.addItems(self._secciones[self._seccion_actual])
        self._combo_tabla.setCurrentText(self._tabla_actual)
        self._combo_tabla.blockSignals(False)

    # ── Eventos ──────────────────────────────────────────────────────────

    def _on_cambiar_seccion(self, seccion):
        self._seccion_actual = seccion
        self._tabla_actual = self._secciones[seccion][0]
        self._fila_seleccionada_rowid = None
        self._popular_combo_tabla()
        self._cargar_tabla()

    def _on_cambiar_tabla(self, tabla):
        if not tabla:
            return
        self._tabla_actual = tabla
        self._fila_seleccionada_rowid = None
        self._cargar_tabla()

    def _on_actualizar(self):
        self._input_buscar.clear()
        self._fila_seleccionada_rowid = None
        self._cargar_tabla()

    def _on_click_fila(self, fila, _columna):
        rowid_item = self._tabla.item(fila, 0)
        if rowid_item is None:
            return
        rowid = rowid_item.data(Qt.UserRole)
        estado = rowid_item.data(Qt.UserRole + 1)
        if estado != "anulado":
            self._cerrar_detalle()
            return
        if self._fila_seleccionada_rowid == rowid:
            self._cerrar_detalle()
            return
        self._fila_seleccionada_rowid = rowid
        self._mostrar_detalle(rowid)

    def _cerrar_detalle(self):
        self._fila_seleccionada_rowid = None
        self._panel_detalle.setVisible(False)

    # ── Datos ────────────────────────────────────────────────────────────

    def _cargar_tabla(self):
        busqueda = self._input_buscar.text().strip()
        columnas, filas = _datos.filas_de(self._tabla_actual, busqueda)

        self._tabla.setSortingEnabled(False)
        self._tabla.setColumnCount(len(columnas) + 1)
        self._tabla.setHorizontalHeaderLabels(columnas + ["Estado"])
        self._tabla.setRowCount(0)

        for fila in filas:
            idx = self._tabla.rowCount()
            self._tabla.insertRow(idx)
            for col, valor in enumerate(fila["valores"]):
                item = QTableWidgetItem(str(valor if valor is not None else ""))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if col == 0:
                    item.setData(Qt.UserRole, fila["rowid"])
                    item.setData(Qt.UserRole + 1, fila["estado"])
                self._tabla.setItem(idx, col, item)

            # Marcador vacío en la celda -- el pill real es un cellWidget
            # (setItem por sí solo no basta para que cellClicked detecte la
            # fila si el usuario hace clic justo sobre el pill).
            self._tabla.setItem(idx, len(columnas), QTableWidgetItem())
            self._tabla.setCellWidget(idx, len(columnas), self._crear_pill_estado(fila["estado"]))

        vigentes = sum(1 for f in filas if f["estado"] == "vigente")
        anulados = sum(1 for f in filas if f["estado"] == "anulado")
        self._lbl_resumen.setText(
            f"{vigentes} vigentes · {anulados} anulados · {len(filas)} en total")

        if self._fila_seleccionada_rowid is not None:
            if not any(f["rowid"] == self._fila_seleccionada_rowid for f in filas):
                self._cerrar_detalle()

    def _mostrar_detalle(self, rowid):
        auditoria = _datos.auditoria_de(self._tabla_actual, rowid)
        if auditoria is None:
            self._lbl_detalle_usuario.setText("--")
            self._lbl_detalle_fecha.setText("--")
            self._lbl_detalle_texto.setText(
                "Sin registro de auditoría encontrado para esta fila.")
        else:
            self._lbl_detalle_usuario.setText(auditoria["usuario"] or "--")
            self._lbl_detalle_fecha.setText(auditoria["fecha"] or "--")
            self._lbl_detalle_texto.setText(auditoria["detalle"] or "--")
        self._panel_detalle.setVisible(True)


# Alias del nombre de clase que espera `mainpages.py` (mismo patrón que
# `Registros`/`ExportarExcel`/`Config`: `importlib.import_module` +
# `getattr(modulo, "<Nombre>")`).
