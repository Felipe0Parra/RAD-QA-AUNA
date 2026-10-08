"""RB.1 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-150): el respaldo es una foto consistente de la base y se
comprueba antes de contar como respaldo.

Defecto (medido en M6, E2): `respaldar_bd` copiaba el archivo `.db` (`shutil.copy2`). Si en el momento del cierre otro equipo
tenia una operacion abierta, el checkpoint del WAL quedaba a medias y esa copia era un archivo DAÑADO ("database disk image is
malformed" o sin las tablas), sin los guardados recientes; aun asi se auditaba como respaldo hecho y la rotacion borraba una
copia buena para hacerle sitio.

Contrato nuevo:
  - la copia se hace con la API de respaldo de SQLite, en UN solo paso, a un nombre provisional (`.parcial`) que no cuenta como
    respaldo; trae todo lo confirmado hasta ese instante aunque haya un lector a medio leer y el checkpoint no haya terminado;
  - solo se renombra (y se rota y se audita) si `PRAGMA integrity_check` da `ok`;
  - si la copia no pasa y la base de origen esta sana: se descarta y se devuelve None; si el origen esta DAÑADO (o SQLite no lo
    puede leer): no se rota ni se cuenta nada, se conserva una copia aparte (`.revisar`, fuera de la rotacion, a lo sumo 3: la
    primera y las mas recientes) y se deja una fila de auditoria visible en Registros -- si la base permite escribirla: cuando
    SQLite no puede ni abrirla, la auditoria vive en esa misma base y la constancia es la copia aparte (H3 de la revision);
  - una base ocupada por otro NO es un defecto (sin alarma), y la espera esta acotada: `Connection.backup` reintenta SIN FIN
    mientras el origen esta ocupado, y un cierre colgado es justo lo que RB.0 elimino;
  - (revision de RB.1) el provisional de cada copia lleva un nombre PROPIO y nadie toca uno ajeno; un archivo ausente o de
    0 bytes nunca se da por bueno.

Todo lo de concurrencia usa PROCESOS separados (en Linux, la SQLite de Python y la de Qt dentro de un mismo proceso no se ven
los bloqueos entre si).
"""
import ast
import contextlib
import errno
import inspect
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

from services import respaldo
from services.respaldo import MAX_COPIAS_A_REVISAR, MAX_RESPALDOS, PREFIJO_RESPALDO, respaldar_bd

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AHORA = datetime(2026, 10, 5, 12, 0, 0)
LIMITE_S = 25


# ----------------------------------------------------------------------------------------------------------- ayudas
def _bd_wal(tmp_path, filas=3000):
    """Base en modo WAL con el autocheckpoint apagado y una conexion de ESCRITURA abierta (la devuelve)."""
    origen = str(tmp_path / "BaseDatosQA.db")
    con = sqlite3.connect(origen)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i}" * 20,) for i in range(filas)])
    con.commit()
    return origen, con


def _bd_simple(ruta, filas=3000):
    """Base en el modo normal (sin WAL), de ~80 paginas."""
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i} " * 10,) for i in range(filas)])
    con.commit()
    con.close()


def _nombre(momento, contador=None):
    sufijo = f"_{contador:02d}" if contador else ""
    return f"{PREFIJO_RESPALDO}{momento.strftime('%Y-%m-%d_%H%M%S')}{sufijo}.db"


def _tocar(carpeta, nombre, contenido=b"copia"):
    with open(os.path.join(carpeta, nombre), "wb") as f:
        f.write(contenido)


def _estado_de_la_copia(ruta):
    """`(integrity_check, filas, ultima fila)` de una copia; si no abre: `('no abre: ...', None, None)`."""
    try:
        con = sqlite3.connect(ruta)
        try:
            integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
            filas = con.execute("SELECT COUNT(*) FROM datos").fetchone()[0]
            ultima = con.execute("SELECT valor FROM datos ORDER BY id DESC LIMIT 1").fetchone()[0]
        finally:
            con.close()
        return integridad, filas, ultima
    except Exception as ex:
        return (f"no abre: {ex}", None, None)


def _auditoria_backup(origen):
    """Filas `(accion, ref, detalle)` de audit_log con tabla = 'backup' (lista vacia si la base no tiene esa tabla)."""
    con = sqlite3.connect(origen)
    try:
        try:
            return con.execute("SELECT accion, ref, detalle FROM audit_log WHERE tabla = 'backup' ORDER BY id").fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        con.close()


def _con_diez_copias(tmp_path):
    """Una base sencilla (origen) y una carpeta de respaldos con 10 copias viejas VALIDAS (el maximo)."""
    origen = str(tmp_path / "BaseDatosQA.db")
    _bd_simple(origen)
    carpeta = str(tmp_path / "respaldos_bd")
    os.makedirs(carpeta)
    nombres = []
    for i in range(MAX_RESPALDOS):
        n = _nombre(datetime(2026, 9, 1, 9, 0, 0) + timedelta(days=i))
        _tocar(carpeta, n)
        nombres.append(n)
    return origen, carpeta, sorted(nombres)


_LECTOR = r'''
import sqlite3, sys
c = sqlite3.connect(sys.argv[1], timeout=30, isolation_level=None)
c.execute("BEGIN")
cur = c.execute("SELECT id, valor FROM datos")
cur.fetchone()
print("listo", flush=True)
sys.stdin.read()
'''


@contextlib.contextmanager
def _lector_a_medio_leer(origen):
    """Otro PROCESO con una consulta a medio leer: retiene su foto vieja y deja el checkpoint a medias."""
    p = subprocess.Popen([sys.executable, "-c", _LECTOR, origen], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "listo"
        yield p
    finally:
        p.stdin.close()
        p.wait(timeout=15)


def _danar_ultima_pagina(ruta):
    with open(ruta, "r+b") as f:
        f.seek(os.path.getsize(ruta) - 4096)
        f.write(b"\xff" * 4096)


def _danar_con_basura(ruta):
    azar = random.Random(7)
    with open(ruta, "r+b") as f:
        f.seek(4096 * 3 + 100)
        f.write(bytes(azar.randrange(256) for _ in range(4096)))


# ----------------------------------------------------------------------------------------------- la foto consistente
class TestFotoConsistente:
    def test_e2_en_pequeno_la_copia_trae_todo_lo_confirmado_y_la_de_archivo_no(self, tmp_path):
        """El escenario E2 de M6, sin esperar 30 s: un lector en OTRO proceso con una consulta a medio leer, un escritor que sigue
        confirmando filas y un checkpoint que queda a medias. La copia por la API abre, pasa integrity_check y trae TODO lo
        confirmado; el CONTROL (la copia de archivo de antes) en la misma situacion sale dañada o incompleta."""
        origen, con = _bd_wal(tmp_path)
        try:
            with _lector_a_medio_leer(origen):
                for lote in range(5):
                    con.executemany("UPDATE datos SET valor = ? WHERE id = ?",
                                    [(f"nuevo {lote} {i}" * 20, i + 1) for i in range(0, 3000, 3)])
                    con.commit()
                con.execute("INSERT INTO datos (valor) VALUES ('ULTIMA FILA CONFIRMADA')")
                con.commit()
                total = con.execute("SELECT COUNT(*) FROM datos").fetchone()[0]
                con.execute("PRAGMA busy_timeout=50")
                ocupado = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
                assert ocupado == 1, "el escenario no se armo: el lector debia dejar el checkpoint a medias"

                control = str(tmp_path / "control_copia_de_archivo.db")
                shutil.copy2(origen, control)
                integridad, filas, ultima = _estado_de_la_copia(control)
                assert not (integridad == "ok" and filas == total and ultima == "ULTIMA FILA CONFIRMADA"), (
                    "CONTROL: la copia de archivo ya sale completa en este escenario; la prueba dejo de discriminar")

                ruta = respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "respaldos_bd"), ahora=AHORA)
        finally:
            con.close()
        assert ruta is not None
        assert _estado_de_la_copia(ruta) == ("ok", total, "ULTIMA FILA CONFIRMADA")

    def test_con_y_sin_checkpoint_la_copia_es_completa(self, tmp_path):
        """Sin ningun checkpoint (lo que vive solo en el -wal) la copia ya trae esa fila: no depende del orden del cierre."""
        origen, con = _bd_wal(tmp_path, filas=50)
        try:
            con.execute("INSERT INTO datos (valor) VALUES ('solo en el wal')")
            con.commit()
            assert os.path.getsize(origen + "-wal") > 0
            ruta = respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "respaldos_bd"), ahora=AHORA)
        finally:
            con.close()
        assert _estado_de_la_copia(ruta) == ("ok", 51, "solo en el wal")

    def test_no_quedan_provisionales_ni_laterales_y_abrir_la_copia_no_los_crea(self, tmp_path):
        origen, con = _bd_wal(tmp_path, filas=50)
        carpeta = str(tmp_path / "respaldos_bd")
        try:
            ruta = respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, ahora=AHORA)
        finally:
            con.close()
        assert sorted(n for n in os.listdir(carpeta) if n != respaldo.NOMBRE_LEEME_RESTAURAR) == [os.path.basename(ruta)]
        c = sqlite3.connect(ruta)
        c.execute("SELECT COUNT(*) FROM datos").fetchone()
        c.close()
        assert sorted(n for n in os.listdir(carpeta) if n != respaldo.NOMBRE_LEEME_RESTAURAR) == [os.path.basename(ruta)], "abrir y cerrar la copia no debe crear -wal ni -shm"

    def test_la_copia_queda_en_el_modo_normal_de_un_solo_archivo(self, tmp_path):
        origen, con = _bd_wal(tmp_path, filas=50)
        try:
            ruta = respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "respaldos_bd"), ahora=AHORA)
        finally:
            con.close()
        with open(ruta, "rb") as f:
            cabecera = f.read(100)
        assert (cabecera[18], cabecera[19]) == (1, 1), "la copia heredaria el modo WAL (2, 2) y dependeria de un -wal"

    def test_cada_respaldo_hecho_pasa_la_comprobacion(self, tmp_path):
        origen, con = _bd_wal(tmp_path, filas=200)
        carpeta = str(tmp_path / "respaldos_bd")
        try:
            rutas = []
            for i in range(3):
                con.execute("INSERT INTO datos (valor) VALUES (?)", (f"fila nueva {i}",))
                con.commit()
                rutas.append(respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, ahora=AHORA + timedelta(hours=i)))
        finally:
            con.close()
        assert [_estado_de_la_copia(r)[:2] for r in rutas] == [("ok", 201), ("ok", 202), ("ok", 203)]

    def test_un_provisional_ajeno_no_se_toca_ni_estorba(self, tmp_path):
        """H1 de la revision: el provisional de cada copia lleva un nombre PROPIO (`<respaldo>.<pid>-<aleatorio>.parcial`); uno ajeno -- de otro
        proceso que esta copiando AHORA, o resto de un cierre que se cayo -- ni estorba ni se borra. Borrarlo (lo que hacia el codigo
        anterior con el de su mismo nombre) era justo lo que dejaba un respaldo de 0 bytes cuando dos copias elegian el mismo nombre."""
        origen, con = _bd_wal(tmp_path, filas=50)
        carpeta = tmp_path / "respaldos_bd"
        carpeta.mkdir()
        ajeno = _nombre(AHORA) + ".parcial"                   # con el nombre que tenia el provisional antes de la revision
        _tocar(str(carpeta), ajeno, b"restos de otra copia")
        try:
            ruta = respaldar_bd(ruta_origen=origen, carpeta_destino=str(carpeta), ahora=AHORA)
        finally:
            con.close()
        assert _estado_de_la_copia(ruta)[:2] == ("ok", 50)
        assert sorted(n for n in os.listdir(str(carpeta)) if n != respaldo.NOMBRE_LEEME_RESTAURAR) == sorted([os.path.basename(ruta), ajeno])
        with open(os.path.join(str(carpeta), ajeno), "rb") as f:
            assert f.read() == b"restos de otra copia"

    def test_se_comprueba_antes_de_renombrar(self, tmp_path, monkeypatch):
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd_simple(origen, filas=100)
        eventos = []
        integridad_real, replace_real = respaldo._integridad, os.replace

        def integridad_espia(ruta):
            eventos.append(("integridad", os.path.basename(ruta)))
            return integridad_real(ruta)

        def replace_espia(origen_, destino_):
            eventos.append(("replace", os.path.basename(origen_), os.path.basename(destino_)))
            return replace_real(origen_, destino_)

        monkeypatch.setattr(respaldo, "_integridad", integridad_espia)
        monkeypatch.setattr(respaldo.os, "replace", replace_espia)
        ruta = respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"), ahora=AHORA)
        assert ruta is not None
        assert [e[0] for e in eventos] == ["integridad", "replace"]
        assert eventos[0][1].endswith(".parcial") and eventos[1][1].endswith(".parcial") and eventos[1][2].endswith(".db")

    def test_la_copia_se_hace_en_un_solo_paso(self):
        """`pages` fijaria varios pasos (otro escritor reiniciaria la copia): `backup` se llama sin `pages` (todo de una vez)."""
        arbol = ast.parse(inspect.getsource(respaldo))
        f = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "_copiar_con_api")
        llamadas = [n for n in ast.walk(f) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "backup"]
        assert len(llamadas) == 1
        assert len(llamadas[0].args) == 1 and not [k for k in llamadas[0].keywords if k.arg == "pages"]

    def test_la_copia_ya_no_es_una_copia_de_archivo(self):
        arbol = ast.parse(inspect.getsource(respaldo.respaldar_bd))
        llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("copy2", "copyfile", "copy")]
        assert not llamadas, "respaldar_bd no debe copiar el archivo .db tal cual (RB.1)"


# --------------------------------------------------------------- una copia que falla no cuenta como respaldo
class TestUnaCopiaQueFallaNoCuentaComoRespaldo:
    """Estas pruebas piden `max_copias=5` con 10 copias previas: si algo rotara por su cuenta aunque la copia falle, borraria 5."""

    def test_un_fallo_a_mitad_de_la_copia_no_deja_nada_ni_rota_ni_audita(self, tmp_path, monkeypatch):
        origen, carpeta, nombres = _con_diez_copias(tmp_path)

        def copia_que_falla(ruta_origen, ruta_parcial):
            with open(ruta_parcial, "wb") as f:
                f.write(b"\x00" * 5000)
            raise OSError("disco lleno (simulado)")

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_que_falla)
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert sorted(os.listdir(carpeta)) == nombres, "ni un archivo nuevo (ni provisional ni a revisar) y ninguna copia rotada"
        assert _auditoria_backup(origen) == []

    def test_una_copia_mala_con_el_origen_sano_se_descarta(self, tmp_path, monkeypatch):
        origen, carpeta, nombres = _con_diez_copias(tmp_path)

        def copia_basura(ruta_origen, ruta_parcial):
            with open(ruta_parcial, "wb") as f:
                f.write(b"esto no es una base de datos" * 300)

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_basura)
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert sorted(os.listdir(carpeta)) == nombres
        assert _auditoria_backup(origen) == []

    def test_una_copia_que_no_pasa_nunca_se_renombra_a_respaldo(self, tmp_path, monkeypatch):
        """Aunque la comprobacion falle, el nombre de respaldo no aparece (si apareciera, la rotacion borraria una buena)."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        def copia_basura(ruta_origen, ruta_parcial):
            with open(ruta_parcial, "wb") as f:
                f.write(b"basura" * 1000)

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_basura)
        respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA)
        assert respaldo._nombres_respaldo(carpeta) == nombres


# ------------------------------------------------- el provisional es de cada copia (H1 y H6 de la revision)
_HIJO_SIMULTANEO = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
from datetime import datetime
from services import respaldo
origen, carpeta, rondas = sys.argv[2], sys.argv[3], int(sys.argv[4])
resultados = []
for _ in range(rondas):
    r = respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, max_copias=100, ahora=datetime(2026, 10, 5, 12, 0, 0))
    resultados.append(os.path.basename(r) if r else None)
print(json.dumps(resultados))
'''


class TestElProvisionalEsDeCadaCopia:
    def test_cada_copia_lleva_su_propio_nombre_provisional(self):
        destino = "/carpeta/BaseDatosQA_2026-10-05_120000.db"
        a, b = respaldo._nombre_provisional(destino), respaldo._nombre_provisional(destino)
        assert a != b, "dos copias del mismo nombre de respaldo no pueden compartir el provisional"
        for nombre in (a, b):
            assert nombre.startswith(destino + ".") and nombre.endswith(respaldo.SUFIJO_PARCIAL)
            assert str(os.getpid()) in nombre
            assert respaldo._marca_y_contador(os.path.basename(nombre)) is None, "un provisional no puede contar como respaldo"

    def test_un_parcial_que_desaparece_entre_la_copia_y_la_comprobacion_no_cuenta_como_respaldo(self, tmp_path, monkeypatch):
        """H1: si el provisional desaparece (otro proceso, antivirus, limpieza) `sqlite3.connect` lo CREABA vacio, `integrity_check` daba
        `ok` y se renombraba un archivo de 0 bytes como respaldo valido, se auditaba y se rotaba una copia buena."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        copia_real = respaldo._copiar_con_api

        def copia_y_se_borra(ruta_origen, ruta_parcial):
            copia_real(ruta_origen, ruta_parcial)
            os.remove(ruta_parcial)

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_y_se_borra)
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert sorted(os.listdir(carpeta)) == nombres, "ni un archivo nuevo (y menos uno de 0 bytes) y ninguna copia rotada"
        assert _auditoria_backup(origen) == []

    def test_un_parcial_vacio_no_cuenta_como_respaldo(self, tmp_path, monkeypatch):
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        copia_real = respaldo._copiar_con_api

        def copia_y_se_vacia(ruta_origen, ruta_parcial):
            copia_real(ruta_origen, ruta_parcial)
            open(ruta_parcial, "wb").close()

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_y_se_vacia)
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert sorted(os.listdir(carpeta)) == nombres
        assert _auditoria_backup(origen) == []

    def test_la_comprobacion_no_crea_el_archivo_que_no_existe(self, tmp_path):
        ruta = str(tmp_path / "no_existe.db")
        estado, _ = respaldo._integridad(ruta)
        assert estado != respaldo.ESTADO_OK
        assert not os.path.exists(ruta), "`sqlite3.connect` crea el archivo vacio: la comprobacion no puede dejarlo ahi"
        vacio = tmp_path / "vacio.db"
        vacio.write_bytes(b"")
        assert respaldo._integridad(str(vacio))[0] == respaldo.ESTADO_DEFECTO

    def test_un_archivo_que_desaparece_entre_medir_y_conectar_no_se_da_por_bueno(self, tmp_path, monkeypatch):
        """B-04 de la segunda revision: si el provisional desaparece (o lo reemplaza un archivo de 0 bytes) DESPUES de medirlo y ANTES de conectar, `connect` lo CREA
        vacio y `integrity_check` da `ok`; se renombraba como respaldo valido, se auditaba como exito y se rotaba la copia buena mas vieja. Un archivo que sigue
        en 0 bytes tras la comprobacion nunca fue una base."""
        ruta = str(tmp_path / "copia.parcial")
        _bd_simple(ruta, filas=100)
        medir_real = respaldo.os.path.getsize
        llamadas = []

        def mide_y_desaparece(p):
            llamadas.append(p)
            tamano = medir_real(p)
            if len(llamadas) == 1:
                os.remove(p)                      # el otro proceso lo borra justo despues de que lo medimos
            return tamano

        monkeypatch.setattr(respaldo.os.path, "getsize", mide_y_desaparece)
        estado, _ = respaldo._integridad(ruta)
        assert estado != respaldo.ESTADO_OK

    def test_un_origen_que_desaparece_no_dispara_la_alarma_ni_se_recrea(self, tmp_path, monkeypatch):
        """Un origen AUSENTE no es un origen dañado (no concluyente): la alarma de ATENCION audita en la propia base de origen, y con el
        origen ausente `sqlite3.connect` CREARIA una base nueva en su lugar."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        copia_real = respaldo._copiar_con_api

        def copia_y_desaparece_todo(ruta_origen, ruta_parcial):
            copia_real(ruta_origen, ruta_parcial)
            os.remove(ruta_parcial)
            os.remove(ruta_origen)

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_y_desaparece_todo)
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert not os.path.exists(origen), "se habria creado una base nueva en el sitio del origen"
        assert sorted(os.listdir(carpeta)) == nombres

    def test_dos_copias_que_eligen_el_mismo_nombre_no_se_pisan(self, tmp_path, monkeypatch):
        """Intercalado determinista: mientras la copia A esta entre copiar y comprobar, entra otra copia B que decide el MISMO nombre de
        respaldo (el nombre se decide antes de copiar). Con un provisional compartido, B borraba el de A."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd_simple(origen)
        carpeta = str(tmp_path / "respaldos_bd")
        copia_real = respaldo._copiar_con_api
        estado = {"dentro": False, "B": None}

        def copia_y_deja_entrar_a_otra(ruta_origen, ruta_parcial):
            copia_real(ruta_origen, ruta_parcial)
            if not estado["dentro"]:
                estado["dentro"] = True
                estado["B"] = respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, ahora=AHORA)

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_y_deja_entrar_a_otra)
        a = respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, ahora=AHORA)
        b = estado["B"]
        destino = os.path.join(carpeta, _nombre(AHORA))
        assert a == destino and b == destino, "las dos copias llegan a buen puerto (cada una comprueba la suya antes de renombrar)"
        assert os.path.getsize(destino) > 0
        assert _estado_de_la_copia(destino)[:2] == ("ok", 3000)
        assert sorted(n for n in os.listdir(carpeta) if n != respaldo.NOMBRE_LEEME_RESTAURAR) == [_nombre(AHORA)], "ningun provisional queda atras"

    def test_varios_procesos_a_la_vez_no_dejan_archivos_vacios_ni_errores(self, tmp_path):
        """PRUEBA DE HUMO (no fija una carrera concreta: eso lo hace el intercalado de arriba): 3 procesos llamando a `respaldar_bd` a la
        vez, con el mismo `ahora` y la misma carpeta, repetido; todo lo que se devuelve existe, no esta vacio y pasa la comprobacion."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd_simple(origen, filas=8000)
        carpeta = str(tmp_path / "respaldos_bd")
        os.makedirs(carpeta)
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        hijos = [subprocess.Popen([sys.executable, "-c", _HIJO_SIMULTANEO, RAIZ_REPO, origen, carpeta, "4"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=RAIZ_REPO) for _ in range(3)]
        salidas = []
        for h in hijos:
            try:
                salida, error = h.communicate(timeout=LIMITE_S * 2)
            except subprocess.TimeoutExpired:
                h.kill()
                pytest.fail("un proceso hijo no termino (cierre colgado)")
            assert h.returncode == 0, error[-1500:]
            assert "disk I/O error" not in salida + error and "readonly" not in (salida + error).lower()
            salidas.append(json.loads([l for l in salida.strip().splitlines() if l.strip()][-1]))
        for nombre in {n for devueltos in salidas for n in devueltos if n}:
            ruta = os.path.join(carpeta, nombre)
            assert os.path.getsize(ruta) > 0, nombre
            assert _estado_de_la_copia(ruta)[0] == "ok", nombre
        for archivo in (n for n in os.listdir(carpeta) if n != respaldo.NOMBRE_LEEME_RESTAURAR):      # RS.2: el LEEME_RESTAURAR.txt no es un respaldo
            assert respaldo._marca_y_contador(archivo) is not None, f"quedo algo que no es un respaldo: {archivo}"
            assert os.path.getsize(os.path.join(carpeta, archivo)) > 0, archivo

    def test_una_copia_que_falla_a_medias_no_deja_el_journal_ni_el_parcial(self, tmp_path, monkeypatch):
        """H6: un disco lleno a mitad de la copia deja un `<provisional>-journal` que nada limpiaba ni contaba."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)

        def copia_que_falla(ruta_origen, ruta_parcial):
            for sufijo in ("", "-journal", "-wal", "-shm"):
                with open(ruta_parcial + sufijo, "wb") as f:
                    f.write(b"\x00" * 2000)
            raise OSError("disco lleno (simulado)")

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_que_falla)
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert sorted(os.listdir(carpeta)) == nombres, "ni el provisional ni sus laterales (`-journal`, `-wal`, `-shm`)"


# ------------------------------------------------------------------------------ el origen esta dañado
def _bd_con_indice(ruta, filas=200):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.execute("CREATE INDEX ix_datos_valor ON datos(valor)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"clave_{i * 10:05d}",) for i in range(filas)])
    con.commit()
    con.close()


def _danar_clave_de_indice(ruta):
    """Cambia UNA clave del indice por otra del mismo largo y del mismo orden (`clave_01010` -> `clave_01011`): la estructura de la
    pagina no cambia, asi que `quick_check` no la ve; solo `integrity_check` compara el indice con la tabla (F-04 de la revision)."""
    con = sqlite3.connect(ruta)
    raiz = con.execute("SELECT rootpage FROM sqlite_master WHERE name = 'ix_datos_valor'").fetchone()[0]
    tam = con.execute("PRAGMA page_size").fetchone()[0]
    con.close()
    with open(ruta, "r+b") as f:
        f.seek((raiz - 1) * tam)
        pagina = bytearray(f.read(tam))
        posicion = pagina.find(b"clave_01010")
        assert posicion >= 0, "la clave no esta en la pagina raiz del indice (la base de prueba es mas grande de lo previsto)"
        pagina[posicion:posicion + 11] = b"clave_01011"
        f.seek((raiz - 1) * tam)
        f.write(bytes(pagina))


class TestOrigenDanado:
    @pytest.mark.parametrize("danar", [_danar_ultima_pagina, _danar_con_basura], ids=["ultima_pagina", "basura_en_pagina_4"])
    def test_se_conserva_una_copia_aparte_se_audita_y_no_se_rota_nada(self, tmp_path, danar):
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        danar(origen)
        tam_antes = os.path.getsize(origen)       # la fila de auditoria agranda el origen DESPUES de la copia
        assert respaldo._integridad(origen)[0] == respaldo.ESTADO_DEFECTO, "la precondicion: el defecto tiene que verse"

        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None

        archivos = sorted(os.listdir(carpeta))
        nuevos = [a for a in archivos if a not in nombres]
        assert len(nuevos) == 1 and nuevos[0] == _nombre(AHORA) + ".revisar", nuevos
        assert respaldo._marca_y_contador(nuevos[0]) is None, "la copia a revisar no puede contar como respaldo"
        assert [a for a in archivos if a in nombres] == nombres, "ninguna copia buena se rota cuando el que esta mal es el origen"
        filas = _auditoria_backup(origen)
        assert len(filas) == 1
        accion, ref, detalle = filas[0]
        assert ref == nuevos[0] and "ATENCION" in detalle and "NO hecho" in detalle and nuevos[0] in detalle
        assert os.path.getsize(os.path.join(carpeta, nuevos[0])) == tam_antes, "la copia a revisar es la base entera, no un trozo"

    def test_un_origen_que_no_es_una_base_sqlite_tambien_deja_la_copia_aparte(self, tmp_path):
        carpeta = tmp_path / "respaldos_bd"
        carpeta.mkdir()
        origen = tmp_path / "BaseDatosQA.db"
        origen.write_bytes(b"esto no es una base de datos " * 400)
        assert respaldar_bd(ruta_origen=str(origen), carpeta_destino=str(carpeta), ahora=AHORA) is None
        assert sorted(os.listdir(str(carpeta))) == [_nombre(AHORA) + ".revisar"]

    def test_a_lo_sumo_tres_copias_a_revisar_y_la_primera_se_conserva(self, tmp_path):
        """H4 de la revision: se conserva la PRIMERA copia (la mas cercana al momento del daño, la que mas vale) y las dos mas
        recientes; antes se conservaban solo las 3 mas recientes y la primera se perdia a los 3 cierres siguientes, el mismo dia."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        _danar_con_basura(origen)
        for i in range(5):
            respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA + timedelta(minutes=i))
        a_revisar = sorted(a for a in os.listdir(carpeta) if a.endswith(".revisar"))
        assert len(a_revisar) == MAX_COPIAS_A_REVISAR
        assert a_revisar == [_nombre(AHORA + timedelta(minutes=i)) + ".revisar" for i in (0, 3, 4)], "la primera y las mas recientes"
        assert sorted(a for a in os.listdir(carpeta) if a in nombres) == nombres

    def test_con_una_copia_valida_de_otro_equipo_adelantada_las_copias_a_revisar_no_se_pisan(self, tmp_path):
        """H4 (omision del revisor, confirmada por el escéptico): el nombre de la copia aparte salia del nombre que habria tenido el
        respaldo, que con una copia valida de otro equipo con el reloj adelantado se REPITE en cada cierre: cada cierre pisaba la
        anterior. Ahora sale de la hora de ESTE equipo."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        _tocar(carpeta, _nombre(AHORA + timedelta(days=1)))             # otro equipo, con el reloj un dia adelantado
        _danar_con_basura(origen)
        for i in range(3):
            respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, max_copias=50, ahora=AHORA + timedelta(minutes=i))
        a_revisar = sorted(a for a in os.listdir(carpeta) if a.endswith(".revisar"))
        assert a_revisar == [_nombre(AHORA + timedelta(minutes=i)) + ".revisar" for i in range(3)]

    def test_un_indice_inconsistente_se_ve_con_integrity_check_y_no_con_quick_check(self, tmp_path):
        """F-04 de la revision: la precondicion que justifica pedir `integrity_check` y no `quick_check` en la comprobacion."""
        ruta = str(tmp_path / "indice.db")
        _bd_con_indice(ruta)
        _danar_clave_de_indice(ruta)
        con = sqlite3.connect(ruta)
        try:
            assert con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert con.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
        finally:
            con.close()

    def test_un_origen_con_el_indice_inconsistente_no_se_acepta_como_respaldo(self, tmp_path):
        """F-04: con `quick_check` en vez de `integrity_check` esta copia (indice con una clave cambiada) se aceptaba como respaldo
        valido, se auditaba como exito y la rotacion borraba copias buenas; se perdian la alarma y la copia aparte."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        os.remove(origen)
        _bd_con_indice(origen)
        _danar_clave_de_indice(origen)
        assert respaldo._integridad(origen)[0] == respaldo.ESTADO_DEFECTO
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        archivos = sorted(os.listdir(carpeta))
        assert [a for a in archivos if a in nombres] == nombres
        assert [a for a in archivos if a not in nombres] == [_nombre(AHORA) + ".revisar"]
        assert "ATENCION" in _auditoria_backup(origen)[0][2]

    def test_solo_las_copias_a_revisar_propias_cuentan(self, tmp_path):
        """F-09: `_nombres_a_revisar` solo mira `<nombre de respaldo>.revisar`; un `.revisar` ajeno ni cuenta para el tope ni se borra."""
        carpeta = str(tmp_path)
        propios = [_nombre(AHORA) + ".revisar", _nombre(AHORA, 2) + ".revisar"]
        ajenos = ["notas.revisar", "AAA.revisar", "BaseDatosQA_Rebuild_14-09-2026.db.revisar", _nombre(AHORA) + ".parcial",
                  _nombre(AHORA), "otra.txt"]
        for n in propios + ajenos:
            _tocar(carpeta, n)
        assert respaldo._nombres_a_revisar(carpeta) == sorted(propios)

    def test_un_revisar_ajeno_no_entra_en_el_tope_ni_se_borra(self, tmp_path):
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        _tocar(carpeta, "notas.revisar")
        _tocar(carpeta, "AAA.revisar")
        _danar_con_basura(origen)
        for i in range(5):
            respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA + timedelta(minutes=i))
        archivos = os.listdir(carpeta)
        assert "notas.revisar" in archivos and "AAA.revisar" in archivos
        propios = [a for a in archivos if a.endswith(".revisar") and a.startswith("BaseDatosQA_2026-10-05_")]
        assert len(propios) == MAX_COPIAS_A_REVISAR

    def test_la_copia_recien_hecha_no_se_borra_aunque_su_nombre_quede_en_medio(self, tmp_path):
        """Con el reloj de este equipo atrasado respecto al de otros que tambien dejaron copias a revisar, el nombre de la nueva queda en
        el MEDIO de la lista: ni es la primera ni esta entre las ultimas, y se borraria al instante."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        for dias in (-1, 1, 2, 3):
            _tocar(carpeta, _nombre(AHORA + timedelta(days=dias)) + ".revisar")
        _danar_con_basura(origen)
        respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA)
        assert os.path.exists(os.path.join(carpeta, _nombre(AHORA) + ".revisar")), "la copia que se acaba de hacer tiene que quedar"

    def test_un_error_inesperado_al_comprobar_no_es_un_defecto(self, tmp_path, monkeypatch):
        """F-09: lo que no se sabe interpretar no dispara la alarma (seria una falsa alarma: la copia aparte y la fila de ATENCION)."""
        ruta = str(tmp_path / "base.db")
        _bd_simple(ruta, filas=50)

        def boom(*a, **k):
            raise RuntimeError("fallo inesperado")

        monkeypatch.setattr(respaldo.sqlite3, "connect", boom)
        assert respaldo._integridad(ruta)[0] == respaldo.ESTADO_NO_CONCLUYENTE


# ------------------------------------------- una fila que viola una restriccion no es un daño (B-02 de la segunda revision)
def _bd_con_filas_que_violan_un_check(ruta, filas_malas=1):
    """Una base FUNCIONAL con filas que violan un CHECK, insertadas con `ignore_check_constraints` como lo haria otra herramienta."""
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE medidas (id INTEGER PRIMARY KEY, valor INTEGER CHECK (valor >= 0), texto TEXT)")
    con.executemany("INSERT INTO medidas (valor, texto) VALUES (?, ?)", [(i, f"fila {i}") for i in range(500)])
    con.execute("PRAGMA ignore_check_constraints = ON")
    con.executemany("INSERT INTO medidas (valor, texto) VALUES (?, ?)", [(-1, f"mala {i}") for i in range(filas_malas)])
    con.commit()
    con.close()


def _bd_con_una_fila_que_viola_un_not_null(ruta):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE medidas (id INTEGER PRIMARY KEY, nombre TEXT)")
    con.executemany("INSERT INTO medidas (nombre) VALUES (?)", [(f"n{i}",) for i in range(200)])
    con.execute("INSERT INTO medidas (nombre) VALUES (NULL)")
    con.commit()
    con.execute("PRAGMA writable_schema = ON")
    con.execute("UPDATE sqlite_master SET sql = 'CREATE TABLE medidas (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL)' WHERE name = 'medidas'")
    con.commit()
    con.close()


class TestFilaQueViolaUnaRestriccion:
    """`PRAGMA integrity_check` no solo detecta daño: tambien verifica CHECK y NOT NULL fila por fila. Una fila infractora no daña la base (se abre, se lee, se
    escribe y se copia bien); tomarla por `defecto` apagaba TODOS los respaldos y frenaba el respaldo previo a la migracion (F1)."""

    def test_un_check_violado_se_distingue_de_un_daño(self, tmp_path):
        ruta = str(tmp_path / "b.db")
        _bd_con_filas_que_violan_un_check(ruta)
        estado, detalle = respaldo._integridad(ruta)
        assert estado == respaldo.ESTADO_OK_CON_AVISO and "CHECK constraint failed" in detalle

    def test_un_not_null_violado_se_distingue_de_un_daño(self, tmp_path):
        ruta = str(tmp_path / "b.db")
        _bd_con_una_fila_que_viola_un_not_null(ruta)
        estado, detalle = respaldo._integridad(ruta)
        assert estado == respaldo.ESTADO_OK_CON_AVISO and "NULL value in" in detalle

    def test_el_respaldo_se_hace_se_rota_y_deja_un_aviso_no_una_alarma(self, tmp_path):
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        os.remove(origen)
        _bd_con_filas_que_violan_un_check(origen)
        ruta = respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA)
        assert ruta is not None and os.path.basename(ruta) == _nombre(AHORA), "el respaldo previo a una migracion (F1) y el de cada cierre salen"
        assert [a for a in os.listdir(carpeta) if a.endswith(".revisar")] == [], "no hay alarma ni copia a revisar: la estructura esta bien"
        assert len(respaldo._nombres_respaldo(carpeta)) == 5, "rota como siempre"
        con = sqlite3.connect(ruta)
        try:
            assert con.execute("SELECT COUNT(*) FROM medidas WHERE valor < 0").fetchone()[0] == 1, "la copia es fiel: trae tambien la fila infractora"
        finally:
            con.close()
        filas = _auditoria_backup(origen)
        assert len(filas) == 2, filas
        assert "AVISO" in filas[1][2] and "ATENCION" not in filas[0][2] + filas[1][2]

    def test_con_tantas_filas_infractoras_que_se_llena_el_tope_no_se_afirma_que_sean_solo_restricciones(self, tmp_path):
        ruta = str(tmp_path / "b.db")
        _bd_con_filas_que_violan_un_check(ruta, filas_malas=respaldo._TOPE_MENSAJES_INTEGRIDAD + 500)
        assert respaldo._integridad(ruta)[0] == respaldo.ESTADO_DEFECTO

    def test_un_daño_de_indice_no_se_esconde_detras_de_muchas_filas_infractoras(self, tmp_path):
        """`integrity_check` corta en 100 mensajes por defecto: con 200 infracciones, un daño de indice que se emite DESPUES quedaba fuera de
        la lista y se clasificaba 'solo restricciones' (medido por el esceptico)."""
        ruta = str(tmp_path / "b.db")
        con = sqlite3.connect(ruta)
        con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT, n INTEGER CHECK (n >= 0))")
        con.execute("CREATE INDEX ix_datos_valor ON datos(valor)")
        con.execute("PRAGMA ignore_check_constraints = ON")
        con.executemany("INSERT INTO datos (valor, n) VALUES (?, -1)", [(f"clave_{i * 10:05d}",) for i in range(200)])
        con.commit()
        con.close()
        _danar_clave_de_indice(ruta)
        assert respaldo._integridad(ruta)[0] == respaldo.ESTADO_DEFECTO

    def test_el_daño_estructural_sigue_siendo_defecto(self, tmp_path):
        ruta = str(tmp_path / "b.db")
        _bd_simple(ruta)
        _danar_con_basura(ruta)
        assert respaldo._integridad(ruta)[0] == respaldo.ESTADO_DEFECTO


class TestComprobacionSinMotivoDeAlarma:
    def test_un_error_al_medir_el_archivo_no_es_un_defecto(self, tmp_path, monkeypatch):
        """B-05 de la segunda revision: la rama `OSError` al medir (red caida, permiso denegado) es la que evita que una caida de la red durante
        el cierre cree una `.revisar` y una fila ATENCION falsas; ninguna prueba la cubria."""
        ruta = str(tmp_path / "base.db")
        _bd_simple(ruta, filas=50)

        def sin_acceso(p):
            raise PermissionError(13, "sin acceso al recurso de red")

        monkeypatch.setattr(respaldo.os.path, "getsize", sin_acceso)
        assert respaldo._integridad(ruta)[0] == respaldo.ESTADO_NO_CONCLUYENTE


# ------------------------------------------------ caminos de error del ultimo recurso (C-2 y C-3 de la segunda revision)
def _usuarios_en_auditoria_backup(origen):
    con = sqlite3.connect(origen)
    try:
        return [u for (u,) in con.execute("SELECT usuario FROM audit_log WHERE tabla = 'backup' ORDER BY id")]
    finally:
        con.close()


class TestCaminosDeError:
    def test_una_comprobacion_no_concluyente_de_la_copia_no_la_promueve_a_respaldo(self, tmp_path, monkeypatch):
        """C-2: error de E/S sobre la carpeta de red, sin acceso al provisional, base ocupada... Con `!= DEFECTO` en lugar de `== OK`, una copia que no se
        pudo comprobar se renombraba, rotaba y auditaba como respaldo, contra el contrato de RB.1 ('solo se renombra si la comprobacion da ok')."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        real = respaldo._integridad
        monkeypatch.setattr(respaldo, "_integridad",
                            lambda r: (respaldo.ESTADO_NO_CONCLUYENTE, "E/S simulado") if r.endswith(respaldo.SUFIJO_PARCIAL) else real(r))
        assert respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert sorted(os.listdir(carpeta)) == nombres, "ni un respaldo nuevo, ni provisional, ni copia aparte; ninguna rotada"
        assert _auditoria_backup(origen) == []

    def test_si_no_se_puede_guardar_la_copia_aparte_el_aviso_se_audita_igual_y_a_nombre_de_quien_cerro(self, tmp_path, monkeypatch):
        """C-3a: es el ultimo recurso (origen dañado y disco lleno): no puede lanzar ni perder el aviso ni el nombre de quien cerro."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        _danar_con_basura(origen)

        def copia_que_falla(ruta_origen, ruta_parcial):
            raise OSError(errno.ENOSPC, "No space left on device")

        monkeypatch.setattr(respaldo, "_copiar_con_api", copia_que_falla)
        monkeypatch.setattr(respaldo.shutil, "copy2", copia_que_falla)
        assert respaldar_bd(usuario="Dra. Mesa", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA) is None
        assert sorted(os.listdir(carpeta)) == nombres, "ninguna .revisar: no se pudo guardar"
        filas = _auditoria_backup(origen)
        assert len(filas) == 1 and "ATENCION" in filas[0][2] and "No se pudo conservar ninguna copia aparte" in filas[0][2], filas
        assert _usuarios_en_auditoria_backup(origen) == ["Dra. Mesa"]

    def test_si_no_se_puede_rotar_un_respaldo_viejo_el_nuevo_se_devuelve_y_se_audita(self, tmp_path, monkeypatch):
        """C-3b: en Windows un antivirus u otro equipo con el archivo abierto impide borrarlo. La rotacion falla, pero el respaldo nuevo YA esta hecho: se
        devuelve y se audita; si la excepcion subiera, el cierre dejaria el respaldo sin fila de auditoria (y, con RB.2, sin `.hecha`: otra copia en la franja)."""
        origen, carpeta, nombres = _con_diez_copias(tmp_path)
        real = os.remove

        def negado(p, *a, **k):
            if os.path.basename(str(p)).startswith(PREFIJO_RESPALDO) and not str(p).endswith(respaldo.SUFIJO_PARCIAL):
                raise PermissionError(errno.EACCES, "archivo en uso")
            return real(p, *a, **k)

        monkeypatch.setattr(os, "remove", negado)
        ruta = respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, max_copias=5, ahora=AHORA)
        assert ruta is not None and os.path.basename(ruta) == _nombre(AHORA)
        assert len(_auditoria_backup(origen)) == 1
        assert len(respaldo._nombres_respaldo(carpeta)) == 11, "no se pudo rotar ninguna: se conservan todas"


# ----------------------------------------------------------------- el origen esta ocupado: sin alarma y sin colgarse
_HIJO_OCUPADO = r'''
import json, os, sqlite3, sys
sys.path.insert(0, sys.argv[1])
from datetime import datetime
from services import respaldo
origen, carpeta = sys.argv[2], sys.argv[3]
respaldo.ESPERA_MAXIMA_COPIA_S = 0.5
otro = sqlite3.connect(origen, isolation_level=None)
otro.execute("BEGIN EXCLUSIVE")
r = respaldo.respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, ahora=datetime(2026, 10, 5, 12, 0, 0))
otro.execute("ROLLBACK")
print(json.dumps(r))
'''


# Un candado que se suelta a los 0.6 s. El hijo baja la espera de la conexion para que su `busy_timeout` no absorba el candado: lo que se
# prueba es la fase de reintento de la copia. (F-03 de la revision, anotado: aqui la base esta en el modo normal; en WAL, el de produccion,
# un `BEGIN EXCLUSIVE` ajeno no bloquea la lectura de la copia -- la cota protege a una base que SI se bloquea, p. ej. en el modo normal.)
_HIJO_OCUPADO_TRANSITORIO = r'''
import json, os, sqlite3, sys, threading
sys.path.insert(0, sys.argv[1])
from datetime import datetime
from services import respaldo
origen, carpeta = sys.argv[2], sys.argv[3]
respaldo._ESPERA_CONEXION_S = 0.05
respaldo.ESPERA_MAXIMA_COPIA_S = 8
otro = sqlite3.connect(origen, isolation_level=None, check_same_thread=False)
otro.execute("BEGIN EXCLUSIVE")
threading.Timer(0.6, lambda: otro.execute("ROLLBACK")).start()
r = respaldo.respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, ahora=datetime(2026, 10, 5, 12, 0, 0))
print(json.dumps(r))
'''


class TestOrigenOcupado:
    def test_una_base_ocupada_no_cuelga_el_cierre_ni_se_toma_por_dañada(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd_simple(origen, filas=500)
        carpeta = str(tmp_path / "respaldos_bd")
        os.makedirs(carpeta)
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        try:
            r = subprocess.run([sys.executable, "-c", _HIJO_OCUPADO, RAIZ_REPO, origen, carpeta],
                               capture_output=True, text=True, timeout=LIMITE_S, env=env, cwd=RAIZ_REPO)
        except subprocess.TimeoutExpired:
            pytest.fail(f"respaldar_bd NO TERMINA en {LIMITE_S} s con la base de origen ocupada: `Connection.backup` reintenta sin fin")
        assert r.returncode == 0, r.stderr[-1500:]
        assert json.loads([l for l in r.stdout.strip().splitlines() if l.strip()][-1]) is None
        assert os.listdir(carpeta) == [], "ni respaldo, ni provisional, ni copia a revisar: una base ocupada no es un defecto"
        assert _auditoria_backup(origen) == []

    def test_la_cota_de_espera_de_produccion_esta_fijada(self):
        """F-02 de la revision: la prueba de arriba baja la cota a 0.5 s, asi que su valor de produccion no lo fijaba nadie. La espera de la
        conexion (el `busy_timeout`) debe ser MENOR que la cota (si no, la fase de reintento no existiria) y la cota no puede crecer sin
        limite: es lo que un cierre espera, con la interfaz congelada, antes de rendirse."""
        assert respaldo._ESPERA_CONEXION_S < respaldo.ESPERA_MAXIMA_COPIA_S <= 60

    def test_un_candado_transitorio_se_espera_y_la_copia_se_hace(self, tmp_path):
        """F-02: un candado que se suelta a los 0.6 s NO debe hacer rendirse a la copia: tras el `busy_timeout` de la conexion (aqui
        50 ms para que no lo absorba) `Connection.backup` reintenta, y el corte solo opera pasada la cota (aqui 8 s). Se rendiria al primer
        `SQLITE_BUSY` si el corte no esperara."""
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd_simple(origen, filas=500)
        carpeta = str(tmp_path / "respaldos_bd")
        os.makedirs(carpeta)
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        try:
            r = subprocess.run([sys.executable, "-c", _HIJO_OCUPADO_TRANSITORIO, RAIZ_REPO, origen, carpeta],
                               capture_output=True, text=True, timeout=LIMITE_S, env=env, cwd=RAIZ_REPO)
        except subprocess.TimeoutExpired:
            pytest.fail("respaldar_bd no termino con un candado transitorio")
        assert r.returncode == 0, r.stderr[-1500:]
        devuelto = json.loads([l for l in r.stdout.strip().splitlines() if l.strip()][-1])
        assert devuelto is not None and os.path.basename(devuelto) == _nombre(datetime(2026, 10, 5, 12, 0, 0))
        assert _estado_de_la_copia(devuelto)[:2] == ("ok", 500)
        assert sorted(n for n in os.listdir(carpeta) if n != respaldo.NOMBRE_LEEME_RESTAURAR) == [os.path.basename(devuelto)]


# ---------------------------------------------------------------------------------- las pruebas que ya existian
class TestLoQueNoCambia:
    def test_el_respaldo_previo_a_una_migracion_conserva_la_firma(self):
        """`F1` y `F6` llaman a `respaldar_bd` con estos argumentos con nombre: la firma solo AÑADE `ahora` al final."""
        params = list(inspect.signature(respaldar_bd).parameters)
        assert params[:5] == ["usuario", "ruta_origen", "carpeta_destino", "max_copias", "motivo"]
        assert params[5] == "ahora"

    def test_un_respaldo_hecho_queda_auditado_una_vez(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd_simple(origen, filas=100)
        ruta = respaldar_bd(usuario="Fisico", ruta_origen=origen, carpeta_destino=str(tmp_path / "r"), ahora=AHORA)
        filas = _auditoria_backup(origen)
        assert len(filas) == 1 and filas[0][1] == os.path.basename(ruta)
        assert "ATENCION" not in filas[0][2]
