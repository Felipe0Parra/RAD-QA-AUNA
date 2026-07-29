"""M1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): herramienta para traer
CUALQUIER archivo .db (una copia vieja de otra sesión de trabajo, un backup
de hace meses) al estándar de esquema de la app actual -- pedida
explícitamente por el físico ("garantizar que está a la par de los cambios
que hemos hecho y listo para usarse en cualquier momento").

Reproduce el escenario real: una BD "vieja" con tablas ya desplegadas pero
sin varias de las columnas que se han ido agregando en fases sucesivas de
este proyecto (activo, energia/vigente/protocolo_trs398, mes_control,
imagen_certificado, etc.) y con el centinela histórico ' ---- ' en
user_id_f2 -- y verifica que `migrar()` la deja igual de completa que una BD
creada hoy, sin tocar ningún otro dato, de forma idempotente.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts.migrar_bd_a_estandar import migrar, CENTINELA_SEGUNDO_FISICO


def _crear_bd_vieja(ruta):
    """Esquema de una BD real ANTERIOR a C2 (controles.activo), B3.1
    (energia/vigente/protocolo_trs398), R3 (mes_control, imagen_certificado,
    etc.) y con el centinela de user_id_f2 que usaba create_control antes de
    X1 -- con datos reales en cada tabla, para verificar que sobreviven."""
    con = sqlite3.connect(ruta)
    con.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT UNIQUE, password TEXT, fullname TEXT UNIQUE,
            active INTEGER, idreal INTEGER, role TEXT, firma BLOB
        )
    """)
    con.execute(
        "INSERT INTO users (user, password, fullname, active) "
        "VALUES ('fisico', 'x', 'Físico de Prueba', 1)")
    con.execute("""
        CREATE TABLE controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo TEXT, control TEXT, fecha TEXT,
            user_id TEXT, user_id_f2 TEXT
        )
    """)
    con.execute(
        "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
        "VALUES ('Clinac iX', 'Mensual', '01/2026', 'Físico de Prueba', ?)",
        (CENTINELA_SEGUNDO_FISICO,))
    con.execute(
        "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
        "VALUES ('Clinac 600', 'Mensual', '02/2026', 'Físico de Prueba', 'Otro Físico')")
    con.execute("""
        CREATE TABLE calculadora_dosimetrica (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT, Acelerador TEXT, Tipo_de_radiacion TEXT
        )
    """)
    con.execute(
        "INSERT INTO calculadora_dosimetrica (Fecha, Acelerador, Tipo_de_radiacion) "
        "VALUES ('09/04/2026', 'Seiscientos', 'Fotones')")
    con.execute("CREATE TABLE pruebas (id_prueba INTEGER PRIMARY KEY AUTOINCREMENT, id_sesion TEXT)")
    con.execute("INSERT INTO pruebas (id_sesion) VALUES ('sesion_vieja')")
    con.commit()
    con.close()


@pytest.fixture
def bd_vieja(tmp_path):
    ruta = str(tmp_path / "bd_vieja.db")
    _crear_bd_vieja(ruta)
    return ruta


class TestDryRunNuncaTocaElArchivoOriginal:

    def test_dry_run_no_modifica_el_archivo(self, bd_vieja):
        con = sqlite3.connect(bd_vieja)
        contenido_antes = con.execute("SELECT * FROM controles").fetchall()
        cols_antes = [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()]
        con.close()

        resultado = migrar(bd_vieja, aplicar=False)

        con = sqlite3.connect(bd_vieja)
        contenido_despues = con.execute("SELECT * FROM controles").fetchall()
        cols_despues = [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()]
        con.close()

        assert resultado["aplicado"] is False
        assert contenido_antes == contenido_despues  # ni el centinela se tocó
        assert cols_antes == cols_despues  # esquema original intacto
        assert "activo" not in cols_despues  # confirma que NO se migró de verdad

    def test_dry_run_no_deja_backup(self, bd_vieja, tmp_path):
        migrar(bd_vieja, aplicar=False)
        archivos = os.listdir(tmp_path)
        assert not any(".pre_migracion_" in f for f in archivos)


class TestAplicarTraeElEsquemaCompleto:

    def test_columnas_de_todas_las_fases_quedan_presentes(self, bd_vieja):
        migrar(bd_vieja, aplicar=True)

        con = sqlite3.connect(bd_vieja)
        cols_controles = [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()]
        cols_calc = [c[1] for c in con.execute("PRAGMA table_info(calculadora_dosimetrica)").fetchall()]
        cols_pruebas = [c[1] for c in con.execute("PRAGMA table_info(pruebas)").fetchall()]
        con.close()

        assert "activo" in cols_controles  # C2
        assert "energia" in cols_calc and "vigente" in cols_calc  # B3.1
        assert "protocolo_trs398" in cols_calc  # K3
        assert "mes_control" in cols_pruebas and "equipo" in cols_pruebas  # R3

    def test_tablas_completamente_nuevas_tambien_se_crean(self, bd_vieja):
        """audit_log no existía en absoluto en la BD vieja."""
        migrar(bd_vieja, aplicar=True)
        con = sqlite3.connect(bd_vieja)
        tablas = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        con.close()
        assert "audit_log" in tablas

    def test_centinela_de_segundo_fisico_se_normaliza_a_null(self, bd_vieja):
        migrar(bd_vieja, aplicar=True)
        con = sqlite3.connect(bd_vieja)
        filas = con.execute(
            "SELECT equipo, user_id_f2 FROM controles ORDER BY id").fetchall()
        con.close()
        assert filas[0] == ("Clinac iX", None)  # tenía el centinela
        assert filas[1] == ("Clinac 600", "Otro Físico")  # no se toca lo que ya estaba bien

    def test_datos_preexistentes_sobreviven_intactos(self, bd_vieja):
        migrar(bd_vieja, aplicar=True)
        con = sqlite3.connect(bd_vieja)
        # createAdmin() (parte del arranque normal que este script reutiliza)
        # agrega un usuario "admin" si no existe -- filtrar por el usuario
        # preexistente en vez de asumir una sola fila en la tabla.
        fisico = con.execute(
            "SELECT fullname FROM users WHERE user = 'fisico'").fetchone()[0]
        fecha_calc = con.execute("SELECT Fecha FROM calculadora_dosimetrica").fetchone()[0]
        sesion = con.execute("SELECT id_sesion FROM pruebas").fetchone()[0]
        con.close()
        assert fisico == "Físico de Prueba"
        assert fecha_calc == "09/04/2026"
        assert sesion == "sesion_vieja"

    def test_deja_backup_con_el_contenido_original(self, bd_vieja, tmp_path):
        con = sqlite3.connect(bd_vieja)
        centinela_antes = con.execute(
            "SELECT user_id_f2 FROM controles WHERE equipo='Clinac iX'").fetchone()[0]
        con.close()

        resultado = migrar(bd_vieja, aplicar=True)

        assert resultado["aplicado"] is True
        respaldo = resultado["respaldo"]
        assert os.path.exists(respaldo)
        con = sqlite3.connect(respaldo)
        centinela_en_backup = con.execute(
            "SELECT user_id_f2 FROM controles WHERE equipo='Clinac iX'").fetchone()[0]
        cols_backup = [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()]
        con.close()
        assert centinela_en_backup == centinela_antes  # el backup preserva el estado ANTES
        assert "activo" not in cols_backup  # el backup es de antes de migrar, no de después

    def test_integrity_check_ok_antes_y_despues(self, bd_vieja):
        resultado = migrar(bd_vieja, aplicar=True)
        assert resultado["integridad_antes"] == "ok"
        assert resultado["integridad_despues"] == "ok"


class TestIdempotencia:

    def test_correr_dos_veces_no_duplica_ni_falla(self, bd_vieja):
        migrar(bd_vieja, aplicar=True)
        con = sqlite3.connect(bd_vieja)
        n_cols_primera = len(con.execute("PRAGMA table_info(controles)").fetchall())
        con.close()

        resultado2 = migrar(bd_vieja, aplicar=True)

        con = sqlite3.connect(bd_vieja)
        n_cols_segunda = len(con.execute("PRAGMA table_info(controles)").fetchall())
        con.close()

        assert n_cols_segunda == n_cols_primera
        assert resultado2["sentinelas_normalizadas"] == 0  # ya no queda ninguno


class TestValidacionDeEntradaFBD2:
    """F-BD2 (INFORME_BARRIDO_BD_RUTAS_24-07.md): sin la validación,
    `sqlite3.connect` sobre una ruta con typo creaba un archivo vacío y la
    herramienta lo "migraba" con éxito -- el físico creería que migró su BD
    real cuando migró una vacía nueva en la ruta equivocada."""

    def test_ruta_inexistente_aborta_sin_crear_archivo(self, tmp_path):
        ruta_typo = str(tmp_path / "BaseDatosQA_typo.db")

        with pytest.raises(SystemExit):
            migrar(ruta_typo, aplicar=True)

        assert not os.path.exists(ruta_typo)  # la herramienta nunca crea archivos

    def test_ruta_inexistente_aborta_tambien_en_dry_run(self, tmp_path):
        ruta_typo = str(tmp_path / "no_existe.db")
        with pytest.raises(SystemExit):
            migrar(ruta_typo, aplicar=False)
        assert not os.path.exists(ruta_typo)

    def test_archivo_que_no_es_sqlite_aborta_sin_tocarlo(self, tmp_path):
        ruta = str(tmp_path / "no_es_bd.db")
        contenido = b"esto es un archivo de texto, no una base de datos"
        with open(ruta, "wb") as f:
            f.write(contenido)

        with pytest.raises(SystemExit):
            migrar(ruta, aplicar=True)

        with open(ruta, "rb") as f:
            assert f.read() == contenido  # intacto, byte a byte
        assert not any(".pre_migracion_" in n for n in os.listdir(tmp_path))

    def test_archivo_vacio_cero_bytes_aborta(self, tmp_path):
        """El caso exacto que produce un connect previo accidental: un .db de
        0 bytes no tiene cabecera SQLite y no es una BD migrable."""
        ruta = str(tmp_path / "vacio.db")
        open(ruta, "wb").close()
        with pytest.raises(SystemExit):
            migrar(ruta, aplicar=True)


class TestWalDeLaBdEntranteI3:
    """I3/F-BD3 (INFORME_BARRIDO_BD_RUTAS_24-07.md): una BD traída de otra
    máquina puede llegar con commits SOLO en su archivo `-wal` (el rebuild
    del físico traía 473 KB así). La herramienta debe consolidarlos, no
    perderlos: el dry-run copia el set completo y el `--aplicar` checkpointea
    antes del backup. Técnica del arnés: mantener abierta una conexión WAL
    con autocheckpoint apagado, para que el commit viva solo en el -wal
    (misma técnica que la suite R2)."""

    def _abrir_con_fila_solo_en_wal(self, ruta):
        """Deja `ruta` con una fila de `controles` (con el centinela) cuyo
        commit vive SOLO en el -wal. Devuelve la conexión (mantener abierta:
        cerrarla dispararía el checkpoint automático y desarmaría el caso)."""
        con = sqlite3.connect(ruta)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_autocheckpoint=0")
        con.execute(
            "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) "
            "VALUES ('Halcyon', 'Mensual', '03/2026', 'Físico de Prueba', ?)",
            (CENTINELA_SEGUNDO_FISICO,))
        con.commit()
        return con

    def test_dry_run_ve_los_datos_que_viven_solo_en_el_wal(self, bd_vieja, capsys):
        con_abierta = self._abrir_con_fila_solo_en_wal(bd_vieja)
        try:
            assert os.path.getsize(bd_vieja + "-wal") > 0  # el commit está en el -wal

            migrar(bd_vieja, aplicar=False)

            salida = capsys.readouterr().out
            # la BD vieja traía 1 centinela en el .db + 1 solo-en-wal = 2;
            # sin la copia del set completo, la simulación solo veía 1
            assert "2 encontradas, 2 normalizadas" in salida
        finally:
            con_abierta.close()

    def test_aplicar_consolida_y_el_backup_es_completo(self, bd_vieja):
        con_abierta = self._abrir_con_fila_solo_en_wal(bd_vieja)
        try:
            resultado = migrar(bd_vieja, aplicar=True)
        finally:
            con_abierta.close()

        # el BACKUP (copia simple del .db, sin -wal) debe contener TAMBIÉN la
        # fila que vivía solo en el -wal -- prueba de que se consolidó antes
        con_bak = sqlite3.connect(resultado["respaldo"])
        n_backup = con_bak.execute(
            "SELECT COUNT(*) FROM controles").fetchone()[0]
        con_bak.close()
        assert n_backup == 3  # las 2 de la BD vieja + la que vivía en el -wal

        con = sqlite3.connect(bd_vieja)
        n_final = con.execute("SELECT COUNT(*) FROM controles").fetchone()[0]
        sentinelas = con.execute(
            "SELECT COUNT(*) FROM controles WHERE user_id_f2 = ?",
            (CENTINELA_SEGUNDO_FISICO,)).fetchone()[0]
        con.close()
        assert n_final == 3
        assert sentinelas == 0  # ambas centinelas (la del .db y la del wal) normalizadas


def _agregar_equipos_del_linaje(ruta, con_deriva=False):
    """Tabla `equipos` como la traería una BD del linaje de producción
    ANTES del saneamiento H2.6/H2.10: la fila id=13 (N30013 vigente) con las
    condiciones AMBIENTALES del certificado grabadas en t_cal/p_cal (el error
    dosimétrico de ~2% en kTP que H2.6 corrigió). Con `con_deriva=True`, la
    fila id=16 trae un valor que NO coincide ni con el antes ni con el
    después esperado -- simula una BD que fue editada por otra vía."""
    con = sqlite3.connect(ruta)
    con.execute("""
        CREATE TABLE equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equip_type TEXT, model TEXT, serie TEXT,
            calibr_fact INTEGER, calibr_fact2 INTEGER,
            fecha_calibr INTEGER, fabricante TEXT,
            t_cal REAL, p_cal REAL, h_cal REAL, v1 TEXT,
            vigente REAL, activo REAL
        )
    """)
    con.execute(
        "INSERT INTO equipos (id, model, serie, t_cal, p_cal, vigente, activo) "
        "VALUES (13, 'N30013', '2123', 20.9, 98.91, 1, 1)")
    if con_deriva:
        con.execute(
            "INSERT INTO equipos (id, model, serie, calibr_fact, vigente, activo) "
            "VALUES (16, 'HDR1000 Plus', 'A972662', 12345, 1, 1)")
    con.commit()
    con.close()


class TestSaneamientoDeEquiposDentroDeM1:
    """I1 (PLAN §10, decisión del físico 2026-07-24): las correcciones del
    catálogo de equipos (H2.6/H2.10) corren POR DEFECTO como parte de la
    migración -- una BD del linaje de producción original llega con los
    mismos errores que los certificados corrigieron, y debe quedar corregida
    en la misma corrida."""

    def test_fila_del_linaje_queda_corregida(self, bd_vieja):
        _agregar_equipos_del_linaje(bd_vieja)

        resultado = migrar(bd_vieja, aplicar=True)

        con = sqlite3.connect(bd_vieja)
        t_cal, p_cal = con.execute(
            "SELECT t_cal, p_cal FROM equipos WHERE id = 13").fetchone()
        con.close()
        assert (t_cal, p_cal) == (22.0, 101.325)  # condiciones de REFERENCIA
        ids_aplicados = [c["id"] for c in resultado["equipos"]["aplicados"]]
        assert 13 in ids_aplicados

    def test_fila_con_deriva_queda_intacta_y_reportada(self, bd_vieja):
        """La garantía de seguridad: una fila que no coincide con el estado
        esperado de los certificados NO se toca -- se reporta para revisión
        humana."""
        _agregar_equipos_del_linaje(bd_vieja, con_deriva=True)

        resultado = migrar(bd_vieja, aplicar=True)

        con = sqlite3.connect(bd_vieja)
        valor = con.execute(
            "SELECT calibr_fact FROM equipos WHERE id = 16").fetchone()[0]
        con.close()
        assert valor == 12345  # intacta, byte a byte
        ids_deriva = [c["id"] for c in resultado["equipos"]["con_deriva"]]
        assert 16 in ids_deriva

    def test_cada_correccion_queda_auditada_en_la_bd_destino(self, bd_vieja):
        _agregar_equipos_del_linaje(bd_vieja)

        migrar(bd_vieja, aplicar=True, usuario="fisico_migrando")

        con = sqlite3.connect(bd_vieja)
        filas = con.execute(
            "SELECT usuario, ref FROM audit_log "
            "WHERE accion = 'saneamiento_h26' AND tabla = 'equipos'").fetchall()
        con.close()
        assert ("fisico_migrando", "13") in filas

    def test_segunda_corrida_reporta_ya_aplicados_sin_recambiar(self, bd_vieja):
        _agregar_equipos_del_linaje(bd_vieja)
        migrar(bd_vieja, aplicar=True)

        resultado2 = migrar(bd_vieja, aplicar=True)

        assert resultado2["equipos"]["aplicados"] == []
        ids_ya = [c["id"] for c in resultado2["equipos"]["ya_aplicados"]]
        assert 13 in ids_ya

    def test_dry_run_muestra_lo_que_corregiria_sin_tocar_el_archivo(self, bd_vieja):
        _agregar_equipos_del_linaje(bd_vieja)

        resultado = migrar(bd_vieja, aplicar=False)

        con = sqlite3.connect(bd_vieja)
        t_cal = con.execute("SELECT t_cal FROM equipos WHERE id = 13").fetchone()[0]
        con.close()
        assert t_cal == 20.9  # el original NO se tocó
        ids_aplicados = [c["id"] for c in resultado["equipos"]["aplicados"]]
        assert 13 in ids_aplicados  # pero el reporte muestra qué corregiría


class TestResumenQcPreservadoI2:
    """I2 (PLAN §10): la razón de incorporar una BD vieja es NO perder ni una
    fila de QC -- el reporte lo demuestra con conteos antes==después, y el
    resultado los expone para verificación programática."""

    def test_conteos_qc_identicos_antes_y_despues(self, bd_vieja):
        con = sqlite3.connect(bd_vieja)
        con.executemany(
            "INSERT INTO controles (equipo, control, fecha, user_id) "
            "VALUES (?, 'Mensual', ?, 'Físico de Prueba')",
            [("Clinac iX", "03/2026"), ("Halcyon", "04/2026"),
             ("Clinac 600", "05/2026")])
        con.commit()
        con.close()

        resultado = migrar(bd_vieja, aplicar=True)

        assert resultado["qc_antes"] == resultado["qc_despues"]
        assert resultado["qc_despues"]["controles"] == 5  # 2 de la vieja + 3 QC extra
        assert resultado["qc_despues"]["calculadora_dosimetrica"] == 1
        assert resultado["qc_despues"]["pruebas"] == 1

    def test_reporte_dice_que_ningun_registro_se_perdio(self, bd_vieja, capsys):
        migrar(bd_vieja, aplicar=True)
        salida = capsys.readouterr().out
        assert "Registros de QC preservados" in salida
        assert "Ningún registro de QC se perdió" in salida
        assert "PERDIDA" not in salida

    def test_tablas_ausentes_en_bd_vieja_cuentan_como_cero(self, bd_vieja):
        """`dosimetriaMen`/`tamano_campo` no existen en la BD vieja sintética
        -- el conteo 'antes' debe ser 0 (no un crash), y 'después' 0 también
        (la migración crea la tabla pero no inventa filas)."""
        resultado = migrar(bd_vieja, aplicar=True)
        assert resultado["qc_antes"]["dosimetriaMen"] == 0
        assert resultado["qc_despues"]["dosimetriaMen"] == 0


class TestBdYaAlDiaNoReportaCambios:

    def test_bd_recien_creada_por_la_app_no_tiene_cambios_que_reportar(self, tmp_path, monkeypatch):
        """Una BD creada HOY por la propia app (vía Conexion()) ya tiene
        todo lo que migrar() asegura -- correr la herramienta sobre ella no
        debería reportar ninguna columna/tabla nueva ni ningún centinela."""
        import data.ManejoDatos.conection as conection_mod
        from data.ManejoDatos.conection import Conexion

        ruta = str(tmp_path / "bd_nueva.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        instancia = Conexion()
        instancia.con.close()
        Conexion._instance = None

        resultado = migrar(ruta, aplicar=True)

        assert resultado["sentinelas_normalizadas"] == 0


def _bd_legada_con_cascada(ruta):
    """F2 (PLAN_F_CIERRE_ESTANDAR_29-07.md): subconjunto real del esquema
    PRE-E10, con una FK que SÍ declara borrado en cascada (mismo patrón que
    test_e10_restrict.py::TestMigracionDeBdLegada) -- `_crear_bd_vieja` de
    este archivo no tiene ninguna FK, así que nunca ejercita la migración
    estructural (E10/E8/E6/sqlite_sequence) que F2 debe reportar."""
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT UNIQUE, password TEXT, fullname TEXT UNIQUE,
            active INTEGER, idreal INTEGER, role TEXT, firma BLOB
        );
        CREATE TABLE controles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo TEXT, control TEXT, fecha TEXT,
            user_id TEXT, user_id_f2 TEXT);
        CREATE TABLE dosimetriaMen (
            ref INTEGER, energia TEXT,
            FOREIGN KEY (ref) REFERENCES controles(id)
                ON DELETE CASCADE ON UPDATE CASCADE);
    """)
    con.execute("INSERT INTO users (user, password, fullname, active) "
                "VALUES ('admin', 'x', 'Administrador', 1)")
    con.execute("INSERT INTO controles (equipo, control, fecha) "
                "VALUES ('Clinac iX', 'Mensual', '01/2026')")
    con.execute("INSERT INTO dosimetriaMen (ref, energia) VALUES (1, '6mv')")
    con.commit()
    con.close()


@pytest.fixture
def bd_legada_con_cascada(tmp_path):
    ruta = str(tmp_path / "legada_cascada.db")
    _bd_legada_con_cascada(ruta)
    return ruta


class TestCambiosEstructuralesReportadosF2:
    """F2: antes, recrear tablas a RESTRICT, crear triggers anti-borrado y
    asignar roles ocurría en silencio -- el reporte no lo mencionaba en
    ningún lado. Esta clase fija que el reporte SÍ lo cuenta."""

    def test_dry_run_reporta_migracion_a_restrict_y_triggers(
            self, bd_legada_con_cascada, capsys):
        migrar(bd_legada_con_cascada, aplicar=False)
        salida = capsys.readouterr().out
        assert "Cambios estructurales" in salida
        assert "dosimetriaMen" in salida.split("Cambios estructurales")[1]
        assert "trg_no_borrar_controles" in salida
        assert "Roles de sistema asignados" in salida

    def test_dry_run_no_modifica_nada_pese_a_reportarlo(
            self, bd_legada_con_cascada):
        con = sqlite3.connect(bd_legada_con_cascada)
        acciones_antes = {fk[6] for fk in con.execute(
            "PRAGMA foreign_key_list('dosimetriaMen')").fetchall()}
        con.close()

        migrar(bd_legada_con_cascada, aplicar=False)

        con = sqlite3.connect(bd_legada_con_cascada)
        acciones_despues = {fk[6] for fk in con.execute(
            "PRAGMA foreign_key_list('dosimetriaMen')").fetchall()}
        con.close()
        assert acciones_antes == acciones_despues == {"CASCADE"}

    def test_aplicar_migra_de_verdad_y_lo_reporta(
            self, bd_legada_con_cascada, capsys):
        migrar(bd_legada_con_cascada, aplicar=True)
        salida = capsys.readouterr().out
        assert "Tablas migradas de borrado en cascada a RESTRICT" in salida
        assert "Triggers anti-borrado creados" in salida
        assert "Filas duplicadas de sqlite_sequence normalizadas" not in salida  # no había ninguna

        con = sqlite3.connect(bd_legada_con_cascada)
        acciones = {fk[6] for fk in con.execute(
            "PRAGMA foreign_key_list('dosimetriaMen')").fetchall()}
        con.close()
        assert acciones == {"RESTRICT"}

    def test_segunda_corrida_no_repite_los_cambios_estructurales(
            self, bd_legada_con_cascada, capsys):
        migrar(bd_legada_con_cascada, aplicar=True)
        capsys.readouterr()  # descarta la salida de la primera corrida

        migrar(bd_legada_con_cascada, aplicar=True)
        salida = capsys.readouterr().out
        assert "sin cambios estructurales -- la base ya estaba al día" in salida

    def test_censo_completo_cubre_todas_las_tablas_no_solo_las_6_de_qc(
            self, bd_legada_con_cascada, capsys):
        resultado = migrar(bd_legada_con_cascada, aplicar=True)
        salida = capsys.readouterr().out
        assert "Censo completo" in salida
        assert "users" in resultado["censo_despues"]  # fuera de TABLAS_QC
        assert "dosimetriaMen" in resultado["censo_despues"]  # dentro de TABLAS_QC
        assert len(resultado["censo_despues"]) >= 3


class TestCensoCompletoDetectaPerdidaFueraDeQc:
    """Prueba unitaria directa: `_reportar_censo_completo` es la red de
    seguridad para las ~63 tablas que `_reportar_qc` no vigila. No hay forma
    natural de inducir una pérdida real vía `migrar()` (es puramente
    aditiva) -- se ejercita la función directamente, como exige verificar
    que la alarma SÍ se dispara y no solo que nunca se dispara."""

    def test_una_tabla_fuera_de_qc_que_pierde_filas_dispara_la_alarma(self):
        from scripts.migrar_bd_a_estandar import _reportar_censo_completo

        antes = {"users": 7, "equipos": 39, "controles": 24}
        despues = {"users": 7, "equipos": 38, "controles": 24}  # equipos perdió 1

        perdida = _reportar_censo_completo(antes, despues)

        assert perdida is True

    def test_ninguna_perdida_no_dispara_la_alarma(self):
        from scripts.migrar_bd_a_estandar import _reportar_censo_completo

        antes = {"users": 7, "equipos": 39}
        despues = {"users": 7, "equipos": 39}

        assert _reportar_censo_completo(antes, despues) is False
