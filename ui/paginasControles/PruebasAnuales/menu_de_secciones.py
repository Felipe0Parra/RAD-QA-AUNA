"""Menú desplegable para las secciones largas de una página anual, con un circulito por tabla (guardada o no)."""
from PyQt5.QtCore import QObject, QPoint, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygon
from PyQt5.QtWidgets import (QAbstractButton, QAction, QLayout, QMenu, QPushButton, QStyledItemDelegate, QVBoxLayout,
                             QWidget)

# Nombre que Qt da a los botones de título de una QToolBox
BOTON_DE_TITULO = "qt_toolbox_toolboxbutton"
VERDE = QColor(46, 160, 67)
ROJO = QColor(200, 40, 40)
COLOR_FLECHITA = QColor(60, 60, 60)
ESTILO_MENU = ("QMenu { background:#ececec; border:1px solid #9a9a9a; color:black; } "
               "QMenu::item { padding:6px 30px 6px 28px; } QMenu::item:selected { background:#cfcfcf; color:black; }")
SEPARADOR = " - "
TEXTO_SIN_ELEGIR = "Ninguna tabla elegida"
TEXTO_CAMBIAR = "▾ cambiar tabla"
AVISO_GUARDADA = "Guardada"
AVISO_SIN_GUARDAR = "Sin guardar"


def circulito(guardada):
    """Un círculo verde (guardada) o rojo (sin guardar), dibujado."""
    imagen = QPixmap(14, 14)
    imagen.fill(Qt.transparent)
    pintor = QPainter(imagen)
    pintor.setRenderHint(QPainter.Antialiasing)
    pintor.setPen(Qt.NoPen)
    pintor.setBrush(VERDE if guardada else ROJO)
    pintor.drawEllipse(2, 2, 10, 10)
    pintor.end()
    return QIcon(imagen)


def flechita():
    """Un triángulo hacia abajo junto al título: la sección abre un menú."""
    imagen = QPixmap(14, 14)
    imagen.fill(Qt.transparent)
    pintor = QPainter(imagen)
    pintor.setRenderHint(QPainter.Antialiasing)
    pintor.setPen(Qt.NoPen)
    pintor.setBrush(COLOR_FLECHITA)
    pintor.drawPolygon(QPolygon([QPoint(2, 4), QPoint(12, 4), QPoint(7, 10)]))
    pintor.end()
    return QIcon(imagen)


def compactar(pagina):
    """Sin márgenes en los layouts de la página: el alto que queda es para las tablas. Devuelve los que tenían."""
    capas = [c for c in [pagina.layout()] + pagina.findChildren(QLayout) if c is not None]
    antes = [(capa, capa.contentsMargins()) for capa in capas]
    for capa in capas:
        capa.setContentsMargins(0, 0, 0, 0)
    return antes


def botones_de_titulo(caja):
    """Los botones de título propios de `caja` (no los de una caja anidada), en su orden."""
    return [b for b in caja.findChildren(QAbstractButton, BOTON_DE_TITULO, Qt.FindDirectChildrenOnly)]


def texto_de_celda(tabla, fila, columna):
    """El texto de una celda como lo compara el circulito: vacío si no hay nada, sin espacios en los bordes."""
    item = tabla.item(fila, columna)
    return item.text().strip() if item is not None else ""


class Elemento:
    """Lo que lleva a una tabla (o a las tablas que se suben juntas) y si está guardada sin editar."""

    def __init__(self, titulo, tablas, calculadas=(), de_la_base=False):
        self.titulo = titulo
        self.tablas = list(tablas)
        self.calculadas = frozenset(calculadas)
        self.a_mano = set()
        self._guardada = self.huella() if de_la_base else None

    def huella(self):
        """El texto de cada celda editable (todas salvo la primera columna), por (tabla, fila, columna)."""
        return {(k, f, c): texto_de_celda(t, f, c) for k, t in enumerate(self.tablas)
                for f in range(t.rowCount()) for c in range(1, t.columnCount())}

    def _cuenta(self, celda):
        """Una celda que calcula la app solo cuenta si el físico la corrigió a mano."""
        return celda[2] not in self.calculadas or celda in self.a_mano

    def guardada(self):
        if self._guardada is None:
            return False
        ahora = self.huella()
        return all(ahora.get(celda) == texto for celda, texto in self._guardada.items() if self._cuenta(celda))

    def editada_a_mano(self, tabla, fila, columna):
        """El físico cambió con el editor el texto de una celda: cuenta aunque la calcule la app."""
        self.a_mano.add((self.tablas.index(tabla), fila, columna))

    def marcar_subida(self):
        self._guardada = self.huella()


class SeccionConMenu(QObject):
    """Una sección de la caja principal que se navega con un menú en lugar de su cascada.
    Si no se puede armar, deja la caja y la sección como estaban y el error sube."""

    def __init__(self, caja, subcaja, titulo, elementos, agrupar):
        super().__init__(caja)
        self.caja, self.subcaja, self.titulo, self.agrupar = caja, subcaja, titulo, agrupar
        self.elementos = list(elementos)
        assert len(self.elementos) == subcaja.count(), "un elemento por cada tabla de la sección"
        self.elegido = None
        self.menu = None
        self.contenedor = QWidget()
        margenes = []
        try:
            self._armar(caja, subcaja, titulo, margenes)
        except Exception:
            self._deshacer(margenes)
            raise

    def _armar(self, caja, subcaja, titulo, margenes):
        """Pone en la caja la barra y la sección; anota en `margenes` los que quita."""
        capa = QVBoxLayout(self.contenedor)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(2)
        self.barra = QPushButton()
        self.barra.setObjectName("barra_de_tabla")
        self.barra.setStyleSheet("text-align:left; padding:4px; font-weight:bold;")
        self.barra.clicked.connect(self.abrir)
        capa.addWidget(self.barra)
        capa.addWidget(subcaja, 1)
        for boton in botones_de_titulo(subcaja):
            boton.hide()
        for k in range(subcaja.count()):
            margenes += compactar(subcaja.widget(k))
        subcaja.hide()
        caja.addItem(self.contenedor, titulo)
        caja.setItemIcon(caja.indexOf(self.contenedor), flechita())
        self.boton.clicked.connect(self.abrir)
        self._refrescar_barra()
        for elemento in self.elementos:
            for tabla in elemento.tablas:
                tabla.itemChanged.connect(self._refrescar_barra)
                self._escuchar_el_editor(elemento, tabla)

    def _deshacer(self, margenes):
        """La caja y la sección vuelven a como estaban, para que quede en cascada."""
        indice = self.caja.indexOf(self.contenedor)
        if indice >= 0:
            self.caja.removeItem(indice)
        self.subcaja.setParent(None)
        for boton in botones_de_titulo(self.subcaja):
            boton.show()
        for capa, antes in margenes:
            capa.setContentsMargins(antes)

    def _escuchar_el_editor(self, elemento, tabla):
        """Anota la celda cuyo texto cambia al confirmar su editor (Enter, Tab, flechas, clic fuera)."""
        delegado = QStyledItemDelegate(tabla)
        antes = []

        def leer(_):
            celda = tabla.currentIndex()
            antes.append((celda.row(), celda.column(), texto_de_celda(tabla, celda.row(), celda.column())))

        def comparar(_):
            fila, columna, texto = antes.pop()
            if texto_de_celda(tabla, fila, columna) != texto:
                self._a_mano(elemento, tabla, fila, columna)
        # Qt llama a las conexiones en su orden: la tabla conecta la que escribe en setItemDelegate, entre estas dos
        delegado.commitData.connect(leer)
        tabla.setItemDelegate(delegado)
        delegado.commitData.connect(comparar)

    @property
    def boton(self):
        """El botón de título de la sección, buscado cada vez: lo crea Qt y su envoltorio no se guarda."""
        return [b for b in botones_de_titulo(self.caja) if b.text() == self.titulo][-1]

    def _a_mano(self, elemento, tabla, fila, columna):
        elemento.editada_a_mano(tabla, fila, columna)
        self._refrescar_barra()

    def estado(self, indice):
        return "verde" if self.elementos[indice].guardada() else "rojo"

    def _accion(self, menu, indice, texto):
        guardada = self.elementos[indice].guardada()
        # Acciones y submenús creados desde Python: así su envoltorio no sobrevive a su destrucción
        accion = QAction(circulito(guardada), texto, menu)
        menu.addAction(accion)
        accion.setToolTip(AVISO_GUARDADA if guardada else AVISO_SIN_GUARDAR)
        accion.triggered.connect(lambda _=False, i=indice: self.elegir(i))
        return accion

    def construir_menu(self):
        """El menú con los circulitos de este momento; los grupos llevan su flechita y abren sus tablas al lado."""
        if self.menu is not None:
            self.menu.hide()
            self.menu.deleteLater()
        self.menu = QMenu(self.contenedor)
        self.menu.setStyleSheet(ESTILO_MENU)
        self.menu.setToolTipsVisible(True)
        grupos = {}
        for i in range(self.subcaja.count()):
            grupo, _, hoja = self.subcaja.itemText(i).rpartition(SEPARADOR)
            if not self.agrupar:
                self._accion(self.menu, i, hoja or self.subcaja.itemText(i))
                continue
            if grupo not in grupos:
                grupos[grupo] = QMenu(grupo, self.menu)
                self.menu.addMenu(grupos[grupo])
                grupos[grupo].setStyleSheet(ESTILO_MENU)
                grupos[grupo].setToolTipsVisible(True)
            self._accion(grupos[grupo], i, hoja)
        return self.menu

    def abrir(self):
        """Abre el menú debajo del título de la sección (popup: nunca modal)."""
        menu = self.construir_menu()
        menu.popup(self.boton.mapToGlobal(QPoint(0, self.boton.height())))

    def elegir(self, indice):
        """Muestra solo la tabla elegida, con todo el alto de la sección, y cierra el menú."""
        self.elegido = indice
        self.subcaja.setCurrentIndex(indice)
        self.subcaja.show()
        if self.menu is not None:
            for submenu in self.menu.findChildren(QMenu):
                submenu.hide()
            self.menu.hide()
        self._refrescar_barra()

    def marcar_subida(self, tabla):
        """Un «Subir» que salió bien: el elemento de esa tabla queda guardado."""
        for elemento in self.elementos:
            if tabla in elemento.tablas:
                elemento.marcar_subida()
        self._refrescar_barra()

    def _refrescar_barra(self, *_):
        if self.elegido is None:
            self.barra.setText(f"{TEXTO_SIN_ELEGIR}        {TEXTO_CAMBIAR}")
            self.barra.setIcon(QIcon())
            return
        guardada = self.elementos[self.elegido].guardada()
        self.barra.setText(f"{self.subcaja.itemText(self.elegido)}        {TEXTO_CAMBIAR}")
        self.barra.setIcon(circulito(guardada))
        self.barra.setToolTip(AVISO_GUARDADA if guardada else AVISO_SIN_GUARDAR)
