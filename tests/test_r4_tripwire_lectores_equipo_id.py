"""R.4 (PLAN_PUNTEROS_A_EQUIPOS_11-09.md §5): tripwire -- que no nazca un
lector de `equipo_id` sin blindaje. El censo de §0.6 del plan es una foto
tomada el 11-09; nada impide que mañana aparezca un séptimo lector que
resuelva un id guardado sin comprobar nada, exactamente como nacieron los
tres que R.3 blindó (commit `9396f83`). Este archivo cierra la clase de
error con una prueba que falla sola cuando alguien la reintroduce, no con
una corrección puntual que se erosiona.

Censo por AST (no por texto plano -- un comentario o un docstring que
mencionen `equipo_id` NO deben disparar nada; el falso positivo por
docstring ya mordió dos veces el 10-09 en otros tripwires de este
proyecto, ver `TestInmuneAComentariosYDocstrings`). Tres patrones, sobre
TODO `.py` de producción (excluidos `tests/`, misma convención que
ES1/EB5/RT1/LE4):
  1. `EquiposService.obtener_por_id(...)` -- cualquier llamada.
  2. `<combo>.findData(<arg>)` donde el argumento MENCIONA `equipo_id`
     como subcadena (cubre `equipo_id` y `equipo_id_confiable`).
  3. Un `SELECT ... FROM equipos WHERE id = ...` crudo pasado como
     argumento directo a `.execute(`/`.executemany(`.

Límite conocido, aceptado a propósito (doctrina del plan: "mejor un falso
positivo que obligue a justificar, que un falso negativo" -- NO al revés):
el patrón 3 no sigue concatenación de cadenas (`"..." + "..."`) ni SQL
armado en una variable intermedia antes del `.execute(`; los 3 sitios
reales de este proyecto pasan el literal directamente, y si alguna vez
alguien lo arma de otra forma, prefiero que quede fuera de este censo
(silencioso) a que el detector se vuelva fràgil tratando de seguir
cualquier forma de composición de cadenas. Documentado, no oculto.

CENSO REAL (14-09-2026, Sonnet), 16 sitios -- MÁS que los "6 sitios de
§0.6" del plan: ese censo estudiaba solo el riesgo de RESTAURAR un id
GUARDADO en el pasado (seiscientos_mensual.py, reporte_calculadora_dos.py,
dialogs.py, equipos.py). Un recorrido literal de TODA la producción --que
es lo que el CAMBIO de esta tarea pide-- también encuentra los selectores
EN VIVO del pozo/electrómetro de braquiterapia y la calculadora
(braq_mensual.py, braquiterapia.py): resuelven la selección ACTUAL de un
combo que el físico acaba de tocar, no un id histórico. Mismo patrón
sintáctico (`obtener_por_id`/`findData`), riesgo distinto. Los 16 quedan
en la lista blanca, cada uno con su categoría (BLINDADO/EXENTO) y su
justificación escrita -- ninguno se omite por no estar en el censo
original del plan; omitirlo habría sido exactamente el error que este
tripwire existe para no volver a cometer.

Trampa 5: la lista blanca lleva NÚMEROS DE LÍNEA de 8 archivos de
producción (`braq_mensual.py`, `braquiterapia.py`, `dialogs.py`,
`equipos.py`, `equipos_service.py`, `reporte_calculadora_dos.py`,
`seiscientos_mensual.py`, `scripts/saneamiento_equipos_h26.py`) --
cualquier cambio que desplace líneas en cualquiera de ellos obliga a
recalcular y actualizar esta lista, igual que los otros 4 censores por
línea del proyecto (ver la Trampa 5 de `CLAUDE.md`).
"""
import ast
import re
import sqlite3
import shutil
from pathlib import Path

import pytest

import data.ManejoDatos.conection as conection_mod
import services.equipos_service as equipos_service_mod

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "mcc_PTW_read",
}

from _bd_referencia import BD_REBUILD_11_09  # DP-104: fuente única de rutas de BD


# ---------------------------------------------------------------------------
# Censor AST
# ---------------------------------------------------------------------------

def _archivos_produccion(raiz: Path):
    for path in sorted(raiz.rglob("*.py")):
        rel = path.relative_to(raiz)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        yield rel, path


def _texto_de_argumento(arg):
    """Equivalente a `ast.unparse` -- reconstruye el texto de un
    argumento para poder buscar `equipo_id` como subcadena."""
    try:
        return ast.unparse(arg)
    except Exception:
        return ast.dump(arg)


def _texto_de_string_literal(nodo):
    """Texto de un `ast.Constant` str o un `ast.JoinedStr` (f-string),
    con cada parte dinámica sustituida por un marcador -- para poder
    aplicar la regex igual que si fuera SQL ya resuelto (mismo criterio
    que `PATRON_FROM_DINAMICO` de test_le4). Devuelve None si el nodo no
    es un literal de cadena (p. ej. una variable ya armada aparte, o una
    concatenación -- ver el límite conocido documentado arriba)."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        partes = []
        for valor in nodo.values:
            if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                partes.append(valor.value)
            else:
                partes.append("{DYN}")
        return "".join(partes)
    return None


PATRON_SQL_EQUIPOS_POR_ID = re.compile(
    r'^\s*SELECT\b.*FROM\s+"?equipos"?\s+WHERE\s+id\s*=', re.IGNORECASE)


def _censar_codigo(codigo_fuente, nombre_archivo="<memoria>"):
    """Devuelve [(linea, tipo), ...]. Un comentario nunca llega aquí:
    `ast.parse` los descarta al tokenizar, antes de construir el árbol.
    Un docstring SÍ es un nodo del árbol (`Expr(Constant)`), pero nunca es
    el ARGUMENTO de una llamada -- ninguna de las tres ramas de abajo
    exige eso, así que un docstring no puede disparar ninguna."""
    try:
        arbol = ast.parse(codigo_fuente, filename=nombre_archivo)
    except SyntaxError:
        return []

    hallazgos = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)):
            continue
        atributo = nodo.func.attr

        if atributo == "obtener_por_id":
            hallazgos.append((nodo.lineno, "obtener_por_id"))

        elif atributo == "findData" and nodo.args:
            if "equipo_id" in _texto_de_argumento(nodo.args[0]):
                hallazgos.append((nodo.lineno, "findData"))

        elif atributo in ("execute", "executemany") and nodo.args:
            texto = _texto_de_string_literal(nodo.args[0])
            if texto and PATRON_SQL_EQUIPOS_POR_ID.search(re.sub(r"\s+", " ", texto)):
                hallazgos.append((nodo.lineno, "sql_crudo"))

    return hallazgos


def censar_produccion(raiz: Path = ROOT):
    """Recorre `raiz` (por defecto, la raíz del repo) y devuelve
    {(archivo_relativo_como_str, linea): tipo}. Parametrizable por `raiz`
    para poder apuntar a un directorio temporal sintético en los tests de
    mordida, sin tocar nunca un archivo de producción real."""
    resultado = {}
    for rel, path in _archivos_produccion(raiz):
        try:
            codigo = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for linea, tipo in _censar_codigo(codigo, nombre_archivo=str(path)):
            resultado[(str(rel).replace("\\", "/"), linea)] = tipo
    return resultado


def _funcion_que_contiene(arbol, linea):
    """La función (o método) MÁS INTERNA cuyo rango de líneas cubre
    `linea` -- para poder mirar si menciona `resolver_guardado`."""
    candidata = None
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fin = getattr(nodo, "end_lineno", None) or nodo.lineno
            if nodo.lineno <= linea <= fin:
                if candidata is None or nodo.lineno > candidata.lineno:
                    candidata = nodo
    return candidata


# ---------------------------------------------------------------------------
# Lista blanca congelada -- censo real del 14-09-2026 (Sonnet)
# ---------------------------------------------------------------------------
# Formato: (archivo, línea): (categoría, justificación)
#   BLINDADO -- resuelve un id GUARDADO contra el catálogo; pasa por
#               `resolver_guardado` antes (verificado abajo: la función
#               que lo contiene debe MENCIONAR resolver_guardado).
#   EXENTO   -- no resuelve dato histórico: selección EN VIVO, código
#               muerto documentado, o lectura por identidad de la propia
#               fila (no de un puntero ajeno).

SITIOS_EQUIPO_ID_PERMITIDOS = {
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 487): (
        "EXENTO",
        "on_serie_pozo_cambio -- equipo_id viene de "
        "combo_serie.currentData(), la calibracion que el fisico ACABA de "
        "elegir en el combo (poblado momentos antes por "
        "calibraciones_activas()); no restaura ningun dato guardado en el "
        "pasado."),
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py", 528): (
        "EXENTO",
        "on_serie_elec_cambio -- mismo patron que :481, combo_serie_elec "
        "EN VIVO."),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 2810): (
        "EXENTO",
        "on_serie_pozo_cambio -- mismo patron que braq_mensual.py:481, "
        "combo_serie EN VIVO (gemelo de esa pantalla en el diario)."),
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py", 3036): (
        "EXENTO",
        "on_serie_elec_cambio -- mismo patron, combo_serie_elec EN VIVO."),
    ("services/equipos_service.py", 293): (
        "EXENTO",
        "Es la PROPIA funcion de blindaje (resolver_guardado) resolviendo "
        "contra el catalogo HOY para poder comparar -- blindar esto "
        "blindaria al blindaje contra si mismo."),
    ("models/PDF/reporte_calculadora_dos.py", 79): (
        "BLINDADO",
        "R.3 (commit 9396f83), sitio #3 del censo original -- guardado "
        "por resolver_guardado en la linea 76 (datos_a_dataframe); "
        "conserva EXACTAMENTE una llamada a obtener_por_id a proposito, "
        "exigido por test_q4_serie_guardada_manda.py::TestCierreDeClase."),
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 3395): (  # A.2 (21-09): 3203->3262; B.3 (21-09): 3262->3323; B.4 (21-09): 3323->3395
        "EXENTO",
        "equipo_id viene de sender.currentData() -- la seleccion EN VIVO "
        "del combo que el fisico acaba de tocar al llenar la seccion de "
        "Equipos, no una restauracion desde BD."),
    ("ui/paginasGuia/dialogs.py", 2430): (
        "EXENTO",
        "seleccionar_equipo_por_id -- CODIGO MUERTO, 0 llamadores en todo "
        "el arbol (documentado en CLAUDE.md, DP-100, 10-09-2026; "
        "reconfirmado en esta tarea con el mismo grep). No blindado "
        "porque nada lo alcanza hoy; si algun dia gana un llamador, esta "
        "entrada debe reabrirse -- no basta con que el test siga verde."),
    ("ui/paginasGuia/dialogs.py", 2448): (
        "EXENTO",
        "cargar_datos_equipo -- self.equipo_id lo fija on_serie_cambiada "
        "(:2416) desde combo_series.currentData(), y ese combo solo "
        "contiene ids que la restauracion ya valido con resolver_guardado "
        "(:2595-2598) o que el fisico eligio en vivo -- hereda la "
        "proteccion del sitio BLINDADO de :2600, no la necesita por si "
        "mismo."),
    ("ui/paginasGuia/dialogs.py", 2436): (
        "EXENTO",
        "seleccionar_equipo_por_id -- misma funcion muerta que :2430."),
    ("ui/paginasGuia/dialogs.py", 2600): (
        "BLINDADO",
        "R.3 (commit 9396f83), sitio #5 del censo original -- guardado "
        "por resolver_guardado en :2595-2598, con respaldo por "
        "Numero_serie si no resuelve."),
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 3964): (  # A.2 (21-09): 3772->3831; B.3 (21-09): 3831->3892; B.4 (21-09): 3892->3964
        "BLINDADO",
        "R.3 (commit 9396f83), sitio #1 del censo original, EL CRITICO -- "
        "guardado por resolver_guardado en :3677 (Traerinfo)."),
    ("ui/paginasGuia/equipos.py", 648): (
        "EXENTO",
        "id_equipo = item.data(Qt.UserRole) -- la fila de la TABLA DEL "
        "CATALOGO en la que el fisico acaba de hacer doble clic para ver "
        "su certificado; identidad de una fila EN VIVO, no un puntero "
        "guardado en otra tabla."),
    ("ui/paginasGuia/equipos.py", 1017): (
        "EXENTO",
        "eliminarEquipo -- lee los 12 campos de la fila que el fisico "
        "seleccionó para BORRAR, para poder auditarla (R.2, "
        "commit 4c077c8); identidad de la fila PROPIA, no una resolucion "
        "de puntero ajeno."),
    ("scripts/saneamiento_equipos_h26.py", 283): (
        "EXENTO",
        "aplicar_saneamiento -- eq_id viene de la lista literal CAMBIOS "
        "(ids 57/58 escritos a mano en este script de migracion de un "
        "solo uso), no de una columna equipo_id de ninguna tabla de QC."),
    ("ui/paginasGuia/equipos.py", 714): (
        "EXENTO",
        "editarEquipo -- id_equipo = item.data(Qt.UserRole), la fila de "
        "la TABLA DEL CATALOGO que el fisico seleccionó para editar; "
        "identidad de una fila EN VIVO, mismo patron que :648."),
    ("ui/paginasGuia/equipos.py", 825): (
        "EXENTO",
        "guardarCambios -- mismo patron que :714, id_equipo = "
        "item.data(Qt.UserRole) de la fila EN VIVO que se está editando; "
        "lee 'datos originales' para comparar contra el formulario, no "
        "resuelve un puntero guardado en otra tabla."),
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 3617): (  # A.2 (21-09): 3425->3484; B.3 (21-09): 3484->3545; B.4 (21-09): 3545->3617
        "EXENTO",
        "R.3, sitio #2 del censo original -- resuelve serie/fecha/tipo al "
        "GUARDAR, con el equipo_id que el propio combo tiene seleccionado "
        "en ese instante; hereda la proteccion del sitio BLINDADO de "
        "linea 3680, que es quien decide que puede quedar seleccionado "
        "('hereda la seleccion de #1', PLAN_PUNTEROS_A_EQUIPOS_11-09.md "
        "S0.6)."),
}

SITIOS_BLINDADOS = [k for k, (cat, _) in SITIOS_EQUIPO_ID_PERMITIDOS.items()
                     if cat == "BLINDADO"]


class TestElCensoDeProduccionEsExactamenteElAutorizado:
    """El corazón del tripwire: todo lo que el censor encuentra en
    producción HOY tiene que estar en la lista blanca, y todo lo que la
    lista blanca cita tiene que seguir existiendo donde dice."""

    def test_censo_coincide_con_la_lista_blanca(self):
        hallado = censar_produccion()
        autorizado = set(SITIOS_EQUIPO_ID_PERMITIDOS)
        extra = sorted(set(hallado) - autorizado)
        faltante = sorted(autorizado - set(hallado))

        assert not extra, (
            "sitio(s) NUEVO(s) que leen equipo_id sin blindaje declarado: "
            f"{extra}. Añadir a SITIOS_EQUIPO_ID_PERMITIDOS con su "
            "justificación (BLINDADO si pasa por "
            "EquiposService.resolver_guardado, EXENTO si no resuelve dato "
            "histórico y se explica por qué), o blindarlo de verdad.")
        assert not faltante, (
            "la lista blanca cita sitio(s) que el censo YA NO ENCUENTRA: "
            f"{faltante}. Probable desplazamiento de línea (Trampa 5): "
            "recalcular con git diff --unified=0 y actualizar la cita, o "
            "retirarla si el sitio de verdad desapareció.")


class TestLosBlindadosSiguenLlamandoResolverGuardado:
    """No exigido literalmente por el CAMBIO de la tarea, pero barato y
    cierra una segunda forma de silenciar el tripwire: que alguien retire
    la llamada a resolver_guardado de una función BLINDADA sin tocar su
    cita en la lista blanca (el número de línea del propio `obtener_por_
    id`/`findData` no cambiaría, así que el test de arriba no lo vería)."""

    @pytest.mark.parametrize("archivo,linea", SITIOS_BLINDADOS)
    def test_la_funcion_contenedora_menciona_resolver_guardado(self, archivo, linea):
        ruta = ROOT / archivo
        codigo = ruta.read_text(encoding="utf-8")
        arbol = ast.parse(codigo, filename=str(ruta))
        funcion = _funcion_que_contiene(arbol, linea)
        assert funcion is not None, f"{archivo}:{linea} no cae dentro de ninguna función"
        segmento = ast.get_source_segment(codigo, funcion) or ""
        assert "resolver_guardado" in segmento, (
            f"{archivo}:{linea} está marcado BLINDADO en la lista blanca "
            f"pero su función '{funcion.name}' ya no menciona "
            "resolver_guardado -- ¿se retiró el blindaje de R.3 sin "
            "retirar esta entrada?")


class TestElContratoDeR1YR3SigueEnPie:
    """CAMBIO punto 3: que resolver_guardado siga existiendo, y que
    PUNTEROS_A_EQUIPOS (R.1) siga declarando las dos columnas de §0.8 --
    si alguien añade un puntero nuevo sin declararlo ahí, R.1 dejaría de
    cubrirlo en silencio."""

    def test_resolver_guardado_sigue_existiendo(self):
        assert hasattr(equipos_service_mod.EquiposService, "resolver_guardado"), (
            "R.3 retirado -- EquiposService.resolver_guardado ya no existe")

    def test_punteros_a_equipos_sigue_declarando_las_dos_columnas_de_r1(self):
        """PUNTEROS_A_EQUIPOS es una variable LOCAL de
        `_asegurar_secuencias_sin_duplicados` (no un atributo de módulo
        importable) -- se extrae por AST, buscando el Assign dentro del
        cuerpo de esa función, igual que el resto de este archivo."""
        ruta = ROOT / "data" / "ManejoDatos" / "conection.py"
        codigo = ruta.read_text(encoding="utf-8")
        arbol = ast.parse(codigo, filename=str(ruta))

        funcion = None
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.FunctionDef)
                    and nodo.name == "_asegurar_secuencias_sin_duplicados"):
                funcion = nodo
                break
        assert funcion is not None, (
            "R.1 retirado -- _asegurar_secuencias_sin_duplicados ya no existe")

        asignacion = None
        for nodo in ast.walk(funcion):
            if (isinstance(nodo, ast.Assign)
                    and len(nodo.targets) == 1
                    and isinstance(nodo.targets[0], ast.Name)
                    and nodo.targets[0].id == "PUNTEROS_A_EQUIPOS"):
                asignacion = nodo
                break
        assert asignacion is not None, (
            "PUNTEROS_A_EQUIPOS ya no se declara dentro de "
            "_asegurar_secuencias_sin_duplicados")

        texto = ast.get_source_segment(codigo, asignacion) or ""
        for tabla, columna in (("equipos_medicion", "equipo_id"),
                                ("calculadora_dosimetrica", "equipo_id")):
            assert f'"{tabla}"' in texto and f'"{columna}"' in texto, (
                f"PUNTEROS_A_EQUIPOS ya no declara ({tabla!r}, {columna!r}) "
                "-- R.1 dejaría de cubrir ese puntero en silencio")


class TestElTripwireMuerde:
    """Protocolo de verificación item 1: sin esto, el censor podría estar
    pasando por vacío sobre producción -- que hoy no haya `extra` no
    prueba que el detector SEPA detectar uno. Se ejercita sobre un
    directorio temporal sintético (`tmp_path`), nunca sobre un archivo de
    producción real -- el mecanismo de detección es el mismo
    (`censar_produccion`), parametrizado en `raiz`."""

    def test_un_lector_sin_blindar_se_detecta_nombrando_archivo_y_linea(self, tmp_path):
        falso = tmp_path / "lector_falso.py"
        falso.write_text(
            "class Fake:\n"
            "    def restaurar(self, datos):\n"
            "        equipo_id = datos.get('equipo_id')\n"
            "        return EquiposService.obtener_por_id(equipo_id)\n"
        )
        hallado = censar_produccion(raiz=tmp_path)
        assert ("lector_falso.py", 4) in hallado, (
            f"el censor no detectó el lector falso -- hallado={hallado}")

    def test_retirando_la_llamada_el_mismo_archivo_queda_limpio(self, tmp_path):
        """Mismo archivo, sustituyendo la línea insegura por la segura --
        el 'retirar la línea y exigir verde' del protocolo."""
        limpio = tmp_path / "lector_falso.py"
        limpio.write_text(
            "class Fake:\n"
            "    def restaurar(self, datos):\n"
            "        equipo_id = datos.get('equipo_id')\n"
            "        return EquiposService.resolver_guardado(equipo_id, None, None)\n"
        )
        hallado = censar_produccion(raiz=tmp_path)
        assert hallado == {}, f"quedaron sitios tras retirar el lector falso -- {hallado}"

    def test_un_finddata_de_equipo_id_tambien_se_detecta(self, tmp_path):
        falso = tmp_path / "combo_falso.py"
        falso.write_text(
            "class Fake:\n"
            "    def restaurar(self, equipo_id):\n"
            "        self.combo.findData(equipo_id)\n"
        )
        hallado = censar_produccion(raiz=tmp_path)
        assert ("combo_falso.py", 3) in hallado, hallado

    def test_un_sql_crudo_tambien_se_detecta(self, tmp_path):
        falso = tmp_path / "sql_falso.py"
        falso.write_text(
            "class Fake:\n"
            "    def restaurar(self, cursor, equipo_id):\n"
            "        cursor.execute('SELECT model FROM equipos WHERE id = ?', (equipo_id,))\n"
        )
        hallado = censar_produccion(raiz=tmp_path)
        assert ("sql_falso.py", 3) in hallado, hallado


class TestInmuneAComentariosYDocstrings:
    """Protocolo de verificación item 2. Comentarios y docstrings que
    mencionen equipo_id -- incluso citando el patrón completo -- no deben
    disparar nada."""

    def test_un_comentario_que_mencione_equipo_id_no_dispara_nada(self, tmp_path):
        archivo = tmp_path / "solo_comentario.py"
        archivo.write_text(
            "# EquiposService.obtener_por_id(equipo_id) -- ejemplo en un comentario\n"
            "# self.combo.findData(equipo_id) -- otro ejemplo\n"
            "class Fake:\n"
            "    def nada(self):\n"
            "        pass\n"
        )
        assert censar_produccion(raiz=tmp_path) == {}

    def test_un_docstring_que_cite_el_patron_completo_no_dispara_nada(self, tmp_path):
        archivo = tmp_path / "solo_docstring.py"
        archivo.write_text(
            'class Fake:\n'
            '    def nada(self):\n'
            '        """Antes esta funcion hacia '
            "EquiposService.obtener_por_id(equipo_id) sin blindar, y un "
            'SELECT model FROM equipos WHERE id = ? crudo. Ya no."""\n'
            '        pass\n'
        )
        assert censar_produccion(raiz=tmp_path) == {}


class TestQuitarUnaJustificacionRompeElTest:
    """Protocolo de verificación item 3, contra el censo REAL de
    producción (no un sintético): borrar una entrada de una COPIA de la
    lista blanca debe dejar ese sitio como 'extra' frente al censo real."""

    def test_sin_un_sitio_blindado_conocido_el_censo_muestra_diferencia(self):
        hallado = censar_produccion()
        blanca_incompleta = dict(SITIOS_EQUIPO_ID_PERMITIDOS)
        sitio_retirado = (
            "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py", 3964)  # A.2 (21-09): 3772->3831; B.3 (21-09): 3831->3892; B.4 (21-09): 3892->3964
        del blanca_incompleta[sitio_retirado]

        extra = set(hallado) - set(blanca_incompleta)
        assert sitio_retirado in extra, (
            "quitar una entrada de la lista blanca debería dejarla como "
            "'extra' frente al censo real -- si no aparece, es que el "
            "censo real ya no la está encontrando ahí (línea movida)")


class TestCensoInformativoDePunterosColgando:
    """CAMBIO punto 4: informa, no falla -- nunca debe tumbar la suite por
    un número que cambie con el tiempo (crece con cada borrado del
    catálogo hasta que el físico autorice R.6). Referencia histórica
    medida en §0.2 del plan y reverificada al escribir esta tarea
    (14-09-2026, sobre copia de BaseDatosQA(Rebuild_11-09-2026).db, md5
    sin cambios): 7 en equipos_medicion, 1 en calculadora_dosimetrica."""

    @pytest.mark.skipif(
        not BD_REBUILD_11_09.exists(),
        reason=f"{BD_REBUILD_11_09.name} no está presente en este entorno")
    def test_cuenta_punteros_colgando_sin_afirmar_un_numero_fijo(self, tmp_path, capsys):
        copia = tmp_path / "copia_solo_lectura.db"
        shutil.copy(BD_REBUILD_11_09, copia)
        con = sqlite3.connect(str(copia))
        try:
            colgando_medicion = con.execute(
                "SELECT COUNT(*) FROM equipos_medicion "
                "WHERE equipo_id IS NOT NULL "
                "AND equipo_id NOT IN (SELECT id FROM equipos)"
            ).fetchone()[0]
            colgando_calculadora = con.execute(
                "SELECT COUNT(*) FROM calculadora_dosimetrica "
                "WHERE equipo_id IS NOT NULL "
                "AND equipo_id NOT IN (SELECT id FROM equipos)"
            ).fetchone()[0]
        finally:
            con.close()

        print(f"[R.4 censo informativo] equipos_medicion: {colgando_medicion} "
              f"punteros colgando -- calculadora_dosimetrica: "
              f"{colgando_calculadora} -- (referencia §0.2: 7 y 1)")

        # No falla por el NÚMERO -- solo por que el mecanismo de conteo
        # deje de poder correr. R.6 (resembrar, ámbar) cambiará estos
        # números el día que se ejecute; este test sigue verde igual.
        assert colgando_medicion >= 0
        assert colgando_calculadora >= 0
