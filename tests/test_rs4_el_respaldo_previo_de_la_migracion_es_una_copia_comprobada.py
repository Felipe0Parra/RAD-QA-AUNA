"""RS.4 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, C4): el respaldo previo de la herramienta de migración es una copia COMPROBADA.

Antes `scripts/migrar_bd_a_estandar.py --aplicar` copiaba solo el archivo `.db` (`shutil.copy`) después de un `wal_checkpoint(TRUNCATE)` cuyo resultado ignoraba. Con una lectura a medias de otro
programa (la herramienta sobre la base con la aplicación abierta) el checkpoint no termina, parte de lo confirmado sigue SOLO en el `-wal` y el `.bak` salió con 534 de 684 filas, integridad `ok` y
`rc=0`, en 5 de 5 corridas (`c4_migrar_s2x5.log`). Es la clase que `RB.1` cerró en `services/respaldo.py`.

Ahora el respaldo se hace con la misma función que los de la aplicación (la API de respaldo de SQLite: una foto consistente que incluye lo que solo vive en el `-wal`), se comprueba su integridad
y que tiene TODAS las filas de cada tabla, y solo entonces se renombra; si no queda íntegro y completo, la migración no corre ("antes de cambiar la base, la herramienta guarda una copia completa o no
hace nada"). El escenario es el real: un lector con una lectura abierta, otro que escribe después de que ese lector empezó, y la herramienta aplicando.
"""
import ast
import os
import re
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import scripts.migrar_bd_a_estandar as herramienta
from scripts.migrar_bd_a_estandar import migrar
from test_m1_migrar_bd_a_estandar import _crear_bd_vieja

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILAS_NUEVAS = 150


def _insertar_filas(con, n=FILAS_NUEVAS):
    for i in range(n):
        con.execute("INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) VALUES ('Clinac 600', 'Mensual', ?, 'Físico de Prueba', 'Otro Físico')", (f"{i:03d}/2026",))
    con.commit()


@pytest.fixture
def base_con_un_lector_a_medias(tmp_path):
    """La base real del incidente en miniatura: modo WAL, un lector con una lectura ABIERTA (su foto del `-wal` es la inicial) y un escritor que confirma 150 filas DESPUÉS de que ese lector
    empezó: el checkpoint no puede pasarlas al `.db` mientras el lector siga ahí, así que viven solo en el `-wal`."""
    ruta = str(tmp_path / "bd.db")
    _crear_bd_vieja(ruta)
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    con.close()
    lector = sqlite3.connect(ruta)
    lector.execute("BEGIN")
    lector.execute("SELECT COUNT(*) FROM controles").fetchone()
    escritor = sqlite3.connect(ruta)
    escritor.execute("PRAGMA wal_autocheckpoint=0")
    _insertar_filas(escritor)
    yield ruta, lector, escritor
    for con in (lector, escritor):
        try:
            con.rollback()
            con.close()
        except Exception:
            pass


def _filas(ruta, tabla="controles"):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    finally:
        con.close()


def _sobrantes(carpeta):
    return sorted(n for n in os.listdir(carpeta) if n.endswith(".parcial") or "-journal" in n)


class TestElEscenarioDelIncidente:

    def test_el_respaldo_tiene_las_filas_que_solo_vivian_en_el_wal(self, base_con_un_lector_a_medias):
        """534 de 684 filas, integridad ok y rc=0 (en 5 de 5 corridas) antes de RS.4."""
        ruta, lector, escritor = base_con_un_lector_a_medias
        assert os.path.getsize(ruta + "-wal") > 0 and _filas(ruta) == 2 + FILAS_NUEVAS, "el escenario no se armo: las filas nuevas deben vivir solo en el -wal"
        resultado = migrar(ruta, aplicar=True)
        assert _filas(resultado["respaldo"]) == 2 + FILAS_NUEVAS, "el respaldo previo perdio las filas que vivian solo en el -wal"
        assert _filas(ruta) == 2 + FILAS_NUEVAS

    def test_el_respaldo_es_un_solo_archivo_autocontenido_y_integro(self, base_con_un_lector_a_medias):
        ruta, lector, escritor = base_con_un_lector_a_medias
        respaldo = migrar(ruta, aplicar=True)["respaldo"]
        assert not os.path.exists(respaldo + "-wal") and not os.path.exists(respaldo + "-shm")
        con = sqlite3.connect(respaldo)
        try:
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert con.execute("PRAGMA journal_mode").fetchone()[0] == "delete", "el respaldo hereda el modo WAL: abrirlo crearia un -wal junto a el"
        finally:
            con.close()

    def test_el_respaldo_conserva_el_esquema_anterior_a_la_migracion(self, base_con_un_lector_a_medias):
        """Es la copia de ANTES: sin las columnas que la migracion agrega."""
        ruta, lector, escritor = base_con_un_lector_a_medias
        respaldo = migrar(ruta, aplicar=True)["respaldo"]
        columnas = lambda r: [c[1] for c in sqlite3.connect(r).execute("PRAGMA table_info(controles)").fetchall()]
        assert "activo" not in columnas(respaldo) and "activo" in columnas(ruta)

    def test_el_nombre_del_respaldo_no_cambia(self, base_con_un_lector_a_medias):
        ruta, lector, escritor = base_con_un_lector_a_medias
        respaldo = migrar(ruta, aplicar=True)["respaldo"]
        assert re.fullmatch(re.escape(ruta) + r"\.pre_migracion_\d{8}_\d{6}\.bak", respaldo), respaldo

    def test_no_queda_ningun_archivo_provisional(self, base_con_un_lector_a_medias, tmp_path):
        ruta, lector, escritor = base_con_un_lector_a_medias
        migrar(ruta, aplicar=True)
        assert _sobrantes(tmp_path) == []


class TestSiLaCopiaNoQuedaIntegraYCompletaLaMigracionNoCorre:

    def _debe_abortar_sin_tocar_nada(self, ruta, tmp_path, capsys, texto):
        antes = sorted(os.listdir(tmp_path))
        with pytest.raises(SystemExit) as salida:
            migrar(ruta, aplicar=True)
        assert salida.value.code == 1
        salida_texto = capsys.readouterr().out
        assert "ALERTA" in salida_texto and "Se aborta sin hacer ningún cambio" in salida_texto and texto in salida_texto, salida_texto
        assert not any(".pre_migracion_" in n for n in os.listdir(tmp_path)), "no debe quedar un respaldo a medias"
        assert _sobrantes(tmp_path) == []
        con = sqlite3.connect(ruta)
        try:
            assert "activo" not in [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()], "la migracion corrio aunque no habia respaldo"
        finally:
            con.close()
        assert sorted(n for n in os.listdir(tmp_path) if not n.endswith(("-wal", "-shm"))) == [n for n in antes if not n.endswith(("-wal", "-shm"))]

    def test_la_copia_falla(self, tmp_path, monkeypatch, capsys):
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)

        def copia_rota(origen, parcial):
            with open(parcial, "wb") as f:
                f.write(b"a medias")
            raise OSError("disco lleno")
        monkeypatch.setattr(herramienta, "_copiar_con_api", copia_rota)
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "disco lleno")

    def test_la_copia_no_pasa_la_comprobacion_de_integridad(self, tmp_path, monkeypatch, capsys):
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)
        monkeypatch.setattr(herramienta, "_integridad", lambda r: ("defecto", "database disk image is malformed"))
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "database disk image is malformed")

    def test_la_integridad_se_comprueba_en_la_copia_y_no_en_la_base(self, tmp_path, monkeypatch, capsys):
        """Revision (hallazgo 1, medio): la prueba de arriba sustituye `_integridad` por una lambda que dice «defecto» sea cual sea la ruta, asi que comprobar la integridad de la BASE (que esta bien) en lugar de
        la de la copia no la hacia caer. Aqui la funcion es sensible a la ruta: solo la copia (el archivo provisional) esta mal."""
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)
        vistas = []

        def integridad_de_la_ruta(r):
            vistas.append(r)
            return ("defecto", "database disk image is malformed") if str(r).endswith(".parcial") else ("ok", None)
        monkeypatch.setattr(herramienta, "_integridad", integridad_de_la_ruta)
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "database disk image is malformed")
        assert vistas and all(v.endswith(".parcial") for v in vistas), vistas

    def test_una_copia_que_falla_a_medias_no_deja_ni_el_journal(self, tmp_path, monkeypatch, capsys):
        """Revision (hallazgo 2): una copia que se corta (disco lleno...) deja a veces un `-journal` junto al provisional; limpiar solo el `.parcial` lo dejaba huerfano."""
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)

        def copia_con_journal(origen, parcial):
            with open(parcial, "wb") as f:
                f.write(b"a medias")
            with open(parcial + "-journal", "wb") as f:
                f.write(b"journal a medias")
            raise OSError("disco lleno")
        monkeypatch.setattr(herramienta, "_copiar_con_api", copia_con_journal)
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "disco lleno")

    def test_no_se_puede_dejar_la_copia_con_su_nombre_definitivo(self, tmp_path, monkeypatch, capsys):
        """Revision (hallazgo 3, Windows): un antivirus o el indexador con el archivo abierto hace fallar el renombrado con `PermissionError`. La garantia «copia completa o nada» se cumplia, pero el fisico
        veia una traza de Python en lugar de la ALERTA."""
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)

        def en_uso(origen, destino):
            raise PermissionError(13, "El proceso no tiene acceso al archivo porque esta siendo utilizado por otro proceso")
        monkeypatch.setattr(herramienta.os, "replace", en_uso)
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "esta siendo utilizado por otro proceso")

    def test_la_comprobacion_no_concluye(self, tmp_path, monkeypatch, capsys):
        """Una copia que no se pudo certificar no vale como respaldo."""
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)
        monkeypatch.setattr(herramienta, "_integridad", lambda r: ("no_concluyente", "database is locked"))
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "database is locked")

    def test_a_la_copia_le_faltan_filas(self, tmp_path, monkeypatch, capsys):
        """Otro programa escribio en la base mientras se copiaba: la copia es una foto anterior y no tiene todas las filas."""
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)
        original = herramienta._copiar_con_api

        def copiar_y_que_otro_escriba(origen, parcial):
            original(origen, parcial)
            con = sqlite3.connect(origen)
            _insertar_filas(con, 3)
            con.close()
        monkeypatch.setattr(herramienta, "_copiar_con_api", copiar_y_que_otro_escriba)
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "controles: 5 filas en la base y 2 en la copia")

    def test_a_la_copia_le_sobran_filas(self, tmp_path, monkeypatch, capsys):
        """Revision (hallazgo 5): otro programa BORRA filas de la base entre la copia y el conteo: la copia tiene MAS filas que la base. Tambien es una copia que no es la base: se rechaza."""
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)
        original = herramienta._copiar_con_api

        def copiar_y_que_otro_borre(origen, parcial):
            original(origen, parcial)
            con = sqlite3.connect(origen)
            con.execute("DELETE FROM controles WHERE id = (SELECT MAX(id) FROM controles)")
            con.commit()
            con.close()
        monkeypatch.setattr(herramienta, "_copiar_con_api", copiar_y_que_otro_borre)
        self._debe_abortar_sin_tocar_nada(ruta, tmp_path, capsys, "controles: 1 filas en la base y 2 en la copia")


class TestElCheckpointYaNoSeIgnora:

    def test_con_un_lector_a_medias_se_avisa(self, base_con_un_lector_a_medias, capsys):
        ruta, lector, escritor = base_con_un_lector_a_medias
        herramienta._consolidar_wal(ruta)
        salida = capsys.readouterr().out
        assert "AVISO" in salida and "no se pudo consolidar" in salida and "otro programa" in salida, salida
        assert os.path.getsize(ruta + "-wal") > 0, "el escenario es el del lector a medias: el -wal no se pudo vaciar"

    def test_sin_nadie_mas_consolida_en_silencio(self, tmp_path, capsys):
        ruta = str(tmp_path / "bd.db")
        _crear_bd_vieja(ruta)
        con = sqlite3.connect(ruta)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA wal_autocheckpoint=0")
            _insertar_filas(con, 5)
            assert os.path.getsize(ruta + "-wal") > 0, "el escenario no se armo: las filas nuevas viven solo en el -wal (con esta conexion todavia abierta, que es lo que impide el checkpoint automatico al cerrar)"
            herramienta._consolidar_wal(ruta)
            assert capsys.readouterr().out == ""
            assert os.path.getsize(ruta + "-wal") == 0, "sin nadie mas leyendo, el -wal queda integrado en el .db"
            assert _filas(ruta) == 2 + 5
        finally:
            con.close()

    def test_el_aviso_sale_en_el_camino_de_aplicar(self, base_con_un_lector_a_medias, capsys):
        ruta, lector, escritor = base_con_un_lector_a_medias
        migrar(ruta, aplicar=True)
        assert "no se pudo consolidar el archivo -wal" in capsys.readouterr().out


class TestFilasQueFaltan:

    def _par(self, tmp_path, filas_base, filas_copia, tablas_copia=("t",)):
        base, copia = str(tmp_path / "base.db"), str(tmp_path / "copia.db")
        for ruta, n, tablas in ((base, filas_base, ("t",)), (copia, filas_copia, tablas_copia)):
            con = sqlite3.connect(ruta)
            for t in tablas:
                con.execute(f"CREATE TABLE {t} (x INTEGER)")
                con.executemany(f"INSERT INTO {t} VALUES (?)", [(i,) for i in range(n)])
            con.commit()
            con.close()
        return base, copia

    def test_iguales(self, tmp_path):
        assert herramienta._filas_que_faltan(*self._par(tmp_path, 4, 4)) == []

    def test_menos_filas_en_la_copia(self, tmp_path):
        assert herramienta._filas_que_faltan(*self._par(tmp_path, 4, 3)) == [("t", 4, 3)]

    def test_una_tabla_que_la_copia_no_tiene(self, tmp_path):
        assert herramienta._filas_que_faltan(*self._par(tmp_path, 4, 4, tablas_copia=("u",))) == [("t", 4, None), ("u", None, 4)]


def test_la_herramienta_ya_no_respalda_copiando_solo_el_db():
    """Tripwire (AST): `migrar` no vuelve a copiar el archivo `.db` con `shutil.copy` como respaldo; el respaldo pasa por `_respaldo_previo`, y esta por la API de respaldo, la comprobacion de
    integridad y el conteo de filas."""
    with open(os.path.join(RAIZ, "scripts", "migrar_bd_a_estandar.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    funciones = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}

    def llamadas(nodo):
        return [n for n in ast.walk(nodo) if isinstance(n, ast.Call)]

    def nombre(c):
        f = c.func
        return f"{f.value.id}.{f.attr}" if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else (f.id if isinstance(f, ast.Name) else None)

    migrar_fn = funciones["migrar"]
    copias_del_db = [c for c in llamadas(migrar_fn) if nombre(c) == "shutil.copy" and c.args and isinstance(c.args[0], ast.Name) and c.args[0].id == "ruta_bd"]
    assert copias_del_db == [], "migrar vuelve a respaldar copiando solo el .db"
    assert "_respaldo_previo" in {nombre(c) for c in llamadas(migrar_fn)}
    usadas = {nombre(c) for c in llamadas(funciones["_respaldo_previo"])}
    assert {"_copiar_con_api", "_integridad", "_filas_que_faltan", "_nombre_provisional", "os.replace"} <= usadas, usadas
