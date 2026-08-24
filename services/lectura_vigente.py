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
_INDICES_PATH = ROOT / "scripts" / "indices_bloque_qc.py"

# Las 7 raíces de proceso independientes del bloque de QC.
#
# Hasta LR4 se llamaba `RAICES_FUERA_DE_ALCANCE` y se RESTABA en
# `tablas_hijas_del_bloque_qc()` para dejar sus lecturas fuera de este
# analizador. Esa resta era el artefacto de que [[DP-31]] siguiera abierta
# -- nunca una decisión de arquitectura -- y es exactamente lo que permitió
# que las raíces llegaran a ~27 lecturas filtrando y ~50 sin filtrar sin
# que ningún tripwire lo viera. [[DA-48]] cerró DP-31 y LR4 retiró la
# resta: el alcance de AN1 es ahora el bloque de QC COMPLETO.
#
# El frozenset NO se vacía ni se borra, porque tenía DOS papeles y solo uno
# se retira. El que queda es el ESTRUCTURAL, y es el original: es el punto
# de partida del cierre transitivo de claves foráneas del bloque de QC
# (`cierre_transitivo_fk`), que usan `scripts/derivar_inventario_qc.py`
# (IV1) y el tripwire IV2. Con el conjunto vacío ese cierre sale vacío, y
# IV2 daría por completo un inventario que no ha mirado nada -- de ahí el
# nombre nuevo: leer "RAICES_FUERA_DE_ALCANCE se retira" invitaba justo a
# ese error.
#
# Lista literal y corta a propósito: que nazca una raíz nueva es un cambio
# de arquitectura deliberado (ha pasado 4 veces en la historia del
# proyecto: controles, TipoCalibracion, LinealidadBraquiterapia, y las 4
# diarias como grupo), no un evento que este módulo deba inferir solo.
RAICES_QC = frozenset({
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


def excepciones_inventario():
    """IV2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV2): lee
    `EXCEPCIONES_INVENTARIO` de `services/anulacion.py` con el mismo criterio
    que `tablas_anulables()` -- AST, sin importar el módulo (PyQt5). Devuelve
    el conjunto de nombres de tabla (las claves), no los motivos: IV2 solo
    necesita saber CUÁLES están clasificadas como excepción, no por qué."""
    arbol = ast.parse(_ANULACION_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and nodo.targets[0].id == "EXCEPCIONES_INVENTARIO"):
            continue
        if not isinstance(nodo.value, ast.Dict):
            raise RuntimeError(
                "EXCEPCIONES_INVENTARIO ya no es un dict literal en "
                f"{_ANULACION_PATH} -- actualiza excepciones_inventario().")
        tablas = set()
        for clave in nodo.value.keys:
            if not (isinstance(clave, ast.Constant) and isinstance(clave.value, str)):
                raise RuntimeError(
                    f"Clave no literal en EXCEPCIONES_INVENTARIO: {ast.dump(clave)}")
            tablas.add(clave.value)
        return frozenset(tablas)
    raise RuntimeError(f"No se encontró EXCEPCIONES_INVENTARIO en {_ANULACION_PATH}")


def cierre_transitivo_fk(con, raices):
    """IV1/IV2 (PLAN_CONTRATO_COMPLETO_19-08.md): todas las tablas alcanzables
    desde `raices` siguiendo claves foráneas HIJO -> PADRE en sentido inverso
    (quién apunta a quién), transitivamente. No incluye las propias raíces.
    Única implementación -- la usan tanto `scripts/derivar_inventario_qc.py`
    (generar el texto para pegar) como el tripwire IV2 (verificar que no hay
    huecos), para que las dos vistas del mismo cierre no puedan divergir entre
    sí por tener cada una su propia copia del algoritmo."""
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'").fetchall()]
    hijos_de = {}
    for tabla in tablas:
        for fk in con.execute(f'PRAGMA foreign_key_list("{tabla}")').fetchall():
            hijos_de.setdefault(fk[2], set()).add(tabla)

    visitados = set()

    def recorrer(padre):
        for hijo in sorted(hijos_de.get(padre, ())):
            if hijo not in visitados:
                visitados.add(hijo)
                recorrer(hijo)

    for raiz in raices:
        recorrer(raiz)
    return visitados


def tablas_pendientes_lf():
    """LF2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF2): las tablas de
    `EXCEPCIONES_INVENTARIO` cuyo motivo empieza con `"PENDIENTE-LF"` --
    las 30 que entraron a `TABLAS_ANULABLES` en MI1, una vez sus lecturas
    ya filtraron. Históricamente NO incluía `equipos_anual` (se retiró en
    MI5, DA-44) ni `posicionamiento_reposicionamiento` (se retiró en EB7,
    DA-50): ninguna de las dos iba a versionar nunca, así que exigirles
    filtro no tenía sentido. Con las dos ya retiradas del esquema,
    `EXCEPCIONES_INVENTARIO` quedó vacío (EB7) -- esta función sigue
    devolviendo `frozenset()` sin cambios, ahora por ausencia total de
    motivos, no por exclusión selectiva. Lee el motivo, no solo la clave
    (a diferencia de `excepciones_inventario()`, que IV2 usa para
    completitud del inventario, no para alcance de lectura)."""
    arbol = ast.parse(_ANULACION_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and nodo.targets[0].id == "EXCEPCIONES_INVENTARIO"):
            continue
        if not isinstance(nodo.value, ast.Dict):
            raise RuntimeError(
                "EXCEPCIONES_INVENTARIO ya no es un dict literal en "
                f"{_ANULACION_PATH} -- actualiza tablas_pendientes_lf().")
        tablas = set()
        for clave, valor in zip(nodo.value.keys, nodo.value.values):
            if not (isinstance(clave, ast.Constant) and isinstance(clave.value, str)):
                raise RuntimeError(
                    f"Clave no literal en EXCEPCIONES_INVENTARIO: {ast.dump(clave)}")
            if not (isinstance(valor, ast.Constant) and isinstance(valor.value, str)):
                raise RuntimeError(
                    f"Motivo no literal en EXCEPCIONES_INVENTARIO: {ast.dump(valor)}")
            if valor.value.startswith("PENDIENTE-LF"):
                tablas.add(clave.value)
        return frozenset(tablas)
    raise RuntimeError(f"No se encontró EXCEPCIONES_INVENTARIO en {_ANULACION_PATH}")


def tablas_del_bloque_qc():
    """Alcance de este analizador: `TABLAS_ANULABLES` MÁS las tablas
    `PENDIENTE-LF` de `EXCEPCIONES_INVENTARIO` ([[LF2]]). **Sin restar
    nada**: desde LR4 ([[DA-48]]) cubre el bloque de QC COMPLETO, raíces
    incluidas -- una lectura nueva sin filtrar sobre `controles` se pone
    roja igual que una sobre `analisis_placa_franjas`. Es el fin de "las
    raíces son especiales", que es lo que dejó llegar a 27/50 sin que nadie
    lo notara.

    Se llamaba `tablas_hijas_del_bloque_qc` mientras las raíces quedaban
    fuera; el nombre se cambió con la resta, porque una función que
    devuelve las raíces y se llama "hijas" es la clase de nombre que dentro
    de seis meses vuelve a hacer creer que hay algo excluido.

    La unión con `tablas_pendientes_lf()` es lo que permite exigir el
    filtro ANTES de que `MI1` amplíe el frozenset de verdad (§4.4 del plan
    del 19-08): sin esto, ES1/RT1 no verían las 30 tablas nuevas hasta
    después de MI1, y quedaría exactamente el mismo hueco que originó el
    plan (una tabla puede tener lecturas sin filtrar durante toda la
    ventana entre 'ya versiona' y 'alguien se acordó de vigilarla'). Se
    deriva en cada llamada -- nunca una copia guardada -- para que no pueda
    quedar desincronizado del contrato real."""
    return tablas_anulables() | tablas_pendientes_lf()


def tablas_con_filtro_no_op():
    """LF3 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF3): las tablas que están en
    el alcance de vigilancia pero para las que `filtro_activo()` devuelve
    HOY la cadena vacía -- es decir, aquellas cuyo filtro existe en el
    FUENTE y no puede existir en el SQL EJECUTADO.

    Por qué hace falta nombrarlas: ES1 y RT1 comparten el criterio
    (`analizar()`) pero observan objetos distintos, y durante la ventana
    LF→MI1 esos dos objetos DIVERGEN por diseño:

      - ES1 mira el FUENTE. Ve `f"... {filtro_activo('pruebas')}"` y lo
        reconstruye como el marcador `{FILTRO_ACTIVO}`: puede comprobar que
        la llamada está escrita, que es exactamente lo que LF1 entrega.
      - RT1 mira el SQL YA RESUELTO. Python ya evaluó `filtro_activo('pruebas')`
        a `""` (porque `pruebas` sigue en `EXCEPCIONES_INVENTARIO`, a la
        espera de MI1), así que el texto ejecutado NO contiene ninguna
        cláusula de `activo` -- y no debe contenerla: la columna todavía no
        existe en el esquema, y el plan (§2.6, §3 regla 4) pide
        explícitamente que LF sea un **no-op observable**, con el SQL
        "idéntico" al de antes.

    Exigirle a RT1 que vea el filtro en estas tablas es pedir algo que solo
    se podría satisfacer escribiendo la cláusula a mano -- rompiendo el
    punto único de LE0 y ejecutando SQL contra una columna inexistente. Por
    eso RT1 DIFIERE su fallo duro sobre ellas (las sigue contando y
    publicando, ver `_rt1_interceptor_sql`), mientras ES1 las cubre entera
    y estáticamente.

    **La resta es lo que hace la excepción auto-cancelable**, y es
    deliberada, no cosmética: en cuanto MI1 mueva una tabla a
    `TABLAS_ANULABLES`, deja de estar aquí y RT1 vuelve a exigirle el filtro
    en el acto -- sin que nadie tenga que acordarse de vaciar una lista. Y
    si MI1 la moviera al frozenset SIN quitarla de `EXCEPCIONES_INVENTARIO`
    (el descuido plausible: IV2 comprueba una UNIÓN, así que una tabla
    duplicada en los dos sitios lo pasa), la resta la saca igual. No hay
    forma de que una tabla que ya versiona siga difiriéndose.
    """
    return tablas_pendientes_lf() - tablas_anulables()


def claves_indice():
    """LF5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF5): lee `CLAVES_INDICE` de
    `scripts/indices_bloque_qc.py` con el mismo criterio AST-only que
    `tablas_anulables()` -- nunca importa el módulo (evita una segunda
    fuente de verdad de "qué columnas forman la clave de bloque de cada
    tabla"). La usa el tercer motivo de `SinFiltro` para distinguir una
    lectura por CLAVE (debe filtrar) de una lectura por IDENTIDAD física
    (no debe): ninguna de las 52 claves declaradas usa `id`/`rowid` como
    columna -- son siempre `ref`, `id_sesion`, `id_energia`, etc."""
    arbol = ast.parse(_INDICES_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and nodo.targets[0].id == "CLAVES_INDICE"):
            continue
        if not isinstance(nodo.value, ast.Dict):
            raise RuntimeError(
                "CLAVES_INDICE ya no es un dict literal en "
                f"{_INDICES_PATH} -- actualiza claves_indice().")
        claves = {}
        for clave, valor in zip(nodo.value.keys, nodo.value.values):
            if not (isinstance(clave, ast.Constant) and isinstance(clave.value, str)):
                raise RuntimeError(
                    f"Clave no literal en CLAVES_INDICE: {ast.dump(clave)}")
            if not isinstance(valor, ast.Tuple):
                raise RuntimeError(
                    f"Valor no es una tupla literal en CLAVES_INDICE "
                    f"({clave.value}): {ast.dump(valor)}")
            columnas = set()
            for elt in valor.elts:
                if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
                    raise RuntimeError(
                        f"Columna no literal en la clave de {clave.value}: "
                        f"{ast.dump(elt)}")
                columnas.add(elt.value)
            claves[clave.value] = frozenset(columnas)
        return claves
    raise RuntimeError(f"No se encontró CLAVES_INDICE en {_INDICES_PATH}")


def tablas_con_filtro_posible():
    """LF5: tablas para las que `filtro_activo()` puede devolver HOY una
    cláusula real -- `TABLAS_ANULABLES` sin más.

    Sigue siendo un alcance distinto al de `tablas_del_bloque_qc()`, aunque
    LR4 haya retirado la exclusión de las raíces: aquel es la UNIÓN con las
    30 tablas `PENDIENTE-LF`, para las que `filtro_activo()` todavía
    devuelve `""`. Preguntar "¿sobra un filtro?" sobre una tabla cuyo
    filtro no puede existir aún no tiene sentido; preguntar "¿falta?" sí
    (ES1 lo ve en el fuente, ver `tablas_con_filtro_no_op`).

    Antes de LR4 la diferencia era además la contraria y más grave: este
    conjunto incluía las 7 raíces a propósito, porque DA-47/LF4 corrigió el
    defecto de "filtro de más" precisamente en una raíz
    (`TipoCalibracion`), invisible entonces para el otro alcance."""
    return tablas_anulables()


@dataclass(frozen=True)
class SinFiltro:
    """Una referencia a una tabla versionada, en un fragmento SQL, sin el
    filtro que distingue el bloque vigente del histórico -- o, para el
    tercer motivo, CON un filtro que no debería estar."""
    tabla: str
    alias: str
    motivo: str  # "sin filtro de activo" | "LIMIT sin ORDER BY" |
                 # "filtro sobre lectura de identidad"


#     `tamaño_pixel` (única tabla del bloque de QC con un carácter no-ASCII en
#     el nombre) no coincidía con `[A-Za-z_][A-Za-z0-9_]*`: el motor de regex
#     paraba en la 'ñ' y capturaba "tama" en silencio -- ni un error, ni una
#     ausencia detectable, un nombre de tabla DISTINTO e inexistente. La
#     tabla quedaba invisible para ES1/RT1 en todos sus sitios de lectura,
#     descubierto al ampliar el alcance en LF2 (PLAN_CONTRATO_COMPLETO_19-08.md
#     §6-LF2). `[^\W\d]` (carácter de palabra que no es dígito) y `\w`
#     coinciden con cualquier letra Unicode -- identificador SQLite válido,
#     no solo ASCII.
_RE_FROM_JOIN = re.compile(
    r'\b(?:FROM|JOIN)\s+"?([^\W\d]\w*)"?'
    r'(?:\s+(?:AS\s+)?([^\W\d]\w*))?',
    re.IGNORECASE)
_RE_UPDATE = re.compile(r'\bUPDATE\s+"?([^\W\d]\w*)"?', re.IGNORECASE)
_RE_LIMIT = re.compile(r'\bLIMIT\b', re.IGNORECASE)
_RE_ORDER_BY = re.compile(r'\bORDER\s+BY\b', re.IGNORECASE)
_RE_WHERE_INICIO = re.compile(r'\bWHERE\b', re.IGNORECASE)
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


def _texto_desde_where(fragmento):
    """Recorta `fragmento` a partir de su primer `WHERE` (vacío si no
    tiene). Las subconsultas ya salieron por `_extraer_subconsultas` antes
    de llegar aquí, así que el primer `WHERE` que queda es el de este
    fragmento -- nunca el de un `(SELECT ...)` anidado."""
    m = _RE_WHERE_INICIO.search(fragmento)
    return fragmento[m.start():] if m else ""


# LR4: la segunda forma de "el predicado nombra UNA fila física" -- la
# tabla entra por un JOIN cuyo PROPIO `ON` iguala su clave primaria a una
# columna de fuera (`JOIN controles c ON c.id = d.ref`). El `ON` se recorta
# hasta el siguiente JOIN/WHERE/GROUP/ORDER/LIMIT para que la condición de
# un JOIN no se le atribuya a otro.
_RE_JOIN_ON = re.compile(
    r'\bJOIN\s+"?([^\W\d]\w*)"?'
    r'(?:\s+(?:AS\s+)?([^\W\d]\w*))?'
    r'\s+ON\s+(.*?)'
    r'(?=\bJOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT\b|$)',
    re.IGNORECASE | re.DOTALL)


def _es_join_de_identidad(fragmento, alias, tabla, claves):
    """¿`alias` entra por un JOIN que la trae POR SU CLAVE PRIMARIA?

    `FROM dosimetriaMen d JOIN controles c ON c.id = d.ref` devuelve UNA
    fila de `controles` por cada fila de `dosimetriaMen`: es una lectura de
    identidad tanto como un `WHERE id = ?`, y filtrarla no elegiría la
    generación vigente del control -- haría desaparecer del informe la fila
    HIJA, que sigue vigente.

    Se exige que el `ON` sea el del JOIN que introduce ESTA tabla, no
    cualquiera de la sentencia. El distingo no es teórico: en
    `FROM controles c LEFT JOIN pruebas p ON p.id_sesion = c.id` aparece
    `c.id` dentro de un `ON`, pero `controles` está en el `FROM` y su
    `WHERE c.equipo = ?` sí es una lectura de bloque -- confundirlas dejaría
    de exigir el filtro en los 10 sitios de `mostrar_controles_*` que hoy
    lo llevan bien.

    Medido al escribirlo: la primera forma existe UNA sola vez en todo el
    árbol de producción (`services/consistencia_dosis.py`). Se resolvió
    aquí, y no con una lista blanca, porque una excepción tendría que
    declararse por separado en ES1 y en RT1 -- dos copias más del mismo
    criterio, que es el defecto de fondo que este módulo existe para evitar
    -- y porque RT1 exige además que sus excepciones estén también en la
    lista de tablas DINÁMICAS de ES1, donde este sitio no encaja.
    """
    clave_bloque = claves.get(tabla)
    if clave_bloque and (clave_bloque & {"id", "rowid"}):
        return False
    for m in _RE_JOIN_ON.finditer(fragmento):
        tabla_join, alias_join, condicion = m.group(1), m.group(2), m.group(3)
        if alias_join and alias_join.lower() in _PALABRAS_RESERVADAS:
            alias_join = None
        if tabla_join != tabla or (alias_join or tabla_join) != alias:
            continue
        if re.search(rf'\b{re.escape(alias)}\s*\.\s*"?(id|rowid)"?\s*=\s*\S+',
                     condicion, re.IGNORECASE):
            return True
    return False


def _es_referencia_de_identidad(fragmento, texto_where, alias, tabla):
    """[[DA-47]] en una sola pregunta: ¿el predicado que trae esta fila la
    nombra por su clave primaria? Las dos formas valen igual -- el `WHERE`
    (`_es_lectura_de_identidad`) y el `ON` del JOIN que la introduce
    (`_es_join_de_identidad`)."""
    claves = claves_indice()
    if texto_where and _es_lectura_de_identidad(texto_where, alias, tabla, claves):
        return True
    return _es_join_de_identidad(fragmento, alias, tabla, claves)


def _es_lectura_de_identidad(texto_where, alias, tabla, claves):
    """LF5 (DA-47): ¿el `WHERE` nombra la fila FÍSICA (`id`/`rowid`) en vez
    de la clave de bloque de `tabla`? Si la clave declarada en
    `CLAVES_INDICE` ya incluye `id`/`rowid` (hoy, ninguna), esta tabla no
    distingue los dos casos y no se marca -- defensivo, no una situación
    real todavía. `texto_where` debe ser SOLO la porción desde `WHERE` en
    adelante (`_texto_desde_where`) -- nunca el fragmento completo: un
    `UPDATE tabla SET activo = 0 WHERE id = ?` (la anulación misma,
    `anular_fila`) tiene "activo" ANTES del WHERE, en el SET, no como
    filtro de lectura -- ver `anular_fila` (services/anulacion.py).

    El valor tras `=` se acepta como `\\S+` (cualquier token sin espacio),
    NO como un `?` literal: `sqlite3.Connection.set_trace_callback` (RT1)
    entrega el SQL con los parámetros YA EXPANDIDOS a su valor literal
    (`sqlite3_expanded_sql`, no el texto preparado) -- `WHERE id = 5`, no
    `WHERE id = ?`. Medido en runtime al verificar este mismo motivo:
    revertir LF4 y ejecutar `addsomething` produce exactamente
    `WHERE id = 5 AND (activo IS NULL OR activo = 1)`. Un patrón anclado a
    `= \\?` nunca habría visto ese texto real -- solo el de ES1/tests, que
    sí usan `?` literal."""
    clave_bloque = claves.get(tabla)
    if clave_bloque and (clave_bloque & {"id", "rowid"}):
        return False
    patron = re.compile(
        rf'\bWHERE\s+(?:{re.escape(alias)}\s*\.\s*)?"?(id|rowid)"?\s*=\s*\S+',
        re.IGNORECASE)
    return bool(patron.search(texto_where))


def _analizar_fragmento(fragmento, tablas_versionadas):
    hallazgos = []
    refs = _tablas_referenciadas(fragmento)
    refs_versionadas = {a: t for a, t in refs.items() if t in tablas_versionadas}
    if refs_versionadas:
        unica = len(refs_versionadas) == 1
        texto_where_frag = _texto_desde_where(fragmento)
        for alias, tabla in refs_versionadas.items():
            if _filtro_presente(fragmento, alias, unica):
                continue
            # LR4 ([[DA-48]]): con las raíces dentro del alcance, este motivo
            # dejaría en rojo las ~20 lecturas por `id` que NO deben filtrar
            # -- exigirles el filtro es exigirles el defecto que LF4
            # corrigió. Es la misma pregunta que el tercer motivo con el
            # signo cambiado: allí sobra el filtro, aquí no falta. La regla
            # se comprueba una sola vez, aquí, en vez de repartirse en listas
            # blancas por ES1 y RT1.
            if _es_referencia_de_identidad(fragmento, texto_where_frag,
                                           alias, tabla):
                continue
            hallazgos.append(SinFiltro(tabla, alias, "sin filtro de activo"))
        if (_RE_SELECT_INICIO.search(fragmento) and _RE_LIMIT.search(fragmento)
                and not _RE_ORDER_BY.search(fragmento)):
            for alias, tabla in refs_versionadas.items():
                hallazgos.append(SinFiltro(tabla, alias, "LIMIT sin ORDER BY"))

    # LF5 (DA-47): alcance PROPIO -- `tablas_con_filtro_posible()` es
    # `TABLAS_ANULABLES` a secas, sin las 30 PENDIENTE-LF cuyo
    # `filtro_activo()` todavía es un no-op: preguntar "¿sobra un filtro?"
    # sobre una tabla cuyo filtro no puede existir aún no tiene sentido.
    # Ver docstring de esa función.
    refs_con_filtro_posible = {a: t for a, t in refs.items()
                                if t in tablas_con_filtro_posible()}
    if refs_con_filtro_posible:
        texto_where = _texto_desde_where(fragmento)
        if texto_where:
            claves = claves_indice()
            unica_identidad = len(refs_con_filtro_posible) == 1
            for alias, tabla in refs_con_filtro_posible.items():
                if (_filtro_presente(texto_where, alias, unica_identidad)
                        and (_es_lectura_de_identidad(texto_where, alias, tabla, claves)
                             or _es_join_de_identidad(fragmento, alias, tabla, claves))):
                    hallazgos.append(
                        SinFiltro(tabla, alias, "filtro sobre lectura de identidad"))
    return hallazgos


def analizar(sql, tablas_versionadas=None):
    """Punto de entrada. `sql`: texto SQL ya formado -- un literal
    reconstruido del AST (con marcadores `{FILTRO_ACTIVO}`/`{DYN}` donde
    aplique) o una cadena ya resuelta en tiempo de ejecución (RT1). Devuelve
    la lista de `SinFiltro` encontrados; vacía si no hay nada que reportar.
    """
    if tablas_versionadas is None:
        tablas_versionadas = tablas_del_bloque_qc()
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


@dataclass(frozen=True)
class EscrituraPeligrosa:
    """EB5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB5): contraparte de
    `SinFiltro` para el lado de ESCRITURA -- un `DELETE FROM` o un `UPDATE
    ... SET <columna de datos>` (no solo `activo`) sobre una tabla del
    bloque de QC. Es el patrón G1/G2 (mutar/borrar el bloque vigente en vez
    de anular e insertar) que toda la Fase 5 existe para eliminar."""
    tabla: str
    motivo: str  # "DELETE" | "UPDATE de columnas de datos"


_RE_TABLA_O_DYN = r'"?(\{DYN\}|[^\W\d]\w*)"?'
_RE_DELETE_TABLA = re.compile(
    r'\bDELETE\s+FROM\s+' + _RE_TABLA_O_DYN, re.IGNORECASE)
_RE_UPDATE_TABLA_SET = re.compile(
    r'\bUPDATE\s+' + _RE_TABLA_O_DYN + r'\s+SET\s+(.*?)(?:\bWHERE\b|$)',
    re.IGNORECASE | re.DOTALL)
_RE_SOLO_ACTIVO = re.compile(r'^"?activo"?\s*=\s*[01]$', re.IGNORECASE)


def _dividir_nivel_superior(texto, separador=","):
    """Divide `texto` por `separador` SOLO fuera de paréntesis -- una
    columna calculada con una función (`strftime('%Y-%m', created_at)`)
    tiene una coma que no separa dos columnas del SET."""
    partes = []
    profundidad = 0
    actual = []
    for ch in texto:
        if ch == "(":
            profundidad += 1
        elif ch == ")":
            profundidad -= 1
        if ch == separador and profundidad == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(ch)
    partes.append("".join(actual))
    return partes


def analizar_escritura(sql, tablas_versionadas=None):
    """Punto de entrada para EB5, hermano de `analizar()` (lectura). `sql`:
    texto ya formado, igual que `analizar()` -- un literal reconstruido del
    AST (con el marcador `{DYN}` donde el nombre de tabla no se pudo
    resolver estáticamente) o una cadena ya resuelta en runtime.

    No intenta clasificar "legítimo" vs "no" -- ninguna heurística sobre el
    WHERE distingue con garantías la edición directa de una celda (A3,
    DA-05/DA-07/DA-08: mecanismo de corrección deliberado, permanente,
    auditado) del patrón G1/G2 (mutar el bloque vigente en cada guardado).
    Igual que ES1 del lado de lectura: se limita a CENSAR todo sitio que
    escriba una columna de datos (cualquiera que no sea `activo`) o borre
    físicamente una tabla del bloque de QC, y el llamador (el test) exige
    que el censo entero encaje con una lista revisada a mano -- un sitio
    nuevo, no revisado, pone el test en rojo."""
    if tablas_versionadas is None:
        tablas_versionadas = tablas_del_bloque_qc()
    hallazgos = []

    for m in _RE_DELETE_TABLA.finditer(sql):
        tabla = m.group(1)
        if tabla == "{DYN}" or tabla in tablas_versionadas:
            hallazgos.append(EscrituraPeligrosa(tabla, "DELETE"))

    for m in _RE_UPDATE_TABLA_SET.finditer(sql):
        tabla, set_clause = m.group(1), m.group(2)
        if not (tabla == "{DYN}" or tabla in tablas_versionadas):
            continue
        columnas = [c.strip() for c in _dividir_nivel_superior(set_clause)]
        if len(columnas) == 1 and _RE_SOLO_ACTIVO.match(columnas[0]):
            continue  # anulación legítima -- UPDATE ... SET activo = 0/1
        hallazgos.append(EscrituraPeligrosa(tabla, "UPDATE de columnas de datos"))

    return hallazgos


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
