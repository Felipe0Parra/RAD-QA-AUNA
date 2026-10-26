"""CC.1 (PLAN_ANALISIS_PELICULAS_08-10.md, H13): en el cargador de imagenes compartido, un clic en «Aceptar» analiza UNA sola vez, tras 1, 2 y 3 selecciones.

CAUSA (medida el 09-10 y vuelta a medir el 18-10). `PruebaBasico.subirlisto` (PruebasDiarias.py) crea «Seleccionar otra Imagen» y conecta su `clicked` DIRECTO a
`subir_imagen`; Qt le entrega `checked=False` como `analisis`, y por eso las selecciones segunda y tercera NO anaden otra conexion de «Aceptar» a `analizar_imagen`
(solo una `lambda` de `print`). El analisis corre una vez por «Aceptar»: es correcto POR ACCIDENTE. Quien «arreglara» ese parametro haria que corriera dos veces,
tres, N sin que nada lo viera. Esta prueba lo fija SIN tocar el codigo compartido (`PruebasDiarias.py` es zona roja).

QUE FIJA (todo por los clics que da el fisico, con el dialogo de archivo simulado y `analizar_imagen` espiado en la CLASE antes de construir la pagina):
  - el diario de braquiterapia (`PruebaDiariaBraq`, pagina real) y la subclase minima de `PruebaBasico` cableada como el mensual del 600 (`imagenUpLoader()` +
    `boton_aceptar.clicked -> subirlisto`, sin base de datos: el experimento de H13 hecho prueba, que fija el MECANISMO compartido), cada una con:
      * 1, 2 y 3 ciclos seleccionar-y-aceptar (la primera seleccion por «Seleccionar Imagen» y las siguientes por «Seleccionar otra Imagen»): cada clic en «Aceptar»
        llama a `analizar_imagen` EXACTAMENTE una vez (`== 1`, no `<= 1` ni `>= 1`) y el total sube de uno en uno;
      * 2 y 3 re-selecciones seguidas sin aceptar entre ellas: el siguiente «Aceptar» sigue llamando una sola vez;
      * cancelar el dialogo de archivo no cuenta como seleccion (ni anade una conexion);
      * en cada seleccion el dialogo se abrio una vez, la imagen elegida paso de verdad por `subir_imagen` (`imagen_path`) y elegir NO analiza (solo «Aceptar» analiza).
  - el anual del Halcyon (`PruebaAnualHalcyon`, pagina real tras «Iniciar»): como `subirlisto` no esta cableado a «Aceptar» en esa pagina, NO existe «Seleccionar otra Imagen»
    y «Seleccionar Imagen» queda oculto tras la primera seleccion: el unico camino de la interfaz a una segunda seleccion no existe. Lo que SI existe y se fija: tras la
    unica seleccion, cada clic en «Aceptar» llama a `analizar_imagen` exactamente una vez (el total sube de uno en uno), cancelar el dialogo no cuenta, y que no haya un
    camino a una segunda seleccion (si alguien lo anade, la prueba lo dice y pide cubrirlo con los casos de 2 y 3 selecciones). El OBJETIVO del plan pedia 1, 2 y 3 selecciones tambien en el anual
    (la primera por «Seleccionar Imagen» y las siguientes por «Seleccionar otra Imagen»): esa premisa NO se cumple en la pagina real y el bloque CC.1 del plan la corrige (hallazgo CC1-R1-01).
  - la RAMA SIN ANALISIS del cargador, la que usa Equipos (`imagenUpLoader(analisis=False)`, ui/paginasGuia/equipos.py:422; su «Aceptar» cierra el visor del certificado y no analiza): sobre dos
    paginas de esa forma (la subclase minima con `analizar_imagen` espiado y una `PruebaBasico` SIN `analizar_imagen`, como la clase `Config` de Equipos), tras elegir una imagen cada clic en «Aceptar»
    llama a `analizar_imagen` CERO veces y ningun slot de Qt lanza (sin el metodo, cualquier intento de analizar es un `AttributeError` dentro del slot). Es el otro lado del contrato: la bandera
    `analisis` decide si «Aceptar» analiza. (Ronda 1 del corrector, CC1-R1-03: la mutacion «`imagenUpLoader` ignora `analisis=False`» sobrevivia a las 19 pruebas de arriba.)

LO QUE NO FIJA, DECLARADO (medido el 18-10 y no tocado): en el diario de braquiterapia, «Cancelar» y cambiar de dia llaman a `resetear_imagen_ui`, que vuelve a mostrar
«Seleccionar Imagen» SIN desconectar el `analizar_imagen` de la seleccion anterior; una nueva seleccion por ese boton (`analisis=True`) anade otra conexion y el siguiente
«Aceptar» analiza DOS veces (medido: +2 despues de «Cancelar» y +2 despues de cambiar de dia; `logs/CC1/medicion_cambio_de_dia.log` del anexo del plan). No es el camino de este
archivo («Seleccionar otra Imagen»), no se arregla aqui (zona roja) y NO se fija: una prueba que lo diera por bueno consagraria un defecto. Queda como deuda para su propia tarea.
Tampoco se prueban el mensual del 600 ni el del iX (`G.1` retira de ellos el analisis viejo). De Equipos no se construye su pantalla real (el visor del certificado, con base de datos y dialogo
modal): solo la RAMA del cargador que usa, sobre paginas de su misma forma (ver arriba).

Contexto de los hechos de cableado (leidos en el codigo y medidos el 18-10): `imagenUpLoader(analisis)` conecta `boton_subir.clicked` a `subir_imagen(analisis=analisis)`;
`subir_imagen` oculta «Seleccionar Imagen», muestra «Aceptar» y, con `analisis` verdadero, conecta `boton_aceptar.clicked` a `self.analizar_imagen` EN ESE MOMENTO (por eso el
espia va en la CLASE y se instala antes de construir la pagina); `subirlisto` oculta «Aceptar» y «Cancelar» y crea «Seleccionar otra Imagen». El numero de receptores de
«Aceptar» crece con cada seleccion (una `lambda` de `print` por cada una): se REGISTRA en la salida (`-s`), no se afirma; no es el defecto.

Trampas: T2 (el dialogo de archivo y todo `QMessageBox` simulados), T9 (cada pagina se cierra con la receta completa), T10 (sin cache a nivel de modulo); una excepcion dentro de un
slot de Qt aborta el proceso entero (Trampa 3), asi que el dialogo y el espia nunca lanzan: cuentan, y un `sys.excepthook` propio convierte cualquier excepcion de un slot en
un fallo de la prueba.
"""
import ast
import gc
import inspect
import os
import sqlite3
import sys
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaAnualHalcyon
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

LISTA_MAQUINA_ANUAL_HALCYON = ['encabezado_anual_Halcyon', 'Control anual', 'Iniciar control anual', 'Halcyon', 'preguntas_anual_Halcyon']
PAGINAS_CON_OTRA_IMAGEN = ["minima", "braqui"]       # las que ofrecen «Seleccionar otra Imagen» tras «Aceptar»
PAGINAS_SIN_ANALISIS = ["equipos", "sin_analisis"]   # las que crean el cargador con `analisis=False` (la rama que usa Equipos)


class PantallaMinima(PruebaBasico):
    """La subclase minima de `PruebaBasico`, cableada como estaba el mensual del 600/iX (seiscientos_mensual.py:984-985) hasta E.2, en `b29784d` (G.1, 26-10: esa cableada ya no existe en el mensual; la subclase sigue
    sirviendo de ejemplo del cargador compartido con `analisis` verdadero): `imagenUpLoader()` y `boton_aceptar.clicked -> subirlisto`.
    No construye el `__init__` pesado de `PruebaBasico` (nada de base de datos)."""

    def __init__(self):
        QWidget.__init__(self)

    def analizar_imagen(self):          # lo sustituye el espia
        pass


class PantallaComoEquipos(PruebaBasico):
    """La forma de la clase `Config` de Equipos (ui/paginasGuia/equipos.py): una `PruebaBasico` que crea su cargador con `analisis=False` y que NO tiene `analizar_imagen` (ni la base ni Equipos la
    definen; `test_la_forma_de_equipos_es_la_de_su_clase_real` lo vigila). Si algo intenta analizar, `self.analizar_imagen` lanza `AttributeError` dentro del slot. Sin base de datos."""

    def __init__(self):
        QWidget.__init__(self)


class _UsuarioFalso:
    _nombre = "Fisico Uno"
    _usuario = "f1"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    """T2: ningun `QMessageBox` real bajo offscreen (esperaria un clic que nunca llega)."""
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture(autouse=True)
def _excepciones_de_slots(monkeypatch):
    """Una excepcion dentro de un slot de Qt llama a `qFatal` y aborta el proceso entero (Trampa 3): con un `sys.excepthook` propio PyQt la entrega aqui y la prueba cae
    con el motivo a la vista en vez de matar la sesion."""
    capturadas = []
    monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, traza: capturadas.append(f"{tipo.__name__}: {valor}"))
    yield capturadas
    assert not capturadas, f"un slot de Qt lanzo una excepcion: {capturadas}"


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    """BD temporal (nunca una de referencia): la ruta se redirige ANTES de construir `Conexion()`; la fila de `users` va antes de construir las paginas (DP-67: dos SQLite en
    un proceso)."""
    ruta = str(tmp_path / "cc1.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES ('f1', 'x', 'Fisico Uno', 1, '1', 'Físico Médico', 'fisico')")
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def placas(tmp_path):
    """Cuatro PNG pequenos y DISTINTOS (tamano y nivel de gris), hechos en `tmp_path`: una por seleccion."""
    rutas = []
    for i in range(4):
        ruta = str(tmp_path / f"placa_{i}.png")
        assert cv2.imwrite(ruta, np.full((12 + 3 * i, 16 + 5 * i, 3), 40 + 50 * i, np.uint8))
        rutas.append(ruta)
    return rutas


class DialogoDeArchivo:
    """Sustituye a `QFileDialog.getOpenFileName` (T2). Contesta lo que la prueba le puso en `respuestas` (una ruta, o "" para cancelar) y cuenta cuantas veces se abrio. Nunca
    lanza: una apertura que la prueba no esperaba se cuenta en `sin_respuesta` y contesta «cancelado»."""

    def __init__(self):
        self.respuestas = []
        self.abiertos = 0
        self.sin_respuesta = 0

    def __call__(self, *args, **kwargs):
        self.abiertos += 1
        if not self.respuestas:
            self.sin_respuesta += 1
            return ("", "")
        return (self.respuestas.pop(0), "")


@pytest.fixture
def dialogo(monkeypatch):
    falso = DialogoDeArchivo()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(falso))
    return falso


class EspiaDeAnalisis:
    """Cuenta las llamadas a `analizar_imagen` de una CLASE. `subir_imagen` conecta `boton_aceptar.clicked` a `self.analizar_imagen` en el momento de la seleccion, asi que el
    espia tiene que estar instalado ANTES de construir la pagina (cubre tambien una conexion hecha al construirla): se instala en la clase, con `monkeypatch`."""

    def __init__(self, monkeypatch, clase):
        self.monkeypatch = monkeypatch
        self.clase = clase
        self.llamadas = 0

    def instalar(self):
        espia = self

        def analizar_imagen(pagina):
            espia.llamadas += 1

        self.monkeypatch.setattr(self.clase, "analizar_imagen", analizar_imagen)


def _cerrar(pagina):
    """T9: la receta completa (sin el bucle de eventos las paginas quedan vivas con sus lambdas)."""
    pagina.hide()
    pagina.close()
    pagina.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


class Escenario:
    """Una pagina real (o la subclase minima) con su dialogo falso y su espia, manejada con los clics que da el fisico."""

    def __init__(self, nombre, pagina, dialogo, espia, placas):
        self.nombre = nombre
        self.pagina = pagina
        self.dialogo = dialogo
        self.espia = espia
        self.placas = placas
        self.selecciones = 0          # selecciones hechas (con una imagen elegida)
        self.bitacora = []            # lo que se REGISTRA y no se afirma: receptores de «Aceptar» en cada paso

    def receptores(self):
        aceptar = self.pagina.boton_aceptar
        return aceptar.receivers(aceptar.clicked)

    def _anotar(self, paso):
        self.bitacora.append(f"CC1 receptores de Aceptar [{self.nombre}] {paso}: {self.receptores()}")

    def _boton_de_la_seleccion(self):
        """La primera seleccion es por «Seleccionar Imagen»; las siguientes, por «Seleccionar otra Imagen» (que `subirlisto` crea al aceptar)."""
        if self.selecciones == 0:
            return self.pagina.boton_subir
        assert hasattr(self.pagina, "agregar_imagen"), (
            "no existe «Seleccionar otra Imagen» tras aceptar: el camino de la segunda seleccion que fija esta prueba no existe en la pagina "
            "(¿se dejo de cablear `subirlisto` a «Aceptar»?)")
        return self.pagina.agregar_imagen

    def _pulsar_seleccion(self, boton, respuesta):
        self.dialogo.respuestas.append(respuesta)
        boton.click()

    def seleccionar(self):
        """Una seleccion de verdad: el dialogo se abre una vez, la imagen elegida pasa por `subir_imagen` y elegir NO analiza."""
        ruta = self.placas[self.selecciones]
        boton = self._boton_de_la_seleccion()
        abiertos_antes = self.dialogo.abiertos
        llamadas_antes = self.espia.llamadas
        self._pulsar_seleccion(boton, ruta)
        assert self.dialogo.abiertos == abiertos_antes + 1, (
            f"el dialogo de archivo se abrio {self.dialogo.abiertos - abiertos_antes} veces en la seleccion {self.selecciones + 1} (debia abrirse una)")
        assert self.dialogo.sin_respuesta == 0, "se abrio un dialogo de archivo que la prueba no esperaba"
        imagen_path = getattr(self.pagina, "imagen_path", None)
        assert imagen_path == ruta, f"la seleccion {self.selecciones + 1} no paso por `subir_imagen`: imagen_path={imagen_path!r}, se esperaba {ruta!r}"
        assert self.espia.llamadas == llamadas_antes, (
            f"elegir la imagen {self.selecciones + 1} ya llamo a `analizar_imagen` ({self.espia.llamadas - llamadas_antes} veces): solo «Aceptar» analiza")
        assert self.pagina.boton_subir.isHidden(), f"tras la seleccion {self.selecciones + 1} «Seleccionar Imagen» sigue a la vista"
        assert not self.pagina.boton_aceptar.isHidden(), f"tras la seleccion {self.selecciones + 1} «Aceptar» no aparece"
        self.selecciones += 1
        self._anotar(f"tras la seleccion {self.selecciones}")

    def cancelar_el_dialogo(self):
        """El fisico abre el dialogo de archivo y lo cancela: no hay seleccion, no cambia nada, y el boton sigue ahi."""
        boton = self._boton_de_la_seleccion()
        abiertos_antes = self.dialogo.abiertos
        llamadas_antes = self.espia.llamadas
        receptores_antes = self.receptores()
        self._pulsar_seleccion(boton, "")
        assert self.dialogo.abiertos == abiertos_antes + 1, "cancelar tambien abre el dialogo de archivo, una vez"
        assert self.espia.llamadas == llamadas_antes, "cancelar el dialogo llamo a `analizar_imagen`"
        assert self.receptores() == receptores_antes, (
            f"cancelar el dialogo de archivo cambio los receptores de «Aceptar»: {receptores_antes} -> {self.receptores()}")
        assert not boton.isHidden(), "cancelar el dialogo oculto el boton de seleccion: se conto como una seleccion"
        assert self.pagina.boton_aceptar.isHidden(), "cancelar el dialogo mostro «Aceptar»: se conto como una seleccion"
        self._anotar("tras cancelar el dialogo")

    def aceptar(self):
        """Un clic en «Aceptar»; devuelve cuantas veces llamo a `analizar_imagen`."""
        antes = self.espia.llamadas
        self.pagina.boton_aceptar.click()
        self._anotar("tras aceptar")
        return self.espia.llamadas - antes


@pytest.fixture
def abrir(app, bd_temporal, dialogo, placas, monkeypatch):
    """Fabrica de escenarios. El espia se instala en la CLASE ANTES de construir la pagina; cada pagina se cierra al terminar la prueba (T9)."""
    abiertas = []

    def _abrir(nombre):
        if nombre == "minima":
            clase = PantallaMinima
        elif nombre == "braqui":
            clase = PruebaDiariaBraq
        elif nombre == "halcyon":
            clase = PruebaAnualHalcyon
        elif nombre == "sin_analisis":           # la subclase minima, con el cargador sin analisis y `analizar_imagen` espiado
            clase = PantallaMinima
        elif nombre == "equipos":                # la forma de Equipos: cargador sin analisis y SIN `analizar_imagen`
            clase = PantallaComoEquipos
        else:
            raise AssertionError(nombre)
        espia = EspiaDeAnalisis(monkeypatch, clase)
        if nombre != "equipos":                  # `PantallaComoEquipos` no tiene `analizar_imagen` que espiar: si algo intenta analizar, lanza `AttributeError` dentro del slot
            espia.instalar()                     # ANTES de construir la pagina y de la primera seleccion (CC1-F)
        if nombre == "minima":
            pagina = PantallaMinima()
            pagina._contenedor_del_cargador = pagina.imagenUpLoader()      # sin una referencia el QWidget se destruye con sus botones
            pagina.boton_aceptar.clicked.connect(pagina.subirlisto)        # como seiscientos_mensual.py:985
        elif nombre in ("sin_analisis", "equipos"):
            pagina = clase()
            pagina._contenedor_del_cargador = pagina.imagenUpLoader(analisis=False)      # como equipos.py:422; sin `subirlisto`: el «Aceptar» de Equipos cierra el visor
        elif nombre == "braqui":
            pagina = PruebaDiariaBraq(_UsuarioFalso())
        else:
            pagina = PruebaAnualHalcyon(_UsuarioFalso())
            indice = pagina.fisico1.findText(_UsuarioFalso._nombre)
            assert indice >= 0, "el fisico de prueba no aparece en el combo: fixture mal sembrada"
            pagina.fisico1.setCurrentIndex(indice)
            pagina._iniciar_moviendo_tabla(LISTA_MAQUINA_ANUAL_HALCYON)
            assert getattr(pagina, "ref", None) is not None, "«Iniciar» no creo el control anual"
        abiertas.append(pagina)
        escenario = Escenario(nombre, pagina, dialogo, espia, placas)
        escenario._anotar("al construir la pagina")
        return escenario

    yield _abrir
    for pagina in abiertas:
        _cerrar(pagina)


@pytest.fixture
def bitacora_a_la_salida():
    """Imprime lo que se registra y no se afirma (con `-s` queda en el log de la corrida)."""
    escenarios = []
    yield escenarios
    for escenario in escenarios:
        for linea in escenario.bitacora:
            print(linea)


@pytest.fixture
def escenario_de(abrir, bitacora_a_la_salida):
    def _abrir(nombre):
        escenario = abrir(nombre)
        bitacora_a_la_salida.append(escenario)
        return escenario
    return _abrir


# ============================================================================================ el mecanismo compartido y el diario de braquiterapia
@pytest.mark.parametrize("pagina", PAGINAS_CON_OTRA_IMAGEN)
class TestOtraImagenNoAnadeOtroAnalisis:
    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_tras_n_selecciones_aceptar_analiza_exactamente_una_vez(self, escenario_de, pagina, n):
        esc = escenario_de(pagina)
        for k in range(1, n + 1):
            esc.seleccionar()                       # la 1a por «Seleccionar Imagen»; las siguientes por «Seleccionar otra Imagen»
            llamadas = esc.aceptar()
            assert llamadas == 1, f"tras {k} selecciones un clic en «Aceptar» llamo {llamadas} veces a `analizar_imagen` (debia ser exactamente 1)"
            assert esc.espia.llamadas == k, (
                f"acumulado: tras {k} ciclos selecciona-y-acepta el total es {esc.espia.llamadas} (debia subir de uno en uno hasta {k})")
        assert esc.dialogo.abiertos == n, f"el dialogo de archivo se abrio {esc.dialogo.abiertos} veces en {n} selecciones"

    @pytest.mark.parametrize("m", [2, 3])
    def test_varias_reselecciones_seguidas_sin_aceptar_siguen_dando_una_sola_llamada(self, escenario_de, pagina, m):
        esc = escenario_de(pagina)
        esc.seleccionar()
        assert esc.aceptar() == 1, "el primer «Aceptar» no llamo exactamente una vez"
        for _ in range(m):
            esc.seleccionar()                       # «Seleccionar otra Imagen», sin aceptar entre una y otra
        llamadas = esc.aceptar()
        assert llamadas == 1, f"tras {1 + m} selecciones (la ultima tanda de {m} sin aceptar) un clic en «Aceptar» llamo {llamadas} veces (debia ser exactamente 1)"
        assert esc.espia.llamadas == 2, f"acumulado: dos «Aceptar» sumaron {esc.espia.llamadas} llamadas (debian ser 2)"
        assert esc.dialogo.abiertos == 1 + m

    def test_cancelar_el_dialogo_antes_de_la_primera_seleccion_no_cuenta(self, escenario_de, pagina):
        esc = escenario_de(pagina)
        esc.cancelar_el_dialogo()
        esc.seleccionar()
        llamadas = esc.aceptar()
        assert llamadas == 1, f"tras cancelar el dialogo y elegir una imagen, «Aceptar» llamo {llamadas} veces (debia ser exactamente 1)"
        assert esc.dialogo.abiertos == 2          # el cancelado y el de la seleccion

    def test_cancelar_el_dialogo_antes_de_una_nueva_seleccion_no_cuenta(self, escenario_de, pagina):
        esc = escenario_de(pagina)
        esc.seleccionar()
        assert esc.aceptar() == 1
        esc.cancelar_el_dialogo()                  # «Seleccionar otra Imagen» y cancelar
        esc.seleccionar()
        llamadas = esc.aceptar()
        assert llamadas == 1, f"tras cancelar una segunda seleccion y elegir una imagen, «Aceptar» llamo {llamadas} veces (debia ser exactamente 1)"
        assert esc.espia.llamadas == 2
        assert esc.dialogo.abiertos == 3


# ============================================================================================ el anual del Halcyon
class TestAnualDelHalcyon:
    @pytest.mark.parametrize("clics", [1, 2, 3])
    def test_cada_clic_en_aceptar_tras_la_unica_seleccion_analiza_exactamente_una_vez(self, escenario_de, clics):
        esc = escenario_de("halcyon")
        esc.seleccionar()
        for c in range(1, clics + 1):
            llamadas = esc.aceptar()
            assert llamadas == 1, f"el clic {c} en «Aceptar» llamo {llamadas} veces a `analizar_imagen` (debia ser exactamente 1)"
            assert esc.espia.llamadas == c, f"acumulado: tras {c} clics el total es {esc.espia.llamadas} (debia subir de uno en uno)"
        assert esc.dialogo.abiertos == 1, "el anual abrio el dialogo de archivo mas de una vez"

    def test_cancelar_el_dialogo_antes_de_la_seleccion_no_cuenta(self, escenario_de):
        esc = escenario_de("halcyon")
        esc.cancelar_el_dialogo()
        esc.seleccionar()
        llamadas = esc.aceptar()
        assert llamadas == 1, f"tras cancelar el dialogo y elegir una imagen, «Aceptar» llamo {llamadas} veces (debia ser exactamente 1)"
        assert esc.dialogo.abiertos == 2

    def test_el_anual_no_ofrece_una_segunda_seleccion(self, escenario_de):
        """Hecho de la pagina REAL, medido el 18-10: `subirlisto` no esta cableado a «Aceptar» en el anual, asi que tras la primera seleccion no hay «Seleccionar otra Imagen» ni
        «Seleccionar Imagen» a la vista, y «Cancelar» no devuelve el boton de seleccion. Si alguien anade un camino a una segunda seleccion, esa seleccion entra por
        `subir_imagen` y hay que cubrirla aqui con los casos de 2 y 3 selecciones (como en el diario de braquiterapia)."""
        esc = escenario_de("halcyon")
        esc.seleccionar()
        assert esc.aceptar() == 1
        assert not hasattr(esc.pagina, "agregar_imagen"), (
            "el anual del Halcyon ya ofrece «Seleccionar otra Imagen»: hay que cubrirla con los casos de 2 y 3 selecciones (copiar los del diario de braquiterapia)")
        assert esc.pagina.boton_subir.isHidden(), (
            "«Seleccionar Imagen» volvio a estar a la vista tras la seleccion: hay un camino a una segunda seleccion que esta prueba no cubre")
        esc.pagina.boton_cancel.click()
        assert esc.pagina.boton_subir.isHidden(), (
            "«Cancelar» devolvio «Seleccionar Imagen» en el anual: hay un camino a una segunda seleccion (Cancelar y volver a seleccionar) que esta prueba no cubre "
            "y que en el diario de braquiterapia suma una conexion de `analizar_imagen`")
        assert esc.dialogo.abiertos == 1


# ============================================================================================ la rama sin analisis del cargador (Equipos)
def _sin_excepciones_de_slots(capturadas, donde):
    """PyQt no deja subir al test una excepcion lanzada dentro de un slot: la entrega a `sys.excepthook` (aqui, la lista del fixture `_excepciones_de_slots`). Se revisa en el paso que corresponde,
    para que el fallo diga CUAL paso la lanzo, y se vacia la lista antes de afirmar para que el cierre del fixture no repita el mismo fallo."""
    motivo = list(capturadas)
    capturadas.clear()
    assert not motivo, f"{donde}: un slot de Qt lanzo una excepcion: {motivo}"


@pytest.mark.parametrize("pagina", PAGINAS_SIN_ANALISIS)
class TestCargadorSinAnalisis:
    @pytest.mark.parametrize("clics", [1, 2, 3])
    def test_con_analisis_falso_aceptar_no_analiza_ninguna_vez(self, escenario_de, _excepciones_de_slots, pagina, clics):
        """El otro lado del contrato, el que usa Equipos (`imagenUpLoader(analisis=False)`): la bandera decide que «Aceptar» NO analiza. Dos instrumentos, uno por pagina: con `analizar_imagen` espiado
        (`sin_analisis`) el conteo debe ser 0 en cada clic; sin el metodo (`equipos`, la forma real de Equipos) cualquier intento de analizar lanza `AttributeError` dentro del slot y la prueba lo
        dice en el paso que lo lanzo. Un cargador que ignorara `analisis=False` (conectar `analizar_imagen` en la primera seleccion de todas formas) cae en las dos."""
        esc = escenario_de(pagina)
        esc.seleccionar()                       # el dialogo se abre una vez, la imagen pasa por `subir_imagen` y elegir NO analiza
        _sin_excepciones_de_slots(_excepciones_de_slots, "al elegir la imagen")
        for c in range(1, clics + 1):
            llamadas = esc.aceptar()
            _sin_excepciones_de_slots(_excepciones_de_slots, f"en el clic {c} en «Aceptar»")
            assert llamadas == 0, f"con `analisis=False` el clic {c} en «Aceptar» llamo {llamadas} veces a `analizar_imagen` (debia ser 0: ese cargador no analiza)"
        assert esc.espia.llamadas == 0, f"con `analisis=False` el total de llamadas a `analizar_imagen` fue {esc.espia.llamadas} (debia ser 0)"
        assert esc.dialogo.abiertos == 1, f"el dialogo de archivo se abrio {esc.dialogo.abiertos} veces en una sola seleccion"


def test_la_forma_de_equipos_es_la_de_su_clase_real():
    """`PantallaComoEquipos` imita a Equipos mientras (a) ni `PruebaBasico` ni `Config` definan `analizar_imagen` (si lo definieran, un intento de analizar dejaria de lanzar y el escenario «equipos»
    perderia su instrumento) y (b) Equipos cree su cargador con `analisis=False` (`imagenUpLoader(analisis=False)` en `Config.imagen_certificado`). Si algo de eso cambia, esta prueba lo dice y hay que
    revisar el escenario en vez de dejar que siga verde sin vigilar nada."""
    from ui.paginasGuia.equipos import Config
    assert not hasattr(PruebaBasico, "analizar_imagen"), (
        "`PruebaBasico` ya define `analizar_imagen`: el escenario «equipos» ya no detecta un intento de analizar (no lanzaria); revisarlo")
    assert not hasattr(Config, "analizar_imagen"), (
        "Equipos ya define `analizar_imagen`: su «Aceptar» podria analizar; revisar el escenario «equipos» y la rama sin analisis")
    arbol = ast.parse(textwrap.dedent(inspect.getsource(Config.imagen_certificado)))
    cargadores = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "imagenUpLoader"]
    assert len(cargadores) == 1, f"`Config.imagen_certificado` crea {len(cargadores)} cargadores (se esperaba 1): revisar el escenario «equipos»"
    banderas = {k.arg: getattr(k.value, "value", "(no es un literal)") for k in cargadores[0].keywords}
    assert banderas == {"analisis": False}, (
        f"Equipos ya no crea su cargador con `analisis=False` (argumentos: {banderas}): su «Aceptar» analizaria y `Config` no tiene `analizar_imagen`")
