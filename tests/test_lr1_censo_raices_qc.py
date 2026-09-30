"""LR1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR1, [[DA-48]]): censo y
clasificación de TODAS las lecturas/escrituras SQL sobre las 7 raíces de
proceso del bloque de QC (`controles`, `TipoCalibracion`,
`LinealidadBraquiterapia`, `aceleradorlineal_600`, `aceleradorlineal_ix`,
`halcyon`, `braqui`).

Por qué existe este archivo y no basta con ES1: hasta DA-48 las 7 raíces
estaban FUERA del alcance del analizador (se restaban en
`tablas_del_bloque_qc()`, entonces llamada `tablas_hijas_del_bloque_qc()`,
artefacto de que [[DP-31]] siguiera abierta), y eso es lo que permitió que
llegaran a ~27 sitios filtrando y ~50 sin filtrar **sin ningún criterio
declarado** que distinguiera unos de otros. LR4 retiró la exclusión: ES1 y
RT1 ya vigilan las raíces igual que al resto del bloque, y este archivo
guarda la CLASIFICACIÓN una a una, que ningún analizador puede derivar
solo.
El censo del 20-08 midió 77 filas; este archivo las clasifica **una por
una** según [[DA-47]] -- el filtro se decide por la SELECTIVIDAD del
`WHERE`, no por la tabla -- y se queda como tripwire permanente: un sitio
nuevo sobre una raíz que no esté aquí pone el test en rojo.

Tres categorías, exhaustivas y excluyentes (§6-LR1 del plan):

  - `IDENTIDAD`: el `WHERE` (o el `ON` del JOIN que la trae) nombra UNA
    fila física por su clave primaria (`id`/`rowid`). **No filtra**: ahí el
    filtro no elige la generación vigente, convierte "la fila que pediste"
    en "nada" -- vaciaría el formulario de un registro que el físico abrió
    a propósito sabiendo que está anulado (es el defecto que LF4 corrigió
    en `braq_mensual.py`).
  - `LISTA`: el `WHERE` puede devolver varias generaciones del mismo bloque
    (catálogo completo, `WHERE equipo = ?`, `WHERE date = ?`, sin `WHERE`).
    **Filtra**: si no, un registro anulado se cuela en una lista de
    vigentes.
  - `CENSO`: lee las dos ramas (vigente e histórica) A PROPÓSITO --
    migración, auditoría, o la reactivación de [[DA-34]]. **No filtra**,
    con la razón declarada aquí mismo.

**Por qué el censo tiene que sumar exactamente 77 sin residuo** (protocolo
de verificación de LR1): un sitio que no cayera limpiamente en una de las
tres es un sitio que no se entendió. Clasificarlo por descarte es
justamente cómo se llegó al 27/50 sin criterio.

Nota de conteo: 77 FILAS del analizador sobre 75 sitios físicos --
`load.py:1488` y `load.py:1491` (`mostrar_controles_mensuales`) arman su
SQL con un `if/else`, así que AN1 resuelve DOS textos posibles para cada
uno y los cuenta por separado. Es el mismo 77 = 27 con filtro + 50 sin
filtro que midió el censo del 20-08.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import lectura_vigente as lv  # noqa: E402
from test_le4_lecturas_filtran_activo import (  # noqa: E402
    EXEC_METHODS, _archivos_produccion)

IDENTIDAD = "identidad"
LISTA = "lista"
CENSO = "censo"

RAICES = lv.RAICES_QC


# ---------------------------------------------------------------------------
# EL CENSO. Clave: (archivo, línea del execute/prepare, tabla raíz tocada).
# Valor: (categoría, razón). La razón no es decorado: es lo que permite
# revisar la clasificación sin volver a leer los 75 sitios.
# ---------------------------------------------------------------------------
CENSO_RAICES = {
    # -- B.2 (PLAN_REFERENCIAS_EDITABLES_21-09.md) -----------------------
    # -- F.2 (PLAN_HANDOFF_IMAGENES_22-09.md) -----------------------------
    ("services/referencias_qc.py", 163, "controles"):
        (LISTA, "_historico_calidad: `ref IN (SELECT id FROM controles WHERE "
         "LOWER(equipo) = LOWER(?))` -- los controles VIGENTES de un equipo (varias "
         "generaciones posibles, una por mes), para leer con qué referencia de "
         "calidad se guardó cada uno; filtra activo con filtro_activo('controles') "
         "dentro del f-string, y el de dosimetriaMen en la consulta de fuera"),
    ("services/referencias_qc.py", 216, "referencias_qc"):  # F.1 (25-09): 70->127; F.2 (25-09): 127->216
        (LISTA, "leer_referencia: WHERE equipo=? AND magnitud=? AND energia=? "
         "-- la CLAVE DE BLOQUE completa (no una fila física), así que filtra "
         "activo con filtro_activo() dentro del propio f-string"),
    ("services/referencias_qc.py", 229, "referencias_qc"):  # F.1 (25-09): 83->140; F.2 (25-09): 140->229
        (LISTA, "listar_vigentes: lista TODAS las referencias vigentes para "
         "la pestaña; filtra activo con filtro_activo() en el f-string"),
    ("services/referencias_qc.py", 244, "referencias_qc"):  # F.1 (25-09): 98->155; F.2 (25-09): 155->244
        (CENSO, "historial: lee las filas vigentes E históricas de una clave "
         "de bloque A PROPÓSITO -- es el rastro de quién cambió qué y cuándo "
         "(paso 8 de la puerta de salida); filtrar activo lo dejaría vacío"),
    # -- T.4 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §5) ----------------
    ("services/contexto_auditoria.py", 133, "controles"):
        (IDENTIDAD, "visor de auditoría -- WHERE id IN (...) resuelve por "
         "LOTE un grupo de filas de `controles`, cada una nombrada por su "
         "propia clave física; DA-47 exige que un control ANULADO siga "
         "identificándose en su propio rastro de auditoría"),
    ("services/contexto_auditoria.py", 141, "TipoCalibracion"):
        (IDENTIDAD, "visor de auditoría -- misma razón que la línea 133, "
         "sobre TipoCalibracion (una calibración anulada también debe "
         "seguir identificándose en su rastro)"),
    # -- Tablas anuales -------------------------------------------------
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", 111, "controles"):
        (LISTA, "catálogo de controles anuales de un equipo -- varias filas"),
    ("data/ManejoDatos/Tablas_Anuales/tablas_anuales.py", 114, "controles"):
        (LISTA, "catálogo de controles anuales, todos los equipos"),

    # -- data/ManejoDatos/load.py ---------------------------------------
    ("data/ManejoDatos/load.py", 243, "braqui"):
        (IDENTIDAD, "abrir_pelicula: WHERE id = ? -- la fila ya elegida en "
                    "la tabla; filtrar la haría desaparecer del visor"),
    ("data/ManejoDatos/load.py", 325, "controles"):
        (LISTA, "create_control -- reclasificado por LR7 (DA-49): hasta "
                "entonces era CENSO (leía activo como dato para ofrecer "
                "reactivar, N1/DA-34). Con la reactivación retirada, esta "
                "lectura vuelve a ser una lectura de bloque cualquiera -- "
                "filtra, y un control anulado del mes se ignora sin más; "
                "create_control crea uno nuevo al lado"),
    ("data/ManejoDatos/load.py", 341, "controles"):
        (IDENTIDAD, "UPDATE de los físicos sobre el control ya localizado, "
                    "WHERE id = ?"),
    ("data/ManejoDatos/load.py", 1044, "TipoCalibracion"):
        (LISTA, "guardar_resultado_CambioFuente: busca por (fecha, tipo) -- "
                "sin filtro, una calibración ANULADA de esa fecha se "
                "reutilizaría como bloque a superar. EB2b (24-08): ahora "
                "solo se USA el `ref` que devuelve (para anular las 5 "
                "hijas del bloque anterior) -- el UPDATE-en-sitio que "
                "vivía justo debajo (antiguo load.py:895) desapareció, "
                "reemplazado por `reemplazar_bloque` (services/"
                "anulacion.py, opaco para este censo -- SQL armado detrás "
                "de un ast.Call)"),
    ("data/ManejoDatos/load.py", 1199, "LinealidadBraquiterapia"):
        (LISTA, "catálogo completo de linealidades de braquiterapia"),
    ("data/ManejoDatos/load.py", 1313, "TipoCalibracion"):
        (LISTA, "catálogo completo de calibraciones (el sitio que ya "
                "filtraba bien y que hizo decidible DP-31)"),
    ("data/ManejoDatos/load.py", 1655, "controles"):
        (LISTA, "mostrar_controles_mensuales, rama con equipo filtrado"),
    ("data/ManejoDatos/load.py", 1658, "controles"):
        (LISTA, "mostrar_controles_mensuales, rama sin equipo filtrado"),
    ("data/ManejoDatos/load.py", 1931, "controles"):
        (LISTA, "mostrar_controles_imgIX_anual: COUNT de pruebas por control"),
    ("data/ManejoDatos/load.py", 1965, "controles"):
        (LISTA, "mostrar_controles_imgIX_anual: SELECT MAX de parámetros"),
    ("data/ManejoDatos/load.py", 2120, "controles"):
        (LISTA, "mostrar_controles_imgIX: COUNT de pruebas por control"),
    # RETIRADA el 01-09 (A9, PLAN_FUGA_CONEXIONES_01-09.md §9): vivía
    # aquí como ("data/ManejoDatos/load.py", 2143, "controles"), LISTA,
    # "mostrar_controles_imgIX: SELECT MAX de parámetros" -- A9 envolvió
    # el cuerpo de mostrar_controles_imgIX en un `with Conexion().
    # conectar() as conn:` y censar_raices() (línea ~358: "if textos is
    # None: continue") deja de ver el sitio en cuanto `query` se vuelve
    # irresoluble para _rastrear_variable (Trampa 6, mismo punto ciego
    # que A7). El sitio SIGUE ahí y sigue filtrando -- solo el analizador
    # de este archivo perdió visibilidad; ver test_eb5/test_le4 para la
    # entrada equivalente, movida a su lista de OPACOS en vez de borrada.
    ("data/ManejoDatos/load.py", 2325, "controles"):
        (LISTA, "mostrar_controles_imgHC_anual: COUNT de pruebas por control"),
    ("data/ManejoDatos/load.py", 2359, "controles"):
        (LISTA, "mostrar_controles_imgHC_anual: SELECT MAX de parámetros"),
    ("data/ManejoDatos/load.py", 2516, "controles"):
        (LISTA, "mostrar_controles_imgHC: COUNT de pruebas por control"),
    # RETIRADA el 01-09 (A10, PLAN_FUGA_CONEXIONES_01-09.md §9): mismo
    # motivo que A9 (2119) -- ("data/ManejoDatos/load.py", 2539,
    # "controles"), LISTA, "mostrar_controles_imgHC: SELECT MAX de
    # parámetros". Ver test_eb5/test_le4 para la entrada equivalente.
    ("data/ManejoDatos/load.py", 2716, "controles"):
        (LISTA, "mostrar_controles_tac: COUNT de pruebas por control"),
    # RETIRADA el 01-09 (A11, PLAN_FUGA_CONEXIONES_01-09.md §9): mismo
    # motivo que A9 (2119) -- ("data/ManejoDatos/load.py", 2739,
    # "controles"), LISTA, "mostrar_controles_tac: SELECT MAX de
    # parámetros". Ver test_eb5/test_le4 para la entrada equivalente.
    ("data/ManejoDatos/load.py", 4566, "controles"):
        (IDENTIDAD, "eliminarRegistroCT: captura la fila ANTES de anularla "
                    "(A2, evidencia de auditoría), WHERE id = ?"),
    ("data/ManejoDatos/load.py", 4580, "controles"):
        (IDENTIDAD, "la anulación misma: UPDATE ... SET activo = 0 WHERE "
                    "id = ? -- el `activo` va en el SET, no es un filtro"),
    ("data/ManejoDatos/load.py", 4643, "controles"):
        (IDENTIDAD, "gemelo anual exacto de eliminarRegistroCT (captura la "
                    "fila antes de anularla, WHERE id = ?)"),
    ("data/ManejoDatos/load.py", 4653, "controles"):
        (IDENTIDAD, "gemelo anual exacto de eliminarRegistroCT (la anulación "
                    "misma, UPDATE ... SET activo = 0 WHERE id = ?)"),
    ("data/ManejoDatos/load.py", 4866, "TipoCalibracion"):
        (IDENTIDAD, "datos de la calibración ya elegida, WHERE id = ?"),

    # -- Halcyon ---------------------------------------------------------
    ("data/ManejoDatos/obtenerDatosHalcyon.py", 206, "halcyon"):
        (LISTA, "_fecha_ya_importada: '¿existe reporte de esta fecha?' -- "
                "gemelo sin filtrar de load.py:214, que sí filtra desde D3"),

    # -- models/PDF ------------------------------------------------------
    ("models/PDF/Anual/reportes_anuales.py", 140, "controles"):
        (LISTA, "referencia del control ANUAL por (fecha, equipo, control)"),
    ("models/PDF/Imagenes/reportes_control_sistema_imagenes.py", 206, "controles"):  # E.3 (24-09): 199->201; E.2 (24-09): 201->204; G.3 (24-09): 204->205; B.3 (25-09): 205->206
        (LISTA, "referencia del control MENSUAL por (fecha, equipo, control)"),
    ("models/PDF/Imagenes/reportes_control_sistema_imagenes.py", 256, "controles"):  # E.3 (24-09): 249->251; E.2 (24-09): 251->254; G.3 (24-09): 254->255; B.3 (25-09): 255->256
        (IDENTIDAD, "_obtener_info_sesion del PDF de imágenes: WHERE c.id = ?"),
    ("models/PDF/Imagenes/reportes_control_sistema_imagenes.py", 432, "controles"):  # E.3 (24-09): 413->417; E.2 (24-09): 417->428; G.3 (24-09): 428->431; B.3 (25-09): 431->432
        (IDENTIDAD, "_obtener_datos_tabla_principal del PDF: WHERE id = ?"),
    ("models/PDF/Mensuales/reportes_mensuales.py", 166, "controles"):
        (LISTA, "referencia del control MENSUAL por (fecha, equipo, control)"),
    ("models/PDF/Mensuales/reportes_mensuales.py", 180, "LinealidadBraquiterapia"):
        (LISTA, "referencia de linealidad de braquiterapia por fecha"),
    ("models/PDF/Mensuales/reportes_mensuales.py", 188, "TipoCalibracion"):
        (LISTA, "referencia de braquiterapia por (fecha, tipo de control)"),
    ("models/PDF/Mensuales/reportes_mensuales.py", 200, "TipoCalibracion"):
        (LISTA, "referencia de braquiterapia por fecha, sin mirar el tipo"),
    ("models/PDF/Mensuales/reportes_mensuales.py", 245, "controles"):
        (IDENTIDAD, "datos del control ya referenciado, WHERE id = ?"),
    ("models/PDF/Mensuales/reportes_mensuales.py", 262, "TipoCalibracion"):
        (IDENTIDAD, "datos de la calibración ya referenciada, WHERE id = ?"),
    ("models/PDF/Mensuales/reportes_mensuales.py", 285, "LinealidadBraquiterapia"):
        (IDENTIDAD, "datos de la linealidad ya referenciada, WHERE id = ?"),

    # -- scripts ---------------------------------------------------------
    ("scripts/migrar_bd_a_estandar.py", 121, "controles"):
        (CENSO, "migración (_contar_centinela): cuenta las filas con el "
                "centinela histórico de 2º físico para saber si hay que "
                "normalizarlas. Tiene que ver TODAS -- una fila anulada con "
                "el centinela sigue teniendo el dato mal y hay que "
                "arreglarlo igual"),
    ("scripts/migrar_bd_a_estandar.py", 355, "controles"):
        (CENSO, "migración (UPDATE que normaliza el centinela a NULL): "
                "misma razón que la cuenta de arriba -- filtrar dejaría el "
                "histórico a medio migrar, que es peor que no migrarlo"),

    # -- services --------------------------------------------------------
    ("services/consistencia_dosis.py", 51, "controles"):
        (IDENTIDAD, "JOIN controles c ON c.id = d.ref -- la raíz entra por "
                    "su clave primaria, UNA fila por cada fila de "
                    "dosimetriaMen. Es la segunda forma de identidad de "
                    "DA-47 (el predicado va en el ON, no en el WHERE); el "
                    "filtro que sí lleva esta consulta es el de "
                    "dosimetriaMen, que sí es una lectura de bloque"),
    ("services/duplicados_control.py", 25, "controles"):
        (LISTA, "U1: agrupa las filas ACTIVAS para detectar duplicados de "
                "(equipo, control, mes) -- tiene que filtrar precisamente "
                "porque el índice UNIQUE de U2 es PARCIAL sobre las activas. "
                "NB: la nota de LR1 en el plan del 19-08 dice que este sitio "
                "'es censo permanente: se queda sin filtro'; es incorrecta y "
                "lo era ya al escribirse -- el sitio filtra desde su commit "
                "de origen (U1, 1a1ad44) y debe seguir filtrando"),
    # services/reactivacion.py (3 sitios, DA-34) -- RETIRADO por LR7
    # ([[DA-49]]): el archivo entero desapareció junto con el mecanismo de
    # reactivación. No hay nada que censar donde ya no hay código.
    ("services/ventana_edicion.py", 78, "controles"):  # R.5 (11-09): 67->78
        (IDENTIDAD, "fecha del control pedido por id (respaldo cuando no "
                    "hay marca de auditoría)"),
    ("services/ventana_edicion.py", 111, "controles"):  # R.5 (11-09): 100->111
        (IDENTIDAD, "_estado_control (W1): lee `activo` como DATO para "
                    "distinguir 'no existe' de 'existe pero anulado'. "
                    "Filtrar aquí borraría justo la distinción que la "
                    "función existe para hacer"),

    # -- ui/PruebasAnuales -----------------------------------------------
    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py", 60, "controles"):
        (LISTA, "create_control anual: busca el control del año por "
                "(fecha LIKE, equipo). Gemelo del mensual (load.py:296) sin "
                "la clasificación de DA-34 -- ver DP-27"),
    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py", 75, "controles"):
        (IDENTIDAD, "UPDATE de los físicos sobre el control ya localizado"),

    # -- ui/PruebasDiarias -----------------------------------------------
    ("ui/paginasControles/PruebasDiarias/IX.py", 269, "aceleradorlineal_ix"):
        (LISTA, "reporte diario del Clinac iX por fecha"),
    ("ui/paginasControles/PruebasDiarias/IX.py", 448, "aceleradorlineal_ix"):
        (LISTA, "serie temporal del Clinac iX por rango de fechas"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 404, "braqui"):
        (LISTA, "reporte diario de braquiterapia por fecha"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 878, "TipoCalibracion"):
        (LISTA, "última fuente instalada antes de una fecha dada"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 1817, "braqui"):
        (LISTA, "serie temporal de actividad por rango de fechas"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 1856, "braqui"):
        (LISTA, "serie temporal de ciclos de braqui por rango de fechas"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2084, "TipoCalibracion"):  # V.4 (28-09): 2076->2081
        (LISTA, "última fecha registrada con tipo 'Cambio de fuente'"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2103, "TipoCalibracion"):  # V.4 (28-09): 2095->2100
        (LISTA, "datos de la calibración de braquiterapia de esa fecha"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2184, "TipoCalibracion"):  # V.4 (28-09): 2176->2181
        (LISTA, "última fecha con tipo 'Cambio de fuente' (2ª copia del mismo patrón)"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2566, "LinealidadBraquiterapia"):  # V.4 (28-09): 2558->2563
        (LISTA, "linealidad de la fuente de braquiterapia por fecha"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2929, "LinealidadBraquiterapia"):  # V.4 (28-09): 2905->2910
        (LISTA, "linealidad por fecha para el PDF -- ya filtraba (el sitio "
                "que fijó el patrón: filtro + ORDER BY id DESC)"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 3512, "TipoCalibracion"):  # V.4 (28-09): 3436->3441; L.3 (28-09): 3495->3512
        (LISTA, "JOIN a la calibración de una fecha para graficar máximos -- "
                "el WHERE es DATE(tc.fecha), no tc.id: es lectura de bloque"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 3541, "LinealidadBraquiterapia"):  # V.4 (28-09): 3465->3470; L.3 (28-09): 3524->3541
        (LISTA, "linealidad de la fuente por fecha, para la gráfica"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 3831, "TipoCalibracion"):  # V.4 (28-09): 3755->3760; L.3 (28-09): 3814->3831
        (LISTA, "actualizar_ref_bd: id de la calibración registrada esa fecha"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 4307, "braqui"):  # V.4 (28-09): 4231->4236; L.3 (28-09): 4290->4307
        (LISTA, "serie temporal de actividad (2ª copia del mismo patrón)"),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 4346, "braqui"):  # V.4 (28-09): 4270->4275; L.3 (28-09): 4329->4346
        (LISTA, "serie temporal de ciclos (2ª copia del mismo patrón)"),
    ("ui/paginasControles/PruebasDiarias/seiscientos.py", 187, "aceleradorlineal_600"):
        (LISTA, "reporte diario del Clinac 600 por fecha"),

    # -- ui/PruebasMensuales ---------------------------------------------
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 149, "TipoCalibracion"):
        (LISTA, "actualizar_ref_bd: id de la calibración registrada esa fecha"),
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1193, "TipoCalibracion"):  # V.5 (28-09): 1109->1184; P.1 (28-09): 1184->1194; RC.1 (30-09): 1194->1193
        (LISTA, "última calibración registrada con tipo 'Cambio de fuente'"),
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1207, "TipoCalibracion"):  # V.5 (28-09): 1123->1198; P.1 (28-09): 1198->1208; RC.1 (30-09): 1208->1207
        (IDENTIDAD, "datos de la calibración ya localizada, WHERE id = ?"),
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1429, "TipoCalibracion"):  # V.5 (28-09): 1344->1419; P.1 (28-09): 1419->1430; RC.1 (30-09): 1430->1429
        (LISTA, "calibración por fecha, admitiendo los dos formatos (DP-32)"),
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1832, "TipoCalibracion"):  # V.5 (28-09): 1747->1822; P.1 (28-09): 1822->1833; RC.1 (30-09): 1833->1832
        (LISTA, "gemelo mensual exacto de braquiterapia.py:3038"),  # V.4 (28-09): 3033->3038
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 1861, "LinealidadBraquiterapia"):  # V.5 (28-09): 1776->1851; P.1 (28-09): 1851->1862; RC.1 (30-09): 1862->1861
        (LISTA, "gemelo mensual exacto de braquiterapia.py:3067"),  # V.4 (28-09): 3062->3067
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 273, "controles"):  # A.2 (21-09): 256->269; B.3 (21-09): 269->270; C.1 (25-09): 270->273
        (LISTA, "actualizar_fisicos: WHERE equipo = ? y desempata el mes en "
                "Python -- un control anulado del mes prestaría sus físicos"),
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 561, "controles"):  # A.2 (21-09): 544->557; B.3 (21-09): 557->558; C.1 (25-09): 558->561
        (IDENTIDAD, "_fecha_real_del_control (F3): WHERE id = ?, fila ya elegida"),
    ("ui/paginasControles/PruebasMensuales/tac_mensual.py", 167, "controles"):  # A.2 (23-09): 164->165; G.2 (24-09): 165->166; G.3 (24-09): 166->167
        (IDENTIDAD, "_existe_ref: WHERE id = ? AND equipo = ? -- el id ya "
                    "nombra la fila; el equipo es una guarda, no un "
                    "selector"),
}

# Filas del analizador (77) frente a sitios físicos (75): los dos sitios que
# arman su SQL con un if/else y por eso resuelven a DOS textos.
# LR7 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR7, [[DA-49]]) retiró
# services/reactivacion.py entero -- 3 sitios menos que el censo original
# del 20-08 (77 filas / 75 sitios). `create_control` (antes CENSO, ahora
# LISTA) no se resta: sigue siendo un sitio, solo cambió de categoría.
# EB2b (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2b, 24-08) retiró el
# `UPDATE TipoCalibracion SET ... WHERE id=?` (antiguo load.py:895) -- ese
# sitio en sí (una fila física) desaparece del censo; lo reemplaza
# `reemplazar_bloque` (services/anulacion.py), invisible para este
# analizador (SQL armado detrás de un `ast.Call`). Un sitio menos: 74 -> 73.
# A9 (PLAN_FUGA_CONEXIONES_01-09.md §9, 01-09): `mostrar_controles_imgIX`
# (load.py:2119, el SELECT MAX final) queda invisible para este analizador
# -- A9 envolvió el cuerpo en un `with Conexion().conectar() as conn:` y
# `_rastrear_variable` da la variable `query` por irresoluble en cuanto se
# la toca dentro de un `ast.With` (Trampa 6, mismo punto ciego que A7). El
# sitio SIGUE filtrando -- solo dejó de ser visible aquí. Un sitio menos:
# 73 -> 72.
# A10 (mismo día, mismo motivo): gemelo exacto sobre `mostrar_controles_
# imgHC` (load.py:2515). Un sitio menos: 72 -> 71.
# A11 (mismo día, mismo motivo): tercer gemelo, `mostrar_controles_tac`
# (load.py:2715). Un sitio menos: 71 -> 70.
# B.2 (PLAN_REFERENCIAS_EDITABLES_21-09.md, 21-09): `referencias_qc` es la
# quinta raíz nueva y su servicio (`services/referencias_qc.py`) lee de ella
# en 3 sitios (leer_referencia, listar_vigentes, historial): 72 -> 75 filas,
# 70 -> 73 sitios físicos.
FILAS_ESPERADAS = 76      # F.2 (25-09): +1, `referencias_qc.py::_historico_calidad` (LISTA sobre `controles`)
SITIOS_FISICOS_ESPERADOS = 74      # F.2 (25-09): +1 (el mismo sitio de `_historico_calidad`)

# La lista de trabajo de LR3, ya VACÍA: los 31 sitios de LISTA que no
# llevaban filtro lo llevan desde LR3. Nunca fue una lista blanca
# permanente -- el test de abajo exige que cada entrada sea de LISTA y que
# siga sin filtrar, así que no puede usarse para tapar un sitio mal
# clasificado, y al vaciarse `test_todo_sitio_de_lista_filtra` pasa a
# exigir el filtro en los 51 sin excepción.
PENDIENTES_LR3 = frozenset()


def _refs_con_activo():
    """Tablas que tienen (o tendrán en MI1) columna `activo`: el alcance de
    vigilancia MÁS las 7 raíces. Sirve para decidir si un `activo` sin
    calificar de la sentencia puede pertenecer a OTRA tabla -- el hueco 4
    de LE4."""
    return lv.tablas_anulables() | lv.tablas_pendientes_lf()


def censar_raices():
    """Recorre el árbol de producción con el MISMO criterio que ES1 (AST, no
    grep; literales y SQL resuelto desde variable) y devuelve una fila por
    cada referencia a una raíz encontrada en un `execute`/`prepare`.

    Cada fila: (archivo, línea, tabla, alias, filtra, es_identidad, sql).
    `filtra` mira SOLO desde el `WHERE` en adelante -- un `SET activo = 0`
    (la anulación) o un `SELECT activo` (leerlo como dato) NO son filtros de
    lectura, y contarlos como tales fue lo que infló el 27 del censo
    original."""
    con_activo = _refs_con_activo()
    claves = lv.claves_indice()
    filas = []
    for rel, path in _archivos_produccion():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:                       # pragma: no cover
            continue
        # Una función ANIDADA se recorre dos veces (como descendiente de la
        # exterior y como FunctionDef propia): sin esta marca, los 6 sitios
        # que viven en closures -- `graficar_maximos_camara`,
        # `graficar_linealidad_fuente`, `consulta_db` -- se contarían por
        # duplicado y el censo daría 83 en vez de 77.
        vistos = set()
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
                if (node.lineno, node.col_offset) in vistos:
                    continue
                vistos.add((node.lineno, node.col_offset))
                arg0 = node.args[0]
                if isinstance(arg0, (ast.Constant, ast.JoinedStr)):
                    textos = [lv._literal_str_ast(arg0)]
                elif isinstance(arg0, ast.Name):
                    textos = lv.resolver_argumento_execute(func, node)
                    if textos is None:
                        continue
                else:
                    continue
                indirectos = _filtros_indirectos(func)
                for texto in textos:
                    if texto is None:
                        continue
                    filas.extend(_filas_del_texto(
                        str(rel), node.lineno, texto, con_activo, claves,
                        indirectos))
    return filas


def _filtros_indirectos(func):
    """{(tabla, alias)} para los que ESTA función guarda el filtro en una
    variable intermedia antes de interpolarlo:

        filtro_tc = filtro_activo('TipoCalibracion').replace("activo", "tc.activo")

    Es el patrón que el proyecto ya usa cuando el filtro tiene que quedar
    CALIFICADO con el alias de un JOIN (`consistencia_dosis.py:51`,
    `load.py::mostrar_controles_mensuales`, `catphan_db.py`...): el filtro
    está aplicado de verdad, pero `_literal_str_ast` solo reconoce
    `{FILTRO_ACTIVO}` cuando el hueco del f-string es una llamada LITERAL a
    `filtro_activo(...)`, y aquí el hueco es un `Name` -- se marca `{DYN}`.
    ES1 lo resuelve con `EXCEPCIONES_LITERALES`, una lista escrita a mano;
    aquí se DERIVA del AST, así que un sitio nuevo con este patrón se
    reconoce solo y uno que pierda el `.replace()` deja de reconocerse.

    Se exige que el segundo argumento de `.replace()` sea exactamente
    `"<alias>.activo"`: así el filtro de OTRA tabla del mismo JOIN no puede
    hacerse pasar por el de esta (hueco 4 de LE4)."""
    encontrados = set()
    for nodo in ast.walk(func):
        if not isinstance(nodo, ast.Call):
            continue
        if not (isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "replace" and len(nodo.args) == 2):
            continue
        interior = nodo.func.value
        if not (isinstance(interior, ast.Call)
                and isinstance(interior.func, ast.Name)
                and interior.func.id == "filtro_activo"
                and len(interior.args) == 1
                and isinstance(interior.args[0], ast.Constant)):
            continue
        destino = nodo.args[1]
        if not (isinstance(destino, ast.Constant)
                and isinstance(destino.value, str)
                and destino.value.endswith(".activo")):
            continue
        encontrados.add((interior.args[0].value,
                         destino.value[:-len(".activo")]))
    return encontrados


def _fragmentos(sql):
    exterior, subs = lv._extraer_subconsultas(sql)
    salida = [exterior]
    for s in subs:
        salida.extend(_fragmentos(s))
    return salida


def _filas_del_texto(rel, lineno, texto, con_activo, claves, indirectos=()):
    filas = []
    for frag in _fragmentos(texto):
        refs = lv._tablas_referenciadas(frag)
        refs_raiz = {a: t for a, t in refs.items() if t in RAICES}
        if not refs_raiz:
            continue
        # `unica` con el criterio de AN1 (hueco 4): un `activo` sin
        # calificar solo vale como filtro si NO hay otra tabla con columna
        # `activo` en la misma sentencia que pudiera ser su dueña.
        unica = len([t for t in refs.values() if t in con_activo]) == 1
        where = lv._texto_desde_where(frag)
        for alias, tabla in refs_raiz.items():
            directo = bool(where) and lv._filtro_presente(where, alias, unica)
            # El filtro por variable intermedia solo cuenta si el `{DYN}` que
            # lo interpola está DESPUÉS del WHERE -- ahí es donde filtra.
            indirecto = ((tabla, alias) in indirectos
                         and bool(where) and "{DYN}" in where)
            filas.append((
                rel, lineno, tabla, alias,
                directo or indirecto,
                bool(where) and lv._es_lectura_de_identidad(
                    where, alias, tabla, claves),
                " ".join(frag.split()),
            ))
    return filas


# ---------------------------------------------------------------------------
# 1. El censo está completo y suma 77 sin residuo
# ---------------------------------------------------------------------------

def test_el_censo_suma_77_filas_sobre_75_sitios_fisicos():
    filas = censar_raices()
    assert len(filas) == FILAS_ESPERADAS, (
        f"El censo de LR1 midió {FILAS_ESPERADAS} filas el 2026-08-20; ahora "
        f"salen {len(filas)}. Si se añadió o retiró una lectura sobre una "
        f"raíz, clasifícala en CENSO_RAICES y actualiza este número a la vez.")
    assert len({(a, l, t) for a, l, t, *_ in filas}) == SITIOS_FISICOS_ESPERADOS


def test_todo_sitio_medido_esta_clasificado_y_al_reves():
    medidos = {(a, l, t) for a, l, t, *_ in censar_raices()}
    declarados = set(CENSO_RAICES)
    sin_clasificar = medidos - declarados
    fantasmas = declarados - medidos
    assert not sin_clasificar, (
        "Lectura/escritura sobre una raíz de QC que nadie clasificó -- no "
        "se clasifica por descarte, se lee y se decide (DA-47): "
        f"{sorted(sin_clasificar)}")
    assert not fantasmas, (
        "Sitio declarado en CENSO_RAICES que ya no existe (¿cambió de "
        f"línea?): {sorted(fantasmas)}")


def test_las_tres_categorias_son_las_unicas_y_todas_se_usan():
    categorias = {c for c, _ in CENSO_RAICES.values()}
    assert categorias == {IDENTIDAD, LISTA, CENSO}


def test_toda_clasificacion_declara_su_razon():
    """Mismo listón que RT1 les pone a sus excepciones censales: una razón
    de una palabra no es revisable por nadie."""
    for clave, (categoria, razon) in CENSO_RAICES.items():
        assert len(razon) > 30, f"{clave} ({categoria}) sin razón revisable"


# ---------------------------------------------------------------------------
# 2. La clasificación se corresponde con lo que el código hace HOY
# ---------------------------------------------------------------------------

def test_ningun_sitio_de_identidad_lleva_filtro():
    """[[DA-47]], dirección "sobra el filtro": en una lectura por `id` el
    filtro no elige la generación vigente -- convierte la fila pedida en
    nada. Es el defecto que LF4 corrigió en braq_mensual.py."""
    sobrantes = [
        (a, l, t) for a, l, t, _alias, filtra, _ident, _sql in censar_raices()
        if CENSO_RAICES[(a, l, t)][0] == IDENTIDAD and filtra
    ]
    assert not sobrantes, (
        "Filtro de `activo` sobre una lectura de IDENTIDAD (WHERE id = ?): "
        f"vacía el formulario de un registro anulado abierto a propósito: "
        f"{sobrantes}")


def test_todo_sitio_de_lista_filtra():
    """[[DA-47]], dirección "falta el filtro": los 51 sitios de lista lo
    llevan, sin excepción. `PENDIENTES_LR3` fue la lista de trabajo de LR3
    y quedó vacía al terminarlo -- nunca fue una lista blanca."""
    sin_filtrar = [
        (a, l, t) for a, l, t, _alias, filtra, _ident, _sql in censar_raices()
        if CENSO_RAICES[(a, l, t)][0] == LISTA and not filtra
    ]
    inesperados = [s for s in sin_filtrar if s not in PENDIENTES_LR3]
    assert not inesperados, (
        "Lectura de LISTA sobre una raíz de QC sin filtro de `activo` -- un "
        f"registro anulado se cuela entre los vigentes: {inesperados}")


def test_pendientes_lr3_son_todos_de_lista_y_siguen_sin_filtrar():
    """La lista de trabajo no puede usarse para tapar otra cosa: cada
    entrada tiene que ser de LISTA y tiene que seguir sin filtrar (si ya
    filtra, sobra de la lista y hay que sacarla)."""
    estado = {(a, l, t): filtra
              for a, l, t, _al, filtra, _i, _s in censar_raices()}
    for clave in PENDIENTES_LR3:
        assert clave in CENSO_RAICES, f"{clave} pendiente pero no censado"
        assert CENSO_RAICES[clave][0] == LISTA, (
            f"{clave} está en PENDIENTES_LR3 sin ser de LISTA")
        assert not estado[clave], (
            f"{clave} ya filtra -- sácalo de PENDIENTES_LR3")


def test_la_reactivacion_quedo_retirada_por_lr7():
    """[[DA-34]]/[[DA-49]]: LR7 retiró `services/reactivacion.py` entero y
    reclasificó `create_control` (antes CENSO, con los DOS candidatos del
    mes) a LISTA -- una lectura de bloque normal que filtra como
    cualquier otra. Tripwire de que LR7 no se revierta por descuido: si
    `reactivacion.py` reaparece, o si `create_control` vuelve a leer sin
    filtrar, este test lo señala."""
    assert not any(c[0] == "services/reactivacion.py" for c in CENSO_RAICES), (
        "services/reactivacion.py fue retirado por LR7 -- no debería "
        "aparecer ningún sitio censado ahí")
    clave_create_control = ("data/ManejoDatos/load.py", 325, "controles")
    assert CENSO_RAICES[clave_create_control][0] == LISTA
    estado = {(a, l, t): filtra for a, l, t, _al, filtra, _i, _s in censar_raices()}
    assert estado[clave_create_control], (
        "create_control debe filtrar activo -- LR7 retiró la reactivación "
        "precisamente porque esta lectura ya no necesita ver el anulado")
