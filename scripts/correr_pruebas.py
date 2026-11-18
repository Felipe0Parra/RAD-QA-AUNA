#!/usr/bin/env python
"""Corre las pruebas de la suite, cada archivo en su propio proceso de pytest.

Sin argumentos corre todos los archivos que pytest recoge, uno a la vez y
mostrando cada prueba en vivo. Con --procesos N reparte los archivos en N
procesos a la vez. Si un archivo pasa --silencio-max segundos sin escribir
nada, se detiene su grupo de procesos y la corrida sigue. Antes de correr,
pytest lista cuántas pruebas recoge por archivo; al final se comprueba que
terminaron todas. Se imprime un informe y se guarda con el registro de cada
archivo en resultados_pruebas/<fecha>/.

Uso (desde la raíz del repositorio, con el Python del entorno virtual):
    .venv/bin/python scripts/correr_pruebas.py
    .venv/bin/python scripts/correr_pruebas.py --procesos 8
    .venv/bin/python scripts/correr_pruebas.py tests/test_x.py tests/test_y.py
"""
import argparse
import ast
import codecs
import collections
import datetime
import errno
import io
import math
import os
import queue
import re
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

SILENCIO_POR_OMISION = 600
AVISO_POR_OMISION = 60
PLAZO_RECOLECCION_POR_OMISION = 600
ESPERA_LINEA_PARCIAL = 1.0
LINEAS_DE_COLA = 80
GRACIA_DE_SALIDA = 5.0
ESPERA_TERMINAR = 10.0
PAUSA = 0.05
ANCHO_POR_OMISION = 80
ANCHO_MINIMO = 40
ESPERA_MAXIMA_DE_ESCRITURA = 10.0
ESPERA_DE_ESCRITURA = 0.2
PERIODO_DE_DESCARTE = 5.0
MARCA_INTRUSO = "intruso"
CODIGOS_BUENOS = (0, 1)
CARPETA_DE_RESULTADOS = "resultados_pruebas"
REGISTRO_DE_RECOLECCION = "recoleccion"
VEREDICTO_COMPLETO = "TODAS LAS PRUEBAS PASARON"
VEREDICTO_SIN_COMPROBAR = "TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS"
VEREDICTO_TODO_OMITIDO = "NINGUNA PRUEBA FALLÓ; NO CORRIÓ NINGUNA: TODO LO PEDIDO SE OMITIÓ ENTERO"
VEREDICTO_CON_FALLAS = "HAY PRUEBAS QUE FALLARON O ARCHIVOS CON PROBLEMA"
VARIABLES_DE_COLOR = ("FORCE_COLOR", "NO_COLOR", "PY_COLORS")
DESCRIPCION_DE_CODIGOS = {
    2: "interrumpida", 3: "error interno de pytest", 4: "error de uso de pytest",
    5: "no recogió ninguna prueba",
}

RE_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
RE_SEPARADOR_IGUAL = re.compile(r"^=+ (?P<titulo>.+?) =+$")
RE_SEPARADOR_RT1 = re.compile(r"^-+ RT1 cobertura -+$")
RE_RECOGIDAS = re.compile(r"\bcollected \d+ items?\b")
RE_LINEA_DE_PRUEBA = re.compile(r"^\S+::\S")
RE_LINEA_RECOGIDA = re.compile(r"^(.+): (\d+)$")
RE_ERRORES_AL_RECOGER = re.compile(r"Interrupted: (\d+) errors? during collection")
RE_ERROR_DE_ARCHIVO = re.compile(r"^ERROR (?!collecting )(\S.*?)(?: - .*)?$")
RE_DESELECCIONADAS = re.compile(r"\b(\d+) deselected\b")
RE_RECOGIDAS_AL_CORRER = re.compile(r"\bcollected (\d+) items?\b")
# archivos donde pytest busca su configuración, en su orden, con la sección que los hace valer (None: vale vacío)
ARCHIVOS_DE_CONFIGURACION = (
    ("pytest.ini", None),
    (".pytest.ini", None),
    ("pyproject.toml", re.compile(r"^\s*\[tool\.pytest(\.ini_options)?\]", re.M)),
    ("tox.ini", re.compile(r"^\s*\[pytest\]", re.M)),
    ("setup.cfg", re.compile(r"^\s*\[tool:pytest\]", re.M)),
)


# ------------------------------------------------------------------ pantalla

class Pantalla:
    """La salida estándar de la corrida: un fallo al escribir no la tumba.

    Si la salida no admite escritura (O_NONBLOCK y un lector lento), espera un rato a que la admita
    y, si no, pierde solo esa escritura. Únicamente una salida cerrada apaga la pantalla.
    """

    def __init__(self):
        self.sin_escribir_hasta = 0.0
        self.sucio = False

    def escribir(self, texto):
        flujo = sys.stdout
        if flujo is None or time.monotonic() < self.sin_escribir_hasta:
            return
        try:
            for trozo in texto.splitlines(keepends=True):
                if not self._escribir_trozo(flujo, trozo):
                    self.sin_escribir_hasta = time.monotonic() + PERIODO_DE_DESCARTE
                    return
        except UnicodeError:
            pass
        except ValueError:
            desviar_salida()
        except OSError as error:
            if es_salida_cerrada(error):
                desviar_salida()

    def _escribir_trozo(self, flujo, trozo):
        if self.sucio and not self._vaciar(flujo):
            return False
        try:
            flujo.write(trozo)
            flujo.flush()
        except BlockingIOError:
            self.sucio = True
            return self._vaciar(flujo)
        return True

    def _vaciar(self, flujo):
        """Espera a que la salida admita escritura, hasta un máximo, y vacía el búfer."""
        limite = time.monotonic() + ESPERA_MAXIMA_DE_ESCRITURA
        while True:
            try:
                flujo.flush()
            except BlockingIOError:
                restante = limite - time.monotonic()
                if restante <= 0:
                    return False
                try:
                    select.select([], [flujo.fileno()], [], min(restante, ESPERA_DE_ESCRITURA))
                except (OSError, ValueError):
                    return False
            else:
                self.sucio = False
                return True

    def terminar(self):
        """Al final: lo que no se pudo vaciar se descarta para que el intérprete no falle al cerrar."""
        try:
            if self.sucio and not self._vaciar(sys.stdout):
                desviar_salida()
        except (OSError, ValueError, AttributeError):
            desviar_salida()


PANTALLA = Pantalla()


def escribir(texto):
    """Escribe en la pantalla; solo una salida cerrada la apaga, y la corrida sigue sin ella."""
    PANTALLA.escribir(texto)


def escribir_error(texto):
    """Escribe en la salida de errores; si no hay o no responde, no hace nada."""
    try:
        sys.stderr.write(texto)
        sys.stderr.flush()
    except (OSError, ValueError, AttributeError):
        pass


def es_salida_cerrada(error):
    """True si el error de escritura es el de una salida cerrada (tubería rota)."""
    return error.errno == errno.EPIPE or (os.name == "nt" and error.errno == errno.EINVAL)


def desviar_salida():
    """Manda la salida estándar a /dev/null para que no vuelva a fallar ni al cerrar el intérprete."""
    try:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        pass


def preparar_flujos():
    """Pone los errores de codificación de la salida y de los errores en «replace» y le da búfer a una salida que no lo tiene."""
    for flujo in (sys.stdout, sys.stderr):
        if flujo is not None and hasattr(flujo, "reconfigure"):
            try:
                flujo.reconfigure(errors="replace")
            except (OSError, ValueError):
                pass
    dar_bufer_a_la_salida()


def dar_bufer_a_la_salida():
    """Con PYTHONUNBUFFERED o python -u la salida no tiene búfer y, en una tubería que no admite escritura,
    lo que no cabe se pierde sin avisar; con búfer se lanza BlockingIOError y la pantalla espera."""
    flujo = sys.stdout
    try:
        if isinstance(flujo, io.TextIOWrapper) and isinstance(flujo.buffer, io.FileIO):
            flujo.flush()
            # en Linux la pantalla va en UTF-8 aunque el codec del flujo sea ascii; en Windows se respeta el de la consola
            codificacion = flujo.encoding if os.name == "nt" else "utf-8"
            sys.stdout = io.TextIOWrapper(io.BufferedWriter(flujo.buffer), encoding=codificacion, errors="replace",
                                          newline=None if os.name == "nt" else "\n")
    except (OSError, ValueError, AttributeError):
        pass


def salida_es_terminal():
    try:
        return sys.stdout.isatty()
    except (OSError, ValueError, AttributeError):
        return False


def ancho_de_pantalla():
    """Ancho que se le fija a pytest: el de la terminal, o 80 si la salida no es una terminal."""
    ancho = shutil.get_terminal_size((ANCHO_POR_OMISION, 24)).columns if salida_es_terminal() else ANCHO_POR_OMISION
    return ancho if ancho >= ANCHO_MINIMO else ANCHO_POR_OMISION


def ancho_de_separador(ancho):
    """Largo de las líneas separadoras de pytest (en Windows escribe una columna menos)."""
    return ancho - 1 if sys.platform == "win32" else ancho


def cuenta(cantidad, singular, plural):
    return f"{cantidad} {singular if cantidad == 1 else plural}"


# ------------------------------------------------------------ pantalla en vivo

class FiltroEnVivo:
    """Quita de la pantalla lo repetitivo de pytest y muestra la prueba en curso.

    Solo toma por separador una línea del ancho exacto que se le fijó a pytest.
    Desde FAILURES o ERRORS y hasta el resumen corto no oculta nada.
    """

    def __init__(self, salida, ancho, reloj=time.monotonic):
        self.salida = salida
        self.ancho = ancho
        self.reloj = reloj
        self.parcial = ""
        self.mostrado = 0
        self.t_parcial = 0.0
        self._reiniciar()

    def _reiniciar(self):
        self.estado = "visible"
        self.hubo_pruebas = False
        self.passes_ocultada = False
        self.rt1_ocultado = False

    def alimentar(self, texto):
        while True:
            fin = texto.find("\n")
            if fin < 0:
                break
            self._cerrar_linea(self.parcial + texto[:fin])
            self.parcial = ""
            self.mostrado = 0
            texto = texto[fin + 1:]
        if texto:
            self.parcial += texto
            self.t_parcial = self.reloj()

    def pendiente(self):
        """Muestra la línea a medio escribir si lleva un rato sin avanzar."""
        sin_mostrar = self.parcial[self.mostrado:]
        if not sin_mostrar or self.estado not in ("visible", "fallas"):
            return
        if self.reloj() - self.t_parcial < ESPERA_LINEA_PARCIAL:
            return
        self.salida(sin_mostrar)
        self.mostrado = len(self.parcial)

    def terminar(self):
        if self.parcial and (self.estado in ("visible", "fallas") or self.mostrado):
            self.salida(self.parcial[self.mostrado:] + "\n")
        self.parcial = ""
        self.mostrado = 0
        self._reiniciar()

    def _cerrar_linea(self, linea):
        limpia = RE_ANSI.sub("", linea).rstrip("\r")
        self.estado, visible = self._clasificar(limpia)
        if visible or self.mostrado:
            self.salida(linea[self.mostrado:] + "\n")

    def _clasificar(self, limpia):
        """Devuelve (estado siguiente, si la línea se muestra)."""
        if len(limpia) == self.ancho:
            igual = RE_SEPARADOR_IGUAL.match(limpia)
            if igual:
                return self._separador(igual.group("titulo"))
            if RE_SEPARADOR_RT1.match(limpia) and self.estado != "fallas" and not self.rt1_ocultado:
                self.rt1_ocultado = True
                return "rt1", False
        if self.estado == "cabecera":
            if RE_RECOGIDAS.search(limpia):
                return "visible", False
            return "cabecera", limpia.startswith(("INTERNALERROR", "ERROR"))
        if self.estado in ("passes", "rt1"):
            return self.estado, False
        if self.estado == "resumen":
            return "resumen", not limpia.startswith("PASSED ")
        if self.estado == "visible" and RE_LINEA_DE_PRUEBA.match(limpia):
            self.hubo_pruebas = True
        return self.estado, True

    def _separador(self, titulo):
        """Estado que sigue a un separador del ancho exacto, y si se muestra."""
        if titulo in ("FAILURES", "ERRORS"):
            return "fallas", True
        if titulo == "short test summary info":
            return "resumen", True
        if self.estado == "fallas":
            return "fallas", True
        if "test session starts" in titulo and not self.hubo_pruebas:
            return "cabecera", False
        if titulo == "PASSES" and not self.passes_ocultada:
            self.passes_ocultada = True
            return "passes", False
        return "visible", True


# --------------------------------------------------------- procesos y grupos

def enviar_a_grupo(pgid, senal):
    try:
        os.killpg(pgid, senal)
    except (ProcessLookupError, PermissionError):
        pass


def grupo_vivo(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def detener_grupos(procesos):
    """Detiene los procesos y todo su grupo: SIGTERM, espera y SIGKILL a lo que siga vivo (en Windows, taskkill)."""
    if os.name == "nt":
        for proc in procesos:
            if proc.poll() is None:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for proc in procesos:
            try:
                proc.wait(timeout=ESPERA_TERMINAR)
            except subprocess.TimeoutExpired:
                pass
        return
    grupos = [proc.pid for proc in procesos]
    for pgid in grupos:
        enviar_a_grupo(pgid, signal.SIGTERM)
    limite = time.monotonic() + ESPERA_TERMINAR
    while time.monotonic() < limite:
        for proc in procesos:
            proc.poll()
        if not any(grupo_vivo(pgid) for pgid in grupos):
            break
        time.sleep(PAUSA)
    for pgid in grupos:
        if grupo_vivo(pgid):
            enviar_a_grupo(pgid, signal.SIGKILL)
    for proc in procesos:
        try:
            proc.wait(timeout=ESPERA_TERMINAR)
        except subprocess.TimeoutExpired:
            pass


def plugins_definidos():
    """Valor de PYTEST_PLUGINS si tiene algo escrito: el corredor lo conserva pero avisa, porque un complemento puede deseleccionar."""
    return os.environ.get("PYTEST_PLUGINS", "").strip()


def addopts_ignorado():
    """Valor de PYTEST_ADDOPTS si tiene algo escrito: el corredor lo quita del entorno de pytest."""
    return os.environ.get("PYTEST_ADDOPTS", "").strip()


def entorno_del_hijo(ancho):
    entorno = os.environ.copy()
    entorno.pop("PYTEST_ADDOPTS", None)
    for nombre in VARIABLES_DE_COLOR:
        entorno.pop(nombre, None)
    entorno["QT_QPA_PLATFORM"] = "offscreen"
    entorno["PYTHONUNBUFFERED"] = "1"
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["COLUMNS"] = str(ancho)
    return entorno


class Ejecucion:
    """Un archivo de pruebas corriendo en su propio proceso de pytest."""

    def __init__(self, archivo, ruta_log, ruta_xml):
        self.archivo = archivo
        self.ruta_log = ruta_log
        self.ruta_xml = ruta_xml
        self.proc = None
        self.lector = None
        self.cola = None
        self.decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.inicio = 0.0
        self.fin = 0.0
        self.ultima_salida = 0.0
        self.termino = None
        self.salio_en = None
        self.sin_salida = None
        self.interrumpido = False
        self.error_registro = None
        self.salida_retenida = False
        self.argumentos_de_raiz = []

    def _orden(self, en_vivo, con_color):
        orden = [sys.executable, "-m", "pytest", self.archivo, "-v", "-rA", "--tb=short",
                 "-p", "no:cacheprovider", f"--junit-xml={self.ruta_xml}"]
        orden.append("--color=yes" if en_vivo and con_color else "--color=no")
        return orden + self.argumentos_de_raiz

    def iniciar(self, raiz, entorno, en_vivo, con_color):
        self.argumentos_de_raiz = argumentos_de_raiz(raiz)
        orden = self._orden(en_vivo, con_color)
        opciones = dict(cwd=str(raiz), env=entorno, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        if os.name == "nt":
            opciones["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            opciones["start_new_session"] = True
        registro = open(self.ruta_log, "wb")
        self.cola = queue.Queue() if en_vivo else None
        self.inicio = self.ultima_salida = time.monotonic()
        try:
            self.proc = subprocess.Popen(orden, **opciones)
        except BaseException:
            registro.close()
            raise
        lector = threading.Thread(target=self._leer, args=(registro,), daemon=True)
        lector.start()
        self.lector = lector
        threading.Thread(target=self._vigilar, daemon=True).start()

    def _leer(self, registro):
        """Pasa la salida del hijo al registro, a medida que llega, y a la cola de la pantalla."""
        try:
            while True:
                bloque = self.proc.stdout.read(65536)
                if not bloque:
                    break
                if self.error_registro is None:
                    try:
                        registro.write(bloque)
                        registro.flush()
                    except OSError as error:
                        self.error_registro = error
                self.ultima_salida = time.monotonic()
                if self.cola is not None:
                    self.cola.put(bloque)
        finally:
            try:
                registro.close()
            except OSError as error:
                self.error_registro = self.error_registro or error
            if self.cola is not None:
                self.cola.put(None)

    def _vigilar(self):
        """Anota el instante en que el proceso termina, sin esperar a que el bucle principal lo note."""
        self.proc.wait()
        self.termino = time.monotonic()

    def volcar(self, filtro):
        """Pasa al filtro de la pantalla lo que haya llegado."""
        while self.cola is not None:
            try:
                bloque = self.cola.get_nowait()
            except queue.Empty:
                return
            if bloque is None:
                return
            filtro.alimentar(self.decodificador.decode(bloque))

    def revisar(self, silencio_max):
        """True cuando el archivo ya terminó (por sí solo o detenido)."""
        ahora = time.monotonic()
        if self.proc.poll() is None:
            if ahora - self.ultima_salida > silencio_max:
                self.sin_salida = ahora - self.ultima_salida
                self.detener()
                self.cerrar()
                return True
            return False
        if self.salio_en is None:
            self.salio_en = self.termino or ahora
        if self.lector is not None and self.lector.is_alive() and ahora - self.salio_en < GRACIA_DE_SALIDA:
            return False
        self.cerrar()
        return True

    def detener(self):
        detener_grupos([self.proc])

    def cerrar(self):
        """Limpia lo que haya quedado del grupo y cierra la lectura."""
        if os.name == "nt":
            sobrante = self.lector is not None and self.lector.is_alive()
        else:
            sobrante = grupo_vivo(self.proc.pid)
        if sobrante:
            self.detener()
        if self.lector is not None:
            self.lector.join(timeout=GRACIA_DE_SALIDA)
            if self.lector.is_alive():
                self.salida_retenida = True
            else:
                self.proc.stdout.close()
        self.fin = self.termino or time.monotonic()
        self.proc.poll()


# --------------------------------------------------------- recolección previa

class Recoleccion(Ejecucion):
    """El pytest --collect-only previo; `recogidas` queda en None si no se pudo comprobar y `motivo` dice por qué."""

    def __init__(self, ruta_log, pedidos):
        super().__init__("(recolección)", ruta_log, None)
        self.pedidos = list(pedidos)
        self.vencio = False
        self.interrumpida = False
        self.recogidas = None
        self.con_error = []
        self.sin_archivo = []
        self.motivo = None
        self.nota = None

    def _orden(self, en_vivo, con_color):
        # --capture=fd aunque el ini apague la captura (-s): lo que un módulo imprima al importarse no entra en la lista
        return [sys.executable, "-m", "pytest", "--collect-only", "-qq", "-p", "no:cacheprovider", "--color=no",
                "--capture=fd", *self.argumentos_de_raiz, *self.pedidos]

    @property
    def usable(self):
        return self.recogidas is not None

    @property
    def total(self):
        return sum(self.recogidas.values())

    @property
    def vacia(self):
        """True si pytest no encontró nada que recoger (código 5): los archivos que se omitan enteros cuadran con eso."""
        return self.usable and not self.recogidas

    def salida(self):
        """Todo lo que escribió pytest, decodificado."""
        partes = []
        while self.cola is not None:
            try:
                bloque = self.cola.get_nowait()
            except queue.Empty:
                break
            if bloque is None:
                break
            partes.append(self.decodificador.decode(bloque))
        return "".join(partes)


def ruta_bajo_la_raiz(texto, raiz):
    """La ruta de un archivo que existe bajo la raíz, relativa a ella y con barras normales; None si no lo es."""
    absoluta = Path(os.path.normpath(raiz / texto.replace("\\", "/")))
    try:
        ruta = absoluta.relative_to(raiz).as_posix()
    except ValueError:
        return None
    return ruta if absoluta.is_file() else None


def bloque_de_cuentas(texto):
    """Las líneas del principio de la salida -qq, hasta la primera vacía: ahí lista pytest las cuentas `ruta: N`."""
    bloque = []
    for linea in texto.split("\n"):
        limpia = RE_ANSI.sub("", linea).rstrip("\r")
        if not limpia.strip():
            break
        bloque.append(limpia)
    return bloque


def configuracion_de_la_raiz(raiz):
    """El archivo de configuración de pytest que tiene la raíz (el primero que pytest reconocería); None si no tiene."""
    for nombre, seccion in ARCHIVOS_DE_CONFIGURACION:
        ruta = raiz / nombre
        if not ruta.is_file():
            continue
        if seccion is None:
            return ruta
        try:
            if seccion.search(ruta.read_text(encoding="utf-8", errors="replace")):
                return ruta
        except OSError:
            continue
    return None


def argumentos_de_raiz(raiz):
    """La raíz y la configuración de la raíz, para que cada archivo y la recolección usen las mismas aunque haya un ini anidado."""
    argumentos = ["--rootdir", str(raiz)]
    configuracion = configuracion_de_la_raiz(raiz)
    if configuracion is not None:
        argumentos += ["-c", str(configuracion)]
    return argumentos


def leer_recogidas(texto, raiz):
    """Pruebas que pytest lista por archivo (líneas `ruta.py: N` del bloque de cuentas); None si una ruta repetida da cifras distintas."""
    recogidas = {}
    for linea in bloque_de_cuentas(texto):
        hallada = RE_LINEA_RECOGIDA.match(linea)
        ruta = ruta_bajo_la_raiz(hallada.group(1), raiz) if hallada else None
        if ruta is None:
            continue
        cantidad = int(hallada.group(2))
        if recogidas.setdefault(ruta, cantidad) != cantidad:
            return None
    return recogidas


def es_archivo_python(ruta):
    return ruta is not None and ruta.lower().endswith(".py")


def destinos_de_error(texto):
    """Las rutas de las líneas `ERROR ruta - motivo` del resumen de pytest, en orden y con repetidas; sin el `::clase`."""
    destinos = []
    for linea in texto.split("\n"):
        hallada = RE_ERROR_DE_ARCHIVO.match(RE_ANSI.sub("", linea).rstrip("\r"))
        destino = hallada.group(1).split("::")[0] if hallada else ""
        if destino:
            destinos.append(destino)
    return destinos


def hay_errores_al_recoger(texto):
    """True si pytest dice «Interrupted: N errors» o trae líneas `ERROR ruta` (con --continue-on-collection-errors no hay «Interrupted»)."""
    return RE_ERRORES_AL_RECOGER.search(texto) is not None or bool(destinos_de_error(texto))


def leer_errores_al_recoger(texto, raiz):
    """Archivos .py que pytest dice que fallaron al recogerse (líneas `ERROR ruta.py` del resumen), en orden y sin repetir."""
    archivos = []
    for destino in destinos_de_error(texto):
        ruta = ruta_bajo_la_raiz(destino, raiz)
        if es_archivo_python(ruta) and ruta not in archivos:
            archivos.append(ruta)
    return archivos


def errores_al_recoger_sin_archivo(texto, raiz):
    """Errores al recoger que pytest cuenta y que no son de ningún .py que el corredor pueda correr (una carpeta, un conftest roto)."""
    contados = RE_ERRORES_AL_RECOGER.search(texto)
    destinos = destinos_de_error(texto)
    if contados is None and not destinos:
        return []
    otros = []
    for destino in destinos:
        if not es_archivo_python(ruta_bajo_la_raiz(destino, raiz)) and destino not in otros:
            otros.append(destino)
    sin_nombre = max(int(contados.group(1)) if contados else 0, len(destinos)) - len(destinos)
    if sin_nombre > 0:
        otros.append(cuenta(sin_nombre, "error sin nombre", "errores sin nombre"))
    return otros


def cuentas_que_el_corredor_no_corre(texto, raiz):
    """Rutas del bloque de cuentas de pytest que el corredor no corre: lo que no es un .py bajo la raíz (una carpeta, un archivo de datos)."""
    ajenas = []
    for linea in bloque_de_cuentas(texto):
        hallada = RE_LINEA_RECOGIDA.match(linea)
        if hallada is None:
            continue
        ruta = hallada.group(1)
        if not es_archivo_python(ruta_bajo_la_raiz(ruta, raiz)) and ruta not in ajenas:
            ajenas.append(ruta)
    return ajenas


def evaluar_recoleccion(codigo, texto, raiz):
    """Dice si la recolección sirve para comprobar: (recogidas por archivo, motivo si no sirve, nota, con error).

    Sirve con código 0 o con código 2 por errores al recoger, y con código 5 si no había nada que recoger;
    con otro código, sin pruebas listadas o con rutas que el corredor no corre, no.
    Los errores al recoger se deciden por el texto de pytest y no solo por el código: un conftest puede forzar el 0.
    Los archivos con error al recoger se devuelven para correrlos aparte y que den su error.
    """
    hubo_errores = hay_errores_al_recoger(texto)
    if codigo not in (0, 2, 5) or (codigo == 2 and not hubo_errores):
        return None, f"la recolección falló: {descripcion_del_codigo(codigo)}", None, []
    recogidas = leer_recogidas(texto, raiz)
    if recogidas is None:
        return None, "pytest dio cifras distintas para un mismo archivo al recoger", None, []
    ajenas = cuentas_que_el_corredor_no_corre(texto, raiz)
    if ajenas:
        return None, f"pytest listó pruebas en {', '.join(ajenas)}, que el corredor no corre", None, []
    if not recogidas:
        if codigo == 5 and not hubo_errores:
            return {}, None, None, []
        return None, "pytest no listó ninguna prueba al recoger", None, []
    nota = None
    if hubo_errores:
        nota = (f"La recolección terminó con código {codigo}: pytest informó errores al recoger. "
                "Se usó lo que alcanzó a listar.")
    return recogidas, None, nota, leer_errores_al_recoger(texto, raiz) if hubo_errores else []


def recolectar(recoleccion, config, raiz, parada):
    """Corre la recolección previa y deja en `recoleccion` lo que listó o el motivo por el que no se pudo comprobar."""
    entorno = entorno_del_hijo(ancho_de_pantalla())
    escribir(f"Recolectando las pruebas que pytest reconoce (plazo {config.plazo_recoleccion:g} [s])...\n")
    parada.protegida = True
    try:
        try:
            recoleccion.iniciar(raiz, entorno, True, False)
        except OSError as error:
            if recoleccion.proc is not None:
                raise
            recoleccion.motivo = f"no se pudo lanzar pytest para recoger las pruebas: {error.strerror or error}"
            return
        parada.protegida = False
        parada.revisar()
        limite = time.monotonic() + config.plazo_recoleccion
        while not recoleccion.revisar(math.inf):
            if time.monotonic() >= limite:
                recoleccion.vencio = True
                recoleccion.detener()
                recoleccion.cerrar()
                break
            time.sleep(PAUSA)
    except KeyboardInterrupt:
        parada.puede_interrumpir = False
        recoleccion.interrumpida = True
        if recoleccion.proc is not None:
            recoleccion.detener()
            recoleccion.cerrar()
        return
    except BaseException:
        if recoleccion.proc is not None:
            recoleccion.detener()
            recoleccion.cerrar()
        raise
    finally:
        parada.protegida = True
    if recoleccion.vencio:
        recoleccion.motivo = f"la recolección superó su plazo de {config.plazo_recoleccion:g} [s] y se detuvo"
    elif recoleccion.salida_retenida:
        recoleccion.motivo = "un proceso fuera del grupo mantiene abierta la salida de la recolección"
    else:
        texto = recoleccion.salida()
        recoleccion.recogidas, recoleccion.motivo, recoleccion.nota, recoleccion.con_error = evaluar_recoleccion(
            recoleccion.proc.returncode, texto, raiz)
        if recoleccion.usable:
            recoleccion.sin_archivo = errores_al_recoger_sin_archivo(texto, raiz)
    if recoleccion.usable:
        escribir(f"pytest recoge {cuenta(recoleccion.total, 'prueba', 'pruebas')} en "
                 f"{cuenta(len(recoleccion.recogidas), 'archivo', 'archivos')}.\n")
    else:
        escribir(f"No se pudo comprobar que se corrieran todas las pruebas: {recoleccion.motivo}.\n")
    if recoleccion.nota:
        escribir(recoleccion.nota + "\n")
    if recoleccion.sin_archivo:
        escribir(texto_de_errores_sin_archivo(recoleccion) + "\n")


# ------------------------------------------------------------- cifras (XML)

class Resultado:
    """Lo que dejó un archivo de pruebas: cifras, detalle y problema si lo hubo."""

    def __init__(self, archivo, duracion, codigo, recogidas=None):
        self.archivo = archivo
        self.duracion = duracion
        self.codigo = codigo
        self.recogidas = recogidas
        self.al_correrse = None
        self.sin_listar = False
        self.leido = False
        self.corte = False
        self.casos = 0
        self.terminadas = 0
        self.pasaron = self.fallaron = self.errores = self.omitidas = self.xfail = 0
        self.ids_fallaron = []
        self.ids_errores = []
        self.ids_omitidas = []
        self.problema = None
        self.avisos = []
        self.ultimas = []

    @property
    def sin_comprobar(self):
        """True si la recolección no pudo listar este archivo y al correrlo trajo pruebas: no hay con qué compararlo."""
        return self.sin_listar and self.terminadas > 0

    @property
    def faltan(self):
        """Pruebas que pytest recogió y no terminaron; 0 si no se comprobó cuántas recogía."""
        if self.recogidas is None:
            return 0
        return max(0, self.recogidas - (self.terminadas if self.leido else 0))


def primera_linea(texto, maximo=160):
    linea = (texto or "").strip().splitlines()[0] if (texto or "").strip() else ""
    return linea if len(linea) <= maximo else linea[:maximo - 3] + "..."


def id_de_caso(caso, archivo):
    clase = caso.get("classname", "")
    nombre = caso.get("name", "")
    modulo = Path(archivo).with_suffix("").as_posix().replace("/", ".")
    if not clase:
        return archivo if nombre == modulo else f"{archivo}::{nombre}"
    if clase == modulo:
        return f"{archivo}::{nombre}"
    if clase.startswith(modulo + "."):
        return f"{archivo}::{clase[len(modulo) + 1:].replace('.', '::')}::{nombre}"
    return f"{archivo}::{clase}::{nombre}"


def es_error_de_cierre(error):
    """True si el error es del cierre de una prueba (teardown), que ya había pasado."""
    return (error.get("message") or "").startswith("failed on teardown")


def motivo_de_omision(omitida):
    """Motivo de una omitida; en un skip de módulo el XML dice «collection skipped» y el motivo va en el texto."""
    mensaje = omitida.get("message") or ""
    if mensaje == "collection skipped":
        try:
            motivo = ast.literal_eval((omitida.text or "").strip())[2]
        except (ValueError, SyntaxError, IndexError, TypeError):
            motivo = None
        if isinstance(motivo, str):
            mensaje = re.sub(r"^Skipped: ", "", motivo)
    return primera_linea(mensaje)


def leer_xml(resultado, ruta_xml):
    """Llena las cifras del resultado desde el XML, contando como pytest; False si no se puede leer."""
    try:
        raiz = ET.parse(ruta_xml).getroot()
    except (OSError, ET.ParseError):
        return False
    if next(raiz.iter("testsuite"), None) is None:
        return False
    todos = list(raiz.iter("testcase"))
    casos = [c for c in todos if c.get("name")]
    resultado.casos = len(casos)
    resultado.corte = len(casos) < len(todos)
    # una prueba que falla y rompe su cierre aparece dos veces y cuenta una; sin classname es un módulo, no una prueba
    resultado.terminadas = len({(c.get("classname"), c.get("name")) for c in casos if c.get("classname")})
    con_resultado = {id_de_caso(c, resultado.archivo) for c in casos
                     if c.find("failure") is not None or c.find("skipped") is not None}
    for caso in casos:
        identificador = id_de_caso(caso, resultado.archivo)
        falla = caso.find("failure")
        errores = caso.findall("error")
        omitida = caso.find("skipped")
        if falla is not None:
            resultado.fallaron += 1
            resultado.ids_fallaron.append((identificador, primera_linea(falla.get("message"))))
        for error in errores:
            resultado.errores += 1
            resultado.ids_errores.append((identificador, primera_linea(error.get("message"))))
        if omitida is not None:
            if omitida.get("type") == "pytest.xfail":
                resultado.xfail += 1
            else:
                resultado.omitidas += 1
                resultado.ids_omitidas.append((identificador, motivo_de_omision(omitida)))
        elif falla is None and identificador not in con_resultado and all(es_error_de_cierre(e) for e in errores):
            resultado.pasaron += 1
    return True


def ultimas_lineas(ruta, cantidad=LINEAS_DE_COLA):
    try:
        with open(ruta, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 65536))
            datos = f.read()
    except OSError:
        return []
    texto = datos.decode("utf-8", errors="replace")
    return [RE_ANSI.sub("", linea.rstrip("\r")) for linea in texto.splitlines()][-cantidad:]


def recogidas_al_correr(ruta, cantidad=4096):
    """Las pruebas que pytest dice haber recogido al correr el archivo solo (línea `collected N items` de su registro)."""
    try:
        with open(ruta, "rb") as f:
            cabecera = f.read(cantidad).decode("utf-8", errors="replace")
    except OSError:
        return None
    hallada = RE_RECOGIDAS_AL_CORRER.search(RE_ANSI.sub("", cabecera))
    return int(hallada.group(1)) if hallada else None


def deseleccionadas(ruta):
    """Las pruebas que pytest dejó sin seleccionar según su línea final de cifras (la última que empieza por «=»); 0 si no dice nada."""
    for linea in reversed(ultimas_lineas(ruta, 40)):
        if linea.startswith("="):
            hallada = RE_DESELECCIONADAS.search(linea)
            return int(hallada.group(1)) if hallada else 0
    return 0


def descripcion_del_codigo(codigo):
    """Dice cómo terminó pytest: con un código o, si es negativo, por una señal (POSIX)."""
    if codigo is not None and codigo < 0:
        try:
            nombre = f" ({signal.Signals(-codigo).name})"
        except ValueError:
            nombre = ""
        return f"pytest terminó por la señal {-codigo}{nombre}"
    detalle = DESCRIPCION_DE_CODIGOS.get(codigo)
    return f"pytest terminó con código {codigo}" + (f" ({detalle})" if detalle else "")


def omitido_entero(resultado):
    """True si pytest salió con 5 porque todo el archivo se omitió (un skip de módulo) y no había pruebas recogidas."""
    return (resultado.codigo == 5 and resultado.leido and resultado.omitidas > 0 and not resultado.recogidas
            and not (resultado.pasaron or resultado.fallaron or resultado.errores or resultado.xfail))


def texto_de_faltantes(resultado):
    """Dice cuántas de las pruebas que pytest recogió no terminaron."""
    terminaron = resultado.recogidas - resultado.faltan
    if terminaron:
        cuerpo = f"solo {terminaron} {'terminó' if terminaron == 1 else 'terminaron'}"
    else:
        cuerpo = "ninguna terminó"
    texto = (f"pytest recogió {cuenta(resultado.recogidas, 'prueba', 'pruebas')} y {cuerpo} "
             f"({'falta' if resultado.faltan == 1 else 'faltan'} {resultado.faltan})")
    if resultado.al_correrse is not None and resultado.al_correrse < resultado.recogidas:
        texto += f"; al correrse solo, pytest recogió {resultado.al_correrse}"
    return texto


def problema_de(resultado):
    """Motivo por el que el resultado de un archivo no es confiable, o None.

    Suma lo que no cuadra entre el código de pytest y su XML con las pruebas que se recogieron y no terminaron.
    """
    base = problema_del_codigo(resultado)
    if resultado.faltan:
        return f"{base}; {texto_de_faltantes(resultado)}" if base else texto_de_faltantes(resultado)
    return base


def problema_del_codigo(resultado):
    """Motivo por el que el código de pytest y su XML no dan un resultado confiable, o None."""
    if omitido_entero(resultado):
        return None
    if resultado.codigo not in CODIGOS_BUENOS and not (resultado.leido and resultado.corte):
        return descripcion_del_codigo(resultado.codigo)
    if not resultado.leido:
        return "sin XML legible"
    if resultado.corte:
        return "pytest se cortó a mitad: una prueba empezó y no terminó"
    hay_fallas = bool(resultado.fallaron or resultado.errores)
    if resultado.codigo == 0 and hay_fallas:
        return "pytest terminó con 0 pero su resultado trae fallas o errores"
    if resultado.codigo == 1 and not hay_fallas:
        return ("pytest terminó con 1 pero su resultado no trae fallas: falló algo fuera de las pruebas, "
                "como un gancho del conftest")
    if resultado.codigo == 0 and resultado.casos == 0:
        return "pytest terminó con 0 pero no corrió ninguna prueba"
    return None


def resultado_de(ejecucion, recogidas=None):
    """Resultado de un archivo; `recogidas` son las pruebas que pytest listó para él (None si no se comprobó)."""
    resultado = Resultado(ejecucion.archivo, ejecucion.fin - ejecucion.inicio, ejecucion.proc.returncode, recogidas)
    if ejecucion.error_registro is not None:
        resultado.avisos.append(f"registro incompleto: {ejecucion.error_registro}")
    if ejecucion.salida_retenida:
        resultado.avisos.append("un proceso fuera del grupo mantiene abierta la salida")
    if ejecucion.sin_salida is not None:
        resultado.problema = f"detenido: {int(ejecucion.sin_salida)} [s] sin salida"
    elif ejecucion.interrumpido:
        resultado.problema = "interrumpido antes de terminar"
    else:
        resultado.leido = leer_xml(resultado, ejecucion.ruta_xml)
        resultado.al_correrse = recogidas_al_correr(ejecucion.ruta_log) if recogidas else None
        resultado.problema = problema_de(resultado)
        sin_elegir = deseleccionadas(ejecucion.ruta_log)
        if sin_elegir:
            resultado.avisos.append(f"pytest dejó {cuenta(sin_elegir, 'prueba', 'pruebas')} sin seleccionar (deselected)")
    if resultado.problema:
        resultado.ultimas = ultimas_lineas(ejecucion.ruta_log)
    return resultado


# ------------------------------------------------------------------ informe

def texto_duracion(segundos):
    total = int(round(segundos))
    horas, resto = divmod(total, 3600)
    minutos = resto // 60
    if horas:
        aproximado = f" ({horas} h {minutos} min)"
    elif minutos:
        aproximado = f" ({minutos} min)"
    else:
        aproximado = ""
    return f"{total} [s]{aproximado}"


def linea_de_resumen(r):
    if r.leido:
        esperadas = f", {cuenta(r.xfail, 'falla esperada', 'fallas esperadas')} (xfail)" if r.xfail else ""
        cuerpo = (f"{cuenta(r.pasaron, 'pasó', 'pasaron')}, {cuenta(r.fallaron, 'falló', 'fallaron')}, "
                  f"{cuenta(r.errores, 'error', 'errores')}, {cuenta(r.omitidas, 'omitida', 'omitidas')}"
                  f"{esperadas} ({r.duracion:.1f} [s])")
    else:
        cuerpo = f"sin cifras ({r.duracion:.1f} [s])"
    if omitido_entero(r):
        cuerpo += " - archivo omitido entero"
    if r.problema:
        cuerpo += f" - ARCHIVO CON PROBLEMA: {r.problema}"
    if r.avisos:
        cuerpo += " - AVISO: " + "; ".join(r.avisos)
    return cuerpo


def texto_de_errores_sin_archivo(recoleccion):
    return ("pytest informó errores al recoger que no son de ningún archivo que se corra: "
            + "; ".join(recoleccion.sin_archivo) + ".")


def lineas_de_completitud(resultados, recoleccion, addopts, plugins=""):
    """Lo que pytest recogió frente a lo que terminó, los avisos del entorno y las diferencias por archivo."""
    lineas = []
    if recoleccion.usable:
        recogidas = sum(r.recogidas for r in resultados)
        faltan = sum(r.faltan for r in resultados)
        lineas.append(f"Pruebas recogidas por pytest: {recogidas}; corridas: {recogidas - faltan}; faltan: {faltan}")
    elif recoleccion.motivo:
        lineas.append("Pruebas recogidas por pytest: sin comprobar")
    if addopts:
        lineas.append(aviso_de_addopts(addopts))
    if plugins:
        lineas.append(aviso_de_plugins(plugins))
    if recoleccion.nota:
        lineas.append(recoleccion.nota)
    if recoleccion.sin_archivo:
        lineas.append(texto_de_errores_sin_archivo(recoleccion))
        lineas.append("No se pudo comprobar que se corrieran todas las pruebas: hubo errores al recoger de los que no se sabe qué prueba eran.")
    if todo_omitido_entero(resultados, recoleccion):
        lineas.append("Ninguna prueba corrió: todo lo pedido se omitió entero (los motivos están en «Omitidas, con su motivo»).")
    if recoleccion.motivo:
        lineas.append(f"No se pudo comprobar que se corrieran todas las pruebas: {recoleccion.motivo}.")
    diferencias = [r for r in resultados if r.faltan]
    if diferencias:
        lineas.append("Pruebas recogidas que no terminaron:")
        lineas += [f"  {r.archivo} - {texto_de_faltantes(r)}" for r in diferencias]
    sin_comprobar = [r for r in resultados if r.sin_comprobar]
    if sin_comprobar:
        lineas.append("No se pudo comprobar que se corrieran todas las pruebas: "
                      "la recolección no pudo listar archivos que se corrieron sin comparar.")
        lineas.append("Archivos sin comprobar:")
        lineas += [f"  {r.archivo} - terminaron {cuenta(r.terminadas, 'prueba', 'pruebas')}" for r in sin_comprobar]
    return lineas


def completitud_comprobada(resultados, recoleccion):
    """True si la recolección sirvió, no dejó errores sin atribuir a un archivo y ningún archivo se corrió sin comparar."""
    return recoleccion.usable and not recoleccion.sin_archivo and not any(r.sin_comprobar for r in resultados)


def todo_omitido_entero(resultados, recoleccion):
    """True si pytest no encontró nada que recoger y todos los archivos pedidos se omitieron enteros."""
    return recoleccion.vacia and bool(resultados) and all(omitido_entero(r) for r in resultados)


def aviso_de_addopts(valor):
    return f"Se ignoró PYTEST_ADDOPTS={valor}: puede deseleccionar pruebas."


def aviso_de_plugins(valor):
    return f"Está definida PYTEST_PLUGINS={valor}: un complemento puede deseleccionar pruebas. No se quitó."


def construir_informe(resultados, config, carpeta, duracion, total_previsto, estado, recoleccion, addopts, plugins=""):
    pasaron = sum(r.pasaron for r in resultados)
    fallaron = sum(r.fallaron for r in resultados)
    errores = sum(r.errores for r in resultados)
    omitidas = sum(r.omitidas for r in resultados)
    esperadas = sum(r.xfail for r in resultados)
    con_problema = [r for r in resultados if r.problema]
    con_aviso = [r for r in resultados if r.avisos]
    parcial = estado != "completa"
    titulo = "RESULTADO DE LAS PRUEBAS"
    if estado == "interrumpida":
        titulo += " (INTERRUMPIDA, INFORME PARCIAL)"
    elif estado == "error":
        titulo += " (ERROR INTERNO DEL CORREDOR, INFORME PARCIAL)"
    modo = ("en vivo, un archivo a la vez" if config.procesos == 1
            else f"repartido en {config.procesos} procesos")
    cantidad = f"{len(resultados)} de {total_previsto}" if parcial and total_previsto else str(len(resultados))
    lineas = [
        f"{titulo} - {datetime.datetime.now():%d-%m-%Y %H:%M}",
        f"Modo: {modo}",
        f"Archivos: {cantidad}    Duración: {texto_duracion(duracion)}",
        f"Pasaron: {pasaron}   Fallaron: {fallaron}   Errores: {errores}   "
        f"Omitidas: {omitidas}   Archivos con problema: {len(con_problema)}",
    ]
    lineas += lineas_de_completitud(resultados, recoleccion, addopts, plugins)
    if esperadas:
        lineas.append(f"Fallas esperadas (xfail): {esperadas}")
    omitidas_detalle = [x for r in resultados for x in r.ids_omitidas]
    if omitidas_detalle:
        lineas.append("Omitidas, con su motivo:")
        lineas += [f"  {i} - {motivo}" for i, motivo in omitidas_detalle]
    else:
        lineas.append("Omitidas, con su motivo: ninguna")
    fallaron_detalle = [x for r in resultados for x in r.ids_fallaron]
    if fallaron_detalle:
        lineas.append("Fallaron:")
        lineas += [f"  {i} - {mensaje}" if mensaje else f"  {i}" for i, mensaje in fallaron_detalle]
    else:
        lineas.append("Fallaron: ninguna")
    errores_detalle = [x for r in resultados for x in r.ids_errores]
    if errores_detalle:
        lineas.append("Errores:")
        lineas += [f"  {i} - {mensaje}" if mensaje else f"  {i}" for i, mensaje in errores_detalle]
    if con_problema:
        lineas.append("Archivos con problema:")
        for r in con_problema:
            lineas.append(f"  {r.archivo} - {r.problema}")
            lineas += [f"      {linea}" for linea in r.ultimas]
    else:
        lineas.append("Archivos con problema: ninguno")
    if con_aviso:
        lineas.append("Avisos:")
        lineas += [f"  {r.archivo} - {aviso}" for r in con_aviso for aviso in r.avisos]
    if resultados:
        cantidad_lentos = min(10, len(resultados))
        lineas.append("El archivo más lento:" if cantidad_lentos == 1 else f"Los {cantidad_lentos} archivos más lentos:")
        for puesto, r in enumerate(sorted(resultados, key=lambda x: x.duracion, reverse=True)[:10], 1):
            lineas.append(f"  {puesto:>2}. {r.duracion:8.1f} [s]  {r.archivo}")
    lineas.append(f"Detalle de cada archivo: {carpeta}")
    if estado == "interrumpida":
        lineas.append("VEREDICTO: CORRIDA INTERRUMPIDA, SIN VEREDICTO")
    elif estado == "error":
        lineas.append("VEREDICTO: ERROR INTERNO DEL CORREDOR, SIN VEREDICTO")
    else:
        comprobado = completitud_comprobada(resultados, recoleccion)
        omitido = todo_omitido_entero(resultados, recoleccion)
        lineas.append(f"VEREDICTO: {veredicto(fallaron, errores, con_problema, comprobado, omitido)}")
    return "\n".join(lineas) + "\n"


def veredicto(fallaron, errores, con_problema, comprobado, todo_omitido=False):
    """El veredicto de una corrida terminada: solo es completo si además se comprobó que se corrieran todas."""
    if fallaron or errores or con_problema:
        return VEREDICTO_CON_FALLAS
    if not comprobado:
        return VEREDICTO_SIN_COMPROBAR
    return VEREDICTO_TODO_OMITIDO if todo_omitido else VEREDICTO_COMPLETO


def codigo_de_salida(fallaron, errores, con_problema, comprobado, todo_omitido=False):
    return 0 if veredicto(fallaron, errores, con_problema, comprobado, todo_omitido) in (
        VEREDICTO_COMPLETO, VEREDICTO_TODO_OMITIDO) else 1


# ------------------------------------------------------------ argumentos

class FormatoEnEspanol(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or "Uso: ")


class ParserEnEspanol(argparse.ArgumentParser):
    def error(self, message):
        if message.startswith("argument "):
            message = "argumento " + message[len("argument "):]
        message = message.replace("unrecognized arguments:", "argumentos no reconocidos:")
        message = message.replace("expected one argument", "falta el valor")
        message = message.replace("invalid int value", "valor entero no válido")
        message = message.replace("invalid float value", "valor numérico no válido")
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def crear_parser():
    parser = ParserEnEspanol(
        prog="correr_pruebas.py", add_help=False, formatter_class=FormatoEnEspanol,
        description="Corre cada archivo de pruebas en su propio proceso de pytest, muestra el avance "
                    "y deja un informe al final.",
        epilog="Código de salida: 0 si todo pasó (o todo lo pedido se omitió entero) y se comprobó que se corrieron "
               "todas las pruebas que pytest recoge, 1 si hubo fallas, errores o archivos con problema, o si no se pudo comprobar que se "
               "corrieran todas, 2 si el uso es incorrecto, 3 si el corredor tuvo un error interno, "
               "130 si se interrumpe (Ctrl+C, SIGTERM o cierre de la terminal).")
    argumentos = parser.add_argument_group("argumentos")
    argumentos.add_argument("archivos", nargs="*", metavar="archivo",
                            help="archivos .py de pruebas a correr, bajo la raíz; sin ellos se corren todos los "
                                 "que pytest recoge")
    opciones = parser.add_argument_group("opciones")
    opciones.add_argument("-h", "--help", action="help", help="muestra esta ayuda y sale")
    opciones.add_argument("--procesos", type=int, default=1, metavar="N",
                          help="archivos a la vez; con 1 (por omisión) se ven las pruebas en vivo, "
                               "con 2 o más solo una línea por archivo")
    opciones.add_argument("--silencio-max", type=float, default=SILENCIO_POR_OMISION, metavar="SEG",
                          help="segundos sin salida tras los cuales se detiene el grupo de procesos de un "
                               f"archivo (por omisión {SILENCIO_POR_OMISION})")
    opciones.add_argument("--aviso-cada", type=float, default=AVISO_POR_OMISION, metavar="SEG",
                          help="con --procesos 2 o más, cada cuántos segundos sin que termine ningún "
                               f"archivo se avisa cuáles siguen corriendo (por omisión {AVISO_POR_OMISION})")
    opciones.add_argument("--plazo-recoleccion", type=float, default=PLAZO_RECOLECCION_POR_OMISION, metavar="SEG",
                          help="segundos que se espera a la recolección previa de pytest antes de detenerla "
                               f"(por omisión {PLAZO_RECOLECCION_POR_OMISION})")
    opciones.add_argument("--salida", metavar="DIR",
                          help="carpeta de los resultados (por omisión resultados_pruebas/<fecha_hora> "
                               "bajo la raíz; si ya existe se le agrega un sufijo)")
    opciones.add_argument("--raiz", metavar="DIR", default=str(Path(__file__).resolve().parent.parent),
                          help="raíz del proyecto (por omisión la carpeta que contiene a scripts/)")
    return parser


def sin_resolver_enlaces(ruta):
    """Ruta absoluta y normalizada que conserva el nombre de un enlace simbólico."""
    absoluta = Path(os.path.abspath(ruta))
    return absoluta.parent.resolve() / absoluta.name


def archivos_del_patron(raiz):
    """Los tests/test_*.py de la raíz, relativos a ella y en orden alfabético."""
    carpeta = raiz / "tests"
    return [a.relative_to(raiz).as_posix() for a in sorted(carpeta.glob("test_*.py"))] if carpeta.is_dir() else []


def archivos_a_correr(raiz, pedidos, recoleccion):
    """Los archivos pedidos o, sin pedido, la unión de los tests/test_*.py, los que pytest listó y los que falló al recoger."""
    if pedidos:
        return list(pedidos)
    archivos = set(archivos_del_patron(raiz))
    if recoleccion.usable:
        archivos.update(recoleccion.recogidas)
        archivos.update(recoleccion.con_error)
    return sorted(archivos, key=lambda a: Path(a).parts)


def resolver_archivos(raiz, pedidos):
    """Devuelve (archivos pedidos relativos a la raíz, mensaje de error o None); sin pedidos, ([], None)."""
    resueltos = []
    for pedido in pedidos:
        ruta = Path(pedido)
        candidatas = [ruta] if ruta.is_absolute() else [Path.cwd() / ruta, raiz / ruta]
        hallada = next((sin_resolver_enlaces(c) for c in candidatas if c.is_file()), None)
        if hallada is None:
            return [], f"no existe el archivo de pruebas: {pedido}"
        if hallada.suffix != ".py":
            return [], f"no es un archivo .py: {pedido}"
        try:
            relativo = hallada.relative_to(raiz).as_posix()
        except ValueError:
            return [], f"el archivo no está bajo la raíz {raiz}: {pedido}"
        if relativo not in resueltos:
            resueltos.append(relativo)
    return resueltos, None


def ruta_segura_para_pytest(ruta):
    """False si pytest expandiría la ruta (variables de entorno o ~) y el XML saldría en otra parte."""
    texto = str(ruta)
    return os.path.expanduser(os.path.expandvars(texto)) == texto


def reservar_carpeta(base):
    """Crea `base` o, si ya existe, `base_2`, `base_3`...; devuelve la que creó (nunca se pisa nada)."""
    base.parent.mkdir(parents=True, exist_ok=True)
    numero = 1
    while True:
        candidata = base if numero == 1 else base.with_name(f"{base.name}_{numero}")
        try:
            os.mkdir(candidata)
        except FileExistsError:
            numero += 1
            continue
        return candidata


def comprobar_escritura(carpeta):
    """Crea y borra un archivo en la carpeta: así se sabe antes de empezar que se puede escribir en ella."""
    prueba = carpeta / ".prueba_de_escritura"
    prueba.write_bytes(b"")
    prueba.unlink()


def preparar_carpeta(config, raiz):
    """Reserva la carpeta de resultados y comprueba que se pueda escribir en ella; si no, dice por qué y da None."""
    if config.salida:
        base = Path(config.salida).resolve()
        if base.exists() and not base.is_dir():
            escribir_error(f"correr_pruebas.py: error: --salida debe ser una carpeta, pero ya existe "
                           f"un archivo con ese nombre: {base}\n")
            return None
    else:
        base = raiz / CARPETA_DE_RESULTADOS / f"{datetime.datetime.now():%Y-%m-%d_%H%M%S}"
    if not ruta_segura_para_pytest(base):
        escribir_error(f"correr_pruebas.py: error: la ruta de los resultados lleva un $ o un % que pytest "
                       f"tomaría por una variable de entorno; use otra con --salida: {base}\n")
        return None
    try:
        carpeta = reservar_carpeta(base)
    except OSError as error:
        escribir_error(f"correr_pruebas.py: error: no se pudo crear la carpeta de resultados "
                       f"{base}: {error.strerror or error}\n")
        return None
    try:
        comprobar_escritura(carpeta)
    except OSError as error:
        escribir_error(f"correr_pruebas.py: error: no se puede escribir en la carpeta de resultados "
                       f"{carpeta}: {error.strerror or error}\n")
        try:
            carpeta.rmdir()
        except OSError:
            pass
        return None
    return carpeta


def nombre_de_registro(archivo, usados):
    base = Path(archivo).stem
    nombre = base
    numero = 1
    while nombre in usados:
        numero += 1
        nombre = f"{base}_{numero}"
    usados.add(nombre)
    return nombre


def es_intruso(raiz, archivo):
    """True si el fuente nombra a un «intruso»: escribe un .py en el árbol por un instante."""
    try:
        texto = (raiz / archivo).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return MARCA_INTRUSO in texto


# ------------------------------------------------------------------ corrida

class Parada:
    """Pedido de parar la corrida (Ctrl+C, SIGTERM o SIGHUP): solo la primera señal interrumpe."""

    def __init__(self):
        self.pedida = None
        self.protegida = True
        self.puede_interrumpir = True

    def instalar(self):
        """Atiende las señales de parada, salvo las que se heredaron ignoradas (como con nohup)."""
        for nombre in ("SIGINT", "SIGTERM", "SIGHUP"):
            numero = getattr(signal, nombre, None)
            if numero is not None and signal.getsignal(numero) != signal.SIG_IGN:
                signal.signal(numero, self.manejar)

    def manejar(self, numero, marco):
        primera = self.pedida is None
        if primera:
            self.pedida = numero
        if primera and self.puede_interrumpir and not self.protegida:
            raise KeyboardInterrupt

    def revisar(self):
        """Atiende la señal que llegó mientras estaba protegida."""
        if self.pedida is not None and self.puede_interrumpir:
            raise KeyboardInterrupt


def correr(config, raiz, archivos, carpeta, resultados, parada, recoleccion):
    """Ejecuta los archivos, anota sus resultados y devuelve cómo terminó: completa, interrumpida o error."""
    en_vivo = config.procesos == 1
    con_color = en_vivo and salida_es_terminal() and os.name != "nt"
    columnas = ancho_de_pantalla()
    entorno = entorno_del_hijo(columnas)
    filtro = FiltroEnVivo(escribir, ancho_de_separador(columnas)) if en_vivo else None
    if en_vivo:
        normales, intrusos = list(archivos), []
    else:
        intrusos = [a for a in archivos if es_intruso(raiz, a)]
        normales = [a for a in archivos if a not in intrusos]
    pendientes = collections.deque(normales)
    en_serie = collections.deque(intrusos)
    usados = {REGISTRO_DE_RECOLECCION}
    activas = []
    total = len(archivos)
    ancho = len(str(total))
    ultimo_fin = ultimo_aviso = time.monotonic()
    lanzados = 0

    def resultado(ejecucion):
        """El resultado de un archivo, con las pruebas que pytest listó para él si la recolección sirvió."""
        recogidas = recoleccion.recogidas.get(ejecucion.archivo, 0) if recoleccion.usable else None
        terminado = resultado_de(ejecucion, recogidas)
        # con errores al recoger o sin nada que recoger, un archivo que pytest no listó y que trae pruebas queda sin comparar
        no_listado = recoleccion.usable and ejecucion.archivo not in recoleccion.recogidas
        terminado.sin_listar = bool(no_listado and (recoleccion.nota or recoleccion.vacia))
        return terminado

    def lanzar(archivo):
        nonlocal lanzados
        nombre = nombre_de_registro(archivo, usados)
        ejecucion = Ejecucion(archivo, carpeta / f"{nombre}.log", carpeta / f"{nombre}.xml")
        parada.protegida = True
        try:
            activas.append(ejecucion)
            try:
                ejecucion.iniciar(raiz, entorno, en_vivo, con_color)
            except BaseException:
                if ejecucion.proc is None:
                    activas.remove(ejecucion)
                raise
        finally:
            parada.protegida = False
        parada.revisar()
        lanzados += 1
        if en_vivo:
            escribir(f"[{lanzados:>{ancho}}/{total}] {archivo}\n")

    def limpiar():
        """Detiene los grupos que sigan registrados y deja su resultado como interrumpido."""
        restantes = list(activas)
        for ejecucion in restantes:
            ejecucion.interrumpido = True
        detener_grupos([ejecucion.proc for ejecucion in restantes])
        for ejecucion in restantes:
            ejecucion.cerrar()
            if en_vivo:
                ejecucion.volcar(filtro)
            if ejecucion.fin == 0.0:
                ejecucion.fin = time.monotonic()
            resultados.append(resultado(ejecucion))
        activas.clear()

    estado = "completa"
    try:
        parada.protegida = False
        parada.revisar()
        while pendientes or en_serie or activas:
            while pendientes and len(activas) < config.procesos:
                lanzar(pendientes.popleft())
            if en_serie and not pendientes and not activas:
                lanzar(en_serie.popleft())
            time.sleep(PAUSA)
            for ejecucion in list(activas):
                if en_vivo:
                    ejecucion.volcar(filtro)
                    filtro.pendiente()
                if not ejecucion.revisar(config.silencio_max):
                    continue
                if en_vivo:
                    ejecucion.volcar(filtro)
                    filtro.terminar()
                parada.protegida = True
                try:
                    terminado = resultado(ejecucion)
                    resultados.append(terminado)
                    activas.remove(ejecucion)
                finally:
                    parada.protegida = False
                parada.revisar()
                ultimo_fin = time.monotonic()
                if en_vivo:
                    escribir(f"    {linea_de_resumen(terminado)}\n")
                    escribir_ultimas(terminado)
                else:
                    escribir(f"[{len(resultados):>{ancho}}/{total}] {terminado.archivo}: "
                             f"{linea_de_resumen(terminado)}\n")
                    escribir_ultimas(terminado)
            ahora = time.monotonic()
            if not en_vivo and activas and ahora - max(ultimo_fin, ultimo_aviso) >= config.aviso_cada:
                nombres = ", ".join(e.archivo for e in activas)
                escribir(f"... siguen corriendo: {nombres} ({ahora - ultimo_fin:.0f} [s])\n")
                ultimo_aviso = ahora
    except KeyboardInterrupt:
        estado = "interrumpida"
        escribir("\nCorrida interrumpida: se detienen los grupos de procesos de pruebas.\n")
    except Exception as error:
        estado = "error"
        escribir_error(f"correr_pruebas.py: Error interno del corredor: {type(error).__name__}: {error}\n"
                       f"{traceback.format_exc()}")
        escribir("\nError interno del corredor: se detienen los grupos de procesos de pruebas.\n")
    finally:
        parada.puede_interrumpir = False
        if activas:
            limpiar()
        if filtro is not None:
            filtro.terminar()
    return estado


def escribir_ultimas(resultado):
    """Muestra las últimas líneas del registro de un archivo con problema."""
    if resultado.problema:
        for linea in resultado.ultimas:
            escribir(f"      {linea}\n")


def guardar_informe(carpeta, informe):
    try:
        (carpeta / "informe.txt").write_text(informe, encoding="utf-8")
    except OSError as error:
        escribir_error(f"correr_pruebas.py: no se pudo guardar el informe: {error}\n")


def ejecutar(argv, parada):
    parser = crear_parser()
    config = parser.parse_args(argv)
    if config.procesos < 1:
        parser.error("--procesos debe ser 1 o mayor")
    plazos = (config.silencio_max, config.aviso_cada, config.plazo_recoleccion)
    if not all(math.isfinite(valor) and valor > 0 for valor in plazos):
        parser.error("--silencio-max, --aviso-cada y --plazo-recoleccion deben ser números finitos mayores que cero")
    raiz = Path(config.raiz).resolve()
    if not raiz.is_dir():
        escribir_error(f"correr_pruebas.py: error: la raíz no existe: {raiz}\n")
        return 2
    pedidos, mensaje = resolver_archivos(raiz, config.archivos)
    if mensaje:
        escribir_error(f"correr_pruebas.py: error: {mensaje}\n")
        return 2
    carpeta = preparar_carpeta(config, raiz)
    if carpeta is None:
        return 2
    addopts = addopts_ignorado()
    if addopts:
        escribir(aviso_de_addopts(addopts) + "\n")
    plugins = plugins_definidos()
    if plugins:
        escribir(aviso_de_plugins(plugins) + "\n")
    recoleccion = Recoleccion(carpeta / f"{REGISTRO_DE_RECOLECCION}.log", pedidos)
    resultados = []
    archivos = []
    sin_archivos = False
    estado = "error"
    inicio = time.monotonic()
    try:
        recolectar(recoleccion, config, raiz, parada)
        if recoleccion.interrumpida:
            estado = "interrumpida"
            escribir("\nCorrida interrumpida: se detienen los grupos de procesos de pruebas.\n")
        else:
            archivos = archivos_a_correr(raiz, pedidos, recoleccion)
            if archivos:
                modo = ("en vivo, un archivo a la vez" if config.procesos == 1
                        else f"repartido en {config.procesos} procesos")
                escribir(f"Se {'va' if len(archivos) == 1 else 'van'} a correr "
                         f"{cuenta(len(archivos), 'archivo', 'archivos')} de pruebas ({modo}).\n"
                         f"Los resultados quedan en {carpeta}\n")
                estado = correr(config, raiz, archivos, carpeta, resultados, parada, recoleccion)
            else:
                sin_archivos = True
    finally:
        if not sin_archivos:
            informe = construir_informe(resultados, config, carpeta, time.monotonic() - inicio, len(archivos),
                                        estado, recoleccion, addopts, plugins)
            guardar_informe(carpeta, informe)
            escribir("\n" + informe)
    if sin_archivos:
        escribir_error(f"correr_pruebas.py: error: no hay archivos de pruebas que correr bajo {raiz}\n")
        return 2
    if estado == "interrumpida":
        return 130
    if estado == "error":
        return 3
    con_problema = [r for r in resultados if r.problema]
    return codigo_de_salida(sum(r.fallaron for r in resultados), sum(r.errores for r in resultados),
                            con_problema, completitud_comprobada(resultados, recoleccion),
                            todo_omitido_entero(resultados, recoleccion))


def principal(argv=None):
    parada = Parada()
    parada.instalar()
    preparar_flujos()
    try:
        return ejecutar(argv, parada)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        escribir_error(f"correr_pruebas.py: Error interno del corredor: {type(error).__name__}: {error}\n"
                       f"{traceback.format_exc()}")
        return 3
    finally:
        PANTALLA.terminar()


if __name__ == "__main__":
    try:
        codigo = principal()
    except KeyboardInterrupt:
        codigo = 130
    sys.exit(codigo)
