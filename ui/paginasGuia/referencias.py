# ui/paginasGuia/referencias.py
"""C.1 (PLAN_REFERENCIAS_EDITABLES_21-09.md): pestaña de referencias.

Patrón calcado de `ui/paginasGuia/usuarios.py` (U5): datos en
`services/referencias_qc.py` (B.2), UI sin SQL propio. Todos pueden VER las
referencias vigentes y su historial (decisión del físico, R4); solo el jefe
y el administrador pueden FIJAR una nueva.

La UI no decide el permiso: pregunta a `es_fisico_jefe` solo para PINTAR
(dejar los controles de edición deshabilitados); el servicio vuelve a
preguntarlo para ACTUAR. Si solo se deshabilitara el botón, el control sería
cosmético -- ver B.2 y el test que invoca `_on_fijar` a mano.

La lista de magnitudes es CERRADA a propósito (§8 del plan: "alguien mete un
umbral normativo en la tabla editable"): solo aparecen magnitudes que un
cálculo LEE de verdad hoy. Una magnitud que se pudiera fijar sin que nada la
consulte sería un campo que miente sobre su propio efecto (DP-25); el test
de la pestaña exige que cada magnitud ofrecida tenga un lector en
producción. Añadir una es una línea aquí MÁS su consumidor.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from services import referencias_qc as _datos
from services.permisos import es_fisico_jefe

# (clave guardada, texto que ve el físico)
MAGNITUDES = (
    ("calidad", "Calidad de referencia (PDD 20/10 en fotones, J2/J1 en electrones)"),
)

# Equipo -> energías con formulario mensual. Las mismas que declara cada
# pantalla mensual en `ENERGIAS`; no se aceptan otras desde la UI.
ENERGIAS_POR_EQUIPO = {
    "Clinac 600": ("6mv",),
    "Clinac ix": ("6mv", "15mv", "6mev", "9mev", "12mev", "15mev"),
    "Halcyon": ("6mv",),
}

COLUMNAS = ["Equipo", "Magnitud", "Energía", "Valor", "Unidad", "Fuente",
            "Observaciones", "Fijada por", "Fecha"]
COLUMNAS_HISTORIAL = ["Estado", "Valor", "Fuente", "Observaciones",
                      "Fijada por", "Fecha"]

TEXTO_SOLO_LECTURA = (
    "Todos pueden consultar las referencias. Solo el físico médico en jefe "
    "y el administrador pueden fijar una nueva.")

MENSAJES_RECHAZO = {
    _datos.DENEGADO_SIN_PERMISO: "No tiene permiso para fijar referencias.",
    _datos.FUENTE_OBLIGATORIA: "Debe indicar de dónde sale el número (fuente).",
    _datos.OBSERVACIONES_OBLIGATORIAS: "Debe escribir una observación.",
    _datos.VALOR_INVALIDO: "El valor debe ser un número mayor que cero.",
}


def _texto_energia(energia):
    return energia if energia else "(no depende de la energía)"


class Referencias(QWidget):

    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self._username_solicitante = getattr(user_id, "_usuario", None)
        self._es_jefe = es_fisico_jefe(self._username_solicitante)
        self._setup_ui()
        self._cargar_tabla()
        self._cargar_historial()

    # ── UI ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        titulo = QLabel("Referencias y líneas base")
        titulo.setStyleSheet("font-size: 20px; font-weight: bold; color: #0a0a0a;")
        root.addWidget(titulo)

        if not self._es_jefe:
            self.banda_solo_lectura = QLabel(TEXTO_SOLO_LECTURA)
            self.banda_solo_lectura.setObjectName("banda_solo_lectura")
            self.banda_solo_lectura.setWordWrap(True)
            root.addWidget(self.banda_solo_lectura)

        self._tabla = self._crear_tabla(COLUMNAS)
        self._tabla.cellClicked.connect(self._on_click_fila)
        root.addWidget(QLabel("Referencias vigentes"))
        root.addWidget(self._tabla, stretch=2)

        root.addLayout(self._crear_formulario())

        self.lbl_vigente = QLabel("")
        root.addWidget(self.lbl_vigente)
        root.addWidget(QLabel("Historial de la referencia elegida"))
        self._tabla_historial = self._crear_tabla(COLUMNAS_HISTORIAL)
        root.addWidget(self._tabla_historial, stretch=1)

    @staticmethod
    def _crear_tabla(columnas):
        tabla = QTableWidget()
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla.setSelectionBehavior(QTableWidget.SelectRows)
        tabla.setAlternatingRowColors(True)
        tabla.verticalHeader().setVisible(False)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabla.setColumnCount(len(columnas))
        tabla.setHorizontalHeaderLabels(columnas)
        return tabla

    def _crear_formulario(self):
        form = QFormLayout()

        self.cb_equipo = QComboBox()
        self.cb_equipo.addItems(list(ENERGIAS_POR_EQUIPO))
        self.cb_equipo.currentIndexChanged.connect(self._on_cambio_equipo)

        self.cb_magnitud = QComboBox()
        for clave, texto in MAGNITUDES:
            self.cb_magnitud.addItem(texto, clave)
        self.cb_magnitud.currentIndexChanged.connect(self._on_cambio_clave)

        self.cb_energia = QComboBox()
        self.cb_energia.currentIndexChanged.connect(self._on_cambio_clave)
        self._llenar_energias()

        self.in_valor = QLineEdit()
        self.in_valor.setPlaceholderText("Número mayor que cero, p. ej. 0.627")
        self.in_unidad = QLineEdit()
        self.in_unidad.setPlaceholderText("Opcional")
        self.in_fuente = QLineEdit()
        self.in_fuente.setPlaceholderText(
            "Obligatoria: de dónde sale el número (p. ej. medición de puesta en servicio)")
        self.in_observaciones = QLineEdit()
        self.in_observaciones.setPlaceholderText(
            "Obligatoria: qué cambió y por qué")

        form.addRow("Equipo:", self.cb_equipo)
        form.addRow("Magnitud:", self.cb_magnitud)
        form.addRow("Energía:", self.cb_energia)
        form.addRow("Valor nuevo:", self.in_valor)
        form.addRow("Unidad:", self.in_unidad)
        form.addRow("Fuente:", self.in_fuente)
        form.addRow("Observaciones:", self.in_observaciones)

        self.btn_fijar = QPushButton("Fijar referencia")
        self.btn_fijar.clicked.connect(self._on_fijar)
        fila_boton = QHBoxLayout()
        fila_boton.addStretch()
        fila_boton.addWidget(self.btn_fijar)
        form.addRow(fila_boton)

        self._controles_edicion = (
            self.cb_equipo, self.cb_magnitud, self.cb_energia, self.in_valor,
            self.in_unidad, self.in_fuente, self.in_observaciones, self.btn_fijar)
        if not self._es_jefe:
            for control in self._controles_edicion:
                control.setEnabled(False)
        return form

    def _llenar_energias(self):
        equipo = self.cb_equipo.currentText()
        self.cb_energia.blockSignals(True)
        self.cb_energia.clear()
        for energia in ENERGIAS_POR_EQUIPO.get(equipo, ()):
            self.cb_energia.addItem(energia, energia)
        self.cb_energia.blockSignals(False)

    # ── Datos ────────────────────────────────────────────────────────────

    def _clave_elegida(self):
        return (self.cb_equipo.currentText(),
                self.cb_magnitud.currentData(),
                self.cb_energia.currentData() or "")

    def _cargar_tabla(self):
        vigentes = _datos.listar_vigentes()
        self._tabla.setRowCount(0)
        for fila in vigentes:
            idx = self._tabla.rowCount()
            self._tabla.insertRow(idx)
            valores = [
                fila["equipo"], fila["magnitud"], _texto_energia(fila["energia"]),
                f"{fila['valor']:g}", fila["unidad"] or "", fila["fuente"] or "",
                fila["observaciones"] or "", fila["fijada_por"] or "",
                fila["fecha"] or "",
            ]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if col == 0:
                    item.setData(Qt.UserRole, (fila["equipo"], fila["magnitud"],
                                               fila["energia"] or ""))
                self._tabla.setItem(idx, col, item)

    def _cargar_historial(self):
        equipo, magnitud, energia = self._clave_elegida()
        filas = _datos.historial(equipo, magnitud, energia) if magnitud else []
        self._tabla_historial.setRowCount(0)
        vigente = None
        for fila in filas:
            es_vigente = fila["activo"] in (None, 1)
            if es_vigente:
                vigente = fila
            idx = self._tabla_historial.rowCount()
            self._tabla_historial.insertRow(idx)
            valores = [
                "Vigente" if es_vigente else "Reemplazada",
                f"{fila['valor']:g}", fila["fuente"] or "",
                fila["observaciones"] or "", fila["fijada_por"] or "",
                fila["fecha"] or "",
            ]
            for col, valor in enumerate(valores):
                self._tabla_historial.setItem(idx, col, QTableWidgetItem(str(valor)))
        if vigente is not None:
            self.lbl_vigente.setText(
                f"Valor vigente: {vigente['valor']:g} (fijado por "
                f"{vigente['fijada_por'] or 'sin dato'}, {vigente['fecha'] or 'sin fecha'})")
        else:
            self.lbl_vigente.setText(
                "Sin referencia fijada para esta combinación: el mensual usa "
                "su valor de respaldo.")

    # ── Eventos ──────────────────────────────────────────────────────────

    def _on_cambio_equipo(self, _indice):
        self._llenar_energias()
        self._cargar_historial()

    def _on_cambio_clave(self, _indice):
        self._cargar_historial()

    def _on_click_fila(self, fila, _columna):
        item = self._tabla.item(fila, 0)
        if item is None:
            return
        equipo, magnitud, energia = item.data(Qt.UserRole)
        # Se posicionan los combos SIN disparar recargas intermedias: una
        # sola carga del historial al final.
        for combo in (self.cb_equipo, self.cb_magnitud, self.cb_energia):
            combo.blockSignals(True)
        self.cb_equipo.setCurrentText(equipo)
        self._llenar_energias()
        self.cb_magnitud.setCurrentIndex(max(0, self.cb_magnitud.findData(magnitud)))
        self.cb_energia.setCurrentIndex(max(0, self.cb_energia.findData(energia)))
        for combo in (self.cb_equipo, self.cb_magnitud, self.cb_energia):
            combo.blockSignals(False)
        self._cargar_historial()

    def _on_fijar(self):
        equipo, magnitud, energia = self._clave_elegida()
        valor_texto = self.in_valor.text().strip().replace(",", ".")
        fuente = self.in_fuente.text().strip()
        observaciones = self.in_observaciones.text().strip()
        unidad = self.in_unidad.text().strip() or None

        if QMessageBox.question(
                self, "Fijar referencia",
                f"¿Fijar {magnitud} de {equipo} ({_texto_energia(energia)}) "
                f"en {valor_texto or 'un valor vacío'}? Los controles NUEVOS "
                "usarán este valor; los ya guardados conservan el que tenían "
                "cuando se firmaron.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        exito, motivo = _datos.fijar_referencia(
            equipo, magnitud, energia, valor_texto, fuente, observaciones,
            self._username_solicitante, unidad=unidad)
        if not exito:
            QMessageBox.warning(
                self, "No se pudo fijar la referencia",
                MENSAJES_RECHAZO.get(motivo, "La operación fue rechazada."))
            return

        QMessageBox.information(
            self, "Referencia fijada",
            f"Se fijó {magnitud} de {equipo} ({_texto_energia(energia)}) en "
            f"{valor_texto}. Quedó registrado quién la cambió y cuándo.")
        self.in_valor.clear()
        self.in_unidad.clear()
        self.in_fuente.clear()
        self.in_observaciones.clear()
        self._cargar_tabla()
        self._cargar_historial()
