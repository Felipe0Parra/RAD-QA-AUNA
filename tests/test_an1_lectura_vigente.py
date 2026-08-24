"""AN1 (PLAN_LECTURA_VIGENTE_18-08.md §6-AN1): batería del analizador
compartido `services/lectura_vigente.py`.

El contrato de este test: AN1 debe marcar EXACTAMENTE los 4 sitios reales
del rebuild del 18-08 (D1, D2, D3, crear_algo) copiados aquí de forma
literal -- no una recreación aproximada -- y debe dejar limpios los
patrones que ya filtran correctamente en el árbol real. Un analizador que
marca todo no sirve de nada; uno que no marca los 4 sitios reales tampoco.
"""
import ast
import textwrap

import pytest

from services import lectura_vigente as lv


# ---------------------------------------------------------------------------
# 1. Derivación del alcance (cierra el hueco 2: la lista ya no se desincroniza)
# ---------------------------------------------------------------------------

def test_tablas_del_bloque_qc_cubre_el_bloque_entero_raices_incluidas():
    """LR4 ([[DA-48]]): hasta aquí este test fijaba la EXCLUSIÓN de las 7
    raíces (`assert raiz not in hijas`). Ahora fija lo contrario, que es el
    pago estructural de la fase: el alcance es el bloque de QC completo, y
    ES1/RT1 lo heredan sin tocar ninguno de los dos."""
    bloque = lv.tablas_del_bloque_qc()
    anulables = lv.tablas_anulables()
    pendientes = lv.tablas_pendientes_lf()

    # LF2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF2): el alcance de AN1 es la
    # UNIÓN de TABLAS_ANULABLES con las tablas "PENDIENTE-LF" -- no solo
    # TABLAS_ANULABLES -- para poder exigir el filtro ANTES de que MI1
    # amplíe el frozenset de verdad (§4.4). Desde LR4, sin restarle nada.
    assert bloque == anulables | pendientes
    # MI1 (§6-MI1, DA-40): movió las 30 PENDIENTE-LF al frozenset -- hasta
    # aquí este assert exigía que la resta NO estuviera vacía ("debería
    # haber tablas PENDIENTE-LF mientras MI1 no se ejecute"); ahora exige
    # justo lo contrario, que es el pago de la fase: ya no queda ninguna
    # tabla esperando a que sus lecturas filtren, así que la unión colapsa
    # a `anulables` a secas.
    assert not pendientes, (
        "tras MI1 no debería quedar ninguna tabla PENDIENTE-LF -- si "
        f"aparece alguna, MI1 se revirtió parcialmente: {sorted(pendientes)}")
    assert bloque == anulables
    for raiz in lv.RAICES_QC:
        assert raiz in bloque, (
            f"{raiz} debe estar vigilada como cualquier otra tabla del "
            "bloque de QC -- LR4 retiró la exclusión (DA-48)")
    assert len(lv.RAICES_QC) == 7

    # Las 3 tablas del rebuild del 18-08 -- deliberadamente FUERA del
    # TABLAS_EN_ALCANCE de 18 tablas que tenía LE4, y sin embargo D3
    # (equipos_medicion) es un defecto real de este mismo rebuild.
    for tabla in ("preguntas", "dosimetriaMen", "equipos_medicion",
                  "control_cunas", "control_conos", "tamano_campo"):
        assert tabla in bloque, f"{tabla} debería estar en el alcance de AN1"

    # LF2 en su día: "pruebas" fue el ejemplo de tabla PENDIENTE-LF real
    # (vigilada por AN1 antes de estar en TABLAS_ANULABLES). MI1 la movió
    # al frozenset -- sigue en el alcance, ahora por la otra mitad de la
    # unión.
    assert "pruebas" in bloque
    assert "pruebas" in anulables


def test_alcance_crece_solo_si_TABLAS_ANULABLES_crece(tmp_path, monkeypatch):
    """Hueco 2, verificado en directo: si TABLAS_ANULABLES ganara una tabla
    ficticia nueva, el alcance de AN1 debe crecer SOLO, sin tocar este
    módulo -- es la garantía de que no puede volver a desincronizarse."""
    fuente_falso = tmp_path / "anulacion_falsa.py"
    fuente_falso.write_text(textwrap.dedent("""
        TABLAS_ANULABLES = frozenset({
            "controles",
            "preguntas",
            "tabla_ficticia_de_prueba",
        })
        EXCEPCIONES_INVENTARIO = {}
    """), encoding="utf-8")
    monkeypatch.setattr(lv, "_ANULACION_PATH", fuente_falso)

    hijas = lv.tablas_del_bloque_qc()
    assert "tabla_ficticia_de_prueba" in hijas
    assert "controles" in hijas  # LR4: la raíz ya no se excluye
    assert "preguntas" in hijas


def test_alcance_crece_tambien_con_una_tabla_pendiente_lf(tmp_path, monkeypatch):
    """LF2: el alcance también debe crecer solo si EXCEPCIONES_INVENTARIO
    gana una tabla PENDIENTE-LF nueva -- sin tocar este módulo, mismo
    espíritu que la prueba anterior pero sobre la mitad que LF2 añadió."""
    fuente_falso = tmp_path / "anulacion_falsa_pendiente.py"
    fuente_falso.write_text(textwrap.dedent('''
        TABLAS_ANULABLES = frozenset({
            "controles",
            "preguntas",
        })
        EXCEPCIONES_INVENTARIO = {
            "tabla_pendiente_de_prueba": "PENDIENTE-LF: ficticia",
            "tabla_retirada_de_prueba": "se retira, DA-44 -- ficticia",
        }
    '''), encoding="utf-8")
    monkeypatch.setattr(lv, "_ANULACION_PATH", fuente_falso)

    hijas = lv.tablas_del_bloque_qc()
    assert "tabla_pendiente_de_prueba" in hijas
    assert "tabla_retirada_de_prueba" not in hijas  # motivo distinto de PENDIENTE-LF


def test_tablas_anulables_falla_ruidosamente_si_la_forma_cambia(tmp_path, monkeypatch):
    fuente_falso = tmp_path / "anulacion_rota.py"
    fuente_falso.write_text("TABLAS_ANULABLES = {'controles', 'preguntas'}\n",
                             encoding="utf-8")
    monkeypatch.setattr(lv, "_ANULACION_PATH", fuente_falso)
    with pytest.raises(RuntimeError):
        lv.tablas_anulables()


# ---------------------------------------------------------------------------
# 2. Los 4 sitios reales del rebuild del 18-08 -- deben marcarse
# ---------------------------------------------------------------------------

TABLAS_PRUEBA = frozenset({"preguntas", "dosimetriaMen", "equipos_medicion"})

# D1+D2: data/ManejoDatos/load.py, mostrar_controles_mensuales, rama general
# (líneas 1442-1465), texto EXACTO tal como queda tras el `query += "..."`
# de la línea 1475 -- copiado literal, no aproximado.
SQL_D1_D2 = """
        SELECT
            cm.id,
            cm.fecha,
            u.fullname,
            cm.equipo,
            p.iso_mec,
            p.reticulo_cent,
            p.bordes_coin,
            p.camilla_vert_rango,
            p.camilla_vert_desp,
            p.camilla_iso_desp,
            p.telem_rango,
            p.telem_desp,
            p.puntero_telem_diff,
            p.laser_techo,
            p.laser_lateral9,
            p.laser_lateral27,
            (SELECT dosis_ref_cgy_um FROM dosimetriaMen
            WHERE ref = cm.id AND energia = '6mv' LIMIT 1) as dosis_ref_cgy_um
        FROM controles cm
        LEFT JOIN users u ON cm.user_id = u.fullname
        LEFT JOIN preguntas p ON cm.id = p.ref
         WHERE (cm.activo IS NULL OR cm.activo = 1)
"""

# D3: data/ManejoDatos/Tablas_Anuales/tablas_anuales.py:595-597
SQL_D3 = """
        SELECT tipo_camara, equip_type, model, serie
        FROM equipos_medicion WHERE ref=?
    """

# crear_algo: data/ManejoDatos/load.py:427 y :436
SQL_CREAR_ALGO_SELECT = "SELECT ref FROM preguntas WHERE ref = ?"
SQL_CREAR_ALGO_UPDATE = "UPDATE preguntas SET imagen = ? WHERE ref = ?"


def test_d1_join_preguntas_sin_filtro_de_alias():
    hallazgos = lv.analizar(SQL_D1_D2, TABLAS_PRUEBA)
    de_preguntas = [h for h in hallazgos if h.tabla == "preguntas"]
    assert de_preguntas, "D1: el JOIN a preguntas debe marcarse sin filtro"
    assert de_preguntas[0].alias == "p"
    assert de_preguntas[0].motivo == "sin filtro de activo"

    # 'controles' es raíz -- fuera del alcance en TABLAS_PRUEBA, no debe
    # aparecer aunque el cm.activo esté ahí (no sería su culpa ni su gloria).
    assert not any(h.tabla == "controles" for h in hallazgos)


def test_d2_subconsulta_dosimetriamen_sin_filtro_ni_orden():
    hallazgos = lv.analizar(SQL_D1_D2, TABLAS_PRUEBA)
    de_dosis = [h for h in hallazgos if h.tabla == "dosimetriaMen"]
    motivos = {h.motivo for h in de_dosis}
    assert "sin filtro de activo" in motivos, (
        "D2: la subconsulta de dosimetriaMen no filtra activo -- por eso "
        "devuelve una fila arbitraria (rowid=45, dosis=None) en vez de la "
        "vigente (rowid=63, dosis=1.0125)")
    assert "LIMIT sin ORDER BY" in motivos, (
        "D2: LIMIT 1 sin ORDER BY sobre una tabla con varias filas por "
        "clave es arbitrario aunque se añada el filtro de activo")


def test_d3_equipos_medicion_sin_alias_sin_filtro():
    hallazgos = lv.analizar(SQL_D3, TABLAS_PRUEBA)
    assert len(hallazgos) == 1
    assert hallazgos[0].tabla == "equipos_medicion"
    assert hallazgos[0].alias == "equipos_medicion"  # sin alias -- la propia tabla
    assert hallazgos[0].motivo == "sin filtro de activo"


def test_crear_algo_select_e_update_sin_filtro():
    h_select = lv.analizar(SQL_CREAR_ALGO_SELECT, TABLAS_PRUEBA)
    assert len(h_select) == 1 and h_select[0].tabla == "preguntas"

    h_update = lv.analizar(SQL_CREAR_ALGO_UPDATE, TABLAS_PRUEBA)
    assert len(h_update) == 1 and h_update[0].tabla == "preguntas"
    assert h_update[0].motivo == "sin filtro de activo"


# ---------------------------------------------------------------------------
# 3. Patrones ya correctos en el árbol real -- no deben marcarse (control de
#    falsos positivos; un analizador ruidoso no se usa)
# ---------------------------------------------------------------------------

def test_filtro_qualificado_real_no_se_marca():
    """consistencia_dosis.py:51, texto YA RESUELTO (lo que RT1 vería en
    tiempo de ejecución tras `filtro_activo("dosimetriaMen").replace("activo",
    "d.activo")`)."""
    sql = """
        SELECT d.ref, d.energia, d.dosis_ref_cgy_um, c.equipo, c.fecha
        FROM dosimetriaMen d
        JOIN controles c ON c.id = d.ref
        WHERE d.energia IS NOT NULL AND d.dosis_ref_cgy_um IS NOT NULL AND (d.activo IS NULL OR d.activo = 1)
        ORDER BY d.ref
    """
    hallazgos = lv.analizar(sql, TABLAS_PRUEBA)
    assert hallazgos == []


def test_filtro_sin_alias_una_sola_tabla_no_se_marca():
    """control_cunas/control_conos (M2): una sola tabla versionada, filtro
    sin calificar, con ORDER BY -- patrón limpio real de
    seiscientos_mensual.py/ix_mensual.py."""
    sql = """
        SELECT angulo, in_val, out_val, right_val, left_val
        FROM control_cunas
        WHERE ref = ? AND activo = 1
        ORDER BY angulo, id DESC
    """
    hallazgos = lv.analizar(sql, frozenset({"control_cunas"}))
    assert hallazgos == []


def test_filtro_activo_interpolado_una_sola_tabla_no_se_marca():
    """Patrón real repetido ~20 veces en load.py:
    f"SELECT {cols} FROM {tabla} WHERE ref=?{filtro_activo(tabla)}" -- el
    texto YA RESUELTO en runtime (tabla='tamano_campo') que RT1 vería."""
    sql = "SELECT id, campo_nominal FROM tamano_campo WHERE ref=? AND (activo IS NULL OR activo = 1)"
    hallazgos = lv.analizar(sql, frozenset({"tamano_campo"}))
    assert hallazgos == []


def test_tabla_no_versionada_nunca_se_marca():
    sql = "SELECT fullname FROM users WHERE id = ?"
    assert lv.analizar(sql, TABLAS_PRUEBA) == []


def test_join_con_alias_correctamente_filtrado_no_se_marca():
    sql = """
        SELECT p.iso_mec FROM controles cm
        LEFT JOIN preguntas p ON cm.id = p.ref AND (p.activo IS NULL OR p.activo = 1)
        WHERE cm.id = ?
    """
    hallazgos = lv.analizar(sql, TABLAS_PRUEBA)
    assert not any(h.tabla == "preguntas" for h in hallazgos)


# ---------------------------------------------------------------------------
# 4. Resolución de variable (hueco 1): el patrón real de D1/D2 y el patrón
#    simple de un-solo-uso, más los casos que deben quedar genuinamente
#    opacos.
# ---------------------------------------------------------------------------

def _funcion_y_llamada_execute(codigo_fuente):
    """Parsea `codigo_fuente` (una función completa) y devuelve
    (FunctionDef, Call) del primer `algo.execute(...)` encontrado."""
    arbol = ast.parse(textwrap.dedent(codigo_fuente))
    func = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef))
    llamada = next(
        n for n in ast.walk(func)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "execute")
    return func, llamada


def test_resuelve_if_else_mas_concatenacion_compartida():
    """La forma EXACTA de mostrar_controles_mensuales: if/else asigna
    `query`, luego un `query +=` compartido, luego el execute()."""
    codigo = '''
        def mostrar_controles_mensuales(parent, tableWidget, equipo_filtrar=None):
            if equipo_filtrar == "Halcyon":
                query = "SELECT 1 FROM controles cm LEFT JOIN preguntas p ON cm.id=p.ref"
            else:
                query = "SELECT 2 FROM controles cm LEFT JOIN preguntas p ON cm.id=p.ref"
            query += " WHERE (cm.activo IS NULL OR cm.activo = 1)"
            cursor.execute(query)
    '''
    func, llamada = _funcion_y_llamada_execute(codigo)
    resultado = lv.resolver_argumento_execute(func, llamada)
    assert resultado is not None
    assert len(resultado) == 2
    assert all(t.endswith(" WHERE (cm.activo IS NULL OR cm.activo = 1)") for t in resultado)
    assert any("SELECT 1" in t for t in resultado)
    assert any("SELECT 2" in t for t in resultado)


def test_resuelve_asignacion_simple_de_un_solo_uso():
    """El patrón más común del árbol (equipos_service.py, crear_algo): una
    asignación, un uso inmediato."""
    codigo = '''
        def f(self):
            sql = "UPDATE preguntas SET imagen = ? WHERE ref = ?"
            cursor.execute(sql, lista)
    '''
    func, llamada = _funcion_y_llamada_execute(codigo)
    resultado = lv.resolver_argumento_execute(func, llamada)
    assert resultado == ["UPDATE preguntas SET imagen = ? WHERE ref = ?"]


def test_reasignacion_dentro_de_bucle_queda_opaca():
    codigo = '''
        def f(self, refs):
            query = "SELECT 1 FROM preguntas"
            for r in refs:
                query = query + " AND ref != " + str(r)
            cursor.execute(query)
    '''
    func, llamada = _funcion_y_llamada_execute(codigo)
    assert lv.resolver_argumento_execute(func, llamada) is None


def test_dos_if_hermanos_cada_uno_con_su_propio_execute_no_se_mezclan():
    """Forma EXACTA de load.py:1470-1476: un if/else EXTERIOR asigna
    `query` (2 valores posibles), y un SEGUNDO if/else, hermano e
    independiente, hace su propio `query +=` y su propio `execute()` en
    CADA rama. Cada sitio debe resolver a exactamente 2 candidatos (los 2
    del if exterior, con SU propio += aplicado) -- nunca 4, que sería
    mezclar el "antes" de una rama con el "después" de la otra rama
    hermana (el bug real que tuvo la primera versión de este resolver)."""
    codigo = '''
        def mostrar_controles_mensuales(parent, tableWidget, equipo_filtrar=None):
            if equipo_filtrar == "Halcyon":
                query = "SELECT 1 FROM controles cm"
            else:
                query = "SELECT 2 FROM controles cm"
            if equipo_filtrar:
                query += " WHERE A"
                cursor.execute(query, (equipo_filtrar,))
            else:
                query += " WHERE B"
                cursor.execute(query)
    '''
    arbol = ast.parse(textwrap.dedent(codigo))
    func = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef))
    llamadas = [n for n in ast.walk(func)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "execute"]
    assert len(llamadas) == 2

    resultado_A = lv.resolver_argumento_execute(func, llamadas[0])
    assert resultado_A is not None and len(resultado_A) == 2, resultado_A
    assert all(t.endswith(" WHERE A") for t in resultado_A)
    assert not any(t.endswith(" WHERE B") for t in resultado_A)

    resultado_B = lv.resolver_argumento_execute(func, llamadas[1])
    assert resultado_B is not None and len(resultado_B) == 2, resultado_B
    assert all(t.endswith(" WHERE B") for t in resultado_B)
    assert not any(t.endswith(" WHERE A") for t in resultado_B)


def test_argumento_ya_literal_no_pasa_por_el_resolver():
    """Si arg0 ya es un literal directo, resolver_argumento_execute no
    aplica (ES1 lo maneja con _literal_str_ast directo, sin necesitar esto)."""
    codigo = '''
        def f(self):
            cursor.execute("SELECT 1 FROM preguntas")
    '''
    func, llamada = _funcion_y_llamada_execute(codigo)
    assert lv.resolver_argumento_execute(func, llamada) is None


# ---------------------------------------------------------------------------
# 5. LF5 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LF5, DA-47): tercer motivo de
#    SinFiltro -- "filtro sobre lectura de identidad". CLAVES_INDICE (IV3,
#    52 entradas) es la fuente de verdad de qué es clave de bloque; ninguna
#    usa `id`/`rowid`, así que un WHERE que nombra esa columna es siempre
#    una lectura por identidad física, nunca por bloque.
# ---------------------------------------------------------------------------

def test_claves_indice_coincide_con_el_fuente():
    from scripts.indices_bloque_qc import CLAVES_INDICE as CLAVES_REALES
    claves = lv.claves_indice()
    assert len(claves) == 56  # IV3 (52) + MI3 (4 diarias, DATE(date))
    assert claves == {t: frozenset(c) for t, c in CLAVES_REALES.items()}
    # LF5: la premisa que hace seguro tratar "id"/"rowid" como identidad
    # física en cualquier tabla, sin mirar CLAVES_INDICE caso por caso.
    assert not any(clave & {"id", "rowid"} for clave in claves.values())


def test_tablas_con_filtro_posible_incluye_las_raices():
    """Las raíces están en los dos alcances desde LR4; lo que distingue a
    este es que NO incluye las 30 PENDIENTE-LF, cuyo `filtro_activo()`
    todavía devuelve "" (no se puede preguntar si sobra un filtro que aún
    no puede existir)."""
    assert lv.tablas_con_filtro_posible() == lv.tablas_anulables()
    for raiz in ("TipoCalibracion", "controles", "LinealidadBraquiterapia"):
        assert raiz in lv.tablas_con_filtro_posible()


def test_identidad_con_filtro_se_marca_incluso_en_una_raiz():
    """El defecto original de LF4, reproducido con
    `tablas_versionadas=frozenset()`: aunque la tabla no estuviera en el
    alcance de "sin filtro", el motivo de "filtro de más" debe verla igual
    -- es lo que hizo visible el defecto de DA-47 cuando TipoCalibracion
    era una raíz excluida."""
    sql = ("SELECT user, fecha FROM TipoCalibracion "
           "WHERE id = ? AND (activo IS NULL OR activo = 1)")
    hallazgos = lv.analizar(sql, frozenset())
    assert len(hallazgos) == 1
    assert hallazgos[0].tabla == "TipoCalibracion"
    assert hallazgos[0].motivo == "filtro sobre lectura de identidad"


def test_identidad_sin_filtro_no_se_marca():
    """El caso correcto: uid="id" con el filtro correctamente omitido
    (LF4, braq_mensual.py::consulta hoy)."""
    sql = "SELECT user, fecha FROM TipoCalibracion WHERE id = ?"
    assert lv.analizar(sql, frozenset()) == []


def test_bloque_con_filtro_no_se_marca():
    """El caso correcto opuesto: uid="ref" SÍ debe filtrar -- no es una
    lectura de identidad, es una lectura de bloque."""
    sql = ("SELECT user, fecha FROM SistemaMedicion "
           "WHERE ref = ? AND (activo IS NULL OR activo = 1)")
    assert lv.analizar(sql, frozenset({"SistemaMedicion"})) == []


def test_anular_fila_no_se_marca():
    """Protocolo de verificación LF5, punto 2: anular_fila() -- WHERE "id"
    = ?, la fila se localiza por identidad para anularla, SIN filtro de
    lectura -- es el caso correcto canónico, no debe reportarse. Copiado
    literal de services/anulacion.py::anular_fila (el SQL que emite tras
    resolver `id_where`)."""
    sql = 'UPDATE "TipoCalibracion" SET activo = 0 WHERE "id" = ?'
    assert lv.analizar(sql, frozenset()) == []


def test_set_activo_antes_del_where_no_cuenta_como_filtro():
    """Aislado del caso anterior: el propio texto_desde_where es lo que
    evita que un `SET activo = 0` (la anulación) se confunda con un filtro
    de lectura -- sin ese recorte, cualquier UPDATE de anulación por id
    daría un falso positivo."""
    sql = 'UPDATE "TipoCalibracion" SET activo = 0, user = ? WHERE "id" = ? AND 1 = 1'
    assert lv.analizar(sql, frozenset()) == []


def test_clave_de_bloque_con_id_en_el_nombre_no_se_confunde_con_identidad():
    """`pruebas` (clave ("id_sesion", "id_tipo")) -- ninguna de las dos
    columnas es literalmente "id"/"rowid", pero ambas lo CONTIENEN como
    subcadena. El límite de palabra (\\b) en el patrón no debe confundir
    "id_sesion" con "id"."""
    sql = ("SELECT * FROM pruebas "
           "WHERE id_sesion = ? AND id_tipo = ? AND (activo IS NULL OR activo = 1)")
    assert lv.analizar(sql, frozenset({"pruebas"})) == []


def test_rojo_antes_que_verde_reproduce_braq_mensual_si_lf4_se_revierte():
    """Reproduce EXACTAMENTE la forma que emitiría braq_mensual.py::consulta
    si LF4 se revirtiera a `filtro_activo(nombre_tabla)` incondicional --
    la resolución en tiempo de ejecución que vería RT1 para uid="id"."""
    sql_si_se_revierte = (
        "SELECT user, fecha, tipo, serie, certificado, fecha_cer, "
        "intensidad, conversion FROM TipoCalibracion WHERE id = ? "
        "AND (activo IS NULL OR activo = 1)")
    hallazgos = lv.analizar(sql_si_se_revierte, frozenset())
    assert any(h.motivo == "filtro sobre lectura de identidad"
               and h.tabla == "TipoCalibracion" for h in hallazgos)


def test_valor_expandido_en_vez_de_signo_de_interrogacion_se_detecta():
    """`sqlite3.Connection.set_trace_callback` (RT1) entrega el SQL con los
    parámetros YA EXPANDIDOS a su valor literal (`sqlite3_expanded_sql`),
    no el texto preparado -- medido reproduciendo en runtime el defecto de
    LF4 revertido: `addsomething` emitió literalmente
    `WHERE id = 5 AND (activo IS NULL OR activo = 1)`, nunca `id = ?`. Un
    patrón anclado a `= \\?` no habría visto ese texto real y LF5 nunca
    hubiera puesto a RT1 en rojo -- solo a este test unitario, que usa `?`
    por comodidad de fixture."""
    sql_expandido = (
        "SELECT user, fecha, tipo, serie, certificado, fecha_cer, "
        "intensidad, conversion FROM TipoCalibracion WHERE id = 5 "
        "AND (activo IS NULL OR activo = 1)")
    hallazgos = lv.analizar(sql_expandido, frozenset())
    assert len(hallazgos) == 1
    assert hallazgos[0].motivo == "filtro sobre lectura de identidad"
    assert hallazgos[0].tabla == "TipoCalibracion"


# ---------------------------------------------------------------------------
# 6. LR4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR4, [[DA-48]]): con las 7
#    raíces DENTRO del alcance, el motivo "sin filtro de activo" tiene que
#    saber callarse sobre una lectura de IDENTIDAD -- si no, exigiría el
#    filtro justo donde DA-47 dice que sobra (el defecto de LF4). Es la
#    misma regla que el tercer motivo, con el signo cambiado, y por eso vive
#    en el mismo sitio en vez de repartirse en listas blancas de ES1 y RT1.
# ---------------------------------------------------------------------------

def test_lr4_identidad_sin_filtro_no_se_marca_estando_en_alcance():
    """El caso que LR4 hace posible: `controles` YA está en el alcance, y
    aun así una lectura por su clave primaria no debe pedirle filtro."""
    sql = "SELECT * FROM controles WHERE id = ?"
    assert lv.analizar(sql, frozenset({"controles"})) == []


def test_lr4_bloque_sin_filtro_si_se_marca_en_una_raiz():
    """La otra mitad, y el pago de la fase: la misma tabla, leída por una
    clave que puede casar varias generaciones, SÍ se marca. Antes de LR4
    esto era invisible -- es lo que dejó llegar a 27 filtradas / 50 sin
    filtrar sin que ningún tripwire lo viera."""
    sql = "SELECT id FROM controles WHERE fecha = ? AND equipo = ?"
    hallazgos = lv.analizar(sql, frozenset({"controles"}))
    assert [h.motivo for h in hallazgos] == ["sin filtro de activo"]
    assert hallazgos[0].tabla == "controles"


def test_lr4_join_al_padre_por_su_pk_es_identidad():
    """`services/consistencia_dosis.py`: `JOIN controles c ON c.id = d.ref`
    trae UNA fila de `controles` por cada fila de `dosimetriaMen`. Filtrar
    ahí no elegiría la generación vigente del control -- borraría del
    informe la fila HIJA, que sigue vigente."""
    sql = ("SELECT d.ref, c.equipo FROM dosimetriaMen d "
           "JOIN controles c ON c.id = d.ref "
           "WHERE d.energia IS NOT NULL AND (d.activo IS NULL OR d.activo = 1)")
    assert lv.analizar(sql, frozenset({"controles", "dosimetriaMen"})) == []


def test_lr4_join_a_la_hija_no_convierte_al_padre_en_identidad():
    """La confusión peligrosa: en `mostrar_controles_*`, `c.id` aparece
    dentro de un `ON`, pero es el ON del JOIN a `pruebas`, no el de
    `controles` -- que está en el FROM y se selecciona por `equipo`. Si AN1
    los confundiera dejaría de exigir el filtro en los 10 sitios que hoy lo
    llevan bien."""
    # El orden del `ON` es el REAL de load.py::mostrar_controles_mensuales
    # (`ON cm.id = p.ref`), el peligroso: `c.id =` aparece literalmente.
    sql = ("SELECT c.id FROM controles c "
           "LEFT JOIN preguntas p ON c.id = p.ref AND (p.activo IS NULL OR p.activo = 1) "
           "WHERE c.equipo = ?")
    hallazgos = lv.analizar(sql, frozenset({"controles", "preguntas"}))
    assert [(h.tabla, h.motivo) for h in hallazgos] == [
        ("controles", "sin filtro de activo")]


def test_lr4_join_por_clave_de_bloque_no_es_identidad():
    """`graficar_maximos_camara`: `TipoCalibracion` entra por un JOIN, pero
    el `WHERE` la selecciona por FECHA -- varias generaciones posibles. Sigue
    necesitando su propio filtro, y el de `MaximosCamaras` no se lo presta
    (hueco 4 de LE4)."""
    sql = ("SELECT mc.posicion FROM MaximosCamaras mc "
           "JOIN TipoCalibracion tc ON mc.ref = tc.id "
           "WHERE DATE(tc.fecha) = ? AND (mc.activo IS NULL OR mc.activo = 1) "
           "ORDER BY mc.posicion ASC")
    hallazgos = lv.analizar(sql, frozenset({"MaximosCamaras", "TipoCalibracion"}))
    assert [(h.tabla, h.motivo) for h in hallazgos] == [
        ("TipoCalibracion", "sin filtro de activo")]


def test_lr4_filtro_sobrante_en_un_join_de_identidad_si_se_marca():
    """La regla es una sola con dos direcciones: si alguien AÑADIERA el
    filtro al JOIN por clave primaria, el tercer motivo tiene que verlo."""
    sql = ("SELECT d.ref, c.equipo FROM dosimetriaMen d "
           "JOIN controles c ON c.id = d.ref "
           "WHERE (c.activo IS NULL OR c.activo = 1)")
    hallazgos = lv.analizar(sql, frozenset())
    assert any(h.tabla == "controles"
               and h.motivo == "filtro sobre lectura de identidad"
               for h in hallazgos)
