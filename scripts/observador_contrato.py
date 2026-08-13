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

# `preguntas` no está en TABLAS_ANULABLES (no tiene ruta de borrado
# alcanzable desde la interfaz todavía -- ver docstring de anulacion.py)
# pero SÍ está dentro del alcance de este plan (§1: "las 28 tablas de
# TABLAS_ANULABLES más `preguntas`"), como preparación para PR1.
TABLA_EXTRA_FUERA_DE_LISTA_BLANCA = "preguntas"


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
    return sorted(_tablas_del_bloque_qc() | {TABLA_EXTRA_FUERA_DE_LISTA_BLANCA})


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
    reinserción, el soft-delete activa/desactiva la misma fila (DA-34)."""
    if "ref" in columnas:
        return "ref"
    if "id" in columnas:
        return "id"
    raise RuntimeError(
        f"Tabla sin columna 'ref' ni 'id' -- no se puede determinar la "
        f"clave de bloque. Columnas: {columnas}")


def _valor_serializable(valor):
    if isinstance(valor, bytes):
        # Las columnas BLOB (p.ej. `preguntas.imagen`) están fuera del
        # alcance del contrato (§1: "el bloque de imágenes... es un asunto
        # de almacenamiento, no de contrato de guardado"). Se resumen a su
        # propio hash para que el snapshot detecte un cambio sin cargar
        # binarios completos en el JSON.
        return "blob:sha256:" + hashlib.sha256(valor).hexdigest()
    return valor


def _censo_y_vigente(cur, tabla, columnas):
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
        fila_dict = {c: _valor_serializable(v) for c, v in zip(columnas_hash, fila[1:])}
        grupos.setdefault(ref_valor, []).append(json.dumps(fila_dict, sort_keys=True))

    vigente = {}
    for ref_valor, filas_json in grupos.items():
        filas_json.sort()
        contenido = "\n".join(filas_json)
        vigente[ref_valor] = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    return {"total": total, "activas": activas, "anuladas": anuladas}, vigente


def capturar(ruta_bd):
    con = sqlite3.connect(_uri_solo_lectura(ruta_bd), uri=True)
    cur = con.cursor()

    resultado = {
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
    }

    for tabla in _tablas_en_alcance():
        columnas = _columnas(cur, tabla)
        if not columnas:
            raise RuntimeError(
                f"La tabla '{tabla}' (esperada por TABLAS_ANULABLES/alcance "
                f"del plan) no existe en {ruta_bd}. No se captura una línea "
                "base incompleta en silencio.")
        resultado["esquema"][tabla] = columnas
        resultado["indices"][tabla] = _indices(cur, tabla)
        censo, vigente = _censo_y_vigente(cur, tabla, columnas)
        resultado["censo"][tabla] = censo
        resultado["vigente"][tabla] = vigente

    integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
    fk_count = len(cur.execute("PRAGMA foreign_key_check").fetchall())
    resultado["integridad"] = {
        "integrity_check": integrity,
        "foreign_key_check": fk_count,
    }

    con.close()
    return resultado


def _reportar_capturar(args):
    snapshot = capturar(args.ruta_bd)
    texto = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)
    if args.salida:
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
        print(f"Snapshot escrito en {args.salida}")
    else:
        print(texto)
    return 0


def _cargar(ruta_json):
    return json.loads(Path(ruta_json).read_text(encoding="utf-8"))


def comparar(antes, despues, esperado=None):
    esperado = esperado or {}
    vigente_esperado = esperado.get("vigente_cambios_esperados", {})
    total_incremento_esperado = set(esperado.get("censo_total_incremento_esperado", []))

    fallos = []
    info = []

    tablas = sorted(set(antes["esquema"]) | set(despues["esquema"]))
    for tabla in tablas:
        if tabla not in despues["esquema"]:
            fallos.append(f"[esquema] tabla '{tabla}' desapareció")
            continue
        if tabla not in antes["esquema"]:
            info.append(f"[esquema] tabla nueva '{tabla}'")
            continue

        cols_antes, cols_despues = set(antes["esquema"][tabla]), set(despues["esquema"][tabla])
        for col in sorted(cols_antes - cols_despues):
            fallos.append(f"[esquema] {tabla}.{col} desapareció")
        for col in sorted(cols_despues - cols_antes):
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
