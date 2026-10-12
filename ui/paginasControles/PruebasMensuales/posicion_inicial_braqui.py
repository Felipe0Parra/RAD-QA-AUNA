"""PI.4 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md, DA-82): la página de la posición inicial de la fuente de braquiterapia.

El físico elige el cambio de fuente, sube la imagen (el recorte o la página completa del escáner), marca dos puntos sobre la
línea de referencia y ve el resultado con su incertidumbre; lo guarda pegado a su cambio de fuente, lo puede anular con
permiso, y lo guardado se vuelve a abrir y se recalcula: si no diera lo mismo, la página lo dice. Es una página PROPIA
(`QWidget`), no heredera de `PruebaBasico`: la vieja heredó la lista de chequeo, el "Fuera de servicio" y un "Eliminar" de
calibraciones que aquí no tienen sentido (§1 del plan).

Sin SQL, sin `pyplot` y sin ningún cálculo propio: todo pasa por el servicio (`services/posicion_inicial_braqui.py`, la única
puerta a la tabla y la única regla de vigencia) y por el motor (`motor.resumen`, `motor.valores_medidos`), de modo que el
sentido físico, el veredicto y los milímetros que muestra la pantalla son los mismos que imprimen los PDF. Los dibujos son
funciones de módulo que reciben un eje (se prueban sobre una `Figure` sin lienzo y no importan matplotlib).

Decisiones de la revisión de diseño de Opus (03-10-2026, `pi4_informe_opus.md`), cada una con su motivo medido:
  - X1 los clics se guardan redondeados a 3 decimales: los `MouseEvent` reales traen ruido de 1e-13 y la posición 472.5 de la
    ventana rotada es un empate exacto (G1 daba -8.5251 en vez de -8.5533).
  - X2 un clic cuenta solo si cae DENTRO de la imagen (`inaxes` no lo garantiza: tras desplazar la vista los ejes muestran
    zona fuera de ella, y el motor da "ok" y "No cumple" con puntos fuera).
  - X3 la herramienta activa de la barra se detecta con `lienzo.widgetlock.locked()` (API pública, vale True con lupa y con
    desplazar); el doble clic y los botones distintos del izquierdo se ignoran.
  - La imagen se muestra como RGB `uint8` con `nearest`: un gris 2D con colormap pedía 2 GB y casi un segundo por dibujo
    sobre la página completa del escáner (6600 x 5100); así, 129 MB y 110 ms.
  - La línea de referencia debe haberse REFINADA (P10, DP-145): si los dos clics quedan a 4 px o más de la línea que el
    motor encuentra (o marcan un tramo corto de ella), éste mide contra los clics y da un veredicto sin aviso; mientras el
    físico no decida (a), Guardar queda deshabilitado en ese caso Y la pantalla no muestra milímetros, sentido ni veredicto
    (solo el aviso y el desfase en píxeles sin interpretar: un "Cumple" que se puede copiar de la pantalla es el mismo
    riesgo que guardarlo; medido en la revisión de Opus del 03-10). El motor y el servicio no se tocan.
  - Guardar pide confirmar si el cambio de fuente elegido está a más de 7 días de la fecha de la película (los mismos 7 días
    de DD7): la selección manual se conserva entre imágenes, un cambio de fuente anulado desplaza la propuesta automática y
    la rueda del ratón sobre un combo cerrado cambia la selección en Qt; ninguno de esos caminos avisaba (medido). La rueda
    solo actúa si el combo tiene el foco.
  - El selector recuerda DE DÓNDE viene su selección (`_origen_seleccion`): una selección automática (DD7) hecha para la
    imagen A no puede quedar pegada a la imagen B; solo la manual (`activated`, que nunca emite un `setCurrentIndex`) se
    conserva. La página queda en caché en el menú: `refrescar()` (público) se llama en `showEvent`.
  - X12 anular pregunta primero lo concreto y después pide el permiso: así no se pide una contraseña para algo que se va a
    cancelar (D9 se cumple en cualquier orden).
  - Ningún manejador deja escapar una excepción (X9) y ningún diálogo se abre con el cursor de espera puesto (X8).

La cuarta pestaña (PI.5, D6), `PestanaSintetica`, deja ver cómo responde el método a anchos y saturación distintos con
una placa sintética de desfase conocido: usa el MISMO `motor.analizar` que la imagen real (validar una copia no validaría
nada) y no toca la BD. Qt solo tiene deslizadores de enteros; el cálculo son varios segundos (la placa, su análisis y el
barrido de desfases: una docena de análisis), así que NO corre en cada paso sino al soltar el deslizador
(`sliderReleased`) y, para el teclado, la rueda y el clic en la barra, una sola vez cuando el valor deja de moverse (un
temporizador de un disparo). El barrido no depende del desfase elegido: se recuerda mientras no cambien los tres
parámetros de forma.

Lo que deja preparado: `abrir_registro(id) -> bool` y `refrescar()` públicos (PI.6 y el visor), `pestanas` con la imagen
sintética como cuarta (su reinicio vive dentro de `_restablecer_estado`), las propiedades `estado` y `puntos`; ninguna
señal."""
import functools
import io
import json
import os
import traceback
from collections import namedtuple
from datetime import date

import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QFrame,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSlider, QTabWidget,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from analisisImagenes import posicion_inicial_braqui as motor
from resources.utils.matplotlib_lazy import get_matplotlib_components
from services import posicion_inicial_braqui as svc
from services.audit_minimo import usuario_actual
from ui.paginasGuia.dialogs import DialogAdminPermisoEliminar

# La línea que el motor dice cuando la refinó por su perfil: lo único que deja guardar. Una prueba la ata al motor real.
LINEA_REFINADA = "linea refinada por su perfil"
DECIMALES_CLIC = 3                     # X1
PESTANA_IMAGEN, PESTANA_GRIS, PESTANA_RGB = 0, 1, 2
PESTANA_SINTETICA = 3                  # PI.5

COLOR_MEDIDO = "#2a78d6"
COLOR_REFERENCIA = "#eb6834"
TINTA = "#0b0b0b"
TINTA_SUAVE = "#898781"
COLOR_CAPA = {"R": "#e34948", "G": "#008300", "B": "#2a78d6"}

SIN_ELEGIR = "Elija el cambio de fuente"
SIN_IMAGEN = "Ninguna imagen"
TEXTO_ANALIZANDO = "Analizando la imagen..."
AVISO_SIN_CAMBIO = ("Elija el cambio de fuente al que pertenece esta película. Si no aparece, guárdelo primero en el "
                    "mensual de braquiterapia.")
FILTRO_IMAGENES = "Imágenes (*.jpg *.jpeg *.JPG *.JPEG *.png *.PNG *.tif *.tiff *.TIF *.TIFF)"

LINEA_SIN_CAMBIO = "Su cambio de fuente ya no existe vigente: elija otro si quiere guardarla de nuevo."
COLOR_LINEA_DESCARTADA = "#00a6b8"
COLOR_REJILLA = "#e1e0d9"

# PI.5: la imagen sintética. Qt solo tiene deslizadores de enteros: cada uno lleva su divisor (el valor que recibe el
# motor es el entero dividido por `escala`) y los decimales con que se muestra. Por omisión, los de la placa sintética
# del físico: anchos de 2.2 y 1.1 mm, saturada al 50 % del pico y la mancha 0.6 mm a la derecha de la línea.
_Deslizador = namedtuple("_Deslizador", "clave rotulo minimo maximo omision escala decimales")
DESLIZADORES = (
    _Deslizador("ancho_x", "Ancho en X [mm]", 5, 60, 22, 10, 1),
    _Deslizador("ancho_y", "Ancho en Y [mm]", 5, 60, 11, 10, 1),
    _Deslizador("saturacion", "Saturación [%]", 30, 100, 50, 100, 0),
    _Deslizador("desfase", "Desfase real [mm]", -50, 50, -6, 10, 1),
)
DESLIZADOR = {d.clave: d for d in DESLIZADORES}
TEXTO_SINTETICA = "Calculando la placa sintética..."
NOTA_SINTETICA = ("Desfase en la imagen = línea - mancha: un desfase negativo pone la mancha a la derecha de la línea. Se "
                  "recalcula al soltar un deslizador (unos segundos).")
ANCHO_DE_LOS_CONTROLES = 270            # px: la columna de los deslizadores; todo el alto de la pestaña es para los dibujos
RETRASO_SINTETICA_MS = 400             # teclado, rueda y clic en la barra: un solo cálculo cuando el valor deja de moverse

_EXTENSIONES_DEL_FORMATO = {"JPEG": (".jpg", ".jpeg"), "TIFF": (".tif", ".tiff"), "PNG": (".png",), "BMP": (".bmp",),
                            "WEBP": (".webp",)}

NOMBRE_DE_PERFIL = {"gris": "Perfil de grises", "R": "Capa roja", "G": "Capa verde", "B": "Capa azul"}
NIVEL_DE_PERFIL = {"gris": "gris", "R": "rojo", "G": "verde", "B": "azul"}

# Cómo se llama, para el físico, cada cosa que se compara al abrir un registro (las 17 claves de `valores_medidos`): una
# prueba exige que no falte ninguna y que no sobre ninguna.
ROTULOS_DE_LO_GUARDADO = {
    "tamano_pixel_mm": "escala del píxel [mm]",
    "lado_transito": "lado de la banda de tránsito",
    "estado_gris": "estado del perfil de grises",
    "desfase_gris_px": "desfase del gris [px]",
    "desfase_gris_mm": "desfase del gris [mm]",
    "incertidumbre_gris_px": "incertidumbre del gris [px]",
    "dispersion_gris_px": "dispersión entre cuerdas del gris [px]",
    "filas_gris": "número de cuerdas del gris",
    "estado_r": "estado de la capa roja",
    "desfase_r_px": "desfase de la capa roja [px]",
    "desfase_r_mm": "desfase de la capa roja [mm]",
    "estado_g": "estado de la capa verde",
    "desfase_g_px": "desfase de la capa verde [px]",
    "desfase_g_mm": "desfase de la capa verde [mm]",
    "estado_b": "estado de la capa azul",
    "desfase_b_px": "desfase de la capa azul [px]",
    "desfase_b_mm": "desfase de la capa azul [mm]",
}


# ----------------------------------------------------------------------------------------------------- textos (puros)

def _numero(valor, decimales):
    """El número con sus decimales y nunca '-0.00' (un desfase que redondea a cero no tiene signo)."""
    texto = f"{valor:.{decimales}f}"
    return texto[1:] if texto.startswith("-") and float(texto) == 0 else texto


def _tolerancia(valor):
    """'1.0' (y no '1'), '0.25', '1.5': siempre con decimales, sin perder los que haya."""
    texto = f"{valor:g}"
    return texto if "." in texto else texto + ".0"


def _motivo_de_estado(estado):
    """'la mancha se sale de la zona marcada' de 'no medible: la mancha se sale de la zona marcada'."""
    return estado.split(":", 1)[1].strip() if ":" in estado else estado


def formato_de_la_imagen(datos, nombre):
    """El formato por el CONTENIDO (un `.jpeg` puede ser un TIFF: EPSON009, que Paint guardó así), con la extensión del
    nombre cuando no es la de ese formato; None si Pillow no lo reconoce."""
    try:
        formato = Image.open(io.BytesIO(datos)).format
    except Exception:
        return None
    if not formato:
        return None
    extension = os.path.splitext(nombre or "")[1].lower()
    esperadas = _EXTENSIONES_DEL_FORMATO.get(formato)
    if extension and esperadas and extension not in esperadas:
        return f"{formato} (extensión {extension})"
    return formato


def texto_resolucion(dpi):
    """Lo que la imagen DECLARA frente al procedimiento, ANTES de analizar (la escala es siempre la del procedimiento y
    la declarada solo se clasifica). Las frases salen del motor: coincide no se anota; un editor (72 o 96) o la falta de
    dato dan la nota; una resolución 'otra' da el aviso (sin milímetros ni veredicto)."""
    P = motor.PARAMETROS
    clase = motor.clase_resolucion(dpi, P)
    if clase == "coincide":
        return f"Resolución: {P['resolucion_escaneo_dpi']:g} dpi"
    if clase == "otra":
        return "Resolución: " + motor.interpretar("ok", 0.0, 0.0, None, None, dpi, P)["aviso"]
    return "Resolución: " + motor.nota_de_resolucion({"parametros": P, "clase_resolucion": clase, "dpi": dpi})


def motivo_para_no_guardar(resultado):
    """None si el resultado se puede guardar; si no, el texto de por qué no (P10, DP-145): el motor descarta la línea que
    encontró cuando queda a 5 px o más de los clics, mide contra los clics y da un veredicto sin ningún aviso. Es también
    la primera línea del recuadro: una sola definición del mensaje."""
    mensaje = resultado["mensaje_linea"]
    if mensaje == LINEA_REFINADA:
        return None
    return (f"No se encontró la línea marcada cerca de los dos puntos ({mensaje}): el resultado se midió contra los "
            "puntos, no contra la línea. Vuelva a marcarlos con la lupa (Recalcular)")


def texto_recuadro(resultado, perfil="gris"):
    """El recuadro de resultado de un perfil. Sale de `motor.resumen` (sentido, veredicto y milímetros son los del PDF) y de
    `motor.incertidumbre_px` (la única suma de incertidumbres): la página no calcula nada por su cuenta. El desfase que
    muestra es el de la IMAGEN; el sentido físico lo dice la banda de tránsito (con la hoja girada 180 grados el de la
    imagen cambia de signo y el físico no)."""
    s = motor.resumen(resultado, perfil)
    lineas = []
    aviso_linea = motivo_para_no_guardar(resultado)
    if aviso_linea:
        lineas.append(aviso_linea)
    if s["estado"] != "ok":
        lineas.append(f"No medible: {_motivo_de_estado(s['estado'])}")
        return "\n".join(lineas)
    if aviso_linea:
        # Medido contra los puntos y no contra la línea: ni milímetros, ni sentido, ni veredicto (con +10 px el recuadro
        # decía "0.12 mm despues de la marca ... Cumple" sobre una película cuyo valor real es -0.362 mm).
        lineas.append(f"Desfase medido contra los puntos, sin interpretar: {_numero(s['desfase_px'], 2)} px")
        return "\n".join(lineas)
    u_px = motor.incertidumbre_px(resultado, perfil)
    if s["desfase_mm"] is None:
        lineas.append(f"Desfase en la imagen: {_numero(s['desfase_px'], 2)} px, sin milímetros")
        lineas.append(f"Incertidumbre (k = 2): {_numero(u_px, 2)} px ({s['filas']} cuerdas)")
        lineas.append(s["aviso"])
        return "\n".join(lineas)
    lineas.append(f"Desfase en la imagen: {_numero(s['desfase_px'], 2)} px = {_numero(s['desfase_mm'], 3)} mm")
    lineas.append(f"Incertidumbre (k = 2): {_numero(s['U_mm'], 2)} mm = {_numero(u_px, 2)} px ({s['filas']} cuerdas)")
    if s["desfase_fisico_mm"] is not None:
        lado = resultado["lado_transito"]
        contraste = resultado["contrastes_transito"][lado]["contraste"]
        lineas.append(f"La fuente quedó {_numero(abs(s['desfase_fisico_mm']), 2)} mm {s['sentido']} "
                      f"(banda de tránsito a la {lado} de la imagen, {contraste:.0f} niveles)")
    else:
        lineas.append(f"Sentido: {s['sentido']}")
    lineas.append(f"Tolerancia {_tolerancia(resultado['parametros']['tolerancia_mm'])} mm: {s['veredicto']}")
    if s.get("nota_resolucion"):
        lineas.append(f"Resolución: {s['nota_resolucion']}")
    return "\n".join(lineas)


def texto_capa(resultado, capa):
    """La línea de una capa de color (R, G o B) de la pestaña de capas: px y mm de la imagen, o por qué no se mide."""
    s = motor.resumen(resultado, capa)
    if s["estado"] != "ok":
        return f"Capa {capa}: No medible: {_motivo_de_estado(s['estado'])}"
    if motivo_para_no_guardar(resultado):
        return f"Capa {capa}: desfase medido contra los puntos, sin interpretar: {_numero(s['desfase_px'], 2)} px"
    if s["desfase_mm"] is None:
        return f"Capa {capa}: desfase en la imagen {_numero(s['desfase_px'], 2)} px, sin milímetros"
    return f"Capa {capa}: desfase en la imagen {_numero(s['desfase_px'], 2)} px = {_numero(s['desfase_mm'], 3)} mm"


def texto_recuadro_capas(resultado):
    """El recuadro de la pestaña de capas: una línea por capa y, si la línea de referencia no se refinó, el mismo aviso
    que el del gris ANTES de ellas (sin él, las tres capas se leían como medidas buenas)."""
    lineas = [texto_capa(resultado, capa) for capa in ("R", "G", "B")]
    aviso = motivo_para_no_guardar(resultado)
    return "\n".join(([aviso] if aviso else []) + lineas)


def motivos_para_confirmar(resultado):
    """Lo que el físico debe saber antes de guardar y que NO impide guardar (P11, P12): el gris que no se pudo medir y la
    resolución 'otra' (solo píxeles, sin veredicto). 'Línea no refinada' no está aquí: eso no se guarda (P10)."""
    motivos = []
    estado = resultado["perfiles"]["gris"]["estado"]
    if estado != "ok":
        motivos.append(f"el perfil de grises no se pudo medir: {_motivo_de_estado(estado)}")
    if resultado["tamano_pixel_mm"] is None:
        escaneo = resultado["parametros"]["resolucion_escaneo_dpi"]
        motivos.append(f"no habrá milímetros ni veredicto: la imagen declara {resultado['dpi']:g} dpi y el procedimiento "
                       f"es de {escaneo:g} dpi")
    return motivos


def motivo_de_distancia(fecha_cambio, fecha_pelicula, origen=None):
    """None si el cambio de fuente elegido (texto 'aaaa-mm-dd') está a 7 días o menos de la fecha de la película (los mismos
    7 días con que DD7 propone uno) o si no hay fecha de la película (un registro abierto); si no, el motivo para que el
    físico lo confirme. La selección manual se conserva entre imágenes, un cambio de fuente anulado desplaza la propuesta
    automática y la rueda del ratón cambia el combo: cualquiera de los tres dejaba guardar bajo un cambio de fuente
    lejano sin preguntar nada."""
    if fecha_pelicula is None:
        return None
    dias = abs((date.fromisoformat(fecha_cambio) - fecha_pelicula).days)
    if dias <= svc.DIAS_PARA_PROPONER:
        return None
    de = f" ({origen})" if origen else ""
    return (f"la película es del {fecha_pelicula.isoformat()}{de} y el cambio de fuente elegido es del {fecha_cambio}: "
            f"{dias} días de diferencia")


def texto_confirmacion(fecha, existe, motivos):
    """La ÚNICA pregunta antes de guardar (con 'No' por omisión), o None si no hay nada que confirmar. Con solo una prueba
    ya guardada es la pregunta del plan; con más, enumera todo lo que haya."""
    if not existe and not motivos:
        return None
    if existe and not motivos:
        return f"Ya hay una posición inicial guardada para el cambio de fuente del {fecha}. ¿Reemplazarla?"
    lineas = list(motivos)
    if existe:
        lineas.insert(0, f"ya hay una posición inicial guardada para el cambio de fuente del {fecha} (se reemplazará)")
    return "Antes de guardar:\n- " + "\n- ".join(lineas) + "\n\n¿Guardar de todos modos?"


def _como_texto(valor):
    return f"{valor:.6g}" if isinstance(valor, float) else str(valor)


def diferencias_con_lo_guardado(registro, resultado):
    """Lo recalculado contra lo guardado (DD3): las 17 claves de `valores_medidos` más la versión del algoritmo. Los
    píxeles se comparan a 0.01 px, los milímetros a 0.01 px expresado en milímetros y todo lo demás (estados, lado del
    tránsito, número de filas, versión) exacto: comparar solo el desfase del gris dejaría pasar un `lado_transito`
    distinto, que es el signo que imprime el PDF. Devuelve una lista de textos; vacía si coinciden."""
    nuevos = motor.valores_medidos(resultado)
    escala = resultado["tamano_pixel_mm"]
    diferencias = []
    if registro.get("version_algoritmo") != resultado["version"]:
        diferencias.append(f"versión del algoritmo: guardada {registro.get('version_algoritmo')}, "
                           f"actual {resultado['version']}")
    for clave, nuevo in nuevos.items():
        viejo = registro.get(clave)
        if isinstance(nuevo, float) and isinstance(viejo, (int, float)):
            if clave == "tamano_pixel_mm":
                tolerancia = 1e-9                   # la ESCALA no es una medida: es la del procedimiento
            elif clave.endswith("_px"):
                tolerancia = 0.01
            elif clave.startswith("desfase_") and clave.endswith("_mm"):
                tolerancia = 0.01 * (escala if escala is not None else 1.0)
            else:
                tolerancia = 1e-9
            if abs(nuevo - viejo) > tolerancia:
                diferencias.append(f"{ROTULOS_DE_LO_GUARDADO[clave]}: guardado {_como_texto(viejo)}, "
                                   f"recalculado {_como_texto(nuevo)}")
        elif nuevo != viejo:
            diferencias.append(f"{ROTULOS_DE_LO_GUARDADO[clave]}: guardado {_como_texto(viejo)}, "
                               f"recalculado {_como_texto(nuevo)}")
    return diferencias


# ------------------------------------------------------------------------------------------------- dibujos (puros)

def fila_representativa(resultado, perfil="gris"):
    """La cuerda que se dibuja: la central de las cuerdas útiles (`filas[len(filas) // 2]`; no `argmax(ancho)`, que da
    empates porque los anchos son enteros). Sin cuerdas útiles, la fila media de los dos clics en la ventana. R, G y B se
    dibujan sobre la fila que da el gris, como el notebook."""
    filas = resultado["perfiles"][perfil]["filas"]
    if len(filas):
        return int(filas[len(filas) // 2])
    alto = resultado["imagenes"]["gris"].shape[0]
    return int(min(max(round(float(np.mean(resultado["clics_ventana"][:, 1]))), 0), alto - 1))


def dibujar_ventana(ax, resultado, perfil, fila):
    """La ventana rotada alrededor de la línea: la línea de referencia (naranja discontinua), los bordes de la meseta por
    cuerda y el centro de cada cuerda (azul, solo si el perfil se mide)."""
    r = resultado["perfiles"][perfil]
    m = r["m"]
    ax.imshow(m["suave"], cmap="gray", vmin=m["tope"] - 60, vmax=m["tope"], interpolation="nearest")
    ax.plot(resultado["x_ref"], np.arange(len(resultado["x_ref"])), "--", color=COLOR_REFERENCIA, lw=1.5,
            label="línea de referencia")
    linea = resultado.get("linea")
    if linea is not None and resultado["mensaje_linea"] != LINEA_REFINADA:
        # La línea que el motor encontró y NO usó: sin verla, el físico no sabe por qué se le pide marcar de nuevo.
        todas = np.arange(len(resultado["x_ref"]))
        ax.plot(linea["pendiente"] * todas + linea["corte"], todas, "--", color=COLOR_LINEA_DESCARTADA, lw=1.2,
                label="línea que se encontró (no se usa)")
    if r["estado"] == "ok":
        filas = r["filas"]
        ax.plot(m["x_izq"][filas], filas, "o", ms=2, mfc="white", mec=TINTA, mew=0.3, label="bordes de la meseta")
        ax.plot(m["x_der"][filas], filas, "o", ms=2, mfc="white", mec=TINTA, mew=0.3)
        ax.plot(r["centros"], filas, "-", color=COLOR_MEDIDO, lw=1.5, label="centro de cada cuerda")
    ax.axhline(fila, color=TINTA_SUAVE, ls=":", lw=1)
    ax.set_xlabel("columna de la ventana [px]")
    ax.set_ylabel("fila de la ventana [px]")


def dibujar_perfil(ax, resultado, perfil, fila, color=TINTA, leyenda=False):
    """El perfil de una cuerda: el crudo y el filtrado, el umbral de la meseta, la meseta sombreada entre sus bordes
    subpíxel, la línea de referencia y el centro de la meseta de ESA cuerda (azul; no se dibuja en un perfil que no se
    mide). Los dos centros que se comparan son la línea y la meseta: los cruces solo entran en la incertidumbre."""
    r = resultado["perfiles"][perfil]
    m = r["m"]
    x = np.arange(m["suave"].shape[1])
    ax.plot(x, resultado["imagenes"][perfil][fila], color=TINTA_SUAVE, lw=0.7, label="perfil crudo")
    ax.plot(x, m["suave"][fila], color=color, lw=1.2, label="perfil con filtro de mediana")
    ax.axhline(m["umbral"], color=TINTA_SUAVE, ls="--", lw=1, label="umbral de la meseta")
    if m["inicio"][fila] >= 0:
        ax.axvspan(m["x_izq"][fila], m["x_der"][fila], color=COLOR_MEDIDO, alpha=0.15, label="meseta")
        ax.set_xlim(m["x_izq"][fila] - 120, m["x_der"][fila] + 120)
        ax.set_ylim(m["tope"] - 40, m["tope"] + 3)
    if r["estado"] == "ok":
        ax.axvline((m["x_izq"][fila] + m["x_der"][fila]) / 2, color=COLOR_MEDIDO, lw=1.5, label="centro de la meseta")
    ax.axvline(resultado["x_ref"][fila], color=COLOR_REFERENCIA, ls="--", lw=1.5, label="línea de referencia")
    ax.set_xlabel("columna de la ventana [px]")
    ax.set_ylabel(f"{NIVEL_DE_PERFIL[perfil]} invertido")
    nombre = NOMBRE_DE_PERFIL[perfil]
    if motivo_para_no_guardar(resultado):
        ax.set_title(f"{nombre}: medido contra los puntos, no contra la línea", fontsize=8)
    elif r["estado"] == "ok" and m["inicio"][fila] >= 0:
        en_cuerda = resultado["x_ref"][fila] - (m["x_izq"][fila] + m["x_der"][fila]) / 2
        ax.set_title(f"{nombre}: en esta cuerda {_numero(en_cuerda, 2)} px; mediana de {len(r['filas'])} cuerdas "
                     f"{_numero(r['desfase_px'], 2)} px", fontsize=8)
    else:
        ax.set_title(f"{nombre}: no medible", fontsize=8)
    if leyenda:
        ax.legend(loc="lower center", fontsize=7, ncol=3)


# ------------------------------------------------------------------------------------- la imagen sintética (puros)

def texto_valor(clave, entero):
    """El valor de un deslizador como se muestra (la unidad ya está en su rótulo): 2.2, 50, -0.6."""
    d = DESLIZADOR[clave]
    return str(entero) if d.decimales == 0 else _numero(entero / d.escala, d.decimales)


def parametros_sinteticos(enteros):
    """De los enteros de los deslizadores (`{clave: entero}`) a lo que recibe el motor: los anchos y el desfase en [mm] y la
    saturación como fracción del pico. Es la ÚNICA conversión: la usan el cálculo y las pruebas."""
    return {"ancho_x_mm": enteros["ancho_x"] / DESLIZADOR["ancho_x"].escala,
            "ancho_y_mm": enteros["ancho_y"] / DESLIZADOR["ancho_y"].escala,
            "saturacion": enteros["saturacion"] / DESLIZADOR["saturacion"].escala,
            "desfase_mm": enteros["desfase"] / DESLIZADOR["desfase"].escala}


def analizar_sintetica(p):
    """La placa sintética con esos parámetros, analizada con el MISMO `motor.analizar` que la imagen real."""
    gris, color, dpi, puntos = motor.placa_sintetica(p["desfase_mm"], p["ancho_x_mm"], p["ancho_y_mm"], p["saturacion"])
    return motor.analizar(gris, color, dpi, puntos)


def texto_sintetica(real_mm, resultado):
    """`Real -0.60 mm, medido -0.60 mm, error 0.00 mm` (el error es medido menos real), o por qué no se mide. Si el motor
    no refinó la línea la placa se midió contra los puntos y se dice: sin el aviso, ese número se leería como medida
    buena."""
    s = motor.resumen(resultado)
    real = _numero(real_mm, 2)
    if s["estado"] != "ok":
        return f"Real {real} mm, no medible: {_motivo_de_estado(s['estado'])}"
    medido = s["desfase_mm"]
    texto = f"Real {real} mm, medido {_numero(medido, 2)} mm, error {_numero(medido - real_mm, 2)} mm"
    if motivo_para_no_guardar(resultado):
        texto += " (la línea no se refinó: se midió contra los puntos)"
    return texto


def dibujar_barrido(ax, puntos, actual, tolerancia):
    """Real contra medido, como la gráfica de calibración del notebook: la franja de tolerancia, la diagonal medido = real,
    los puntos del barrido, los que no se pudieron medir aparte (cruces sobre el borde inferior) y el punto de la placa
    que se muestra, resaltado. `puntos` son los pares `(real, medido o None)` de `motor.barrido_sintetico`; `actual` es el
    par de la placa mostrada."""
    medidos = [(r, m) for r, m in puntos if m is not None]
    no_medibles = [r for r, m in puntos if m is None]
    real, medido = actual
    valores = [abs(r) for r, _ in puntos] + [abs(m) for _, m in medidos] + [abs(real)]
    if medido is not None:
        valores.append(abs(medido))
    limite = max(6.0, max(valores) + 1.0)
    suelo = -limite + 0.4
    ax.axhspan(-tolerancia, tolerancia, color=COLOR_REJILLA, alpha=0.6, label=f"tolerancia ±{_tolerancia(tolerancia)} mm")
    ax.plot([-limite, limite], [-limite, limite], color=TINTA_SUAVE, lw=1, label="medido = real")
    ax.plot([r for r, _ in medidos], [m for _, m in medidos], "o", ms=6, color=COLOR_MEDIDO,
            label=f"barrido de {len(puntos)} desfases")
    if no_medibles:
        ax.plot(no_medibles, [suelo] * len(no_medibles), "x", ms=7, mew=1.5, color=TINTA, label="no medible")
    if medido is None:
        ax.plot([real], [suelo], "X", ms=11, color=COLOR_REFERENCIA, mec=TINTA, label="placa mostrada, no medible")
    else:
        ax.plot([real], [medido], "D", ms=9, color=COLOR_REFERENCIA, mec=TINTA, label="placa mostrada")
    ax.set_xlim(-limite, limite)
    ax.set_ylim(-limite, limite)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color=COLOR_REJILLA)
    ax.set_xlabel("desfase real [mm]")
    ax.set_ylabel("desfase medido [mm]")
    ax.set_title("Medido contra real", fontsize=9)
    ax.legend(fontsize=7, loc="upper left")


# ------------------------------------------------------------------------------------------- ningún manejador escapa

def _protegido(titulo, por_defecto=None):
    """X9: ningún manejador de una señal o de un evento deja escapar una excepción. Bajo Qt una excepción que sale de un
    slot aborta el proceso o se pierde en silencio, según cómo esté el `excepthook`; matplotlib además se traga las de sus
    manejadores. Aquí se imprime la traza y se avisa. Los cursores y los indicadores de espera ya se restauraron: el aviso
    sale de la envoltura, no de dentro de ella (X8)."""
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


# ---------------------------------------------------------------------------------- piezas de pantalla compartidas

def _nuevo_lienzo(mpl):
    """(contenedor, figura, lienzo, barra): la figura NO se registra en pyplot (nunca `plt.*`), así que se libera al soltar
    la referencia. Lo usan las pestañas de la página y la imagen sintética."""
    contenedor = QWidget()
    capa = QVBoxLayout(contenedor)
    capa.setContentsMargins(0, 0, 0, 0)
    figura = mpl["Figure"](layout="constrained")
    lienzo = mpl["FigureCanvas"](figura)
    barra = mpl["NavigationToolbar"](lienzo, contenedor)
    capa.addWidget(barra)
    capa.addWidget(lienzo, 1)
    return contenedor, figura, lienzo, barra


def _recuadro():
    """El aspecto del recuadro de resultado de `mostrar_resultados_AnalisisImagen` (texto con borde y relleno), sin reutilizar
    esa función: ella borra a sus hermanos con `deleteLater` (V6 y DA-71)."""
    recuadro = QLabel()
    recuadro.setTextFormat(Qt.PlainText)
    recuadro.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    recuadro.setWordWrap(True)
    recuadro.setTextInteractionFlags(Qt.TextSelectableByMouse)
    recuadro.setStyleSheet("padding: 5px; border: 1px solid #ccc;")
    return recuadro


def _apagar_barra(barra):
    """Lupa y desplazar apagadas (X4): `zoom()` y `pan()` alternan, así que solo se llaman si están activas."""
    if barra.mode == "zoom rect":
        barra.zoom()
    elif barra.mode == "pan/zoom":
        barra.pan()


# ------------------------------------------------------------------------------------------------------------ página

class _SelectorSinRueda(QComboBox):
    """El combo del cambio de fuente: la rueda del ratón solo actúa si tiene el foco. En Qt un solo paso de la rueda sobre
    un combo cerrado cambia su selección y emite `activated` (medido: de 2026-09-27 a 2026-03-01, marcada como manual), y
    Guardar guarda bajo el cambio de fuente que haya, sea cual sea."""

    def wheelEvent(self, evento):
        if self.hasFocus():
            super().wheelEvent(evento)
        else:
            evento.ignore()


class _DeslizadorSinRueda(QSlider):
    """Como el combo: la rueda del ratón solo mueve el deslizador si tiene el foco (sin él, un paso de rueda al pasar por la
    pestaña cambiaba un parámetro y lanzaba un cálculo de varios segundos; lo midió la revisión de Opus de PI.5)."""

    def wheelEvent(self, evento):
        if self.hasFocus():
            super().wheelEvent(evento)
        else:
            evento.ignore()


class PestanaSintetica(QWidget):
    """PI.5 (D6): la imagen sintética. Cuatro deslizadores (anchos en X e Y de la mancha, saturación y desfase real), la
    placa sintética de ese desfase con su línea y sus centros, su perfil y la gráfica real contra medido del barrido de
    desfases. Sin acceso a la BD. El cálculo es de varios segundos: corre al soltar un deslizador y la primera vez que se
    abre la pestaña, dentro de la espera de la página (UX1); nunca en cada paso de un arrastre. `con_espera(texto,
    funcion)` es la espera de la página (indicador, cursor y `try/finally`): una pestaña suelta usa una que solo llama
    a la función."""

    def __init__(self, con_espera=None, parent=None):
        super().__init__(parent)
        self._con_espera = con_espera or (lambda texto, funcion: funcion())
        self._construir()
        self.reiniciar()

    def _construir(self):
        mpl = get_matplotlib_components()
        capa = QHBoxLayout(self)
        # Los controles a la izquierda y los dibujos a la derecha: encima de los dibujos, cuatro deslizadores y la nota se
        # comían 155 px y a 1280 x 760 la figura quedaba en 180 px de alto (medido en la captura): tres ejes aplastados.
        controles = QVBoxLayout()
        self.rotulos, self.deslizadores, self.valores = {}, {}, {}
        for d in DESLIZADORES:
            rotulo, valor = QLabel(d.rotulo), QLabel()
            valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            valor.setMinimumWidth(40)
            fila = QHBoxLayout()
            fila.addWidget(rotulo, 1)
            fila.addWidget(valor)
            deslizador = _DeslizadorSinRueda(Qt.Horizontal)
            deslizador.setRange(d.minimo, d.maximo)
            deslizador.setValue(d.omision)
            controles.addLayout(fila)
            controles.addWidget(deslizador)
            self.rotulos[d.clave] = rotulo
            self.deslizadores[d.clave] = deslizador
            self.valores[d.clave] = valor
            # Cada señal por su pasarela. NUNCA `valueChanged` directo al cálculo: un arrastre emite uno por paso y cada
            # cálculo son varios segundos (la prueba de PI.5 mide cuántos análisis dispara un gesto).
            deslizador.valueChanged.connect(lambda entero, clave=d.clave: self._al_cambiar_valor(clave, entero))
            deslizador.sliderPressed.connect(lambda *_: self._al_pulsar_deslizador())
            deslizador.sliderReleased.connect(lambda *_: self._actualizar())
        self.nota = QLabel(NOTA_SINTETICA)
        self.nota.setWordWrap(True)
        controles.addWidget(self.nota)
        controles.addStretch(1)
        panel = QWidget()
        panel.setLayout(controles)
        panel.setFixedWidth(ANCHO_DE_LOS_CONTROLES)
        capa.addWidget(panel)
        dibujos = QVBoxLayout()
        contenedor, self.figura, self.lienzo, self.barra = _nuevo_lienzo(mpl)
        dibujos.addWidget(contenedor, 1)
        self.recuadro = _recuadro()
        dibujos.addWidget(self.recuadro)
        capa.addLayout(dibujos, 1)
        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.setInterval(RETRASO_SINTETICA_MS)
        self._temporizador.timeout.connect(lambda *_: self._al_vencer_temporizador())
        self._barrido = None             # (forma, puntos): el último barrido; solo depende de los tres parámetros de forma

    # ------------------------------------------------------------------------------------------------------ estado

    @property
    def calculada(self):
        return self._calculada

    def parametros(self):
        """Lo que recibe el motor con los deslizadores como están ahora."""
        return parametros_sinteticos({clave: d.value() for clave, d in self.deslizadores.items()})

    def _descartar(self):
        """IM3: antes de calcular, el resultado anterior desaparece (si el cálculo falla no queda uno viejo en pantalla)."""
        self._calculada = False
        self._ultimos = None
        self.recuadro.clear()
        self.figura.clear()
        self.barra.update()              # X5: sin esto, Home volvería a la vista de la figura anterior
        self.lienzo.draw_idle()

    def reiniciar(self):
        """El estado de arranque, y el ÚNICO sitio que lo define: `__init__` lo llama y 'Limpiar' de la página lo llama
        otra vez (la prueba compara con una huella del árbol de widgets). Los valores por omisión se ponen con las señales
        bloqueadas: reiniciar no es un gesto del físico y no debe disparar un cálculo."""
        self._temporizador.stop()
        for d in DESLIZADORES:
            deslizador = self.deslizadores[d.clave]
            deslizador.blockSignals(True)
            deslizador.setValue(d.omision)
            deslizador.blockSignals(False)
            self.valores[d.clave].setText(texto_valor(d.clave, d.omision))
        self._barrido = None
        self._descartar()
        _apagar_barra(self.barra)

    # ------------------------------------------------------------------------------------------------ los manejadores

    @_protegido("Imagen sintética")
    def _al_cambiar_valor(self, clave, entero):
        """El valor visible sigue al deslizador en cada paso (es barato); el cálculo no: arrastrando, lo dispara el
        soltar; con el teclado, la rueda o un clic en la barra no hay soltar, así que se arma un temporizador de un
        disparo."""
        self.valores[clave].setText(texto_valor(clave, entero))
        if not self.deslizadores[clave].isSliderDown():
            self._temporizador.start()

    @_protegido("Imagen sintética")
    def _al_pulsar_deslizador(self):
        """Pulsar un asa detiene el temporizador que un cambio anterior del teclado dejó armado: vencería con el ratón
        apretado y el gesto acabaría en dos cálculos (medido por la revisión de Opus de PI.5)."""
        self._temporizador.stop()

    @_protegido("Imagen sintética")
    def _al_vencer_temporizador(self):
        """Con un botón del ratón apretado (el asa, o un clic mantenido en la barra, que Qt repite cada medio segundo) el gesto
        no terminó: se vuelve a armar y se calcula al soltar o al dejar de moverse."""
        if QApplication.mouseButtons() or any(d.isSliderDown() for d in self.deslizadores.values()):
            self._temporizador.start()
            return
        self._actualizar()

    @_protegido("Imagen sintética")
    def al_mostrarse(self):
        """La primera vez que se abre la pestaña (la página no calcula al construirse: son unos segundos)."""
        if not self._calculada:
            self._actualizar()

    @_protegido("Imagen sintética")
    def _actualizar(self):
        self._temporizador.stop()
        p = self.parametros()
        if self._calculada and p == self._ultimos:
            return                       # soltar sin mover no cambia nada: ni se recalcula ni se pierde el zoom
        self._descartar()
        try:
            self._con_espera(TEXTO_SINTETICA, lambda: self._calcular(p))
        except Exception:
            self._descartar()            # un fallo a medio dibujar no deja medio dibujo en pantalla
            raise

    def _calcular(self, p):
        resultado = analizar_sintetica(p)
        forma = (p["ancho_x_mm"], p["ancho_y_mm"], p["saturacion"])
        if self._barrido is None or self._barrido[0] != forma:
            self._barrido = (forma, motor.barrido_sintetico(*forma))
        self._mostrar(p, resultado, self._barrido[1])
        self._ultimos = p
        self._calculada = True

    def _mostrar(self, p, resultado, barrido):
        """Dibuja sobre la figura ya vacía: `_actualizar` llama antes a `_descartar` (que la vacía y deja a la barra sin
        historial), y es lo que garantiza que un fallo no deja nada viejo."""
        fila = fila_representativa(resultado, "gris")
        rejilla = self.figura.add_gridspec(2, 2, width_ratios=(3, 2))
        ventana = self.figura.add_subplot(rejilla[0, 0])
        dibujar_ventana(ventana, resultado, "gris", fila)
        ventana.set_ylabel("fila [px]")             # el rótulo largo de la pestaña del gris no cabe en este eje bajo
        dibujar_perfil(self.figura.add_subplot(rejilla[1, 0]), resultado, "gris", fila, leyenda=True)
        s = motor.resumen(resultado)
        medido = s["desfase_mm"] if s["estado"] == "ok" else None
        dibujar_barrido(self.figura.add_subplot(rejilla[:, 1]), barrido, (p["desfase_mm"], medido),
                        resultado["parametros"]["tolerancia_mm"])
        self.recuadro.setText(texto_sintetica(p["desfase_mm"], resultado))
        self.lienzo.draw_idle()


class PosicionInicialBraqui(QWidget):
    def __init__(self, user_id, parent=None):
        """`user_id` es el OBJETO de usuario de la sesión (no un texto): el nombre para el servicio sale de
        `usuario_actual(self)` y el objeto es lo que recibe el diálogo de permiso."""
        super().__init__(parent)
        self.user_id = user_id
        self._construir()
        self._restablecer_estado()
        self.refrescar()

    # ----------------------------------------------------------------------------------------------------- construir

    def _construir(self):
        """Todos los widgets, una sola vez: ninguno se crea ni se destruye después (un widget que alguien vacía deja
        referencias muertas: `RuntimeError: wrapped C/C++ object has been deleted`)."""
        mpl = get_matplotlib_components()
        principal = QVBoxLayout(self)

        # Barra superior: el cambio de fuente, la imagen y el indicador de espera (UX1) en su sitio fijo.
        fila_imagen = QHBoxLayout()
        self.selector_cambio = _SelectorSinRueda()
        self.selector_cambio.setFocusPolicy(Qt.StrongFocus)
        self.selector_cambio.setMinimumContentsLength(30)
        self.boton_imagen = QPushButton("Seleccionar imagen")
        self.nombre_archivo = QLineEdit()
        self.nombre_archivo.setReadOnly(True)
        self.nombre_archivo.setFocusPolicy(Qt.NoFocus)
        self.nombre_archivo.setStyleSheet("QLineEdit { background-color: #ececec; }")
        self.indicador = QLabel(TEXTO_ANALIZANDO)
        fila_imagen.addWidget(QLabel("Cambio de fuente:"))
        fila_imagen.addWidget(self.selector_cambio, 1)
        fila_imagen.addWidget(self.boton_imagen)
        fila_imagen.addWidget(self.nombre_archivo, 2)
        fila_imagen.addWidget(self.indicador)
        principal.addLayout(fila_imagen)

        fila_datos = QHBoxLayout()
        self.etiqueta_escaneo = QLabel(f"Escanear a {motor.PARAMETROS['resolucion_escaneo_dpi']:g} dpi")
        self.etiqueta_escaneo.setStyleSheet("font-weight: bold;")
        # Con una nota de resolución larga (la placa típica trae 'la imagen declara 96.012 dpi (lo escribe el editor...)'),
        # una etiqueta sin ajuste de línea hacía que la página exigiera 1691 px de ancho y ensanchaba la ventana principal.
        self.etiqueta_resolucion = QLabel()
        self.etiqueta_resolucion.setWordWrap(True)
        self.etiqueta_fecha = QLabel()
        self.etiqueta_fecha.setWordWrap(True)
        separador = QFrame()
        separador.setFrameShape(QFrame.VLine)
        fila_datos.addWidget(self.etiqueta_escaneo)
        fila_datos.addWidget(separador)
        fila_datos.addWidget(self.etiqueta_resolucion, 1)
        fila_datos.addWidget(self.etiqueta_fecha)
        principal.addLayout(fila_datos)

        fila_botones = QHBoxLayout()
        self.boton_recalcular = QPushButton("Recalcular")
        self.boton_limpiar = QPushButton("Limpiar")
        self.boton_guardar = QPushButton("Guardar")
        self.boton_anular = QPushButton("Anular")
        self.etiqueta_registro = QLabel()
        self.etiqueta_registro.setWordWrap(True)
        for boton in (self.boton_recalcular, self.boton_limpiar, self.boton_guardar, self.boton_anular):
            fila_botones.addWidget(boton)
        fila_botones.addWidget(self.etiqueta_registro, 1)
        principal.addLayout(fila_botones)

        # Pestañas: la imagen para marcar, el perfil del gris, las tres capas y, al final, la imagen sintética (PI.5), que
        # es de la pestaña misma: no depende de la imagen que se haya subido.
        self.pestanas = QTabWidget()
        tab_imagen, self._fig_imagen, self.lienzo_imagen, self.barra_imagen = _nuevo_lienzo(mpl)
        self.eje_imagen = self._fig_imagen.add_subplot(111)
        contenedor_gris, self._fig_gris, self.lienzo_gris, self.barra_gris = _nuevo_lienzo(mpl)
        tab_gris = QWidget()
        capa_gris = QVBoxLayout(tab_gris)
        capa_gris.addWidget(contenedor_gris, 1)
        self.recuadro_gris = _recuadro()
        capa_gris.addWidget(self.recuadro_gris)
        contenedor_rgb, self._fig_rgb, self.lienzo_rgb, self.barra_rgb = _nuevo_lienzo(mpl)
        tab_rgb = QWidget()
        capa_rgb = QVBoxLayout(tab_rgb)
        capa_rgb.addWidget(contenedor_rgb, 1)
        self.recuadro_rgb = _recuadro()
        capa_rgb.addWidget(self.recuadro_rgb)
        self.pestanas.addTab(tab_imagen, "Imagen")
        self.pestanas.addTab(tab_gris, "Perfil gris")
        self.pestanas.addTab(tab_rgb, "Capas RGB")
        self.sintetica = PestanaSintetica(self._con_espera)
        self.pestanas.addTab(self.sintetica, "Imagen sintética")
        principal.addWidget(self.pestanas, 3)

        # Registros guardados.
        principal.addWidget(QLabel("Registros guardados"))
        self.tabla_registros = QTableWidget(0, 4)
        self.tabla_registros.setHorizontalHeaderLabels(["Cambio de fuente", "Serie de la fuente", "Guardado por",
                                                        "Resultado"])
        self.tabla_registros.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_registros.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_registros.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla_registros.setSortingEnabled(False)
        self.tabla_registros.verticalHeader().setVisible(False)
        cabecera = self.tabla_registros.horizontalHeader()
        cabecera.setSectionResizeMode(QHeaderView.ResizeToContents)
        cabecera.setStretchLastSection(True)
        self.tabla_registros.setMinimumHeight(120)
        principal.addWidget(self.tabla_registros, 1)

        self._marcas = []
        # Cada señal por su pasarela: Qt entrega argumentos (`checked`, el índice) que los manejadores no esperan.
        self.boton_imagen.clicked.connect(lambda *_: self._al_seleccionar_imagen())
        self.boton_recalcular.clicked.connect(lambda *_: self._al_recalcular())
        self.boton_limpiar.clicked.connect(lambda *_: self._al_limpiar())
        self.boton_guardar.clicked.connect(lambda *_: self._al_guardar())
        self.boton_anular.clicked.connect(lambda *_: self._al_anular())
        self.selector_cambio.activated.connect(lambda indice: self._al_elegir_a_mano(indice))   # solo lo emite el usuario
        self.tabla_registros.cellDoubleClicked.connect(lambda fila, columna: self._al_doble_clic(fila, columna))
        # UN solo manejador de clics, aquí y no al instalar cada imagen: ya hay otros tres de la barra y N imágenes
        # seguidas acumularían N marcas por clic.
        self.lienzo_imagen.mpl_connect("button_press_event", self._al_pulsar)
        self.pestanas.currentChanged.connect(lambda indice: self._al_cambiar_pestana(indice))

    # ------------------------------------------------------------------------------------------------------ estado

    @property
    def estado(self):
        """'vacia', 'imagen', 'analizada', 'fallida' o 'registro' (abierto o recién guardado)."""
        return self._estado

    @property
    def puntos(self):
        return tuple(self._puntos)

    def _descartar_resultado(self):
        """IM3: antes de analizar, el resultado anterior desaparece (si el nuevo análisis falla, no queda uno viejo que se
        pueda guardar contra la imagen nueva) y Guardar se deshabilita."""
        self._resultado = None
        self.boton_guardar.setEnabled(False)
        self.recuadro_gris.clear()
        self.recuadro_rgb.clear()
        self._fig_gris.clear()
        self._fig_rgb.clear()
        self.barra_gris.update()
        self.barra_rgb.update()
        self.lienzo_gris.draw_idle()
        self.lienzo_rgb.draw_idle()

    def _descartar_puntos(self):
        """Las marcas se quitan con `remove()` ANTES de `ax.clear()`: después de `clear()` da `NotImplementedError` (X6)."""
        self._puntos = []
        for marca in self._marcas:
            marca.remove()
        self._marcas = []
        self.lienzo_imagen.draw_idle()

    def _apagar_herramientas(self):
        """Lupa y desplazar apagadas (X4): `zoom()` y `pan()` alternan, así que solo se llaman si están activas."""
        for barra in (self.barra_imagen, self.barra_gris, self.barra_rgb):
            _apagar_barra(barra)

    def _rotular_eje_imagen(self):
        self.eje_imagen.set_xlabel("columna de la imagen [px]")
        self.eje_imagen.set_ylabel("fila de la imagen [px]")

    def _restablecer_estado(self):
        """El estado de arranque, y el ÚNICO sitio que lo define: `__init__` lo llama tras construir y Limpiar lo llama
        otra vez, así que 'Limpiar' deja una página igual a una recién creada (la prueba lo comprueba con una huella del
        árbol de widgets, no con una lista de lo que este método limpia)."""
        self._descartar_resultado()
        self._descartar_puntos()
        self._apagar_herramientas()
        self._bytes = None
        self._nombre = None
        self._forma = None
        self._fecha_escaneo = None
        self._origen_fecha = None
        self._registro_abierto = None
        self._origen_seleccion = None            # None, 'automatica', 'registro' o 'manual'
        self._estado = "vacia"
        self.eje_imagen.clear()
        self._rotular_eje_imagen()
        self.barra_imagen.update()
        self.nombre_archivo.setText(SIN_IMAGEN)
        self.etiqueta_resolucion.clear()
        self.etiqueta_fecha.clear()
        self.etiqueta_registro.clear()
        self.indicador.setText(TEXTO_ANALIZANDO)
        self.indicador.hide()
        self.selector_cambio.setCurrentIndex(0 if self.selector_cambio.count() else -1)
        self.tabla_registros.clearSelection()
        self.tabla_registros.setCurrentCell(-1, -1)
        self.sintetica.reiniciar()
        self.pestanas.setCurrentIndex(PESTANA_IMAGEN)
        self.lienzo_imagen.draw_idle()

    # --------------------------------------------------------------------------------- selector y tabla de registros

    def refrescar(self):
        """Vuelve a leer los cambios de fuente y los registros. Público y llamado en `showEvent`: la página queda en
        caché en el menú y sin esto el selector no vería un cambio de fuente recién guardado en el mensual. Una selección
        manual o la de un registro abierto se conserva por su fecha; una automática se recalcula con la fecha del
        escaneo (DD7)."""
        # Primero se lee todo y después se toca la página: con la BD caída, el combo no se queda vacío ni el origen de la
        # selección inconsistente.
        cambios = svc.cambios_de_fuente()
        registros = svc.listar()
        elegida, origen = self._fecha_elegida(), self._origen_seleccion
        self.selector_cambio.clear()
        self.selector_cambio.addItem(SIN_ELEGIR, None)
        for fecha, serie in cambios:
            self.selector_cambio.addItem(f"{fecha} · fuente {serie or 'sin serie'}", fecha)
        if origen in ("manual", "registro"):
            indice = self.selector_cambio.findData(elegida) if elegida else 0
            self.selector_cambio.setCurrentIndex(max(indice, 0))
            if elegida and indice <= 0:
                self._origen_seleccion = None            # su cambio de fuente ya no existe vigente
                if origen == "registro" and self._registro_abierto is not None:
                    self._anotar_registro(LINEA_SIN_CAMBIO)
        else:
            self._origen_seleccion = None
            self.selector_cambio.setCurrentIndex(0)
            if self._fecha_escaneo is not None:
                self._aplicar_dd7(self._fecha_escaneo)
        self._refrescar_registros(registros)

    @_protegido("Cambio de fuente")
    def showEvent(self, evento):
        super().showEvent(evento)
        self.refrescar()

    def _anotar_registro(self, linea):
        """Añade una línea a la etiqueta del registro abierto. Se llama una sola vez por registro abierto: tras la primera
        anotación el origen de la selección deja de ser 'registro', y abrir otro registro o cargar otra imagen reinicia la
        etiqueta (por eso no hace falta comprobar si la línea ya está: esa comprobación era inalcanzable)."""
        texto = self.etiqueta_registro.text()
        self.etiqueta_registro.setText(f"{texto}\n{linea}" if texto else linea)

    def _refrescar_registros(self, filas=None):
        filas = svc.listar() if filas is None else filas
        self.tabla_registros.setRowCount(0)
        for registro in filas:
            fila = self.tabla_registros.rowCount()
            self.tabla_registros.insertRow(fila)
            fecha = registro["fecha"]
            columna_fecha = fecha if registro["cambio_de_fuente_vigente"] else \
                f"{fecha}, sin cambio de fuente vigente en esa fecha"
            celdas = (columna_fecha, registro["serie_fuente"] or "", registro["user"] or "",
                      svc.texto_breve(registro, con_cambio_de_fuente=False))
            for columna, texto in enumerate(celdas):
                item = QTableWidgetItem(texto)
                item.setToolTip(texto)                 # la celda del resultado es larga y se corta
                if columna == 0:
                    item.setData(Qt.UserRole, registro["id"])          # la id, nunca una referencia al item (X10)
                    item.setData(Qt.UserRole + 1, fecha)
                self.tabla_registros.setItem(fila, columna, item)

    def _fecha_elegida(self):
        return self.selector_cambio.currentData() if self.selector_cambio.count() else None

    def _seleccion(self):
        """(id, fecha del cambio de fuente) de la fila elegida en la tabla, o None."""
        filas = self.tabla_registros.selectionModel().selectedRows()
        if not filas:
            return None
        item = self.tabla_registros.item(filas[0].row(), 0)
        return item.data(Qt.UserRole), item.data(Qt.UserRole + 1)

    def _aplicar_dd7(self, fecha):
        """DD7: el cambio de fuente a 7 días o menos de la fecha del escaneo, o sin elegir. Una selección manual no se
        toca; una automática de la imagen anterior sí se reemplaza."""
        if self._origen_seleccion == "manual":
            return
        propuesta = svc.cambio_de_fuente_por_defecto(fecha)
        indice = self.selector_cambio.findData(propuesta[0]) if propuesta else 0
        self.selector_cambio.setCurrentIndex(max(indice, 0))
        self._origen_seleccion = "automatica" if indice > 0 else None

    def _al_elegir_a_mano(self, _indice):
        self._origen_seleccion = "manual"

    # ---------------------------------------------------------------------------------------------- la imagen

    @_protegido("Seleccionar imagen")
    def _al_seleccionar_imagen(self):
        ruta, _filtro = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", FILTRO_IMAGENES)
        if not ruta:
            return
        # La carga es atómica (X7): se lee y se interpreta todo ANTES de tocar la página; si algo falla, queda igual.
        try:
            with open(ruta, "rb") as archivo:
                datos = archivo.read()
            gris, _color, dpi, fecha = motor.leer_imagen(datos)
            origen_fecha = "fecha del escaneo"
            if fecha is None:
                fecha = date.fromtimestamp(os.path.getmtime(ruta))
                origen_fecha = "fecha de modificación del archivo"
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Seleccionar imagen", f"No se pudo leer la imagen: {error}")
            return
        self._instalar_imagen(datos, os.path.basename(ruta), gris, dpi, fecha, origen_fecha)
        self._aplicar_dd7(fecha)

    def _instalar_imagen(self, datos, nombre, gris, dpi, fecha, origen_fecha):
        """Descarta todo lo de la imagen anterior (resultado, puntos, marcas, registro abierto, herramientas) y muestra la
        nueva como RGB uint8 con `nearest` (ver el docstring del módulo): la de 16 bits llega en float32 de 0 a 255 y se muestra con sus
        niveles de 8 bits redondeados (A.1), como ya se muestra la de 8 (un RGB float32 de 0 a 255 sale casi todo blanco en `imshow`).
        `fecha` es la que propone el cambio de fuente y solo se muestra: no se guarda."""
        self._descartar_resultado()
        self._descartar_puntos()
        self._registro_abierto = None
        self.etiqueta_registro.clear()
        self._apagar_herramientas()
        self._bytes, self._nombre, self._forma = datos, nombre, gris.shape
        self._fecha_escaneo = fecha
        self._origen_fecha = origen_fecha
        self.eje_imagen.clear()
        gris8 = gris if gris.dtype == np.uint8 else np.clip(np.rint(gris), 0, 255).astype(np.uint8)
        self.eje_imagen.imshow(np.dstack([gris8, gris8, gris8]), interpolation="nearest")
        self._rotular_eje_imagen()
        self.barra_imagen.update()
        self.nombre_archivo.setText(nombre)
        formato = formato_de_la_imagen(datos, nombre)
        self.etiqueta_resolucion.setText(f"{formato} · {texto_resolucion(dpi)}" if formato else texto_resolucion(dpi))
        self.etiqueta_fecha.setText(f"Fecha: {fecha.isoformat()}, {origen_fecha}" if fecha is not None else "")
        self._estado = "imagen"
        self.pestanas.setCurrentIndex(PESTANA_IMAGEN)
        self.lienzo_imagen.draw_idle()

    @_protegido("Marcar un punto")
    def _al_pulsar(self, evento):
        """Un clic cuenta solo si la página espera puntos, la lupa y el desplazar están apagados, es el botón izquierdo
        (no un doble clic) y cae DENTRO de la imagen (X2, X3). Se guarda redondeado a 3 decimales (X1)."""
        if self._bytes is None or self._estado != "imagen" or len(self._puntos) >= 2:
            return
        if self.lienzo_imagen.widgetlock.locked() or evento.inaxes is not self.eje_imagen:
            return
        if evento.button != 1 or evento.dblclick or evento.xdata is None or evento.ydata is None:
            return
        alto, ancho = self._forma
        if not (-0.5 <= evento.xdata < ancho - 0.5 and -0.5 <= evento.ydata < alto - 0.5):
            return
        punto = (round(float(evento.xdata), DECIMALES_CLIC), round(float(evento.ydata), DECIMALES_CLIC))
        self._puntos.append(punto)
        self._marcar(punto)
        self.lienzo_imagen.draw_idle()
        if len(self._puntos) == 2:
            self._analizar(None)

    def _marcar(self, punto):
        self._marcas.extend(self.eje_imagen.plot(punto[0], punto[1], "+", color=COLOR_REFERENCIA, ms=12, mew=2))

    # ---------------------------------------------------------------------------------------------- el análisis

    def _con_espera(self, texto, funcion):
        """UX1: indicador visible (con `repaint()`: el cómputo es síncrono y bloquea el bucle de eventos que lo pintaría),
        cursor de espera y `try/finally`. Nunca `processEvents`: dejaría entrar otro clic en mitad del análisis."""
        self.indicador.setText(texto)
        self.indicador.show()
        self.indicador.repaint()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return funcion()
        finally:
            QApplication.restoreOverrideCursor()
            self.indicador.hide()

    def _calcular(self, datos, puntos, parametros, consejo="Pulse Recalcular para marcar otra vez."):
        """Corre el análisis con la espera. Si falla avisa (ya con el cursor restaurado) y devuelve None sin tocar nada.
        `consejo` es lo que se le dice al físico que haga: marcar otra vez no aplica a abrir un registro."""
        try:
            return self._con_espera(TEXTO_ANALIZANDO, lambda: svc.analizar_imagen(datos, puntos, parametros))
        except ValueError as error:
            QMessageBox.warning(self, "Analizar", f"No se pudo analizar: {error}. {consejo}")
        except Exception as error:
            traceback.print_exc()
            QMessageBox.critical(self, "Analizar", f"Error inesperado al analizar ({type(error).__name__}: {error}).")
        return None

    def _analizar(self, parametros):
        self._descartar_resultado()
        resultado = self._calcular(self._bytes, list(self._puntos), parametros)
        if resultado is None:
            self._estado = "fallida"
            return None
        self._resultado = resultado
        self._estado = "analizada"
        self._mostrar(resultado)
        self.boton_guardar.setEnabled(motivo_para_no_guardar(resultado) is None)
        self.pestanas.setCurrentIndex(PESTANA_GRIS)
        return resultado

    def _mostrar(self, resultado):
        fila = fila_representativa(resultado, "gris")
        self._fig_gris.clear()
        arriba, abajo = self._fig_gris.subplots(2, 1)
        dibujar_ventana(arriba, resultado, "gris", fila)
        dibujar_perfil(abajo, resultado, "gris", fila, leyenda=True)
        self.recuadro_gris.setText(texto_recuadro(resultado, "gris"))
        self._fig_rgb.clear()
        for eje, capa in zip(self._fig_rgb.subplots(3, 1), ("R", "G", "B")):
            dibujar_perfil(eje, resultado, capa, fila, COLOR_CAPA[capa], leyenda=(capa == "R"))
        self.recuadro_rgb.setText(texto_recuadro_capas(resultado))
        self.barra_gris.update()                 # X5: sin esto, Home vuelve a la vista de la figura anterior
        self.barra_rgb.update()
        self.lienzo_gris.draw_idle()
        self.lienzo_rgb.draw_idle()

    # ------------------------------------------------------------------------------------------------ los botones

    @_protegido("Cambiar de pestaña")
    def _al_cambiar_pestana(self, indice):
        """La imagen sintética no calcula al construirse la página (son unos segundos): la primera vez que se abre su
        pestaña."""
        if indice == PESTANA_SINTETICA:
            self.sintetica.al_mostrarse()

    @_protegido("Recalcular")
    def _al_recalcular(self):
        """Conserva la imagen, su nombre y el cambio de fuente elegido; borra los puntos, las marcas y el resultado."""
        self._descartar_resultado()
        self._descartar_puntos()
        self._apagar_herramientas()
        self._registro_abierto = None
        self.etiqueta_registro.clear()
        self._estado = "imagen" if self._bytes is not None else "vacia"
        self.pestanas.setCurrentIndex(PESTANA_IMAGEN)

    @_protegido("Limpiar")
    def _al_limpiar(self):
        self._restablecer_estado()
        self.refrescar()

    @_protegido("Guardar")
    def _al_guardar(self):
        if self._resultado is None or self._estado != "analizada" or motivo_para_no_guardar(self._resultado):
            return
        fecha = self._fecha_elegida()
        if not fecha:
            QMessageBox.warning(self, "Guardar", AVISO_SIN_CAMBIO)
            return
        existe = svc.existe_vigente(fecha)
        motivos = motivos_para_confirmar(self._resultado)
        distancia = motivo_de_distancia(fecha, self._fecha_escaneo, self._origen_fecha)
        if distancia:
            motivos.insert(0, distancia)
        pregunta = texto_confirmacion(fecha, existe, motivos)
        if pregunta and QMessageBox.question(self, "Guardar", pregunta, QMessageBox.Yes | QMessageBox.No,
                                             QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            # Guardar vuelve a analizar desde los bytes y los puntos (el servicio no confía en un resultado ajeno), así
            # que va dentro de la misma espera.
            nuevo = self._con_espera("Guardando...", lambda: svc.guardar(
                usuario_actual(self), fecha, self._bytes, self._nombre, list(self._puntos), reemplazar=existe))
        except ValueError as error:
            QMessageBox.warning(self, "Guardar", f"No se guardó: {error}.")
            return
        self._registro_abierto = nuevo
        self._estado = "registro"
        self.boton_guardar.setEnabled(False)
        self.etiqueta_registro.setText(f"Guardada: cambio de fuente del {fecha}.")
        self._refrescar_registros()
        QMessageBox.information(self, "Guardar", f"Posición inicial guardada para el cambio de fuente del {fecha}.")

    @_protegido("Anular")
    def _al_anular(self):
        seleccion = self._seleccion()
        if seleccion is None:
            QMessageBox.warning(self, "Anular", "Elija en la tabla la posición inicial que quiere anular.")
            return
        id_registro, fecha = seleccion
        # X12: primero lo concreto y después el permiso; así no se pide una contraseña para algo que se va a cancelar.
        if QMessageBox.question(self, "Anular", f"¿Anular la posición inicial del cambio de fuente del {fecha}?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if DialogAdminPermisoEliminar(self.user_id).exec() != QDialog.DialogCode.Accepted:
            return
        try:
            anulado = svc.anular(id_registro, usuario_actual(self), "anulada desde la página de posición inicial")
        except ValueError as error:
            QMessageBox.warning(self, "Anular", f"No se anuló: {error}.")
            return
        if not anulado:
            QMessageBox.warning(self, "Anular", "Esa posición inicial ya estaba anulada o ya no existe.")
        elif self._registro_abierto == id_registro:
            self.etiqueta_registro.setText("Registro anulado: ya no vale para ningún PDF.")
        self._refrescar_registros()

    @_protegido("Abrir")
    def _al_doble_clic(self, fila, _columna):
        item = self.tabla_registros.item(fila, 0)
        if item is not None:
            self.abrir_registro(item.data(Qt.UserRole))

    @_protegido("Abrir", por_defecto=False)
    def abrir_registro(self, id_registro):
        """Abre un registro guardado: sus bytes, sus puntos y sus PARÁMETROS guardados (no los de hoy) se vuelven a analizar
        y se compara con lo guardado (DD3). Devuelve True si se abrió. Si no se puede leer ni analizar, avisa y la página
        queda como estaba (todo se lee y se calcula antes de tocarla). Si fallara después, al dibujar (muy improbable), la
        página queda en estado 'fallida', sin resultado y con Guardar deshabilitado, nunca con medio registro. Deja Guardar
        deshabilitado: para guardar de nuevo, Recalcular."""
        registro = svc.leer(id_registro)
        if registro is None:
            QMessageBox.warning(self, "Abrir", "El registro ya no existe.")
            return False
        try:
            gris, _color, dpi, _fecha = motor.leer_imagen(registro["imagen"])
            puntos = [tuple(float(v) for v in par) for par in json.loads(registro["puntos"])]
            parametros = json.loads(registro["parametros"])
        except (ValueError, TypeError) as error:
            QMessageBox.warning(self, "Abrir", f"No se pudo abrir el registro: {error}")
            return False
        resultado = self._calcular(registro["imagen"], puntos, parametros, consejo="No se abrió el registro.")
        if resultado is None:
            return False
        try:
            self._instalar_imagen(registro["imagen"], registro["imagen_nombre"] or "", gris, dpi, None, None)
            for punto in puntos:
                self._marcar(punto)
            self._puntos = list(puntos)
            self._resultado = resultado
            self._mostrar(resultado)
        except Exception:
            self._descartar_resultado()
            self._estado = "fallida"
            raise
        self._estado = "registro"
        self._registro_abierto = registro["id"]
        self.boton_guardar.setEnabled(False)
        self.pestanas.setCurrentIndex(PESTANA_GRIS)
        indice = self.selector_cambio.findData(registro["fecha"])
        self.selector_cambio.setCurrentIndex(max(indice, 0))
        self._origen_seleccion = "registro" if indice > 0 else None
        lineas = [f"Registro abierto: cambio de fuente del {registro['fecha']}, guardado por {registro['user'] or 'sin dato'}."]
        if registro.get("activo") == 0:
            lineas.append("Este registro está anulado: no vale para ningún PDF.")
        if indice <= 0:
            lineas.append(LINEA_SIN_CAMBIO)
        diferencias = diferencias_con_lo_guardado(registro, resultado)
        if diferencias:
            lineas.append("Lo recalculado no coincide con lo guardado:\n" + "\n".join(diferencias))
        self.etiqueta_registro.setText("\n".join(lineas))
        if diferencias:
            QMessageBox.warning(self, "Abrir", "Lo recalculado no coincide con lo guardado:\n" + "\n".join(diferencias))
        return True
