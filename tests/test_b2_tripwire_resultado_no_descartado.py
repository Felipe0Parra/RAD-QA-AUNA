"""B2 (PLAN_CORRECCIONES_REBUILD_25-08.md §Fase B): tripwire permanente --
nadie vuelve a llamar `loadtablacomplex` (u otra función de la misma
familia: devuelve `True`/`False` para decir si el guardado tuvo éxito) como
sentencia suelta, descartando el resultado.

Es lo que habría atrapado a `R3` el día que se escribió, en vez de tres
semanas después en un rebuild: `ix_anual.py::guardar_todas_fse` llamaba
`loadtablacomplex(...)` sin capturar el retorno, y la terminal imprimía
"subida(s) correctamente" sobre un guardado que el índice UNIQUE había
rechazado. B1 corrigió esa copia y otras DOS que el plan no nombraba
(`seiscientos_mensual.py::_subir_tabla_optimizada` y
`fieldSize::subir_tabla`) -- la misma clase de error, no solo el sitio
puntual.

Mismo espíritu que ES1/EB5: censal, con la lista de funciones vigiladas
revisada a mano (`FUNCIONES_VIGILADAS`). No intenta resolver SQL ni tipos --
solo AST: ¿la llamada es un `ast.Expr` de nivel de sentencia (nadie usa su
valor) o está dentro de una asignación/`return`/argumento de otra llamada
(alguien lo usa)?

Lo que este tripwire NO detecta a propósito (documentado, no un hueco
oculto): una variable asignada (`resultado = loadtablacomplex(...)`) que
luego nunca se lee -- eso es "variable no usada", terreno de un linter, no
de este censo. El patrón que causó R3 (y las otras dos copias) era la
llamada suelta, sin ninguna asignación; es lo que se vigila aquí.
"""
import ast
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIRECTORIOS_PRODUCCION = ["ui", "data", "services", "scripts"]

# Funciones que devuelven éxito/fallo del guardado -- revisada a mano.
# `loadtablacomplex` es la que R3 midió; se deja la lista abierta a mano
# para sumar otras si en el futuro se decide vigilarlas igual.
FUNCIONES_VIGILADAS = {"loadtablacomplex"}


def _archivos_produccion():
    for base in DIRECTORIOS_PRODUCCION:
        ruta_base = os.path.join(RAIZ, base)
        if not os.path.isdir(ruta_base):
            continue
        for dirpath, dirnames, filenames in os.walk(ruta_base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if fn.endswith(".py"):
                    yield os.path.join(dirpath, fn)


def _nombre_llamada(nodo_call):
    if isinstance(nodo_call.func, ast.Name):
        return nodo_call.func.id
    if isinstance(nodo_call.func, ast.Attribute):
        return nodo_call.func.attr
    return None


def censar_llamadas_descartadas():
    """Devuelve [(archivo, linea, nombre_funcion), ...] de toda llamada a
    una función vigilada hecha como sentencia suelta (ast.Expr de nivel de
    módulo/función -- el valor de retorno no se asigna, no se retorna, no
    se pasa como argumento)."""
    hallazgos = []
    for ruta in _archivos_produccion():
        with open(ruta, encoding="utf-8") as f:
            try:
                arbol = ast.parse(f.read(), filename=ruta)
            except SyntaxError:
                continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Call):
                nombre = _nombre_llamada(nodo.value)
                if nombre in FUNCIONES_VIGILADAS:
                    hallazgos.append(
                        (os.path.relpath(ruta, RAIZ), nodo.lineno, nombre))
    return hallazgos


def test_ninguna_llamada_vigilada_descarta_su_resultado():
    hallazgos = censar_llamadas_descartadas()
    assert hallazgos == [], (
        "Llamada a una función que devuelve éxito/fallo del guardado, con "
        "el resultado descartado (mismo síntoma que R3) -- captura el "
        "retorno (asignación, `return`, o como argumento) y avisa si es "
        "False:\n" +
        "\n".join(f"  {a}:{l} -- {n}()" for a, l, n in hallazgos))


class TestElPropioMecanismoDetectaUnaLlamadaSuelta:
    """Rojo-antes-que-verde, permanente: sin un archivo de producción real
    que romper, se verifica el mecanismo contra fuente sintética -- prueba
    que el AST realmente distingue "descartado" de "usado", no solo que la
    lista actual da cero."""

    def _censar_fuente(self, tmp_path, codigo, monkeypatch):
        modulo = sys.modules[__name__]
        archivo = tmp_path / "ui" / "modulo_sintetico.py"
        archivo.parent.mkdir(parents=True)
        archivo.write_text(codigo, encoding="utf-8")
        monkeypatch.setattr(modulo, "RAIZ", str(tmp_path))
        monkeypatch.setattr(modulo, "DIRECTORIOS_PRODUCCION", ["ui"])
        return modulo.censar_llamadas_descartadas()

    def test_llamada_suelta_se_detecta(self, tmp_path, monkeypatch):
        hallazgos = self._censar_fuente(
            tmp_path,
            "def f(nombre_tabla, table, datos, reference):\n"
            "    loadtablacomplex(nombre_tabla, table, datos, reference=reference)\n"
            "    print('subida correctamente')\n",
            monkeypatch)
        assert len(hallazgos) == 1
        assert hallazgos[0][1] == 2
        assert hallazgos[0][2] == "loadtablacomplex"

    def test_asignacion_no_se_marca(self, tmp_path, monkeypatch):
        hallazgos = self._censar_fuente(
            tmp_path,
            "def f(nombre_tabla, table, datos, reference):\n"
            "    resultado = loadtablacomplex(nombre_tabla, table, datos, reference=reference)\n"
            "    if not resultado:\n"
            "        print('fallo')\n",
            monkeypatch)
        assert hallazgos == []

    def test_append_como_argumento_no_se_marca(self, tmp_path, monkeypatch):
        hallazgos = self._censar_fuente(
            tmp_path,
            "def f(nombre_tabla, table, datos, reference):\n"
            "    resultados = []\n"
            "    resultados.append(loadtablacomplex(nombre_tabla, table, datos, reference=reference))\n",
            monkeypatch)
        assert hallazgos == []

    def test_return_no_se_marca(self, tmp_path, monkeypatch):
        hallazgos = self._censar_fuente(
            tmp_path,
            "def f(nombre_tabla, table, datos, reference):\n"
            "    return loadtablacomplex(nombre_tabla, table, datos, reference=reference)\n",
            monkeypatch)
        assert hallazgos == []

    def test_otra_funcion_no_vigilada_no_se_marca(self, tmp_path, monkeypatch):
        hallazgos = self._censar_fuente(
            tmp_path,
            "def f():\n"
            "    otra_funcion_cualquiera()\n",
            monkeypatch)
        assert hallazgos == []
