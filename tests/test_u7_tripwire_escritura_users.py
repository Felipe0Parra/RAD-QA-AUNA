"""U7 (PLAN_PESTANA_USUARIOS_02-09.md): tripwire de la clase de defecto que
este plan puede introducir -- un camino FUTURO que escriba en `users`
saltándose `es_fisico_jefe`. Es la lección de DP-79 ya pagada: el censo se
DERIVA del productor ("todo INSERT/UPDATE/DELETE sobre `users` en
producción"), nunca se copia del arreglo -- de lo contrario solo confirma
lo que ya se arregló, nunca encuentra lo que un cambio futuro omita.

Censo por `(archivo, función)`, NO por línea -- inmune a Trampa 5, misma
decisión que el frente de lectura de `L1`/`PLAN_CIERRE_LECTURAS_02-09.md`.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

# \busers\b evita que "braqui_users" o similar cuente como la tabla real.
PATRON_ESCRITURA_USERS = re.compile(
    r"(insert\s+into\s+users\b|update\s+users\b|delete\s+from\s+users\b)",
    re.IGNORECASE)

# Motivo declarado -- exigido por el plan, documenta POR QUÉ cada sitio es
# seguro sin tener que releer su código cada vez.
SITIOS_PERMITIDOS = {
    ("data/ManejoDatos/conection.py", "_asegurar_roles_de_sistema"):
        "migración idempotente de rol_sistema, arranque -- no expuesta a la UI",
    ("data/ManejoDatos/conection.py", "createAdmin"):
        "alta de la cuenta admin de instalación, arranque",
    ("data/ManejoDatos/usuariosManager.py", "add_user"):
        "alta; rol_sistema forzado a 'fisico' (E6)",
    ("data/ManejoDatos/usuariosManager.py", "update_password"):
        "recuperación de contraseña, valida get_user antes",
    ("services/gestion_usuarios.py", "dar_de_baja"):
        "verifica es_fisico_jefe y audita (U3)",
    ("services/gestion_usuarios.py", "reactivar"):
        "verifica es_fisico_jefe y audita (U3)",
    ("services/gestion_usuarios.py", "cambiar_rol_sistema"):
        "verifica es_fisico_jefe y audita (U4-bis)",
}


def _archivos_produccion():
    for ruta in ROOT.rglob("*.py"):
        relativo = ruta.relative_to(ROOT)
        if set(relativo.parts) & EXCLUDE_DIRS:
            continue
        yield relativo, ruta


def _funciones_que_escriben_en_archivo(ruta):
    """Nombres de toda función (`def`, no anidada por asunto propio: si una
    función interna también escribe, se cuenta aparte -- correcto, es un
    sitio más) cuyo cuerpo contiene un literal de texto que hace
    INSERT/UPDATE/DELETE sobre `users`."""
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    encontradas = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(nodo):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if PATRON_ESCRITURA_USERS.search(sub.value):
                    encontradas.add(nodo.name)
                    break
    return encontradas


def _censar():
    """(archivo, función) por cada sitio de escritura real en producción."""
    hallazgos = set()
    for relativo, ruta in _archivos_produccion():
        for nombre_funcion in _funciones_que_escriben_en_archivo(ruta):
            hallazgos.add((str(relativo), nombre_funcion))
    return hallazgos


def test_ninguna_escritura_nueva_sobre_users_sin_declarar():
    """El corazón del tripwire: si un camino NUEVO escribe en `users` (o
    uno YA CENSADO se renombra/mueve) y no está en `SITIOS_PERMITIDOS`,
    la suite se pone en rojo -- exige declarar el motivo, no solo pasa
    en silencio."""
    hallazgos = _censar()
    sin_declarar = hallazgos - set(SITIOS_PERMITIDOS)
    assert not sin_declarar, (
        f"Escritura(s) NUEVA(S) sobre `users`, sin permiso declarado -- "
        f"agrega el sitio a SITIOS_PERMITIDOS con su motivo, o revierte "
        f"el cambio si no debía escribir ahí: {sin_declarar}"
    )


def test_sitios_permitidos_siguen_existiendo():
    """Si un sitio de SITIOS_PERMITIDOS desaparece (la función se renombró,
    se retiró el código), hay que revisar y limpiar la lista -- no
    dejarla acumulando entradas muertas (mismo criterio que MI0)."""
    hallazgos = _censar()
    ausentes = set(SITIOS_PERMITIDOS) - hallazgos
    assert not ausentes, (
        f"Sitio(s) en SITIOS_PERMITIDOS que ya no aparecen -- revisa y "
        f"limpia la lista: {ausentes}"
    )


def test_censo_encuentra_los_siete_sitios_reales():
    """Que el censo no sea un placebo: debe encontrar exactamente los 7
    sitios reales conocidos hoy (3 UPDATE en _asegurar_roles_de_sistema
    cuentan como UNA función; el resto, una función cada uno)."""
    hallazgos = _censar()
    assert hallazgos == set(SITIOS_PERMITIDOS)


def test_toda_funcion_de_gestion_usuarios_que_escribe_llama_a_es_fisico_jefe():
    """Segundo test pedido por el plan: inspección del AST del módulo, no
    del texto -- si mañana alguien añade una función nueva a
    gestion_usuarios.py que escriba en `users` sin llamar a
    `es_fisico_jefe`, este test la atrapa sin que nadie tenga que
    acordarse de actualizar una lista aparte."""
    ruta = ROOT / "services" / "gestion_usuarios.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    funciones = {
        nodo.name: nodo for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef)
    }
    funciones_que_escriben = _funciones_que_escriben_en_archivo(ruta)
    assert funciones_que_escriben, (
        "el censo no encontró ninguna función que escriba en "
        "gestion_usuarios.py -- ¿cambió el archivo de forma que el "
        "detector ya no lo ve?")

    for nombre in funciones_que_escriben:
        nodo = funciones[nombre]
        llama_a_permiso = any(
            isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
            and sub.func.id == "es_fisico_jefe"
            for sub in ast.walk(nodo)
        )
        assert llama_a_permiso, (
            f"{nombre} escribe en `users` pero no llama a es_fisico_jefe -- "
            f"control de acceso cosmético")
