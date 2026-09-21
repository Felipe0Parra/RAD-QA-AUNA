"""C.3 (PLAN_REFERENCIAS_EDITABLES_21-09.md): tripwire de la clase de defecto
que esta pestaña puede introducir -- un camino FUTURO que escriba en
`referencias_qc` saltándose el permiso (`es_fisico_jefe`) y la auditoría que
viven en `services/referencias_qc.py`.

*"Ninguna pantalla futura puede cambiar una referencia sin pasar por el
permiso y la auditoría."*

Mismo criterio que U7 (`test_u7_tripwire_escritura_users.py`): el censo se
DERIVA del productor -- todo sitio de producción que escribe en la tabla --
nunca se copia del arreglo, y va por `(archivo, función)`, no por número de
línea (inmune a Trampa 5).

Se detectan TRES formas de escribir, porque una sola dejaría pasar las otras:
  1. SQL de escritura (INSERT/UPDATE/DELETE/REPLACE/DROP) que nombra la
     tabla, sea con el nombre literal o con la constante `TABLA` del servicio
     (dentro de un f-string, que es como lo escribe el propio servicio);
  2. una llamada a una primitiva de escritura del contrato de QC
     (`reemplazar_bloque`, `anular_fila`, `sql_anular_bloque`) cuyo argumento
     sea la tabla (literal o `TABLA`);
  3. (en el servicio) toda función que escribe debe llamar a
     `es_fisico_jefe`, para que un segundo escritor DENTRO del módulo no
     se salte el permiso.

Solo se examinan los archivos que TOCAN la tabla (mencionan el literal
'referencias_qc' o importan el servicio): una `TABLA` ajena en otro módulo
no es ruido.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "dist", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

NOMBRE_TABLA = "referencias_qc"
PRIMITIVAS_DE_ESCRITURA = {"reemplazar_bloque", "anular_fila", "sql_anular_bloque"}

# La tabla, con su nombre o con la constante del servicio embebida en un
# f-string (`{TABLA}`, que es cómo la escribe el propio servicio).
# `{TABLA}` distingue mayúsculas a propósito: las primitivas genéricas del
# contrato (anular_fila, reemplazar_bloque) escriben `{tabla}` en minúscula.
_TABLA = r"(?:referencias_qc|(?-i:\{TABLA\}))"
PATRON_ESCRITURA = re.compile(
    rf"(insert\s+(?:or\s+\w+\s+)?into\s+{_TABLA}"
    rf"|replace\s+into\s+{_TABLA}"
    rf"|update\s+{_TABLA}"
    rf"|delete\s+from\s+{_TABLA}"
    rf"|drop\s+table\s+(?:if\s+exists\s+)?{_TABLA})",
    re.IGNORECASE)

# El ÚNICO sitio autorizado, con su motivo escrito.
SITIOS_PERMITIDOS = {
    ("services/referencias_qc.py", "fijar_referencia"):
        "verifica es_fisico_jefe, valida fuente/observaciones/valor y audita "
        "en la misma transacción (B.2, DA-52)",
}


def _texto_de(nodo):
    """Texto de una cadena o de un f-string, con cada `{nombre}` conservado
    como tal (así `f"INSERT INTO {TABLA}"` se reconoce)."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        partes = []
        for valor in nodo.values:
            if isinstance(valor, ast.Constant):
                partes.append(str(valor.value))
            elif isinstance(valor, ast.FormattedValue):
                v = valor.value
                if isinstance(v, ast.Name):
                    partes.append("{" + v.id + "}")
                elif isinstance(v, ast.Attribute):
                    partes.append("{" + v.attr + "}")
                else:
                    partes.append("{?}")
        return "".join(partes)
    return None


def _es_la_tabla(nodo):
    """¿Este argumento ES la tabla? Literal, o la constante `TABLA`."""
    if isinstance(nodo, ast.Constant):
        return nodo.value == NOMBRE_TABLA
    if isinstance(nodo, ast.Name):
        return nodo.id == "TABLA"
    if isinstance(nodo, ast.Attribute):
        return nodo.attr == "TABLA"
    return False


def _toca_la_tabla(arbol):
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                and NOMBRE_TABLA in nodo.value):
            return True
        if (isinstance(nodo, ast.ImportFrom) and nodo.module
                and nodo.module.endswith("referencias_qc")):
            return True
        if (isinstance(nodo, ast.ImportFrom) and nodo.module == "services"
                and any(a.name == "referencias_qc" for a in nodo.names)):
            return True
        if (isinstance(nodo, ast.Import)
                and any(a.name.endswith("referencias_qc") for a in nodo.names)):
            return True
    return False


class _Censo(ast.NodeVisitor):
    """Recorre el módulo llevando la función que envuelve a cada nodo
    (`<modulo>` fuera de toda función)."""

    def __init__(self):
        self._pila = ["<modulo>"]
        self.sitios = set()

    def _entrar(self, nodo):
        self._pila.append(nodo.name)
        self.generic_visit(nodo)
        self._pila.pop()

    visit_FunctionDef = _entrar
    visit_AsyncFunctionDef = _entrar

    def visit_Constant(self, nodo):
        self._revisar_texto(nodo)

    def visit_JoinedStr(self, nodo):
        # no se desciende: el texto completo del f-string ya se examinó
        self._revisar_texto(nodo)

    def _revisar_texto(self, nodo):
        texto = _texto_de(nodo)
        if texto and PATRON_ESCRITURA.search(texto):
            self.sitios.add(self._pila[-1])

    def visit_Call(self, nodo):
        f = nodo.func
        nombre = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
        if nombre in PRIMITIVAS_DE_ESCRITURA:
            if (any(_es_la_tabla(a) for a in nodo.args)
                    or any(_es_la_tabla(k.value) for k in nodo.keywords)):
                self.sitios.add(self._pila[-1])
        self.generic_visit(nodo)


def _archivos_produccion():
    for ruta in ROOT.rglob("*.py"):
        relativo = ruta.relative_to(ROOT)
        if set(relativo.parts) & EXCLUDE_DIRS:
            continue
        yield relativo, ruta


def _sitios_de_archivo(ruta):
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    if not _toca_la_tabla(arbol):
        return set()
    censo = _Censo()
    censo.visit(arbol)
    return censo.sitios


def _censar():
    hallazgos = set()
    for relativo, ruta in _archivos_produccion():
        for funcion in _sitios_de_archivo(ruta):
            hallazgos.add((relativo.as_posix(), funcion))
    return hallazgos


def test_ninguna_escritura_sobre_referencias_qc_fuera_del_servicio():
    """El corazón del tripwire: cualquier escritura nueva fuera de
    `services/referencias_qc.py` (o una ya censada que se renombre o se
    mueva) pone la suite en rojo y exige declarar el motivo."""
    sin_declarar = _censar() - set(SITIOS_PERMITIDOS)
    assert not sin_declarar, (
        "Escritura(s) NUEVA(S) sobre `referencias_qc` fuera del servicio -- "
        "se saltan el permiso del jefe y la auditoría. Pasa por "
        "services.referencias_qc.fijar_referencia, o (si de verdad es "
        f"legítima) declárala en SITIOS_PERMITIDOS con su motivo: {sin_declarar}")


def test_los_sitios_permitidos_siguen_existiendo():
    """Si el único sitio autorizado desaparece o se renombra, hay que
    revisar la lista en vez de dejarla acumulando entradas muertas."""
    ausentes = set(SITIOS_PERMITIDOS) - _censar()
    assert not ausentes, f"Sitio(s) autorizado(s) que ya no aparecen: {ausentes}"


def test_el_censo_encuentra_exactamente_el_sitio_real():
    """Que no sea un placebo: hoy hay UN escritor, y es el servicio."""
    assert _censar() == set(SITIOS_PERMITIDOS)


def test_toda_funcion_del_servicio_que_escribe_llama_a_es_fisico_jefe():
    """Un segundo escritor DENTRO del módulo (una función `importar_...`
    futura) no puede saltarse el permiso por vivir en el sitio autorizado."""
    ruta = ROOT / "services" / "referencias_qc.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    escriben = _sitios_de_archivo(ruta)
    assert escriben, (
        "el censo no encontró ninguna función que escriba en el servicio -- "
        "¿cambió el archivo de forma que el detector ya no lo ve?")
    funciones = {n.name: n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}
    for nombre in escriben:
        llama_al_permiso = any(
            isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
            and sub.func.id == "es_fisico_jefe"
            for sub in ast.walk(funciones[nombre]))
        assert llama_al_permiso, (
            f"{nombre} escribe en `referencias_qc` pero no llama a "
            "es_fisico_jefe -- control de acceso cosmético")


class TestElCensoDiscrimina:
    """Rojo dirigido (patrón de R.4/B.4): un intruso temporal dentro de la
    raíz del proyecto DEBE aparecer en el censo, en cada una de las formas de
    escribir. El archivo se borra siempre; el árbol real no se toca."""

    def _con_intruso(self, cuerpo):
        intruso = ROOT / "services" / "_intruso_c3_tmp.py"
        intruso.write_text(cuerpo, encoding="utf-8")
        try:
            return _censar() - set(SITIOS_PERMITIDOS)
        finally:
            intruso.unlink()

    def test_detecta_un_insert_literal(self):
        extra = self._con_intruso(
            "def cambia(cur):\n"
            "    cur.execute(\"INSERT INTO referencias_qc (equipo) VALUES ('x')\")\n")
        assert extra == {("services/_intruso_c3_tmp.py", "cambia")}

    def test_detecta_un_update_y_un_delete_y_un_drop(self):
        for sql in ("UPDATE referencias_qc SET valor = 1",
                    "DELETE FROM referencias_qc",
                    "DROP TABLE IF EXISTS referencias_qc"):
            extra = self._con_intruso(f"def cambia(cur):\n    cur.execute({sql!r})\n")
            assert extra == {("services/_intruso_c3_tmp.py", "cambia")}, sql

    def test_detecta_una_primitiva_de_escritura_con_la_tabla_literal(self):
        extra = self._con_intruso(
            "def cambia(cur):\n"
            "    reemplazar_bloque(cur, 'referencias_qc', [], '', [], 'u')\n")
        assert extra == {("services/_intruso_c3_tmp.py", "cambia")}

    def test_detecta_la_constante_TABLA_importada_del_servicio(self):
        extra = self._con_intruso(
            "from services.referencias_qc import TABLA\n"
            "def cambia(cur):\n"
            "    cur.execute(f'INSERT INTO {TABLA} (equipo) VALUES (1)')\n"
            "    anular_fila(cur, TABLA, 1)\n")
        assert extra == {("services/_intruso_c3_tmp.py", "cambia")}

    def test_una_lectura_no_es_una_escritura(self):
        extra = self._con_intruso(
            "def lee(cur):\n"
            "    return cur.execute('SELECT valor FROM referencias_qc').fetchall()\n")
        assert extra == set()

    def test_una_TABLA_ajena_en_un_modulo_que_no_toca_la_tabla_no_es_ruido(self):
        extra = self._con_intruso(
            "TABLA = 'otra'\n"
            "def escribe(cur):\n"
            "    cur.execute(f'INSERT INTO {TABLA} VALUES (1)')\n")
        assert extra == set()

    def test_el_intruso_no_queda_en_el_arbol(self):
        self._con_intruso("def x():\n    pass\n")
        assert not (ROOT / "services" / "_intruso_c3_tmp.py").exists()
