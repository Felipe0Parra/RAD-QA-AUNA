"""S1 (PLAN_CONOS_MENSUAL_12-08.md §4-S1): garantía duradera de la paridad
por máquina que §3 del plan diagnosticó una sola vez. Ninguna modificación
de producción; este archivo es el tripwire permanente de §3.3.

No es una simulación completa de la UI de las cuatro clases mensuales
(600/iX/Halcyon/TAC) -- eso exigiría BD real, widgets.xlsx cargado y las
señales completas de Qt, un costo desproporcionado para un diagnóstico. En
su lugar combina tres técnicas deliberadamente distintas, cada una elegida
por ser la señal MÁS DIRECTA de cada invariante de la tabla §3.1, sin
necesidad de levantar la interfaz completa:

1. **Paridad**: existencia de método (conos, exclusivo de la subclase iX,
   nunca definido en la base) + comportamiento real de
   `_crear_accion_botones` (el botón de calculadora, que decide con una
   condición ejecutable) + inspección de fuente (equipos/cuñas, que se
   deciden por qué llamadas hace cada `iniGUI`/método de construcción, no
   por un flag). Es un heurístico de texto, no un verificador matemático --
   si algún día alguien reformatea esas llamadas a varias líneas o cambia
   el nombre de una variable intermedia, este test puede dar un falso rojo;
   eso es preferible a un falso verde silencioso.
2. **Tripwire AST del patrón colapsante**: cero SQL de producción con
   `MAX(id)` + `GROUP BY serie` a la vez (el patrón que E1, H2.10, F9 y G8
   fueron eliminando por separado). Allowlist vacía tras E1 y el borrado de
   `buscarModelo` (load.py, código muerto, mismo patrón).
3. **Tripwire de restauración**: toda función `Traerinfo*` de producción que
   consulte una tabla de `TABLAS_ANULABLES` debe filtrar `activo` en la
   misma consulta -- para que la próxima `Traerinfo_*` nazca correcta.
"""
import ast
import inspect
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QGridLayout, QWidget

from services.anulacion import TABLAS_ANULABLES
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "models", "mcc_PTW_read",
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _instancia_pelada(clase, equipo_f):
    """Solo lo que `_crear_accion_botones` necesita: category3/category4
    con un QGridLayout real (`.addLayout(buttonLayout, 62, 0)` exige la
    sobrecarga de 3 argumentos, exclusiva de QGridLayout) y `equipo_f`."""
    obj = clase.__new__(clase)
    QWidget.__init__(obj)
    obj.equipo_f = equipo_f
    obj.category3 = QWidget()
    obj.category3.setLayout(QGridLayout())
    obj.category4 = QWidget()
    obj.category4.setLayout(QGridLayout())
    return obj


class TestConosExclusivoDelIX:
    """§3.1: 'Conos (control_conos)' -- solo iX. Los métodos que lo
    implementan (`guardar_control_conos`, `Traerinfo_conos`) se definen
    ÚNICAMENTE en `PruebaMensualIX`, nunca en la base ni en las otras dos
    subclases -- si mañana alguien añade conos al 600 sin `Traerinfo_conos`,
    la definición aparecerá en `PruebaMensual600.__dict__` y este test lo
    dice."""

    def test_metodos_de_conos_solo_existen_en_ix(self):
        for nombre in ("guardar_control_conos", "Traerinfo_conos"):
            assert nombre in PruebaMensualIX.__dict__, (
                f"{nombre} debería estar definido en PruebaMensualIX")
            for otra in (PruebaMensual600, PruebaMensualHc, PruebaMensualTAC):
                assert nombre not in otra.__dict__, (
                    f"{nombre} apareció en {otra.__name__} -- conos deja de "
                    f"ser exclusivo del iX (§3.1)")

    def test_600_halcyon_tac_no_tienen_atributo_conos(self):
        """Ancla positiva complementaria: ni siquiera por herencia (hasattr,
        no solo __dict__ propio) 600/Halcyon/TAC alcanzan estos métodos."""
        for clase in (PruebaMensual600, PruebaMensualHc, PruebaMensualTAC):
            assert not hasattr(clase, "guardar_control_conos")
            assert not hasattr(clase, "Traerinfo_conos")
        assert hasattr(PruebaMensualIX, "guardar_control_conos")
        assert hasattr(PruebaMensualIX, "Traerinfo_conos")


class TestCalculadoraAlcanzablePorMaquina:
    """§3.1: '600/iX/Halcyon' tienen el botón "Calculadora de Dosis";
    'TAC' no. La decisión vive en una condición ejecutable
    (`_crear_accion_botones`, seiscientos_mensual.py) -- se ejercita
    directo, sin construir la interfaz completa."""

    def test_600_tiene_calculadora_en_category4(self, app):
        obj = _instancia_pelada(PruebaMensual600, "Clinac 600")
        _, btn = obj._crear_accion_botones(obj.category4)
        assert btn is not None

    def test_ix_tiene_calculadora_en_category4(self, app):
        obj = _instancia_pelada(PruebaMensualIX, "Clinac ix")
        _, btn = obj._crear_accion_botones(obj.category4)
        assert btn is not None

    def test_halcyon_tiene_calculadora_en_category3(self, app):
        obj = _instancia_pelada(PruebaMensualHc, "Halcyon")
        _, btn = obj._crear_accion_botones(obj.category3)
        assert btn is not None

    def test_tac_nunca_tiene_calculadora(self, app):
        """`_crear_accion_botones` decide por DOS ramas independientes: la
        de 600/iX (por nombre de clase) y la de Halcyon (por `equipo_f`,
        sin mirar la clase -- si algún día un TAC llegara con
        `equipo_f == "Halcyon"`, SÍ obtendría el botón sobre category3; eso
        no ocurre en producción porque TAC usa 'esHC'/'Tomógrafo'/
        'Clinac ix', nunca el string exacto 'Halcyon'. Este test refleja
        ese uso real, no un valor adversario inventado)."""
        obj = _instancia_pelada(PruebaMensualTAC, "Clinac ix")
        _, btn3 = obj._crear_accion_botones(obj.category3)
        _, btn4 = obj._crear_accion_botones(obj.category4)
        assert btn3 is None and btn4 is None


class TestEquiposYCunasPorMaquina:
    """§3.1: sección Equipos en 600/iX/Halcyon, ausente en TAC; cuñas en
    600/iX, ausente en Halcyon/TAC. Heurístico de texto sobre el método
    real de construcción de cada clase -- documentado como tal en el
    docstring del módulo."""

    _RE_EQUIPOS = re.compile(
        r"botonescombobox\(\s*self\.category1\s*,\s*self\.combo_menu\s*,\s*None\s*\)")
    _RE_CUNAS = re.compile(
        r"botonescombobox\(\s*self\.category2\s*,\s*None\s*,\s*self\.combos_seguridad\s*\)")

    def test_600_tiene_equipos_y_cunas(self):
        fuente = inspect.getsource(
            PruebaMensual600._configurar_aspectos_mecanicos_dosimetricos)
        assert self._RE_EQUIPOS.search(fuente), "600 debería tener sección Equipos"
        assert self._RE_CUNAS.search(fuente), "600 debería tener cuñas"

    def test_ix_hereda_equipos_y_cunas_de_600_sin_sobreescribir(self):
        """iX no define su propio `_configurar_aspectos_mecanicos_
        dosimetricos` -- hereda exactamente el de 600 (equipos + cuñas)."""
        assert "_configurar_aspectos_mecanicos_dosimetricos" not in PruebaMensualIX.__dict__, (
            "iX sobreescribió _configurar_aspectos_mecanicos_dosimetricos -- "
            "revisar si equipos/cuñas siguen presentes ahí")

    def test_halcyon_tiene_equipos_sin_cunas(self):
        fuente = inspect.getsource(PruebaMensualHc.controlTestWindow)
        assert self._RE_EQUIPOS.search(fuente), (
            "Halcyon debería tener sección Equipos en controlTestWindow")

        archivo = ROOT / "ui" / "paginasControles" / "PruebasMensuales" / "halcyon_mensual.py"
        texto = archivo.read_text(encoding="utf-8")
        assert "combos_seguridad" not in texto, (
            "halcyon_mensual.py ya menciona combos_seguridad -- Halcyon "
            "dejó de ser 'sin cuñas' (§3.1), revisar el inventario")

    def test_tac_no_tiene_equipos_ni_cunas(self):
        archivo = ROOT / "ui" / "paginasControles" / "PruebasMensuales" / "tac_mensual.py"
        texto = archivo.read_text(encoding="utf-8")
        assert "botonescombobox" not in texto, (
            "tac_mensual.py ya llama a botonescombobox -- TAC dejó de "
            "estar 'sin equipos' (§3.1), revisar el inventario")
        assert "combos_seguridad" not in texto


# ─────────────────────────────────────────────────────────────────────────
# Tripwire AST 1: el patrón colapsante MAX(id) + GROUP BY serie
# ─────────────────────────────────────────────────────────────────────────

EXEC_METHODS = {"execute", "executemany", "executescript", "prepare", "exec_", "exec"}
_RE_MAXID = re.compile(r"MAX\s*\(\s*ID\s*\)", re.IGNORECASE)
_RE_GROUPBY_SERIE = re.compile(r"GROUP\s+BY\s+SERIE", re.IGNORECASE)

# Vacía tras E1 (5c57d39, seiscientos_mensual.py:buscarModeloActivo) y el
# borrado de buscarModelo (load.py, código muerto, mismo patrón, S1).
ALLOWLIST_COLAPSO = frozenset()


def _literal_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value for v in node.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def _nombre_llamado(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _es_sql_colapsante(texto):
    return bool(texto) and _RE_MAXID.search(texto) and _RE_GROUPBY_SERIE.search(texto)


def _archivos_de(*subdirs):
    for subdir in subdirs:
        base = ROOT / subdir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(parte in EXCLUDE_DIRS for parte in path.parts):
                continue
            yield path


def _sql_colapsante_en_archivo(path):
    """Consultas SQL (argumento de un método execute*) con MAX(id) +
    GROUP BY serie a la vez, resolviendo también asignaciones locales
    simples (`sql = "..."`; `cursor.execute(sql)`), como ya hace
    test_a6_1_tripwire_auditoria.py -- comentarios (#...) y docstrings
    quedan fuera porque solo se inspeccionan los argumentos de llamadas
    exec*, no cualquier string literal del archivo."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hallazgos = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self):
            self.variables = {}

        def visit_FunctionDef(self, node):
            variables = dict(self.variables)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    s = _literal_str(sub.value)
                    if s is not None:
                        for t in sub.targets:
                            if isinstance(t, ast.Name):
                                variables[t.id] = s
                if isinstance(sub, ast.Call):
                    fname = _nombre_llamado(sub)
                    if fname in EXEC_METHODS and sub.args:
                        arg = sub.args[0]
                        texto = _literal_str(arg)
                        if texto is None and isinstance(arg, ast.Name):
                            texto = variables.get(arg.id)
                        if _es_sql_colapsante(texto):
                            hallazgos.append((sub.lineno, texto.strip()[:120]))

        visit_AsyncFunctionDef = visit_FunctionDef

    _Visitor().generic_visit(tree)
    return hallazgos


class TestPatronColapsanteBlindado:
    def test_produccion_sin_max_id_group_by_serie(self):
        violaciones = []
        for path in _archivos_de("ui", "data", "services"):
            clave = str(path.relative_to(ROOT))
            for lineno, _texto in _sql_colapsante_en_archivo(path):
                if f"{clave}:{lineno}" in ALLOWLIST_COLAPSO:
                    continue
                violaciones.append(f"{clave}:{lineno}")

        assert not violaciones, (
            "Patrón colapsante MAX(id)+GROUP BY serie encontrado fuera de "
            "la allowlist (vacía tras E1 y el borrado de buscarModelo, "
            "load.py). Este patrón esconde filas activas de id bajo detrás "
            "de un duplicado activo=0 de id alto (H2.6/H2.10/F9/G8/E1) -- "
            "reemplazar por una consulta filtrada por activo, sin "
            "colapsar. Hallazgos:\n" + "\n".join(violaciones))

    def test_el_detector_reconoce_el_patron_real(self, tmp_path):
        """Control positivo: el detector SÍ reconoce el patrón exacto que
        tenía `buscarModeloActivo` antes de E1 y que tenía `buscarModelo`
        antes de borrarse -- si esto no fuera cierto, el test de arriba
        pasaría en falso (nunca encontraría nada, allowlist vacía o no)."""
        archivo = tmp_path / "ejemplo_colapsante.py"
        archivo.write_text(
            'def f(self):\n'
            '    cursor.execute("""\n'
            '        SELECT model FROM equipos WHERE activo = 1\n'
            '        AND id IN (SELECT MAX(id) FROM equipos GROUP BY serie)\n'
            '    """)\n',
            encoding="utf-8")
        hallazgos = _sql_colapsante_en_archivo(archivo)
        assert len(hallazgos) == 1

    def test_el_detector_no_marca_sql_sano(self, tmp_path):
        """Control negativo: una consulta que solo filtra por activo, sin
        colapsar por serie, no debe marcarse."""
        archivo = tmp_path / "ejemplo_sano.py"
        archivo.write_text(
            'def f(self):\n'
            '    cursor.execute("SELECT model FROM equipos WHERE activo = 1")\n',
            encoding="utf-8")
        assert _sql_colapsante_en_archivo(archivo) == []


# ─────────────────────────────────────────────────────────────────────────
# Tripwire AST 2: Traerinfo* sobre TABLAS_ANULABLES sin filtro de activo
# ─────────────────────────────────────────────────────────────────────────

_RE_FROM = re.compile(r"FROM\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_RE_ACTIVO = re.compile(r"activo", re.IGNORECASE)


def _consultas_traerinfo_en_archivo(path):
    """(nombre_funcion, lineno, tabla, tiene_filtro_activo) para cada
    consulta SQL dentro de una función `Traerinfo*` que apunte a una tabla
    de TABLAS_ANULABLES."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    resultado = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("Traerinfo"):
            continue

        variables = {}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign):
                s = _literal_str(sub.value)
                if s is not None:
                    for t in sub.targets:
                        if isinstance(t, ast.Name):
                            variables[t.id] = s
            if isinstance(sub, ast.Call):
                fname = _nombre_llamado(sub)
                if fname in EXEC_METHODS and sub.args:
                    arg = sub.args[0]
                    texto = _literal_str(arg)
                    if texto is None and isinstance(arg, ast.Name):
                        texto = variables.get(arg.id)
                    if not texto:
                        continue
                    m = _RE_FROM.search(texto)
                    if not m:
                        continue
                    tabla = m.group(1)
                    if tabla not in TABLAS_ANULABLES:
                        continue
                    resultado.append(
                        (node.name, sub.lineno, tabla, bool(_RE_ACTIVO.search(texto))))

    return resultado


class TestTraerinfoFiltraActivo:
    def test_toda_traerinfo_sobre_tabla_anulable_filtra_activo(self):
        violaciones = []
        for path in _archivos_de("ui", "data", "services"):
            clave = str(path.relative_to(ROOT))
            for nombre, lineno, tabla, tiene_activo in _consultas_traerinfo_en_archivo(path):
                if not tiene_activo:
                    violaciones.append(f"{clave}:{lineno} {nombre}() -> {tabla}")

        assert not violaciones, (
            "Traerinfo* consulta una tabla de TABLAS_ANULABLES sin filtrar "
            "activo -- un bloque anulado (M2) podría restaurarse. "
            "Hallazgos:\n" + "\n".join(violaciones))

    def test_hay_al_menos_una_traerinfo_sobre_tabla_anulable(self):
        """Ancla positiva: si este test empezara a dar 0 encontradas, el
        de arriba pasaría vacío por falta de casos, no porque todo esté
        bien -- Traerinfo_cunas (control_cunas) y Traerinfo_conos
        (control_conos) deben seguir siendo detectados."""
        encontradas = set()
        for path in _archivos_de("ui", "data", "services"):
            for nombre, _lineno, tabla, _activo in _consultas_traerinfo_en_archivo(path):
                encontradas.add((nombre, tabla))
        assert ("Traerinfo_cunas", "control_cunas") in encontradas
        assert ("Traerinfo_conos", "control_conos") in encontradas

    def test_el_detector_reconoce_una_traerinfo_sin_filtro(self, tmp_path):
        """Control positivo: el detector SÍ marca una Traerinfo* que
        consulte una tabla anulable sin 'activo' en la consulta."""
        archivo = tmp_path / "ejemplo_sin_filtro.py"
        archivo.write_text(
            'def Traerinfo_ejemplo(self):\n'
            '    cursor.execute("SELECT x FROM control_cunas WHERE ref = ?", (self.ref,))\n',
            encoding="utf-8")
        resultado = _consultas_traerinfo_en_archivo(archivo)
        assert resultado == [("Traerinfo_ejemplo", 2, "control_cunas", False)]
