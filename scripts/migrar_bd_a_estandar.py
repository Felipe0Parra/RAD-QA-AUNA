"""Trae CUALQUIER archivo .db (una copia vieja, una BD de otra sesión de
trabajo, un backup de hace meses) al estándar de esquema que usa la versión
ACTUAL de la app -- para poder incorporar datos que se llenaron en una forma
"antigua" de la base sin que falte ninguna columna/tabla de las que se han
ido agregando a lo largo de este proyecto (M1,
PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8, petición del físico 2026-07-24).

Diseño clave -- por qué esto no puede quedar desactualizado: en vez de
reimplementar la lista de columnas/tablas que la app ha ido agregando (una
segunda copia que habría que recordar mantener sincronizada para siempre),
este script REUTILIZA exactamente la misma secuencia de arranque que corre
`Conexion.__init_connection()` cada vez que la app abre un archivo --
apuntándola temporalmente al archivo dado, con el mismo mecanismo de
aislamiento que usa `tests/conftest.py` (parchear `conection.ruta_base_datos`
a la ruta deseada). Cualquier `_asegurar_columna`/`CREATE TABLE IF NOT
EXISTS` que se agregue en el futuro al arranque de la app queda cubierto acá
automáticamente, sin tocar este archivo.

Además de esquema, normaliza UN dato histórico conocido: el centinela de
texto `" ---- "` que versiones anteriores de `create_control` guardaban en
`controles.user_id_f2` cuando no había 2º físico (X1, mismo plan) -- ese
centinela viola la FOREIGN KEY a `users(fullname)` y bloquearía activar
`PRAGMA foreign_keys=ON` sobre una BD antigua. Se convierte a NULL (la
representación correcta; todo lector ya la trata igual). Nunca se inventan
otros valores ni se tocan columnas/filas que no sean estas dos cosas.

Modo de uso:
    python scripts/migrar_bd_a_estandar.py <ruta.db>              # dry-run
    python scripts/migrar_bd_a_estandar.py <ruta.db> --aplicar    # aplica

Por defecto es DRY-RUN (solo reporta qué cambiaría, corriendo la migración
real sobre una copia temporal -- nunca toca el archivo original). Con
--aplicar: hace un backup con timestamp junto al archivo ANTES de tocarlo,
corre `PRAGMA integrity_check` antes y después, y aborta sin escribir nada
si la BD ya venía con problemas de integridad. Idempotente: correrlo dos
veces sobre la misma BD no repite ni deshace nada la segunda vez.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.duplicados_control import duplicados_controles

CENTINELA_SEGUNDO_FISICO = " ---- "

# F6 (PLAN_F_CIERRE_ESTANDAR_29-07.md): identidad para el respaldo previo a
# la migración estructural (F1) cuando la dispara ESTE script, en vez de la
# apertura normal de la app -- nunca un nombre de persona inventado.
ETIQUETA_EJECUCION_TERMINAL = "ejecucion desde terminal"

CABECERA_SQLITE = b"SQLite format 3\x00"


def _validar_archivo_bd(ruta_bd):
    """F-BD2 (INFORME_BARRIDO_BD_RUTAS_24-07.md): `sqlite3.connect()` CREA un
    archivo vacío si la ruta no existe -- sin esta guarda, un typo en la ruta
    hacía que la herramienta "migrara" con éxito una BD vacía recién creada
    en la ruta equivocada (reportando `integrity_check: ok` y 66 tablas
    nuevas), y el físico creería que migró su archivo real. Se valida ANTES
    de abrir cualquier conexión: la ruta existe, es un archivo, y trae la
    cabecera SQLite (primeros 16 bytes) -- toda BD real la tiene; un archivo
    de 0 bytes o de otro formato, no."""
    if not os.path.isfile(ruta_bd):
        print(f"ERROR: no existe ningún archivo en la ruta indicada:\n"
              f"  {ruta_bd}\n"
              f"Revise la ruta -- esta herramienta nunca crea archivos nuevos.")
        sys.exit(1)
    with open(ruta_bd, "rb") as f:
        cabecera = f.read(16)
    if cabecera != CABECERA_SQLITE:
        print(f"ERROR: el archivo indicado no es una base de datos SQLite "
              f"válida:\n  {ruta_bd}\n"
              f"No se hizo ningún cambio.")
        sys.exit(1)


def _consolidar_wal(ruta_bd):
    """I3/F-BD3 (lección R2 aplicada a la propia herramienta): en modo WAL,
    los commits recientes pueden vivir SOLO en el archivo `-wal` -- una BD
    traída de otra máquina puede llegar así (el rebuild del físico del 23-07
    traía un -wal de 473 KB sin consolidar). Sin este paso: el backup de
    `--aplicar` copiaba solo el `.db` (backup incompleto) y el dry-run
    simulaba sobre una copia sin esos datos. `wal_checkpoint(TRUNCATE)`
    consolida todo al `.db` y deja el `-wal` en cero -- preserva el contenido
    lógico, solo lo reubica -- de modo que una copia simple del `.db` ya es
    la base completa."""
    con = sqlite3.connect(ruta_bd)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        con.close()


def _copiar_set_sqlite(ruta_origen, ruta_destino):
    """Copia `.db` + `-wal` + `-shm` (los que existan) -- el 'set' completo
    de un archivo SQLite en modo WAL. Copiar solo el `.db` puede perder los
    commits aún no consolidados (la trampa demostrada en R2)."""
    for ext in ("", "-wal", "-shm"):
        origen = ruta_origen + ext
        if os.path.exists(origen):
            shutil.copy(origen, ruta_destino + ext)


def _inventario_esquema(con):
    """dict tabla -> set(columnas) -- para diffear antes/después."""
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    return {t: set(c[1] for c in con.execute(f"PRAGMA table_info('{t}')").fetchall())
            for t in tablas}


def _contar_centinela(con):
    try:
        return con.execute(
            "SELECT COUNT(*) FROM controles WHERE user_id_f2 = ?",
            (CENTINELA_SEGUNDO_FISICO,)).fetchone()[0]
    except sqlite3.OperationalError:
        return 0  # tabla controles aun no existe (BD recien creada)


CATALOGOS_BASE = ["tipos_prueba", "materiales_ct", "regiones_uniformidad", "energias"]

# I2 (PLAN §10): las tablas que cargan el TRABAJO DE QC del físico -- la
# razón de ser de incorporar una BD vieja es no perder ni una fila de estas.
# El reporte demuestra conteos antes==después; si alguno bajara (no debería
# poder pasar: la migración es puramente aditiva), se avisa en mayúsculas.
TABLAS_QC = ["controles", "dosimetriaMen", "preguntas", "tamano_campo",
             "pruebas", "calculadora_dosimetrica"]


def _contar_qc(con):
    conteos = {}
    for tabla in TABLAS_QC:
        try:
            conteos[tabla] = con.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
        except sqlite3.OperationalError:
            conteos[tabla] = 0  # la tabla aún no existía en la BD vieja
    return conteos


def _reportar_qc(qc_antes, qc_despues):
    print("\n--- Registros de QC preservados ---")
    perdida = False
    for tabla in TABLAS_QC:
        antes, despues = qc_antes[tabla], qc_despues[tabla]
        marca = ""
        if despues < antes:
            perdida = True
            marca = "  <<< PERDIDA DE REGISTROS -- NO USAR, RESTAURAR EL BACKUP"
        print(f"  {tabla}: {antes} -> {despues}{marca}")
    if not perdida:
        print("  Ningún registro de QC se perdió (la migración nunca borra filas).")
    return perdida


def _contar_todas_las_tablas(con):
    """F2 (PLAN_F_CIERRE_ESTANDAR_29-07.md): censo de TODAS las tablas, no
    solo las 6 de TABLAS_QC -- con la migración estructural (E10) recreando
    hasta 59 tablas en una sola corrida, limitar la vigilancia de "ninguna
    fila perdida" a 6 dejaba las otras 63 sin comprobar."""
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'").fetchall()]
    conteos = {}
    for tabla in tablas:
        try:
            conteos[tabla] = con.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
        except sqlite3.OperationalError:
            conteos[tabla] = 0
    return conteos


def _reportar_censo_completo(censo_antes, censo_despues):
    """Extiende la garantía de `_reportar_qc` (que solo vigila las 6 tablas
    destacadas) a TODAS las demás. Devuelve True si alguna tabla (fuera de
    las ya destacadas en 'Registros de QC preservados') perdió filas."""
    otras = sorted(set(censo_despues) - set(TABLAS_QC))
    perdida = [(t, censo_antes.get(t, 0), censo_despues[t])
               for t in otras if censo_despues[t] < censo_antes.get(t, 0)]
    print(f"\n--- Censo completo ({len(censo_despues)} tablas revisadas) ---")
    if perdida:
        print("  ALERTA -- estas tablas (fuera de las destacadas arriba) "
              "PERDIERON filas:")
        for tabla, antes, despues in perdida:
            print(f"    {tabla}: {antes} -> {despues}  <<< PERDIDA DE REGISTROS")
    else:
        print(f"  Las {len(otras)} tablas restantes conservan sus conteos "
              "(ninguna perdió filas).")
    return bool(perdida)


def _reportar_duplicados_controles(duplicados):
    """U1 (PLAN_NUCLEO_04-08.md, Bloque U): duplicados por (equipo, control,
    mes/año) entre las filas ACTIVAS de `controles` -- la precondición que
    U2 (el índice UNIQUE parcial) necesita ver ANTES de intentar crearse.
    Solo reporta; nunca borra ni corrige nada. Devuelve True si hay
    duplicados (para que el llamador pueda decidir no seguir con U2)."""
    print("\n--- Duplicados de controles (unicidad DP-06) ---")
    if not duplicados:
        print("  Ningún duplicado por (equipo, control, mes/año) entre las "
              "filas activas.")
        return False
    print(f"  ALERTA -- {len(duplicados)} grupo(s) duplicado(s), requieren "
          f"decisión del físico (no se toca nada automáticamente):")
    for grupo in duplicados:
        print(f"    {grupo['equipo']} / {grupo['control']} / "
              f"{grupo['mes']:02d}/{grupo['anio']}: ids {grupo['ids']}")
    return True


def _inventario_estructural(con):
    """F2: estado de las cuatro migraciones estructurales de PLAN_E, para
    poder diffear antes/después y reportar lo que antes quedaba en silencio
    (recrear 59 tablas sin decir que las recreó)."""
    from data.ManejoDatos.conection import _tablas_con_borrado_en_cascada
    cascada = set(_tablas_con_borrado_en_cascada(con.cursor()))
    triggers = set(r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall())
    try:
        roles = dict(con.execute(
            "SELECT rol_sistema, COUNT(*) FROM users GROUP BY rol_sistema"
        ).fetchall())
    except sqlite3.OperationalError:
        roles = {}
    try:
        seq_dup = con.execute(
            "SELECT COUNT(*) FROM (SELECT name FROM sqlite_sequence "
            "GROUP BY name HAVING COUNT(*) > 1)").fetchone()[0]
    except sqlite3.OperationalError:
        seq_dup = 0
    try:
        # Z11 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md §6.4-S7/§7): el
        # índice se crea al arranque (_asegurar_indice_unico_controles), pero
        # el reporte no decía nada al respecto -- desde aquí no había forma
        # de confirmar que la unicidad de controles quedó activa.
        indice_unico_controles = bool(con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_controles_unico_mes'").fetchone())
    except sqlite3.OperationalError:
        indice_unico_controles = False
    return {"cascada": cascada, "triggers": triggers, "roles": roles,
            "seq_dup": seq_dup, "indice_unico_controles": indice_unico_controles}


def _reportar_cambios_estructurales(est_antes, est_despues, duplicados_controles=None):
    """F2: antes, recrear 59 tablas a RESTRICT y crear triggers anti-borrado
    no aparecía en ningún lado del reporte -- el físico no tenía forma de
    saber, leyendo la salida, que eso había ocurrido.

    Z11: la línea del índice único de controles SIEMPRE se imprime, con una
    de tres estados posibles ("creado" / "ya existía" / "NO CREADO -- hay N
    duplicados") -- que el silencio deje de ser un estado posible, mismo
    criterio que _asegurar_indice_unico_controles ya aplica al imprimir por
    consola en el arranque de la app."""
    print("\n--- Cambios estructurales ---")
    migradas = sorted(est_antes["cascada"] - est_despues["cascada"])
    if migradas:
        print(f"  Tablas migradas de borrado en cascada a RESTRICT: {len(migradas)}")
        for tabla in migradas:
            print(f"    {tabla}")

    triggers_nuevos = sorted(est_despues["triggers"] - est_antes["triggers"])
    if triggers_nuevos:
        print(f"  Triggers anti-borrado creados: {triggers_nuevos}")

    if est_despues["roles"] and est_despues["roles"] != est_antes["roles"]:
        print(f"  Roles de sistema asignados: {est_despues['roles']}")

    if est_antes["seq_dup"] and not est_despues["seq_dup"]:
        print(f"  Filas duplicadas de sqlite_sequence normalizadas: "
              f"{est_antes['seq_dup']} tabla(s)")

    if not (migradas or triggers_nuevos
            or (est_despues["roles"] and est_despues["roles"] != est_antes["roles"])
            or (est_antes["seq_dup"] and not est_despues["seq_dup"])):
        print("  (sin cambios estructurales -- la base ya estaba al día)")

    if est_despues["indice_unico_controles"]:
        if est_antes["indice_unico_controles"]:
            print("  Índice único de controles: ya existía")
        else:
            print("  Índice único de controles: creado")
    elif duplicados_controles:
        print(f"  Índice único de controles: NO CREADO -- hay "
              f"{len(duplicados_controles)} grupo(s) duplicado(s) por "
              f"(equipo, control, mes/año) entre filas activas (ver "
              f"'Duplicados de controles' arriba)")
    else:
        print("  Índice único de controles: NO CREADO")


def _contar_catalogos_base(con):
    """INSERT-audit (§8): estos 4 catálogos nunca se sembraban desde el
    código (solo se creaban vacíos) -- reportar cuántas filas tenían antes y
    después deja explícito cuándo la migración sembró un catálogo vacío."""
    conteos = {}
    for tabla in CATALOGOS_BASE:
        try:
            conteos[tabla] = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        except sqlite3.OperationalError:
            conteos[tabla] = 0
    return conteos


def _aplicar_migracion_en(ruta_bd, usuario=None):
    """Corre la MISMA secuencia de arranque que usa la app real
    (Conexion.__init_connection) apuntada a `ruta_bd`, más la normalización
    del centinela de user_id_f2. No reimplementa ninguna migración -- las
    reutiliza tal cual están hoy en el código de producción."""
    from data.ManejoDatos import conection as conection_mod

    instancia_previa = conection_mod.Conexion._instance
    ruta_original = conection_mod.ruta_base_datos
    usuario_respaldo_previo = conection_mod.USUARIO_RESPALDO_MIGRACION
    conection_mod.Conexion._instance = None
    conection_mod.ruta_base_datos = lambda: ruta_bd
    # F6: si `_asegurar_fk_on_delete_restrict` dispara un respaldo dentro de
    # `Conexion()` (BD aún en CASCADE), que quede identificado con quien
    # lanzó el script -- nunca con un nombre de persona inventado si no se
    # pasó --usuario. Restaurado a None (nunca queda puesto) en el `finally`.
    conection_mod.USUARIO_RESPALDO_MIGRACION = usuario or ETIQUETA_EJECUCION_TERMINAL
    try:
        instancia = conection_mod.Conexion()
        con = instancia.con
        filas_centinela = _contar_centinela(con)
        if filas_centinela:
            con.execute(
                "UPDATE controles SET user_id_f2 = NULL WHERE user_id_f2 = ?",
                (CENTINELA_SEGUNDO_FISICO,))
            con.commit()
            try:
                from services.audit_minimo import registrar, ACCION_MIGRACION
                registrar(usuario, ACCION_MIGRACION, tabla="controles",
                          detalle=(f"normalizadas {filas_centinela} fila(s) "
                                   f"con el centinela historico de 2do "
                                   f"fisico (' ---- ' -> NULL)"),
                          ruta_db=ruta_bd)
            except Exception:
                pass  # el audit_log del archivo destino es best-effort
        con.close()

        # I1 (PLAN §10, decisión del físico 2026-07-24): saneamiento del
        # catálogo de equipos (H2.6/H2.10) POR DEFECTO, como parte de la
        # migración. Es seguro incluso sobre una BD que NO sea del linaje
        # esperado: cada cambio declara su estado ANTES exacto (verificado
        # contra los certificados de calibración reales) y la guarda de
        # deriva SALTA con aviso cualquier fila que no coincida, sin tocarla.
        # Cada corrección aplicada queda auditada en el audit_log de la BD
        # destino (el script ya lo hace vía registrar(ruta_db=...)).
        from scripts.saneamiento_equipos_h26 import aplicar_saneamiento
        resultado_equipos = aplicar_saneamiento(ruta_bd, usuario=usuario)
    finally:
        conection_mod.ruta_base_datos = ruta_original
        conection_mod.Conexion._instance = instancia_previa
        conection_mod.USUARIO_RESPALDO_MIGRACION = usuario_respaldo_previo
    return filas_centinela, resultado_equipos


def _reportar_diff(inv_antes, inv_despues, sentinelas_antes, sentinelas_normalizadas,
                    catalogos_antes=None, catalogos_despues=None):
    print("\n--- Cambios de esquema ---")
    tablas_nuevas = sorted(set(inv_despues) - set(inv_antes))
    if tablas_nuevas:
        print("  Tablas nuevas creadas:", tablas_nuevas)
    hubo_columnas = False
    for tabla in sorted(inv_despues):
        antes = inv_antes.get(tabla, set())
        nuevas_cols = inv_despues[tabla] - antes
        if nuevas_cols and tabla in inv_antes:
            hubo_columnas = True
            print(f"  {tabla}: columna(s) nueva(s) {sorted(nuevas_cols)}")
    if not tablas_nuevas and not hubo_columnas:
        print("  (sin cambios de esquema -- la base ya estaba al día)")

    print("\n--- Normalización de datos (X1) ---")
    print(f"  Filas con el centinela histórico de 2º físico (' ---- '): "
          f"{sentinelas_antes} encontradas, {sentinelas_normalizadas} normalizadas a NULL")

    if catalogos_antes is not None and catalogos_despues is not None:
        print("\n--- Catálogos base (prerrequisito de foreign_keys=ON) ---")
        hubo_siembra = False
        for tabla in CATALOGOS_BASE:
            antes, despues = catalogos_antes[tabla], catalogos_despues[tabla]
            if despues > antes:
                hubo_siembra = True
                print(f"  {tabla}: sembradas {despues - antes} fila(s) "
                      f"({antes} -> {despues})")
        if not hubo_siembra:
            print("  (los 4 catálogos ya estaban sembrados -- sin cambios)")


def _reportar_equipos(resultado_equipos):
    """I1: qué hizo el saneamiento de equipos (H2.6/H2.10) en esta corrida."""
    print("\n--- Saneamiento del catálogo de equipos (certificados H2.6/H2.10) ---")
    aplicados = resultado_equipos["aplicados"]
    ya = resultado_equipos["ya_aplicados"]
    deriva = resultado_equipos["con_deriva"]
    if aplicados:
        print(f"  corregidas en esta corrida: {len(aplicados)} fila(s)")
        for c in aplicados:
            print(f"    id={c['id']}: {c['motivo']}")
    if ya:
        print(f"  ya estaban corregidas (idempotencia): {len(ya)} fila(s)")
    if deriva:
        print(f"  ATENCION -- saltadas por deriva: {len(deriva)} fila(s) no "
              f"coinciden con el estado esperado de los certificados; se "
              f"dejaron INTACTAS, revisar a mano:")
        for c in deriva:
            print(f"    id={c['id']}: estado actual {c['actual']}")
    if not (aplicados or ya or deriva):
        print("  (ninguna fila coincide con el catálogo de este linaje -- "
              "nada que corregir)")


def migrar(ruta_bd, aplicar=False, usuario=None):
    """Punto de entrada reutilizable (además de la CLI). Devuelve un dict
    con el resultado -- útil para tests y para invocarlo desde la propia
    app en el futuro sin pasar por subprocess."""
    ruta_bd = str(ruta_bd)
    _validar_archivo_bd(ruta_bd)
    con_antes = sqlite3.connect(ruta_bd)
    try:
        integridad_antes = con_antes.execute("PRAGMA integrity_check").fetchone()[0]
        inventario_antes = _inventario_esquema(con_antes)
        sentinelas_antes = _contar_centinela(con_antes)
        catalogos_antes = _contar_catalogos_base(con_antes)
        qc_antes = _contar_qc(con_antes)
        censo_antes = _contar_todas_las_tablas(con_antes)
        estructural_antes = _inventario_estructural(con_antes)
    finally:
        con_antes.close()

    print(f"Base de datos: {ruta_bd}")
    print(f"integrity_check antes: {integridad_antes}")

    if not aplicar:
        print("\n[MODO DRY-RUN] No se modifica el archivo original. "
              "Use --aplicar para aplicar los cambios de verdad.\n")
        with tempfile.TemporaryDirectory() as tmp:
            copia = str(Path(tmp) / "copia_para_simular.db")
            # I3/F-BD3: set completo (.db + -wal + -shm), no solo el .db --
            # si la BD entrante trae commits sin consolidar en el -wal, la
            # simulación debe verlos igual que los vería la app real.
            _copiar_set_sqlite(ruta_bd, copia)
            _consolidar_wal(copia)
            sentinelas_normalizadas, equipos = _aplicar_migracion_en(copia, usuario=usuario)
            con_copia = sqlite3.connect(copia)
            try:
                inventario_despues = _inventario_esquema(con_copia)
                catalogos_despues = _contar_catalogos_base(con_copia)
                qc_despues = _contar_qc(con_copia)
                censo_despues = _contar_todas_las_tablas(con_copia)
                estructural_despues = _inventario_estructural(con_copia)
                duplicados_controles_despues = duplicados_controles(con_copia)
            finally:
                con_copia.close()
        _reportar_diff(inventario_antes, inventario_despues,
                        sentinelas_antes, sentinelas_normalizadas,
                        catalogos_antes, catalogos_despues)
        _reportar_equipos(equipos)
        _reportar_cambios_estructurales(estructural_antes, estructural_despues,
                                     duplicados_controles_despues)
        _reportar_qc(qc_antes, qc_despues)
        _reportar_censo_completo(censo_antes, censo_despues)
        _reportar_duplicados_controles(duplicados_controles_despues)
        return {"aplicado": False, "integridad_antes": integridad_antes,
                "sentinelas_antes": sentinelas_antes, "equipos": equipos,
                "qc_antes": qc_antes, "qc_despues": qc_despues,
                "censo_antes": censo_antes, "censo_despues": censo_despues,
                "duplicados_controles": duplicados_controles_despues}

    if integridad_antes != "ok":
        print(f"ALERTA: integrity_check antes de migrar dio "
              f"'{integridad_antes}' (no 'ok') -- revise la base antes de "
              f"continuar. Se aborta sin hacer ningún cambio.")
        sys.exit(1)

    # I3/F-BD3: consolidar el WAL de la BD entrante ANTES del backup --
    # preserva el contenido lógico (solo lo reubica del -wal al .db), y
    # garantiza que el backup por copia simple del .db sea la base COMPLETA
    # aunque la BD haya llegado con un -wal sin consolidar.
    _consolidar_wal(ruta_bd)

    respaldo = f"{ruta_bd}.pre_migracion_{datetime.now():%Y%m%d_%H%M%S}.bak"
    shutil.copy(ruta_bd, respaldo)
    print(f"Backup creado: {respaldo}")

    sentinelas_normalizadas, equipos = _aplicar_migracion_en(ruta_bd, usuario=usuario)

    con_despues = sqlite3.connect(ruta_bd)
    try:
        integridad_despues = con_despues.execute("PRAGMA integrity_check").fetchone()[0]
        inventario_despues = _inventario_esquema(con_despues)
        catalogos_despues = _contar_catalogos_base(con_despues)
        qc_despues = _contar_qc(con_despues)
        censo_despues = _contar_todas_las_tablas(con_despues)
        estructural_despues = _inventario_estructural(con_despues)
        duplicados_controles_despues = duplicados_controles(con_despues)
    finally:
        con_despues.close()

    print(f"integrity_check después: {integridad_despues}")
    _reportar_diff(inventario_antes, inventario_despues,
                    sentinelas_antes, sentinelas_normalizadas,
                    catalogos_antes, catalogos_despues)
    _reportar_equipos(equipos)
    _reportar_cambios_estructurales(estructural_antes, estructural_despues,
                                     duplicados_controles_despues)
    hubo_perdida_qc = _reportar_qc(qc_antes, qc_despues)
    hubo_perdida_censo = _reportar_censo_completo(censo_antes, censo_despues)
    _reportar_duplicados_controles(duplicados_controles_despues)

    if integridad_despues != "ok":
        print(f"ALERTA: integrity_check después de migrar dio "
              f"'{integridad_despues}' (no 'ok'). El backup previo está en "
              f"{respaldo} -- restáurelo y avise antes de seguir usando "
              f"este archivo.")
        sys.exit(1)

    if hubo_perdida_qc or hubo_perdida_censo:
        # Tripwire defensivo: la migración es puramente aditiva, así que
        # esto no debería poder dispararse jamás -- pero si algún cambio
        # futuro lo rompiera, el físico debe enterarse RUIDOSAMENTE y con la
        # instrucción de restaurar, no por un número menor en una tabla.
        print(f"\nALERTA GRAVE: algún conteo de fila BAJÓ tras la migración "
              f"(ver arriba). Restaure el backup ({respaldo}) y NO use este "
              f"archivo.")
        sys.exit(1)

    print(f"\nListo. Backup de seguridad conservado en: {respaldo}")
    return {"aplicado": True, "respaldo": respaldo,
            "integridad_antes": integridad_antes,
            "integridad_despues": integridad_despues,
            "sentinelas_normalizadas": sentinelas_normalizadas,
            "equipos": equipos,
            "qc_antes": qc_antes, "qc_despues": qc_despues,
            "censo_antes": censo_antes, "censo_despues": censo_despues,
            "duplicados_controles": duplicados_controles_despues}


def _main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ruta_bd", help="Ruta al archivo .db a migrar")
    parser.add_argument("--aplicar", action="store_true",
                         help="Aplica los cambios de verdad (por defecto "
                              "solo reporta que cambiaría -- dry-run)")
    parser.add_argument("--usuario", default=None,
                         help="Nombre para dejar auditado quién corrió la migración")
    args = parser.parse_args()
    migrar(args.ruta_bd, aplicar=args.aplicar, usuario=args.usuario)


if __name__ == "__main__":
    _main()
