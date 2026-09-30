"""RC.3 (PLAN_RECALCULO_CALIBRACION_BRAQUI_30-09.md): tres guardas para que la
reparación de RC.1/RC.2 no se vuelva a desviar.

CAUSA. El recálculo de la calibración se desvió porque nada impedía una
segunda implementación de la cuenta (la historia de `V.2`). Además, qué es
editable (`col_mapeo` de `load.py::mostrar_db_mensualBraqui`) y qué se
recalcula (`load.py::corregir_calibracion`) se deciden en sitios distintos que
nadie comparaba: mañana una entrada `("SistemaMedicion", "calibracion")` en
`col_mapeo` corregiría el factor de la cámara sin recalcular la actividad, y
`("TipoCalibracion", "fecha")` rompería la lectura por fecha (DP-44).

Nada aquí lista celdas ni columnas a mano: todo se deriva del productor -- el
esquema real de una BD recién creada, el SQL real de `consulta_mesualBraq`
(por AST) y la vista real sobre una copia de `Rebuild_21-09`.

  Guarda 1. Fuera de `analisisImagenes/ActividadFuente.py`, ninguna función de
            producción llama a `factores_correccion` ni a `actividad_fuente`:
            la cuenta de lo archivado vive solo en `resultados_para_archivar`,
            y la vista previa (`CalcularActividad`) en el mismo módulo.
  Guarda 2. Toda columna de `TipoCalibracion` del esquema real tiene
            EXACTAMENTE una política de corrección
            (`services/correccion_calibracion.py`), y lo que
            `consulta_mesualBraq` lee coincide con esa clasificación.
  Guarda 3. Toda celda editable de la vista del mensual y de la redundante
            declara su tabla (tupla) y no apunta a una entrada del cálculo de
            otra tabla, a un resultado archivado ni a una columna que no se
            corrige en sitio.

Rojo real (árbol sin RC.1/RC.2): la guarda 1 nombra `braq_mensual.py::
guardar_DB` y `load.py::guardarEdicion`; las guardas 2 y 3 fallan por
`ImportError` del módulo de clasificación. Por eso ese módulo se importa
DENTRO de cada prueba y no arriba: cada guarda debe poder fallar por su
cuenta, con su propio mensaje.

Cada detector es una función pura con su prueba de discriminación (una
intrusa sintética que DEBE detectar): una guarda que nunca se ha visto fallar
no demuestra nada.
"""
import ast
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

sys.path.insert(0, os.path.dirname(__file__))

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import mostrar_db_mensualBraqui
from _bd_referencia import BD_REBUILD_21_09

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

ARCHIVO_DE_LA_CUENTA = "analisisImagenes/ActividadFuente.py"
CUENTA_DE_BAJO_NIVEL = {"factores_correccion", "actividad_fuente"}
ARCHIVO_DE_LA_CORRECCION = "data/ManejoDatos/load.py"
FUNCION_PRODUCTORA = "consulta_mesualBraq"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _reset_qtsql_default_connection():
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


@pytest.fixture(autouse=True)
def _limpiar_conexion_tras_cada_test():
    yield
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None
    _reset_qtsql_default_connection()


def _clasificacion():
    """Importación dentro de cada prueba: sin RC.2 este módulo no existe, y
    cada guarda debe poder fallar por su cuenta (la guarda 1 no lo necesita)."""
    import services.correccion_calibracion as cc
    return cc


# ===========================================================================
# Guarda 1 -- la cuenta de lo archivado vive en UN solo sitio
# ===========================================================================

def _archivos_de_produccion(raiz):
    for path in sorted(raiz.rglob("*.py")):
        rel = path.relative_to(raiz)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel.as_posix(), path


def _fuentes_de_produccion(incluir_la_definicion=False):
    """(archivo_relativo, texto) de cada archivo de producción. Por omisión
    sin el módulo que DEFINE la cuenta (es el único sitio donde se permite)."""
    for rel, path in _archivos_de_produccion(ROOT):
        if rel == ARCHIVO_DE_LA_CUENTA and not incluir_la_definicion:
            continue
        try:
            yield rel, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def _nombre_de_la_llamada(nodo):
    objetivo = nodo.func
    return getattr(objetivo, "id", None) or getattr(objetivo, "attr", None)


def _funcion_que_envuelve(arbol, nodo_objetivo):
    """Nombre de la función más interna que contiene `nodo_objetivo`, o None
    si está a nivel de módulo."""
    mejor = None
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if nodo.lineno <= nodo_objetivo.lineno <= getattr(nodo, "end_lineno", nodo.lineno):
                if any(sub is nodo_objetivo for sub in ast.walk(nodo)):
                    mejor = nodo.name
    return mejor


def _llamadas_a_la_cuenta(fuentes):
    """[(archivo, funcion_envolvente, llamada, linea)] de cada llamada a
    `factores_correccion`/`actividad_fuente` en `fuentes` (iterable de
    (archivo_relativo, texto_del_fuente)). Por AST: no le afectan
    comentarios, docstrings ni cadenas que solo nombren las funciones."""
    encontradas = []
    for rel, texto in fuentes:
        try:
            arbol = ast.parse(texto)
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and _nombre_de_la_llamada(nodo) in CUENTA_DE_BAJO_NIVEL:
                encontradas.append((rel, _funcion_que_envuelve(arbol, nodo),
                                    _nombre_de_la_llamada(nodo), nodo.lineno))
    return encontradas


def test_ninguna_funcion_de_produccion_repite_la_cuenta_de_lo_archivado():
    sospechosas = _llamadas_a_la_cuenta(_fuentes_de_produccion())
    assert not sospechosas, (
        "La cuenta de lo archivado (Ks, Kp, Ktp y las dos actividades) vive "
        "SOLO en `resultados_para_archivar`, y su vista previa "
        "(`CalcularActividad`) en el mismo módulo. Estas llamadas directas a "
        "`factores_correccion`/`actividad_fuente` son una segunda copia de "
        "esa cuenta -- la historia de V.2: usen `resultados_para_archivar`:\n" +
        "\n".join(f"  {archivo}::{funcion} -- {llamada} (línea {linea})"
                  for archivo, funcion, llamada, linea in sospechosas))


def test_el_censo_de_la_cuenta_no_mide_el_vacio():
    """Compuerta: el recorrido ve los archivos que importan, y el detector SÍ
    ve las llamadas reales cuando se le da el módulo que las define -- así
    `sospechosas == []` significa "nadie más la repite", no "no miré"."""
    vistos = {rel for rel, _ in _fuentes_de_produccion()}
    assert {"ui/paginasControles/PruebasMensuales/braq_mensual.py",
            ARCHIVO_DE_LA_CORRECCION} <= vistos
    assert ARCHIVO_DE_LA_CUENTA not in vistos

    propias = _llamadas_a_la_cuenta(_fuentes_de_produccion(incluir_la_definicion=True))
    donde = {(funcion, llamada) for archivo, funcion, llamada, _ in propias
             if archivo == ARCHIVO_DE_LA_CUENTA}
    assert {("resultados_para_archivar", "factores_correccion"),
            ("resultados_para_archivar", "actividad_fuente")} <= donde, (
        "la cuenta de lo archivado ya no vive en `resultados_para_archivar`: "
        f"el detector solo vio {sorted(donde)}")


def test_el_detector_de_la_cuenta_ve_una_llamada_suelta_y_nombra_su_funcion():
    fuente = (
        "def guardar_otra_vez():\n"
        "    Ks, Kp, Ktp = factores_correccion(1, 2, 3, 4, 5, 6, 7)\n"
        "    return actividad_fuente(Ks, Kp, Ktp, 1, 1, 1, 1)\n"
    )
    hallazgos = _llamadas_a_la_cuenta([("ui/falso.py", fuente)])
    assert [(a, f, n) for a, f, n, _ in hallazgos] == [
        ("ui/falso.py", "guardar_otra_vez", "factores_correccion"),
        ("ui/falso.py", "guardar_otra_vez", "actividad_fuente"),
    ]


def test_el_detector_de_la_cuenta_ve_la_llamada_por_atributo_y_a_nivel_de_modulo():
    fuente = "import ActividadFuente as af\nKs = af.factores_correccion(1)\n"
    hallazgos = _llamadas_a_la_cuenta([("scripts/falso.py", fuente)])
    assert [(a, f, n) for a, f, n, _ in hallazgos] == [
        ("scripts/falso.py", None, "factores_correccion")]


def test_el_detector_de_la_cuenta_no_marca_lo_permitido():
    """Las dos puertas legítimas (`resultados_para_archivar`, la vista
    previa `CalcularActividad`) y las menciones en texto no son una segunda
    copia de la cuenta."""
    fuente = (
        '"""Antes se llamaba factores_correccion(...) y actividad_fuente(...) aquí."""\n'
        "def guardar():\n"
        "    # no llamar a actividad_fuente(...) directamente\n"
        "    mensaje = 'factores_correccion(x)'\n"
        "    previa = CalcularActividad(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)\n"
        "    return resultados_para_archivar(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, v_alto=300, v_bajo=50)\n"
    )
    assert _llamadas_a_la_cuenta([("ui/ok.py", fuente)]) == []


# ===========================================================================
# Guarda 2 -- cada columna de TipoCalibracion tiene UNA política de corrección
# ===========================================================================

def _politicas(cc):
    """Las tres políticas de `TipoCalibracion` como conjuntos NUEVOS: una
    prueba puede mutarlos sin tocar las constantes del módulo."""
    return {
        "recalcula": set(cc.COLUMNAS_QUE_RECALCULAN),
        "sin efecto en el cálculo": set(cc.COLUMNAS_SIN_EFECTO_EN_EL_CALCULO),
        "no se corrige en sitio": set(cc.COLUMNAS_QUE_NO_SE_CORRIGEN_EN_SITIO),
    }


def _problemas_de_clasificacion(columnas_reales, politicas):
    """Textos de lo que impide que cada columna real tenga EXACTAMENTE una
    política: repetidas, sin política o políticas de columnas que ya no
    existen. Vacía si todo cuadra."""
    problemas = []
    nombres = list(politicas)
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            comunes = politicas[a] & politicas[b]
            if comunes:
                problemas.append(
                    f"columnas en dos políticas a la vez ({a} y {b}): {sorted(comunes)}")
    clasificadas = set().union(*politicas.values())
    sin_politica = set(columnas_reales) - clasificadas
    if sin_politica:
        problemas.append(
            f"columnas de TipoCalibracion sin política de corrección: {sorted(sin_politica)}")
    inexistentes = clasificadas - set(columnas_reales)
    if inexistentes:
        problemas.append(
            f"políticas para columnas que TipoCalibracion ya no tiene: {sorted(inexistentes)}")
    return problemas


@pytest.fixture
def conexion_nueva(monkeypatch, tmp_path):
    """Una BD RECIÉN creada por `Conexion()` en un temporal: el esquema real
    tal como lo deja el código de producción, sin copiar ninguna BD de
    referencia. `ruta_base_datos` se apunta al temporal ANTES de conectar
    (si no, se crearía `Codigo_radqa/BaseDatosQA.db`, el incidente de DP-117)."""
    ruta = tmp_path / "nueva.db"
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(ruta))
    conection_mod.Conexion._instance = None
    return Conexion()


def _columnas_de(conexion, tabla):
    return [fila[1] for fila in conexion.con.execute(f"PRAGMA table_info({tabla})")]


def test_toda_columna_de_tipocalibracion_tiene_exactamente_una_politica(app, conexion_nueva):
    cc = _clasificacion()
    columnas = _columnas_de(conexion_nueva, "TipoCalibracion")
    assert {"id", "fecha", "tipo", "conversion", "intensidad", "fecha_cer"} <= set(columnas), (
        f"compuerta: la BD recién creada no trae el esquema esperado: {columnas}")
    problemas = _problemas_de_clasificacion(columnas, _politicas(cc))
    assert not problemas, (
        "la clasificación de `services/correccion_calibracion.py` no cubre "
        "TipoCalibracion tal como la crea el código:\n  " + "\n  ".join(problemas))


def test_una_columna_nueva_de_tipocalibracion_sin_clasificar_se_nombra(app, conexion_nueva):
    """Discriminación con el mecanismo real: `ALTER TABLE ... ADD COLUMN`
    sobre el temporal, como haría la próxima migración."""
    cc = _clasificacion()
    conexion_nueva.con.execute("ALTER TABLE TipoCalibracion ADD COLUMN columna_nueva_x TEXT")
    columnas = _columnas_de(conexion_nueva, "TipoCalibracion")
    problemas = _problemas_de_clasificacion(columnas, _politicas(cc))
    assert any("columna_nueva_x" in p and "sin política" in p for p in problemas), problemas


def test_el_detector_de_politicas_nombra_la_columna_sin_politica_la_repetida_y_la_fantasma(app):
    cc = _clasificacion()
    reales = sorted(set().union(*_politicas(cc).values()))

    politicas = _politicas(cc)
    politicas["sin efecto en el cálculo"].discard("serie")
    problemas = _problemas_de_clasificacion(reales, politicas)
    assert any("serie" in p and "sin política" in p for p in problemas), problemas

    politicas = _politicas(cc)
    politicas["recalcula"].add("fecha")
    problemas = _problemas_de_clasificacion(reales, politicas)
    assert any("fecha" in p and "dos políticas" in p for p in problemas), problemas

    politicas = _politicas(cc)
    politicas["sin efecto en el cálculo"].add("columna_retirada")
    problemas = _problemas_de_clasificacion(reales, politicas)
    assert any("columna_retirada" in p and "ya no tiene" in p for p in problemas), problemas


# --- lo que la corrección LEE, derivado del productor (por AST) -------------

_SELECT = re.compile(r"\bSELECT\s+(?P<columnas>.+?)\s+FROM\s+(?P<tabla>\w+)", re.S | re.I)


def _texto_de_la_cadena(nodo):
    """Texto estático de una constante o f-string; cada `{expresión}` queda
    como un hueco. None si no es una cadena que se pueda leer."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        return "".join(p.value if isinstance(p, ast.Constant) else "{}" for p in nodo.values)
    return None


def _selects_de_la_funcion(texto_del_fuente, nombre_de_la_funcion):
    """({tabla: {columnas}}, [líneas con SQL que no se pudo leer]) de los
    `execute(...)` de UNA función, leídos de sus cadenas por AST."""
    arbol = ast.parse(texto_del_fuente)
    funciones = [n for n in ast.walk(arbol)
                 if isinstance(n, ast.FunctionDef) and n.name == nombre_de_la_funcion]
    assert len(funciones) == 1, (
        f"se esperaba exactamente una definición de {nombre_de_la_funcion}, "
        f"hay {len(funciones)}")
    selects, opacas = {}, []
    for nodo in ast.walk(funciones[0]):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "execute" and nodo.args):
            continue
        texto = _texto_de_la_cadena(nodo.args[0])
        if texto is None:
            opacas.append(nodo.lineno)
            continue
        m = _SELECT.search(texto)
        if m:
            columnas = {c.strip() for c in m.group("columnas").split(",")}
            selects.setdefault(m.group("tabla"), set()).update(columnas)
    return selects, opacas


def _desvios_del_productor(selects, cc):
    """Textos de lo que `consulta_mesualBraq` lee y la clasificación no dice
    igual. Vacía si las constantes describen exactamente lo que se lee."""
    desvios = []
    esperadas = {tabla: set(cols) for tabla, cols in cc.ENTRADAS_DE_OTRAS_TABLAS.items()}
    esperadas["ResultadosActividad"] = set(cc.RESULTADOS_ARCHIVADOS)
    for tabla, declaradas in esperadas.items():
        leidas = selects.get(tabla, set())
        if leidas != declaradas:
            desvios.append(
                f"{tabla}: la corrección lee {sorted(leidas)} y la clasificación "
                f"declara {sorted(declaradas)}")
    propias = selects.get("TipoCalibracion", set())
    sin_leer = set(cc.COLUMNAS_QUE_RECALCULAN) - propias
    if sin_leer:
        desvios.append(
            "TipoCalibracion: columnas que recalculan y la corrección no lee "
            f"(su cambio nunca se detectaría): {sorted(sin_leer)}")
    clasificadas = set().union(*_politicas(cc).values())
    sin_politica = propias - clasificadas
    if sin_politica:
        desvios.append(
            f"TipoCalibracion: columnas que la corrección lee y no tienen política: "
            f"{sorted(sin_politica)}")
    desconocidas = set(selects) - set(esperadas) - {"TipoCalibracion"}
    if desconocidas:
        desvios.append(f"tablas que la corrección lee y la clasificación no conoce: {sorted(desconocidas)}")
    return desvios


def test_lo_que_consulta_mesualbraq_lee_coincide_con_la_clasificacion(app):
    cc = _clasificacion()
    texto = (ROOT / ARCHIVO_DE_LA_CORRECCION).read_text(encoding="utf-8")
    selects, opacas = _selects_de_la_funcion(texto, FUNCION_PRODUCTORA)
    assert not opacas, (
        f"{FUNCION_PRODUCTORA} ejecuta SQL que esta guarda no puede leer "
        f"(líneas {opacas}): una lectura nueva escapa a la clasificación")
    desvios = _desvios_del_productor(selects, cc)
    assert not desvios, (
        "las constantes de `services/correccion_calibracion.py` ya no describen "
        f"lo que {FUNCION_PRODUCTORA} lee de verdad:\n  " + "\n  ".join(desvios))


_FUENTE_SINTETICA = '''
def consulta_mesualBraq(self, id):
    cursor.execute(f"""
        SELECT t, p, h
        FROM CondicionesMedicion
        WHERE ref = ?{filtro_activo('CondicionesMedicion')}
    """, (id,))
    cursor.execute("SELECT t0, p0 FROM SistemaMedicion WHERE ref = ?", (id,))
    cursor.execute("SELECT conversion FROM TipoCalibracion WHERE id = ?", (id,))
    cursor.execute("SELECT x FROM TablaNueva WHERE ref = ?", (id,))
    cursor.execute(consulta_en_una_variable, (id,))
'''


def test_el_lector_del_productor_ve_una_lectura_de_mas_una_de_menos_y_el_sql_opaco(app):
    cc = _clasificacion()
    selects, opacas = _selects_de_la_funcion(_FUENTE_SINTETICA, FUNCION_PRODUCTORA)
    assert selects["CondicionesMedicion"] == {"t", "p", "h"}
    assert selects["SistemaMedicion"] == {"t0", "p0"}
    assert opacas, "el SQL que sale de una variable debe quedar registrado como opaco"
    desvios = _desvios_del_productor(selects, cc)
    texto = " | ".join(desvios)
    assert "'h'" in texto, f"no nombra la columna de más: {desvios}"
    assert "calibracion" in texto and "electrometro" in texto, f"no nombra lo que falta: {desvios}"
    assert "TablaNueva" in texto, f"no nombra la tabla desconocida: {desvios}"
    assert "ResultadosActividad" in texto, f"no nombra la tabla que dejó de leerse: {desvios}"
    assert "fecha_cer" in texto and "intensidad" in texto, (
        f"no nombra las columnas que recalculan y nadie lee: {desvios}")


# ===========================================================================
# Guarda 3 -- ninguna celda editable es entrada del cálculo sin su recálculo
# ===========================================================================

def _problemas_de_las_celdas(table, cc):
    """Textos de cada celda con metadata de edición (`Qt.UserRole + 1`) que
    no declara su tabla, o que apunta a una entrada del cálculo de otra tabla,
    a un resultado archivado o a una columna de TipoCalibracion que no se
    corrige en sitio o no está clasificada."""
    problemas = []
    for r in range(table.rowCount()):
        for c in range(table.columnCount()):
            item = table.item(r, c)
            if item is None:
                continue
            meta = item.data(Qt.UserRole + 1)
            if meta is None:
                continue
            cabecera = table.horizontalHeaderItem(c)
            donde = f"fila {r}, columna {c} ({cabecera.text() if cabecera else 's/n'})"
            if not (isinstance(meta, tuple) and len(meta) == 2):
                problemas.append(
                    f"{donde}: la metadata {meta!r} no declara (tabla, columna) -- "
                    "`guardarEdicion` la mandaría a la tabla del nombre que pase la vista")
                continue
            tabla, columna = meta
            if columna in cc.ENTRADAS_DE_OTRAS_TABLAS.get(tabla, ()):
                problemas.append(
                    f"{donde}: {tabla}.{columna} es una entrada del cálculo de la "
                    "actividad; editarla sin recalcular deja Ks/Kp/Ktp/actividad desfasados")
            if tabla == "ResultadosActividad" and columna in cc.RESULTADOS_ARCHIVADOS:
                problemas.append(
                    f"{donde}: {tabla}.{columna} es un resultado archivado; se recalcula, "
                    "no se escribe a mano")
            if tabla == "TipoCalibracion":
                if columna in cc.COLUMNAS_QUE_NO_SE_CORRIGEN_EN_SITIO:
                    problemas.append(
                        f"{donde}: TipoCalibracion.{columna} no se corrige en sitio: "
                        f"{cc.COLUMNAS_QUE_NO_SE_CORRIGEN_EN_SITIO[columna]}")
                elif (columna not in cc.COLUMNAS_QUE_RECALCULAN
                      and columna not in cc.COLUMNAS_SIN_EFECTO_EN_EL_CALCULO):
                    problemas.append(
                        f"{donde}: TipoCalibracion.{columna} no tiene política de corrección "
                        "(sin política)")
    return problemas


def _celdas_con_metadata(table):
    return [(r, c) for r in range(table.rowCount()) for c in range(table.columnCount())
            if table.item(r, c) is not None and table.item(r, c).data(Qt.UserRole + 1) is not None]


class _PantallaFalsa:
    """Lo único que `mostrar_db_mensualBraqui` necesita de `self`: una
    `QTableWidget` (patrón de W.1)."""
    def __init__(self):
        self.table = QTableWidget()


def _vista_real_del_mensual(monkeypatch, tmp_path):
    if not BD_REBUILD_21_09.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_21_09.name}")
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    conection_mod.Conexion._instance = None
    pantalla = _PantallaFalsa()
    mostrar_db_mensualBraqui(pantalla)
    return pantalla


def test_toda_celda_editable_de_la_vista_del_mensual_esta_clasificada(app, monkeypatch, tmp_path):
    """La vista del mensual y de la redundante es UNA función
    (`mostrar_db_mensualBraqui`). Sobre una copia de `Rebuild_21-09`."""
    cc = _clasificacion()
    pantalla = _vista_real_del_mensual(monkeypatch, tmp_path)
    assert pantalla.table.rowCount() > 0, "compuerta: la copia debe traer filas reales"
    assert _celdas_con_metadata(pantalla.table), "compuerta: la vista debe traer alguna celda editable"
    problemas = _problemas_de_las_celdas(pantalla.table, cc)
    assert not problemas, (
        "celdas editables de la vista del mensual que editarían una entrada del "
        "cálculo, un resultado archivado o una columna sin política (si una "
        "columna nueva debe ser editable, clasifíquela primero en "
        "`services/correccion_calibracion.py`):\n  " + "\n  ".join(problemas))


def _tabla_con_celda(meta):
    tabla = QTableWidget(1, 1)
    tabla.setHorizontalHeaderLabels(["Celda de prueba"])
    item = QTableWidgetItem("x")
    item.setData(Qt.UserRole, 1)
    item.setData(Qt.UserRole + 1, meta)
    tabla.setItem(0, 0, item)
    return tabla


@pytest.mark.parametrize("meta, fragmento", [
    (("SistemaMedicion", "calibracion"), "entrada del cálculo"),
    (("SistemaMedicion", "electrometro"), "entrada del cálculo"),
    (("CondicionesMedicion", "t"), "entrada del cálculo"),
    (("LecturasMaximos", "V_300"), "entrada del cálculo"),
    (("TipoCalibracion", "fecha"), "no se corrige en sitio"),
    (("TipoCalibracion", "tipo"), "no se corrige en sitio"),
    (("TipoCalibracion", "activo"), "no se corrige en sitio"),
    (("ResultadosActividad", "Ks"), "resultado archivado"),
    (("ResultadosActividad", "actividad_decaimiento"), "resultado archivado"),
    ("conversion", "no declara (tabla, columna)"),
    (("TipoCalibracion", "columna_inventada"), "sin política"),
])
def test_el_detector_de_celdas_marca_cada_intrusa(app, meta, fragmento):
    cc = _clasificacion()
    problemas = _problemas_de_las_celdas(_tabla_con_celda(meta), cc)
    assert len(problemas) >= 1 and any(fragmento in p for p in problemas), (
        f"la celda {meta!r} debería detectarse como «{fragmento}»: {problemas}")


@pytest.mark.parametrize("meta", [
    ("ResultadosActividad", "actividad_monitor"),  # la única celda editable de hoy
    ("TipoCalibracion", "conversion"),             # recalcula (RC.2)
    ("TipoCalibracion", "serie"),                  # sin efecto en el cálculo
])
def test_el_detector_de_celdas_deja_pasar_lo_clasificado(app, meta):
    cc = _clasificacion()
    assert _problemas_de_las_celdas(_tabla_con_celda(meta), cc) == []
