"""RS.2 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, C1 de la auditoria): restaurar un respaldo sin que el `-wal` viejo lo deshaga.

V4 midio que copiar un respaldo encima de `BaseDatosQA.db` dejando al lado un `BaseDatosQA.db-wal` con contenido NO restaura: SQLite aplica ese `-wal` viejo (595 filas de `audit_log` en vez de
las 554 del respaldo, con `integrity_check` en ok y sin aviso) o deja la base danada; moviendo antes `-wal` y `-shm`, 14 de 14 controles restauraban bien. Un `-wal` con contenido queda tras una
caida o un cierre forzado (3 de 14 `-wal` de las carpetas del fisico lo tenian). El `RUNBOOK_MIGRAR_BD.md` no lo decia y una de sus frases («al cerrar, la app deja el `.db` completo») es falsa tras
«Inicio».

Ahora `respaldar_bd` deja UNA vez en la carpeta de respaldos un `LEEME_RESTAURAR.txt` de cuatro lineas con el procedimiento (cerrar la app, mover los tres archivos a otra carpeta sin borrarlos,
copiar el respaldo) y el RUNBOOK se corrige en esas tres frases. La prueba reproduce el caso de V4 con SQLite de verdad y comprueba que seguir el procedimiento restaura EXACTAMENTE el respaldo.

Revision de la tarea (dos revisores escepticos, hallazgos reproducidos): el texto dice «si existen» para el `-wal` y el `-shm` (tras un cierre limpio SQLite los borra), avisa de que lo guardado
despues del respaldo elegido no estara y aclara cual es «la carpeta de la base de datos»; el LEEME no se escribe a medias (si la escritura falla no queda un archivo de 0 bytes, y uno que ya lo
fuera se rehace); y una prueba EJECUTA el texto entregado (mueve y copia lo que sus pasos dicen, en el orden en que lo dicen): con los pasos invertidos o sin copiar el respaldo, restaurar deja
la base sin archivo. El LEEME tambien aparece en `respaldos_bd/pre_migracion/` (el respaldo previo a una migracion usa la misma funcion).

Sobre el rojo contra el codigo anterior: las pruebas del LEEME caen por `AttributeError` (`NOMBRE_LEEME_RESTAURAR` no existe en la base) y la del RUNBOOK por su aserción; la de la restauracion
ingenua es el CONTROL que demuestra que el defecto es real (no cae contra nada: describe SQLite).
"""
import errno
import os
import re
import shutil
import sqlite3

import pytest

import services.respaldo as respaldo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIMBOLOS_PROHIBIDOS = "✓✗✔✘❌✅⚠"        # DA-18: ni chulito ni equis ni advertencia


def _crear_bd(ruta, filas=5):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i}",) for i in range(filas)])
    con.commit()
    con.close()


@pytest.fixture
def origen(tmp_path):
    ruta = str(tmp_path / "BaseDatosQA.db")
    _crear_bd(ruta)
    return ruta


def _leeme(carpeta):
    return os.path.join(carpeta, respaldo.NOMBRE_LEEME_RESTAURAR)


class TestElLeemeDeLaCarpetaDeRespaldos:

    def test_el_primer_respaldo_lo_deja_con_el_procedimiento_en_cinco_lineas(self, tmp_path, origen):
        carpeta = str(tmp_path / "respaldos")
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta) is not None
        texto = open(_leeme(carpeta), encoding="utf-8").read()
        assert len(texto.splitlines()) == 5, texto
        for clave in ("BaseDatosQA.db", "BaseDatosQA.db-wal", "BaseDatosQA.db-shm", "Cierre", "no los borre", "otra carpeta", "si existen", "respaldos_bd", "despues de la fecha del respaldo"):
            assert clave in texto, clave

    def test_tambien_lo_deja_el_respaldo_previo_a_una_migracion(self, tmp_path, origen):
        """El respaldo de F1 usa `respaldos_bd/pre_migracion/`: el LEEME tambien aparece ahi, y su frase «la que contiene la carpeta respaldos_bd» sigue senalando la carpeta de la base."""
        carpeta = str(tmp_path / "respaldos_bd" / "pre_migracion")
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta) is not None
        assert os.path.isfile(_leeme(carpeta))

    def test_si_la_escritura_falla_no_queda_un_leeme_de_cero_bytes(self, tmp_path, origen, monkeypatch):
        """Revision (PROD-5): el archivo se crea de forma exclusiva y despues se escribe; si la escritura falla (disco lleno) quedaba de 0 bytes y, al existir, nunca se reescribia."""
        carpeta = str(tmp_path / "respaldos")
        real = os.write

        def disco_lleno(fd, datos):
            if datos.startswith(b"COMO RESTAURAR"):
                raise OSError(errno.ENOSPC, "No queda espacio en el dispositivo")
            return real(fd, datos)
        monkeypatch.setattr(respaldo.os, "write", disco_lleno)
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta) is not None
        assert not os.path.exists(_leeme(carpeta)), "un LEEME vacio no debe quedar"
        monkeypatch.setattr(respaldo.os, "write", real)
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta)
        assert open(_leeme(carpeta), encoding="utf-8").read() == respaldo.TEXTO_LEEME_RESTAURAR, "el siguiente respaldo lo escribe"

    def test_un_leeme_que_ya_esta_vacio_se_rehace(self, tmp_path, origen):
        carpeta = str(tmp_path / "respaldos")
        os.makedirs(carpeta)
        open(_leeme(carpeta), "w").close()
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta)
        assert open(_leeme(carpeta), encoding="utf-8").read() == respaldo.TEXTO_LEEME_RESTAURAR

    def test_es_texto_simple_sin_simbolos(self, tmp_path, origen):
        carpeta = str(tmp_path / "respaldos")
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta)
        texto = open(_leeme(carpeta), "rb").read()
        assert all(b < 128 for b in texto), "ASCII: se abre igual con cualquier editor"
        assert not any(s in texto.decode("ascii") for s in SIMBOLOS_PROHIBIDOS)

    def test_el_cierre_de_la_app_tambien_lo_deja(self, tmp_path, origen):
        carpeta = str(tmp_path / "respaldos")
        assert respaldo.respaldar_al_cerrar(ruta_origen=origen, carpeta_destino=carpeta) is not None
        assert os.path.isfile(_leeme(carpeta))

    def test_no_se_reescribe_si_ya_existe(self, tmp_path, origen):
        carpeta = str(tmp_path / "respaldos")
        os.makedirs(carpeta)
        with open(_leeme(carpeta), "w", encoding="utf-8") as f:
            f.write("texto que escribio una persona\n")
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta)
        assert open(_leeme(carpeta), encoding="utf-8").read() == "texto que escribio una persona\n"

    def test_un_respaldo_tras_otro_dejan_un_solo_archivo(self, tmp_path, origen):
        carpeta = str(tmp_path / "respaldos")
        for _ in range(3):
            respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta)
        assert [n for n in os.listdir(carpeta) if "LEEME" in n] == [respaldo.NOMBRE_LEEME_RESTAURAR]

    def test_no_cuenta_como_respaldo_ni_lo_borra_la_rotacion(self, tmp_path, origen):
        carpeta = str(tmp_path / "respaldos")
        for i in range(respaldo.MAX_RESPALDOS + 3):
            respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, max_copias=3, ahora=respaldo.datetime(2026, 10, 8, 10, 0, i))
        assert respaldo.NOMBRE_LEEME_RESTAURAR not in respaldo._nombres_respaldo(carpeta)
        assert os.path.isfile(_leeme(carpeta)), "la rotacion borra respaldos viejos, no el LEEME"
        assert len(respaldo._nombres_respaldo(carpeta)) == 3

    def test_si_no_hay_base_de_origen_no_se_crea_la_carpeta_ni_el_leeme(self, tmp_path):
        carpeta = str(tmp_path / "respaldos")
        assert respaldo.respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=carpeta) is None
        assert not os.path.exists(carpeta)

    def test_una_copia_que_falla_no_deja_ni_el_leeme(self, tmp_path, origen, monkeypatch):
        """El LEEME aparece junto al primer respaldo HECHO: un fallo no deja nada en la carpeta (RB.1: «no deja nada»)."""
        monkeypatch.setattr(respaldo, "_copiar_con_api", lambda o, p: (_ for _ in ()).throw(OSError("disco lleno")))
        carpeta = str(tmp_path / "respaldos")
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta) is None
        assert os.listdir(carpeta) == []

    def test_un_leeme_que_no_se_puede_escribir_no_impide_el_respaldo(self, tmp_path, origen, monkeypatch):
        def falla(ruta, texto):
            raise OSError("sin permiso")
        monkeypatch.setattr(respaldo, "_crear_exclusivo", falla)
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "respaldos")) is not None


class TestSeguirElProcedimientoRestauraExactamenteElRespaldo:
    """El caso de V4 con SQLite de verdad: un `-wal` con contenido junto al `.db`."""

    def _caida(self, tmp_path):
        """Una base viva con un respaldo hecho en T1 y mas filas en T2 que quedan SOLO en el `-wal`; devuelve (carpeta de la caida, ruta del respaldo, filas del respaldo, filas en T2)."""
        vivo = tmp_path / "vivo"
        vivo.mkdir()
        db = str(vivo / "BaseDatosQA.db")
        con = sqlite3.connect(db)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_autocheckpoint=0")
        con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
        con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i}",) for i in range(100)])
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"t1 {i}",) for i in range(200)])
        con.commit()
        copia = respaldo.respaldar_bd(ruta_origen=db, carpeta_destino=str(tmp_path / "respaldos"))
        assert copia is not None
        filas_respaldo = sqlite3.connect(copia).execute("SELECT COUNT(*) FROM datos").fetchone()[0]
        con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"t2 {i}",) for i in range(300)])
        con.commit()                                                   # estas 300 viven solo en el -wal: la app sigue abierta o se cayo
        assert os.path.getsize(db + "-wal") > 0
        caida = tmp_path / "tras_la_caida"
        caida.mkdir()
        for sufijo in ("", "-wal", "-shm"):
            if os.path.exists(db + sufijo):
                shutil.copy2(db + sufijo, str(caida / ("BaseDatosQA.db" + sufijo)))
        con.close()
        return str(caida), copia, filas_respaldo, filas_respaldo + 300

    @staticmethod
    def _filas(ruta):
        con = sqlite3.connect(ruta)
        try:
            return con.execute("SELECT COUNT(*) FROM datos").fetchone()[0], con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()

    @staticmethod
    def _ejecutar_el_leeme(texto, caida, copia):
        """Hace lo que el LEEME dice, en el orden en que lo dice (numerado): el paso que empieza por «Mueva» aparta los archivos que NOMBRA y el que empieza por «Copie el respaldo» lo copia con
        el nombre que NOMBRA. Si el texto invierte los pasos o pierde uno, la base restaurada no existe o no es el respaldo."""
        pasos = {int(m.group(1)): m.group(2) for m in re.finditer(r"^(\d)\. (.*)$", texto, re.M)}
        aparte = os.path.join(caida, "movidos")
        for numero in sorted(pasos):
            paso = pasos[numero]
            if paso.startswith("Mueva"):
                os.makedirs(aparte, exist_ok=True)
                for nombre in dict.fromkeys(re.findall(r"BaseDatosQA\.db(?:-wal|-shm)?", paso)):
                    if os.path.exists(os.path.join(caida, nombre)):
                        shutil.move(os.path.join(caida, nombre), os.path.join(aparte, nombre))
            elif paso.startswith("Copie el respaldo"):
                shutil.copy2(copia, os.path.join(caida, re.search(r"con el nombre (BaseDatosQA\.db)\b", paso).group(1)))
        return aparte

    def test_el_procedimiento_del_leeme_restaura_exactamente_el_respaldo(self, tmp_path):
        """Ejecuta el LEEME ENTREGADO (el texto de `respaldo.TEXTO_LEEME_RESTAURAR`), no un procedimiento escrito a mano en la prueba."""
        caida, copia, filas_respaldo, _ = self._caida(tmp_path)
        aparte = self._ejecutar_el_leeme(respaldo.TEXTO_LEEME_RESTAURAR, caida, copia)
        assert os.path.getsize(os.path.join(aparte, "BaseDatosQA.db-wal")) > 0, "el escenario es el de V4: habia un -wal con contenido que el procedimiento aparta"
        assert self._filas(os.path.join(caida, "BaseDatosQA.db")) == (filas_respaldo, "ok")

    def test_con_los_pasos_invertidos_el_procedimiento_destruye_lo_restaurado(self, tmp_path):
        """Control del ejecutor: si el texto mandara copiar ANTES de mover, la base restaurada se aparta y no queda base."""
        caida, copia, filas_respaldo, _ = self._caida(tmp_path)
        invertido = respaldo.TEXTO_LEEME_RESTAURAR.replace("2. Mueva", "3. Mueva").replace("3. Copie", "2. Copie")
        self._ejecutar_el_leeme(invertido, caida, copia)
        assert not os.path.exists(os.path.join(caida, "BaseDatosQA.db")), "con los pasos invertidos el restaurado se aparta"

    def test_sin_el_paso_de_copiar_no_hay_base(self, tmp_path):
        caida, copia, _, _ = self._caida(tmp_path)
        sin_copia = "\n".join(l for l in respaldo.TEXTO_LEEME_RESTAURAR.splitlines() if not l.startswith("3. "))
        self._ejecutar_el_leeme(sin_copia, caida, copia)
        assert not os.path.exists(os.path.join(caida, "BaseDatosQA.db"))

    def test_control_la_restauracion_ingenua_NO_restaura_el_respaldo(self, tmp_path):
        """El defecto que el LEEME evita: copiar el respaldo encima y dejar el `-wal` viejo. SQLite aplica el `-wal` encima del archivo restaurado: salen las filas de DESPUES del respaldo, con la
        integridad en ok y sin ningun aviso. Si algun dia SQLite dejara de hacerlo, esta prueba lo dice y el LEEME se puede revisar."""
        caida, copia, filas_respaldo, filas_t2 = self._caida(tmp_path)
        shutil.copy2(copia, os.path.join(caida, "BaseDatosQA.db"))
        filas, integridad = self._filas(os.path.join(caida, "BaseDatosQA.db"))
        assert filas != filas_respaldo, "la restauracion ingenua deberia haber dejado filas que NO son las del respaldo"
        assert integridad == "ok", "y sin que nada lo delate"


class TestElRunbook:

    def _texto(self):
        with open(os.path.join(RAIZ, "RUNBOOK_MIGRAR_BD.md"), encoding="utf-8") as f:
            return f.read()

    def test_el_paso_3_manda_cerrar_y_mover_el_wal_antes_de_copiar(self):
        paso3 = re.search(r"### Paso 3.*?(?=\n---)", self._texto(), re.S).group(0)
        for clave in ("Cierre RAD-QA", "`BaseDatosQA.db-wal`", "`BaseDatosQA.db-shm`", "Mueva a otra carpeta (sin borrar)"):
            assert clave in paso3, clave

    def test_la_frase_falsa_sobre_el_cierre_ya_no_esta(self):
        texto = self._texto()
        assert "al cerrar, la app deja el `.db` completo)" not in texto
        assert "volver a «Inicio» no es cerrarla" in texto

    def test_deshacer_una_migracion_tambien_mueve_el_wal(self):
        deshacer = re.search(r"\*\*¿Cómo deshago una migración\?\*\*.*?(?=\n\n|\Z)", self._texto(), re.S).group(0)
        assert "`BaseDatosQA.db-wal`" in deshacer and "Cierre RAD-QA" in deshacer and "Paso 3" in deshacer
