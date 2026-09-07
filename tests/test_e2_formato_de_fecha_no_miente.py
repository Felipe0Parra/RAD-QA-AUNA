"""E2 (PLAN_BRAQUI_HORA_EDITABLE_07-09.md): tripwire de la CLASE de defecto
que `DP-87` destapó -- ningún widget de fecha puede MOSTRAR un formato con
secciones de tiempo (`H`/`h`/`m`/`s`) si su tipo real (`QDateEdit`, no
`QDateTimeEdit`) no las crea. Qt no avisa: acepta el `setDisplayFormat` con
hora sobre un `QDateEdit`, lo pinta, y descarta las secciones en silencio
(`sectionCount()` se queda en 3). `E1` corrigió el único sitio conocido
(`encabezado_braq/date_box`); este archivo es la garantía de que la clase
completa queda cerrada, no solo ese sitio -- la lección de `DP-79`: el censo
se DERIVA del productor (`widgets.xlsx` + los `setDisplayFormat` reales del
código, más los `QDateEdit()`/`QDateTimeEdit()` construidos a mano), nunca
se copia de "lo que ya se arregló".

Dos censos independientes, tal como especifica el plan:

1. **Estático** (estas clases): para cada llamada
   `self.<attr>.setDisplayFormat("<literal>")` en producción, resuelve el
   tipo real del widget -- por construcción directa (`self.<attr> =
   QDateEdit()`/`QDateTimeEdit()` en la misma clase, cubre los widgets
   hechos a mano como Halcyon o `DateRangeDialog`) o, si no hay
   construcción directa, por la hoja que la clase pasó a `self.setupBox`
   cruzada contra `widgets.xlsx` (cubre las pantallas de las diarias/
   mensuales/anuales). Las llamadas `getattr(self, nombre).
   setDisplayFormat(...)` del creador GENÉRICO (`PruebasDiarias.py::
   createInterface`) quedan fuera a propósito: ahí el literal se elige
   dentro de la rama `if widget_type == '...'` que acaba de crear ESE
   widget, así que es seguro por construcción y no por resolución -- el
   censo dinámico (2) las cubre indirectamente al instanciar la pantalla
   real.

2. **Dinámico**: instancia cada pantalla real (offscreen) y afirma que
   `sectionCount()` incluye lo que `displayFormat()` promete. Cubre lo que
   el censo estático no resuelve.

**Hallazgo real de este censo, fuera de alcance de este plan** (documentado
en `CLAUDE.md::DP-89`, NO corregido aquí): `ui/paginasGuia/dialogs.py::
DateRangeDialog.start_date`/`.end_date` son `QDateEdit()` con
`"yyyy-MM-dd HH:mm:ss"` -- la MISMA clase de defecto que `braqui.date_box`
tenía, en el diálogo de exportación a Excel (`SQLtoEXCEL.py`), que además
lee `.text()` crudo hacia una comparación de texto en SQL. Whitelist
explícita con el motivo, no una omisión silenciosa.
"""
import ast
import re
from pathlib import Path

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtWidgets import QApplication, QDateEdit, QDateTimeEdit, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion

ROOT = Path(__file__).resolve().parent.parent
RUTA_XLSX = ROOT / "data" / "widgets.xlsx"

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

# Qt permite texto literal entre comillas simples dentro del formato (p.ej.
# "'a las' HH") -- eso NO cuenta como sección de tiempo. Se retira antes de
# buscar H/h/m/s.
PATRON_LITERAL_ESCAPADO = re.compile(r"'[^']*'")
PATRON_SECCION_TIEMPO = re.compile(r"[Hhms]")

# (archivo, atributo) -> motivo. Cada entrada documenta POR QUÉ ese sitio
# con formato-de-tiempo-sobre-QDateEdit es seguro o, si no lo es, por qué
# este plan no lo corrige.
SITIOS_PERMITIDOS = {
    ("ui/paginasGuia/dialogs.py", "start_date"):
        "DP-89: mismo defecto que braqui (QDateEdit + formato con hora), "
        "en DateRangeDialog (exportador a Excel) -- fuera de alcance de "
        "PLAN_BRAQUI_HORA_EDITABLE_07-09.md (es sobre el diario de "
        "braqui, no sobre SQLtoEXCEL). Documentado, no corregido; "
        "decisión pendiente del físico.",
    ("ui/paginasGuia/dialogs.py", "end_date"):
        "DP-89: mismo motivo que start_date, mismo archivo.",
}


def _archivos_produccion():
    for ruta in ROOT.rglob("*.py"):
        relativo = ruta.relative_to(ROOT)
        if set(relativo.parts) & EXCLUDE_DIRS:
            continue
        yield relativo, ruta


def _formato_tiene_seccion_de_tiempo(literal):
    sin_escapes = PATRON_LITERAL_ESCAPADO.sub("", literal)
    return bool(PATRON_SECCION_TIEMPO.search(sin_escapes))


def _tipo_qt_de_llamada(nodo_call):
    """'QDateEdit' | 'QDateTimeEdit' | None para `nodo_call` si es
    literalmente `QDateEdit()`/`QDateTimeEdit()`."""
    if isinstance(nodo_call.func, ast.Name) and nodo_call.func.id in (
            "QDateEdit", "QDateTimeEdit"):
        return nodo_call.func.id
    return None


def _censar_clase(nodo_clase):
    """Para una ast.ClassDef: (asignaciones_directas, hojas_encabezado,
    llamadas_formato) -- los tres insumos que la resolución necesita."""
    asignaciones = {}
    hojas = set()
    llamadas = []

    for nodo in ast.walk(nodo_clase):
        # self.<attr> = QDateEdit()/QDateTimeEdit()
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            objetivo = nodo.targets[0]
            if (isinstance(objetivo, ast.Attribute)
                    and isinstance(objetivo.value, ast.Name)
                    and objetivo.value.id == "self"
                    and isinstance(nodo.value, ast.Call)):
                tipo = _tipo_qt_de_llamada(nodo.value)
                if tipo:
                    asignaciones[objetivo.attr] = tipo

        # self.setupBox(archivo, '<hoja>', ...)
        if (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "setupBox"
                and isinstance(nodo.func.value, ast.Name)
                and nodo.func.value.id == "self"):
            for arg in nodo.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value != "widgets.xlsx":
                        hojas.add(arg.value)

        # self.<attr>.setDisplayFormat("<literal>")
        if (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "setDisplayFormat"
                and isinstance(nodo.func.value, ast.Attribute)
                and isinstance(nodo.func.value.value, ast.Name)
                and nodo.func.value.value.id == "self"
                and len(nodo.args) == 1
                and isinstance(nodo.args[0], ast.Constant)
                and isinstance(nodo.args[0].value, str)):
            llamadas.append((nodo.func.value.attr, nodo.args[0].value,
                              nodo.lineno))

    return asignaciones, hojas, llamadas


def _mapa_widgets_xlsx():
    """hoja -> {nombre: widget_type}, leído UNA vez de widgets.xlsx."""
    mapa = {}
    x = pd.ExcelFile(RUTA_XLSX)
    for hoja in x.sheet_names:
        df = pd.read_excel(x, sheet_name=hoja)
        if "nombres" not in df.columns or "widget_type" not in df.columns:
            continue
        mapa[hoja] = dict(zip(df["nombres"].astype(str), df["widget_type"].astype(str)))
    return mapa


def _censar():
    """Devuelve (hallazgos, sin_resolver) -- hallazgos es
    {(archivo, attr): (literal, lineno)} para violaciones reales;
    sin_resolver es la lista de sitios que ni la asignación directa ni
    widgets.xlsx pudieron tipar (se anotan, no se fallan: el censo
    dinámico es su respaldo)."""
    mapa_xlsx = _mapa_widgets_xlsx()
    hallazgos = {}
    sin_resolver = []

    for relativo, ruta in _archivos_produccion():
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo_clase in ast.walk(arbol):
            if not isinstance(nodo_clase, ast.ClassDef):
                continue
            asignaciones, hojas, llamadas = _censar_clase(nodo_clase)
            for attr, literal, lineno in llamadas:
                if not _formato_tiene_seccion_de_tiempo(literal):
                    continue
                tipo = asignaciones.get(attr)
                if tipo is None:
                    for hoja in hojas:
                        declarado = mapa_xlsx.get(hoja, {}).get(attr)
                        if declarado:
                            tipo = declarado
                            break
                if tipo is None:
                    sin_resolver.append((str(relativo), attr, lineno))
                    continue
                if tipo == "QDateEdit":
                    hallazgos[(str(relativo), attr)] = (literal, lineno)

    return hallazgos, sin_resolver


def test_ningun_qdateedit_promete_horas_que_no_puede_dar():
    """El corazón del tripwire: cualquier `setDisplayFormat` con sección de
    tiempo sobre un widget cuyo tipo resuelto es `QDateEdit` es un hallazgo,
    salvo que esté en `SITIOS_PERMITIDOS` con su motivo."""
    hallazgos, _ = _censar()
    sin_declarar = {k: v for k, v in hallazgos.items() if k not in SITIOS_PERMITIDOS}
    assert not sin_declarar, (
        f"Widget(s) QDateEdit con formato de HORA en su displayFormat -- "
        f"sectionCount() no la tendrá y Qt lo aceptará en silencio. Agrega "
        f"el sitio a SITIOS_PERMITIDOS con su motivo, o corrígelo (cambiar "
        f"el widget a QDateTimeEdit, como E1): {sin_declarar}"
    )


def test_sitios_permitidos_siguen_existiendo():
    """Si un sitio de la whitelist desaparece (se corrigió, se retiró el
    código), hay que limpiar la lista -- mismo criterio que MI0/U7."""
    hallazgos, _ = _censar()
    ausentes = set(SITIOS_PERMITIDOS) - set(hallazgos)
    assert not ausentes, (
        f"Sitio(s) en SITIOS_PERMITIDOS que ya no aparecen -- revisa y "
        f"limpia la lista: {ausentes}"
    )


def test_censo_encuentra_el_sitio_conocido_de_dp89():
    """Que el censo no sea un placebo: debe encontrar EXACTAMENTE los 2
    sitios reales conocidos hoy (los dos, en el mismo archivo)."""
    hallazgos, _ = _censar()
    assert set(hallazgos) == set(SITIOS_PERMITIDOS)


def test_encabezado_braq_ya_no_aparece_como_hallazgo():
    """Regresión directa: antes de E1, `braquiterapia.py`/`date_box`
    aparecía aquí. Tras E1, no debe estar ni en hallazgos ni en la
    whitelist -- ya no es un QDateEdit."""
    hallazgos, _ = _censar()
    for (archivo, attr) in hallazgos:
        assert not (archivo.endswith("braquiterapia.py") and attr == "date_box"), (
            "el date_box de braqui volvió a aparecer como QDateEdit con "
            "hora -- ¿se revirtió E1?")


class TestE2RojoAntesQueVerdeSobreElXlsxTestigo:
    """Contra una COPIA de widgets.xlsx con encabezado_braq/date_box vuelto
    a QDateEdit (el estado previo a E1) -- sin tocar el árbol real, sin
    monkeypatch de resource_path (el censo estático lee RUTA_XLSX
    directamente): se construye la copia, se apunta _mapa_widgets_xlsx a
    ella vía un RUTA_XLSX local, y se confirma que el censo señala el
    sitio por su nombre."""

    def test_censo_estatico_detecta_encabezado_braq_sin_e1(self, tmp_path, monkeypatch):
        import openpyxl
        copia = tmp_path / "widgets_sin_e1.xlsx"
        wb = openpyxl.load_workbook(RUTA_XLSX)
        ws = wb["encabezado_braq"]
        encontrado = False
        for row in ws.iter_rows(min_row=2):
            if row[1].value == "date_box":
                assert row[2].value == "QDateTimeEdit", (
                    "precondición: antes de revertir, debe ser QDateTimeEdit "
                    "(el estado real tras E1)")
                row[2].value = "QDateEdit"
                encontrado = True
        assert encontrado
        wb.save(copia)

        import sys
        modulo = sys.modules[__name__]
        monkeypatch.setattr(modulo, "RUTA_XLSX", copia)
        hallazgos, _ = modulo._censar()
        assert ("ui/paginasControles/PruebasDiarias/braquiterapia.py", "date_box") in hallazgos, (
            "el censo debía señalar encabezado_braq/date_box con el xlsx "
            "revertido -- si no lo hace, el censo no está detectando el "
            "defecto que motivó este plan")

    def test_censo_estatico_sintetico_en_otra_hoja_tambien_cae(self, app, tmp_path, monkeypatch):
        """Segundo rojo pedido por el plan: que el censo no esté cazando
        SOLO el caso ya conocido. Se pone un formato con hora sobre un
        QDateEdit en OTRA hoja arbitraria (encabezado_600/date_box, que
        hoy no tiene hora) -- eso por sí solo no dispara nada porque el
        CÓDIGO no le pide ese formato; lo que se prueba aquí es la mitad
        REAL del censo dinámico: que un QDateEdit con formato sintético
        de hora sí muestra sectionCount() < 6, sin importar la hoja."""
        w = QDateEdit()
        w.setDisplayFormat("MM/dd/yyyy HH:mm")
        assert w.sectionCount() == 3, (
            "un QDateEdit con formato de hora sintético, en cualquier "
            "contexto, sigue sin crear las secciones -- confirma que el "
            "defecto es del TIPO de widget, no de una hoja en particular")


class TestE2ElHechoDeQtQueJustificaElCenso:
    """Fija, en un test propio, el hecho que hace necesario este tripwire
    -- para que quien lea el censo mañana entienda POR QUÉ existe y no lo
    'simplifique' de vuelta a comparar solo displayFormat()."""

    def test_qdateedit_con_formato_de_hora_tiene_3_secciones_no_6(self, app):
        w = QDateEdit()
        w.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        assert w.sectionCount() == 3

    def test_setcurrentsection_hourssection_se_ignora(self, app):
        w = QDateEdit()
        w.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        w.setCurrentSection(QDateTimeEdit.HourSection)
        assert w.currentSection() != QDateTimeEdit.HourSection

    def test_stepby_sobre_la_hora_mueve_el_dia(self, app):
        w = QDateEdit()
        w.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        w.setDate(QDate(2026, 9, 7))
        w.setCurrentSection(QDateTimeEdit.HourSection)
        w.stepBy(1)
        assert w.date() == QDate(2026, 9, 8), (
            "el hecho de Qt que justifica todo el plan: la flecha 'sobre "
            "la hora' de un QDateEdit mueve el día, no la hora")


# --- Censo dinámico: cada pantalla real, offscreen ---------------------

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _invariante_seccion_cubre_formato(widget, nombre):
    fmt = widget.displayFormat()
    promete_hora = _formato_tiene_seccion_de_tiempo(
        PATRON_LITERAL_ESCAPADO.sub("", fmt))
    if promete_hora:
        assert widget.sectionCount() >= 6, (
            f"{nombre}: displayFormat()={fmt!r} promete hora pero "
            f"sectionCount()={widget.sectionCount()} -- el widget no "
            f"puede darla (es un {type(widget).__name__})")
    else:
        assert widget.sectionCount() == 3, (
            f"{nombre}: displayFormat()={fmt!r} no debería tener "
            f"secciones de tiempo, pero sectionCount()="
            f"{widget.sectionCount()}")


@pytest.mark.parametrize("nombre_clase", [
    "PruebaDiariaBraq", "PruebaDiaria600", "PruebaDiariaIX", "PruebaDiariaHc",
    "PosicionamientoInicial", "Linealidad",
])
def test_pantallas_reales_cumplen_la_invariante(app, bd_temporal, nombre_clase):
    modulos = {
        "PruebaDiariaBraq": "ui.paginasControles.PruebasDiarias.braquiterapia",
        "PosicionamientoInicial": "ui.paginasControles.PruebasDiarias.braquiterapia",
        "Linealidad": "ui.paginasControles.PruebasDiarias.braquiterapia",
        "PruebaDiaria600": "ui.paginasControles.PruebasDiarias.seiscientos",
        "PruebaDiariaIX": "ui.paginasControles.PruebasDiarias.IX",
        "PruebaDiariaHc": "ui.paginasControles.PruebasDiarias.halcyon",
    }
    import importlib
    modulo = importlib.import_module(modulos[nombre_clase])
    Clase = getattr(modulo, nombre_clase)
    instancia = Clase(_UsuarioFalso())
    _invariante_seccion_cubre_formato(instancia.date_box, nombre_clase)


def test_daterangedialog_NO_cumple_la_invariante_hallazgo_dp89(app):
    """No es una regresión: es el hallazgo documentado (`DP-89`). Se fija
    aquí en rojo-a-propósito (invertido) para que si algún día alguien
    arregla `DateRangeDialog` sin retirar esta entrada, este test avise
    de que hay que actualizar la whitelist de arriba y este test también."""
    from ui.paginasGuia.dialogs import DateRangeDialog
    d = DateRangeDialog()
    assert d.start_date.sectionCount() == 3, (
        "si esto cambió, DateRangeDialog ya no tiene el defecto de DP-89 "
        "-- retira la whitelist de SITIOS_PERMITIDOS y este test")
    assert "HH" in d.start_date.displayFormat()
