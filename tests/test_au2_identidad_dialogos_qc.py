"""AU2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-AU2): tripwire de identidad en los
diálogos "Ver tabla" del bloque de QC.

Origen: rebuild del físico del 19-08. `_dialogo_con_identidad` (A6.2-bis,
`data/ManejoDatos/load.py:23`) propaga la identidad del formulario que abre un
diálogo emergente a las acciones de editar/borrar (`guardarEdicion`,
`verificar_eliminar`) que ese diálogo ofrece. Pero 5 de los 6 sitios que llaman
a `mostrar_controles_mensuales` -- la función que fabrica los botones "Ver
tabla" del mensual -- le pasaban `None` como `parent` en vez de `self`:
`dlg.user_id` quedaba `None`, y cualquier borrado o edición hecho desde ahí
auditaba con `usuario` NULL. AU1 corrigió los 5 sitios.

AU2 cierra la CLASE del defecto, no los 5 sitios: cualquier función nueva que
llegue a `_dialogo_con_identidad` -- directa o transitivamente, reenviando su
propio primer parámetro -- puede sufrir el mismo defecto si algún llamador le
pasa `None` en esa posición.

Cómo se deriva el conjunto (mismo espíritu que AN1/`services/lectura_vigente.py`
-- estructural, no una lista escrita a mano): se parte de la única raíz real,
`_dialogo_con_identidad`, y se expande por punto fijo dentro de cada archivo de
producción -- una función entra al conjunto si reenvía su propio primer
parámetro (posicional, o anidado como `QDialog(parent)`, o por *keyword* con el
nombre del parámetro del destino) a la raíz o a otra función ya identificada.
El nombre del parámetro no se asume `parent`: en `Tablas_Anuales/tablas_anuales.py`
el mismo patrón usa `self` (`crear_ventanas_emergentes_tablas`).

Deliberadamente NO se usa el nombre `mostrar_*` como criterio (habría que
mantenerlo a mano y volvería a divergir, el defecto de origen de este plan
entero -- §2.1 del plan). Tampoco se asume que `mostrar_controles_mensuales` y
`mostrar_controles_anuales` son ambas parte del conjunto solo porque el plan
las nombra como ejemplo: verificado que HOY `mostrar_controles_anuales` no
alcanza `_dialogo_con_identidad` (sus "Ver tabla" abren visores de solo
lectura, sin editar/eliminar) -- si algún día se le conecta un flujo de
edición, el punto fijo la incorpora sola, sin tocar este archivo.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

RAIZ_IDENTIDAD = "_dialogo_con_identidad"


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


def _nombre_llamada(call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _primer_parametro(func_node):
    args = func_node.args.args
    return args[0].arg if args else None


def _contiene_nombre(node, nombre):
    """`nombre` aparece en cualquier parte de `node` -- cubre el caso
    `QDialog(parent)`, donde `parent` no es el argumento directo sino que va
    anidado dentro de otra llamada."""
    return any(isinstance(n, ast.Name) and n.id == nombre for n in ast.walk(node))


def _reenvia(call, nombre_propio, primer_parametro_destino=None):
    """La llamada `call` reenvía la variable `nombre_propio` en la posición
    del primer parámetro del destino: posicional (con anidamiento) o como
    *keyword* nombrado como el primer parámetro del destino."""
    if call.args and _contiene_nombre(call.args[0], nombre_propio):
        return True
    if primer_parametro_destino:
        for kw in call.keywords:
            if (kw.arg == primer_parametro_destino
                    and isinstance(kw.value, ast.Name)
                    and kw.value.id == nombre_propio):
                return True
    return False


def _funciones_dependientes_de_identidad(path):
    """Punto fijo, dentro de UN archivo: qué funciones reenvían su propio
    primer parámetro hasta `_dialogo_con_identidad`. Devuelve
    {nombre_función: nombre_de_su_primer_parámetro}."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            pp = _primer_parametro(node)
            if pp:
                funcs[node.name] = (node, pp)

    dependientes = {}

    def depende(node, pp_propio):
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            fname = _nombre_llamada(call)
            if fname == RAIZ_IDENTIDAD:
                if _reenvia(call, pp_propio):
                    return True
            elif fname in dependientes:
                if _reenvia(call, pp_propio, dependientes[fname]):
                    return True
        return False

    cambio = True
    while cambio:
        cambio = False
        for nombre, (node, pp) in funcs.items():
            if nombre in dependientes:
                continue
            if depende(node, pp):
                dependientes[nombre] = pp
                cambio = True
    return dependientes


def _conjunto_identidad():
    """Unión, sobre todo el árbol de producción, de las funciones que
    alcanzan `_dialogo_con_identidad` reenviando su propio primer parámetro.
    {nombre_función: nombre_del_parámetro_identidad}."""
    total = {}
    for _, path in _archivos_produccion():
        total.update(_funciones_dependientes_de_identidad(path))
    return total


def _sitios_con_none_literal(conjunto_identidad):
    """Recorre TODO el árbol de producción buscando llamadas a una función
    del conjunto donde el argumento en la posición de identidad es un `None`
    literal."""
    hallazgos = []
    for rel, path in _archivos_produccion():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fname = _nombre_llamada(node)
            if fname not in conjunto_identidad:
                continue
            es_none = (node.args and isinstance(node.args[0], ast.Constant)
                       and node.args[0].value is None)
            if not es_none:
                pp_destino = conjunto_identidad[fname]
                for kw in node.keywords:
                    if (kw.arg == pp_destino
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is None):
                        es_none = True
                        break
            if es_none:
                hallazgos.append(f"{rel}:{node.lineno} llama a "
                                  f"'{fname}' con {conjunto_identidad[fname]}=None")
    return hallazgos


def test_conjunto_identidad_incluye_los_sitios_conocidos():
    """El punto fijo debe encontrar, HOY, exactamente las funciones que de
    verdad propagan identidad -- ni más (falsos positivos que generarían
    ruido) ni menos (huecos). Ancla el resultado para que un cambio en el
    grafo de llamadas de estos módulos se note aquí, no en producción."""
    conjunto = _conjunto_identidad()
    assert conjunto == {
        "_mostrar_dialogo": "parent",
        "mostrar_controles_mensuales": "parent",
        "mostrar_equipos": "parent",
        "mostrar_seguridad": "parent",
        "mostrar_tam_campos": "parent",
        "mostrar_analisis_img": "parent",
        "mostrar_dosimetria": "parent",
        "crear_ventanas_emergentes_tablas": "self",
        "mostrar_tablas_anuales_600_ix": "self",
        "mostrar_tablas_anuales_halcyon": "self",
    }, (
        "El conjunto de funciones que propagan identidad hacia "
        "_dialogo_con_identidad cambió. Si es una función NUEVA legítima "
        "(p.ej. mostrar_controles_anuales gana un flujo de editar/eliminar), "
        "actualiza esta lista a mano tras revisar que de verdad reenvía la "
        "identidad correcta -- es la única lista de este archivo que se "
        "mantiene a mano, y existe para que el cambio se note."
    )


def test_ningun_dialogo_con_identidad_recibe_none():
    """AU2: ningún sitio de producción pasa `None` en la posición de
    identidad a una función que alcanza `_dialogo_con_identidad`. Esto es lo
    que AU1 corrigió en los 5 sitios de `mostrar_controles_mensuales`; este
    test cierra la clase entera, no esos 5 sitios."""
    conjunto = _conjunto_identidad()
    hallazgos = _sitios_con_none_literal(conjunto)
    assert not hallazgos, (
        "Sitio(s) que pasan None donde debía ir la identidad del formulario "
        "-- audit_log quedará con usuario NULL en cualquier editar/eliminar "
        "hecho desde ese diálogo:\n" + "\n".join(hallazgos)
    )
