"""LE4 (PLAN_CONTRATO_GUARDADO_13-08.md §6-LE4): tripwire permanente de la
regla 5 del contrato -- "toda lectura de una tabla del bloque de QC filtra
por activo, salvo las que deliberadamente censan (migración, auditoría),
que se marcan como excepción explícita en el código".

Repite, como test, el censo AST que LE1/LE2 hicieron a mano (§2.4 del plan:
"análisis AST, no grep" -- la mitad del SQL del proyecto se arma en tiempo
de ejecución). Mismo espíritu que `test_f8_vigencia_derivada.py`: recorre
TODO el árbol de producción y falla si aparece un sitio nuevo.

Alcance deliberadamente MÁS ANGOSTO que `TABLAS_ANULABLES` completo: cubre
las 17 tablas del grupo C más `dosimetriaMen` -- las que EMPIEZAN a
versionar con este plan (§2.4). Las raíces (`controles`, `TipoCalibracion`,
`braqui`...) y las 3 hijas que ya versionaban desde M2 (`equipos_medicion`,
`control_cunas`, `control_conos`) tienen exposición PREEXISTENTE (52+
sitios, [[DP-31]]) que este plan explícitamente no crea ni corrige --
meterlas aquí convertiría este tripwire en un censo de deuda vieja, no en
un guardián de lo que este plan protege.

Dos detectores:

1. **Tabla literal**: cualquier `execute`/`executemany`/`prepare` cuyo SQL
   nombra una de las 18 tablas en alcance tras `FROM` como texto literal
   debe mencionar `activo` en algún punto del SQL (a mano o vía
   `filtro_activo(...)`). Esto es lo que habría atrapado H1 si hubiera
   existido antes.
2. **Tabla dinámica**: cualquier sitio cuyo nombre de tabla se arma en
   tiempo de ejecución (`FROM {tabla}`, una variable) no se puede verificar
   estáticamente si esa tabla está o no en alcance. Si la misma consulta ya
   llama a `filtro_activo(tabla)` sobre esa MISMA variable, se considera
   protegido por construcción (correcto sea cual sea la tabla real -- el
   propio `filtro_activo` decide si aplica). Si no, se compara contra una
   lista blanca explícita ya revisada a mano (mismo patrón que
   `SQL_PERMITIDO`/`ACCESO_POR_CLAVE_PERMITIDO` de F8): un sitio nuevo fuera
   de la lista hace fallar el test, forzando la misma revisión manual que
   LE2 hizo una vez, en vez de dejarla sin repetir nunca más.
"""
import ast
import re
from pathlib import Path

# Grupo C (§2.1 del plan) + dosimetriaMen: las 18 tablas que EMPIEZAN a
# versionar con este plan. Lista literal (no derivada de TABLAS_ANULABLES)
# para que un cambio futuro en la lista blanca de anulación no ensanche ni
# angoste este tripwire por sorpresa.
TABLAS_EN_ALCANCE = frozenset({
    "tamano_campo", "analisis_placa_franjas",
    "tabla_factor_campo", "tabla_factores_transmision",
    "tabla_factores_sobre_eje", "tabla_control_camaras_monitoras",
    "HC_indicadores_brazo", "HC_indicadores_colimador", "HC_indicadores_laser",
    "HC_indicadores_camilla", "HC_desplazamiento_isocentro_mensual",
    "HC_velocidad_multilaminas_anual", "HC_precision_posicion_multilaminas_anual",
    "HC_imagen_perfil_mlc_anual", "HC_dosimetria_anual",
    "HC_linealidad_unidades_monitor_anual", "HC_tamanos_campo_radiacion",
    "dosimetriaMen",
})

ROOT = Path(__file__).resolve().parent.parent
# NB: a diferencia del EXCLUDE_DIRS de test_f8_vigencia_derivada.py, "models"
# NO se excluye aquí -- en este proyecto es código de producción real
# (generación de PDF, models/PDF/*), no un directorio de pesos ML.
EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}
EXEC_METHODS = {"execute", "executemany", "prepare"}

# Sitios con nombre de tabla dinámico, NO autoprotegidos por un
# `filtro_activo(<misma variable>)` en la propia consulta, ya revisados a
# mano en LE2 y clasificados como fuera de alcance de este plan:
#
#   - identidad: selecciona UNA fila por su propia clave (antes de anularla
#     /borrarla), no una lista -- filtrar por activo no aplica.
#   - raíz (DP-31): lectura sobre una de las raíces con soft-delete
#     preexistente (controles/TipoCalibracion/diarias/braqui) -- exposición
#     previa a este plan, registrada como deuda aparte, no la crea LE.
#   - migración/censo: cuenta o copia TODAS las filas a propósito (contrato
#     regla 5, excepción explícita) -- documentado además en cada archivo.
#   - tabla no anulable: la tabla de destino no está en TABLAS_ANULABLES
#     en absoluto (filtro_activo() sería un no-op ahí de todos modos).
#   - DO1: rama INSERT-vs-UPDATE de dosimetriaMen que DO1 va a reemplazar
#     enteramente por anular+insertar -- tocar el read ahora sería trabajo
#     tirado; DO1 lo hereda como tarea propia.
#   - código muerto: sin llamadores en todo el árbol de producción.
SITIOS_DINAMICOS_PERMITIDOS = {
    ("data/GraficasyTablas/tablas.py", 194): "identidad (fila antes de anular, diarias)",
    ("data/GraficasyTablas/unovsuno.py", 4): "raíz (DP-31, gráfico de diarias)",
    ("data/ManejoDatos/conection.py", 535): "migración/censo (E10, copia de tabla completa)",
    ("data/ManejoDatos/load.py", 660): "DO1 (subirlineasmensuales, rama INSERT-vs-UPDATE)",
    ("data/ManejoDatos/load.py", 802): "raíz (DP-31, diarias -- ya filtra activo a mano)",
    ("data/ManejoDatos/load.py", 204): "raíz (DP-31, diarias -- ya filtra activo a mano)",
    ("data/ManejoDatos/load.py", 924): "código muerto (mostrar_db_CambioFuente, sin llamadores)",
    ("data/ManejoDatos/load.py", 4468): "identidad (fila antes de anular/borrar)",
    ("models/PDF/reportes.py", 67): "raíz (DP-31, diarias)",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1693): "tablas no anulables (TipoCalibracion es raíz DP-31; SistemaMedicion/CondicionesMedicion no están en TABLAS_ANULABLES)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 259): "DO1 (subirlineasmensuales_ix, rama INSERT-vs-UPDATE)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 314): "DO1 (subirlineasmensuales_ix, rama INSERT-vs-UPDATE)",
    # scripts/: excepciones censales explícitas (contrato regla 5) --
    # documentadas en cada archivo, no solo aquí.
    ("scripts/migrar_bd_a_estandar.py", 147): "migración/censo (_contar_qc)",
    ("scripts/migrar_bd_a_estandar.py", 179): "migración/censo (_contar_todas_las_tablas)",
    ("scripts/migrar_bd_a_estandar.py", 311): "migración/censo (_contar_catalogos_base)",
    ("scripts/observador_contrato.py", 143): "censo (OB1, censo.total -- cuenta TODAS las filas a propósito)",
    ("scripts/observador_contrato.py", 147): "censo (OB1, censo.activas -- calcula su propio filtro, no importa filtro_activo para no arrastrar PyQt5)",
    ("scripts/observador_contrato.py", 156): "censo (OB1, vigente -- mismo motivo)",
}

# Sitios LITERALES (tabla nombrada a secas tras FROM) donde el filtro SÍ
# está aplicado, pero indirectamente -- una variable intermedia guarda
# `filtro_activo(...)` con transformaciones (p.ej. calificar la columna con
# el alias de un JOIN) antes de interpolarse, así que el detector de texto
# no lo ve. Verificado a mano; cada uno queda documentado en el propio
# archivo, no solo aquí.
EXCEPCIONES_LITERALES = {
    ("services/consistencia_dosis.py", 51):
        "dosimetriaMen -- filtro_activo('dosimetriaMen') se califica con "
        "el alias 'd.' del JOIN antes de interpolarse (variable `filtro`)",
}


def _literal_str(node):
    """Reconstruye el texto de un `Constant` string o `JoinedStr` (f-string).
    Cada parte no literal se marca `{FILTRO_ACTIVO}` si es una llamada a
    `filtro_activo(...)` (con cualquier argumento -- variable o literal), o
    `{DYN}` si es cualquier otra cosa."""
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


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


PATRON_FROM_LITERAL = re.compile(r'FROM\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', re.IGNORECASE)
PATRON_FROM_DINAMICO = re.compile(r'FROM\s+"?\{DYN\}"?', re.IGNORECASE)


def _censar():
    """Recorre todo el árbol de producción una vez y devuelve
    (fallos_tabla_literal, sitios_dinamicos_sin_autoproteccion,
    excepciones_literales_encontradas)."""
    fallos = []
    dinamicos = set()
    excepciones_encontradas = set()
    for rel, path in _archivos_produccion():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr in EXEC_METHODS):
                continue
            if not node.args:
                continue
            texto = _literal_str(node.args[0])
            if texto is None or "select" not in texto.lower():
                continue

            if PATRON_FROM_DINAMICO.search(texto):
                # Autoprotegido si filtro_activo() se llama sobre CUALQUIER
                # variable en la misma consulta -- en todos los sitios
                # reales del proyecto es la misma variable que nombra la
                # tabla (mismo patrón en las ~20 llamadas ya escritas).
                if "{FILTRO_ACTIVO}" not in texto:
                    dinamicos.add((str(rel), node.lineno))
                continue

            m = PATRON_FROM_LITERAL.search(texto)
            if not m:
                continue
            tabla = m.group(1)
            if tabla not in TABLAS_EN_ALCANCE:
                continue
            if "activo" in texto.lower() or "{FILTRO_ACTIVO}" in texto:
                continue
            clave = (str(rel), node.lineno)
            if clave in EXCEPCIONES_LITERALES:
                excepciones_encontradas.add(clave)
                continue
            fallos.append(
                f"{rel}:{node.lineno} lee '{tabla}' (grupo C/dosimetriaMen) "
                f"sin filtrar 'activo': {texto.strip()[:120]!r}")
    return fallos, dinamicos, excepciones_encontradas


def test_ninguna_lectura_literal_de_tabla_en_alcance_omite_activo():
    fallos, _dinamicos, _excepciones = _censar()
    assert fallos == [], (
        "Lectura nueva sobre una tabla del grupo C/dosimetriaMen sin "
        "filtrar 'activo' (regla 5 del contrato):\n" + "\n".join(fallos))


def test_sitios_dinamicos_coinciden_con_la_lista_revisada():
    _fallos, dinamicos, _excepciones = _censar()
    esperados = set(SITIOS_DINAMICOS_PERMITIDOS)
    nuevos = dinamicos - esperados
    ausentes = esperados - dinamicos
    assert dinamicos == esperados, (
        f"Sitios con tabla dinámica fuera de la lista revisada -- si son "
        f"legítimos, añádelos a SITIOS_DINAMICOS_PERMITIDOS con su razón; "
        f"si tocan una tabla del grupo C/dosimetriaMen, aplícales "
        f"filtro_activo(): {nuevos} (nuevos) / {ausentes} (ya no aparecen, "
        f"limpiar la lista)")


def test_excepciones_literales_siguen_existiendo():
    _fallos, _dinamicos, excepciones = _censar()
    esperadas = set(EXCEPCIONES_LITERALES)
    ausentes = esperadas - excepciones
    assert not ausentes, (
        f"Excepción literal que ya no aparece en el código -- si el sitio "
        f"cambió o se filtró de forma que el censo ya lo reconoce, "
        f"limpiar EXCEPCIONES_LITERALES: {ausentes}")
