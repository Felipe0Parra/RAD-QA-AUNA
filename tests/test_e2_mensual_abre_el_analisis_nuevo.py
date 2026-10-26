"""E.2 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-82, DA-83, DA-89): en el mensual del 600 y del iX, «Imagen del campo» abre el analisis nuevo (la ventana de E.1) y deja de ofrecer el viejo.

CAUSA. La unica entrada del analisis viejo era «Imagen del campo» de `PruebaMensual600._configurar_elementos_adicionales`: el cargador compartido (`imagenUpLoader`) se construia con `analisis=True`, el
fisico elegia una imagen con «Seleccionar Imagen» y «Aceptar» corria `PruebaMensual600.analizar_imagen`. Con D.1, E.1 y F.1 el analisis nuevo ya se mide, se guarda y se imprime, pero el formulario no
lo abria; y los controles viejos (V: tiene filas vigentes en `analisis_placa_franjas`; I: tiene imagen en su fila vigente de `preguntas`) no tenian como repararse (DA-89).

LO QUE SE GARANTIZA, todo por el camino del usuario (la pagina real del 600 y del iX construida por su constructor de produccion y «Iniciar» con el boton real) y cada cosa contra una verdad que NO sale
de la produccion (sqlite3 a mano sobre copias, el BLOB decodificado por Qt, los textos escritos aqui):
  1. LA LINEA, PURA. Las ocho combinaciones de V, I y N dan los textos EXACTOS (N > V > I > nada; con V, la imagen elige entre dos textos); un archivo sin nombre dice «sin nombre de archivo»; ninguna
     constante lleva simbolos de correcto o incorrecto (DA-18); el unico sitio que usa los cinco textos es `texto_de_la_linea`; y ninguna consulta de E.2 lee una columna de `analisis_placa_*`
     (DA-89: la tabla vieja se desconecta; V solo se CUENTA).
  2. EL ESTADO EN LAS BASES REALES (copias de la produccion del 06-10, sus TRES archivos): V e I de los 19 mensuales del 600 y del iX iguales a los de sqlite3 a mano, y la linea de cada uno; las
     anuladas no cuentan; un analisis nuevo sembrado por el servicio se dice con su archivo, su fecha y su usuario.
  3. LA SECCION. El boton, el boton de la imagen guardada, la linea y el visor, en ese orden dentro del contenedor; «Seleccionar Imagen» oculto; «Aceptar» y «Cancelar» sin receptores; el visor solo
     con I; el boton de la imagen guardada solo con I; sin camino al analisis viejo (un clic programatico en «Seleccionar Imagen» y despues «Aceptar» no llaman a `analizar_imagen`).
  4. LA COMPUERTA DE PIXELES. Los 10 controles con imagen vieja pintan la MISMA imagen que antes (el oraculo: el BLOB con `QPixmap.loadFromData`, a la mitad, `KeepAspectRatio` y `SmoothTransformation`),
     y la comparacion discrimina (sin `label_imagen` o con el visor sin pintar da «no pasa»).
  5. LA VENTANA. Una por control, la misma en cada clic, con el `ref` del control, el usuario de la SESION (no el Fisico 1), la pagina de padre y la bandera `Qt.Window`; construida solo en el clic;
     cerrarla la oculta; el import de la ventana es diferido.
  6. «CERRAR CONTROL» E «INICIO». «Cerrar control» destruye la pagina y la ventana; «Inicio» (la ventana principal se cierra) oculta la ventana aunque la pagina siga viva; minimizar la ventana
     principal NO la cierra.
  7. LA LINEA SE VUELVE A ESCRIBIR al ocultarse la ventana (la ventana no emite ninguna senal al guardar).
  8. LOS FALLOS. La ventana que no se construye: un `critical` con el texto, la pagina viva, el registro en `error_log.txt`; el estado que no se puede leer: la linea lo dice y el visor se muestra.
  9. LA COMPUERTA POR AST Y POR MRO: ninguna pantalla con el cargador compartido en `analisis=True` resuelve `analizar_imagen` a `PruebaMensual600.analizar_imagen`.
 10. LOS MANEJADORES ENVUELVEN TODO SU CUERPO EN `try` (Trampa 3), por AST y por conducta.
 11. DA-89, REPARAR. «Analizar la imagen guardada» carga en la ventana los bytes de `imagen_vigente(ref)` leidos EN EL CLIC, con el nombre «imagen guardada del control N»; con los clics del 40 se analiza y
     se guarda (queda N con esos bytes y la linea lo dice al ocultar); a 300 ppp la ventana dice la resolucion y no mide; sin imagen avisa; y `VentanaPlacaMensual.cargar_imagen` es el MISMO camino
     que «Seleccionar imagen» (misma huella).
  12. RONDA 1 DEL CORRECTOR (26-10, revisores escepticos). El segundo clic TRAE AL FRENTE una ventana minimizada (o minimizada y cerrada) y conserva lo maximizado (E2-REV-PROD-1); el visor de la imagen
     vieja, «Analizar la imagen guardada» y «Seleccionar Imagen» siguen SOLO a la imagen en los 8 casos de V, I y N de la copia del 06-10 (E2-REV-P1 a P4); el parche de `close` de la prueba del
     vigilante se deshace solo, sin llevarse los de las fixtures (E2-REV-P5).
  13. RONDA 2 DEL CORRECTOR (26-10, revisores escepticos). Si leer la imagen guardada falla en el clic, el fisico ve un cuadro con el motivo, el detalle va a `error_log.txt` y nada sale del slot
     (E2-PROD-1, E2-R2P-1); el aviso que a su vez falle tampoco sale; la ventana de E.1 no se importa al construir el formulario en NINGUNA forma de `import` (E2-R2P-2: el formulario se construye
     con la ventana imposible de importar y el AST reconoce las tres formas); el visor de la imagen vieja se oculta tambien si la imagen se anula con el formulario abierto, igual que el boton (E2-R2P-3); y
     el 14 (sin fila de `preguntas`) con un analisis nuevo dice N (E2-R2P-4).

Trampa 2 (todo cuadro de dialogo se parcha: la fixture `dialogos` de `_e1_ayudas`), Trampa 3 (los temporizadores del formulario: `limpiar_recursos()` antes de cerrar cada pagina y un `sys.excepthook` que
recoge las excepciones de los slots; se exigen 0), Trampa 9 (cada pagina y cada ventana se cierran con la receta completa; la huella no mira internos de Qt), Trampa 10 (ningun `lru_cache` ni `skip` por
parametro).
Rojo contra HEAD (b29784d): el modulo `imagen_del_campo.py` y `VentanaPlacaMensual.cargar_imagen` no existen; las pruebas importan POR DENTRO (`idc()`), asi que cada una cae con su error.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import hashlib
import importlib
import importlib.util
import inspect
import shutil
import sqlite3
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt5 import sip
from PyQt5.QtCore import QDate, QEvent, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

import _bd_referencia
import data.ManejoDatos.conection as conection_mod
from _e1_ayudas import _cursor_limpio, app, cargar, cerrar, dialogos, huella, marcar, sin_simbolos, ventana_mod  # noqa: F401  (fixtures y ayudas de E.1)
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.user import Usuario
from test_c2_perfiles_y_coincidencia import CLICS_REALES
from test_d1_guardado_placa_mensual import bd, clics, placa, plantilla  # noqa: F401  (fixtures de D.1)

RAIZ = Path(__file__).resolve().parent.parent
IDC_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "imagen_del_campo.py"
SEISCIENTOS_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "seiscientos_mensual.py"
SESION = "Fisico Uno"                 # la sesion
FISICO_1 = "Fisico Dos"               # el Fisico 1 del control: DISTINTO de la sesion, o la prueba del usuario no discrimina
EQUIPOS = {"600": "Clinac 600", "ix": "Clinac ix"}

# ---- los textos, escritos AQUI (el oraculo no sale de la produccion)
TEXTO_N = "Análisis de la placa guardado: {archivo}, {fecha}, por {usuario}."
TEXTO_V = "Análisis hecho con la herramienta anterior, ya retirada: puede volver a analizar la imagen guardada con «Analizar la imagen guardada»."
TEXTO_V_SIN_IMAGEN = "Análisis hecho con la herramienta anterior, ya retirada, y sin imagen guardada: cargue el escaneo de la película en «Análisis de la placa»."
TEXTO_I = "Imagen guardada sin análisis de la placa: puede analizarla con «Analizar la imagen guardada»."
TEXTO_NADA = "Sin análisis de la placa."
TEXTO_SIN_NOMBRE = "sin nombre de archivo"
TEXTO_SIN_ESTADO = "No se pudo leer qué análisis tiene este control: {motivo}"
BOTON = "Análisis de la placa"
BOTON_IMAGEN = "Analizar la imagen guardada"
NOMBRE_IMAGEN_GUARDADA = "imagen guardada del control {ref}"

# V e I de los 19 mensuales del 600 y del iX de la copia de la produccion del 06-10 (medidos a mano con sqlite3 el 21-10 y comprobados otra vez en la prueba contra la copia, sin esta tabla)
V_I_DE_LA_PRODUCCION = {1: (0, 1), 5: (0, 1), 6: (0, 1), 13: (1, 0), 14: (0, 0), 16: (1, 0), 20: (0, 0), 22: (0, 0), 23: (0, 0), 30: (1, 1), 31: (0, 0), 35: (1, 1), 38: (1, 1), 40: (1, 1),
                        41: (1, 1), 43: (1, 1), 44: (1, 1), 45: (1, 1), 47: (0, 0)}
CON_IMAGEN = (1, 5, 6, 30, 35, 38, 40, 41, 44, 45)         # los controles vigentes con imagen vieja: la compuerta de pixeles


def idc():
    return importlib.import_module("ui.paginasControles.PruebasMensuales.imagen_del_campo")


def la_linea(v, i, n=None):
    """El texto que debe decir la linea para esos V, I y N (la tabla de verdad, escrita aqui)."""
    if n is not None:
        return TEXTO_N.format(**n)
    if v:
        return TEXTO_V if i else TEXTO_V_SIN_IMAGEN
    return TEXTO_I if i else TEXTO_NADA


class _Sesion:
    """El objeto de sesion que el menu le pasa a la pantalla (`user_id`): lo unico que se le pide es `_nombre` (y `_usuario`)."""

    def __init__(self, nombre):
        self._nombre = nombre
        self._usuario = nombre.replace(" ", "").lower()


# ------------------------------------------------------------------------------------------------------ fixtures: excepciones de slots, BD, paginas

@pytest.fixture(autouse=True)
def _excepciones_de_slots(monkeypatch):
    """Trampa 3: una excepcion dentro de un slot de Qt llama a `qFatal` y aborta el proceso; con un `sys.excepthook` propio PyQt la entrega aqui y la prueba cae con el motivo a la vista."""
    capturadas = []
    monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, traza: capturadas.append(f"{tipo.__name__}: {valor}"))
    yield capturadas
    assert not capturadas, f"un slot de Qt lanzo una excepcion: {capturadas}"


def _sembrar_usuarios(ruta):
    con = sqlite3.connect(ruta)
    for i, (usuario, nombre) in enumerate((("f1", "Fisico Uno"), ("f2", "Fisico Dos"), ("f3", "Fisico Tres")), 1):
        con.execute("INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES (?, 'x', ?, 1, ?, 'Físico Médico', 'fisico')", (usuario, nombre, str(i)))
    con.commit()
    con.close()


@pytest.fixture
def base_nueva(app, monkeypatch, tmp_path):
    """Una BD temporal que la app crea desde cero (nunca una de referencia): la ruta se redirige ANTES de construir `Conexion()`; el registro de errores va a un archivo del `tmp_path`."""
    ruta = str(tmp_path / "e2.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    conexion = Conexion()
    _sembrar_usuarios(ruta)
    yield ruta
    conexion.con.close()
    Conexion._instance = previa


def _el_log(ruta_bd):
    """El `error_log.txt` de esta prueba (junto a la BD temporal)."""
    p = Path(ruta_bd).parent / "error_log.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        cursor = con.execute(sql, parametros)
        con.commit()
        return cursor.lastrowid
    finally:
        con.close()


def _consulta(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, parametros).fetchall()
    finally:
        con.close()


def _sembrar_control_de_hoy(ruta, equipo, fisico_1=FISICO_1):
    """Un control mensual de HOY, hecho por otro fisico: al «Iniciar» la pagina lo encuentra (el fisico 1 del control NO es la sesion)."""
    return _sql(ruta, "INSERT INTO controles (equipo, control, fecha, user_id, activo) VALUES (?, 'Mensual', ?, ?, 1)", (equipo, QDate.currentDate().toString("dd/MM/yyyy"), fisico_1))


def _nueva_pagina(familia, sesion):
    if familia == "600":
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        return PruebaMensual600(_Sesion(sesion), equipo_f="Clinac 600")
    from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
    return PruebaMensualIX(_Sesion(sesion))


def _cerrar_pagina(pagina):
    """Trampa 3 y 9: los temporizadores de debounce (`QTimer()` sin padre) se detienen ANTES de destruir la pagina; despues la receta completa."""
    if sip.isdeleted(pagina):
        return
    pagina.limpiar_recursos()
    cerrar(pagina)


@pytest.fixture
def paginas(base_nueva, dialogos):
    """`crear(familia='600', sesion=SESION, iniciar=True)`: la pagina REAL del 600 o del iX, con un control de hoy hecho por otro fisico, «Iniciar» pulsado (el `information` «Control existente» esta parchado)."""
    creadas = []

    def crear(familia="600", sesion=SESION, iniciar=True):
        if iniciar:
            _sembrar_control_de_hoy(base_nueva, EQUIPOS[familia])
        pagina = _nueva_pagina(familia, sesion)
        creadas.append(pagina)
        if iniciar:
            pagina.date_box.setDate(QDate.currentDate())
            pagina.iniciar.click()
            assert getattr(pagina, "ref", None) is not None, "«Iniciar» no dejo el control abierto"
        return pagina

    crear.ruta = base_nueva
    yield crear
    for pagina in reversed(creadas):
        _cerrar_pagina(pagina)


def _copiar_una_base_de_referencia(original, destino):
    """Una base de referencia a `destino`: sus TRES archivos juntos (`.db`, `-wal`, `-shm`: copiar solo el `.db` da otra base); el md5 de los originales es el mismo antes y despues de copiar. Salta con
    HI-0 si falta (un salto por una carpeta ausente, no un `skip` por parametro: los skips de la suite siguen siendo EXACTAMENTE 4 mientras la carpeta este)."""
    if not original.exists():
        pytest.skip(f"HI-0: falta {original.name} en {_bd_referencia.CARPETA_BD}")
    nombres = [original.name, original.name + "-wal", original.name + "-shm"]

    def md5(p):
        h = hashlib.md5()
        with open(p, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
        return h.hexdigest()
    antes = {n: md5(original.parent / n) for n in nombres if (original.parent / n).exists()}
    for n in antes:
        shutil.copy2(original.parent / n, destino / n)
    despues = {n: md5(original.parent / n) for n in antes}
    assert antes == despues, "el md5 de la base de referencia cambio al copiarla"
    return str(destino / original.name)


class _CopiaAbierta:
    """Una COPIA de una base de referencia (nunca el original) con `ruta_base_datos` redirigida ANTES de construir `Conexion()`; `crear(ref)` construye la pagina del control con su constructor de produccion,
    pone su fecha y pulsa «Iniciar» (sesion «Javier Castillo»: distinta del Fisico 1 del control)."""

    def __init__(self, ruta, conexion):
        self.ruta, self.conexion, self.creadas = ruta, conexion, []

    def crear(self, ref, sesion="Javier Castillo"):
        from ui.util_fechas import fecha_control_a_qdate
        equipo, fecha = _consulta(self.ruta, "SELECT equipo, fecha FROM controles WHERE id = ?", (ref,))[0]
        pagina = _nueva_pagina("600" if equipo == "Clinac 600" else "ix", sesion)
        self.creadas.append(pagina)
        pagina.date_box.setDate(fecha_control_a_qdate(fecha))
        pagina.iniciar.click()
        assert pagina.ref == ref, (pagina.ref, ref)
        return pagina

    __call__ = crear


def _abrir_copia(monkeypatch, tmp_path, original):
    ruta = _copiar_una_base_de_referencia(original, tmp_path)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    return _CopiaAbierta(ruta, Conexion()), previa


def _cerrar_copia(copia, previa):
    for pagina in reversed(copia.creadas):
        _cerrar_pagina(pagina)
    copia.conexion.con.close()
    Conexion._instance = previa


@pytest.fixture
def produccion(app, monkeypatch, tmp_path, dialogos):
    """La copia de la produccion del 06-10 (declarada en `tests/_bd_referencia.py`)."""
    copia, previa = _abrir_copia(monkeypatch, tmp_path, _bd_referencia.BD_PRODUCCION_06_10)
    yield copia
    _cerrar_copia(copia, previa)


@pytest.fixture
def rebuild_21_09(app, monkeypatch, tmp_path, dialogos):
    copia, previa = _abrir_copia(monkeypatch, tmp_path, _bd_referencia.BD_REBUILD_21_09)
    yield copia
    _cerrar_copia(copia, previa)


def _v_i_a_mano(ruta, ref):
    """V e I contados con sqlite3 a mano (el oraculo): filas vigentes de `analisis_placa_franjas` por `ref`, y una imagen no vacia en la fila vigente de `preguntas`."""
    v = _consulta(ruta, "SELECT COUNT(*) FROM analisis_placa_franjas WHERE ref = ? AND (activo IS NULL OR activo = 1)", (ref,))[0][0]
    filas = _consulta(ruta, "SELECT imagen FROM preguntas WHERE ref = ? AND (activo IS NULL OR activo = 1)", (ref,))
    i = bool(filas) and filas[0][0] is not None and len(filas[0][0]) > 0
    return int(v > 0), int(i)


def _png_pequeno():
    """Un PNG valido y diminuto (lo que `QPixmap.loadFromData` sabe pintar), para sembrar una imagen vieja sin cargar los 9 MB de la sintetica."""
    from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
    imagen = QImage(8, 6, QImage.Format_RGB32)
    imagen.fill(0x336699)
    datos = QByteArray()
    buffer = QBuffer(datos)
    buffer.open(QIODevice.WriteOnly)
    assert imagen.save(buffer, "PNG")
    return bytes(datos)


def _de(pagina, nombre):
    """Una pieza que E.2 deja en la pagina (`boton_analisis_placa`, `boton_imagen_guardada`, `linea_analisis_placa`): si la pagina no la tiene, la prueba CAE POR ASERCION diciendo que «Imagen del campo» no
    es la seccion nueva (y no por un `AttributeError` que no dice nada)."""
    pieza = getattr(pagina, nombre, None)
    assert pieza is not None, f"la pagina no tiene `{nombre}`: «Imagen del campo» no es la seccion nueva de E.2"
    return pieza


def _ventanas_vivas():
    from ui.paginasControles.PruebasMensuales.placa_mensual import VentanaPlacaMensual
    return [w for w in QApplication.allWidgets() if isinstance(w, VentanaPlacaMensual) and not sip.isdeleted(w)]


def _procesar_borrados():
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _seccion(pagina):
    """El contenedor de «Imagen del campo» dentro del toolbox de aspectos mecanicos."""
    toolbox = pagina.subtool
    for i in range(toolbox.count()):
        if toolbox.itemText(i) == "Imagen del campo":
            return toolbox.widget(i)
    raise AssertionError("la pagina no tiene «Imagen del campo»")


def _widgets_de(contenedor):
    capa = contenedor.layout()
    return [capa.itemAt(i).widget() for i in range(capa.count())]


def _visor(pagina):
    """El widget que devolvio el cargador (`imagenUpLoader`): el padre del layout `layout_imagen`."""
    return pagina.layout_imagen.parentWidget()


def _sembrar_un_analisis_nuevo(ref, placa, clics, capa="G", usuario="Fisico Uno", nombre="placa_sintetica.png"):
    """Un analisis nuevo REAL por la unica puerta (el servicio de D.1), con la placa sintetica de PF.0."""
    import copy
    from analisisImagenes import placa_mensual as motor
    from services import placa_mensual as svc
    return svc.guardar(ref, usuario, placa.datos, nombre, clics, copy.deepcopy(motor.VALORES_DE_LA_GEOMETRIA), capa, "automatico")


# ======================================================================================================================================= 1. la linea, pura

COMBINACIONES = [(v, i, n) for v in (False, True) for i in (False, True) for n in (False, True)]


class TestLaLineaEsPura:
    @pytest.mark.parametrize("v,i,n", COMBINACIONES)
    def test_las_ocho_combinaciones_dan_el_texto_exacto(self, v, i, n):
        """La tabla de verdad entera (N > V > I > nada; con V, la imagen elige entre dos textos). El texto con N lleva el archivo, la fecha del registro y quien guardo."""
        m = idc()
        registro = {"archivo": "placa_x.png", "fecha": "2026-10-21 15:42:51", "usuario": "Fisico Uno", "capa": "G"} if n else None
        texto = m.texto_de_la_linea(m.EstadoDeLaPlaca(v=v, i=i, n=registro))
        assert texto == la_linea(v, i, registro)

    @pytest.mark.parametrize("archivo", [None, ""])
    def test_un_archivo_sin_nombre_lo_dice(self, archivo):
        m = idc()
        texto = m.texto_de_la_linea(m.EstadoDeLaPlaca(v=False, i=False, n={"archivo": archivo, "fecha": "2026-10-21 15:42:51", "usuario": "Fisico Uno", "capa": "R"}))
        assert texto == TEXTO_N.format(archivo=TEXTO_SIN_NOMBRE, fecha="2026-10-21 15:42:51", usuario="Fisico Uno")
        assert "None" not in texto

    def test_el_estado_es_inmutable(self):
        import dataclasses
        m = idc()
        e = m.EstadoDeLaPlaca(v=True, i=False, n=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.v = False

    def test_los_textos_son_los_escritos_aqui(self):
        m = idc()
        assert m.TEXTO_DEL_BOTON == BOTON
        assert m.TEXTO_DEL_BOTON_IMAGEN == BOTON_IMAGEN
        assert m.TEXTO_CON_N == TEXTO_N
        assert m.TEXTO_CON_V == TEXTO_V
        assert m.TEXTO_CON_V_SIN_IMAGEN == TEXTO_V_SIN_IMAGEN
        assert m.TEXTO_CON_I == TEXTO_I
        assert m.TEXTO_SIN_NADA == TEXTO_NADA
        assert m.TEXTO_SIN_NOMBRE == TEXTO_SIN_NOMBRE
        assert m.TEXTO_SIN_ESTADO == TEXTO_SIN_ESTADO
        assert m.NOMBRE_DE_LA_IMAGEN_GUARDADA == NOMBRE_IMAGEN_GUARDADA

    def test_ninguna_constante_de_texto_lleva_simbolos_ni_unidades_entre_parentesis(self):
        """DA-18 (sin simbolos de correcto o incorrecto) y NAV-D1 (sin unidades entre parentesis): todo texto del modulo que el fisico ve."""
        m = idc()
        textos = {n: v for n, v in vars(m).items() if n.isupper() and isinstance(v, str)}
        assert len(textos) >= 9, sorted(textos)
        for nombre, texto in textos.items():
            assert sin_simbolos(texto), (nombre, texto)
        # lo que sale en un `critical` o un aviso tambien
        for texto in (m.TEXTO_NO_ABRE.format(motivo="RuntimeError: x"), m.AVISO_SIN_IMAGEN, m.TEXTO_NO_CARGA.format(motivo="RuntimeError: x")):
            assert sin_simbolos(texto), texto

    def test_el_unico_sitio_que_usa_los_cinco_textos_es_texto_de_la_linea(self):
        """Una operacion, una definicion: quien necesite saber que dice la linea llama a `texto_de_la_linea`, no vuelve a elegir entre los textos."""
        arbol = ast.parse(IDC_PY.read_text(encoding="utf-8"))
        guardados = {"TEXTO_CON_N", "TEXTO_CON_V", "TEXTO_CON_V_SIN_IMAGEN", "TEXTO_CON_I", "TEXTO_SIN_NADA"}
        dentro = {}
        for funcion in [n for n in arbol.body if isinstance(n, ast.FunctionDef)]:
            for nodo in ast.walk(funcion):
                if isinstance(nodo, ast.Name) and nodo.id in guardados and isinstance(nodo.ctx, ast.Load):
                    dentro.setdefault(nodo.id, set()).add(funcion.name)
        assert dentro == {n: {"texto_de_la_linea"} for n in guardados}, dentro
        # y fuera de las funciones (al nivel del modulo o de una clase) nadie los lee
        for nodo in arbol.body:
            if isinstance(nodo, ast.FunctionDef):
                continue
            leidos = {n.id for n in ast.walk(nodo) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            assert not (leidos & guardados), (ast.dump(nodo)[:80], leidos & guardados)

    def test_ninguna_consulta_de_e2_lee_una_columna_de_analisis_placa(self):
        """DA-89: la tabla vieja se desconecta. La unica consulta SQL del modulo es el COUNT de V (`SELECT COUNT(*) FROM analisis_placa_franjas WHERE ref = ?` con el filtro de vigencia dentro del
        mismo f-string); nada lee una columna de `analisis_placa_*` y nada la escribe."""
        arbol = ast.parse(IDC_PY.read_text(encoding="utf-8"))
        ejecuciones = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("execute", "executemany", "executescript")]
        assert len(ejecuciones) == 1, [ast.dump(e.args[0])[:60] for e in ejecuciones]
        primero = ejecuciones[0].args[0]
        assert isinstance(primero, ast.JoinedStr), "el COUNT lleva el filtro de vigencia DENTRO del f-string (si va aparte, el analizador de ES1 lo ve opaco)"
        literal = "".join(p.value for p in primero.values if isinstance(p, ast.Constant))
        assert literal.startswith("SELECT COUNT(*) FROM analisis_placa_franjas WHERE ref = ?"), literal
        assert any(isinstance(p, ast.FormattedValue) and isinstance(p.value, ast.Call) and getattr(p.value.func, "id", None) == "filtro_activo" for p in primero.values)
        # ninguna otra cadena del codigo (fuera de los docstrings) nombra una tabla vieja: nadie arma otra consulta en una variable
        docstrings = {id(n.body[0].value) for n in ast.walk(arbol) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr)
                      and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)}
        del_count = {id(n) for n in ast.walk(primero)}
        otras = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "analisis_placa_" in n.value and id(n) not in docstrings and id(n) not in del_count]
        assert otras == [], otras


# ======================================================================================================================================= 2. el estado en las bases reales

class TestElEstadoEnLasBasesReales:
    def test_v_e_i_de_los_19_mensuales_son_los_de_sqlite3_a_mano_y_la_linea_dice_lo_que_toca(self, produccion):
        """La copia de la produccion del 06-10: V e I de cada mensual del 600 y del iX contra el oraculo (sqlite3 a mano y la tabla medida el 21-10) y la linea de cada uno."""
        m = idc()
        refs = [r[0] for r in _consulta(produccion.ruta, "SELECT id FROM controles WHERE control = 'Mensual' AND equipo IN ('Clinac 600', 'Clinac ix') ORDER BY id")]
        assert refs == sorted(V_I_DE_LA_PRODUCCION), refs
        for ref in refs:
            esperado = V_I_DE_LA_PRODUCCION[ref]
            assert _v_i_a_mano(produccion.ruta, ref) == esperado, ref
            estado = m.estado_de_la_placa(ref)
            assert (int(estado.v), int(estado.i)) == esperado, (ref, estado)
            assert estado.n is None
            assert m.texto_de_la_linea(estado) == la_linea(*esperado), ref

    @pytest.mark.parametrize("ref,texto", [(38, TEXTO_V), (1, TEXTO_I), (13, TEXTO_V_SIN_IMAGEN), (22, TEXTO_NADA), (14, TEXTO_NADA), (20, TEXTO_NADA), (23, TEXTO_NADA), (16, TEXTO_V_SIN_IMAGEN),
                                            (6, TEXTO_I), (40, TEXTO_V)])
    def test_la_linea_en_la_pagina_real_es_la_del_caso(self, produccion, ref, texto):
        """Los casos del plan (38: imagen y analisis viejo; 1: solo imagen; 13: solo analisis viejo; 22: nada) y los tres sin fila de `preguntas` (14, 20, 23), en la PAGINA, no solo en la funcion."""
        pagina = produccion(ref)
        assert _de(pagina, "linea_analisis_placa").text() == texto

    def test_en_rebuild_21_09_el_control_44_no_tiene_fila_de_preguntas_y_no_tiene_imagen(self, rebuild_21_09):
        """En `Rebuild_21-09` el control 44 no tiene fila de `preguntas`: I es falso (sqlite3 a mano) y la funcion lo dice igual; V sale igual que a mano."""
        m = idc()
        assert _consulta(rebuild_21_09.ruta, "SELECT COUNT(*) FROM preguntas WHERE ref = 44")[0][0] == 0
        v, i = _v_i_a_mano(rebuild_21_09.ruta, 44)
        assert i == 0
        estado = m.estado_de_la_placa(44)
        assert (int(estado.v), int(estado.i)) == (v, i)
        assert m.texto_de_la_linea(estado) == la_linea(v, i)

    def test_las_anuladas_no_cuentan(self, base_nueva):
        """Franjas y `preguntas` ANULADAS con el primitivo real dejan V e I en falso; vigentes, en verdadero. (El primitivo: `sql_anular_bloque` de EB1, la unica forma de anular un bloque.)"""
        from services.anulacion import sql_anular_bloque
        m = idc()
        ref = _sql(base_nueva, "INSERT INTO controles (equipo, control, fecha, activo) VALUES ('Clinac 600', 'Mensual', '10/2026', 1)")
        _sql(base_nueva, "INSERT INTO preguntas (ref, imagen, activo) VALUES (?, ?, 1)", (ref, b"imagen cualquiera"))
        _sql(base_nueva, "INSERT INTO analisis_placa_franjas (ref, franja, activo) VALUES (?, 1, 1)", (ref,))
        estado = m.estado_de_la_placa(ref)
        assert (estado.v, estado.i) == (True, True)
        for tabla, clave in (("analisis_placa_franjas", [("ref", ref)]), ("preguntas", [("ref", ref)])):
            sql, parametros = sql_anular_bloque(tabla, [c for c, _ in clave]), [v for _, v in clave]
            _sql(base_nueva, sql, tuple(parametros))
        assert _v_i_a_mano(base_nueva, ref) == (0, 0)
        estado = m.estado_de_la_placa(ref)
        assert (estado.v, estado.i) == (False, False)
        assert m.texto_de_la_linea(estado) == TEXTO_NADA

    def test_un_analisis_nuevo_sembrado_se_dice_con_su_archivo_su_fecha_y_su_usuario(self, produccion, placa, clics):
        """N gana a V e I (E2-D10): en el 40 (V e I), el 1 (solo I), el 13 (solo V), el 22 (una fila de `preguntas` sin imagen) y el 14 (NINGUNA fila de `preguntas`), la linea dice el archivo, la
        `fecha_registro` y el `usuario` del registro (quien guardo, no la sesion): N no depende de la imagen ni de que exista su fila (E2-R2P-4)."""
        from services import placa_mensual as svc
        for ref in (40, 1, 13, 22, 14):
            _sembrar_un_analisis_nuevo(ref, placa, clics, usuario="Fisico Tres")
            registro = svc.leer(ref)
            esperado = TEXTO_N.format(archivo="placa_sintetica.png", fecha=registro["fecha_registro"], usuario="Fisico Tres")
            assert idc().texto_de_la_linea(idc().estado_de_la_placa(ref)) == esperado
        pagina = produccion(40)
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_N.format(archivo="placa_sintetica.png", fecha=svc.leer(40)["fecha_registro"], usuario="Fisico Tres")
        assert _de(pagina, "linea_analisis_placa").text() != TEXTO_V


# ======================================================================================================================================= 3. la seccion

@pytest.mark.parametrize("familia", ["600", "ix"])
class TestLaSeccion:
    def test_el_orden_es_boton_boton_de_la_imagen_linea_y_visor(self, paginas, familia):
        pagina = paginas(familia)
        contenedor = _seccion(pagina)
        assert contenedor is pagina.imagen_campo
        assert _widgets_de(contenedor) == [_de(pagina, "boton_analisis_placa"), _de(pagina, "boton_imagen_guardada"), _de(pagina, "linea_analisis_placa"), _visor(pagina)]
        assert _de(pagina, "boton_analisis_placa").text() == BOTON
        assert _de(pagina, "boton_imagen_guardada").text() == BOTON_IMAGEN
        assert _de(pagina, "linea_analisis_placa").wordWrap()
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_NADA

    def test_seleccionar_imagen_esta_oculto_y_aceptar_y_cancelar_no_tienen_receptores(self, paginas, familia):
        pagina = paginas(familia)
        assert pagina.boton_subir.isHidden()
        assert pagina.boton_subir.text() == "Seleccionar Imagen"
        for boton in (pagina.boton_aceptar, pagina.boton_cancel):
            assert boton.receivers(boton.clicked) == 0, boton.text()

    def test_el_visor_y_el_boton_de_la_imagen_solo_con_imagen_vieja(self, paginas, familia):
        """Sin imagen vieja el visor no se muestra y el boton de la imagen guardada tampoco; con ella (se siembra en `preguntas`) los dos y la linea lo dice."""
        sin = paginas(familia)
        assert _visor(sin).isHidden()
        assert _de(sin, "boton_imagen_guardada").isHidden()
        assert not _de(sin, "boton_analisis_placa").isHidden()
        assert _de(sin, "linea_analisis_placa").text() == TEXTO_NADA
        _sql(paginas.ruta, "INSERT INTO preguntas (ref, imagen, activo) VALUES (?, ?, 1)", (sin.ref, _png_pequeno()))
        con_imagen = paginas(familia, iniciar=False)
        con_imagen.date_box.setDate(QDate.currentDate())
        con_imagen.iniciar.click()
        assert con_imagen.ref == sin.ref
        assert not _visor(con_imagen).isHidden()
        assert not _de(con_imagen, "boton_imagen_guardada").isHidden()
        assert _de(con_imagen, "linea_analisis_placa").text() == TEXTO_I

    def test_no_hay_camino_al_analisis_viejo(self, paginas, familia, tmp_path, monkeypatch, placa):
        """Un clic programatico en el boton oculto «Seleccionar Imagen» y despues en «Aceptar» NO llaman a `PruebaMensual600.analizar_imagen` (un espia en la CLASE, antes de construir la pagina). En HEAD
        el cargador se construia con `analisis=True`: el segundo clic llamaba una vez."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        llamadas = []
        monkeypatch.setattr(PruebaMensual600, "analizar_imagen", lambda self, *a, **k: llamadas.append(1))
        archivo = tmp_path / "placa.png"
        archivo.write_bytes(placa.datos)
        monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(archivo), "")))
        pagina = paginas(familia)
        pagina.boton_subir.click()
        pagina.boton_aceptar.click()
        pagina.boton_aceptar.click()
        assert llamadas == []


def test_el_cargador_se_construye_sin_analisis_y_ya_no_se_conecta_aceptar_a_subirlisto():
    """Los dos cambios que cierran el camino (E2-D2): el cargador con `analisis=False` y «Aceptar» sin la conexion a `subirlisto`; por AST sobre el archivo de produccion. (La conducta, con la pagina real,
    la prueba `test_no_hay_camino_al_analisis_viejo`; la compuerta por AST y por MRO, `TestNingunaPantallaLlegaAlAnalisisViejo`.)"""
    fuente = SEISCIENTOS_PY.read_text(encoding="utf-8")
    metodos = [n for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.FunctionDef) and n.name == "_configurar_elementos_adicionales"]
    assert len(metodos) == 1
    cuerpo = ast.get_source_segment(fuente, metodos[0])
    cargadores = [n for n in ast.walk(metodos[0]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "imagenUpLoader"]
    assert len(cargadores) == 1
    assert _analisis_de(cargadores[0]) is False, "el cargador del formulario se construye con `analisis=False` (por palabra clave o posicional; lo que no es un literal cuenta como verdadero)"
    assert "self.boton_aceptar.clicked.connect(self.subirlisto)" not in cuerpo
    assert "seccion_imagen_del_campo" in cuerpo


def test_el_bloque_de_imagen_del_campo_son_tres_lineas_y_el_visor_viejo_sigue_despues():
    """E2-D1: en `seiscientos_mensual.py` el bloque «Imagen del campo» son TRES lineas seguidas (el comentario, el import diferido y la construccion de la seccion con el cargador sin analisis), la
    `addItem` sigue igual y `_mostrar_imagen_guardada()` se llama despues de agregar la pagina (IM4: pinta la imagen en el visor ya agregado). El numero de lineas del archivo no cambia respecto de
    HEAD (Trampa 5; lo mide `remapear_censos.py` en seco: 0 citas que se mueven), sin fijar aqui un total que G.1 cambiara."""
    lineas = [l.strip() for l in SEISCIENTOS_PY.read_text(encoding="utf-8").splitlines()]
    i = next(n for n, l in enumerate(lineas) if l.startswith("# Imagen del campo"))
    assert lineas[i + 1].startswith("from ui.paginasControles.PruebasMensuales.imagen_del_campo import seccion_imagen_del_campo")
    assert lineas[i + 2].startswith("self.imagen_campo = seccion_imagen_del_campo(self, self.imagenUpLoader(analisis=False))")
    assert lineas[i + 3] == "self.subtool.addItem(self.imagen_campo, 'Imagen del campo')"
    assert lineas[i + 5].startswith("# IM4: mostrar la imagen ya guardada de este control, si la hay.")
    assert lineas[i + 6] == "self._mostrar_imagen_guardada()"


# ======================================================================================================================================= 4. la compuerta de pixeles

def _oraculo_de_pixeles(blob):
    """Lo que IM4 dice que se pinta: el BLOB a la mitad, conservando la proporcion, suavizado. Independiente del formulario: (ancho, alto, sha256 de los pixeles en ARGB32)."""
    pm = QPixmap()
    if not pm.loadFromData(bytes(blob)):
        return None
    escalado = pm.scaled(int(pm.width() * 0.5), int(pm.height() * 0.5), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _huella_del_pixmap(escalado)


def _huella_del_pixmap(pm):
    if pm is None or pm.isNull():
        return None
    imagen = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    puntero = imagen.constBits()
    puntero.setsize(imagen.sizeInBytes())
    return (imagen.width(), imagen.height(), hashlib.sha256(bytes(puntero)).hexdigest())


def _pinta_lo_que_dice_im4(pagina, blob):
    """True si la etiqueta del visor de la pagina PINTA el oraculo, pixel a pixel. Sin `label_imagen` (o con la etiqueta sin pintar) da False: la comparacion discrimina."""
    etiqueta = getattr(pagina, "label_imagen", None)
    if etiqueta is None or sip.isdeleted(etiqueta):
        return False
    pintado = _huella_del_pixmap(etiqueta.pixmap())
    esperado = _oraculo_de_pixeles(blob)
    return esperado is not None and pintado == esperado


class TestLaCompuertaDePixeles:
    def test_los_10_controles_con_imagen_pintan_lo_mismo_que_antes(self, produccion):
        """Los 10 controles con imagen vieja de la copia del 06-10 (1, 5, 6, 30, 35, 38, 40, 41, 44 —un TIFF RGBA de 2728 x 2720— y 45): el `pixmap()` de `label_imagen` es el oraculo. Es de no-regresion:
        pasa antes y despues de E.2. Se mide que las paginas MUEREN (`sip.isdeleted`), no el VmRSS (el asignador no devuelve la memoria)."""
        con_imagen = sorted(r for r, (v, i) in V_I_DE_LA_PRODUCCION.items() if i and r != 43)
        assert tuple(con_imagen) == CON_IMAGEN
        assert sorted(r[0] for r in _consulta(produccion.ruta, "SELECT c.id FROM controles c JOIN preguntas p ON p.ref = c.id WHERE c.control = 'Mensual' AND c.equipo IN ('Clinac 600', 'Clinac ix') "
                                                                "AND (c.activo IS NULL OR c.activo = 1) AND (p.activo IS NULL OR p.activo = 1) AND p.imagen IS NOT NULL AND length(p.imagen) > 0")) == sorted(CON_IMAGEN)
        from data.ManejoDatos.load import imagen_vigente
        fallos, muertas = [], []
        for ref in CON_IMAGEN:
            pagina = produccion(ref)
            blob = imagen_vigente(ref)
            if not _pinta_lo_que_dice_im4(pagina, blob):
                fallos.append((ref, _huella_del_pixmap(pagina.label_imagen.pixmap()) if getattr(pagina, "label_imagen", None) is not None else None, _oraculo_de_pixeles(blob)))
            _cerrar_pagina(pagina)
            muertas.append(sip.isdeleted(pagina))
        assert not fallos, f"el visor de la imagen vieja ya no pinta lo mismo en {[f[0] for f in fallos]}: {fallos}"
        assert all(muertas), muertas

    def test_la_comparacion_discrimina(self, produccion):
        """La compuerta no es decorativa: sin `label_imagen` o con el visor sin pintar la funcion de comparacion da «no pasa»."""
        from data.ManejoDatos.load import imagen_vigente
        pagina = produccion(1)
        blob = imagen_vigente(1)
        assert _pinta_lo_que_dice_im4(pagina, blob)
        pagina.label_imagen.setPixmap(QPixmap())
        assert not _pinta_lo_que_dice_im4(pagina, blob)
        del pagina.label_imagen
        assert not _pinta_lo_que_dice_im4(pagina, blob)
        # y un oraculo de otra imagen tampoco pasa
        otra = produccion(5)
        assert not _pinta_lo_que_dice_im4(otra, blob)


# ======================================================================================================================================= 5. la ventana

NOMBRE_DE_E1 = "ui.paginasControles.PruebasMensuales.placa_mensual"


def _importa_la_ventana_de_e1(nodo):
    """True si el nodo del AST importa la ventana de E.1 (`placa_mensual` del paquete `PruebasMensuales`, no el servicio `services.placa_mensual`) en cualquiera de sus formas."""
    if isinstance(nodo, ast.Import):
        return any(a.name == NOMBRE_DE_E1 for a in nodo.names)
    if isinstance(nodo, ast.ImportFrom):
        modulo = nodo.module or ""
        if nodo.level:                                    # el relativo: `from . import placa_mensual` o `from .placa_mensual import X` (dentro de PruebasMensuales)
            return modulo == "placa_mensual" or (modulo == "" and any(a.name == "placa_mensual" for a in nodo.names))
        return modulo == NOMBRE_DE_E1 or (modulo == "ui.paginasControles.PruebasMensuales" and any(a.name == "placa_mensual" for a in nodo.names))
    return False


class TestLaVentana:
    def test_antes_del_clic_no_hay_ventana_y_dos_clics_dan_una_sola(self, paginas, dialogos):
        """La ventana se construye en el clic (con un analisis guardado cuesta 2.7 s: no se construye al abrir el formulario). Dos clics: una ventana, la misma; `ref` del control, usuario de la SESION (no el
        Fisico 1), la pagina de padre, ventana de verdad con la bandera `Qt.Window`; 0 cuadros para un control sin analisis nuevo."""
        pagina = paginas("600")
        assert getattr(pagina, "ventana_placa", None) is None
        assert _ventanas_vivas() == []
        cuadros = len(dialogos.llamadas)
        _de(pagina, "boton_analisis_placa").click()
        v1 = pagina.ventana_placa
        _de(pagina, "boton_analisis_placa").click()
        v2 = pagina.ventana_placa
        assert len(dialogos.llamadas) == cuadros, f"construir la ventana de un control sin analisis nuevo no abre ningun cuadro: {dialogos.llamadas[cuadros:]}"
        assert v1 is v2
        assert _ventanas_vivas() == [v1]
        assert v1.ref == pagina.ref
        assert v1.usuario == SESION != pagina.nombre_fisico1 == FISICO_1
        assert v1.equipo == "Clinac 600"
        assert v1.parentWidget() is pagina
        assert v1.isWindow()
        assert v1.windowFlags() & Qt.Window
        assert v1.isVisible()

    def test_ix_abre_la_ventana_con_su_equipo(self, paginas, dialogos):
        pagina = paginas("ix")
        _de(pagina, "boton_analisis_placa").click()
        assert pagina.ventana_placa.equipo == "Clinac ix"
        assert pagina.ventana_placa.ref == pagina.ref
        assert dialogos.llamadas and all(c["tipo"] == "information" for c in dialogos.llamadas), dialogos.orden()     # solo el «Control existente» de «Iniciar»

    def test_cerrar_la_ventana_la_oculta_y_el_segundo_clic_la_vuelve_a_mostrar_la_misma(self, paginas):
        pagina = paginas("600")
        _de(pagina, "boton_analisis_placa").click()
        v = pagina.ventana_placa
        v.close()
        assert not v.isVisible() and not sip.isdeleted(v)
        _de(pagina, "boton_analisis_placa").click()
        assert pagina.ventana_placa is v
        assert v.isVisible()

    @pytest.mark.parametrize("estado_previo,maximizada", [("minimizada", False), ("minimizada_y_cerrada", False), ("maximizada_y_minimizada", True)])
    def test_el_segundo_clic_trae_al_frente_una_ventana_minimizada(self, paginas, estado_previo, maximizada):
        """E2-REV-PROD-1 (OBJETIVO 1: «si ya esta abierta, se trae al frente»): si el fisico minimizo la ventana de la placa (o la minimizo y la cerro desde la barra de tareas), el segundo clic en
        «Analisis de la placa» la DEVUELVE a la pantalla: la misma ventana, a la vista y sin el estado minimizado; si estaba maximizada sigue maximizada (solo se quita lo minimizado). Una ventana con
        padre no tiene boton propio en la barra de tareas de Windows: minimizada, el fisico no tiene otra forma de volver a ella."""
        pagina = paginas("600")
        _de(pagina, "boton_analisis_placa").click()
        v = pagina.ventana_placa
        if maximizada:
            v.showMaximized()
            QApplication.processEvents()
            assert v.isMaximized()
        v.showMinimized()
        QApplication.processEvents()
        if estado_previo == "minimizada_y_cerrada":
            v.close()
            QApplication.processEvents()
            assert not v.isVisible()
        assert v.isMinimized(), "la precondicion de la prueba: la ventana esta minimizada"
        _de(pagina, "boton_analisis_placa").click()
        QApplication.processEvents()
        assert pagina.ventana_placa is v
        assert v.isVisible()
        assert not v.isMinimized(), "el segundo clic deja la ventana minimizada: no se trae al frente"
        assert v.isMaximized() is maximizada

    def test_el_import_de_la_ventana_esta_dentro_de_abrir_analisis_placa(self):
        """Por AST: el modulo no importa la ventana de E.1 (`placa_mensual` de `PruebasMensuales`) arriba NI en ninguna otra funcion, en NINGUNA forma de `import` (`from m import X`, `from p import m`,
        `import p.m`, el relativo); solo lo hace `abrir_analisis_placa` (si E.1 fallara al importar, el formulario se abre igual). E2-R2P-2: antes solo reconocia la primera forma."""
        arbol = ast.parse(IDC_PY.read_text(encoding="utf-8"))
        arriba = [n for n in arbol.body if _importa_la_ventana_de_e1(n)]
        assert not arriba, [ast.dump(n)[:90] for n in arriba]
        donde = []
        for funcion in [n for n in arbol.body if isinstance(n, ast.FunctionDef)]:
            for nodo in ast.walk(funcion):
                if _importa_la_ventana_de_e1(nodo):
                    donde.append(funcion.name)
        for clase in [n for n in arbol.body if isinstance(n, ast.ClassDef)]:
            for nodo in ast.walk(clase):
                if _importa_la_ventana_de_e1(nodo):
                    donde.append(clase.name)
        assert donde == ["abrir_analisis_placa"], donde

    @pytest.mark.parametrize("fuente,es_de_e1", [
        ("from ui.paginasControles.PruebasMensuales.placa_mensual import VentanaPlacaMensual", True),
        ("from ui.paginasControles.PruebasMensuales import placa_mensual", True),
        ("from ui.paginasControles.PruebasMensuales import placa_mensual as _pm", True),
        ("import ui.paginasControles.PruebasMensuales.placa_mensual", True),
        ("import ui.paginasControles.PruebasMensuales.placa_mensual as _pm", True),
        ("from . import placa_mensual", True),
        ("from .placa_mensual import VentanaPlacaMensual", True),
        ("from services import placa_mensual as svc", False),
        ("from services.placa_mensual import leer", False),
        ("import services.placa_mensual", False),
        ("from ui.paginasControles.PruebasMensuales import seiscientos_mensual", False),
    ])
    def test_el_detector_de_imports_de_la_ventana_discrimina(self, fuente, es_de_e1):
        """Control del detector de arriba: las siete formas de importar la ventana de E.1 se reconocen y los otros `placa_mensual` (el servicio) y los otros modulos del paquete, no."""
        assert _importa_la_ventana_de_e1(ast.parse(fuente).body[0]) is es_de_e1

    def test_al_construir_el_formulario_no_se_importa_ni_se_construye_la_ventana(self, paginas, dialogos, monkeypatch):
        """La ventana solo se importa y se construye en el clic. (1) NO SE IMPORTA: con la ventana de E.1 IMPOSIBLE de importar (`sys.modules[...] = None` y el atributo del paquete quitado, que es lo
        que hace fallar tambien `from paquete import modulo`) el formulario se construye igual, la linea dice lo que toca y el clic dice por que no se abre; (2) NO SE CONSTRUYE: con el constructor espiado,
        abrir y «Iniciar» el formulario no lo llama y el primer clic, ya con E.1 importable, lo llama una vez. E2-R2P-2: antes solo miraba el constructor y la forma `from paquete import modulo` pasaba."""
        import ui.paginasControles.PruebasMensuales as paquete
        mod = ventana_mod()
        llamadas = []
        original = mod.VentanaPlacaMensual.__init__
        monkeypatch.setattr(mod.VentanaPlacaMensual, "__init__", lambda self, *a, **k: llamadas.append(a) or original(self, *a, **k))
        dialogos.criticos_esperados = True
        with monkeypatch.context() as sin_e1:
            sin_e1.setitem(sys.modules, NOMBRE_DE_E1, None)
            sin_e1.delattr(paquete, "placa_mensual", raising=False)
            pagina = paginas("600")
            assert _de(pagina, "linea_analisis_placa").text() == TEXTO_NADA
            assert llamadas == []
            _de(pagina, "boton_analisis_placa").click()
            criticos = dialogos.de("critical")
            assert len(criticos) == 1 and criticos[0]["texto"].startswith("No se pudo abrir el análisis de la placa (ModuleNotFoundError: "), criticos
            assert getattr(pagina, "ventana_placa", None) is None
        assert llamadas == []
        _de(pagina, "boton_analisis_placa").click()
        assert len(llamadas) == 1


# ======================================================================================================================================= 6. «Cerrar control» e «Inicio»

def _cerrar_principal(principal_o_menu):
    """Trampa 3 y 9 para una ventana principal o un menu: cada pagina viva detiene sus temporizadores ANTES de que todo se destruya; despues la receta completa."""
    menus = [principal_o_menu] if hasattr(principal_o_menu, "_paginas") else [m for m in getattr(principal_o_menu, "_tab_instancias", {}).values() if hasattr(m, "_paginas")]
    for menu in menus:
        for pagina in list(menu._paginas.values()):
            if not sip.isdeleted(pagina) and hasattr(pagina, "limpiar_recursos"):
                pagina.limpiar_recursos()
    cerrar(principal_o_menu)


def _menu_del_600(base_nueva):
    from ui.mainpages import Menuu
    menuu = Menuu("600", _Sesion(SESION))
    menuu._mostrar_pagina("mensual")
    return menuu, menuu._paginas["mensual"]


def _iniciar_con_otro_fisico(pagina, base_nueva):
    _sembrar_control_de_hoy(base_nueva, "Clinac 600")
    pagina.date_box.setDate(QDate.currentDate())
    pagina.iniciar.click()
    assert pagina.ref is not None


class TestCerrarControlEInicio:
    def test_cerrar_control_destruye_la_pagina_y_la_ventana(self, base_nueva, dialogos):
        menuu, pagina = _menu_del_600(base_nueva)
        try:
            _iniciar_con_otro_fisico(pagina, base_nueva)
            _de(pagina, "boton_analisis_placa").click()
            v = pagina.ventana_placa
            assert v.isVisible()
            menuu._cerrar_control()
            _procesar_borrados()
            assert dialogos.de("question"), "«Cerrar control» pregunta antes de cerrar"
            assert sip.isdeleted(pagina)
            assert sip.isdeleted(v)
            assert _ventanas_vivas() == []
        finally:
            _cerrar_principal(menuu)

    def test_inicio_oculta_la_ventana_aunque_la_pagina_siga_viva(self, base_nueva, dialogos):
        """`Menuu.entrada` -> `MainWindow.cerrar` hace `logout` y `close()`: la pagina NO se destruye (la ventana principal queda viva y oculta hasta el siguiente ingreso) y una ventana hija «a secas»
        quedaria a la vista con el `ref` y el usuario de la sesion cerrada. La de la placa se cierra con la ventana principal."""
        from ui.mainpages import MainWindow
        usuario = Usuario(username="f1", fullname=SESION, active=1, role="Físico Médico")
        principal = MainWindow(usuario)
        try:
            menuu = principal._tab_instancias[0]
            menuu._mostrar_pagina("mensual")
            pagina = menuu._paginas["mensual"]
            _iniciar_con_otro_fisico(pagina, base_nueva)
            _de(pagina, "boton_analisis_placa").click()
            v = pagina.ventana_placa
            assert v.isVisible() and principal.isVisible()
            menuu.back_button.click()                    # «Inicio»
            QApplication.processEvents()
            assert not principal.isVisible()
            assert not sip.isdeleted(pagina), "«Inicio» no destruye la pagina (este es el caso que la prueba cubre)"
            assert not sip.isdeleted(v)
            assert not v.isVisible(), "la ventana de la placa queda a la vista con el control y el usuario de la sesion cerrada"
        finally:
            _cerrar_principal(principal)

    def test_minimizar_la_ventana_principal_no_cierra_la_ventana_de_la_placa(self, base_nueva, dialogos):
        """Qt manda un `Hide` espontaneo a la ventana principal al minimizar (medido bajo offscreen: `logs/E2/minimizar_offscreen.log`): filtrar su `Hide` en vez de su `Close` cerraria la ventana
        de la placa cada vez que el fisico minimiza."""
        from ui.mainpages import MainWindow
        usuario = Usuario(username="f1", fullname=SESION, active=1, role="Físico Médico")
        principal = MainWindow(usuario)
        try:
            menuu = principal._tab_instancias[0]
            menuu._mostrar_pagina("mensual")
            pagina = menuu._paginas["mensual"]
            _iniciar_con_otro_fisico(pagina, base_nueva)
            _de(pagina, "boton_analisis_placa").click()
            v = pagina.ventana_placa
            assert v.isVisible()
            principal.showMinimized()
            QApplication.processEvents()
            assert principal.isMinimized()
            assert v.isVisible(), "minimizar la ventana principal cerro la de la placa"
            principal.showNormal()
            QApplication.processEvents()
            assert v.isVisible()
        finally:
            _cerrar_principal(principal)

    def test_el_recorrido_completo_cerrar_control_abrir_otra_ventana_e_inicio(self, base_nueva, dialogos, _excepciones_de_slots):
        """«Cerrar control», abrir el mensual nuevo, iniciar, abrir OTRA ventana e «Inicio»: la segunda queda oculta y no hay excepciones (el filtro de la ventana destruida no deja nada colgando en la
        ventana principal)."""
        from ui.mainpages import MainWindow
        usuario = Usuario(username="f1", fullname=SESION, active=1, role="Físico Médico")
        principal = MainWindow(usuario)
        try:
            menuu = principal._tab_instancias[0]
            menuu._mostrar_pagina("mensual")
            pagina = menuu._paginas["mensual"]
            _iniciar_con_otro_fisico(pagina, base_nueva)
            _de(pagina, "boton_analisis_placa").click()
            primera = pagina.ventana_placa
            menuu._cerrar_control()
            _procesar_borrados()
            assert sip.isdeleted(pagina) and sip.isdeleted(primera)
            menuu._mostrar_pagina("mensual")
            pagina2 = menuu._paginas["mensual"]
            assert pagina2 is not pagina
            pagina2.date_box.setDate(QDate.currentDate())
            pagina2.iniciar.click()
            _de(pagina2, "boton_analisis_placa").click()
            segunda = pagina2.ventana_placa
            assert segunda is not primera and segunda.isVisible()
            menuu.back_button.click()
            QApplication.processEvents()
            assert not segunda.isVisible()
            assert _excepciones_de_slots == []
        finally:
            _cerrar_principal(principal)


# ======================================================================================================================================= 7. la linea se vuelve a escribir

class TestLaLineaSeVuelveAEscribir:
    def test_guardar_con_la_ventana_abierta_no_cambia_la_linea_y_al_ocultarla_dice_n(self, paginas, placa, clics):
        """La ventana no emite ninguna senal al guardar: mientras esta abierta la linea sigue diciendo lo de antes; al ocultarse (cerrar) se vuelve a escribir con lo del registro."""
        from services import placa_mensual as svc
        pagina = paginas("600")
        antes = _de(pagina, "linea_analisis_placa").text()
        assert antes == TEXTO_NADA
        _de(pagina, "boton_analisis_placa").click()
        v = pagina.ventana_placa
        _sembrar_un_analisis_nuevo(pagina.ref, placa, clics, usuario="Fisico Tres")
        assert _de(pagina, "linea_analisis_placa").text() == antes
        v.close()
        registro = svc.leer(pagina.ref)
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_N.format(archivo="placa_sintetica.png", fecha=registro["fecha_registro"], usuario="Fisico Tres")

    def test_cada_vez_que_se_oculta_se_vuelve_a_escribir(self, paginas, placa, clics):
        pagina = paginas("600")
        _de(pagina, "boton_analisis_placa").click()
        v = pagina.ventana_placa
        v.close()
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_NADA
        _de(pagina, "boton_analisis_placa").click()
        _sembrar_un_analisis_nuevo(pagina.ref, placa, clics)
        v.hide()
        assert _de(pagina, "linea_analisis_placa").text().startswith("Análisis de la placa guardado: placa_sintetica.png, ")


# ======================================================================================================================================= 8. los fallos

class TestLosFallos:
    def test_la_ventana_que_no_se_construye_dice_el_error_y_la_pagina_sigue_viva(self, paginas, dialogos, monkeypatch, base_nueva):
        """E2-D8: un `critical` con el texto, la entrada en `error_log.txt`, la pagina viva, ninguna ventana guardada y 0 excepciones en los slots (la fixture autouse)."""
        dialogos.criticos_esperados = True
        mod = ventana_mod()

        class Rota:
            def __init__(self, *a, **k):
                raise RuntimeError("ventana rota a proposito")
        monkeypatch.setattr(mod, "VentanaPlacaMensual", Rota)
        pagina = paginas("600")
        _de(pagina, "boton_analisis_placa").click()
        criticos = dialogos.de("critical")
        assert len(criticos) == 1
        assert criticos[0]["titulo"] == BOTON
        assert criticos[0]["texto"] == "No se pudo abrir el análisis de la placa (RuntimeError: ventana rota a proposito)."
        assert not sip.isdeleted(pagina)
        assert getattr(pagina, "ventana_placa", None) is None
        log = _el_log(base_nueva)
        assert "E.2" in log and "ventana rota a proposito" in log

    def test_lo_que_falla_despues_de_construir_se_registra_y_no_sale_del_slot(self, paginas, dialogos, monkeypatch, base_nueva, _excepciones_de_slots):
        """Trampa 3: el manejador del clic envuelve TODO su cuerpo, no solo la construccion. Un `show()` que lanza se registra y el clic no propaga nada."""
        mod = ventana_mod()
        monkeypatch.setattr(mod.VentanaPlacaMensual, "show", lambda self: (_ for _ in ()).throw(RuntimeError("show roto a proposito")))
        pagina = paginas("600")
        _de(pagina, "boton_analisis_placa").click()
        assert _excepciones_de_slots == []
        assert "show roto a proposito" in _el_log(base_nueva)
        assert not sip.isdeleted(pagina)

    def test_el_estado_que_no_se_puede_leer_se_dice_y_el_visor_se_muestra(self, paginas, monkeypatch, base_nueva):
        """E2-D7: `svc.leer` que lanza -> la linea dice «No se pudo leer qué análisis tiene este control: Clase: mensaje», el visor queda visible (como hoy), el boton de la imagen guardada oculto y el detalle va
        a `error_log.txt`; el formulario se abre igual."""
        from services import placa_mensual as svc

        def boom(ref):
            raise RuntimeError("lectura rota a proposito")
        monkeypatch.setattr(svc, "leer", boom)
        pagina = paginas("600")
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_SIN_ESTADO.format(motivo="RuntimeError: lectura rota a proposito")
        assert not _visor(pagina).isHidden()
        assert pagina.boton_subir.isHidden()
        assert _de(pagina, "boton_imagen_guardada").isHidden()
        assert not _de(pagina, "boton_analisis_placa").isHidden()
        log = _el_log(base_nueva)
        assert "E.2" in log and "lectura rota a proposito" in log


# ======================================================================================================================================= 9. la compuerta por AST y por MRO

def _importar_toda_la_ui():
    importados, fallidos = [], {}
    for ruta in sorted((RAIZ / "ui").rglob("*.py")):
        nombre = ".".join(ruta.relative_to(RAIZ).with_suffix("").parts)
        if nombre.endswith("__init__"):
            continue
        try:
            importlib.import_module(nombre)
            importados.append(nombre)
        except BaseException as error:      # noqa: BLE001
            fallidos[nombre] = f"{type(error).__name__}: {error}"
    return importados, fallidos


def _subclases(clase):
    vistas, pendientes = set(), [clase]
    while pendientes:
        for s in pendientes.pop().__subclasses__():
            if s not in vistas:
                vistas.add(s)
                pendientes.append(s)
    return sorted(vistas, key=lambda c: (c.__module__, c.__qualname__))


def _resuelto(clase, nombre):
    for base in clase.__mro__:
        if nombre in base.__dict__:
            return base, base.__dict__[nombre]
    return None, None


def _analisis_de(llamada):
    """El valor de `analisis` de una llamada al cargador: palabra clave, primer posicional o, sin argumento, el valor por omision (`True`); lo que no es un literal cuenta como `True`."""
    for kw in llamada.keywords:
        if kw.arg == "analisis":
            return kw.value.value if isinstance(kw.value, ast.Constant) else True
    if llamada.args:
        return llamada.args[0].value if isinstance(llamada.args[0], ast.Constant) else True
    return True


def _nodo_de_la_funcion(funcion, arboles):
    """El `FunctionDef` de `funcion` en el AST de SU archivo, por la linea de su `def` o de su primer decorador (`inspect.getsource` + `dedent` falla en un metodo de `ui/`)."""
    archivo = inspect.getsourcefile(funcion)
    if archivo is None:
        return None, None
    if archivo not in arboles:
        arboles[archivo] = ast.parse(Path(archivo).read_text(encoding="utf-8"))
    primera = funcion.__code__.co_firstlineno
    for nodo in ast.walk(arboles[archivo]):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and nodo.name == funcion.__name__ and primera in [nodo.lineno] + [d.lineno for d in nodo.decorator_list]:
            return archivo, nodo
    return archivo, None


def _sitios_del_cargador(clase, cargador_compartido, arboles):
    """Cada llamada `self.imagenUpLoader(...)` de los metodos que `clase` RESUELVE y que llega al cargador compartido: (metodo, archivo, linea, analisis)."""
    _, cargador = _resuelto(clase, "imagenUpLoader")
    if cargador is not cargador_compartido:
        return []
    sitios = []
    for nombre in dir(clase):
        base, funcion = _resuelto(clase, nombre)
        funcion = getattr(funcion, "__wrapped__", funcion)
        if not inspect.isfunction(funcion):
            continue
        try:
            archivo, arbol = _nodo_de_la_funcion(funcion, arboles)
        except (OSError, TypeError, SyntaxError):
            continue
        if arbol is None:
            continue
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "imagenUpLoader" and isinstance(nodo.func.value, ast.Name)
                    and nodo.func.value.id == "self"):
                sitios.append((nombre, archivo, nodo.lineno, _analisis_de(nodo)))
    return sitios


def _clases_que_violan(clases, cargador_compartido, analisis_viejo):
    """Las clases con el cargador compartido en `analisis` verdadero cuyo `analizar_imagen` RESUELTO es el del 600 (el viejo)."""
    arboles, violan = {}, []
    for clase in clases:
        sitios = _sitios_del_cargador(clase, cargador_compartido, arboles)
        _, analizar = _resuelto(clase, "analizar_imagen")
        if any(analisis for *_, analisis in sitios) and analizar is analisis_viejo:
            violan.append(f"{clase.__module__}.{clase.__qualname__}")
    return violan


@pytest.fixture(scope="module")
def la_ui(app):
    importados, fallidos = _importar_toda_la_ui()
    from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
    from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
    clases = [c for c in _subclases(PruebaBasico) if c.__module__.startswith("ui.")]
    return SimpleNamespace(importados=importados, fallidos=fallidos, clases=clases, cargador=PruebaBasico.__dict__["imagenUpLoader"], viejo=PruebaMensual600.__dict__["analizar_imagen"],
                           PruebaBasico=PruebaBasico, PruebaMensual600=PruebaMensual600)


class TestNingunaPantallaLlegaAlAnalisisViejo:
    def test_ninguna_clase_con_el_cargador_en_analisis_verdadero_resuelve_el_analisis_viejo(self, la_ui):
        """Por AST y por MRO: el 600, el iX y (por heredar el metodo sin llamarlo) el mensual del Halcyon violaban en HEAD; con E.2, ninguna."""
        assert not la_ui.fallidos, la_ui.fallidos
        assert len(la_ui.importados) >= 25
        assert _clases_que_violan(la_ui.clases, la_ui.cargador, la_ui.viejo) == []

    def test_no_es_vacua_hay_al_menos_cuatro_sitios_del_cargador_compartido(self, la_ui):
        """Sin sitios el detector pasaria siempre: hoy `halcyon_anual.py`, `braquiterapia.py`, `seiscientos_mensual.py` y `equipos.py` construyen el cargador compartido."""
        arboles, archivos = {}, set()
        for clase in la_ui.clases:
            for _, archivo, _, _ in _sitios_del_cargador(clase, la_ui.cargador, arboles):
                archivos.add(Path(archivo).name)
        assert {"halcyon_anual.py", "braquiterapia.py", "seiscientos_mensual.py", "equipos.py"} <= archivos, archivos

    def test_el_detector_caza_una_intrusa_y_deja_pasar_la_que_no_analiza(self, la_ui, tmp_path):
        """Control del detector: una pantalla que hereda del 600 y construye el cargador sin argumento, o con `True` posicional, se caza; la de `analisis=False`, no. (El AST necesita el archivo.)"""
        archivo = tmp_path / "intrusas_e2.py"
        archivo.write_text(textwrap.dedent("""
            from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600

            class IntrusaConAnalisis(PruebaMensual600):
                def seccion(self):
                    return self.imagenUpLoader()

            class IntrusaPosicional(PruebaMensual600):
                def seccion(self):
                    return self.imagenUpLoader(True)

            class IntrusaPorVariable(PruebaMensual600):
                def seccion(self):
                    bandera = True
                    return self.imagenUpLoader(analisis=bandera)

            class IntrusaSinAnalisis(PruebaMensual600):
                def _configurar_elementos_adicionales(self):
                    return self.imagenUpLoader(analisis=False)
        """), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("intrusas_e2", archivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        try:
            violan = _clases_que_violan([modulo.IntrusaConAnalisis, modulo.IntrusaPosicional, modulo.IntrusaPorVariable, modulo.IntrusaSinAnalisis], la_ui.cargador, la_ui.viejo)
        finally:
            sys.modules.pop("intrusas_e2", None)
        assert sorted(v.split(".")[-1] for v in violan) == ["IntrusaConAnalisis", "IntrusaPorVariable", "IntrusaPosicional"]


# ======================================================================================================================================= 10. los manejadores envuelven todo su cuerpo en try

def _cuerpo_sin_docstring(funcion):
    cuerpo = list(funcion.body)
    if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant) and isinstance(cuerpo[0].value.value, str):
        cuerpo = cuerpo[1:]
    return cuerpo


def _solo_try(funcion):
    """True si TODO el cuerpo (sin el docstring) es un `try` con `except Exception`, salvo un `return` de un literal al final (el `return False` del filtro de eventos)."""
    cuerpo = _cuerpo_sin_docstring(funcion)
    if cuerpo and isinstance(cuerpo[-1], ast.Return) and (cuerpo[-1].value is None or isinstance(cuerpo[-1].value, ast.Constant)):
        cuerpo = cuerpo[:-1]
    return len(cuerpo) == 1 and isinstance(cuerpo[0], ast.Try) and any(h.type is not None and getattr(h.type, "id", None) == "Exception" for h in cuerpo[0].handlers)


class TestLosManejadoresEstanProtegidos:
    def _funciones(self):
        arbol = ast.parse(IDC_PY.read_text(encoding="utf-8"))
        funciones = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}
        for clase in [n for n in arbol.body if isinstance(n, ast.ClassDef)]:
            for n in clase.body:
                if isinstance(n, ast.FunctionDef):
                    funciones[f"{clase.name}.{n.name}"] = n
        return funciones

    @pytest.mark.parametrize("nombre", ["abrir_analisis_placa", "analizar_imagen_guardada", "_Vigilante.eventFilter"])
    def test_el_manejador_envuelve_todo_su_cuerpo_en_try(self, nombre):
        """Como la prueba de E.1 `test_cada_manejador...`: un manejador de un clic o de un evento que deja escapar una excepcion aborta el proceso (Trampa 3). Por AST."""
        funciones = self._funciones()
        assert nombre in funciones, sorted(funciones)
        assert _solo_try(funciones[nombre]), f"{nombre} no envuelve todo su cuerpo en un try con except Exception"

    def test_el_detector_de_manejadores_discrimina(self):
        """Control: una funcion con una sentencia fuera del `try` NO pasa; una con todo dentro, si."""
        mal = ast.parse("def f(x):\n    y = 1\n    try:\n        g()\n    except Exception:\n        pass\n").body[0]
        bien = ast.parse("def f(x):\n    '''doc'''\n    try:\n        g()\n    except Exception:\n        pass\n    return False\n").body[0]
        assert not _solo_try(mal) and _solo_try(bien)

    def test_el_vigilante_no_deja_escapar_una_excepcion_al_ocultarse_la_ventana(self, paginas, monkeypatch, base_nueva, _excepciones_de_slots):
        """Por conducta: si volver a escribir la linea lanza (aqui, `refrescar_la_linea` entera), ocultar la ventana no propaga nada al bucle de eventos y el detalle queda en el registro. Con el
        `eventFilter` sin su `try` la excepcion llega a `sys.excepthook` y la fixture autouse la ve."""
        m = idc()
        pagina = paginas("600")
        _de(pagina, "boton_analisis_placa").click()
        v = pagina.ventana_placa
        monkeypatch.setattr(m, "refrescar_la_linea", lambda pagina: (_ for _ in ()).throw(RuntimeError("refrescar roto a proposito")))
        v.close()
        QApplication.processEvents()
        assert _excepciones_de_slots == []
        assert "refrescar roto a proposito" in _el_log(base_nueva)

    def test_el_vigilante_de_la_ventana_principal_no_deja_escapar_una_excepcion_al_cerrarse(self, base_nueva, dialogos, monkeypatch, _excepciones_de_slots):
        """El otro lado del filtro: el `Close` de la ventana principal cierra la de la placa; si cerrarla lanza, no sale del evento."""
        from ui.mainpages import MainWindow
        usuario = Usuario(username="f1", fullname=SESION, active=1, role="Físico Médico")
        principal = MainWindow(usuario)
        colector = sys.excepthook                          # el de la fixture autouse `_excepciones_de_slots`
        try:
            menuu = principal._tab_instancias[0]
            menuu._mostrar_pagina("mensual")
            pagina = menuu._paginas["mensual"]
            _iniciar_con_otro_fisico(pagina, base_nueva)
            _de(pagina, "boton_analisis_placa").click()
            v = pagina.ventana_placa
            with monkeypatch.context() as solo_este:      # E2-REV-P5: `monkeypatch.undo()` deshacia TAMBIEN los parches de las fixtures (BD, registro de errores, excepthook) antes de cerrar la principal
                solo_este.setattr(type(v), "close", lambda self: (_ for _ in ()).throw(RuntimeError("cerrar roto a proposito")))
                principal.close()
                QApplication.processEvents()
                assert _excepciones_de_slots == []
                assert "cerrar roto a proposito" in _el_log(base_nueva)
            assert conection_mod.ruta_base_datos() == base_nueva, "se deshizo la redireccion de la BD de la fixture"
            assert os.environ.get("RADQA_ERROR_LOG") == str(Path(base_nueva).parent / "error_log.txt"), "se deshizo el registro de errores de la fixture"
            assert sys.excepthook is colector, "se deshizo el recolector de excepciones de slots de la fixture"
        finally:
            _cerrar_principal(principal)


# ======================================================================================================================================= 11. DA-89: reparar los controles viejos con su imagen guardada

class TestElBotonDeLaImagenGuardada:
    @pytest.mark.parametrize("ref,visible", [(40, True), (1, True), (6, True), (38, True), (13, False), (16, False), (22, False), (14, False)])
    def test_visible_solo_si_el_control_tiene_imagen(self, produccion, ref, visible):
        pagina = produccion(ref)
        assert _de(pagina, "boton_imagen_guardada").isHidden() is (not visible)
        assert _de(pagina, "boton_imagen_guardada").text() == BOTON_IMAGEN
        assert not _de(pagina, "boton_analisis_placa").isHidden()

    def test_tambien_se_ofrece_si_el_control_ya_tiene_un_analisis_nuevo(self, produccion, placa, clics):
        """E2-DA89-D2: con N el boton sigue (volver a analizar la imagen guardada la carga y descarta el analisis abierto, igual que elegir un archivo; guardar crea la generacion nueva)."""
        _sembrar_un_analisis_nuevo(40, placa, clics)
        assert not _de(produccion(40), "boton_imagen_guardada").isHidden()


# V, I y N del control (E2-REV-P1..P4, P3 y P4): (ref de la copia de la produccion del 06-10, con un analisis nuevo sembrado, tiene imagen vieja). El 40 tiene V e I, el 1 solo I, el 13 solo V, el 22 una fila de
# `preguntas` sin imagen y el 14 NINGUNA fila de `preguntas` (E2-R2P-4: el unico caso sin esa fila con N).
CASOS_DEL_VISOR = [(40, False, True), (1, False, True), (40, True, True), (1, True, True), (13, False, False), (13, True, False), (22, True, False), (22, False, False), (14, True, False)]


class TestElVisorYLosBotonesSiguenALaImagen:
    @pytest.mark.parametrize("ref,con_n,hay_imagen", CASOS_DEL_VISOR)
    def test_el_visor_y_los_dos_botones_dependen_solo_de_la_imagen(self, produccion, placa, clics, ref, con_n, hay_imagen):
        """Plan (OBJETIVO 3, E2-D9, E2-DA89-D2): el visor de la imagen vieja y el boton «Analizar la imagen guardada» se muestran EXACTAMENTE cuando el control tiene imagen (I), sin importar si tiene
        analisis viejo (V) o nuevo (N); «Seleccionar Imagen» queda oculto SIEMPRE, tambien con imagen; «Analisis de la placa» siempre se ve. Los 8 casos de V, I y N que existen en la copia de la
        produccion (el oraculo de I, sqlite3 a mano), y la linea dice lo que toca en cada uno."""
        from services import placa_mensual as svc
        if con_n:
            _sembrar_un_analisis_nuevo(ref, placa, clics)
        v, i = _v_i_a_mano(produccion.ruta, ref)
        assert bool(i) is hay_imagen, "el oraculo de la tabla de casos"
        pagina = produccion(ref)
        seccion = _seccion(pagina)
        assert _visor(pagina).isVisibleTo(seccion) is hay_imagen, "el visor de la imagen vieja sigue a la imagen y a nada mas"
        assert _de(pagina, "boton_imagen_guardada").isVisibleTo(seccion) is hay_imagen, "«Analizar la imagen guardada» sigue a la imagen y a nada mas"
        assert pagina.boton_subir.isHidden(), "«Seleccionar Imagen» queda oculto aunque el control tenga imagen"
        assert _de(pagina, "boton_analisis_placa").isVisibleTo(seccion)
        n = {"archivo": "placa_sintetica.png", "fecha": svc.leer(ref)["fecha_registro"], "usuario": "Fisico Uno"} if con_n else None
        assert _de(pagina, "linea_analisis_placa").text() == la_linea(v, i, n)


    @pytest.mark.parametrize("como", ["el_clic_en_analizar_la_imagen_guardada", "ocultar_la_ventana_del_analisis"])
    def test_si_la_imagen_se_anula_con_el_formulario_abierto_el_visor_se_oculta_igual_que_el_boton(self, produccion, dialogos, como):
        """E2-R2P-3: el visor se decide al construir la seccion y de nuevo cada vez que se vuelve a escribir la linea (el clic de «Analizar la imagen guardada» que encuentra el control sin imagen, o la
        ventana del analisis que se oculta): con la imagen anulada entre medias, el visor deja de verse con el boton y la linea, y no queda a la vista con el dibujo viejo."""
        pagina = produccion(40)
        seccion = _seccion(pagina)
        assert _visor(pagina).isVisibleTo(seccion) and _de(pagina, "boton_imagen_guardada").isVisibleTo(seccion)
        if como == "ocultar_la_ventana_del_analisis":
            _de(pagina, "boton_analisis_placa").click()
            v = pagina.ventana_placa
        _sql(produccion.ruta, "UPDATE preguntas SET activo = 0 WHERE ref = 40")
        if como == "ocultar_la_ventana_del_analisis":
            v.close()
            QApplication.processEvents()
        else:
            _de(pagina, "boton_imagen_guardada").click()
        assert not _visor(pagina).isVisibleTo(seccion), "el visor de la imagen vieja sigue a la vista con la imagen anulada"
        assert not _de(pagina, "boton_imagen_guardada").isVisibleTo(seccion)
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_V_SIN_IMAGEN

    def test_si_la_imagen_aparece_despues_se_ofrece_el_boton_pero_el_visor_no_se_muestra_vacio(self, produccion, dialogos):
        """El visor solo se OCULTA despues de construido: su dibujo se pinta una sola vez (IM4), asi que un control que gana una imagen con el formulario abierto ofrece el boton y la linea lo dice, pero el
        visor sigue oculto (se veria vacio) hasta que se vuelva a abrir el control."""
        pagina = produccion(22)
        seccion = _seccion(pagina)
        assert not _visor(pagina).isVisibleTo(seccion) and not _de(pagina, "boton_imagen_guardada").isVisibleTo(seccion)
        _sql(produccion.ruta, "UPDATE preguntas SET imagen = ? WHERE ref = 22 AND activo = 1", (_png_pequeno(),))
        _de(pagina, "boton_analisis_placa").click()
        pagina.ventana_placa.close()
        QApplication.processEvents()
        assert _de(pagina, "boton_imagen_guardada").isVisibleTo(seccion)
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_I
        assert not _visor(pagina).isVisibleTo(seccion), "el visor aparecio vacio: su dibujo solo se pinta al construir la pagina"


class TestAnalizarLaImagenGuardada:
    def test_el_clic_carga_los_bytes_de_la_base_con_su_nombre_y_el_estado_imagen(self, produccion, dialogos):
        """El clic lee `imagen_vigente(ref)` EN EL CLIC y la carga en la ventana: `_bytes` es el BLOB de la fila vigente de `preguntas`, el nombre «imagen guardada del control 40», estado «imagen»."""
        from data.ManejoDatos.load import imagen_vigente
        pagina = produccion(40)
        blob = bytes(imagen_vigente(40))
        _de(pagina, "boton_imagen_guardada").click()
        v = pagina.ventana_placa
        assert v.estado == "imagen"
        assert bytes(v._bytes) == blob
        assert v._nombre == NOMBRE_IMAGEN_GUARDADA.format(ref=40) == "imagen guardada del control 40"
        assert v.nombre_archivo.text() == "imagen guardada del control 40"
        assert v.ref == 40 and v.usuario == "Javier Castillo"
        assert v._con_milimetros                                       # el 40 esta a 600 ppp
        assert "INTERNO" not in v.etiqueta_imagen.text()
        assert [c["tipo"] for c in dialogos.llamadas] == ["information"]       # solo el «Control existente» de «Iniciar»

    def test_los_bytes_se_leen_en_el_clic_y_no_al_construir_la_seccion(self, produccion, placa):
        """El fisico pudo cambiar la imagen entre la construccion de la pagina y el clic: la ventana recibe la de AHORA."""
        from data.ManejoDatos.load import imagen_vigente
        pagina = produccion(40)
        nueva = placa.datos
        _sql(produccion.ruta, "UPDATE preguntas SET imagen = ? WHERE ref = 40 AND activo = 1", (nueva,))
        assert bytes(imagen_vigente(40)) == nueva
        _de(pagina, "boton_imagen_guardada").click()
        assert bytes(pagina.ventana_placa._bytes) == nueva

    def test_con_los_clics_del_40_se_analiza_se_guarda_y_la_linea_pasa_a_n(self, produccion, dialogos):
        """El camino completo del fisico: reparar un control viejo. Con los clics reales de la placa del 40 (`CLICS_REALES['PLACA_REF40']`) la ventana analiza y «Guardar» deja el analisis NUEVO de ese
        control con esos bytes (D.1); al ocultar la ventana la linea pasa de V a N."""
        from data.ManejoDatos.load import imagen_vigente
        from services import placa_mensual as svc
        pagina = produccion(40)
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_V
        blob = bytes(imagen_vigente(40))
        _de(pagina, "boton_imagen_guardada").click()
        v = pagina.ventana_placa
        v.resize(1380, 880)
        marcar(v, CLICS_REALES["PLACA_REF40"])
        assert v.estado == "analizada", (v.estado, dialogos.llamadas[-2:])
        v.boton_guardar.click()
        assert v.estado == "registro"
        registro = svc.leer(40)
        assert registro is not None
        assert bytes(registro["imagen"]) == blob
        assert registro["nombre_archivo"] == "imagen guardada del control 40"
        assert registro["usuario"] == "Javier Castillo"
        assert registro["capa"] == "G"
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_V                      # mientras la ventana esta abierta, la linea no se entera
        v.close()
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_N.format(archivo="imagen guardada del control 40", fecha=registro["fecha_registro"], usuario="Javier Castillo")

    def test_a_300_ppp_la_ventana_dice_la_resolucion_no_da_milimetros_y_no_guarda(self, produccion, dialogos, _excepciones_de_slots):
        """P25 (por omision no): el 38 esta a 300 ppp. La ventana lo dice, no da milimetros (`escala_mm` es None) y, con cinco puntos marcados DENTRO de la imagen, analiza sin medir y no deja guardar;
        ningun cuadro de error ni excepcion, y no queda ningun analisis nuevo. E.2 no lo cambia: lo prueba."""
        from services import placa_mensual as svc
        pagina = produccion(38)
        _de(pagina, "boton_imagen_guardada").click()
        v = pagina.ventana_placa
        assert v.estado == "imagen"
        assert not v._con_milimetros
        assert "sin esa escala no hay milímetros ni medidas" in v.etiqueta_imagen.text()
        assert not v.boton_guardar.isEnabled()
        v.resize(1380, 880)
        alto, ancho = v._forma
        marcar(v, [(0.08 * ancho, 0.08 * alto), (0.92 * ancho, 0.08 * alto), (0.92 * ancho, 0.92 * alto), (0.08 * ancho, 0.92 * alto), (0.5 * ancho, 0.5 * alto)])
        assert len(v._marcas) == 5 and v.estado == "analizada"
        assert not v.boton_guardar.isEnabled(), "a 300 ppp no hay milimetros: el analisis no se puede guardar (D.1b)"
        assert svc.leer(38) is None
        assert not dialogos.de("critical")
        assert _excepciones_de_slots == []

    def test_la_imagen_borrada_entre_la_construccion_y_el_clic_avisa_y_no_abre_nada(self, produccion, dialogos):
        pagina = produccion(40)
        assert not _de(pagina, "boton_imagen_guardada").isHidden()
        _sql(produccion.ruta, "UPDATE preguntas SET activo = 0 WHERE ref = 40")
        antes = len(dialogos.llamadas)
        _de(pagina, "boton_imagen_guardada").click()
        nuevos = dialogos.llamadas[antes:]
        assert [(c["tipo"], c["titulo"], c["texto"]) for c in nuevos] == [("warning", BOTON_IMAGEN, "El control ya no tiene imagen guardada.")]
        assert getattr(pagina, "ventana_placa", None) is None
        assert _ventanas_vivas() == []
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_V_SIN_IMAGEN                 # la linea se refresco: ya no hay imagen
        assert _de(pagina, "boton_imagen_guardada").isHidden()
        assert not _visor(pagina).isVisibleTo(_seccion(pagina)), "el visor de la imagen vieja sigue a la vista con la imagen anulada (E2-R2P-3)"

    def test_una_imagen_guardada_que_no_se_lee_avisa_con_el_titulo_del_boton_y_la_ventana_queda_vacia(self, produccion, dialogos, _excepciones_de_slots):
        """Lo guardado en `preguntas.imagen` puede ser un PDF (el visor viejo ya lo dice: «no se puede previsualizar»): la ventana se abre, `cargar_imagen` avisa con el titulo del boton que el fisico
        pulso («Analizar la imagen guardada», no el de «Seleccionar imagen») y el motivo, y queda vacia; ninguna excepcion ni `critical`."""
        _sql(produccion.ruta, "UPDATE preguntas SET imagen = ? WHERE ref = 40 AND activo = 1", (b"%PDF-1.4 esto no es una imagen que la herramienta sepa leer",))
        pagina = produccion(40)
        antes = len(dialogos.llamadas)
        _de(pagina, "boton_imagen_guardada").click()
        v = pagina.ventana_placa
        avisos = dialogos.llamadas[antes:]
        assert [(a["tipo"], a["titulo"]) for a in avisos] == [("warning", BOTON_IMAGEN)], avisos
        assert str(avisos[0]["texto"]).startswith("No se pudo leer la imagen: ")
        assert v.estado == "vacia"
        assert not v._bytes
        assert not dialogos.de("critical")
        assert _excepciones_de_slots == []

    def test_si_leer_la_imagen_guardada_falla_en_el_clic_se_avisa_se_registra_y_no_sale_del_slot(self, produccion, dialogos, monkeypatch, _excepciones_de_slots):
        """E2-PROD-1 y E2-R2P-1: `imagen_vigente` que lanza en el clic (un `disk I/O error` sobre la base compartida) no puede dejar al fisico pulsando sin que pase nada visible: un solo `critical` con el
        texto de «no se pudo cargar la imagen guardada» y el motivo, la entrada en `error_log.txt`, ninguna ventana y ninguna excepcion en el slot (Trampa 3); y el manejador, llamado directo, contesta None."""
        import sqlite3
        dialogos.criticos_esperados = True
        pagina = produccion(40)
        assert _de(pagina, "linea_analisis_placa").text() == TEXTO_V

        def falla(ref):
            raise sqlite3.OperationalError("disk I/O error")
        monkeypatch.setattr(idc(), "imagen_vigente", falla)
        antes = len(dialogos.llamadas)
        _de(pagina, "boton_imagen_guardada").click()
        nuevos = dialogos.llamadas[antes:]
        assert [(c["tipo"], c["titulo"], c["texto"]) for c in nuevos] == [("critical", BOTON_IMAGEN, "No se pudo cargar la imagen guardada (OperationalError: disk I/O error).")], nuevos
        assert _excepciones_de_slots == []
        assert getattr(pagina, "ventana_placa", None) is None and _ventanas_vivas() == []
        log = _el_log(produccion.ruta)
        assert "E.2: analizar la imagen guardada" in log and "disk I/O error" in log
        assert idc().analizar_imagen_guardada(pagina) is None                  # llamado directo: ni sale la excepcion ni devuelve una ventana

    def test_si_el_aviso_de_que_no_se_pudo_cargar_falla_tampoco_sale_del_slot(self, produccion, dialogos, monkeypatch, _excepciones_de_slots):
        """El aviso se da desde un `except`: si el cuadro mismo lanza, el error se registra y el clic no propaga nada (Trampa 3). Con el aviso sin su `try` la excepcion llega al recolector de la fixture."""
        import sqlite3
        pagina = produccion(40)

        def falla(ref):
            raise sqlite3.OperationalError("disk I/O error")
        monkeypatch.setattr(idc(), "imagen_vigente", falla)
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("aviso roto a proposito"))))
        _de(pagina, "boton_imagen_guardada").click()
        assert _excepciones_de_slots == []
        log = _el_log(produccion.ruta)
        assert "disk I/O error" in log and "aviso roto a proposito" in log
        assert not sip.isdeleted(pagina)

    def test_con_la_ventana_abierta_sobre_un_analisis_guardado_cargar_la_imagen_lo_descarta(self, produccion, placa, clics, dialogos):
        """Como seleccionar un archivo (`_instalar_imagen`): el analisis abierto, las marcas y el registro se descartan; la ventana queda en «imagen» con los bytes de la base."""
        from data.ManejoDatos.load import imagen_vigente
        _sembrar_un_analisis_nuevo(40, placa, clics)
        pagina = produccion(40)
        _de(pagina, "boton_analisis_placa").click()
        v = pagina.ventana_placa
        assert v.estado == "registro" and v._registro is not None
        _de(pagina, "boton_imagen_guardada").click()
        assert pagina.ventana_placa is v
        assert v.estado == "imagen"
        assert v._registro is None and v._resultado is None and v._marcas == []
        assert bytes(v._bytes) == bytes(imagen_vigente(40))
        assert v._nombre == "imagen guardada del control 40"

    def test_con_la_ventana_minimizada_el_clic_la_trae_al_frente_y_el_descarte_se_ve(self, produccion, dialogos):
        """E2-REV-PROD-1: cargar la imagen guardada descarta las marcas abiertas (E2-DA89-D2). Con la ventana minimizada ese descarte ocurria donde el fisico no lo ve: el clic la trae al frente."""
        pagina = produccion(40)
        _de(pagina, "boton_imagen_guardada").click()
        v = pagina.ventana_placa
        marcar(v, CLICS_REALES["PLACA_REF40"][:3])
        assert len(v.marcas) == 3
        v.showMinimized()
        QApplication.processEvents()
        assert v.isMinimized()
        _de(pagina, "boton_imagen_guardada").click()
        QApplication.processEvents()
        assert pagina.ventana_placa is v
        assert v.isVisible() and not v.isMinimized(), "las marcas se descartaron en una ventana que sigue minimizada"
        assert v.estado == "imagen" and len(v.marcas) == 0

    def test_si_la_ventana_no_se_construye_no_se_carga_nada_y_el_aviso_es_el_de_la_construccion(self, produccion, dialogos, monkeypatch):
        dialogos.criticos_esperados = True

        class Rota:
            def __init__(self, *a, **k):
                raise RuntimeError("ventana rota a proposito")
        monkeypatch.setattr(ventana_mod(), "VentanaPlacaMensual", Rota)
        pagina = produccion(40)
        _de(pagina, "boton_imagen_guardada").click()
        assert [c["tipo"] for c in dialogos.llamadas[1:]] == ["critical"]
        assert getattr(pagina, "ventana_placa", None) is None

    def test_si_cargar_la_imagen_falla_por_un_error_inesperado_se_registra_y_se_avisa(self, produccion, dialogos, monkeypatch):
        """E2-DA89-D6: `cargar_imagen` ya contesta `False` ante lo que espera (el archivo no se lee). Un error INESPERADO se registra y se avisa con un cuadro, y no sale del slot."""
        dialogos.criticos_esperados = True
        monkeypatch.setattr(ventana_mod().VentanaPlacaMensual, "cargar_imagen", lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("carga rota a proposito")))
        pagina = produccion(40)
        _de(pagina, "boton_imagen_guardada").click()
        criticos = dialogos.de("critical")
        assert len(criticos) == 1
        assert criticos[0]["titulo"] == BOTON_IMAGEN
        assert criticos[0]["texto"] == "No se pudo cargar la imagen guardada (RuntimeError: carga rota a proposito)."
        assert "carga rota a proposito" in _el_log(produccion.ruta)

    def test_abrir_analisis_placa_devuelve_la_ventana(self, paginas):
        """Quien llama (el boton de la imagen guardada) necesita la ventana: la que se abre y, en el segundo clic, la misma."""
        m = idc()
        pagina = paginas("600")
        v = m.abrir_analisis_placa(pagina)
        assert v is pagina.ventana_placa and v is not None
        assert m.abrir_analisis_placa(pagina) is v


class TestCargarImagenEsElMismoCaminoQueSeleccionarImagen:
    def test_misma_huella_con_el_mismo_archivo(self, fabrica_de_ventanas, dialogos, archivo_placa_e2, placa):
        """`cargar_imagen(datos, nombre)` y «Seleccionar imagen» con el mismo archivo dejan la MISMA huella de la ventana (todo lo observable)."""
        ref = fabrica_de_ventanas.control()
        por_archivo = fabrica_de_ventanas(ref)
        cargar(por_archivo, dialogos, archivo_placa_e2)
        por_metodo = fabrica_de_ventanas(ref)
        assert por_metodo.cargar_imagen(placa.datos, os.path.basename(archivo_placa_e2)) is True
        assert huella(por_archivo) == huella(por_metodo)

    def test_el_titulo_solo_cambia_el_aviso(self, fabrica_de_ventanas, dialogos):
        """Una imagen que no se lee: `False`, UN `warning` con el titulo que se pidio («Seleccionar imagen» por omision) y el mismo texto «No se pudo leer la imagen: ...»; la ventana queda como estaba."""
        v = fabrica_de_ventanas(fabrica_de_ventanas.control())
        antes = huella(v)
        assert v.cargar_imagen(b"esto no es una imagen", "x.png") is False
        assert v.cargar_imagen(b"esto no es una imagen", "x.png", "Otro titulo") is False
        avisos = dialogos.de("warning")
        assert [a["titulo"] for a in avisos] == ["Seleccionar imagen", "Otro titulo"]
        assert all(str(a["texto"]).startswith("No se pudo leer la imagen: ") for a in avisos)
        assert huella(v) == antes

    def test_la_carga_es_atomica_si_el_dibujo_de_la_imagen_falla_la_ventana_queda_como_estaba(self, fabrica_de_ventanas, dialogos, monkeypatch, placa):
        """La carga se lee y se interpreta TODA (`leer_pelicula` y `imagen_rgb`) antes de tocar la ventana: si el segundo paso falla con un `ValueError`, avisa, devuelve False y la huella no cambia."""
        from _e1_ayudas import dibujo_mod
        v = fabrica_de_ventanas(fabrica_de_ventanas.control())
        antes = huella(v)
        monkeypatch.setattr(dibujo_mod(), "imagen_rgb", lambda pelicula: (_ for _ in ()).throw(ValueError("rgb roto a proposito")))
        assert v.cargar_imagen(placa.datos, "placa.png") is False
        assert [(a["titulo"], a["texto"]) for a in dialogos.de("warning")] == [("Seleccionar imagen", "No se pudo leer la imagen: rgb roto a proposito")]
        assert huella(v) == antes

    def test_seleccionar_imagen_conserva_su_dialogo_y_su_aviso_ante_un_archivo_que_no_se_lee(self, fabrica_de_ventanas, dialogos, tmp_path):
        """El camino por archivo: un archivo que existe pero no es una imagen -> el aviso de siempre y nada cambia; uno que no existe -> el mismo aviso."""
        v = fabrica_de_ventanas(fabrica_de_ventanas.control())
        antes = huella(v)
        malo = tmp_path / "malo.png"
        malo.write_bytes(b"no soy una imagen")
        cargar(v, dialogos, str(malo))
        cargar(v, dialogos, str(tmp_path / "no_existe.png"))
        avisos = dialogos.de("warning")
        assert len(avisos) == 2 and all(a["titulo"] == "Seleccionar imagen" and str(a["texto"]).startswith("No se pudo leer la imagen: ") for a in avisos)
        assert huella(v) == antes

    def test_seleccionar_imagen_termina_en_cargar_imagen_por_ast(self):
        """Una sola forma de cargar una imagen en la ventana, venga de un archivo o de la base: `_al_seleccionar_imagen` delega en `cargar_imagen` y ya no llama a `leer_pelicula` ni a `_instalar_imagen`."""
        fuente = (RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "placa_mensual.py").read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        clase = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "VentanaPlacaMensual")
        metodos = {n.name: n for n in clase.body if isinstance(n, ast.FunctionDef)}
        seleccionar = ast.get_source_segment(fuente, metodos["_al_seleccionar_imagen"])
        assert "self.cargar_imagen(" in seleccionar
        assert "leer_pelicula" not in seleccionar and "_instalar_imagen" not in seleccionar
        cargar_ = ast.get_source_segment(fuente, metodos["cargar_imagen"])
        assert "leer_pelicula" in cargar_ and "imagen_rgb" in cargar_ and "self._instalar_imagen(" in cargar_
        assert [a.arg for a in metodos["cargar_imagen"].args.args] == ["self", "datos", "nombre", "titulo"]
        assert [getattr(d, "value", None) for d in metodos["cargar_imagen"].args.defaults] == ["Seleccionar imagen"]


@pytest.fixture
def fabrica_de_ventanas(app, bd, dialogos):
    """Ventanas de E.1 sueltas (sin pagina) sobre una BD temporal de D.1: `fabrica(ref)` construye una, `fabrica.control()` siembra un control."""
    from test_d1_guardado_placa_mensual import _control
    creadas = []

    def fabrica(ref):
        v = ventana_mod().VentanaPlacaMensual(ref, "Clinac de prueba", "Fisico de prueba")
        v.resize(1380, 880)
        creadas.append(v)
        return v
    fabrica.control = lambda: _control(bd)
    yield fabrica
    for v in creadas:
        cerrar(v)


@pytest.fixture
def archivo_placa_e2(tmp_path, placa):
    ruta = tmp_path / "placa.png"
    ruta.write_bytes(placa.datos)
    return str(ruta)
