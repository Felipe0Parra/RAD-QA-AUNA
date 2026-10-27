"""G.1 (26-10-2026; PLAN_ANALISIS_PELICULAS_08-10.md, DA-89): el codigo del analisis mensual VIEJO se retira, y nadie lo vuelve a conectar por descuido (DA-68: lo que no existe no se reconecta).

Tras E.2 (la ventana nueva) y F.1 (el PDF nuevo) nadie llega al analisis viejo: `PruebaMensual600.analizar_imagen` y todo lo que alcanza quedaron sin llamadores. G.1 los retira (derivado del
grafo por AST, no de una lista a mano) y NO cambia nada que se imprima ni que se guarde: lo guardado con el metodo viejo sigue en la base, en el contrato de QC y en la exportacion, sin que el mensual
ni el PDF lo lean. Este archivo es el tripwire de esa retirada. Por AST sobre el arbol de produccion (fuera de `tests/`, `.venv/`, `build/`), cada tripwire con su caso sintetico en `tmp_path` (un
intruso que lo viola se caza, uno que no, pasa) para que ninguno sea vacuo:

  1. LO RETIRADO NO EXISTE: los dos archivos borrados no estan ni se importan; ninguna de las definiciones retiradas esta definida (las 42 del grafo mas las 7 de la pestana y del punto 8 de DA-89);
     `PruebaMensual600` no tiene ninguno de sus 9 metodos; `Analisis_PlacaRC.py` define EXACTAMENTE las 10 funciones de `analizar_lineas` y todas son alcanzables desde ella (el control del recorte).
  2. NADIE VUELVE A IMPORTAR: ningun import (ni cadena) nombra `analisisImagenes.Analisis_PlacaCuadrada` ni `services.conexiones_qt`; ningun nombre `analizar_cuadrado2`, `generar_reporte_completo` ni
     `conectar_unico`; `build_exe.py` no lista el modulo y todo hidden-import suyo existe.
  3. NADIE INSERTA EN `analisis_placa_*`: ninguna constante SQL de produccion con INSERT o REPLACE sobre las tres tablas ni una llamada a `reemplazar_bloque` con esos nombres literales. El nombre se lee
     como SQLite lo lee: sin distinguir mayusculas y con el sufijo interpolado o armado por partes (`analisis_placa_{tipo}`, `"analisis_placa_" + tipo`) contado como una tabla vieja (ronda 1, G1-REV-P1 y P3).
  4. NADIE ESCRIBE UN VALOR NUEVO EN `preguntas.imagen`: ninguna constante `UPDATE preguntas SET ... imagen` (ni con la lista de campos dinamica), ningun `INSERT INTO preguntas (... imagen ...)` o `REPLACE INTO` igual
     (ni con la lista de columnas dinamica ni SIN lista de columnas, que escribe todas) y ninguna llamada a `reemplazar_bloque` con `"preguntas"` literal (ronda 1, G1-REV-P2) (la unica escritura que queda es la generica de `subirlineasmensuales`, que hereda la vigente: lo fija PR1).
  5. NADIE LEE LOS VALORES DE LAS TABLAS VIEJAS FUERA DE LA LISTA (DA-89): el conjunto (archivo, funcion, tabla) de las constantes de texto que no son docstrings y nombran las tres tablas es EXACTAMENTE
     el de 18 sitios de abajo, cada uno con su motivo. Una lectura nueva, o volver a poner una hermana en `tablas_relacionadas`, cae; tambien la que escribe el nombre en mayusculas o deja el sufijo
     interpolado (ese sitio se llama `analisis_placa_<dinamica>` y ninguno esta declarado; ronda 1, G1-REV-P1 y P3).
  6. LA PESTANA «GRAFICOS» (lo que se queda): `setupTap1` ya no crea `boton_anterior` ni `boton_siguiente` ni nombra `lista_graficas`/`grafica_actual`, cada `X.connect(self.Y)` de `graphicsWindow` y
     `setupTap1` resuelve `Y` en la MRO de `PruebaMensual600`, y con el 600 mensual real construido la pestana tiene combo, lienzo, tabla y la barra Eliminar/Editar/Aceptar/Cancelar/Buscar, y ningun
     boton «Anterior» o «Siguiente».
  7. «ANALISIS IMG» QUEDA VACIA (G1-D1; G.1b, DA-91): `mostrar_controles_mensuales` para el 600, el iX y el Halcyon, sobre una BD sembrada y sobre la copia de la produccion del 06-10: la columna «Analisis Img»
     (su encabezado se queda) no tiene widget y lleva en cada fila UN item vacio, no editable y sin metadatos de tabla (G.1 la dejaba sin item; el fisico eligio la opcion (a) de G1-D1 el 26-10 y G.1b la hizo:
     lo que hace «Editar» y el doble clic sobre ella lo fija `test_g1b_analisis_img_no_editable.py`); «Dif. Punt - Tel» sigue con su valor; las demas «Ver tabla» siguen con su boton.
  8. EL PDF DICE LO MISMO: sin N y sin V, `_secciones_de_la_placa` da `analisis_imagen` = el DataFrame de una fila «No hay datos de analisis de imagen» (igual a HEAD: la 8a no cae contra HEAD);
     el PDF del 600 y del iX ya no lee las dos tablas hermanas (G1-D2) y sigue leyendo `analisis_placa_franjas` (V de F.1).
  9. NINGUNA PANTALLA LLEGA A UN `analizar_imagen` DE `seiscientos_mensual.py` (la arista dinamica de `PruebasDiarias.py:1039`): solo braqui diario y el anual del Halcyon construyen el cargador
     compartido con `analisis` verdadero, y los dos resuelven el suyo.

Trampa 2 (todo cuadro de dialogo se parcha: la fixture `dialogos` de `_e1_ayudas`), Trampa 3 (`limpiar_recursos()` antes de cerrar una pagina y un `sys.excepthook` propio), Trampa 9 (cierre completo
de cada pagina y tabla; ninguna huella mira internos de Qt), Trampa 10 (ningun `lru_cache` ni `skip` por parametro). Ninguna BD de referencia se abre directo: se copia a `tmp_path` y `ruta_base_datos`
se parchea ANTES de construir `Conexion()`.
Rojo contra HEAD (b5a8234): caen 1-7 y 9 por aserciones; la 8a (el DataFrame) pasa en los dos (no regresion), la 8b (las tablas hermanas) cae.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import importlib
import importlib.util
import re
import shutil
import sqlite3
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest
from PyQt5 import sip
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem

import _bd_referencia
import data.ManejoDatos.conection as conection_mod
from _e1_ayudas import _cursor_limpio, app, cerrar, dialogos  # noqa: F401  (fixtures y ayudas de E.1)
from data.ManejoDatos.conection import Conexion
from test_e2_mensual_abre_el_analisis_nuevo import (  # noqa: F401  (la compuerta por AST y por MRO de E.2, una sola definicion)
    _clases_que_violan, _es_el_analisis_viejo, _sitios_del_cargador, la_ui)

RAIZ = Path(__file__).resolve().parent.parent
SM = "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py"
RC = "analisisImagenes/Analisis_PlacaRC.py"
CU = "analisisImagenes/Analisis_PlacaCuadrada.py"
LOAD = "data/ManejoDatos/load.py"
CQT = "services/conexiones_qt.py"
RM = "models/PDF/Mensuales/reportes_mensuales.py"
BUILD = "build_exe.py"

# ---- 1. lo retirado (derivado del grafo: `PLAN_ANALISIS_PELICULAS_08-10_anexo/logs/G1/grafo.log` §2)
METODOS_DEL_600 = ("analizar_imagen", "mostrar_resultados_AnalisisImagen", "guardar_analsis", "guardar_analisis_e_imagen", "dbImagen",
                   "mostrar_grafica_actual", "mostrar_grafica_anterior", "mostrar_grafica_siguiente", "limpiar_canvas")
FUNCIONES_RETIRADAS = {
    RC: ("cargar_imagen", "calcular_altura_media", "hallar_interceptos", "encontrar_anchura", "guardar_datos", "normalizar_perfil", "informacion_perfil", "_filtrar_cruces_externos", "interseccion",
         "detectar_contornos", "ajustar_esquinas_manual", "analisis_campo", "graficar_analisis_campo", "analizar_cuadrado"),
    LOAD: ("crear_algo", "guardar_analisis_placa600", "mostrar_analisis_img", "mostrar_analisis_franjas", "mostrar_veri_corr"),
    RM: ("_crear_tabla_analisis_imagen",),
}
LAS_DIEZ = {"_get_mpl", "analizar_circulos_perfil", "analizar_lineas", "calcular_distancias", "detectar_picos", "generar_reporte", "graficar_resultados", "metadata", "obtener_perfil", "preprocesar_imagen"}
ARCHIVOS_BORRADOS = (CU, CQT)
MODULOS_RETIRADOS = ("analisisImagenes.Analisis_PlacaCuadrada", "services.conexiones_qt")
NOMBRES_RETIRADOS = ("analizar_cuadrado2", "generar_reporte_completo", "conectar_unico")
NOMBRES_DE_LA_PESTANA = ("boton_anterior", "boton_siguiente", "lista_graficas", "grafica_actual", "botones_layout")

TABLAS_VIEJAS = ("analisis_placa_franjas", "analisis_placa_verificaciones", "analisis_placa_correcciones")
# UNA sola definicion de como un texto SQL nombra una de las tres tablas viejas (los detectores de los tripwires 3 y 5 la usan; revision ronda 1, G1-REV-P1 y P3). SQLite no distingue mayusculas en los nombres
# (`ANALISIS_PLACA_CORRECCIONES` es la misma tabla), y el sufijo puede llegar interpolado o armado por partes (`f"... analisis_placa_{tipo}"`, `"analisis_placa_" + tipo`, `% tipo`, `.format`): el prefijo
# seguido de una interpolacion (`\x00` en `unidades_de_texto`), de `%`, de `{` o del final del texto cuenta como UNA tabla vieja de la que no se ve cual es (`PREFIJO_DINAMICO`, que ningun sitio permitido
# declara). `analisis_placa_mensual` (la tabla nueva de D.1) comparte el prefijo y no es ninguna de las dos cosas.
PREFIJO_DINAMICO = "analisis_placa_<dinamica>"
NOMBRE_DE_TABLA_VIEJA = r"analisis_placa_(?:(?:franjas|verificaciones|correcciones)\b|(?=[\x00%{]|$))"
TABLA_VIEJA = re.compile(NOMBRE_DE_TABLA_VIEJA, re.IGNORECASE)


def nombre_de_la_tabla_vieja(coincidencia):
    """El nombre normalizado (minusculas) de lo que `TABLA_VIEJA` encontro, o `PREFIJO_DINAMICO` si el sufijo no se ve."""
    nombre = coincidencia.group(0).lower()
    return nombre if nombre in TABLAS_VIEJAS else PREFIJO_DINAMICO

# ---- 5. los 18 sitios (archivo, funcion, tabla) donde el codigo de produccion nombra las tres tablas viejas, cada uno con su motivo (`logs/G1/sitios_tablas_viejas.log`, `espejo_g1`)
ESQUEMA = "el esquema: `Conexion.crearTablaAnalisis600` crea la tabla (sigue en la base)"
CONTRATO = "el contrato de QC: la anulacion generica (`TABLAS_ANULABLES`/`CLAVES_INDICE`) las nombra y sigue permitida"
SCRIPT_INDICES = "el script de indices del bloque de QC (`scripts/indices_bloque_qc.py`)"
SCRIPT_SANEAMIENTO = "el script de saneamiento del bloque de QC (`scripts/saneamiento_bloque_qc.py`)"
SITIOS_PERMITIDOS = {
    ("data/ManejoDatos/conection.py", "Conexion.crearTablaAnalisis600", "analisis_placa_franjas"): ESQUEMA,
    ("data/ManejoDatos/conection.py", "Conexion.crearTablaAnalisis600", "analisis_placa_verificaciones"): ESQUEMA,
    ("data/ManejoDatos/conection.py", "Conexion.crearTablaAnalisis600", "analisis_placa_correcciones"): ESQUEMA,
    ("data/ManejoDatos/load.py", "_mostrar_dialogo", "analisis_placa_franjas"): "G1-D4: la guarda `if tabla_db != \"analisis_placa_franjas\":` del dialogo compartido de las «Ver tabla» vivas (queda siempre verdadera)",
    ("models/PDF/Mensuales/reportes_mensuales.py", "ReporteMensual.__init__", "analisis_placa_franjas"): "el PDF del 600 y del iX SOLO cuenta las franjas (V de F.1); G1-D2: las dos hermanas salieron",
    ("models/PDF/Mensuales/reportes_mensuales.py", "_secciones_de_la_placa", "analisis_placa_franjas"): "V de F.1: `bool(datos_completos['analisis_placa_franjas'])` elige la linea sin analisis nuevo",
    ("scripts/indices_bloque_qc.py", "<modulo>", "analisis_placa_franjas"): SCRIPT_INDICES,
    ("scripts/indices_bloque_qc.py", "<modulo>", "analisis_placa_verificaciones"): SCRIPT_INDICES,
    ("scripts/indices_bloque_qc.py", "<modulo>", "analisis_placa_correcciones"): SCRIPT_INDICES,
    ("scripts/saneamiento_bloque_qc.py", "<modulo>", "analisis_placa_franjas"): SCRIPT_SANEAMIENTO,
    ("scripts/saneamiento_bloque_qc.py", "<modulo>", "analisis_placa_verificaciones"): SCRIPT_SANEAMIENTO,
    ("scripts/saneamiento_bloque_qc.py", "<modulo>", "analisis_placa_correcciones"): SCRIPT_SANEAMIENTO,
    ("services/anulacion.py", "<modulo>", "analisis_placa_franjas"): CONTRATO,
    ("services/anulacion.py", "<modulo>", "analisis_placa_verificaciones"): CONTRATO,
    ("services/anulacion.py", "<modulo>", "analisis_placa_correcciones"): CONTRATO,
    ("ui/paginasControles/PruebasMensuales/imagen_del_campo.py", "hay_franjas_vigentes", "analisis_placa_franjas"): "el conteo de V de E.2 (`SELECT COUNT(*) ... WHERE ref = ?`, sin leer ningun valor)",
    ("ui/paginasGuia/SQLtoEXCEL.py", "ExportarExcel.__init__", "analisis_placa_correcciones"): "la exportacion a Excel (lo guardado no se toca, regla del 09-09)",
    ("ui/paginasGuia/SQLtoEXCEL.py", "ExportarExcel.__init__", "analisis_placa_franjas"): "la exportacion a Excel (lo guardado no se toca, regla del 09-09)",
}

EQUIPOS = {"600": "Clinac 600", "ix": "Clinac ix", "halcyon": "Halcyon"}
ANALISIS_IMG = "Análisis Img"
TAL_CUAL_600_IX = {"Eq. Medición", "Seguridad", "Indc. Angulares", "Tam. Campos", "Dosimetría", "Reporte PDF"}
TAL_CUAL_HALCYON = {"Eq. Medición", "Laseres", "Indc. Angulares", "Indc. Camilla", "Desp. Isocentro", "Tam. Campos", "Dosimetría", "Reporte PDF"}


# ====================================================================================================================================== el recorrido del arbol de produccion

def archivos_de_produccion(raiz):
    """Cada `.py` del arbol de produccion bajo `raiz` (rutas relativas, con `/`): sin `tests/`, `.venv/`, `build/` ni `dist/` de la raiz, ni `__pycache__` ni carpetas ocultas. Con `os.walk` y poda: recorrer
    el `.venv` entero (decenas de miles de archivos) con `rglob` cuesta segundos por prueba."""
    raiz = Path(raiz)
    salida = []
    for dirpath, dirnames, filenames in os.walk(raiz):
        en_la_raiz = Path(dirpath) == raiz
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__" and not d.startswith(".") and not (en_la_raiz and d in ("tests", "build", "dist")))
        salida.extend((Path(dirpath) / f).relative_to(raiz).as_posix() for f in sorted(filenames) if f.endswith(".py"))
    return sorted(salida)


def arboles_de(raiz):
    """{ruta relativa: AST} de todo el arbol de produccion bajo `raiz`."""
    return {rel: ast.parse((Path(raiz) / rel).read_text(encoding="utf-8")) for rel in archivos_de_produccion(raiz)}


@pytest.fixture(scope="module")
def produccion_ast():
    """El AST de todo el arbol de produccion real: se lee una vez por modulo y nadie lo muta (Trampa 10: sin `lru_cache`, el orden de las pruebas no cuenta)."""
    return arboles_de(RAIZ)


def _docstrings(arbol):
    """Los ids de los nodos `Constant` que son docstring de modulo, clase o funcion."""
    salida = set()
    for n in ast.walk(arbol):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
            salida.add(id(n.body[0].value))
    return salida


def constantes_de_texto(arbol):
    """(linea, texto) de cada `Constant` de texto que no es docstring, tambien las partes de un f-string y los textos dentro de sus llamadas."""
    docs = _docstrings(arbol)
    return [(n.lineno, n.value) for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


# Como arma el codigo un texto SQL que no es un literal solo: un f-string, `+` entre textos, `texto % valores` y `texto.format(valores)`. `_texto_armado` los lee a todos igual: el texto que se VE, con `\x00` donde va
# una parte que no es un literal (G1-R2-P1, revision ronda 2: la ronda 1 solo lo hizo para el f-string, y el mismo `INSERT INTO preguntas (%s)` con `%`, `.format` o `+` pasaba).
_MARCA_DE_PORCENTAJE = re.compile(r"%%|%(?:\([^)]*\))?[#0\- +]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[diouxXeEfFgGcrsa]")
_MARCA_DE_FORMAT = re.compile(r"\{\{|\}\}|\{[^{}]*\}")


def _texto_armado(nodo):
    """El texto que arma una expresion de texto (un literal, un f-string, una suma de textos, `texto % valores` o `texto.format(valores)`), con `\\x00` donde va cada parte que no es un literal; `None` si la
    expresion no arma texto. Una suma solo cuenta si algun lado es texto (`1 + 2` no); `%%`, `{{` y `}}` son los literales `%`, `{` y `}`."""
    if isinstance(nodo, ast.Constant):
        return nodo.value if isinstance(nodo.value, str) else None
    if isinstance(nodo, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "\x00" for v in nodo.values)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        izquierda, derecha = _texto_armado(nodo.left), _texto_armado(nodo.right)
        if izquierda is None and derecha is None:
            return None
        return ("\x00" if izquierda is None else izquierda) + ("\x00" if derecha is None else derecha)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Mod):
        base = _texto_armado(nodo.left)
        return None if base is None else _MARCA_DE_PORCENTAJE.sub(lambda m: "%" if m.group(0) == "%%" else "\x00", base)
    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "format":
        base = _texto_armado(nodo.func.value)
        return None if base is None else _MARCA_DE_FORMAT.sub(lambda m: {"{{": "{", "}}": "}"}.get(m.group(0), "\x00"), base)
    return None


def unidades_de_texto(arbol):
    """(linea, texto) de cada texto SQL completo que no es docstring: un `Constant` suelto o el texto que ARMA una expresion (f-string, `+`, `%`, `.format`; ver `_texto_armado`), con `\\x00` donde va cada parte que no
    es un literal (asi `INSERT INTO preguntas ({columnas})`, `"INSERT INTO preguntas (%s)" % columnas` y `"INSERT INTO preguntas (" + columnas + ")"` se ven igual: `INSERT INTO preguntas (\\x00)`). Los literales
    que son parte de una expresion mayor no cuentan aparte."""
    docs = _docstrings(arbol)
    dentro = set()
    unidades = []
    for n in ast.walk(arbol):                                         # en anchura: el padre se ve antes que sus hijos, que ya quedan dentro de el
        if id(n) in dentro or id(n) in docs or not isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)):
            continue
        texto = _texto_armado(n)
        if texto is not None:
            unidades.append((n.lineno, texto))
            dentro.update(id(h) for h in ast.walk(n) if h is not n)
    return unidades


def _dueno(arbol, linea):
    """La funcion de nivel superior (o `Clase.metodo`) que contiene esa linea; `<modulo>` si es codigo del modulo."""
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= linea <= n.end_lineno:
            return n.name
        if isinstance(n, ast.ClassDef) and n.lineno <= linea <= n.end_lineno:
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.lineno <= linea <= m.end_lineno:
                    return f"{n.name}.{m.name}"
            return f"{n.name}.<cuerpo>"
    return "<modulo>"


# ====================================================================================================================================== los detectores (cada uno con su prueba sintetica)

def sitios_de_las_tablas_viejas(arboles):
    """{(archivo, funcion, tabla)} de los textos (no docstrings; `unidades_de_texto`: el texto entero, armado con f-string, `+`, `%` o `.format`) que nombran `analisis_placa_franjas`, `_verificaciones` o `_correcciones`."""
    return {(rel, _dueno(arbol, linea), nombre_de_la_tabla_vieja(m)) for rel, arbol in arboles.items() for linea, texto in unidades_de_texto(arbol) for m in TABLA_VIEJA.finditer(texto)}


def _llamadas(arbol, nombre):
    return [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and (getattr(n.func, "id", None) == nombre or getattr(n.func, "attr", None) == nombre)]


def _con_la_tabla_literal(llamada, tablas):
    """Si algun argumento de la llamada es, como literal, el nombre de una de `tablas` (en minusculas; SQLite no distingue mayusculas)."""
    return any(isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.lower() in tablas for a in list(llamada.args) + [k.value for k in llamada.keywords])


ESCRITURA_EN_LAS_VIEJAS = re.compile(r"\b(INSERT|REPLACE)\b[^;]*?" + NOMBRE_DE_TABLA_VIEJA, re.IGNORECASE | re.DOTALL)


def inserciones_en_las_tablas_viejas(arboles):
    """Donde la produccion INSERTA o REEMPLAZA en las tablas viejas: una constante SQL (INSERT o REPLACE ... tabla) o un `reemplazar_bloque` con el nombre de la tabla como literal."""
    hallazgos = []
    for rel, arbol in arboles.items():
        for linea, texto in unidades_de_texto(arbol):
            if ESCRITURA_EN_LAS_VIEJAS.search(texto):
                hallazgos.append(f"{rel}:{linea} SQL: {texto.strip()[:70]!r}")
        for llamada in _llamadas(arbol, "reemplazar_bloque"):
            if _con_la_tabla_literal(llamada, TABLAS_VIEJAS):
                hallazgos.append(f"{rel}:{llamada.lineno} reemplazar_bloque con una tabla vieja")
    return hallazgos


# El nombre de la tabla `preguntas` como SQLite lo acepta (revision ronda 1, G1-REV-P2): con su base (`main.`) y entre comillas (`"preguntas"`, `'preguntas'`, `` `preguntas` ``, `[preguntas]`); `preguntas_respaldo` es otra tabla.
TABLA_PREGUNTAS = r"""(?:main\s*\.\s*)?["`\['"]?preguntas(?!\w)["`\]'"]?"""
UPDATE_DE_PREGUNTAS = r"\bUPDATE\s+(?:OR\s+\w+\s+)?" + TABLA_PREGUNTAS + r"\s+SET\b"
UPDATE_DE_IMAGEN = re.compile(UPDATE_DE_PREGUNTAS + r"[^;]*?\bimagen\b", re.IGNORECASE | re.DOTALL)
# Una lista de campos dinamica en el SET (`SET {campos} WHERE ...`) no deja ver que no lleve `imagen`: la misma regla que la lista de columnas dinamica del INSERT. El WHERE no cuenta.
UPDATE_CON_CAMPOS_QUE_NO_SE_VEN = re.compile(UPDATE_DE_PREGUNTAS + r"(?:(?!\bWHERE\b)[^;])*?\x00", re.IGNORECASE | re.DOTALL)
# `INSERT [OR x] INTO` o `REPLACE INTO` (la otra forma de INSERT OR REPLACE), con la lista de columnas si la lleva.
INSERT_DE_PREGUNTAS = re.compile(r"\b(?:INSERT\s+(?:OR\s+\w+\s+)?|REPLACE\s+)INTO\s+" + TABLA_PREGUNTAS + r"\s*(\([^)]*\))?", re.IGNORECASE | re.DOTALL)


def escrituras_de_la_imagen(arboles):
    """Donde la produccion escribe un valor NUEVO en `preguntas.imagen`: `UPDATE preguntas SET ... imagen` (o con la lista de campos dinamica), `INSERT INTO preguntas (...)` o `REPLACE INTO preguntas (...)` con
    `imagen` en la lista o con la lista de columnas dinamica (no se puede ver que no la incluya), un INSERT o REPLACE SIN lista de columnas (escribe todas, la imagen incluida) y `reemplazar_bloque` con
    `\"preguntas\"` literal."""
    hallazgos = []
    for rel, arbol in arboles.items():
        for linea, texto in unidades_de_texto(arbol):
            if UPDATE_DE_IMAGEN.search(texto):
                hallazgos.append(f"{rel}:{linea} UPDATE de la imagen")
            if UPDATE_CON_CAMPOS_QUE_NO_SE_VEN.search(texto):
                hallazgos.append(f"{rel}:{linea} UPDATE de preguntas con campos que no se ven")
            for m in INSERT_DE_PREGUNTAS.finditer(texto):
                columnas = m.group(1)
                if columnas is None:
                    hallazgos.append(f"{rel}:{linea} INSERT en preguntas sin lista de columnas (escribe todas, la imagen incluida)")
                elif "imagen" in columnas.lower() or "\x00" in columnas:
                    hallazgos.append(f"{rel}:{linea} INSERT en preguntas con la imagen (o con columnas que no se ven)")
        for llamada in _llamadas(arbol, "reemplazar_bloque"):
            if _con_la_tabla_literal(llamada, ("preguntas",)):
                hallazgos.append(f"{rel}:{llamada.lineno} reemplazar_bloque sobre preguntas")
    return hallazgos


def _ultimo(dotted):
    return dotted.split(".")[-1]


def usos_de_lo_retirado(arboles):
    """Los imports (de cualquier forma, tambien por cadena) que nombran los dos modulos retirados, y los nombres retirados como nombre, atributo, alias, definicion o cadena. Los docstrings y los
    comentarios no cuentan (un comentario ni siquiera esta en el AST)."""
    modulos = {_ultimo(m) for m in MODULOS_RETIRADOS}                    # Analisis_PlacaCuadrada, conexiones_qt
    identificadores = set(NOMBRES_RETIRADOS) | modulos
    hallazgos = []
    for rel, arbol in arboles.items():
        docs = _docstrings(arbol)
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                hallazgos += [f"{rel}:{n.lineno} import {a.name}" for a in n.names if _ultimo(a.name) in modulos]
            elif isinstance(n, ast.ImportFrom):
                if _ultimo(n.module or "") in modulos:
                    hallazgos.append(f"{rel}:{n.lineno} from {n.module} import ...")
                hallazgos += [f"{rel}:{n.lineno} from {n.module or '.'} import {a.name}" for a in n.names if a.name in modulos]
            if isinstance(n, ast.Name):
                nombres = [n.id]
            elif isinstance(n, ast.Attribute):
                nombres = [n.attr]
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nombres = [n.name]
            elif isinstance(n, ast.alias):
                nombres = [n.name, n.asname or ""]
            else:
                nombres = []
            hallazgos += [f"{rel}:{getattr(n, 'lineno', '?')} nombra {x!r}" for x in nombres if x in identificadores]
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and (n.value in identificadores or any(m in n.value for m in modulos)):
                hallazgos.append(f"{rel}:{n.lineno} cadena {n.value[:60]!r}")
    return hallazgos


def _escribir_arbol(raiz, archivos):
    for rel, texto in archivos.items():
        destino = Path(raiz) / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(textwrap.dedent(texto), encoding="utf-8")
    return Path(raiz)


# ====================================================================================================================================== 1. lo retirado no existe

class TestLoRetiradoNoExiste:
    @pytest.mark.parametrize("rel", ARCHIVOS_BORRADOS)
    def test_los_dos_archivos_borrados_no_existen_ni_se_importan(self, rel):
        assert not (RAIZ / rel).exists(), f"{rel} debia desaparecer con G.1 (git rm)"
        dotted = rel[:-3].replace("/", ".")
        assert importlib.util.find_spec(dotted) is None, f"{dotted} todavia se puede importar"

    @pytest.mark.parametrize("rel", sorted(FUNCIONES_RETIRADAS))
    def test_ninguna_definicion_retirada_sigue_definida_en_su_archivo(self, rel, produccion_ast):
        definidas = {n.name for n in ast.walk(produccion_ast[rel]) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        vivas = sorted(definidas & set(FUNCIONES_RETIRADAS[rel]))
        assert vivas == [], f"{rel} todavia define lo retirado: {vivas}"

    def test_el_bloque_main_de_analisis_placa_rc_salio(self, produccion_ast):
        assert [n for n in produccion_ast[RC].body if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)] == []

    def test_pruebamensual600_no_tiene_ninguno_de_sus_nueve_metodos(self, app):
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        vivos = [m for m in METODOS_DEL_600 if m in PruebaMensual600.__dict__]
        assert vivos == [], f"PruebaMensual600 todavia define: {vivos}"
        assert not hasattr(PruebaMensual600, "analizar_imagen"), "ni heredado de otra clase"

    def test_analisis_placa_rc_define_exactamente_las_diez_y_todas_se_alcanzan_desde_analizar_lineas(self, produccion_ast):
        """El control del recorte: si se retira una funcion de MAS (alguna de las 10) o se deja una de menos, cae. El recorrido es el de los nombres que cada funcion nombra, desde `analizar_lineas`."""
        arbol = produccion_ast[RC]
        funciones = {n.name: n for n in arbol.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert not [n for n in arbol.body if isinstance(n, ast.ClassDef)], "el archivo no define clases"
        assert set(funciones) == LAS_DIEZ, (sorted(set(funciones) - LAS_DIEZ), sorted(LAS_DIEZ - set(funciones)))
        alcanzadas, pendientes = set(), ["analizar_lineas"]
        while pendientes:
            actual = pendientes.pop()
            if actual in alcanzadas:
                continue
            alcanzadas.add(actual)
            pendientes += [n.id for n in ast.walk(funciones[actual]) if isinstance(n, ast.Name) and n.id in funciones]
        assert alcanzadas == LAS_DIEZ, f"no se alcanzan desde analizar_lineas: {sorted(LAS_DIEZ - alcanzadas)}"

    def test_la_prueba_del_recorrido_discrimina(self, tmp_path):
        """Control: en un archivo sintetico con una funcion que nadie nombra, el recorrido la deja fuera."""
        arbol = ast.parse("def a():\n    return b()\n\ndef b():\n    return 1\n\ndef huerfana():\n    return 2\n")
        funciones = {n.name: n for n in arbol.body}
        alcanzadas, pendientes = set(), ["a"]
        while pendientes:
            actual = pendientes.pop()
            if actual not in alcanzadas:
                alcanzadas.add(actual)
                pendientes += [n.id for n in ast.walk(funciones[actual]) if isinstance(n, ast.Name) and n.id in funciones]
        assert alcanzadas == {"a", "b"}


# ====================================================================================================================================== 2. nadie vuelve a importar

class TestNadieVuelveAImportar:
    def test_ningun_import_ni_nombre_ni_cadena_de_produccion_nombra_lo_retirado(self, produccion_ast):
        assert usos_de_lo_retirado(produccion_ast) == []

    def test_build_exe_no_lista_el_modulo_retirado(self, produccion_ast):
        textos = [t for _, t in constantes_de_texto(produccion_ast[BUILD])]
        assert not [t for t in textos if "Analisis_PlacaCuadrada" in t or "conexiones_qt" in t], textos
        assert "analisisImagenes.Analisis_PlacaRC" in textos, "el control: el modulo que se queda sigue listado"

    def test_todo_hidden_import_de_build_exe_existe(self, produccion_ast):
        """Un hidden-import de un modulo que ya no existe: PyInstaller no se verifico (la puerta manual es el rebuild de Windows), asi que ninguno se deja huerfano."""
        lista = next(n.value for n in produccion_ast[BUILD].body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
        modulos = [e.value for e in lista.elts if isinstance(e, ast.Constant)]
        assert len(modulos) >= 20
        faltan = [m for m in modulos if not ((RAIZ / (m.replace(".", "/") + ".py")).exists() or (RAIZ / m.replace(".", "/") / "__init__.py").exists())]
        assert faltan == [], faltan

    @pytest.mark.parametrize("fuente", [
        "from analisisImagenes.Analisis_PlacaCuadrada import analizar_cuadrado2,  generar_reporte_completo\n",
        "from services.conexiones_qt import conectar_unico\n",
        "import analisisImagenes.Analisis_PlacaCuadrada as cuadrada\n",
        "from analisisImagenes import Analisis_PlacaCuadrada\n",
        "from services import conexiones_qt\n",
        "from . import conexiones_qt\n",
        "import importlib\nm = importlib.import_module('services.conexiones_qt')\n",
        "def f(x):\n    return x.analizar_cuadrado2(1)\n",
        "def generar_reporte_completo():\n    return 1\n",
        "n = getattr(obj, 'conectar_unico')\n",
        "MODULOS = ['analisisImagenes.Analisis_PlacaCuadrada']\n",
    ])
    def test_el_detector_caza_cada_forma_de_volver_a_conectar_lo_retirado(self, tmp_path, fuente):
        raiz = _escribir_arbol(tmp_path, {"pantalla.py": fuente})
        assert usos_de_lo_retirado(arboles_de(raiz)), fuente

    def test_el_detector_deja_pasar_el_codigo_que_no_lo_nombra(self, tmp_path):
        raiz = _escribir_arbol(tmp_path, {"limpia.py": '''
            """Un docstring que dice analizar_cuadrado2 y services.conexiones_qt no cuenta."""
            from analisisImagenes.Analisis_PlacaRC import analizar_lineas
            # un comentario que dice conectar_unico tampoco

            def usa():
                return analizar_lineas
        '''})
        assert usos_de_lo_retirado(arboles_de(raiz)) == []

    def test_archivos_de_produccion_poda_tests_y_venv(self, tmp_path):
        raiz = _escribir_arbol(tmp_path, {"a.py": "x = 1\n", "ui/b.py": "x = 1\n", "tests/c.py": "x = 1\n", ".venv/d.py": "x = 1\n", "build/e.py": "x = 1\n", "ui/__pycache__/f.py": "x = 1\n",
                                           "ui/tests/g.py": "x = 1\n"})
        assert archivos_de_produccion(raiz) == ["a.py", "ui/b.py", "ui/tests/g.py"]


# ====================================================================================================================================== 2b. ningun mensaje de fallo de las pruebas manda a usar lo retirado

def mensajes_que_nombran_lo_retirado(carpeta):
    """(archivo, linea, nombre) de cada MENSAJE DE FALLO (`assert cond, "mensaje"`, `pytest.fail("mensaje")`, `AssertionError("mensaje")`) de los `test_*.py` de `carpeta` que nombra uno de `NOMBRES_RETIRADOS`.
    El tripwire 2 los prohibe en produccion: un mensaje que los nombra le dice a quien lo lea que los use, y quien lo siga hace caer este archivo (G1-R2-P2: el de `test_sn2` mandaba a usar
    `conectar_unico()`). Un docstring o un comentario que cuenta la historia no cuenta; solo el texto que sale en pantalla cuando una prueba falla."""
    hallazgos = []
    for ruta in sorted(Path(carpeta).glob("test_*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        mensajes = [n.msg for n in ast.walk(arbol) if isinstance(n, ast.Assert) and n.msg is not None]
        mensajes += [a for n in ast.walk(arbol) if isinstance(n, ast.Call) and (getattr(n.func, "attr", None) == "fail" or getattr(n.func, "id", None) in ("fail", "AssertionError")) for a in n.args]
        for mensaje in mensajes:
            for h in ast.walk(mensaje):
                if isinstance(h, ast.Constant) and isinstance(h.value, str):
                    hallazgos += [(ruta.name, h.lineno, nombre) for nombre in NOMBRES_RETIRADOS if re.search(r"(?<![A-Za-z0-9_])" + re.escape(nombre) + r"(?![A-Za-z0-9_])", h.value)]
    return hallazgos


class TestNingunMensajeDeLasPruebasMandaAUsarLoRetirado:
    def test_ningun_mensaje_de_fallo_de_las_pruebas_nombra_lo_que_el_tripwire_2_prohibe(self):
        assert mensajes_que_nombran_lo_retirado(Path(__file__).resolve().parent) == []

    @pytest.mark.parametrize("fuente", [
        "def test_a(x):\n    assert x, 'sin pasar por conectar_unico() -- riesgo'\n",
        "def test_a(x):\n    assert x, ('Sitio nuevo ' 'sin pasar por conectar_unico() ahi' + 'ya')\n",
        "def test_a(x):\n    assert x, f'hace falta conectar_unico() en {x}'\n",
        "import pytest\ndef test_a():\n    pytest.fail('usa generar_reporte_completo')\n",
        "def test_a():\n    raise AssertionError('usa analizar_cuadrado2')\n",
    ])
    def test_el_detector_caza_el_mensaje_que_manda_a_usarlo(self, tmp_path, fuente):
        raiz = _escribir_arbol(tmp_path, {"test_intruso.py": fuente})
        assert mensajes_que_nombran_lo_retirado(raiz), fuente

    def test_el_detector_deja_pasar_la_historia_y_los_mensajes_que_no_lo_nombran(self, tmp_path):
        raiz = _escribir_arbol(tmp_path, {"test_limpio.py": '''
            """SN1 lo corrigio con `conectar_unico`, que G.1 retiro: un docstring cuenta la historia."""
            # un comentario que dice conectar_unico tampoco
            NOTA = "conectar_unico, como dato"

            def test_a(x):
                assert x, "conecta la senal una sola vez bajo `if not hasattr(...)`"

            def test_b(x):
                assert x, "conectar_unico_2 es otro nombre"
        '''})
        assert mensajes_que_nombran_lo_retirado(raiz) == []


# ====================================================================================================================================== 3. nadie inserta en analisis_placa_*

class TestNadieInsertaEnLasTablasViejas:
    def test_ninguna_constante_sql_ni_reemplazar_bloque_inserta_en_las_tres_tablas(self, produccion_ast):
        assert inserciones_en_las_tablas_viejas(produccion_ast) == []

    @pytest.mark.parametrize("fuente", [
        "SQL = '''INSERT INTO analisis_placa_franjas (ref, franja) VALUES (?, ?)'''\n",
        "SQL = 'INSERT OR REPLACE INTO analisis_placa_correcciones (ref) VALUES (?)'\n",
        "SQL = 'REPLACE INTO analisis_placa_verificaciones (ref) VALUES (?)'\n",
        "SQL = f'insert into analisis_placa_franjas ({columnas}) values (?)'\n",
        "def guarda(cur):\n    reemplazar_bloque(cur, 'analisis_placa_verificaciones', [('ref', 1)], '', [], 'u')\n",
        "def guarda(cur):\n    anulacion.reemplazar_bloque(cur, tabla='analisis_placa_correcciones', clave=[])\n",
        # G1-REV-P1 y P3 (revision ronda 1): SQLite no distingue mayusculas en el nombre de la tabla, y el sufijo puede llegar interpolado o armado por partes
        "SQL = 'INSERT INTO ANALISIS_PLACA_FRANJAS (ref) VALUES (?)'\n",
        "SQL = 'Replace Into Analisis_Placa_Correcciones (ref) VALUES (?)'\n",
        "SQL = f'INSERT INTO analisis_placa_{tipo} (ref) VALUES (?)'\n",
        "SQL = 'INSERT INTO analisis_placa_' + tipo + ' (ref) VALUES (?)'\n",
        "SQL = 'INSERT INTO analisis_placa_%s (ref) VALUES (?)' % tipo\n",
        "SQL = 'INSERT INTO analisis_placa_{} (ref) VALUES (?)'.format(tipo)\n",
        "def guarda(cur):\n    reemplazar_bloque(cur, 'ANALISIS_PLACA_VERIFICACIONES', [('ref', 1)], '', [], 'u')\n",
        # G1-R2-P1 (revision ronda 2): el texto SQL armado con `+` entre literales es el mismo texto, partido donde sea
        "SQL = 'INSERT INTO analisis_' + 'placa_franjas (ref) VALUES (?)'\n",
        "SQL = 'INSERT INTO ' + 'analisis_placa_correcciones' + ' (ref) VALUES (?)'\n",
    ])
    def test_el_detector_caza_cada_forma_de_insertar(self, tmp_path, fuente):
        raiz = _escribir_arbol(tmp_path, {"intruso.py": fuente})
        assert inserciones_en_las_tablas_viejas(arboles_de(raiz)), fuente

    @pytest.mark.parametrize("fuente", [
        "SQL = 'SELECT COUNT(*) FROM analisis_placa_franjas WHERE ref = ?'\n",
        "def anula(cur, tabla):\n    reemplazar_bloque(cur, tabla, [('ref', 1)], '', [], 'u')\n",
        "def anula(cur):\n    reemplazar_bloque(cur, 'indicadores_brazo', [('ref', 1)], '', [], 'u')\n",
        "SQL = 'INSERT INTO placa_mensual (ref) VALUES (?)'\n",
        "def f():\n    '''INSERT INTO analisis_placa_franjas, dicho en un docstring'''\n",
        # la tabla NUEVA de D.1 (`analisis_placa_mensual`) comparte el prefijo y no es ninguna de las tres: ni con la lista de columnas interpolada ni con su nombre en un f-string
        "SQL = 'INSERT INTO analisis_placa_mensual (ref) VALUES (?)'\n",
        "SQL = f'INSERT INTO analisis_placa_mensual ({columnas}) VALUES ({marcas})'\n",
        "SQL = f\"SELECT id FROM analisis_placa_mensual WHERE ref = ?{filtro}\"\n",
    ])
    def test_el_detector_deja_pasar_lo_que_no_inserta(self, tmp_path, fuente):
        raiz = _escribir_arbol(tmp_path, {"limpio.py": fuente})
        assert inserciones_en_las_tablas_viejas(arboles_de(raiz)) == [], fuente


# ====================================================================================================================================== 4. nadie escribe un valor nuevo en preguntas.imagen

class TestNadieEscribeUnValorNuevoEnLaImagen:
    def test_ninguna_constante_sql_ni_reemplazar_bloque_escribe_la_imagen_de_preguntas(self, produccion_ast):
        assert escrituras_de_la_imagen(produccion_ast) == []

    @pytest.mark.parametrize("fuente", [
        "SQL = 'UPDATE preguntas SET imagen = ? WHERE ref = ?'\n",
        "SQL = 'update preguntas set activo = 1, imagen = ? where ref = ?'\n",
        "SQL = 'INSERT INTO preguntas (ref, iso_mec, imagen, activo) VALUES (?, ?, ?, 1)'\n",
        "SQL = f\"INSERT INTO preguntas ({', '.join(columnas)}) VALUES ({marcas})\"\n",
        "def guarda(cur):\n    reemplazar_bloque(cur, 'preguntas', [('ref', 1)], '', [], 'u')\n",
        # G1-REV-P2 (revision ronda 1): un INSERT sin lista de columnas escribe TODAS, la imagen incluida; REPLACE INTO es INSERT OR REPLACE; el nombre puede ir entre comillas o con su base; y una lista de
        # campos dinamica en el UPDATE puede llevar `imagen` (la misma regla que la lista de columnas dinamica del INSERT)
        "SQL = 'INSERT INTO preguntas VALUES (NULL, ?, ?, 1)'\n",
        "SQL = 'insert or replace into preguntas values (?, ?)'\n",
        "SQL = 'INSERT INTO preguntas SELECT * FROM preguntas_copia'\n",
        "SQL = 'INSERT INTO preguntas VALUES (' + marcas + ')'\n",
        "SQL = 'REPLACE INTO preguntas (ref, imagen, activo) VALUES (?, ?, 1)'\n",
        "SQL = 'REPLACE INTO preguntas VALUES (?, ?)'\n",
        "SQL = 'INSERT INTO \"preguntas\" VALUES (?, ?)'\n",
        "SQL = 'INSERT INTO main.preguntas VALUES (?, ?)'\n",
        "SQL = 'UPDATE \"preguntas\" SET imagen = ? WHERE ref = ?'\n",
        "SQL = f'UPDATE preguntas SET {campos} WHERE ref = ?'\n",
        "SQL = f'UPDATE OR REPLACE preguntas SET activo = 1, {campos}'\n",
        # G1-R2-P1 (revision ronda 2): las mismas listas dinamicas armadas con `%`, `.format` o `+` (no solo en un f-string), el nombre entre comillas simples y el texto partido en dos literales
        "SQL = 'INSERT INTO preguntas (%s) VALUES (%s)' % (columnas, marcas)\n",
        "SQL = 'INSERT INTO preguntas (%(columnas)s) VALUES (?)' % {'columnas': columnas}\n",
        "SQL = 'INSERT INTO preguntas ({}) VALUES ({})'.format(columnas, marcas)\n",
        "SQL = 'INSERT INTO preguntas ({columnas}) VALUES (?)'.format(columnas=columnas)\n",
        "SQL = 'INSERT INTO preguntas (' + columnas + ') VALUES (?)'\n",
        "SQL = 'UPDATE preguntas SET %s WHERE ref = ?' % campos\n",
        "SQL = 'UPDATE preguntas SET {} WHERE ref = ?'.format(campos)\n",
        "SQL = 'UPDATE preguntas SET ' + campo + ' = ? WHERE ref = ?'\n",
        "SQL = \"INSERT INTO 'preguntas' VALUES (?, ?)\"\n",
        "SQL = \"UPDATE 'preguntas' SET imagen = ? WHERE ref = ?\"\n",
        "SQL = 'INSERT INTO pre' + 'guntas (ref, imagen) VALUES (?, ?)'\n",
        "SQL = 'UPDATE preguntas' + ' SET imagen = ? WHERE ref = ?'\n",
        "def guarda(cur, columnas):\n    cur.execute(\n        'INSERT INTO preguntas (' +\n        columnas + ') VALUES (?)')\n",
    ])
    def test_el_detector_caza_cada_forma_de_escribir_la_imagen(self, tmp_path, fuente):
        raiz = _escribir_arbol(tmp_path, {"intruso.py": fuente})
        assert escrituras_de_la_imagen(arboles_de(raiz)), fuente

    @pytest.mark.parametrize("fuente", [
        "SQL = 'SELECT imagen FROM preguntas WHERE ref = ?'\n",
        "SQL = 'UPDATE preguntas SET activo = 0 WHERE ref = ?'\n",
        "SQL = 'INSERT INTO preguntas (ref, iso_mec, activo) VALUES (?, ?, 1)'\n",
        "def anula(cur, tabla):\n    reemplazar_bloque(cur, tabla, [('ref', 1)], '', [], 'u')\n",
        "SQL = 'REPLACE INTO preguntas (ref, iso_mec, activo) VALUES (?, ?, 1)'\n",
        "SQL = 'INSERT INTO preguntas_respaldo VALUES (?, ?)'\n",
        "SQL = 'UPDATE preguntas_respaldo SET imagen = ? WHERE ref = ?'\n",
        "SQL = f'UPDATE preguntas SET activo = 0 WHERE ref IN ({marcas})'\n",
        "SQL = 'SELECT * FROM preguntas WHERE ref = ?'\n",
        # G1-R2-P1: lo dinamico que NO es la lista de columnas ni la de campos (los valores, la lista del WHERE) y las otras tablas con el mismo prefijo no se confunden
        "SQL = 'UPDATE preguntas SET activo = 0 WHERE ref IN (%s)' % marcas\n",
        "SQL = 'UPDATE preguntas SET activo = 0 WHERE ref IN ({})'.format(marcas)\n",
        "SQL = 'UPDATE preguntas SET activo = 0 WHERE ref = ' + str(ref)\n",
        "SQL = 'INSERT INTO preguntas (ref, iso_mec, activo) VALUES (' + marcas + ')'\n",
        "SQL = 'INSERT INTO preguntas (ref, activo) VALUES (%s, %s)' % (ref, 1)\n",
        "SQL = 'INSERT INTO preguntas_respaldo (%s) VALUES (%s)' % (columnas, marcas)\n",
        "SQL = 'SELECT %s FROM preguntas WHERE ref = ?' % columnas\n",
        "SQL = 'UPDATE preguntas_respaldo SET ' + campo + ' = ? WHERE ref = ?'\n",
    ])
    def test_el_detector_deja_pasar_lo_que_no_escribe_la_imagen(self, tmp_path, fuente):
        raiz = _escribir_arbol(tmp_path, {"limpio.py": fuente})
        assert escrituras_de_la_imagen(arboles_de(raiz)) == [], fuente


# ====================================================================================================================================== 5. los 18 sitios de las tablas viejas

class TestNadieLeeLosValoresDeLasTablasViejas:
    def test_los_sitios_de_produccion_son_exactamente_los_dieciocho_declarados(self, produccion_ast):
        """DA-89: las tres tablas siguen en la base, en el contrato y en la exportacion, pero nadie lee sus VALORES fuera de esta lista. Volver a poner una hermana en `tablas_relacionadas`, o una funcion
        nueva que las lea, agrega un sitio y cae; borrar un sitio de la lista que declara su motivo tambien (la lista es EXACTA, como el conteo de V de E.2 y de F.1)."""
        sitios = sitios_de_las_tablas_viejas(produccion_ast)
        assert len(SITIOS_PERMITIDOS) == 18
        assert all(SITIOS_PERMITIDOS.values()), "cada sitio con su motivo"
        nuevos = sorted(sitios - set(SITIOS_PERMITIDOS))
        faltan = sorted(set(SITIOS_PERMITIDOS) - sitios)
        assert (nuevos, faltan) == ([], []), f"sitios nuevos: {nuevos}; sitios declarados que ya no existen: {faltan}"

    def test_el_detector_caza_una_lectura_nueva_y_deja_pasar_el_resto(self, tmp_path):
        raiz = _escribir_arbol(tmp_path, {
            "intruso.py": '''
                def lee(cur):
                    return cur.execute("SELECT * FROM analisis_placa_correcciones WHERE ref = ?", (1,)).fetchall()

                class Servicio:
                    TABLAS = ["indicadores_brazo", "analisis_placa_verificaciones"]
            ''',
            "limpio.py": '''
                """Habla de analisis_placa_franjas en un docstring: no cuenta."""
                def lee(cur):
                    return cur.execute("SELECT * FROM placa_mensual WHERE ref = ?", (1,)).fetchall()
            ''',
        })
        assert sitios_de_las_tablas_viejas(arboles_de(raiz)) == {("intruso.py", "lee", "analisis_placa_correcciones"), ("intruso.py", "Servicio.<cuerpo>", "analisis_placa_verificaciones")}

    def test_el_detector_ve_el_nombre_en_mayusculas_y_el_sufijo_interpolado_y_no_confunde_la_tabla_nueva(self, tmp_path):
        """G1-REV-P1 y P3 (revision ronda 1): SQLite no distingue mayusculas (`ANALISIS_PLACA_CORRECCIONES` es la misma tabla) y el sufijo puede llegar interpolado o por partes; esos sitios cuentan, con el nombre
        normalizado a minusculas o como `analisis_placa_<dinamica>` (que ningun sitio permitido declara). `analisis_placa_mensual` (la tabla nueva de D.1) no es ninguno."""
        raiz = _escribir_arbol(tmp_path, {
            "intruso.py": '''
                def mayusculas(cur):
                    return cur.execute("SELECT * FROM ANALISIS_PLACA_CORRECCIONES WHERE ref = ?", (1,)).fetchall()

                def mezcladas(cur):
                    return cur.execute("select * from Analisis_Placa_Franjas").fetchall()

                def f_string(cur, tipo):
                    return cur.execute(f"SELECT * FROM analisis_placa_{tipo} WHERE ref = ?", (1,)).fetchall()

                def concatenada(cur, tipo):
                    return cur.execute("SELECT * FROM analisis_placa_" + tipo).fetchall()

                def con_porcentaje(cur, tipo):
                    return cur.execute("SELECT * FROM analisis_placa_%s" % tipo).fetchall()

                def con_format(cur, tipo):
                    return cur.execute("SELECT * FROM analisis_placa_{}".format(tipo)).fetchall()
            ''',
            "limpio.py": '''
                def lee(cur, filtro):
                    return cur.execute(f"SELECT id FROM analisis_placa_mensual WHERE ref = ?{filtro}", (1,)).fetchall()

                CLAVE = "analisis_placa_mensual_vigente"
            ''',
        })
        assert sitios_de_las_tablas_viejas(arboles_de(raiz)) == {
            ("intruso.py", "mayusculas", "analisis_placa_correcciones"), ("intruso.py", "mezcladas", "analisis_placa_franjas"),
            ("intruso.py", "f_string", "analisis_placa_<dinamica>"), ("intruso.py", "concatenada", "analisis_placa_<dinamica>"),
            ("intruso.py", "con_porcentaje", "analisis_placa_<dinamica>"), ("intruso.py", "con_format", "analisis_placa_<dinamica>")}

    def test_el_detector_ve_el_nombre_partido_en_dos_literales_y_no_confunde_la_tabla_nueva_partida_igual(self, tmp_path):
        """G1-R2-P1 (revision ronda 2): el texto SQL se lee entero (`unidades_de_texto`), no literal por literal: `"... FROM analisis_" + "placa_franjas"` es una lectura de la tabla vieja, y
        `"... FROM analisis_placa_" + "mensual"` (la tabla nueva de D.1, partida donde cae el prefijo) no es ningun sitio."""
        raiz = _escribir_arbol(tmp_path, {
            "intruso.py": '''
                def partida(cur):
                    return cur.execute("SELECT * FROM analisis_" + "placa_franjas WHERE ref = ?", (1,)).fetchall()
            ''',
            "limpio.py": '''
                def lee(cur):
                    return cur.execute("SELECT id FROM analisis_placa_" + "mensual WHERE ref = ?", (1,)).fetchall()
            ''',
        })
        assert sitios_de_las_tablas_viejas(arboles_de(raiz)) == {("intruso.py", "partida", "analisis_placa_franjas")}

    def test_la_lista_de_tablas_relacionadas_de_los_dos_aceleradores_ya_no_trae_las_hermanas(self):
        """G1-D2: el PDF del 600 y del iX deja de leer `analisis_placa_verificaciones` y `_correcciones` (nadie las usa desde F.1) y sigue leyendo `analisis_placa_franjas` (el conteo de V)."""
        from models.PDF.Mensuales.reportes_mensuales import ReporteMensual
        tablas = ReporteMensual().tablas_por_maquina
        for equipo in ("Clinac 600", "Clinac ix"):
            relacionadas = tablas[equipo]["tablas_relacionadas"]
            assert "analisis_placa_franjas" in relacionadas, equipo
            assert "analisis_placa_verificaciones" not in relacionadas, equipo
            assert "analisis_placa_correcciones" not in relacionadas, equipo
        assert not [t for t in tablas["Halcyon"]["tablas_relacionadas"] if t in TABLAS_VIEJAS], "el Halcyon nunca las tuvo"


# ====================================================================================================================================== sesion, base y paginas (6 y 7)

class _Sesion:
    """El objeto de sesion que el menu le pasa a la pantalla: lo unico que se le pide es `_nombre` (y `_usuario`)."""

    def __init__(self, nombre):
        self._nombre = nombre
        self._usuario = nombre.replace(" ", "").lower()


@pytest.fixture(autouse=True)
def _excepciones_de_slots(monkeypatch):
    """Trampa 3: una excepcion dentro de un slot de Qt llama a `qFatal` y aborta el proceso; con un `sys.excepthook` propio PyQt la entrega aqui y la prueba cae con el motivo a la vista."""
    capturadas = []
    monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, traza: capturadas.append(f"{tipo.__name__}: {valor}"))
    yield capturadas
    assert not capturadas, f"un slot de Qt lanzo una excepcion: {capturadas}"


@pytest.fixture
def base_nueva(app, monkeypatch, tmp_path):
    """Una BD temporal que la app crea desde cero (nunca una de referencia): la ruta se redirige ANTES de construir `Conexion()`."""
    ruta = str(tmp_path / "g1.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    for i, (usuario, nombre) in enumerate((("f1", "Fisico Uno"), ("f2", "Fisico Dos")), 1):
        con.execute("INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES (?, 'x', ?, 1, ?, 'Físico Médico', 'fisico')", (usuario, nombre, str(i)))
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = previa


def _copia_de_la_produccion(monkeypatch, tmp_path):
    """La copia de la produccion del 06-10 (TRES archivos juntos: `.db`, `-wal`, `-shm`) en `tmp_path`, con `ruta_base_datos` redirigida ANTES de construir `Conexion()`. Nunca el original."""
    original = _bd_referencia.BD_PRODUCCION_06_10
    if not original.exists():
        pytest.skip(f"HI-0: falta {original.name} en {_bd_referencia.CARPETA_BD}")
    for sufijo in ("", "-wal", "-shm"):
        origen = original.parent / (original.name + sufijo)
        if origen.exists():
            shutil.copy2(origen, tmp_path / origen.name)
    ruta = str(tmp_path / original.name)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    return ruta, Conexion(), previa


@pytest.fixture
def produccion(app, monkeypatch, tmp_path, dialogos):
    ruta, conexion, previa = _copia_de_la_produccion(monkeypatch, tmp_path)
    yield ruta
    conexion.con.close()
    Conexion._instance = previa


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


# ====================================================================================================================================== 6. la pestana «Graficos»

def _metodo(arboles, clase, nombre):
    c = next(n for n in arboles[SM].body if isinstance(n, ast.ClassDef) and n.name == clase)
    return next(n for n in c.body if isinstance(n, ast.FunctionDef) and n.name == nombre)


def conexiones_a_metodos_de_self(funcion):
    """[(linea, nombre)] de cada `X.connect(self.Y)` de una funcion: el `Y` al que se conecta."""
    salida = []
    for n in ast.walk(funcion):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "connect" and n.args:
            a = n.args[0]
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == "self":
                salida.append((n.lineno, a.attr))
    return salida


class TestLaPestanaGraficosSeQuedaSinLosBotonesOcultos:
    def test_setuptap1_ya_no_crea_ni_nombra_la_navegacion_entre_graficas(self, produccion_ast):
        funcion = _metodo(produccion_ast, "PruebaMensual600", "setupTap1")
        nombres = {n.attr for n in ast.walk(funcion) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(funcion) if isinstance(n, ast.Name)}
        assert sorted(nombres & set(NOMBRES_DE_LA_PESTANA)) == []
        textos = [t for _, t in constantes_de_texto(funcion)]
        assert "Anterior" not in textos and "Siguiente" not in textos
        assert "Eliminar" in textos and "Editar" in textos and "Aceptar" in textos and "Cancelar" in textos, "el control: la barra se queda"

    def test_ninguna_otra_funcion_de_la_clase_nombra_los_botones_ni_el_estado_de_navegacion(self, produccion_ast):
        c = next(n for n in produccion_ast[SM].body if isinstance(n, ast.ClassDef) and n.name == "PruebaMensual600")
        nombrando = sorted(f.name for f in c.body if isinstance(f, ast.FunctionDef) and {n.attr for n in ast.walk(f) if isinstance(n, ast.Attribute)} & {"boton_anterior", "boton_siguiente", "lista_graficas", "grafica_actual"})
        assert nombrando == []

    def test_cada_conexion_de_la_pestana_graficos_resuelve_en_la_mro_de_pruebamensual600(self, produccion_ast, app):
        """`graphicsWindow()` se llama sin `try` en seis pantallas: una conexion a un metodo que no existe es un `AttributeError` al construirlas."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        conexiones = []
        for nombre in ("graphicsWindow", "setupTap1"):
            conexiones += [(nombre, y) for _, y in conexiones_a_metodos_de_self(_metodo(produccion_ast, "PruebaMensual600", nombre))]
        assert len(conexiones) >= 1 and ("graphicsWindow", "closeTab") in conexiones, conexiones
        sin_resolver = [(f, y) for f, y in conexiones if not hasattr(PruebaMensual600, y)]
        assert sin_resolver == [], f"conexiones a metodos que no existen: {sin_resolver}"

    def test_el_detector_de_conexiones_caza_un_metodo_inexistente(self):
        funcion = ast.parse("def f(self):\n    self.boton.clicked.connect(self.metodo_que_no_existe)\n    self.otro.clicked.connect(lambda: 1)\n    self.x.connect(self.closeTab)\n").body[0]
        assert [y for _, y in conexiones_a_metodos_de_self(funcion)] == ["metodo_que_no_existe", "closeTab"]

    def test_el_600_mensual_real_tiene_la_pestana_con_todo_lo_que_se_queda_y_sin_los_botones(self, base_nueva, dialogos):
        """La pagina REAL del 600 con «Iniciar» pulsado (es ahi donde se construye `graphicsWindow`), sobre un control de hoy hecho por otro fisico, como las pruebas de E.2."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sql(base_nueva, "INSERT INTO controles (equipo, control, fecha, user_id, activo) VALUES ('Clinac 600', 'Mensual', ?, 'Fisico Dos', 1)", (QDate.currentDate().toString("dd/MM/yyyy"),))
        pagina = PruebaMensual600(_Sesion("Fisico Uno"), equipo_f="Clinac 600")
        try:
            pagina.date_box.setDate(QDate.currentDate())
            pagina.iniciar.click()
            assert getattr(pagina, "ref", None) is not None, "«Iniciar» no dejo el control abierto"
            assert pagina.tab_widget.tabText(0) == "Graficos"
            assert pagina.tab_widget.widget(0) is pagina.tab1
            assert isinstance(pagina.graficar, QComboBox) and pagina.tab1.isAncestorOf(pagina.graficar)
            assert pagina.tab1.isAncestorOf(pagina.canvas)
            assert isinstance(pagina.tabla, QTableWidget) and pagina.tab1.isAncestorOf(pagina.tabla)
            assert pagina.tabla.rowCount() == 1, "la tabla de controles se llena (el control sembrado)"
            propios = sorted(b.text() for b in pagina.tab1.findChildren(QPushButton) if not pagina.tabla.isAncestorOf(b))          # sin los botones «Ver tabla» de las celdas
            assert propios == ["Aceptar", "Cancelar", "Editar", "Eliminar"], propios
            assert not [b for b in pagina.findChildren(QPushButton) if b.text() in ("Anterior", "Siguiente")]
            buscar = [e for e in pagina.tab1.findChildren(QLineEdit) if e.placeholderText() == "Buscar en la tabla..."]
            assert len(buscar) == 1 and buscar[0] is pagina.search_bar
            for nombre in NOMBRES_DE_LA_PESTANA[:4]:
                assert not hasattr(pagina, nombre), nombre
        finally:
            if not sip.isdeleted(pagina):
                pagina.limpiar_recursos()
                cerrar(pagina)


SEIS_PANTALLAS = {
    "600_mensual": ("ui.paginasControles.PruebasMensuales.seiscientos_mensual", "PruebaMensual600", {"equipo_f": "Clinac 600"}),
    "ix_mensual": ("ui.paginasControles.PruebasMensuales.ix_mensual", "PruebaMensualIX", {}),
    "halcyon_mensual": ("ui.paginasControles.PruebasMensuales.halcyon_mensual", "PruebaMensualHc", {}),
    "600_anual": ("ui.paginasControles.PruebasAnuales.seiscientos_anual", "PruebaAnual600", {"equipo_f": "Clinac 600"}),
    "ix_anual": ("ui.paginasControles.PruebasAnuales.ix_anual", "PruebaAnualIX", {}),
    "halcyon_anual": ("ui.paginasControles.PruebasAnuales.halcyon_anual", "PruebaAnualHalcyon", {}),
}


class TestLasSeisPantallasQueHeredanElSetupTap1:
    """Las seis pantallas que construyen `PruebaMensual600.setupTap1` (600, iX y Halcyon, mensuales y anuales): `graphicsWindow()` se llama sin `try`, asi que una conexion a un metodo retirado, o un
    `setupTap1` que falte, seria un `AttributeError` al construir cada una. Con cada una construida e «Iniciar» pulsado (como las pruebas de E.2 y la huella del diferencial): la pestana «Graficos» tiene
    su combo, su lienzo, su tabla y la barra Eliminar/Editar/Aceptar/Cancelar/Buscar, y ningun boton «Anterior» o «Siguiente»."""

    @pytest.mark.parametrize("familia", sorted(SEIS_PANTALLAS))
    def test_la_pestana_graficos_sigue_completa_y_sin_los_botones_ocultos(self, base_nueva, dialogos, familia):
        from data.ManejoDatos.user import Usuario
        modulo, clase, kwargs = SEIS_PANTALLAS[familia]
        pagina = getattr(importlib.import_module(modulo), clase)(Usuario(username="fisicouno", fullname="Fisico Uno", active=1, role="Físico Médico"), **kwargs)
        try:
            pagina.iniciar.click()
            assert getattr(pagina, "ref", None) is not None, "«Iniciar» no dejo el control abierto"
            assert pagina.tab_widget.tabText(0) == "Graficos"
            assert isinstance(pagina.graficar, QComboBox) and pagina.tab1.isAncestorOf(pagina.graficar)
            assert pagina.tab1.isAncestorOf(pagina.canvas)
            assert isinstance(pagina.tabla, QTableWidget) and pagina.tab1.isAncestorOf(pagina.tabla)
            propios = {b.text() for b in pagina.tab1.findChildren(QPushButton) if not pagina.tabla.isAncestorOf(b)}
            assert {"Eliminar", "Editar", "Aceptar", "Cancelar"} <= propios, propios
            assert not [b for b in pagina.findChildren(QPushButton) if b.text() in ("Anterior", "Siguiente")]
            assert any(e.placeholderText() == "Buscar en la tabla..." for e in pagina.tab1.findChildren(QLineEdit))
            for nombre in NOMBRES_DE_LA_PESTANA[:4]:
                assert not hasattr(pagina, nombre), nombre
        finally:
            if not sip.isdeleted(pagina):
                pagina.limpiar_recursos()
                cerrar(pagina)


# ====================================================================================================================================== 7. «Analisis Img» queda vacia

def _texto_de_la_celda(valor):
    """El texto con que `mostrar_controles_mensuales` pinta un valor de la base (la regla de `valor_a_texto`, escrita aqui)."""
    if valor is None:
        return ""
    return f"{valor:.3f}" if isinstance(valor, float) else str(valor)


def _columnas(tabla):
    return {tabla.horizontalHeaderItem(c).text(): c for c in range(tabla.columnCount())}


def _problemas_del_item_vacio(tabla, fila, columna):
    """Lo que le falta o le sobra a la celda para ser, desde G.1b (DA-91), la de «Analisis Img»: UN item de texto vacio, sin `Qt.ItemIsEditable`, con las MISMAS banderas que las demas celdas sin tabla de origen de
    `mostrar_controles_mensuales` (un item nuevo al que solo se le quita lo editable: tambien seleccionable, que es lo que el plan pide con «igual que las demas»; `setFlags(Qt.ItemIsEnabled)` a secas no lo es), sin los
    metadatos de tabla (`Qt.UserRole + 1`, que son lo que hace que «Editar» pida la contrasena) y SIN widget. Lista vacia = la celda es la esperada. La unica definicion: la usan esta prueba y `test_g1b_analisis_img_no_editable.py`."""
    item = tabla.item(fila, columna)
    if item is None:
        return ["no tiene item (asi la dejaba G.1: «Editar» pedia la contrasena y luego decia «Celda vacia o no editable»)"]
    problemas = []
    if item.text() != "":
        problemas.append(f"el texto no es vacio: {item.text()!r}")
    if item.flags() & Qt.ItemIsEditable:
        problemas.append("el item es editable")
    elif int(item.flags()) != int(QTableWidgetItem().flags() & ~Qt.ItemIsEditable):                  # solo si no es editable: un item editable ya tiene su propio problema
        problemas.append(f"las banderas son {int(item.flags())} y las de las demas celdas sin tabla de origen son {int(QTableWidgetItem().flags() & ~Qt.ItemIsEditable)}")
    if item.data(Qt.UserRole + 1) is not None:
        problemas.append(f"trae metadatos de tabla: {item.data(Qt.UserRole + 1)!r}")
    if tabla.cellWidget(fila, columna) is not None:
        problemas.append("tiene un widget")
    return problemas


def _verificar_la_tabla(tabla, familia):
    """Lo que G1-D1 deja (con G.1b, DA-91): la columna «Analisis Img» (con su encabezado) sin widget y con UN item vacio, no editable y sin metadatos en TODAS las filas, y las demas «Ver tabla» con su boton en TODAS las filas."""
    assert tabla.rowCount() > 0, "la prueba no puede ser vacua"
    columnas = _columnas(tabla)
    assert ANALISIS_IMG in columnas, "la columna y su encabezado se quedan"
    c = columnas[ANALISIS_IMG]
    con_problemas = {f: p for f in range(tabla.rowCount()) if (p := _problemas_del_item_vacio(tabla, f, c))}
    assert con_problemas == {}, f"«{ANALISIS_IMG}» debia llevar un item vacio y no editable en cada fila: {con_problemas}"
    con_boton = {nombre for nombre, col in columnas.items() if all(tabla.cellWidget(f, col) is not None and tabla.cellWidget(f, col).findChild(QPushButton) is not None for f in range(tabla.rowCount()))}
    assert con_boton == (TAL_CUAL_HALCYON if familia == "halcyon" else TAL_CUAL_600_IX), sorted(con_boton)


def _cargar_la_tabla(equipo):
    from data.ManejoDatos.load import mostrar_controles_mensuales
    tabla = QTableWidget()
    mostrar_controles_mensuales(None, tabla, equipo_filtrar=equipo)
    return tabla


class TestAnalisisImgQuedaVacia:
    @pytest.mark.parametrize("familia", ["600", "ix", "halcyon"])
    def test_sobre_una_base_sembrada_la_celda_tiene_un_item_vacio_no_editable_y_las_demas_siguen(self, base_nueva, dialogos, familia):
        equipo = EQUIPOS[familia]
        ref = _sql(base_nueva, "INSERT INTO controles (equipo, control, fecha, user_id, activo) VALUES (?, 'Mensual', '15/03/2026', 'Fisico Uno', 1)", (equipo,))
        if familia != "halcyon":
            _sql(base_nueva, "INSERT INTO preguntas (ref, iso_mec, puntero_telem_diff, telem_rango, laser_techo, activo) VALUES (?, 1.0, '0.25', '3.5', '0.5', 1)", (ref,))
        tabla = _cargar_la_tabla(equipo)
        try:
            _verificar_la_tabla(tabla, familia)
            if familia != "halcyon":
                columnas = _columnas(tabla)
                esperado = _texto_de_la_celda(_consulta(base_nueva, "SELECT puntero_telem_diff FROM preguntas WHERE ref = ?", (ref,))[0][0])
                assert esperado != "", "la prueba sembro un valor"
                item = tabla.item(0, columnas["Dif. Punt - Tel"])
                assert item is not None and item.text() == esperado, "«Dif. Punt - Tel» sigue con su valor, editable"
                assert item.data(Qt.UserRole + 1) == ("preguntas", "puntero_telem_diff")
                assert tabla.item(0, columnas["Rango Tel."]).text() == _texto_de_la_celda(_consulta(base_nueva, "SELECT telem_rango FROM preguntas WHERE ref = ?", (ref,))[0][0])
                assert tabla.item(0, columnas["Des. Tel"]) is not None, "la ultima columna que el bucle de 10-14 escribe se queda"
                assert tabla.item(0, columnas["Lás. Techo"]).text() == _texto_de_la_celda(_consulta(base_nueva, "SELECT laser_techo FROM preguntas WHERE ref = ?", (ref,))[0][0])
            else:
                assert tabla.item(0, _columnas(tabla)["Imagen"]) is not None, "la columna «Imagen» de al lado se queda"
        finally:
            cerrar(tabla)

    @pytest.mark.parametrize("familia", ["600", "ix", "halcyon"])
    def test_sobre_la_copia_de_la_produccion_del_06_10_ninguna_fila_tiene_nada_en_la_celda_salvo_su_item_vacio(self, produccion, familia):
        equipo = EQUIPOS[familia]
        esperadas = _consulta(produccion, "SELECT COUNT(*) FROM controles WHERE equipo = ? AND control = 'Mensual' AND (activo IS NULL OR activo = 1)", (equipo,))[0][0]
        tabla = _cargar_la_tabla(equipo)
        try:
            assert tabla.rowCount() == esperadas > 0, (tabla.rowCount(), esperadas)
            _verificar_la_tabla(tabla, familia)
            if familia != "halcyon":
                columnas = _columnas(tabla)
                for fila in range(tabla.rowCount()):
                    ref = tabla.item(fila, 0).data(Qt.UserRole)
                    vigentes = _consulta(produccion, "SELECT puntero_telem_diff FROM preguntas WHERE ref = ? AND (activo IS NULL OR activo = 1)", (ref,))
                    esperado = _texto_de_la_celda(vigentes[0][0]) if vigentes else ""
                    assert tabla.item(fila, columnas["Dif. Punt - Tel"]).text() == esperado, (ref, esperado)
        finally:
            cerrar(tabla)


# ====================================================================================================================================== 8. el PDF dice lo mismo

class TestElPdfDiceLoMismo:
    @pytest.mark.parametrize("datos", [
        {"preguntas": []},
        {"preguntas": [], "analisis_placa_franjas": []},
        {"preguntas": [{"isocentro": "Funciona", "imagen": None}], "analisis_placa_franjas": []},
        {"analisis_placa_franjas": [], "analisis_placa_verificaciones": [{"x": 1}], "analisis_placa_correcciones": [{"x": 1}]},
    ])
    def test_8a_sin_n_y_sin_v_la_seccion_es_el_dataframe_de_no_hay_datos_de_analisis_de_imagen(self, datos):
        """Igual a HEAD (donde lo daba `_crear_tabla_analisis_imagen`): una fila, columna «Información». Las dos hermanas llenas NO cuentan (F1-M19: V sale solo de franjas)."""
        from models.PDF.Mensuales.reportes_mensuales import _secciones_de_la_placa
        secciones = _secciones_de_la_placa(dict(datos))
        pd.testing.assert_frame_equal(secciones["analisis_imagen"], pd.DataFrame([["No hay datos de análisis de imagen"]], columns=["Información"]))
        assert "imagen" in secciones

    def test_8a_con_v_sin_n_es_la_linea_de_la_herramienta_anterior(self):
        """El control de la rama de al lado: con franjas vigentes y sin analisis nuevo, la linea de DA-89 (F.1), tal cual."""
        from models.PDF.Mensuales.reportes_mensuales import _secciones_de_la_placa
        from models.PDF.Mensuales.seccion_placa_mensual import LINEA_SIN_ANALISIS_NUEVO
        secciones = _secciones_de_la_placa({"preguntas": [], "analisis_placa_franjas": [{"franja": 1}]})
        pd.testing.assert_frame_equal(secciones["analisis_imagen"], pd.DataFrame([[LINEA_SIN_ANALISIS_NUEVO]], columns=["Información"]))

    def test_8b_el_pdf_del_600_y_del_ix_lee_las_franjas_y_no_las_dos_hermanas(self):
        from models.PDF.Mensuales.reportes_mensuales import ReporteMensual
        tablas = ReporteMensual().tablas_por_maquina
        for equipo in ("Clinac 600", "Clinac ix"):
            relacionadas = tablas[equipo]["tablas_relacionadas"]
            assert [t for t in relacionadas if t in TABLAS_VIEJAS] == ["analisis_placa_franjas"], (equipo, relacionadas)

    def test_la_nota_de_la_convencion_de_ejes_y_la_tabla_vieja_salieron_del_modulo(self, produccion_ast):
        nombres = {n.id for n in ast.walk(produccion_ast[RM]) if isinstance(n, ast.Name)} | {n.name for n in ast.walk(produccion_ast[RM]) if isinstance(n, ast.FunctionDef)}
        assert not nombres & {"ENCABEZADO_ANALISIS_IMAGEN", "_crear_tabla_analisis_imagen"}, nombres & {"ENCABEZADO_ANALISIS_IMAGEN", "_crear_tabla_analisis_imagen"}


# ====================================================================================================================================== el control del recorte: el diario de braquiterapia sigue analizando

DPI_DE_LA_PLACA = 600
MM_POR_PIXEL = 25.4 / DPI_DE_LA_PLACA
CENTROS_DE_LAS_LINEAS = (100, 230, 360, 490, 620)                 # en pixeles: cinco lineas oscuras de 5 px de ancho, separadas 130 px


class TestElDiarioDeBraquiSigueAnalizandoTrasElRecorte:
    """`analizar_lineas` (y las 9 funciones que alcanza) es lo que el diario de braquiterapia usa y G.1 NO toca; si el recorte de `Analisis_PlacaRC.py` se llevara de mas una de las 10 (por ejemplo
    `detectar_picos`), el diario dejaria de analizar. La verdad conocida la fija un GENERADOR independiente del motor: cinco lineas oscuras a 130 px, a 600 ppp, son 4 distancias de 130 x 25.4 / 600 =
    5.503 mm (la placa real de las pruebas de B.2 es otra cosa: aqui se prueba que la funcion CORRE y mide)."""

    @pytest.fixture
    def placa(self, tmp_path):
        import numpy as np
        from PIL import Image
        imagen = np.full((120, 700), 235, dtype=np.uint8)
        for x in CENTROS_DE_LAS_LINEAS:
            imagen[:, x - 2:x + 3] = 25
        ruta = tmp_path / "lineas.png"
        Image.fromarray(imagen).save(ruta, dpi=(DPI_DE_LA_PLACA, DPI_DE_LA_PLACA))
        return str(ruta)

    @staticmethod
    def _distancias(informe):
        m = re.search(r"Distancias entre líneas\(mm\):</b> <span style='font-weight:normal'>\[([^\]]*)\]", informe)
        assert m, informe
        return [float(x) for x in m.group(1).split(",")]

    def test_analizar_lineas_mide_las_distancias_conocidas(self, placa):
        from analisisImagenes.Analisis_PlacaRC import analizar_lineas
        informe = analizar_lineas(placa, metodo=True, umbral_relativo=1.0, distancia_minima=30, mostrar=False, filtro="clahe")
        distancias = self._distancias(informe)
        verdad = 130 * MM_POR_PIXEL
        assert len(distancias) == len(CENTROS_DE_LAS_LINEAS) - 1
        assert all(abs(d - verdad) < 0.05 for d in distancias), (distancias, verdad)
        assert f"{verdad:.2f} mm" in informe, "el promedio"

    def test_con_el_lienzo_dibuja_los_tres_ejes_y_da_el_mismo_informe(self, placa):
        """El camino de la pagina real (`mostrar=True` con su lienzo): `graficar_resultados` y los perfiles, y el informe es el mismo que sin dibujar."""
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from analisisImagenes.Analisis_PlacaRC import analizar_lineas
        sin = analizar_lineas(placa, metodo=True, umbral_relativo=1.0, distancia_minima=30, mostrar=False, filtro="clahe")
        lienzo = FigureCanvasAgg(Figure())
        con = analizar_lineas(placa, metodo=True, umbral_relativo=1.0, distancia_minima=30, mostrar=True, filtro="clahe", canvas=lienzo)
        assert con == sin
        assert len(lienzo.figure.axes) == 3

    def test_las_diez_funciones_se_alcanzan_en_una_corrida_real(self, placa, monkeypatch):
        """Una corrida real con el lienzo pasa por las funciones del camino (espiadas): sin `detectar_picos`, `obtener_perfil`, `preprocesar_imagen`, `calcular_distancias`, `metadata`,
        `analizar_circulos_perfil`, `generar_reporte` o `graficar_resultados` el diario no analiza. (`_get_mpl` lo llama `graficar_resultados` por dentro del modulo y no por el nombre espiado.)"""
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        import analisisImagenes.Analisis_PlacaRC as rc
        llamadas = set()
        for nombre in sorted(LAS_DIEZ - {"analizar_lineas"}):
            original = getattr(rc, nombre)

            def espia(*a, _n=nombre, _o=original, **k):
                llamadas.add(_n)
                return _o(*a, **k)
            monkeypatch.setattr(rc, nombre, espia)
        rc.analizar_lineas(placa, metodo=True, umbral_relativo=1.0, distancia_minima=30, mostrar=True, filtro="clahe", canvas=FigureCanvasAgg(Figure()))
        assert {"detectar_picos", "obtener_perfil", "preprocesar_imagen", "calcular_distancias", "metadata", "analizar_circulos_perfil", "generar_reporte", "graficar_resultados"} <= llamadas, sorted(llamadas)


# ====================================================================================================================================== 9. ninguna pantalla llega a un analizar_imagen de seiscientos_mensual.py

class TestNingunaPantallaLlegaAUnAnalizarImagenDeSeiscientosMensual:
    def test_el_archivo_no_define_ningun_analizar_imagen(self, produccion_ast):
        definidos = [(c.name, f.lineno) for c in ast.walk(produccion_ast[SM]) if isinstance(c, ast.ClassDef) for f in c.body if isinstance(f, ast.FunctionDef) and f.name == "analizar_imagen"]
        definidos += [("<modulo>", f.lineno) for f in produccion_ast[SM].body if isinstance(f, ast.FunctionDef) and f.name == "analizar_imagen"]
        assert definidos == [], f"seiscientos_mensual.py todavia define analizar_imagen: {definidos}"

    def test_solo_braqui_diario_y_el_anual_del_halcyon_construyen_el_cargador_con_analisis_y_los_dos_resuelven_el_suyo(self, la_ui):
        assert not la_ui.fallidos, la_ui.fallidos
        arboles, con_analisis = {}, {}
        for clase in la_ui.clases:
            sitios = _sitios_del_cargador(clase, la_ui.cargador, arboles)
            if any(analisis for *_, analisis in sitios):
                con_analisis[f"{clase.__module__}.{clase.__qualname__}"] = (clase, {Path(archivo).name for _, archivo, _, analisis in sitios if analisis})
        archivos_que_construyen = set().union(*(a for _, a in con_analisis.values()))
        assert archivos_que_construyen == {"braquiterapia.py", "halcyon_anual.py"}, archivos_que_construyen
        assert {c.split(".")[-1] for c in con_analisis} >= {"PruebaDiariaBraq", "PruebaAnualHalcyon"}, sorted(con_analisis)
        for nombre, (clase, _) in sorted(con_analisis.items()):
            propio = next((b.__dict__["analizar_imagen"] for b in clase.__mro__ if "analizar_imagen" in b.__dict__), None)
            assert propio is not None, f"{nombre} construye el cargador con analisis y no resuelve ningun analizar_imagen"
            assert not la_ui.es_viejo(propio), f"{nombre} resuelve el analizar_imagen de seiscientos_mensual.py"
            assert Path(propio.__code__.co_filename).name in ("braquiterapia.py", "halcyon_anual.py"), (nombre, propio.__code__.co_filename)

    def test_ninguna_clase_de_la_ui_con_el_cargador_en_analisis_verdadero_resuelve_el_analisis_de_seiscientos_mensual(self, la_ui):
        assert len(la_ui.importados) >= 25
        assert _clases_que_violan(la_ui.clases, la_ui.cargador, _es_el_analisis_viejo) == []

    def test_el_detector_por_archivo_caza_un_analizar_imagen_vuelto_a_definir_en_ese_archivo(self, tmp_path):
        """Control: una funcion cuyo archivo se llama `seiscientos_mensual.py` es «la vieja»; una de otro archivo, no; `None` (nadie la define), tampoco."""
        carpeta = tmp_path / "viejo"
        carpeta.mkdir()
        (carpeta / "seiscientos_mensual.py").write_text("def analizar_imagen(self):\n    return 1\n", encoding="utf-8")
        (tmp_path / "otro.py").write_text("def analizar_imagen(self):\n    return 1\n", encoding="utf-8")
        modulos = []
        for nombre, ruta in (("viejo_g1", carpeta / "seiscientos_mensual.py"), ("otro_g1", tmp_path / "otro.py")):
            spec = importlib.util.spec_from_file_location(nombre, ruta)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
            modulos.append(modulo)
        assert _es_el_analisis_viejo(modulos[0].analizar_imagen) is True
        assert _es_el_analisis_viejo(modulos[1].analizar_imagen) is False
        assert _es_el_analisis_viejo(None) is False
