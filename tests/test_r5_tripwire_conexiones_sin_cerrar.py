"""R5 (PLAN_FUGA_CONEXIONES_01-09.md §3-P7/§4): tripwire censal permanente
-- sin él, "el sitio 108 repite la historia" (DP-67/DP-71).

Contraparte, para la fuga de conexiones, de `test_lr1_censo_raices_qc.py`/
`test_le4_lecturas_filtran_activo.py`/`test_eb5_tripwire_escritura.py`
(mismo mecanismo: censo AST exhaustivo del árbol de producción, comparado
contra una lista blanca revisada a mano).

Dos frentes, cada uno con su propia lista blanca -- L1 (PLAN_CIERRE_
LECTURAS_02-09.md) añadió el segundo sin tocar el primero:

**Frente de ESCRITURA** (el original, R5): para cada función de producción
que ESCRIBE (contiene, en su propio texto fuente, `INSERT`/`UPDATE`/
`DELETE`, o -- lección de M3, DP-71 -- `COMMIT`/`ROLLBACK`/`BEGIN
TRANSACTION` como texto SQL crudo, no solo `conn.commit()`), se busca una
asignación PELADA (`conn = Conexion().conectar()` o `conn = algo.
obtener_conexion()`, directa o en un ternario) que NO esté envuelta en un
`with`. Lista blanca `SITIOS_REVISADOS`, hoy VACÍA a propósito: A1-A8/M1-M3/
B10-B17 (PLAN_FUGA_CONEXIONES_01-09.md) convirtieron los únicos sitios que
escribían sin cerrar. Clave `(archivo, línea, función)` -- sujeta a la
Trampa 5 si la lista deja de estar vacía.

**Frente de LECTURA** (`L1`, 02-09): mismo censo AST, pero para funciones que
NO escriben, con el mismo criterio de asignación pelada. Lista blanca
`SITIOS_LECTURA_REVISADOS`, hoy con **47** entradas -- las que el propio
censo ya declaraba como deuda de bajo riesgo (`DP-71`/`DP-76`) antes de que
`R5` pudiera vigilarlas. Clave **`(archivo, función)`**, sin línea --
[medido, PLAN_CIERRE_LECTURAS_02-09.md §5.4] las 47 dan 47 claves distintas
(ninguna función tiene dos asignaciones peladas), así que la clave es única
y **inmune a la Trampa 5**: reindentar o insertar código en cualquiera de
esos archivos no la rompe. Un sitio de lectura nuevo (no en la lista) SÍ
hace fallar la suite -- así se cierra el hueco que R5 dejaba documentado
como "uno nuevo no bloquea a nadie".

Lo que NINGÚN frente cubre (documentado, no un hueco silencioso):
- `services/db_pool.py::obtener_conexion` misma (la fachada): por diseño
  ENTREGA la conexión al llamador -- excluida a propósito (R4, DP-71).
- Un `with` cuyo `__exit__` no cierre de verdad (eso es responsabilidad
  de `_ConexionUnaVez`, ya fijado por su propio test, R1)."""
import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

_RE_ESCRITURA = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|BEGIN\s+TRANSACTION|"
    r'"COMMIT"|\'COMMIT\'|"ROLLBACK"|\'ROLLBACK\')',
    re.IGNORECASE,
)

# services/db_pool.py::DatabaseManager.obtener_conexion es la fachada que
# ENTREGA la conexión al llamador -- por diseño no puede cerrar lo que
# devuelve (R4, DP-71). Es la ÚNICA excepción estructural: no es un sitio
# que "olvidó" envolver su conexión, es lo que hace posible que sus 22
# llamadores (ya todos revisados: A-sitios y M-sitios con with, B-sitios
# de solo lectura documentados) puedan hacerlo.
SITIOS_PERMITIDOS = {
    ("services/db_pool.py", "obtener_conexion"),
}


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


def _es_llamada_conectar(node):
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    return isinstance(fn, ast.Attribute) and fn.attr in ("conectar", "obtener_conexion")


def _contiene_llamada_conectar(node):
    """True si `node` (el `value` de una asignación) ES la llamada, o la
    CONTIENE -- el caso del ternario `X if cond else Y` que B5-B7 usan."""
    return any(_es_llamada_conectar(n) for n in ast.walk(node))


def _nombres_con_target_en_with(func_node):
    """Nombres de variable que en ALGÚN punto de esta función son el
    context_expr de un `with` (directo, o vía el propio Name) -- para no
    marcar como "pelada" una asignación intermedia (`_gestor_conn = ...`)
    que sí se abre con `with` dos líneas después."""
    nombres = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if isinstance(expr, ast.Name):
                    nombres.add(expr.id)
                elif _contiene_llamada_conectar(expr):
                    # el propio with envuelve la llamada directamente --
                    # no hay variable intermedia que registrar aquí.
                    pass
    return nombres


def _nombre_cerrado_en_finally(nombre, cuerpo_try):
    """True si algún `finally:` DENTRO de este cuerpo de `try` (buscando
    recursivamente, para tolerar un try/except anidado dentro del
    mismo try externo) llama `<nombre>.close()` en cualquier parte de su
    bloque -- el patrón real que T7/EB2d/etc. usan en vez de `with`
    (`finally: conn.close()`, a veces con una guarda `if conn:` o
    `if 'conn' in locals():` alrededor)."""
    for node in ast.walk(cuerpo_try):
        if not isinstance(node, ast.Try):
            continue
        for stmt in node.finalbody:
            for sub in ast.walk(stmt):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "close"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == nombre):
                    return True
    return False


def _asignacion_pelada_de_conexion(func_node):
    """Sitios `conn = Conexion().conectar()` / `conn = algo.
    obtener_conexion()` (directos o en ternario) que NO están, ellos
    mismos, envueltos en un `with`, NI resueltos después vía una variable
    intermedia que sí lo esté, NI cerrados por un `finally: <nombre>.
    close()` en algún try que los contenga (patrón EB2d/T7, tan válido
    como el `with` -- R5 solo exige que SE CIERRE en todos los caminos,
    no que sea con `with` específicamente)."""
    nombres_protegidos = _nombres_con_target_en_with(func_node)
    hallados = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Assign):
            continue
        if not _contiene_llamada_conectar(node.value):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        nombre = node.targets[0].id
        if nombre in nombres_protegidos:
            continue
        if _nombre_cerrado_en_finally(nombre, func_node):
            continue
        hallados.append(node.lineno)
    return hallados


def _censar():
    hallazgos = set()
    for rel, path in _archivos_produccion():
        try:
            texto = path.read_text(encoding="utf-8")
            tree = ast.parse(texto, filename=str(path))
        except Exception:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (str(rel), func.name) in SITIOS_PERMITIDOS:
                continue
            fuente_func = ast.get_source_segment(texto, func) or ""
            if not _RE_ESCRITURA.search(fuente_func):
                continue  # esta función no escribe -- fuera del alcance de R5 (P1)
            for lineno in _asignacion_pelada_de_conexion(func):
                hallazgos.add((str(rel), lineno, func.name))
    return hallazgos


def _censar_lectura():
    """L1 (PLAN_CIERRE_LECTURAS_02-09.md §5.4): mismo recorrido que `_censar()`,
    pero para funciones que NO escriben -- el frente que R5 dejaba fuera a
    propósito. Clave `(archivo, función)`, sin línea (ver docstring del
    módulo: es deliberado, no un descuido -- hace la lista inmune a la
    Trampa 5)."""
    hallazgos = set()
    for rel, path in _archivos_produccion():
        try:
            texto = path.read_text(encoding="utf-8")
            tree = ast.parse(texto, filename=str(path))
        except Exception:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (str(rel), func.name) in SITIOS_PERMITIDOS:
                continue
            fuente_func = ast.get_source_segment(texto, func) or ""
            if _RE_ESCRITURA.search(fuente_func):
                continue  # esta función escribe -- la cubre el frente de arriba
            if _asignacion_pelada_de_conexion(func):
                hallazgos.add((str(rel), func.name))
    return hallazgos


# Lista blanca revisada a mano -- HOY VACÍA a propósito: A1-A8/M1-M3/
# B10-B17 (PLAN_FUGA_CONEXIONES_01-09.md) convirtieron todos los sitios
# conocidos que escribían sin cerrar. Un sitio nuevo aquí es SIEMPRE una
# regresión real -- no hay ninguna razón legítima documentada todavía
# para que exista uno.
SITIOS_REVISADOS = set()


def test_ninguna_funcion_que_escribe_deja_una_conexion_pelada():
    encontrados = _censar()
    nuevos = encontrados - SITIOS_REVISADOS
    assert not nuevos, (
        "Función que ESCRIBE (INSERT/UPDATE/DELETE, o COMMIT/ROLLBACK/"
        "BEGIN TRANSACTION como texto SQL crudo) con una conexión pelada "
        "(`conn = Conexion().conectar()` o `conn = algo.obtener_conexion()`) "
        "que no está envuelta en un `with` -- el patrón exacto que "
        "PLAN_FUGA_CONEXIONES_01-09.md cerró en A1-A8/M1-M3/B10-B17. "
        "Conviértela con `with Conexion().conectar() as conn:` (P3 de ese "
        "plan) o, si de verdad hay una razón para no hacerlo, añádela a "
        f"SITIOS_REVISADOS con esa razón: {sorted(nuevos)}")


def test_sitios_revisados_siguen_existiendo():
    """Si `SITIOS_REVISADOS` alguna vez deja de estar vacía, que una
    entrada MUERTA (el sitio se cerró o se borró) no quede pudriéndose
    sin que nadie la note -- mismo criterio que LE4/EB5."""
    encontrados = _censar()
    fantasmas = SITIOS_REVISADOS - encontrados
    assert not fantasmas, (
        f"Entrada en SITIOS_REVISADOS que ya no aparece en el censo -- "
        f"límpiala: {fantasmas}")


# Frente de LECTURA (`L1`, PLAN_CIERRE_LECTURAS_02-09.md). Lista blanca
# GENERADA con `scratchpad/generar_lista_lectura.py` (mismo espíritu que
# IV1/IV2, DA-40: un script deriva el texto, este tripwire vigila que no
# diverja) -- no se transcribe a mano. Reejecutar ese script y pegar su
# salida aquí es el único modo soportado de tocar este diccionario; una
# edición manual que no coincida con el script se detecta comparando contra
# una nueva corrida.
#
# `load.py::mostrar_db_CambioFuente` entra marcada como código MUERTO --
# decisión del físico (`L3`, 02-09): "dejar anotado", 0 llamadores en
# producción, no se convierte ni se retira por ahora.
SITIOS_LECTURA_REVISADOS = {
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "buscar_datos_db"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "buscar_datos_db_energia"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "buscar_datos_db_energia_pdd"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "check_imagen_mlc_subida"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_controles_anuales"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_dosimetria_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_tabla_control_camaras_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_tabla_equipos_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_tabla_factor_campo_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_tabla_factores_sobre_eje_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_tabla_factores_transmision_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_tabla_fantomas_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", "mostrar_tabla_simple_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "_mostrar_tabla_generica"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "abrir_pelicula"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "consulta_mesualBraq"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_analisis_franjas"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_analisis_img"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_controles_imgHC_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_controles_imgIX_anual"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_controles_mensuales"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_db_CambioFuente"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_db_linealidad"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_db_mensualBraqui"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_des_isoc"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_dosimetria"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_equipos"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_indc_angulares"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_indc_brazo_HC"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_indicadores_camilla"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_laseres"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_seguridad"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_tam_campos"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_tam_campos_HC"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("data/ManejoDatos/load.py", "mostrar_veri_corr"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("models/PDF/pdf.py", "_leer_datos_starshot_db"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", "actualizar_ref_bd"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", "construir_tablas_reporte_linealidad"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", "consulta_db"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", "actualizar_ref_bd"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", "consulta_db"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", "mostrar_tabla_lecturas"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", "mostrar_tabla_maximos"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("ui/paginasControles/PruebasMensuales/tac_mensual.py", "_existe_ref"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
    ("ui/paginasGuia/equipos.py", "cargartabla"):
        "solo lee; cierra fuera de un `finally`, sin `except` -- la excepcion sube al llamador y salta el close",
    ("ui/paginasGuia/equipos.py", "editarEquipo"):
        "solo lee; cierra fuera de un `finally` TENIENDO `except` -- el camino de excepcion se traga el fallo y salta el close",
}


def test_ninguna_funcion_que_lee_deja_una_conexion_pelada_sin_revisar():
    """L1: mismo criterio que el frente de escritura, pero un sitio nuevo
    aquí NO es automáticamente una regresión grave (P1 solo lo exige para
    escritura) -- es, como mínimo, un sitio que hay que mirar y clasificar:
    añadirlo a `SITIOS_LECTURA_REVISADOS` con su razón, o convertirlo."""
    encontrados = _censar_lectura()
    nuevos = encontrados - set(SITIOS_LECTURA_REVISADOS)
    assert not nuevos, (
        "Función de solo LECTURA con una conexión pelada "
        "(`conn = Conexion().conectar()` o `conn = algo.obtener_conexion()`) "
        "que no está envuelta en un `with` ni cerrada en un `finally`, y que "
        "no está en la lista blanca de PLAN_CIERRE_LECTURAS_02-09.md (`L1`). "
        "Conviértela con `with Conexion().conectar() as conn:` (P3 de ese "
        "plan) o añádela a SITIOS_LECTURA_REVISADOS con su razón (regenera "
        "la lista con scratchpad/generar_lista_lectura.py en vez de "
        f"transcribirla a mano): {sorted(nuevos)}")


def test_cada_excepcion_de_lectura_declara_su_razon():
    for sitio, razon in SITIOS_LECTURA_REVISADOS.items():
        assert len(razon) > 40, f"{sitio} sin razón documentada"


def test_sitios_lectura_revisados_siguen_existiendo():
    """Si un sitio de `SITIOS_LECTURA_REVISADOS` se convierte a `with`
    (L2a/L2b/L2c y, más adelante, L4), su entrada debe RETIRARSE en el mismo
    commit -- si no, esta entrada fantasma lo señala. La lista debe encoger,
    nunca pudrirse (mismo criterio que LE4/EB5/el frente de escritura)."""
    encontrados = _censar_lectura()
    fantasmas = set(SITIOS_LECTURA_REVISADOS) - encontrados
    assert not fantasmas, (
        f"Entrada en SITIOS_LECTURA_REVISADOS que ya no aparece en el censo "
        f"-- límpiala (el sitio ya se convirtió a `with`): {fantasmas}")


def test_el_censo_de_lectura_detecta_un_sitio_nuevo_de_verdad(tmp_path, monkeypatch):
    """P8 (PLAN_CIERRE_LECTURAS_02-09.md, verificación de `L1`): que el
    censo reproduzca la lista de 47 no demuestra que vigile algo -- podría
    estar simplemente leyendo la lista blanca. Esta prueba escribe un
    archivo `.py` REAL (no un mock, no un `compile()` con `co_filename`
    falso: `_archivos_produccion()` recorre el disco de verdad con
    `rglob`, a diferencia de RT1, que inspecciona frames en ejecución) con
    una función de solo lectura y una conexión pelada, y confirma que
    `_censar_lectura()` la encuentra -- sobre CUALQUIER archivo del árbol,
    no solo sobre los 47 ya conocidos."""
    archivo_sintetico = tmp_path / "_sitio_sintetico_verificacion_l1.py"
    archivo_sintetico.write_text(
        "from data.ManejoDatos.conection import Conexion\n"
        "\n"
        "def leer_algo_sin_cerrar_bien(id_x):\n"
        "    conn = Conexion().conectar()\n"
        "    cursor = conn.cursor()\n"
        "    cursor.execute('SELECT 1 FROM controles WHERE id = ?', (id_x,))\n"
        "    fila = cursor.fetchone()\n"
        "    conn.close()\n"
        "    return fila\n",
        encoding="utf-8",
    )
    ruta_relativa_ficticia = "data/ManejoDatos/_sitio_sintetico_verificacion_l1.py"

    # Obstáculo real (P6): capturar la función ORIGINAL en una variable local
    # ANTES de parchear es obligatorio -- si el generador de abajo llamara a
    # `_archivos_produccion()` por nombre, resolvería el nombre en el
    # namespace del MÓDULO en cada iteración (búsqueda dinámica de Python),
    # y como el módulo ya apunta a esta misma función tras el `monkeypatch`,
    # se llamaría a sí misma -- `RecursionError: maximum recursion depth
    # exceeded` (reproducido al escribir esta prueba).
    _archivos_produccion_original = _archivos_produccion

    def _archivos_produccion_mas_el_sintetico():
        yield from _archivos_produccion_original()
        yield Path(ruta_relativa_ficticia), archivo_sintetico

    # `tests/` no es un paquete (sin `__init__.py`): `sys.modules[__name__]`
    # es la forma segura de referirse a este mismo módulo para parchear su
    # función global -- `_censar_lectura` resuelve `_archivos_produccion`
    # desde el namespace del módulo en cada llamada, así que basta con
    # reemplazar el atributo del módulo.
    monkeypatch.setattr(sys.modules[__name__], "_archivos_produccion",
                         _archivos_produccion_mas_el_sintetico)
    encontrados = _censar_lectura()

    clave_esperada = (ruta_relativa_ficticia, "leer_algo_sin_cerrar_bien")
    assert clave_esperada in encontrados, (
        "el censo de lectura no detectó el sitio sintético recién creado -- "
        "si esto falla, el censo dejó de recorrer archivos nuevos y solo "
        "estaría reproduciendo la lista blanca")
    assert clave_esperada not in SITIOS_LECTURA_REVISADOS, (
        "el sitio sintético no debería estar en la lista blanca real -- si "
        "lo está, esta prueba no demuestra nada nuevo")
