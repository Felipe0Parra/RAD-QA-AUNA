"""E.2 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-82, DA-83, DA-89): la sección «Imagen del campo» del formulario mensual del 600 y del iX.

Hasta E.2 la única entrada del análisis viejo era esta página: el cargador compartido (`imagenUpLoader`) se construía con `analisis=True` y «Aceptar» corría `PruebaMensual600.analizar_imagen`. Ahora la
página tiene el botón «Análisis de la placa», que abre la ventana de E.1 (`VentanaPlacaMensual`); el botón «Analizar la imagen guardada» (DA-89), que carga en esa ventana la imagen que el control ya
tenía guardada, para reparar un control viejo con la herramienta nueva; una línea que dice qué análisis tiene el control; y, debajo, el visor de la imagen vieja como hasta hoy (IM4) pero sin
«Seleccionar Imagen» ni «Aceptar» conectado a nada: ya no hay ningún camino, ni escondido, al análisis anterior.

Qué sabe la línea de estado (cada letra es un hecho sobre el control, no un valor):
  V  el control tiene filas vigentes en `analisis_placa_franjas` (el análisis viejo). Solo se CUENTAN: ningún valor de las tablas `analisis_placa_*` se lee (DA-89: la tabla vieja se desconecta);
  I  tiene imagen en su fila vigente de `preguntas` (`imagen_vigente`, la misma lectura con que el visor pinta);
  N  tiene un análisis nuevo vigente (`services.placa_mensual.leer`, la única puerta a `analisis_placa_mensual`).
La precedencia es N, después V, después I, después nada (`texto_de_la_linea`, la única definición de lo que dice la línea).

La ventana no emite ninguna señal al guardar, así que la línea se vuelve a escribir cuando la ventana se OCULTA o se cierra. La ventana es hija de la página con la bandera `Qt.Window` y se conserva
oculta mientras viva la página (una sola por control; construirla con un análisis guardado cuesta unos 3 s). «Cerrar control» destruye la página y, con ella, la ventana. «Inicio» NO destruye la página
(la ventana principal queda viva y oculta): por eso un vigilante, hijo de la ventana de la placa, cierra esta cuando se CIERRA la ventana principal (su `Close`; el `Hide` no sirve porque Qt lo manda
también al minimizar).

Cada manejador de un clic o de un evento envuelve TODO su cuerpo en un `try`: bajo Qt una excepción que sale de un slot aborta el proceso; lo que el físico pulsa y falla se le DICE con un cuadro además de registrarlo. Sin estado global; el único SQL es el conteo de V.
"""
from dataclasses import dataclass
from typing import Optional

from PyQt5 import sip
from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import imagen_vigente
from services import placa_mensual as svc
from services.anulacion import filtro_activo
from services.audit_minimo import usuario_actual
from services.registro_errores import registrar_error

TEXTO_DEL_BOTON = "Análisis de la placa"
TEXTO_DEL_BOTON_IMAGEN = "Analizar la imagen guardada"
TEXTO_CON_N = "Análisis de la placa guardado: {archivo}, {fecha}, por {usuario}."
TEXTO_CON_V = f"Análisis hecho con la herramienta anterior, ya retirada: puede volver a analizar la imagen guardada con «{TEXTO_DEL_BOTON_IMAGEN}»."
TEXTO_CON_V_SIN_IMAGEN = f"Análisis hecho con la herramienta anterior, ya retirada, y sin imagen guardada: cargue el escaneo de la película en «{TEXTO_DEL_BOTON}»."
TEXTO_CON_I = f"Imagen guardada sin análisis de la placa: puede analizarla con «{TEXTO_DEL_BOTON_IMAGEN}»."
TEXTO_SIN_NADA = "Sin análisis de la placa."
TEXTO_SIN_NOMBRE = "sin nombre de archivo"
TEXTO_SIN_ESTADO = "No se pudo leer qué análisis tiene este control: {motivo}"
TEXTO_NO_ABRE = "No se pudo abrir el análisis de la placa ({motivo})."
TEXTO_NO_CARGA = "No se pudo cargar la imagen guardada ({motivo})."
AVISO_SIN_IMAGEN = "El control ya no tiene imagen guardada."
NOMBRE_DE_LA_IMAGEN_GUARDADA = "imagen guardada del control {ref}"


@dataclass(frozen=True)
class EstadoDeLaPlaca:
    """Lo que el control tiene: `v` y `i` son hechos (verdadero o falso); `n` es None o un diccionario con el archivo, la fecha, el usuario y la capa del análisis nuevo vigente."""
    v: bool
    i: bool
    n: Optional[dict]


def hay_franjas_vigentes(ref):
    """V: el control tiene filas VIGENTES en `analisis_placa_franjas`. Un conteo por la clave de bloque `ref`: no elige fila ni lee un valor (por eso su sitio está declarado como «clave incompleta» en
    los censos de lecturas, igual que el conteo de Q.1 de los equipos)."""
    with Conexion().conectar() as db:
        fila = db.execute(f"SELECT COUNT(*) FROM analisis_placa_franjas WHERE ref = ?{filtro_activo('analisis_placa_franjas')}", (ref,)).fetchone()
    return bool(fila and fila[0])


def estado_de_la_placa(ref):
    """V, I y N del control `ref`. Lanza lo que lance una lectura: quien lo muestra (`refrescar_la_linea`) lo registra y lo dice."""
    registro = svc.leer(ref)
    n = None if registro is None else {"archivo": registro.get("nombre_archivo"), "fecha": registro.get("fecha_registro"), "usuario": registro.get("usuario"), "capa": registro.get("capa")}
    return EstadoDeLaPlaca(v=hay_franjas_vigentes(ref), i=bool(imagen_vigente(ref)), n=n)


def texto_de_la_linea(estado):
    """Lo que dice la línea de estado: la ÚNICA definición. Con un análisis nuevo habla de ese (fecha y usuario del registro, no de la sesión); sin él, con el viejo dice cómo repararlo (con la imagen
    guardada, desde ella; sin ella, cargando el escaneo); sin ninguno de los dos, si hay imagen la ofrece; si no hay nada, lo dice."""
    if estado.n is not None:
        return TEXTO_CON_N.format(archivo=estado.n["archivo"] or TEXTO_SIN_NOMBRE, fecha=estado.n["fecha"], usuario=estado.n["usuario"])
    if estado.v:
        return TEXTO_CON_V if estado.i else TEXTO_CON_V_SIN_IMAGEN
    if estado.i:
        return TEXTO_CON_I
    return TEXTO_SIN_NADA


def _decidir_el_boton_de_la_imagen(pagina, estado):
    """El botón «Analizar la imagen guardada» se ofrece solo si el estado se pudo leer y el control tiene imagen."""
    boton = getattr(pagina, "boton_imagen_guardada", None)
    if boton is not None and not sip.isdeleted(boton):
        boton.setVisible(estado is not None and estado.i)


def _decidir_el_visor_de_la_imagen(pagina, estado):
    """El visor de la imagen vieja sigue a la imagen como el botón: se OCULTA en cuanto se sabe que el control no la tiene, al construir la sección o, si la imagen se anula con el formulario abierto, al
    volver a escribir la línea (el clic de «Analizar la imagen guardada» que la encuentra borrada, o la ventana del análisis que se oculta). Nunca se vuelve a mostrar: su dibujo se pinta una sola vez, al
    construir la página (IM4), y uno que apareciera después se vería vacío. Con el estado ilegible no se toca: se muestra como hasta hoy (E2-D7)."""
    visor = getattr(pagina, "visor_imagen_vieja", None)
    if visor is not None and not sip.isdeleted(visor) and estado is not None and not estado.i:
        visor.hide()


def refrescar_la_linea(pagina):
    """Vuelve a escribir la línea de estado y a decidir si se ofrece el botón de la imagen guardada. Devuelve el estado, o None si la etiqueta ya no existe o el estado no se pudo leer (entonces la
    línea lo dice con «Clase: mensaje» y el detalle va a `error_log.txt`)."""
    linea = getattr(pagina, "linea_analisis_placa", None)
    if linea is None or sip.isdeleted(linea):
        return None
    try:
        estado = estado_de_la_placa(pagina.ref)
    except Exception as error:
        registrar_error("E.2: leer el estado del análisis de la placa", error)
        linea.setText(TEXTO_SIN_ESTADO.format(motivo=f"{type(error).__name__}: {error}"))
        _decidir_el_boton_de_la_imagen(pagina, None)
        return None
    linea.setText(texto_de_la_linea(estado))
    _decidir_el_boton_de_la_imagen(pagina, estado)
    _decidir_el_visor_de_la_imagen(pagina, estado)
    return estado


class _Vigilante(QObject):
    """Hijo de la ventana de la placa (muere con ella). Cuando la ventana de la placa se OCULTA, vuelve a escribir la línea; cuando se CIERRA la ventana principal, cierra la de la placa. Nunca lanza."""

    def __init__(self, pagina, ventana):
        super().__init__(ventana)
        self._pagina = pagina
        self._ventana = ventana

    def eventFilter(self, objeto, evento):
        try:
            if objeto is self._ventana:
                if evento.type() == QEvent.Hide and not sip.isdeleted(self._pagina):
                    refrescar_la_linea(self._pagina)
            elif evento.type() == QEvent.Close and not sip.isdeleted(self._ventana):
                self._ventana.close()
        except Exception as error:
            registrar_error("E.2: vigilante de la ventana de la placa", error)
        return False


def abrir_analisis_placa(pagina):
    """Abre la ventana del análisis de la placa de este control y la devuelve (o None si no se pudo construir). Una sola por página: si ya existe, se trae al frente, y si el físico la minimizó se
    le quita lo minimizado (una ventana con padre no tiene botón propio en la barra de tareas de Windows: minimizada no habría cómo volver a ella; lo maximizado se conserva). Si no se puede construir,
    un solo `critical` con el error y la entrada en `error_log.txt`; lo que falle DESPUÉS de construirla se registra y no sale del manejador."""
    try:
        ventana = getattr(pagina, "ventana_placa", None)
        if ventana is not None and not sip.isdeleted(ventana):
            ventana.setWindowState((ventana.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
            ventana.show()
            ventana.raise_()
            ventana.activateWindow()
            return ventana
        try:
            from ui.paginasControles.PruebasMensuales.placa_mensual import VentanaPlacaMensual
            ventana = VentanaPlacaMensual(pagina.ref, pagina.equipo_f, usuario_actual(pagina), pagina)
        except Exception as error:
            registrar_error("E.2: abrir la ventana del análisis de la placa", error)
            QMessageBox.critical(pagina, TEXTO_DEL_BOTON, TEXTO_NO_ABRE.format(motivo=f"{type(error).__name__}: {error}"))
            return None
        pagina.ventana_placa = ventana
        vigilante = _Vigilante(pagina, ventana)
        ventana.installEventFilter(vigilante)
        principal = pagina.window()
        if principal is not ventana:
            principal.installEventFilter(vigilante)
        ventana.show()
        return ventana
    except Exception as error:
        registrar_error("E.2: abrir el análisis de la placa", error)
        return None


def _avisar_que_no_se_pudo_cargar(pagina, error):
    """El `critical` de «Analizar la imagen guardada» cuando la imagen no se pudo leer de la base o cargar en la ventana: la ÚNICA definición del aviso (lo dan la carga y el manejador exterior). Se da
    desde un `except` de un slot de Qt, así que nunca lanza: si el cuadro mismo falla, se registra."""
    try:
        QMessageBox.critical(pagina, TEXTO_DEL_BOTON_IMAGEN, TEXTO_NO_CARGA.format(motivo=f"{type(error).__name__}: {error}"))
    except Exception as otro:
        registrar_error("E.2: avisar que no se pudo cargar la imagen guardada", otro)


def analizar_imagen_guardada(pagina):
    """DA-89: carga en la ventana del análisis la imagen que el control tiene guardada, por el mismo camino que «Seleccionar imagen». Los bytes se leen AQUÍ, en el clic, y nunca al construir la sección:
    el físico pudo cambiar la imagen. Si el control ya no tiene imagen, avisa, vuelve a escribir la línea y no abre nada. Si leerla o cargarla falla, lo registra y lo dice con un cuadro (antes de E.2-R2
    el fallo de la lectura solo iba al registro y el físico pulsaba sin que pasara nada visible); nada sale del slot."""
    try:
        datos = imagen_vigente(pagina.ref)
        if not datos:
            QMessageBox.warning(pagina, TEXTO_DEL_BOTON_IMAGEN, AVISO_SIN_IMAGEN)
            refrescar_la_linea(pagina)
            return None
        ventana = abrir_analisis_placa(pagina)
        if ventana is None:
            return None
        try:
            ventana.cargar_imagen(bytes(datos), NOMBRE_DE_LA_IMAGEN_GUARDADA.format(ref=pagina.ref), TEXTO_DEL_BOTON_IMAGEN)
        except Exception as error:
            registrar_error("E.2: cargar la imagen guardada en la ventana del análisis", error)
            _avisar_que_no_se_pudo_cargar(pagina, error)
            return None
        return ventana
    except Exception as error:
        registrar_error("E.2: analizar la imagen guardada", error)
        _avisar_que_no_se_pudo_cargar(pagina, error)
        return None


def seccion_imagen_del_campo(pagina, visor):
    """El contenedor de «Imagen del campo»: el botón «Análisis de la placa», el botón «Analizar la imagen guardada», la línea de estado y, debajo, `visor` (lo que devolvió el cargador compartido). Deja en
    la página `boton_analisis_placa`, `boton_imagen_guardada`, `linea_analisis_placa` y `visor_imagen_vieja`, oculta «Seleccionar Imagen» y deja el visor a la vista salvo que se sepa que el control no
    tiene imagen (`_decidir_el_visor_de_la_imagen`; con el estado ilegible se muestra como hasta hoy)."""
    contenedor = QWidget()
    capa = QVBoxLayout(contenedor)
    boton = QPushButton(TEXTO_DEL_BOTON)
    boton_imagen = QPushButton(TEXTO_DEL_BOTON_IMAGEN)
    linea = QLabel()
    linea.setWordWrap(True)
    for pieza in (boton, boton_imagen, linea, visor):
        capa.addWidget(pieza)
    pagina.boton_analisis_placa = boton
    pagina.boton_imagen_guardada = boton_imagen
    pagina.linea_analisis_placa = linea
    pagina.visor_imagen_vieja = visor
    pagina.boton_subir.hide()
    refrescar_la_linea(pagina)
    boton.clicked.connect(lambda _marcado=False: abrir_analisis_placa(pagina))
    boton_imagen.clicked.connect(lambda _marcado=False: analizar_imagen_guardada(pagina))
    return contenedor
