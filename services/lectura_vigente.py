"""AN1 (PLAN_LECTURA_VIGENTE_18-08.md §6-AN1): analizador único y compartido
de "toda lectura/escritura de una tabla versionada del bloque de QC debe
distinguir el bloque vigente por construcción".

Por qué existe: el 13-08 versionamos (contrato anular+insertar) 22 tablas
hijas del bloque de QC, pero no revisamos todas las lecturas que colgaban de
ellas. El 18-08 aparecieron tres defectos reales (control mensual duplicado
en pantalla, dosis de referencia mostrada vacía, catálogo de equipos anual
mezclando históricos con vigentes) que el tripwire LE4 de entonces no
atrapó, por cuatro huecos exactos:

  1. SQL armado en una variable (`query = "..."; query += "..."`) es
     invisible para un analizador que solo mira el argumento LITERAL de
     `execute()`.
  2. El alcance de LE4 era una lista escrita a mano (`TABLAS_EN_ALCANCE`)
     que quedó desincronizada de `TABLAS_ANULABLES` en cuanto PR1 amplió
     el contrato sin ensanchar la vigilancia.
  3. El detector solo reconocía `FROM`, no `JOIN` -- una tabla que entra
     por un `LEFT JOIN` era invisible.
  4. El filtro se comprobaba por SENTENCIA, no por TABLA -- un `cm.activo`
     de otra tabla en el mismo SQL daba por bueno un `p.activo` que nunca
     estuvo.

Este módulo es el ÚNICO lugar donde vive el criterio "¿esta referencia a
una tabla versionada tiene su propio filtro de `activo`?". Lo consultan por
igual ES1 (frente estático, sobre SQL reconstruido del AST) y RT1 (frente
dinámico, sobre SQL ya resuelto en tiempo de ejecución) -- nunca dos copias
independientes del mismo criterio, que es precisamente la causa por la que
LE4 quedó ciego (mismo defecto de fondo que LE0 corrigió unificando
`filtro_activo()`).

No importa PyQt5 ni abre ninguna base de datos: opera sobre TEXTO SQL ya
formado y sobre el frozenset `TABLAS_ANULABLES`, leído del FUENTE de
`services/anulacion.py` vía `ast` -- el mismo mecanismo, sin duplicarlo,
que ya usa `scripts/observador_contrato.py::_tablas_del_bloque_qc`. El
alcance de este analizador nunca puede desincronizarse de la lista real de
tablas anulables: si `TABLAS_ANULABLES` cambia, el alcance cambia solo.
"""
import ast
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ANULACION_PATH = ROOT / "services" / "anulacion.py"

# Las 7 raíces de proceso independientes ([[DP-31]]): tienen soft-delete
# (E7/C2) pero sus lecturas NO están en el alcance de este analizador -- es
# una decisión del físico todavía abierta (52+ sitios sin filtrar), no un
# defecto de PLAN_LECTURA_VIGENTE_18-08 (ver ese plan, §1). Lista literal y
# corta a propósito: que nazca una raíz nueva es un cambio de arquitectura
# deliberado (ha pasado 4 veces en la historia del proyecto: controles,
# TipoCalibracion, LinealidadBraquiterapia, y las 4 diarias como grupo), no
# un evento que este módulo deba inferir solo.
RAICES_FUERA_DE_ALCANCE = frozenset({
    "controles", "TipoCalibracion", "LinealidadBraquiterapia",
    "aceleradorlineal_600", "aceleradorlineal_ix", "halcyon", "braqui",
})


def tablas_anulables():
    """Lee `TABLAS_ANULABLES` de `services/anulacion.py` sin importar el
    módulo (arrastra PyQt5 vía `QSqlQuery`): parsea el AST y extrae los
    literales del `frozenset({...})`. Si esa forma cambia, falla ruidosamente
    en vez de devolver una lista incompleta en silencio -- mismo criterio que
    `observador_contrato.py::_tablas_del_bloque_qc`."""
    arbol = ast.parse(_ANULACION_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and nodo.targets[0].id == "TABLAS_ANULABLES"):
            continue
        llamada = nodo.value
        if not (isinstance(llamada, ast.Call)
                and isinstance(llamada.func, ast.Name)
                and llamada.func.id == "frozenset"
                and len(llamada.args) == 1
                and isinstance(llamada.args[0], ast.Set)):
            raise RuntimeError(
                "TABLAS_ANULABLES ya no es un frozenset({...}) literal en "
                f"{_ANULACION_PATH} -- actualiza tablas_anulables().")
        tablas = set()
        for elt in llamada.args[0].elts:
            if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
                raise RuntimeError(
                    f"Elemento no literal en TABLAS_ANULABLES: {ast.dump(elt)}")
            tablas.add(elt.value)
        return frozenset(tablas)
    raise RuntimeError(f"No se encontró TABLAS_ANULABLES en {_ANULACION_PATH}")


def tablas_hijas_del_bloque_qc():
    """Alcance de este analizador: `TABLAS_ANULABLES` menos las raíces
    ([[DP-31]], fuera de `PLAN_LECTURA_VIGENTE_18-08.md`). Se deriva en cada
    llamada -- nunca una copia guardada -- para que no pueda quedar
    desincronizado del contrato real."""
    return tablas_anulables() - RAICES_FUERA_DE_ALCANCE


@dataclass(frozen=True)
class SinFiltro:
    """Una referencia a una tabla versionada, en un fragmento SQL, sin el
    filtro que distingue el bloque vigente del histórico."""
    tabla: str
    alias: str
    motivo: str  # "sin filtro de activo" | "LIMIT sin ORDER BY"


_RE_FROM_JOIN = re.compile(
    r'\b(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?'
    r'(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?',
    re.IGNORECASE)
_RE_UPDATE = re.compile(r'\bUPDATE\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', re.IGNORECASE)
_RE_LIMIT = re.compile(r'\bLIMIT\b', re.IGNORECASE)
_RE_ORDER_BY = re.compile(r'\bORDER\s+BY\b', re.IGNORECASE)
_RE_SELECT_INICIO = re.compile(r'^\s*SELECT\b', re.IGNORECASE)
_RE_SUBCONSULTA_INICIO = re.compile(r'\(\s*SELECT\b', re.IGNORECASE)

# Palabras reservadas que pueden seguir al nombre de tabla sin ser un alias
# (p.ej. "FROM controles WHERE ..." -- "WHERE" no es alias de "controles").
_PALABRAS_RESERVADAS = {
    "where", "on", "left", "right", "inner", "outer", "cross", "join",
    "order", "group", "limit", "as", "and", "or", "set", "values", "union",
}


def _extraer_subconsultas(sql):
    """Devuelve (texto_exterior, [subconsultas]). Cada `(SELECT ...)` de
    nivel superior se reemplaza en el texto exterior por espacios del mismo
    largo (preserva posiciones, y evita que el análisis exterior confunda
    las tablas de la subconsulta con referencias propias) y se devuelve
    aparte para analizarse de forma independiente -- D2 real: la
    subconsulta necesita SU PROPIO filtro y su propio ORDER BY, que el
    `cm.activo` de la consulta exterior no le presta."""
    subs = []
    texto = sql
    while True:
        m = _RE_SUBCONSULTA_INICIO.search(texto)
        if not m:
            break
        inicio = m.start()
        profundidad = 0
        fin = None
        for i in range(inicio, len(texto)):
            if texto[i] == '(':
                profundidad += 1
            elif texto[i] == ')':
                profundidad -= 1
                if profundidad == 0:
                    fin = i
                    break
        if fin is None:
            break  # paréntesis sin cerrar -- texto no analizable, se abandona
        subs.append(texto[inicio + 1:fin])
        texto = texto[:inicio] + (" " * (fin - inicio + 1)) + texto[fin + 1:]
    return texto, subs


def _tablas_referenciadas(fragmento):
    """(alias_o_tabla -> tabla) para referencias LITERALES de FROM/JOIN/
    UPDATE. Los nombres dinámicos (`{DYN}`, una tabla armada en variable)
    quedan fuera a propósito: esos los sigue vigilando el mecanismo de
    tablas dinámicas que ES1 conserva de LE4, sin tocarlo -- es una forma de
    opacidad distinta (no se sabe qué tabla es) a la que resuelve este
    módulo (se sabe qué tabla es, falta saber si está filtrada)."""
    refs = {}
    for m in _RE_FROM_JOIN.finditer(fragmento):
        tabla = m.group(1)
        alias = m.group(2)
        if alias and alias.lower() in _PALABRAS_RESERVADAS:
            alias = None
        refs[alias if alias else tabla] = tabla
    for m in _RE_UPDATE.finditer(fragmento):
        refs.setdefault(m.group(1), m.group(1))
    return refs


def _tiene_activo_no_calificado(fragmento):
    """Un `activo` genuinamente sin calificar -- NO uno que ya está
    calificado a OTRO alias (p.ej. `cm.activo` no cuenta como filtro de
    `preguntas` solo porque la palabra 'activo' aparece en el texto: hueco
    4 de LE4, el que dejó pasar D1 el 13-08)."""
    for m in re.finditer(r'\bactivo\b', fragmento, re.IGNORECASE):
        precedente = fragmento[:m.start()].rstrip(' \t\n"\'')
        if not precedente.endswith('.'):
            return True
    return False


def _filtro_presente(fragmento, alias, unica_tabla_versionada):
    calificado = re.compile(rf'\b{re.escape(alias)}\s*\.\s*"?activo"?', re.IGNORECASE)
    if calificado.search(fragmento):
        return True
    if unica_tabla_versionada:
        if "{filtro_activo}" in fragmento.lower():
            return True
        if _tiene_activo_no_calificado(fragmento):
            return True
    return False


def _analizar_fragmento(fragmento, tablas_versionadas):
    hallazgos = []
    refs = _tablas_referenciadas(fragmento)
    refs_versionadas = {a: t for a, t in refs.items() if t in tablas_versionadas}
    if not refs_versionadas:
        return hallazgos
    unica = len(refs_versionadas) == 1
    for alias, tabla in refs_versionadas.items():
        if not _filtro_presente(fragmento, alias, unica):
            hallazgos.append(SinFiltro(tabla, alias, "sin filtro de activo"))
    if (_RE_SELECT_INICIO.search(fragmento) and _RE_LIMIT.search(fragmento)
            and not _RE_ORDER_BY.search(fragmento)):
        for alias, tabla in refs_versionadas.items():
            hallazgos.append(SinFiltro(tabla, alias, "LIMIT sin ORDER BY"))
    return hallazgos


def analizar(sql, tablas_versionadas=None):
    """Punto de entrada. `sql`: texto SQL ya formado -- un literal
    reconstruido del AST (con marcadores `{FILTRO_ACTIVO}`/`{DYN}` donde
    aplique) o una cadena ya resuelta en tiempo de ejecución (RT1). Devuelve
    la lista de `SinFiltro` encontrados; vacía si no hay nada que reportar.
    """
    if tablas_versionadas is None:
        tablas_versionadas = tablas_hijas_del_bloque_qc()
    exterior, subconsultas = _extraer_subconsultas(sql)
    hallazgos = _analizar_fragmento(exterior, tablas_versionadas)
    for sub in subconsultas:
        hallazgos = hallazgos + analizar(sub, tablas_versionadas)
    return hallazgos


# ---------------------------------------------------------------------------
# Resolución de SQL armado en una variable local (hueco 1 de LE4).
#
# `execute(query, ...)` con `query` como nombre desnudo es invisible para
# cualquier análisis que solo mire el argumento literal. En vez de tratar
# TODO sitio así como "opaco" (se midió: 106 sitios en el árbol, la enorme
# mayoría CREATE TABLE/INSERT de una sola asignación, irrelevantes para este
# análisis -- una lista blanca de 106 entradas no sería una lista revisable,
# sería ruido), se resuelve el patrón real que aparece en el código: una
# asignación simple, o un if/else que asigna en cada rama seguido de una o
# más concatenaciones (`+=`) compartidas -- exactamente la forma de D1/D2.
#
# Lo que NO se intenta resolver (bucles, `try`, reasignación dentro de
# ellos) se declara irresoluble (`None`) a propósito: es más seguro dejarlo
# opaco y exigir revisión manual que fingir una resolución incorrecta.
# ---------------------------------------------------------------------------

def _literal_str_ast(node):
    """Como el `_literal_str` de LE4 (mismo criterio): reconstruye un
    `Constant` string o `JoinedStr`, marcando cada parte no literal como
    `{FILTRO_ACTIVO}` (llamada a `filtro_activo(...)`) o `{DYN}` (cualquier
    otra cosa). `None` si el nodo no es ninguna de las dos formas."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        partes = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                partes.append(v.value)
                continue
            valor = v.value if isinstance(v, ast.FormattedValue) else v
            if (isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name)
                    and valor.func.id == "filtro_activo"):
                partes.append("{FILTRO_ACTIVO}")
            else:
                partes.append("{DYN}")
        return "".join(partes)
    return None


def _nombre_tocado_dentro(nodo, nombre):
    for sub in ast.walk(nodo):
        if isinstance(sub, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == nombre for t in sub.targets):
            return True
        if isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name) \
                and sub.target.id == nombre:
            return True
    return False


def _rango_lineas(stmt):
    """(primera, última) línea que ocupa `stmt`, incluidos sus
    descendientes -- para decidir si la sentencia objetivo cae DENTRO de
    una rama concreta de un `if`, no solo comparar contra un umbral global
    (que confunde ramas hermanas: ver nota en `_rastrear_variable`)."""
    linenos = [n.lineno for n in ast.walk(stmt) if hasattr(n, "lineno")]
    return min(linenos), max(linenos)


def _contiene_linea(stmt, lineno):
    inicio, fin = _rango_lineas(stmt)
    return inicio <= lineno <= fin


def _rastrear_variable(cuerpo, nombre, valores, antes_de_lineno):
    """Recorre `cuerpo` (lista de sentencias, EN ORDEN DE FUENTE) y devuelve
    (valores_posibles, detenido) -- el conjunto de valores literales
    posibles de `nombre` justo antes de la línea `antes_de_lineno`, y si ya
    se alcanzó ese punto. `None` en el conjunto significa "irresoluble
    desde aquí en adelante". Recursión estructural (si/else), nunca
    `ast.walk` de la función completa -- `ast.walk` es un recorrido en
    anchura que no respeta el orden real de ejecución de las ramas.

    Un `if` se trata de dos formas distintas según si la sentencia objetivo
    cae DENTRO de él o no: si NO cae dentro, es un `if` ya completamente
    ejecutado en el pasado y de rama desconocida -- se procesan las DOS
    ramas COMPLETAS (sin truncar) y se unen los resultados (no se sabe cuál
    se tomó). Si SÍ cae dentro, ese `if` es justo el que decide el camino
    real hacia el objetivo -- solo se desciende a la rama que lo contiene,
    la otra rama NUNCA se ejecutó en este camino y no debe aportar nada.
    Unir siempre las dos ramas sin este distingo produce candidatos
    espurios (mezcla del "antes" de una rama con el "después" de la otra)
    cuando dos `if` hermanos, cada uno con su propio `execute()`, comparten
    la misma variable -- exactamente la forma real de
    `mostrar_controles_mensuales` (load.py:1470-1476)."""
    for stmt in cuerpo:
        if stmt.lineno >= antes_de_lineno and not _contiene_linea(stmt, antes_de_lineno):
            return valores, True
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == nombre:
            valores = {_literal_str_ast(stmt.value)}
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name) \
                and stmt.target.id == nombre and isinstance(stmt.op, ast.Add):
            texto = _literal_str_ast(stmt.value)
            valores = {
                (v + texto) if (v is not None and texto is not None) else None
                for v in valores
            }
        elif isinstance(stmt, ast.If):
            if _contiene_linea(stmt, antes_de_lineno):
                # el objetivo está en ESTA rama -- la otra nunca se ejecutó
                # en este camino, no se explora ni se une.
                if _contiene_linea_en_lista(stmt.body, antes_de_lineno):
                    valores, parado = _rastrear_variable(stmt.body, nombre, valores, antes_de_lineno)
                else:
                    valores, parado = _rastrear_variable(stmt.orelse, nombre, valores, antes_de_lineno)
                if parado:
                    return valores, True
            else:
                # `if` ya resuelto en el pasado, rama desconocida -- las dos
                # ramas se procesan COMPLETAS (sin límite de línea) y se unen.
                v_then, _ = _rastrear_variable(stmt.body, nombre, set(valores), float("inf"))
                if stmt.orelse:
                    v_else, _ = _rastrear_variable(stmt.orelse, nombre, set(valores), float("inf"))
                else:
                    v_else = set(valores)
                valores = v_then | v_else
        elif isinstance(stmt, (ast.For, ast.While, ast.Try, ast.With)):
            if _nombre_tocado_dentro(stmt, nombre):
                valores = {None}
    return valores, False


def _contiene_linea_en_lista(cuerpo, lineno):
    return any(_contiene_linea(s, lineno) for s in cuerpo)


def resolver_argumento_execute(func_node, call_node):
    """Para `call_node` = una llamada `algo.execute(arg0, ...)` cuyo `arg0`
    es un `ast.Name` (no un literal directo), intenta resolver el/los
    valor(es) SQL posibles de esa variable dentro de `func_node`.

    Devuelve una lista de textos (uno solo en el caso común; dos si la
    variable se asignó en un if/else, como en D1/D2) o `None` si la
    construcción es demasiado compleja para resolverse con garantías
    (bucle, `try`, más de una reasignación fuera de un if/else simple) --
    en ese caso el sitio queda genuinamente opaco y debe revisarse a mano.
    """
    arg0 = call_node.args[0]
    if not isinstance(arg0, ast.Name):
        return None
    valores, _ = _rastrear_variable(func_node.body, arg0.id, {""}, call_node.lineno)
    if None in valores or not valores:
        return None
    return sorted(valores)
