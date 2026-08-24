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
#   - diarias/raíces: LR4 (DA-48) retiró la exclusión, así que una lectura
#     de LISTA sobre una raíz ya NO vale como excepción -- las que quedan
#     aquí filtran de verdad (`filtro_activo(<variable>)` sobre la misma
#     tabla dinámica) o son de identidad. Su clasificación una a una vive en
#     `tests/test_lr1_censo_raices_qc.py`.
#   - migración/censo: cuenta o copia TODAS las filas a propósito (contrato
#     regla 5, excepción explícita) -- documentado además en cada archivo.
#   - tabla no anulable: la tabla de destino no está en TABLAS_ANULABLES
#     en absoluto (filtro_activo() sería un no-op ahí de todos modos).
#   - DO1: rama de subirlineasmensuales_ix/subirlineasmensuales que compone
#     el bloque vigente o cae fuera del bloque de QC; ya filtra activo a
#     mano donde aplica.
#   - código muerto: sin llamadores en todo el árbol de producción.
SITIOS_DINAMICOS_PERMITIDOS = {
    ("services/visor_anulados.py", 77): "LR6 (censo/visor, DA-49): lee TODAS las filas de `tabla` (vigentes e históricas) A PROPÓSITO -- es el visor de solo lectura que sustituye a la reactivación. `tabla` recorre TABLAS_ANULABLES completo (derivado, ver `secciones()`), nunca fuera de ese alcance -- `columnas_de` lo rechaza si no",
    ("data/GraficasyTablas/tablas.py", 213): "identidad (fila antes de anular, diarias)",
    ("data/ManejoDatos/conection.py", 535): "migración/censo (E10, copia de tabla completa)",
    ("data/ManejoDatos/load.py", 672): "DO1/PR1 (subirlineasmensuales -- SELECT del bloque vigente, esquema completo para componer el nuevo sin perder columnas fuera de columnas_lista, p.ej. preguntas.imagen; ya filtra activo a mano, tabla dinámica)",
    ("data/ManejoDatos/load.py", 699): "PR1 (subirlineasmensuales, rama else -- ya no aplica a preguntas tras PR1, pero sigue alcanzable para cualquier tabla futura fuera de TABLAS_ANULABLES)",
    ("data/ManejoDatos/load.py", 839): "diarias (EB4) -- ya filtra activo a mano, tabla dinámica",
    ("data/ManejoDatos/load.py", 164): "diarias (D3) -- ya filtra activo a mano, tabla dinámica",
    ("data/ManejoDatos/load.py", 984): "código muerto (mostrar_db_CambioFuente, sin llamadores)",
    ("data/ManejoDatos/load.py", 4574): "identidad (fila antes de anular/borrar)",
    # NOTA (LF, gap hallado por el subagente que resolvió LF3): hasta aquí
    # decía "TipoCalibracion es raíz DP-31; SistemaMedicion/CondicionesMedicion
    # no están en TABLAS_ANULABLES" -- cierto antes de LF2, falso después
    # (ambas son PENDIENTE-LF). En LF `addsomething::consulta` pasó a llamar
    # a `filtro_activo(nombre_tabla)` DENTRO del propio f-string, sobre la
    # misma variable dinámica -- protegido por construcción, y por eso el
    # sitio dejó de aparecer en el censo sin necesidad de entrada aquí.
    #
    # LF4 (PLAN_CONTRATO_COMPLETO_19-08.md §4.6, DA-47) vuelve a hacer
    # falta la entrada: el filtro dejó de ser incondicional (`uid="id"`
    # nombra UNA fila física y NO debe filtrar; `uid="ref"` selecciona un
    # BLOQUE y sí), y esa condición no cabe dentro del f-string -- vive en
    # la variable intermedia `filtro`. `_literal_str_ast` solo reconoce
    # `{FILTRO_ACTIVO}` cuando el hueco es una llamada literal a
    # `filtro_activo(...)`; un `Name` se marca `{DYN}`. Mismo caso, misma
    # solución que `load.py:2746-2747` (`filtro_t`/`filtro_p`): el sitio SÍ
    # filtra, el detector de texto no puede verlo, se documenta a mano.
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1730): "LF4/DA-47 (addsomething::consulta) -- filtra CONDICIONALMENTE por selectividad del WHERE: `filtro = filtro_activo(nombre_tabla) if uid != \"id\" else \"\"`. Con uid='ref' (SistemaMedicion/CondicionesMedicion, clave de BLOQUE) el filtro se aplica; con uid='id' (TipoCalibracion, fila física) se omite a propósito -- filtrar ahí vaciaría el formulario de una calibración anulada abierta a propósito. Invisible para el detector por ir en variable intermedia (igual que load.py:2746-2747). Cubierto por tests/test_lf4_braqui_lectura_identidad.py en las dos direcciones",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 264): "DO1 (subirlineasmensuales_ix -- SELECT del bloque vigente para componer el nuevo; ya filtra activo a mano, tabla dinámica)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 303): "DO1 (subirlineasmensuales_ix, rama fuera del bloque de QC)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 354): "DO1 (_cargar_dosimetria_bd_ix -- ya filtra activo a mano, tabla dinámica)",
    ("data/ManejoDatos/load.py", 2755): "tabla dinámica (_mostrar_tabla_generica -- módulo TAC/Catphan: 'config[\"tabla\"]' es una de las 7 hijas de TAC, PENDIENTE-LF hoy; JOIN literal con 'pruebas' (también PENDIENTE-LF). LF: corregido el gap que decía \"ninguna está en TABLAS_ANULABLES\" (cierto antes de LF2) -- ahora filtra las DOS con `filtro_t`/`filtro_p` calificados por alias, invisibles para el detector de texto por ir en variables intermedias)",
    # scripts/: excepciones censales explícitas (contrato regla 5) --
    # documentadas en cada archivo, no solo aquí.
    ("scripts/migrar_bd_a_estandar.py", 147): "migración/censo (_contar_qc)",
    ("scripts/migrar_bd_a_estandar.py", 179): "migración/censo (_contar_todas_las_tablas)",
    ("scripts/migrar_bd_a_estandar.py", 311): "migración/censo (_contar_catalogos_base)",
    ("scripts/observador_contrato.py", 154): "censo (OB1, censo.total -- cuenta TODAS las filas a propósito)",
    ("scripts/observador_contrato.py", 158): "censo (OB1, censo.activas -- calcula su propio filtro, no importa filtro_activo para no arrastrar PyQt5)",
    ("scripts/observador_contrato.py", 167): "censo (OB1, vigente -- mismo motivo)",
    ("scripts/saneamiento_bloque_qc.py", 80): "SA1/SA2 -- ya filtra 'activo' a mano en el WHERE (visible en el propio texto), no importa filtro_activo() para no arrastrar PyQt5 en un script que solo usa sqlite3",
    # LR4 (DA-48): los 8 `UPDATE {DYN}` que el detector no miraba hasta
    # ahora (ver PATRON_UPDATE_DINAMICO). Ninguno es una lectura de lista:
    # seis ESCRIBEN la anulación (poner `activo = 0` no puede filtrar por
    # `activo` sin volverse un no-op sobre lo ya anulado), uno edita UNA
    # celda por su id, y el octavo es una migración de formato de fecha.
    # EB2b (24-08) añadió un noveno -- ver más abajo.
    #
    # EB0/EB1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB0/EB1, DA-52, 24-08):
    # `anular_fila` dejó de escribir su `UPDATE` como un f-string inline
    # (JoinedStr, lo que la hacía "dinámica" para este detector) -- ahora
    # delega en `_SQL_ANULAR.format(...)`, un `ast.Call`. El texto y la
    # semántica NO cambiaron (sigue sin filtrar por vigencia: anular por
    # identidad ya selecciona una sola fila); lo que cambió es que el
    # detector ya no puede verlo -- pasa a `SITIOS_OPACOS_PERMITIDOS`, más
    # abajo, cubierto en tiempo de ejecución por RT1 (ve el SQL resuelto).
    # EB2b (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2b, 24-08, cierra §2.3):
    # noveno `UPDATE {DYN}` -- guardar_resultado_CambioFuente anula las 5
    # hijas del bloque ANTERIOR de TipoCalibracion (SistemaMedicion,
    # CondicionesMedicion, MaximosCamaras, LecturasMaximos,
    # ResultadosActividad), iterando sobre sus nombres en una tupla
    # literal. Escribe la anulación (`SET activo = 0`) sobre el `ref`
    # VIEJO que ya se localizó antes -- no es una lectura, filtrar el
    # propio UPDATE no tendría sentido (volvería un no-op sobre lo que
    # acaba de anular).
    ("data/ManejoDatos/load.py", 918): "guardar_resultado_CambioFuente (EB2b) -- anula las 5 hijas del bloque ANTERIOR de TipoCalibracion sobre su `ref` viejo; escritura de anulación, no lectura",
    ("data/ManejoDatos/load.py", 500): "eliminarfilas/subirlineas -- anula el bloque vigente antes de insertar el nuevo; YA filtra 'activo' a mano en el WHERE compuesto (línea 552)",
    ("data/ManejoDatos/load.py", 691): "subirlineasmensuales -- anula el bloque vigente de ese `ref`; ya filtra 'activo' a mano en el propio texto",
    ("data/ManejoDatos/load.py", 720): "subirlineasmensuales, rama FUERA del bloque de QC (`preguntas` antes de PR1 y las tablas sin columna `activo`): UPDATE parcial por `ref`, contrato original",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 283): "subirlineasmensuales_ix -- anula el bloque vigente de (ref, energia); ya filtra 'activo' a mano en el propio texto",
    ("scripts/saneamiento_bloque_qc.py", 116): "SA2 -- anula por `rowid` las filas duplicadas que perdieron el desempate: identidad física, una fila nombrada",
    ("ui/paginasControles/PruebasDiarias/PruebasDiarias.py", 826): "edición directa de UNA celda ya identificada (`WHERE id = ?`) -- identidad, no filtra (DA-47)",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 54): "censo/migración (normalizar_fechas_db): reescribe el FORMATO de `fecha` (DD-MM-YYYY -> YYYY-MM-DD) en las 6 tablas de braquiterapia. Tiene que alcanzar TAMBIÉN a las filas anuladas: una fila anulada con la fecha en el formato viejo la conserva para siempre, y es justo lo que obliga a `braq_mensual.py:1257` a consultar en los dos formatos (DP-32). Declarado también en la lista censal de RT1, que fue quien lo vio",
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
    ("data/ManejoDatos/load.py", 1466):
        "preguntas -- RP1: filtro_activo('preguntas') se califica con el "
        "alias 'p.' del LEFT JOIN antes de interpolarse (variable `filtro_p`, "
        "mismo patrón que consistencia_dosis.py)",
    ("data/ManejoDatos/load.py", 1469):
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
    ("models/PDF/Imagenes/reportes_control_sistema_imagenes.py", 326):
        "pruebas -- filtro_activo('pruebas') se califica con el alias 'p.' "
        "del JOIN (variable `filtro_p`) en _obtener_imagenes_blob",
    # LF1b (§6-LF1): 'pruebas' se une con LEFT JOIN a 'controles' (raíz) --
    # el filtro va en el ON, no en el WHERE (si fuera WHERE, un control sin
    # pruebas VIGENTES desaparecería de la lista en vez de mostrar
    # num_pruebas=0). Variable `filtro_p_on`, 5 funciones gemelas
    # (mostrar_controles_imgIX[_anual], mostrar_controles_imgHC[_anual],
    # mostrar_controles_tac), 2 sitios cada una (COUNT + SELECT MAX).
    ("data/ManejoDatos/load.py", 1741): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX_anual, COUNT)",
    ("data/ManejoDatos/load.py", 1775): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX_anual, SELECT MAX)",
    ("data/ManejoDatos/load.py", 1930): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX, COUNT)",
    ("data/ManejoDatos/load.py", 1978): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgIX, SELECT MAX)",
    ("data/ManejoDatos/load.py", 2136): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC_anual, COUNT)",
    ("data/ManejoDatos/load.py", 2170): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC_anual, SELECT MAX)",
    ("data/ManejoDatos/load.py", 2327): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC, COUNT)",
    ("data/ManejoDatos/load.py", 2375): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_imgHC, SELECT MAX)",
    ("data/ManejoDatos/load.py", 2528): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_tac, COUNT)",
    ("data/ManejoDatos/load.py", 2576): "pruebas -- filtro_p_on en el ON del LEFT JOIN (mostrar_controles_tac, SELECT MAX)",
    # MaximosCamaras JOIN TipoCalibracion (raíz) -- mismo patrón, variable
    # `filtro_mc` calificada con el alias 'mc.'. Dos hallazgos en la misma
    # línea (el analizador reporta 'sin filtro' y 'LIMIT sin ORDER BY' por
    # separado aunque sea un solo sitio revisado).
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2774): "MaximosCamaras (filtro_mc, alias 'mc.') Y TipoCalibracion (filtro_tc, alias 'tc.', añadido en LR3) -- graficar_maximos_camara; las dos calificadas en variables intermedias",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1594): "MaximosCamaras (filtro_mc) Y TipoCalibracion (filtro_tc, LR3) -- gemelo mensual del anterior",
    # LR3 (DA-48): sitios de RAÍZ que ganaron su filtro calificado por alias
    # -- mismo patrón de variable intermedia, ahora visibles para ES1 porque
    # LR4 metió las raíces en el alcance.
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 605): "TipoCalibracion -- filtro_tc calificado con el alias 'tc.' (_ejecutar_carga_calibracion: última fuente instalada antes de una fecha)",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2803): "LinealidadBraquiterapia -- filtro_lf calificado con el alias 'lf.' (graficar_linealidad_fuente)",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1623): "LinealidadBraquiterapia -- filtro_lf calificado con el alias 'lf.' (gemelo mensual de graficar_linealidad_fuente)",
}

# LR4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR4, [[DA-48]]): sitios de tabla
# LITERAL que leen las DOS ramas (vigente e histórica) A PROPÓSITO. Antes de
# LR4 no hacía falta declararlos porque tocaban una raíz y las raíces
# estaban fuera del alcance; ahora que el alcance es el bloque completo, la
# excepción tiene que quedar dicha -- que es justamente lo que DA-48 pide
# (tercera categoría de LR1: "no filtra, con excepción declarada y su
# razón"). Su clasificación completa vive en
# `tests/test_lr1_censo_raices_qc.py::CENSO_RAICES`.
#
# RT1 comparte estos dos sitios en su propia lista censal
# (`SITIOS_CENSALES_PERMITIDOS`) y un test cruzado exige que las dos listas
# sigan de acuerdo.
SITIOS_CENSALES_LITERALES = {
    ("scripts/migrar_bd_a_estandar.py", 121):
        "migración (_contar_centinela): cuenta las filas de `controles` con "
        "el centinela histórico de 2º físico (' ---- ') para decidir si hay "
        "que normalizarlas. Tiene que ver TODAS: una fila anulada con el "
        "dato mal sigue teniendo el dato mal, y filtrar dejaría el histórico "
        "a medio migrar.",
    ("scripts/migrar_bd_a_estandar.py", 339):
        "migración (el UPDATE que normaliza ese centinela a NULL): misma "
        "razón que la cuenta de arriba -- si la cuenta ve una fila y el "
        "UPDATE no, la migración se quedaría a medias sin avisar.",
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
#   - tabla no anulable: la tabla de destino no está en el alcance de AN1
#     (no está en TABLAS_ANULABLES ni en PENDIENTE-LF) -- el contenido
#     exacto del SQL no importa para este tripwire. Las 7 raíces ya NO
#     cuentan como excepción: LR4 (DA-48) las metió en el alcance.
#   - DO1: rama ya revisada en su momento, dynamic-table filtrado a mano
#     (`sql += filtro_activo(nombre_tabla)`, una llamada real, no un
#     literal -- por eso es opaca para el resolver aunque esté bien).
SITIOS_OPACOS_PERMITIDOS = {
    # EB0/EB1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB0/EB1, DA-52, 24-08):
    # tres sitios de `services/anulacion.py` cuyo SQL se arma detrás de un
    # `ast.Call` (función auxiliar), invisible para este detector estático
    # -- verificados a mano, y cubiertos en tiempo de ejecución por RT1
    # (ve el SQL ya resuelto sobre la conexión real).
    ("services/anulacion.py", 236): "anular_fila -- `_SQL_ANULAR.format(tabla=tabla, where=id_where)`. Mismo UPDATE de siempre (identidad física, sin filtro de vigencia -- ver el docstring de la función), ahora detrás de un helper compartido con sql_anular_bloque en vez de un f-string inline",
    ("services/anulacion.py", 338): "reemplazar_bloque (EB1) -- `sql_anular_bloque(tabla, columnas_clave)` compone el UPDATE con el AND de vigencia ya incluido (ver su propio docstring); es la ESCRITURA que anula el bloque anterior, no una lectura",
    # No hace falta entrada para `cursor.execute(sql_insert, fila)` (dentro
    # del bucle `for fila in filas`, más abajo -- reemplaza al `executemany`
    # original, ver el docstring de `reemplazar_bloque` sobre
    # `cursor.lastrowid`): `sql_insert` es un parámetro sin asignación en
    # el cuerpo de la función, el resolver de AN1 lo trata como texto vacío
    # -- no aparece en el censo de opacos (verificado, no es un hueco: el
    # INSERT lo arma cada llamador con columnas explícitas, MI0).
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", 875): "INSERT (linealidad_ct)",
    ("data/ManejoDatos/conection.py", 534): "DDL/migración (E10, tabla temporal de la migración CASCADE->RESTRICT)",
    ("data/ManejoDatos/conection.py", 1954): "INSERT (users, no está en TABLAS_ANULABLES)",
    ("data/ManejoDatos/load.py", 182): "INSERT (diarias -- tabla dinámica; un INSERT nunca elige entre filas existentes)",
    ("data/ManejoDatos/load.py", 331): "INSERT (controles -- un INSERT nunca necesita filtro)",
    ("data/ManejoDatos/load.py", 4189): "UPDATE por id_where -- identidad, edición directa de UNA celda ya identificada (equivalente al patrón 'identidad' de tablas dinámicas)",
    # LF (gap hallado por el subagente que resolvió LF3): decía "no está en
    # TABLAS_ANULABLES" -- cierto antes de LF2, falso después (PENDIENTE-LF).
    # Corregido: la sentencia ahora SÍ llama a `filtro_activo('ResultadosActividad')`
    # -- sigue "opaca" para AN1 no por el filtro sino porque `sql` se
    # reasigna en varias ramas de `guardarEdicion` (misma función que la
    # entrada anterior), irresoluble a propósito por diseño de AN1.
    ("data/ManejoDatos/load.py", 4269): "UPDATE ResultadosActividad -- ya filtra con filtro_activo('ResultadosActividad'); opaca a AN1 por reasignación de `sql` en varias ramas de guardarEdicion, no por falta de filtro",
    ("data/ManejoDatos/load.py", 4605): "DELETE por id_where -- rama de eliminarRegistro para tablas FUERA de TABLAS_ANULABLES (las anulables van por anular_fila, no llegan aquí)",
    ("data/ManejoDatos/obtenerDatosHalcyon.py", 397): "INSERT (halcyon -- un INSERT nunca necesita filtro)",
    ("services/dosis_service.py", 281): "DDL (CREATE TABLE calculadora_dosimetrica, no está en TABLAS_ANULABLES -- tiene su propia columna `vigente`, mecanismo de versionado independiente de este contrato)",
    ("services/dosis_service.py", 391): "INSERT (calculadora_dosimetrica, no está en TABLAS_ANULABLES)",
    ("services/dosis_service.py", 449): "SELECT calculadora_dosimetrica -- no está en TABLAS_ANULABLES (versiona con su propia columna `vigente`, no `activo`)",
    ("services/dosis_service.py", 550): "SELECT calculadora_dosimetrica -- mismo motivo",
    ("services/dosis_service.py", 556): "SELECT calculadora_dosimetrica -- mismo motivo",
    ("ui/paginasControles/PruebasAnuales/halcyon_anual.py", 303): "INSERT (HC_imagen_perfil_mlc_anual)",
    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py", 88): "INSERT (controles -- un INSERT nunca necesita filtro)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 289): "INSERT (subirlineasmensuales_ix, dentro del bucle de energías -- reasignación de `sql` en cada vuelta, irresoluble a propósito por AN1; INSERT no necesita filtro de todos modos)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 309): "INSERT (subirlineasmensuales_ix, rama fuera del bloque de QC -- ver comentario en el propio archivo)",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py", 323): "UPDATE por (ref, energia) -- subirlineasmensuales_ix, rama fuera del bloque de QC (nombre_tabla no anulable en esta rama)",
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 3609): "DO1 (pruebatalas -- `sql += filtro_activo(nombre_tabla)` es una llamada real, no un literal; ya documentado en el propio archivo como filtrado a mano)",
    ("ui/paginasGuia/SQLtoEXCEL.py", 517): "LR3 (DA-48): la consulta compañera de `pelicula` YA filtra con filtro_activo('braqui') -- sigue opaca al AST porque `query` se reasigna en varias ramas dentro del bucle de exportación, no por falta de filtro",
}


def _archivos_produccion():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


PATRON_FROM_DINAMICO = re.compile(r'FROM\s+"?\{DYN\}"?', re.IGNORECASE)
# LR4 (DA-48): hueco de ES1 destapado al meter las raíces en el alcance --
# el detector de tabla dinámica solo miraba `FROM {DYN}`, así que un
# `UPDATE {DYN}` sobre una tabla versionada no se contaba NI como sitio
# dinámico ni como violación: era invisible por completo. Lo encontró RT1
# (que ve el SQL resuelto) en `braq_mensual.py::normalizar_fechas_db`.
# Son 8 sitios, todos revisados en `SITIOS_DINAMICOS_PERMITIDOS`.
PATRON_UPDATE_DINAMICO = re.compile(r'UPDATE\s+"?\{DYN\}"?', re.IGNORECASE)


def _censar():
    """Recorre todo el árbol de producción una vez y devuelve un dict con:
      fallos: violaciones nuevas de AN1 sobre tabla literal (hard failures)
      dinamicos: sitios de tabla dinámica sin autoprotección
      opacos: sitios donde ni el literal ni el resolver de AN1 alcanzan
      excepciones_encontradas: cuáles de EXCEPCIONES_LITERALES siguen ahí
      censales_encontrados: cuáles de SITIOS_CENSALES_LITERALES siguen ahí
    """
    tablas = lv.tablas_del_bloque_qc()
    fallos = []
    dinamicos = set()
    opacos = set()
    excepciones_encontradas = set()
    censales_encontrados = set()

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

                    if (PATRON_FROM_DINAMICO.search(texto)
                            or PATRON_UPDATE_DINAMICO.search(texto)):
                        if "{filtro_activo}" not in texto.lower():
                            dinamicos.add(clave)
                        continue

                    hallazgos = lv.analizar(texto, tablas)
                    if not hallazgos:
                        continue
                    if clave in EXCEPCIONES_LITERALES:
                        excepciones_encontradas.add(clave)
                        continue
                    if clave in SITIOS_CENSALES_LITERALES:
                        censales_encontrados.add(clave)
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
        "censales_encontrados": censales_encontrados,
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


def test_sitios_censales_literales_siguen_existiendo():
    """LR4: si una excepción censal deja de aparecer (porque el sitio ganó
    su filtro, cambió de línea o se retiró), la entrada sobra -- una lista
    de excepciones que nadie limpia deja de ser revisable, que es
    exactamente cómo las raíces llegaron a 27/50."""
    resultado = _censar()
    ausentes = set(SITIOS_CENSALES_LITERALES) - resultado["censales_encontrados"]
    assert not ausentes, (
        f"Excepción censal literal que ya no aparece en el censo -- "
        f"límpiala de SITIOS_CENSALES_LITERALES: {ausentes}")


def test_cada_excepcion_censal_literal_declara_su_razon():
    for sitio, razon in SITIOS_CENSALES_LITERALES.items():
        assert len(razon) > 40, f"{sitio} sin razón documentada"
