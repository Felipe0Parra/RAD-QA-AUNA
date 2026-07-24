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
