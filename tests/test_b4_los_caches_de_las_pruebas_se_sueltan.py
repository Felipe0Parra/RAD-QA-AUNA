"""B.4 (PLAN_ANALISIS_PELICULAS_08-10.md; deuda heredada de B.3, R1-LD-02): los caches de modulo de las pruebas se sueltan al terminar el modulo.

CAUSA. La revision de B.3 hallo (R1-LD-02) que su archivo de pruebas dejaba en un cache de modulo dos escenas de ~160 MB al terminar el modulo, y B.3 lo corrigio EN SU archivo
(`liberar_las_escenas()`, una fixture de modulo autouse y `TestElModuloSueltaSuMemoria`). B.3 dejo anotada, sin tocar, la MISMA clase de defecto en otros dos sitios: `_CACHE` de
`tests/test_b2_rango_de_ventana.py` y `_REJILLAS` de `tests/_verdad_braqui.py` (que llenan las pruebas de B.2 con `vb.rejilla`). Un cache de modulo vive lo que vive el proceso: lo que guarda lo
heredan los archivos siguientes de su reparto en la suite repartida en procesos.

MEDIDO (B.4, `b4_medir_caches2.py` del anexo: el archivo entero en un solo proceso y un contador PROFUNDO de lo alcanzable desde el cache; `logs/B4/cache2/`).
  * LOS DOS NOMBRADOS retienen POCO: `_CACHE` guarda 6 `SimpleNamespace` de escalares (0.01 MB: la ventana del DICOM, el rango y cuatro estadisticos; el volumen de cientos de MB NO se conserva) y
    `_REJILLAS`, 8 combinaciones de 33 `Caso` (0.70 MB: la verdad y la medicion de cada placa, no la placa). La memoria alta que deja cada archivo (VmRSS de 181 a 399 MB al terminar) es la de los
    volumenes y las placas locales ya liberados que el asignador no devuelve al sistema, y vaciar el cache no la baja. Se cierran IGUAL: el contrato de B.3 es que un cache de modulo de las pruebas
    se suelta al terminar el modulo, pese lo que pese hoy (basta que un cambio futuro guarde el volumen o la placa para repetir R1-LD-02 sin que nada lo vea).
  * LO QUE SI RETIENE MUCHO, hallado al medir los vecinos que el propio codigo dice que guardan paginas enteras: `_CACHE` de `tests/test_a2_piso_de_pelicula.py` retiene 11 objetos y 2604 MB al
    terminar ese archivo (las peliculas sinteticas y reales de A.2, de 250 MB cada pagina con sus planos); `tests/test_a3_piso_por_esquinas_y_pelicula_virgen.py` LO LLENA TAMBIEN (usa
    `A2._sint`, `A2._real` y `A2._con_fondo`) y al terminar A.3 el cache de A.2 retiene 11 objetos y 2677 MB (VmRSS 4396 MB), de modo que en la suite repartida quedaba vivo en el proceso que corriera
    A.3 aunque A.2 estuviera en otro; y el `_CACHE_VIRGEN` de A.3 retiene 3 objetos y 64 MB. Es la misma clase: se miden, se cierran y entran a la tabla `CACHES`.
  * LO QUE NO SE CIERRA, medido: `_CACHE` de `test_b3_escala_de_hu` (6 escalares, 0.00 MB) y `_ENTRADAS` de `test_g3_criterios_por_equipo` (4 cortes ya recortados, 4.45 MB), por debajo de los
    10 MB con que se decidio cerrar uno; y los cuatro registros de la sesion del interceptor de RT1, que viven toda la sesion a proposito. Se DECLARAN en `NO_SE_CIERRAN` con ese motivo.
  * LA RONDA 1 DE LA REVISION (16-10, R1-06) encontro que el censo de contenedores no veia las familias vecinas del mismo defecto, y que la frase «el siguiente cache de modulo que alguien escriba no
    pasa en silencio» sobreactuaba: el repo ya tenia cinco `functools.lru_cache(maxsize=None)` de pruebas sin liberador (`test_e1_espesor_como_pylinac._ct`, `test_e2_tabla_de_parametros_una_vez._adq_real`,
    `test_gi1_guardado_claves_del_analisis._analisis_real`, `test_se0_carpeta_real_con_topograma._serie_real`, `test_b3_escala_de_hu._adq_real`). Medidos con `b4_medir_caches3.py` (el archivo entero en un
    proceso y un contador profundo por `gc.get_referents`, que abre el objeto de C de un `lru_cache`): UNO retenia mucho, `_ct` de test_e1 (5 objetos CatPhan, 1587 MB: se CIERRA como los otros, con
    `cache_clear()` + `gc.collect()` y una fixture de modulo autouse), y los demas poco (0.00, 0.00, 1.18 y 0.09 MB: se DECLARAN con su cifra). Los globales perezosos y los contadores de
    `_rt1_interceptor_sql` y `test_f2_guarda_de_verosimilitud` (kilobytes) tambien se declaran.

LO QUE EL CENSO DERIVA DEL ARBOL, de cada `tests/*.py` (una funcion de nivel de modulo o un nombre de nivel de modulo que una funcion llena), y exige cerrado o declarado:
  (a) los CONTENEDORES de modulo, vacios o no (`{}`, `[0]`, `set()`, `dict()`, `defaultdict(list)`, `OrderedDict()`, `Counter()`) que una funcion o metodo escribe: `C[k] = v`, `C[k] += v`,
      `C.setdefault/update/append/add/extend(...)`;
  (b) las FUNCIONES de modulo decoradas con `lru_cache` o `cache` (`@lru_cache(maxsize=None)`, `@functools.lru_cache(...)`, `@cache`): su tabla de resultados es un cache que ningun contenedor muestra;
  (c) los GLOBALES PEREZOSOS: un nombre de modulo asignado a `None` que una funcion declara `global` y reasigna (`_V = None; global _V; _V = calcula()`).
LO QUE NO VE (medido el 16-10: ninguna de estas formas tiene un solo caso real en `tests/`, y por eso no se inventaron detectores): la escritura por un ALIAS LOCAL (`c = _C; c[k] = v`), por `__setitem__`,
`pop`, `insert` o `clear` explicitos, el rebinding `global X; X = X + [1]`, los atributos de CLASE o de instancia, los metodos con `lru_cache` (su tabla es de instancia), los caches que viven en otro estado de
proceso (`sys.modules`, variables de entorno, un `monkeypatch` sin deshacer), y las fixtures de alcance de sesion (se sueltan al terminar la sesion, a proposito). Una forma de esas que aparezca de verdad en
`tests/` es la que hace falta detectar: la prueba de los detectores (`TestLosDetectoresDiscriminan`) dice cuales son y las pone a la vista.

QUE FIJA ESTE ARCHIVO, para cada cache de la tabla `CACHES`:
  * EL LIBERADOR: la funcion que lo suelta lo vacia y hace `gc.collect()` (se prueba con un objeto vigilado por una referencia debil, metido en un ciclo para que solo `gc.collect()` lo suelte);
  * LA FIXTURE: todo modulo de pruebas que llena el cache -- el propio, y cada `tests/test_*.py` que llama a una funcion del dueno que lo llena (DERIVADO del arbol por AST: las funciones que escriben en
    el cache o llaman a una que lo escribe, y quien las llama a traves del `import` del dueno; no una lista) -- tiene exactamente UNA fixture de modulo autouse que llama al liberador DESPUES de su
    `yield`: la unica forma de que corra sola y al terminar el modulo;
  * NINGUN CONTENEDOR SIN CLASIFICAR: cada contenedor de nivel de modulo de `tests/*.py` que una funcion llena (derivado del arbol) esta en la tabla `CACHES` o declarado en `NO_SE_CIERRAN` con lo que
    se midio: el siguiente cache de modulo que alguien escriba no pasa en silencio;
  * LOS DETECTORES discriminan: el de la fixture distingue la que libera de las que no (antes del yield, sin autouse, de alcance de funcion, dos yield, otra llamada) y los censos ven las llamadas y no las
    cadenas, los comentarios, los nombres parecidos ni una funcion homonima de otro modulo; y lo que el detector acepta se EJECUTA con el pytest de verdad (un modulo minimo por cada forma, en un proceso
    hijo): el cache queda vacio al terminar el modulo si y solo si el detector la acepta.
Esta prueba no toca produccion (riesgo NULO). Trampa 10: ningun `lru_cache`; la prueba que mira un cache lo sustituye (`monkeypatch`) en vez de tocar el de verdad.
"""
import ast
import functools
import gc
import importlib
import subprocess
import sys
import weakref
from dataclasses import dataclass
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Cache:
    """Un cache de modulo de las pruebas y la forma de soltarlo."""
    modulo: str                        # el modulo que lo guarda (se importa por su nombre; su archivo vive en tests/)
    nombre: str                        # el nombre del cache en ese modulo
    libera: str                        # la funcion de ese modulo que lo suelta
    conocidos: tuple                   # los modulos de pruebas que lo llenan HOY: el censo tiene que verlos (no vacuidad del detector)
    lru: bool = False                  # True si el cache es una funcion decorada con `lru_cache` (se vacia con `cache_clear()`), no un dict

    @property
    def ident(self):
        return f"{self.modulo}.{self.nombre}"


CACHES = (
    Cache("test_b2_rango_de_ventana", "_CACHE", "liberar_los_datos", conocidos=("test_b2_rango_de_ventana",)),
    Cache("_verdad_braqui", "_REJILLAS", "liberar_las_rejillas", conocidos=("test_b2_braqui_contra_la_verdad",)),
    Cache("test_a2_piso_de_pelicula", "_CACHE", "liberar_los_objetos_caros", conocidos=("test_a2_piso_de_pelicula", "test_a3_piso_por_esquinas_y_pelicula_virgen")),
    Cache("test_a3_piso_por_esquinas_y_pelicula_virgen", "_CACHE_VIRGEN", "liberar_las_virgenes", conocidos=("test_a3_piso_por_esquinas_y_pelicula_virgen",)),
    # R1-06 (16-10): el unico `lru_cache` de pruebas que retenia mucho (5 objetos CatPhan, 1587 MB medidos)
    Cache("test_e1_espesor_como_pylinac", "_ct", "liberar_los_ct", conocidos=("test_e1_espesor_como_pylinac",), lru=True),
    # los dos de B.3 (R1-LD-02), cerrados desde B.3 con su propio liberador: entran a la tabla para que el censo y las pruebas genericas los vean tambien
    Cache("test_b3_braqui_no_depende_del_piso", "_CACHE", "liberar_las_escenas", conocidos=("test_b3_braqui_no_depende_del_piso",)),
    Cache("test_b3_braqui_no_depende_del_piso", "_PLACAS_DEL_FONDO", "liberar_las_escenas", conocidos=("test_b3_braqui_no_depende_del_piso",)),
    # B.6 (17-10): el analisis de EPSON009 (las imagenes de la ventana de las cuatro capas y sus perfiles) que usa la prueba de los dos PDF: se suelta al terminar el archivo
    Cache("test_b6_pdf_capa_reportada_braqui", "_CACHE", "liberar_el_analisis", conocidos=("test_b6_pdf_capa_reportada_braqui",)),
)
IDENTIFICADORES = [c.ident for c in CACHES]

# Los demas contenedores de modulo que alguna funcion llena y que NO se cierran, cada uno con el motivo MEDIDO (b4_medir_caches2.py, archivo entero en un proceso, contador profundo). Un contenedor
# nuevo que no este aqui ni en la tabla de arriba hace caer `test_todo_contenedor_de_modulo_de_las_pruebas_esta_en_la_tabla_o_declarado`: o se cierra o se declara con lo que se midio.
NO_SE_CIERRAN = {
    ("test_b3_escala_de_hu", "_CACHE"): "guarda un escalar por serie (el desplazamiento en HU; el volumen no se conserva): 6 elementos y 0.00 MB medidos",
    ("test_g3_criterios_por_equipo", "_ENTRADAS"): "4 cortes de HU ya recortados (el corte, su ventana y el tamano de pixel): 4 elementos y 4.45 MB medidos, por debajo de los 10 MB con que se decidio cerrar uno",
    ("_rt1_interceptor_sql", "hallazgos_sesion"): "registro de la SESION del interceptor de RT1: vive toda la sesion a proposito y su reinicio lo vacia",
    ("_rt1_interceptor_sql", "sitios_diferidos"): "registro de la SESION del interceptor de RT1: vive toda la sesion a proposito y su reinicio lo vacia",
    ("_rt1_interceptor_sql", "funciones_produccion_ejercitadas"): "registro de la SESION del interceptor de RT1: vive toda la sesion a proposito y su reinicio lo vacia",
    ("_rt1_interceptor_sql", "descartados_por_origen"): "registro de la SESION del interceptor de RT1: vive toda la sesion a proposito y su reinicio lo vacia",
    # R1-06 (16-10): las demas formas que el censo ve desde que deriva tambien las funciones con `lru_cache`, los globales perezosos y los contenedores con valor inicial. Medidas con
    # `b4_medir_caches3.py` (el archivo entero en un proceso, contador profundo por `gc.get_referents`; el de las cadenas y los contadores, importando el modulo).
    ("test_e2_tabla_de_parametros_una_vez", "_adq_real"): "lru_cache: la adquisicion (un diccionario de metadatos) de cada serie real: 3 elementos y 0.00 MB medidos",
    ("test_b3_escala_de_hu", "_adq_real"): "lru_cache: la adquisicion (un diccionario de metadatos) de cada serie real: 3 elementos y 0.00 MB medidos",
    ("test_gi1_guardado_claves_del_analisis", "_analisis_real"): ("lru_cache: el analisis de cada serie real sin su volumen (los gi8c, gi8d y gi8g lo importan): 3 elementos y 1.18 MB medidos, por debajo de los 10 MB "
                                                                 "con que se decidio cerrar uno; quien necesite aislarse llama a `_analisis_real.__wrapped__` (GI.8c)"),
    ("test_se0_carpeta_real_con_topograma", "_serie_real"): "lru_cache: las rutas y las etiquetas de una serie real (no los cortes): 1 elemento y 0.09 MB medidos",
    ("_rt1_interceptor_sql", "_tablas_cache"): "global perezoso: el conjunto de las tablas del bloque de QC (65 nombres): 8.59 KB medidos; vive la sesion a proposito",
    ("_rt1_interceptor_sql", "_diferidas_cache"): "global perezoso: el conjunto de las tablas diferidas (0 nombres hoy): 0.21 KB medidos; vive la sesion a proposito",
    ("_rt1_interceptor_sql", "_tablas_filtro_posible_cache"): "global perezoso: el conjunto de las tablas con filtro posible (65 nombres): 8.59 KB medidos; vive la sesion a proposito",
    ("_rt1_interceptor_sql", "_estadisticas"): "contenedor con valor inicial: seis contadores enteros del interceptor de RT1, 0.29 KB medidos; vive la sesion a proposito y `reiniciar` los pone en cero",
    ("test_f2_guarda_de_verosimilitud", "_MES"): "contenedor con valor inicial: `[0]`, un contador de meses (un entero) para fabricar fechas distintas: 1 elemento",
}


# ============================================================================================================================ el detector de la fixture que libera
def _es_fixture_de_modulo_autouse(funcion):
    """True si `funcion` (un `ast.FunctionDef`) esta decorada con `@pytest.fixture(scope="module", autouse=True)`: la que corre sola y una vez por modulo."""
    for d in funcion.decorator_list:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "fixture" and isinstance(d.func.value, ast.Name) and d.func.value.id == "pytest":
            claves = {k.arg: k.value for k in d.keywords}
            return all(isinstance(claves.get(c), ast.Constant) and claves[c].value == v for c, v in (("scope", "module"), ("autouse", True)))
    return False


def _nombre_de_la_llamada(llamada):
    """El nombre con que se llama a algo: `f(...)` -> «f», `m.f(...)` -> «f»; None si es otra cosa."""
    if isinstance(llamada.func, ast.Name):
        return llamada.func.id
    if isinstance(llamada.func, ast.Attribute):
        return llamada.func.attr
    return None


def _llama_al_terminar(funcion, nombre):
    """True si el cuerpo de `funcion` tiene UN `yield` y, DESPUES de el (lo que corre al cerrar el modulo), una llamada a `nombre`."""
    cuerpo = funcion.body
    yields = [i for i, s in enumerate(cuerpo) if isinstance(s, ast.Expr) and isinstance(s.value, ast.Yield)]
    if len(yields) != 1:
        return False
    return any(isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and _nombre_de_la_llamada(s.value) == nombre for s in cuerpo[yields[0] + 1:])


def fixtures_que_liberan(texto, nombre):
    """Los nombres de las fixtures de modulo autouse de `texto` que llaman a `nombre` despues de su yield."""
    return [f.name for f in ast.parse(texto).body if isinstance(f, ast.FunctionDef) and _es_fixture_de_modulo_autouse(f) and _llama_al_terminar(f, nombre)]


# ============================================================================================================================ el censo de quien llena un cache
def _escribe_en(nodo, cache):
    """True si `nodo` (una funcion) escribe en `cache` (un nombre de modulo): `cache[clave] = ...`, `cache[clave] += ...` o `cache.setdefault(...)` / `.update(...)` / `.append(...)` / `.add(...)` / `.extend(...)`
    (tambien sobre un elemento: `cache[clave].append(...)`)."""
    for n in ast.walk(nodo):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == cache for t in n.targets):
            return True
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript) and isinstance(n.target.value, ast.Name) and n.target.value.id == cache:
            return True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and _es_el_cache(n.func.value, cache) and n.func.attr in ("setdefault", "update", "append", "add", "extend"):
            return True
    return False


def _es_el_cache(nodo, cache):
    """True si `nodo` es el cache (`C`) o un elemento suyo (`C[k]`: el `defaultdict(list)` se llena con `C[k].append(v)`)."""
    if isinstance(nodo, ast.Subscript):
        nodo = nodo.value
    return isinstance(nodo, ast.Name) and nodo.id == cache


def funciones_que_llenan(texto_del_dueno, cache, lru=False):
    """Las funciones de nivel de modulo del dueno que escriben en `cache` o llaman (transitivamente) a una que escribe. Con `lru=True`, `cache` ES una funcion decorada con `lru_cache`: llenan el cache ella
    misma (cada llamada con una clave nueva) y las que la llaman (transitivamente)."""
    funciones = {f.name: f for f in ast.parse(texto_del_dueno).body if isinstance(f, ast.FunctionDef)}
    llenan = {cache} if lru else {nombre for nombre, f in funciones.items() if _escribe_en(f, cache)}
    crecio = True
    while crecio:
        crecio = False
        for nombre, f in funciones.items():
            if nombre not in llenan and any(isinstance(c, ast.Call) and _nombre_de_la_llamada(c) in llenan for c in ast.walk(f)):
                llenan.add(nombre)
                crecio = True
    return llenan


def _es_contenedor(valor):
    """Un literal de contenedor, vacio o no (`{}`, `[0]`, `{'a': 0}`, `set()`), o la llamada a un constructor de contenedor con o sin argumentos (`dict()`, `defaultdict(list)`, `OrderedDict()`, `Counter()`)."""
    return (isinstance(valor, (ast.Dict, ast.List, ast.Set))
            or (isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name) and valor.func.id in ("dict", "list", "set", "defaultdict", "OrderedDict", "Counter")))


def contenedores_de_modulo(texto):
    """Los nombres de nivel de modulo asignados a un contenedor (vacio o con valor inicial: `{}`, `[0]`, `set()`, `defaultdict(list)`...) que alguna funcion o metodo del mismo modulo escribe: los caches, los
    contadores y los registros que viven lo que vive el proceso."""
    arbol = ast.parse(texto)
    candidatos = set()
    for n in arbol.body:
        if isinstance(n, ast.Assign) and _es_contenedor(n.value):
            candidatos |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and n.value is not None and isinstance(n.target, ast.Name) and _es_contenedor(n.value):
            candidatos.add(n.target.id)
    funciones = [f for f in ast.walk(arbol) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return sorted(c for c in candidatos if any(_escribe_en(f, c) for f in funciones))


def _es_decorador_de_cache(decorador):
    """`@lru_cache`, `@lru_cache(maxsize=None)`, `@functools.lru_cache(...)`, `@cache` o `@functools.cache`."""
    objetivo = decorador.func if isinstance(decorador, ast.Call) else decorador
    nombre = objetivo.attr if isinstance(objetivo, ast.Attribute) else objetivo.id if isinstance(objetivo, ast.Name) else None
    return nombre in ("lru_cache", "cache")


def funciones_con_cache(texto):
    """Los nombres de las funciones de NIVEL DE MODULO decoradas con `lru_cache` o `cache`: su tabla de resultados es un cache que vive lo que vive el proceso y que ningun contenedor de modulo muestra
    (R1-06: el repo ya tenia cinco, una de ellas con 1587 MB de objetos CatPhan)."""
    return sorted(f.name for f in ast.parse(texto).body if isinstance(f, ast.FunctionDef) and any(_es_decorador_de_cache(d) for d in f.decorator_list))


def globales_perezosos(texto):
    """Los nombres de nivel de modulo asignados a `None` que una funcion declara `global` y reasigna: `_V = None` + `global _V` + `_V = calcula()`, el cache que se llena la primera vez que se pide."""
    arbol = ast.parse(texto)
    en_none = {t.id for n in arbol.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and n.value.value is None for t in n.targets if isinstance(t, ast.Name)}
    en_none |= {n.target.id for n in arbol.body if isinstance(n, ast.AnnAssign) and n.value is not None and isinstance(n.value, ast.Constant) and n.value.value is None and isinstance(n.target, ast.Name)}
    reasignados = set()
    for f in (f for f in ast.walk(arbol) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))):
        globales = {g for s in ast.walk(f) if isinstance(s, ast.Global) for g in s.names}
        asignados = {t.id for s in ast.walk(f) if isinstance(s, ast.Assign) for t in s.targets if isinstance(t, ast.Name)}
        reasignados |= globales & asignados
    return sorted(en_none & reasignados)


def caches_de_modulo(texto):
    """Todo lo que el censo deriva de un modulo: los contenedores que una funcion escribe, las funciones con `lru_cache`/`cache` y los globales perezosos (ver el docstring del archivo: que ve y que no)."""
    return sorted(set(contenedores_de_modulo(texto)) | set(funciones_con_cache(texto)) | set(globales_perezosos(texto)))


def llama_a_las_del_modulo(texto, modulo, funciones):
    """True si `texto` llama a alguna de `funciones` DEL MODULO `modulo`, a traves de su `import`: `import modulo as m` + `m.f(...)`, o `from modulo import f` + `f(...)`. Ni cadenas, ni comentarios, ni
    una funcion homonima de otro modulo."""
    arbol = ast.parse(texto)
    alias, sueltas = set(), set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            alias |= {a.asname or a.name for a in n.names if a.name == modulo}
        elif isinstance(n, ast.ImportFrom) and n.module == modulo:
            sueltas |= {a.asname or a.name for a in n.names if a.name in funciones}
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and n.func.attr in funciones and isinstance(n.func.value, ast.Name) and n.func.value.id in alias:
                return True
            if isinstance(n.func, ast.Name) and n.func.id in sueltas:
                return True
    return False


def modulos_que_lo_llenan(cache, fuentes, texto_del_dueno):
    """Los modulos de pruebas (`fuentes`: {nombre del modulo: texto}) que llenan `cache`: el dueno, si es un modulo de pruebas, y cada uno que llama a una funcion del dueno que lo llena."""
    funciones = funciones_que_llenan(texto_del_dueno, cache.nombre, lru=cache.lru)
    llenan = {cache.modulo} if cache.modulo in fuentes else set()
    llenan |= {m for m, texto in fuentes.items() if m != cache.modulo and cache.modulo in texto and llama_a_las_del_modulo(texto, cache.modulo, funciones)}
    return sorted(llenan)


def _fuentes_de_las_pruebas():
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(TESTS.glob("test_*.py"))}


def _llenan_hoy(cache):
    return modulos_que_lo_llenan(cache, _fuentes_de_las_pruebas(), (TESTS / f"{cache.modulo}.py").read_text(encoding="utf-8"))


# ============================================================================================================================ (a) el liberador
class _Pesada:
    """Un objeto cualquiera que se vigila con una referencia debil: hace de volumen, de placa o de caso."""


class TestElLiberadorSueltaLoQueGuardaba:
    @pytest.mark.parametrize("cache", CACHES, ids=IDENTIFICADORES)
    def test_liberar_vacia_el_cache_y_suelta_lo_que_guardaba_aun_si_estaba_en_un_ciclo(self, cache, monkeypatch):
        """El cache de verdad no se toca (otras pruebas del modulo lo estan usando): se sustituye por uno vacio (un `lru_cache` nuevo con una funcion que entrega el objeto vigilado, si el cache es una funcion
        con `lru_cache`). El objeto vigilado se mete en un ciclo, que solo `gc.collect()` suelta; el recolector automatico se apaga durante la prueba para que no lo suelte por su cuenta."""
        modulo = importlib.import_module(cache.modulo)
        objeto = _Pesada()
        objeto.ciclo = objeto
        vigilada = weakref.ref(objeto)
        if cache.lru:
            guardado = [objeto]
            sustituto = functools.lru_cache(maxsize=None)(lambda clave: guardado.pop())
            sustituto(("clave", 1))
            quedan = lambda: sustituto.cache_info().currsize                       # noqa: E731
        else:
            sustituto = {("clave", 1): objeto}
            quedan = lambda: len(sustituto)                                        # noqa: E731
        monkeypatch.setattr(modulo, cache.nombre, sustituto)
        del objeto
        recolector_activo = gc.isenabled()
        gc.disable()
        try:
            getattr(modulo, cache.libera)()
            assert not quedan(), f"{cache.ident} sigue con elementos despues de {cache.libera}()"
            assert vigilada() is None, f"alguien mas retiene lo que {cache.ident} guardaba (o {cache.libera}() no llama a gc.collect()): no se soltaron de verdad"
        finally:
            if recolector_activo:
                gc.enable()

    @pytest.mark.parametrize("cache", CACHES, ids=IDENTIFICADORES)
    def test_el_liberador_existe_y_es_una_funcion_sin_argumentos_del_modulo_que_guarda_el_cache(self, cache):
        modulo = importlib.import_module(cache.modulo)
        valor = getattr(modulo, cache.nombre)
        if cache.lru:
            assert callable(valor) and hasattr(valor, "cache_clear") and hasattr(valor, "cache_info"), f"{cache.ident} ya no es una funcion con lru_cache: la prueba sustituye un lru_cache"
        else:
            assert isinstance(valor, dict), f"{cache.ident} ya no es un dict: la prueba sustituye un dict"
        liberador = getattr(modulo, cache.libera)
        assert callable(liberador) and liberador.__module__ == modulo.__name__
        assert liberador.__code__.co_argcount == 0, "la fixture lo llama sin argumentos"


# ============================================================================================================================ (b) la fixture de modulo
class TestCadaModuloQueLlenaUnCacheLoSueltaAlTerminar:
    @pytest.mark.parametrize("cache", CACHES, ids=IDENTIFICADORES)
    def test_hay_una_fixture_de_modulo_autouse_que_llama_al_liberador_despues_del_yield(self, cache):
        llenan = _llenan_hoy(cache)
        assert set(cache.conocidos) <= set(llenan), f"el censo no ve a {sorted(set(cache.conocidos) - set(llenan))}: el detector esta ciego (no vacuidad); ve {llenan}"
        fuentes = _fuentes_de_las_pruebas()
        con_fixture = {m: fixtures_que_liberan(fuentes[m], cache.libera) for m in llenan}
        malos = {m: f for m, f in con_fixture.items() if len(f) != 1}
        assert not malos, (f"cada modulo que llena {cache.ident} debe tener exactamente UNA fixture de modulo autouse que llame a {cache.libera}() despues de su yield; "
                           f"modulos con otra cantidad: {malos}")


# ============================================================================================================================ (b2) ningun contenedor de modulo queda sin clasificar
class TestNingunCacheDeModuloQuedaSinClasificar:
    # lo que el censo VE hoy en tests/ (medido el 16-10): la no vacuidad del detector. Si alguno deja de verse, el censo esta ciego a esa forma.
    VISTOS_HOY = {("test_e1_espesor_como_pylinac", "_ct"), ("test_e2_tabla_de_parametros_una_vez", "_adq_real"), ("test_gi1_guardado_claves_del_analisis", "_analisis_real"),
                  ("test_se0_carpeta_real_con_topograma", "_serie_real"), ("test_b3_escala_de_hu", "_adq_real"),                                                  # funciones con lru_cache
                  ("_rt1_interceptor_sql", "_tablas_cache"), ("_rt1_interceptor_sql", "_diferidas_cache"), ("_rt1_interceptor_sql", "_tablas_filtro_posible_cache"),   # globales perezosos
                  ("_rt1_interceptor_sql", "_estadisticas"), ("test_f2_guarda_de_verosimilitud", "_MES"),                                                         # contenedores con valor inicial
                  ("test_b2_rango_de_ventana", "_CACHE"), ("_verdad_braqui", "_REJILLAS")}                                                                       # contenedores vacios

    def test_todo_cache_de_modulo_de_las_pruebas_esta_en_la_tabla_o_declarado(self):
        """El mismo defecto se repitio tres veces (R1-LD-02 en B.3, estos dos de B.2 y los de A.2 y A.3, que nadie habia visto) y una cuarta con los `lru_cache` (R1-06): cada vez un cache de modulo nuevo que
        nadie suelta. Aqui se DERIVA del arbol de cada `tests/*.py` lo que el censo sabe ver (contenedores de modulo que una funcion escribe, funciones con `lru_cache`/`cache`, globales perezosos: ver el docstring
        del archivo, que dice tambien lo que NO ve) y tiene que estar cerrado (tabla `CACHES`) o declarado con lo que se midio (`NO_SE_CIERRAN`): uno nuevo de esas formas no pasa en silencio."""
        hallados = set()
        for p in sorted(TESTS.glob("*.py")):
            hallados |= {(p.stem, nombre) for nombre in caches_de_modulo(p.read_text(encoding="utf-8"))}
        declarados = {(c.modulo, c.nombre) for c in CACHES} | set(NO_SE_CIERRAN)
        assert self.VISTOS_HOY <= hallados, f"el censo dejo de ver {sorted(self.VISTOS_HOY - hallados)}: esta ciego a esa forma (no vacuidad)"
        assert not hallados - declarados, (f"caches de modulo sin clasificar: {sorted(hallados - declarados)}. Si guardan arreglos, imagenes, series o objetos de pylinac, se cierran como los de la tabla `CACHES` "
                                           f"(liberador, fixture de modulo autouse, una fila); si guardan poco, se declaran en `NO_SE_CIERRAN` con lo que se midio (b4_medir_caches3.py)")
        assert not declarados - hallados, f"declarados que ya no existen (o que el censo ya no ve): {sorted(declarados - hallados)}: quitarlos de la tabla"

    def test_los_que_no_se_cierran_tienen_su_motivo_medido(self):
        assert all(motivo.strip() for motivo in NO_SE_CIERRAN.values())
        assert not {(c.modulo, c.nombre) for c in CACHES} & set(NO_SE_CIERRAN), "un contenedor esta cerrado y a la vez declarado como no cerrado"


# ============================================================================================================================ (c) los detectores discriminan
class TestLosDetectoresDiscriminan:
    def test_el_detector_de_la_fixture_distingue_la_que_libera_de_las_que_no(self):
        def fuente(decorador, cuerpo):
            return f"@pytest.fixture({decorador})\ndef f():\n" + "".join(f"    {linea}\n" for linea in cuerpo)
        modulo_autouse = "scope='module', autouse=True"
        casos = {
            "libera al terminar": (fuente(modulo_autouse, ["yield", "liberar()"]), True),
            "libera al terminar, con el modulo delante": (fuente(modulo_autouse, ["yield", "vb.liberar()"]), True),
            "libera ANTES del yield": (fuente(modulo_autouse, ["liberar()", "yield"]), False),
            "no libera": (fuente(modulo_autouse, ["yield", "pass"]), False),
            "llama a OTRA funcion": (fuente(modulo_autouse, ["yield", "otra()"]), False),
            "sin autouse": (fuente("scope='module'", ["yield", "liberar()"]), False),
            "de alcance de funcion": (fuente("scope='function', autouse=True", ["yield", "liberar()"]), False),
            "de alcance de sesion": (fuente("scope='session', autouse=True", ["yield", "liberar()"]), False),
            "dos yield": (fuente(modulo_autouse, ["yield", "liberar()", "yield"]), False),
            "sin yield (return)": (fuente(modulo_autouse, ["liberar()"]), False),
        }
        for nombre, (texto, esperado) in casos.items():
            assert bool(fixtures_que_liberan(texto, "liberar")) == esperado, nombre

    def test_lo_que_el_detector_acepta_suelta_de_verdad_el_cache_al_terminar_el_modulo_y_lo_que_rechaza_no(self, tmp_path):
        """El detector dice «esta es la forma de la fixture que suelta el cache al terminar el modulo»; aqui se EJECUTA, con el pytest de verdad, un modulo de pruebas minimo por cada forma y se mira el cache
        cuando el modulo termino: el detector acepta si y solo si todas las pruebas pasan y el cache queda VACIO (la convergencia se afirma, no se confia: corolario 3)."""
        modulo = ("import gc\nimport pytest\n\n_CACHE = {{}}\n\n\ndef liberar():\n    _CACHE.clear()\n    gc.collect()\n\n\n{fixture}\n\n\n"
                  "def test_a():\n    _CACHE['x'] = [0] * 1000\n    assert _CACHE\n\n\ndef test_b():\n    assert _CACHE, 'el cache se vacio entre dos pruebas del mismo modulo'\n")
        script = ("import sys, pytest\nrc = pytest.main([sys.argv[1], '-q', '-p', 'no:cacheprovider', '--rootdir', sys.argv[2]])\n"
                  "modulo = sys.modules[sys.argv[3]]\nprint('RESULTADO', rc, len(modulo._CACHE))\n")
        formas = {
            "libera_al_terminar": ("@pytest.fixture(scope='module', autouse=True)\ndef f():\n    yield\n    liberar()", True),
            "libera_antes_del_yield": ("@pytest.fixture(scope='module', autouse=True)\ndef f():\n    liberar()\n    yield", False),
            "sin_autouse": ("@pytest.fixture(scope='module')\ndef f():\n    yield\n    liberar()", False),
            "de_alcance_de_funcion": ("@pytest.fixture(scope='function', autouse=True)\ndef f():\n    yield\n    liberar()", False),
            "dos_yield": ("@pytest.fixture(scope='module', autouse=True)\ndef f():\n    yield\n    liberar()\n    yield", False),
        }
        for nombre, (fixture, acepta_el_detector) in formas.items():
            fuente = modulo.format(fixture=fixture)
            archivo = tmp_path / f"test_mini_{nombre}.py"
            archivo.write_text(fuente, encoding="utf-8")
            corrida = subprocess.run([sys.executable, "-c", script, str(archivo), str(tmp_path), archivo.stem], capture_output=True, text=True, timeout=120, cwd=tmp_path)
            linea = next((l for l in corrida.stdout.splitlines() if l.startswith("RESULTADO")), None)
            assert linea is not None, f"{nombre}: el pytest hijo no dijo su resultado\n{corrida.stdout[-800:]}\n{corrida.stderr[-800:]}"
            _, rc, quedan = linea.split()
            suelta_de_verdad = int(rc) == 0 and int(quedan) == 0
            assert bool(fixtures_que_liberan(fuente, "liberar")) == acepta_el_detector, f"{nombre}: el detector"
            assert suelta_de_verdad == acepta_el_detector, f"{nombre}: ejecutado de verdad, rc={rc} y el cache queda con {quedan} elementos"

    def test_las_funciones_que_llenan_un_cache_son_las_que_escriben_en_el_o_llaman_a_una_que_lo_escribe(self):
        dueno = ("_C = {}\n_OTRO = {}\n\n\ndef primitiva(k, f):\n    _C[k] = f()\n\n\ndef con_setdefault(k):\n    return _C.setdefault(k, 1)\n\n\ndef intermedia(k):\n    return primitiva(k, int)\n\n\n"
                 "def usa_la_intermedia():\n    return intermedia(1)\n\n\ndef no_lo_toca():\n    return _OTRO.get(1)\n\n\ndef escribe_otro_cache(k):\n    _OTRO[k] = 1\n")
        assert funciones_que_llenan(dueno, "_C") == {"primitiva", "con_setdefault", "intermedia", "usa_la_intermedia"}

    def test_las_funciones_que_llenan_un_lru_cache_son_ella_y_las_que_la_llaman(self):
        dueno = ("import functools\n\n\n@functools.lru_cache(maxsize=None)\ndef cargar(k):\n    return [k]\n\n\ndef usa(k):\n    return cargar(k)\n\n\ndef usa_la_que_usa():\n    return usa(1)\n\n\n"
                 "def no_la_toca():\n    return 1\n")
        assert funciones_que_llenan(dueno, "cargar", lru=True) == {"cargar", "usa", "usa_la_que_usa"}

    def test_el_censo_de_contenedores_ve_los_que_una_funcion_escribe_y_no_los_demas(self):
        texto = ("from collections import defaultdict, Counter\nA = {}\nB = []\nC = set()\nD = dict()\nE = {}\nF = {'x': 1}\nG = []\nH: dict = {}\nI = {}\nJ = defaultdict(list)\nK = [0]\nL = 5\nM = Counter()\n\n\n"
                 "def f():\n    A['k'] = 1\n    B.append(1)\n    C.add(1)\n    D.setdefault(1, 2)\n    H['k'] = 3\n    F['z'] = 0\n    J['a'].append(1)\n    K[0] += 1\n    M['p'] += 1\n\n\n"
                 "class N:\n    def m(self):\n        G.extend([1])\n\n\ndef g():\n    return E.get(1)\n")
        assert contenedores_de_modulo(texto) == ["A", "B", "C", "D", "F", "G", "H", "J", "K", "M"], "E solo se lee, I nadie lo llena, L no es un contenedor; F (valor inicial), J (defaultdict), K y M (+=) si"

    def test_el_censo_ve_las_funciones_con_lru_cache_y_cache_y_no_las_demas(self):
        texto = ("import functools\nfrom functools import lru_cache, cache\nimport pytest\n\n\n"
                 "@functools.lru_cache(maxsize=None)\ndef a(k):\n    return [k]\n\n\n@lru_cache\ndef b(k):\n    return k\n\n\n@lru_cache(maxsize=32)\ndef c(k):\n    return k\n\n\n"
                 "@functools.cache\ndef d(k):\n    return k\n\n\n@cache\ndef e(k):\n    return k\n\n\n"
                 "@pytest.fixture(scope='module')\ndef f():\n    return 1\n\n\ndef g(k):\n    return k\n\n\n"
                 "class K:\n    @functools.lru_cache(maxsize=None)\n    def m(self, k):\n        return k\n\n\n"
                 "def h():\n    @functools.lru_cache(maxsize=None)\n    def interna(k):\n        return k\n    return interna\n")
        assert funciones_con_cache(texto) == ["a", "b", "c", "d", "e"], "las de nivel de modulo; ni una fixture, ni una funcion sin decorar, ni un metodo (cache de instancia), ni una anidada"

    def test_el_censo_ve_los_globales_perezosos_y_no_los_demas(self):
        texto = ("_A = None\n_B = None\n_C = None\n_D = None\n_E: object = None\n_F = 0\n\n\n"
                 "def a():\n    global _A\n    if _A is None:\n        _A = [0] * 10\n    return _A\n\n\n"
                 "def b():\n    global _B\n    return _B\n\n\n"                      # declara global pero no lo reasigna: solo lo lee
                 "def c():\n    _C = [1]\n    return _C\n\n\n"                       # un local con el mismo nombre
                 "def d():\n    return _D\n\n\n"
                 "def e():\n    global _E, _F\n    _E = {}\n    _F = 1\n")
        assert globales_perezosos(texto) == ["_A", "_E"], "_B solo se lee, _C es un local, _D nadie lo asigna, _F no vale None al empezar"

    def test_caches_de_modulo_une_las_tres_formas(self):
        texto = ("import functools\n_C = {}\n_V = None\n\n\n@functools.lru_cache(maxsize=None)\ndef f(k):\n    return k\n\n\n"
                 "def g(k):\n    global _V\n    _C[k] = 1\n    _V = k\n")
        assert caches_de_modulo(texto) == ["_C", "_V", "f"]

    def test_el_censo_de_los_modulos_que_llenan_ve_las_llamadas_por_el_import_y_no_lo_demas(self):
        dueno = "_C = {}\n\n\ndef llena(k):\n    _C[k] = 1\n\n\ndef lee(k):\n    return _C.get(k)\n"
        cache = Cache("duenio", "_C", "liberar", conocidos=())
        fuentes = {
            "con_alias": "import duenio as D\n\n\ndef f():\n    return D.llena(1)\n",
            "con_el_nombre": "import duenio\n\n\ndef f():\n    return duenio.llena(1)\n",
            "desde": "from duenio import llena as ll\n\n\ndef f():\n    return ll(1)\n",
            "solo_lee": "import duenio as D\n\n\ndef f():\n    return D.lee(1)\n",
            "homonima_de_otro_modulo": "import duenio\nimport otro\n\n\ndef f():\n    return otro.llena(1)\n",
            "sin_importar_el_dueno": "# duenio\ndef llena(k):\n    return k\n\n\ndef f():\n    return llena(1)\n",
            "cadena_y_comentario": "# D.llena(1)\nTEXTO = 'duenio.llena(1)'\n\n\ndef f():\n    return TEXTO\n",
            "solo_el_nombre": "import duenio as D\n\n\ndef f():\n    return D.llena\n",
        }
        # los casos negativos nombran al dueno en el texto (un comentario, un import que no se usa): el filtro rapido por el nombre no los esconde y lo que decide es el arbol
        assert modulos_que_lo_llenan(cache, fuentes, dueno) == ["con_alias", "con_el_nombre", "desde"]
        con_el_dueno = {**fuentes, "duenio": dueno}
        assert modulos_que_lo_llenan(cache, con_el_dueno, dueno) == ["con_alias", "con_el_nombre", "desde", "duenio"], "el dueno, si es un modulo de pruebas, lo llena"
