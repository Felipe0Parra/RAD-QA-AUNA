# ui/paginasGuia/usuarios.py
"""U5 (PLAN_PESTANA_USUARIOS_02-09.md): pestaña de usuarios registrados.

Patrón calcado de `ui/paginasGuia/visor_anulados.py` (LR6): datos en
`services/gestion_usuarios.py` (U3/U4/U4-bis), UI sin SQL propio. La lista
es legítima para cualquier físico (son sus compañeros de turno) -- lo que
se restringe son las ACCIONES, nunca la visibilidad de quién tiene cuenta.

La UI no decide el permiso: pregunta a `es_fisico_jefe` solo para PINTAR
(mostrar u ocultar los botones); el servicio vuelve a preguntarlo para
ACTUAR. Si solo se ocultara el botón, el control sería cosmético -- ver
U3/U7.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from services import gestion_usuarios as _datos
from services.permisos import es_fisico_jefe

COLUMNAS = ["Usuario", "Nombre completo", "Cargo", "Rol de sistema", "Estado"]


class _DialogoAgregarUsuario(QDialog):
    """Alta -- los campos que `crear_usuario` (U4) necesita para delegar en
    `UsuarioData.add_user`. `firma` se deja vacía a propósito: cargar una
    imagen de firma real desde aquí es una funcionalidad aparte, no pedida
    por el físico en este plan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar usuario")
        layout = QFormLayout(self)

        self.in_user = QLineEdit()
        self.in_fullname = QLineEdit()
        self.in_password = QLineEdit()
        self.in_password.setEchoMode(QLineEdit.Password)
        self.in_idreal = QLineEdit()
        self.in_role = QComboBox()
        self.in_role.addItems(["Físico Médico", "Medicos"])

        layout.addRow("Usuario:", self.in_user)
        layout.addRow("Nombre completo:", self.in_fullname)
        layout.addRow("Contraseña:", self.in_password)
        layout.addRow("Identificación:", self.in_idreal)
        layout.addRow("Cargo:", self.in_role)

        botones = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_aceptar = QPushButton("Agregar")
        btn_aceptar.clicked.connect(self.accept)
        botones.addWidget(btn_cancelar)
        botones.addWidget(btn_aceptar)
        layout.addRow(botones)

    def datos(self):
        return {
            "user": self.in_user.text().strip(),
            "fullname": self.in_fullname.text().strip(),
            "password": self.in_password.text(),
            "idreal": self.in_idreal.text().strip(),
            "role": self.in_role.currentText(),
        }


class Usuarios(QWidget):

    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self._username_solicitante = getattr(user_id, "_usuario", None)
        self._es_jefe = es_fisico_jefe(self._username_solicitante)
        self._fila_seleccionada = None  # (user, fullname, active)
        self._setup_ui()
        self._cargar_tabla()

    # ── UI ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        titulo = QLabel("Usuarios registrados")
        titulo.setStyleSheet("font-size: 20px; font-weight: bold; color: #0a0a0a;")
        root.addWidget(titulo)

        if self._es_jefe:
            root.addLayout(self._crear_barra_acciones())
        else:
            root.addWidget(self._crear_banda_solo_lectura())

        self._tabla = QTableWidget()
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla.setColumnCount(len(COLUMNAS))
        self._tabla.setHorizontalHeaderLabels(COLUMNAS)
        if self._es_jefe:
            self._tabla.cellClicked.connect(self._on_click_fila)
        root.addWidget(self._tabla, stretch=1)

    def _crear_barra_acciones(self):
        acciones = QHBoxLayout()
        self.btn_agregar = QPushButton("Agregar usuario")
        self.btn_agregar.clicked.connect(self._on_agregar)
        acciones.addWidget(self.btn_agregar)

        self.btn_baja = QPushButton("Dar de baja")
        self.btn_baja.setEnabled(False)
        self.btn_baja.clicked.connect(self._on_dar_de_baja)
        acciones.addWidget(self.btn_baja)

        self.btn_reactivar = QPushButton("Reactivar")
        self.btn_reactivar.setEnabled(False)
        self.btn_reactivar.clicked.connect(self._on_reactivar)
        acciones.addWidget(self.btn_reactivar)

        self.btn_cambiar_rol = QPushButton("Cambiar rol")
        self.btn_cambiar_rol.setEnabled(False)
        self.btn_cambiar_rol.clicked.connect(self._on_cambiar_rol)
        acciones.addWidget(self.btn_cambiar_rol)

        acciones.addStretch()
        return acciones

    def _crear_banda_solo_lectura(self):
        banda = QWidget()
        banda.setObjectName("banda_solo_lectura")
        layout = QHBoxLayout(banda)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.addWidget(QLabel(
            "ⓘ Solo el físico médico en jefe puede agregar o dar de baja usuarios."))
        return banda

    def _crear_pill_estado(self, activo):
        """Mismo patrón que `visor_anulados.py::_crear_pill_estado` --
        reusa la convención `QLabel[valor="1"/"0"]` de `resources/
        estilo.qss` (sin símbolos, DA-18)."""
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(6, 2, 6, 2)
        lbl = QLabel("Activo" if activo else "Inactivo")
        lbl.setProperty("valor", "1" if activo else "0")
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(lbl)
        layout.addStretch()
        contenedor.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return contenedor

    # ── Datos ────────────────────────────────────────────────────────────

    def _cargar_tabla(self):
        usuarios = _datos.listar_usuarios()
        self._tabla.setSortingEnabled(False)
        self._tabla.setRowCount(0)

        for fila in usuarios:
            idx = self._tabla.rowCount()
            self._tabla.insertRow(idx)
            activo = bool(fila["active"])
            valores = [
                fila["user"], fila["fullname"], fila["role"] or "",
                fila["rol_sistema"] or "",
            ]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if col == 0:
                    item.setData(Qt.UserRole, fila["user"])
                    item.setData(Qt.UserRole + 1, fila["fullname"])
                    item.setData(Qt.UserRole + 2, activo)
                if not activo:
                    # Atenuado, nunca oculto -- si desaparecieran, el jefe
                    # no podría reactivarlos ni saber que existen.
                    item.setForeground(QColor("#9aa3ad"))
                self._tabla.setItem(idx, col, item)

            self._tabla.setItem(idx, len(COLUMNAS) - 1, QTableWidgetItem())
            self._tabla.setCellWidget(
                idx, len(COLUMNAS) - 1, self._crear_pill_estado(activo))

        if self._es_jefe:
            self._actualizar_botones_seleccion()

    # ── Eventos ──────────────────────────────────────────────────────────

    def _on_click_fila(self, fila, _columna):
        item = self._tabla.item(fila, 0)
        if item is None:
            return
        self._fila_seleccionada = (
            item.data(Qt.UserRole), item.data(Qt.UserRole + 1),
            item.data(Qt.UserRole + 2))
        self._actualizar_botones_seleccion()

    def _actualizar_botones_seleccion(self):
        hay_seleccion = self._fila_seleccionada is not None
        activo = hay_seleccion and self._fila_seleccionada[2]
        self.btn_baja.setEnabled(hay_seleccion and activo)
        self.btn_reactivar.setEnabled(hay_seleccion and not activo)
        self.btn_cambiar_rol.setEnabled(hay_seleccion)

    def _on_agregar(self):
        dialogo = _DialogoAgregarUsuario(self)
        if dialogo.exec_() != QDialog.Accepted:
            return
        datos = dialogo.datos()
        exito, motivo = _datos.crear_usuario(datos, self._username_solicitante)
        if exito:
            QMessageBox.information(
                self, "Usuario agregado",
                f"Se agregó a {datos['fullname']} ({datos['user']}).")
            self._cargar_tabla()
            return
        mensajes = {
            _datos.MOTIVO_SIN_PERMISO: "No tiene permiso para agregar usuarios.",
            _datos.MOTIVO_FULLNAME_VACIO: "El nombre completo no puede quedar vacío.",
            _datos.MOTIVO_USUARIO_DUPLICADO: f"El usuario '{datos['user']}' ya existe.",
            _datos.MOTIVO_ERROR_BD: "No se pudo guardar por un error de base de datos.",
        }
        QMessageBox.warning(self, "No se pudo agregar",
                             mensajes.get(motivo, "No se pudo agregar el usuario."))

    def _on_dar_de_baja(self):
        if self._fila_seleccionada is None:
            return
        user, fullname, _activo = self._fila_seleccionada
        if QMessageBox.question(
                self, "Dar de baja",
                f"¿Dar de baja a {fullname} ({user})? Su historial de "
                "controles se conserva intacto.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if _datos.dar_de_baja(user, self._username_solicitante):
            self._cargar_tabla()
        else:
            QMessageBox.warning(
                self, "No se pudo dar de baja",
                "La operación fue rechazada -- puede que intente darse de "
                "baja a sí mismo o dejar el sistema sin nadie que "
                "administre usuarios.")

    def _on_reactivar(self):
        if self._fila_seleccionada is None:
            return
        user, fullname, _activo = self._fila_seleccionada
        if QMessageBox.question(
                self, "Reactivar",
                f"¿Reactivar a {fullname} ({user})? Su historial de "
                "controles se conserva intacto.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if _datos.reactivar(user, self._username_solicitante):
            self._cargar_tabla()
        else:
            QMessageBox.warning(self, "No se pudo reactivar",
                                 "La operación fue rechazada.")

    def _on_cambiar_rol(self):
        if self._fila_seleccionada is None:
            return
        user, fullname, _activo = self._fila_seleccionada
        rol_actual = next(
            (f["rol_sistema"] for f in _datos.listar_usuarios() if f["user"] == user),
            None)
        opciones = sorted(_datos.ROLES_ASIGNABLES_DESDE_UI)
        indice_actual = opciones.index(rol_actual) if rol_actual in opciones else 0
        from PyQt5.QtWidgets import QInputDialog
        rol_nuevo, ok = QInputDialog.getItem(
            self, "Cambiar rol",
            f"Nuevo rol de sistema para {fullname} ({user}):",
            opciones, indice_actual, editable=False)
        if not ok or rol_nuevo == rol_actual:
            return
        if QMessageBox.question(
                self, "Confirmar cambio de rol",
                f"{fullname} pasará de '{rol_actual}' a '{rol_nuevo}'. "
                "¿Continuar?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if _datos.cambiar_rol_sistema(user, rol_nuevo, self._username_solicitante):
            self._cargar_tabla()
        else:
            QMessageBox.warning(
                self, "No se pudo cambiar el rol",
                "La operación fue rechazada -- puede dejar el sistema sin "
                "nadie que administre usuarios.")
