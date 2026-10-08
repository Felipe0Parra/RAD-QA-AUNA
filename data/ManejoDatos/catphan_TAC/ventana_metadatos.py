"""A.3 (PLAN_HANDOFF_IMAGENES_22-09.md, reformulada el 23-09 a pedido del
físico): una ventana de metadatos en CADA carga de una carpeta DICOM.

El físico pidió *"que al seleccionar la carpeta, además de mostrar el cuadro de
los cortes recomendados, primero muestre una ventana emergente con la
información de metadatos del equipo"*. La ventana junta en un solo sitio lo
que el plan repartía en dos avisos (el modal de identidad de A.2 y la franja de
carpeta mixta de A.3), y lo hace ANTES de cualquier análisis:

  1. EQUIPO -- lo que el propio DICOM dice: fabricante, modelo, estación, número
     de serie, software.
  2. ADQUISICION -- descripción de la serie, fecha, kV, mA, mAs, CTDIvol,
     espesor, kernel/filtro, FOV, píxel, número de cortes.
  3. PROTOCOLO EXIGIDO para el equipo seleccionado (catálogo de A.2), al lado y
     fila por fila. Si las imágenes son de otro equipo, la ventana lo dice
     arriba y en rojo.
  4. LA CARPETA -- series descartadas (y de qué modelo), archivos que no son
     imagen CT, paso no uniforme y (CD.3) lo que la carga dejó fuera: archivos
     .dcm que no se pudieron leer y cortes de CT cuyo archivo no termina en .dcm.
     Dos niveles: informativo (un RTSTRUCT es normal y no debe gritar) y
     atención (más de una serie; archivos ilegibles; cortes de la serie que
     faltan por llamarse sin .dcm).

Botones Continuar y Cancelar. Cancelar no carga nada. Continuar con alguna fila
que no cumple pide una confirmación explícita; la desviación queda archivada
con cada prueba (A.2). Una adquisición que no cumple el protocolo NO bloquea: la
toma no la controla la aplicación.

DA-18: sin símbolos de correcto/incorrecto en los textos del usuario -- los
estados se dicen con palabras ("Cumple", "No cumple", "No se exige") y color.

El CONTENIDO se arma en una función pura (`construir_modelo_ventana`), probable
sin Qt; el diálogo solo lo dibuja. La decisión se puede tomar sin una persona
(Trampa 2 de CLAUDE.md: un `exec_()` sin nadie que lo conteste cuelga la suite):
`VisualizadorDicom.confirmador_de_carga` es reemplazable por instancia.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from analisisImagenes.catphan.descripcion import (  # noqa: F401  (NO_PUBLICADO: se sigue importando desde aquí)
    NO_PUBLICADO, filas_adquisicion, filas_identidad, filas_medidas)
from analisisImagenes.catphan.escala import CLAVE_EN_ADQUISICION, nota_escala
from analisisImagenes.catphan.obligatorios import faltantes_de, redondear_espesor
from analisisImagenes.catphan.protocolos import (
    COINCIDE, NO_IDENTIFICADO, OTRO_EQUIPO, ROTULO_FUERA_DE_PROTOCOLO, SIN_EQUIPO, SIN_PROTOCOLO,
    comparar_con_protocolo, texto_encontrado, texto_exigido)

# Niveles de los avisos de la carpeta y del banner.
INFO = "info"
ATENCION = "atencion"
ERROR = "error"
AVISO = "aviso"

# Estados de una fila de protocolo (palabras, no símbolos: DA-18).
CUMPLE = "Cumple"
NO_CUMPLE = "No cumple"
NO_SE_EXIGE = "No se exige"

_COLOR = {
    CUMPLE: "#1e8449",
    NO_CUMPLE: "#c0392b",
    NO_SE_EXIGE: "#7f8c8d",
    ERROR: "#c0392b",
    AVISO: "#b9770e",
    ATENCION: "#b9770e",
    INFO: "#566573",
}


@dataclass
class FilaVentana:
    etiqueta: str
    exigido: str
    encontrado: str
    estado: str  # CUMPLE | NO_CUMPLE | NO_SE_EXIGE


@dataclass
class ModeloVentana:
    equipo_seleccionado: Optional[str]
    identidad: list = field(default_factory=list)        # [(etiqueta, valor)]
    adquisicion: list = field(default_factory=list)      # [(etiqueta, valor)]
    banner: Optional[tuple] = None                       # (nivel, texto) o None
    protocolo_titulo: str = "Protocolo exigido"
    protocolo: list = field(default_factory=list)        # [FilaVentana]
    protocolo_nota: Optional[str] = None
    carpeta: list = field(default_factory=list)          # [(nivel, texto)]
    requiere_confirmacion: bool = False
    resumen_desviacion: Optional[str] = None
    identidad_estado: str = SIN_EQUIPO
    aviso_guardado: Optional[str] = None                 # GI.4: kV, mA o espesor que la serie no publica (o publica en 0): no se podrá guardar

    def texto_confirmacion(self) -> str:
        cuerpo = (self.resumen_desviacion or "").rstrip(".")
        if self.aviso_guardado:
            # GI.4: «se puede analizar igual» sería cierto a medias -- analizar sí, guardar no.
            desviacion = f"\n\n{cuerpo}." if cuerpo else ""
            return f"{self.aviso_guardado}{desviacion}\n\n¿Desea continuar?"
        if self.identidad_estado == OTRO_EQUIPO:
            cola = (f"Si continúa, las pruebas se guardarán como de '{self.equipo_seleccionado}', "
                    f"con la marca de desviación.")
        else:
            cola = ("Se puede analizar igual, pero cada prueba quedará marcada con esa desviación "
                    "y no será comparable con la línea base.")
        return f"{cuerpo}.\n\n{cola}\n\n¿Desea continuar?"


def _ejemplos(nombres) -> str:
    """Hasta tres nombres entre comillas y «y N más» si hay más."""
    return ", ".join(f"'{n}'" for n in nombres[:3]) + (f" y {len(nombres) - 3} más" if len(nombres) > 3 else "")


def _carpeta(vol, adq: dict) -> list:
    filas = []
    n_cortes = adq.get("n_cortes")
    if n_cortes is not None:
        filas.append((INFO, f"Se leyeron {n_cortes} cortes de una sola serie."))

    detalle = getattr(vol, "detalle_series_descartadas", None) or {}
    descartadas = getattr(vol, "series_descartadas", None) or {}
    modelo_principal = adq.get("modelo")
    for uid, n in descartadas.items():
        d = detalle.get(uid) or {}
        origen = " / ".join(str(p) for p in (d.get("modelo"), d.get("estacion")) if p)
        descripcion = d.get("descripcion_serie")
        detalle_txt = ", ".join(p for p in (origen, descripcion) if p)
        if d.get("modelo") and modelo_principal and d.get("modelo") != modelo_principal:
            filas.append((ATENCION,
                          f"Carpeta mixta de equipos distintos: se descartaron {n} cortes de otra serie "
                          f"({detalle_txt}); se analiza la serie de {modelo_principal}."))
        else:
            filas.append((ATENCION,
                          f"La carpeta trae más de una serie: se descartaron {n} cortes de otra serie"
                          + (f" ({detalle_txt})." if detalle_txt else ".")))

    nota = nota_escala(adq.get(CLAVE_EN_ADQUISICION))
    if nota:
        filas.append((INFO, nota))                       # B.3: no se corrigen las imágenes: se declara su escala

    no_imagen = getattr(vol, "no_imagen", 0) or 0
    if no_imagen:
        filas.append((INFO, f"{no_imagen} archivo(s) que no son imagen CT (por ejemplo, un RTSTRUCT) "
                            f"se ignoraron: es normal."))
    # CD.3 (B6): lo que la carga dejo fuera y NO es normal -- la serie puede estar incompleta
    ilegibles = getattr(vol, "ilegibles", 0) or 0
    if ilegibles:
        filas.append((ATENCION, f"{ilegibles} archivo(s) .dcm no se pudieron leer (dañados o incompletos) y se ignoraron: la serie puede estar incompleta."))
    sin_extension = list(getattr(vol, "sin_extension", None) or [])
    if sin_extension:
        filas.append((ATENCION, f"{len(sin_extension)} corte(s) de CT no se leyeron porque su archivo no termina en .dcm ({_ejemplos(sin_extension)}): la serie puede estar incompleta. "
                                "Renómbrelos con la extensión .dcm y cargue la carpeta de nuevo."))
    otras = list(getattr(vol, "sin_extension_otras", None) or [])
    if otras:
        filas.append((INFO, f"{len(otras)} corte(s) de CT de otra serie tampoco se leyeron porque su archivo no termina en .dcm ({_ejemplos(otras)}): "
                            "no pertenecen a la serie que se carga."))
    for aviso in getattr(vol, "avisos", None) or []:
        filas.append((ATENCION, str(aviso)))
    return filas


def construir_modelo_ventana(vol, equipo_seleccionado: Optional[str]) -> ModeloVentana:
    """El contenido de la ventana para `vol` (un `DicomVolume` o cualquier
    objeto con `adquisicion`, `series_descartadas`, `detalle_series_descartadas`,
    `no_imagen` y `avisos`) frente al `equipo_seleccionado`. Función pura."""
    adq = getattr(vol, "adquisicion", None) or {}
    c = comparar_con_protocolo(equipo_seleccionado, adq)

    # E.2: las filas de identidad y de adquisición se definen en `descripcion.py` -- el PDF del
    # informe muestra la MISMA metadata con las mismas etiquetas.
    identidad = filas_identidad(adq)
    # B.3: lo que la aplicación midió en los píxeles (el corrimiento de la escala de HU) va con la adquisición; sin
    # medición (una comparación solo con encabezados) no se muestra la fila.
    adquisicion = filas_adquisicion(adq) + filas_medidas(adq)

    filas = []
    for f in c.filas:
        estado = NO_SE_EXIGE if f.cumple is None else (CUMPLE if f.cumple else NO_CUMPLE)
        filas.append(FilaVentana(f.etiqueta, texto_exigido(f), texto_encontrado(f), estado))

    banner = None
    nota = None
    if c.identidad == OTRO_EQUIPO:
        banner = (ERROR, f"Estas imágenes son de {c.imagenes_de} (equipo identificado: "
                         f"{c.equipo_identificado}) y usted seleccionó {c.equipo_seleccionado}.")
    elif c.identidad == NO_IDENTIFICADO:
        banner = (AVISO, f"No se reconoce el equipo de estas imágenes ({c.imagenes_de}): no se puede "
                         f"confirmar que sean de {c.equipo_seleccionado}.")
    elif c.identidad == SIN_PROTOCOLO:
        banner = (AVISO, f"El equipo seleccionado ({c.equipo_seleccionado}) no tiene protocolo de imagen "
                         f"definido: no hay con qué comparar.")
        nota = "Sin protocolo definido para este equipo."
    elif c.identidad == SIN_EQUIPO:
        nota = "No hay un equipo seleccionado con el que comparar."
    elif c.advertencia_identidad:
        banner = (AVISO, f"Identidad: {c.advertencia_identidad}")

    # GI.4: kV, mA y espesor son obligatorios para guardar (D1): si la serie no los trae, el físico lo sabe ANTES de analizar.
    faltantes = faltantes_de(adq.get("kv"), adq.get("ma"), redondear_espesor(adq.get("espesor_mm")), hay_serie=True)
    aviso_guardado = None
    if faltantes:
        aviso_guardado = ("Con esta serie no se podrá guardar ninguna prueba. " + " ".join(f.texto("esta serie") for f in faltantes)
                          + " Puede analizarla y ver los resultados, pero no guardarlos.")

    requiere = (c.identidad in (OTRO_EQUIPO, NO_IDENTIFICADO) or any(f.cumple is False for f in c.filas)
                or aviso_guardado is not None)
    titulo = (f"Protocolo exigido para {equipo_seleccionado}" if equipo_seleccionado else "Protocolo exigido")

    return ModeloVentana(
        equipo_seleccionado=equipo_seleccionado, identidad=identidad, adquisicion=adquisicion,
        banner=banner, protocolo_titulo=titulo, protocolo=filas, protocolo_nota=nota,
        carpeta=_carpeta(vol, adq), requiere_confirmacion=requiere,
        resumen_desviacion=c.desviacion_texto(), identidad_estado=c.identidad, aviso_guardado=aviso_guardado)


# ---------------------------------------------------------------------------
# El diálogo: solo dibuja el modelo
# ---------------------------------------------------------------------------

def _tabla_clave_valor(pares) -> str:
    filas = "".join(
        f"<tr><td style='padding-right:14px;color:#566573'>{html.escape(k)}</td>"
        f"<td><b>{html.escape(v)}</b></td></tr>" for k, v in pares)
    return f"<table cellspacing='2'>{filas}</table>"


def _tabla_protocolo(filas) -> str:
    cab = ("<tr><th align='left'>Campo</th><th align='left'>Exigido</th>"
           "<th align='left'>Encontrado</th><th align='left'>Estado</th></tr>")
    cuerpo = "".join(
        f"<tr><td style='padding-right:14px'>{html.escape(f.etiqueta)}</td>"
        f"<td style='padding-right:14px'>{html.escape(f.exigido)}</td>"
        f"<td style='padding-right:14px'><b>{html.escape(f.encontrado)}</b></td>"
        f"<td><b style='color:{_COLOR[f.estado]}'>{f.estado}</b></td></tr>" for f in filas)
    return f"<table cellspacing='2'>{cab}{cuerpo}</table>"


def _lista_carpeta(filas) -> str:
    return "".join(
        f"<p style='margin:2px 0;color:{_COLOR[nivel]}'>"
        f"{'<b>Atención: </b>' if nivel == ATENCION else ''}{html.escape(texto)}</p>"
        for nivel, texto in filas)


class VentanaMetadatos(QDialog):
    """La ventana. `exec_()` devuelve `Accepted` (Continuar) o `Rejected`
    (Cancelar); no hay más lógica aquí, para que se pueda decidir con un
    `exec_` sustituido en las pruebas."""

    def __init__(self, parent, modelo: ModeloVentana):
        super().__init__(parent)
        self.modelo = modelo
        self.setWindowTitle("Datos de la adquisición")
        self.setModal(True)
        self.setMinimumWidth(640)

        raiz = QVBoxLayout(self)
        if modelo.banner:
            nivel, texto = modelo.banner
            banner = QLabel(texto)
            banner.setTextFormat(Qt.PlainText)
            banner.setWordWrap(True)
            banner.setObjectName("banner")
            banner.setStyleSheet(
                f"background:{_COLOR[nivel]};color:white;padding:8px;font-weight:bold;")
            raiz.addWidget(banner)

        if modelo.aviso_guardado:
            aviso = QLabel(modelo.aviso_guardado)
            aviso.setTextFormat(Qt.PlainText)
            aviso.setWordWrap(True)
            aviso.setObjectName("aviso_guardado")
            aviso.setStyleSheet(f"background:{_COLOR[ERROR]};color:white;padding:8px;font-weight:bold;")
            raiz.addWidget(aviso)

        contenido = QWidget()
        cuerpo = QVBoxLayout(contenido)
        self._bloques = {}
        self._agregar(cuerpo, "equipo", "Equipo (leído del DICOM)", _tabla_clave_valor(modelo.identidad))
        self._agregar(cuerpo, "adquisicion", "Adquisición", _tabla_clave_valor(modelo.adquisicion))
        if modelo.protocolo:
            proto = _tabla_protocolo(modelo.protocolo)
        else:
            proto = f"<p>{html.escape(modelo.protocolo_nota or '')}</p>"
        self._agregar(cuerpo, "protocolo", modelo.protocolo_titulo, proto)
        self._agregar(cuerpo, "carpeta", "La carpeta", _lista_carpeta(modelo.carpeta))
        cuerpo.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(contenido)
        raiz.addWidget(scroll)

        botones = QHBoxLayout()
        botones.addStretch()
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_continuar = QPushButton("Continuar")
        self.boton_continuar.setDefault(True)
        self.boton_cancelar.clicked.connect(self.reject)
        self.boton_continuar.clicked.connect(self.accept)
        botones.addWidget(self.boton_cancelar)
        botones.addWidget(self.boton_continuar)
        raiz.addLayout(botones)
        self.resize(720, 640)

    def _agregar(self, layout, clave, titulo, html_cuerpo):
        caja = QGroupBox(titulo)
        interior = QVBoxLayout(caja)
        etiqueta = QLabel(html_cuerpo)
        etiqueta.setTextFormat(Qt.RichText)
        etiqueta.setWordWrap(True)
        interior.addWidget(etiqueta)
        layout.addWidget(caja)
        self._bloques[clave] = (titulo, html_cuerpo)

    def texto_visible(self) -> str:
        """Todo el texto que ve el usuario (títulos, banner, cuerpos y botones),
        para que una prueba pueda afirmar sobre él."""
        partes = [self.windowTitle()]
        for etiqueta in self.findChildren(QLabel):
            partes.append(etiqueta.text())
        for caja in self.findChildren(QGroupBox):
            partes.append(caja.title())
        for boton in self.findChildren(QPushButton):
            partes.append(boton.text())
        return "\n".join(partes)


def mostrar_ventana_metadatos(parent, vol, equipo_seleccionado: Optional[str]) -> bool:
    """Muestra la ventana y devuelve `True` si el físico decide continuar.

    Cancelar devuelve `False`. Continuar con alguna fila que no cumple (o con
    imágenes de otro equipo) pide una segunda confirmación explícita, que
    también puede negar; sin filas que incumplan, Continuar basta.
    """
    modelo = construir_modelo_ventana(vol, equipo_seleccionado)
    dialogo = VentanaMetadatos(parent, modelo)
    if dialogo.exec_() != QDialog.Accepted:
        return False
    if not modelo.requiere_confirmacion:
        return True
    respuesta = QMessageBox.question(
        parent, ROTULO_FUERA_DE_PROTOCOLO, modelo.texto_confirmacion(),
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return respuesta == QMessageBox.Yes
