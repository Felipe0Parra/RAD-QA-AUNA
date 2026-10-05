"""PI.10 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md, DP-139, regla del 18-08): que no vuelva a haber DOS. La posición inicial de la fuente de
braquiterapia tiene cuatro «una sola» (§5.2 del plan) y una quinta del PI.1; cada una se puede romper en silencio en una tarea futura (alguien copia
el motor «para probar», le pone un `execute` a la página, hace que un PDF busque la prueba por su cuenta...). Aquí cada una es un TRIPWIRE derivado
del ÁRBOL de producción (AST), no una lista escrita a mano:

  1. UNA SOLA FORMA DE MEDIR. (a) Fuera de `analisisImagenes/posicion_inicial_braqui.py` nadie define una función con el nombre Y los parámetros de
     `analizar`, `mesetas_por_fila` o `lado_del_transito` (los parámetros se leen del propio motor: los homónimos de otros módulos, como el `analizar`
     del motor de Catphan o el del censo de SQL, tienen otra firma y no cuentan); (b) solo la página y el servicio importan el motor; (c) UN solo lector
     de la resolución declarada de una imagen (`resolucion_declarada`; excepción declarada: `Analisis_PlacaRC.metadata`, zona ROJA, DP-141); (d) UNA sola
     función vuelve una resolución en escala (`escala_mm`: nadie más divide 25.4 entre un dpi en el motor, el servicio, la página ni los PDF; las otras
     tres divisiones del motor están declaradas, cada una con su motivo).
  2. LA PÁGINA NO TIENE SQL: ni `execute`, ni `cursor`, ni `commit`, ni `Conexion`, ni `sqlite3`, ni `QtSql`.
  3. UNA SOLA REGLA DE VIGENCIA. Ninguna consulta a `braqui_posicion_inicial` por fecha fuera de `_vigente_por_fecha` (la regla de dos pasos del servicio);
     `posicion_inicial_para` y `existe_vigente` la llaman; y los dos PDF piden el texto con `texto_para_pdf` (que usa `posicion_inicial_para`).
  4. NINGUNA ESCRITURA A `CondicionesMedicion.desplazamiento_ini` fuera del guardado del mensual (`guardar_resultado_CambioFuente`): censo de las
     sentencias `INSERT`/`UPDATE` de ese texto. Lo dinámico (el `UPDATE {tabla}` genérico de la corrección en «Ver tabla») lo vigilan EB5/A6.1.
  5. EL TEXTO BREVE SE CONSTRUYE EN UN SOLO SITIO: ningún texto que lleve a la vez «±» y «(k = 2)» sale de `texto_breve`; la página lo pide con
     `texto_breve` y los PDF con `texto_para_pdf`.

Cada guarda tiene (i) su COMPUERTA DE NO VACUIDAD por archivo, con su motivo (Trampa 8: sin ella pasaría en vacío si el árbol cambiara de forma) y
(ii) su CASO SINTÉTICO que la hace caer y que nombra el sitio (discriminación). Las guardas son funciones puras sobre `{ruta: (texto, árbol)}`: la misma
función se corre sobre el árbol real (debe salir limpia) y sobre fuentes fabricadas (debe señalar)."""
import ast
import os
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
EXCLUIDOS = {".venv", "build", "dist", "tests", "__pycache__", ".git", "node_modules", ".pytest_cache"}

MOTOR = "analisisImagenes/posicion_inicial_braqui.py"
RESOLUCION = "analisisImagenes/resolucion_imagen.py"
SERVICIO = "services/posicion_inicial_braqui.py"
PAGINA = "ui/paginasControles/PruebasMensuales/posicion_inicial_braqui.py"
PDF_DIARIO = "models/PDF/reportes.py"
PDF_MENSUAL = "models/PDF/Mensuales/reportes_mensuales.py"
CARGA_DE_LA_PRUEBA = "data/ManejoDatos/load.py"
FUNCIONES_DEL_MOTOR = ("analizar", "mesetas_por_fila", "lado_del_transito")
MODULOS_DE_LA_FUNCION = (MOTOR, SERVICIO, PAGINA, PDF_DIARIO, PDF_MENSUAL, RESOLUCION)

# --- las EXCEPCIONES declaradas, cada una con su motivo (una excepción sin motivo es una puerta abierta) ---------------------------------------------
LECTORES_DE_DPI_PERMITIDOS = {
    (RESOLUCION, "resolucion_declarada"): "el ÚNICO lector: Pillow rellena `info['dpi']` (72 en un JPEG con EXIF, 1 en un TIFF sin la etiqueta), así que solo se lee lo que el archivo declara",
    ("analisisImagenes/Analisis_PlacaRC.py", "metadata"): "DP-141: el análisis de la placa del diario (zona ROJA, no se toca en este plan) lee la resolución con el defecto que PI.1 corrigió",
}
DIVISIONES_DE_25_4_PERMITIDAS = {
    (MOTOR, "escala_mm"): "la ÚNICA función que vuelve una resolución en escala (siempre la del procedimiento de escaneo, nunca la declarada)",
    (MOTOR, "ventana_rotada"): "dimensiona la ventana de análisis cuando NO hay escala (resolución «otra»): usa `DPI_SI_FALTA`, no una resolución declarada",
    (MOTOR, "lado_del_transito"): "ídem para el recorte de la banda de tránsito: solo dimensiona, no mide",
    (MOTOR, "placa_sintetica"): "genera una placa de un dpi dado (la inversa: construir una imagen con una escala, no leerla)",
}
CONSULTAS_POR_FECHA_PERMITIDAS = {
    (SERVICIO, "_vigente_por_fecha"): "la regla de vigencia: el cambio de fuente que vale en la fecha y, DESPUÉS, su prueba",
}
ESCRITURAS_DE_DESPLAZAMIENTO_PERMITIDAS = {
    (CARGA_DE_LA_PRUEBA, "guardar_resultado_CambioFuente"): "el guardado del mensual: el `INSERT INTO CondicionesMedicion` del contrato de QC (anular + insertar)",
}
CONSTRUCTORES_DEL_TEXTO_PERMITIDOS = {
    (SERVICIO, "texto_breve"): "la ÚNICA definición del texto breve de la posición inicial",
}


# ------------------------------------------------------------------------------------------------------------------ el árbol de producción

def _cargar_produccion():
    fuentes = {}
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in EXCLUIDOS]
        for nombre in archivos:
            if nombre.endswith(".py"):
                ruta = Path(carpeta) / nombre
                texto = ruta.read_text(encoding="utf-8", errors="replace")
                try:
                    fuentes[str(ruta.relative_to(RAIZ)).replace(os.sep, "/")] = (texto, ast.parse(texto, str(ruta)))
                except SyntaxError:
                    pass
    return fuentes


# Trampa 8, POR ARCHIVO: cada archivo que una guarda vigila (o donde busca lo permitido) existe en el árbol y tiene cuerpo. {ruta: (motivo, mínimo de funciones)}.
# El mínimo es la MITAD de lo que hay hoy (el archivo puede crecer o encogerse un poco; si se vacía o desaparece, la guarda estaría vigilando nada).
ARCHIVOS_VIGILADOS = {
    MOTOR: ("el motor: define las tres funciones que nadie más debe copiar y la única que vuelve una resolución en escala", 15),
    RESOLUCION: ("el único lector de la resolución declarada de una imagen", 3),
    SERVICIO: ("la única puerta a la tabla: la regla de vigencia y el texto breve", 12),
    PAGINA: ("la página: no tiene SQL y pide el texto al servicio", 40),
    PDF_DIARIO: ("el PDF diario de braquiterapia: pide el texto con `texto_para_pdf`", 3),
    PDF_MENSUAL: ("el PDF mensual de braquiterapia: ídem", 30),
    CARGA_DE_LA_PRUEBA: ("el guardado del mensual: el único `INSERT INTO CondicionesMedicion` que nombra `desplazamiento_ini`", 60),
    "data/ManejoDatos/conection.py": ("la definición de la tabla (nombra la columna y trae `ON UPDATE`: no es una escritura)", 30),
    "analisisImagenes/Analisis_PlacaRC.py": ("la excepción declarada de DP-141 (lee `info['dpi']`)", 20),
}


@pytest.fixture(scope="module")
def produccion():
    fuentes = _cargar_produccion()
    assert len(fuentes) >= 100, f"el árbol de producción leyó {len(fuentes)} archivos: no está leyendo el árbol"
    return fuentes


class TestNoVacuidadPorArchivo:
    @pytest.mark.parametrize("ruta", sorted(ARCHIVOS_VIGILADOS))
    def test_el_archivo_vigilado_existe_y_tiene_cuerpo(self, produccion, ruta):
        motivo, minimo = ARCHIVOS_VIGILADOS[ruta]
        assert ruta in produccion, f"{ruta} ya no está en el árbol de producción ({motivo}): la guarda vigilaría nada"
        funciones = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(produccion[ruta][1]))
        assert funciones >= minimo, f"{ruta} tiene {funciones} funciones (mínimo {minimo}; {motivo})"


def _fuente(texto, ruta="<sintetico>.py"):
    return {ruta: (texto, ast.parse(texto))}


def _funcion_contenedora(arbol):
    """{id(nodo): nombre de la función más interna que lo contiene, o None}: así cada hallazgo nombra su sitio."""
    contenedora = {id(arbol): None}

    def visitar(nodo, funcion):
        for hijo in ast.iter_child_nodes(nodo):
            propia = hijo.name if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)) else funcion
            contenedora[id(hijo)] = propia
            visitar(hijo, propia)

    visitar(arbol, None)
    return contenedora


def _trozos_de_texto(arbol):
    """[(nodo, texto)] de cada cadena que se USA como valor: las constantes y las partes literales de un f-string. Se saltan las cadenas sueltas
    (docstrings y comentarios en forma de cadena: no son SQL ni texto que se imprima)."""
    sueltas = {id(n.value) for n in ast.walk(arbol) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    trozos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.JoinedStr):
            partes = "".join(p.value for p in nodo.values if isinstance(p, ast.Constant) and isinstance(p.value, str))
            trozos.append((nodo, partes))
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in sueltas:
            trozos.append((nodo, nodo.value))
    return trozos


def _sitios(fuentes, ruta, encontrar):
    """[(ruta, función, línea)] de lo que `encontrar(nodo)` marca en `ruta`, con la función que lo contiene."""
    texto, arbol = fuentes[ruta]
    contenedora = _funcion_contenedora(arbol)
    return [(ruta, contenedora.get(id(n)), n.lineno) for n in ast.walk(arbol) if encontrar(n)]


def _fuera_de_lo_permitido(hallados, permitidos):
    return sorted({(r, f, l) for r, f, l in hallados if (r, f) not in permitidos})


# ======================================================================================================== 1. una sola forma de medir

def _firmas_del_motor(fuentes):
    _, arbol = fuentes[MOTOR]
    return {n.name: tuple(a.arg for a in n.args.args) for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name in FUNCIONES_DEL_MOTOR}


def segundas_copias_del_motor(fuentes):
    """Funciones FUERA del motor con el nombre y los parámetros de una del motor: [(ruta, nombre, línea)]."""
    firmas = _firmas_del_motor(fuentes)
    copias = []
    for ruta, (_, arbol) in fuentes.items():
        if ruta == MOTOR:
            continue
        for n in ast.walk(arbol):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and firmas.get(n.name) == tuple(a.arg for a in n.args.args):
                copias.append((ruta, n.name, n.lineno))
    return sorted(copias)


def importadores_del_motor(fuentes):
    """El conjunto de módulos (fuera del motor) que importan el motor, de cualquier forma."""
    importadores = set()
    for ruta, (_, arbol) in fuentes.items():
        if ruta == MOTOR:
            continue
        for n in ast.walk(arbol):
            if isinstance(n, ast.ImportFrom) and ((n.module == "analisisImagenes" and any(a.name == "posicion_inicial_braqui" for a in n.names))
                                                  or n.module == "analisisImagenes.posicion_inicial_braqui"):
                importadores.add(ruta)
            elif isinstance(n, ast.Import) and any(a.name == "analisisImagenes.posicion_inicial_braqui" for a in n.names):
                importadores.add(ruta)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("analisisImagenes.posicion_inicial_braqui"):
                importadores.add(ruta)           # importlib.import_module("...") / el cargador de paginas por nombre
    return importadores


def _es_lectura_de_dpi(n):
    llamada = (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" and isinstance(n.func.value, ast.Attribute)
               and n.func.value.attr == "info" and bool(n.args) and isinstance(n.args[0], ast.Constant) and n.args[0].value == "dpi")
    indice = (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Attribute) and n.value.attr == "info"
              and isinstance(n.slice, ast.Constant) and n.slice.value == "dpi")
    return llamada or indice


def lectores_de_dpi(fuentes):
    return [s for ruta in fuentes for s in _sitios(fuentes, ruta, _es_lectura_de_dpi)]


def _es_25_4_entre_algo(n):
    """Una división en la que interviene 25.4 (mm por pulgada): `25.4 / dpi`, `(25.4 * k) / dpi` y la inversa `dpi / 25.4` (píxeles por mm): las dos
    son «una resolución vuelta escala»."""
    return isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) and (
        any(isinstance(x, ast.Constant) and x.value == 25.4 for x in ast.walk(n.left)) or (isinstance(n.right, ast.Constant) and n.right.value == 25.4))


def divisiones_de_25_4(fuentes, modulos=MODULOS_DE_LA_FUNCION):
    return [s for ruta in modulos if ruta in fuentes for s in _sitios(fuentes, ruta, _es_25_4_entre_algo)]


class TestUnaSolaFormaDeMedir:
    def test_nadie_mas_define_una_copia_del_motor(self, produccion):
        copias = segundas_copias_del_motor(produccion)
        assert not copias, f"hay una SEGUNDA forma de medir (mismo nombre y parámetros que el motor): {copias}"

    def test_no_vacuidad_el_motor_define_las_tres_y_los_homonimos_no_cuentan(self, produccion):
        firmas = _firmas_del_motor(produccion)
        assert set(firmas) == set(FUNCIONES_DEL_MOTOR) and all(len(f) >= 2 for f in firmas.values()), firmas
        # los homónimos reales de otros módulos existen y tienen OTRA firma: por eso el guardia mira nombre Y parámetros
        homonimos = [(r, tuple(a.arg for a in n.args.args)) for r, (_, ar) in produccion.items() if r != MOTOR for n in ast.walk(ar)
                     if isinstance(n, ast.FunctionDef) and n.name == "analizar"]
        assert homonimos and all(f != firmas["analizar"] for _, f in homonimos), homonimos

    def test_discrimina_una_copia_del_motor_y_no_confunde_un_homonimo(self, produccion):
        firmas = _firmas_del_motor(produccion)
        parametros = ", ".join(firmas["analizar"])
        copia = {**produccion, **_fuente(f"def analizar({parametros}):\n    return None\n", "services/otra_forma_de_medir.py")}
        assert segundas_copias_del_motor(copia) == [("services/otra_forma_de_medir.py", "analizar", 1)]
        homonimo = {**produccion, **_fuente("def analizar(sql, tablas):\n    return None\n", "services/otra_cosa.py")}
        assert segundas_copias_del_motor(homonimo) == []

    def test_solo_la_pagina_y_el_servicio_importan_el_motor(self, produccion):
        assert importadores_del_motor(produccion) == {PAGINA, SERVICIO}

    def test_discrimina_un_tercer_importador_de_cualquier_forma(self, produccion):
        for linea in ("from analisisImagenes import posicion_inicial_braqui as m", "from analisisImagenes.posicion_inicial_braqui import analizar",
                      "import analisisImagenes.posicion_inicial_braqui", "import importlib\nm = importlib.import_module('analisisImagenes.posicion_inicial_braqui')"):
            fuentes = {**produccion, **_fuente(linea + "\n", "models/PDF/un_pdf_que_mide.py")}
            assert importadores_del_motor(fuentes) == {PAGINA, SERVICIO, "models/PDF/un_pdf_que_mide.py"}, linea

    def test_un_solo_lector_de_la_resolucion_declarada(self, produccion):
        fuera = _fuera_de_lo_permitido(lectores_de_dpi(produccion), LECTORES_DE_DPI_PERMITIDOS)
        assert not fuera, f"otro sitio lee `info['dpi']` de una imagen (use `resolucion_declarada`): {fuera}"

    def test_no_vacuidad_los_dos_lectores_permitidos_existen(self, produccion):
        hallados = {(r, f) for r, f, _ in lectores_de_dpi(produccion)}
        assert hallados == set(LECTORES_DE_DPI_PERMITIDOS), f"los lectores permitidos ya no son los que hay (¿se retiró uno?): {sorted(hallados)}"

    def test_discrimina_un_lector_nuevo_de_dpi(self, produccion):
        fuentes = {**produccion, **_fuente("from PIL import Image\ndef leer(ruta):\n    return Image.open(ruta).info.get('dpi')\n", "ui/otra_pantalla.py")}
        assert _fuera_de_lo_permitido(lectores_de_dpi(fuentes), LECTORES_DE_DPI_PERMITIDOS) == [("ui/otra_pantalla.py", "leer", 3)]
        fuentes = {**produccion, **_fuente("def leer(imagen):\n    return imagen.info['dpi']\n", "ui/otra_pantalla.py")}
        assert _fuera_de_lo_permitido(lectores_de_dpi(fuentes), LECTORES_DE_DPI_PERMITIDOS) == [("ui/otra_pantalla.py", "leer", 2)]

    def test_una_sola_funcion_vuelve_una_resolucion_en_escala(self, produccion):
        fuera = _fuera_de_lo_permitido(divisiones_de_25_4(produccion), DIVISIONES_DE_25_4_PERMITIDAS)
        assert not fuera, f"otra función divide 25.4 entre un dpi (use `escala_mm`): {fuera}"

    def test_no_vacuidad_las_divisiones_permitidas_existen_cada_una_en_su_funcion(self, produccion):
        hallados = {(r, f) for r, f, _ in divisiones_de_25_4(produccion)}
        assert hallados == set(DIVISIONES_DE_25_4_PERMITIDAS), f"las divisiones declaradas ya no son las que hay: {sorted(hallados)}"

    @pytest.mark.parametrize("modulo", [SERVICIO, PAGINA, PDF_DIARIO, PDF_MENSUAL])
    @pytest.mark.parametrize("expresion", ["25.4 / dpi", "(25.4 * 2) / dpi", "dpi / 25.4"])
    def test_discrimina_una_division_nueva_en_cada_modulo_vigilado_y_en_cada_forma(self, produccion, modulo, expresion):
        texto = produccion[modulo][0] + f"\n\ndef _escala_a_mano(dpi):\n    return {expresion}\n"
        fuentes = {**produccion, modulo: (texto, ast.parse(texto))}
        fuera = _fuera_de_lo_permitido(divisiones_de_25_4(fuentes), DIVISIONES_DE_25_4_PERMITIDAS)
        assert [(r, f) for r, f, _ in fuera] == [(modulo, "_escala_a_mano")]


# ======================================================================================================== 2. la página no tiene SQL

LLAMADAS_DE_SQL = {"execute", "executemany", "executescript", "cursor", "commit", "rollback", "conectar"}
MODULOS_DE_SQL = ("sqlite3", "PyQt5.QtSql")
NOMBRES_DE_SQL = {"Conexion", "QSqlQuery", "QSqlDatabase"}


def sql_en(fuentes, ruta):
    """[(qué, línea)] de todo lo que en `ruta` toca una base de datos: llamadas de SQL, el nombre `Conexion` y los imports de sqlite3 o QtSql."""
    _, arbol = fuentes[ruta]
    hallados = []
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in LLAMADAS_DE_SQL:
            hallados.append((f".{n.func.attr}(", n.lineno))
        elif isinstance(n, ast.Name) and n.id in NOMBRES_DE_SQL:
            hallados.append((n.id, n.lineno))
        elif isinstance(n, ast.Attribute) and n.attr in NOMBRES_DE_SQL:
            hallados.append((n.attr, n.lineno))
        elif isinstance(n, ast.Import) and any(a.name.split(".")[0] == "sqlite3" or a.name in MODULOS_DE_SQL for a in n.names):
            hallados.append(("import " + ",".join(a.name for a in n.names), n.lineno))
        elif isinstance(n, ast.ImportFrom) and n.module and (n.module.split(".")[0] == "sqlite3" or n.module in MODULOS_DE_SQL or "conection" in n.module):
            hallados.append(("from " + n.module, n.lineno))
    return sorted(hallados)


class TestLaPaginaNoTieneSql:
    def test_la_pagina_no_toca_la_base_de_datos(self, produccion):
        assert not sql_en(produccion, PAGINA), f"la página tiene SQL (todo pasa por el servicio): {sql_en(produccion, PAGINA)}"

    def test_no_vacuidad_es_la_pagina_de_verdad_y_usa_el_servicio(self, produccion):
        texto, arbol = produccion[PAGINA]
        clases = [n.name for n in arbol.body if isinstance(n, ast.ClassDef)]
        funciones = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)]
        llamadas_al_servicio = [n for n in ast.walk(arbol) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "svc"]
        assert "PosicionInicialBraqui" in clases and len(funciones) >= 30 and len(llamadas_al_servicio) >= 6, (clases, len(funciones), len(llamadas_al_servicio))

    @pytest.mark.parametrize("linea", ["cursor.execute('SELECT 1')", "conn.commit()", "c = Conexion()", "import sqlite3",
                                       "from PyQt5.QtSql import QSqlQuery", "from data.ManejoDatos.conection import Conexion", "x = db.cursor()"])
    def test_discrimina_cada_forma_de_tocar_la_bd(self, produccion, linea):
        texto = produccion[PAGINA][0] + "\n\ndef _por_si_acaso(cursor, conn, db):\n    " + linea + "\n" if not linea.startswith(("import", "from")) \
            else linea + "\n" + produccion[PAGINA][0]
        fuentes = {**produccion, PAGINA: (texto, ast.parse(texto))}
        assert sql_en(fuentes, PAGINA), f"el guardia no ve: {linea}"


# ======================================================================================================== 3. una sola regla de vigencia

PREDICADO_DE_FECHA = re.compile(r"\bDATE\(\s*fecha\s*\)|\bfecha\s*(?:=|<=|>=|<>|!=|<|>|BETWEEN\b|IN\b)", re.IGNORECASE)


def consultas_por_fecha(fuentes):
    """[(ruta, función, línea)] de las cadenas que consultan `braqui_posicion_inicial` con un predicado sobre `fecha`."""
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        contenedora = _funcion_contenedora(arbol)
        for nodo, texto in _trozos_de_texto(arbol):
            if "braqui_posicion_inicial" in texto and re.search(r"\bSELECT\b", texto, re.IGNORECASE) and PREDICADO_DE_FECHA.search(texto.split("FROM", 1)[-1]):
                hallados.append((ruta, contenedora.get(id(nodo)), nodo.lineno))
    return sorted(hallados)


def _llama_a(fuentes, ruta, funcion, destino):
    """¿La función `funcion` de `ruta` contiene una llamada a `destino` (por nombre)?"""
    _, arbol = fuentes[ruta]
    for n in ast.walk(arbol):
        if isinstance(n, ast.FunctionDef) and n.name == funcion:
            return any(isinstance(c, ast.Call) and ((isinstance(c.func, ast.Name) and c.func.id == destino)
                                                    or (isinstance(c.func, ast.Attribute) and c.func.attr == destino)) for c in ast.walk(n))
    return False


def _llama_en_cualquier_sitio(fuentes, ruta, destino):
    _, arbol = fuentes[ruta]
    return any(isinstance(c, ast.Call) and ((isinstance(c.func, ast.Name) and c.func.id == destino) or (isinstance(c.func, ast.Attribute) and c.func.attr == destino))
               for c in ast.walk(arbol))


def reglas_incumplidas(fuentes):
    """Lo que debe cumplirse sobre QUIÉN llama a la regla: [texto que nombra el sitio]."""
    falta = []
    for funcion in ("posicion_inicial_para", "existe_vigente"):
        if not _llama_a(fuentes, SERVICIO, funcion, "_vigente_por_fecha"):
            falta.append(f"{SERVICIO}::{funcion} no llama a `_vigente_por_fecha` (¿tiene su propia regla?)")
    for pdf in (PDF_DIARIO, PDF_MENSUAL):
        if not _llama_en_cualquier_sitio(fuentes, pdf, "texto_para_pdf"):
            falta.append(f"{pdf} no pide el texto con `texto_para_pdf` (¿busca la prueba por su cuenta?)")
    if not _llama_a(fuentes, SERVICIO, "texto_para_pdf", "posicion_inicial_para"):
        falta.append(f"{SERVICIO}::texto_para_pdf no usa `posicion_inicial_para`")
    return falta


class TestUnaSolaReglaDeVigencia:
    def test_ninguna_consulta_por_fecha_fuera_de_la_regla(self, produccion):
        fuera = _fuera_de_lo_permitido(consultas_por_fecha(produccion), CONSULTAS_POR_FECHA_PERMITIDAS)
        assert not fuera, f"una consulta de `braqui_posicion_inicial` por fecha fuera de `_vigente_por_fecha` (otra regla de vigencia): {fuera}"

    def test_no_vacuidad_la_regla_existe_y_es_la_unica_que_el_guardia_ve(self, produccion):
        assert {(r, f) for r, f, _ in consultas_por_fecha(produccion)} == set(CONSULTAS_POR_FECHA_PERMITIDAS)
        texto, arbol = produccion[SERVICIO]
        # el servicio tiene varias consultas a la tabla, y solo UNA es por fecha: si el guardia no distinguiera, todas contarían
        consultas = [t for _, t in _trozos_de_texto(arbol) if "braqui_posicion_inicial" in t and re.search(r"\bSELECT\b", t, re.IGNORECASE)]
        assert len(consultas) >= 4, len(consultas)

    def test_los_llamadores_cumplen_la_regla(self, produccion):
        assert reglas_incumplidas(produccion) == []

    def test_discrimina_una_segunda_consulta_por_fecha_en_cualquier_modulo(self, produccion):
        for ruta, sql in (("models/PDF/un_pdf.py", "SELECT * FROM braqui_posicion_inicial WHERE fecha <= ? ORDER BY fecha DESC"),
                          ("ui/una_pantalla.py", "SELECT id FROM braqui_posicion_inicial WHERE DATE(fecha) = ?"),
                          (SERVICIO, "SELECT id FROM braqui_posicion_inicial WHERE fecha BETWEEN ? AND ?")):
            texto = (produccion[ruta][0] if ruta in produccion else "") + f"\n\ndef buscar_por_mi_cuenta(cursor):\n    cursor.execute({sql!r})\n"
            fuentes = {**produccion, ruta: (texto, ast.parse(texto))}
            fuera = _fuera_de_lo_permitido(consultas_por_fecha(fuentes), CONSULTAS_POR_FECHA_PERMITIDAS)
            assert [(r, f) for r, f, _ in fuera] == [(ruta, "buscar_por_mi_cuenta")], (ruta, fuera)

    def test_discrimina_un_llamador_que_no_usa_la_regla(self, produccion):
        servicio = produccion[SERVICIO][0].replace("_vigente_por_fecha(cursor,", "_otra_regla(cursor,")
        assert servicio != produccion[SERVICIO][0]
        fuentes = {**produccion, SERVICIO: (servicio, ast.parse(servicio))}
        assert any("posicion_inicial_para" in f or "existe_vigente" in f for f in reglas_incumplidas(fuentes)), reglas_incumplidas(fuentes)

    @pytest.mark.parametrize("pdf", [PDF_DIARIO, PDF_MENSUAL])
    def test_discrimina_un_pdf_que_busca_la_prueba_por_su_cuenta(self, produccion, pdf):
        texto = produccion[pdf][0].replace("texto_para_pdf", "posicion_inicial_para")
        assert texto != produccion[pdf][0]
        fuentes = {**produccion, pdf: (texto, ast.parse(texto))}
        assert any(f.startswith(pdf) for f in reglas_incumplidas(fuentes)), reglas_incumplidas(fuentes)


# ======================================================================================================== 4. ninguna escritura a desplazamiento_ini

ESCRITURA_DE_DESPLAZAMIENTO = re.compile(r"(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|REPLACE\s+INTO|UPDATE)\s+CondicionesMedicion\b", re.IGNORECASE)


def escrituras_de_desplazamiento(fuentes):
    """[(ruta, función, línea)] de las sentencias que ESCRIBEN `CondicionesMedicion` y nombran `desplazamiento_ini` (`INSERT`, `REPLACE`, `UPDATE`)."""
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        contenedora = _funcion_contenedora(arbol)
        for nodo, texto in _trozos_de_texto(arbol):
            if "desplazamiento_ini" in texto and ESCRITURA_DE_DESPLAZAMIENTO.search(texto):
                hallados.append((ruta, contenedora.get(id(nodo)), nodo.lineno))
    return sorted(hallados)


class TestNingunaEscrituraADesplazamientoIni:
    def test_solo_el_guardado_del_mensual_escribe_desplazamiento_ini(self, produccion):
        fuera = _fuera_de_lo_permitido(escrituras_de_desplazamiento(produccion), ESCRITURAS_DE_DESPLAZAMIENTO_PERMITIDAS)
        assert not fuera, f"otra sentencia escribe `CondicionesMedicion.desplazamiento_ini` fuera del guardado del mensual: {fuera}"

    def test_no_vacuidad_el_insert_del_guardado_existe_y_la_definicion_de_la_tabla_no_cuenta(self, produccion):
        assert {(r, f) for r, f, _ in escrituras_de_desplazamiento(produccion)} == set(ESCRITURAS_DE_DESPLAZAMIENTO_PERMITIDAS)
        # el CREATE TABLE de `conection.py` nombra la columna y trae `ON UPDATE`: el guardia distingue una definición de una escritura
        definiciones = [t for _, t in _trozos_de_texto(produccion["data/ManejoDatos/conection.py"][1]) if "CREATE TABLE" in t and "CondicionesMedicion" in t]
        assert definiciones and all("desplazamiento_ini" in t for t in definiciones)

    @pytest.mark.parametrize("sql", ["UPDATE CondicionesMedicion SET desplazamiento_ini = ? WHERE ref = ?",
                                     "INSERT INTO CondicionesMedicion (ref, desplazamiento_ini) VALUES (?, ?)",
                                     "INSERT OR REPLACE INTO CondicionesMedicion (ref, desplazamiento_ini) VALUES (?, ?)",
                                     "REPLACE INTO CondicionesMedicion (ref, desplazamiento_ini) VALUES (?, ?)"])
    def test_discrimina_cada_forma_de_escribir_la_columna(self, produccion, sql):
        for ruta in ("ui/paginasControles/PruebasMensuales/braq_mensual.py", SERVICIO):
            texto = produccion[ruta][0] + f"\n\ndef escribir_a_mano(cursor, a, b):\n    cursor.execute({sql!r}, (a, b))\n"
            fuentes = {**produccion, ruta: (texto, ast.parse(texto))}
            fuera = _fuera_de_lo_permitido(escrituras_de_desplazamiento(fuentes), ESCRITURAS_DE_DESPLAZAMIENTO_PERMITIDAS)
            assert [(r, f) for r, f, _ in fuera] == [(ruta, "escribir_a_mano")], (ruta, sql, fuera)

    def test_una_lectura_o_una_definicion_no_es_una_escritura(self, produccion):
        for sql in ("SELECT t, p, h, desplazamiento_ini FROM CondicionesMedicion WHERE ref = ?",
                    "CREATE TABLE IF NOT EXISTS CondicionesMedicion (ref INTEGER, desplazamiento_ini REAL, FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON UPDATE CASCADE)"):
            texto = produccion[SERVICIO][0] + f"\n\ndef leer(cursor):\n    cursor.execute({sql!r})\n"
            fuentes = {**produccion, SERVICIO: (texto, ast.parse(texto))}
            assert _fuera_de_lo_permitido(escrituras_de_desplazamiento(fuentes), ESCRITURAS_DE_DESPLAZAMIENTO_PERMITIDAS) == [], sql


# ======================================================================================================== 5. el texto breve se construye en un solo sitio

def constructores_del_texto(fuentes):
    """[(ruta, función, línea)] de las cadenas que llevan a la vez «±» y «(k = 2)»: la huella del texto breve de la posición inicial."""
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        contenedora = _funcion_contenedora(arbol)
        for nodo, texto in _trozos_de_texto(arbol):
            if "±" in texto and "(k = 2)" in texto:
                hallados.append((ruta, contenedora.get(id(nodo)), nodo.lineno))
    return sorted(hallados)


def consumidores_incumplidos(fuentes):
    falta = []
    if not _llama_en_cualquier_sitio(fuentes, PAGINA, "texto_breve"):
        falta.append(f"{PAGINA} no pide el texto con `texto_breve`")
    for pdf in (PDF_DIARIO, PDF_MENSUAL):
        if not _llama_en_cualquier_sitio(fuentes, pdf, "texto_para_pdf"):
            falta.append(f"{pdf} no pide el texto con `texto_para_pdf`")
    return falta


class TestElTextoBreveSeConstruyeEnUnSoloSitio:
    def test_ningun_otro_sitio_arma_el_texto(self, produccion):
        fuera = _fuera_de_lo_permitido(constructores_del_texto(produccion), CONSTRUCTORES_DEL_TEXTO_PERMITIDOS)
        assert not fuera, f"otro sitio arma un texto con «±» y «(k = 2)» (use `texto_breve`): {fuera}"

    def test_no_vacuidad_texto_breve_tiene_sus_ramas_y_es_el_unico(self, produccion):
        hallados = constructores_del_texto(produccion)
        assert {(r, f) for r, f, _ in hallados} == set(CONSTRUCTORES_DEL_TEXTO_PERMITIDOS)
        assert len(hallados) >= 3, f"`texto_breve` tiene {len(hallados)} ramas con «±» y «(k = 2)» (eran 3): ¿se partió?"

    def test_los_tres_consumidores_piden_el_texto_a_su_unico_dueno(self, produccion):
        assert consumidores_incumplidos(produccion) == []

    @pytest.mark.parametrize("ruta", [PDF_DIARIO, PDF_MENSUAL, PAGINA])
    def test_discrimina_un_consumidor_que_arma_su_propio_texto(self, produccion, ruta):
        texto = produccion[ruta][0] + "\n\ndef _mi_texto(px, u):\n    return f'{px:.2f} ± {u:.2f} mm (k = 2)'\n"
        fuentes = {**produccion, ruta: (texto, ast.parse(texto))}
        assert [(r, f) for r, f, _ in _fuera_de_lo_permitido(constructores_del_texto(fuentes), CONSTRUCTORES_DEL_TEXTO_PERMITIDOS)] == [(ruta, "_mi_texto")]

    @pytest.mark.parametrize("ruta,destino", [(PAGINA, "texto_breve"), (PDF_DIARIO, "texto_para_pdf"), (PDF_MENSUAL, "texto_para_pdf")])
    def test_discrimina_un_consumidor_que_deja_de_pedirlo(self, produccion, ruta, destino):
        texto = produccion[ruta][0].replace(destino, "otra_cosa")
        assert texto != produccion[ruta][0]
        fuentes = {**produccion, ruta: (texto, ast.parse(texto))}
        assert any(f.startswith(ruta) for f in consumidores_incumplidos(fuentes)), consumidores_incumplidos(fuentes)
