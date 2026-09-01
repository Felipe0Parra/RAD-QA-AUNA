import sqlite3
import sys
import os
import re
from data.ManejoDatos.encriptarInfo import encrypt_data
import traceback


def ruta_datos(nombre_archivo):
    """
    Ruta absoluta para archivos de datos mutables (base de datos, JSON de
    campos, etc.) anclada a la carpeta del ejecutable (congelado) o a la raíz
    del proyecto (desarrollo), en vez de depender del directorio de trabajo
    actual del proceso (cwd).
    """
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(base_dir, nombre_archivo)


def ruta_base_datos():
    """
    Resuelve la ruta absoluta de BaseDatosQA.db anclada a la ubicación real del
    ejecutable (o de la raíz del proyecto en desarrollo), en vez de depender del
    directorio de trabajo actual del proceso (cwd). Antes de esta corrección, la
    ruta relativa 'BaseDatosQA.db' hacía que la aplicación pudiera terminar
    leyendo/escribiendo un archivo distinto según desde dónde se lanzara el
    ejecutable, bifurcando los datos en dos copias divergentes con el tiempo.
    """
    return ruta_datos('BaseDatosQA.db')


class _ConexionUnaVez:
    """T7 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md): envoltorio de una
    conexión sqlite3 que además se puede usar como `with` -- cierra la
    conexión REAL al salir del bloque.

    El `with` NATIVO de `sqlite3.Connection` no cierra nada (solo hace
    commit/rollback de la transacción, un malentendido frecuente); por
    eso `Conexion.conectar()` devuelve esto en vez de la conexión desnuda:
    `with Conexion().conectar() as con:` cierra de verdad, y es lo que
    hace que el patrón correcto sea el fácil. Cualquier sitio que siga
    usando la conexión directamente (`con = Conexion().conectar()`, sin
    `with`) no se rompe: todo lo que no sea `__enter__`/`__exit__` se
    reenvía a la conexión real."""

    def __init__(self, con):
        self._con = con

    def __getattr__(self, nombre):
        return getattr(self._con, nombre)

    def __enter__(self):
        return self._con

    def __exit__(self, exc_type, exc, tb):
        # R1 (PLAN_FUGA_CONEXIONES_01-09.md §8.8): [medido] `close()` solo
        # YA revierte una transacción abierta (SQLite lo hace al cerrar el
        # handle) -- este `rollback()` explícito no cambia el resultado,
        # pero hace el invariante de P1 ("sin transacción abierta") una
        # garantía LEGIBLE en el código, no un efecto colateral implícito
        # del que depender. NUNCA `commit()`: eso convertiría un guardado
        # interrumpido a medias en una escritura parcial comprometida.
        if self._con.in_transaction:
            self._con.rollback()
        self._con.close()
        return False


def aplicar_pragmas_conexion(con):
    """H2.5 (auditoría 2026-07-14): WAL + busy_timeout, en UN solo sitio (antes
    estaban duplicados en las 3 fábricas de conexión -> riesgo de
    desincronización, TEMA B del PLAN_HI). journal_mode=WAL elimina el
    bloqueo lector<->escritor; busy_timeout=30000 hace que un segundo
    escritor espere en vez de fallar con 'database is locked' (doble patrón
    de conexión de esta app: el singleton persistente de Conexion conviviendo
    con conexiones nuevas por llamada en conectar()/DosisService).

    W2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): foreign_keys=ON en
    TODAS las conexiones sqlite3 de la app (antes solo lo activaba, de forma
    aislada, el camino QtSql del borrado genérico -- load.py `eliminarRegistro`
    -- dejando huérfano cualquier INSERT hecho por las demás conexiones; esa
    inconsistencia es la causa habilitante de H-A, la dosimetría huérfana
    tras borrar un control). SQLite NO hereda este flag entre conexiones ni
    lo persiste en el archivo -- hay que pedirlo en cada `sqlite3.connect()`,
    por eso vive en el mismo punto único que WAL/busy_timeout. Prerrequisitos
    verificados antes de activarlo (X1: controles.user_id_f2 ya no guarda el
    centinela ' ---- ', que violaba su FK a users; INSERT-audit: los 4
    catálogos con FK RESTRICT -- tipos_prueba/materiales_ct/
    regiones_uniformidad/energias -- se siembran al arranque). NO retroactivo:
    huérfanos que ya existían en una BD (116 en producción, heredados de la
    fusión 2026-07-03) no se tocan ni se resuelven solos -- FK ON solo valida
    escrituras NUEVAS."""
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def checkpoint_wal(con):
    """R2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): en modo WAL (H2.5), los
    commits recientes pueden vivir SOLO en el archivo "-wal", no en el .db
    principal, hasta que ocurre un checkpoint. Copiar/mover la BD llevándose
    solo el .db (sin "-wal"/"-shm", o sin checkpoint antes) puede perder esos
    commits en silencio -- el "verificar las rutas" que pidió el físico
    (2026-07-23) tras traer una copia de la BD con un "-wal" de 473 KB sin
    consolidar.

    TRUNCATE consolida todo el WAL al .db y además vacía el archivo -wal (a
    diferencia de PASSIVE/FULL, que solo lo intentan sin garantizar que quede
    en cero) -- así una copia posterior del .db, aunque no incluya el -wal,
    queda completa. Best-effort: nunca lanza (mismo principio que
    audit_minimo.registrar()) -- un fallo al checkpointar no debe impedir que
    la app siga cerrando.
    """
    if con is None:
        return
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as ex:
        print("Error al hacer checkpoint del WAL:", ex)


def _asegurar_columna(cursor, tabla, columna, ddl):
    """Migración mínima idempotente: agrega la columna si no existe.

    Mismo patrón ya usado en DosisService._asegurar_columna
    (services/dosis_service.py) para calculadora_dosimetrica -- no hay un
    sistema de migraciones real en el proyecto (deuda conocida); CREATE TABLE
    IF NOT EXISTS solo cubre bases de datos nuevas, las existentes (copias de
    producción ya desplegadas) necesitan un ALTER TABLE explícito. Con
    DEFAULT constante, SQLite hace que las filas ya existentes devuelvan ese
    valor sin necesidad de un UPDATE.
    """
    cols = [c[1] for c in cursor.execute(f"PRAGMA table_info('{tabla}')").fetchall()]
    if columna not in cols:
        cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {ddl}")


def _tablas_con_borrado_en_cascada(cur):
    """Tablas cuyo esquema aún declara la cascada vieja de borrado (ver
    `_asegurar_fk_on_delete_restrict`) en alguna FK.

    F1 (PLAN_F_CIERRE_ESTANDAR_29-07.md): fuente ÚNICA para dos consumidores
    que antes podían desincronizarse -- `_asegurar_fk_on_delete_restrict`
    (que las recrea en RESTRICT) y el respaldo previo a esa recreación (que
    debe activarse exactamente cuando la primera tiene trabajo que hacer, ni
    antes ni después). Vacío en cualquier BD ya migrada o nacida del DDL
    actual (que ya declara RESTRICT) -- ahí ninguno de los dos consumidores
    hace nada.
    """
    pendientes = []
    for (nombre,) in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'").fetchall():
        for fk in cur.execute(f"PRAGMA foreign_key_list('{nombre}')").fetchall():
            if fk[6] == "CASCADE":  # on_delete
                pendientes.append(nombre)
                break
    return pendientes


MOTIVO_RESPALDO_MIGRACION_ESTRUCTURAL = "respaldo previo a la migracion estructural (E10)"

# F6 (PLAN_F_CIERRE_ESTANDAR_29-07.md): identidad a asociar con el respaldo
# previo a la migración estructural (F1) cuando quien lo dispara es
# `scripts/migrar_bd_a_estandar.py`, no la apertura normal de la app.
#
# RESTRICCIÓN DURA: None por defecto -- en el arranque normal de la app (sin
# sesión iniciada) el respaldo se audita con usuario NULL, nunca con una
# etiqueta de ejecución de terminal. El script es el ÚNICO que la fija, y
# solo mientras dura su propia llamada a `Conexion()` (mismo patrón de
# aislamiento por swap+try/finally que ya usa `_aplicar_migracion_en` para
# `ruta_base_datos`/`Conexion._instance`): jamás debe quedar puesta cuando la
# app abre el archivo por su cuenta.
USUARIO_RESPALDO_MIGRACION = None


class Conexion():
    _instance = None  # Variable de clase para almacenar una única instancia de la conexión
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:  # Si no hay una instancia, la crea
            cls._instance = super(Conexion, cls).__new__(cls)
            cls._instance.__init_connection()  # Llama a un nuevo método de inicialización
        return cls._instance  # Devuelve la única instancia existente
    
    def __init_connection(self):
        #print("Conexion               __init__ called")
        
        #print("Inicialización de la base de datos (Archivo: conection.py)")
        try:
            self.con = sqlite3.connect(ruta_base_datos(), check_same_thread=False)  # Evita errores de hilos
            aplicar_pragmas_conexion(self.con)
            self.createTable()
            self.crearTablasCambioFuente()
            self.crearTablaLinealidad()
            self.crearTablaAnalisis600()
            self.crearTablasCatphan()
            self.crearTablasAnuales() # Crear tablas para controles anuales del 600 e IX
            self.crearTablasHalcyon()  # Crear tablas para controles Halcyon (Anuales y Mensuales)
            self.crearTablasMLCs()

            # R1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): DosisService.crear_tabla()
            # (que asegura columnas como "energia"/"vigente" via ALTER TABLE)
            # antes solo se llamaba dentro de guardar_datos -- sobre una BD sin
            # migrar, cualquier lectura previa (p.ej. el chequeo de duplicado
            # F6b) reventaba con "no such column: energia" antes del primer
            # guardado (hallazgo H-C, terminal del físico 2026-07-23).
            # Import local: dosis_service importa este módulo a nivel de
            # módulo (`from data.ManejoDatos import conection as _conection`)
            # -- un import de nivel de módulo aquí sería circular.
            try:
                from services.dosis_service import DosisService
                DosisService.crear_tabla()
            except Exception as ex_dosis:
                print("Error asegurando esquema de calculadora_dosimetrica al arranque:", ex_dosis)

            self._asegurar_migraciones_ad_hoc()
            self._asegurar_catalogos_base()
            self._asegurar_roles_de_sistema()
            self._asegurar_activo_bloque_qc()
            # E10: DESPUÉS de _asegurar_activo_bloque_qc, para que la
            # recreación de tablas ya incluya las columnas `activo` de E7 y
            # solo haya UNA recreación. Y SIEMPRE ANTES de que exista
            # cualquier trigger (E8): recrear una tabla BORRA sus triggers
            # (comprobado empíricamente) -- si algún día esta migración
            # vuelve a activarse sobre una BD ya blindada, los triggers de
            # E8 deben recrearse después (por eso E8 también corre al
            # arranque, tras esta línea).
            self._asegurar_secuencias_sin_duplicados()
            self._asegurar_fk_on_delete_restrict()
            # EB2d (DA-57) YA NO CORRE AQUÍ ([[DA-69]], decisión del físico
            # 2026-08-25): `_asegurar_angulo_starshot_sin_unique_de_tabla`
            # RECONSTRUYE una tabla (crear temporal, copiar, DROP, renombrar)
            # y, a diferencia de E10, lo hace SIN respaldo previo. Que una
            # reconstrucción se dispare sola al abrir la app es justo lo que
            # el físico pidió acotar: las correcciones de estructura se
            # aplican UNA vez, desde la herramienta de migración, con
            # respaldo y reporte.
            #
            # Se movió SOLO esta, no las demás: E10 lleva desde el 29-07 con
            # su respaldo propio (F1) y `_asegurar_activo_bloque_qc` es
            # aditivo (`ALTER TABLE ADD COLUMN`, no puede perder una fila).
            # Mover lo que ya funciona era el riesgo mayor.
            #
            # La llama ahora `scripts/migrar_bd_a_estandar.py`, DESPUÉS de
            # este `Conexion()`. La restricción de orden que tenía aquí
            # ("antes de E8, porque recrear una tabla borra sus triggers")
            # NO aplica en el sitio nuevo: los 4 triggers de E8 viven en
            # `controles`/`TipoCalibracion`/`LinealidadBraquiterapia`/`users`
            # (`TABLAS_CON_TRIGGER_ANTI_DELETE`), y `angulo_starshot` no es
            # ninguna de ellas -- reconstruirla no borra ningún trigger.
            # Verificado antes de moverla, no supuesto.
            # E8: SIEMPRE después de E10 -- recrear una tabla borra sus
            # triggers, así que si E10 alguna vez recrea algo sobre una BD
            # ya blindada, los triggers deben reponerse justo después.
            self._asegurar_triggers_anti_delete()
            # U2 (PLAN_NUCLEO_04-08.md, Bloque U): al final -- es aditivo
            # (no recrea tablas, no le afecta el orden con E10/E8) y
            # depende de "controles.activo" (createTable, arriba) y de la
            # medición de U1 (duplicados_control), que se corre primero.
            self._asegurar_indice_unico_controles()

        except Exception as ex:
            traceback.print_exc()
            print("Error al conectar a la base de datos:", ex)

    # E8 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §14, alcance AJUSTADO en la
    # ejecución -- ver docstring de _asegurar_triggers_anti_delete): el plan
    # pedía un trigger por cada tabla de TABLAS_ANULABLES (27) + users. Al
    # implementarlo se descubrió un conflicto real, no anticipado por el
    # plan: `loadtablacomplex` (load.py) y `add_info` (load.py, reporte
    # diario) usan un mecanismo YA DECIDIDO de "reemplazar al guardar"
    # (DELETE FROM <tabla> WHERE ref=?/date=? seguido de INSERT) para las ~20
    # tablas hijas mensuales/anuales y las 4 diarias -- un trigger BEFORE
    # DELETE ahí habría bloqueado el guardado normal ("Subir"), no solo el
    # borrado. Verificado empíricamente antes de decidir el recorte.
    # Las 4 tablas de abajo SÍ se verificaron sin ningún DELETE físico
    # alcanzable (barrido completo del árbol de producción): son puro
    # "una fila por evento", nunca "reemplazar el conjunto al guardar".
    TABLAS_CON_TRIGGER_ANTI_DELETE = frozenset({
        "controles", "TipoCalibracion", "LinealidadBraquiterapia", "users",
    })

    def _asegurar_triggers_anti_delete(self):
        """E8 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §14): guardas
        estructurales -- un `TRIGGER BEFORE DELETE` para que la BASE DE
        DATOS misma rechace el borrado físico, sin importar qué haga la
        aplicación (una consulta SQL directa, o una ruta de código futura
        que se olvide de pasar por `anular_fila`).

        ALCANCE AJUSTADO respecto al plan original: `TABLAS_CON_TRIGGER_
        ANTI_DELETE` (4 tablas) en vez de las 27 de `TABLAS_ANULABLES` +
        users. El plan asumía que, tras E7, "todas las rutas de la app ya
        anulan en vez de borrar, así que no hay nada legítimo que
        bloquear" -- cierto para el botón "Eliminar", pero no contempló que
        ~20 tablas hijas (mensual/anual, vía `loadtablacomplex`) y las 4
        diarias (vía `add_info`, decisión H2.2 ya vigente) usan DELETE+
        INSERT como mecanismo normal de GUARDADO ("Subir"), no de borrado.
        Confirmado con una prueba directa: el mismo DELETE que `add_info`
        ejecuta al reemplazar el reporte de una fecha queda bloqueado por
        un trigger genérico. Ampliar la protección a esas tablas exigiría
        rediseñar ese mecanismo (UPDATE-or-insert en vez de recrear todo el
        conjunto), un cambio de mayor alcance y riesgo que esta tarea --
        quedan protegidas solo por E7 (sin ruta de borrado alcanzable),
        igual que antes de E8. Cierra igual los dos peligros más graves de
        §13.2: TipoCalibracion arrastrando en cascada ResultadosActividad
        (el borrado más destructivo posible), y la regla permanente de que
        los usuarios nunca se eliminan.

        No requiere recrear ninguna tabla (a diferencia de E10) -- es
        aditivo y reversible con `DROP TRIGGER`. Va DESPUÉS de E10 a
        propósito: recrear una tabla borra sus triggers (comprobado
        empíricamente), así que si E10 llegara a recrear algo sobre una BD
        ya blindada, este método repone la guarda justo después en el
        mismo arranque.

        `users` lleva un mensaje propio ("los usuarios nunca se eliminan")
        en vez de "use activo=0": la regla del proyecto es no borrar
        cuentas nunca, no anularlas -- `users.active` ya cumple otro papel
        (activar/desactivar el acceso), no es el mecanismo de anulación de
        `services/anulacion.py`.

        Idempotente (`CREATE TRIGGER IF NOT EXISTS`): correrla de nuevo no
        cambia nada.
        """
        try:
            cur = self.con.cursor()
            for tabla in sorted(self.TABLAS_CON_TRIGGER_ANTI_DELETE - {"users"}):
                mensaje = f"{tabla} no admite borrado fisico: use activo=0 (anular)"
                cur.execute(
                    f'CREATE TRIGGER IF NOT EXISTS "trg_no_borrar_{tabla}" '
                    f'BEFORE DELETE ON "{tabla}" '
                    f"BEGIN SELECT RAISE(ABORT, '{mensaje}'); END")
            cur.execute(
                'CREATE TRIGGER IF NOT EXISTS "trg_no_borrar_users" '
                'BEFORE DELETE ON "users" '
                "BEGIN SELECT RAISE(ABORT, "
                "'users no admite borrado fisico: los usuarios nunca se eliminan'); END")
            self.con.commit()
            cur.close()
        except Exception as ex:
            print("Error asegurando triggers anti-DELETE al arranque:", ex)

    def _asegurar_indice_unico_controles(self):
        """U2 (PLAN_NUCLEO_04-08.md, Bloque U, DP-06): índice UNIQUE
        PARCIAL sobre expresión que impide dos controles activos del mismo
        (equipo, control, mes/año) -- defensa en profundidad, no la primera
        línea: `create_control` (load.py) ya busca-o-crea por esa misma
        clave; el índice garantiza que ninguna ruta futura pueda saltárselo
        (mismo principio que E10/E8 respecto de `anular_fila`).

        Precedido SIEMPRE por U1 (`duplicados_control.duplicados_controles`):
        si hay duplicados, NO se crea el índice y se reporta ruidosamente --
        nunca se borra ni se corrige nada automáticamente, esa decisión es
        del físico. Regla dura de esta ronda: "evitar siempre borrar
        información antes de verificar".

        Parcial (`WHERE activo IS NULL OR activo = 1`, mismo criterio que
        el resto del proyecto desde E7): anular un control y crear otro del
        mismo mes sigue siendo legal -- el caso excepcional que el físico
        pidió no bloquear. La normalización de fecha
        (`CASE WHEN length(fecha)=10 THEN substr(fecha,4,7) ELSE fecha END`)
        es determinista porque `controles.fecha` solo tiene dos formatos
        reales (medido: "MM/yyyy" de 7 caracteres y "dd/MM/yyyy" de 10; no
        existe "d/MM/yyyy" en esta columna, a diferencia de `equipos`).

        Aditivo y reversible (`DROP INDEX`); no recrea ninguna tabla, así
        que no le afecta el orden con E10/E8 ni borra los triggers de E8
        (lección de E10: recrear SÍ borra triggers; crear un índice, no).

        Import local (mismo motivo que `_asegurar_activo_bloque_qc`):
        evita cualquier riesgo de import circular con el resto de
        `services/`.
        """
        try:
            from services.duplicados_control import duplicados_controles
            duplicados = duplicados_controles(self.con)
            if duplicados:
                print(
                    "ALERTA: no se creó el índice único de controles -- hay "
                    f"{len(duplicados)} grupo(s) duplicado(s) por (equipo, "
                    "control, mes/año) entre filas activas. Requiere "
                    "decisión del físico (services/duplicados_control.py, "
                    "o el reporte de scripts/migrar_bd_a_estandar.py):"
                )
                for grupo in duplicados:
                    print(f"  {grupo['equipo']} / {grupo['control']} / "
                          f"{grupo['mes']:02d}/{grupo['anio']}: "
                          f"ids {grupo['ids']}")
                return
            cur = self.con.cursor()
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_controles_unico_mes "
                "ON controles ("
                "    equipo,"
                "    control,"
                "    CASE WHEN length(fecha)=10 THEN substr(fecha,4,7) "
                "ELSE fecha END"
                ") WHERE activo IS NULL OR activo = 1"
            )
            self.con.commit()
            cur.close()
        except Exception as ex:
            print("Error asegurando el índice único de controles al arranque:", ex)

    def _asegurar_secuencias_sin_duplicados(self):
        """E10, hallazgo del ensayo sobre la BD real: `sqlite_sequence`
        traía filas DUPLICADAS para una misma tabla (users x4,
        TipoCalibracion x4, LinealidadBraquiterapia x4, equipos x4,
        HC_dosimetria_anual x2, ...) -- herencia de recreaciones antiguas y
        de la fusión de BD de 2026-07-03. `sqlite_sequence` no declara
        unicidad, y con duplicados SQLite puede leer el contador MENOR y
        reutilizar el id de una fila borrada físicamente en el pasado: un
        huérfano heredado que apunte a ese id "adoptaría" en silencio al
        registro nuevo. Se normaliza a UNA fila por tabla con el contador
        MÁXIMO (lo conservador: un salto de ids es inocuo; una reutilización
        no). Es metadato de infraestructura, no dato clínico -- ninguna fila
        de ninguna tabla de QC se toca.
        """
        try:
            cur = self.con.cursor()
            try:
                duplicadas = cur.execute(
                    "SELECT name, MAX(seq) FROM sqlite_sequence "
                    "GROUP BY name HAVING COUNT(*) > 1").fetchall()
            except sqlite3.OperationalError:
                cur.close()
                return  # la BD no tiene sqlite_sequence
            for nombre, seq_max in duplicadas:
                cur.execute("DELETE FROM sqlite_sequence WHERE name=?", (nombre,))
                cur.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                            (nombre, seq_max))
                print(f"E10: sqlite_sequence normalizada para {nombre} "
                      f"(duplicados -> seq={seq_max})")
            self.con.commit()
            cur.close()
        except Exception as ex:
            print("Error normalizando sqlite_sequence al arranque:", ex)

    def _respaldar_antes_de_recrear(self, pendientes):
        """F1 (PLAN_F_CIERRE_ESTANDAR_29-07.md): copia de seguridad ANTES de
        que `_asegurar_fk_on_delete_restrict` recree tablas. Devuelve True si
        es seguro proceder con la recreación, False si no.

        Por qué: E9 (respaldo) corre en `closeEvent`, al CERRAR; E10 (la
        recreación que sigue a esto) corre en `__init_connection`, al ABRIR.
        Verificado sobre la BD de producción real (2026-07-29): la primera
        vez que un build nuevo abre un archivo aún en CASCADE, recrea 59
        tablas antes de que exista ningún respaldo de esa sesión. Un disco
        que falla a mitad de esa recreación no necesita que nadie dispare un
        DELETE -- a diferencia del resto del plan (E7/E8), que protege
        contra acciones de usuario, este es el único paso que se dispara
        solo, sin que nadie lo pida, la primera vez que se abre una BD vieja.

        DELIBERADAMENTE fundido dentro de `_asegurar_fk_on_delete_restrict`
        (llamado con la MISMA lista de `pendientes` que esa función ya
        calculó, en vez de volver a detectarlas) en lugar de un método
        aparte con una bandera de instancia: una bandera que nadie lee no
        bloquea nada -- es el mismo defecto que E9 vino a corregir (la app
        anunciaba un respaldo que no hacía). Aquí no hay bandera: el propio
        `if not self._respaldar_antes_de_recrear(pendientes): return` es la
        única puerta hacia la recreación.

        Si el respaldo falla, la migración estructural NO se ejecuta --
        deliberadamente distinto de E9 (best-effort): no respaldar al cerrar
        no debe impedir cerrar la app, pero recrear 59 tablas sin una copia
        previa sí debe evitarse. La app sigue funcionando con el esquema
        viejo (como ya lo hace hoy) hasta el siguiente arranque. E8 no se ve
        afectado: sus triggers no dependen de que E10 se haya aplicado, y si
        E10 llega a aplicarse en un arranque posterior, E8 los repone justo
        después (mismo orden ya documentado en `__init_connection`).
        """
        try:
            print(f"F1: {len(pendientes)} tablas con borrado en cascada -- "
                  "respaldando antes de recrear el esquema en RESTRICT...")
            from services.respaldo import respaldar_bd, carpeta_respaldos
            checkpoint_wal(self.con)  # R2: el .db solo puede no tener los commits recientes
            carpeta = os.path.join(carpeta_respaldos(ruta_base_datos()), "pre_migracion")
            # max_copias por defecto (no 0): _rotar trata max_copias<=0 como
            # "borrar TODAS las existentes", lo que eliminaría de inmediato
            # la copia recién creada -- verificado antes de usarlo aquí.
            destino = respaldar_bd(usuario=USUARIO_RESPALDO_MIGRACION,
                                   motivo=MOTIVO_RESPALDO_MIGRACION_ESTRUCTURAL,
                                   ruta_origen=ruta_base_datos(),
                                   carpeta_destino=carpeta)
            if destino is None:
                print("F1: el respaldo previo a la migración estructural "
                      "FALLÓ -- la migración a ON DELETE RESTRICT se "
                      "posterga al próximo arranque (el esquema actual "
                      "sigue funcionando).")
                return False
            return True
        except Exception as ex:
            print("Error en el respaldo previo a la migración estructural:", ex)
            return False

    def _asegurar_fk_on_delete_restrict(self):
        """E10 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §18): migra toda FK
        con borrado en cascada a `ON DELETE RESTRICT`.

        Por qué: medido sobre la BD real, un solo DELETE en `controles` se
        llevaba 19 filas hijas de 5 tablas con un único statement. El
        soft-delete de C2/E7 evita que la APP lo dispare, pero era
        convención de aplicación; con RESTRICT es la BD misma la que
        rechaza el borrado de un padre con hijas, venga de donde venga.
        OJO (aviso del plan §18): RESTRICT NO da soft-delete -- no impide
        borrar un padre sin hijas ni borrar hijas directamente. Esa capa la
        dan E7 (anulación) y E8 (triggers). Son complementarias, ninguna
        sustituye a otra.

        SQLite no permite alterar una constraint: el procedimiento es el
        documentado por SQLite (recrear y copiar), tabla por tabla, en una
        transacción cada una, con foreign_keys=OFF durante la copia (los
        109 huérfanos heredados no deben bloquear la migración; el criterio
        es "no aumentan", no "son cero" -- directriz del físico).
        Idempotente: detecta por `PRAGMA foreign_key_list` y no hace nada
        si ya no queda ninguna FK en cascada. Alcance medido sobre la
        producción real: 59 tablas, 59 FK, 2158 filas, 0 índices propios.

        El texto de la declaración vieja se compone en dos partes a
        propósito: tests/test_e10_restrict.py exige que este archivo no la
        contenga escrita (tripwire para que ninguna tabla nueva la
        reintroduzca), y esta función es precisamente quien la elimina.

        F1 (PLAN_F_CIERRE_ESTANDAR_29-07.md): antes de recrear una sola
        tabla, `_respaldar_antes_de_recrear` deja una copia de la BD tal
        como estaba. Si el respaldo falla, esta función no recrea nada ese
        arranque -- se reintenta en el siguiente.
        """
        _CASCADA = "ON DELETE " + "CASCADE"
        try:
            cur = self.con.cursor()
            pendientes = _tablas_con_borrado_en_cascada(cur)
            if not pendientes:
                cur.close()
                return
            if not self._respaldar_antes_de_recrear(pendientes):
                cur.close()
                return
            print(f"E10: migrando {len(pendientes)} tablas a ON DELETE RESTRICT...")

            patron = re.compile(r"ON\s+DELETE\s+CASCADE", re.IGNORECASE)
            self.con.commit()
            aislamiento_previo = self.con.isolation_level
            # autocommit: BEGIN/COMMIT manuales por tabla, y PRAGMA
            # foreign_keys solo surte efecto fuera de una transacción.
            self.con.isolation_level = None
            try:
                cur.execute("PRAGMA foreign_keys=OFF")
                for nombre in pendientes:
                    sql = cur.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (nombre,)).fetchone()[0]
                    sql_restrict, n_cambios = patron.subn("ON DELETE RESTRICT", sql)
                    if n_cambios == 0:
                        raise Exception(
                            f"{nombre}: foreign_key_list reporta cascada pero el SQL "
                            "almacenado no la contiene -- no se migra a ciegas")
                    temporal = f"_e10_nueva_{nombre}"
                    sql_temporal = re.sub(
                        rf'CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?["\[]?{re.escape(nombre)}["\]]?',
                        f'CREATE TABLE "{temporal}"', sql_restrict,
                        count=1, flags=re.IGNORECASE)
                    indices = [r[0] for r in cur.execute(
                        "SELECT sql FROM sqlite_master WHERE type='index' "
                        "AND tbl_name=? AND sql IS NOT NULL", (nombre,)).fetchall()]
                    # Preservar el contador AUTOINCREMENT: DROP TABLE borra su
                    # fila de sqlite_sequence y el INSERT masivo la re-siembra
                    # solo hasta MAX(id) copiado -- si el contador previo iba
                    # más adelante (filas altas borradas físicamente en el
                    # pasado), un id se REUTILIZARÍA y los huérfanos heredados
                    # que apuntan a ese id "adoptarían" al registro nuevo.
                    # MAX(seq): sqlite_sequence no tiene restricción de
                    # unicidad y la producción real trae filas DUPLICADAS
                    # para una misma tabla (HC_dosimetria_anual: seq=1 y
                    # seq=3, herencia de una recreación antigua) -- leer la
                    # primera a secas tomaba el contador equivocado.
                    seq_previa = None
                    try:
                        fila_seq = cur.execute(
                            "SELECT MAX(seq) FROM sqlite_sequence WHERE name=?",
                            (nombre,)).fetchone()
                        seq_previa = fila_seq[0] if fila_seq else None
                    except sqlite3.OperationalError:
                        pass  # la BD no tiene sqlite_sequence
                    cur.execute("BEGIN")
                    try:
                        cur.execute(sql_temporal)
                        cur.execute(f'INSERT INTO "{temporal}" SELECT * FROM "{nombre}"')
                        cur.execute(f'DROP TABLE "{nombre}"')
                        cur.execute(f'ALTER TABLE "{temporal}" RENAME TO "{nombre}"')
                        for sql_indice in indices:
                            cur.execute(sql_indice)
                        if seq_previa is not None:
                            fila_seq = cur.execute(
                                "SELECT MAX(seq) FROM sqlite_sequence WHERE name=?",
                                (nombre,)).fetchone()
                            seq_final = max(seq_previa,
                                            fila_seq[0] if fila_seq and fila_seq[0] is not None else 0)
                            # normaliza también los duplicados heredados:
                            # queda UNA sola fila con el contador máximo.
                            cur.execute("DELETE FROM sqlite_sequence WHERE name=?", (nombre,))
                            cur.execute(
                                "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                                (nombre, seq_final))
                        cur.execute("COMMIT")
                    except Exception:
                        cur.execute("ROLLBACK")
                        raise
                cur.execute("PRAGMA foreign_keys=ON")
            finally:
                self.con.isolation_level = aislamiento_previo
            cur.close()
        except Exception as ex:
            try:
                self.con.execute("PRAGMA foreign_keys=ON")
            except Exception:
                pass
            print(f"Error migrando FK ({_CASCADA} -> RESTRICT) al arranque:", ex)

    def _asegurar_angulo_starshot_sin_unique_de_tabla(self):
        """EB2d (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2d, DA-57, 24-08):
        `angulo_starshot` traía un `UNIQUE(ref, spoke_index)` DE TABLA --
        no `partial` (a diferencia del índice que `crear_indices()` (CL1)
        crea sobre la misma clave, `WHERE activo IS NULL OR activo=1`).
        Esa constraint bloquea por completo el modelo de anular+insertar
        que `starshot_angles_insertion` (EB2d) pasó a usar: una fila
        ANULADA y una VIGENTE con el mismo (ref, spoke_index) la violan
        igual, aunque `activo` sea distinto -- reventaría con
        `IntegrityError` en el segundo análisis starshot de cualquier
        control. Medido: 0 filas en las 3 BD de referencia (la
        funcionalidad de starshot es reciente, DA-42) -- el rebuild es
        seguro sin importar cuántas filas traiga cualquier otra BD real.

        Mismo procedimiento que `_asegurar_fk_on_delete_restrict` (E10):
        recrear y copiar, preservando filas, índices y el contador de
        `sqlite_sequence`. Sin la parte de respaldo previo de E10 (F1):
        esto solo retira UNA constraint de UNA tabla, no cambia el
        comportamiento de `ON DELETE` de ninguna FK ya existente -- blast
        radius mucho menor que la migración masiva de 59 tablas que
        motivó ese respaldo.

        Idempotente: si la tabla no existe (BD nueva, ya sin la
        constraint desde este mismo cambio) o ya fue migrada, no hace
        nada.
        """
        try:
            cur = self.con.cursor()
            fila = cur.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                "AND name='angulo_starshot'").fetchone()
            if fila is None or fila[0] is None:
                cur.close()
                return {"estado": "no aplica -- la tabla no existe en esta BD"}
            sql_original = fila[0]
            patron = re.compile(r",\s*UNIQUE\s*\(\s*ref\s*,\s*spoke_index\s*\)",
                                 re.IGNORECASE)
            sql_sin_unique, n_cambios = patron.subn("", sql_original)
            if n_cambios == 0:
                cur.close()
                # ya migrada, o nunca tuvo la constraint
                return {"estado": "ya estaba sin el UNIQUE de tabla"}

            temporal = "_eb2d_nueva_angulo_starshot"
            sql_temporal = re.sub(
                r'CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?["\[]?angulo_starshot["\]]?',
                f'CREATE TABLE "{temporal}"', sql_sin_unique,
                count=1, flags=re.IGNORECASE)
            indices = [r[0] for r in cur.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND tbl_name='angulo_starshot' AND sql IS NOT NULL").fetchall()]
            seq_previa = None
            try:
                fila_seq = cur.execute(
                    "SELECT MAX(seq) FROM sqlite_sequence WHERE name='angulo_starshot'"
                ).fetchone()
                seq_previa = fila_seq[0] if fila_seq else None
            except sqlite3.OperationalError:
                pass  # la BD no tiene sqlite_sequence

            self.con.commit()
            aislamiento_previo = self.con.isolation_level
            self.con.isolation_level = None
            try:
                cur.execute("PRAGMA foreign_keys=OFF")
                cur.execute("BEGIN")
                try:
                    cur.execute(sql_temporal)
                    cur.execute(f'INSERT INTO "{temporal}" SELECT * FROM angulo_starshot')
                    cur.execute("DROP TABLE angulo_starshot")
                    cur.execute(f'ALTER TABLE "{temporal}" RENAME TO angulo_starshot')
                    for sql_indice in indices:
                        cur.execute(sql_indice)
                    if seq_previa is not None:
                        fila_seq = cur.execute(
                            "SELECT MAX(seq) FROM sqlite_sequence WHERE name='angulo_starshot'"
                        ).fetchone()
                        seq_final = max(
                            seq_previa,
                            fila_seq[0] if fila_seq and fila_seq[0] is not None else 0)
                        cur.execute(
                            "DELETE FROM sqlite_sequence WHERE name='angulo_starshot'")
                        cur.execute(
                            "INSERT INTO sqlite_sequence (name, seq) VALUES "
                            "('angulo_starshot', ?)", (seq_final,))
                    cur.execute("COMMIT")
                except Exception:
                    cur.execute("ROLLBACK")
                    raise
                cur.execute("PRAGMA foreign_keys=ON")
            finally:
                self.con.isolation_level = aislamiento_previo
            cur.close()
            print("EB2d: angulo_starshot migrada -- UNIQUE(ref, spoke_index) de "
                  "tabla retirado (el índice parcial de CL1 ya cubre lo mismo, "
                  "respetando 'activo').")
            return {"estado": "migrada -- UNIQUE(ref, spoke_index) de tabla retirado"}
        except Exception as ex:
            try:
                self.con.execute("PRAGMA foreign_keys=ON")
            except Exception:
                pass
            print("Error migrando angulo_starshot (EB2d):", ex)
            return {"estado": f"NO MIGRADA -- {ex}"}

    def _asegurar_activo_bloque_qc(self):
        """E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11): `activo INTEGER
        DEFAULT 1` en las tablas del inventario cerrado de anulación
        (services/anulacion.py::TABLAS_ANULABLES, menos `controles`, que ya
        la tiene desde C2). Con DEFAULT 1, SQLite hace que TODAS las filas
        existentes se comporten como activas sin ningún UPDATE -- migración
        de coste cero, no reescribe ni una fila.

        IV1b (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV1b): el `try/except` es
        POR TABLA, no alrededor de todo el bucle. Antes, si una tabla del
        inventario no existía en esa BD (`PRAGMA table_info` vacío ->
        `_asegurar_columna` intenta `ALTER TABLE` sobre una tabla inexistente
        -> `OperationalError`), la excepción abortaba el resto del bucle: TODAS
        las tablas alfabéticamente posteriores a la que faltaba se quedaban
        sin `activo`, en silencio. Detectado auditando IV1 con un subagente:
        `posicionamiento_reposicionamiento` (sin `CREATE TABLE` en este
        archivo) haría exactamente eso en cualquier BD nueva en cuanto
        `TABLAS_ANULABLES` se ampliara. Una tabla problemática ahora se
        reporta y se salta; el resto del bloque queda protegido igual.

        Import local (mismo motivo que DosisService.crear_tabla() arriba):
        `services.anulacion` importa `services.audit_minimo`, que importa
        este módulo -- un import de nivel de módulo aquí sería circular.
        """
        from services.anulacion import TABLAS_ANULABLES
        cur = self.con.cursor()
        for tabla in sorted(TABLAS_ANULABLES - {"controles"}):
            try:
                _asegurar_columna(cur, tabla, "activo", "INTEGER DEFAULT 1")
            except Exception as ex:
                print(f"Error asegurando 'activo' en '{tabla}' al arranque:", ex)
        self.con.commit()
        cur.close()

    def _asegurar_roles_de_sistema(self):
        """E6 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §10): modelo de roles
        real en `users.rol_sistema` ('admin' / 'jefe' / 'fisico').

        Columna NUEVA en vez de migrar `role` en sitio -- decisión de
        implementación verificada contra los consumidores reales: `role` es
        el CARGO MOSTRADO ('Físico Médico') y lo imprimen 5 reportes PDF
        clínicos en el bloque de firma (`SELECT firma, role FROM users` en
        reportes_mensuales/reportes/braquiterapia/imagenes) y lo compara
        literal la recuperación de contraseña (`get_user`, recover_page).
        Reescribirlo habría cambiado el texto de los PDF a 'fisico' y roto
        la recuperación para todos los físicos. `rol_sistema` es el rol de
        PERMISOS (lo lee services/permisos.py); `role` queda intacto.

        Idempotente y conservador: solo se puebla donde está NULL/vacío --
        una asignación manual posterior (p.ej. otra física asciende a jefe)
        nunca se pisa. Mapeo inicial: admin->'admin', lamaya->'jefe'
        (decisión del físico, C3), resto->'fisico'.
        """
        try:
            cur = self.con.cursor()
            _asegurar_columna(cur, "users", "rol_sistema", "TEXT")
            cur.execute(
                "UPDATE users SET rol_sistema='admin' "
                "WHERE lower(user)='admin' AND (rol_sistema IS NULL OR rol_sistema='')")
            cur.execute(
                "UPDATE users SET rol_sistema='jefe' "
                "WHERE lower(user)='lamaya' AND (rol_sistema IS NULL OR rol_sistema='')")
            cur.execute(
                "UPDATE users SET rol_sistema='fisico' "
                "WHERE rol_sistema IS NULL OR rol_sistema=''")
            self.con.commit()
            cur.close()
        except Exception as ex:
            print("Error asegurando roles de sistema al arranque:", ex)

    def _asegurar_catalogos_base(self):
        """INSERT-audit (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8,
        prerrequisito de W2): `tipos_prueba`, `materiales_ct`,
        `regiones_uniformidad` y `energias` nunca se sembraban desde ningún
        punto del código -- solo se CREABAN vacíos (`CREATE TABLE IF NOT
        EXISTS`). El código que escribe en tablas con FK hacia ellos usa ids
        LITERALES fijos en Python que asumen que esas filas ya existen
        (`mapeo_tipos`/`mapeo_materiales`/`mapeo_regiones` en catphan_db.py,
        `energia_ids`/`id_energia=0` en ix_anual.py/halcyon_*.py) -- la BD de
        producción real SÍ las tiene (probablemente insertadas a mano en
        algún momento), pero una BD nueva o traída de otra sesión queda con
        estos catálogos VACÍOS. Hoy es inofensivo (FK apagado, H-F); en
        cuanto se active `PRAGMA foreign_keys=ON` (W2), CUALQUIER guardado
        de CT/Halcyon/tablas anuales de iX en una BD así fallaría de
        inmediato. `INSERT OR IGNORE`: aditivo, nunca sobreescribe una fila
        ya sembrada (aunque alguien la haya editado a mano después). Valores
        verificados contra `AUNA_2026_2/BaseDatosQA.db` real -- se replica
        exactamente lo que ya está desplegado, no se inventa nada nuevo.
        """
        try:
            cur = self.con.cursor()
            cur.executemany(
                "INSERT OR IGNORE INTO tipos_prueba (id_tipo, nombre_prueba, descripcion) "
                "VALUES (?, ?, ?)",
                [
                    (1, "ESPESOR_CORTE", "Medición del espesor de corte"),
                    (2, "TAMAÑO_PIXEL", "Medición del tamaño de pixel"),
                    (3, "RESOLUCION_CONTRASTE", "Resolución de contraste"),
                    (4, "RESOLUCION_ESPACIAL", "Resolución espacial"),
                    (5, "VALORES_CT", "Valores del número CT"),
                    (6, "LINEALIDAD_CT", "Linealidad del número CT y escala de contraste"),
                    (7, "UNIFORMIDAD_RUIDO", "Uniformidad y ruido"),
                ]
            )
            cur.executemany(
                "INSERT OR IGNORE INTO materiales_ct "
                "(id_material, nombre_material, rango_referencia_min, rango_referencia_max) "
                "VALUES (?, ?, ?, ?)",
                [
                    (1, "Aire", -1000.0, -970.0),
                    (2, "PMP", -200.0, -180.0),
                    (3, "LDPE", -120.0, -90.0),
                    (4, "Poliestireno", -65.0, -25.0),
                    (5, "Acrilico", 110.0, 140.0),
                    (6, "Delrin", 340.0, 380.0),
                    (7, "Teflon", 940.0, 1000.0),
                ]
            )
            cur.executemany(
                "INSERT OR IGNORE INTO regiones_uniformidad "
                "(id_region, nombre_region, angulo) VALUES (?, ?, ?)",
                [
                    (1, "Centro", 0),
                    (2, "Superior", 270),
                    (3, "Derecha", 0),
                    (4, "Inferior", 90),
                    (5, "Izquierda", 180),
                ]
            )
            cur.executemany(
                "INSERT OR IGNORE INTO energias (id, energia) VALUES (?, ?)",
                [
                    (0, "6 MV"), (1, "15 MV"), (2, "6 MeV"),
                    (3, "9 MeV"), (4, "12 MeV"), (5, "15 MeV"),
                ]
            )
            self.con.commit()
            cur.close()
        except Exception as ex:
            print("Error asegurando catálogos base al arranque:", ex)

    def _asegurar_migraciones_ad_hoc(self):
        """R3 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): cierra el resto
        de la deuda de ALTER TABLE ad-hoc que quedaba FUERA del arranque --
        mismo patrón de riesgo que H-C/R1 (columna faltante que revienta una
        lectura antes de que el único punto que la agrega llegue a ejecutarse
        alguna vez), pero para otras tablas: `pruebas.mes_control`/`.equipo`
        (antes solo se agregaban dentro de las funciones de listado anual/CT,
        nunca al arranque), `CondicionesMedicion.observaciones` (antes solo
        dentro de `observaciones_db` de braquiterapia). `equipos.imagen_certificado`/
        `.h_cal` y `dosimetriaMen.energia` YA están en el CREATE TABLE actual
        (cubren BD nuevas) pero el ALTER histórico que las agregó a una BD ya
        desplegada quedó comentado/inerte en el código -- para una BD
        genuinamente antigua (anterior a que esas columnas existieran) hacía
        falta repetirlo aquí. Puramente aditivo e idempotente (mismo
        `_asegurar_columna`); no toca ninguna fila existente.
        """
        try:
            cur = self.con.cursor()
            _asegurar_columna(cur, "pruebas", "mes_control", "TEXT")
            _asegurar_columna(cur, "pruebas", "equipo", "TEXT")
            # MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1): descubierto al
            # ejecutar MI1 sobre una BD anterior al módulo TAC/Catphan --
            # sin `id_tipo`, el índice UNIQUE de CL1 sobre `pruebas`
            # (clave `id_sesion, id_tipo`) no puede crearse
            # ("faltan columnas de la clave"), y antes de MI1 ese hueco
            # quedaba enmascarado porque `pruebas` se saltaba entera por
            # falta de `activo`. Mismo patrón que `mes_control`/`equipo`
            # arriba -- una columna añadida en una fase posterior del
            # proyecto que nunca se sumó al arranque para BD ya desplegadas.
            _asegurar_columna(cur, "pruebas", "id_tipo", "INTEGER")
            _asegurar_columna(cur, "CondicionesMedicion", "observaciones", "TEXT")
            _asegurar_columna(cur, "equipos", "imagen_certificado", "BLOB")
            _asegurar_columna(cur, "equipos", "h_cal", "REAL")
            _asegurar_columna(cur, "dosimetriaMen", "energia", "TEXT")
            # I4: repara las BD nacidas del DDL equivocado de
            # HC_dosimetria_anual (val_teo_discrepancia en vez de
            # val_teo_dosis/val_teo_calidad, ver el CREATE TABLE) -- sin
            # estas columnas, el "Subir" de la dosimetría anual del Halcyon
            # fallaría en una BD fresca al escribir val_teo_calidad.
            _asegurar_columna(cur, "HC_dosimetria_anual", "val_teo_dosis", "REAL")
            _asegurar_columna(cur, "HC_dosimetria_anual", "val_teo_calidad", "REAL")
            # F9 (PLAN_F_CIERRE_ESTANDAR_29-07.md §9 punto 7): puntero de
            # trazabilidad hacia el catálogo de equipos -- mismo patrón que
            # `calculadora_dosimetrica.equipo_id` desde B3. Sin FK declarada
            # a propósito (el catálogo conserva filas históricas; el id es
            # un puntero, la copia de datos sigue siendo la fuente para
            # reproducir el control). Las 55 filas históricas quedan con
            # `equipo_id = NULL` -- no se rellenan retroactivamente (46 de
            # 55 no son determinables sin ambigüedad, ver §8.7 del plan).
            _asegurar_columna(cur, "equipos_medicion", "equipo_id", "INTEGER")
            # MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1, DA-45):
            # `angulos_entre_lineas_starshot` no tenía con qué distinguir
            # una fila de otra -- sus dos columnas de datos son una MEDIDA
            # (`error_separacion`, cambia con cada corrección) y una
            # constante derivada (`separacion_ideal`, igual para todas las
            # filas de un control). El ordinal `par_index` es la misma
            # convención que ya usan sus hermanas (`angulo_starshot.spoke_index`,
            # `uniformidad_angular_starshot.gap_index`). Se añade sobre una
            # tabla vacía en las 3 BD de referencia -- sin retrollenado.
            _asegurar_columna(cur, "angulos_entre_lineas_starshot", "par_index", "INTEGER")
            self.con.commit()
            cur.close()
        except Exception as ex:
            print("Error asegurando migraciones ad-hoc al arranque:", ex)
            
    # A6.0 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.5): fetchone(sql, params) se
    # borró -- cero llamadores en producción. Recibía el SQL por parámetro,
    # así que era invisible para el detector estático de A6.1 (cualquier
    # escritura que pasara por aquí no se habría podido auditar ni vigilar).

    def createTable(self):
        sql_create_table1 = """
        CREATE TABLE IF NOT EXISTS users (
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT UNIQUE,
            password TEXT,
            fullname TEXT UNIQUE,
            active INTEGER,
            idreal INTEGER,
            role TEXT,
            firma BLOB,
            rol_sistema TEXT
        )
        """
        # Control diario del 600
        sql_create_table2 = """
        CREATE TABLE IF NOT EXISTS aceleradorlineal_600 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id TEXT,
            luces_consola INTEGER,
            luces_puerta INTEGER,
            luces_irradiacion INTEGER,
            sistema_visualizacion INTEGER,
            sistema_anticolision INTEGER,
            interruptor_radiacion_puerta INTEGER,
            interruptor_radiacion_panel INTEGER,
            interrupcion_um INTEGER,
            verificacion_monitoras INTEGER,
            movimiento_brazo INTEGER,
            movimiento_colimador INTEGER,
            movimientos_camilla INTEGER,
            laseres INTEGER,
            telemetro INTEGER,
            tamano_campo INTEGER,
            centrado_reticulo INTEGER,
            dosis_referencia INTEGER,
            observaciones TEXT,
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE RESTRICT ON UPDATE CASCADE
        )  
        """
        # Control diario del ix
        sql_create_table3 = """
        CREATE TABLE IF NOT EXISTS aceleradorlineal_ix (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id TEXT,
            luces_consola INTEGER,
            luces_puerta INTEGER,
            luces_irradiacion INTEGER,
            sistema_visualizacion INTEGER,
            sistema_anticolision INTEGER,
            interruptor_radiacion_puerta INTEGER,
            interruptor_radiacion_panel INTEGER,
            interrupcion_um INTEGER,
            verificacion_monitoras INTEGER,
            movimiento_brazo INTEGER,
            movimiento_colimador INTEGER,
            movimientos_camilla INTEGER,
            laseres INTEGER,
            telemetro INTEGER,
            tamano_campo INTEGER,
            centrado_reticulo INTEGER,
            tol_fot_6mv INTEGER,
            tol_fot_15mv INTEGER,
            tol_ele_6mev INTEGER,
            tol_ele_9mev INTEGER,
            tol_ele_12mev INTEGER,
            tol_ele_15mev INTEGER,
            observaciones TEXT,
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE RESTRICT ON UPDATE CASCADE
        )  
        """
        # Control diario de braqui
        sql_create_table4 = """
        CREATE TABLE IF NOT EXISTS braqui (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id TEXT,
            int_con_box INTEGER,
            emerg_con INTEGER,
            blq_puerta INTEGER,
            pos_fuente INTEGER,
            res_fuente INTEGER,
            key_fuente INTEGER,
            mon_area INTEGER,
            lum_puerta INTEGER,
            tub_guia INTEGER,
            visual_sys INTEGER,
            intercom INTEGER,
            mon_rad_port INTEGER,
            tol_rep_act_ci INTEGER,
            tol_exp_act INTEGER,
            tol_cyc_dummy INTEGER,
            tol_cyc_rad INTEGER,
            observaciones TEXT,
            pelicula BLOB,
            distancias TEXT NULL,
            promedio REAL NULL,
            desviacion REAL NULL,
            desplazamientos TEXT NULL,
            promedio_des REAL NULL,
            desviacion_des REAL NULL,
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
        # Control del halcyon
        sql_create_table5 = """
        CREATE TABLE IF NOT EXISTS halcyon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            user_id TEXT,
            IsoCenterSize_name2 INTEGER,
            IsoCenterMVOffset INTEGER,
            IsoCenterKVOffset INTEGER, 
            BeamOutputChange INTEGER,
            BeamUniformityChange INTEGER,
            BeamMu1GainChange INTEGER,
            BeamMu2GainChange INTEGER,
            GantryAbsolute INTEGER,
            GantryRelative INTEGER,
            CouchLat INTEGER,
            CouchLng INTEGER,
            CouchVrt INTEGER,
            CouchLatLong INTEGER,
            CouchLngLong INTEGER,
            CouchVrtLong INTEGER,
            VirtualToIsoLat INTEGER,
            VirtualToIsoLng INTEGER,
            VirtualToIsoVrt INTEGER,
            MVImagerCalibrationGain INTEGER,
            MVImagerCalibrationUniformity INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE RESTRICT ON UPDATE CASCADE
        )  
        """
        # Tabla de equipos, las unidades están: 
        #       Factores de Calibración cámara de inización: 1x10^9 (Gy/C) 
        #       Factores de Calibración cámara de pozo: 1x10^1 (Gy·m²/h·A) 
        #       Temperatura de calibración: °C
        #       Presión de calibración: kPa
        #       Humedad de calibración: %
        sql_create_table6 = """
        CREATE TABLE IF NOT EXISTS equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equip_type TEXT,
            model TEXT,
            serie TEXT,
            calibr_fact INTEGER,
            calibr_fact2 INTEGER,
            fecha_calibr INTEGER,
            fabricante TEXT,
            t_cal REAL,
            p_cal REAL,
            h_cal REAL,
            v1 TEXT,
            vigente REAL,
            activo REAL,
            imagen_certificado BLOB
        )"""
        #sql_alter_table = """
        #ALTER TABLE equipos ADD COLUMN imagen_cetificado BLOB;
        #"""
        # Alterar tabla (solo si no existe la columna)
        #sql_alter_table = """
        #ALTER TABLE equipos ADD COLUMN h_cal TEXT;
        #"""
        #-----------------------------------------------------------------------------------------------
        # Información general del control (equipo, fecha, usuario)        
        sql_create_tableMENSUAL = """
        CREATE TABLE IF NOT EXISTS controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo TEXT,
            control TEXT,
            fecha TEXT,
            user_id TEXT,
            user_id_f2 TEXT,
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (user_id_f2) REFERENCES users(fullname) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
        # Tabla de datos de los indicadores de brazos
        sql_create_table7 = """
        CREATE TABLE IF NOT EXISTS indicadores_brazo (
            ref INTEGER,
            nivel TEXT,
            indicador_luminoso_consola TEXT,
            indicador_luminoso_equipo TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )  
        """
        # Tabla de datos de los indicadores del colimador
        sql_create_table8 = """
        CREATE TABLE IF NOT EXISTS indicadores_angulares_colimador (
            ref INTEGER,
            nivel TEXT,
            indicador_luminoso_consola TEXT,
            indicador_luminoso_equipo TEXT, 
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )  
        """
        # Tabla de tamaños de campo
        sql_create_table9 = """
        CREATE TABLE IF NOT EXISTS tamano_campo (
            ref INTEGER,
            campo_nominal TEXT,
            ie_largoy1 TEXT,
            ie_largoy2 TEXT,
            ie_anchox1 TEXT,
            ie_anchox2 TEXT,
            ic_largoy1 TEXT,
            ic_largoy2 TEXT,
            ic_anchox1 TEXT,
            ic_anchox2 TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )  
        """
        # Tabla de datos del funcionamiento mecánico del dispositivo
        sql_create_table10 = """
        CREATE TABLE IF NOT EXISTS preguntas (
            ref INTEGER,
            iso_mec,
            reticulo_cent,
            bordes_coin,
            camilla_vert_rango,
            camilla_vert_desp,
            camilla_iso_desp,
            telem_rango,
            telem_desp,
            camp_luz_desp,
            puntero_telem_diff,
            laser_techo,
            laser_lateral27,
            laser_lateral9,
            observaciones,
            imagen BLOB,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )  """

        # Tabla de equipos que se usuan en el control
        sql_create_table11 = """
        CREATE TABLE IF NOT EXISTS equipos_medicion (
            ref INTEGER,
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_camara TEXT,
            equip_type TEXT,
            model TEXT,
            serie TEXT,
            calibr_fact INTEGER,
            fecha_calibr INTEGER,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )  
        """
        # Tabla de datos relacionados con la dosis.
        # H2.7: el DDL decía `val_teo_discrepancia`, pero la BD de PRODUCCIÓN
        # tiene `val_teo_dosis` + `val_teo_calidad` -- toda BD fresca (tests,
        # instalación nueva) nacía con un esquema divergente del real. Se
        # alinea con producción (CREATE IF NOT EXISTS: no toca BDs existentes).
        sql_create_table12 = """
        CREATE TABLE IF NOT EXISTS dosimetriaMen (
            ref INTEGER,
            val_teo_dosis REAL,
            val_teo_calidad REAL,
            dosis_ref_cgy_um INTEGER,
            discrepancia_dosis INTEGER,
            tolerancia_dosis INTEGER,
            calidad_pdd20_10 INTEGER,
            discrepancia_calidad INTEGER,
            tolerancia_calidad INTEGER,
            simetria_inplane INTEGER,
            simetria_crossplane INTEGER,
            tolerancia_simetria INTEGER,
            planicidad_inplane INTEGER,
            planicidad_crossplane INTEGER,
            tolerancia_planicidad INTEGER,
            observaciones_dosi TEXT,
            energia TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
        # Alterar tabla (solo si no existe la columna)
        #sql_alter_table = """ALTER TABLE dosimetriaMen ADD COLUMN energia TEXT;"""

        sql_create_table13 = """CREATE TABLE IF NOT EXISTS control_cunas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            angulo INTEGER NOT NULL,
            in_val INTEGER CHECK(in_val IN (0,1)),
            out_val INTEGER CHECK(out_val IN (0,1)),
            right_val INTEGER CHECK(right_val IN (0,1)),
            left_val INTEGER CHECK(left_val IN (0,1)),
            observaciones TEXT, 
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )"""
        
        sql_create_table14 = """CREATE TABLE IF NOT EXISTS control_conos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,         -- referencia o identificador del equipo/paciente
            medida TEXT NOT NULL,      -- por ejemplo "6x6", "10x10", etc.
            valor INTEGER NOT NULL,     -- 1 = funciona, 0 = no funciona
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )"""

        # H2.4 (auditoría 2026-07-14): audit trail mínimo -- quién/qué/cuándo
        # en los puntos de guardado. Antes de esto, services/auditorias.py y
        # decoradores_audit.py existían pero 100% comentados; esta tabla NUNCA
        # se creaba. Ver services/audit_minimo.py (helper único, best-effort).
        sql_create_table15 = """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            usuario TEXT,
            accion TEXT NOT NULL,
            tabla TEXT,
            ref TEXT,
            detalle TEXT
        )"""

        cur = self.con.cursor()
        cur.execute(sql_create_table1)
        cur.execute(sql_create_table2)
        cur.execute(sql_create_table3)
        cur.execute(sql_create_table4)
        cur.execute(sql_create_table5)
        #cur.execute(sql_alter_table)  # Se ejecuta una sola vez para agregar alguna columna a la tabla equipos
        cur.execute(sql_create_table6)
        cur.execute(sql_create_tableMENSUAL)
        cur.execute(sql_create_table7)
        cur.execute(sql_create_table8)
        cur.execute(sql_create_table9)
        cur.execute(sql_create_table10)
        cur.execute(sql_create_table11)
        cur.execute(sql_create_table12)
        cur.execute(sql_create_table13)
        cur.execute(sql_create_table14)
        cur.execute(sql_create_table15)

        # C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md / PLAN_AUDITORIA_DOS_EJES
        # §7 P4): "controles" es la raíz de la jerarquía mensual/anual/CT --
        # migración idempotente (mismo patrón que
        # DosisService._asegurar_columna), corre en cada arranque, no toca
        # filas existentes salvo darles el DEFAULT (activas).
        _asegurar_columna(cur, "controles", "activo", "INTEGER DEFAULT 1")

        cur.close()
        self.createAdmin()

    # RETIRADA el 2026-08-25 ([[DA-68]], decisión del físico): aquí vivía
    # `eliminar_tablas_cambio_fuente()`, que hacía `DROP TABLE IF EXISTS`
    # sobre las 6 tablas de braquiterapia (`TipoCalibracion` y sus 5 hijas,
    # incluida `ResultadosActividad`) SIN NINGUNA GUARDA: no miraba si
    # tenían datos, no confirmaba, no auditaba, no respaldaba. Era el
    # borrado más destructivo que existía en el código -- más que el DELETE
    # en cascada que E7/E8/E10 blindaron, porque se llevaba el esquema
    # entero.
    #
    # Nunca estuvo conectada (su única llamada estaba comentada en
    # `__init_connection`, y `git log -S` la encuentra ya comentada en el
    # commit inicial `408090b`), pero nada impedía que alguien
    # descomentara esa línea: habría destruido braquiterapia completa en el
    # siguiente arranque. Se retira en vez de dejarla vigilada por un
    # tripwire -- lo que no existe no se puede reconectar por descuido.
    #
    # Hallada al responder una pregunta del físico sobre qué borra
    # automáticamente la aplicación (DP-44).

    def crearTablasCambioFuente(self):
        tablas_sql = [
            """
            CREATE TABLE IF NOT EXISTS TipoCalibracion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                fecha TEXT,
                tipo REAL,
                serie TEXT,
                certificado REAL,
                fecha_cer TEXT,
                intensidad REAL,
                conversion REAL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS SistemaMedicion (
                ref INTEGER,
                user TEXT,
                fecha TEXT,
                modelo TEXT,
                serie_cp TEXT,
                calibracion REAL,
                modelo_elec TEXT,
                serie_ele TEXT,
                electrometro REAL,
                t0 REAL,
                p0 REAL,
                h0 REAL,
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE RESTRICT ON UPDATE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS CondicionesMedicion (
                ref INTEGER,
                user TEXT,
                fecha TEXT,
                t REAL,
                p REAL,
                h REAL,
                desplazamiento_ini REAL,
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE RESTRICT ON UPDATE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS MaximosCamaras (
                ref INTEGER,
                user TEXT,
                fecha TEXT,
                posicion TEXT,
                medida1 TEXT,
                medida2 TEXT,
                promedio TEXT,
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE RESTRICT ON UPDATE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS LecturasMaximos (
                ref INTEGER,
                user TEXT,
                fecha TEXT,
                voltaje TEXT,
                V_300 TEXT,
                V_150 TEXT,
                Vn_300 TEXT,
                promediosV TEXT,
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE RESTRICT ON UPDATE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ResultadosActividad (
                ref INTEGER,
                user TEXT,
                fecha TEXT,
                Ks REAL,
                Kp REAL,
                Ktp REAL,
                actividad_monitor REAL,
                actividad_calculada REAL,
                actividad_decaimiento REAL,
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE RESTRICT ON UPDATE CASCADE
            )
            """
        ]
        cursor = self.con.cursor()
        for tabla in tablas_sql:
            cursor.execute(tabla)
        self.con.commit()

    def crearTablaLinealidad(self):
        tabla = """
            CREATE TABLE IF NOT EXISTS LinealidadBraquiterapia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                fecha TEXT,
                modelo TEXT,
                serie_cp TEXT,
                calibracion REAL,
                modelo_elec TEXT,
                serie_ele TEXT,
                electrometro REAL,
                q_est REAL,
                t_integrado REAL,
                i_est REAL,
                reproducibilidad REAL,
                exactitud REAL,
                tiempo_transito REAL,
                repro_m1 REAL,
                repro_m2 REAL,
                repro_m3 REAL,
                repro_m4 REAL,
                repro_m5 REAL,
                repro_prom REAL,
                lin_tp_0 REAL, lin_q1_0 REAL, lin_q2_0 REAL, lin_qprom_0 REAL, lin_te_0 REAL,
                lin_tp_1 REAL, lin_q1_1 REAL, lin_q2_1 REAL, lin_qprom_1 REAL, lin_te_1 REAL,
                lin_tp_2 REAL, lin_q1_2 REAL, lin_q2_2 REAL, lin_qprom_2 REAL, lin_te_2 REAL,
                lin_tp_3 REAL, lin_q1_3 REAL, lin_q2_3 REAL, lin_qprom_3 REAL, lin_te_3 REAL,
                lin_tp_4 REAL, lin_q1_4 REAL, lin_q2_4 REAL, lin_qprom_4 REAL, lin_te_4 REAL,
                lin_tp_5 REAL, lin_q1_5 REAL, lin_q2_5 REAL, lin_qprom_5 REAL, lin_te_5 REAL,
                lin_tp_6 REAL, lin_q1_6 REAL, lin_q2_6 REAL, lin_qprom_6 REAL, lin_te_6 REAL,
                lin_tp_7 REAL, lin_q1_7 REAL, lin_q2_7 REAL, lin_qprom_7 REAL, lin_te_7 REAL,
                lin_tp_8 REAL, lin_q1_8 REAL, lin_q2_8 REAL, lin_qprom_8 REAL, lin_te_8 REAL,
                lin_tp_9 REAL, lin_q1_9 REAL, lin_q2_9 REAL, lin_qprom_9 REAL, lin_te_9 REAL
            )
            """
        cursor = self.con.cursor()
        cursor.execute(tabla)
        self.con.commit()

    def crearTablaAnalisis600(self):
        resultados_franja = """
            CREATE TABLE IF NOT EXISTS analisis_placa_franjas (
            ref INTEGER,                  
            franja TEXT NOT NULL,          
            ancho_media_h REAL,
            ancho_media_v REAL,
            penumbra_izq_h REAL,
            penumbra_izq_v REAL,
            penumbra_der_h REAL,
            penumbra_der_v REAL,
            diferencia_arriba_izq REAL,
            diferencia_arriba_der REAL,
            diferencia_abajo_izq REAL,
            diferencia_abajo_der REAL,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        );"""

        verificaciones = """
        CREATE TABLE IF NOT EXISTS analisis_placa_verificaciones (
            ref INTEGER,
            tipo TEXT NOT NULL,
            angulo1 REAL,
            angulo2 REAL,
            angulo3 REAL,
            angulo4 REAL,
            lado_arriba REAL,
            lado_abajo REAL,
            lado_izquierda REAL,
            lado_derecha REAL,
            desv_vert_izq REAL,
            desv_vert_der REAL,
            desv_horiz_arriba REAL,
            desv_horiz_abajo REAL,
            ortogonal INTEGER,
            simetrico INTEGER,
            alineado_horizontal INTEGER,
            alineado_vertical INTEGER,
            torcido INTEGER,
            FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE
            );"""

        correcciones = """
        CREATE TABLE IF NOT EXISTS analisis_placa_correcciones (
            ref INTEGER,
            vertice TEXT NOT NULL,
            delta_x REAL,
            delta_y REAL,
            diferencia_arriba REAL,
            diferencia_abajo REAL,
            diferencia_izquierda REAL,
            diferencia_derecha REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE
        );

        """
        cursor = self.con.cursor()
        cursor.execute(resultados_franja)
        cursor.execute(verificaciones)
        cursor.execute(correcciones)
        self.con.commit()

    def crearTablasCatphan(self):
        # Tabla de tipos de prueba (catálogo)
        tipos_prueba = """
        CREATE TABLE IF NOT EXISTS tipos_prueba (
            id_tipo INTEGER PRIMARY KEY,
            nombre_prueba VARCHAR(100) NOT NULL UNIQUE,
            descripcion TEXT,
            activo BOOLEAN DEFAULT 1
        );"""

        # Tabla principal de pruebas individuales
        pruebas = """   
        CREATE TABLE IF NOT EXISTS pruebas (
            id_prueba INTEGER PRIMARY KEY AUTOINCREMENT,    -- Identificador único de cada prueba
            id_sesion INTEGER NOT NULL,                     -- Referencia a la sesión de prueba
            id_tipo INTEGER NOT NULL,                       -- Referencia al tipo de prueba
            kv INTEGER NOT NULL,
            ma INTEGER NOT NULL,
            espesor_corte REAL NOT NULL,
            imagen_path BLOB,                               -- Imagen asociada a la prueba
            imagen_resultado BLOB,                          -- Imagen con resultados (BLOB)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Fecha y hora de creación

            FOREIGN KEY (id_sesion) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_tipo) REFERENCES tipos_prueba(id_tipo)
        );"""

        # Tabla específica para ESPESOR DE CORTE
        espesor_corte = """
        CREATE TABLE IF NOT EXISTS espesor_corte (
            id_prueba INTEGER PRIMARY KEY,                  -- Referencia a la prueba en la tabla principal
            espesor_promedio_mm REAL NOT NULL,              -- Espesor promedio medido en mm
            espesor_teorico_mm REAL NOT NULL,               -- Espesor teórico en mm    
            diferencia_mm REAL NOT NULL,                    -- Diferencia entre espesor medido y teórico en mm
            error_pct REAL NOT NULL,                        -- Error porcentual
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT ON UPDATE CASCADE
        );"""

        # Tabla específica para TAMAÑO DE PIXEL
        tamaño_pixel = """
                    CREATE TABLE IF NOT EXISTS tamaño_pixel (
                id_prueba INTEGER PRIMARY KEY,
                valor_teorico_dicom REAL,                   -- Valor del DICOM header
                X REAL,                                     -- Promedio xarr, xabajo
                Y REAL,                                     -- Promedio yizq, yder
                diferencia_x REAL,                          -- |promedio_x - teorico|
                diferencia_y REAL,                          -- |promedio_y - teorico|
                FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT
            );"""
        
        # Tabla para detalles por ROI en RESOLUCIÓN DE CONTRASTE
        rois_contraste = """
        CREATE TABLE IF NOT EXISTS resolucion_contraste_rois (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prueba INTEGER NOT NULL,
            diametro_mm INTEGER NOT NULL,               -- 15, 9, 8, 7, 6, 5
            centro_x INTEGER,
            centro_y INTEGER,
            roi_promedio_hu REAL,
            background_promedio_hu REAL,
            contraste_michelson REAL,                   -- Métrica principal
            cnr REAL,                                   -- Contrast-to-Noise Ratio
            snr REAL,                                   -- Signal-to-Noise Ratio  
            visibilidad_lim REAL,                       -- Criterio de Rose
            pasa_cnr BOOLEAN,
            pasa_visibilidad_lim BOOLEAN,               -- Criterio recomendado
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT
        );"""

        # Tabla específica para RESOLUCIÓN DE CONTRASTE
        resolucion_contraste = """
        CREATE TABLE IF NOT EXISTS resolucion_contraste (
            id_prueba INTEGER PRIMARY KEY,
            rois_visibles_cnr INTEGER,                  -- Cantidad que pasan CNR
            rois_visibles_visibilidad INTEGER,          -- Cantidad que pasan visibilidad
            total_rois INTEGER,                         -- Total evaluados (6)
            diametro_minimo_visible REAL,              -- Menor diámetro visible
            pasa_test_cnr BOOLEAN,                     -- ≥4 ROIs visibles con CNR
            pasa_test_visibilidad BOOLEAN,             -- ≥4 ROIs visibles con visibilidad
            metodo_recomendado VARCHAR(20),            -- 'visibilidad_lim'
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT
        );"""

        # Tabla específica para RESOLUCIÓN ESPACIAL
        resolucion_espacial = """
            CREATE TABLE IF NOT EXISTS resolucion_espacial (
                id_prueba INTEGER PRIMARY KEY,
                regiones_analizadas INTEGER,                -- Cantidad de regiones procesadas
                regiones_exitosas INTEGER,                  -- Regiones con status "OK"
                lp_mm_maximo REAL,                         -- Máximo lp/mm logrado
                ultima_region_exitosa VARCHAR(20),         -- Nombre de la última región OK
                gap_size_minimo_cm REAL,                   -- Gap size de la mejor resolución
                num_picos_totales INTEGER,                 -- Total de picos detectados
                mtf_10_pct REAL,                          -- lp/mm para MTF 10%
                mtf_20_pct REAL,                          -- lp/mm para MTF 20%
                mtf_50_pct REAL,                          -- lp/mm para MTF 50%
                FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT
            );"""

        resolucion_espacial_regiones = """
            CREATE TABLE IF NOT EXISTS resolucion_espacial_regiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_prueba INTEGER NOT NULL,
                region_nombre VARCHAR(20),                  -- "region 1", "region 2", etc.
                lp_mm REAL,                                -- 0.1, 0.2, 0.3, etc.
                peak_mean REAL,
                valley_mean REAL,
                gap_size_cm REAL,
                n_peaks_used INTEGER,
                n_valleys_used INTEGER,
                status VARCHAR(50),                        -- "OK", "Picos insuficientes", etc.
                FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT
            );"""
        
        # Catálogo de materiales para pruebas CT
        materiales_ct = """
        CREATE TABLE IF NOT EXISTS materiales_ct (
            id_material INTEGER PRIMARY KEY,                -- Identificador único del material
            nombre_material VARCHAR(50) NOT NULL UNIQUE,    -- Nombre descriptivo del material
            rango_referencia_min REAL,                      -- Valor mínimo del rango de referencia para el material
            rango_referencia_max REAL                       -- Valor máximo del rango de referencia para el material
        );"""

        # Tabla para VALORES DEL NÚMERO CT (detalle por material)
        valores_ct = """
        CREATE TABLE IF NOT EXISTS valores_ct (
            id INTEGER PRIMARY KEY AUTOINCREMENT,          -- Identificador único de la prueba valor CT
            id_prueba INTEGER NOT NULL,                    -- Referencia a la prueba en la tabla principal
            id_material INTEGER NOT NULL,                  -- Referencia al material en la tabla de materiales
            promedio_hu REAL NOT NULL,                     -- Valor promedio medido en Hounsfield Units (HU)
            error_absoluto REAL NOT NULL,                  -- Error absoluto entre el valor medido y el rango de referencia
            error_relativo REAL NOT NULL,                  -- Error relativo en porcentaje

            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT,
            FOREIGN KEY (id_material) REFERENCES materiales_ct(id_material),
            UNIQUE(id_prueba, id_material)
        );"""

        # Catálogo de regiones para uniformidad
        regiones_uniformidad = """
        CREATE TABLE IF NOT EXISTS regiones_uniformidad ( 
            id_region INTEGER PRIMARY KEY,                 -- Identificador único de la región
            nombre_region VARCHAR(20) NOT NULL UNIQUE,     -- Nombre descriptivo de la región (Centro, Superior, Derecha, Inferior, Izquierda)
            angulo INTEGER NOT NULL                        -- Ángulo asociado a la región (0, 90, 180, 270)
        );"""

        # Tabla para UNIFORMIDAD Y RUIDO (detalle por región)
        uniformidad_ruido = """
        CREATE TABLE IF NOT EXISTS uniformidad_ruido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,          -- Identificador único de la prueba de uniformidad y ruido
            id_prueba INTEGER NOT NULL,                    -- Referencia a la prueba en la tabla principal
            id_region INTEGER NOT NULL,                    -- Referencia a la región en la tabla de regiones
            hu_promedio REAL NOT NULL,                     -- Valor promedio medido en Hounsfield Units (HU) para la región
            desviacion REAL NOT NULL,                      -- Desviación estándar de los valores medidos en la región

            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_region) REFERENCES regiones_uniformidad(id_region),
            UNIQUE(id_prueba, id_region)
        );"""

        # Tabla para resultados globales de uniformidad
        uniformidad_global = """
        CREATE TABLE IF NOT EXISTS uniformidad_global (
            id_prueba INTEGER PRIMARY KEY,
            max_diferencia REAL NOT NULL,              -- Diferencia máxima entre ROIs
            desviacion_global REAL,                    -- Desviación estándar global
            uniformity_index_max REAL,                -- |UI|max (%)
            uniformity_index_roi VARCHAR(20),         -- ROI con peor UI
            integral_non_uniformity REAL,             -- INU (fracción)
            integral_non_uniformity_pct REAL,         -- INU (%)
            pasa_ui BOOLEAN NOT NULL,                 -- UI <= threshold
            pasa_inu BOOLEAN NOT NULL,                -- INU <= threshold  
            pasa_global BOOLEAN NOT NULL,             -- Ambos criterios
            ui_threshold_pct REAL,                    -- Umbral UI usado (2.0%)
            inu_threshold_pct REAL,                   -- Umbral INU usado (2.0%)
            hu_tolerancia REAL,                       -- Tolerancia HU usada (40.0)
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT
        );  """

        # Tabla para LINEALIDAD CT (pendiente de implementación)
        linealidad_ct = """
        CREATE TABLE IF NOT EXISTS linealidad_ct (
            id_prueba INTEGER PRIMARY KEY,
            pendiente REAL,                           -- Pendiente de la regresión
            intercepto REAL,                          -- Intercepto
            r_cuadrado REAL,                          -- Coeficiente de correlación²
            referencia REAL,                          -- Valor de referencia calculado
            escala_contraste REAL,                    -- 1/pendiente
            num_materiales INTEGER,                   -- Cantidad de materiales usados
            rango_hu_min REAL,                        -- HU mínimo del análisis
            rango_hu_max REAL,                        -- HU máximo del análisis
            linealidad_aceptable BOOLEAN,            -- r² >= 0.99
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE RESTRICT
        );"""

        cursor = self.con.cursor()
        cursor.execute(tipos_prueba)
        cursor.execute(pruebas)
        cursor.execute(espesor_corte)
        cursor.execute(tamaño_pixel)
        cursor.execute(rois_contraste)
        cursor.execute(resolucion_contraste)
        cursor.execute(resolucion_espacial)
        cursor.execute(resolucion_espacial_regiones)
        cursor.execute(materiales_ct)
        cursor.execute(valores_ct)
        cursor.execute(regiones_uniformidad)
        cursor.execute(uniformidad_ruido)
        cursor.execute(uniformidad_global)
        cursor.execute(linealidad_ct)
        self.con.commit()

    def crearTablasAnuales(self):
        energias = """
            CREATE TABLE IF NOT EXISTS energias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                energia TEXT
            )
        """
        # ------------------------------------------ 600 e ix ------------------------------------------
        tabla_factor_campo = """
            CREATE TABLE IF NOT EXISTS tabla_factor_campo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER, 
                id_energia INTEGER,
                tamano_campo TEXT,
                factor_campo REAL,
                factor_campo_esperado REAL,
                discrepancia REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )
        """

        tabla_factores_transmision = """
            CREATE TABLE IF NOT EXISTS tabla_factores_transmision (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER,
                id_energia INTEGER,
                angulo INTEGER,
                factor_transmision REAL,
                factor_transmision_esperado REAL,
                discrepancia REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""
        
        tabla_factores_sobre_eje = """
            CREATE TABLE IF NOT EXISTS tabla_factores_sobre_eje (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER,
                id_energia INTEGER,
                tam_pdd TEXT,
                profundidad INTEGER,
                ppd REAL,
                ppd_esperado REAL,
                discrepancia REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""
        
        tabla_control_camaras_monitoras = """
            CREATE TABLE IF NOT EXISTS tabla_control_camaras_monitoras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER,
                id_energia INTEGER,
                indicador_medir TEXT,
                valor_medido REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""

        # R1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 3, F-5): lecturas crudas
        # de la hoja "Linealidad" del formato oficial -- lo que hoy solo se
        # guarda como factor final derivado. Mismo patrón de las tablas de
        # arriba (id/ref/id_energia + FK), sin columna `activo`: la agrega
        # `_asegurar_activo_bloque_qc` en el arranque siguiente porque ya
        # están en `TABLAS_ANULABLES` desde que nacen.
        tabla_linealidad_um_anual = """
            CREATE TABLE IF NOT EXISTS anual_linealidad_um (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER,
                id_energia INTEGER,
                um TEXT,
                q1 REAL,
                q2 REAL,
                q_prom REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""

        tabla_lecturas_factor_campo_anual = """
            CREATE TABLE IF NOT EXISTS anual_lecturas_factor_campo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER,
                id_energia INTEGER,
                clave TEXT,
                q1 REAL,
                q2 REAL,
                q_prom REAL,
                factor REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""

        tabla_lecturas_transmision_anual = """
            CREATE TABLE IF NOT EXISTS anual_lecturas_transmision (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER,
                id_energia INTEGER,
                accesorio TEXT,
                q1_in REAL,
                q2_in REAL,
                q1_out REAL,
                q2_out REAL,
                q_med REAL,
                factor_t REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""

        tabla_tasa_dosis_anual = """
            CREATE TABLE IF NOT EXISTS anual_tasa_dosis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref INTEGER,
                id_energia INTEGER,
                tasa_um_min TEXT,
                med1 REAL,
                med2 REAL,
                FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""

        # -----------------------------------------------------------------------------------------------

        cursor = self.con.cursor()
        cursor.execute(energias)
        cursor.execute(tabla_factor_campo)
        cursor.execute(tabla_factores_transmision)
        cursor.execute(tabla_factores_sobre_eje)
        cursor.execute(tabla_control_camaras_monitoras)
        cursor.execute(tabla_linealidad_um_anual)
        cursor.execute(tabla_lecturas_factor_campo_anual)
        cursor.execute(tabla_lecturas_transmision_anual)
        cursor.execute(tabla_tasa_dosis_anual)
        self.con.commit()

    # Tablas para el Halcyon anual o mensual
    def crearTablasHalcyon(self):
        # Halcyon

        tabla_fantomas = """
        CREATE TABLE IF NOT EXISTS HC_fantomas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            modelo1 TEXT,
            serie1 TEXT,
            modelo2 TEXT,
            serie2 TEXT,
            modelo3 TEXT,
            serie3 TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        tabla_indi_colimador = """
        CREATE TABLE IF NOT EXISTS HC_indicadores_colimador (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            nivel REAL,
            valor_medido REAL,
            discrepancia REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        tabla_indi_brazo = """
        CREATE TABLE IF NOT EXISTS HC_indicadores_brazo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            nivel REAL,
            valor_medido REAL,
            discrepancia REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""
        
        tabla_indi_laser = """
        CREATE TABLE IF NOT EXISTS HC_indicadores_laser (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            ubicacion TEXT,
            concordancia REAL,
            dif_isocentro REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        tabla_indicadores_camilla = """
        CREATE TABLE IF NOT EXISTS HC_indicadores_camilla (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            ubicacion TEXT,
            desplazamiento REAL,
            medido_cm REAL,
            diferencia REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""    

        tabla_desplazamiento_iso = """
        CREATE TABLE IF NOT EXISTS HC_desplazamiento_isocentro_mensual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            ubicacion INTEGER,
            teorico REAL,
            medido REAL,
            diferencia REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        tabla_velocidad_multilaminas = """
        CREATE TABLE IF NOT EXISTS HC_velocidad_multilaminas_anual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            banco TEXT,
            velocidad_prom REAL,
            desviacion_med REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        tabla_precision_posicion_multilaminas = """
        CREATE TABLE IF NOT EXISTS HC_precision_posicion_multilaminas_anual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            medida REAL,
            esperada REAL,
            discrepancia REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        tabla_imagen_perfil_mlc = """
        CREATE TABLE IF NOT EXISTS HC_imagen_perfil_mlc_anual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            imagen BLOB,
            imagen_perfil_horiz BLOB,
            picos_perfil TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        # I4 (INFORME_BARRIDO_BD_RUTAS_24-07.md): mismo defecto clase-H2.7
        # que dosimetriaMen -- el DDL decía `val_teo_discrepancia`, pero la
        # BD de PRODUCCIÓN (y las copias del linaje) tienen `val_teo_dosis` +
        # `val_teo_calidad`, y NINGÚN código escribe/lee la columna del DDL
        # (la escritura real pasa por widget_a_columna → val_teo_calidad).
        # Encontrado por el test integral de migración (comparar el esquema
        # de una BD nueva contra la BD real migrada). Se alinea con
        # producción; _asegurar_migraciones_ad_hoc repara las BD que hayan
        # nacido del DDL equivocado.
        tabla_dosimetria_anual_hc = """CREATE TABLE IF NOT EXISTS HC_dosimetria_anual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            val_teo_dosis REAL,
            val_teo_calidad REAL,
            dosis_ref_cgy_um INTEGER,
            discrepancia_dosis INTEGER,
            tolerancia_dosis INTEGER,
            calidad_pdd20_10 INTEGER,
            discrepancia_calidad INTEGER,
            tolerancia_calidad INTEGER,
            simetria_inplane INTEGER,
            simetria_crossplane INTEGER,
            tolerancia_simetria INTEGER,
            planicidad_inplane INTEGER,
            planicidad_crossplane INTEGER,
            tolerancia_planicidad INTEGER,
            observaciones_dosi TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )
        """

        tabla_linealidad_unidades_monitor = """
        CREATE TABLE IF NOT EXISTS HC_linealidad_unidades_monitor_anual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            UM TEXT,
            Q1 REAL,
            Q2 REAL,
            Qprom REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""

        tabla_tamanos_campo_radiacion = """
        CREATE TABLE IF NOT EXISTS HC_tamanos_campo_radiacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,
            id_energia INTEGER,
            indicado_inplane REAL,
            indicado_crossplane REAL,
            medido_inplane REAL,
            medido_crossplane REAL,
            FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (id_energia) REFERENCES energias(id)
        )"""
        cursor = self.con.cursor()
        cursor.execute(tabla_fantomas)
        cursor.execute(tabla_indi_colimador)
        cursor.execute(tabla_indi_brazo)
        cursor.execute(tabla_indi_laser)
        cursor.execute(tabla_indicadores_camilla)
        cursor.execute(tabla_desplazamiento_iso)
        cursor.execute(tabla_velocidad_multilaminas)
        cursor.execute(tabla_precision_posicion_multilaminas)
        cursor.execute(tabla_dosimetria_anual_hc)
        cursor.execute(tabla_linealidad_unidades_monitor)
        cursor.execute(tabla_tamanos_campo_radiacion)
        cursor.execute(tabla_imagen_perfil_mlc)
        self.con.commit()
        
    def crearTablasMLCs(self):
        
        configuracion_picketfence=""" 
        CREATE TABLE IF NOT EXISTS configuracion_picketfence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER NOT NULL ,
            fecha TEXT, 
            equipo TEXT,
            fisico_1 TEXT,
            fisico_2 TEXT,
            tolerancia REAL,
            action_tolerance REAL,
            imagen_mlc BLOB,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
            )"""
        error_picket = """ 
        CREATE TABLE IF NOT EXISTS error_picket (
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER NOT NULL,
            picket INTEGER NOT NULL,
            picket_mean_error REAL NOT NULL,
            picket_max_error REAL NOT NULL,
            FOREIGN KEY (ref) REFERENCES configuracion_picketfence(id) ON DELETE RESTRICT ON UPDATE CASCADE
            
        )
        """
        leaf_error = """ 
        CREATE TABLE IF NOT EXISTS leaf_error (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER NOT NULL,
            leaf INTEGER NOT NULL,
            error REAL NOT NULL,
            FOREIGN KEY (ref) REFERENCES configuracion_picketfence(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
        highest_leaf_errors = """ 
        CREATE TABLE IF NOT EXISTS highest_leaf_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref integer NOT NULL,
            leaf_out INTEGER NOT NULL,
            picket_asociado INTEGER NOT NULL,
            desviacion REAL,
            FOREIGN KEY (ref) REFERENCES configuracion_picketfence(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
        
        # STARSHOT 
        
        configurar_starshot = """ 
        CREATE TABLE IF NOT EXISTS configuracion_starshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref integer NOT NULL,
            fecha TEXT,
            equipo TEXT,
            fisico_1 TEXT,
            fisico_2 TEXT,
            tolerancia REAL,
            sid REAL,
            imagen_mlc_spoke,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
      
        # EB2d (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2d, DA-57, 24-08): el
        # `UNIQUE(ref, spoke_index)` de tabla se retira -- NO es partial
        # (a diferencia del índice que crea CL1/`crear_indices()` sobre la
        # misma clave, `WHERE activo IS NULL OR activo=1`), así que
        # bloqueaba el modelo de anular+insertar: una fila anulada y una
        # vigente con el mismo (ref, spoke_index) violan esta constraint
        # aunque `activo` sea distinto. `_asegurar_migrar_angulo_starshot_
        # sin_unique_de_tabla` (abajo) migra cualquier BD que ya la tenga.
        angulos_starshot = """
        CREATE TABLE IF NOT EXISTS angulo_starshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref INTEGER NOT NULL,
        spoke_index INTEGER NOT NULL,
        angulo_nominal_deg REAL NOT NULL,
        angulo_real_deg REAL NOT NULL,
        desviacion_deg REAL NOT NULL,
        FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
        
        estadisticas_starshot = """ 
        CREATE TABLE IF NOT EXISTS estadisticas_starshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref integer NOT NULL,
            std_mm REAL, 
            rms_mm REAL,
            pm_95 REAL,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """
        
        angulos_entre_lineas_starshot = """ 
        CREATE TABLE IF NOT EXISTS angulos_entre_lineas_starshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER NOT NULL,
            separacion_ideal REAL,
            error_separacion REAL,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE RESTRICT ON UPDATE CASCADE
        )
        """   
        uniformidad_angular_starshot ="""
            CREATE TABLE IF NOT EXISTS uniformidad_angular_starshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref INTEGER NOT NULL,
        gap_index INTEGER NOT NULL,
        spoke_inicial INTEGER,
        spoke_final INTEGER,
        separacion_deg REAL,
        separacion_ideal_deg REAL,
        error_deg REAL,
        FOREIGN KEY (ref) REFERENCES controles(id)
            ON DELETE RESTRICT
            ON UPDATE CASCADE
    )"""
        
        cursor = self.con.cursor()
        
        tablas = [configuracion_picketfence, error_picket, leaf_error, highest_leaf_errors, configurar_starshot, angulos_starshot, estadisticas_starshot, uniformidad_angular_starshot, angulos_entre_lineas_starshot]
        
        for tabla in tablas:
            cursor.execute(tabla)
        self.con.commit()
        

        
            
        
        
            
        

    "Aqui solo se está llenando la tabla de los usuarios"
    def createAdmin(self):
        try:
            cur = self.con.cursor()
            cur.execute("SELECT COUNT(*) FROM users WHERE user = ?", ("admin",))
            if cur.fetchone()[0] == 0:  # Solo inserta si el admin no existe
                sql_insert = "INSERT INTO users (user, password, fullname, active) VALUES (?, ?, ?, ?)"
                encrypted_pass = encrypt_data("admin2025")
                print("Contraseña encriptada:", encrypted_pass)
                cur.execute(sql_insert, ("admin", encrypted_pass, "Administrador", 1))
                self.con.commit()
            cur.close()
        except Exception as ex:
            traceback.print_exc()
            print("Error al crear admin:", ex)

    def conectar(self):
        try:
            con = sqlite3.connect(ruta_base_datos(), check_same_thread=False)
            aplicar_pragmas_conexion(con)
            return _ConexionUnaVez(con)
        except Exception as e:
            print("Error al obtener conexión nueva:", e)
            return None
