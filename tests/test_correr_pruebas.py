"""Pruebas del corredor de pruebas (scripts/correr_pruebas.py).

Cada caso arma un proyecto sintético en una carpeta temporal y lanza el corredor
como proceso aparte. No se importa Qt ni nada de la aplicación.
"""
import ctypes
import errno
import importlib.util
import io
import os
import re
import select
import signal
import subprocess
import sys
import textwrap
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

RUTA_CORREDOR = Path(__file__).resolve().parent.parent / "scripts" / "correr_pruebas.py"
ES_POSIX = os.name == "posix"
ES_LINUX = sys.platform.startswith("linux")
ES_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
PR_SET_PDEATHSIG = 1
SOLO_POSIX = pytest.mark.skipif(not ES_POSIX, reason="usa grupos de procesos y señales de POSIX")
SOLO_LINUX = pytest.mark.skipif(not ES_LINUX, reason="usa /proc y prctl, que solo existen en Linux")
NO_ROOT = pytest.mark.skipif(ES_ROOT, reason="root escribe en carpetas sin permiso de escritura")

RE_CIFRAS = re.compile(
    r"Pasaron: (\d+)\s+Fallaron: (\d+)\s+Errores: (\d+)\s+Omitidas: (\d+)\s+Archivos con problema: (\d+)")
RE_COMPLETITUD = re.compile(r"^Pruebas recogidas por pytest: (\d+); corridas: (\d+); faltan: (\d+)$", re.M)


# ---------------------------------------------------------------- utilidades

VARIABLES_QUE_CAMBIAN_LA_SALIDA = ("FORCE_COLOR", "PY_COLORS", "NO_COLOR", "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
                                  "PYTHONUNBUFFERED")


@pytest.fixture(autouse=True)
def _entorno_del_llamador_no_cambia_los_casos(monkeypatch):
    """Los casos no dependen del color ni de las opciones de pytest que traiga el entorno de quien los lanza."""
    for nombre in VARIABLES_QUE_CAMBIAN_LA_SALIDA:
        monkeypatch.delenv(nombre, raising=False)


def _fuente(texto):
    return textwrap.dedent(texto).lstrip("\n")


def _proyecto(base, archivos, conftest=None):
    """Crea <base>/proyecto con su pytest.ini, su carpeta tests/ y los archivos dados."""
    proyecto = base / "proyecto"
    (proyecto / "tests").mkdir(parents=True)
    (proyecto / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    for nombre, cuerpo in archivos.items():
        (proyecto / "tests" / nombre).parent.mkdir(parents=True, exist_ok=True)
        (proyecto / "tests" / nombre).write_text(_fuente(cuerpo), encoding="utf-8")
    if conftest is not None:
        (proyecto / "tests" / "conftest.py").write_text(_fuente(conftest), encoding="utf-8")
    return proyecto


def _fijar_senales(ignorando=()):
    """Para el proceso hijo: las señales de parada con su acción por omisión, aunque se hayan heredado ignoradas."""
    for nombre in ("SIGINT", "SIGTERM", "SIGHUP"):
        accion = signal.SIG_IGN if nombre in ignorando else signal.SIG_DFL
        signal.signal(getattr(signal, nombre), accion)


def _preparar_hijo(ignorando=(), limite_de_archivo=None, mascara=None, cerrar=()):
    """Función para preexec_fn: señales por omisión, muerte con el padre (Linux) y lo que pida cada caso."""
    padre = os.getpid()
    libc = ctypes.CDLL(None, use_errno=True) if ES_LINUX else None
    if limite_de_archivo is not None:
        import resource

    def preparar():
        _fijar_senales(ignorando)
        if libc is not None:
            libc.prctl(PR_SET_PDEATHSIG, int(signal.SIGTERM), 0, 0, 0)
            if os.getppid() != padre:
                os._exit(1)
        if limite_de_archivo is not None:
            resource.setrlimit(resource.RLIMIT_FSIZE, (limite_de_archivo, resource.RLIM_INFINITY))
        if mascara is not None:
            os.umask(mascara)
        for descriptor in cerrar:
            os.close(descriptor)
    return preparar


def _lanzar(orden, cwd, entorno=None, ignorando=(), stderr=subprocess.STDOUT, **hijo):
    """Lanza un proceso en su propio grupo; en Linux muere con el proceso que lo lanzó."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(entorno or {})
    opciones = dict(cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr)
    if ES_POSIX:
        opciones["start_new_session"] = True
        opciones["preexec_fn"] = _preparar_hijo(ignorando, **hijo)
    else:
        opciones["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(orden, **opciones)


def _detener(proc):
    """Detiene al proceso: primero con SIGTERM, para que el corredor limpie a los suyos."""
    if proc.poll() is not None:
        return
    if ES_POSIX:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=20)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    else:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    proc.wait()


def _esperar_con_errores(proc, limite):
    """Espera al proceso y devuelve (salida, errores); si vence el tiempo lo detiene y falla."""
    try:
        salida, errores = proc.communicate(timeout=limite)
    except subprocess.TimeoutExpired:
        _detener(proc)
        parcial, _ = proc.communicate()
        pytest.fail(f"venció el tiempo ({limite} [s]); salida parcial:\n"
                    + parcial.decode("utf-8", errors="replace"))
    return salida.decode("utf-8", errors="replace"), (errores or b"").decode("utf-8", errors="replace")


def _esperar(proc, limite):
    return _esperar_con_errores(proc, limite)[0]


def _ejecutar(orden, cwd, limite=240, entorno=None, **hijo):
    proc = _lanzar(orden, cwd, entorno, **hijo)
    salida = _esperar(proc, limite)
    return proc.returncode, salida


class Corrida:
    def __init__(self, codigo, pantalla, segundos, carpeta, errores=""):
        self.codigo = codigo
        self.pantalla = pantalla
        self.segundos = segundos
        self.carpeta = carpeta
        self.errores = errores

    @property
    def informe(self):
        return (self.carpeta / "informe.txt").read_text(encoding="utf-8")


def _correr(proyecto, *argumentos, limite=240, entorno=None, salida="auto", aparte=False, **hijo):
    """Corre el corredor sobre el proyecto sintético y espera a que termine.

    Con `aparte` la salida de errores no se mezcla con la pantalla y queda en `errores`.
    """
    carpeta = proyecto / "salidas" / uuid.uuid4().hex[:8]
    orden = [sys.executable, str(RUTA_CORREDOR), "--raiz", str(proyecto)]
    if salida == "auto":
        orden += ["--salida", str(carpeta)]
    orden += [str(a) for a in argumentos]
    inicio = time.monotonic()
    proc = _lanzar(orden, proyecto, entorno, stderr=subprocess.PIPE if aparte else subprocess.STDOUT, **hijo)
    pantalla, errores = _esperar_con_errores(proc, limite)
    return Corrida(proc.returncode, pantalla, time.monotonic() - inicio, carpeta, errores)


def _cifras(texto):
    hallado = RE_CIFRAS.search(texto)
    assert hallado, f"no hay línea de cifras en:\n{texto}"
    return tuple(int(x) for x in hallado.groups())


def _completitud(texto):
    """(recogidas, corridas, faltan) de la línea de completitud del informe."""
    hallado = RE_COMPLETITUD.search(texto)
    assert hallado, f"no hay línea de completitud en:\n{texto}"
    return tuple(int(x) for x in hallado.groups())


def _seccion(informe, titulo):
    """Líneas sangradas que siguen a la línea `titulo` (sola en su renglón)."""
    lineas = informe.splitlines()
    assert titulo in [l.rstrip() for l in lineas], f"falta la sección {titulo!r} en:\n{informe}"
    inicio = [l.rstrip() for l in lineas].index(titulo) + 1
    cuerpo = []
    for linea in lineas[inicio:]:
        if linea.startswith((" ", "\t")):
            cuerpo.append(linea.strip())
        else:
            break
    return cuerpo


def _viva(pid):
    """True si el proceso existe y no es un zombi."""
    estado = Path(f"/proc/{pid}/stat")
    if estado.exists():
        try:
            return estado.read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except (OSError, IndexError):
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _esperar_muerte(pid, limite=30.0):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if not _viva(pid):
            return True
        time.sleep(0.1)
    return not _viva(pid)


def _matar_si_es_nuestro(pid, marca):
    """Mata un proceso sobrante de la prueba, solo si su línea de órdenes lleva la marca."""
    try:
        linea = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return
    if marca in linea:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _con_marca_en_el_entorno(marca):
    """Pids vivos cuyo entorno lleva la marca (solo procesos propios, que se pueden leer)."""
    buscada = marca.encode()
    hallados = []
    for entrada in Path("/proc").iterdir():
        if not entrada.name.isdigit() or int(entrada.name) == os.getpid():
            continue
        try:
            if buscada in (entrada / "environ").read_bytes() and _viva(int(entrada.name)):
                hallados.append(int(entrada.name))
        except OSError:
            continue
    return hallados


def _matar_los_de_la_marca(marca):
    for pid in _con_marca_en_el_entorno(marca):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _esperar_pids(ruta, proc, cantidad=2, limite=240.0):
    """Espera a que el archivo traiga los pids; se rinde si el proceso termina antes."""
    def listo():
        return ruta.exists() and len(ruta.read_text().split()) == cantidad

    fin = time.monotonic() + limite
    while time.monotonic() < fin and proc.poll() is None:
        if listo():
            return True
        time.sleep(0.05)
    return listo()


def _leer_pids(proyecto):
    return [int(x) for x in (proyecto / "pids.txt").read_text().split()]


def _orden_del_corredor(proyecto, carpeta, *argumentos):
    orden = [sys.executable, str(RUTA_CORREDOR), "--raiz", str(proyecto), "--salida", str(carpeta)]
    return orden + [str(a) for a in argumentos]


def _leer_con_instantes(proc):
    """Lee la salida del proceso mientras corre; devuelve (registro, hilo)."""
    registro = []

    def leer():
        descriptor = proc.stdout.fileno()
        while True:
            bloque = os.read(descriptor, 4096)
            if not bloque:
                break
            registro.append((time.time(), bloque.decode("utf-8", errors="replace")))

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    return registro, hilo


def _instante_en_que_aparece(registro, texto):
    acumulado = ""
    for instante, trozo in registro:
        acumulado += trozo
        if texto in acumulado:
            return instante
    return None


def _cargar_corredor():
    """El corredor como módulo, para probar sus piezas sin lanzarlo."""
    especificacion = importlib.util.spec_from_file_location("corredor_bajo_prueba", RUTA_CORREDOR)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


LANZADOR_CON_CONSTANTES = """
import importlib.util
import sys

especificacion = importlib.util.spec_from_file_location("corredor_con_constantes", sys.argv[1])
corredor = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(corredor)
for nombre, valor in eval(sys.argv[2]).items():
    setattr(corredor, nombre, valor)
sys.exit(corredor.principal(sys.argv[3:]))
"""

LANZADOR_CON_SENAL = """
import importlib.util
import os
import signal
import sys

especificacion = importlib.util.spec_from_file_location("corredor_con_senal", sys.argv[1])
corredor = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(corredor)
original = corredor.crear_parser


def parser_con_senal():
    os.kill(os.getpid(), getattr(signal, sys.argv[2]))
    return original()


corredor.crear_parser = parser_con_senal
sys.exit(corredor.principal(sys.argv[3:]))
"""


LANZADOR_CON_CORRER_QUE_FALLA = """
import importlib.util
import sys

especificacion = importlib.util.spec_from_file_location("corredor_con_falla", sys.argv[1])
corredor = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(corredor)


def correr_que_falla(*argumentos):
    raise RuntimeError("falla que correr no atrapa")


corredor.correr = correr_que_falla
sys.exit(corredor.principal(sys.argv[2:]))
"""


def _correr_con_constantes(proyecto, constantes, *argumentos, limite=90):
    """Corre el corredor en un proceso aparte, con esas constantes de módulo cambiadas; devuelve (código, pantalla, carpeta)."""
    carpeta = proyecto / "salidas" / uuid.uuid4().hex[:8]
    orden = [sys.executable, "-c", LANZADOR_CON_CONSTANTES, str(RUTA_CORREDOR), repr(constantes),
             "--raiz", str(proyecto), "--salida", str(carpeta)] + [str(a) for a in argumentos]
    codigo, pantalla = _ejecutar(orden, proyecto, limite=limite)
    return codigo, pantalla, carpeta


# -------------------------------------------------- fuentes de los proyectos

ESTADO_QUE_DEJA_A = """
    import os


    def test_deja_estado_global():
        os.environ["MARCA_DE_A"] = "1"
        assert os.environ["MARCA_DE_A"] == "1"
"""

ESTADO_QUE_NO_HEREDA_B = """
    import os


    def test_no_hereda_el_estado():
        assert "MARCA_DE_A" not in os.environ
"""

CON_MARCAS = """
    import time
    from pathlib import Path

    MARCAS = Path(__file__).resolve().parent.parent / "marcas"


    def anotar(nombre):
        MARCAS.mkdir(parents=True, exist_ok=True)
        (MARCAS / nombre).write_text(repr(time.time()))


    def esperar(nombre, limite=240):
        fin = time.monotonic() + limite
        while time.monotonic() < fin and not (MARCAS / nombre).exists():
            time.sleep(0.05)
"""

CON_SEPARADORES = """
    import io
    import os

    from _pytest._io import TerminalWriter


    def sep(caracter, titulo):
        \"\"\"Línea separadora del ancho exacto que usa pytest, con su salto de línea.\"\"\"
        salida = io.StringIO()
        TerminalWriter(salida).sep(caracter, titulo)
        return salida.getvalue()
"""

CONFTEST_RT1 = """
    def pytest_terminal_summary(terminalreporter):
        terminalreporter.write_sep("-", "RT1 cobertura")
        for i in range(10):
            terminalreporter.write_line(f"MARCA_COBERTURA {i}")
"""


def _con_marcas(cuerpo):
    """Fuente de un archivo de pruebas que sabe anotar instantes en <proyecto>/marcas."""
    return _fuente(CON_MARCAS) + "\n\n" + _fuente(cuerpo)


def _con_separadores(cuerpo):
    """Fuente de un archivo de pruebas que sabe armar separadores del ancho exacto de pytest."""
    return _fuente(CON_SEPARADORES) + "\n\n" + _fuente(cuerpo)


def _trabada_con_nieto(marca):
    """Archivo cuya prueba deja un nieto que duerme, anota los dos pids y se queda trabada."""
    return _fuente("""
        import os
        import subprocess
        import sys
        import time
        from pathlib import Path


        def test_trabada():
            nieto = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(100)  # MARCA_DEL_NIETO"])
            ruta = Path(__file__).resolve().parent.parent / "pids.txt"
            ruta.write_text(f"{os.getpid()} {nieto.pid}")
            time.sleep(300)
    """).replace("MARCA_DEL_NIETO", marca)


def _matar_los_de(proyecto, marca):
    """Mata los procesos sobrantes de una prueba (el nieto y el pytest trabado), solo si son nuestros."""
    if (proyecto / "pids.txt").exists():
        pids = _leer_pids(proyecto)
        for pid in pids[1:]:
            _matar_si_es_nuestro(pid, marca)
        for pid in pids[:1]:
            _matar_si_es_nuestro(pid, "test_a_trabada.py")


def _marca(proyecto, nombre):
    return float((proyecto / "marcas" / nombre).read_text())


# ------------------------------------------------------------------- casos

def _crear_archivos(raiz, *nombres):
    for nombre in nombres:
        (raiz / nombre).parent.mkdir(parents=True, exist_ok=True)
        (raiz / nombre).write_text("def test_x():\n    pass\n", encoding="utf-8")


def test_la_recoleccion_solo_acepta_lineas_ruta_py_dos_puntos_cantidad(tmp_path):
    corredor = _cargar_corredor()
    raiz = tmp_path / "raiz"
    _crear_archivos(raiz, "tests/test_a.py", "tests/sub/test_b.py", "tests/test_d.py")
    _crear_archivos(tmp_path, "afuera/test_c.py")
    texto = "\n".join([
        "tests/test_a.py: 3",
        "tests\\sub\\test_b.py: 2",
        "tests/test_a.py: 3",
        "\x1b[32mtests/test_d.py: 4\x1b[0m",
        "tests/test_a.py::test_x: 4",
        " tests/test_a.py: 5",
        "tests/test_a.py: 5 de más",
        "tests/no_existe.py: 7",
        "../afuera/test_c.py: 1",
        "ERROR tests/test_a.py",
        "2 tests collected in 0.01s",
    ]) + "\n"
    # una ruta repetida con la misma cifra cuenta una vez; no cuenta lo que no tiene la forma exacta
    # ni lo que no es un archivo bajo la raíz
    assert corredor.leer_recogidas(texto, raiz) == {"tests/test_a.py": 3, "tests/sub/test_b.py": 2, "tests/test_d.py": 4}
    # una ruta repetida con otra cifra no se puede creer
    assert corredor.leer_recogidas("tests/test_a.py: 3\ntests/test_a.py: 4\n", raiz) is None


def test_si_la_recoleccion_no_puede_lanzarse_se_dice_por_que_y_no_se_cae(tmp_path):
    corredor = _cargar_corredor()
    _crear_archivos(tmp_path, "tests/test_a.py")
    recoleccion = corredor.Recoleccion(tmp_path / "no_existe" / "recoleccion.log", [])
    config = SimpleNamespace(plazo_recoleccion=5.0)
    corredor.recolectar(recoleccion, config, tmp_path, corredor.Parada())
    assert not recoleccion.usable and not recoleccion.interrumpida
    assert recoleccion.motivo.startswith("no se pudo lanzar pytest para recoger las pruebas: "), recoleccion.motivo


RECOLECCIONES = (
    # (código de pytest, salida, ¿sirve?, texto que debe tener el motivo o la nota)
    (0, "tests/test_a.py: 3\n", True, None),
    (2, "tests/test_a.py: 3\n!!!! Interrupted: 1 error during collection !!!!\n", True, "código 2"),
    (2, "tests/test_a.py: 3\n!!!! Interrupted: 2 errors during collection !!!!\n", True, "código 2"),
    (2, "tests/test_a.py: 3\n!!!! Interrupted: stopping after 1 failures !!!!\n", False, "pytest terminó con código 2"),
    (0, "", False, "no listó ninguna prueba"),
    (0, "tests/no_existe.py: 3\n", False, "pytest listó pruebas en tests/no_existe.py, que el corredor no corre"),
    (0, "tests/test_a.py: 3\ntests/test_a.py: 4\n", False, "cifras distintas"),
    (1, "tests/test_a.py: 3\n", False, "pytest terminó con código 1"),
    (3, "tests/test_a.py: 3\n", False, "pytest terminó con código 3"),
    (4, "tests/test_a.py: 3\n", False, "pytest terminó con código 4"),
    (120, "tests/test_a.py: 3\n", False, "pytest terminó con código 120"),
    (-11, "tests/test_a.py: 3\n", False, "señal 11"),
)


@pytest.mark.parametrize("codigo, salida, sirve, texto", RECOLECCIONES,
                         ids=[f"codigo_{c}_{i}" for i, (c, *_) in enumerate(RECOLECCIONES)])
def test_la_recoleccion_sirve_solo_si_llego_al_final_y_listo_pruebas(tmp_path, codigo, salida, sirve, texto):
    corredor = _cargar_corredor()
    _crear_archivos(tmp_path, "tests/test_a.py")
    recogidas, motivo, nota, con_error = corredor.evaluar_recoleccion(codigo, salida, tmp_path)
    assert con_error == [], "estas salidas no traen líneas ERROR de archivos"
    if sirve:
        assert recogidas == {"tests/test_a.py": 3} and motivo is None
        assert (nota is None) if texto is None else (texto in nota), nota
    else:
        assert recogidas is None and nota is None
        assert texto in motivo, motivo


def test_sin_nada_que_recoger_la_recoleccion_sirve_con_cero_pruebas_solo_con_codigo_5(tmp_path):
    corredor = _cargar_corredor()
    _crear_archivos(tmp_path, "tests/test_a.py")
    recogidas, motivo, nota, con_error = corredor.evaluar_recoleccion(5, "", tmp_path)
    assert recogidas == {} and motivo is None and nota is None and con_error == []
    # con código 0 y nada listado, o con código 5 y errores al recoger, sigue sin servir
    assert corredor.evaluar_recoleccion(0, "", tmp_path)[0] is None
    assert corredor.evaluar_recoleccion(5, "!!!! Interrupted: 1 error during collection !!!!\n", tmp_path)[0] is None


def test_los_archivos_con_error_al_recoger_salen_de_las_lineas_error_del_resumen(tmp_path):
    corredor = _cargar_corredor()
    _crear_archivos(tmp_path, "tests/test_a.py", "tests/sub/test_roto.py")
    texto = "\n".join([
        "_____________________ ERROR collecting tests/sub/test_roto.py ______________________",
        "ERROR tests/sub/test_roto.py",
        "ERROR tests\\test_a.py - ImportError: no se pudo",
        "ERROR tests/sub/test_roto.py",
        "ERROR tests/no_existe.py",
        "ERROR collecting tests/test_a.py",
        "FAILED tests/test_a.py::test_x",
        "!!!! Interrupted: 2 errors during collection !!!!",
    ]) + "\n"
    assert corredor.leer_errores_al_recoger(texto, tmp_path) == ["tests/sub/test_roto.py", "tests/test_a.py"]
    # los errores al recoger se deciden por el texto de pytest: con código 2 o con un 0 forzado por un conftest
    recogidas = "tests/test_a.py: 3\n"
    assert corredor.evaluar_recoleccion(2, recogidas + texto, tmp_path)[3] == ["tests/sub/test_roto.py", "tests/test_a.py"]
    asi_con_cero = corredor.evaluar_recoleccion(0, recogidas + texto, tmp_path)
    assert asi_con_cero[3] == ["tests/sub/test_roto.py", "tests/test_a.py"] and "código 0" in asi_con_cero[2], asi_con_cero
    # sin la línea «Interrupted: N errors» (como con --continue-on-collection-errors) las líneas ERROR siguen contando
    sin_cuenta = "\n".join(l for l in texto.split("\n") if "Interrupted" not in l)
    assert corredor.evaluar_recoleccion(0, recogidas + sin_cuenta, tmp_path)[3] == ["tests/sub/test_roto.py", "tests/test_a.py"]
    # un 1 sigue sin servir: la recolección no llegó al final como debía
    assert corredor.evaluar_recoleccion(1, recogidas + sin_cuenta, tmp_path)[0] is None


def test_los_errores_que_pytest_cuenta_y_no_nombra_quedan_sin_atribuir(tmp_path):
    corredor = _cargar_corredor()
    _crear_archivos(tmp_path, "tests/test_a.py", "tests/sub/otro.txt")
    resumen = "ERROR tests/sub - ModuleNotFoundError: x\nERROR tests/test_a.py\nERROR collecting tests/test_a.py\n"
    # tres errores contados: una carpeta, un archivo que se corre y uno que pytest no nombra
    contados = resumen + "!!!! Interrupted: 3 errors during collection !!!!\n"
    assert corredor.errores_al_recoger_sin_archivo(contados, tmp_path) == ["tests/sub", "1 error sin nombre"]
    assert corredor.errores_al_recoger_sin_archivo(contados.replace("3 errors", "2 errors"), tmp_path) == ["tests/sub"]
    # sin la cuenta de pytest (--continue-on-collection-errors) las líneas ERROR bastan para saber qué no se corre
    assert corredor.errores_al_recoger_sin_archivo(resumen, tmp_path) == ["tests/sub"]
    assert corredor.errores_al_recoger_sin_archivo("ERROR tests/test_a.py\n", tmp_path) == []
    assert corredor.errores_al_recoger_sin_archivo("tests/test_a.py: 3\n", tmp_path) == []
    # un archivo que existe pero no es .py tampoco se corre
    solo_el_txt = "ERROR tests/sub/otro.txt - x\n!!!! Interrupted: 1 error during collection !!!!\n"
    assert corredor.errores_al_recoger_sin_archivo(solo_el_txt, tmp_path) == ["tests/sub/otro.txt"]


def test_el_veredicto_solo_es_completo_si_no_hubo_problemas_y_se_comprobo():
    corredor = _cargar_corredor()
    assert corredor.veredicto(0, 0, [], True) == "TODAS LAS PRUEBAS PASARON"
    assert corredor.veredicto(0, 0, [], False) == "TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS"
    con_fallas = "HAY PRUEBAS QUE FALLARON O ARCHIVOS CON PROBLEMA"
    for comprobado in (True, False):
        assert corredor.veredicto(1, 0, [], comprobado) == con_fallas
        assert corredor.veredicto(0, 1, [], comprobado) == con_fallas
        assert corredor.veredicto(0, 0, ["archivo"], comprobado) == con_fallas
    assert corredor.codigo_de_salida(0, 0, [], True) == 0
    assert corredor.codigo_de_salida(0, 0, [], False) == 1
    assert corredor.codigo_de_salida(1, 0, [], True) == 1
    # todo lo pedido omitido entero: ninguna falló y ninguna corrió; solo vale si se comprobó y nada falló
    todo_omitido = "NINGUNA PRUEBA FALLÓ; NO CORRIÓ NINGUNA: TODO LO PEDIDO SE OMITIÓ ENTERO"
    assert corredor.veredicto(0, 0, [], True, True) == todo_omitido and corredor.codigo_de_salida(0, 0, [], True, True) == 0
    assert corredor.veredicto(0, 0, [], False, True) == "TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS"
    assert corredor.veredicto(1, 0, [], True, True) == con_fallas and corredor.codigo_de_salida(0, 0, ["a"], True, True) == 1


def test_la_completitud_solo_se_comprueba_si_la_recoleccion_sirvio_y_ningun_archivo_quedo_sin_comparar():
    corredor = _cargar_corredor()
    sirve = SimpleNamespace(usable=True, sin_archivo=[])
    no_sirve = SimpleNamespace(usable=False, sin_archivo=[])
    con_errores_sin_archivo = SimpleNamespace(usable=True, sin_archivo=["tests/sub"])
    limpio = corredor.Resultado("tests/test_a.py", 0.0, 0, recogidas=1)
    sin_comparar = corredor.Resultado("tests/test_b.py", 0.0, 0, recogidas=0)
    sin_comparar.sin_listar, sin_comparar.terminadas = True, 2
    sin_pruebas = corredor.Resultado("tests/test_c.py", 0.0, 2, recogidas=0)
    sin_pruebas.sin_listar = True
    assert corredor.completitud_comprobada([limpio], sirve)
    assert not corredor.completitud_comprobada([limpio], no_sirve)
    assert not corredor.completitud_comprobada([limpio], con_errores_sin_archivo)
    assert not corredor.completitud_comprobada([limpio, sin_comparar], sirve)
    # un archivo que no se pudo listar y no trajo pruebas no deja nada sin comparar (ya es un problema por sí solo)
    assert corredor.completitud_comprobada([limpio, sin_pruebas], sirve)


def test_una_prueba_cuenta_una_sola_vez_aunque_aparezca_dos_veces_en_el_xml(tmp_path):
    corredor = _cargar_corredor()
    xml = tmp_path / "x.xml"
    xml.write_text("""<testsuites><testsuite name="pytest">
        <testcase classname="tests.test_x" name="test_a"/>
        <testcase classname="tests.test_x" name="test_a"><error message="failed on teardown with X"/></testcase>
        <testcase classname="tests.test_x" name="test_b[1]"/>
        <testcase classname="tests.test_x.TestC" name="test_b[1]"/>
        <testcase classname="" name="tests.test_y"><skipped message="collection skipped"/></testcase>
        <testcase time="0.0"/>
    </testsuite></testsuites>""", encoding="utf-8")
    resultado = corredor.Resultado("tests/test_x.py", 0.0, 1, recogidas=5)
    resultado.leido = corredor.leer_xml(resultado, xml)
    assert resultado.leido
    # distintas por (classname, name); no cuentan el testcase sin name ni el módulo omitido al recoger
    assert resultado.terminadas == 3, resultado.terminadas
    assert resultado.faltan == 2
    # sin XML legible no terminó ninguna; sin recolección no hay con qué comparar
    assert corredor.Resultado("tests/test_x.py", 0.0, 1, recogidas=5).faltan == 5
    assert corredor.Resultado("tests/test_x.py", 0.0, 1, recogidas=None).faltan == 0
    resultado.recogidas = 2
    assert resultado.faltan == 0, "terminar más pruebas de las recogidas no es un problema"


def test_los_textos_de_lo_que_falta_van_en_singular_y_plural():
    corredor = _cargar_corredor()

    def texto(recogidas, terminadas):
        resultado = corredor.Resultado("tests/test_x.py", 0.0, 0, recogidas=recogidas)
        resultado.leido, resultado.terminadas = True, terminadas
        return corredor.texto_de_faltantes(resultado)

    assert texto(3, 1) == "pytest recogió 3 pruebas y solo 1 terminó (faltan 2)"
    assert texto(4, 2) == "pytest recogió 4 pruebas y solo 2 terminaron (faltan 2)"
    assert texto(3, 2) == "pytest recogió 3 pruebas y solo 2 terminaron (falta 1)"
    assert texto(1, 0) == "pytest recogió 1 prueba y ninguna terminó (falta 1)"


def test_aislamiento_por_archivo(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": ESTADO_QUE_DEJA_A,
                                    "test_b.py": ESTADO_QUE_NO_HEREDA_B})
    # control: en un solo proceso el segundo archivo hereda el estado y cae
    codigo, salida = _ejecutar([sys.executable, "-m", "pytest", "tests/test_a.py", "tests/test_b.py",
                                "-q", "-p", "no:cacheprovider"], proyecto)
    assert codigo != 0 and "test_no_hereda_el_estado" in salida, salida
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 0)


def test_falla_se_informa_con_su_id(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_f.py": """
        def test_bien():
            pass


        def test_mala():
            assert 1 == 2


        def test_otra_bien():
            pass
    """})
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 1, 0, 0, 0)
    assert _cifras(corrida.pantalla) == (2, 1, 0, 0, 0)
    # una prueba que falla terminó: no cuenta como faltante
    assert _completitud(corrida.informe) == (3, 3, 0) and _completitud(corrida.pantalla) == (3, 3, 0)
    fallaron = _seccion(corrida.informe, "Fallaron:")
    assert len(fallaron) == 1 and fallaron[0].startswith("tests/test_f.py::test_mala"), fallaron
    assert "HAY PRUEBAS QUE FALLARON" in corrida.informe
    assert "TODAS LAS PRUEBAS PASARON" not in corrida.pantalla
    assert re.search(r"^\[1/1\] tests/test_f\.py$", corrida.pantalla, re.M), corrida.pantalla
    # con una sola cifra, los textos van en singular
    assert "Se va a correr 1 archivo de pruebas" in corrida.pantalla, corrida.pantalla
    assert re.search(r"^    2 pasaron, 1 falló, 0 errores, 0 omitidas \(", corrida.pantalla, re.M), corrida.pantalla
    assert "\nEl archivo más lento:\n" in corrida.informe, corrida.informe


def test_error_de_coleccion_no_pasa(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_roto.py": "import modulo_que_no_existe_xyz\n\n\ndef test_x():\n    pass\n",
        "test_b_vacio.py": "VALOR = 1\n",
        "test_c_bueno.py": "def test_ok():\n    pass\n",
    })
    corrida = _correr(proyecto)
    pasaron, fallaron, errores, omitidas, problemas = _cifras(corrida.informe)
    assert corrida.codigo == 1, corrida.pantalla
    assert (pasaron, fallaron, omitidas) == (1, 0, 0)
    assert errores >= 1
    assert problemas == 2, corrida.informe
    con_problema = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "test_a_roto.py" in con_problema and "test_b_vacio.py" in con_problema
    assert "TODAS LAS PRUEBAS PASARON" not in corrida.informe
    assert "TODAS LAS PRUEBAS PASARON" not in corrida.pantalla
    # repartido: el registro de cada archivo y las últimas líneas del que tiene problema también quedan
    repartido = _correr(proyecto, "--procesos", "2")
    assert repartido.codigo == 1, repartido.pantalla
    registro = (repartido.carpeta / "test_a_roto.log").read_text(encoding="utf-8")
    assert "test session starts" in registro and "ModuleNotFoundError" in registro, registro
    assert "ModuleNotFoundError" in repartido.pantalla.split("RESULTADO DE LAS PRUEBAS")[0], repartido.pantalla


def test_omitida_con_su_motivo(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_o.py": """
        import pytest


        def test_ok():
            pass


        @pytest.mark.skip(reason="falta la base de referencia X")
        def test_omitida():
            pass
    """})
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (1, 0, 0, 1, 0)
    omitidas = _seccion(corrida.informe, "Omitidas, con su motivo:")
    assert omitidas == ["tests/test_o.py::test_omitida - falta la base de referencia X"], omitidas
    assert "TODAS LAS PRUEBAS PASARON" in corrida.informe


def test_un_skip_de_modulo_omite_el_archivo_entero_y_no_es_un_problema(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_skip_de_modulo.py": """
            import pytest

            pytest.skip("faltan las bases de referencia", allow_module_level=True)


            def test_x():
                pass
        """,
        "test_b_importorskip.py": """
            import pytest

            pytest.importorskip("modulo_opcional_que_no_esta_xyz")


            def test_x():
                pass
        """,
        "test_c_bueno.py": "def test_ok():\n    pass\n",
        "test_d_vacio.py": "VALOR = 1\n",
    })
    corrida = _correr(proyecto)
    # el archivo vacío es el control: sin pruebas recogidas y sin omitidas sigue siendo un problema
    assert _cifras(corrida.informe) == (1, 0, 0, 2, 1), corrida.informe
    assert corrida.codigo == 1, corrida.pantalla
    omitidas = _seccion(corrida.informe, "Omitidas, con su motivo:")
    assert omitidas[0] == "tests/test_a_skip_de_modulo.py - faltan las bases de referencia", omitidas
    assert omitidas[1].startswith("tests/test_b_importorskip.py - could not import "
                                  "'modulo_opcional_que_no_esta_xyz'"), omitidas
    assert "collection skipped" not in corrida.informe
    problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "tests/test_d_vacio.py - pytest terminó con código 5" in problemas, problemas
    assert "test_a_skip_de_modulo" not in problemas and "test_b_importorskip" not in problemas, problemas
    assert corrida.pantalla.count("archivo omitido entero") == 2, corrida.pantalla


def test_un_archivo_cortado_a_mitad_o_sin_pruebas_con_codigo_0_no_pasa(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_cortado.py": """
            import pytest


            def test_antes():
                pass


            def test_corta():
                pytest.exit("alto con codigo 0", returncode=0)


            def test_despues():
                assert False, "nunca corre"
        """,
        "test_b_sin_pruebas.py": "VALOR = 1\n",
        "test_c_bueno.py": "def test_ok():\n    pass\n",
    }, conftest="""
        import pytest


        @pytest.hookimpl(trylast=True)
        def pytest_sessionfinish(session, exitstatus):
            if session.exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
                session.exitstatus = 0
    """)
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 2), corrida.informe
    problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert ("tests/test_a_cortado.py - pytest se cortó a mitad: una prueba empezó y no terminó") in problemas, problemas
    assert "tests/test_b_sin_pruebas.py - pytest terminó con 0 pero no corrió ninguna prueba" in problemas, problemas
    for texto in (corrida.informe, corrida.pantalla):
        assert "TODAS LAS PRUEBAS PASARON" not in texto


def test_silencio_detiene_el_archivo_y_sigue(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_trabada.py": "import time\n\n\ndef test_trabada():\n    time.sleep(300)\n",
        "test_b_siguiente.py": "def test_ok():\n    pass\n",
    })
    corrida = _correr(proyecto, "--silencio-max", "15", limite=300)
    assert corrida.segundos < 280, "el corredor esperó a la prueba trabada (300 [s])"
    assert corrida.codigo == 1, corrida.pantalla
    assert re.search(r"detenido: \d+ \[s\] sin salida", corrida.pantalla), corrida.pantalla
    assert _cifras(corrida.informe) == (1, 0, 0, 0, 1)
    # el archivo detenido no dejó XML: su prueba recogida cuenta como faltante
    assert _completitud(corrida.informe) == (2, 1, 1), corrida.informe
    problemas = _seccion(corrida.informe, "Archivos con problema:")
    assert "test_a_trabada.py" in problemas[0] and "detenido" in problemas[0], problemas
    assert any("test_trabada" in linea for linea in problemas), "faltan las últimas líneas"
    assert "tests/test_b_siguiente.py" in corrida.pantalla


def test_el_silencio_se_mide_en_bytes_y_no_en_lineas(tmp_path):
    corredor = _cargar_corredor()
    ejecucion = corredor.Ejecucion("tests/test_x.py", tmp_path / "x.log", tmp_path / "x.xml")
    ejecucion.proc = SimpleNamespace(stdout=io.BytesIO(b"sin salto de linea"))
    ejecucion.ultima_salida = -1.0
    with open(tmp_path / "x.log", "wb") as registro:
        ejecucion._leer(registro)
    assert ejecucion.ultima_salida > 0, "una salida sin salto de línea no cuenta como actividad"
    assert (tmp_path / "x.log").read_bytes() == b"sin salto de linea"


@SOLO_POSIX
def test_el_nieto_muere_con_el_grupo(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a_trabada.py": _trabada_con_nieto("NIETO_DE_LA_PRUEBA")})
    try:
        corrida = _correr(proyecto, "--silencio-max", "15", limite=300)
        hijo, nieto = _leer_pids(proyecto)
        assert corrida.codigo == 1, corrida.pantalla
        assert _esperar_muerte(hijo), "el proceso de pytest sigue vivo"
        assert _esperar_muerte(nieto), "el nieto sigue vivo: no se detuvo el grupo"
    finally:
        _matar_los_de(proyecto, "NIETO_DE_LA_PRUEBA")


def test_los_intrusos_corren_al_final_solos_y_de_uno_en_uno(tmp_path):
    # tres normales a la vez (el corto no termina hasta ver empezar a los otros dos) y dos intrusos
    proyecto = _proyecto(tmp_path, {
        "test_a_largo.py": _con_marcas("""
            def test_largo():
                anotar("a_inicio")
                esperar("b_fin")
                esperar("i1_inicio", 4)
                anotar("a_fin")
        """),
        "test_b_corto.py": _con_marcas("""
            def test_corto():
                anotar("b_inicio")
                esperar("a_inicio")
                esperar("c_inicio")
                anotar("b_fin")
        """),
        "test_c_medio.py": _con_marcas("""
            def test_medio():
                anotar("c_inicio")
                esperar("b_fin")
                anotar("c_fin")
        """),
        "test_i1_primero.py": _con_marcas("""
            # prueba que escribe un intruso en el arbol
            def test_primero():
                anotar("i1_inicio")
                esperar("i2_inicio", 4)
                anotar("i1_fin")
        """),
        "test_i2_segundo.py": _con_marcas("""
            # prueba que escribe un intruso en el arbol
            def test_segundo():
                anotar("i2_inicio")
                anotar("i2_fin")
        """),
    })
    corrida = _correr(proyecto, "--procesos", "3", limite=300)
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (5, 0, 0, 0, 0)
    assert _marca(proyecto, "a_inicio") < _marca(proyecto, "b_fin"), "los normales no corrieron a la vez"
    assert _marca(proyecto, "c_inicio") < _marca(proyecto, "b_fin"), "los normales no corrieron a la vez"
    ultimo_normal = max(_marca(proyecto, n) for n in ("a_fin", "b_fin", "c_fin"))
    assert _marca(proyecto, "i1_inicio") >= ultimo_normal, "el primer intruso empezó antes de que terminaran los normales"
    assert _marca(proyecto, "i1_inicio") < _marca(proyecto, "i2_inicio"), "los intrusos no van en orden alfabético"
    assert _marca(proyecto, "i2_inicio") >= _marca(proyecto, "i1_fin"), "los intrusos corrieron a la vez"


def test_la_salida_llega_en_vivo_de_verdad(tmp_path):
    # la prueba dormida no termina hasta que este caso ve, en la pantalla del corredor, la línea PASSED de la primera
    # y el nombre de la que está corriendo; si la salida llegara solo al final del archivo, las marcas no se
    # escribirían y la prueba dormida fallaría por su plazo
    proyecto = _proyecto(tmp_path, {"test_vivo.py": _con_marcas("""
        def test_rapida():
            assert True


        def test_dormida():
            esperar("vista_la_pasada", 20)
            esperar("visto_el_nombre", 20)
            assert (MARCAS / "vista_la_pasada").exists() and (MARCAS / "visto_el_nombre").exists()
            anotar("dormida_fin")
    """)})
    marcas = proyecto / "marcas"
    marcas.mkdir()
    orden = [sys.executable, str(RUTA_CORREDOR), "--raiz", str(proyecto),
             "--salida", str(proyecto / "salida")]
    proc = _lanzar(orden, proyecto)
    registro = []

    def leer():
        descriptor = proc.stdout.fileno()
        while True:
            bloque = os.read(descriptor, 4096)
            if not bloque:
                break
            registro.append(bloque.decode("utf-8", errors="replace"))
            visto = "".join(registro)
            if "test_rapida PASSED" in visto:
                (marcas / "vista_la_pasada").write_text("1")
            if "tests/test_vivo.py::test_dormida" in visto:
                (marcas / "visto_el_nombre").write_text("1")

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    try:
        proc.wait(timeout=240)
    except subprocess.TimeoutExpired:
        _detener(proc)
        pytest.fail("venció el tiempo")
    hilo.join(timeout=60)
    pantalla = "".join(registro)
    assert (marcas / "vista_la_pasada").exists(), "la línea PASSED llegó junto con el final del archivo"
    assert (marcas / "visto_el_nombre").exists(), "no se vio la prueba que está corriendo"
    assert (marcas / "dormida_fin").exists() and proc.returncode == 0, pantalla
    assert pantalla.count("tests/test_vivo.py::test_dormida") == 1, pantalla


def test_offscreen_se_fuerza(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_qt.py": """
        import os


        def test_plataforma():
            assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
    """})
    corrida = _correr(proyecto, entorno={"QT_QPA_PLATFORM": "xcb"})
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (1, 0, 0, 0, 0)


def test_cifras_iguales_a_la_suma_de_los_xml(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_m1.py": """
            import pytest


            def test_a():
                pass


            def test_b():
                pass


            def test_c():
                pass


            @pytest.mark.skip(reason="motivo de m1")
            def test_d():
                pass
        """,
        "test_m2.py": """
            import pytest


            @pytest.mark.parametrize("n", range(4))
            def test_param(n):
                assert n >= 0


            def test_falla():
                assert False
        """,
        "test_m3.py": "import time\n\n\ndef test_unica():\n    time.sleep(1.5)\n",
    })
    en_vivo = _correr(proyecto)
    repartido = _correr(proyecto, "--procesos", "2")
    for corrida in (en_vivo, repartido):
        suma = [0, 0, 0, 0]
        for xml in sorted(corrida.carpeta.glob("*.xml")):
            for suite in ET.parse(xml).getroot().iter("testsuite"):
                suma[0] += int(suite.get("tests"))
                suma[1] += int(suite.get("failures"))
                suma[2] += int(suite.get("errors"))
                suma[3] += int(suite.get("skipped"))
        esperado = (suma[0] - suma[1] - suma[2] - suma[3], suma[1], suma[2], suma[3], 0)
        assert esperado == (8, 1, 0, 1, 0)
        assert _cifras(corrida.informe) == esperado
        assert _cifras(corrida.pantalla) == esperado
        assert _completitud(corrida.informe) == (suma[0], suma[0], 0)
        assert corrida.codigo == 1
        assert "Se van a correr 3 archivos de pruebas" in corrida.pantalla
        lentos = re.findall(r"^\s+\d+\.\s+([0-9.]+) \[s\]  tests/test_m\d\.py$", corrida.informe, re.M)
        assert "\nLos 3 archivos más lentos:\n" in corrida.informe
        duraciones = [float(x) for x in lentos]
        assert len(duraciones) == 3 and duraciones == sorted(duraciones, reverse=True), corrida.informe
        assert len(set(duraciones)) > 1, "las tres duraciones salieron iguales: no se puede ver el orden"
    assert "repartido en 2 procesos" in repartido.informe
    assert "en vivo" in en_vivo.informe
    assert re.search(r"^\[\d/3\] tests/test_m\d\.py: \d+ (pasaron|pasó), \d+ (fallaron|falló)",
                     repartido.pantalla, re.M), repartido.pantalla


def test_argumentos(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a():\n    pass\n",
        "test_b.py": "def test_b():\n    assert False\n",
        "ayuda.py": "VALOR = 1\n",
        "datos.txt": "no es un archivo de pruebas\n",
    })
    solo_a = _correr(proyecto, "tests/test_a.py")
    assert solo_a.codigo == 0, solo_a.pantalla
    assert _cifras(solo_a.informe) == (1, 0, 0, 0, 0)
    assert sorted(p.name for p in solo_a.carpeta.glob("*.log")) == ["recoleccion.log", "test_a.log"]
    assert "test_b" not in solo_a.pantalla
    repetido = _correr(proyecto, "tests/test_a.py", "tests/test_a.py")
    assert _cifras(repetido.informe) == (1, 0, 0, 0, 0), "un archivo repetido corrió dos veces"
    assert repetido.pantalla.count("[1/1] tests/test_a.py") == 1 and "[2/" not in repetido.pantalla
    for malo in ("tests/no_existe.py", "tests/datos.txt"):
        corrida = _correr(proyecto, "tests/test_a.py", malo)
        assert corrida.codigo == 2, corrida.pantalla
        assert malo in corrida.pantalla
        assert not corrida.carpeta.exists(), "no debía crear la carpeta de resultados"
        assert "pasaron" not in corrida.pantalla
    # el nombre no tiene que empezar por test_: pytest decide si el archivo trae pruebas
    sin_pruebas = _correr(proyecto, "tests/ayuda.py")
    assert sin_pruebas.codigo == 1, sin_pruebas.pantalla
    assert "tests/ayuda.py - pytest terminó con código 5" in sin_pruebas.informe, sin_pruebas.informe
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    (afuera / "test_afuera.py").write_text("def test_afuera():\n    pass\n", encoding="utf-8")
    fuera = _correr(proyecto, str(afuera / "test_afuera.py"))
    assert fuera.codigo == 2 and "no está bajo la raíz" in fuera.pantalla, fuera.pantalla
    assert not fuera.carpeta.exists()
    ayuda = _correr(proyecto, "--help", salida=None)
    assert ayuda.codigo == 0
    assert "Uso:" in ayuda.pantalla and "usage:" not in ayuda.pantalla
    for opcion in ("--procesos", "--silencio-max", "--aviso-cada", "--plazo-recoleccion", "--salida", "--raiz"):
        assert opcion in ayuda.pantalla
    texto = " ".join(ayuda.pantalla.split())
    # cada valor por omisión va atado a su opción (el 60 y el 600 comparten texto)
    assert re.search(r"--silencio-max SEG[^(]*\(por omisión 600\)", texto), texto
    assert re.search(r"--aviso-cada SEG[^(]*\(por omisión 60\)", texto), texto
    assert re.search(r"--plazo-recoleccion SEG[^(]*\(por omisión 600\)", texto), texto
    assert "3 si el corredor tuvo un error interno" in texto and "130 si se interrumpe" in texto, texto
    assert "se detiene el grupo de procesos de un archivo" in texto, texto


ARGUMENTOS_INVALIDOS = (
    ("--procesos", "0"), ("--procesos", "-3"), ("--procesos", "abc"),
    ("--silencio-max", "0"), ("--silencio-max", "-5"), ("--silencio-max", "nan"), ("--silencio-max", "inf"),
    ("--silencio-max", "-inf"), ("--aviso-cada", "0"), ("--aviso-cada", "nan"), ("--aviso-cada", "inf"),
    ("--plazo-recoleccion", "0"), ("--plazo-recoleccion", "-5"), ("--plazo-recoleccion", "nan"),
    ("--plazo-recoleccion", "inf"), ("--plazo-recoleccion", "abc"),
)


@pytest.mark.parametrize("argumentos", ARGUMENTOS_INVALIDOS, ids=[" ".join(a) for a in ARGUMENTOS_INVALIDOS])
def test_los_argumentos_invalidos_dan_codigo_2_sin_correr_nada(tmp_path, argumentos):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    corrida = _correr(proyecto, *argumentos)
    assert corrida.codigo == 2, corrida.pantalla
    assert not corrida.carpeta.exists(), "no debía crear la carpeta de resultados"
    assert "Traceback" not in corrida.pantalla and "pasaron" not in corrida.pantalla


def test_una_raiz_que_no_existe_da_codigo_2(tmp_path):
    codigo, salida = _ejecutar([sys.executable, str(RUTA_CORREDOR), "--raiz", str(tmp_path / "no_existe")], tmp_path)
    assert codigo == 2, salida
    assert "la raíz no existe" in salida and "Traceback" not in salida


def test_la_carpeta_de_resultados_que_no_se_puede_preparar_da_un_mensaje_y_codigo_2(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    archivo = tmp_path / "es_un_archivo.txt"
    archivo.write_text("contenido", encoding="utf-8")
    # la carpeta pedida cuelga de un archivo: no se puede crear
    corrida = _correr(proyecto, "--salida", archivo / "resultados", salida=None, aparte=True)
    assert corrida.codigo == 2, corrida.errores
    assert "no se pudo crear la carpeta de resultados" in corrida.errores, corrida.errores
    assert "Traceback" not in corrida.errores and "INTERRUMPIDA" not in corrida.pantalla
    assert corrida.pantalla == ""


@SOLO_POSIX
@NO_ROOT
def test_una_carpeta_sin_permiso_de_escritura_da_un_mensaje_y_codigo_2_sin_informe(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    destino = proyecto / "resultados_nuevos"
    # con la máscara 222 la carpeta recién creada queda sin permiso de escritura
    corrida = _correr(proyecto, "--salida", destino, salida=None, aparte=True, mascara=0o222)
    assert corrida.codigo == 2, corrida.errores
    assert "no se puede escribir en la carpeta de resultados" in corrida.errores, corrida.errores
    assert "Traceback" not in corrida.errores
    assert "INTERRUMPIDA" not in corrida.pantalla and "RESULTADO DE LAS PRUEBAS" not in corrida.pantalla
    assert not destino.exists(), "debía quitar la carpeta vacía que había creado"


def test_si_la_ruta_de_resultados_lleva_una_variable_de_entorno_se_rechaza(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    literal = str(proyecto / "con_$VAR_DE_PRUEBA_XYZ")
    corrida = _correr(proyecto, "--salida", literal, salida=None, aparte=True,
                      entorno={"VAR_DE_PRUEBA_XYZ": "DESVIADA"})
    assert corrida.codigo == 2, corrida.errores
    assert "$" in corrida.errores and "con_$VAR_DE_PRUEBA_XYZ" in corrida.errores, corrida.errores
    assert not (proyecto / "con_$VAR_DE_PRUEBA_XYZ").exists() and not (proyecto / "con_DESVIADA").exists()


def test_carpeta_de_resultados_por_omision(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a():\n    pass\n",
        "test_b.py": "def test_b():\n    pass\n",
    })
    corrida = _correr(proyecto, salida=None)
    assert corrida.codigo == 0, corrida.pantalla
    carpetas = list((proyecto / "resultados_pruebas").iterdir())
    assert len(carpetas) == 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}", carpetas[0].name), carpetas
    nombres = sorted(p.name for p in carpetas[0].iterdir())
    assert nombres == ["informe.txt", "recoleccion.log", "test_a.log", "test_a.xml", "test_b.log", "test_b.xml"], nombres
    assert str(carpetas[0]) in (carpetas[0] / "informe.txt").read_text(encoding="utf-8")
    assert "test session starts" in (carpetas[0] / "test_a.log").read_text(encoding="utf-8")


def test_una_segunda_corrida_en_la_misma_carpeta_no_lee_los_resultados_de_la_primera(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    comun = proyecto / "resultados"
    primera = _correr(proyecto, "--salida", comun, salida=None)
    assert primera.codigo == 0, primera.pantalla
    assert (comun / "test_a.xml").exists()
    # la segunda sale con 0 sin dejar XML: si leyera el de la primera diría que todo pasó
    (proyecto / "tests" / "test_a.py").write_text("import os\n\n# sale con 0 al importarse, sin dejar XML\nos._exit(0)\n",
                                                  encoding="utf-8")
    segunda = _correr(proyecto, "--salida", comun, salida=None)
    assert segunda.codigo == 1, segunda.pantalla
    assert "TODAS LAS PRUEBAS PASARON" not in segunda.pantalla
    assert str((proyecto / "resultados_2").resolve()) in segunda.pantalla, segunda.pantalla
    informe = (proyecto / "resultados_2" / "informe.txt").read_text(encoding="utf-8")
    assert "sin XML legible" in informe and _cifras(informe) == (0, 0, 0, 0, 1), informe
    assert "TODAS LAS PRUEBAS PASARON" in (comun / "informe.txt").read_text(encoding="utf-8")
    # una carpeta vacía que ya reservó otro tampoco se comparte
    (proyecto / "tests" / "test_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    reservada = proyecto / "reservada"
    reservada.mkdir()
    tercera = _correr(proyecto, "--salida", reservada, salida=None)
    assert tercera.codigo == 0 and str((proyecto / "reservada_2").resolve()) in tercera.pantalla, tercera.pantalla
    assert list(reservada.iterdir()) == [], "usó una carpeta que ya había reservado otro"


def test_dos_corridas_a_la_vez_no_comparten_la_carpeta_de_resultados(tmp_path):
    uno = _proyecto(tmp_path / "uno", {"test_x.py": "def test_x():\n    pass\n"})
    otro = _proyecto(tmp_path / "otro", {"test_x.py": "def test_x():\n    assert False\n"})
    comun = tmp_path / "comun"
    procesos = [_lanzar(_orden_del_corredor(p, comun), p) for p in (uno, otro)]
    pantallas = [_esperar(proc, 240) for proc in procesos]
    carpetas = [re.search(r"Los resultados quedan en (.+)", p).group(1) for p in pantallas]
    assert carpetas[0] != carpetas[1], carpetas
    assert sorted(procesos[i].returncode for i in (0, 1)) == [0, 1]
    for p, carpeta, proc in zip((uno, otro), carpetas, procesos):
        informe = (Path(carpeta) / "informe.txt").read_text(encoding="utf-8")
        esperado = (1, 0, 0, 0, 0) if proc.returncode == 0 else (0, 1, 0, 0, 0)
        assert _cifras(informe) == esperado, informe


@SOLO_POSIX
@pytest.mark.parametrize("nombre_senal", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_una_interrupcion_deja_el_informe_parcial_y_nada_vivo(tmp_path, nombre_senal):
    marca = f"NIETO_DE_{nombre_senal}"
    proyecto = _proyecto(tmp_path, {"test_a_trabada.py": _trabada_con_nieto(marca),
                                    "test_b_pendiente.py": "def test_ok():\n    pass\n"})
    carpeta = proyecto / "salida"
    proc = _lanzar(_orden_del_corredor(proyecto, carpeta), proyecto)
    try:
        assert _esperar_pids(proyecto / "pids.txt", proc), "la prueba trabada no llegó a arrancar"
        hijo, nieto = _leer_pids(proyecto)
        proc.send_signal(getattr(signal, nombre_senal))
        pantalla = _esperar(proc, 240)
        assert proc.returncode == 130, pantalla
        assert "interrumpida" in pantalla.lower()
        informe = (carpeta / "informe.txt").read_text(encoding="utf-8")
        lineas = informe.splitlines()
        assert "INTERRUMPIDA" in lineas[0], lineas[0]
        assert "VEREDICTO: CORRIDA INTERRUMPIDA, SIN VEREDICTO" in lineas, lineas
        assert "TODAS LAS PRUEBAS PASARON" not in informe
        assert _esperar_muerte(hijo), "el proceso de pytest sigue vivo"
        assert _esperar_muerte(nieto), "el nieto sigue vivo"
    finally:
        _detener(proc)
        _matar_los_de(proyecto, marca)


@SOLO_POSIX
@pytest.mark.parametrize("nombre_senal", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_una_senal_antes_de_empezar_da_130_con_su_informe_y_sin_traza(tmp_path, nombre_senal):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    carpeta = proyecto / "salida"
    orden = [sys.executable, "-c", LANZADOR_CON_SENAL, str(RUTA_CORREDOR), nombre_senal,
             "--raiz", str(proyecto), "--salida", str(carpeta)]
    codigo, salida = _ejecutar(orden, proyecto)
    assert codigo == 130, salida
    assert "Traceback" not in salida, salida
    assert "INTERRUMPIDA" in (carpeta / "informe.txt").read_text(encoding="utf-8")


@SOLO_POSIX
def test_un_sighup_heredado_como_ignorado_se_respeta(tmp_path):
    # como con nohup: la corrida debe seguir aunque llegue SIGHUP
    proyecto = _proyecto(tmp_path, {"test_a_espera.py": _con_marcas("""
        def test_espera():
            anotar("a_inicio")
            esperar("liberada", 60)
    """)})
    orden = _orden_del_corredor(proyecto, proyecto / "salida")
    proc = _lanzar(orden, proyecto, ignorando=("SIGHUP",))
    try:
        fin = time.monotonic() + 240
        while not (proyecto / "marcas" / "a_inicio").exists() and time.monotonic() < fin and proc.poll() is None:
            time.sleep(0.05)
        proc.send_signal(signal.SIGHUP)
        time.sleep(1.5)
        assert proc.poll() is None, "el corredor se interrumpió con un SIGHUP que se había heredado como ignorado"
        (proyecto / "marcas" / "liberada").write_text("1")
        pantalla = _esperar(proc, 240)
        assert proc.returncode == 0, pantalla
    finally:
        _detener(proc)


@SOLO_POSIX
def test_dos_interrupciones_seguidas_no_dejan_nada_vivo(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a_trabada.py": """
        import os
        import signal
        import time
        from pathlib import Path


        def test_trabada_que_ignora_sigterm():
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            (Path(__file__).resolve().parent.parent / "pids.txt").write_text(str(os.getpid()))
            time.sleep(300)
    """})
    carpeta = proyecto / "salida"
    proc = _lanzar(_orden_del_corredor(proyecto, carpeta), proyecto)
    registro, hilo = _leer_con_instantes(proc)
    try:
        assert _esperar_pids(proyecto / "pids.txt", proc, cantidad=1), "la prueba trabada no llegó a arrancar"
        hijo = _leer_pids(proyecto)[0]
        proc.send_signal(signal.SIGINT)
        fin = time.monotonic() + 120
        while _instante_en_que_aparece(registro, "Corrida interrumpida") is None and time.monotonic() < fin:
            time.sleep(0.05)
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=180)
        hilo.join(timeout=60)
        assert proc.returncode == 130, "".join(trozo for _, trozo in registro)
        assert _esperar_muerte(hijo), "el pytest que ignora SIGTERM sigue vivo: faltó el SIGKILL final"
        assert "INTERRUMPIDA" in (carpeta / "informe.txt").read_text(encoding="utf-8")
    finally:
        _detener(proc)
        _matar_los_de(proyecto, "NIETO_NO_HAY")


@SOLO_POSIX
def test_la_salida_cerrada_no_tumba_la_corrida(tmp_path):
    marca = "NIETO_DE_SALIDA_CERRADA"
    proyecto = _proyecto(tmp_path, {
        "test_a_trabada.py": _trabada_con_nieto(marca),
        "test_b_siguiente.py": _con_marcas("""
            def test_ok():
                anotar("b_corrio")
        """),
    })
    carpeta = proyecto / "salida"
    errores = proyecto / "errores.txt"
    entorno = os.environ.copy()
    entorno["PYTHONIOENCODING"] = "utf-8"
    with open(errores, "wb") as destino:
        proc = subprocess.Popen(_orden_del_corredor(proyecto, carpeta, "--silencio-max", "15"), cwd=str(proyecto),
                                env=entorno, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=destino,
                                start_new_session=True, preexec_fn=_preparar_hijo())
    try:
        for _ in range(3):
            proc.stdout.readline()
        proc.stdout.close()
        proc.wait(timeout=300)
        assert proc.returncode == 1, errores.read_text(errors="replace")
        assert "Traceback" not in errores.read_text(errors="replace")
        assert (proyecto / "marcas" / "b_corrio").exists(), "la corrida no siguió con el archivo siguiente"
        informe = (carpeta / "informe.txt").read_text(encoding="utf-8")
        assert "Archivos: 2" in informe and "INTERRUMPIDA" not in informe
        hijo, nieto = _leer_pids(proyecto)
        assert _esperar_muerte(hijo), "el proceso de pytest sigue vivo"
        assert _esperar_muerte(nieto), "el nieto sigue vivo"
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
        _matar_los_de(proyecto, marca)


@SOLO_POSIX
@pytest.mark.parametrize("descriptor", [1, 2], ids=["sin_salida_estandar", "sin_salida_de_errores"])
def test_sin_salida_estandar_o_sin_salida_de_errores_la_corrida_sigue_y_deja_informe(tmp_path, descriptor):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    carpeta = proyecto / "salida"
    proc = _lanzar(_orden_del_corredor(proyecto, carpeta), proyecto, stderr=subprocess.PIPE, cerrar=(descriptor,))
    _, errores = _esperar_con_errores(proc, 90)
    assert proc.returncode == 0, errores
    assert "Traceback" not in errores, errores
    assert "TODAS LAS PRUEBAS PASARON" in (carpeta / "informe.txt").read_text(encoding="utf-8")


def _bytes_en_la_tuberia(descriptor):
    """Bytes que hay en la tubería sin leer (POSIX)."""
    import array
    import fcntl
    import termios
    cantidad = array.array("i", [0])
    fcntl.ioctl(descriptor, termios.FIONREAD, cantidad)
    return cantidad[0]


def _tuberia_llena(descriptor):
    """True si en la tubería hay casi todo lo que cabe, de modo que quien escribe ya no puede seguir (POSIX)."""
    import fcntl
    capacidad = fcntl.fcntl(descriptor, fcntl.F_GETPIPE_SZ) if hasattr(fcntl, "F_GETPIPE_SZ") else 65536
    return _bytes_en_la_tuberia(descriptor) >= capacidad - 2048


class _SalidaQueNoAdmiteEscritura:
    """Salida no bloqueante de mentira: lo escrito queda en un búfer y vaciarlo lanza BlockingIOError mientras esté llena."""

    def __init__(self):
        self.llena = True
        self.pendiente = ""
        self.entregado = ""

    def write(self, texto):
        self.pendiente += texto

    def flush(self):
        if self.llena:
            raise BlockingIOError(errno.EAGAIN, "la tubería está llena")
        self.entregado += self.pendiente
        self.pendiente = ""

    def fileno(self):
        return 1000


class _RelojFalso:
    """Un reloj que solo avanza cuando la pantalla espera: la espera se prueba sin esperar de verdad."""

    def __init__(self):
        self.ahora = 1000.0

    def monotonic(self):
        return self.ahora

    def sleep(self, segundos):
        self.ahora += segundos


def _pantalla_de_mentira(monkeypatch, salida, abre_a_los=None, vueltas_maximas=10000):
    """Una Pantalla del corredor con reloj, select y salida falsos. Devuelve (corredor, pantalla, reloj, vueltas, desviadas).

    `abre_a_los` son los segundos de espera falsa tras los que la salida admite escritura; sin él, nunca se abre sola.
    """
    corredor = _cargar_corredor()
    reloj = _RelojFalso()
    vueltas = []
    desviadas = []

    def select_falso(leer, escribir, errores, espera):
        vueltas.append(espera)
        assert len(vueltas) <= vueltas_maximas, "la pantalla espera sin límite a una salida que no admite escritura"
        reloj.ahora += espera
        if abre_a_los is not None and reloj.ahora >= 1000.0 + abre_a_los:
            salida.llena = False
        return [], list(escribir), []

    monkeypatch.setattr(corredor, "time", reloj)
    monkeypatch.setattr(corredor, "select", SimpleNamespace(select=select_falso))
    monkeypatch.setattr(corredor, "sys", SimpleNamespace(stdout=salida, stderr=None))
    monkeypatch.setattr(corredor, "desviar_salida", lambda: desviadas.append(True))
    return corredor, corredor.Pantalla(), reloj, vueltas, desviadas


def test_una_salida_que_no_admite_escritura_se_espera_y_no_se_pierde_nada(monkeypatch):
    salida = _SalidaQueNoAdmiteEscritura()
    _, pantalla, reloj, vueltas, desviadas = _pantalla_de_mentira(monkeypatch, salida, abre_a_los=3.0)
    pantalla.escribir("primera\nsegunda\n")
    # la salida se abre tras 3 [s] de espera falsa, menos que la espera máxima: nada se pierde ni se apaga
    assert salida.entregado == "primera\nsegunda\n" and salida.pendiente == "", (salida.entregado, salida.pendiente)
    assert reloj.ahora - 1000.0 >= 3.0 and vueltas, "no esperó a que la salida admitiera escritura"
    assert desviadas == [] and not pantalla.sucio
    pantalla.escribir("tercera\n")
    assert salida.entregado == "primera\nsegunda\ntercera\n"


def test_una_salida_que_no_admite_escritura_nunca_no_cuelga_la_corrida_ni_apaga_la_pantalla_para_siempre(monkeypatch):
    salida = _SalidaQueNoAdmiteEscritura()
    corredor, pantalla, reloj, vueltas, desviadas = _pantalla_de_mentira(monkeypatch, salida)
    pantalla.escribir("perdida\n")
    espera = reloj.ahora - 1000.0
    # espera un rato a que la salida admita escritura y se rinde: ni se cuelga ni se rinde sin esperar
    assert 1.0 <= espera <= 60.0, espera
    assert salida.entregado == "" and desviadas == []
    # durante el período de descarte no espera ni escribe
    antes = len(vueltas)
    pantalla.escribir("descartada\n")
    assert len(vueltas) == antes and salida.entregado == ""
    # pasado ese período y con la salida abierta, la pantalla vuelve a escribir
    reloj.ahora += corredor.PERIODO_DE_DESCARTE + 1.0
    salida.llena = False
    pantalla.escribir("llega\n")
    assert salida.entregado.endswith("llega\n") and "descartada" not in salida.entregado, salida.entregado
    assert desviadas == [] and not pantalla.sucio


def _llenar_y_vaciar_tuberia():
    """Una tubería no bloqueante llena hasta el último byte, y una función que lee lo que haya. Devuelve (leer, escribir, vaciar)."""
    import fcntl
    leer, escribir = os.pipe()
    for descriptor in (leer, escribir):
        fcntl.fcntl(descriptor, fcntl.F_SETFL, fcntl.fcntl(descriptor, fcntl.F_GETFL) | os.O_NONBLOCK)
    for trozo in (b"x" * 1024, b"x"):
        try:
            while True:
                os.write(escribir, trozo)
        except BlockingIOError:
            pass

    def vaciar():
        datos = b""
        while True:
            try:
                bloque = os.read(leer, 65536)
            except BlockingIOError:
                return datos
            if not bloque:
                return datos
            datos += bloque
    return leer, escribir, vaciar


@SOLO_POSIX
def test_una_salida_sin_bufer_tampoco_pierde_en_silencio_lo_que_no_cabe_en_la_tuberia(monkeypatch):
    # con PYTHONUNBUFFERED o python -u la salida es texto sin búfer sobre el descriptor en bruto: una escritura que no
    # cabe en la tubería no lanza BlockingIOError, se pierde, y la pantalla no se entera
    leer, escribir, vaciar = _llenar_y_vaciar_tuberia()
    try:
        sin_bufer = io.TextIOWrapper(io.FileIO(escribir, "wb", closefd=False), encoding="utf-8", write_through=True)
        corredor, pantalla, reloj, vueltas, desviadas = _pantalla_de_mentira(monkeypatch, sin_bufer)
        corredor.preparar_flujos()
        pantalla.escribir("primera\n")
        # la tubería sigue llena y nadie lee: la pantalla se entera, espera y deja lo escrito pendiente
        assert pantalla.sucio and vueltas, "lo escrito se perdió sin que la pantalla lo supiera"
        relleno = vaciar()
        # pasado el período de descarte y con la tubería libre, entrega lo pendiente y lo nuevo, en orden
        reloj.ahora += corredor.PERIODO_DE_DESCARTE + 1.0
        pantalla.escribir("segunda\n")
        assert (relleno + vaciar()).endswith(b"primera\nsegunda\n"), relleno[-40:]
        assert desviadas == [] and not pantalla.sucio
    finally:
        os.close(leer)
        os.close(escribir)


@SOLO_POSIX
@pytest.mark.parametrize("sin_bufer", [False, True], ids=["con_bufer", "sin_bufer"])
def test_una_salida_que_no_admite_escritura_un_rato_no_pierde_el_informe(tmp_path, sin_bufer):
    import fcntl
    muchas = _con_marcas("""
        import pytest


        @pytest.mark.parametrize('n', range(1500))
        def test_p(n):
            if n == 1499:
                anotar("fin_de_las_pruebas")
    """)
    proyecto = _proyecto(tmp_path, {"test_a_muchas.py": muchas, "test_b_ultima.py": "def test_ultima():\n    pass\n"})
    leer, escribir = os.pipe()
    fcntl.fcntl(escribir, fcntl.F_SETFL, fcntl.fcntl(escribir, fcntl.F_GETFL) | os.O_NONBLOCK)
    # la espera máxima del corredor para una salida que no admite escritura es de 300 [s] en este caso: ninguna carga la agota
    orden = [sys.executable, "-c", LANZADOR_CON_CONSTANTES, str(RUTA_CORREDOR), repr({"ESPERA_MAXIMA_DE_ESCRITURA": 300.0}),
             "--raiz", str(proyecto), "--salida", str(proyecto / "salida")]
    # sin búfer es como corre el corredor dentro de otro corredor: PYTHONUNBUFFERED=1 en el entorno heredado
    entorno = os.environ.copy()
    if sin_bufer:
        entorno["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(orden, cwd=str(proyecto), env=entorno, stdin=subprocess.DEVNULL, stdout=escribir,
                            stderr=subprocess.PIPE, start_new_session=True, preexec_fn=_preparar_hijo())
    os.close(escribir)
    datos = b""
    try:
        # nadie lee hasta que pytest terminó el primer archivo y la tubería está llena: el corredor tiene que
        # esperar a quien lee, sin descartar nada ni apagar la pantalla
        fin_de_pytest = proyecto / "marcas" / "fin_de_las_pruebas"
        limite = time.monotonic() + 240
        while time.monotonic() < limite and proc.poll() is None:
            if fin_de_pytest.exists() and _tuberia_llena(leer):
                break
            time.sleep(0.02)
        assert proc.poll() is None and _tuberia_llena(leer), "no se llegó a la situación que prueba el caso"
        limite = time.monotonic() + 240
        while True:
            if not select.select([leer], [], [], 1.0)[0]:
                assert time.monotonic() < limite, "el corredor dejó de escribir"
                continue
            bloque = os.read(leer, 65536)
            if not bloque:
                break
            datos += bloque
        proc.wait(timeout=240)
    finally:
        os.close(leer)
        _detener(proc)
    errores = proc.stderr.read().decode("utf-8", errors="replace")
    proc.stderr.close()
    texto = datos.decode("utf-8", errors="replace")
    assert proc.returncode == 0, errores
    # no se perdió ninguna línea: ni las de después de llenarse la tubería, ni el segundo archivo, ni el informe
    assert len(re.findall(r"test_p\[\d+\] PASSED", texto)) == 1500, texto[-600:]
    assert "[2/2] tests/test_b_ultima.py" in texto and "VEREDICTO: TODAS LAS PRUEBAS PASARON" in texto, texto[-600:]
    assert errores == "", errores


@SOLO_POSIX
def test_si_el_registro_no_se_puede_escribir_la_corrida_sigue_y_lo_avisa(tmp_path):
    conftest = """
        import resource

        _blando, _duro = resource.getrlimit(resource.RLIMIT_FSIZE)
        resource.setrlimit(resource.RLIMIT_FSIZE, (_duro, _duro))
    """
    mucho = """
        def test_imprime_mucho():
            for i in range(3000):
                print(f"{i:06d} " + "x" * 100)
    """
    proyecto = _proyecto(tmp_path, {"test_a_mucho.py": mucho, "test_b_normal.py": "def test_ok():\n    pass\n"},
                         conftest=conftest)
    # solo el registro del corredor queda sin poder crecer más de 32 KiB; el pytest hijo recupera su límite
    corrida = _correr(proyecto, "--silencio-max", "60", limite=300, limite_de_archivo=32768)
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 0), corrida.informe
    avisos = _seccion(corrida.informe, "Avisos:")
    assert len(avisos) == 1 and avisos[0].startswith("tests/test_a_mucho.py - registro incompleto: "), avisos
    assert "AVISO: registro incompleto" in corrida.pantalla, corrida.pantalla
    assert "detenido" not in corrida.pantalla and "detenido" not in corrida.informe
    assert "[2/2] tests/test_b_normal.py" in corrida.pantalla
    assert (corrida.carpeta / "test_a_mucho.log").stat().st_size <= 32768


@SOLO_POSIX
def test_una_falla_interna_detiene_a_los_que_siguen_vivos(tmp_path):
    marca = "NIETO_DE_FALLA_INTERNA"
    maximo = os.pathconf(str(tmp_path), "PC_NAME_MAX")
    # con el nombre más largo que admite el sistema, el registro (.log) ya no cabe y lanzar el archivo falla
    nombre_largo = "test_c" + "a" * (maximo - 9) + ".py"
    proyecto = _proyecto(tmp_path, {
        "test_a_trabada.py": _trabada_con_nieto(marca),
        "test_b_espera.py": """
            import time
            from pathlib import Path


            def test_espera_al_nieto():
                ruta = Path(__file__).resolve().parent.parent / "pids.txt"
                fin = time.monotonic() + 90
                while time.monotonic() < fin and not (ruta.exists() and len(ruta.read_text().split()) == 2):
                    time.sleep(0.05)
        """,
        nombre_largo: "def test_x():\n    pass\n",
    })
    try:
        corrida = _correr(proyecto, "--procesos", "2", "--silencio-max", "120", limite=300, aparte=True)
        assert corrida.codigo == 3, corrida.pantalla
        assert "Error interno del corredor" in corrida.errores and "Traceback" in corrida.errores, corrida.errores
        lineas = corrida.informe.splitlines()
        assert "ERROR INTERNO DEL CORREDOR" in lineas[0], lineas[0]
        assert "VEREDICTO: ERROR INTERNO DEL CORREDOR, SIN VEREDICTO" in lineas, lineas
        assert "INTERRUMPIDA" not in corrida.informe and "INTERRUMPIDA" not in corrida.pantalla
        hijo, nieto = _leer_pids(proyecto)
        assert _esperar_muerte(hijo), "el proceso de pytest sigue vivo"
        assert _esperar_muerte(nieto), "el nieto sigue vivo"
    finally:
        _matar_los_de(proyecto, marca)


def test_un_error_interno_que_escapa_de_correr_tambien_deja_informe_y_codigo_3(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    carpeta = proyecto / "salida"
    orden = [sys.executable, "-c", LANZADOR_CON_CORRER_QUE_FALLA, str(RUTA_CORREDOR),
             "--raiz", str(proyecto), "--salida", str(carpeta)]
    codigo, salida = _ejecutar(orden, proyecto)
    assert codigo == 3, salida
    assert "Error interno del corredor: RuntimeError: falla que correr no atrapa" in salida and "Traceback" in salida
    lineas = (carpeta / "informe.txt").read_text(encoding="utf-8").splitlines()
    assert "ERROR INTERNO DEL CORREDOR" in lineas[0], lineas[0]
    assert "VEREDICTO: ERROR INTERNO DEL CORREDOR, SIN VEREDICTO" in lineas, lineas


@SOLO_POSIX
def test_el_nieto_de_una_prueba_que_termina_bien_tambien_muere(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a_deja_nieto.py": """
        import os
        import subprocess
        import sys
        from pathlib import Path


        def test_pasa_y_deja_un_nieto():
            nieto = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(100)  # NIETO_DE_FINAL_NORMAL"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ruta = Path(__file__).resolve().parent.parent / "pids.txt"
            ruta.write_text(f"{os.getpid()} {nieto.pid}")
    """})
    try:
        corrida = _correr(proyecto, limite=300)
        assert corrida.codigo == 0, corrida.pantalla
        hijo, nieto = _leer_pids(proyecto)
        assert _esperar_muerte(nieto), "el nieto sigue vivo: no se detuvo el grupo tras un final normal"
    finally:
        _matar_los_de(proyecto, "NIETO_DE_FINAL_NORMAL")


ESCAPA_DEL_GRUPO = """
    import subprocess
    import sys
    from pathlib import Path


    def test_pasa_y_deja_uno_fuera_del_grupo(capfd):
        with capfd.disabled():
            hijo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)  # ESCAPADO_DEL_GRUPO"],
                                    start_new_session=True{salida})
        (Path(__file__).resolve().parent.parent / "pids.txt").write_text(str(hijo.pid))
"""


@SOLO_POSIX
@pytest.mark.parametrize("retiene_la_salida", [True, False], ids=["retiene_la_salida", "no_retiene_la_salida"])
def test_un_proceso_fuera_del_grupo_que_retiene_la_salida_se_avisa_sin_cambiar_el_veredicto(tmp_path, retiene_la_salida):
    salida = "" if retiene_la_salida else ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL"
    proyecto = _proyecto(tmp_path, {"test_a_escapa.py": ESCAPA_DEL_GRUPO.replace("{salida}", salida),
                                    "test_b_normal.py": "def test_ok():\n    pass\n"})
    try:
        # si nadie retiene la salida la gracia no se gasta: una larga evita un aviso falso con la máquina cargada
        gracia = 1.0 if retiene_la_salida else 30.0
        codigo, pantalla, carpeta = _correr_con_constantes(proyecto, {"GRACIA_DE_SALIDA": gracia}, limite=300)
        informe = (carpeta / "informe.txt").read_text(encoding="utf-8")
        assert codigo == 0, pantalla
        assert _cifras(informe) == (2, 0, 0, 0, 0)
        assert "TODAS LAS PRUEBAS PASARON" in informe
        aviso = "un proceso fuera del grupo mantiene abierta la salida"
        if retiene_la_salida:
            assert f"AVISO: {aviso}" in pantalla, pantalla
            assert _seccion(informe, "Avisos:") == [f"tests/test_a_escapa.py - {aviso}"], informe
        else:
            assert "AVISO" not in pantalla and "Avisos:" not in informe
    finally:
        if (proyecto / "pids.txt").exists():
            _matar_si_es_nuestro(_leer_pids(proyecto)[0], "ESCAPADO_DEL_GRUPO")


def test_la_pantalla_en_vivo_oculta_lo_repetitivo_y_el_registro_guarda_todo(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_falla.py": _con_separadores("""
            def test_a1_imprime_separadores_falsos_y_falla():
                print(sep("=", "test session starts"), end="")
                print(sep("=", "PASSES"), end="")
                print(sep("-", "RT1 cobertura"), end="")
                print("MARCA_SALIDA_A1")
                assert "a" == "b"


            def test_a2_falla_despues():
                assert 3 == 4


            def test_a3_pasa_e_imprime():
                print("MARCA_SALIDA_A3")
        """),
        "test_b_pasa.py": """
            import pytest


            def test_b1_imprime():
                print("MARCA_SALIDA_B")


            @pytest.mark.skip(reason="motivo visible de la omitida")
            def test_b2_omitida():
                pass
        """,
        "test_c_pasa.py": "def test_c1():\n    pass\n",
    }, conftest=CONFTEST_RT1)
    corrida = _correr(proyecto)
    pantalla = corrida.pantalla
    assert corrida.codigo == 1, pantalla
    assert _cifras(corrida.informe) == (3, 2, 0, 1, 0)
    partes = re.split(r"^\[\d/3\] (tests/\S+)$", pantalla, flags=re.M)
    assert partes[1::2] == ["tests/test_a_falla.py", "tests/test_b_pasa.py", "tests/test_c_pasa.py"], partes[1::2]
    a, b, c = partes[2::2]
    # el archivo con fallas lo muestra casi todo: la traza de la segunda falla, PASSES y la cobertura de RT1
    for visible in ("in test_a2_falla_despues", "E   assert 3 == 4", "MARCA_SALIDA_A1", "MARCA_SALIDA_A3",
                    "MARCA_COBERTURA 9", "FAILURES"):
        assert visible in a, f"{visible!r} debía verse en el archivo con fallas:\n{a}"
    assert a.count("test session starts") == 1, "solo debía verse la cabecera falsa que imprimió la prueba"
    assert a.count(" PASSES ") == 2 and a.count("RT1 cobertura") == 2, a
    assert "rootdir" not in a, "la cabecera real del archivo no debía verse"
    # los archivos que pasan no muestran la cabecera, ni PASSES, ni RT1, ni la salida de sus pruebas
    for sin_fallas in (b, c):
        for oculto in ("MARCA_COBERTURA", "MARCA_SALIDA_B", "PASSES", "test session starts", "rootdir", "RT1"):
            assert oculto not in sin_fallas, f"{oculto!r} no debía verse:\n{sin_fallas}"
    for visible in ("test_b1_imprime PASSED", "test_b2_omitida SKIPPED", "motivo visible de la omitida"):
        assert visible in b, f"{visible!r} debía verse:\n{b}"
    assert re.search(r"SKIPPED \[1\] tests[\\/]test_b_pasa\.py", b), b
    assert "test_c1 PASSED" in c, c
    assert not re.search(r"^PASSED ", pantalla, re.M), pantalla
    assert re.search(r"^=+ 2 failed, 1 passed in ", a, re.M), a
    for archivo in ("test_a_falla", "test_c_pasa"):
        registro = (corrida.carpeta / f"{archivo}.log").read_text(encoding="utf-8")
        for completo in ("MARCA_COBERTURA 9", " PASSES ", "test session starts", "rootdir"):
            assert completo in registro, f"{completo!r} faltó en el registro de {archivo}"
        assert re.search(r"^PASSED tests/", registro, re.M)
    assert "MARCA_SALIDA_B" in (corrida.carpeta / "test_b_pasa.log").read_text(encoding="utf-8")


def test_un_separador_que_llega_sin_captura_no_oculta_las_pruebas_que_siguen(tmp_path):
    # lo que una prueba escribe fuera de la captura sale entre las líneas de pytest, antes de FAILURES
    proyecto = _proyecto(tmp_path, {"test_directo.py": _con_separadores("""
        def test_a_escribe_separadores_de_otro_ancho(capfd):
            with capfd.disabled():
                os.write(1, ("\\n" + "=" * 5 + " PASSES " + "=" * 5 + "\\n").encode())
                os.write(1, ("-" * 5 + " RT1 cobertura " + "-" * 5 + "\\n").encode())


        def test_b_escribe_una_cabecera_exacta_tras_la_primera_prueba(capfd):
            with capfd.disabled():
                os.write(1, ("\\n" + sep("=", "test session starts")).encode())


        def test_c_sigue_a_la_vista():
            pass
    """)})
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert "test_c_sigue_a_la_vista PASSED" in corrida.pantalla, corrida.pantalla
    assert "===== PASSES =====" in corrida.pantalla and "----- RT1 cobertura -----" in corrida.pantalla
    assert corrida.pantalla.count("test session starts") == 1, corrida.pantalla


def test_los_errores_de_la_cabecera_se_ven_en_vivo(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_x.py": "def test_x():\n    pass\n"},
                         conftest="""
        def pytest_collection(session):
            raise RuntimeError("fallo al recoger")
    """)
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    en_vivo = corrida.pantalla.split("ARCHIVO CON PROBLEMA")[0]
    assert "INTERNALERROR> RuntimeError: fallo al recoger" in en_vivo, corrida.pantalla


def test_los_bytes_que_no_son_utf8_no_cortan_la_corrida(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_bytes.py": """
            import os


            def test_escribe_bytes_crudos(capfd):
                with capfd.disabled():
                    os.write(1, b"\\nantes \\xff\\xfe despues\\n")
        """,
        "test_b_siguiente.py": "def test_ok():\n    pass\n",
    })
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 0)
    assert "antes " in corrida.pantalla and " despues" in corrida.pantalla
    assert b"antes \xff\xfe despues" in (corrida.carpeta / "test_a_bytes.log").read_bytes()
    assert "[2/2] tests/test_b_siguiente.py" in corrida.pantalla


def test_aviso_en_el_modo_repartido(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_rapido.py": _con_marcas("""
            def test_ok():
                anotar("rapido_fin")
        """),
        # el lento espera la marca del rápido y luego la del aviso, que anota esta misma prueba
        "test_b_lento.py": _con_marcas("""
            def test_lento():
                esperar("rapido_fin")
                esperar("aviso_visto", 150)
        """),
    })
    orden = _orden_del_corredor(proyecto, proyecto / "salida", "--procesos", "2", "--aviso-cada", "1")
    proc = _lanzar(orden, proyecto)
    registro, hilo = _leer_con_instantes(proc)
    termino_el_rapido = re.compile(r"^\[\d/2\] tests/test_a_rapido\.py: .*$", re.M)
    aviso_del_lento = re.compile(r"siguen corriendo: .*tests/test_b_lento\.py")
    visto = None
    try:
        limite = time.monotonic() + 300
        while proc.poll() is None and time.monotonic() < limite:
            pantalla = "".join(trozo for _, trozo in registro)
            termino = termino_el_rapido.search(pantalla)
            if termino and visto is None:
                visto = time.monotonic()
            if termino and (aviso_del_lento.search(pantalla, termino.end()) or time.monotonic() - visto > 90):
                (proyecto / "marcas" / "aviso_visto").write_text("1")
            time.sleep(0.1)
        proc.wait(timeout=240)
    except subprocess.TimeoutExpired:
        _detener(proc)
        pytest.fail("venció el tiempo")
    finally:
        _detener(proc)
    hilo.join(timeout=60)
    pantalla = "".join(trozo for _, trozo in registro)
    assert proc.returncode == 0, pantalla
    termino = termino_el_rapido.search(pantalla)
    assert termino, pantalla
    despues = pantalla[termino.end():]
    assert aviso_del_lento.search(despues), pantalla
    assert not re.search(r"siguen corriendo: .*test_a_rapido", despues), pantalla


def test_el_codigo_de_pytest_debe_cuadrar_con_su_resultado(tmp_path):
    # un gancho del conftest que lanza al cerrar: pytest sale con 1 y su XML no trae fallas
    dos_pasan = "def test_uno():\n    pass\n\n\ndef test_dos():\n    pass\n"
    gancho = _proyecto(tmp_path / "gancho", {"test_ok.py": dos_pasan},
                       conftest="""
        def pytest_unconfigure(config):
            raise RuntimeError("fallo al cerrar la sesion")
    """)
    corrida = _correr(gancho)
    assert corrida.codigo == 1, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 1)
    problema = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "pytest terminó con 1 pero su resultado no trae fallas" in problema
    assert "fallo al cerrar la sesion" in problema, "faltan las últimas líneas del registro"
    for texto in (corrida.informe, corrida.pantalla):
        assert "TODAS LAS PRUEBAS PASARON" not in texto
    # el caso contrario: pytest sale con 0 aunque su XML trae una falla
    una_falla = "def test_ok():\n    pass\n\n\ndef test_mala():\n    assert False\n"
    forzado = _proyecto(tmp_path / "forzado", {"test_f.py": una_falla},
                        conftest="""
        import pytest


        @pytest.hookimpl(trylast=True)
        def pytest_sessionfinish(session, exitstatus):
            session.exitstatus = 0
    """)
    corrida = _correr(forzado)
    assert corrida.codigo == 1, corrida.pantalla
    assert _cifras(corrida.informe) == (1, 1, 0, 0, 1)
    problema = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "pytest terminó con 0 pero su resultado trae fallas" in problema
    assert "TODAS LAS PRUEBAS PASARON" not in corrida.informe


def test_un_separador_impreso_por_una_prueba_que_falla_no_esconde_la_traza_siguiente(tmp_path):
    # tres separadores del ancho exacto de la terminal, impresos por una prueba que falla
    proyecto = _proyecto(tmp_path, {"test_sep.py": _con_separadores("""
        def test_a_imprime_separadores():
            print(sep("=", "test session starts"), end="")
            print(sep("=", "PASSES"), end="")
            print(sep("-", "RT1 cobertura"), end="")
            assert "a" == "b"


        def test_b_falla_despues():
            assert 3 == 4
    """)}, conftest=CONFTEST_RT1)
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    for visible in ("in test_b_falla_despues", "E   assert 3 == 4", "short test summary info"):
        assert visible in corrida.pantalla, f"{visible!r} debía verse:\n{corrida.pantalla}"


def test_el_corredor_fija_el_ancho_de_pytest(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_ancho.py": """
        import os
        import shutil


        def test_columns():
            assert os.environ["COLUMNS"] == "80"
            assert shutil.get_terminal_size().columns == 80
    """})
    corrida = _correr(proyecto, entorno={"COLUMNS": "200"})
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (1, 0, 0, 0, 0)


def _correr_en_terminal(proyecto, columnas, limite=240):
    """Corre el corredor con su salida en una terminal simulada de ese ancho; devuelve lo que se escribió."""
    import fcntl
    import pty
    import struct
    import termios
    maestro, esclavo = pty.openpty()
    fcntl.ioctl(esclavo, termios.TIOCSWINSZ, struct.pack("HHHH", 24, columnas, 0, 0))
    entorno = os.environ.copy()
    entorno.pop("COLUMNS", None)
    entorno["PYTHONIOENCODING"] = "utf-8"
    orden = _orden_del_corredor(proyecto, proyecto / "salida")
    proc = subprocess.Popen(orden, cwd=str(proyecto), env=entorno, stdin=subprocess.DEVNULL,
                            stdout=esclavo, stderr=esclavo, start_new_session=True,
                            preexec_fn=_preparar_hijo())
    os.close(esclavo)
    datos = b""
    try:
        fin = time.monotonic() + limite
        while time.monotonic() < fin:
            if select.select([maestro], [], [], 0.2)[0]:
                try:
                    bloque = os.read(maestro, 65536)
                except OSError:
                    break
                if not bloque:
                    break
                datos += bloque
            elif proc.poll() is not None:
                break
        proc.wait(timeout=120)
    finally:
        _detener(proc)
        os.close(maestro)
    return proc.returncode, datos.decode("utf-8", errors="replace")


@SOLO_POSIX
def test_en_una_terminal_se_usa_su_ancho_y_el_color(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_t.py": """
        def test_pasa():
            print("MARCA_SALIDA_DE_PRUEBA")


        def test_falla():
            assert 1 == 2
    """}, conftest="""
        def pytest_terminal_summary(terminalreporter):
            terminalreporter.write_sep("-", "RT1 cobertura")
            terminalreporter.write_line("MARCA_COBERTURA")
    """)
    codigo, crudo = _correr_en_terminal(proyecto, 100)
    limpio = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", crudo).replace("\r", "")
    assert codigo == 1, limpio
    assert "\x1b[" in crudo, "no se pidió color a pytest en una terminal"
    for visible in ("test_pasa PASSED", "test_falla FAILED", "FAILURES", "assert 1 == 2"):
        assert visible in limpio, f"{visible!r} debía verse:\n{limpio}"
    for oculto in ("test session starts", "rootdir"):
        assert oculto not in limpio, f"{oculto!r} no debía verse:\n{limpio}"
    separadores = [l for l in limpio.splitlines() if "FAILURES" in l and l.startswith("=")]
    assert separadores and len(separadores[0]) == 100, separadores
    # el archivo falla, así que su cobertura y PASSES sí se ven; el ancho de las líneas es el de la terminal
    assert "MARCA_COBERTURA" in limpio


@SOLO_POSIX
def test_en_una_terminal_un_archivo_que_pasa_no_muestra_cabecera_ni_cobertura(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_t.py": """
        def test_pasa():
            print("MARCA_SALIDA_DE_PRUEBA")
    """}, conftest="""
        def pytest_terminal_summary(terminalreporter):
            terminalreporter.write_sep("-", "RT1 cobertura")
            terminalreporter.write_line("MARCA_COBERTURA")
    """)
    codigo, crudo = _correr_en_terminal(proyecto, 100)
    limpio = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", crudo).replace("\r", "")
    assert codigo == 0, limpio
    for oculto in ("MARCA_COBERTURA", "MARCA_SALIDA_DE_PRUEBA", "test session starts", "PASSES", "rootdir"):
        assert oculto not in limpio, f"{oculto!r} no debía verse:\n{limpio}"
    assert "test_pasa PASSED" in limpio


def test_las_cifras_son_las_de_pytest_con_teardown_roto_y_xfail(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_td.py": """
        import pytest


        @pytest.fixture
        def roto_al_cerrar():
            yield
            raise RuntimeError("fallo en el teardown")


        @pytest.fixture
        def roto_al_abrir():
            raise RuntimeError("fallo en el setup")


        @pytest.mark.parametrize("n", [1, 2, 3])
        def test_param_pasa_y_teardown_roto(n, roto_al_cerrar):
            pass


        def test_setup_roto(roto_al_abrir):
            pass


        @pytest.mark.skip(reason="omitida a proposito")
        def test_omitida(roto_al_cerrar):
            pass


        @pytest.mark.xfail(strict=True)
        def test_xfail_estricto_que_pasa():
            pass


        @pytest.mark.xfail(reason="se espera")
        def test_xfail():
            assert False
    """})
    _, salida = _ejecutar([sys.executable, "-m", "pytest", "tests/test_td.py", "-q", "-p", "no:cacheprovider"],
                          proyecto)
    resumen = [l for l in salida.splitlines() if " passed" in l][-1]
    de_pytest = {nombre: int(n)
                 for n, nombre in re.findall(r"(\d+) (failed|passed|skipped|xfailed|errors?)\b", resumen)}
    assert de_pytest.get("passed") == 3 and de_pytest.get("xfailed") == 1, resumen
    errores = de_pytest.get("errors", de_pytest.get("error", 0))
    esperado = (de_pytest["passed"], de_pytest["failed"], errores, de_pytest["skipped"], 0)
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    assert _cifras(corrida.informe) == esperado, (resumen, corrida.informe)
    assert _cifras(corrida.pantalla) == esperado
    for texto in (corrida.informe, corrida.pantalla):
        assert re.search(r"^Fallas esperadas \(xfail\): 1$", texto, re.M), texto
    assert re.search(r"^    3 pasaron, 1 falló, 4 errores, 1 omitida, 1 falla esperada \(xfail\) \(", corrida.pantalla,
                     re.M), corrida.pantalla
    omitidas = _seccion(corrida.informe, "Omitidas, con su motivo:")
    assert omitidas == ["tests/test_td.py::test_omitida - omitida a proposito"], omitidas
    fallaron = _seccion(corrida.informe, "Fallaron:")
    assert len(fallaron) == 1 and "test_xfail_estricto_que_pasa" in fallaron[0], fallaron
    con_error = _seccion(corrida.informe, "Errores:")
    assert len(con_error) == errores == 4, con_error
    assert sum("test_param_pasa_y_teardown_roto" in l for l in con_error) == 3, con_error
    assert sum("test_setup_roto" in l for l in con_error) == 1, con_error


def test_una_xfail_que_no_es_estricta_y_pasa_cuenta_como_pasada(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_xp.py": """
        import pytest


        @pytest.mark.xfail(reason="no debía pasar")
        def test_xpass():
            pass


        def test_ok():
            pass
    """})
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 0), corrida.informe


@SOLO_POSIX
def test_una_caida_al_recoger_se_nombra_y_se_ven_sus_ultimas_lineas(tmp_path):
    fuente = "import faulthandler\n\nfaulthandler._sigsegv()\n\n\ndef test_x():\n    pass\n"
    proyecto = _proyecto(tmp_path, {"test_cae.py": fuente})
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    en_vivo = corrida.pantalla.split("RESULTADO DE LAS PRUEBAS")[0]
    assert "ARCHIVO CON PROBLEMA: pytest terminó por la señal 11 (SIGSEGV)" in en_vivo, en_vivo
    assert "Current thread" in en_vivo, "faltan las últimas líneas del registro, con el volcado de faulthandler"
    assert "Fatal Python error: Segmentation fault" in en_vivo, "la cola de líneas es demasiado corta"
    assert "señal 11 (SIGSEGV)" in corrida.informe


def test_salida_sobre_un_archivo_da_un_mensaje_y_codigo_2(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"})
    archivo = tmp_path / "un_archivo.txt"
    archivo.write_text("contenido", encoding="utf-8")
    corrida = _correr(proyecto, "--salida", archivo, salida=None)
    assert corrida.codigo == 2, corrida.pantalla
    assert "Traceback" not in corrida.pantalla
    assert "--salida" in corrida.pantalla and str(archivo.resolve()) in corrida.pantalla
    assert "pasaron" not in corrida.pantalla
    assert archivo.read_text(encoding="utf-8") == "contenido"


@SOLO_POSIX
def test_un_enlace_simbolico_se_corre_y_se_informa_con_el_nombre_pedido(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_real.py": "def test_real():\n    pass\n"})
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    (afuera / "test_origen.py").write_text("def test_origen():\n    pass\n", encoding="utf-8")
    os.symlink("test_real.py", proyecto / "tests" / "test_enlace_interno.py")
    os.symlink(afuera / "test_origen.py", proyecto / "tests" / "test_enlace_afuera.py")
    corrida = _correr(proyecto, "tests/test_enlace_interno.py", "tests/test_enlace_afuera.py")
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 0), corrida.informe
    assert "[1/2] tests/test_enlace_interno.py" in corrida.pantalla, corrida.pantalla
    assert "[2/2] tests/test_enlace_afuera.py" in corrida.pantalla, corrida.pantalla
    assert sorted(p.name for p in corrida.carpeta.glob("*.log")) == [
        "recoleccion.log", "test_enlace_afuera.log", "test_enlace_interno.log"]
    # la recolección también los nombra como se pidieron, y las dos pruebas cuentan como recogidas y corridas
    assert _completitud(corrida.informe) == (2, 2, 0), corrida.informe


@SOLO_POSIX
def test_la_duracion_de_un_archivo_es_la_del_proceso_aunque_el_bucle_tarde_en_verlo(tmp_path):
    corredor = _cargar_corredor()
    proyecto = _proyecto(tmp_path, {"test_rapido.py": "def test_ok():\n    pass\n"})
    ejecucion = corredor.Ejecucion("tests/test_rapido.py", tmp_path / "r.log", tmp_path / "r.xml")
    ejecucion.iniciar(proyecto, corredor.entorno_del_hijo(80), en_vivo=False, con_color=False)
    try:
        # se espera el hecho (el vigilante anotó el fin del proceso), no un plazo
        limite = time.monotonic() + 240
        while ejecucion.termino is None and time.monotonic() < limite:
            time.sleep(0.02)
        assert ejecucion.termino is not None, "pytest no terminó"
        visto = time.monotonic()
        # el bucle principal está ocupado (por ejemplo deteniendo a otro archivo) y tarda en llegar a este
        time.sleep(0.5)
        limite = time.monotonic() + 240
        while not ejecucion.revisar(600) and time.monotonic() < limite:
            time.sleep(0.05)
        resultado = corredor.resultado_de(ejecucion)
        # el fin es el instante en que terminó el proceso, anotado antes de que el bucle lo viera; sin márgenes de reloj
        assert ejecucion.fin <= visto, f"el fin se anotó {ejecucion.fin - visto:.1f} [s] después de haberse visto el final"
        assert resultado.pasaron == 1 and resultado.problema is None, resultado.problema
    finally:
        corredor.detener_grupos([ejecucion.proc])


@SOLO_LINUX
def test_si_se_interrumpe_el_corredor_externo_no_queda_vivo_nada_de_la_cadena(tmp_path):
    # un corredor externo corre un archivo que lanza otro corredor (como las pruebas de este archivo)
    marca = uuid.uuid4().hex
    entorno = {"MARCA_DE_LA_CADENA": marca}
    base_interna = tmp_path / "interna"
    meta = _proyecto(tmp_path / "externa", {"test_meta.py": f"""
        import importlib.util
        import time
        from pathlib import Path


        def test_lanza_el_corredor_interno():
            especificacion = importlib.util.spec_from_file_location("pruebas_del_corredor", {str(Path(__file__).resolve())!r})
            modulo = importlib.util.module_from_spec(especificacion)
            especificacion.loader.exec_module(modulo)
            interno = modulo._proyecto(Path({str(base_interna)!r}), {{"test_a_trabada.py": modulo._trabada_con_nieto("NIETO_DE_LA_CADENA")}})
            modulo._lanzar(modulo._orden_del_corredor(interno, interno / "salida"), interno)
            time.sleep(300)
    """})
    proc = _lanzar(_orden_del_corredor(meta, meta / "salida"), meta, entorno=entorno)
    try:
        assert _esperar_pids(base_interna / "proyecto" / "pids.txt", proc), "la cadena no llegó a armarse"
        assert len(_con_marca_en_el_entorno(marca)) >= 5, _con_marca_en_el_entorno(marca)
        proc.send_signal(signal.SIGTERM)
        pantalla = _esperar(proc, 240)
        assert proc.returncode == 130, pantalla
        fin = time.monotonic() + 90
        while _con_marca_en_el_entorno(marca) and time.monotonic() < fin:
            time.sleep(0.25)
        quedan = _con_marca_en_el_entorno(marca)
        assert quedan == [], f"quedan vivos {len(quedan)} procesos de la cadena"
    finally:
        _detener(proc)
        _matar_los_de_la_marca(marca)


# ------------------------------------------ completitud: recogidas = corridas

CONFTEST_QUE_DUERME_AL_RECOGER = """
    import os
    import subprocess
    import sys
    import time
    from pathlib import Path

    if "--collect-only" in sys.argv:
        nieto = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)  # NIETO_DE_LA_RECOLECCION"])
        (Path(__file__).resolve().parent.parent / "pids.txt").write_text(f"{os.getpid()} {nieto.pid}")
        time.sleep(300)
"""

CONFTEST_QUE_CAE_AL_RECOGER = """
    import os
    import sys

    if "--collect-only" in sys.argv:
        os._exit(3)
"""

CONFTEST_QUE_TRAGA_UNA_PRUEBA = """
    def pytest_runtest_protocol(item, nextitem):
        if item.name == "test_tragada":
            return True
"""

CIERRE_ROTO = """
    import pytest


    @pytest.fixture
    def roto_al_cerrar():
        yield
        raise RuntimeError("fallo en el cierre")
"""


def _matar_la_recoleccion(proyecto):
    """Mata los procesos sobrantes de una recolección que duerme (el pytest y su nieto), solo si son nuestros."""
    if (proyecto / "pids.txt").exists():
        pids = _leer_pids(proyecto)
        _matar_si_es_nuestro(pids[0], "--collect-only")
        for pid in pids[1:]:
            _matar_si_es_nuestro(pid, "NIETO_DE_LA_RECOLECCION")


def test_los_archivos_que_pytest_recoge_y_el_patron_no_ve_tambien_se_corren(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a():\n    pass\n",
        "foo_test.py": "def test_f():\n    pass\n",
        "sub/test_b.py": "def test_b1():\n    pass\n\n\ndef test_b2():\n    pass\n",
    })
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert re.search(r"^Archivos: 3 ", corrida.informe, re.M), corrida.informe
    assert _cifras(corrida.informe) == (4, 0, 0, 0, 0)
    assert _completitud(corrida.informe) == (4, 4, 0)
    assert "pytest recoge 4 pruebas en 3 archivos." in corrida.pantalla, corrida.pantalla
    assert "Se van a correr 3 archivos de pruebas" in corrida.pantalla, corrida.pantalla
    assert sorted(p.name for p in corrida.carpeta.glob("*.log")) == [
        "foo_test.log", "recoleccion.log", "test_a.log", "test_b.log"]
    orden = re.findall(r"^\[\d/3\] (tests/\S+)$", corrida.pantalla, re.M)
    assert orden == ["tests/foo_test.py", "tests/sub/test_b.py", "tests/test_a.py"], orden


def test_pytest_addopts_no_deselecciona_pruebas_y_se_avisa(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a1():\n    pass\n\n\ndef test_a2():\n    pass\n",
        "test_b.py": "def test_b1():\n    pass\n",
    })
    valor = "-k nada_que_coincida"
    aviso = f"Se ignoró PYTEST_ADDOPTS={valor}: puede deseleccionar pruebas."
    corrida = _correr(proyecto, entorno={"PYTEST_ADDOPTS": valor})
    assert corrida.codigo == 0, corrida.pantalla
    # con la variable puesta pytest no habría corrido ninguna: se ignora al recoger y en cada archivo
    assert _cifras(corrida.informe) == (3, 0, 0, 0, 0)
    assert _completitud(corrida.informe) == (3, 3, 0)
    assert corrida.informe.count(aviso) == 1, corrida.informe
    en_vivo = corrida.pantalla.split("RESULTADO DE LAS PRUEBAS")[0]
    assert en_vivo.count(aviso) == 1 and en_vivo.index(aviso) < en_vivo.index("pytest recoge"), en_vivo
    # sin la variable, o con ella vacía o en blanco, no hay aviso
    for entorno in ({}, {"PYTEST_ADDOPTS": ""}, {"PYTEST_ADDOPTS": "   "}):
        limpia = _correr(proyecto, entorno=entorno)
        assert limpia.codigo == 0, limpia.pantalla
        assert "PYTEST_ADDOPTS" not in limpia.pantalla and "PYTEST_ADDOPTS" not in limpia.informe


def test_una_prueba_que_pytest_recoge_y_no_termina_no_pasa_aunque_pytest_salga_con_0(tmp_path):
    # una prueba que un gancho del conftest se traga: pytest sale con 0 y su XML no trae ni una entrada rara
    tragada = _proyecto(tmp_path / "tragada", {"test_a_tragada.py": """
        def test_uno():
            pass


        def test_tragada():
            pass


        def test_tres():
            pass
    """}, conftest=CONFTEST_QUE_TRAGA_UNA_PRUEBA)
    codigo, salida = _ejecutar([sys.executable, "-m", "pytest", "tests/test_a_tragada.py", "-q", "-p", "no:cacheprovider"],
                               tragada)
    assert codigo == 0 and "2 passed" in salida, salida
    corrida = _correr(tragada)
    assert corrida.codigo == 1, corrida.pantalla
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in corrida.informe
    assert _cifras(corrida.informe) == (2, 0, 0, 0, 1), corrida.informe
    assert _completitud(corrida.informe) == (3, 2, 1), corrida.informe
    assert "pytest recogió 3 pruebas y solo 2 terminaron (falta 1)" in corrida.informe, corrida.informe
    assert _seccion(corrida.informe, "Pruebas recogidas que no terminaron:") == [
        "tests/test_a_tragada.py - pytest recogió 3 pruebas y solo 2 terminaron (falta 1)"], corrida.informe
    # a mitad del archivo pytest sale con 0 por una orden de la propia prueba
    cortado = _proyecto(tmp_path / "cortado", {"test_a_cortado.py": """
        import pytest


        def test_antes():
            pass


        def test_corta():
            pytest.exit("alto con codigo 0", returncode=0)


        def test_despues():
            assert False, "nunca corre"
    """})
    corrida = _correr(cortado)
    assert corrida.codigo == 1, corrida.pantalla
    assert _completitud(corrida.informe) == (3, 1, 2), corrida.informe
    problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "tests/test_a_cortado.py - " in problemas
    assert "pytest recogió 3 pruebas y solo 1 terminó (faltan 2)" in problemas, problemas
    assert "tests/test_a_cortado.py - pytest recogió 3 pruebas y solo 1 terminó (faltan 2)" in corrida.informe
    # pytest que muere a mitad sin dejar XML: ninguna de sus pruebas recogidas terminó
    sin_xml = _proyecto(tmp_path / "sin_xml", {"test_a_sale.py": """
        import os


        def test_uno():
            pass


        def test_sale_sin_dejar_xml():
            os._exit(0)


        def test_tres():
            pass
    """})
    corrida = _correr(sin_xml)
    assert corrida.codigo == 1, corrida.pantalla
    assert _completitud(corrida.informe) == (3, 0, 3), corrida.informe
    assert "pytest recogió 3 pruebas y ninguna terminó (faltan 3)" in corrida.informe, corrida.informe
    for texto in (corrida.informe, corrida.pantalla):
        assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in texto
    # un archivo con pruebas recogidas que al correrlo se omite entero no es un archivo omitido entero
    omitido = _proyecto(tmp_path / "omitido", {"test_a_omitido.py": """
        import sys

        import pytest

        if "--collect-only" not in sys.argv:
            pytest.skip("se omite solo al correrlo", allow_module_level=True)


        def test_uno():
            pass


        def test_dos():
            pass
    """})
    corrida = _correr(omitido)
    assert corrida.codigo == 1, corrida.pantalla
    assert _completitud(corrida.informe) == (2, 0, 2), corrida.informe
    problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "pytest terminó con código 5" in problemas, problemas
    assert "pytest recogió 2 pruebas y ninguna terminó (faltan 2)" in problemas, problemas
    assert "archivo omitido entero" not in corrida.pantalla
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in corrida.informe


def test_un_modulo_que_no_se_puede_importar_no_impide_comprobar_los_demas(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a_roto.py": "import modulo_que_no_existe_xyz\n\n\ndef test_x():\n    pass\n",
        "test_b_bueno.py": "def test_ok():\n    pass\n\n\ndef test_ok2():\n    pass\n",
    })
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    # el bueno se recoge y se corre; el roto da su error al correrse
    assert "pytest recoge 2 pruebas en 1 archivo." in corrida.pantalla, corrida.pantalla
    assert _completitud(corrida.informe) == (2, 2, 0), corrida.informe
    assert _cifras(corrida.informe)[0] == 2 and _cifras(corrida.informe)[4] == 1
    nota = "La recolección terminó con código 2: pytest informó errores al recoger."
    en_vivo = corrida.pantalla.split("RESULTADO DE LAS PRUEBAS")[0]
    assert nota in en_vivo and nota in corrida.informe
    assert "No se pudo comprobar" not in corrida.informe
    problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "tests/test_a_roto.py - pytest terminó con código 2" in problemas, problemas
    assert "test_b_bueno" not in problemas
    assert "VEREDICTO: HAY PRUEBAS QUE FALLARON O ARCHIVOS CON PROBLEMA" in corrida.informe


@SOLO_POSIX
def test_si_la_recoleccion_vence_su_plazo_se_corre_por_patron_y_el_veredicto_es_condicional(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"}, conftest=CONFTEST_QUE_DUERME_AL_RECOGER)
    motivo = "la recolección superó su plazo de 15 [s] y se detuvo"
    try:
        corrida = _correr(proyecto, "--plazo-recoleccion", "15", limite=300)
        # la recolección duerme 300 [s]: si se respetó el plazo, la corrida no los esperó
        assert corrida.segundos < 250, corrida.segundos
        assert corrida.codigo == 1, corrida.pantalla
        assert _cifras(corrida.informe) == (1, 0, 0, 0, 0), corrida.informe
        en_vivo = corrida.pantalla.split("RESULTADO DE LAS PRUEBAS")[0]
        for texto in (en_vivo, corrida.informe):
            assert f"No se pudo comprobar que se corrieran todas las pruebas: {motivo}." in texto, texto
        assert "Pruebas recogidas por pytest: sin comprobar" in corrida.informe
        assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe
        assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in corrida.informe
        hijo, nieto = _leer_pids(proyecto)
        assert _esperar_muerte(hijo), "el pytest de la recolección sigue vivo"
        assert _esperar_muerte(nieto), "el nieto de la recolección sigue vivo: no se detuvo el grupo"
    finally:
        _matar_la_recoleccion(proyecto)


CONFTEST_QUE_RETIENE_LA_SALIDA = """
    import subprocess
    import sys
    from pathlib import Path


    def pytest_collection_finish(session):
        if "--collect-only" not in sys.argv:
            return
        capman = session.config.pluginmanager.getplugin("capturemanager")
        with capman.global_and_fixture_disabled():
            hijo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)  # ESCAPADO_DE_LA_RECOLECCION"],
                                    start_new_session=True)
        (Path(__file__).resolve().parent.parent / "pids.txt").write_text(str(hijo.pid))
"""


@SOLO_POSIX
def test_si_un_proceso_fuera_del_grupo_retiene_la_salida_de_la_recoleccion_no_se_puede_comprobar(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"}, conftest=CONFTEST_QUE_RETIENE_LA_SALIDA)
    try:
        codigo, pantalla, carpeta = _correr_con_constantes(proyecto, {"GRACIA_DE_SALIDA": 1.0}, limite=300)
        informe = (carpeta / "informe.txt").read_text(encoding="utf-8")
        assert codigo == 1, pantalla
        assert _cifras(informe) == (1, 0, 0, 0, 0)
        motivo = "un proceso fuera del grupo mantiene abierta la salida de la recolección"
        en_vivo = pantalla.split("RESULTADO DE LAS PRUEBAS")[0]
        for texto in (en_vivo, informe):
            assert f"No se pudo comprobar que se corrieran todas las pruebas: {motivo}." in texto, texto
        assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in informe
    finally:
        if (proyecto / "pids.txt").exists():
            _matar_si_es_nuestro(_leer_pids(proyecto)[0], "ESCAPADO_DE_LA_RECOLECCION")


CASOS_DE_RECOLECCION_QUE_NO_SIRVE = (
    # (qué pasa al recoger, motivo que se informa)
    ("cae", "la recolección falló: pytest terminó con código 3 (error interno de pytest)"),
    ("no_lista_nada", "pytest no listó ninguna prueba al recoger"),
)


@pytest.mark.parametrize("caso, motivo", CASOS_DE_RECOLECCION_QUE_NO_SIRVE,
                         ids=[c for c, _ in CASOS_DE_RECOLECCION_QUE_NO_SIRVE])
def test_si_la_recoleccion_no_sirve_se_corre_lo_pedido_y_el_veredicto_es_condicional(tmp_path, caso, motivo):
    if caso == "cae":
        proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"}, conftest=CONFTEST_QUE_CAE_AL_RECOGER)
        corrida = _correr(proyecto)
        esperadas = (1, 0, 0, 0, 0)
    else:
        # al recoger no lista nada y sale con 0 (un conftest lo fuerza), pero el archivo pedido corre bien
        proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"}, conftest="""
            import sys

            import pytest


            def pytest_collection_modifyitems(config, items):
                if "--collect-only" in sys.argv:
                    items[:] = []


            @pytest.hookimpl(trylast=True)
            def pytest_sessionfinish(session, exitstatus):
                if "--collect-only" in sys.argv:
                    session.exitstatus = 0
        """)
        corrida = _correr(proyecto, "tests/test_a.py")
        esperadas = (1, 0, 0, 0, 0)
    assert corrida.codigo == 1, corrida.pantalla
    assert _cifras(corrida.informe) == esperadas, corrida.informe
    en_vivo = corrida.pantalla.split("RESULTADO DE LAS PRUEBAS")[0]
    for texto in (en_vivo, corrida.informe):
        assert f"No se pudo comprobar que se corrieran todas las pruebas: {motivo}." in texto, texto
    for texto in (corrida.pantalla, corrida.informe):
        assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in texto
    assert "Pruebas recogidas por pytest: sin comprobar" in corrida.informe
    assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe
    assert "Se va a correr 1 archivo de pruebas" in corrida.pantalla, corrida.pantalla


def test_un_modulo_roto_fuera_del_patron_tambien_se_corre_y_da_su_error(tmp_path):
    # pytest dice que no puede recoger tests/sub/test_roto.py, pero el patrón tests/test_*.py no lo ve
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a():\n    pass\n",
        "sub/test_roto.py": "import modulo_que_no_existe_xyz\n\n\ndef test_x():\n    pass\n",
    })
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    assert re.search(r"^Archivos: 2 ", corrida.informe, re.M), corrida.informe
    orden = re.findall(r"^\[\d/2\] (tests/\S+)$", corrida.pantalla, re.M)
    assert orden == ["tests/sub/test_roto.py", "tests/test_a.py"], orden
    problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert "tests/sub/test_roto.py - pytest terminó con código 2" in problemas, problemas
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in corrida.informe


def test_un_archivo_del_patron_que_pytest_no_lista_se_corre_como_antes(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a():\n    pass\n",
        "test_b.py": "def test_b1():\n    pass\n\n\ndef test_b2():\n    pass\n",
    })
    # con este patrón pytest no recoge test_b.py por su cuenta, pero el corredor sí lo corre porque es un tests/test_*.py
    (proyecto / "pytest.ini").write_text("[pytest]\npython_files = test_a*.py\n", encoding="utf-8")
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert "pytest recoge 1 prueba en 1 archivo." in corrida.pantalla, corrida.pantalla
    assert re.search(r"^Archivos: 2 ", corrida.informe, re.M), corrida.informe
    assert _cifras(corrida.informe) == (3, 0, 0, 0, 0), corrida.informe
    assert _completitud(corrida.informe) == (1, 1, 0), corrida.informe
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" in corrida.informe and "sin comprobar" not in corrida.informe


@pytest.mark.parametrize("pruebas", [1, 2], ids=["una_prueba", "dos_pruebas"])
def test_un_archivo_que_falla_al_recogerse_junto_con_los_demas_pero_corre_bien_queda_sin_comprobar(tmp_path, pruebas):
    # en un solo proceso su importación falla (como pasaría con un efecto de otro módulo); solo, pasa
    cuerpo = "".join(f"\n\ndef test_b{i}():\n    pass\n" for i in range(1, pruebas + 1))
    proyecto = _proyecto(tmp_path, {
        "test_a_bueno.py": "def test_a():\n    pass\n",
        "test_b_fragil.py": 'import sys\n\nif "--collect-only" in sys.argv:\n    raise ImportError("solo falla al recoger")\n' + cuerpo,
    })
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        assert _cifras(corrida.informe) == (1 + pruebas, 0, 0, 0, 0), corrida.informe
        # el archivo bueno sí se comprueba; el frágil no tiene con qué compararse
        assert _completitud(corrida.informe) == (1, 1, 0), corrida.informe
        assert "La recolección terminó con código 2" in corrida.informe
        assert "No se pudo comprobar que se corrieran todas las pruebas: la recolección no pudo listar" in corrida.informe
        assert _seccion(corrida.informe, "Archivos sin comprobar:") == [
            f"tests/test_b_fragil.py - terminaron {'1 prueba' if pruebas == 1 else '2 pruebas'}"]
        assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe
        assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in corrida.informe


def test_un_proyecto_sano_cuadra_recogidas_y_corridas_en_vivo_y_repartido(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    proyecto = _proyecto(tmp_path, {
        "test_p.py": """
            import pytest


            @pytest.mark.parametrize("a", range(4))
            @pytest.mark.parametrize("b", range(3))
            def test_producto(a, b):
                assert a * b >= 0


            @pytest.mark.parametrize("texto", ["x", "y", "z"], ids=["uno", "dos", "tres"])
            def test_texto(texto):
                assert texto
        """,
        "test_q.py": """
            class TestGrupo:
                def test_uno(self):
                    pass

                def test_dos(self):
                    pass


            def test_suelta():
                pass
        """,
    })
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 0, corrida.pantalla
        assert _cifras(corrida.informe) == (18, 0, 0, 0, 0)
        for texto in (corrida.informe, corrida.pantalla):
            assert "Pruebas recogidas por pytest: 18; corridas: 18; faltan: 0" in texto, texto
            assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" in texto
            assert "No se pudo comprobar" not in texto and "PYTEST_ADDOPTS" not in texto
        assert "pytest recoge 18 pruebas en 2 archivos." in corrida.pantalla, corrida.pantalla
        assert "Pruebas recogidas que no terminaron" not in corrida.informe
        assert "Avisos:" not in corrida.informe


def test_con_argumentos_solo_se_recogen_y_comprueban_esos_archivos(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a1():\n    pass\n\n\ndef test_a2():\n    pass\n\n\ndef test_a3():\n    pass\n",
        "test_b.py": "def test_b():\n    pass\n",
        "test_c_roto.py": "import modulo_que_no_existe_xyz\n\n\ndef test_c():\n    pass\n",
    })
    corrida = _correr(proyecto, "tests/test_a.py")
    assert corrida.codigo == 0, corrida.pantalla
    assert "pytest recoge 3 pruebas en 1 archivo." in corrida.pantalla, corrida.pantalla
    assert _completitud(corrida.informe) == (3, 3, 0), corrida.informe
    registro = (corrida.carpeta / "recoleccion.log").read_text(encoding="utf-8")
    assert "tests/test_a.py: 3" in registro, registro
    # ni el otro archivo ni el módulo roto que no se pidió entran en la recolección
    assert "test_b" not in registro and "test_c_roto" not in registro and "Interrupted" not in registro, registro
    assert "La recolección terminó con código 2" not in corrida.informe
    dos = _correr(proyecto, "tests/test_a.py", "tests/test_b.py")
    assert dos.codigo == 0, dos.pantalla
    assert _completitud(dos.informe) == (4, 4, 0), dos.informe


def test_un_error_de_cierre_no_es_un_problema_de_completitud_pero_un_duplicado_no_oculta_lo_que_falta(tmp_path):
    cierre = _proyecto(tmp_path / "cierre", {"test_cierre.py": CIERRE_ROTO + """

    def test_pasa_y_rompe_su_cierre(roto_al_cerrar):
        pass


    def test_normal():
        pass
    """})
    corrida = _correr(cierre)
    assert corrida.codigo == 1, corrida.pantalla
    # la prueba que pasa y rompe su cierre cuenta como pasada y, además, como error
    assert _cifras(corrida.informe) == (2, 0, 1, 0, 0), corrida.informe
    assert _completitud(corrida.informe) == (2, 2, 0), corrida.informe
    assert "Archivos con problema: ninguno" in corrida.informe
    assert "Pruebas recogidas que no terminaron" not in corrida.informe
    # la prueba que falla y rompe su cierre aparece dos veces en el XML, y una prueba tragada no aparece
    duplicado = _proyecto(tmp_path / "duplicado", {"test_dup.py": CIERRE_ROTO + """

    def test_falla_y_rompe_su_cierre(roto_al_cerrar):
        assert False


    def test_pasa():
        pass


    def test_tragada():
        pass
    """}, conftest=CONFTEST_QUE_TRAGA_UNA_PRUEBA)
    corrida = _correr(duplicado)
    assert corrida.codigo == 1, corrida.pantalla
    entradas = list(ET.parse(corrida.carpeta / "test_dup.xml").getroot().iter("testcase"))
    assert len(entradas) == 3, "el XML debía traer una entrada de más para que el caso discrimine"
    assert _completitud(corrida.informe) == (3, 2, 1), corrida.informe
    assert "tests/test_dup.py - pytest recogió 3 pruebas y solo 2 terminaron (falta 1)" in corrida.informe


@SOLO_POSIX
@pytest.mark.parametrize("nombre_senal", ["SIGINT", "SIGTERM"])
def test_una_interrupcion_durante_la_recoleccion_deja_el_informe_parcial_y_nada_vivo(tmp_path, nombre_senal):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_a():\n    pass\n"}, conftest=CONFTEST_QUE_DUERME_AL_RECOGER)
    carpeta = proyecto / "salida"
    proc = _lanzar(_orden_del_corredor(proyecto, carpeta), proyecto)
    try:
        assert _esperar_pids(proyecto / "pids.txt", proc), "la recolección no llegó a arrancar"
        hijo, nieto = _leer_pids(proyecto)
        proc.send_signal(getattr(signal, nombre_senal))
        pantalla = _esperar(proc, 240)
        assert proc.returncode == 130, pantalla
        informe = (carpeta / "informe.txt").read_text(encoding="utf-8")
        lineas = informe.splitlines()
        assert "INTERRUMPIDA" in lineas[0], lineas[0]
        assert "VEREDICTO: CORRIDA INTERRUMPIDA, SIN VEREDICTO" in lineas, lineas
        assert "TODAS LAS PRUEBAS" not in informe
        assert not (carpeta / "test_a.log").exists(), "no debía correr ningún archivo"
        assert _esperar_muerte(hijo), "el pytest de la recolección sigue vivo"
        assert _esperar_muerte(nieto), "el nieto de la recolección sigue vivo"
    finally:
        _detener(proc)
        _matar_la_recoleccion(proyecto)


def test_un_archivo_sano_no_dispara_ninguna_regla_aunque_dure_mas_que_el_silencio(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    proyecto = _proyecto(tmp_path, {
        "test_a_lento.py": """
            import time

            import pytest


            @pytest.mark.parametrize("n", range(30))
            def test_corta(n):
                time.sleep(0.25)
        """,
        "test_b_ruidoso.py": """
            def test_imprime_mucho():
                for i in range(3000):
                    print(f"{i:06d} " + "x" * 100)
        """,
        "test_c_variado.py": """
            import pytest


            @pytest.mark.skip(reason="se omite a proposito")
            def test_omitida():
                pass


            @pytest.mark.xfail(reason="se espera que falle")
            def test_xfail():
                assert False


            @pytest.mark.xfail(reason="no debia pasar")
            def test_xpass():
                pass


            @pytest.mark.parametrize("n", range(5))
            def test_param(n):
                assert n >= 0
        """,
    })
    corrida = _correr(proyecto, "--silencio-max", "6", "--aviso-cada", "5", "--plazo-recoleccion", "60", limite=300)
    assert corrida.codigo == 0, corrida.pantalla
    assert _cifras(corrida.informe) == (37, 0, 0, 1, 0), corrida.informe
    assert _completitud(corrida.informe) == (39, 39, 0), corrida.informe
    # el archivo lento dura más que el silencio permitido (6 [s]) y escribe cada 0.25 [s]: es la condición para que
    # el caso discrimine, con un hueco entre salidas mucho menor que el silencio
    duracion = float(re.search(r"^\s*\d+\.\s+([0-9.]+) \[s\]  tests/test_a_lento\.py$", corrida.informe, re.M).group(1))
    assert duracion > 6, duracion
    for texto in (corrida.informe, corrida.pantalla):
        assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" in texto
        for ausente in ("detenido", "ARCHIVO CON PROBLEMA", "AVISO", "INTERRUMPIDA", "No se pudo comprobar",
                        "PYTEST_ADDOPTS"):
            assert ausente not in texto, f"{ausente!r} no debía aparecer:\n{texto}"
    assert "Archivos con problema: ninguno" in corrida.informe and "Avisos:" not in corrida.informe


def test_un_archivo_llamado_recoleccion_no_pisa_el_registro_de_la_recoleccion(tmp_path):
    proyecto = _proyecto(tmp_path, {"recoleccion.py": "def test_x():\n    pass\n"})
    corrida = _correr(proyecto, "tests/recoleccion.py")
    assert corrida.codigo == 0, corrida.pantalla
    assert "tests/recoleccion.py: 1" in (corrida.carpeta / "recoleccion.log").read_text(encoding="utf-8")
    assert "test session starts" in (corrida.carpeta / "recoleccion_2.log").read_text(encoding="utf-8")
    assert (corrida.carpeta / "recoleccion_2.xml").exists()


def test_un_proyecto_sin_archivos_de_pruebas_da_codigo_2(tmp_path):
    proyecto = _proyecto(tmp_path, {})
    corrida = _correr(proyecto)
    assert corrida.codigo == 2, corrida.pantalla
    assert "no hay archivos de pruebas que correr" in corrida.pantalla, corrida.pantalla
    assert "Traceback" not in corrida.pantalla and "VEREDICTO" not in corrida.pantalla
    assert "a correr" not in corrida.pantalla, "no debía anunciar que corría archivos"


# ---------------------- el color, los errores al recoger, lo omitido y los complementos de pytest

def test_el_color_que_pide_el_entorno_no_llega_a_la_pantalla_ni_al_informe_ni_a_los_registros(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": """
        import os


        def test_pasa():
            pass


        def test_falla():
            assert 1 == 2


        def test_el_hijo_no_hereda_el_color_del_llamador():
            assert not {"FORCE_COLOR", "PY_COLORS", "NO_COLOR"} & set(os.environ)
    """})
    for entorno in ({"FORCE_COLOR": "1"}, {"PY_COLORS": "1"}, {"FORCE_COLOR": "1", "PY_COLORS": "1", "NO_COLOR": "1"}):
        for argumentos in ((), ("--procesos", "2")):
            corrida = _correr(proyecto, *argumentos, entorno=entorno)
            assert corrida.codigo == 1, corrida.pantalla
            assert _cifras(corrida.informe) == (2, 1, 0, 0, 0), corrida.informe
            assert "\x1b[" not in corrida.pantalla and "\x1b[" not in corrida.informe, (entorno, argumentos)
            for registro in corrida.carpeta.glob("*.log"):
                assert "\x1b[" not in registro.read_text(encoding="utf-8"), registro.name
            if not argumentos:
                assert "test_pasa PASSED" in corrida.pantalla, corrida.pantalla


def test_un_conftest_roto_en_una_carpeta_deja_la_comprobacion_sin_hacer_y_nunca_dice_que_todo_paso(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_pasa():\n    pass\n",
        "sub/test_b.py": "def test_falla():\n    assert False\n",
        "sub/conftest.py": "import modulo_que_no_existe_xyz\n",
    })
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        for texto in (corrida.informe, corrida.pantalla):
            assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in texto
            assert "pytest informó errores al recoger que no son de ningún archivo que se corra: tests/sub" in texto, texto
        assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe
        assert _cifras(corrida.informe) == (1, 0, 0, 0, 0), corrida.informe


CONFTEST_QUE_RECOGE_YAML = """
    import pytest


    class Archivo(pytest.File):
        def collect(self):
            yield Caso.from_parent(self, name="caso_yaml")


    class Caso(pytest.Item):
        def runtest(self):
            raise AssertionError("EL CASO YAML FALLA")


    def pytest_collect_file(parent, file_path):
        if file_path.suffix == ".yaml":
            return Archivo.from_parent(parent, path=file_path)
"""


def test_pruebas_que_pytest_recoge_en_un_archivo_que_no_es_py_dejan_la_comprobacion_sin_hacer(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_pasa():\n    pass\n", "casos.yaml": "uno: 1\n"},
                         conftest=CONFTEST_QUE_RECOGE_YAML)
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        motivo = "pytest listó pruebas en tests/casos.yaml, que el corredor no corre"
        for texto in (corrida.informe, corrida.pantalla):
            assert f"No se pudo comprobar que se corrieran todas las pruebas: {motivo}." in texto, texto
            assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in texto
        assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe


def test_pruebas_que_pytest_recoge_fuera_de_la_raiz_dejan_la_comprobacion_sin_hacer(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_pasa():\n    pass\n"})
    (proyecto / "pytest.ini").write_text("[pytest]\ntestpaths = tests ../hermano\n", encoding="utf-8")
    (tmp_path / "hermano").mkdir()
    (tmp_path / "hermano" / "test_h.py").write_text("def test_falla():\n    assert False\n", encoding="utf-8")
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    assert "pytest listó pruebas en test_h.py, que el corredor no corre" in corrida.informe, corrida.informe
    assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in corrida.pantalla


def test_una_carpeta_con_espacios_se_corre_y_su_falla_se_ve(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_pasa():\n    pass\n",
        "sub dir/test_b.py": "def test_falla():\n    assert False\n",
    })
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        assert _cifras(corrida.informe) == (1, 1, 0, 0, 0), corrida.informe
        assert _completitud(corrida.informe) == (2, 2, 0), corrida.informe
        assert _seccion(corrida.informe, "Fallaron:")[0].startswith("tests/sub dir/test_b.py::test_falla"), corrida.informe
        assert "HAY PRUEBAS QUE FALLARON" in corrida.informe


def test_un_conftest_que_fuerza_el_codigo_0_no_esconde_un_modulo_roto_fuera_del_patron(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a():\n    pass\n",
        "foo_test.py": "import modulo_que_no_existe_xyz\n\n\ndef test_f():\n    assert False\n",
    }, conftest="""
        def pytest_sessionfinish(session, exitstatus):
            session.exitstatus = 0
    """)
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        assert re.search(r"^Archivos: 2 ", corrida.informe, re.M), corrida.informe
        assert "La recolección terminó con código 0: pytest informó errores al recoger" in corrida.informe, corrida.informe
        problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
        assert "tests/foo_test.py - pytest terminó con 0 pero su resultado trae fallas o errores" in problemas, problemas
        assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in corrida.informe


ARCHIVO_QUE_SE_OMITE_ENTERO = """
    import pytest

    pytest.skip("faltan las bases de referencia", allow_module_level=True)


    def test_x():
        pass
"""


def test_pedir_solo_archivos_que_se_omiten_enteros_no_es_una_falsa_alarma(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_pide_bases.py": ARCHIVO_QUE_SE_OMITE_ENTERO})
    veredicto = "VEREDICTO: NINGUNA PRUEBA FALLÓ; NO CORRIÓ NINGUNA: TODO LO PEDIDO SE OMITIÓ ENTERO"
    for argumentos in ((), ("tests/test_pide_bases.py",)):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 0, corrida.pantalla
        for texto in (corrida.informe, corrida.pantalla):
            assert veredicto in texto, texto
            assert "No se pudo comprobar" not in texto and "TODAS LAS PRUEBAS PASARON" not in texto
        assert "Ninguna prueba corrió: todo lo pedido se omitió entero" in corrida.informe
        assert _cifras(corrida.informe) == (0, 0, 0, 1, 0), corrida.informe
        assert _seccion(corrida.informe, "Omitidas, con su motivo:") == [
            "tests/test_pide_bases.py - faltan las bases de referencia"]
    # si además hay un archivo que corre pruebas, el veredicto de siempre; si falla, el de las fallas
    mixto = _proyecto(tmp_path / "mixto", {"test_pide_bases.py": ARCHIVO_QUE_SE_OMITE_ENTERO,
                                           "test_b.py": "def test_b():\n    pass\n"})
    corrida = _correr(mixto)
    assert corrida.codigo == 0 and "VEREDICTO: TODAS LAS PRUEBAS PASARON" in corrida.informe, corrida.pantalla
    assert "Ninguna prueba corrió" not in corrida.informe


def test_si_pytest_no_lista_nada_pero_un_archivo_corre_pruebas_la_comprobacion_queda_sin_hacer(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a_fragil.py": """
        import sys

        import pytest

        if "--collect-only" in sys.argv:
            pytest.skip("solo se omite al recoger", allow_module_level=True)


        def test_uno():
            pass


        def test_dos():
            pass
    """})
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    assert _seccion(corrida.informe, "Archivos sin comprobar:") == ["tests/test_a_fragil.py - terminaron 2 pruebas"]
    assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe
    assert "NINGUNA PRUEBA FALLÓ" not in corrida.informe


COMPLEMENTO_QUE_DESELECCIONA = """
    def pytest_collection_modifyitems(config, items):
        quitadas = [i for i in items if i.name == "test_falla"]
        if quitadas:
            config.hook.pytest_deselected(items=quitadas)
            items[:] = [i for i in items if i.name != "test_falla"]
"""


def test_un_complemento_que_deselecciona_se_avisa_y_las_deseleccionadas_se_listan_sin_cambiar_el_veredicto(tmp_path):
    fuente = "def test_pasa():\n    pass\n\n\ndef test_falla():\n    assert False\n"
    # por PYTEST_PLUGINS: se conserva (puede ser legítima) pero se avisa al empezar y en el informe
    proyecto = _proyecto(tmp_path / "plugins", {"test_a.py": fuente})
    (proyecto / "deselector.py").write_text(_fuente(COMPLEMENTO_QUE_DESELECCIONA), encoding="utf-8")
    corrida = _correr(proyecto, entorno={"PYTEST_PLUGINS": "deselector", "PYTHONPATH": str(proyecto)})
    aviso = "Está definida PYTEST_PLUGINS=deselector: un complemento puede deseleccionar pruebas. No se quitó."
    assert corrida.codigo == 0, corrida.pantalla
    assert corrida.informe.count(aviso) == 1, corrida.informe
    en_vivo = corrida.pantalla.split("RESULTADO DE LAS PRUEBAS")[0]
    assert en_vivo.count(aviso) == 1 and en_vivo.index(aviso) < en_vivo.index("pytest recoge"), en_vivo
    # el complemento siguió actuando: la prueba que falla no corrió, y el informe lo dice sin cambiar el veredicto
    assert _cifras(corrida.informe) == (1, 0, 0, 0, 0), corrida.informe
    assert _seccion(corrida.informe, "Avisos:") == ["tests/test_a.py - pytest dejó 1 prueba sin seleccionar (deselected)"]
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" in corrida.informe
    # lo mismo vale para un conftest, sin la variable: solo el aviso de lo deseleccionado
    con_conftest = _proyecto(tmp_path / "conftest", {"test_a.py": fuente}, conftest=COMPLEMENTO_QUE_DESELECCIONA)
    corrida = _correr(con_conftest)
    assert corrida.codigo == 0 and "PYTEST_PLUGINS" not in corrida.informe, corrida.pantalla
    assert _seccion(corrida.informe, "Avisos:") == ["tests/test_a.py - pytest dejó 1 prueba sin seleccionar (deselected)"]
    assert "AVISO: pytest dejó 1 prueba sin seleccionar" in corrida.pantalla, corrida.pantalla


def test_con_pedidos_que_pytest_no_pudo_recoger_el_corredor_los_corre_y_da_su_error(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_a():\n    pass\n",
        "test_roto.py": "import modulo_que_no_existe_xyz\n\n\ndef test_x():\n    pass\n",
    })
    for argumentos in (("tests/test_a.py", "tests/test_roto.py"), ("--procesos", "2", "tests/test_a.py", "tests/test_roto.py")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        pasaron, fallaron, errores, omitidas, problemas = _cifras(corrida.informe)
        assert (pasaron, errores, problemas) == (1, 1, 1), corrida.informe
        assert "tests/test_roto.py - pytest terminó con código 2" in " ".join(
            _seccion(corrida.informe, "Archivos con problema:")), corrida.informe


def test_la_recoleccion_se_hace_con_el_entorno_de_los_hijos_y_no_con_el_del_llamador(tmp_path, monkeypatch):
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    proyecto = _proyecto(tmp_path, {"test_qt_al_importar.py": """
        import os

        assert os.environ.get("QT_QPA_PLATFORM") == "offscreen", "se importó con el entorno del llamador"


        def test_x():
            pass
    """})
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert "pytest recoge 1 prueba en 1 archivo." in corrida.pantalla, corrida.pantalla
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" in corrida.informe


def test_un_archivo_cuyo_numero_de_pruebas_depende_de_otro_modulo_dice_cuantas_recogio_al_correrse_solo(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "registro.py": "AMPLIACIONES = []\n",
        "test_a_amplia.py": "import registro\n\nregistro.AMPLIACIONES.append('extra')\n\n\ndef test_a():\n    pass\n",
        "test_b_recorre.py": ("import pytest\n\nimport registro\n\n\n@pytest.mark.parametrize('valor', ['base'] + registro.AMPLIACIONES)\n"
                              "def test_b(valor):\n    pass\n"),
    })
    corrida = _correr(proyecto)
    assert corrida.codigo == 1, corrida.pantalla
    problemas = " ".join(_seccion(corrida.informe, "Archivos con problema:"))
    assert ("tests/test_b_recorre.py - pytest recogió 2 pruebas y solo 1 terminó (falta 1); "
            "al correrse solo, pytest recogió 1") in problemas, problemas


def test_la_configuracion_de_la_raiz_es_la_primera_que_pytest_reconoce(tmp_path):
    corredor = _cargar_corredor()
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    solo_la_raiz = ["--rootdir", str(raiz)]
    assert corredor.argumentos_de_raiz(raiz) == solo_la_raiz
    # un tox.ini o un setup.cfg sin la sección de pytest no son configuración de pytest
    (raiz / "tox.ini").write_text("[tox]\nenvlist = py\n", encoding="utf-8")
    (raiz / "setup.cfg").write_text("[metadata]\nname = x\n", encoding="utf-8")
    (raiz / "pyproject.toml").write_text("[tool.black]\nline-length = 100\n", encoding="utf-8")
    assert corredor.argumentos_de_raiz(raiz) == solo_la_raiz
    (raiz / "setup.cfg").write_text("[tool:pytest]\naddopts = -q\n", encoding="utf-8")
    assert corredor.argumentos_de_raiz(raiz) == solo_la_raiz + ["-c", str(raiz / "setup.cfg")]
    (raiz / "tox.ini").write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    assert corredor.argumentos_de_raiz(raiz) == solo_la_raiz + ["-c", str(raiz / "tox.ini")]
    (raiz / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = '-q'\n", encoding="utf-8")
    assert corredor.argumentos_de_raiz(raiz) == solo_la_raiz + ["-c", str(raiz / "pyproject.toml")]
    # un pytest.ini vale aunque esté vacío y manda sobre los demás
    (raiz / "pytest.ini").write_text("", encoding="utf-8")
    assert corredor.argumentos_de_raiz(raiz) == solo_la_raiz + ["-c", str(raiz / "pytest.ini")]


def test_las_cuentas_que_el_corredor_no_corre_son_todo_lo_del_bloque_que_no_es_un_py_bajo_la_raiz(tmp_path):
    corredor = _cargar_corredor()
    _crear_archivos(tmp_path, "tests/test_a.py", "tests/datos.csv", "tests/paquete.py/__init__.py")
    (tmp_path / "tests" / "datos").mkdir()
    bloque = "\n".join(["tests/test_a.py: 3", "tests/datos: 1", "tests/datos.csv: 4", "tests/paquete.py: 2",
                        "tests/virtual: 5", "tests/virtual: 6"]) + "\n"
    # una carpeta (aunque se llame x.py), un archivo de datos y una ruta inventada: ninguna se corre
    assert corredor.cuentas_que_el_corredor_no_corre(bloque, tmp_path) == [
        "tests/datos", "tests/datos.csv", "tests/paquete.py", "tests/virtual"]
    # solo cuenta el bloque del principio, hasta la primera línea vacía: lo que sigue es el detalle de los errores
    despues = bloque.split("\n")[0] + "\n\nE   tests/otro: 9\ntests/otra_carpeta: 2\n"
    assert corredor.cuentas_que_el_corredor_no_corre(despues, tmp_path) == []
    assert corredor.leer_recogidas(despues, tmp_path) == {"tests/test_a.py": 3}
    for salida, motivo in ((bloque, "tests/datos, tests/datos.csv, tests/paquete.py, tests/virtual"),
                           ("tests/test_a.py: 3\ntests/datos: 1\n", "tests/datos")):
        recogidas, razon, nota, con_error = corredor.evaluar_recoleccion(0, salida, tmp_path)
        assert recogidas is None and razon == f"pytest listó pruebas en {motivo}, que el corredor no corre", razon


def test_un_error_al_recoger_se_atribuye_a_su_archivo_con_espacios_en_la_ruta_o_con_clase(tmp_path):
    corredor = _cargar_corredor()
    _crear_archivos(tmp_path, "tests/sub dir/foo_test.py", "tests/bar_test.py")
    con_espacios = "ERROR tests/sub dir/foo_test.py - ImportError: no se pudo\n"
    assert corredor.leer_errores_al_recoger(con_espacios, tmp_path) == ["tests/sub dir/foo_test.py"]
    contados = con_espacios + "!!!! Interrupted: 1 error during collection !!!!\n"
    assert corredor.errores_al_recoger_sin_archivo(contados, tmp_path) == []
    assert corredor.evaluar_recoleccion(2, "tests/sub dir/foo_test.py: 1\n" + contados, tmp_path)[3] == ["tests/sub dir/foo_test.py"]
    # un error de clase («ruta.py::Clase») es del archivo; dos clases rotas de un mismo archivo son dos errores de ese archivo
    de_clase = "ERROR tests/bar_test.py::TestA - Failed: x\nERROR tests/bar_test.py::TestB - Failed: y\n"
    assert corredor.leer_errores_al_recoger(de_clase, tmp_path) == ["tests/bar_test.py"]
    assert corredor.errores_al_recoger_sin_archivo(de_clase + "!!!! Interrupted: 2 errors during collection !!!!\n", tmp_path) == []
    assert corredor.errores_al_recoger_sin_archivo(de_clase + "!!!! Interrupted: 3 errors during collection !!!!\n", tmp_path) == [
        "1 error sin nombre"]


def _log_de_pytest(tmp_path, lineas):
    ruta = tmp_path / "archivo.log"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def test_las_deseleccionadas_se_leen_de_la_linea_final_de_pytest_y_no_de_cualquier_linea_con_igual(tmp_path):
    corredor = _cargar_corredor()
    impresa = "===== 3 deselected in 0.01s ====="
    final = lambda cifras: f"=========== {cifras} in 0.02s ==========="  # noqa: E731
    assert corredor.deseleccionadas(_log_de_pytest(tmp_path, ["tests/test_d.py::test_a PASSED", impresa, "", final("2 passed")])) == 0
    assert corredor.deseleccionadas(_log_de_pytest(tmp_path, [impresa, "", final("2 passed, 1 deselected")])) == 1
    assert corredor.deseleccionadas(_log_de_pytest(tmp_path, ["PASSED", final("1 passed, 4 deselected"), ""])) == 4
    assert corredor.deseleccionadas(tmp_path / "no_existe.log") == 0


def test_un_ini_anidado_no_cambia_la_configuracion_ni_la_raiz_con_que_se_corre_cada_archivo(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_pasa():\n    pass\n",
        "sub/test_b.py": """
            import os
            import warnings


            def test_avisa():
                warnings.warn("API vieja", DeprecationWarning)


            def test_ensucia():
                os.environ["MARCA_SUCIA"] = "1"
        """,
        "sub/pytest.ini": "[pytest]\n",
    }, conftest="""
        import os

        import pytest


        @pytest.fixture(autouse=True)
        def guarda_de_la_raiz():
            yield
            assert not os.environ.get("MARCA_SUCIA"), "la prueba dejó la marca sucia"
    """)
    (proyecto / "pytest.ini").write_text("[pytest]\nfilterwarnings =\n    error\n", encoding="utf-8")
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        # con la configuración de la raíz el aviso es una falla y la guarda del conftest de la raíz salta
        assert _cifras(corrida.informe) == (2, 1, 1, 0, 0), corrida.informe
        assert _seccion(corrida.informe, "Fallaron:")[0].startswith("tests/sub/test_b.py::test_avisa"), corrida.informe
        assert "tests/sub/test_b.py::test_ensucia" in " ".join(_seccion(corrida.informe, "Errores:")), corrida.informe
        assert "VEREDICTO: HAY PRUEBAS QUE FALLARON" in corrida.informe
        assert "TODAS LAS PRUEBAS PASARON" not in corrida.informe
    # con el archivo pedido, la recolección también usa la raíz y su configuración: lista el archivo con su ruta completa
    corrida = _correr(proyecto, "tests/sub/test_b.py")
    assert corrida.codigo == 1, corrida.pantalla
    assert "pytest recoge 2 pruebas en 1 archivo." in corrida.pantalla, corrida.pantalla
    assert "No se pudo comprobar" not in corrida.informe, corrida.informe


def test_pytest_que_recoge_en_una_carpeta_deja_la_comprobacion_sin_hacer_y_nunca_dice_que_todo_paso(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_a.py": "def test_pasa():\n    pass\n", "datos/casos.cfg": "x\n"}, conftest="""
        import pytest


        class CasoDeDatos(pytest.Item):
            def runtest(self):
                assert False, "el caso de datos falla"


        class Datos(pytest.File):
            def collect(self):
                yield CasoDeDatos.from_parent(self, name="caso_1")


        def pytest_collect_file(file_path, parent):
            if file_path.suffix == ".cfg":
                return Datos.from_parent(parent, path=file_path.parent)
    """)
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        for texto in (corrida.informe, corrida.pantalla):
            assert "No se pudo comprobar que se corrieran todas las pruebas: pytest listó pruebas en tests/datos, que el corredor no corre." in texto
            assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" not in texto
        assert "VEREDICTO: TODAS LAS PRUEBAS CORRIDAS PASARON, SIN COMPROBAR QUE SE CORRIERAN TODAS" in corrida.informe


def test_con_continue_on_collection_errors_y_un_conftest_que_fuerza_el_0_el_modulo_roto_se_corre_y_da_su_error(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_pasa():\n    pass\n",
        "foo_test.py": "import modulo_que_no_existe_xyz\n\n\ndef test_falla():\n    assert False\n",
    }, conftest="""
        def pytest_sessionfinish(session, exitstatus):
            session.exitstatus = 0
    """)
    (proyecto / "pytest.ini").write_text(
        "[pytest]\naddopts = --continue-on-collection-errors\npython_files = test_*.py *_test.py\n", encoding="utf-8")
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        assert re.search(r"^Archivos: 2 ", corrida.informe, re.M), corrida.informe
        assert _cifras(corrida.informe) == (1, 0, 1, 0, 1), corrida.informe
        assert "tests/foo_test.py" in " ".join(_seccion(corrida.informe, "Errores:")), corrida.informe
        assert "La recolección terminó con código 0: pytest informó errores al recoger" in corrida.informe, corrida.informe
        assert "VEREDICTO: HAY PRUEBAS QUE FALLARON" in corrida.informe
        assert "TODAS LAS PRUEBAS PASARON" not in corrida.informe


def test_un_modulo_roto_fuera_del_patron_en_una_carpeta_con_espacios_se_corre_y_da_su_error(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_a.py": "def test_pasa():\n    pass\n",
        "sub dir/foo_test.py": "import modulo_que_no_existe_xyz\n\n\ndef test_falla():\n    assert False\n",
    })
    (proyecto / "pytest.ini").write_text("[pytest]\npython_files = test_*.py *_test.py\n", encoding="utf-8")
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        assert _cifras(corrida.informe) == (1, 0, 1, 0, 1), corrida.informe
        assert "tests/sub dir/foo_test.py" in " ".join(_seccion(corrida.informe, "Errores:")), corrida.informe
        assert "tests/sub dir/foo_test.py" in " ".join(_seccion(corrida.informe, "Archivos con problema:")), corrida.informe
        assert "VEREDICTO: HAY PRUEBAS QUE FALLARON" in corrida.informe
        assert "SIN COMPROBAR" not in corrida.informe


def test_una_clase_que_no_se_puede_recoger_cuenta_como_error_de_su_archivo_aunque_no_siga_el_patron(tmp_path):
    proyecto = _proyecto(tmp_path, {
        "test_ok.py": "def test_ok():\n    pass\n",
        "foo_test.py": """
            import pytest


            class TestA:
                @pytest.mark.parametrize("x", [1])
                def test_m(self):
                    assert False
        """,
    })
    (proyecto / "pytest.ini").write_text("[pytest]\npython_files = test_*.py *_test.py\n", encoding="utf-8")
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 1, corrida.pantalla
        assert _cifras(corrida.informe) == (1, 0, 1, 0, 1), corrida.informe
        assert "tests/foo_test.py" in " ".join(_seccion(corrida.informe, "Archivos con problema:")), corrida.informe
        assert "no son de ningún archivo que se corra" not in corrida.informe, corrida.informe
        assert "VEREDICTO: HAY PRUEBAS QUE FALLARON" in corrida.informe
        assert "TODAS LAS PRUEBAS CORRIDAS PASARON" not in corrida.informe


def test_algo_que_un_modulo_imprime_al_importarse_no_entra_en_la_recoleccion_aunque_el_ini_apague_la_captura(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_f.py": """
        print("tests/datos.csv: 3")


        def test_pasa():
            pass
    """, "datos.csv": "a,b\n"})
    (proyecto / "pytest.ini").write_text("[pytest]\naddopts = -s\n", encoding="utf-8")
    for argumentos in ((), ("--procesos", "2")):
        corrida = _correr(proyecto, *argumentos)
        assert corrida.codigo == 0, corrida.pantalla
        assert "pytest recoge 1 prueba en 1 archivo." in corrida.pantalla, corrida.pantalla
        assert "No se pudo comprobar" not in corrida.informe and "VEREDICTO: TODAS LAS PRUEBAS PASARON" in corrida.informe


def test_una_prueba_que_imprime_un_texto_con_deselected_no_levanta_un_aviso_falso(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_d.py": """
        def test_imprime():
            print("===== 3 deselected in 0.01s =====")


        def test_pasa():
            pass
    """})
    corrida = _correr(proyecto)
    assert corrida.codigo == 0, corrida.pantalla
    assert "pytest dejó" not in corrida.informe and "AVISO" not in corrida.pantalla, corrida.informe
    assert "VEREDICTO: TODAS LAS PRUEBAS PASARON" in corrida.informe


@SOLO_POSIX
def test_con_la_salida_sin_bufer_y_un_codec_ascii_la_pantalla_conserva_las_tildes(tmp_path):
    proyecto = _proyecto(tmp_path, {"test_pide_bases.py": ARCHIVO_QUE_SE_OMITE_ENTERO})
    corrida = _correr(proyecto, entorno={"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "ascii"})
    assert corrida.codigo == 0, corrida.pantalla
    veredicto = "VEREDICTO: NINGUNA PRUEBA FALLÓ; NO CORRIÓ NINGUNA: TODO LO PEDIDO SE OMITIÓ ENTERO"
    assert veredicto in corrida.pantalla and veredicto in corrida.informe, corrida.pantalla
