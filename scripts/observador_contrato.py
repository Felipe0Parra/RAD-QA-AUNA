"""OB1 (PLAN_CONTRATO_GUARDADO_13-08.md §5): observador secuencial de solo
lectura para el contrato único de guardado del bloque de QC.

Por qué hace falta: cada fase del plan (FG, AV, LE, SA, CL, CT, DO, PR) toca
en algún punto el mecanismo de guardado, y el criterio de terminación (§8)
exige que ninguna tarea cambie lo que el físico ve, salvo las dos que lo
declaran explícitamente (SA1, CT2). Este script es el instrumento pedido
para eso: captura una huella de una BD y compara dos huellas, para que un
cambio no declarado se vea como un fallo del gate, no como un detalle a
discutir a ojo.

No abre ninguna conexión de escritura -- toda apertura usa `mode=ro`. No
importa `services.anulacion` (arrastra PyQt5 al importar `QSqlQuery`): la
lista de tablas del bloque de QC (`TABLAS_ANULABLES`) se extrae con `ast`
del archivo fuente, sin ejecutarlo -- mismo principio que el censo AST de
lecturas del plan (§2.4): no duplicar a mano una lista que ya existe en
forma canónica en otro sitio.

Modo de uso:
    python scripts/observador_contrato.py capturar <ruta.db> --salida snap.json
    python scripts/observador_contrato.py comparar antes.json despues.json \
        [--esperado cambios.json]

Formato de `--esperado` (opcional, solo lo usan las tareas que declaran un
cambio, p.ej. SA1 y CT2):
    {
      "vigente_cambios_esperados": {"<tabla>": ["<ref>", ...]},
      "censo_total_incremento_esperado": ["<tabla>", ...]
    }

`comparar` termina con exit code 0 si no hay ningún cambio no declarado, 1
si lo hay -- pensado para usarse como gate de un commit, no solo como
reporte para leer.
"""
import argparse
import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANULACION_PATH = ROOT / "services" / "anulacion.py"


def _tablas_del_bloque_qc():
    """Lee `TABLAS_ANULABLES` del código fuente sin importar el módulo (que
    arrastra PyQt5) ni ejecutarlo: parsea el árbol sintáctico y extrae los
    literales del `frozenset({...})`. Si ese frozenset dejara de ser un
    literal simple de strings, esto falla ruidosamente en vez de devolver
    una lista incompleta en silencio."""
    arbol = ast.parse(ANULACION_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Assign)
                and len(nodo.targets) == 1
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
                f"{ANULACION_PATH} -- actualiza _tablas_del_bloque_qc() en "
                "vez de asumir la forma vieja.")
        tablas = set()
        for elt in llamada.args[0].elts:
            if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
                raise RuntimeError(
                    "Un elemento de TABLAS_ANULABLES no es un string "
                    f"literal ({ast.dump(elt)}) -- revisa manualmente.")
            tablas.add(elt.value)
        return frozenset(tablas)
    raise RuntimeError(f"No se encontró TABLAS_ANULABLES en {ANULACION_PATH}")


def _tablas_en_alcance():
    # PR1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-PR1): `preguntas` entró a
    # TABLAS_ANULABLES, así que ya no hace falta unirla a mano -- antes de
    # PR1 este observador la vigilaba por fuera de la lista blanca (§1: "las
    # 28 tablas de TABLAS_ANULABLES más `preguntas`") porque el plan la
    # incluía en su alcance antes de que el código la reconociera.
    return sorted(_tablas_del_bloque_qc())


def _uri_solo_lectura(ruta_bd):
    return Path(ruta_bd).resolve().as_uri() + "?mode=ro"


def _md5_archivo(ruta_bd):
    h = hashlib.md5()
    with open(ruta_bd, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _columnas(cur, tabla):
    cur.execute(f'PRAGMA table_info("{tabla}")')
    return [fila[1] for fila in cur.fetchall()]


def _indices(cur, tabla):
    cur.execute(f'PRAGMA index_list("{tabla}")')
    return sorted(fila[1] for fila in cur.fetchall())


def _clave_bloque(columnas):
    """La columna que identifica "el mismo bloque lógico" dentro de una
    tabla: `ref` para las hijas (apunta al control padre); `id` para las
    raíces, donde cada fila ES su propio bloque -- no hay reemplazo por
    reinserción, el soft-delete activa/desactiva la misma fila (DA-34).

    MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1): la rama TAC/Catphan no
    usa `ref` -- `pruebas` (raíz de esa rama, aunque no una de las 7 raíces
    de QC) no tiene ninguna columna `ref` ni `id` (su PK es `id_prueba`,
    AUTOINCREMENT), y sus 10 hijas (`espesor_corte`, `linealidad_ct`, etc.)
    usan `id_prueba` como PK Y como FK 1:1 al mismo tiempo -- exactamente el
    papel que `ref` cumple en el resto del bloque. Descubierto al ejecutar
    MI1: estas 11 tablas pasaron de PENDIENTE-LF (fuera del alcance de este
    observador) a TABLAS_ANULABLES, y `capturar()` reventaba con
    `RuntimeError` en la primera de ellas."""
    if "ref" in columnas:
        return "ref"
    if "id" in columnas:
        return "id"
    if "id_prueba" in columnas:
        return "id_prueba"
    raise RuntimeError(
        f"Tabla sin columna 'ref', 'id' ni 'id_prueba' -- no se puede "
        f"determinar la clave de bloque. Columnas: {columnas}")


def _valor_serializable(valor):
    if isinstance(valor, bytes):
        # Las columnas BLOB (p.ej. `preguntas.imagen`) están fuera del
        # alcance del contrato (§1: "el bloque de imágenes... es un asunto
        # de almacenamiento, no de contrato de guardado"). Se resumen a su
        # propio hash para que el snapshot detecte un cambio sin cargar
        # binarios completos en el JSON.
        return "blob:sha256:" + hashlib.sha256(valor).hexdigest()
    return valor


def _censo_y_vigente(cur, tabla, columnas, renombres=()):
    tiene_activo = "activo" in columnas
    clave = _clave_bloque(columnas)
    columnas_hash = [c for c in columnas if c not in ("id", "activo")]

    cur.execute(f'SELECT COUNT(*) FROM "{tabla}"')
    total = cur.fetchone()[0]

    if tiene_activo:
        cur.execute(
            f'SELECT COUNT(*) FROM "{tabla}" WHERE activo IS NULL OR activo = 1')
        activas = cur.fetchone()[0]
    else:
        activas = total
    anuladas = total - activas

    lista_columnas_hash = ", ".join(f'"{c}"' for c in columnas_hash)
    filtro_where = ' WHERE activo IS NULL OR activo = 1' if tiene_activo else ''
    cur.execute(
        f'SELECT "{clave}", {lista_columnas_hash} FROM "{tabla}"{filtro_where}')
    grupos = {}
    for fila in cur.fetchall():
        ref_valor = "null" if fila[0] is None else str(fila[0])
        fila_dict = {_nombre_canonico(tabla, c, renombres): _valor_serializable(v) for c, v in zip(columnas_hash, fila[1:])}
        grupos.setdefault(ref_valor, []).append(json.dumps(fila_dict, sort_keys=True))

    vigente = {}
    for ref_valor, filas_json in grupos.items():
        filas_json.sort()
        contenido = "\n".join(filas_json)
        vigente[ref_valor] = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    return {"total": total, "activas": activas, "anuladas": anuladas}, vigente


# GI.0b (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, DP-86): un renombrado de columna EN
# SITIO (GI.0: `resolucion_espacial.lp_mm_maximo` -> `lp_cm_maximo`, `resolucion_espacial_
# regiones.lp_mm` -> `lp_cm`) no toca un valor, pero este observador lo veía como
# `<tabla>.<columna> desapareció` (fallo que `--esperado` no puede declarar) y como un cambio
# de huella de TODOS los bloques de la tabla (la huella lleva el nombre de cada columna).
# Medido el 06-10 sobre una copia de `Rebuild_21-09`: 2 fallos residuales y 80 bloques.
# Declarar los 80 bloques con la receta de DP-86 habría dejado sin vigilar un valor alterado
# dentro de ellos. Lo que cuenta como renombrado declarado sale de UNA fuente: la misma
# constante con la que la app renombra (`RENOMBRES_DE_COLUMNAS`, leída por AST como
# `TABLAS_ANULABLES`). Nada de esto se escribe antes de `_censo_y_vigente`: sus tres
# `execute` están citados por número de línea en dos censos (Trampa 5).
CONEXION_PATH = ROOT / "data" / "ManejoDatos" / "conection.py"
LINEA_RENOMBRADO = ("[esquema] columna renombrada {tabla}.{vieja} -> {nueva} "
                    "(declarada en RENOMBRES_DE_COLUMNAS de conection.py)")
# 1: huellas con el nombre real de cada columna. 2 (GI.0b): con el nombre canónico de los
# renombrados declarados. Dos fotos solo se comparan si las tomó la misma versión con la
# misma lista de renombrados: si no, las huellas difieren por el instrumento, no por la base.
VERSION_OBSERVADOR = 2


def _renombres_declarados():
    """Lee `RENOMBRES_DE_COLUMNAS` de `conection.py` sin importar el módulo (arrastra
    PyQt5 y abre la base al instanciar `Conexion`) ni ejecutarlo: parsea el árbol
    sintáctico y extrae la tupla de tuplas `(tabla, vieja, nueva)` -- el mismo
    principio que `_tablas_del_bloque_qc()`. Si dejara de ser un literal simple de
    tuplas de tres strings, esto falla ruidosamente en vez de devolver una lista
    incompleta en silencio."""
    arbol = ast.parse(CONEXION_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Assign)
                and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and nodo.targets[0].id == "RENOMBRES_DE_COLUMNAS"):
            continue
        if not isinstance(nodo.value, (ast.Tuple, ast.List)):
            raise RuntimeError(
                "RENOMBRES_DE_COLUMNAS ya no es una tupla literal en "
                f"{CONEXION_PATH} -- actualiza _renombres_declarados() en vez de "
                "asumir la forma vieja.")
        renombres = []
        for elt in nodo.value.elts:
            if not (isinstance(elt, ast.Tuple) and len(elt.elts) == 3
                    and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                            for e in elt.elts)):
                raise RuntimeError(
                    "Un elemento de RENOMBRES_DE_COLUMNAS no es una tupla de tres "
                    f"strings literales ({ast.dump(elt)}) -- revisa manualmente.")
            renombres.append(tuple(e.value for e in elt.elts))
        _validar_renombres(renombres)
        return tuple(renombres)
    raise RuntimeError(f"No se encontró RENOMBRES_DE_COLUMNAS en {CONEXION_PATH}")


# Columnas de clave de bloque y de vigencia: la huella y el censo las tratan por su nombre
# (`_clave_bloque`, `tiene_activo`), así que un renombrado declarado sobre ellas no se
# podría seguir; se rechaza al leer la lista, no al comparar (H5 de la revisión de GI.0b).
CLAVES_NO_RENOMBRABLES = frozenset({"id", "activo", "ref", "id_prueba"})


def _validar_renombres(renombres):
    """Una lista con la que la huella no sabría qué hacer se rechaza ruidosamente: un
    renombrado que no renombra, uno repetido, uno encadenado (el nuevo de uno es el viejo
    de otro: `_nombre_canonico` no sigue cadenas), dos que desembocan en el mismo nombre
    (colisión de claves en la huella) o uno sobre una columna de clave o de vigencia."""
    vistas, destinos = set(), set()
    for tabla, vieja, nueva in renombres:
        v, n = vieja.lower(), nueva.lower()
        if v == n:
            raise RuntimeError(f"RENOMBRES_DE_COLUMNAS: {tabla}.{vieja} -> {nueva} no renombra nada")
        if v in CLAVES_NO_RENOMBRABLES or n in CLAVES_NO_RENOMBRABLES:
            raise RuntimeError(
                f"RENOMBRES_DE_COLUMNAS: {tabla}.{vieja} -> {nueva} toca una columna de clave o de "
                f"vigencia ({sorted(CLAVES_NO_RENOMBRABLES)}), que la huella sigue por su nombre")
        if (tabla, v) in vistas:
            raise RuntimeError(f"RENOMBRES_DE_COLUMNAS: {tabla}.{vieja} declarada dos veces")
        if (tabla, n) in destinos:
            raise RuntimeError(
                f"RENOMBRES_DE_COLUMNAS: dos renombrados de '{tabla}' desembocan en {nueva}")
        vistas.add((tabla, v))
        destinos.add((tabla, n))
    encadenados = sorted(vistas & destinos)
    if encadenados:
        raise RuntimeError(
            "RENOMBRES_DE_COLUMNAS: renombrados encadenados (el nombre nuevo de uno es el viejo "
            f"de otro): {encadenados}; declare el salto completo (viejo -> último)")


def _nombre_canonico(tabla, columna, renombres):
    """El nombre bajo el que se hashea una columna: el NUEVO de un renombrado declarado
    para esa tabla, venga la columna con el nombre viejo o con el nuevo y en cualquier
    capitalización (SQLite compara los nombres de columna sin distinguir mayúsculas);
    cualquier otra columna, tal cual. Así la huella de un bloque es la misma antes y
    después del renombrado, y un valor alterado dentro de él se sigue viendo."""
    for t, vieja, nueva in renombres:
        if t == tabla and columna.lower() in (vieja.lower(), nueva.lower()):
            return nueva
    return columna


def _destino_declarado(tabla, columna, renombres):
    """`nueva` si `columna` es el nombre VIEJO de un renombrado declarado para `tabla`;
    si no, None."""
    for t, vieja, nueva in renombres:
        if t == tabla and columna.lower() == vieja.lower():
            return nueva
    return None


def capturar(ruta_bd, tolerar_tablas_ausentes=False):
    """Foto de solo lectura de la base. `tolerar_tablas_ausentes` (GI.0b, H2 de la
    revisión): la foto de ANTES del rebuild se toma sobre la copia cruda de producción, y
    las tablas del contrato que la app nueva crea al abrir todavía no existen; con la
    opción se anotan en `tablas_ausentes` y se omiten (`comparar` las verá como «tabla
    nueva», informativo). Por omisión sigue siendo un error: no se captura una línea base
    incompleta en silencio."""
    con = sqlite3.connect(_uri_solo_lectura(ruta_bd), uri=True)
    cur = con.cursor()
    renombres = _renombres_declarados()

    resultado = {
        "observador": {
            "version": VERSION_OBSERVADOR,
            "renombres_declarados": [list(r) for r in renombres],
        },
        "bd": {
            "ruta": str(Path(ruta_bd).resolve()),
            "md5": _md5_archivo(ruta_bd),
            "page_count": cur.execute("PRAGMA page_count").fetchone()[0],
        },
        "esquema": {},
        "indices": {},
        "censo": {},
        "vigente": {},
        "integridad": {},
        # GI.0b: [tabla, nombre real, nombre canónico] de cada columna hasheada bajo otro
        # nombre en ESTA foto (vacío cuando la base ya tiene los nombres nuevos).
        "renombres_aplicados": [],
        # GI.0b: tablas del contrato que no existían al tomar la foto (solo con
        # `tolerar_tablas_ausentes`; si no, su ausencia es un error).
        "tablas_ausentes": [],
    }

    for tabla in _tablas_en_alcance():
        columnas = _columnas(cur, tabla)
        if not columnas:
            if tolerar_tablas_ausentes:
                resultado["tablas_ausentes"].append(tabla)
                print(f"AVISO: la tabla '{tabla}' del contrato no existe en {ruta_bd}: la foto "
                      "la omite (--tolerar-tablas-ausentes).", file=sys.stderr)
                continue
            raise RuntimeError(
                f"La tabla '{tabla}' (esperada por TABLAS_ANULABLES/alcance "
                f"del plan) no existe en {ruta_bd}. No se captura una línea "
                "base incompleta en silencio.")
        canonicas = [_nombre_canonico(tabla, c, renombres) for c in columnas]
        if len(set(canonicas)) != len(canonicas):
            # H1 de la revisión de GI.0b: con el nombre viejo Y el nuevo presentes a la vez
            # (el caso que GI.0 deja sin tocar: «existen las dos columnas»), las dos caerían
            # bajo una sola clave de la huella y la que perdiera la clave quedaría CIEGA: un
            # valor alterado en ella daría luz verde. Medido: alterar `lp_cm` con `lp_mm` al
            # lado -> 0 fallos.
            repetidas = sorted({c for c in canonicas if canonicas.count(c) > 1})
            raise RuntimeError(
                f"La tabla '{tabla}' de {ruta_bd} tiene a la vez el nombre viejo y el nuevo "
                f"de una columna renombrada ({repetidas}; columnas reales: {columnas}): la "
                "huella no puede vigilar las dos bajo un solo nombre. Resuelva las dos "
                "columnas antes de capturar. No se captura una línea base ciega en silencio.")
        resultado["esquema"][tabla] = columnas          # los nombres REALES: el esquema dice la verdad
        resultado["indices"][tabla] = _indices(cur, tabla)
        censo, vigente = _censo_y_vigente(cur, tabla, columnas, renombres)
        resultado["censo"][tabla] = censo
        resultado["vigente"][tabla] = vigente
        for columna, canonica in zip(columnas, canonicas):
            if canonica != columna:
                resultado["renombres_aplicados"].append([tabla, columna, canonica])

    integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
    fk_count = len(cur.execute("PRAGMA foreign_key_check").fetchall())
    resultado["integridad"] = {
        "integrity_check": integrity,
        "foreign_key_check": fk_count,
    }

    con.close()
    return resultado


def _reportar_capturar(args):
    snapshot = capturar(args.ruta_bd, tolerar_tablas_ausentes=args.tolerar_tablas_ausentes)
    texto = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)
    if args.salida:
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
        print(f"Snapshot escrito en {args.salida}")
    else:
        print(texto)
    return 0


def _cargar(ruta_json):
    return json.loads(Path(ruta_json).read_text(encoding="utf-8"))


def comparar(antes, despues, esperado=None, renombres=None):
    """(fallos, info) entre dos fotos de `capturar`. GI.0b: una columna que desaparece
    de `antes` y cuyo destino declarado en `RENOMBRES_DE_COLUMNAS` (`renombres`, por
    omisión la lista real) aparece en `despues` SIN haber existido antes es un
    renombrado (informativo); cualquier otra desaparición sigue siendo fallo. Las
    huellas de los bloques ya vienen canónicas de `capturar`, así que un renombrado no
    las cambia y un valor alterado dentro de una tabla renombrada sí."""
    esperado = esperado or {}
    if renombres is None:
        # H3 de la revisión de GI.0b: la lista que manda es la que registran las fotos (con
        # ella se hashearon), no la del árbol en el momento de comparar; el árbol solo si la
        # foto es de una versión sin registro.
        registrados = (antes.get("observador") or {}).get("renombres_declarados")
        renombres = (tuple(tuple(r) for r in registrados) if registrados is not None
                     else _renombres_declarados())
    vigente_esperado = esperado.get("vigente_cambios_esperados", {})
    total_incremento_esperado = set(esperado.get("censo_total_incremento_esperado", []))

    fallos = []
    info = []

    if antes.get("observador") != despues.get("observador"):
        fallos.append(
            "[observador] las dos instantáneas no las tomó la misma versión del "
            f"observador ({antes.get('observador')} frente a {despues.get('observador')}): "
            "vuelva a capturar las dos con esta versión")
        return fallos, info   # lo demás sería ruido del instrumento, no de la base (H4)

    tablas = sorted(set(antes["esquema"]) | set(despues["esquema"]))
    for tabla in tablas:
        if tabla not in despues["esquema"]:
            fallos.append(f"[esquema] tabla '{tabla}' desapareció")
            continue
        if tabla not in antes["esquema"]:
            info.append(f"[esquema] tabla nueva '{tabla}'")
            continue

        cols_antes, cols_despues = set(antes["esquema"][tabla]), set(despues["esquema"][tabla])
        bajas_antes = {c.lower() for c in cols_antes}
        bajas_despues = {c.lower() for c in cols_despues}
        renombradas = set()   # destinos (en minúsculas) ya explicados por un renombrado declarado
        for col in sorted(cols_antes - cols_despues):
            destino = _destino_declarado(tabla, col, renombres)
            if (destino is not None and destino.lower() in bajas_despues
                    and destino.lower() not in bajas_antes):
                info.append(LINEA_RENOMBRADO.format(tabla=tabla, vieja=col, nueva=destino))
                renombradas.add(destino.lower())
                continue
            fallos.append(f"[esquema] {tabla}.{col} desapareció")
        for col in sorted(cols_despues - cols_antes):
            if col.lower() in renombradas:
                continue
            info.append(f"[esquema] columna nueva {tabla}.{col}")

        idx_antes, idx_despues = set(antes["indices"].get(tabla, [])), set(despues["indices"].get(tabla, []))
        for idx in sorted(idx_antes - idx_despues):
            fallos.append(f"[indices] {tabla}: índice '{idx}' desapareció")
        for idx in sorted(idx_despues - idx_antes):
            info.append(f"[indices] {tabla}: índice nuevo '{idx}'")

        censo_antes = antes["censo"].get(tabla, {})
        censo_despues = despues["censo"].get(tabla, {})
        total_antes = censo_antes.get("total")
        total_despues = censo_despues.get("total")
        if total_antes is not None and total_despues is not None:
            if total_despues < total_antes:
                fallos.append(
                    f"[censo] {tabla}: total bajó de {total_antes} a "
                    f"{total_despues} -- se perdió una fila de registro clínico")
            elif total_despues > total_antes:
                mensaje = (f"[censo] {tabla}: total subió de {total_antes} a "
                           f"{total_despues}")
                if tabla in total_incremento_esperado:
                    info.append(mensaje + " (declarado)")
                else:
                    fallos.append(mensaje + " (no declarado)")

        vigente_antes = antes["vigente"].get(tabla, {})
        vigente_despues = despues["vigente"].get(tabla, {})
        refs = sorted(set(vigente_antes) | set(vigente_despues))
        refs_esperados = set(vigente_esperado.get(tabla, []))
        for ref in refs:
            h_antes = vigente_antes.get(ref)
            h_despues = vigente_despues.get(ref)
            if h_antes == h_despues:
                continue
            declarado = ref in refs_esperados
            if h_antes is None:
                descripcion = f"[vigente] {tabla} ref={ref}: aparece"
            elif h_despues is None:
                descripcion = f"[vigente] {tabla} ref={ref}: desaparece"
            else:
                descripcion = f"[vigente] {tabla} ref={ref}: cambia"
            (info if declarado else fallos).append(
                descripcion + (" (declarado)" if declarado else " (NO declarado)"))

    integ_antes = antes.get("integridad", {})
    integ_despues = despues.get("integridad", {})
    if integ_despues.get("integrity_check") != "ok":
        fallos.append(
            f"[integridad] integrity_check = {integ_despues.get('integrity_check')!r}")
    fk_antes = integ_antes.get("foreign_key_check", 0)
    fk_despues = integ_despues.get("foreign_key_check", 0)
    if fk_despues > fk_antes:
        fallos.append(
            f"[integridad] foreign_key_check subió de {fk_antes} a {fk_despues}")
    elif fk_despues < fk_antes:
        info.append(
            f"[integridad] foreign_key_check bajó de {fk_antes} a {fk_despues}")

    return fallos, info


def _reportar_comparar(args):
    antes = _cargar(args.antes)
    despues = _cargar(args.despues)
    esperado = _cargar(args.esperado) if args.esperado else None

    fallos, info = comparar(antes, despues, esperado)

    if info:
        print("Cambios declarados / informativos:")
        for linea in info:
            print(f"  - {linea}")
    if fallos:
        print("FALLOS -- cambios no declarados:")
        for linea in fallos:
            print(f"  - {linea}")
        print(f"\n{len(fallos)} fallo(s). El observador NO da luz verde.")
        return 1

    print("OK -- sin cambios no declarados." if not info
          else "OK -- todos los cambios están declarados.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="modo", required=True)

    p_capturar = sub.add_parser("capturar", help="Captura un snapshot de una BD")
    p_capturar.add_argument("ruta_bd")
    p_capturar.add_argument("--salida", help="Archivo de salida (por defecto, stdout)")
    p_capturar.add_argument(
        "--tolerar-tablas-ausentes", action="store_true",
        help="GI.0b: para la foto de ANTES de un rebuild sobre la copia cruda de producción "
             "(las tablas que la app nueva crea al abrir aún no existen): se anotan en "
             "`tablas_ausentes` y se omiten en vez de abortar")
    p_capturar.set_defaults(func=_reportar_capturar)

    p_comparar = sub.add_parser("comparar", help="Compara dos snapshots")
    p_comparar.add_argument("antes")
    p_comparar.add_argument("despues")
    p_comparar.add_argument("--esperado", help="JSON con los cambios declarados")
    p_comparar.set_defaults(func=_reportar_comparar)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
