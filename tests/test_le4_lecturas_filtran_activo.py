"""LE4/ES1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-LE4, reescrito sobre
PLAN_LECTURA_VIGENTE_18-08.md §6-ES1): tripwire permanente de la regla 5
del contrato -- "toda lectura de una tabla del bloque de QC filtra por
activo, salvo las que deliberadamente censan (migración, auditoría), que se
marcan como excepción explícita en el código".

Por qué se reescribió el 18-08: la primera versión de LE4 (13-08) tenía
cuatro huecos que dejaron pasar 3 defectos reales en el rebuild del 18-08
(control mensual duplicado, dosis de referencia mostrada vacía, catálogo de
equipos anual mezclando históricos con vigentes):

  1. SQL armado en una variable (`query = "..."; query += "..."`) era
     invisible -- el analizador solo miraba el argumento LITERAL de
     `execute()`.
  2. El alcance (`TABLAS_EN_ALCANCE`, 18 tablas escritas a mano) quedó
     desincronizado de `TABLAS_ANULABLES` en cuanto PR1 amplió el contrato.
  3. El detector solo reconocía `FROM`, no `JOIN`.
  4. El filtro se comprobaba por SENTENCIA, no por TABLA (un `cm.activo`
     de otra tabla daba por bueno un `p.activo` que nunca estuvo).

Los cuatro huecos se cierran delegando el criterio entero a
`services/lectura_vigente.py` (AN1): alcance derivado de
`TABLAS_ANULABLES` vía `ast` (hueco 2), detección de `FROM`/`JOIN` con
filtro ligado a su propio alias (huecos 3 y 4), y resolución de SQL armado
en variable para el patrón real de asignación simple o if/else +
concatenación compartida (hueco 1) -- ver PLAN_LECTURA_VIGENTE_18-08.md
§2.4 y §6-AN1.

Repite, como test, el censo AST que LE1/LE2 hicieron a mano (§2.4 del plan
13-08: "análisis AST, no grep"). Mismo espíritu que
`test_f8_vigencia_derivada.py`: recorre TODO el árbol de producción y falla
si aparece un sitio nuevo.

Cuatro detectores:

1. **Tabla literal**: cualquier `execute`/`executemany`/`prepare` cuyo
   argumento (directo, o resuelto desde una variable -- ver 4) nombra una
   tabla del alcance de AN1 tras `FROM`/`JOIN`/`UPDATE` sin su filtro
   propio.
2. **Tabla dinámica**: el nombre de tabla se arma en tiempo de ejecución
   (`FROM {tabla}`). No verificable estáticamente cuál tabla es -- se
   acepta si la misma consulta llama a `filtro_activo(tabla)` sobre esa
   MISMA variable (protegido por construcción); si no, se compara contra
   una lista blanca revisada a mano (`SITIOS_DINAMICOS_PERMITIDOS`).
3. **Excepciones literales**: el filtro SÍ está aplicado pero de forma
   indirecta (una variable intermedia califica `filtro_activo(...)` con un
   alias antes de interpolarse) -- el detector de texto no lo ve;
   verificado a mano, documentado en `EXCEPCIONES_LITERALES`.
4. **Sitios opacos** (NUEVO en ES1, cierra el hueco 1): el argumento de
   `execute()` no es un literal ni una variable resoluble por AN1 (bucle,
   `try`, reasignación compleja) -- genuinamente invisible para el análisis
   estático. Se compara contra una lista blanca revisada a mano
   (`SITIOS_OPACOS_PERMITIDOS`, análoga a la de tablas dinámicas). Un sitio
   opaco nuevo hace fallar el test -- es lo que habría atrapado D1/D2 el
   13-08 si el patrón que los produce ('query = ...'; 'query += ...') no
   hubiera sido además resoluble por AN1 (en cuyo caso ya cae en el
   detector 1, más fuerte que "opaco").
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import lectura_vigente as lv  # noqa: E402

# NB: a diferencia del EXCLUDE_DIRS de test_f8_vigencia_derivada.py, "models"
# NO se excluye aquí -- en este proyecto es código de producción real
# (generación de PDF, models/PDF/*), no un directorio de pesos ML.
EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}
EXEC_METHODS = {"execute", "executemany", "prepare"}

# Sitios con nombre de tabla DINÁMICO (`FROM {tabla}`), NO autoprotegidos
# por un `filtro_activo(<misma variable>)` en la propia consulta, revisados
# a mano y clasificados como fuera de alcance de este plan:
#
#   - identidad: selecciona/actualiza UNA fila por su propia clave (antes
#     de anularla/borrarla), no una lista -- filtrar por activo no aplica.
#   - raíz (DP-31): lectura sobre una de las raíces con soft-delete
#     preexistente (controles/TipoCalibracion/diarias/braqui) -- exposición
#     previa a este plan, registrada como deuda aparte.
#   - migración/censo: cuenta o copia TODAS las filas a propósito (contrato
#     regla 5, excepción explícita) -- documentado además en cada archivo.
#   - tabla no anulable: la tabla de destino no está en TABLAS_ANULABLES
#     en absoluto (filtro_activo() sería un no-op ahí de todos modos).
#   - DO1: rama de subirlineasmensuales_ix/subirlineasmensuales que compone
#     el bloque vigente o cae fuera del bloque de QC; ya filtra activo a
#     mano donde aplica.
#   - código muerto: sin llamadores en todo el árbol de producción.
SITIOS_DINAMICOS_PERMITIDOS = {
    ("data/GraficasyTablas/tablas.py", 213): "identidad (fila antes de anular, diarias)",
    ("data/GraficasyTablas/unovsuno.py", 4): "raíz (DP-31, gráfico de diarias)",
    ("data/ManejoDatos/conection.py", 535): "migración/censo (E10, copia de tabla completa)",
    ("data/ManejoDatos/load.py", 726): "DO1/PR1 (subirlineasmensuales -- SELECT del bloque vigente, esquema completo para componer el nuevo sin perder columnas fuera de columnas_lista, p.ej. preguntas.imagen; ya filtra activo a mano, tabla dinámica)",
    ("data/ManejoDatos/load.py", 753): "PR1 (subirlineasmensuales, rama else -- ya no aplica a preguntas tras PR1, pero sigue alcanzable para cualquier tabla futura fuera de TABLAS_ANULABLES)",
    ("data/ManejoDatos/load.py", 893): "raíz (DP-31, diarias -- ya filtra activo a mano)",
    ("data/ManejoDatos/load.py", 204): "raíz (DP-31, diarias -- ya filtra activo a mano)",
    ("data/ManejoDatos/load.py", 1020): "código muerto (mostrar_db_CambioFuente, sin llamadores)",
    ("data/ManejoDatos/load.py", 4610): "identidad (fila antes de anular/borrar)",
    ("models/PDF/reportes.py", 67): "raíz (DP-31, diarias)",
    # NOTA (LF, gap hallado por el subagente que resolvió LF3): hasta aquí
    # decía "TipoCalibracion es raíz DP-31; SistemaMedicion/CondicionesMedicion
    # no están en TABLAS_ANULABLES" -- cierto antes de LF2, falso después
    # (ambas son PENDIENTE-LF). Corregido: `addsomething::consulta` ahora
    # llama a `filtro_activo(nombre_tabla)` directamente sobre la MISMA
    # variable dinámica -- protegido por construcción (ver docstring del
    # módulo, "Tabla dinámica"), por eso el sitio YA NO aparece en absoluto
    # en el censo (ni fallo ni dinámico): el propio analizador reconoce la
    # llamada. No hace falta entrada aquí.
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 271): "DO1 (subirlineasmensuales_ix -- SELECT del bloque vigente para componer el nuevo; ya filtra activo a mano, tabla dinámica)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 310): "DO1 (subirlineasmensuales_ix, rama fuera del bloque de QC)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 361): "DO1 (_cargar_dosimetria_bd_ix -- ya filtra activo a mano, tabla dinámica)",
    ("data/ManejoDatos/load.py", 2791): "tabla dinámica (_mostrar_tabla_generica -- módulo TAC/Catphan: 'config[\"tabla\"]' es una de las 7 hijas de TAC, PENDIENTE-LF hoy; JOIN literal con 'pruebas' (también PENDIENTE-LF). LF: corregido el gap que decía \"ninguna está en TABLAS_ANULABLES\" (cierto antes de LF2) -- ahora filtra las DOS con `filtro_t`/`filtro_p` calificados por alias, invisibles para el detector de texto por ir en variables intermedias)",
    # scripts/: excepciones censales explícitas (contrato regla 5) --
    # documentadas en cada archivo, no solo aquí.
    ("scripts/migrar_bd_a_estandar.py", 147): "migración/censo (_contar_qc)",
    ("scripts/migrar_bd_a_estandar.py", 179): "migración/censo (_contar_todas_las_tablas)",
    ("scripts/migrar_bd_a_estandar.py", 311): "migración/censo (_contar_catalogos_base)",
    ("scripts/observador_contrato.py", 142): "censo (OB1, censo.total -- cuenta TODAS las filas a propósito)",
    ("scripts/observador_contrato.py", 146): "censo (OB1, censo.activas -- calcula su propio filtro, no importa filtro_activo para no arrastrar PyQt5)",
    ("scripts/observador_contrato.py", 155): "censo (OB1, vigente -- mismo motivo)",
    ("scripts/saneamiento_bloque_qc.py", 42): "SA1/SA2 -- ya filtra 'activo' a mano en el WHERE (visible en el propio texto), no importa filtro_activo() para no arrastrar PyQt5 en un script que solo usa sqlite3",
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
    ("data/ManejoDatos/load.py", 1502):
        "preguntas -- RP1: filtro_activo('preguntas') se califica con el "
        "alias 'p.' del LEFT JOIN antes de interpolarse (variable `filtro_p`, "
        "mismo patrón que consistencia_dosis.py)",
    ("data/ManejoDatos/load.py", 1505):
        "preguntas -- RP1, mismo `filtro_p` que la excepción anterior, "
        "usado en la segunda rama (equipo_filtrar no truthy) de "
        "mostrar_controles_mensuales",
    # LF1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF1): mismo patrón, aplicado a
    # las 30 tablas nuevas -- variable intermedia califica filtro_activo()
    # con el alias del JOIN antes de interpolarse.
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", 1010):
        "pruebas -- filtro_activo('pruebas') se califica con el alias 'p.' "
        "del LEFT JOIN (variable `filtro_p`) en consultar_pruebas_disponibles",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", 1373):
        "valores_ct -- filtro_activo('valores_ct') se califica con el alias "
        "'vc.' del JOIN (variable `filtro_vc`) en reconstruir_valores_ct",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", 1464):
        "uniformidad_ruido -- filtro_activo('uniformidad_ruido') se califica "
        "con el alias 'ur.' del JOIN (variable `filtro_ur`) en "
        "reconstruir_uniformidad",
    ("models/PDF/Imagenes/reportes_control_sistema_imagenes.py", 323):
        "pruebas -- filtro_activo('pruebas') se califica con el alias 'p.' "
        "del JOIN (variable `filtro_p`) en _obtener_imagenes_blob",
    # LF1b (§6-LF1): 'pruebas' se une con LEFT JOIN a 'controles' (raíz) --
    # el filtro va en el ON, no en el WHERE (si fuera WHERE, un control sin
    # pruebas VIGENTES desaparecería de la lista en vez de mostrar
    # num_pruebas=0). Variable `filtro_p_on`, 5 funciones gemelas
    # (mostrar_controles_imgIX[_anual], mostrar_controles_imgHC[_anual],
    # mostrar_controles_tac), 2 sitios cada una (COUNT + SELECT MAX).
    ("data/ManejoDatos/load.py", 1777): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX_anual, COUNT)",
    ("data/ManejoDatos/load.py", 1811): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX_anual, SELECT MAX)",
    ("data/ManejoDatos/load.py", 1966): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX, COUNT)",
    ("data/ManejoDatos/load.py", 2014): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX, SELECT MAX)",
    ("data/ManejoDatos/load.py", 2172): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC_anual, COUNT)",
    ("data/ManejoDatos/load.py", 2206): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC_anual, SELECT MAX)",
    ("data/ManejoDatos/load.py", 2363): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC, COUNT)",
    ("data/ManejoDatos/load.py", 2411): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC, SELECT MAX)",
    ("data/ManejoDatos/load.py", 2564): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_tac, COUNT)",
    ("data/ManejoDatos/load.py", 2612): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_tac, SELECT MAX)",
    # MaximosCamaras JOIN TipoCalibracion (raíz) -- mismo patrón, variable
    # `filtro_mc` calificada con el alias 'mc.'. Dos hallazgos en la misma
    # línea (el analizador reporta 'sin filtro' y 'LIMIT sin ORDER BY' por
    # separado aunque sea un solo sitio revisado).
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2759): "MaximosCamaras -- filtro_mc calificado con el alias 'mc.' (graficar_maximos_camara)",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1585): "MaximosCamaras -- filtro_mc calificado con el alias 'mc.' (graficar_maximos_camara)",
}

# ES1 (NUEVO, hueco 1): sitios donde el argumento de execute() no es un
# literal NI resoluble por AN1 (`resolver_argumento_execute` devuelve
# `None` -- reasignación dentro de un bucle/try, o una expresión que no es
# ni Name ni Constant/JoinedStr). Revisados a mano uno por uno el 18-08:
#
#   - INSERT: nunca necesita filtro de activo (no elige entre filas
#     existentes, crea una nueva) -- se acepta pase lo que pase con la
#     tabla de destino, dinámica o no.
#   - DDL/migración: CREATE TABLE / ALTER TABLE, no es una lectura de datos.
#   - tabla no anulable / raíz: la tabla de destino no está en el alcance
#     de AN1 (no está en TABLAS_ANULABLES, o es una de las 7 raíces de
#     DP-31) -- el contenido exacto del SQL no importa para este tripwire.
#   - DO1: rama ya revisada en su momento, dynamic-table filtrado a mano
#     (`sql += filtro_activo(nombre_tabla)`, una llamada real, no un
#     literal -- por eso es opaca para el resolver aunque esté bien).
SITIOS_OPACOS_PERMITIDOS = {
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", 875): "INSERT (linealidad_ct)",
    ("data/ManejoDatos/conection.py", 534): "DDL/migración (E10, tabla temporal de la migración CASCADE->RESTRICT)",
    ("data/ManejoDatos/conection.py", 1934): "INSERT (users, no está en TABLAS_ANULABLES)",
    ("data/ManejoDatos/load.py", 222): "INSERT (diarias -- tabla dinámica; raíz DP-31 de todos modos)",
    ("data/ManejoDatos/load.py", 384): "INSERT (controles, raíz DP-31)",
    ("data/ManejoDatos/load.py", 4225): "UPDATE por id_where -- identidad, edición directa de UNA celda ya identificada (equivalente al patrón 'identidad' de tablas dinámicas)",
    # LF (gap hallado por el subagente que resolvió LF3): decía "no está en
    # TABLAS_ANULABLES" -- cierto antes de LF2, falso después (PENDIENTE-LF).
    # Corregido: la sentencia ahora SÍ llama a `filtro_activo('ResultadosActividad')`
    # -- sigue "opaca" para AN1 no por el filtro sino porque `sql` se
    # reasigna en varias ramas de `guardarEdicion` (misma función que la
    # entrada anterior), irresoluble a propósito por diseño de AN1.
    ("data/ManejoDatos/load.py", 4305): "UPDATE ResultadosActividad -- ya filtra con filtro_activo('ResultadosActividad'); opaca a AN1 por reasignación de `sql` en varias ramas de guardarEdicion, no por falta de filtro",
    ("data/ManejoDatos/load.py", 4641): "DELETE por id_where -- rama de eliminarRegistro para tablas FUERA de TABLAS_ANULABLES (las anulables van por anular_fila, no llegan aquí)",
    ("data/ManejoDatos/obtenerDatosHalcyon.py", 391): "INSERT (halcyon, raíz DP-31)",
    ("services/dosis_service.py", 281): "DDL (CREATE TABLE calculadora_dosimetrica, no está en TABLAS_ANULABLES -- tiene su propia columna `vigente`, mecanismo de versionado independiente de este contrato)",
    ("services/dosis_service.py", 391): "INSERT (calculadora_dosimetrica, no está en TABLAS_ANULABLES)",
    ("services/dosis_service.py", 449): "SELECT calculadora_dosimetrica -- no está en TABLAS_ANULABLES (versiona con su propia columna `vigente`, no `activo`)",
    ("services/dosis_service.py", 550): "SELECT calculadora_dosimetrica -- mismo motivo",
    ("services/dosis_service.py", 556): "SELECT calculadora_dosimetrica -- mismo motivo",
    ("ui/paginasControles/PruebasAnuales/halcyon_anual.py", 303): "INSERT (HC_imagen_perfil_mlc_anual)",
    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py", 79): "INSERT (controles, raíz DP-31)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 296): "INSERT (subirlineasmensuales_ix, dentro del bucle de energías -- reasignación de `sql` en cada vuelta, irresoluble a propósito por AN1; INSERT no necesita filtro de todos modos)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 316): "INSERT (subirlineasmensuales_ix, rama fuera del bloque de QC -- ver comentario en el propio archivo)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 330): "UPDATE por (ref, energia) -- subirlineasmensuales_ix, rama fuera del bloque de QC (nombre_tabla no anulable en esta rama)",
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 3605): "DO1 (pruebatalas -- `sql += filtro_activo(nombre_tabla)` es una llamada real, no un literal; ya documentado en el propio archivo como filtrado a mano)",
    ("ui/paginasGuia/SQLtoEXCEL.py", 510): "raíz (DP-31, braqui.pelicula por rango de fechas)",
}


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


PATRON_FROM_DINAMICO = re.compile(r'FROM\s+"?\{DYN\}"?', re.IGNORECASE)


def _censar():
    """Recorre todo el árbol de producción una vez y devuelve un dict con:
      fallos: violaciones nuevas de AN1 sobre tabla literal (hard failures)
      dinamicos: sitios de tabla dinámica sin autoprotección
      opacos: sitios donde ni el literal ni el resolver de AN1 alcanzan
      excepciones_encontradas: cuáles de EXCEPCIONES_LITERALES siguen ahí
    """
    tablas = lv.tablas_hijas_del_bloque_qc()
    fallos = []
    dinamicos = set()
    opacos = set()
    excepciones_encontradas = set()

    for rel, path in _archivos_produccion():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:
            continue
        for func in [n for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (isinstance(fn, ast.Attribute) and fn.attr in EXEC_METHODS):
                    continue
                if not node.args:
                    continue
                arg0 = node.args[0]
                clave = (str(rel), node.lineno)

                if isinstance(arg0, (ast.Constant, ast.JoinedStr)):
                    textos = [lv._literal_str_ast(arg0)]
                elif isinstance(arg0, ast.Name):
                    textos = lv.resolver_argumento_execute(func, node)
                    if textos is None:
                        opacos.add(clave)
                        continue
                else:
                    opacos.add(clave)
                    continue

                for texto in textos:
                    if texto is None:
                        continue
                    minus = texto.lower()
                    if "select" not in minus and "update" not in minus:
                        continue

                    if PATRON_FROM_DINAMICO.search(texto):
                        if "{filtro_activo}" not in texto.lower():
                            dinamicos.add(clave)
                        continue

                    hallazgos = lv.analizar(texto, tablas)
                    if not hallazgos:
                        continue
                    if clave in EXCEPCIONES_LITERALES:
                        excepciones_encontradas.add(clave)
                        continue
                    for h in hallazgos:
                        fallos.append(
                            f"{rel}:{node.lineno} lee/escribe '{h.tabla}' "
                            f"(alias '{h.alias}') -- {h.motivo}: "
                            f"{texto.strip()[:110]!r}")

    return {
        "fallos": fallos,
        "dinamicos": dinamicos,
        "opacos": opacos,
        "excepciones_encontradas": excepciones_encontradas,
    }


def test_ninguna_lectura_o_escritura_omite_el_filtro_de_activo():
    resultado = _censar()
    assert resultado["fallos"] == [], (
        "Lectura/escritura nueva sobre una tabla del bloque de QC sin "
        "filtrar 'activo' (regla 5 del contrato):\n" + "\n".join(resultado["fallos"]))


def test_sitios_dinamicos_coinciden_con_la_lista_revisada():
    resultado = _censar()
    dinamicos = resultado["dinamicos"]
    esperados = set(SITIOS_DINAMICOS_PERMITIDOS)
    nuevos = dinamicos - esperados
    ausentes = esperados - dinamicos
    assert dinamicos == esperados, (
        f"Sitios con tabla dinámica fuera de la lista revisada -- si son "
        f"legítimos, añádelos a SITIOS_DINAMICOS_PERMITIDOS con su razón; "
        f"si tocan una tabla del bloque de QC, aplícales filtro_activo(): "
        f"{nuevos} (nuevos) / {ausentes} (ya no aparecen, limpiar la lista)")


def test_sitios_opacos_coinciden_con_la_lista_revisada():
    """ES1 (hueco 1, PLAN_LECTURA_VIGENTE_18-08.md): un sitio opaco NUEVO
    (SQL armado en variable que ni siquiera AN1 puede resolver) hace fallar
    el test -- exige la misma revisión manual que antes se saltaba en
    silencio. Es lo que habría atrapado D1/D2 el 13-08 si no hubieran sido,
    además, resolubles por AN1 (en cuyo caso los atrapa el primer test,
    más fuerte)."""
    resultado = _censar()
    opacos = resultado["opacos"]
    esperados = set(SITIOS_OPACOS_PERMITIDOS)
    nuevos = opacos - esperados
    ausentes = esperados - opacos
    assert opacos == esperados, (
        f"Sitio opaco nuevo (SQL armado en variable, irresoluble para AN1) "
        f"-- revísalo a mano: si es un INSERT, DDL, o toca una tabla fuera "
        f"del alcance de AN1, añádelo a SITIOS_OPACOS_PERMITIDOS con su "
        f"razón; si toca una tabla del bloque de QC sin filtrar, corrígelo: "
        f"{nuevos} (nuevos) / {ausentes} (ya no aparecen, limpiar la lista)")


def test_excepciones_literales_siguen_existiendo():
    resultado = _censar()
    esperadas = set(EXCEPCIONES_LITERALES)
    ausentes = esperadas - resultado["excepciones_encontradas"]
    assert not ausentes, (
        f"Excepción literal que ya no aparece en el código -- si el sitio "
        f"cambió o se filtró de forma que el censo ya lo reconoce, "
        f"limpiar EXCEPCIONES_LITERALES: {ausentes}")
