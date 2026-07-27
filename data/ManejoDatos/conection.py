import sqlite3
import sys
import os
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
            #self.eliminar_tablas_cambio_fuente()
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

        except Exception as ex:
            traceback.print_exc()
            print("Error al conectar a la base de datos:", ex)

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
            firma BLOB
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
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (user_id) REFERENCES users(fullname) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (user_id_f2) REFERENCES users(fullname) ON DELETE CASCADE ON UPDATE CASCADE
        )
        """
        # Tabla de datos de los indicadores de brazos
        sql_create_table7 = """
        CREATE TABLE IF NOT EXISTS indicadores_brazo (
            ref INTEGER,
            nivel TEXT,
            indicador_luminoso_consola TEXT,
            indicador_luminoso_equipo TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
        )  
        """
        # Tabla de datos de los indicadores del colimador
        sql_create_table8 = """
        CREATE TABLE IF NOT EXISTS indicadores_angulares_colimador (
            ref INTEGER,
            nivel TEXT,
            indicador_luminoso_consola TEXT,
            indicador_luminoso_equipo TEXT, 
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
        )"""
        
        sql_create_table14 = """CREATE TABLE IF NOT EXISTS control_conos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER,         -- referencia o identificador del equipo/paciente
            medida TEXT NOT NULL,      -- por ejemplo "6x6", "10x10", etc.
            valor INTEGER NOT NULL,     -- 1 = funciona, 0 = no funciona
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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

    def eliminar_tablas_cambio_fuente(self):
        nombres_tablas = [
            "TipoCalibracion",
            "SistemaMedicion",
            "CondicionesMedicion",
            "MaximosCamaras",
            "LecturasMaximos",
            "ResultadosActividad"
        ]
        
        cursor = self.con.cursor()
        for nombre in nombres_tablas:
            cursor.execute(f"DROP TABLE IF EXISTS {nombre}")
        self.con.commit()

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
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE CASCADE ON UPDATE CASCADE
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
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE CASCADE ON UPDATE CASCADE
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
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE CASCADE ON UPDATE CASCADE
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
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE CASCADE ON UPDATE CASCADE
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
                FOREIGN KEY (ref) REFERENCES TipoCalibracion(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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
                ON DELETE CASCADE ON UPDATE CASCADE
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
                ON DELETE CASCADE ON UPDATE CASCADE
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

            FOREIGN KEY (id_sesion) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE,
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
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE ON UPDATE CASCADE
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
                FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE
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
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE
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
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE
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
                FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE
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
                FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE
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

            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE,
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

            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE ON UPDATE CASCADE,
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
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE
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
            FOREIGN KEY (id_prueba) REFERENCES pruebas(id_prueba) ON DELETE CASCADE
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
                ON DELETE CASCADE ON UPDATE CASCADE,
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
                ON DELETE CASCADE ON UPDATE CASCADE,
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
                ON DELETE CASCADE ON UPDATE CASCADE,
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
                ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (id_energia) REFERENCES energias(id)
            )"""

        # -----------------------------------------------------------------------------------------------

        cursor = self.con.cursor()
        cursor.execute(energias)
        cursor.execute(tabla_factor_campo)
        cursor.execute(tabla_factores_transmision)
        cursor.execute(tabla_factores_sobre_eje)
        cursor.execute(tabla_control_camaras_monitoras)
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            ON DELETE CASCADE ON UPDATE CASCADE,
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
            )"""
        error_picket = """ 
        CREATE TABLE IF NOT EXISTS error_picket (
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER NOT NULL,
            picket INTEGER NOT NULL,
            picket_mean_error REAL NOT NULL,
            picket_max_error REAL NOT NULL,
            FOREIGN KEY (ref) REFERENCES configuracion_picketfence(id) ON DELETE CASCADE ON UPDATE CASCADE
            
        )
        """
        leaf_error = """ 
        CREATE TABLE IF NOT EXISTS leaf_error (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER NOT NULL,
            leaf INTEGER NOT NULL,
            error REAL NOT NULL,
            FOREIGN KEY (ref) REFERENCES configuracion_picketfence(id) ON DELETE CASCADE ON UPDATE CASCADE
        )
        """
        highest_leaf_errors = """ 
        CREATE TABLE IF NOT EXISTS highest_leaf_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref integer NOT NULL,
            leaf_out INTEGER NOT NULL,
            picket_asociado INTEGER NOT NULL,
            desviacion REAL,
            FOREIGN KEY (ref) REFERENCES configuracion_picketfence(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
        )
        """
      
        angulos_starshot = """    
        CREATE TABLE IF NOT EXISTS angulo_starshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref INTEGER NOT NULL,
        spoke_index INTEGER NOT NULL,
        angulo_nominal_deg REAL NOT NULL,
        angulo_real_deg REAL NOT NULL,
        desviacion_deg REAL NOT NULL,
        FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE, 
        UNIQUE(ref, spoke_index)
        )
        """
        
        estadisticas_starshot = """ 
        CREATE TABLE IF NOT EXISTS estadisticas_starshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref integer NOT NULL,
            std_mm REAL, 
            rms_mm REAL,
            pm_95 REAL,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
        )
        """
        
        angulos_entre_lineas_starshot = """ 
        CREATE TABLE IF NOT EXISTS angulos_entre_lineas_starshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref INTEGER NOT NULL,
            separacion_ideal REAL,
            error_separacion REAL,
            FOREIGN KEY (ref) REFERENCES controles(id) ON DELETE CASCADE ON UPDATE CASCADE
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
            ON DELETE CASCADE
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
            return con
        except Exception as e:
            print("Error al obtener conexión nueva:", e)
            return None
