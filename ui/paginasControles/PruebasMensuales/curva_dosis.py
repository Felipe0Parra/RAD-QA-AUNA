"""CD.5 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-90, DA-92): la ventana de calibración de las películas, `VentanaCurvaDosis(usuario, parent=None)`.

Lo pidió el físico: «un pequeño botón por dosis donde se cargue la imagen de la película irradiada de forma uniforme a esa dosis, al lado la dosis real medida con una cámara de ionización y así debajo
diferentes dosis». Una fila por dosis (arranca con la plantilla de P12, que se edita; «Agregar dosis» y «Quitar»; se aceptan réplicas), el encabezado de la calibración (lote, tipo de película, fecha y hora
de irradiación, acelerador, energía, profundidad, DFS, campo, cámara y electrómetro del catálogo con su copia, la incertidumbre de la dosis medida, el escáner declarado y el modo de escaneo, observaciones), y
el gráfico ÚNICO de las cuatro capas con los residuos debajo y la tabla de la curva (DA-92). Al cargar cada imagen la pieza se mide (CD.2) con el cursor de espera y la curva se vuelve a ajustar (CD.3).

SIN SQL: todo lo que se guarda y se lee pasa por `services/curva_dosis.py` (la ÚNICA puerta a las dos tablas de CD.4), el catálogo de equipos por `EquiposService` y la película virgen montada por
`pelicula.leer_referencia_virgen`. Lo que se mide y se ajusta lo dicen el motor de CD.2 y el de CD.3; los dibujos y los textos son funciones puras de `analisisImagenes/dibujo_curva_dosis.py`.

LA CURVA DE LA PANTALLA ES LA QUE SE GUARDA (CD5-D1). `guardar` del servicio vuelve a MEDIR cada pieza desde sus bytes y vuelve a AJUSTAR (no confía en una curva ajena, CD.4); la ventana mide y ajusta por
EL MISMO camino (`_medir_la_pieza` y `_ajustar`: `medir_pieza_uniforme` con una copia de `VALORES_DE_LA_GEOMETRIA` y `escala="declarada"`, `pieza_de_calibracion` con el orden de la fila y `ajustar` sin
parámetros propios, con la virgen montada y la incertidumbre del formulario), como la ventana mensual hace con `guardar` de D.1 (`_medir`). Una prueba guarda y compara la curva de la pantalla con la guardada.

Lo que el servicio rechaza (`CurvaDosisError`) se dice TAL CUAL, sin recortarlo ni traducirlo (CD.4); un error inesperado al guardar se traduce con `errores_guardado.traducir` y su causa queda en
`error_log.txt` (GI.6). El usuario que se le pasa al servicio es un TEXTO (su nombre); el objeto de la sesión, si lo hay, es el del diálogo del permiso de anular (DA-01).

Una calibración ABIERTA se ve y no se edita (como la calculadora, Z4): se dibuja su COPIA guardada (`curva_desde_dict` del ajuste, DA-81), se vuelve a ajustar (`recalcular`) y se dice lo que no coincide
(`diferencias`), los escaneos que faltan y las copias que ya no coinciden con su huella, cada cosa aparte. «Nueva» deja la ventana igual a una recién creada (la prueba lo comprueba con una huella).

Ningún manejador deja escapar una excepción (`_protegido`) y ningún cuadro se abre con el cursor de espera puesto."""
import copy
import os
from datetime import date

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QDateEdit, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QSplitter, QTableWidgetItem, QVBoxLayout, QWidget)

from analisisImagenes import curva_dosis as motor
from analisisImagenes import dibujo_curva_dosis as dibujo
from analisisImagenes import pelicula as pel
from analisisImagenes.catphan.errores_guardado import traducir as traducir_error_de_guardado
from analisisImagenes.placa_mensual import VALORES_DE_LA_GEOMETRIA
from data.ManejoDatos import conection
from resources.utils.matplotlib_lazy import get_matplotlib_components
from services import curva_dosis as svc
from services.equipos_service import EquiposService
from services.registro_errores import registrar_error
from ui.paginasControles.PruebasMensuales.placa_mensual import (_SelectorSinRueda, _llenar_tabla, _nombre_del_usuario, _nueva_tabla, _nuevo_lienzo, _poner_texto, _protegido, _recuadro,
                                                                _tamano_inicial)
from ui.paginasGuia.dialogs import DialogAdminPermisoEliminar

TITULO = "Curva de dosis de las películas: calibración"
FILTRO_IMAGENES = "Imágenes sin pérdida (*.tif *.tiff *.TIF *.TIFF *.png *.PNG);;Todos los archivos (*)"
TIPO_CAMARA, TIPO_ELECTROMETRO = "Cámara de ionización", "Electrómetro"
SIN_CAMARA, SIN_ELECTROMETRO = "Sin cámara", "Sin electrómetro"
MODOS = (("sin declarar", None), ("transmisión", "transmisión"), ("reflexión", "reflexión"))
ESTADO_NUEVA, ESTADO_REGISTRO = "nueva", "registro"
TEXTO_MIDIENDO = "Midiendo la pieza..."
TEXTO_GUARDANDO = "Guardando la calibración..."
TEXTO_ABRIENDO = "Abriendo la calibración..."
SIN_CURVA = "Cargue la imagen de cada pieza y escriba su dosis medida: la curva se ajusta sola."
PREGUNTA_GUARDAR = "¿Guardar la calibración de todos modos?"
PREGUNTA_NUEVA = "Hay piezas cargadas que no se guardaron. ¿Empezar una calibración nueva y descartarlas?"
NO_GUARDA_SIN_CERO = ("No se guardó: la curva no tiene cero. Cargue la película virgen (0 cGy), o escriba la dosis medida de una pieza irradiada que se haya podido medir: la de menor dosis haría de cero "
                      "(solo como guía).")          # CD5-PROD-R1-01: cierto en cada causa (ninguna pieza medible, o piezas bien medidas sin pieza de 0 cGy ni virgen y sin su dosis medida)
NOTA_DEL_REGISTRO = "Calibración guardada: se ve y no se edita. Para cambiarla, «Nueva» y guárdela otra vez con el mismo lote, fecha y energía (la reemplaza)."
CONTEXTO_DEL_ERROR = "Calibración de película (CD.5): guardar"
CONTEXTO_DEL_ERROR_AL_MEDIR = "Calibración de película (CD.5): medir una pieza"


def _fila_vacia(nominal):
    """Una fila de la tabla de piezas: lo que escribió el físico (los dos textos de dosis) y lo que cargó (los bytes, su nombre y su medida de CD.2)."""
    return {"nominal": dibujo.texto_de_la_dosis(nominal), "medida_texto": "", "datos": None, "nombre": None, "medida": None}


class VentanaCurvaDosis(QWidget):
    """La ventana de calibración. `usuario`: el nombre del usuario de la sesión (el texto con que se audita) o el objeto de usuario (su `_nombre`; el objeto es el que recibe el diálogo del permiso de
    anular). `parent`: la ventana que la abre (se destruye con ella)."""

    def __init__(self, usuario, parent=None):
        super().__init__(parent, Qt.Window)
        self._usuario_de_la_sesion = usuario
        self.usuario = _nombre_del_usuario(usuario)
        self.setWindowTitle(TITULO)
        self.resize(*_tamano_inicial())
        self._construir()
        self._restablecer_estado()

    # ----------------------------------------------------------------------------------------------------- construir

    def _construir(self):
        mpl = get_matplotlib_components()
        raiz = QHBoxLayout(self)
        divisor = QSplitter(Qt.Horizontal)
        raiz.addWidget(divisor)

        izquierda = QWidget()
        col = QVBoxLayout(izquierda)
        grupo = QGroupBox("Calibración")
        rejilla = QGridLayout(grupo)
        self.lote = QLineEdit()
        self.tipo_pelicula = _SelectorSinRueda()
        self.tipo_pelicula.setEditable(True)
        self.fecha_irradiacion = QDateEdit()
        self.fecha_irradiacion.setDisplayFormat("dd/MM/yyyy")
        self.fecha_irradiacion.setCalendarPopup(True)
        self.hora_irradiacion = QLineEdit()
        self.hora_irradiacion.setPlaceholderText("hh:mm")
        self.acelerador = _SelectorSinRueda()
        self.acelerador.setEditable(True)
        self.energia = _SelectorSinRueda()
        self.energia.setEditable(True)
        self.profundidad = QLineEdit()
        self.profundidad.setPlaceholderText("3")
        self.dfs = QLineEdit()
        self.dfs.setPlaceholderText("100")
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("10 × 10")
        self.camara = _SelectorSinRueda()
        self.electrometro = _SelectorSinRueda()
        self.u_dosis = QLineEdit()
        self.u_dosis.setPlaceholderText("vacía: la U dice que es solo la de la curva y la película")
        self.u_dosis.textChanged.connect(lambda *_: self._al_cambiar_la_incertidumbre())          # la incertidumbre declarada entra al ajuste (la U de DC10): la curva se vuelve a ajustar
        self.escaner = QLineEdit()
        self.modo = _SelectorSinRueda()
        for texto, valor in MODOS:
            self.modo.addItem(texto, valor)
        self.observaciones = QLineEdit()
        campos = (("Lote", self.lote), ("Tipo de película", self.tipo_pelicula), ("Fecha de irradiación", self.fecha_irradiacion), ("Hora de irradiación", self.hora_irradiacion),
                  ("Acelerador", self.acelerador), ("Energía", self.energia), ("Profundidad [cm]", self.profundidad), ("DFS [cm]", self.dfs), ("Campo [cm × cm]", self.campo),
                  ("Cámara", self.camara), ("Electrómetro", self.electrometro), ("Incertidumbre de la dosis medida [%] k = 1", self.u_dosis), ("Escáner declarado", self.escaner),
                  ("Modo de escaneo", self.modo), ("Observaciones", self.observaciones))
        for i, (rotulo, widget) in enumerate(campos):
            rejilla.addWidget(QLabel(rotulo), i // 2, 2 * (i % 2))
            rejilla.addWidget(widget, i // 2, 2 * (i % 2) + 1)
        col.addWidget(grupo)
        self.etiqueta_virgen = _recuadro()
        col.addWidget(self.etiqueta_virgen)
        self.tabla_piezas = _nueva_tabla(dibujo.COLUMNAS_DE_LAS_PIEZAS)
        self.tabla_piezas.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed)
        self.tabla_piezas.itemChanged.connect(lambda item: self._al_editar_celda(item))
        col.addWidget(self.tabla_piezas, 1)
        botones = QHBoxLayout()
        self.boton_agregar = QPushButton("Agregar dosis")
        self.boton_nueva = QPushButton("Nueva")
        self.boton_abrir = QPushButton("Abrir...")
        self.boton_guardar = QPushButton("Guardar")
        self.boton_anular = QPushButton("Anular")
        for b in (self.boton_agregar, self.boton_nueva, self.boton_abrir, self.boton_guardar, self.boton_anular):
            botones.addWidget(b)
        self.boton_agregar.clicked.connect(lambda *_: self._al_agregar())
        self.boton_nueva.clicked.connect(lambda *_: self._al_nueva())
        self.boton_abrir.clicked.connect(lambda *_: self._al_abrir())
        self.boton_guardar.clicked.connect(lambda *_: self._al_guardar())
        self.boton_anular.clicked.connect(lambda *_: self._al_anular())
        col.addLayout(botones)
        self.indicador = QLabel(TEXTO_MIDIENDO)
        col.addWidget(self.indicador)
        self.etiqueta_registro = _recuadro()
        col.addWidget(self.etiqueta_registro)
        divisor.addWidget(izquierda)

        derecha = QWidget()
        col2 = QVBoxLayout(derecha)
        contenedor, self.figura, self.lienzo, self.barra = _nuevo_lienzo(mpl, 420)
        rejilla_figura = self.figura.add_gridspec(2, 1, height_ratios=(3, 1))
        self.eje_curva = self.figura.add_subplot(rejilla_figura[0])
        self.eje_residuos = self.figura.add_subplot(rejilla_figura[1])
        col2.addWidget(contenedor, 3)
        self.tabla_curva = _nueva_tabla(dibujo.COLUMNAS_DE_LA_CURVA)
        col2.addWidget(self.tabla_curva, 1)
        self.etiqueta_curva = _recuadro()
        col2.addWidget(self.etiqueta_curva)
        divisor.addWidget(derecha)
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 1)

    # ----------------------------------------------------------------------------------------------------- estado

    @property
    def estado(self):
        return self._estado

    def _restablecer_estado(self):
        """El estado de arranque, y el ÚNICO sitio que lo define: `__init__` lo llama y «Nueva» lo llama otra vez, así que «Nueva» deja una ventana igual a una recién creada."""
        self._estado = ESTADO_NUEVA
        self._registro = None
        self._recalculo = None
        self._curva = None
        self._filas = [_fila_vacia(d) for d in dibujo.PLANTILLA_DE_DOSIS]
        for campo in (self.lote, self.hora_irradiacion, self.profundidad, self.dfs, self.campo, self.u_dosis, self.escaner, self.observaciones):
            campo.blockSignals(True)
            campo.setText("")
            campo.blockSignals(False)
        for menu, opciones in ((self.tipo_pelicula, dibujo.TIPOS_DE_PELICULA), (self.acelerador, ("",) + dibujo.ACELERADORES), (self.energia, dibujo.ENERGIAS)):
            menu.clear()                                  # CD5-PROD-R1-09: lo que el físico escribió y confirmó con Enter entró a la lista del menú; la ventana de arranque no lo tiene
            menu.addItems(opciones)
            menu.setCurrentIndex(0)
            menu.setEditText(opciones[0])
        self.modo.setCurrentIndex(0)
        self.fecha_irradiacion.setDate(QDate.currentDate())
        self._llenar_equipos()
        self.indicador.hide()
        _poner_texto(self.etiqueta_registro, "")
        self._leer_la_virgen()
        self._actualizar()

    def _editable(self, si):
        for w in (self.lote, self.tipo_pelicula, self.fecha_irradiacion, self.hora_irradiacion, self.acelerador, self.energia, self.profundidad, self.dfs, self.campo, self.camara,
                  self.electrometro, self.u_dosis, self.escaner, self.modo, self.observaciones, self.boton_agregar):
            w.setEnabled(si)
        self.tabla_piezas.setEditTriggers((QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed) if si else QAbstractItemView.NoEditTriggers)

    def _llenar_equipos(self):
        """Los combos de la cámara y del electrómetro: una entrada por calibración ACTIVA del catálogo (DA-12, DA-22), con su id como dato; el catálogo solo posiciona el combo (DP-105)."""
        problemas = []
        for combo, tipo, vacio in ((self.camara, TIPO_CAMARA, SIN_CAMARA), (self.electrometro, TIPO_ELECTROMETRO, SIN_ELECTROMETRO)):
            combo.clear()
            combo.addItem(vacio, None)
            try:
                for modelo in EquiposService.modelos_actuales(tipo):
                    for id_, serie, fecha, _tipo in EquiposService.calibraciones_activas(tipo, modelo):
                        combo.addItem(f"{dibujo.texto_seguro(modelo)} {dibujo.texto_seguro(serie)} (calibración {dibujo.texto_seguro(fecha)})", id_)
            except Exception as error:                       # el catálogo no se puede leer: se dice y la calibración se puede guardar sin equipo
                problemas.append(f"No se pudo leer el catálogo de equipos ({tipo}): {error}")
            combo.setCurrentIndex(0)
        self._aviso_de_los_equipos = " ".join(problemas)

    def _leer_la_virgen(self):
        """La película virgen montada junto a la base (OD.1): la que lee la ventana mensual, por la misma función."""
        try:
            self._referencia_virgen = pel.leer_referencia_virgen(os.path.dirname(conection.ruta_base_datos()))
            self._aviso_virgen = ""
        except (ValueError, OSError) as error:
            self._referencia_virgen = None
            self._aviso_virgen = str(error)

    def _virgen_utilizable(self):
        r = self._referencia_virgen
        return r if r is not None and r.estado == "ok" else None

    def _con_espera(self, texto, funcion):
        """Indicador visible, cursor de espera y `try/finally`: el cursor se restaura aunque la medición o el guardado fallen."""
        self.indicador.setText(texto)
        self.indicador.show()
        self.indicador.repaint()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return funcion()
        finally:
            QApplication.restoreOverrideCursor()
            self.indicador.hide()
            self.indicador.setText(TEXTO_MIDIENDO)

    # ----------------------------------------------------------------------------------------------------- medir y ajustar: el MISMO camino que `guardar` del servicio (CD5-D1)

    def _medir_la_pieza(self, datos, nombre):
        return pel.medir_pieza_uniforme(datos, copy.deepcopy(VALORES_DE_LA_GEOMETRIA), nombre, date.today().isoformat(), escala="declarada")

    def _piezas_de_la_pantalla(self):
        """(piezas de CD.3, problemas): una por fila con imagen, con el orden de la fila (1, 2, ...) y sus dosis como NÚMEROS; una dosis que no es un número es un problema y esa fila no entra."""
        piezas, problemas = [], []
        for orden, fila in enumerate(self._filas, 1):
            if fila["medida"] is None:
                continue
            nominal, p1 = dibujo.leer_numero(fila["nominal"])
            medida, p2 = dibujo.leer_numero(fila["medida_texto"])
            if p1 or nominal is None or nominal < 0:
                problemas.append(f"la dosis nominal de la fila {orden} {p1 or 'debe ser un número de 0 o más'}")
                continue
            if p2:
                problemas.append(f"la dosis medida de la fila {orden} {p2}")
                continue
            piezas.append(motor.pieza_de_calibracion(orden, nominal, medida, fila["medida"]))
        return piezas, problemas

    def _incertidumbre(self):
        valor, problema = dibujo.leer_numero(self.u_dosis.text())
        return valor, (f"la incertidumbre de la dosis medida {problema}" if problema else None)

    def _ajustar(self):
        piezas, problemas = self._piezas_de_la_pantalla()
        u, problema = self._incertidumbre()
        if problema:
            problemas.append(problema)
        curva = motor.ajustar(piezas, virgen=self._virgen_utilizable(), u_dosis_medida_pct=u) if piezas else None
        return curva, problemas

    # ----------------------------------------------------------------------------------------------------- pintar

    def _actualizar(self):
        """Vuelve a ajustar (si la calibración no es una guardada) y pinta la tabla, el gráfico, la tabla de la curva y las líneas."""
        problemas = []
        if self._estado == ESTADO_NUEVA:
            self._curva, problemas = self._ajustar()
        self._editable(self._estado == ESTADO_NUEVA)
        self._llenar_la_tabla_de_piezas()
        self._pintar_la_curva(problemas)
        self.boton_guardar.setEnabled(self._estado == ESTADO_NUEVA and any(f["medida"] is not None for f in self._filas))
        self.boton_anular.setEnabled(self._estado == ESTADO_REGISTRO and bool(self._registro) and self._registro.get("activo") == 1)
        self.boton_abrir.setEnabled(True)
        self.boton_nueva.setEnabled(True)

    def _pieza_de_la_curva(self, orden):
        if self._curva is None:
            return None
        return next((p for p in self._curva.piezas if p.orden == orden), None)

    def _llenar_la_tabla_de_piezas(self):
        t = self.tabla_piezas
        nueva = self._estado == ESTADO_NUEVA
        t.blockSignals(True)
        try:
            t.setRowCount(len(self._filas))
            for i, fila in enumerate(self._filas):
                orden = fila.get("orden", i + 1)          # una calibración abierta trae el orden guardado; una nueva, el de la fila
                nominal, _p = dibujo.leer_numero(fila["nominal"])
                celdas = {dibujo.COLUMNA_NOMINAL: fila["nominal"], dibujo.COLUMNA_ARCHIVO: dibujo.texto_del_archivo(fila["nombre"], fila["datos"], nominal),
                          dibujo.COLUMNA_MEDIDA: fila["medida_texto"]}
                pieza = self._pieza_de_la_curva(orden) if fila["medida"] is not None else None
                for c, columna in dibujo.COLUMNA_DE_LA_CAPA.items():
                    celdas[columna] = dibujo.texto_de_la_capa_de_la_pieza(pieza, c, self._curva)
                for columna, texto in celdas.items():
                    item = QTableWidgetItem(texto)
                    item.setToolTip(texto)
                    editable = nueva and columna in (dibujo.COLUMNA_NOMINAL, dibujo.COLUMNA_MEDIDA)
                    item.setFlags((item.flags() | Qt.ItemIsEditable) if editable else (item.flags() & ~Qt.ItemIsEditable))
                    t.setItem(i, columna, item)
                cargar = QPushButton("Cargar imagen...")
                cargar.setEnabled(nueva)
                cargar.clicked.connect(lambda *_, k=i: self._al_cargar(k))
                t.setCellWidget(i, dibujo.COLUMNA_CARGAR, cargar)
                quitar = QPushButton("Quitar")
                quitar.setEnabled(nueva)
                quitar.clicked.connect(lambda *_, k=i: self._al_quitar(k))
                t.setCellWidget(i, dibujo.COLUMNA_QUITAR, quitar)
        finally:
            t.blockSignals(False)

    def _pintar_la_curva(self, problemas):
        curva = self._curva
        if curva is None:
            dibujo.dibujar_vacio(self.eje_curva, self.eje_residuos, SIN_CURVA)
            _llenar_tabla(self.tabla_curva, [])
        else:
            dibujo.dibujar_curva(self.eje_curva, curva)
            dibujo.dibujar_residuos(self.eje_residuos, curva)
            _llenar_tabla(self.tabla_curva, dibujo.filas_de_la_curva(curva))
        self.lienzo.draw_idle()
        _poner_texto(self.etiqueta_virgen, dibujo.texto_de_la_virgen(self._referencia_virgen if self._estado == ESTADO_NUEVA else None, self._aviso_virgen, curva)
                     if self._estado == ESTADO_NUEVA else self._texto_de_la_virgen_guardada())
        lineas = [dibujo.texto_del_cero(curva)] if curva is not None else []
        lineas += [f"Aviso: {a}." for a in (curva.avisos if curva is not None else ())]
        lineas += [f"No entra en la curva: {p}." for p in problemas]
        if self._aviso_de_los_equipos:
            lineas.append(self._aviso_de_los_equipos)
        _poner_texto(self.etiqueta_curva, "\n".join(lineas))

    def _texto_de_la_virgen_guardada(self):
        copia = (self._registro or {}).get("virgen")
        if copia is None:
            return "Película virgen montada al calibrar: ninguna."
        pr = copia.get("procedencia") or {}
        return f"Película virgen montada al calibrar (su copia guardada): «{pr.get('archivo') or 'sin nombre'}» ({pr.get('fecha_escaneo') or pr.get('fecha_calculo') or 'sin fecha'})."

    # ----------------------------------------------------------------------------------------------------- la tabla de piezas

    @_protegido("Dosis")
    def _al_editar_celda(self, item):
        if self._estado != ESTADO_NUEVA:
            return
        fila = self._filas[item.row()]
        if item.column() == dibujo.COLUMNA_NOMINAL:
            fila["nominal"] = item.text()
        elif item.column() == dibujo.COLUMNA_MEDIDA:
            fila["medida_texto"] = item.text()
        else:
            return
        self._actualizar()

    @_protegido("Incertidumbre")
    def _al_cambiar_la_incertidumbre(self):
        if self._estado == ESTADO_NUEVA:
            self._actualizar()

    @_protegido("Agregar dosis")
    def _al_agregar(self):
        self._filas.append(_fila_vacia(None))
        self._actualizar()

    @_protegido("Quitar")
    def _al_quitar(self, indice):
        if self._estado != ESTADO_NUEVA or not 0 <= indice < len(self._filas):
            return
        del self._filas[indice]
        self._actualizar()

    @_protegido("Cargar imagen")
    def _al_cargar(self, indice):
        ruta, _filtro = QFileDialog.getOpenFileName(self, "Cargar la imagen de la pieza", "", FILTRO_IMAGENES)
        if not ruta:
            return
        try:
            with open(ruta, "rb") as archivo:
                datos = archivo.read()
        except OSError as error:
            QMessageBox.warning(self, "Cargar imagen", f"No se pudo leer el archivo: {error}")
            return
        self.cargar_pieza(indice, datos, os.path.basename(ruta.replace("\\", "/")).strip())

    def cargar_pieza(self, indice, datos, nombre):
        """Mide la pieza de la fila `indice` (CD.2, con el cursor de espera) y vuelve a ajustar. Si la medición falla, se dice y la fila queda como estaba (el cursor ya se restauró)."""
        if self._estado != ESTADO_NUEVA or not 0 <= indice < len(self._filas):
            return False
        try:
            medida = self._con_espera(TEXTO_MIDIENDO, lambda: self._medir_la_pieza(datos, nombre))
        except ValueError as error:
            QMessageBox.warning(self, "Cargar imagen", f"No se pudo medir la pieza «{nombre}»: {error}")
            return False
        except Exception as error:                       # CD5-PROD-R1-08: CD.2 promete no lanzar por el contenido, pero una imagen de 40 píxeles o menos hace lanzar un ZeroDivisionError; se dice con la pieza y la causa queda en error_log.txt
            detalle = "La causa quedó en error_log.txt." if registrar_error(CONTEXTO_DEL_ERROR_AL_MEDIR, error, f"pieza «{nombre}»") else "No se pudo escribir la causa en error_log.txt: anote este aviso."
            QMessageBox.warning(self, "Cargar imagen", f"No se pudo medir la pieza «{nombre}»: error inesperado ({type(error).__name__}: {error}). {detalle}")
            return False
        fila = self._filas[indice]
        fila.update(datos=bytes(datos), nombre=nombre, medida=medida)
        self._actualizar()
        return True

    # ----------------------------------------------------------------------------------------------------- guardar

    def _copia_del_equipo(self, combo, que):
        """La copia (modelo, serie, factor) y el puntero del equipo elegido (DA-13), o None si no se eligió ninguno. El factor es el del catálogo hoy, como número (o nada si no lo es)."""
        equipo_id = combo.currentData()
        if equipo_id is None:
            return None, None
        equipo = EquiposService.obtener_por_id(equipo_id)
        if equipo is None:
            return None, f"{que} elegido ya no está en el catálogo"
        factor = dibujo.numero_del_catalogo(equipo.get("calibr_fact"))          # CD5-PR-7: el número del catálogo tal cual, no su texto de seis cifras
        return {"modelo": None if equipo.get("model") is None else str(equipo["model"]), "serie": None if equipo.get("serie") is None else str(equipo["serie"]),
                "factor": factor, "equipo_id": int(equipo_id)}, None

    def _texto_o_nada(self, texto):
        limpio = (texto or "").strip()
        return limpio or None

    def encabezado(self):
        """(encabezado para `services.curva_dosis.guardar`, problemas). Los opcionales vacíos van como None (no ''), los números como números y las condiciones solo con lo que el físico escribió."""
        problemas = []
        condiciones = {}
        for clave, campo, que in (("profundidad_cm", self.profundidad, "la profundidad"), ("dfs_cm", self.dfs, "la DFS")):
            valor, problema = dibujo.leer_numero(campo.text())
            if problema:
                problemas.append(f"{que} {problema}")
            elif valor is not None:
                condiciones[clave] = valor
        if self._texto_o_nada(self.campo.text()):
            condiciones["campo_cm"] = self.campo.text().strip()
        hora = self._texto_o_nada(self.hora_irradiacion.text())
        if hora:
            partes = hora.split(":")
            if len(partes) != 2 or not all(p.isdecimal() for p in partes) or not (0 <= int(partes[0]) <= 23 and 0 <= int(partes[1]) <= 59):
                problemas.append(f"la hora de irradiación debe ser hh:mm, no {hora!r}")
            else:
                condiciones["hora_irradiacion"] = f"{int(partes[0]):02d}:{int(partes[1]):02d}"
        u, problema = self._incertidumbre()
        if problema:
            problemas.append(problema)
        camara, p1 = self._copia_del_equipo(self.camara, "la cámara")
        electrometro, p2 = self._copia_del_equipo(self.electrometro, "el electrómetro")
        problemas += [p for p in (p1, p2) if p]
        encabezado = {"lote": self.lote.text().strip(), "tipo_pelicula": self.tipo_pelicula.currentText().strip(), "fecha_irradiacion": self.fecha_irradiacion.date().toString("yyyy-MM-dd"),
                      "energia": self.energia.currentText().strip(), "acelerador": self._texto_o_nada(self.acelerador.currentText()), "condiciones": condiciones or None,
                      "camara": camara, "electrometro": electrometro, "u_dosis_medida_pct": u, "escaner_declarado": self._texto_o_nada(self.escaner.text()),
                      "modo_de_escaneo": self.modo.currentData(), "observaciones": self._texto_o_nada(self.observaciones.text())}
        return encabezado, problemas

    def piezas(self):
        """(piezas para `services.curva_dosis.guardar`, problemas): las filas con imagen, con el orden de la fila y sus dosis como NÚMEROS (la medida, None si falta: la curva queda «incompleta»)."""
        piezas, problemas = [], []
        for orden, fila in enumerate(self._filas, 1):
            if fila["datos"] is None:
                continue
            nominal, p1 = dibujo.leer_numero(fila["nominal"])
            medida, p2 = dibujo.leer_numero(fila["medida_texto"])
            if p1 or nominal is None:
                problemas.append(f"la dosis nominal de la fila {orden} {p1 or 'falta'}")
            if p2:
                problemas.append(f"la dosis medida de la fila {orden} {p2}")
            piezas.append({"orden": orden, "dosis_nominal_cgy": nominal, "dosis_medida_cgy": medida, "datos": fila["datos"], "nombre_archivo": fila["nombre"]})
        return piezas, problemas

    def _lo_que_hay_que_confirmar(self, curva, piezas, encabezado):
        lineas = []
        no_validas = [f"{dibujo.NOMBRE_EN_EL_GRAFICO[c]}: {curva.estado(c)}" for c in dibujo.CAPAS if curva.estado(c) != motor.ESTADO_VALIDA]
        if no_validas:
            lineas.append("Estas capas no salen «válida»: " + "; ".join(no_validas) + ".")
        sin_medida = [f"fila {p['orden']} ({dibujo.texto_de_la_dosis(p['dosis_nominal_cgy'])} cGy)" for p in piezas if p["dosis_medida_cgy"] is None and p["dosis_nominal_cgy"] != 0]
        if sin_medida:
            lineas.append("Falta la dosis medida de: " + ", ".join(sin_medida) + ".")
        if curva.cero["fuente"] != "piezas_de_0_cgy":
            lineas.append(f"La curva no tiene una pieza de 0 cGy: {curva.cero['detalle']}.")
        anterior = dibujo.la_calibracion_que_reemplaza(svc.listar(), encabezado)          # CD5-PROD-R1-02: el servicio anula la vigente de la misma clave de bloque; se pregunta ANTES (como las diarias, DA-41)
        if anterior is not None:
            lineas.append(dibujo.texto_de_la_que_reemplaza(anterior))
        return lineas

    @_protegido("Guardar")
    def _al_guardar(self):
        if self._estado != ESTADO_NUEVA:
            return
        encabezado, problemas = self.encabezado()
        piezas, problemas_de_las_piezas = self.piezas()
        problemas += problemas_de_las_piezas
        if problemas:
            QMessageBox.warning(self, "Guardar", "No se guardó: " + "; ".join(problemas) + ".")
            return
        curva = self._curva
        if curva is None or curva.cero is None:
            QMessageBox.warning(self, "Guardar", NO_GUARDA_SIN_CERO)
            return
        confirmar = self._lo_que_hay_que_confirmar(curva, piezas, encabezado)
        if confirmar and QMessageBox.question(self, "Guardar", "\n".join(confirmar + [PREGUNTA_GUARDAR]), QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            nuevo = self._con_espera(TEXTO_GUARDANDO, lambda: svc.guardar(self.usuario, encabezado, piezas, virgen=self._virgen_utilizable()))
        except svc.CurvaDosisError as error:                 # lo que el servicio rechaza, TAL CUAL (CD.4)
            QMessageBox.warning(self, "Guardar", f"No se guardó: {error}")
            return
        except Exception as error:                           # lo inesperado (la base ocupada, la red): traducido, y la causa en error_log.txt (GI.6)
            mensaje = traducir_error_de_guardado(error, "La calibración", registrar_error(CONTEXTO_DEL_ERROR, error))
            QMessageBox.warning(self, mensaje.titulo, mensaje.texto)
            return
        QMessageBox.information(self, "Guardar", f"Calibración guardada: lote {encabezado['lote']}, irradiada el {encabezado['fecha_irradiacion']}, {encabezado['energia']} (id {nuevo}).")
        self.abrir(nuevo)

    # ----------------------------------------------------------------------------------------------------- abrir, anular y nueva

    @_protegido("Abrir")
    def _al_abrir(self):
        lista = svc.listar()
        if not lista:
            QMessageBox.information(self, "Abrir", "No hay calibraciones guardadas.")
            return
        textos = [dibujo.texto_de_una_calibracion(f) for f in lista]
        elegido, aceptado = QInputDialog.getItem(self, "Abrir", "Calibración guardada:", textos, 0, False)
        if aceptado and elegido in textos:
            self.abrir(lista[textos.index(elegido)]["id"])

    @_protegido("Abrir", por_defecto=False)
    def abrir(self, id_calibracion):
        """Abre una calibración guardada para VERLA (no se edita): su copia del ajuste (DA-81), sus piezas y su encabezado; vuelve a ajustarla (`recalcular`) y dice lo que no coincide, los escaneos que
        faltan y las copias que ya no coinciden, cada cosa aparte. Devuelve True si se abrió."""
        try:
            registro = svc.leer(int(id_calibracion))
        except svc.CurvaDosisError as error:
            QMessageBox.warning(self, "Abrir", f"No se pudo abrir la calibración: {error}")
            return False
        if registro is None:
            QMessageBox.warning(self, "Abrir", f"No hay ninguna calibración con el id {id_calibracion}.")
            return False
        curva = motor.curva_desde_dict(registro["ajuste"])
        lineas = []
        try:
            recalculo = self._con_espera(TEXTO_ABRIENDO, lambda: svc.recalcular(registro))
        except svc.CurvaDosisError as error:
            recalculo = None
            lineas.append(str(error))
        diferencias = svc.diferencias(registro, recalculo) if recalculo is not None else []
        self._estado = ESTADO_REGISTRO
        self._registro = registro
        self._recalculo = recalculo
        self._curva = curva
        self._poner_el_encabezado(registro)
        self._filas = [{"nominal": dibujo.texto_de_la_dosis(f["dosis_nominal_cgy"]), "medida_texto": dibujo.texto_de_la_dosis(f["dosis_medida_cgy"]), "datos": None,
                        "nombre": f["nombre_archivo"], "medida": True, "orden": f["orden"]} for f in registro["piezas"]]
        self._actualizar()
        estado = "vigente" if registro.get("activo") == 1 else "anulada"
        lineas = [f"Calibración {registro['id']} ({estado}): lote {dibujo.texto_seguro(registro['lote'])}, irradiada el {dibujo.texto_seguro(registro['fecha_irradiacion'])}, "
                  f"guardada por {dibujo.texto_seguro(registro['usuario'])} el {dibujo.texto_seguro(registro['fecha_registro'])}. {NOTA_DEL_REGISTRO}"] + lineas
        lineas += dibujo.texto_de_la_carpeta(recalculo)
        if diferencias:
            lineas.append("Lo recalculado no coincide con lo guardado: " + "; ".join(diferencias) + ".")
        _poner_texto(self.etiqueta_registro, "\n".join(lineas))
        if diferencias:
            QMessageBox.warning(self, "Abrir", "Lo recalculado no coincide con lo guardado:\n" + "\n".join(diferencias))
        return True

    def _poner_el_encabezado(self, registro):
        """El encabezado GUARDADO en los campos (que quedan sin editar): los equipos, por su COPIA (DA-13, DP-105), nunca por lo que diga el catálogo hoy."""
        condiciones = registro.get("condiciones") or {}
        self.lote.setText(dibujo.texto_seguro(registro.get("lote")))
        self.tipo_pelicula.setEditText(dibujo.texto_seguro(registro.get("tipo_pelicula")))
        self.fecha_irradiacion.setDate(QDate.fromString(str(registro.get("fecha_irradiacion")), "yyyy-MM-dd"))
        self.hora_irradiacion.setText(dibujo.texto_seguro(condiciones.get("hora_irradiacion")))
        self.acelerador.setEditText(dibujo.texto_seguro(registro.get("acelerador")))
        self.energia.setEditText(dibujo.texto_seguro(registro.get("energia")))
        self.profundidad.setText(dibujo.texto_seguro(condiciones.get("profundidad_cm")))
        self.dfs.setText(dibujo.texto_seguro(condiciones.get("dfs_cm")))
        self.campo.setText(dibujo.texto_seguro(condiciones.get("campo_cm")))
        self.u_dosis.setText(dibujo.texto_seguro(registro.get("u_dosis_medida_pct")))
        self.escaner.setText(dibujo.texto_seguro((registro.get("cadena_de_captura") or {}).get("escaner_declarado")))
        modo = (registro.get("cadena_de_captura") or {}).get("modo_de_escaneo")
        self.modo.setCurrentIndex(next((i for i, (_t, v) in enumerate(MODOS) if v == modo), 0))
        self.observaciones.setText(dibujo.texto_seguro(registro.get("observaciones")))
        for combo, prefijo, vacio in ((self.camara, "camara", SIN_CAMARA), (self.electrometro, "electrometro", SIN_ELECTROMETRO)):
            combo.clear()
            if registro.get(f"{prefijo}_modelo") is None and registro.get(f"{prefijo}_serie") is None:
                combo.addItem(vacio, None)
            else:
                combo.addItem(f"{dibujo.texto_seguro(registro.get(f'{prefijo}_modelo'))} {dibujo.texto_seguro(registro.get(f'{prefijo}_serie'))} "
                              f"(factor {dibujo.texto_seguro(registro.get(f'{prefijo}_factor'))}; copia guardada)", None)          # sin id: lo abierto no se guarda (DA-13: la copia manda)

    @_protegido("Anular")
    def _al_anular(self):
        if self._estado != ESTADO_REGISTRO or not self._registro or self._registro.get("activo") != 1:
            return
        id_calibracion = self._registro["id"]
        if QMessageBox.question(self, "Anular", f"¿Anular la calibración {id_calibracion} (lote {dibujo.texto_seguro(self._registro['lote'])})? Queda su rastro y deja de ser una curva vigente.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if DialogAdminPermisoEliminar(self._usuario_de_la_sesion).exec() != QDialog.DialogCode.Accepted:
            return
        try:
            anulada = svc.anular(id_calibracion, self.usuario)
        except svc.CurvaDosisError as error:
            QMessageBox.warning(self, "Anular", f"No se anuló: {error}")
            return
        if not anulada:
            QMessageBox.warning(self, "Anular", "Esa calibración ya estaba anulada o ya no existe.")
        self.abrir(id_calibracion)

    @_protegido("Nueva")
    def _al_nueva(self):
        if self._estado == ESTADO_NUEVA and any(f["datos"] is not None for f in self._filas):
            if QMessageBox.question(self, "Nueva", PREGUNTA_NUEVA, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
        self._restablecer_estado()
