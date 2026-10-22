"""E.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-83 a DA-86, PD1): la ventana del análisis mensual de aceleradores, `VentanaPlacaMensual(ref, equipo, usuario, parent)`.

El físico abre la película del control (el recorte o la página completa del escáner), marca los cinco puntos del campo luminoso (las cuatro esquinas y el retículo, en cualquier orden) y ve el análisis en cinco
pestañas, «lo más parecido a braqui» (la posición inicial): la imagen con el recuadro del campo luminoso y, al lado, los perfiles del gris con la tabla de sus desfases; las tres capas acondicionadas; los
perfiles de cada capa con sus FWHM; los barridos; la cuadratura. Con la capa que elige en el menú «Capa reportada» (rojo, verde o azul) guarda los datos finales del análisis (D.1); al abrir un control con
análisis guardado, la ventana carga la imagen y los puntos, recalcula y, si lo recalculado difiere de lo guardado, lo dice (DD3).

SIN SQL y SIN cv2: todo lo que se guarda y se lee pasa por el servicio (`services/placa_mensual.py`, la única puerta a la tabla) y todo lo que se mide por el motor (`analisisImagenes/pelicula.py` y
`analisisImagenes/placa_mensual.py`); la ventana solo compone. Los dibujos y los textos son funciones puras de `analisisImagenes/dibujo_placa_mensual.py` (se prueban sin Qt).

LA REGLA DE «GUARDAR» ES DEL SERVICIO (D.1b, decisión del físico del 20-10-2026: «que se rechace el guardado de la capa que es no medible con el comentario de que es no medible por cualquier motivo»). La ventana
NO tiene otra: ningún `estado == "ok"` propio decide «Guardar»; importa el servicio como módulo y llama a `svc.motivo_para_no_guardar(resultado, capa)`, que da None si se puede guardar y, si no, el texto EXACTO con
que `guardar` lo rechazaría. UNA función de la ventana (`_regla_de_guardar`) da a la vez el habilitado del botón y el texto de la línea que dice por qué no; la llaman el final de cada análisis, el cambio de
«Capa reportada» (que NO recalcula: la regla lee un estado), el de «Piso» y el sexto clic (que SÍ recalculan) y quien mueva el menú con las señales bloqueadas (`_poner_capa`); `_al_guardar` la vuelve a consultar. Hay
otra función con el mismo nombre en `analisisImagenes/dibujo_posicion_inicial.py` (la de braqui, con un argumento): esta ventana no la importa ni la copia.

Lo que la ventana ofrece y lo que cambia un número (PD1: nada escondido): se ve, se guarda y se imprime. Los únicos controles que cambian algo son la imagen, los clics, «Marcar película sin irradiar» (el sexto clic),
el menú «Piso» y «Película virgen...» (que cambian el piso y, con él, los números: por eso el piso se guarda con cada análisis y el PDF lo imprime) y el menú «Capa reportada», que NO cambia ninguna medida, solo
cuál se reporta. Con un análisis guardado a la vista (B7-C1) la capa que dice la pantalla es la que ese registro GUARDÓ y los dos menús quedan fijos (como «Guardar»): para reportar otra capa o tomar otro piso, «Recalcular».

Memoria. La película se lee de los bytes cuando hace falta y NO se retiene tras el análisis (una página del escáner, 6600 x 5100, son 135 MB leída y 540 MB con sus cuatro capas en flotante): la ventana guarda los
bytes del archivo, la imagen para mostrar en RGB uint8 con `nearest` (101 MB; un gris 2D con mapa de color pedía 2 GB) y el resultado, cuya película girada es la RECORTADA a la película (nunca la página).

Ningún manejador deja escapar una excepción (`_protegido`) y ningún diálogo se abre con el cursor de espera puesto."""
import copy
import dataclasses
import functools
import gc
import os
import traceback
from datetime import date

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
                             QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from analisisImagenes import dibujo_placa_mensual as dibujo
from analisisImagenes import pelicula as pel
from analisisImagenes import placa_mensual as motor
from data.ManejoDatos import conection
from resources.utils.matplotlib_lazy import get_matplotlib_components
from services import audit_minimo
from services import placa_mensual as svc

DECIMALES_CLIC = 3                     # los clics se guardan redondeados a 3 decimales: los `MouseEvent` reales traen ruido de 1e-13
PESTANA_IMAGEN, PESTANA_CAPAS, PESTANA_PERFILES, PESTANA_BARRIDOS, PESTANA_CUADRATURA = range(5)
NOMBRES_DE_LAS_PESTANAS = ("Imagen", "Capas", "Perfiles por capa", "Barridos", "Cuadratura")
SIN_IMAGEN = "Ninguna imagen"
TEXTO_ANALIZANDO = "Analizando la imagen..."
FILTRO_IMAGENES = "Imágenes (*.jpg *.jpeg *.JPG *.JPEG *.png *.PNG *.tif *.tiff *.TIF *.TIFF)"
# el alto mínimo de cada lienzo con dibujos, en píxeles: por debajo de él el lienzo se DESPLAZA dentro de su área en vez de aplastar los ejes
ALTO_MINIMO_DEL_LIENZO = {"imagen": 300, "perfiles_del_gris": 420, "capas": 300, "perfiles": 780, "barridos": 480, "cuadratura": 380}
ALTO_DE_LA_FILA = 21                   # alto de cada fila de las tablas, en píxeles
TAMANO_DE_LETRA_DE_LAS_LINEAS = 9      # puntos: las lineas de informacion y la de la regla (algunas miden de 250 a 390 caracteres) ocupan menos alto que con la letra de los botones
ALTO_DEL_PIE = 62
TAMANO_DE_LA_VENTANA = (1380, 880)
PARTES_DEL_DIVISOR = {"imagen": (5, 3), "perfiles": (3, 1), "barridos": (3, 1)}     # el alto de cada pestaña con tabla se reparte (gráfica, tabla) así; el físico puede mover el divisor
FILAS_MINIMAS_DE_UNA_TABLA = 4         # una tabla nunca se ve con menos de estas filas (más su cabecera): el divisor no la deja más baja
TEXTO_PISO_AUTOMATICO = "Automático (esquinas)"
TEXTO_PISO_PUNTO = "Punto marcado (sexto clic)"
TEXTO_PISO_SIN_VIRGEN = "Película virgen (no hay referencia)"
TEXTO_DEL_SEXTO = "Marcar película sin irradiar"
TEXTO_DE_LA_VIRGEN = "Película virgen..."
RESPUESTA_AL_REEMPLAZAR = "Ya hay un análisis guardado para este control. Guardar este lo REEMPLAZA (el anterior queda anulado, con su rastro). ¿Reemplazarlo?"
NOTA_DE_LA_CAPA = ("Capa con la que se reporta este análisis: la que se guarda y la que imprimen los PDF (rojo, verde o azul). Cambiarla no vuelve a medir nada. Con un análisis guardado o abierto "
                   "queda fija en la capa de ese análisis: para reportar otra, pulse Recalcular.")
NOTA_DEL_PISO = ("Cómo se toma el piso de la película: automático (en las cuatro esquinas), el punto marcado sobre película sin irradiar o la película virgen guardada como referencia. Cambiarlo vuelve a "
                 "medir (el piso cambia los números); se guarda y se imprime con el análisis. Con un análisis guardado o abierto queda fijo: para tomar otro piso, pulse Recalcular.")


# ----------------------------------------------------------------------------------------------------- piezas de pantalla (copias de las de la posición inicial; ver obstaculos de E.1)

def _protegido(titulo, por_defecto=None):
    """Ningún manejador de una señal o de un evento deja escapar una excepción: bajo Qt una excepción que sale de un slot aborta el proceso o se pierde en silencio, y matplotlib se traga las de sus
    manejadores. Aquí se imprime la traza y se avisa. Los cursores y los indicadores de espera ya se restauraron: el aviso sale de la envoltura, no de dentro de ella."""
    def decorador(funcion):
        @functools.wraps(funcion)
        def envoltura(self, *args, **kwargs):
            try:
                return funcion(self, *args, **kwargs)
            except Exception as error:
                traceback.print_exc()
                QMessageBox.critical(self, titulo, f"Error inesperado ({type(error).__name__}: {error}).")
                return por_defecto
        return envoltura
    return decorador


class _SelectorSinRueda(QComboBox):
    """Un menú cuya selección no cambia con la rueda del ratón si no tiene el foco: en Qt un paso de la rueda sobre un menú cerrado cambia su selección y emite `activated`, y lo que se guarda (la capa
    reportada) o lo que se mide (el piso) cambiaría al pasar por la ventana. Hacen falta DOS cosas y las dos viven aquí, para que ningún menú tenga una sin la otra: `wheelEvent` ignora la rueda si el menú no
    tiene el foco, y la política de foco es `StrongFocus` (clic o tabulador). La de un `QComboBox` es `WheelFocus`: con ella Qt le da el foco al primer paso de la rueda ANTES de entregarle el evento,
    `hasFocus()` ya es verdadero cuando llega `wheelEvent` y la protección no protege nada."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, evento):
        if self.hasFocus():
            super().wheelEvent(evento)
        else:
            evento.ignore()


def _nuevo_lienzo(mpl, alto_minimo=None):
    """(contenedor, figura, lienzo, barra): la figura NO se registra en pyplot (nunca `plt.*`), así que se libera al soltar la referencia. `alto_minimo`, en píxeles, le da al lienzo ese alto como mínimo y, si la
    ventana no se lo da, el lienzo se DESPLAZA dentro de un área (los ejes se reparten lo que sobra de lo fijo del dibujo); la barra de herramientas (lupa, desplazar, Home) queda fuera del área."""
    contenedor = QWidget()
    capa = QVBoxLayout(contenedor)
    capa.setContentsMargins(0, 0, 0, 0)
    figura = mpl["Figure"](layout="constrained")
    lienzo = mpl["FigureCanvas"](figura)
    barra = mpl["NavigationToolbar"](lienzo, contenedor)
    capa.addWidget(barra)
    if alto_minimo:
        lienzo.setMinimumHeight(alto_minimo)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setWidget(lienzo)
        capa.addWidget(area, 1)
    else:
        capa.addWidget(lienzo, 1)
    return contenedor, figura, lienzo, barra


def _apagar_barra(barra):
    """Lupa y desplazar apagadas: `zoom()` y `pan()` alternan, así que solo se llaman si están activas."""
    if barra.mode == "zoom rect":
        barra.zoom()
    elif barra.mode == "pan/zoom":
        barra.pan()


def _recuadro():
    """Un texto largo con borde y relleno, seleccionable, con ajuste de línea."""
    recuadro = QLabel()
    recuadro.setTextFormat(Qt.PlainText)
    recuadro.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    recuadro.setWordWrap(True)
    recuadro.setTextInteractionFlags(Qt.TextSelectableByMouse)
    recuadro.setStyleSheet(f"padding: 2px 4px; border: 1px solid #ccc; font-size: {TAMANO_DE_LETRA_DE_LAS_LINEAS}pt;")
    return recuadro


def _poner_texto(etiqueta, texto):
    """El texto de una etiqueta que se esconde si está vacía (una línea vacía no ocupa alto)."""
    etiqueta.setText(texto)
    etiqueta.setVisible(bool(texto))


def _nueva_tabla(columnas, alto=None):
    """Una tabla de solo lectura con esas columnas (cada una al ancho de su contenido y la última toma lo que sobra)."""
    tabla = QTableWidget(0, len(columnas))
    tabla.setHorizontalHeaderLabels(list(columnas))
    tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
    tabla.setSelectionMode(QAbstractItemView.SingleSelection)
    tabla.verticalHeader().setVisible(False)
    tabla.verticalHeader().setDefaultSectionSize(ALTO_DE_LA_FILA)
    cabecera = tabla.horizontalHeader()
    cabecera.setSectionResizeMode(QHeaderView.ResizeToContents)
    cabecera.setStretchLastSection(True)
    tabla.setWordWrap(False)
    tabla.setMinimumHeight(alto if alto else ALTO_DE_LA_FILA * (FILAS_MINIMAS_DE_UNA_TABLA + 1) + 6)
    return tabla


def _divisor(arriba, abajo, partes):
    """Un divisor vertical entre la gráfica (arriba) y su tabla (abajo): se reparten el alto en `partes` (una entrada de `PARTES_DEL_DIVISOR`) y el físico puede moverlo."""
    divisor = QSplitter(Qt.Vertical)
    divisor.addWidget(arriba)
    divisor.addWidget(abajo)
    divisor.setStretchFactor(0, partes[0])
    divisor.setStretchFactor(1, partes[1])
    divisor.setChildrenCollapsible(False)
    divisor.setSizes([parte * 1000 for parte in partes])       # Qt las escala al alto que haya
    return divisor


def _llenar_tabla(tabla, filas):
    """Las filas (tuplas de texto) en la tabla; cada celda con su texto completo como ayuda (las largas se cortan)."""
    tabla.setRowCount(len(filas))
    for i, fila in enumerate(filas):
        for j, texto in enumerate(fila):
            item = QTableWidgetItem(texto)
            item.setToolTip(texto)
            tabla.setItem(i, j, item)


def _tamano_inicial():
    """El tamaño con que se abre la ventana: `TAMANO_DE_LA_VENTANA`, sin pasar del 95 % del ancho ni del 92 % del alto de la pantalla (en una de 1366 x 768 la ventana entera se ve)."""
    ancho, alto = TAMANO_DE_LA_VENTANA
    try:
        pantalla = QApplication.primaryScreen().availableGeometry()
        return min(ancho, int(pantalla.width() * 0.95)), min(alto, int(pantalla.height() * 0.92))
    except AttributeError:
        return ancho, alto


def _nombre_del_usuario(usuario):
    """El nombre con que se audita lo que se guarda: el texto que se da (`usuario_actual` del formulario) o el nombre de un objeto de usuario de la sesión (`_nombre`)."""
    if isinstance(usuario, str):
        return usuario
    return getattr(usuario, "_nombre", None)


# ----------------------------------------------------------------------------------------------------- la película virgen

class DialogoPeliculaVirgen(QDialog):
    """El cuadro de «Película virgen...»: el escaneo de la película virgen con la zona que se midió dibujada, su valor por capa, cada comprobación con su cifra y su resultado en palabras, los avisos, de
    dónde salió el archivo y la orientación que el físico declara (no se mide), y «Guardar como referencia» (solo si la referencia es válida; si ya había una, pregunta con «No» por omisión). NO guarda nada
    por sí mismo: al aceptar deja `guardar_solicitado` en True y `referencia_final()` con la orientación declarada; quien lo abrió escribe el archivo y la fila de auditoría."""

    def __init__(self, referencia, datos, existente=None, parent=None):
        super().__init__(parent)
        self.referencia = referencia
        self.datos = datos
        self.existente = existente
        self.guardar_solicitado = False
        self.setWindowTitle("Película virgen")
        mpl = get_matplotlib_components()
        principal = QHBoxLayout(self)
        contenedor, self._figura, self.lienzo, self.barra = _nuevo_lienzo(mpl)
        self.eje = self._figura.add_subplot(111)
        principal.addWidget(contenedor, 3)
        derecha = QVBoxLayout()
        self.resumen = _recuadro()
        derecha.addWidget(self.resumen)
        derecha.addWidget(QLabel("Valor de la película virgen por capa"))
        self.tabla_valores = _nueva_tabla(dibujo.COLUMNAS_DE_LA_VIRGEN, 150)
        derecha.addWidget(self.tabla_valores)
        derecha.addWidget(QLabel("Comprobaciones"))
        self.tabla_pruebas = _nueva_tabla(dibujo.COLUMNAS_DE_LAS_PRUEBAS, 200)
        derecha.addWidget(self.tabla_pruebas, 1)
        self.avisos = _recuadro()
        derecha.addWidget(self.avisos)
        self.procedencia = _recuadro()
        derecha.addWidget(self.procedencia)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Orientación de la película virgen:"))
        self.selector_orientacion = _SelectorSinRueda()
        for texto in dibujo.ORIENTACIONES_DE_LA_VIRGEN:
            self.selector_orientacion.addItem(texto)
        pr = referencia.procedencia.get("orientacion_declarada")
        if pr in dibujo.ORIENTACIONES_DE_LA_VIRGEN:
            self.selector_orientacion.setCurrentIndex(dibujo.ORIENTACIONES_DE_LA_VIRGEN.index(pr))
        fila.addWidget(self.selector_orientacion, 1)
        derecha.addLayout(fila)
        botones = QHBoxLayout()
        self.boton_guardar = QPushButton("Guardar como referencia")
        self.boton_cerrar = QPushButton("Cerrar")
        botones.addWidget(self.boton_guardar)
        botones.addWidget(self.boton_cerrar)
        derecha.addLayout(botones)
        principal.addLayout(derecha, 2)
        self.boton_guardar.setEnabled(referencia.estado == "ok")
        self.boton_guardar.clicked.connect(lambda *_: self._al_guardar())
        self.boton_cerrar.clicked.connect(lambda *_: self.reject())
        self._mostrar()

    def _mostrar(self):
        r = self.referencia
        self.resumen.setText(r.descripcion())
        _llenar_tabla(self.tabla_valores, dibujo.filas_de_la_virgen(r))
        _llenar_tabla(self.tabla_pruebas, dibujo.filas_de_las_pruebas(r))
        _poner_texto(self.avisos, "Avisos: " + "; ".join(r.avisos) if r.avisos else "")
        self.procedencia.setText(dibujo.texto_de_la_procedencia(r))
        try:
            pelicula = pel.leer_pelicula(self.datos)
        except ValueError:
            return
        dibujo.dibujar_imagen(self.eje, dibujo.imagen_rgb(pelicula))
        dibujo.dibujar_zona_de_la_virgen(self.eje, r)
        manejadores, etiquetas = self.eje.get_legend_handles_labels()
        if manejadores:
            self.eje.legend(manejadores, etiquetas, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=7)
        self.lienzo.draw_idle()

    def orientacion_declarada(self):
        return self.selector_orientacion.currentText()

    def referencia_final(self):
        """La referencia con la orientación que el físico declaró en el cuadro (un dato de la procedencia: no se mide ni cambia ningún número)."""
        procedencia = {**self.referencia.procedencia, "orientacion_declarada": self.orientacion_declarada()}
        return dataclasses.replace(self.referencia, procedencia=procedencia)

    @_protegido("Película virgen")
    def _al_guardar(self):
        if self.referencia.estado != "ok":
            return
        if self.existente is not None:
            anterior = self.existente.procedencia
            if QMessageBox.question(self, "Película virgen", f"Ya hay una película virgen de referencia («{anterior.get('archivo')}», {anterior.get('fecha_escaneo') or anterior.get('fecha_calculo')}). "
                                    "¿Reemplazarla? La anterior se archiva, no se borra.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
        self.guardar_solicitado = True
        self.accept()


# ----------------------------------------------------------------------------------------------------- la ventana

class VentanaPlacaMensual(QWidget):
    """La ventana del análisis mensual. `ref`: el id del control (`controles.id`) al que pertenece el análisis. `equipo`: el nombre del equipo (solo se muestra). `usuario`: el nombre del usuario de la sesión,
    con que se audita lo que se guarda (`usuario_actual` del formulario, no el Físico 1 del control), o el objeto de usuario. `parent`: la página mensual (la ventana es hija suya con la bandera `Qt.Window`:
    se destruye con ella). Al construirse carga el análisis guardado del control, si lo tiene (`abrir_guardado`)."""

    def __init__(self, ref, equipo, usuario, parent=None):
        super().__init__(parent, Qt.Window)
        self.ref = ref
        self.equipo = equipo
        self.usuario = _nombre_del_usuario(usuario)
        self.setWindowTitle(f"Análisis de la placa del campo luminoso - {equipo}" if equipo else "Análisis de la placa del campo luminoso")
        self._referencia_virgen = None
        self._aviso_referencia = ""
        self.resize(*_tamano_inicial())
        self._construir()
        self._restablecer_estado()
        self.refrescar()
        self.abrir_guardado()

    # ----------------------------------------------------------------------------------------------------- construir

    def _construir(self):
        """Todos los widgets, una sola vez: ninguno se crea ni se destruye después (un widget que alguien vacía deja referencias muertas)."""
        mpl = get_matplotlib_components()
        principal = QVBoxLayout(self)

        fila_imagen = QHBoxLayout()
        self.boton_imagen = QPushButton("Seleccionar imagen")
        self.nombre_archivo = QLineEdit()
        self.nombre_archivo.setReadOnly(True)
        self.nombre_archivo.setFocusPolicy(Qt.NoFocus)
        self.nombre_archivo.setStyleSheet("QLineEdit { background-color: #ececec; }")
        self.boton_sexto = QPushButton(TEXTO_DEL_SEXTO)
        self.boton_sexto.setCheckable(True)
        self.boton_sexto.setToolTip("Marque con el siguiente clic un punto sobre película sin irradiar (un trozo escaneado junto a la película): con él se toma el piso. El clic nunca es uno de los cinco "
                                    "puntos del campo luminoso.")
        self.indicador = QLabel(TEXTO_ANALIZANDO)
        fila_imagen.addWidget(self.boton_imagen)
        fila_imagen.addWidget(self.nombre_archivo, 1)
        fila_imagen.addWidget(self.boton_sexto)
        fila_imagen.addWidget(self.indicador)
        principal.addLayout(fila_imagen)

        fila_controles = QHBoxLayout()
        self.etiqueta_piso_menu = QLabel("Piso:")
        self.selector_piso = _SelectorSinRueda()
        self.selector_piso.setToolTip(NOTA_DEL_PISO)
        for modo in pel.MODOS_DEL_PISO:
            self.selector_piso.addItem("", modo)
        self.etiqueta_piso_menu.setBuddy(self.selector_piso)
        self.boton_virgen = QPushButton(TEXTO_DE_LA_VIRGEN)
        self.etiqueta_capa = QLabel("Capa reportada:")
        self.selector_capa = _SelectorSinRueda()
        self.selector_capa.setToolTip(NOTA_DE_LA_CAPA)
        for capa in pel.CAPAS:
            self.selector_capa.addItem(pel.NOMBRE_DE_CAPA[capa], capa)
        self.etiqueta_capa.setBuddy(self.selector_capa)
        self.boton_recalcular = QPushButton("Recalcular")
        self.boton_limpiar = QPushButton("Limpiar")
        self.boton_guardar = QPushButton("Guardar")
        for widget in (self.etiqueta_piso_menu, self.selector_piso, self.boton_virgen, self.etiqueta_capa, self.selector_capa):
            fila_controles.addWidget(widget)
        fila_controles.addStretch(1)
        for boton in (self.boton_recalcular, self.boton_limpiar, self.boton_guardar):
            fila_controles.addWidget(boton)
        principal.addLayout(fila_controles)

        # Las líneas de información: cada una se esconde si está vacía. La línea de la REGLA (D.1b) va aparte, a todo lo ancho y con ajuste de línea (mide de 250 a 390 caracteres).
        self.linea_regla = _recuadro()
        self.linea_regla.setStyleSheet(f"padding: 3px 4px; border: 1px solid #b04040; background-color: #fbeeee; font-size: {TAMANO_DE_LETRA_DE_LAS_LINEAS}pt;")
        self.etiqueta_imagen = _recuadro()
        self.etiqueta_marcas = _recuadro()
        self.etiqueta_piso = _recuadro()
        self.etiqueta_registro = _recuadro()
        self.etiqueta_escaneo = QLabel(f"Escanear a {motor.VALORES_DE_LA_GEOMETRIA['resolucion_escaneo_dpi']:g} dpi")
        self.etiqueta_escaneo.setStyleSheet("font-weight: bold;")
        fila_datos = QHBoxLayout()
        fila_datos.addWidget(self.etiqueta_escaneo)
        fila_datos.addWidget(self.etiqueta_imagen, 1)
        principal.addWidget(self.linea_regla)
        principal.addLayout(fila_datos)
        for etiqueta in (self.etiqueta_marcas, self.etiqueta_piso, self.etiqueta_registro):
            principal.addWidget(etiqueta)

        self.pestanas = QTabWidget()
        # 1. Imagen: la imagen para marcar, al lado los dos perfiles del gris y debajo la tabla de sus desfases
        arriba = QWidget()
        fila1 = QHBoxLayout(arriba)
        fila1.setContentsMargins(0, 0, 0, 0)
        contenedor, self._fig_imagen, self.lienzo_imagen, self.barra_imagen = _nuevo_lienzo(mpl, ALTO_MINIMO_DEL_LIENZO["imagen"])
        self.eje_imagen = self._fig_imagen.add_subplot(111)
        fila1.addWidget(contenedor, 3)
        contenedor, self._fig_gris, self.lienzo_gris, self.barra_gris = _nuevo_lienzo(mpl, ALTO_MINIMO_DEL_LIENZO["perfiles_del_gris"])
        fila1.addWidget(contenedor, 2)
        self.tabla_desfases = _nueva_tabla(("Medida", "Valor"))
        self.nota_pestana1 = _recuadro()
        tab1 = QWidget()                              # la nota va FUERA del divisor: un divisor no respeta la altura de un texto con ajuste de linea y lo dibujaria encima de la tabla
        capa1 = QVBoxLayout(tab1)
        capa1.setContentsMargins(0, 0, 0, 0)
        capa1.addWidget(_divisor(arriba, self.tabla_desfases, PARTES_DEL_DIVISOR["imagen"]), 1)
        capa1.addWidget(self.nota_pestana1)
        # 2. Capas
        tab2 = QWidget()
        capa2 = QVBoxLayout(tab2)
        contenedor, self._fig_capas, self.lienzo_capas, self.barra_capas = _nuevo_lienzo(mpl, ALTO_MINIMO_DEL_LIENZO["capas"])
        capa2.addWidget(contenedor, 1)
        self.nota_pestana2 = _recuadro()
        capa2.addWidget(self.nota_pestana2)
        # 3. Perfiles por capa: los ocho perfiles y, en un panel inferior, los datos de FWHM de cada uno
        contenedor, self._fig_perfiles, self.lienzo_perfiles, self.barra_perfiles = _nuevo_lienzo(mpl, ALTO_MINIMO_DEL_LIENZO["perfiles"])
        self.tabla_perfiles = _nueva_tabla(dibujo.COLUMNAS_DE_LOS_PERFILES)
        tab3 = _divisor(contenedor, self.tabla_perfiles, PARTES_DEL_DIVISOR["perfiles"])
        # 4. Barridos
        contenedor, self._fig_barridos, self.lienzo_barridos, self.barra_barridos = _nuevo_lienzo(mpl, ALTO_MINIMO_DEL_LIENZO["barridos"])
        self.tabla_barridos = _nueva_tabla(dibujo.COLUMNAS_DE_LOS_BARRIDOS)
        tab4 = _divisor(contenedor, self.tabla_barridos, PARTES_DEL_DIVISOR["barridos"])
        # 5. Cuadratura
        tab5 = QWidget()
        capa5 = QHBoxLayout(tab5)
        contenedor, self._fig_cuadratura, self.lienzo_cuadratura, self.barra_cuadratura = _nuevo_lienzo(mpl, ALTO_MINIMO_DEL_LIENZO["cuadratura"])
        self.eje_cuadratura = self._fig_cuadratura.add_subplot(111)
        capa5.addWidget(contenedor, 2)
        self.tabla_cuadratura = _nueva_tabla(dibujo.COLUMNAS_DE_LA_CUADRATURA)
        capa5.addWidget(self.tabla_cuadratura, 2)
        for tab, nombre in zip((tab1, tab2, tab3, tab4, tab5), NOMBRES_DE_LAS_PESTANAS):
            self.pestanas.addTab(tab, nombre)
        principal.addWidget(self.pestanas, 3)

        # El pie de parámetros fijos (PD1): el valor con que se midió cada parámetro que no tiene un trazo propio, siempre a la vista (con su barra si no cabe).
        self.pie_de_parametros = QLabel()
        self.pie_de_parametros.setTextFormat(Qt.PlainText)
        self.pie_de_parametros.setWordWrap(True)
        self.pie_de_parametros.setStyleSheet("color: #666; font-size: 9px;")
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setWidget(self.pie_de_parametros)
        area.setFixedHeight(ALTO_DEL_PIE)
        principal.addWidget(area)

        self._artistas_de_la_imagen = []              # lo que se dibujó ENCIMA de la imagen (marcas, geometría, región del piso): se quita sin tocar la imagen
        self._ejes_de_los_perfiles = {}

        # Cada señal por su pasarela: Qt entrega argumentos (`checked`, el índice) que los manejadores no esperan.
        self.boton_imagen.clicked.connect(lambda *_: self._al_seleccionar_imagen())
        self.boton_sexto.clicked.connect(lambda marcado: self._al_marcar_el_sexto(marcado))
        self.boton_virgen.clicked.connect(lambda *_: self._al_abrir_la_virgen())
        self.boton_recalcular.clicked.connect(lambda *_: self._al_recalcular())
        self.boton_limpiar.clicked.connect(lambda *_: self._al_limpiar())
        self.boton_guardar.clicked.connect(lambda *_: self._al_guardar())
        self.selector_capa.currentIndexChanged.connect(lambda indice: self._al_cambiar_capa(indice))     # cualquier cambio del menú; las veces que la VENTANA lo mueve (`_poner_capa`) lo hace con las señales bloqueadas
        self.selector_piso.currentIndexChanged.connect(lambda indice: self._al_cambiar_piso(indice))     # ídem: la ventana lo mueve con `_poner_modo`
        # UN solo manejador de clics, aquí y no al instalar cada imagen: N imágenes seguidas acumularían N marcas por clic.
        self.lienzo_imagen.mpl_connect("button_press_event", self._al_pulsar)

    # ----------------------------------------------------------------------------------------------------- estado

    @property
    def estado(self):
        """'vacia', 'imagen', 'analizada', 'fallida' o 'registro' (abierto o recién guardado)."""
        return self._estado_actual

    @property
    def _estado(self):
        return self._estado_actual

    @_estado.setter
    def _estado(self, valor):
        """El estado de la ventana y, con él, si los menús «Capa reportada» y «Piso» se pueden mover. Con un análisis guardado o abierto ('registro') la capa que se reporta es la que guardó ese análisis y el
        piso el que usó (B7-C1: la pantalla nunca contradice lo guardado): los dos menús quedan fijos, como «Guardar»; en cualquier otro estado son la elección del físico. UNA sola definición de cuándo se
        bloquean: cada `self._estado = ...` de la ventana pasa por aquí."""
        self._estado_actual = valor
        self.selector_capa.setEnabled(valor != "registro")
        self.selector_piso.setEnabled(valor != "registro")

    @property
    def marcas(self):
        return tuple(self._marcas)

    @property
    def sexto_clic(self):
        return self._sexto

    @property
    def capa_reportada(self):
        """La letra (R, G o B; `pelicula.CAPAS`) de la capa que el menú «Capa reportada» tiene elegida: la que «Guardar» guarda. Con un análisis guardado o abierto el menú queda fijo en la capa de ese
        análisis; lo que dicen los paneles sale de `_capa_que_se_reporta`."""
        return self.selector_capa.currentData()

    @property
    def modo_del_piso(self):
        """«automatico», «punto_manual» o «virgen»: el modo que el menú «Piso» tiene elegido."""
        return self.selector_piso.currentData()

    def _capa_que_se_reporta(self):
        """La capa que ESTA ventana dice que se reporta, o None si no dice ninguna. Con un análisis guardado o abierto es la que GUARDÓ ese registro (B7-C1) y no depende del menú; en cualquier otro
        estado, la que el menú tiene elegida, que es la que «Guardar» guardará."""
        return self._capa_guardada if self._estado == "registro" else self.capa_reportada

    def _poner_capa(self, capa):
        """Pone el menú «Capa reportada» en `capa` SIN emitir señales: las veces que la VENTANA mueve el menú (arrancar, Limpiar, abrir un análisis) no son una elección del físico; quien lo mueve ya escribe lo
        que corresponde."""
        bloqueado = self.selector_capa.blockSignals(True)
        try:
            self.selector_capa.setCurrentIndex(self.selector_capa.findData(capa))
        finally:
            self.selector_capa.blockSignals(bloqueado)

    def _poner_modo(self, modo):
        """Pone el menú «Piso» en `modo` SIN emitir señales (ver `_poner_capa`): quien lo mueve decide si hay que volver a medir."""
        bloqueado = self.selector_piso.blockSignals(True)
        try:
            self.selector_piso.setCurrentIndex(self.selector_piso.findData(modo))
        finally:
            self.selector_piso.blockSignals(bloqueado)

    def _parametros(self):
        """Los parámetros con que se mide: una copia de los del motor (los 40, de fábrica). Ningún control de la ventana los cambia (PD1)."""
        return copy.deepcopy(motor.VALORES_DE_LA_GEOMETRIA)

    def _descartar_resultado(self):
        """Antes de analizar, el resultado anterior desaparece (si el nuevo análisis falla no queda uno viejo que se pueda guardar contra la imagen nueva) y «Guardar» se apaga."""
        self._resultado = None
        self._barrido = None
        self.boton_guardar.setEnabled(False)
        for figura, barra, lienzo in ((self._fig_gris, self.barra_gris, self.lienzo_gris), (self._fig_capas, self.barra_capas, self.lienzo_capas),
                                      (self._fig_perfiles, self.barra_perfiles, self.lienzo_perfiles), (self._fig_barridos, self.barra_barridos, self.lienzo_barridos)):
            figura.clear()
            barra.update()                       # sin esto, «Home» volvería a la vista de la figura anterior
            lienzo.draw_idle()
        self.eje_cuadratura.clear()
        self.barra_cuadratura.update()
        self.lienzo_cuadratura.draw_idle()
        self._ejes_de_los_perfiles = {}
        for tabla in (self.tabla_desfases, self.tabla_perfiles, self.tabla_barridos, self.tabla_cuadratura):
            tabla.setRowCount(0)
        for etiqueta in (self.nota_pestana1, self.nota_pestana2, self.linea_regla):
            _poner_texto(etiqueta, "")
        _poner_texto(self.etiqueta_piso, "")
        self.pie_de_parametros.setText(dibujo.texto_de_parametros())

    def _quitar_artistas_de_la_imagen(self):
        """Quita de la imagen lo que se dibujó encima de ella (marcas, geometría, región del piso, sexto clic, leyenda); la imagen queda."""
        for artista in self._artistas_de_la_imagen:
            try:
                artista.remove()
            except (ValueError, NotImplementedError, AttributeError):
                pass
        self._artistas_de_la_imagen = []

    def _apagar_herramientas(self):
        for barra in (self.barra_imagen, self.barra_gris, self.barra_capas, self.barra_perfiles, self.barra_barridos, self.barra_cuadratura):
            _apagar_barra(barra)

    def _restablecer_estado(self):
        """El estado de arranque, y el ÚNICO sitio que lo define: `__init__` lo llama tras construir y «Limpiar» lo llama otra vez, así que «Limpiar» deja una ventana igual a una recién creada (la prueba lo
        comprueba con una huella del árbol de widgets, no con una lista de lo que este método limpia)."""
        self._descartar_resultado()
        self._quitar_artistas_de_la_imagen()
        self._apagar_herramientas()
        self._bytes = None
        self._nombre = None
        self._forma = None
        self._con_milimetros = True              # el archivo abierto da escala en milímetros (lo dice `_instalar_imagen`); el texto de las marcas habla en milímetros solo si la hay
        self._pelicula = None
        self._marcas = []
        self._sexto = None
        self._registro = None
        self._capa_guardada = None
        self._estado = "vacia"
        self.eje_imagen.clear()
        self.eje_imagen.set_xlabel("columna de la imagen [px]")
        self.eje_imagen.set_ylabel("fila de la imagen [px]")
        self.barra_imagen.update()
        self.lienzo_imagen.draw_idle()
        self.boton_sexto.setChecked(False)
        self.nombre_archivo.setText(SIN_IMAGEN)
        self.indicador.setText(TEXTO_ANALIZANDO)
        self.indicador.hide()
        for etiqueta in (self.etiqueta_imagen, self.etiqueta_marcas, self.etiqueta_registro):
            _poner_texto(etiqueta, "")
        self._poner_capa(pel.CAPA_POR_OMISION)                  # el menú de la capa reportada arranca en la capa por omisión (el valor inicial: ningún PDF la lee)
        self._actualizar_el_menu_del_piso()
        self._poner_modo(pel.MODO_DEL_PISO_POR_OMISION)
        self.pestanas.setCurrentIndex(PESTANA_IMAGEN)

    # ----------------------------------------------------------------------------------------------------- el menú «Piso» y la película virgen

    def _carpeta_de_la_base(self):
        """La carpeta de la base de datos: donde se guarda la película virgen de referencia (la comparten todos los equipos que abren esa base)."""
        return os.path.dirname(conection.ruta_base_datos())

    def refrescar(self):
        """Vuelve a leer la película virgen de referencia (y con ella el menú «Piso»). Público y llamado en `showEvent`: la ventana puede quedar abierta mientras otro equipo guarda una referencia nueva."""
        try:
            self._referencia_virgen = pel.leer_referencia_virgen(self._carpeta_de_la_base())
            self._aviso_referencia = ""
        except (ValueError, OSError) as error:               # un archivo danado o que no se puede leer (permisos, la red): se dice y no se usa
            self._referencia_virgen = None
            self._aviso_referencia = str(error)
        modo_perdido = self._actualizar_el_menu_del_piso()
        if len(self._marcas) == 5 and self._estado_actual in ("analizada", "fallida") and (modo_perdido or self._la_virgen_del_analisis_ya_no_es_la_vigente()):
            self._analizar()                        # el análisis se hizo con un modo que ya no está disponible, o con una película virgen que ya no es la vigente: se vuelve a medir con la que el menú dice
        else:
            self._aplicar_la_regla()

    @_protegido("Película virgen")
    def showEvent(self, evento):
        super().showEvent(evento)
        self.refrescar()

    def _referencia_utilizable(self):
        """La referencia de la película virgen que se puede usar (la guardada, si es válida), o None."""
        r = self._referencia_virgen
        return r if r is not None and r.estado == "ok" else None

    def _la_virgen_del_analisis_ya_no_es_la_vigente(self):
        """True si el análisis que la ventana tiene a la vista se midió en el modo «virgen» con una película virgen que ya no es la vigente (otro equipo guardó una nueva, o el físico la cambió con «Película
        virgen...»): «Guardar» guardaría con la vigente lo que la pantalla muestra medido con la anterior (E1-PROD-01: lo guardado difería de lo que el físico vio). Se compara la COPIA entera
        (`como_dict`: la huella y también la orientación declarada y lo medido), no solo la huella: esa copia viaja dentro de cada análisis (DA-81). Un registro no se compara (se muestra con SU copia),
        un análisis medido sin la virgen (piso automático o punto marcado) no la usa, y uno sin piso no llegó a usar ninguna."""
        resultado, vigente = self._resultado, self._referencia_utilizable()
        if resultado is None or resultado.piso is None or self._estado_actual != "analizada" or resultado.piso.modo != "virgen" or vigente is None:
            return False
        usada = resultado.piso.referencia
        return usada is None or usada.como_dict() != vigente.como_dict()

    def _referencia_que_nombra_el_menu(self):
        """La película virgen que el renglón «Película virgen» del menú «Piso» nombra. Con un análisis guardado o abierto en el modo «virgen» es la COPIA con que se midió (la guardada manda, DA-81): la línea
        del piso y la etiqueta del registro hablan de ella y el menú, fijo y con ese renglón seleccionado, no puede nombrar otra (B7-C1: la pantalla no contradice lo guardado), ni «no hay referencia» si la vigente
        desapareció. En cualquier otro caso es la referencia vigente (None si no hay una válida)."""
        if self._registro is not None and self._resultado is not None:
            piso = self._resultado.piso
            if piso is not None and piso.modo == "virgen" and piso.referencia is not None:
                return piso.referencia
        return self._referencia_utilizable()

    def _actualizar_el_menu_del_piso(self):
        """Los tres textos del menú «Piso» y cuáles se pueden elegir: «Punto marcado» solo con un sexto clic, «Película virgen» solo con una referencia válida (el menú dice cuál: archivo y fecha; con un
        análisis guardado, la copia que ese análisis usó). Si el modo elegido deja de estar disponible, el menú vuelve al de omisión y devuelve True (quien lo llama decide si hay que volver a medir)."""
        referencia = self._referencia_utilizable()
        nombrada = self._referencia_que_nombra_el_menu()
        textos = {"automatico": TEXTO_PISO_AUTOMATICO, "punto_manual": TEXTO_PISO_PUNTO, "virgen": TEXTO_PISO_SIN_VIRGEN}
        if nombrada is not None:
            pr = nombrada.procedencia
            textos["virgen"] = f"Película virgen «{pr.get('archivo') or 'sin nombre'}» ({pr.get('fecha_escaneo') or pr.get('fecha_calculo')})"
        disponible = {"automatico": True, "punto_manual": self._sexto is not None, "virgen": referencia is not None}
        modelo = self.selector_piso.model()
        bloqueado = self.selector_piso.blockSignals(True)
        try:
            for i in range(self.selector_piso.count()):
                modo = self.selector_piso.itemData(i)
                self.selector_piso.setItemText(i, textos[modo])
                modelo.item(i).setEnabled(disponible[modo])
        finally:
            self.selector_piso.blockSignals(bloqueado)
        if self._estado_actual != "registro" and not disponible.get(self.modo_del_piso, True):
            self._poner_modo(pel.MODO_DEL_PISO_POR_OMISION)
            return True
        return False

    @_protegido("Película virgen")
    def _al_abrir_la_virgen(self):
        """«Película virgen...»: elegir el escaneo, medirlo (`piso_de_pelicula_virgen`), mostrar el cuadro con todo lo que se comprobó y, si el físico la guarda como referencia, escribirla junto a la base
        (`guardar_referencia_virgen`) con su fila de auditoría."""
        ruta, _filtro = QFileDialog.getOpenFileName(self, "Seleccionar la película virgen", "", FILTRO_IMAGENES)
        if not ruta:
            return
        try:
            with open(ruta, "rb") as archivo:
                datos = archivo.read()
        except OSError as error:
            QMessageBox.warning(self, "Película virgen", f"No se pudo leer el archivo: {error}")
            return
        referencia = self._con_espera("Midiendo la película virgen...", lambda: pel.piso_de_pelicula_virgen(datos, self._parametros(), os.path.basename(ruta), date.today().isoformat()))
        dialogo = DialogoPeliculaVirgen(referencia, datos, self._referencia_utilizable(), self)
        aceptado = dialogo.exec_() == QDialog.Accepted
        if not aceptado or not dialogo.guardar_solicitado:
            return
        final = dialogo.referencia_final()
        existia = self._referencia_utilizable() is not None
        try:
            pel.guardar_referencia_virgen(final, self._carpeta_de_la_base(), datos, self.usuario)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Película virgen", f"No se guardó la película virgen: {error}")
            return
        pr = final.procedencia
        audit_minimo.registrar(self.usuario, audit_minimo.ACCION_REEMPLAZO if existia else audit_minimo.ACCION_GUARDAR, "piso_pelicula_virgen", ref=str(pr["sha256"])[:8],
                               detalle=dibujo.detalle_de_la_referencia_virgen(pr))
        self.refrescar()
        QMessageBox.information(self, "Película virgen", f"Película virgen guardada como referencia: «{pr.get('archivo')}». Elija «Película virgen» en el menú «Piso» para usarla.")

    # ----------------------------------------------------------------------------------------------------- la imagen y los clics

    def _pelicula_cargada(self):
        """La `Pelicula` de la imagen abierta, leída de sus bytes la primera vez que hace falta (marcar un punto necesita su gris y su máscara de píxeles con dato). No se retiene tras el análisis."""
        if self._pelicula is None:
            self._pelicula = pel.leer_pelicula(self._bytes)
        return self._pelicula

    def _soltar_la_pelicula(self):
        """Suelta la película (sus capas en flotante pesan 540 MB en una página del escáner): el resultado ya trae la película girada y recortada."""
        self._pelicula = None
        gc.collect()

    @_protegido("Seleccionar imagen")
    def _al_seleccionar_imagen(self):
        ruta, _filtro = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", FILTRO_IMAGENES)
        if not ruta:
            return
        # La carga es atómica: se lee y se interpreta todo ANTES de tocar la ventana; si algo falla, queda igual.
        try:
            with open(ruta, "rb") as archivo:
                datos = archivo.read()
            pelicula = pel.leer_pelicula(datos)
            rgb = dibujo.imagen_rgb(pelicula)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Seleccionar imagen", f"No se pudo leer la imagen: {error}")
            return
        self._instalar_imagen(datos, os.path.basename(ruta), pelicula, rgb)

    def _instalar_imagen(self, datos, nombre, pelicula, rgb):
        """Descarta todo lo de la imagen anterior (resultado, marcas, sexto clic, análisis abierto, herramientas) y muestra la nueva en su color original (RGB uint8 con `nearest`)."""
        self._descartar_resultado()
        self._quitar_artistas_de_la_imagen()
        self._apagar_herramientas()
        self._marcas = []
        self._sexto = None
        self._registro = None
        self._capa_guardada = None
        self.boton_sexto.setChecked(False)
        self._bytes, self._nombre, self._forma = datos, nombre, rgb.shape[:2]
        self._pelicula = pelicula
        self.eje_imagen.clear()
        dibujo.dibujar_imagen(self.eje_imagen, rgb)
        self.barra_imagen.update()
        self.nombre_archivo.setText(nombre)
        P = motor.VALORES_DE_LA_GEOMETRIA
        self._con_milimetros = pel.escala_mm(pelicula.dpi, P) is not None
        _poner_texto(self.etiqueta_imagen, dibujo.texto_de_la_imagen(pelicula.formato, pelicula.bits, self._forma, pelicula.dpi, pel.clase_resolucion(pelicula.dpi, P), pelicula.fecha_escaneo,
                                                                    pelicula.transparentes, P["resolucion_escaneo_dpi"]))
        _poner_texto(self.etiqueta_marcas, "")
        _poner_texto(self.etiqueta_registro, "")
        self._estado = "imagen"
        self._actualizar_el_menu_del_piso()
        self.pestanas.setCurrentIndex(PESTANA_IMAGEN)
        self.lienzo_imagen.draw_idle()

    @_protegido("Marcar un punto")
    def _al_pulsar(self, evento):
        """Un clic cuenta solo si la ventana espera puntos, la lupa y el desplazar están apagados, es el botón izquierdo (no un doble clic) y cae DENTRO de la imagen. Se guarda redondeado a 3 decimales.
        El siguiente clic tras «Marcar película sin irradiar» es el SEXTO: nunca entra a la clasificación de los cinco puntos del campo."""
        if self._bytes is None or self._estado not in ("imagen", "analizada", "fallida"):
            return
        if self.lienzo_imagen.widgetlock.locked() or evento.inaxes is not self.eje_imagen:
            return
        if evento.button != 1 or evento.dblclick or evento.xdata is None or evento.ydata is None:
            return
        alto, ancho = self._forma
        if not (-0.5 <= evento.xdata < ancho - 0.5 and -0.5 <= evento.ydata < alto - 0.5):
            return
        punto = (round(float(evento.xdata), DECIMALES_CLIC), round(float(evento.ydata), DECIMALES_CLIC))
        if self.boton_sexto.isChecked():
            self._registrar_el_sexto(punto)
            return
        if len(self._marcas) >= 5 or self._estado != "imagen":
            return
        self._marcas.append(self._refinar(punto))
        _poner_texto(self.etiqueta_marcas, dibujo.texto_de_las_marcas(self._marcas, self._con_milimetros))
        self._pintar_la_imagen()
        if len(self._marcas) == 5:
            self._analizar()

    def _refinar(self, clic):
        """Refina el clic igual que `guardar` (la misma función con los mismos argumentos, así lo que ve el físico y lo que se guarda no pueden discrepar): acerca el clic al centro de su marca de tinta o lo
        deja «sin refinar» con su motivo."""
        pelicula = self._pelicula_cargada()
        P = self._parametros()
        tam_mm = pel.escala_mm(pelicula.dpi, P)
        return motor.refinar_marca(pelicula.gris, clic, P, tam_mm, pelicula.validos)

    @_protegido("Marcar película sin irradiar")
    def _al_marcar_el_sexto(self, marcado):
        """El botón «Marcar película sin irradiar»: arma el siguiente clic como el sexto (un trozo de película sin irradiar escaneado junto). Pulsarlo otra vez lo desarma."""
        if self._bytes is None or self._estado == "registro":
            self.boton_sexto.setChecked(False)

    def _registrar_el_sexto(self, punto):
        """El sexto clic: es `punto_manual` (con el modo «punto_manual» del piso, que el menú pasa a elegir) y nunca un punto del campo. Con los cinco puntos ya marcados vuelve a medir; sin ellos, el
        piso se mide cuando se completen."""
        self._sexto = punto
        self.boton_sexto.setChecked(False)
        self._actualizar_el_menu_del_piso()
        self._poner_modo("punto_manual")
        if len(self._marcas) == 5 and self._estado in ("analizada", "fallida"):
            self._analizar()
        else:
            self._pintar_la_imagen()
            self._aplicar_la_regla()

    def _pintar_la_imagen(self):
        """Dibuja encima de la imagen lo que hay: las marcas (clic, punto refinado y círculo de búsqueda), el sexto clic con su cuadrado y, con un análisis, el recuadro del campo luminoso, las bandas de los
        perfiles, la zona central y la región del piso. Lo que había encima se quita y la vista (el zoom del físico) se conserva."""
        ax = self.eje_imagen
        limites = ax.get_xlim(), ax.get_ylim()
        self._quitar_artistas_de_la_imagen()
        antes = set(ax.get_children())
        dibujo.dibujar_marcas(ax, self._marcas)
        if self._sexto is not None:
            P = self._parametros()
            dibujo.dibujar_sexto_clic(ax, self._sexto, P["lado_punto_manual_mm"] / pel.escala_mm(None, P))
        if self._resultado is not None:
            dibujo.dibujar_geometria(ax, self._resultado, self._barrido, self._marcas)
            dibujo.dibujar_region_del_piso(ax, self._resultado, "imagen")
        dibujo.dibujar_leyenda_de_la_imagen(ax)
        self._artistas_de_la_imagen = [a for a in ax.get_children() if a not in antes]
        ax.set_xlim(*limites[0])
        ax.set_ylim(*limites[1])
        self.lienzo_imagen.draw_idle()

    # ----------------------------------------------------------------------------------------------------- el análisis

    def _con_espera(self, texto, funcion):
        """Indicador visible (con `repaint()`: el cómputo es síncrono y bloquea el bucle de eventos que lo pintaría), cursor de espera y `try/finally`. Nunca `processEvents`: dejaría entrar otro clic en mitad
        del análisis."""
        self.indicador.setText(texto)
        self.indicador.show()
        self.indicador.repaint()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return funcion()
        finally:
            QApplication.restoreOverrideCursor()
            self.indicador.hide()
            self.indicador.setText(TEXTO_ANALIZANDO)             # el texto de arranque: lo que dijo la ultima espera no es un estado de la ventana

    def _medir(self):
        """Lo que mide el análisis, por el MISMO camino que `guardar`: la película de los bytes, las marcas ya refinadas con `refinar_marca` y `analizar` con los parámetros de fábrica entero, el modo del piso, el
        sexto clic (solo en el modo «punto_manual») y la referencia (solo en el modo «virgen»). Devuelve (resultado, barrido)."""
        modo = self.modo_del_piso
        resultado = motor.analizar(self._pelicula_cargada(), self._marcas, self._parametros(), modo_piso=modo, punto_manual=self._sexto if modo == "punto_manual" else None,
                                   referencia_virgen=self._referencia_utilizable() if modo == "virgen" else None)
        return resultado, motor.barrido(resultado)

    def _calcular(self):
        """Corre el análisis con la espera. Si falla avisa (ya con el cursor restaurado) y devuelve None sin tocar nada."""
        try:
            return self._con_espera(TEXTO_ANALIZANDO, self._medir)
        except ValueError as error:
            QMessageBox.warning(self, "Analizar", dibujo.con_punto_final(f"No se pudo analizar: {error}") + " Pulse Recalcular para marcar otra vez.")
        except Exception as error:
            traceback.print_exc()
            QMessageBox.critical(self, "Analizar", f"Error inesperado al analizar ({type(error).__name__}: {error}).")
        return None

    def _analizar(self):
        self._descartar_resultado()
        medido = self._calcular()
        self._soltar_la_pelicula()
        if medido is None:
            self._estado = "fallida"
            self._pintar_la_imagen()
            return None
        self._resultado, self._barrido = medido
        self._estado = "analizada"
        self._mostrar()
        return self._resultado

    # ----------------------------------------------------------------------------------------------------- mostrar

    def _mostrar(self):
        """Dibuja las cinco pestañas con el resultado y escribe lo que depende de la capa reportada (la nota, el panel de la pestaña 3, la línea de la regla y «Guardar»)."""
        resultado, barrido = self._resultado, self._barrido
        self._pintar_la_imagen()
        self._fig_gris.clear()
        dibujo.dibujar_perfiles_del_gris(self._fig_gris, resultado)
        self._fig_capas.clear()
        dibujo.dibujar_capas(self._fig_capas, resultado)
        self._fig_perfiles.clear()
        self._ejes_de_los_perfiles = dibujo.dibujar_perfiles_por_capa(self._fig_perfiles, resultado, self._capa_que_se_reporta())
        self._fig_barridos.clear()
        dibujo.dibujar_barridos(self._fig_barridos, barrido)
        self.eje_cuadratura.clear()
        if resultado.geometria is not None and resultado.geometria.ok:
            dibujo.dibujar_cuadratura(self.eje_cuadratura, resultado.geometria)
            _llenar_tabla(self.tabla_cuadratura, dibujo.filas_de_la_cuadratura(resultado.geometria))
        else:
            self.tabla_cuadratura.setRowCount(0)
        _llenar_tabla(self.tabla_barridos, dibujo.filas_de_los_barridos(barrido))
        _llenar_tabla(self.tabla_desfases, dibujo.tabla_de_desfases(resultado))
        self.pie_de_parametros.setText(dibujo.texto_de_parametros(resultado.parametros))
        for barra in (self.barra_gris, self.barra_capas, self.barra_perfiles, self.barra_barridos, self.barra_cuadratura):
            barra.update()
        self._aplicar_la_regla()
        for lienzo in (self.lienzo_gris, self.lienzo_capas, self.lienzo_perfiles, self.lienzo_barridos, self.lienzo_cuadratura):
            lienzo.draw_idle()

    def _texto_del_piso(self):
        """La línea del piso (de dónde salió, a qué distancia del campo y, en el modo virgen, la comparación solo informativa) y, si el piso no se pudo medir, lo que se puede hacer."""
        piso = self._resultado.piso if self._resultado is not None else None
        partes = []
        if piso is not None:
            texto = dibujo.con_punto_final(pel.texto_breve_del_piso(piso, self._capa_que_se_reporta()))       # la frase de una capa o de un piso sin número no trae punto: se cierra antes de lo que sigue
            if piso.estado == "ok":
                comparacion = pel.texto_de_la_comparacion(piso)
                texto += (" " + comparacion if comparacion else "") + ("".join(" " + a for a in piso.avisos) if piso.avisos else "")
            else:
                texto += " Puede tomar el piso con «Marcar película sin irradiar» o con una película virgen («Película virgen...»)."
            partes.append(texto)
        if self._aviso_referencia:
            partes.append(self._aviso_referencia)
        return " ".join(partes)

    # ----------------------------------------------------------------------------------------------------- la regla de «Guardar» (D.1b)

    def _regla_de_guardar(self):
        """(habilitado, texto, motivo): LA regla de «Guardar», una sola. «Guardar» se ofrece solo con un análisis de esta sesión (estado «analizada») y si `svc.motivo_para_no_guardar(resultado, capa del menú)`
        es None; si no, `texto` es la línea que dice por qué (el texto del servicio TAL CUAL con el prefijo de la ventana y, si hay otras capas que sí se pueden guardar, cuáles) y `motivo` el del servicio.
        Ninguna decisión propia: la ventana no compara ningún estado con «ok»."""
        if self._resultado is None or self._estado != "analizada":
            return False, "", None
        motivo = svc.motivo_para_no_guardar(self._resultado, self.capa_reportada)
        if motivo is None:
            return True, "", None
        guardables = tuple(c for c in pel.CAPAS if svc.motivo_para_no_guardar(self._resultado, c) is None)
        return False, dibujo.texto_de_la_regla(motivo, guardables), motivo

    def _motivo_de_la_capa_que_se_reporta(self):
        """El motivo del servicio para la capa que la ventana dice que se reporta (None si se puede guardar o si no hay capa ni resultado)."""
        capa = self._capa_que_se_reporta()
        if self._resultado is None or capa not in pel.CAPAS:
            return None
        return svc.motivo_para_no_guardar(self._resultado, capa)

    def _aplicar_la_regla(self):
        """Escribe todo lo que depende de la regla y de la capa reportada: el habilitado de «Guardar», la línea que dice por qué no, la nota de la pestaña 1, la columna «Se guarda» del panel de la
        pestaña 3, la línea del piso y el título de los perfiles. Lo llaman el final de cada análisis, el cambio de «Capa reportada» (que no recalcula), el de «Piso», el sexto clic y quien mueva el menú."""
        habilitado, texto, _motivo = self._regla_de_guardar()
        self.boton_guardar.setEnabled(habilitado)
        _poner_texto(self.linea_regla, texto)
        texto_del_piso = self._texto_del_piso()
        _poner_texto(self.etiqueta_piso, texto_del_piso)
        if self._resultado is None:
            return
        registro = self._estado == "registro"
        capa = self._capa_que_se_reporta()
        motivo = self._motivo_de_la_capa_que_se_reporta()
        _poner_texto(self.nota_pestana1, dibujo.nota_de_la_pestana_1(motivo, capa, registro))
        _llenar_tabla(self.tabla_perfiles, dibujo.filas_de_los_perfiles(self._resultado, capa, motivo, registro))
        _poner_texto(self.nota_pestana2, "")
        for (capa_del_eje, eje), ax in self._ejes_de_los_perfiles.items():
            ax.set_title(dibujo.titulo_del_perfil(getattr(self._resultado.capas[capa_del_eje], eje), capa_del_eje, reportada=(capa_del_eje == capa)), fontsize=8)
        self.lienzo_perfiles.draw_idle()

    # ----------------------------------------------------------------------------------------------------- los menús

    @_protegido("Capa reportada")
    def _al_cambiar_capa(self, _indice):
        """El físico eligió otra capa en el menú. NO se mide ni se redibuja nada: el motor ya midió las tres capas; cambia lo que se REPORTA, así que solo se vuelve a evaluar la regla (leer un estado) y se
        reescriben lo que depende de ella. Sin resultado el menú guarda la elección para el próximo análisis."""
        if self._resultado is None:
            return
        self._aplicar_la_regla()

    @_protegido("Piso")
    def _al_cambiar_piso(self, _indice):
        """El físico eligió otro piso: eso SÍ cambia los números, así que se vuelve a medir (con las marcas ya hechas) y se vuelve a evaluar la regla; se guarda con el análisis y el PDF lo imprime (PD1).
        Sin los cinco puntos el menú guarda la elección para cuando se completen."""
        if len(self._marcas) == 5 and self._bytes is not None and self._estado in ("analizada", "fallida"):
            self._analizar()

    # ----------------------------------------------------------------------------------------------------- los botones

    @_protegido("Recalcular")
    def _al_recalcular(self):
        """Conserva la imagen y su nombre y borra los puntos, el sexto clic, las marcas y el resultado; el menú «Capa reportada» conserva su elección (cambiarla no mide nada) y el de «Piso» también, salvo el
        punto marcado, que se borra con el sexto clic."""
        self._descartar_resultado()
        self._quitar_artistas_de_la_imagen()
        self._apagar_herramientas()
        self._marcas = []
        self._sexto = None
        self._registro = None
        self._capa_guardada = None
        self.boton_sexto.setChecked(False)
        _poner_texto(self.etiqueta_marcas, "")
        _poner_texto(self.etiqueta_registro, "")
        self._estado = "imagen" if self._bytes is not None else "vacia"
        self._actualizar_el_menu_del_piso()
        if self._bytes is not None:
            self._pintar_la_imagen()
        self.pestanas.setCurrentIndex(PESTANA_IMAGEN)

    @_protegido("Limpiar")
    def _al_limpiar(self):
        self._restablecer_estado()
        self.refrescar()

    @_protegido("Guardar")
    def _al_guardar(self):
        """Guarda los datos finales de la capa elegida. La regla se vuelve a consultar AQUÍ (el botón ya debería estar apagado, pero esta función se puede llamar sola): con la capa no medible no se llama al
        servicio. La pregunta de reemplazo, si ya hay un análisis guardado, va DESPUÉS de la regla: nunca se pregunta «¿reemplazar?» por algo que no se va a guardar."""
        if self._resultado is None or self._estado != "analizada":
            return
        capa = self.capa_reportada
        if svc.motivo_para_no_guardar(self._resultado, capa) is not None:
            self._aplicar_la_regla()
            return
        existe = svc.leer(self.ref) is not None
        if existe and QMessageBox.question(self, "Guardar", RESPUESTA_AL_REEMPLAZAR, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        modo = self.modo_del_piso
        try:
            # `guardar` vuelve a analizar desde los bytes y los CLICS sin refinar (el servicio no confía en un resultado ajeno), así que va dentro de la misma espera.
            nuevo = self._con_espera("Guardando...", lambda: svc.guardar(self.ref, self.usuario, self._bytes, self._nombre, [m.clic for m in self._marcas], self._parametros(), capa, modo,
                                                                         punto_manual=self._sexto if modo == "punto_manual" else None,
                                                                         referencia_virgen=self._referencia_utilizable() if modo == "virgen" else None))
        except svc.PlacaMensualError as error:                # incluye `ControlNoEditable`: el mensaje del servicio, tal cual
            QMessageBox.warning(self, "Guardar", dibujo.con_punto_final(f"No se guardó: {error}"))
            return
        self._registro = svc.leer(self.ref)
        self._capa_guardada = capa
        self._estado = "registro"
        self._aplicar_la_regla()
        _poner_texto(self.etiqueta_registro, f"Guardado: análisis del control {self.ref}, capa reportada {pel.ADJETIVO_DE_LA_CAPA[capa]}.")
        QMessageBox.information(self, "Guardar", f"Análisis guardado para el control {self.ref} (capa {pel.ADJETIVO_DE_LA_CAPA[capa]}; id {nuevo}).")

    @_protegido("Abrir", por_defecto=False)
    def abrir_guardado(self):
        """Abre el análisis guardado del control: la imagen, los puntos YA refinados, los parámetros y el piso GUARDADOS (no los de hoy ni la referencia vigente: la copia guardada manda, DA-81) se vuelven a
        medir con `svc.recalcular` y se compara con lo guardado (DD3). Devuelve True si se abrió. Si no se puede leer ni analizar, avisa y la ventana queda como estaba (todo se lee y se calcula antes de
        tocarla). Deja «Guardar» apagado y los menús fijos en la capa y el piso del análisis (B7-C1): para guardar de nuevo, con esa capa u otra, «Recalcular»."""
        registro = svc.leer(self.ref)
        if registro is None:
            return False
        try:
            pelicula = pel.leer_pelicula(registro["imagen"])
            rgb = dibujo.imagen_rgb(pelicula)
            formato, bits, dpi, fecha, transparentes = pelicula.formato, pelicula.bits, pelicula.dpi, pelicula.fecha_escaneo, pelicula.transparentes
            del pelicula
            resultado = self._con_espera("Abriendo el análisis guardado...", lambda: svc.recalcular(registro))
            barrido = motor.barrido(resultado)
        except ValueError as error:                       # incluye `PlacaMensualError`
            QMessageBox.warning(self, "Abrir", f"No se pudo abrir el análisis guardado: {error}")
            return False
        self._descartar_resultado()
        self._quitar_artistas_de_la_imagen()
        self._apagar_herramientas()
        self.eje_imagen.clear()
        dibujo.dibujar_imagen(self.eje_imagen, rgb)
        self._bytes, self._nombre, self._forma = registro["imagen"], registro["nombre_archivo"] or "", rgb.shape[:2]
        self._pelicula = None
        self._marcas = list(registro["puntos"])
        piso = registro["piso"]
        self._sexto = None if piso.get("punto") is None else tuple(piso["punto"])
        self._registro = registro
        self._resultado, self._barrido = resultado, barrido
        self.nombre_archivo.setText(self._nombre or SIN_IMAGEN)
        P = registro["parametros"]
        self._con_milimetros = pel.escala_mm(dpi, P) is not None
        _poner_texto(self.etiqueta_imagen, dibujo.texto_de_la_imagen(formato, bits, self._forma, dpi, pel.clase_resolucion(dpi, P), fecha, transparentes, P["resolucion_escaneo_dpi"]))
        _poner_texto(self.etiqueta_marcas, dibujo.texto_de_las_marcas(self._marcas, self._con_milimetros))
        self._actualizar_el_menu_del_piso()
        self._poner_modo(piso["modo"])
        self._poner_capa(registro["capa"])
        self._capa_guardada = registro["capa"]
        self._estado = "registro"                       # el estado se fija ANTES de dibujar porque `_mostrar` escribe los paneles con él
        self._mostrar()
        self.pestanas.setCurrentIndex(PESTANA_IMAGEN)
        lineas = [f"Análisis guardado: {self._nombre or 'sin nombre de archivo'}, {registro['fecha_registro']}, por {registro['usuario']}; capa reportada {pel.ADJETIVO_DE_LA_CAPA[registro['capa']]}."]
        motivo = svc.motivo_para_no_guardar(resultado, registro["capa"])
        if motivo is not None:
            lineas.append(dibujo.con_punto_final(f"En lo recalculado la capa guardada ya no es medible: {motivo}"))
        vigente = self._referencia_utilizable()
        guardada = piso.get("referencia_virgen")
        if guardada is not None and vigente is not None and guardada["procedencia"].get("sha256") != vigente.procedencia.get("sha256"):
            lineas.append(f"La película virgen de referencia vigente es otra («{vigente.procedencia.get('archivo')}»); este análisis usa la copia que se guardó con él («{guardada['procedencia'].get('archivo')}»).")
        diferencias = svc.diferencias(registro, resultado)
        if diferencias:
            lineas.append("Lo recalculado no coincide con lo guardado:\n" + "\n".join(diferencias))
        _poner_texto(self.etiqueta_registro, "\n".join(lineas))
        if diferencias:
            QMessageBox.warning(self, "Abrir", "Lo recalculado no coincide con lo guardado:\n" + "\n".join(diferencias))
        return True
