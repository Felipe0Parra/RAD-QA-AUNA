"""A6.1 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.6): tripwire de cobertura de
auditoría. Reemplaza al A6 original (§2.4, "wrapper de Conexion") -- ese
mecanismo es ciego a QtSql e invierte la granularidad correcta (§10.1). Este
test hace lo que A6 en verdad necesitaba: recorrer TODO el código de
producción, encontrar TODA función que escriba en la BD (sqlite3 y QtSql --
ambas pasan por los mismos nombres de método: execute/executemany/
executescript/prepare/exec_), y exigir que cada una esté auditada o
justificada.

Las categorías de la allowlist NO son exenciones estáticas: son afirmaciones
verificables.

  - `bootstrap` / `es-la-propia-auditoria`: no verificables (son metadatos
    sobre la naturaleza de la función), pero explícitos y con su motivo.
  - `audita-el-llamador:<archivo>::<qualname>`: el test verifica que ESE
    llamador exista de verdad y contenga una llamada a `registrar()`. Si
    alguien la quita, este test se pone en rojo aunque la allowlist no
    cambie.
  - `detalle-de:<archivo>::<qualname>`: igual, sobre la acción padre.
  - `PENDIENTE-A6.N`: hueco real, todavía sin instrumentar. Es la cola de
    trabajo de §10.7 -- cada tarea borra sus propias entradas al cerrar.

Detector: una escritura es un `INSERT`/`UPDATE`/`DELETE`/`REPLACE` que llega,
literal o vía variable local asignada antes en la misma función, como primer
argumento de un método `execute/executemany/executescript/prepare/exec_`.
`ALTER TABLE`/`CREATE TABLE`/`PRAGMA` no cuentan -- son evolución de esquema
(bootstrap), no acción de usuario sobre datos (medido: los únicos call-sites
de `ALTER TABLE` en producción están todos dentro de funciones de self-heal
ya en la allowlist o de funciones que YA se auditan por otro motivo).
`.exec_`/`.exec` de QtSql están sobrecargados (`QMenu.exec_()`,
`QDialog.exec_()` no son SQL) -- por eso solo cuentan cuando reciben un
argumento cuyo texto resuelto es SQL de escritura; el único `.exec_(<literal>)`
real en producción es un `PRAGMA` (lectura de configuración, no escritura).

Alcance: todo `Codigo_radqa/` salvo tests/build/venv/recursos. 57 funciones
de producción escriben en BD hoy (2026-07-27, después de A6.0); 14 auditan
directamente. Este test verifica que las 43 restantes estén todas explicadas.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "models", "mcc_PTW_read",
}

WRITE_RE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE)\b", re.IGNORECASE)
EXEC_METHODS = {"execute", "executemany", "executescript", "prepare", "exec_", "exec"}


def _literal_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value.strip():
                return v.value
        return None
    return None


def _resolver_alias_registrar(tree):
    """Nombres locales que apuntan a `services.audit_minimo.registrar` en
    ESTE archivo (cada archivo lo importa con su propio alias, normalmente
    `_registrar_auditoria`)."""
    nombres = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "services.audit_minimo":
            for alias in node.names:
                if alias.name == "registrar":
                    nombres.add(alias.asname or alias.name)
    return nombres


class _EscaneadorFunciones(ast.NodeVisitor):
    """Recorre un módulo y registra, por cada función/método, si contiene
    una escritura y si se audita a sí misma. `registro` queda indexado por
    qualname (`Clase.metodo` o `funcion` a nivel de módulo)."""

    def __init__(self, alias_registrar):
        self.alias_registrar = alias_registrar
        self.pila_clases = []
        self.registro = {}  # qualname -> {"escribe": bool, "audita": bool}

    def _qualname(self, nombre):
        return ".".join(self.pila_clases + [nombre])

    def visit_ClassDef(self, node):
        self.pila_clases.append(node.name)
        self.generic_visit(node)
        self.pila_clases.pop()

    def _escanear_funcion(self, node):
        qualname = self._qualname(node.name)
        variables_locales = {}
        escribe = False
        audita = False

        alias_registrar = self.alias_registrar

        class _Interno(ast.NodeVisitor):
            def visit_FunctionDef(self, n):
                pass  # no bajar a funciones/métodos anidados: son otra entrada

            def visit_AsyncFunctionDef(self, n):
                pass

            def visit_Lambda(self, n):
                pass

            def visit_Assign(self, n):
                s = _literal_str(n.value)
                if s is not None:
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            variables_locales[t.id] = s
                self.generic_visit(n)

            def visit_Call(self, n):
                nonlocal escribe, audita
                fname = None
                if isinstance(n.func, ast.Attribute):
                    fname = n.func.attr
                elif isinstance(n.func, ast.Name):
                    fname = n.func.id

                if fname in alias_registrar:
                    audita = True

                if fname in EXEC_METHODS and n.args:
                    arg0 = n.args[0]
                    s = _literal_str(arg0)
                    if s is None and isinstance(arg0, ast.Name):
                        s = variables_locales.get(arg0.id)
                    if s and WRITE_RE.match(s):
                        escribe = True

                self.generic_visit(n)

        _Interno().generic_visit(node)
        self.registro[qualname] = {"escribe": escribe, "audita": audita}

        # seguir bajando para no perder clases/funciones anidadas
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def visit_FunctionDef(self, node):
        self._escanear_funcion(node)

    def visit_AsyncFunctionDef(self, node):
        self._escanear_funcion(node)


def _construir_inventario():
    """registro[(ruta_relativa_str, qualname)] = {"escribe": bool, "audita": bool}"""
    inventario = {}
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(parte in EXCLUDE_DIRS for parte in rel.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        except SyntaxError:
            continue
        alias_registrar = _resolver_alias_registrar(tree)
        escaneador = _EscaneadorFunciones(alias_registrar)
        escaneador.visit(tree)
        rel_str = rel.as_posix()
        for qualname, info in escaneador.registro.items():
            inventario[(rel_str, qualname)] = info
    return inventario


INVENTARIO = _construir_inventario()


# ---------------------------------------------------------------------------
# Allowlist -- 43 funciones que escriben y no se auditan a sí mismas
# (57 funciones con escritura - 14 que auditan directamente, 2026-07-27).
# ---------------------------------------------------------------------------
BOOTSTRAP = "bootstrap"
ES_LA_PROPIA_AUDITORIA = "es-la-propia-auditoria"

ALLOWLIST = {
    # --- bootstrap / self-heal: no es acción de usuario ---
    ("data/ManejoDatos/conection.py", "Conexion._asegurar_catalogos_base"): BOOTSTRAP,
    ("data/ManejoDatos/conection.py", "Conexion.createAdmin"): BOOTSTRAP,
    ("data/ManejoDatos/load.py", "mostrar_controles_imgIX"): BOOTSTRAP,
    ("data/ManejoDatos/load.py", "mostrar_controles_imgHC"): BOOTSTRAP,
    ("data/ManejoDatos/load.py", "mostrar_controles_tac"): BOOTSTRAP,
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py",
     "PruebaMensualBraq.normalizar_fechas_db"): BOOTSTRAP,

    # --- es la propia auditoría ---
    ("services/audit_minimo.py", "registrar"): ES_LA_PROPIA_AUDITORIA,

    # --- audita-el-llamador: verificado, el llamador SÍ contiene registrar() ---
    ("services/dosis_service.py", "DosisService.guardar_datos"):
        "audita-el-llamador:ui/paginasGuia/dialogs.py::DialogCalculadoraDosis.guardar_db",
    ("data/ManejoDatos/obtenerDatosHalcyon.py", "createDB"):
        "audita-el-llamador:data/ManejoDatos/obtenerDatosHalcyon.py::addInfo",

    # --- PENDIENTE-A6.2: identidad y catálogo ---
    ("data/ManejoDatos/usuariosManager.py", "UsuarioData.add_user"): "PENDIENTE-A6.2",
    ("data/ManejoDatos/usuariosManager.py", "UsuarioData.update_password"): "PENDIENTE-A6.2",
    ("ui/paginasGuia/equipos.py", "Config.eliminarEquipo"): "PENDIENTE-A6.2",

    # --- PENDIENTE-A6.3: mensual 600 / IX / Halcyon ---
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py",
     "PruebaMensual600.subirtodo_modificado"): "PENDIENTE-A6.3",
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py",
     "PruebaMensual600.subir_control_cunas"): "PENDIENTE-A6.3",
    ("ui/paginasControles/PruebasMensuales/ix_mensual.py",
     "PruebaMensualIX.guardar_control_conos"): "PENDIENTE-A6.3",
    ("data/ManejoDatos/load.py", "guardar_analisis_placa600"): "PENDIENTE-A6.3",
    ("data/ManejoDatos/load.py", "crear_algo"): "PENDIENTE-A6.3",
    # loadtablacomplex: de sus 7 call-sites reales solo 1 audita hoy
    # (fieldSize->subir_tabla, from_range=3). Los otros 6 -- incluida la vía
    # "optimizada" que comparten 600 mensual Y Halcyon mensual -- no auditan
    # todavía (ver PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7, corrección del
    # mismo día). Pasa a `audita-el-llamador` cuando _subir_tabla_optimizada
    # y los guardar_todas_fse de A6.4 auditen.
    ("data/ManejoDatos/load.py", "loadtablacomplex"): "PENDIENTE-A6.3",
    ("ui/paginasControles/PruebasMensuales/seiscientos_mensual.py",
     "PruebaMensual600._subir_tabla_optimizada"): "PENDIENTE-A6.3",

    # --- PENDIENTE-A6.4: anual (600 / IX / Halcyon) ---
    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py",
     "PruebaAnual600.create_control"): "PENDIENTE-A6.4",
    ("ui/paginasControles/PruebasAnuales/halcyon_anual.py",
     "PruebaAnualHalcyon.subir_imagen_perfil_mlc_db"): "PENDIENTE-A6.4",

    # --- PENDIENTE-A6.5: diario ---
    ("data/ManejoDatos/load.py", "conectarfueradeservicio"): "PENDIENTE-A6.5",

    # --- PENDIENTE-A6.6: braquiterapia ---
    ("data/ManejoDatos/load.py", "guardar_resultado_CambioFuente"): "PENDIENTE-A6.6",
    ("ui/paginasControles/PruebasMensuales/braq_mensual.py",
     "PruebaMensualBraq.actualizar_desplazamiento_en_db"): "PENDIENTE-A6.6",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py",
     "Linealidad.guardar_linealidad"): "PENDIENTE-A6.6",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py",
     "PruebaDiariaBraq.eliminar_fila_resultado"): "PENDIENTE-A6.6",
    ("ui/paginasControles/PruebasDiarias/braquiterapia.py",
     "PosicionamientoInicial.eliminar_fila_resultado"): "PENDIENTE-A6.6",

    # --- PENDIENTE-A6.7: TAC / Catphan (los 2 padres en tac_mensual.py NO
    # escriben directo -- solo llaman a catphan_db.py -- por eso no aparecen
    # aquí como write-sites; van a `detalle-de:` cuando A6.7 los audite) ---
    ("data/ManejoDatos/catphan_TAC/catphan_db.py",
     "guardar_prueba_completa_catphan"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py",
     "eliminar_datos_especificos"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", "guardar_espesor_corte"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", "guardar_tamano_pixel"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py",
     "guardar_resolucion_contraste"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py",
     "guardar_resolucion_espacial"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", "guardar_valores_ct"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", "guardar_linealidad_ct"): "PENDIENTE-A6.7",
    ("data/ManejoDatos/catphan_TAC/catphan_db.py", "guardar_uniformidad"): "PENDIENTE-A6.7",

    # --- PENDIENTE-A6.8: Picket Fence / Starshot (mismo patrón: los 2
    # padres en seiscientos_mensual.py no escriben directo) ---
    ("services/MLCs_calibration_service.py", "pf_db_insertion"): "PENDIENTE-A6.8",
    ("services/MLCs_calibration_service.py", "pf_picket_error_insertion"): "PENDIENTE-A6.8",
    ("services/MLCs_calibration_service.py", "pf_leaf_error_insertion"): "PENDIENTE-A6.8",
    ("services/MLCs_calibration_service.py",
     "pf_highest_leaf_errors_insertion"): "PENDIENTE-A6.8",
    ("services/MLCs_calibration_service.py", "starshot_insert"): "PENDIENTE-A6.8",
    ("services/MLCs_calibration_service.py",
     "starshot_residual_statistics_insert"): "PENDIENTE-A6.8",
    ("services/MLCs_calibration_service.py", "starshot_angles_insertion"): "PENDIENTE-A6.8",
    ("services/MLCs_calibration_service.py",
     "starshot_angular_uniformity_insert"): "PENDIENTE-A6.8",
}


def _resolver_llamador(reason):
    """Para 'audita-el-llamador:<archivo>::<qualname>' o 'detalle-de:...',
    devuelve la clave (archivo, qualname) del llamador nombrado."""
    _, objetivo = reason.split(":", 1)
    archivo, qualname = objetivo.split("::", 1)
    return (archivo, qualname)


class TestTripwireAuditoria:
    def test_toda_funcion_que_escribe_y_no_audita_esta_en_la_allowlist(self):
        sin_explicar = []
        for clave, info in INVENTARIO.items():
            if not info["escribe"] or info["audita"]:
                continue
            if clave not in ALLOWLIST:
                sin_explicar.append(clave)

        assert not sin_explicar, (
            "Función(es) que escriben en BD sin auditar y sin entrada en la "
            "allowlist de A6.1 (tests/test_a6_1_tripwire_auditoria.py) -- "
            "añade `_registrar_auditoria(...)` en el punto que sepa qué "
            "acción hizo el usuario, o documenta el motivo en ALLOWLIST "
            "(PLAN_AUDITORIA_DOS_EJES_21-07.md §10.6):\n" +
            "\n".join(f"  {archivo} :: {qualname}" for archivo, qualname in sin_explicar)
        )

    def test_toda_entrada_de_la_allowlist_corresponde_a_una_funcion_real(self):
        huerfanas = [clave for clave in ALLOWLIST if clave not in INVENTARIO]
        assert not huerfanas, (
            "Entrada(s) de la allowlist de A6.1 que ya no corresponden a "
            "ninguna función del código (renombrada o borrada) -- "
            "actualiza tests/test_a6_1_tripwire_auditoria.py:\n" +
            "\n".join(f"  {archivo} :: {qualname}" for archivo, qualname in huerfanas)
        )

    def test_audita_el_llamador_y_detalle_de_apuntan_a_algo_que_de_verdad_audita(self):
        mal_referenciadas = []
        for clave, reason in ALLOWLIST.items():
            if not (reason.startswith("audita-el-llamador:") or reason.startswith("detalle-de:")):
                continue
            llamador = _resolver_llamador(reason)
            info = INVENTARIO.get(llamador)
            if info is None:
                mal_referenciadas.append((clave, reason, "el llamador no existe"))
            elif not info["audita"]:
                mal_referenciadas.append((clave, reason, "el llamador ya NO contiene registrar()"))

        assert not mal_referenciadas, (
            "Entrada(s) 'audita-el-llamador'/'detalle-de' cuya referencia ya "
            "no es válida -- si alguien quitó el registrar() del llamador, "
            "este es exactamente el caso que A6.1 debe atrapar:\n" +
            "\n".join(f"  {a} :: {b} -> {reason} ({motivo})"
                      for (a, b), reason, motivo in mal_referenciadas)
        )
